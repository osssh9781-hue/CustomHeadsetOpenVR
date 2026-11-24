"""0.24.315 (user, mech leg / arm photos: "관절 메뉴도 만들어 줘, 관절 제네레이터야"): the Joint Generator - five styles,
closed parts, the lower link bending round the pin live, a piston that follows the bend."""
import math

import numpy as np
from _harness import bpy, bmesh, check, fresh, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import joint_gen as jg, tool_state as ts, ui_tool_settings as uts

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
check('Joint Generator: a tool of its own (Block-out, enum 96), Real Parts joints kept',
      ts.TOOL_BY_ID['JOINT'][5] == 'mecha.joint_gen' and ts._ENUM_NUMBERS['JOINT'] == 96 and 'JOINT' in uts.DRAWERS
      and 'JOINT' in dict(ts.TOOL_GROUPS)['Block-out'])
check('the enum numbers stay unique', len(set(ts._ENUM_NUMBERS.values())) == len(ts._ENUM_NUMBERS))


def open_edges(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    n = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return n


def W(ob):
    C.view_layer.update()
    return np.array([(ob.matrix_world @ v.co)[:] for v in ob.data.vertices])


st = S.mch_joint
st.size, st.width, st.upper_len, st.lower_len, st.bend = 0.5, 0.36, 1.2, 1.2, 0.0
S.cursor.location = (0, 0, 0)
for style in ('FORK', 'PLATES', 'TUBE', 'BALL', 'UNIVERSAL'):
    for o in C.selected_objects:
        o.select_set(False)
    st.style = style
    bpy.ops.mch.joint_add()
    parts = jg.parts_of(S, jg.joint_of(C.active_object))
    meshes = [o for o in parts.values() if o.type == 'MESH']
    op = {o.get(jg.PART): open_edges(o) for o in meshes}
    U, L = W(parts['UPPER']), W(parts['LOWER'])
    check(f'{style}: upper / lower links ({len(meshes)} parts), closed ({op}), the upper up to 1.2, the lower down to -1.2',
          all(v == 0 for v in op.values()) and abs(U[:, 2].max() - 1.2) < 1e-3 and abs(L[:, 2].min() + 1.2) < 1e-3,
          (op, U[:, 2].max(), L[:, 2].min()))
    S.cursor.location.x += 2.0
# bend live
lower = parts['LOWER']
st.style = 'FORK'
for o in C.selected_objects:
    o.select_set(False)
bpy.ops.mch.joint_add()
parts = jg.parts_of(S, jg.joint_of(C.active_object))
lower, upper = parts['LOWER'], parts['UPPER']
nv = len(lower.data.vertices)
st.bend = 60.0
L = W(lower)
lowest = L[np.argmin(L[:, 2])]
pin = upper.matrix_world.translation
check(f'Bend 60: the lower link turned round the pin (its end now {lowest - np.array(pin)})',
      abs(math.degrees(math.atan2(abs(lowest[1] - pin.y), abs(lowest[2] - pin.z))) - 60) < 8 and len(lower.data.vertices) == nv)
st.holes = 4
st.style = 'PLATES'
check('Side Plates, Holes 4: still closed', open_edges(upper) == 0)
st.cap = 'DOME'
check('Dome Cap: closed', open_edges(lower) == 0)
st.cap = 'FLAT'
st.piston = True
parts = jg.parts_of(S, jg.joint_of(upper))
check('Piston: a barrel on the upper link, a rod on the lower one, each tracking the other',
      'PISTON_A' in parts and 'PISTON_B' in parts and parts['PISTON_A'].parent == upper and
      parts['PISTON_B'].parent == lower and parts['PISTON_A'].constraints.get('MCH Piston') is not None)
a, b = parts['PISTON_A'], parts['PISTON_B']


def gap():
    C.view_layer.update()
    return (a.matrix_world.translation - b.matrix_world.translation).length


g60 = gap()
ax = (a.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
toward = (b.matrix_world.translation - a.matrix_world.translation).normalized()
check(f'... the barrel points at the rod\'s eye ({ax.dot(toward):.4f})', ax.dot(toward) > 0.999)
st.bend = 0.0
g0 = gap()
check(f'... bend 0 -> its ends further apart ({g60:.3f} -> {g0:.3f}), the barrel and rod still overlap',
      g0 > g60 and (len_a := max(v.co.z for v in a.data.vertices) - min(v.co.z for v in a.data.vertices)) +
      (max(v.co.z for v in b.data.vertices) - min(v.co.z for v in b.data.vertices)) > g0)
st.piston = False
check('Piston off: gone', 'PISTON_A' not in jg.parts_of(S, jg.joint_of(upper)))
bpy.ops.mch.joint_plain()
check('Make Plain', not jg.joint_of(upper))

# 0.24.316 My Joints: your own joint saved and loaded (in a scratch folder, never the user's own)
import os
import tempfile
jg.DIR[0] = tempfile.mkdtemp()
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=1, location=(1, 2, 3))
a_ = C.active_object
a_.name = 'MyKnee_Upper'
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.3, location=(1, 2, 2))
b_ = C.active_object
b_.name = 'MyKnee_Ball'
b_.parent = a_
b_.matrix_parent_inverse = a_.matrix_world.inverted()
c_ = b_.constraints.new('DAMPED_TRACK')
c_.target = a_
C.view_layer.update()
path = jg.save_joint(C, 'My Knee', [a_, b_], a_.matrix_world.translation.copy())
check('Save: a .blend in My Joints', path is not None and os.path.isfile(path) and jg.my_joints() == ['My_Knee'],
      jg.my_joints())
check('... the scene\'s objects untouched (no marks left on them)', jg.PIVOT not in a_.keys() and jg.PIVOT not in b_.keys())
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
S.cursor.location = (10, 0, 0)
obs = jg.load_joint(C, 'My_Knee')
C.view_layer.update()
by = {o.name.split('.')[0]: o for o in obs}
up, ball = by.get('MyKnee_Upper'), by.get('MyKnee_Ball')
check('Load: both parts back, the parent and the constraint kept', len(obs) == 2 and up is not None and ball is not None
      and ball.parent == up and ball.constraints and ball.constraints[0].target == up)
check('... its pivot on the 3D cursor, the parts where they were to each other',
      (up.matrix_world.translation - Vector((10, 0, 0))).length < 1e-5 and
      (ball.matrix_world.translation - Vector((10, 0, -1))).length < 1e-5, (up.matrix_world.translation[:], ball.matrix_world.translation[:]))
obs2 = jg.load_joint(C, 'My_Knee', where=(0, 5, 0))
check('loaded twice: two copies', len(obs2) == 2 and len([o for o in bpy.data.objects if o.type == 'MESH']) == 4)
os.remove(path)
check('deleted: gone from the list', jg.my_joints() == [])
summary()
