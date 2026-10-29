"""0.24.86 High-poly cut: the boolean only on the faces round the cutter.

A Cut / Split on a dense part (hundreds of thousands of faces) spent its time in Blender's boolean walking the
whole part for a few hundred new faces.  Here the faces near the cutter (its box, a margin, two rings) are taken out
as an open patch and two small Exact booleans are run on it:

* ``patch - cutter``  -> the patch's faces outside the cutter, split along the cut line
* ``cutter & patch``  -> the cutter's faces inside the part (the cut's walls; the patch piece inside the cutter comes
  along as a cap and is dropped)

(the Exact solver classifies against the CLOSED operand, so each result is right where we read it; a face's origin is
carried by a face INT attribute through the boolean).  The two results are stitched back onto the untouched faces:
points on the seams welded by position (KD tree, a millionth of the part), the rest of the part's points, faces and
attributes untouched.  Everything is checked at the end - open edges must not grow - and the caller falls back to
the whole-part boolean when the check fails or the cutter reaches outside the region.

Manifold on 1.3M faces: 3.2 s, Exact 9.6 s; this: ~1.3 s, most of it reading the big arrays.
"""
from __future__ import annotations

import os
import time

import bpy
import numpy as np
from mathutils.kdtree import KDTree

from . import mesh_io as mio

TAG = 'mch_region_src'
SRC = 'mch_region_face'
LAST_TIMES = {}                   # the last region boolean's stage times (region / extract / boolean / knife / sort / stitch)
_PRE_TIDY = {}                    # the tidy run on the region sub-mesh inside the stitch (counts, seconds)
LAST_REGION = {}                  # the last stitched result: {'name': mesh name, 'faces': total, 'untouched': first N faces untouched}
TIDY_SUB_MIN = 50_000             # faces: below this the whole-mesh tidy is as fast as taking the region out
MIN_FACES = int(os.environ.get('MECH_REGION_MIN', 100_000))   # (below this the whole-part boolean is as fast)
MARGIN = 0.15                     # of the cutter's box diagonal, each side
RINGS = 2
_SKIP = {'position', '.edge_verts', '.corner_vert', '.corner_edge', TAG, SRC}
_TYPES = {'FLOAT': ('value', 1, np.float32), 'INT': ('value', 1, np.int32), 'INT8': ('value', 1, np.int32),
          'BOOLEAN': ('value', 1, bool), 'FLOAT_VECTOR': ('vector', 3, np.float32), 'FLOAT2': ('vector', 2, np.float32),
          'FLOAT_COLOR': ('color', 4, np.float32), 'BYTE_COLOR': ('color', 4, np.float32),
          'INT32_2D': ('value', 2, np.int32), 'QUATERNION': ('value', 4, np.float32)}


def arrays(me):
    """(points (n, 3) float64, face sizes, face starts, corner point indices int64) - from the mesh's built-in
    attributes (0.24.86: 0.36 s -> 0.06 s on 1.3M faces)."""
    start, tot = mio.read_face_starts(me)
    return mio.read_co(me), tot, start, mio.read_corner_verts(me)


def _shared_points(vi, lm, nv):
    """Points used by corners on both sides of the corner mask ``lm`` (the rim between two face sets).  Two
    boolean marks: ``np.intersect1d`` sorted the 3.9M corners of a 1.3M-face part (0.5 s); this is 15 ms."""
    a = np.zeros(nv, bool)
    b = np.zeros(nv, bool)
    a[vi[lm]] = True
    b[vi[~lm]] = True
    return np.flatnonzero(a & b)


def build(V, corners, sizes, name, like=None):
    """A mesh from arrays; ``like``: an empty copy of that mesh (materials, settings, custom props) is filled."""
    if like is not None:
        from .fast_decimate import fresh_like
        m = fresh_like(like)
        m.name = name
    else:
        m = bpy.data.meshes.new(name)
    if not len(sizes):
        return m                                    # (an empty mesh to fill later)
    m.vertices.add(len(V))
    mio.write_co(m, V)
    m.loops.add(len(corners))
    mio.write_corner_verts(m, corners)
    m.polygons.add(len(sizes))
    m.polygons.foreach_set('loop_start', np.concatenate([[0], np.cumsum(sizes)[:-1]]).astype(np.int32))
    m.update(calc_edges=True)
    return m


def _boundary_verts(corners, sizes):
    """Indices of points on edges used by one face only (the open rim of a patch)."""
    if not len(corners):
        return np.zeros(0, np.int64)
    start = np.concatenate([[0], np.cumsum(sizes)[:-1]])
    nxt = np.arange(1, len(corners) + 1)
    nxt[start + sizes - 1] = start
    a, b = corners, corners[nxt]
    key = np.minimum(a, b) * (int(corners.max()) + 1) + np.maximum(a, b)
    u, cnt = np.unique(key, return_counts=True)
    single = np.isin(key, u[cnt == 1])
    return np.unique(np.concatenate([a[single], b[single]]))


def _tagged(me, want):
    at = me.attributes.get(TAG)
    v = np.zeros(len(me.polygons), np.int32)
    if at is not None and at.domain == 'FACE':
        at.data.foreach_get('value', v)
    return v == want


def _read_attr(me, name, domain, dtype):
    a = me.attributes.get(name)
    if a is None or a.domain != domain or a.data_type != dtype or a.data_type not in _TYPES:
        return None
    key, w, dt = _TYPES[dtype]
    vals = np.empty(len(a.data) * w, dt)
    a.data.foreach_get(key, vals)
    return vals.reshape(len(a.data), w)


def _attr_list(me):
    out = []
    for a in me.attributes:
        if a.name in _SKIP or a.domain not in {'POINT', 'FACE', 'CORNER', 'EDGE'} or a.data_type not in _TYPES:
            continue
        if a.name.startswith(('.select', '.vs.', '.es.', '.pn.', '.uv')):
            continue
        out.append((a.name, a.domain, a.data_type))
    return out


def _frame(cb):
    """An orthonormal frame aligned with the cutter's own axes (PCA of its points): a lasso cutter is a long prism
    along the view, and its world box would take in most of the part."""
    mu = cb.mean(0)
    d = cb - mu
    cov = d.T @ d
    try:
        _w, R = np.linalg.eigh(cov)
    except np.linalg.LinAlgError:
        R = np.eye(3)
    return mu, R


def region_mask(co, tot, start, vi, lo, hi, rings=RINGS, frame=None):
    """Faces with a point inside the box lo..hi (in ``frame`` = (origin, 3x3 axes) when given), grown by ``rings``."""
    pts = co if frame is None else (co - frame[0]) @ frame[1]
    inside = np.all((pts >= lo) & (pts <= hi), axis=1)
    fmask = np.maximum.reduceat(inside[vi].astype(np.int8), start).astype(bool)
    for _ in range(rings):
        vm = np.zeros(len(co), bool)
        vm[vi[np.repeat(fmask, tot)]] = True
        fmask = np.maximum.reduceat(vm[vi].astype(np.int8), start).astype(bool)
    return fmask


def region_boolean(context, target, cutter, operation, log=None):
    """The ``operation`` (DIFFERENCE / INTERSECT) of ``target`` with the closed ``cutter`` done on the faces round the
    cutter only.  Returns a new mesh (caller owns it) or None when it should not be used (too few faces, the cutter
    reaches outside the region, open edges grew)."""
    from . import core_geometry as cg
    me = target.data
    if operation not in {'DIFFERENCE', 'INTERSECT'} or len(me.polygons) < MIN_FACES or not len(cutter.data.polygons):
        return None
    if me.shape_keys is not None or cutter.type != 'MESH':
        return None
    t0 = time.perf_counter()
    try:
        context.view_layer.update()            # (a cutter linked a moment ago: its matrix_world is not set yet)
    except (AttributeError, RuntimeError):
        pass
    co, tot, start, vi = arrays(me)
    inv = target.matrix_world.inverted()
    cb = np.array([(inv @ (cutter.matrix_world @ v.co))[:] for v in cutter.data.vertices])
    mu, R = _frame(cb)
    cl = (cb - mu) @ R
    lo, hi = cl.min(0), cl.max(0)
    ext = hi - lo
    if not (ext > 0).any():
        return None
    m = MARGIN * float(np.sort(ext)[1])     # (of the cutter's middle extent: a long prism's width, not its depth)
    fmask = region_mask(co, tot, start, vi, lo - m, hi + m, frame=(mu, R))
    fmask0 = fmask
    nreg = int(fmask.sum())
    t0b = time.perf_counter()
    if os.environ.get('MECH_REGION_DEBUG'):
        print(f'[region] cutter {len(cb)} pts ext {np.round(ext, 3).tolist()} margin {m:.3f} region {nreg:,} of {len(tot):,} '
              f'cutter at {np.round(np.array(cutter.matrix_world.translation), 3).tolist()} target at {np.round(np.array(target.matrix_world.translation), 3).tolist()}', flush=True)
    if nreg == 0 or nreg > 0.6 * len(tot):           # (nothing near, or most of the part: no gain)
        return None
    # the patch (region faces, points compacted) with its origin tag
    lm = np.repeat(fmask, tot)
    pverts, pcorners = np.unique(vi[lm], return_inverse=True)
    patch = build(co[pverts], pcorners, tot[fmask], 'MCH_RegionPatch', like=me)   # (its material slots: the solver
                                                                                #  clamps indices to the slots it has)
    a = patch.attributes.new(TAG, 'INT', 'FACE')
    a.data.foreach_set('value', np.ones(len(patch.polygons), np.int32))
    a = patch.attributes.new(SRC, 'INT', 'FACE')              # (which part face each triangle came from: the quads
    a.data.foreach_set('value', np.nonzero(fmask)[0].astype(np.int32))   #  are put back together after the boolean)
    for name, domain, dtype in _attr_list(me):        # (the patch carries the part's attributes into the boolean)
        vals = _read_attr(me, name, domain, dtype)
        if vals is None or domain == 'EDGE':
            continue
        idx = pverts if domain == 'POINT' else (np.nonzero(fmask)[0] if domain == 'FACE' else np.nonzero(lm)[0])
        try:
            b = patch.attributes.new(name, dtype, domain)
            b.data.foreach_set(_TYPES[dtype][0], vals[idx].ravel())
        except (RuntimeError, TypeError, ValueError):
            pass
    # the patch's quads / n-gons split into triangles once, here: the boolean and the knife then see the same
    # triangles and cut the same seam (each would split a non-planar quad its own way - a T-junction per quad)
    if int(tot[fmask].max()) > 3:
        import bmesh
        bmp = bmesh.new()
        try:
            bmp.from_mesh(patch)
            bmesh.ops.triangulate(bmp, faces=[f for f in bmp.faces if len(f.verts) > 3], quad_method='BEAUTY', ngon_method='BEAUTY')
            bmp.to_mesh(patch)
        finally:
            bmp.free()
        patch.update()
    pco, ptot, _pst, pvi = arrays(patch)
    tmp = bpy.data.objects.new('MCH_RegionPatch', patch)
    context.scene.collection.objects.link(tmp)
    tmp.matrix_world = target.matrix_world.copy()
    # the cutter's faces tagged 2 for the time of the booleans (a face's origin is then never a guess: the solver
    # fills a missing attribute as it likes)
    cme = cutter.data
    had = cme.attributes.get(TAG)
    if had is not None:
        cme.attributes.remove(had)
    ct = cme.attributes.new(TAG, 'INT', 'FACE')
    ct.data.foreach_set('value', np.full(len(cme.polygons), 2, np.int32))
    t1 = time.perf_counter()
    M = np.array(target.matrix_world.inverted() @ cutter.matrix_world)
    try:
        if operation == 'DIFFERENCE':
            kept = cg.evaluate_boolean(context, tmp, cutter, 'DIFFERENCE', 'EXACT')
        else:
            kept = cg.evaluate_boolean(context, tmp, cutter, 'INTERSECT', 'EXACT')
        # the slivers the solver leaves at the seam (edges a millionth long, zero-size faces): welded away on the
        # small result now, not found as open edges on the whole part later (a 1.3M-face part: 3.7 s of hole work)
        try:
            _clean_seam(kept, float(np.linalg.norm(co.max(0) - co.min(0))))
        except (RuntimeError, ValueError):
            pass
        t1b = time.perf_counter()
        # the cutter's walls: the solver sorts the cutter's pieces by the patch's winding number, which an open
        # patch cannot give (a thin column through a part: the pieces inside vanish from Intersect, Union and
        # Difference alike) - so the cutter is only SPLIT along the patch (Edit-mode Intersect / Knife, no sorting)
        # and the pieces are sorted here, by a ray along the cutter's axis (``_walls``)
        pieces = _knife_pieces(context, target, cutter, pco, pvi, ptot, M)
    except Exception:
        bpy.data.objects.remove(tmp)
        bpy.data.meshes.remove(patch)
        return None
    finally:
        ct = cme.attributes.get(TAG)
        if ct is not None:
            cme.attributes.remove(ct)
    t2 = time.perf_counter()
    if os.environ.get('MECH_REGION_DEBUG'):
        print(f'[region] patch {len(patch.polygons)} -> kept {len(kept.polygons)} (patch-tagged {int(_tagged(kept, 1).sum())}) '
              f'cutter pieces {len(pieces[2]) if pieces is not None else None} (cutter faces {len(cutter.data.polygons)})', flush=True)
    try:
        if pieces is None:
            return None
        wV, wC, wS = _walls(patch, pieces, R)
        t2b = time.perf_counter()
        if os.environ.get('MECH_REGION_DEBUG'):
            print(f'[region] walls inside the part: {len(wS)} faces', flush=True)
        # nothing cut (the cutter is in the box but misses the surface): the whole-part path says so properly
        if not len(wS) and len(kept.polygons) == len(patch.polygons):
            return None
        if operation == 'INTERSECT' and not _tagged(kept, 1).any():
            return None
        if operation == 'INTERSECT':               # (the piece inside the cutter: none of the untouched faces)
            fmask = np.ones(len(tot), bool)
            lm = np.ones(len(vi), bool)
        rim = pverts[_boundary_verts(pcorners, tot[fmask] if operation != 'INTERSECT' else tot[fmask0])]
        out = _stitch(me, co, tot, vi, fmask, lm, kept, (wV, wC, wS), target, cutter, rim, operation)
    finally:
        bpy.data.objects.remove(tmp)
        for mm in (patch, kept):
            bpy.data.meshes.remove(mm)
    t3 = time.perf_counter()
    LAST_TIMES.clear()
    LAST_TIMES.update(region=t0b - t0, extract=t1 - t0b, boolean=t1b - t1, knife=t2 - t1b, sort=t2b - t2,
                      stitch=t3 - t2b, faces_region=nreg, faces_total=len(tot), walls=int(len(wS)),
                      tidy=_PRE_TIDY.get('counts'), tidy_s=_PRE_TIDY.get('s', 0.0))
    _PRE_TIDY.clear()
    if log is not None:
        log.append(f'region {nreg:,} of {len(tot):,} faces: region {t0b - t0:.2f} extract {t1 - t0b:.2f} boolean {t1b - t1:.2f} '
                   f'knife {t2 - t1b:.2f} sort {t2b - t2:.2f} stitch {t3 - t2b:.2f} s (tidy {LAST_TIMES["tidy_s"]:.2f} s in the stitch)')
    return out


def _clean_seam(kept, size):
    """The Exact solver's leftovers at the seam of the patch result: points a hundred-thousandth apart welded (on
    the open edges only), edges that short dissolved, zero-size faces hanging on 3+-face edges dropped."""
    import bmesh
    eps = 1e-5 * max(1e-9, size)
    bm = bmesh.new()
    try:
        bm.from_mesh(kept)
        bnd = [v for v in bm.verts if any(len(e.link_faces) != 2 for e in v.link_edges)]
        if bnd:
            bmesh.ops.remove_doubles(bm, verts=bnd, dist=eps)
        short = [e for e in bm.edges if e.is_valid and e.calc_length() < eps]
        if short:
            bmesh.ops.dissolve_degenerate(bm, edges=short, dist=eps)
        tiny = [f for f in bm.faces if f.is_valid and f.calc_area() < eps * eps
                and any(len(e.link_faces) > 2 for e in f.edges)]
        if tiny:
            bmesh.ops.delete(bm, geom=tiny, context='FACES_ONLY')
        # a face the solver dropped inside the result (a non-planar quad cut through): a hole of a few sides,
        # filled - the patch rim and the cut outline have far more sides than 8 and stay open
        opn = [e for e in bm.edges if e.is_valid and len(e.link_faces) == 1]
        filled = 0
        if opn:
            res = bmesh.ops.holes_fill(bm, edges=opn, sides=8)
            filled = len(res.get('faces', []))
        if os.environ.get('MECH_REGION_DEBUG'):
            print(f'[region] seam clean: {len(bnd)} boundary points, {len(short)} short edges, {len(tiny)} tiny faces, '
                  f'{filled} small holes filled', flush=True)
            for e in [e for e in bm.edges if e.is_valid and len(e.link_faces) > 2][:3]:
                print(f'[region]   3-face edge len {e.calc_length():.2e}: ' + ' | '.join(
                    f'f{f.index} n{len(f.verts)} area {f.calc_area():.2e} verts {sorted(v.index for v in f.verts)}' for f in e.link_faces), flush=True)
                for f in e.link_faces:
                    print(f'[region]      f{f.index} edges faces ' + str([len(x.link_faces) for x in f.edges]), flush=True)
        bm.to_mesh(kept)
    finally:
        bm.free()


def _knife_pieces(context, target, cutter, pV, pcorners, psizes, M):
    """The cutter's faces split along the patch (Edit-mode Intersect, Exact, no inside / outside sorting), in the
    part's space: (V, corners, sizes), or None when the operator could not run (not in Object Mode)."""
    import bmesh
    if context.mode != 'OBJECT':
        return None
    cc, ct, _cs, cv = arrays(cutter.data)
    cc = (np.c_[cc, np.ones(len(cc))] @ M.T)[:, :3]
    V = np.concatenate([pV, cc])
    corners = np.concatenate([pcorners, cv + len(pV)])
    sizes = np.concatenate([psizes, ct])
    K = build(V, corners, sizes, 'MCH_RegionKnife')
    a = K.attributes.new(TAG, 'INT', 'FACE')
    a.data.foreach_set('value', np.concatenate([np.ones(len(psizes), np.int32), np.full(len(ct), 2, np.int32)]))
    ko = bpy.data.objects.new('MCH_RegionKnife', K)
    context.scene.collection.objects.link(ko)
    ko.matrix_world = target.matrix_world.copy()
    vl = context.view_layer
    active = vl.objects.active
    selected = [o for o in vl.objects if o.select_get()]
    try:
        for o in selected:
            o.select_set(False)
        ko.select_set(True)
        vl.objects.active = ko
        bpy.ops.object.mode_set(mode='EDIT')
        try:
            bm = bmesh.from_edit_mesh(K)
            lay = bm.faces.layers.int.get(TAG)
            nsel = 0
            for f in bm.faces:
                f.select_set(f[lay] == 2)
                nsel += f[lay] == 2
            bm.select_flush_mode()
            bmesh.update_edit_mesh(K)
            n_before = len(bm.faces)
            r = bpy.ops.mesh.intersect(mode='SELECT_UNSELECT', separate_mode='NONE', solver='EXACT')
            # a cutter face the surface crosses in a closed loop comes back as one n-gon with the loop bridged into
            # its outline (a face cannot have a hole): triangulated, every piece is a plain triangle that is either
            # inside the part or outside, sorted on its own
            bm = bmesh.from_edit_mesh(K)
            lay = bm.faces.layers.int.get(TAG)
            cut_faces = [f for f in bm.faces if f[lay] == 2 and len(f.verts) > 4]
            if cut_faces:
                size = float(np.linalg.norm(pV.max(0) - pV.min(0))) if len(pV) else 1.0
                bmesh.ops.triangulate(bm, faces=cut_faces, quad_method='BEAUTY', ngon_method='BEAUTY')
                bmesh.update_edit_mesh(K)
            if os.environ.get('MECH_REGION_DEBUG'):
                print(f'[region]   knife: {r} selected {nsel} of {n_before} faces -> {len(bm.faces)} faces; mode {context.mode} active {context.view_layer.objects.active.name}', flush=True)
        finally:
            bpy.ops.object.mode_set(mode='OBJECT')
        c2, t2, _s2, v2 = arrays(K)
        fm = _tagged(K, 2)
        if os.environ.get('MECH_REGION_DEBUG'):
            at = K.attributes.get(TAG)
            vals = np.zeros(len(K.polygons), np.int32)
            if at is not None:
                at.data.foreach_get('value', vals)
            u, cnt = np.unique(vals, return_counts=True)
            print(f'[region]   knife tags {dict(zip(u.tolist(), cnt.tolist()))}; tag-2 corner counts {sorted(t2[fm].tolist())[:20]}', flush=True)
        if not fm.any():
            return np.zeros((0, 3)), np.zeros(0, np.int64), np.zeros(0, np.int32)
        return compact_arrays(c2, t2, v2, fm)
    finally:
        ko.select_set(False)
        bpy.data.objects.remove(ko)
        bpy.data.meshes.remove(K)
        for o in selected:
            try:
                o.select_set(True)
            except (ReferenceError, RuntimeError):
                pass
        try:
            vl.objects.active = active
        except (ReferenceError, RuntimeError):
            pass


def _walls(patch, pieces, R):
    """The cutter's pieces (``pieces``: V, corners, sizes in the part's space) that lie inside the part: rays along
    the cutter's three axes (``R``, both ways) and the nearest hit's side on the patch: hit from behind = inside.
    (A lasso prism meets the surface along its long axis, a shallow pocket along its short one.)  Returns
    (V, corners, sizes)."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    V, corners, sizes = pieces
    if not len(sizes):
        return np.zeros((0, 3)), np.zeros(0, np.int64), np.zeros(0, np.int32)
    # centres (area-weighted: the pieces' corners crowd along the seam, a plain mean would sit on the surface)
    start = np.concatenate([[0], np.cumsum(sizes)[:-1]])
    centres = np.empty((len(sizes), 3))
    for i, (a, n) in enumerate(zip(start.tolist(), sizes.tolist())):
        P = V[corners[a:a + n]]
        if n == 3:
            centres[i] = P.mean(0)
            continue
        tri_c = (P[0] + P[1:-1] + P[2:]) / 3.0
        tri_a = np.linalg.norm(np.cross(P[1:-1] - P[0], P[2:] - P[0]), axis=1)
        centres[i] = (tri_c * tri_a[:, None]).sum(0) / tri_a.sum() if tri_a.sum() > 0 else P.mean(0)
    pc, pt, _ps, pv = arrays(patch)
    pstart = np.concatenate([[0], np.cumsum(pt)[:-1]])
    polys = [pv[a:a + n].tolist() for a, n in zip(pstart.tolist(), pt.tolist())]
    bvh = BVHTree.FromPolygons([Vector(x) for x in pc.tolist()], polys)
    keep = np.zeros(len(sizes), bool)
    dirs = []
    for k in range(3):
        ax = Vector(R[:, k].tolist()).normalized()
        dirs += [ax, -ax]
    eps = 1e-6 * max(1e-9, float(np.linalg.norm(pc.max(0) - pc.min(0))))
    for i, cen in enumerate(centres.tolist()):
        o = Vector(cen)
        best = None
        for d in dirs:
            loc, nrm, _idx, dist = bvh.ray_cast(o, d)
            if loc is not None and dist < eps:          # (a centre lying on the patch: the hit beyond it counts)
                loc, nrm, _idx, dist2 = bvh.ray_cast(loc + d * eps, d)
                dist = dist2 + eps if loc is not None else None
            if loc is not None and (best is None or dist < best[0]):
                best = (dist, d.dot(nrm))
        keep[i] = best is not None and best[1] > 0.0
        if os.environ.get('MECH_REGION_DEBUG'):
            print(f'[region]   piece {i} centre {np.round(cen, 3).tolist()} size {sizes[i]} nearest hit {best} -> {"in" if keep[i] else "out"}', flush=True)
    if not keep.any():
        return np.zeros((0, 3)), np.zeros(0, np.int64), np.zeros(0, np.int32)
    Vk, inv, sz = compact_arrays(V, sizes, corners, keep)
    return _merge_flat(Vk, inv, sz)


def _merge_flat(V, corners, sizes):
    """The wall triangles (a cutter face split and triangulated) merged back into flat polygons: the needle-thin
    triangles a bridged n-gon leaves would otherwise cost the result tidy a copy of the whole part each."""
    import bmesh
    if not len(sizes):
        return V, corners, sizes
    bm = bmesh.new()
    try:
        vs = [bm.verts.new(tuple(p)) for p in V.tolist()]
        start = np.concatenate([[0], np.cumsum(sizes)[:-1]])
        for a, n in zip(start.tolist(), sizes.tolist()):
            try:
                bm.faces.new([vs[i] for i in corners[a:a + n].tolist()])
            except ValueError:
                pass
        size = float(np.linalg.norm(V.max(0) - V.min(0))) if len(V) > 1 else 1.0
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-7 * max(size, 1e-9))
        # edges between two coplanar triangles dissolved, the points all kept (dissolve_limit took the seam's
        # collinear points with it: a T-junction against the patch, an open edge per missing point)
        flat = []
        for e in bm.edges:
            if len(e.link_faces) == 2:
                a, b = e.link_faces
                if a.normal.length > 0 and b.normal.length > 0 and a.normal.angle(b.normal, 1.0) < 1e-2:
                    flat.append(e)
        if flat:
            bmesh.ops.dissolve_edges(bm, edges=flat, use_verts=False, use_face_split=False)
        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        Vo = np.array([v.co[:] for v in bm.verts]) if len(bm.verts) else np.zeros((0, 3))
        co, sz = [], []
        for f in bm.faces:
            co.extend(v.index for v in f.verts)
            sz.append(len(f.verts))
        return Vo, np.array(co, np.int64), np.array(sz, np.int32)
    finally:
        bm.free()


def compact_arrays(co, tot, vi, keep):
    """(V, corners, sizes) of the faces ``keep``, their points compacted."""
    lm = np.repeat(keep, tot)
    used, inv = np.unique(vi[lm], return_inverse=True)
    return co[used], inv, tot[keep]


def _directed_keys(corners, sizes, pts, q):
    """A key per corner edge (from this corner's point to the next, by rounded position)."""
    start = np.concatenate([[0], np.cumsum(sizes)[:-1]])
    nxt = np.arange(1, len(corners) + 1)
    nxt[start + sizes - 1] = start
    k = np.round(pts[corners] / q).astype(np.int64)
    h = (k[:, 0] * 73856093) ^ (k[:, 1] * 19349663) ^ (k[:, 2] * 83492791)
    return h, h[nxt]


def _same_way(kcor, ksz, wcor, wsz, kc, wc, co):
    """Do the wall faces run the same way as the patch faces along their shared seam edges (= they need flipping)?"""
    if not len(kcor) or not len(wcor):
        return False
    q = 1e-5 * max(1e-9, float(np.linalg.norm(co.max(0) - co.min(0))))
    ka, kb = _directed_keys(kcor, ksz, kc, q)
    wa, wb = _directed_keys(wcor, wsz, wc, q)
    kfwd = ka * 1000003 + kb
    same = np.isin(wa * 1000003 + wb, kfwd).sum()
    opposite = np.isin(wb * 1000003 + wa, kfwd).sum()
    return same > opposite


def _reversed_corners(vi, tot):
    """The corner list with every face's corners in reverse order (flips the faces)."""
    start = np.concatenate([[0], np.cumsum(tot)[:-1]])
    end = start + tot - 1
    idx = np.repeat(end, tot) - (np.arange(len(vi)) - np.repeat(start, tot))
    return vi[idx]


def _region_sub(kept, walls, size):
    """The patch result's own faces (tag 1) and the cutter's walls as ONE small mesh, cleaned with bmesh: the seam
    welded (points a hundred-thousandth apart, on open edges only), degenerate edges dissolved, holes of up to 8
    sides shut (the solver's slivers at the seam become tiny holes once the walls are on), zero-size faces on
    3+-face edges dropped.  The walls are turned to run against the patch faces along the seam.  Returns a mesh
    (caller owns it)."""
    import bmesh
    kc, kt, _ks, kv = arrays(kept)
    kface = _tagged(kept, 1)
    wc, wv, wt = walls
    if len(wt) and _same_way(kv[np.repeat(kface, kt)], kt[kface], wv, wt, kc, wc, kc):
        wv = _reversed_corners(wv, wt)
    sub = kept.copy()                          # (the patch result's attributes stay on its faces)
    bm = bmesh.new()
    try:
        bm.from_mesh(sub)
        bm.faces.ensure_lookup_table()
        drop = [f for f, k in zip(bm.faces, kface.tolist()) if not k]
        if drop:
            bmesh.ops.delete(bm, geom=drop, context='FACES')
        # a quad / n-gon the cut never touched came through the boolean as its triangles: put back together
        # (the triangles of one source face that still share their diagonal, with no new point on it)
        src = bm.faces.layers.int.get(SRC)
        if src is not None:
            groups = {}
            for f in bm.faces:
                if f.is_valid and len(f.verts) == 3:
                    groups.setdefault(f[src], []).append(f)
            diag = []
            for fs in groups.values():
                if len(fs) < 2:
                    continue
                for e in {e for f in fs for e in f.edges}:
                    lf = e.link_faces
                    if len(lf) == 2 and lf[0] in fs and lf[1] in fs and not any(len(x.link_faces) != 2 for x in e.verts[0].link_edges if False):
                        diag.append(e)
            if diag:
                bmesh.ops.dissolve_edges(bm, edges=diag, use_verts=False, use_face_split=False)
        if len(wt):
            vs = [bm.verts.new(tuple(p)) for p in wc.tolist()]
            start = np.concatenate([[0], np.cumsum(wt)[:-1]])
            for a, n in zip(start.tolist(), wt.tolist()):
                try:
                    bm.faces.new([vs[i] for i in wv[a:a + n].tolist()])
                except ValueError:
                    pass
        eps = 1e-5 * max(1e-9, size)
        bnd = [v for v in bm.verts if any(len(e.link_faces) != 2 for e in v.link_edges)]
        if bnd:
            bmesh.ops.remove_doubles(bm, verts=bnd, dist=eps)
        short = [e for e in bm.edges if e.is_valid and e.calc_length() < eps]
        if short:
            bmesh.ops.dissolve_degenerate(bm, edges=short, dist=eps)
        dbg = bool(os.environ.get('MECH_REGION_DEBUG'))
        if dbg:
            print(f'[region] sub: open edges after the seam weld {sum(1 for e in bm.edges if len(e.link_faces) == 1)}', flush=True)
        for _pass in range(3):                 # (an edge with two such points: the new edge gets the next pass)
            if not _seam_tees(bm, 10 * eps):
                break
        if dbg:
            print(f'[region] sub: open edges after the T-junction pass {sum(1 for e in bm.edges if len(e.link_faces) == 1)}', flush=True)
        opn = [e for e in bm.edges if e.is_valid and len(e.link_faces) == 1]
        if opn:
            bmesh.ops.holes_fill(bm, edges=opn, sides=8)
        if dbg:
            print(f'[region] sub: open edges after the hole fill {sum(1 for e in bm.edges if len(e.link_faces) == 1)}', flush=True)
        tiny = [f for f in bm.faces if f.is_valid and f.calc_area() < eps * eps
                and any(len(e.link_faces) > 2 for e in f.edges)]
        if tiny:
            bmesh.ops.delete(bm, geom=tiny, context='FACES_ONLY')
        loose = [v for v in bm.verts if not v.link_faces]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context='VERTS')
        bm.to_mesh(sub)
    finally:
        bm.free()
    sub.update()
    return sub


def _seam_tees(bm, tol):
    """T-junctions on the seam: the solver and the knife put the same crossing a little apart (one side has a
    point the other has not, or two points where the other has one - 4e-5 on a 1.3M-face part, past the weld).
    An open point that lies on an open edge of the other side splits that edge there and is welded to the new
    point.  Only open geometry is looked at (a few hundred points)."""
    import bmesh
    opn = [e for e in bm.edges if e.is_valid and len(e.link_faces) == 1]
    if not opn:
        return 0
    pts = {v for e in opn for v in e.verts}
    pts = [v for v in pts]
    kd = KDTree(len(pts))
    for i, v in enumerate(pts):
        kd.insert(v.co, i)
    kd.balance()
    done = 0
    for e in opn:
        if not e.is_valid or len(e.link_faces) != 1:
            continue
        a, b = e.verts[0].co.copy(), e.verts[1].co.copy()
        d = b - a
        L = d.length
        if L <= tol:
            continue
        mid = (a + b) * 0.5
        for co, i, _dist in kd.find_range(mid, L * 0.5 + tol):
            v = pts[i]
            if not v.is_valid or v in e.verts:
                continue
            t = (v.co - a).dot(d) / (L * L)
            if t <= 0.0 or t >= 1.0:
                continue
            if ((a + d * t) - v.co).length > tol:
                continue
            try:
                _ne, nv = bmesh.utils.edge_split(e, e.verts[0], t)
            except (ValueError, RuntimeError):
                continue
            bmesh.ops.remove_doubles(bm, verts=[nv, v], dist=tol * 2)
            done += 1
            break
    return done


def _stitch(me, co, tot, vi, fmask, lm, kept, walls, target, cutter, rim, operation):
    """The untouched faces of ``me`` + the cleaned region (patch result + walls), the rim welded: a new mesh."""
    size = float(np.linalg.norm(co.max(0) - co.min(0))) if len(co) else 1.0
    sub = _region_sub(kept, walls, size)
    try:
        # the cut's result tidy, on the region while it is still a small mesh (the cut's own tidy then finds nothing
        # and need not take the region out and put it back a second time: 1.4 s on 1.3M faces)
        from . import core_geometry as cg
        t = time.perf_counter()
        try:
            _PRE_TIDY['counts'] = cg.tidy_result(sub, size, before=None, flip=False)
        except (RuntimeError, ValueError, AttributeError, IndexError, MemoryError):
            _PRE_TIDY['counts'] = None
        _PRE_TIDY['s'] = time.perf_counter() - t
        out = build(np.zeros((0, 3)), np.zeros(0, np.int64), np.zeros(0, np.int32), me.name + '_cut', like=me)
        if not replace_faces(me, fmask, sub, size, into=out):
            bpy.data.meshes.remove(out)
            raise RuntimeError('region: a rim point of the part is missing from the cut region')
        LAST_REGION.clear()
        LAST_REGION.update(name=out.name, faces=len(out.polygons), untouched=int((~fmask).sum()))
        if os.environ.get('MECH_REGION_DEBUG'):
            print(f'[region] {operation}: faces part {int((~fmask).sum())} region {len(sub.polygons)} -> out {len(out.polygons)}', flush=True)
            debug_open_edges(out, None)
        return out
    finally:
        bpy.data.meshes.remove(sub)


def debug_open_edges(out, V=None):
    """(MECH_REGION_DEBUG) Where are the open edges of a stitched result: by side and nearest other point."""
    import bmesh
    from mathutils.kdtree import KDTree
    a = out.attributes.get('mch_dbg_side')
    side = np.zeros(len(out.vertices), np.int32)
    if a is not None:
        a.data.foreach_get('value', side)
    bm = bmesh.new()
    bm.from_mesh(out)
    opn = [e for e in bm.edges if len(e.link_faces) != 2]
    print(f'[region] open edges {len(opn)}', flush=True)
    if opn:
        kd = KDTree(len(bm.verts))
        for v in bm.verts:
            kd.insert(v.co, v.index)
        kd.balance()
        hist = {}
        for e in opn:
            k = tuple(sorted((int(side[e.verts[0].index]), int(side[e.verts[1].index]))))
            hist[k] = hist.get(k, 0) + 1
        print(f'[region]   by side (0 part, 1 kept, 2 walls): {hist}', flush=True)
        for e in opn[:3]:
            print(f'[region]   open edge faces {len(e.link_faces)} len {e.calc_length():.2e} verts ' +
                  str([(v.index, int(side[v.index]), len(v.link_faces)) for v in e.verts]), flush=True)
            for f in e.link_faces:
                print(f'[region]      face {f.index} n{len(f.verts)} area {f.calc_area():.2e} verts {[v.index for v in f.verts]} '
                      f'edge faces {[len(x.link_faces) for x in f.edges]}', flush=True)
            for v in e.verts:
                for f in v.link_faces:
                    if f not in e.link_faces:
                        print(f'[region]      round v{v.index}: face {f.index} verts {[x.index for x in f.verts]} edge faces {[len(x.link_faces) for x in f.edges]}', flush=True)
    bm.free()


def _carry_attrs(out, me, kept, walls, fmask, lm, kface, klm, wface, wlm, used, newidx, n0, nk, ckeep, fkeep):
    """The part's attributes onto the untouched points / faces / corners, the results' onto the new ones; edge
    attributes by the edge's two points."""
    src_point = [me, kept, walls]
    for name, domain, dtype in _attr_list(me):
        key, w, dt = _TYPES[dtype]
        mine = _read_attr(me, name, domain, dtype)
        if mine is None:
            continue
        if domain == 'POINT':
            vals = np.zeros((len(out.vertices), w), dt)
            vals[newidx[:n0][used[:n0]]] = mine[used[:n0]]
            for src, off, n in ((kept, n0, nk), (walls, n0 + nk, len(out.vertices))):
                v = _read_attr(src, name, domain, dtype) if src is not None else None
                if v is None:
                    continue
                m = used[off:off + n]
                vals[newidx[off:off + n][m]] = v[m]
        elif domain == 'FACE':
            parts = [mine[~fmask]]
            for src, fm in ((kept, kface), (walls, wface)):
                v = _read_attr(src, name, domain, dtype) if src is not None else None
                parts.append(v[fm] if v is not None else np.zeros((int(fm.sum()), w), dt))
            vals = np.concatenate(parts)[fkeep]
        elif domain == 'CORNER':
            parts = [mine[~lm]]
            for src, cm in ((kept, klm), (walls, wlm)):
                v = _read_attr(src, name, domain, dtype) if src is not None else None
                parts.append(v[cm] if v is not None else np.zeros((int(cm.sum()), w), dt))
            vals = np.concatenate(parts)[ckeep]
        else:                                            # EDGE: by the two points' output indices
            vals = _edge_attr(out, me, kept, walls, name, dtype, mine, used, newidx, n0, nk)
            if vals is None:
                continue
        try:
            a = out.attributes.get(name)
            if a is None or a.domain != domain or a.data_type != dtype:
                if a is not None:
                    out.attributes.remove(a)
                a = out.attributes.new(name, dtype, domain)
            a.data.foreach_set(key, np.ascontiguousarray(vals, dt).ravel())
        except (RuntimeError, TypeError, ValueError):
            pass


def _edge_keys(me, vmap):
    ev = vmap[mio.read_edge_verts(me)]
    ok = (ev >= 0).all(1)
    a, b = np.minimum(ev[:, 0], ev[:, 1]), np.maximum(ev[:, 0], ev[:, 1])
    return a * 4_000_000_000 + b, ok


def _edge_attr(out, me, kept, walls, name, dtype, mine, used, newidx, n0, nk):
    key, w, dt = _TYPES[dtype]
    vmap_out = np.arange(len(out.vertices))
    okeys, _ = _edge_keys(out, vmap_out)
    vals = np.zeros((len(out.edges), w), dt)
    # the part's edges (both points kept) first, then the results' (new points)
    for src, off, n, v in ((me, 0, n0, mine), (kept, n0, nk, _read_attr(kept, name, 'EDGE', dtype))):
        if v is None:
            continue
        vmap = np.where(used[off:off + n], newidx[off:off + n], -1)
        skeys, ok = _edge_keys(src, vmap)
        skeys, v = skeys[ok], v[ok]
        if not len(skeys):
            continue
        order = np.argsort(skeys)
        skeys, v = skeys[order], v[order]
        pos = np.searchsorted(skeys, okeys)
        pos[pos >= len(skeys)] = 0
        hit = skeys[pos] == okeys
        vals[hit] = v[pos[hit]]
    return vals


# ---------------------------------------------------------------------------------------------------------------------
# 0.24.86 the result tidy on the changed region only: the faces round the cut taken out as a small mesh (attributes
# along), tidied, and put back with the rim welded onto the part's own points.  The whole-mesh tidy walked a 1.3M-face
# part for a few hundred new faces (4.5 s of a 10 s cut).
# ---------------------------------------------------------------------------------------------------------------------

def _write_attr(me, name, domain, dtype, vals):
    key, w, dt = _TYPES[dtype]
    try:
        a = me.attributes.get(name)
        if a is None or a.domain != domain or a.data_type != dtype:
            if a is not None:
                me.attributes.remove(a)
            a = me.attributes.new(name, dtype, domain)
        a.data.foreach_set(key, np.ascontiguousarray(vals, dt).ravel())
    except (RuntimeError, TypeError, ValueError):
        pass


def _edge_lookup(me, vmap):
    """Sorted edge keys (by output point indices) of ``me`` and the matching row order, for edge attribute copies."""
    keys, ok = _edge_keys(me, vmap)
    order = np.argsort(keys)
    return keys[order], order, ok


def region_faces_of(me, before, size):
    """The faces to tidy after a cut: the stitched region of the last High Poly cut when ``me`` is that result,
    else the faces with a point ``before`` does not have (plus a ring).  None = everything."""
    from . import core_geometry as cg
    n = len(me.polygons)
    if LAST_REGION.get('name') == me.name and LAST_REGION.get('faces') == n:
        fmask = np.zeros(n, bool)
        fmask[LAST_REGION['untouched']:] = True
        co, tot, start, vi = arrays(me)
        vm = np.zeros(len(co), bool)
        vm[vi[np.repeat(fmask, tot)]] = True            # (one ring round the stitched faces)
        fmask = np.maximum.reduceat(vm[vi].astype(np.int8), start).astype(bool)
        return fmask
    fmask, _vmask = cg._changed_faces(me, before, size)
    return fmask


def extract_faces(me, fmask, name='MCH_TidySub'):
    """A mesh of the faces ``fmask`` with the part's point / face / corner / edge attributes.  Returns (mesh, the
    part's point indices the mesh's points came from)."""
    co, tot, start, vi = arrays(me)
    lm = np.repeat(fmask, tot)
    used, inv = np.unique(vi[lm], return_inverse=True)
    sub = build(co[used], inv, tot[fmask], name, like=me)
    for aname, domain, dtype in _attr_list(me):
        vals = _read_attr(me, aname, domain, dtype)
        if vals is None:
            continue
        if domain == 'POINT':
            v = vals[used]
        elif domain == 'FACE':
            v = vals[fmask]
        elif domain == 'CORNER':
            v = vals[lm]
        else:
            vmap = np.full(len(co), -1, np.int64)
            vmap[used] = np.arange(len(used))
            skeys, sorder, sok = _edge_lookup(me, vmap)
            skeys, sv = skeys[sok[sorder]], vals[sorder][sok[sorder]]
            okeys, _oo = _edge_keys(sub, np.arange(len(sub.vertices)))
            pos = np.searchsorted(skeys, okeys)
            pos[pos >= len(skeys)] = 0
            hit = skeys[pos] == okeys
            v = np.zeros((len(sub.edges), vals.shape[1]), vals.dtype)
            v[hit] = sv[pos[hit]]
        _write_attr(sub, aname, domain, dtype, v)
    return sub, used


def replace_faces(me, fmask, sub, size, into=None):
    """The faces ``fmask`` of ``me`` replaced by ``sub`` (a tidied / cut copy of them), the rim welded onto the
    part's points - in place, or written into the empty mesh ``into`` (``me`` untouched).  False when a rim point
    of the part has no match in ``sub`` (nothing written)."""
    from mathutils.kdtree import KDTree
    co, tot, start, vi = arrays(me)
    lm = np.repeat(fmask, tot)
    # the rim: the part's points that faces on both sides use (a point on an open sliver edge inside the region is
    # no rim point - the fix may weld it away, and no untouched face needs it)
    rim_part = _shared_points(vi, lm, len(co))
    sc, st, _ss, sv = arrays(sub)
    if not len(sc):
        return False
    # every rim point of the part must still be a point of the sub-mesh (any point: a point on an open sliver edge
    # is a rim point here and an inner point once its hole is shut)
    eps = 1e-6 * max(1e-9, size)
    kd = KDTree(len(sc))
    for j in range(len(sc)):
        kd.insert(sc[j], j)
    kd.balance()
    sub_to_part = np.full(len(sc), -1, np.int64)
    missed = []
    for i in rim_part.tolist():
        hit = kd.find(co[i])
        if hit[0] is None or hit[2] > eps:
            missed.append((i, None if hit[0] is None else float(hit[2])))
            if not os.environ.get('MECH_REGION_DEBUG'):
                return False                          # (a rim point moved or vanished: the whole-mesh tidy instead)
            continue
        sub_to_part[hit[1]] = i
    if missed:
        if os.environ.get('MECH_REGION_DEBUG'):
            print(f'[region] replace_faces: {len(missed)} of {len(rim_part)} rim points not found in the sub-mesh '
                  f'(nearest {[m[1] for m in missed[:5]]}, eps {eps:.2e})', flush=True)
        return False
    # the new point list: the part's points, then the sub's non-rim points
    n0 = len(co)
    new_sub = sub_to_part < 0
    sub_to_part[new_sub] = n0 + np.arange(int(new_sub.sum()))
    V = np.concatenate([co, sc[new_sub]])
    corners = np.concatenate([vi[~lm], sub_to_part[sv]])
    sizes = np.concatenate([tot[~fmask], st])
    used = np.zeros(len(V), bool)
    used[corners] = True
    newidx = np.cumsum(used) - 1
    # attributes read before the geometry goes
    attrs = []
    for aname, domain, dtype in _attr_list(me):
        mine = _read_attr(me, aname, domain, dtype)
        if mine is None:
            continue
        theirs = _read_attr(sub, aname, domain, dtype)
        key, w, dt = _TYPES[dtype]
        if domain == 'POINT':
            vals = np.zeros((int(used.sum()), w), dt)
            vals[newidx[:n0][used[:n0]]] = mine[used[:n0]]
            if theirs is not None:
                vals[newidx[n0:]] = theirs[new_sub]
        elif domain == 'FACE':
            vals = np.concatenate([mine[~fmask], theirs if theirs is not None else np.zeros((len(st), w), dt)])
        elif domain == 'CORNER':
            vals = np.concatenate([mine[~lm], theirs if theirs is not None else np.zeros((len(sv), w), dt)])
        else:
            vals = ('EDGE', mine, theirs)
        attrs.append((aname, domain, dtype, vals))
    # edge attribute sources, by output point indices
    emaps = []
    for aname, domain, dtype, vals in attrs:
        if domain == 'EDGE':
            vmap_me = np.where(used[:n0], newidx[:n0], -1)
            vmap_sub = newidx[sub_to_part]
            emaps.append((aname, dtype, vals[1], vmap_me, vals[2], vmap_sub))
    old_edge_keys = [(_edge_lookup(me, vm), v) for (_a, _d, v, vm, _t, _vs) in emaps]
    sub_edge_keys = [(_edge_lookup(sub, vs), t) if t is not None else None for (_a, _d, _v, _vm, t, vs) in emaps]
    if into is not None:
        me = into
    else:
        me.clear_geometry()
    me.vertices.add(int(used.sum()))
    mio.write_co(me, V[used])
    me.loops.add(len(corners))
    mio.write_corner_verts(me, newidx[corners])
    me.polygons.add(len(sizes))
    me.polygons.foreach_set('loop_start', np.concatenate([[0], np.cumsum(sizes)[:-1]]).astype(np.int32))
    me.update(calc_edges=True)
    ei = 0
    for aname, domain, dtype, vals in attrs:
        if domain != 'EDGE':
            _write_attr(me, aname, domain, dtype, vals)
            continue
        (okeys, oorder, ook), ov = old_edge_keys[ei]
        sk = sub_edge_keys[ei]
        ei += 1
        keys, _ok = _edge_keys(me, np.arange(len(me.vertices)))
        out_vals = np.zeros((len(me.edges), ov.shape[1]), ov.dtype)
        for (skeys, sorder, sok), v in ([((okeys, oorder, ook), ov)] + ([((sk[0][0], sk[0][1], sk[0][2]), sk[1])] if sk else [])):
            k2, v2 = skeys[sok[sorder]], v[sorder][sok[sorder]]
            if not len(k2):
                continue
            pos = np.searchsorted(k2, keys)
            pos[pos >= len(k2)] = 0
            hit = k2[pos] == keys
            out_vals[hit] = v2[pos[hit]]
        _write_attr(me, aname, 'EDGE', dtype, out_vals)
    return True


def tidy_sub(me, fmask, size, shards, slivers):
    """The whole tidy on the faces ``fmask`` only (a small mesh), put back into ``me``.  Returns the counts, or None
    when the sub-mesh path could not be used (the caller runs the whole-mesh tidy)."""
    from . import core_geometry as cg
    sub, _used = extract_faces(me, fmask)
    try:
        out = cg.tidy_result(sub, size, shards=shards, slivers=slivers, before=None, flip=False)
        if any(out.values()):
            if not replace_faces(me, fmask, sub, size):
                return None
        return out
    finally:
        bpy.data.meshes.remove(sub)


def open_edge_faces(me, rings=2):
    """The faces round the open / 3+-face edges of ``me`` (plus ``rings`` rings), as a face mask; None when there
    are none."""
    co, tot, start, vi = arrays(me)
    le = mio.read_corner_edges(me)
    cnt = np.bincount(le, minlength=len(me.edges))
    bad = (cnt != 2) & (cnt > 0)
    if not bad.any():
        return None
    fmask = np.maximum.reduceat(bad[le].astype(np.int8), start).astype(bool)
    for _ in range(rings):
        vm = np.zeros(len(co), bool)
        vm[vi[np.repeat(fmask, tot)]] = True
        fmask = np.maximum.reduceat(vm[vi].astype(np.int8), start).astype(bool)
    return fmask


def fix_holes_sub(me, size, fill='SMALL'):
    """0.24.86 ``mesh_fix.fix_mesh`` on the faces round the open edges only (a dense part: the whole-mesh fix took
    14 s of a 1.3M-face cut for 19 sliver edges).  False = not done (nothing open, or the rim could not be put
    back): the caller runs the whole-mesh fix."""
    import bmesh
    fm = open_edge_faces(me)
    if fm is None or fm.sum() >= 0.3 * len(fm):
        return False
    sub, _used = extract_faces(me, fm, 'MCH_HoleSub')
    try:
        # at the PART's scale (mesh_fix welds relative to the mesh it gets - the tiny sub - and took rim points)
        eps = 1e-5 * max(1e-9, size)
        bm = bmesh.new()
        try:
            bm.from_mesh(sub)
            bnd = [v for v in bm.verts if any(len(e.link_faces) == 1 for e in v.link_edges)]
            if bnd:
                bmesh.ops.remove_doubles(bm, verts=bnd, dist=eps)
            short = [e for e in bm.edges if e.is_valid and e.calc_length() < eps]
            if short:
                bmesh.ops.dissolve_degenerate(bm, edges=short, dist=eps)
            opn = [e for e in bm.edges if e.is_valid and len(e.link_faces) == 1]
            filled = 0
            if opn:
                filled = len(bmesh.ops.holes_fill(bm, edges=opn, sides=12).get('faces', []))
            tiny = [f for f in bm.faces if f.is_valid and f.calc_area() < eps * eps
                    and any(len(e.link_faces) > 2 for e in f.edges)]
            if tiny:
                bmesh.ops.delete(bm, geom=tiny, context='FACES_ONLY')
            bm.to_mesh(sub)
        finally:
            bm.free()
        ok = replace_faces(me, fm, sub, size)
        if os.environ.get('MECH_REGION_DEBUG'):
            print(f'[region] holes: {int(fm.sum()):,} faces round the open edges of {len(fm):,}; {len(bnd)} open points, '
                  f'{len(short)} short edges, {filled} holes filled; put back {ok}', flush=True)
        return ok
    finally:
        bpy.data.meshes.remove(sub)
