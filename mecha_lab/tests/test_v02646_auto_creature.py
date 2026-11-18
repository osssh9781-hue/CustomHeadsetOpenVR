"""0.24.246 (user: "자동 크리쳐 모드 - 팔 큰 거 하나 덩어리로 만들어서 해 봐"): a big-armed kaiju as one lump mesh (two huge arms
coming down to the ground far out, two hind legs, two small arms and a tail off the ground) - Rig > Auto Creature
finds its four legs and its three chains with no template, puts the joints near the bends, binds it, holds the rest
pose; Auto Animation walks it on all four (neighbours opposite, each foot planted), the tail swings; the Unreal FBX
comes back with its animation."""
import json
import os
import tempfile

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
import kaiju_mesh as km
from mecha_lab import auto_creature as ac, locomotion as lo, rigging as rg  # noqa: E402

mecha_lab.register(); fresh()
C = bpy.context
S = C.scene
ob = km.make(C)
S.mch_rig.kind = 'AUTO'
r = bpy.ops.mch.rig_make()
arm = C.active_object
legs = json.loads(arm['mch_legs'])
chains = json.loads(arm['mch_chains'])
check(f'Auto Creature: {len(legs)} legs and {len(chains)} chains found ({len(arm.data.bones)} bones), the mesh bound',
      r == {'FINISHED'} and rg.is_rig(arm) and arm.get(rg.RIG_KEY) == 'AUTO' and len(legs) == 4 and len(chains) == 3
      and any(m.type == 'ARMATURE' and m.object is arm for m in ob.modifiers))
T = {k: np.array(v) for k, v in km.SKELETON.items()}
feet = {b: np.array(arm.data.bones[b + '.foot'].head_local) for b in legs}
want = ['hand.L', 'hand.R', 'toe.L', 'toe.R']
match = {w: min(float(np.linalg.norm(T[w] - p)) for p in feet.values()) for w in want}
check(f'each leg ends where the creature stands: the big hands and the hind toes (cm: '
      f'{", ".join(f"{k} {v * 100:.0f}" for k, v in match.items())})', max(match.values()) < 0.2)
joints = [np.array(b.head_local) for b in arm.data.bones if b.name.startswith('leg') and b.name[-2:].isdigit()]
jm = {w: min(float(np.linalg.norm(T[w] - p)) for p in joints) for w in ('elbow.L', 'elbow.R', 'knee.L', 'knee.R')}
check(f'a joint at each big bend (cm: {", ".join(f"{k} {v * 100:.0f}" for k, v in jm.items())})', max(jm.values()) < 0.3)
tips = []
for c in chains:
    names = sorted(n for n in arm.data.bones.keys() if n.startswith(c + '.') and n[len(c) + 1:].isdigit())
    tips.append(np.array(arm.data.bones[names[-1]].tail_local))
tm = {w: min(float(np.linalg.norm(T[w] - p)) for p in tips) for w in ('shand.L', 'shand.R', 'tail4')}
check(f'the chains are the small arms and the tail (their tips, cm: {", ".join(f"{k} {v * 100:.0f}" for k, v in tm.items())})',
      max(tm.values()) < 0.25)
C.view_layer.update()
still = max((p.matrix.to_translation() - p.bone.matrix_local.to_translation()).length for p in arm.pose.bones)
check(f'the IK keeps the rest pose ({still * 1000:.1f} mm)', still < 0.005)

st = S.mch_loco
st.gait, st.in_place, st.loops = 'WALK', False, 2
r = bpy.ops.mch.loco_make()
F = lo.plan(arm, st)['frames']
f0 = S.frame_start


def wpos(name, f, tail=False):
    S.frame_set(f)
    b = arm.pose.bones[name]
    return np.array(arm.matrix_world @ (b.tail if tail else b.head))


Z = {b: np.array([wpos(b + '.foot', f)[2] for f in range(f0, f0 + F)]) for b in legs}
lifts = {b: float(np.ptp(z)) for b, z in Z.items()}
up = {b: z - z.min() > 0.02 for b, z in Z.items()}
both = [(a, b) for i, a in enumerate(legs) for b in legs[i + 1:] if (up[a] & up[b]).sum() > 0]
check(f'Walk: every foot lifts in turn (lifts {[round(v, 2) for v in lifts.values()]} m); legs off the ground together: '
      f'{len(both)} pair(s) of 6', r == {'FINISHED'} and min(lifts.values()) > 0.05 and len(both) <= 2)
plants = []
for b in legs:
    P = np.array([wpos(b + '.foot', f) for f in range(f0, f0 + F)])
    down = P[:, 2] - P[:, 2].min() < 0.003                 # (the frames it stands on the ground: each stretch alone)
    runs, cur = [], []
    for i, d_ in enumerate(down):
        if d_:
            cur.append(i)
        elif cur:
            runs.append(cur); cur = []
    if cur:
        runs.append(cur)
    plants.append(max((float(np.ptp(P[r_, 1])) for r_ in runs if len(r_) > 2), default=9.0))
ph = lo.auto_phases(arm, [b + '.foot_ik' for b in legs], 'WALK')
fp = {b: np.array(arm.data.bones[b + '.foot'].head_local) for b in legs}
diag = [(a, c) for a in legs for c in legs if a < c and np.sign(fp[a][0]) != np.sign(fp[c][0])
        and np.sign(fp[a][1] - np.mean([v[1] for v in fp.values()])) != np.sign(fp[c][1] - np.mean([v[1] for v in fp.values()]))]
same_diag = all(abs(((ph[a + '.foot_ik'] - ph[c + '.foot_ik']) + 0.5) % 1.0 - 0.5) < 0.2 for a, c in diag)
check(f'diagonal legs step together ({len(diag)} diagonal pairs in step)', len(diag) == 2 and same_diag)
travel = -(wpos('body', f0 + 2 * F)[1] - wpos('body', f0)[1])
check(f'the body walks on ({travel:.2f} m in 2 cycles), each planted foot stays put (worst slide {max(plants) * 100:.1f} cm)',
      travel > 0.5 and plants and max(plants) < 0.05)
tl = sorted(n for n in arm.data.bones.keys() if n.startswith(chains[-1] + '.') and n[len(chains[-1]) + 1:].isdigit())[-1]
sway = np.ptp([wpos(tl, f, tail=True)[0] for f in range(f0, f0 + F)])
check(f'the chains swing (the tail tip {sway:.2f} m sideways - a 3 m tail)', 0.05 < sway < 1.2)
tmp = tempfile.mkdtemp()
path = os.path.join(tmp, 'kaiju_UE.fbx')
r = bpy.ops.mch.loco_export(filepath=path)
fresh()
bpy.ops.import_scene.fbx(filepath=path)
acts = list(bpy.data.actions)
check(f'Export to Unreal: back with the rig, the mesh and the walk ({[a.name.split("|")[-1] for a in acts]})',
      r == {'FINISHED'} and any(o.type == 'ARMATURE' for o in C.scene.objects) and any(o.type == 'MESH' for o in C.scene.objects)
      and len(acts) == 1)
summary()
