"""0.24.58 Drawn bottom toolbar (one dark bar, icons, key letters, names on hover) and the left tool strip (every
tool by job), in the Mecha Menu look; clicks via the HUD click operator; the Quick HUD / key legend / Tool Active
button move right of the strip; Preferences: Drawn Toolbar / Tool Strip."""
import inspect
import types

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import bottom_bar as bb, mecha_menu as mm, quick_hud as qh, tool_state as ts, ui_bars as ub
from mecha_lab import ui_gpu as G

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
real_ui = bb.ui_active
bb.ui_active = lambda c: True
S.mch_settings.mch_active_tool = 'CUT'

W, H = 1920, 1000
bar = ub.bar_items(C, W, H, 1.0)
card = [i for i in bar if i.kind == 'card']
btns = [i for i in bar if i.kind == 'abtn']
check('Bottom toolbar: one dark bar, bottom middle, a button per toolbar tool', len(card) == 1
      and abs(card[0].x + card[0].w / 2 - W / 2) < 1 and card[0].y < 60 and len(btns) == len(bb.BAR_TOOLS))
check('... every button inside the bar, icons (PNG / glyph), key letters', all(card[0].x <= b.x and
      b.x + b.w <= card[0].x + card[0].w for b in btns) and all(b.icon for b in btns)
      and {i.label for i in bar if i.kind == 'keycap'} >= {'F', 'C', 'B'})
narrow = ub.bar_items(C, 700, H, 1.0)
nc = [i for i in narrow if i.kind == 'card'][0]
check('Narrow viewport: smaller buttons, the bar stays on screen', nc.x >= 0 and nc.x + nc.w <= 700)
groups = ts.grouped_tools()
strip = ub.strip_items(C, W, H, 1.0)
sbtn = [i for i in strip if i.kind in {'button', 'sbtn'}]     # 0.24.59 'sbtn' = icon + name
check('Left strip: every tool once, grouped with headings', len(sbtn) == sum(len(r) for _n, r in groups)
      and len([i for i in strip if i.kind == 'striphead']) == len(groups)
      and {i.action[1] for i in sbtn} == {t[0] for _n, r in groups for t in r})
sc = [i for i in strip if i.kind == 'card'][0]
check('... a column at the left edge, inside the viewport, the tool in use on (blue)', sc.x < 40 and sc.y >= 0
      and sc.y + sc.h <= H and next(i for i in sbtn if i.action[1] == 'CUT').on)
short = ub.strip_items(C, W, 600, 1.0)
ss = [i for i in short if i.kind == 'card'][0]
check('Short viewport: the strip shrinks / adds a column to fit', ss.y >= 0 and ss.y + ss.h <= 600
      and ub.strip_layout(600, 1.0, groups)[0] >= 3)
fake_region = types.SimpleNamespace(width=W, height=H, x=0, type='WINDOW')
ctx = types.SimpleNamespace(region=fake_region, area=None, window_manager=C.window_manager, scene=S,
                            preferences=C.preferences, workspace=C.workspace, mode='OBJECT')
real_all = ub.all_items
ub.all_items = lambda c: ub.bar_items(C, W, H, 1.0) + ub.strip_items(C, W, H, 1.0)
plate = next(i for i in ub.strip_items(C, W, H, 1.0) if i.kind in {'button', 'sbtn'} and i.action[1] == 'PLATE')
inside, it = ub.hit(ctx, plate.x + 3, plate.y + 3)
check('Click on a strip button: that tool', inside and it is not None and it.action == ('tool', 'PLATE'))
ub.run(C, it)
check('... switches to it', ts.effective_tool(C) == 'PLATE' or S.mch_settings.mch_active_tool == 'PLATE')
inside, it = ub.hit(ctx, sc.x + sc.w - 2, sc.y + 2)
check('Click on the strip / bar background: taken (nothing behind), no button', inside and it is None)
inside, it = ub.hit(ctx, W / 2, H / 2)
check('Click in the viewport: not taken (the tool gets it)', not inside)
ub.all_items = real_all
src = inspect.getsource(qh.MCH_OT_quick_hud_press.invoke)
check('The HUD click operator asks the bar / strip first', 'ui_bars.hit' in src
      and src.index('ui_bars.hit') < src.index('symmetry.card_hit'))
check('The round-button toolbar is off while the drawn one is on (Preferences)',
      "not _pref('drawn_toolbar', True)" in inspect.getsource(bb.MCH_GGT_bottom_toolbar.poll))
kms = [(k.name, it.type) for k in C.window_manager.keyconfigs.addon.keymaps for it in k.keymap_items
       if it.idname == 'mch.ui_hover']
check('Name bubbles: a pass-through mouse-move item tracks the mouse', ('3D View', 'MOUSEMOVE') in kms)
r = bpy.ops.mch.ui_hover('INVOKE_DEFAULT') if False else None
check('Quick HUD / key legend / Tool Active button move right of the strip',
      'strip_width' in inspect.getsource(qh.current) and 'strip_width' in inspect.getsource(
          mecha_lab.key_legend.box) and 'strip_width' in inspect.getsource(bb.active_button_pos))
# paint once with stand-ins (no GPU in the background)
CALLS = []
real = {n: getattr(G, n) for n in ('rounded_rect', 'lines', 'text', 'image', 'glyph', 'fit')}
G.rounded_rect = lambda *a, **k: CALLS.append('rect')
G.lines = lambda *a, **k: CALLS.append('lines')
G.text = lambda *a, **k: CALLS.append('text') or 10.0
G.image = lambda *a, **k: CALLS.append('image') or True
G.glyph = lambda *a, **k: CALLS.append('glyph')
G.fit = lambda s, *a: s
items = ub.bar_items(C, W, H, 1.0) + ub.strip_items(C, W, H, 1.0)
err = None
try:
    mm.draw(items, items[3], 1.0, C)
    mm.draw(items, None, 1.0, C)
except Exception as ex:
    err = repr(ex)
for n, f in real.items():
    setattr(G, n, f)
check('Drawing runs (stand-in painter): cards, icons, key letters, headings, a name bubble', err is None
      and CALLS.count('image') > 40 and CALLS.count('text') > 15, err)
bb.ui_active = real_ui
summary()
