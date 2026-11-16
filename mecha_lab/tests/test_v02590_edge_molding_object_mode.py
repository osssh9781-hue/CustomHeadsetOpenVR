"""0.24.177 Edge Molding (user: "엣지 몰딩은 작동이 되긴 하는 거야?"): in the MECHA LAB tab it could not be used - its
buttons wanted Edit Mode, but there Tab goes to ZBrush and the window is hidden in Edit Mode, so a click only said
"Tab into Edit Mode" (the real window: tests/gui/round177_real_window.py).  Now in Object Mode:
- drag along a mesh: a molding along the line, laid on its surface (it stops where the line leaves the mesh, a line
  over two meshes: two pieces; back to where it started: a ring); it follows the mesh; its values live;
- click a part: along its edges - its open rim, else its sharp edges (Edge Angle); a smooth ball: told why not;
- a heavy part showing its Light Copy: laid on the part itself;
- "From Selected Faces / Edges" in Object Mode: what was picked in Edit Mode (a new mesh, all of it picked: told how)."""
import json
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Euler, Vector

import bmesh  # noqa: E402
import mecha_lab
from mecha_lab import core_geometry as cg, edge_molding as em, light_copies as lc, tool_state as ts  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)   # (looking +Y)


def px(x, z):
    return tuple(FRONT.to_screen(Vector((x, -5.0, z))))


def unselect():
    for o in C.selected_objects:
        o.select_set(False)
    C.view_layer.objects.active = None


def world(ob):
    C.view_layer.update()
    return np.array([tuple(ob.matrix_world @ v.co) for v in ob.data.vertices])


def non_manifold(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    n = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return n


check(f'the tool has its own Object Mode tool now ({ts.TOOL_BY_ID["MOLDING"][5]}); before: none',
      ts.TOOL_BY_ID['MOLDING'][5] == 'mecha.edge_molding')
bpy.ops.mesh.primitive_cube_add(size=2.0)
hull = C.active_object
hull.name = 'Hull'
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.subdivide(number_cuts=6)
bpy.ops.object.mode_set(mode='OBJECT')
unselect()
mp = S.mch_molding
mp.width, mp.height = 0.06, 0.03
# 1 a line across the front
ob, msg = em.perform_line(C, [px(x, 0.3 + 0.1 * math.sin(3 * x)) for x in np.linspace(-0.7, 0.7, 50)], FRONT)
P = world(ob)
ch = json.loads(ob.mch_molding.chains)
check(f'a line dragged across the front: a molding along it on the face (y {P[:, 1].min():.3f}..{P[:, 1].max():.3f}; '
      f'the face at -1, {mp.height} high), x {P[:, 0].min():.2f}..{P[:, 0].max():.2f}, one piece, closed tube - {msg}',
      len(ch) == 1 and not ch[0]['closed'] and P[:, 1].min() > -1.0 - mp.height - 1e-3 and P[:, 1].max() < -1.0 + 1e-3
      and P[:, 0].min() < -0.65 and P[:, 0].max() > 0.65 and non_manifold(ob) == 0 and 'follows' in msg)
check(f'it follows the hull (its child: {ob.parent and ob.parent.name}), picked, the window on it',
      ob.parent == hull and C.active_object == ob and em.active_molding(C) == ob)
n0 = len(ob.data.vertices)
bb0 = float(np.ptp(world(ob)[:, 2]))
ob.mch_molding.width = 0.15
bb1 = float(np.ptp(world(ob)[:, 2]))
check(f'its values live: Width 0.06 -> 0.15 (its height on the face {bb0:.3f} -> {bb1:.3f})', bb1 > bb0 + 0.08)
P0 = world(ob)
hull.location = (0.5, 0.0, 0.25)
P1 = world(ob)
check(f'the hull moved: the molding with it ({np.round((P1 - P0).mean(0), 4).tolist()})',
      np.abs(P1 - P0 - np.array([0.5, 0.0, 0.25])).max() < 1e-4)
hull.location = (0.0, 0.0, 0.0)
C.view_layer.update()
# 2 a ring
unselect()
ring = [px(0.5 * math.cos(t), -0.2 + 0.4 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 64, endpoint=False)]
ob2, msg2 = em.perform_line(C, ring, FRONT, closed=True)
ch2 = json.loads(ob2.mch_molding.chains)
check(f'drawn back to where it started: a ring (closed {[c["closed"] for c in ch2]}), a closed tube with no ends '
      f'({non_manifold(ob2)} open edges) - {msg2}', len(ch2) == 1 and ch2[0]['closed'] and non_manifold(ob2) == 0
      and 'ring' in msg2)
# 3 off the mesh, and over two meshes
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(2.5, 0.0, 0.0))
box = C.active_object
box.name = 'Box'
unselect()
ob3, msg3 = em.perform_line(C, [px(x, 0.0) for x in np.linspace(0.2, 3.6, 80)], FRONT)
ch3 = json.loads(ob3.mch_molding.chains)
xs = [(round(min(p[0] for p in c['pts']), 2), round(max(p[0] for p in c['pts']), 2)) for c in ch3]
ys = [round(c['pts'][0][1], 3) for c in ch3]
check(f'a line from the hull over the gap to the box and off it: two pieces, each on its own face (x {xs}, y {ys}), '
      f'nothing in the air - {msg3}', len(ch3) == 2 and xs[0][1] <= 1.0 + 1e-3 and xs[1][0] >= 2.0 - 1e-3
      and xs[1][1] <= 3.0 + 1e-3 and abs(ys[0] + 1.0) < 1e-3 and abs(ys[1] + 0.5) < 1e-3 and 'pieces' in msg3)
try:
    em.perform_line(C, [px(x, 2.5) for x in np.linspace(-1, 1, 20)], FRONT)
    err = None
except em.MoldingError as ex:
    err = str(ex)
check(f'a line in the air: told ({err})', err is not None and 'not on a mesh' in err)
for o in (ob, ob2, ob3):
    bpy.data.objects.remove(o)
# 4 click a part: its rim, its sharp edges
bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0.0, -1.5, 0.0), rotation=(math.pi / 2, 0, 0))
plate = C.active_object
plate.name = 'Plate'
unselect()
ob4, msg4 = em.perform_click(C, px(0.1, 0.1), FRONT)
ch4 = json.loads(ob4.mch_molding.chains)
P4 = world(ob4)
check(f'a plate (an open rim) clicked: a molding round its rim ({len(ch4)} ring, closed {ch4[0]["closed"]}, '
      f'{len(ch4[0]["pts"])} corners), on the plate (y {P4[:, 1].min():.3f}..{P4[:, 1].max():.3f}) - {msg4}',
      len(ch4) == 1 and ch4[0]['closed'] and len(ch4[0]['pts']) == 4 and 'rim' in msg4 and ob4.parent == plate
      and abs(P4[:, 0]).max() < 0.5 + mp.width)
bpy.data.objects.remove(ob4)
bpy.data.objects.remove(plate)
unselect()
ob5, msg5 = em.perform_click(C, px(2.5, 0.1), FRONT)
ch5 = json.loads(ob5.mch_molding.chains)
nrm = np.array([n for c in ch5 for n in c['nrm']])
check(f'a box clicked (no rim): along its sharp edges ({len(ch5)} pieces, the box has 12 edges), set on the edge '
      f'(normals between the two faces: |n| components {np.round(np.abs(nrm[0]), 3).tolist()}) - {msg5}',
      len(ch5) == 12 and 'sharp edges' in msg5 and np.all(np.sort(np.abs(nrm), axis=1)[:, 0] < 1e-6)
      and np.allclose(np.sort(np.abs(nrm), axis=1)[:, 1:], math.sqrt(0.5), atol=1e-3))
bpy.data.objects.remove(ob5)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, segments=32, ring_count=16, location=(5.0, 0.0, 0.0))
ballx = C.active_object
bpy.ops.object.shade_smooth()
unselect()
try:
    em.perform_click(C, px(5.0, 0.0), FRONT)
    err = None
except em.MoldingError as ex:
    err = str(ex)
check(f'a smooth ball clicked: no rim, no sharp edge - told ({err})', err is not None and 'Edge Angle' in err)
S.mch_molding.edge_angle = math.radians(5.0)
ob6, msg6 = em.perform_click(C, px(5.0, 0.0), FRONT)
check(f'... Edge Angle 5: its ring edges ({msg6[:60]}...)', 'sharp edges' in msg6 and len(ob6.data.polygons) > 0)
S.mch_molding.edge_angle = math.radians(30.0)
bpy.data.objects.remove(ob6)
bpy.data.objects.remove(ballx)
# 5 a heavy part showing its Light Copy: on the part itself
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=8, radius=1.2, location=(0.0, 4.0, 0.0))     # 327,680 faces
heavy = C.active_object
heavy.name = 'Heavy'
hull.hide_set(True)
box.hide_set(True)
lc.make_now(heavy, C)
lc._mod(heavy).show_viewport = True
unselect()
C.view_layer.update()
shown = len(heavy.evaluated_get(C.evaluated_depsgraph_get()).data.polygons)
ob7, _m7 = em.perform_line(C, [px(x, 0.2) for x in np.linspace(-0.8, 0.8, 60)], FRONT)
pts = np.array(json.loads(ob7.mch_molding.chains)[0]['pts'])
off = np.abs(np.linalg.norm(pts - np.array([0.0, 4.0, 0.0]), axis=1) - 1.2)
check(f'a heavy part showing its Light Copy ({shown:,} of {len(heavy.data.polygons):,} faces shown): the line on the '
      f'part itself (off its surface at most {off.max() * 1000:.2f} mm)', shown < 50_000 and off.max() < 5e-4)
bpy.data.objects.remove(ob7)
bpy.data.objects.remove(heavy)
hull.hide_set(False)
box.hide_set(False)
# 6 From Selected Faces in Object Mode: what was picked in Edit Mode
unselect()
hull.select_set(True)
C.view_layer.objects.active = hull
r_all = bpy.ops.mch.molding_create(source='FACES')            # (a new mesh: all of it picked)
bpy.ops.object.mode_set(mode='EDIT')
bm = bmesh.from_edit_mesh(hull.data)
for f in bm.faces:
    c = f.calc_center_median()
    f.select_set(c.z > 0.99 and abs(c.x) < 0.5 and abs(c.y) < 0.5)
bmesh.update_edit_mesh(hull.data)
bpy.ops.object.mode_set(mode='OBJECT')
r = bpy.ops.mch.molding_create(source='FACES')
fm = S.mch_molding_last
check(f'"From Selected Faces" in Object Mode: all of a mesh picked - told how ({r_all}); faces picked in Edit Mode, '
      f'back in Object Mode: a molding round them ({r}, {fm and fm.name}, {fm and non_manifold(fm)} open edges)',
      r_all == {'CANCELLED'} and r == {'FINISHED'} and fm is not None and fm.mch_molding.source == hull
      and non_manifold(fm) == 0 and len(json.loads(fm.mch_molding.chains)) == 1)
summary()
