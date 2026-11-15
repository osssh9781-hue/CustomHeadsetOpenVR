"""0.24.174 two faults the real-window test (tests/gui/round174_real_window.py) found:
- Insect Wing failed whenever the Fur tool's Scales / Feathers were in the scene ("Object 'Scales' could not create
  internal data for finding nearest point": a cover is points only, no surface to find the wing's root on);
- Dirt / Dust / Leaves / Snow in "Click a Mesh": the click never reached it - Blender runs an add-on tool's keys
  last-first, so the tool's lasso (later in its list) was asked first and took the click.  Now the lasso passes it on
  in Click a Mesh.
- Weathering drawn on a curved body sank into it in its middle (the render: snow drawn on a rock - a white rim round a
  bare grey top): its plate took Armor Plate's Face Size (120 px), a few big flat faces cutting through the curve.
  Now a drawn area's plate has its own finer faces (24 px at most); the window's Face Size is left as it is."""
import math
import types

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Euler, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, creature_fur as cf, cut_engine as ce, insect_wing as iw  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32)
body = C.active_object
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)


def loop(cx, cz, rx, rz, n=48):
    return [[FRONT.to_screen(Vector((cx + rx * math.cos(a), -2.0, cz + rz * math.sin(a))))
             for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]]


S.mch_cover.grow = 'SCALES'
cf.perform(C, loop(0.0, 0.1, 0.5, 0.4), FRONT)
cov = C.active_object
try:
    cov.closest_point_on_mesh(Vector((0, 0, 0)))
    fails = False
except RuntimeError:
    fails = True
check(f'the Fur tool\'s Scales in the scene ({cov.name}: {len(cov.data.vertices)} points, '
      f'{len(cov.data.polygons)} faces - Blender cannot find a nearest point on it: {fails})',
      len(cov.data.polygons) == 0 and len(cov.data.vertices) > 0)
for o in C.selected_objects:
    o.select_set(False)
try:
    msg = iw.perform(C, loop(1.9, 0.2, 0.7, 0.18), FRONT)
    err = None
except Exception as ex:                                  # (before: "could not create internal data ...")
    msg, err = None, repr(ex)
wing = next((o for o in S.objects if iw.is_wing(o)), None)
check(f'Insect Wing drawn with them in the scene: a wing ({wing and len(wing.data.polygons):,} faces; error: {err})',
      err is None and wing is not None and len(wing.data.polygons) > 1000)

S.mch_weather_how = 'CLICK'
fake = types.SimpleNamespace(mode='WSNOW', press_lasso=False, force=True)
ev = types.SimpleNamespace(type='LEFTMOUSE', value='PRESS', mouse_region_x=10, mouse_region_y=10)
r_click = ce.StrokeLogic.invoke(fake, C, ev)
S.mch_weather_how = 'DRAW'
try:
    r_draw = ce.StrokeLogic.invoke(fake, C, ev)         # (no 3D view here: it goes on toward drawing and stops)
except (AttributeError, TypeError):
    r_draw = 'went on to draw'
fake.mode = 'PLATE'
S.mch_weather_how = 'CLICK'
try:
    r_plate = ce.StrokeLogic.invoke(fake, C, ev)
except (AttributeError, TypeError):
    r_plate = 'went on to draw'
S.mch_weather_how = 'DRAW'
check(f'Snow in "Click a Mesh": the lasso passes the click on ({r_click}); in Draw it draws ({r_draw}); other tools '
      f'are not touched by it ({r_plate})', r_click == {'PASS_THROUGH'} and r_draw != {'PASS_THROUGH'}
      and r_plate != {'PASS_THROUGH'})
# snow drawn on top of a ball (seen from above, 200 px = 1): it lies on the ball, its middle not sunk into it
from mecha_lab import weathering as wt  # noqa: E402
TOP = cg.OrthoProjector(Euler((0, 0, 0)).to_quaternion(), pixels_per_unit=200.0)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.6, segments=64, ring_count=32, location=(6.0, 0.0, 0.0))
ball = C.active_object
for o in C.selected_objects:
    o.select_set(False)
face_px = S.mch_plate.spacing
ring_top = [[TOP.to_screen(Vector((6.0 + 0.36 * math.cos(a), 0.36 * math.sin(a), 2.0)))
             for a in np.linspace(0, 2 * math.pi, 48, endpoint=False)]]


def snow_on_ball(face_cap):
    old_cap = wt.FACE_PX
    wt.FACE_PX = face_cap
    try:
        wt.perform(C, ring_top, TOP, 'SNOW')
    finally:
        wt.FACE_PX = old_cap
    ob = C.active_object
    dg = C.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    P_ = np.array([tuple(ev.matrix_world @ v.co) for v in me.vertices])
    ev.to_mesh_clear()
    d_ = np.linalg.norm(P_ - np.array([6.0, 0.0, 0.0]), axis=1)
    mid_ = np.hypot(P_[:, 0] - 6.0, P_[:, 1]) < 0.12
    top_ = float(P_[mid_, 2].max()) if mid_.any() else 0.0
    for o in C.selected_objects:
        o.select_set(False)
    return ob, top_, float((d_ < 0.57).mean()), len(P_)


old, top_old, deep_old, _n = snow_on_ball(120)              # (as before: the window's Face Size)
bpy.data.objects.remove(old)
snow, top_mid, deep, n = snow_on_ball(wt.FACE_PX)
check(f'snow drawn on a ball: its middle on top of the ball (highest there {top_mid:.3f}, the ball\'s top 0.600; with '
      f'the 120 px faces before: {top_old:.3f}), little of it deep in the ball ({deep * 100:.1f} % of {n:,} '
      f'points over 3 cm in; before {deep_old * 100:.1f} %); the window\'s Face Size left at {S.mch_plate.spacing} px',
      wt.kind_of(snow) == 'SNOW' and top_mid > 0.6 and deep < 0.02 and deep_old > 0.08
      and S.mch_plate.spacing == face_px)
summary()
