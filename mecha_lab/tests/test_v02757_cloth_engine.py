"""0.24.358 (user: "클로스가 좀 느린데 ... c 엔진으로 옮겨 줘"): the position-based cloth's work in Mecha Lab's C engine
(mcloth.c: the constraint passes, the smoothing, the grid collider's push and bake, the wide-bending pairs) - the very
same result as the numpy code, faster; numpy stays as the fallback (ENGINE[0] = False / no engine)."""
import os
import time

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import cloth_pbd as cp

fresh()
mecha_lab.register()
L = cp.clib()
dll = open(os.path.join(os.path.dirname(cp.__file__), 'bin', 'mdecim_win_x64.dll'), 'rb').read()
check('the engine has the cloth (mcloth v3), here and in the Windows build',
      L is not None and L.mcloth_version() >= 3 and b'mcloth_project' in dll and b'mcloth_splat' in dll
      and b'mcloth_ring_pairs' in dll and b'mcloth_push' in dll)

bpy.ops.mesh.primitive_grid_add(x_subdivisions=81, y_subdivisions=81, size=2)
me = bpy.context.active_object.data
co0 = np.array([v.co[:] for v in me.vertices])
vi = np.array([i for p in me.polygons for i in p.vertices])
tot = np.array([len(p.vertices) for p in me.polygons])
st = np.concatenate([[0], np.cumsum(tot)[:-1]])
rng = np.random.default_rng(1)
body = rng.normal(size=(8000, 3)) * 0.4 + np.array([0, 0, -0.45])
nrm = body - np.array([0, 0, -0.45])
nrm /= np.linalg.norm(nrm, axis=1)[:, None]


def run(engine):
    cp.ENGINE[0] = engine
    c = cp.Cloth(co0 * 1.05, vi, st, tot, bend=0.5)
    c.set_far()
    c.smooth = 0.05
    c.pin[np.abs(co0[:, 0]) > 0.99] = 1.0
    g = cp.GridCollider(body, nrm, 0.04, 3)
    c.collide = lambda cl: g.push(cl.co, 0.02)
    c.jitter(0.002)
    t = time.perf_counter()
    for _ in range(40):
        c.step(gravity=(0, 0, -0.002), iterations=6)
    return c.co.copy(), time.perf_counter() - t, g, cp.ring_pairs(c.edges, c.n)


a, ta, ga, ra = run(True)
b, tb, gb, rb = run(False)
cp.ENGINE[0] = True
check(f'the same cloth as numpy, point for point (largest difference {np.abs(a - b).max():.1e})', np.array_equal(a, b))
check('the same collider grid and the same wide-bending pairs', np.array_equal(ga.sdf, gb.sdf) and np.array_equal(ga.grad, gb.grad)
      and all(np.array_equal(ra[k], rb[k]) for k in (2, 3, 4)))
check(f'it fell and folded (moved {np.linalg.norm(a - co0 * 1.05, axis=1).max():.3f}), nothing broke', np.all(np.isfinite(a))
      and np.linalg.norm(a - co0 * 1.05, axis=1).max() > 0.01)
check(f'faster than numpy ({ta:.2f} s vs {tb:.2f} s for 40 frames of {len(co0):,} points)', ta < tb * 0.5)
summary()
