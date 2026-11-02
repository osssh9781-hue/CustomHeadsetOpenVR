"""0.24.95 one Resolution for every made / cut shape (user: "베이스 메시로 생성되는 원이나 베벨에 해상도를 올릴 수 있게
해 줘, 컷으로 자르는 면도 늘리거나 줄일 수 있게, 다른 툴도 잘리는 단면이나 영향 끼치는 게 있으면 다 조절하게 - 최종으로 낼 때
하이폴리여야 돼서"): scene.mch_settings.geo_res (%) multiplies every circle / curve / corner / bevel / finish / profile
segment count; 100 % is exactly what each tool made before."""
import inspect
import math
from types import SimpleNamespace

from _harness import bpy, check, cube, fresh, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import base_mesh as bm_mod, core_geometry as cg, cut_engine as ce, curve_tube as ct
from mecha_lab import screw_stamp as ss, tool_state as ts, top_bar, ui_tool_settings as uts

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
st = S.mch_settings
TOP = cg.OrthoProjector(Quaternion())

prop = type(st).bl_rna.properties['geo_res']
check('Setting: Resolution (%) on the scene, 100 by default, 25 - 800', st.geo_res == 100 and prop.default == 100
      and prop.hard_min == 25 and prop.hard_max == 800, (st.geo_res, prop.hard_min, prop.hard_max))
check('res_n: 100 % = the count as set (unchanged); 200 % doubles; 50 % halves but never under the minimum',
      [ts.res_n(n) for n in (1, 3, 64)] == [1, 3, 64]
      and (setattr(st, 'geo_res', 200) or [ts.res_n(n) for n in (1, 3, 64)]) == [2, 6, 128]
      and (setattr(st, 'geo_res', 50) or [ts.res_n(3), ts.res_n(64, 8), ts.res_n(1)]) == [2, 32, 1])
st.geo_res = 100

# ---- the shown places
groups = dict(top_bar.groups(C, 'BASE'))
groups_cut = dict(top_bar.groups(C, 'CUT'))
check('Top bar: a "Resolution" group (Res) for Base Mesh and Cut (every lasso tool + Screw / Perforate / SubD)',
      'Resolution' in groups and 'Resolution' in groups_cut and {'SCREW', 'PERF'} <= top_bar.RES_TOOLS
      and ts.SHAPE_TOOLS - {'ZONE'} <= top_bar.RES_TOOLS and 'ZONE' not in top_bar.RES_TOOLS, list(groups))   # (0.24.95 Lasso Zone: no geometry)
check('Side panel: the shape box shows "Resolution (all tools)"', "'geo_res'" in inspect.getsource(uts.draw_shape_options))


# ---- the lasso shapes: circle / ellipse / curve / round corners / freehand
def logic(shape):
    lg = ce.StrokeLogic.__new__(ce.StrokeLogic)
    lg.brush = S.mch_brush
    lg.shape = shape
    lg.anchor = (500.0, 500.0)
    return lg


S.mch_brush.circle_segments = 64
n100 = len(logic('CIRCLE')._drag_loops((600.0, 500.0), False, False)[0])
st.geo_res = 200
n200 = len(logic('CIRCLE')._drag_loops((600.0, 500.0), False, False)[0])
e200 = len(logic('ELLIPSE')._drag_loops((600.0, 560.0), False, False)[0])
st.geo_res = 50
n50 = len(logic('CIRCLE')._drag_loops((600.0, 500.0), False, False)[0])
st.geo_res = 100
check('Circle / Ellipse lasso: 64 segments at 100 %, 128 at 200 % (the ellipse too), 32 at 50 %',
      (n100, n200, e200, n50) == (64, 128, 128, 32), (n100, n200, e200, n50))
lg = logic('LASSO')
S.mch_brush.outline_corner, S.mch_brush.outline_radius, S.mch_brush.outline_segments = 'ROUND', 40.0, 6
sq = [(400.0, 400.0), (600.0, 400.0), (600.0, 600.0), (400.0, 600.0)]
r100 = len(lg._outline(sq))
st.geo_res = 300
r300 = len(lg._outline(sq))
st.geo_res = 100
S.mch_brush.outline_corner = 'NONE'
check('Round outline corners: 3x the points per corner at 300 %', r300 > 2.5 * r100 - 8, (r100, r300))
lg = logic('CURVE_LASSO')
lg.pts, lg.rounds = [(400.0, 400.0), (600.0, 420.0), (560.0, 600.0)], [1.0, 1.0, 1.0]
c100 = len(lg._curve())
st.geo_res = 200
c200 = len(lg._curve())
st.geo_res = 100
check('Curve Lasso: about twice the samples at 200 %', c200 > 1.7 * c100, (c100, c200))

# ---- Base Mesh: the circle and its bevel


def base(res, profile='BEVEL'):
    st.geo_res = res
    s = S.mch_base
    s.profile, s.bevel_segments, s.bevel_width = profile, 4, 0.05
    before = set(bpy.data.objects)
    bm_mod.perform_base(C, [logic('CIRCLE')._drag_loops((600.0, 500.0), False, False)[0]], TOP)
    new = [o for o in bpy.data.objects if o not in before]
    st.geo_res = 100
    ob = new[0]
    out = (len(ob.data.vertices), len(ob.data.polygons), ob.dimensions.copy())
    bpy.data.objects.remove(ob)
    return out, 0


(v1, f1, d1), _ = base(100)
(v2, f2, d2), _ = base(200)
(v4, f4, d4), _ = base(400)
check('Base Mesh, a beveled circle (64 x 4 rows): 2x round and 2x bevel rows at 200 % (64 x 6 -> 128 x 10 points), '
      '4x each at 400 % (256 x 18); the same size',
      (v1, v2, v4) == (64 * 6, 128 * 10, 256 * 18) and (d2 - d1).length < 0.02 * d1.length
      and (d4 - d1).length < 0.02 * d1.length, (v1, v2, v4, tuple(d1), tuple(d4)))
(vd1, fd1, _d), _ = base(100, 'DOME')
(vd2, fd2, _d), _ = base(200, 'DOME')
check('Base Mesh Dome: denser at 200 % (point spacing halved: ~4x the points)', 2.5 * vd1 < vd2 < 5.5 * vd1, (vd1, vd2))
(vb1, _f, _d), _ = base(50)
check('Base Mesh at 50 %: fewer points (a quick block-out)', vb1 < 0.4 * v1, (vb1, v1))

# ---- Cut: the round hole and its Edge Finish bevel


def cut(res):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    tgt = cube(size=2.0)
    c = S.mch_cut
    c.edge_finish, c.finish_width, c.finish_segments = 'BEVEL', 0.03, 3
    st.geo_res = res
    lp = logic('CIRCLE')._drag_loops((540.0, 500.0), False, False)[0]   # (a hole of radius 0.4 in the 2.0 cube)
    ce.perform_closed(C, 'CUT', [tgt], [lp], TOP)
    st.geo_res = 100
    return len(tgt.data.vertices), len(tgt.data.polygons)


cv1, cf1 = cut(100)
cv2, cf2 = cut(200)
check('Cut, a round hole with a Bevel finish: about 4x the points at 200 % (2x around, 2x finish rows)',
      3.0 * cv1 < cv2 < 5.0 * cv1 and cf2 > 2.5 * cf1, (cv1, cv2, cf1, cf2))

# ---- other tools: screw heads, tubes
st.geo_res = 100
sv1 = len(ss.head_mesh('DOME', 0.1, 0.05).vertices)
st.geo_res = 200
sv2 = len(ss.head_mesh('DOME', 0.1, 0.05).vertices)
st.geo_res = 100
check('Screw Stamp: a dome head has ~4x the points at 200 % (2x around, 2x up the dome)', 3.0 * sv1 < sv2 < 5.0 * sv1,
      (sv1, sv2))
samples = ct.path_samples([Vector((0, 0, 0)), Vector((1, 0, 0)), Vector((2, 0.5, 0))], [1.0, 1.0, 1.0], False,
                          'SMOOTH', 12)
base_s = dict(profile='ROUND', sides=16, radius=0.1, cap='ROUND')
t1 = len(ct.tube_mesh(samples, dict(base_s, sides=ct._res_sides('ROUND', 16)))[0])
st.geo_res = 200
t2 = len(ct.tube_mesh(samples, dict(base_s, sides=ct._res_sides('ROUND', 16)))[0])
hexa = ct._res_sides('ROUND', 6)
st.geo_res = 100
check('Tube: a round section doubles its sides at 200 %; a 6-sided one stays a hexagon', t2 > 1.7 * t1 and hexa == 6,
      (t1, t2, hexa))
check('Wired into the other tools (source): plate / extract bevels, Edge Molding, Cable, Mesh Along Curve, Hollow, '
      'Plate Detail, Ridge, polygon primitive, placed primitives, Line ends',
      all('res_n' in inspect.getsource(m) for m in (
          __import__('mecha_lab.panel_gen', fromlist=['x']), __import__('mecha_lab.face_extract', fromlist=['x']),
          __import__('mecha_lab.edge_molding', fromlist=['x']), __import__('mecha_lab.cable', fromlist=['x']),
          __import__('mecha_lab.along_curve', fromlist=['x']), __import__('mecha_lab.hollow_shell', fromlist=['x']),
          __import__('mecha_lab.plate_detail', fromlist=['x']), __import__('mecha_lab.mech_ridge', fromlist=['x']),
          __import__('mecha_lab.station_primitive', fromlist=['x']), __import__('mecha_lab.primitive_place', fromlist=['x']),
          __import__('mecha_lab.lasso_line', fromlist=['x']))))

# ---- Line mode band (user, a Line cut at Res 800 %: "덜 촘촘해" - the band's path was resampled every half
# half-width whatever the Resolution)
from mecha_lab import lasso_line as ll
arc = [(100 + 300 * math.sin(t / 40.0), 100 + 300 * (1 - math.cos(t / 40.0))) for t in range(0, 63)]
st.geo_res = 100
b100 = ll.band(arc, 40.0)
st.geo_res = 200
b200 = ll.band(arc, 40.0)
st.geo_res = 800
b800 = ll.band(arc, 40.0)
st.geo_res = 100
check('Line mode band: 100 % as before (140 points on this arc), about 2x at 200 %, about 5x at 800 %',
      len(b100) == 140 and 1.7 * len(b100) < len(b200) < 2.3 * len(b100) and len(b800) > 4.5 * len(b100),
      (len(b100), len(b200), len(b800)))
summary()
