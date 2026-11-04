"""0.24.95 Work Scene (user: "그룹 안에 넣은 거 콜렉션 인스턴스로 복사하면 그룹 원본 수정하면 인스턴스도 변경되잖아",
"그렇게 버튼 만들어 줘"):

* Work Scene: the group to a scene of its own ("Work - <group>": only it, the main scene's world and Mecha settings);
  in the main scene a Collection Instance of it where it was - it shows the parts in the same places
* live: an edit in the work scene (a part's mesh, the group moved) shows on the instance at once
* Main / Work: the window's scene switches (New Window off: the work scene in this window)
* Bring Back: the group back in the main scene (moved as the instance was moved), the instance and the work scene
  gone, the parts in the main scene again
* the selection (no group): made a group, then sent
* the buttons: the Layers panel's second row, the sidebar Groups card, the Mecha Menu's Groups"""
from _harness import bpy, check, fresh, summary
from mathutils import Matrix, Vector

import mecha_lab
from mecha_lab import groups, layers_panel, mecha_menu, work_scene as wk

fresh()
mecha_lab.register()
C = bpy.context
main = C.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(2.0, 0.0, 0.0))
a = C.active_object
bpy.ops.mesh.primitive_cylinder_add(radius=0.3, depth=1.0, location=(3.0, 0.5, 0.0))
b = C.active_object
a.select_set(True)
g = groups.create(C, [a, b], 'Arm')
coll = groups.collection_of(g)
before = {o.name: o.matrix_world.copy() for o in (a, b)}
main.mch_tire.diameter = 0.9                     # (a Mecha setting: the work scene has it too)


def shown(scene, inst_ob):
    """{part name: world matrix} the instance shows in ``scene``."""
    dg = scene.view_layers[0].depsgraph
    dg.update()
    out = {}
    for di in dg.object_instances:
        if di.is_instance and di.parent is not None and di.parent.original == inst_ob:
            out[di.object.original.name] = di.matrix_world.copy()
    return out


def close(m1, m2, tol=1e-4):
    return all(abs(m1[i][j] - m2[i][j]) < tol for i in range(4) for j in range(4))


C.view_layer.objects.active = g
r = bpy.ops.mch.work_scene(action='SEND', new_window=False)
ws = bpy.data.scenes.get('Work - Arm')
inst = next((o for o in main.objects if o.get(wk.OF) == coll.name), None)
check('Work Scene: the group in a scene of its own ("Work - Arm": only its parts and handle), the main scene\'s '
      'world and Mecha settings', r == {'FINISHED'} and ws is not None
      and {o.name for o in ws.objects} == {a.name, b.name, g.name} and ws.world == main.world
      and abs(ws.mch_tire.diameter - 0.9) < 1e-6, sorted(o.name for o in ws.objects) if ws else None)
check('... in the main scene: the parts gone, a Collection Instance of the group where it was',
      inst is not None and inst.instance_type == 'COLLECTION' and inst.instance_collection == coll
      and a.name not in main.objects and b.name not in main.objects and g.name not in main.objects
      and (inst.matrix_world.translation - g.matrix_world.translation).length < 1e-6)
sh = shown(main, inst)
check('... the instance shows every part in the same place it was', set(sh) == {a.name, b.name}
      and all(close(sh[n], before[n]) for n in sh), sorted(sh))

v0 = a.data.vertices[0].co.copy()
a.data.vertices[0].co += Vector((0.0, 0.0, 0.5))
a.data.update()
dg = main.view_layers[0].depsgraph
dg.update()
moved = None
for di in dg.object_instances:
    if di.is_instance and di.parent is not None and di.parent.original == inst and di.object.original == a:
        moved = di.object.data.vertices[0].co.copy()
check('Live: a part\'s mesh edited in the work scene - the instance in the main scene shows it at once',
      moved is not None and abs(moved.z - (v0.z + 0.5)) < 1e-6, moved)
g.location.z += 1.0
ws.view_layers[0].depsgraph.update()
sh = shown(main, inst)
check('... the group moved in the work scene (its handle up 1): the instance shows it moved',
      a.name in sh and abs(sh[a.name].translation.z - (before[a.name].translation.z + 1.0)) < 1e-4,
      round(sh[a.name].translation.z, 4) if a.name in sh else None)
g.location.z -= 1.0
ws.view_layers[0].depsgraph.update()

check('... New Window off: this window shows the work scene', C.scene == ws, C.scene.name)
r = bpy.ops.mch.work_scene(action='SWITCH')
check('Main / Work: from the work scene this window goes back to the main scene', r == {'FINISHED'}
      and C.scene == main, C.scene.name)
C.view_layer.objects.active = inst
r = bpy.ops.mch.work_scene(action='SWITCH')
ok = r == {'FINISHED'} and C.scene == ws
bpy.ops.mch.work_scene(action='SWITCH')
check('... the instance selected in the main scene: to the work scene, and back again', ok and C.scene == main)
C.view_layer.objects.active = inst
cells = [c[0] for c in layers_panel._toolbar(C)]
row2 = [c[0] for c in wk.toolbar_cells(C)]
check('The buttons: the Layers panel\'s second row (the instance selected: Work / Bring Back), the Mecha Menu\'s '
      'Groups (Work Scene, Bring Back)', row2 == ['Work', 'Bring Back'] and 'Group' in cells
      and any(lab == 'Work Scene' for sec, items in mecha_menu.ACTIONS for lab, *_r in items)
      and any(lab == 'Bring Back' for sec, items in mecha_menu.ACTIONS for lab, *_r in items)
      and mecha_menu._needs_ok(C, 'work'), row2)

inst.matrix_world = Matrix.Translation(inst.matrix_world.translation + Vector((0.0, 3.0, 0.0)))
C.view_layer.update()
r = bpy.ops.mch.work_scene(action='BACK')
check('Bring Back: the group in the main scene again - moved where the instance was moved (3 along Y); the '
      'instance and the work scene gone', r == {'FINISHED'} and g.name in main.objects and a.name in main.objects
      and b.name in main.objects and 'Work - Arm' not in bpy.data.scenes
      and not [o for o in main.objects if o.get(wk.OF)] and coll.name in main.collection.children
      and abs(a.matrix_world.translation.y - (before[a.name].translation.y + 3.0)) < 1e-4
      and not coll.get(wk.WORK) and tuple(coll.instance_offset) == (0.0, 0.0, 0.0),
      round(a.matrix_world.translation.y, 4))
check('... the group still a group (its handle the parent, its collection)', groups.group_of(a) == g
      and groups.collection_of(g) == coll)

for o in C.selected_objects:
    o.select_set(False)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.4, location=(-3.0, 0.0, 0.0))
s1 = C.active_object
bpy.ops.mesh.primitive_cube_add(size=0.5, location=(-4.0, 0.0, 0.0))
s2 = C.active_object
s1.select_set(True)
r = bpy.ops.mch.work_scene(action='SEND', new_window=False)
g2 = groups.group_of(s1)
check('Work Scene with parts selected (no group): made a group first, then sent', r == {'FINISHED'}
      and g2 is not None and groups.group_of(s2) == g2 and f'Work - {g2.name}' in bpy.data.scenes
      and s1.name not in main.objects, g2.name if g2 else None)
summary()
