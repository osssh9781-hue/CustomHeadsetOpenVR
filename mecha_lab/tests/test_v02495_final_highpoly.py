"""0.24.95 (user picked 2 + 6 + 5 of the ideas): parts already made take a new Resolution (Apply to Parts); a slow
part shown at the Preview Resolution while a slider is dragged, made at the full one after; Final High Poly - high
copies at the Final Resolution, Round Facets / Bake Maps if on, <file>_low.fbx + <file>_high.fbx."""
import inspect
import json
import math
import os
import tempfile
import time

from _harness import bpy, check, cube, fresh, summary
from mathutils import Quaternion

import mecha_lab
from mecha_lab import base_mesh as bm_mod, core_geometry as cg, cut_engine as ce, final_export as fe
from mecha_lab import live_queue as lq, mesh_tools, res_parts, tool_state as ts, top_bar, zb_ui

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion())

# ---- the outline resampler
circ = [(math.cos(2 * math.pi * i / 64) * 100, math.sin(2 * math.pi * i / 64) * 100) for i in range(64)]
up = cg.reres_loop(circ, 2.0)
down = cg.reres_loop(circ, 0.5)
dev = max(abs(math.hypot(*p) - 100.0) for p in up)
check('reres_loop: a 64-gon circle x2 -> 128 points on the circle (within 0.05 % of the radius), x0.5 -> 32, x1 the same',
      len(up) == 128 and dev < 0.05 and len(down) == 32 and cg.reres_loop(circ, 1.0) == circ, (len(up), dev, len(down)))
rect = [(0.0, 0.0), (300.0, 0.0), (300.0, 200.0), (0.0, 200.0)]
check('... a sharp rectangle stays exactly as it is (corners, straight sides)', cg.reres_loop(rect, 3.0) == rect)
lg = ce.StrokeLogic.__new__(ce.StrokeLogic)
lg.brush = S.mch_brush
S.mch_brush.outline_corner, S.mch_brush.outline_radius, S.mch_brush.outline_segments = 'ROUND', 40.0, 6
rr = lg._outline([(400.0, 400.0), (700.0, 400.0), (700.0, 600.0), (400.0, 600.0)])
S.mch_brush.outline_corner = 'NONE'
rr2 = cg.reres_loop(rr, 2.0)
xs = sorted({round(p[0], 6) for p in rr2 if abs(p[1] - 400.0) < 1e-6})
check('... a rounded rectangle: the corners get 2x the points, the straight sides stay single straight edges',
      len(rr2) > 1.8 * len(rr) and len(xs) == 2, (len(rr), len(rr2), xs))


# ---- 2. parts already made
def circle_loop(r=80.0):
    lg = ce.StrokeLogic.__new__(ce.StrokeLogic)
    lg.brush, lg.shape, lg.anchor = S.mch_brush, 'CIRCLE', (500.0, 500.0)
    return lg._drag_loops((500.0 + r, 500.0), False, False)[0]


def base_part(loc_x=0.0):
    s = S.mch_base
    s.profile, s.bevel_segments, s.bevel_width, s.height = 'BEVEL', 4, 0.05, 0.3
    before = set(bpy.data.objects)
    bm_mod.perform_base(C, [circle_loop()], TOP)
    ob = [o for o in bpy.data.objects if o not in before][0]
    ob.location.x += loc_x
    return ob


S.mch_settings.geo_res = 100
part = base_part()
check('Base Mesh remembers the Resolution it was drawn at (100 %)', json.loads(part.mch_base.outline).get('res') == 1.0
      and len(part.data.vertices) == 64 * 6)
S.mch_settings.geo_res = 200
fresh_200 = base_part(3.0)
n_new = len(fresh_200.data.vertices)
bpy.data.objects.remove(fresh_200)
plain = cube(name='Plain', size=1.0, loc=(-3, 0, 0))
for o in C.selected_objects:
    o.select_set(False)
r = bpy.ops.mch.apply_resolution()
check('Apply to Parts at 200 % (nothing selected = all): the 100 % part now has exactly the points of a new 200 % '
      'part (round outline 64 -> 128, bevel rows 4 -> 8); the plain cube is left as it is',
      r == {'FINISHED'} and len(part.data.vertices) == n_new == 128 * 10 and len(plain.data.vertices) == 8,
      (len(part.data.vertices), n_new))
ext = max(v.co.x for v in part.data.vertices) - min(v.co.x for v in part.data.vertices)
check('... the same size (the resampled outline lies on the old circle)', abs(ext - 1.6) < 0.01, ext)
S.mch_settings.geo_res = 100
res_parts.apply(C, [part])
check('... and back at 100 %: the part as it was made (64 x 6 points)', len(part.data.vertices) == 64 * 6)
old_json = json.loads(part.mch_base.outline)
old_json.pop('res')
part.mch_base.outline = json.dumps(old_json)
S.mch_settings.geo_res = 200
res_parts.apply(C, [part])
check('A part from before (no Resolution stored) counts as drawn at 100 %', len(part.data.vertices) == 128 * 10)
S.mch_settings.geo_res = 100
counts, left, failed = res_parts.apply(C, [part, plain])
msg = res_parts.describe(counts, left, failed)
check('The message: what was made again and what was kept', counts == {'Base Mesh': 1} and left == ['Plain']
      and 'Base Mesh' in msg and 'kept' in msg, msg)
cells = dict(top_bar.groups(C, 'BASE'))['Resolution']
check('Top bar Resolution group: Res + "Apply to Parts" (mch.apply_resolution)',
      any(c[3] == ('op', 'mch.apply_resolution', {}) for c in cells if isinstance(c, tuple) and len(c) > 3)
      or 'mch.apply_resolution' in inspect.getsource(top_bar))

# ---- 6. Fast Preview while dragging
st = S.mch_settings
seen = []


def fn():
    seen.append(ts.res_scale())


st.geo_res, st.geo_draft, st.geo_draft_res = 400, True, 100
lq._FULLCOST['k'] = 1.0                         # (a slow part: its full rebuild took 1 s)
lq._PENDING['k'] = fn
lq._TOUCH['k'] = time.perf_counter()
lq._tick()
in_full = 'k' in lq._FULL
lq._TOUCH['k'] = time.perf_counter() - 1.0      # (the drag stopped a second ago)
lq._settle()
check('Fast Preview: a slow part is made at the Preview Resolution (100 %) during the drag, then once at the full '
      'one (400 %) when the drag stops', seen == [1.0, 4.0] and in_full and 'k' not in lq._FULL, seen)
seen.clear()
lq._FULLCOST['k'] = 0.01
lq._PENDING['k'] = fn
lq._tick()
check('... a fast part (0.01 s) is always made at the full Resolution (no second run)', seen == [4.0] and 'k' not in lq._FULL,
      seen)
seen.clear()
st.geo_draft = False
lq._FULLCOST['k'] = 1.0
lq._PENDING['k'] = fn
lq._tick()
check('... Fast Preview off: the full Resolution even for a slow part', seen == [4.0], seen)
seen.clear()
st.geo_draft = True
lq._FULLCOST['k'] = 1.0
lq._PENDING['k'] = fn
lq._tick()
lq.flush()
check('... flush (before Apply / export) makes a part waiting for its full run at the full Resolution', seen == [1.0, 4.0]
      and not lq._FULL, seen)
st.geo_res = 100
seen.clear()
lq._PENDING['k'] = fn
lq._tick()
check('... Resolution not above the Preview one: no preview run at all', seen == [1.0] and not lq._FULL, seen)
lq.drop()

# ---- 5. Final High Poly
tmp = tempfile.mkdtemp(prefix='mch_final_')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(tmp, 'robot.blend'))
S = C.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
S.mch_settings.geo_res = 100
part = base_part()
plain = cube(name='Plain', size=1.0, loc=(-3, 0, 0))
n_low = len(part.data.vertices)
for o in C.selected_objects:
    o.select_set(False)
fst = S.mch_final
fst.final_res, fst.export, fst.round_facets, fst.bake = 200, True, False, False
r = bpy.ops.mch.final_highpoly()
info = dict(fe.LAST)
hi = bpy.data.objects.get(part.name + '_high')
hplain = bpy.data.objects.get('Plain_high')
check('Final High Poly (nothing selected = every visible part): a "_high" copy of each in "MCH Final High", hidden',
      r == {'FINISHED'} and hi is not None and hplain is not None and hi.hide_get() and hplain.hide_get()
      and hi.users_collection[0].name == fe.COLL and info['parts'] == 2, info)
check('... the Base Mesh copy made again at 200 % (128 x 10 points), the plain cube copied as it is (8)',
      len(hi.data.vertices) == 128 * 10 and len(hplain.data.vertices) == 8 and info['rebuilt'] == 1,
      (len(hi.data.vertices), len(hplain.data.vertices)))
check('... the working part untouched (still live, 64 x 6 points) and the scene Resolution back at 100 %',
      part.mch_base.live and len(part.data.vertices) == n_low and S.mch_settings.geo_res == 100)
low_f = os.path.join(tmp, 'final_export', 'robot_low.fbx')
high_f = os.path.join(tmp, 'final_export', 'robot_high.fbx')
check('... robot_low.fbx and robot_high.fbx written to //final_export/ (the high one bigger)',
      os.path.isfile(low_f) and os.path.isfile(high_f) and os.path.getsize(high_f) > os.path.getsize(low_f),
      (info['files'], os.path.getsize(high_f) if os.path.isfile(high_f) else None))
fst.round_facets, fst.round_faces, fst.export = True, 40000, False
r = bpy.ops.mch.final_highpoly()
hi2 = bpy.data.objects.get(part.name + '_high')
check('Again with Round Facets: the earlier copy replaced (one "_high" each), subdivided towards the target',
      r == {'FINISHED'} and len([o for o in bpy.data.objects if o.name.startswith(part.name + '_high')]) == 1
      and len(hi2.data.polygons) > 4 * 1280 * 0.5 and fe.LAST['rounded'] == 2, (len(hi2.data.polygons), fe.LAST))
fst.round_facets, fst.bake = False, True
S.mch_bake.res, S.mch_bake.ao_samples, S.mch_bake.save = '256', 4, False
part.select_set(True)
r = bpy.ops.mch.final_highpoly()
check('Bake Maps on: the selected part only; its high copy baked onto it (Normal + AO images)',
      r == {'FINISHED'} and fe.LAST['parts'] == 1 and fe.LAST['baked'] == 1
      and bpy.data.images.get(part.name + '_Normal') is not None, fe.LAST)
check('In the Mecha Lab tab (Mesh Tools) and the ZBrush tab, after Bake Maps',
      'final_export.draw' in inspect.getsource(mesh_tools.draw) and 'final_export.draw' in inspect.getsource(zb_ui))
fresh()
C.scene.mch_final.export = True
try:
    fe.folder_path(C, C.scene.mch_final) if not bpy.data.filepath else None
    refused = bool(bpy.data.filepath)
except RuntimeError as ex:
    refused = 'save' in str(ex)
check('An unsaved file with the //folder: refused with a hint (save first or pick a folder)', refused)
summary()
