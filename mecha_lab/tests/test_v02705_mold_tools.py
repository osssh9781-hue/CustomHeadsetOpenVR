"""0.24.305 (user: "기존 베이스 메쉬랑 아머 플레이트는 냅두고 복사해서 몰드 베이스 메쉬, 몰드 아머 플레이트로 분리하라니깐"):
the moldings (Side / Edge Molding, Top Dome, Mold Cut) only in Mold Base Mesh / Mold Armor Plate; the originals as
before them."""
import math

from _harness import bpy, check, fresh, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import armor_plate as ap, base_mesh as bm_, core_geometry as cg, tool_state as ts, mold_cut

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
LOOP = [(500 + 50 * math.cos(a), 500 + 50 * math.sin(a)) for a in (2 * math.pi * k / 64 for k in range(64))]
check('Mold Base Mesh / Mold Armor Plate are tools (beside their originals, enum 90 / 91, own workspace tools)',
      ts.TOOL_BY_ID['MBASE'][5] == 'mecha.mold_base' and ts.TOOL_BY_ID['MPLATE'][5] == 'mecha.mold_plate'
      and 'MBASE' in dict(ts.TOOL_GROUPS)['Block-out'] and 'MPLATE' in dict(ts.TOOL_GROUPS)['Surface detail']
      and ts._ENUM_NUMBERS['MBASE'] == 90 and ts._ENUM_NUMBERS['MPLATE'] == 91)
st = S.mch_settings


def use(tool):
    st.mch_active_tool = tool


use('MBASE')
check('Mold Base Mesh runs as Base Mesh (every Base Mesh path), and is told apart (mold_on)',
      ts.effective_tool(C) == 'BASE' and ts.mold_on(C))
use('BASE')
check('the original Base Mesh: no mold_on', ts.effective_tool(C) == 'BASE' and not ts.mold_on(C))

p = S.mch_base
p.sketch = False
p.surface_align = False
p.profile = 'FLAT'
p.height = 0.3
p.emold_bottom = True
p.emold_out = 0.08
p.emold_band = 0.05
p.mold_count = 2


def xmax(ob):
    return max(v.co.x for v in ob.data.vertices)


def clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)


clear()
use('BASE')
bm_.perform_base(C, [LOOP], TOP)
ob = C.active_object
check('Base Mesh (original) with moldings set in the scene: made WITHOUT them (as before 0.24.295)',
      abs(xmax(ob) - 0.5) < 1e-3 and not ob.mch_base.emold_bottom and ob.mch_base.mold_count == 0, xmax(ob))
use('MBASE')
bm_.perform_base(C, [LOOP], TOP)
ob = C.active_object
check('Mold Base Mesh: made with them (the flange 0.08 out)', abs(xmax(ob) - 0.58) < 1e-3 and ob.mch_base.emold_bottom,
      xmax(ob))
p.emold_bottom = False
p.mold_count = 0

# Mold Cut only in the Mold tools
mc = S.mch_moldcut
mc.on = True
mc.emold_bottom = True
mc.emold_out = 0.06
mc.emold_band = 0.03


def depth(x):
    C.view_layer.update()
    r = S.ray_cast(C.evaluated_depsgraph_get(), Vector((x, 0, 5)), Vector((0, 0, -1)))
    return round(1.0 - r[1].z, 4) if r[0] else None


def cube():
    clear()
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    return C.active_object


p.alt_mode = 'HEIGHT'
cube()
use('BASE')
bm_.perform_base(C, [LOOP], TOP, cutter=True)
check('Base Mesh (original) Alt: a plain carve, the Mold Cut not used (no step at the opening)', abs(depth(0.53)) < 1e-4,
      depth(0.53))
cube()
use('MBASE')
bm_.perform_base(C, [LOOP], TOP, cutter=True)
check('Mold Base Mesh Alt: the Mold Cut step at the opening', abs(depth(0.53) - 0.03) < 0.01, depth(0.53))

# Armor Plate
ex = S.mch_extract
ex.emold_bottom = True
ex.emold_out = 0.05
S.mch_plate.preset = 'FLAT'


def plate_x(part):
    C.view_layer.update()
    me = part.evaluated_get(C.evaluated_depsgraph_get()).to_mesh()
    x = max((part.matrix_world @ v.co).x for v in me.vertices)
    part.evaluated_get(C.evaluated_depsgraph_get()).to_mesh_clear()
    return x


cube()
use('PLATE')
ap.perform_plate(C, [LOOP], TOP)
part = C.active_object
check('Armor Plate (original) with Edge Molding set for the next plates: made without it',
      abs(plate_x(part) - 0.5) < 1e-3 and not part.mch_extract.emold_bottom, plate_x(part))
cube()
use('MPLATE')
ap.perform_plate(C, [LOOP], TOP)
part = C.active_object
check('Mold Armor Plate: made with it (0.05 wider at the bottom)', abs(plate_x(part) - 0.55) < 0.006
      and part.mch_extract.emold_bottom, plate_x(part))
ex.emold_bottom = False
cube()
use('PLATE')
ap.perform_plate_carve(C, [LOOP], TOP, live=False)
plain = depth(0.53)
cube()
use('MPLATE')
ap.perform_plate_carve(C, [LOOP], TOP, live=False)
check('Armor Plate Alt: plain in the original, the Mold Cut step in Mold Armor Plate', abs(plain or 0.0) < 1e-4
      and depth(0.53) is not None and depth(0.53) > 0.005, (plain, depth(0.53)))
mc.on = False
use('CUT')
summary()
