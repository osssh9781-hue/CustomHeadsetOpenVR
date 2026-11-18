"""0.24.244 (user: "IK 로 리깅한 김에 언리얼 연동되는 프로시저럴 애니메이팅" - Auto Creature Locomotion): on a rig made by
the Rig tool - Walk in place loops (the feet take turns: one up while the other is down, each down on the ground,
the arms against the legs, the body bobbing); Walk forward keeps each planted foot still in the world while the body
moves on; a Quadruped trot moves the diagonal legs together; Idle breathes; the mesh moves with it; Export to Unreal
writes an FBX that comes back with the deform bones only and the animation."""
import math
import os
import tempfile

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import body_whole as bw, locomotion as lo, rigging as rg  # noqa: E402

mecha_lab.register(); fresh()
C = bpy.context
S = C.scene
S.cursor.location = (0, 0, 0)
S.mch_bodykit_new.height = 1.8
bpy.ops.mch.bodywhole_add()
kb, kr = bw.pair(C.active_object)
dg = C.evaluated_depsgraph_get()
me = bpy.data.meshes.new_from_object(kb.evaluated_get(dg), preserve_all_data_layers=False, depsgraph=dg)
body = bpy.data.objects.new('Hero', me); S.collection.objects.link(body)
bpy.data.objects.remove(kb); bpy.data.objects.remove(kr)
for o in list(C.selected_objects):
    o.select_set(False)
body.select_set(True); C.view_layer.objects.active = body
S.mch_rig.kind, S.mch_rig.fingers, S.mch_rig.face = 'BODY', False, False
bpy.ops.mch.rig_make()
arm = C.active_object
st = S.mch_loco
st.gait, st.in_place = 'WALK', True
r = bpy.ops.mch.loco_make()
act = arm.animation_data.action
F = lo.plan(arm, st)['frames']
check(f'Walk: an action on the rig ({act.name}), {F} frames a cycle, looping', r == {'FINISHED'} and act is not None
      and all(any(m.type == 'CYCLES' for m in fc.modifiers) for fc in lo._fcurves(act)))


def wpos(name, f, tail=False):
    S.frame_set(f)
    b = arm.pose.bones[name]
    return np.array(arm.matrix_world @ (b.tail if tail else b.head))


f0 = S.frame_start
zl = np.array([wpos('foot.L', f)[2] for f in range(f0, f0 + F)])
zr = np.array([wpos('foot.R', f)[2] for f in range(f0, f0 + F)])
rest_z = arm.data.bones['foot.L'].head_local.z
lift = zl.max() - zl.min()
LL = lo.leg_length(arm)
check(f'each foot lifts ({lift / LL:.0%} of the leg) and comes down to where it stands ({zl.min():.3f} for {rest_z:.3f})',
      lift > 0.08 * LL and abs(zl.min() - rest_z) < 0.005 * LL)
check('the feet take turns: one up while the other is down',
      ((zl - zl.min() > 0.01 * LL) & (zr - zr.min() > 0.01 * LL)).sum() == 0 and (zl - zl.min()).max() > 0.08 * LL
      and (zr - zr.min()).max() > 0.08 * LL)
yl = np.array([wpos('hand.L', f)[1] for f in range(f0, f0 + F)])
yfl = np.array([wpos('foot.L', f)[1] for f in range(f0, f0 + F)])
check(f'the arms swing against the legs (left hand against left foot: {np.corrcoef(yl, yfl)[0, 1]:.2f})',
      np.corrcoef(yl, yfl)[0, 1] < -0.3 and np.ptp(yl) > 0.1)
hz = np.array([wpos('hips', f)[2] for f in range(f0, f0 + F)])
check(f'the body bobs ({np.ptp(hz):.3f} m) and stays in place', np.ptp(hz) > 0.01 and np.ptp([wpos('hips', f)[1] for f in range(f0, f0 + F)]) < 0.1)
a0 = [wpos(n, f0) for n in ('foot.L', 'hand.R', 'hips')]
a1 = [wpos(n, f0 + F) for n in ('foot.L', 'hand.R', 'hips')]
check('it loops: the frame after the cycle is its first frame', max(np.linalg.norm(x - y) for x, y in zip(a0, a1)) < 1e-4)
S.frame_set(f0)
P0 = np.array([v.co for v in body.evaluated_get(C.evaluated_depsgraph_get()).data.vertices])
S.frame_set(f0 + F // 4)
P1 = np.array([v.co for v in body.evaluated_get(C.evaluated_depsgraph_get()).data.vertices])
check(f'the mesh walks with it (up to {np.linalg.norm(P1 - P0, axis=1).max() / LL:.0%} of the leg)', np.linalg.norm(P1 - P0, axis=1).max() > 0.1 * LL)

# forward: the planted foot stays still in the world
st.in_place, st.loops = False, 2
bpy.ops.mch.loco_make()
duty = lo.DUTY['WALK']
stance = [f0 + int(F * 0.05) + i for i in range(int(F * duty * 0.8))]
P = np.array([wpos('foot.L', f) for f in stance])
travel = wpos('hips', f0 + 2 * F)[1] - wpos('hips', f0)[1]
check(f'Walk forward: the body moves on ({-travel:.2f} m in 2 cycles) while a planted foot stays put '
      f'({np.ptp(P[:, 1]) * 100:.1f} cm over {len(stance)} frames)', -travel > LL and np.ptp(P[:, 1]) < 0.02 * LL)

# idle
st.gait, st.in_place = 'IDLE', True
bpy.ops.mch.loco_make()
F2 = lo.plan(arm, st)['frames']
ch = np.array([wpos('chest', f, tail=True)[2] for f in range(f0, f0 + F2)])
fz = np.array([wpos('foot.L', f)[2] for f in range(f0, f0 + F2)])
check(f'Idle: the chest rises and falls ({np.ptp(ch) * 1000:.0f} mm), the feet stay ({np.ptp(fz) * 1000:.1f} mm)',
      np.ptp(ch) > 0.004 and np.ptp(fz) < 0.001)


# export to Unreal
other = bpy.data.actions.new('Somebody_Else_Walk')      # (another rig's action in the file: not this rig's)
fc = other.fcurves.new('pose.bones["hips"].location', index=0) if hasattr(other, 'fcurves') else None
other.use_fake_user = True
tmp = tempfile.mkdtemp()
path = os.path.join(tmp, 'hero_UE.fbx')
r = bpy.ops.mch.loco_export(filepath=path)
check('Export to Unreal: an FBX written', r == {'FINISHED'} and os.path.isfile(path) and os.path.getsize(path) > 100000)
names = {a.name for a in bpy.data.actions}
fresh()
bpy.ops.import_scene.fbx(filepath=path)
arms = [o for o in C.scene.objects if o.type == 'ARMATURE']
meshes = [o for o in C.scene.objects if o.type == 'MESH']
bn = set(arms[0].data.bones.keys()) if arms else set()
acts = list(bpy.data.actions)
rng = max((a.frame_range[1] - a.frame_range[0]) for a in acts) if acts else 0
check(f'only this rig\'s own animations ({[a.name.split("|")[-1] for a in acts]}); it comes back: the rig with its deform bones under one root ({len(bn)}: no IK / pole controls - Unreal\'s root bone on top), the mesh, '
      f'{len(acts)} animation(s), the longest {rng:.0f} frames',
      len(arms) == 1 and meshes and not any(n.endswith(('_ik', '_pole')) for n in bn) and 'root' in bn
      and {'hips', 'thigh.L', 'foot.R'} <= bn and len(acts) == 2 and rng >= F - 2
      and not any('Somebody' in a.name for a in acts))

# quadruped trot
fresh(); S = C.scene
parts = []
def box(c, s):
    bpy.ops.mesh.primitive_cube_add(location=c, scale=s); parts.append(C.active_object)
box((0, 0, 0.9), (0.25, 0.7, 0.25))
for x in (-0.18, 0.18):
    for y in (-0.5, 0.5):
        box((x, y, 0.33), (0.07, 0.07, 0.33))
box((0, -0.9, 1.25), (0.12, 0.2, 0.15)); box((0, 0.95, 0.95), (0.04, 0.3, 0.04))
for o in parts:
    o.select_set(True)
C.view_layer.objects.active = parts[0]
bpy.ops.object.join()
S.mch_rig.kind = 'QUAD'
bpy.ops.mch.rig_make()
arm = C.active_object
st = S.mch_loco
st.gait, st.in_place = 'RUN', True
r = bpy.ops.mch.loco_make()
F = lo.plan(arm, st)['frames']
z = {n: np.array([wpos(n, f)[2] for f in range(S.frame_start, S.frame_start + F)]) for n in ('footF.L', 'footF.R', 'footB.L', 'footB.R')}
c_diag = np.corrcoef(z['footF.L'], z['footB.R'])[0, 1]
c_side = np.corrcoef(z['footF.L'], z['footF.R'])[0, 1]
tl = np.array([wpos('tail.04', f, tail=True)[0] for f in range(S.frame_start, S.frame_start + F)])
check(f'Quadruped trot ({arm.animation_data.action.name}): the diagonal legs together ({c_diag:.2f}), the left and right apart '
      f'({c_side:.2f}), the tail swings ({np.ptp(tl):.2f} m)', r == {'FINISHED'} and c_diag > 0.9 and c_side < -0.3 and np.ptp(tl) > 0.03)
summary()
