"""MECHA LAB workspace UI.

Layout inside the dedicated ``MECHA LAB`` workspace tab:

* LEFT   - big icon + name tool list.  Hosted by a narrow Properties editor in
           its Tool tab (``MCH_PT_tool_list``), created next to the 3D View.
           The native T-toolbar also carries the Cut / Split / Mask tools.
* TOP-LEFT of the viewport - the shared shape palette, drawn in the 3D View
  Tool Header (native buttons, no GPU hit-testing): Lasso, Curve Lasso,
  Rectangle, Circle, Ellipse, Brush Stroke + PNG thumbnails.
* RIGHT  - ``MCH_PT_main`` in the Sidebar shows the settings of ONE tool.

Space opens the same tool list as a large-icon popup; RMB in a drawing tool
opens the shape popup.  All custom hotkeys poll the active workspace, so in
every other workspace the key falls through to Blender's own binding.  The
workspace is created only on request (button / menu); the startup file is
never written unless the user clicks "Save as Startup" and confirms.
"""
from __future__ import annotations

import os

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, StringProperty

from . import primitive_place
from . import screw_stamp
from . import tool_state as ts

ADDON_ID = __package__
ICON_DIR = os.path.join(os.path.dirname(__file__), 'icons')
_icons = None
_keymaps = []
_tools_registered = False

_ORTHO_LOCK_KEY = "mch_ortho_lock"
_ORTHO_REFRESH = 0.17


# -----------------------------------------------------------------------------
# Preferences / icons
# -----------------------------------------------------------------------------


def prefs():
    try:
        return bpy.context.preferences.addons[ADDON_ID].preferences
    except (KeyError, AttributeError):
        return None


def pref(name, default=True):
    p = prefs()
    return getattr(p, name, default) if p is not None else default


def isz(base):
    """Thumbnail size for ``template_icon`` scaled by Preferences > Icon Size (0.14.2)."""
    try:
        f = float(pref('icon_scale', 1.0))
    except (TypeError, ValueError):
        f = 1.0
    return max(0.5, base * f)


def dial_factor():
    """0.18.2: Blender's dial counts the other way round to the shape turn we
    apply, so dials turned the shape opposite to the mouse.  -1 fixes it;
    Preferences / Icon Size panel 'Flip Dial Turning' switches it back."""
    return -1.0 if pref('dial_flip', True) else 1.0


def handle_scale():
    """Multiplier for the viewport handles (station / ghost gizmos)."""
    try:
        return max(0.2, float(pref('handle_scale', 1.0)))
    except (TypeError, ValueError):
        return 1.0


# 0.14.3: icon sizes survive a restart even when Blender's preferences are not
# saved (Auto-Save Preferences off): they are kept in the add-on's own small
# file in the user config folder.  Blender's own preference file is untouched.
SIZE_KEYS = ('icon_scale', 'toolbar_scale', 'handle_scale')
_SIZE_MUTE = [False]


def sizes_path():
    try:
        folder = bpy.utils.user_resource('CONFIG', path='mecha_lab', create=True)
    except (TypeError, ValueError, RuntimeError, OSError):
        return ''
    return os.path.join(folder, 'ui_sizes.json') if folder else ''


def save_sizes(p=None):
    import json
    p = p or prefs()
    path = sizes_path()
    if p is None or not path or _SIZE_MUTE[0]:
        return False
    try:
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump({k: float(getattr(p, k)) for k in SIZE_KEYS}, fh)
        return True
    except OSError:
        return False


def load_sizes(p=None):
    import json
    p = p or prefs()
    path = sizes_path()
    if p is None or not path or not os.path.isfile(path):
        return False
    try:
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return False
    _SIZE_MUTE[0] = True
    try:
        for k in SIZE_KEYS:
            if isinstance(data.get(k), (int, float)):
                setattr(p, k, float(data[k]))
    finally:
        _SIZE_MUTE[0] = False
    return True


def _sizes_changed(self, context):
    save_sizes(self)
    try:
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()
    except (AttributeError, ReferenceError):
        pass


def _deferred_load_sizes():
    load_sizes()
    return None


def icon_id(stem):
    global _icons
    if _icons is None:
        return 0
    if stem not in _icons:
        path = os.path.join(ICON_DIR, stem + '.png')
        if not os.path.isfile(path):
            return 0
        _icons.load(stem, path, 'IMAGE')
    return _icons[stem].icon_id


def _load_icons():
    global _icons
    try:
        import bpy.utils.previews
        _icons = bpy.utils.previews.new()
    except Exception:   # pragma: no cover - previews unavailable
        _icons = None


def _free_icons():
    global _icons
    if _icons is not None:
        import bpy.utils.previews
        bpy.utils.previews.remove(_icons)
    _icons = None


def _icon_kw(stem, fallback):
    iid = icon_id(stem)
    return {'icon_value': iid} if iid else {'icon': fallback}


# -----------------------------------------------------------------------------
# Workspace-scoped orthographic viewport lock (never modifies global Blender
# navigation preferences). Blender Auto Perspective can revert NumPad 5 / an
# orthographic view as soon as the user orbits; this lock restores ORTHO only
# in workspaces explicitly opted in by the user.
# -----------------------------------------------------------------------------


def _force_ortho(area):
    if area.type != 'VIEW_3D':
        return
    space = area.spaces.active
    if space is None or space.type != 'VIEW_3D':
        return
    rv3d = space.region_3d
    if rv3d is not None and rv3d.view_perspective == 'PERSP':      # leave camera views alone
        rv3d.view_perspective = 'ORTHO'
        area.tag_redraw()


def _ortho_watchdog():
    """Lightweight UI-only guard; stop when no open window uses this lock."""
    try:
        wm = bpy.context.window_manager
        if wm is None:
            return None
        active = False
        for window in wm.windows:
            ws = window.workspace
            if ws is None or not ws.get(_ORTHO_LOCK_KEY, False):
                continue
            active = True
            for area in window.screen.areas:
                _force_ortho(area)
        return _ORTHO_REFRESH if active else None
    except (ReferenceError, RuntimeError, AttributeError):
        return None


def _ensure_ortho_timer():
    if not bpy.app.timers.is_registered(_ortho_watchdog):
        bpy.app.timers.register(_ortho_watchdog, first_interval=_ORTHO_REFRESH)


@bpy.app.handlers.persistent
def _ortho_on_load(_dummy=None):
    """Re-arm the Ortho Lock after opening a file saved with the lock ON
    (v0.7.2 only started the timer when the button was pressed)."""
    if any(ws.get(_ORTHO_LOCK_KEY, False) for ws in bpy.data.workspaces):
        _ensure_ortho_timer()


class MCH_OT_ortho_lock(bpy.types.Operator):
    bl_idname = 'mch.ortho_lock'
    bl_label = 'Orthographic Lock (No Perspective)'
    bl_description = ('Toggle persistent orthographic viewport in the current workspace. '
                      'Unlike Numpad 5, orbiting will not switch it back to perspective.')
    bl_options = {'REGISTER', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.workspace is not None and context.screen is not None

    def execute(self, context):
        ws = context.workspace
        enabled = not bool(ws.get(_ORTHO_LOCK_KEY, False))
        ws[_ORTHO_LOCK_KEY] = enabled
        if enabled:
            for area in context.screen.areas:
                _force_ortho(area)
            _ensure_ortho_timer()
        else:
            # Pressing the same button again returns to ordinary perspective.
            # This is intuitive for a two-state "Ortho / Perspective" toggle.
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    space = area.spaces.active
                    if space and space.type == 'VIEW_3D' and space.region_3d:
                        space.region_3d.view_perspective = 'PERSP'
                    area.tag_redraw()
        self.report({'INFO'}, 'Orthographic lock ON' if enabled else 'Orthographic lock OFF')
        return {'FINISHED'}


def _deferred_ortho_check():
    try:
        _ortho_on_load()
    except (AttributeError, ReferenceError, RuntimeError):
        pass
    return None


_HOTKEY_IDS = ('mch.tool_pie', 'mch.toggle_last_tool', 'mch.select_move_key', 'mch.space_tools', 'mch.hotkey',
               'mch.concept_hold')


def hotkey_items(context=None):
    """Mecha keymap items looked up FRESH (never cached between redraws: a held
    KeyMapItem reference can point to freed memory after Blender rebuilds its
    keymaps, and drawing it crashes Blender).  The user keyconfig is what
    Blender actually uses and what Preferences > Keymap saves."""
    wm = (context or bpy.context).window_manager
    if wm is None:
        return []
    out, seen = [], set()
    for kc in (wm.keyconfigs.user, wm.keyconfigs.addon):
        if kc is None:
            continue
        for km_name in ('3D View', 'Object Mode'):
            km = kc.keymaps.get(km_name)
            if km is None:
                continue
            for item in km.keymap_items:
                if item.idname not in _HOTKEY_IDS:
                    continue
                key = hotkey_id(item) + (len([o for o in out if hotkey_id(o[1]) == hotkey_id(item)]),)
                if key in seen:
                    continue
                seen.add(key)
                out.append((km, item))
        if out:
            break
    return out


HOTKEY_LABELS = {'BOOLEAN': 'Boolean Difference', 'CUT': 'Cut', 'SPLIT': 'Split (nothing selected)',
                 'PLATE': 'Armor Plate', 'MIRROR': 'Mirror', 'SHAPES': 'Lasso Shape Menu',
                 'REMESH': 'Remesh + Smooth (run now)'}
# tools whose key is one of the named hotkeys above (C = Cut, S = Split, Alt+A = Armor Plate)
TOOL_ACTIONS = {'CUT': 'CUT', 'SPLIT': 'SPLIT', 'PLATE': 'PLATE'}
HOTKEYS_FILE = 'hotkeys.json'


def tool_key_ids():
    return [t[0] for t in ts.VISIBLE_TOOLS if t[0] not in TOOL_ACTIONS]


def hotkey_id(item):
    """(operator, action, tool) - what a Mecha key item does (stable across sessions)."""
    if item.idname != 'mch.hotkey':
        return (item.idname, '', '')
    action = getattr(item.properties, 'action', '')
    return (item.idname, action, getattr(item.properties, 'tool', '') if action == 'TOOL' else '')


def _hotkeys_path():
    import os
    try:
        d = bpy.utils.user_resource('CONFIG', path='mecha_lab', create=True)
    except (TypeError, ValueError, RuntimeError, OSError):
        return None
    return os.path.join(d, HOTKEYS_FILE) if d else None


_KEY_FIELDS = ('type', 'value', 'ctrl', 'shift', 'alt', 'oskey', 'key_modifier')


def save_hotkeys(context=None):
    """0.24.17 the keys as set in the Hotkeys box -> config/mecha_lab/hotkeys.json (Mecha Lab's own file)."""
    import json
    path = _hotkeys_path()
    if path is None:
        return 0
    rows = []
    for _km, item in hotkey_items(context):
        rec = {k: (bool(getattr(item, k)) if k in ('ctrl', 'shift', 'alt', 'oskey') else getattr(item, k))
               for k in _KEY_FIELDS}
        rec['id'] = list(hotkey_id(item))
        rows.append(rec)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump({'version': 1, 'keys': rows}, fh, indent=1)
    return len(rows)


def load_hotkeys(items):
    """Apply the saved keys to freshly made key items (first item of each kind)."""
    import json
    import os
    path = _hotkeys_path()
    if path is None or not os.path.isfile(path):
        return 0
    try:
        with open(path, encoding='utf-8') as fh:
            rows = json.load(fh).get('keys', [])
    except (OSError, ValueError, AttributeError):
        return 0
    by_id = {}
    for it in items:
        try:
            by_id.setdefault(hotkey_id(it), it)
        except ReferenceError:
            continue
    done = 0
    for rec in rows:
        it = by_id.get(tuple(rec.get('id', ())))
        if it is None:
            continue
        try:
            for k in _KEY_FIELDS:
                if k in rec:
                    setattr(it, k, rec[k])
            done += 1
        except (TypeError, ValueError, AttributeError):
            continue
    return done


def draw_hotkey_editor(layout, context=None):
    """Editable keys of the Mecha hotkeys (menus, B / C, Alt+X / S / Alt+A, L) and one per tool of the left
    list (0.24.17); Save keeps them for the next Blender start."""
    box = layout.box()
    box.label(text='Hotkeys (MECHA LAB only)', icon='KEYINGSET')
    items = hotkey_items(context)
    by_id = {}
    for km, item in items:
        by_id.setdefault(hotkey_id(item), item)
    for km, item in items:
        hid = hotkey_id(item)
        if hid[1] == 'TOOL' or hid[1] in TOOL_ACTIONS.values():
            continue
        row = box.row(align=True)
        label = {'mch.select_move_key': 'Select / Move', 'mch.tool_pie': 'Tool Pie',
                 'mch.toggle_last_tool': 'Select <-> Last Tool',
                 'mch.space_tools': 'Big Tool Menu',
                 'mch.concept_hold': 'Concept Move (hold + drag)'}.get(hid[0], HOTKEY_LABELS.get(hid[1], 'Hotkey'))
        row.label(text=label)
        if hid[0] == 'mch.concept_hold':                 # the key you hold; the drag is the left mouse
            row.prop(item, 'key_modifier', text='', event=True)
        else:
            row.prop(item, 'type', text='', full_event=True)
    box.label(text='Tools (left list)', icon='TOOL_SETTINGS')
    col = box.column(align=True)
    for t in ts.VISIBLE_TOOLS:
        tid = t[0]
        item = by_id.get(('mch.hotkey', TOOL_ACTIONS[tid], '')) if tid in TOOL_ACTIONS else \
            by_id.get(('mch.hotkey', 'TOOL', tid))
        if item is None:
            continue
        row = col.row(align=True)
        row.label(text=t[1])
        row.prop(item, 'type', text='', full_event=True)
    row = box.row(align=True)
    row.operator('mch.hotkeys_save', icon='FILE_TICK')
    row.operator('mch.hotkeys_reset', icon='LOOP_BACK')


def draw_ortho_button(layout, context, text='Ortho Lock'):
    locked = bool(context.workspace and context.workspace.get(_ORTHO_LOCK_KEY, False))
    layout.operator('mch.ortho_lock', text=text, icon='LOCKED' if locked else 'UNLOCKED', depress=locked)


# -----------------------------------------------------------------------------
# Tool activation
# -----------------------------------------------------------------------------


def _view3d_override(context):
    """Window/area/region of a 3D View, for operators started from another
    editor (the left tool list is a Properties editor): ``wm.tool_set_by_id``
    must run in a 3D View context or the native tool silently stays as is."""
    if context.area is not None and context.area.type == 'VIEW_3D':
        return None
    win = context.window
    screen = win.screen if win is not None else context.screen
    if screen is None:
        return None
    areas = sorted((a for a in screen.areas if a.type == 'VIEW_3D'), key=lambda a: -a.width * a.height)
    for area in areas:
        region = next((r for r in area.regions if r.type == 'WINDOW'), None)
        if region is not None:
            return {'window': win, 'screen': screen, 'area': area, 'region': region}
    return None


def set_native_tool(context, idname):
    ov = _view3d_override(context)
    if ov:
        with context.temp_override(**ov):
            bpy.ops.wm.tool_set_by_id(name=idname, space_type='VIEW_3D')
    else:
        bpy.ops.wm.tool_set_by_id(name=idname, space_type='VIEW_3D')


def activate_mecha_tool(context, tool_id):
    """Select a Mecha tool; drawing tools also become the native active tool."""
    settings = context.scene.mch_settings
    try:
        previous = ts.effective_tool(context)
    except (AttributeError, KeyError, TypeError):
        previous = None
    if previous in {'BASE', 'CBASE'} and tool_id != previous:
        from . import base_mesh
        base_mesh.auto_apply_session(context)     # F02: only this tool's own live results
    settings.mch_active_tool = tool_id
    if tool_id == 'CBASE':
        from . import base_mesh
        base_mesh.init_creature_defaults(context.scene)
    # 0.23.4: the normal Armor / Cloth Plate (the Creature brushes switch their flag back on after this)
    for pg, tid in (('mch_wrinkle', 'WRINKLE'), ('mch_plate', 'PLATE')):
        if tool_id == tid and hasattr(context.scene, pg):
            getattr(context.scene, pg).creature = False
    try:
        from . import bottom_bar
        bottom_bar.note_tool(context, tool_id)
    except (AttributeError, ImportError):
        pass
    native = ts.TOOL_BY_ID[tool_id][5]
    current = ts.native_tool_id(context)
    try:
        if native:
            if context.mode != 'OBJECT' and context.active_object is not None:
                bpy.ops.object.mode_set(mode='OBJECT')
            if current != native:
                set_native_tool(context, native)
        elif current in ts.NATIVE_TO_TOOL:
            set_native_tool(context, 'builtin.select_box')
    except (RuntimeError, TypeError) as ex:
        print('[Mecha Lab] tool switch:', ex)
    # If the toolbar could not be switched, the explicit choice still wins
    # (see tool_state.effective_tool) instead of the panel staying on Cut.
    if native:
        if 'mch_native_at_choice' in settings:
            del settings['mch_native_at_choice']
    else:
        settings['mch_native_at_choice'] = ts.native_tool_id(context)
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type in {'VIEW_3D', 'PROPERTIES'}:
                area.tag_redraw()
    if tool_id == 'PRIMITIVE' and previous != 'PRIMITIVE':
        primitive_place.ensure_placed(context)   # 0.14.3: the ghost appears only once a shape is picked
    if tool_id in {'TUBE', 'TUBE_SAME'} and previous != tool_id:
        # 0.23: picking Tube starts drawing right away (Enter / right click ends; the tube stays live)
        # 0.24.10 Line Curve: its own tool; 0.24.17 a tube of one thickness everywhere
        try:
            from . import curve_tube
            ob = context.active_object
            if tool_id == 'TUBE_SAME':      # Line Curve: edit the active Line Curve or start a new one
                curve_tube.start_draw(context, new=not curve_tube.is_line_curve(ob), mode='LINE')
            else:
                curve_tube.start_draw(context, new=not curve_tube.is_tube(ob) or curve_tube.is_line_curve(ob))
        except (RuntimeError, AttributeError, TypeError) as ex:
            print('[Mecha Lab] tube start:', ex)
    if tool_id == 'MIRROR' and previous != 'MIRROR':
        # 0.11.3: picking Mirror starts the live lean mirror right away
        try:
            from . import mirror_tools
            mirror_tools.start_lean_mirror(context)
        except (RuntimeError, TypeError, AttributeError) as ex:
            print('[Mecha Lab] mirror start:', ex)


# -----------------------------------------------------------------------------
# Native WorkSpaceTools (left T-toolbar, one undo step per stroke)
# -----------------------------------------------------------------------------


def _lasso_sketch_keys():
    from . import lasso_sketch
    return lasso_sketch.KEYMAP       # 0.19.3: Enter / Alt+Enter / Backspace / Esc while a sketch exists


def lasso_sketch_modes():
    from . import lasso_sketch
    return lasso_sketch.MODES


def _tool_keymap(mode):
    return (
        # 0.24.31 hold D + drag = Concept Move (before the tool's own left mouse)
        ('mch.concept_hold', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'key_modifier': 'D'}, None),
        ('mch.cut_stroke', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'any': True},
         {'properties': [('mode', mode)]}),
        ('mch.rmb_gate', {'type': 'RIGHTMOUSE', 'value': 'PRESS'},
         {'properties': [('popup', 'PROFILE' if mode in {'BASE', 'CBASE'} else 'SHAPE')]}),
        ('mch.toggle_targets', {'type': 'T', 'value': 'PRESS'}, None),
        # 0.24.34 F + mouse left / right = brush size (like Concept Move)
        ('mch.brush_resize', {'type': 'F', 'value': 'PRESS'}, None),
    ) + ((
        # 0.14.1 Base Mesh sketch: Enter = mesh, Alt+Enter = cut into mesh, Esc = clear, Backspace = last shape
        ('mch.base_sketch_key', {'type': 'RET', 'value': 'PRESS'}, None),
        ('mch.base_sketch_key', {'type': 'NUMPAD_ENTER', 'value': 'PRESS'}, None),
        ('mch.base_sketch_key', {'type': 'RET', 'value': 'PRESS', 'alt': True}, {'properties': [('cutter', True)]}),
        ('mch.base_sketch_key', {'type': 'NUMPAD_ENTER', 'value': 'PRESS', 'alt': True},
         {'properties': [('cutter', True)]}),
        ('mch.base_sketch_clear', {'type': 'ESC', 'value': 'PRESS'}, None),
        ('mch.base_sketch_undo', {'type': 'BACK_SPACE', 'value': 'PRESS'}, None),
    ) if mode in {'BASE', 'CBASE'} else ()) + (_lasso_sketch_keys() if mode in lasso_sketch_modes() else ()) + (
        # Esc with no stroke pending: back to Blender's Select Box tool.
        ('mch.exit_tool', {'type': 'ESC', 'value': 'PRESS'}, None),
        # B06: R / Shift+R rotate a PNG stamp (poll fails for other shapes -> Blender's R).
        ('mch.stamp_rotate', {'type': 'R', 'value': 'PRESS'}, {'properties': [('sign', 1)]}),
        ('mch.stamp_rotate', {'type': 'R', 'value': 'PRESS', 'shift': True}, {'properties': [('sign', -1)]}),
        # 0.24.21 [ / ] = Line Width (the band in Line mode), like a brush size
        ('mch.line_width_step', {'type': 'LEFT_BRACKET', 'value': 'PRESS'}, {'properties': [('factor', 1.0 / 1.15)]}),
        ('mch.line_width_step', {'type': 'RIGHT_BRACKET', 'value': 'PRESS'}, {'properties': [('factor', 1.15)]}),
    )


def _draw_tool_settings(context, layout, tool):
    if context.region and context.region.type == 'TOOL_HEADER':
        return   # the shape palette is drawn by draw_shape_palette()
    layout.label(text='Settings: Sidebar (N) > Mecha Lab', icon='INFO')


class MCH_TOOL_cut(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.cut'
    bl_label = 'Mecha Cut'
    bl_description = ('Draw a shape to remove the inside of the mesh (Alt: keep inside).\n'
                      'RMB: shapes, RMB double-click: exit')
    bl_icon = 'ops.sculpt.lasso_trim'
    bl_widget = None
    bl_keymap = _tool_keymap('CUT')

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)

    def draw_cursor(context, tool, xy):
        from . import cut_engine
        cut_engine.draw_stamp_cursor(context, xy)


class MCH_TOOL_split(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.split'
    bl_label = 'Mecha Split'
    bl_description = 'Draw a shape to split the mesh into two solid parts'
    bl_icon = 'ops.mesh.bisect'
    bl_widget = None
    bl_keymap = _tool_keymap('SPLIT')

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)

    def draw_cursor(context, tool, xy):
        from . import cut_engine
        cut_engine.draw_stamp_cursor(context, xy)


class MCH_TOOL_box_hide(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.box_hide'
    bl_label = 'Mecha Box Hide'
    bl_description = 'Draw a shape over meshes to hide what is inside it (Alt: show it again)'
    bl_icon = 'ops.generic.select_box'
    bl_widget = None
    bl_keymap = _tool_keymap('HIDE')

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)

    def draw_cursor(context, tool, xy):
        from . import cut_engine
        cut_engine.draw_stamp_cursor(context, xy)


class MCH_TOOL_plate_detail(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.plate_detail'
    bl_label = 'Mecha Plate Detail'
    bl_description = 'Draw an outline on a plate: low trim detail (flat inside, stepped layers, screws)'
    bl_icon = 'ops.mesh.inset'
    bl_widget = None
    bl_keymap = _tool_keymap('DETAIL')

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)


class MCH_TOOL_plate_detail3(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.plate_detail3'
    bl_label = 'Mecha Plate Detail 3'
    bl_description = 'Draw an outline on a plate: a flat raised panel, straight walls, no trim layers'
    bl_icon = 'ops.mesh.inset'
    bl_widget = None
    bl_keymap = _tool_keymap('DETAIL3')

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)


class MCH_TOOL_plate_detail2(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.plate_detail2'
    bl_label = 'Mecha Plate Detail 2'
    bl_description = 'Draw an outline on a surface: it rises smoothly inside to a flat top'
    bl_icon = 'ops.mesh.extrude_region_shrink_fatten'
    bl_widget = None
    bl_keymap = _tool_keymap('DETAIL2')

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)


class MCH_TOOL_screw_stamp(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.screw_stamp'
    bl_label = 'Mecha Screw Stamp'
    bl_description = 'Click on a surface: a screw head aligned to it. Alt + click: remove, Esc: exit'
    bl_icon = 'ops.generic.cursor'
    bl_widget = None
    bl_keymap = screw_stamp.TOOL_KEYMAP

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)


class MCH_TOOL_mask(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.mask'
    bl_label = 'Mecha Mask'
    bl_description = 'Paint a face mask with the shared shapes (Alt: erase)'
    bl_icon = 'ops.sculpt.lasso_mask'
    bl_widget = None
    bl_keymap = _tool_keymap('MASK')

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)


class MCH_TOOL_base_mesh(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.base_mesh'
    bl_label = 'Mecha Base Mesh'
    bl_description = ('Draw an outline to create a NEW solid (original meshes untouched).\n'
                      'RMB: Flat / Chamfer / Bevel / Dome profiles, RMB double-click or Esc: exit')
    bl_icon = 'ops.mesh.primitive_cube_add_gizmo'
    bl_widget = None
    bl_keymap = _tool_keymap('BASE')

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)


class MCH_TOOL_creature_base(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.creature_base'
    bl_label = 'Mecha Creature Base Mesh'
    bl_description = ('Draw an outline: a NEW rounded solid - Puff (round), Ridge (diamond), Pillow (flat, round '
                      'edge).\nRMB: profiles, RMB double-click or Esc: exit')
    bl_icon = 'ops.mesh.primitive_sphere_add_gizmo'
    bl_widget = None
    bl_keymap = _tool_keymap('CBASE')

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)


class MCH_TOOL_creature_plate(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.creature_plate'
    bl_label = 'Mecha Creature Plate'
    bl_description = ('Draw on a mesh: a rounded plate on the surface - Puff / Ridge / Pillow, Height and End '
                      'Height, Edge.\nRMB: shapes, Esc: exit')
    bl_icon = 'ops.mesh.extrude_region_move'
    bl_widget = None
    bl_keymap = _tool_keymap('CPLATE')

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)


class MCH_TOOL_belt_maker(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.belt_maker'
    bl_label = 'Mecha Belt Maker'
    bl_description = ('Draw a line over a mesh: a strap around it there (Wrap) or along the line (Follow).\n'
                      'Enter / double-click: make it, Esc: exit')
    bl_icon = 'ops.curve.draw'
    bl_widget = None
    bl_keymap = _tool_keymap('BELT')

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)


class MCH_TOOL_creature_spike(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.creature_spike'
    bl_label = 'Mecha Creature Spike'
    bl_description = ('Draw a line over a mesh: spikes stand along it (presets mixed at random).\n'
                      'Enter / double-click: make them, Esc: exit')
    bl_icon = 'ops.curve.draw'
    bl_widget = None
    bl_keymap = _tool_keymap('SPIKE')

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)


class MCH_TOOL_creature_scales(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.creature_scales'
    bl_label = 'Mecha Creature Scales'
    bl_description = ('Draw a line over a mesh: overlapping scales along it (presets mixed at random).\n'
                      'Enter / double-click: make them, Esc: exit')
    bl_icon = 'ops.curve.draw'
    bl_widget = None
    bl_keymap = _tool_keymap('SCALES')

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)


class MCH_TOOL_scale_brush(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.scale_brush'
    bl_label = 'Mecha Scale Brush'
    bl_description = ('Lasso an area on a mesh: it fills with scales packed close together.\n'
                      'RMB: shapes, Esc: exit')
    bl_icon = 'ops.mesh.primitive_sphere_add_gizmo'
    bl_widget = None
    bl_keymap = _tool_keymap('SBRUSH')

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)


class MCH_TOOL_bridge_patch(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.bridge_patch'
    bl_label = 'Mecha Bridge Patch'
    bl_description = ('Lasso across two meshes: a smooth patch fills the gap between them (front side).\n'
                      'RMB: shapes, Esc: exit')
    bl_icon = 'ops.mesh.loopcut_slide'
    bl_widget = None
    bl_keymap = _tool_keymap('BRIDGE')

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)


class MCH_TOOL_flower_plate(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.flower_plate'
    bl_label = 'Mecha Flower Plate'
    bl_description = ('Draw an outline on a mesh: it grows from there - attached where you start, bending away.\n'
                      'RMB: shapes, Esc: exit')
    bl_icon = 'ops.mesh.extrude_region_move'
    bl_widget = None
    bl_keymap = _tool_keymap('FLOWER')

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)


class MCH_TOOL_cape(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.cape'
    bl_label = 'Mecha Cape'
    bl_description = ('Draw on a body from the side the cape hangs on: the top of the drawing is the collar.\n'
                      'RMB: shapes, Esc: exit')
    bl_icon = 'ops.mesh.extrude_region_move'
    bl_widget = None
    bl_keymap = _tool_keymap('CAPE')

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)


class MCH_TOOL_scarf_cape(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.scarf_cape'
    bl_label = 'Mecha Scarf Cape'
    bl_description = ('Draw a line across a body: a cape hangs from it with fold lines across (Gravity sags the middle).\n'
                      'RMB: shapes, Esc: exit')
    bl_icon = 'ops.mesh.extrude_region_move'
    bl_widget = None
    bl_keymap = _tool_keymap('SCAPE')

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)


class MCH_TOOL_creature_hair(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.creature_hair'
    bl_label = 'Mecha Creature Hair'
    bl_description = ('Draw the scalp area on a head: dreadlocks / tentacles / quills grow there.\n'
                      'RMB: shapes, Esc: exit')
    bl_icon = 'ops.mesh.extrude_region_move'
    bl_widget = None
    bl_keymap = _tool_keymap('HAIR')

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)


class MCH_TOOL_surface_draw(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.surface_draw'
    bl_label = 'Mecha Surface Draw'
    bl_description = ('Draw on a mesh: a raised band along the line (same width / height every stroke).\n'
                      'Alt + draw / lasso: cut that area out of it.  Esc: exit')
    bl_icon = 'ops.gpencil.draw'
    bl_widget = None
    bl_keymap = _tool_keymap('SDRAW')

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)


class MCH_TOOL_clothing(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.clothing'
    bl_label = 'Mecha Clothing'
    bl_description = ('Front view: draw the outline of a top or pants over a body.\n'
                      'RMB: shapes, Esc: exit')
    bl_icon = 'ops.mesh.extrude_region_move'
    bl_widget = None
    bl_keymap = _tool_keymap('GARMENT')

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)


class MCH_TOOL_hood(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.hood'
    bl_label = 'Mecha Hood'
    bl_description = ('Look at the face and draw round the head: a live hood.\n'
                      'RMB: shapes, Esc: exit')
    bl_icon = 'ops.mesh.extrude_region_move'
    bl_widget = None
    bl_keymap = _tool_keymap('HOOD')

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)


class MCH_TOOL_scarf(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.scarf'
    bl_label = 'Mecha Scarf'
    bl_description = ('Look at the front and draw round the neck: a live scarf.\n'
                      'RMB: shapes, Esc: exit')
    bl_icon = 'ops.mesh.extrude_region_move'
    bl_widget = None
    bl_keymap = _tool_keymap('SCARF')

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)


class MCH_TOOL_surface_curve(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.surface_curve'
    bl_label = 'Mecha Surface Curve'
    bl_description = ('Draw along a mesh (hold and drag, release): a curve lies on it, editable like a Mesh '
                      'Curve.\nEsc: exit')
    bl_icon = 'ops.curve.draw'
    bl_widget = None
    bl_keymap = _tool_keymap('SCURVE')

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)


class MCH_TOOL_armor_plate(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.armor_plate'
    bl_label = 'Mecha Armor Plate'
    bl_description = ('Draw on a mesh: a separate armour plate of new clean faces (no retopology).\n'
                      'Mouse wheel while drawing: profile, RMB: shapes, Esc: exit')
    bl_icon = 'ops.mesh.extrude_region_move'
    bl_widget = None
    bl_keymap = _tool_keymap('PLATE')

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)


class MCH_TOOL_cloth_wrinkle(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.cloth_wrinkle'
    bl_label = 'Mecha Cloth Plate'
    bl_description = ('Draw on a mesh: a separate padded cloth panel (puff, edge roll, seam pinch, stitching).\n'
                      'RMB: shapes, Esc: exit')
    bl_icon = 'ops.mesh.extrude_region_move'
    bl_widget = None
    bl_keymap = _tool_keymap('WRINKLE')

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)


class MCH_TOOL_primitive(bpy.types.WorkSpaceTool):
    """0.14: a real tool so click / Enter / Alt+Enter reach the ghost shape
    before Blender's Select Box tool takes the click."""
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.primitive'
    bl_label = 'Mecha Primitive'
    bl_description = ('Semi-transparent shape with handles. Enter: merge into the mesh it touches, '
                      'Alt+Enter: subtract.\nClick: move the shape there, drag: box select, RMB: shapes, Esc: exit')
    bl_icon = 'ops.mesh.primitive_cylinder_add_gizmo'
    bl_widget = None
    bl_keymap = primitive_place.TOOL_KEYMAP

    def draw_settings(context, layout, tool):
        _draw_tool_settings(context, layout, tool)


NATIVE_TOOLS = (MCH_TOOL_cut, MCH_TOOL_split, MCH_TOOL_base_mesh, MCH_TOOL_primitive, MCH_TOOL_armor_plate,
                MCH_TOOL_cloth_wrinkle, MCH_TOOL_box_hide, MCH_TOOL_plate_detail, MCH_TOOL_plate_detail2, MCH_TOOL_plate_detail3,
                MCH_TOOL_screw_stamp, MCH_TOOL_creature_base, MCH_TOOL_creature_plate,
                MCH_TOOL_belt_maker, MCH_TOOL_creature_spike, MCH_TOOL_creature_scales,
                MCH_TOOL_scale_brush, MCH_TOOL_bridge_patch, MCH_TOOL_flower_plate, MCH_TOOL_surface_curve, MCH_TOOL_cape, MCH_TOOL_scarf_cape, MCH_TOOL_creature_hair, MCH_TOOL_surface_draw, MCH_TOOL_clothing, MCH_TOOL_hood, MCH_TOOL_scarf)   # MCH_TOOL_mask kept, not registered (Mask hidden)


STALE_KEYMAP_IDS = {'mch.stamp_scale'}     # 0.24.5 wheel = stamp size (removed in 0.24.6)


def purge_stale_keymap_items():
    """0.24.7 remove key items of removed Mecha operators left in the add-on keyconfig (e.g. the 0.24.5 wheel =
    stamp size item kept the wheel from zooming after an update without a Blender restart)."""
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon if wm else None
    if kc is None:
        return 0
    removed = 0
    for tool in NATIVE_TOOLS:          # register_tool keeps an existing tool keymap: rebuild it from bl_keymap
        km = kc.keymaps.get('3D View Tool: Object, ' + tool.bl_label)
        if km is not None:
            try:
                kc.keymaps.remove(km)
            except (ReferenceError, RuntimeError):
                pass
    for km in kc.keymaps:
        for item in list(km.keymap_items):
            if item.idname in STALE_KEYMAP_IDS:
                try:
                    km.keymap_items.remove(item)
                    removed += 1
                except (ReferenceError, RuntimeError):
                    pass
    return removed


def register_native_tools():
    global _tools_registered
    if _tools_registered:
        return
    bpy.utils.register_tool(MCH_TOOL_cut, separator=True, group=False)
    bpy.utils.register_tool(MCH_TOOL_split, after={MCH_TOOL_cut.bl_idname}, group=False)
    bpy.utils.register_tool(MCH_TOOL_base_mesh, after={MCH_TOOL_split.bl_idname}, group=False)
    bpy.utils.register_tool(MCH_TOOL_primitive, after={MCH_TOOL_base_mesh.bl_idname}, group=False)
    bpy.utils.register_tool(MCH_TOOL_armor_plate, after={MCH_TOOL_primitive.bl_idname}, group=False)
    bpy.utils.register_tool(MCH_TOOL_cloth_wrinkle, after={MCH_TOOL_armor_plate.bl_idname}, group=False)
    bpy.utils.register_tool(MCH_TOOL_box_hide, after={MCH_TOOL_split.bl_idname}, group=False)
    bpy.utils.register_tool(MCH_TOOL_plate_detail, after={MCH_TOOL_armor_plate.bl_idname}, group=False)
    bpy.utils.register_tool(MCH_TOOL_plate_detail2, after={MCH_TOOL_plate_detail.bl_idname}, group=False)
    bpy.utils.register_tool(MCH_TOOL_plate_detail3, after={MCH_TOOL_plate_detail2.bl_idname}, group=False)
    bpy.utils.register_tool(MCH_TOOL_screw_stamp, after={MCH_TOOL_plate_detail3.bl_idname}, group=False)
    bpy.utils.register_tool(MCH_TOOL_creature_base, after={MCH_TOOL_base_mesh.bl_idname}, group=False)
    bpy.utils.register_tool(MCH_TOOL_creature_plate, after={MCH_TOOL_screw_stamp.bl_idname}, group=False)
    bpy.utils.register_tool(MCH_TOOL_belt_maker, after={MCH_TOOL_creature_plate.bl_idname}, group=False)
    bpy.utils.register_tool(MCH_TOOL_creature_spike, after={MCH_TOOL_belt_maker.bl_idname}, group=False)
    bpy.utils.register_tool(MCH_TOOL_creature_scales, after={MCH_TOOL_creature_spike.bl_idname}, group=False)
    bpy.utils.register_tool(MCH_TOOL_scale_brush, after={MCH_TOOL_creature_scales.bl_idname}, group=False)
    bpy.utils.register_tool(MCH_TOOL_bridge_patch, after={MCH_TOOL_scale_brush.bl_idname}, group=False)
    bpy.utils.register_tool(MCH_TOOL_flower_plate, after={MCH_TOOL_bridge_patch.bl_idname}, group=False)
    bpy.utils.register_tool(MCH_TOOL_surface_curve, after={MCH_TOOL_flower_plate.bl_idname}, group=False)
    bpy.utils.register_tool(MCH_TOOL_cape, after={MCH_TOOL_surface_curve.bl_idname}, group=False)
    bpy.utils.register_tool(MCH_TOOL_scarf_cape, after={MCH_TOOL_cape.bl_idname}, group=False)
    bpy.utils.register_tool(MCH_TOOL_creature_hair, after={MCH_TOOL_scarf_cape.bl_idname}, group=False)
    bpy.utils.register_tool(MCH_TOOL_surface_draw, after={MCH_TOOL_creature_hair.bl_idname}, group=False)
    if ts.EXPERIMENTAL_CLOTH:          # 0.24.31: Clothing / Hood / Scarf hidden until they are ready
        bpy.utils.register_tool(MCH_TOOL_clothing, after={MCH_TOOL_creature_hair.bl_idname}, group=False)
        bpy.utils.register_tool(MCH_TOOL_hood, after={MCH_TOOL_clothing.bl_idname}, group=False)
        bpy.utils.register_tool(MCH_TOOL_scarf, after={MCH_TOOL_hood.bl_idname}, group=False)
    _tools_registered = True


def unregister_native_tools():
    global _tools_registered
    if not _tools_registered:
        return
    for tool in reversed(NATIVE_TOOLS):
        try:
            bpy.utils.unregister_tool(tool)
        except (ValueError, RuntimeError, AttributeError):    # AttributeError: a hidden tool never registered
            pass
    _tools_registered = False


# -----------------------------------------------------------------------------
# Drawing helpers
# -----------------------------------------------------------------------------


def draw_tool_rows(layout, context, scale=2.0):
    """Vertical list: big icon + readable name (left area)."""
    active = ts.effective_tool(context)
    col = layout.column(align=True)
    sm = col.row(align=True)
    sm.scale_y = scale * 0.6
    sm.operator('mch.select_move', icon='RESTRICT_SELECT_OFF')
    col.separator()
    for tid, label, desc, stem, fallback, native, status in ts.VISIBLE_TOOLS:
        row = col.row(align=True)
        iid = icon_id(stem)
        if iid:
            row.template_icon(icon_value=iid, scale=isz(scale))
        sub = row.row(align=True)
        sub.scale_y = scale
        text = label + ('  (todo)' if status == 'TODO' else '')
        kw = {} if iid else {'icon': fallback}
        op = sub.operator('mch.set_tool', text=text, depress=(tid == active), **kw)
        op.tool = tid
        if tid == 'MIRROR':
            col.separator()


def icon_tile(layout, icon, fallback, operator_id, text, scale, depress=False):
    """One tile: the big picture on top, the name button under it.  Returns the
    operator(s) to fill.  (0.15: Blender never enlarges an icon inside a button,
    so the 0.14.3 "icon = button" made tall empty buttons with a tiny icon; the
    picture is back and the name button is what you click.)
    ``icon`` = preview icon id or icon stem."""
    iid = icon_id(icon) if isinstance(icon, str) else int(icon or 0)
    cell = layout.column(align=True)
    if iid:
        cell.template_icon(icon_value=iid, scale=isz(scale))
        return [cell.operator(operator_id, text=text, depress=depress)]
    return [cell.operator(operator_id, text=text, icon=fallback, depress=depress)]


def draw_tool_grid(layout, context, columns=4, scale=3.0, tools=None):
    """Grid of tiles: big icon above a name button (popup / sidebar fallback)."""
    active = ts.effective_tool(context)
    sm = layout.row()
    sm.scale_y = 1.4
    sm.operator('mch.select_move', icon='RESTRICT_SELECT_OFF')
    grid = layout.grid_flow(row_major=True, columns=columns, even_columns=True, even_rows=True, align=False)
    for tid, label, desc, stem, fallback, native, status in tools or ts.VISIBLE_TOOLS:
        text = label + (' (todo)' if status == 'TODO' else '')
        for op in icon_tile(grid, stem, fallback, 'mch.set_tool', text, scale, depress=(tid == active)):
            op.tool = tid


# 0.24.21 sculpt brush presets under the tool list: (label, essentials brush asset, icon stem, fallback icon)
SCULPT_BRUSHES = (
    ('Draw', 'Draw', 'sculpt_draw', 'BRUSH_DATA'),
    ('Clay Strips', 'Clay Strips', 'sculpt_clay', 'BRUSH_DATA'),
    ('Inflate', 'Inflate/Deflate', 'sculpt_inflate', 'BRUSH_DATA'),
    ('Grab', 'Grab', 'sculpt_grab', 'BRUSH_DATA'),
    ('Smooth', 'Smooth', 'sculpt_smooth', 'BRUSH_DATA'),
    ('Crease', 'Crease Polish', 'sculpt_crease', 'BRUSH_DATA'),
)
SCULPT_LIB = 'brushes/essentials_brushes-mesh_sculpt.blend/Brush/'


def sculpt_target(context):
    """The mesh to sculpt: the active one, else the first selected mesh."""
    ob = context.active_object
    if ob is not None and ob.type == 'MESH':
        return ob
    return next((o for o in context.selected_objects if o.type == 'MESH'), None)


def draw_sculpt_grid(layout, context, columns=3, scale=2.2):
    """0.24.21 SCULPT tiles: a click goes to Sculpt Mode on the selected mesh with that brush; Select / Move (top
    of the tool list) or any Mecha tool brings you back to Object Mode."""
    box = layout.box()
    head = box.row()
    head.label(text='SCULPT', icon='SCULPTMODE_HLT')
    if context.mode == 'SCULPT':
        head.operator('mch.select_move', text='Back to Object', icon='OBJECT_DATAMODE')
    current = ''
    if context.mode == 'SCULPT':
        try:
            current = context.tool_settings.sculpt.brush.name
        except AttributeError:
            current = ''
    grid = box.grid_flow(row_major=True, columns=columns, even_columns=True, even_rows=True, align=False)
    for label, asset, stem, fallback in SCULPT_BRUSHES:
        for op in icon_tile(grid, stem, fallback, 'mch.sculpt_brush', label, scale, depress=(current == asset)):
            op.brush = asset
    if sculpt_target(context) is None:
        box.label(text='Select a mesh to sculpt', icon='INFO')


class MCH_OT_sculpt_brush(bpy.types.Operator):
    """0.24.21 Sculpt Mode on the selected mesh with this brush (no workspace / tab change)"""
    bl_idname = 'mch.sculpt_brush'
    bl_label = 'Sculpt Brush'
    bl_options = {'REGISTER'}
    brush: StringProperty(default='Draw')

    @classmethod
    def description(cls, context, properties):
        return f'Sculpt with "{properties.brush}" on the selected mesh (Select / Move goes back to Object Mode)'

    @classmethod
    def poll(cls, context):
        return sculpt_target(context) is not None

    def execute(self, context):
        ob = sculpt_target(context)
        try:
            if context.mode not in {'OBJECT', 'SCULPT'}:
                bpy.ops.object.mode_set(mode='OBJECT')
            if context.view_layer.objects.active != ob:
                context.view_layer.objects.active = ob
            if context.mode != 'SCULPT':
                bpy.ops.object.mode_set(mode='SCULPT')
        except RuntimeError as ex:
            self.report({'ERROR'}, f'Sculpt Mode not available: {ex}')
            return {'CANCELLED'}
        try:
            bpy.ops.brush.asset_activate(asset_library_type='ESSENTIALS',
                                         relative_asset_identifier=SCULPT_LIB + self.brush)
        except (RuntimeError, TypeError, AttributeError) as ex:
            self.report({'WARNING'}, f'Sculpt Mode on; brush "{self.brush}" not found ({ex}) - pick it in the toolbar')
            return {'FINISHED'}
        self.report({'INFO'}, f'Sculpt: {self.brush} - Select / Move in the tool list goes back to Object Mode')
        return {'FINISHED'}


def draw_shape_grid(layout, context, columns=4, scale=2.6):
    brush = context.scene.mch_brush
    grid = layout.grid_flow(row_major=True, columns=columns, even_columns=True, even_rows=True, align=False)
    for sid, label, desc, stem, fallback in ts.SHAPES:
        if sid == 'CUSTOM':
            continue
        for op in icon_tile(grid, stem, fallback, 'mch.set_shape', label, scale, depress=(brush.shape == sid)):
            op.shape = sid
            op.preset = ''


def draw_custom_grid(layout, context, columns=4, scale=3.0):
    from . import cut_presets
    presets = cut_presets.list_presets()
    brush = context.scene.mch_brush
    current = context.scene.mch_png_preset if presets else 'NONE'
    if not presets:
        layout.label(text='No PNG shapes yet', icon='INFO')
    grid = layout.grid_flow(row_major=True, columns=columns, even_columns=True, even_rows=True, align=False)
    for stem, name in presets[:48]:
        for op in icon_tile(grid, cut_presets.preset_icon(stem), 'IMAGE_DATA', 'mch.set_shape', name[:18], scale,
                            depress=(brush.shape == 'CUSTOM' and current == stem)):
            op.shape = 'CUSTOM'
            op.preset = stem
    row = layout.row(align=True)
    row.operator('mch.import_cut_png', text='Import PNG / JPG Shape', icon='IMPORT')
    if presets:
        row.operator('mch.delete_cut_preset', text='', icon='TRASH')


def draw_shape_palette(self, context):
    """Prepended to VIEW3D_HT_tool_header (viewport top-left) in MECHA LAB."""
    if not ts.is_mecha_workspace(context.workspace) or context.mode != 'OBJECT':
        return
    scene = context.scene
    if not hasattr(scene, 'mch_brush'):
        return
    layout = self.layout
    tool = ts.effective_tool(context)
    row = layout.row(align=True)
    brush = scene.mch_brush
    for sid, label, desc, stem, fallback in ts.SHAPES:
        if sid == 'CUSTOM':
            continue
        op = row.operator('mch.set_shape', text=label, depress=(brush.shape == sid), **_icon_kw(stem, fallback))
        op.shape = sid
        op.preset = ''
    from . import lasso_sketch
    sk = layout.row(align=True)
    skb = sk.row(align=True)
    skb.enabled = tool in lasso_sketch.MODES or tool in {'BASE', 'CBASE'}     # 0.24.1 only where the sketch works
    skb.operator('mch.sketch_toggle', text='Sketch', icon='GREASEPENCIL', depress=lasso_sketch.is_on(context))
    from . import lasso_line
    lb = sk.row(align=True)
    lb.enabled = tool in lasso_line.MODES or tool in lasso_line.ALWAYS     # 0.24.36 greyed where Line does nothing
    lb.prop(brush, 'line_mode', text='Line', icon='IPO_LINEAR', toggle=True)
    if tool == 'CPLATE':                         # 0.24.20 Creature Plate: through front and back
        sk.prop(brush, 'through_mode', text='Through', icon='XRAY', toggle=True)
    if tool in {'CUT', 'SPLIT', 'PLATE', 'WRINKLE'}:
        sk.prop(brush, 'surface_mode', text='Surface', icon='SNAP_FACE', toggle=True)
        if brush.surface_mode and tool in {'CUT', 'SPLIT'}:
            sk.prop(brush, 'surface_gap', text='Gap')
        if tool in {'PLATE', 'WRINKLE'}:
            sk.prop(brush, 'through_mode', text='Through', icon='XRAY', toggle=True)
            if brush.through_mode:
                sk.prop(brush, 'through_crease', text='Crease')
        if tool == 'WRINKLE' and hasattr(context.scene, 'mch_wrinkle'):
            ws = context.scene.mch_wrinkle
            sk.prop(ws, 'sim_after', text='Sim', icon='MOD_CLOTH', toggle=True)
            if ws.sim_after:
                sk.prop(ws, 'sim_preset', text='')
    if brush.line_mode:
        sk.prop(brush, 'line_width', text='')
        sk.prop(brush, 'line_caps', text='')
        # 0.24.21 pointed ends / pen pressure: on-off buttons (the amount only while Taper is on)
        sk.prop(brush, 'line_taper_on', text='Taper', icon='SHARPCURVE', toggle=True)
        if brush.line_taper_on:
            sk.prop(brush, 'line_taper', text='', slider=True)
        sk.prop(brush, 'line_pressure', text='Pressure', icon='STYLUS_PRESSURE', toggle=True)
    row.separator()
    sub = row.row(align=True)
    sub.template_icon_view(scene, 'mch_png_preset', show_labels=True, scale=isz(1.0), scale_popup=isz(5.0))
    op = sub.operator('mch.set_shape', text='Custom', depress=(brush.shape == 'CUSTOM'),
                      **_icon_kw('custom', 'IMAGE_DATA'))
    op.shape = 'CUSTOM'
    op.preset = ''
    sub.operator('mch.import_cut_png', text='', icon='IMPORT')
    if tool in {'CUT', 'SPLIT'} and hasattr(scene, 'mch_cut'):
        tr = layout.row(align=True)
        tr.prop(scene.mch_cut, 'targets', expand=True)
    # Always visible next to the shared shapes in the Mecha workspace.
    draw_ortho_button(layout.row(align=True), context, text='Ortho')
    layout.separator_spacer()


def draw_workspace_menu(self, context):
    self.layout.separator()
    self.layout.operator('mch.workspace_open', text='Open MECHA LAB Workspace', icon='WORKSPACE')


# -----------------------------------------------------------------------------
# Workspace creation
# -----------------------------------------------------------------------------


def _largest(screen, area_type):
    areas = [a for a in screen.areas if a.type == area_type]
    return max(areas, key=lambda a: a.width * a.height) if areas else None


def left_tool_area(screen, view_area=None):
    view_area = view_area or _largest(screen, 'VIEW_3D')
    if view_area is None:
        return None
    for a in screen.areas:
        if a.type == 'PROPERTIES' and a.x + a.width <= view_area.x + 4 and \
                a.y < view_area.y + view_area.height and a.y + a.height > view_area.y:
            return a
    return None


def configure_screen(screen):
    """Data-level setup of a MECHA LAB screen (safe on inactive screens)."""
    area = _largest(screen, 'VIEW_3D')
    if area is None:
        return None
    space = area.spaces.active
    for attr in ('show_region_toolbar', 'show_region_tool_header', 'show_region_ui', 'show_region_header'):
        if hasattr(space, attr):
            setattr(space, attr, True)
    for region in area.regions:
        if region.type == 'UI':
            try:
                region.active_panel_category = 'Mecha Lab'
            except (TypeError, ValueError, AttributeError):
                pass
    left = left_tool_area(screen, area)
    if left is not None:
        try:
            left.spaces.active.context = 'TOOL'
        except (TypeError, AttributeError):
            pass
    return area


def _finalize_layout(ws_name, split, tries=[0]):
    """Timer: runs after Blender switched the window to the new workspace."""
    wm = bpy.context.window_manager
    for win in wm.windows:
        ws = win.workspace
        if ws is None or ws.name != ws_name:
            continue
        screen = win.screen
        area = _largest(screen, 'VIEW_3D')
        if area is None:
            return None
        region = next((r for r in area.regions if r.type == 'WINDOW'), None)
        try:
            with bpy.context.temp_override(window=win, area=area, region=region):
                if split and left_tool_area(screen, area) is None:
                    before = {a.as_pointer() for a in screen.areas}
                    bpy.ops.screen.area_split(direction='VERTICAL', factor=0.12)
                    new = [a for a in screen.areas if a.as_pointer() not in before]
                    if new:
                        left = min([area] + new, key=lambda a: a.x)
                        left.ui_type = 'PROPERTIES'
                        left.spaces.active.context = 'TOOL'
                if ts.native_tool_id(bpy.context) not in ts.NATIVE_TO_TOOL:
                    bpy.ops.wm.tool_set_by_id(name='mecha.cut', space_type='VIEW_3D')
        except Exception as ex:   # layout is optional; never break the session
            print('[Mecha Lab] workspace layout step skipped:', ex)
        configure_screen(screen)
        for a in screen.areas:
            a.tag_redraw()
        return None
    tries[0] += 1
    if tries[0] > 30:
        tries[0] = 0
        return None
    return 0.15


def schedule_layout(ws_name, split):
    bpy.app.timers.register(lambda: _finalize_layout(ws_name, split), first_interval=0.15)


class MCH_OT_workspace_open(bpy.types.Operator):
    bl_idname = 'mch.workspace_open'
    bl_label = 'Open MECHA LAB Workspace'
    bl_description = ('Switch to the MECHA LAB workspace tab, creating it in this file if needed '
                      '(other workspaces are not changed; the startup file is not saved)')
    bl_options = {'REGISTER'}

    def execute(self, context):
        win = context.window
        if win is None:
            self.report({'ERROR'}, 'No window available')
            return {'CANCELLED'}
        ws = ts.find_mecha_workspace()
        if ws is not None:
            win.workspace = ws
            schedule_layout(ws.name, split=False)
            return {'FINISHED'}
        before = {w.name for w in bpy.data.workspaces}
        if context.mode != 'OBJECT' and context.active_object is not None:
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except RuntimeError:
                pass
        try:
            bpy.ops.workspace.duplicate()
        except RuntimeError as ex:
            self.report({'ERROR'}, f'Could not create workspace: {ex}')
            return {'CANCELLED'}
        new = [w for w in bpy.data.workspaces if w.name not in before]
        if not new:
            self.report({'ERROR'}, 'Workspace duplicate produced nothing')
            return {'CANCELLED'}
        ws = new[0]
        ws.name = ts.WORKSPACE_NAME
        ws[ts.WORKSPACE_TAG] = True
        try:
            ws.object_mode = 'OBJECT'
        except (TypeError, AttributeError):
            pass
        for screen in ws.screens:
            configure_screen(screen)
        win.workspace = ws
        schedule_layout(ws.name, split=True)
        self.report({'INFO'}, 'MECHA LAB workspace created in this file (save the file to keep it)')
        return {'FINISHED'}


class MCH_OT_workspace_repair(bpy.types.Operator):
    bl_idname = 'mch.workspace_repair'
    bl_label = 'Repair MECHA LAB Layout'
    bl_description = 'Re-create the left tool list area and show toolbar / tool header / sidebar'
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return ts.is_mecha_workspace(context.workspace)

    def execute(self, context):
        context.workspace[ts.WORKSPACE_TAG] = True
        configure_screen(context.window.screen)
        schedule_layout(context.workspace.name, split=True)
        return {'FINISHED'}


class MCH_OT_workspace_save_startup(bpy.types.Operator):
    bl_idname = 'mch.workspace_save_startup'
    bl_label = 'Save Current Layout as Startup File'
    bl_description = ('OVERWRITES your Blender startup file with the current file so new files open '
                      'with the MECHA LAB tab. Only do this if you really want it')
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(
            self, event, title='Overwrite Startup File?',
            message='This replaces your startup.blend (File > Defaults). Continue?',
            confirm_text='Overwrite', icon='WARNING')

    def execute(self, context):
        try:
            bpy.ops.wm.save_homefile()
        except RuntimeError as ex:
            self.report({'ERROR'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Startup file saved (restore: File > Defaults > Load Factory Settings)')
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# Tool / shape operators and gated hotkeys
# -----------------------------------------------------------------------------


class MCH_OT_set_tool(bpy.types.Operator):
    bl_idname = 'mch.set_tool'
    bl_label = 'Mecha Tool'
    bl_description = 'Select this Mecha Lab tool'
    bl_options = {'INTERNAL'}
    tool: EnumProperty(items=ts.TOOL_ENUM_ITEMS, default='CUT')

    @classmethod
    def description(cls, context, properties):
        t = ts.TOOL_BY_ID.get(properties.tool)
        if not t:
            return cls.bl_description
        note = {'PARTIAL': '\nStatus: partial (see Known Limitations)',
                'TODO': '\nStatus: NOT implemented yet'}.get(t[6], '')
        return t[2] + note

    def execute(self, context):
        activate_mecha_tool(context, self.tool)
        return {'FINISHED'}


class MCH_OT_set_shape(bpy.types.Operator):
    bl_idname = 'mch.set_shape'
    bl_label = 'Mecha Shape'
    bl_description = 'Shared shape for Cut / Split / Mask'
    bl_options = {'INTERNAL'}
    shape: EnumProperty(items=ts.SHAPE_ENUM_ITEMS, default='LASSO')
    preset: StringProperty(default='', options={'SKIP_SAVE'})

    @classmethod
    def description(cls, context, properties):
        s = ts.SHAPE_BY_ID.get(properties.shape)
        return s[2] if s else cls.bl_description

    def execute(self, context):
        scene = context.scene
        if self.preset:
            try:
                scene.mch_png_preset = self.preset
            except TypeError:
                pass
        scene.mch_brush.shape = self.shape
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}


def _space_ok(context):
    return (pref('space_menu') and ts.is_mecha_workspace(context.workspace)
            and context.area is not None and context.area.type == 'VIEW_3D')


class MCH_OT_space_tools(bpy.types.Operator):
    bl_idname = 'mch.space_tools'
    bl_label = 'Mecha Tool Menu'
    bl_description = 'Large-icon Mecha Lab tool menu (MECHA LAB workspace only)'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return _space_ok(context)   # outside the workspace Space keeps its Blender binding

    def execute(self, context):
        bpy.ops.wm.call_panel(name='MCH_PT_tool_popup', keep_open=False)
        return {'FINISHED'}


class MCH_OT_quick_menu(bpy.types.Operator):
    bl_idname = 'mch.quick_menu'
    bl_label = 'Mecha Quick Tools'
    bl_description = 'V: Cut / Boolean / Base Mesh / SubD Plane / Split / Radial Array at the mouse (MECHA LAB only)'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return (pref('quick_menu') and ts.is_mecha_workspace(context.workspace) and context.mode == 'OBJECT'
                and context.area is not None and context.area.type == 'VIEW_3D')

    def execute(self, context):
        bpy.ops.wm.call_panel(name='MCH_PT_quick_popup', keep_open=False)
        return {'FINISHED'}


def object_under_mouse(context, event):
    """Visible object under the mouse (ray cast against evaluated geometry)."""
    from bpy_extras import view3d_utils
    region, rv3d = context.region, context.region_data
    if region is None or rv3d is None:
        return None
    xy = (event.mouse_region_x, event.mouse_region_y)
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy)
    hit, _loc, _no, _idx, ob, _m = context.scene.ray_cast(context.evaluated_depsgraph_get(), origin, direction)
    if not hit or ob is None:
        return None
    return bpy.data.objects.get(ob.name)


class MCH_OT_select_move(bpy.types.Operator):
    """Replaces the removed Alt+click mode switch."""
    bl_idname = 'mch.select_move'
    bl_label = 'Select / Move'
    bl_description = ('Blender selection + Move gizmo (click / Shift+click / box select, drag the gizmo). '
                      'A running Cut / Split stroke is cancelled safely; pick Cut / Split again to start fresh')
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' or _view3d_override(context) is not None

    def execute(self, context):
        if context.mode != 'OBJECT' and context.active_object is not None:
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except RuntimeError:
                pass
        try:
            # a running stroke modal sees the tool change and cancels itself (no cut)
            set_native_tool(context, 'builtin.move')
        except (RuntimeError, TypeError) as ex:
            self.report({'WARNING'}, f'Move tool unavailable here: {ex}')
            return {'CANCELLED'}
        from . import bottom_bar
        bottom_bar.note_select(context)
        space = context.space_data if getattr(context.space_data, 'type', '') == 'VIEW_3D' else None
        if space is not None and not space.show_gizmo:
            space.show_gizmo = True
        self.report({'INFO'}, 'Select / Move: click or box-select objects, drag the gizmo. Pick a Mecha tool to continue')
        return {'FINISHED'}


class MCH_OT_select_move_key(bpy.types.Operator):
    """Hotkey wrapper (gated to the MECHA LAB workspace)."""
    bl_idname = 'mch.select_move_key'
    bl_label = 'Select / Move (hotkey)'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return (pref('select_move_key') and ts.is_mecha_workspace(context.workspace) and context.area is not None
                and context.area.type == 'VIEW_3D')

    def execute(self, context):
        return bpy.ops.mch.select_move()


class MCH_OT_sculpt_back(bpy.types.Operator):
    """0.24.23 G in Sculpt Mode: back to Object Mode with Select / Move (like the Select / Move tile)."""
    bl_idname = 'mch.sculpt_back'
    bl_label = 'Back to Select / Move'
    bl_description = 'Leave Sculpt Mode: Object Mode with the Select / Move tool'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'SCULPT'

    def execute(self, context):
        return bpy.ops.mch.select_move()


LINE_KEY_SKIP = {'mecha.screw_stamp', 'mecha.primitive'}


class MCH_OT_line_width_key(bpy.types.Operator):
    """0.24.23 [ / ] in Object Mode while a Mecha drawing tool is active: Line Width (Blender's own [ / ]
    = select parent / child stays everywhere else)."""
    bl_idname = 'mch.line_width_key'
    bl_label = 'Line Width Step (hotkey)'
    bl_options = {'INTERNAL'}

    factor: FloatProperty(default=1.15, min=0.1, max=10.0)

    @classmethod
    def poll(cls, context):
        tid = ts.native_tool_id(context)
        return (tid.startswith('mecha.') and tid not in LINE_KEY_SKIP and context.area is not None
                and context.area.type == 'VIEW_3D' and getattr(context.scene, 'mch_brush', None) is not None)

    def execute(self, context):
        from . import cut_engine
        cut_engine.step_line_width(context, self.factor, self.report)
        context.area.tag_redraw()
        return {'FINISHED'}


class MCH_MT_add_mecha(bpy.types.Menu):
    """Shift+A > Mecha Lab (appended to Blender's Add menu, nothing removed)."""
    bl_idname = 'MCH_MT_add_mecha'
    bl_label = 'Mecha Lab'

    def draw(self, context):
        layout = self.layout
        layout.operator_context = 'EXEC_DEFAULT'
        for kind, label in (('BOX', 'Box'), ('CYLINDER', 'Cylinder'), ('SPHERE', 'Sphere'), ('CONE', 'Cone'),
                            ('CAPSULE', 'Capsule')):
            kw = _icon_kw('primitive_' + kind.lower(), 'MESH_CUBE')
            layout.operator('mch.primitive_create', text='Primitive ' + label, **kw).kind = kind
        layout.separator()
        layout.operator('mch.subd_plane_create', text='SubD Plane', **_icon_kw('subd', 'MOD_SUBSURF'))
        layout.operator_context = 'INVOKE_DEFAULT'
        layout.operator('mch.set_tool', text='Base Mesh (draw)', **_icon_kw('base', 'MESH_CUBE')).tool = 'BASE'
        layout.separator()
        layout.operator('mch.deform_lattice', text='Lattice Cage (selected)', icon='MOD_LATTICE')
        layout.operator('mch.deform_bend', text='Bend Curve (active)', icon='CURVE_BEZCURVE')


def draw_add_menu(self, context):
    self.layout.separator()
    self.layout.menu(MCH_MT_add_mecha.bl_idname, **_icon_kw('base', 'MESH_CUBE'))


class MCH_OT_hotkeys_save(bpy.types.Operator):
    """Keep the keys set here for the next Blender start (Mecha Lab's own file, not Blender's preferences)"""
    bl_idname = 'mch.hotkeys_save'
    bl_label = 'Save Hotkeys'
    bl_options = {'INTERNAL'}

    def execute(self, context):
        n = save_hotkeys(context)
        self.report({'INFO'}, f'Mecha hotkeys saved ({n})')
        return {'FINISHED'}


class MCH_OT_hotkeys_reset(bpy.types.Operator):
    """Back to the Mecha Lab default keys (the saved keys are deleted)"""
    bl_idname = 'mch.hotkeys_reset'
    bl_label = 'Default Keys'
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        import os
        path = _hotkeys_path()
        if path and os.path.isfile(path):
            os.remove(path)
        unregister_keymaps()
        register_keymaps()
        self.report({'INFO'}, 'Mecha hotkeys back to the defaults')
        return {'FINISHED'}


class MCH_OT_hotkey(bpy.types.Operator):
    bl_idname = 'mch.hotkey'
    bl_label = 'Mecha Hotkey'
    bl_options = {'INTERNAL'}
    action: EnumProperty(items=[('BOOLEAN', 'Boolean Difference', ''), ('CUT', 'Cut Tool', ''),
                                ('SPLIT', 'Split Tool', ''), ('PLATE', 'Armor Plate Tool', ''),
                                ('MIRROR', 'Mirror (lean)', ''), ('SHAPES', 'Lasso Shape Menu', ''),
                                ('TOOL', 'Pick a Tool', ''), ('REMESH', 'Remesh + Smooth (run)', '')])
    # 0.24.17 TOOL: one key per tool of the left list (unassigned until you set one)
    tool: EnumProperty(items=ts.TOOL_ENUM_ITEMS, default='CUT')
    # 0.24.8 S = Split only with nothing selected (with a selection S stays Blender's Scale; 0.24.27 only plain S)
    only_empty: BoolProperty(default=False, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return (pref('workspace_hotkeys') and ts.is_mecha_workspace(context.workspace)
                and context.mode == 'OBJECT')

    def invoke(self, context, event):
        # 0.24.27 only a plain S gives way to Blender's Scale when something is selected; a key you set yourself
        # in the Hotkeys box (D, Shift+S, ...) always works
        plain_s = (getattr(event, 'type', '') == 'S' and not (getattr(event, 'shift', False) or
                   getattr(event, 'ctrl', False) or getattr(event, 'alt', False) or getattr(event, 'oskey', False)))
        if self.only_empty and context.selected_objects and plain_s:
            return {'PASS_THROUGH'}
        if self.action == 'MIRROR':
            # 0.24.8 Alt+X = the left Mirror button: lean the mouse, the result stays a live Mirror
            # 0.24.13 a selected collection instance: the same lean gesture, a live mirrored instance
            from . import mirror_tools
            return mirror_tools.start_mirror(context, True, self.report)
        return self.execute(context)

    def execute(self, context):
        if self.action == 'BOOLEAN':
            return bpy.ops.mch.boolean('EXEC_DEFAULT', operation='DIFFERENCE')
        if self.action == 'MIRROR':
            return {'CANCELLED'}
        if self.action == 'REMESH':
            # 0.24.20 run Remesh + Smooth on the selection right away (the Remesh tool's settings), any tool
            if not bpy.ops.mch.one_click_remesh.poll():
                self.report({'WARNING'}, 'Remesh: select a mesh first (Object Mode)')
                return {'CANCELLED'}
            return bpy.ops.mch.one_click_remesh('EXEC_DEFAULT')
        if self.action == 'SHAPES':
            # 0.24.17 L = the lasso shape menu at the mouse (like the old Space menu)
            bpy.ops.wm.call_panel(name='MCH_PT_shape_popup', keep_open=False)
            return {'FINISHED'}
        activate_mecha_tool(context, self.tool if self.action == 'TOOL' else self.action)
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# Panels
# -----------------------------------------------------------------------------


class MCH_PT_main(bpy.types.Panel):
    bl_idname = 'MCH_PT_main'
    bl_label = 'Mecha Lab'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Mecha Lab'

    def draw_header(self, context):
        tool = ts.TOOL_BY_ID.get(ts.effective_tool(context))
        self.layout.label(text='MECHA LAB | ' + (tool[1] if tool else ''))

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        if not hasattr(scene, 'mch_settings'):
            return
        in_ws = ts.is_mecha_workspace(context.workspace)
        from . import addon_safety
        if addon_safety.FOREIGN:
            box = layout.box()
            box.alert = True
            box.label(text='Another Mecha Lab copy was enabled:', icon='ERROR')
            for name in addon_safety.FOREIGN:
                box.label(text='  ' + name)
            box.label(text='Disable / remove it in Preferences, then restart Blender')
        if not in_ws:
            row = layout.row()
            row.scale_y = 1.5
            row.operator('mch.workspace_open', text='Open MECHA LAB Workspace', icon='WORKSPACE')
        draw_ortho_button(layout.row(align=True), context, text='Orthographic Lock (No Perspective)')
        tool_id = ts.effective_tool(context)
        tid, label, desc, stem, fallback, native, status = ts.TOOL_BY_ID[tool_id]
        head = layout.row(align=True)
        iid = icon_id(stem)
        if iid:
            head.template_icon(icon_value=iid, scale=isz(2.2))
        col = head.column(align=True)
        col.label(text=label.upper())
        col.label(text={'OK': '', 'PARTIAL': 'Status: partial', 'TODO': 'Status: not implemented'}[status])
        if native and ts.native_tool_id(context) != native:
            layout.operator('mch.set_tool', text=f'Activate {label} tool in viewport', icon='RESTRICT_SELECT_OFF').tool = tid
        from . import target_rules
        if tool_id in target_rules.PICKING:      # 0.24.34 the Cut panel's Targets row, in every tool
            from . import ui_tool_settings
            ui_tool_settings.draw_targets(layout, context)
        if tool_id in target_rules.PICKING | target_rules.OWN_ROW - {'CMOVE', 'CPATH'}:
            from . import ui_tool_settings              # 0.24.36 Slow Line (Lazy Mouse) on / off, every drawing tool
            ui_tool_settings.draw_slow_line(layout, context)
        drawer = _drawers().get(tool_id)
        if drawer is not None:
            drawer(layout, context)


class MCH_PT_lasso(bpy.types.Panel):
    """0.23.27 lasso / shape settings: one shared panel shown in every tool."""
    bl_idname = 'MCH_PT_lasso'
    bl_label = 'Lasso Settings'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Mecha Lab'
    bl_order = 1

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, 'mch_brush')         # every tool, Select included

    def draw(self, context):
        from . import ui_tool_settings
        ui_tool_settings.draw_shape_options(self.layout, context, ts.effective_tool(context))


def _drawers():
    from . import ui_tool_settings
    return ui_tool_settings.DRAWERS


def draw_icon_sizes(layout, p):
    col = layout.column(align=True)
    col.label(text='Icon Size', icon='FULLSCREEN_ENTER')
    col.prop(p, 'icon_scale', slider=True)
    col.prop(p, 'toolbar_scale', slider=True)
    col.prop(p, 'handle_scale', slider=True)
    if hasattr(p, 'dial_flip'):
        layout.prop(p, 'dial_flip')
    if hasattr(p, 'bottom_toolbar'):
        layout.prop(p, 'bottom_toolbar', toggle=True)
    row = layout.row(align=True)
    for label, v in (('Small', 0.75), ('Normal', 1.0), ('Large', 1.4), ('Huge', 1.9)):
        row.operator('mch.icon_size_preset', text=label).factor = v


class MCH_OT_icon_size_preset(bpy.types.Operator):
    """Set all Mecha Lab icon sizes at once (panel icons, bottom toolbar, handles)"""
    bl_idname = 'mch.icon_size_preset'
    bl_label = 'Icon Size Preset'
    bl_options = {'INTERNAL'}
    factor: FloatProperty(default=1.0)

    def execute(self, context):
        p = prefs()
        if p is None:
            return {'CANCELLED'}
        p.icon_scale = p.toolbar_scale = p.handle_scale = self.factor
        save_sizes(p)
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()
        return {'FINISHED'}


class MCH_PT_icon_size(bpy.types.Panel):
    """Sidebar > Mecha Lab > Icon Size: bigger or smaller icons (0.14.2)."""
    bl_idname = 'MCH_PT_icon_size'
    bl_label = 'Icon Size'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Mecha Lab'
    bl_order = 90

    @classmethod
    def poll(cls, context):
        return prefs() is not None and ts.sidebar_select(context)

    def draw(self, context):
        draw_icon_sizes(self.layout, prefs())


class MCH_PT_tools(bpy.types.Panel):
    """Fallback tool list in the sidebar (always available, collapsed by default).

    The primary list is the left area; this guarantees access even if that
    area is missing or the Space popup is blocked by another add-on.
    """
    bl_idname = 'MCH_PT_tools'
    bl_label = 'Tools (fallback list)'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Mecha Lab'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, 'mch_settings') and ts.sidebar_select(context)

    def draw(self, context):
        layout = self.layout
        draw_tool_grid(layout, context, columns=3, scale=1.8)
        if ts.is_mecha_workspace(context.workspace) and context.screen and \
                left_tool_area(context.screen) is None:
            layout.operator('mch.workspace_repair', icon='FILE_REFRESH')


class MCH_PT_workspace(bpy.types.Panel):
    bl_idname = 'MCH_PT_workspace'
    bl_label = 'Workspace & Hotkeys'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Mecha Lab'
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 100

    @classmethod
    def poll(cls, context):
        return ts.sidebar_select(context)           # 0.23.24 Select only

    def draw(self, context):
        layout = self.layout
        in_ws = ts.is_mecha_workspace(context.workspace)
        layout.label(text='Current: ' + (context.workspace.name if context.workspace else '-'))
        layout.operator('mch.workspace_open', icon='WORKSPACE')
        row = layout.row()
        row.enabled = in_ws
        row.operator('mch.workspace_repair', icon='FILE_REFRESH')
        p = prefs()
        if p is not None:
            col = layout.column(align=True)
            col.prop(p, 'workspace_hotkeys')
            col.prop(p, 'quick_menu')
            col.prop(p, 'select_move_key')
            draw_hotkey_editor(layout)
        layout.label(text='Hotkeys only work in MECHA LAB', icon='INFO')
        layout.separator()
        layout.operator('mch.self_test', icon='CHECKMARK')
        layout.label(text='Temporary scene; report goes to the clipboard', icon='INFO')
        layout.separator()
        draw_ortho_button(layout, context, text='Orthographic View Lock')
        layout.label(text='Keeps ortho when orbiting; does not alter global preferences', icon='INFO')
        layout.operator('mch.workspace_save_startup', icon='ERROR')


class MCH_PT_tool_list(bpy.types.Panel):
    """Left area (Properties editor, Tool tab) of the MECHA LAB workspace."""
    bl_idname = 'MCH_PT_tool_list'
    bl_label = 'MECHA LAB TOOLS'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'
    bl_options = {'DEFAULT_CLOSED'}    # 0.15: the floating side list in the viewport is the main one

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (space is not None and space.type == 'PROPERTIES'
                and ts.is_mecha_workspace(context.workspace) and hasattr(context.scene, 'mch_settings'))

    def draw(self, context):
        layout = self.layout
        layout.label(text='MECHA LAB TOOLS')
        # 0.14.3: tiles (icon above, name below) instead of rows with a wide name column;
        # columns follow the width of the left area
        draw_tool_grid(layout, context, columns=0, scale=2.2)
        draw_sculpt_grid(layout, context, columns=3, scale=2.2)      # 0.24.21
        layout.separator()
        layout.label(text='Space (while drawing): move the outline', icon='EVENT_SPACEKEY')


class MCH_PT_tool_popup(bpy.types.Panel):
    bl_idname = 'MCH_PT_tool_popup'
    bl_label = 'MECHA LAB | Tools'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'HEADER'
    bl_ui_units_x = 26

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, 'mch_settings')

    def draw(self, context):
        layout = self.layout
        layout.label(text='MECHA LAB TOOLS', icon='TOOL_SETTINGS')
        draw_tool_grid(layout, context, columns=5, scale=3.0)


class MCH_PT_quick_popup(bpy.types.Panel):
    bl_idname = 'MCH_PT_quick_popup'
    bl_label = 'MECHA LAB | Quick'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'HEADER'
    bl_ui_units_x = 16

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, 'mch_settings')

    def draw(self, context):
        tools = [ts.TOOL_BY_ID[t] for t in ts.QUICK_TOOLS]
        draw_tool_grid(self.layout, context, columns=3, scale=3.0, tools=tools)


class MCH_PT_shape_popup(bpy.types.Panel):
    bl_idname = 'MCH_PT_shape_popup'
    bl_label = 'MECHA LAB | Shapes'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'HEADER'
    bl_ui_units_x = 22

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, 'mch_brush')

    def draw(self, context):
        layout = self.layout
        tool = ts.TOOL_BY_ID.get(ts.effective_tool(context))
        layout.label(text='SHAPES  |  ' + (tool[1] if tool else ''), icon='SELECT_SET')
        draw_shape_grid(layout, context, columns=3, scale=2.6)
        brush = context.scene.mch_brush
        if brush.shape == 'STROKE':
            box = layout.box()
            box.prop(brush, 'stab_enable')
            col = box.column(align=True)
            col.active = brush.stab_enable
            col.prop(brush, 'stab_strength', slider=True)
            col.prop(brush, 'stab_radius', slider=True)
            col.prop(brush, 'stroke_spacing')
        if tool is not None and tool[0] in {'CUT', 'BASE'}:
            from .ui_tool_settings import draw_edge_finish
            draw_edge_finish(layout, context, tool[0])       # 0.19.2 edge bevel / chamfer sliders
        layout.separator()
        # 0.24.18 the custom (PNG) shapes start folded: open them with this row
        wm = context.window_manager
        is_open = bool(getattr(wm, 'mch_show_custom_shapes', False))
        row = layout.row()
        row.prop(wm, 'mch_show_custom_shapes', text='Custom PNG Shapes', emboss=False,
                 icon='DISCLOSURE_TRI_DOWN' if is_open else 'DISCLOSURE_TRI_RIGHT')
        if is_open:
            draw_custom_grid(layout, context, columns=4, scale=2.6)
        layout.label(text='RMB double-click or Esc in the viewport exits the tool')


def draw_profile_grid(layout, context, columns=4, scale=3.0):
    from . import base_mesh
    current = base_mesh.scene_defaults(context).profile
    live = base_mesh.active_live_base(context)
    if live is not None:
        current = live.mch_base.profile
    grid = layout.grid_flow(row_major=True, columns=columns, even_columns=True, even_rows=True, align=False)
    for pid, label, desc, stem, fallback in base_mesh.profiles_for(context, live):
        for op in icon_tile(grid, stem, fallback, 'mch.set_profile', label, scale, depress=(pid == current)):
            op.profile = pid


class MCH_PT_profile_popup(bpy.types.Panel):
    """RMB in the Base Mesh tool: section profile presets."""
    bl_idname = 'MCH_PT_profile_popup'
    bl_label = 'MECHA LAB | Base Mesh Profile'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'HEADER'
    bl_ui_units_x = 24

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, 'mch_base')

    def draw(self, context):
        from . import base_mesh
        layout = self.layout
        live = base_mesh.active_live_base(context)
        p = live.mch_base if live else base_mesh.scene_defaults(context)
        creature = p.profile in base_mesh.CREATURE_PROFILES
        layout.label(text=('CREATURE BASE MESH PROFILE' if creature else 'BASE MESH PROFILE') +
                     (f'  |  editing {live.name}' if live else '  |  next shape'), icon='MESH_CUBE')
        draw_profile_grid(layout, context, columns=4 if not creature else 3, scale=3.0)
        row = layout.row(align=True)
        if creature:
            row.prop(p, 'peak')
            row.prop(p, 'edge_round', slider=True)
        else:
            row.enabled = p.profile in {'BEVEL', 'CHAMFER'}
            row.prop(p, 'bevel_sides', expand=True)
        layout.separator()
        layout.label(text='Shape (shared palette)', icon='SELECT_SET')
        draw_shape_grid(layout, context, columns=6, scale=1.6)
        layout.label(text='RMB double-click or Esc in the viewport exits the tool')


class MCH_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = ADDON_ID

    space_menu: BoolProperty(name='Space = Big Mecha Tool Menu', default=True,
                             description='Only inside the MECHA LAB workspace; elsewhere Space keeps Blender behaviour')
    workspace_hotkeys: BoolProperty(name='B / C / Alt+X / S / Alt+A Hotkeys', default=True,
                                    description='B = Boolean Difference, C = Cut tool, Alt+X = Mirror, S = Split '
                                                '(nothing selected; else Scale), Alt+A = Armor Plate; MECHA LAB only')
    tool_pie: BoolProperty(name='V = Tool Pie', default=True,
                           description='All Mecha tools as a pie at the mouse, MECHA LAB only')
    last_tool_key: BoolProperty(name='Q = Select <-> Last Tool', default=True,
                                description='One key flips between Select / Move and the last modelling tool (like Tab), '
                                            'MECHA LAB only (elsewhere Q = Quick Favorites)')
    bottom_toolbar: BoolProperty(name='Bottom Toolbar', default=True,
                                 description='Tool buttons at the bottom centre of the viewport (MECHA LAB, Object Mode)')
    toolbar_labels: BoolProperty(name='Names Under Icons', default=True)
    toolbar_size: EnumProperty(name='Toolbar Size', items=[('S', 'S', ''), ('M', 'M', ''), ('L', 'L', '')], default='M')
    icon_scale: FloatProperty(name='Panel Icons', default=1.0, min=0.5, max=2.5, subtype='FACTOR',
                              update=_sizes_changed,
                              description='Size of the Mecha Lab thumbnails in panels, menus and popups')
    toolbar_scale: FloatProperty(name='Bottom Toolbar', default=1.0, min=0.5, max=2.5, subtype='FACTOR',
                                 update=_sizes_changed,
                                 description='Size of the bottom toolbar buttons and their names')
    dial_flip: BoolProperty(name='Flip Dial Turning', default=True,
                            description='Rotation dials turn the shape the same way as the mouse. If a dial still '
                                        'turns the wrong way on your system, switch this off')
    handle_scale: FloatProperty(name='Viewport Handles', default=1.0, min=0.3, max=3.0, subtype='FACTOR',
                                update=_sizes_changed,
                                description='Size of the arrows, dials and dots of the Primitive / Station handles')
    quick_menu: BoolProperty(name='Quick Tool Menu (no key since 0.12)', default=True,
                             description='Six core tools at the mouse, only inside MECHA LAB (Object Mode)')
    select_move_key: BoolProperty(name='Select / Move Hotkey', default=True,
                                  description='Hotkey for Select / Move inside MECHA LAB (change the key below or in '
                                              'Preferences > Keymap, "mch.select_move_key")')

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text='Bottom toolbar / keys (0.12)')
        row = box.row()
        row.prop(self, 'bottom_toolbar')
        row.prop(self, 'toolbar_labels')
        box.row().prop(self, 'toolbar_size', expand=True)
        draw_icon_sizes(box, self)
        row = box.row()
        row.prop(self, 'tool_pie')
        row.prop(self, 'last_tool_key')
        layout.prop(self, 'workspace_hotkeys')
        layout.prop(self, 'quick_menu')
        layout.prop(self, 'select_move_key')
        draw_hotkey_editor(layout)
        layout.label(text='Key bindings can be changed in Preferences > Keymap ("mch.").')
        layout.operator('mch.workspace_open', icon='WORKSPACE')


# 0.24.5 Enter = Apply for the live results (first match for the selection wins)
ENTER_APPLY = (
    ('pdetail_apply', 'Plate Detail'),
    ('plate_apply', 'Armor Plate'),
    ('mridge_apply', 'Mech Ridge'),
    ('cape_apply', 'Cape'),
    ('sdraw_apply', 'Surface Draw'),
    ('hair_apply', 'Creature Hair'),
    ('clothing_apply', 'Clothing'),
    ('hood_apply', 'Hood'),
    ('scarf_apply', 'Scarf'),
    ('wrinkle_apply', 'Cloth Plate'),
    ('base_freeze', 'Base Mesh'),
    ('mesh_mirror_apply', 'Mirror'),
    ('box_hide_apply', 'Box Hide'),
    ('tube_apply', 'Curve'),
)


def enter_apply_target(context):
    """(operator id, label) of the live result Enter applies now, or None."""
    for opid, label in ENTER_APPLY:
        if opid == 'box_hide_apply':
            try:
                from . import box_hide
                hidden = any(o.type == 'MESH' and box_hide.is_hidden(o) for o in context.selected_objects)
                if not hidden and ts.effective_tool(context) == 'HIDE':
                    # 0.24.18 in the Box Hide tool the hidden mesh is usually not selected (Auto Target):
                    # Enter applies every mesh hidden in the view (as the Apply button does)
                    hidden = any(o.type == 'MESH' and box_hide.is_hidden(o) for o in context.view_layer.objects)
                if not hidden:
                    continue
            except (ImportError, AttributeError, ReferenceError):
                continue
            return opid, label
        op = getattr(bpy.ops.mch, opid, None)
        try:
            if op is not None and op.poll():
                return opid, label
        except (RuntimeError, AttributeError, TypeError):
            continue
    return None


class MCH_OT_enter_apply(bpy.types.Operator):
    """Enter: apply the live result of the selection (Plate Detail, Armor Plate, Cloth Plate, Base Mesh,
    Mirror, Box Hide, Curve)"""
    bl_idname = 'mch.enter_apply'
    bl_label = 'Apply (Enter)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        try:
            return (context.mode == 'OBJECT' and ts.is_mecha_workspace(context.workspace)
                    and enter_apply_target(context) is not None)
        except (AttributeError, ReferenceError):
            return False

    def execute(self, context):
        target = enter_apply_target(context)
        if target is None:
            return {'CANCELLED'}
        opid, label = target
        res = getattr(bpy.ops.mch, opid)()
        if 'FINISHED' in res:
            self.report({'INFO'}, f'{label}: applied')
        return res


CLASSES = (
    MCH_AddonPreferences,
    MCH_OT_enter_apply,
    MCH_OT_workspace_open, MCH_OT_workspace_repair, MCH_OT_workspace_save_startup,
    MCH_OT_set_tool, MCH_OT_set_shape, MCH_OT_space_tools, MCH_OT_hotkey, MCH_OT_hotkeys_save,
    MCH_OT_hotkeys_reset, MCH_OT_ortho_lock,
    MCH_OT_quick_menu, MCH_OT_sculpt_brush, MCH_OT_select_move, MCH_OT_select_move_key, MCH_OT_sculpt_back,
    MCH_OT_line_width_key, MCH_MT_add_mecha,
    MCH_OT_icon_size_preset, MCH_PT_tools, MCH_PT_main, MCH_PT_lasso, MCH_PT_icon_size, MCH_PT_workspace, MCH_PT_tool_list, MCH_PT_tool_popup, MCH_PT_shape_popup,
    MCH_PT_quick_popup, MCH_PT_profile_popup,
)


def register_keymaps():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon if wm else None
    if kc is None:
        return
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    # 0.22.1: Q = Select <-> last tool (one key, like Tab); 0.23.2: V = tool pie
    # (it duplicated the pie) and N is Blender's sidebar again. 0.23.13: Space no longer
    # opens the big tool menu (it moves the outline while drawing). All gated to MECHA LAB
    # by the operators' poll.
    _keymaps.append((km, km.keymap_items.new('mch.toggle_last_tool', 'Q', 'PRESS')))
    _keymaps.append((km, km.keymap_items.new('mch.tool_pie', 'V', 'PRESS')))
    km = kc.keymaps.new(name='Object Mode', space_type='EMPTY')
    item = km.keymap_items.new('mch.hotkey', 'B', 'PRESS')
    item.properties.action = 'BOOLEAN'
    _keymaps.append((km, item))
    item = km.keymap_items.new('mch.hotkey', 'C', 'PRESS')
    item.properties.action = 'CUT'
    _keymaps.append((km, item))
    # 0.24.8 Alt+X = Mirror, S = Split (nothing selected; else Scale), Alt+A = Armor Plate
    item = km.keymap_items.new('mch.hotkey', 'X', 'PRESS', alt=True)
    item.properties.action = 'MIRROR'
    _keymaps.append((km, item))
    item = km.keymap_items.new('mch.hotkey', 'S', 'PRESS')
    item.properties.action = 'SPLIT'
    item.properties.only_empty = True
    _keymaps.append((km, item))
    item = km.keymap_items.new('mch.hotkey', 'A', 'PRESS', alt=True)
    item.properties.action = 'PLATE'
    _keymaps.append((km, item))
    # 0.24.17 L = lasso shape menu; one (unassigned) key per tool of the left list - set them in the
    # Hotkeys box, Save keeps them (config/mecha_lab/hotkeys.json)
    item = km.keymap_items.new('mch.hotkey', 'L', 'PRESS')
    item.properties.action = 'SHAPES'
    _keymaps.append((km, item))
    # 0.24.20 run Remesh + Smooth right away (no key until you set one in the Hotkeys box)
    item = km.keymap_items.new('mch.hotkey', 'NONE', 'PRESS')
    item.properties.action = 'REMESH'
    _keymaps.append((km, item))
    for tid in tool_key_ids():
        item = km.keymap_items.new('mch.hotkey', 'NONE', 'PRESS')
        item.properties.action = 'TOOL'
        item.properties.tool = tid
        _keymaps.append((km, item))
    # Select / Move (replaces the removed Alt+click mode switch). Default F (user
    # request, 0.11.3); rebind freely (panel or Preferences > Keymap).
    _keymaps.append((km, km.keymap_items.new('mch.select_move_key', 'F', 'PRESS')))
    # 0.24.31 hold D + drag = Concept Move in any tool (D alone does nothing in Object Mode; D + drag outside
    # MECHA LAB is still Blender's annotate - the operator's poll)
    _keymaps.append((km, km.keymap_items.new('mch.concept_hold', 'LEFTMOUSE', 'PRESS', key_modifier='D')))
    # 0.24.5 Enter = Apply the live result (tool keymaps, e.g. a pending sketch, come first)
    for key in ('RET', 'NUMPAD_ENTER'):
        _keymaps.append((km, km.keymap_items.new('mch.enter_apply', key, 'PRESS')))
    # 0.24.23 [ / ] = Line Width in every Mecha drawing tool, also before Blender's Object Mode [ / ]
    # (select parent / child) - that one still works when no Mecha tool is active (poll)
    for key, f in (('LEFT_BRACKET', 1.0 / 1.15), ('RIGHT_BRACKET', 1.15)):
        item = km.keymap_items.new('mch.line_width_key', key, 'PRESS')
        item.properties.factor = f
        _keymaps.append((km, item))
    # 0.24.23 G in Sculpt Mode = back to Object Mode + Select / Move
    km = kc.keymaps.new(name='Sculpt', space_type='EMPTY')
    _keymaps.append((km, km.keymap_items.new('mch.sculpt_back', 'G', 'PRESS')))
    # Mesh Curve: double-click a path point in Curve Edit Mode = Straight <-> Smooth.
    # (Registered since v0.5.9 but always inactive; the operator passes through
    # for curves that are not Mecha Lab paths.)
    km = kc.keymaps.new(name='Curve', space_type='EMPTY')
    _keymaps.append((km, km.keymap_items.new('mch.double_click_point', 'LEFTMOUSE', 'DOUBLE_CLICK')))
    load_hotkeys([item for _km, item in _keymaps])


def unregister_keymaps():
    for km, item in _keymaps:
        try:
            km.keymap_items.remove(item)
        except (ReferenceError, RuntimeError):
            pass
    _keymaps.clear()


def register():
    _load_icons()
    bpy.types.WindowManager.mch_show_custom_shapes = BoolProperty(
        name='Custom PNG Shapes', default=False, description='Show the custom (PNG) stamp shapes in the shape menu')
    for c in CLASSES:
        bpy.utils.register_class(c)
    purge_stale_keymap_items()
    register_native_tools()
    bpy.types.VIEW3D_HT_tool_header.prepend(draw_shape_palette)
    bpy.types.VIEW3D_MT_add.append(draw_add_menu)
    if hasattr(bpy.types, 'TOPBAR_MT_workspace_menu'):
        bpy.types.TOPBAR_MT_workspace_menu.append(draw_workspace_menu)
    register_keymaps()
    if _ortho_on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_ortho_on_load)
    # bpy.data is restricted while add-ons are enabled at startup
    # ("'_RestrictData' object has no attribute 'workspaces'"): check later.
    if not bpy.app.timers.is_registered(_deferred_ortho_check):
        bpy.app.timers.register(_deferred_ortho_check, first_interval=0.5)
    if not load_sizes() and not bpy.app.timers.is_registered(_deferred_load_sizes):
        bpy.app.timers.register(_deferred_load_sizes, first_interval=0.3)


def unregister():
    if hasattr(bpy.types.WindowManager, 'mch_show_custom_shapes'):
        del bpy.types.WindowManager.mch_show_custom_shapes
    if _ortho_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_ortho_on_load)
    if bpy.app.timers.is_registered(_ortho_watchdog):
        bpy.app.timers.unregister(_ortho_watchdog)
    if bpy.app.timers.is_registered(_deferred_ortho_check):
        bpy.app.timers.unregister(_deferred_ortho_check)
    unregister_keymaps()
    if hasattr(bpy.types, 'TOPBAR_MT_workspace_menu'):
        bpy.types.TOPBAR_MT_workspace_menu.remove(draw_workspace_menu)
    bpy.types.VIEW3D_HT_tool_header.remove(draw_shape_palette)
    bpy.types.VIEW3D_MT_add.remove(draw_add_menu)
    unregister_native_tools()
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
    _free_icons()
