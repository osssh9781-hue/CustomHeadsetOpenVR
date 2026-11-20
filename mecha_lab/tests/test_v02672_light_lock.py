"""0.24.272 (user: "전체를 원래 메쉬로 안 돌아가게 하는 버튼 - 다시 눌러야 복사본 풀리게"): Lock Copies - every part stays
on its light copy: selected, read by a tool (back at once), edited (the old copy until the new one is ready); Edit Mode
still the real part; pressed again: as before."""
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
bpy.ops.mch.light_lock()
check('Lock Copies (Light Copies off before): Light Copies on, locked', st.on and st.lock)
run_worker()
ha = lc._holder(a)
a.select_set(True); C.view_layer.objects.active = a
lc.sync(C); C.view_layer.update()
check('locked: the selected part stays light', faces(a) == len(ha.data.polygons))
ev = lc.full(a, C.evaluated_depsgraph_get())
check('a tool reading it still gets the real part', len(ev.data.polygons) == 40960)
time.sleep(lc.LOCK_REST + 0.05)
lc.sync(C); C.view_layer.update()
check('... and it is light again right after (not 3 s later)', faces(a) == len(ha.data.polygons))
# an edit: the old copy stays shown while the new one is made
import bmesh
bm = bmesh.new(); bm.from_mesh(b.data)
for v in bm.verts[:200]:
    v.co.z += 0.3
bm.to_mesh(b.data); bm.free(); b.data.update()
C.view_layer.update(); time.sleep(lc.OWN_SECONDS + 0.1)
lc._on_update(S, C.evaluated_depsgraph_get())
lc.DIRTY.add('PartB')
lc.sync(C); C.view_layer.update()
hb = lc._holder(b)
check('an edited part: the old copy stays shown while the new one is made', lc._mod(b).show_viewport)
run_worker()
check('... the new copy comes in, still light', lc._mod(b).show_viewport and faces(b) == len(lc._holder(b).data.polygons))
bpy.ops.object.mode_set(mode='EDIT')
lc.sync(C)
check('Edit Mode: the real part', not lc._mod(a).show_viewport)
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.mch.light_lock()
lc.sync(C); C.view_layer.update()
check('pressed again: unlocked - the selected part shows itself again', not st.lock and st.on and faces(a) == 40960)
lc.turn_off(C)
check('Light Copies off clears the lock too', not st.lock)
summary()
