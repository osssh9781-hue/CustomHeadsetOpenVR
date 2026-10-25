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

# one mirror: an object with its own Mirror - a grab on the mirrored copy moves the real half
from mathutils import Vector
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
half = bpy.context.active_object
for v in half.data.vertices:
    v.co.x += 1.0                                    # the real half sits at x 0.5 .. 1.5
check('no Mirror modifier: no reflections (Concept Mirror X as before)', cm.mirror_reflections(half) == [])
mod = half.modifiers.new('MCH_Mirror', 'MIRROR')
refl = cm.mirror_reflections(half)
m = cm.base_side(half, Vector((-1.0, 0.2, 0.0)), refl)
check('a grab on the mirrored copy is mapped onto the real half', len(refl) == 1
      and (m @ Vector((-1.0, 0.2, 0.0)) - Vector((1.0, 0.2, 0.0))).length < 1e-6)
m = cm.base_side(half, Vector((1.0, 0.2, 0.0)), refl)
check('a grab on the real half stays where it is', (m @ Vector((1.0, 0.2, 0.0)) - Vector((1.0, 0.2, 0.0))).length < 1e-6)
bpy.ops.object.empty_add(location=(3.0, 0, 0))
piv = bpy.context.active_object
mod.mirror_object = piv
refl = cm.mirror_reflections(half)
check('mirror round a pivot object: reflected about its plane', (refl[0] @ Vector((1.0, 0, 0)) - Vector((5.0, 0, 0))).length < 1e-6)
mod.use_axis[1] = True
check('two axes: three mirrored copies', len(cm.mirror_reflections(half)) == 3)

# light preview: only the points the brush can reach are computed, same result
rng = np.random.default_rng(1)
co = rng.uniform(-5, 5, (20000, 3))
for mv in ({'centre': [1.0, 0, 0], 'delta': [0, 0, 0.5], 'radius': 0.8, 'falloff': 'CLAY', 'mirror': True,
            'shape': 'BOX', 'hardness': 0.5, 'axes': list(np.eye(3).ravel()), 'twist': [0, 0, 1, 0.4]},
           {'centre': [0.0, 1.0, 0], 'delta': [0.3, 0, 0], 'radius': 0.5, 'falloff': 'ELASTIC', 'mirror': False}):
    mask = cm.near_mask(co, mv)
    full = cm.move_field(mv)(co)
    fast = cm.fast_field(mv, mask)(co)
    check(f'light preview ({mv["falloff"]}): same as the full move, far fewer points computed',
          np.allclose(full, fast, atol=1e-9) and mask.sum() < len(co) * 0.25, (int(mask.sum()), float(abs(full - fast).max())))

# Even Out: the pulled part's faces get more even, the shape stays
def edge_spread(me):
    """spread of the edge lengths in the pulled part (x > 1.1 in the sphere's own space)"""
    co = cm.read_coords(me)
    ev = np.array([e.vertices[:] for e in me.edges])
    m = (co[ev[:, 0], 0] > 1.1) & (co[ev[:, 1], 0] > 1.1)
    l = np.linalg.norm(co[ev[m, 0]] - co[ev[m, 1]], axis=1)
    return float(l.std() / l.mean()), co
res = []
for eo in (False, True):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1.0, location=(20, 0, 0))
    sp = bpy.context.active_object
    bpy.ops.mch.concept_move('EXEC_DEFAULT', centre=(1, 0, 0), delta=(1.0, 0, 0), radius=0.7, hardness=0.4,
                             mirror=False, generate_mesh=True, even_out=eo)
    res.append(edge_spread(sp.data))
(s0, c0), (s1, c1) = res
check('Even Out: the faces of the pulled part are more even than without', s1 < s0 * 0.8, (s0, s1))
check('Even Out keeps the shape (the pull still reaches as far)', abs(c1[:, 0].max() - c0[:, 0].max()) < 0.05,
      (c0[:, 0].max(), c1[:, 0].max()))
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(30, 0, 0))
cb = bpy.context.active_object
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.subdivide(number_cuts=4)
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.mch.concept_move('EXEC_DEFAULT', centre=(1, 0, 0), delta=(1.0, 0, 0), radius=0.9, hardness=0.9, shape='BOX',
                         axes=(1, 0, 0, 0, 1, 0, 0, 0, 1), mirror=False, generate_mesh=True, even_out=True)
cc = cm.read_coords(cb.data)
corner = np.abs(np.abs(cc[:, 1:]) - 1.0).max(1) < 1e-6
check('Even Out: the sharp corners of a box stay sharp', corner.sum() >= 8, int(corner.sum()))
summary()
