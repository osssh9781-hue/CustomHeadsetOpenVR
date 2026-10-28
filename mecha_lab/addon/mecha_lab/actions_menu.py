"""0.24.49 RMB Actions popup, laid out after Substance 3D Modeler's right-click Actions menu.

One popup at the mouse, in labelled sections of big one-click buttons, showing only what fits what is
selected:
- left: a strip of tool buttons - Recent (last 5), then Favorites, the star pins the current tool;
- middle: the tool's own card (its shapes / profiles, as before);
- right: the Actions panel - icon buttons in threes under small section titles: Actions (Duplicate, Join,
  Delete, Origin, Reset Axis, Auto Smooth), Resolution (Remesh, Quad Remesh, Low Poly), Symmetry (live Mirror
  X / Y / Z on the part - cuts and plates follow it), Repetition (Radial Array, Curve Array, Radial Symmetry),
  Visibility (Hide, Show All, Isolate) and Live (Apply / Remove for a live result, Apply Modifiers).

RMB in a drawing tool opens it (single click; double click still exits the tool).  In Select / Move it
replaces Blender's object context menu inside the MECHA LAB workspace only (Preferences: RMB Actions Menu),
with a button for Blender's own menu.
"""
from __future__ import annotations

import bpy
from bpy.props import IntProperty

from . import tool_state as ts

MIRROR_NAME = 'MCH_Symmetry'


def _meshes(context):
    return [o for o in context.selected_objects if o.type == 'MESH']


def mirror_mod(ob):
    """0.24.52 the part's live mirror (one name now: mirror_tools' MCH_Mirror; the 0.24.49 name still read)."""
    from . import symmetry
    return symmetry.mirror_mod(ob)


def toggle_mirror(ob, axis):
    """Turn one mirror plane of the part on / off (0.24.52: the Symmetry system - same mirror as Alt+X, so its
    card, Apply and Enter see it).  Returns the axis state now."""
    from . import symmetry
    return symmetry.toggle_axis(bpy.context, ob, axis)


def _header(col, title):
    """Section title like Modeler's: small, centred, between thin lines."""
    col.separator(type='LINE')
    r = col.row()
    r.alignment = 'CENTER'
    r.active = False                       # muted grey
    r.label(text=title)


def _grid(col, columns=3):
    g = col.grid_flow(row_major=True, columns=columns, even_columns=True, even_rows=True, align=False)
    g.scale_y = 1.6
    return g


def _btn(grid, op, icon, enabled=True, depress=False, **props):
    """One icon-only button (the operator's tooltip names it)."""
    cell = grid.row(align=True)
    cell.enabled = enabled
    b = cell.operator(op, text='', icon=icon, depress=depress)
    for k, v in props.items():
        setattr(b, k, v)
    return b


def _tool_btn(grid, tool, active):
    cell = grid.row(align=True)
    b = cell.operator('mch.set_tool', text='', icon=TOOL_ICONS.get(tool, 'TOOL_SETTINGS'), depress=(tool == active))
    b.tool = tool


TOOL_ICONS = {'RADIAL': 'MOD_SCREW', 'ARRAY': 'MOD_ARRAY', 'MIRROR': 'MOD_MIRROR', 'RSYM': 'FORCE_FORCE'}


def draw_actions(layout, context):
    """Right panel: what can be done to the selection, icon buttons in threes under small section titles
    (Substance 3D Modeler's Actions panel)."""
    ob = context.active_object
    meshes = _meshes(context)
    sel = bool(context.selected_objects)
    mesh_on = ob is not None and ob.type == 'MESH'
    col = layout.column(align=True)
    r = col.row()
    r.alignment = 'CENTER'
    r.label(text=ob.name if ob is not None else 'Nothing selected', icon='OBJECT_DATA' if ob else 'INFO')

    _header(col, 'Actions')
    g = _grid(col)
    _btn(g, 'mch.duplicate', 'DUPLICATE', sel)
    _btn(g, 'object.join', 'AUTOMERGE_ON', len(meshes) > 1)
    _btn(g, 'object.delete', 'TRASH', sel, use_global=False)
    _btn(g, 'mch.object_tidy', 'PIVOT_MEDIAN', bool(meshes), action='ORIGIN_GEOMETRY')
    _btn(g, 'mch.object_tidy', 'ORIENTATION_GLOBAL', bool(meshes), action='RESET_AXIS')
    _btn(g, 'object.shade_auto_smooth', 'MOD_SMOOTH', bool(meshes))

    _header(col, 'Resolution')
    g = _grid(col)
    _btn(g, 'mch.one_click_remesh', 'MOD_REMESH', mesh_on)
    _btn(g, 'mch.quad_remesh', 'MESH_GRID', mesh_on)
    _btn(g, 'mch.lowpoly_make', 'MOD_DECIM', mesh_on)

    _header(col, 'Symmetry')
    m = mirror_mod(ob) if mesh_on else None
    g = _grid(col)
    for i, icon in enumerate(('AXIS_SIDE', 'AXIS_FRONT', 'AXIS_TOP')):
        _btn(g, 'mch.actions_mirror', icon, mesh_on, depress=bool(m and m.use_axis[i]), axis=i)

    _header(col, 'Repetition')
    active = ts.effective_tool(context)
    g = _grid(col)
    for tool in ('RADIAL', 'ARRAY', 'RSYM'):
        if tool in ts.TOOL_BY_ID:
            _tool_btn(g, tool, active)

    _header(col, 'Visibility')
    g = _grid(col)
    _btn(g, 'object.hide_view_set', 'HIDE_ON', sel, unselected=False)
    _btn(g, 'object.hide_view_clear', 'HIDE_OFF')
    _btn(g, 'view3d.localview', 'ZOOM_SELECTED', sel or bool(getattr(context.space_data, 'local_view', None)))

    live = _live_rows(context)
    if live:
        _header(col, 'Live')
        g = _grid(col)
        for op, _text, icon, props in live:
            _btn(g, op, icon, **props)


def _live_rows(context):
    """Apply / Remove buttons for the live result under the selection (only those that fit)."""
    rows = []
    try:
        from . import last_op                          # 0.24.82 the last drawn part, with the settings of now
        if last_op.available(context):
            rows.append(('mch.last_redo', 'Redo Last: ' + last_op.label(), 'FILE_REFRESH', {}))
    except (ImportError, AttributeError, KeyError, TypeError):
        pass
    try:
        from . import ramp_edit
        if ramp_edit.live_target(context) is not None:
            rows += [('mch.ramp_apply', 'Apply Ramp', 'CHECKMARK', {}),
                     ('mch.ramp_remove', 'Remove Ramp', 'X', {})]
    except (ImportError, AttributeError, KeyError, TypeError):
        pass
    try:
        from . import quad_remesh
        if quad_remesh.is_quad(context.active_object):
            rows += [('mch.quad_apply', 'Apply Quad', 'CHECKMARK', {}),
                     ('mch.quad_show_source', 'Show Original', 'HIDE_OFF', {})]
    except (ImportError, AttributeError):
        pass
    ob = context.active_object
    if ob is not None and ob.type == 'MESH' and ob.modifiers:
        rows.append(('mch.actions_apply_modifiers', 'Apply Modifiers', 'MODIFIER_ON', {}))
    return rows


def draw_tool_strip(layout, context):
    """Left strip: Recent then Favorites as a column of tool buttons, the star pins the current tool."""
    from . import tool_recent
    from .workspace_ui import icon_id
    active = ts.effective_tool(context)
    col = layout.column(align=True)
    col.scale_y = 1.5

    def tool(tid):
        t = ts.TOOL_BY_ID[tid]
        iid = icon_id(t[3])
        kw = {'icon_value': iid} if iid else {'icon': t[4]}
        col.operator('mch.set_tool', text='', depress=(tid == active), **kw).tool = tid

    for tid in tool_recent.recent():
        tool(tid)
    col.separator(type='LINE')
    for tid in tool_recent.favorites():
        tool(tid)
    if tool_recent._valid(active):
        pinned = active in tool_recent.favorites()
        col.separator()
        col.operator('mch.tool_fav_toggle', text='', icon='SOLO_ON' if pinned else 'SOLO_OFF',
                     depress=pinned).tool = active
    col.separator()
    col.scale_y = 1.0
    col.prop(context.window_manager, 'mch_fav_set', text='', icon='SOLO_ON')


def draw(layout, context, middle=None):
    """Three panels side by side like Modeler: tool strip | the tool's settings (middle) | Actions."""
    row = layout.row(align=False)
    draw_tool_strip(row.column(), context)
    if middle is not None:
        mid = row.column()
        mid.ui_units_x = 16
        middle(mid)
    right = row.column()
    right.ui_units_x = 8
    draw_actions(right, context)


class MCH_OT_actions_mirror(bpy.types.Operator):
    """Live mirror of the active part on this axis (on / off); Cut, Plate and other tools follow it"""
    bl_idname = 'mch.actions_mirror'
    bl_label = 'Symmetry Axis'
    bl_options = {'REGISTER', 'UNDO'}
    axis: IntProperty(default=0, min=0, max=2)

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        if ob is not None and context.mode == 'OBJECT' and ob.type == 'EMPTY':
            from . import groups
            return groups.is_group(ob)
        return ob is not None and ob.type == 'MESH' and context.mode == 'OBJECT'

    def execute(self, context):
        from . import groups
        g = context.active_object
        if groups.is_group(g):                 # 0.24.57 a group selected: the whole group is mirrored
            axes = list(groups.repeat_axes(g)) if groups.repeat_mode(g) in {'MIRROR', 'KALEIDO'} else [False] * 3
            axes[self.axis] = not axes[self.axis]
            if any(axes):
                mode = 'KALEIDO' if groups.repeat_mode(g) in {'RADIAL', 'KALEIDO'} else 'MIRROR'
                groups.set_repeat(context, g, mode=mode, axes=axes)
            else:
                groups.set_repeat(context, g, mode='RADIAL' if groups.repeat_mode(g) == 'KALEIDO' else 'OFF')
            context.window_manager.mch_sym_card = g.name
            self.report({'INFO'}, f'{g.name}: Mirror {"XYZ"[self.axis]} ' + ('on' if axes[self.axis] else 'off'))
            return {'FINISHED'}
        on = toggle_mirror(context.active_object, self.axis)
        self.report({'INFO'}, f'Symmetry {"XYZ"[self.axis]}: ' + ('on' if on else 'off'))
        return {'FINISHED'}


class MCH_OT_actions_apply_modifiers(bpy.types.Operator):
    """Apply all modifiers of the selected meshes, top to bottom"""
    bl_idname = 'mch.actions_apply_modifiers'
    bl_label = 'Apply Modifiers'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and any(o.modifiers for o in _meshes(context))

    def execute(self, context):
        from . import safe_apply
        done = 0
        for ob in _meshes(context):
            for mod in list(ob.modifiers):
                try:
                    safe_apply(context, ob, mod)
                    done += 1
                except RuntimeError as ex:
                    self.report({'WARNING'}, f'{ob.name}: {mod.name} not applied ({ex})')
        self.report({'INFO'}, f'{done} modifiers applied')
        return {'FINISHED'}


def select_rmb_ok(context):
    """RMB in Select / Move opens the Actions popup: MECHA LAB workspace, Object Mode, preference on."""
    from . import bottom_bar
    from .workspace_ui import pref
    return (pref('rmb_actions', True) and bottom_bar.ui_active(context) and context.area is not None
            and context.area.type == 'VIEW_3D' and bottom_bar.in_select(context))


class MCH_PT_actions_popup(bpy.types.Panel):
    bl_idname = 'MCH_PT_actions_popup'
    bl_label = 'MECHA LAB | Actions'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'HEADER'
    bl_ui_units_x = 34

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, 'mch_settings')

    def draw(self, context):
        layout = self.layout
        from . import tool_recent
        draw(layout, context, middle=lambda col: tool_recent.draw(col, context))
        row = layout.row()
        row.operator('wm.call_menu', text='Blender Object Menu', icon='BLENDER').name = 'VIEW3D_MT_object_context_menu'


class MCH_OT_actions_menu(bpy.types.Operator):
    """RMB in Select / Move (MECHA LAB): Actions popup - recent tools, favorites, actions on the selection"""
    bl_idname = 'mch.actions_menu'
    bl_label = 'Mecha Actions'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return select_rmb_ok(context)      # elsewhere RMB keeps Blender's meaning

    def invoke(self, context, event):
        from . import zb_sculpt
        if zb_sculpt.nav_on(context):                 # 0.24.60 ZBrush style: right-drag turns the view
            self.rmb = zb_sculpt.RMBDrag()
            self.rmb.rmb_drag_start(context, event)
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        return self._open(context)

    def _open(self, context):
        from . import mecha_menu
        if not (mecha_menu.use_menu() and mecha_menu.open_menu(context, 'right click (Select)')):   # 0.24.50 Mecha Menu
            bpy.ops.wm.call_panel(name=MCH_PT_actions_popup.bl_idname, keep_open=False)
        return {'FINISHED'}

    def modal(self, context, event):
        if self.rmb.rmb_drag_check(context, event):
            return {'FINISHED'}
        if event.type == 'RIGHTMOUSE' and event.value == 'RELEASE':
            return self._open(context)
        if event.type == 'ESC':
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}

    def execute(self, context):
        bpy.ops.wm.call_panel(name=MCH_PT_actions_popup.bl_idname, keep_open=False)
        return {'FINISHED'}


CLASSES = (MCH_OT_actions_mirror, MCH_OT_actions_apply_modifiers, MCH_PT_actions_popup, MCH_OT_actions_menu)
_keymaps = []


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon if wm else None
    if kc is not None:
        km = kc.keymaps.new(name='Object Mode', space_type='EMPTY')
        _keymaps.append((km, km.keymap_items.new('mch.actions_menu', 'RIGHTMOUSE', 'PRESS')))


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
