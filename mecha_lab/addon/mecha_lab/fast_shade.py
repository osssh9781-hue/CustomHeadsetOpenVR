"""0.24.341 Fast No High Poly bake (user: "노하이폴리도 느려서 만들라는거야"): a mesh's own material baked onto its own
UVs without Cycles - the material's node tree evaluated texel by texel (numpy, all texels at once), the ray nodes
(Ambient Occlusion, Bevel) and the image lookups by Mecha Lab's engine (mbake v4, C, threads), the way Cycles' SVM
does each node.  One pass per map instead of a Cycles render per map, no samples, no noise.

What it cannot evaluate (a node it does not know - Noise / Voronoi textures, Light Path, Pointiness ...), it says so
(``Unsupported``) and that map is baked by Cycles as before.  Nothing in the material is changed."""
from __future__ import annotations

import ctypes
import math
import os
import time

import bpy
import numpy as np

from . import fast_bake

_FP = ctypes.POINTER(ctypes.c_float)
_IP = ctypes.POINTER(ctypes.c_int)
_UIP = ctypes.POINTER(ctypes.c_uint)
_UP = ctypes.POINTER(ctypes.c_ubyte)
_L = [None]
LUMA = np.array([0.2126729, 0.7151522, 0.0721750], np.float32)     # (Cycles' rgb_to_y for linear Rec.709 / sRGB)
# (Cycles averages a ray node over its samples x the bake's pixel samples: ours takes that many rays at once - one
#  smooth value a texel, where Cycles' would be noise)
AO_MULT = 2
BEVEL_MULT = 4
KINDS = ('NORMAL', 'AO', 'COLOR', 'ROUGH', 'METAL', 'EMIT')


class Unsupported(Exception):
    """A node / setting the fast evaluator does not do: that map goes to Cycles."""


def lib():
    if _L[0] is None:
        _L[0] = False
        L = fast_bake.lib()
        if L is not None:
            try:
                if L.mbake_version() >= 4:
                    L.mbake_raster.restype = ctypes.c_int
                    L.mbake_raster.argtypes = [ctypes.c_int, _FP, ctypes.c_int, ctypes.c_int, _IP, _FP, _UP]
                    L.mbake_margin.restype = None
                    L.mbake_margin.argtypes = [_FP, ctypes.c_int, _UP, ctypes.c_int, ctypes.c_int, ctypes.c_int]
                    L.mbake_image.restype = None
                    L.mbake_image.argtypes = [_FP, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                              ctypes.c_int, ctypes.c_int, _FP, _FP, ctypes.c_int]
                    L.mbake_scene_new.restype = ctypes.c_void_p
                    L.mbake_scene_new.argtypes = [ctypes.c_int, _FP, ctypes.c_int, _IP, _FP]
                    L.mbake_scene_free.restype = None
                    L.mbake_scene_free.argtypes = [ctypes.c_void_p]
                    L.mbake_ao.restype = None
                    L.mbake_ao.argtypes = [ctypes.c_void_p, ctypes.c_int, _FP, _FP, _FP, _IP, _UIP, ctypes.c_int,
                                           ctypes.c_float, ctypes.c_int, _FP, ctypes.c_int]
                    L.mbake_bevel.restype = None
                    L.mbake_bevel.argtypes = [ctypes.c_void_p, ctypes.c_int, _FP, _FP, _FP, _FP, _UIP, ctypes.c_int,
                                              _FP, ctypes.c_int]
                    _L[0] = L
            except AttributeError:
                pass
    return _L[0] or None


def _threads():
    return max(1, min(64, os.cpu_count() or 1))


def _c(a, dt=np.float32):
    return np.ascontiguousarray(a, dt)


def _ptr(a, t=_FP):
    return a.ctypes.data_as(t)


# ---------------------------------------------------------------------------------------------------------------------
# colour
# ---------------------------------------------------------------------------------------------------------------------

def srgb_to_lin(c):
    c = np.asarray(c, np.float32)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4).astype(np.float32)


def lin_to_srgb(c):
    c = np.clip(np.asarray(c, np.float32), 0.0, None)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1.0 / 2.4) - 0.055).astype(np.float32)


LINEAR_SPACES = {'Non-Color', 'Linear', 'Linear Rec.709', 'Linear CIE-XYZ D65', 'Raw', 'Generic Data', 'Scene Linear'}


class Images:
    """Each image's pixels once, linear float (Cycles converts the image into the scene's linear space on load)."""

    def __init__(self):
        self.d = {}

    def get(self, img):
        k = img.name
        if k in self.d:
            return self.d[k]
        w, h = img.size
        if w <= 0 or h <= 0:
            raise Unsupported(f'image {img.name} has no pixels')
        ch = img.channels
        px = np.empty(w * h * ch, np.float32)
        img.pixels.foreach_get(px)
        px = px.reshape(h * w, ch)
        if ch < 4:
            px = np.concatenate([px, np.ones((h * w, 4 - ch), np.float32)], 1) if ch >= 3 else \
                np.concatenate([np.repeat(px[:, :1], 3, 1), np.ones((h * w, 1), np.float32)], 1)
        cs = img.colorspace_settings.name
        if cs == 'sRGB' and not img.is_float:
            px[:, :3] = srgb_to_lin(px[:, :3])
        elif cs == 'sRGB' and img.is_float:
            pass                                    # (a float image is stored linear already)
        elif cs not in LINEAR_SPACES:
            raise Unsupported(f'image colour space {cs}')
        self.d[k] = (_c(px), w, h)
        return self.d[k]


# ---------------------------------------------------------------------------------------------------------------------
# the low's texels
# ---------------------------------------------------------------------------------------------------------------------

class Geo:
    """Every covered texel of the low's UVs (res x res): its triangle, point, normals, UVs ... (world and object)."""

    def __init__(self, context, low, res):
        import bmesh
        from . import bake_maps as bm_
        L = lib()
        dg = context.evaluated_depsgraph_get()
        src = bm_._lc_full(low, dg) if hasattr(bm_, '_lc_full') else low.evaluated_get(dg)
        me = bpy.data.meshes.new_from_object(src, depsgraph=dg)
        try:
            if any(len(p.vertices) > 4 for p in me.polygons):
                b = bmesh.new()
                b.from_mesh(me)
                bmesh.ops.triangulate(b, faces=[f for f in b.faces if len(f.verts) > 4], quad_method='BEAUTY',
                                      ngon_method='BEAUTY')
                b.to_mesh(me)
                b.free()
            uvl = me.uv_layers.active
            if uvl is None:
                raise Unsupported('no UVs')
            self.bake_uv = uvl.name
            rend = next((u for u in me.uv_layers if u.active_render), uvl)
            self.render_uv = rend.name
            me.calc_tangents(uvmap=uvl.name)
            me.calc_loop_triangles()
            nt = len(me.loop_triangles)
            lo = np.empty(nt * 3, np.int64)
            me.loop_triangles.foreach_get('loops', lo)
            vi = np.empty(nt * 3, np.int64)
            me.loop_triangles.foreach_get('vertices', vi)
            pi = np.empty(nt, np.int64)
            me.loop_triangles.foreach_get('polygon_index', pi)
            mi = np.zeros(len(me.polygons), np.int64)
            if len(me.polygons):
                me.polygons.foreach_get('material_index', mi)
            sm = np.ones(len(me.polygons), bool)
            if len(me.polygons):
                me.polygons.foreach_get('use_smooth', sm)
            co = np.empty(len(me.vertices) * 3, np.float32)
            me.vertices.foreach_get('co', co)
            co = co.reshape(-1, 3)
            uvs = {}
            for u in me.uv_layers:
                a = np.empty(len(me.loops) * 2, np.float32)
                u.data.foreach_get('uv', a)
                uvs[u.name] = a.reshape(-1, 2)
            tan = np.empty(len(me.loops) * 3, np.float32)
            me.loops.foreach_get('tangent', tan)
            sgn = np.empty(len(me.loops), np.float32)
            me.loops.foreach_get('bitangent_sign', sgn)
            cn = fast_bake._corner_normals(me)
            # the texels
            luv = _c(uvs[uvl.name][lo])
            np_ = res * res
            ptri = np.empty(np_, np.int32)
            pbar = np.empty(np_ * 3, np.float32)
            mask = np.zeros(np_, np.uint8)
            L.mbake_raster(int(nt), _ptr(luv), int(res), int(res), _ptr(ptri, _IP), _ptr(pbar), _ptr(mask, _UP))
            self.mask = mask
            self.idx = np.nonzero(mask)[0]
            t = ptri[self.idx].astype(np.int64)
            w = pbar.reshape(-1, 3)[self.idx]
            self.tri = t
            self.mat = mi[pi[t]]
            self.n = len(t)
            self.res = res
            c3 = t[:, None] * 3 + np.arange(3)[None, :]          # (n, 3) corners
            L_ = lo[c3]
            V_ = vi[c3]

            def lerp(a):                                         # a per corner -> per texel
                return np.einsum('nk,nkc->nc', w, a) if a.ndim == 3 else (w * a).sum(1)
            self._w, self._L, self._V, self._lerp = w, L_, V_, lerp
            self.Po = lerp(co[V_]).astype(np.float32)
            P0, P1, P2 = co[vi[t * 3]], co[vi[t * 3 + 1]], co[vi[t * 3 + 2]]
            ng = np.cross(P1 - P0, P2 - P0)
            ng /= np.maximum(np.linalg.norm(ng, axis=1, keepdims=True), 1e-20)
            self.Ngo = ng.astype(np.float32)
            nso = lerp(cn[L_])
            flat = ~sm[pi[t]]
            nso[flat] = ng[flat]
            self.No = _unit(nso)
            # world
            M = np.array(low.matrix_world, np.float64)
            self.M = M
            R = M[:3, :3]
            self.R = R
            self.Rn = np.linalg.inv(R).T
            self.P = (self.Po @ R.T + M[:3, 3]).astype(np.float32)
            self.N = _unit(self.No @ self.Rn.T)
            self.Ng = _unit(self.Ngo @ self.Rn.T)
            self.T = _unit(lerp(tan.reshape(-1, 3)[L_]) @ R.T)
            self.S = np.where(lerp(sgn[L_]) < 0, -1.0, 1.0).astype(np.float32)
            self.uv = {k: lerp(a[L_]).astype(np.float32) for k, a in uvs.items()}
            # one texel step in u / v, in world space (the bump's offsets): the triangle's dP / dUV
            U0, U1, U2 = (uvs[uvl.name][lo[t * 3 + k]] for k in range(3))
            e1, e2 = P1 - P0, P2 - P0
            d1, d2 = U1 - U0, U2 - U0
            det = d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]
            det = np.where(np.abs(det) < 1e-20, 1e-20, det)
            dPdu = (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) / det[:, None]
            dPdv = (e2 * d1[:, 0:1] - e1 * d2[:, 0:1]) / det[:, None]
            self.dPdu_o, self.dPdv_o = dPdu.astype(np.float32), dPdv.astype(np.float32)
            # generated coordinates: the mesh's texture space (auto: its bounds)
            d = low.data
            try:
                loc = np.array(d.texspace_location, np.float32)
                size = np.array(d.texspace_size, np.float32)
            except AttributeError:
                lo_, hi_ = co.min(0), co.max(0)
                loc, size = (lo_ + hi_) / 2, (hi_ - lo_) / 2
            size = np.where(np.abs(size) < 1e-9, 1e-9, size)
            self.tex_loc, self.tex_size = loc, size
            self.me_co, self.me_tris = co, vi.reshape(-1, 3)
            self.me_cn = cn[lo].reshape(-1, 3, 3)
            self._attr_cache = {}
            self._me = me
            self._lo, self._vi, self._pi = lo, vi, pi
            self.attrs = self._read_attrs(me)
        finally:
            bpy.data.meshes.remove(me)
            self._me = None

    def _read_attrs(self, me):
        out = {}
        for a in me.attributes:
            if a.name.startswith('.'):
                continue
            dom, dt = a.domain, a.data_type
            if dt in {'FLOAT', 'INT', 'BOOLEAN', 'INT8'}:
                k, key = 1, 'value'
            elif dt in {'FLOAT_VECTOR'}:
                k, key = 3, 'vector'
            elif dt in {'FLOAT_COLOR', 'BYTE_COLOR'}:
                k, key = 4, 'color'
            elif dt == 'FLOAT2':
                k, key = 2, 'vector'
            else:
                continue
            ln = len(a.data)
            try:
                if dt == 'BOOLEAN':
                    arr = np.empty(ln, bool)
                    a.data.foreach_get('value', arr)
                    arr = arr.astype(np.float32)
                elif dt in {'INT', 'INT8'}:
                    arr = np.empty(ln, np.int64)
                    a.data.foreach_get('value', arr)
                    arr = arr.astype(np.float32)
                else:
                    arr = np.empty(ln * k, np.float32)
                    a.data.foreach_get(key, arr)
            except (AttributeError, RuntimeError, TypeError):
                continue
            arr = arr.reshape(ln, k) if k > 1 else arr.reshape(ln, 1)
            out[a.name] = (dom, dt, arr)
        return out

    def attr(self, name):
        """(n, 4) per texel (colour attrs rgba; vectors xyz + 1; floats f, f, f, 1) or None."""
        if name in self._attr_cache:
            return self._attr_cache[name]
        res = None
        if name in self.uv:
            u = self.uv[name]
            res = np.concatenate([u, np.zeros((self.n, 1), np.float32), np.ones((self.n, 1), np.float32)], 1)
        elif name in self.attrs:
            dom, dt, arr = self.attrs[name]
            if dom == 'POINT':
                per = self._lerp(arr[self._V])
            elif dom == 'CORNER':
                per = self._lerp(arr[self._L])
            elif dom == 'FACE':
                per = arr[self._pi[self.tri]]
            else:
                raise Unsupported(f'attribute {name} on {dom}')
            k = per.shape[1]
            if k == 1:
                res = np.concatenate([np.repeat(per, 3, 1), np.ones((self.n, 1), np.float32)], 1)
            elif k == 2:
                res = np.concatenate([per, np.zeros((self.n, 1), np.float32), np.ones((self.n, 1), np.float32)], 1)
            elif k == 3:
                res = np.concatenate([per, np.ones((self.n, 1), np.float32)], 1)
            else:
                res = per
                if dt == 'BYTE_COLOR':                # (stored sRGB, read linear by Cycles)
                    pass                              # (foreach_get 'color' gives linear already)
            res = res.astype(np.float32)
        self._attr_cache[name] = res
        return res

    def subset(self, sel):
        """A Geo of just the texels ``sel`` (a bool / index array)."""
        g = object.__new__(Geo)
        g.__dict__.update(self.__dict__)
        for k in ('idx', 'tri', 'mat', 'Po', 'Ngo', 'No', 'P', 'N', 'Ng', 'T', 'S', 'dPdu_o', 'dPdv_o', '_w', '_L',
                  '_V'):
            setattr(g, k, getattr(self, k)[sel])
        g.uv = {k: a[sel] for k, a in self.uv.items()}
        g.n = len(g.idx)
        g._attr_cache = {k: (a[sel] if a is not None else None) for k, a in self._attr_cache.items()}
        w = g._w

        def lerp(a):
            return np.einsum('nk,nkc->nc', w, a) if a.ndim == 3 else (w * a).sum(1)
        g._lerp = lerp
        return g


def _unit(v):
    v = np.asarray(v, np.float32)
    return (v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-20)).astype(np.float32)


class Shift:
    """The texels moved a little along the surface (the Bump node's offset points): positions and the bake UVs
    moved, the normals kept."""

    def __init__(self, g, du, dv):
        self.base = g
        dPo = g.dPdu_o * du + g.dPdv_o * dv
        self.Po = (g.Po + dPo).astype(np.float32)
        self.P = (self.Po @ g.R.T + g.M[:3, 3]).astype(np.float32)
        self.uv = {k: (a + np.array([du, dv], np.float32)) if k == g.bake_uv else a for k, a in g.uv.items()}

    def __getattr__(self, k):
        return getattr(self.base, k)


# ---------------------------------------------------------------------------------------------------------------------
# values: float (n,) or scalar; vector / colour (n, 3) or (3,)
# ---------------------------------------------------------------------------------------------------------------------

def as_float(v, typ):
    if typ in ('VALUE', 'INT', 'BOOLEAN'):
        return v
    v = np.asarray(v, np.float32)
    if typ == 'RGBA':
        return v @ LUMA
    return v.mean(-1)


def as_vec(v, typ):
    if typ in ('VALUE', 'INT', 'BOOLEAN'):
        v = np.asarray(v, np.float32)
        return np.stack([v, v, v], -1) if v.ndim else np.array([v, v, v], np.float32)
    return v


def convert(v, frm, to):
    if to in ('VALUE', 'INT', 'BOOLEAN'):
        return as_float(v, frm)
    if to in ('RGBA', 'VECTOR'):
        return as_vec(v, frm)
    return v


def _sock_default(s):
    v = s.default_value
    if s.type in ('RGBA',):
        return np.array(v[:3], np.float32)
    if s.type == 'VECTOR':
        return np.array(v[:3], np.float32)
    if s.type == 'BOOLEAN':
        return 1.0 if v else 0.0
    return float(v)


def sat(x):
    return np.clip(x, 0.0, 1.0)


def _dot(a, b):
    return (np.asarray(a) * np.asarray(b)).sum(-1)


def _safe_div(a, b):
    a, b = np.asarray(a, np.float32), np.asarray(b, np.float32)
    with np.errstate(divide='ignore', invalid='ignore'):
        r = np.where(b != 0, a / np.where(b != 0, b, 1), 0.0)
    return r.astype(np.float32) if r.ndim else float(r)


def _fmod(a, b):
    a, b = np.asarray(a, np.float32), np.asarray(b, np.float32)
    with np.errstate(divide='ignore', invalid='ignore'):
        r = np.where(b != 0, np.fmod(a, np.where(b != 0, b, 1)), 0.0)
    return r


def _floored_mod(a, b):
    a, b = np.asarray(a, np.float32), np.asarray(b, np.float32)
    with np.errstate(divide='ignore', invalid='ignore'):
        r = np.where(b != 0, a - np.floor(a / np.where(b != 0, b, 1)) * b, 0.0)
    return r


def _wrap(v, mx, mn):
    rng = mx - mn
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.where(rng != 0, v - rng * np.floor((v - mn) / np.where(rng != 0, rng, 1)), mn)


def _pingpong(a, b):
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.where(b != 0, np.abs(np.fmod(a - b, 2 * np.where(b != 0, b, 1)) - b) if False else
                        np.abs(_floored_mod(a - b, 2 * b) - b), 0.0)


def _pow(a, b):
    a, b = np.asarray(a, np.float32), np.asarray(b, np.float32)
    with np.errstate(divide='ignore', invalid='ignore', over='ignore'):
        r = np.where(a >= 0, np.power(np.abs(a), b),
                     np.where(np.floor(b) == b, np.power(np.abs(a), b) * np.where(np.fmod(np.abs(b), 2) == 1, -1, 1),
                              0.0))
    return np.nan_to_num(r, nan=0.0, posinf=0.0, neginf=0.0)


def _smin(a, b, c):
    a, b, c = np.asarray(a, np.float32), np.asarray(b, np.float32), np.asarray(c, np.float32)
    with np.errstate(divide='ignore', invalid='ignore'):
        h = np.maximum(c - np.abs(a - b), 0.0) / np.where(c != 0, c, 1)
    r = np.minimum(a, b) - h * h * h * c * (1.0 / 6.0)
    return np.where(c != 0, r, np.minimum(a, b))


MATH = {
    'ADD': lambda a, b, c: a + b,
    'SUBTRACT': lambda a, b, c: a - b,
    'MULTIPLY': lambda a, b, c: a * b,
    'DIVIDE': lambda a, b, c: _safe_div(a, b),
    'MULTIPLY_ADD': lambda a, b, c: a * b + c,
    'POWER': lambda a, b, c: _pow(a, b),
    'LOGARITHM': lambda a, b, c: np.where((np.asarray(a) > 0) & (np.asarray(b) > 0),
                                          np.log(np.maximum(a, 1e-30)) / np.log(np.maximum(b, 1e-30)), 0.0),
    'SQRT': lambda a, b, c: np.where(np.asarray(a) > 0, np.sqrt(np.maximum(a, 0)), 0.0),
    'INVERSE_SQRT': lambda a, b, c: np.where(np.asarray(a) > 0, 1 / np.sqrt(np.maximum(a, 1e-30)), 0.0),
    'ABSOLUTE': lambda a, b, c: np.abs(a),
    'EXPONENT': lambda a, b, c: np.exp(a),
    'MINIMUM': lambda a, b, c: np.minimum(a, b),
    'MAXIMUM': lambda a, b, c: np.maximum(a, b),
    'LESS_THAN': lambda a, b, c: (np.asarray(a) < b) * 1.0,
    'GREATER_THAN': lambda a, b, c: (np.asarray(a) > b) * 1.0,
    'SIGN': lambda a, b, c: np.sign(a),
    'COMPARE': lambda a, b, c: (np.abs(np.asarray(a) - b) <= np.maximum(c, 1e-5)) * 1.0,
    'SMOOTH_MIN': lambda a, b, c: _smin(a, b, c),
    'SMOOTH_MAX': lambda a, b, c: -_smin(-np.asarray(a), -np.asarray(b), c),
    'ROUND': lambda a, b, c: np.floor(np.asarray(a) + 0.5),
    'FLOOR': lambda a, b, c: np.floor(a),
    'CEIL': lambda a, b, c: np.ceil(a),
    'TRUNC': lambda a, b, c: np.trunc(a),
    'FRACT': lambda a, b, c: np.asarray(a) - np.floor(a),
    'MODULO': lambda a, b, c: _fmod(a, b),
    'FLOORED_MODULO': lambda a, b, c: _floored_mod(a, b),
    'WRAP': lambda a, b, c: _wrap(a, b, c),
    'SNAPPING': lambda a, b, c: np.where(np.asarray(b) != 0, np.floor(_safe_div(a, b)) * b, 0.0),
    'PINGPONG': lambda a, b, c: _pingpong(a, b),
    'SINE': lambda a, b, c: np.sin(a),
    'COSINE': lambda a, b, c: np.cos(a),
    'TANGENT': lambda a, b, c: np.tan(a),
    'SINH': lambda a, b, c: np.sinh(a),
    'COSH': lambda a, b, c: np.cosh(a),
    'TANH': lambda a, b, c: np.tanh(a),
    'ARCSINE': lambda a, b, c: np.where(np.abs(a) <= 1, np.arcsin(np.clip(a, -1, 1)), 0.0),
    'ARCCOSINE': lambda a, b, c: np.where(np.abs(a) <= 1, np.arccos(np.clip(a, -1, 1)), 0.0),
    'ARCTANGENT': lambda a, b, c: np.arctan(a),
    'ARCTAN2': lambda a, b, c: np.arctan2(a, b),
    'RADIANS': lambda a, b, c: np.asarray(a) * (math.pi / 180.0),
    'DEGREES': lambda a, b, c: np.asarray(a) * (180.0 / math.pi),
}


def _rgb_to_hsv(c):
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    d = mx - mn
    v = mx
    s = np.where(mx != 0, d / np.where(mx != 0, mx, 1), 0.0)
    dd = np.where(d != 0, d, 1)
    cr, cg, cb = (mx - r) / dd, (mx - g) / dd, (mx - b) / dd
    h = np.where(r == mx, cb - cg, np.where(g == mx, 2.0 + cr - cb, 4.0 + cg - cr)) / 6.0
    h = np.where(h < 0, h + 1.0, h)
    h = np.where(s != 0, h, 0.0)
    return np.stack([h, s, v], -1)


def _hsv_to_rgb(c):
    h, s, v = c[..., 0], c[..., 1], c[..., 2]
    h = (h - np.floor(h)) * 6.0
    i = np.floor(h)
    f = h - i
    p = v * (1 - s)
    q = v * (1 - s * f)
    t = v * (1 - s * (1 - f))
    i = i.astype(np.int64) % 6
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    out = np.stack([r, g, b], -1)
    return np.where((s == 0)[..., None], np.stack([v, v, v], -1), out)


def _blend(kind, t, a, b):
    """Cycles' svm_mix (t already clamped where it asks)."""
    t = np.asarray(t, np.float32)
    t3 = t[..., None] if t.ndim else t
    tm = 1.0 - t3
    a = np.asarray(a, np.float32)
    b = np.asarray(b, np.float32)
    if kind == 'MIX':
        return tm * a + t3 * b
    if kind == 'ADD':
        return a + t3 * b
    if kind == 'MULTIPLY':
        return a * (tm + t3 * b)
    if kind == 'SUBTRACT':
        return a - t3 * b
    if kind == 'SCREEN':
        return 1.0 - (tm + t3 * (1.0 - b)) * (1.0 - a)
    if kind == 'DIVIDE':
        with np.errstate(divide='ignore', invalid='ignore'):
            return np.where(b != 0, tm * a + t3 * a / np.where(b != 0, b, 1), a)
    if kind == 'DIFFERENCE':
        return tm * a + t3 * np.abs(a - b)
    if kind == 'EXCLUSION':
        return np.maximum(tm * a + t3 * (a + b - 2 * a * b), 0.0)
    if kind == 'DARKEN':
        return tm * a + t3 * np.minimum(a, b)
    if kind == 'LIGHTEN':
        return tm * a + t3 * np.maximum(a, b)
    if kind == 'OVERLAY':
        return np.where(a < 0.5, a * (tm + 2 * t3 * b), 1.0 - (tm + 2 * t3 * (1.0 - b)) * (1.0 - a))
    if kind == 'SOFT_LIGHT':
        scr = 1.0 - (1.0 - b) * (1.0 - a)
        return tm * a + t3 * ((1.0 - a) * b * a + a * scr)
    if kind == 'LINEAR_LIGHT':
        return a + t3 * (2.0 * b - 1.0)
    if kind == 'DODGE':
        with np.errstate(divide='ignore', invalid='ignore'):
            tmp = 1.0 - t3 * b
            r = np.where(a != 0, np.where(tmp <= 0, 1.0, np.minimum(a / np.where(tmp != 0, tmp, 1), 1.0)), a)
        return r
    if kind == 'BURN':
        with np.errstate(divide='ignore', invalid='ignore'):
            tmp = tm + t3 * b
            r = np.where(tmp <= 0, 0.0, np.clip(1.0 - (1.0 - a) / np.where(tmp != 0, tmp, 1), 0.0, 1.0))
        return r
    if kind in ('HUE', 'SATURATION', 'VALUE', 'COLOR'):
        ha, hb = _rgb_to_hsv(np.broadcast_to(a, np.broadcast(a, b).shape)), _rgb_to_hsv(
            np.broadcast_to(b, np.broadcast(a, b).shape))
        if kind == 'VALUE':
            o = ha.copy()
            o[..., 2] = hb[..., 2]
            return tm * a + t3 * _hsv_to_rgb(o)
        if kind == 'SATURATION':
            o = ha.copy()
            o[..., 1] = np.where(ha[..., 1] != 0, hb[..., 1], ha[..., 1])
            return tm * a + t3 * _hsv_to_rgb(o)
        if kind == 'HUE':
            o = ha.copy()
            o[..., 0] = hb[..., 0]
            return np.where((hb[..., 1] != 0)[..., None], tm * a + t3 * _hsv_to_rgb(o), a)
        o = ha.copy()
        o[..., 0], o[..., 1] = hb[..., 0], hb[..., 1]
        return np.where((hb[..., 1] != 0)[..., None], tm * a + t3 * _hsv_to_rgb(o), a)
    raise Unsupported(f'mix {kind}')


def _euler_matrix(r):
    r = np.asarray(r, np.float64)
    if r.ndim != 1:
        raise Unsupported('a linked Mapping rotation')
    cx, cy, cz = np.cos(r)
    sx, sy, sz = np.sin(r)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return (Rz @ Ry @ Rx).astype(np.float32)


# ---------------------------------------------------------------------------------------------------------------------
# the evaluator
# ---------------------------------------------------------------------------------------------------------------------

class Eval:
    """Values of a material's sockets over the texels ``g`` (a Geo, or a Shift of one for a Bump's offsets)."""

    def __init__(self, ob, g, images, scene, local, seeds, ray_quality=1.0, parent=None):
        self.ob, self.g, self.images, self.scene, self.local, self.seeds = ob, g, images, scene, local, seeds
        self.memo = {}
        self.ray_quality = ray_quality
        self.parent = parent
        self.shifts = None

    # -- links ---------------------------------------------------------------------------------------------------
    def inp(self, node, key, path):
        s = node.inputs[key] if not isinstance(key, bpy.types.NodeSocket) else key
        return self.sock_in(s, path)

    def sock_in(self, s, path, want=None):
        typ = want or s.type
        lk = next((lk for lk in s.links if not lk.is_muted), None) if s.is_linked else None
        if lk is None:
            return self.implicit(s, path)
        if not lk.is_valid:
            raise Unsupported('an invalid link')
        fs, fn = lk.from_socket, lk.from_node
        v, ftyp = self.out(fn, fs, path)
        return convert(v, ftyp, typ)

    def implicit(self, s, path):
        """An unlinked input: its value, or the implicit one Cycles gives (texture vectors, normals)."""
        node = s.node
        if s.type == 'VECTOR' and getattr(s, 'hide_value', False):
            if s.name == 'Normal' or s.name == 'Coat Normal':
                return self.g.N
            if s.name == 'Tangent':
                raise Unsupported('an implicit tangent')
            if node.type == 'TEX_IMAGE':
                return self._uv(self.g.render_uv)
            if node.type.startswith('TEX_'):
                return self._generated()
            return np.zeros(3, np.float32)
        if s.type == 'SHADER':
            return None
        return _sock_default(s)

    def out(self, node, sock, path):
        """(value, socket type) of ``node``'s output ``sock``."""
        key = (path, node.name, sock.identifier, id(node.id_data))
        if key in self.memo:
            return self.memo[key]
        if node.mute:
            r = self._muted(node, sock, path)
        else:
            r = (self._node(node, sock, path), sock.type)
        self.memo[key] = r
        return r

    def _muted(self, node, sock, path):
        for lk in node.internal_links:
            if lk.to_socket == sock:
                return self.sock_in(lk.from_socket, path, sock.type), sock.type
        return (np.zeros(3, np.float32) if sock.type in ('RGBA', 'VECTOR') else 0.0), sock.type

    # -- geometry ------------------------------------------------------------------------------------------------
    def _uv(self, name):
        u = self.g.uv.get(name) if name else self.g.uv.get(self.g.render_uv)
        if u is None:
            raise Unsupported(f'UV map {name}')
        return np.concatenate([u, np.zeros((len(u), 1), np.float32)], 1)

    def _generated(self):
        g = self.g
        return ((g.Po - g.tex_loc + g.tex_size) / (2 * g.tex_size)).astype(np.float32)

    def _to_world(self, v, kind):
        g = self.g
        if kind == 'POINT':
            return (v @ g.R.T + g.M[:3, 3]).astype(np.float32)
        if kind == 'NORMAL':
            return _unit(v @ g.Rn.T)
        return (v @ g.R.T).astype(np.float32)

    # -- nodes ---------------------------------------------------------------------------------------------------
    def _node(self, n, s, path):
        t = n.type
        f = getattr(self, 'n_' + t, None)
        if f is None:
            raise Unsupported(f'node {n.bl_idname}')
        return f(n, s, path)

    def n_REROUTE(self, n, s, path):
        return self.sock_in(n.inputs[0], path, s.type)

    def n_VALUE(self, n, s, path):
        return float(n.outputs[0].default_value)

    def n_RGB(self, n, s, path):
        return np.array(n.outputs[0].default_value[:3], np.float32)

    def n_GROUP(self, n, s, path):
        nt = n.node_tree
        if nt is None:
            return 0.0
        go = next((x for x in nt.nodes if x.type == 'GROUP_OUTPUT' and x.is_active_output), None) or \
            next((x for x in nt.nodes if x.type == 'GROUP_OUTPUT'), None)
        if go is None:
            return 0.0
        ins = next((x for x in go.inputs if x.identifier == s.identifier), None)
        if ins is None:
            return 0.0
        return self.sock_in(ins, path + (n.name,), s.type)

    def n_GROUP_INPUT(self, n, s, path):
        if not path:
            raise Unsupported('a group input outside a group')
        # the group node in the parent path
        parent_path = path[:-1]
        gnode = self._group_node(parent_path, path[-1])
        si = next((x for x in gnode.inputs if x.identifier == s.identifier), None)
        if si is None:
            return 0.0
        return self.sock_in(si, parent_path, s.type)

    def _group_node(self, parent_path, name):
        nt = self.root_tree
        for nm in parent_path:
            nt = nt.nodes[nm].node_tree
        return nt.nodes[name]

    def n_MATH(self, n, s, path):
        op = n.operation
        if op not in MATH:
            raise Unsupported(f'math {op}')
        a = self.inp(n, 0, path)
        b = self.inp(n, 1, path)
        c = self.inp(n, 2, path) if len(n.inputs) > 2 else 0.0
        with np.errstate(all='ignore'):
            r = MATH[op](np.asarray(a, np.float32) if not np.isscalar(a) else a,
                         np.asarray(b, np.float32) if not np.isscalar(b) else b, c)
        if n.use_clamp:
            r = sat(r)
        r = np.asarray(r, np.float32)
        return float(r) if r.ndim == 0 else r

    def n_VECT_MATH(self, n, s, path):
        op = n.operation
        a = np.asarray(self.inp(n, 0, path), np.float32)
        b = np.asarray(self.inp(n, 1, path), np.float32)
        val = None
        vec = None
        with np.errstate(all='ignore'):
            if op == 'ADD':
                vec = a + b
            elif op == 'SUBTRACT':
                vec = a - b
            elif op == 'MULTIPLY':
                vec = a * b
            elif op == 'DIVIDE':
                vec = np.where(b != 0, a / np.where(b != 0, b, 1), 0.0)
            elif op == 'MULTIPLY_ADD':
                vec = a * b + np.asarray(self.inp(n, 2, path), np.float32)
            elif op == 'CROSS_PRODUCT':
                vec = np.cross(*np.broadcast_arrays(a, b))
            elif op == 'PROJECT':
                bb = _dot(b, b)
                vec = np.where(np.asarray(bb)[..., None] != 0, (_dot(a, b) / np.where(bb != 0, bb, 1))[..., None] * b,
                               0.0) if np.ndim(bb) else (b * (_dot(a, b) / bb) if bb != 0 else np.zeros(3, np.float32))
            elif op == 'REFLECT':
                nb = _unit(b)
                vec = a - 2 * _dot(nb, a)[..., None] * nb if np.ndim(_dot(nb, a)) else a - 2 * _dot(nb, a) * nb
            elif op == 'DOT_PRODUCT':
                val = _dot(a, b)
            elif op == 'DISTANCE':
                val = np.linalg.norm(a - b, axis=-1)
            elif op == 'LENGTH':
                val = np.linalg.norm(a, axis=-1)
            elif op == 'SCALE':
                sc = self.inp(n, 'Scale', path)
                sc = np.asarray(sc, np.float32)
                vec = a * (sc[..., None] if sc.ndim else sc)
            elif op == 'NORMALIZE':
                vec = _unit(a)
            elif op == 'ABSOLUTE':
                vec = np.abs(a)
            elif op == 'MINIMUM':
                vec = np.minimum(a, b)
            elif op == 'MAXIMUM':
                vec = np.maximum(a, b)
            elif op == 'FLOOR':
                vec = np.floor(a)
            elif op == 'CEIL':
                vec = np.ceil(a)
            elif op == 'FRACT':
                vec = a - np.floor(a)
            elif op == 'MODULO':
                vec = _fmod(a, b)
            elif op == 'SNAP':
                vec = np.where(b != 0, np.floor(np.where(b != 0, a / np.where(b != 0, b, 1), 0)) * b, 0.0)
            elif op == 'SINE':
                vec = np.sin(a)
            elif op == 'COSINE':
                vec = np.cos(a)
            elif op == 'TANGENT':
                vec = np.tan(a)
            else:
                raise Unsupported(f'vector math {op}')
        if s.type == 'VALUE':
            if val is None:
                return 0.0
            val = np.asarray(val, np.float32)
            return float(val) if val.ndim == 0 else val
        if vec is None:
            return np.zeros(3, np.float32)
        return np.asarray(vec, np.float32)

    def _in_id(self, n, ident):
        return next(x for x in n.inputs if x.identifier == ident)

    def n_MIX(self, n, s, path):
        dt = n.data_type
        if dt == 'FLOAT':
            f = self.sock_in(self._in_id(n, 'Factor_Float'), path)
            if n.clamp_factor:
                f = sat(f)
            a = self.sock_in(self._in_id(n, 'A_Float'), path)
            b = self.sock_in(self._in_id(n, 'B_Float'), path)
            r = (1 - np.asarray(f, np.float32)) * a + np.asarray(f, np.float32) * b
            r = np.asarray(r, np.float32)
            return float(r) if r.ndim == 0 else r
        if dt == 'VECTOR':
            uni = getattr(n, 'factor_mode', 'UNIFORM') == 'UNIFORM'
            f = self.sock_in(self._in_id(n, 'Factor_Float' if uni else 'Factor_Vector'), path)
            if n.clamp_factor:
                f = sat(f)
            a = np.asarray(self.sock_in(self._in_id(n, 'A_Vector'), path), np.float32)
            b = np.asarray(self.sock_in(self._in_id(n, 'B_Vector'), path), np.float32)
            f = np.asarray(f, np.float32)
            if uni and f.ndim:
                f = f[..., None]
            return (1 - f) * a + f * b
        if dt == 'RGBA':
            f = self.sock_in(self._in_id(n, 'Factor_Float'), path)
            if n.clamp_factor:
                f = sat(f)
            a = self.sock_in(self._in_id(n, 'A_Color'), path)
            b = self.sock_in(self._in_id(n, 'B_Color'), path)
            r = _blend(n.blend_type, f, a, b)
            if n.clamp_result:
                r = sat(r)
            return np.asarray(r, np.float32)
        raise Unsupported(f'mix {dt}')

    def n_MIX_RGB(self, n, s, path):
        f = sat(self.inp(n, 'Fac', path))
        r = _blend(n.blend_type, f, self.inp(n, 'Color1', path), self.inp(n, 'Color2', path))
        if n.use_clamp:
            r = sat(r)
        return np.asarray(r, np.float32)

    def n_MAP_RANGE(self, n, s, path):
        if n.data_type != 'FLOAT':
            raise Unsupported('vector map range')
        v = np.asarray(self.inp(n, 'Value', path), np.float32)
        fmn, fmx = self.inp(n, 1, path), self.inp(n, 2, path)
        tmn, tmx = self.inp(n, 3, path), self.inp(n, 4, path)
        it = n.interpolation_type
        d = np.asarray(fmx, np.float32) - fmn
        with np.errstate(all='ignore'):
            fac = np.where(d != 0, (v - fmn) / np.where(d != 0, d, 1), 0.0)
        if it == 'LINEAR':
            pass
        elif it == 'STEPPED':
            st = np.asarray(self.inp(n, 5, path), np.float32)
            fac = np.where(st > 0, np.floor(fac * (st + 1)) / np.where(st > 0, st, 1), 0.0)
        elif it == 'SMOOTHSTEP':
            fac = np.where(fac <= 0, 0.0, np.where(fac >= 1, 1.0, fac * fac * (3 - 2 * fac)))
        elif it == 'SMOOTHERSTEP':
            fac = np.where(fac <= 0, 0.0, np.where(fac >= 1, 1.0, fac * fac * fac * (fac * (fac * 6 - 15) + 10)))
        r = tmn + fac * (np.asarray(tmx, np.float32) - tmn)
        if n.clamp and it in ('LINEAR', 'STEPPED'):
            lo, hi = np.minimum(tmn, tmx), np.maximum(tmn, tmx)
            r = np.clip(r, lo, hi)
        r = np.asarray(r, np.float32)
        return float(r) if r.ndim == 0 else r

    def n_CLAMP(self, n, s, path):
        v, a, b = self.inp(n, 'Value', path), self.inp(n, 'Min', path), self.inp(n, 'Max', path)
        if n.clamp_type == 'RANGE':
            lo, hi = np.minimum(a, b), np.maximum(a, b)
        else:
            lo, hi = a, b
        r = np.minimum(np.maximum(v, lo), hi)
        r = np.asarray(r, np.float32)
        return float(r) if r.ndim == 0 else r

    def n_HUE_SAT(self, n, s, path):
        hue = np.asarray(self.inp(n, 'Hue', path), np.float32)
        satv = np.asarray(self.inp(n, 'Saturation', path), np.float32)
        val = np.asarray(self.inp(n, 'Value', path), np.float32)
        fac = np.asarray(self.inp(n, 'Fac', path), np.float32)
        c = np.asarray(self.inp(n, 'Color', path), np.float32)
        hsv = _rgb_to_hsv(c)
        h = hsv[..., 0] + hue + 0.5
        h = h - np.floor(h)
        sv = sat(hsv[..., 1] * satv)
        vv = hsv[..., 2] * val
        out = _hsv_to_rgb(np.stack(np.broadcast_arrays(h, sv, vv), -1))
        f3 = fac[..., None] if fac.ndim else fac
        r = f3 * out + (1 - f3) * c
        return np.maximum(r, 0.0).astype(np.float32)

    def n_BRIGHTCONTRAST(self, n, s, path):
        c = np.asarray(self.inp(n, 'Color', path), np.float32)
        br = np.asarray(self.inp(n, 'Bright', path), np.float32)
        co = np.asarray(self.inp(n, 'Contrast', path), np.float32)
        a = 1 + co
        b = br - co * 0.5
        if a.ndim:
            a, b = a[..., None], b[..., None]
        return np.maximum(a * c + b, 0.0).astype(np.float32)

    def n_INVERT(self, n, s, path):
        f = np.asarray(self.inp(n, 'Fac', path), np.float32)
        c = np.asarray(self.inp(n, 'Color', path), np.float32)
        f3 = f[..., None] if f.ndim else f
        return ((1 - f3) * c + f3 * (1 - c)).astype(np.float32)

    def n_GAMMA(self, n, s, path):
        c = np.asarray(self.inp(n, 'Color', path), np.float32)
        g = np.asarray(self.inp(n, 'Gamma', path), np.float32)
        g3 = g[..., None] if g.ndim else g
        with np.errstate(all='ignore'):
            return np.where(c > 0, np.power(np.maximum(c, 1e-30), g3), c).astype(np.float32)

    def n_RGBTOBW(self, n, s, path):
        return as_float(np.asarray(self.inp(n, 'Color', path), np.float32), 'RGBA')

    def n_VALTORGB(self, n, s, path):
        f = np.asarray(self.inp(n, 'Fac', path), np.float32)
        ramp = n.color_ramp
        key = ('ramp', id(n))
        tab = self.memo.get(key)
        if tab is None:
            tab = np.array([ramp.evaluate(i / 255.0) for i in range(256)], np.float32)
            self.memo[key] = tab
        x = sat(f) * 255.0
        if ramp.interpolation == 'CONSTANT':
            i = np.floor(x + 0.5).astype(np.int64) if False else np.clip(np.floor(x).astype(np.int64), 0, 255)
            v = tab[i]
        else:
            i = np.clip(np.floor(x).astype(np.int64), 0, 255)
            t = x - i
            j = np.minimum(i + 1, 255)
            t = np.asarray(t)
            v = tab[i] * (1 - t[..., None]) + tab[j] * t[..., None] if t.ndim else tab[i] * (1 - t) + tab[j] * t
        if s.identifier == 'Alpha':
            return np.asarray(v[..., 3], np.float32)
        return np.asarray(v[..., :3], np.float32)

    def n_SEPXYZ(self, n, s, path):
        v = np.asarray(self.inp(n, 0, path), np.float32)
        i = {'X': 0, 'Y': 1, 'Z': 2}[s.identifier]
        r = v[..., i]
        return float(r) if np.ndim(r) == 0 else r

    def n_COMBXYZ(self, n, s, path):
        xs = [np.asarray(self.inp(n, k, path), np.float32) for k in range(3)]
        if all(x.ndim == 0 for x in xs):
            return np.array([float(x) for x in xs], np.float32)
        return np.stack(np.broadcast_arrays(*xs), -1).astype(np.float32)

    def n_SEPARATE_COLOR(self, n, s, path):
        c = np.asarray(self.inp(n, 0, path), np.float32)
        if n.mode == 'HSV':
            c = _rgb_to_hsv(c)
        elif n.mode != 'RGB':
            raise Unsupported('separate HSL')
        i = {'Red': 0, 'Green': 1, 'Blue': 2}[s.identifier]
        r = c[..., i]
        return float(r) if np.ndim(r) == 0 else r

    def n_COMBINE_COLOR(self, n, s, path):
        xs = [np.asarray(self.inp(n, k, path), np.float32) for k in range(3)]
        c = np.stack(np.broadcast_arrays(*xs), -1).astype(np.float32)
        if n.mode == 'HSV':
            c = _hsv_to_rgb(c)
        elif n.mode != 'RGB':
            raise Unsupported('combine HSL')
        return c

    def n_SEPRGB(self, n, s, path):
        c = np.asarray(self.inp(n, 0, path), np.float32)
        r = c[..., {'R': 0, 'G': 1, 'B': 2}[s.identifier]]
        return float(r) if np.ndim(r) == 0 else r

    def n_COMBRGB(self, n, s, path):
        return self.n_COMBXYZ(n, s, path)

    def n_TEX_COORD(self, n, s, path):
        k = s.identifier
        g = self.g
        if n.object is not None and k == 'Object' and n.object != self.ob:
            # (0.24.342 another object's space - e.g. a lasso Zone's projector, or the part a baking copy came from)
            Mo = np.array(n.object.matrix_world, np.float64)
            return ((g.P - Mo[:3, 3]) @ np.linalg.inv(Mo[:3, :3]).T).astype(np.float32)
        if k == 'Generated':
            return self._generated()
        if k == 'Normal':
            return g.No if not isinstance(g, Shift) else g.base.No
        if k == 'UV':
            return self._uv(g.render_uv)
        if k == 'Object':
            return g.Po
        raise Unsupported(f'texture coordinate {k}')

    def n_UVMAP(self, n, s, path):
        return self._uv(n.uv_map or self.g.render_uv)

    def n_NEW_GEOMETRY(self, n, s, path):
        k = s.identifier
        g = self.g
        if k == 'Position':
            return g.P
        if k == 'Normal':
            return g.N
        if k == 'True Normal':
            return g.Ng
        if k == 'Backfacing':
            return 0.0
        raise Unsupported(f'geometry {k}')

    def n_ATTRIBUTE(self, n, s, path):
        if n.attribute_type == 'OBJECT':
            v = self.ob.get(n.attribute_name)
            if v is None:
                v = getattr(self.ob, n.attribute_name, None)
            if v is None:
                return np.zeros(3, np.float32) if s.type in ('RGBA', 'VECTOR') else 0.0
            try:
                vv = [float(x) for x in v][:4]
            except TypeError:
                vv = [float(v)] * 3
            vv = (vv + [0.0, 0.0, 0.0])[:3] if len(vv) < 3 else vv
            a = np.array(vv[:3], np.float32)
            if s.identifier == 'Fac':
                return float(a.mean()) if len(set(vv[:3])) > 1 else float(a[0])
            if s.identifier == 'Alpha':
                return float(vv[3]) if len(vv) > 3 else 1.0
            return a
        if n.attribute_type != 'GEOMETRY':
            raise Unsupported('attribute ' + n.attribute_type)
        a = self.g.attr(n.attribute_name)
        if a is None:
            return np.zeros(3, np.float32) if s.type in ('RGBA', 'VECTOR') else 0.0
        if s.identifier == 'Fac':
            dom, dt, arr = self.g.attrs.get(n.attribute_name, (None, 'FLOAT_VECTOR', None))
            if dt in ('FLOAT', 'INT', 'BOOLEAN', 'INT8'):
                return a[:, 0]
            if dt in ('FLOAT_COLOR', 'BYTE_COLOR'):
                return a[:, :3] @ LUMA
            return a[:, :3].mean(1)
        if s.identifier == 'Alpha':
            return a[:, 3]
        return a[:, :3]

    def n_VERTEX_COLOR(self, n, s, path):
        name = n.layer_name or (self.ob.data.color_attributes.active_color.name
                                if self.ob.data.color_attributes.active_color else '')
        a = self.g.attr(name) if name else None
        if a is None:
            return np.zeros(3, np.float32) if s.identifier == 'Color' else 0.0
        return a[:, 3] if s.identifier == 'Alpha' else a[:, :3]

    def n_VECT_TRANSFORM(self, n, s, path):
        v = np.asarray(self.inp(n, 'Vector', path), np.float32)
        fr, to, vt = n.convert_from, n.convert_to, n.vector_type
        if 'CAMERA' in (fr, to):
            raise Unsupported('camera space')
        if fr == to:
            return v
        if fr == 'OBJECT' and to == 'WORLD':
            if v.ndim == 1:
                g = self.g
                if vt == 'POINT':
                    return (g.R @ v + g.M[:3, 3]).astype(np.float32)
                if vt == 'NORMAL':
                    r = g.Rn @ v
                    return (r / max(np.linalg.norm(r), 1e-20)).astype(np.float32)
                return (g.R @ v).astype(np.float32)
            return self._to_world(v, vt)
        if fr == 'WORLD' and to == 'OBJECT':
            g = self.g
            Ri = np.linalg.inv(g.R)
            if vt == 'POINT':
                return ((v - g.M[:3, 3]) @ Ri.T).astype(np.float32)
            if vt == 'NORMAL':
                return _unit(v @ g.R)
            return (v @ Ri.T).astype(np.float32)
        raise Unsupported('vector transform')

    def n_MAPPING(self, n, s, path):
        v = np.asarray(self.inp(n, 'Vector', path), np.float32)
        vt = n.vector_type
        rot = _euler_matrix(self.inp(n, 'Rotation', path))
        sc = np.asarray(self.inp(n, 'Scale', path), np.float32)
        if sc.ndim != 1:
            raise Unsupported('a linked Mapping scale')
        loc = np.asarray(self.inp(n, 'Location', path), np.float32) if vt in ('POINT', 'TEXTURE') else 0.0
        if np.ndim(loc) > 1:
            raise Unsupported('a linked Mapping location')
        if vt == 'POINT':
            return ((v * sc) @ rot.T + loc).astype(np.float32)
        if vt == 'TEXTURE':
            with np.errstate(all='ignore'):
                return (((v - loc) @ rot) / np.where(sc != 0, sc, 1)).astype(np.float32)
        if vt == 'VECTOR':
            return ((v * sc) @ rot.T).astype(np.float32)
        with np.errstate(all='ignore'):
            return _unit((v / np.where(sc != 0, sc, 1)) @ rot.T)

    # -- textures ------------------------------------------------------------------------------------------------
    def _lookup(self, img, n, uv):
        L = lib()
        px, w, h = self.images.get(img)
        m = len(uv)
        uv = _c(uv)
        out = np.empty((m, 4), np.float32)
        interp = 0 if n.interpolation == 'Closest' else 1
        ext = {'REPEAT': 0, 'EXTEND': 1, 'CLIP': 2, 'MIRROR': 3}.get(n.extension, 0)
        L.mbake_image(_ptr(px), int(w), int(h), 4, interp, ext, int(m), _ptr(uv), _ptr(out), _threads())
        return out

    def n_TEX_IMAGE(self, n, s, path):
        img = n.image
        g = self.g
        vec = np.asarray(self.inp(n, 'Vector', path), np.float32)
        if vec.ndim == 1:
            vec = np.broadcast_to(vec, (g.n, 3))
        if img is None:
            c = np.empty((g.n, 4), np.float32)
            c[:] = (1.0, 0.0, 1.0, 1.0)
        elif img.source not in ('FILE', 'GENERATED', 'MOVIE') or img.source == 'MOVIE' or \
                getattr(img, 'source', '') == 'TILED':
            raise Unsupported('image ' + img.source)
        elif n.projection == 'FLAT':
            c = self._lookup(img, n, vec[:, :2])
        elif n.projection == 'BOX':
            c = self._box(img, n, vec)
        else:
            raise Unsupported('image projection ' + n.projection)
        if s.identifier == 'Alpha':
            return c[:, 3].copy()
        if img is not None and img.alpha_mode == 'PREMUL':
            pass
        return c[:, :3].copy()

    def _box(self, img, n, co):
        """Cycles' svm_node_tex_image_box: three planar lookups blended by the object-space normal."""
        g = self.g
        N = g.No.astype(np.float32)
        sN = N
        A = np.abs(N)
        A = A / np.maximum(A.sum(1, keepdims=True), 1e-20)
        blend = float(n.projection_blend)
        limit = 0.5 * (1.0 + blend)
        x, y, z = A[:, 0], A[:, 1], A[:, 2]
        W = np.zeros_like(A)
        cx = (x > limit * (x + y)) & (x > limit * (x + z))
        cy = ~cx & (y > limit * (x + y)) & (y > limit * (y + z))
        cz = ~cx & ~cy & (z > limit * (x + z)) & (z > limit * (y + z))
        W[cx, 0] = 1
        W[cy, 1] = 1
        W[cz, 2] = 1
        rest = ~(cx | cy | cz)
        if blend > 0:
            with np.errstate(all='ignore'):
                m1 = rest & (z < (1 - limit) * (y + x))
                wx = sat((x / (x + y) - 0.5 * (1 - blend)) / blend)
                W[m1, 0], W[m1, 1] = wx[m1], 1 - wx[m1]
                m2 = rest & ~m1 & (x < (1 - limit) * (y + z))
                wy = sat((y / (y + z) - 0.5 * (1 - blend)) / blend)
                W[m2, 1], W[m2, 2] = wy[m2], 1 - wy[m2]
                m3 = rest & ~m1 & ~m2 & (y < (1 - limit) * (x + z))
                wx2 = sat((x / (x + z) - 0.5 * (1 - blend)) / blend)
                W[m3, 0], W[m3, 2] = wx2[m3], 1 - wx2[m3]
                m4 = rest & ~m1 & ~m2 & ~m3
                den = 2 * limit - 1
                for k, comp in enumerate((x, y, z)):
                    W[m4, k] = ((2 - limit) * comp[m4] + (limit - 1)) / den
        else:
            W[rest, 0] = 1
        out = np.zeros((g.n, 4), np.float32)
        for k in range(3):
            sel = np.nonzero(W[:, k] > 0)[0]
            if not len(sel):
                continue
            c = co[sel]
            if k == 0:
                uv = np.stack([np.where(sN[sel, 0] < 0, 1 - c[:, 1], c[:, 1]), c[:, 2]], 1)
            elif k == 1:
                uv = np.stack([np.where(sN[sel, 1] > 0, 1 - c[:, 0], c[:, 0]), c[:, 2]], 1)
            else:
                uv = np.stack([np.where(sN[sel, 2] > 0, 1 - c[:, 1], c[:, 1]), c[:, 0]], 1)
            out[sel] += W[sel, k:k + 1] * self._lookup(img, n, uv)
        return out

    # -- ray nodes -----------------------------------------------------------------------------------------------
    def n_AMBIENT_OCCLUSION(self, n, s, path):
        if self.parent is not None:                       # (a bump's offset point: the centre's)
            return self.parent.out(n, s, path)[0]
        g = self.g
        L = lib()
        N = np.asarray(self.inp(n, 'Normal', path), np.float32)
        N = np.broadcast_to(N, (g.n, 3)) if N.ndim == 1 else N
        dist = self.inp(n, 'Distance', path)
        if np.ndim(dist):
            raise Unsupported('a linked AO distance')
        col = self.inp(n, 'Color', path)
        sc = self.local if n.only_local else self.scene
        out = np.ones(g.n, np.float32)
        ns = min(256, max(1, int(round(max(n.samples, 1) * AO_MULT * self.ray_quality))))
        if sc:
            P, Nn, Ng = _c(g.P), _c(_unit(N)), _c(g.Ng)
            tri = _c(g.tri, np.int32) if sc is self.local else None
            L.mbake_ao(sc, int(g.n), _ptr(P), _ptr(Nn), _ptr(Ng), _ptr(tri, _IP) if tri is not None else None,
                       _ptr(self.seeds, _UIP), int(ns), float(dist), 1 if n.inside else 0, _ptr(out), _threads())
        if s.identifier == 'AO':
            return out
        col = np.asarray(col, np.float32)
        return (col * out[:, None]).astype(np.float32)

    def n_BEVEL(self, n, s, path):
        if self.parent is not None:
            return self.parent.out(n, s, path)[0]
        g = self.g
        L = lib()
        R = np.asarray(self.inp(n, 'Radius', path), np.float32)
        R = np.broadcast_to(R, (g.n,)) if R.ndim == 0 else R
        out = np.empty((g.n, 3), np.float32)
        if self.local and float(np.max(R)) > 0:
            ns = min(256, max(1, int(round(max(n.samples, 1) * BEVEL_MULT * self.ray_quality))))
            L.mbake_bevel(self.local, int(g.n), _ptr(_c(g.P)), _ptr(_c(g.N)), _ptr(_c(g.Ng)), _ptr(_c(R)),
                          _ptr(self.seeds, _UIP), int(ns), _ptr(out), _threads())
        else:
            out[:] = g.N
        if n.inputs['Normal'].is_linked:                  # (Cycles: the input normal kept, the bevel's turn added)
            ref = np.asarray(self.inp(n, 'Normal', path), np.float32)
            out = _unit(ref + (out - g.N))
        return out

    # -- normals -------------------------------------------------------------------------------------------------
    def n_BUMP(self, n, s, path):
        g = self.g
        Nin = np.asarray(self.inp(n, 'Normal', path), np.float32)
        Nin = np.broadcast_to(Nin, (g.n, 3)) if Nin.ndim == 1 else Nin
        strength = np.maximum(np.asarray(self.inp(n, 'Strength', path), np.float32), 0.0)
        dist = np.asarray(self.inp(n, 'Distance', path), np.float32)
        fw = self.inp(n, 'Filter Width', path) if n.inputs.get('Filter Width') is not None else 0.1
        if np.ndim(fw):
            raise Unsupported('a linked bump filter width')
        fw = max(float(fw), 1e-4)
        if n.invert:
            dist = -dist
        hs = n.inputs['Height']
        if not hs.is_linked:
            return np.asarray(Nin, np.float32)
        hc = np.asarray(self.sock_in(hs, path), np.float32)
        if hc.ndim == 0:
            return np.asarray(Nin, np.float32)
        # Cycles' way: the height again at points 1/10 texel along u and v (Filter Width) - the ray nodes in it
        # (Bevel / AO) keep their centre values there (traced once)
        if self.parent is not None:
            raise Unsupported('a bump inside a bump height')
        step = fw / g.res
        ex, ey = self._shifted(step)
        hx = np.asarray(ex.sock_in(hs, path), np.float32)
        hy = np.asarray(ey.sock_in(hs, path), np.float32)
        dx = (g.dPdu_o * step) @ g.R.T
        dy = (g.dPdv_o * step) @ g.R.T
        Rx = np.cross(dy, Nin)
        Ry = np.cross(Nin, dx)
        det = _dot(dx, Rx)
        surf = (hx - hc)[:, None] * Rx + (hy - hc)[:, None] * Ry
        absdet = np.abs(det)
        d3 = dist[..., None] if dist.ndim else dist
        no = absdet[:, None] * Nin - d3 * np.sign(det)[:, None] * surf
        ln = np.linalg.norm(no, axis=1, keepdims=True)
        no = np.where(ln > 1e-30, no / np.maximum(ln, 1e-30), Nin)
        s3 = strength[..., None] if strength.ndim else strength
        return _unit(s3 * no + (1 - s3) * Nin)

    def _shifted(self, step):
        if self.shifts is None or self.shifts[0] != step:
            g = self.g
            ex = Eval(self.ob, Shift(g, step, 0.0), self.images, self.scene, self.local, self.seeds, self.ray_quality,
                      self)
            ey = Eval(self.ob, Shift(g, 0.0, step), self.images, self.scene, self.local, self.seeds, self.ray_quality,
                      self)
            ex.root_tree = ey.root_tree = self.root_tree
            self.shifts = (step, ex, ey)
        return self.shifts[1], self.shifts[2]

    def n_NORMAL_MAP(self, n, s, path):
        g = self.g
        c = np.asarray(self.inp(n, 'Color', path), np.float32)
        st = np.asarray(self.inp(n, 'Strength', path), np.float32)
        c = c * 2.0 - 1.0
        c = np.broadcast_to(c, (g.n, 3)) if c.ndim == 1 else c
        sp = n.space
        if sp == 'TANGENT':
            if n.uv_map and n.uv_map != g.bake_uv:
                raise Unsupported('a normal map on another UV map')
            B = g.S[:, None] * np.cross(g.N, g.T)
            N = _unit(c[:, 0:1] * g.T + c[:, 1:2] * B + c[:, 2:3] * g.N)
        elif sp == 'OBJECT':
            N = _unit(c @ g.Rn.T)
        elif sp == 'WORLD':
            N = _unit(c)
        else:
            raise Unsupported('normal map ' + sp)
        s3 = st[..., None] if st.ndim else st
        return _unit(g.N + (N - g.N) * s3)

    def n_NORMAL(self, n, s, path):
        nv = np.array(n.outputs['Normal'].default_value[:3], np.float32)
        if s.identifier == 'Normal':
            return nv
        v = np.asarray(self.inp(n, 'Normal', path), np.float32)
        return -_dot(_unit(v), nv)

    def n_FRESNEL(self, n, s, path):
        raise Unsupported('fresnel (depends on the view)')


# ---------------------------------------------------------------------------------------------------------------------
# closures: what the bake reads of the shader
# ---------------------------------------------------------------------------------------------------------------------

GLOW_NAMES = {'COLOR': ('Base Color', 'Color'), 'ROUGH': ('Roughness',), 'METAL': ('Metallic',)}
GLOW_DEF = {'COLOR': (0.8, 0.8, 0.8), 'ROUGH': (0.5, 0.5, 0.5), 'METAL': (0.0, 0.0, 0.0)}


def shade(ev, sock_out, path, kind):
    """The bake's value from the shader socket ``sock_out`` (an output): COLOR / ROUGH / METAL (as the Emission
    swap of bake_maps._metal_glow bakes them), EMIT, NORMAL (sum of normal x weight, weight)."""
    n = sock_out.node
    if n.mute:
        lk = next((lk for lk in n.internal_links if lk.to_socket == sock_out), None)
        if lk is None:
            return _zero(ev, kind)
        return shade_in(ev, lk.from_socket, path, kind)
    t = n.type
    if t == 'REROUTE':
        return shade_in(ev, n.inputs[0], path, kind)
    if t == 'GROUP':
        nt = n.node_tree
        go = next((x for x in nt.nodes if x.type == 'GROUP_OUTPUT' and x.is_active_output), None) if nt else None
        if go is None:
            return _zero(ev, kind)
        ins = next((x for x in go.inputs if x.identifier == sock_out.identifier), None)
        return shade_in(ev, ins, path + (n.name,), kind) if ins is not None else _zero(ev, kind)
    if t == 'GROUP_INPUT':
        gnode = ev._group_node(path[:-1], path[-1])
        si = next((x for x in gnode.inputs if x.identifier == sock_out.identifier), None)
        return shade_in(ev, si, path[:-1], kind) if si is not None else _zero(ev, kind)
    if t == 'MIX_SHADER':
        f = sat(np.asarray(ev.inp(n, 0, path), np.float32))
        a = shade_in(ev, n.inputs[1], path, kind)
        b = shade_in(ev, n.inputs[2], path, kind)
        return _lerp_c(a, b, f, kind)
    if t == 'ADD_SHADER':
        a = shade_in(ev, n.inputs[0], path, kind)
        b = shade_in(ev, n.inputs[1], path, kind)
        return _add_c(a, b, kind)
    if t == 'EMISSION':
        col = np.asarray(ev.inp(n, 'Color', path), np.float32)
        stv = ev.inp(n, 'Strength', path)
        if kind == 'NORMAL':
            return _zero(ev, kind)
        if kind in GLOW_NAMES and not n.inputs['Strength'].is_linked:
            return _zero(ev, kind)                  # (bake_maps turns its own unlinked glow off)
        sv = np.asarray(stv, np.float32)
        return _full(ev, col * (sv[..., None] if sv.ndim else sv))
    if t == 'HOLDOUT':
        return _zero(ev, kind)
    if t.startswith('BSDF_') or t == 'SUBSURFACE_SCATTERING':
        if t in ('BSDF_HAIR', 'BSDF_HAIR_PRINCIPLED', 'BSDF_TOON', 'BSDF_RAY_PORTAL'):
            raise Unsupported(t)
        if kind in GLOW_NAMES:
            src = next((n.inputs[k] for k in GLOW_NAMES[kind] if n.inputs.get(k) is not None), None)
            if src is None:
                return _full(ev, np.array(GLOW_DEF[kind], np.float32))
            v = ev.sock_in(src, path, 'RGBA')
            return _full(ev, np.asarray(v, np.float32))
        if kind == 'EMIT':
            if t == 'BSDF_PRINCIPLED':
                c = np.asarray(ev.inp(n, 'Emission Color', path), np.float32)
                sv = np.asarray(ev.inp(n, 'Emission Strength', path), np.float32)
                return _full(ev, c * (sv[..., None] if sv.ndim else sv))
            return _zero(ev, kind)
        if kind == 'NORMAL':
            if t in ('BSDF_TRANSPARENT', 'BSDF_HOLDOUT'):
                return _zero(ev, kind)
            nm = n.inputs.get('Normal')
            N = np.asarray(ev.sock_in(nm, path), np.float32) if nm is not None else ev.g.N
            N = np.broadcast_to(N, (ev.g.n, 3)) if N.ndim == 1 else N
            acc = N.astype(np.float32).copy()
            if t == 'BSDF_PRINCIPLED':
                cw = np.asarray(ev.inp(n, 'Coat Weight', path), np.float32)
                if np.any(cw > 1e-5):
                    cn = np.asarray(ev.inp(n, 'Coat Normal', path), np.float32)
                    cn = np.broadcast_to(cn, (ev.g.n, 3)) if cn.ndim == 1 else cn
                    acc = acc + (cw[..., None] if cw.ndim else cw) * cn
            return acc
    raise Unsupported(f'shader {n.bl_idname}')


def shade_in(ev, sock_in, path, kind):
    lk = next((lk for lk in sock_in.links if not lk.is_muted), None) if sock_in.is_linked else None
    if lk is None:
        return _zero(ev, kind)
    if lk.from_socket.type != 'SHADER':
        raise Unsupported('a colour into a shader socket')
    return shade(ev, lk.from_socket, path, kind)


def _zero(ev, kind):
    return np.zeros((ev.g.n, 3), np.float32)


def _full(ev, v):
    v = np.asarray(v, np.float32)
    if v.ndim == 0:
        v = np.array([v, v, v], np.float32)
    elif v.ndim == 1 and v.shape[0] == ev.g.n and ev.g.n != 3:
        v = np.repeat(v[:, None], 3, 1)
    return np.broadcast_to(v, (ev.g.n, 3)).astype(np.float32) if v.ndim == 1 else v


def _lerp_c(a, b, f, kind):
    f = np.asarray(f, np.float32)
    f3 = f[..., None] if f.ndim else f
    return (1 - f3) * a + f3 * b


def _add_c(a, b, kind):
    return a + b


# ---------------------------------------------------------------------------------------------------------------------
# the bake
# ---------------------------------------------------------------------------------------------------------------------

def _scene_of(context, low, g, dist, others=True):
    """(scene with the low and the meshes near it - for AO, the object alone - for Bevel and local AO)."""
    L = lib()
    V = g.me_co @ g.R.T + g.M[:3, 3]
    T = g.me_tris.astype(np.int32)
    Nn = (g.me_cn.reshape(-1, 3) @ g.Rn.T).reshape(-1, 9)
    local = L.mbake_scene_new(int(len(V)), _ptr(_c(V)), int(len(T)), _ptr(_c(T, np.int32), _IP), _ptr(_c(Nn)))
    if not others:
        return local, local
    lo_, hi_ = V.min(0) - dist, V.max(0) + dist
    Vs, Ts, Ns, base = [V.astype(np.float32)], [T], [Nn.astype(np.float32)], len(V)
    dg = context.evaluated_depsgraph_get()
    for o in context.scene.objects:
        if o is low or o.type != 'MESH' or o.hide_render or not o.visible_get():
            continue
        bb = np.array([o.matrix_world @ __import__('mathutils').Vector(c) for c in o.bound_box])
        if (bb.max(0) < lo_).any() or (bb.min(0) > hi_).any():
            continue
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        try:
            me.calc_loop_triangles()
            nt = len(me.loop_triangles)
            if not nt:
                continue
            co = np.empty(len(me.vertices) * 3, np.float32)
            me.vertices.foreach_get('co', co)
            M = np.array(o.matrix_world, np.float32)
            Vs.append(co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3])
            vi = np.empty(nt * 3, np.int32)
            me.loop_triangles.foreach_get('vertices', vi)
            Ts.append(vi.reshape(-1, 3) + base)
            Ns.append(np.zeros((nt, 9), np.float32))
            base += len(me.vertices)
        finally:
            ev.to_mesh_clear()
    if len(Vs) == 1:
        return local, local
    V2, T2, N2 = np.concatenate(Vs), np.concatenate(Ts).astype(np.int32), np.concatenate(Ns)
    sc = L.mbake_scene_new(int(len(V2)), _ptr(_c(V2)), int(len(T2)), _ptr(_c(T2, np.int32), _IP), _ptr(_c(N2)))
    return sc or local, local


AA_SIGMA = 0.6


def _aa(full, mask, res, sigma=AA_SIGMA):
    """Cycles' bake averages its samples over the pixel filter (1.5 px): a texel's value is its neighbourhood's, not
    its centre's (a fine pattern - photo maps, bumps - shows softer).  The same here: a small Gaussian over the baked
    texels only (each island's border texels from their own island, nothing from the empty space)."""
    r = 2
    x = np.arange(-r, r + 1, dtype=np.float32)
    k = np.exp(-x * x / (2 * sigma * sigma))
    k /= k.sum()
    m = mask.reshape(res, res).astype(np.float32)
    img = full.reshape(res, res, 4) * m[..., None]

    def sep(a):
        for ax in (0, 1):
            pad = [(0, 0)] * a.ndim
            pad[ax] = (r, r)
            b = np.pad(a, pad)
            sl = [slice(None)] * a.ndim
            acc = None
            for i in range(2 * r + 1):
                sl[ax] = slice(i, i + a.shape[ax])
                t = k[i] * b[tuple(sl)]
                acc = t if acc is None else acc + t
            a = acc
        return a
    num = sep(img)
    den = sep(m)
    on = m > 0
    out = full.reshape(res, res, 4).copy()
    out[on] = num[on] / np.maximum(den[on], 1e-6)[:, None]
    return out.reshape(-1, 4)


def bake(context, low, mats, kinds, res, st, margin=16, ray_quality=1.0):
    """The maps ``kinds`` of ``low``'s own materials on its own UVs (res x res).  Returns ({kind: pixels (res*res*4)
    ready for the image}, {kind: reason it went to Cycles}, seconds)."""
    t0 = time.time()
    L = lib()
    if L is None:
        return {}, {k: 'no engine' for k in kinds}, 0.0
    out, why = {}, {}
    g = Geo(context, low, res)
    if g.n == 0:
        return {}, {k: 'no texels' for k in kinds}, 0.0
    from . import bake_maps as bm_
    size = bm_.size_of(low)
    ao_dist = size * float(st.ao_distance) / 100.0
    scene, local = _scene_of(context, low, g, max(ao_dist, 0.5))
    seeds = (np.arange(g.n, dtype=np.uint64) * 2654435761 % (2 ** 32)).astype(np.uint32)
    images = Images()
    slot_mats = [s.material for s in low.material_slots]
    try:
        per = {}
        for mi in np.unique(g.mat):
            m = slot_mats[mi] if 0 <= mi < len(slot_mats) else None
            sel = np.nonzero(g.mat == mi)[0]
            per[int(mi)] = (m, sel)
        pix = {k: np.zeros((g.n, 3), np.float32) for k in kinds}
        evs = {}
        for k in kinds:
            if k == 'AO':
                continue
            try:
                for mi, (m, sel) in per.items():
                    if m is None or not m.use_nodes or m.node_tree is None:
                        val = {'COLOR': (0.8, 0.8, 0.8), 'ROUGH': (0.5,) * 3, 'METAL': (0.0,) * 3,
                               'EMIT': (0.0,) * 3}.get(k)
                        if k == 'NORMAL':
                            pix[k][sel] = g.N[sel]
                        else:
                            pix[k][sel] = val
                        continue
                    if mi not in evs:
                        gs = g.subset(sel)
                        sseeds = _c(seeds[sel], np.uint32)
                        e = Eval(low, gs, images, scene, local, sseeds, ray_quality)
                        e.root_tree = m.node_tree
                        evs[mi] = e
                    e = evs[mi]
                    nt = m.node_tree
                    outn = nt.get_output_node('CYCLES') or nt.get_output_node('ALL')
                    if outn is None:
                        pix[k][sel] = g.N[sel] if k == 'NORMAL' else 0.0
                        continue
                    if k == 'NORMAL' and outn.inputs['Displacement'].is_linked and \
                            getattr(m, 'displacement_method', 'BUMP') != 'DISPLACEMENT':
                        raise Unsupported('a displacement bump')
                    v = shade_in(e, outn.inputs['Surface'], (), k)
                    if k == 'NORMAL':
                        ln = np.linalg.norm(v, axis=1, keepdims=True)
                        v = np.where(ln > 1e-12, v / np.maximum(ln, 1e-12), e.g.N)
                    pix[k][sel] = v
            except Unsupported as ex:
                why[k] = str(ex)
                pix.pop(k, None)
        if 'AO' in kinds:
            o = np.ones(g.n, np.float32)
            ns = min(int(st.ao_samples), bm_.AO_CAP.get(getattr(st, 'quality', 'NORMAL'), 10 ** 6))
            L.mbake_ao(scene, int(g.n), _ptr(_c(g.P)), _ptr(_c(g.N)), _ptr(_c(g.Ng)), None, _ptr(seeds, _UIP),
                       int(max(ns, 16)), float(ao_dist), 0, _ptr(o), _threads())
            pix['AO'] = np.repeat(o[:, None], 3, 1)
        for k, v in pix.items():
            if k == 'NORMAL':
                B = np.cross(g.N, g.T)
                x = _dot(v, g.T)
                y = g.S * _dot(v, B)
                z = _dot(v, g.N)
                if st.green == 'DIRECTX':
                    y = -y
                v = np.stack([x, y, z], 1) * 0.5 + 0.5
            elif k in ('COLOR', 'EMIT'):
                v = lin_to_srgb(np.clip(v, 0.0, 1.0))
            else:
                v = np.clip(v, 0.0, 1.0)
            full = np.zeros((res * res, 4), np.float32)
            if k == 'NORMAL':
                full[:] = (0.5, 0.5, 1.0, 1.0)
            full[g.idx, :3] = v
            full[g.idx, 3] = 1.0
            full = _c(_aa(full, g.mask, res))
            if margin > 0:
                L.mbake_margin(_ptr(full), 4, _ptr(g.mask, _UP), int(res), int(res), int(margin))
            out[k] = full
    finally:
        L.mbake_scene_free(local)
        if scene and scene != local:
            L.mbake_scene_free(scene)
    return out, why, time.time() - t0
