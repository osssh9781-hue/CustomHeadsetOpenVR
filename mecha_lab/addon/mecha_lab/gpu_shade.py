"""0.24.348 GPU material evaluation for Fast Bake (user: "2.3.4 먼저 해 줘" - 3: the node maths on the graphics card).

The material's node tree (the same nodes ``fast_shade.Eval`` works out with numpy) written as one GLSL compute shader
- every node a line of GLSL, each texel one GPU thread.  The texels' geometry (points, normals, UVs, tangents, the
bump's steps, the attributes the material reads) goes in as one float texture, every picture the material samples as
one atlas texture (looked up as the C engine does: Closest / Linear, Repeat / Extend / Clip / Mirror, Flat / Box);
the ray nodes (Ambient Occlusion, Bevel) are traced first (GPU / C engine) and read in as values, the Bump's
heights worked out at the offset points by a GLSL function of their own (the ray nodes kept at their centre values,
as on the CPU).  The answer: the maps' values per texel, read back.

Anything it does not know raises ``fast_shade.Unsupported``: that material is worked out by numpy as before - the
same result, slower."""
from __future__ import annotations

import hashlib
import math
import time

import numpy as np

from .fast_shade import LUMA, Unsupported, _blend  # noqa: F401  (_blend: the reference the GLSL follows)

TEXW = 4096
MAXROWS = [8192]                  # (rows per texture: each batch of texels well under the GPUs' 16384-row limit)
_CACHE = {}
STATS = {'compiled': 0, 'reused': 0, 'materials': 0, 'last_error': ''}

HELPERS = r'''
vec4 fetch(sampler2D t, int i) { return texelFetch(t, ivec2(i % TEXW, i / TEXW), 0); }
float lum(vec3 c) { return dot(c, vec3(0.2126729, 0.7151522, 0.0721750)); }
float avg3(vec3 v) { return (v.x + v.y + v.z) / 3.0; }
float sdiv(float a, float b) { return b != 0.0 ? a / b : 0.0; }
vec3 sdiv3(vec3 a, vec3 b) { return vec3(sdiv(a.x, b.x), sdiv(a.y, b.y), sdiv(a.z, b.z)); }
float cfmod(float a, float b) { return b != 0.0 ? a - b * trunc(a / b) : 0.0; }
vec3 cfmod3(vec3 a, vec3 b) { return vec3(cfmod(a.x, b.x), cfmod(a.y, b.y), cfmod(a.z, b.z)); }
float ffmod(float a, float b) { return b != 0.0 ? a - floor(a / b) * b : 0.0; }
float wrapf(float v, float mx, float mn) { float r = mx - mn; return r != 0.0 ? v - r * floor((v - mn) / r) : mn; }
float pingpongf(float a, float b) { return b != 0.0 ? abs(ffmod(a - b, 2.0 * b) - b) : 0.0; }
float spow(float a, float b) {
  if (a >= 0.0) return pow(a, b);
  if (floor(b) == b) { float r = pow(-a, b); return (mod(abs(b), 2.0) == 1.0) ? -r : r; }
  return 0.0;
}
float smin(float a, float b, float c) {
  if (c == 0.0) return min(a, b);
  float h = max(c - abs(a - b), 0.0) / c;
  return min(a, b) - h * h * h * c * (1.0 / 6.0);
}
vec3 rgb2hsv(vec3 c) {
  float mx = max(max(c.r, c.g), c.b), mn = min(min(c.r, c.g), c.b), d = mx - mn;
  float s = mx != 0.0 ? d / mx : 0.0, h = 0.0;
  if (s != 0.0) {
    float dd = d != 0.0 ? d : 1.0;
    float cr = (mx - c.r) / dd, cg = (mx - c.g) / dd, cb = (mx - c.b) / dd;
    if (c.r == mx) h = cb - cg; else if (c.g == mx) h = 2.0 + cr - cb; else h = 4.0 + cg - cr;
    h /= 6.0;
    if (h < 0.0) h += 1.0;
  }
  return vec3(h, s, mx);
}
vec3 hsv2rgb(vec3 c) {
  float h = c.x, s = c.y, v = c.z;
  if (s == 0.0) return vec3(v);
  h = (h - floor(h)) * 6.0;
  float i = floor(h), f = h - i;
  float p = v * (1.0 - s), q = v * (1.0 - s * f), t = v * (1.0 - s * (1.0 - f));
  int ii = int(i) % 6;
  if (ii == 0) return vec3(v, t, p);
  if (ii == 1) return vec3(q, v, p);
  if (ii == 2) return vec3(p, v, t);
  if (ii == 3) return vec3(p, q, v);
  if (ii == 4) return vec3(t, p, v);
  return vec3(v, p, q);
}
vec3 unit3(vec3 v) { float l = length(v); return l > 1e-20 ? v / l : v; }
int pmod(int i, int n) { return i >= 0 ? i % n : n - 1 - ((-i - 1) % n); }   // (GLSL's % of a negative: undefined)
int wrapi(int i, int n, int ext, inout bool ok) {
  if (ext == 0) return pmod(i, n);
  if (ext == 2) { if (i < 0 || i >= n) ok = false; return clamp(i, 0, n - 1); }
  if (ext == 3) { int p = 2 * n; i = pmod(i, p); return i < n ? i : p - 1 - i; }
  return clamp(i, 0, n - 1);
}
vec4 img_px(int off, int w, int x, int y) { return fetch(atlas, off + y * w + x); }
vec4 sample_img(int off, int w, int h, int interp, int ext, vec2 uv) {
  if (interp == 0) {
    bool ok = true;
    int x = wrapi(int(floor(uv.x * float(w))), w, ext, ok), y = wrapi(int(floor(uv.y * float(h))), h, ext, ok);
    return ok ? img_px(off, w, x, y) : vec4(0.0);
  }
  float fx = uv.x * float(w) - 0.5, fy = uv.y * float(h) - 0.5;
  int x0 = int(floor(fx)), y0 = int(floor(fy));
  float tx = fx - float(x0), ty = fy - float(y0);
  vec4 acc = vec4(0.0);
  for (int dy = 0; dy < 2; dy++) for (int dx = 0; dx < 2; dx++) {
    bool ok = true;
    int x = wrapi(x0 + dx, w, ext, ok), y = wrapi(y0 + dy, h, ext, ok);
    float wt = (dx == 1 ? tx : 1.0 - tx) * (dy == 1 ? ty : 1.0 - ty);
    if (ok) acc += wt * img_px(off, w, x, y);
  }
  return acc;
}
vec4 sample_box(int off, int w, int h, int interp, int ext, vec3 co, vec3 sn, float blend) {
  float limit = 0.5 * (1.0 + blend);
  vec3 a = abs(sn);
  float sum = a.x + a.y + a.z;
  if (sum > 0.0) a /= sum;
  float x = a.x, y = a.y, z = a.z;
  vec3 wv = vec3(0.0);
  if (x > limit * (x + y) && x > limit * (x + z)) wv.x = 1.0;
  else if (y > limit * (x + y) && y > limit * (y + z)) wv.y = 1.0;
  else if (z > limit * (x + z) && z > limit * (y + z)) wv.z = 1.0;
  else if (blend > 0.0) {
    if (z < (1.0 - limit) * (y + x)) { wv.x = clamp((x / (x + y) - 0.5 * (1.0 - blend)) / blend, 0.0, 1.0); wv.y = 1.0 - wv.x; }
    else if (x < (1.0 - limit) * (y + z)) { wv.y = clamp((y / (y + z) - 0.5 * (1.0 - blend)) / blend, 0.0, 1.0); wv.z = 1.0 - wv.y; }
    else if (y < (1.0 - limit) * (x + z)) { wv.x = clamp((x / (x + z) - 0.5 * (1.0 - blend)) / blend, 0.0, 1.0); wv.z = 1.0 - wv.x; }
    else {
      float den = 2.0 * limit - 1.0;
      wv = ((2.0 - limit) * vec3(x, y, z) + (limit - 1.0)) / den;
    }
  } else wv.x = 1.0;
  vec4 o = vec4(0.0);
  if (wv.x > 0.0) o += wv.x * sample_img(off, w, h, interp, ext, vec2(sn.x < 0.0 ? 1.0 - co.y : co.y, co.z));
  if (wv.y > 0.0) o += wv.y * sample_img(off, w, h, interp, ext, vec2(sn.y > 0.0 ? 1.0 - co.x : co.x, co.z));
  if (wv.z > 0.0) o += wv.z * sample_img(off, w, h, interp, ext, vec2(sn.z > 0.0 ? 1.0 - co.y : co.y, co.x));
  return o;
}
struct Ctx { vec3 P; vec3 Po; vec2 uvb; vec2 uvr; int i; };
'''


def _f(x):
    """A GLSL float literal."""
    x = float(x)
    if not math.isfinite(x):
        x = 0.0
    r = repr(x)
    if 'e' in r or 'E' in r:
        return f'{x:.9e}'.replace('e+', 'e')
    return r if '.' in r else r + '.0'


def _v3(v):
    return f'vec3({_f(v[0])}, {_f(v[1])}, {_f(v[2])})'


class Gen:
    """GLSL for one material's sockets, in the texel context ``ctx`` (a GLSL expression of type Ctx)."""

    def __init__(self, mat, ob, geo_layout, ctx='c', parent=None):
        self.mat, self.ob, self.L, self.ctx = mat, ob, geo_layout, ctx
        self.lines = []
        self.memo = {}
        self.n = 0
        self.parent = parent
        self.root = parent.root if parent else self
        self.funcs = [] if parent is None else None

    # -- the variables ------------------------------------------------------------------------------------------
    def var(self, typ, expr):
        self.root.n += 1
        nm = f't{self.root.n}'
        self.lines.append(f'  {typ} {nm} = {expr};')
        return nm

    def slot(self, key):
        return self.L.slot(key)

    def g(self, key):
        """A texel's geometry value (vec4 expression) of the centre texel."""
        return f'fetch(geo, {self.ctx}.i * SLOTS + {self.slot(key)})'

    # -- conversions ----------------------------------------------------------------------------------------------
    @staticmethod
    def conv(expr, frm, to):
        fv = frm in ('VALUE', 'INT', 'BOOLEAN')
        tv = to in ('VALUE', 'INT', 'BOOLEAN')
        if fv and tv:
            return expr
        if fv and not tv:
            return f'vec3({expr})'
        if not fv and tv:
            return f'lum({expr})' if frm == 'RGBA' else f'avg3({expr})'
        return expr

    # -- inputs / outputs ---------------------------------------------------------------------------------------
    def inp(self, node, key, path):
        s = node.inputs[key]
        return self.sock_in(s, path)

    def sock_in(self, s, path, want=None):
        typ = want or s.type
        lk = next((lk for lk in s.links if not lk.is_muted), None) if s.is_linked else None
        if lk is None:
            e, t = self.implicit(s, path)
            return self.conv(e, t, typ)
        if not lk.is_valid:
            raise Unsupported('an invalid link')
        e, ft = self.out(lk.from_node, lk.from_socket, path)
        return self.conv(e, ft, typ)

    def implicit(self, s, path):
        node = s.node
        if s.type == 'VECTOR' and getattr(s, 'hide_value', False):
            if s.name in ('Normal', 'Coat Normal'):
                return self.g('N') + '.xyz', 'VECTOR'
            if s.name == 'Tangent':
                raise Unsupported('an implicit tangent')
            if node.type == 'TEX_IMAGE':
                return f'vec3({self.ctx}.uvr, 0.0)', 'VECTOR'
            if node.type.startswith('TEX_'):
                return self._generated(), 'VECTOR'
            return 'vec3(0.0)', 'VECTOR'
        if s.type == 'SHADER':
            return 'vec3(0.0)', 'VECTOR'
        v = s.default_value
        if s.type in ('RGBA', 'VECTOR'):
            return _v3(v[:3]), s.type
        if s.type == 'BOOLEAN':
            return _f(1.0 if v else 0.0), 'VALUE'
        return _f(v), 'VALUE'

    def out(self, node, sock, path):
        key = (path, node.name, sock.identifier, id(node.id_data))
        if key in self.memo:
            return self.memo[key]
        if node.mute:
            r = None
            for lk in node.internal_links:
                if lk.to_socket == sock:
                    r = (self.sock_in(lk.from_socket, path, sock.type), sock.type)
                    break
            if r is None:
                r = ('vec3(0.0)', sock.type) if sock.type in ('RGBA', 'VECTOR') else ('0.0', sock.type)
        else:
            f = getattr(self, 'n_' + node.type, None)
            if f is None:
                raise Unsupported(f'node {node.bl_idname} (GPU)')
            e = f(node, sock, path)
            r = (e, sock.type)
        self.memo[key] = r
        return r

    def _generated(self):
        loc, size = self.L.tex_loc, self.L.tex_size
        return f'(({self.ctx}.Po - {_v3(loc)} + {_v3(size)}) / {_v3(2 * size)})'

    # -- nodes ----------------------------------------------------------------------------------------------------
    def n_REROUTE(self, n, s, path):
        return self.sock_in(n.inputs[0], path, s.type)

    def n_VALUE(self, n, s, path):
        return _f(n.outputs[0].default_value)

    def n_RGB(self, n, s, path):
        return _v3(n.outputs[0].default_value[:3])

    def n_GROUP(self, n, s, path):
        nt = n.node_tree
        if nt is None:
            return '0.0' if s.type in ('VALUE', 'INT', 'BOOLEAN') else 'vec3(0.0)'
        go = next((x for x in nt.nodes if x.type == 'GROUP_OUTPUT' and x.is_active_output), None) or \
            next((x for x in nt.nodes if x.type == 'GROUP_OUTPUT'), None)
        ins = next((x for x in go.inputs if x.identifier == s.identifier), None) if go else None
        if ins is None:
            return '0.0' if s.type in ('VALUE', 'INT', 'BOOLEAN') else 'vec3(0.0)'
        return self.sock_in(ins, path + (n.name,), s.type)

    def n_GROUP_INPUT(self, n, s, path):
        if not path:
            raise Unsupported('a group input outside a group')
        nt = self.mat.node_tree
        for nm in path[:-1]:
            nt = nt.nodes[nm].node_tree
        gnode = nt.nodes[path[-1]]
        si = next((x for x in gnode.inputs if x.identifier == s.identifier), None)
        if si is None:
            return '0.0' if s.type in ('VALUE', 'INT', 'BOOLEAN') else 'vec3(0.0)'
        return self.sock_in(si, path[:-1], s.type)

    MATH = {
        'ADD': '({a} + {b})', 'SUBTRACT': '({a} - {b})', 'MULTIPLY': '({a} * {b})', 'DIVIDE': 'sdiv({a}, {b})',
        'MULTIPLY_ADD': '({a} * {b} + {c})', 'POWER': 'spow({a}, {b})',
        'LOGARITHM': '(({a}) > 0.0 && ({b}) > 0.0 ? log({a}) / log({b}) : 0.0)',
        'SQRT': '(({a}) > 0.0 ? sqrt({a}) : 0.0)', 'INVERSE_SQRT': '(({a}) > 0.0 ? inversesqrt({a}) : 0.0)',
        'ABSOLUTE': 'abs({a})', 'EXPONENT': 'exp({a})', 'MINIMUM': 'min({a}, {b})', 'MAXIMUM': 'max({a}, {b})',
        'LESS_THAN': '(({a}) < ({b}) ? 1.0 : 0.0)', 'GREATER_THAN': '(({a}) > ({b}) ? 1.0 : 0.0)',
        'SIGN': 'sign({a})', 'COMPARE': '(abs(({a}) - ({b})) <= max({c}, 1e-5) ? 1.0 : 0.0)',
        'SMOOTH_MIN': 'smin({a}, {b}, {c})', 'SMOOTH_MAX': '(-smin(-({a}), -({b}), {c}))',
        'ROUND': 'floor(({a}) + 0.5)', 'FLOOR': 'floor({a})', 'CEIL': 'ceil({a})', 'TRUNC': 'trunc({a})',
        'FRACT': '(({a}) - floor({a}))', 'MODULO': 'cfmod({a}, {b})', 'FLOORED_MODULO': 'ffmod({a}, {b})',
        'WRAP': 'wrapf({a}, {b}, {c})', 'SNAPPING': '(({b}) != 0.0 ? floor(sdiv({a}, {b})) * ({b}) : 0.0)',
        'PINGPONG': 'pingpongf({a}, {b})', 'SINE': 'sin({a})', 'COSINE': 'cos({a})', 'TANGENT': 'tan({a})',
        'SINH': 'sinh({a})', 'COSH': 'cosh({a})', 'TANH': 'tanh({a})',
        'ARCSINE': '(abs({a}) <= 1.0 ? asin(clamp({a}, -1.0, 1.0)) : 0.0)',
        'ARCCOSINE': '(abs({a}) <= 1.0 ? acos(clamp({a}, -1.0, 1.0)) : 0.0)',
        'ARCTANGENT': 'atan({a})', 'ARCTAN2': 'atan({a}, {b})', 'RADIANS': '(({a}) * 0.017453292519943295)',
        'DEGREES': '(({a}) * 57.29577951308232)',
    }

    def n_MATH(self, n, s, path):
        op = n.operation
        if op not in self.MATH:
            raise Unsupported(f'math {op}')
        a = self.inp(n, 0, path)
        b = self.inp(n, 1, path)
        c = self.inp(n, 2, path) if len(n.inputs) > 2 else '0.0'
        e = self.MATH[op].format(a=a, b=b, c=c)
        if n.use_clamp:
            e = f'clamp({e}, 0.0, 1.0)'
        return self.var('float', e)

    def n_VECT_MATH(self, n, s, path):
        op = n.operation
        a = self.inp(n, 0, path)
        b = self.inp(n, 1, path)
        val = vec = None
        if op == 'ADD':
            vec = f'({a} + {b})'
        elif op == 'SUBTRACT':
            vec = f'({a} - {b})'
        elif op == 'MULTIPLY':
            vec = f'({a} * {b})'
        elif op == 'DIVIDE':
            vec = f'sdiv3({a}, {b})'
        elif op == 'MULTIPLY_ADD':
            vec = f'({a} * {b} + {self.inp(n, 2, path)})'
        elif op == 'CROSS_PRODUCT':
            vec = f'cross({a}, {b})'
        elif op == 'PROJECT':
            vec = f'(dot({b}, {b}) != 0.0 ? {b} * (dot({a}, {b}) / dot({b}, {b})) : vec3(0.0))'
        elif op == 'REFLECT':
            nb = self.var('vec3', f'unit3({b})')
            vec = f'({a} - 2.0 * dot({nb}, {a}) * {nb})'
        elif op == 'DOT_PRODUCT':
            val = f'dot({a}, {b})'
        elif op == 'DISTANCE':
            val = f'distance({a}, {b})'
        elif op == 'LENGTH':
            val = f'length({a})'
        elif op == 'SCALE':
            vec = f'({a} * {self.inp(n, "Scale", path)})'
        elif op == 'NORMALIZE':
            vec = f'unit3({a})'
        elif op == 'ABSOLUTE':
            vec = f'abs({a})'
        elif op == 'MINIMUM':
            vec = f'min({a}, {b})'
        elif op == 'MAXIMUM':
            vec = f'max({a}, {b})'
        elif op == 'FLOOR':
            vec = f'floor({a})'
        elif op == 'CEIL':
            vec = f'ceil({a})'
        elif op == 'FRACT':
            vec = f'({a} - floor({a}))'
        elif op == 'MODULO':
            vec = f'cfmod3({a}, {b})'
        elif op == 'SINE':
            vec = f'sin({a})'
        elif op == 'COSINE':
            vec = f'cos({a})'
        elif op == 'TANGENT':
            vec = f'tan({a})'
        else:
            raise Unsupported(f'vector math {op}')
        if s.type == 'VALUE':
            return self.var('float', val) if val is not None else '0.0'
        return self.var('vec3', vec) if vec is not None else 'vec3(0.0)'

    def _sock_id(self, n, ident):
        return next(x for x in n.inputs if x.identifier == ident)

    def _blend(self, kind, t, a, b, vec=True):
        """GLSL of fast_shade._blend."""
        tm = f'(1.0 - {t})'
        if kind == 'MIX':
            return f'({tm} * {a} + {t} * {b})'
        if kind == 'ADD':
            return f'({a} + {t} * {b})'
        if kind == 'MULTIPLY':
            return f'({a} * ({tm} + {t} * {b}))'
        if kind == 'SUBTRACT':
            return f'({a} - {t} * {b})'
        if kind == 'SCREEN':
            return f'(1.0 - ({tm} + {t} * (1.0 - {b})) * (1.0 - {a}))'
        if kind == 'DIFFERENCE':
            return f'({tm} * {a} + {t} * abs({a} - {b}))'
        if kind == 'EXCLUSION':
            return f'max({tm} * {a} + {t} * ({a} + {b} - 2.0 * {a} * {b}), 0.0)'
        if kind == 'DARKEN':
            return f'({tm} * {a} + {t} * min({a}, {b}))'
        if kind == 'LIGHTEN':
            return f'({tm} * {a} + {t} * max({a}, {b}))'
        if kind == 'LINEAR_LIGHT':
            return f'({a} + {t} * (2.0 * {b} - 1.0))'
        if kind == 'SOFT_LIGHT':
            return f'({tm} * {a} + {t} * ((1.0 - {a}) * {b} * {a} + {a} * (1.0 - (1.0 - {b}) * (1.0 - {a}))))'
        if kind == 'DIVIDE':
            A, B = self.var('vec3', a), self.var('vec3', b)
            return (f'vec3(({B}.x != 0.0 ? {tm} * {A}.x + {t} * {A}.x / {B}.x : {A}.x), '
                    f'({B}.y != 0.0 ? {tm} * {A}.y + {t} * {A}.y / {B}.y : {A}.y), '
                    f'({B}.z != 0.0 ? {tm} * {A}.z + {t} * {A}.z / {B}.z : {A}.z))')
        if kind == 'OVERLAY':
            A, B = self.var('vec3', a), self.var('vec3', b)
            parts = []
            for c in 'xyz':
                parts.append(f'({A}.{c} < 0.5 ? {A}.{c} * ({tm} + 2.0 * {t} * {B}.{c}) : '
                             f'1.0 - ({tm} + 2.0 * {t} * (1.0 - {B}.{c})) * (1.0 - {A}.{c}))')
            return 'vec3(' + ', '.join(parts) + ')'
        if kind in ('HUE', 'SATURATION', 'VALUE', 'COLOR'):
            A, B = self.var('vec3', a), self.var('vec3', b)
            ha, hb = self.var('vec3', f'rgb2hsv({A})'), self.var('vec3', f'rgb2hsv({B})')
            if kind == 'VALUE':
                return f'({tm} * {A} + {t} * hsv2rgb(vec3({ha}.x, {ha}.y, {hb}.z)))'
            if kind == 'SATURATION':
                return f'({tm} * {A} + {t} * hsv2rgb(vec3({ha}.x, {ha}.y != 0.0 ? {hb}.y : {ha}.y, {ha}.z)))'
            if kind == 'HUE':
                return f'({hb}.y != 0.0 ? {tm} * {A} + {t} * hsv2rgb(vec3({hb}.x, {ha}.y, {ha}.z)) : {A})'
            return f'({hb}.y != 0.0 ? {tm} * {A} + {t} * hsv2rgb(vec3({hb}.x, {hb}.y, {ha}.z)) : {A})'
        raise Unsupported(f'mix {kind}')

    def n_MIX(self, n, s, path):
        dt = n.data_type
        if dt == 'FLOAT':
            f = self.sock_in(self._sock_id(n, 'Factor_Float'), path)
            if n.clamp_factor:
                f = f'clamp({f}, 0.0, 1.0)'
            f = self.var('float', f)
            a = self.sock_in(self._sock_id(n, 'A_Float'), path)
            b = self.sock_in(self._sock_id(n, 'B_Float'), path)
            return self.var('float', f'((1.0 - {f}) * {a} + {f} * {b})')
        if dt == 'VECTOR':
            uni = getattr(n, 'factor_mode', 'UNIFORM') == 'UNIFORM'
            f = self.sock_in(self._sock_id(n, 'Factor_Float' if uni else 'Factor_Vector'), path)
            if n.clamp_factor:
                f = f'clamp({f}, 0.0, 1.0)' if uni else f'clamp({f}, vec3(0.0), vec3(1.0))'
            f = self.var('float' if uni else 'vec3', f)
            a = self.sock_in(self._sock_id(n, 'A_Vector'), path)
            b = self.sock_in(self._sock_id(n, 'B_Vector'), path)
            return self.var('vec3', f'((1.0 - {f}) * {a} + {f} * {b})')
        if dt == 'RGBA':
            f = self.sock_in(self._sock_id(n, 'Factor_Float'), path)
            if n.clamp_factor:
                f = f'clamp({f}, 0.0, 1.0)'
            f = self.var('float', f)
            a = self.var('vec3', self.sock_in(self._sock_id(n, 'A_Color'), path))
            b = self.var('vec3', self.sock_in(self._sock_id(n, 'B_Color'), path))
            r = self._blend(n.blend_type, f, a, b)
            if n.clamp_result:
                r = f'clamp({r}, vec3(0.0), vec3(1.0))'
            return self.var('vec3', r)
        raise Unsupported(f'mix {dt}')

    def n_MIX_RGB(self, n, s, path):
        f = self.var('float', f'clamp({self.inp(n, "Fac", path)}, 0.0, 1.0)')
        a = self.var('vec3', self.inp(n, 'Color1', path))
        b = self.var('vec3', self.inp(n, 'Color2', path))
        r = self._blend(n.blend_type, f, a, b)
        if n.use_clamp:
            r = f'clamp({r}, vec3(0.0), vec3(1.0))'
        return self.var('vec3', r)

    def n_MAP_RANGE(self, n, s, path):
        if n.data_type != 'FLOAT':
            raise Unsupported('vector map range')
        v = self.inp(n, 'Value', path)
        fmn, fmx = self.var('float', self.inp(n, 1, path)), self.var('float', self.inp(n, 2, path))
        tmn, tmx = self.var('float', self.inp(n, 3, path)), self.var('float', self.inp(n, 4, path))
        d = self.var('float', f'({fmx} - {fmn})')
        fac = self.var('float', f'({d} != 0.0 ? (({v}) - {fmn}) / {d} : 0.0)')
        it = n.interpolation_type
        if it == 'STEPPED':
            st = self.var('float', self.inp(n, 5, path))
            fac = self.var('float', f'({st} > 0.0 ? floor({fac} * ({st} + 1.0)) / {st} : 0.0)')
        elif it == 'SMOOTHSTEP':
            fac = self.var('float', f'({fac} <= 0.0 ? 0.0 : ({fac} >= 1.0 ? 1.0 : {fac} * {fac} * (3.0 - 2.0 * {fac})))')
        elif it == 'SMOOTHERSTEP':
            fac = self.var('float', f'({fac} <= 0.0 ? 0.0 : ({fac} >= 1.0 ? 1.0 : {fac} * {fac} * {fac} * '
                                    f'({fac} * ({fac} * 6.0 - 15.0) + 10.0)))')
        r = f'({tmn} + {fac} * ({tmx} - {tmn}))'
        if n.clamp and it in ('LINEAR', 'STEPPED'):
            r = f'clamp({r}, min({tmn}, {tmx}), max({tmn}, {tmx}))'
        return self.var('float', r)

    def n_CLAMP(self, n, s, path):
        v, a, b = self.inp(n, 'Value', path), self.var('float', self.inp(n, 'Min', path)), \
            self.var('float', self.inp(n, 'Max', path))
        if n.clamp_type == 'RANGE':
            return self.var('float', f'min(max({v}, min({a}, {b})), max({a}, {b}))')
        return self.var('float', f'min(max({v}, {a}), {b})')

    def n_HUE_SAT(self, n, s, path):
        hue, sat, val = self.inp(n, 'Hue', path), self.inp(n, 'Saturation', path), self.inp(n, 'Value', path)
        fac = self.var('float', self.inp(n, 'Fac', path))
        c = self.var('vec3', self.inp(n, 'Color', path))
        hsv = self.var('vec3', f'rgb2hsv({c})')
        h = self.var('float', f'{hsv}.x + {hue} + 0.5')
        h = self.var('float', f'{h} - floor({h})')
        o = self.var('vec3', f'hsv2rgb(vec3({h}, clamp({hsv}.y * {sat}, 0.0, 1.0), {hsv}.z * {val}))')
        return self.var('vec3', f'max({fac} * {o} + (1.0 - {fac}) * {c}, vec3(0.0))')

    def n_BRIGHTCONTRAST(self, n, s, path):
        c = self.inp(n, 'Color', path)
        br, co = self.var('float', self.inp(n, 'Bright', path)), self.var('float', self.inp(n, 'Contrast', path))
        return self.var('vec3', f'max((1.0 + {co}) * {c} + ({br} - {co} * 0.5), vec3(0.0))')

    def n_INVERT(self, n, s, path):
        f = self.var('float', self.inp(n, 'Fac', path))
        c = self.var('vec3', self.inp(n, 'Color', path))
        return self.var('vec3', f'((1.0 - {f}) * {c} + {f} * (1.0 - {c}))')

    def n_GAMMA(self, n, s, path):
        c = self.var('vec3', self.inp(n, 'Color', path))
        g = self.var('float', self.inp(n, 'Gamma', path))
        return self.var('vec3', f'vec3({c}.x > 0.0 ? pow({c}.x, {g}) : {c}.x, {c}.y > 0.0 ? pow({c}.y, {g}) : {c}.y, '
                                f'{c}.z > 0.0 ? pow({c}.z, {g}) : {c}.z)')

    def n_RGBTOBW(self, n, s, path):
        return self.var('float', f'lum({self.inp(n, "Color", path)})')

    def n_VALTORGB(self, n, s, path):
        f = self.inp(n, 'Fac', path)
        key = ('ramp', n.as_pointer())
        if key not in self.root.L.ramps:
            tab = np.array([n.color_ramp.evaluate(i / 255.0) for i in range(256)], np.float32)
            self.root.L.add_ramp(key, tab)
        off = self.root.L.ramps[key]
        x = self.var('float', f'clamp({f}, 0.0, 1.0) * 255.0')
        i = self.var('int', f'clamp(int(floor({x})), 0, 255)')
        if n.color_ramp.interpolation == 'CONSTANT':
            v = self.var('vec4', f'fetch(atlas, {off} + {i})')
        else:
            t = self.var('float', f'{x} - float({i})')
            v = self.var('vec4', f'mix(fetch(atlas, {off} + {i}), fetch(atlas, {off} + min({i} + 1, 255)), {t})')
        return f'{v}.w' if s.identifier == 'Alpha' else f'{v}.xyz'

    def n_SEPXYZ(self, n, s, path):
        v = self.var('vec3', self.inp(n, 0, path))
        return f'{v}.' + {'X': 'x', 'Y': 'y', 'Z': 'z'}[s.identifier]

    def n_COMBXYZ(self, n, s, path):
        return self.var('vec3', f'vec3({self.inp(n, 0, path)}, {self.inp(n, 1, path)}, {self.inp(n, 2, path)})')

    def n_SEPARATE_COLOR(self, n, s, path):
        c = self.var('vec3', self.inp(n, 0, path))
        if n.mode == 'HSV':
            c = self.var('vec3', f'rgb2hsv({c})')
        elif n.mode != 'RGB':
            raise Unsupported('separate HSL')
        return f'{c}.' + {'Red': 'x', 'Green': 'y', 'Blue': 'z'}[s.identifier]

    def n_COMBINE_COLOR(self, n, s, path):
        c = self.var('vec3', f'vec3({self.inp(n, 0, path)}, {self.inp(n, 1, path)}, {self.inp(n, 2, path)})')
        if n.mode == 'HSV':
            return self.var('vec3', f'hsv2rgb({c})')
        if n.mode != 'RGB':
            raise Unsupported('combine HSL')
        return c

    def n_SEPRGB(self, n, s, path):
        c = self.var('vec3', self.inp(n, 0, path))
        return f'{c}.' + {'R': 'x', 'G': 'y', 'B': 'z'}[s.identifier]

    def n_COMBRGB(self, n, s, path):
        return self.n_COMBXYZ(n, s, path)

    def n_TEX_COORD(self, n, s, path):
        k = s.identifier
        c = self.ctx
        if n.object is not None and k == 'Object' and n.object != self.ob:
            Mo = np.array(n.object.matrix_world, np.float64)
            Ri = np.linalg.inv(Mo[:3, :3])
            return self.var('vec3', f'{self._mat3(Ri)} * ({c}.P - {_v3(Mo[:3, 3])})')
        if k == 'Generated':
            return self.var('vec3', self._generated())
        if k == 'Normal':
            return self.g('No') + '.xyz'
        if k == 'UV':
            return f'vec3({c}.uvr, 0.0)'
        if k == 'Object':
            return f'{c}.Po'
        raise Unsupported(f'texture coordinate {k}')

    def n_UVMAP(self, n, s, path):
        nm = n.uv_map or self.L.render_uv
        if nm == self.L.render_uv:
            return f'vec3({self.ctx}.uvr, 0.0)'
        if nm == self.L.bake_uv:
            return f'vec3({self.ctx}.uvb, 0.0)'
        raise Unsupported(f'UV map {nm} (GPU)')

    def n_NEW_GEOMETRY(self, n, s, path):
        k = s.identifier
        if k == 'Position':
            return f'{self.ctx}.P'
        if k == 'Normal':
            return self.g('N') + '.xyz'
        if k == 'True Normal':
            return self.g('Ng') + '.xyz'
        if k == 'Backfacing':
            return '0.0'
        raise Unsupported(f'geometry {k}')

    def n_ATTRIBUTE(self, n, s, path):
        if n.attribute_type == 'OBJECT':
            v = self.ob.get(n.attribute_name)
            if v is None:
                v = getattr(self.ob, n.attribute_name, None)
            if v is None:
                return 'vec3(0.0)' if s.type in ('RGBA', 'VECTOR') else '0.0'
            try:
                vv = [float(x) for x in v][:4]
            except TypeError:
                vv = [float(v)] * 3
            vv = (vv + [0.0, 0.0, 0.0])[:3] if len(vv) < 3 else vv
            if s.identifier == 'Fac':
                return _f(sum(vv[:3]) / 3.0 if len(set(vv[:3])) > 1 else vv[0])
            if s.identifier == 'Alpha':
                return _f(vv[3] if len(vv) > 3 else 1.0)
            return _v3(vv[:3])
        if n.attribute_type != 'GEOMETRY':
            raise Unsupported('attribute ' + n.attribute_type)
        key = 'attr:' + n.attribute_name
        if not self.L.has_attr(n.attribute_name):
            return 'vec3(0.0)' if s.type in ('RGBA', 'VECTOR') else '0.0'
        a = self.g(key)
        if s.identifier == 'Fac':
            dt = self.L.attr_type(n.attribute_name)
            if dt in ('FLOAT', 'INT', 'BOOLEAN', 'INT8'):
                return f'{a}.x'
            if dt in ('FLOAT_COLOR', 'BYTE_COLOR'):
                return f'lum({a}.xyz)'
            return f'avg3({a}.xyz)'
        if s.identifier == 'Alpha':
            return f'{a}.w'
        return f'{a}.xyz'

    def n_VERTEX_COLOR(self, n, s, path):
        me = self.ob.data
        name = n.layer_name or (me.color_attributes.active_color.name if me.color_attributes.active_color else '')
        if not name or not self.L.has_attr(name):
            return 'vec3(0.0)' if s.identifier == 'Color' else '0.0'
        a = self.g('attr:' + name)
        return f'{a}.w' if s.identifier == 'Alpha' else f'{a}.xyz'

    def _mat3(self, m):
        """GLSL mat3 of a numpy 3x3 (row-major in, GLSL column-major)."""
        cols = [m[:, j] for j in range(3)]
        return 'mat3(' + ', '.join(_f(x) for c in cols for x in c) + ')'

    def n_VECT_TRANSFORM(self, n, s, path):
        v = self.var('vec3', self.inp(n, 'Vector', path))
        fr, to, vt = n.convert_from, n.convert_to, n.vector_type
        if 'CAMERA' in (fr, to):
            raise Unsupported('camera space')
        if fr == to:
            return v
        M = self.L.M
        R = M[:3, :3]
        if fr == 'OBJECT' and to == 'WORLD':
            if vt == 'POINT':
                return self.var('vec3', f'{self._mat3(R)} * {v} + {_v3(M[:3, 3])}')
            if vt == 'NORMAL':
                return self.var('vec3', f'unit3({self._mat3(np.linalg.inv(R).T)} * {v})')
            return self.var('vec3', f'{self._mat3(R)} * {v}')
        if fr == 'WORLD' and to == 'OBJECT':
            Ri = np.linalg.inv(R)
            if vt == 'POINT':
                return self.var('vec3', f'{self._mat3(Ri)} * ({v} - {_v3(M[:3, 3])})')
            if vt == 'NORMAL':
                return self.var('vec3', f'unit3({self._mat3(R.T)} * {v})')
            return self.var('vec3', f'{self._mat3(Ri)} * {v}')
        raise Unsupported('vector transform')

    def _const_vec(self, n, key):
        s = n.inputs[key]
        if s.is_linked:
            raise Unsupported(f'a linked Mapping {key.lower()} (GPU)')
        return np.array(s.default_value[:3], np.float64)

    def n_MAPPING(self, n, s, path):
        from .fast_shade import _euler_matrix
        v = self.var('vec3', self.inp(n, 'Vector', path))
        vt = n.vector_type
        rot = np.asarray(_euler_matrix(self._const_vec(n, 'Rotation')), np.float64)
        sc = self._const_vec(n, 'Scale')
        loc = self._const_vec(n, 'Location') if vt in ('POINT', 'TEXTURE') else np.zeros(3)
        Rm = self._mat3(rot)
        if vt == 'POINT':
            return self.var('vec3', f'{Rm} * ({v} * {_v3(sc)}) + {_v3(loc)}')
        if vt == 'TEXTURE':
            scs = np.where(sc != 0, sc, 1.0)
            return self.var('vec3', f'(transpose({Rm}) * ({v} - {_v3(loc)})) / {_v3(scs)}')
        if vt == 'VECTOR':
            return self.var('vec3', f'{Rm} * ({v} * {_v3(sc)})')
        scs = np.where(sc != 0, sc, 1.0)
        return self.var('vec3', f'unit3({Rm} * ({v} / {_v3(scs)}))')

    def n_TEX_IMAGE(self, n, s, path):
        img = n.image
        vec = self.var('vec3', self.inp(n, 'Vector', path))
        if img is None:
            c = 'vec4(1.0, 0.0, 1.0, 1.0)'
        else:
            if img.source not in ('FILE', 'GENERATED'):
                raise Unsupported('image ' + img.source)
            off, w, h = self.root.L.image(img)
            interp = 0 if n.interpolation == 'Closest' else 1
            ext = {'REPEAT': 0, 'EXTEND': 1, 'CLIP': 2, 'MIRROR': 3}.get(n.extension, 0)
            if n.projection == 'FLAT':
                c = f'sample_img({off}, {w}, {h}, {interp}, {ext}, {vec}.xy)'
            elif n.projection == 'BOX':
                c = f'sample_box({off}, {w}, {h}, {interp}, {ext}, {vec}, {self.g("No")}.xyz, ' \
                    f'{_f(n.projection_blend)})'
            else:
                raise Unsupported('image projection ' + n.projection)
        r = self.var('vec4', c)
        return f'{r}.w' if s.identifier == 'Alpha' else f'{r}.xyz'

    # -- the ray nodes: traced before (their values in the geometry texture) ----------------------------------------
    def n_AMBIENT_OCCLUSION(self, n, s, path):
        key = self.L.ray_key(n, path)
        a = self.g(key)
        if s.identifier == 'AO':
            return f'{a}.x'
        col = self.inp(n, 'Color', path)
        return self.var('vec3', f'({col}) * {a}.x')

    def n_BEVEL(self, n, s, path):
        return self.g(self.L.ray_key(n, path)) + '.xyz'

    # -- normals ------------------------------------------------------------------------------------------------
    def n_BUMP(self, n, s, path):
        Nin = self.var('vec3', self.inp(n, 'Normal', path))
        strength = self.var('float', f'max({self.inp(n, "Strength", path)}, 0.0)')
        dist = self.var('float', self.inp(n, 'Distance', path))
        fws = n.inputs.get('Filter Width')
        if fws is not None and fws.is_linked:
            raise Unsupported('a linked bump filter width')
        fw = max(float(fws.default_value) if fws is not None else 0.1, 1e-4)
        if n.invert:
            dist = self.var('float', f'(-{dist})')
        hs = n.inputs['Height']
        if not hs.is_linked:
            return Nin
        if self.parent is not None:
            raise Unsupported('a bump inside a bump height')
        fname = self.root._height_fn(n, hs, path)
        step = fw / self.L.res
        c = self.ctx
        hc = self.var('float', f'{fname}({c})')
        hx = self.var('float', f'{fname}(shift({c}, {_f(step)}, 0.0))')
        hy = self.var('float', f'{fname}(shift({c}, 0.0, {_f(step)}))')
        R = self._mat3(self.L.R)
        dx = self.var('vec3', f'{R} * ({self.g("dPdu")}.xyz * {_f(step)})')
        dy = self.var('vec3', f'{R} * ({self.g("dPdv")}.xyz * {_f(step)})')
        Rx = self.var('vec3', f'cross({dy}, {Nin})')
        Ry = self.var('vec3', f'cross({Nin}, {dx})')
        det = self.var('float', f'dot({dx}, {Rx})')
        surf = self.var('vec3', f'({hx} - {hc}) * {Rx} + ({hy} - {hc}) * {Ry}')
        no = self.var('vec3', f'abs({det}) * {Nin} - {dist} * sign({det}) * {surf}')
        no = self.var('vec3', f'(length({no}) > 1e-30 ? {no} / length({no}) : {Nin})')
        return self.var('vec3', f'unit3({strength} * {no} + (1.0 - {strength}) * {Nin})')

    def _height_fn(self, n, hs, path):
        key = ('H', n.name, path)
        for k, nm in self.funcs:
            if k == key:
                return nm
        nm = f'H{len(self.funcs)}'
        sub = Gen(self.mat, self.ob, self.L, ctx='c', parent=self)
        e = sub.sock_in(hs, path, 'VALUE')
        body = '\n'.join(sub.lines)
        self.funcs.append((key, nm))
        self.L.fn_src.append(f'float {nm}(Ctx c) {{\n{body}\n  return {e};\n}}\n')
        return nm

    def n_NORMAL_MAP(self, n, s, path):
        c = self.var('vec3', f'({self.inp(n, "Color", path)}) * 2.0 - 1.0')
        st = self.var('float', self.inp(n, 'Strength', path))
        N = self.g('N') + '.xyz'
        sp = n.space
        if sp == 'TANGENT':
            if n.uv_map and n.uv_map != self.L.bake_uv:
                raise Unsupported('a normal map on another UV map')
            T = self.g('T')
            B = self.var('vec3', f'{T}.w * cross({N}, {T}.xyz)')
            Nm = self.var('vec3', f'unit3({c}.x * {T}.xyz + {c}.y * {B} + {c}.z * {N})')
        elif sp == 'OBJECT':
            Nm = self.var('vec3', f'unit3({self._mat3(np.linalg.inv(self.L.R).T)} * {c})')
        elif sp == 'WORLD':
            Nm = self.var('vec3', f'unit3({c})')
        else:
            raise Unsupported('normal map ' + sp)
        return self.var('vec3', f'unit3({N} + ({Nm} - {N}) * {st})')

    def n_NORMAL(self, n, s, path):
        nv = np.array(n.outputs['Normal'].default_value[:3], np.float64)
        if s.identifier == 'Normal':
            return _v3(nv)
        v = self.inp(n, 'Normal', path)
        return self.var('float', f'-dot(unit3({v}), {_v3(nv)})')

    # -- closures --------------------------------------------------------------------------------------------------
    GLOW = {'COLOR': ('Base Color', 'Color'), 'ROUGH': ('Roughness',), 'METAL': ('Metallic',)}
    GLOW_DEF = {'COLOR': (0.8, 0.8, 0.8), 'ROUGH': (0.5, 0.5, 0.5), 'METAL': (0.0, 0.0, 0.0)}

    def shade_in(self, sock_in, path, kind):
        lk = next((lk for lk in sock_in.links if not lk.is_muted), None) if sock_in.is_linked else None
        if lk is None:
            return 'vec3(0.0)'
        if lk.from_socket.type != 'SHADER':
            raise Unsupported('a colour into a shader socket')
        return self.shade(lk.from_socket, path, kind)

    def shade(self, so, path, kind):
        n = so.node
        if n.mute:
            lk = next((lk for lk in n.internal_links if lk.to_socket == so), None)
            return self.shade_in(lk.from_socket, path, kind) if lk is not None else 'vec3(0.0)'
        t = n.type
        if t == 'REROUTE':
            return self.shade_in(n.inputs[0], path, kind)
        if t == 'GROUP':
            nt = n.node_tree
            go = next((x for x in nt.nodes if x.type == 'GROUP_OUTPUT' and x.is_active_output), None) if nt else None
            ins = next((x for x in go.inputs if x.identifier == so.identifier), None) if go else None
            return self.shade_in(ins, path + (n.name,), kind) if ins is not None else 'vec3(0.0)'
        if t == 'GROUP_INPUT':
            nt = self.mat.node_tree
            for nm in path[:-1]:
                nt = nt.nodes[nm].node_tree
            gnode = nt.nodes[path[-1]]
            si = next((x for x in gnode.inputs if x.identifier == so.identifier), None)
            return self.shade_in(si, path[:-1], kind) if si is not None else 'vec3(0.0)'
        if kind == 'ALPHA':
            if t == 'BSDF_TRANSPARENT':
                return 'vec3(0.0)'
            if t == 'BSDF_PRINCIPLED':
                return f'vec3({self.inp(n, "Alpha", path)})'
            if t == 'ADD_SHADER':
                return self.var('vec3', f'min({self.shade_in(n.inputs[0], path, kind)} + '
                                        f'{self.shade_in(n.inputs[1], path, kind)}, vec3(1.0))')
            if t.startswith('BSDF_') or t in ('EMISSION', 'HOLDOUT', 'SUBSURFACE_SCATTERING'):
                return 'vec3(1.0)'
        if t == 'MIX_SHADER':
            f = self.var('float', f'clamp({self.inp(n, 0, path)}, 0.0, 1.0)')
            a = self.shade_in(n.inputs[1], path, kind)
            b = self.shade_in(n.inputs[2], path, kind)
            return self.var('vec3', f'(1.0 - {f}) * {a} + {f} * {b}')
        if t == 'ADD_SHADER':
            return self.var('vec3', f'{self.shade_in(n.inputs[0], path, kind)} + '
                                    f'{self.shade_in(n.inputs[1], path, kind)}')
        if t == 'EMISSION':
            if kind == 'NORMAL':
                return 'vec3(0.0)'
            if kind in self.GLOW and not n.inputs['Strength'].is_linked:
                return 'vec3(0.0)'
            return self.var('vec3', f'({self.inp(n, "Color", path)}) * ({self.inp(n, "Strength", path)})')
        if t == 'HOLDOUT':
            return 'vec3(0.0)'
        if t.startswith('BSDF_') or t == 'SUBSURFACE_SCATTERING':
            if t in ('BSDF_HAIR', 'BSDF_HAIR_PRINCIPLED', 'BSDF_TOON', 'BSDF_RAY_PORTAL'):
                raise Unsupported(t)
            if kind in self.GLOW:
                src = next((n.inputs[k] for k in self.GLOW[kind] if n.inputs.get(k) is not None), None)
                if src is None:
                    return _v3(self.GLOW_DEF[kind])
                return self.var('vec3', self.sock_in(src, path, 'RGBA'))
            if kind == 'EMIT':
                if t == 'BSDF_PRINCIPLED':
                    return self.var('vec3', f'({self.inp(n, "Emission Color", path)}) * '
                                            f'({self.inp(n, "Emission Strength", path)})')
                return 'vec3(0.0)'
            if kind == 'NORMAL':
                if t in ('BSDF_TRANSPARENT', 'BSDF_HOLDOUT'):
                    return 'vec3(0.0)'
                nm = n.inputs.get('Normal')
                N = self.var('vec3', self.sock_in(nm, path) if nm is not None else self.g('N') + '.xyz')
                if t == 'BSDF_PRINCIPLED':
                    cw = self.var('float', self.inp(n, 'Coat Weight', path))
                    cn = self.var('vec3', self.inp(n, 'Coat Normal', path))
                    return self.var('vec3', f'({cw} > 1e-5 ? {N} + {cw} * {cn} : {N})')
                return N
        raise Unsupported(f'shader {n.bl_idname}')


class Layout:
    """What goes into the geometry texture (slots per texel) and the atlas (pictures, colour ramps)."""

    BASE = ('P', 'Po', 'N', 'No', 'Ng', 'uv', 'dPdu', 'dPdv', 'T')

    def __init__(self, g, ob, res):
        self.gm = g
        self.ob = ob
        self.res = res
        self.M = np.asarray(g.M, np.float64)
        self.R = np.asarray(g.R, np.float64)
        self.tex_loc = np.asarray(g.tex_loc, np.float64)
        self.tex_size = np.asarray(g.tex_size, np.float64)
        self.bake_uv, self.render_uv = g.bake_uv, g.render_uv
        self.slots = {k: i for i, k in enumerate(self.BASE)}
        self.attrs = {}
        self.rays = {}               # key -> (node, path)
        self.images = {}             # name -> (offset, w, h)
        self.atlas = []              # [(offset, array (k, 4))]
        self.atlas_n = 0
        self.ramps = {}
        self.fn_src = []

    def slot(self, key):
        if key not in self.slots:
            self.slots[key] = len(self.slots)
        return self.slots[key]

    def has_attr(self, name):
        return self.gm.attr(name) is not None

    def attr_type(self, name):
        return self.gm.attrs.get(name, (None, 'FLOAT_VECTOR', None))[1] if name in self.gm.attrs else 'FLOAT2'

    def ray_key(self, node, path):
        key = f'ray:{"/".join(path)}:{node.name}'
        self.rays[key] = (node, path)
        self.slot(key)
        return key

    def _put(self, arr):
        off = self.atlas_n
        self.atlas.append((off, arr))
        self.atlas_n += len(arr)
        return off

    def image(self, img):
        if img.name not in self.images:
            from .fast_shade import Images
            px, w, h = Images().get(img) if not hasattr(self, '_imgs') else self._imgs.get(img)
            off = self._put(np.asarray(px, np.float32).reshape(-1, 4))
            self.images[img.name] = (off, w, h)
        return self.images[img.name]

    def add_ramp(self, key, tab):
        self.ramps[key] = self._put(np.asarray(tab, np.float32).reshape(-1, 4))


def _tex(arr):
    """(TEXW x rows) RGBA32F texture of (n, 4) float32."""
    import gpu
    n = max(1, len(arr))
    rows = max(1, (n + TEXW - 1) // TEXW)
    full = np.zeros((rows * TEXW, 4), np.float32)
    full[:len(arr)] = arr
    return gpu.types.GPUTexture((TEXW, rows), format='RGBA32F', data=gpu.types.Buffer('FLOAT', full.size, full.ravel()))


def build(ev, mat, kinds, images, probes=None):
    """The compute shader's source for material ``mat`` and its inputs: (source, geometry (n, slots, 4), atlas
    (k, 4), kinds).  No GPU needed (the ray nodes are traced here, on the ray engine).  Raises Unsupported."""
    g = ev.g
    n = g.n
    nt = mat.node_tree
    outn = nt.get_output_node('CYCLES') or nt.get_output_node('ALL')
    if outn is None:
        raise Unsupported('no material output')
    L = Layout(g, ev.ob, g.res)
    L._imgs = images
    gen = Gen(mat, ev.ob, L, ctx='c')
    results = []
    if probes:                                    # (tests: the value of given (node, output socket, path) as rgb)
        kinds = [f'probe{j}' for j in range(len(probes))]
        for node, sock, path in probes:
            e, t = gen.out(node, sock, path)
            results.append(gen.var('vec3', gen.conv(e, t, 'VECTOR') if t in ('VALUE', 'INT', 'BOOLEAN') else e))
    for k in ([] if probes else kinds):
        if k == 'NORMAL' and outn.inputs['Displacement'].is_linked and \
                getattr(mat, 'displacement_method', 'BUMP') != 'DISPLACEMENT':
            raise Unsupported('a displacement bump')
        e = gen.shade_in(outn.inputs['Surface'], (), k)
        if k == 'NORMAL':
            e = gen.var('vec3', f'(length({e}) > 1e-12 ? {e} / length({e}) : {gen.g("N")}.xyz)')
        else:
            e = gen.var('vec3', e)
        results.append(e)
    # the ray nodes first (their values for the texture) - by the numpy / ray engine path itself
    slots = len(L.slots)
    geo = np.zeros((n, slots, 4), np.float32)
    geo[:, L.slots['P'], :3] = g.P
    geo[:, L.slots['Po'], :3] = g.Po
    geo[:, L.slots['N'], :3] = g.N
    geo[:, L.slots['No'], :3] = g.No
    geo[:, L.slots['Ng'], :3] = g.Ng
    uvb = g.uv.get(g.bake_uv)
    uvr = g.uv.get(g.render_uv)
    if uvb is not None:
        geo[:, L.slots['uv'], 0:2] = uvb
    if uvr is not None:
        geo[:, L.slots['uv'], 2:4] = uvr
    geo[:, L.slots['dPdu'], :3] = g.dPdu_o
    geo[:, L.slots['dPdv'], :3] = g.dPdv_o
    geo[:, L.slots['T'], :3] = g.T
    geo[:, L.slots['T'], 3] = g.S
    for key, idx in L.slots.items():
        if key.startswith('attr:'):
            a = g.attr(key[5:])
            if a is not None:
                geo[:, idx, :] = a
        elif key.startswith('ray:'):
            node, path = L.rays[key]
            sock = node.outputs['AO'] if node.type == 'AMBIENT_OCCLUSION' else node.outputs['Normal']
            v = np.asarray(ev.out(node, sock, path)[0], np.float32)
            if v.ndim == 1:
                geo[:, idx, 0] = v
            else:
                geo[:, idx, :3] = v
    src_body = '\n'.join(gen.lines)
    writes = '\n'.join(f'  imageStore(result, ivec2((k{j} * count + c.i) % TEXW, (k{j} * count + c.i) / TEXW), '
                       f'vec4({r}, 1.0));'.replace(f'k{j}', str(j)) for j, r in enumerate(results))
    shift = ('Ctx shift(Ctx c, float du, float dv) {\n  Ctx o = c;\n'
             f'  vec3 d = fetch(geo, c.i * SLOTS + {L.slots["dPdu"]}).xyz * du + '
             f'fetch(geo, c.i * SLOTS + {L.slots["dPdv"]}).xyz * dv;\n'
             '  o.Po = c.Po + d;\n'
             f'  o.P = {Gen._mat3(gen, L.R)} * o.Po + {_v3(L.M[:3, 3])};\n'
             '  o.uvb = c.uvb + vec2(du, dv);\n'
             + ('  o.uvr = c.uvr + vec2(du, dv);\n' if g.bake_uv == g.render_uv else '') +
             '  return o;\n}\n')
    main = ('void main() {\n  int i = int(gl_GlobalInvocationID.x) + offset;\n  if (i >= count) return;\n'
            '  Ctx c;\n  c.i = i;\n'
            f'  c.P = fetch(geo, i * SLOTS + {L.slots["P"]}).xyz;\n'
            f'  c.Po = fetch(geo, i * SLOTS + {L.slots["Po"]}).xyz;\n'
            f'  vec4 uvs = fetch(geo, i * SLOTS + {L.slots["uv"]});\n'
            '  c.uvb = uvs.xy;\n  c.uvr = uvs.zw;\n'
            f'{src_body}\n{writes}\n}}\n')
    src = (HELPERS + shift + '\n'.join(L.fn_src) + main).replace('SLOTS', str(slots))
    atlas = np.zeros((max(1, L.atlas_n), 4), np.float32)
    for off, arr in L.atlas:
        atlas[off:off + len(arr)] = arr
    return src, geo, atlas, kinds


def evaluate(ev, mat, kinds, images, probes=None):
    """The maps ``kinds`` of material ``mat`` over the texels of the Eval ``ev`` (its Geo, its ray scenes) on the GPU.
    {kind: (n, 3) float32}.  Raises Unsupported (then numpy as before)."""
    import gpu
    from gpu.types import GPUShaderCreateInfo
    src, geo, atlas, kinds = build(ev, mat, kinds, images, probes)
    n, slots = geo.shape[0], geo.shape[1]
    key = hashlib.sha1(src.encode()).hexdigest()
    sh = _CACHE.get(key)
    if sh is None:
        info = GPUShaderCreateInfo()
        info.local_group_size(64, 1, 1)
        info.define('TEXW', str(TEXW))
        info.sampler(0, 'FLOAT_2D', 'geo')
        info.sampler(1, 'FLOAT_2D', 'atlas')
        info.image(0, 'RGBA32F', 'FLOAT_2D', 'result', qualifiers={'WRITE'})
        info.push_constant('INT', 'count')
        info.push_constant('INT', 'offset')
        info.compute_source(src)
        try:
            sh = gpu.shader.create_from_info(info)
        except Exception as ex:
            STATS['last_error'] = str(ex)
            raise Unsupported(f'GPU shader did not compile ({ex})')
        _CACHE[key] = sh
        STATS['compiled'] += 1
    else:
        STATS['reused'] += 1
    ta = _tex(atlas)

    batch = max(1024, min(n, (MAXROWS[0] * TEXW) // max(slots, len(kinds))))
    outs = [np.empty((n, 3), np.float32) for _ in kinds]
    for b0 in range(0, n, batch):
        m = min(batch, n - b0)
        tg = _tex(geo[b0:b0 + m].reshape(-1, 4))
        rows = max(1, (len(kinds) * m + TEXW - 1) // TEXW)
        res = gpu.types.GPUTexture((TEXW, rows), format='RGBA32F')
        sh.bind()
        sh.uniform_sampler('geo', tg)
        sh.uniform_sampler('atlas', ta)
        sh.image('result', res)
        sh.uniform_int('count', m)
        chunk = 1 << 17
        for off in range(0, m, chunk):
            sh.uniform_int('offset', off)
            gpu.compute.dispatch(sh, (min(chunk, m - off) + 63) // 64, 1, 1)
        buf = res.read()
        try:
            a = np.frombuffer(buf, np.float32)
        except (TypeError, ValueError):
            a = np.asarray(buf.to_list(), np.float32)
        a = a.reshape(-1, 4)
        for j in range(len(kinds)):
            outs[j][b0:b0 + m] = a[j * m:(j + 1) * m, :3]
        del tg, res
    STATS['materials'] += 1
    return {k: outs[j] for j, k in enumerate(kinds)}


def timed(fn, *a, **k):
    t = time.time()
    r = fn(*a, **k)
    return r, time.time() - t
