"""0.24.157 (user: "털도 방법이 있니? 내가 지정한 영역에 털이 생겼으면 좋겠는데 기장, 곱슬, 끝이 모이는지, 중력, 두께랑 팁 두께"
... "색은 폴리페인트에서 가져오는 것도 넣어 주고 지오메트리 노드로"): the Fur tool - an area drawn on a body (the shared
lasso; here the outline in pixels through a fixed front view), live hair curves made by Geometry Nodes.  Every value
is measured on the evaluated strands.  The real drawing: tests/gui/fur_real_window.py."""
import math
import os
import time

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Euler, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, creature_fur as cf, tool_state as ts, ui_tool_settings as uts  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
check('the tool: Fur in the Creature tools, its icon, its window, its stroke mode',
      'FUR' in ts.TOOL_BY_ID and 'FUR' in dict(ts.TOOL_GROUPS)['Creature'] and 'FUR' in ts.SHAPE_TOOLS
      and os.path.isfile(os.path.join(os.path.dirname(cf.__file__), 'icons', 'fur.png'))
      and uts.DRAWERS.get('FUR') is not None and hasattr(S, 'mch_fur')
      and 'FUR' in {i.identifier for i in bpy.ops.mch.cut_stroke.get_rna_type().properties['mode'].enum_items})

bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=192, ring_count=96)        # (faces about 3 cm: 6.5 px)
body = C.active_object
me = body.data
ca = me.color_attributes.new('Polypaint', 'FLOAT_COLOR', 'POINT')
co = np.empty(len(me.vertices) * 3, np.float32)
me.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
ca.data.foreach_set('color', np.where((co[:, 0] < 0)[:, None], [[1, 0, 0, 1]], [[0, 0, 1, 1]]).astype(np.float32).ravel())
me.color_attributes.active_color = ca
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)   # 200 px = 1


def ellipse(cx, cy, rx, ry, n=64):
    return [[(cx + rx * math.cos(a), cy + ry * math.sin(a)) for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]]


def strands(ob):
    dg = C.evaluated_depsgraph_get()
    cv = ob.evaluated_get(dg).data
    k = len(cv.curves)
    if not k:
        return np.zeros((0, 2, 3)), cv
    pos = np.empty(len(cv.points) * 3, np.float32)
    cv.attributes['position'].data.foreach_get('vector', pos)
    return pos.reshape(k, -1, 3), cv


def settle(ob):
    ob.update_tag()
    C.view_layer.update()


st = S.mch_fur
st.density, st.length, st.clump, st.frizz, st.edge_soft = 8000.0, 0.08, 0.0, 0.0, 0
st.volume, st.spread = 0.0, 0.0                                     # (0.24.160 off for the exact angles; tried below)
t0 = time.time()
msg = cf.perform(C, ellipse(500, 500, 120, 90), FRONT)                  # (0.6 x 0.45 on the sphere's front)
t_draw = time.time() - t0
fur = C.active_object
P, cv = strands(fur)
roots = P[:, 0]
w = np.empty(len(me.vertices), np.float32)                          # (the area's size on the sphere: each face x the
me.attributes[fur[cf.AREA_KEY]].data.foreach_get('value', w)        #  mean weight of its corners)
area = sum(poly.area * float(np.mean(w[list(poly.vertices)])) for poly in me.polygons)
check(f'a drawn area on the sphere: a fur ({len(P):,} strands = Density 8000 x {area:.3f} m2 of area, within 12 %; '
      f'drawn in {t_draw:.2f} s), a hair Curves object on the body, live (Geometry Nodes)', fur.type == 'CURVES'
      and cf.is_fur(fur) and fur.parent == body and fur.modifiers.get(cf.MOD) is not None
      and abs(len(P) - 8000 * area) < 0.12 * 8000 * area and 'Creature Fur' in [c.name for c in fur.users_collection], msg)
sx = 500 + roots[:, 0] * 200
sy = 500 + roots[:, 2] * 200
ang = np.arctan2((sy - 500) / 90, (sx - 500) / 120)                  # (the outline's point in each root's direction)
edge = np.c_[500 + 120 * np.cos(ang), 500 + 90 * np.sin(ang)]
r_root = np.hypot(sx - 500, sy - 500)
r_edge = np.hypot(edge[:, 0] - 500, edge[:, 1] - 500)
past = np.maximum(r_root - r_edge, 0.0)
check(f'every root inside the drawn outline as seen from the front (at most {past.max():.1f} px past it - a face of '
      f'the sphere is 6.5 px; {np.mean(past > 0) * 100:.1f} % past at all) and on the side that faced the view',
      len(P) > 0 and past.max() < 6.5 and np.mean(past > 0) < 0.03 and roots[:, 1].max() < 0.0)
d = np.linalg.norm(roots, axis=1)
check('... on the surface (1 from the centre)', abs(d - 1).max() < 0.01, (d.min(), d.max()))

lens = np.linalg.norm(np.diff(P, axis=1), axis=2).sum(1)
check(f'Length 0.08, Length Random 0.35: every strand 0.052 .. 0.08 long (here {lens.min():.4f} .. {lens.max():.4f})',
      lens.min() > 0.08 * 0.65 - 1e-3 and lens.max() < 0.08 + 1e-3)
rad = np.empty(len(cv.points), np.float32)
cv.attributes['radius'].data.foreach_get('value', rad)
rad = rad.reshape(len(P), -1)
check(f'Root / Tip Thickness {st.root_thick * 1000:.2f} mm / {st.tip_thick * 1000:.2f} mm: the radius half of it at the '
      f'root and the tip', abs(rad[:, 0].mean() - st.root_thick / 2) < 1e-6 and abs(rad[:, -1].mean() - st.tip_thick / 2) < 1e-6)
col = np.empty(len(cv.points) * 4, np.float32)
cv.attributes['mch_fur_col'].data.foreach_get('color', col)
col = col.reshape(len(P), -1, 4)
L_, R_ = roots[:, 0] < -0.08, roots[:, 0] > 0.08
check('the colour from the polypaint at each root (left half red, right half blue)', L_.any() and R_.any()
      and np.allclose(col[L_, 0, :3].mean(0), (1, 0, 0), atol=0.02) and np.allclose(col[R_, 0, :3].mean(0), (0, 0, 1), atol=0.02))
tipc = np.array(st.tip_color[:3])
want = (np.array([1, 0, 0]) * (1 - st.tip_blend) + tipc * st.tip_blend)
check(f'... to the Tip Color by Tip Blend {st.tip_blend} at the tip', np.allclose(col[L_, -1, :3].mean(0), want, atol=0.02),
      col[L_, -1, :3].mean(0).round(3).tolist())


def direction(P):
    v = P[:, 1] - P[:, 0]
    return v / np.linalg.norm(v, axis=1)[:, None]


eq = np.abs(roots[:, 2]) < 0.1                                       # (round the sphere's equator: the normal flat)
pg = fur.mch_fur
tilt = cf.current_part(fur)                                         # (0.24.159 the drawn area's own tilt)
check('the drawn area is the fur\'s Area 1, with the tilt it was drawn with (the next fur\'s values)', len(pg.parts) == 1
      and tilt is not None and abs(tilt.lie - S.mch_fur.lie) < 1e-6 and cf.part_sizes(fur).get(1, 0) > 100)
tilt.lie, pg.gravity = 0.0, 0.0
settle(fur)
P, cv = strands(fur)
roots = P[:, 0]
nrm = roots / np.linalg.norm(roots, axis=1)[:, None]
straight = np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', direction(P), nrm), -1, 1)))
tipdir = (P[:, -1] - P[:, 0]) / np.linalg.norm(P[:, -1] - P[:, 0], axis=1)[:, None]
tipang = np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', tipdir, nrm), -1, 1)))
check(f'Lie Down 0, Gravity 0: every strand straight out of the skin (worst {max(straight.max(), tipang.max()):.1f} deg '
      f'from the normal, root and tip)', max(straight.max(), tipang.max()) < 2.0)
tilt.lie = math.pi / 2                                              # (Lie Down: an angle from the normal - 90 flat)
settle(fur)
P, _cv = strands(fur)
dd = direction(P)
nrm = P[:, 0] / np.linalg.norm(P[:, 0], axis=1)[:, None]
eq = np.abs(P[:, 0, 2]) < 0.1
flat = np.abs(np.einsum('ij,ij->i', dd, nrm)).max()
check(f'Lie Down 90 deg (Flow 0): flat on the skin (|dir . normal| at most {flat:.3f}), pointing down the body round the '
      f'equator (dir.z {dd[eq, 2].mean():.2f})', flat < 0.03 and dd[eq, 2].mean() < -0.95)
tilt.flow = math.radians(90)
settle(fur)
P, _cv = strands(fur)
dd = direction(P)
eq = np.abs(P[:, 0, 2]) < 0.1
side = np.abs(dd[eq, 0]).mean()
check(f'Flow Angle 90: the fur lies sideways instead (|dir.x| {side:.2f}, dir.z {dd[eq, 2].mean():.2f})',
      side > 0.9 and abs(dd[eq, 2].mean()) < 0.1)
tilt.flow = 0.0
# 0.24.159 areas: a second area drawn below (a band across the lower front) - its own tilt; the first area unchanged
pg.part_soft = 0
cf.perform(C, ellipse(500, 360, 110, 30), FRONT)                    # (z -0.85 .. -0.55: screen up = +z)
a2 = cf.current_part(fur)
a2.flow = math.radians(90)
a2.lie = math.radians(30)
settle(fur)
P, _cv = strands(fur)
dd = direction(P)
r0 = P[:, 0]
nn = r0 / np.linalg.norm(r0, axis=1)[:, None]
ang = np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', dd, nn), -1, 1)))
ids = cf.part_ids(fur)
lower = (r0[:, 2] < -0.6) & (r0[:, 2] > -0.8)
upper = np.abs(r0[:, 2]) < 0.1
tan = dd - nn * np.einsum('ij,ij->i', dd, nn)[:, None]
tan /= np.maximum(np.linalg.norm(tan, axis=1), 1e-9)[:, None]
check(f'Area 2 drawn below, set to Lie Down 30 deg, Flow 90: its fur 30 deg off the normal (measured '
      f'{ang[lower].mean():.1f}), tilted sideways (|tangent x| {np.abs(tan[lower, 0]).mean():.2f}, z {np.abs(tan[lower, 2]).mean():.2f}); Area 1 still flat and '
      f'down the body (measured {ang[upper].mean():.1f} deg, dir.z {dd[upper, 2].mean():.2f})', len(pg.parts) == 2
      and pg.part_index == 1 and lower.sum() > 20 and abs(ang[lower].mean() - 30) < 3
      and np.abs(tan[lower, 0]).mean() > 0.85 and np.abs(tan[lower, 2]).mean() < 0.1     # (sideways: round the sphere)
      and abs(ang[upper].mean() - 90) < 3 and dd[upper, 2].mean() < -0.95)
for o in C.selected_objects:
    o.select_set(False)
fur.select_set(True)
C.view_layer.objects.active = fur
r = bpy.ops.mch.fur_part(index=0)
pg.parts[pg.part_index].lie = math.radians(45)
settle(fur)
P, _cv = strands(fur)
dd = direction(P)
r0 = P[:, 0]
nn = r0 / np.linalg.norm(r0, axis=1)[:, None]
ang = np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', dd, nn), -1, 1)))
lower = (r0[:, 2] < -0.6) & (r0[:, 2] > -0.8)
upper = np.abs(r0[:, 2]) < 0.1
check(f'pick Area 1 (the window), set its Lie Down to 45 deg: only Area 1 changes (measured {ang[upper].mean():.1f}); '
      f'Area 2 keeps its 30 deg ({ang[lower].mean():.1f})', 'FINISHED' in r and pg.part_index == 0
      and abs(ang[upper].mean() - 45) < 3 and abs(ang[lower].mean() - 30) < 3)
# overlap: the last drawn area wins where they overlap
cf.perform(C, ellipse(500, 500, 30, 30), FRONT)                     # (a small area in Area 1's middle)
ids2 = cf.part_ids(fur)
check('a third area drawn over the middle of Area 1: those points are Area 3\'s now (the last drawn wins), the rest '
      'Area 1\'s still', len(pg.parts) == 3 and (ids2 == 3).sum() > 0 and (ids2 == 1).sum() > 0
      and (ids2 == 1).sum() + (ids2 == 3).sum() == (ids == 1).sum() + (ids2 == 3).sum() - ((ids == 1) & (ids2 == 3)).sum()
      and sorted(cf.part_sizes(fur)) == [1, 2, 3])
pg.part_soft = 4
settle(fur)
check('Part Soft 4: the borders blended, the strands still there', len(strands(fur)[0]) > 0)
for part in pg.parts:
    part.lie, part.flow = 0.0, 0.0
pg.gravity = 2.0
settle(fur)
P, _cv = strands(fur)
eq = np.abs(P[:, 0, 2]) < 0.1
drop = (P[eq, -1, 2] - P[eq, 0, 2]).mean()
check(f'Gravity 2 (standing out at the root): the strands bend down toward the tip (tips {-drop * 1000:.1f} mm below '
      f'their roots round the equator, the first segment still out of the skin)', drop < -0.02
      and np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', direction(P)[eq], P[eq, 0] / np.linalg.norm(P[eq, 0], axis=1)[:, None]), -1, 1))).mean() < 25)
pg.gravity = 0.0


def curliness(P):
    path = np.linalg.norm(np.diff(P, axis=1), axis=2).sum(1)
    return float(np.mean(path / np.maximum(np.linalg.norm(P[:, -1] - P[:, 0], axis=1), 1e-9)))


pg.segments = 32
settle(fur)
c0 = curliness(strands(fur)[0])


def allp(**kw):
    """(0.24.160 Curl / Clump / Tip Gather are each area's: every area set)"""
    for part_ in pg.parts:
        for k_, v_ in kw.items():
            setattr(part_, k_, v_)


allp(curl=1.0)
pg.curl_turns = 3.0
settle(fur)
c1 = curliness(strands(fur)[0])
check(f'Curl 1, 3 turns (32 segments): the strands curl (path / straight distance {c0:.2f} -> {c1:.2f})', c0 < 1.01 and c1 > 1.25)
allp(curl=0.0)
pg.frizz = 1.0
settle(fur)
cf_ = curliness(strands(fur)[0])
check(f'Frizz 1: a small wobble ({cf_:.3f}, straight {c0:.3f})', 1.015 < cf_ < 1.3)
pg.frizz = 0.0
pg.segments = 8


def tip_spread(P):
    from mathutils.kdtree import KDTree
    kd = KDTree(len(P))
    for i, p in enumerate(P[:, -1]):
        kd.insert(Vector(p), i)
    kd.balance()
    return float(np.mean([kd.find_n(Vector(p), 2)[1][2] for p in P[:, -1]]))


allp(clump=0.0)
pg.clump_size = 15
settle(fur)
P0, _cv = strands(fur)
s0 = tip_spread(P0)
allp(clump=1.0)
settle(fur)
P1, _cv = strands(fur)
s1 = tip_spread(P1)
tips_unique = len({tuple(np.round(p, 5)) for p in P1[:, -1]})
check(f'Clump 1, Clump Size 15: the tips meet in tufts ({tips_unique} tip spots for {len(P1)} strands, about 1 in 15; the '
      f'nearest other tip {s0 * 1000:.1f} -> {s1 * 1000:.2f} mm), the roots where they were',
      s1 < s0 * 0.05 and len(P1) / 30 < tips_unique < len(P1) / 7 and np.allclose(P0[:, 0], P1[:, 0], atol=1e-6))
allp(clump=0.4)
settle(fur)
P2, _cv = strands(fur)
check('Clump 0.4: halfway - the tips closer together, not met', s1 < tip_spread(P2) < s0)
allp(clump=0.0)
# 0.24.160 per area: Curl / Clump on one area only; Tip Gather - the area's tips to one point (the end of its tilt)
settle(fur)
ids = cf.part_ids(fur)
P0, _cv = strands(fur)
pg.parts[1].curl = 1.2
pg.curl_turns = 3.0
settle(fur)
P1, _cv = strands(fur)
r0 = P1[:, 0]
low = (r0[:, 2] < -0.6) & (r0[:, 2] > -0.8)
mid = np.abs(r0[:, 2]) < 0.1
check(f'Curl on Area 2 only: its strands curl (path / straight {curliness(P1[low]):.2f}), Area 1\'s stay straight '
      f'({curliness(P1[mid]):.2f})', curliness(P1[low]) > 1.2 and curliness(P1[mid]) < 1.01)
pg.parts[1].curl = 0.0
for i_, part_ in enumerate(pg.parts):
    part_.lie = math.radians(60)
pg.parts[1].gather = 1.0
settle(fur)
P2, _cv = strands(fur)
r0 = P2[:, 0]
low = (r0[:, 2] < -0.6) & (r0[:, 2] > -0.8)
mid = np.abs(r0[:, 2]) < 0.1
tip_sd_low = float(np.linalg.norm(P2[low, -1].std(axis=0)))
root_sd_low = float(np.linalg.norm(P2[low, 0].std(axis=0)))
tip_sd_mid = float(np.linalg.norm(P2[mid, -1].std(axis=0)))
check(f'Tip Gather 1 on Area 2: its tips meet in one point (their spread {tip_sd_low * 1000:.2f} mm, the roots '
      f'{root_sd_low * 1000:.0f} mm), its roots where they were; Area 1\'s tips as spread as before ({tip_sd_mid * 1000:.0f} mm)',
      low.sum() > 20 and tip_sd_low < 0.002 and root_sd_low > 0.05 and tip_sd_mid > 0.05)
pg.parts[1].gather = 0.5
settle(fur)
P3, _cv = strands(fur)
r0 = P3[:, 0]
low = (r0[:, 2] < -0.6) & (r0[:, 2] > -0.8)
half = float(np.linalg.norm(P3[low, -1].std(axis=0)))
check(f'... Tip Gather 0.5: halfway ({half * 1000:.1f} mm)', tip_sd_low < half < root_sd_low)
pg.parts[1].gather = 0.0
# Volume: the strands rise off the skin at the root and bend over into their tilt; Spread: each a little different
allp(lie=math.radians(80))
pg.volume = 1.0
settle(fur)
P4, _cv = strands(fur)
nn = P4[:, 0] / np.linalg.norm(P4[:, 0], axis=1)[:, None]
first = P4[:, 1] - P4[:, 0]
last = P4[:, -1] - P4[:, -2]
a_first = np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', first / np.linalg.norm(first, axis=1)[:, None], nn), -1, 1)))
a_last = np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', last / np.linalg.norm(last, axis=1)[:, None], nn), -1, 1)))
check(f'Volume 1 (Lie Down 80): each strand rises off the skin ({a_first.mean():.0f} deg off the normal at the root) and bends '
      f'over to its tilt at the tip ({a_last.mean():.0f} deg) - fuller', a_first.mean() < 25 and a_last.mean() > 70)
pg.volume = 0.0
pg.spread = 1.0
settle(fur)
P5, _cv = strands(fur)
nn = P5[:, 0] / np.linalg.norm(P5[:, 0], axis=1)[:, None]
d5 = (P5[:, 1] - P5[:, 0])
d5 /= np.linalg.norm(d5, axis=1)[:, None]
a5 = np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', d5, nn), -1, 1)))
check(f'Spread 1: each strand\'s tilt a little different (their tilts {a5.std():.1f} deg apart round {a5.mean():.0f})',
      a5.std() > 8)
pg.spread = 0.0
allp(lie=0.0)
check('new furs start fuller: Density 40000 a square metre, Root Thickness 1 mm, Volume 0.5, Spread 0.3',
      abs(cf.MCH_PG_Fur.bl_rna.properties['density'].default - 40000) < 1e-3
      and abs(cf.MCH_PG_Fur.bl_rna.properties['root_thick'].default - 0.001) < 1e-9
      and abs(cf.MCH_PG_Fur.bl_rna.properties['volume'].default - 0.5) < 1e-6)

# more area: draw again with the fur selected - the same fur, more strands; Alt: taken away
n_before = len(strands(fur)[0])
msg2 = cf.perform(C, ellipse(500, 360, 120, 60), FRONT)
P, _cv = strands(fur)
check(f'draw again (the fur selected): the same fur, its area bigger - {n_before:,} -> {len(P):,} strands',
      C.active_object == fur and len([o for o in S.objects if cf.is_fur(o)]) == 1 and len(P) > n_before * 1.3, msg2)
msg3 = cf.perform(C, [[(330, 250), (500, 250), (500, 700), (330, 700)]], FRONT, erase=True)   # (the left side)
P, _cv = strands(fur)
check(f'Alt + draw: the area taken away on the left - no root left of the middle now, but for the faces the line '
      f'crosses (the leftmost {P[:, 0, 0].min():.3f}; a face is 0.033 wide; {len(P):,} strands)',
      len(P) > 0 and P[:, 0, 0].min() > -0.033, msg3)
pg.edge_soft = 6
settle(fur)
P, _cv = strands(fur)
check(f'Edge Soft 6: the border thinned out, never past what was drawn (the leftmost root {P[:, 0, 0].min():.3f} still)',
      len(P) > 0 and P[:, 0, 0].min() > -0.033)
pg.edge_soft = 0

# a new fur: its own object and area
setattr(C.window_manager, cf.NEW_KEY, True)
cf.perform(C, ellipse(500, 650, 60, 40), FRONT)
furs = [o for o in S.objects if cf.is_fur(o)]
check('New Fur, then draw: a second fur with its own area (the first one unchanged)', len(furs) == 2
      and C.active_object != fur and furs[0][cf.AREA_KEY] != furs[1][cf.AREA_KEY])
fur2 = C.active_object

# live: values, the body changing, no polypaint
pg.length = 0.12
settle(fur)
P, _cv = strands(fur)
lens = np.linalg.norm(np.diff(P, axis=1), axis=2).sum(1)
check(f'live: Length 0.08 -> 0.12, every strand redone (longest {lens.max():.3f}); the next fur takes it too',
      0.115 < lens.max() < 0.121 and abs(S.mch_fur.length - 0.12) < 1e-6)
me.vertices.foreach_set('co', (co * 1.2).ravel())
me.update()
settle(fur)
P, _cv = strands(fur)
d = np.linalg.norm(P[:, 0], axis=1)
check(f'the body made 1.2 x bigger: the fur grows on it still (roots {d.min():.3f} .. {d.max():.3f} from the centre)',
      abs(d - 1.2).max() < 0.012)
fur.mch_fur.use_polypaint = False
settle(fur)
P, cv = strands(fur)
col = np.empty(len(cv.points) * 4, np.float32)
cv.attributes['mch_fur_col'].data.foreach_get('color', col)
check('Use Polypaint off: the Root Color at the roots', np.allclose(col.reshape(len(P), -1, 4)[:, 0, :3].mean(0),
                                                                  fur.mch_fur.root_color[:3], atol=0.02))
mat = bpy.data.materials.get(cf.MAT)
nodes = {n.bl_idname for n in mat.node_tree.nodes}
check('the material MCH Fur: the strand colour attribute into Principled Hair (Cycles) and Principled (EEVEE)',
      {'ShaderNodeAttribute', 'ShaderNodeBsdfHairPrincipled', 'ShaderNodeBsdfPrincipled'} <= nodes
      and fur.data.materials[0] == mat)

# Apply
for o in C.selected_objects:
    o.select_set(False)
fur.select_set(True)
C.view_layer.objects.active = fur
n = len(strands(fur)[0])
r = bpy.ops.mch.fur_apply()
check(f'Apply: {len(fur.data.curves):,} real hair curves (as many as it had), not live any more', 'FINISHED' in r
      and len(fur.data.curves) == n and not fur.modifiers and not cf.is_fur(fur))
# a high-poly body seen from the side: the area only where the view sees the body (the far arm's inside faces the view
# but is behind the chest)
import sys  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools_dev'))
import make_test_human as mth  # noqa: E402
human = mth.build(4)
nv = len(human.data.vertices)
C.view_layer.objects.active = human
SIDE = cg.OrthoProjector(Euler((math.pi / 2, 0, math.pi / 2)).to_quaternion(), center=Vector((0.3, 0.0, 1.3)),
                         pixels_per_unit=400.0)                  # (from +X: screen x = world y, screen y = z)
t0 = time.time()
idx = cf.area_points(C, human, ellipse(504, 500, 60, 60), SIDE)
t_area = time.time() - t0
hc = np.empty(nv * 3, np.float32)
human.data.vertices.foreach_get('co', hc)
hc = hc.reshape(-1, 3)
far = int(np.sum(hc[idx, 0] < -0.005))       # (the middle line itself: the back's edge, seen)
check(f'a {len(human.data.polygons):,}-face body from the side, an area over the near upper arm: {len(idx):,} points, '
      f'none on the far side (x < -0.005: the far arm\'s inside faces the view but the chest hides it - {far}), found in '
      f'{t_area:.2f} s', len(idx) > 100 and far == 0 and t_area < 3.0)
for o in C.selected_objects:
    o.select_set(False)
t0 = time.time()
cf.perform(C, ellipse(504, 500, 60, 60), SIDE)
hf = C.active_object
n_h = len(strands(hf)[0])
check(f'... the fur there: {n_h:,} strands, drawn and grown in {time.time() - t0:.2f} s', cf.is_fur(hf)
      and hf.parent == human and n_h > 0 and time.time() - t0 < 5.0)
summary()
