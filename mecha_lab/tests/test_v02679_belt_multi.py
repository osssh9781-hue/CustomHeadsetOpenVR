"""0.24.279 / 0.24.280 (user: "벨트 메이커 ... 오토랑 셀렉트 액티브별로 여러 개", "선택한 레이어가 두 개면 두 개를 같이 묶어야지"):
a belt line across several parts - Auto: the parts it crosses, Selected: the selected ones, Active: the active one -
ONE belt binding them together (Wrap: round all of them, the strap bridging the gap)."""
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
import json as _j
a = body('Left', (-1.2, 0, 0)); b = body('Right', (1.2, 0, 0))
line = [scr(-2.6, 0.1), scr(0, 0.1), scr(2.6, 0.1)]
C.scene.mch_cut.targets = 'AUTO'
only()
msg = bmk.perform(C, line, proj)
belts = [o for o in C.scene.objects if o.get(bmk.SRC_KEY)]
src = _j.loads(belts[0][bmk.SRC_KEY]) if belts else {}
xs = [(belts[0].matrix_world @ v.co).x for v in belts[0].data.vertices] if belts else [0]
check(f'Auto: ONE belt binding both parts the line crosses ({src.get("targets")}; x {min(xs):.2f} .. {max(xs):.2f}; {msg})',
      len(belts) == 1 and sorted(src.get('targets', [])) == ['Left', 'Right'] and min(xs) < -2.0 and max(xs) > 2.0)
p_ = belts[0].mch_belt
check('... a closed loop round both (Wrap)', p_.mode == 'WRAP' and len(belts[0].data.polygons) > 0)
for o in belts:
    bpy.data.objects.remove(o)
C.scene.mch_cut.targets = 'SELECTED'
only(b)
msg = bmk.perform(C, line, proj)
belts = [o for o in C.scene.objects if o.get(bmk.SRC_KEY)]
xs = [(belts[0].matrix_world @ v.co).x for v in belts[0].data.vertices]
check(f'Selected (only Right): a belt round Right only ({min(xs):.2f} .. {max(xs):.2f})',
      len(belts) == 1 and _j.loads(belts[0][bmk.SRC_KEY])['targets'] == ['Right'] and min(xs) > 0.0)
for o in belts:
    bpy.data.objects.remove(o)
only(b, a)
msg = bmk.perform(C, line, proj)
belts = [o for o in C.scene.objects if o.get(bmk.SRC_KEY)]
check('Selected (both): one belt round both', len(belts) == 1
      and sorted(_j.loads(belts[0][bmk.SRC_KEY])['targets']) == ['Left', 'Right'])
belts[0].mch_belt.width = belts[0].mch_belt.width * 1.5
check('... live: a slider lays it again round both', len(belts[0].data.polygons) > 0)
for o in belts:
    bpy.data.objects.remove(o)
C.scene.mch_cut.targets = 'ACTIVE'
only(b, a)                                  # (Left active)
msg = bmk.perform(C, line, proj)
belts = [o for o in C.scene.objects if o.get(bmk.SRC_KEY)]
check(f'Active: the active part only ({msg})', [_j.loads(o[bmk.SRC_KEY])['targets'] for o in belts] == [['Left']])
C.scene.mch_cut.targets = 'AUTO'
summary()
