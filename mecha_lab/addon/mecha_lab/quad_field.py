"""0.24.71 Quad Remesh (ZBrush shelf): Mecha Lab's own field-aligned quad remesher, in the C engine (mquad).

The part is first sampled with Fast Decimate in its even-spacing mode at a few resolutions; a direction field and a
position field (Instant Meshes, Jakob et al. 2015) are solved on them coarse to fine with the hard edges as
constraints, and the quads are read off the fine one.  Mostly Quads keeps the few triangles where rows of quads
end; All Quads makes the quads at half the count and splits every face once (quad -> 4, triangle -> 3).
Polygroups, materials and point attributes (mask, colours) come along; UVs do not (new topology).
0.24.75 a low-poly input (a Cut / Base Mesh part, a decimated one) is first laid out as even triangles - its points
and edges kept, every face filled on its own plane - and its edges are the quads' fixed lines; while the result has
holes (a groove narrower than a quad) it goes finer (2x, 4x), what is still open is closed.
"""
from __future__ import annotations

import ctypes
import math
import time

import numpy as np

import bpy

from . import fast_decimate as fd

VERSION = 2                     # mquad API this module talks to (2: guide lines, hard edges out)
MAXLEV = 8
LENGTH_WEIGHT = 0.1             # Fast Decimate even spacing for the levels
LEVELS = (16.0, 4.0, 1.0, 0.25)  # level triangles per quad, fine to coarse
ITERS_ORIENT = (20, 30, 60)     # Gauss-Seidel sweeps per level (fine first); the coarsest gets COARSE_ITERS
ITERS_POS = (30, 40, 80)
COARSE_ITERS = 200
MIN_CHAIN = 1.5                 # hard-edge chains shorter than this many quads are ignored
COARSE_PLAIN = False             # plain decimation for an oversized coarse level (quality fell: off)
COARSE_SCALE = True             # fewer sweeps on an oversized coarse level
ITERS_MIN = 0.1
COARSE_SLACK = 1.5              # a coarse level more than this x its wanted count: plain decimation instead
GUIDE_RATIO = 20.0              # an input with at most this many triangles per wanted face is followed edge by edge


class _Opts(ctypes.Structure):
    _fields_ = [('scale', ctypes.c_float), ('crease_deg', ctypes.c_float), ('min_chain', ctypes.c_float),
                ('all_quads', ctypes.c_int), ('threads', ctypes.c_int), ('seed', ctypes.c_int),
                ('iters_orient', ctypes.c_int * MAXLEV), ('iters_pos', ctypes.c_int * MAXLEV),
                ('crease_tol', ctypes.c_float)]


class _Out(ctypes.Structure):
    _fields_ = [('nv', ctypes.c_int), ('nf', ctypes.c_int), ('V', ctypes.POINTER(ctypes.c_float)),
                ('F', ctypes.POINTER(ctypes.c_int)), ('fsrc', ctypes.POINTER(ctypes.c_int)),
                ('vsrc', ctypes.POINTER(ctypes.c_int)), ('stats', ctypes.c_int * 8), ('nhard', ctypes.c_int),
                ('hard', ctypes.POINTER(ctypes.c_int))]


_IP = ctypes.POINTER(ctypes.c_int)
_FP = ctypes.POINTER(ctypes.c_float)


def lib():
    """The engine with the quad remesher, or None."""
    L = fd.lib()
    if L is None:
        return None
    try:
        L.mquad_version.restype = ctypes.c_int
        L.mquad_version.argtypes = []
        if L.mquad_version() != VERSION:                # (the structures change between versions)
            return None
        L.mquad_run.restype = ctypes.c_int
        L.mquad_run.argtypes = [ctypes.c_int, _IP, _IP, _FP, _IP, _IP, _FP, ctypes.c_int, ctypes.POINTER(_Opts),
                                ctypes.POINTER(_Out)]
        L.mquad_free.restype = None
        L.mquad_free.argtypes = [ctypes.POINTER(_Out)]
    except AttributeError:
        return None
    return L


def available():
    return lib() is not None


def subdivide(V, T, tsrc, vsrc):
    """Every triangle into 4 (edge midpoints).  tsrc / vsrc: the original triangle / point of each one."""
    e = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]]).astype(np.int64)
    e.sort(1)
    key = e[:, 0] * len(V) + e[:, 1]
    uk, inv = np.unique(key, return_inverse=True)
    a, b = uk // len(V), uk % len(V)
    mid = len(V) + inv.reshape(3, -1).T                     # midpoint of sides 01, 12, 20 of each triangle
    V2 = np.concatenate([V, (V[a] + V[b]) * 0.5]).astype(np.float32)
    v0, v1, v2 = T[:, 0], T[:, 1], T[:, 2]
    m01, m12, m20 = mid[:, 0], mid[:, 1], mid[:, 2]
    T2 = np.concatenate([np.stack([v0, m01, m20], 1), np.stack([m01, v1, m12], 1), np.stack([m20, m12, v2], 1),
                         np.stack([m01, m12, m20], 1)]).astype(np.int32)
    return V2, T2, np.tile(tsrc, 4), np.concatenate([vsrc, vsrc[a]])


def hard_segments(V, T, crease_deg):
    """The input's hard edges as line segments (n, 2, 3): sides where its faces meet at more than ``crease_deg``,
    and open borders."""
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]]).astype(np.float64)
    ln = np.linalg.norm(fn, axis=1)
    fn /= np.maximum(ln, 1e-30)[:, None]
    e = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]]).astype(np.int64)
    f = np.tile(np.arange(len(T)), 3)
    e.sort(1)
    key = e[:, 0] * len(V) + e[:, 1]
    o = np.argsort(key, kind='stable')
    key, e, f = key[o], e[o], f[o]
    first = np.r_[True, key[1:] != key[:-1]]
    starts = np.nonzero(first)[0]
    counts = np.diff(np.r_[starts, len(key)])
    hard = counts != 2
    two = np.nonzero(counts == 2)[0]
    fa, fb = f[starts[two]], f[starts[two] + 1]
    ok = (ln[fa] > 1e-30) & (ln[fb] > 1e-30)                # (a zero-area triangle has no direction)
    hard[two] = ok & ((fn[fa] * fn[fb]).sum(1) < math.cos(math.radians(crease_deg)))
    ee = e[starts[hard]]
    return np.stack([V[ee[:, 0]], V[ee[:, 1]]], 1).astype(np.float32)


def _fill_face(P, h):
    """Points inside polygon P (k, 2; counter-clockwise) on a staggered lattice h apart, none nearer than h / 2 to
    its border."""
    lo, hi = P.min(0), P.max(0)
    ys = np.arange(lo[1] + 0.5 * h, hi[1], h * 0.866)
    if not len(ys):
        return np.zeros((0, 2))
    rows = []
    for r, y in enumerate(ys):
        xs = np.arange(lo[0] + (0.5 + 0.5 * (r % 2)) * h, hi[0], h)
        if len(xs):
            rows.append(np.stack([xs, np.full(len(xs), y)], 1))
    if not rows:
        return np.zeros((0, 2))
    Q = np.concatenate(rows)
    A, B = P, np.roll(P, -1, 0)
    # inside: even-odd crossings of a ray to +x
    cross = ((A[None, :, 1] > Q[:, None, 1]) != (B[None, :, 1] > Q[:, None, 1]))
    with np.errstate(divide='ignore', invalid='ignore'):
        xi = A[None, :, 0] + (Q[:, None, 1] - A[None, :, 1]) * (B[None, :, 0] - A[None, :, 0]) / (B[None, :, 1] - A[None, :, 1])
    inside = (cross & (Q[:, None, 0] < xi)).sum(1) % 2 == 1
    Q = Q[inside]
    if not len(Q):
        return Q
    E = B - A
    L2 = np.maximum((E * E).sum(1), 1e-30)
    t = np.clip(((Q[:, None, :] - A[None]) * E[None]).sum(2) / L2[None], 0.0, 1.0)
    d = np.linalg.norm(Q[:, None, :] - (A[None] + t[..., None] * E[None]), axis=2).min(1)
    return Q[d > 0.5 * h]


def even_triangles(me, h):
    """0.24.75 an exact Cut / Base Mesh part as even triangles about ``h`` big: its points and edges kept exactly
    (long edges get points every ~h), every face filled on its own plane with points ~h apart.  (The polygons' own
    fan triangles are long slivers: the remesher sampled them badly and lost the part's edges.)
    Returns (V (n, 3), T (m, 3), the polygon under each triangle, the part's point nearest each point)."""
    import bmesh
    from mathutils import Vector
    from mathutils.geometry import delaunay_2d_cdt
    from mathutils.kdtree import KDTree
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        bm.normal_update()
        bm.verts.ensure_lookup_table()
        V = [v.co.copy() for v in bm.verts]
        # long edges: points every ~h, shared by the two faces on them (each face's border walks them in its order)
        along = {}
        for e in bm.edges:
            ln = e.calc_length()
            k = int(math.ceil(ln / h)) - 1 if ln > 1.5 * h else 0
            if k > 0:
                a0, a1 = e.verts[0].co, e.verts[1].co
                along[e.index] = list(range(len(V), len(V) + k))
                V += [a0.lerp(a1, (j + 1) / (k + 1)) for j in range(k)]
        T, TP = [], []
        me.calc_loop_triangles()
        own = {}
        for lt in me.loop_triangles:
            own.setdefault(lt.polygon_index, []).append(list(lt.vertices))
        small = 0.6 * h * h
        for f in bm.faces:
            if f.calc_area() < small and not any(lp.edge.index in along for lp in f.loops) and f.index in own:
                T += own[f.index]                            # (already small: its own triangles, no fill needed)
                TP += [f.index] * len(own[f.index])
                continue
            ids = []
            for lp in f.loops:
                ids.append(lp.vert.index)
                pts = along.get(lp.edge.index)
                if pts:
                    ids += pts if lp.edge.verts[0] is lp.vert else pts[::-1]
            if len(ids) < 3:
                continue
            nrm = f.normal.normalized() if f.normal.length > 1e-12 else Vector((0, 0, 1))
            o = V[ids[0]].copy()
            a = Vector((1, 0, 0)) if abs(nrm.x) < 0.9 else Vector((0, 1, 0))
            u = (a - nrm * a.dot(nrm)).normalized()
            w = nrm.cross(u)
            P = np.array([((V[i] - o).dot(u), (V[i] - o).dot(w)) for i in ids])
            if 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1]) < 0:
                P, ids = P[::-1].copy(), ids[::-1]
            inner = _fill_face(P, h)
            coords = [Vector(q) for q in P] + [Vector(q) for q in inner]
            tris = []
            try:
                oV, _oE, oF, oVo, _a, _b = delaunay_2d_cdt(coords, [], [list(range(len(P)))], 1, 1e-9 * (1 + h), True)
            except (ValueError, RuntimeError):
                oF = None
            if oF:
                loc = {}
                for k, orig in enumerate(oVo):
                    s = [x for x in orig if x < len(coords)]
                    if s and s[0] < len(P):
                        loc[k] = ids[s[0]]
                    else:
                        q = Vector(oV[k])
                        V.append(o + u * q.x + w * q.y)
                        loc[k] = len(V) - 1
                tris = [[loc[k] for k in t] for t in oF if len(t) == 3]
            if not tris:                                     # (a face the CDT could not take: its own fan)
                tris = [[ids[0], ids[k], ids[k + 1]] for k in range(1, len(ids) - 1)]
            T += tris
            TP += [f.index] * len(tris)
        Va = np.array([tuple(v) for v in V], np.float32)
        kd = KDTree(len(me.vertices))
        for v in me.vertices:
            kd.insert(v.co, v.index)
        kd.balance()
        near = np.array([kd.find(tuple(p))[1] for p in Va], np.int64)
        return Va, np.array(T, np.int32), np.array(TP, np.int64), near
    finally:
        bm.free()


def open_edges(Fq):
    """Sides used by one face or by more than two (k, 2)."""
    e = []
    for f in Fq:
        vs = [v for v in f if v >= 0]
        e += [(min(vs[k], vs[(k + 1) % len(vs)]), max(vs[k], vs[(k + 1) % len(vs)])) for k in range(len(vs))]
    if not e:
        return np.zeros((0, 2), np.int64)
    u, cnt = np.unique(np.array(e, np.int64), axis=0, return_counts=True)
    return u[cnt != 2]


def border_tree(me, step):
    """Points every ``step`` along the input's own open borders (a KD tree), or None: sides of the result lying on
    them are the part's border, not holes the remesher left."""
    from mathutils.kdtree import KDTree
    me.calc_loop_triangles()
    count = {}
    for p in me.polygons:
        for ek in p.edge_keys:
            count[ek] = count.get(ek, 0) + 1
    pts = []
    for (a, b), c in count.items():
        if c == 1:
            p0, p1 = me.vertices[a].co, me.vertices[b].co
            n = max(1, int((p1 - p0).length / step))
            pts += [p0.lerp(p1, j / n) for j in range(n + 1)]
    if not pts:
        return None
    kd = KDTree(len(pts))
    for k, p in enumerate(pts):
        kd.insert(p, k)
    kd.balance()
    return kd


def holes(P, sides, border, tol):
    """The open ``sides`` that are not on the input's border (``border`` from ``border_tree``)."""
    if border is None or not len(sides):
        return sides
    mid = (P[sides[:, 0]] + P[sides[:, 1]]) * 0.5
    keep = [border.find(tuple(m))[2] > tol for m in mid]
    return sides[np.array(keep, bool)]


VOLUME_KEEP = 0.5               # 0.24.83 a closed part keeps at least this share of its volume (else finer / kept)
VOLUME_TRIES = 2
OPEN_OK = 0.03                  # ... and comes back closed, give or take this share of open sides (thin walls of a
OPEN_OK_MIN = 2                 # sculpt; at least this many) - more than that: finer / kept as it is
QUAD_MAX_FACES = 400000
_st_tries = {}
YIELD_MIN = 0.5                 # 0.24.82 under this share of the faces asked for: All Quads -> Mostly at the same
YIELD_FALLBACK = True           # count / Mostly -> 2x finer, once; the nearer result is kept (see _remesh_object)
CUT_TRIES = (1, 2)              # finer while the result has holes (a groove narrower than a quad); 0.24.81 4x no
                                # more: it tripled the time and gave 4x the faces asked for, the holes close anyway
HOLES_OK = 0.01                 # this share of the faces (at least 16 sides) left open: close them, no finer try


def is_cut_mesh(me, target):
    """0.24.75 a low-poly input - an exact part made with Cut / Base Mesh, or a decimated one: at most GUIDE_RATIO
    triangles per wanted face.  It is remeshed from even triangles with its own edges as the quads' fixed lines
    (its fan / sliver triangles sampled badly: edges lost, open seams)."""
    nt = len(me.loop_triangles)
    return 0 < nt <= GUIDE_RATIO * max(int(target), 1)


def remesh_cut(me, target, all_quads=False, crease_deg=30.0, nthreads=None):
    """Quad Remesh of a low-poly part (see ``is_cut_mesh``).  Returns (points, faces, polygon under each face,
    part's point nearest each point, stats with 'tries' = how much finer it had to go, 'open' = sides left open)."""
    area = sum(p.area for p in me.polygons)
    best = None
    for k in CUT_TRIES:
        h = math.sqrt(2.0 * area / max(1, 6 * target * k))
        V, T, tpoly, near = even_triangles(me, h)
        P, Fq, tsrc, psrc, st = remesh_arrays(V, T, target * k, all_quads=all_quads, crease_deg=crease_deg,
                                              nthreads=nthreads, guide=True)
        bad = len(holes(P, open_edges(Fq), border_tree(me, 0.25 * h), 0.5 * h))   # (an open plate's border stays)
        if best is not None and bad >= best[0]:
            break                                    # 0.24.76 finer did not help: no use going finer still
        st['tries'] = k
        st['h'] = h
        best = (bad, (P, Fq, tpoly[tsrc], near[psrc], st))
        if bad <= max(16, HOLES_OK * len(Fq)):        # 0.24.81 a few: closed below (a 2x finer try cost 2 s +)
            break
    best[1][4]['open'] = best[0]
    return best[1]


def _open_multi(me):
    """(open sides, edges with 3+ faces) of a mesh."""
    import numpy as np
    ne = len(me.edges)
    if not ne:
        return 0, 0
    le = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get('edge_index', le)
    n = np.bincount(le, minlength=ne)
    return int((n == 1).sum()), int((n > 2).sum())


def _volume(me):
    import bmesh
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        return abs(bm.calc_volume(signed=True))
    finally:
        bm.free()


def drop_twins(me):
    """0.24.77 Faces on the very same points.  A flat pocket of two such triangles (their edges used by nothing else)
    goes completely - an FBX / Blender's mesh check keeps one of them and leaves a hole; a face lying on a face of the
    surface goes alone.  Returns how many faces were removed."""
    import bmesh
    seen, twins = {}, []
    for p in me.polygons:
        key = tuple(sorted(p.vertices))
        if key in seen:
            twins.append((seen[key], p.index))
        else:
            seen[key] = p.index
    if not twins:
        return 0
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        dead = set()
        for a, b in twins:
            fa, fb = bm.faces[a], bm.faces[b]
            pair = {fa, fb}
            if all(set(e.link_faces) <= pair for e in fa.edges):
                dead |= pair
            else:
                dead.add(fb)
        bmesh.ops.delete(bm, geom=list(dead), context='FACES_ONLY')
        loose_e = [e for e in bm.edges if not e.link_faces]
        if loose_e:
            bmesh.ops.delete(bm, geom=loose_e, context='EDGES')
        loose_v = [v for v in bm.verts if not v.link_faces]
        if loose_v:
            bmesh.ops.delete(bm, geom=loose_v, context='VERTS')
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()
    return len(dead)


def close_holes(me, fpoly, border=None, tol=0.0, max_sides=64, weld=0.0):
    """Close what the remesher left open - not the input's own border (``border`` / ``tol`` as in ``holes``): a crack
    (open sides lying on each other) is zipped by welding points closer than ``weld``, each open loop gets faces
    (quads where they fit).  Returns (the polygon source of every face - new ones take a neighbour's -, hole sides
    before, after, the old point of each point now or None, {welded old point: the old point it went to})."""
    import bmesh
    bm = bmesh.new()

    def hole_sides():
        out = []
        for e in bm.edges:
            if e.is_manifold:
                continue
            if border is not None and border.find((e.verts[0].co + e.verts[1].co) * 0.5)[2] <= tol:
                continue
            out.append(e)
        return out

    try:
        bm.from_mesh(me)
        fl = bm.faces.layers.int.new('mch_quad_src')
        vl = bm.verts.layers.int.new('mch_quad_old')
        for f in bm.faces:
            f[fl] = int(fpoly[f.index]) + 1
        for v in bm.verts:
            v[vl] = v.index
        sides = hole_sides()
        before = len(sides)
        if not before:
            return fpoly, 0, 0, None, {}
        welded = {}
        if weld > 0.0:
            tm = bmesh.ops.find_doubles(bm, verts=list({v for e in sides for v in e.verts}), dist=weld)['targetmap']
            welded = {v[vl]: t[vl] for v, t in tm.items()}
            if tm:
                bmesh.ops.weld_verts(bm, targetmap=tm)
            sides = hole_sides()
        multi = list({f for e in sides if len(e.link_faces) > 2 for f in e.link_faces})
        if multi:                                            # a fin (a side with 3+ faces): its faces go, then filled
            bmesh.ops.delete(bm, geom=multi, context='FACES_ONLY')
            loose = [v for v in bm.verts if not v.link_faces]
            if loose:
                bmesh.ops.delete(bm, geom=loose, context='VERTS')
            sides = hole_sides()
        for _r in range(3):
            if not sides:
                break
            res = bmesh.ops.holes_fill(bm, edges=[e for e in sides if e.is_boundary], sides=max_sides)
            new = res.get('faces', [])
            if new:
                tri = bmesh.ops.triangulate(bm, faces=new)['faces']
                bmesh.ops.join_triangles(bm, faces=tri, cmp_seam=False, cmp_sharp=False, cmp_uvs=False,
                                         cmp_vcols=False, cmp_materials=False, angle_face_threshold=math.radians(30),
                                         angle_shape_threshold=math.radians(60))
            sides = hole_sides()
            # a flap (a face hanging into the hole by one side: two open sides, no closed loop to fill) goes
            flaps = list({f for e in sides for f in e.link_faces if sum(1 for g in f.edges if g.is_boundary) >= 2})
            if not flaps:
                break
            bmesh.ops.delete(bm, geom=flaps, context='FACES_ONLY')
            loose = [v for v in bm.verts if not v.link_faces]
            if loose:
                bmesh.ops.delete(bm, geom=loose, context='VERTS')
            sides = hole_sides()
        for _r in range(8):                                  # new faces: the source of a face next to them
            todo = [f for f in bm.faces if f[fl] <= 0]
            if not todo:
                break
            for f in todo:
                for e in f.edges:
                    g = next((g for g in e.link_faces if g is not f and g[fl] > 0), None)
                    if g is not None:
                        f[fl] = g[fl]
                        break
        bm.verts.index_update()
        bm.faces.index_update()
        new2old = np.array([v[vl] for v in bm.verts], np.int64)
        fpoly = np.array([max(f[fl], 1) - 1 for f in bm.faces], np.int64)
        after = len(hole_sides())
        bm.verts.layers.int.remove(vl)
        bm.faces.layers.int.remove(fl)
        bm.to_mesh(me)
        return fpoly, before, after, new2old, welded
    finally:
        bm.free()


def level_iters(wanted, got):
    """Gauss-Seidel sweeps (orientation, position) per level, fine first.  0.24.81 a level that could not coarsen
    to its count (the even decimation stops early on a part with many hard edges: level 3 wanted 935 faces, got
    8,906) gets the sweeps its size pays for - the 200 coarse sweeps ran on a level nearly as big as the fine one
    (Mostly Quads on a 7k-face part: 31 s, now 8 s, the same result)."""
    n = len(got)
    out = []
    for k in range(n):
        io = COARSE_ITERS if k == n - 1 else ITERS_ORIENT[min(k, len(ITERS_ORIENT) - 1)]
        ip = COARSE_ITERS if k == n - 1 else ITERS_POS[min(k, len(ITERS_POS) - 1)]
        if COARSE_SCALE and k > 0:
            f = max(ITERS_MIN, min(1.0, wanted[k] / max(1, got[k])))
            io, ip = max(ITERS_ORIENT[0], int(io * f)), max(ITERS_POS[0], int(ip * f))
        out.append((io, ip))
    return out


def remesh_arrays(V, T, target, all_quads=False, crease_deg=30.0, nthreads=None, seed=0, guide='auto'):
    """Quad remesh triangles T over points V to about ``target`` faces.

    guide: 'auto' - a coarse input (a decimated part: at most GUIDE_RATIO triangles per wanted face) is followed edge
    by edge (its hard edges become the quads' fixed lines); a dense one (DynaMesh) by the angle on the even sampling.
    True / False force it.
    Returns (points (n, 3), faces (m, 4) with -1 as the 4th index of a triangle, the input triangle under each face,
    the input point nearest each point, stats dict with 'hard': the result's hard edges as point pairs (k, 2))."""
    L = lib()
    if L is None:
        raise RuntimeError('Quad Remesh engine not available on this system')
    V = np.ascontiguousarray(V, np.float32).reshape(-1, 3)
    T = np.ascontiguousarray(T, np.int32).reshape(-1, 3)
    if not np.isfinite(V).all():
        raise RuntimeError('Quad Remesh: the mesh has invalid (NaN / infinite) point positions')
    if len(T) and (int(T.min()) < 0 or int(T.max()) >= len(V)):
        raise RuntimeError('Quad Remesh: the mesh has broken faces (point index out of range)')
    area = float(0.5 * np.linalg.norm(np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]]), axis=1).sum())
    if area <= 0.0:
        raise RuntimeError('Quad Remesh: the mesh has no area')
    n_ext = max(12, int(target / 4) if all_quads else int(target))
    h = math.sqrt(area / n_ext)
    if guide == 'auto':
        guide = len(T) <= GUIDE_RATIO * max(int(target), 1)
    segs = hard_segments(V, T, crease_deg) if guide else np.zeros((0, 2, 3), np.float32)
    counts = [int(n_ext * m) for m in LEVELS]
    counts = [c for k, c in enumerate(counts) if k == 0 or c >= 100]
    # the fine level needs small, even triangles: subdivide a coarse mesh first, then sample it evenly
    tsrc = np.arange(len(T), dtype=np.int64)
    vsrc = np.arange(len(V), dtype=np.int64)
    for _ in range(6):
        if len(T) >= 1.25 * counts[0]:
            break
        V, T, tsrc, vsrc = subdivide(V, T, tsrc, vsrc)
    levels = []
    srcs = []
    cur = (V, T)
    for k, c in enumerate(counts):
        if c >= len(cur[1]):
            break
        oV, oF, vs, fs = fd.run(cur[0], cur[1], c, even=True, uniform=LENGTH_WEIGHT, nthreads=nthreads)
        if k > 0 and COARSE_PLAIN and len(oF) > COARSE_SLACK * c:
            # 0.24.81 the even decimation stops early on a part with many hard edges (a cut part: level 3 wanted
            # 935 faces, got 8,906): the coarse levels were nearly as big as the fine one and the 200 coarse sweeps
            # ran on them (Mostly Quads on a 7k-face part: 31 s).  A coarse level only seeds the field: the plain
            # decimation reaches the count.
            oV, oF, vs, fs = fd.run(cur[0], cur[1], c, even=False, nthreads=nthreads)
        if k == 0:
            tsrc = tsrc[fs]
            vsrc = vsrc[vs]
        else:
            srcs.append(vs.astype(np.int32))
        levels.append((oV, oF))
        cur = (oV, oF)
    if not levels:
        raise RuntimeError('Quad Remesh: too few triangles')
    n = len(levels)
    o = _Opts()
    o.scale = h
    o.crease_deg = crease_deg
    o.min_chain = MIN_CHAIN * h
    o.all_quads = 1 if all_quads else 0
    o.threads = nthreads or fd.threads()
    o.seed = seed
    o.crease_tol = 0.02 * h
    for k, (io, ip) in enumerate(level_iters(counts, [len(lv[1]) for lv in levels])):
        o.iters_orient[k], o.iters_pos[k] = io, ip
    nv = (ctypes.c_int * n)(*[len(lv[0]) for lv in levels])
    nf = (ctypes.c_int * n)(*[len(lv[1]) for lv in levels])
    Vc = np.ascontiguousarray(np.concatenate([lv[0].ravel() for lv in levels]), np.float32)
    Fc = np.ascontiguousarray(np.concatenate([lv[1].ravel() for lv in levels]), np.int32)
    Sc = np.ascontiguousarray(np.concatenate(srcs) if srcs else np.zeros(1, np.int32), np.int32)
    G = np.ascontiguousarray(segs.reshape(-1), np.float32)
    out = _Out()
    rc = L.mquad_run(n, nv, nf, Vc.ctypes.data_as(_FP), Fc.ctypes.data_as(_IP), Sc.ctypes.data_as(_IP),
                     G.ctypes.data_as(_FP) if len(segs) else None, len(segs), ctypes.byref(o), ctypes.byref(out))
    if rc:
        raise RuntimeError(f'Quad Remesh failed (code {rc})')
    try:
        if out.nv == 0 or out.nf == 0:
            raise RuntimeError('Quad Remesh: no faces came out (try more polygons)')
        P = np.ctypeslib.as_array(out.V, shape=(out.nv * 3,)).reshape(-1, 3).copy()
        Fq = np.ctypeslib.as_array(out.F, shape=(out.nf * 4,)).reshape(-1, 4).copy()
        fsrc = np.ctypeslib.as_array(out.fsrc, shape=(out.nf,)).copy()
        psrc = np.ctypeslib.as_array(out.vsrc, shape=(out.nv,)).copy()
        stats = dict(zip(('collapses', 'conflicts', 'points', 'holes', 'joined', 'triangles', 'quads'),
                         list(out.stats)[:7]))
        hard = (np.ctypeslib.as_array(out.hard, shape=(out.nhard * 2,)).reshape(-1, 2).copy() if out.nhard
                else np.zeros((0, 2), np.int32))
        if len(Fq) and (Fq.max() >= len(P) or (Fq[:, :3] < 0).any()) or len(hard) and hard.max() >= len(P):
            raise RuntimeError('Quad Remesh: the engine returned broken faces')
    finally:
        L.mquad_free(ctypes.byref(out))
    stats['levels'] = [len(lv[1]) for lv in levels]
    stats['scale'] = h
    stats['hard'] = hard
    stats['guide'] = len(segs)
    return P, Fq, tsrc[fsrc], vsrc[psrc], stats


def remesh_object(ob, target, all_quads=False, crease_deg=30.0, nthreads=None):
    """Quad remesh mesh object ``ob`` (Object Mode) to about ``target`` polygons.  Returns a message."""
    me = ob.data
    if me.shape_keys is not None:
        return 'Quad Remesh: remove the shape keys first'
    if any(m.type == 'MULTIRES' for m in ob.modifiers):
        return 'Quad Remesh: delete or apply the subdivision levels first (Multires)'
    if not available():
        return 'Quad Remesh: the engine is not available on this system'
    t0 = time.perf_counter()
    polys0 = len(me.polygons)
    from . import mesh_fix
    fixed, fixst = None, None
    if mesh_fix.needs_fix(me):                         # 0.24.76 open sides / 3+-face edges: a repaired copy is
        fixed = me.copy()                              # remeshed (welded cracks, no slivers / inside walls; an
        fixst = mesh_fix.fix_mesh(fixed, fill='CRACKS')  # open plate's own border stays open)
        if mesh_fix.changed(fixst):
            me = fixed
        else:
            bpy.data.meshes.remove(fixed)
            fixed = fixst = None
    try:
        return _remesh_object(ob, me, polys0, t0, fixst, target, all_quads, crease_deg, nthreads)
    finally:
        if fixed is not None and fixed.users == 0:
            bpy.data.meshes.remove(fixed)


def _remesh_object(ob, me, polys0, t0, fixst, target, all_quads, crease_deg, nthreads):
    me.calc_loop_triangles()
    nt = len(me.loop_triangles)
    if nt < 4:
        return 'Quad Remesh: nothing to remesh'
    V = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', V)
    T = np.empty(nt * 3, np.int32)
    me.loop_triangles.foreach_get('vertices', T)
    tpoly = np.empty(nt, np.int32)
    me.loop_triangles.foreach_get('polygon_index', tpoly)
    cut = is_cut_mesh(me, target)
    asked, got_note = target, ''

    def one(target, all_q):
        if cut:
            # 0.24.75 a low-poly part (Cut / Base Mesh / decimated): even triangles, its own edges as fixed lines
            P, Fq, fpoly, pvert, st = remesh_cut(me, target, all_quads=all_q, crease_deg=crease_deg,
                                                 nthreads=nthreads)
        else:
            P, Fq, tsrc, psrc, st = remesh_arrays(V, T.reshape(-1, 3), target, all_quads=all_q,
                                                  crease_deg=crease_deg, nthreads=nthreads)
            fpoly, pvert = tpoly[tsrc], psrc
        return P, Fq, fpoly, pvert, st
    try:
        P, Fq, fpoly, pvert, st = one(target, all_quads)
        # 0.24.82 far fewer faces than asked: a thin-walled sculpt loses most walls at the coarse scale All Quads
        # works at (8,000 asked gave 1,076; 2x / 4x finer gave 2,277 then 66,642 - a cliff, not a slope).  So no
        # scaling: All Quads falls back to Mostly Quads at the same count, Mostly tries 2x once; the result nearer
        # (in ratio) to what was asked is kept, and the message says what happened.
        if YIELD_FALLBACK and len(Fq) < YIELD_MIN * asked:
            first = (P, Fq, fpoly, pvert, st)
            again = one(asked, False) if all_quads else one(asked * 2, False)
            ratio = lambda n: abs(math.log(max(1, n) / asked))
            if ratio(len(again[1])) < ratio(len(first[1])):
                P, Fq, fpoly, pvert, st = again
                got_note = (f' ({"All Quads" if all_quads else "the first try"} kept only {len(first[1]):,} faces'
                            f' - thin walls: {"Mostly Quads at the same count" if all_quads else "2x finer"} instead)')
            else:
                got_note = f' (only {len(Fq):,} faces could be kept: walls thinner than a quad)'
    except RuntimeError as ex:
        return str(ex)
    if not len(Fq):                                        # 0.24.81 (seen on one part of a 45-part export: the
        return 'Quad Remesh: nothing came back - the part is kept as it is'   # mesh went out empty, then 0 / 0)
    attrs = [a for a in fd._read_attrs(me) if a[2] in {'POINT', 'FACE'}]
    sizes = np.where(Fq[:, 3] < 0, 3, 4)
    loops = Fq[Fq >= 0]                                    # row by row: each face's corners in order
    new = fd.fresh_like(me)
    closed = None
    try:
        for a in [a for a in new.attributes if a.domain == 'CORNER' and not a.name.startswith('.')]:
            new.attributes.remove(a)                       # (UVs / corner colours do not fit the new faces)
        fd.build_mesh(new, P, loops, sizes)
        if cut and st.get('open'):
            fpoly, b0, b1, new2old, welded = close_holes(new, fpoly, border_tree(me, 0.25 * st['h']), 0.5 * st['h'],
                                                         weld=0.05 * st['h'])
            closed = (b0, b1)
            sizes = np.array([len(p.vertices) for p in new.polygons])
            if new2old is not None:                        # (points welded: their attributes / hard edges follow)
                pvert = pvert[new2old]
                old2new = {int(o): n for n, o in enumerate(new2old)}
                pairs = [(old2new.get(welded.get(int(a), int(a))), old2new.get(welded.get(int(b), int(b))))
                         for a, b in st['hard']]
                st['hard'] = np.array([(a, b) for a, b in pairs if a is not None and b is not None and a != b],
                                      np.int32).reshape(-1, 2)
        fd._write_attrs(new, attrs, pvert, fpoly, None)
        from . import hard_edges
        hard_edges.mark_pairs(new, st['hard'], crease=True)
        new.update()
        if drop_twins(new):                                # 0.24.77 (attributes / hard edges kept by BMesh)
            sizes = np.array([len(p.vertices) for p in new.polygons])
        from . import core_geometry as cg
        if any(cg.tidy_result(new, shards=False, slivers=False).values()):   # 0.24.83 zero-area faces dissolved
            sizes = np.array([len(p.vertices) for p in new.polygons])
    except Exception:
        bpy.data.meshes.remove(new)                        # the SubTool keeps its mesh
        raise
    if not len(new.polygons):
        bpy.data.meshes.remove(new)
        return 'Quad Remesh: nothing came back - the part is kept as it is'
    # 0.24.83 a closed part thinner than a quad came back as a flat sheet (its two sides on the same points: no
    # volume, holes once the folds are cleaned): the volume must survive, else finer (x2, up to VOLUME_TRIES) and
    # at last the part is kept as it is
    vol0, vol1 = _volume(me), _volume(new)
    open_new, multi_new = _open_multi(new)
    if (open_new or multi_new) and cg.non_manifold_edge_count(me) == 0:
        from . import mesh_fix                             # (a few sides open on a closed part: shut first)
        mesh_fix.fix_mesh(new, fill='SMALL')
        open_new, multi_new = _open_multi(new)
        vol1 = _volume(new)
    n_new = len(new.polygons)
    closed_in = cg.non_manifold_edge_count(me) == 0
    if closed_in and (vol0 > 0 and (vol1 < VOLUME_KEEP * vol0 or vol1 > vol0 / VOLUME_KEEP)
                      or open_new > max(OPEN_OK_MIN, OPEN_OK * n_new) or multi_new):
        bpy.data.meshes.remove(new)
        tries = _st_tries.get(id(ob), 0)
        if tries < VOLUME_TRIES and target * 2 <= QUAD_MAX_FACES:
            _st_tries[id(ob)] = tries + 1
            try:
                return _remesh_object(ob, me, polys0, t0, fixst, target * 2, all_quads, crease_deg, nthreads)
            finally:
                _st_tries.pop(id(ob), None)
        why = (f'{open_new} sides would stay open' if open_new > max(OPEN_OK_MIN, OPEN_OK * max(1, n_new))
               else f'{multi_new} edges would carry 3+ faces' if multi_new
               else f'the quads lost {100 - vol1 / max(vol0, 1e-12) * 100:.0f} % of its volume')
        return (f'Quad Remesh{got_note}: the part is thinner than a quad at this count ({polys0:,} faces kept as '
                f'they are - {why}): ask for more faces')
    fd.swap_mesh(ob, new)
    ob.show_wire = ob.show_all_edges = True               # 0.24.76 the new quads are shown
    if len(st['hard']):
        from . import hard_edges
        ob[hard_edges.KEY] = 1                             # the Hard Edges bevel / subdivide work on it right away
    quads = int((sizes == 4).sum())
    dt = time.perf_counter() - t0
    edges = f', {len(st["hard"]):,} hard edges marked' if len(st['hard']) else ''
    how = got_note
    if cut:
        how += ' (low-poly part: its own edges kept'
        if st.get('tries', 1) > 1:
            how += f', {st["tries"]}x finer for a groove narrower than a quad'
        if closed and closed[0]:
            how += (', holes closed' if not closed[1] else
                    f', {closed[1]} sides left open / pinched (a wall thinner than a quad)')
        how += ')'
    if fixst is not None:
        fixed = fixst['open_before'] + fixst['multi_before'] - fixst['open_after'] - fixst['multi_after']
        how += f' (Fix Mesh first: {fixed:,} broken edges repaired)'
    return (f'Quad Remesh{how}: {polys0:,} > {len(sizes):,} polygons, {quads / len(sizes) * 100:.0f} % quads{edges} '
            f'in {dt:.1f} s')
