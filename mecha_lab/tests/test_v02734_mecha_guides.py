"""0.24.338 Rig > Mecha Guides (user: "메카 리그도 가이드 라인 그을 수 있게", "네임 말고 그냥 가이드로", "가이드 그리면 한
덩어리당 본 하나야 명심해"): lines through the parts' middles; ONE bone a part a line crosses; Leg / IK lines get IK."""
import bmesh  # noqa: F401  (the box helper uses it)
import json
import math

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import mecha_guides as mg, rigging as rg

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
src = open(__file__.replace('test_v02734_mecha_guides.py', 'test_v02733_mecha_named.py')).read()
exec(src[src.index('def box('):src.index('obs = [box(n, lo, hi)')])
parts = {}
for i, (n, lo, hi) in enumerate(BODY):             # noqa: F821  (no body names: Part_00 ...)
    if n == 'Armor_plate':
        continue
    parts[n] = box(f'Part_{i:02d}', lo, hi)          # noqa: F821
P = lambda *pts: np.array(pts, float)              # noqa: E731
L = [(P((0, 0, 0.95), (0, 0, 1.3), (0, 0, 1.65), (0, 0, 1.9), (0, 0, 1.4)), 'BODY'),   # (up and back down into the chest)
     (P((0.1, 0, 1.0), (0.11, 0, 0.7), (0.115, 0, 0.3), (0.115, -0.12, 0.05)), 'LEG'),
     (P((-0.1, 0, 1.0), (-0.11, 0, 0.7), (-0.115, 0, 0.3), (-0.115, -0.12, 0.05)), 'AUTO'),   # (ends on the ground)
     (P((0.2, 0, 1.5), (0.33, 0, 1.52), (0.35, 0, 1.3), (0.35, 0, 1.05), (0.35, 0, 0.88)), 'IK'),
     (P((-0.2, 0, 1.5), (-0.33, 0, 1.52), (-0.35, 0, 1.3), (-0.35, 0, 1.05), (-0.35, 0, 0.88)), 'BONES')]
for pts, kind in L:
    mg.add_line(C, pts, kind)
got = mg.lines()
check(f'the guide lines kept on a curve, with their kinds ({[g[1] for g in got]})',
      [g[1] for g in got] == ['BODY', 'LEG', 'AUTO', 'IK', 'BONES'])
for o in S.objects:
    o.select_set(o.type == 'MESH')
C.view_layer.objects.active = parts['Pelvis']
S.mch_rig.kind = 'MGUIDE'
S.mch_rig.seamless = False
r = bpy.ops.mch.rig_make()
arm = rg.rig_of(parts['Pelvis'])
B = arm.data.bones
deform = [b.name for b in B if b.use_deform and b.name != 'root']
names = {v.name: k for k, v in parts.items()}
check(f'Make Rig: ONE bone for each part a line crosses - 18 parts, 18 bones, none twice (the body line goes up and '
      f'back down through the chest: still one) ({r}; {len(deform)} bones)',
      r == {'FINISHED'} and sorted(deform) == sorted(o.name for o in parts.values()))
pn = lambda n: B[parts[n].name].parent.name if B[parts[n].name].parent else None   # noqa: E731
check('along each line the bones follow the parts: belly on pelvis, chest on belly, head on neck; the legs off the '
      'pelvis (the line starts in it), the arms off the chest',
      pn('몸통') == parts['Pelvis'].name and pn('Head') == parts['Neck'].name and pn('Thigh.L') == parts['Pelvis'].name
      and pn('Shin.L') == parts['Thigh.L'].name and pn('Foot.L') == parts['Shin.L'].name
      and pn('Shoulder.L') == parts['몸통'].name and pn('UpperArm.L') == parts['Shoulder.L'].name
      and pn('Hand.L') == parts['LeftForearm'].name)
kn = arm.matrix_world @ B[parts['Shin.L'].name].head_local
el = arm.matrix_world @ B[parts['LeftForearm'].name].head_local
check(f'joints where the line goes from part to part: knee at z 0.55 ({kn.z:.3f}), elbow at z 1.2 ({el.z:.3f})',
      abs(kn.z - 0.55) < 0.02 and abs(el.z - 1.2) < 0.02)
ik = {pb.name for pb in arm.pose.bones for c in pb.constraints if c.type == 'IK'}
want_ik = {parts['Shin.L'].name, parts['Calf.R'].name, parts['LeftForearm'].name}
check(f'IK: the Leg line, the Auto line ending on the ground, the IK arm - not the Plain arm ({sorted(names[n] for n in ik)})',
      ik == want_ik and set(json.loads(arm['mch_legs'])) == {parts['Foot.L'].name, parts['발.R'].name})
C.view_layer.update()
mw = {o.name: o.matrix_world.copy() for o in parts.values()}
pb = arm.pose.bones[parts['Foot.L'].name + '_ik']
import mathutils  # noqa: E402
M = pb.matrix.copy()
M.translation += mathutils.Vector((0, -0.1, 0.25))
pb.matrix = M
C.view_layer.update()
up = (parts['Foot.L'].matrix_world.translation - mw[parts['Foot.L'].name].translation).z
check(f'the leg IK works: its foot target up 0.25 - the foot part goes with it ({up:.3f})', up > 0.15)
# through the middle: the point under the mouse is half way through the part
hit = mg.through_part(C, [parts['몸통'], parts['Head']], (0, -5, 1.3), (0, 1, 0))
check(f'drawing: a view ray through the chest gives the chest\'s middle (y {hit[0][1]:.3f}), the chest part',
      hit is not None and abs(hit[0][1]) < 0.01 and hit[1].obj is parts['몸통'])
# a part hidden inside another (a neck post sunk into the chest): the part under the mouse when drawn decides, not a
# guess - the line drawn over the chest there gives the chest, not the post inside it
for o in list(S.objects):
    bpy.data.objects.remove(o)
chest = box('Chest', (-0.3, -0.2, 1.0), (0.3, 0.2, 1.5))   # noqa: F821
post = box('Post', (-0.05, -0.05, 1.1), (0.05, 0.05, 1.7))  # noqa: F821
head = box('Head', (-0.12, -0.12, 1.7), (0.12, 0.12, 1.95))  # noqa: F821
mg.drop_line('ALL')
pts, own = [], []
for z in np.linspace(1.05, 1.9, 60):
    h_ = mg.through_part(C, [chest, post, head], (0, -5, z), (0, 1, 0))
    if h_ is not None:
        pts.append(h_[0])
        own.append(h_[1].name)
mg.add_line(C, np.array(pts), 'BODY', own)
arm2, rep2 = mg.build(C, [chest, post, head], mg.lines(), False)
check(f'a part inside another: the drawn line\'s own parts decide - chest, then the post where it shows above the '
      f'chest, then the head, one bone each ({rep2["bones"]}, {rep2["parent"]})',
      rep2['bones'] == ['Chest', 'Post', 'Head'] and rep2['parent'] == {'Chest': None, 'Post': 'Chest', 'Head': 'Post'})
# 0.24.339 (the user's spider: ONE object of 19 loose pieces) each loose piece of an object is a part of its own - one
# bone each - and the object stays one object, each piece's points wholly on its own bone
for o in list(S.objects):
    if o.type == 'MESH' or o.type == 'ARMATURE':
        bpy.data.objects.remove(o)
mg.drop_line('ALL')
a1 = box('A', (-0.3, -0.3, 0.0), (0.3, 0.3, 0.3))          # noqa: F821
a2 = box('B', (0.3, -0.05, 0.1), (0.9, 0.05, 0.2))         # noqa: F821
a3 = box('C', (0.9, -0.05, 0.1), (1.5, 0.05, 0.2))         # noqa: F821
for o in (a1, a2, a3):
    o.select_set(True)
C.view_layer.objects.active = a1
with C.temp_override(active_object=a1, selected_objects=[a1, a2, a3], selected_editable_objects=[a1, a2, a3]):
    bpy.ops.object.join()
one = C.view_layer.objects.active
pcs = mg.pieces_of([one])
pts, own = [], []
for x in np.linspace(-0.25, 1.45, 60):
    h_ = mg.through_part(C, [one], (x, 0, 5), (0, 0, -1), pcs)
    if h_ is not None:
        pts.append(h_[0])
        own.append(h_[1].name)
mg.add_line(C, np.array(pts), 'BONES', own)
arm3, rep3 = mg.build(C, [one], mg.lines(), False)
vg = {g.name for g in one.vertex_groups}
w_ok = all(len(v.groups) == 1 and v.groups[0].weight == 1.0 for v in one.data.vertices)
pb_ = arm3.pose.bones[rep3['bones'][2]]
pb_.rotation_mode = 'XYZ'
pb_.rotation_euler = (0, 0, 0.8)
C.view_layer.update()
ev = one.evaluated_get(C.evaluated_depsgraph_get()).to_mesh()
moved = [i for i in range(len(one.data.vertices)) if (ev.vertices[i].co - one.data.vertices[i].co).length > 1e-4]
one.evaluated_get(C.evaluated_depsgraph_get()).to_mesh_clear()
last = max(pcs, key=lambda pc: pc.V.mean(0)[0])
tip = set(last.verts)
check(f'one object of 3 loose pieces: 3 parts, 3 bones ({rep3["bones"]}), each piece wholly on its own bone, the '
      f'object still one object; turn the last bone - only the last piece moves ({len(moved)} points moved)',
      len(pcs) == 3 and len(rep3['bones']) == 3 and vg >= set(rep3['bones']) and w_ok
      and any(m.type == 'ARMATURE' for m in one.modifiers) and set(moved) == tip and len(tip) == 8)
summary()
