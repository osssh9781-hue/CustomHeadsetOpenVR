"""0.24.95 The colour picker of the drawn side panel's swatches (user: "컬러 피커에 휴 · 새츄레이션 · 밸류 다 넣어 주고
스포이드도 넣어 줘"):

* Hue / Saturation / Value bars under the colour wheel - they read and write the swatch's colour (the colour as it is
  shown: a linear colour is turned to display values first, so Value moves the way the eye expects)
* Pick (the eyedropper): click anywhere in the Blender window - a 3D view, an image, a reference picture - and the
  swatch takes the colour seen there (the area under the mouse is captured once and read; Esc / right click cancels).
  It is the colour on the screen, lit and shaded, as any eyedropper sees it.
"""
from __future__ import annotations

import colorsys
import os
import tempfile

import bpy
from bpy.props import FloatProperty

_HUE = [0.0]                    # (the last hue: kept while Saturation or Value is 0 - grey has no hue of its own)


def target():
    """(data, prop) of the swatch the picker edits, or (None, '')."""
    from .ui_bars import EDIT
    data, prop = EDIT
    try:
        rna = data.bl_rna.properties.get(prop) if data is not None else None
    except (AttributeError, ReferenceError):
        return None, ''
    if rna is None or rna.subtype not in {'COLOR', 'COLOR_GAMMA'}:
        return None, ''
    return data, prop


def _to_display(c, linear):
    if not linear:
        return c
    return tuple(12.92 * v if v <= 0.0031308 else 1.055 * max(v, 0.0) ** (1 / 2.4) - 0.055 for v in c)


def _to_linear(c, linear):
    if not linear:
        return c
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c)


def _is_linear(data, prop):
    return data.bl_rna.properties[prop].subtype == 'COLOR'


def get_hsv():
    data, prop = target()
    if data is None:
        return 0.0, 0.0, 0.0
    col = tuple(getattr(data, prop))[:3]
    h, s, v = colorsys.rgb_to_hsv(*[min(max(x, 0.0), 1.0) for x in _to_display(col, _is_linear(data, prop))])
    if s > 1e-4 and v > 1e-4:
        _HUE[0] = h
    else:
        h = _HUE[0]
    return h, s, v


def set_hsv(h=None, s=None, v=None):
    data, prop = target()
    if data is None:
        return
    h0, s0, v0 = get_hsv()
    h = h0 if h is None else h
    s = s0 if s is None else s
    v = v0 if v is None else v
    _HUE[0] = h
    rgb = _to_linear(colorsys.hsv_to_rgb(h, s, v), _is_linear(data, prop))
    cur = list(getattr(data, prop))
    cur[:3] = rgb
    setattr(data, prop, cur)


def set_display_colour(data, prop, rgb):
    """The swatch set from a colour seen on the screen (display values 0 .. 1)."""
    col = _to_linear(tuple(min(max(x, 0.0), 1.0) for x in rgb[:3]), _is_linear(data, prop))
    cur = list(getattr(data, prop))
    cur[:3] = col
    setattr(data, prop, cur)


def _hsv_prop(i, name, desc):
    return FloatProperty(name=name, min=0.0, max=1.0, subtype='FACTOR', description=desc, options={'SKIP_SAVE'},
                         get=lambda self: get_hsv()[i],
                         set=lambda self, val: set_hsv(**{'hsv'[i]: val}))


def draw(layout, data, prop):
    """The picker: the wheel, Hue / Saturation / Value, the colour field, Pick."""
    wm = bpy.context.window_manager
    layout.template_color_picker(data, prop, value_slider=True)
    col = layout.column(align=True)
    col.prop(wm, 'mch_pick_h', text='Hue', slider=True)
    col.prop(wm, 'mch_pick_s', text='Saturation', slider=True)
    col.prop(wm, 'mch_pick_v', text='Value', slider=True)
    row = layout.row(align=True)
    row.prop(data, prop, text='')
    row.operator('mch.color_eyedrop', text='Pick', icon='EYEDROPPER')


def sample(path, x, y, r=1):
    """The mean colour (display values) of the picture ``path`` round pixel (x, y) - y up, as Blender's pictures."""
    import numpy as np
    img = bpy.data.images.load(path, check_existing=False)
    try:
        w, h = img.size
        a = np.empty(w * h * 4, np.float32)
        img.pixels.foreach_get(a)
        a = a.reshape(h, w, 4)
        x, y = int(min(max(x, 0), w - 1)), int(min(max(y, 0), h - 1))
        patch = a[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1, :3]
        return tuple(float(v) for v in patch.reshape(-1, 3).mean(0))
    finally:
        bpy.data.images.remove(img)


def _area_at(screen, mx, my):
    for area in screen.areas:
        if area.x <= mx < area.x + area.width and area.y <= my < area.y + area.height:
            return area
    return None


class MCH_OT_color_eyedrop(bpy.types.Operator):
    """Pick a colour from the screen: click anywhere (a 3D view, an image ...) - the swatch takes the colour seen there.
    Esc / right click: cancel"""
    bl_idname = 'mch.color_eyedrop'
    bl_label = 'Pick a Colour'
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        self.data, self.prop = target()
        if self.data is None or context.window is None or bpy.app.background:      # (no screen to pick from)
            self.report({'WARNING'}, 'Pick: open a colour swatch first')
            return {'CANCELLED'}
        context.window.cursor_modal_set('EYEDROPPER')
        context.window_manager.modal_handler_add(self)
        try:
            context.workspace.status_text_set('Pick a colour: click anywhere   Esc / right click: cancel')
        except (AttributeError, TypeError):
            pass
        return {'RUNNING_MODAL'}

    def _end(self, context):
        context.window.cursor_modal_restore()
        try:
            context.workspace.status_text_set(None)
        except (AttributeError, TypeError):
            pass

    def modal(self, context, event):
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            self._end(context)
            return {'CANCELLED'}
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self._end(context)
            win = context.window
            area = _area_at(win.screen, event.mouse_x, event.mouse_y)
            if area is None:
                return {'CANCELLED'}
            path = os.path.join(tempfile.mkdtemp(prefix='mch_pick_'), 'area.png')
            region = next((r for r in area.regions if r.type == 'WINDOW'), None)
            try:
                with context.temp_override(window=win, area=area, region=region):
                    bpy.ops.screen.screenshot_area(filepath=path, check_existing=False)
                rgb = sample(path, event.mouse_x - area.x, event.mouse_y - area.y)
            except (RuntimeError, OSError, TypeError) as ex:
                self.report({'WARNING'}, f'Pick: {ex}')
                return {'CANCELLED'}
            finally:
                try:
                    os.remove(path)
                    os.rmdir(os.path.dirname(path))
                except OSError:
                    pass
            try:
                set_display_colour(self.data, self.prop, rgb)
            except (ReferenceError, AttributeError, TypeError) as ex:
                self.report({'WARNING'}, f'Pick: {ex}')
                return {'CANCELLED'}
            for a in win.screen.areas:
                a.tag_redraw()
            self.report({'INFO'}, 'Picked ' + ' '.join(f'{v:.2f}' for v in rgb))
            return {'FINISHED'}
        return {'RUNNING_MODAL'}


CLASSES = (MCH_OT_color_eyedrop,)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    wm = bpy.types.WindowManager
    wm.mch_pick_h = _hsv_prop(0, 'Hue', 'The swatch colour\'s hue')
    wm.mch_pick_s = _hsv_prop(1, 'Saturation', 'The swatch colour\'s saturation (0 grey)')
    wm.mch_pick_v = _hsv_prop(2, 'Value', 'The swatch colour\'s brightness')


def unregister():
    for name in ('mch_pick_h', 'mch_pick_s', 'mch_pick_v'):
        if hasattr(bpy.types.WindowManager, name):
            delattr(bpy.types.WindowManager, name)
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
