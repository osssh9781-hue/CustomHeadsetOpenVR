"""0.24.183 Body Kit (user: "팔다리 허벅지 이런 거 분리해서 내가 각각 조절" / "이걸 이용해서 슬라이더로 체형이랑 다리 길이 이런
것도 변경하고 싶어" / "둘 다") and the sculpted muscles (user: "내가 하나짜리 근육이랑 두 개짜리 어깨 가슴 삼두 보내니까 사용해서
만들어 줘"): the user's two part-split bodies as kits - sliders for the whole body and for each part, poses at the joints,
parts swapped (the other body's, your own), Join; a part's muscles put on it with the user's sculpted shapes, moving
with the part's sliders.  Measured on the evaluated meshes."""
import math
import os
import shutil
import sys
import tempfile

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector  # noqa: E402

import mecha_lab
from mecha_lab import body_kit as bk, muscle_gen as mg, tool_state as ts, ui_tool_settings as uts  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
MY = tempfile.mkdtemp()
bk.MY_DIR[0] = MY                                   # (never the user's own folder)


def ev_verts(obs):
    dg = C.evaluated_depsgraph_get()
    out = []
    for o in obs:
        e = o.evaluated_get(dg)
        me = e.to_mesh()
        V = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', V)
        M = np.array(e.matrix_world)
        out.append(V.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3])
        e.to_mesh_clear()
    return np.concatenate(out)


def part(root, name):
    C.view_layer.update()                           # (the matrices as the sliders left them)
    return next(o for o in bk.parts_of(root) if bk.info(o)['name'] == name)


def centre(ob):
    V = ev_verts([ob])
    return V.mean(0)


# --- 1. the tool, the kits --------------------------------------------------------------------------------------------
row = ts.TOOL_BY_ID.get('BODYKIT')
check('Body Kit is a tool in the Creature group, its icon, its window', row is not None and
      row[5] == 'mecha.body_kit' and 'BODYKIT' in dict(ts.TOOL_GROUPS)['Creature'] and 'BODYKIT' in uts.DRAWERS and
      os.path.isfile(os.path.join(os.path.dirname(bk.__file__), 'icons', 'bodykit.png')))
hum = bk.load('human')
cre = bk.load('creature')
check('the human kit: torso (with the head), pelvis and both sides\' upper arms, forearms, hands, thighs, knees, shins, '
      'feet - 16 parts, light (under 70k faces)',
      len(hum) == 16 and {p['slot'] for p in hum.values()} == {'Torso', 'Pelvis', 'UpperArm', 'Forearm', 'Hand', 'Thigh',
                                                              'Knee', 'Shin', 'Foot'}
      and sum(len(p['N']) for p in hum.values()) < 70000, sum(len(p['N']) for p in hum.values()))
check('the creature kit: head, torso, pelvis, both sides\' arms, hands, thighs, knees, shins, feet - 15 parts',
      len(cre) == 15 and 'Head' in {p['slot'] for p in cre.values()} and sum(len(p['N']) for p in cre.values()) < 70000)
check('each part hangs on the one before it: the shin on the knee, the knee on the thigh, the thigh on the pelvis',
      hum['Shin.L']['parent'] == 'Knee.L' and hum['Knee.L']['parent'] == 'Thigh.L' and
      hum['Thigh.L']['parent'] == 'Pelvis' and hum['Hand.R']['parent'] == 'Forearm.R')
check('left and right mirror each other (pivots)', np.allclose(np.array(hum['Thigh.L']['pivot']) * (-1, 1, 1),
                                                                hum['Thigh.R']['pivot'], atol=1e-5))

# --- 2. a body in the scene ---------------------------------------------------------------------------------------------
S.mch_bodykit_new.kit = 'human'
S.mch_bodykit_new.height = 1.8
S.cursor.location = (0.0, 0.0, 0.0)
r = bpy.ops.mch.bodykit_add()
H = bk.root_of(C.active_object)
V = ev_verts(bk.parts_of(H))
check(f'Add Body: 16 parts standing on the cursor, 1.8 tall ({V[:, 2].min():.3f} .. {V[:, 2].max():.3f})',
      r == {'FINISHED'} and len(bk.parts_of(H)) == 16 and abs(V[:, 2].min()) < 1e-3 and abs(V[:, 2].max() - 1.8) < 0.01)
kp = H.mch_bodykit
knee0 = Vector(part(H, 'Knee.L').matrix_world.translation)
hip0 = H.matrix_world.translation.z - knee0.z
kp.legs = 1.3
V2 = ev_verts(bk.parts_of(H))
knee1 = Vector(part(H, 'Knee.L').matrix_world.translation)
hip1 = H.matrix_world.translation.z - knee1.z
check(f'Legs 1.3: taller ({V2[:, 2].max():.3f}), the feet still on the floor ({V2[:, 2].min():.4f}), hip to knee '
      f'{hip0:.3f} -> {hip1:.3f}', V2[:, 2].max() > 1.95 and abs(V2[:, 2].min()) < 1e-3 and hip1 > hip0 * 1.25)
kp.legs = 1.0
sh0 = part(H, 'UpperArm.L').matrix_world.translation.x
kp.shoulders = 1.3
sh1 = part(H, 'UpperArm.L').matrix_world.translation.x
check(f'Shoulders 1.3: the arms move out with them ({sh0:.3f} -> {sh1:.3f})', sh1 > sh0 + 0.02)
kp.shoulders = 1.0
w0 = np.ptp(ev_verts([part(H, 'Thigh.L')])[:, 0])
kp.build = 1.25
w1 = np.ptp(ev_verts([part(H, 'Thigh.L')])[:, 0])
check(f'Build 1.25: the thigh wider ({w0:.3f} -> {w1:.3f})', w1 > w0 * 1.12)
kp.build = 1.0
th = part(H, 'Thigh.L')
th.mch_bodypart.length = 1.2
check('Symmetry: a part\'s slider on the other side too', abs(part(H, 'Thigh.R').mch_bodypart.length - 1.2) < 1e-6)
th.mch_bodypart.length = 1.0
fa = part(H, 'UpperArm.L')
h0 = Vector(part(H, 'Hand.L').matrix_world.translation)
fa.mch_bodypart.bend = math.radians(60)
h1 = Vector(part(H, 'Hand.L').matrix_world.translation)
check(f'Bend 60 on the upper arm: the parts after it follow (the hand moved {(h1 - h0).length:.3f}, forward)',
      (h1 - h0).length > 0.05 and h1.y < h0.y)
fa.mch_bodypart.bend = 0.0
part(H, 'Forearm.L').rotation_euler = (math.radians(-50), 0.2, 0.1)
C.view_layer.objects.active = part(H, 'Forearm.L')
bpy.ops.mch.bodykit_mirror_pose()
e = part(H, 'Forearm.R').rotation_euler
check('Mirror Pose: the left\'s turn on the right, mirrored', abs(e.x - math.radians(-50)) < 1e-5 and
      abs(e.y + 0.2) < 1e-5 and abs(e.z + 0.1) < 1e-5)
bpy.ops.mch.bodykit_reset(what='POSE')
check('Reset Pose', all(Vector(o.rotation_euler).length < 1e-9 for o in bk.parts_of(H)))
# swap: the creature's shin on the human
sh = part(H, 'Shin.L')
C.view_layer.objects.active = sh
n0 = len(sh.data.polygons)
r = bpy.ops.mch.bodykit_swap(variant='creature:Shin.L')
L1 = np.ptp(ev_verts([sh]) @ np.array(bk._frame_of(bk.info(sh))[0]))
check(f'Swap Part: the creature\'s shin on the human (both sides - Symmetry), as long as the human\'s ({L1:.3f})',
      r == {'FINISHED'} and len(sh.data.polygons) != n0 and bk.info(sh)['variant'] == 'creature:Shin.L'
      and bk.info(part(H, 'Shin.R'))['variant'] == 'creature:Shin.L' and 0.2 < L1 < 0.6)
# your own part: a mesh over the part, used and saved
bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=0.4, location=tuple(centre(part(H, 'Forearm.L'))))
mine = C.active_object
fo = part(H, 'Forearm.L')
for o in C.selected_objects:
    o.select_set(False)
mine.select_set(True)
fo.select_set(True)
C.view_layer.objects.active = fo
r = bpy.ops.mch.bodykit_use_mesh(save=True, name='Tube Forearm')
check('Use Selected Mesh: your mesh in the forearm\'s place (it moves with it), saved as your part',
      r == {'FINISHED'} and len(fo.data.polygons) == len(mine.data.polygons) and
      os.path.isfile(os.path.join(MY, 'Forearm', 'Tube Forearm.npz')) and
      ('mine:Tube Forearm', 'My Tube Forearm') in bk.variants('Forearm'))

# --- 3. the sculpted muscles --------------------------------------------------------------------------------------------
tp = mg.templates()
check('the user\'s five sculpted muscles are in the add-on (light)', set(tp) == {'SINGLE', 'DOUBLE', 'TRICEPS', 'PEC',
                                                                               'DELTOID'}
      and all(len(t['N']) < 3500 for t in tp.values()))
th = part(H, 'Thigh.L')
C.view_layer.objects.active = th
r = bpy.ops.mch.bodykit_muscles(which='ALL')
mus = [o for o in S.objects if mg.is_muscle(o)]
names = sorted(o.name for o in mus)
check(f'Muscles on the thigh: front, back, inner, outer on both thighs (Symmetry) - each its own object on its part '
      f'({len(mus)})', r == {'FINISHED'} and len(mus) == 8 and all(o.parent.name.startswith('Body Thigh') for o in mus),
      names)
quad = next(o for o in mus if o.name == 'Thigh Quads.L')
check('the front one laid with the user\'s triceps shape (heads into a tendon): its faces, its points on the thigh',
      len(quad.data.polygons) == len(tp['TRICEPS']['N']) and mg.sculpt_of(quad.mch_muscle, 'LINE') == 'TRICEPS')
from mathutils.bvhtree import BVHTree  # noqa: E402
TV = ev_verts([th])
QV = ev_verts([quad])
dg = C.evaluated_depsgraph_get()
the = th.evaluated_get(dg)
tme = the.to_mesh()
bvh = BVHTree.FromPolygons([tuple(the.matrix_world @ v.co) for v in tme.vertices], [tuple(p.vertices) for p in tme.polygons])
the.to_mesh_clear()
d = np.array([bvh.find_nearest(Vector(p))[3] for p in QV[::7]])
check(f'... lying on the thigh (all its points within {d.max():.3f} of its surface)', d.max() < 0.08)
c0 = QV.mean(0)
th.mch_bodypart.length = 1.25
mg._BVH.clear()
bk._refit_now()                                     # (the timer, now)
QV2 = ev_verts([quad])
check(f'the thigh longer: its muscles laid again where its points went (moved {np.linalg.norm(QV2.mean(0) - c0):.3f})',
      np.linalg.norm(QV2.mean(0) - c0) > 0.01)
th.mch_bodypart.length = 1.0
# a chest fan on a ball: the user's shape between the three points
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32, location=(10, 0, 0))
ball = C.active_object


def on(theta, phi):
    return Vector((10 + math.sin(phi) * math.cos(theta), -math.cos(phi) * math.cos(theta), math.sin(theta)))


st = S.mch_muscle
st.style, st.shape, st.sculpt, st.preset = 'CREATURE', 'SCULPT', 'AUTO', 'PEC'
P3 = [on(0.35, -0.6), on(-0.15, -0.6), on(0.1, -0.2)]
pec, _m = mg.make(C, 'MUSCLE', [(ball.name, tuple(p), tuple((p - Vector((10, 0, 0))).normalized())) for p in P3])
PV = ev_verts([pec])
dmin = [float(np.min(np.linalg.norm(PV - np.array(p), axis=1))) for p in P3]
check(f'Chest (three points): the user\'s chest fan between them - a corner at each start point, its tendon at the '
      f'third ({", ".join(f"{x:.3f}" for x in dmin)})', len(pec.data.polygons) == len(tp['PEC']['N']) and
      max(dmin) < 0.08)
st.shape = 'STRANDS'
st.preset = 'SPINDLE'
sp, _m = mg.make(C, 'MUSCLE', [(ball.name, tuple(P3[0]), (0, -1, 0)), (ball.name, tuple(P3[2]), (0, -1, 0))])
check('Shape Strands: built from strands as before', mg.sculpt_of(sp.mch_muscle, 'LINE') is None and
      len(sp.data.polygons) != len(tp['SINGLE']['N']))

# --- 4. join ------------------------------------------------------------------------------------------------------------
C.view_layer.objects.active = H
for o in C.selected_objects:
    o.select_set(False)
H.select_set(True)
r = bpy.ops.mch.bodykit_join(remesh=False)
out = C.active_object
check('Join to One Mesh: one mesh as shaped (the kit hidden, kept)', r == {'FINISHED'} and out.name.startswith('Body')
      and not bk.is_part(out) and all(o.hide_get() for o in bk.parts_of(H)) and len(out.data.polygons) > 40000)

shutil.rmtree(MY, ignore_errors=True)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
