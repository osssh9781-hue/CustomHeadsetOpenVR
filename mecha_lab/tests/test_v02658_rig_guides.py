"""0.24.258 (user: "리그 만들기 전에 표면에다가 가이드 라인을 그을 수는 없나?"): Rig > Guides - the user's lines through the
creature become the rig: the first the body, the others hanging off the nearest bone (a line drawn from the tip turned
round), lines ending on the ground legs with IK feet, the rest swaying chains; bound, rest pose still, it walks."""
import json

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
import kaiju_mesh as km
from mecha_lab import rig_guides as rgd, rigging as rg  # noqa: E402

mecha_lab.register(); fresh()
C = bpy.context
S = C.scene
ob = km.make(C)
K = {k: np.array(v, float) for k, v in km.SKELETON.items()}


def line(*names, n=8):
    P = [K[names[0]]]
    for a, b in zip(names, names[1:]):
        for t in np.linspace(0, 1, n + 1)[1:]:
            P.append(K[a] * (1 - t) + K[b] * t)
    return np.array(P)


lines = [line('pelvis', 'chest', 'neck', 'head'), line('tail1', 'tail2', 'tail3', 'tail4')]
for s in 'LR':
    lines += [line(f'hip.{s}', f'knee.{s}', f'ankle.{s}', f'toe.{s}'),
              line(f'shoulder.{s}', f'elbow.{s}', f'wrist.{s}', f'hand.{s}')]
lines += [line('sarm.L', 'selbow.L', 'shand.L'), line('shand.R', 'selbow.R', 'sarm.R')]     # (the last from its tip)
for P in lines:
    rgd.add_stroke(C, ob, P)
g = rgd.guides_of(ob)
check(f'the guide lines kept beside the mesh ({g.name}: {len(g.data.splines)} lines), not rendered',
      g is not None and len(rgd.strokes(ob)) == len(lines) and g.hide_render)
for o in list(C.selected_objects):
    o.select_set(False)
ob.select_set(True); C.view_layer.objects.active = ob
st = S.mch_rig
st.kind, st.bind = 'GUIDE', True
r = bpy.ops.mch.rig_make()
arm = C.active_object
legs = json.loads(arm['mch_legs']); chains = json.loads(arm['mch_chains'])
check(f'Make Rig from the lines: {len(legs)} legs (the 2 legs + the 2 knuckle-walking arms), {len(chains)} chains (tail, 2 small arms), '
      f'{len(arm.data.bones)} bones, the mesh bound, the lines hidden',
      r == {'FINISHED'} and rg.is_rig(arm) and len(legs) == 4 and len(chains) == 3 and not g.visible_get()
      and any(m.type == 'ARMATURE' and m.object is arm for m in ob.modifiers))
B = [(np.array(b.head_local), np.array(b.tail_local)) for b in arm.data.bones if b.use_deform]
dd = {k: min(rgd._seg_dist(p, h, t) for h, t in B) for k, p in K.items()}
far = max(v for k, v in dd.items() if not k.startswith(('toe', 'wrist')))   # (nearly straight there: no joint)
check(f'the bones lie on the lines (the farthest bend {far * 100:.1f} cm off a bone)', far < 0.1)
sarmR = [b for b in arm.data.bones if b.use_deform and np.linalg.norm(np.array(b.head_local) - K['sarm.R']) < 0.15]
check('a line drawn from its tip is turned round: its first bone starts at the body end', bool(sarmR))
C.view_layer.update()
still = max((pb.matrix.to_translation() - pb.bone.matrix_local.to_translation()).length for pb in arm.pose.bones)
check(f'IK on the feet, the rest pose still ({still * 1000:.1f} mm)',
      all(b + '.foot_ik' in arm.data.bones for b in legs) and still < 0.005)
S.mch_loco.gait = 'WALK'
r = bpy.ops.mch.loco_make()
feet = [b + '.foot_ik' for b in legs]
pos = []
for f in range(S.frame_start, S.frame_start + 24, 3):
    S.frame_set(f)
    pos.append([np.array(arm.matrix_world @ arm.pose.bones[n].head) for n in feet])
pos = np.array(pos)
lift = float((pos[:, :, 2] - pos[0, :, 2].min()).max())
check(f'Auto Animation walks it (feet lift {lift * 100:.0f} cm)', r == {'FINISHED'} and lift > 0.02)
# the user's own kinds (user: "가장 베이스가 되는 몸, 뼈, IK 위치를 내가 잡으면"): a small arm drawn FIRST as IK, then the body,
# the big arms (they reach the ground) as IK not legs, the legs as Leg, the tail as plain Bones
bpy.ops.mch.rig_delete()
for o in list(C.selected_objects):
    o.select_set(False)
ob.select_set(True); C.view_layer.objects.active = ob
g = rgd.guides_of(ob)
if g is not None:
    bpy.data.objects.remove(g)
plan = [('IK', line('sarm.L', 'selbow.L', 'shand.L')), ('BODY', line('pelvis', 'chest', 'neck', 'head')),
        ('BONES', line('tail1', 'tail2', 'tail3', 'tail4'))]
for s_ in 'LR':
    plan += [('LEG', line(f'hip.{s_}', f'knee.{s_}', f'ankle.{s_}', f'toe.{s_}')),
             ('IK', line(f'shoulder.{s_}', f'elbow.{s_}', f'wrist.{s_}', f'hand.{s_}'))]
for k_, P in plan:
    rgd.add_stroke(C, ob, P, k_)
check('each line keeps the kind it was drawn with', rgd.line_kinds(ob) == [k_ for k_, _P in plan])
r = bpy.ops.mch.rig_make()
arm = C.active_object
legs = json.loads(arm['mch_legs']); chains = json.loads(arm['mch_chains'])
iks = [pb.name for pb in arm.pose.bones for c in pb.constraints if c.type == 'IK']
body_first = arm.data.bones['trunk1.01'].parent.name == 'body' and np.linalg.norm(np.array(arm.data.bones['trunk1.01'].head_local) - K['pelvis']) < 0.1
C.view_layer.update()
still = max((pb.matrix.to_translation() - pb.bone.matrix_local.to_translation()).length for pb in arm.pose.bones)
check(f'Make Rig with the kinds: the body first whatever the order drawn, {len(legs)} legs (the Leg lines), '
      f'{len(iks) - len(legs)} IK ends (the 3 IK lines), {len(chains)} swaying chain (the tail), rest pose still ({still * 1000:.1f} mm)',
      r == {'FINISHED'} and body_first and len(legs) == 2 and len(iks) - len(legs) == 3 and len(chains) == 1 and still < 0.005)
summary()
