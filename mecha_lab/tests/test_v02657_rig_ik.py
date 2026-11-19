"""0.24.257 (user: "아래 입에만 IK 가 생기는데 내가 IK 생길 부분을 지정할 수 있니?"): IK where the user wants it - select the
end bone(s), Add IK (IK Bones: how many bend): a target past its tip and a pole, the rest pose still, the tip follows
the target; select any bone of an IK (or its target / pole), Remove IK: the constraints and control bones gone, the
chain back at rest, a leg it was no longer walked."""
import json

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector

import mecha_lab
import kaiju_mesh as km
from mecha_lab import rigging as rg  # noqa: E402

mecha_lab.register(); fresh()
C = bpy.context
S = C.scene
ob = km.make(C)
S.mch_rig.kind = 'AUTO'
bpy.ops.mch.rig_make()
arm = C.active_object
legs = json.loads(arm['mch_legs'])
chains = json.loads(arm['mch_chains'])
dg = C.evaluated_depsgraph_get()
P0 = np.array([v.co for v in ob.evaluated_get(dg).to_mesh().vertices]); ob.evaluated_get(dg).to_mesh_clear()


def select(names, mode='POSE'):
    for o in list(C.selected_objects):
        o.select_set(False)
    arm.select_set(True); C.view_layer.objects.active = arm
    if C.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for pb in arm.pose.bones:
        pb.select = pb.name in names
    arm.data.bones.active = arm.data.bones[names[0]]
    bpy.ops.object.mode_set(mode=mode)
    if mode == 'EDIT':
        for e in arm.data.edit_bones:
            e.select = e.select_head = e.select_tail = e.name in names
        arm.data.edit_bones.active = arm.data.edit_bones[names[0]]


def iks():
    return {pb.name: c.subtarget for pb in arm.pose.bones for c in pb.constraints if c.type == 'IK'}


# 1. take a leg's IK off (like the jaw tips the user did not want) - picked by its upper bone, in Edit Bones
leg = legs[0]
upper = sorted(n for n in arm.data.bones.keys() if n.startswith(leg + '.') and n[len(leg) + 1:].isdigit())[0]
n_ik = len(iks())
select([upper], 'EDIT')
r = bpy.ops.mch.rig_ik(mode='REMOVE')
C.view_layer.update()
dg = C.evaluated_depsgraph_get()
P1 = np.array([v.co for v in ob.evaluated_get(dg).to_mesh().vertices]); ob.evaluated_get(dg).to_mesh_clear()
check(f'Remove IK (a leg picked by its upper bone, in Edit Bones): its IK gone ({n_ik} -> {len(iks())}), its target / pole '
      f'bones gone, no longer a walking leg, the mesh as it was ({float(np.abs(P1 - P0).max()) * 1000:.2f} mm)',
      r == {'FINISHED'} and len(iks()) == n_ik - 1 and leg + '.foot_ik' not in arm.data.bones
      and leg not in json.loads(arm['mch_legs']) and float(np.abs(P1 - P0).max()) < 1e-3
      and not any(c.subtarget == leg + '.foot_ik' for pb in arm.pose.bones for c in pb.constraints if hasattr(c, 'subtarget')))
# 2. IK on a chain's end (an arm / claw the user wants)
ch = chains[0]
end = sorted(n for n in arm.data.bones.keys() if n.startswith(ch + '.') and n[len(ch) + 1:].isdigit())[-1]
S.mch_rig.ik_chain = 3
select([end])
r = bpy.ops.mch.rig_ik(mode='ADD')
C.view_layer.update()
c = next((c for c in arm.pose.bones[end].constraints if c.type == 'IK'), None)
still = max((pb.matrix.to_translation() - pb.bone.matrix_local.to_translation()).length for pb in arm.pose.bones)
check(f'Add IK on a chain end ({end}, IK Bones 3): a target and a pole, the chain 3 long, the rest pose still ({still * 1000:.2f} mm), '
      f'in Pose mode after', r == {'FINISHED'} and c is not None and c.chain_count == 3 and c.subtarget == end + '_ik'
      and end + '_pole' in arm.data.bones and still < 0.002 and arm.mode == 'POSE')
bpy.ops.object.mode_set(mode='OBJECT')
t = arm.pose.bones[end + '_ik']
tip0 = (arm.matrix_world @ arm.pose.bones[end].tail).copy()
goal = arm.matrix_world @ (t.bone.head_local + Vector((0.0, -0.15, 0.1)) * arm.data.bones[end].length * 3)
t.location = t.bone.matrix_local.inverted().to_3x3() @ (Vector((0.0, -0.15, 0.1)) * arm.data.bones[end].length * 3)
C.view_layer.update()
tip1 = arm.matrix_world @ arm.pose.bones[end].tail
check(f'moving its target moves the tip after it ({(tip1 - tip0).length * 100:.1f} cm moved, {(tip1 - goal).length * 100:.1f} cm off the target)',
      (tip1 - tip0).length > 0.05 and (tip1 - goal).length < 0.25 * (tip1 - tip0).length + 0.01)
t.location = (0, 0, 0)
select([end])
r = bpy.ops.mch.rig_ik(mode='ADD')
check('Add IK again on it: nothing doubled', sum(1 for c in arm.pose.bones[end].constraints if c.type == 'IK') == 1)
select([end + '_pole'])
bpy.ops.mch.rig_ik(mode='REMOVE')
check('Remove IK by picking its pole: gone again, the bones back at rest',
      end + '_ik' not in arm.data.bones and not any(c.type == 'IK' for c in arm.pose.bones[end].constraints))
summary()
