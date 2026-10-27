"""0.24.49 Key legend: a small list at the bottom left of the viewport saying what the keys do in the tool
that is on (Alt, Shift, Ctrl, wheel, F, D, RMB, Q / V).  The keys keep their meaning - this only shows it.
Preferences: Key Legend.  Drawn only in MECHA LAB, Object Mode, with a drawing tool on.
"""
from __future__ import annotations

import bpy

from . import tool_state as ts

# what Alt does per drawing tool (from cut_engine's Alt dispatch); tools not listed: Alt does nothing special
ALT = {
    'CUT': 'keep the inside (Line: keep the clicked side)',
    'HIDE': 'show again',
    'MASK': 'erase mask',
    'BASE': 'subtract from the sketch / cut into the mesh',
    'CBASE': 'subtract from the sketch / cut into the mesh',
    'PLATE': 'carve the plate in',
    'CPLATE': 'cut that area out of the live plate',
    'DETAIL': 'cut that area out of the live detail',
    'DETAIL2': 'cut that area out of the live detail',
    'DETAIL3': 'cut that area out of the live detail',
    'SDRAW': 'cut out / carve in',
}
EXTRA = {
    'PLATE': ['Wheel (drawing)   profile'],
    'BASE': ['Enter   make the sketch,  Alt+Enter   cut it in'],
    'CBASE': ['Enter   make the sketch,  Alt+Enter   cut it in'],
    'CUT': ['T   targets: auto / selected'],
    'SPLIT': ['T   targets: auto / selected'],
    'CPATH': ['Tab (dragging)   Extend: brush area / whole section', 'B (dragging)   Back Mask: the far side stays put'],
}
COMMON = [
    'Shift   straight 0/45/90° · square / circle',
    'Ctrl   from the centre',
    'F   brush size     [ ]   line width',
    'D + drag   Concept Move',
    'RMB   tools + actions + shapes     RMB×2 / Esc   exit',
    'Q   Select <-> last tool     V   tool pie',
]
_handle = None


def lines(tool_id):
    t = ts.TOOL_BY_ID.get(tool_id)
    if t is None:
        return []
    out = [t[1].upper()]
    if tool_id in ALT:
        out.append('Alt   ' + ALT[tool_id])
    out += EXTRA.get(tool_id, [])
    return out + COMMON


def _stroke_tool(context):
    """The drawing (lasso / stroke) tool that is on, or None."""
    from .workspace_ui import pref
    if not pref('key_legend', True):
        return None
    from . import bottom_bar
    if not bottom_bar.ui_active(context) or bottom_bar.in_select(context):
        return None
    try:
        tid = ts.effective_tool(context)
    except (AttributeError, KeyError, TypeError):
        return None
    native = ts.native_tool_id(context) or ''
    return tid if native.startswith('mecha.') and tid in ts.TOOL_BY_ID else None


def _width(s, size):
    """Text width as drawn (the same font and size the card uses)."""
    import blf
    blf.size(0, size)
    return blf.dimensions(0, s)[0]


def box(context, k=None):
    """(x, y, w, h, rows, keyw) of the card in region px, or None when no legend shows.
    0.24.59 the bottom left corner, left of the main menu (above the menu and the actions when they are in
    the way on a narrow screen); with the tool strip on the left (Tool Menu Place = Left): right of it."""
    tid = _stroke_tool(context)
    region = getattr(context, 'region', None)
    if tid is None or region is None:
        return None
    from . import ui_gpu as G, ui_bars
    k = G.ui_factor(context) if k is None else k
    rows = lines(tid)
    size, lh, pad = 12 * k, 20 * k, 12 * k
    keyw = max(_width(t.partition('   ')[0], size) for t in rows[1:]) + 16 * k
    what_w = max(_width(t.partition('   ')[2], size) for t in rows[1:])
    # the texts start at the key column, so the card is key column + the widest text (was per row: a short key
    # with a long text ran out of the card)
    w = max(keyw + what_w, _width(rows[0], 13 * k), keyw + 120 * k) + 2 * pad
    h = lh * len(rows) + 2 * pad
    left = ui_bars.left_inset(context)
    if ui_bars.menu_on(context):
        x, y = left + 14 * k, 14 * k
        kk = k * ui_bars.strip_scale()
        mw = ui_bars.menu_layout(region.width, kk, ts.grouped_tools(), left)[4]
        menu_x = max(left + 8 * k, (region.width - mw) / 2.0)
        if x + w + 10 * k > menu_x:                  # no room beside the menu: above it and the actions
            y = ui_bars.dock_top(context, k, region.width) + 6 * k
    else:                                            # 0.24.58 right of the left tool strip, above the toolbar
        x, y = left + 14 * k + ui_bars.strip_width(context, k), 90 * k
    return x, y, w, h, rows, keyw


def _draw():
    """0.24.50 readable: a dark rounded card bottom left, sized with the Mecha UI factor."""
    try:
        context = bpy.context
        from . import ui_gpu as G
        k = G.ui_factor(context)
        b = box(context, k)
        if b is None:
            return
        x, y, w, h, rows, keyw = b
        size, lh, pad = 12 * k, 20 * k, 12 * k
        G.rounded_rect(x - 1, y - 1, w + 2, h + 2, 12 * k, G.card_color(edge=True))
        G.rounded_rect(x, y, w, h, 12 * k, G.card_color())
        for i, t in enumerate(rows):
            ty = y + h - pad - lh * (i + 0.5)
            if i == 0:
                G.text(x + pad, ty, t, 13 * k, G.ORANGE)
                continue
            key, _sep, what = t.partition('   ')
            alt = key.startswith('Alt')
            G.text(x + pad, ty, key, size, (1.0, 0.45, 0.5, 1.0) if alt else G.TEXT)
            G.text(x + pad + keyw, ty, what, size, G.TEXT_DIM if not alt else G.TEXT)
    except Exception:            # never break viewport drawing
        pass
    from . import ui_gpu
    ui_gpu.done()


def register():
    global _handle
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
