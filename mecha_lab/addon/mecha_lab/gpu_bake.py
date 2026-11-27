"""0.24.346 GPU Bake (user: "GPU도 하구" / "빨리 짜줘 gpu" / "나 gpu가 5090인데 안 쓰면 아깝잖아"): the ray work of
Fast Bake on the graphics card - Blender's own GPU module (a compute shader, no extra install), the scene's BVH (built
by Mecha Lab's engine) and the rays' points / normals sent as float textures, the answer read back.

The same rays as the C engine (the same stratified cosine samples, turned by the same hash per texel, the same
self-skip and offset), so the result is the same map - only faster on a big card.  Long jobs are cut into pieces (a
driver stops a GPU job that runs for seconds).  No GPU / no context (a background run) / anything unexpected: None -
the caller uses the C engine."""
from __future__ import annotations

import ctypes
import time

import numpy as np

TEX_W = 4096
CHUNK = 1 << 18                   # (rays a dispatch at 64 samples: well under a second on any recent card)
_STATE = {'shader': None, 'failed': None, 'last': None}

COMMON_SRC = r'''
uint hash32(uint x) { x ^= x >> 16u; x *= 0x7feb352du; x ^= x >> 15u; x *= 0x846ca68bu; x ^= x >> 16u; return x; }
float rnd(inout uint s) { s = hash32(s + 0x9e3779b9u); return float(s >> 8u) * (1.0 / 16777216.0); }
vec4 fetch(sampler2D t, int i) { return texelFetch(t, ivec2(i % TEXW, i / TEXW), 0); }

bool hit_box(vec3 o, vec3 inv, vec3 mn, vec3 mx, float tmax) {
  vec3 t0 = (mn - o) * inv, t1 = (mx - o) * inv;
  vec3 a = min(t0, t1), b = max(t0, t1);
  float tn = max(max(a.x, a.y), a.z), tf = min(min(b.x, b.y), b.z);
  return tf >= max(tn, 0.0) && tn <= tmax;
}

bool occluded(vec3 o, vec3 d, float tmax, int skip) {
  vec3 inv;
  for (int a = 0; a < 3; a++) inv[a] = 1.0 / (abs(d[a]) > 1e-20 ? d[a] : (d[a] < 0.0 ? -1e-20 : 1e-20));
  int stack[64];
  int sp = 0;
  vec4 r0 = fetch(nodes, 0), r1 = fetch(nodes, 1);
  if (!hit_box(o, inv, r0.xyz, r1.xyz, tmax)) return false;
  stack[sp++] = 0;
  while (sp > 0) {
    int ni = stack[--sp];
    vec4 n0 = fetch(nodes, ni * 2), n1 = fetch(nodes, ni * 2 + 1);
    int cnt = int(n1.w), left = int(n0.w);
    if (cnt > 0) {
      for (int k = left; k < left + cnt; k++) {
        vec4 p0 = fetch(tris, k * 3), p1 = fetch(tris, k * 3 + 1), p2 = fetch(tris, k * 3 + 2);
        if (int(p0.w) == skip) continue;
        vec3 e1 = p1.xyz - p0.xyz, e2 = p2.xyz - p0.xyz;
        vec3 pv = cross(d, e2);
        float det = dot(e1, pv);
        if (abs(det) < 1e-20) continue;
        float id = 1.0 / det;
        vec3 tv = o - p0.xyz;
        float u = dot(tv, pv) * id;
        if (u < 0.0 || u > 1.0) continue;
        vec3 qv = cross(tv, e1);
        float v = dot(d, qv) * id;
        if (v < 0.0 || u + v > 1.0) continue;
        float tt = dot(e2, qv) * id;
        if (tt > 0.0 && tt <= tmax) return true;
      }
    } else {
      int l = left, r = -cnt;
      if (sp > 60) continue;
      vec4 l0 = fetch(nodes, l * 2), l1 = fetch(nodes, l * 2 + 1);
      vec4 q0 = fetch(nodes, r * 2), q1 = fetch(nodes, r * 2 + 1);
      if (hit_box(o, inv, l0.xyz, l1.xyz, tmax)) stack[sp++] = l;
      if (hit_box(o, inv, q0.xyz, q1.xyz, tmax)) stack[sp++] = r;
    }
  }
  return false;
}

void frame(vec3 n, out vec3 t, out vec3 b) {
  if (n.x != n.y || n.x != n.z) t = vec3(n.z - n.y, n.x - n.z, n.y - n.x);
  else t = vec3(n.z - n.y, n.x + n.z, -n.x - n.y);
  t = normalize(t);
  b = cross(n, t);
}
'''

AO_SRC = r'''
void main() {
  int i = int(gl_GlobalInvocationID.x) + offset;
  if (i >= count) return;
  vec4 pp = fetch(pts, i), nn = fetch(nrm, i), gg = fetch(ngs, i);
  vec3 P = pp.xyz, n = nn.xyz, g = gg.xyz;
  int skip = int(pp.w);
  uint s = uint(nn.w) | (uint(gg.w) << 16u);
  if (inside != 0) n = -n;
  n = normalize(n);
  float sgn = dot(g, n) < 0.0 ? -1.0 : 1.0;
  float eps = mode == 1 ? dist * 1e-4 + 1e-7 : 1e-5 * (1.0 + abs(P.x) + abs(P.y) + abs(P.z));
  vec3 O = P + sgn * g * eps;
  int tot = 0;
  vec3 ta, tb;
  frame(n, ta, tb);
  int sq = max(1, int(sqrt(float(samples))));
  float r0 = rnd(s), r1 = rnd(s);
  int open = 0;
  for (int k = 0; k < samples; k++) {
    float u1, u2;
    if (k < sq * sq) { u1 = (float(k % sq) + 0.5) / float(sq); u2 = (float(k / sq) + 0.5) / float(sq); }
    else { u1 = rnd(s); u2 = rnd(s); }
    u1 += r0; if (u1 >= 1.0) u1 -= 1.0;
    u2 += r1; if (u2 >= 1.0) u2 -= 1.0;
    float rr = sqrt(u1), ph = 6.2831853 * u2;
    vec3 d = ta * (rr * cos(ph)) + tb * (rr * sin(ph)) + n * sqrt(max(0.0, 1.0 - u1));
    if (mode == 1 && dot(d, sgn * g) <= 0.0) continue;     /* (the high poly's AO: not under its own face) */
    tot++;
    if (!occluded(O, d, dist, skip)) open++;
  }
  float v = mode == 1 ? (tot > 0 ? float(open) / float(tot) : 1.0) : float(open) / float(max(samples, 1));
  imageStore(result, ivec2(i % TEXW, i / TEXW), vec4(v, 0.0, 0.0, 1.0));
}
'''


BEVEL_SRC = r"""
float cubic_eval(float R, float r) {
  if (r >= R) return 0.0;
  float R5 = R * R * R * R * R, f = R - r;
  return 10.0 * f * f * f / (R5 * 3.14159265);
}
float quintic_root(float xi) {
  float x = 0.25;
  for (int i = 0; i < 10; i++) {
    float x2 = x * x, x3 = x2 * x, nx = 1.0 - x;
    float f = 10.0 * x2 - 20.0 * x3 + 15.0 * x2 * x2 - 4.0 * x2 * x3 - xi;
    float f_ = 20.0 * (x * nx) * (nx * nx);
    if (abs(f) < 1e-6 || f_ == 0.0) break;
    x = clamp(x - f / f_, 0.0, 1.0);
  }
  return x;
}

#define CAP 8
int hk[CAP]; float htt[CAP], hu[CAP], hv[CAP];

int hits_all(vec3 o, vec3 d, float tmax) {
  vec3 inv;
  for (int a = 0; a < 3; a++) inv[a] = 1.0 / (abs(d[a]) > 1e-20 ? d[a] : (d[a] < 0.0 ? -1e-20 : 1e-20));
  int stack[64];
  int sp = 0, nh = 0;
  vec4 r0 = fetch(nodes, 0), r1 = fetch(nodes, 1);
  if (!hit_box(o, inv, r0.xyz, r1.xyz, tmax)) return 0;
  stack[sp++] = 0;
  while (sp > 0) {
    int ni = stack[--sp];
    vec4 n0 = fetch(nodes, ni * 2), n1 = fetch(nodes, ni * 2 + 1);
    int cnt = int(n1.w), left = int(n0.w);
    if (cnt > 0) {
      for (int k = left; k < left + cnt; k++) {
        vec4 p0 = fetch(tris, k * 3), p1 = fetch(tris, k * 3 + 1), p2 = fetch(tris, k * 3 + 2);
        vec3 e1 = p1.xyz - p0.xyz, e2 = p2.xyz - p0.xyz;
        vec3 pv = cross(d, e2);
        float det = dot(e1, pv);
        if (abs(det) < 1e-20) continue;
        float id = 1.0 / det;
        vec3 tv = o - p0.xyz;
        float u = dot(tv, pv) * id;
        if (u < 0.0 || u > 1.0) continue;
        vec3 qv = cross(tv, e1);
        float v = dot(d, qv) * id;
        if (v < 0.0 || u + v > 1.0) continue;
        float tt = dot(e2, qv) * id;
        if (tt > 0.0 && tt <= tmax) {
          if (nh < CAP) { hk[nh] = k; htt[nh] = tt; hu[nh] = u; hv[nh] = v; }
          nh++;
        }
      }
    } else {
      int l = left, r = -cnt;
      if (sp > 60) continue;
      vec4 l0 = fetch(nodes, l * 2), l1 = fetch(nodes, l * 2 + 1);
      vec4 q0 = fetch(nodes, r * 2), q1 = fetch(nodes, r * 2 + 1);
      if (hit_box(o, inv, l0.xyz, l1.xyz, tmax)) stack[sp++] = l;
      if (hit_box(o, inv, q0.xyz, q1.xyz, tmax)) stack[sp++] = r;
    }
  }
  return nh;
}

void main() {
  int i = int(gl_GlobalInvocationID.x) + offset;
  if (i >= count) return;
  vec4 pp = fetch(pts, i), nn = fetch(nrm, i), gg = fetch(ngs, i);
  vec3 P = pp.xyz, n0 = nn.xyz, Ng = gg.xyz;
  float R = fetch(rad, i).x;
  uint s = uint(nn.w) | (uint(gg.w) << 16u);
  vec3 outn = n0;
  if (R > 0.0) {
    vec3 T0, B0;
    frame(Ng, T0, B0);
    vec3 sum = vec3(0.0);
    int sq = max(1, int(sqrt(float(samples))));
    float r0 = rnd(s), r1 = rnd(s);
    for (int k = 0; k < samples; k++) {
      float du, dv;
      if (k < sq * sq) { du = (float(k % sq) + 0.5) / float(sq); dv = (float(k / sq) + 0.5) / float(sq); }
      else { du = rnd(s); dv = rnd(s); }
      du += r0; if (du >= 1.0) du -= 1.0;
      dv += r1; if (dv >= 1.0) dv -= 1.0;
      vec3 dN, dT, dB; float pN, pT, pB;
      if (du < 0.5) { dN = Ng; dT = T0; dB = B0; pN = 0.5; pT = 0.25; pB = 0.25; du *= 2.0; }
      else if (du < 0.75) { dN = T0; dT = Ng; dB = B0; pN = 0.25; pT = 0.5; pB = 0.25; du = (du - 0.5) * 4.0; }
      else { dN = B0; dT = T0; dB = Ng; pN = 0.25; pT = 0.25; pB = 0.5; du = (du - 0.75) * 4.0; }
      float phi = 6.2831853 * du;
      float dr = quintic_root(dv) * R;
      float hgt = sqrt(max(0.0, R * R - dr * dr));
      vec3 O = P + dN * hgt + dr * cos(phi) * dT + dr * sin(phi) * dB, D = -dN;
      int nh = hits_all(O, D, 2.0 * hgt);
      int ne = min(nh, CAP);
      float disk_pdf = cubic_eval(R, dr);
      if (disk_pdf <= 0.0) continue;
      for (int q = 0; q < ne; q++) {
        int kk = hk[q];
        vec4 p0 = fetch(tris, kk * 3), p1 = fetch(tris, kk * 3 + 1), p2 = fetch(tris, kk * 3 + 2);
        vec3 hg = normalize(cross(p1.xyz - p0.xyz, p2.xyz - p0.xyz));
        float w0 = 1.0 - hu[q] - hv[q];
        vec3 hn = normalize(w0 * fetch(tnrm, kk * 3).xyz + hu[q] * fetch(tnrm, kk * 3 + 1).xyz
                            + hv[q] * fetch(tnrm, kk * 3 + 2).xyz);
        float qN = pN * abs(dot(dN, hg)), qT = pT * abs(dot(dT, hg)), qB = pB * abs(dot(dB, hg));
        float den = qN * qN + qT * qT + qB * qB;
        if (den <= 0.0) continue;
        float w = qN / den;
        if (nh > CAP) w *= float(nh) / float(CAP);
        float r = length(O + D * htt[q] - P);
        w *= cubic_eval(R, r) / disk_pdf;
        sum += w * hn;
      }
    }
    float l = length(sum);
    if (l >= 1e-20) outn = sum / l;
  }
  imageStore(result, ivec2(i % TEXW, i / TEXW), vec4(outn, 1.0));
}
"""


_SHADERS = {}


def _make(key, main_src, samplers, out_format, ints, floats=()):
    """A compute shader (made once): COMMON_SRC + ``main_src``; ``samplers`` float textures in order, one image
    ``result`` (``out_format``), push constants ``ints`` / ``floats``.  None when it cannot be made."""
    if key in _SHADERS:
        return _SHADERS[key]
    sh = None
    try:
        import gpu
        from gpu.types import GPUShaderCreateInfo
        info = GPUShaderCreateInfo()
        info.local_group_size(64, 1, 1)
        info.define('TEXW', str(TEX_W))
        for i, nm in enumerate(samplers):
            info.sampler(i, 'FLOAT_2D', nm)
        info.image(0, out_format, 'FLOAT_2D', 'result', qualifiers={'WRITE'})
        for nm in ints:
            info.push_constant('INT', nm)
        for nm in floats:
            info.push_constant('FLOAT', nm)
        info.compute_source(COMMON_SRC + main_src)
        sh = gpu.shader.create_from_info(info)
    except Exception as ex:                          # (no GPU, background mode, an old driver ...)
        _STATE['failed'] = f'{type(ex).__name__}: {ex}'
        sh = None
    _SHADERS[key] = sh
    return sh


def _shader():
    return _make('ao', AO_SRC, ('nodes', 'tris', 'pts', 'nrm', 'ngs'), 'R32F',
                 ('count', 'offset', 'samples', 'inside', 'mode'), ('dist',))


def _bevel_shader():
    return _make('bevel', BEVEL_SRC, ('nodes', 'tris', 'tnrm', 'pts', 'nrm', 'ngs', 'rad'), 'RGBA32F',
                 ('count', 'offset', 'samples'))


def available():
    """True when this Blender can run our compute shader (a GPU context exists)."""
    return _shader() is not None


def why_not():
    return _STATE['failed'] or ''


def _texture(arr, rows_of=4):
    """A (TEX_W x rows) RGBA32F texture holding ``arr`` ((n, 4) float32), row by row."""
    import gpu
    n = len(arr)
    rows = max(1, (n + TEX_W - 1) // TEX_W)
    full = np.zeros((rows * TEX_W, 4), np.float32)
    full[:n] = arr
    buf = gpu.types.Buffer('FLOAT', full.size, full.ravel())
    return gpu.types.GPUTexture((TEX_W, rows), format='RGBA32F', data=buf)


class Scene:
    """A C-engine scene's BVH on the GPU (nodes + triangles as textures)."""

    def __init__(self, L, scene_ptr):
        nn, nt = ctypes.c_int(0), ctypes.c_int(0)
        L.mbake_scene_size(scene_ptr, ctypes.byref(nn), ctypes.byref(nt))
        nodes = np.zeros(nn.value * 8, np.float32)
        tris = np.zeros(nt.value * 12, np.float32)
        FP = ctypes.POINTER(ctypes.c_float)
        L.mbake_scene_export(scene_ptr, nodes.ctypes.data_as(FP), tris.ctypes.data_as(FP))
        self.nodes = _texture(nodes.reshape(-1, 4))
        self.tris = _texture(tris.reshape(-1, 4))
        self.nn, self.nt = nn.value, nt.value
        self._L, self._ptr, self._tnrm = L, scene_ptr, None

    def tnrm(self):
        """The triangles' corner normals (leaf order) - made when the Bevel first needs them."""
        if self._tnrm is None:
            nrm = np.zeros(self.nt * 12, np.float32)
            L = self._L
            L.mbake_scene_export_normals.restype = None
            L.mbake_scene_export_normals.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float)]
            L.mbake_scene_export_normals(self._ptr, nrm.ctypes.data_as(ctypes.POINTER(ctypes.c_float)))
            self._tnrm = _texture(nrm.reshape(-1, 4))
        return self._tnrm


_SCENES = {}


def scene_for(L, scene_ptr):
    key = int(scene_ptr or 0)
    sc = _SCENES.get(key)
    if sc is None:
        sc = Scene(L, scene_ptr)
        _SCENES[key] = sc
    return sc


def forget(scene_ptr):
    _SCENES.pop(int(scene_ptr or 0), None)


def ao(L, scene_ptr, P, N, Ng, tri, seeds, samples, dist, inside=False, mode=0):
    """The AO of points ``P`` (n, 3) with normals ``N`` / geometric normals ``Ng`` on the GPU (each ray skipping its
    own triangle ``tri`` (n,) or none) - as the C engine's mbake_ao.  (n,) float32, or None (no GPU)."""
    sh = _shader()
    if sh is None or not scene_ptr:
        return None
    try:
        import gpu
        t0 = time.time()
        n = len(P)
        sc = scene_for(L, scene_ptr)
        s = np.asarray(seeds, np.uint32) if seeds is not None else \
            ((np.arange(n, dtype=np.uint64) * 9781 + 7) % (2 ** 32)).astype(np.uint32)
        pts = np.empty((n, 4), np.float32)
        pts[:, :3] = P
        pts[:, 3] = tri if tri is not None else -1
        nrm = np.empty((n, 4), np.float32)
        nrm[:, :3] = N
        nrm[:, 3] = (s & 0xFFFF).astype(np.float32)
        ngs = np.empty((n, 4), np.float32)
        ngs[:, :3] = Ng
        ngs[:, 3] = (s >> 16).astype(np.float32)
        tp, tn, tg = _texture(pts), _texture(nrm), _texture(ngs)
        rows = max(1, (n + TEX_W - 1) // TEX_W)
        res = gpu.types.GPUTexture((TEX_W, rows), format='R32F')
        sh.bind()
        sh.uniform_sampler('nodes', sc.nodes)
        sh.uniform_sampler('tris', sc.tris)
        sh.uniform_sampler('pts', tp)
        sh.uniform_sampler('nrm', tn)
        sh.uniform_sampler('ngs', tg)
        sh.image('result', res)
        sh.uniform_int('count', n)
        sh.uniform_int('samples', int(samples))
        sh.uniform_int('inside', 1 if inside else 0)
        sh.uniform_int('mode', int(mode))
        sh.uniform_float('dist', float(dist))
        chunk = max(4096, int(CHUNK * 64 / max(int(samples), 1)))
        for off in range(0, n, chunk):
            sh.uniform_int('offset', off)
            m = min(chunk, n - off)
            gpu.compute.dispatch(sh, (m + 63) // 64, 1, 1)
        out = _read(res, n)
        _STATE['last'] = (n, int(samples), time.time() - t0)
        return out
    except Exception as ex:
        _STATE['failed'] = f'{type(ex).__name__}: {ex}'
        return None


def _read(tex, n):
    buf = tex.read()
    try:
        a = np.frombuffer(buf, np.float32)
    except (TypeError, ValueError):
        a = np.asarray(buf.to_list(), np.float32)
    return a.reshape(-1)[:n].copy()


def _seed_tex(n, N, Ng, seeds):
    s = np.asarray(seeds, np.uint32) if seeds is not None else \
        ((np.arange(n, dtype=np.uint64) * 2654435761 + 3) % (2 ** 32)).astype(np.uint32)
    nrm = np.empty((n, 4), np.float32)
    nrm[:, :3] = N
    nrm[:, 3] = (s & 0xFFFF).astype(np.float32)
    ngs = np.empty((n, 4), np.float32)
    ngs[:, :3] = Ng
    ngs[:, 3] = (s >> 16).astype(np.float32)
    return _texture(nrm), _texture(ngs)


def bevel(L, scene_ptr, P, N, Ng, radius, seeds, samples):
    """0.24.348 the Bevel node's normal at points ``P`` on the GPU - as the C engine's mbake_bevel.  (n, 3) or None."""
    sh = _bevel_shader()
    if sh is None or not scene_ptr or L.mbake_version() < 10:
        return None
    try:
        import gpu
        t0 = time.time()
        n = len(P)
        sc = scene_for(L, scene_ptr)
        pts = np.zeros((n, 4), np.float32)
        pts[:, :3] = P
        rad = np.zeros((n, 4), np.float32)
        rad[:, 0] = radius
        tn, tg = _seed_tex(n, N, Ng, seeds)
        tp, tr = _texture(pts), _texture(rad)
        rows = max(1, (n + TEX_W - 1) // TEX_W)
        res = gpu.types.GPUTexture((TEX_W, rows), format='RGBA32F')
        sh.bind()
        for nm, tx in (('nodes', sc.nodes), ('tris', sc.tris), ('tnrm', sc.tnrm()), ('pts', tp), ('nrm', tn),
                       ('ngs', tg), ('rad', tr)):
            sh.uniform_sampler(nm, tx)
        sh.image('result', res)
        sh.uniform_int('count', n)
        sh.uniform_int('samples', int(samples))
        chunk = max(4096, int(CHUNK * 16 / max(int(samples), 1)))
        for off in range(0, n, chunk):
            sh.uniform_int('offset', off)
            gpu.compute.dispatch(sh, (min(chunk, n - off) + 63) // 64, 1, 1)
        buf = res.read()
        try:
            a = np.frombuffer(buf, np.float32)
        except (TypeError, ValueError):
            a = np.asarray(buf.to_list(), np.float32)
        out = a.reshape(-1, 4)[:n, :3].copy()
        _STATE['last'] = (n, int(samples), time.time() - t0)
        return out
    except Exception as ex:
        _STATE['failed'] = f'{type(ex).__name__}: {ex}'
        return None
