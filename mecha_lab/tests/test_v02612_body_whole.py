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
check(f'Add One-Piece Human: ONE mesh ({len(body.data.polygons)} faces, light) on bones (51 - 19 of the body, 3 for each of the 10 fingers, the front of each foot: the waist and the chest, the neck and the head, a shoulder before each upper arm), standing on the cursor, '
      f'1.8 tall ({V0[:, 2].min():.3f} .. {V0[:, 2].max():.3f})', r == {'FINISHED'} and body.type == 'MESH' and
      rig.type == 'ARMATURE' and len(rig.pose.bones) == 51 and {'Waist', 'Chest', 'Neck', 'Head', 'Shoulder.L', 'UpperArm.L'} <= set(rig.pose.bones.keys()) and len(body.data.polygons) < 60000 and
      abs(V0[:, 2].min()) < 1e-3 and abs(V0[:, 2].max() - 1.8) < 0.01)
W = np.zeros(len(body.data.vertices))
for v in body.data.vertices:
    W[v.index] = sum(g.weight for g in v.groups if not body.vertex_groups[g.group].name.startswith('MCH End'))
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
h0, n0, c0_ = tip('Head'), tip('Neck'), tip('Chest')
kp.joint = 'Head'
kp.j_bend = math.radians(40)
dh, dn = np.linalg.norm(tip('Head') - h0), np.linalg.norm(tip('Neck') - n0)
check(f'Head Bend: the head nods ({dh:.3f}), its neck goes part of the way with it ({dn:.3f} - no sharp fold at the '
      'nape), the chest stays', dh > 0.03 and 1e-3 < dn < dh and np.linalg.norm(tip('Chest') - c0_) < 1e-4)
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

# 0.24.187 fingers and toes on bones (user: "손이나 발 쪽도 세부적으로 조절 가능하게 리깅을")
f0 = tip('Finger3c.L')
kp.fingers_curl = math.radians(60)
f1, f1r = tip('Finger3c.L'), tip('Finger3c.R')
check(f'Fingers Curl 60: every finger curls in (a fingertip moved {np.linalg.norm(f1 - f0):.3f}), both sides the same',
      np.linalg.norm(f1 - f0) > 0.04 and abs(f1[0] + f1r[0]) < 2e-3 and abs(f1[2] - f1r[2]) < 2e-3)
kp.fingers_curl = 0.0
a0 = np.linalg.norm(tip('Finger1c.L') - tip('Finger5c.L'))
kp.fingers_spread = math.radians(25)
a1 = np.linalg.norm(tip('Finger1c.L') - tip('Finger5c.L'))
check(f'Fingers Spread 25: the outer fingertips further apart ({a0:.3f} -> {a1:.3f})', a1 > a0 + 0.02)
kp.fingers_spread = 0.0
l0 = np.linalg.norm(tip('Finger2c.L') - np.array(rig.matrix_world @ rig.pose.bones['Finger2a.L'].head))
kp.fingers_length = 1.5
l1 = np.linalg.norm(tip('Finger2c.L') - np.array(rig.matrix_world @ rig.pose.bones['Finger2a.L'].head))
check(f'Fingers Length 1.5: longer ({l0:.3f} -> {l1:.3f})', abs(l1 / l0 - 1.5) < 0.05)
kp.fingers_length = 1.0
g0, o0 = tip('Finger2c.L'), tip('Finger3c.L')
kp.joint = 'Finger2a.L'
kp.j_bend = math.radians(50)
check('one finger picked in Joint (Finger 2 - root), Bend: only it moves',
      np.linalg.norm(tip('Finger2c.L') - g0) > 0.02 and np.linalg.norm(tip('Finger3c.L') - o0) < 1e-4)
kp.j_bend = 0.0
t0 = tip('Toes.L')
kp.ground = False
kp.toes_curl = math.radians(-40)
check('Toes -40: the feet\'s fronts bent up', tip('Toes.L')[2] > t0[2] + 0.01)
kp.toes_curl = 0.0
kp.ground = True
V_f = verts()
check('... all back: as it stood', np.abs(V_f - V0).max() < 1e-3)

# 0.24.187 the creatures on bones too (user: "기존에 보낸 크리쳐도 리깅해 주고 ... 크리쳐 바디 하나 더")
for kind in ('creature', 'creature2'):
    r = bpy.ops.mch.bodywhole_add(kind=kind)
    b2, r2 = bw.pair(C.active_object)
    C.view_layer.update()
    ev = b2.evaluated_get(C.evaluated_depsgraph_get())
    Z = np.array([(ev.matrix_world @ v.co)[2] for v in ev.data.vertices])
    used = {b2.vertex_groups[g.group].name for v in b2.data.vertices for g in v.groups if g.weight > 0.5} - {f'MCH End {e}.{d}' for e in ('Hand', 'Foot') for d in 'LR'}
    C.view_layer.objects.active = b2
    r_p = bpy.ops.mch.bodywhole_pose(pose='CROUCH')
    C.view_layer.update()
    ev = b2.evaluated_get(C.evaluated_depsgraph_get())
    Z2 = np.array([(ev.matrix_world @ v.co)[2] for v in ev.data.vertices])
    check(f'One-piece {kind}: one mesh on bones (19 of the body, the fingers, the front of each foot), every bone has skin, 1.8 tall on the floor; Crouch: '
          f'lower ({Z2.max():.2f}), on the floor', r == {'FINISHED'} and len(r2.pose.bones) >= 39 and
          len(used) == len(r2.pose.bones) and abs(Z.min()) < 2e-3 and abs(Z.max() - 1.8) < 0.01 and r_p == {'FINISHED'} and
          Z2.max() < 1.65 and abs(Z2.min()) < 2e-3, (len(used), Z.min(), Z.max(), Z2.max()))

mecha_lab.unregister()
sys.exit(1 if summary() else 0)
