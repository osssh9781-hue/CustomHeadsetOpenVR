"""0.24.38 Radial Symmetry keeps the pivot and axis picked first: turning or moving a mesh turns only that mesh (its
copies are re-placed round the same pivot / axis); moving the pivot moves all; until Apply."""
import math

from _harness import bpy, check, fresh, summary
from mathutils import Matrix, Vector

import mecha_lab
from mecha_lab import radial_sym as rs

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
check('the auto re-place runs after every change', rs._on_depsgraph in bpy.app.handlers.depsgraph_update_post)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(2, 0, 0))
cube = C.active_object
S.mch_rsym.count, S.mch_rsym.axis = 4, 'Z'
bpy.ops.mch.radial_sym('EXEC_DEFAULT', point=(0, 0, 0))
pivot0 = S.mch_rsym.pivot.matrix_world.copy()


def copies(ob):
    C.view_layer.update()
    dg = C.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    pts = [ob.matrix_world @ v.co for v in me.vertices]
    ev.to_mesh_clear()
    n = len(ob.data.vertices)
    return [pts[i:i + n] for i in range(0, len(pts), n)]


def centre(ps):
    return sum(ps, Vector()) / len(ps)


turn = rs.step_matrix(Vector((0, 0, 0)), Vector((0, 0, 1)), 4)          # a quarter turn round the world Z at 0
cube.rotation_euler = (math.radians(30), math.radians(20), 0)          # turn the mesh itself (any axis)
cube.location = (2.5, 0.5, 0.3)                                         # and move it
cs = copies(cube)
c0, c1 = centre(cs[0]), centre(cs[1])
check('turned + moved: copy 2 is still the first one turned a quarter round the SAME pivot (0, 0, 0) and Z',
      (turn @ c0 - c1).length < 1e-4, (c0, c1))
check('... point for point (the copies turn with the mesh, round the fixed axis)',
      max((turn @ a - b).length for a, b in zip(cs[0], cs[1])) < 1e-4)
check('the pivot did not move or turn', all(abs(a - b) < 1e-6 for a, b in zip(
    [x for r in pivot0 for x in r], [x for r in S.mch_rsym.pivot.matrix_world for x in r])))
check('copy 0 is the mesh where it is (only it turned)', abs((c0 - cube.matrix_world @ centre([v.co for v in cube.data.vertices])).length) < 1e-4)
S.mch_rsym.pivot.location = (1, 0, 0)                                   # move the pivot: all copies follow it
cs = copies(cube)
turn2 = rs.step_matrix(Vector((1, 0, 0)), Vector((0, 0, 1)), 4)
check('moving the pivot re-places the copies round the new point', (turn2 @ centre(cs[0]) - centre(cs[1])).length < 1e-4)
# Distance: slide the meshes (and every copy) away from / toward the axis
S.mch_rsym.pivot.location = (0, 0, 0)
C.view_layer.update()
r_before = rs.radial(S.mch_rsym, cube)[0].length
S.mch_rsym.distance = 0.5
r_after = rs.radial(S.mch_rsym, cube)[0].length
cs = copies(cube)
check('Distance +0.5: the mesh is 0.5 further from the axis, the copies with it',
      abs(r_after - (r_before + 0.5)) < 1e-4 and (turn @ centre(cs[0]) - centre(cs[1])).length < 1e-4, (r_before, r_after))
z0 = cube.matrix_world.translation.z
S.mch_rsym.distance = -0.3
check('... -0.3: closer than at first, straight in (the height along the axis stays)',
      abs(rs.radial(S.mch_rsym, cube)[0].length - (r_before - 0.3)) < 1e-4
      and abs(cube.matrix_world.translation.z - z0) < 1e-6, (rs.radial(S.mch_rsym, cube)[0].length, r_before, cube.matrix_world.translation.z, z0, cube.get(rs.R0_KEY)))
bpy.ops.mch.radial_sym_end(apply=True)
check('Apply: the copies become real, the handler leaves the mesh alone', cube.modifiers.get(rs.MOD_NAME) is None
      and len(cube.data.vertices) == 32 and not S.mch_rsym.active and rs.R0_KEY not in cube)
summary()
