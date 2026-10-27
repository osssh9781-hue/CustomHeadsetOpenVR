"""0.24.59 Side panel: the tool's own settings at the right of the viewport, in the Mecha look - so the sidebar (N)
can stay closed.

The content is the tool's normal sidebar panel, read with ``panel_capture`` and laid out again:

* numbers -> Quick HUD style bars (drag, click = type, Ctrl+click = default)
* choices shown as buttons -> pills (blue = in use), a closed list -> a pill that opens the list
* on / off -> a switch (or a pill when the panel shows it as a button)
* boxes -> sections with a title (click = fold), buttons -> pills, notes -> small grey text
* the help lines (small grey text at the end of a panel) -> a folded Help section

What the top bar shows for every tool (``top_bar``: Line / Sketch / Slow Line, Targets, Depth, Auto Apply) is left
out here.  Layout only so far (``items``); drawing and clicks follow once the look is agreed.
"""
from __future__ import annotations

from . import panel_capture as pc
from . import tool_state as ts

WIDTH = 300.0
ROW = 28.0
GAP = 6.0
PAD = 12.0
HEAD = 40.0
SECTION = 26.0
NOTE = 17.0
TOP_MARGIN = 150.0          # below the navigation gizmo
BOTTOM_MARGIN = 16.0
MIN_W = 44.0             # the folded panel: a small tab with the tool icon

# shown in the top bar for every tool - not repeated here
TOP_BAR_PROPS = {('mch_cut', 'depth_mode'), ('mch_cut', 'targets'), ('mch_settings', 'auto_apply'),
                 ('mch_brush', 'line_mode'), ('mch_brush', 'sketch_first'), ('mch_brush', 'stab_enable'),
                 ('mch_brush', 'stab_strength'), ('mch_brush', 'stab_radius'), ('mch_brush', 'stab_guide'),
                 ('mch_base', 'sketch'), ('mch_cbase', 'sketch')}
# an icon-only button ('text=""'): a sign instead of the icon
ICON_TEXT = {'ADD': '+', 'REMOVE': '−', 'X': '×', 'CANCEL': '×', 'CHECKMARK': '✓', 'LOOP_BACK': '↺',
             'FILE_REFRESH': '↻', 'TRIA_UP': '▲', 'TRIA_DOWN': '▼', 'TRIA_LEFT': '◀', 'TRIA_RIGHT': '▶',
             'ARROW_LEFTRIGHT': '⇄', 'PRESET': '☰', 'TRASH': '×', 'DUPLICATE': '⧉', 'EYEDROPPER': 'Pick'}

FOLDED = set()              # 'TOOL:section title' the user folded (Help / Lasso start folded)
OPENED = set()              # ... and the start-folded ones the user opened


# --- what a property is ----------------------------------------------------------------------------------------

def _owner(data):
    try:
        return data.path_from_id()
    except (AttributeError, ValueError, TypeError):
        return ''


def is_top_bar(data, prop):
    return (_owner(data), prop) in TOP_BAR_PROPS


def info(data, prop):
    """(type, name, enum items [(id, name)], is_array) - also for Geometry Nodes inputs (``'["Socket_2"]'``)."""
    if prop.startswith('["'):
        key = prop[2:-2]
        try:
            v = data[key]
        except (KeyError, TypeError):
            return None
        t = 'BOOLEAN' if isinstance(v, bool) else 'INT' if isinstance(v, int) else \
            'FLOAT' if isinstance(v, float) else 'OTHER'
        return t, key, [], False
    rna = data.bl_rna.properties.get(prop)
    if rna is None:
        return None
    items = [(e.identifier, e.name) for e in rna.enum_items] if rna.type == 'ENUM' else []
    return rna.type, rna.name or prop, items, bool(getattr(rna, 'is_array', False)) and rna.type != 'ENUM'


def folded(tool, title, default=False):
    key = f'{tool}:{title}'
    return (key not in OPENED) if default else (key in FOLDED)


# --- the capture -> rows -------------------------------------------------------------------------------------

def _is_help(node):
    """A block of small grey lines (``_hint``): only labels, scaled down."""
    return (node.kind == 'column' and float(node.attrs.get('scale_y', 1.0)) < 1.0 and node.children
            and all(c.kind == 'label' for c in node.children))


def _cells(node, tool):
    """The widgets of one element as cells [(kind, label, on, action, data, prop, extra)]."""
    out = []
    active = node.state('active') and node.state('enabled')
    if node.kind == 'prop':
        if node.data is None or is_top_bar(node.data, node.prop):
            return out
        inf = info(node.data, node.prop)
        if inf is None:
            return out
        typ, name, items, is_array = inf
        text = node.opts.get('text')
        label = name if text is None else text
        if not label and node.opts.get('icon', 'NONE') in ICON_TEXT:
            label = ICON_TEXT[node.opts['icon']]
        if typ == 'ENUM' and node.opts.get('expand'):
            v = getattr(node.data, node.prop)
            for ident, iname in items:
                on = ident in v if isinstance(v, set) else v == ident
                out.append(('seg', iname, on, ('enum', ident), node.data, node.prop, active))
        elif typ == 'ENUM':
            out.append(('drop', label, False, ('menu_enum',), node.data, node.prop, active))
        elif typ == 'BOOLEAN' and not is_array:
            on = bool(node.data[node.prop[2:-2]] if node.prop.startswith('["') else getattr(node.data, node.prop))
            as_button = node.opts.get('toggle') not in (-1, False, 0) or node.opts.get('icon', 'NONE') != 'NONE'
            out.append(('seg' if as_button else 'switch', label or name, on, ('bool',), node.data, node.prop, active))
        elif typ in {'INT', 'FLOAT'} and not is_array:
            out.append(('mini', label, False, ('number',), node.data, node.prop, active))
        elif typ in {'INT', 'FLOAT'}:
            out.append(('note', f'{label}: (sidebar)', False, None, None, None, active))
        else:
            try:
                v = getattr(node.data, node.prop)
                v = getattr(v, 'name', v)
            except AttributeError:
                v = ''
            out.append(('note', f'{label}: {v}' if label else str(v), False, None, None, None, active))
    elif node.kind == 'prop_enum':
        inf = info(node.data, node.prop)
        if inf is not None:
            value = node.opts['value']
            label = node.opts.get('text') or dict(inf[2]).get(value, value)
            out.append(('seg', label, getattr(node.data, node.prop) == value, ('enum', value), node.data, node.prop,
                        active))
    elif node.kind == 'op':
        import bpy
        idname = node.opts['idname']
        text = node.opts.get('text')
        if text == '' and node.opts.get('icon', 'NONE') in ICON_TEXT:
            text = ICON_TEXT[node.opts['icon']]
        if not text:
            try:
                mod, name = idname.split('.')
                text = getattr(getattr(bpy.ops, mod), name).get_rna_type().name
            except (AttributeError, ValueError, KeyError):
                text = idname
        big = float(node.parent.attrs.get('scale_y', 1.0)) >= 1.2 if node.parent else False
        out.append(('tbtn', text, bool(node.opts.get('depress')),
                    ('op', idname, dict(node.opts.get('props', {}))), None, None,
                    active, big, node.state('alert', False)))
    elif node.kind == 'menu':
        out.append(('tbtn', (node.opts.get('text') or 'Menu') + '  ▾', False, ('menu', node.opts['name']), None,
                    None, active))
    elif node.kind == 'label' and node.opts.get('text'):
        icon = node.opts.get('icon', 'NONE')
        out.append(('note', node.opts['text'], icon == 'ERROR', None, None, None, active))
    return out


def _prefix(labels):
    """'Alt: ' when every label starts with it (a word and a colon)."""
    first = labels[0]
    if ': ' not in first:
        return ''
    pre = first[:first.index(': ') + 2]
    return pre if all(lb.startswith(pre) and len(lb) > len(pre) for lb in labels) else ''


class Builder:
    """Places rows top-down inside the panel (y = the next row's top edge, going down)."""

    def __init__(self, tool, x, width, k):
        from .mecha_menu import Item
        self.Item, self.tool, self.k = Item, tool, k
        self.x, self.width = x, width
        self.y = 0.0
        self.out = []
        self.help = []

    def gap(self, f=1.0):
        self.y -= GAP * self.k * f

    def place_row(self, cells, x, w, columns=None):
        """One row of cells, equal widths; wraps to more lines when they would be narrower than they need."""
        k = self.k
        if not cells:
            return
        pre = _prefix([c[1] for c in cells]) if len(cells) > 1 and all(c[0] == 'seg' for c in cells) else ''
        if pre:
            self.note(('note', pre.rstrip(': '), False, None, None, None, cells[0][6]), x, w)
            cells = [(c[0], c[1][len(pre):]) + tuple(c[2:]) for c in cells]
        if len(cells) == 1 and cells[0][0] == 'note':
            self.note(cells[0], x, w)
            return
        need = max(self._min_w(c) for c in cells)
        per_line = columns or max(1, min(len(cells), int((w + GAP * k) / (need + GAP * k))))
        if per_line < len(cells) and not columns:     # wrap evenly (5 choices on a narrow panel: 3 + 2)
            lines = (len(cells) + per_line - 1) // per_line
            per_line = (len(cells) + lines - 1) // lines
        for start in range(0, len(cells), per_line):
            line = cells[start:start + per_line]
            n = per_line if columns else len(line)
            cw = (w - (n - 1) * GAP * k) / n
            h = max(self._h(c) for c in line)
            self.y -= h
            for i, c in enumerate(line):
                self.out.append(self._item(c, x + i * (cw + GAP * k), self.y, cw, h))
            self.y -= GAP * k

    def _min_w(self, c):
        kind, label = c[0], c[1]
        if kind in {'mini', 'switch'}:
            return 150.0 * self.k
        if kind == 'drop':
            return (110.0 if label else 80.0) * self.k
        return (len(label) * 5.8 + 16.0) * self.k

    def _h(self, c):
        if c[0] == 'tbtn' and len(c) > 7 and c[7]:
            return 34.0 * self.k
        return ROW * self.k

    def _item(self, c, x, y, w, h):
        kind, label, on, action, data, prop, active = c[:7]
        it = self.Item(kind, x, y, w, h, label, '', on, bool(active), action, data, prop or '')
        if kind == 'tbtn' and len(c) > 8 and c[8]:
            it.icon = 'alert'
        return it

    def note(self, c, x, w):
        k = self.k
        self.y -= NOTE * k
        self.out.append(self.Item('pnote', x, self.y, w, NOTE * k, c[1], 'error' if c[2] else '', False, bool(c[6])))
        self.y -= 2 * k

    def node(self, node, x, w):
        k = self.k
        if node.kind in {'root', 'column', 'other'}:
            if _is_help(node):
                self.help += [c.opts.get('text', '') for c in node.children if c.opts.get('text')]
                return
            kids = node.children
            i = 0
            while i < len(kids):
                c = kids[i]
                if c.kind == 'prop_enum':
                    j = i
                    while j < len(kids) and kids[j].kind == 'prop_enum' and kids[j].prop == c.prop \
                            and kids[j].data == c.data:
                        j += 1
                    self.place_row([cell for n in kids[i:j] for cell in _cells(n, self.tool)], x, w)
                    i = j
                    continue
                self.node(c, x, w)
                i += 1
        elif node.kind == 'box':
            self.section(node, x, w)
        elif node.kind in {'row', 'split', 'grid'}:
            if any(c.kind in {'row', 'column', 'box', 'split', 'grid', 'other'} for c in node.children):
                for c in node.children:          # rows holding containers: one after the other
                    self.node(c, x, w)
                return
            cells = [cell for c in node.children for cell in _cells(c, self.tool)]
            notes = [c for c in cells if c[0] == 'note']
            rest = [c for c in cells if c[0] != 'note']
            for c in notes:
                self.note(c, x, w)
            cols = node.opts.get('columns') if node.kind == 'grid' else None
            self.place_row(rest, x, w, columns=cols or None)
        elif node.kind == 'sep':
            self.gap(float(node.opts.get('factor', 1.0)))
        else:
            cells = _cells(node, self.tool)
            for c in cells:
                if c[0] == 'note':
                    self.note(c, x, w)
                elif c[0] == 'seg' and c[3] and c[3][0] == 'enum':
                    pass
                else:
                    self.place_row([c], x, w)
            segs = [c for c in cells if c[0] == 'seg' and c[3] and c[3][0] == 'enum']
            if segs:
                self.place_row(segs, x, w)

    def section(self, node, x, w, title=None, start_folded=False):
        k = self.k
        kids = list(node.children)
        head_cells = []
        if title is None and kids and kids[0].kind == 'label' and kids[0].opts.get('text'):
            title = kids.pop(0).opts['text']
        elif title is None and kids and kids[0].kind == 'row' and kids[0].children \
                and kids[0].children[0].kind == 'label' and kids[0].children[0].opts.get('text') \
                and all(c.kind in {'op', 'prop'} for c in kids[0].children[1:]):
            row = kids.pop(0)
            title = row.children[0].opts['text']
            head_cells = [cell for c in row.children[1:] for cell in _cells(c, self.tool)]
        title = title or ''
        key_folded = folded(self.tool, title, start_folded) if title else False
        top = self.y
        self.gap(0.5)
        bg = self.Item('sbg', x, 0, w, 0)
        self.out.append(bg)
        if title:
            self.y -= SECTION * k
            hw = 30 * k * len(head_cells)
            self.out.append(self.Item('shead', x, self.y, w - hw, SECTION * k, title.upper(), '', not key_folded,
                                      True, ('fold', f'{self.tool}:{title}', start_folded)))
            for i, c in enumerate(head_cells):            # e.g. Reset at the right of the title
                it = self._item(c, x + w - hw + i * 30 * k + 3 * k, self.y + 2 * k, 26 * k, SECTION * k - 4 * k)
                self.out.append(it)
        if not key_folded:
            self.gap(0.5)
            for c in kids:
                self.node(c, x + 8 * k, w - 16 * k)
        self.gap(0.3)
        bg.y, bg.h = self.y, top - self.y - GAP * k * 0.5
        self.gap(0.7)


# --- reading the panels (cached: the viewport redraws far more often than the settings change) ------------------

_CACHE = {'key': None, 'time': 0.0, 'trees': (None, None)}
REFRESH = 0.5               # s: read again at least this often (changes made elsewhere: undo, the sidebar ...)


def dirty():
    """Read the panels again on the next draw (after a click here, a data change, undo)."""
    _CACHE['key'] = None
    from . import ui_bars
    ui_bars.bump()


def _trees(context, tool):
    import time
    from . import ui_tool_settings as uts
    ob = getattr(context, 'active_object', None)
    key = (tool, ob.name if ob is not None else '', ob.mode if ob is not None else '')
    now = time.monotonic()
    if _CACHE['key'] == key and now - _CACHE['time'] < REFRESH:
        return _CACHE['trees']
    drawer = uts.DRAWERS.get(tool)
    tree = pc.capture(drawer, context) if drawer is not None else None
    lasso = None
    if tool in ts.SHAPE_TOOLS:
        lasso = pc.capture(lambda layout, ctx: uts.draw_shape_options(layout, ctx, tool), context)
    _CACHE.update(key=key, time=now, trees=(tree, lasso))
    return tree, lasso


def content(context, tool, x, width, k):
    """(items, content height) - the panel's rows, y measured down from 0."""
    b = Builder(tool, x, width, k)
    tree, lt = _trees(context, tool)
    if tree is not None:
        if tree.opts.get('error'):
            b.note(('note', 'Open the sidebar (N) for this tool', True, None, None, None, True), x, width)
        b.node(tree, x, width)
    if lt is not None and lt.children:
        b.section(lt, x, width, 'Lasso', start_folded=True)
    if b.help:
        hn = pc.Node('box')
        for line in b.help:
            hn.children.append(pc.Node('label', hn, text=line, icon='NONE'))
        b.help = []
        b.section(hn, x, width, 'Help', start_folded=True)
    return b.out, -b.y


# --- where it is -------------------------------------------------------------------------------------------------

def sidebar_open(context):
    area = getattr(context, 'area', None)
    return area is not None and any(r.type == 'UI' and r.width > 1 for r in area.regions)


def on(context):
    """Shown: preference on, MECHA LAB, a tool with a panel, and the sidebar (N) closed (it shows the same)."""
    from .workspace_ui import pref
    from . import bottom_bar, ui_tool_settings as uts
    try:
        return (pref('side_panel', True) and bottom_bar.ui_active(context) and not sidebar_open(context)
                and ts.effective_tool(context) in uts.DRAWERS)
    except (AttributeError, KeyError, TypeError, ReferenceError):
        return False


def minimised(context):
    return bool(getattr(context.window_manager, 'mch_side_min', False))


def taken(context, k):
    """How much of the right side the panel takes (0 when it is not shown) - the top bar / cards keep clear."""
    if not on(context):
        return 0.0
    return (MIN_W if minimised(context) else WIDTH + 12.0) * k + 12.0 * k



def frame(region_w, region_h, k):
    w = WIDTH * k
    return region_w - w - 12 * k, region_h - TOP_MARGIN * k, w


def layout(context, region_w, region_h, k=1.0):
    """{'items': [...], 'clip': (x, y, w, h) of the scrolled rows or None, 'content': rows height, 'view': ...}."""
    from .mecha_menu import Item
    tool = ts.effective_tool(context)
    t = ts.TOOL_BY_ID.get(tool)
    if t is None:
        return {'items': [], 'clip': None, 'content': 0.0, 'view': 0.0}
    x0, top, w = frame(region_w, region_h, k)
    if minimised(context):                       # a small tab: the tool icon, click = open again
        mw = MIN_W * k
        card = Item('card', region_w - mw - 12 * k, top - mw, mw, mw)
        tab = Item('pmin', card.x + 4 * k, card.y + 4 * k, mw - 8 * k, mw - 8 * k, t[1], 'png:' + t[3], False, True,
                   ('minimise',))
        return {'items': [card, tab], 'clip': None, 'content': 0.0, 'view': 0.0}
    rows, h = content(context, tool, x0 + PAD * k, w - 2 * PAD * k, k)
    try:                                         # 0.24.59 above the bottom main menu
        from . import ui_bars
        floor = ui_bars.bottom_taken(context, k, region_w)
    except (ImportError, AttributeError, TypeError, ReferenceError):
        floor = 0.0
    room = top - BOTTOM_MARGIN * k - floor - HEAD * k - 2 * PAD * k
    view = max(0.0, min(h, room))
    wm = context.window_manager
    scroll = max(0.0, min(float(getattr(wm, 'mch_side_scroll', 0.0)), h - view))
    card_h = HEAD * k + view + 2 * PAD * k
    out = [Item('card', x0, top - card_h, w, card_h)]
    out.append(Item('phead', x0 + PAD * k, top - PAD * k - HEAD * k + 6 * k, w - 2 * PAD * k - 34 * k,
                    HEAD * k - 6 * k, t[1].upper(), 'png:' + t[3], False, True, None))
    out.append(Item('pbtn', x0 + w - PAD * k - 26 * k, top - PAD * k - 30 * k, 26 * k, 26 * k, '–', '', False, True,
                    ('minimise',)))
    y_top = top - PAD * k - HEAD * k
    cy, ch = y_top - view, view
    for it in rows:                              # only whole rows inside the window (no half-drawn rows)
        it.y += y_top + scroll
        if it.kind == 'sbg':                     # a section's background: cut to the window
            lo, hi = max(it.y, cy), min(it.y + it.h, cy + ch)
            if hi - lo < 2 * k:
                continue
            it.y, it.h = lo, hi - lo
        elif it.y < cy - 0.5 or it.y + it.h > cy + ch + 0.5:
            continue
        out.append(it)
    if h > view + 1:
        bar_h = max(30 * k, view * view / h)
        bar_y = y_top - bar_h - (view - bar_h) * (scroll / max(1e-6, h - view))
        out.append(Item('sbar', x0 + w - 7 * k, bar_y, 3 * k, bar_h))
    return {'items': out, 'clip': (x0, cy, w, ch), 'content': h, 'view': view}


def items(context, region_w, region_h, k=1.0):
    return layout(context, region_w, region_h, k)['items']


def toggle_fold(key, start_folded):
    if start_folded:
        OPENED.symmetric_difference_update({key})
    else:
        FOLDED.symmetric_difference_update({key})
    dirty()


def scroll_by(context, region_w, region_h, k, dy):
    lay = layout(context, region_w, region_h, k)
    wm = context.window_manager
    wm.mch_side_scroll = max(0.0, min(float(wm.mch_side_scroll) + dy, max(0.0, lay['content'] - lay['view'])))
    from . import ui_bars
    ui_bars.bump()


def over(context, x, y):
    """Is region point (x, y) on the panel?"""
    region = getattr(context, 'region', None)
    if region is None or not on(context):
        return False
    from .ui_gpu import ui_factor
    its = items(context, region.width, region.height, ui_factor(context, region))
    return bool(its) and its[0].hit(x, y)
