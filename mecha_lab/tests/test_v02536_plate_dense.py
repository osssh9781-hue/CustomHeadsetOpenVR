"""0.24.131 (user: "다이나메쉬 한 메쉬 위에 크리처 플레이트나 아머 플레이트 하면 ... 개 오래 걸려") Plates on a dense body:
the target BVH and the surround faces are read with numpy (no Python loop over a million points / faces) and the BVH is
cached per target for a short while (a live plate's sliders rebuild from the same surface).  The ZBrush exports carry
no UVs at all (user: never used)."""
import inspect
import os
import tempfile
import time

from _harness import bpy, check, cube, fresh, summary
import bmesh  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Quaternion, Vector  # noqa: E402

import mecha_lab
from mecha_lab import armor_plate as ap, core_geometry as cg, creature_plate as cp, zbrush_bridge as zb  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion())


def select_only(ob):
    for o in bpy.data.objects:
        o.select_set(False)
    ob.select_set(True)
    C.view_layer.objects.active = ob


def surround_py(verts_world, polys, inv, lo, hi):
    """The 0.24.130 Python version (the reference)."""
    keep = []
    for poly in polys:
        for i in poly:
            p = verts_world[i]
            if all(lo[k] <= p[k] <= hi[k] for k in range(3)):
                keep.append(poly)
                break
    vmap, coords, faces = {}, [], []
    for poly in keep:
        idx = []
        for i in poly:
            if i not in vmap:
                vmap[i] = len(coords)
                coords.append(inv @ Vector(verts_world[i]))
            idx.append(vmap[i])
        faces.append(idx)
    return coords, faces


# --- the BVH: numpy world points, face lists, a cache ----------------------------------------------------------------
bpy.ops.mesh.primitive_uv_sphere_add(radius=2.0, segments=48, ring_count=24, location=(0.5, 0.0, 0.0))
ball = C.active_object
ball.name = 'Ball'
bvh, wv, faces = ap._target_bvh(C, ball)
hit = bvh.ray_cast(Vector((0.5, 0.0, 10.0)), Vector((0.0, 0.0, -1.0)))
check('_target_bvh: numpy world points (N x 3), faces as index lists, the BVH in world space (a ray from above hits the top)',
      isinstance(wv, np.ndarray) and wv.shape == (len(ball.data.vertices), 3) and len(faces) == len(ball.data.polygons)
      and faces[0] == list(ball.data.polygons[0].vertices) and hit[0] is not None and abs(hit[0].z - 2.0) < 1e-3
      and abs(wv[:, 0].mean() - 0.5) < 1e-3, (wv.shape, len(faces), hit[0]))
bvh2, _w, _f = ap._target_bvh(C, ball)
check('... the second call within the TTL is the cached BVH (the same object)', bvh2 is bvh)
ball.location.x = 1.5
C.view_layer.update()
bvh3, wv3, _f = ap._target_bvh(C, ball)
hit3 = bvh3.ray_cast(Vector((1.5, 0.0, 10.0)), Vector((0.0, 0.0, -1.0)))
check('... moving the target: a new BVH at the new place', bvh3 is not bvh and hit3[0] is not None and abs(wv3[:, 0].mean() - 1.5) < 1e-3)
ball.data.vertices[0].co.z += 0.1
bvh4 = ap._target_bvh(C, ball)[0]
check('... editing a point of the target: a new BVH too (the checksum)', bvh4 is not bvh3)
# surround: numpy == the Python reference, on a mixed mesh (quads, triangles, an n-gon)
mix = cube('Mix', size=2.0, loc=(0, 5, 0))
bm = bmesh.new()
bm.from_mesh(mix.data)
bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=3, use_grid_fill=True)
bm.faces.ensure_lookup_table()
bmesh.ops.triangulate(bm, faces=bm.faces[:10])
bmesh.ops.dissolve_faces(bm, faces=bm.faces[-4:])
bm.to_mesh(mix.data)
bm.free()
mix.rotation_euler = (0.3, 0.2, 0.1)
C.view_layer.update()
bvh_m, wv_m, faces_m = ap._target_bvh(C, mix)
inv = mix.matrix_world.inverted_safe()
lo, hi = Vector((-0.4, 4.3, -0.4)), Vector((0.9, 5.9, 0.9))
me_np = ap.surround_mesh(wv_m, faces_m, inv, lo, hi)
co_py, f_py = surround_py([Vector(v) for v in wv_m], [list(q) for q in faces_m], inv, lo, hi)
same_count = len(me_np.polygons) == len(f_py) and 0 < len(f_py) < len(faces_m)
co_np = sorted(tuple(round(c, 4) for c in v.co) for v in me_np.vertices)
co_ref = sorted(tuple(round(c, 4) for c in v) for v in co_py)
check('surround_mesh (numpy) keeps the same faces and points as the Python version on a mixed quad / tri / n-gon mesh',
      same_count and co_np == co_ref and sorted(len(p.vertices) for p in me_np.polygons) == sorted(len(f) for f in f_py),
      (len(me_np.polygons), len(f_py), len(faces_m)))
bpy.data.meshes.remove(me_np)
# the legacy call (lists of Vectors + tuples) still works
me_legacy = ap.surround_mesh([Vector(v) for v in wv_m], [tuple(q) for q in faces_m], inv, lo, hi)
check('... and still takes lists of Vectors / tuples (other callers)', len(me_legacy.polygons) == len(f_py))
bpy.data.meshes.remove(me_legacy)

# --- plates on a dense (voxel remeshed) body ---------------------------------------------------------------------------
for o in (ball, mix):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_uv_sphere_add(radius=3.0, segments=64, ring_count=32)
body = C.active_object
body.name = 'Body'
select_only(body)
body.data.remesh_voxel_size = mecha_lab.voxel_for_points(C, body, 150000)
bpy.ops.object.voxel_remesh()
n_body = len(body.data.vertices)
loop = [(450, 460), (550, 460), (550, 540), (450, 540)]
t = time.perf_counter()
msg = ap.perform_plate(C, [loop], TOP)
t1 = time.perf_counter() - t
plate = C.active_object
t = time.perf_counter()
msg2 = ap.perform_plate(C, [[(x + 30, y - 20) for x, y in loop]], TOP)
t2 = time.perf_counter() - t
check(f'Armor Plate on a {n_body:,}-point DynaMesh body: made, and the second one (cached BVH) at least as fast',
      'Armor plate' in msg and 'Armor plate' in msg2 and plate.mch_extract.source == body and t2 <= t1 * 1.2 + 0.05, (round(t1, 2), round(t2, 2)))
S.mch_plate.spacing = 60
ok_rebuild = ap.rebuild_plate(C, plate, 60)
check('... a live plate rebuilds (Face Size changed) from the cached surface', ok_rebuild and len(plate.data.polygons) > 0)
t = time.perf_counter()
msgc = cp.perform(C, [[(400, 400), (480, 400), (480, 470), (400, 470)]], TOP)
tc = time.perf_counter() - t
check(f'Creature Plate on the same body: made ({tc:.2f} s)', 'Creature plate' in str(msgc) and C.active_object.mch_cplate.live)
check('timing: a plate on 150 k points well under a second each here', t1 < 1.5 and t2 < 1.0 and tc < 1.5, (t1, t2, tc))

# --- the ZBrush export: no UVs at all ---------------------------------------------------------------------------------
tmpdir = tempfile.mkdtemp(prefix='mch_zb_')
S.mch_zbrush.exchange_dir = tmpdir
S.mch_zbrush.send_max_points = 0
part = cube('UVPart', size=1.0, loc=(10, 0, 0))
part.data.uv_layers.new(name='UVMap')
select_only(part)
folder, sent = zb.send_objects(C, [part], S.mch_zbrush)
txt = open(os.path.join(folder, [f for f in os.listdir(folder) if f.endswith('.obj')][0]), errors='replace').read()
check('a part WITH a UV layer is sent without vt / vn lines (UVs are never used, ZBrush recomputes normals)',
      sent == ['UVPart'] and txt.count('\nv ') == 8 and '\nvt ' not in txt and '\nvn ' not in txt)
check('wired: both OBJ exports of the bridge write no UVs', inspect.getsource(zb).count('export_uv=False') >= 2
      and 'export_uv=True' not in inspect.getsource(zb))
summary()
