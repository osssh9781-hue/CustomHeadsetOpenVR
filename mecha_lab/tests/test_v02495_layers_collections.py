"""0.24.95 Collections in the Layers panel (user: "콜렉션도 오리진 투 오브젝트랑 미러 되게 해 주고 레이어에도 나오게
해 주고 레이어 이름도 바꿀 수 있게 해 줘"):

* the scene's collections are rows (folders) with their collections, groups and parts under them; they fold; Mecha's
  own collections and a group's collection are not shown as folders
* the eye hides / shows the collection; a click on its row selects every part in it
* Origin / Mirror on a collection row: the collection is made a group in place (a handle at its middle, its parts -
  sub-collections too - stay in their collections); Origin = the handle to the middle, Mirror = a live mirrored copy
  (again: off); Ungroup takes the handle away, the collection and its parts stay as they were
* the bottom bar's Origin to Geometry / Origin to 3D Cursor / Mirror on a selected group handle: the group as one piece
* rename: parts, groups (their collection, repetition and its node tree too), collections; a second click on the same
  row soon after = rename"""
from _harness import bpy, check, cube, fresh, summary
from mathutils import Vector  # noqa: E402  (after bpy)

import mecha_lab
from mecha_lab import groups, layers_panel as lp, side_panel

fresh()
mecha_lab.register()
C = bpy.context
sc = C.scene


def part(name, loc, coll):
    ob = cube(name, size=1.0, loc=loc)
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    coll.objects.link(ob)
    return ob


robot = bpy.data.collections.new('Robot')
sc.collection.children.link(robot)
arms = bpy.data.collections.new('Arms')
robot.children.link(arms)
res = bpy.data.collections.new('MCH_Cutters')
sc.collection.children.link(res)
torso = part('Torso', (2.0, 0.0, 0.0), robot)
arm_l = part('Arm_L', (3.0, 0.0, 1.0), arms)
arm_r = part('Arm_R', (3.0, 0.0, -1.0), arms)
rock = cube('Rock', size=1.0, loc=(0.0, 5.0, 0.0))
cutter = part('Cutter', (0, 0, 0), res)
C.view_layer.update()


def rows():
    return [(it.name, d, kind) for it, d, _g, _f, kind in lp.tree(C)]


check('Collections as rows (folders), their collections and parts under them, loose parts last; Mecha\'s own '
      'collection not shown', rows() == [('Robot', 0, 'COLL'), ('Arms', 1, 'COLL'), ('Arm_L', 2, 'OBJ'),
                                       ('Arm_R', 2, 'OBJ'), ('Torso', 1, 'OBJ'), ('Rock', 0, 'OBJ')], rows())
items, _h = lp.content(C, 0.0, 270.0, 1.0)
row = next(i for i in items if i.kind == 'lrow' and i.label == 'Robot')
fold = next(i for i in items if i.kind == 'lfold' and i.action[1] == 'LAYERS:coll:Robot')
btns = [i.label for i in items if i.kind == 'pmin' and i.action[0] == 'op' and i.action[2].get('name') == 'Robot']
check('... a collection row: a folder, a fold arrow, the eye, Mirror and Origin buttons',
      row.icon == 'folder' and fold.on and 'Hide' in btns and 'Mirror (a live copy)' in btns
      and 'Origin to its middle' in btns, btns)
side_panel.toggle_fold('LAYERS:coll:Robot', False)
check('... folded: only its row', rows() == [('Robot', 0, 'COLL'), ('Rock', 0, 'OBJ')], rows())
side_panel.toggle_fold('LAYERS:coll:Robot', False)

# the eye and the click
bpy.ops.mch.layer_eye(name='Arms', coll=True)
lc = lp.layer_coll(C, arms)
check('The eye on a collection: the collection hidden (its parts not drawn), the row says so',
      lc.hide_viewport and not arm_l.visible_get() and torso.visible_get() and lp._hidden(C, arms))
bpy.ops.mch.layer_eye(name='Arms', coll=True)
check('... again: shown', not lc.hide_viewport and arm_l.visible_get() and not lp._hidden(C, arms))
rock.select_set(True)
bpy.ops.mch.layer_pick(name='Robot', coll=True)
check('A click on a collection row: every part in it selected (the others not), the row lit',
      {o.name for o in C.selected_objects} == {'Torso', 'Arm_L', 'Arm_R'}
      and next(i for i in lp.content(C, 0.0, 270.0, 1.0)[0] if i.kind == 'lrow' and i.label == 'Robot').on)

# Mirror on a collection: made a group in place
before = {o.name: o.matrix_world.translation.copy() for o in (torso, arm_l, arm_r)}
bpy.ops.mch.layer_group_op(name='Robot', coll=True, action='MIRROR')
g = bpy.data.objects.get('Robot')
car = groups.carrier_of(g)
check('Mirror on a collection: a handle made at the middle of its parts, the parts not moved and still in their '
      'collections, a live mirrored copy', groups.is_group(g) and groups.collection_of(g) == robot
      and (g.matrix_world.translation - Vector((2.5, 0.0, 0.0))).length < 1e-4
      and all((o.matrix_world.translation - before[o.name]).length < 1e-5 for o in (torso, arm_l, arm_r))
      and torso.users_collection[0] == robot and arm_l.users_collection[0] == arms
      and groups.repeat_mode(g) == 'MIRROR' and car is not None, g.matrix_world.translation if g else None)
dg = C.evaluated_depsgraph_get()
xs = []
for inst in dg.object_instances:
    if inst.is_instance and inst.parent is not None and inst.parent.original == car:
        ob = inst.object
        xs += [(inst.matrix_world @ Vector(c)).x for c in ob.bound_box]
check('... the copy is the mirror image across X (the parts at x 1.5 .. 3.5: the copy at -3.5 .. -1.5), sub-collection '
      'parts too', xs and abs(min(xs) + 3.5) < 1e-4 and abs(max(xs) + 1.5) < 1e-4 and len(xs) == 3 * 8,
      (min(xs) if xs else None, max(xs) if xs else None, len(xs)))
its = lp.content(C, 0.0, 270.0, 1.0)[0]
grow = next(i for i in its if i.kind == 'lrow' and i.label == 'Robot')
check('... in the Layers panel: the group row in its place (its Mirror button lit, no badge saying it again: the name '
      'keeps its room), its sub-collection and parts under it',
      rows() == [('Robot', 0, 'GROUP'), ('Arms', 1, 'COLL'), ('Arm_L', 2, 'OBJ'), ('Arm_R', 2, 'OBJ'),
                 ('Torso', 1, 'OBJ'), ('Rock', 0, 'OBJ')] and grow.data['badge'] == ''
      and any(i.kind == 'pmin' and i.icon == 'flip' and i.on and abs(i.y - grow.y) < 3 for i in its)
      and grow.w > 100, (rows(), grow.w))
g.location.z += 2.0
C.view_layer.update()
check('... moved by its handle: every part moves with it (the sub-collection\'s too)',
      abs(arm_l.matrix_world.translation.z - 3.0) < 1e-5 and abs(torso.matrix_world.translation.z - 2.0) < 1e-5)
g.location.z -= 2.0
C.view_layer.update()
bpy.ops.mch.layer_group_op(name='Robot', coll=False, action='MIRROR')
check('... Mirror again: off (the copy gone)', groups.repeat_mode(g) == 'OFF' and groups.carrier_of(g) is None)

# Origin
g.location = (9.0, 9.0, 9.0)
C.view_layer.update()
for o in (torso, arm_l, arm_r):                      # (the parts put back: the handle alone far away)
    mw = o.matrix_world.copy()
    mw.translation = before[o.name]
    o.matrix_world = mw
C.view_layer.update()
bpy.ops.mch.layer_group_op(name='Robot', coll=False, action='ORIGIN')
check('Origin on the row: the handle back to the middle of its parts, the parts stay put',
      (g.matrix_world.translation - Vector((2.5, 0.0, 0.0))).length < 1e-4
      and all((o.matrix_world.translation - before[o.name]).length < 1e-5 for o in (torso, arm_l, arm_r)))

# the bottom bar's buttons on a selected handle
groups.select_group(C, g)
sc.cursor.location = (0.0, 0.0, 4.0)
bpy.ops.mch.object_tidy(action='ORIGIN_CURSOR')
check('Bottom bar, the group handle selected: Origin to 3D Cursor = the handle to the cursor, the parts stay put',
      (g.matrix_world.translation - Vector((0, 0, 4))).length < 1e-5
      and all((o.matrix_world.translation - before[o.name]).length < 1e-5 for o in (torso, arm_l, arm_r)))
bpy.ops.mch.object_tidy(action='ORIGIN_GEOMETRY')
check('... Origin to Geometry = the handle to the middle of its parts',
      (g.matrix_world.translation - Vector((2.5, 0.0, 0.0))).length < 1e-4)
bpy.ops.mch.object_tidy(action='MIRROR')
on = groups.repeat_mode(g) == 'MIRROR'
bpy.ops.mch.object_tidy(action='MIRROR')
check('... Mirror = the group\'s mirrored copy on, again off', on and groups.repeat_mode(g) == 'OFF')

# rename
bpy.ops.mch.layer_rename(name='Arm_L', new_name='Left Arm')
bpy.ops.mch.layer_rename(name='Arms', coll=True, new_name='Limbs')
check('Rename: a part, a collection', arm_l.name == 'Left Arm' and arms.name == 'Limbs'
      and ('Limbs', 1, 'COLL') in rows())
groups.set_repeat(C, g, mode='MIRROR')
bpy.ops.mch.layer_rename(name='Robot', new_name='Mech')
car = groups.carrier_of(g)
check('... a group: its handle, its collection, its repetition (and its node tree) follow',
      g.name == 'Mech' and groups.collection_of(g) == robot and robot.name == 'Mech' and car is not None
      and car.name == 'Mech Repetition' and bpy.data.node_groups.get(groups.TREE_PREFIX + 'Mech') is not None
      and bpy.data.node_groups.get(groups.TREE_PREFIX + 'Robot') is None, (g.name, robot.name, car and car.name))
groups.set_repeat(C, g, mode='OFF')
check('... the mirror still switches off after the rename (no copy, no node tree left)',
      groups.carrier_of(g) is None and not [n for n in bpy.data.node_groups if n.name.startswith(groups.TREE_PREFIX)])
lp._LAST_CLICK.update(key=None, time=0.0)
check('A second click on the same row soon after = rename; a third starts over; another row, or too late: not',
      not lp.double_click('O:Rock', 10.0) and lp.double_click('O:Rock', 10.2) and not lp.double_click('O:Rock', 10.3)
      and not lp.double_click('O:Torso', 10.4) and not lp.double_click('O:Torso', 11.0)
      and not lp.double_click('C:Torso', 11.1))

# Ungroup: the collection stays
groups.ungroup(C, g)
check('Ungroup on a collection made a group: the handle gone, the collection and its parts stay as they were',
      'Mech' not in bpy.data.objects and bpy.data.collections.get('Mech') == robot and groups.GROUP_KEY not in robot
      and torso.parent is None and arm_l.parent is None and torso.users_collection[0] == robot
      and all((o.matrix_world.translation - before[o.name]).length < 1e-5 for o in (torso, arm_r))
      and rows()[0] == ('Mech', 0, 'COLL'), rows())

# speed (user: "레이어는 왜 이렇게 느려?"): Blender's users_collection walks every collection for one object - it was
# asked once per part (twice for a part in a collection row) on every rebuild of the panel
import time  # noqa: E402
me = bpy.data.meshes.new('many')
for i in range(12):
    c = bpy.data.collections.new(f'Many{i:02d}')
    sc.collection.children.link(c)
    for j in range(40):
        c.objects.link(bpy.data.objects.new(f'M{i:02d}_{j:02d}', me))
C.view_layer.update()
calls = [0]
real_uc = bpy.types.Object.users_collection


def counted(self):
    calls[0] += 1
    return real_uc.fget(self)


bpy.types.Object.users_collection = property(counted)
try:
    t0 = time.perf_counter()
    its_many, _h = lp.content(C, 0.0, 270.0, 1.0)
    took = time.perf_counter() - t0
finally:
    bpy.types.Object.users_collection = real_uc
same = all((o.name in lp.scan(C)['listed']) == lp.listed(o) for o in C.view_layer.objects)
check('480 more parts in 12 collections: the panel rebuilt without asking each part for its collections (one walk of '
      'the collections instead), the same parts listed as before', calls[0] == 0 and same
      and sum(1 for i in its_many if i.kind == 'lrow') >= 480 + 12, (calls[0], round(took * 1000, 1), same))

empty = bpy.data.collections.new('Empty')
sc.collection.children.link(empty)
r = bpy.ops.mch.layer_group_op(name='Empty', coll=True, action='ORIGIN')
check('A collection with no parts: nothing made (a message)', r == {'CANCELLED'} and len(
    [o for o in bpy.data.objects if groups.is_group(o)]) == 0)
summary()
