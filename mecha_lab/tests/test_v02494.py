"""0.24.61 High Poly Mode (Deform Only, Delay Viewport Updates, light viewport while the ZBrush screen is on, all
put back after), ZBrush's Focal Shift as a custom falloff curve, LazyStep = dot spacing with LazyMouse, alphas
projected from the view and shown in the brush circle, Shift+D = Duplicate, G no longer leaves the ZBrush screen."""
import inspect
import types

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import ui_bars as ub, workspace_ui as wui, zb_highpoly as hp, zb_sculpt as zs, zb_ui as zu
from mecha_lab.mecha_menu import Item

mecha_lab.register()
fresh()
C = bpy.context
real_on = zs.on
zs.on = lambda c: getattr(c, 'mode', '') == 'SCULPT'          # (the test has no MECHA LAB tab)
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=32, ring_count=16)
ob = C.active_object
bpy.ops.object.mode_set(mode='SCULPT')
zb = C.scene.mch_zb
PREF = {'zb_highpoly': False}
real_pref = wui.pref
wui.pref = lambda name, default=None: PREF.get(name, real_pref(name, default))   # (no add-on preferences here)
hp_set = hp.set_pref
hp.set_pref = lambda v: PREF.__setitem__('zb_highpoly', bool(v))

# --- High Poly Mode -----------------------------------------------------------------------------------------------
screen = C.screen                                # (the HiPoly button works on the window's own screen)
sp = next(a for a in screen.areas if a.type == 'VIEW_3D').spaces.active
sc = C.scene.tool_settings.sculpt
sp.overlay.show_wireframes, sp.overlay.show_stats, sp.shading.show_cavity, sp.shading.show_xray = True, True, True, True
sc.use_deform_only, sc.use_sculpt_delay_updates = False, False
check('High Poly Mode is a preference (off at first) and a HiPoly button on the view shelf',
      'zb_highpoly' in wui.MCH_AddonPreferences.__annotations__ and not zb.highpoly
      and any(r[0] == 'HiPoly' and r[1] == 'highpoly' for r in zu.VIEW_SHELF))
ctx = types.SimpleNamespace(screen=screen, scene=C.scene, mode='SCULPT')
check('Off: nothing changes', not hp.update(ctx) and not hp.applied(screen) and sp.overlay.show_wireframes)
zb.highpoly = True                               # (the button applies it at once; the watcher would too)
hp.update(ctx)
check('On in the ZBrush screen: Delay Viewport Updates, wireframe / stats / cavity / X-Ray off; 0.24.76 Deform Only '
      'left alone (it hid Smooth by Angle: flat parts turned smooth)',
      hp.applied(screen) and not sc.use_deform_only and sc.use_sculpt_delay_updates
      and not sp.overlay.show_wireframes and not sp.overlay.show_stats and not sp.shading.show_cavity
      and not sp.shading.show_xray)
check('... applied once (no second change while it stays on)', not hp.update(ctx))
ctx.mode = 'OBJECT'
check('Leaving the ZBrush screen puts everything back as it was', hp.update(ctx) and not hp.applied(screen)
      and not sc.use_deform_only and not sc.use_sculpt_delay_updates and sp.overlay.show_wireframes
      and sp.overlay.show_stats and sp.shading.show_cavity and sp.shading.show_xray)
ctx.mode = 'SCULPT'
hp.update(ctx)
zb.highpoly = False
check('Turning it off puts everything back too', hp.update(ctx) is False and not hp.applied(screen)
      and sp.overlay.show_wireframes and not sc.use_sculpt_delay_updates or (not hp.applied(screen)
                                                                     and sp.overlay.show_wireframes))
zb.highpoly = True
hp.update(ctx)
check('What it changed is kept on the screen (not in the undo history), so a saved file is put back too',
      hp.KEY in screen.keys() and 'show_wireframes' in screen[hp.KEY])
hp.restore(screen)
zb.highpoly = False
other = next(s for s in bpy.data.screens if s != screen and any(a.type == 'VIEW_3D' for a in s.areas))
sc.use_sculpt_delay_updates = False
hp.apply(C.scene, screen)
hp.apply(C.scene, other)
hp.restore(screen)
check('Two windows on one scene: the sculpt options stay light until the last one leaves, then go back',
      sc.use_sculpt_delay_updates and hp.restore(other) and not sc.use_sculpt_delay_updates)
check('A watcher keeps it right every 0.4 s (mode / tab / style changes)', bpy.app.timers.is_registered(hp._tick))
check('Blender Preferences are never changed (only named)', 'preferences' not in inspect.getsource(hp.apply).lower()
      and any('Undo Steps' in a for a in hp.advice()))
ob.shape_key_add(name='Basis')
ob.shape_key_add(name='Smile')
mod = ob.modifiers.new('Smooth', 'SMOOTH')
notes = hp.heavy(ob)
check('It names what weighs on the SubTool (shape keys, modifiers ...)', any('shape key' in n for n in notes)
      and any('modifiers on' in n for n in notes), notes)
ob.modifiers.remove(mod)
bpy.ops.object.mode_set(mode='OBJECT')
ob.shape_key_clear()
bpy.ops.object.mode_set(mode='SCULPT')


class Ctx:
    region = types.SimpleNamespace(width=2560, height=1440, x=0, y=0, type='WINDOW')
    area = None

    def __getattr__(self, n):
        return getattr(bpy.context, n)


zb.highpoly = True
sub = zu.subtool_list(Ctx(), 2560, 1.0, Item, 1200, 100)
check('High Poly Mode on: the SubTool card says so', any(i.label == 'High Poly Mode on' for i in sub))
hp.restore(screen)
zb.highpoly = False

# --- Focal Shift as ZBrush's curve ------------------------------------------------------------------------------------
zs.activate(C, 'Standard')
b = zs.brush(C)
cm = b.curve_distance_falloff
vals = {}
for fs in (-100, -50, 0, 50, 100):
    zb.focal_shift = fs
    vals[fs] = [cm.evaluate(cm.curves[0], t) for t in (0.0, 0.25, 0.5, 0.75, 1.0)]
check('Every Focal Shift value has its own curve (custom), read back as set', b.curve_distance_falloff_preset == 'CUSTOM'
      and zb.focal_shift == 100)
check('Focal Shift 0: a soft bell (1 at the centre, 0.5 half way, 0 at the edge)',
      abs(vals[0][0] - 1) < 0.02 and abs(vals[0][2] - 0.5) < 0.05 and vals[0][4] < 0.02, vals[0])
check('... minus: a flat top (still 1 half way at -100) with a firm edge', vals[-100][2] > 0.97 and vals[-50][1] > 0.97
      and vals[-100][4] < 0.02, vals[-100])
check('... plus: pointier (less half way the higher it goes)', vals[100][2] < vals[50][2] < vals[0][2], (
    vals[50][2], vals[100][2]))
check('The curve follows zb_falloff (ZBrush profile) closely', all(
    abs(cm.evaluate(cm.curves[0], t) - zs.zb_falloff(t, 100)) < 0.05 for t in (0.1, 0.3, 0.6, 0.9)))
zb.focal_shift = 0

# --- LazyMouse: LazyStep = the dot spacing ------------------------------------------------------------------------
b.spacing = 5
zb.lazy_step = 0.6
check('LazyStep with LazyMouse off: kept for later, the spacing stays', b.spacing == 5 and abs(zb.lazy_step - 0.6) < 1e-6)
zb.lazy_mouse = True
check('LazyMouse on: dots LazyStep apart (0.6 = 60 % of the Draw Size) - stitches / rivets with an alpha',
      b.use_smooth_stroke and b.spacing == 60)
zb.lazy_step = 1.0
check('... LazyStep 1: a dot every Draw Size', b.spacing == 100)
zb.lazy_mouse = False
check('LazyMouse off: the spacing it had', not b.use_smooth_stroke and b.spacing == 5)

# --- alphas from the view ---------------------------------------------------------------------------------------------
files, _n = zs.alpha_files(C)
zs.set_alpha(C, files[2])
b = zs.brush(C)
check('The alpha is projected from the view (ZBrush) and shows in the brush circle',
      b.texture_slot.map_mode == 'VIEW_PLANE' and b.use_primary_overlay)
check('0.24.65 The alpha turns with the stroke (ZBrush: a vertical alpha follows a sideways line - Blender Rake)',
      b.texture_slot.use_rake and zb.alpha_directional)
zb.alpha_directional = False
check('... Directional off: it stays fixed on screen', not b.texture_slot.use_rake and not zb.alpha_directional)
b.texture = None
zs.restore_alpha(C)
check('... remembered with the alpha (off stays off when it comes back)', zs.brush(C).texture is not None
      and not zs.brush(C).texture_slot.use_rake)
zb.alpha_directional = True
check('... a Directional switch under Flh / Flv / Rot / Invr', any(
    i.prop == 'alpha_directional' for i in zu.shelf_b(Ctx(), 1.0, Item, 1300) if i.kind == 'seg'))
zs.set_alpha(C, '')

# --- 0.24.63 alpha on the Paint brush (the case that stayed "Alpha Off" in a Blender window) ------------------------
zs.activate(C, 'Paint')
paint = zs.brush(C)
msg = zs.set_alpha(C, files[4])
check('Paint brush + alpha: on the brush itself at once (a linked texture; no brush switch to wait for)',
      zs.brush(C) == paint and paint.library is not None and paint.texture is not None
      and paint.texture.library is not None and zs.current_alpha(C) != '', msg)
check('No "(ZB)" brush copies and no retry timers any more', not hasattr(zs, 'local_brush')
      and not hasattr(zs, '_activate_retry'))
zs.set_alpha(C, '')

# --- keys -------------------------------------------------------------------------------------------------------------
check('Shift+D = Duplicate (asked: SDiv seldom used), D = SDiv up', (
    'D', False, True, False, 'mch.zb_action', {'action': 'DUPLICATE'}) in zs.KEYS and (
    'D', False, False, False, 'mch.zb_action', {'action': 'SDIV_UP'}) in zs.KEYS)
check('G does not leave the ZBrush screen (Blender style / outside the tab it still goes back to Select / Move)',
      not wui.MCH_OT_sculpt_back.poll(C) and 'zb_sculpt.on(context)' in inspect.getsource(
          wui.MCH_OT_sculpt_back.poll))
check('The key card says Shift+D = Duplicate', any('Duplicate' in t for t in zu.KEYS_TEXT if t.startswith('D /')))
check('Right drag turns the view anywhere on the ZBrush screen, over the model too (pen side button), Alt: move; '
      'a right click still opens the menu', ('RIGHTMOUSE', False, False, False, 'mch.zb_popup', {}) in zs.KEYS
      and ('RIGHTMOUSE', False, False, True, 'mch.zb_popup', {}) in zs.KEYS
      and 'RMBDrag()' in inspect.getsource(zs.MCH_OT_zb_popup.invoke)
      and 'rmb_drag_check' in inspect.getsource(zs.MCH_OT_zb_popup.modal)
      and "event.value == 'RELEASE'" in inspect.getsource(zs.MCH_OT_zb_popup.modal))
check('The key card says so', any(t.startswith('Right drag') for t in zu.KEYS_TEXT))
check('Version 0.24.78', mecha_lab.bl_info['version'] == (0, 24, 78))
zs.on = real_on
wui.pref = real_pref
hp.set_pref = hp_set
mecha_lab.unregister()
summary()
