"""0.24.49 RMB Actions popup, laid out after Substance 3D Modeler's right-click Actions menu.

One popup at the mouse, in labelled sections of big one-click buttons, showing only what fits what is
selected:
- left: TOOLS - Recent (last 5) and Favorites (tool_recent);
- right: ACTIONS on the selection (Duplicate, Join, Delete, Origin), SYMMETRY (live Mirror X / Y / Z on the
  part - cuts and plates follow it), VISIBILITY (Hide, Show All, Isolate) and LIVE (Apply / Remove for a live
  result, Apply Modifiers);
- under it, in a drawing tool, its shapes / profiles as before (the caller draws those).

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
    if ob is None:
        return None
    m = ob.modifiers.get(MIRROR_NAME)
    if m is not None:
        return m
    return next((m for m in ob.modifiers if m.type == 'MIRROR'), None)


def toggle_mirror(ob, axis):
    """Turn one axis of the part's live Mirror on / off (made on first use, removed when no axis is left).
    Returns the axis state now."""
    m = mirror_mod(ob)
    if m is None:
        m = ob.modifiers.new(MIRROR_NAME, 'MIRROR')
        m.use_axis = (False, False, False)
        m.use_clip = True
        m.use_mirror_merge = True
    axes = list(m.use_axis)
    axes[axis] = not axes[axis]
    m.use_axis = axes
    if not any(axes):
        ob.modifiers.remove(m)
        return False
    return axes[axis]


def _section(col, title, icon):
    box = col.box()
    box.label(text=title, icon=icon)
    return box


def _grid(box, columns=3):
    g = box.grid_flow(row_major=True, columns=columns, even_columns=True, align=True)
    g.scale_y = 1.35
    return g


def draw_actions(layout, context):
    """Right column: what can be done to the selection."""
    ob = context.active_object
    meshes = _meshes(context)
    col = layout.column(align=False)

    box = _section(col, 'ACTIONS' + (f'  |  {ob.name}' if ob else ''), 'OBJECT_DATA')
    g = _grid(box)
    sub = g.row(align=True)
    sub.enabled = bool(context.selected_objects)
    sub.operator('object.duplicate_move', text='Duplicate', icon='DUPLICATE')
    sub = g.row(align=True)
    sub.enabled = len(meshes) > 1
    sub.operator('object.join', text='Join', icon='AUTOMERGE_ON')
    sub = g.row(align=True)
    sub.enabled = bool(context.selected_objects)
    sub.operator('object.delete', text='Delete', icon='TRASH').use_global = False
    sub = g.row(align=True)
    sub.enabled = bool(meshes)
    sub.operator('mch.object_tidy', text='Origin to Geometry', icon='PIVOT_MEDIAN').action = 'ORIGIN_GEOMETRY'
    sub = g.row(align=True)
    sub.enabled = bool(meshes)
    sub.operator('mch.object_tidy', text='Reset Axis', icon='ORIENTATION_GLOBAL').action = 'RESET_AXIS'
    sub = g.row(align=True)
    sub.enabled = bool(meshes)
    sub.operator('object.shade_auto_smooth', text='Auto Smooth', icon='MOD_SMOOTH')

    box = _section(col, 'SYMMETRY', 'MOD_MIRROR')
    m = mirror_mod(ob) if ob is not None and ob.type == 'MESH' else None
    row = box.row(align=True)
    row.scale_y = 1.35
    row.enabled = ob is not None and ob.type == 'MESH'
    for i, name in enumerate('XYZ'):
        on = bool(m and m.use_axis[i])
        row.operator('mch.actions_mirror', text=name, depress=on).axis = i
    if m is None:
        box.label(text='Live mirror on the part: cuts and plates follow it', icon='INFO')

    box = _section(col, 'VISIBILITY', 'HIDE_OFF')
    g = _grid(box)
    sub = g.row(align=True)
    sub.enabled = bool(context.selected_objects)
    sub.operator('object.hide_view_set', text='Hide', icon='HIDE_ON').unselected = False
    g.operator('object.hide_view_clear', text='Show All', icon='HIDE_OFF')
    sub = g.row(align=True)
    sub.enabled = bool(context.selected_objects) or bool(getattr(context.space_data, 'local_view', None))
    sub.operator('view3d.localview', text='Isolate', icon='ZOOM_SELECTED')

    live = _live_rows(context)
    if live:
        box = _section(col, 'LIVE RESULT', 'MODIFIER')
        g = _grid(box, 2)
        for op, text, icon, props in live:
            b = g.operator(op, text=text, icon=icon)
            for k, v in props.items():
                setattr(b, k, v)


def _live_rows(context):
    """Apply / Remove buttons for the live result under the selection (only those that fit)."""
    rows = []
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


def draw(layout, context, scale=1.4):
    """The whole Actions block: tools (left) | actions on the selection (right)."""
    from . import tool_recent
    split = layout.split(factor=0.5)
    tool_recent.draw(split.column(), context, scale)
    draw_actions(split.column(), context)


class MCH_OT_actions_mirror(bpy.types.Operator):
    """Live mirror of the active part on this axis (on / off); Cut, Plate and other tools follow it"""
    bl_idname = 'mch.actions_mirror'
    bl_label = 'Symmetry Axis'
    bl_options = {'REGISTER', 'UNDO'}
    axis: IntProperty(default=0, min=0, max=2)

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.type == 'MESH' and context.mode == 'OBJECT'

    def execute(self, context):
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
    bl_ui_units_x = 30

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, 'mch_settings')

    def draw(self, context):
        layout = self.layout
        draw(layout, context)
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
        bpy.ops.wm.call_panel(name=MCH_PT_actions_popup.bl_idname, keep_open=False)
        return {'FINISHED'}

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
        except (ReferenceError, RuntimeError):
            pass
    _keymaps.clear()
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
