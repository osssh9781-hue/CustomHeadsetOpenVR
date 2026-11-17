"""0.24.221 (user, after how ZBrush's BevelFlat / BevelArc brushes work was looked up: "점만 옮기기로 하자, 그리고 컷 버전도
옵션으로 만들어 줘"): the bevel tool's Method - Move Points (now the default): drag along an edge and the part's OWN
points near it are moved onto the bevel (a flat chamfer, or a round on the arc touching both faces); the mesh keeps
its faces.  Cut: the boolean bevel as before.  Measured on a dense box."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary

import bmesh  # noqa: E402
import mecha_lab
from mecha_lab import bool_bevel as bb, edge_runs as er  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
st = C.scene.mch_bool_bevel
check('the tool starts on Move Points; Cut is the other choice', st.method == 'MOVE'
      and [i.identifier for i in st.bl_rna.properties['method'].enum_items] == ['MOVE', 'CUT'])


def dense_box(n=40):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=n - 1, use_grid_fill=True)
    me = bpy.data.meshes.new('Box')
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new('Box', me)
    C.scene.collection.objects.link(ob)
    C.view_layer.objects.active = ob
    ob.select_set(True)
    er.clear()
    return ob


def co_of(ob):
    a = np.empty(len(ob.data.vertices) * 3)
    ob.data.vertices.foreach_get('co', a)
    return a.reshape(-1, 3)


W = 0.2
st.width, st.profile = W, 'CHAMFER'
ob = dense_box()
c0 = co_of(ob)
faces0, verts0 = len(ob.data.polygons), len(ob.data.vertices)
# the top front edge: y = -1, z = 1, along x - the whole of it (a click)
msg = bb.perform(C, ob, [(0.0, -1.0, 1.0)], whole=True)
c1 = co_of(ob)
moved = np.linalg.norm(c1 - c0, axis=1) > 1e-9
# (the corner the cut takes away: on the two faces within the Width - and, on the box's two end faces, inside it)
zone = (c0[:, 1] < -1 + W + 1e-6) & (c0[:, 2] > 1 - W - 1e-6) & ((c0[:, 2] - c0[:, 1]) > 2.0 - W - 1e-6)
# the chamfer plane: through (y, z) = (-1 + W, 1) and (-1, 1 - W):  z - y = 2 - W
on_plane = np.abs((c1[:, 2] - c1[:, 1]) - (2.0 - W))
check(f'Chamfer, the whole top front edge: {int(moved.sum()):,} points moved - the ones on the two faces within the Width '
      f'of the edge and the end faces\' corners; they now lie on the flat cut (worst {on_plane[moved].max():.2e} off its plane); nothing else moved',
      moved.sum() > 100 and on_plane[moved].max() < 1e-6 and not np.any(moved & ~zone)
      and np.abs(c1[~moved] - c0[~moved]).max() == 0, msg)
edge_pts = (np.abs(c0[:, 1] + 1) < 1e-6) & (np.abs(c0[:, 2] - 1) < 1e-6)
mid = np.array([-1 + W / 2, 1 - W / 2])
check(f'... the edge\'s own points are at the middle of the cut, a point half the Width in is half way to its end; the '
      f'mesh keeps its faces and points ({faces0:,} faces, {verts0:,} points)',
      np.abs(c1[edge_pts][:, 1:] - mid).max() < 1e-6 and len(ob.data.polygons) == faces0
      and len(ob.data.vertices) == verts0 and 'points moved' in msg)
bm = bmesh.new()
bm.from_mesh(ob.data)
vol = bm.calc_volume()
bm.free()
check(f'the box lost what a {W} chamfer takes off one edge: volume 8 -> {vol:.4f} (8 - W * W / 2 * 2 = {8 - W * W:.4f})',
      abs(vol - (8 - W * W)) < 0.02)

# a stretch of an edge: only that much, fading out at its ends
ob = dense_box()
c0 = co_of(ob)
bb.perform(C, ob, [(-0.5 + i * 0.1, -1.0, 1.0) for i in range(11)], reach=0.05)
c1 = co_of(ob)
mv = np.linalg.norm(c1 - c0, axis=1)
check(f'a drag over part of the edge (x -0.5 .. 0.5): only there (moved points span x {c0[mv > 1e-9, 0].min():.2f} .. '
      f'{c0[mv > 1e-9, 0].max():.2f}), full depth in the middle ({mv[edge_pts & (np.abs(c0[:, 0]) < 0.2)].max():.3f} = '
      f'{W / math.sqrt(2):.3f}), fading out over a Width at each end (at x 0.45: '
      f'{mv[edge_pts & (np.abs(c0[:, 0] - 0.45) < 0.01)].max():.3f})',
      c0[mv > 1e-9, 0].min() > -0.51 and c0[mv > 1e-9, 0].max() < 0.51
      and abs(mv[edge_pts & (np.abs(c0[:, 0]) < 0.2)].max() - W / math.sqrt(2)) < 1e-6
      and 0 < mv[edge_pts & (np.abs(c0[:, 0] - 0.45) < 0.01)].max() < W / math.sqrt(2) * 0.5)

# Round: on the arc touching both faces
st.profile = 'ROUND'
ob = dense_box()
c0 = co_of(ob)
bb.perform(C, ob, [(0.0, -1.0, 1.0)], whole=True)
c1 = co_of(ob)
moved = np.linalg.norm(c1 - c0, axis=1) > 1e-9
centre = np.array([-1 + W, 1 - W])                         # (a square corner: the arc's centre, radius W)
rad = np.linalg.norm(c1[moved][:, 1:] - centre, axis=1)
check(f'Round: the moved points lie on the arc of radius {W} touching both faces (radius {rad.min():.4f} .. {rad.max():.4f})',
      moved.sum() > 100 and abs(rad.min() - W) < 1e-6 and abs(rad.max() - W) < 1e-6)

# an edge loop (Shift + click): all four edges round the top face
st.profile = 'CHAMFER'
ob = dense_box()
c0 = co_of(ob)
msg = bb.perform(C, ob, [(0.0, -1.0, 1.0)], whole=True, loop=True, view=(0.0, 0.0, -1.0))
c1 = co_of(ob)
mv = np.linalg.norm(c1 - c0, axis=1) > 1e-9
sides_hit = [bool(np.any(mv & (np.abs(c0[:, 2] - 1) < 1e-6) & m)) for m in (c0[:, 1] < -0.9, c0[:, 1] > 0.9, c0[:, 0] < -0.9, c0[:, 0] > 0.9)]
check(f'Edge Loop: the click takes the whole loop round the top face (4 edges: {sides_hit})', all(sides_hit), msg)

# a mesh with nothing to move says so; Cut still cuts
st.profile = 'CHAMFER'
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=2.0)
cube = C.active_object
er.clear()
st.width = 0.2
try:
    bb.perform(C, cube, [(0.0, -1.0, 1.0)], whole=True)
    low = 'moved'
except bb.BevelError as ex:
    low = str(ex)
c = co_of(cube)
check(f'a plain cube (8 points): Move Points moves its two corner points onto the cut, or says the mesh is too coarse '
      f'- never a broken mesh ("{low[:60]}"), still 6 faces', len(cube.data.polygons) == 6 and np.all(np.isfinite(c)))
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=2.0)
cube = C.active_object
er.clear()
st.method = 'CUT'
n0 = len(cube.data.polygons)
msg = bb.perform(C, cube, [(0.0, -1.0, 1.0)], whole=True)
check(f'Method Cut: the boolean bevel as before ({n0} -> {len(cube.data.polygons)} faces)', len(cube.data.polygons) > n0
      and 'Boolean Bevel' in msg)
st.method = 'MOVE'
try:
    bb.perform(C, cube, [(0.0, -1.0, 1.0)], whole=True, remove=True)
    said = ''
except bb.BevelError as ex:
    said = str(ex)
check('Alt + click (take a bevel off) in Move Points: says Ctrl+Z does that', 'Ctrl+Z' in said)
summary()
