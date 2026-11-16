"""0.24.180 (user: "내가 눈을 끈 메쉬들을 렌더를 안 하게, 눈 끈 거만 한 번에 카메라 꺼지게 가능? 다시 켜는 것도"): two
buttons in the Layers window -

* **Hidden: No Render** - every part whose eye is off (its own, or its folder's) is left out of renders too (its camera
  off: ``hide_render``), all at once; each one so turned off is marked;
* **Render Again** - only the parts this turned off back in renders (a part you turned off yourself stays off).
"""
from __future__ import annotations

import bpy

MARK = 'mch_render_off'
KINDS = {'MESH', 'CURVE', 'CURVES', 'SURFACE', 'META', 'FONT', 'POINTCLOUD', 'VOLUME'}


def eye_off(ob):
    try:
        return ob.hide_get() or not ob.visible_get()
    except RuntimeError:                              # (not in this view layer)
        return False


def hidden_parts(context):
    return [o for o in context.view_layer.objects if o.type in KINDS and eye_off(o)]


def turned_off(scene=None):
    return [o for o in bpy.data.objects if o.get(MARK)]


def no_render(context):
    """The eye-off parts out of renders.  Returns how many were turned off now."""
    n = 0
    for o in hidden_parts(context):
        if o.hide_render:
            continue                                  # (off already - yours: not marked, left as it is)
        o.hide_render = True
        o[MARK] = 1
        n += 1
    return n


def render_again():
    n = 0
    for o in turned_off():
        o.hide_render = False
        del o[MARK]
        n += 1
    return n


class MCH_OT_hidden_no_render(bpy.types.Operator):
    """Every part with its eye off (its own or its folder's) left out of renders too - its camera off - all at once"""
    bl_idname = 'mch.hidden_no_render'
    bl_label = 'Hidden: No Render'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        n = no_render(context)
        self.report({'INFO'}, f'{n} hidden part{"s" if n != 1 else ""} left out of renders' if n else
                    'No hidden part to leave out of renders')
        return {'FINISHED'}


class MCH_OT_render_again(bpy.types.Operator):
    """The parts "Hidden: No Render" turned off back in renders (one you turned off yourself stays off)"""
    bl_idname = 'mch.render_again'
    bl_label = 'Render Again'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        n = render_again()
        self.report({'INFO'}, f'{n} part{"s" if n != 1 else ""} back in renders')
        return {'FINISHED'}


def toolbar_cells(context):
    """The Layers window's row: (label, action, enabled)."""
    hid = len([o for o in hidden_parts(context) if not o.hide_render])
    back = len(turned_off())
    return [(f'No Render ({hid})', ('op', 'mch.hidden_no_render', {}), hid > 0),        # (the eye-off ones)
            (f'Render Again ({back})', ('op', 'mch.render_again', {}), back > 0)]


CLASSES = (MCH_OT_hidden_no_render, MCH_OT_render_again)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
