"""0.24.321 (user: "쿼드 플로우에 세밀한 면은 좀 더 면을 분배 가능하게 옵션을 추가"): Quad Remesh Detail Boost and Mark
Detail Area (the points selected in Edit Mode).  0.24.322 (user: "1.3 해줘" - in the engine): the remesher's own quad
size changes over the part - smaller where it bends sharply and on the Detail Area - the count staying about Target.
Off (0, no area): the same result as before."""
import math

import bmesh
import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import quad_detail as qd, quad_field as qf  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context


def block(name):
    bpy.ops.mesh.primitive_cube_add(size=2)
    ob = C.active_object
    ob.name = name
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=60, use_grid_fill=True)
    for v in bm.verts:
        if v.co.z > 0.999 and abs(v.co.x) < 0.04:
            v.co.z -= 0.1                                    # a groove narrower than a quad
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def bad_edges(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    n = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return n


a, b = block('A'), block('B')
qf.remesh_object(a, 1500)
qf.remesh_object(b, 1500, detail=0.0)
check('Detail Boost 0, no area: the same result as before', len(a.data.polygons) == len(b.data.polygons) and
      'mch_detail' not in a.data.attributes)
from mathutils.bvhtree import BVHTree


def far(ob, pts):
    """How far the result is from the original's points ``pts`` (the largest)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    t = BVHTree.FromBMesh(bm)
    bm.free()
    return max(t.find_nearest(p)[3] for p in pts)


groove = [v.co.copy() for v in block('G').data.vertices if abs(v.co.x) < 0.045 and v.co.z > 0.85]
c = block('C')
msg = qf.remesh_object(c, 1500, detail=0.9)
na, nc = len(a.data.polygons), len(c.data.polygons)
check(f'Detail 0.9: about the same count ({na} -> {nc})', 0.75 * na < nc < 1.35 * na)
check('... said in the message', 'Detail' in msg, msg)
check('... still closed (no open / 3-face edges)', bad_edges(c.data) == 0)
cx = np.array([p.center.x for p in c.data.polygons])
ax = np.array([p.center.x for p in a.data.polygons])
check(f'... more of them by the groove ({(np.abs(ax) < 0.2).sum()} -> {(np.abs(cx) < 0.2).sum()}), fewer on the flats',
      (np.abs(cx) < 0.2).sum() > 1.15 * (np.abs(ax) < 0.2).sum())
fa, fc = far(a, groove), far(c, groove)
check(f'... the groove kept closer ({fa:.4f} -> {fc:.4f} off)', fc < fa)
d = block('D')
qf.remesh_object(d, 1500, all_quads=True, detail=0.9)
nq = sum(len(p.vertices) == 4 for p in d.data.polygons)
check(f'All Quads + Detail: quads ({nq} of {len(d.data.polygons)}; the tidy-up may leave a few), closed',
      nq >= 0.99 * len(d.data.polygons) and bad_edges(d.data) == 0)

# Mark Detail Area: the selected points (Edit Mode) -> finer quads there, with Detail 0
e = block('E')
for v in e.data.vertices:
    v.select = v.co.x > 0.5
for o in C.selected_objects:
    o.select_set(False)
e.select_set(True)
C.view_layer.objects.active = e
bpy.ops.object.mode_set(mode='EDIT')
r = bpy.ops.mch.quad_detail_area()
bpy.ops.object.mode_set(mode='OBJECT')
check('Mark Detail Area (Edit Mode selection): marked', r == {'FINISHED'} and qd.area_count(e.data) > 100,
      qd.area_count(e.data))
qf.remesh_object(e, 1500)
ex = np.array([p.center.x for p in e.data.polygons])
check(f'... Quad Remesh: finer there ({(ex > 0.6).sum()} faces past x 0.6 vs {(ax > 0.6).sum()} unmarked), '
      f'the count about the same ({len(ex)})', (ex > 0.6).sum() > 2 * (ax > 0.6).sum() and len(ex) < 1.6 * na)
check('... closed', bad_edges(e.data) == 0)
r = bpy.ops.mch.quad_detail_area(clear=True)
check('X: the area cleared', 'mch_detail' not in e.data.attributes)

# a sphere with one bump: the quads smaller round the bump
bpy.ops.mesh.primitive_uv_sphere_add(segments=128, ring_count=64, radius=1)
s = C.active_object
for v in s.data.vertices:
    n = v.co.normalized()
    v.co = n * (1 + 0.06 * math.exp(-((n.x - 0.5) ** 2 + (n.z - 0.6) ** 2) / 0.004))
plain = s.copy()
plain.data = s.data.copy()
C.scene.collection.objects.link(plain)
qf.remesh_object(plain, 1500)
qf.remesh_object(s, 1500, detail=0.6)


def near_bump(ob):
    return sum(1 for p in ob.data.polygons if (p.center.normalized().x - 0.5) ** 2 + (p.center.normalized().z - 0.6) ** 2
               < 0.02)


np_, ns = len(plain.data.polygons), len(s.data.polygons)
check(f'a sphere with one bump: about the same count ({np_} -> {ns}), more round the bump '
      f'({near_bump(plain)} -> {near_bump(s)})', 0.7 * np_ < ns < 1.4 * np_ and near_bump(s) > 1.3 * near_bump(plain))
check('... closed', bad_edges(s.data) == 0)
zb = C.scene.mch_zb
check('Detail Boost on the shelf: 0 by default', zb.bl_rna.properties['qr_detail'].default == 0.0)
summary()
