"""0.24.22 Apply Modifiers (click a mesh): every enabled modifier of the clicked mesh is applied in stack order,
top to bottom; switched-off ones stay; a failing one stops the run (the ones before it stay applied)."""
from _harness import bpy, check, cube, fresh, non_manifold, summary

import mecha_lab
from mecha_lab import bottom_bar as bb

mecha_lab.register()
fresh()
C = bpy.context


def evaluated_counts(ob):
    dg = C.evaluated_depsgraph_get()
    me = ob.evaluated_get(dg).to_mesh()
    out = (len(me.vertices), len(me.polygons))
    ob.evaluated_get(dg).to_mesh_clear()
    return out


ob = cube('Box', 2.0)
a = ob.modifiers.new('Array', 'ARRAY')
a.count = 3
b = ob.modifiers.new('Bevel', 'BEVEL')
b.width = 0.1
s = ob.modifiers.new('Subsurf', 'SUBSURF')
s.levels = 1
off = ob.modifiers.new('Off Wire', 'WIREFRAME')
off.show_viewport = False
expect = evaluated_counts(ob)
done, err = bb.apply_all_modifiers(C, ob)
check('all enabled modifiers applied, top to bottom', done == ['Array', 'Bevel', 'Subsurf'] and err == '', (done, err))
check('the mesh is what the stack showed (order kept)', (len(ob.data.vertices), len(ob.data.polygons)) == expect,
      ((len(ob.data.vertices), len(ob.data.polygons)), expect))
check('a switched-off modifier stays (not applied)', [m.name for m in ob.modifiers] == ['Off Wire'])
check('result is a closed mesh', non_manifold(ob) == 0)

# order matters: Bevel then Array differs from Array then Bevel - the stack order is used
o1 = cube('O1', 2.0)
m = o1.modifiers.new('Bevel', 'BEVEL'); m.width = 0.2; m.segments = 3
m = o1.modifiers.new('Array', 'ARRAY'); m.count = 2; m.relative_offset_displace = (0.6, 0, 0)
want = evaluated_counts(o1)
bb.apply_all_modifiers(C, o1)
check('stack order respected (overlapping array after bevel)', (len(o1.data.vertices), len(o1.data.polygons)) == want)

empty = cube('Plain', 2.0)
done, err = bb.apply_all_modifiers(C, empty)
check('no modifiers: nothing to do, no error', done == [] and err == '')
for o in C.selected_objects:
    o.select_set(False)
o2 = cube('Sel', 2.0)
o2.modifiers.new('Sub', 'SUBSURF')
o2.select_set(True)
C.view_layer.objects.active = o2
r = bpy.ops.mch.apply_modifiers_pick('EXEC_DEFAULT')
check('without a click it applies the selected meshes', r == {'FINISHED'} and not o2.modifiers, r)
check('the button sits above the tool button in the viewport list', bb.TOP_TIDY[0] == 'APPLY_MODS')
summary()
