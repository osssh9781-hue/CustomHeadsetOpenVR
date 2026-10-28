"""0.24.59 The drawn viewport UI, part 2: the top bar (shapes and the other tool-header settings), the side panel
(the tool's own sidebar panel read and drawn again), the tool strip with names, the compact actions card - layout,
hit test and what a click does (the GPU drawing itself needs a window: not tested here)."""
import inspect
import json
import types

from _harness import bpy, check, cube, fresh, select_only, summary

import mecha_lab
from mecha_lab import (bottom_bar as bb, mecha_menu as mm, panel_capture as pc, quick_hud as qh, side_panel as sp,
                       tool_state as ts, top_bar as tb, ui_bars as ub, ui_tool_settings as uts, ui_values as uv,
                       workspace_ui as wui)

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
select_only(cube('A'))
W, H = 2000, 1100
HP = 1500          # the side panel's tests: a tall viewport (the bottom main menu takes the lower part)
TOOL = ['CUT']
real_tool = ts.effective_tool
ts.effective_tool = lambda c: TOOL[0]
mm.ts.effective_tool = ts.effective_tool
bb.ui_active = lambda c: True


class Ctx:
    region = types.SimpleNamespace(width=W, height=H, x=0, y=0, type='WINDOW')
    area = None

    def __getattr__(self, n):
        return getattr(bpy.context, n)


CTX = Ctx()


def fresh_items(tool):
    TOOL[0] = tool
    ub.bump()
    sp.dirty()
    return ub.all_items(CTX)


# --- capture -----------------------------------------------------------------------------------------------------
errors = [t for t, fn in uts.DRAWERS.items() if pc.capture(fn, C).opts.get('error')]
check('Every tool panel can be read without drawing it', not errors, errors)
root = pc.capture(uts.draw_cut, C)
props = {(n.prop) for n in pc.walk(root) if n.kind == 'prop'}
check('... the Cut panel as a tree: its settings, boxes, buttons', {'gn_finish', 'solver'} <= props
      and any(n.kind == 'box' for n in pc.walk(root)) and any(n.kind == 'op' for n in pc.walk(root)))

# --- top bar -------------------------------------------------------------------------------------------------------
items = fresh_items('CUT')
bar = tb.items(CTX, W, H, 1.0)
shapes = [i for i in bar if i.kind == 'ibtn']
check('Top bar: the shapes as big icons (all of them, the one in use on), at the top middle',
      len(shapes) == len(ts.SHAPES) and sum(i.on for i in shapes) == 1 and bar[0].y + bar[0].h > H - 20
      and all(i.icon.startswith('png:') for i in shapes))
labels = {i.label for i in bar if i.kind == 'seg'}
check('... Line / Sketch / Slow Line, Target, Depth, Auto Apply, Surface, Ortho for Cut',
      {'Line', 'Sketch', 'Slow Line', 'Auto', 'Selected', 'Active', 'Through All', 'From Surface', 'Auto Apply',
       'Surface', 'Ortho'} <= labels, sorted(labels))
TOOL[0] = 'BASE'
bar_b = tb.items(CTX, W, H, 1.0)
lb = {i.label for i in bar_b if i.kind == 'seg'}
check('Base Mesh: no Depth / Auto Apply (not its settings)', 'Through All' not in lb and 'Auto Apply' not in lb)
S.mch_brush.line_mode = True
bar_b = tb.items(CTX, W, H, 1.0)
check('... Line on: its width, caps, Taper, Pressure, Attach Ends join the bar', any(i.kind == 'mini' and
      i.prop == 'line_width' for i in bar_b) and any(i.kind == 'drop' and i.prop == 'line_caps' for i in bar_b)
      and {'Taper', 'Pressure', 'Attach Ends'} <= {i.label for i in bar_b})
narrow = tb.items(CTX, 1100, H, 1.0, left=0, right=1100)
rows = sorted({round(i.y) for i in narrow if i.kind in {'seg', 'ibtn', 'mini', 'drop'}})
check('A narrow viewport: the groups wrap to more rows, the bar stays inside', len(rows) >= 2
      and narrow[0].x >= 0 and narrow[0].x + narrow[0].w <= 1100, rows)
S.mch_brush.line_mode = False
src = inspect.getsource(wui.draw_shape_palette)
check("Blender's tool header keeps only the Custom PNG picker while the top bar is on",
      "pref('top_bar', True)" in src and 'template_icon_view' in src)

# --- clicks through the one handler -----------------------------------------------------------------------------
TOOL[0] = 'CUT'
items = fresh_items('CUT')


def find(pred):
    return next(i for i in ub.all_items(CTX) if pred(i))


rect = find(lambda i: i.kind == 'ibtn' and i.action == ('shape', 'RECT'))
inside, it = ub.hit(CTX, rect.x + rect.w / 2, rect.y + rect.h / 2)
check('Hit test: the shape button under the mouse', inside and it is rect)
ub.run(CTX, it)
check('... click: that shape', S.mch_brush.shape == 'RECT')
sel = find(lambda i: i.kind == 'seg' and i.label == 'Selected')
ub.run(CTX, sel)
check('Target Selected from the bar', S.mch_cut.targets == 'SELECTED')
ub.run(CTX, find(lambda i: i.kind == 'seg' and i.label == 'Auto'))
slow = find(lambda i: i.kind == 'seg' and i.label == 'Slow Line')
before = S.mch_brush.stab_enable
ub.run(CTX, slow)
check('Slow Line on: its two bars appear in the top bar', S.mch_brush.stab_enable != before and any(
    i.kind == 'mini' and i.prop == 'stab_strength' for i in ub.all_items(CTX)))
inside, it = ub.hit(CTX, 5, 5)
check('Empty viewport: not inside any card', not inside and it is None)

# --- side panel ----------------------------------------------------------------------------------------------------
items = fresh_items('WRINKLE')
side = sp.items(CTX, W, HP, 1.0)
card = side[0]
check('Side panel: docked right under the navigation gizmo, the tool name on top',
      card.x + card.w <= W - 8 and card.x > W - 400 and any(i.kind == 'phead' and i.label == 'CLOTH PLATE'
                                                              for i in side))
kinds = {i.kind for i in side}
check('... numbers as bars, choices as pills, switches, buttons, folded Lasso / Help sections',
      {'mini', 'seg', 'switch', 'tbtn', 'shead'} <= kinds
      and {i.label for i in side if i.kind == 'shead'} >= {'LASSO', 'HELP'}, sorted(kinds))
check('... what the top bar shows is not repeated (Targets / Slow Line / Line / Sketch / Auto Apply)',
      not any(i.data is not None and sp.is_top_bar(i.data, i.prop) for i in side))
puffer = next(i for i in side if i.kind == 'seg' and i.label == 'Puffer')
ub.run(CTX, puffer)
check('Click a pill: that choice (Cloth Plate type Puffer)', S.mch_wrinkle.wtype == 'PUFFER')
height = next(i for i in side if i.kind == 'mini' and i.prop == 'lift')
v0 = S.mch_wrinkle.lift
uv.set(height.data, height.prop, uv.drag(height.data, height.prop, v0, 60))
check('A number bar drags the value (the press operator does this on the mouse)', S.mch_wrinkle.lift > v0)
uv.reset(height.data, height.prop)
check('... Ctrl+click = back to the default', abs(S.mch_wrinkle.lift - 0.002) < 1e-6)
src = inspect.getsource(qh.MCH_OT_quick_hud_press)
check("The press operator: a number bar is dragged (Shift fine), click types, Ctrl+click resets, Esc puts back",
      "item.kind == 'mini'" in src and 'ui_values.drag' in src and 'open_value' in src and 'ui_values.reset' in src)
lasso = next(i for i in sp.items(CTX, W, HP, 1.0) if i.kind == 'shead' and i.label == 'LASSO')
n_before = len(sp.items(CTX, W, HP, 1.0))
ub.run(CTX, lasso)
n_open = len(sp.items(CTX, W, HP, 1.0))
ub.run(CTX, next(i for i in sp.items(CTX, W, HP, 1.0) if i.kind == 'shead' and i.label == 'LASSO'))
check('Click a section title: it opens / folds', n_open > n_before and len(sp.items(CTX, W, HP, 1.0)) == n_before,
      (n_before, n_open))
small = sp.layout(CTX, W, 520, 1.0)
check('A short viewport: the panel scrolls (bar on the side), the wheel moves it', small['content'] > small['view']
      and any(i.kind == 'sbar' for i in small['items']))
first = [i.y for i in small['items'] if i.kind == 'mini'][:1]
sp.scroll_by(CTX, W, 520, 1.0, 120)
moved = sp.layout(CTX, W, 520, 1.0)
check('... scrolled rows move up, only whole rows inside the window are shown', C.window_manager.mch_side_scroll > 0
      and all(moved['clip'][1] - 1 <= i.y and i.y + i.h <= moved['clip'][1] + moved['clip'][3] + 1
              for i in moved['items'] if i.kind in {'mini', 'seg', 'switch', 'tbtn'}))
C.window_manager.mch_side_scroll = 0.0
mini = next(i for i in sp.items(CTX, W, HP, 1.0) if i.kind == 'pbtn')
ub.run(CTX, mini)
folded = sp.items(CTX, W, HP, 1.0)
check('– folds the panel to a small tab with the tool icon; click it to open again',
      C.window_manager.mch_side_min and any(i.kind == 'pmin' for i in folded) and folded[0].w < 60)
ub.run(CTX, next(i for i in folded if i.kind == 'pmin'))
check('... open again', not C.window_manager.mch_side_min)
check('Hidden while the sidebar (N) is open (it shows the same)', 'sidebar_open(context)' in inspect.getsource(sp.on))
check('The Symmetry card keeps clear of the panel', 'side_panel.taken' in inspect.getsource(
    __import__('mecha_lab.symmetry', fromlist=['x'])._anchor))
TOOL[0] = 'BASE'
sp.dirty()
bside = sp.items(CTX, W, HP, 1.0)
alt = [i for i in bside if i.kind == 'seg' and i.action and i.action[0] == 'enum' and i.prop == 'alt_mode']
check('Base Mesh: the Alt choices as one group of pills ("Alt" said once)', len(alt) == 5
      and not any(i.label.startswith('Alt:') for i in alt) and any(i.kind == 'pnote' and i.label == 'Alt'
                                                                   for i in bside))
prof = next(i for i in bside if i.kind == 'tbtn' and i.label == 'Bevel')
ub.run(CTX, prof)
check('... a panel button runs its operator (profile Bevel)', __import__('mecha_lab.base_mesh', fromlist=['x'])
      .scene_defaults(C).profile == 'BEVEL')

# --- values ---------------------------------------------------------------------------------------------------------
ob = C.active_object
ob['mch_test'] = 0.5
ob.id_properties_ui('mch_test').update(min=0.0, max=2.0, soft_min=0.0, soft_max=1.0, default=0.25)
check('Geometry Nodes style inputs ("[\\"name\\"]") work like settings: text, bar position, drag, reset',
      uv.text(ob, '["mch_test"]') == 'mch_test  0.500' and abs(uv.fraction(ob, '["mch_test"]') - 0.5) < 1e-6
      and abs(uv.drag(ob, '["mch_test"]', 0.5, 300) - 1.5) < 1e-6 and (uv.reset(ob, '["mch_test"]') or True)
      and abs(ob['mch_test'] - 0.25) < 1e-6)

# --- strip with names, actions card ------------------------------------------------------------------------------
strip = ub.strip_items(CTX, W, H, 1.0)
named = [i for i in strip if i.kind == 'sbtn']
check('Tool strip: a 6 : 4 tile per tool with its name inside (3 to 6 columns)',
      len(named) == sum(len(r) for _n, r in ts.grouped_tools()) and 3 <= len({round(i.x) for i in named}) <= 6
      and all(i.label and abs(i.w / i.h - 1.5) < 1e-6 and i.w >= 60 for i in named), (len({round(i.x) for i in named}),
                                                                                  named[0].w, named[0].h))
src = inspect.getsource(mm._draw_new)
check('... drawn with the icon in the top 80 % and the name in the bottom 20 % (a long name a bit smaller first)',
      'band = h * 0.2' in src and 'size -= 0.5 * S' in src)
bar_card = ub.bar_items(CTX, 1300, H, 1.0)[0]
real_bar_on = ub.bar_on
ub.bar_on = lambda c: True                       # (0.24.76 the strip only steps over the toolbar when it is on)
st = [i for i in ub.strip_items(CTX, 1300, H, 1.0) if i.kind == 'card'][0]
ub.bar_on = real_bar_on
check('... on a narrower screen it stays above the bottom toolbar', st.y >= bar_card.y + bar_card.h
      or st.x + st.w <= bar_card.x, (st.y, bar_card.y + bar_card.h))
sc = [i for i in strip if i.kind == 'card'][0]
check('... fits the viewport height', sc.y >= 0 and sc.y + sc.h <= H)
check('Tool Strip size and names in Preferences / the Icon Size tab, saved with the other sizes',
      'strip_scale' in wui.SIZE_KEYS and "'strip_scale'" in inspect.getsource(wui.draw_icon_sizes)
      and "strip_names: BoolProperty" in inspect.getsource(wui.MCH_AddonPreferences))
acts = ub.actions_items(CTX, W, H, 1.0)
rows_ = [i for i in acts if i.kind == 'arow']
check('Actions card: one compact card - Apply Modifiers, Reset Axis, Origin x2, Symmetry, Mirror',
      [i.label for i in rows_][-7:] == ['Apply Modifiers', 'Reset Axis', 'Origin to Geometry', 'Origin to 3D Cursor',
                                         'Symmetry', 'Mirror', 'Search Tools (Ctrl+F)'] and acts[0].w < 220)
check('... the round gizmo buttons are off while the drawn UI is on',
      "not _pref('drawn_toolbar', True)" in inspect.getsource(bb.MCH_GGT_object_tidy.poll))
check('One click catcher for all of it (the invisible gizmo asks the same hit test)',
      'ui_bars.hit' in inspect.getsource(qh.over_ui))
ts.effective_tool = real_tool
mm.ts.effective_tool = real_tool
summary()
