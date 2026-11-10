"""0.24.130 (user: "지브러시에서 불러올 때 너무 오래 걸리고 블렌더에서 다이나 메쉬 하는 것도 엄청 오래 걸려")
  1. DynaMesh: ``prepare`` reads the mesh with numpy first and skips the bmesh pass when nothing needs fixing (measured:
     11 s -> 0.8 s on a million points); open / flipped / loose meshes still go the old way.  ``cleanup`` finds the
     parts with a numpy union-find (2.7 s -> 0.3 s).
  2. ZBrush send: the OBJ carries no normals (ZBrush ignores them; half the file), UVs only when there are any,
     "Send: Max Points" Fast-Decimates the temporary copy, the report counts the points and warns above 2 M."""
import inspect
import os
import tempfile

from _harness import bpy, check, cube, fresh, summary
import bmesh  # noqa: E402
import numpy as np  # noqa: E402

import mecha_lab
from mecha_lab import dynamesh_fix as dfx, fast_decimate as fd, zbrush_bridge as zb  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene


def select_only(ob):
    for o in bpy.data.objects:
        o.select_set(False)
    ob.select_set(True)
    C.view_layer.objects.active = ob


# --- 1. the clean mesh: nothing to prepare, no bmesh pass -------------------------------------------------------------
part = cube('Part', size=2.0)
select_only(part)
part.data.remesh_voxel_size = mecha_lab.voxel_for_points(C, part, 60000)
bpy.ops.object.voxel_remesh()
me = part.data
nv0, nf0 = len(me.vertices), len(me.polygons)
d = dfx.quick_diag(me)
check('a voxel-remeshed part reads clean with numpy (no loose / boundary / flipped edges)', d == {'loose': 0, 'boundary': 0, 'nonman': 0, 'flipped': 0}
      and dfx.is_remesh_safe(me), (d, nv0))
done = dfx.prepare(me, 0.02)
check('prepare on it: nothing done, the mesh untouched (the fast path)', done == dict(merged=0, flipped=0, holes=0, solidified=False, loose=0)
      and (len(me.vertices), len(me.polygons)) == (nv0, nf0))
# an open sheet still gets solidified
sheet = cube('Sheet', size=1.0)
bm = bmesh.new()
bm.from_mesh(sheet.data)
bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.normal.z > 0.5], context='FACES')
bm.to_mesh(sheet.data)
bm.free()
d2 = dfx.quick_diag(sheet.data)
done2 = dfx.prepare(sheet.data, 0.02)
check('an open box: numpy sees the boundary, prepare goes the old way (hole capped / sheet handled)', d2['boundary'] == 4
      and (done2['holes'] > 0 or done2['solidified']) and dfx.is_remesh_safe(sheet.data), (d2, done2))
# a flipped face
flip = cube('Flip', size=1.0)
bm = bmesh.new()
bm.from_mesh(flip.data)
bm.faces.ensure_lookup_table()
bmesh.ops.reverse_faces(bm, faces=[bm.faces[0]])
bm.to_mesh(flip.data)
bm.free()
d3 = dfx.quick_diag(flip.data)
done3 = dfx.prepare(flip.data, 0.02)
check('one face flipped: numpy counts its 4 edges, prepare makes the normals consistent', d3['flipped'] == 4 and done3['flipped'] == 4
      and dfx.quick_diag(flip.data)['flipped'] == 0, (d3, done3))
# a loose point
loose = cube('Loose', size=1.0)
bm = bmesh.new()
bm.from_mesh(loose.data)
bm.verts.new((5.0, 5.0, 5.0))
bm.to_mesh(loose.data)
bm.free()
d4 = dfx.quick_diag(loose.data)
done4 = dfx.prepare(loose.data, 0.02)
check('a loose point: numpy sees it, prepare drops it', d4['loose'] == 1 and done4['loose'] == 1 and len(loose.data.vertices) == 8)
# --- components / cleanup ---------------------------------------------------------------------------------------------
two = cube('Two', size=2.0)
bm = bmesh.new()
bm.from_mesh(two.data)
bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=19, use_grid_fill=True)
bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.1)
bm.to_mesh(two.data)
bm.free()
labels, n = dfx.components(two.data)
bm = bmesh.new()
bm.from_mesh(two.data)
n_bm = len(dfx._parts(bm))
bm.free()
sizes = sorted(np.bincount(labels))
check('components (numpy union-find) finds the two parts like the bmesh walk, with their sizes', n == 2 and n_bm == 2
      and sizes == [12, 2402], (n, n_bm, sizes))
nf_before = len(two.data.polygons)
dropped = dfx.cleanup(two.data)
check('cleanup drops the tiny part (under 2 % of the faces) and keeps the big one', dropped == 1 and len(two.data.polygons) == nf_before - 20
      and dfx.components(two.data)[1] == 1)
check('wired: dynamesh prepare / cleanup use the numpy paths first', 'is_remesh_safe(me)' in inspect.getsource(dfx.prepare)
      and 'components(me)' in inspect.getsource(dfx.cleanup))

# --- 2. the ZBrush send: a lighter OBJ ---------------------------------------------------------------------------------
tmpdir = tempfile.mkdtemp(prefix='mch_zb_')
S.mch_zbrush.exchange_dir = tmpdir
S.mch_zbrush.send_max_points = 0
select_only(part)
folder, sent = zb.send_objects(C, [part], S.mch_zbrush)
files = [f for f in os.listdir(folder) if f.endswith('.obj')]
txt = open(os.path.join(folder, files[0]), 'r', errors='replace').read()
n_v = txt.count('\nv '); n_vn = txt.count('\nvn '); n_vt = txt.count('\nvt ')
check('the sent OBJ has the points but no normals and no UVs (none on the part); the report counts the points',
      sent == ['Part'] and n_v == nv0 and n_vn == 0 and n_vt == 0 and zb.SEND_POINTS[0] == nv0, (n_v, n_vn, n_vt, zb.SEND_POINTS[0]))
# Send: Max Points - the copy is decimated, the part itself is not
S.mch_zbrush.send_max_points = 5000
folder, sent = zb.send_objects(C, [part], S.mch_zbrush)
txt = open(os.path.join(folder, files[0]), 'r', errors='replace').read()
n_v2 = txt.count('\nv ')
if fd.available():
    check('Send: Max Points 5,000 on a 60 k part: the file carries about that many points, the part keeps its own',
          n_v2 <= 6500 and len(part.data.vertices) == nv0 and zb.SEND_POINTS[0] == n_v2 and zb.SEND_NOTES and 'sent with' in zb.SEND_NOTES[0],
          (n_v2, nv0, zb.SEND_NOTES))
else:
    check('Send: Max Points without the Fast Decimate engine: sent as is with a note', n_v2 == nv0 and zb.SEND_NOTES and 'not available' in zb.SEND_NOTES[0],
          (n_v2, zb.SEND_NOTES))
S.mch_zbrush.send_max_points = 0
src = inspect.getsource(zb.MCH_OT_zbrush_send.execute)
check('the send report names the points and warns above 2 M points when no cap is set', 'HEAVY_POINTS' in src and zb.HEAVY_POINTS == 2000000
      and 'export_normals=False' in inspect.getsource(zb.send_objects))
summary()
