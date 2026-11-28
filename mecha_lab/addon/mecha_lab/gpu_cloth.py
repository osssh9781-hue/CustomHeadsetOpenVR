"""0.24.359 GPU cloth - a TEST (user: "GPU 한번 먼저 테스트 해 봐"): a whole frame of the position-based cloth
(cloth_pbd.Cloth) on the graphics card with Blender's own GPU module (compute shaders, float textures, the way GPU
Bake works), the points read back once a frame.

Every point is one GPU thread that walks its own constraints (the edges, the bending pairs and the wide-bending rings
of ``Cloth``, kept per point - nobody writes another point), so one pass is ONE dispatch however many sets there
are; then the pins and the grid collider (the same narrow-band distance grid as ``GridCollider``) in the same
thread.  The passes are one Jacobi over all the constraints at once (the CPU does the sets one after another), and
the card counts in float32 - so the cloth folds a little differently from the CPU one; this module is for measuring
(``mch.gpu_cloth_check``), not yet wired into the tools.

No GPU / no context (a background run) / anything unexpected: ``GPUCloth`` raises, ``available()`` is False."""
from __future__ import annotations

import time

import numpy as np

TEX_W = 4096
_STATE = {'failed': None}
_SH = {}

COMMON = r'''
vec4 fetch(sampler2D t, int i) { return texelFetch(t, ivec2(i % TEXW, i / TEXW), 0); }
'''

PREDICT = r'''
void main() {
  int i = int(gl_GlobalInvocationID.x);
  if (i >= count) return;
  vec4 c = fetch(cur, i), p = fetch(prev, i), a = fetch(init, i), info = fetch(pinfo, i);
  vec3 vel = (c.xyz - p.xyz) * (1.0 - damping);
  if (maxstep > 0.0) { float l = length(vel); if (l > maxstep) vel *= maxstep / l; }
  vec3 o = c.xyz + vel + vec3(gx, gy, gz);
  float pin = info.z;
  o = o * (1.0 - pin) + a.xyz * pin;
  imageStore(result, ivec2(i % TEXW, i / TEXW), vec4(o, c.w));
}
'''

SOLVE = r'''
void main() {
  int i = int(gl_GlobalInvocationID.x);
  if (i >= count) return;
  vec4 me = fetch(cur, i), info = fetch(pinfo, i), a = fetch(init, i);
  int s = int(info.x), n = int(info.y);
  vec3 p = me.xyz, acc = vec3(0.0);
  float wi = me.w;
  for (int k = s; k < s + n; k++) {
    vec4 e = fetch(ent, k);
    vec4 o = fetch(cur, int(e.x));
    vec3 d = o.xyz - p;
    float L = max(length(d), 1e-12);
    float c = clamp((L - e.y) / L * e.z * sor, -0.5, 0.5);
    acc += d * (c * wi / (wi + o.w));
  }
  vec3 q = p + (n > 0 ? acc / float(n) : vec3(0.0));
  q = q * (1.0 - info.z) + a.xyz * info.z;
  if (use_grid != 0) {
    vec3 f = (q - vec3(ox, oy, oz)) / cell - 0.5;
    ivec3 i0 = ivec3(floor(f));
    vec3 t = f - vec3(i0);
    bool inside = all(greaterThanEqual(i0, ivec3(0))) && all(lessThan(i0 + 1, ivec3(dx, dy, dz)));
    if (inside) {
      float dist = 0.0; vec3 g = vec3(0.0);
      for (int cx = 0; cx < 2; cx++) for (int cy = 0; cy < 2; cy++) for (int cz = 0; cz < 2; cz++) {
        float w = (cx == 1 ? t.x : 1.0 - t.x) * (cy == 1 ? t.y : 1.0 - t.y) * (cz == 1 ? t.z : 1.0 - t.z);
        int idx = (i0.x + cx) * dy * dz + (i0.y + cy) * dz + (i0.z + cz);
        vec4 gc = fetch(grid, idx);
        dist += w * gc.w; g += w * gc.xyz;
      }
      if (dist < margin) { float l = length(g); if (l > 1e-9) q += g / l * (margin - dist); }
    }
  }
  imageStore(result, ivec2(i % TEXW, i / TEXW), vec4(q, me.w));
}
'''


def _make(key, src, samplers, ints, floats):
    if key in _SH:
        return _SH[key]
    sh = None
    try:
        import gpu
        from gpu.types import GPUShaderCreateInfo
        info = GPUShaderCreateInfo()
        info.local_group_size(64, 1, 1)
        info.define('TEXW', str(TEX_W))
        for k, nm in enumerate(samplers):
            info.sampler(k, 'FLOAT_2D', nm)
        info.image(0, 'RGBA32F', 'FLOAT_2D', 'result', qualifiers={'WRITE'})
        for nm in ints:
            info.push_constant('INT', nm)
        for nm in floats:
            info.push_constant('FLOAT', nm)
        info.compute_source(COMMON + src)
        sh = gpu.shader.create_from_info(info)
    except Exception as ex:                          # noqa: BLE001  (no GPU, background mode, an old driver ...)
        _STATE['failed'] = f'{type(ex).__name__}: {ex}'
        sh = None
    _SH[key] = sh
    return sh


def _predict():
    return _make('predict', PREDICT, ('cur', 'prev', 'init', 'pinfo'), ('count',), ('damping', 'maxstep', 'gx', 'gy', 'gz'))


def _solve():
    return _make('solve', SOLVE, ('cur', 'pinfo', 'init', 'ent', 'grid'),
                 ('count', 'use_grid', 'dx', 'dy', 'dz'), ('sor', 'cell', 'margin', 'ox', 'oy', 'oz'))


def available():
    return _predict() is not None and _solve() is not None


def why_not():
    return _STATE['failed'] or ''


def _tex(arr):
    import gpu
    arr = np.asarray(arr, np.float32).reshape(-1, 4)
    n = len(arr)
    rows = max(1, (n + TEX_W - 1) // TEX_W)
    full = np.zeros((rows * TEX_W, 4), np.float32)
    full[:n] = arr
    buf = gpu.types.Buffer('FLOAT', full.size, full.ravel())
    return gpu.types.GPUTexture((TEX_W, rows), format='RGBA32F', data=buf)


class GPUCloth:
    """``cloth`` (cloth_pbd.Cloth) on the GPU.  ``grid``: a cloth_pbd.GridCollider (or None), ``margin``: its push
    distance.  ``step()`` runs one frame on the card; ``read()`` gives the points back (N, 3)."""

    def __init__(self, cloth, grid=None, margin=0.0):
        if not available():
            raise RuntimeError('GPU cloth: ' + (why_not() or 'no GPU'))
        c = cloth
        n = c.n
        if n >= (1 << 24):
            raise RuntimeError('GPU cloth: too many points')
        sets = [(c.edges, c.rest_e * c.scale_e, float(c.stretch_k))]
        if c.bend > 0 and len(c.bends):
            sets.append((c.bends, c.rest_b * c.scale_b, float(c.bend)))
        if c.far and c.far_scale > 0:
            sc = float(np.mean(c.scale_e)) if np.ndim(c.scale_e) else float(c.scale_e)
            for pairs, rest, st in c.far:
                sets.append((pairs, rest * sc, float(st) * c.far_scale * c.stretch_k))
        own, oth, rst, kk = [], [], [], []
        for pairs, rest, k in sets:
            pairs = np.asarray(pairs, np.int64)
            rest = np.broadcast_to(np.asarray(rest, np.float64), (len(pairs),))
            own += [pairs[:, 0], pairs[:, 1]]
            oth += [pairs[:, 1], pairs[:, 0]]
            rst += [rest, rest]
            kk += [np.full(len(pairs), k), np.full(len(pairs), k)]
        own, oth = np.concatenate(own), np.concatenate(oth)
        rst, kk = np.concatenate(rst), np.concatenate(kk)
        order = np.argsort(own, kind='stable')
        cnt = np.bincount(own, minlength=n)
        start = np.concatenate([[0], np.cumsum(cnt)[:-1]])
        if len(own) >= (1 << 24):
            raise RuntimeError('GPU cloth: too many constraints')
        ent = np.zeros((len(own), 4), np.float32)
        ent[:, 0], ent[:, 1], ent[:, 2] = oth[order], rst[order], kk[order]
        w = 1.0 / np.asarray(c.mass, np.float64)
        pin = np.clip(np.asarray(c.pin, np.float64), 0.0, 1.0)
        pinfo = np.zeros((n, 4), np.float32)
        pinfo[:, 0], pinfo[:, 1], pinfo[:, 2] = start, cnt, pin
        co4 = np.zeros((n, 4), np.float32)
        co4[:, :3], co4[:, 3] = c.co, w
        pr4 = co4.copy()
        pr4[:, :3] = c.prev
        in4 = co4.copy()
        in4[:, :3] = c.init
        self.n, self.sor = n, float(c.sor)
        self.t_ent, self.t_pinfo, self.t_init = _tex(ent), _tex(pinfo), _tex(in4)
        self.t = [_tex(pr4), _tex(co4), _tex(co4)]       # prev, cur, spare
        self.margin = float(margin)
        if grid is not None:
            gc = np.zeros((len(grid.sdf), 4), np.float32)
            gc[:, :3], gc[:, 3] = grid.grad, grid.sdf
            self.t_grid = _tex(gc)
            self.gdims = [int(x) for x in grid.dims]
            self.gorigin = [float(x) for x in grid.origin]
            self.gcell = float(grid.cell)
        else:
            self.t_grid = _tex(np.zeros((1, 4), np.float32))
            self.gdims, self.gorigin, self.gcell = [1, 1, 1], [0.0, 0.0, 0.0], 1.0
        self.use_grid = grid is not None

    def step(self, gravity=(0.0, 0.0, 0.0), damping=0.1, iterations=5, max_step=0.0):
        import gpu
        groups = (self.n + 63) // 64
        prev, cur, spare = self.t
        sh = _predict()
        sh.uniform_sampler('cur', cur)
        sh.uniform_sampler('prev', prev)
        sh.uniform_sampler('init', self.t_init)
        sh.uniform_sampler('pinfo', self.t_pinfo)
        sh.image('result', spare)
        sh.uniform_int('count', self.n)
        sh.uniform_float('damping', float(damping))
        sh.uniform_float('maxstep', float(max_step))
        for nm, v in zip(('gx', 'gy', 'gz'), gravity):
            sh.uniform_float(nm, float(v))
        gpu.compute.dispatch(sh, groups, 1, 1)
        prev, cur, spare = cur, spare, prev              # (the old current is the new "prev")
        sv = _solve()
        for _k in range(int(iterations)):
            sv.uniform_sampler('cur', cur)
            sv.uniform_sampler('pinfo', self.t_pinfo)
            sv.uniform_sampler('init', self.t_init)
            sv.uniform_sampler('ent', self.t_ent)
            sv.uniform_sampler('grid', self.t_grid)
            sv.image('result', spare)
            sv.uniform_int('count', self.n)
            sv.uniform_int('use_grid', 1 if self.use_grid else 0)
            for nm, v in zip(('dx', 'dy', 'dz'), self.gdims):
                sv.uniform_int(nm, v)
            sv.uniform_float('sor', self.sor)
            sv.uniform_float('cell', self.gcell)
            sv.uniform_float('margin', self.margin)
            for nm, v in zip(('ox', 'oy', 'oz'), self.gorigin):
                sv.uniform_float(nm, v)
            gpu.compute.dispatch(sv, groups, 1, 1)
            cur, spare = spare, cur
        self.t = [prev, cur, spare]

    def read(self):
        buf = self.t[1].read()
        try:
            a = np.frombuffer(buf, np.float32)
        except (TypeError, ValueError):
            a = np.asarray(buf.to_list(), np.float32)
        return a.reshape(-1, 4)[:self.n, :3].astype(np.float64)


def bench(sizes=(64, 128, 256), frames=30, iterations=6):
    """The same cloth (a square sheet falling on a ball) for ``frames`` frames on the CPU (the C engine) and on the
    GPU, for sheets of size x size points.  Returns rows (points, CPU s, GPU s, GPU used, how far apart the two
    end, sheet size)."""
    from . import cloth_pbd as cp
    rows = []
    for m in sizes:
        xs = np.linspace(-1.0, 1.0, m)
        X, Y = np.meshgrid(xs, xs, indexing='ij')
        co = np.stack([X.ravel(), Y.ravel(), np.full(m * m, 0.4)], 1)
        quads = []
        for i in range(m - 1):
            for j in range(m - 1):
                a = i * m + j
                quads.append((a, a + m, a + m + 1, a + 1))
        quads = np.array(quads, np.int64)
        vi, tot = quads.ravel(), np.full(len(quads), 4)
        st = np.arange(len(quads)) * 4
        rng = np.random.default_rng(2)
        ball = rng.normal(size=(20000, 3))
        ball /= np.linalg.norm(ball, axis=1)[:, None]
        nrm = ball.copy()
        ball *= 0.5
        grid = cp.GridCollider(ball, nrm, 2.0 / m * 1.5, 3)
        margin = 2.0 / m * 0.5

        def make():
            c = cp.Cloth(co, vi, st, tot, bend=0.5)
            c.set_far()
            c.pin[:] = 0.0
            return c
        g = (0.0, 0.0, -0.004)
        c = make()
        c.collide = lambda cl: grid.push(cl.co, margin)
        t = time.perf_counter()
        for _f in range(frames):
            c.step(gravity=g, iterations=iterations)
        tc = time.perf_counter() - t
        used, tg, diff = False, 0.0, float('nan')
        try:
            gcl = GPUCloth(make(), grid, margin)
            import gpu
            t = time.perf_counter()
            for _f in range(frames):
                gcl.step(gravity=g, iterations=iterations)
                out = gcl.read()                      # (once a frame, as the tool shows it)
            tg = time.perf_counter() - t
            used = True
            diff = float(np.linalg.norm(out - c.co, axis=1).max())
        except Exception as ex:                       # noqa: BLE001
            _STATE['failed'] = f'{type(ex).__name__}: {ex}'
        rows.append((m * m, tc, tg, used, diff, 2.0))
    return rows
