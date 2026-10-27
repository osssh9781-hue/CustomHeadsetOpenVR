"""0.24.59 Top bar: what the drawing tools share, big and clear at the top middle of the viewport (it replaces the
shape / Sketch / Line / Surface ... buttons of Blender's tool header, which keeps only the Custom PNG picker).

    SHAPE [lasso][curve][rect][circle][ellipse][free][custom]  |  DRAW [Line] [Sketch] [Slow Line] (Strength)
    (Radius)  |  LINE (Width) [Caps v] [Taper] (Taper) [Pressure] [Attach Ends]  |  [Surface] (Gap) [Through]
    [Sim] [Preset v]  |  TARGET [Auto] [Selected] [Active]  |  DEPTH [Through All] [From Surface] (Depth)
    |  [Auto Apply]  |  [Ortho]

Only what the tool in use has; groups wrap to a second / third row when the room between the tool strip and the
side panel is too narrow.  The tool's own settings are in the side panel (``side_panel``), which leaves these out.
"""
from __future__ import annotations

from . import tool_state as ts

ROW = 30.0
ICON = 34.0
GAP = 5.0
PAD = 8.0
TOP = 10.0
CUT_LIKE = {'CUT', 'SPLIT', 'HIDE'}


def _cell(kind, label, on=False, action=None, data=None, prop='', width=None, icon=''):
    return {'kind': kind, 'label': label, 'on': on, 'action': action, 'data': data, 'prop': prop,
            'width': width, 'icon': icon}


def _seg(label, data, prop, on=None):
    return _cell('seg', label, bool(getattr(data, prop)) if on is None else on, ('bool',), data, prop)


def groups(context, tool):
    """[(title, [cells])] for the tool in use."""
    from . import lasso_line, lasso_sketch, mecha_menu, target_rules
    scene = context.scene
    brush = getattr(scene, 'mch_brush', None)
    out = []
    if brush is None:
        return out
    if tool in ts.SHAPE_TOOLS:
        out.append(('Shape', [_cell('ibtn', label, brush.shape == sid, ('shape', sid), icon='png:' + stem,
                                    width=ICON) for sid, label, _d, stem, _f in ts.SHAPES]))
    draw = [_cell('seg', label, on, ('mode', key)) for key, label, on in mecha_menu.draw_modes(context)]
    drawing = tool in target_rules.PICKING | target_rules.OWN_ROW - {'CMOVE', 'CPATH'}
    if drawing:
        draw.append(_seg('Slow Line', brush, 'stab_enable'))
        if brush.stab_enable:
            draw.append(_cell('mini', 'Strength', action=('number',), data=brush, prop='stab_strength', width=150))
            draw.append(_cell('mini', 'Radius', action=('number',), data=brush, prop='stab_radius', width=130))
    if draw:
        out.append(('Draw', draw))
    line_tool = tool in lasso_line.MODES or tool in lasso_line.ALWAYS
    if line_tool and (brush.line_mode or tool in lasso_line.ALWAYS):
        line = [_cell('mini', 'Width', action=('number',), data=brush, prop='line_width', width=140),
                _cell('drop', '', action=('menu_enum',), data=brush, prop='line_caps', width=96),
                _seg('Taper', brush, 'line_taper_on')]
        if brush.line_taper_on:
            line.append(_cell('mini', 'Taper', action=('number',), data=brush, prop='line_taper', width=120))
        line.append(_seg('Pressure', brush, 'line_pressure'))
        if tool in {'BASE', 'CBASE'}:
            from . import base_mesh
            bd = base_mesh.scene_defaults(context)
            line.append(_seg('Attach Ends', bd, 'line_attach'))
            if bd.line_attach:
                line.append(_cell('drop', '', action=('menu_enum',), data=bd, prop='attach_curve', width=104))
        out.append(('Line', line))
    extra = []
    if tool in {'CUT', 'SPLIT', 'PLATE', 'WRINKLE'}:
        extra.append(_seg('Surface', brush, 'surface_mode'))
        if brush.surface_mode and tool in {'CUT', 'SPLIT'}:
            extra.append(_cell('mini', 'Gap', action=('number',), data=brush, prop='surface_gap', width=110))
    if tool in {'PLATE', 'WRINKLE', 'CPLATE'}:
        extra.append(_seg('Through', brush, 'through_mode'))
        if brush.through_mode and tool != 'CPLATE':
            extra.append(_cell('mini', 'Crease', action=('number',), data=brush, prop='through_crease', width=120))
    if tool == 'WRINKLE' and hasattr(scene, 'mch_wrinkle'):
        ws = scene.mch_wrinkle
        extra.append(_seg('Sim', ws, 'sim_after'))
        if ws.sim_after:
            extra.append(_cell('drop', '', action=('menu_enum',), data=ws, prop='sim_preset', width=110))
    if extra:
        out.append(('', extra))
    cut = getattr(scene, 'mch_cut', None)
    if cut is not None and drawing:
        out.append(('Target', [_cell('seg', label, cut.targets == ident, ('enum', ident), cut, 'targets')
                               for ident, label in (('AUTO', 'Auto'), ('SELECTED', 'Selected'),
                                                    ('ACTIVE', 'Active'))]))
    if cut is not None and tool in CUT_LIKE:
        depth = [_cell('seg', label, cut.depth_mode == ident, ('enum', ident), cut, 'depth_mode')
                 for ident, label in (('THROUGH', 'Through All'), ('SURFACE', 'From Surface'))]
        if cut.depth_mode == 'SURFACE':
            depth.append(_cell('mini', 'Depth', action=('number',), data=cut, prop='depth', width=130))
        out.append(('Depth', depth))
        st = getattr(scene, 'mch_settings', None)
        if st is not None and tool != 'HIDE':
            out.append(('', [_seg('Auto Apply', st, 'auto_apply')]))
    from .workspace_ui import _ORTHO_LOCK_KEY
    locked = bool(context.workspace and context.workspace.get(_ORTHO_LOCK_KEY, False))
    out.append(('', [_cell('seg', 'Ortho', locked, ('op', 'mch.ortho_lock', {}))]))
    return out


def _width(c, k):
    if c['width']:
        return c['width'] * k
    return (len(c['label']) * 7.0 + 24.0) * k


def _group_width(title, cells, k):
    w = sum(_width(c, k) for c in cells) + GAP * k * (len(cells) - 1)
    if title:
        w += (len(title) * 7.0 + 8.0) * k + GAP * k
    return w


def rows_of(gs, room, k):
    """Groups in the fewest rows that fit ``room`` px (at most 3), split so the rows are about equally wide (a
    row with one lonely button looked odd)."""
    import itertools
    sep = 14.0 * k
    widths = [_group_width(t, c, k) for t, c in gs]

    def row_w(a, b):
        return sum(widths[a:b]) + sep * (b - a - 1)
    n = len(gs)
    for rows in (1, 2, 3):
        best = None
        for cuts in itertools.combinations(range(1, n), rows - 1):
            bounds = (0,) + cuts + (n,)
            w = max(row_w(a, b) for a, b in zip(bounds, bounds[1:]))
            if best is None or w < best[0]:
                best = (w, bounds)
        if best is not None and (best[0] <= room or rows == 3 or rows >= n):
            b = best[1]
            return [gs[x:y] for x, y in zip(b, b[1:])]
    return [gs]


def room(context, region_w, k):
    """(left, right) px the bar may use: right of the tool strip, left of the side panel (``items`` uses the whole
    width while the bar stays above the side panel's top)."""
    from . import ui_bars
    left = ui_bars.left_inset(context) + ui_bars.strip_width(context, k)
    right = 0.0
    try:
        from . import side_panel
        right = side_panel.taken(context, k)
    except (ImportError, AttributeError, TypeError, ReferenceError):
        pass
    return left, region_w - right


def items(context, region_w, region_h, k=1.0, left=None, right=None):
    """The bar as Mecha Menu Items (region px)."""
    from .mecha_menu import Item
    tool = ts.effective_tool(context)
    gs = groups(context, tool)
    if not gs:
        return []
    panel_top = None
    l_low = left
    if left is None or right is None:
        from . import side_panel, ui_bars
        left, right = room(context, region_w, k)
        l_low = left
        if not ui_bars.strip_on(context):          # 0.24.59 the Layers panel starts as low as the side panel
            l_low = ui_bars.left_inset(context)
        if right < region_w or l_low < left:        # ... and the side panel starts lower: use the whole width
            panel_top = side_panel.frame(region_w, region_h, k)[1]
    sep = 14.0 * k
    from . import ui_bars
    inset = ui_bars.top_inset(context)             # 0.24.59 under Blender's see-through header rows
    corner = 0.0
    try:                                             # 0.24.60 the MECHA LAB / ZBRUSH card in the corner
        from . import zb_ui
        corner = zb_ui.corner_reserve(context, region_w, region_h, k)
    except (ImportError, AttributeError, TypeError, ReferenceError):
        pass
    for full in ((True, False) if panel_top is not None else (False,)):
        r_edge = (region_w - corner) if full else min(right, region_w - corner)
        l_edge = l_low if full else left
        avail = max(300.0 * k, r_edge - l_edge - 24 * k)
        rows = rows_of(gs, avail - 2 * PAD * k, k)
        widths = [sum(_group_width(t, c, k) for t, c in r) + sep * (len(r) - 1) for r in rows]
        width = max(widths) + 2 * PAD * k
        height = len(rows) * ROW * k + (len(rows) - 1) * GAP * k + 2 * PAD * k
        y0 = region_h - TOP * k - inset - height
        if not full or y0 >= panel_top + 6 * k:
            break
    # 0.24.59 centred in the viewport (like the main menu below), moved only as far as the strip / panel need
    x0 = max(l_edge + 8 * k, min((region_w - width) / 2.0, r_edge - 8 * k - width))
    out = [Item('card', x0, y0, width, height)]
    y = y0 + height - PAD * k - ROW * k
    for r, rw in zip(rows, widths):
        x = x0 + (width - rw) / 2.0
        for gi, (title, cells) in enumerate(r):
            if gi:
                out.append(Item('vrule', x + sep / 2 - 0.5 * k, y + 6 * k, 1.0 * k, ROW * k - 12 * k))
                x += sep
            if title:
                tw = (len(title) * 7.0 + 8.0) * k
                out.append(Item('glabel', x, y, tw, ROW * k, title.upper()))
                x += tw + GAP * k
            for c in cells:
                w = _width(c, k)
                it = Item(c['kind'], x, y, w, ROW * k, c['label'], c['icon'], c['on'], True, c['action'],
                          c['data'], c['prop'])
                out.append(it)
                x += w + GAP * k
            x -= GAP * k
        y -= ROW * k + GAP * k
    return out


def on(context):
    from .workspace_ui import pref
    from . import bottom_bar
    return pref('top_bar', True) and bottom_bar.ui_active(context)
