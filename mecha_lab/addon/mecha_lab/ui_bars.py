"""0.24.58 The viewport UI Mecha Lab draws itself, in the Mecha Menu look.

- Bottom toolbar: one dark rounded bar at the bottom middle, the toolbar tools as icons (the tool in use on blue),
  their key letter small in the corner, the name in a bubble while the mouse is over a button.
- Left tool strip: every tool, grouped by job (tool_state.TOOL_GROUPS), at the left edge (right of Blender's
  toolbar).  0.24.59: icon + name in two columns (Preferences: Tool Strip Names off = icons only, three columns),
  its size in Icon Size (Tool Strip); it shrinks to fit the viewport height.
- 0.24.59 Actions card: Apply Modifiers / the chosen tool on-off / Reset Axis / Origin / Symmetry / Mirror as
  compact rows right of the strip (were round gizmo buttons with loose labels).
- 0.24.59 Top bar (``top_bar``) and side panel (``side_panel``) go through here too: one hit test, one click
  handler, one draw.

A left click is taken by ``mch.quick_hud_press`` (an invisible gizmo over these, then the keymaps), so the buttons
work in any tool and a click on a card never falls through to the tool behind it.  The mouse position for the name
bubbles comes from ``mch.ui_hover`` (a pass-through on mouse move).
"""
from __future__ import annotations

import bpy
from bpy.props import BoolProperty, FloatProperty, FloatVectorProperty

from . import tool_state as ts

BAR_BTN = 46.0           # px at size factor 1
BAR_GAP = 6.0
BAR_PAD = 10.0
STRIP_ICON = 38.0        # icons-only strip
STRIP_GAP = 5.0
STRIP_HEAD = 22.0
STRIP_PAD = 8.0
TILE_W = 72.0            # 0.24.59 a named strip tile, 6 : 4 - the icon fills the top 80 %, the name the bottom 20 %
TILE_H = 48.0
TILE_GAP = 4.0
TILE_HEAD = 17.0
MENU_SEP = 14.0          # 0.24.59 bottom main menu: room between two groups (a thin rule in it)
MENU_MIN_W = 50.0        # narrower tiles than this: each group in three rows instead of two
DOCK_W = 100.0           # 0.24.59 a tile of the actions dock (where the bottom toolbar was): big icon, name under
DOCK_H = 66.0
ACT_W = 196.0            # 0.24.59 actions card
ACT_ROW = 26.0
BAR_ICON = {'SELECT': 'arrow', 'SKIN': 'WRINKLE', 'SHELL': 'SCALES'}


def _pref(name, default=True):
    from .workspace_ui import pref
    return pref(name, default)


def bar_on(context):
    """The drawn bottom toolbar - not with the bottom main menu (it has every tool; the actions dock takes the
    toolbar's place)."""
    from . import bottom_bar
    return (_pref('bottom_toolbar') and _pref('drawn_toolbar', True) and bottom_bar.ui_active(context)
            and not menu_on(context))


def menu_pos():
    """0.24.59 Where the tool tiles go: 'BOTTOM' (the main menu under the bottom toolbar) or 'LEFT' (the strip)."""
    return 'LEFT' if _pref('tool_menu', 'BOTTOM') == 'LEFT' else 'BOTTOM'


def strip_on(context):
    from . import bottom_bar
    return _pref('tool_strip', True) and menu_pos() == 'LEFT' and bottom_bar.ui_active(context)


def menu_on(context):
    from . import bottom_bar
    return _pref('tool_strip', True) and menu_pos() == 'BOTTOM' and bottom_bar.ui_active(context)


def actions_on(context):
    from . import bottom_bar
    return _pref('drawn_toolbar', True) and bottom_bar.ui_active(context)


def left_inset(context):
    """Region px covered by Blender's own toolbar (T) on the left."""
    area, region = getattr(context, 'area', None), getattr(context, 'region', None)
    tools = next((r for r in area.regions if r.type == 'TOOLS'), None) if area else None
    if tools is None or tools.width <= 1 or region is None:
        return 0.0
    return max(0.0, float(tools.x + tools.width - region.x))


def top_inset(context):
    """0.24.59 Region px at the top covered by Blender's header / tool settings rows (with Region Overlap they lie
    over the viewport, see-through) - the top bar goes under them."""
    area, region = getattr(context, 'area', None), getattr(context, 'region', None)
    if area is None or region is None:
        return 0.0
    top = region.y + region.height
    low = top
    for r in area.regions:
        if r.type in {'HEADER', 'TOOL_HEADER'} and r.height > 1 and r.y < top and r.y > region.y + region.height / 2:
            low = min(low, r.y)
    return max(0.0, float(top - low))


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


def strip_layout(region_h, k, groups, named=False, avail=None):
    """(columns, size factor) so the strip fits ``avail`` px of height (default: the viewport less its margins).
    Named tiles keep their size and take more columns first (3 -> 6); icons only shrink a little first."""
    cell, gap, head = (TILE_H, TILE_GAP, TILE_HEAD) if named else (STRIP_ICON, STRIP_GAP, STRIP_HEAD)

    def height(cols, s):
        rows = sum((len(r) + cols - 1) // cols for _n, r in groups)
        return rows * (cell + gap) * s + len(groups) * head * s + 2 * STRIP_PAD * s
    if avail is None:
        avail = region_h - 150.0 * k
    avail = max(200.0, avail)
    choices = (3, 4, 5, 6) if named else (3, 4, 5)
    for cols in choices:
        s = min(k, k * avail / height(cols, k))
        if s >= (0.92 if named else 0.75) * k or cols == choices[-1]:
            return cols, s
    return choices[-1], k


def strip_scale():
    try:
        return max(0.5, float(_pref('strip_scale', 1.0)))
    except (TypeError, ValueError):
        return 1.0


def strip_items(context, region_w, region_h, k=1.0):
    from .mecha_menu import Item
    groups = ts.grouped_tools()
    named = bool(_pref('strip_names', True))
    kk = k * strip_scale()
    x0 = left_inset(context) + 12 * k
    top = region_h - (40 if named else 60) * k
    bottom = 8 * k
    for _pass in range(2):           # a second pass when the bottom toolbar would be under the strip
        cols, s = strip_layout(region_h, kk, groups, named, top - bottom if named else None)
        cw = (TILE_W if named else STRIP_ICON) * s
        chh = (TILE_H if named else STRIP_ICON) * s
        gap = (TILE_GAP if named else STRIP_GAP) * s
        head = (TILE_HEAD if named else STRIP_HEAD) * s
        pad = STRIP_PAD * s
        w = cols * cw + (cols - 1) * gap + 2 * pad
        rows = sum((len(r) + cols - 1) // cols for _n, r in groups)
        h = rows * (chh + gap) + len(groups) * head + 2 * pad
        y0 = max(bottom, top - h)
        clash = False
        if bar_on(context) and _pass == 0:
            bar = bar_items(context, region_w, region_h, k)[0]
            clash = bar.x < x0 + w + 8 * k and y0 < bar.y + bar.h + 8 * k
        if not clash:
            break
        bottom = bar.y + bar.h + 10 * k
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
            out.append(Item('sbtn' if named else 'button', x0 + pad + c * (cw + gap), y - (r + 1) * (chh + gap) + gap,
                            cw, chh, t[1], 'png:' + t[3], t[0] == active, True, ('tool', t[0])))
        y -= ((len(rows_) + cols - 1) // cols) * (chh + gap)
    return out


def strip_width(context, k=1.0):
    """How much of the left side the strip (or 0.24.59 the Layers panel) takes (0 when off) - the Quick HUD / key
    legend go right of it."""
    region = getattr(context, 'region', None)
    if region is not None and not strip_on(context):
        from . import layers_panel
        return layers_panel.taken(context, k)
    if region is None or not strip_on(context):
        return 0.0
    cards = [i for i in strip_items(context, region.width, region.height, k) if i.kind == 'card']
    return cards[0].x + cards[0].w - left_inset(context) + 4 * k if cards else 0.0


def menu_layout(region_w, k, groups, left=0.0):
    """(rows, [columns per group], tile w, tile h, card w, card h) of the bottom main menu: each group's tiles in
    two rows side by side, the tiles as big as the strip's (6 : 4) while they fit the viewport width, three rows
    when they would get narrower than MENU_MIN_W."""
    avail = max(300.0 * k, region_w - 2 * left - 24 * k)
    pad, gap, sep, head = STRIP_PAD * k, TILE_GAP * k, MENU_SEP * k, TILE_HEAD * k
    for rows in (2, 3):
        cols = [(len(r) + rows - 1) // rows for _n, r in groups]
        fixed = 2 * pad + sep * (len(groups) - 1) + gap * (sum(cols) - len(cols))
        cw = min(TILE_W * k, (avail - fixed) / max(1, sum(cols)))
        if cw >= MENU_MIN_W * k or rows == 3:
            break
    ch = cw * TILE_H / TILE_W
    return rows, cols, cw, ch, fixed + cw * sum(cols), 2 * pad + head + rows * ch + (rows - 1) * gap


def menu_items(context, region_w, region_h, k=1.0):
    """0.24.59 The main menu: every tool as a 6 : 4 tile (icon on top, name under it), grouped by job, in one
    band along the bottom of the viewport (the bottom toolbar sits on it)."""
    from .mecha_menu import Item
    groups = ts.grouped_tools()
    kk = k * strip_scale()
    left = left_inset(context)
    rows, cols, cw, ch, w, h = menu_layout(region_w, kk, groups, left)
    pad, gap, sep, head = STRIP_PAD * kk, TILE_GAP * kk, MENU_SEP * kk, TILE_HEAD * kk
    x0 = max(left + 8 * k, (region_w - w) / 2.0)
    y0 = 8 * k
    out = [Item('card', x0, y0, w, h)]
    from . import bottom_bar
    try:
        active = '' if bottom_bar.in_select(context) else ts.effective_tool(context)
    except (AttributeError, KeyError, TypeError):
        active = ''
    from .bottom_bar import BAR_TOOLS
    keys = {tid: key for tid, _l, key, *_r in BAR_TOOLS if key}
    x = x0 + pad
    top = y0 + h - pad
    for g, ((name, tools), n) in enumerate(zip(groups, cols)):
        gw = n * cw + (n - 1) * gap
        if g:
            out.append(Item('vrule', x - sep / 2 - 0.5 * k, y0 + pad + 2 * kk, 1.0 * k, h - 2 * pad - 4 * kk))
        out.append(Item('striphead', x, top - head, gw, head, name.upper()))
        for j, t in enumerate(tools):
            c, r = j % n, j // n
            tx, ty = x + c * (cw + gap), top - head - (r + 1) * ch - r * gap
            out.append(Item('sbtn', tx, ty, cw, ch, t[1], 'png:' + t[3], t[0] == active, True, ('tool', t[0]),
                            'ABOVE'))
            if t[0] in keys:
                out.append(Item('keycap', tx + cw - 10 * kk, ty + ch - 11 * kk, 8 * kk, 10 * kk, keys[t[0]]))
        x += gw + sep
    return out


def bottom_taken(context, k=1.0, region_w=None):
    """0.24.59 Region px from the bottom the main menu takes (0 when the tiles are on the left) - the bottom
    toolbar, key legend, actions card and side panel stay above it."""
    region = getattr(context, 'region', None)
    if not menu_on(context) or (region is None and region_w is None):
        return 0.0
    if region_w is None:
        region_w = region.width
    kk = k * strip_scale()
    h = menu_layout(region_w, kk, ts.grouped_tools(), left_inset(context))[5]
    return 8 * k + h + 8 * k


ACTIONS = (('apply_mods', 'stack', 'Apply Modifiers', ('op', 'mch.apply_modifiers_pick', {})),
           ('reset_axis', 'axes', 'Reset Axis', ('op', 'mch.object_tidy', {'action': 'RESET_AXIS'})),
           ('origin_geo', 'origin', 'Origin to Geometry', ('op', 'mch.object_tidy', {'action': 'ORIGIN_GEOMETRY'})),
           ('origin_cur', 'origin', 'Origin to 3D Cursor', ('op', 'mch.object_tidy', {'action': 'ORIGIN_CURSOR'})),
           ('symmetry', 'X', 'Symmetry', ('op', 'mch.object_tidy', {'action': 'SYMMETRY'})),
           ('mirror', 'png:mirror', 'Mirror', ('op', 'mch.object_tidy', {'action': 'MIRROR'})),
           ('search', 'menu', 'Search Tools (Ctrl+F)', ('op', 'mch.tool_search', {})))   # 0.24.65


def actions_items(context, region_w, region_h, k=1.0):
    """0.24.59 The compact actions card: the chosen tool's on / off row first, then the object actions."""
    from .mecha_menu import Item
    from . import bottom_bar
    w, rh, pad = ACT_W * k, ACT_ROW * k, 6 * k
    rows = []
    tid, t = bottom_bar.chosen_tool(context)
    if t is not None:
        live = bottom_bar.tool_live(context)
        rows.append(('arow', (t[1] + ('  ON' if live else '')), 'png:' + t[3], live, ('op', 'mch.tool_active', {})))
        rows.append(None)                              # a thin rule
    for _key, icon, label, action in ACTIONS:
        if icon == 'png:mirror':
            m = ts.TOOL_BY_ID.get('MIRROR')
            icon = 'png:' + m[3] if m else 'X'
        rows.append(('arow', label, icon, False, action))
    h = sum(rh if r else 7 * k for r in rows) + 2 * pad
    x0 = left_inset(context) + strip_width(context, k) + 12 * k
    top = region_h - 150 * k                         # under the Quick HUD when it shows
    try:
        from . import quick_hud
        its, grip, hud_rows = quick_hud.current(context)
        if its:
            top = (hud_rows[-1][1] if hud_rows else grip[1]) - quick_hud.ROW_H * k / 2 - 18 * k
    except (AttributeError, KeyError, TypeError, ReferenceError, IndexError):
        pass
    y0 = max(top - h, 210 * k + max(0.0, bottom_taken(context, k, region_w) - 80 * k))   # above the key legend
    out = [Item('card', x0, y0, w, h)]
    y = y0 + h - pad
    for r in rows:
        if r is None:
            y -= 7 * k
            out.append(Item('vrule', x0 + 10 * k, y + 3 * k, w - 20 * k, 1.0 * k))
            continue
        kind, label, icon, on, action = r
        y -= rh
        out.append(Item(kind, x0 + pad, y, w - 2 * pad, rh, label, icon, on, True, action))
    return out


_MEMO = {'key': None, 'time': 0.0, 'items': []}
VERSION = [0]
MEMO_TTL = 0.2           # s: the items are rebuilt at most this often unless something changed


def bump():
    """Something the drawn UI shows changed (a click here, undo, a data change): rebuild on the next look."""
    VERSION[0] += 1


def all_items(context):
    """Every drawn card's items (bottom bar, strip, actions, side panel, top bar), memoised briefly - they are
    asked for by the draw, the hover tracker and the click catcher on every mouse move."""
    import time
    region = getattr(context, 'region', None)
    if region is None:
        return []
    from .ui_gpu import ui_factor
    k = ui_factor(context, region)
    try:
        ob = context.active_object
        key = (region.width, region.height, round(k, 4), ts.effective_tool(context), ob.name if ob else '',
               ob.mode if ob else '', VERSION[0])
    except (AttributeError, ReferenceError):
        key = None
    now = time.monotonic()
    if key is not None and key == _MEMO['key'] and now - _MEMO['time'] < MEMO_TTL:
        return _MEMO['items']
    out = _build_all(context, region, k)
    _MEMO.update(key=key, time=now, items=out)
    return out


def dock_items(context, region_w, region_h, k=1.0):
    """0.24.59 With the bottom main menu: the actions as big tiles where the bottom toolbar was (centred, on the
    menu) - Select, the chosen tool on / off, then Apply Modifiers / Reset Axis / Origin / Symmetry / Mirror."""
    from .mecha_menu import Item
    from . import bottom_bar
    kk = k * strip_scale()
    tw, th, gap, pad = DOCK_W * kk, DOCK_H * kk, 6 * kk, 8 * kk
    try:
        sel = bottom_bar.in_select(context)
    except (AttributeError, KeyError, TypeError):
        sel = False
    tiles = [('Select', _icon_for('SELECT'), sel, ('bar', 'SELECT'), 'F')]
    tid, t = bottom_bar.chosen_tool(context)
    if t is not None:
        live = bottom_bar.tool_live(context)
        tiles.append((t[1] + (' ON' if live else ' OFF'), 'png:' + t[3], live, ('op', 'mch.tool_active', {}), ''))
    tiles.append(None)                                 # a thin rule
    for _key, icon, label, action in ACTIONS:
        if icon == 'png:mirror':
            m = ts.TOOL_BY_ID.get('MIRROR')
            icon = 'png:' + m[3] if m else 'X'
        tiles.append((label, icon, False, action, ''))
    n = sum(1 for c in tiles if c)
    rule = 14 * kk
    w = n * tw + (n - 1) * gap + rule * (len(tiles) - n) + 2 * pad
    h = th + 2 * pad
    x0, y0 = max(left_inset(context) + 8 * k, (region_w - w) / 2.0), bottom_taken(context, k, region_w)
    out = [Item('card', x0, y0, w, h)]
    x = x0 + pad
    for c in tiles:
        if c is None:
            out.append(Item('vrule', x + rule / 2 - gap / 2 - 0.5 * k, y0 + pad + 6 * kk, 1.0 * k, th - 12 * kk))
            x += rule
            continue
        label, icon, on, action, key = c
        out.append(Item('sbtn', x, y0 + pad, tw, th, label, icon, on, True, action, 'ABOVE'))
        if key:
            out.append(Item('keycap', x + tw - 11 * kk, y0 + pad + th - 12 * kk, 8 * kk, 10 * kk, key))
        x += tw + gap
    return out


def dock_top(context, k=1.0, region_w=None):
    """Region px from the bottom the main menu + actions dock take (0 when the tiles are on the left)."""
    base = bottom_taken(context, k, region_w)
    if not base or not actions_on(context):
        return base
    return base + (DOCK_H + 16.0) * k * strip_scale() + 8 * k


def _build_all(context, region, k):
    out = []
    try:
        from . import zb_sculpt, zb_ui
        if zb_sculpt.on(context):                     # 0.24.60 Sculpt Mode in MECHA LAB: the ZBrush screen
            return zb_ui.items(context, region.width, region.height, k)
        if zb_sculpt.mecha_sculpt(context):           # ... Blender style: Blender's sculpting, only the corner card
            return zb_ui.corner_items(context, region.width, region.height, k)
    except (AttributeError, KeyError, TypeError, ReferenceError, RuntimeError):
        return out
    try:
        if bar_on(context):
            out += bar_items(context, region.width, region.height, k)
        if strip_on(context):
            out += strip_items(context, region.width, region.height, k)
        if menu_on(context):
            out += menu_items(context, region.width, region.height, k)
        if actions_on(context):
            if menu_on(context):
                out += dock_items(context, region.width, region.height, k)
            else:
                out += actions_items(context, region.width, region.height, k)
        from . import layers_panel, side_panel, top_bar
        if layers_panel.on(context):
            out += layers_panel.items(context, region.width, region.height, k)
        if side_panel.on(context):
            out += side_panel.items(context, region.width, region.height, k)
        if top_bar.on(context):
            out += top_bar.items(context, region.width, region.height, k)
        from . import bottom_bar
        if bottom_bar.ui_active(context):              # 0.24.60 MECHA LAB | ZBRUSH card
            from . import zb_ui
            out += zb_ui.corner_items(context, region.width, region.height, k)
    except (AttributeError, KeyError, TypeError, ReferenceError):
        return out
    return out


def _cards(items):
    """[(card, its items)] - a hit test must only look at the items of the card under the mouse."""
    groups = []
    for it in items:
        if it.kind == 'card':
            groups.append((it, []))
        elif groups:
            groups[-1][1].append(it)
    return groups


def hit(context, x, y):
    """(inside a bar / strip / card / panel?, the clickable item under the mouse or None)."""
    items = all_items(context)
    inside = False
    for card, its in reversed(_cards(items)):          # the last drawn is on top
        if not card.hit(x, y):
            continue
        inside = True
        it = next((i for i in its if i.clickable() and i.hit(x, y)), None)
        if it is not None:
            return True, it
        return True, None
    return inside, None


EDIT = [None, '']        # the (data, prop) the value popup / choice menu edit


def run(context, item):
    """A click on a button: switch tool, set a value, run the operator ... (number bars are dragged by
    ``mch.quick_hud_press`` itself).  Returns a short report."""
    from . import side_panel, ui_values
    a = item.action
    kind = a[0]
    msg = ''
    try:
        if kind in {'bar', 'tool'}:
            bpy.ops.mch.bar_tool(tool=a[1])
            t = ts.TOOL_BY_ID.get(a[1])
            msg = t[1] if t else item.label
        elif kind == 'shape':
            bpy.ops.mch.set_shape(shape=a[1], preset='')
            msg = item.label
        elif kind == 'mode':
            from . import mecha_menu
            mecha_menu.run(context, item)
        elif kind == 'bool':
            ui_values.toggle(item.data, item.prop)
            _undo(item.label, item.data)
        elif kind == 'enum':
            ui_values.set(item.data, item.prop, a[1])
            _undo(item.label, item.data)
        elif kind == 'menu_enum':
            EDIT[:] = [item.data, item.prop]
            bpy.ops.wm.call_menu(name='MCH_MT_ui_choice')
        elif kind == 'op':
            mod, name = a[1].split('.')
            # 0.24.65 like a click on a Blender button: an operator that changes the model gets its undo step
            # (from here, inside the click handler, Blender had dropped it - Ctrl+Z then jumped further back)
            getattr(getattr(bpy.ops, mod), name)('INVOKE_DEFAULT', True, **a[2])
        elif kind == 'menu':
            bpy.ops.wm.call_menu(name=a[1])
        elif kind == 'fold':
            side_panel.toggle_fold(a[1], a[2])
        elif kind == 'minimise':
            wm = context.window_manager
            wm.mch_side_min = not wm.mch_side_min
        elif kind == 'layers_min':
            wm = context.window_manager
            wm.mch_layers_min = not wm.mch_layers_min
    except (RuntimeError, TypeError, ValueError, AttributeError, KeyError, ReferenceError) as ex:
        print('Mecha UI:', a, ex)
        msg = str(ex).splitlines()[0][:120] if str(ex) else ''
    side_panel.dirty()
    return msg


def _undo(what, data=None):
    """An undo step for a change to the model (a live part's value ...); 0.24.65 none for a setting: Ctrl+Z
    undoes what you did, not the settings you chose (undo_keep)."""
    from . import undo_keep
    if undo_keep.is_setting(data):
        return
    try:
        bpy.ops.ed.undo_push(message='Mecha ' + (what or 'setting'))
    except RuntimeError:
        pass


def open_value(context, item):
    """Click (no drag) on a number bar: type the exact value."""
    EDIT[:] = [item.data, item.prop]
    try:
        bpy.ops.wm.call_panel(name='MCH_PT_ui_value', keep_open=False)
    except RuntimeError:
        pass


class MCH_PT_ui_value(bpy.types.Panel):
    """Type the exact value of a number bar"""
    bl_idname = 'MCH_PT_ui_value'
    bl_label = 'Value'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'HEADER'
    bl_ui_units_x = 12

    def draw(self, context):
        data, prop = EDIT
        if data is None:
            return
        try:
            self.layout.prop(data, prop)
        except (TypeError, ReferenceError):
            pass


class MCH_MT_ui_choice(bpy.types.Menu):
    """The choices of a closed list in the side panel / top bar"""
    bl_idname = 'MCH_MT_ui_choice'
    bl_label = 'Choose'

    def draw(self, context):
        data, prop = EDIT
        if data is None:
            return
        try:
            self.layout.props_enum(data, prop)
        except (TypeError, ReferenceError):
            pass


# --- drawing ---------------------------------------------------------------------------------------------------

_handle = None


def hovered(context, items):
    wm = context.window_manager
    x, y = tuple(getattr(wm, 'mch_ui_hover', (-1.0, -1.0)))
    for card, its in reversed(_cards(items)):
        if card.hit(x, y):
            return next((i for i in its if i.clickable() and i.hit(x, y)), None)
    return None


def _draw():
    try:
        context = bpy.context
        if context.region is None or context.region.type != 'WINDOW':
            return
        from .mecha_menu import draw              # 0.24.58 stays on while the Mecha Menu is open (it draws on top)
        items = all_items(context)
        if items:
            from .ui_gpu import ui_factor
            from . import mecha_menu, ui_gpu, zb_sculpt
            orange = zb_sculpt.on(context)            # 0.24.60 the ZBrush screen: orange
            keep = (ui_gpu.ACCENT, mecha_menu.FILL)
            if orange:
                ui_gpu.ACCENT, mecha_menu.FILL = zb_sculpt.ORANGE, zb_sculpt.ORANGE_FILL
            try:
                draw(items, hovered(context, items), ui_factor(context, context.region), context)
            finally:
                ui_gpu.ACCENT, mecha_menu.FILL = keep
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
            x, y = float(event.mouse_region_x), float(event.mouse_region_y)
            from . import zb_sculpt, zb_ui
            if zb_sculpt.on(context) and zb_sculpt.popup_open(context) and zb_ui.popup_leave(context, x, y):
                bump()
                if context.area:
                    context.area.tag_redraw()
            items = all_items(context)
            if items:
                before = hovered(context, items)
                wm.mch_ui_hover = (x, y)
                if hovered(context, items) is not before and context.area:
                    context.area.tag_redraw()
        except (AttributeError, KeyError, TypeError, ReferenceError, ImportError, RuntimeError):
            pass
        return {'PASS_THROUGH'}


class MCH_OT_ui_scroll(bpy.types.Operator):
    """0.24.59 The mouse wheel over the side panel / Layers panel scrolls it (elsewhere it zooms the view)"""
    bl_idname = 'mch.ui_scroll'
    bl_label = 'Mecha Panel Scroll'
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        from . import layers_panel, side_panel, zb_ui
        try:
            x, y = event.mouse_region_x, event.mouse_region_y
            panel = side_panel if side_panel.over(context, x, y) else \
                layers_panel if layers_panel.over(context, x, y) else \
                zb_ui if zb_ui.over_shelf(context, x, y) else None
            if panel is None:
                return {'PASS_THROUGH'}
            from .ui_gpu import ui_factor
            region = context.region
            k = ui_factor(context, region)
            step = 48.0 * k
            panel.scroll_by(context, region.width, region.height, k,
                            step if event.type == 'WHEELDOWNMOUSE' else -step)
            if context.area:
                context.area.tag_redraw()
            return {'FINISHED'}
        except (AttributeError, KeyError, TypeError, ReferenceError):
            return {'PASS_THROUGH'}


CLASSES = (MCH_OT_ui_hover, MCH_OT_ui_scroll, MCH_PT_ui_value, MCH_MT_ui_choice)
_keymaps = []


@bpy.app.handlers.persistent
def _dirty_handler(*_args):
    from . import side_panel
    side_panel.dirty()


def register():
    global _handle
    wmt = bpy.types.WindowManager
    wmt.mch_ui_hover = FloatVectorProperty(size=2, default=(-1.0, -1.0), options={'SKIP_SAVE'})
    wmt.mch_side_scroll = FloatProperty(default=0.0, min=0.0, options={'SKIP_SAVE'})
    wmt.mch_side_min = BoolProperty(default=False, options={'SKIP_SAVE'})
    for c in CLASSES:
        bpy.utils.register_class(c)
    from . import layers_panel, tool_presets, zb_sculpt, zb_ui
    layers_panel.register()
    zb_sculpt.register()                              # 0.24.60 ZBrush-style sculpting
    zb_ui.register()
    tool_presets.register()                           # 0.24.65 Tool Search / Presets
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon if wm else None
    if kc is not None:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        _keymaps.append((km, km.keymap_items.new('mch.ui_hover', 'MOUSEMOVE', 'ANY', any=True)))
        for wheel in ('WHEELUPMOUSE', 'WHEELDOWNMOUSE'):
            _keymaps.append((km, km.keymap_items.new('mch.ui_scroll', wheel, 'PRESS')))
    for hl in (bpy.app.handlers.undo_post, bpy.app.handlers.redo_post, bpy.app.handlers.depsgraph_update_post):
        if _dirty_handler not in hl:
            hl.append(_dirty_handler)
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
    for hl in (bpy.app.handlers.undo_post, bpy.app.handlers.redo_post, bpy.app.handlers.depsgraph_update_post):
        if _dirty_handler in hl:
            hl.remove(_dirty_handler)
    for km, kmi in _keymaps:
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass
    _keymaps.clear()
    from . import layers_panel, tool_presets, zb_sculpt, zb_ui
    for mod in (tool_presets, zb_ui, zb_sculpt, layers_panel):
        try:
            mod.unregister()
        except RuntimeError:
            pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
    for name in ('mch_ui_hover', 'mch_side_scroll', 'mch_side_min'):
        if hasattr(bpy.types.WindowManager, name):
            delattr(bpy.types.WindowManager, name)
