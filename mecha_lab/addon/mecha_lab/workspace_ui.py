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
from bpy.props import BoolProperty, EnumProperty, StringProperty

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
    if rv3d is not None and rv3d.view_perspective != 'ORTHO':
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


def draw_ortho_button(layout, context, text='Ortho Lock'):
    locked = bool(context.workspace and context.workspace.get(_ORTHO_LOCK_KEY, False))
    layout.operator('mch.ortho_lock', text=text, icon='LOCKED' if locked else 'UNLOCKED', depress=locked)


# -----------------------------------------------------------------------------
# Tool activation
# -----------------------------------------------------------------------------


def activate_mecha_tool(context, tool_id):
    """Select a Mecha tool; drawing tools also become the native active tool."""
    settings = context.scene.mch_settings
    settings.mch_active_tool = tool_id
    native = ts.TOOL_BY_ID[tool_id][5]
    current = ts.native_tool_id(context)
    try:
        if native:
            if context.mode != 'OBJECT' and context.active_object is not None:
                bpy.ops.object.mode_set(mode='OBJECT')
            if current != native:
                bpy.ops.wm.tool_set_by_id(name=native, space_type='VIEW_3D')
        elif current in ts.NATIVE_TO_TOOL:
            bpy.ops.wm.tool_set_by_id(name='builtin.select_box', space_type='VIEW_3D')
    except RuntimeError as ex:
        print('[Mecha Lab] tool switch:', ex)
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type in {'VIEW_3D', 'PROPERTIES'}:
                area.tag_redraw()


# -----------------------------------------------------------------------------
# Native WorkSpaceTools (left T-toolbar, one undo step per stroke)
# -----------------------------------------------------------------------------


def _tool_keymap(mode):
    return (
        ('mch.cut_stroke', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'any': True},
         {'properties': [('mode', mode)]}),
        ('mch.rmb_gate', {'type': 'RIGHTMOUSE', 'value': 'PRESS'}, None),
        ('mch.space_tools', {'type': 'SPACE', 'value': 'PRESS'}, None),
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


NATIVE_TOOLS = (MCH_TOOL_cut, MCH_TOOL_split, MCH_TOOL_mask)


def register_native_tools():
    global _tools_registered
    if _tools_registered:
        return
    bpy.utils.register_tool(MCH_TOOL_cut, separator=True, group=False)
    bpy.utils.register_tool(MCH_TOOL_split, after={MCH_TOOL_cut.bl_idname}, group=False)
    bpy.utils.register_tool(MCH_TOOL_mask, after={MCH_TOOL_split.bl_idname}, group=False)
    _tools_registered = True


def unregister_native_tools():
    global _tools_registered
    if not _tools_registered:
        return
    for tool in reversed(NATIVE_TOOLS):
        try:
            bpy.utils.unregister_tool(tool)
        except (ValueError, RuntimeError):
            pass
    _tools_registered = False


# -----------------------------------------------------------------------------
# Drawing helpers
# -----------------------------------------------------------------------------


def draw_tool_rows(layout, context, scale=2.0):
    """Vertical list: big icon + readable name (left area)."""
    active = ts.effective_tool(context)
    col = layout.column(align=True)
    for tid, label, desc, stem, fallback, native, status in ts.TOOLS:
        row = col.row(align=True)
        iid = icon_id(stem)
        if iid:
            row.template_icon(icon_value=iid, scale=scale)
        sub = row.row(align=True)
        sub.scale_y = scale
        text = label + ('  (todo)' if status == 'TODO' else '')
        kw = {} if iid else {'icon': fallback}
        op = sub.operator('mch.set_tool', text=text, depress=(tid == active), **kw)
        op.tool = tid
        if tid == 'MIRROR':
            col.separator()


def draw_tool_grid(layout, context, columns=4, scale=3.0):
    """Grid of tiles: big icon above a name button (popup / sidebar fallback)."""
    active = ts.effective_tool(context)
    grid = layout.grid_flow(row_major=True, columns=columns, even_columns=True, even_rows=True, align=False)
    for tid, label, desc, stem, fallback, native, status in ts.TOOLS:
        box = grid.box()
        col = box.column(align=True)
        iid = icon_id(stem)
        if iid:
            col.template_icon(icon_value=iid, scale=scale)
        kw = {} if iid else {'icon': fallback}
        text = label + (' (todo)' if status == 'TODO' else '')
        op = col.operator('mch.set_tool', text=text, depress=(tid == active), **kw)
        op.tool = tid


def draw_shape_grid(layout, context, columns=4, scale=2.6):
    brush = context.scene.mch_brush
    grid = layout.grid_flow(row_major=True, columns=columns, even_columns=True, even_rows=True, align=False)
    for sid, label, desc, stem, fallback in ts.SHAPES:
        if sid == 'CUSTOM':
            continue
        box = grid.box()
        col = box.column(align=True)
        iid = icon_id(stem)
        if iid:
            col.template_icon(icon_value=iid, scale=scale)
        kw = {} if iid else {'icon': fallback}
        op = col.operator('mch.set_shape', text=label, depress=(brush.shape == sid), **kw)
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
        box = grid.box()
        col = box.column(align=True)
        iid = cut_presets.preset_icon(stem)
        if iid:
            col.template_icon(icon_value=iid, scale=scale)
        op = col.operator('mch.set_shape', text=name[:18],
                          depress=(brush.shape == 'CUSTOM' and current == stem))
        op.shape = 'CUSTOM'
        op.preset = stem
    row = layout.row(align=True)
    row.operator('mch.import_cut_png', text='Import PNG Shape', icon='IMPORT')
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
    row.enabled = tool in ts.SHAPE_TOOLS
    brush = scene.mch_brush
    for sid, label, desc, stem, fallback in ts.SHAPES:
        if sid == 'CUSTOM':
            continue
        op = row.operator('mch.set_shape', text=label, depress=(brush.shape == sid), **_icon_kw(stem, fallback))
        op.shape = sid
        op.preset = ''
    row.separator()
    sub = row.row(align=True)
    sub.template_icon_view(scene, 'mch_png_preset', show_labels=True, scale=1.0, scale_popup=5.0)
    op = sub.operator('mch.set_shape', text='Custom', depress=(brush.shape == 'CUSTOM'),
                      **_icon_kw('custom', 'IMAGE_DATA'))
    op.shape = 'CUSTOM'
    op.preset = ''
    sub.operator('mch.import_cut_png', text='', icon='IMPORT')
    if tool not in ts.SHAPE_TOOLS:
        layout.label(text='Shapes: Cut / Split / Mask only')
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


class MCH_OT_hotkey(bpy.types.Operator):
    bl_idname = 'mch.hotkey'
    bl_label = 'Mecha Hotkey'
    bl_options = {'INTERNAL'}
    action: EnumProperty(items=[('BOOLEAN', 'Boolean Difference', ''), ('CUT', 'Cut Tool', ''),
                                ('SPLIT', 'Split Tool', '')])

    @classmethod
    def poll(cls, context):
        return (pref('workspace_hotkeys') and ts.is_mecha_workspace(context.workspace)
                and context.mode == 'OBJECT')

    def execute(self, context):
        if self.action == 'BOOLEAN':
            return bpy.ops.mch.boolean('EXEC_DEFAULT', operation='DIFFERENCE')
        activate_mecha_tool(context, self.action)
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
            head.template_icon(icon_value=iid, scale=2.2)
        col = head.column(align=True)
        col.label(text=label.upper())
        col.label(text={'OK': '', 'PARTIAL': 'Status: partial', 'TODO': 'Status: not implemented'}[status])
        if native and ts.native_tool_id(context) != native:
            layout.operator('mch.set_tool', text=f'Activate {label} tool in viewport', icon='RESTRICT_SELECT_OFF').tool = tid
        drawer = _drawers().get(tool_id)
        if drawer is not None:
            drawer(layout, context)


def _drawers():
    from . import ui_tool_settings
    return ui_tool_settings.DRAWERS


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
        return hasattr(context.scene, 'mch_settings')

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
            col.prop(p, 'space_menu')
            col.prop(p, 'workspace_hotkeys')
        layout.label(text='Hotkeys only work in MECHA LAB', icon='INFO')
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
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (space is not None and space.type == 'PROPERTIES'
                and ts.is_mecha_workspace(context.workspace) and hasattr(context.scene, 'mch_settings'))

    def draw(self, context):
        layout = self.layout
        layout.label(text='MECHA LAB TOOLS')
        draw_tool_rows(layout, context, scale=2.0)
        layout.separator()
        layout.label(text='Space: tool menu', icon='EVENT_SPACEKEY')


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
        layout.separator()
        layout.label(text='Custom PNG Shapes', icon='IMAGE_DATA')
        draw_custom_grid(layout, context, columns=4, scale=2.6)
        layout.label(text='RMB double-click in the viewport exits the tool')


class MCH_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = ADDON_ID

    space_menu: BoolProperty(name='Space = Mecha Tool Menu', default=True,
                             description='Only inside the MECHA LAB workspace; elsewhere Space keeps Blender behaviour')
    workspace_hotkeys: BoolProperty(name='B / C Hotkeys', default=True,
                                    description='B = Boolean Difference, C = Cut tool, only inside MECHA LAB')

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'space_menu')
        layout.prop(self, 'workspace_hotkeys')
        layout.label(text='Key bindings can be changed in Preferences > Keymap ("mch.").')
        layout.operator('mch.workspace_open', icon='WORKSPACE')


CLASSES = (
    MCH_AddonPreferences,
    MCH_OT_workspace_open, MCH_OT_workspace_repair, MCH_OT_workspace_save_startup,
    MCH_OT_set_tool, MCH_OT_set_shape, MCH_OT_space_tools, MCH_OT_hotkey, MCH_OT_ortho_lock,
    MCH_PT_tools, MCH_PT_main, MCH_PT_workspace, MCH_PT_tool_list, MCH_PT_tool_popup, MCH_PT_shape_popup,
)


def register_keymaps():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon if wm else None
    if kc is None:
        return
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    _keymaps.append((km, km.keymap_items.new('mch.space_tools', 'SPACE', 'PRESS')))
    km = kc.keymaps.new(name='Object Mode', space_type='EMPTY')
    item = km.keymap_items.new('mch.hotkey', 'B', 'PRESS')
    item.properties.action = 'BOOLEAN'
    _keymaps.append((km, item))
    item = km.keymap_items.new('mch.hotkey', 'C', 'PRESS')
    item.properties.action = 'CUT'
    _keymaps.append((km, item))


def unregister_keymaps():
    for km, item in _keymaps:
        try:
            km.keymap_items.remove(item)
        except (ReferenceError, RuntimeError):
            pass
    _keymaps.clear()


def register():
    _load_icons()
    for c in CLASSES:
        bpy.utils.register_class(c)
    register_native_tools()
    bpy.types.VIEW3D_HT_tool_header.prepend(draw_shape_palette)
    if hasattr(bpy.types, 'TOPBAR_MT_workspace_menu'):
        bpy.types.TOPBAR_MT_workspace_menu.append(draw_workspace_menu)
    register_keymaps()


def unregister():
    if bpy.app.timers.is_registered(_ortho_watchdog):
        bpy.app.timers.unregister(_ortho_watchdog)
    unregister_keymaps()
    if hasattr(bpy.types, 'TOPBAR_MT_workspace_menu'):
        bpy.types.TOPBAR_MT_workspace_menu.remove(draw_workspace_menu)
    bpy.types.VIEW3D_HT_tool_header.remove(draw_shape_palette)
    unregister_native_tools()
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
    _free_icons()
