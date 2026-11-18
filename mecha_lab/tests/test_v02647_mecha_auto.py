"""0.24.247 (user: 메카 리깅 - 부품 접촉으로 자동, 다리 IK, 자동 걷기): a two-legged walker mech of separate parts - Rig >
Mecha (Auto Joints) puts the body first and each part on the one it touches nearer the body, the joints where they
meet; the legs (down to a foot on the ground) get IK and the rest pose holds; each part rides its bone rigidly;
Auto Animation walks it (feet in turn, each planted, the body moving on); the Unreal FBX comes back with the walk."""
import json
import os
import tempfile

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
import mech_walker as mw
from mecha_lab import locomotion as lo, rigging as rg  # noqa: E402

mecha_lab.register(); fresh()
C = bpy.context
S = C.scene
parts = mw.make(C)
before = {p.name: p.matrix_world.copy() for p in parts}
S.mch_rig.kind, S.mch_rig.auto_joints = 'MECHA', True
r = bpy.ops.mch.rig_make()
arm = C.active_object
b = arm.data.bones
par = {p.name: (b[p.name].parent.name if b[p.name].parent else None) for p in parts}
want = {'Turret': 'Body', 'Thigh.L': 'Body', 'Shin.L': 'Thigh.L', 'Foot.L': 'Shin.L', 'UpperArm.L': 'Body', 'Gun.L': 'UpperArm.L',
        'Thigh.R': 'Body', 'Shin.R': 'Thigh.R', 'Foot.R': 'Shin.R', 'UpperArm.R': 'Body', 'Gun.R': 'UpperArm.R'}
check(f'Auto Joints: the body first, each part on the one it touches ({sum(par[k] == v for k, v in want.items())} / {len(want)} right)',
      r == {'FINISHED'} and all(par[k] == v for k, v in want.items()), {k: par[k] for k in want if par[k] != want[k]})
err = {k: float(np.linalg.norm(np.array(b[k].head_local) - np.array(v))) for k, v in mw.JOINTS.items()}
check(f'the joints where the parts meet (worst {max(err.values()) * 100:.0f} cm: '
      f'{", ".join(f"{k} {v * 100:.0f}" for k, v in sorted(err.items(), key=lambda t: -t[1])[:3])})', max(err.values()) < 0.15)
check('nothing moved, each part on its bone', all((before[p.name].translation - p.matrix_world.translation).length < 1e-5
                                                   and p.parent is arm and p.parent_type == 'BONE' for p in parts))
legs = json.loads(arm['mch_legs'])
C.view_layer.update()
still = max((p.matrix.to_translation() - p.bone.matrix_local.to_translation()).length for p in arm.pose.bones)
check(f'the legs found ({legs}) with IK on their feet, the rest pose holds ({still * 1000:.1f} mm)',
      sorted(legs) == ['Foot.L', 'Foot.R'] and all(any(c.type == 'IK' for pb in arm.pose.bones for c in pb.constraints
                                                       if c.subtarget == f + '_ik') for f in legs) and still < 0.005)
fik = arm.pose.bones['Foot.L_ik']
from mathutils import Matrix
fik.matrix = Matrix.Translation((0, -0.2, 0.3)) @ fik.matrix
C.view_layer.update()
foot = parts[[p.name for p in parts].index('Foot.L')]
shin = parts[[p.name for p in parts].index('Shin.L')]
check('moving a foot target lifts the foot part, the shin and thigh bend with it (rigidly)',
      (foot.matrix_world.translation - before['Foot.L'].translation).length > 0.25
      and (shin.matrix_world.translation - before['Shin.L'].translation).length > 0.05)
fik.matrix = Matrix.Translation((0, 0.2, -0.3)) @ fik.matrix
st = S.mch_loco
st.gait, st.in_place, st.loops = 'WALK', False, 2
r = bpy.ops.mch.loco_make()
F = lo.plan(arm, st)['frames']
f0 = S.frame_start


def wpos(ob, f):
    S.frame_set(f)
    return np.array(ob.matrix_world.translation)


fl = np.array([wpos(foot, f) for f in range(f0, f0 + F)])
fr_ = np.array([wpos(parts[[p.name for p in parts].index('Foot.R')], f) for f in range(f0, f0 + F)])
upl, upr = fl[:, 2] - fl[:, 2].min() > 0.01, fr_[:, 2] - fr_[:, 2].min() > 0.01
runs, cur = [], []
down = ~upl
for i, d_ in enumerate(down):
    if d_:
        cur.append(i)
    elif cur:
        runs.append(cur); cur = []
if cur:
    runs.append(cur)
slide = max((float(np.ptp(fl[r_, 1])) for r_ in runs if len(r_) > 2), default=9.0)
body = parts[0]
travel = -(wpos(body, f0 + 2 * F)[1] - wpos(body, f0)[1])
check(f'Walk: the feet take turns ({int((upl & upr).sum())} frames both up), each lifts ({np.ptp(fl[:, 2]):.2f} m), '
      f'a planted foot stays put ({slide * 100:.1f} cm), the mech walks on ({travel:.2f} m)',
      r == {'FINISHED'} and (upl & upr).sum() == 0 and np.ptp(fl[:, 2]) > 0.05 and slide < 0.02 and travel > 0.5)
path = os.path.join(tempfile.mkdtemp(), 'mech_UE.fbx')
r = bpy.ops.mch.loco_export(filepath=path)
check('Export to Unreal: an FBX with the parts and the walk', r == {'FINISHED'} and os.path.getsize(path) > 10000)
# without Auto Joints: as before (every part on the root, a bone through its middle)
fresh(); S = C.scene
parts = mw.make(C)
S.mch_rig.kind, S.mch_rig.auto_joints = 'MECHA', False
bpy.ops.mch.rig_make()
arm = C.active_object
check('Auto Joints off: every part on the root as before', all(arm.data.bones[p.name].parent.name == 'root' for p in parts))
summary()
