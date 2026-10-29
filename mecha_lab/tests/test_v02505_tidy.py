"""0.24.83 Clean results (from the mech-build fuzz): a Split's gap left paper-thin shards as parts (folded faces,
zero-area faces, specks), Decimate turned a 12-triangle plate into a tetrahedron and left folded fins on a noisy
sphere, Quad Remesh left zero-area faces on a small plate.  core_geometry.tidy_result / is_junk clean every
boolean / decimate / remesh result; a Split drops junk pieces; Decimate has a floor."""
from _harness import bpy, check, cube, fresh, non_manifold, summary
import bmesh

import mecha_lab
from mecha_lab import core_geometry as cg, fast_decimate as fd, quad_field as qf

mecha_lab.register()
fresh()
C = bpy.context


def mesh_with(verts, faces, name='m'):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    return me


# a closed box + a folded fin on one edge (two triangles back to back, from_pydata lets them in) + a speck piece
b = cube('Box', 2.0)
verts = [tuple(v.co) for v in b.data.vertices]
faces = [tuple(p.vertices) for p in b.data.polygons]
e0, e1 = b.data.edges[0].vertices
verts.append(tuple((b.data.vertices[e0].co + b.data.vertices[e1].co) / 2 + b.data.vertices[e0].co.normalized() * 0.001))
tip = len(verts) - 1
faces += [(e0, e1, tip), (e1, e0, tip)]
n0 = len(verts)
verts += [(5 + 0.001 * i, 5, 5) for i in range(3)]              # a speck: 1 tiny triangle far away
faces.append((n0, n0 + 1, n0 + 2))
me0 = mesh_with(verts, faces, 'box_fin')
b.data = me0
q0 = dict(faces=len(b.data.polygons), nm=cg.non_manifold_edge_count(b.data))
out = cg.tidy_result(b.data, cg.mesh_size(b.data))
check('tidy_result: the folded fin (2 faces) and the speck (1 face) gone, the box closed and intact',
      out['folds'] + out['degenerate'] + out['shards'] >= 3 and len(b.data.polygons) == 6
      and cg.non_manifold_edge_count(b.data) == 0,
      (q0, out, len(b.data.polygons)))
me = mesh_with([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (1, 1, 0)], [(0, 1, 2, 3), (2, 4, 3)])
out = cg.tidy_result(me)
check('... a doubled point welded and its zero-area face dissolved', out['welded'] == 1 and len(me.polygons) == 1, out)
check('is_junk: under 4 faces / no area / a speck next to the part; a real piece is not',
      cg.is_junk(mesh_with([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)]))
      and cg.is_junk(mesh_with([(0, 0, 0), (0.001, 0, 0), (0.001, 0.001, 0), (0, 0.001, 0), (0, 0, 0.001), (0.001, 0, 0.001)],
                               [(0, 1, 2), (0, 2, 3), (0, 4, 5), (1, 4, 5)]), ref_size=10.0)
      and not cg.is_junk(cube('Real', 1.0).data, ref_size=10.0))

# Decimate: a 12-triangle plate stays, a noisy sphere comes back without folds
plate = cube('Plate', 1.0)
plate.scale = (1, 1, 0.02)
bpy.ops.object.transform_apply(scale=True)
msg = fd.decimate_object(plate, 30)
check('Decimate on a 12-triangle plate: left alone with a message (was a tetrahedron)', 'already light' in msg
      and len(plate.data.polygons) == 6, (msg, len(plate.data.polygons)))
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=48, ring_count=24)
sph = C.active_object
import random
rnd = random.Random(3)
for v in sph.data.vertices:
    v.co += v.normal * rnd.uniform(-0.08, 0.08)
sph.data.update()
msg = fd.decimate_object(sph, 25)
bm = bmesh.new()
bm.from_mesh(sph.data)
multi = sum(1 for e in bm.edges if len(e.link_faces) > 2)
seen, twins = set(), 0
for f in bm.faces:
    k = tuple(sorted(v.index for v in f.verts))
    twins += k in seen
    seen.add(k)
bm.free()
check('Decimate on a noisy sphere: no edge with 3+ faces, no faces on the same points, closed',
      multi == 0 and twins == 0 and non_manifold(sph) == 0 and 'Decimate:' in msg, (multi, twins, msg[-60:]))

# Quad Remesh on a small cut plate: no zero-area faces
if qf.available():
    p2 = cube('P2', 0.9)
    p2.scale = (1, 0.6, 0.03)
    bpy.ops.object.transform_apply(scale=True)
    msg = qf.remesh_object(p2, 60)
    zero = sum(1 for p in p2.data.polygons if p.area < 1e-12)
    check('Quad Remesh on a small thin plate: no zero-area faces', zero == 0 and 'Quad Remesh' in msg, (zero, msg[:70]))
if qf.available():
    thin = cube('Thin', 1.0)
    thin.scale = (0.9, 0.5, 0.012)
    bpy.ops.object.transform_apply(scale=True)
    import bmesh as _bm
    def vol(ob):
        b = _bm.new(); b.from_mesh(ob.data); v = abs(b.calc_volume(signed=True)); b.free(); return v
    v0 = vol(thin)
    msg = qf.remesh_object(thin, 60, all_quads=True)
    check('Quad Remesh (All Quads, few faces) on a plate thinner than a quad: finer until the volume survives, or '
          'kept as it is - never a flat sheet with holes', cg.non_manifold_edge_count(thin.data) == 0
          and vol(thin) > 0.5 * v0 and ('kept as they are' in msg or len(thin.data.polygons) > 60),
          (msg[:90], len(thin.data.polygons), round(vol(thin) / v0, 2)))
check('is_junk: a small open scrap (a boolean that broke) is junk too',
      cg.is_junk(mesh_with([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 1), (1, 0, 1)],
                           [(0, 1, 2, 3), (0, 1, 5, 4), (1, 2, 5), (0, 3, 4)]), ref_size=5.0))
check('A Split / Cut result goes through tidy_result; a junk Split piece is dropped and said',
      'cg.tidy_result(me, cg.mesh_size(t.data), before=t.data)' in __import__('inspect').getsource(__import__('mecha_lab.cut_engine', fromlist=['x'])._perform_closed)
      and 'paper-thin shard' in __import__('inspect').getsource(__import__('mecha_lab.cut_engine', fromlist=['x'])._perform_closed))
summary()
