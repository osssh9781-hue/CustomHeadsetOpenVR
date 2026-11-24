"""0.24.312 (user: "이 실린더도 내가 근육 만든 거처럼 양 끝 찍으면 저 경첩 바닥면이 붙어서 나오면 편하겠네"): two clicks - a cylinder
between two surface points, each bracket's base plate (or arm) flat on its surface, its pins square to it all."""
import math

import numpy as np
from _harness import bpy, bmesh, check, fresh, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import actuator_gen as ag

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene


def W(ob):
    C.view_layer.update()
    return np.array([(ob.matrix_world @ v.co)[:] for v in ob.data.vertices])


def open_edges(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    n = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return n


bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, -1))
floor = C.active_object
bpy.ops.mesh.primitive_cube_add(size=2, location=(0.3, 0, 5))
ceil = C.active_object
st = S.mch_actuator
st.rear_type, st.front_type, st.rear_bracket, st.front_bracket = 'CLEVIS', 'EYE', True, True
st.rear_bstyle, st.front_bstyle = 'PLATE', 'PLATE'
aid, out = ag.place_between(C, ((0, 0, 0), (0, 0, 1), floor), ((0.3, 0, 4), (0, 0, -1), ceil))
p = ag.numbers(st)
br, bf, body = out['BRACKET_REAR'], out['BRACKET_FRONT'], out['BODY']
Wr, Wf = W(br), W(bf)
check('two points: a cylinder and its two brackets', aid and body is not None and br is not None and bf is not None)
check(f'the rear bracket\'s base plate flat on the floor (its underside at z 0: {Wr[:, 2].min():.4f})',
      abs(Wr[:, 2].min()) < 1e-4 and np.ptp(Wr[np.abs(Wr[:, 2]) < 1e-4][:, 2]) < 1e-6 and
      (Wr[:, 2] < 1e-4).sum() >= 4)
check(f'the front one\'s under the ceiling (its top at z 4: {Wf[:, 2].max():.4f})', abs(Wf[:, 2].max() - 4) < 1e-4)
pa = body.matrix_world.translation
check('the pins off the surfaces by the brackets\' height', abs(pa.z - ag.reach(p, 'rear')) < 1e-4)
C.view_layer.update()
rod = out['ROD']
pb = rod.matrix_world.translation
check(f'the rod end\'s pin under the ceiling bracket\'s (length {st.length:.3f})',
      (pb - Vector((0.3, 0, 4 - ag.reach(p, 'front')))).length < 1e-4)
check('the brackets are children of the meshes clicked (they go with the mech)', br.parent == floor and bf.parent == ceil)
x_body = body.matrix_world.to_3x3().col[0]
check('the hinge pin square to the cylinder', abs(x_body.dot((pb - pa).normalized())) < 1e-6)
# moving the mech moves its bracket; a slider change leaves it
floor.location.x += 1.0
C.view_layer.update()
check('moving the floor moves its bracket', abs(br.matrix_world.translation.x - 1.0) < 1e-5)
floor.location.x -= 1.0
for o in out.values():
    if o.type == 'MESH':
        o.select_set(True)
st.width = 0.5
C.view_layer.update()
check('a slider change: the bracket stays on its surface', abs(W(br)[:, 2].min()) < 1e-4)

st.rear_bstyle = 'ARM'                                 # (a higher bracket: the pins move, the plates stay)
C.view_layer.update()
check(f'Base Plate -> Lever Arm after: still flat on the floor ({W(br)[:, 2].min():.4f}) and under the ceiling '
      f'({W(bf)[:, 2].max():.4f})', abs(W(br)[:, 2].min()) < 1e-4 and abs(W(bf)[:, 2].max() - 4) < 1e-4)
check('... the rear pin moved up by the arm\'s thickness', abs(body.matrix_world.translation.z - ag.reach(ag.numbers(st), 'rear')) < 1e-4)
floor.location.z -= 0.5
st.rear_bstyle = 'PLATE'
C.view_layer.update()
check('the floor moved down, a slider changed: glued to it again where it is now', abs(W(br)[:, 2].min() + 0.5) < 1e-4
      and abs(W(bf)[:, 2].max() - 4) < 1e-4)
floor.location.z += 0.5
# a slanted wall: the plate lies on it
bpy.ops.mesh.primitive_cube_add(size=2, location=(6, 0, 0))
f2 = C.active_object
n = Vector((-1, 0, 1)).normalized()
wall_pt = Vector((8, 0, 3))
for o in C.selected_objects:
    o.select_set(False)
st.front_bstyle = 'ARM'
aid2, out2 = ag.place_between(C, ((6, 0, 1), (0, 0, 1), f2), (tuple(wall_pt), tuple(n), None))
bf2 = out2['BRACKET_FRONT']
Wf2 = W(bf2)
dist = (Wf2 - np.array(wall_pt)) @ np.array(n)
check(f'a slanted wall: the arm bracket lies flat on it (nothing past it: {dist.min():.5f}, a face on it)',
      dist.min() > -1e-4 and (np.abs(dist) < 1e-4).sum() >= 4, dist.min())
check('... closed meshes', all(open_edges(o) == 0 for o in out2.values() if o.type == 'MESH'))

# a scaled, turned mesh (a sheared parent): the bracket keeps its own shape after a slider change
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 8, 3))
tilted = C.active_object
tilted.scale = (4, 1.2, 0.6)
tilted.rotation_euler = (0, math.radians(-18), 0)
C.view_layer.update()
nt = (tilted.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
pt = tilted.matrix_world @ Vector((0, 0, -0.5))
for o in C.selected_objects:
    o.select_set(False)
st.front_bstyle, st.rear_bstyle = 'PLATE', 'PLATE'
bpy.ops.mesh.primitive_cube_add(size=1, location=(-1.5, 8, -0.3))
slab = C.active_object
slab.scale = (4, 1.2, 0.6)                             # (non-uniform: a diagonal cylinder's bracket under it shears)
C.view_layer.update()
for o in C.selected_objects:
    o.select_set(False)
aid3, out3 = ag.place_between(C, ((-1.5, 8, 0), (0, 0, 1), slab), (tuple(pt), tuple(nt), tilted))
bf3 = out3['BRACKET_REAR']
ext0 = np.ptp(W(bf3), axis=0)
for o in out3.values():
    if o.type == 'MESH':
        o.select_set(True)
st.width = 0.45
ext1 = np.ptp(W(bf3), axis=0)
d3 = W(bf3)[:, 2] - 0.0
check(f'under a scaled, turned mesh: the bracket keeps its shape after a slider change ({ext0.round(3)} -> {ext1.round(3)}) '
      f'and lies on it ({d3.min():.5f})', np.allclose(ext0, ext1, atol=1e-3) and d3.min() > -1e-4 and (np.abs(d3) < 1e-4).sum() >= 4)
summary()
