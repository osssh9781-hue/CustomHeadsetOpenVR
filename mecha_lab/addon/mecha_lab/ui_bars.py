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


FOLD_W, FOLD_H = 150.0, 30.0
FOLD = [None]            # None = as the preference says; True / False = set here (no preferences: tests, a script)


def menu_folded():
    """0.24.207 (user: "아래 있는 이거는 이제 기본으로 접어 두자"): is the bottom tool menu folded to its tab?"""
    if FOLD[0] is not None:
        return bool(FOLD[0])
    return bool(_pref('menu_folded', False))


def set_menu_folded(value):
    from .workspace_ui import prefs
    p = prefs()
    if p is not None and hasattr(p, 'menu_folded'):
        FOLD[0] = None
        p.menu_folded = bool(value)
    else:
        FOLD[0] = bool(value)
    bump()


class MCH_OT_menu_fold(bpy.types.Operator):
    """Fold the bottom tool menu to a small tab / open it again (the Tool Wheel - V or Alt + right click - has every tool too)"""
    bl_idname = 'mch.menu_fold'
    bl_label = 'Fold Tool Menu'
    bl_options = {'INTERNAL'}

    def execute(self, context):
        set_menu_folded(not menu_folded())
        if context.area is not None:
            context.area.tag_redraw()
        return {'FINISHED'}


def menu_items(context, region_w, region_h, k=1.0):
    """0.24.59 The main menu: every tool as a 6 : 4 tile (icon on top, name under it), grouped by job, in one
    band along the bottom of the viewport (the bottom toolbar sits on it)."""
    from .mecha_menu import Item
    groups = ts.grouped_tools()
    kk = k * strip_scale()
    left = left_inset(context)
    if menu_folded():                 # 0.24.207 folded: one small tab at the bottom (a click opens the menu)
        w, h = FOLD_W * kk, FOLD_H * kk
        x0, y0 = max(left + 8 * k, (region_w - w) / 2.0), 8 * k
        if _fold_in_dock(context):     # 0.24.227 its open button is in the dock's Options: nothing here
            return []
        return [Item('card', x0, y0, w, h),
                Item('tbtn', x0 + 3 * kk, y0 + 3 * kk, w - 6 * kk, h - 6 * kk, 'TOOLS  (open)', '', False, True,
                     ('op', 'mch.menu_fold', {}))]
    rows, cols, cw, ch, w, h = menu_layout(region_w, kk, groups, left)
    pad, gap, sep, head = STRIP_PAD * kk, TILE_GAP * kk, MENU_SEP * kk, TILE_HEAD * kk
    x0 = max(left + 8 * k, (region_w - w) / 2.0)
    y0 = 8 * k
    out = [Item('card', x0, y0, w, h)]
    fw = 46 * kk                      # (its fold button: the card's top right corner - or the view's right edge
    fx = min(x0 + w, region_w - 8 * k) - fw - 4 * kk      #  when the card is wider than the view)
    fold = Item('tbtn', fx, y0 + h - head - 1 * kk, fw, head, 'Fold', '', False, True, ('op', 'mch.menu_fold', {}))
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
    out.append(fold)                  # (last: drawn over a heading it may sit on)
    return out


def _fold_in_dock(context):
    """0.24.227 Is the tool menu's open button in the dock's Options (the dock with Options is shown)?"""
    try:
        from . import bottom_row
        return bottom_row.on(context)
    except (ImportError, AttributeError, KeyError, TypeError, ReferenceError):
        return False


def bottom_taken(context, k=1.0, region_w=None):
    """0.24.59 Region px from the bottom the main menu takes (0 when the tiles are on the left) - the bottom
    toolbar, key legend, actions card and side panel stay above it."""
    region = getattr(context, 'region', None)
    if not menu_on(context) or (region is None and region_w is None):
        return 0.0
    if region_w is None:
        region_w = region.width
    kk = k * strip_scale()
    if menu_folded():
        if _fold_in_dock(context):            # (its open button is in the dock's Options: no row of its own)
            return 8 * k
        return 8 * k + FOLD_H * kk + 8 * k
    h = menu_layout(region_w, kk, ts.grouped_tools(), left_inset(context))[5]
    return 8 * k + h + 8 * k


ACTIONS = (('apply_mods', 'stack', 'Apply Modifiers', ('op', 'mch.apply_modifiers_pick', {})),
           ('reset_axis', 'axes', 'Reset Axis', ('op', 'mch.object_tidy', {'action': 'RESET_AXIS'})),
           ('origin_geo', 'origin', 'Origin to Geometry', ('op', 'mch.object_tidy', {'action': 'ORIGIN_GEOMETRY'})),
           ('origin_cur', 'origin', 'Origin to 3D Cursor', ('op', 'mch.object_tidy', {'action': 'ORIGIN_CURSOR'})),
           ('symmetry', 'X', 'Symmetry', ('op', 'mch.object_tidy', {'action': 'SYMMETRY'})),
           ('mirror', 'png:mirror', 'Mirror', ('op', 'mch.object_tidy', {'action': 'MIRROR'})),
           ('render', 'camera', 'Quick Render', ('op', 'mch.quick_render', {})),        # 0.24.133 Cycles, fast
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
        from . import name_fix
        ob = context.active_object
        key = (region.width, region.height, round(k, 4), ts.effective_tool(context), name_fix.safe_name(ob) if ob else '',
               ob.mode if ob else '', VERSION[0])
    except (AttributeError, ReferenceError, ImportError):
        key = None
    now = time.monotonic()
    if key is not None and key == _MEMO['key'] and now - _MEMO['time'] < MEMO_TTL:
        return _MEMO['items']
    try:
        out = _build_all(context, region, k)
    except UnicodeDecodeError as ex:
        # 0.24.129 (user: "아머 플레이트 하는데 계속 꺼지냐") a data-block name that is not UTF-8 (a Korean Windows file):
        # repair the names once and build again; if that fails too, an empty UI beats a dead tool
        from . import name_fix
        if not name_fix.on_error(ex):
            return []
        try:
            out = _build_all(context, region, k)
        except UnicodeDecodeError:
            return []
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
    # 0.24.226 (user: "옵션은 여기다가 그냥 넣어 줘"): the top bar's Options (Auto Apply, Ortho, 한글) at the dock's right end
    opts, ow, goz, gws, goz_groups = [], 0.0, [], [], []
    try:
        from . import top_bar
        if top_bar.on(context) and top_bar.sections_wanted():
            opts = top_bar.option_cells(context)
            # 0.24.227 (user: "툴 오픈은 여기 옵션 쪽에다 놔 줘"): the tool menu's open / fold button, lit while open
            opts.append(dict(kind='seg', label='Tools', icon='', on=not menu_folded(), action=('op', 'mch.menu_fold', {}),
                             data=None, prop='', width=None))
            ows = [top_bar._width(c, k) for c in opts]
            ow = (rule + sum(ows) + top_bar.GAP * k * (len(ows) - 1)) if opts else 0.0
            # 0.24.229 (user: "이거 고즈 버튼 여기로 옮겨 줘"): GoZ Send / Import after Options (off the corner card)
            goz = [dict(kind='seg', label=lb, icon='', on=False, action=('op', op_, {}), data=None, prop='', width=None)
                   for lb, op_ in (('Send', 'mch.goz_send'), ('Import', 'mch.goz_import'))]
            gws = [top_bar._width(c, k) for c in goz]
            ow += rule + sum(gws) + top_bar.GAP * k * (len(gws) - 1)
            # 0.24.234 (user: "토글 버튼으로 전체 메쉬에 베벨 노말 … 중앙 메뉴에, 두께는 슬라이더로" / "선택한 거 베벨 노말
            # 지우는 것도"): Bevel Normal on / off, its Radius, Remove from the selected
            sc = context.scene
            if hasattr(sc, 'mch_bevel_normal'):
                bev = [dict(kind='seg', label='Bevel Normal', icon='', on=bool(sc.mch_bevel_normal), action=('bool',),
                            data=sc, prop='mch_bevel_normal', width=None),
                       dict(kind='mini', label='Radius', icon='', on=False, action=('number',), data=sc,
                            prop='mch_bevel_normal_radius', width=150),
                       dict(kind='seg', label='Remove Selected', icon='', on=False,
                            action=('op', 'mch.bevel_normal_remove', {}), data=None, prop='', width=None)]
                bws = [top_bar._width(c, k) for c in bev]
                ow += rule + sum(bws) + top_bar.GAP * k * (len(bws) - 1)
                goz_groups = [('GOZ', goz, gws), ('BEVEL', bev, bws)]
            else:
                goz_groups = [('GOZ', goz, gws)]
    except (ImportError, AttributeError, KeyError, TypeError, ReferenceError):
        opts, ow, goz, gws, goz_groups = [], 0.0, [], [], []
    w += ow
    # 0.24.234 too wide for the view (Options, GoZ, Bevel at its end): the big tiles narrower, to fit
    room_w = region_w - 2 * (left_inset(context) + 10 * k)      # (centred: as much room on both sides)
    if w > room_w and n:
        cut = min((w - room_w) / n, tw * 0.35)
        tw -= cut
        w -= cut * n
    h = th + 2 * pad
    x0, y0 = max(left_inset(context) + 8 * k, (region_w - w) / 2.0), bottom_taken(context, k, region_w)
    y0 += _row_h(context, k, region_w)               # 0.24.226 above the row of boxes
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
    if opts:
        x -= gap
        out.append(Item('vrule', x + rule / 2 - 0.5 * k, y0 + pad + 6 * kk, 1.0 * k, th - 12 * kk))
        x += rule
        row_h, title_h = top_bar.ROW * k, top_bar.TITLE_H * k
        base = y0 + pad + max(0.0, (th - row_h - title_h) / 2.0)
        out.append(Item('glabel', x, base + row_h, 120 * k, title_h, 'OPTIONS', 'title'))
        for c, cw in zip(opts, ows):
            out.append(Item(c['kind'], x, base, cw, row_h, c['label'], c['icon'], c['on'], True, c['action'], c['data'],
                            c['prop']))
            x += cw + top_bar.GAP * k
        for gname, gcells, gw_ in goz_groups:        # GOZ, BEVEL (0.24.234)
            if not gcells:
                continue
            x -= top_bar.GAP * k
            out.append(Item('vrule', x + rule / 2 - 0.5 * k, y0 + pad + 6 * kk, 1.0 * k, th - 12 * kk))
            x += rule
            out.append(Item('glabel', x, base + row_h, 120 * k, title_h, gname, 'title'))
            for c, cw in zip(gcells, gw_):
                out.append(Item(c['kind'], x, base, cw, row_h, c['label'], c['icon'], c['on'], True, c['action'],
                                c['data'], c['prop']))
                x += cw + top_bar.GAP * k
    return out


def dock_top(context, k=1.0, region_w=None):
    """Region px from the bottom the main menu + actions dock take (0 when the tiles are on the left)."""
    base = bottom_taken(context, k, region_w)
    if not base or not actions_on(context):
        return base
    return base + _row_h(context, k, region_w) + (DOCK_H + 16.0) * k * strip_scale() + 8 * k


def panel_floor(context, k, region_w, x_left):
    """0.24.226 How low a panel at the view's right (from ``x_left``) may reach: down to the row of boxes when the
    dock (centred above the row) ends left of it - else above the dock as before."""
    top = dock_top(context, k, region_w)
    rh = _row_h(context, k, region_w)
    if rh <= 0:
        return top
    try:
        region = getattr(context, 'region', None)
        d = dock_items(context, region_w, region.height if region is not None else 1000, k)[0]
        if d.x + d.w + 8 * k <= x_left:
            return bottom_taken(context, k, region_w) + rh
    except (AttributeError, IndexError, KeyError, TypeError, ReferenceError):
        pass
    return top


def _row_h(context, k, region_w=None):
    """0.24.226 the height of the row of boxes under the dock (0 when it is not shown)."""
    try:
        from . import bottom_row
        region = getattr(context, 'region', None)
        if region_w is None:
            if region is None:
                return 0.0
            region_w = region.width
        return bottom_row.height(context, region_w, k)
    except (ImportError, AttributeError, KeyError, TypeError, ReferenceError):
        return 0.0


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
        from . import bottom_row                       # 0.24.226 the tool's box + the action boxes, under the dock
        if bottom_row.on(context):
            out += bottom_row.items(context, region.width, region.height, k)
        elif top_bar.on(context):
            out += top_bar.items(context, region.width, region.height, k, part='BOTTOM')
        from . import bottom_bar
        if bottom_bar.ui_active(context):              # 0.24.60 MECHA LAB | ZBRUSH card
            from . import zb_ui
            out += zb_ui.corner_items(context, region.width, region.height, k)
        from . import float_card                       # 0.24.223 a picker card, on top of everything
        if float_card.is_open():
            out += float_card.items(context, region.width, region.height, k)
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


_DRAWN = {}             # region -> (width, height, time, items): what that region shows now (its last draw)
DRAWN_KEEP = 30.0       # s: a click goes to what is on the screen - the last draw of its region - this long


def drawn_items(context):
    """0.24.95 (user: "지금 hdri 고를 때 하나 밑에 칸으로 밀려서 선택돼") the items as the region last DREW them: a
    click hits what the eye sees, even when the layout moved since (a line came or went - "making previews ...", a
    page, a scroll) and the screen is not drawn again yet; none drawn (or the region resized): built now."""
    region = getattr(context, 'region', None)
    try:
        d = _DRAWN.get(region.as_pointer()) if region is not None else None
    except (AttributeError, ReferenceError):
        d = None
    import time
    if d and d[0] == region.width and d[1] == region.height and time.monotonic() - d[2] < DRAWN_KEEP:
        return d[3]
    return all_items(context)


def hit(context, x, y):
    """(inside a bar / strip / card / panel?, the clickable item under the mouse or None) - on what the region shows
    (its last draw)."""
    items = drawn_items(context)
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
    from . import float_card
    if kind == 'float_close':
        float_card.close()
        return ''
    picked = float_card.is_open() and float_card.holds(context, item)   # 0.24.223 a pick closes the picker card
    from . import mecha_mask                         # 0.24.200 Paint Mask: any other button ends it first (back to
    if mecha_mask.ON[0] and not (kind in {'number', 'bool', 'enum'}              # Object Mode), then does its job
                                 or (kind == 'op' and a[1] == 'mch.mecha_mask')):
        mecha_mask.end(context)
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
            EDIT[:] = [item.ref, item.prop]
            open_menu('MCH_MT_ui_choice')
        elif kind == 'op':
            mod, name = a[1].split('.')
            # 0.24.65 like a click on a Blender button: an operator that changes the model gets its undo step
            # (from here, inside the click handler, Blender had dropped it - Ctrl+Z then jumped further back)
            getattr(getattr(bpy.ops, mod), name)('INVOKE_DEFAULT', True, **a[2])
        elif kind == 'mop':                       # 0.24.226 an action button (the right-click popup's): as there
            mod, name = a[1].split('.')
            getattr(getattr(bpy.ops, mod), name)('INVOKE_DEFAULT' if a[3] else 'EXEC_DEFAULT', True, **a[2])
        elif kind == 'menu':
            open_menu(a[1])
        elif kind == 'fold':
            side_panel.toggle_fold(a[1], a[2])
        elif kind == 'usage_help':                # 0.24.235 a section's "?": its usage card
            from . import key_legend
            key_legend.show_feature(context, a[1])
        elif kind == 'minimise':
            wm = context.window_manager
            wm.mch_side_min = not wm.mch_side_min
        elif kind == 'layers_min':
            wm = context.window_manager
            wm.mch_layers_min = not wm.mch_layers_min
        elif kind == 'page':                      # 0.24.95 side panel: the tool's settings | Material
            bpy.ops.mch.side_page(page=a[1])
        elif kind == 'color':                     # 0.24.95 a colour swatch: the colour picker
            open_value(context, item)
    except (RuntimeError, TypeError, ValueError, AttributeError, KeyError, ReferenceError) as ex:
        print('Mecha UI:', a, ex)
        msg = str(ex).splitlines()[0][:120] if str(ex) else ''
    if picked and kind not in {'fold', 'number'}:
        float_card.close()
    side_panel.dirty()
    return msg


def _undo(what, data=None):
    """An undo step for a change to the model (a live part's value ...); 0.24.65 none for a setting: Ctrl+Z
    undoes what you did, not the settings you chose (undo_keep)."""
    from . import undo_keep
    if undo_keep.is_setting(data):
        return
    from . import undo_keep
    undo_keep.push('Mecha ' + (what or 'setting'))


def open_value(context, item):
    """Click (no drag) on a number bar: type the exact value."""
    EDIT[:] = [item.ref, item.prop]
    if bpy.app.background or getattr(context, 'window', None) is None:    # (no real window: call_panel crashes)
        return
    try:
        from . import live_ref
        data = live_ref.resolve(item.ref)
        rna = data.bl_rna.properties.get(item.prop) if data is not None else None
        if rna is not None and rna.subtype in {'COLOR', 'COLOR_GAMMA'}:
            bpy.ops.mch.ui_colour('INVOKE_DEFAULT')    # 0.24.223 the colour picker: a dialog that stays (OK closes)
            return
        bpy.ops.wm.call_panel(name='MCH_PT_ui_value', keep_open=False)
    except (RuntimeError, AttributeError, ReferenceError):
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
        from . import live_ref
        data = live_ref.resolve(data)          # (0.24.132 a Ref: looked up fresh)
        if data is None:
            return
        try:
            rna = data.bl_rna.properties.get(prop)
            if rna is not None and rna.subtype in {'COLOR', 'COLOR_GAMMA'}:     # 0.24.95 a swatch: the picker
                self.layout.label(text=rna.name)
                from . import color_pick                # (the wheel, Hue / Saturation / Value, Pick - the eyedropper)
                color_pick.draw(self.layout, data, prop)
                return
            self.layout.activate_init = True       # 0.24.223 the number is ready to type at once
            self.layout.prop(data, prop)
        except (TypeError, ReferenceError):
            pass


class MCH_OT_ui_colour(bpy.types.Operator):
    """0.24.223 Pick a colour: the wheel, Hue / Saturation / Value and the eyedropper - the window stays open when
    the mouse leaves it (OK closes it)"""
    bl_idname = 'mch.ui_colour'
    bl_label = 'Colour'
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        data, prop = EDIT
        from . import live_ref, color_pick
        data = live_ref.resolve(data)
        if data is None:
            return
        try:
            rna = data.bl_rna.properties.get(prop)
            self.layout.label(text=rna.name if rna is not None else 'Colour')
            color_pick.draw(self.layout, data, prop)
        except (TypeError, ReferenceError, AttributeError):
            pass

    def execute(self, context):
        bump()
        return {'FINISHED'}


class MCH_OT_toggle_language(bpy.types.Operator):
    """0.24.225 한글 / English: switch the language of Mecha Lab's own screen (the same switch as Preferences > 한글)"""
    bl_idname = 'mch.toggle_language'
    bl_label = '한글 / English'
    bl_options = {'INTERNAL'}

    def execute(self, context):
        from . import i18n, workspace_ui
        p = workspace_ui.prefs()
        if p is not None and hasattr(p, 'korean'):
            p.korean = not p.korean                    # (its update lays everything out again)
            try:
                context.preferences.is_dirty = True    # kept with the preferences
            except (AttributeError, TypeError):
                pass
        else:                                          # (no preferences - tests: for this run only)
            i18n.force('EN' if i18n.lang() == 'KO' else 'KO')
            from . import side_panel
            side_panel.dirty()
        bump()
        return {'FINISHED'}


class MCH_OT_side_page(bpy.types.Operator):
    """Show the tool's settings, the Mech Shader, the Creature Shader, the decals, the HDRI or the random base shapes
    in the Mecha Lab side panel"""
    bl_idname = 'mch.side_page'
    bl_label = 'Side Panel Page'
    bl_options = {'INTERNAL'}
    page: bpy.props.EnumProperty(items=[('TOOL', 'Tool', 'The tool\'s settings'),
                                        ('MATERIAL', 'Mech', 'The Mech Shader'),
                                        ('CREATURE', 'Creature', 'The Creature Shader (skins, parts, eyes)'),
                                        ('DECALS', 'Decals', 'Decals: place them, their look and damage'),
                                        ('HDRI', 'HDRI', 'The scene\'s HDRI lighting'),
                                        ('SHAPES', 'Shapes', 'Random base shapes: Polygon, Curved, variations')],
                                 default='MATERIAL')

    def execute(self, context):
        from . import side_panel
        wm = context.window_manager
        if wm.mch_side_page != self.page:
            wm.mch_side_scroll = 0.0
        wm.mch_side_page = self.page
        wm.mch_side_min = False
        side_panel.dirty()
        for w in wm.windows:
            for a in w.screen.areas:
                if a.type == 'VIEW_3D':
                    a.tag_redraw()
        if self.page != 'TOOL' and getattr(context, 'area', None) is not None and not side_panel.on(context):
            from .workspace_ui import pref
            why = ('the sidebar (N) is open - it has the same (Mecha Lab tab, Mech Shader)'
                   if side_panel.sidebar_open(context) else
                   'the side panel is off (Preferences, Side Panel) - the sidebar (N) has it'
                   if not pref('side_panel', True) else 'the sidebar (N) has it (Mecha Lab tab, Mech Shader)')
            self.report({'INFO'}, self.page.title() + ': ' + why)
        return {'FINISHED'}


class MCH_MT_ui_choice(bpy.types.Menu):
    """The choices of a closed list in the side panel / top bar"""
    bl_idname = 'MCH_MT_ui_choice'
    bl_label = 'Choose'

    def draw(self, context):
        data, prop = EDIT
        from . import live_ref
        data = live_ref.resolve(data)          # (0.24.132 a Ref: looked up fresh)
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
        try:                                      # (0.24.95 what is drawn: what a click hits - ``drawn_items``)
            import time
            r = context.region
            _DRAWN[r.as_pointer()] = (r.width, r.height, time.monotonic(), items)
        except (AttributeError, ReferenceError):
            pass
        if items:
            from .ui_gpu import ui_factor
            from . import mecha_menu, ui_gpu, zb_sculpt
            orange = zb_sculpt.on(context)            # 0.24.60 the ZBrush screen: orange
            keep = (ui_gpu.ACCENT, mecha_menu.FILL)
            if orange:
                from . import paint_lab
                if paint_lab.flag(context):           # 0.24.93 the Paint Lab screen: cyan
                    ui_gpu.ACCENT, mecha_menu.FILL = paint_lab.ACCENT, paint_lab.ACCENT_FILL
                else:
                    ui_gpu.ACCENT, mecha_menu.FILL = zb_sculpt.ORANGE, zb_sculpt.ORANGE_FILL
            try:
                draw(items, hovered(context, items), ui_factor(context, context.region), context)
            finally:
                ui_gpu.ACCENT, mecha_menu.FILL = keep
        from . import toast                       # 0.24.82 short messages above the bottom toolbar
        from .ui_gpu import ui_factor as _uf
        k = _uf(context, context.region)
        toast.draw(context, context.region.width, context.region.height, k, bottom_taken(context, k, context.region.width))
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
        from . import layers_panel, side_panel, zb_ui, float_card
        try:
            x, y = event.mouse_region_x, event.mouse_region_y
            panel = float_card if float_card.over(context, x, y) else \
                side_panel if side_panel.over(context, x, y) else \
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


def open_menu(name):
    """0.24.212 a list opened from a drawn cell.  The cell is pressed with the button still DOWN: a Blender menu
    opened then is its hold-and-drag kind - it went when the mouse moved off it and only stayed while the button
    was held (user: "마우스 대면 갑자기 사라졌다가 꾹 누르고 있어야 나타나는").  So the menu opens when the button comes
    UP: a plain click, the list stays until a choice is clicked."""
    if bpy.app.background:
        bpy.ops.wm.call_menu(name=name)
        return
    try:
        bpy.ops.mch.ui_menu_release('INVOKE_DEFAULT', name=name)
    except RuntimeError:
        bpy.ops.wm.call_menu(name=name)


def _menu_later(context, name, delay=0.06):
    """The menu a moment later, from a timer: outside the click's own event handling (opened inside it, Blender
    closed the menu again with that same click)."""
    win, area, region = context.window, context.area, context.region

    def go():
        try:
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.wm.call_menu('INVOKE_DEFAULT', name=name)
        except (RuntimeError, TypeError, ReferenceError, AttributeError) as ex:
            print('Mecha Lab list:', ex)
        return None
    bpy.app.timers.register(go, first_interval=delay)


class MCH_OT_ui_menu_release(bpy.types.Operator):
    """Opens a list of the drawn UI once the mouse button is released"""
    bl_idname = 'mch.ui_menu_release'
    bl_label = 'Mecha List'
    bl_options = {'INTERNAL'}

    name: bpy.props.StringProperty()

    def invoke(self, context, event):
        if event.type != 'LEFTMOUSE' or event.value == 'RELEASE':    # (no button down: at once)
            _menu_later(context, self.name)
            return {'FINISHED'}
        self._timer = context.window_manager.event_timer_add(0.05, window=context.window)
        self._t0 = __import__('time').perf_counter()
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        up = event.type == 'LEFTMOUSE' and event.value == 'RELEASE'
        late = __import__('time').perf_counter() - self._t0 > 1.5     # (the release was missed: open anyway)
        if up or late or event.type in {'ESC', 'RIGHTMOUSE'}:
            context.window_manager.event_timer_remove(self._timer)
            if event.type not in {'ESC', 'RIGHTMOUSE'}:
                _menu_later(context, self.name)
            return {'FINISHED'}
        return {'RUNNING_MODAL'}


CLASSES = (MCH_OT_ui_hover, MCH_OT_ui_scroll, MCH_PT_ui_value, MCH_OT_ui_colour, MCH_OT_toggle_language, MCH_MT_ui_choice, MCH_OT_side_page, MCH_OT_menu_fold,
           MCH_OT_ui_menu_release)
_keymaps = []


@bpy.app.handlers.persistent
def _dirty_handler(*_args):
    from . import side_panel
    side_panel.dirty()


def release_refs():
    """0.24.132 Drop every cached UI item / panel tree / edit target NOW - called right before undo, redo and a file
    load, while the data they point at is still alive, and after them.  The items hold live_ref.Refs (names), not
    structs, since 0.24.132; this makes doubly sure nothing cached outlives the data it was built from."""
    _MEMO.update(key=None, time=0.0, items=[])
    EDIT[:] = [None, '']
    try:
        from . import float_card
        float_card.CARD.clear()
    except (ImportError, AttributeError):
        pass
    try:
        from . import side_panel
        side_panel._CACHE.update(key=None, time=0.0, trees=(None, None))
    except (ImportError, AttributeError):
        pass
    VERSION[0] += 1


@bpy.app.handlers.persistent
def _release_handler(*_args):
    try:
        release_refs()
    except Exception as ex:          # noqa: BLE001 (a handler must never raise)
        print('[Mecha Lab] release_refs:', repr(ex))


def register():
    global _handle
    wmt = bpy.types.WindowManager
    wmt.mch_ui_hover = FloatVectorProperty(size=2, default=(-1.0, -1.0), options={'SKIP_SAVE'})
    wmt.mch_side_scroll = FloatProperty(default=0.0, min=0.0, options={'SKIP_SAVE'})
    wmt.mch_side_min = BoolProperty(default=False, options={'SKIP_SAVE'})
    wmt.mch_side_page = bpy.props.EnumProperty(items=[('TOOL', 'Tool', ''), ('MATERIAL', 'Mech', ''),
                                                      ('CREATURE', 'Creature', ''), ('DECALS', 'Decals', ''),
                                                      ('HDRI', 'HDRI', ''), ('SHAPES', 'Shapes', '')],
                                                default='TOOL', options={'SKIP_SAVE'})
    for c in CLASSES:
        bpy.utils.register_class(c)
    from . import tool_header_icon
    tool_header_icon.register()                       # 0.24.227 no tool icon in Blender's tool settings row
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
    for hl in (bpy.app.handlers.undo_pre, bpy.app.handlers.redo_pre, bpy.app.handlers.load_pre,
               bpy.app.handlers.undo_post, bpy.app.handlers.redo_post, bpy.app.handlers.load_post):
        if _release_handler not in hl:
            hl.append(_release_handler)
    if not bpy.app.background and _handle is None:
        _handle = bpy.types.SpaceView3D.draw_handler_add(_draw, (), 'WINDOW', 'POST_PIXEL')


def unregister():
    try:
        from . import tool_header_icon
        tool_header_icon.unregister()
    except (ImportError, AttributeError):
        pass
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
    for hl in (bpy.app.handlers.undo_pre, bpy.app.handlers.redo_pre, bpy.app.handlers.load_pre,
               bpy.app.handlers.undo_post, bpy.app.handlers.redo_post, bpy.app.handlers.load_post):
        while _release_handler in hl:
            hl.remove(_release_handler)
    release_refs()
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
    for name in ('mch_ui_hover', 'mch_side_scroll', 'mch_side_min', 'mch_side_page'):
        if hasattr(bpy.types.WindowManager, name):
            delattr(bpy.types.WindowManager, name)
