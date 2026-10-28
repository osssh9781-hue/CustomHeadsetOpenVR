"""0.24.31 Concept Move and Path Move in the Mecha menus (tool list, bottom bar, V pie, sidebar) and hold D + drag
= Concept Move in any Mecha tool (editable in the Hotkeys box)."""
from _harness import bpy, check, summary
import mecha_lab
from mecha_lab import tool_state as ts, bottom_bar as bb, ui_tool_settings as uts, workspace_ui as wui

mecha_lab.register()
vis = {t[0] for t in ts.VISIBLE_TOOLS}
check('Concept Move and Path Move in the tool list (Jungle Gym removed)', {'CMOVE', 'CPATH'} <= vis and 'GYM' not in ts.TOOL_BY_ID)
check('their native tools', ts.TOOL_BY_ID['CMOVE'][5] == 'mecha.concept_move' and ts.TOOL_BY_ID['CPATH'][5] == 'mecha.concept_path'
      and ts.NATIVE_TO_TOOL.get('mecha.concept_path') == 'CPATH')
check('enum numbers new (saved files keep their old tools)', ts._ENUM_NUMBERS['CMOVE'] == 48 and ts._ENUM_NUMBERS['CPATH'] == 50
      and len(set(ts._ENUM_NUMBERS.values())) == len(ts._ENUM_NUMBERS))
check('bottom bar buttons', {'CMOVE', 'CPATH'} <= {t[0] for t in bb.BAR_TOOLS})
check('V pie: stacked under Primitive', bb.PIE_SHARED.get('PRIMITIVE')[:2] == ('CMOVE', 'CPATH'))   # (0.24.76 + Silhouette Move)
check('sidebar settings drawers', 'CMOVE' in uts.DRAWERS and 'CPATH' in uts.DRAWERS)
check('an assignable key per tool (Hotkeys box)', {'CMOVE', 'CPATH'} <= set(wui.tool_key_ids()))
items = [it for _km, it in wui._keymaps if it.idname == 'mch.concept_hold']
check('hold D + drag key item (Object Mode)', len(items) == 1 and items[0].key_modifier == 'D'
      and items[0].type == 'LEFTMOUSE', [(i.type, i.key_modifier) for i in items])
check('hold D + drag also first in the Mecha drawing tools', wui._tool_keymap('CUT')[0][0] == 'mch.concept_hold'
      and wui._tool_keymap('CUT')[0][1].get('key_modifier') == 'D')
check('the hold key shows in the Hotkeys box (and is saved)', 'mch.concept_hold' in wui._HOTKEY_IDS
      and 'key_modifier' in wui._KEY_FIELDS)
check('hold operator registered', hasattr(bpy.ops.mch, 'concept_hold'))
bpy.ops.mch.set_tool(tool='CPATH')
check('picking Path Move from the menu selects it', bpy.context.scene.mch_settings.mch_active_tool == 'CPATH')

# Ctrl while dragging: turn the grabbed part (and F9 Turn)
import json
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

# Path Move: the grabbed box / ball keeps its shape and follows the path, turning where it bends
from mathutils import Vector
L = [Vector((0, 0, 0)), Vector((1, 0, 0)), Vector((2, 0, 0)), Vector((2, 0, 1)), Vector((2, 0, 2))]
mv = cm.path_moves(L, 0.3, shape='BOX')
ang = sum(m['twist'][3] for m in mv if 'twist' in m)
check('path moves: one short grab per step, the turns add up to the bend (90 degrees)', len(mv) == 4
      and abs(math.degrees(ang) - 90) < 1e-6, math.degrees(ang))
ax_last = np.array(mv[-1]['axes']).reshape(3, 3)
check('the box turns with the path (its X axis now points up the new way)', np.allclose(np.abs(ax_last[0]), (0, 0, 1), atol=1e-9),
      ax_last.tolist())
check('Taper 0: the same size all the way', len({round(m['radius'], 9) for m in mv}) == 1)
check('Follow Turns off: no turning', all('twist' not in m for m in cm.path_moves(L, 0.3, turn=False)))
sp = cm.smooth_path([Vector((0, 0, 0)), Vector((1, 0.2, 0)), Vector((2, -0.2, 0)), Vector((3, 0, 0))])
check('the shake is taken out of a hand-drawn path, the ends stay', abs(sp[1].y) < 0.2 and sp[0] == Vector((0, 0, 0))
      and sp[-1] == Vector((3, 0, 0)))


def grid_cube(loc):
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=loc)
    o = bpy.context.active_object
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=9)
    bpy.ops.object.mode_set(mode='OBJECT')
    return o


def tip_extent(o, at, r):
    co = cm.read_coords(o.data)
    near = co[np.linalg.norm(co - np.asarray(at), axis=1) < r]
    return near, np.ptp(near, axis=0) if len(near) else np.zeros(3)


for shape in ('BOX', 'SPHERE'):
    o = grid_cube((50, 0, 0))
    path = [(1.0, 0, 0), (1.6, 0, 0), (2.2, 0, 0), (2.8, 0, 0), (3.4, 0, 0)]
    res = bpy.ops.mch.concept_path('EXEC_DEFAULT', path=json.dumps([list(p) for p in path]), radius=0.45, hardness=0.9,
                                   shape=shape, mirror=False, generate_mesh=True, turn=True)
    near0 = cm.read_coords(o.data)
    _n, ext = tip_extent(o, (3.4, 0, 0), 0.6)
    long_faces = max(o.data.edges[i].calc_length() if hasattr(o.data.edges[i], 'calc_length') else 0 for i in range(0))  if False else 0
    check(f'Path Move ({shape}): the grabbed part arrives at the end of the path, still as wide as it was',
          res == {'FINISHED'} and near0[:, 0].max() > 3.3 and 0.55 < ext[1] < 1.1, (near0[:, 0].max(), ext.tolist()))
    mid = near0[(near0[:, 0] > 2.0) & (near0[:, 0] < 2.6)]
    check(f'Path Move ({shape}): a body along the path (not a thin thread)', len(mid) > 8 and np.ptp(mid[:, 1]) > 0.5,
          (len(mid), float(np.ptp(mid[:, 1])) if len(mid) else 0))
bend = [(1.0, 0, 0), (1.6, 0, 0), (2.2, 0, 0), (2.4, 0, 0.6), (2.4, 0, 1.2), (2.4, 0, 1.8)]
tops = {}
for turn in (True, False):
    o = grid_cube((60 + 10 * turn, 0, 0))
    res = bpy.ops.mch.concept_path('EXEC_DEFAULT', path=json.dumps([list(p) for p in bend]), radius=0.45, hardness=0.9,
                                   shape='BOX', mirror=False, generate_mesh=True, turn=turn)
    co = cm.read_coords(o.data)
    top = co[co[:, 2] > co[:, 2].max() - 0.15]
    tops[turn] = (res, co[:, 2].max(), np.ptp(top[:, 0]))
check('Path Move round a bend: it goes up the new way', tops[True][0] == {'FINISHED'} and tops[True][1] > 1.7, tops[True][1])
check('Follow Turns: the end turned with the path (its flat side faces up, wide across X)',
      tops[True][2] > 0.5 and tops[True][2] > tops[False][2] * 1.5, (tops[True][2], tops[False][2]))

# Ctrl turn as seen on screen: left / right round the screen's up axis, up / down round its right axis
from mathutils import Matrix
ax, an = cm.screen_turn(Matrix.Identity(3), math.radians(90), 0.0)
front = Matrix.Rotation(an, 3, ax) @ Vector((0, 0, 1))
check('Ctrl + mouse right: the front turns to the right (round the screen up axis)', (front - Vector((1, 0, 0))).length < 1e-6,
      (tuple(ax), math.degrees(an)))
ax, an = cm.screen_turn(Matrix.Identity(3), 0.0, math.radians(90))
front = Matrix.Rotation(an, 3, ax) @ Vector((0, 0, 1))
check('Ctrl + mouse up: the front tips up (round the screen right axis)', (front - Vector((0, 1, 0))).length < 1e-6, tuple(front))
vr = Matrix.Rotation(math.radians(90), 3, 'X')               # a view from the top: screen up = world -Y ... any view
ax, an = cm.screen_turn(vr, math.radians(30), 0.0)
check('follows the view: the axis is the screen up axis in the world', (ax - vr @ Vector((0, 1, 0))).length < 1e-6
      and abs(math.degrees(an) - 30) < 1e-4)
summary()
