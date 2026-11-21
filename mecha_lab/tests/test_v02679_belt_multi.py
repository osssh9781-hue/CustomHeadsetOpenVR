"""0.24.279 (user: "벨트 메이커 쓸 때 하나만 선택이 되니까 오토랑 셀렉트 액티브별로 여러 개 선택하면 쓸 수 있게"): a belt
line across several parts - Auto: a belt on every part it crosses; Selected: on the selected ones only; Active: on the
active one; each its own live belt, all selected after."""
import math

from _harness import bpy, check, fresh, summary
from mathutils import Euler, Matrix, Vector

import mecha_lab
from mecha_lab import armor_plate as ap, belt_maker as bmk, core_geometry as cg

mecha_lab.register()
fresh()
C = bpy.context
proj = cg.OrthoProjector(Euler((math.radians(90), 0, 0)).to_quaternion(), center=Vector((0, 0, 0)),
                         pixels_per_unit=200.0, size=(1000, 1000))
scr = lambda x, z: (500 + x * 200, 500 + z * 200)


def size(ob):
    P = [ob.matrix_world @ v.co for v in ob.data.vertices]
    return max(max(p[k] for p in P) - min(p[k] for p in P) for k in range(3))


def only(*obs):
    for x in C.scene.objects:
        x.select_set(False)
    for x in obs:
        x.select_set(True)
    C.view_layer.objects.active = obs[-1] if obs else None


def body(name, loc=(0, 0, 0)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=1.0, location=loc)
    b = C.active_object
    b.name = name
    return b



from mecha_lab import belt_maker as _b  # noqa
a = body('Left', (-1.2, 0, 0)); b = body('Right', (1.2, 0, 0))
line = [scr(-2.6, 0.1), scr(0, 0.1), scr(2.6, 0.1)]
C.scene.mch_cut.targets = 'AUTO'
only()
msg = bmk.perform(C, line, proj)
belts = [o for o in C.scene.objects if o.get(bmk.SRC_KEY)]
import json as _j
on = sorted(_j.loads(o[bmk.SRC_KEY])['target'] for o in belts)
check(f'Auto: a belt on every part the line crosses ({on}; {msg})', on == ['Left', 'Right']
      and sorted(o.name for o in C.selected_objects) == sorted(o.name for o in belts))
for o in belts:
    bpy.data.objects.remove(o)
C.scene.mch_cut.targets = 'SELECTED'
only(b)
msg = bmk.perform(C, line, proj)
belts = [o for o in C.scene.objects if o.get(bmk.SRC_KEY)]
check(f'Selected (only Right): its belt only ({msg})', [_j.loads(o[bmk.SRC_KEY])['target'] for o in belts] == ['Right'])
for o in belts:
    bpy.data.objects.remove(o)
only(b, a)
msg = bmk.perform(C, line, proj)
belts = [o for o in C.scene.objects if o.get(bmk.SRC_KEY)]
check(f'Selected (both): a belt on each', sorted(_j.loads(o[bmk.SRC_KEY])['target'] for o in belts) == ['Left', 'Right'])
for o in belts:
    bpy.data.objects.remove(o)
C.scene.mch_cut.targets = 'ACTIVE'
only(b, a)                                  # (Left active)
msg = bmk.perform(C, line, proj)
belts = [o for o in C.scene.objects if o.get(bmk.SRC_KEY)]
check(f'Active: the active part only ({msg})', [_j.loads(o[bmk.SRC_KEY])['target'] for o in belts] == ['Left'])
C.scene.mch_cut.targets = 'AUTO'
summary()
