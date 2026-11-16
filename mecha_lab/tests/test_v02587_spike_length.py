"""0.24.177 (user: "크리쳐 스파이크는 길이 조절 좀 넣어 줘"): Creature Spike's Length (x their height; the base as wide /
as thick as before) and Length Random (each spike a little longer / shorter) - live on the selected spikes, the next
line's settings in the window.  Measured on the spikes' own points over a ball (their height above it).
Found on the way: Creature Spike along a line and Belt Maker "Follow Line" stopped with a TypeError since 0.24.89 (the
cached mesh's ray cast did not take the distance Armor Plate's surface projection passes) - both checked here."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Euler, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, creature_spike as cs  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
R = 1.0
bpy.ops.mesh.primitive_uv_sphere_add(radius=R, segments=96, ring_count=48)
ball = C.active_object
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)
st = S.mch_spike
check('the window: Length and Length Random (Length 1 / random 0: as before)',
      hasattr(st, 'length') and hasattr(st, 'length_random') and abs(st.length - 1.0) < 1e-9
      and st.length_random == 0.0 and 'length' in cs.LIVE_KEYS and 'length_random' in cs.LIVE_KEYS)
st.use_fin, st.use_horn, st.use_hook, st.use_notch = False, True, False, False
st.size, st.size_random, st.lean, st.lean_random, st.turn_random = 0.25, 0.0, 0.0, 0.0, 0.0
path = [FRONT.to_screen(Vector((x, -3.0, 0.2))) for x in np.linspace(-0.6, 0.6, 30)]
for o in C.selected_objects:
    o.select_set(False)
msg = cs.perform(C, path, FRONT)
sp = C.active_object


def heights(ob):
    C.view_layer.update()
    P = np.array([tuple(ob.matrix_world @ v.co) for v in ob.data.vertices])
    r = np.linalg.norm(P, axis=1) - R
    K = len(cs.unit_spike('HORN', ob.mch_spike.thickness)[0])
    n = len(P) // K
    per = r[:n * K].reshape(n, K)
    base = P[:n * K].reshape(n, K, 3)
    lo_, hi_ = per.min(1, keepdims=True), per.max(1, keepdims=True)
    low = per < lo_ + 0.08 * (hi_ - lo_)                   # (each spike's points by its base: its lowest 8 %)
    width = np.array([np.ptp(base[i][low[i]][:, 0]) for i in range(n)])
    return per.max(1), width, n


h1, w1, n1 = heights(sp)
sp.mch_spike.length = 2.0
h2, w2, n2 = heights(sp)
check(f'Length 2: the spikes twice as long (tallest {h1.max():.3f} -> {h2.max():.3f}, x{h2.max() / h1.max():.2f}), '
      f'their base as wide ({np.median(w1):.3f} -> {np.median(w2):.3f}), as many ({n1} -> {n2}) - live, {msg[:40]}',
      1.8 < h2.max() / h1.max() < 2.2 and abs(np.median(w2) / np.median(w1) - 1.0) < 0.1 and n1 == n2
      and abs(st.length - 2.0) < 1e-9)
sp.mch_spike.length = 0.5
h3, _w3, _n3 = heights(sp)
check(f'Length 0.5: half as long (x{h3.max() / h1.max():.2f})', 0.4 < h3.max() / h1.max() < 0.62)
sp.mch_spike.length = 1.0
sp.mch_spike.length_random = 0.6
h4, _w4, n4 = heights(sp)
check(f'Length Random 0.6: each its own length ({h4.min():.3f} .. {h4.max():.3f}; at 0: all {h1.min():.3f} .. '
      f'{h1.max():.3f}), still {n4} spikes', np.ptp(h4) > 0.3 * h1.max() and np.ptp(h1) < 0.02 and n4 == n1)
sp.mch_spike.length_random = 0.0
h5, _w5, _n5 = heights(sp)
check(f'back to Length 1 / random 0: as at first (tallest {h5.max():.3f})', np.abs(h5 - h1).max() < 1e-4)
# Belt Maker "Follow Line" (the same projection): it makes its belt now
from mecha_lab import belt_maker as bmk  # noqa: E402
for o in C.selected_objects:
    o.select_set(False)
S.mch_belt.mode = 'FOLLOW'
try:
    bmsg = bmk.perform(C, path, FRONT)
    berr = None
except Exception as ex:                               # (before: TypeError ... ray_cast() takes 3 positional arguments)
    bmsg, berr = '', repr(ex)
belt = C.active_object
check(f'Belt Maker Follow Line along the same line: a belt ({bmsg[:60]}; error: {berr})',
      berr is None and belt is not None and belt != ball and len(belt.data.polygons) > 10)
summary()
