"""0.12 Mecha Lab UX (from the browser prototype v2.1): bottom toolbar, Q pie,
Shift+Q toggle between Select / Move and the last modelling tool.

All of it is active only in the MECHA LAB workspace (Object Mode); outside it
the keys keep their Blender meaning because the operators' poll fails there.

Bottom toolbar = 2D button gizmos (the same kind as the viewport navigation
buttons): no modal operator, so it cannot fight the Cut / Split stroke modal.
"""
import bpy
from bpy.props import EnumProperty, StringProperty

from . import tool_state as ts

# (id, label, key, Blender icon, operator, tool argument)
BAR_TOOLS = (
    ('SELECT', 'Select', 'F', 'RESTRICT_SELECT_OFF', 'mch.select_move', None),
    ('CUT', 'Cut', 'C', 'SELECT_SUBTRACT', 'mch.set_tool', 'CUT'),
    ('SPLIT', 'Split', '', 'MOD_EDGESPLIT', 'mch.set_tool', 'SPLIT'),
    ('BASE', 'Base', '', 'MOD_SOLIDIFY', 'mch.set_tool', 'BASE'),
    ('BOOLEAN', 'Boolean', 'B', 'MOD_BOOLEAN', 'mch.set_tool', 'BOOLEAN'),
    ('MIRROR', 'Mirror', '', 'MOD_MIRROR', 'mch.set_tool', 'MIRROR'),
    ('PRIMITIVE', 'Primitive', '', 'MESH_CUBE', 'mch.set_tool', 'PRIMITIVE'),
    ('RADIAL', 'Radial', '', 'MOD_SCREW', 'mch.set_tool', 'RADIAL'),
)
SELECT_NATIVE = {'builtin.move', 'builtin.select', 'builtin.select_box', 'builtin.select_circle',
                 'builtin.select_lasso', 'builtin.rotate', 'builtin.scale', 'builtin.transform'}
SIZES = {'S': 34, 'M': 42, 'L': 52}       # button diameter in px at UI scale 1
ACCENT = (1.0, 0.62, 0.16)
BASE_COL = (0.17, 0.19, 0.23)
_label_handle = None


def _pref(name, default=True):
    from .workspace_ui import pref
    return pref(name, default)


def ui_active(context):
    return (ts.is_mecha_workspace(getattr(context, 'workspace', None)) and context.mode == 'OBJECT')


def toolbar_layout(region_width, ui_scale=1.0, count=len(BAR_TOOLS), size='M', margin=26.0):
    """Centres (x, y) of the toolbar buttons in region pixels, bottom centre."""
    d = SIZES.get(size, SIZES['M']) * ui_scale
    gap = 8.0 * ui_scale
    total = count * d + (count - 1) * gap
    x0 = region_width / 2.0 - total / 2.0 + d / 2.0
    y = margin * ui_scale + d / 2.0
    return [(x0 + i * (d + gap), y) for i in range(count)], d


def current_bar_tool(context):
    """Which toolbar button shows as active."""
    wm = context.window_manager
    native = ts.native_tool_id(context)
    if native in SELECT_NATIVE and getattr(wm, 'mch_ui_mode', 'TOOL') == 'SELECT':
        return 'SELECT'
    try:
        return ts.effective_tool(context)
    except (AttributeError, KeyError, TypeError):
        return ''


def note_tool(context, tool_id):
    """Called by activate_mecha_tool: remember the last modelling tool (not undoable)."""
    wm = context.window_manager
    if wm is None or not hasattr(wm, 'mch_last_model'):
        return
    wm.mch_ui_mode = 'TOOL'
    if tool_id in ts.TOOL_BY_ID:
        wm.mch_last_model = tool_id


def note_select(context):
    wm = context.window_manager
    if wm is not None and hasattr(wm, 'mch_ui_mode'):
        wm.mch_ui_mode = 'SELECT'


def in_select(context):
    wm = context.window_manager
    native = ts.native_tool_id(context)
    return native in SELECT_NATIVE and (getattr(wm, 'mch_ui_mode', 'TOOL') == 'SELECT' or
                                        ts.TOOL_BY_ID.get(ts.effective_tool(context), (None,) * 6)[5] is not None)


# -----------------------------------------------------------------------------
# Q pie / Shift+Q
# -----------------------------------------------------------------------------


class MCH_MT_tool_pie(bpy.types.Menu):
    bl_idname = 'MCH_MT_tool_pie'
    bl_label = 'Mecha Tools'

    def draw(self, context):
        pie = self.layout.menu_pie()
        # pie order: W, E, S, N, NW, NE, SW, SE  (N = Select, clockwise as in the prototype)
        order = ('PRIMITIVE', 'SPLIT', 'BOOLEAN', 'SELECT', 'RADIAL', 'CUT', 'MIRROR', 'BASE')
        by_id = {t[0]: t for t in BAR_TOOLS}
        for tid in order:
            t = by_id[tid]
            if t[4] == 'mch.select_move':
                pie.operator('mch.select_move', text='Select / Move  (F)', icon=t[3])
            else:
                op = pie.operator('mch.set_tool', text=t[1] + (f'  ({t[2]})' if t[2] else ''), icon=t[3])
                op.tool = t[5]


class MCH_OT_tool_pie(bpy.types.Operator):
    """Q: all Mecha tools as a pie at the mouse (MECHA LAB only; elsewhere Q = Quick Favorites)"""
    bl_idname = 'mch.tool_pie'
    bl_label = 'Mecha Tool Pie'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return _pref('tool_pie') and ui_active(context) and context.area is not None and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        bpy.ops.wm.call_menu_pie(name=MCH_MT_tool_pie.bl_idname)
        return {'FINISHED'}

    def execute(self, context):
        bpy.ops.wm.call_menu_pie(name=MCH_MT_tool_pie.bl_idname)
        return {'FINISHED'}


class MCH_OT_toggle_last_tool(bpy.types.Operator):
    """Shift+Q: Select / Move <-> the last Mecha modelling tool (its shape and settings are kept)"""
    bl_idname = 'mch.toggle_last_tool'
    bl_label = 'Select <-> Last Tool'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return _pref('last_tool_key') and ui_active(context) and context.area is not None and context.area.type == 'VIEW_3D'

    def execute(self, context):
        from .workspace_ui import activate_mecha_tool
        wm = context.window_manager
        if in_select(context):
            tool = wm.mch_last_model if wm.mch_last_model in ts.TOOL_BY_ID else 'CUT'
            activate_mecha_tool(context, tool)
            self.report({'INFO'}, 'Back to ' + ts.TOOL_BY_ID[tool][1])
        else:
            try:
                current = ts.effective_tool(context)
                if current in ts.TOOL_BY_ID:
                    wm.mch_last_model = current
            except (AttributeError, KeyError, TypeError):
                pass
            bpy.ops.mch.select_move()
        return {'FINISHED'}


class MCH_OT_toggle_targets(bpy.types.Operator):
    """T (Cut / Split tool): Auto Target <-> Selected Only"""
    bl_idname = 'mch.toggle_targets'
    bl_label = 'Toggle Cut Targets'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, 'mch_cut') and ts.effective_tool(context) in {'CUT', 'SPLIT'}

    def execute(self, context):
        cut = context.scene.mch_cut
        cut.targets = 'SELECTED' if cut.targets == 'AUTO' else 'AUTO'
        self.report({'INFO'}, 'Targets: ' + ('Auto (what the shape covers)' if cut.targets == 'AUTO'
                                              else 'Selected only'))
        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# Bottom toolbar (2D button gizmos)
# -----------------------------------------------------------------------------


class MCH_GGT_bottom_toolbar(bpy.types.GizmoGroup):
    bl_idname = 'MCH_GGT_bottom_toolbar'
    bl_label = 'Mecha Bottom Toolbar'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE'}

    @classmethod
    def poll(cls, context):
        return _pref('bottom_toolbar') and ui_active(context)

    def setup(self, context):
        self.buttons = []
        for tid, label, key, icon, op, arg in BAR_TOOLS:
            gz = self.gizmos.new('GIZMO_GT_button_2d')
            gz.icon = icon
            gz.draw_options = {'BACKDROP', 'OUTLINE'}
            props = gz.target_set_operator(op)
            if arg:
                props.tool = arg
            gz.color = BASE_COL
            gz.alpha = 0.9
            gz.color_highlight = (0.32, 0.35, 0.41)
            gz.alpha_highlight = 1.0
            self.buttons.append((tid, gz))

    def draw_prepare(self, context):
        region = context.region
        ui = context.preferences.system.ui_scale
        pos, d = toolbar_layout(region.width, 1.0, len(self.buttons), _pref('toolbar_size', 'M'))
        active = current_bar_tool(context)
        for (tid, gz), (x, y) in zip(self.buttons, pos):
            # 'SCALE' multiplies the gizmo by the UI scale; positions are in region px
            gz.scale_basis = d / 2.0
            gz.matrix_basis[0][3] = x * ui
            gz.matrix_basis[1][3] = y * ui
            on = tid == active
            gz.color = ACCENT if on else BASE_COL
            gz.alpha = 1.0 if on else 0.9


def _draw_labels():
    """Optional names under the toolbar icons (Preferences: Toolbar Labels)."""
    try:
        context = bpy.context
        if not (_pref('bottom_toolbar') and _pref('toolbar_labels', False) and ui_active(context)):
            return
        import blf
        region = context.region
        ui = context.preferences.system.ui_scale
        pos, d = toolbar_layout(region.width, 1.0, len(BAR_TOOLS), _pref('toolbar_size', 'M'))
        active = current_bar_tool(context)
        font = 0
        blf.size(font, 10 * ui)
        for (tid, label, *_), (x, y) in zip(BAR_TOOLS, pos):
            w, _h = blf.dimensions(font, label)
            on = tid == active
            blf.color(font, *(ACCENT if on else (0.85, 0.87, 0.9)), 1.0)
            blf.position(font, x * ui - w / 2, (y - d / 2 - 12) * ui, 0)
            blf.draw(font, label)
    except Exception:            # never break viewport drawing
        pass


CLASSES = (MCH_MT_tool_pie, MCH_OT_tool_pie, MCH_OT_toggle_last_tool, MCH_OT_toggle_targets, MCH_GGT_bottom_toolbar)


def register():
    global _label_handle
    bpy.types.WindowManager.mch_last_model = StringProperty(default='CUT', options={'SKIP_SAVE'})
    bpy.types.WindowManager.mch_ui_mode = EnumProperty(items=[('TOOL', 'Tool', ''), ('SELECT', 'Select', '')],
                                                       default='TOOL', options={'SKIP_SAVE'})
    for c in CLASSES:
        bpy.utils.register_class(c)
    if not bpy.app.background and _label_handle is None:
        _label_handle = bpy.types.SpaceView3D.draw_handler_add(_draw_labels, (), 'WINDOW', 'POST_PIXEL')


def unregister():
    global _label_handle
    if _label_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_label_handle, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _label_handle = None
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
    for n in ('mch_ui_mode', 'mch_last_model'):
        if hasattr(bpy.types.WindowManager, n):
            delattr(bpy.types.WindowManager, n)
