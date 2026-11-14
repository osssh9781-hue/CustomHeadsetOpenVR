"""0.24.172 (user: "퍼 에드온에도 피부에 넣을 수 있는 페더 탭도 만들어 줘, 스케일이랑 이론은 같을 거 아냐, 그리고 비늘 탭도
그렇고 - 여기에 넣는 비늘도 좀 더 리얼하게" ... "지금 말한 거도 싹 다 엔터 누르면 어플라이 되게"): the Fur tool's
Feathers / Scales tabs - an area drawn on a body (the Fur tool's lasso, here the outline in pixels through a fixed front
view), feathers / scales lying down the body there, evenly spread, the free end lifted; live (instances), Enter makes
them real.  The real drawing: tests/gui/round172_real_window.py."""
import json
import math
import time

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Euler, Quaternion, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, creature_fur as cf, skin_cover as sc, workspace_ui as wu  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=96, ring_count=48)
body = C.active_object
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)   # 200 px = 1


def ellipse(cx, cy, rx, ry, n=64):
    return [[(cx + rx * math.cos(a), cy + ry * math.sin(a)) for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]]


def points(ob):
    me = ob.data
    n = len(me.vertices)
    P = np.empty(n * 3, np.float32)
    me.vertices.foreach_get('co', P)
    q = np.empty(n * 4, np.float32)
    me.attributes['mch_rot'].data.foreach_get('value', q)
    s = np.empty(n * 3, np.float32)
    me.attributes['mch_scale'].data.foreach_get('vector', s)
    k = np.empty(n, np.int32)
    me.attributes['mch_pick'].data.foreach_get('value', k)
    return P.reshape(-1, 3), q.reshape(-1, 4), s.reshape(-1, 3), k


def axes(q):
    Q = Quaternion(q)
    return np.array(Q @ Vector((1, 0, 0))), np.array(Q @ Vector((0, 0, 1)))


def instances(ob):
    dg = C.evaluated_depsgraph_get()
    return sum(1 for d in dg.object_instances if d.is_instance and d.parent is not None and d.parent.original == ob)


st = S.mch_cover
check('the Fur tool has three tabs (Fur / Feathers / Scales); Feathers starts with its own values',
      [i.identifier for i in st.bl_rna.properties['grow'].enum_items] == ['FUR', 'FEATHERS', 'SCALES']
      and st.grow == 'FUR')
st.grow = 'FEATHERS'
check('Feathers: its own start (Size 4 %, Contour feather)', abs(st.size - 4.0) < 1e-6
      and json.loads(st.shapes_json) == ['CONTOUR'], (st.size, st.shapes_json))

t0 = time.time()
msg = cf.perform(C, ellipse(500, 520, 130, 100), FRONT)          # (the Fur tool's draw: on the Feathers tab)
dt = time.time() - t0
cov = C.active_object
P, Q, SC, K = points(cov)
check(f'a drawn area: feathers there ({len(P)} of them, {dt:.2f} s), a cover object on the body (its child), live '
      f'(instances: {instances(cov)})', sc.is_cover(cov) and cov.parent == body and 100 < len(P) < 3000
      and cov.modifiers.get('MCH Greeble') is not None and instances(cov) == len(P) and not cf.is_fur(cov), msg)
size = sc.body_size(body) * st.size / 100.0
_k, shp = sc.cover_shapes(C, cov)
along, across = sc.spacings(cov.mch_cover, size, shp)
d = np.linalg.norm(P[:, None, :] - P[None, :, :], axis=2) + np.eye(len(P)) * 9
sx, sy = 500 + P[:, 0] * 200, 500 + P[:, 2] * 200
inside = ((sx - 500) / 130) ** 2 + ((sy - 520) / 100) ** 2
xs0 = np.array([axes(q)[0] for q in Q])
nn = d.argmin(1)
dd = P[nn] - P
da = np.abs((dd * xs0).sum(1))
fresh_shapes = {k: o for k, o in shp.items()}
ext = [sc.shape_extent(o) for o in fresh_shapes.values()]
check(f'its shapes measured from their points (a hidden shape just made has no bounding box yet): {ext}',
      all(e[0] > 0.01 and e[1] > 0.005 for e in ext))
check(f'spread like a coat: none closer than Spacing x their length along the way they lie ({along:.4f}) or Side '
      f'Spacing x their width side by side ({across:.4f}): nearest {d.min():.4f}; the nearest one mostly along '
      f'({np.median(da / d.min(1)):.2f}), all on the front inside the outline (worst {inside.max():.2f})',
      d.min() >= min(along, across) * 0.97 and along < across * 1.5 and inside.max() < 1.12 and np.all(P[:, 1] < 0))
xs = np.array([axes(q)[0] for q in Q])
zs = np.array([axes(q)[1] for q in Q])
nrm = P / np.linalg.norm(P, axis=1)[:, None]
lift = np.degrees(np.arcsin(np.clip((xs * nrm).sum(1), -1, 1)))
down = -xs[:, 2]
check(f'lying down the body (each one\'s length pointing down: {down.min():.2f}..{down.mean():.2f}), the free end '
      f'lifted by Lift ({lift.mean():.1f} deg, Lift {math.degrees(st.lift):.0f}), its face out',
      down.min() > 0.3 and abs(lift.mean() - math.degrees(st.lift)) < 1.0 and np.all((zs * nrm).sum(1) > 0.7))
L0 = SC[:, 0].copy()
check(f'size: Size x the feather\'s own length, a little random (length {L0.min():.3f}..{L0.max():.3f})',
      L0.std() > 0 and abs(np.median(L0) / (size * cov.mch_cover.size_random + size) - 1) < 0.6)

cov.mch_cover.lift = math.radians(35)                             # (live: its sliders lay them again)
P2, Q2, _s, _k = points(cov)
xs = np.array([axes(q)[0] for q in Q2])
nrm = P2 / np.linalg.norm(P2, axis=1)[:, None]
lift2 = np.degrees(np.arcsin(np.clip((xs * nrm).sum(1), -1, 1))).mean()
cov.mch_cover.flow = math.radians(90)
_P, Q3, _s, _k = points(cov)
xs3 = np.array([axes(q)[0] for q in Q3])
cov.mch_cover.length = 2.0
_P, _q, SC4, _k = points(cov)
check(f'live sliders: Lift 35 -> {lift2:.1f} deg, Flow Angle 90 -> sideways (down {(-xs3[:, 2]).mean():.2f}), '
      f'Length x2 -> {np.median(SC4[:, 0]) / np.median(SC[:, 0]):.2f} x (fewer: {len(SC)} -> {len(SC4)}), the next one starts like it (scene Lift '
      f'{math.degrees(st.lift):.0f})', abs(lift2 - 35) < 1.0 and abs((-xs3[:, 2]).mean()) < 0.25
      and abs(np.median(SC4[:, 0]) / np.median(SC[:, 0]) - 2.0) < 0.1 and len(SC4) < len(SC) * 0.7 and abs(math.degrees(st.lift) - 35) < 0.1)
cov.mch_cover.flow = 0.0
cov.mch_cover.length = 1.0

bpy.ops.mch.cover_shape(shape='OWL')
ng = cov.modifiers['MCH Greeble'].node_group
objs = [n.inputs['Object'].default_value for n in ng.nodes if n.bl_idname == 'GeometryNodeObjectInfo']
st.mix = True
bpy.ops.mch.cover_shape(shape='PRIMARY')
_P, _q, _s, K2 = points(cov)
ng = cov.modifiers['MCH Greeble'].node_group
objs2 = [n.inputs['Object'].default_value for n in ng.nodes if n.bl_idname == 'GeometryNodeObjectInfo']
check(f'a feather button: that feather ({[o.name for o in objs]}); Mix on: two of them, each one picks one '
      f'({[o.name for o in objs2]}, {np.bincount(K2).tolist()})', len(objs) == 1 and 'Owl' in objs[0].name
      and len(objs2) == 2 and set(K2.tolist()) == {0, 1} and json.loads(cov.mch_cover.shapes_json) == ['OWL', 'PRIMARY'])
st.mix = False

n_before = len(cov.data.vertices)
cf.perform(C, ellipse(500, 520, 60, 50), FRONT, erase=True)     # (Alt + draw: the middle taken away)
P5, *_r = points(cov)
sx, sy = 500 + P5[:, 0] * 200, 500 + P5[:, 2] * 200
mid = ((sx - 500) / 60) ** 2 + ((sy - 520) / 50) ** 2
check(f'Alt + draw: area taken away ({n_before} -> {len(P5)}, none left in the middle: nearest {mid.min():.2f})',
      len(P5) < n_before and mid.min() > 0.7 and C.active_object == cov)

mat = bpy.data.materials.new('Green Feathers')
cov.data.materials.append(mat)
bpy.context.view_layer.update()
from mecha_lab import greeble_line as gl  # noqa: E402
gl.sync_material(cov)
check('a material given to the cover: on every feather, live (no Apply)', gl.line_material(cov) == mat
      and bool(cov.modifiers['MCH Greeble'].node_group and
               __import__('mecha_lab.geo_sculpt', fromlist=['x']).get_input(cov.modifiers['MCH Greeble'], 'Use Material')))
cov.data.materials.clear()
gl.sync_material(cov)

st.grow = 'SCALES'
check('Scales: its own start (Size 2.2 %, Keeled scale)', abs(st.size - 2.2) < 1e-6
      and json.loads(st.shapes_json) == ['KEELED'])
cf.perform(C, ellipse(500, 420, 110, 80), FRONT)                 # (the feathers selected: scales are a new one)
sca = C.active_object
Ps, Qs, SCs, Ks = points(sca)
check(f'the Scales tab: a new cover of scales ({len(Ps)}), the feathers kept ({len(cov.data.vertices)})',
      sca != cov and sc.is_cover(sca) and sca.mch_cover.grow == 'SCALES' and len(Ps) > 30
      and len(cov.data.vertices) == len(P5) and sca.name.startswith('Scales'))
ns = Ps / np.linalg.norm(Ps, axis=1)[:, None]
dep = (Ps * ns).sum(1) - 1.0
check(f'scales sit a little into the skin (Sink: {dep.mean():.4f})', dep.mean() < 0)

target = wu.enter_apply_target(C)
check(f'Enter applies the selected scales ({target})', target is not None and target[0] == 'cover_apply')
area = sca[sc.AREA_KEY]
bpy.ops.mch.cover_apply()
check(f'applied: one real mesh ({len(sca.data.polygons):,} faces), not live, its area gone from the body',
      not sc.is_cover(sca) and len(sca.data.polygons) > 50 * len(Ps) and not sca.modifiers
      and body.data.attributes.get(area) is None and sca.name.startswith('Scales'))

st.grow = 'FEATHERS'
setattr(C.window_manager, cf.NEW_KEY, True)
cf.perform(C, ellipse(500, 420, 60, 40), FRONT)                  # (drawn over the applied scales)
over = C.active_object
check(f'drawn over applied scales: on the body under them ({over.parent and over.parent.name}), not on the scales',
      sc.is_cover(over) and over.parent == body)
st.grow = 'FUR'
S.mch_fur.density, S.mch_fur.length = 3000.0, 0.05
for o in C.selected_objects:
    o.select_set(False)
cf.perform(C, ellipse(500, 600, 80, 60), FRONT)
fur = C.active_object
check('the Fur tab: fur as before', cf.is_fur(fur))
tg = wu.enter_apply_target(C)
r = getattr(bpy.ops.mch, tg[0])() if tg else None              # (what Enter runs - its poll wants the 3D view)
check(f'Enter on a live fur: Apply ({tg}) - real hair curves', tg is not None and tg[0] == 'fur_apply'
      and r == {'FINISHED'} and not cf.is_fur(fur) and len(fur.data.curves) > 50, r)
for o in C.selected_objects:
    o.select_set(False)
cov.select_set(True)
C.view_layer.objects.active = cov
target = wu.enter_apply_target(C)
check(f'Enter applies the feathers too ({target}); the Fur: Enter as well ("fur_apply" in the list)',
      target is not None and target[0] == 'cover_apply' and 'fur_apply' in dict(wu.ENTER_APPLY))

st.grow = 'FEATHERS'
st.size = 1.0
st.spacing = 0.3
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=128, ring_count=64, location=(5, 0, 0))
big = C.active_object
t0 = time.time()
cf.perform(C, ellipse(1500, 500, 230, 230), FRONT)
dt = time.time() - t0
check(f'a big area with small feathers stays quick ({len(C.active_object.data.vertices):,} feathers in {dt:.2f} s)',
      dt < 12.0 and len(C.active_object.data.vertices) > 300)

summary()
