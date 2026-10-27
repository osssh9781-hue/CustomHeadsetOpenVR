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


def _draw():
    """0.24.50 readable: a dark rounded card bottom left, sized with the Mecha UI factor."""
    try:
        context = bpy.context
        tid = _stroke_tool(context)
        if tid is None:
            return
        from . import ui_gpu as G
        k = G.ui_factor(context)
        rows = lines(tid)
        size, lh, pad = 12 * k, 20 * k, 12 * k
        import blf
        blf.size(0, size)
        widths = []
        for t in rows:
            key, _sep, what = t.partition('   ')
            widths.append(blf.dimensions(0, key)[0] + 16 * k + blf.dimensions(0, what)[0])
        keyw = max(blf.dimensions(0, t.partition('   ')[0])[0] for t in rows[1:]) + 16 * k
        w = max(widths + [keyw + 120 * k]) + 2 * pad
        h = lh * len(rows) + 2 * pad
        x, y = 14 * k, 90 * k
        try:                                     # 0.24.58 right of the left tool strip
            from . import ui_bars
            x += ui_bars.left_inset(context) + ui_bars.strip_width(context, k)
        except (ImportError, AttributeError, TypeError):
            pass
        G.rounded_rect(x - 1, y - 1, w + 2, h + 2, 12 * k, G.CARD_EDGE)
        G.rounded_rect(x, y, w, h, 12 * k, G.CARD)
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
