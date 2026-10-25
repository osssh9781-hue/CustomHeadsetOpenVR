"""0.24.33 Point Radial Symmetry: pick a centre - the selected meshes repeat round it (local X / Y / Z axis, Count);
new parts get it too; a Cut drawn on any copy cuts every copy; Apply / Remove."""
import math

from _harness import bpy, check, fresh, summary
import bmesh
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce, radial_sym as rs, tool_state as ts, ui_tool_settings as uts

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
check('tool in the list with settings', 'RSYM' in {t[0] for t in ts.VISIBLE_TOOLS} and 'RSYM' in uts.DRAWERS)
m = rs.step_matrix(Vector((1, 0, 0)), Vector((0, 0, 1)), 4)
check('one step: a quarter turn round the pivot', (m @ Vector((2, 0, 0)) - Vector((1, 1, 0))).length < 1e-6)
check('Count rotations, the first is no turn', len(rs.rotations(Vector(), Vector((0, 0, 1)), 6)) == 6
      and (rs.rotations(Vector(), Vector((0, 0, 1)), 6)[0] @ Vector((1, 2, 3)) - Vector((1, 2, 3))).length < 1e-9)

bpy.ops.mesh.primitive_cube_add(size=1.0, location=(2, 0, 0))
cube = C.active_object
cube.name = 'Part'
S.mch_rsym.count = 4
res = bpy.ops.mch.radial_sym('EXEC_DEFAULT', point=(0, 0, 0))


def world_points(ob):
    dg = C.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    pts = [ob.matrix_world @ v.co for v in me.vertices]
    ev.to_mesh_clear()
    return pts


pts = world_points(cube)
centres = {(round(sum(p.x for p in pts[i:i + 8]) / 8, 3), round(sum(p.y for p in pts[i:i + 8]) / 8, 3))
           for i in range(0, len(pts), 8)}
check('4 copies round the centre point', res == {'FINISHED'} and len(pts) == 32
      and centres == {(2.0, 0.0), (0.0, 2.0), (-2.0, 0.0), (0.0, -2.0)}, sorted(centres))
S.mch_rsym.count = 6
check('Count is live', len(world_points(cube)) == 48)
cube.rotation_euler = (math.radians(90), 0, 0)               # its local Z now lies along world -Y
bpy.ops.mch.radial_sym('EXEC_DEFAULT', point=(0, 0, 0))
zs = [p.z for p in world_points(cube)]
check("the active mesh's own axis: copies now go round its local Z (up and down too)", max(zs) > 1.5 and min(zs) < -1.5,
      (min(zs), max(zs)))
cube.rotation_euler = (0, 0, 0)
S.mch_rsym.axis = 'Y'                                         # pivot keeps the old turn: local Y = world Z now
bpy.ops.mch.radial_sym_end(apply=False)
check('Remove: no modifier, no helper, no pivot', cube.modifiers.get(rs.MOD_NAME) is None
      and not any(o.name.startswith('MCH_RS_') or o.name.startswith('MCH_RadialPivot') for o in bpy.data.objects)
      and not S.mch_rsym.active)

for o in C.selected_objects:
    o.select_set(False)
cube.select_set(True)
C.view_layer.objects.active = cube
S.mch_rsym.count = 4
S.mch_rsym.axis = 'Z'
bpy.ops.mch.radial_sym('EXEC_DEFAULT', point=(0, 0, 0))
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.3, location=(2, 0, 1))
new = C.active_object
note = rs.after_create(C, 'BASE')
check('a new part drawn while it is on repeats too', new.modifiers.get(rs.MOD_NAME) is not None and 'x4' in note
      and len(world_points(new)) == 4 * len(new.data.vertices))
check('only drawing tools that make parts', rs.after_create(C, 'CUT') == '')

TOP = cg.OrthoProjector(Quaternion())                          # looking down -Z, 100 px per unit
nv = len(cube.data.vertices)
loops = [[(480, 680), (520, 680), (520, 720), (480, 720)]]    # a square over the copy at (0, 2)
msg = ce.perform_closed(C, 'CUT', [cube], loops, TOP)
bm = bmesh.new()
bm.from_mesh(cube.data)
vol = bm.calc_volume()
bm.free()
check('Cut drawn on a copy: the part itself is cut (so every copy is)', len(cube.data.vertices) > nv and vol < 0.99,
      (msg, len(cube.data.vertices), vol))
n_src = len(cube.data.vertices)
bpy.ops.mch.radial_sym_end(apply=True)
check('Apply: the copies are real', cube.modifiers.get(rs.MOD_NAME) is None and len(cube.data.vertices) == 4 * n_src
      and not S.mch_rsym.active)
summary()
