"""0.24.336 Rig > Mecha Names (user: "팔다리 몸통 골반 머리 이렇게 나눠 놓으니까 ... 이름 변경하면 그걸로 각 조인트 연결하는
리깅 ... IK 로", "이렇게 나눠 놓으면 그냥 본에 붙이기만 하면 되잖아"): bones by the parts' names, joints where they meet (or,
laid out apart, at each part's end toward its parent), IK on the arms and legs."""
import bmesh
import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import mecha_named as mn, rigging as rg

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene


def box(name, lo, hi, shift=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    lo, hi = np.array(lo, float), np.array(hi, float)
    for v in bm.verts:
        v.co = [lo[i] + (v.co[i] + 0.5) * (hi[i] - lo[i]) + shift[i] for i in range(3)]
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    S.collection.objects.link(ob)
    return ob


BODY = [('Pelvis', (-0.2, -0.12, 0.9), (0.2, 0.12, 1.1)),
        ('몸통', (-0.25, -0.15, 1.1), (0.25, 0.15, 1.6)),
        ('Neck', (-0.05, -0.05, 1.6), (0.05, 0.05, 1.7)),
        ('Head', (-0.12, -0.12, 1.7), (0.12, 0.12, 1.95)),
        ('Shoulder.L', (0.25, -0.08, 1.45), (0.38, 0.08, 1.58)),
        ('Shoulder_R', (-0.38, -0.08, 1.45), (-0.25, 0.08, 1.58)),
        ('UpperArm.L', (0.3, -0.05, 1.2), (0.4, 0.05, 1.45)),
        ('upper arm R', (-0.4, -0.05, 1.2), (-0.3, 0.05, 1.45)),
        ('LeftForearm', (0.3, -0.05, 0.95), (0.4, 0.05, 1.2)),
        ('Forearm.R', (-0.4, -0.05, 0.95), (-0.3, 0.05, 1.2)),
        ('Hand.L', (0.31, -0.04, 0.85), (0.39, 0.04, 0.95)),
        ('손 오른', (-0.39, -0.04, 0.85), (-0.31, 0.04, 0.95)),
        ('Thigh.L', (0.05, -0.07, 0.55), (0.18, 0.07, 0.9)),
        ('Leg_R', (-0.18, -0.07, 0.55), (-0.05, 0.07, 0.9)),
        ('Shin.L', (0.06, -0.06, 0.1), (0.17, 0.06, 0.55)),
        ('Calf.R', (-0.17, -0.06, 0.1), (-0.06, 0.06, 0.55)),
        ('Foot.L', (0.06, -0.2, 0.0), (0.17, 0.06, 0.1)),
        ('발.R', (-0.17, -0.2, 0.0), (-0.06, 0.06, 0.1)),
        ('Armor_plate', (-0.2, -0.2, 1.2), (0.2, -0.15, 1.5))]
obs = [box(n, lo, hi) for n, lo, hi in BODY]
mw0 = {o.name: o.matrix_world.copy() for o in obs}
for o in obs:
    o.select_set(True)
C.view_layer.objects.active = obs[0]
S.mch_rig.kind = 'NAMED'
r = bpy.ops.mch.rig_make()
arm = rg.rig_of(obs[0])
bones = set(arm.data.bones.keys()) if arm else set()
want = {'root', 'pelvis', 'torso', 'neck', 'head'} | {f'{b}.{s}' for b in ('shoulder', 'upper_arm', 'forearm', 'hand',
                                                                            'thigh', 'shin', 'foot') for s in 'LR'}
check(f'Make Rig (Mecha Names): every named bone, both sides ({r}; missing {sorted(want - bones)})',
      r == {'FINISHED'} and want <= bones)
B = arm.data.bones
check('the chain by the names: torso on pelvis, head on neck, hand on forearm on upper arm on shoulder, foot on shin '
      'on thigh on pelvis',
      B['torso'].parent.name == 'pelvis' and B['head'].parent.name == 'neck' and B['neck'].parent.name == 'torso'
      and B['hand.L'].parent.name == 'forearm.L' and B['forearm.L'].parent.name == 'upper_arm.L'
      and B['upper_arm.R'].parent.name == 'shoulder.R' and B['shoulder.R'].parent.name == 'torso'
      and B['foot.R'].parent.name == 'shin.R' and B['thigh.L'].parent.name == 'pelvis')
bon = {o.name: o.parent_bone for o in obs}
check(f'each part on its bone (Korean / mixed names, sides from the name); "Armor_plate" (not a body word) on the '
      f'nearest bone ({bon["몸통"]}, {bon["손 오른"]}, {bon["Leg_R"]}, {bon["발.R"]}, {bon["Armor_plate"]})',
      bon['몸통'] == 'torso' and bon['손 오른'] == 'hand.R' and bon['Leg_R'] == 'thigh.R' and bon['발.R'] == 'foot.R'
      and bon['LeftForearm'] == 'forearm.L' and bon['Armor_plate'] == 'torso')
hk = (arm.matrix_world @ B['shin.L'].head_local)
hl = (arm.matrix_world @ B['forearm.R'].head_local)
check(f'joints where the parts meet: knee at z 0.55 ({hk.z:.3f}), elbow at z 1.2 ({hl.z:.3f})',
      abs(hk.z - 0.55) < 0.03 and abs(hl.z - 1.2) < 0.03)
C.view_layer.update()
moved = max((o.matrix_world.translation - mw0[o.name].translation).length for o in obs)
check(f'the parts stay where they were (rest pose: {moved:.5f} moved - under 1 mm on a 2 m body)', moved < 1e-3)
ik = {pb.name for pb in arm.pose.bones for c in pb.constraints if c.type == 'IK'}
check(f'IK on both arms and legs (forearm / shin), with targets and poles ({sorted(ik)})',
      ik == {'forearm.L', 'forearm.R', 'shin.L', 'shin.R'} and 'foot.L_ik' in B and 'hand.R_ik' in B
      and 'shin.L_pole' in B and 'forearm.L_pole' in B)
# pose: the left foot target up and forward - the knee bends, the foot part follows
pb = arm.pose.bones['foot.L_ik']
f0 = S.objects['Foot.L'].matrix_world.translation.copy()
s0 = S.objects['Shin.L'].matrix_world.copy()
pb.location = (0, 0.25, 0)                      # (bone space: along the bone)
C.view_layer.update()
f1 = S.objects['Foot.L'].matrix_world.translation.copy()
pb.location = (0, 0, 0)
arm.pose.bones['foot.L_ik'].location = (0, 0, 0)
pb.matrix = pb.matrix  # noqa
wl = arm.matrix_world @ pb.matrix
pb.location = (0, 0, 0)
C.view_layer.update()
tgt = arm.matrix_world @ arm.pose.bones['foot.L_ik'].head
arm.pose.bones['foot.L_ik'].matrix = arm.pose.bones['foot.L_ik'].matrix.copy()
import mathutils  # noqa: E402
M = arm.pose.bones['foot.L_ik'].matrix.copy()
M.translation += mathutils.Vector((0, -0.1, 0.25))
arm.pose.bones['foot.L_ik'].matrix = M
C.view_layer.update()
f2 = S.objects['Foot.L'].matrix_world.translation.copy()
s2 = S.objects['Shin.L'].matrix_world
check(f'IK works: the foot target moved up 0.25 - the foot part goes with it ({(f2 - f0).z:.3f} up), the shin turns',
      (f2 - f0).z > 0.15 and s2.to_quaternion().rotation_difference(s0.to_quaternion()).angle > 0.05
)
arm.pose.bones['foot.L_ik'].matrix = M.copy()
for pb_ in arm.pose.bones:
    pb_.location = (0, 0, 0)
    pb_.rotation_quaternion = (1, 0, 0, 0)
C.view_layer.update()
check('Auto Animation knows the legs (feet)', set(__import__('json').loads(arm['mch_legs'])) == {'foot.L', 'foot.R'})

# laid out apart (as the user's picture): each bone at its part's end toward its parent
for o in list(S.objects):
    bpy.data.objects.remove(o)
for a_ in list(bpy.data.armatures):
    bpy.data.armatures.remove(a_)
spread = {'Head': (0, 0, 0.6), 'UpperArm.L': (0.8, 0, 0.3), 'LeftForearm': (1.0, 0, 0), 'Hand.L': (1.2, 0, -0.3),
          'Thigh.L': (0.3, 0, -0.4), 'Shin.L': (0.5, 0, -0.9), 'Foot.L': (0.5, 0, -1.3)}
obs = [box(n, lo, hi, spread.get(n, (0, 0, 0))) for n, lo, hi in BODY if n in
       ('Pelvis', '몸통', 'Neck', 'Head', 'UpperArm.L', 'LeftForearm', 'Hand.L', 'Thigh.L', 'Shin.L', 'Foot.L')]
arm2, rep = mn.build(C, obs)
B2 = arm2.data.bones
hh = arm2.matrix_world @ B2['hand.L'].head_local
hand = S.objects['Hand.L']
top_hand = max((hand.matrix_world @ v.co).z for v in hand.data.vertices)
check(f'laid out apart: still every bone by name, each on its part - the hand\'s joint on the hand\'s end toward the '
      f'forearm ({hh.z:.2f} vs the hand top {top_hand:.2f}); IK on the arm and the leg ({rep["ik"]})',
      {'hand.L', 'forearm.L', 'upper_arm.L', 'foot.L', 'shin.L', 'thigh.L', 'head'} <= set(B2.keys())
      and abs(hh.z - top_hand) < 0.06 and set(rep['ik']) == {'hand.L', 'foot.L'})
summary()
