"""0.24.49 Key legend: a small list at the bottom left of the viewport saying what the keys do in the tool
that is on (Alt, Shift, Ctrl, wheel, F, D, RMB, Q / V).  The keys keep their meaning - this only shows it.
Preferences: Key Legend.  Drawn only in MECHA LAB, Object Mode, with a drawing tool on.
"""
from __future__ import annotations

from .i18n import tr as _tr
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
    'DETAIL4': 'cut that area out of the live detail',
    'SDRAW': 'cut out / carve in',
}
EXTRA = {
    'PLATE': ['Wheel (drawing)   profile'],
    'BASE': ['Enter   make the sketch,  Alt+Enter   cut it in'],
    'CBASE': ['Enter   make the sketch,  Alt+Enter   cut it in'],
    'CUT': ['T   targets: auto / selected'],
    'SUBD': ['Drag a point   move it,  drag an outline edge   a new face out of it (Shift: move the edge)',
             'Alt + click a point   remove it,  Ctrl + click an edge   crease on / off',
             'A point dragged onto another   they join (Ctrl while dragging: no snap)'],
    'TUBE': ['Shift + click another part (the curve stays orange)   the part is repeated along the curve'],
    'SPLIT': ['T   targets: auto / selected'],
    'PRESS': ['Hold LMB on a part   a mesh grows out of the surface - taller the longer you hold,  release   keep',
              'Alt + hold LMB   press the stamp in (a cut) - deeper the longer you hold', 'Drag   Base Mesh line, the stamp as its section (as wide as the stamp),  Alt + drag   Line Cut - the stamp as its section, Max deep', 'Start a drag on a line\'s end mark   it goes on from there (turn the view between strokes if you like)', 'Dots beside a made line   Sharp / Round corners,  Move   drag an end ring,  Pick   press on the line anywhere = a new joint,  Section Bend / Each View,  Ends Flat / Round;  sliders   thickness, corner radius, detail (live);  blue joint rings stay until Enter - drag them any time', 'A stroke from one end ring to the other   closes the loop;  a bend near 0 / 45 / 90 / 135 deg catches', 'Shift + draw   your own stamp - Lasso / Rectangle / Circle / Free Draw ... (top bar), Sketch: Enter = the stamp', 'Esc / RMB (holding)   put it back,  [ ] / F   stamp size',
              'Draw: Lasso (top bar)   a drag is the Base Mesh tool\'s lasso - the closed shape becomes a part, Alt as there;  Line   the stamp swept',
              'R + mouse / 3D mouse   turn (Shift fine, Ctrl 5\u00b0),  Shift+R   0\u00b0',
              'Plate (top bar: Armor / Creature)   press   the stamp as a plate on the part,  Line   the stamp\'s section laid along the surface (a stepped rim),  Lasso   that plate tool\'s lasso'],
    'CPATH': ['Tab (dragging)   Extend: brush area / whole section', 'B (dragging)   Back Mask: the far side stays put'],
    'SMOVE': ['Drag from the part   the whole part follows the way (stretches, bends)'],
    'CGREEBLE': ['Drag on a creature   scales (overlapping, staggered rows) or details laid along the line, on the surface',
                 'The window   Scale Parts / Detail Parts (each with its settings),  Pick Part,  Add Selected',
                 'Select a line   change it (Up, Turn, Tilt, Gap, Rows, Stagger ...),  Apply   real geometry',
                 'Shift + draw   your own scale / detail from the outline (a Creature Base Mesh stamp: Puff / Ridge / Pillow)'],
    'FGREEBLE': ['Drag along a creature   feathers along the line, their quills on it, overlapping',
                 'The window   16 feathers, Length / Width, Longer to End / at Start, Length Random',
                 'Select a line   change it;  Enter   Apply (real geometry)'],
    'WDIRT': ['Click a mesh   it becomes dirt (live: its values in the window)', 'Alt + click   back to the shape'],
    'WDUST': ['Click a mesh   it becomes a soft dust layer (live)', 'Alt + click   back to the shape'],
    'WLEAF': ['Click a mesh   leaves piled over it (live)', 'Alt + click   back to the shape'],
    'WSNOW': ['Click a mesh   it becomes snow (live)', 'Alt + click   back to the shape'],
    'PMEASURE': ['Drag on the model   length, horizontal, vertical', 'Shift   straight horizontal / vertical',
                 'X / Y / Z   along that axis', 'Alt + click   the nearest measure gone'],
    'PCUT': ['Drag a line across a part   cut, pins across the cut', 'Shift   the line straight'],
    'FPOP': ['Click a face of a part   it stands out (Height, Taper);  drag   each face passed',
             'Alt + click / drag   off;  the window   Each Face, From Edit Mode Selection, Apply'],
    'BBEVEL': ['Drag along an edge (shown blue)   that much of it cut off - Chamfer / Round, Width wide',
               'Click an edge   all of it;  Ctrl+Z   back'],
    'MOLDING': ['Drag along a mesh   a molding along the line, on its surface (back to the start: a ring)',
                'Shift   the line straight;  click a part   along its edges (its rim, else its sharp edges)',
                'The window   Profile, Width, Height, Offset, Chamfer, Bevel (live)'],
    'RIG': ['Make Rig in the window (Human / Quadruped / Mecha / Chain)   click a mecha part: its joint there   Edit Bones / Pose / Bind'],   # 0.24.241
    'CYLGEN': ['Summon Cylinder at the 3D cursor   select it: the sliders change it   move its Rod along Z to extend it'],
    'BOLT': ['Click a surface: a bolt in a pocket   Alt + click: remove   the sliders change the selected bolts'],
    'TIREGEN': ['Summon Tire / Wheel / Gear at the 3D cursor   select one: its sliders change it live   Array Around: a piece drawn on it, round the axle'],
    'BODYKIT': ['Click a part to pick it - on a one-piece body: the head, a forearm, a finger ... (Shift: more)   R: turn it at its joint   the window: Body Shape / Part sliders',
                'Mirror Pose: the picked side onto the other   Join to One Mesh: one mesh as shaped'],
    'MUSCLE': ['Click the muscle\'s points in order (the window says which)   the last one makes it',
               'Backspace   the last point off;  Esc   cancel;  Enter   keep (Membrane: make it)',
               'The window   Strands, Thickness, Volume, Length, Skin Over All'],
    'MMUSCLE': ['Click its points as Muscle   an artificial muscle / cables',
                'The window   Core, Sleeve holes, End Caps, your own presets'],
    'MHOLE': ['Draw an outline on a part   a panel of holes on it (a frame round it)',
              'The window   Square / Round / Hex / Slots / Diamond / Hex Tiles, Spacing, Hole Size, Frame',
              'Enter   keep the selected panel'],
    'OMASS': ['Draw an outline   a lump of the picked matter in that shape (Rock, Scale, Mushroom, Crystal...)',
              'The window   the matter, Thickness, Back, Lumps, Detail, Pattern, colours (live)',
              'Enter   keep the selected lump'],
    'WING': ['Draw a wing outline   a wing, its veins raised (its root: the point nearest the body)',
             'The window   Dragonfly / Damselfly / Bee / Fly / Lacewing / Cicada, Vein Height, Width, Density',
             'Enter   keep the selected wing'],
    'MEMBRANE': ['Draw over your mesh   a membrane: pinned on the mesh, the rest free',
             'Space   let it fall (cloth) / pause,  Enter   keep (+ Thickness),  Esc   drop',
             'The window   Skin / vein presets, Slack, Gravity, Stretch, Thickness'],
    'FUR': ['Draw on a body   fur grows in the area (a new fur, or another area of the selected one - its own tilt)',
            'Alt + draw   take area away from the selected fur,  New Fur (the window)   a second fur',
            'The window   Density, Length, Lie Down / Flow, Gravity, Curl, Frizz, Clump, Root / Tip Thickness, Color'],
    'GREEBLE': ['Drag on a part   the picked meshes laid one after another along the line, standing on the surface',
                'The window   Pick Part (click meshes, Esc when done),  Add Selected,  Starter Parts',
                'Select a line   change it (Part Size, Gap, Rows, Sink ...),  Apply   real geometry',
                'Shift + draw   your own part from the outline (a Base Mesh stamp: Flat / Chamfer / Bevel / Dome)'],
    'GSCULPT': ['Drag on a part   the brush (the window: Standard, Clay, Clay Buildup, Flat, Move, Smooth, Edge Line, Panel Line, Chamfer, Round)',
                'S   Draw Size at the cursor (move left / right, click = keep),  U   Intensity',
                'Alt + drag   invert (Flat: a raised pad, Edge Line: an inward edge, Panel Line: a rib, Chamfer / Round: taken off),  Shift + drag   Smooth',
                'Ctrl+Z   the last stroke back;  Apply (window)   into the mesh,  Clear   all off'],
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
    if tid in ts.TOOL_BY_ID and (native.startswith('mecha.') or tid in _usage().DOCS):
        return tid                                   # (0.24.233 every tool with a usage entry, click tools too)
    return None


def _legend_allowed(context):
    from .workspace_ui import pref
    from . import bottom_bar
    try:
        return pref('key_legend', True) and bottom_bar.ui_active(context)
    except (AttributeError, KeyError, TypeError):
        return False


def _usage():
    from . import usage_docs
    return usage_docs


def folded(context):
    """0.24.124 (user: "기능 설명은 접을 수 있게") the card folded to its title line (click the title to fold / open).
    0.24.132 folded unless opened."""
    return bool(getattr(getattr(context, 'window_manager', None), 'mch_legend_min', True))


def toggle(context):
    wm = context.window_manager
    if FEATURE[0] is not None:                       # (0.24.235 a section's usage open: its title closes it)
        FEATURE[0] = None
        for w in wm.windows:
            for a in w.screen.areas:
                if a.type == 'VIEW_3D':
                    a.tag_redraw()
        return wm.mch_legend_min
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
    return x0 <= x <= x0 + w and y0 + h - pad - lh - 4 * k <= y <= y0 + h and not search_hit(context, x, y)


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
    return blf.dimensions(0, _tr(s))[0]


TEXT_MAX = 430.0          # 0.24.233 a usage line wider than this (px at scale 1) goes on in the next row


def _wrap(text, width, size):
    """``text`` cut into lines no wider than ``width`` px (at words; a very long word is cut)."""
    if _width(text, size) <= width:
        return [text]
    out, cur = [], ''
    for word in text.split(' '):
        test = (cur + ' ' + word).strip()
        if cur and _width(test, size) > width:
            out.append(cur)
            cur = word
        else:
            cur = test
    if cur:
        out.append(cur)
    return out or [text]


FEATURE = [None]          # 0.24.235 a page section's usage shown in the card ("?" on its title), or None


def show_feature(context, key):
    """The card shows the usage of page section ``key`` (opened); the same "?" again: back to the tool's."""
    FEATURE[0] = None if FEATURE[0] == key else key
    wm = context.window_manager
    if FEATURE[0] is not None:
        wm.mch_legend_min = False
    for w in wm.windows:
        for a in w.screen.areas:
            if a.type == 'VIEW_3D':
                a.tag_redraw()


def card_rows(tid, k, fold):
    """[(kind, key, text)] of the card: kind 'title' / 'head' / 'kv' / 'text'; long texts wrapped."""
    if FEATURE[0] is not None and _usage().feature_rows(FEATURE[0]) is not None:
        rows = _usage().feature_rows(FEATURE[0])
        if fold:
            return rows[:1]
        return _wrapped(rows, k)
    t = ts.TOOL_BY_ID.get(tid)
    name = t[1] if t else tid
    rows = _usage().card_rows(tid, name)
    if rows is None:                                 # (no usage entry yet: the keys as before)
        old = lines(tid)
        rows = [('title', '', old[0])] + [('kv', ln.partition('   ')[0], ln.partition('   ')[2]) for ln in old[1:]]
    if fold:
        return rows[:1]
    return _wrapped(rows, k)


def _wrapped(rows, k):
    size = 12 * k
    out = [rows[0]]
    for kind, key, text in rows[1:]:
        if kind in ('kv', 'text'):
            for n, part in enumerate(_wrap(_tr(text), TEXT_MAX * k, size)):
                out.append((kind, key if n == 0 else '', part))
        else:
            out.append((kind, key, text))
    return out


def _search_w(k):
    return _width(_search_label(), 11 * k) + 18 * k


def _search_label():
    from . import i18n
    return '검색' if i18n.lang() == 'KO' else 'Search'


def search_box(context, k=None):
    """(x, y, w, h) of the card's Search pill (on its title line), or None."""
    b = box(context, k)
    if b is None:
        return None
    k = _k(context) if k is None else k
    x, y, w, h, _rows, _kw = b
    lh, pad = 20 * k, 12 * k
    sw = _search_w(k)
    return x + w - pad - 22 * k - sw, y + h - pad - lh + 1 * k, sw, lh - 2 * k


def search_hit(context, x, y):
    sb = search_box(context)
    return sb is not None and sb[0] <= x <= sb[0] + sb[2] and sb[1] <= y <= sb[1] + sb[3]


_BOX = {'key': None, 'time': 0.0, 'val': None}


def box(context, k=None):
    """0.24.243 (user: "뷰포트 조정이 엄청 렉") kept between redraws: the card's place was worked out again on every
    frame (the dock's and the boxes' layout with it) - now only when something on screen changed."""
    import time
    from . import ui_gpu as G, ui_bars
    region = getattr(context, 'region', None)
    kk = G.ui_factor(context) if k is None else k
    try:
        tid = _stroke_tool(context)
        try:
            rows = tuple(tuple(r) for r in card_rows(tid, kk, folded(context))) if tid is not None else None
        except (IndexError, KeyError, TypeError, AttributeError):
            rows = None
        key = (region.width if region else 0, region.height if region else 0, round(kk, 4), ui_bars.VERSION[0],
               tid, FEATURE[0], folded(context), ui_bars.menu_on(context), ui_bars.left_inset(context),
               round(ui_bars.strip_width(context, kk), 2), rows)
    except (AttributeError, ReferenceError, TypeError, KeyError):
        key = None
    now = time.monotonic()
    if key is not None and key == _BOX['key'] and now - _BOX['time'] < 2.0:
        return _BOX['val']
    val = _box(context, kk)
    _BOX.update(key=key, time=now, val=val)
    return val


def _box(context, k=None):
    """(x, y, w, h, rows, keyw) of the card in region px, or None when no legend shows.
    0.24.59 the bottom left corner, left of the main menu (above the menu and the actions when they are in
    the way on a narrow screen); with the tool strip on the left (Tool Menu Place = Left): right of it."""
    tid = _stroke_tool(context)
    region = getattr(context, 'region', None)
    if tid is None and FEATURE[0] is not None and _legend_allowed(context):
        tid = ''                                     # (0.24.235 a page section's usage: shown in Select too)
    if tid is None:
        return None
    from . import ui_gpu as G, ui_bars
    k = G.ui_factor(context) if k is None else k
    rows = card_rows(tid, k, folded(context))
    size, lh, pad = 12 * k, 20 * k, 12 * k
    title_w = _width(rows[0][2], 13 * k) + 34 * k + _search_w(k) + 2 * pad
    if folded(context):                              # 0.24.124 only the title line (a small card)
        keyw = 0.0
        w = title_w
    else:
        keys = [r[1] for r in rows if r[0] == 'kv' and r[1]]
        keyw = (max(_width(t, size) for t in keys) + 16 * k) if keys else 0.0
        texts = [_width(r[2], size) + (keyw if r[0] == 'kv' else 0.0) for r in rows[1:]]
        w = max([title_w] + texts + [keyw + 120 * k]) + 2 * pad
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
        elif not folded(context):                    # 0.24.226 open, over the row of boxes: above them and the dock
            try:
                from . import bottom_row
                if bottom_row.on(context):
                    y = ui_bars.dock_top(context, k, region.width) + 6 * k
            except (ImportError, AttributeError):
                pass
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
        for i, (kind, key, text) in enumerate(rows):
            ty = y + h - pad - lh * (i + 0.5)
            if kind == 'title':
                G.text(x + pad, ty, text, 13 * k, G.ORANGE)
                # the fold / open mark at the right end of the title (click the title line); Search beside it
                G.text(x + w - pad - 10 * k, ty, '\u00d7' if FEATURE[0] is not None else ('\u25b8' if fold else '\u25be'),
                       13 * k, G.TEXT_DIM)
                sb = search_box(context, k)
                if sb is not None:
                    G.rounded_rect(sb[0], sb[1], sb[2], sb[3], sb[3] / 2, (0.2, 0.205, 0.225, 1.0))
                    G.text(sb[0] + sb[2] / 2, sb[1] + sb[3] / 2, _search_label(), 11 * k, G.TEXT, 'CENTER')
                continue
            if kind == 'head':                       # 0.24.233 a part of the usage: What / How / Keys ...
                G.text(x + pad, ty - 2 * k, text, 10.5 * k, (0.96, 0.78, 0.36, 1.0))
                continue
            if kind == 'text':
                G.text(x + pad, ty, text, size, G.TEXT)
                continue
            alt = key.startswith('Alt')
            G.text(x + pad, ty, key, size, (1.0, 0.45, 0.5, 1.0) if alt else G.TEXT)
            G.text(x + pad + keyw, ty, text, size, G.TEXT_DIM if not alt else G.TEXT)
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


_SEARCH_ITEMS = []


def _search_items(self, context):
    _SEARCH_ITEMS[:] = [(ident, text, '') for ident, text in _usage().search_entries(ts.TOOLS)]
    return _SEARCH_ITEMS


class MCH_OT_usage_search(bpy.types.Operator):
    """0.24.233 Search how to use the tools (type a word - Korean or English: a tool, a key, a setting); the tool
    you pick is switched on and its usage card opened"""
    bl_idname = 'mch.usage_search'
    bl_label = 'Search Usage'
    bl_options = {'INTERNAL'}
    bl_property = 'entry'
    entry: bpy.props.EnumProperty(name='Usage', items=_search_items)

    @classmethod
    def poll(cls, context):
        return getattr(context, 'mode', '') == 'OBJECT'

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        tid = str(self.entry).split('|')[0]
        if tid.startswith('F:'):                         # 0.24.235 a page section: that page, its usage card
            key = tid[2:]
            try:
                bpy.ops.mch.side_page(page=key.partition(':')[0])
            except (RuntimeError, TypeError, AttributeError):
                pass
            FEATURE[0] = None
            show_feature(context, key)
            return {'FINISHED'}
        FEATURE[0] = None
        if tid not in ts.TOOL_BY_ID:
            return {'CANCELLED'}
        from .workspace_ui import activate_mecha_tool
        try:
            activate_mecha_tool(context, tid)
        except (RuntimeError, AttributeError, KeyError) as ex:
            self.report({'WARNING'}, str(ex).splitlines()[0][:120])
        context.window_manager.mch_legend_min = False      # (its card opened)
        for w in context.window_manager.windows:
            for a in w.screen.areas:
                if a.type == 'VIEW_3D':
                    a.tag_redraw()
        self.report({'INFO'}, ts.TOOL_BY_ID[tid][1])
        return {'FINISHED'}


_keymaps = []


def register():
    global _handle
    bpy.utils.register_class(MCH_OT_legend_fold)
    bpy.utils.register_class(MCH_OT_usage_search)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon if wm else None
    if kc is not None:                                 # 0.24.233 Ctrl+Shift+F: search the usage
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        _keymaps.append((km, km.keymap_items.new('mch.usage_search', 'F', 'PRESS', ctrl=True, shift=True)))
    # 0.24.132 (user: "툴 설명은 디폴트로 접혀 있는 게 좋을 것 같아") folded by default: only the title line, a click opens it
    bpy.types.WindowManager.mch_legend_min = bpy.props.BoolProperty(
        name='Key Legend Folded', default=True, description='The key legend card folded to its title (click the title)')
    if not bpy.app.background and _handle is None:
        _handle = bpy.types.SpaceView3D.draw_handler_add(_draw, (), 'WINDOW', 'POST_PIXEL')


def unregister():
    global _handle
    for km, kmi in _keymaps:
        try:
            km.keymap_items.remove(kmi)
        except (ReferenceError, RuntimeError):
            pass
    _keymaps.clear()
    try:
        bpy.utils.unregister_class(MCH_OT_usage_search)
    except RuntimeError:
        pass
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
