"""0.24.351 Quad Remesh (QuadriFlow / Patch: Patch) on hard-surface parts with micro bevels (rows ~0.15 mm apart - the
user's tret01 plate: 98 open edges and 619 near-zero quads, sparks in a wireframe): the micro edges merged first ->
closed, all quads, no near-zero faces, on the surface.  Where merging them would bend the part (a notch cut through
the micro bevel), the result without is kept (closed, on the surface)."""
import math

import bmesh
from _harness import bpy, check, fresh, summary
from mathutils.bvhtree import BVHTree

import mecha_lab
from mecha_lab import quad_remesh as qr

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene


def plate(notch):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    ob = C.active_object
    ob.scale = (0.8, 0.25, 0.08)
    bpy.ops.object.transform_apply(scale=True)
    bv = ob.modifiers.new('b', 'BEVEL')
    bv.width, bv.segments = 0.0004, 3                      # (micro bevel: rows ~0.15 mm apart)
    bpy.ops.object.modifier_apply(modifier='b')
    if notch:
        bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=1.0, location=(0.1, 0.125, 0.0))
        cyl = C.active_object
        bo = ob.modifiers.new('n', 'BOOLEAN')
        bo.object, bo.solver = cyl, 'EXACT'
        C.view_layer.objects.active = ob
        bpy.ops.object.modifier_apply(modifier='n')
        bpy.data.objects.remove(cyl)
    return ob


def patch(ob):
    src = ob.data.copy()
    st = S.mch_quadremesh
    st.method, st.faces, st.edge_angle = 'PATCH', 4000, math.radians(10)
    for o in C.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    C.view_layer.objects.active = ob
    r = bpy.ops.mch.quad_remesh()
    q = C.active_object
    bm = bmesh.new()
    bm.from_mesh(q.data)
    open_ = sum(not e.is_manifold for e in bm.edges)
    areas = sorted(f.calc_area() for f in bm.faces)
    tiny = sum(1 for a in areas if a < areas[len(areas) // 2] * 1e-3)
    quads = sum(len(f.verts) == 4 for f in bm.faces)
    bvh = BVHTree.FromPolygons([v.co for v in src.vertices], [p.vertices for p in src.polygons])
    far = max((bvh.find_nearest(v.co)[0] - v.co).length for v in bm.verts)
    n = len(bm.faces)
    bm.free()
    return r, open_, quads, n, tiny, far


r, open_, quads, n, tiny, far = patch(plate(False))
check('Patch on a micro-bevelled plate: closed, all quads', r == {'FINISHED'} and open_ == 0 and quads == n,
      (open_, quads, n))
check('... no near-zero faces (the micro rows merged) and on the old surface (within 1 mm)',
      tiny == 0 and far < 0.001 and qr.PATCH_LOG.get('used') != 'plain', (tiny, far, qr.PATCH_LOG))
r, open_, quads, n, tiny, far = patch(plate(True))
check('... with a notch through the micro bevel: closed, all quads, on the surface (merging would bend it there: '
      'the result without merging kept)', r == {'FINISHED'} and open_ == 0 and quads == n and far < 0.001,
      (open_, quads, n, far, qr.PATCH_LOG))
summary()
