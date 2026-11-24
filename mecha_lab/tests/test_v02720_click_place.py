"""0.24.320 (user: "조인트랑 타이어 터빈 다 내가 클릭한곳에 생성되게 해줘"): the Joint Generator, Tire & Gear and Turbine tools - a
click in the view summons one there (the view clicks are checked in a real window; here: the keymaps, the summon at a
point with the 3D cursor put back, the buttons unchanged)."""
from _harness import bpy, check, fresh, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import click_place, joint_gen as jg, tire_gen as tg, turbine_gen as tb

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene

for tool, op in ((jg.MCH_TOOL_joint, 'mch.joint_click'), (tg.MCH_TOOL_tire_gear, 'mch.tire_click'),
                 (tb.MCH_TOOL_turbine, 'mch.turbine_click')):
    km = tool.bl_keymap
    check(f'{tool.bl_idname}: a click -> {op}, Shift+click still Select toggle',
          km[0][0] == op and km[0][1] == {'type': 'LEFTMOUSE', 'value': 'CLICK'} and km[1][0] == 'view3d.select'
          and km[1][1].get('shift') is True)
    check(f'... {op} registered', hasattr(bpy.ops.mch, op.split('.')[1]))

S.cursor.location = (7, 7, 7)
where = Vector((1.5, -2.0, 0.25))
click_place.summon_at(C, where, lambda: bpy.ops.mch.joint_add())
U = next(o for o in S.objects if jg.joint_of(o) and o.get(jg.PART) == 'UPPER')
C.view_layer.update()
check('joint summoned at the point', (U.matrix_world.translation - where).length < 1e-5)
check('the 3D cursor put back', (S.cursor.location - Vector((7, 7, 7))).length < 1e-6)
click_place.summon_at(C, where, lambda: bpy.ops.mch.turbine_add())
Bd = next(o for o in S.objects if tb.turbine_of(o) and o.get(tb.PART) == 'BODY')
C.view_layer.update()
check('turbine summoned at the point', (Bd.matrix_world.translation - where).length < 1e-5)
for kind in ('TIRE', 'GEAR'):
    S.mch_tire.click_kind = kind
    click_place.summon_at(C, where, lambda: bpy.ops.mch.tire_add(kind=S.mch_tire.click_kind))
    ob = C.active_object
    check(f'Click: {kind.title()} -> a {kind.lower()} at the point', tg.kind_of(ob) == kind and
          (ob.location - where).length < 1e-5)
check('Click Makes: Tire by default', type(S.mch_tire).bl_rna.properties['click_kind'].default == 'TIRE')
bpy.ops.mch.turbine_add()
C.view_layer.update()
check('the Summon button: still on the 3D cursor', (C.active_object.matrix_world.translation - Vector((7, 7, 7))).length < 1e-5)
summary()
