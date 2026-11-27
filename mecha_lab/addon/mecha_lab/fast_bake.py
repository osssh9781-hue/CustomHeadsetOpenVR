"""0.24.340 Fast Bake (user: "베이크를 좀 더 빠르게 ... 4번으로 가자 빠르게 해 줘 최대한"): the Normal map baked by Mecha
Lab's own engine (mbake, C, multi-threaded) instead of a Cycles render.

The rule is the one Blender's Selected to Active bake with our cage follows: the low poly rasterised in its own UV
space; for each texel a ray from the cage point (the low pushed out ``ext`` along its averaged point normals) through
the low's point, within twice ``ext``; the nearest high poly hit gives the high's smooth normal there, written in the
low's tangent space (MikkTSpace tangents, as Blender's).  One ray a texel is exact - no samples, no noise, no Cycles
scene to build.  A miss writes the low's own normal (flat).  The margin is filled outward (Extend).

GPU Gems 3 ch. 22 (Baking Normal Maps on the GPU); AssetGen (arXiv 2605.26137): the same projection on the GPU."""
from __future__ import annotations

import ctypes
import os
import time

import bpy
import numpy as np

VERSION = 3
_FP = ctypes.POINTER(ctypes.c_float)
_IP = ctypes.POINTER(ctypes.c_int)
_UP = ctypes.POINTER(ctypes.c_ubyte)
_L = [None]


def lib():
    """The engine with the baker, or None (then Cycles bakes as before)."""
    if _L[0] is None:
        _L[0] = False
        from . import fast_decimate as fd
        L = fd.lib()
        if L is not None:
            try:
                L.mbake_version.restype = ctypes.c_int
                L.mbake_version.argtypes = []
                if L.mbake_version() == VERSION:
                    L.mbake_maps.restype = ctypes.c_int
                    L.mbake_maps.argtypes = [ctypes.c_int, _FP, _FP, _FP, _FP, _FP, _FP, ctypes.c_int, _FP,
                                             ctypes.c_int, _IP, _FP, _FP, ctypes.c_int, ctypes.c_int, ctypes.c_float,
                                             ctypes.c_int, ctypes.c_int, ctypes.c_int, _FP, _FP, _FP, _FP,
                                             ctypes.c_int, ctypes.c_float, _UP]
                    _L[0] = L
            except AttributeError:                    # (an older engine without the baker)
                pass
    return _L[0] or None


def _corner_normals(me):
    n = np.empty(len(me.loops) * 3, np.float32)
    try:
        me.corner_normals.foreach_get('vector', n)
    except AttributeError:                            # (older Blender)
        me.calc_normals_split()
        me.loops.foreach_get('normal', n)
    return n.reshape(-1, 3)


def _low_arrays(context, low, ext):
    """(uv, P, N, T, S, C) per loop-triangle corner of the low (with its modifiers), world space."""
    import bmesh
    from . import bake_maps as bm_
    dg = context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(bm_._lc_full(low, dg) if hasattr(bm_, '_lc_full') else
                                         low.evaluated_get(dg), depsgraph=dg)
    try:
        vn = np.empty(len(me.vertices) * 3, np.float32)
        me.vertex_normals.foreach_get('vector', vn)
        vn = vn.reshape(-1, 3)
        if any(len(p.vertices) > 4 for p in me.polygons):   # (MikkTSpace here wants tris / quads)
            b = bmesh.new()
            b.from_mesh(me)
            bmesh.ops.triangulate(b, faces=[f for f in b.faces if len(f.verts) > 4], quad_method='BEAUTY',
                                  ngon_method='BEAUTY')
            b.to_mesh(me)
            b.free()
        uvl = me.uv_layers.active
        if uvl is None:
            raise RuntimeError('the low has no UVs')
        me.calc_tangents(uvmap=uvl.name)
        me.calc_loop_triangles()
        nt = len(me.loop_triangles)
        lo = np.empty(nt * 3, np.int64)
        me.loop_triangles.foreach_get('loops', lo)
        vi = np.empty(nt * 3, np.int64)
        me.loop_triangles.foreach_get('vertices', vi)
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        uv = np.empty(len(me.loops) * 2, np.float32)
        uvl.data.foreach_get('uv', uv)
        uv = uv.reshape(-1, 2)
        tan = np.empty(len(me.loops) * 3, np.float32)
        me.loops.foreach_get('tangent', tan)
        sgn = np.empty(len(me.loops), np.float32)
        me.loops.foreach_get('bitangent_sign', sgn)
        cn = _corner_normals(me)
        M = np.array(low.matrix_world, np.float64)
        R = M[:3, :3]
        Nm = np.linalg.inv(R).T
        sc = low.matrix_world.to_scale()
        s = max(float(np.mean(np.abs([sc.x, sc.y, sc.z]))), 1e-9)

        def pts(X):
            return X @ R.T + M[:3, 3]

        def dirs(X, Q):
            Y = X @ Q.T
            return Y / np.maximum(np.linalg.norm(Y, axis=1, keepdims=True), 1e-20)
        P = pts(co[vi].astype(np.float64))
        C = pts((co[vi] + vn[vi] * (ext / s)).astype(np.float64))
        N = dirs(cn[lo].astype(np.float64), Nm)
        T = dirs(tan.reshape(-1, 3)[lo].astype(np.float64), R)
        return uv[lo], P, N, T, sgn[lo], C, nt
    finally:
        bpy.data.meshes.remove(me)


def _high_arrays(context, highs, want_curv=False):
    """(points, triangles, corner normals per triangle, curvature per point or None) of all the highs, world space,
    float32 (the engine normalises what it interpolates)."""
    dg = context.evaluated_depsgraph_get()
    Vs, Ts, Ns, Cs, base = [], [], [], [], 0
    for h in highs:
        ev = h.evaluated_get(dg)
        me = ev.to_mesh()
        try:
            me.calc_loop_triangles()
            nt = len(me.loop_triangles)
            if not nt:
                continue
            nv = len(me.vertices)
            co = np.empty(nv * 3, np.float32)
            me.vertices.foreach_get('co', co)
            co = co.reshape(-1, 3)
            vi = np.empty(nt * 3, np.int32)
            me.loop_triangles.foreach_get('vertices', vi)
            lo = np.empty(nt * 3, np.int32)
            me.loop_triangles.foreach_get('loops', lo)
            cn = _corner_normals(me)
            M = np.array(h.matrix_world, np.float32)
            R = M[:3, :3]
            Nm = np.linalg.inv(R.astype(np.float64)).T.astype(np.float32)
            Vs.append(co @ R.T + M[:3, 3])
            Ts.append(vi.reshape(-1, 3) + base)
            Ns.append(cn[lo] @ Nm.T)
            if want_curv:
                from . import bake_maps as bm_
                nr = np.empty(nv * 3, np.float32)
                me.vertex_normals.foreach_get('vector', nr)
                E = np.empty(len(me.edges) * 2, np.int64)
                me.edges.foreach_get('vertices', E)
                Cs.append(bm_._curvature(co.astype(np.float64), nr.reshape(-1, 3).astype(np.float64),
                                         E.reshape(-1, 2), nv).astype(np.float32))
            base += nv
        finally:
            ev.to_mesh_clear()
    if not Vs:
        raise RuntimeError('the high poly has no faces')
    return (np.concatenate(Vs), np.concatenate(Ts).astype(np.int32), np.concatenate(Ns),
            np.concatenate(Cs) if want_curv else None)


def bake_maps(context, low, highs, w, h, ext, kinds=('NORMAL',), green='OPENGL', margin=16, threads=None,
              ao_samples=64, ao_dist=1.0):
    """The maps ``kinds`` (NORMAL / HEIGHT / CURV / AO - 0.24.341: ``ao_samples`` cosine rays a texel from the high's
    point, ``ao_dist`` world units) of ``highs`` onto ``low`` (w x h), all from the same rays, with
    the cage ``ext`` (world units).  Returns {kind: pixels (h, w, 4) float32}, 'HEIGHT_RANGE': the height range
    (world units, 0.5 grey = on the low), 'seconds'.  Raises RuntimeError (no engine: the caller bakes with Cycles)."""
    L = lib()
    if L is None:
        raise RuntimeError('the fast baker is not available on this system')
    t0 = time.time()
    uv, P, N, T, S, C, nlt = _low_arrays(context, low, ext)
    HV, HT, HN, HA = _high_arrays(context, highs, 'CURV' in kinds)
    n = w * h
    out = np.zeros(n * 4, np.float32) if 'NORMAL' in kinds else None
    outh = np.zeros(n, np.float32) if 'HEIGHT' in kinds else None
    outa = np.zeros(n, np.float32) if 'CURV' in kinds else None
    outo = np.zeros(n, np.float32) if 'AO' in kinds else None
    mask = np.zeros(n, np.uint8)
    keep = []

    def fp(a):
        if a is None:
            return None
        a = np.ascontiguousarray(a, np.float32)
        keep.append(a)
        return a.ctypes.data_as(_FP)
    a_HT = np.ascontiguousarray(HT, np.int32)
    th = threads or max(1, min(64, os.cpu_count() or 1))
    rc = L.mbake_maps(int(nlt), fp(uv), fp(P), fp(N), fp(T), fp(S), fp(C), int(len(HV)), fp(HV), int(len(HT)),
                      a_HT.ctypes.data_as(_IP), fp(HN), fp(HA), int(w), int(h), float(2.0 * ext),
                      1 if green == 'DIRECTX' else 0, int(margin), int(th),
                      out.ctypes.data_as(_FP) if out is not None else None,
                      outh.ctypes.data_as(_FP) if outh is not None else None,
                      outa.ctypes.data_as(_FP) if outa is not None else None,
                      outo.ctypes.data_as(_FP) if outo is not None else None, int(ao_samples), float(ao_dist),
                      mask.ctypes.data_as(_UP))
    if rc != 0:
        raise RuntimeError(f'the fast baker stopped (code {rc})')
    res = {}
    if out is not None:
        res['NORMAL'] = out.reshape(h, w, 4)
    on = mask.astype(bool)
    if outh is not None:
        rng = max(float(np.percentile(np.abs(outh[on]), 99)) if on.any() else 0.0, 1e-9)
        g = np.clip(0.5 + 0.5 * outh / rng, 0.0, 1.0)
        res['HEIGHT'] = np.repeat(g, 4).reshape(h, w, 4)
        res['HEIGHT'][..., 3] = 1.0
        res['HEIGHT_RANGE'] = rng
    if outa is not None:
        res['CURV'] = np.repeat(outa, 4).reshape(h, w, 4)
        res['CURV'][..., 3] = 1.0
    if outo is not None:
        res['AO'] = np.repeat(outo, 4).reshape(h, w, 4)
        res['AO'][..., 3] = 1.0
    res['seconds'] = time.time() - t0
    return res


def bake_normal(context, low, highs, img, ext, green='OPENGL', margin=16, threads=None):
    """The Normal map of ``highs`` onto ``low`` into ``img`` (its size).  Returns seconds."""
    w, h = img.size
    r = bake_maps(context, low, highs, w, h, ext, ('NORMAL',), green, margin, threads)
    img.pixels.foreach_set(r['NORMAL'].ravel())
    img.update()
    return r['seconds']
