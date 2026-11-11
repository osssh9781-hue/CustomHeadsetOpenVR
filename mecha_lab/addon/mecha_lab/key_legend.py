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
    'TUBE': ['Shift + click another part (the curve stays orange)   the part is repeated along the curve'],
    'SPLIT': ['T   targets: auto / selected'],
    'PRESS': ['Hold LMB on a part   a mesh grows out of the surface - taller the longer you hold,  release   keep',
              'Alt + hold LMB   press the stamp in (a cut) - deeper the longer you hold', 'Drag   Base Mesh line, the stamp as its section (as wide as the stamp),  Alt + drag   Line Cut - the stamp as its section, Max deep', 'Start a drag on a line\'s end mark   it goes on from there (turn the view between strokes if you like)', 'Dots beside a made line   Sharp / Round corners,  Move   drag an end ring,  Pick   press on the line anywhere = a new joint,  Section Bend / Each View,  Ends Flat / Round;  sliders   thickness, corner radius, detail (live);  blue joint rings stay until Enter - drag them any time', 'A stroke from one end ring to the other   closes the loop;  a bend near 0 / 45 / 90 / 135 deg catches', 'Shift + draw   your own stamp - Lasso / Rectangle / Circle / Free Draw ... (top bar), Sketch: Enter = the stamp', 'Esc / RMB (holding)   put it back,  [ ] / F   stamp size',
              'Draw: Lasso (top bar)   a drag is the Base Mesh tool\'s lasso - the closed shape becomes a part, Alt as there;  Line   the stamp swept',
              'R + mouse / 3D mouse   turn (Shift fine, Ctrl 5\u00b0),  Shift+R   0\u00b0',
              'Plate (top bar: Armor / Creature)   press   the stamp as a plate on the part,  Line   the stamp\'s section laid along the surface (a stepped rim),  Lasso   that plate tool\'s lasso'],
    'CPATH': ['Tab (dragging)   Extend: brush area / whole section', 'B (dragging)   Back Mask: the far side stays put'],
    'SMOVE': ['Drag from the part   the whole part follows the way (stretches, bends)'],
    'SMART': ['LMB on a part   hold it (a ring on its origin),  LMB on a surface   its origin goes there - same rotation and size',
              '3D mouse   turn it about its origin (Turntable = round the world\'s up like the view / View / World axes, Speed, Invert - panel / top bar),  Push: Free (left / right, forward / back on the ground, push down / pull up = down / up; X Y Z toggles) / Normal   slide it',
              'S (holding)   Smart Size: the 3D mouse scales the part about its origin - push x / y / z = that axis (Local / World), twist = all;  S again   move',
              'Enter / Space / RMB   keep (one undo step),  Esc   put it back;  MMB / wheel   the view'],
    'CDRAPE': ['Lasso on a mesh   a loose cloth over that region', 'Space   drape / pause,  Enter   keep the cloth,  Esc   drop it'],
    'ZONE': ['Lasso on a Mech / Creature part   a zone (top bar: Paint / Split)',
             'Sketch: Enter   make the zone,  Esc   back to Select'],
    'WLINES': ['Drag   a wrinkle line,  drag a point   move it', 'Shift + click   add a point,  Ctrl + click   remove it,  X   remove the line',
               'Space   simulate / pause,  Enter   keep,  Esc   back'],
}
COMMON = [
    'Shift   straight 0/45/90° · square / circle',
    'Ctrl   from the centre',
    'F   brush size     [ ]   line width',
    'D + drag   Concept Move     E   Smart Move (the part under the mouse / the selected one)',
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


def folded(context):
    """0.24.124 (user: "기능 설명은 접을 수 있게") the card folded to its title line (click the title to fold / open).
    0.24.132 folded unless opened."""
    return bool(getattr(getattr(context, 'window_manager', None), 'mch_legend_min', True))


def toggle(context):
    wm = context.window_manager
    wm.mch_legend_min = not bool(getattr(wm, 'mch_legend_min', True))
    for w in wm.windows:
        for a in w.screen.areas:
            if a.type == 'VIEW_3D':
                a.tag_redraw()
    return wm.mch_legend_min


def title_hit(context, x, y):
    """Is region point (x, y) on the card's title line (the fold / open button)?"""
    b = box(context)
    if b is None:
        return False
    x0, y0, w, h, rows, _keyw = b
    k = _k(context)
    lh, pad = 20 * k, 12 * k
    return x0 <= x <= x0 + w and y0 + h - pad - lh - 4 * k <= y <= y0 + h


def card_hit(context, x, y):
    """Is region point (x, y) anywhere on the card?  (a press there is the card's, never a stroke)"""
    b = box(context)
    if b is None:
        return False
    x0, y0, w, h, _rows, _keyw = b
    return x0 <= x <= x0 + w and y0 <= y <= y0 + h


def _k(context):
    from . import ui_gpu as G
    return G.ui_factor(context)


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
    if tid is None:
        return None
    from . import ui_gpu as G, ui_bars
    k = G.ui_factor(context) if k is None else k
    rows = lines(tid)
    size, lh, pad = 12 * k, 20 * k, 12 * k
    if folded(context):                              # 0.24.124 only the title line (a small card)
        rows = rows[:1]
        keyw = 0.0
        w = _width(rows[0], 13 * k) + 34 * k + 2 * pad
        h = lh + 2 * pad
    else:
        keyw = max(_width(t.partition('   ')[0], size) for t in rows[1:]) + 16 * k
        what_w = max(_width(t.partition('   ')[2], size) for t in rows[1:])
        # the texts start at the key column, so the card is key column + the widest text (was per row: a short key
        # with a long text ran out of the card)
        w = max(keyw + what_w, _width(rows[0], 13 * k), keyw + 120 * k) + 2 * pad
        h = lh * len(rows) + 2 * pad
    left = ui_bars.left_inset(context)
    if region is None:                               # (no viewport region: the old bottom left place)
        x, y = left + 14 * k, 90 * k
    elif ui_bars.menu_on(context):
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
        fold = folded(context)
        for i, t in enumerate(rows):
            ty = y + h - pad - lh * (i + 0.5)
            if i == 0:
                G.text(x + pad, ty, t, 13 * k, G.ORANGE)
                # the fold / open mark at the right end of the title (click the title line)
                G.text(x + w - pad - 10 * k, ty, '\u25b8' if fold else '\u25be', 13 * k, G.TEXT_DIM)
                continue
            key, _sep, what = t.partition('   ')
            alt = key.startswith('Alt')
            G.text(x + pad, ty, key, size, (1.0, 0.45, 0.5, 1.0) if alt else G.TEXT)
            G.text(x + pad + keyw, ty, what, size, G.TEXT_DIM if not alt else G.TEXT)
    except Exception:            # never break viewport drawing
        pass
    from . import ui_gpu
    ui_gpu.done()


class MCH_OT_legend_fold(bpy.types.Operator):
    """Fold / open the key legend card (click its title line)"""
    bl_idname = 'mch.legend_fold'
    bl_label = 'Fold Key Legend'
    bl_options = {'INTERNAL'}

    def execute(self, context):
        toggle(context)
        return {'FINISHED'}


def register():
    global _handle
    bpy.utils.register_class(MCH_OT_legend_fold)
    # 0.24.132 (user: "툴 설명은 디폴트로 접혀 있는 게 좋을 것 같아") folded by default: only the title line, a click opens it
    bpy.types.WindowManager.mch_legend_min = bpy.props.BoolProperty(
        name='Key Legend Folded', default=True, description='The key legend card folded to its title (click the title)')
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
    try:
        del bpy.types.WindowManager.mch_legend_min
    except (AttributeError, RuntimeError):
        pass
    try:
        bpy.utils.unregister_class(MCH_OT_legend_fold)
    except (RuntimeError, ValueError):
        pass
