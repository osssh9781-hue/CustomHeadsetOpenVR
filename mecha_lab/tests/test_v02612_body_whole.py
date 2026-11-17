"""0.24.186 the one-piece body (user: "그전에 보냈던 붙어 있는 모델로 만들어 줘, 이건 예시 모델이잖아"): the user's whole human
body as ONE mesh on bones - sizes, proportions, joints and poses by sliders; the skin bends at the joints (no parts)."""
import math
import sys

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import body_whole as bw  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.cursor.location = (0.0, 0.0, 0.0)
S.mch_bodykit_new.height = 1.8
r = bpy.ops.mch.bodywhole_add()
body, rig = bw.pair(C.active_object)


def verts():
    C.view_layer.update()
    dg = C.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg)
    return np.array([ev.matrix_world @ v.co for v in ev.data.vertices])


def tip(n):
    C.view_layer.update()
    return np.array(rig.matrix_world @ rig.pose.bones[n].tail)


V0 = verts()
check(f'Add One-Piece Human: ONE mesh ({len(body.data.polygons)} faces, light) on bones (19: the waist and the chest, the neck and the head, a shoulder before each upper arm), standing on the cursor, '
      f'1.8 tall ({V0[:, 2].min():.3f} .. {V0[:, 2].max():.3f})', r == {'FINISHED'} and body.type == 'MESH' and
      rig.type == 'ARMATURE' and len(rig.pose.bones) == 19 and {'Waist', 'Chest', 'Neck', 'Head', 'Shoulder.L', 'UpperArm.L'} <= set(rig.pose.bones.keys()) and len(body.data.polygons) < 45000 and
      abs(V0[:, 2].min()) < 1e-3 and abs(V0[:, 2].max() - 1.8) < 0.01)
W = np.zeros(len(body.data.vertices))
for v in body.data.vertices:
    W[v.index] = sum(g.weight for g in v.groups)
check('every point follows bones (its weights add up to 1)', abs(W - 1.0).max() < 0.02, (W.min(), W.max()))
kp = rig.mch_bodywhole
kp.legs = 1.3
V1 = verts()
check(f'Legs 1.3: taller ({V1[:, 2].max():.3f}), the feet on the floor', V1[:, 2].max() > 1.95 and abs(V1[:, 2].min()) < 2e-3)
kp.legs = 1.0
h0 = np.linalg.norm(tip('Hand.L') - np.array(rig.matrix_world @ rig.pose.bones['Hand.L'].head))
kp.arm_size = 1.3
h1 = np.linalg.norm(tip('Hand.L') - np.array(rig.matrix_world @ rig.pose.bones['Hand.L'].head))
check(f'Arms Size 1.3: the arm scaled, its hand too ({h0:.3f} -> {h1:.3f})', abs(h1 / h0 - 1.3) < 0.02)
kp.arm_size = 1.0
t0 = tip('Hand.L')
kp.joint = 'UpperArm.L'
kp.j_side = math.radians(70)
t1, t1r = tip('Hand.L'), tip('Hand.R')
check('the joint picked (Upper Arm, left), Side 70: the hand out and up; the right mirrored (Symmetry)',
      t1[0] > t0[0] + 0.2 and t1[2] > t0[2] + 0.2 and abs(t1r[0] + t1[0]) < 1e-3 and abs(t1r[2] - t1[2]) < 1e-3)
kp.j_side = 0.0
C.view_layer.objects.active = body
z0 = float(rig.matrix_world.translation.z)
r = bpy.ops.mch.bodywhole_pose(pose='CROUCH')
V2 = verts()
check(f'Pose Crouch: lower ({V2[:, 2].max():.3f}), the feet on the floor, the head forward',
      r == {'FINISHED'} and V2[:, 2].max() < 1.6 and abs(V2[:, 2].min()) < 2e-3 and
      tip('Head')[1] < np.array(rig.matrix_world.translation)[1] - 0.05,
      (V2[:, 2].min(), tip('Head'), np.array(rig.matrix_world.translation)))
# the skin bends: no edge pulled long (a part-split body would tear at the knee)
E = np.array([e.vertices[:] for e in body.data.edges])
L0 = np.linalg.norm(V0[E[:, 0]] - V0[E[:, 1]], axis=1)
L2 = np.linalg.norm(V2[E[:, 0]] - V2[E[:, 1]], axis=1)
ratio = L2 / np.maximum(L0, 1e-9)
check(f'the skin bends at the joints, nothing torn or pulled into strands (99 % of the edges stretched under '
      f'x{np.quantile(ratio, 0.99):.2f}, the longest - inside the bent knee - x{ratio.max():.1f})',
      np.quantile(ratio, 0.99) < 2.5 and ratio.max() < 12.0)
# 0.24.187 the neck / the shoulder / the waist on their own; hands and feet swapped
bpy.ops.mch.bodywhole_pose(pose='__RESET__')
h0, n0 = tip('Head'), tip('Neck')
kp.joint = 'Head'
kp.j_bend = math.radians(40)
check('Head Bend: the head nods, the neck stays', np.linalg.norm(tip('Head') - h0) > 0.03 and
      np.linalg.norm(tip('Neck') - n0) < 1e-4)
kp.j_bend = 0.0
e0, hd0 = tip('UpperArm.L'), tip('Hand.L')
kp.joint = 'Shoulder.L'
kp.j_side = math.radians(25)
check('Shoulder Side: the whole arm lifts from the collarbone', tip('UpperArm.L')[2] > e0[2] + 0.03 and
      tip('Hand.L')[2] > hd0[2] + 0.03)
kp.j_side = 0.0
c0, w0 = tip('Chest'), tip('Waist')
kp.joint = 'Chest'
kp.j_bend = math.radians(30)
check('Chest Bend: the chest leans, the waist under it stays', tip('Chest')[1] < c0[1] - 0.03 and
      np.linalg.norm(tip('Waist') - w0) < 1e-4)
kp.j_bend = 0.0
n_before = len(verts())
r = bpy.ops.mch.bodywhole_end(slot='Hand', variant='creature:Hand.L')
ends = [o for o in rig.children if o.get(bw.END_KEY)]
check('Swap Hands -> the creature\'s: a hand hung on each hand bone, the body\'s own hidden there',
      r == {'FINISHED'} and sorted(o[bw.END_KEY] for o in ends) == ['Hand.L', 'Hand.R'] and len(verts()) < n_before and
      all(o.parent_bone == o[bw.END_KEY] for o in ends))
r = bpy.ops.mch.bodywhole_end(slot='Hand', variant='own')
check('... Own: back as it was', r == {'FINISHED'} and not [o for o in rig.children if o.get(bw.END_KEY)] and
      len(verts()) == n_before)
r = bpy.ops.mch.bodywhole_pose(pose='__RESET__')
V3 = verts()
check('Reset Pose: as it stood', np.abs(V3 - V0).max() < 1e-3)

mecha_lab.unregister()
sys.exit(1 if summary() else 0)
