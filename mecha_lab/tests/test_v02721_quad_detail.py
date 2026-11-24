"""0.24.321 (user: "쿼드 플로우에 세밀한 면은 좀 더 면을 분배 가능하게 옵션을 추가"): Quad Remesh Detail Boost (the quads
that miss the original split 3 x 3 with transition quads round them, the new points on the original) and Mark Detail
Area (the points selected in Edit Mode get them).  Off (0, no area): the same result as before."""
import math

import bmesh
import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import quad_detail as qd, quad_field as qf

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
c = block('C')
msg = qf.remesh_object(c, 1500, detail=0.9)
check('Detail Boost 0.9: more faces (only where they miss)', len(a.data.polygons) < len(c.data.polygons) <
      len(a.data.polygons) * 2, (len(a.data.polygons), len(c.data.polygons)))
check('... said in the message', 'Detail Boost' in msg, msg)
check('... still closed (no open / 3-face edges)', bad_edges(c.data) == 0)
cx = np.array([p.center.x for p in c.data.polygons])
ax = np.array([p.center.x for p in a.data.polygons])
check('... the new faces by the groove', (np.abs(cx) < 0.2).sum() > (np.abs(ax) < 0.2).sum() and
      (np.abs(cx) > 0.6).sum() <= (np.abs(ax) > 0.6).sum() * 1.1)
d = block('D')
qf.remesh_object(d, 1500, all_quads=True, detail=0.9)
check('All Quads + Detail Boost: still only quads', all(len(p.vertices) == 4 for p in d.data.polygons) and
      bad_edges(d.data) == 0)

# Mark Detail Area: the selected points (Edit Mode) -> finer quads there, with Detail Boost 0
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
check(f'... Quad Remesh: finer there ({(ex > 0.6).sum()} faces past x 0.6 vs {(ax > 0.6).sum()} unmarked)',
      (ex > 0.6).sum() > 4 * (ax > 0.6).sum() and abs((ex < -0.6).sum() - (ax < -0.6).sum()) <= 0.2 * (ax < -0.6).sum())
check('... closed', bad_edges(e.data) == 0)
r = bpy.ops.mch.quad_detail_area(clear=True)
check('X: the area cleared', 'mch_detail' not in e.data.attributes)

# a Mostly Quads result with triangles: the marks do not run over the whole part
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
check(f'a sphere with one bump: only round the bump ({len(plain.data.polygons)} -> {len(s.data.polygons)} faces)',
      len(plain.data.polygons) < len(s.data.polygons) < 2 * len(plain.data.polygons))
check('... closed', bad_edges(s.data) == 0)
zb = C.scene.mch_zb
check('Detail Boost on the shelf: 0 by default', zb.bl_rna.properties['qr_detail'].default == 0.0)
summary()
