"""0.24.340 Fast Bake (user: "베이크를 좀 더 빠르게 ... 4번으로 가자 빠르게 해 줘 최대한"): Normal, Height and Curvature by
Mecha Lab's own engine (mbake, C: one ray a pixel from the cage, all three maps at once) - the same result as Cycles,
several times faster; Cycles as before when Fast Bake is off or the engine is missing."""
import os
import time

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import bake_maps as bm, fast_bake as fb, fast_decimate as fd

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
RES = 512
L = fb.lib()
check('the engine has the baker (mbake v2), here and in the Windows build',
      L is not None and L.mbake_version() == 2
      and b'mbake_maps' in open(os.path.join(os.path.dirname(fd.__file__), 'bin', 'mdecim_win_x64.dll'), 'rb').read())

bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=1.0)
hi = C.active_object
m = hi.modifiers.new('S', 'SUBSURF')
m.levels = m.render_levels = 2
tex = bpy.data.textures.new('T', 'VORONOI')
tex.noise_scale = 0.35
d = hi.modifiers.new('D', 'DISPLACE')
d.texture, d.strength = tex, 0.06
bpy.ops.object.shade_smooth()
bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1.0)
lo = C.active_object
bpy.ops.object.shade_smooth()
st = S.mch_bake
st.res = str(RES)
st.normal, st.ao, st.color, st.height, st.curv = True, False, False, True, True
for k in ('rough', 'metal', 'emit'):
    setattr(st, k, False)
st.save, st.use_on_low, st.new_uv, st.smooth = False, False, False, False


def run(fast):
    st.fast = fast
    for o in S.objects:
        o.select_set(False)
    t0 = time.time()
    bm.bake_pair(C, lo, [hi], st)
    dt = time.time() - t0
    out = {k: np.array(bpy.data.images[f'{lo.name}_{bm.SUFFIX[k]}'].pixels[:]).reshape(RES, RES, 4)
           for k in ('NORMAL', 'HEIGHT', 'CURV')}
    return dt, out, list(bm.LAST.get('fast') or [])


tc, cyc, fc = run(False)
tf, fst, ff = run(True)
a = cyc['NORMAL'][..., :3] * 2 - 1
b = fst['NORMAL'][..., :3] * 2 - 1
a /= np.maximum(np.linalg.norm(a, axis=2, keepdims=True), 1e-9)
b /= np.maximum(np.linalg.norm(b, axis=2, keepdims=True), 1e-9)
ang = np.degrees(np.arccos(np.clip((a * b).sum(2), -1, 1)))
check(f'Normal: the same as Cycles (angle between them: mean {ang.mean():.2f}°, 95% under {np.percentile(ang, 95):.2f}°)',
      ang.mean() < 1.0 and np.percentile(ang, 95) < 2.0)


def corr(x, y):
    x, y = x[..., 0].ravel(), y[..., 0].ravel()
    return float(np.corrcoef(x, y)[0, 1])


ch, cc = corr(cyc['HEIGHT'], fst['HEIGHT']), corr(cyc['CURV'], fst['CURV'])
check(f'Height and Curvature: the same picture as Cycles\' (correlation {ch:.3f}, {cc:.3f})', ch > 0.9 and cc > 0.85)
check(f'all three by the fast engine in one go ({ff}), faster than Cycles: {tf:.2f} s vs {tc:.2f} s',
      set(ff) == {'NORMAL', 'HEIGHT', 'CURV'} and fc == [] and tf < tc * 0.7)
real = fb.lib
fb.lib = lambda: None
t2, _o, f2 = run(True)
fb.lib = real
check(f'no engine (another system): Cycles bakes them as before ({f2})', f2 == [])
summary()
