"""0.24.81 Shift+D on a group copied the group handle alone (Blender's duplicate: the handle is the selection, the
parts are only its children).  Shift+D / Alt+D / the Duplicate buttons are the Mecha duplicate now: a group handle
copies the whole group (parts, nested groups, symmetry centres, repetition) into a collection of its own; plain
objects copy as before.  Origin to Geometry for a group: the handle to the middle of its parts.

Not verified here (no window in bpy): the grab that follows Shift+D (transform.translate needs a region)."""
import json

from _harness import bpy, check, fresh, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import groups, mecha_menu, tool_state as ts

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
real_ws = ts.is_mecha_workspace
ts.is_mecha_workspace = lambda ws: True            # (the keys work in the MECHA LAB workspace, or on a group anywhere)


def cube(name, loc):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    ob = C.active_object
    ob.name = name
    return ob


def select(*obs):
    for o in C.selected_objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    C.view_layer.objects.active = obs[0]


a, b = cube('A', (0, 0, 0)), cube('B', (2, 0, 0))
inner = groups.create(C, [cube('C', (1, 2, 0)), cube('D', (3, 2, 0))], 'Inner')
select(a, b, inner)
g = groups.create(C, [a, b, inner], 'Outer')
groups.set_repeat(C, g, mode='MIRROR', axes=(True, False, False))
n_obj, n_coll = len(bpy.data.objects), len(bpy.data.collections)
select(g)
r = bpy.ops.mch.duplicate(move=False)
h = C.active_object
check('Shift+D on a group handle: a new group (handle, its own collection), the handle selected and active',
      r == {'FINISHED'} and groups.is_group(h) and h != g and h.select_get() and not g.select_get()
      and groups.collection_of(h) is not None and groups.collection_of(h) != groups.collection_of(g), (r, h.name))
mem_g = [o for o in groups.members(g) if o.type == 'MESH' and groups.CARRIER_KEY not in o]
mem_h = [o for o in groups.members(h) if o.type == 'MESH' and groups.CARRIER_KEY not in o]
check('... every part copied (4 cubes), each its own mesh, at the same place', len(mem_h) == 4
      and all(o.data not in {m.data for m in mem_g} for o in mem_h)
      and sorted(tuple(round(c, 4) for c in o.matrix_world.translation) for o in mem_h)
      == sorted(tuple(round(c, 4) for c in o.matrix_world.translation) for o in mem_g), len(mem_h))
subs = [o for o in h.children if groups.is_group(o)]
check('... the nested group copied too (its own handle and collection under the new one)', len(subs) == 1
      and subs[0] != inner and groups.collection_of(subs[0]).name in groups.collection_of(h).children
      and len([o for o in groups.members(subs[0]) if o.type == 'MESH']) == 2)
check('... the parts follow the new handle, not the old one', all(o.parent in {h, subs[0]} for o in mem_h))
car_h = groups.carrier_of(h)
check('... Repetition (Mirror X) set up again on the copy', groups.repeat_mode(h) == 'MIRROR' and car_h is not None
      and car_h != groups.carrier_of(g))
check('... the old group untouched', len([o for o in groups.members(g) if o.type == 'MESH'
                                          and groups.CARRIER_KEY not in o]) == 4 and groups.carrier_of(g) is not None)
h.location.y += 5
C.view_layer.update()
check('Move the new handle: its parts move, the old group\'s do not',
      all(abs(o.matrix_world.translation.y - 5 - (o.matrix_world.translation.y - 5)) < 1e-6 for o in mem_h)
      and min(o.matrix_world.translation.y for o in mem_h) > 4.5
      and max(o.matrix_world.translation.y for o in mem_g) < 2.5)

# --- Alt+D: linked copies ------------------------------------------------------------------------------------------
select(g)
bpy.ops.mch.duplicate(linked=True, move=False)
h2 = C.active_object
check('Alt+D on a group: the copies share the meshes', groups.is_group(h2)
      and all(o.data in {m.data for m in mem_g} for o in groups.members(h2) if o.type == 'MESH'
              and groups.CARRIER_KEY not in o))

# --- plain objects, and a mix --------------------------------------------------------------------------------------
e = cube('E', (0, 5, 0))
select(e)
before = set(bpy.data.objects)
bpy.ops.mch.duplicate(move=False)
new = [o for o in bpy.data.objects if o not in before]
check('Shift+D on a plain object: one copy (as before)', len(new) == 1 and new[0].type == 'MESH'
      and new[0].select_get() and not e.select_get())
select(e, g)
before = set(bpy.data.objects)
bpy.ops.mch.duplicate(move=False)
new = [o for o in bpy.data.objects if o not in before and groups.CARRIER_KEY not in o]
check('... a group and an object together: the group as a whole + the object, all the copies selected',
      sum(1 for o in new if groups.is_group(o) and o.parent is None) == 1 and any(o.type == 'MESH' and o.parent is None
                                                                                     for o in new)
      and all(o.select_get() for o in new if o.parent is None) and not g.select_get())
select(a)                                      # a part inside a group: the part alone (it stays in the group)
before = set(bpy.data.objects)
bpy.ops.mch.duplicate(move=False)
new = [o for o in bpy.data.objects if o not in before]
check('... a part picked inside a group: that part alone, still in the group', len(new) == 1
      and new[0].parent == g and groups.collection_of(g).name in [c.name for c in new[0].users_collection])

# --- Origin to Geometry for a group --------------------------------------------------------------------------------
select(g)
g.location.x += 10
C.view_layer.update()
pos = {o.name: o.matrix_world.translation.copy() for o in groups.members(g) if o.type == 'MESH'}
r = bpy.ops.mch.group_action(action='ORIGIN')
C.view_layer.update()
lo, hi = groups.group_box(g)
check('Group > Origin to Geometry: the handle at the middle of its parts, the parts where they were',
      r == {'FINISHED'} and (g.matrix_world.translation - (lo + hi) / 2).length < 1e-4
      and all((o.matrix_world.translation - pos[o.name]).length < 1e-4 for o in groups.members(g)
              if o.type == 'MESH'), (r, g.matrix_world.translation, (lo + hi) / 2))
check('... in the Groups sidebar card (Duplicate / Origin to Geometry) and the Mecha Menu (Group Origin)',
      "'ORIGIN'" in __import__('inspect').getsource(groups.draw_list)
      and any(lab == 'Group Origin' for sec, items in mecha_menu.ACTIONS for lab, *_r in items))

# --- the keys and buttons point at the Mecha duplicate ---------------------------------------------------------------
kc = C.window_manager.keyconfigs.addon
km = kc.keymaps.get('Object Mode') if kc else None
items = [(i.idname, i.shift, i.alt) for i in (km.keymap_items if km else []) if i.type == 'D']
check('Shift+D and Alt+D (Object Mode) run mch.duplicate', ('mch.duplicate', True, False) in items
      and ('mch.duplicate', False, True) in items, items)
check('... Mecha Menu / Actions card Duplicate too', any(op == 'mch.duplicate' for sec, items in mecha_menu.ACTIONS
                                                          for lab, ic, op, *_r in items)
      and 'mch.duplicate' in __import__('inspect').getsource(__import__('mecha_lab.actions_menu', fromlist=['x'])))
ts.is_mecha_workspace = real_ws
select(e)
check('Outside MECHA LAB too (the Mecha Menu / Actions card call it there): a plain object gets Blender\'s duplicate + '
      'grab through it', groups.MCH_OT_duplicate.poll(C))
select(g)
check('... a group handle anywhere: the Mecha duplicate', groups.MCH_OT_duplicate.poll(C))
select(e)
bpy.ops.object.mode_set(mode='EDIT')
check('... not in Edit mode (Blender\'s own Shift+D there)', not groups.MCH_OT_duplicate.poll(C))
bpy.ops.object.mode_set(mode='OBJECT')
summary()
