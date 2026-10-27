"""0.24.66 Fast Decimate: Mecha Lab's own decimation engine (``bin/mdecim_*``), for Decimate Current.

The same kind of decimation as Blender's Decimate (quadric error edge collapse: detail stays where the shape needs
it) in plain C on many threads: about 2x faster on one core, more on many (the mesh is cut into one block per
core, then one pass over the whole mesh finishes it).  Options (ZBrush Decimation Master names):

* Even Tris - the triangles stay round (no slivers): nicer topology, a little less exact
* Allow Quads - pairs of triangles become quads afterwards
* Keep Mask - masked parts keep more detail
* Keep Groups - polygroup (face set) borders stay where they are
* Keep Borders - open borders do not move

Points and polygons keep who they are, so the mask, polygroups, colours, materials and hidden parts come along
(UVs too, approximately at seams).  Edge data (creases, seams) is not kept.  Without the engine for this system
(macOS, ARM) Blender's Decimate modifier is used.  The engine is a C library loaded with ctypes (no Python API, so
any Blender version); its source is ``tools_dev/native/mdecim.c``.
"""
from __future__ import annotations

import ctypes
import os
import platform
import shutil
import sys
import time

import numpy as np

import bpy

VERSION = 4                 # engine API this module talks to (4: length_weight)
SHAPE_TIE = 0.02           # the small shape term of plain decimation (Even Tris: 1.0)
MASK_WEIGHT = 24.0          # a fully masked point's collapse cost x (1 + this): about 2x the density there
_LIB = [None]               # the loaded library, False = none for this system


class _Opts(ctypes.Structure):
    _fields_ = [('boundary_weight', ctypes.c_float), ('min_quality', ctypes.c_float),
                ('quality_weight', ctypes.c_float), ('lock_boundary', ctypes.c_int), ('threads', ctypes.c_int),
                ('length_weight', ctypes.c_float)]


def lib_name():
    machine = platform.machine().lower()
    if machine not in {'amd64', 'x86_64', 'x64'}:
        return ''
    if sys.platform == 'win32':
        return 'mdecim_win_x64.dll'
    if sys.platform.startswith('linux'):
        return 'mdecim_linux_x64.so'
    return ''


def _load_path(src):
    """Windows keeps a loaded DLL locked: load a copy in the user folder, so the add-on can still be updated."""
    if sys.platform != 'win32':
        return src
    try:
        d = bpy.utils.extension_path_user(__package__, path='bin', create=True)
    except (AttributeError, ValueError, TypeError, OSError):
        return src
    st = os.stat(src)
    dst = os.path.join(d, f'mdecim_{st.st_size}_{int(st.st_mtime)}.dll')
    if not os.path.isfile(dst):
        tmp = dst + '.tmp'
        shutil.copyfile(src, tmp)
        os.replace(tmp, dst)
    return dst


def lib():
    """The engine (ctypes library) or None."""
    if _LIB[0] is None:
        _LIB[0] = False
        name = lib_name()
        src = os.path.join(os.path.dirname(__file__), 'bin', name) if name else ''
        if src and os.path.isfile(src):
            try:
                L = ctypes.CDLL(_load_path(src))
                L.mdecim_version.restype = ctypes.c_int
                if L.mdecim_version() >= VERSION:
                    L.mdecim_run.restype = ctypes.c_int
                    _LIB[0] = L
            except (OSError, AttributeError) as ex:
                print('[Mecha Lab] Fast Decimate engine not loaded:', ex)
    return _LIB[0] or None


def available():
    return lib() is not None


def threads():
    return max(1, min(64, os.cpu_count() or 1))


def _ptr(a, t):
    return None if a is None else a.ctypes.data_as(ctypes.POINTER(t))


def run(V, F, target, even=False, keep_borders=False, locked=None, weight=None, feat=None, nthreads=None,
        uniform=0.0):
    """Decimate triangles F (n x 3) over points V (n x 3) to about ``target`` triangles.

    Returns (points, triangles, source point of each point, source triangle of each triangle)."""
    L = lib()
    if L is None:
        raise RuntimeError('Fast Decimate engine not available on this system')
    V = np.ascontiguousarray(V, np.float32).reshape(-1, 3)
    F = np.ascontiguousarray(F, np.int32).reshape(-1, 3)
    oV = np.empty_like(V)
    oF = np.empty_like(F)
    oVs = np.empty(len(V), np.int32)
    oFs = np.empty(len(F), np.int32)
    if locked is not None:
        locked = np.ascontiguousarray(locked, np.uint8)
    if weight is not None:
        weight = np.ascontiguousarray(weight, np.float32)
    nfeat = 0
    if feat is not None and len(feat):
        feat = np.ascontiguousarray(feat, np.int32).reshape(-1, 3)
        nfeat = len(feat)
    else:
        feat = None
    # 0.24.70 plain decimation keeps a small shape term too: on flat parts every collapse costs 0, without it the
    # slivers piled up and most collapses failed again and again (a 357k-triangle hard-surface part: 7 s -> 0.6 s)
    o = _Opts(1000.0, 0.25 if even else 0.0, 1.0 if even else SHAPE_TIE, 1 if keep_borders else 0,
              nthreads or threads(), uniform)
    nv = ctypes.c_int()
    nf = ctypes.c_int()
    rc = L.mdecim_run(_ptr(V, ctypes.c_float), len(V), _ptr(F, ctypes.c_int), len(F), int(target), ctypes.byref(o),
                      _ptr(locked, ctypes.c_ubyte), _ptr(weight, ctypes.c_float), _ptr(feat, ctypes.c_int), nfeat,
                      _ptr(oV, ctypes.c_float), _ptr(oF, ctypes.c_int), _ptr(oVs, ctypes.c_int),
                      _ptr(oFs, ctypes.c_int), ctypes.byref(nv), ctypes.byref(nf))
    if rc:
        raise RuntimeError(f'Fast Decimate failed (code {rc})')
    return oV[:nv.value], oF[:nf.value], oVs[:nv.value], oFs[:nf.value]


# --- mesh attributes ----------------------------------------------------------------------------------------------

_TYPES = {  # data type: (foreach key, values per element, numpy type)
    'FLOAT': ('value', 1, np.float32), 'INT': ('value', 1, np.int32), 'INT8': ('value', 1, np.int32),
    'BOOLEAN': ('value', 1, bool), 'FLOAT_VECTOR': ('vector', 3, np.float32), 'FLOAT2': ('vector', 2, np.float32),
    'FLOAT_COLOR': ('color', 4, np.float32), 'BYTE_COLOR': ('color', 4, np.float32),
    'INT32_2D': ('value', 2, np.int32), 'QUATERNION': ('value', 4, np.float32),
}
_SKIP = {'position', '.edge_verts', '.corner_vert', '.corner_edge'}


def _read_attrs(me):
    out = []
    for a in me.attributes:
        if a.name in _SKIP or a.domain not in {'POINT', 'FACE', 'CORNER'} or a.data_type not in _TYPES:
            continue
        if a.name.startswith(('.select', '.vs.', '.es.', '.pn.', '.uv')):
            continue
        key, w, dt = _TYPES[a.data_type]
        vals = np.empty(len(a.data) * w, dt)
        a.data.foreach_get(key, vals)
        out.append((a.name, a.data_type, a.domain, key, w, vals.reshape(len(a.data), w)))
    return out


def _write_attrs(me, attrs, vsrc, fpoly, corner_loop):
    for name, dtype, domain, key, w, vals in attrs:
        idx = vsrc if domain == 'POINT' else (fpoly if domain == 'FACE' else corner_loop)
        a = me.attributes.get(name)
        if a is None or a.domain != domain or a.data_type != dtype:
            if a is not None:
                me.attributes.remove(a)
            try:
                a = me.attributes.new(name, dtype, domain)
            except RuntimeError:
                continue
        a.data.foreach_set(key, vals[idx].ravel())


def decimate_object(ob, keep_percent, even=False, quads=False, keep_mask=False, keep_groups=False,
                    keep_borders=False, nthreads=None):
    """Decimate mesh object ``ob`` (Object Mode) to about ``keep_percent`` % of its triangles.  Returns a message."""
    me = ob.data
    if me.shape_keys is not None:
        return 'Decimate: remove the shape keys first'
    if any(m.type == 'MULTIRES' for m in ob.modifiers):
        return 'Decimate: delete or apply the subdivision levels first (Multires)'
    t0 = time.perf_counter()
    polys0 = len(me.polygons)
    me.calc_loop_triangles()
    nt = len(me.loop_triangles)
    nv = len(me.vertices)
    if nt < 8:
        return 'Decimate: nothing to decimate'
    V = np.empty(nv * 3, np.float32)
    me.vertices.foreach_get('co', V)
    T = np.empty(nt * 3, np.int32)
    me.loop_triangles.foreach_get('vertices', T)
    tpoly = np.empty(nt, np.int32)
    me.loop_triangles.foreach_get('polygon_index', tpoly)
    tloop = np.empty(nt * 3, np.int32)
    me.loop_triangles.foreach_get('loops', tloop)
    cvert = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get('vertex_index', cvert)
    T = T.reshape(-1, 3)
    weight = feat = None
    if keep_mask:
        a = me.attributes.get('.sculpt_mask')
        if a is not None and a.domain == 'POINT':
            m = np.empty(nv, np.float32)
            a.data.foreach_get('value', m)
            if m.any():
                weight = 1.0 + MASK_WEIGHT * np.clip(m, 0.0, 1.0)
    if keep_groups:
        a = me.attributes.get('.sculpt_face_set')
        if a is not None and a.domain == 'FACE':
            g = np.empty(len(me.polygons), np.int32)
            a.data.foreach_get('value', g)
            feat = group_borders(T, g[tpoly], nv)
    target = max(4, int(round(nt * keep_percent / 100.0)))
    oV, oF, vsrc, fsrc = run(V, T, target, even=even, keep_borders=keep_borders, weight=weight, feat=feat,
                             nthreads=nthreads)
    # corners: the triangle's own corner when it still has its point, else any corner of the point that stayed
    first_loop = np.full(nv, -1, np.int64)
    first_loop[cvert[::-1]] = np.arange(len(cvert))[::-1]
    src_loop = tloop.reshape(-1, 3)[fsrc]
    keep = cvert[src_loop] == vsrc[oF]
    corner_loop = np.where(keep, src_loop, first_loop[vsrc[oF]]).ravel()
    attrs = _read_attrs(me)
    uv_active = me.uv_layers.active.name if me.uv_layers.active else ''
    col_active = getattr(me.color_attributes, 'active_color_name', '')
    col_render = getattr(me.color_attributes, 'default_color_name', '')
    me.clear_geometry()
    me.vertices.add(len(oV))
    me.vertices.foreach_set('co', oV.ravel())
    me.loops.add(len(oF) * 3)
    me.loops.foreach_set('vertex_index', oF.ravel())
    me.polygons.add(len(oF))
    me.polygons.foreach_set('loop_start', np.arange(0, len(oF) * 3, 3, dtype=np.int32))
    me.update(calc_edges=True)
    _write_attrs(me, attrs, vsrc, tpoly[fsrc], corner_loop)
    if uv_active and uv_active in me.uv_layers:
        me.uv_layers.active = me.uv_layers[uv_active]
    try:
        if col_active:
            me.color_attributes.active_color_name = col_active
        if col_render:
            me.color_attributes.default_color_name = col_render
    except (AttributeError, TypeError, KeyError):
        pass
    if quads:
        join_quads(me)
    me.update()
    dt = time.perf_counter() - t0
    return f'Decimate: {polys0:,} > {len(me.polygons):,} polygons in {dt:.1f} s ({nthreads or threads()} threads)'


def group_borders(T, tgroup, nv):
    """(point, point, triangle) for every triangle side between two polygroups."""
    e = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]]).astype(np.int64)
    tri = np.tile(np.arange(len(T)), 3)
    lo = e.min(1)
    hi = e.max(1)
    key = lo * nv + hi
    order = np.argsort(key, kind='stable')
    k = key[order]
    same = k[1:] == k[:-1]
    i = np.nonzero(same)[0]
    a, b = order[i], order[i + 1]
    diff = tgroup[tri[a]] != tgroup[tri[b]]
    s = np.concatenate([a[diff], b[diff]])
    if not len(s):
        return None
    return np.stack([e[s, 0], e[s, 1], tri[s]], 1).astype(np.int32)


def join_quads(me):
    import math

    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.join_triangles(bm, faces=bm.faces[:], angle_face_threshold=math.radians(40.0),
                             angle_shape_threshold=math.radians(40.0), cmp_seam=True, cmp_materials=True)
    bm.to_mesh(me)
    bm.free()


def blender_decimate(context, ob, keep_percent):
    """Fallback: Blender's Decimate modifier."""
    mod = ob.modifiers.new('MCH_Decimate', 'DECIMATE')
    mod.ratio = keep_percent / 100.0
    with context.temp_override(object=ob, active_object=ob):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return f'Decimate (Blender): {len(ob.data.polygons):,} polygons'
