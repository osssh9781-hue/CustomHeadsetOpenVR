"""0.24.59 Layers panel: the scene's parts and groups on the left of the viewport (where the tool strip was), with
Export and the ZBrush Bridge under them - drawn in the Mecha look like the side panel on the right.

    LAYERS                                   [-]
    [Group] [Ungroup] [Merge] [Enter]
    v [#] Arm_L              Mirror  [>] (eye)
          [ ] Shoulder_L                 (eye)
          [ ] Forearm_L                  (eye)
      [ ] Torso                          (eye)
    v LIVE STACK    0.24.82 the live steps (modifiers) on the active part: eye, up / down, Apply, remove, Apply All
    > EXPORT        OBJ | FBX, Selected | Visible, Apply Modifiers, ZBrush-safe Faces, Scale, [Export...]
    > ZBRUSH BRIDGE [Send to ZBrush] [Import Back] [Open Folder], the folder, what was sent
    > UI SIZE       (Viewport Panels) (RMB Menu) (Tool Menu) (Panel Opacity) [Small] [Normal] [Large] [Huge]

A click on a row selects the part (Shift: add / remove), on a group row the group handle; the eye hides / shows
(a group: all its parts); [>] works inside the group (Enter / Exit, as in the Mecha Menu).  Groups fold with the
arrow.  0.24.95 the scene's collections are folder rows too (their collections, groups and parts under them; the eye
hides the collection, a click selects its parts); group and collection rows have Origin and Mirror (a collection
is made a group in place for them); a second click on a row soon after the first renames it.  The wheel scrolls a long list.  Export and the Bridge start folded; they share one set of options (the
ZBrush settings), so "Send to ZBrush" and "Export" write the same mesh.
"""
from __future__ import annotations

import os

import bpy
from bpy.props import BoolProperty, StringProperty

from . import panel_capture as pc
from .quick_hud import points_text

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

def listed(ob, owners=None):
    """A part the user made - not a cutter, a repetition helper or a hidden Mecha resource.  ``owners``: the
    collections each object is in (``scan``) - else Blender's ``users_collection``, which walks every collection
    in the file for one object (0.24.95 user: "레이어는 왜 이렇게 느려?" - that, once per part per redraw)."""
    from . import groups
    if ob is None or ob.type not in SHOWN_TYPES:
        return False
    if ob.type == 'EMPTY' and not groups.is_group(ob):
        return False
    if groups.CARRIER_KEY in ob or ob.hide_viewport:
        return False
    colls = owners.get(ob.name, ()) if owners is not None else ob.users_collection
    if any(c.name.startswith('MCH') for c in colls):
        return False
    return not (ob.display_type in {'WIRE', 'BOUNDS'} and ob.hide_render)


def _in_group(ob, owners=None):
    from . import groups
    colls = owners.get(ob.name, ()) if owners is not None else ob.users_collection
    return any(c.get(groups.GROUP_KEY) for c in colls)


def scan(context):
    """0.24.95 one walk of the scene's collections: {'owners': object name -> its collections, 'listed': the names
    of the listed parts in the view layer} - what ``listed`` / ``_in_group`` asked Blender object by object."""
    owners = {}
    seen = set()
    stack = [context.scene.collection]
    while stack:
        c = stack.pop()
        if c.as_pointer() in seen:              # (a collection linked in two places: once)
            continue
        seen.add(c.as_pointer())
        for o in c.objects:
            owners.setdefault(o.name, []).append(c)
        stack.extend(c.children)
    names = {o.name for o in context.view_layer.objects if listed(o, owners)}
    return {'owners': owners, 'listed': names}


def _user_coll(c):
    """A collection of the user's (not a Mecha resource; a group's own collection shows as its group)."""
    from . import groups
    return not c.name.startswith('MCH') and not c.get(groups.GROUP_KEY)


def layer_coll(context, coll):
    """The view layer's entry for ``coll`` (its hide / exclude), or None."""
    def walk(lc):
        if lc.collection == coll:
            return lc
        for ch in lc.children:
            r = walk(ch)
            if r is not None:
                return r
        return None
    return walk(context.view_layer.layer_collection)


def tree(context, sc=None):
    """[(item, depth, is_group, folded, kind)] top to bottom.  0.24.95 (user: "콜렉션도 레이어에 나오게") the scene's
    collections as folders (kind 'COLL': their collections, groups and parts under them), groups ('GROUP': their parts
    under them) and parts ('OBJ') - collections first, then groups, then parts.  ``sc``: ``scan`` (made here if not
    given)."""
    from . import groups, side_panel
    sc = sc if sc is not None else scan(context)
    shown = sc['listed']
    owners = sc['owners']
    out = []

    def add(ob, depth):
        is_g = groups.is_group(ob)
        fold = is_g and side_panel.folded(TOOL, 'grp:' + ob.name)
        out.append((ob, depth, is_g, fold, 'GROUP' if is_g else 'OBJ'))
        if is_g and not fold:
            coll = groups.collection_of(ob)
            if coll is not None:
                sub_colls(coll, depth + 1)          # (a collection made a group: its own collections under it)
            kids = [o for o in (coll.objects if coll is not None else []) if o is not ob and o.name in shown]
            for o in sorted(kids, key=lambda o: (not groups.is_group(o), o.name.lower())):
                add(o, depth + 1)

    def sub_colls(c, depth):
        for ch in sorted(c.children, key=lambda x: x.name.lower()):
            if not _user_coll(ch):
                continue
            fold = side_panel.folded(TOOL, 'coll:' + ch.name)
            out.append((ch, depth, False, fold, 'COLL'))
            if not fold:
                add_coll(ch, depth + 1)

    def add_coll(c, depth):
        sub_colls(c, depth)
        objs = [o for o in c.objects if o.name in shown and not _in_group(o, owners)]
        for o in sorted(objs, key=lambda o: (not groups.is_group(o), o.name.lower())):
            add(o, depth)
    add_coll(context.scene.collection, 0)
    return out


def _hidden(context, ob):
    from . import groups
    try:
        if isinstance(ob, bpy.types.Collection):
            lc = layer_coll(context, ob)
            return lc is None or lc.exclude or lc.hide_viewport
        if groups.is_group(ob):
            parts = [o for o in groups.members(ob) if o.type != 'EMPTY'] or [ob]
            return all(o.hide_get() for o in parts)
        return ob.hide_get()
    except (RuntimeError, ReferenceError):
        return False


def _icon(ob):
    from . import groups
    if isinstance(ob, bpy.types.Collection):
        return 'folder'
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
    box.prop(s, 'crease_groups')
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
    try:                                     # 0.24.95 Work Scene (user: "그렇게 버튼 만들어 줘") - a second row
        from . import work_scene
        cells2 = work_scene.toolbar_cells(context)
    except (ImportError, AttributeError, ReferenceError):
        cells2 = []
    if cells2:
        cw2 = (width - GAP * k * (len(cells2) - 1)) / len(cells2)
        y -= ROW * k
        for i, (label, action, ok) in enumerate(cells2):
            out.append(Item('tbtn', x + i * (cw2 + GAP * k), y, cw2, ROW * k, label, '', False, ok, action))
        y -= GAP * k
    try:                                     # 0.24.59 ZBrush's Active / Total Points Count
        from . import point_counts
        act, tot = point_counts(context)
        y -= 17 * k
        out.append(Item('pnote', x, y, width, 17 * k,
                        f'Active Points {points_text(act)}   Total Points {points_text(tot)}', '', False, True))
        y -= 4 * k
    except (ImportError, AttributeError, RuntimeError, ReferenceError):
        pass
    sc = scan(context)
    rows = tree(context, sc)
    active = getattr(context, 'active_object', None)
    inside = groups.scope(context)
    if not rows:
        y -= 17 * k
        out.append(Item('pnote', x, y, width, 17 * k, 'No parts yet', '', False, True))
    rh = ROW * k
    bw = 24 * k

    def small(right, label, icon, on, action):
        out.append(Item('pmin', right - bw, y + 1 * k, bw, rh - 2 * k, label, icon, on, True, action, 'RIGHT'))
        return right - bw - 2 * k
    for ob, depth, is_g, fold, kind in rows:
        y -= rh
        ix = x + depth * INDENT * k
        hidden = _hidden(context, ob)
        is_c = kind == 'COLL'
        if is_g or is_c:
            out.append(Item('lfold', ix, y, 16 * k, rh, '', '', not fold, True,
                            ('fold', f'{TOOL}:{"coll" if is_c else "grp"}:{ob.name}', False)))
        right = x + width
        right = small(right, 'Hide' if not hidden else 'Show', 'eye_off' if hidden else 'eye', False,
                      ('op', 'mch.layer_eye', {'name': ob.name, 'coll': is_c}))
        badge = ''
        if is_g:
            right = small(right, 'Exit' if inside == ob else 'Work inside', 'exit' if inside == ob else 'enter',
                          False, ('op', 'mch.group_pick', {'name': ob.name, 'enter': inside != ob}))
            box_off = bool(ob.get(groups.BOX_HIDDEN_KEY))        # 0.24.84 the group's box lines: on / off
            right = small(right, 'Box lines off' if box_off else 'Box lines on', 'card', not box_off,
                          ('op', 'mch.group_box_eye', {'name': ob.name}))
            mode = groups.repeat_mode(ob)
            badge = '' if mode in {'OFF', 'MIRROR'} else mode.title()     # (0.24.95 Mirror: its button lit)
        if is_g or is_c:                    # (0.24.95 user: "콜렉션도 오리진 투 오브젝트랑 미러 되게")
            mir = is_g and groups.repeat_mode(ob) == 'MIRROR'
            right = small(right, 'Mirror off' if mir else 'Mirror (a live copy)', 'flip', mir,
                          ('op', 'mch.layer_group_op', {'name': ob.name, 'coll': is_c, 'action': 'MIRROR'}))
            right = small(right, 'Origin to its middle', 'origin', False,
                          ('op', 'mch.layer_group_op', {'name': ob.name, 'coll': is_c, 'action': 'ORIGIN'}))
        if is_c:
            from . import name_fix
            from . import live_ref               # 0.24.132 not all_objects (its cache can be stale right after Ctrl+Z)
            parts = [o for o in live_ref.deep_objects(ob) if name_fix.safe_name(o) in sc['listed']]   # 0.24.129 a name that is not UTF-8
            sel = bool(parts) and all(o.select_get() for o in parts)
        else:
            try:
                sel = ob.select_get()
            except RuntimeError:
                sel = False
        lx = ix + 18 * k
        out.append(Item('lrow', lx, y, right - lx - 2 * k, rh, ob.name, _icon(ob), sel, True,
                        ('op', 'mch.layer_pick', {'name': ob.name, 'coll': is_c}),
                        {'hidden': hidden, 'badge': badge, 'active': ob == active}))
        y -= 2 * k
    y -= GAP * k
    b = side_panel.Builder(TOOL, x, width, k)
    b.y = y
    from . import live_stack                                  # 0.24.82 the live steps on the active part
    for drawer in (live_stack.draw, draw_export, draw_bridge, draw_sizes):   # folded at first (the list gets the room)
        node = pc.capture(drawer, context)
        if node.opts.get('error'):
            continue
        for box in node.children:
            if box.kind == 'box':
                b.section(box, x, width, start_folded=drawer is not live_stack.draw)
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
    from . import groups
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
    out.append(Item('phead', x0 + PAD * k, top - PAD * k - HEAD * k + 6 * k, w - 2 * PAD * k - 62 * k,
                    HEAD * k - 6 * k, 'LAYERS', 'stack', False, True, None))
    boxes = groups.boxes_on(context)                                     # 0.24.87 every group's box lines at once
    out.append(Item('pmin', x0 + w - PAD * k - 54 * k, top - PAD * k - 30 * k, 26 * k, 26 * k,
                    'Hide all group box lines' if boxes else 'Show all group box lines', 'card', boxes, True,
                    ('op', 'mch.group_boxes_all', {}), 'RIGHT'))
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

_LAST_CLICK = {'key': None, 'time': 0.0}
DOUBLE = 0.4                    # s: a second click on the same row this soon = rename


def double_click(key, now=None):
    """True when this click on row ``key`` is the second one on it within ``DOUBLE`` s (the third starts over)."""
    import time
    now = time.monotonic() if now is None else now
    twice = _LAST_CLICK['key'] == key and now - _LAST_CLICK['time'] < DOUBLE
    _LAST_CLICK.update(key=None if twice else key, time=now)
    return twice


class MCH_OT_layer_pick(bpy.types.Operator):
    """Select this part (Shift: add / remove); a group row selects the group, a collection row every part in it.
    Click twice: rename"""
    bl_idname = 'mch.layer_pick'
    bl_label = 'Pick Layer'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    name: StringProperty()
    coll: BoolProperty(default=False, options={'SKIP_SAVE'})
    extend: BoolProperty(default=False, options={'SKIP_SAVE'})

    def invoke(self, context, event):
        self.extend = bool(event.shift)
        twice = double_click(('C:' if self.coll else 'O:') + self.name) and not self.extend
        if twice and not bpy.app.background:   # (0.24.95 user: "레이어 이름도 바꿀 수 있게")
            bpy.ops.mch.layer_rename('INVOKE_DEFAULT', name=self.name, coll=self.coll)
            return {'CANCELLED'}                # (the dialog's own OK makes the undo step)
        return self.execute(context)

    def execute(self, context):
        if context.mode != 'OBJECT':
            return {'CANCELLED'}
        if self.coll:
            c = bpy.data.collections.get(self.name)
            if c is None:
                return {'CANCELLED'}
            shown = scan(context)['listed']
            from . import live_ref
            obs = [o for o in live_ref.deep_objects(c) if o.name in shown]
            if not obs:
                return {'CANCELLED'}
            try:
                if not self.extend:
                    for o in context.selected_objects:
                        o.select_set(False)
                for o in obs:
                    if o.hide_get():
                        o.hide_set(False)
                    o.select_set(True)
                context.view_layer.objects.active = obs[0]
            except RuntimeError:
                return {'CANCELLED'}
            return {'FINISHED'}
        ob = bpy.data.objects.get(self.name)
        if ob is None or ob.name not in context.view_layer.objects:
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
    """Hide / show this part (a group: all its parts; a collection: the collection)"""
    bl_idname = 'mch.layer_eye'
    bl_label = 'Hide / Show Layer'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    name: StringProperty()
    coll: BoolProperty(default=False, options={'SKIP_SAVE'})

    def execute(self, context):
        from . import groups
        if self.coll:
            c = bpy.data.collections.get(self.name)
            lc = layer_coll(context, c) if c is not None else None
            if lc is None:
                return {'CANCELLED'}
            if lc.exclude:
                lc.exclude = False
                lc.hide_viewport = False
            else:
                lc.hide_viewport = not lc.hide_viewport
            return {'FINISHED'}
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


class MCH_OT_layer_rename(bpy.types.Operator):
    """Rename this part, group or collection (in the Layers panel: click its row twice)"""
    bl_idname = 'mch.layer_rename'
    bl_label = 'Rename'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    name: StringProperty(options={'SKIP_SAVE'})
    coll: BoolProperty(default=False, options={'SKIP_SAVE'})
    new_name: StringProperty(name='Name', options={'SKIP_SAVE'})

    def invoke(self, context, event):
        self.new_name = self.name
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        col = self.layout.column()
        col.activate_init = True                # (typing goes straight into the name, as Blender's F2)
        col.prop(self, 'new_name', text='')

    def execute(self, context):
        from . import groups, side_panel
        new = self.new_name.strip()
        if not new:
            return {'CANCELLED'}
        if self.coll:
            c = bpy.data.collections.get(self.name)
            if c is None:
                return {'CANCELLED'}
            c.name = new
            got = c.name
        else:
            ob = bpy.data.objects.get(self.name)
            if ob is None:
                return {'CANCELLED'}
            if groups.is_group(ob):
                got = groups.rename(context, ob, new)
            else:
                ob.name = new
                got = ob.name
        side_panel.dirty()
        self.report({'INFO'}, f'Renamed: {self.name} -> {got}')
        return {'FINISHED'}


class MCH_OT_layer_group_op(bpy.types.Operator):
    """A collection or a group as one piece (0.24.95): Origin - its origin to the middle of its parts; Mirror - a live
    mirrored copy of it all (across X at the world centre unless set otherwise in Groups; again: off).  A collection
    is made a group in place the first time (a handle at its middle; its parts stay in it - Ungroup takes the handle
    away, the collection stays)"""
    bl_idname = 'mch.layer_group_op'
    bl_label = 'Collection / Group'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    name: StringProperty()
    coll: BoolProperty(default=False, options={'SKIP_SAVE'})
    action: StringProperty(default='ORIGIN', options={'SKIP_SAVE'})

    def execute(self, context):
        from . import groups, side_panel
        if context.mode != 'OBJECT':
            self.report({'WARNING'}, 'Object Mode first')
            return {'CANCELLED'}
        if self.coll:
            c = bpy.data.collections.get(self.name)
            g = groups.adopt(context, c) if c is not None else None
        else:
            g = bpy.data.objects.get(self.name)
        if not groups.is_group(g):
            self.report({'WARNING'}, f'{self.name}: no parts to work on')
            return {'CANCELLED'}
        if self.action == 'MIRROR':
            on = groups.repeat_mode(g) != 'MIRROR'
            groups.set_repeat(context, g, mode='MIRROR' if on else 'OFF')       # (its axes: X unless set)
            msg = f'{g.name}: Mirror ' + ('on' if on else 'off')
        else:
            groups.recenter(context, g)
            msg = f'{g.name}: origin to the middle of its parts'
        side_panel.dirty()
        self.report({'INFO'}, msg)
        return {'FINISHED'}


CLASSES = (MCH_OT_layer_pick, MCH_OT_layer_eye, MCH_OT_layer_rename, MCH_OT_layer_group_op)


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
