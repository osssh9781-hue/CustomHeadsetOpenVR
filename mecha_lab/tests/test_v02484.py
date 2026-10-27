"""0.24.58 The RMB Mecha Menu has its own size (Preferences / sidebar Icon Size: RMB Menu), apart from the other
viewport panels (Viewport Panels: Quick HUD, key legend, Symmetry card, drawn toolbar, tool strip); the toolbar,
tool strip and Symmetry card stay on while the menu is open (it draws on top)."""
import inspect
import json
import os
from types import SimpleNamespace

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import cut_engine as ce, mecha_menu as mm, quick_hud as qh, symmetry as sy, ui_bars, ui_gpu as G, \
    workspace_ui as wui

mecha_lab.register()
fresh()
C = bpy.context
src = inspect.getsource(wui.MCH_AddonPreferences)
check('Preferences: RMB Menu size next to Viewport Panels', "menu_size: FloatProperty(name='RMB Menu', default=1.0"
      in src and "mecha_ui_size: FloatProperty(name='Viewport Panels'" in src
      and "'menu_size'" in inspect.getsource(wui.MCH_AddonPreferences.draw))
check('Sidebar Icon Size tab shows both; presets set both; saved with the other sizes',
      "'menu_size'" in inspect.getsource(wui.draw_icon_sizes) and 'menu_size' in wui.SIZE_KEYS
      and 'menu_size' in inspect.getsource(wui.MCH_OT_icon_size_preset.execute))
sizes = {'mecha_ui_size': 1.0, 'menu_size': 2.0}
real_pref = wui.pref
wui.pref = lambda name, default=True: sizes.get(name, default)
try:
    panels, menu = G.ui_factor(C), G.ui_factor(C, None, menu=True)
    check('The menu uses RMB Menu, the panels Viewport Panels', abs(menu - 2.0 * panels) < 1e-9, (panels, menu))
    check('Menu − / + and Ctrl + wheel change the menu size only', mm.ui_size() == 2.0)
finally:
    wui.pref = real_pref
check('The menu operator scales itself by RMB Menu', inspect.getsource(mm.MCH_OT_mecha_menu).count('menu=True') == 3)
path = wui.sizes_path()
ns = SimpleNamespace(icon_scale=1.0, toolbar_scale=1.0, handle_scale=1.0, mecha_ui_size=1.0, menu_size=1.0)
if path:
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump({'icon_scale': 1.2, 'mecha_ui_size': 1.4}, fh)
    wui.load_sizes(ns)
    os.remove(path)
check('Sizes saved before 0.24.58 (one size): the menu keeps the size it had', path and ns.menu_size == 1.4
      and ns.mecha_ui_size == 1.4, vars(ns))
check('Drawn toolbar, tool strip and Symmetry card stay on while the menu is open',
      '_OPEN' not in inspect.getsource(ui_bars._draw) and '_OPEN' not in inspect.getsource(sy._draw))

# a plain click / drag on the panels in every tool (no Ctrl, no double click)
real = (ui_bars.hit, sy.card_hit, qh.visible, qh.hit)
spots = {'bar': (500, 40), 'card': (1500, 600), 'hud': (120, 800)}
ui_bars.hit = lambda c, x, y: ((x, y) == spots['bar'], None)
sy.card_hit = lambda c, x, y: ((x, y) == spots['card'], None)
qh.visible = lambda c: True
qh.hit = lambda c, x, y: ('row', 0) if (x, y) == spots['hud'] else None
try:
    t = qh.MCH_GT_ui_catch.test_select
    check('The invisible panel gizmo is "hit" over the toolbar / strip, the Symmetry card and the Quick HUD only',
          all(t(None, C, xy) == 0 for xy in spots.values()) and t(None, C, (800, 400)) == -1)
finally:
    ui_bars.hit, sy.card_hit, qh.visible, qh.hit = real
src = inspect.getsource(qh.MCH_GGT_ui_catch)
check('... it runs the same click operator, no tooltip, in every tool (gizmos come before tool keymaps, so Blender '
      "Select / Move's click-select no longer takes the click)", "target_set_operator(MCH_OT_quick_hud_press" in src
      and 'use_tooltip = False' in src and qh.MCH_GGT_ui_catch in qh.CLASSES)
src = inspect.getsource(ce.StrokeLogic._modal)
check('While a shape is drawn point by point, a click on a panel works the panel (not a new point)',
      'quick_hud.over_ui' in src and "bpy.ops.mch.quick_hud_press('INVOKE_DEFAULT')" in src)
summary()
