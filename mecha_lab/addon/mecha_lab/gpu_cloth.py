"""0.24.359 / 0.24.361 GPU cloth (user: "GPU 한번 먼저 테스트 해 봐" -> RTX 5090: 10k points 44x, 250k points 44x faster
than the C engine): a whole frame of the position-based cloth (cloth_pbd.Cloth) on the graphics card with Blender's
own GPU module (compute shaders, float textures, the way GPU Bake works).

The frame is the CPU one, step for step (cloth_pbd.Cloth.step): the velocity (capped) + gravity + the frame's force;
then every pass: the edges, the bending pairs and each ring of the wide bending as their own Jacobi pass (one
dispatch each - every point one thread walking its own constraints, nobody writes another point), then the
smoothing, the keep pull, the pins, the tethers and the grid collider with its friction; last the per-frame move cap
and the floor.  The card counts in float32 (the CPU in float64), so the cloth comes out a hair different, not another
cloth.  What the GPU does not do (self collision, seams, tack pins, a grab in progress) runs that frame on the CPU
(``supports``), then the card takes over again from the CPU's points.

No GPU / no context (a background run) / anything unexpected: ``available()`` is False and the CPU runs it."""
from __future__ import annotations

import time

import numpy as np

TEX_W = 4096
_STATE = {'failed': None}
_SH = {}

COMMON = r'''
vec4 fetch(sampler2D t, int i) { return texelFetch(t, ivec2(i % TEXW, i / TEXW), 0); }
void put(int i, vec4 v) { imageStore(result, ivec2(i % TEXW, i / TEXW), v); }
'''

PREDICT = r'''
void main() {
  int i = int(gl_GlobalInvocationID.x);
  if (i >= count) return;
  vec4 c = fetch(cur, i), p = fetch(prev, i);
  vec3 vel = (c.xyz - p.xyz) * (1.0 - damping);
  if (maxstep > 0.0) { float l = length(vel); if (l > maxstep) vel *= maxstep / l; }
  vec3 o = c.xyz + vel + vec3(gx, gy, gz);
  if (use_force != 0) o += fetch(force, i).xyz;
  put(i, vec4(o, c.w));
}
'''

CONSTRAIN = r'''
void main() {
  int i = int(gl_GlobalInvocationID.x);
  if (i >= count) return;
  vec4 me = fetch(cur, i), info = fetch(pset, i);
  int s = int(info.x), n = int(info.y);
  vec3 p = me.xyz, acc = vec3(0.0);
  for (int k = s; k < s + n; k++) {
    vec4 e = fetch(ent, k);
    vec4 o = fetch(cur, int(e.x));
    vec3 d = o.xyz - p;
    float L = max(length(d), 1e-12);
    float c = clamp((L - e.y) / L * strength * sor, -0.5, 0.5);
    acc += d * (c * me.w / (me.w + o.w));
  }
  put(i, vec4(n > 0 ? p + acc / float(n) : p, me.w));
}
'''

POST = r'''
void main() {
  int i = int(gl_GlobalInvocationID.x);
  if (i >= count) return;
  vec4 me = fetch(cur, i), info = fetch(pinfo, i), a = fetch(init, i);
  vec3 q = me.xyz;
  if (smoothk > 0.0) {                                   /* toward the mean of the edge neighbours */
    vec4 es = fetch(pset0, i);
    int s = int(es.x), n = int(es.y);
    vec3 m = vec3(0.0);
    for (int k = s; k < s + n; k++) m += fetch(cur, int(fetch(ent, k).x)).xyz;
    m = n > 0 ? m / float(n) : vec3(0.0);
    q += (m - q) * smoothk;
  }
  if (info.y > 0.0) q += (a.xyz - q) * (info.y * keeprate);          /* keep: toward where it started */
  q = q * (1.0 - info.x) + a.xyz * info.x;                           /* pin */
  if (info.z >= 0.0) {                                               /* tether to a pinned point (at its start) */
    vec3 an = fetch(init, int(info.z)).xyz;
    vec3 d = q - an; float l = length(d);
    if (l > info.w) q = an + d * (info.w / l);
  }
  if (use_grid != 0) {                                               /* the grid collider (GridCollider.push) */
    vec3 f = (q - vec3(ox, oy, oz)) / cell - 0.5;
    ivec3 i0 = ivec3(floor(f));
    vec3 t = f - vec3(i0);
    float dist = 1e9; vec3 g = vec3(0.0);
    if (all(greaterThanEqual(i0, ivec3(0))) && all(lessThan(i0 + 1, ivec3(dx, dy, dz)))) {
      dist = 0.0;
      for (int cx = 0; cx < 2; cx++) for (int cy = 0; cy < 2; cy++) for (int cz = 0; cz < 2; cz++) {
        float w = (cx == 1 ? t.x : 1.0 - t.x) * (cy == 1 ? t.y : 1.0 - t.y) * (cz == 1 ? t.z : 1.0 - t.z);
        vec4 gc = fetch(grid, (i0.x + cx) * dy * dz + (i0.y + cy) * dz + (i0.z + cz));
        dist += w * gc.w; g += w * gc.xyz;
      }
    }
    if (dist < margin) { float l = length(g); if (l < 1e-9) l = 1.0; q += g / l * (margin - dist); }
    if (friction > 0.0 && dist < margin * 1.5) q += (fetch(prev, i).xyz - q) * friction;
  }
  put(i, vec4(q, me.w));
}
'''

FINAL = r'''
void main() {
  int i = int(gl_GlobalInvocationID.x);
  if (i >= count) return;
  vec4 me = fetch(cur, i);
  vec3 q = me.xyz, b = fetch(prev, i).xyz;              /* (prev = where the frame started) */
  if (maxstep > 0.0) { vec3 d = q - b; float l = length(d); if (l > maxstep * 2.0) q = b + d * (maxstep * 2.0 / l); }
  if (use_floor != 0) { vec3 dn = vec3(fx, fy, fz); float depth = dot(q, dn); if (depth > level) q -= dn * (depth - level); }
  put(i, vec4(q, me.w));
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


def _shaders():
    return (_make('predict', PREDICT, ('cur', 'prev', 'force'), ('count', 'use_force'),
                  ('damping', 'maxstep', 'gx', 'gy', 'gz')),
            _make('constrain', CONSTRAIN, ('cur', 'ent', 'pset'), ('count',), ('strength', 'sor')),
            _make('post', POST, ('cur', 'prev', 'init', 'pinfo', 'ent', 'pset0', 'grid'),
                  ('count', 'use_grid', 'dx', 'dy', 'dz'), ('smoothk', 'keeprate', 'cell', 'margin', 'friction',
                                                            'ox', 'oy', 'oz')),
            _make('final', FINAL, ('cur', 'prev'), ('count', 'use_floor'), ('maxstep', 'fx', 'fy', 'fz', 'level')))


def available():
    try:
        import bpy
        if bpy.app.background:
            _STATE['failed'] = 'background run (no GPU context)'
            return False
    except ImportError:
        return False
    return all(s is not None for s in _shaders())


def why_not():
    return _STATE['failed'] or ''


def _tex(arr):
    import gpu
    arr = np.ascontiguousarray(np.asarray(arr, np.float32).reshape(-1, 4))
    n = len(arr)
    rows = max(1, (n + TEX_W - 1) // TEX_W)
    full = np.zeros((rows * TEX_W, 4), np.float32)
    full[:n] = arr
    buf = gpu.types.Buffer('FLOAT', full.size, full.ravel())
    return gpu.types.GPUTexture((TEX_W, rows), format='RGBA32F', data=buf)


def _read(tex, n):
    buf = tex.read()
    try:
        a = np.frombuffer(buf, np.float32)
    except (TypeError, ValueError):
        a = np.asarray(buf.to_list(), np.float32)
    return a.reshape(-1, 4)[:n, :3].astype(np.float64)


def supports(cloth):
    """Can this frame of ``cloth`` run on the GPU?  (Self collision, seams, tack pins and a grab: the CPU.)"""
    return (not (getattr(cloth, 'self_d', 0.0) > 0) and (cloth.sew is None or not len(cloth.sew))
            and cloth.tack is None and cloth.hold is None)


class GPUSession:
    """``cloth`` (cloth_pbd.Cloth) on the GPU, with its ``grid`` collider (cloth_pbd.GridCollider or None),
    ``margin`` and ``friction`` (the collide callback's).  ``step(...)`` = ``cloth.step(...)``; the points come back
    into ``cloth.co`` / ``cloth.prev`` every frame (the mesh shows them)."""

    def __init__(self, cloth, grid=None, margin=0.0, friction=0.0):
        if not available():
            raise RuntimeError('GPU cloth: ' + (why_not() or 'no GPU'))
        if cloth.n >= (1 << 24):
            raise RuntimeError('GPU cloth: too many points')
        self.c = cloth
        self.n = cloth.n
        self.margin, self.friction = float(margin), float(friction)
        self.sig = None
        self.co_sent = None
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
        self.t_force = _tex(np.zeros((1, 4), np.float32))

    # -- what does not change from frame to frame (rebuilt when a setting changed it) ---------------------------
    def _signature(self):
        c = self.c

        def arr_sig(a):
            return (id(a), float(np.sum(a)) if np.ndim(a) else float(a))
        return (arr_sig(c.scale_e), arr_sig(c.scale_b), float(c.far_scale), float(c.stretch_k), float(c.bend),
                float(c.sor), id(c.far), arr_sig(c.keep), arr_sig(c.pin), arr_sig(c.mass), id(c.init),
                float(np.sum(c.init)), id(c.tether))

    def _build_static(self):
        c = self.c
        n = self.n
        sets = [(c.edges, c.rest_e * c.scale_e, float(c.stretch_k))]
        if c.bend > 0 and len(c.bends):
            sets.append((c.bends, c.rest_b * c.scale_b, float(c.bend)))
        if c.far and c.far_scale > 0:
            sc = float(np.mean(c.scale_e)) if np.ndim(c.scale_e) else float(c.scale_e)
            for pairs, rest, st in c.far:
                sets.append((pairs, rest * sc, float(st) * c.far_scale * c.stretch_k))
        ents, psets, self.strengths = [], [], []
        base = 0
        for pairs, rest, k in sets:
            pairs = np.asarray(pairs, np.int64)
            rest = np.broadcast_to(np.asarray(rest, np.float64), (len(pairs),))
            own = np.concatenate([pairs[:, 0], pairs[:, 1]])
            oth = np.concatenate([pairs[:, 1], pairs[:, 0]])
            rr = np.concatenate([rest, rest])
            order = np.argsort(own, kind='stable')
            cnt = np.bincount(own, minlength=n)
            start = np.concatenate([[0], np.cumsum(cnt)[:-1]]) + base
            e = np.zeros((len(own), 4), np.float32)
            e[:, 0], e[:, 1] = oth[order], rr[order]
            ents.append(e)
            ps = np.zeros((n, 4), np.float32)
            ps[:, 0], ps[:, 1] = start, cnt
            psets.append(ps)
            self.strengths.append(k)
            base += len(own)
        if base >= (1 << 24):
            raise RuntimeError('GPU cloth: too many constraints')
        self.t_ent = _tex(np.concatenate(ents) if ents else np.zeros((1, 4), np.float32))
        self.t_psets = [_tex(p) for p in psets]
        pinfo = np.zeros((n, 4), np.float32)
        pinfo[:, 0] = np.clip(np.broadcast_to(np.asarray(c.pin, np.float64), (n,)), 0.0, 1.0)
        pinfo[:, 1] = np.broadcast_to(np.asarray(c.keep, np.float64), (n,))
        pinfo[:, 2] = -1.0
        if c.tether is not None:
            idx, anc, mx = c.tether
            pinfo[np.asarray(idx, np.int64), 2] = np.asarray(anc, np.int64)
            pinfo[np.asarray(idx, np.int64), 3] = np.asarray(mx, np.float64)
        self.t_pinfo = _tex(pinfo)
        self.w = (1.0 / np.broadcast_to(np.asarray(c.mass, np.float64), (n,))).astype(np.float32)
        in4 = np.zeros((n, 4), np.float32)
        in4[:, :3], in4[:, 3] = c.init, self.w
        self.t_init = _tex(in4)
        self.co_sent = None

    def _send_points(self):
        c = self.c
        cur = np.zeros((self.n, 4), np.float32)
        cur[:, :3], cur[:, 3] = c.co, self.w
        prv = cur.copy()
        prv[:, :3] = c.prev
        self.t = [_tex(prv), _tex(cur), _tex(cur)]          # prev, cur, spare
        self.co_sent = c.co

    def step(self, force=None, gravity=None, damping=0.1, iterations=5, keep_rate=0.3):
        import gpu
        c = self.c
        sig = self._signature()
        if sig != self.sig:
            self._build_static()
            self.sig = sig
        if self.co_sent is not c.co:                       # (the CPU moved the points: a CPU frame, a reset ...)
            self._send_points()
        groups = (self.n + 63) // 64
        pr, cu, sp = self.t
        before = c.co.copy()
        sh_p, sh_c, sh_q, sh_f = _shaders()
        g = np.zeros(3) if gravity is None else np.asarray(gravity, np.float64)
        if force is not None:
            f4 = np.zeros((self.n, 4), np.float32)
            f4[:, :3] = force
            self.t_force = _tex(f4)
        sh_p.uniform_sampler('cur', cu)
        sh_p.uniform_sampler('prev', pr)
        sh_p.uniform_sampler('force', self.t_force)
        sh_p.image('result', sp)
        sh_p.uniform_int('count', self.n)
        sh_p.uniform_int('use_force', 1 if force is not None else 0)
        sh_p.uniform_float('damping', float(damping))
        sh_p.uniform_float('maxstep', float(c.max_step))
        for nm, v in zip(('gx', 'gy', 'gz'), g):
            sh_p.uniform_float(nm, float(v))
        gpu.compute.dispatch(sh_p, groups, 1, 1)
        pr, cu, sp = cu, sp, pr                             # (the frame's start is the new "prev")
        keeprate = float(keep_rate) / max(1, int(iterations))
        for _k in range(int(iterations)):
            for ps, k in zip(self.t_psets, self.strengths):
                sh_c.uniform_sampler('cur', cu)
                sh_c.uniform_sampler('ent', self.t_ent)
                sh_c.uniform_sampler('pset', ps)
                sh_c.image('result', sp)
                sh_c.uniform_int('count', self.n)
                sh_c.uniform_float('strength', float(k))
                sh_c.uniform_float('sor', float(c.sor))
                gpu.compute.dispatch(sh_c, groups, 1, 1)
                cu, sp = sp, cu
            sh_q.uniform_sampler('cur', cu)
            sh_q.uniform_sampler('prev', pr)
            sh_q.uniform_sampler('init', self.t_init)
            sh_q.uniform_sampler('pinfo', self.t_pinfo)
            sh_q.uniform_sampler('ent', self.t_ent)
            sh_q.uniform_sampler('pset0', self.t_psets[0])
            sh_q.uniform_sampler('grid', self.t_grid)
            sh_q.image('result', sp)
            sh_q.uniform_int('count', self.n)
            sh_q.uniform_int('use_grid', 1 if self.use_grid else 0)
            for nm, v in zip(('dx', 'dy', 'dz'), self.gdims):
                sh_q.uniform_int(nm, v)
            sh_q.uniform_float('smoothk', float(c.smooth))
            sh_q.uniform_float('keeprate', keeprate)
            sh_q.uniform_float('cell', self.gcell)
            sh_q.uniform_float('margin', self.margin)
            sh_q.uniform_float('friction', self.friction)
            for nm, v in zip(('ox', 'oy', 'oz'), self.gorigin):
                sh_q.uniform_float(nm, v)
            gpu.compute.dispatch(sh_q, groups, 1, 1)
            cu, sp = sp, cu
        fl = c.floor
        sh_f.uniform_sampler('cur', cu)
        sh_f.uniform_sampler('prev', pr)
        sh_f.image('result', sp)
        sh_f.uniform_int('count', self.n)
        sh_f.uniform_int('use_floor', 1 if fl is not None else 0)
        sh_f.uniform_float('maxstep', float(c.max_step))
        dn = np.asarray(fl[0], np.float64) if fl is not None else np.zeros(3)
        for nm, v in zip(('fx', 'fy', 'fz'), dn):
            sh_f.uniform_float(nm, float(v))
        sh_f.uniform_float('level', float(fl[1]) if fl is not None else 0.0)
        gpu.compute.dispatch(sh_f, groups, 1, 1)
        cu, sp = sp, cu
        self.t = [pr, cu, sp]
        c.prev = before
        c.co = _read(cu, self.n)
        self.co_sent = c.co
        return c.co


def bench(sizes=(100, 250, 500), frames=30, iterations=6):
    """The same cloth (a square sheet falling on a ball) for ``frames`` frames on the CPU (the C engine) and on the
    GPU, for sheets of size x size points.  Returns rows (points, CPU s, GPU s, GPU used, how far apart the two
    end, sheet size)."""
    from . import cloth_pbd as cp
    rows = []
    for m in sizes:
        xs = np.linspace(-1.0, 1.0, m)
        X, Y = np.meshgrid(xs, xs, indexing='ij')
        co = np.stack([X.ravel(), Y.ravel(), np.full(m * m, 0.4)], 1)
        ii, jj = np.meshgrid(np.arange(m - 1), np.arange(m - 1), indexing='ij')
        a = (ii * m + jj).ravel()
        quads = np.stack([a, a + m, a + m + 1, a + 1], 1)
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
            c.smooth = 0.05
            c.max_step = 2.0 / m * 1.5
            return c
        g = (0.0, 0.0, -0.004)
        c = make()

        def collide(cl):
            touch = grid.push(cl.co, margin)
            cl.co[touch] += (cl.prev[touch] - cl.co[touch]) * 0.3
        c.collide = collide
        t = time.perf_counter()
        for _f in range(frames):
            c.step(gravity=g, iterations=iterations)
        tc = time.perf_counter() - t
        used, tg, diff = False, 0.0, float('nan')
        try:
            cg_ = make()
            s = GPUSession(cg_, grid, margin, 0.3)
            t = time.perf_counter()
            for _f in range(frames):
                s.step(gravity=g, iterations=iterations)
            tg = time.perf_counter() - t
            used = True
            diff = float(np.linalg.norm(cg_.co - c.co, axis=1).max())
        except Exception as ex:                       # noqa: BLE001
            _STATE['failed'] = f'{type(ex).__name__}: {ex}'
        rows.append((m * m, tc, tg, used, diff, 2.0))
    return rows
