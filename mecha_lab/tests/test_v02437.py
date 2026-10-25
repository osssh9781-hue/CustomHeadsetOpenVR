"""0.24.31 Concept Move and Jungle Gym in the Mecha menus (tool list, bottom bar, V pie, sidebar) and hold D + drag
= Concept Move in any Mecha tool (editable in the Hotkeys box)."""
from _harness import bpy, check, summary
import mecha_lab
from mecha_lab import tool_state as ts, bottom_bar as bb, ui_tool_settings as uts, workspace_ui as wui

mecha_lab.register()
vis = {t[0] for t in ts.VISIBLE_TOOLS}
check('Concept Move and Jungle Gym in the tool list', {'CMOVE', 'GYM'} <= vis)
check('their native tools', ts.TOOL_BY_ID['CMOVE'][5] == 'mecha.concept_move' and ts.TOOL_BY_ID['GYM'][5] == 'mecha.jungle_gym'
      and ts.NATIVE_TO_TOOL.get('mecha.jungle_gym') == 'GYM')
check('enum numbers new (saved files keep their old tools)', ts._ENUM_NUMBERS['CMOVE'] == 48 and ts._ENUM_NUMBERS['GYM'] == 49
      and len(set(ts._ENUM_NUMBERS.values())) == len(ts._ENUM_NUMBERS))
check('bottom bar buttons', {'CMOVE', 'GYM'} <= {t[0] for t in bb.BAR_TOOLS})
check('V pie: stacked under Primitive', bb.PIE_SHARED.get('PRIMITIVE') == ('CMOVE', 'GYM'))
check('sidebar settings drawers', 'CMOVE' in uts.DRAWERS and 'GYM' in uts.DRAWERS)
check('an assignable key per tool (Hotkeys box)', {'CMOVE', 'GYM'} <= set(wui.tool_key_ids()))
items = [it for _km, it in wui._keymaps if it.idname == 'mch.concept_hold']
check('hold D + drag key item (Object Mode)', len(items) == 1 and items[0].key_modifier == 'D'
      and items[0].type == 'LEFTMOUSE', [(i.type, i.key_modifier) for i in items])
check('hold D + drag also first in the Mecha drawing tools', wui._tool_keymap('CUT')[0][0] == 'mch.concept_hold'
      and wui._tool_keymap('CUT')[0][1].get('key_modifier') == 'D')
check('the hold key shows in the Hotkeys box (and is saved)', 'mch.concept_hold' in wui._HOTKEY_IDS
      and 'key_modifier' in wui._KEY_FIELDS)
check('hold operator registered', hasattr(bpy.ops.mch, 'concept_hold'))
bpy.ops.mch.set_tool(tool='GYM')
check('picking Jungle Gym from the menu selects it', bpy.context.scene.mch_settings.mch_active_tool == 'GYM')

# Ctrl while dragging: turn the grabbed part (and F9 Turn)
import math
import numpy as np
from mecha_lab import concept_move as cm
o = cm.displace(np.array([[1.0, 0, 0]]), (0, 0, 0), (0, 0, 0), 10.0, 'CLAY', hardness=0.9, twist=(0, 0, 1, math.pi / 2))
check('turn: the grabbed part turns round the grab point (90 degrees)', np.allclose(o[0], (0, 1, 0), atol=1e-9), o.tolist())
o = cm.displace(np.array([[3.0, 0.5, 0], [-3.0, 0.5, 0]]), (2, 0, 0), (0.2, 0, 0), 3.0, 'CLAY', mirror_x=True, hardness=0.9,
                twist=(0, 0, 1, 0.5))
check('turn with Mirror X: the other side turns the mirrored way', np.allclose(o[1], o[0] * (-1, 1, 1), atol=1e-9), o.tolist())
o2 = cm.displace(np.array([[3.0, 0.5, 0]]), (2, 0, 0), (0.2, 0, 0), 3.0, 'CLAY', hardness=0.9)
check('no turn = the old move exactly', np.allclose(o2[0], (3.2, 0.5, 0)))
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
cube = bpy.context.active_object
res = bpy.ops.mch.concept_move('EXEC_DEFAULT', centre=(0, 0, 0), delta=(0, 0, 0), radius=5.0, hardness=0.95,
                               generate_mesh=False, mirror=False, twist=math.radians(45), twist_axis=(0, 0, 1))
xs = [v.co.x for v in cube.data.vertices]
check('F9 Turn: the cube turned 45 degrees (corner now on the X axis)', res == {'FINISHED'}
      and abs(max(xs) - math.sqrt(0.5)) < 1e-4, max(xs))

# brush size: F + drag (tool key), Real Size keeps the scene size
st = bpy.context.scene.mch_concept
st.radius_px = 100
cm.scale_size(st, 2.0)
check('size in pixels by default ([ ] / F drag)', st.radius_px == 200 and not st.lock_size)
st.lock_size = True
st.radius_world = 0.2
cm.scale_size(st, 0.5)
check('Real Size: the scene size changes instead', abs(st.radius_world - 0.1) < 1e-6 and st.radius_px == 200)
st.lock_size = False
check('F = brush size in the Concept Move tool', any(k[0] == 'mch.concept_resize' and k[1]['type'] == 'F'
                                                     for k in cm.MCH_TOOL_concept_move.bl_keymap)
      and hasattr(bpy.ops.mch, 'concept_resize'))
summary()
