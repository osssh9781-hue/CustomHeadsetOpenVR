"""0.24.344 (user: "메카 텍스처에서 영역 나눠서 칠하는 거 경계 해상도를 높일 수 있어?" / "심플 텍스처에다가 메크 메테리얼
추가하면 기본으로 더스트인지 러스트인지가 켜져 있는데 처음엔 다 꺼져 있고 내가 하나씩 키고 싶어"):
* a Paint Zone's mask covers the lasso's area (+ room for the widest edge / line) at up to 5x the old whole-view
  picture's resolution - the outline that much finer; the fields reach as far on the screen as before
* the Mech Shader laid over the user's own material (e.g. a Simple one): every wear / weather layer off at first."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import mech_shader as ms, zones as zn

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
RW = RH = 1000


def camera(loc, rot):
    cd = bpy.data.cameras.new('Cam')
    cam = bpy.data.objects.new('Cam', cd)
    S.collection.objects.link(cam)
    cam.location, cam.rotation_euler = loc, rot
    S.camera = cam
    C.view_layer.update()
    return cam


bpy.ops.mesh.primitive_cube_add(size=2.0)
part = C.active_object
bpy.ops.mch.mech_shader_apply(preset='PAINTED')
far = camera((0.0, -14.0, 0.0), (math.radians(90), 0.0, 0.0))
vm, wm = far.matrix_world.inverted(), far.calc_matrix_camera(C.evaluated_depsgraph_get(), x=RW, y=RH)


def to_px(co):
    v = wm @ vm @ Vector((*co, 1.0))
    return ((v.x / v.w * 0.5 + 0.5) * RW, (v.y / v.w * 0.5 + 0.5) * RH)


circ = [to_px((0.6 * math.cos(t), -1.0, 0.6 * math.sin(t))) for t in np.linspace(0, 2 * math.pi, 64, endpoint=False)]
z = zn.add_paint_zone(C, part, circ, vm, wm, True, RW, RH)
k = zn.mask_scale(z.mask)
check(f'the mask covers the lasso\'s area, {k:.1f}x finer than the old whole-view picture ({z.mask.size[:]})',
      k > 4.5 and z.mask.get('mch_crop') is not None)
c = (sum(p[0] for p in circ) / 64, sum(p[1] for p in circ) / 64)
r = math.hypot(circ[0][0] - c[0], circ[0][1] - c[1])
on = [zn.mask_at(z, c[0] + r * math.cos(t), c[1] + r * math.sin(t)) for t in np.linspace(0, 6.2, 40)]
check(f'the outline exactly on the lasso (0.5 all round: {min(on):.3f}..{max(on):.3f}), the middle inside '
      f'({zn.mask_at(z, *c):.3f}), far outside 0',
      max(abs(v - 0.5) for v in on) < 0.06 and abs(zn.mask_at(z, *c) - min(1.0, 0.5 + r / 192.0)) < 0.03
      and zn.mask_at(z, 5, 5) < 0.01)
d = 20.0
v_in = zn.mask_at(z, c[0] + r - d, c[1])
check(f'the field reads in screen pixels as before (20 px in: {v_in:.3f} = 0.5 + 20 / 192)',
      abs(v_in - (0.5 + d / 192.0)) < 0.02)

# Over My Material: a plain material of the user's -> the Mech Shader over it, every layer off
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(5, 0, 0))
ob = C.active_object
m = bpy.data.materials.new('Mine')
m.use_nodes = True
ob.data.materials.append(m)
for o in S.objects:
    o.select_set(False)
ob.select_set(True)
C.view_layer.objects.active = ob
r1 = bpy.ops.mch.material_over(kind='MECH', preset='')
mat = ob.active_material
st = getattr(mat, ms.KEY)
on_ = {k_: round(getattr(st, k_), 3) for k_ in ms.LAYERS_OFF if getattr(st, k_) > 0}
check(f'Layer Over My Material: every wear / weather layer off at first ({on_ or "none on"})',
      r1 == {'FINISHED'} and mat is not m and not on_)
m2 = bpy.data.materials.new('Mine2')
m2.use_nodes = True
ob.data.materials.clear()
ob.data.materials.append(m2)
r2 = bpy.ops.mch.material_over(kind='MECH', preset='DIRTY')
st2 = getattr(ob.active_material, ms.KEY)
check('... a preset picked on purpose keeps its layers (Dirty Metal: dirt on)', r2 == {'FINISHED'} and st2.dirt > 0.3)
summary()
