"""0.24.76 ZBrush screen: a pen right-click (side button) that wobbles the tip while pressed is still a click (the
menu opens) when it lets go quickly; the picked SubTool stands out (the other objects faded) while the ZBrush
screen is on, all put back after.  Also the Ramp Soft side band of the facet carve is smooth along the walls."""
import time
import types

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import zb_highpoly as hp, zb_sculpt as zs

mecha_lab.register()
fresh()
C = bpy.context

# --- pen right-click ------------------------------------------------------------------------------------------------
CALLS = []
shim = types.SimpleNamespace(ops=types.SimpleNamespace(mch=types.SimpleNamespace(
    zb_nav=lambda *a, **k: CALLS.append(k))))
real_bpy, real_nav = zs.bpy, zs.nav_on
zs.bpy, zs.nav_on = shim, (lambda context: True)


def ev(x, y, pen, kind='MOUSEMOVE', value='NOTHING'):
    return types.SimpleNamespace(mouse_x=x, mouse_y=y, alt=False, is_tablet=pen, type=kind, value=value)


def press(pen, age=0.0):
    r = zs.RMBDrag()
    r.rmb_drag_start(C, ev(500, 500, pen, 'RIGHTMOUSE', 'PRESS'))
    r.rmb_t0 -= age
    return r


try:
    r = press(True)
    turned = r.rmb_drag_check(C, ev(530, 512, True))
    check('Pen: the tip wobbles 42 px right after the side button press -> still a click (no view turn)',
          not turned and not CALLS, CALLS)
    r.rmb_drag_check(C, ev(530, 512, True, 'RIGHTMOUSE', 'RELEASE'))
    check('... let go: the menu (the press was a click)', not r.rmb_live)
    r = press(True, age=0.4)
    check('Pen held a moment and moved 42 px: the view turns (right-drag)',
          r.rmb_drag_check(C, ev(530, 512, True)) and CALLS and CALLS[-1]['mode'] == 'ROTATE', CALLS)
    CALLS.clear()
    r = press(True)
    check('Pen moved far (80 px) at once: the view turns', r.rmb_drag_check(C, ev(560, 520, True)) and len(CALLS) == 1)
    CALLS.clear()
    r = press(True)
    check('Pen: a small wobble (10 px) is a click at any time', not r.rmb_drag_check(C, ev(506, 504, True)))
    r = press(False)
    check('Mouse: unchanged - 10 px turns the view at once', r.rmb_drag_check(C, ev(506, 504, False)) and len(CALLS) == 1)
    check('Pen tolerance values', zs.RMBDrag.PEN_SLOP < zs.RMBDrag.PEN_FAR and 0.1 <= zs.RMBDrag.PEN_HOLD <= 0.5)
finally:
    zs.bpy, zs.nav_on = real_bpy, real_nav

# --- the picked SubTool stands out ----------------------------------------------------------------------------------
screen = C.screen
sp = next(a for a in screen.areas if a.type == 'VIEW_3D').spaces.active
ov = sp.overlay
ov.show_fade_inactive, ov.fade_inactive_alpha = False, 0.8
real_on = zs.on
state = {'on': True}
zs.on = lambda context: state['on']
try:
    ctx = types.SimpleNamespace(screen=screen)
    check('ZBrush screen on: the other objects are faded (Fade Inactive Geometry), the picked one stays bright',
          hp.fade_update(ctx) and ov.show_fade_inactive and abs(ov.fade_inactive_alpha - hp.FADE_ALPHA) < 1e-6)
    check('... once (no change while it stays on)', not hp.fade_update(ctx))
    state['on'] = False
    check('Leaving the ZBrush screen: back as it was', hp.fade_update(ctx) and not ov.show_fade_inactive
          and abs(ov.fade_inactive_alpha - 0.8) < 1e-6)
    check('... once', not hp.fade_update(ctx))
    ov.show_fade_inactive = True
    state['on'] = True
    hp.fade_update(ctx)
    state['on'] = False
    hp.fade_update(ctx)
    check('A user who had it on keeps it on', ov.show_fade_inactive)
    ov.show_fade_inactive = False
    state['on'] = True
    hp.fade_update(ctx)
    check('Turning the add-on off puts it back too', hp.fade_restore(screen) and not ov.show_fade_inactive
          and hp.FADE_KEY not in screen.keys())
    check('The watcher drives it (every tick, with High Poly Mode)', 'fade_update' in __import__('inspect').getsource(hp._tick))
finally:
    zs.on = real_on

# --- Ramp Soft side band (facet carve) --------------------------------------------------------------------------------
from mathutils import Quaternion, Vector
from mecha_lab import core_geometry as cg, cut_engine as ce, facet_carve as fc
from _harness import non_manifold

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
C.scene.mch_settings.auto_apply = True
cut = C.scene.mch_cut
bpy.ops.mesh.primitive_cube_add(size=1.0, scale=(3.0, 2.0, 0.4))
plate = C.active_object
bpy.ops.object.transform_apply(scale=True)
cut.depth_mode, cut.depth, cut.gn_ramp, cut.gn_finish, cut.gn_ramp_length, cut.gn_ramp_soft = 'SURFACE', 0.12, True, 'NONE', 1.0, 0.5
t0 = time.perf_counter()
ce.perform_closed(C, 'CUT', [plate], [[(380, 420), (420, 420), (640, 600), (600, 600)]], TOP, False)
dt = time.perf_counter() - t0


def depth_at(x, y):
    C.view_layer.update()
    hit, loc, _n, _i, _o, _m = C.scene.ray_cast(C.evaluated_depsgraph_get(), Vector((x, y, 5)), Vector((0, 0, -1)))
    return 0.2 - loc.z if hit else 0.0


d = Vector((2.2, 1.8, 0)).normalized()
side = Vector((-d.y, d.x, 0))
worst = 0.0
for off in (0.0, 0.06, 0.095, 0.11):           # the middle, and across the rounded side band
    prof = [depth_at(*(Vector((-1.0, -0.8, 0)) + d * (0.6 + 1.2 * k / 59) + side * off).xy) for k in range(60)]
    worst = max(worst, max(abs(prof[i + 1] - 2 * prof[i] + prof[i - 1]) for i in range(1, 59)))
check('Ramp Soft on a long thin ramp (facet carve): smooth along the walls and in the middle, closed, few faces',
      fc.LAST.get('path') == 'facet' and worst < 0.0008 and non_manifold(plate) == 0 and len(plate.data.polygons) < 4000,
      (fc.LAST.get('path'), round(worst, 5), len(plate.data.polygons), round(dt, 2)))
cut.gn_ramp = False

summary()
