"""0.24.71 Quad Remesh (ZBrush shelf): Mecha Lab's own field-aligned quad remesher, in the C engine (mquad).

The part is first sampled with Fast Decimate in its even-spacing mode at a few resolutions; a direction field and a
position field (Instant Meshes, Jakob et al. 2015) are solved on them coarse to fine with the hard edges as
constraints, and the quads are read off the fine one.  Mostly Quads keeps the few triangles where rows of quads
end; All Quads makes the quads at half the count and splits every face once (quad -> 4, triangle -> 3).
Polygroups, materials and point attributes (mask, colours) come along; UVs do not (new topology).
"""
from __future__ import annotations

import ctypes
import math
import time

import numpy as np

from . import fast_decimate as fd

VERSION = 1                     # mquad API this module talks to
MAXLEV = 8
LENGTH_WEIGHT = 0.1             # Fast Decimate even spacing for the levels
LEVELS = (16.0, 4.0, 1.0, 0.25)  # level triangles per quad, fine to coarse
ITERS_ORIENT = (20, 30, 60)     # Gauss-Seidel sweeps per level (fine first); the coarsest gets COARSE_ITERS
ITERS_POS = (30, 40, 80)
COARSE_ITERS = 200
MIN_CHAIN = 1.5                 # hard-edge chains shorter than this many quads are ignored


class _Opts(ctypes.Structure):
    _fields_ = [('scale', ctypes.c_float), ('crease_deg', ctypes.c_float), ('min_chain', ctypes.c_float),
                ('all_quads', ctypes.c_int), ('threads', ctypes.c_int), ('seed', ctypes.c_int),
                ('iters_orient', ctypes.c_int * MAXLEV), ('iters_pos', ctypes.c_int * MAXLEV)]


class _Out(ctypes.Structure):
    _fields_ = [('nv', ctypes.c_int), ('nf', ctypes.c_int), ('V', ctypes.POINTER(ctypes.c_float)),
                ('F', ctypes.POINTER(ctypes.c_int)), ('fsrc', ctypes.POINTER(ctypes.c_int)),
                ('vsrc', ctypes.POINTER(ctypes.c_int)), ('stats', ctypes.c_int * 8)]


def lib():
    """The engine with the quad remesher, or None."""
    L = fd.lib()
    if L is None:
        return None
    try:
        L.mquad_version.restype = ctypes.c_int
        if L.mquad_version() < VERSION:
            return None
        L.mquad_run.restype = ctypes.c_int
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


def remesh_arrays(V, T, target, all_quads=False, crease_deg=30.0, nthreads=None, seed=0):
    """Quad remesh triangles T over points V to about ``target`` faces.

    Returns (points (n, 3), faces (m, 4) with -1 as the 4th index of a triangle, the input triangle under each face,
    the input point nearest each point, stats dict)."""
    L = lib()
    if L is None:
        raise RuntimeError('Quad Remesh engine not available on this system')
    V = np.ascontiguousarray(V, np.float32).reshape(-1, 3)
    T = np.ascontiguousarray(T, np.int32).reshape(-1, 3)
    area = float(0.5 * np.linalg.norm(np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]]), axis=1).sum())
    if area <= 0.0:
        raise RuntimeError('Quad Remesh: the mesh has no area')
    n_ext = max(12, int(target / 4) if all_quads else int(target))
    h = math.sqrt(area / n_ext)
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
    for k in range(n):
        o.iters_orient[k] = COARSE_ITERS if k == n - 1 else ITERS_ORIENT[min(k, len(ITERS_ORIENT) - 1)]
        o.iters_pos[k] = COARSE_ITERS if k == n - 1 else ITERS_POS[min(k, len(ITERS_POS) - 1)]
    nv = (ctypes.c_int * n)(*[len(lv[0]) for lv in levels])
    nf = (ctypes.c_int * n)(*[len(lv[1]) for lv in levels])
    Vc = np.ascontiguousarray(np.concatenate([lv[0].ravel() for lv in levels]), np.float32)
    Fc = np.ascontiguousarray(np.concatenate([lv[1].ravel() for lv in levels]), np.int32)
    Sc = np.ascontiguousarray(np.concatenate(srcs) if srcs else np.zeros(1, np.int32), np.int32)
    out = _Out()
    rc = L.mquad_run(n, nv, nf, Vc.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                     Fc.ctypes.data_as(ctypes.POINTER(ctypes.c_int)), Sc.ctypes.data_as(ctypes.POINTER(ctypes.c_int)),
                     ctypes.byref(o), ctypes.byref(out))
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
    finally:
        L.mquad_free(ctypes.byref(out))
    stats['levels'] = [len(lv[1]) for lv in levels]
    stats['scale'] = h
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
    try:
        P, Fq, tsrc, psrc, st = remesh_arrays(V, T.reshape(-1, 3), target, all_quads=all_quads,
                                              crease_deg=crease_deg, nthreads=nthreads)
    except RuntimeError as ex:
        return str(ex)
    attrs = [a for a in fd._read_attrs(me) if a[2] in {'POINT', 'FACE'}]
    sizes = np.where(Fq[:, 3] < 0, 3, 4)
    loops = Fq[Fq >= 0]                                    # row by row: each face's corners in order
    me.clear_geometry()
    me.vertices.add(len(P))
    me.vertices.foreach_set('co', P.astype(np.float32).ravel())
    me.loops.add(len(loops))
    me.loops.foreach_set('vertex_index', loops.astype(np.int32))
    me.polygons.add(len(Fq))
    me.polygons.foreach_set('loop_start', np.concatenate([[0], np.cumsum(sizes)[:-1]]).astype(np.int32))
    me.update(calc_edges=True)
    fd._write_attrs(me, attrs, psrc, tpoly[tsrc], None)
    me.update()
    quads = int((sizes == 4).sum())
    dt = time.perf_counter() - t0
    return (f'Quad Remesh: {polys0:,} > {len(Fq):,} polygons, {quads / len(Fq) * 100:.0f} % quads '
            f'in {dt:.1f} s')
