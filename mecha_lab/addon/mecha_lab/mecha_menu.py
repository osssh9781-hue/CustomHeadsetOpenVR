"""0.24.50 Mecha Menu: the RMB popup drawn by Mecha Lab itself, in the Substance 3D Modeler look - dark rounded
cards side by side at the mouse, big icons, white text, blue for what is on:

  [ tool strip ]  [ <Tool> tool card                ]  [ Actions panel        ]
    Select          Shapes | Stamps  (pill tabs)          Actions   (3 per row)
    recent 5        4-column grid of shape icons          Resolution
    ---             Settings: sliders / pills / toggles   Symmetry  X Y Z
    favorites                                             Repetition
    star, set                                             Visibility, Live

Mouse: hover lights a button, click runs it; drag a slider (Shift = fine), click a slider = type the value,
Ctrl + click = default.  0.24.52: a click never closes it (a tool switches in place, Duplicate copies in place);
moving the mouse off the menu closes it, so do RMB / Esc / a click outside.
Middle click (press and let go without moving, in MECHA LAB) opens it too; a middle drag still orbits.
Hold Ctrl + Alt (a quarter second, in MECHA LAB): the menu opens and stays while they are held - every click
works without closing it (tools switch in place, Duplicate is in place); letting go closes it.  The layout (``build``) is plain data so
it is tested without a window; ``draw`` only paints it.  Size: the − / + under the tool strip or Ctrl + wheel
over the menu (= Preferences / sidebar Icon Size > Viewport Popups, also the Quick HUD and key legend).
"""
from __future__ import annotations

import time

import bpy
from bpy.props import BoolProperty

from . import tool_state as ts

_OPEN = [False]           # a Mecha Menu is open (the middle-click gate must not open a second one)
HOLD_DELAY = 0.25          # Ctrl + Alt held this long opens the menu in hold mode (sooner = a normal Ctrl+Alt use)
from . import ui_gpu as G

ACTIONS = (            # (section, [(label, glyph or png stem, operator, props, needs, closes)])
    ('Actions', [('Duplicate', 'duplicate', 'object.duplicate_move', {}, 'sel', True),
                 ('Join', 'join', 'object.join', {}, 'multi', False),
                 ('Delete', 'delete', 'object.delete', {'use_global': False}, 'sel', False),
                 ('Origin', 'origin', 'mch.object_tidy', {'action': 'ORIGIN_GEOMETRY'}, 'mesh', False),
                 ('Reset Axis', 'axes', 'mch.object_tidy', {'action': 'RESET_AXIS'}, 'mesh', False)]),
    ('Shading', [('Flat', 'shade_flat', 'object.shade_flat', {}, 'mesh', False),
                 ('Auto Smooth', 'shade_auto', 'object.shade_auto_smooth', {}, 'mesh', False),
                 ('Smooth', 'shade_smooth', 'object.shade_smooth', {}, 'mesh', False)]),
    ('Resolution', [('Remesh', 'png:remesh', 'mch.one_click_remesh', {}, 'active', True),
                    ('Quad', 'quad', 'mch.quad_remesh', {}, 'active', True),
                    ('Low Poly', 'lowpoly', 'mch.lowpoly_make', {}, 'active', True)]),
    ('Symmetry', [('Mirror X', 'X', 'mch.actions_mirror', {'axis': 0}, 'active', False),
                  ('Mirror Y', 'Y', 'mch.actions_mirror', {'axis': 1}, 'active', False),
                  ('Mirror Z', 'Z', 'mch.actions_mirror', {'axis': 2}, 'active', False),
                  ('Radial', 'radial', 'mch.symmetry_mode', {'mode': '@RADIAL'}, 'active', False),
                  ('Kaleido', 'kaleido', 'mch.symmetry_mode', {'mode': '@KALEIDO'}, 'active', False),
                  ('Symmetry Card', 'card', 'mch.symmetry_card', {}, 'active', False)]),
    ('Groups', [('Group', 'group', 'mch.group', {}, 'sel', False),
                ('Ungroup', 'ungroup', 'mch.group_action', {'action': 'UNGROUP'}, 'group', False),
                ('Merge', 'merge', 'mch.group_action', {'action': 'MERGE'}, 'group', False),
                ('Enter Group', 'enter', 'mch.group_action', {'action': '@SCOPE'}, 'group_or_scope', False),
                ('Select Group', 'select_group', 'mch.group_action', {'action': 'SELECT'}, 'group', False)]),
    ('Repetition', [('Repeat Mirror', 'X', 'mch.group_repeat', {'mode': 'MIRROR'}, 'group', False),
                    ('Repeat Radial', 'radial', 'mch.group_repeat', {'mode': 'RADIAL'}, 'group', False),
                    ('Repeat Kaleido', 'kaleido', 'mch.group_repeat', {'mode': 'KALEIDO'}, 'group', False),
                    ('Repeat Grid', 'grid', 'mch.group_repeat', {'mode': 'GRID'}, 'group', False),
                    ('Radial Array', 'png:radial', 'tool:RADIAL', {}, '', True),
                    ('Curve Array', 'png:array', 'tool:ARRAY', {}, '', True),
                    ('Radial Sym Tool', 'png:radial_sym', 'tool:RSYM', {}, '', True)]),
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
    if needs in {'group', 'group_or_scope'}:
        from . import groups
        return groups.group_of(ob) is not None or (needs == 'group_or_scope' and groups.scope(context) is not None)
    return True


def _tool_icon(tid):
    t = ts.TOOL_BY_ID.get(tid)
    return 'png:' + t[3] if t else 'png:'


def _middle_kind(context):
    tool = ts.effective_tool(context)
    return 'PROFILE' if tool in {'BASE', 'CBASE'} else 'SHAPES'


def draw_modes(context):
    """0.24.58 [(key, label, on)] - the Line / Sketch switches the drawing tool in use supports."""
    from . import lasso_line, lasso_sketch
    tool = ts.effective_tool(context)
    brush = getattr(context.scene, 'mch_brush', None)
    if brush is None:
        return []
    out = []
    if tool in lasso_line.MODES:
        out.append(('line', 'Line', bool(brush.line_mode)))
    if tool in lasso_sketch.MODES or tool in {'BASE', 'CBASE'}:
        on = bool(getattr(brush, 'sketch_first', False))
        if tool in {'BASE', 'CBASE'}:
            pg = getattr(context.scene, 'mch_base' if tool == 'BASE' else 'mch_cbase', None)
            on = bool(getattr(pg, 'sketch', on))
        out.append(('sketch', 'Sketch', on))
    return out


def build(context, mx, my, region_w, region_h, S=1.0):
    """The whole menu as a list of Items (region px), placed around the mouse and kept on screen."""
    from . import quick_hud, tool_recent
    pad, gap, r_btn = 10 * S, 10 * S, 44 * S
    strip_w, card_w, act_w = r_btn + 2 * pad, 320 * S, 3 * 56 * S + 2 * 14 * S
    out = []

    # ---- left strip: white line icons, the one in use on blue ------------------------------------------
    strip = []
    y = -pad + 6 * S
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
        y -= 4 * S

    strip_btn('Select / Move', 'arrow', ('op', 'mch.select_move', {}, True), selecting)
    for tid in tool_recent.recent():
        strip_btn(ts.TOOL_BY_ID[tid][1], _tool_icon(tid), ('tool', tid), tid == active and not selecting)
    y -= 6 * S
    strip.append(Item('divider', pad, y, r_btn, 2 * S))
    y -= 10 * S
    for tid in tool_recent.favorites():
        strip_btn(ts.TOOL_BY_ID[tid][1], _tool_icon(tid), ('tool', tid), tid == active and not selecting)
    if tool_recent._valid(active):
        pinned = active in tool_recent.favorites()
        strip_btn('Pin / unpin ' + ts.TOOL_BY_ID[active][1], 'star_on' if pinned else 'star',
                  ('fav_toggle', active), False)
    y -= 26 * S
    strip.append(Item('pill', pad - 4 * S, y, r_btn + 8 * S, 22 * S, tool_recent.current_set().title(), '',
                      False, True, ('fav_set',)))
    # 0.24.51 size of every viewport popup, right here (Ctrl + wheel over the menu does the same)
    y -= 30 * S
    half = (r_btn + 8 * S - 4 * S) / 2
    strip.append(Item('pill', pad - 4 * S, y, half, 22 * S, '−', '', False, True, ('ui_size', -1)))
    strip.append(Item('pill', pad - 4 * S + half + 4 * S, y, half, 22 * S, '+', '', False, True, ('ui_size', 1)))
    strip_h = -y + pad

    # ---- middle card: '<Tool> tool', text tabs, icon grid, settings like Modeler's Dynamics ----------------
    mid = []
    inner = card_w - 2 * 16 * S
    px0 = 16 * S
    y = -10 * S
    tool = ts.TOOL_BY_ID.get(active)
    y -= 30 * S
    mid.append(Item('title', px0, y, inner, 30 * S, (tool[1] if tool else 'Mecha') + ' tool'))
    kind = _middle_kind(context)
    cols = 4
    tile = (inner - (cols - 1) * 10 * S) / cols
    tiles = []
    if kind == 'SHAPES':
        wm = context.window_manager
        stamps = bool(getattr(wm, 'mch_show_custom_shapes', False))
        y -= 26 * S
        mid.append(Item('tab', px0, y, 70 * S, 24 * S, 'Shapes', '', not stamps, True, ('tab', False)))
        mid.append(Item('tab', px0 + 74 * S, y, 70 * S, 24 * S, 'Stamps', '', stamps, True, ('tab', True)))
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
                mid.append(Item('note', px0, y, inner, 24 * S, 'No stamps yet - import a PNG shape'))
        else:
            for sid, label, _d, stem, _f in ts.SHAPES:
                if sid != 'CUSTOM':
                    tiles.append((label, 'png:' + stem, ('shape', sid, ''), brush.shape == sid))
    else:
        from . import base_mesh
        live = base_mesh.active_live_base(context)
        p = live.mch_base if live else base_mesh.scene_defaults(context)
        y -= 6 * S
        for pid, label, _d, stem, _icon in base_mesh.profiles_for(context, live):
            tiles.append((label, 'png:' + stem, ('op', 'mch.set_profile', {'profile': pid}, False), p.profile == pid))
    for n, (label, icon, action, on) in enumerate(tiles):
        c, r = n % cols, n // cols
        mid.append(Item('tile', px0 + c * (tile + 10 * S), y - (r + 1) * tile - r * 10 * S, tile, tile,
                        label, icon, on, True, action))
    if tiles:
        rows = (len(tiles) + cols - 1) // cols
        y -= rows * tile + (rows - 1) * 10 * S
    if kind == 'PROFILE':
        # 0.24.53 the lasso shapes too (the 0.24.49 popup had them under the profiles; the menu had lost them)
        brush = context.scene.mch_brush
        shapes = [(label, 'png:' + stem, ('shape', sid, ''), brush.shape == sid)
                  for sid, label, _d, stem, _f in ts.SHAPES if sid != 'CUSTOM']
        y -= 16 * S
        mid.append(Item('section', px0, y - 18 * S, inner, 18 * S, 'Lasso'))
        y -= 26 * S
        scol = 6
        st = (inner - (scol - 1) * 6 * S) / scol
        for n, (label, icon, action, on) in enumerate(shapes):
            c, r = n % scol, n // scol
            mid.append(Item('tile', px0 + c * (st + 6 * S), y - (r + 1) * st - r * 6 * S, st, st,
                            label, icon, on, True, action))
        rows = (len(shapes) + scol - 1) // scol
        y -= rows * st + (rows - 1) * 6 * S
    modes = draw_modes(context)
    if modes:                                   # 0.24.58 Line / Sketch on / off right here
        y -= 12 * S + 30 * S
        w = (inner - (len(modes) - 1) * 6 * S) / len(modes)
        for k, (key, label, on) in enumerate(modes):
            mid.append(Item('seg', px0 + k * (w + 6 * S), y, w, 28 * S, label, '', on, True, ('mode', key)))
    its = quick_hud.items(context)
    if its:
        y -= 16 * S
        mid.append(Item('section', px0, y - 18 * S, inner, 18 * S, 'Settings'))
        y -= 22 * S
        for idx, (data, prop) in enumerate(its):
            rna = data.bl_rna.properties[prop]
            if rna.type == 'ENUM':
                choices = [(e.identifier, e.name) for e in rna.enum_items]
                if len(choices) <= 4:
                    y -= 22 * S
                    mid.append(Item('label', px0, y, inner, 22 * S, rna.name or prop))
                    y -= 30 * S
                    w = (inner - (len(choices) - 1) * 6 * S) / len(choices)
                    for k, (ident, name) in enumerate(choices):
                        mid.append(Item('seg', px0 + k * (w + 6 * S), y, w, 28 * S, name, '',
                                        getattr(data, prop) == ident, True, ('set', idx, ident), data, prop))
                    y -= 6 * S
                    continue
                y -= 34 * S
                mid.append(Item('cycle', px0, y, inner, 30 * S, '', '', False, True, ('cycle', idx), data, prop))
            elif rna.type == 'BOOLEAN':
                y -= 34 * S
                mid.append(Item('toggle', px0, y, inner, 30 * S, rna.name or prop, '',
                                bool(getattr(data, prop)), True, ('cycle', idx), data, prop))
            else:
                y -= 46 * S
                mid.append(Item('slider', px0, y, inner, 44 * S, '', '', False, True, ('slider', idx), data, prop))
    mid_h = -y + 16 * S

    # ---- actions panel: white icons in threes, thin rules and small grey titles between groups -------------
    act = []
    ax0, ainner = 14 * S, act_w - 28 * S
    y = -10 * S
    ob = context.active_object
    y -= 26 * S
    act.append(Item('title', ax0, y, ainner, 26 * S, G.fit(ob.name, 14 * S, ainner)
                    if ob is not None else 'Nothing selected'))
    from . import actions_menu
    m = actions_menu.mirror_mod(ob) if ob is not None and ob.type == 'MESH' else None
    bw, bh = ainner / 3.0, 48 * S
    sections = list(ACTIONS) + ([('Live', _live(context))] if _live(context) else [])
    for sec, buttons in sections:
        y -= 8 * S
        act.append(Item('section', ax0, y - 22 * S, ainner, 22 * S, sec))
        y -= 26 * S
        for k, (label, icon, op, props, needs, closes) in enumerate(buttons):
            c = k % 3
            if c == 0:
                y -= bh
            on = sec == 'Symmetry' and 'axis' in props and bool(m and m.use_axis[props['axis']])
            props, label, on = _dynamic(context, ob, op, props, label, on)
            if op.startswith('tool:'):
                on = active == op[5:]
                action = ('tool', op[5:])
            else:
                action = ('op', op, props, closes)
            act.append(Item('abtn', ax0 + c * bw + 4 * S, y, bw - 8 * S, bh - 4 * S, label, icon, on,
                            _needs_ok(context, needs), action))
    act_h = -y + 14 * S

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


def _dynamic(context, ob, op, props, label, on):
    """Buttons whose effect depends on the state: Radial / Kaleido toggles, Enter / Exit, repetition on."""
    from . import groups, symmetry
    if op == 'mch.actions_mirror' and groups.is_group(ob):          # 0.24.57 a group: the group's mirror
        return props, label, groups.repeat_mode(ob) in {'MIRROR', 'KALEIDO'} and groups.repeat_axes(ob)[props['axis']]
    if op == 'mch.symmetry_mode' and props.get('mode', '').startswith('@'):
        now = symmetry.mode_of(ob) if ob is not None and ob.type == 'MESH' else 'OFF'
        if props['mode'] == '@RADIAL':
            target = {'OFF': 'RADIAL', 'MIRROR': 'KALEIDO', 'RADIAL': 'OFF', 'KALEIDO': 'MIRROR'}[now]
            return {'mode': target}, label, now in {'RADIAL', 'KALEIDO'}
        return {'mode': 'OFF' if now == 'KALEIDO' else 'KALEIDO'}, label, now == 'KALEIDO'
    if op == 'mch.group_action' and props.get('action') == '@SCOPE':
        inside = groups.scope(context) is not None
        return {'action': 'EXIT' if inside else 'ENTER'}, 'Exit Group' if inside else 'Enter Group', inside
    if op == 'mch.group_repeat':
        g = groups.group_of(ob)
        return props, label, g is not None and groups.repeat_mode(g) == props['mode']
    return props, label, on


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
    if kind == 'ui_size':
        set_ui_size(ui_size() + 0.1 * a[1])
        return False
    if kind == 'mode':                          # 0.24.58 Line / Sketch
        on = dict((k, v) for k, _l, v in draw_modes(context)).get(a[1], False)
        if a[1] == 'line':
            context.scene.mch_brush.line_mode = not on
        else:
            from . import lasso_sketch
            lasso_sketch.set_on(context, not on)
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


def ui_size():
    from .workspace_ui import pref
    try:
        return float(pref('menu_size', 1.0))
    except (TypeError, ValueError):
        return 1.0


def set_ui_size(v):
    """Preferences > RMB Menu (0.24.58 the Mecha Menu only; the other viewport panels have their own size), kept in
    ui_sizes.json."""
    from .workspace_ui import prefs
    p = prefs()
    if p is not None and hasattr(p, 'menu_size'):
        p.menu_size = round(max(0.5, min(3.0, v)), 2)


def _undo(message):
    try:
        bpy.ops.ed.undo_push(message=message)
    except RuntimeError:
        pass


# --- drawing -------------------------------------------------------------------------------------------------

def _icon(icon, x, y, size, color, alpha=1.0, mono=False):
    """PNG icons in their own colours (as in the panels); glyph names drawn as lines in ``color``."""
    if icon.startswith('png:'):
        if not G.image(G.icon_path(icon[4:]), x, y, size, alpha, mono, color):
            G.glyph('', x, y, size, color)
    elif icon.startswith('file:'):
        if not G.image(icon[5:], x, y, size, alpha):
            G.glyph('', x, y, size, color)
    elif icon:
        G.glyph(icon, x, y, size, color, max(1.5, size / 14.0))


HOVER = (1.0, 1.0, 1.0, 0.08)
DARK_ICON = (0.08, 0.08, 0.09, 1.0)
RULE = (1.0, 1.0, 1.0, 0.10)


def _tip(x, y, label, S, side='RIGHT'):
    """A small dark name bubble (icon-only buttons say what they are on hover)."""
    w = G.text(-9999, -9999, label, 12 * S) + 20 * S
    h = 26 * S
    if side == 'ABOVE':
        x, y = x - w / 2, y + 6 * S
    else:
        y -= h / 2
    G.rounded_rect(x, y, w, h, 8 * S, (0.02, 0.02, 0.025, 0.96))
    G.text(x + 10 * S, y + h / 2, label, 12 * S, G.TEXT)


def draw(items, hover, S, context):
    from . import quick_hud
    r = 10 * S
    tip = None
    for it in items:
        dim = 1.0 if it.enabled else 0.35
        white = (G.TEXT[0], G.TEXT[1], G.TEXT[2], dim)
        hot = it is hover and it.clickable()
        if it.kind == 'card':
            G.rounded_rect(it.x, it.y, it.w, it.h, 18 * S, G.CARD)
        elif it.kind == 'title':
            G.text(it.x, it.y + it.h / 2, it.label, 16 * S, G.TEXT)
        elif it.kind == 'section':
            G.lines([((it.x, it.y + it.h + 2 * S), (it.x + it.w, it.y + it.h + 2 * S))], RULE, 1.0 * S)
            G.text(it.x + it.w / 2, it.y + it.h / 2 - 2 * S, it.label, 11 * S, G.TEXT_DIM, 'CENTER')
        elif it.kind == 'note':
            G.text(it.x + it.w / 2, it.y + it.h / 2, it.label, 11 * S, G.TEXT_DIM, 'CENTER')
        elif it.kind == 'keycap':                 # 0.24.58 a key letter in a toolbar button's corner
            G.text(it.x + it.w / 2, it.y + it.h / 2, it.label, 9 * S, G.TEXT_DIM, 'CENTER')
        elif it.kind == 'striphead':              # 0.24.58 a group name in the tool strip
            G.text(it.x + 2 * S, it.y + it.h / 2, it.label, 9 * S, G.TEXT_DIM)
        elif it.kind == 'divider':
            G.rounded_rect(it.x + 8 * S, it.y, it.w - 16 * S, it.h, it.h / 2, RULE)
        elif it.kind in {'button', 'abtn'}:
            if it.on:
                G.rounded_rect(it.x, it.y, it.w, it.h, 12 * S, G.ACCENT)
            elif hot:
                G.rounded_rect(it.x, it.y, it.w, it.h, 12 * S, HOVER)
            size = min(it.w, it.h) * (0.62 if it.kind == 'button' else 0.58)
            _icon(it.icon, it.x + (it.w - size) / 2, it.y + (it.h - size) / 2, size, white, dim)
            if hot:
                tip = (it, 'RIGHT' if it.kind == 'button' else 'ABOVE')
        elif it.kind == 'tile':
            if it.on:
                G.rounded_rect(it.x, it.y, it.w, it.h, 14 * S, (0.93, 0.93, 0.95, 1.0))
            elif hot:
                G.rounded_rect(it.x, it.y, it.w, it.h, 14 * S, HOVER)
            size = it.w * 0.58
            _icon(it.icon, it.x + (it.w - size) / 2, it.y + (it.h - size) / 2, size,
                  DARK_ICON if it.on else G.TEXT)
            if hot:
                tip = (it, 'ABOVE')
        elif it.kind == 'tab':
            G.text(it.x, it.y + it.h / 2, it.label, 13 * S, G.TEXT if it.on else G.TEXT_DIM)
            if it.on:
                G.rounded_rect(it.x, it.y - 1 * S, G.text(-9999, -9999, it.label, 13 * S), 2 * S, 1 * S, G.TEXT)
        elif it.kind in {'seg', 'pill'}:
            bg = G.ACCENT if it.on else ((0.24, 0.245, 0.27, 1.0) if hot else (0.17, 0.175, 0.19, 1.0))
            G.rounded_rect(it.x, it.y, it.w, it.h, it.h / 2, bg)
            G.text(it.x + it.w / 2, it.y + it.h / 2, G.fit(it.label, 12 * S, it.w - 10 * S), 12 * S, G.TEXT,
                   'CENTER')
        elif it.kind == 'label':
            G.text(it.x, it.y + it.h / 2, G.fit(it.label, 12 * S, it.w), 12 * S, G.TEXT_DIM)
        elif it.kind == 'toggle':
            G.text(it.x, it.y + it.h / 2, it.label, 13 * S, G.TEXT)
            sw, sh = 40 * S, 22 * S
            sx, sy = it.x + it.w - sw, it.y + (it.h - sh) / 2
            G.rounded_rect(sx, sy, sw, sh, sh / 2, G.ACCENT if it.on else (0.24, 0.245, 0.27, 1.0))
            kx = sx + (sw - sh + 3 * S if it.on else 3 * S)
            G.rounded_rect(kx, sy + 3 * S, sh - 6 * S, sh - 6 * S, (sh - 6 * S) / 2, G.TEXT)
        elif it.kind in {'slider', 'cycle'}:
            data, prop = it.data, it.prop
            try:
                txt = quick_hud.value_text(data, prop)
            except (AttributeError, KeyError, ReferenceError):
                continue
            name, _sep, val = txt.partition('  ')
            if it.kind == 'cycle':
                G.rounded_rect(it.x, it.y, it.w, it.h, it.h / 2, (0.24, 0.245, 0.27, 1.0) if hot
                               else (0.17, 0.175, 0.19, 1.0))
                G.text(it.x + 14 * S, it.y + it.h / 2, name, 13 * S, G.TEXT)
                G.text(it.x + it.w - 14 * S, it.y + it.h / 2, val, 13 * S, G.TEXT, 'RIGHT')
                continue
            # Modeler's Dynamics row: name ... value on top, a thin track with a white knob under it
            G.text(it.x, it.y + it.h - 11 * S, name, 13 * S, G.TEXT)
            G.text(it.x + it.w, it.y + it.h - 11 * S, val, 13 * S, G.TEXT if hot else G.TEXT_DIM, 'RIGHT')
            ty = it.y + 10 * S
            f = _fraction(data, prop)
            G.rounded_rect(it.x, ty - 2 * S, it.w, 4 * S, 2 * S, (0.28, 0.285, 0.31, 1.0))
            if f > 0:
                G.rounded_rect(it.x, ty - 2 * S, it.w * f, 4 * S, 2 * S, G.ACCENT)
            kr = (9 if hot else 8) * S
            G.rounded_rect(it.x + it.w * f - kr, ty - kr, 2 * kr, 2 * kr, kr, G.TEXT)
    if tip is not None:
        it, side = tip
        if side == 'RIGHT':
            _tip(it.x + it.w + 8 * S, it.y + it.h / 2, it.label, S)
        else:
            _tip(it.x + it.w / 2, it.y + it.h, it.label, S, 'ABOVE')


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
        self.S = G.ui_factor(context, self.region, menu=True)
        self.mouse = (event.mouse_region_x, event.mouse_region_y)
        self.items = build(context, *self.mouse, self.region.width, self.region.height, self.S)
        self.hover = None
        self.drag = None
        self._handle = bpy.types.SpaceView3D.draw_handler_add(self._draw, (), 'WINDOW', 'POST_PIXEL')
        _OPEN[0] = True
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
        _OPEN[0] = False
        if self._handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            self._handle = None
        if context.area:
            context.area.tag_redraw()

    def _at(self, x, y):
        return next((it for it in reversed(self.items) if it.kind != 'card' and it.hit(x, y)), None)

    def _inside(self, x, y):
        return any(it.kind == 'card' and it.hit(x, y) for it in self.items)

    def _near(self, x, y):
        """Over the menu or the gaps between its cards (a little margin, so a quick move does not close it)."""
        return near(self.items, x, y, 36 * self.S)

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
                if run(context, it, event.ctrl and not self.hold, True) == 'TYPE':
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
            if not self.hold and not self._near(x, y):
                self._finish(context)             # 0.24.52 the mouse left the menu: it closes
                return {'FINISHED'}
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
                if not self._near(x, y) and not self.hold:
                    self._finish(context)
                    return {'CANCELLED'}
                return {'RUNNING_MODAL'}
            if it.kind == 'slider':
                self.drag = (it, x, getattr(it.data, it.prop), False)
                return {'RUNNING_MODAL'}
            try:                                  # 0.24.52 a click never closes it (tools switch in place)
                r = run(context, it, event.ctrl and not self.hold, True)
            except (RuntimeError, AttributeError, TypeError, ReferenceError) as ex:
                print('Mecha Menu:', ex)
                r = False
            if r == 'TYPE':
                self._finish(context)
                bpy.ops.wm.call_panel(name='MCH_PT_quick_value', keep_open=False)
                return {'FINISHED'}
            self.S = G.ui_factor(context, self.region, menu=True)
            self._rebuild(context)
            self.hover = self._at(x, y)
            return {'RUNNING_MODAL'}
        if event.ctrl and event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            set_ui_size(ui_size() + (0.1 if event.type == 'WHEELUPMOUSE' else -0.1))   # Ctrl + wheel: size
            self.S = G.ui_factor(context, self.region, menu=True)
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


class MCH_OT_mecha_mmb_gate(bpy.types.Operator):
    """Middle mouse in MECHA LAB: a click (no movement) opens the Mecha Menu, a drag orbits the view as always"""
    bl_idname = 'mch.mecha_mmb_gate'
    bl_label = 'Mecha Menu (middle click)'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        from . import bottom_bar
        from .workspace_ui import pref
        return (pref('mmb_menu', True) and context.area is not None and context.area.type == 'VIEW_3D'
                and bottom_bar.ui_active(context) and not _OPEN[0])

    def invoke(self, context, event):
        self.x0, self.y0 = event.mouse_x, event.mouse_y
        try:
            self.limit = max(5, context.preferences.inputs.drag_threshold_mouse)
        except AttributeError:
            self.limit = 5
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            if abs(event.mouse_x - self.x0) + abs(event.mouse_y - self.y0) > self.limit:
                try:                                   # a drag: Blender's own orbit takes over from here
                    bpy.ops.view3d.rotate('INVOKE_DEFAULT')
                except RuntimeError:
                    pass
                return {'FINISHED'}
            return {'RUNNING_MODAL'}
        if event.type == 'MIDDLEMOUSE' and event.value == 'RELEASE':
            open_menu(context)                        # a click: the menu
            return {'FINISHED'}
        if event.type == 'ESC':
            return {'CANCELLED'}
        if event.type.startswith('NDOF') or event.type.startswith('TRACKPAD'):
            return {'FINISHED', 'PASS_THROUGH'}       # 0.24.54 a 3D mouse / trackpad: never held up here
        return {'PASS_THROUGH'}                       # 0.24.54 everything else goes on as usual


def near(items, x, y, margin):
    cards = [i for i in items if i.kind == 'card']
    if not cards:
        return False
    x0 = min(c.x for c in cards) - margin
    x1 = max(c.x + c.w for c in cards) + margin
    if not x0 <= x <= x1:
        return False
    # inside the band the cards span, but not far above / below the card under the mouse column
    for c in cards:
        if c.x - margin <= x <= c.x + c.w + margin and c.y - margin <= y <= c.y + c.h + margin:
            return True
    top = max(c.y + c.h for c in cards)
    bottom = min(c.y for c in cards)
    # between two cards (the gap): allowed within the shorter card's height
    return any(a.x + a.w <= x <= b.x and max(a.y, b.y) - margin <= y <= min(a.y + a.h, b.y + b.h) + margin
               for a in cards for b in cards if a is not b) and bottom <= y <= top


def open_menu(context):
    """Open the Mecha Menu (False if it could not be opened here)."""
    try:
        return bpy.ops.mch.mecha_menu('INVOKE_DEFAULT') == {'RUNNING_MODAL'}
    except RuntimeError:
        return False


def use_menu():
    from .workspace_ui import pref
    return not bpy.app.background and not pref('classic_rmb_popup', False)


CLASSES = (MCH_OT_mecha_menu, MCH_OT_mecha_hold_gate, MCH_OT_mecha_mmb_gate)
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
        # 0.24.51 middle click = menu (exact: Shift / Ctrl + middle mouse keep panning / zooming)
        _keymaps.append((km, km.keymap_items.new('mch.mecha_mmb_gate', 'MIDDLEMOUSE', 'PRESS')))


def unregister():
    for km, item in _keymaps:
        try:
            km.keymap_items.remove(item)
        except Exception:            # a stale item (key configuration rebuilt, e.g. factory settings)
            pass
    _keymaps.clear()
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
    G.free_textures()
