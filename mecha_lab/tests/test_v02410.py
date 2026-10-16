"""0.24.10 two new tools in the tool list: Plate Detail 3 (the Plate Detail 1 build without trim layers - a flat
raised panel with straight walls, Height / Lift live) and Mesh Curve Same Size (Repeat with every copy the same
size: point radius and start / end size ignored, Radius / Size scale all copies together)."""
import sys

_src = open(__file__.replace('test_v02410.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
import bmesh
import numpy as np
from mathutils import Vector

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
from mecha_lab import plate_detail as pd, tool_state as ts, bottom_bar as bb, ui_tool_settings as uts, \
    workspace_ui as wui, lasso_sketch as ls, curve_tube as ct

for tid in ('DETAIL3', 'TUBE_SAME'):
    check(f'{tid}: in the tool list, bottom bar, settings drawer', tid in ts.TOOL_BY_ID and
          tid in {t[0] for t in bb.BAR_TOOLS} and tid in uts.DRAWERS and
          tid in {i[0] for i in ts.TOOL_ENUM_ITEMS})
check('DETAIL3 is a lasso tool with sketch and a native tool', 'DETAIL3' in ts.SHAPE_TOOLS and 'DETAIL3' in ls.MODES
      and ts.TOOL_BY_ID['DETAIL3'][5] == 'mecha.plate_detail3' and wui.MCH_TOOL_plate_detail3 in wui.NATIVE_TOOLS)


def manifold(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    bad = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    bm.free()
    return bad == 0


MODE[0], NATIVE[0] = 'DETAIL3', 'mecha.plate_detail3'
S.mch_settings.mch_active_tool = 'DETAIL3'
b = cube('B', 4.0)
r, m = lasso([(330, 330), (670, 330), (670, 670), (330, 670)])
d = C.active_object
p = d.mch_pdetail if d is not None else None
check('lasso -> live flat panel parented to the mesh', r == {'FINISHED'} and pd.is_detail(d) and d.parent == b and
      p.kind == 'FLAT' and 'flat panel' in m, m)
z = np.array([v.co.z for v in d.data.vertices]) - b.dimensions.z / 2
top = z.max()
check('one flat top at Height (no trim levels): only two height levels (top, embedded bottom)',
      abs(top - p.flat_h) < 1e-4 and len({round(v, 5) for v in z}) == 2, sorted({round(v, 5) for v in z}))
check('height about 2% of the size by default', abs(p.flat_h - p.size * pd.FLAT_FRAC) < 1e-6, (p.flat_h, p.size))
check('closed solid, light, the mesh under it untouched', manifold(d.data) and len(d.data.polygons) < 200 and
      len(b.data.polygons) == 6, len(d.data.polygons))
xs = np.array([v.co.x for v in d.data.vertices])
tops = np.array([v.co.x for v in d.data.vertices if v.co.z - 2.0 > top - 1e-4])
check('straight walls: the top reaches the outline (as wide as the bottom)', abs(tops.max() - xs.max()) < 1e-4 and
      abs(tops.min() - xs.min()) < 1e-4)
p.flat_h = p.flat_h * 2
pd._PENDING.clear()
if bpy.app.timers.is_registered(pd._rebuild_timer):
    bpy.app.timers.unregister(pd._rebuild_timer)
pd.rebuild(d)
z2 = np.array([v.co.z for v in d.data.vertices]) - b.dimensions.z / 2
check('Height live', abs(z2.max() - p.flat_h) < 1e-4)
p.lift = 0.05
pd.rebuild(d)
z3 = np.array([v.co.z for v in d.data.vertices]) - b.dimensions.z / 2
check('Lift moves it along the normal', abs(z3.max() - (p.flat_h + 0.05)) < 1e-4)
check('Enter applies it (same Enter as the other details)', wui.enter_apply_target(C) == ('pdetail_apply', 'Plate Detail'))
for k in ('TRIM', 'RISE', 'FLAT'):
    check(f'sidebar maps {k} to its tool', pd.TOOL_OF_KIND[k] in {'DETAIL', 'DETAIL2', 'DETAIL3'})
# Plate Detail 1 unchanged
MODE[0], NATIVE[0] = 'DETAIL', 'mecha.plate_detail'
S.mch_settings.mch_active_tool = 'DETAIL'
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
b = cube('B1', 4.0)
r, m = lasso([(330, 330), (670, 330), (670, 670), (330, 670)])
d1 = C.active_object
check('Plate Detail 1 still makes a layered trim', d1.mch_pdetail.kind == 'TRIM' and d1.mch_pdetail.layers >= 1 and
      len({round(v.co.z, 5) for v in d1.data.vertices}) > 2)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)

# ---- Mesh Curve Same Size
src = cube('Src', 1.0)
tube = ct.new_tube(C, Vector((0, 0, 0)), mode='REPEAT_SAME')
check('new curve in Same Size mode', tube.mch_tube.mode == 'REPEAT_SAME')
tb = tube.mch_tube
tb.source = src
tb.count = 4
tb.radius = 0.1
tb.taper_start, tb.taper_end = 0.5, 2.0
ct.set_points(tube, [(Vector((0, 0, 0)), 1.0), (Vector((2, 0, 0)), 3.0), (Vector((4, 0, 0)), 0.3)])
ct.rebuild(tube)


def copy_sizes(ob, n):
    co = np.array([v.co[:] for v in ob.data.vertices])
    per = len(co) // n
    return [float(np.ptp(co[i * per:(i + 1) * per], axis=0).max()) for i in range(n)]


sz = copy_sizes(tube, 4)
check('Same Size: 4 copies, all the same size despite point radius / start-end size',
      len(tube.data.vertices) == 4 * 8 and max(sz) - min(sz) < 1e-5, sz)
tb.radius = 0.2
ct.rebuild(tube)
sz2 = copy_sizes(tube, 4)
check('Radius scales every copy together (x2)', all(abs(b_ / a_ - 2.0) < 1e-4 for a_, b_ in zip(sz, sz2)), sz2)
tb.size = 0.5
ct.rebuild(tube)
sz3 = copy_sizes(tube, 4)
check('Size scales every copy together (x0.5)', all(abs(b_ / a_ - 0.5) < 1e-4 for a_, b_ in zip(sz2, sz3)), sz3)
tb.mode = 'REPEAT'
ct.rebuild(tube)
szr = copy_sizes(tube, 4)
check('normal Repeat still follows the point radius / start-end size', max(szr) - min(szr) > 1e-3, szr)
check('Same Size curves are followed for source edits like Repeat', 'REPEAT_SAME' in ct.REPEAT_MODES)
check('tool pick passes the mode to the draw operator', 'mode' in ct.MCH_OT_tube_draw.__annotations__)

mecha_lab.unregister()
sys.exit(1 if summary() else 0)
