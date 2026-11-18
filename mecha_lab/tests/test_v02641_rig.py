"""0.24.241 (user: "리깅 툴" - 사람 / 크리쳐 몸, 메카, 꼬리 / 촉수 체인): the Rig tool.  Human: on the One-Piece
Human's mesh (copied bare, as a sculpt would be) the joints found sit near the body kit's own skeleton, IK keeps the
rest pose still and moves the hand, the mesh is bound (every point weighted) and bends with the bones.  Quadruped:
four legs, spine, head, tail inside a block animal.  Mecha: one bone per part, the parts ride them rigidly, a click
sets a part's joint without moving it.  Chain: bones along a tapered tail from the thick end, bound, Jiggle lags."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector, Matrix

import mecha_lab
from mecha_lab import body_whole as bw, rigging as rg, tool_state as ts, ui_tool_settings as uts  # noqa: E402

mecha_lab.register(); fresh()
C = bpy.context
S = C.scene
check('the Rig tool: in Move beside Pose, its icon, its window, its native tool',
      'RIG' in ts.TOOL_BY_ID and 'RIG' in dict(ts.TOOL_GROUPS)['Move'] and uts.DRAWERS.get('RIG') is not None)
S.cursor.location = (0, 0, 0)
S.mch_bodykit_new.height = 1.8
bpy.ops.mch.bodywhole_add()
kit_body, kit_rig = bw.pair(C.active_object)
dg = C.evaluated_depsgraph_get()
me = bpy.data.meshes.new_from_object(kit_body.evaluated_get(dg), preserve_all_data_layers=False, depsgraph=dg)
body = bpy.data.objects.new('Sculpt', me)
S.collection.objects.link(body)
body.matrix_world = kit_body.matrix_world.copy()
for vg in list(body.vertex_groups):
    body.vertex_groups.remove(vg)
truth = {n: np.array(kit_rig.matrix_world @ kit_rig.data.bones[n].head_local) for n in kit_rig.data.bones.keys()}
kit_rig.hide_set(True); kit_body.hide_set(True)
for o in list(C.selected_objects):
    o.select_set(False)
body.select_set(True); C.view_layer.objects.active = body
st = S.mch_rig
st.kind, st.ik, st.bind = 'BODY', True, True
r = bpy.ops.mch.rig_make()
arm = C.active_object
check('Human: Make Rig builds the armature', r == {'FINISHED'} and rg.is_rig(arm) and arm.get(rg.RIG_KEY) == 'BODY'
      and {'hips', 'chest', 'head', 'upper_arm.L', 'forearm.R', 'thigh.L', 'shin.R', 'foot.L'} <= set(arm.data.bones.keys()))
H = 1.8
J = {n: np.array(arm.matrix_world @ arm.data.bones[n].head_local) for n in arm.data.bones.keys()}
pairs = [('upper_arm.L', 'UpperArm.L'), ('forearm.L', 'Forearm.L'), ('hand.L', 'Hand.L'), ('thigh.L', 'Thigh.L'),
         ('shin.L', 'Shin.L'), ('foot.L', 'Foot.L'), ('neck', 'Neck'), ('head', 'Head'), ('forearm.R', 'Forearm.R'),
         ('shin.R', 'Shin.R')]
have = [(a, b) for a, b in pairs if b in truth]
err = {a: float(np.linalg.norm(J[a] - truth[b])) for a, b in have}
check(f'the joints found sit near the body kit\'s own skeleton ({len(have)} joints, worst {max(err.values()):.3f} m = '
      f'{max(err.values()) / H:.1%} of the height): {", ".join(f"{k} {v:.3f}" for k, v in err.items())}',
      len(have) >= 8 and max(err.values()) < 0.09 * H and np.mean(list(err.values())) < 0.05 * H)
C.view_layer.update()
still = max((pb.matrix.to_translation() - pb.bone.matrix_local.to_translation()).length for pb in arm.pose.bones)
check(f'IK on: the rest pose does not move (largest joint shift {still:.4f})', still < 0.005)
W = np.zeros(len(body.data.vertices))
idx = {vg.index for vg in body.vertex_groups if vg.name in arm.data.bones and arm.data.bones[vg.name].use_deform}
for v in body.data.vertices:
    W[v.index] = sum(g.weight for g in v.groups if g.group in idx)
check(f'the body is bound: every point weighted ({(W > 0.01).mean():.1%})', (W > 0.01).mean() > 0.995 and
      any(m.type == 'ARMATURE' and m.object is arm for m in body.modifiers))


def eval_pts(ob):
    C.view_layer.update()
    d = C.evaluated_depsgraph_get()
    ev = ob.evaluated_get(d)
    return np.array([ev.matrix_world @ v.co for v in ev.data.vertices])


P0 = eval_pts(body)
hand0 = np.array(arm.matrix_world @ arm.pose.bones['hand.L'].head)
arm.pose.bones['hand.L_ik'].location = (0.0, 0.0, 0.0)
ik = arm.pose.bones['hand.L_ik']
ik.matrix = Matrix.Translation((0, -0.15, 0.25)) @ ik.matrix
P1 = eval_pts(body)
hand1 = np.array(arm.matrix_world @ arm.pose.bones['hand.L'].head)
moved = np.linalg.norm(P1 - P0, axis=1)
left = P0[:, 0] > 0.35
check(f'moving the hand target: the arm follows (hand {np.linalg.norm(hand1 - hand0):.3f} m), the hand\'s skin with it, '
      f'the other side still', np.linalg.norm(hand1 - hand0) > 0.15 and moved[left].max() > 0.15
      and moved[P0[:, 0] < -0.35].max() < 1e-4)
ik.matrix = Matrix.Translation((0, 0.15, -0.25)) @ ik.matrix
C.view_layer.update()
# 0.24.242 fingers + face
fing = {'index': 'Finger2', 'middle': 'Finger3', 'ring': 'Finger4', 'pinky': 'Finger5'}
ferr = {}
for f, k in fing.items():
    if f'{k}a.L' in truth and f'{f}.01.L' in arm.data.bones:
        ferr[f] = float(np.linalg.norm(J[f'{f}.01.L'] - truth[f'{k}a.L']))
tipe = {}
for f, k in fing.items():
    b = arm.data.bones.get(f'{f}.03.L')
    if b is not None and f'{k}c.L' in kit_rig.data.bones:
        tipe[f] = float(np.linalg.norm(np.array(arm.matrix_world @ b.tail_local) - np.array(kit_rig.matrix_world @ kit_rig.data.bones[f'{k}c.L'].tail_local)))
check(f'Fingers: thumb + four, 3 bones each, both hands; the knuckles near the body kit\'s (cm: '
      f'{", ".join(f"{k} {v * 100:.1f}" for k, v in ferr.items())}; tips {", ".join(f"{k} {v * 100:.1f}" for k, v in tipe.items())})',
      all(f'{f}.0{i}.{s_}' in arm.data.bones for f in rg.FINGERS for i in (1, 2, 3) for s_ in 'LR')
      and len(ferr) == 4 and max(ferr.values()) < 0.03 and max(tipe.values()) < 0.04)
P0 = eval_pts(body)
pb = arm.pose.bones['index.01.L']; pb.rotation_mode = 'XYZ'; pb.rotation_euler = (math.radians(50), 0, 0)
C.view_layer.update()
t3 = arm.pose.bones['index.03.L']
curl = math.degrees((t3.matrix.to_3x3() @ Vector((0, 1, 0))).angle(t3.bone.matrix_local.to_3x3() @ Vector((0, 1, 0))))
P1 = eval_pts(body)
check(f'turning the index finger\'s first bone curls the whole finger (tip turned {curl:.0f} degrees), its skin moves, '
      f'the other hand still', curl > 100 and np.linalg.norm(P1 - P0, axis=1).max() > 0.01
      and np.linalg.norm(P1 - P0, axis=1)[P0[:, 0] < -0.2].max() < 1e-5)
pb.rotation_euler = (0, 0, 0)
check('Face: jaw, chin, lips, brows, eyes looking at a target',
      {'jaw', 'chin', 'lip.upper', 'lip.lower', 'lip.L', 'lip.R', 'brow.L', 'brow.R', 'eye.L', 'eye.R', 'eyes_target'}
      <= set(arm.data.bones.keys()) and any(c.type == 'DAMPED_TRACK' for c in arm.pose.bones['eye.L'].constraints))
eyeL = np.array(arm.matrix_world @ arm.data.bones['eye.L'].head_local)
lipL = np.array(arm.matrix_world @ arm.data.bones['lip.L'].head_local)
jaw = arm.data.bones['jaw']
check(f'the face bones sit in the face (eye z {eyeL[2]:.3f} x {eyeL[0]:.3f}, mouth corner z {lipL[2]:.3f}; height 1.8)',
      1.65 < eyeL[2] < 1.73 and 0.015 < eyeL[0] < 0.05 and 1.58 < lipL[2] < 1.66 and eyeL[1] < 0.0)
C.view_layer.update()
P0 = eval_pts(body)
pj = arm.pose.bones['jaw']; pj.rotation_mode = 'XYZ'; pj.rotation_euler = (math.radians(20), 0, 0)
P1 = eval_pts(body)
mv = np.linalg.norm(P1 - P0, axis=1)
chin = (P0[:, 2] > 1.54) & (P0[:, 2] < 1.6) & (P0[:, 1] < 0) & (np.abs(P0[:, 0]) < 0.03)
check(f'opening the jaw moves the chin ({mv[chin].max():.3f} m), not the top of the head ({mv[P0[:, 2] > 1.75].max():.4f})',
      mv[chin].max() > 0.01 and mv[P0[:, 2] > 1.75].max() < 0.003)
pj.rotation_euler = (0, 0, 0)
# 0.24.242 place the bones on one side, mirror, bind
for o in list(C.selected_objects):
    o.select_set(False)
arm.select_set(True); C.view_layer.objects.active = arm
with rg._Edit(C, arm) as ebs:
    ebs['forearm.L'].head = ebs['forearm.L'].head + Vector((0.0, 0.03, 0.02))
r = bpy.ops.mch.rig_mirror(side='L')
er = arm.data.bones['forearm.R'].head_local
el = arm.data.bones['forearm.L'].head_local
x0 = arm['mch_x0']
check('Mirror L -> R: the moved elbow\'s place copied to the other side', r == {'FINISHED'}
      and abs(er.x - (2 * x0 - el.x)) < 1e-5 and abs(er.y - el.y) < 1e-5 and abs(er.z - el.z) < 1e-5)
with rg._Edit(C, arm) as ebs:
    ebs['hand.L'].head = ebs['hand.L'].head + Vector((0.0, 0.0, 0.03))
    ebs['forearm.L'].tail = ebs['hand.L'].head
r = bpy.ops.mch.rig_bind()
C.view_layer.update()
hik = arm.data.bones['hand.L_ik'].head_local
still = max((p.matrix.to_translation() - p.bone.matrix_local.to_translation()).length for p in arm.pose.bones)
check(f'Bind after moving bones: the IK targets follow the moved hand, the rest pose still ({still:.4f}), the body weighted',
      r == {'FINISHED'} and (hik - arm.data.bones['hand.L'].head_local).length < 1e-5 and still < 0.006
      and any(m.type == 'ARMATURE' for m in body.modifiers))

# 0.24.242 the controls: big coloured shapes, out of the mesh
check('IK controls drawn as rings / balls (not hidden in the hands and feet)',
      all(arm.pose.bones[n].custom_shape is not None for n in ('hand.L_ik', 'foot.R_ik', 'forearm.L_pole', 'shin.R_pole'))
      and arm.pose.bones['foot.L_ik'].custom_shape.name == 'WGT_mch_foot')

# 0.24.242 (user: a striding digitigrade creature, "역관절") a posed creature with reverse legs
fresh(); S = C.scene; st = S.mch_rig
pts = {'pelvis': (0, 0, 0.95), 'chest': (0, 0.02, 1.35), 'neck': (0, 0, 1.55), 'head': (0, -0.05, 1.75),
       'hip.L': (0.11, 0, 0.92), 'knee.L': (0.14, -0.22, 0.62), 'hock.L': (0.15, 0.12, 0.3), 'ankle.L': (0.15, 0.0, 0.06),
       'toe.L': (0.15, -0.22, 0.03),
       'sh.L': (0.22, 0.02, 1.42), 'elbow.L': (0.42, 0.12, 1.18), 'wrist.L': (0.5, -0.18, 1.02), 'tip.L': (0.55, -0.3, 0.98)}
for k in list(pts):
    if k.endswith('.L'):
        x, y, z = pts[k]
        pts[k[:-1] + 'R'] = (-x, y, z)
names = list(pts)
idx = {n: i for i, n in enumerate(names)}
edges = [('pelvis', 'chest'), ('chest', 'neck'), ('neck', 'head')]
for sd in 'LR':
    edges += [('pelvis', f'hip.{sd}'), (f'hip.{sd}', f'knee.{sd}'), (f'knee.{sd}', f'hock.{sd}'), (f'hock.{sd}', f'ankle.{sd}'),
              (f'ankle.{sd}', f'toe.{sd}'), ('chest', f'sh.{sd}'), (f'sh.{sd}', f'elbow.{sd}'), (f'elbow.{sd}', f'wrist.{sd}'),
              (f'wrist.{sd}', f'tip.{sd}')]
me = bpy.data.meshes.new('cr'); me.from_pydata([pts[n] for n in names], [(idx[a], idx[b]) for a, b in edges], [])
cr = bpy.data.objects.new('Creature', me); S.collection.objects.link(cr)
sk = cr.modifiers.new('Skin', 'SKIN')
rad = {'pelvis': 0.13, 'chest': 0.16, 'neck': 0.06, 'head': 0.1}
for i, n in enumerate(names):
    r_ = rad.get(n, 0.05 if not n.startswith(('tip', 'toe', 'wrist', 'ankle')) else 0.035)
    me.skin_vertices[0].data[i].radius = (r_, r_)
me.skin_vertices[0].data[idx['pelvis']].use_root = True
cr.modifiers.new('Sub', 'SUBSURF').levels = 1
for o in list(C.selected_objects):
    o.select_set(False)
cr.select_set(True); C.view_layer.objects.active = cr
bpy.ops.object.convert(target='MESH')
cr = C.active_object
st.kind, st.legs, st.fingers, st.face, st.ik, st.bind = 'BODY', 'REVERSE', False, False, True, True
r = bpy.ops.mch.rig_make()
arm = C.active_object
B = lambda n: np.array(arm.matrix_world @ arm.data.bones[n].head_local)
err = {'knee': np.linalg.norm(B('shin.L') - pts['knee.L']), 'hock': np.linalg.norm(B('hock.L') - pts['hock.L']),
       'ankle': np.linalg.norm(B('foot.L') - pts['ankle.L']), 'elbow': np.linalg.norm(B('forearm.L') - pts['elbow.L']),
       'elbow.R': np.linalg.norm(B('forearm.R') - pts['elbow.R'])}
check(f'Reverse Legs on a striding creature with bent arms: thigh, shin, hock, foot; the joints where it bends '
      f'(cm: {", ".join(f"{k} {v * 100:.1f}" for k, v in err.items())})',
      r == {'FINISHED'} and 'hock.L' in arm.data.bones and max(err.values()) < 0.05 * 1.8)
C.view_layer.update()
still = max((p_.matrix.to_translation() - p_.bone.matrix_local.to_translation()).length for p_ in arm.pose.bones)
ikc = next(c for c in arm.pose.bones['hock.L'].constraints if c.type == 'IK')
check(f'its leg IK runs over all three leg bones, the rest pose still ({still:.4f})', ikc.chain_count == 3 and still < 0.01)
fik = arm.pose.bones['foot.L_ik']
P0 = eval_pts(cr)
foot0 = np.array(arm.matrix_world @ arm.pose.bones['foot.L'].head)
fik.matrix = Matrix.Translation((0, -0.1, 0.2)) @ fik.matrix
P1 = eval_pts(cr)
foot1 = np.array(arm.matrix_world @ arm.pose.bones['foot.L'].head)
check(f'lifting the foot control: the foot goes with it ({foot1.round(3).tolist()} for {(np.array(pts["ankle.L"]) + [0, -0.1, 0.2]).round(3).tolist()}, was {B("foot.L").round(3).tolist()}), the leg bends ({np.linalg.norm(P1 - P0, axis=1).max():.3f})', np.linalg.norm(foot1 - (foot0 + [0, -0.1, 0.2])) < 0.01
      and np.linalg.norm(P1 - P0, axis=1).max() > 0.1)
fik.matrix = Matrix.Translation((0, 0.1, -0.2)) @ fik.matrix
# 0.24.242 (user: "에딧 본에서 뼈 편집해도 오브젝트 모드 들어오면 약간 이상해") Edit Mode by hand, then back
C.view_layer.update()
for o in list(C.selected_objects):
    o.select_set(False)
arm.select_set(True); C.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
rg._edit_watch(S)
kept = list(rg._EDITING.get(arm.name, []))
rg._hide_bend(arm.name)
mod = next(m for m in cr.modifiers if m.type == 'ARMATURE')
check('in Edit Mode the mesh is shown unbent (its armature modifier off while editing)', bool(kept) and not mod.show_viewport)
eb = arm.data.edit_bones
eb['hock.L'].head = eb['hock.L'].head + Vector((0, 0.04, 0.03))
bpy.ops.object.mode_set(mode='OBJECT')
rg._edit_watch(S)
check('leaving Edit Mode is noticed', arm.name not in rg._EDITING)
msg = rg.after_edit(C, arm, kept)
C.view_layer.update()
still = max((p_.matrix.to_translation() - p_.bone.matrix_local.to_translation()).length for p_ in arm.pose.bones)
check(f'back in Object Mode: the bending shown again, the IK targets on the moved bones, the mesh weighted again, '
      f'the rest pose still ({still:.4f}) - {msg}', all(m.show_viewport for m in cr.modifiers if m.type == 'ARMATURE') and still < 0.01 and 'weighted again' in msg)

# --- quadruped ---
fresh(); S = C.scene; st = S.mch_rig
bm_parts = []
def box(c, s):
    bpy.ops.mesh.primitive_cube_add(location=c, scale=s)
    bm_parts.append(C.active_object)
box((0, 0, 0.9), (0.25, 0.7, 0.25))          # torso
for x in (-0.18, 0.18):
    for y in (-0.5, 0.5):
        box((x, y, 0.33), (0.07, 0.07, 0.33))
box((0, -0.9, 1.25), (0.12, 0.2, 0.15))      # neck + head
box((0, 0.95, 0.95), (0.04, 0.3, 0.04))      # tail
for o in bm_parts:
    o.select_set(True)
C.view_layer.objects.active = bm_parts[0]
bpy.ops.object.join()
animal = C.active_object
st.kind = 'QUAD'
r = bpy.ops.mch.rig_make()
arm = C.active_object
legs = [n for n in arm.data.bones.keys() if n.startswith('leg')]
feet = {n: np.array(arm.matrix_world @ arm.data.bones[n].head_local) for n in arm.data.bones.keys() if n.startswith('foot') and not n.endswith('_ik')}
ok_feet = all(abs(abs(p[0]) - 0.18) < 0.06 and abs(abs(p[1]) - 0.5) < 0.1 and p[2] < 0.25 for p in feet.values())
check(f'Quadruped: four legs ({sorted(legs)}), each foot in its leg ({len(feet)})', r == {'FINISHED'} and len(legs) == 4
      and len(feet) == 4 and ok_feet, {k: v.round(2).tolist() for k, v in feet.items()})
hd = np.array(arm.matrix_world @ arm.data.bones['head'].head_local)
tt = np.array(arm.matrix_world @ arm.data.bones['tail.04'].tail_local)
check(f'the head toward -Y and the tail to +Y (head {hd.round(2).tolist()}, tail tip {tt.round(2).tolist()})',
      hd[1] < -0.6 and tt[1] > 1.1)
C.view_layer.update()
still = max((pb.matrix.to_translation() - pb.bone.matrix_local.to_translation()).length for pb in arm.pose.bones)
check(f'its IK keeps the rest pose ({still:.4f}), the animal bound', still < 0.005 and
      any(m.type == 'ARMATURE' for m in animal.modifiers))

# --- mecha ---
fresh(); S = C.scene; st = S.mch_rig
parts = []
for i, (c, s) in enumerate((((0, 0, 0.5), (0.3, 0.3, 0.5)), ((0, 0, 1.4), (0.15, 0.15, 0.4)), ((0, 0, 2.1), (0.1, 0.1, 0.3)))):
    bpy.ops.mesh.primitive_cube_add(location=c, scale=s)
    parts.append(C.active_object)
    C.active_object.name = f'Part{i}'
for o in parts:
    o.select_set(True)
st.kind = 'MECHA'
r = bpy.ops.mch.rig_make()
arm = C.active_object
before = {o.name: o.matrix_world.copy() for o in parts}
check('Mecha: one bone per part (+ root), each part on its bone, nothing moved',
      r == {'FINISHED'} and len(arm.data.bones) == 4 and all(o.parent is arm and o.parent_type == 'BONE' for o in parts)
      and all((before[o.name].translation - o.matrix_world.translation).length < 1e-5 for o in parts))
C.view_layer.update()
rg.set_pivot(C, parts[1], Vector((0, 0, 1.0)))
C.view_layer.update()
check('setting a joint does not move the part', (parts[1].matrix_world.translation - before['Part1'].translation).length < 1e-4)
for o in parts[1:]:
    o.select_set(True)
parts[1].select_set(True)
for o in list(C.selected_objects):
    o.select_set(False)
parts[2].select_set(True); parts[1].select_set(True); C.view_layer.objects.active = parts[1]
r = bpy.ops.mch.rig_link()
pb = arm.pose.bones['Part1']
pb.rotation_mode = 'XYZ'
pb.rotation_euler = (math.radians(90), 0, 0)
C.view_layer.update()
p1 = parts[1].matrix_world.translation
p2 = parts[2].matrix_world.translation
check(f'turning a part\'s bone: it turns about its joint (z 1.0: centre now {tuple(round(x, 2) for x in p1)}), the linked part follows '
      f'({tuple(round(x, 2) for x in p2)}), the base stays', r == {'FINISHED'} and abs(p1.z - 1.0) < 0.02 and abs(abs(p1.y) - 0.4) < 0.02
      and abs(p2.z - 1.0) < 0.05 and abs(abs(p2.y) - 1.1) < 0.05 and (parts[0].matrix_world.translation - before['Part0'].translation).length < 1e-5)

# 0.24.242 turn limits, a hatch, a piston
S.mch_rig.axis, S.mch_rig.lo, S.mch_rig.hi = 'X', -30.0, 60.0
arm.pose.bones['Part1'].rotation_euler = (0, 0, 0); C.view_layer.update(); before_lim = parts[2].matrix_world.translation.copy()
for o in list(C.selected_objects):
    o.select_set(False)
parts[2].select_set(True); C.view_layer.objects.active = parts[2]
pb2 = arm.pose.bones['Part2']; pb2.rotation_mode = 'XYZ'
r = bpy.ops.mch.rig_limit(kind='LIMIT')
pb2 = arm.pose.bones['Part2']
pb2.rotation_euler = (0.0, math.radians(120), 0.0)
C.view_layer.update()
def turned(ob, axis):
    m = ob.matrix_world.to_3x3()
    return m
ang = math.degrees(Matrix(pb2.matrix_channel.to_3x3()).to_euler().y)
lim = next(c for c in pb2.constraints if c.type == 'LIMIT_ROTATION')
check(f'Limit Turn: the part turns round X only (its other turns locked), 120 asked -> held at the limit',
      r == {'FINISHED'} and tuple(pb2.lock_rotation) == (True, False, True) and abs(math.degrees(lim.max_y) - 60) < 1e-4
      and abs(math.degrees(lim.min_y) + 30) < 1e-4)
dirn = arm.data.bones['Part2'].vector.normalized()
check('the bone points along the turn axis (world X)', abs(abs(dirn.x) - 1.0) < 1e-4)
p_before = parts[2].matrix_world.copy()
pb2.rotation_euler = (0, 0, 0)
C.view_layer.update()
check('limiting does not move the part', (parts[2].matrix_world.translation - before_lim).length < 1e-4)
S.mch_rig.hatch = 110.0
r = bpy.ops.mch.rig_limit(kind='HATCH')
lim = next(c for c in arm.pose.bones['Part2'].constraints if c.type == 'LIMIT_ROTATION')
check('Hatch: opens 110 degrees only (one way)', r == {'FINISHED'} and abs(math.degrees(lim.max_y - lim.min_y) - 110) < 1e-4
      and (abs(lim.min_y) < 1e-6 or abs(lim.max_y) < 1e-6))
r = bpy.ops.mch.rig_limit(kind='FREE')
check('Free: no limit again', r == {'FINISHED'} and not any(c.type == 'LIMIT_ROTATION' for c in arm.pose.bones['Part2'].constraints))
# piston: a cylinder on the base, a rod on an arm
fresh(); S = C.scene; st = S.mch_rig
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0.25), scale=(0.5, 0.5, 0.25)); base = C.active_object; base.name = 'Base'
bpy.ops.mesh.primitive_cube_add(location=(0, 1.0, 1.0), scale=(0.1, 1.0, 0.1)); boom = C.active_object; boom.name = 'Boom'
bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=0.6, location=(0, 0.3, 0.75)); cyl = C.active_object; cyl.name = 'Cyl'
bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=0.6, location=(0, 0.3, 1.25)); rod = C.active_object; rod.name = 'Rod'
for o in (base, boom, cyl, rod):
    o.select_set(True)
st.kind = 'MECHA'
bpy.ops.mch.rig_make()
arm = C.active_object
for o in list(C.selected_objects):
    o.select_set(False)
cyl.select_set(True); rod.select_set(True); C.view_layer.objects.active = rod
r = bpy.ops.mch.rig_piston()
for o in list(C.selected_objects):
    o.select_set(False)
rod.select_set(True); boom.select_set(True); C.view_layer.objects.active = boom
bpy.ops.mch.rig_link()
for o in list(C.selected_objects):
    o.select_set(False)
cyl.select_set(True); base.select_set(True); C.view_layer.objects.active = base
bpy.ops.mch.rig_link()
with rg._Edit(C, arm) as ebs:
    pass
pbm = arm.pose.bones['Boom']; pbm.rotation_mode = 'XYZ'
rb = arm.data.bones['Rod']
def line_err():
    C.view_layer.update()
    pc, pr = arm.pose.bones['Cyl'], arm.pose.bones['Rod']
    hc, hr = arm.matrix_world @ pc.head, arm.matrix_world @ pr.head
    dc = (arm.matrix_world.to_3x3() @ (pc.tail - pc.head)).normalized()
    dr = (arm.matrix_world.to_3x3() @ (pr.tail - pr.head)).normalized()
    return dc.angle((hr - hc).normalized()), dr.angle((hc - hr).normalized()), (hr - hc).length
a0 = line_err()
pbm.rotation_euler = (math.radians(-25), 0, 0)
a1 = line_err()
check(f'Piston: the rod slides in the cylinder, both in line when the arm turns (off-line {math.degrees(max(a1[:2])):.2f} deg; '
      f'length {a0[2]:.3f} -> {a1[2]:.3f})', r == {'FINISHED'} and max(a1[:2]) < math.radians(0.5) and abs(a1[2] - a0[2]) > 0.02)

# a hatch on a box: it opens outward, not into the box
fresh(); S = C.scene; st = S.mch_rig
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0.5), scale=(0.6, 0.6, 0.5)); boxo = C.active_object
bpy.ops.mesh.primitive_cube_add(location=(0, -0.3, 1.03), scale=(0.3, 0.3, 0.03)); hat = C.active_object
for o in (boxo, hat):
    o.select_set(True)
st.kind = 'MECHA'
bpy.ops.mch.rig_make()
arm = C.active_object
for o in list(C.selected_objects):
    o.select_set(False)
hat.select_set(True); C.view_layer.objects.active = hat
rg.set_pivot(C, hat, Vector((0, 0.0, 1.03)))
st.axis, st.hatch = 'X', 110.0
bpy.ops.mch.rig_limit(kind='HATCH')
ph = arm.pose.bones[hat[rg.PART_KEY]]
lim = next(c for c in ph.constraints if c.type == 'LIMIT_ROTATION')
ph.rotation_euler = (0, lim.max_y if abs(lim.max_y) > abs(lim.min_y) else lim.min_y, 0)
C.view_layer.update()
cz = hat.matrix_world.translation.z
check(f'the hatch opens outward - up off the box (its middle at z {cz:.2f}, the box top 1.0)', cz > 1.1)

# --- chain ---
fresh(); S = C.scene; st = S.mch_rig
bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=0.15, radius2=0.02, depth=2.0, location=(0, 0, 1.0))
tail = C.active_object
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.subdivide(number_cuts=12); bpy.ops.object.mode_set(mode='OBJECT')
st.kind, st.bones, st.jiggle, st.stiffness, st.damping = 'CHAIN', 6, True, 0.2, 0.2
r = bpy.ops.mch.rig_make()
arm = C.active_object
names = [b.name for b in arm.data.bones]
root = np.array(arm.matrix_world @ arm.data.bones[names[0]].head_local)
tipp = np.array(arm.matrix_world @ arm.data.bones[names[-1]].tail_local)
check(f'Chain: {len(names)} bones from the thick end (root z {root[2]:.2f}) to the thin end (tip z {tipp[2]:.2f}), the tail bound',
      r == {'FINISHED'} and len(names) == 6 and root[2] < 0.15 and tipp[2] > 1.85
      and any(m.type == 'ARMATURE' for m in tail.modifiers))
S.frame_start, S.frame_end = 1, 40
S.frame_set(1)
for f in range(2, 8):
    arm.location.x = 0.1 * (f - 1)
    S.frame_set(f)
C.view_layer.update()
pb = arm.pose.bones[names[-1]]
tip_world = arm.matrix_world @ pb.tail
straight = arm.matrix_world @ (arm.data.bones[names[-1]].tail_local)
check(f'Jiggle: moving the rig, the tip lags behind (by {straight.x - tip_world.x:.3f} m)', straight.x - tip_world.x > 0.02)
summary()
