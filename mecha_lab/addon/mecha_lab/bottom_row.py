"""0.24.226 The row of boxes above the folded tool menu (user: "맨 왼쪽은 변동 메뉴", "우클릭 팝업 메뉴를 잘 정리해서
박스로", "이 정도 크기로 잘라서 이렇게 배치"; the bar with Select goes above it): the tool's own box at the left (what
changes from tool to tool - the top bar's Depth / Surface / own sections), then what the right-click popup had, cut into
boxes: Settings + Actions + Shading | Resolution + Symmetry | Group + Repeat + Visibility (+ Live).
"""
import time

from . import tool_state as ts

BTN_W, BTN_H = 50.0, 46.0
TITLE_H = 19.0
PAD = 14.0
GAP = 8.0                 # between two boxes
SEC_GAP = 20.0            # between two sections in a box
SET_W = 190.0
CHUNKS = ((0, 2), (2, 4), (4, None))       # mecha_menu.ACTIONS sections per box
_MEMO = {'key': None, 'time': 0.0, 'value': ([], 0.0)}
TTL = 0.15


def on(context):
    from . import top_bar, ui_bars
    try:
        return (top_bar.on(context) and top_bar.sections_wanted() and ui_bars.menu_on(context)
                and ui_bars.actions_on(context))
    except (AttributeError, KeyError, TypeError, ReferenceError):
        return False


def _settings(context, k):
    """The tool's quick settings (the popup's sliders): (width, height, items at 0, 0 going down) or None."""
    from .mecha_menu import Item
    from . import quick_hud
    try:
        its = quick_hud.items(context)
    except (AttributeError, KeyError, TypeError, ReferenceError):
        its = []
    if not its:
        return None
    w = SET_W * k
    out = [Item('glabel', 0, -TITLE_H * k, w, TITLE_H * k, 'SETTINGS', 'title')]
    y = -TITLE_H * k
    for data, prop in its[:4]:
        rna = data.bl_rna.properties[prop]
        y -= 34 * k
        if rna.type in {'INT', 'FLOAT'}:
            out.append(Item('mini', 0, y, w, 30 * k, rna.name or prop, '', False, True, ('number',), data, prop))
        elif rna.type == 'BOOLEAN':
            out.append(Item('seg', 0, y, w, 30 * k, rna.name or prop, '', bool(getattr(data, prop)), True, ('bool',),
                            data, prop))
        else:
            out.append(Item('drop', 0, y, w, 30 * k, '', '', False, True, ('menu_enum',), data, prop))
    return w, -y, out


def _section(context, sec, buttons, k):
    from .mecha_menu import Item
    from . import mecha_menu as mm, res_panel
    ob = context.active_object
    active = ts.effective_tool(context)
    per = max(1, (len(buttons) + 2) // 3)
    w = max(per * BTN_W * k, 64 * k)
    out = [Item('glabel', 0, -TITLE_H * k, w, TITLE_H * k, sec.upper(), 'title')]
    if sec == 'Resolution':                      # 0.24.283 the Settings switch beside the title
        sw = 92 * k
        out.append(Item('seg', w - sw - 3 * k, -TITLE_H * k - 2 * k, sw, TITLE_H * k + 4 * k, 'Settings', '',
                        res_panel.settings_on(), True, ('resset',)))
    rows = 0
    for i, (label, icon, op, props, needs, closes) in enumerate(buttons):
        c, r = i % per, i // per
        rows = max(rows, r + 1)
        try:
            props, label, on_ = mm._dynamic(context, ob, op, props, label, False)
            ok = mm._needs_ok(context, needs)
        except (AttributeError, KeyError, TypeError, ReferenceError):
            on_, ok = False, True
        if sec == 'Symmetry' and 'axis' in props and ob is not None and ob.type == 'MESH':
            try:
                from . import actions_menu
                m = actions_menu.mirror_mod(ob)
                on_ = on_ or bool(m and m.use_axis[props['axis']])
            except (AttributeError, KeyError, TypeError, ReferenceError):
                pass
        if op.startswith('tool:'):
            action, on_ = ('tool', op[5:]), active == op[5:]
        elif sec == 'Resolution' and label in res_panel.KEYS:
            # 0.24.283 runs at once; with the Settings switch on: its settings in the leftmost box
            key = res_panel.KEYS[label]
            action, on_ = ('resarm', key), on_ or (res_panel.settings_on() and res_panel.armed() == key)
        else:
            action = ('mop', op, props, closes)
        out.append(Item('abtn', c * BTN_W * k + 3 * k, -TITLE_H * k - (r + 1) * BTN_H * k, (BTN_W - 6) * k,
                        (BTN_H - 4) * k, label, icon, on_, ok, action))
    return w, TITLE_H * k + rows * BTN_H * k, out


def boxes(context, region_w, region_h, k):
    """[(width, height, items placed with the box's bottom left at 0, 0)] - the tool's box first."""
    from .mecha_menu import Item
    from . import mecha_menu as mm, top_bar
    out = []
    from . import res_panel
    rc = res_panel.card(context, k)                  # 0.24.282 a Resolution button's settings instead of the tool's
    if rc is not None:
        rw, rh, its = rc
        w, h = rw + 2 * PAD * k, rh + 2 * PAD * k
        items = [Item('card', 0, 0, w, h)]
        for i in its:
            i.x += PAD * k
            i.y += h - PAD * k
            items.append(i)
        out.append((w, h, items))
        tool = []
    else:
        tool = top_bar.items(context, region_w, region_h, k, part='BOTTOM')
    card = next((i for i in tool if i.kind == 'card'), None)
    if card is not None:
        dx, dy = -card.x, -card.y
        for i in tool:
            i.x += dx
            i.y += dy
        out.append((card.w, card.h, tool))
    sections = list(mm.ACTIONS)
    try:
        live = mm._live(context)
    except (AttributeError, KeyError, TypeError, ReferenceError):
        live = []
    if live:
        sections.append(('Live', live))
    for n, (a, b) in enumerate(CHUNKS):
        parts = [_section(context, sec, buttons, k) for sec, buttons in sections[a:b]]
        if n == 0:
            s = _settings(context, k)
            if s:
                parts.insert(0, s)
        if not parts:
            continue
        w = sum(p[0] for p in parts) + SEC_GAP * k * (len(parts) - 1) + 2 * PAD * k
        h = max(p[1] for p in parts) + 2 * PAD * k
        items = [Item('card', 0, 0, w, h)]
        x = PAD * k
        for pw, _ph, its in parts:
            for i in its:
                i.x += x
                i.y += h - PAD * k
                items.append(i)
            x += pw + SEC_GAP * k
        out.append((w, h, items))
    return out


def layout(context, region_w, region_h, k):
    """(items in region px, the row's height) - the boxes in rows that fit the view, centred, bottom up from the
    folded tool menu."""
    if not on(context):
        return [], 0.0
    from . import ui_bars
    try:
        ob = context.active_object
        from . import res_panel
        key = (region_w, region_h, round(k, 4), ts.effective_tool(context), ob.name if ob else '', ui_bars.VERSION[0],
               res_panel.armed(), res_panel.settings_on())
    except (AttributeError, ReferenceError, UnicodeDecodeError):
        key = None
    now = time.monotonic()
    if key is not None and key == _MEMO['key'] and now - _MEMO['time'] < TTL:
        return _MEMO['value']
    bx = boxes(context, region_w, region_h, k)
    room = region_w - 16 * k
    rows, cur, cw = [], [], 0.0
    for b in bx:
        if cur and cw + GAP * k + b[0] > room:
            rows.append(cur)
            cur, cw = [], 0.0
        cw += (GAP * k if cur else 0.0) + b[0]
        cur.append(b)
    if cur:
        rows.append(cur)
    floor = ui_bars.bottom_taken(context, k, region_w)
    out, y = [], floor
    for row in reversed(rows):                           # (the first row on top)
        rh = max(b[1] for b in row)
        total = sum(b[0] for b in row) + GAP * k * (len(row) - 1)
        x = max(8 * k, (region_w - total) / 2.0)
        for w, h, items in row:
            for i in items:
                i.x += x
                i.y += y + (rh - h)                       # (tops level)
            out += items
            x += w + GAP * k
        y += rh + GAP * k
    value = (out, (y - floor) if rows else 0.0)
    _MEMO.update(key=key, time=now, value=value)
    return value


def height(context, region_w, k):
    region = getattr(context, 'region', None)
    return layout(context, region_w, region.height if region is not None else 1000, k)[1]


def items(context, region_w, region_h, k=1.0):
    return list(layout(context, region_w, region_h, k)[0])
