"""0.23.0 Tube / Curve tool (Nomad-style): live solid tube along clicked points, per-point
radius, profile / cap / hole / twist, Smooth / B-Spline / Linear, Closed; Repeat mode
(copies of an object or a sphere along the curve); Apply."""
import math
import sys
import types

from _harness import bpy, check, cube, fresh, non_manifold, summary
import bmesh
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import bottom_bar as bb, core_geometry as cg, curve_tube as ct, tool_state as ts

# ---- pure path / mesh
pts = [Vector((0, 0, 0)), Vector((1, 0, 0)), Vector((1, 1, 0)), Vector((0, 1, 0))]
for sp in ('SMOOTH', 'BSPLINE', 'LINEAR'):
    sm = ct.path_samples(pts, [1, 1, 1, 1], False, sp, 8)
    check(f'{sp}: open path starts and ends at the end points', (sm[0][0] - pts[0]).length < 1e-6
          and (sm[-1][0] - pts[-1]).length < 1e-6 and len(sm) > 8, len(sm))
sm = ct.path_samples(pts, [1, 1, 1, 1], False, 'SMOOTH', 8)
check('Smooth passes through every point', all(min((p - q).length for p, _r in sm) < 1e-6 for q in pts))
sb = ct.path_samples(pts, [1, 1, 1, 1], False, 'BSPLINE', 8)
check('B-Spline is softer (does not reach the middle points)', min((p - pts[1]).length for p, _r in sb) > 0.05)
sc = ct.path_samples(pts, [1, 1, 1, 1], True, 'SMOOTH', 8)
check('Closed: 4 segments, back near the start', len(sc) == 32 and (sc[-1][0] - pts[0]).length < 0.5)
sr = ct.path_samples(pts, [1, 2, 3, 4], False, 'LINEAR', 4)
check('radius is interpolated along the curve', abs(sr[0][1] - 1) < 1e-6 and abs(sr[-1][1] - 4) < 1e-6)
fr = ct.frames(sm)
check('frames: orthonormal', all(abs(t.dot(n)) < 1e-5 and abs(t.dot(b)) < 1e-5 and abs(n.length - 1) < 1e-5
                                  for t, n, b in fr))

S0 = dict(radius=0.1, profile='ROUND', sides=12, cap='FLAT', hole=0.0)


def mesh_of(verts, faces):
    me = bpy.data.meshes.new('t')
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new('t', me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def vol(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    v = bm.calc_volume(signed=True)
    bm.free()
    return v


fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
for cap in ('FLAT', 'ROUND'):
    o = mesh_of(*ct.tube_mesh(sm, dict(S0, cap=cap)))
    check(f'tube with {cap} caps: closed, normals out', non_manifold(o) == 0 and vol(o) > 0, (non_manifold(o), vol(o)))
o = mesh_of(*ct.tube_mesh(sm, dict(S0, cap='OPEN')))
check('open caps: open tube ends', non_manifold(o) > 0)
o = mesh_of(*ct.tube_mesh(sm, dict(S0, hole=0.6)))
check('hole: hollow pipe, closed walls', non_manifold(o) == 0 and vol(o) > 0)
o = mesh_of(*ct.tube_mesh(sc, dict(S0, closed=True)))
check('closed ring tube: closed', non_manifold(o) == 0 and vol(o) > 0)
for prof in ('SQUARE', 'FLAT'):
    o = mesh_of(*ct.tube_mesh(sm, dict(S0, profile=prof)))
    check(f'{prof} profile: closed', non_manifold(o) == 0)
v1, _f = ct.tube_mesh(sm, dict(S0, twist=1.0))
v0, _f = ct.tube_mesh(sm, S0)
check('twist changes the tube', v0 != v1)
rv, rf = ct.repeat_mesh(sm, dict(radius=0.1, count=5, size=1.0), *ct.sphere_source())
sv, _sf = ct.sphere_source()
check('repeat: 5 spheres along the curve', len(rv) == 5 * len(sv))
ap = ct.arc_points(sm, 5)
check('repeat spacing: first / last at the ends', (ap[0][0] - pts[0]).length < 1e-6
      and (ap[-1][0] - pts[-1]).length < 1e-6)

# ---- tool registered
check('Tube tool in the tool list, toolbar and pie', 'TUBE' in ts.TOOL_BY_ID and any(t[0] == 'TUBE' for t in bb.BAR_TOOLS)
      and 'TUBE' in sum((v for v in bb.PIE_SHARED.values()), ()))

# ---- drawing logic (front view, ortho)
VIEW = cg.OrthoProjector(Quaternion((1, 0, 0), math.radians(90)))
ct.make_projector = lambda region, rv3d: VIEW


class Ctx:
    def __init__(self):
        self.area = types.SimpleNamespace(type='VIEW_3D', header_text_set=lambda t: None, tag_redraw=lambda: None)
        self.region = types.SimpleNamespace(width=1000, height=1000)
        self.region_data = object()

    scene = property(lambda self: bpy.context.scene)
    view_layer = property(lambda self: bpy.context.view_layer)
    active_object = property(lambda self: bpy.context.view_layer.objects.active)

    def evaluated_depsgraph_get(self):
        return bpy.context.evaluated_depsgraph_get()


ctx, op = Ctx(), ct.TubeLogic()
op.start(ctx)
r = op.click(ctx, (300, 500))
ob = op._ob()
check('first click makes a live tube object', r == 'NEW' and ct.is_tube(ob))
op.click(ctx, (500, 600))
op.click(ctx, (700, 500))
check('3 points -> a solid tube right away (not a curve line)', len(ct.get_points(ob)) == 3
      and len(ob.data.polygons) > 20 and non_manifold(ob) == 0)
w = op._world_pts()
check('air points at the depth of the first point (3D cursor plane)', all(abs(p.y) < 1e-6 for p in w)
      and abs(w[1].z - 1.0) < 1e-6, [tuple(round(c, 3) for c in p) for p in w])
r = op.click(ctx, (500, 600))
op.move(ctx, (500, 700))
op.release()
check('drag a point', r == 'DRAG' and abs(op._world_pts()[1].z - 2.0) < 1e-6)
seg_xy = VIEW.to_screen(ob.matrix_world @ ct.path_samples([p for p, _r in ct.get_points(ob)], [1, 1, 1],
                                                          False, 'SMOOTH', 12)[6][0])
r = op.click(ctx, seg_xy)
op.release()
check('click on the line inserts a point', r == 'INSERT' and len(ct.get_points(ob)) == 4)
r0 = ct.get_points(ob)[0][1]
op.point_radius(ctx, (300, 500), 1.1)
check('Ctrl+Wheel on a point: its radius', abs(ct.get_points(ob)[0][1] - r0 * 1.1) < 1e-6)
h = op.handle_world(ctx, 1)
p1 = op._world_pts()[1]
import math as _m
check('0.24.38 orange radius handle right beside the point (26 px on screen), whatever the radius', h is not None
      and abs(_m.dist(VIEW.to_screen(h), VIEW.to_screen(p1)) - ct.HANDLE_PX) < 0.5,
      _m.dist(VIEW.to_screen(h), VIEW.to_screen(p1)))
rad0 = ob.mch_tube.radius * ct.get_points(ob)[1][1]
hs = VIEW.to_screen(h)
r = op.click(ctx, hs)
target = VIEW.to_screen(p1 + (h - p1) * 2.0)
op.move(ctx, target)
txt = op.radius_text()
op.release()
check('drag the orange handle twice as far: that point gets twice the radius', r == 'RADIUS'
      and abs(ob.mch_tube.radius * ct.get_points(ob)[1][1] - 2 * rad0) < 1e-3 and txt.startswith('Radius:'),
      (r, txt, ob.mch_tube.radius * ct.get_points(ob)[1][1], rad0))
h2 = op.handle_world(ctx, 1)
check('... and the handle is back beside the point after the drag', abs(_m.dist(VIEW.to_screen(h2), VIEW.to_screen(p1))
                                                                   - ct.HANDLE_PX) < 0.5)
check('other points keep their radius', abs(ct.get_points(ob)[2][1] - 1.0) < 1e-6)
op.delete_point(ctx, (300, 500))
check('X on a point deletes it', len(ct.get_points(ob)) == 3)
# click on a mesh: the point goes on the surface
box = cube('Box', 2.0, loc=(0, 0, -3))
C.view_layer.update()
n = len(ct.get_points(ob))
op.click(ctx, (500, 200))
w = op._world_pts()[-1]
check('point on a mesh sits on its surface', len(ct.get_points(ob)) == n + 1 and abs(w.y + 1.0) < 1e-4, tuple(w))
check('done keeps the live tube', op.done(ctx) == ob and ct.is_tube(ob))

# ---- live settings
tb = ob.mch_tube
k0 = len(ob.data.vertices)
tb.sides = 24
check('Sides slider rebuilds', len(ob.data.vertices) > k0)
def xspan():
    xs = [v_.co.x for v_ in ob.data.vertices]
    return max(xs) - min(xs)


x0 = xspan()
tb.radius *= 2
check('Radius slider', xspan() > x0 + 0.05, (x0, xspan()))
for k, v in (('profile', 'SQUARE'), ('cap', 'OPEN'), ('hole', 0.5), ('spline', 'BSPLINE'), ('closed', True),
             ('twist', 1.0), ('taper_end', 0.2), ('resolution', 4)):
    before = [tuple(v_.co) for v_ in ob.data.vertices]
    setattr(tb, k, v)
    check(f'{k} changes the tube', [tuple(v_.co) for v_ in ob.data.vertices] != before)
tb.mode = 'REPEAT'
tb.count = 6
check('Repeat: spheres along the curve', len(ob.data.vertices) == 6 * len(sv))
src = cube('Bolt', 0.2, loc=(5, 0, 0))
tb.source = src
check('Repeat an object', len(ob.data.vertices) == 6 * 8)
tb.count = 10
check('Repeat count', len(ob.data.vertices) == 10 * 8)
C.view_layer.objects.active = ob
ob.select_set(True)
r = bpy.ops.mch.tube_apply()
check('Apply: plain mesh, points gone', r == {'FINISHED'} and not ct.is_tube(ob) and ct.PTS_KEY not in ob)

# a single click then done -> nothing left
ctx, op = Ctx(), ct.TubeLogic()
op.start(ctx)
op.click(ctx, (100, 100))
name = op.ob_name
check('one point only: removed on done', op.done(ctx) is None and name not in bpy.data.objects)
check('operators registered', hasattr(bpy.ops.mch, 'tube_draw') and hasattr(bpy.ops.mch, 'tube_apply'))
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
