"""0.24.60 ZBrush screen, round 2: Ctrl + drag on empty canvas (mask cleared / DynaMesh again), the Ctrl lasso, the
DynaMesh button that stays lit, point counts in Mil, Mask By Cavity options, the S menu closing when the mouse
leaves it, Alt + click on another SubTool, texture stamps with the Paint brush (DragRect), and the ZBrush pickers
for Material / Stroke / Texture."""
import inspect
import math
import os
import types

import numpy as np

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import quick_hud as qh, ui_bars as ub, zb_sculpt as zs, zb_ui as zu
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

# --- point counts in Mil ------------------------------------------------------------------------------------------
check('Points in Mil like ZBrush from a million (1.578 Mil, 2.5 Mil, 1 Mil), commas below',
      qh.points_text(1578123) == '1.578 Mil' and qh.points_text(2500000) == '2.5 Mil'
      and qh.points_text(1000000) == '1 Mil' and qh.points_text(250000) == '250,000' and qh.points_text(999) == '999',
      [qh.points_text(v) for v in (1578123, 2500000, 1000000, 250000, 999)])
zb.points = 2500000
check('The DynaMesh points bar reads 2.5 Mil', qh.value_text(zb, 'points') == 'Points  2.5 Mil',
      qh.value_text(zb, 'points'))
zb.points = 4000

# --- DynaMesh: the button stays lit, Ctrl + drag on empty canvas ----------------------------------------------------
check('A new SubTool: DynaMesh off', not zs.dynamesh_on(ob))
check('... Ctrl + drag on empty canvas with no mask and DynaMesh off does nothing', zs.empty_ctrl_drag(ob) == 'OFF')
msg = zs.run(C, 'DYNAMESH')
ob = C.active_object
check('DynaMesh: remeshed and the button stays lit (DynaMesh on)', zs.dynamesh_on(ob) and 'DynaMesh' in msg
      and C.mode == 'SCULPT', msg)
check('... Ctrl + drag on empty canvas, no mask: DynaMesh again', zs.empty_ctrl_drag(ob) == 'DYNAMESH')
att = ob.data.attributes.get('.sculpt_mask') or ob.data.attributes.new('.sculpt_mask', 'FLOAT', 'POINT')
vals = np.zeros(len(ob.data.vertices), dtype=np.float32)
vals[:10] = 1.0
att.data.foreach_set('value', vals)
check('... something masked: Ctrl + drag on empty canvas clears the mask (no remesh)',
      zs.has_mask(ob) and zs.empty_ctrl_drag(ob) == 'CLEAR_MASK')
att.data.foreach_set('value', np.zeros(len(ob.data.vertices), dtype=np.float32))
n0 = len(ob.data.vertices)
msg = zs.run(C, 'DYNA_UPDATE')
check('DynaMesh again (the Ctrl drag update) keeps it on', zs.dynamesh_on(C.active_object) and 'DynaMesh' in msg, msg)
msg = zs.run(C, 'DYNAMESH')
check('Pressing the lit DynaMesh turns it off (ZBrush)', not zs.dynamesh_on(C.active_object) and msg == 'DynaMesh off')
src = inspect.getsource(zs.ctrl_canvas_release)
check('Ctrl let go on the canvas: click inverts, lasso round the model masks (Alt unmasks), empty: clear / DynaMesh',
      "mode='INVERT'" in src and 'mask_lasso_gesture' in src and "'path'" not in src and 'path=[' in src
      and "value=0.0 if unmask else 1.0" in src and "action='DYNA_UPDATE'" in src and "mode='VALUE', value=0.0" in src)
check('DynaMesh in a window runs in Sculpt Mode (its own Ctrl+Z step), Object Mode only without a window',
      'bpy.app.background' in inspect.getsource(zs.dynamesh))
check('The DynaMesh button is drawn lit while on (depress)', 'depress=zs.dynamesh_on' in inspect.getsource(
    zu.draw_tool_shelf))

# --- the Ctrl lasso: round the model or on empty canvas --------------------------------------------------------------
co = np.array([(x * 0.1, y * 0.1, 0.0) for x in range(-5, 6) for y in range(-5, 6)])
M = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]      # (NDC = the points: x, y in -0.5 .. 0.5)
W, H = 1000, 800
round_model = [(400, 300), (600, 300), (600, 500), (400, 500)]
empty = [(20, 20), (120, 20), (120, 120), (20, 120)]
check('A lasso round the model holds points (it masks)', zs.lasso_holds(co, M, W, H, round_model))
check('A lasso on empty canvas holds none (clear mask / DynaMesh)', not zs.lasso_holds(co, M, W, H, empty))
ring = [(500 + 300 * math.cos(a / 20 * 2 * math.pi), 400 + 300 * math.sin(a / 20 * 2 * math.pi)) for a in range(20)]
check('... a big lasso round everything holds them too', zs.lasso_holds(co, M, W, H, ring))
src = inspect.getsource(zs.MCH_OT_zb_press)
check('The press: Ctrl on the canvas draws our own lasso (orange) and decides when let go',
      'lasso_show(self.path)' in src and 'ctrl_canvas_release' in src and 'lasso_hide()' in src)
check('Alt + click another SubTool picks it (ZBrush)', 'object_under(' in src and 'switch_to(context, other)' in src)

# --- Mask By Cavity --------------------------------------------------------------------------------------------------
src = inspect.getsource(zs.run)
check('Mask By Cavity: Intensity / Blur / Inv (ridges) go to Blender Mask From Cavity',
      'factor=zb.cavity_int / 100.0' in src and 'blur_steps=zb.blur' in src and 'invert=zb.cavity_inv' in src)
zb.cavity_auto = True
check('CavityMask (brush auto masking) = Blender Auto-Masking Cavity', zs.automask_settings(C).use_automasking_cavity)
zb.cavity_auto = False
check('... off again', not zs.automask_settings(C).use_automasking_cavity)


# --- the S menu closes when the mouse leaves it -----------------------------------------------------------------------
class Ctx:
    region = types.SimpleNamespace(width=2560, height=1440, x=0, y=0, type='WINDOW')
    area = None

    def __getattr__(self, n):
        return getattr(bpy.context, n)


CTX = Ctx()
wm = C.window_manager
wm.mch_zb_pop, wm.mch_zb_pop_xy, wm.mch_zb_pop_focus = 'MENU', (900, 700), 'draw_size'
card = zu.popup(CTX, 2560, 1440, __import__('mecha_lab.ui_gpu', fromlist=['x']).ui_factor(CTX, CTX.region), Item)[0]
check('S menu: the mouse on it keeps it open', not zu.popup_leave(CTX, 900, 700) and wm.mch_zb_pop == 'MENU')
check('... a little past its edge still open', not zu.popup_leave(CTX, card.x + card.w + 10, card.y + card.h / 2)
      and wm.mch_zb_pop == 'MENU')
check('... out of the card: it closes', zu.popup_leave(CTX, card.x + card.w + 200, card.y + card.h / 2)
      and wm.mch_zb_pop == '')
check('The hover tracker closes it on every mouse move', 'zb_ui.popup_leave' in inspect.getsource(
    ub.MCH_OT_ui_hover.invoke))

# --- ZBrush pickers: Material / Stroke / Texture ------------------------------------------------------------------------
wm.mch_zb_pop, wm.mch_zb_pop_xy = 'STROKE', (900, 700)
pop = zu.popup(CTX, 2560, 1440, 1.0, Item)
tiles = [i for i in pop if i.kind == 'sbtn']
icons = os.path.join(os.path.dirname(zs.__file__), 'icons')
check('Stroke picker: a tile with its icon per stroke (FreeHand, Dots, DragDot, DragRect, Spray, LineII, Curve)',
      [i.label for i in tiles] == [n for _k, n, _b in zs.STROKES]
      and all(os.path.isfile(os.path.join(icons, i.icon[4:] + '.png')) for i in tiles))
ub.run(CTX, next(i for i in tiles if i.label == 'DragRect'))
check('... a click picks it (Blender Anchored) and the picker closes', zb.stroke == 'DRAGRECT'
      and zs.brush(C).stroke_method == 'ANCHORED' and wm.mch_zb_pop == '')
zb.stroke = 'DOTS'
caps = zs.matcaps(C)
wm.mch_zb_pop = 'MATERIAL'
pop = zu.popup(CTX, 2560, 1440, 1.0, Item)
tiles = [i for i in pop if i.kind == 'sbtn']
check('Material picker: a thumbnail per MatCap', len(tiles) == len(caps) and (not caps or all(
    i.icon.startswith('alpha:') for i in tiles if i.icon != 'card')), (len(tiles), len(caps)))
if caps:
    ub.run(CTX, tiles[min(3, len(tiles) - 1)])
    check('... a click puts that MatCap on and closes', zb.matcap == caps[min(3, len(tiles) - 1)][0]
          and wm.mch_zb_pop == '')
wm.mch_zb_pop = 'TEXTURE'
pop = zu.popup(CTX, 2560, 1440, 1.0, Item)
tiles = [i for i in pop if i.kind == 'sbtn']
check('Texture picker: Mecha / Folder... / Texture Off, Rgb Intensity and a thumbnail per texture',
      len(tiles) >= 10 and {'Mecha', 'Folder...', 'Texture Off'} <= {i.label for i in pop if i.kind == 'seg'}
      and any(i.kind == 'mini' and i.prop == 'rgb_int' for i in pop))
zs.activate(C, 'Standard')
ub.run(CTX, next(i for i in tiles if i.label == 'Hazard Stripes'))
check('... a click picks the texture and the Paint brush (it stamps)', os.path.basename(zs.current_texture(C))
      == 'Hazard Stripes.png' and zs.zb_name(zs.brush(C)) == 'Paint' and zs.stamp_ready(C) and wm.mch_zb_pop == '')
shelf = zu.shelf_b(CTX, 1.0, Item, 1300)
labels = {i.label for i in shelf if i.kind == 'sbtn'}
check('Shelf tiles: Stroke / Material / Texture open the pickers', {'Dots', 'Hazard Stripes'} <= labels and any(
    i.action == ('op', 'mch.zb_popup', {'kind': 'MATERIAL'}) for i in shelf), sorted(labels))
short = zu.shelf_b(CTX, 1.0, Item, 700, 100)
card_b = short[0]
check('The brush tray scrolls on a short viewport (stays above the brush shelf, scroll bar)',
      card_b.kind == 'card' and card_b.y >= 100 - 0.5 and any(i.kind == 'sbar' for i in short))
CTX.region = types.SimpleNamespace(width=2560, height=1440, x=0, y=0, type='WINDOW')
kk = __import__('mecha_lab.ui_gpu', fromlist=['x']).ui_factor(CTX, CTX.region)
check('... the mouse wheel over it scrolls it (its own scroll)', zu.over_shelf(CTX, (12 + zu.A_W + 8 + 40) * kk, 600)
      and zu._OVER[0] == 'B')
zu.scroll_by(CTX, 2560, 1440, 1.0, 48)
check('... down 48 px', abs(wm.mch_zb_scroll_b - 48) < 1e-6 and abs(wm.mch_zb_scroll) < 1e-6)
wm.mch_zb_scroll_b = 0.0
check('Top shelf Mat opens the Material picker too', any(
    i.action == ('op', 'mch.zb_popup', {'kind': 'MATERIAL'}) for i in zu.top_shelf(CTX, 2560, 1440, 1.0, Item)[0]))

# --- the texture stamp --------------------------------------------------------------------------------------------------
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.mesh.primitive_grid_add(x_subdivisions=60, y_subdivisions=60, size=2.0)
g = C.active_object
px = zs.texture_pixels(zs.current_texture(C))
check('Texture pixels read once (sRGB, with alpha)', px is not None and px.shape[2] == 4 and not any(
    im.name.startswith('Hazard') for im in bpy.data.images))
n = zs.texture_stamp(g, px, M, 1000, 1000, (500, 500), 250, 0.0, ('ORTHO', (0, 0, -1)))
att = g.data.color_attributes.active_color
cols = np.empty(len(att.data) * 4, dtype=np.float32)
att.data.foreach_get('color_srgb', cols)
cols = cols.reshape(-1, 4)
cov = np.empty(len(g.data.vertices) * 3)
g.data.vertices.foreach_get('co', cov)
cov = cov.reshape(-1, 3)
inside = (np.abs(cov[:, 0]) < 0.45) & (np.abs(cov[:, 1]) < 0.45)
outside = (np.abs(cov[:, 0]) > 0.55) | (np.abs(cov[:, 1]) > 0.55)
yellow = (cols[:, 0] > 0.9) & (cols[:, 1] > 0.6) & (cols[:, 2] < 0.2)
black = cols[:, :3].max(axis=1) < 0.1
check('Stamp: the texture lands inside the DragRect (yellow and black stripes)', n > 0 and yellow[inside].any()
      and black[inside].any() and (yellow | black)[inside].mean() > 0.95, (n, (yellow | black)[inside].mean()))
check('... outside it the colour stays (white)', np.allclose(cols[outside, :3], 1.0, atol=2e-3))
check('... a new colour layer was made (Color, white)', att is not None and att.name == 'Color')
att.data.foreach_set('color_srgb', np.ones(len(att.data) * 4, dtype=np.float32))
m = g.data.attributes.new('.sculpt_mask', 'FLOAT', 'POINT')
mv = np.where(cov[:, 0] < 0.0, 1.0, 0.0).astype(np.float32)
m.data.foreach_set('value', mv)
zs.texture_stamp(g, px, M, 1000, 1000, (500, 500), 250, 0.0, ('ORTHO', (0, 0, -1)))
att = g.data.color_attributes.active_color          # (a new attribute can move the others: look it up again)
att.data.foreach_get('color_srgb', cols.ravel())
check('The mask protects (masked half stays white, the other half takes the stamp)',
      np.allclose(cols[inside & (cov[:, 0] < -0.02), :3], 1.0, atol=2e-3) and (yellow | black).any())
g.data.attributes.remove(g.data.attributes['.sculpt_mask'])
att = g.data.color_attributes.active_color
att.data.foreach_set('color_srgb', np.ones(len(att.data) * 4, dtype=np.float32))
zs.texture_stamp(g, px, M, 1000, 1000, (500, 500), 250, 0.0, ('ORTHO', (0, 0, 1)))
att.data.foreach_get('color_srgb', cols.ravel())
check('Only points facing the view take it (from below: nothing)', np.allclose(cols[:, :3], 1.0, atol=2e-3))
zs.texture_stamp(g, px, M, 1000, 1000, (650, 500), 100, 0.0, ('ORTHO', (0, 0, -1)), 1.0, ((1, 1, 1), (-1, 1, 1)))
att.data.foreach_get('color_srgb', cols.ravel())
hit = cols[:, :3].min(axis=1) < 0.99
check('Symmetry X stamps the mirror side too', hit[cov[:, 0] > 0.2].any() and hit[cov[:, 0] < -0.2].any())
att.data.foreach_set('color_srgb', np.ones(len(att.data) * 4, dtype=np.float32))
zs.texture_stamp(g, px, M, 1000, 1000, (500, 500), 250, 0.0, ('ORTHO', (0, 0, -1)), 0.5)
att.data.foreach_get('color_srgb', cols.ravel())
check('Rgb Intensity 50: half way to the texture', cols[inside, :3].min() > 0.4 and cols[inside, :3].min() < 0.6)
r = zs.stamp_rect((100, 100), 50, math.pi / 2, 0.5)
check('DragRect corners: half width 50, turned 90 deg, image aspect kept',
      all(abs(a - b) < 1e-6 for p, q in zip(r, [(125, 50), (125, 150), (75, 150), (75, 50)]) for a, b in zip(p, q)), r)
g2 = bpy.data.objects.new('cornerlayer', g.data.copy())
C.collection.objects.link(g2)
for a in list(g2.data.color_attributes):
    g2.data.color_attributes.remove(a)
lay = g2.data.color_attributes.new('Corner', 'BYTE_COLOR', 'CORNER')
g2.data.color_attributes.active_color = lay
lay.data.foreach_set('color_srgb', np.ones(len(lay.data) * 4, dtype=np.float32))
n2 = zs.texture_stamp(g2, px, M, 1000, 1000, (500, 500), 250, 0.0, ('ORTHO', (0, 0, -1)))
cc = np.empty(len(lay.data) * 4, dtype=np.float32)
lay.data.foreach_get('color_srgb', cc)
check('A face corner colour layer takes the stamp too', n2 > 0 and (cc.reshape(-1, 4)[:, :3].min(axis=1) < 0.2).any())
src = inspect.getsource(zs.apply_stamp)
check('One Ctrl+Z takes a stamp back (in a window: Blender colour filter at zero strength stores the colours)',
      "bpy.ops.sculpt.color_filter('EXEC_DEFAULT', True, type='FILL', strength=0.0" in src)
src = inspect.getsource(zs.MCH_OT_zb_press)
check('Paint + Texture: a press on the model starts the stamp (DragRect), elsewhere the brush as before',
      'stamp_ready(context)' in src and "mch.zb_tex_stamp('INVOKE_DEFAULT')" in src)
check('The stamp: drag = size, direction = turn, a click = Draw Size; preview of the texture while dragging',
      'math.hypot(dx, dy)' in inspect.getsource(zs.MCH_OT_zb_tex_stamp.modal) and 'draw_size' in inspect.getsource(
          zs.MCH_OT_zb_tex_stamp.modal) and 'image_quad' in inspect.getsource(zs._stamp_draw))
tex_dir = zs.TEXTURE_DIR
check('Mecha textures come with the add-on (hazard stripes, camo, carbon, decals ...)',
      len([f for f in os.listdir(tex_dir) if f.endswith('.png')]) >= 10)
zs.set_texture(C, '')
check('Texture Off: back to the normal Paint stroke', not zs.stamp_ready(C))
zs.on = real_on
mecha_lab.unregister()
summary()
