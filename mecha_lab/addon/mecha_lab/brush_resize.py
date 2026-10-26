"""0.24.34 F + mouse left / right = brush size in every drawing tool (like Concept Move).

What "brush size" is depends on the tool:

* Line Width (the band of Line mode, Surface Draw, Belt, Surface Curve ...) - Surface Draw also scales the kept
  Width / Height of the next stroke.
* PNG stamp shape: Stamp Radius.  Mask Brush stroke: Mask Brush Radius.  Screw Stamp: Size.

Click / Enter / F again = keep, right click / Esc = back.  ``targets`` and ``scale`` are plain (tested headless).
"""
from __future__ import annotations

import math

import bpy
from bpy_extras import view3d_utils

from . import tool_state as ts

_DRAW = [None]


def targets(context):
    """[(owner, property, 'WORLD' | 'PX', is diameter)] the F drag scales, and a label."""
    scene = context.scene
    brush = scene.mch_brush
    tool = ts.effective_tool(context)
    if tool == 'SCREW':
        return [(scene.mch_screw, 'radius', 'WORLD', False)], 'Screw Size'
    if brush.shape == 'CUSTOM':
        return [(brush, 'custom_size', 'PX', False)], 'Stamp Radius'
    if tool == 'MASK' and brush.shape == 'STROKE':
        return [(brush, 'mask_brush_radius', 'PX', False)], 'Mask Brush Radius'
    out = [(brush, 'line_width', 'WORLD', True)]
    if tool == 'SDRAW':
        st = scene.mch_sdraw
        if st.width > 0:                        # Keep First Size stored it: the next stroke follows the F size
            out.append((st, 'width', 'WORLD', True))
        if st.height > 0:
            out.append((st, 'height', 'WORLD', False))
    return out, 'Line Width'


def values(items):
    return [getattr(o, p) for o, p, _k, _d in items]


def scale(items, start, factor):
    """Every size times ``factor`` (from the values at the start), kept inside each property's limits."""
    for (o, p, _k, _d), v in zip(items, start):
        rna = o.bl_rna.properties[p]
        hi = rna.hard_max if rna.hard_max < 1e30 else v * 1000.0
        setattr(o, p, max(rna.hard_min, min(hi, v * factor)))


def _px_per_world(context, at):
    from . import concept_move
    return concept_move._px_per_world(context, at)


def radius_px(context, items, at):
    o, p, kind, diam = items[0]
    v = getattr(o, p)
    if kind == 'WORLD':
        v *= _px_per_world(context, at)
    return v * 0.5 if diam else v


def _draw(op, context):
    import gpu
    from gpu_extras.batch import batch_for_shader
    try:
        cx, cy = op.center_2d
        r = max(1.0, op.r_px)
        pts = [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in (2 * math.pi * i / 64 for i in range(65))]
        sh = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        gpu.state.line_width_set(2.0)
        batch = batch_for_shader(sh, 'LINE_STRIP', {'pos': pts})
        sh.bind()
        sh.uniform_float('color', (1.0, 0.75, 0.25, 0.95))
        batch.draw(sh)
        gpu.state.line_width_set(1.0)
        gpu.state.blend_set('NONE')
    except (AttributeError, ReferenceError, ValueError):
        pass


class MCH_OT_brush_resize(bpy.types.Operator):
    """F + move the mouse left / right: brush size (click or F again = keep, right click / Esc = back)"""
    bl_idname = 'mch.brush_resize'
    bl_label = 'Brush Size (F)'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return (context.area is not None and context.area.type == 'VIEW_3D'
                and getattr(context.scene, 'mch_brush', None) is not None)

    def invoke(self, context, event):
        self.items, self.label = targets(context)
        self.start = values(self.items)
        region, rv3d = context.region, context.region_data
        mouse = (event.mouse_region_x, event.mouse_region_y)
        origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, mouse)
        ray = view3d_utils.region_2d_to_vector_3d(region, rv3d, mouse).normalized()
        try:
            hit, loc, _n, _i, _o, _m = context.scene.ray_cast(context.evaluated_depsgraph_get(), origin, ray)
        except (RuntimeError, AttributeError):
            hit = False
        self.at = loc if hit else view3d_utils.region_2d_to_location_3d(region, rv3d, mouse,
                                                                         context.scene.cursor.location)
        self.x0 = event.mouse_region_x
        self.center_2d = mouse
        self.r_px = radius_px(context, self.items, self.at)
        _DRAW[0] = bpy.types.SpaceView3D.draw_handler_add(_draw, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        self._header(context)
        return {'RUNNING_MODAL'}

    def _header(self, context):
        o, p, kind, _d = self.items[0]
        v = getattr(o, p)
        txt = f'{v * 100:.2f} cm' if kind == 'WORLD' else f'{v:.0f} px'
        context.area.header_text_set(f'{self.label}  {txt}   (F / click: keep, Esc / right click: back)')
        context.area.tag_redraw()

    def _end(self, context):
        if _DRAW[0] is not None:
            bpy.types.SpaceView3D.draw_handler_remove(_DRAW[0], 'WINDOW')
            _DRAW[0] = None
        context.area.header_text_set(None)
        context.area.tag_redraw()

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            scale(self.items, self.start, math.exp((event.mouse_region_x - self.x0) * 0.006))
            self.r_px = radius_px(context, self.items, self.at)
            self._header(context)
        elif (event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS') or \
                (event.type == 'F' and event.value == 'PRESS'):
            self._end(context)
            return {'FINISHED'}
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            for (o, p, _k, _d), v in zip(self.items, self.start):
                setattr(o, p, v)
            self._end(context)
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}


CLASSES = (MCH_OT_brush_resize,)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    if _DRAW[0] is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_DRAW[0], 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _DRAW[0] = None
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
