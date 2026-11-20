"""0.24.277 (user: "뷰포트 성능 표시는 좋다"): the Render page's Performance - visible triangles and parts (evaluated:
modifiers and every instance counted, hidden parts not), the heaviest parts with Select / Hide / Subdiv 0 / Subdiv Back
(viewport level only; renders keep theirs).  The drawing time is measured in the real window (tests/gui)."""
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import perf_view as pv, side_panel as sp  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
for o in list(S.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0)); cube = C.active_object; cube.name = 'Cube'          # 12
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5, location=(3, 0, 0)); ico = C.active_object; ico.name = 'Ico'  # 5120
bpy.ops.mesh.primitive_cube_add(location=(6, 0, 0)); sub = C.active_object; sub.name = 'Subd'
m = sub.modifiers.new('Subdivision', 'SUBSURF'); m.levels = 3; m.render_levels = 3                      # 6*64*2 = 768
bpy.ops.mesh.primitive_cube_add(location=(9, 0, 0)); hid = C.active_object; hid.name = 'Hidden'; hid.hide_set(True)
C.view_layer.update()
s = pv.scan(C, force=True)
check(f'visible triangles: modifiers counted, the hidden part not ({s["total"]}, {s["parts"]} parts)',
      s['total'] == 12 + 5120 + 768 and s['parts'] == 3)
check(f'the heaviest first ({s["top"]})', [n for n, _t in s['top']] == ['Ico', 'Subd', 'Cube'])
check('Subdiv seen at viewport level 3', pv.subd_level(sub) == 3)
bpy.ops.mch.perf_part(name='Subd', action='SUBD0')
C.view_layer.update()
s = pv.scan(C, force=True)
check(f'Subdiv 0: drawn at level 0 (12 triangles), renders keep 3 ({m.levels}/{m.render_levels})',
      dict(s['top'])['Subd'] == 12 and m.levels == 0 and m.render_levels == 3)
bpy.ops.mch.perf_part(name='Subd', action='SUBDBACK')
check('Subdiv Back: level 3 again', m.levels == 3 and pv.SUBD_KEY not in sub)
bpy.ops.mch.perf_part(name='Ico', action='HIDE')
C.view_layer.update()
s = pv.scan(C, force=True)
check('Hide: out of the count', 'Ico' not in dict(s['top']) and ico.hide_get())
ico.hide_set(False)
bpy.ops.mch.perf_part(name='Ico', action='SELECT')
check('Select: that part selected and active', ico.select_get() and C.view_layer.objects.active == ico and not cube.select_get())
C.window_manager.mch_side_page = 'HDRI'
sp.FOLDED.discard('MATERIAL:perf')
pv._SCAN['val'] = None
items, _h = sp.content(C, 'CUT', 0, 300, 1.0)
L = [getattr(i, 'label', '') for i in items]
heads = [i.label for i in items if i.kind == 'shead']
check(f'the Performance section under Viewport ({heads})', heads.index('PERFORMANCE') == heads.index('VIEWPORT') + 1)
check('its rows: the drawing line, the visible line, the heavy parts with their buttons',
      any(l.startswith('Drawing:') for l in L) and any(l.startswith('Visible:') for l in L)
      and any(l.startswith('Ico  5 K') for l in L) and 'Subdiv 0' in L and 'Hide' in L)
summary()
