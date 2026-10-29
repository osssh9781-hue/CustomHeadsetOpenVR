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
    if os.environ.get('MECH_REGION_DEBUG'):
        print(f'[region] cutter {len(cb)} pts ext {np.round(ext, 3).tolist()} margin {m:.3f} region {nreg:,} of {len(tot):,}', flush=True)
    if nreg == 0 or nreg > 0.6 * len(tot):           # (nothing near, or most of the part: no gain)
        return None
    # the patch (region faces, points compacted) with its origin tag
    lm = np.repeat(fmask, tot)
    pverts, pcorners = np.unique(vi[lm], return_inverse=True)
    patch = build(co[pverts], pcorners, tot[fmask], 'MCH_RegionPatch')
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
    try:
        if operation == 'DIFFERENCE':
            kept = cg.evaluate_boolean(context, tmp, cutter, 'DIFFERENCE', 'EXACT')
        else:
            kept = cg.evaluate_boolean(context, tmp, cutter, 'INTERSECT', 'EXACT')
        walls = cg.evaluate_boolean(context, cutter, tmp, 'INTERSECT', 'EXACT')
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
              f'walls {len(walls.polygons)} (cutter-tagged {int(_tagged(walls, 2).sum())}) cutter faces {len(cutter.data.polygons)}', flush=True)
    try:
        # nothing cut (the cutter is in the box but misses the surface): the whole-part path says so properly
        if not _tagged(walls, 2).any() and len(kept.polygons) == len(patch.polygons):
            return None
        if operation == 'INTERSECT' and not _tagged(kept, 1).any():
            return None
        if operation == 'INTERSECT':               # (the piece inside the cutter: none of the untouched faces)
            fmask = np.ones(len(tot), bool)
            lm = np.ones(len(vi), bool)
        rim = pverts[_boundary_verts(pcorners, tot[fmask] if operation != 'INTERSECT' else tot[fmask0])]
        out = _stitch(me, co, tot, vi, fmask, lm, kept, walls, target, cutter, rim, operation)
    finally:
        bpy.data.objects.remove(tmp)
        for mm in (patch, kept, walls):
            bpy.data.meshes.remove(mm)
    t3 = time.perf_counter()
    if log is not None:
        log.append(f'region {nreg:,} of {len(tot):,} faces: mask {t1 - t0:.2f} booleans {t2 - t1:.2f} stitch {t3 - t2:.2f} s')
    return out


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
    points on the patch boundary (the untouched side of the seam)."""
    kc, kt, ks, kv = arrays(kept)
    wc, wt, ws, wv = arrays(walls)
    kface = _tagged(kept, 1)                   # the patch's faces (the cutter's that slipped in are dropped)
    wface = _tagged(walls, 2)                  # the cutter's faces (the patch cap is dropped)
    M = np.array(target.matrix_world.inverted() @ cutter.matrix_world)
    wc = (np.c_[wc, np.ones(len(wc))] @ M.T)[:, :3]
    # the walls' orientation: whatever the cutter's was (a mirrored or inside-out cutter flips it), the walls must run
    # against the patch faces along the seam - counted on the seam edges, flipped when they run the same way
    if _same_way(kv[np.repeat(kface, kt)], kt[kface], wv[np.repeat(wface, wt)], wt[wface], kc, wc, co):
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
    _carry_attrs(out, me, kept, walls, fmask, lm, kface, klm, wface, wlm, used, newidx, n0, len(kc), ckeep, fkeep)
    if os.environ.get('MECH_REGION_DEBUG'):
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
            for src, off, n in ((kept, n0, nk), (walls, n0 + nk, len(walls.vertices))):
                v = _read_attr(src, name, domain, dtype)
                if v is None:
                    continue
                m = used[off:off + n]
                vals[newidx[off:off + n][m]] = v[m]
        elif domain == 'FACE':
            parts = [mine[~fmask]]
            for src, fm in ((kept, kface), (walls, wface)):
                v = _read_attr(src, name, domain, dtype)
                parts.append(v[fm] if v is not None else np.zeros((int(fm.sum()), w), dt))
            vals = np.concatenate(parts)[fkeep]
        elif domain == 'CORNER':
            parts = [mine[~lm]]
            for src, cm in ((kept, klm), (walls, wlm)):
                v = _read_attr(src, name, domain, dtype)
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
    for src, off, n, v in ((me, 0, n0, mine), (kept, n0, nk, _read_attr(kept, name, 'EDGE', dtype)),
                           (walls, n0 + nk, len(walls.vertices), _read_attr(walls, name, 'EDGE', dtype))):
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
