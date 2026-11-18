"""0.24.223 A card of our own drawn in the viewport for a picker that used to be a Blender popup (user: the popups
close as soon as the mouse leaves them).  It stays while the mouse is anywhere; a click on one of its buttons does its
job and closes it (user: "내가 버튼 누르면 닫혀야지"), and so does the X.

``open(title, drawer, width)``: ``drawer(layout, context)`` draws like a panel (read by panel_capture).
"""
from . import panel_capture as pc

CARD = {}                # {'title', 'drawer', 'width', 'scroll'} while one is open
HEAD = 40.0
PAD = 12.0
MARGIN = 40.0


def is_open():
    return bool(CARD)


def open(title, drawer, width=640.0, icon=''):
    CARD.clear()
    CARD.update(title=title, drawer=drawer, width=float(width), scroll=0.0, icon=icon)
    _bump()


def close():
    if CARD:
        CARD.clear()
        _bump()


def _bump():
    try:
        from . import ui_bars
        ui_bars.bump()
        import bpy
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    except (ImportError, AttributeError, ReferenceError, RuntimeError):
        pass


def layout(context, region_w, region_h, k=1.0):
    """{'items', 'content', 'view'} - the card in the middle of the viewport."""
    from .mecha_menu import Item
    from . import side_panel
    if not CARD:
        return {'items': [], 'content': 0.0, 'view': 0.0}
    w = min(CARD['width'] * k, region_w - 2 * MARGIN * k)
    x0 = (region_w - w) / 2
    b = side_panel.Builder('FLOAT', x0 + PAD * k, w - 2 * PAD * k, k)
    tree = pc.capture(CARD['drawer'], context)
    if tree is not None and not tree.opts.get('error'):
        b.node(tree, x0 + PAD * k, w - 2 * PAD * k)
    rows, h = b.out, -b.y
    head = HEAD * k
    room = region_h - 2 * MARGIN * k - head - 2 * PAD * k
    view = max(0.0, min(h, room))
    scroll = max(0.0, min(float(CARD.get('scroll', 0.0)), h - view))
    CARD['scroll'] = scroll
    card_h = head + view + 2 * PAD * k
    top = (region_h + card_h) / 2
    out = [Item('card', x0, top - card_h, w, card_h, '', 'solid')]
    out.append(Item('phead', x0 + PAD * k, top - PAD * k - head + 6 * k, w - 2 * PAD * k - 34 * k, head - 6 * k,
                    CARD['title'], CARD.get('icon', ''), False, True, None))
    out.append(Item('pbtn', x0 + w - PAD * k - 26 * k, top - PAD * k - 30 * k, 26 * k, 26 * k, '×', '', False, True,
                    ('float_close',)))
    y_top = top - PAD * k - head
    cy = y_top - view
    for it in rows:                              # only whole rows inside the window
        it.y += y_top + scroll
        if it.kind == 'sbg':
            lo, hi = max(it.y, cy), min(it.y + it.h, cy + view)
            if hi - lo < 2 * k:
                continue
            it.y, it.h = lo, hi - lo
        elif it.y < cy - 0.5 or it.y + it.h > cy + view + 0.5:
            continue
        out.append(it)
    if h > view + 1:
        bar_h = max(30 * k, view * view / h)
        bar_y = y_top - bar_h - (view - bar_h) * (scroll / max(1e-6, h - view))
        out.append(Item('sbar', x0 + w - 7 * k, bar_y, 3 * k, bar_h))
    return {'items': out, 'content': h, 'view': view}


def items(context, region_w, region_h, k=1.0):
    return layout(context, region_w, region_h, k)['items']


def holds(context, item):
    """Is ``item`` one of the open card's buttons?"""
    region = getattr(context, 'region', None)
    if not CARD or region is None:
        return False
    from . import ui_bars
    its = ui_bars.drawn_items(context)
    start = next((i for i in range(len(its) - 1, -1, -1) if its[i].kind == 'pbtn'
                  and its[i].action == ('float_close',)), None)
    return start is not None and any(i is item for i in its[start:])


def over(context, x, y):
    region = getattr(context, 'region', None)
    if not CARD or region is None:
        return False
    from .ui_gpu import ui_factor
    its = items(context, region.width, region.height, ui_factor(context, region))
    return bool(its) and its[0].hit(x, y)


def scroll_by(context, region_w, region_h, k, dy):
    lay = layout(context, region_w, region_h, k)
    CARD['scroll'] = max(0.0, min(float(CARD.get('scroll', 0.0)) + dy, max(0.0, lay['content'] - lay['view'])))
    _bump()
