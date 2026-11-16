"""0.24.179 Hair in a Sculpted Shape (user: "털 부분에 내가 만든 털 모양 스컬핑에 맞춰서 머리카락 만드는 거도 가능한가?" -
"따로 만든 메쉬"): pick the hair you sculpted (a mesh of its own - locks, a bun, a mane); strands fill it, following it
from where it sits on the body to its ends.  A live hair Curves object (the Fur tool's material - Cycles / EEVEE render
it as hair); the shape is hidden (it stays, a guide you can sculpt again and press Rebuild).

How:
* the body: the other mesh most of the shape's points sit on (found by itself); the roots: where the shape meets it
  (no body: each piece's top);
* the shape is read as clusters (cells about 1/70 of its size) joined along its edges; the distance from the roots
  along the shape (Dijkstra) gives each cluster its way on (away from the roots, smoothed) - a lock that bends round
  is followed round, not cut across;
* each strand starts at a point of the root area, a depth into the shape (Fill: from the skin to its middle), and
  steps along the way on, kept inside the shape at that depth, to the shape's end;
* then (quick, no tracing again): more strands beside the traced ones gathering to them toward the tips (Clump),
  Frizz, Curl, Length Random, thickness root to tip, colour root to tip.
"""
from __future__ import annotations

import heapq
import json
import math
import zlib

import bpy
import numpy as np
from bpy.props import BoolProperty, FloatProperty, FloatVectorProperty, IntProperty, PointerProperty
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

KEY = 'mch_hair_shape'                 # on the hair object: 1
COLLECTION = 'Creature Hair'
CELLS = 70                             # (the shape's size / this = a cluster's size)
TRACE_MAX = 1500                       # strands traced along the shape; more are made beside them
_CACHE = {}                            # hair object name -> {'key': trace settings, 'strands': [local (k, 3)], ...}
_PENDING = set()
_BUSY = [False]


class ShapeError(Exception):
    pass


# -----------------------------------------------------------------------------
# reading the shape
# -----------------------------------------------------------------------------

def _world_mesh(context, ob, colors=False):
    """(V world (n, 3), triangles (m, 3), edges (k, 2)) of ``ob`` as shown (its own geometry, not a light copy);
    ``colors``: also its painted colour per point ((n, 4), or None with no colour attribute)."""
    from . import light_copies as lc
    dg = context.evaluated_depsgraph_get()
    ev = lc.full(ob, dg)
    me = ev.to_mesh()
    col = None
    try:
        n = len(me.vertices)
        co = np.empty(n * 3, np.float64)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        M = np.array(ob.matrix_world)
        V = co @ M[:3, :3].T + M[:3, 3]
        me.calc_loop_triangles()
        T = np.empty(len(me.loop_triangles) * 3, np.int64)
        me.loop_triangles.foreach_get('vertices', T)
        E = np.empty(len(me.edges) * 2, np.int64)
        me.edges.foreach_get('vertices', E)
        if colors:
            col = _point_colors(ob, me)
    finally:
        ev.to_mesh_clear()
    if colors:
        return V, T.reshape(-1, 3), E.reshape(-1, 2), col
    return V, T.reshape(-1, 3), E.reshape(-1, 2)


def _point_colors(ob, me):
    """The painted colour (the active colour attribute - polypaint) per point of ``me``, or None."""
    try:
        name = ob.data.color_attributes.active_color_name
    except AttributeError:
        name = ''
    att = me.color_attributes.get(name) if name else None
    if att is None and len(me.color_attributes):
        att = me.color_attributes[0]
    if att is None or len(att.data) == 0:
        return None
    c = np.empty(len(att.data) * 4, np.float32)
    att.data.foreach_get('color', c)
    c = c.reshape(-1, 4).astype(np.float64)
    n = len(me.vertices)
    if att.domain == 'POINT' and len(c) == n:
        return c
    if att.domain == 'CORNER':
        lv = np.empty(len(me.loops), np.int64)
        me.loops.foreach_get('vertex_index', lv)
        acc = np.zeros((n, 4))
        np.add.at(acc, lv, c)
        cnt = np.bincount(lv, minlength=n).astype(float)
        return acc / np.maximum(cnt, 1.0)[:, None]
    return None


def find_body(context, shape, V, size):
    """The other visible mesh most of the shape's points sit on (within 2 % of its size), or None."""
    lo, hi = V.min(0) - size * 0.05, V.max(0) + size * 0.05
    step = max(1, len(V) // 400)
    sample = V[::step]
    tol = size * 0.02
    best, best_n = None, 0
    for ob in context.visible_objects:
        if ob is shape or ob.type != 'MESH' or ob.get(KEY):
            continue
        bb = np.array([tuple(ob.matrix_world @ Vector(c)) for c in ob.bound_box])
        if (bb.max(0) < lo).any() or (bb.min(0) > hi).any():
            continue
        try:
            BV, BT, _E = _world_mesh(context, ob)
        except RuntimeError:
            continue
        if not len(BT):
            continue
        bvh = BVHTree.FromPolygons([tuple(p) for p in BV], [tuple(t) for t in BT])
        n = sum(1 for p in sample if (bvh.find_nearest(Vector(p))[3] or 1e9) < tol)
        if n > best_n:
            best, best_n = ob, n
    return best if best_n >= 3 else None


def analyse(context, shape, body=None, starts=None):
    """The shape's flow: clusters (centroids), the distance along the shape from the roots, the way on, thickness;
    its surface (BVH); the root triangles.  ``starts`` (world points clicked on the shape - 0.24.179 user: "결 시작
    부분은 내가 찍어 주는 게 낫지 않나?"): the roots there, not found from the body."""
    V, T, E, colors = _world_mesh(context, shape, colors=True)
    if not len(T):
        raise ShapeError(f'"{shape.name}" has no faces - pick the hair shape you sculpted (a mesh)')
    size = float(np.ptp(V, axis=0).max())
    h = size / CELLS
    cells = np.floor((V - V.min(0)) / h).astype(np.int64)
    K = int(cells.max()) + 2
    keyv = cells[:, 0] + cells[:, 1] * K + cells[:, 2] * K * K
    _u, inv = np.unique(keyv, return_inverse=True)
    nC = int(inv.max()) + 1
    cnt = np.bincount(inv, minlength=nC).astype(float)
    cen = np.stack([np.bincount(inv, weights=V[:, k], minlength=nC) for k in range(3)], axis=1) / cnt[:, None]
    ca, cb = inv[E[:, 0]], inv[E[:, 1]]
    m = ca != cb
    pairs = np.unique(np.sort(np.stack([ca[m], cb[m]], axis=1), axis=1), axis=0)
    adj = [[] for _ in range(nC)]
    wts = np.linalg.norm(cen[pairs[:, 0]] - cen[pairs[:, 1]], axis=1)
    for (a, b), w in zip(pairs.tolist(), wts.tolist()):
        adj[a].append((b, w))
        adj[b].append((a, w))
    bvh = BVHTree.FromPolygons([tuple(p) for p in V], [tuple(t) for t in T])
    if body is None:
        body = find_body(context, shape, V, size)
    tol = size * 0.03
    roots = np.zeros(nC, bool)                        # (where the distance starts: at the body's skin and in it)
    skin = np.zeros(nC, bool)                         # (where strands start: at the skin)
    if starts:                                        # (picked: round each clicked point)
        rs = max(h * 3.0, size * 0.05)
        for q in starts:
            near = np.linalg.norm(cen - np.asarray(q, float), axis=1) < rs
            roots |= near
            skin |= near
    elif body is not None:
        BV, BT, _E = _world_mesh(context, body)
        bb = BVHTree.FromPolygons([tuple(p) for p in BV], [tuple(t) for t in BT])
        for c in range(nC):
            loc, nrm, _i, d = bb.find_nearest(Vector(cen[c]))
            if loc is None:
                continue
            inside = float(np.dot(cen[c] - np.array(loc), np.array(nrm))) < 0
            if d < tol:
                roots[c] = skin[c] = True
            elif inside:                              # (the part of the shape sunk into the body)
                roots[c] = True
    # pieces of the shape (the cluster graph's parts): a piece with no root starts at its top
    comp = -np.ones(nC, np.int64)
    k = 0
    for s in range(nC):
        if comp[s] >= 0:
            continue
        stack = [s]
        comp[s] = k
        while stack:
            x = stack.pop()
            for y, _w in adj[x]:
                if comp[y] < 0:
                    comp[y] = k
                    stack.append(y)
        k += 1
    for piece in range(k):
        idx = np.nonzero(comp == piece)[0]
        if not roots[idx].any():                      # (its top: the clusters within a cell of the highest)
            top = cen[idx, 2].max()
            near = idx[cen[idx, 2] >= top - h * 1.5]
            roots[near] = skin[near] = True
        elif not skin[idx].any():
            skin[idx[roots[idx]]] = True
    D = np.full(nC, np.inf)
    parent = -np.ones(nC, np.int64)
    heap = []
    for c in np.nonzero(roots)[0]:
        D[c] = 0.0
        heap.append((0.0, int(c)))
    heapq.heapify(heap)
    while heap:
        d, x = heapq.heappop(heap)
        if d > D[x]:
            continue
        for y, w in adj[x]:
            nd = d + w
            if nd < D[y]:
                D[y] = nd
                parent[y] = x
                heapq.heappush(heap, (nd, y))
    D[~np.isfinite(D)] = 0.0
    # how thick the shape is at each cluster (straight in from its surface to the other side)
    thick = np.full(nC, size * 0.05)
    for c in range(nC):
        loc, nrm, _i, _d = bvh.find_nearest(Vector(cen[c]))
        if loc is None:
            continue
        o = loc - nrm * (h * 0.01)
        hit = bvh.ray_cast(o, -nrm, size)
        if hit[0] is not None:
            thick[c] = max(min((hit[0] - o).length, size * 0.4), h * 0.2)
    kd0 = KDTree(nC)
    for c in range(nC):
        kd0.insert(Vector(cen[c]), c)
    kd0.balance()
    # 0.24.180 the thickness evened over 3 cells (the median: a ray slipping out at an edge is one far-off cluster)
    ts = thick.copy()
    for c in range(nC):
        nb = [i for _co, i, _d in kd0.find_range(Vector(cen[c]), h * 3.0)]
        if nb:
            ts[c] = float(np.median(thick[nb]))
    thick = ts
    # the way on: where the distance from the roots grows fastest round each cluster (a fit over the clusters within
    # 3 cells - the shortest paths' own steps zigzag round a lock's sides)
    # (first the distance evened round the lock: each cluster the mean over the clusters within its thickness - the
    #  surface distance differs between a bend's inside and outside; so it becomes a distance along the lock)
    Ds = D.copy()
    for c in range(nC):
        nb = [i for _co, i, _d in kd0.find_range(Vector(cen[c]), max(h * 3.0, thick[c] * 0.6))]
        if nb:
            Ds[c] = float(np.mean(D[nb]))
    D = Ds
    way = np.zeros((nC, 3))
    for c in range(nC):
        R = max(h * 3.0, thick[c] * 0.5)
        nb = [i for _co, i, _d in kd0.find_range(Vector(cen[c]), R) if i != c]
        if len(nb) < 3:
            nb = [i for _co, i, _d in kd0.find_n(Vector(cen[c]), 8) if i != c]
        A = cen[nb] - cen[c]
        bvec = D[nb] - D[c]
        g, *_r = np.linalg.lstsq(A, bvec, rcond=None)
        way[c] = g
    bad = np.linalg.norm(way, axis=1) < 1e-9
    has = parent >= 0
    way[bad & has] = (cen - cen[np.maximum(parent, 0)])[bad & has]
    way /= np.maximum(np.linalg.norm(way, axis=1, keepdims=True), 1e-12)
    for _it in range(2):                              # (smoothed a little over the neighbours)
        acc = way.copy()
        for (a_, b_) in pairs.tolist():
            acc[a_] += way[b_]
            acc[b_] += way[a_]
        way = acc / np.maximum(np.linalg.norm(acc, axis=1, keepdims=True), 1e-12)
    dmax = np.zeros(nC)
    for piece in range(k):
        idx = np.nonzero(comp == piece)[0]
        dmax[idx] = D[idx].max()
    kd = kd0
    root_tris = T[skin[inv[T]].sum(1) >= 2]
    if not len(root_tris):
        root_tris = T[skin[inv[T]].any(1)]
    return {'V': V, 'T': T, 'root_tris': root_tris, 'bvh': bvh, 'kd': kd, 'cen': cen, 'D': D, 'dmax': dmax,
            'way': way, 'thick': thick, 'h': h, 'size': size, 'body': body, 'roots': int(roots.sum()), 'pieces': k,
            'picked': bool(starts), 'rootc': roots, 'comp': comp, 'colors': colors}


# -----------------------------------------------------------------------------
# strands
# -----------------------------------------------------------------------------

def _seeds(a, n, fill, rng):
    """0.24.180 (user: "메쉬에서 만드는 머리카락 좋긴 한데 좀 더 메쉬 외곽까지의 형태가 비슷한 게 좋을 거 같아"): ``n``
    points spread through the shape's volume (no deeper than ``fill`` of the way to its middle), each with its depth
    as a share of the half thickness there.  A strand is traced through each - back to the roots and on to the
    end - so where the shape is wide the strands are spread to its outline (traced from the roots alone they stayed
    as close together as the roots: a fan / a bulge was filled a third)."""
    V, bvh, kd, thick, h = a['V'], a['bvh'], a['kd'], a['thick'], a['h']
    lo, hi = V.min(0), V.max(0)
    pts, rho = [], []
    top = max(float(fill), 0.05)
    for _round in range(80):
        Q = lo + rng.random((max(4 * n, 4000), 3)) * (hi - lo)
        for q in Q:
            loc, nrm, _i, d = bvh.find_nearest(Vector(q))
            if loc is None or (Vector(q) - loc).dot(nrm) >= 0.0:          # (outside)
                continue
            _co, c, _dd = kd.find(loc)
            r = d / max(thick[c] * 0.5, 1e-12)
            if d < h * 0.05 or r > top:
                continue
            pts.append(q)
            rho.append(min(r, 1.0))
            if len(pts) >= n:
                return np.array(pts), np.array(rho)
    return np.array(pts).reshape(-1, 3), np.array(rho)


def _walk(a, p, rho, back, step):
    """From ``p`` along the way on (``back``: against it, to the roots), kept at ``rho`` of the half thickness under
    the shape's skin.  Returns (points after ``p``, reached: the roots / the end)."""
    bvh, kd, way, D, dmax, thick, h, rootc = (a['bvh'], a['kd'], a['way'], a['D'], a['dmax'], a['thick'], a['h'],
                                              a['rootc'])
    sign = -1.0 if back else 1.0
    pts = []
    prev = None
    _co, c, _dd = kd.find(Vector(p))
    best, stall = -1e18, 0
    limit = int(max(dmax[c], h) / step * 3.0) + 20
    for _s in range(limit):
        _co, c, _dd = kd.find(Vector(p))
        if back and rootc[c]:
            return pts, True
        d = way[c] * sign
        if prev is not None:
            d = prev * 0.5 + d * 0.5
            d = d / max(np.linalg.norm(d), 1e-12)
        q = p + d * step
        sl, sn, _i, _dist = bvh.find_nearest(Vector(q))
        if sl is not None:
            sl, sn = np.array(sl), np.array(sn)
            depth = -float(np.dot(q - sl, sn))
            want = min(max(rho * thick[c] * 0.5, h * 0.08), thick[c] * 0.48)
            if depth < h * 0.05:                       # (leaving the shape: back in, at its depth)
                q = sl - sn * want
            else:                                      # (eased to its depth: the strands keep their place across)
                q = q - sn * ((want - depth) * 0.25)
        moved = q - p
        if np.linalg.norm(moved) < step * 0.05:
            break
        prev = moved / np.linalg.norm(moved)
        p = q
        pts.append(p.copy())
        _co, c2, _dd = kd.find(Vector(p))
        prog = -D[c2] if back else D[c2]
        if prog > best + h * 0.05:
            best, stall = prog, 0
        else:
            stall += 1
        if not back and D[c2] >= dmax[c2] * 0.985:
            return pts, True
        if stall > 10:
            break
    return pts, False


def trace(a, n, fill, seed):
    """``n`` strands (world points, root first) through the shape: each through a point spread in its volume
    (``_seeds``), back to the roots and on to its end, kept at its share of the depth.  Returns (strands, the piece
    of the shape each runs in)."""
    rng = np.random.default_rng(seed)
    h, D, dmax, kd = a['h'], a['D'], a['dmax'], a['kd']
    step = h * 0.9
    seeds, rho = _seeds(a, int(n * 1.25) + 8, fill, rng)
    out = []
    pieces = []
    for q, r in zip(seeds, rho):
        back, rooted = _walk(a, q, r, True, step)
        if not rooted:                                 # (lost on the way back: kept only if it began near the roots)
            _co, c0, _dd = kd.find(Vector(back[-1] if back else q))
            if D[c0] > dmax[c0] * 0.15:
                continue
        fwd, _end = _walk(a, q, r, False, step)
        pts = back[::-1] + [q] + fwd
        if len(pts) >= 3:
            out.append(np.array(pts))
            _co, cq, _dd = kd.find(Vector(q))
            pieces.append(int(a['comp'][cq]))
        if len(out) >= n:
            break
    if not out:
        raise ShapeError('No strand could run through the shape')
    return out, pieces


def resample(P, n):
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    if s[-1] <= 1e-12:
        return np.repeat(P[:1], n, axis=0)
    t = np.linspace(0.0, s[-1], n)
    return np.stack([np.interp(t, s, P[:, k]) for k in range(3)], axis=1)


# -----------------------------------------------------------------------------
# 0.24.180 shaping the traced strands (user: "그래비티나 그런 게 왜 메쉬 머리카락에는 안 되는겨", "원래 기존에 있던
# 헤어 세팅 다 쓸 수 있으면 좋겠어", "머리카락 빗는 것도 만들어 주고"): the traced ones (guides) - Length, Bend,
# Gravity, then the combing, then out of the body; the rest of the strands are made beside them (finish).
# -----------------------------------------------------------------------------

def _turn(G, goal, w):
    """Each segment of the strands ``G`` (n, seg, 3) turned toward ``goal`` (unit: (3,) or per segment) by ``w``
    (per segment), its length kept - built again from the root."""
    v = np.diff(G, axis=1)
    L = np.linalg.norm(v, axis=2, keepdims=True)
    d = v / np.maximum(L, 1e-12)
    nd = d + w[..., None] * (goal - d)
    n_ = np.linalg.norm(nd, axis=2, keepdims=True)
    nd = np.where(n_ > 1e-6, nd / np.maximum(n_, 1e-12), d)          # (turned right round: kept)
    out = G.copy()
    out[:, 1:] = G[:, :1] + np.cumsum(nd * L, axis=1)
    return out


def _length(G, frac):
    """The strands cut to ``frac`` of their length, or carried on straight past their tips (above 1)."""
    if abs(frac - 1.0) < 1e-6:
        return G
    seg = G.shape[1]
    u = np.linspace(0.0, frac, seg) * (seg - 1)
    i0 = np.clip(np.floor(u).astype(np.int64), 0, seg - 2)
    w = (u - i0)[None, :, None]
    return G[:, i0] * (1.0 - w) + G[:, i0 + 1] * w


def _ramp(t, at, soft):
    """0 before ``at``, 1 after it, over ``soft`` (smooth)."""
    lo, hi = at - soft * 0.5, at + soft * 0.5 + 1e-6
    x = np.clip((t - lo) / (hi - lo), 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def shaped(G0, p, M):
    """Length, Bend, Gravity on the traced strands (local); ``M`` the hair's world matrix."""
    G = _length(G0, float(p.length))
    seg = G.shape[1]
    tm = (np.arange(seg - 1) + 0.5) / max(seg - 1, 1)
    inv = np.linalg.inv(np.array(M)[:3, :3])
    if p.bend > 1e-6:
        bd = inv @ np.array(tuple(p.bend_dir), float)
        bd /= max(np.linalg.norm(bd), 1e-12)
        w = _ramp(tm, float(p.bend_at), float(p.bend_soft)) * min(1.0, float(p.bend) / (math.pi / 2))
        G = _turn(G, bd[None, None, :], np.tile(w, (len(G), 1)))
    if p.gravity > 1e-6:
        down = inv @ np.array((0.0, 0.0, -1.0))
        down /= max(np.linalg.norm(down), 1e-12)
        w = np.clip(float(p.gravity) * tm ** 0.8, 0.0, 1.0)
        G = _turn(G, down[None, None, :], np.tile(w, (len(G), 1)))
    return G


COMBS = 'mch_hair_combs'               # on the hair object: the comb strokes (its local space, JSON)


def combs_of(ob):
    try:
        return json.loads(ob.get(COMBS, '[]'))
    except ValueError:
        return []


def comb_sample(G, ref, c, d, v, r, strength, restore=False):
    """One step of a comb stroke on the strands ``G`` (changed in place): the segments within ``r`` across of the
    line through ``c`` along the view ``v`` (from ``r`` in front to 1.5 ``r`` behind) turned toward ``d`` (Restore:
    back toward ``ref``'s), the root's segment half as much.  Returns the strands changed."""
    mids = (G[:, 1:] + G[:, :-1]) * 0.5
    rel = mids - c
    along = rel @ v
    lat = np.linalg.norm(rel - along[..., None] * v, axis=2)
    m = (lat < r) & (along > -r) & (along < r * 1.5)
    if not m.any():
        return np.zeros(0, np.int64)
    rows = np.nonzero(m.any(1))[0]
    w = np.zeros(m.shape)
    w[m] = float(strength) * 0.35 * (1.0 - (lat[m] / r) ** 2) ** 2
    w[:, 0] *= 0.5
    if restore:
        rv = np.diff(ref[rows], axis=1)
        goal = rv / np.maximum(np.linalg.norm(rv, axis=2, keepdims=True), 1e-12)
    else:
        goal = np.asarray(d, float)[None, None, :]
    G[rows] = _turn(G[rows], goal, w[rows])
    return rows


def combed(Gs, strokes):
    G = Gs.copy()
    for st in strokes:
        r, sv, v = float(st.get('r', 0.1)), float(st.get('s', 0.5)), np.array(st.get('v', (0, 0, -1)), float)
        for q in st.get('p', ()):
            comb_sample(G, Gs, np.array(q[:3]), np.array(q[3:6]), v, float(q[6]) if len(q) > 6 else r, sv,
                        st.get('m') == 'R')
    return G


_BODY = {}                             # body name -> (key, BVH world, size)


def _body_tree(context, body):
    key = (body.data.as_pointer(), len(body.data.vertices), tuple(tuple(r) for r in body.matrix_world))
    hit = _BODY.get(body.name)
    if hit is not None and hit[0] == key:
        return hit[1], hit[2]
    V, T, _E = _world_mesh(context, body)
    bvh = BVHTree.FromPolygons([tuple(q) for q in V], [tuple(t) for t in T]) if len(T) else None
    size = float(np.ptp(V, axis=0).max()) if len(V) else 1.0
    _BODY.clear()
    _BODY[body.name] = (key, bvh, size)
    return bvh, size


def _inside_mask(Gw, bvh):
    m = np.zeros(Gw.shape[:2], bool)
    for i in range(Gw.shape[0]):
        for j in range(Gw.shape[1]):
            loc, nrm, _f, _d = bvh.find_nearest(Vector(Gw[i, j]))
            if loc is not None and (Vector(Gw[i, j]) - loc).dot(nrm) < 0.0:
                m[i, j] = True
    return m


def collide(Gw, keep, bvh, eps):
    """The strands (world) kept out of the body: built again from the root, a point that would go in is put on the
    body's skin (its segment's length kept); points in it from the start (``keep`` - a root sunk in) stay."""
    v = np.diff(Gw, axis=1)
    L = np.linalg.norm(v, axis=2)
    d = v / np.maximum(L[..., None], 1e-12)
    P = Gw.copy()
    reach = float(L.max()) * 2.0 + eps * 4.0 if L.size else eps
    for j in range(1, Gw.shape[1]):
        want = P[:, j - 1] + d[:, j - 1] * L[:, j - 1, None]
        for i in np.nonzero(~keep[:, j])[0]:
            q = Vector(want[i])
            loc, nrm, _f, _d = bvh.find_nearest(q, reach)
            if loc is not None and (q - loc).dot(nrm) < eps:
                dv = np.array(loc + nrm * eps) - P[i, j - 1]
                want[i] = P[i, j - 1] + dv / max(np.linalg.norm(dv), 1e-12) * L[i, j - 1]
        P[:, j] = want
    return P


def guides(ob, cache, p, context=None):
    """The traced strands as drawn (local, (n, seg, 3)): resampled, shaped, combed, kept out of the body - each step
    kept until what it reads changes."""
    seg = int(p.segments)
    if cache.get('k0') != seg:
        cache['G0'] = np.array([resample(q, seg) for q in cache['strands']])
        cols = cache.get('colors')
        cache['C0'] = (np.array([np.stack([np.interp(np.linspace(0, 1, seg), np.linspace(0, 1, len(c_)), c_[:, k])
                                           for k in range(4)], axis=1) for c_ in cols]) if cols is not None else None)
        cache['k0'] = seg
        for k in ('k1', 'k2', 'k3', 'mask'):
            cache.pop(k, None)
    M = ob.matrix_world
    k1 = (seg, round(p.length, 5), round(p.bend, 5), round(p.bend_at, 5), round(p.bend_soft, 5),
          tuple(round(x, 5) for x in p.bend_dir), round(p.gravity, 5), tuple(tuple(round(x, 6) for x in r) for r in M))
    if cache.get('k1') != k1:
        cache['Gs'] = shaped(cache['G0'], p, M)
        cache['k1'] = k1
    raw = ob.get(COMBS, '')
    k2 = (k1, zlib.crc32(raw.encode()) if raw else 0)
    if cache.get('k2') != k2:
        cache['Gc'] = combed(cache['Gs'], combs_of(ob)) if raw else cache['Gs']
        cache['k2'] = k2
    k3 = (k2, _bkey(ob, p, raw))
    if cache.get('k3') != k3:
        cache['Gf'] = settle(ob, cache, cache['Gc'], context)
        cache['k3'] = k3
    return cache['Gf']


def _moved(p, raw):
    return bool(raw) or p.gravity > 1e-6 or p.bend > 1e-6 or p.length > 1.0 + 1e-6


def _bkey(ob, p, raw):
    body = p.body
    if body is None or body.type != 'MESH' or not _moved(p, raw):
        return None
    return (body.name, body.data.as_pointer(), len(body.data.vertices))


def settle(ob, cache, G, context=None, rows=None, force=False):
    """``G`` (local) kept out of the hair's body (``rows``: only those strands); as it is with no body or nothing
    moved (``force``: a comb stroke's strands - moved)."""
    p = ob.mch_hshape
    body = p.body
    raw = ob.get(COMBS, '')
    if body is None or body.type != 'MESH' or not (force or _moved(p, raw)):
        return G if rows is None else G[rows]
    bvh, bsize = _body_tree(context or bpy.context, body)
    if bvh is None:
        return G if rows is None else G[rows]
    M = np.array(ob.matrix_world)
    if cache.get('mask') is None:
        G0w = cache['G0'] @ M[:3, :3].T + M[:3, 3]
        cache['mask'] = _inside_mask(G0w, bvh)
    sub = G if rows is None else G[rows]
    keep = cache['mask'] if rows is None else cache['mask'][rows]
    if keep.shape != sub.shape[:2]:
        keep = np.zeros(sub.shape[:2], bool)
    W = sub @ M[:3, :3].T + M[:3, 3]
    eps = max(float(p.root_thick) * 2.0, bsize * 0.0015)
    P = collide(W, keep, bvh, eps)
    return (P - M[:3, 3]) @ np.linalg.inv(M[:3, :3]).T


def _tufts(G, N, size_):
    """Each traced strand's tuft: the traced strand its tips gather to (Clump Size strands a tuft)."""
    nT = len(G)
    n_t = int(round(N / max(int(size_), 1)))
    if n_t >= nT:
        return np.arange(nT)
    n_t = max(n_t, 1)
    mid = G[:, G.shape[1] // 2]
    kd = KDTree(n_t)
    for i in range(n_t):
        kd.insert(Vector(mid[i]), i)
    kd.balance()
    return np.array([kd.find(Vector(q))[1] for q in mid], np.int64)


def finish(G, p, size, seed, pieces=None, colors=None, body_colors=None, base=None):
    """The strands as drawn (local): (points (N, seg, 3), radius (N, seg), colour (N, seg, 4)) - the traced ones
    ``G`` (n, seg, 3) and Amount - n more beside them; Spread, Clump (+ Size), Tip Gather, Volume, Length Random,
    Frizz, Curl; thickness; colour (``colors``: painted, per traced point).  ``base``: the traced strands as traced
    (the others are set round their roots by them: a comb or Gravity does not move the roots)."""
    rng = np.random.default_rng(seed + 7)
    nT = len(G)
    seg = G.shape[1] if nT else int(p.segments)
    if not nT:
        return np.zeros((0, seg, 3)), np.zeros((0, seg)), np.zeros((0, seg, 4))
    N = max(int(p.count), 1)
    t = np.linspace(0.0, 1.0, seg)
    h = size / CELLS
    src = np.arange(N) % nT
    S = G[src].copy()
    kids = np.nonzero(np.arange(N) >= nT)[0]
    if len(kids):                                      # (made beside a traced one: Spread)
        B = base if base is not None and base.shape == G.shape else G
        tan = B[src[kids], 1] - B[src[kids], 0]
        tan /= np.maximum(np.linalg.norm(tan, axis=1, keepdims=True), 1e-12)
        o = rng.normal(size=(len(kids), 3))
        o -= tan * np.sum(o * tan, axis=1, keepdims=True)
        o /= np.maximum(np.linalg.norm(o, axis=1, keepdims=True), 1e-12)
        o *= (h * (0.4 + 3.0 * float(p.spread)) * rng.random(len(kids)) ** 0.5)[:, None]
        S[kids] += o[:, None, :]
    if p.length_random > 0:
        cut = 1.0 - float(p.length_random) * rng.random(N)
        u = cut[:, None] * np.arange(seg)[None, :]
        i0 = np.clip(np.floor(u).astype(np.int64), 0, seg - 2)
        w = (u - i0)[..., None]
        S = (np.take_along_axis(S, i0[..., None], axis=1) * (1.0 - w)
             + np.take_along_axis(S, (i0 + 1)[..., None], axis=1) * w)
    if p.clump > 0:                                    # (the tips gathered into tufts)
        cen = _tufts(G, N, p.clump_size)
        S += (G[cen[src]] - S) * (float(p.clump) * t ** 0.8)[None, :, None]
    pc = np.asarray(pieces if pieces is not None else np.zeros(nT), np.int64)
    if p.gather > 0 or p.volume > 0:
        ids = np.unique(pc)
        if p.gather > 0:                               # (Tip Gather: a piece's tips meet at its end)
            end = {k: G[pc == k, -1].mean(0) for k in ids}
            E = np.array([end[k] for k in pc[src]])
            S += (E - S[:, -1])[:, None, :] * (float(p.gather) * t ** 1.5)[None, :, None]
        if p.volume > 0:                               # (Volume: fuller - out from the piece's middle)
            mid = {k: G[pc == k].mean(0) for k in ids}
            Mi = np.array([mid[k] for k in pc[src]])
            S += (S - Mi) * (float(p.volume) * 0.6 * np.minimum(t * 3.0, 1.0))[None, :, None]
    spread = h * 1.6
    if p.frizz > 0:
        wv = rng.normal(size=(N, 4, 3)) * spread * float(p.frizz)
        ph = rng.random((N, 4)) * 2 * math.pi
        k_ = np.arange(4) + 2
        sn = np.sin(t[None, None, :] * k_[None, :, None] * math.pi + ph[:, :, None])          # (N, 4, seg)
        S = S + np.einsum('njs,njc->nsc', sn, wv) * t[None, :, None]
    if p.curl > 0:
        tan = S[:, -1] - S[:, 0]
        tan /= np.maximum(np.linalg.norm(tan, axis=1, keepdims=True), 1e-12)
        ref = np.where(np.abs(tan[:, 2:3]) < 0.9, np.array([[0.0, 0.0, 1.0]]), np.array([[1.0, 0.0, 0.0]]))
        u_ = np.cross(tan, ref)
        u_ /= np.maximum(np.linalg.norm(u_, axis=1, keepdims=True), 1e-12)
        v_ = np.cross(tan, u_)
        ang = t[None, :] * float(p.curl_turns) * 2 * math.pi + rng.random(N)[:, None] * 2 * math.pi
        amp = float(p.curl) * spread * np.minimum(t * 4.0, 1.0)
        S = S + (np.cos(ang)[..., None] * u_[:, None, :] + np.sin(ang)[..., None] * v_[:, None, :]) * amp[None, :, None]
    R = np.tile(p.root_thick + (p.root_thick * p.tip_thin - p.root_thick) * t, (N, 1))
    tip = np.array(tuple(p.tip_color) + (1.0,))
    if p.use_polypaint and colors is not None:
        base = colors[src]
    elif p.use_polypaint and body_colors is not None:
        base = np.repeat(body_colors[src][:, None, :], seg, axis=1)
    else:
        base = np.tile(np.array(tuple(p.root_color) + (1.0,))[None, None, :], (N, seg, 1))
    mix = np.clip((t - (1.0 - p.tip_blend)) / max(p.tip_blend, 1e-6), 0.0, 1.0) if p.tip_blend > 0 else np.zeros(seg)
    Cc = base * (1 - mix[None, :, None]) + tip[None, None, :] * mix[None, :, None]
    Cc[..., 3] = 1.0
    return S, R, Cc


# -----------------------------------------------------------------------------
# the hair object
# -----------------------------------------------------------------------------

def is_hair(ob):
    return ob is not None and bool(ob.get(KEY))


def _trace_key(p):
    """What the tracing reads (0.24.180: not Amount - the strands beside the traced ones are made again only)."""
    return (round(p.fill, 4), int(p.seed))


def _collection(context):
    coll = bpy.data.collections.get(COLLECTION)
    if coll is None:
        coll = bpy.data.collections.new(COLLECTION)
    if coll.name not in context.scene.collection.children:
        context.scene.collection.children.link(coll)
    return coll


def _write(ob, P, R, Cc):
    """``ob``'s curves from points (N, seg, 3) local, radius, colour: in place when as many strands as long as
    before (0.24.180 - a comb stroke redraws them as you drag), else new curves data."""
    from . import creature_fur as cf
    old = ob.data
    N, seg = (P.shape[0], P.shape[1]) if len(P) else (0, 0)
    if (old is not None and N and len(old.curves) == N and len(old.points) == N * seg
            and old.attributes.get('mch_fur_col') is not None and old.attributes.get('radius') is not None):
        old.attributes['position'].data.foreach_set('vector', P.reshape(-1).astype(np.float32))
        old.attributes['radius'].data.foreach_set('value', R.reshape(-1).astype(np.float32))
        old.attributes['mch_fur_col'].data.foreach_set('color', Cc.reshape(-1).astype(np.float32))
        old.update_tag()
        ob.update_tag()
        return
    data = bpy.data.hair_curves.new(old.name if old is not None else 'Hair')
    N, seg = (P.shape[0], P.shape[1]) if len(P) else (0, 0)
    if N:
        data.add_curves([seg] * N)
        data.attributes['position'].data.foreach_set('vector', P.reshape(-1).astype(np.float32))
        rad = data.attributes.get('radius') or data.attributes.new('radius', 'FLOAT', 'POINT')
        rad.data.foreach_set('value', R.reshape(-1).astype(np.float32))
        col = data.attributes.new('mch_fur_col', 'FLOAT_COLOR', 'POINT')
        col.data.foreach_set('color', Cc.reshape(-1).astype(np.float32))
    mats = list(old.materials) if old is not None else []
    for m in (mats or [cf.fur_material()]):
        data.materials.append(m)
    try:
        if old is not None and old.surface is not None:
            data.surface = old.surface
    except (AttributeError, TypeError):
        pass
    ob.data = data
    if old is not None and old.users == 0:
        bpy.data.hair_curves.remove(old)


def _trace_into(context, ob, a):
    """Trace the strands for the hair ``ob`` (its settings) through the analysed shape: the cache entry."""
    p = ob.mch_hshape
    traced_w, pieces = trace(a, TRACE_MAX, p.fill, p.seed)
    colors = _paint_along(a, traced_w)
    body_cols = None
    if colors is None and a['body'] is not None:
        body_cols = _body_paint(context, a['body'], [q[0] for q in traced_w])
    inv = np.array(ob.matrix_world.inverted())
    return {'key': _trace_key(p), 'strands': [q @ inv[:3, :3].T + inv[:3, 3] for q in traced_w],
            'pieces': np.array(pieces, np.int64), 'colors': colors, 'body_colors': body_cols,
            'size': a['size'] / max(_scale(ob), 1e-9), 'roots': a['roots'], 'n_pieces': a['pieces']}


def _bary(bvh, V, T, col, q):
    loc, _n, f, _d = bvh.find_nearest(Vector(q))
    if loc is None or f is None:
        return None
    a_, b_, c_ = V[T[f, 0]], V[T[f, 1]], V[T[f, 2]]
    v0, v1, v2 = b_ - a_, c_ - a_, np.array(loc) - a_
    d00, d01, d11 = v0 @ v0, v0 @ v1, v1 @ v1
    d20, d21 = v2 @ v0, v2 @ v1
    den = d00 * d11 - d01 * d01
    if abs(den) < 1e-18:
        return col[T[f, 0]]
    v = (d11 * d20 - d01 * d21) / den
    w = (d00 * d21 - d01 * d20) / den
    return col[T[f, 0]] * (1 - v - w) + col[T[f, 1]] * v + col[T[f, 2]] * w


def _paint_along(a, strands):
    """0.24.180 Use Polypaint: the colour painted on the shape where each strand runs (per point), or None."""
    col = a.get('colors')
    if col is None:
        return None
    out = []
    for q in strands:
        c = [_bary(a['bvh'], a['V'], a['T'], col, x) for x in q]
        c = [x if x is not None else col.mean(0) for x in c]
        out.append(np.array(c))
    return out


def _body_paint(context, body, roots):
    """The body's painted colour at each root (the Fur tool's way), or None with no paint on it."""
    try:
        V, T, _E, col = _world_mesh(context, body, colors=True)
    except RuntimeError:
        return None
    if col is None or not len(T):
        return None
    bvh = BVHTree.FromPolygons([tuple(q) for q in V], [tuple(t) for t in T])
    out = [_bary(bvh, V, T, col, r) for r in roots]
    return np.array([x if x is not None else col.mean(0) for x in out])


VIEW_TREE = 'MCH Hair Viewport'
VIEW_MOD = 'MCH Hair Viewport'


def _view_tree():
    ng = bpy.data.node_groups.get(VIEW_TREE)
    if ng is not None and ng.get('mch_v') == 1:
        return ng
    if ng is None:
        ng = bpy.data.node_groups.new(VIEW_TREE, 'GeometryNodeTree')
    ng.nodes.clear()
    for it in list(ng.interface.items_tree):
        ng.interface.remove(it)
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    sh = ng.interface.new_socket('Viewport %', in_out='INPUT', socket_type='NodeSocketFloat')
    sh.default_value, sh.min_value, sh.max_value = 1.0, 0.0, 1.0
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
    isv = N.new('GeometryNodeIsViewport')
    rnd = N.new('FunctionNodeRandomValue')
    rnd.data_type = 'BOOLEAN'
    inv = N.new('ShaderNodeMath')
    inv.operation = 'SUBTRACT'
    inv.inputs[0].default_value = 1.0
    L.new(gi.outputs['Viewport %'], inv.inputs[1])
    L.new(inv.outputs[0], rnd.inputs['Probability'])
    both = N.new('FunctionNodeBooleanMath')
    both.operation = 'AND'
    L.new(isv.outputs[0], both.inputs[0])
    L.new(rnd.outputs[3] if len(rnd.outputs) > 3 else rnd.outputs['Value'], both.inputs[1])
    dele = N.new('GeometryNodeDeleteGeometry')
    dele.domain = 'CURVE'
    L.new(gi.outputs['Geometry'], dele.inputs['Geometry'])
    L.new(both.outputs[0], dele.inputs['Selection'])
    L.new(dele.outputs[0], go.inputs[0])
    ng['mch_v'] = 1
    return ng


def viewport_share(ob, share):
    """Viewport %: only that share of the strands drawn in the viewport (all of them render)."""
    mod = ob.modifiers.get(VIEW_MOD)
    if share >= 0.999:
        if mod is not None:
            ob.modifiers.remove(mod)
        return
    if mod is None:
        mod = ob.modifiers.new(VIEW_MOD, 'NODES')
        mod.node_group = _view_tree()
        mod.show_in_editmode = False
    from . import geo_sculpt as gs                     # (the modifier's input: the way every Mecha node tool sets it)
    gs.set_input(mod, 'Viewport %', float(share))
    ob.update_tag()


def rebuild(ob, context=None, force_trace=False):
    """``ob``'s strands from its settings: traced again only when Fill or Seed changed (or never in this session);
    Amount and the rest only make the strands again from the traced ones."""
    context = context or bpy.context
    p = ob.mch_hshape
    shape = p.shape
    cache = _CACHE.get(ob.name)
    if force_trace or cache is None or cache['key'] != _trace_key(p):
        if shape is None:
            raise ShapeError('Its shape is gone - pick the shape again')
        a = _analysed(context, shape, p.body, fresh=force_trace,
                      starts=[tuple(ob.matrix_world @ Vector(q)) for q in starts_of(ob)])
        cache = _trace_into(context, ob, a)
        _CACHE[ob.name] = cache
    G = guides(ob, cache, p, context)
    P, R, Cc = finish(G, p, cache['size'], p.seed, cache['pieces'], cache.get('C0'), cache.get('body_colors'),
                      cache.get('G0'))
    _write(ob, P, R, Cc)
    viewport_share(ob, p.display)
    return len(P)


def _scale(ob):
    s = ob.matrix_world.to_scale()
    return (abs(s.x) + abs(s.y) + abs(s.z)) / 3.0


_ANALYSED = {}                         # shape name -> (its mesh and place, the analysis): Fill / Seed trace again only


def starts_of(ob):
    try:
        return [tuple(q) for q in json.loads(ob.get(STARTS, '[]'))]
    except ValueError:
        return []


STARTS = 'mch_hair_starts'             # on the hair object: the start points clicked (its local space)


def _analysed(context, shape, body, fresh=False, starts=None):
    me = shape.data
    key = (me.as_pointer(), len(me.vertices), len(me.polygons), tuple(tuple(r) for r in shape.matrix_world),
           body.name if body is not None else None, tuple(tuple(round(x, 6) for x in q) for q in (starts or ())))
    hit = _ANALYSED.get(shape.name)
    if not fresh and hit is not None and hit[0] == key:
        return hit[1]
    a = analyse(context, shape, body, starts)
    _ANALYSED.clear()                                 # (one kept: they hold the shape's trees)
    _ANALYSED[shape.name] = (key, a)
    return a


def make(context, shape, body=None, starts=None):
    """A hair object filling ``shape`` (the Fur tool's settings for the next hair); ``starts``: world points where it
    starts (clicked), else found from the body.  Returns (object, message)."""
    st = context.scene.mch_hshape
    a = _analysed(context, shape, body, fresh=True, starts=starts)
    from . import creature_fur as cf
    data = bpy.data.hair_curves.new('Hair')
    data.materials.append(cf.fur_material())
    ob = bpy.data.objects.new(shape.name + ' Hair', data)
    _collection(context).objects.link(ob)
    holder = a['body'] or shape
    ob.matrix_world = Matrix.Identity(4)
    ob.parent = holder
    ob.matrix_parent_inverse = holder.matrix_world.inverted_safe()
    try:
        if a['body'] is not None:
            data.surface = a['body']
    except (AttributeError, TypeError):
        pass
    ob[KEY] = 1
    _BUSY[0] = True
    try:
        p = ob.mch_hshape
        for k in LIVE:
            setattr(p, k, getattr(st, k))
        if p.root_thick <= 0 or st.auto_thick:
            p.root_thick = a['size'] * 0.0012
        p.shape = shape
        p.body = a['body']
    finally:
        _BUSY[0] = False
    if starts:
        inv0 = ob.matrix_world.inverted()
        ob[STARTS] = json.dumps([list(inv0 @ Vector(q)) for q in starts])
    _ANALYSED[shape.name] = ((shape.data.as_pointer(), len(shape.data.vertices), len(shape.data.polygons),
                              tuple(tuple(r) for r in shape.matrix_world), a['body'].name if a['body'] else None,
                              tuple(tuple(round(x, 6) for x in Vector(q)) for q in ([ob.matrix_world @ Vector(v)
                                    for v in starts_of(ob)] if starts else ()))), a)
    _CACHE[ob.name] = _trace_into(context, ob, a)
    traced = _CACHE[ob.name]['strands']
    n = rebuild(ob, context)
    if p.hide_shape:
        shape.hide_set(True)
        shape.hide_render = True
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    if a.get('picked'):
        on = f' (from the {len(starts)} start{"s" if len(starts) != 1 else ""} you clicked)'
    elif a['body'] is not None:
        on = f' on "{a["body"].name}" (rooted where it meets it)'
    else:
        on = ' (no body under it: rooted at its top)'
    return ob, (f'Hair in "{shape.name}"{on}: {n:,} strands, {len(traced):,} traced through it, {a["pieces"]} '
                f'piece{"s" if a["pieces"] != 1 else ""} - its values live in the window')


# -----------------------------------------------------------------------------
# settings, operators, window
# -----------------------------------------------------------------------------

def _timer():
    names = list(_PENDING)
    _PENDING.clear()
    for n in names:
        ob = bpy.data.objects.get(n)
        if ob is not None and is_hair(ob):
            try:
                rebuild(ob)
            except ShapeError as ex:
                print('Mecha Lab hair:', ex)
    return None


def _upd(self, context):
    if _BUSY[0]:
        return
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and is_hair(ob):
        _PENDING.add(ob.name)
        if bpy.app.timers.is_registered(_timer):
            bpy.app.timers.unregister(_timer)
        bpy.app.timers.register(_timer, first_interval=0.15)


def _upd_hide(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and is_hair(ob) and self.shape is not None:
        try:
            self.shape.hide_set(self.hide_shape)
            self.shape.hide_render = self.hide_shape      # (in renders too: it would hide the hair inside it)
        except RuntimeError:
            pass


LIVE = ('count', 'fill', 'seed', 'segments', 'clump', 'frizz', 'curl', 'curl_turns', 'length_random', 'root_thick',
        'tip_thin', 'root_color', 'tip_color', 'tip_blend', 'hide_shape',
        # 0.24.180 the Fur tool's values too (user: "원래 기존에 있던 헤어 세팅 다 쓸 수 있으면 좋겠어")
        'length', 'display', 'volume', 'spread', 'gravity', 'clump_size', 'gather', 'bend', 'bend_at', 'bend_soft',
        'bend_dir', 'bend_side', 'use_polypaint')


class MCH_PG_HairShape(bpy.types.PropertyGroup):
    shape: PointerProperty(type=bpy.types.Object, name='Shape')
    body: PointerProperty(type=bpy.types.Object, name='Body')
    # 0.24.180 (user: "머리카락 양도 조절 가능하게"): live - the strands beside the traced ones made again, no tracing
    count: IntProperty(name='Amount', default=4000, min=10, soft_max=40000, max=200000, update=_upd,
                       description=f'How many strands (live: {TRACE_MAX} traced through the shape, the rest made '
                                   f'beside them - changing it traces nothing again)')
    fill: FloatProperty(name='Fill', default=0.8, min=0.0, max=1.0, update=_upd,
                        description='How deep into the shape the strands go: 0 only under its skin, 1 to its middle')
    seed: IntProperty(name='Seed', default=1, min=0, update=_upd)
    segments: IntProperty(name='Segments', default=24, min=4, max=96, update=_upd)
    clump: FloatProperty(name='Clump', default=0.6, min=0.0, max=1.0, update=_upd,
                         description='Strands made beside a traced one gather to it toward the tip')
    frizz: FloatProperty(name='Frizz', default=0.15, min=0.0, max=3.0, update=_upd)
    curl: FloatProperty(name='Curl', default=0.0, min=0.0, max=5.0, update=_upd)
    curl_turns: FloatProperty(name='Curl Turns', default=3.0, min=0.0, max=40.0, update=_upd)
    length_random: FloatProperty(name='Length Random', default=0.15, min=0.0, max=0.9, update=_upd)
    root_thick: FloatProperty(name='Root Thickness', default=0.0, min=0.0, soft_max=0.02, precision=4, unit='LENGTH',
                              update=_upd, description='Root radius (0: from the shape\'s size)')
    tip_thin: FloatProperty(name='Tip Thickness', default=0.2, min=0.0, max=1.0, update=_upd,
                            description='The tip\'s thickness, a share of the root\'s')
    root_color: FloatVectorProperty(name='Root Color', subtype='COLOR', size=3, min=0.0, max=1.0,
                                    default=(0.09, 0.06, 0.04), update=_upd)
    tip_color: FloatVectorProperty(name='Tip Color', subtype='COLOR', size=3, min=0.0, max=1.0,
                                   default=(0.32, 0.22, 0.14), update=_upd)
    tip_blend: FloatProperty(name='Tip Blend', default=0.5, min=0.0, max=1.0, update=_upd)
    hide_shape: BoolProperty(name='Hide the Shape', default=True, update=_upd_hide)
    # 0.24.180 the Fur tool's values (user: "그래비티나 그런 게 왜 메쉬 머리카락에는 안 되는겨", "원래 기존에 있던 헤어
    # 세팅 다 쓸 수 있으면 좋겠어")
    length: FloatProperty(name='Length', default=1.0, min=0.05, soft_max=2.0, max=5.0, update=_upd,
                          description='1: as long as the shape; less: shorter; more: on past the shape\'s end')
    display: FloatProperty(name='Viewport %', default=1.0, min=0.0, max=1.0, subtype='FACTOR', update=_upd,
                           description='The share of strands drawn in the viewport (all of them render)')
    volume: FloatProperty(name='Volume', default=0.0, min=0.0, max=1.0, update=_upd,
                          description='Fuller: the strands out from the middle of the shape (0: as the shape)')
    spread: FloatProperty(name='Spread', default=0.4, min=0.0, max=1.0, update=_upd,
                          description='How far beside a traced strand the others are made')
    gravity: FloatProperty(name='Gravity', default=0.0, min=0.0, max=1.0, update=_upd,
                           description='Bends the strands down toward their tips (1: the tips hang straight down); '
                                       'they stay out of the body')
    clump_size: IntProperty(name='Clump Size', default=3, min=1, max=500, update=_upd,
                            description='About how many strands in a tuft (Clump gathers their tips)')
    gather: FloatProperty(name='Tip Gather', default=0.0, min=0.0, max=1.0, update=_upd,
                          description='The tips of a piece of the shape gathered to its end (1: they meet)')
    bend: FloatProperty(name='Bend', default=0.0, min=0.0, max=math.pi, subtype='ANGLE', update=_upd,
                        description='How far the strands turn toward the bend side (set by the buttons; 0 = none)')
    bend_at: FloatProperty(name='Bend At', default=0.3, min=0.0, max=0.95, update=_upd,
                           description='Where along the strands they bend (0 = at the root, 0.9 = near the tip)')
    bend_soft: FloatProperty(name='Bend Soft', default=0.35, min=0.0, max=1.0, update=_upd,
                             description='0 = a sharp kink, 1 = a long smooth curve')
    bend_dir: FloatVectorProperty(name='Bend Direction', size=3, default=(1.0, 0.0, 0.0), options={'HIDDEN'},
                                  update=_upd)
    bend_side: bpy.props.StringProperty(default='', options={'HIDDEN'})
    use_polypaint: BoolProperty(name='Use Polypaint', default=True, update=_upd,
                                description='The colour painted on the hair shape (along each strand), else the '
                                            'body\'s at the root; off: Root Color')
    # the comb (the tool's, not each hair's)
    comb_size: IntProperty(name='Comb Size', default=70, min=5, max=600, subtype='PIXEL',
                           description='The comb\'s circle on the screen')
    comb_strength: FloatProperty(name='Comb Strength', default=0.5, min=0.01, max=1.0, subtype='FACTOR')
    auto_thick: BoolProperty(name='Thickness from the Shape', default=True,
                             description='The next hair: its thickness from the shape\'s size')


def _shape_pick(context):
    obs = [o for o in context.selected_objects if o.type == 'MESH' and not is_hair(o)]
    act = context.active_object
    if act is not None and act in obs and len(obs) > 1:
        # (the shape(s) selected, the body active: Shift + click the body last)
        return [o for o in obs if o is not act], act
    return obs, None


_PICK = {'op': None}


def _draw_starts():
    op = _PICK['op']
    if op is None:
        return
    try:
        from bpy_extras import view3d_utils
        from . import ui_gpu as ug
        region, rv3d = bpy.context.region, bpy.context.region_data
        if region is None or rv3d is None or region != op.region:
            return
        for q in op.starts:
            c = view3d_utils.location_3d_to_region_2d(region, rv3d, Vector(q[1]))
            if c is not None:
                ug.polyline(ug.circle_pts(c.x, c.y, 9.0, n=24), (1.0, 0.85, 0.2, 1.0), 2.5, closed=True)
                ug.polyline(ug.circle_pts(c.x, c.y, 3.0, n=12), (1.0, 0.85, 0.2, 1.0), 3.0, closed=True)
    except (ReferenceError, AttributeError, RuntimeError):
        pass


class PickStarts:
    """0.24.179 (user: "결 시작 부분은 내가 찍어 주는 게 낫지 않나?"): click on the shape where the hair starts
    (Shift + click: more starts), Enter: go (no click: found by itself), Esc: cancel."""

    def begin(self, context, shapes):
        from . import light_copies as lc
        self.region = context.region
        self.shapes = [o for o in shapes if o is not None and o.type == 'MESH']
        self.trees = {}
        for o in self.shapes:
            V, T, _E = _world_mesh(context, o)
            if len(T):
                self.trees[o.name] = BVHTree.FromPolygons([tuple(p) for p in V], [tuple(t) for t in T])
        del lc
        self.starts = []                             # [(shape name, world point)]
        for o in self.shapes:                        # (seen while picking, even when hidden by an earlier hair)
            try:
                o.hide_set(False)
            except RuntimeError:
                pass
        _PICK['op'] = self
        self._h = bpy.types.SpaceView3D.draw_handler_add(_draw_starts, (), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        self._status(context)
        return {'RUNNING_MODAL'}

    def _status(self, context):
        try:
            context.area.header_text_set(f'Hair: click where it starts on the shape (Shift + click: more) - '
                                         f'{len(self.starts)} start{"s" if len(self.starts) != 1 else ""} | Enter: '
                                         f'make it{" (no click: found by itself)" if not self.starts else ""} | Esc: cancel')
        except (AttributeError, ReferenceError):
            pass

    def _end(self, context):
        _PICK['op'] = None
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self._h, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        try:
            context.area.header_text_set(None)
            context.area.tag_redraw()
        except (AttributeError, ReferenceError):
            pass

    def modal(self, context, event):
        from bpy_extras import view3d_utils
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM',
                          'NDOF_MOTION', 'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            return {'PASS_THROUGH'}
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            xy = (event.mouse_region_x, event.mouse_region_y)
            o = view3d_utils.region_2d_to_origin_3d(context.region, context.region_data, xy)
            d = view3d_utils.region_2d_to_vector_3d(context.region, context.region_data, xy).normalized()
            best = None
            for name, bvh in self.trees.items():
                loc, _n, _i, dist = bvh.ray_cast(o, d)
                if loc is not None and (best is None or dist < best[2]):
                    best = (name, tuple(loc), dist)
            if best is not None:
                if not event.shift:
                    self.starts = [s_ for s_ in self.starts if s_[0] != best[0]]
                self.starts.append(best[:2])
            self._status(context)
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}
        if event.type in {'RET', 'NUMPAD_ENTER', 'SPACE'} and event.value == 'PRESS':
            self._end(context)
            return self.go(context)
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            self._end(context)
            self.cancelled(context)
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}

    def starts_for(self, shape):
        return [q for n, q in self.starts if n == shape.name] or None

    def cancelled(self, context):
        pass


class MCH_OT_hair_from_shape(PickStarts, bpy.types.Operator):
    """Strands in the hair shape you sculpted (a mesh of its own): select it (and Shift + click the body last, if it
    is not found by itself) - the hair follows it from where it sits on the body to its ends"""
    bl_idname = 'mch.hair_from_shape'
    bl_label = 'Hair in the Selected Shape'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def invoke(self, context, event):
        shapes, body = _shape_pick(context)
        if not shapes:
            self.report({'WARNING'}, 'Select the hair shape you sculpted (a mesh of its own) first')
            return {'CANCELLED'}
        self._body = body
        if context.area is None or context.area.type != 'VIEW_3D':
            # (from the Mecha window: its click comes without the view - picked in the biggest 3D View)
            from . import workspace_ui
            ov = workspace_ui._view3d_override(context)
            if ov is None:
                return self.execute(context)
            with context.temp_override(**ov):
                return self.begin(bpy.context, shapes)
        return self.begin(context, shapes)

    def go(self, context):
        return self._make(context, self.shapes, self._body, self)

    def execute(self, context):
        shapes, body = _shape_pick(context)
        if not shapes:
            self.report({'WARNING'}, 'Select the hair shape you sculpted (a mesh of its own) first')
            return {'CANCELLED'}
        return self._make(context, shapes, body, None)

    def _make(self, context, shapes, body, picker):
        msgs = []
        for shape in shapes:
            try:
                _ob, msg = make(context, shape, body, picker.starts_for(shape) if picker is not None else None)
                msgs.append(msg)
            except ShapeError as ex:
                self.report({'WARNING'}, str(ex))
                return {'CANCELLED'}
        self.report({'INFO'}, ' | '.join(msgs))
        return {'FINISHED'}


class MCH_OT_hair_shape_pick(PickStarts, bpy.types.Operator):
    """Click where the selected hair starts on its shape again (Shift + click: more starts), Enter: rebuilt from
    there (no click: found by itself)"""
    bl_idname = 'mch.hair_shape_pick'
    bl_label = 'Pick Where It Starts'
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        ob = context.active_object
        if not is_hair(ob) or ob.mch_hshape.shape is None:
            return {'CANCELLED'}
        self.hair = ob.name
        self.was_hidden = ob.mch_hshape.shape.hide_get()
        if context.area is None or context.area.type != 'VIEW_3D':
            from . import workspace_ui
            ov = workspace_ui._view3d_override(context)
            if ov is None:
                return {'CANCELLED'}
            with context.temp_override(**ov):
                return self.begin(bpy.context, [ob.mch_hshape.shape])
        return self.begin(context, [ob.mch_hshape.shape])

    def cancelled(self, context):
        ob = bpy.data.objects.get(self.hair)
        if ob is not None and ob.mch_hshape.shape is not None and self.was_hidden:
            ob.mch_hshape.shape.hide_set(True)

    def go(self, context):
        ob = bpy.data.objects.get(self.hair)
        if ob is None:
            return {'CANCELLED'}
        starts = self.starts_for(ob.mch_hshape.shape)
        if starts:
            inv = ob.matrix_world.inverted()
            ob[STARTS] = json.dumps([list(inv @ Vector(q)) for q in starts])
        elif STARTS in ob:
            del ob[STARTS]
        try:
            n = rebuild(ob, context, force_trace=True)
        except ShapeError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        if ob.mch_hshape.hide_shape and ob.mch_hshape.shape is not None:
            ob.mch_hshape.shape.hide_set(True)
            ob.mch_hshape.shape.hide_render = True
        self.report({'INFO'}, f'{ob.name}: {n:,} strands, from ' + (f'the {len(starts)} start(s) you clicked' if starts
                                                                     else 'where the shape meets the body'))
        return {'FINISHED'}


class MCH_OT_hair_shape_rebuild(bpy.types.Operator):
    """Trace the strands through the shape again (after sculpting it)"""
    bl_idname = 'mch.hair_shape_rebuild'
    bl_label = 'Rebuild from the Shape'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ob = context.active_object
        if not is_hair(ob):
            return {'CANCELLED'}
        try:
            n = rebuild(ob, context, force_trace=True)
        except ShapeError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, f'{ob.name}: {n:,} strands')
        return {'FINISHED'}


class MCH_OT_hair_shape_apply(bpy.types.Operator):
    """Keep the strands as they are (not live any more)"""
    bl_idname = 'mch.hair_shape_apply'
    bl_label = 'Apply'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ob = context.active_object
        if not is_hair(ob):
            return {'CANCELLED'}
        del ob[KEY]
        _CACHE.pop(ob.name, None)
        return {'FINISHED'}


_COMB = {'op': None}


def _draw_comb():
    op = _COMB['op']
    if op is None or op.mouse is None:
        return
    try:
        if bpy.context.region != op.region:
            return
        from . import ui_gpu as ug
        x, y = op.mouse
        r = float(bpy.context.scene.mch_hshape.comb_size)
        col = (1.0, 0.6, 0.25, 1.0) if op.alt else (1.0, 1.0, 1.0, 0.95)
        ug.polyline(ug.circle_pts(x, y, r, n=48), col, 1.6, closed=True)
        ug.polyline(ug.circle_pts(x, y, 2.5, n=10), col, 2.0, closed=True)
    except (ReferenceError, AttributeError, RuntimeError):
        pass


class MCH_OT_hair_shape_comb(bpy.types.Operator):
    """0.24.180 (user: "머리카락 빗는 것도 만들어 주고"): comb the selected hair - drag over it: the strands under the comb
    turn the way you drag (their roots stay, their length kept, out of the body); Alt + drag: back as they were;
    [ ]: comb size; Ctrl + Z: the last stroke off; Enter / Esc / right click: done.  Kept with the hair: the values,
    Amount, Rebuild comb it again the same way"""
    bl_idname = 'mch.hair_shape_comb'
    bl_label = 'Comb'
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        ob = context.active_object
        if not is_hair(ob):
            self.report({'WARNING'}, 'Select a hair made in a sculpted shape first')
            return {'CANCELLED'}
        self.hair = ob.name
        if context.area is None or context.area.type != 'VIEW_3D':
            from . import workspace_ui
            ov = workspace_ui._view3d_override(context)
            if ov is None:
                return {'CANCELLED'}
            with context.temp_override(**ov):
                return self._begin(bpy.context)
        return self._begin(context)

    def _begin(self, context):
        ob = bpy.data.objects.get(self.hair)
        try:
            rebuild(ob, context)
        except ShapeError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.region, self.rv3d, self.area = context.region, context.region_data, context.area
        self.mouse, self.stroke, self.alt, self.last, self.n = None, None, False, None, 0
        _COMB['op'] = self
        self._h = bpy.types.SpaceView3D.draw_handler_add(_draw_comb, (), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        self._status()
        return {'RUNNING_MODAL'}

    def _status(self):
        try:
            self.area.header_text_set(f'Comb: drag over the hair | Alt + drag: back as it was | [ ]: size | Ctrl + Z: '
                                      f'the last stroke off | Enter / Esc: done  ({self.n} stroke'
                                      f'{"s" if self.n != 1 else ""})')
        except (AttributeError, ReferenceError):
            pass

    def _end(self):
        _COMB['op'] = None
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self._h, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        try:
            self.area.header_text_set(None)
            self.area.tag_redraw()
        except (AttributeError, ReferenceError):
            pass

    def modal(self, context, event):
        ob = bpy.data.objects.get(self.hair)
        if ob is None or not is_hair(ob):
            self._end()
            return {'CANCELLED'}
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM',
                          'NDOF_MOTION'}:
            return {'PASS_THROUGH'}
        self.alt = event.alt
        reg = self.region
        mx, my = event.mouse_x - reg.x, event.mouse_y - reg.y
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            self.mouse = (mx, my)
            if self.stroke is not None:
                self._sample(context, ob, mx, my)
            self.area.tag_redraw()
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                self._start(ob, restore=event.alt)
                self.mouse = (mx, my)
                self._sample(context, ob, mx, my)
            elif event.value == 'RELEASE' and self.stroke is not None:
                self._commit(ob)
            return {'RUNNING_MODAL'}
        st = context.scene.mch_hshape
        if event.type in {'LEFT_BRACKET', 'RIGHT_BRACKET'} and event.value == 'PRESS':
            st.comb_size = int(round(st.comb_size * (1.15 if event.type == 'RIGHT_BRACKET' else 1 / 1.15)))
            self.area.tag_redraw()
            return {'RUNNING_MODAL'}
        if event.type == 'Z' and event.value == 'PRESS' and (event.ctrl or event.oskey):
            strokes = combs_of(ob)
            if strokes:
                strokes.pop()
                if strokes:
                    ob[COMBS] = json.dumps(strokes, separators=(',', ':'))
                elif COMBS in ob:
                    del ob[COMBS]
                rebuild(ob, context)
                self.n = max(self.n - 1, 0)
                self._status()
            return {'RUNNING_MODAL'}
        if event.type in {'RET', 'NUMPAD_ENTER', 'ESC', 'RIGHTMOUSE', 'SPACE'} and event.value == 'PRESS':
            if self.stroke is not None:
                self._commit(ob)
            self._end()
            return {'FINISHED'}
        return {'RUNNING_MODAL'}

    def _start(self, ob, restore=False):
        cache = _CACHE.get(ob.name)
        if cache is None or 'Gf' not in cache:
            return
        cache['Gc'] = cache['Gc'].copy()              # (combed in place from here: never the steps before it)
        cache['Gf'] = cache['Gf'].copy()
        self.stroke = {'m': 'R' if restore else 'C', 's': round(float(bpy.context.scene.mch_hshape.comb_strength), 4),
                       'v': None, 'p': []}
        self.last = None

    def _sample(self, context, ob, mx, my):
        from bpy_extras import view3d_utils as vu
        cache = _CACHE.get(ob.name)
        if cache is None or self.stroke is None or 'Gf' not in cache:
            return
        reg, rv3d = self.region, self.rv3d
        R = float(context.scene.mch_hshape.comb_size)
        M = np.array(ob.matrix_world)
        W = (cache['Gf'] @ M[:3, :3].T + M[:3, 3]).reshape(-1, 3)
        PM = np.array(rv3d.perspective_matrix)
        hom = W @ PM[:3, :3].T + PM[:3, 3]
        w = W @ PM[3, :3] + PM[3, 3]
        ok = w > 1e-6
        ws = np.where(ok, w, 1.0)
        sx = (hom[:, 0] / ws * 0.5 + 0.5) * reg.width
        sy = (hom[:, 1] / ws * 0.5 + 0.5) * reg.height
        under = ok & ((sx - mx) ** 2 + (sy - my) ** 2 < R * R)
        if not under.any():
            self.last = None                           # (off the hair: the next step starts again)
            return
        vdir = np.array(vu.region_2d_to_vector_3d(reg, rv3d, (mx, my)).normalized())
        org = np.array(vu.region_2d_to_origin_3d(reg, rv3d, (mx, my)))
        front = W[under][np.argmin((W[under] - org) @ vdir)]
        c = vu.region_2d_to_location_3d(reg, rv3d, (mx, my), Vector(front))
        r = (vu.region_2d_to_location_3d(reg, rv3d, (mx + R, my), c) - c).length
        c = np.array(c)
        if self.last is None:
            self.last = c
            return
        delta = c - self.last
        delta -= vdir * float(delta @ vdir)
        if np.linalg.norm(delta) < r * 0.12:
            return
        d = delta / np.linalg.norm(delta)
        self.last = c
        inv = np.linalg.inv(M)
        cl = inv[:3, :3] @ c + inv[:3, 3]
        dl = inv[:3, :3] @ d
        dl /= max(np.linalg.norm(dl), 1e-12)
        vl = inv[:3, :3] @ vdir
        vl /= max(np.linalg.norm(vl), 1e-12)
        rl = r / max(_scale(ob), 1e-9)
        st = self.stroke
        if st['v'] is None:
            st['v'] = [round(float(x), 5) for x in vl]
        st['p'].append([round(float(x), 6) for x in cl] + [round(float(x), 5) for x in dl] + [round(float(rl), 6)])
        rows = comb_sample(cache['Gc'], cache['Gs'], cl, dl, np.array(st['v']), rl, st['s'], st['m'] == 'R')
        if len(rows):
            cache['Gf'][rows] = settle(ob, cache, cache['Gc'], context, rows=rows, force=True)
            p = ob.mch_hshape
            P, R_, Cc = finish(cache['Gf'], p, cache['size'], p.seed, cache['pieces'], cache.get('C0'),
                               cache.get('body_colors'), cache.get('G0'))
            _write(ob, P, R_, Cc)

    def _commit(self, ob):
        st, self.stroke = self.stroke, None
        if st is None or not st['p']:
            return
        strokes = combs_of(ob)
        strokes.append(st)
        raw = json.dumps(strokes, separators=(',', ':'))
        ob[COMBS] = raw
        cache = _CACHE.get(ob.name)
        if cache is not None and 'k1' in cache:        # (combed as drawn: not combed again; out of the body once
            cache['k2'] = (cache['k1'], zlib.crc32(raw.encode()))      # more, all of it the way a rebuild does -
            cache.pop('k3', None)                      # so Ctrl + Z / a value later gives back just this)
            try:
                rebuild(ob)
            except ShapeError:
                pass
        self.n += 1
        self._status()


class MCH_OT_hair_shape_comb_clear(bpy.types.Operator):
    """Take all the combing off the selected hair (back as the shape has it)"""
    bl_idname = 'mch.hair_shape_comb_clear'
    bl_label = 'Clear Comb'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ob = context.active_object
        if not is_hair(ob):
            return {'CANCELLED'}
        if COMBS in ob:
            del ob[COMBS]
        try:
            rebuild(ob, context)
        except ShapeError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        return {'FINISHED'}


class MCH_OT_hair_shape_bend(bpy.types.Operator):
    """Bend the hair toward this side of the view you are looking through (the selected hair and the next)"""
    bl_idname = 'mch.hair_shape_bend'
    bl_label = 'Hair Bend Toward'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    side: bpy.props.StringProperty(default='RIGHT')

    def execute(self, context):
        from . import creature_hair as ch
        d = None if self.side == 'OFF' else ch.view_direction(context, self.side)
        if self.side != 'OFF' and d is None:
            self.report({'WARNING'}, 'Bend: no 3D view to take the direction from')
            return {'CANCELLED'}
        ob = context.active_object
        for pg in [context.scene.mch_hshape] + ([ob.mch_hshape] if is_hair(ob) else []):
            _BUSY[0] = True
            try:
                if self.side == 'OFF':
                    pg.bend, pg.bend_side = 0.0, ''
                else:
                    pg.bend_dir, pg.bend_side = tuple(d), self.side
                    if pg.bend < 1e-6:
                        pg.bend = math.radians(60.0)
            finally:
                _BUSY[0] = False
        if is_hair(ob):
            rebuild(ob, context)
        return {'FINISHED'}


class MCH_OT_hair_shape_colour(bpy.types.Operator):
    """The hair's colour from a preset (root and tip; the painted colour off)"""
    bl_idname = 'mch.hair_shape_colour'
    bl_label = 'Hair Colour'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    preset: bpy.props.StringProperty(default='BROWN')

    def execute(self, context):
        from . import creature_hair as ch
        hit = next((c for c in ch.COLOUR_PRESETS if c[0] == self.preset), None)
        if hit is None:
            return {'CANCELLED'}
        ob = context.active_object
        for pg in [context.scene.mch_hshape] + ([ob.mch_hshape] if is_hair(ob) else []):
            _BUSY[0] = True
            try:
                pg.root_color, pg.tip_color, pg.use_polypaint = hit[2], hit[3], False
            finally:
                _BUSY[0] = False
        if is_hair(ob):
            rebuild(ob, context)
        return {'FINISHED'}


def draw(layout, context, ob=None):
    """In the Fur window: the selected shape-hair's values (live), else the next one's and the button."""
    ob = ob if ob is not None else context.active_object
    live = is_hair(ob)
    p = ob.mch_hshape if live else context.scene.mch_hshape
    box = layout.box()
    box.label(text='Hair in a Sculpted Shape')
    col = box.column(align=True)
    if live:
        c = _CACHE.get(ob.name)
        col.label(text=f'{ob.name}: {len(ob.data.curves):,} strands (live)')
        if p.shape is not None:
            col.label(text=f'Shape: {p.shape.name}' + (f',  on {p.body.name}' if p.body is not None else ''))
        del c
    else:
        col.label(text='Select your hair shape (its own mesh), then')
        col.label(text='the button: click where it starts, Enter')
        box.operator('mch.hair_from_shape', text='Hair in the Selected Shape')
        return                                         # (its values once it is made: pick the hair)
    # 0.24.180 Amount first (live), the comb, then the Fur tool's groups
    row = box.row(align=True)
    row.scale_y = 1.3
    row.prop(p, 'count')
    comb = box.box()
    r = comb.row(align=True)
    r.scale_y = 1.4
    r.operator('mch.hair_shape_comb', text='Comb', icon='BRUSH_DATA')
    st = context.scene.mch_hshape
    r = comb.row(align=True)
    r.prop(st, 'comb_size', text='Size')
    r.prop(st, 'comb_strength', text='Strength')
    n = len(combs_of(ob))
    if n:
        comb.operator('mch.hair_shape_comb_clear', text=f'Clear Comb ({n} stroke{"s" if n != 1 else ""})')
    comb.label(text='Drag: comb | Alt + drag: back | [ ]: size')
    for group, props in (('Strands', ('length', 'length_random', 'segments', 'display', 'fill', 'seed')),
                         ('Shape', ('volume', 'spread', 'gravity', 'curl', 'curl_turns', 'frizz', 'clump',
                                    'clump_size', 'gather')),
                         ('Bend', ()),
                         ('Thickness', ('root_thick', 'tip_thin'))):
        col = box.column(align=True)
        col.label(text=group)
        if group == 'Bend':                            # (toward a side of the view you look through)
            from . import creature_hair as ch
            for keys in (ch.BEND_SIDES[:4], ch.BEND_SIDES[4:] + (('OFF', 'No Bend'),)):
                rr = col.row(align=True)
                for key, label in keys:
                    on = (p.bend > 0 and p.bend_side == key) if key != 'OFF' else p.bend <= 0
                    rr.operator('mch.hair_shape_bend', text=label, depress=on).side = key
            col.prop(p, 'bend')
            if p.bend > 0:
                col.prop(p, 'bend_at')
                col.prop(p, 'bend_soft')
        for k in props:
            col.prop(p, k)
    col = box.column(align=True)
    col.label(text='Color')
    col.prop(p, 'use_polypaint')
    c = _CACHE.get(ob.name) or {}
    painted = c.get('colors') is not None
    if p.use_polypaint:
        col.label(text='Painted on the shape' if painted else ('From the body\'s paint' if c.get('body_colors')
                                                                is not None else 'No paint found: Root Color'))
    if not p.use_polypaint or not (painted or c.get('body_colors') is not None):
        col.prop(p, 'root_color')
    col.prop(p, 'tip_color')
    col.prop(p, 'tip_blend')
    from . import creature_hair as ch
    g = col.grid_flow(columns=4, align=True)
    for key, label, _r, _t in ch.COLOUR_PRESETS:
        g.operator('mch.hair_shape_colour', text=label).preset = key
    box.prop(p, 'hide_shape')
    box.operator('mch.hair_shape_pick', text='Pick Where It Starts')
    row = box.row(align=True)
    row.operator('mch.hair_shape_rebuild', text='Rebuild')
    row.operator('mch.hair_shape_apply', text='Apply')


CLASSES = (MCH_PG_HairShape, MCH_OT_hair_from_shape, MCH_OT_hair_shape_pick, MCH_OT_hair_shape_rebuild,
           MCH_OT_hair_shape_apply, MCH_OT_hair_shape_comb, MCH_OT_hair_shape_comb_clear, MCH_OT_hair_shape_bend,
           MCH_OT_hair_shape_colour)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Object.mch_hshape = PointerProperty(type=MCH_PG_HairShape)
    bpy.types.Scene.mch_hshape = PointerProperty(type=MCH_PG_HairShape)


def unregister():
    for owner in (bpy.types.Scene, bpy.types.Object):
        if hasattr(owner, 'mch_hshape'):
            delattr(owner, 'mch_hshape')
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
    _CACHE.clear()
    _ANALYSED.clear()
    _BODY.clear()



