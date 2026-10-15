"""0.24.0 Plate Detail (trim: flat inside, 1/2/3 stepped layers, edge high / inside high, screw recesses) and
Plate Detail 2 (smooth rise): lasso tools of their own, live values, presets, apply / remove."""
import sys

_src = open(__file__.replace('test_v0240.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
import bmesh
import numpy as np

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
from mecha_lab import plate_detail as pd, tool_state as ts, bottom_bar as bb, ui_tool_settings as uts

check('two tools, lasso tools, bottom bar buttons', {'DETAIL', 'DETAIL2'} <= set(ts.TOOL_BY_ID) and
      {'DETAIL', 'DETAIL2'} <= ts.SHAPE_TOOLS and {'DETAIL', 'DETAIL2'} <= {t[0] for t in bb.BAR_TOOLS} and
      {'DETAIL', 'DETAIL2'} <= set(uts.DRAWERS))


def manifold(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    bad = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    bm.free()
    return bad == 0


def heights(ob, target):
    co = np.array([v.co[:] for v in ob.data.vertices])
    return co[:, 2] - target.dimensions.z / 2


MODE[0], NATIVE[0] = 'DETAIL', 'mecha.plate_detail'
S.mch_settings.mch_active_tool = 'DETAIL'
b = cube('B', 4.0)
r, m = lasso([(330, 330), (670, 330), (670, 670), (330, 670)])
d = C.active_object
p = d.mch_pdetail if d is not None else None
check('lasso on a mesh -> live detail parented to it', r == {'FINISHED'} and pd.is_detail(d) and d.parent == b and
      p.kind == 'TRIM' and p.layers == 2, m)
check('closed solid, B untouched', manifold(d.data) and len(b.data.polygons) == 6)
h = heights(d, b)
check('low: top below 5% of the size, bottom just under the surface', h.max() < p.size * 0.05 and h.min() < 0 and
      h.min() > -p.size * 0.01, (h.max(), h.min(), p.size))
top_edge = p.base + p.h1
check('edge high: the outer layer is the highest level', abs(h.max() - top_edge) < 1e-4, (h.max(), top_edge))
f0 = len(d.data.polygons)
p.w1 = p.w1 * 1.5
check('a change queues a rebuild', d.name in pd._PENDING)
bpy.app.timers.unregister(pd._rebuild_timer)
pd._rebuild_timer()
check('width change rebuilt the mesh', len(d.data.polygons) != f0 and manifold(d.data))
p.h1 = p.h1 * 2
pd.rebuild(d)
check('height change: higher edge', abs(heights(d, b).max() - (p.base + p.h1)) < 1e-4)
pd._PENDING.clear()
bpy.ops.mch.pdetail_layers(count=3)
check('3-layer preset: values from the preset for this size', p.layers == 3 and
      abs(p.w3 - pd.LAYER_PRESETS[3][2][0] * p.size) < 1e-6 and manifold(d.data))
p.direction = 'IN'
pd.rebuild(d)
hin = heights(d, b).max()
check('inside high: inside panel highest (sum of layers + inside height)',
      abs(hin - (p.base + p.h1 + p.h2 + p.h3 + p.center)) < 1e-4, hin)
p.screws = '2'
pd.rebuild(d)
check('2 screws', d.data.get('mch_detail_screws') == 2 and manifold(d.data))
pd._PENDING.clear()
check('values remembered for the next detail (as fractions)', S.mch_pdetail.layers == 3 and
      S.mch_pdetail.direction == 'IN' and S.mch_pdetail.screws == '2')
check('Select-mode panel shows for the live detail', pd.MCH_PT_plate_detail.poll(C) in (True, False))
bpy.ops.mch.pdetail_apply()
check('Apply: plain mesh, not live', not pd.is_detail(d) and len(d.data.polygons) > 0)

# ---- on an armour plate
MODE[0], NATIVE[0] = 'PLATE', 'mecha.armor_plate'
S.mch_settings.mch_active_tool = 'PLATE'
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
b2 = cube('B2', 4.0)
r, m = lasso([(330, 330), (670, 330), (670, 670), (330, 670)])
plate = C.active_object
MODE[0], NATIVE[0] = 'DETAIL', 'mecha.plate_detail'
S.mch_settings.mch_active_tool = 'DETAIL'
r, m = lasso([(400, 400), (600, 400), (600, 600), (400, 600)])
d2 = C.active_object
check('detail drawn over an armour plate lands on the plate', pd.is_detail(d2) and d2.parent == plate, m)

# ---- Detail 2
MODE[0], NATIVE[0] = 'DETAIL2', 'mecha.plate_detail2'
S.mch_settings.mch_active_tool = 'DETAIL2'
for o in (d2, plate):
    bpy.data.objects.remove(o)
r, m = lasso([(330, 330), (670, 330), (670, 670), (330, 670)])
rz = C.active_object
q = rz.mch_pdetail
check('Detail 2: smooth rise object', pd.is_detail(rz) and q.kind == 'RISE' and manifold(rz.data), m)
hz = heights(rz, b2)
check('rises to Height, edge at the surface', abs(hz.max() - (q.height + q.size * 0.0004)) < 1e-3 and
      abs(np.sort(hz)[len(hz) // 2]) >= 0, (hz.max(), q.height))
co = np.array([v.co[:] for v in rz.data.vertices])
top = co[hz > q.height * 0.99]
w_top = top[:, 0].max() - top[:, 0].min()
q.ramp = q.ramp * 2
pd.rebuild(rz)
co2 = np.array([v.co[:] for v in rz.data.vertices])
hz2 = heights(rz, b2)
w_top2 = co2[hz2 > q.height * 0.99][:, 0].max() - co2[hz2 > q.height * 0.99][:, 0].min()
check('wider slope = narrower top', w_top2 < w_top - 1e-3, (w_top, w_top2))
for prof in ('CHAMFER', 'DOME', 'FOOT'):
    q.profile = prof
    pd.rebuild(rz)
    check(f'slope shape {prof} builds', manifold(rz.data))
pd._PENDING.clear()
bpy.ops.mch.pdetail_remove()
check('Remove deletes it', not any(pd.is_detail(o) for o in bpy.data.objects))
mecha_lab.unregister()
check('unregister removes the properties', not hasattr(bpy.types.Object, 'mch_pdetail'))
sys.exit(1 if summary() else 0)
