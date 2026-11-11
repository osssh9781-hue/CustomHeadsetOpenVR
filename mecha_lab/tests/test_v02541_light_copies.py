"""0.24.136 (user: "사본 쓰면 더 빨라?" -> "그럼 일단 그렇게 해 보고") Light Copies: heavy parts not being worked on are
drawn from a light copy (Fast Decimate, made in the background); selected / touched parts, renders, exports, Apply
Modifiers and every add-on read of a part's geometry use the part itself; an edited part gets a new copy; a saved file
holds no copy in sight; off removes everything."""
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
check('on: the two heavy parts (Mirror counted) queued, the cube not', sorted(lc.QUEUE) == ['PartA', 'PartB'], (msg, lc.QUEUE))
run_worker()
ha, hb = lc._holder(a), lc._holder(b)
check('copies made in the background: a hidden object each (in no scene), ~10 % of the part (A with its Mirror)',
      ha is not None and hb is not None and ha.name not in S.objects and hb.name not in S.objects
      and 3500 <= len(ha.data.polygons) <= 4500 and 1700 <= len(hb.data.polygons) <= 2300 and lc._mod(small) is None,
      (len(ha.data.polygons) if ha else None, len(hb.data.polygons) if hb else None))
check('the viewport draws the copies (parts not selected), the Mirror not applied twice',
      faces(a) == len(ha.data.polygons) and faces(b) == len(hb.data.polygons) and len(a.data.polygons) == 20480,
      (faces(a), faces(b)))
check('the modifier: last (pinned), off for renders; the parts\' own counts kept (A 40,960 with its Mirror)',
      a.modifiers[-1].name == lc.MOD and not lc._mod(a).show_render and getattr(lc._mod(a), 'use_pin_to_last', True)
      and lc._info(a)['full'] == 40960 and lc._info(b)['full'] == 20480)
check('Quick Render\'s memory estimate counts the parts themselves (40,960 + 20,480 + 12)',
      qr.scene_load(C, S.mch_qrender, depsgraph=C.evaluated_depsgraph_get(), cache=False)[0] == 40960 + 20480 + 12,
      qr.scene_load(C, S.mch_qrender, depsgraph=C.evaluated_depsgraph_get(), cache=False))
# selected -> itself
a.select_set(True)
C.view_layer.objects.active = a
lc.sync(C)
check('a selected / active part shows itself, the other stays light', faces(a) == 40960 and faces(b) < 2400,
      (faces(a), faces(b)))
a.select_set(False)                    # a click on empty space: deselected, Blender keeps it active
lc.sync(C)
check('deselected but still active (a click on empty space): light again - nothing shows it, it is not worked on',
      C.view_layer.objects.active == a and faces(a) < 4600, faces(a))
C.view_layer.objects.active = None
lc.sync(C)
# a tool reads B's geometry -> B itself, until it rests
ev = lc.full(b)
got = len(ev.data.polygons)
lc.sync(C)
still = faces(b)
lc.TOUCH['PartB'] = time.monotonic() - 10.0
lc.sync(C)
check('full(): a tool reading a part gets the part itself (20,480), it stays itself while worked on, light again when '
      'it rests', got == 20480 and still == 20480 and faces(b) < 2400, (got, still, faces(b)))
# the Live Stack never lists it; applying it is refused; Apply Modifiers applies the rest, never the copy
check('the Live Stack does not list it', [e[1] for e in live_stack.entries(a)] and
      all(not lc.is_light_mod(e[0]) for e in live_stack.entries(a)))
cg.apply_single_modifier(C, b, lc._mod(b))
check('applying the light copy modifier directly: nothing happens (mesh and modifier kept)',
      len(b.data.polygons) == 20480 and lc._mod(b) is not None)
done, err = bottom_bar.apply_all_modifiers(C, a)                   # (A not selected: it shows its copy)
check('Apply Modifiers on a part showing its copy: its Mirror applied to the part itself (40,960 faces), the copy '
      'never baked, the light copy modifier kept', done == ['Mirror'] and not err and len(a.data.polygons) == 40960
      and lc._mod(a) is not None, (done, err, len(a.data.polygons)))
# A changed: a new copy when it rests (Apply Modifiers made it the active, selected part)
for o in S.objects:
    o.select_set(False)
C.view_layer.objects.active = None
lc.TOUCH['PartA'] = time.monotonic() - 10.0
lc.OWN['PartA'] = -1e9
lc.DIRTY.add('PartA')
lc.sync(C)
stale = 'PartA' in lc.STALE and faces(a) == 40960
run_worker()
check('an edited part shows itself until its new copy is ready, then the new copy (~4,096 of 40,960)',
      stale and 3500 <= faces(a) <= 4500 and 'PartA' not in lc.STALE, (stale, faces(a)))
# exports: the part itself
tmp = zb.export_copy(C, b, apply_modifiers=True)
exp_faces = len(tmp.data.polygons) if tmp.data else 0
bpy.data.objects.remove(tmp)
check('an add-on export reads the part itself (20,480 triangles), not its copy', exp_faces >= 20480, exp_faces)
# a file browser open -> every part itself
lc.TOUCH.clear()
real = lc._browser_open
lc._browser_open = lambda: True
lc.sync(C)
br = (faces(a), faces(b))
lc._browser_open = real
lc.sync(C)
check('while a file browser is open (File > Export ...) every part shows itself', br == (40960, 20480), br)
# the copy object gone (an undo) -> the part itself, never nothing
hb = lc._holder(b)
lc._mod(b).show_viewport = False
lc._set_input(lc._mod(b), lc._copy_socket(lc._mod(b).node_group), None)
lc.sync(C)
check('no copy object (an undo took it): the part shows itself, it never disappears', faces(b) == 20480, faces(b))
lc._set_input(lc._mod(b), lc._copy_socket(lc._mod(b).node_group), hb)
lc.sync(C)
# save: on disk no copy in sight; reopened: checked, then light again
path = os.path.join(tempfile.mkdtemp(prefix='mch_lc_'), 'light.blend')
before = (lc._mod(a).show_viewport, lc._mod(b).show_viewport)
bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
after = (lc._mod(a).show_viewport, lc._mod(b).show_viewport)
bpy.ops.wm.open_mainfile(filepath=path)
C = bpy.context
a2, b2 = bpy.data.objects['PartA'], bpy.data.objects['PartB']
on_disk = (lc._mod(a2).show_viewport, lc._mod(b2).show_viewport)
for o in C.scene.objects:
    o.select_set(False)
C.view_layer.objects.active = None
for _i in range(4):
    lc.sync(C)
C.view_layer.update()
check('saved: the file holds the parts showing themselves (opened without the add-on: no copy in sight); here they '
      'were light before and after the save; reopened: checked against the parts, light again',
      before == (True, True) and after == (True, True) and on_disk == (False, False)
      and len(C.scene.objects['PartA'].evaluated_get(C.evaluated_depsgraph_get()).data.polygons) < 4600,
      (before, after, on_disk))
# off: everything gone, the parts as they were
msg = lc.turn_off(C)
check('off: no light copy modifier, no copy object or mesh, no node group; the parts\' meshes as they were',
      all(lc._mod(o) is None for o in C.scene.objects) and not [o for o in bpy.data.objects if o.get('mch_light_holder')]
      and bpy.data.node_groups.get(lc.GROUP) is None and len(a2.data.polygons) == 40960 and len(b2.data.polygons) == 20480,
      msg)
summary()
