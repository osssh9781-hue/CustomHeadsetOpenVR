"""0.24.50 Quick HUD: the 3-5 settings you change most for the tool that is on, as sliders in the viewport, so
you don't go to the sidebar while drawing.

- drag a slider left / right: change the value (Shift = fine); the live result follows like in the panel
- click (no drag): type the exact value;  Ctrl + click: back to the default
- on / off and choice settings: click flips / steps to the next choice
- the grip on top moves the whole HUD (kept per Blender session)
Shown in MECHA LAB, Object Mode, with a modelling tool on (not in Select / Move), when the tool has no HUD of
its own on screen.  Preferences: Quick HUD.  Everything else stays in the sidebar.
"""
from __future__ import annotations

import bpy
from bpy.props import FloatVectorProperty, StringProperty
from mathutils import Matrix

from . import tool_state as ts

ROW_H = 22.0          # px at UI scale 1
ROW_W = 150.0
GAP = 4.0


# --- what the HUD shows -------------------------------------------------------------------------------------

def _scene(name):
    return lambda context: getattr(context.scene, name, None)


def _base(context):
    from . import base_mesh
    ob = base_mesh.active_live_base(context)
    return ob.mch_base if ob is not None else base_mesh.scene_defaults(context)


def _sdraw(context):
    from . import surface_draw
    ob = surface_draw.live_object(context, 'BAND')
    return ob.mch_sdraw if ob is not None else surface_draw.scene_settings(context.scene, 'BAND')


def _screw(context):
    from . import screw_stamp
    ob = context.active_object
    return ob.mch_screw if screw_stamp.is_screw(ob) else context.scene.mch_screw


def _detail(context):
    from . import plate_detail
    ob = plate_detail.active_detail(context)
    return ob.mch_pdetail if ob is not None else None


def _plate_scene(context):
    from . import armor_plate
    return None if armor_plate.pending_plate(context) is not None else context.scene.mch_plate   # own HUD then


# tool -> [(data resolver, property)]; a property the data does not have is skipped
SPEC = {
    'CUT': [(_scene('mch_cut'), 'depth'), (_scene('mch_cut'), 'gn_finish'), (_scene('mch_cut'), 'gn_width'),
            (_scene('mch_cut'), 'gn_segments'), (_scene('mch_cut'), 'gn_ramp')],
    'SPLIT': [(_scene('mch_cut'), 'split_mode'), (_scene('mch_cut'), 'gap_width'),
              (_scene('mch_cut'), 'side_a_finish'), (_scene('mch_cut'), 'side_a_width')],
    'BASE': [(_base, 'profile'), (_base, 'height'), (_base, 'bevel_width'), (_base, 'bevel_segments'),
             (_base, 'offset')],
    'CBASE': [(_base, 'profile'), (_base, 'peak'), (_base, 'edge_round'), (_base, 'resolution')],
    'PLATE': [(_plate_scene, 'spacing'), (_plate_scene, 'carve_depth')],
    'DETAIL': [(_detail, 'height'), (_detail, 'lift')],
    'DETAIL2': [(_detail, 'height'), (_detail, 'lift')],
    'DETAIL3': [(_detail, 'profile'), (_detail, 'height'), (_detail, 'lift')],
    'SDRAW': [(_sdraw, 'profile'), (_sdraw, 'width'), (_sdraw, 'height'), (_sdraw, 'edge')],
    'SCREW': [(_screw, 'kind'), (_screw, 'radius'), (_screw, 'height')],
    'CMOVE': [(_scene('mch_concept'), 'radius_px'), (_scene('mch_concept'), 'strength'),
              (_scene('mch_concept'), 'falloff')],
    'CPATH': [(_scene('mch_concept'), 'path_method'), (_scene('mch_concept'), 'radius_px'),
              (_scene('mch_concept'), 'path_hardness'), (_scene('mch_concept'), 'path_taper')],
    'TUBE': [(_scene('mch_tube_defaults'), 'radius')],
    'TUBE_SAME': [(_scene('mch_tube_defaults'), 'radius')],
}
MAX_ROWS = 5


def items(context, tool=None):
    """[(data, prop)] the HUD shows now (only properties that exist)."""
    tool = tool or ts.effective_tool(context)
    out = []
    for resolve, prop in SPEC.get(tool, ()):
        try:
            data = resolve(context)
        except (AttributeError, KeyError, TypeError, ImportError):
            data = None
        if data is not None and prop in data.bl_rna.properties:
            out.append((data, prop))
    return out[:MAX_ROWS]


def visible(context):
    from .workspace_ui import pref
    if not pref('quick_hud', True):
        return False
    from . import bottom_bar
    try:
        return bottom_bar.ui_active(context) and not bottom_bar.in_select(context) and bool(items(context))
    except (AttributeError, KeyError, TypeError):
        return False


# --- values -----------------------------------------------------------------------------------------------

def value_text(data, prop):
    rna = data.bl_rna.properties[prop]
    v = getattr(data, prop)
    name = rna.name or prop
    if rna.type == 'ENUM':
        label = next((i.name for i in rna.enum_items if i.identifier == v), str(v))
        return f'{name}  {label}'
    if rna.type == 'BOOLEAN':
        return f'{name}  {"On" if v else "Off"}'
    if rna.type == 'INT':
        return f'{name}  {v}'
    if rna.subtype in {'ANGLE'}:
        import math
        return f'{name}  {math.degrees(v):.0f}°'
    if rna.subtype == 'FACTOR' or rna.subtype == 'PERCENTAGE':
        return f'{name}  {v:.2f}'
    return f'{name}  {v:.3f}'


def drag_value(data, prop, start, dx, fine=False):
    """New value after dragging ``dx`` px from ``start`` (whole soft range ≈ 300 px; ints 1 per 8 px)."""
    rna = data.bl_rna.properties[prop]
    k = 0.1 if fine else 1.0
    if rna.type == 'INT':
        lo, hi = rna.hard_min, rna.hard_max
        return int(max(lo, min(hi, round(start + dx * k / 8.0))))
    lo, hi = rna.soft_min, rna.soft_max
    span = hi - lo
    if not (0.0 < span < 1e6):
        span = max(abs(start) * 2.0, 0.1)
    v = start + dx * k * span / 300.0
    return max(rna.hard_min, min(rna.hard_max, v))


def step_choice(data, prop, step=1):
    rna = data.bl_rna.properties[prop]
    if rna.type == 'BOOLEAN':
        setattr(data, prop, not getattr(data, prop))
        return
    ids = [i.identifier for i in rna.enum_items]
    cur = getattr(data, prop)
    i = ids.index(cur) if cur in ids else 0
    setattr(data, prop, ids[(i + step) % len(ids)])


def reset(data, prop):
    rna = data.bl_rna.properties[prop]
    if getattr(rna, 'is_array', False):
        return
    setattr(data, prop, rna.default)


def layout_rows(region_w, region_h, n, offset=(0.0, 0.0), left=0.0):
    """Upper left, right of Blender's toolbar (``left``), above the Tool Active button: (grip, [row centres])
    in px at UI scale 1; ``offset`` = where the grip moved it."""
    x = min(max(left + 14.0 + ROW_W / 2.0 + offset[0], ROW_W / 2.0 + 4.0), region_w - ROW_W / 2.0 - 4.0)
    top = min(max(region_h - 70.0 + offset[1], (ROW_H + GAP) * (n + 1)), region_h - ROW_H)
    grip = (x, top)
    rows = [(x, top - (ROW_H + GAP) * (i + 1)) for i in range(n)]
    return grip, rows


def _offset(context):
    wm = context.window_manager
    return tuple(getattr(wm, 'mch_hud_offset', (0.0, 0.0)))


def current(context):
    """(items, grip, rows) for drawing, or (None, None, None)."""
    if not visible(context) or context.region is None:
        return None, None, None
    ui = context.preferences.system.ui_scale
    its = items(context)
    left = 0.0
    area = context.area
    tools = next((r for r in area.regions if r.type == 'TOOLS'), None) if area else None
    if tools is not None and tools.width > 1:
        left = max(0.0, float(tools.x + tools.width - context.region.x)) / ui
    grip, rows = layout_rows(context.region.width / ui, context.region.height / ui, len(its), _offset(context),
                             left)
    return its, grip, rows


# --- gizmos -----------------------------------------------------------------------------------------------

def _rect():
    from .primitive_hud import _RECT
    return _RECT


class MCH_GT_quick_slider(bpy.types.Gizmo):
    bl_idname = 'MCH_GT_quick_slider'
    __slots__ = ('shape', 'index', 'init_x', 'init_value', 'moved', 'ctrl')

    def setup(self):
        if not hasattr(self, 'shape'):
            self.shape = self.new_custom_shape('TRIS', _rect())

    def draw(self, context):
        self.draw_custom_shape(self.shape)

    def draw_select(self, context, select_id):
        self.draw_custom_shape(self.shape, select_id=select_id)

    def _item(self, context):
        its = items(context)
        return its[self.index] if self.index < len(its) else (None, None)

    def invoke(self, context, event):
        data, prop = self._item(context)
        if data is None:
            return {'CANCELLED'}
        self.init_x = event.mouse_region_x
        self.init_value = getattr(data, prop)
        self.moved = False
        self.ctrl = event.ctrl
        return {'RUNNING_MODAL'}

    def modal(self, context, event, tweak):
        data, prop = self._item(context)
        if data is None:
            return {'CANCELLED'}
        dx = event.mouse_region_x - self.init_x
        if abs(dx) > 3:
            self.moved = True
        rna = data.bl_rna.properties[prop]
        if self.moved and rna.type in {'INT', 'FLOAT'} and not getattr(rna, 'is_array', False):
            v = drag_value(data, prop, self.init_value, dx, fine=event.shift)
            if v != getattr(data, prop):
                setattr(data, prop, v)
            if context.area:
                context.area.header_text_set(value_text(data, prop) + '   (Shift: fine, Esc / RMB: back)')
        elif self.moved and rna.type == 'ENUM':
            ids = [i.identifier for i in rna.enum_items]
            i0 = ids.index(self.init_value) if self.init_value in ids else 0
            v = ids[int(i0 + dx // 30) % len(ids)]
            if v != getattr(data, prop):
                setattr(data, prop, v)
        return {'RUNNING_MODAL'}

    def exit(self, context, cancel):
        if context.area:
            context.area.header_text_set(None)
        data, prop = self._item(context)
        if data is None:
            return
        if cancel:
            if self.moved:
                setattr(data, prop, self.init_value)
            return
        rna = data.bl_rna.properties[prop]
        if not self.moved:
            if self.ctrl:
                reset(data, prop)
            elif rna.type in {'BOOLEAN', 'ENUM'}:
                step_choice(data, prop)
            else:
                context.window_manager.mch_hud_edit = f'{self.index}'
                try:
                    bpy.ops.wm.call_panel(name=MCH_PT_quick_value.bl_idname, keep_open=False)
                except RuntimeError:
                    pass
                return
        try:
            bpy.ops.ed.undo_push(message='HUD ' + (rna.name or prop))
        except RuntimeError:
            pass


class MCH_GT_quick_grip(bpy.types.Gizmo):
    bl_idname = 'MCH_GT_quick_grip'
    __slots__ = ('shape', 'start', 'init')

    def setup(self):
        if not hasattr(self, 'shape'):
            self.shape = self.new_custom_shape('TRIS', _rect())

    def draw(self, context):
        self.draw_custom_shape(self.shape)

    def draw_select(self, context, select_id):
        self.draw_custom_shape(self.shape, select_id=select_id)

    def invoke(self, context, event):
        self.start = (event.mouse_region_x, event.mouse_region_y)
        self.init = _offset(context)
        return {'RUNNING_MODAL'}

    def modal(self, context, event, tweak):
        ui = context.preferences.system.ui_scale
        context.window_manager.mch_hud_offset = (self.init[0] + (event.mouse_region_x - self.start[0]) / ui,
                                                 self.init[1] + (event.mouse_region_y - self.start[1]) / ui)
        if context.area:
            context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def exit(self, context, cancel):
        if cancel:
            context.window_manager.mch_hud_offset = self.init


class MCH_GGT_quick_hud(bpy.types.GizmoGroup):
    bl_idname = 'MCH_GGT_quick_hud'
    bl_label = 'Mecha Quick HUD'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE'}

    @classmethod
    def poll(cls, context):
        return visible(context)

    def setup(self, context):
        self.sliders = []
        for i in range(MAX_ROWS):
            gz = self.gizmos.new(MCH_GT_quick_slider.bl_idname)
            gz.index = i
            gz.color = (0.20, 0.22, 0.27)
            gz.alpha = 0.9
            gz.color_highlight = (0.34, 0.38, 0.45)
            gz.alpha_highlight = 1.0
            gz.use_draw_scale = False
            self.sliders.append(gz)
        g = self.gizmos.new(MCH_GT_quick_grip.bl_idname)
        g.color = (1.0, 0.62, 0.16)
        g.alpha = 0.55
        g.color_highlight = (1.0, 0.72, 0.3)
        g.alpha_highlight = 0.9
        g.use_draw_scale = False
        self.grip = g

    def draw_prepare(self, context):
        its, grip, rows = current(context)
        ui = context.preferences.system.ui_scale
        for i, gz in enumerate(self.sliders):
            if its is None or i >= len(rows):
                gz.hide = True
                continue
            gz.hide = False
            x, y = rows[i]
            gz.matrix_basis = Matrix.Translation((x * ui, y * ui, 0.0)) @ Matrix.Diagonal(
                (ROW_W / 2.0 * ui, ROW_H / 2.0 * ui, 1.0, 1.0))
        self.grip.hide = its is None
        if its is not None:
            x, y = grip
            self.grip.matrix_basis = Matrix.Translation((x * ui, (y + ROW_H / 4.0) * ui, 0.0)) @ Matrix.Diagonal(
                (ROW_W / 2.0 * ui, 4.0 * ui, 1.0, 1.0))


class MCH_PT_quick_value(bpy.types.Panel):
    """Click on a HUD slider: type the exact value"""
    bl_idname = 'MCH_PT_quick_value'
    bl_label = 'Value'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'HEADER'
    bl_ui_units_x = 12

    def draw(self, context):
        try:
            i = int(context.window_manager.mch_hud_edit)
        except ValueError:
            return
        its = items(context)
        if i < len(its):
            data, prop = its[i]
            self.layout.prop(data, prop)
            self.layout.label(text='Ctrl + click a slider: default', icon='INFO')


_label_handle = None


def _draw_labels():
    try:
        context = bpy.context
        its, grip, rows = current(context)
        if its is None:
            return
        import blf
        ui = context.preferences.system.ui_scale
        blf.size(0, 11 * ui)
        tool = ts.TOOL_BY_ID.get(ts.effective_tool(context))
        gx, gy = grip
        title = (tool[1] if tool else '') + '  ·  drag / click / Ctrl+click'
        blf.color(0, 1.0, 0.62, 0.16, 0.9)
        blf.position(0, (gx - ROW_W / 2.0) * ui, (gy + ROW_H / 4.0 + 7.0) * ui, 0)
        blf.draw(0, title)
        for (data, prop), (x, y) in zip(its, rows):
            text = value_text(data, prop)
            w, _h = blf.dimensions(0, text)
            blf.color(0, 0.95, 0.96, 1.0, 1.0)
            blf.position(0, x * ui - w / 2.0, y * ui - 4.0 * ui, 0)
            blf.draw(0, text)
    except Exception:          # never break viewport drawing
        pass


CLASSES = (MCH_GT_quick_slider, MCH_GT_quick_grip, MCH_GGT_quick_hud, MCH_PT_quick_value)


def register():
    global _label_handle
    bpy.types.WindowManager.mch_hud_offset = FloatVectorProperty(size=2, default=(0.0, 0.0), options={'SKIP_SAVE'})
    bpy.types.WindowManager.mch_hud_edit = StringProperty(default='', options={'SKIP_SAVE'})
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
    for name in ('mch_hud_offset', 'mch_hud_edit'):
        if hasattr(bpy.types.WindowManager, name):
            delattr(bpy.types.WindowManager, name)
