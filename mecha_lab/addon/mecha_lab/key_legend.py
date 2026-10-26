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
    try:
        context = bpy.context
        tid = _stroke_tool(context)
        if tid is None:
            return
        import blf
        ui = context.preferences.system.ui_scale
        font = 0
        size = 11 * ui
        blf.size(font, size)
        x = 14 * ui
        y = 80 * ui
        rows = lines(tid)
        for i, text in enumerate(reversed(rows)):
            top = i == len(rows) - 1
            alt = text.startswith('Alt')
            blf.color(font, *((1.0, 0.62, 0.16) if top else (1.0, 0.4, 0.45) if alt else (0.86, 0.88, 0.92)),
                      0.95 if top else 0.75)
            blf.position(font, x, y + i * size * 1.45, 0)
            blf.draw(font, text)
    except Exception:            # never break viewport drawing
        pass


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
