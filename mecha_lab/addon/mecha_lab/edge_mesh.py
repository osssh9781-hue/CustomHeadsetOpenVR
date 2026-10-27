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
        V, T, _vs, fs = fd.run(V, T, goal, even=n0 <= EVEN_FROM * target, weight=w)
        V, T = V.copy(), T.copy()
        if mats is not None:
            mats = mats[fs]
        steps += 1
        if report:
            report(steps, len(T))
        if len(T) >= n0:                                 # (nothing more comes off: stop)
            break
    return V, T, mats, steps


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
    nv0, nt0 = len(V), len(T)
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
    if st.he_crease:                                 # (the support bevel makes the edge: a full crease on top
        st.he_crease = False                         # pinches it and shades wrong without Sharp marks)
    he.set_live(ob, st)
    head = f'{nt0:,} -> {len(T):,} triangles in {steps} steps' if steps else f'{nt0:,} triangles (lighter than Detail)'
    return f'Edge Mesh: {head}, {n:,} hard edges, {quads:,} quads + {tris:,} triangles'
