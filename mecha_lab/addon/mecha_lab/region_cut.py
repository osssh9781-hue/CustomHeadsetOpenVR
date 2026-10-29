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

TAG = 'mch_region_src'
LAST_TIMES = {}                   # the last region boolean's stage times (region / extract / boolean / knife / sort / stitch)
LAST_REGION = {}                  # the last stitched result: {'name': mesh name, 'faces': total, 'untouched': first N faces untouched}
TIDY_SUB_MIN = 50_000             # faces: below this the whole-mesh tidy is as fast as taking the region out
MIN_FACES = int(os.environ.get('MECH_REGION_MIN', 100_000))   # (below this the whole-part boolean is as fast)
MARGIN = 0.15                     # of the cutter's box diagonal, each side
RINGS = 2
_SKIP = {'position', '.edge_verts', '.corner_vert', '.corner_edge', TAG}
_TYPES = {'FLOAT': ('value', 1, np.float32), 'INT': ('value', 1, np.int32), 'INT8': ('value', 1, np.int32),
          'BOOLEAN': ('value', 1, bool), 'FLOAT_VECTOR': ('vector', 3, np.float32), 'FLOAT2': ('vector', 2, np.float32),
          'FLOAT_COLOR': ('color', 4, np.float32), 'BYTE_COLOR': ('color', 4, np.float32),
          'INT32_2D': ('value', 2, np.int32), 'QUATERNION': ('value', 4, np.float32)}


def arrays(me):
    n = len(me.polygons)
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    tot = np.empty(n, np.int32)
    me.polygons.foreach_get('loop_total', tot)
    start = np.empty(n, np.int32)
    me.polygons.foreach_get('loop_start', start)
    vi = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get('vertex_index', vi)
    return co.reshape(-1, 3), tot, start, vi


def build(V, corners, sizes, name, like=None):
    """A mesh from arrays; ``like``: an empty copy of that mesh (materials, settings, custom props) is filled."""
    if like is not None:
        from .fast_decimate import fresh_like
        m = fresh_like(like)
        m.name = name
    else:
        m = bpy.data.meshes.new(name)
    m.vertices.add(len(V))
    m.vertices.foreach_set('co', np.ascontiguousarray(V, np.float64).ravel())
    m.loops.add(len(corners))
    m.loops.foreach_set('vertex_index', np.ascontiguousarray(corners, np.int32))
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
        t1b = time.perf_counter()
        # the cutter's walls: the solver sorts the cutter's pieces by the patch's winding number, which an open
        # patch cannot give (a thin column through a part: the pieces inside vanish from Intersect, Union and
        # Difference alike) - so the cutter is only SPLIT along the patch (Edit-mode Intersect / Knife, no sorting)
        # and the pieces are sorted here, by a ray along the cutter's axis (``_walls``)
        pieces = _knife_pieces(context, target, cutter, co[pverts], pcorners, tot[fmask], M)
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
                      stitch=t3 - t2b, faces_region=nreg, faces_total=len(tot), walls=int(len(wS)))
    if log is not None:
        log.append(f'region {nreg:,} of {len(tot):,} faces: region {t0b - t0:.2f} extract {t1 - t0b:.2f} boolean {t1b - t1:.2f} '
                   f'knife {t2 - t1b:.2f} sort {t2b - t2:.2f} stitch {t3 - t2b:.2f} s')
    return out


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
        bmesh.ops.dissolve_limit(bm, angle_limit=1e-2, verts=[], edges=bm.edges[:])   # (edges only: the seam points stay)
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


def _stitch(me, co, tot, vi, fmask, lm, kept, walls, target, cutter, rim, operation):
    """Untouched faces + the patch result's own faces + the cutter's wall faces, seams welded.  ``rim``: the part's
    points on the patch boundary (the untouched side of the seam); ``walls``: (V, corners, sizes) in the part's
    space."""
    kc, kt, ks, kv = arrays(kept)
    wc, wv, wt = walls
    kface = _tagged(kept, 1)                   # the patch's faces (the cutter's that slipped in are dropped)
    wface = np.ones(len(wt), bool)
    # the walls' orientation: whatever the cutter's was (a mirrored or inside-out cutter flips it), the walls must run
    # against the patch faces along the seam - counted on the seam edges, flipped when they run the same way
    if _same_way(kv[np.repeat(kface, kt)], kt[kface], wv, wt, kc, wc, co):
        wv = _reversed_corners(wv, wt)
    # output points: the part's own, then the two results' (their own point lists; welded below)
    n0 = len(co)
    klm = np.repeat(kface, kt)
    wlm = np.repeat(wface, wt)
    V = np.concatenate([co, kc, wc])
    corners = np.concatenate([vi[~lm], kv[klm] + n0, wv[wlm] + n0 + len(kc)])
    sizes = np.concatenate([tot[~fmask], kt[kface], wt[wface]])
    # seams: the rim of the untouched part, the rims of the two results
    rim_part = rim if (~fmask).any() else np.zeros(0, np.int64)
    rim_kept = _boundary_verts(kv[klm], kt[kface]) + n0
    rim_walls = _boundary_verts(wv[wlm], wt[wface]) + n0 + len(kc)
    bnd = np.concatenate([rim_part, rim_kept, rim_walls]).astype(np.int64)
    if os.environ.get('MECH_REGION_DEBUG') and len(rim_walls) and len(rim_kept):
        from mathutils.kdtree import KDTree as _KD
        kdk = _KD(len(rim_kept))
        for j, i in enumerate(rim_kept.tolist()):
            kdk.insert(V[i], j)
        kdk.balance()
        ds = np.array([kdk.find(V[i])[2] for i in rim_walls.tolist()])
        print(f'[region]   seam: walls rim {len(rim_walls)} pts, kept rim {len(rim_kept)} pts, part rim {len(rim_part)}; '
              f'walls->kept nearest: min {ds.min():.2e} median {np.median(ds):.2e} max {ds.max():.2e}; '
              f'walls rim bbox {np.round(V[rim_walls].min(0), 3).tolist()}..{np.round(V[rim_walls].max(0), 3).tolist()} '
              f'kept rim bbox {np.round(V[rim_kept].min(0), 3).tolist()}..{np.round(V[rim_kept].max(0), 3).tolist()}', flush=True)
    side = np.concatenate([np.zeros(len(rim_part), np.int8), np.ones(len(rim_kept), np.int8), np.full(len(rim_walls), 2, np.int8)])
    remap = np.arange(len(V))
    if len(bnd):
        kd = KDTree(len(bnd))
        pts = V[bnd]
        for j in range(len(bnd)):
            kd.insert(pts[j], j)
        kd.balance()
        eps = 1e-5 * max(1e-9, float(np.linalg.norm(co.max(0) - co.min(0))))   # (the two booleans round a seam point apart by ~1e-6)
        parent = list(range(len(bnd)))

        def root(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for j in range(len(bnd)):                  # (only points of different sides are welded: a seam, never a
            for _c, k, d in kd.find_range(pts[j], eps):   # short edge of one piece)
                if side[k] != side[j]:
                    a, b = root(j), root(k)
                    if a != b:
                        parent[max(a, b)] = min(a, b)
        for j in range(len(bnd)):
            remap[bnd[j]] = bnd[root(j)]
    corners = remap[corners]
    # a corner repeated in its face (two seam points welded onto one): dropped, a face left with under 3 corners goes
    start = np.concatenate([[0], np.cumsum(sizes)[:-1]])
    nxt = np.arange(1, len(corners) + 1)
    nxt[start + sizes - 1] = start
    ckeep = corners != corners[nxt]
    fsizes = np.add.reduceat(ckeep.astype(np.int32), start) if len(sizes) else sizes
    fkeep = fsizes >= 3
    ckeep &= np.repeat(fkeep, sizes)
    corners, sizes = corners[ckeep], fsizes[fkeep]
    # drop the points no face uses (the region's inner points, welded duplicates)
    used = np.zeros(len(V), bool)
    used[corners] = True
    newidx = np.cumsum(used) - 1
    out = build(V[used], newidx[corners], sizes, me.name + '_cut', like=me)
    _carry_attrs(out, me, kept, None, fmask, lm, kface, klm, wface, wlm, used, newidx, n0, len(kc), ckeep, fkeep)
    LAST_REGION.clear()
    LAST_REGION.update(name=out.name, faces=len(out.polygons), untouched=int(fkeep[:int((~fmask).sum())].sum()))
    if os.environ.get('MECH_REGION_DEBUG'):
        print(f'[region] {operation}: faces part {int((~fmask).sum())} kept {int(kface.sum())} walls {len(wt)} -> out {len(out.polygons)} '
              f'(points part {int(used[:n0].sum())} kept {int(used[n0:n0 + len(kc)].sum())} walls {int(used[n0 + len(kc):].sum())})', flush=True)
        side_all = np.concatenate([np.zeros(n0, np.int32), np.ones(len(kc), np.int32), np.full(len(wc), 2, np.int32)])
        a = out.attributes.new('mch_dbg_side', 'INT', 'POINT')
        a.data.foreach_set('value', side_all[used])
        debug_open_edges(out, V[used])
    return out


def debug_open_edges(out, V):
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
        for e in opn[:4]:
            for v in e.verts:
                near = [(round(d, 7), int(side[i])) for (_c, i, d) in kd.find_n(v.co, 3) if i != v.index]
                print(f'[region]   v{v.index} side {side[v.index]} faces {len(v.link_faces)} nearest {near}', flush=True)
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
    ev = np.empty(len(me.edges) * 2, np.int64)
    me.edges.foreach_get('vertices', ev)
    ev = vmap[ev.reshape(-1, 2)]
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


def replace_faces(me, fmask, sub, size):
    """The faces ``fmask`` of ``me`` replaced in place by ``sub`` (a tidied copy of them), the rim welded onto the
    part's points.  False (``me`` untouched) when a rim point of the part has no match in ``sub``."""
    from mathutils.kdtree import KDTree
    co, tot, start, vi = arrays(me)
    lm = np.repeat(fmask, tot)
    # the rim: the part's points that faces on both sides use (a point on an open sliver edge inside the region is
    # no rim point - the fix may weld it away, and no untouched face needs it)
    rim_part = np.intersect1d(vi[lm], vi[~lm])
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
    me.clear_geometry()
    me.vertices.add(int(used.sum()))
    me.vertices.foreach_set('co', np.ascontiguousarray(V[used], np.float64).ravel())
    me.loops.add(len(corners))
    me.loops.foreach_set('vertex_index', np.ascontiguousarray(newidx[corners], np.int32))
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
    le = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get('edge_index', le)
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
    from . import mesh_fix
    fm = open_edge_faces(me)
    if fm is None or fm.sum() >= 0.3 * len(fm):
        return False
    sub, _used = extract_faces(me, fm, 'MCH_HoleSub')
    try:
        st = mesh_fix.fix_mesh(sub, fill=fill)
        ok = replace_faces(me, fm, sub, size)
        if os.environ.get('MECH_REGION_DEBUG'):
            print(f'[region] holes: {int(fm.sum()):,} faces round the open edges of {len(fm):,}; fix {st}; put back {ok}', flush=True)
        return ok
    finally:
        bpy.data.meshes.remove(sub)
