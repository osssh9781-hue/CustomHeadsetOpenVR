"""0.24.59 Top bar: the settings the drawing tools share, in one dark bar at the top middle of the viewport.

    DRAW  [Line] [Sketch] [Slow Line] (Strength) (Radius)  |  TARGET  [Auto] [Selected] [Active]
          |  DEPTH  [Through All] [From Surface] (Depth)  |  [Auto Apply]

Only what the tool in use has: Line / Sketch where the tool draws lines / sketches, Target for the tools that draw
on a mesh, Depth and Auto Apply for Cut / Split / Box Hide.  The tool's own settings are in the side panel
(``side_panel``), which leaves these out.  Layout only so far (``items``).
"""
from __future__ import annotations

from . import tool_state as ts

ROW = 28.0
GAP = 6.0
GROUP_GAP = 12.0
PAD = 8.0
TOP = 10.0
CUT_LIKE = {'CUT', 'SPLIT', 'HIDE'}


def groups(context, tool):
    """[(title, [cells])]; a cell: (kind, label, on, action, data, prop, width px at size 1)."""
    from . import mecha_menu, target_rules
    scene = context.scene
    brush = getattr(scene, 'mch_brush', None)
    out = []
    draw = [('seg', label, on, ('mode', key), None, '', None) for key, label, on in mecha_menu.draw_modes(context)]
    drawing = tool in target_rules.PICKING | target_rules.OWN_ROW - {'CMOVE', 'CPATH'}
    if brush is not None and drawing:
        draw.append(('seg', 'Slow Line', brush.stab_enable, ('bool',), brush, 'stab_enable', None))
        if brush.stab_enable:
            draw.append(('mini', 'Strength', False, ('number',), brush, 'stab_strength', 150))
            draw.append(('mini', 'Radius', False, ('number',), brush, 'stab_radius', 130))
    if draw:
        out.append(('Draw', draw))
    cut = getattr(scene, 'mch_cut', None)
    if cut is not None and tool in target_rules.PICKING | target_rules.OWN_ROW - {'CMOVE', 'CPATH'}:
        out.append(('Target', [('seg', label, cut.targets == ident, ('enum', ident), cut, 'targets', None)
                               for ident, label in (('AUTO', 'Auto'), ('SELECTED', 'Selected'), ('ACTIVE', 'Active'))]))
    if cut is not None and tool in CUT_LIKE:
        depth = [('seg', label, cut.depth_mode == ident, ('enum', ident), cut, 'depth_mode', None)
                 for ident, label in (('THROUGH', 'Through All'), ('SURFACE', 'From Surface'))]
        if cut.depth_mode == 'SURFACE':
            depth.append(('mini', 'Depth', False, ('number',), cut, 'depth', 140))
        out.append(('Depth', depth))
        st = getattr(scene, 'mch_settings', None)
        if st is not None and tool != 'HIDE':
            out.append(('', [('seg', 'Auto Apply', st.auto_apply, ('bool',), st, 'auto_apply', None)]))
    return out


def items(context, region_w, region_h, k=1.0, left=0.0, right=0.0):
    """The bar as Mecha Menu Items (region px), centred in the room between ``left`` and ``right`` (what the tool
    strip / side panel take)."""
    from .mecha_menu import Item
    tool = ts.effective_tool(context)
    gs = groups(context, tool)
    if not gs:
        return []
    cells = []
    for gi, (title, entries) in enumerate(gs):
        if gi:
            cells.append(('vrule', '', 1.0 * k))
        if title:
            cells.append(('glabel', title.upper(), (len(title) * 7.0 + 6) * k))
        for e in entries:
            w = (e[6] if e[6] else len(e[1]) * 7.0 + 26) * k
            cells.append(('cell', e, w))
    width = sum(c[2] for c in cells) + GAP * k * (len(cells) - 1) + 2 * PAD * k
    room_l, room_r = left, region_w - right
    x0 = max(room_l + 8 * k, (room_l + room_r - width) / 2.0)
    h = ROW * k + 2 * PAD * k
    y0 = region_h - TOP * k - h
    out = [Item('card', x0, y0, width, h)]
    x = x0 + PAD * k
    y = y0 + PAD * k
    for kind, e, w in cells:
        if kind == 'vrule':
            out.append(Item('vrule', x, y + 5 * k, 1.0 * k, ROW * k - 10 * k))
        elif kind == 'glabel':
            out.append(Item('glabel', x, y, w, ROW * k, e))
        else:
            ck, label, on, action, data, prop, _w = e
            out.append(Item(ck, x, y, w, ROW * k, label, '', on, True, action, data, prop))
        x += w + GAP * k
    return out
