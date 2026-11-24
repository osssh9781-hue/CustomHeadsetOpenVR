"""0.24.304: the carve's moldings are the Mold Cut (scene.mch_moldcut), apart from Edge Molding.
0.24.300 (user: "왜 컷할 때는 림이랑 몰드가 적용이 안 돼?" / "당연히 빠지는 걸로" / "바텀 몰딩은 우리 기준 표면 쪽이 계단처럼
파이는 게 좋겠지"): Alt carve with Edge Molding / Top Dome - the shape turned the other way: the bottom flange a step at
the opening (the surface side), the Dome a bowl floor."""
import math

from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import armor_plate as ap, base_mesh as bm_, core_geometry as cg

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
S.mch_settings.mch_active_tool = 'MPLATE'          # 0.24.305 the Mold Cut lives in the Mold tools
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
LOOP = [(500 + 50 * math.cos(a), 500 + 50 * math.sin(a)) for a in (2 * math.pi * k / 64 for k in range(64))]


def depth(x, y=0.0):
    C.view_layer.update()
    r = S.ray_cast(C.evaluated_depsgraph_get(), Vector((x, y, 5)), Vector((0, 0, -1)))
    return round(1.0 - r[1].z, 4) if r[0] else None


def cube():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    return C.active_object


# ---- Armor Plate Alt carve (0.24.304: Mold Cut)
ex = S.mch_moldcut
ex.on = True
ex.emold_bottom = False
S.mch_plate.preset = 'FLAT'
c = cube()
ap.perform_plate_carve(C, [LOOP], TOP, live=False)
plain_mid, plain_out = depth(0.0), depth(0.53)
ex.emold_bottom = True
ex.emold_out = 0.06
ex.emold_band = 0.02
c = cube()
msg = ap.perform_plate_carve(C, [LOOP], TOP, live=False)
d_mid, d_step, d_far = depth(0.0), depth(0.53), depth(0.62)
check('Armor Plate Alt + Bottom molding: a step at the opening (0.53: shallow, ~0.02), the floor as deep as before, '
      'outside the step untouched; closed, no plate left',
      plain_out in (None, 0.0) or plain_out < 1e-3, (plain_mid, plain_out))
check('... values', d_step is not None and 0.01 < d_step < 0.035 and abs(d_mid - plain_mid) < 0.01 and abs(d_far) < 1e-4
      and non_manifold(c) == 0 and len([o for o in bpy.data.objects if o.type == 'MESH']) == 1,
      (d_mid, d_step, d_far, msg))
ex.emold_bottom = False
ex.emold_dome = 0.04
c = cube()
ap.perform_plate_carve(C, [LOOP], TOP, live=False)
check('Armor Plate Alt + Top Dome: a bowl - the middle 0.04 deeper than plain, closed', abs(depth(0.0) - (plain_mid + 0.04)) < 0.01
      and non_manifold(c) == 0, (plain_mid, depth(0.0)))
ex.emold_dome = 0.0
c = cube()
ap.perform_plate_carve(C, [LOOP], TOP, live=False)
check('molding off: the carve as before', abs(depth(0.0) - plain_mid) < 1e-3)
S.mch_extract.emold_bottom = True
S.mch_extract.emold_out = 0.06
c = cube()
ap.perform_plate_carve(C, [LOOP], TOP, live=False)
check('Armor Plate Alt: the plates\' Edge Molding alone does not change the carve (Mold Cut does)',
      abs(depth(0.0) - plain_mid) < 1e-3 and abs(depth(0.53)) < 1e-4, (depth(0.0), depth(0.53)))
S.mch_extract.emold_bottom = False

# ---- Base Mesh Alt (Carve Height)
S.mch_settings.mch_active_tool = 'MBASE'
p = S.mch_base
p.sketch = False
p.profile = 'FLAT'
p.height = 0.2
p.alt_mode = 'HEIGHT'
c = cube()
bm_.perform_base(C, [LOOP], TOP, cutter=True)
b_plain = depth(0.0)
# Edge Molding alone (the solid's) no longer changes the carve
p.emold_bottom = True
p.emold_out = 0.06
p.emold_band = 0.03
c = cube()
bm_.perform_base(C, [LOOP], TOP, cutter=True)
check('Base Mesh Alt: the solid\'s Edge Molding alone does not change the carve (Mold Cut off): no step at the opening',
      abs(depth(0.0) - b_plain) < 1e-3 and abs(depth(0.53)) < 1e-4, (depth(0.0), depth(0.53)))
p.emold_bottom = False
mc = S.mch_moldcut
mc.on = True
mc.emold_top = False
mc.emold_bottom = True
mc.emold_out = 0.06
mc.emold_band = 0.03
mc.emold_dome = 0.0
c = cube()
msg = bm_.perform_base(C, [LOOP], TOP, cutter=True)
check('Base Mesh Alt + Bottom molding: carved 0.2 deep, a 0.03 step at the opening (0.53), closed, no solid left',
      abs(depth(0.0) - 0.2) < 0.01 and abs(depth(0.53) - 0.03) < 0.01 and abs(depth(0.62)) < 1e-4
      and non_manifold(c) == 0 and len([o for o in bpy.data.objects if o.type == 'MESH']) == 1,
      (b_plain, depth(0.0), depth(0.53), msg))
mc.emold_bottom = False
mc.emold_dome = 0.05
c = cube()
bm_.perform_base(C, [LOOP], TOP, cutter=True)
check('Base Mesh Alt + Top Dome: a bowl 0.25 in the middle, closed', abs(depth(0.0) - 0.25) < 0.01 and non_manifold(c) == 0,
      depth(0.0))
p.emold_dome = 0.0
# 0.24.303 (user, a picture: Alt carve with moldings on a round part broke) - on the side of a cylinder
from mathutils import Euler
FRONT = cg.OrthoProjector(Euler((math.radians(90), 0, 0)).to_quaternion(), pixels_per_unit=100.0)
for combo in (dict(emold_top=True, emold_bottom=False, emold_out=0.08, emold_band=0.05, emold_dome=0.0),
              dict(emold_top=True, emold_bottom=True, emold_out=0.06, emold_band=0.04, emold_dome=0.05),
              dict(emold_top=True, emold_bottom=True, emold_out=-0.05, emold_band=0.04, emold_dome=0.0, emold_shape='SLOPE')):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cylinder_add(radius=1.5, depth=2.0, vertices=96)
    cyl = C.active_object
    mc.emold_shape = 'SQUARE'
    for k, v in combo.items():
        setattr(mc, k, v)
    p.height = 0.25
    p.surface_align = True
    msg = bm_.perform_base(C, [[(500 + 45 * math.cos(a), 500 + 45 * math.sin(a)) for a in (2 * math.pi * k / 64 for k in range(64))]],
                           FRONT, cutter=True)
    C.view_layer.update()
    r = S.ray_cast(C.evaluated_depsgraph_get(), Vector((0, -5, 0)), Vector((0, 1, 0)))
    d = r[1].y + 1.5 if r[0] else None
    check(f'on a cylinder\'s side {combo}: a clean pocket (closed mesh, one part), about Height deep in the middle',
          non_manifold(cyl) == 0 and len([o for o in bpy.data.objects if o.type == 'MESH']) == 1 and d is not None
          and 0.15 < d < 0.45, (non_manifold(cyl), d, msg[:80]))
mc.emold_top = mc.emold_bottom = False
mc.emold_dome = 0.0
mc.emold_shape = 'SQUARE'
mc.on = False
summary()
