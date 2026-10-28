"""0.24.73 Edge Mesh (ZBrush shelf, Hard Edges box): a light, clean hard-surface mesh with crisp edges from a dense one
(a DynaMesh / sculpt / imported FBX) - what pressing Decimate again and again shows: the flats empty out, the edges
stay and line up.

1. Decimate in steps down to Detail triangles; every step keeps STEP of the triangles with a fresh error, so the
   flats go first and the edges come out.  Adaptive: in the last steps the points where an edge line bends (a
   rounded slot end, a corner) cost more to take away - round ends stay round, straight edges stay light.
2. Hard edges: faces meeting at more than Angle (open borders too); lone specks are dropped and the edge lines
   straightened a little (the small zigzag the steps leave on a straight edge).
3. The near-flat triangles between the hard edges are joined into quads (triangles stay where it is hard).
4. Live and adjustable like Find Edges (hard_edges): support Bevel - each edge as wide as Width asks where it fits
   (fit_weights: no bevels running into each other, a small part keeps a narrow one), Subdivide, and
   Fit to Original - a Shrinkwrap onto the dense original away from the hard edges, so the subdivided surface keeps
   the original's shape.  Apply bakes it into a plain mesh (Client Look: the same in Maya / Max / ZBrush).

The dense original is kept off-scene (an object in no scene, held by a fake user: never drawn, never exported) for
Fit to Original until Apply / Clear.

0.24.74 Auto Detail (``auto_detail``): the count from a Tolerance in % of the part size - plain steps while the light
mesh stays that close to the original (``deviation``), then the last steps as with that Detail.  Match Original
(``match_round``): every hard edge's bevel as round as the original is there; Width is the least.
"""
from __future__ import annotations

import math

import numpy as np

import bmesh
import bpy

from . import fast_decimate as fd
from . import hard_edges as he

STEP = 0.8                      # every decimation step keeps this share of the triangles
ADAPT_FROM = 8                  # adaptive weights once the mesh is under this x the target
TURN_COST = 30.0                # a point where an edge line turns 90 degrees costs this much more to take away
SMALL_MAX = 8.0                 # ... more on short edge segments (small round ends), up to this factor
STRAIGHT = math.radians(12.0)   # edge-line points bending less than this are straightened
STRAIGHT_ITERS = 2
JOIN_FACE = math.radians(20.0)  # triangles joined into a quad: faces this close to flat ...
JOIN_SHAPE = math.radians(45.0)  # ... and a quad this close to a rectangle
MIN_TARGET = 100
MERGE = 0.2                     # points closer than this x the bevel Width are merged first: a chamfer strip
MERGE_MAX = 0.02                # narrower than the bevel becomes one edge to round (at most this x the part size)
EVEN_FROM = 3                   # the last steps (under this x the target) keep the triangles round: no slivers
                                # along the edges (a bevel needs the faces next to an edge to reach Width away)
AUTO_FROM = 30000               # Auto Detail: the light mesh is compared with the original once under this many
AUTO_SAMPLES = 20000            # ... triangles, at this many points of the original
AUTO_SHARE = 0.99               # ... this share of them must be within Tolerance
AUTO_FLAT = 0.3                 # ... points away from the hard edges count this much (Fit to Original puts them back)
MATCH_FLAT = math.radians(25.0)  # ... the original's flats are read where its normal is this close to the face's
MATCH_TURN = math.radians(60.0)  # Match Original: on a shallower edge the gap to the original is too small to read
                                # well - its bevel is worked out as if it turned this much (no noise blown up)


def _tri_edges(T, nv):
    """Unique edges of triangles T: (edges (k, 2), first face, second face (-1 none), faces per edge)."""
    he_ = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]])
    fa = np.tile(np.arange(len(T)), 3)
    lo, hi = he_.min(1).astype(np.int64), he_.max(1).astype(np.int64)
    key = lo * nv + hi
    o = np.argsort(key, kind='stable')
    key, fa = key[o], fa[o]
    first = np.ones(len(key), bool)
    first[1:] = key[1:] != key[:-1]
    idx = np.flatnonzero(first)
    cnt = np.diff(np.append(idx, len(key)))
    f1 = fa[idx]
    f2 = np.where(cnt > 1, fa[np.minimum(idx + 1, len(fa) - 1)], -1)
    k = key[idx]
    return np.stack([k // nv, k % nv], 1), f1, f2, cnt


def hard_lines(V, T, angle):
    """Hard edges of triangles (V, T) (faces meeting at more than ``angle``, open / non-manifold edges): (k, 2)."""
    if not len(T):
        return np.zeros((0, 2), np.int64)
    E, f1, f2, cnt = _tri_edges(T, len(V))
    n = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]]).astype(np.float64)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-30)
    two = cnt == 2
    hard = ~two
    c = (n[f1[two]] * n[f2[two]]).sum(1)
    hard[two] = c < math.cos(angle)
    return E[hard]


def line_points(V, H):
    """Points on exactly two hard edges: (points, neighbour 1, neighbour 2, turn angle) - and hard edges per point."""
    nv = len(V)
    deg = np.bincount(H.ravel(), minlength=nv) if len(H) else np.zeros(nv, np.int64)
    if not len(H):
        z = np.zeros(0, np.int64)
        return z, z, z, np.zeros(0), deg
    a = np.concatenate([H[:, 0], H[:, 1]])
    b = np.concatenate([H[:, 1], H[:, 0]])
    o = np.argsort(a, kind='stable')
    a, b = a[o], b[o]
    start = np.searchsorted(a, np.arange(nv))
    p = np.flatnonzero(deg == 2)
    o1, o2 = b[start[p]], b[start[p] + 1]
    d1, d2 = V[o1] - V[p], V[o2] - V[p]
    c = (d1 * d2).sum(1) / np.maximum(np.linalg.norm(d1, axis=1) * np.linalg.norm(d2, axis=1), 1e-30)
    turn = math.pi - np.arccos(np.clip(c, -1.0, 1.0))
    return p, o1, o2, turn, deg


def turn_weights(V, T, angle):
    """Adaptive: per point, how much more taking it away costs - edge lines that bend and corners keep their points
    (more on short segments: a small round end), straight edge lines and flats cost nothing extra."""
    V = np.asarray(V, np.float64)
    w = np.ones(len(V), np.float32)
    H = hard_lines(V, T, angle)
    if not len(H):
        return w
    p, o1, o2, turn, deg = line_points(V, H)
    seg = 0.5 * (np.linalg.norm(V[o1] - V[p], axis=1) + np.linalg.norm(V[o2] - V[p], axis=1))
    el = np.linalg.norm(V[H[:, 0]] - V[H[:, 1]], axis=1)
    typical = float(np.median(el)) if len(el) else 1.0
    small = np.clip(typical / np.maximum(seg, 1e-12), 1.0, SMALL_MAX)
    w[p] = 1.0 + TURN_COST * (turn / (0.5 * math.pi)) ** 2 * small ** 2
    w[deg >= 3] = 1.0 + TURN_COST
    return np.clip(w, 1.0, 1e5)


def progressive(V, T, target, angle, step=STEP, adapt=True, mats=None, report=None):
    """Decimate (V, T) in steps down to ``target`` triangles (fresh error every step).  Returns (V, T, mats, steps)."""
    V = np.ascontiguousarray(V, np.float32)
    T = np.ascontiguousarray(T, np.int32)
    target = max(MIN_TARGET, int(target))
    steps = 0
    while len(T) > target * 1.02:
        n0 = len(T)
        goal = max(target, int(n0 * step))
        w = turn_weights(V, T, angle) if adapt and n0 <= ADAPT_FROM * target else None
        even = n0 <= EVEN_FROM * target
        oV, oT, _vs, fs = fd.run(V, T, goal, even=even, weight=w)
        if even and len(oT) > 1.05 * goal:               # 0.24.74 (round triangles only can't get past a mesh full of
            oV, oT, _vs, fs = fd.run(V, T, goal, weight=w)  # slivers: that step plain - it stopped at 27k of 18k)
        V, T = oV.copy(), oT.copy()
        if mats is not None:
            mats = mats[fs]
        steps += 1
        if report:
            report(steps, len(T))
        if len(T) >= n0:                                 # (nothing more comes off: stop)
            break
    return V, T, mats, steps


def deviation(P, V, T, angle):
    """How far the light mesh (V, T) leaves the original, sampled at its points ``P``: the AUTO_SHARE quantile of
    their distances to it - a point whose nearest face doesn't touch a hard edge counts AUTO_FLAT (the subdivided
    surface is fitted back onto the original there; at the edges it isn't)."""
    from mathutils.bvhtree import BVHTree
    bvh = BVHTree.FromPolygons(np.asarray(V, np.float64).tolist(), np.asarray(T).tolist())
    d = np.zeros(len(P))
    face = np.zeros(len(P), np.int64)
    for i, p in enumerate(P):
        hit = bvh.find_nearest(p)
        if hit[0] is not None:
            d[i], face[i] = hit[3], hit[2]
    H = hard_lines(np.asarray(V, np.float64), T, angle)
    on = np.zeros(len(V), bool)
    on[H.ravel()] = True
    near = on[T].any(1)[face]
    return float(np.quantile(np.where(near, d, AUTO_FLAT * d), AUTO_SHARE)) if len(P) else 0.0


def auto_detail(V, T, tol, angle, report=None):
    """Auto Detail: decimate in plain steps (as ``progressive`` does far above its target) while the light mesh stays
    within ``tol`` of the original (``deviation``).  Returns (triangles, start) - start = (points, triangles, source
    triangle of each) of the last step at least ADAPT_FROM x that many triangles: ``progressive`` goes on from there
    to the count found exactly as it would have from the original (only its last steps differ)."""
    V = np.ascontiguousarray(V, np.float32)
    T = np.ascontiguousarray(T, np.int32)
    rng = np.random.default_rng(0)
    P = V[rng.choice(len(V), min(AUTO_SAMPLES, len(V)), replace=False)].astype(np.float64).tolist()
    idx = np.arange(len(T))
    snaps = [(len(T), V, T, idx)]                    # (only the ones the second pass may start from are kept)
    good = len(T)
    steps = 0
    while len(T) > MIN_TARGET * 1.02:
        n0 = len(T)
        V, T, _vs, fs = fd.run(V, T, max(MIN_TARGET, int(n0 * STEP)), even=False)
        V, T, idx = V.copy(), T.copy(), idx[fs]
        steps += 1
        if report:
            report(steps, len(T))
        if len(T) >= n0:
            break
        if len(T) <= AUTO_FROM and deviation(P, V, T, angle) > tol:
            break
        good = len(T)
        snaps.append((len(T), V, T, idx))
        while len(snaps) > 2 and snaps[1][0] >= ADAPT_FROM * good:
            snaps.pop(0)                             # (the second-largest is still far enough above: the largest goes)
    start = next((s for s in reversed(snaps) if s[0] >= ADAPT_FROM * good), snaps[0])
    return good, start[1:]


def straighten(V, H, iters=STRAIGHT_ITERS, limit=STRAIGHT):
    """The edge lines a little straighter: points on a line that bends less than ``limit`` move half-way to the middle
    of their two neighbours (sharper bends - corners, round ends - stay)."""
    V = np.array(V, np.float64)
    for _i in range(iters):
        p, o1, o2, turn, _deg = line_points(V, H)
        m = turn < limit
        p, o1, o2 = p[m], o1[m], o2[m]
        if not len(p):
            break
        V[p] = 0.5 * V[p] + 0.25 * (V[o1] + V[o2])
    return V.astype(np.float32)


def _read(me):
    me.calc_loop_triangles()
    V = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', V)
    T = np.empty(len(me.loop_triangles) * 3, np.int32)
    me.loop_triangles.foreach_get('vertices', T)
    mats = np.empty(len(me.loop_triangles), np.int32)
    me.loop_triangles.foreach_get('material_index', mats)
    return V.reshape(-1, 3), T.reshape(-1, 3), mats


def _mark_and_join(me, angle, size, merge=0.0):
    """Hard edges (angle, open borders; lone specks dropped) on the new mesh, the near-flat triangles between them
    joined into quads; marks written like Find Edges.  Points closer than ``merge`` are merged first (a strip
    narrower than the bevel can't hold two bevels: it becomes one edge).  Returns (hard edges, quads, triangles)."""
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        if merge > 0:
            bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=merge)
            bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=merge * 0.1)
        hard = [e for e in bm.edges if len(e.link_faces) != 2 or e.calc_face_angle(0.0) > angle]
        hard = set(he.drop_short_lines(he._drop_specks(hard, size), size))
        for e in bm.edges:
            e.seam = e in hard
        bmesh.ops.join_triangles(bm, faces=bm.faces[:], cmp_seam=True, cmp_sharp=False, cmp_uvs=False,
                                 cmp_vcols=False, cmp_materials=True, angle_face_threshold=JOIN_FACE,
                                 angle_shape_threshold=JOIN_SHAPE)
        conv = bm.edges.layers.bool.get(he.CONVEX) or bm.edges.layers.bool.new(he.CONVEX)
        n = 0
        for e in bm.edges:
            h = e.seam
            e.seam = False
            e.smooth = not h
            e[conv] = h and he._convex(e)
            n += h
        for f in bm.faces:
            f.smooth = True
        quads = sum(len(f.verts) == 4 for f in bm.faces)
        tris = sum(len(f.verts) == 3 for f in bm.faces)
        bm.to_mesh(me)
    finally:
        bm.free()
    hard_e = he._edge_bool(me, 'sharp_edge')
    a = me.attributes.get(he.HARD) or me.attributes.new(he.HARD, 'BOOLEAN', 'EDGE')
    a.data.foreach_set('value', hard_e)
    return n, quads, tris


def _bvh(me):
    from mathutils.bvhtree import BVHTree
    V, T, _m = _read(me)
    return BVHTree.FromPolygons(V.tolist(), T.tolist())


def match_round(me, bvh):
    """0.24.74 Match Original: per hard edge of the light mesh ``me``, the bevel width that rounds it like the dense
    original (``bvh``) is rounded there.  The original's two flats are read a little way into each face (its own
    surface and normal there - the light faces next to an edge lean over the rounding); where those planes meet is
    the corner a sharp edge would have, and the original's surface is some gap ``d`` in from it.  A round edge of
    radius r turning phi leaves d = r (sec(phi/2) - 1) and starts r tan(phi/2) = d cot(phi/4) in from the corner on
    each face - the bevel width.  Measured at three points along the edge (the middle value), then one pass of the
    middle value of each edge and the edges before and after it on the same line (a line keeps one width).
    Written to the ROUND edge attribute (0 = sharp)."""
    hard = he.hard_flags(me)
    _f1, _f2, cnt = he._edge_faces(me)
    ne = len(me.edges)
    out = np.zeros(ne, np.float32)
    sel = np.flatnonzero(hard & (cnt == 2))
    if len(sel) and bvh is not None:
        nrm = np.empty(len(me.polygons) * 3)
        me.polygons.foreach_get('normal', nrm)
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        ev = np.empty(ne * 2, np.int64)
        me.edges.foreach_get('vertices', ev)
        nrm, co, ev = nrm.reshape(-1, 3), co.reshape(-1, 3), ev.reshape(-1, 2)
        le = np.empty(len(me.loops), np.int64)
        me.loops.foreach_get('edge_index', le)
        lv = np.empty(len(me.loops), np.int64)
        me.loops.foreach_get('vertex_index', lv)
        ls = np.empty(len(me.polygons), np.int64)
        me.polygons.foreach_get('loop_start', ls)
        lt = np.empty(len(me.polygons), np.int64)
        me.polygons.foreach_get('loop_total', lt)
        lp = np.repeat(np.arange(len(ls)), lt)
        order = np.argsort(le, kind='stable')
        start = np.searchsorted(le[order], sel)
        l1, l2 = order[start], order[start + 1]
        a, b = co[ev[sel, 0]], co[ev[sel, 1]]
        span = np.linalg.norm(b - a, axis=1)
        e = (b - a) / np.maximum(span, 1e-30)[:, None]

        def into(lo):                                    # (unit direction into the face across the edge - from its
            f = lp[lo]                                   # loop's turning: inside is left of the edge as the face runs
            n = nrm[f]                                   # - and how far the face reaches that way; a big or bent
            u = np.cross(n, e)                           # face's centre can lie outside it)
            u[lv[lo] != ev[sel, 0]] *= -1.0
            u /= np.maximum(np.linalg.norm(u, axis=1), 1e-30)[:, None]
            reach = np.zeros(len(f))
            for k, (fk, uk, ak) in enumerate(zip(f.tolist(), u, a)):
                pts = co[lv[ls[fk]:ls[fk] + lt[fk]]]
                reach[k] = float(((pts - ak) @ uk).max())
            return f, u, 0.5 * np.maximum(reach, 0.0)
        f1, u1, s1 = into(l1)
        f2, u2, s2 = into(l2)

        def surface(pts, fallback):                      # (nearest original point + its normal, facing like ours)
            P = np.array(pts)
            N = np.array(fallback, dtype=np.float64)
            for i, p in enumerate(pts.tolist()):
                hit = bvh.find_nearest(p)
                if hit[0] is not None:
                    P[i] = hit[0]
                    N[i] = hit[1]
            N[(N * fallback).sum(1) < 0] *= -1.0
            return P, N
        cap = 0.1 * he._size(me)
        flat = math.cos(MATCH_FLAT)
        ts = []
        for k in (0.25, 0.5, 0.75):
            m = a + k * (b - a)
            p1, n1, p2, n2 = m.copy(), nrm[f1].copy(), m.copy(), nrm[f2].copy()
            used = np.zeros(len(sel))
            read = np.zeros(len(sel), bool)
            for reach in (0.25, 0.5, 1.0, 1.5):          # (as far in as the original is still that face's flat:
                r1, r2 = np.minimum(reach * s1, cap), np.minimum(reach * s2, cap)     # away from the rounding;
                q1, m1 = surface(m + u1 * r1[:, None], nrm[f1])                       # a face that isn't a
                q2, m2 = surface(m + u2 * r2[:, None], nrm[f2])                       # rectangle can end
                ok = ((m1 * nrm[f1]).sum(1) > flat) & ((m2 * nrm[f2]).sum(1) > flat)  # before its reach)
                p1[ok], n1[ok], p2[ok], n2[ok], used[ok] = q1[ok], m1[ok], q2[ok], m2[ok], np.minimum(r1, r2)[ok]
                read |= ok
            c12 = np.clip((n1 * n2).sum(1), -1.0, 1.0)
            det = np.maximum(1.0 - c12 ** 2, 1e-9)
            r1, r2 = (n1 * (p1 - m)).sum(1), (n2 * (p2 - m)).sum(1)
            x = m + ((r1 - c12 * r2) / det)[:, None] * n1 + ((r2 - c12 * r1) / det)[:, None] * n2
            far = np.linalg.norm(x - m, axis=1) > span       # (planes nearly parallel: the edge itself)
            x[far] = m[far]
            d = np.zeros(len(sel))
            for i, p in enumerate(x.tolist()):
                hit = bvh.find_nearest(p)
                d[i] = hit[3] if hit[0] is not None else 0.0
            phi = np.maximum(np.arccos(c12), MATCH_TURN)
            ts.append(np.where(read, np.minimum(d / np.tan(phi / 4.0), used), 0.0))   # (wider than where its
                                         # flats were read is not a rounding; flats not found: read as sharp)
        t = np.median(np.stack(ts), axis=0)
        # one width per line: the middle of each edge and its neighbours on the same line
        H = ev[sel]
        deg = np.bincount(H.ravel(), minlength=len(co))
        first = np.full(len(co), -1, np.int64)
        second = np.full(len(co), -1, np.int64)
        for j, (i0, i1) in enumerate(H.tolist()):
            for vtx in (i0, i1):
                if first[vtx] < 0:
                    first[vtx] = j
                else:
                    second[vtx] = j

        def other(vtx, j):
            o = np.where(first[vtx] == j, second[vtx], first[vtx])
            return np.where(deg[vtx] == 2, o, j)
        j = np.arange(len(H))
        out[sel] = np.median(np.stack([t[other(H[:, 0], j)], t, t[other(H[:, 1], j)]]), axis=0)
    a = me.attributes.get(he.ROUND)
    if a is None or a.domain != 'EDGE' or a.data_type != 'FLOAT':
        if a is not None:
            me.attributes.remove(a)
        a = me.attributes.new(he.ROUND, 'FLOAT', 'EDGE')
    a.data.foreach_set('value', out)
    return out[sel]


def _fit_group(ob):
    """Point group for Fit to Original: 0 on the hard edges (they stay where they are), 1 everywhere else."""
    me = ob.data
    hard = he.hard_flags(me)
    ev = np.empty(len(me.edges) * 2, np.int64)
    me.edges.foreach_get('vertices', ev)
    on = np.zeros(len(me.vertices), bool)
    on[ev.reshape(-1, 2)[hard].ravel()] = True
    g = ob.vertex_groups.get(he.FIT_GROUP) or ob.vertex_groups.new(name=he.FIT_GROUP)
    free = np.flatnonzero(~on).tolist()
    if free:
        g.add(free, 1.0, 'REPLACE')
    held = np.flatnonzero(on).tolist()
    if held:
        g.add(held, 0.0, 'REPLACE')
    return g


def build(context, ob, st, report=None):
    """Edge Mesh on mesh object ``ob`` (Object Mode, modifiers already applied by the caller).  Returns a message."""
    from . import budget
    src = he.source(ob)                              # (again on an Edge Mesh result: from its dense original)
    me = src.data if src is not None else ob.data
    if not len(me.polygons):
        raise RuntimeError('Edge Mesh: the mesh has no faces')
    if getattr(me, 'shape_keys', None) is not None:
        raise RuntimeError('Edge Mesh: remove the shape keys first')
    V, T, mats = _read(me)
    target = max(MIN_TARGET, int(st.em_detail))
    ok, why = budget.faces_fit(len(T) * 2)
    if not ok:
        raise RuntimeError('Edge Mesh: ' + why)
    angle = st.he_angle
    size = he._size(me)
    nt0 = len(T)
    auto = getattr(st, 'em_auto', False)
    if auto:                                         # 0.24.74 the count from Tolerance (written back to Detail)
        target, (V, T, idx) = auto_detail(V, T, st.em_tolerance * 0.01 * size, angle, report)
        mats = mats[idx]
        st.em_detail = max(MIN_TARGET, min(1_000_000, target))
    V, T, mats, steps = progressive(V, T, target, angle, adapt=st.em_adaptive, mats=mats, report=report)
    if st.em_straight:
        V = straighten(V, hard_lines(np.asarray(V, np.float64), T, angle))
    new = fd.fresh_like(me)
    try:
        fd.build_mesh(new, V, T)
        if len(new.materials) > 1 and mats is not None and len(mats) == len(new.polygons):
            new.polygons.foreach_set('material_index', np.clip(mats, 0, len(new.materials) - 1).astype(np.int32))
        for name in [a.name for a in new.attributes]:             # (nothing old carries over: UVs ... are gone)
            a = new.attributes.get(name)
            if a is not None and not name.startswith('.') and name not in ('position', 'material_index') \
                    and a.domain in {'POINT', 'EDGE', 'FACE', 'CORNER'}:
                try:
                    new.attributes.remove(a)
                except RuntimeError:
                    pass
        merge = min(MERGE * st.he_width, MERGE_MAX * size) if st.he_bevel else 0.0
        n, quads, tris = _mark_and_join(new, angle, size, merge)
        match_round(new, _bvh(me))                   # 0.24.74 (Match Original reads it; kept for when it's turned on)
    except Exception:
        bpy.data.meshes.remove(new)
        raise
    old = ob.data
    name = old.name
    ob.data = new
    if src is not None:                              # (the earlier result goes, the original stays kept)
        if old.users == 0:
            bpy.data.meshes.remove(old)
            new.name = name
    else:                                            # (the old mesh is the off-scene original now)
        if old.users == 0:                           # (an Alt+D twin still showing it keeps its name)
            old.name = name + '_EdgeSource'
            new.name = name
        he.keep_source(ob, old)
    _fit_group(ob)
    ob[he.KEY] = 1
    if st.he_subdiv == 0:                            # (the client look needs the subdivision)
        st.he_subdiv = 2
    if st.he_bevel and st.he_crease:                 # (the support bevel makes the edge: a full crease on top
        st.he_crease = False                         # pinches it and shades wrong without Sharp marks; without
                                                     # a bevel the crease is what keeps the edges)
    he.set_live(ob, st)
    if len(T) < nt0:
        head = f'{nt0:,} -> {len(T):,} triangles' + (' (Auto)' if auto else '')
    else:
        head = f'{nt0:,} triangles (' + ('already within Tolerance' if auto else 'lighter than Detail') + ')'
    return f'Edge Mesh: {head}, {n:,} hard edges, {quads:,} quads + {tris:,} triangles'
