"""0.24.259 (user: "얼굴 눈, 턱도 내가 그려서 - 눈은 동그랗게, 입은 입 경계를 따라, 혀는 뼈, 턱도 IK" / "손가락 리깅 - 한 번에 오므리고
펼 수 있게"): guide kinds Eye (a circle on the skin: an eye bone looking at one shared target, the skin round it on
it), Mouth (along the lips: lip bones, the lower ones on the jaw), Finger (3 bones per finger, Finger Curl / Spread
drive them all at once)."""
import json

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector

import mecha_lab
import kaiju_mesh as km
from mecha_lab import rig_guides as rgd, rigging as rg  # noqa: E402

mecha_lab.register(); fresh()
C = bpy.context
S = C.scene
ob = km.make(C)
K = {k: np.array(v, float) for k, v in km.SKELETON.items()}


def line(*pts, n=8):
    P = [np.array(pts[0], float)]
    for a, b in zip(pts, pts[1:]):
        for t in np.linspace(0, 1, n + 1)[1:]:
            P.append(np.array(a, float) * (1 - t) + np.array(b, float) * t)
    return np.array(P)


def on_skin(x, z):
    """The point of the skin seen from the front (-Y) at (x, z)."""
    Mi = ob.matrix_world.inverted()
    hit, loc, _n, _i = ob.ray_cast(Mi @ Vector((x, -5.0, z)), Vector((0, 1, 0)))
    return np.array(tuple(ob.matrix_world @ loc)) if hit else None


hc = K['head']
eye = lambda sx: np.array([on_skin(hc[0] + sx + 0.06 * np.cos(a), hc[2] + 0.05 + 0.06 * np.sin(a)) for a in np.linspace(0, 2 * np.pi, 24)])
mouth = np.array([on_skin(hc[0] + x, hc[2] - 0.1 - 0.04 * np.cos(x / 0.12 * np.pi / 2)) for x in np.linspace(-0.12, 0.12, 16)])
plan = [('BODY', line(K['pelvis'], K['chest'], K['neck'], K['head'])),
        ('IK', line(K['head'] + np.array([0, 0.05, 0.0]), K['head'] + np.array([0, -0.2, -0.17]))),     # (the jaw)
        ('BONES', line(K['head'] + np.array([0, 0.0, -0.08]), K['head'] + np.array([0, -0.17, -0.1]))),  # (the tongue)
        ('EYE', eye(-0.09)), ('EYE', eye(0.09)), ('MOUTH', mouth)]
check('eyes and mouth drawn on the skin (every point found)', all(p is not None for _k, P in plan for p in P))
for k_, P in plan:
    rgd.add_stroke(C, ob, P, k_)
for o in list(C.selected_objects):
    o.select_set(False)
ob.select_set(True); C.view_layer.objects.active = ob
S.mch_rig.kind, S.mch_rig.bind = 'GUIDE', True
r = bpy.ops.mch.rig_make()
arm = C.active_object
bn = arm.data.bones
eyes = [b.name for b in bn if b.name.startswith('eye.')]
lips = [b.name for b in bn if b.name.startswith('lip.')]
check(f'Make Rig: {len(eyes)} eye bones, {len(lips)} lip bones, an eyes target', r == {'FINISHED'} and len(eyes) == 2
      and 4 <= len(lips) <= 12 and 'eyes_target' in bn)
C.view_layer.update()
still = max((pb.matrix.to_translation() - pb.bone.matrix_local.to_translation()).length for pb in arm.pose.bones)
d0 = {e: (arm.pose.bones[e].matrix.col[1].xyz.copy()) for e in eyes}
arm.pose.bones['eyes_target'].location = (0.3, 0, 0)
C.view_layer.update()
turned = min((arm.pose.bones[e].matrix.col[1].xyz - d0[e]).length for e in eyes)
arm.pose.bones['eyes_target'].location = (0, 0, 0)
check(f'the eyes look at the target (moved it: both eyes turned {turned:.2f}), rest pose still ({still * 1000:.1f} mm)',
      turned > 0.05 and still < 0.005)
g = ob.vertex_groups.get(eyes[0])
specs = {n: (np.array(c), r_) for n, c, r_ in json.loads(arm['mch_face_w'])}
c, r_ = specs[eyes[0]]
M = np.array(ob.matrix_world)
inside = [v for v in ob.data.vertices if np.linalg.norm(np.array(M[:3, :3] @ np.array(v.co) + M[:3, 3]) - c) < 0.4 * r_]
w = [next((ge.weight for ge in v.groups if ge.group == g.index), 0.0) for v in inside] if g else []
check(f'the skin inside the eye circle is on the eye bone ({len(inside)} points, weight {np.mean(w) if w else 0:.2f})',
      len(inside) > 0 and np.mean(w) > 0.9)
low = min(lips, key=lambda n: bn[n].head_local.z)
high = max(lips, key=lambda n: bn[n].head_local.z)
jaw = next(b.name for b in bn if any(c_.type == 'IK' for c_ in arm.pose.bones[b.name].constraints))
check(f'the lower lip hangs on the jaw ({low} on {bn[low].parent.name}, the jaw IK on {jaw}); the upper on the head ({bn[high].parent.name})',
      bn[low].parent.name.split('.')[0] == jaw.split('.')[0] and bn[high].parent.name.split('.')[0] != jaw.split('.')[0])

# fingers: a hand with four fingers
fresh()
parts = []
bpy.ops.mesh.primitive_cylinder_add(radius=0.25, depth=1.6, location=(0, 0, 1.2)); parts.append(C.active_object)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0.0, -0.25, 0.35), scale=(0.5, 0.15, 0.4)); parts.append(C.active_object)
for i, x in enumerate((-0.33, -0.11, 0.11, 0.33)):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.07, depth=0.7, location=(x, -0.25, -0.15)); parts.append(C.active_object)
for p in parts:
    p.select_set(True)
C.view_layer.objects.active = parts[0]
bpy.ops.object.join()
hand = C.active_object; hand.name = 'Hand'
m = hand.modifiers.new('V', 'REMESH'); m.mode = 'VOXEL'; m.voxel_size = 0.03
bpy.ops.object.convert(target='MESH')
fl = [('BODY', line((0, 0, 2.0), (0, 0, 0.9), (0, -0.25, 0.35)))]
for x in (-0.33, -0.11, 0.11, 0.33):
    fl.append(('FINGER', line((x, -0.25, 0.15), (x, -0.25, -0.45))))
for k_, P in fl:
    rgd.add_stroke(C, hand, P, k_)
for o in list(C.selected_objects):
    o.select_set(False)
hand.select_set(True); C.view_layer.objects.active = hand
S = C.scene
S.mch_rig.kind, S.mch_rig.bind = 'GUIDE', True
r = bpy.ops.mch.rig_make()
arm = C.active_object
fing = sorted({b.name.split('.')[0] for b in arm.data.bones if b.name.startswith('finger')})


def tip(f):
    e = arm.evaluated_get(C.evaluated_depsgraph_get())        # (the drivers work on the evaluated pose)
    return np.array(e.matrix_world @ e.pose.bones[f + '.03'].tail)
C.view_layer.update()
tips0 = {f: tip(f) for f in fing}
arm['mch_curl'] = 1.0
arm.update_tag()
C.view_layer.update()
tips1 = {f: tip(f) for f in fing}
moved = [float(np.linalg.norm(tips1[f] - tips0[f])) for f in fing]
check(f'Finger: {len(fing)} fingers of 3 bones on the hand; Finger Curl 1 curls them all at once '
      f'(tips moved {min(moved) * 100:.0f}-{max(moved) * 100:.0f} cm, all the same way)',
      r == {'FINISHED'} and len(fing) == 4 and min(moved) > 0.15
      and all(np.dot(tips1[f] - tips0[f], tips1[fing[0]] - tips0[fing[0]]) > 0 for f in fing))
arm['mch_curl'] = 0.0
arm['mch_spread'] = 1.0
arm.update_tag()
C.view_layer.update()
tips2 = {f: tip(f) for f in fing}
gap0 = abs(tips0[fing[-1]][0] - tips0[fing[0]][0]); gap2 = abs(tips2[fing[-1]][0] - tips2[fing[0]][0])
arm['mch_spread'] = 0.0
arm.update_tag()
C.view_layer.update()
back = max(float(np.linalg.norm(tip(f) - tips0[f])) for f in fing)
check(f'Finger Spread 1 fans them out (outer tips {gap0 * 100:.0f} -> {gap2 * 100:.0f} cm apart); 0 puts them back ({back * 1000:.1f} mm)',
      gap2 > gap0 + 0.1 and back < 1e-3)
summary()
