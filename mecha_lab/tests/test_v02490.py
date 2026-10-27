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
      dt[0].label == 'Select' and [i.label for i in dt][-6:] == ['Apply Modifiers', 'Reset Axis',
                                                                 'Origin to Geometry', 'Origin to 3D Cursor',
                                                                 'Symmetry', 'Mirror']
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
check('Key legend and Symmetry card go above the menu + actions',
      'dock_top' in inspect.getsource(key_legend._draw) and 'dock_top' in inspect.getsource(symmetry._anchor))

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
check('Export and ZBrush Bridge under the list, folded at first',
      [i.label for i in heads] == ['EXPORT', 'ZBRUSH BRIDGE'] and not any(i.on for i in heads)
      and not any(i.kind == 'tbtn' and i.label == 'Export...' for i in lay))
ub.run(CTX, heads[0])
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
