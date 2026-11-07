"""0.24.112 Line HUD: buttons that float next to a swept line (Press plain drag / Base Mesh Line) once it is made.

    (dot)  click = Sharp <-> Round corners         [Thickness ----]  drag = the section's size (width and height
                                                                       together, the stamp kept in proportion)
                                                   [Radius -------]  (Round) drag = the bend radius

(user: "만든 이후에 두께랑 이런 거 실시간으로 조정할 수 있게", "꺾이는 부분이 완전 꺾이는 거랑 라운드로 꺾이는 거 옵션으로 ...
그리고 있는 메쉬 옆에 떠 있는 점으로 내가 클릭하면 변하는 걸로")  The HUD sits by the line's end (where the next stroke
goes on from) and follows it.  Everything it sets is the live object's own settings, so the N panel shows the same
values and Ctrl+Z steps back.  ``hud_layout`` is pure and tested headless; the gizmos need a real viewport."""
from __future__ import annotations

import math

import bpy
from bpy.props import StringProperty
from mathutils import Matrix, Vector

from . import base_mesh
from . import tool_state as ts

ACCENT = (1.0, 0.62, 0.16)
BASE_COL = (0.17, 0.19, 0.23)
ROUND_COL = (0.3, 0.75, 1.0)
BTN = 26.0                 # the corner dot, px at UI scale 1
SLIDER_W, SLIDER_H = 96.0, 18.0
GAP = 8.0
THICK_PX = 160.0           # thickness slider: pixels for x2
RADIUS_PX = 60.0           # radius slider: pixels per 1.0 x width
HUD_TOOLS = {'PRESS', 'BASE'}


def hud_target(context):
    """The live swept line the HUD belongs to (active, selected, made by a line sweep), or None."""
    try:
        if not ts.is_mecha_workspace(getattr(context, 'workspace', None)) or context.mode != 'OBJECT':
            return None
    except (AttributeError, TypeError):
        return None
    ob = base_mesh.active_live_base(context)
    if ob is None or not ob.get(base_mesh.SWEEP_KEY):
        return None
    try:
        tool = ts.effective_tool(context)
    except (AttributeError, KeyError, TypeError):
        tool = ''
    if tool in HUD_TOOLS:
        return ob
    try:
        from .station_gizmos import SELECT_NATIVE
        if ts.native_tool_id(context) in SELECT_NATIVE:
            return ob
    except (ImportError, AttributeError):
        pass
    return None


def hud_layout(end_px, region_w, region_h, btn=BTN, gap=GAP, round_on=False):
    """Pure: where the dot and the sliders go (region px, centres) for a line whose end shows at ``end_px``: to the
    right of the end, kept inside the region.  Keys: 'corner', 'thick' and - Round only - 'radius'."""
    if end_px is None:
        return {}
    x, y = float(end_px[0]), float(end_px[1])
    x0, y0 = x + btn * 1.8, y + btn * 0.9
    total_w = btn + gap + SLIDER_W
    if x0 + total_w > region_w - gap:                      # no room on the right: put it on the left
        x0 = x - btn * 1.8 - total_w + btn
    x0 = max(btn, min(x0, region_w - total_w))
    rows = 2 if round_on else 1
    y0 = max(gap + SLIDER_H * rows, min(y0, region_h - btn))
    lay = {'corner': (x0, y0), 'thick': (x0 + btn / 2 + gap + SLIDER_W / 2, y0)}
    if round_on:
        lay['radius'] = (lay['thick'][0], y0 - SLIDER_H - gap)
    return lay


def line_end_px(context, ob):
    """Region px of the line's end (the far end of its path), or None when off screen."""
    from bpy_extras import view3d_utils
    region, rv3d = context.region, context.region_data
    if region is None or rv3d is None:
        return None
    ends = base_mesh.sweep_ends(ob)
    if not ends:
        return None
    p = view3d_utils.location_3d_to_region_2d(region, rv3d, ends[1])
    return None if p is None else (float(p.x), float(p.y))


def layout_for(context, ob):
    """The HUD layout (region px) for ``ob`` in this region now."""
    end = line_end_px(context, ob)
    if end is None:
        return {}
    ui = context.preferences.system.ui_scale
    lay = hud_layout((end[0] / ui, end[1] / ui), context.region.width / ui, context.region.height / ui,
                     round_on=ob.mch_base.line_corner == 'ROUND')
    return {k: (v[0] * ui, v[1] * ui) for k, v in lay.items()}


# -----------------------------------------------------------------------------
# what the HUD sets
# -----------------------------------------------------------------------------

def thickness(ob):
    return float(ob.mch_base.section_width)


def set_thickness(ob, width, init=None):
    """The section's size: width ``width``, and the height scaled by the same factor (the stamp in proportion).
    ``init`` = (width, height) the drag started from (so a long drag does not drift)."""
    p = ob.mch_base
    w0, h0 = init if init is not None else (p.section_width, p.height)
    width = max(0.001, float(width))
    f = width / max(float(w0), 1e-9)
    p.height = max(0.001, float(h0) * f)
    p.section_width = width


def toggle_corner(ob):
    p = ob.mch_base
    p.line_corner = 'ROUND' if p.line_corner == 'SHARP' else 'SHARP'
    return p.line_corner


class MCH_OT_line_corner_toggle(bpy.types.Operator):
    """Line HUD dot: Sharp (mitred) <-> Round corners on this line"""
    bl_idname = 'mch.line_corner_toggle'
    bl_label = 'Line Corners: Sharp / Round'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hud_target(context) is not None

    def execute(self, context):
        ob = hud_target(context)
        if ob is None:
            return {'CANCELLED'}
        mode = toggle_corner(ob)
        self.report({'INFO'}, f'{ob.name}: {"Round" if mode == "ROUND" else "Sharp"} corners')
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# gizmos
# -----------------------------------------------------------------------------

_RECT = ((-1.0, -1.0, 0.0), (1.0, -1.0, 0.0), (1.0, 1.0, 0.0), (-1.0, -1.0, 0.0), (1.0, 1.0, 0.0), (-1.0, 1.0, 0.0))


class MCH_GT_line_slider(bpy.types.Gizmo):
    bl_idname = 'MCH_GT_line_slider'
    __slots__ = ('shape', 'kind', 'init_x', 'init_w', 'init_h', 'init_r')

    def setup(self):
        if not hasattr(self, 'shape'):
            self.shape = self.new_custom_shape('TRIS', _RECT)
        if not hasattr(self, 'kind'):
            self.kind = 'thick'

    def draw(self, context):
        self.draw_custom_shape(self.shape)

    def test_select(self, context, location):
        """A 2D gizmo group picks by this (not by draw_select): inside the slider's rectangle?"""
        m = self.matrix_basis
        cx, cy, hw, hh = m[0][3], m[1][3], abs(m[0][0]), abs(m[1][1])
        return 0 if abs(location[0] - cx) <= hw and abs(location[1] - cy) <= hh else -1

    def invoke(self, context, event):
        ob = hud_target(context)
        if ob is None:
            return {'CANCELLED'}
        self.init_x = event.mouse_region_x
        self.init_w, self.init_h = float(ob.mch_base.section_width), float(ob.mch_base.height)
        self.init_r = float(ob.mch_base.corner_radius)
        return {'RUNNING_MODAL'}

    def modal(self, context, event, tweak):
        ob = hud_target(context)
        if ob is None:
            return {'CANCELLED'}
        dx = (event.mouse_region_x - self.init_x) / max(context.preferences.system.ui_scale, 1e-6)
        if 'PRECISE' in tweak:
            dx *= 0.2
        if self.kind == 'radius':
            r = max(0.1, min(20.0, self.init_r + dx / RADIUS_PX))
            if abs(r - ob.mch_base.corner_radius) > 1e-6:
                ob.mch_base.corner_radius = r
            text = f'Corner Radius: {r:.2f} x width'
        else:
            w = max(0.001, self.init_w * (2.0 ** (dx / THICK_PX)))
            if abs(w - ob.mch_base.section_width) > 1e-7:
                set_thickness(ob, w, (self.init_w, self.init_h))
            text = f'Thickness: {w:.3f}'
        if context.area:
            context.area.header_text_set(text + '   (drag left / right, Shift = fine)')
        return {'RUNNING_MODAL'}

    def exit(self, context, cancel):
        if context.area:
            context.area.header_text_set(None)
        if cancel:
            ob = hud_target(context)
            if ob is not None:
                if self.kind == 'radius':
                    ob.mch_base.corner_radius = self.init_r
                else:
                    set_thickness(ob, self.init_w, (self.init_w, self.init_h))


class MCH_GGT_line_hud(bpy.types.GizmoGroup):
    bl_idname = 'MCH_GGT_line_hud'
    bl_label = 'Line HUD'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE'}

    @classmethod
    def poll(cls, context):
        return hud_target(context) is not None

    def setup(self, context):
        self.items = {}
        gz = self.gizmos.new('GIZMO_GT_button_2d')
        gz.icon = 'SHARPCURVE'
        gz.draw_options = {'BACKDROP', 'OUTLINE'}
        gz.target_set_operator('mch.line_corner_toggle')
        gz.color = BASE_COL
        gz.alpha = 0.92
        gz.color_highlight = (0.32, 0.35, 0.41)
        gz.alpha_highlight = 1.0
        self.items['corner'] = gz
        for kind in ('thick', 'radius'):
            gz = self.gizmos.new(MCH_GT_line_slider.bl_idname)
            gz.kind = kind
            gz.color = (0.24, 0.27, 0.32)
            gz.alpha = 0.95
            gz.color_highlight = (0.36, 0.40, 0.47)
            gz.alpha_highlight = 1.0
            gz.use_draw_scale = False
            self.items[kind] = gz

    def draw_prepare(self, context):
        ob = hud_target(context)
        lay = layout_for(context, ob) if ob is not None else {}
        ui = context.preferences.system.ui_scale
        try:
            from .workspace_ui import handle_scale
            f = min(1.6, handle_scale())
        except (ImportError, AttributeError):
            f = 1.0
        round_on = ob is not None and ob.mch_base.line_corner == 'ROUND'
        for name, gz in self.items.items():
            pos = lay.get(name)
            gz.hide = pos is None
            if gz.hide:
                continue
            if name == 'corner':
                gz.icon = 'SPHERECURVE' if round_on else 'SHARPCURVE'
                gz.color = ROUND_COL if round_on else BASE_COL
                gz.scale_basis = BTN / 2.0 * f
                gz.matrix_basis[0][3] = pos[0]
                gz.matrix_basis[1][3] = pos[1]
                continue
            gz.matrix_basis = Matrix.Translation((pos[0], pos[1], 0.0)) @ Matrix.Diagonal(
                (SLIDER_W * ui / 2, SLIDER_H * ui / 2, 1.0, 1.0))


def _draw_labels():
    """The dot's state and the slider values, in text."""
    try:
        context = bpy.context
        ob = hud_target(context)
        if ob is None:
            return
        lay = layout_for(context, ob)
        if not lay:
            return
        import blf
        ui = context.preferences.system.ui_scale
        font = 0
        blf.size(font, 11 * ui)
        p = ob.mch_base
        round_on = p.line_corner == 'ROUND'
        x, y = lay['corner']
        blf.color(font, *(ROUND_COL if round_on else (0.85, 0.87, 0.9)), 1.0)
        blf.position(font, x - BTN * 0.55 * ui, y + BTN * 0.75 * ui, 0)
        blf.draw(font, 'Round' if round_on else 'Sharp')
        blf.color(font, 1.0, 1.0, 1.0, 1.0)
        x, y = lay['thick']
        text = f'Thickness  {p.section_width:.3f}'
        w, _h = blf.dimensions(font, text)
        blf.position(font, x - w / 2, y - 4 * ui, 0)
        blf.draw(font, text)
        if 'radius' in lay:
            x, y = lay['radius']
            text = f'Radius  {p.corner_radius:.2f} x'
            w, _h = blf.dimensions(font, text)
            blf.position(font, x - w / 2, y - 4 * ui, 0)
            blf.draw(font, text)
    except Exception:          # never break viewport drawing
        pass


CLASSES = (MCH_OT_line_corner_toggle, MCH_GT_line_slider, MCH_GGT_line_hud)
_label_handle = None


def register():
    global _label_handle
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
