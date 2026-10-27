"""0.24.50 Mecha Menu: the RMB popup drawn by Mecha Lab itself in the Substance 3D Modeler look (tool strip |
'<Tool> tool' card | Actions panel), sized for big screens; hold Ctrl + Alt = the menu stays open while held
(clicks never close it); Quick HUD and key legend as readable dark cards."""
import inspect
import os
import tempfile
import types

from _harness import bpy, check, cube, fresh, select_only, summary

import mecha_lab
from mecha_lab import last_used, mecha_menu as mm, quick_hud as qh, tool_recent as tr, ui_gpu as G
from mecha_lab import cut_engine as ce, actions_menu as am

TMP = os.path.join(tempfile.mkdtemp(), 'last_used.json')
last_used._path = lambda: TMP
last_used._DATA = {}
mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
for t in ('PLATE', 'BASE', 'CUT'):
    tr.note(t)
S.mch_settings.mch_active_tool = 'CUT'
part = cube('Part')
select_only(part)

W, H = 1920, 1080
items = mm.build(C, 960, 540, W, H, 1.0)
cards = [i for i in items if i.kind == 'card']
check('Three cards side by side: tool strip | tool card | Actions', len(cards) == 3
      and cards[0].x + cards[0].w < cards[1].x and cards[1].x + cards[1].w < cards[2].x)
check('... all on screen', all(0 <= i.x and i.x + i.w <= W and 0 <= i.y and i.y + i.h <= H for i in items))
strip = [i for i in items if cards[0].hit(i.x + 1, i.y + 1) and i.kind == 'button']
check('Strip: Select first, then the recent tools (icons), the current tool on (blue)',
      strip[0].label == 'Select / Move' and [i.label for i in strip[1:4]] == ['Cut', 'Base Mesh', 'Armor Plate']
      and strip[1].on and strip[1].icon == 'png:cut')
titles = [i.label for i in items if i.kind == 'title']
check('Card title "Cut tool", Shapes / Stamps tabs, a 4-column grid of the 6 shapes',
      'Cut tool' in titles and [i.label for i in items if i.kind == 'tab'] == ['Shapes', 'Stamps']
      and len([i for i in items if i.kind == 'tile']) == 6
      and len({round(i.x) for i in items if i.kind == 'tile'}) == 4)
sl = [i for i in items if i.kind in {'slider', 'seg', 'toggle', 'cycle'}]
check('Settings = the Quick HUD rows (sliders, segmented choices, toggles)', any(i.kind == 'slider' for i in sl)
      and any(i.kind == 'seg' for i in sl) and any(i.kind == 'toggle' for i in sl), [i.kind for i in sl])
secs = [i.label for i in items if i.kind == 'section']
check('Actions panel sections like Modeler', secs[:1] == ['Settings']
      and secs[1:] == ['Actions', 'Shading', 'Resolution', 'Symmetry', 'Groups', 'Repetition', 'Visibility'],
      secs)                                                       # 0.24.52 + Shading, Groups
ops = [i.action[1] for i in items if i.action and i.action[0] == 'op']
bad = []
for idname in ops:
    mod, name = idname.split('.')
    try:
        getattr(getattr(bpy.ops, mod), name).get_rna_type()
    except (AttributeError, KeyError):
        bad.append(idname)
check('... every button runs a real operator', not bad and len(ops) >= 15, bad)
small = mm.build(C, 960, 540, W, H, 1.0)
big = mm.build(C, 960, 540, W * 2, H * 2, 2.0)
check('Bigger on big screens (size factor)', [i for i in big if i.kind == 'card'][1].w
      > 1.9 * [i for i in small if i.kind == 'card'][1].w)
check('Size factor: 4K at 100 % doubles, a normal screen stays, Mecha UI Size multiplies',
      abs(G.ui_factor(C, types.SimpleNamespace(height=2000)) / (C.preferences.system.ui_scale or 1.0) - 2.0) < 1e-6
      and abs(G.ui_factor(C, types.SimpleNamespace(height=800)) / (C.preferences.system.ui_scale or 1.0) - 1.0) < 1e-6)
corner = mm.build(C, 5, 5, W, H, 1.0)
check('Opened at a screen corner: still all on screen', all(0 <= i.x and i.x + i.w <= W and 0 <= i.y
                                                            and i.y + i.h <= H for i in corner))


def find(its, kind, label):
    return next(i for i in its if i.kind == kind and i.label == label)


# clicks
items = mm.build(C, 960, 540, W, H, 1.0)
r = mm.run(C, find(items, 'tile', 'Circle'))
check('Shape tile: sets the shape, the menu stays', S.mch_brush.shape == 'CIRCLE' and r is False)
mm.run(C, find(items, 'tab', 'Stamps'))
check('Stamps tab', C.window_manager.mch_show_custom_shapes)
items = mm.build(C, 960, 540, W, H, 1.0)
check('... the grid shows stamps (or a note when there are none)', not any(i.kind == 'tile' and i.label == 'Circle'
                                                                        for i in items))
mm.run(C, find(items, 'tab', 'Shapes'))
x_btn = find(items, 'abtn', 'Mirror X')
mm.run(C, x_btn)
check('Symmetry X button: live mirror on the part', am.mirror_mod(part) is not None
      and am.mirror_mod(part).use_axis[0])
items = mm.build(C, 960, 540, W, H, 1.0)
check('... shown on (blue) next time', find(items, 'abtn', 'Mirror X').on)
seg = next(i for i in items if i.kind == 'seg' and not i.on and i.data is not None)   # (Line / Sketch: modes)
mm.run(C, seg)
check('Segmented choice sets that value', getattr(seg.data, seg.prop) == seg.action[2])
cut = S.mch_cut
cut.depth = 0.31
slider = next(i for i in items if i.kind == 'slider' and i.prop == 'depth')
mm.run(C, slider, ctrl=True)
check('Ctrl + click on a slider: default', abs(cut.depth - cut.bl_rna.properties['depth'].default) < 1e-6)
check('Click on a slider (no drag): type the value', mm.run(C, slider) == 'TYPE')
was = 'CUT' in tr.favorites()
check('Star pins / unpins the tool; the set name cycles the favorites sets',
      mm.run(C, find(items, 'button', 'Pin / unpin Cut')) is False and ('CUT' in tr.favorites()) != was
      and (mm.run(C, next(i for i in items if i.kind == 'pill')) or tr.current_set() == 'CREATURE'))
C.window_manager.mch_fav_set = 'MECHA'
n = len(bpy.data.objects)
check('Tool button closes the menu; held (Ctrl + Alt) it switches in place and stays',
      mm.run(C, find(items, 'button', 'Base Mesh'), hold=True) is False
      and S.mch_settings.mch_active_tool == 'BASE')
select_only(part)
dup = find(items, 'abtn', 'Duplicate')
r = mm.run(C, dup, hold=True)
check('Held: Duplicate makes the copy in place (no grab), the menu stays', r is False
      and len(bpy.data.objects) == n + 1)
items = mm.build(C, 960, 540, W, H, 1.0)
check('Base Mesh: the card shows its profiles (Flat / Chamfer / Bevel ...)',
      'Base Mesh tool' in [i.label for i in items if i.kind == 'title']
      and any(i.kind == 'tile' and i.action[1] == 'mch.set_profile' for i in items))
check('RMB opens it (stroke tools and Select / Move), the old panel stays as an option',
      'mecha_menu.open_menu' in inspect.getsource(ce.GateLogic.modal)
      and 'mecha_menu.open_menu' in inspect.getsource(am.MCH_OT_actions_menu.invoke)
      and "pref('classic_rmb_popup'" in inspect.getsource(mm.use_menu))

# hold Ctrl + Alt
items_km = [it for km in C.window_manager.keyconfigs.addon.keymaps for it in km.keymap_items
            if it.idname == 'mch.mecha_hold_gate']
check('Hold Ctrl + Alt: keys for either order (left / right)', len(items_km) == 4
      and {it.type for it in items_km} == {'LEFT_ALT', 'RIGHT_ALT', 'LEFT_CTRL', 'RIGHT_CTRL'})
src = inspect.getsource(mm.MCH_OT_mecha_hold_gate.modal)
check('... opens after a moment held (sooner + click = a normal Ctrl + Alt draw)', mm.HOLD_DELAY > 0.1
      and 'PASS_THROUGH' in src and 'hold=True' in src)
src = inspect.getsource(mm.MCH_OT_mecha_menu.modal)
check('... in hold mode clicks never close it, letting go of Ctrl / Alt does',
      "'LEFT_CTRL'" in src and 'self.hold' in src and 'RELEASE' in src)
outside = types.SimpleNamespace(workspace=types.SimpleNamespace(name='Layout', get=lambda k, d=None: d),
                                mode='OBJECT', area=types.SimpleNamespace(type='VIEW_3D'), scene=S,
                                window_manager=C.window_manager)
check('... only in MECHA LAB', not mm.MCH_OT_mecha_hold_gate.poll(outside))

# readable HUD / legend
grip, rows = qh.layout_rows(1920, 1080, 4, k=1.0)
grip2, rows2 = qh.layout_rows(3840, 2160, 4, k=2.0)
check('Quick HUD: under the view name text, twice as big on a 4K screen', 1080 - grip[1] >= 140
      and abs((rows2[0][1] - rows2[1][1]) - 2 * (rows[0][1] - rows[1][1])) < 1e-6)
check('Quick HUD and key legend paint dark rounded cards with the size factor',
      'G.rounded_rect' in inspect.getsource(qh._draw_labels) and 'ui_factor' in inspect.getsource(qh._draw_labels)
      and 'G.rounded_rect' in inspect.getsource(mecha_lab.key_legend._draw))
check('Text fits its button (shortened with …)', G.fit('A very long tool name indeed', 10, 40).endswith('…'))
check('Icons are read into GPU textures and the temporary image is removed (nothing left in the file)',
      'bpy.data.images.remove' in inspect.getsource(G._texture) and not bpy.data.images)

# paint once with recording stand-ins (no GPU without a window): catches mistakes in the drawing code
CALLS = []
real = {n: getattr(G, n) for n in ('rounded_rect', 'lines', 'text', 'image', 'glyph', 'fit')}
G.rounded_rect = lambda *a, **k: CALLS.append('rect')
G.lines = lambda *a, **k: CALLS.append('lines')
G.text = lambda *a, **k: CALLS.append('text') or 10.0
G.image = lambda *a, **k: CALLS.append('image') or True
G.glyph = lambda *a, **k: CALLS.append('glyph')
G.fit = lambda s, *a: s
items = mm.build(C, 960, 540, W, H, 1.0)
err = None
try:
    for hov in [None] + [i for i in items if i.clickable()][:40]:
        mm.draw(items, hov, 1.0, C)
except Exception as ex:
    err = repr(ex)
check('Drawing code runs for every hovered button (stand-in painter)', err is None
      and CALLS.count('image') > 5 and CALLS.count('rect') > 20, err)
from mecha_lab import key_legend as kl
kl._stroke_tool = lambda c: 'CUT'
CALLS.clear()
kl._draw()
check('Key legend paints its card and lines', CALLS.count('rect') >= 2 and CALLS.count('text') >= len(kl.lines('CUT')))
for n, f in real.items():
    setattr(G, n, f)
summary()
