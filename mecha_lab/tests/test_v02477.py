"""0.24.57 Quick HUD / Symmetry card clicks: a quick second click (DOUBLE_CLICK) is taken too, a click between
rows or just beside a card button still counts, a click on the card never falls through to the tool."""
import types

from _harness import bpy, check, cube, fresh, select_only, summary

import mecha_lab
from mecha_lab import quick_hud as qh, screw_stamp as ss, symmetry as sy, workspace_ui as wui
import mecha_lab.bottom_bar as bb

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
S.mch_settings.mch_active_tool = 'CUT'

km = {(k.name, it.value) for k in C.window_manager.keyconfigs.addon.keymaps for it in k.keymap_items
      if it.idname == 'mch.quick_hud_press'}
check('HUD clicks: press and double-click, in 3D View and before Object Mode clicks',
      {('3D View', 'PRESS'), ('3D View', 'DOUBLE_CLICK'), ('Object Mode', 'PRESS'), ('Object Mode', 'DOUBLE_CLICK')}
      <= km, km)
tk = [(k[0], k[1]['value']) for k in wui._tool_keymap('CUT')]
check('... and in every drawing tool, before the tool\'s own clicks',
      tk.index(('mch.quick_hud_press', 'DOUBLE_CLICK')) < tk.index(('mch.cut_stroke', 'PRESS')))
sk = [(k[0], k[1]['value']) for k in ss.TOOL_KEYMAP]
check('... Screw: before its double-click (take the screw back)',
      sk.index(('mch.quick_hud_press', 'DOUBLE_CLICK')) < sk.index(('mch.screw_stamp', 'DOUBLE_CLICK')))

# a fake region / HUD layout to hit-test
its, grip, rows = qh.current(C) if qh.current(C)[0] is not None else (None, None, None)
real_cur = qh.current
grip, rows = (200.0, 900.0), [(200.0, 860.0), (200.0, 826.0), (200.0, 792.0)]
qh.current = lambda c: ([None, None, None], grip, rows)
k = 1.0
from mecha_lab import ui_gpu
real_f = ui_gpu.ui_factor
ui_gpu.ui_factor = lambda c, r=None: 1.0
check('On a row: that row', qh.hit(C, 200, 826) == ('row', 1))
gap_y = (826 + 860) / 2.0
check('Between two rows: the nearer row (not the tool behind)', qh.hit(C, 200, gap_y + 3) == ('row', 0)
      and qh.hit(C, 200, gap_y - 3) == ('row', 1))
check('On the card edge beside a row: that row', qh.hit(C, 200 + qh.ROW_W / 2 + 5, 792) == ('row', 2))
check('Above the first row on the card: the title (move the HUD)', qh.hit(C, 120, 912) == ('grip', None))
check('Outside the card: nothing (the click goes to the tool)', qh.hit(C, 200, 700) is None
      and qh.hit(C, 500, 826) is None)
qh.current = real_cur
ui_gpu.ui_factor = real_f

# card: just beside a button
part = cube('Part', loc=(2, 0, 0))
select_only(part)
sy.set_mode(C, part, 'MIRROR')
real_ui = bb.ui_active
bb.ui_active = lambda c: True
region = types.SimpleNamespace(width=1600, height=900)
real_items = sy.card_items
sy.card_items = lambda c: sy.build_card(c, 1600, 900, 1.0)
items = sy.build_card(C, 1600, 900, 1.0)
yb = next(i for i in items if i.label == 'Mirror Y')
inside, it = sy.card_hit(C, yb.x - 2, yb.y + yb.h / 2)
check('Card: in the gap just left of the Mirror Y button still clicks it', inside and it is not None and it.label == 'Mirror Y')
card = next(i for i in items if i.kind == 'card')
inside, it = sy.card_hit(C, card.x + card.w - 3, card.y + 3)
check('... a click on the empty card is still taken by the card (nothing behind it)', inside)
sy.card_items = real_items
bb.ui_active = real_ui

# a symmetric part in a group moves as one piece; the group itself can be mirrored
from mathutils import Vector
from mecha_lab import groups as gr, radial_sym as rs, actions_menu as am, mecha_menu as mm
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
p = cube('Hex', size=0.5, loc=(1.5, 0, 0))
select_only(p)
sy.set_mode(C, p, 'RADIAL')
S.mch_rsym.count = 6
rs.refresh(C)


def cluster(o):
    C.view_layer.update()
    me = o.evaluated_get(C.evaluated_depsgraph_get()).to_mesh()
    pts = [o.matrix_world @ v.co for v in me.vertices]
    c = sum(pts, Vector()) / len(pts)
    return c, max((q - c).length for q in pts)


c0, r0 = cluster(p)
g = gr.create(C, [p])
check('Grouping a radial part: its centre follows the group', S.mch_rsym.pivot.parent == g)
g.location.x += 5.0
c1, r1 = cluster(p)
check('... move the group: the six copies move as one piece (same ring, not spread round the world origin)',
      abs(c1.x - (c0.x + 5.0)) < 1e-3 and abs(r1 - r0) < 1e-3, (c0, c1, r0, r1))
select_only(g)
C.view_layer.objects.active = g
r = bpy.ops.mch.actions_mirror(axis=0)
check('Mirror X with the group selected: the whole group is mirrored across the world X plane',
      r == {'FINISHED'} and gr.repeat_mode(g) == 'MIRROR' and gr.repeat_axes(g)[0] and gr.repeat_center(g) == 'WORLD')
items = mm.build(C, 800, 450, 1600, 900, 1.0)
check('... shown on (blue) in the menu', next(i for i in items if i.label == 'Mirror X').on)
dg = C.evaluated_depsgraph_get()
car = gr.carrier_of(g)
xs = [(i.matrix_world @ Vector((6.5, 0, 0))).x for i in dg.object_instances
      if i.is_instance and i.parent is not None and i.parent.original == car]
check('... the copy sits on the other side', xs and all(x < -5.0 for x in xs), xs)
bpy.ops.mch.actions_mirror(axis=0)
check('... Mirror X again: off', gr.repeat_mode(g) == 'OFF')
gr.ungroup(C, g)
check('Ungroup: the centre stays where it is (no parent)', S.mch_rsym.pivot.parent is None
      and abs(S.mch_rsym.pivot.matrix_world.translation.x - 5.0) < 1e-6)
summary()
