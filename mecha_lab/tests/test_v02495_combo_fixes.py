"""0.24.95 fixes found by the combination fuzz (user: "복스 하이드, 베이스 메쉬 빼기, 컷, 스플릿 이거 다 조합해 가지고
한 100개 만들어 보고 문제 계속 추적해 줄래?" - tests/fuzz/combo_scenario.py): the pieces checked one by one."""
import numpy as np
from _harness import bmesh, bpy, check, fresh, summary
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import mecha_lab
from mecha_lab import bake_highpoly as bk, box_hide as bh, cape_gen, core_geometry as cg, edge_memory as em

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene


def mesh_from(verts, faces, name='m'):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.update()
    return me


# ---- 1. split_warped: a face bent off its plane is cut into triangles, flat faces stay
verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0.5, 1.4, 0.0), (0, 1, 0),           # a flat pentagon
         (2, 0, 0), (3, 0, 0), (3, 1, 0), (2.5, 1.4, 0.25), (2, 1, 0)]          # one corner lifted
me = mesh_from(verts, [(0, 1, 2, 3, 4), (5, 6, 7, 8, 9)])
n = cg.split_warped(me)
sides = sorted(len(p.vertices) for p in me.polygons)
check('split_warped: the pentagon with a corner lifted 8 % of the size is cut into triangles, the flat one kept',
      n == 1 and sides == [3, 3, 3, 5], (n, sides))
check('... a flat mesh is left alone (0 faces cut)', cg.split_warped(me) == 0)

# ---- 2. pulled_back: a point outside the box but in the plane of its end face (the nearest point on an edge,
# found on the END face - its normal says "on the surface"; seed 82 of the fuzz: two Bevel points 1.2 % under a floor)
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
real = BVHTree.FromBMesh(bm)


class EndFaceFirst:
    """the box's BVH, but the nearest point of the test point reported on the front face (as the fuzz part did)"""
    def find_nearest(self, co):
        if (co - Vector((0.3, -0.5, -0.6))).length < 1e-6:
            return Vector((0.3, -0.5, -0.5)), Vector((0.0, -1.0, 0.0)), 0, 0.1
        return real.find_nearest(co)

    def ray_cast(self, o, d):
        return real.ray_cast(o, d)


before = EndFaceFirst()
out = bm.verts.new((0.3, -0.5, -0.6))           # below the floor, in the plane y = -0.5 of the front face
ins = bm.verts.new((0.1, 0.0, 0.1))             # inside
old_rule = cg.pulled_back(bm, before, [out, ins], 0.02)                     # (the normal test alone)
check('pulled_back (normal test only, as before): the point under the floor in the front face\'s plane is missed',
      old_rule == 0 and abs(out.co.z + 0.6) < 1e-6, (old_rule, tuple(out.co)))
moved = cg.pulled_back(bm, before, [out, ins], 0.02, closed=True)
check('... with the ray test (a closed shape): it goes back onto the box (z = -0.5), the inside point stays',
      moved == 1 and abs(out.co.z + 0.5) < 1e-5 and (ins.co - Vector((0.1, 0.0, 0.1))).length < 1e-9,
      (moved, tuple(out.co), tuple(ins.co)))
check('... _inside: the centre is inside, a point past a corner outside',
      cg._inside(real, Vector((0, 0, 0)), 1.0) and not cg._inside(real, Vector((0.6, 0.6, 0.6)), 1.0))
bm.free()

# ---- 3. Divide: a concave (dart) quad is cut before the subdivision
bm = bmesh.new()
a = [bm.verts.new(p) for p in ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0))]
b = [bm.verts.new(p) for p in ((2, 0, 0), (4, 0, 0), (3, 0.3, 0), (3, 2, 0))]
fa, fb = bm.faces.new(a), bm.faces.new(b)
bm.normal_update()
check('_convex_quad: a square is convex, a dart (one corner pushed in) is not',
      bk._convex_quad(fa) and not bk._convex_quad(fb))
bm.free()
me = mesh_from([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (2, 0, 0), (4, 0, 0), (3, 0.3, 0), (3, 2, 0),
                (5, 0, 0), (6, 0, 0), (6, 1, 0), (5.5, 1.5, 0), (5, 1, 0)],
               [(0, 1, 2, 3), (4, 5, 6, 7), (8, 9, 10, 11, 12)], 'cutfirst')
check('_cut_first (numpy): the dart quad and the pentagon are cut before Divide, the square is not',
      bk._cut_first(me).tolist() == [1, 2], bk._cut_first(me).tolist())

# ---- 4. mark_cut_borders: a sharp edge the Boolean made between two OLD points is a line
pts = [(0, 0, 0), (1, 0, 1), (1, 1, 0), (0, 1, 1)]
old = mesh_from(pts, [(0, 1, 2), (0, 2, 3)], 'old')
from mecha_lab import mesh_io as mio
old_co, old_ev = mio.read_co(old), mio.read_edge_verts(old)
new = mesh_from(pts, [(0, 1, 3), (1, 2, 3)], 'new')                       # the other diagonal: a 109-degree ridge
em.mark_cut_borders(new, cg.CUTTER_ATTR, old_co=old_co)
ridge = [e.index for e in new.edges if set(e.vertices) == {1, 3}][0]
check('mark_cut_borders without the old edges: the new 109-degree ridge between old points stays unmarked (before)',
      not em.marked(new)[ridge])
new2 = mesh_from(pts, [(0, 1, 3), (1, 2, 3)], 'new2')
em.mark_cut_borders(new2, cg.CUTTER_ATTR, old_co=old_co, old_ev=old_ev)
ridge2 = [e.index for e in new2.edges if set(e.vertices) == {1, 3}][0]
mk = em.marked(new2)
check('... with them (old_ev): it is marked, the outline edges (old pairs) are not',
      mk[ridge2] and mk.sum() == 1, (bool(mk[ridge2]), int(mk.sum())))

# ---- 5. a part a Box Hide hides all of: refused with a message, never an empty object or a Python error
me = bpy.data.meshes.new('Part')
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bm.to_mesh(me)
bm.free()
ob = bpy.data.objects.new('Part', me)
S.collection.objects.link(ob)
for o in C.selected_objects:
    o.select_set(False)
C.view_layer.objects.active = ob
ob.select_set(True)
mod = ob.modifiers.new('hide all', 'MASK')                  # (stands in for a Box Hide that hides everything)
mod.vertex_group = ob.vertex_groups.new(name='none').name
C.view_layer.update()
try:
    cape_gen._body(C, ob)
    got = 'no error'
except cg.CutError as ex:
    got = str(ex)
check('Drawing on an all-hidden part (Base Mesh subtract -> cape_gen._body): refused with a message (before: '
      'ValueError: min() iterable argument is empty)', 'no faces' in got, got)
try:
    bk.build(C, ob, target_faces=10_000, bevels='DIVIDE')
    got = 'no error'
except RuntimeError as ex:
    got = str(ex)
check('Bake High Poly on it: refused ("nothing to bake"), no 0-face high poly', 'nothing to bake' in got, got)
check('Box Hide all-hidden check: an evaluated mesh with 0 faces counts as all hidden', bh._all_hidden(C, ob))
summary()
