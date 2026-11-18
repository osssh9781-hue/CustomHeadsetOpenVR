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
