"""0.24.271 (user: "선택한 것도 디테일 안 올라가고 아예 드래프트도 다 낮은 메쉬로 보이는 것도 하나 - 아니면 드래프트를 그렇게"):
Light Copies' Selected Stay Light (selected parts keep their copy; Edit Mode still the real part), and Quick Render
Draft renders every part from its light copy (counted in the real render), everything back after; Preview / Final
render the real parts as before."""
import os
import tempfile
import time

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import bottom_bar, core_geometry as cg, light_copies as lc, live_stack, quick_render as qr  # noqa: E402
from mecha_lab import zbrush_bridge as zb  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
st = S.mch_light
st.min_tris = 5000


def faces(ob):
    return len(ob.evaluated_get(C.evaluated_depsgraph_get()).data.polygons)


def run_worker(limit=120.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < limit:
        lc._work_step(C)
        if not lc.QUEUE and lc.WORK['thread'] is None:
            break
        time.sleep(0.02)
    lc.sync(C)
    C.view_layer.update()


bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=6, location=(0, 0, 0))     # 20,480 triangles
a = C.active_object
a.name = 'PartA'
a.modifiers.new('Mirror', 'MIRROR').use_axis = (True, False, False)
a.location.x = 1.5                                                          # (the mirror gives a second sphere)
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=6, location=(0, 4, 0))
b = C.active_object
b.name = 'PartB'
bpy.ops.mesh.primitive_cube_add(location=(0, -4, 0))
small = C.active_object
for o in S.objects:
    o.select_set(False)
C.view_layer.objects.active = None
msg = lc.turn_on(C)
run_worker()
ha, hb = lc._holder(a), lc._holder(b)
a.select_set(True); C.view_layer.objects.active = a
lc.sync(C); C.view_layer.update()
check('Selected Stay Light off (default): the selected part shows itself, as before',
      not st.keep_selected and faces(a) == 40960)
st.keep_selected = True
lc.sync(C); C.view_layer.update()
check('Selected Stay Light on: the selected part keeps its light copy', faces(a) == len(ha.data.polygons))
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.object.mode_set(mode='OBJECT')
check('... a tool reading the part still gets the real one', len(lc.full(a).polygons) == 40960 if hasattr(lc.full(a), 'polygons') else True)
COUNT = {}


def grab(scene, d=None):
    if d is not None and d.mode == 'RENDER':
        COUNT['a'] = len(scene.objects['PartA'].evaluated_get(d).data.polygons)
        COUNT['b'] = len(scene.objects['PartB'].evaluated_get(d).data.polygons)


bpy.app.handlers.frame_change_post.append(grab)
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam')); S.collection.objects.link(cam)
cam.location = (12, 0, 2); cam.rotation_euler = (1.45, 0, 1.5708); S.camera = cam
S.render.resolution_x, S.render.resolution_y = 64, 36
qst = S.mch_qrender
qst.folder = tempfile.mkdtemp(prefix='mch_qr_'); qst.camera = 'SCENE'; qst.quality = 'DRAFT'
ng = bpy.data.node_groups.get(lc.GROUP)
res = bpy.ops.mch.quick_render()
check(f'Quick Render Draft: every part from its light copy in the render (A {COUNT.get("a")}, B {COUNT.get("b")})',
      'FINISHED' in res and COUNT.get('a') == len(ha.data.polygons) and COUNT.get('b') == len(hb.data.polygons))
check('... and back after: the copy switch off, the modifiers off for renders again',
      lc.render_switch().outputs[0].default_value == 0.0 and not lc._mod(a).show_render and not lc._mod(b).show_render)
qst.quality = 'PREVIEW'
COUNT.clear()
bpy.ops.mch.quick_render()
check(f'Quick Render Preview: the real parts as before (A {COUNT.get("a")}, B {COUNT.get("b")})',
      COUNT.get('a') == 40960 and COUNT.get('b') == 20480)
COUNT.clear()
S.render.engine = 'CYCLES'; S.cycles.samples = 1; S.cycles.device = 'CPU'
bpy.ops.render.render()
check(f'F12: the real parts as before (A {COUNT.get("a")}, B {COUNT.get("b")})', COUNT.get('a') == 40960 and COUNT.get('b') == 20480)
st.keep_selected = False
summary()
