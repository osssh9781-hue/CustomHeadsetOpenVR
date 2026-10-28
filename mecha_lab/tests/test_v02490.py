"""0.24.59 The drawn viewport UI, part 3: the main menu along the bottom (every tool as a 6 : 4 tile), the actions
dock where the bottom toolbar was, the Layers panel on the left (parts / groups, Export, ZBrush Bridge) and the top
bar centred - layout, hit test and what a click does (the GPU drawing itself needs a window: not tested here)."""
import inspect
import os
import tempfile
import types

from _harness import bpy, check, cube, fresh, select_only, summary

import mecha_lab
from mecha_lab import (bottom_bar as bb, groups, key_legend, layers_panel as lp, mecha_menu as mm, side_panel as sp,
                       symmetry, tool_state as ts, top_bar as tb, ui_bars as ub, workspace_ui as wui)

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
W, H = 2000, 1100
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


def part(name, loc):
    ob = cube(name)
    ob.location = loc
    return ob


torso = part('Torso', (0, 0, 0))
arm = [part('Shoulder_L', (2, 0, 1)), part('Hand_L', (3, 0, 0))]
pack = part('Backpack', (0, 2, 0))
garm = groups.create(C, arm, 'Arm_L')
groups.set_repeat(C, garm, mode='MIRROR')
select_only(torso)
ub.bump()
items = ub.all_items(CTX)
K = __import__('mecha_lab.ui_gpu', fromlist=['x']).ui_factor(CTX, CTX.region)    # the size factor the UI uses

# --- where things are -----------------------------------------------------------------------------------------------
check('Tool menu at the bottom by default: the left strip and the bottom toolbar are off, the menu is on',
      ub.menu_pos() == 'BOTTOM' and ub.menu_on(CTX) and not ub.strip_on(CTX) and not ub.bar_on(CTX))
menu = ub.menu_items(CTX, W, H, K)
tiles = [i for i in menu if i.kind == 'sbtn']
all_tools = [t[0] for _n, r in ts.grouped_tools() for t in r]
check('Main menu: every tool once as a 6 : 4 tile with its name, a title per group',
      sorted(i.action[1] for i in tiles) == sorted(all_tools) and all(abs(i.w / i.h - 1.5) < 1e-6 and i.label
                                                                       for i in tiles)
      and len([i for i in menu if i.kind == 'striphead']) == len(ts.grouped_tools()))
card = menu[0]
check('... one band along the bottom, inside the viewport, centred', card.y < 20 and card.x >= 0
      and card.x + card.w <= W and abs(card.x + card.w / 2 - W / 2) < 1.0)
rows = {round(i.y) for i in tiles}
check('... two rows on a wide screen', len(rows) == 2, sorted(rows))
narrow = ub.menu_items(CTX, 1200, H, 1.0)
ncard = narrow[0]
check('... a narrow screen: three rows, still inside', len({round(i.y) for i in narrow if i.kind == 'sbtn'}) == 3
      and ncard.x >= 0 and ncard.x + ncard.w <= 1200)
keys = {i.label for i in menu if i.kind == 'keycap'}
check("... the toolbar's key letters on their tiles (Move D, Cut C, Boolean B)", {'D', 'C', 'B'} <= keys, keys)
cut = next(i for i in tiles if i.action == ('tool', 'CUT'))
check('... the tool in use on blue, a long name says itself above the tile', cut.on and cut.data == 'ABOVE')

dock = ub.dock_items(CTX, W, H, K)
dt = [i for i in dock if i.kind == 'sbtn']
check('Actions where the bottom toolbar was: Select first, then Apply Modifiers ... Mirror as big tiles',
      dt[0].label == 'Select' and [i.label for i in dt][-7:] == ['Apply Modifiers', 'Reset Axis',
                                                                 'Origin to Geometry', 'Origin to 3D Cursor',
                                                                 'Symmetry', 'Mirror', 'Search Tools (Ctrl+F)']
      and dt[0].w > cut.w and any(i.kind == 'keycap' and i.label == 'F' for i in dock))
check('... on top of the menu, centred', abs(dock[0].y - ub.bottom_taken(CTX, K, W)) < 1e-6
      and dock[0].y > card.y + card.h and abs(dock[0].x + dock[0].w / 2 - W / 2) < 1.0)
check('... no floating actions card in this mode', not any(i.kind == 'arow' for i in items))

# --- clicks ------------------------------------------------------------------------------------------------------
inside, it = ub.hit(CTX, cut.x + cut.w / 2, cut.y + cut.h / 2)
check('A click on a menu tile hits that tool', inside and it is not None and it.action == ('tool', 'CUT'))
sel = dt[0]
inside, it = ub.hit(CTX, sel.x + sel.w / 2, sel.y + sel.h / 2)
check('... a click on Select hits the Select button', inside and it is not None and it.action == ('bar', 'SELECT'))

# --- top bar, side panel, cards keep clear ------------------------------------------------------------------------
bar = tb.items(CTX, W, H, 1.0)
check('Top bar centred in the viewport (the side panels start below it)',
      abs(bar[0].x + bar[0].w / 2 - W / 2) < 1.0, (bar[0].x, bar[0].w))
side = sp.items(CTX, W, H, 1.0)
check('Side panel stays above the menu and the actions', side[0].y >= ub.dock_top(CTX, 1.0, W) - 1e-6)
check('Symmetry card goes above the menu + actions', 'dock_top' in inspect.getsource(symmetry._anchor))
real_stroke = key_legend._stroke_tool
key_legend._stroke_tool = lambda c: 'BASE'
wide = types.SimpleNamespace(width=3400, height=H, x=0, y=0, type='WINDOW')
CTX.region = wide
kb = key_legend.box(CTX, 1.0)
CTX.region = Ctx.region
kn = key_legend.box(CTX, 1.0)
lay_floor = lp.frame(CTX, W, H, 1.0)[3]
key_legend._stroke_tool = real_stroke
check('Key legend: in the bottom left corner beside the main menu on a wide screen',
      kb is not None and kb[1] < 20 and kb[0] < 40, kb[:4] if kb else None)
check('... above the menu + actions when the menu leaves no room beside it; the Layers panel stays above it',
      kn is not None and kn[1] >= ub.dock_top(CTX, 1.0, W) and lay_floor >= kn[1] + kn[3], (kn[:4], lay_floor))

# --- layers panel ------------------------------------------------------------------------------------------------
lay = lp.items(CTX, W, H, 1.0)
lrows = [i for i in lay if i.kind == 'lrow']
names = [i.label for i in lrows]
check('Layers panel on the left: groups first with their parts under them, then the loose parts',
      lay[0].x < 40 and names[:3] == ['Arm_L', 'Hand_L', 'Shoulder_L'] and {'Torso', 'Backpack'} <= set(names), names)
check('... repetition helpers are not listed, the group says it mirrors',
      not any(groups.CARRIER_KEY in bpy.data.objects[n] for n in names)
      and next(i for i in lrows if i.label == 'Arm_L').data['badge'] == 'Mirror')
check('... the selected part on blue', next(i for i in lrows if i.label == 'Torso').on)
indent = {i.label: i.x for i in lrows}
check('... parts of a group indented', indent['Hand_L'] > indent['Arm_L'])
check('... the left cards go right of it (Quick HUD, key legend)', ub.strip_width(CTX, 1.0) >= lay[0].w)

pick = next(i for i in lrows if i.label == 'Backpack')
ub.run(CTX, pick)
check('Click a row: that part is selected and active', C.active_object == pack and pack.select_get()
      and not torso.select_get())
bpy.ops.mch.layer_pick(name='Torso', extend=True)
check('... Shift adds to the selection', torso.select_get() and pack.select_get())
eye = next(i for i in lay if i.kind == 'pmin' and i.action[1] == 'mch.layer_eye' and i.action[2]['name'] == 'Backpack')
ub.run(CTX, eye)
check('The eye hides the part', pack.hide_get())
lay = lp.items(CTX, W, H, 1.0)
check('... shown dimmed with the closed eye', next(i for i in lay if i.kind == 'lrow' and i.label == 'Backpack')
      .data['hidden'] and any(i.kind == 'pmin' and i.icon == 'eye_off' for i in lay))
bpy.ops.mch.layer_eye(name='Arm_L')
check('... a group eye hides all its parts', all(o.hide_get() for o in arm))
bpy.ops.mch.layer_eye(name='Arm_L')
bpy.ops.mch.layer_eye(name='Backpack')
check('... and shows them again', not any(o.hide_get() for o in arm) and not pack.hide_get())
fold = next(i for i in lay if i.kind == 'lfold')
ub.run(CTX, fold)
names2 = [i.label for i in lp.items(CTX, W, H, 1.0) if i.kind == 'lrow']
check('The arrow folds a group', 'Hand_L' not in names2 and 'Arm_L' in names2)
ub.run(CTX, next(i for i in lp.items(CTX, W, H, 1.0) if i.kind == 'lfold'))

heads = [i for i in lay if i.kind == 'shead']
check('Live Stack (0.24.82, open at first), Export and ZBrush Bridge under the list, the last two folded at first',
      [i.label for i in heads] == ['LIVE STACK', 'EXPORT', 'ZBRUSH BRIDGE'] and heads[0].on
      and not any(i.on for i in heads[1:]) and not any(i.kind == 'tbtn' and i.label == 'Export...' for i in lay))
ub.run(CTX, heads[1])
TALL = 1600
opened = lp.items(CTX, W, TALL, 1.0)
exp = next((i for i in opened if i.kind == 'tbtn' and i.label == 'Export...'), None)
check('... open Export: format, what, options and the Export button with those settings', exp is not None
      and exp.action[1] == 'mch.export_mesh' and exp.action[2]['file_format'] == S.mch_zbrush.export_format
      and exp.action[2]['scope'] == S.mch_zbrush.export_scope
      and {'OBJ', 'FBX', 'Selected', 'Visible'} <= {i.label for i in opened if i.kind == 'seg'})
ub.run(CTX, next(i for i in opened if i.kind == 'seg' and i.label == 'FBX'))
exp = next(i for i in lp.items(CTX, W, TALL, 1.0) if i.kind == 'tbtn' and i.label == 'Export...')
check('... choosing FBX changes what Export writes', S.mch_zbrush.export_format == 'FBX'
      and exp.action[2]['file_format'] == 'FBX')
ub.run(CTX, next(i for i in lp.items(CTX, W, TALL, 1.0) if i.kind == 'shead' and i.label == 'ZBRUSH BRIDGE'))
zb = lp.items(CTX, W, TALL, 1.0)
check('... open the Bridge: Send to ZBrush, Import Back, Open Folder',
      {'Send to ZBrush', 'Import Back', 'Open Folder'} <= {i.label for i in zb if i.kind == 'tbtn'})
missing = os.path.join(tempfile.mkdtemp(), 'not_made_yet')
S.mch_zbrush.exchange_dir = missing
ub.bump()
lp.items(CTX, W, TALL, 1.0)
check('... drawing never makes the exchange folder', not os.path.exists(missing))
S.mch_zbrush.exchange_dir = ''
mini = next(i for i in lay if i.kind == 'pbtn')
ub.run(CTX, mini)
folded = lp.items(CTX, W, H, 1.0)
check('– folds the Layers panel to a small tab', C.window_manager.mch_layers_min and folded[0].w < 60)
ub.run(CTX, next(i for i in folded if i.kind == 'pmin'))
check('... and opens again', not C.window_manager.mch_layers_min)
C.window_manager.mch_layers_scroll = 0.0
short = lp.layout(CTX, W, 640, 1.0)
check('A short viewport: the Layers panel scrolls (the wheel over it moves it)', short['content'] > short['view']
      and 'layers_panel' in inspect.getsource(ub.MCH_OT_ui_scroll.invoke))

# --- under Blender's header rows, Apply Modifiers, UI Size ----------------------------------------------------------
R = types.SimpleNamespace
hdr = [R(type='HEADER', x=0, y=H - 26, width=W, height=26), R(type='TOOL_HEADER', x=0, y=H - 52, width=W, height=26),
       R(type='WINDOW', x=0, y=0, width=W, height=H)]
CTX.area = R(type='VIEW_3D', regions=hdr)
ub.bump()
inset = ub.top_inset(CTX)
bar2 = tb.items(CTX, W, H, 1.0)
check("Top bar under Blender's see-through header rows (Region Overlap), not over them",
      abs(inset - 52) < 1e-6 and bar2[0].y + bar2[0].h <= H - 52, (inset, bar2[0].y + bar2[0].h))
hdr[0].y, hdr[1].y = H, H + 26                      # no overlap: the headers are outside the viewport region
check('... no header over the viewport: no gap', ub.top_inset(CTX) == 0.0)
CTX.area = None
ub.bump()
src = inspect.getsource(bb.MCH_OT_apply_modifiers_pick.invoke)
check('Apply Modifiers: meshes already selected are applied at once (picking only when nothing is selected)',
      'selected_editable_objects' in src and src.index('selected_editable_objects') < src.index('modal_handler_add'))
m = part('Mod_Part', (5, 0, 0))
m.modifiers.new('Bevel', 'BEVEL')
select_only(m)
bpy.ops.mch.apply_modifiers_pick()
check('... the selected mesh: its modifiers applied', len(m.modifiers) == 0 and len(m.data.polygons) > 6)
src = inspect.getsource(lp.draw_sizes)
check('UI Size in the Layers panel (folded): Viewport Panels, RMB Menu, Tool Menu, presets',
      all(k in src for k in ("'mecha_ui_size'", "'menu_size'", "'strip_scale'", 'icon_size_preset'))
      and 'draw_sizes' in inspect.getsource(lp.content))

# --- panel opacity, Quick HUD, key legend ---------------------------------------------------------------------------
from mecha_lab import quick_hud as qh, ui_gpu as G
real_pref2 = wui.pref
wui.pref = lambda name, default=True: 0.4 if name == 'panel_opacity' else real_pref2(name, default)
c, e = G.card_color(), G.card_color(edge=True)
wui.pref = real_pref2
check('Panel Opacity: only the card background follows it (Preferences / Layers panel > UI Size)',
      abs(c[3] - 0.4) < 1e-6 and c[:3] == G.CARD[:3] and abs(e[3] - G.CARD_EDGE[3] * 0.4) < 1e-6
      and 'panel_opacity' in wui.SIZE_KEYS and "'panel_opacity'" in inspect.getsource(lp.draw_sizes))
check('... every card uses it (menus / bars / panels / cards, Quick HUD, key legend); buttons and bars do not',
      'G.card_color()' in inspect.getsource(mm.draw) and 'card_color' in inspect.getsource(key_legend._draw)
      and 'card_color' in inspect.getsource(qh._draw_labels)
      and 'G.card_color' not in inspect.getsource(mm._draw_new))
real_on, real_min = sp.on, sp.minimised
sp.on = lambda c: True
sp.minimised = lambda c: False
hidden = not qh.visible(C)
sp.minimised = lambda c: True
back = qh._side_panel_shows(C)
sp.on, sp.minimised = real_on, real_min
check('Quick HUD: not shown while the side panel shows the same settings (folded panel: the HUD may show)',
      hidden and not back)
src = inspect.getsource(key_legend.box)
check('Key legend: the card fits the key column + the widest text (a long text ran out of it)',
      'keyw + what_w' in src)

# --- number bars: the fill follows the mouse ------------------------------------------------------------------------
from mecha_lab import base_mesh, ui_values as uv
bd = base_mesh.scene_defaults(C)
rna = bd.bl_rna.properties['height']
v_end = uv.drag(bd, 'height', rna.soft_min, 240.0, width=240.0)
v_half = uv.drag(bd, 'height', rna.soft_min, 120.0, width=240.0)
check('Number bar: dragging across the whole bar = its whole range (the fill follows the mouse; Base Mesh Height)',
      abs(v_end - rna.soft_max) < 1e-3 * rna.soft_max and abs(v_half - (rna.soft_min + rna.soft_max) / 2) < 1e-2,
      (v_end, v_half))
seg = bd.bl_rna.properties['bevel_segments']
s_end = uv.drag(bd, 'bevel_segments', seg.hard_min, 400.0, width=400.0)
check('... whole numbers too (the whole range over the bar)', s_end == seg.hard_max, s_end)
check('... Shift: ten times finer', abs(uv.drag(bd, 'height', 1.0, 240.0, fine=True, width=240.0) - 1.0
                                        - (rna.soft_max - rna.soft_min) / 10) < 1e-3)
br = S.mch_brush
lw = br.bl_rna.properties['line_width']
br.line_width = 0.339
lw_end = uv.drag(br, 'line_width', 0.339, 140.0 * (1 - 0.339 / lw.soft_max), width=140.0)
big = uv.drag(bd, 'height', 62.0, 100.0, width=200.0)
check('... Line Width: the bar goes to 2 (was 0.5), its end = 2; a value past a bar (big scene) moves as fast as it is big',
      lw.soft_max >= 2.0 and abs(lw_end - lw.soft_max) < 1e-3 and big - 62.0 >= 31.0 - 1e-6, (lw_end, big))
src = inspect.getsource(qh.MCH_OT_quick_hud_press._modal_ui)
check('... the drag keeps going at the viewport edge (the cursor wraps round) and uses the bar width',
      'cursor_warp' in src and 'width=it.w' in src)

# --- the old way back ---------------------------------------------------------------------------------------------
ann = wui.MCH_AddonPreferences.__annotations__
check('Preferences: Tool Menu Place (Bottom / Left) and Layers Panel', 'tool_menu' in ann and 'layers_panel' in ann
      and "'tool_menu'" in inspect.getsource(wui.MCH_AddonPreferences.draw))
real_pref = wui.pref
wui.pref = lambda name, default=True: 'LEFT' if name == 'tool_menu' else real_pref(name, default)
ub.bump()
left_items = ub.all_items(CTX)
check('... Left: the strip, the bottom toolbar and the actions card come back, no menu / dock / Layers panel',
      ub.strip_on(CTX) and ub.bar_on(CTX) and any(i.kind == 'arow' for i in left_items)
      and not ub.menu_on(CTX) and not lp.on(CTX) and not any(i.kind == 'lrow' for i in left_items))
wui.pref = real_pref
ub.bump()
ts.effective_tool = real_tool
mm.ts.effective_tool = real_tool
summary()
