"""0.24.39 Base Mesh Alt carve along the surface is clean: a Line band carved into a bent, low-poly plate gets
rows of points across the band, a clean edge row for Chamfer / Bevel and smoothed normals - no sliver faces in
the groove, closed mesh, the full depth in the middle of the band."""
import math

from _harness import bpy, check, fresh, non_manifold, summary
import bmesh
from mathutils import Euler, Vector

import mecha_lab
from mecha_lab import base_mesh as bm_, core_geometry as cg, lasso_line as ll, surface_draw as sd

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene


def bent_plate():
    b = bmesh.new()
    rows = []
    for i in range(13):
        a = -0.7 + 1.4 * i / 12
        rows.append([b.verts.new((math.sin(a), y, math.cos(a) - 1.0)) for y in (-0.6, 0.6)])
    for i in range(12):
        b.faces.new((rows[i][0], rows[i + 1][0], rows[i + 1][1], rows[i][1]))
    me = bpy.data.meshes.new('Plate')
    b.to_mesh(me)
    b.free()
    ob = bpy.data.objects.new('Plate', me)
    C.collection.objects.link(ob)
    C.view_layer.objects.active = ob
    ob.select_set(True)
    m = ob.modifiers.new('s', 'SOLIDIFY')
    m.thickness, m.offset = 0.08, -1
    bpy.ops.object.modifier_apply(modifier='s')
    return ob


def slivers(ob, tiny=1e-6):
    """thin faces big enough to see (a few microscopic ones where the line's round end meets the surface are
    not counted)"""
    b = bmesh.new()
    b.from_mesh(ob.data)
    bad = 0
    for f in b.faces:
        if f.calc_area() < tiny:
            continue
        vs = [v.co for v in f.verts]
        for k in range(len(vs)):
            u, w = vs[k - 1] - vs[k], vs[(k + 1) % len(vs)] - vs[k]
            if u.length > 1e-9 and w.length > 1e-9 and u.angle(w) < math.radians(3):
                bad += 1
                break
    b.free()
    return bad


TOP = cg.OrthoProjector(Euler((0, 0, 0)).to_quaternion(), pixels_per_unit=300.0)
p = bm_.scene_defaults(C)
p.sketch, p.alt_mode, p.carve_depth, p.bevel_width = False, 'HEIGHT', 0.035, 0.015
S.mch_brush.line_width = 0.08
PATH = [(500 + 300 * (-0.55 + 1.1 * k / 40), 500 + 300 * (0.25 * math.sin(k / 40 * 3.0))) for k in range(41)]
for prof in ('CHAMFER', 'BEVEL', 'FLAT'):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    ob = bent_plate()
    p.profile = prof
    msg = bm_.perform_base(C, [ll.line_loop(C, TOP, PATH, S.mch_brush)], TOP, cutter=True)
    check(f'{prof}: carved, closed, no sliver faces in the groove', 'deep along the surface' in msg
          and non_manifold(ob) == 0 and slivers(ob) == 0, (msg, non_manifold(ob), slivers(ob)))
    # the middle of the band, along the line: as deep as Carve Depth under the bent surface
    C.view_layer.update()
    deep = []
    for k in (8, 20, 32):
        x, y = (PATH[k][0] - 500) / 300, (PATH[k][1] - 500) / 300
        top = math.cos(math.asin(max(-1, min(1, x)))) - 1.0
        hit, loc, _n, _i = ob.ray_cast(Vector((x, y, 2.0)), Vector((0, 0, -1)))
        deep.append(top - loc.z if hit else None)
    check(f'{prof}: the full depth in the middle of the band, everywhere along it',
          all(d is not None and abs(d - 0.035) < 0.006 for d in deep), deep)



def carve_faces(prof, segs, res):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    ob = bent_plate()
    p.profile, p.bevel_segments, p.resolution = prof, segs, res
    bm_.perform_base(C, [ll.line_loop(C, TOP, PATH, S.mch_brush)], TOP, cutter=True)
    return len(ob.data.polygons), non_manifold(ob) + slivers(ob)


p.bevel_width = 0.03
(f2, b2), (f8, b8) = carve_faces('BEVEL', 2, 28), (carve_faces('BEVEL', 8, 28))
check('Bevel: the Segments slider gives the carved edge more steps (still clean)', f8 > f2 and b2 == b8 == 0,
      (f2, f8, b2, b8))
(r1, c1), (r2, c2) = carve_faces('CHAMFER', 4, 28), carve_faces('CHAMFER', 4, 70)
check('Resolution: more points in the carve (smoother along the line), still clean', r2 > r1 and c1 == c2 == 0,
      (r1, r2, c1, c2))
p.resolution, p.bevel_segments = 28, 4

nrms = sd.smooth_normals([Vector((0, 0, 1)), Vector((0, 1, 0)), Vector((0, 0, 1))], [(0, 1, 2)], 3)
check('smoothed normals stay unit length and lean together', all(abs(n.length - 1) < 1e-6 for n in nrms)
      and nrms[1].z > 0.5, nrms)
summary()
