"""0.24.249 (user: "리그 지우기도 만들어줘"): Delete Rig removes the rig and puts back what it touched - the body back
in its own shape (no Armature modifier, no bone weight groups, the user's own groups kept), mecha parts let go where
they were made even after posing, its Auto Animation actions gone; another rig and its control shapes untouched."""
import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
import mech_walker as mw
from mecha_lab import rigging as rg  # noqa: E402

mecha_lab.register(); fresh()
C = bpy.context
S = C.scene
st = S.mch_rig


def only(o):
    for x in list(C.selected_objects):
        x.select_set(False)
    o.select_set(True); C.view_layer.objects.active = o


def pts(ob):
    dg = C.evaluated_depsgraph_get()
    e = ob.evaluated_get(dg)
    M = np.array(e.matrix_world)
    P = np.array([v.co for v in e.data.vertices])
    return P @ M[:3, :3].T + M[:3, 3]


# a body (Human)
S.mch_bodykit_new.height = 1.8
bpy.ops.mch.bodywhole_add()
from mecha_lab import body_whole as bw
kb, kr = bw.pair(C.active_object)
dg = C.evaluated_depsgraph_get()
body = bpy.data.objects.new('Sculpt', bpy.data.meshes.new_from_object(kb.evaluated_get(dg), depsgraph=dg))
S.collection.objects.link(body); body.matrix_world = kb.matrix_world.copy()
for vg in list(body.vertex_groups):
    body.vertex_groups.remove(vg)
body.vertex_groups.new(name='MyMask')
kb.hide_set(True); kr.hide_set(True)
rest = pts(body); mw0 = body.matrix_world.copy()
only(body)
st.kind, st.ik, st.bind = 'BODY', True, True
bpy.ops.mch.rig_make()
arm = C.active_object
for pb in arm.pose.bones:                                  # (posed: the rig bends the body)
    if pb.name.startswith('foot') or pb.name.endswith('_ik'):
        pb.location.z += 0.2
S.mch_loco.gait = 'WALK'
bpy.ops.mch.loco_make()
acts = [a.name for a in bpy.data.actions if a.name.startswith(arm.name + '_')]
# 0.24.249 (user: "걷는 포즈 이상해") the walking arms hang from the shoulder and swing (not folded behind the back)
reach, swing = [], []
for f_ in range(S.frame_start, S.frame_start + 24, 2):
    S.frame_set(f_)
    for sd in 'LR':
        sh = arm.pose.bones[f'upper_arm.{sd}'].head
        hd = arm.pose.bones[f'hand.{sd}'].head
        r0 = (arm.data.bones[f'hand.{sd}'].head_local - arm.data.bones[f'upper_arm.{sd}'].head_local).length
        reach.append((hd - sh).length / r0)
        swing.append((hd - sh).y)
S.frame_set(S.frame_start)
check(f'walk: the arms nearly straight (reach {min(reach):.0%}..{max(reach):.0%} of the rest), swinging '
      f'{(max(swing) - min(swing)) * 100:.0f} cm front to back', min(reach) > 0.9 and max(swing) - min(swing) > 0.15)
moved = float(np.abs(pts(body) - rest).max())

# a mecha, another rig
parts = mw.make(C)
C.view_layer.update()
before = {p.name: p.matrix_world.copy() for p in parts}
for p in parts:
    p.select_set(True)
C.view_layer.objects.active = parts[0]
st.kind, st.auto_joints = 'MECHA', True
bpy.ops.mch.rig_make()
mech = C.active_object
for pb in mech.pose.bones:
    pb.rotation_mode = 'XYZ'; pb.rotation_euler.x += 0.3
C.view_layer.update()

only(body)
r = bpy.ops.mch.rig_delete()
back = float(np.abs(pts(body) - rest).max())
check(f'Delete Rig on the body (the body selected): the rig gone (bent {moved * 100:.0f} cm before, its own shape now: {back * 1000:.2f} mm)',
      r == {'FINISHED'} and 'Sculpt_Rig' not in bpy.data.objects and moved > 0.01 and back < 1e-4)
check('no Armature modifier, no bone groups, the own group kept, not parented, where it was',
      not any(m.type == 'ARMATURE' for m in body.modifiers) and [g.name for g in body.vertex_groups] == ['MyMask']
      and body.parent is None and (body.matrix_world.translation - mw0.translation).length < 1e-6)
check(f'its Auto Animation gone ({acts} -> none left)', acts and not any(bpy.data.actions.get(a) for a in acts))
check('the other rig (mecha) and the control shapes untouched',
      rg.is_rig(mech) and all(p.parent is mech for p in parts) and bpy.data.collections.get(rg.WIDGETS) is not None)

only(mech)
r = bpy.ops.mch.rig_delete()
err = max((before[p.name].translation - p.matrix_world.translation).length for p in parts)
dm = max(float(np.abs(np.array(before[p.name]) - np.array(p.matrix_world)).max()) for p in parts)
check(f'Delete Rig on the posed mecha: every part let go where it was made ({err * 1000:.2f} mm, matrix off {dm:.1e})',
      r == {'FINISHED'} and err < 1e-4 and dm < 1e-4 and all(p.parent is None and rg.PART_KEY not in p for p in parts))
check('no rig left: the control shapes deleted too, nothing else',
      not any(rg.is_rig(o) for o in bpy.data.objects) and bpy.data.collections.get(rg.WIDGETS) is None
      and all(p.name in bpy.data.objects for p in parts) and 'Sculpt' in bpy.data.objects)
only(parts[0])
check('the button only shows / works with a rig', not bpy.ops.mch.rig_delete.poll())
summary()
