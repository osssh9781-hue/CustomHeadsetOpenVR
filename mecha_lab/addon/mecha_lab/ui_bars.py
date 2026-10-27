"""0.24.58 The bottom toolbar and the left tool strip drawn by Mecha Lab itself, in the Mecha Menu look.

- Bottom toolbar: one dark rounded bar at the bottom middle, the toolbar tools as icons (the tool in use on blue),
  their key letter small in the corner, the name in a bubble while the mouse is over a button.
- Left tool strip: every tool, grouped by job (tool_state.TOOL_GROUPS), in a dark column at the left edge (right
  of Blender's toolbar); it shrinks / takes a fourth column to fit the viewport height.

Both are drawn with the Mecha Menu painter.  A left click is taken by ``mch.quick_hud_press`` (first in every
Mecha tool keymap and in 3D View / Object Mode), so the buttons work in any tool and a click on a card never falls
through to the tool behind it.  The mouse position for the name bubble comes from ``mch.ui_hover`` (a pass-through
on mouse move).  Preferences: Drawn Toolbar / Tool Strip (off = the 0.12 button toolbar, no strip).
"""
from __future__ import annotations

import bpy
from bpy.props import FloatVectorProperty

from . import tool_state as ts

BAR_BTN = 46.0           # px at size factor 1
BAR_GAP = 6.0
BAR_PAD = 10.0
STRIP_ICON = 38.0
STRIP_GAP = 5.0
STRIP_HEAD = 22.0
STRIP_PAD = 8.0
BAR_ICON = {'SELECT': 'arrow', 'SKIN': 'WRINKLE', 'SHELL': 'SCALES'}


def _pref(name, default=True):
    from .workspace_ui import pref
    return pref(name, default)


def bar_on(context):
    from . import bottom_bar
    return _pref('bottom_toolbar') and _pref('drawn_toolbar', True) and bottom_bar.ui_active(context)


def strip_on(context):
    from . import bottom_bar
    return _pref('tool_strip', True) and bottom_bar.ui_active(context)


def left_inset(context):
    """Region px covered by Blender's own toolbar (T) on the left."""
    area, region = getattr(context, 'area', None), getattr(context, 'region', None)
    tools = next((r for r in area.regions if r.type == 'TOOLS'), None) if area else None
    if tools is None or tools.width <= 1 or region is None:
        return 0.0
    return max(0.0, float(tools.x + tools.width - region.x))


def _icon_for(tid):
    if tid in BAR_ICON:
        alias = BAR_ICON[tid]
        if alias in ts.TOOL_BY_ID:
            return 'png:' + ts.TOOL_BY_ID[alias][3]
        return alias
    t = ts.TOOL_BY_ID.get(tid)
    return 'png:' + t[3] if t else ''


# --- layout --------------------------------------------------------------------------------------------------

def bar_items(context, region_w, region_h, k=1.0):
    from .bottom_bar import BAR_TOOLS, current_bar_tool
    from .mecha_menu import Item
    n = len(BAR_TOOLS)
    b, gap, pad = BAR_BTN * k, BAR_GAP * k, BAR_PAD * k
    avail = max(100.0, region_w - 2 * left_inset(context) - 40 * k)
    w = n * b + (n - 1) * gap + 2 * pad
    if w > avail:                                     # narrow viewport: smaller buttons
        f = avail / w
        b, gap, pad, w = b * f, gap * f, pad * f, avail
    x0, y0 = (region_w - w) / 2.0, 22 * k
    out = [Item('card', x0, y0, w, b + 2 * pad)]
    try:
        active = current_bar_tool(context)
    except (AttributeError, KeyError, TypeError):
        active = ''
    for i, (tid, label, key, _icon, _op, _arg) in enumerate(BAR_TOOLS):
        x = x0 + pad + i * (b + gap)
        out.append(Item('abtn', x, y0 + pad, b, b, label, _icon_for(tid), tid == active, True, ('bar', tid)))
        if key:
            out.append(Item('keycap', x + b - 9 * k, y0 + pad + 2 * k, 8 * k, 10 * k, key))
    return out


def strip_layout(region_h, k, groups):
    """(columns, icon size, gap) so the strip fits ``region_h``."""
    def height(cols, s):
        rows = sum((len(r) + cols - 1) // cols for _n, r in groups)
        return rows * (STRIP_ICON * s + STRIP_GAP * s) + len(groups) * STRIP_HEAD * s + 2 * STRIP_PAD * s
    avail = max(200.0, region_h - 150.0 * k)
    for cols in (3, 4, 5):
        s = min(k, k * avail / height(cols, k))
        if s >= 0.7 * k or cols == 5:
            return cols, s
    return 5, k


def strip_items(context, region_w, region_h, k=1.0):
    from .mecha_menu import Item
    groups = ts.grouped_tools()
    cols, s = strip_layout(region_h, k, groups)
    ic, gap, head, pad = STRIP_ICON * s, STRIP_GAP * s, STRIP_HEAD * s, STRIP_PAD * s
    w = cols * ic + (cols - 1) * gap + 2 * pad
    rows = sum((len(r) + cols - 1) // cols for _n, r in groups)
    h = rows * (ic + gap) + len(groups) * head + 2 * pad
    x0 = left_inset(context) + 12 * k
    top = region_h - 60 * k
    y0 = max(8 * k, top - h)
    out = [Item('card', x0, y0, w, h)]
    from . import bottom_bar
    try:
        active = '' if bottom_bar.in_select(context) else ts.effective_tool(context)
    except (AttributeError, KeyError, TypeError):
        active = ''
    y = y0 + h - pad
    for name, rows_ in groups:
        y -= head
        out.append(Item('striphead', x0 + pad, y, w - 2 * pad, head, name.upper()))
        for j, t in enumerate(rows_):
            c, r = j % cols, j // cols
            out.append(Item('button', x0 + pad + c * (ic + gap), y - (r + 1) * (ic + gap) + gap, ic, ic, t[1],
                            'png:' + t[3], t[0] == active, True, ('tool', t[0])))
        y -= ((len(rows_) + cols - 1) // cols) * (ic + gap)
    return out


def strip_width(context, k=1.0):
    """How much of the left side the strip takes (0 when it is off) - the Quick HUD / key legend go right of it."""
    region = getattr(context, 'region', None)
    if region is None or not strip_on(context):
        return 0.0
    cards = [i for i in strip_items(context, region.width, region.height, k) if i.kind == 'card']
    return cards[0].x + cards[0].w - left_inset(context) + 4 * k if cards else 0.0


def all_items(context):
    region = getattr(context, 'region', None)
    if region is None:
        return []
    from .ui_gpu import ui_factor
    k = ui_factor(context, region)
    out = []
    try:
        if bar_on(context):
            out += bar_items(context, region.width, region.height, k)
        if strip_on(context):
            out += strip_items(context, region.width, region.height, k)
    except (AttributeError, KeyError, TypeError, ReferenceError):
        return []
    return out


def hit(context, x, y):
    """(inside a bar / strip?, the button under the mouse or None)."""
    items = all_items(context)
    if not any(i.kind == 'card' and i.hit(x, y) for i in items):
        return False, None
    it = next((i for i in items if i.kind != 'card' and i.clickable() and i.hit(x, y)), None)
    return True, it


def run(context, item):
    """A button click: switch to that tool (Select / Move, Skin / Shell, a Mecha tool)."""
    kind, tid = item.action[0], item.action[1]
    try:
        bpy.ops.mch.bar_tool(tool=tid)
    except RuntimeError:
        return ''
    t = ts.TOOL_BY_ID.get(tid)
    return t[1] if t else item.label


# --- drawing ---------------------------------------------------------------------------------------------------

_handle = None


def hovered(context, items):
    wm = context.window_manager
    x, y = tuple(getattr(wm, 'mch_ui_hover', (-1.0, -1.0)))
    return next((i for i in items if i.kind != 'card' and i.clickable() and i.hit(x, y)), None)


def _draw():
    try:
        context = bpy.context
        if context.region is None or context.region.type != 'WINDOW':
            return
        from .mecha_menu import _OPEN, draw
        if _OPEN[0]:
            return
        items = all_items(context)
        if items:
            from .ui_gpu import ui_factor
            draw(items, hovered(context, items), ui_factor(context, context.region), context)
    except Exception:          # never break viewport drawing
        pass
    from . import ui_gpu
    ui_gpu.done()


class MCH_OT_ui_hover(bpy.types.Operator):
    """Mouse position for the toolbar / strip name bubble (passes every move on)"""
    bl_idname = 'mch.ui_hover'
    bl_label = 'Mecha UI Hover'
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        try:
            wm = context.window_manager
            if bar_on(context) or strip_on(context):
                x, y = float(event.mouse_region_x), float(event.mouse_region_y)
                items = all_items(context)
                before = hovered(context, items)
                wm.mch_ui_hover = (x, y)
                if hovered(context, items) is not before and context.area:
                    context.area.tag_redraw()
        except (AttributeError, KeyError, TypeError, ReferenceError):
            pass
        return {'PASS_THROUGH'}


CLASSES = (MCH_OT_ui_hover,)
_keymaps = []


def register():
    global _handle
    bpy.types.WindowManager.mch_ui_hover = FloatVectorProperty(size=2, default=(-1.0, -1.0), options={'SKIP_SAVE'})
    for c in CLASSES:
        bpy.utils.register_class(c)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon if wm else None
    if kc is not None:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        _keymaps.append((km, km.keymap_items.new('mch.ui_hover', 'MOUSEMOVE', 'ANY', any=True)))
    if not bpy.app.background and _handle is None:
        _handle = bpy.types.SpaceView3D.draw_handler_add(_draw, (), 'WINDOW', 'POST_PIXEL')


def unregister():
    global _handle
    if _handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_handle, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _handle = None
    for km, kmi in _keymaps:
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass
    _keymaps.clear()
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
    if hasattr(bpy.types.WindowManager, 'mch_ui_hover'):
        del bpy.types.WindowManager.mch_ui_hover
