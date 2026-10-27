"""0.24.59 Layers panel: the scene's parts and groups on the left of the viewport (where the tool strip was), with
Export and the ZBrush Bridge under them - drawn in the Mecha look like the side panel on the right.

    LAYERS                                   [-]
    [Group] [Ungroup] [Merge] [Enter]
    v [#] Arm_L              Mirror  [>] (eye)
          [ ] Shoulder_L                 (eye)
          [ ] Forearm_L                  (eye)
      [ ] Torso                          (eye)
    > EXPORT        OBJ | FBX, Selected | Visible, Apply Modifiers, ZBrush-safe Faces, Scale, [Export...]
    > ZBRUSH BRIDGE [Send to ZBrush] [Import Back] [Open Folder], the folder, what was sent
    > UI SIZE       (Viewport Panels) (RMB Menu) (Tool Menu) (Panel Opacity) [Small] [Normal] [Large] [Huge]

A click on a row selects the part (Shift: add / remove), on a group row the group handle; the eye hides / shows
(a group: all its parts); [>] works inside the group (Enter / Exit, as in the Mecha Menu).  Groups fold with the
arrow.  The wheel scrolls a long list.  Export and the Bridge start folded; they share one set of options (the
ZBrush settings), so "Send to ZBrush" and "Export" write the same mesh.
"""
from __future__ import annotations

import os

import bpy
from bpy.props import BoolProperty, StringProperty

from . import panel_capture as pc

WIDTH = 270.0
ROW = 26.0
GAP = 6.0
PAD = 12.0
HEAD = 40.0
INDENT = 16.0
TOP_MARGIN = 150.0          # same top as the side panel on the right
BOTTOM_MARGIN = 10.0
MIN_W = 44.0
TOOL = 'LAYERS'             # the fold keys of its sections ('LAYERS:Export')
SHOWN_TYPES = {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'EMPTY'}


# --- what is listed -------------------------------------------------------------------------------------------

def listed(ob):
    """A part the user made - not a cutter, a repetition helper or a hidden Mecha resource."""
    from . import groups
    if ob is None or ob.type not in SHOWN_TYPES:
        return False
    if ob.type == 'EMPTY' and not groups.is_group(ob):
        return False
    if groups.CARRIER_KEY in ob or ob.hide_viewport:
        return False
    if any(c.name.startswith('MCH') for c in ob.users_collection):
        return False
    return not (ob.display_type in {'WIRE', 'BOUNDS'} and ob.hide_render)


def _in_group(ob):
    from . import groups
    return any(c.get(groups.GROUP_KEY) for c in ob.users_collection)


def tree(context):
    """[(object, depth, is_group, folded)] top to bottom: groups (their parts under them) then loose parts."""
    from . import groups, side_panel
    out = []

    def add(ob, depth):
        is_g = groups.is_group(ob)
        fold = is_g and side_panel.folded(TOOL, 'grp:' + ob.name)
        out.append((ob, depth, is_g, fold))
        if is_g and not fold:
            coll = groups.collection_of(ob)
            kids = [o for o in (coll.objects if coll is not None else []) if o is not ob and listed(o)]
            for o in sorted(kids, key=lambda o: (not groups.is_group(o), o.name.lower())):
                add(o, depth + 1)
    top = [o for o in context.scene.objects if listed(o) and not _in_group(o)]
    for o in sorted(top, key=lambda o: (not groups.is_group(o), o.name.lower())):
        add(o, 0)
    return out


def _hidden(context, ob):
    from . import groups
    try:
        if groups.is_group(ob):
            parts = [o for o in groups.members(ob) if o.type != 'EMPTY'] or [ob]
            return all(o.hide_get() for o in parts)
        return ob.hide_get()
    except (RuntimeError, ReferenceError):
        return False


def _icon(ob):
    from . import groups
    if groups.is_group(ob):
        return 'group'
    return 'curve' if ob.type in {'CURVE', 'SURFACE'} else 'cube'


# --- the export / bridge sections (normal panel code, turned into Mecha rows like the side panel) --------------

def draw_export(layout, context):
    s = context.scene.mch_zbrush
    box = layout.box()
    box.label(text='Export')
    box.row().prop(s, 'export_format', expand=True)
    box.row().prop(s, 'export_scope', expand=True)
    box.prop(s, 'apply_modifiers', text='Apply Modifiers')
    box.prop(s, 'split_ngons')
    box.prop(s, 'scale')
    row = box.row()
    row.scale_y = 1.4
    op = row.operator('mch.export_mesh', text='Export...', icon='EXPORT')
    op.scope, op.file_format = s.export_scope, s.export_format
    op.apply_modifiers, op.split_ngons, op.scale = s.apply_modifiers, s.split_ngons, s.scale


def draw_sizes(layout, context):
    """0.24.59 the viewport UI sizes right here (were only in Preferences / the sidebar)."""
    from .workspace_ui import prefs
    p = prefs()
    if p is None:
        return
    box = layout.box()
    box.label(text='UI Size')
    box.prop(p, 'mecha_ui_size')
    box.prop(p, 'menu_size')
    box.prop(p, 'strip_scale', text='Tool Menu')
    box.prop(p, 'panel_opacity')
    row = box.row()
    for label, v in (('Small', 0.75), ('Normal', 1.0), ('Large', 1.4), ('Huge', 1.9)):
        row.operator('mch.icon_size_preset', text=label).factor = v


def draw_bridge(layout, context):
    from . import zbrush_bridge
    s = context.scene.mch_zbrush
    box = layout.box()
    box.label(text='ZBrush Bridge')
    row = box.row()
    row.scale_y = 1.4
    row.operator('mch.zbrush_send', text='Send to ZBrush', icon='EXPORT')
    row.operator('mch.zbrush_import', text='Import Back', icon='IMPORT')
    box.operator('mch.zbrush_open_folder', text='Open Folder', icon='FILE_FOLDER')
    folder = _folder(s)
    box.label(text='Folder: ' + (folder or '(Blender config)/mecha_lab/zbrush_bridge'))
    if folder and os.path.isdir(folder):        # only read - drawing never makes the folder
        try:
            rows = zbrush_bridge.manifest_rows(s)
        except (OSError, ValueError, KeyError):
            rows = []
        if rows:
            changed = sum(1 for r in rows if r[2] == 'CHANGED')
            box.label(text=f'Sent {len(rows)} part(s), {changed} changed in ZBrush')


def _folder(s):
    """The exchange folder's path without creating it ('' when it cannot be told)."""
    if s.exchange_dir:
        return bpy.path.abspath(s.exchange_dir).strip()
    try:
        return bpy.utils.user_resource('CONFIG', path='mecha_lab/zbrush_bridge', create=False) or ''
    except (TypeError, ValueError):
        return ''


# --- layout ---------------------------------------------------------------------------------------------------

def on(context):
    from .workspace_ui import pref
    from . import bottom_bar, ui_bars
    try:
        return pref('layers_panel', True) and bottom_bar.ui_active(context) and not ui_bars.strip_on(context)
    except (AttributeError, KeyError, TypeError, ReferenceError):
        return False


def minimised(context):
    return bool(getattr(context.window_manager, 'mch_layers_min', False))


def taken(context, k):
    """How much of the left side the panel takes (0 when it is not shown)."""
    if not on(context):
        return 0.0
    return (MIN_W if minimised(context) else WIDTH) * k + 12.0 * k


def _toolbar(context):
    from . import groups
    mode_ok = getattr(context, 'mode', 'OBJECT') == 'OBJECT'
    g = groups.group_of(getattr(context, 'active_object', None))
    inside = groups.scope(context)
    sel = bool(getattr(context, 'selected_objects', None))
    cells = [('Group', ('op', 'mch.group', {}), mode_ok and sel),
             ('Ungroup', ('op', 'mch.group_action', {'action': 'UNGROUP'}), mode_ok and g is not None),
             ('Merge', ('op', 'mch.group_action', {'action': 'MERGE'}), mode_ok and g is not None)]
    if inside is not None:
        cells.append(('Exit', ('op', 'mch.group_action', {'action': 'EXIT'}), mode_ok))
    else:
        cells.append(('Enter', ('op', 'mch.group_action', {'action': 'ENTER'}), mode_ok and g is not None))
    return cells


def content(context, x, width, k):
    """(items, height): the panel's rows, y measured down from 0."""
    from .mecha_menu import Item
    from . import groups, side_panel
    out = []
    y = 0.0
    cells = _toolbar(context)
    cw = (width - GAP * k * (len(cells) - 1)) / len(cells)
    y -= ROW * k
    for i, (label, action, ok) in enumerate(cells):
        out.append(Item('tbtn', x + i * (cw + GAP * k), y, cw, ROW * k, label, '', False, ok, action))
    y -= GAP * k
    try:                                     # 0.24.59 ZBrush's Active / Total Points Count
        from . import point_counts
        act, tot = point_counts(context)
        y -= 17 * k
        out.append(Item('pnote', x, y, width, 17 * k, f'Active Points {act:,}   Total Points {tot:,}', '', False,
                        True))
        y -= 4 * k
    except (ImportError, AttributeError, RuntimeError, ReferenceError):
        pass
    rows = tree(context)
    active = getattr(context, 'active_object', None)
    inside = groups.scope(context)
    if not rows:
        y -= 17 * k
        out.append(Item('pnote', x, y, width, 17 * k, 'No parts yet', '', False, True))
    rh = ROW * k
    for ob, depth, is_g, fold in rows:
        y -= rh
        ix = x + depth * INDENT * k
        hidden = _hidden(context, ob)
        if is_g:
            out.append(Item('lfold', ix, y, 16 * k, rh, '', '', not fold, True,
                            ('fold', f'{TOOL}:grp:{ob.name}', False)))
        right = x + width
        out.append(Item('pmin', right - 24 * k, y + 1 * k, 24 * k, rh - 2 * k, 'Hide' if not hidden else 'Show',
                        'eye_off' if hidden else 'eye', False, True, ('op', 'mch.layer_eye', {'name': ob.name}),
                        'RIGHT'))
        right -= 26 * k
        badge = ''
        if is_g:
            out.append(Item('pmin', right - 24 * k, y + 1 * k, 24 * k, rh - 2 * k,
                            'Exit' if inside == ob else 'Work inside', 'exit' if inside == ob else 'enter', False,
                            True, ('op', 'mch.group_pick', {'name': ob.name, 'enter': inside != ob}), 'RIGHT'))
            right -= 26 * k
            mode = groups.repeat_mode(ob)
            badge = '' if mode == 'OFF' else mode.title()
        try:
            sel = ob.select_get()
        except RuntimeError:
            sel = False
        lx = ix + 18 * k
        out.append(Item('lrow', lx, y, right - lx - 2 * k, rh, ob.name, _icon(ob), sel, True,
                        ('op', 'mch.layer_pick', {'name': ob.name}),
                        {'hidden': hidden, 'badge': badge, 'active': ob == active}))
        y -= 2 * k
    y -= GAP * k
    b = side_panel.Builder(TOOL, x, width, k)
    b.y = y
    for drawer in (draw_export, draw_bridge, draw_sizes):     # folded at first (the list gets the room)
        node = pc.capture(drawer, context)
        if node.opts.get('error'):
            continue
        for box in node.children:
            if box.kind == 'box':
                b.section(box, x, width, start_folded=True)
            else:
                b.node(box, x, width)
    out += b.out
    return out, -b.y


def frame(context, region_w, region_h, k):
    from . import ui_bars
    x0 = ui_bars.left_inset(context) + 12 * k
    floor = ui_bars.bottom_taken(context, k, region_w) + BOTTOM_MARGIN * k
    try:                                     # the key legend in the bottom left corner: stay above it
        from . import key_legend
        b = key_legend.box(context, k)
        if b is not None and b[0] < x0 + WIDTH * k:
            floor = max(floor, b[1] + b[3] + BOTTOM_MARGIN * k)
    except (ImportError, AttributeError, TypeError, ValueError, ReferenceError):
        pass
    return x0, region_h - TOP_MARGIN * k, WIDTH * k, floor


def layout(context, region_w, region_h, k=1.0):
    """{'items', 'content', 'view'} like side_panel.layout (whole rows only, a scroll bar when it is long)."""
    from .mecha_menu import Item
    x0, top, w, floor = frame(context, region_w, region_h, k)
    if minimised(context):
        mw = MIN_W * k
        card = Item('card', x0, top - mw, mw, mw)
        tab = Item('pmin', card.x + 4 * k, card.y + 4 * k, mw - 8 * k, mw - 8 * k, 'Layers', 'stack', False, True,
                   ('layers_min',))
        return {'items': [card, tab], 'content': 0.0, 'view': 0.0}
    rows, h = content(context, x0 + PAD * k, w - 2 * PAD * k, k)
    room = top - floor - HEAD * k - 2 * PAD * k
    view = max(0.0, min(h, room))
    scroll = max(0.0, min(float(getattr(context.window_manager, 'mch_layers_scroll', 0.0)), h - view))
    card_h = HEAD * k + view + 2 * PAD * k
    out = [Item('card', x0, top - card_h, w, card_h)]
    out.append(Item('phead', x0 + PAD * k, top - PAD * k - HEAD * k + 6 * k, w - 2 * PAD * k - 34 * k,
                    HEAD * k - 6 * k, 'LAYERS', 'stack', False, True, None))
    out.append(Item('pbtn', x0 + w - PAD * k - 26 * k, top - PAD * k - 30 * k, 26 * k, 26 * k, '–', '', False, True,
                    ('layers_min',)))
    y_top = top - PAD * k - HEAD * k
    cy = y_top - view
    for it in rows:
        it.y += y_top + scroll
        if it.kind == 'sbg':
            lo, hi = max(it.y, cy), min(it.y + it.h, y_top)
            if hi - lo < 2 * k:
                continue
            it.y, it.h = lo, hi - lo
        elif it.y < cy - 0.5 or it.y + it.h > y_top + 0.5:
            continue
        out.append(it)
    if h > view + 1:
        bar_h = max(30 * k, view * view / h)
        bar_y = y_top - bar_h - (view - bar_h) * (scroll / max(1e-6, h - view))
        out.append(Item('sbar', x0 + w - 7 * k, bar_y, 3 * k, bar_h))
    return {'items': out, 'content': h, 'view': view}


def items(context, region_w, region_h, k=1.0):
    return layout(context, region_w, region_h, k)['items']


def scroll_by(context, region_w, region_h, k, dy):
    lay = layout(context, region_w, region_h, k)
    wm = context.window_manager
    wm.mch_layers_scroll = max(0.0, min(float(wm.mch_layers_scroll) + dy, max(0.0, lay['content'] - lay['view'])))
    from . import ui_bars
    ui_bars.bump()


def over(context, x, y):
    region = getattr(context, 'region', None)
    if region is None or not on(context):
        return False
    from .ui_gpu import ui_factor
    its = items(context, region.width, region.height, ui_factor(context, region))
    return bool(its) and its[0].hit(x, y)


# --- operators ------------------------------------------------------------------------------------------------

class MCH_OT_layer_pick(bpy.types.Operator):
    """Select this part (Shift: add / remove); a group row selects the group"""
    bl_idname = 'mch.layer_pick'
    bl_label = 'Pick Layer'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    name: StringProperty()
    extend: BoolProperty(default=False, options={'SKIP_SAVE'})

    def invoke(self, context, event):
        self.extend = bool(event.shift)
        return self.execute(context)

    def execute(self, context):
        ob = bpy.data.objects.get(self.name)
        if ob is None or context.mode != 'OBJECT' or ob.name not in context.view_layer.objects:
            return {'CANCELLED'}
        try:
            if ob.hide_get():
                ob.hide_set(False)
            if self.extend:
                ob.select_set(not ob.select_get())
            else:
                for o in context.selected_objects:
                    o.select_set(False)
                ob.select_set(True)
            if ob.select_get():
                context.view_layer.objects.active = ob
        except RuntimeError:
            return {'CANCELLED'}
        return {'FINISHED'}


class MCH_OT_layer_eye(bpy.types.Operator):
    """Hide / show this part (a group: all its parts)"""
    bl_idname = 'mch.layer_eye'
    bl_label = 'Hide / Show Layer'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    name: StringProperty()

    def execute(self, context):
        from . import groups
        ob = bpy.data.objects.get(self.name)
        if ob is None or ob.name not in context.view_layer.objects:
            return {'CANCELLED'}
        hide = not _hidden(context, ob)
        targets = groups.members(ob) + [ob] if groups.is_group(ob) else [ob]
        for o in targets:
            if o.name in context.view_layer.objects:
                try:
                    o.hide_set(hide)
                except RuntimeError:
                    pass
        return {'FINISHED'}


CLASSES = (MCH_OT_layer_pick, MCH_OT_layer_eye)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    from bpy.props import FloatProperty
    bpy.types.WindowManager.mch_layers_scroll = FloatProperty(default=0.0, options={'SKIP_SAVE'})
    bpy.types.WindowManager.mch_layers_min = BoolProperty(default=False, options={'SKIP_SAVE'})


def unregister():
    for name in ('mch_layers_scroll', 'mch_layers_min'):
        if hasattr(bpy.types.WindowManager, name):
            delattr(bpy.types.WindowManager, name)
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
