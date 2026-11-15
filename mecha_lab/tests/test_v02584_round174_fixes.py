"""0.24.174 two faults the real-window test (tests/gui/round174_real_window.py) found:
- Insect Wing failed whenever the Fur tool's Scales / Feathers were in the scene ("Object 'Scales' could not create
  internal data for finding nearest point": a cover is points only, no surface to find the wing's root on);
- Dirt / Dust / Leaves / Snow in "Click a Mesh": the click never reached it - Blender runs an add-on tool's keys
  last-first, so the tool's lasso (later in its list) was asked first and took the click.  Now the lasso passes it on
  in Click a Mesh."""
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
summary()
