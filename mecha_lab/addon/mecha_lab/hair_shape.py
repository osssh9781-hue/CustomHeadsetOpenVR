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
import random

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

def _world_mesh(context, ob):
    """(V world (n, 3), triangles (m, 3), edges (k, 2)) of ``ob`` as shown (its own geometry, not a light copy)."""
    from . import light_copies as lc
    dg = context.evaluated_depsgraph_get()
    ev = lc.full(ob, dg)
    me = ev.to_mesh()
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
    finally:
        ev.to_mesh_clear()
    return V, T.reshape(-1, 3), E.reshape(-1, 2)


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


def analyse(context, shape, body=None):
    """The shape's flow: clusters (centroids), the distance along the shape from the roots, the way on, thickness;
    its surface (BVH); the root triangles."""
    V, T, E = _world_mesh(context, shape)
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
    if body is not None:
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
            'way': way, 'thick': thick, 'h': h, 'size': size, 'body': body, 'roots': int(roots.sum()), 'pieces': k}


# -----------------------------------------------------------------------------
# strands
# -----------------------------------------------------------------------------

def _root_points(a, n, rng):
    V, RT = a['V'], a['root_tris']
    if not len(RT):
        raise ShapeError('No root area found on the shape')
    p0, p1, p2 = V[RT[:, 0]], V[RT[:, 1]], V[RT[:, 2]]
    area = np.linalg.norm(np.cross(p1 - p0, p2 - p0), axis=1) / 2
    prob = area / max(area.sum(), 1e-18)
    pick = rng.choice(len(RT), size=n, p=prob)
    u, v = rng.random(n), rng.random(n)
    flip = u + v > 1
    u[flip], v[flip] = 1 - u[flip], 1 - v[flip]
    return p0[pick] + (p1[pick] - p0[pick]) * u[:, None] + (p2[pick] - p0[pick]) * v[:, None]


def trace(a, n, fill, seed):
    """``n`` strands (world points) through the shape, each at its own depth (0 .. ``fill`` of the way to the
    shape's middle): it steps along the way on and is put back in only where it would leave the shape."""
    rng = np.random.default_rng(seed)
    roots = _root_points(a, n, rng)
    bvh, kd, way, D, dmax, thick, h = a['bvh'], a['kd'], a['way'], a['D'], a['dmax'], a['thick'], a['h']
    step = h * 0.9
    out = []
    for r in roots:
        loc, nrm, _i, _d = bvh.find_nearest(Vector(r))
        if loc is None:
            continue
        _co, c, _dd = kd.find(loc)
        frac = max(0.06, fill * float(rng.random()) ** 0.7)
        depth = max(frac * thick[c] * 0.5, h * 0.15)
        keep = max(min(depth, thick[c] * 0.5), h * 0.15)
        p = np.array(loc - nrm * depth)
        pts = [p.copy()]
        prev = None
        best_d, stall = -1.0, 0
        limit = int(dmax[c] / step * 2.5) + 20
        for _s in range(limit):
            _co, c, _dd = kd.find(Vector(p))
            d = way[c]
            if prev is not None:
                d = prev * 0.5 + d * 0.5
                d = d / max(np.linalg.norm(d), 1e-12)
            q = p + d * step
            sl, sn, _i, _dist = bvh.find_nearest(Vector(q))
            if sl is not None:
                sl, sn = np.array(sl), np.array(sn)
                if float(np.dot(q - sl, sn)) > -h * 0.1:              # (leaving the shape: back in, as deep as it was)
                    q = sl - sn * min(keep, thick[c] * 0.45)
            moved = q - p
            if np.linalg.norm(moved) < step * 0.05:
                break
            prev = moved / np.linalg.norm(moved)
            p = q
            pts.append(p.copy())
            _co, c2, _dd = kd.find(Vector(p))
            if D[c2] > best_d + h * 0.05:
                best_d, stall = D[c2], 0
            else:
                stall += 1
            if D[c2] >= dmax[c2] * 0.985 or stall > 10:
                break
        if len(pts) >= 3:
            out.append(np.array(pts))
    if not out:
        raise ShapeError('No strand could run through the shape')
    return out


def resample(P, n):
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    if s[-1] <= 1e-12:
        return np.repeat(P[:1], n, axis=0)
    t = np.linspace(0.0, s[-1], n)
    return np.stack([np.interp(t, s, P[:, k]) for k in range(3)], axis=1)


def finish(traced, p, size, seed):
    """The strands as drawn (local): (points (N, seg, 3), radius (N, seg), colour (N, seg, 4)) from the traced ones."""
    rng = np.random.default_rng(seed + 7)
    seg = int(p.segments)
    base = [resample(s, seg) for s in traced]
    if not base:
        return np.zeros((0, seg, 3)), np.zeros((0, seg)), np.zeros((0, seg, 4))
    B = np.array(base)
    nT = len(B)
    N = max(int(p.count), 1)
    t = np.linspace(0.0, 1.0, seg)
    out = []
    src = [i % nT for i in range(N)]
    spread = size / CELLS * 1.6
    for k, i in enumerate(src):
        S = B[i].copy()
        if k >= nT:                                   # (made beside a traced one, gathering to it toward the tip)
            tan = S[min(1, seg - 1)] - S[0]
            tan = tan / max(np.linalg.norm(tan), 1e-12)
            o = rng.normal(size=3)
            o -= tan * float(np.dot(o, tan))
            o = o / max(np.linalg.norm(o), 1e-12) * spread * float(rng.random()) ** 0.5
            S = S + o[None, :] * (1.0 - p.clump * t[:, None] ** 0.8)
        if p.length_random > 0:
            cut = 1.0 - p.length_random * float(rng.random())
            S = resample(S[: max(2, int(round(cut * (seg - 1))) + 1)], seg)
        if p.frizz > 0:
            w = rng.normal(size=(4, 3)) * spread * p.frizz
            ph = rng.random(4) * 2 * math.pi
            wob = sum(w[j][None, :] * np.sin(t * (j + 2) * math.pi + ph[j])[:, None] for j in range(4))
            S = S + wob * t[:, None]
        if p.curl > 0:
            tan = S[-1] - S[0]
            tan = tan / max(np.linalg.norm(tan), 1e-12)
            u = np.cross(tan, (0.0, 0.0, 1.0) if abs(tan[2]) < 0.9 else (1.0, 0.0, 0.0))
            u /= max(np.linalg.norm(u), 1e-12)
            v = np.cross(tan, u)
            ang = t * p.curl_turns * 2 * math.pi + float(rng.random()) * 2 * math.pi
            amp = p.curl * spread * np.minimum(t * 4.0, 1.0)
            S = S + (np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v) * amp[:, None]
        out.append(S)
    P = np.array(out)
    R = np.tile(p.root_thick + (p.root_thick * p.tip_thin - p.root_thick) * t, (len(P), 1))
    root, tip = np.array(tuple(p.root_color) + (1.0,)), np.array(tuple(p.tip_color) + (1.0,))
    mix = np.clip((t - (1.0 - p.tip_blend)) / max(p.tip_blend, 1e-6), 0.0, 1.0) if p.tip_blend > 0 else np.zeros(seg)
    Cc = np.tile(root[None, :] * (1 - mix[:, None]) + tip[None, :] * mix[:, None], (len(P), 1, 1))
    return P, R, Cc


# -----------------------------------------------------------------------------
# the hair object
# -----------------------------------------------------------------------------

def is_hair(ob):
    return ob is not None and bool(ob.get(KEY))


def _trace_key(p):
    return (int(min(p.count, TRACE_MAX)), round(p.fill, 4), int(p.seed))


def _collection(context):
    coll = bpy.data.collections.get(COLLECTION)
    if coll is None:
        coll = bpy.data.collections.new(COLLECTION)
    if coll.name not in context.scene.collection.children:
        context.scene.collection.children.link(coll)
    return coll


def _write(ob, P, R, Cc):
    """New curves data for ``ob`` from points (N, seg, 3) local, radius, colour."""
    from . import creature_fur as cf
    old = ob.data
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


def rebuild(ob, context=None, force_trace=False):
    """``ob``'s strands from its settings: traced again only when Strands (up to the traced share), Fill or Seed
    changed (or never in this session)."""
    context = context or bpy.context
    p = ob.mch_hshape
    shape = p.shape
    cache = _CACHE.get(ob.name)
    key = _trace_key(p)
    if force_trace or cache is None or cache['key'] != key:
        if shape is None:
            raise ShapeError('Its shape is gone - pick the shape again')
        a = _analysed(context, shape, p.body, fresh=force_trace)
        traced_w = trace(a, key[0], p.fill, p.seed)
        inv = np.array(ob.matrix_world.inverted())
        traced = [s @ inv[:3, :3].T + inv[:3, 3] for s in traced_w]
        cache = {'key': key, 'strands': traced, 'size': a['size'] / max(_scale(ob), 1e-9), 'roots': a['roots'],
                 'pieces': a['pieces']}
        _CACHE[ob.name] = cache
    P, R, Cc = finish(cache['strands'], p, cache['size'], p.seed)
    _write(ob, P, R, Cc)
    return len(P)


def _scale(ob):
    s = ob.matrix_world.to_scale()
    return (abs(s.x) + abs(s.y) + abs(s.z)) / 3.0


_ANALYSED = {}                         # shape name -> (its mesh and place, the analysis): Fill / Seed trace again only


def _analysed(context, shape, body, fresh=False):
    me = shape.data
    key = (me.as_pointer(), len(me.vertices), len(me.polygons), tuple(tuple(r) for r in shape.matrix_world),
           body.name if body is not None else None)
    hit = _ANALYSED.get(shape.name)
    if not fresh and hit is not None and hit[0] == key:
        return hit[1]
    a = analyse(context, shape, body)
    _ANALYSED.clear()                                 # (one kept: they hold the shape's trees)
    _ANALYSED[shape.name] = (key, a)
    return a


def make(context, shape, body=None):
    """A hair object filling ``shape`` (the Fur tool's settings for the next hair).  Returns (object, message)."""
    st = context.scene.mch_hshape
    a = _analysed(context, shape, body, fresh=True)
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
    _ANALYSED[shape.name] = ((shape.data.as_pointer(), len(shape.data.vertices), len(shape.data.polygons),
                              tuple(tuple(r) for r in shape.matrix_world), a['body'].name if a['body'] else None), a)
    traced = trace(a, min(int(p.count), TRACE_MAX), p.fill, p.seed)
    inv = np.array(ob.matrix_world.inverted())
    _CACHE[ob.name] = {'key': _trace_key(p), 'strands': [s @ inv[:3, :3].T + inv[:3, 3] for s in traced],
                       'size': a['size'], 'roots': a['roots'], 'pieces': a['pieces']}
    n = rebuild(ob, context)
    if p.hide_shape:
        shape.hide_set(True)
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    on = f' on "{a["body"].name}" (rooted where it meets it)' if a['body'] is not None else ' (no body under it: rooted at its top)'
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
        except RuntimeError:
            pass


LIVE = ('count', 'fill', 'seed', 'segments', 'clump', 'frizz', 'curl', 'curl_turns', 'length_random', 'root_thick',
        'tip_thin', 'root_color', 'tip_color', 'tip_blend', 'hide_shape')


class MCH_PG_HairShape(bpy.types.PropertyGroup):
    shape: PointerProperty(type=bpy.types.Object, name='Shape')
    body: PointerProperty(type=bpy.types.Object, name='Body')
    count: IntProperty(name='Strands', default=4000, min=10, soft_max=40000, max=200000, update=_upd,
                       description=f'How many strands (up to {TRACE_MAX} traced through the shape, the rest beside them)')
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
    root_thick: FloatProperty(name='Thickness', default=0.0, min=0.0, soft_max=0.02, precision=4, unit='LENGTH',
                              update=_upd, description='Root radius (0: from the shape\'s size)')
    tip_thin: FloatProperty(name='Tip', default=0.2, min=0.0, max=1.0, update=_upd,
                            description='The tip\'s thickness, a share of the root\'s')
    root_color: FloatVectorProperty(name='Root Color', subtype='COLOR', size=3, min=0.0, max=1.0,
                                    default=(0.09, 0.06, 0.04), update=_upd)
    tip_color: FloatVectorProperty(name='Tip Color', subtype='COLOR', size=3, min=0.0, max=1.0,
                                   default=(0.32, 0.22, 0.14), update=_upd)
    tip_blend: FloatProperty(name='Tip Blend', default=0.5, min=0.0, max=1.0, update=_upd)
    hide_shape: BoolProperty(name='Hide the Shape', default=True, update=_upd_hide)
    auto_thick: BoolProperty(name='Thickness from the Shape', default=True,
                             description='The next hair: its thickness from the shape\'s size')


def _shape_pick(context):
    obs = [o for o in context.selected_objects if o.type == 'MESH' and not is_hair(o)]
    act = context.active_object
    if act is not None and act in obs and len(obs) > 1:
        # (the shape(s) selected, the body active: Shift + click the body last)
        return [o for o in obs if o is not act], act
    return obs, None


class MCH_OT_hair_from_shape(bpy.types.Operator):
    """Strands in the hair shape you sculpted (a mesh of its own): select it (and Shift + click the body last, if it
    is not found by itself) - the hair follows it from where it sits on the body to its ends"""
    bl_idname = 'mch.hair_from_shape'
    bl_label = 'Hair in the Selected Shape'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        shapes, body = _shape_pick(context)
        if not shapes:
            self.report({'WARNING'}, 'Select the hair shape you sculpted (a mesh of its own) first')
            return {'CANCELLED'}
        msgs = []
        for shape in shapes:
            try:
                _ob, msg = make(context, shape, body)
                msgs.append(msg)
            except ShapeError as ex:
                self.report({'WARNING'}, str(ex))
                return {'CANCELLED'}
        self.report({'INFO'}, ' | '.join(msgs))
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
        col.label(text='Select your hair shape (its own mesh),')
        col.label(text='then: Hair in the Selected Shape')
        box.operator('mch.hair_from_shape', text='Hair in the Selected Shape')
        return                                         # (its values once it is made: pick the hair)
    for group, props in (('Strands', ('count', 'fill', 'segments', 'seed')),
                         ('Look', ('clump', 'frizz', 'curl', 'curl_turns', 'length_random')),
                         ('Thickness', ('root_thick', 'tip_thin')),
                         ('Color', ('root_color', 'tip_color', 'tip_blend'))):
        col = box.column(align=True)
        col.label(text=group)
        for k in props:
            col.prop(p, k)
    box.prop(p, 'hide_shape')
    if live:
        row = box.row(align=True)
        row.operator('mch.hair_shape_rebuild', text='Rebuild')
        row.operator('mch.hair_shape_apply', text='Apply')


CLASSES = (MCH_PG_HairShape, MCH_OT_hair_from_shape, MCH_OT_hair_shape_rebuild, MCH_OT_hair_shape_apply)


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


_unused = (json, random)
