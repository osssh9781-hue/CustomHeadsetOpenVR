"""0.24.77 Path Move (Whole) / Silhouette Move Extend on a part where the section cut's edges stayed with the far side
after the split: 'nothing stays behind' came out, so Extend gave up and made a Separate Tube (seen on a Quad Remeshed
part - it happened on any mesh, by its face order: a plain subdivided cylinder too).  The faces round the cut are
taken before the split now."""
from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import path_sweep as ps

mecha_lab.register()
fresh()
C = bpy.context


def cylinder(cuts):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.5, depth=3.0)
    ob = C.active_object
    if cuts:
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.subdivide(number_cuts=cuts)
        bpy.ops.object.mode_set(mode='OBJECT')
    return ob


HIT, UP = Vector((0.5, 0, 1.0)), Vector((0, 0, 1))
for cuts in (0, 3):
    ob = cylinder(cuts)
    info = ps.analyse(ob.data, HIT, UP)
    check(f'A cylinder ({len(ob.data.polygons)} faces): grabbed on the side, the end above is cut off (it was "not cut '
          f'off" -> Separate Tube)', info is not None and info['tip'] is not None and info['area'] == 'SECTION',
          None if info is None else info['tip'] is None)
    n0 = len(ob.data.vertices)
    top0 = max(v.co.z for v in ob.data.vertices)
    msg = ps.extend(ob.data, HIT, UP, [Vector((0, 0, 0)), Vector((0.3, 0, 0.5)), Vector((0.8, 0, 1.0))])
    top1 = max(v.co.z for v in ob.data.vertices)
    check('... Extend works on the mesh itself: new rings, the end carried up the path, still closed',
          len(ob.data.vertices) > n0 and top1 > top0 + 0.5 and non_manifold(ob) == 0, (msg, top0, top1))

ob = cylinder(3)
r = bpy.ops.mch.mesh_tool(action='QUAD_REMESH')
q = C.active_object
ok = 0
for z in (0.5, 1.0, 1.3):
    info = ps.analyse(q.data, Vector((0.5, 0, z)), UP)
    ok += info is not None and info['tip'] is not None
check('A Quad Remeshed part: the end is cut off wherever it is grabbed', r == {'FINISHED'} and ok == 3, (r, ok))
msg = ps.extend(q.data, Vector((0.5, 0, 1.0)), UP, [Vector((0, 0, 0)), Vector((0, 0.4, 0.6))])
check('... and Extend works on it (closed)', non_manifold(q) == 0, msg)

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_grid_add(x_subdivisions=8, y_subdivisions=8, size=2.0)
g = C.active_object
g.rotation_euler = (1.5708, 0, 0)
bpy.ops.object.transform_apply(rotation=True)
info = ps.analyse(g.data, Vector((0, 0, 0.2)), UP)
check('An open sheet: still "not cut off" (nothing to carry - Separate Tube as before)', info is None
      or info['tip'] is None)
summary()
