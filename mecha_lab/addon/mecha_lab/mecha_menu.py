"""0.24.50 Mecha Menu: the RMB popup drawn by Mecha Lab itself, in the Substance 3D Modeler look - dark rounded
cards side by side at the mouse, big icons, white text, blue for what is on:

  [ tool strip ]  [ <Tool> tool card                ]  [ Actions panel        ]
    Select          Shapes | Stamps  (pill tabs)          Actions   (3 per row)
    recent 5        4-column grid of shape icons          Resolution
    ---             Settings: sliders / pills / toggles   Symmetry  X Y Z
    favorites                                             Repetition
    star, set                                             Visibility, Live

Mouse: hover lights a button, click runs it; drag a slider (Shift = fine), click a slider = type the value,
Ctrl + click = default.  Choosing a tool or an action that needs the mouse closes the menu; shapes, tabs,
settings and toggles keep it open.  RMB / Esc / click outside closes.
Hold Ctrl + Alt (a quarter second, in MECHA LAB): the menu opens and stays while they are held - every click
works without closing it (tools switch in place, Duplicate is in place); letting go closes it.  The layout (``build``) is plain data so
it is tested without a window; ``draw`` only paints it.  Preferences: Mecha UI Size, Classic RMB Popup.
"""
from __future__ import annotations

import time

import bpy
from bpy.props import BoolProperty

from . import tool_state as ts

HOLD_DELAY = 0.25          # Ctrl + Alt held this long opens the menu in hold mode (sooner = a normal Ctrl+Alt use)
from . import ui_gpu as G

ACTIONS = (            # (section, [(label, glyph or png stem, operator, props, needs, closes)])
    ('Actions', [('Duplicate', 'duplicate', 'object.duplicate_move', {}, 'sel', True),
                 ('Join', 'join', 'object.join', {}, 'multi', False),
                 ('Delete', 'delete', 'object.delete', {'use_global': False}, 'sel', False),
                 ('Origin', 'origin', 'mch.object_tidy', {'action': 'ORIGIN_GEOMETRY'}, 'mesh', False),
                 ('Reset Axis', 'axes', 'mch.object_tidy', {'action': 'RESET_AXIS'}, 'mesh', False),
                 ('Smooth', 'smooth', 'object.shade_auto_smooth', {}, 'mesh', False)]),
    ('Resolution', [('Remesh', 'png:remesh', 'mch.one_click_remesh', {}, 'active', True),
                    ('Quad', 'quad', 'mch.quad_remesh', {}, 'active', True),
                    ('Low Poly', 'lowpoly', 'mch.lowpoly_make', {}, 'active', True)]),
    ('Symmetry', [('X', 'X', 'mch.actions_mirror', {'axis': 0}, 'active', False),
                  ('Y', 'Y', 'mch.actions_mirror', {'axis': 1}, 'active', False),
                  ('Z', 'Z', 'mch.actions_mirror', {'axis': 2}, 'active', False)]),
    ('Repetition', [('Radial', 'png:radial', 'tool:RADIAL', {}, '', True),
                    ('Curve Array', 'png:array', 'tool:ARRAY', {}, '', True),
                    ('Radial Sym', 'png:radial_sym', 'tool:RSYM', {}, '', True)]),
    ('Visibility', [('Hide', 'eye_off', 'object.hide_view_set', {'unselected': False}, 'sel', False),
                    ('Show All', 'eye', 'object.hide_view_clear', {}, '', False),
                    ('Isolate', 'isolate', 'view3d.localview', {}, 'sel', True)]),
)


class Item:
    __slots__ = ('kind', 'x', 'y', 'w', 'h', 'label', 'icon', 'on', 'enabled', 'action', 'data', 'prop')

    def __init__(self, kind, x, y, w, h, label='', icon='', on=False, enabled=True, action=None, data=None,
                 prop=''):
        self.kind, self.x, self.y, self.w, self.h = kind, x, y, w, h
        self.label, self.icon, self.on, self.enabled, self.action = label, icon, on, enabled, action
        self.data, self.prop = data, prop

    def hit(self, mx, my):
        return self.x <= mx <= self.x + self.w and self.y <= my <= self.y + self.h

    def clickable(self):
        return self.action is not None and self.enabled


def _needs_ok(context, needs):
    ob = context.active_object
    sel = list(getattr(context, 'selected_objects', []) or [])
    if needs == 'sel':
        return bool(sel)
    if needs == 'multi':
        return sum(1 for o in sel if o.type == 'MESH') > 1
    if needs == 'mesh':
        return any(o.type == 'MESH' for o in sel)
    if needs == 'active':
        return ob is not None and ob.type == 'MESH'
    return True


def _tool_icon(tid):
    t = ts.TOOL_BY_ID.get(tid)
    return 'png:' + t[3] if t else 'png:'


def _middle_kind(context):
    tool = ts.effective_tool(context)
    return 'PROFILE' if tool in {'BASE', 'CBASE'} else 'SHAPES'


def build(context, mx, my, region_w, region_h, S=1.0):
    """The whole menu as a list of Items (region px), placed around the mouse and kept on screen."""
    from . import quick_hud, tool_recent
    pad, gap, r_btn = 12 * S, 10 * S, 48 * S
    strip_w, card_w, act_w = r_btn + 2 * pad, 330 * S, 3 * 64 * S + 2 * pad
    out = []

    # ---- left strip ---------------------------------------------------------------------------------
    strip = []
    y = 0.0
    active = ts.effective_tool(context)
    from . import bottom_bar
    try:
        selecting = bottom_bar.in_select(context)
    except (AttributeError, KeyError, TypeError):
        selecting = False

    def strip_btn(label, icon, action, on=False):
        nonlocal y
        y -= r_btn
        strip.append(Item('button', pad, y, r_btn, r_btn, label, icon, on, True, action))
        y -= 6 * S

    strip_btn('Select / Move', 'arrow', ('op', 'mch.select_move', {}, True), selecting)
    for tid in tool_recent.recent():
        strip_btn(ts.TOOL_BY_ID[tid][1], _tool_icon(tid), ('tool', tid), tid == active and not selecting)
    y -= 4 * S
    strip.append(Item('divider', pad, y, r_btn, 2 * S))
    y -= 10 * S
    for tid in tool_recent.favorites():
        strip_btn(ts.TOOL_BY_ID[tid][1], _tool_icon(tid), ('tool', tid), tid == active and not selecting)
    if tool_recent._valid(active):
        pinned = active in tool_recent.favorites()
        strip_btn('Pin / unpin ' + ts.TOOL_BY_ID[active][1], 'star_on' if pinned else 'star',
                  ('fav_toggle', active), pinned)
    y -= 26 * S
    strip.append(Item('pill', pad - 4 * S, y, r_btn + 8 * S, 24 * S, tool_recent.current_set().title(), '',
                      False, True, ('fav_set',)))
    strip_h = -y + pad

    # ---- middle card ---------------------------------------------------------------------------------
    mid = []
    y = 0.0
    tool = ts.TOOL_BY_ID.get(active)
    title = (tool[1] if tool else 'Mecha') + ' tool'
    y -= 30 * S
    mid.append(Item('title', pad, y, card_w - 2 * pad, 30 * S, title))
    kind = _middle_kind(context)
    tile_w = (card_w - 2 * pad - 3 * 8 * S) / 4.0
    tile_h = tile_w + 16 * S
    tiles = []
    if kind == 'SHAPES':
        wm = context.window_manager
        stamps = bool(getattr(wm, 'mch_show_custom_shapes', False))
        y -= 34 * S
        half = (card_w - 2 * pad - 4 * S) / 2.0
        mid.append(Item('tab', pad, y, half, 28 * S, 'Shapes', '', not stamps, True, ('tab', False)))
        mid.append(Item('tab', pad + half + 4 * S, y, half, 28 * S, 'Stamps', '', stamps, True, ('tab', True)))
        y -= 8 * S
        brush = context.scene.mch_brush
        if stamps:
            from . import cut_presets
            current = getattr(context.scene, 'mch_png_preset', '')
            for stem, name in cut_presets.list_presets()[:16]:
                tiles.append((name, 'file:' + _stamp_path(stem), ('shape', 'CUSTOM', stem),
                              brush.shape == 'CUSTOM' and current == stem))
            if not tiles:
                y -= 24 * S
                mid.append(Item('note', pad, y, card_w - 2 * pad, 24 * S, 'No stamps yet - import a PNG shape'))
        else:
            for sid, label, _d, stem, _f in ts.SHAPES:
                if sid != 'CUSTOM':
                    tiles.append((label, 'png:' + stem, ('shape', sid, ''), brush.shape == sid))
    else:
        from . import base_mesh
        live = base_mesh.active_live_base(context)
        p = live.mch_base if live else base_mesh.scene_defaults(context)
        y -= 8 * S
        for pid, label, _d, stem, _icon in base_mesh.profiles_for(context, live):
            tiles.append((label, 'png:' + stem, ('op', 'mch.set_profile', {'profile': pid}, False), p.profile == pid))
    for i, (label, icon, action, on) in enumerate(tiles):
        c, r = i % 4, i // 4
        mid.append(Item('tile', pad + c * (tile_w + 8 * S), y - (r + 1) * tile_h - r * 8 * S, tile_w, tile_h,
                        label, icon, on, True, action))
    if tiles:
        rows = (len(tiles) + 3) // 4
        y -= rows * tile_h + (rows - 1) * 8 * S
    its = quick_hud.items(context)
    if its:
        y -= 14 * S
        mid.append(Item('section', pad, y - 18 * S, card_w - 2 * pad, 18 * S, 'Settings'))
        y -= 24 * S
        for idx, (data, prop) in enumerate(its):
            rna = data.bl_rna.properties[prop]
            y -= 32 * S
            if rna.type == 'ENUM':
                choices = [(e.identifier, e.name) for e in rna.enum_items]
                if len(choices) <= 4:
                    mid.append(Item('label', pad, y, 100 * S, 28 * S, rna.name or prop))
                    w = (card_w - 2 * pad - 100 * S - 3 * 3 * S) / len(choices)
                    for j, (ident, name) in enumerate(choices):
                        mid.append(Item('seg', pad + 100 * S + j * (w + 3 * S), y, w, 28 * S, name, '',
                                        getattr(data, prop) == ident, True, ('set', idx, ident), data, prop))
                    continue
                mid.append(Item('cycle', pad, y, card_w - 2 * pad, 28 * S, '', '', False, True, ('cycle', idx),
                                data, prop))
            elif rna.type == 'BOOLEAN':
                mid.append(Item('toggle', pad, y, card_w - 2 * pad, 28 * S, rna.name or prop, '',
                                bool(getattr(data, prop)), True, ('cycle', idx), data, prop))
            else:
                mid.append(Item('slider', pad, y, card_w - 2 * pad, 28 * S, '', '', False, True, ('slider', idx),
                                data, prop))
    mid_h = -y + pad

    # ---- actions card --------------------------------------------------------------------------------
    act = []
    y = 0.0
    ob = context.active_object
    y -= 26 * S
    act.append(Item('title', pad, y, act_w - 2 * pad, 26 * S, G.fit(ob.name, 13 * S, act_w - 2 * pad)
                    if ob is not None else 'Nothing selected'))
    from . import actions_menu
    m = actions_menu.mirror_mod(ob) if ob is not None and ob.type == 'MESH' else None
    bw, bh = 64 * S, 58 * S
    sections = list(ACTIONS) + ([('Live', _live(context))] if _live(context) else [])
    for sec, buttons in sections:
        y -= 10 * S
        act.append(Item('section', pad, y - 16 * S, act_w - 2 * pad, 16 * S, sec))
        y -= 20 * S
        for i, (label, icon, op, props, needs, closes) in enumerate(buttons):
            c = i % 3
            if c == 0:
                y -= bh
            on = sec == 'Symmetry' and bool(m and m.use_axis[props['axis']])
            if op.startswith('tool:'):
                on = active == op[5:]
                action = ('tool', op[5:])
            else:
                action = ('op', op, props, closes)
            act.append(Item('button', pad + c * bw, y, bw - 4 * S, bh - 4 * S, label, icon, on,
                            _needs_ok(context, needs), action))
    act_h = -y + pad

    # ---- place the three cards around the mouse --------------------------------------------------------
    total_w = strip_w + gap + card_w + gap + act_w
    height = max(strip_h, mid_h, act_h)
    left = min(max(mx - strip_w - gap - card_w / 2.0, 8 * S), max(8 * S, region_w - total_w - 8 * S))
    top = min(max(my + height / 2.0, height + 8 * S), region_h - 8 * S)
    for x0, w, h, items in ((left, strip_w, strip_h, strip), (left + strip_w + gap, card_w, mid_h, mid),
                            (left + strip_w + gap + card_w + gap, act_w, act_h, act)):
        out.append(Item('card', x0, top - h, w, h))
        for it in items:
            it.x += x0
            it.y += top
            out.append(it)
    return out


def _stamp_path(stem):
    from . import cut_presets
    if cut_presets.is_builtin(stem):
        return G.icon_path('shape_' + stem[len(cut_presets.BUILTIN_PREFIX):].lower())
    info = cut_presets._INDEX.get(stem)
    if info is None:
        return ''
    thumb = cut_presets._small_thumb(cut_presets.preset_folder() / info[2])
    return str(thumb) if thumb is not None else ''


def _live(context):
    from . import actions_menu
    out = []
    for _op, label, _icon, _props in actions_menu._live_rows(context):
        glyph = 'check' if 'Apply' in label and 'Modifiers' not in label else 'cross' if 'Remove' in label \
            else 'eye' if 'Show' in label else 'stack'
        out.append((label, glyph, _op, {}, '', False))
    return out


# --- clicks --------------------------------------------------------------------------------------------------

def run(context, item, ctrl=False, hold=False):
    """Do what a click on ``item`` means.  Returns True when the menu should close.  ``hold`` (Ctrl + Alt held):
    nothing closes it - a tool is switched in place, mouse-driven actions run straight away (Duplicate in place)."""
    from . import quick_hud, tool_recent
    a = item.action
    kind = a[0]
    if kind == 'tool':
        bpy.ops.mch.set_tool(tool=a[1])
        return not hold
    if kind == 'shape':
        bpy.ops.mch.set_shape(shape=a[1], preset=a[2])
        return False
    if kind == 'tab':
        context.window_manager.mch_show_custom_shapes = a[1]
        return False
    if kind == 'fav_toggle':
        tool_recent.toggle_favorite(a[1])
        return False
    if kind == 'fav_set':
        ids = [s[0] for s in tool_recent.SETS]
        i = ids.index(tool_recent.current_set())
        context.window_manager.mch_fav_set = ids[(i + 1) % len(ids)]
        return False
    if kind in {'set', 'cycle', 'slider'}:
        its = quick_hud.items(context)
        if a[1] >= len(its):
            return False
        data, prop = its[a[1]]
        if ctrl:
            quick_hud.reset(data, prop)
        elif kind == 'set':
            setattr(data, prop, a[2])
        elif kind == 'cycle':
            quick_hud.step_choice(data, prop)
        elif hold:
            return False                                            # no typing while the keys are held
        else:
            context.window_manager.mch_hud_edit = str(a[1])        # click on a slider: type the value
            return 'TYPE'
        _undo('Mecha ' + prop)
        return False
    if kind == 'op':
        _op, idname, props, closes = a
        if hold and idname == 'object.duplicate_move':
            idname = 'object.duplicate'                             # in place: the mouse is busy with the menu
        mod, name = idname.split('.')
        fn = getattr(getattr(bpy.ops, mod), name)
        try:
            fn('INVOKE_DEFAULT' if closes and not hold else 'EXEC_DEFAULT', **props)
        except RuntimeError as ex:
            print('Mecha Menu:', idname, ex)
        return bool(closes) and not hold
    return False


def _undo(message):
    try:
        bpy.ops.ed.undo_push(message=message)
    except RuntimeError:
        pass


# --- drawing -------------------------------------------------------------------------------------------------

def _icon(icon, x, y, size, color, alpha=1.0):
    if icon.startswith('png:'):
        if not G.image(G.icon_path(icon[4:]), x, y, size, alpha):
            G.glyph('', x, y, size, color)
    elif icon.startswith('file:'):
        if not G.image(icon[5:], x, y, size, alpha):
            G.glyph('', x, y, size, color)
    elif icon:
        G.glyph(icon, x, y, size, color, max(1.5, size / 16.0))


def draw(items, hover, S, context):
    from . import quick_hud
    r = 10 * S
    for it in items:
        dim = 1.0 if it.enabled else 0.45
        col_t = (G.TEXT[0], G.TEXT[1], G.TEXT[2], dim)
        hot = it is hover and it.clickable()
        if it.kind == 'card':
            G.rounded_rect(it.x - 1, it.y - 1, it.w + 2, it.h + 2, 14 * S, G.CARD_EDGE)
            G.rounded_rect(it.x, it.y, it.w, it.h, 14 * S, G.CARD)
        elif it.kind == 'title':
            G.text(it.x + 2 * S, it.y + it.h / 2, it.label, 15 * S, G.TEXT)
        elif it.kind in {'section', 'note'}:
            G.text(it.x + it.w / 2, it.y + it.h / 2, it.label, 11 * S, G.TEXT_DIM, 'CENTER')
            if it.kind == 'section':
                lw = it.w / 2 - 50 * S
                if lw > 6 * S:
                    G.lines([((it.x, it.y + it.h / 2), (it.x + lw, it.y + it.h / 2)),
                             ((it.x + it.w - lw, it.y + it.h / 2), (it.x + it.w, it.y + it.h / 2))],
                            (0.3, 0.31, 0.34, 1.0), 1.0 * S)
        elif it.kind == 'divider':
            G.rounded_rect(it.x + 6 * S, it.y, it.w - 12 * S, it.h, it.h / 2, (0.3, 0.31, 0.34, 1.0))
        elif it.kind == 'button':
            bg = G.ACCENT if it.on else (G.BTN_HOVER if hot else G.BTN)
            G.rounded_rect(it.x, it.y, it.w, it.h, r, bg)
            has_label = it.h > it.w * 0.8 and it.w > 52 * S          # action buttons: icon + name under it
            size = (it.h - 26 * S) if has_label else it.h * 0.68
            ix = it.x + (it.w - size) / 2
            iy = it.y + (it.h - size) / 2 + (8 * S if has_label else 0)
            _icon(it.icon, ix, iy, size, col_t, dim)
            if has_label:
                G.text(it.x + it.w / 2, it.y + 10 * S, G.fit(it.label, 10 * S, it.w - 4 * S), 10 * S, col_t, 'CENTER')
        elif it.kind == 'tile':
            bg = (0.9, 0.9, 0.92, 1.0) if it.on else (G.BTN_HOVER if hot else G.BTN)
            G.rounded_rect(it.x, it.y, it.w, it.h, r, bg)
            size = it.w * 0.62
            _icon(it.icon, it.x + (it.w - size) / 2, it.y + it.h - size - 6 * S, size, col_t)
            G.text(it.x + it.w / 2, it.y + 10 * S, G.fit(it.label, 10 * S, it.w - 4 * S), 10 * S,
                   (0.1, 0.1, 0.12, 1.0) if it.on else G.TEXT, 'CENTER')
        elif it.kind in {'tab', 'seg', 'pill'}:
            bg = G.ACCENT if it.on else (G.BTN_HOVER if hot else G.BTN)
            G.rounded_rect(it.x, it.y, it.w, it.h, it.h / 2, bg)
            G.text(it.x + it.w / 2, it.y + it.h / 2, G.fit(it.label, 11 * S, it.w - 8 * S), 11 * S, G.TEXT, 'CENTER')
        elif it.kind == 'label':
            G.text(it.x, it.y + it.h / 2, G.fit(it.label, 11 * S, it.w - 4 * S), 11 * S, G.TEXT_DIM)
        elif it.kind == 'toggle':
            G.text(it.x, it.y + it.h / 2, it.label, 12 * S, G.TEXT)
            sw, sh = 40 * S, 20 * S
            sx, sy = it.x + it.w - sw, it.y + (it.h - sh) / 2
            G.rounded_rect(sx, sy, sw, sh, sh / 2, G.ACCENT if it.on else G.TRACK)
            kx = sx + (sw - sh + 2 * S if it.on else 2 * S)
            G.rounded_rect(kx, sy + 2 * S, sh - 4 * S, sh - 4 * S, (sh - 4 * S) / 2, G.TEXT)
        elif it.kind in {'slider', 'cycle'}:
            data, prop = it.data, it.prop
            try:
                txt = quick_hud.value_text(data, prop)
            except (AttributeError, KeyError, ReferenceError):
                continue
            name, _sep, val = txt.partition('  ')
            G.rounded_rect(it.x, it.y, it.w, it.h, it.h / 2, G.BTN_HOVER if hot else G.TRACK)
            if it.kind == 'slider':
                frac = _fraction(data, prop)
                if frac > 0.0:
                    G.rounded_rect(it.x, it.y, max(it.h, it.w * frac), it.h, it.h / 2, (0.22, 0.38, 0.72, 1.0))
            G.text(it.x + 12 * S, it.y + it.h / 2, name, 12 * S, G.TEXT)
            G.text(it.x + it.w - 12 * S, it.y + it.h / 2, val, 12 * S, G.TEXT, 'RIGHT')
    if hover is not None and hover.clickable() and hover.kind == 'button' and hover.w <= 52 * S:
        # strip buttons have no room for a name: show it beside them
        G.rounded_rect(hover.x + hover.w + 8 * S, hover.y + hover.h / 2 - 13 * S,
                       G.text(-9999, -9999, hover.label, 12 * S) + 20 * S, 26 * S, 8 * S, (0.05, 0.05, 0.06, 0.95))
        G.text(hover.x + hover.w + 18 * S, hover.y + hover.h / 2, hover.label, 12 * S, G.TEXT)


def _fraction(data, prop):
    rna = data.bl_rna.properties[prop]
    v = getattr(data, prop)
    lo, hi = (rna.hard_min, rna.hard_max) if rna.type == 'INT' else (rna.soft_min, rna.soft_max)
    if rna.type == 'INT' and hi - lo > 64:
        lo, hi = rna.soft_min, rna.soft_max
    span = hi - lo
    return max(0.0, min(1.0, (v - lo) / span)) if 0 < span < 1e7 else 0.0


# --- the operator ------------------------------------------------------------------------------------------

class MCH_OT_mecha_menu(bpy.types.Operator):
    """Mecha Menu at the mouse: tools, the tool's shapes and settings, actions on the selection"""
    bl_idname = 'mch.mecha_menu'
    bl_label = 'Mecha Menu'
    bl_options = {'INTERNAL'}
    hold: BoolProperty(default=False, options={'SKIP_SAVE'},
                       description='Open while Ctrl + Alt are held; clicks never close it, letting go does')

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and context.region is not None

    def invoke(self, context, event):
        self.region = context.region
        self.S = G.ui_factor(context, self.region)
        self.mouse = (event.mouse_region_x, event.mouse_region_y)
        self.items = build(context, *self.mouse, self.region.width, self.region.height, self.S)
        self.hover = None
        self.drag = None
        self._handle = bpy.types.SpaceView3D.draw_handler_add(self._draw, (), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def _draw(self):
        try:
            if bpy.context.region is None or bpy.context.region.as_pointer() != self.region.as_pointer():
                return
            draw(self.items, self.hover, self.S, bpy.context)
        except Exception as ex:          # never break viewport drawing
            print('Mecha Menu draw:', ex)
        G.done()

    def _rebuild(self, context):
        self.items = build(context, *self.mouse, self.region.width, self.region.height, self.S)

    def _finish(self, context):
        if self._handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            self._handle = None
        if context.area:
            context.area.tag_redraw()

    def _at(self, x, y):
        return next((it for it in reversed(self.items) if it.kind != 'card' and it.hit(x, y)), None)

    def _inside(self, x, y):
        return any(it.kind == 'card' and it.hit(x, y) for it in self.items)

    def modal(self, context, event):
        from . import quick_hud
        x, y = event.mouse_region_x, event.mouse_region_y
        if context.area:
            context.area.tag_redraw()
        if self.drag is not None:
            it, x0, v0, moved = self.drag
            if event.type == 'MOUSEMOVE':
                if abs(x - x0) > 3:
                    moved = True
                if moved:
                    v = quick_hud.drag_value(it.data, it.prop, v0, x - x0, fine=event.shift)
                    if v != getattr(it.data, it.prop):
                        setattr(it.data, it.prop, v)
                self.drag = (it, x0, v0, moved)
                return {'RUNNING_MODAL'}
            if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                self.drag = None
                if moved:
                    _undo('Mecha ' + it.prop)
                    return {'RUNNING_MODAL'}
                if run(context, it, event.ctrl and not self.hold, self.hold) == 'TYPE':
                    self._finish(context)
                    bpy.ops.wm.call_panel(name='MCH_PT_quick_value', keep_open=False)
                    return {'FINISHED'}
                self._rebuild(context)
                return {'RUNNING_MODAL'}
            if event.type in {'ESC', 'RIGHTMOUSE'}:
                setattr(it.data, it.prop, v0)
                self.drag = None
            return {'RUNNING_MODAL'}
        if event.type == 'MOUSEMOVE':
            self.hover = self._at(x, y)
            return {'RUNNING_MODAL'}
        if self.hold and event.type in {'LEFT_CTRL', 'RIGHT_CTRL', 'LEFT_ALT', 'RIGHT_ALT'} \
                and event.value == 'RELEASE':
            self._finish(context)                 # hold mode: letting go of Ctrl / Alt closes it
            return {'FINISHED'}
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            self._finish(context)
            return {'CANCELLED'}
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            it = self._at(x, y)
            if it is None or not it.clickable():
                if not self._inside(x, y) and not self.hold:
                    self._finish(context)
                    return {'CANCELLED'}
                return {'RUNNING_MODAL'}
            if it.kind == 'slider':
                self.drag = (it, x, getattr(it.data, it.prop), False)
                return {'RUNNING_MODAL'}
            closes = it.action[0] == 'op' and it.action[3]
            if (closes or it.action[0] == 'tool') and not self.hold:
                self._finish(context)
                run(context, it, event.ctrl)
                return {'FINISHED'}
            try:
                run(context, it, event.ctrl and not self.hold, self.hold)
            except (RuntimeError, AttributeError, TypeError, ReferenceError) as ex:
                print('Mecha Menu:', ex)
            self._rebuild(context)
            self.hover = self._at(x, y)
            return {'RUNNING_MODAL'}
        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM'}:
            return {'PASS_THROUGH'}         # the view can still be turned behind it
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        self._finish(context)


class MCH_OT_mecha_hold_gate(bpy.types.Operator):
    """Ctrl + Alt held a moment (MECHA LAB): the Mecha Menu stays open while they are held"""
    bl_idname = 'mch.mecha_hold_gate'
    bl_label = 'Mecha Menu (hold Ctrl + Alt)'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        from . import bottom_bar
        from .workspace_ui import pref
        return (pref('hold_menu', True) and context.area is not None and context.area.type == 'VIEW_3D'
                and bottom_bar.ui_active(context))

    def invoke(self, context, event):
        self.t0 = time.monotonic()
        self.keys = {'ctrl': True, 'alt': True}
        self.timer = context.window_manager.event_timer_add(0.03, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _stop(self, context):
        if self.timer is not None:
            context.window_manager.event_timer_remove(self.timer)
            self.timer = None

    def modal(self, context, event):
        if event.type in {'LEFT_CTRL', 'RIGHT_CTRL'} and event.value == 'RELEASE':
            self.keys['ctrl'] = False
        elif event.type in {'LEFT_ALT', 'RIGHT_ALT'} and event.value == 'RELEASE':
            self.keys['alt'] = False
        if not all(self.keys.values()):
            self._stop(context)
            return {'FINISHED'}
        if event.type == 'TIMER':
            if time.monotonic() - self.t0 >= HOLD_DELAY:
                self._stop(context)
                bpy.ops.mch.mecha_menu('INVOKE_DEFAULT', hold=True)
                return {'FINISHED'}
            return {'RUNNING_MODAL'}
        if event.value in {'PRESS', 'CLICK_DRAG'} and event.type not in {'LEFT_CTRL', 'RIGHT_CTRL', 'LEFT_ALT',
                                                                         'RIGHT_ALT', 'MOUSEMOVE'}:
            self._stop(context)                    # a click / key before the delay: a normal Ctrl + Alt use
            return {'FINISHED', 'PASS_THROUGH'}
        return {'PASS_THROUGH'}

    def cancel(self, context):
        self._stop(context)


def open_menu(context):
    """Open the Mecha Menu (False if it could not be opened here)."""
    try:
        return bpy.ops.mch.mecha_menu('INVOKE_DEFAULT') == {'RUNNING_MODAL'}
    except RuntimeError:
        return False


def use_menu():
    from .workspace_ui import pref
    return not bpy.app.background and not pref('classic_rmb_popup', False)


CLASSES = (MCH_OT_mecha_menu, MCH_OT_mecha_hold_gate)
_keymaps = []
HOLD_KEYS = (('LEFT_ALT', {'ctrl': True}), ('RIGHT_ALT', {'ctrl': True}),
             ('LEFT_CTRL', {'alt': True}), ('RIGHT_CTRL', {'alt': True}))


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon if wm else None
    if kc is not None:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        for key, mods in HOLD_KEYS:                 # whichever of the two goes down second
            _keymaps.append((km, km.keymap_items.new('mch.mecha_hold_gate', key, 'PRESS', **mods)))


def unregister():
    for km, item in _keymaps:
        try:
            km.keymap_items.remove(item)
        except (ReferenceError, RuntimeError):
            pass
    _keymaps.clear()
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
    G.free_textures()
