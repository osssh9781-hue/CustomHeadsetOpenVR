"""Loft / Sweep: open & closed curves, different point counts, reversed curves,
3+ sections, caps, closed loft, live update, thickness/apply, error cases."""
import math
import sys

from _harness import bpy, bmesh, check, fresh, non_manifold, select_only, summary, volume
from mathutils import Vector

import mecha_lab
from mecha_lab import loft_surface as ls

C = bpy.context


def curve(name, pts, cyclic=False, kind='BEZIER'):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    sp = cu.splines.new(kind)
    if kind == 'BEZIER':
        sp.bezier_points.add(len(pts) - 1)
        for bp, p in zip(sp.bezier_points, pts):
            bp.co = p
            bp.handle_left_type = bp.handle_right_type = 'AUTO'
    else:
        sp.points.add(len(pts) - 1)
        for bp, p in zip(sp.points, pts):
            bp.co = (*p, 1)
    sp.use_cyclic_u = cyclic
    ob = bpy.data.objects.new(name, cu)
    C.scene.collection.objects.link(ob)
    return ob


def ring(name, r, z, n, cyclic=True):
    return curve(name, [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n), z)
                        for i in range(n)], cyclic)


def call(op, **kw):
    try:
        return op(**kw)
    except RuntimeError as ex:
        print('  (operator reported)', str(ex).splitlines()[0])
        return {'CANCELLED'}


def reset():
    fresh()
    d = C.scene.mch_loft
    d.samples, d.segments, d.smoothness, d.thickness = 32, 8, 1.0, 0.0
    d.cap_ends, d.flip_normals, d.auto_align, d.twist, d.close_loft = False, False, True, 0, False


mecha_lab.register()

# 1. Two open curves, one reversed -> auto aligned, no crossing
reset()
a = curve('A', [(0, 0, 0), (1, 0, 0.3), (2, 0, 0)])
b = curve('B', [(2, 2, 0), (1, 2, 0.5), (0, 2, 0)])       # opposite direction
select_only(a, b)
r = call(bpy.ops.mch.loft_create)
L = C.view_layer.objects.active
check('loft 2 open curves', r == {'FINISHED'} and L.name.startswith('MCH_Loft'))
check('quad grid size = samples x (segments+1)', len(L.data.vertices) == 32 * 9, len(L.data.vertices))
bm = bmesh.new()
bm.from_mesh(L.data)
bm.normal_update()
areas = [f.calc_area() for f in bm.faces]
check('auto-align: no collapsed/twisted faces', min(areas) > 1e-4, min(areas))
bm.free()
L.mch_loft.auto_align = False
bm = bmesh.new()
bm.from_mesh(L.data)
twisted = min(f.calc_area() for f in bm.faces)
bm.free()
check('without auto-align the reversed curve twists (proves alignment works)', twisted < min(areas))
L.mch_loft.auto_align = True

# 2. Three sections, different point counts and types (POLY + BEZIER), smooth vs ruled
reset()
a = curve('S1', [(0, 0, 0), (1, 0, 0), (2, 0, 0)])
b = curve('S2', [(0, 1, 1), (0.7, 1, 1.4), (1.4, 1, 1.2), (2, 1, 1)], kind='POLY')
c = curve('S3', [(0, 2, 0), (2, 2, 0)])
select_only(a, b, c)
C.view_layer.objects.active = a
r = call(bpy.ops.mch.loft_create)
L = C.view_layer.objects.active
check('loft 3 sections with 3/4/2 points', r == {'FINISHED'} and len(L.data.vertices) == 32 * 17)
smooth_co = [v.co.copy() for v in L.data.vertices]
L.mch_loft.smoothness = 0.0
diff = sum((v.co - c).length for v, c in zip(L.data.vertices, smooth_co))
check('smoothness changes the surface (Catmull-Rom vs ruled)', diff > 0.1, diff)
ys = sorted({round(v.co.y, 3) for v in L.data.vertices})
check('surface passes through every section', all(any(abs(y - t) < 1e-3 for y in ys) for t in (0, 1, 2)))
# live: move a section point
L.mch_loft.smoothness = 1.0
b.data.splines[0].points[1].co = (0.7, 1, 3.0, 1)
C.view_layer.update()
check('live: moving a curve point updates the surface', max(v.co.z for v in L.data.vertices) > 2.5,
      max(v.co.z for v in L.data.vertices))
b.location.z = 1.0
C.view_layer.update()
check('live: moving a curve object updates the surface', max(v.co.z for v in L.data.vertices) > 3.5)
# reorder sections via operator
select_only(L)
call(bpy.ops.mch.loft_move, index=2, direction=-1)
check('section order can be changed', [e.curve.name for e in L.mch_loft.curves] == ['S1', 'S3', 'S2'])

# 3. Closed rings with caps -> closed solid; thickness + apply
reset()
r1 = ring('R1', 1.0, 0, 6)
r2 = ring('R2', 0.5, 2, 8)
r3 = ring('R3', 0.8, 3, 5)
select_only(r1, r2, r3)
C.view_layer.objects.active = r1
C.scene.mch_loft.cap_ends = True
r = call(bpy.ops.mch.loft_create)
T = C.view_layer.objects.active
check('closed rings + caps = closed manifold solid', r == {'FINISHED'} and non_manifold(T) == 0)
bm = bmesh.new()
bm.from_mesh(T.data)
check('capped loft has outward normals', bm.calc_volume(signed=True) > 0)
bm.free()
T.mch_loft.cap_ends = False
T.mch_loft.thickness = 0.05
check('thickness = live Solidify modifier', T.modifiers.get(ls.THICK_MOD) is not None)
select_only(T)
r = call(bpy.ops.mch.loft_apply)
check('apply bakes thickness and stops live updates', r == {'FINISHED'} and not T.modifiers and not T.mch_loft.live
      and non_manifold(T) == 0)
n = len(T.data.vertices)
r1.location.z = 5
C.view_layer.update()
check('applied surface no longer follows curves', len(T.data.vertices) == n)

# 4. Closed loft (ring of sections) and twist
reset()
secs = []
for k in range(4):
    a = 2 * math.pi * k / 4
    secs.append(curve(f'Q{k}', [(math.cos(a) * 2 + math.cos(a) * 0.3 * math.cos(t), math.sin(a) * 2 + math.sin(a) * 0.3 * math.cos(t),
                                 0.3 * math.sin(t)) for t in [i * 2 * math.pi / 8 for i in range(8)]], True))
select_only(*secs)
C.view_layer.objects.active = secs[0]
C.scene.mch_loft.close_loft = True
r = call(bpy.ops.mch.loft_create)
Tor = C.view_layer.objects.active
check('closed loft through 4 rings = torus-like closed surface', r == {'FINISHED'} and non_manifold(Tor) == 0)
Tor.mch_loft.twist = 3
check('twist rebuilds without error', not Tor.get('mch_loft_error'))

# 5. Errors
reset()
a = curve('Open', [(0, 0, 0), (1, 0, 0)])
b = ring('Closed', 1, 1, 6)
select_only(a, b)
r = call(bpy.ops.mch.loft_create)
check('open + closed mix refused with message, nothing created', r == {'CANCELLED'} and
      not any(o.name.startswith('MCH_Loft') for o in bpy.data.objects))

# 6. Sweep
reset()
prof = ring('Prof', 0.2, 0, 8)
path = curve('Path', [(0, 0, 0), (1, 1, 1), (2, 0, 2)])
select_only(prof, path)
C.view_layer.objects.active = path
C.scene.mch_loft.cap_ends = True
r = call(bpy.ops.mch.sweep_create)
S = C.view_layer.objects.active
check('sweep profile along path', r == {'FINISHED'} and S.name.startswith('MCH_Sweep'))
check('capped sweep is closed', non_manifold(S) == 0)
radii = []
pts = ls.resample(ls.curve_polyline(path)[0], 50, False)
check('sweep tube follows the path', all(min((v.co - p).length for p in pts) < 0.25 for v in S.data.vertices))
path.data.splines[0].bezier_points[1].co.z = 2.0
C.view_layer.update()
check('sweep is live', max(v.co.z for v in S.data.vertices) > 1.9)

mecha_lab.unregister()
sys.exit(1 if summary() else 0)
