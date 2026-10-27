"""0.24.52 Mecha Menu: Shading (Flat / Auto Smooth / Smooth), clicks never close it, leaving it does.
Symmetry the Substance 3D Modeler way (Off / Mirror / Radial / Kaleido, one mirror for Alt+X, the menu and the
card; the Symmetry card replaces the old mirror side buttons).  Groups: group / ungroup / merge, enter / exit,
Repetition (Mirror / Radial / Kaleido, linked Geometry Nodes copies), Apply."""
import inspect
import json
import types

from _harness import bpy, check, cube, fresh, select_only, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import groups as gr, mecha_menu as mm, symmetry as sy, actions_menu as am, mirror_hud, quick_hud

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene


def eval_verts(ob):
    dg = C.evaluated_depsgraph_get()
    return len(ob.evaluated_get(dg).to_mesh().vertices)


# --- menu ------------------------------------------------------------------------------------------------------
part = cube('Part', loc=(2.0, 0.0, 0.0))
select_only(part)
items = mm.build(C, 800, 450, 1600, 900, 1.0)
secs = [i.label for i in items if i.kind == 'section']
shade = {i.label: i.action[1] for i in items if i.kind == 'abtn' and i.action and i.action[0] == 'op'}
check('Menu: a Shading section with Flat / Auto Smooth / Smooth', 'Shading' in secs
      and shade.get('Flat') == 'object.shade_flat' and shade.get('Auto Smooth') == 'object.shade_auto_smooth'
      and shade.get('Smooth') == 'object.shade_smooth')
flat = next(i for i in items if i.label == 'Flat')
mm.run(C, flat, hold=True)
check('... Flat shades the part flat', not any(p.use_smooth for p in part.data.polygons))
mm.run(C, next(i for i in items if i.label == 'Smooth'), hold=True)
check('... Smooth shades it smooth', all(p.use_smooth for p in part.data.polygons))
S.mch_settings.mch_active_tool = 'BASE'
bitems = mm.build(C, 800, 450, 1600, 900, 1.0)
lasso = [i for i in bitems if i.kind == 'tile' and i.action and i.action[0] == 'shape']
check('Base Mesh menu: the profiles and the lasso shapes again (they had gone from the menu)',
      any(i.kind == 'tile' and i.action[1] == 'mch.set_profile' for i in bitems) and len(lasso) >= 5
      and 'Lasso' in [i.label for i in bitems if i.kind == 'section'])
mm.run(C, next(i for i in lasso if i.action[1] != S.mch_brush.shape))
check('... a lasso tile sets the shape', any(S.mch_brush.shape == i.action[1] for i in lasso))
S.mch_settings.mch_active_tool = 'CUT'
src = inspect.getsource(mm.MCH_OT_mecha_menu.modal)
check('Clicks never close the menu (tools switch in place), moving off it does',
      "run(context, it, event.ctrl and not self.hold, True)" in src and 'self._near(x, y)' in src)
cards = [i for i in items if i.kind == 'card']
mid = cards[1]
check('... "near": over a card yes, in the gap between cards yes, far away no',
      mm.near(items, mid.x + 5, mid.y + mid.h - 5, 36)
      and mm.near(items, (cards[0].x + cards[0].w + cards[1].x) / 2, mid.y + mid.h - 40, 36)
      and not mm.near(items, mid.x + mid.w / 2, mid.y - 200, 36) and not mm.near(items, 5, 5, 36))
check('... a middle click while the menu is open does not open a second one', '_OPEN[0]'
      in inspect.getsource(mm.MCH_OT_mecha_mmb_gate.poll))

# --- symmetry ----------------------------------------------------------------------------------------------------
from mecha_lab import mirror_tools as mt
r = bpy.ops.mch.actions_mirror(axis=0)
check('Menu Mirror X = the same live mirror as Alt+X (MCH_Mirror; the card, Apply and Enter see it)',
      r == {'FINISHED'} and part.modifiers.get(mt.MOD_NAME) is not None and sy.mode_of(part) == 'MIRROR'
      and sy.axes_of(part) == (True, False, False) and part.modifiers.get('MCH_Symmetry') is None)
check('... a copy on the other side of the world centre', eval_verts(part) == 16)
items = mm.build(C, 800, 450, 1600, 900, 1.0)
rad = next(i for i in items if i.label == 'Radial')
check('Menu Radial: with a mirror on it means Kaleido', rad.action[2] == {'mode': 'KALEIDO'} and not rad.on)
mm.run(C, rad, hold=True)
check('Kaleido: mirror first, then the radial copies', sy.mode_of(part) == 'KALEIDO'
      and [m.name for m in part.modifiers] == [mt.MOD_NAME, 'MCH_RadialSym']
      and eval_verts(part) == 8 * 2 * S.mch_rsym.count)
sy.set_count(C, 4)
check('Count: 4 copies round the axis', eval_verts(part) == 8 * 2 * 4)
sy.set_mode(C, part, 'RADIAL')
check('Radial only: the mirror goes, the copies stay', sy.mode_of(part) == 'RADIAL' and eval_verts(part) == 8 * 4)
sy.set_radial_axis(C, 'X')
check('Radial axis X', S.mch_rsym.axis == 'X')
sy.set_mode(C, part, 'MIRROR')
check('Mirror only: the radial copies, helper and centre go', sy.mode_of(part) == 'MIRROR'
      and S.mch_rsym.pivot is None and not any(o.name.startswith('MCH_RS_') for o in bpy.data.objects))
sy.toggle_axis(C, part, 2)
m = sy.mirror_mod(part)
if any(m.use_bisect_axis):
    sy.toggle_bisect(part)                     # bisect on: the Z plane through the world centre cuts the cube
check('Mirror planes X + Z (bisect off: 4 whole copies)', sy.axes_of(part) == (True, False, True)
      and eval_verts(part) == 32)
on = sy.toggle_bisect(part)
check('Bisect toggle: on only for the active planes', on and tuple(m.use_bisect_axis) == (True, False, True))
off = sy.toggle_bisect(part)
check('... and off again', not off and not any(m.use_bisect_axis))
check('Flip toggle', sy.toggle_flip(part) and all(m.use_bisect_flip_axis) and not sy.toggle_flip(part)
      and not any(m.use_bisect_flip_axis))
sy.toggle_axis(C, part, 0)
sy.toggle_axis(C, part, 2)
check('Last plane off: the mirror ends', sy.mode_of(part) == 'OFF' and not part.modifiers)
legacy = part.modifiers.new('MCH_Symmetry', 'MIRROR')
legacy.use_axis = (False, True, False)
sy.set_mode(C, part, 'MIRROR')
check('A 0.24.49 menu mirror is taken over (one mirror, its planes kept)', part.modifiers.get('MCH_Symmetry') is None
      and sy.axes_of(part) == (False, True, False))
nv = len(part.data.vertices)
sy.apply(C, part)
check('Apply bakes it into the mesh', not part.modifiers and len(part.data.vertices) > nv)

# --- the card ------------------------------------------------------------------------------------------------
import mecha_lab.bottom_bar as bb
real_ui = bb.ui_active
bb.ui_active = lambda c: True
part2 = cube('Part2', loc=(0, 3, 0))
select_only(part2)
check('No symmetry: no card', sy.card_target(C) == (None, None))
bpy.ops.mch.symmetry_card()
check('Card opened from the menu (Symmetry Card)', sy.card_target(C) == ('PART', part2))
items = sy.build_card(C, 1600, 900, 1.0)
labels = [i.label for i in items if i.kind == 'seg']
check('Card: Off / Mirror / Radial / Kaleido', labels[:4] == ['Off', 'Mirror', 'Radial', 'Kaleido'])
sy.run_card(C, next(i for i in items if i.label == 'Kaleido'))
items = sy.build_card(C, 1600, 900, 1.0)
secs = [i.label for i in items if i.kind == 'section']
check('... Kaleido shows Mirror (X Y Z, Bisect, Flip) and Radial (axis, count, centre), Apply / Remove',
      secs == ['Mirror', 'Radial'] and {'Mirror X', 'Mirror Y', 'Mirror Z'} <= {i.label for i in items}
      and {'Bisect', 'Flip'} <= {i.label for i in items if i.kind == 'toggle'}
      and {'Apply', 'Remove'} <= {i.label for i in items if i.kind == 'seg'})
plus = next(i for i in items if i.label == '+')
c0 = S.mch_rsym.count
sy.run_card(C, plus)
check('... + adds a copy', S.mch_rsym.count == c0 + 1)
check('... a new Kaleido starts with the plane that holds the radial axis (axis X: the Y plane)',
      S.mch_rsym.axis == 'X' and sy.axes_of(part2) == (False, True, False))
sy.run_card(C, next(i for i in items if i.label == 'Mirror Z'))
check('... Mirror Z plane', sy.axes_of(part2) == (False, True, True))
check('... Kaleido: the mirror planes go through the radial centre (its mirror object)',
      sy.mirror_mod(part2).mirror_object == S.mch_rsym.pivot)
sy.run_card(C, next(i for i in items if i.label == 'Remove'))
check('... Remove: off, card closed', sy.mode_of(part2) == 'OFF' and sy.card_target(C) == (None, None))
check('... Remove: the radial centre is gone, nothing points at it',
      S.mch_rsym.pivot is None and not any(o.name.startswith('MCH_RadialPivot') for o in bpy.data.objects))

# a real kaleidoscope: radial Z x4 round the world origin + the X plane -> the shape has 8-fold dihedral symmetry
S.mch_rsym.axis = 'Z'
S.mch_rsym.count = 4
part3 = cube('Part3', loc=(2.0, 0.6, 0.3), size=0.5)
part3.rotation_euler.z = 0.3
C.view_layer.update()
select_only(part3)
sy.set_mode(C, part3, 'KALEIDO')
m3 = sy.mirror_mod(part3)
if any(m3.use_bisect_axis):
    sy.toggle_bisect(part3)
C.view_layer.update()
dg = C.evaluated_depsgraph_get()
me = part3.evaluated_get(dg).to_mesh()
pts = {tuple(round(c, 3) for c in (part3.matrix_world @ v.co)) for v in me.vertices}


def has(p):
    return any(abs(p[0] - q[0]) < 2e-3 and abs(p[1] - q[1]) < 2e-3 and abs(p[2] - q[2]) < 2e-3 for q in pts)


check('Kaleido = mirror in each slice: the copies are symmetric to the X plane and to a quarter turn round Z',
      len(me.vertices) == 8 * 2 * 4 and all(has((-x, y, z)) and has((-y, x, z)) for x, y, z in pts)
      and S.mch_rsym.pivot.matrix_world.translation.length < 1e-6, len(me.vertices))
S.mch_rsym.pivot.location = (1.0, 1.0, 0.0)
C.view_layer.update()
check('... move the centre: the mirror planes move with it (one origin)', m3.mirror_object == S.mch_rsym.pivot)
sy.set_mode(C, part3, 'MIRROR')
check('... back to Mirror: the radial centre goes, the mirror is on the mirror centre again',
      S.mch_rsym.pivot is None and m3.mirror_object is not None and m3.mirror_object.get('_mch_world_pivot')
      and m3.mirror_object.matrix_world.translation.length < 1e-6)
sy.set_mode(C, part3, 'OFF')

check('Card clicks are taken first by the HUD click operator (in every tool)', 'symmetry.card_hit'
      in inspect.getsource(quick_hud.MCH_OT_quick_hud_press.invoke))
check('The old mirror side buttons are replaced by the card (Preferences: Symmetry Card)',
      not mirror_hud.classic() and 'classic()' in inspect.getsource(mirror_hud.MCH_GGT_mirror_hud.poll))

# --- groups ---------------------------------------------------------------------------------------------------
fresh()
S = C.scene
a = cube('A', loc=(3, 1, 0))
b = cube('B', loc=(3, -1, 0))
home = list(a.users_collection)
select_only(a, b)
r = bpy.ops.mch.group()
g = C.active_object
check('Group: a handle at the middle, the parts inside follow it', r == {'FINISHED'} and gr.is_group(g)
      and a.parent == g and b.parent == g and (g.matrix_world.translation - Vector((3, 0, 0))).length < 1e-6
      and set(gr.members(g)) == {a, b})
g.location.z += 1.0
C.view_layer.update()
check('... move the handle: the parts move', abs(a.matrix_world.translation.z - 1.0) < 1e-6)
g.location.z -= 1.0
C.view_layer.update()


def copies(g):
    dg = C.evaluated_depsgraph_get()
    car = gr.carrier_of(g)
    return [i.matrix_world.translation.copy() for i in dg.object_instances
            if i.is_instance and i.parent is not None and car is not None and i.parent.original == car]


r = bpy.ops.mch.group_repeat(mode='MIRROR')
check('Repetition Mirror X: linked copies across the world X plane (0.24.53: world axes by default)',
      r == {'FINISHED'} and len(copies(g)) == 2 and gr.repeat_center(g) == 'WORLD'
      and all(abs(p.x + 3.0) < 1e-6 for p in copies(g)) and C.window_manager.mch_sym_card == g.name,
      [tuple(round(c, 3) for c in p) for p in copies(g)])
gr.set_repeat(C, g, center='GROUP')
check('... Centre Group: through the group handle instead', all(abs(p.x - 3.0) < 1e-6 for p in copies(g)))
S.cursor.location = (1.0, 0.0, 0.0)
gr.set_repeat(C, g, center='CURSOR')
check('... Centre Cursor: through the 3D cursor', all(abs(p.x + 1.0) < 1e-6 for p in copies(g)))
S.cursor.location = (0.0, 0.0, 0.0)
gr.set_repeat(C, g, center='WORLD')
g.location.y += 2.0
C.view_layer.update()
check('... World: moving the group moves the copies on the other side', all(abs(p.x + 3.0) < 1e-6 and p.y > 0.5
                                                                          for p in copies(g)))
g.location.y -= 2.0
C.view_layer.update()
gr.set_repeat(C, g, mode='RADIAL', count=4)
check('Radial x4 round the world Z axis: 3 copies of each part', len(copies(g)) == 6)
gr.set_repeat(C, g, mode='KALEIDO', axes=(True, False, False), count=3)
check('Kaleido (mirror X + 3 round): 5 copies of each part', len(copies(g)) == 10)
before = sorted(round(p.length, 4) for p in copies(g))
a.location.x += 0.5
C.view_layer.update()
after = sorted(round(p.length, 4) for p in copies(g))
check('Linked: move a part and its copies move too', before != after)
a.location.x -= 0.5
bb.ui_active = lambda c: True
select_only(g)
C.view_layer.objects.active = g
check('The group handle selected: the card is its Repetition', sy.card_target(C) == ('GROUP', g))
items = sy.build_card(C, 1600, 900, 1.0)
sy.run_card(C, next(i for i in items if i.label == 'Radial'))
check('... Radial from the card', gr.repeat_mode(g) == 'RADIAL')
items = sy.build_card(C, 1600, 900, 1.0)
cen = {i.label: i for i in items if i.action and i.action[0] == 'sym_center'}
check('... the group card has Centre World (on) / Group / Cursor', set(cen) == {'World', 'Group', 'Cursor'}
      and cen['World'].on)
sy.run_card(C, cen['Group'])
check('... Group from the card', gr.repeat_center(g) == 'GROUP')
sy.run_card(C, next(i for i in sy.build_card(C, 1600, 900, 1.0) if i.label == 'World'))
card = next(i for i in sy.build_card(C, 1600, 900, 1.0) if i.kind == 'card')
from mecha_lab import side_panel as _sp          # 0.24.59 left of the side panel when it shows
_room = 1600 - _sp.taken(C, 1.0)
check('The card is docked at the right of the viewport (not over the part / group)', card.x + card.w > _room - 100
      and card.x > _room - 600, (card.x, card.w, _room))
sy.run_card(C, next(i for i in sy.build_card(C, 1600, 900, 1.0) if i.label == '+'))
check('... + one more copy', gr.repeat_count(g) == 4)
n_before = len(gr.members(g))
made = gr.make_real(C, g)
check('Apply: the copies become real objects in the group, the repetition is off', made == 6
      and len(gr.members(g)) == n_before + 6 and gr.carrier_of(g) is None and gr.repeat_mode(g) == 'OFF')
outside = cube('Outside', loc=(-4, 0, 0))
select_only(a)
bpy.ops.mch.group_action(action='ENTER')
check('Enter: everything else is wire and cannot be picked', outside.hide_select
      and outside.display_type == 'WIRE' and gr.scope(C) == g)
bpy.ops.mch.group_action(action='EXIT')
check('Exit: as before', not outside.hide_select and outside.display_type != 'WIRE' and gr.scope(C) is None)
select_only(a)
bpy.ops.mch.group_action(action='MERGE')
check('Merge: the group\'s meshes are one mesh', len([o for o in gr.members(g) if o.type == 'MESH']) == 1)
merged = [o for o in gr.members(g) if o.type == 'MESH'][0]
select_only(merged)
bpy.ops.mch.group_action(action='UNGROUP')
check('Ungroup: back in its old collection, handle and group collection gone',
      merged.parent is None and set(merged.users_collection) == set(home)
      and not any(gr.is_group(o) for o in bpy.data.objects)
      and not any(c.get(gr.GROUP_KEY) for c in bpy.data.collections))
# nested groups
p1, p2, p3 = cube('P1', loc=(0, 0, 0)), cube('P2', loc=(1, 0, 0)), cube('P3', loc=(5, 0, 0))
g1 = gr.create(C, [p1, p2])
g2 = gr.create(C, [g1, p3])
check('Groups in groups: the inner group (handle + collection) goes inside', g1.parent == g2
      and gr.collection_of(g1).name in gr.collection_of(g2).children and gr.group_of(p1) == g1)
p4 = cube('P4', loc=(7, 0, 0))
gr.collection_of(g2).objects.link(p4)
for c in [c for c in p4.users_collection if c != gr.collection_of(g2)]:
    c.objects.unlink(p4)
p4.parent = g2
g3 = gr.create(C, [p3, p4])
check('... grouping parts inside a group: the new group nests in that group', g3.parent == g2
      and gr.collection_of(g3).name in gr.collection_of(g2).children and gr.group_of(p3) == g3)
gr.ungroup(C, g3)
check('... ungroup it: back in the outer group', gr.group_of(p3) == g2 and p3.parent == g2)
gr.set_repeat(C, g2, mode='MIRROR')
check('... the outer repetition copies the inner group too', len(copies(g2)) >= 3)
bb.ui_active = real_ui
summary()
