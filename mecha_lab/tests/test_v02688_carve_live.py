"""0.24.293 (user: "알트 눌러서 빼는 거 뺀 이후에 실시간으로 조정하는 거 왜 안 돼?") the Armor Plate Alt carve stays live:
Alt Carve Depth / Floor / the profile carve it again from the mesh as it was; a new plate (or a new carve) keeps it."""
import math

from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import armor_plate as ap, core_geometry as cg, ramp_edit as re_

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
LOOP = [(500 + 55 * math.cos(a), 500 + 45 * math.sin(a)) for a in (2 * math.pi * k / 48 for k in range(48))]


def depth(x=0.0, y=0.0):
    C.view_layer.update()
    r = S.ray_cast(C.evaluated_depsgraph_get(), Vector((x, y, 5)), Vector((0, 0, -1)))
    return 1.0 - r[1].z if r[0] else None


bpy.ops.mesh.primitive_cube_add(size=2.0)
cube = C.active_object
S.mch_plate.preset = 'CHAMFER'
msg = ap.perform_plate_carve(C, [LOOP], TOP)
d0 = depth()
rec = re_.record(cube)
check('Alt carve: live (kept mesh + record), the report says so', rec is not None and rec.get('kind') == 'platecarve'
      and bpy.data.meshes.get(rec['backup']) is not None and 'live' in msg, (msg, rec and rec.get('kind')))
S.mch_plate.carve_depth = 0.02
re_.flush()
d1 = depth()
check('Alt Carve Depth 0.02 after the carve: carved again 0.02 deep (from the kept mesh, not deeper)',
      d1 is not None and abs(d1 - 0.02) < 0.004 and non_manifold(cube) == 0, (d0, d1))
S.mch_plate.carve_floor = 'FLAT'
re_.flush()
check('Floor changed: carved again, still 0.02 deep and closed', abs(depth() - 0.02) < 0.004 and non_manifold(cube) == 0,
      depth())
S.mch_plate.carve_floor = 'FOLLOW'
S.mch_plate.carve_depth = 0.0
re_.flush()
f_ch = len(cube.data.polygons)
S.mch_plate.preset = 'MRIDGE'
re_.flush()
dm = depth()
side = depth(0.38, 0.0)
check('profile changed to Mech Ridge: carved again as a valley', dm is not None and side is not None and dm > side * 1.1
      and non_manifold(cube) == 0, (dm, side, f_ch, len(cube.data.polygons)))
S.mch_plate.preset = 'CHAMFER'
re_.flush()
check('back to Chamfer: the chamfer carve again (as the first one)', abs(depth() - d0) < d0 * 0.05, (depth(), d0))
n_back = len([m for m in bpy.data.meshes if m.name.startswith('MCH_RampBackup_')])
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(3.0, 0, 0))
ap.perform_plate(C, [[(x + 300, y) for x, y in LOOP]], TOP)
check('a new plate keeps the carve as it is (the kept mesh goes)', re_.record(cube) is None
      and len([m for m in bpy.data.meshes if m.name.startswith('MCH_RampBackup_')]) == n_back - 1, n_back)
dd = depth()
S.mch_plate.carve_depth = 0.05
re_.flush()
check('... and the settings no longer change it', abs(depth() - dd) < 1e-6, (dd, depth()))
S.mch_plate.carve_depth = 0.0
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=2.0)
cube = C.active_object
S.mch_plate.preset = 'CHAMFER'
ap.perform_plate_carve(C, [LOOP], TOP)
re_.flush()
d0 = depth()
ap.cycle_preset(S, 1)
re_.flush()
check('the mouse wheel while drawing (next plate\'s profile) does not carve the last one again', abs(depth() - d0) < 1e-6
      and re_.record(cube) is not None, (d0, depth(), S.mch_plate.preset))
summary()
