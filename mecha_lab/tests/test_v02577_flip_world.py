"""0.24.171 (user: "머리는 월드 기준 x축으로 뒤집는 것도 되게 해 줘, 그리고 다른 것들도 뒤집을 땐 월드 기준으로" - "미러랑
뒤집기는 다르지"): Flip (the right-click menus) turns hair over to the other side across the world's X plane - the
object itself, not a copy: an applied Fur's curves, a live Fur (its area moved on the body, still live), a live
Creature Hair (applied first).  Measured on the evaluated objects."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Euler, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, creature_fur as cf, creature_hair as ch  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)


def blob(cx, cz, r=0.2):
    return [[FRONT.to_screen(Vector((cx + r * math.cos(a), -2.0, cz + r * math.sin(a))))
             for a in np.linspace(0, 2 * math.pi, 40, endpoint=False)]]


def select(*obs):
    for o in C.selected_objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    C.view_layer.objects.active = obs[0]


def roots(ob):
    dg = C.evaluated_depsgraph_get()
    d = ob.evaluated_get(dg).data
    P = np.empty(len(d.points) * 3, np.float32)
    d.attributes['position'].data.foreach_get('vector', P)
    off = np.empty(len(d.curves), np.int32)
    d.curves.foreach_get('first_point_index', off)
    M = np.array(ob.matrix_world)
    return (P.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3])[off]


bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=96, ring_count=48)
body = C.active_object
S.mch_fur.density = 12000.0
select(body)
cf.perform(C, blob(0.45, 0.4), FRONT)
fur = C.active_object
fur.mch_fur.parts[0].flow = math.radians(40)
r0 = roots(fur)
select(fur)
r = bpy.ops.mch.flip_object(axis='X')
r1 = roots(fur)
check(f'a LIVE fur on +X, Flip: its area now on -X (roots x {r1[:, 0].min():.2f} .. {r1[:, 0].max():.2f}, were '
      f'{r0[:, 0].min():.2f} .. {r0[:, 0].max():.2f}), still live, about as many strands ({len(r1):,} / {len(r0):,})',
      r == {'FINISHED'} and cf.is_fur(fur) and r1[:, 0].max() < 0.0 and r0[:, 0].min() > 0.0
      and abs(len(r1) - len(r0)) < 0.15 * len(r0) and abs(r1[:, 0].mean() + r0[:, 0].mean()) < 0.03)
check(f'...its Flow Angle turned the other way (the mirror image: {math.degrees(fur.mch_fur.parts[0].flow):.0f} degrees)',
      abs(math.degrees(fur.mch_fur.parts[0].flow) + 40) < 1e-3)
# an applied fur (the user's case): its curves
cf.apply_fur(C, fur)
a0 = roots(fur)
select(fur)
bpy.ops.mch.flip_object(axis='X')
a1 = roots(fur)
check(f'an APPLIED fur (real hair curves), Flip: every strand across the world\'s X plane (roots x {a1[:, 0].min():.2f} .. '
      f'{a1[:, 0].max():.2f}) - itself, no copy ({len(a1):,} strands)', len(a1) == len(a0)
      and np.allclose(a1, a0 * np.array([-1, 1, 1]), atol=1e-5))
# a live Creature Hair
S.mch_hair.style = 'STRANDS'
select(body)
ch.perform(C, blob(0.5, 0.5), FRONT)
hair = C.active_object
P0 = np.array([hair.matrix_world @ v.co for v in hair.data.vertices])
select(hair)
bpy.ops.mch.flip_object(axis='X')
P1 = np.array([hair.matrix_world @ v.co for v in hair.data.vertices])
check(f'a LIVE Creature Hair on +X, Flip: applied first (not rebuilt back), now on -X (x {P1[:, 0].min():.2f} .. '
      f'{P1[:, 0].max():.2f})', not hair.mch_hair.live and np.allclose(P1, P0 * np.array([-1, 1, 1]), atol=1e-5)
      and all(s_ > 0 for s_ in hair.scale))
hair.mch_hair.count = 10                                                 # (a slider: nothing rebuilt over it)
P2 = np.array([hair.matrix_world @ v.co for v in hair.data.vertices])
check('...a slider afterwards does not rebuild it on the old side', len(P2) == len(P1) and np.allclose(P2, P1))
# a mesh away from the middle (an arm on the right): to the left
bpy.ops.mesh.primitive_cube_add(size=0.3, location=(2.0, 0.5, 1.0))
arm = C.active_object
W0 = np.array([arm.matrix_world @ v.co for v in arm.data.vertices])
select(arm)
bpy.ops.mch.flip_object(axis='X')
W1 = np.array([arm.matrix_world @ v.co for v in arm.data.vertices])
check(f'a mesh at x = 2: Flip puts it at x = -2 (the world\'s X plane, not its own origin)',
      np.allclose(W1, W0 * np.array([-1, 1, 1]), atol=1e-5) and abs(arm.location.x + 2.0) < 1e-6)

mecha_lab.unregister()
summary()
