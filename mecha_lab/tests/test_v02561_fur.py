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
check('Root / Tip Thickness 0.8 mm / 0.12 mm: the radius half of it at the root and the tip',
      abs(rad[:, 0].mean() - 0.0004) < 1e-6 and abs(rad[:, -1].mean() - 0.00006) < 1e-6)
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
pg.lie, pg.gravity = 0.0, 0.0
settle(fur)
P, cv = strands(fur)
roots = P[:, 0]
nrm = roots / np.linalg.norm(roots, axis=1)[:, None]
straight = np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', direction(P), nrm), -1, 1)))
tipdir = (P[:, -1] - P[:, 0]) / np.linalg.norm(P[:, -1] - P[:, 0], axis=1)[:, None]
tipang = np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', tipdir, nrm), -1, 1)))
check(f'Lie Down 0, Gravity 0: every strand straight out of the skin (worst {max(straight.max(), tipang.max()):.1f} deg '
      f'from the normal, root and tip)', max(straight.max(), tipang.max()) < 2.0)
pg.lie = math.pi / 2                                               # (Lie Down: an angle from the normal - 90 flat)
settle(fur)
P, _cv = strands(fur)
dd = direction(P)
nrm = P[:, 0] / np.linalg.norm(P[:, 0], axis=1)[:, None]
eq = np.abs(P[:, 0, 2]) < 0.1
flat = np.abs(np.einsum('ij,ij->i', dd, nrm)).max()
check(f'Lie Down 90 deg (Flow 0): flat on the skin (|dir . normal| at most {flat:.3f}), pointing down the body round the '
      f'equator (dir.z {dd[eq, 2].mean():.2f})', flat < 0.03 and dd[eq, 2].mean() < -0.95)
pg.flow = math.radians(90)
settle(fur)
P, _cv = strands(fur)
dd = direction(P)
eq = np.abs(P[:, 0, 2]) < 0.1
side = np.abs(dd[eq, 0]).mean()
check(f'Flow Angle 90: the fur lies sideways instead (|dir.x| {side:.2f}, dir.z {dd[eq, 2].mean():.2f})',
      side > 0.9 and abs(dd[eq, 2].mean()) < 0.1)
pg.flow = 0.0
# combing (Shift + drag): a drag to the right across the middle - the fur under the brush lies to the right, the rest
# down the body as before
comb = cf.Comb(C, fur, FRONT, radius=40.0, strength=1.0)
k = sum(comb.step((440 + 20 * i, 500), (460 + 20 * i, 500)) for i in range(6))
settle(fur)
P, _cv = strands(fur)
dd = direction(P)
r0 = P[:, 0]
sx_, sy_ = 500 + r0[:, 0] * 200, 500 + r0[:, 2] * 200
under = (np.abs(sy_ - 500) < 15) & (sx_ > 450) & (sx_ < 550)
away = np.abs(sy_ - 500) > 70
check(f'Comb: a drag to the right across the middle ({k} points of the body combed) - the fur under the brush lies to '
      f'the right (dir.x {dd[under, 0].mean():.2f}), flat on the skin still; away from it down the body (dir.z '
      f'{dd[away, 2].mean():.2f})', under.sum() > 20 and dd[under, 0].mean() > 0.9
      and np.abs(np.einsum('ij,ij->i', dd[under], r0[under] / np.linalg.norm(r0[under], axis=1)[:, None])).max() < 0.05
      and dd[away, 2].mean() < -0.9)
pg.lie = math.radians(45)
settle(fur)
P, _cv = strands(fur)
dd = direction(P)
r0 = P[:, 0]
sx_, sy_ = 500 + r0[:, 0] * 200, 500 + r0[:, 2] * 200
under = (np.abs(sy_ - 500) < 15) & (sx_ > 450) & (sx_ < 550)
nn = r0 / np.linalg.norm(r0, axis=1)[:, None]
ang = np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', dd, nn), -1, 1)))
check(f'... Lie Down 45 deg: the combed fur 45 deg off the normal (measured {ang[under].mean():.1f}), leaning to the '
      f'right (dir.x {dd[under, 0].mean():.2f})', abs(ang[under].mean() - 45) < 3 and dd[under, 0].mean() > 0.6)
pg.lie = math.pi / 2
settle(fur)
P, _cv = strands(fur)                                               # (before the drag that Esc takes back)
comb2 = cf.Comb(C, fur, FRONT, radius=40.0, strength=1.0)
comb2.step((500, 600), (500, 640))                                  # (an upward drag lower down ...)
comb2.undo()                                                        # (... Esc: taken back)
settle(fur)
P2, _cv = strands(fur)
check('... Esc during a drag: the combing as it was before that drag (every strand the same)', P2.shape == P.shape
      and np.allclose(P2, P, atol=1e-5))
cf.clear_comb(fur)
settle(fur)
P, _cv = strands(fur)
dd = direction(P)
eq = np.abs(P[:, 0, 2]) < 0.1
check(f'Clear Comb: down the body again (dir.z {dd[eq, 2].mean():.2f})', dd[eq, 2].mean() < -0.95)
pg.lie = 0.0
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
pg.curl, pg.curl_turns = 1.0, 3.0
settle(fur)
c1 = curliness(strands(fur)[0])
check(f'Curl 1, 3 turns (32 segments): the strands curl (path / straight distance {c0:.2f} -> {c1:.2f})', c0 < 1.01 and c1 > 1.25)
pg.curl = 0.0
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


pg.clump, pg.clump_size = 0.0, 15
settle(fur)
P0, _cv = strands(fur)
s0 = tip_spread(P0)
pg.clump = 1.0
settle(fur)
P1, _cv = strands(fur)
s1 = tip_spread(P1)
tips_unique = len({tuple(np.round(p, 5)) for p in P1[:, -1]})
check(f'Clump 1, Clump Size 15: the tips meet in tufts ({tips_unique} tip spots for {len(P1)} strands, about 1 in 15; the '
      f'nearest other tip {s0 * 1000:.1f} -> {s1 * 1000:.2f} mm), the roots where they were',
      s1 < s0 * 0.05 and len(P1) / 30 < tips_unique < len(P1) / 7 and np.allclose(P0[:, 0], P1[:, 0], atol=1e-6))
pg.clump = 0.4
settle(fur)
P2, _cv = strands(fur)
check('Clump 0.4: halfway - the tips closer together, not met', s1 < tip_spread(P2) < s0)
pg.clump = 0.0

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
