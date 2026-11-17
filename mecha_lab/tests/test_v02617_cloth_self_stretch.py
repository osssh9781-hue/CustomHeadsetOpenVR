"""0.24.199 (user: "떨어지는 거 할 때는 천끼리 콜리전이랑 탄성 조절이 뭐야?" / "일단 넣고"): Cloth Drape - Self Collision
(the cloth does not pass through itself) and Stretch (0 = cloth, 100 = rubber)."""
import time

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import cloth_drape as cd, cloth_pbd as cp  # noqa: E402

fresh()
mecha_lab.register()
st = cd.settings(bpy.context)
check('the two settings: Stretch 0 and Self Collision off by default (the cloth as before)',
      st.stretch == 0.0 and st.self_collide is False)


def sheet(n, z, size=1.0):
    g = np.linspace(-size / 2, size / 2, n)
    X, Y = np.meshgrid(g, g, indexing='ij')
    co = np.c_[X.ravel(), Y.ravel(), np.full(n * n, z)]
    quads = [(i * n + j, (i + 1) * n + j, (i + 1) * n + j + 1, i * n + j + 1) for i in range(n - 1) for j in range(n - 1)]
    vi = np.array(quads, np.int64).ravel()
    start = np.arange(len(quads), dtype=np.int64) * 4
    return co, vi, start, np.full(len(quads), 4, np.int64)


# Stretch: a strip held by its top row, hanging under gravity
def hang(k):
    co, vi, start, tot = sheet(12, 0.0)
    co = co[:, [0, 2, 1]] * 1.0                    # (upright: z is down the strip)
    pin = (co[:, 2] > co[:, 2].max() - 1e-6).astype(float)
    c = cp.Cloth(co, vi, start, tot, bend=0.3, pin=pin)
    c.stretch_k = k
    for _i in range(120):
        c.step(gravity=(0.0, 0.0, -0.001), damping=0.05, iterations=5)
    return float(np.ptp(c.co[:, 2]))


l0, l1 = hang(1.0), hang(1.0 - 0.92 * 0.8)
check(f'Stretch: a strip (1.0 long) hung by its top edge - Stretch 0 hangs {l0:.3f} long, Stretch 80 {l1:.3f} (longer)',
      l0 < 1.15 and l1 > l0 * 1.08 and np.isfinite(l1))


# Self collision: the right half of a sheet folded over onto the left half and pressed down
def fold(on):
    co, vi, start, tot = sheet(20, 0.0)
    step = 1.0 / 19
    init = co.copy()
    right = co[:, 0] > 0
    co[right, 0] *= -1.0                           # folded over at x = 0 ...
    co[right, 2] = step * 1.5                      # ... lying a little above the left half
    c = cp.Cloth(init, vi, start, tot, bend=0.2, pin=(~right).astype(float))
    c.co = co.copy()
    c.prev = co.copy()
    c.init[~right] = co[~right]
    if on:
        c.self_d, c.self_far = step * 0.9, step * 2.6
    t0 = time.perf_counter()
    for _i in range(60):
        c.step(gravity=(0.0, 0.0, -0.003), damping=0.1, iterations=5)
    far = right & (init[:, 0] > 0.25)              # (away from the fold line)
    return float(c.co[far, 2].min()), float(c.co[far, 2].mean()), time.perf_counter() - t0, bool(np.all(np.isfinite(c.co)))


lo_off, mean_off, t_off, _f = fold(False)
lo_on, mean_on, t_on, fin = fold(True)
step = 1.0 / 19
check(f'Self Collision off: the folded half falls through the half under it (lowest {lo_off:.3f}, below 0); on: it '
      f'stays on top (lowest {lo_on:.3f}, at least half the thickness up), finite; 400 points, 60 frames in '
      f'{t_on:.2f} s (off {t_off:.2f} s)', lo_off < -0.02 and lo_on > step * 0.3 and fin and t_on < 20.0)
c = cp.Cloth(*sheet(20, 0.0))
c.self_d, c.self_far = step * 0.9, step * 2.6
check('a flat sheet has no pairs to push (neighbours on the cloth are left alone)', len(c.find_self_pairs()) == 0)
summary()
