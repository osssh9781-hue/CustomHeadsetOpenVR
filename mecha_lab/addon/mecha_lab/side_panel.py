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
TABS = 34.0              # 0.24.95 the Tool | Material | HDRI tabs under the title
# page -> (title, icon); 0.24.95 (user: "이건 데칼 탭으로 가자! 메테리얼도 크리쳐랑 메카닉이랑 좀 분리해 줘") the Material
# page split: Mech (the Mech Shader - still 'MATERIAL'), Creature (the Creature Shader, eyes), Decals
PAGES = {'MATERIAL': ('Mech', 'material'), 'CREATURE': ('Creature', 'creature'),
         'SIMPLE': ('Simple', 'material'),   # 0.24.263 a plain Principled material, shader-panel style
         'DECALS': ('Decals', 'decal'),
         'HDRI': ('Render', 'hdri'), 'SHAPES': ('Shapes', 'shapes')}   # 0.24.137 HDRI -> Render   # 0.24.95 Shapes: random base shapes
SECTION = 26.0
BIG_SECTION = 34.0       # 0.24.213 a big coloured title (a box whose title label has a STRIP_COLOR_0n icon)
NOTE = 17.0
TOP_MARGIN = 150.0          # below the navigation gizmo
BOTTOM_MARGIN = 16.0
MIN_W = 44.0             # the folded panel: a small tab with the tool icon

# shown in the top bar for every tool - not repeated here
TOP_BAR_PROPS = {('mch_cut', 'depth_mode'), ('mch_cut', 'targets'), ('mch_settings', 'auto_apply'),
                 ('mch_brush', 'line_mode'), ('mch_brush', 'sketch_first'), ('mch_brush', 'stab_enable'),
                 ('mch_brush', 'stab_strength'), ('mch_brush', 'stab_radius'), ('mch_brush', 'stab_guide'),
                 ('mch_base', 'sketch'), ('mch_cbase', 'sketch')}
# 0.24.78 the lasso's own options / corners and the cut edge's bevel moved to the top bar too
TOP_BAR_PROPS |= {('mch_brush', p) for p in (
    'circle_segments', 'curve_resolution', 'stroke_spacing', 'stroke_smooth', 'stroke_simplify', 'mask_brush_radius',
    'custom_size', 'custom_rotation', 'custom_drag_rotate', 'line_open', 'outline_corner', 'outline_radius',
    'outline_segments')}
TOP_BAR_PROPS |= {('mch_cut', p) for p in (
    'gn_finish', 'gn_width', 'gn_segments', 'gn_sides', 'edge_finish', 'finish_width', 'finish_segments',
    'finish_profile', 'finish_clamp', 'finish_crisp', 'side_a_finish', 'side_a_width', 'side_a_segments',
    'side_b_finish', 'side_b_width', 'side_b_segments')}
TOP_BAR_PROPS |= {('mch_base', p) for p in ('bevel_sides', 'bevel_width', 'bevel_segments')}
# 0.24.79 Concept Move / Path Move / Silhouette Move: their brush settings are in the top bar
TOP_BAR_PROPS |= {('mch_concept', p) for p in (
    'path_method', 'path_area', 'radius_px', 'radius_world', 'lock_size', 'hardness', 'falloff', 'strength',
    'path_hardness', 'path_taper', 'path_turn', 'path_back_mask', 'shape', 'mirror_x', 'keep_density', 'even_out',
    'follow_view')}
TOP_BAR_OPS = {'mch.set_profile', 'mch.split_swap_sides'}   # (set_profile: only the edge bevel's Flat / Chamfer / Bevel)
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


def _moved_away(node, tool):
    """0.24.78 A section whose settings all went to the top bar (and has no button left): not shown - it would be
    a title with nothing (or only a note about those settings) under it."""
    moved = [False]

    def live(n):
        if n.kind in {'prop', 'prop_enum'}:
            if n.data is not None and is_top_bar(n.data, n.prop):
                moved[0] = True
                return False
            return n.data is not None
        if n.kind == 'op':
            return not _op_moved(n)
        if n.kind == 'menu':
            return True
        return any(live(c) for c in n.children)
    return not live(node) and moved[0]


def _op_moved(node):
    idname = node.opts.get('idname')
    return idname in TOP_BAR_OPS and (idname != 'mch.set_profile' or _edge_ops(node))


def _edge_ops(node):
    """An edge bevel button (Flat / Chamfer / Bevel) of the lasso section - not Base Mesh's own profile row."""
    return node.opts.get('props', {}).get('profile') in {'FLAT', 'BEVEL', 'CHAMFER'} and \
        node.parent is not None and len([c for c in node.parent.children if c.kind == 'op']) == 3


def info(data, prop):
    """(type, name, enum items [(id, name)], is_array) - also for Geometry Nodes inputs (``'["Socket_2"]'``)."""
    if prop.startswith('["'):
        key = prop[2:-2]
        try:
            from . import ui_values
            v = ui_values.get(data, prop)
        except (KeyError, TypeError, AttributeError):
            return None
        t = 'BOOLEAN' if isinstance(v, bool) else 'INT' if isinstance(v, int) else \
            'FLOAT' if isinstance(v, float) else 'OTHER'
        return t, key, [], False
    rna = data.bl_rna.properties.get(prop)
    if rna is None:
        return None
    items = [(e.identifier, e.name) for e in rna.enum_items] if rna.type == 'ENUM' else []
    return rna.type, rna.name or prop, items, bool(getattr(rna, 'is_array', False)) and rna.type != 'ENUM'


def summary(kids, tool, most=3):
    """0.24.213 what a folded big section is set to, in a few words: its first settings ("Cotton · Looseness 25").
    Text only - nothing is changed."""
    from . import i18n
    out = []
    stack = list(reversed(kids))
    while stack and len(out) < most:
        n = stack.pop()
        if n.kind in {'row', 'column', 'split', 'grid', 'other'}:
            stack.extend(reversed(n.children))
            continue
        if n.kind != 'prop' or n.data is None or is_top_bar(n.data, n.prop):
            continue
        try:
            inf = info(n.data, n.prop)
            v = getattr(n.data, n.prop)
        except (AttributeError, TypeError, ReferenceError):
            continue
        if inf is None:
            continue
        typ, name, items, arr = inf
        name = n.opts.get('text') or name
        if arr or not name:
            continue
        if typ == 'ENUM':
            out.append(i18n.tr(dict(items).get(v, str(v))))
        elif typ == 'BOOLEAN':
            if v:
                out.append(i18n.tr(name))
        elif typ == 'INT':
            out.append(f'{i18n.tr(name)} {v}')
        elif typ == 'FLOAT':
            out.append(f'{i18n.tr(name)} {v:.3g}')
    return i18n.raw(' · '.join(out))


AUTO_COLOURS = '54263718'    # the big titles' colours in turn (STRIP_COLOR_0n) for a window that names none
KEEPS_OWN = {'RETOPO + BAKE'}  # 0.24.256 boxes put first that bring their own colour and take no turn (the
                             # sections after them keep the colours they had)
CONTROLS = {'prop', 'prop_enum', 'op', 'menu', 'tiles'}


def _has_controls(node):
    return any(n.kind in CONTROLS for n in pc.walk(node))


def _heading(node):
    """The label a loose block starts with: a bare label, or a column of nothing but labels (not the help block)
    - (title, the other label nodes), else None."""
    if node.kind == 'label' and node.opts.get('text'):
        return node, []
    if node.kind in {'column', 'row'} and node.children and not _is_help(node) \
            and all(c.kind == 'label' for c in node.children) and node.children[0].opts.get('text'):
        return node.children[0], list(node.children[1:])
    return None


def _titled(node):
    """A block of the panel that starts with its own name: a column, a label first, controls after it."""
    return (node.kind == 'column' and bool(node.children) and node.children[0].kind == 'label'
            and bool(node.children[0].opts.get('text')) and _has_controls(node))


def auto_sections(tree, tool):
    """0.24.215 (user: "다른 툴들도 클로스 드레이프처럼 정리 - 공통 기능은 묶어 주고 목록 구별해 주고, 기능이나 이상은 없게"):
    every tool's window as big titled sections, made from what its panel already is - nothing is added, taken away
    or put in another order:

    * a box keeps its title, now big and coloured;
    * a block that starts with a label ("Strands", then its sliders) is a section named by that label;
    * what stands loose before / between them is a section "Settings" (or "Actions": only buttons).

    Returns a root Node to lay out (the nodes themselves are the panel's own: their enabled / active state is
    read from where they really are)."""
    top = tree.children
    while len(top) == 1 and top[0].kind in {'column', 'other'} and not _is_help(top[0]) and top[0].children \
            and not (top[0].children[0].kind == 'label' and _has_controls(top[0])):
        top = top[0].children
    if not any(_has_controls(n) for n in top):
        return tree
    out = pc.Node('root')
    out.opts.update(tree.opts)
    count = [0]

    def colour():
        c = AUTO_COLOURS[count[0] % len(AUTO_COLOURS)]
        count[0] += 1
        return f'STRIP_COLOR_0{c}'

    def new_box(title_node=None, title=''):
        box = pc.Node('box')
        lab = pc.Node('label', box, text=title_node.opts['text'] if title_node is not None else title, icon=colour())
        box.children.append(lab)
        out.children.append(box)
        return box
    used = set()
    cur = None                    # the open section loose nodes go into
    cur_auto = False              # ... made here (not a titled column of the panel)
    i = 0
    while i < len(top):
        n = top[i]
        nxt = top[i + 1] if i + 1 < len(top) else None
        if _is_help(n) or n.kind == 'sep' and cur is None:
            out.children.append(n)
        elif n.kind == 'box':
            first = n.children[0] if n.children else None
            if first is not None and first.kind == 'label' and first.opts.get('text') and _has_controls(n):
                if not str(first.opts.get('icon') or '').startswith('STRIP_COLOR_0'):
                    first.opts['icon'] = colour()
                elif first.opts.get('text') not in KEEPS_OWN:
                    count[0] += 1
            out.children.append(n)
            cur = None
        elif _titled(n):
            box = new_box(n.children[0])
            box.children += n.children[1:]
            cur, cur_auto = None, False
        elif _heading(n) is not None and nxt is not None and nxt.kind != 'box' and _heading(nxt) is None \
                and not _is_help(nxt) and not _titled(nxt):
            lab, notes = _heading(n)
            cur = new_box(lab)
            cur.children += notes
            cur_auto = True
        else:
            if cur is None:
                rest = []
                j = i
                while j < len(top) and top[j].kind != 'box' and not _is_help(top[j]) and not _titled(top[j]):
                    rest.append(top[j])
                    j += 1
                only_ops = all(x.kind in {'op', 'label', 'sep'} for r in rest for x in pc.walk(r)
                               if x.kind in CONTROLS | {'label'}) and any(_has_controls(r) for r in rest)
                if not _has_controls(n) and not any(_has_controls(r) for r in rest[:3]):
                    out.children.append(n)                  # (a loose note with nothing under it: as it was)
                    i += 1
                    continue
                name = 'Actions' if only_ops else 'Settings'
                if name in used:                           # (a second one further down: its own fold)
                    name = 'More ' + name
                    while name in used:
                        name += ' +'
                used.add(name)
                cur = new_box(title=name)
                cur_auto = True
            cur.children.append(n)
        i += 1
    return out


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
            from . import ui_values
            on = bool(ui_values.get(node.data, node.prop))
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
        if _op_moved(node):
            return out
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
        main = bool(node.parent.attrs.get('mch_primary')) if node.parent else False     # 0.24.230 a main action
        out.append(('tbtn', text, bool(node.opts.get('depress')),
                    ('op', idname, dict(node.opts.get('props', {}))), None, None,
                    active, big or main, node.state('alert', False), main))
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
        from . import i18n
        return (i18n.vlen(label) * 5.8 + 16.0) * self.k

    def _h(self, c):
        if c[0] == 'tbtn' and len(c) > 9 and c[9]:
            return 38.0 * self.k                      # (a main action button)
        if c[0] == 'tbtn' and len(c) > 7 and c[7]:
            return 34.0 * self.k
        return ROW * self.k

    def _item(self, c, x, y, w, h):
        kind, label, on, action, data, prop, active = c[:7]
        it = self.Item(kind, x, y, w, h, label, '', on, bool(active), action, data, prop or '')
        if kind == 'tbtn' and len(c) > 8 and c[8]:
            it.icon = 'alert'
        if kind == 'tbtn' and len(c) > 9 and c[9]:
            it.icon = 'primary'
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
        elif node.kind == 'tiles':
            self.tiles(node, x, w)
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

    def tiles(self, node, x, w):
        """0.24.177 picture tiles (stamps, presets): rows of ``columns``, the picture over its name, the picked one
        blue; a click runs its operator."""
        k = self.k
        cols = max(1, int(node.opts.get('columns') or 4))
        gap = 5 * k
        tw = (w - (cols - 1) * gap) / cols
        th = tw + 15 * k
        active = node.state('active') and node.state('enabled')
        for i, (label, path, _icon_value, on, idname, props) in enumerate(node.opts.get('tiles', ())):
            if i % cols == 0:
                self.y -= th + (gap if i else 0)
            self.out.append(self.Item('mtile', x + (i % cols) * (tw + gap), self.y, tw, th, label,
                                      ('file:' + path) if path else '', bool(on), bool(active),
                                      ('op', idname, dict(props))))
        self.y -= GAP * k

    def section(self, node, x, w, title=None, start_folded=False, big=''):
        k = self.k
        if _moved_away(node, self.tool):
            return
        kids = list(node.children)
        head_cells = []
        if title is None and kids and kids[0].kind == 'label' and kids[0].opts.get('text'):
            icon = str(kids[0].opts.get('icon') or '')
            if icon.startswith('STRIP_COLOR_0'):      # 0.24.213 a big part of the window: its colour
                big = icon[-1]
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
        if title and big:
            self.y -= BIG_SECTION * k
            # (folded: what it is set to, at the right of the title - "Cotton · Looseness 25 · Wrinkles 50")
            self.out.append(self.Item('shead', x, self.y, w, BIG_SECTION * k, title.upper(),
                                      f'big:{big}|' + (summary(kids, self.tool) if key_folded else ''), not key_folded,
                                      True, ('fold', f'{self.tool}:{title}', start_folded)))
            self.gap(0.3)
        elif title:
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


def page(context):
    """0.24.95 What the panel shows: 'TOOL' (the tool's settings), 'MATERIAL' (the Mech Shader), 'CREATURE' (the
    Creature Shader), 'DECALS' (the decals), 'HDRI' (the scene's HDRI) - ``mech_shader_ui`` - or 'SHAPES' (random
    base shapes - ``random_shapes``); the tabs at its top."""
    return getattr(context.window_manager, 'mch_side_page', 'TOOL')


def content(context, tool, x, width, k):
    """(items, content height) - the panel's rows, y measured down from 0."""
    if page(context) == 'MATERIAL':
        from . import mech_shader_ui
        return mech_shader_ui.content(context, x, width, k)
    if page(context) == 'HDRI':
        from . import mech_shader_ui
        return mech_shader_ui.hdri_content(context, x, width, k)
    if page(context) == 'CREATURE':
        from . import mech_shader_ui
        return mech_shader_ui.creature_page(context, x, width, k)
    if page(context) == 'SIMPLE':
        from . import simple_material
        return simple_material.page(context, x, width, k)
    if page(context) == 'DECALS':
        from . import mech_shader_ui
        return mech_shader_ui.decal_page(context, x, width, k)
    if page(context) == 'SHAPES':
        from . import random_shapes
        return random_shapes.page(context, x, width, k)
    b = Builder(tool, x, width, k)
    tree, lt = _trees(context, tool)
    if tree is not None:
        if tree.opts.get('error'):
            b.note(('note', 'Open the sidebar (N) for this tool', True, None, None, None, True), x, width)
        b.node(auto_sections(tree, tool) if not tree.opts.get('error') else tree, x, width)
    if lt is not None and lt.children:
        b.section(lt, x, width, 'Lasso', start_folded=True, big='9')
    from . import tool_presets                       # 0.24.65 the tool's presets (yours, kept for every file)
    pt = pc.capture(lambda layout, ctx: tool_presets.draw_presets(layout, ctx, tool), context)
    if pt is not None and pt.children and not pt.opts.get('error'):
        b.section(pt, x, width, 'Presets', start_folded=True, big='9')
    if b.help:
        hn = pc.Node('box')
        for line in b.help:
            hn.children.append(pc.Node('label', hn, text=line, icon='NONE'))
        b.help = []
        b.section(hn, x, width, 'Help', start_folded=True, big='9')
    return b.out, -b.y


# --- where it is -------------------------------------------------------------------------------------------------

TAB_TEXT = 11.0          # the page tabs' font size (mecha_menu draws 'ptab' at 11 * scale)


def _text_w(s, size):
    """Width of ``s`` in the UI font at ``size`` px (an estimate when the font cannot be asked)."""
    try:
        import blf
        from . import i18n
        s = i18n.tr(s)
        blf.size(0, size)
        wd = blf.dimensions(0, s)[0]
        if wd > 0:
            return wd
    except (ImportError, AttributeError, ValueError):
        pass
    return 0.62 * size * len(s)


def sidebar_open(context):
    area = getattr(context, 'area', None)
    return area is not None and any(r.type == 'UI' and r.width > 1 for r in area.regions)


def on(context):
    """Shown: preference on, MECHA LAB, a tool with a panel (or the Material page: in any tool), and the sidebar
    (N) closed (it shows the same)."""
    from .workspace_ui import pref
    from . import bottom_bar, ui_tool_settings as uts
    try:
        return (pref('side_panel', True) and bottom_bar.ui_active(context) and not sidebar_open(context)
                and (ts.effective_tool(context) in uts.DRAWERS or page(context) in PAGES))
    except (AttributeError, KeyError, TypeError, ReferenceError):
        return False


def minimised(context):
    return bool(getattr(context.window_manager, 'mch_side_min', False))


def taken(context, k):
    """How much of the right side the panel takes (0 when it is not shown) - the top bar / cards keep clear."""
    if not on(context):
        return 0.0
    return (MIN_W if minimised(context) else panel_width() + 12.0) * k + 12.0 * k


_PW = {}


def panel_width():
    """0.24.264 (user: "메뉴 자체를 옆으로 늘리는 게 낫지 않나?" - seven tabs: "T...", "Me...", "Creat..." in English)
    the panel's width (unscaled): WIDTH, or as wide as the page tabs' names need in the language shown (each name
    whole), up to 440."""
    try:
        from . import i18n
        key = i18n.lang()
    except (ImportError, AttributeError):
        key = ''
    if key not in _PW:
        names = ['Tool'] + [PAGES[p][0] for p in PAGES]
        need = sum(_text_w(n, TAB_TEXT) + 14.0 for n in names) + 3.0 * (len(names) - 1) + 2 * PAD
        _PW[key] = float(min(440.0, max(WIDTH, need)))
    return _PW[key]



def frame(region_w, region_h, k, context=None):
    w = panel_width() * k
    x0, top = region_w - w - 12 * k, region_h - TOP_MARGIN * k
    if context is not None:          # 0.24.77 below the corner card where they would meet (its VIEW row made it taller)
        try:
            from . import bottom_bar, zb_ui
            if bottom_bar.ui_active(context):
                cx, cy, cw, _ch = zb_ui.corner_box(context, region_w, region_h, k)
                if cx < x0 + w and cx + cw > x0:
                    top = min(top, cy - 8 * k)
        except (ImportError, AttributeError, TypeError, ReferenceError):
            pass
    return x0, top, w


def _help_marks(rows, pg, k):
    """0.24.235 (user: "?표 카드도 붙여 줘") the big section titles of a page (Mech / Creature / Decals / Render /
    Shapes) that have a usage entry get a small "?" at their right: a click shows that usage card."""
    from .mecha_menu import Item
    from . import usage_docs
    out = []
    for it in rows:
        out.append(it)
        if it.kind != 'shead':
            continue
        key = usage_docs.feature_key(pg, it.label)
        if key is None:
            continue
        bw = 24 * k
        it.w -= bw + 6 * k
        out.append(Item('pbtn', it.x + it.w + 6 * k, it.y + (it.h - bw) / 2, bw, bw, '?', '', False, True,
                        ('usage_help', key)))
    return out


def layout(context, region_w, region_h, k=1.0):
    """{'items': [...], 'clip': (x, y, w, h) of the scrolled rows or None, 'content': rows height, 'view': ...}."""
    from .mecha_menu import Item
    from . import ui_tool_settings as uts
    tool = ts.effective_tool(context)
    t = ts.TOOL_BY_ID.get(tool)
    pg = page(context)
    mat_page = pg in PAGES
    if t is None and not mat_page:
        return {'items': [], 'clip': None, 'content': 0.0, 'view': 0.0}
    name, icon = PAGES[pg] if mat_page else (t[1], 'png:' + t[3])
    x0, top, w = frame(region_w, region_h, k, context)
    if minimised(context):                       # a small tab: the tool icon, click = open again
        mw = MIN_W * k
        card = Item('card', region_w - mw - 12 * k, top - mw, mw, mw)
        tab = Item('pmin', card.x + 4 * k, card.y + 4 * k, mw - 8 * k, mw - 8 * k, name, icon, False, True,
                   ('minimise',))
        return {'items': [card, tab], 'clip': None, 'content': 0.0, 'view': 0.0}
    rows, h = content(context, tool, x0 + PAD * k, w - 2 * PAD * k, k)
    if mat_page:                                 # 0.24.235 a "?" on the sections that have a usage card
        rows = _help_marks(rows, pg, k)
    try:                                         # 0.24.59 above the bottom main menu
        from . import ui_bars
        floor = ui_bars.panel_floor(context, k, region_w, x0)
    except (ImportError, AttributeError, TypeError, ReferenceError):
        floor = 0.0
    head = (HEAD + TABS) * k
    room = top - BOTTOM_MARGIN * k - floor - head - 2 * PAD * k
    view = max(0.0, min(h, room))
    wm = context.window_manager
    scroll = max(0.0, min(float(getattr(wm, 'mch_side_scroll', 0.0)), h - view))
    card_h = head + view + 2 * PAD * k
    out = [Item('card', x0, top - card_h, w, card_h)]
    out.append(Item('phead', x0 + PAD * k, top - PAD * k - HEAD * k + 6 * k, w - 2 * PAD * k - 34 * k,
                    HEAD * k - 6 * k, name.upper(), icon, False, True, None))
    out.append(Item('pbtn', x0 + w - PAD * k - 26 * k, top - PAD * k - 30 * k, 26 * k, 26 * k, '–', '', False, True,
                    ('minimise',)))
    # 0.24.95 the pages: the tool's settings | Material (Mech Shader) | HDRI (user: "재질이랑 hdri는 분리해야지")
    # 0.24.95 five tabs (Tool | Mech | Creature | Decals | HDRI): each as wide as its name needs (the tool's own name
    # is in the title above when its page is shown)
    # 0.24.95 six with Shapes: a narrower gap, each as wide as its name needs plus a little
    # 0.24.137 each tab as wide as its name really is in the font ("Mech" is wider than "Tool": with "Render" for
    # "HDRI" the letter-count share cut it to "Me…"), the spare room shared out evenly
    tabs = [('Tool', 'TOOL')] + [(PAGES[p][0], p) for p in PAGES]
    gap = 3 * k
    room = w - 2 * PAD * k - (len(tabs) - 1) * gap
    need = [_text_w(label, TAB_TEXT * k) + 8 * k for label, _p in tabs]
    spare = room - sum(need)
    widths = [n + spare / len(need) for n in need] if spare >= 0 else [room * n / sum(need) for n in need]
    tx = x0 + PAD * k
    ty = top - PAD * k - HEAD * k - (TABS - 6) * k
    for (label, p), tw in zip(tabs, widths):
        out.append(Item('ptab', tx, ty, tw, (TABS - 8) * k, label, '', pg == p, True, ('page', p)))
        tx += tw + gap
    y_top = top - PAD * k - head
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
