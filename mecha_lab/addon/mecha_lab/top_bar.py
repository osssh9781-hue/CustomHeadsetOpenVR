"""0.24.59 Top bar: what the drawing tools share, big and clear at the top middle of the viewport (it replaces the
shape / Sketch / Line / Surface ... buttons of Blender's tool header, which keeps only the Custom PNG picker).

    SHAPE [lasso][curve][rect][circle][ellipse][free][custom]  |  LASSO (the shape's own options)  |  CORNERS
    [Sharp][Round][Chamfer] (Width) (Segments)  |  DRAW [Line] [Sketch] [Slow Line] (Strength) (Radius)  |  LINE
    (Width) [Caps v] [Taper] (Taper) [Pressure] [Attach Ends]  |  [Surface] (Gap) [Through] [Sim] [Preset v]  |
    TARGET [Auto] [Selected] [Active]  |  DEPTH [Through All] [From Surface] (Depth)  |  [Auto Apply]  |  GN EDGE /
    EDGE FINISH / SIDE A · B / EDGE (the cut edge's bevel)  |  [Ortho]

0.24.78 every lasso setting sits here, in the same place for every drawing tool (right after the shapes), and the
bevel of the new cut edges (Cut / Split GN Edge, Edge Finish, Split per side; Base Mesh edge bevel) too.

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
    if tool in ts.SHAPE_TOOLS:
        out += lasso_groups(brush, tool)
    draw = [_cell('seg', label, on, ('mode', key)) for key, label, on in mecha_menu.draw_modes(context)]
    drawing = tool in target_rules.PICKING | target_rules.OWN_ROW - {'CMOVE', 'CPATH', 'SMOVE'}
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
    out += edge_groups(context, tool)
    out += concept_groups(context, tool)
    from .workspace_ui import _ORTHO_LOCK_KEY
    locked = bool(context.workspace and context.workspace.get(_ORTHO_LOCK_KEY, False))
    out.append(('', [_cell('seg', 'Ortho', locked, ('op', 'mch.ortho_lock', {}))]))
    return out


def _mini(label, data, prop, width=130):
    return _cell('mini', label, action=('number',), data=data, prop=prop, width=width)


def _enum_segs(data, prop, items):
    v = getattr(data, prop)
    return [_cell('seg', label, v == ident, ('enum', ident), data, prop) for ident, label in items]


def lasso_groups(brush, tool):
    """0.24.78 LASSO = the drawn shape's own options, CORNERS = the 2D lasso's corners (Lasso / Rectangle) - they
    were in a folded Lasso section of the side panel."""
    shape = brush.shape
    cells = []
    if shape in {'CIRCLE', 'ELLIPSE'}:
        cells.append(_mini('Segments', brush, 'circle_segments', 140))
    elif shape == 'CURVE_LASSO':
        cells.append(_mini('Samples', brush, 'curve_resolution', 130))
    elif shape == 'STROKE':
        cells += [_mini('Spacing', brush, 'stroke_spacing', 130), _mini('Smooth', brush, 'stroke_smooth', 120),
                  _mini('Simplify', brush, 'stroke_simplify', 130)]
        if tool == 'MASK':
            cells.append(_mini('Radius', brush, 'mask_brush_radius', 130))
    elif shape == 'LASSO' and tool not in {'MASK', 'BASE', 'CBASE'}:
        cells.append(_seg('Open Line', brush, 'line_open'))
    elif shape == 'CUSTOM':
        cells += [_mini('Size', brush, 'custom_size', 130), _mini('Rotation', brush, 'custom_rotation', 140),
                  _seg('Rotate With Drag', brush, 'custom_drag_rotate')]
    out = [('Lasso', cells)] if cells else []
    if shape in {'LASSO', 'RECT'}:
        corners = _enum_segs(brush, 'outline_corner', (('NONE', 'Sharp'), ('ROUND', 'Round'), ('CHAMFER', 'Chamfer')))
        if brush.outline_corner != 'NONE':
            corners.append(_mini('Width', brush, 'outline_radius', 130))
            if brush.outline_corner == 'ROUND':
                corners.append(_mini('Segments', brush, 'outline_segments', 140))
        out.append(('Corners', corners))
    return out


FINISH3 = (('NONE', 'Off'), ('CHAMFER', 'Chamfer'), ('BEVEL', 'Bevel'))


def _finish(label, data, kind, width, segments, extra=()):
    """[Off][Chamfer][Bevel] (Width) (Segments on a bevel) for one finish enum."""
    cells = _enum_segs(data, kind, FINISH3)
    if getattr(data, kind) != 'NONE':
        cells.append(_mini('Width', data, width, 130))
        if getattr(data, kind) == 'BEVEL' and segments:
            cells.append(_mini('Segments', data, segments, 140))
        cells += list(extra)
    return (label, cells)


def edge_groups(context, tool):
    """0.24.78 the bevel of the new cut edges: Cut / Split GN Edge (+ Split sides), the Edge Finish under it when GN
    Edge is off (Split: per side), Base Mesh: its edge bevel."""
    scene = context.scene
    out = []
    cut = getattr(scene, 'mch_cut', None)
    if cut is not None and tool in {'CUT', 'SPLIT'}:
        extra = [_cell('drop', '', action=('menu_enum',), data=cut, prop='gn_sides', width=96)] if tool == 'SPLIT' else []
        out.append(_finish('GN Edge', cut, 'gn_finish', 'gn_width', 'gn_segments', extra))
        if cut.gn_finish == 'NONE':
            safe = [_seg('Clamp', cut, 'finish_clamp'), _seg('Crisp', cut, 'finish_crisp')]
            if tool == 'CUT':
                lbl, cells = _finish('Edge Finish', cut, 'edge_finish', 'finish_width', 'finish_segments')
                if cut.edge_finish == 'BEVEL':
                    cells.append(_mini('Profile', cut, 'finish_profile', 120))
                if cut.edge_finish != 'NONE':
                    cells += safe
                out.append((lbl, cells))
            else:
                for side in ('a', 'b'):
                    out.append(_finish(f'Side {side.upper()}', cut, f'side_{side}_finish', f'side_{side}_width',
                                       f'side_{side}_segments'))
                swap = [_cell('seg', '⇄ Swap', action=('op', 'mch.split_swap_sides', {}))]
                out.append(('', swap + (safe if cut.side_a_finish != 'NONE' or cut.side_b_finish != 'NONE' else [])))
    if tool == 'BASE':                           # (Creature Base Mesh: Puff / Ridge / Pillow, no edge bevel)
        from . import base_mesh
        ob = base_mesh.active_live_base(context)
        p = ob.mch_base if ob is not None else base_mesh.scene_defaults(context)
        if p is not None and hasattr(p, 'bevel_sides'):
            cells = [_cell('seg', label, p.profile == pid, ('op', 'mch.set_profile', {'profile': pid}))
                     for pid, label in (('FLAT', 'Flat'), ('CHAMFER', 'Chamfer'), ('BEVEL', 'Bevel'))]
            if p.profile in {'BEVEL', 'CHAMFER'}:
                cells.append(_cell('drop', '', action=('menu_enum',), data=p, prop='bevel_sides', width=104))
                if p.bevel_sides != 'NONE':
                    cells.append(_mini('Width', p, 'bevel_width', 130))
                    if p.profile == 'BEVEL':
                        cells.append(_mini('Segments', p, 'bevel_segments', 140))
            out.append(('Edge', cells))
    return out


CONCEPT_TOOLS = {'CMOVE', 'CPATH', 'SMOVE'}


def concept_groups(context, tool):
    """0.24.79 Concept Move / Path Move / Silhouette Move: the brush settings that filled Blender's tool header
    (method, area, size, hardness, taper, turns, back mask, shape, mirror, generate, follow view) - here, in the
    Mecha bar; the side panel keeps the rest (cuts, knife, auto apply, moves)."""
    st = getattr(context.scene, 'mch_concept', None)
    if st is None or tool not in CONCEPT_TOOLS:
        return []
    out = []
    if tool == 'CPATH':
        method = [_cell('drop', '', action=('menu_enum',), data=st, prop='path_method', width=150)]
        if st.path_method == 'EXTEND':
            method += _enum_segs(st, 'path_area', (('BRUSH', 'Brush'), ('SECTION', 'Whole')))
        out.append(('Method', method))
    brush = [_mini('Size', st, 'radius_world' if st.lock_size else 'radius_px', 140), _seg('Real Size', st, 'lock_size')]
    if tool == 'CMOVE':
        if st.falloff == 'CLAY':
            brush.append(_mini('Hardness', st, 'hardness', 140))
        brush.append(_cell('drop', '', action=('menu_enum',), data=st, prop='falloff', width=110))
        brush.append(_mini('Strength', st, 'strength', 140))
    else:
        brush += [_mini('Hardness', st, 'path_hardness', 140), _mini('Taper', st, 'path_taper', 120),
                  _seg('Follow Turns', st, 'path_turn')]
        if tool == 'CPATH':
            brush.append(_seg('Back Mask', st, 'path_back_mask'))
    brush.append(_cell('drop', '', action=('menu_enum',), data=st, prop='shape', width=110))
    out.append(('Brush', brush))
    more = []
    ob = getattr(context, 'active_object', None)
    try:
        from . import concept_move
        own = ob is not None and concept_move.mirror_reflections(ob)
    except (ImportError, AttributeError, TypeError, ReferenceError):
        own = False
    if not own:                                   # (an object with its own Mirror: that one, nothing to pick)
        more.append(_seg('Mirror X', st, 'mirror_x'))
    more.append(_seg('Generate', st, 'keep_density'))
    if st.keep_density:
        more.append(_seg('Even Out', st, 'even_out'))
    more.append(_seg('Follow View', st, 'follow_view'))
    out.append(('', more))
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
            panel_top = side_panel.frame(region_w, region_h, k, context)[1]
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
