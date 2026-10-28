"""0.24.79 NAV ZBrush | Blender on the corner card: how the view turns (the ZBrush canvas / right-drag, or Blender's
own - middle mouse, the gizmo) chosen apart from STYLE, so the ZBrush screen can be used with Blender's navigation and
the MECHA LAB Select tool box-selects again.  With ZBrush navigation the Select tool's click on the empty canvas
deselects, and the ZBrush screen's select mode picks another SubTool with a click.  Concept Move / Path Move /
Silhouette Move show their brush settings in the Mecha top bar.

Not verified here (no window in bpy): real mouse drags, the view turning, a click picking a SubTool under the mouse."""
import inspect
import types

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import (key_legend, side_panel as sp, tool_state as ts, top_bar as tb, ui_bars as ub,
                       zb_sculpt as zs, zb_ui as zu)
from mecha_lab.ui_gpu import ui_factor

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
W, H = 2560, 1440


class Ctx:
    region = types.SimpleNamespace(width=W, height=H, x=0, y=0, type='WINDOW')
    area = None
    region_data = object()

    def __getattr__(self, n):
        return getattr(bpy.context, n)


CTX = Ctx()
real_ws = ts.is_mecha_workspace
ts.is_mecha_workspace = lambda ws: True
K = ui_factor(CTX, CTX.region)


def corner():
    cx, cy, cw, ch = zu.corner_box(CTX, W, H, K)
    ub.bump()
    its = zu.corner_items(CTX, W, H, K)
    return its, {(i.label, i.action[1] if i.action else ''): i for i in its if i.kind == 'seg'}


zs.set_style('ZBRUSH')
zs.set_nav('ZBRUSH')
its, seg = corner()
labels = [i.label for i in its if i.kind == 'glabel']
check('Corner card (ZBrush style): a NAV row ZBrush | Blender under STYLE', 'NAV' in labels
      and labels.index('NAV') == labels.index('STYLE') + 1 and seg[('ZBrush', 'mch.zb_nav_style')].on
      and not seg[('Blender', 'mch.zb_nav_style')].on, labels)
cx, cy, cw, ch = zu.corner_box(CTX, W, H, K)
check('... the card holds it (4 rows in MECHA LAB: + VIEW)', all(cy - 0.5 <= i.y and i.y + i.h <= cy + ch + 0.5
                                                                for i in its if i.kind != 'card'))
check('ZBrush navigation: the canvas / right-drag turn the view (as before)', zs.nav_on(C))
ub.run(CTX, seg[('Blender', 'mch.zb_nav_style')])
check('NAV Blender (from the card): kept in the preferences, the canvas no longer turns the view',
      zs.nav_style() == 'BLENDER' and not zs.nav_on(C))
check('... the MECHA LAB Select tool gets the press again (the ZBrush canvas press does not run)',
      not zs.MCH_OT_zb_obj_press.poll(C))
check('... the ZBrush shelf\'s Move / Zoom3D / Rotate buttons still work (they turn the view on purpose)',
      zs.MCH_OT_zb_nav.poll(CTX))
r = zs.RMBDrag()
r.rmb_drag_start(C, types.SimpleNamespace(mouse_x=0, mouse_y=0, alt=False, is_tablet=False))
check('... a right-drag no longer turns the view (a right click opens the menu as before)', not r.rmb_live)
legend = zu.KEYS_TEXT
zs_text = [i.label for i in zu.key_legend(CTX, K, __import__('mecha_lab.mecha_menu', fromlist=['x']).Item, 0, 0)
           if i.kind == 'pnote']
check('... the ZBrush key legend says Middle mouse instead of the canvas drags', 'Middle mouse' in zs_text
      and 'Drag canvas' not in zs_text, zs_text[:6])
src = inspect.getsource(zs.MCH_OT_zb_press.invoke)
check('... the ZBrush mouse: the canvas does not turn the view with NAV Blender',
      'if not nav_on(context):' in src and src.index('if not nav_on(context):') < src.index("mode='PAN' if canvas"))
zs.set_style('BLENDER')
its, seg = corner()
check('STYLE Blender: no NAV row (Blender\'s own anyway)', 'NAV' not in [i.label for i in its if i.kind == 'glabel'])
zs.set_style('ZBRUSH')
zs.set_nav('ZBRUSH')

# --- the Select tool with ZBrush navigation: a click on the empty canvas deselects ------------------------------
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add()
bpy.ops.mesh.primitive_cube_add(location=(3, 0, 0))
for o in bpy.data.objects:
    o.select_set(True)
me = types.SimpleNamespace(x0=100, y0=100, alt=False, limit=3)
res = zs.MCH_OT_zb_obj_press.modal(me, C, types.SimpleNamespace(type='LEFTMOUSE', value='RELEASE', shift=False,
                                                                mouse_x=101, mouse_y=100, alt=False))
check('ZBrush navigation, Select tool: a click on the empty canvas deselects all (it did nothing)',
      res == {'FINISHED'} and not any(o.select_get() for o in bpy.data.objects))
for o in bpy.data.objects:
    o.select_set(True)
zs.MCH_OT_zb_obj_press.modal(me, C, types.SimpleNamespace(type='LEFTMOUSE', value='RELEASE', shift=True,
                                                          mouse_x=100, mouse_y=100, alt=False))
check('... Shift + click on the canvas keeps the selection', all(o.select_get() for o in bpy.data.objects))
src = inspect.getsource(zs.MCH_OT_zb_obj_press.modal)
check('... a drag past the drag threshold turns the view (Alt: move)', "bpy.ops.mch.zb_nav('INVOKE_DEFAULT'" in src
      and 'self.limit' in src)

# --- the ZBrush screen's select mode picks another SubTool --------------------------------------------------------
src = inspect.getsource(zs.MCH_OT_zb_press.invoke)
pick, passthru = src.index('switch_to(context, other)'), src.index("return {'PASS_THROUGH'}                       # Blender")
check('ZBrush select mode (Q): a click on another SubTool picks it - checked before "not a brush: pass through" '
      '(Alt + click did nothing in the select mode)', pick < passthru and '(event.alt or gizmo)' in src)

# --- Concept Move family in the Mecha top bar --------------------------------------------------------------------
TOOL = ['CPATH']
real_eff = ts.effective_tool
ts.effective_tool = lambda c: TOOL[0]
st = S.mch_concept
st.path_method = 'EXTEND'
g = [t for t, _c in tb.groups(CTX, 'CPATH')]
bar = tb.items(CTX, W, H, 1.0)
props = {i.prop for i in bar if i.prop}
check('Path Move: METHOD (Extend v, Brush | Whole) and BRUSH (Size, Real Size, Hardness, Taper, Follow Turns, Back '
      'Mask, Shape) in the Mecha top bar', g[:2] == ['Method', 'Brush'] and {
          'path_method', 'path_area', 'radius_px', 'lock_size', 'path_hardness', 'path_taper', 'path_turn',
          'path_back_mask', 'shape', 'keep_density', 'follow_view'} <= props, (g, sorted(props)))
TOOL[0] = 'SMOVE'
props = {i.prop for i in tb.items(CTX, W, H, 1.0) if i.prop}
check('Silhouette Move: no method / area / back mask (always Extend, Whole)', 'path_method' not in props
      and 'path_back_mask' not in props and 'path_hardness' in props)
TOOL[0] = 'CMOVE'
st.falloff = 'CLAY'
props = {i.prop for i in tb.items(CTX, W, H, 1.0) if i.prop}
check('Concept Move: Size, Hardness (Clay), Falloff, Strength, Shape, Mirror X, Generate, Follow View',
      {'radius_px', 'hardness', 'falloff', 'strength', 'shape', 'mirror_x', 'keep_density', 'follow_view'} <= props)
st.lock_size = True
check('... Real Size on: the size in scene units', 'radius_world' in {i.prop for i in tb.items(CTX, W, H, 1.0)})
st.lock_size = False
real_on = sp.on
sp.on = lambda c: True
for tool in ('CMOVE', 'CPATH', 'SMOVE'):
    TOOL[0] = tool
    sp.dirty()
    side = sp.items(CTX, W, H, 1.0)
    rep = [i.prop for i in side if i.data is not None and sp.is_top_bar(i.data, i.prop)]
    check(f'Side panel ({tool}): the top bar\'s settings not repeated, the rest still there', not rep
          and len(side) > 3, rep)
sp.on = real_on
ts.effective_tool = real_eff
ts.is_mecha_workspace = real_ws
summary()
