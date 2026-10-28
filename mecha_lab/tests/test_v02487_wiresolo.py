"""0.24.77 VIEW Wire | Solo on the MECHA LAB corner card: the wireframe a Make Quad / Quad Remesh result shows can be
turned off (and on) without the Object Properties, and Solo shows only the selected parts (Blender's Local View) like
the ZBrush screen's Solo.  The side panel starts below the taller card where they would meet.

Not verified here (no window in bpy): the Local View itself and how the card looks."""
import types

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import bottom_bar, side_panel, tool_state as ts, ui_bars as ub, zb_sculpt as zs, zb_ui as zu
from mecha_lab.ui_gpu import ui_factor

mecha_lab.register()
fresh()
C = bpy.context
W, H = 2560, 1440


class Ctx:
    region = types.SimpleNamespace(width=W, height=H, x=0, y=0, type='WINDOW')
    area = None

    def __getattr__(self, n):
        return getattr(bpy.context, n)


CTX = Ctx()
real_ws = ts.is_mecha_workspace
ts.is_mecha_workspace = lambda ws: True
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
a = C.active_object
bpy.ops.mesh.primitive_cube_add(location=(3, 0, 0))
b = C.active_object
a.show_wire = True                               # (as a Make Quad result comes out)
for o in (a, b):
    o.select_set(False)

def corner_segs():
    """The corner card's buttons (other cards have their own 'Wire' pills)."""
    cx, cy, cw, ch = zu.corner_box(CTX, W, H, K)
    ub.bump()
    its = ub.all_items(CTX)
    return its, {i.label: i for i in its if i.kind == 'seg' and cx - 0.5 <= i.x <= cx + cw and cy - 0.5 <= i.y <= cy + ch}


K = ui_factor(CTX, CTX.region)                  # (the drawn UI's size factor)
items, seg = corner_segs()
check('MECHA LAB corner card: a VIEW row with Wire and Solo under MECHA LAB | ZBRUSH and STYLE',
      bottom_bar.ui_active(CTX) and {'MECHA LAB', 'ZBRUSH', 'ZBrush', 'Blender', 'Wire', 'Solo'} <= set(seg)
      and seg['Wire'].y < seg['ZBrush'].y and abs(seg['Wire'].y - seg['Solo'].y) < 0.5
      and any(i.kind == 'glabel' and i.label == 'VIEW' for i in items), sorted(seg))
check('... Wire lit while a part shows its wireframe, Solo dark (not soloed)', seg['Wire'].on and not seg['Solo'].on)
cx, cy, cw, ch = zu.corner_box(CTX, W, H, K)
check('... the card holds the third row', all(cy - 0.5 <= seg[n].y and seg[n].y + seg[n].h <= cy + ch + 0.5
                                              for n in ('Wire', 'Solo', 'MECHA LAB')), (cy, ch, seg['Wire'].y))

ub.run(CTX, seg['Wire'])
check('Wire with nothing selected: every visible part\'s wireframe off', not a.show_wire and not b.show_wire)
_its, seg = corner_segs()
check('... the button goes dark', not seg['Wire'].on)
b.select_set(True)
C.view_layer.objects.active = b
r = bpy.ops.mch.view_toggle(action='WIRE')
check('Wire with a part selected: only that one shows its wireframe (all edges)', r == {'FINISHED'} and b.show_wire
      and b.show_all_edges and not a.show_wire)
bpy.ops.mch.view_toggle(action='WIRE')
check('... again: off', not b.show_wire)

b.select_set(False)
r = bpy.ops.mch.view_toggle(action='SOLO')
check('Solo with nothing selected (and not soloed): nothing happens, it says what to do', r == {'CANCELLED'})
b.select_set(True)
try:
    r = bpy.ops.mch.view_toggle(action='SOLO')
except RuntimeError as ex:
    r = str(ex)
check('Solo without a 3D view (bpy has no window): no error, nothing changed', r == {'CANCELLED'} and not zs.solo_on(C),
      r)

# the side panel keeps clear of the taller card
real_on = side_panel.on
side_panel.on = lambda c: True
bpy.ops.mch.bar_tool(tool='CUT')
x0, top, w = side_panel.frame(W, H, K, CTX)
overlap = cx < x0 + w and cx + cw > x0
check('The side panel starts below the corner card where they would meet', not overlap or top <= cy - 7.5 * K,
      (top, cy, overlap))
check('... without a context it is where it was', side_panel.frame(W, H, K)[1] == H - side_panel.TOP_MARGIN * K)
side_panel.on = real_on

bpy.ops.object.mode_set(mode='SCULPT')
real_zon = zs.on
zs.on = lambda c: True
segs = set(corner_segs()[1])
check('ZBRUSH screen: the corner card as before (its own PolyF / Solo on the right shelf)',
      'Wire' not in segs and 'MECHA LAB' in segs, sorted(segs))
zs.on = real_zon
bpy.ops.object.mode_set(mode='OBJECT')
ts.is_mecha_workspace = real_ws
summary()
