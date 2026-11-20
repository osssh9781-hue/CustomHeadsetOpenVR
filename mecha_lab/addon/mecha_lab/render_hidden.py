"""0.24.180 (user: "내가 눈을 끈 메쉬들을 렌더를 안 하게, 눈 끈 거만 한 번에 카메라 꺼지게 가능? 다시 켜는 것도"): two
buttons in the Layers window -

* **Hidden: No Render** - every part whose eye is off (its own, or its folder's) is left out of renders too (its camera
  off: ``hide_render``), all at once; each one so turned off is marked;
* **Render Again** - only the parts this turned off back in renders (a part you turned off yourself stays off).

0.24.270 (user: "눈 꺼 놓은 거는 렌더할 때 끌 수 있게 해 달라고 했는데 왜 계속 켜져 있어" - a hair with its eye off but its
camera on rendered in F12): **Auto** (on by default) - an eye turned off (the object's own eye, or its folder's eye in
the outliner / Layers window) turns its camera off at once, marked; the eye on again turns the camera back on (only the
ones Auto turned off).  So F12, the Rendered view and Quick Render all leave out what you hid.  Only the change is
acted on: a camera you turn on again yourself while the eye stays off is left on.  Folders switched off with Blender's
"Disable in Viewports" (the monitor) are not eyes and are left alone (Light Copies uses them).
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


# --- 0.24.270 Auto ---------------------------------------------------------------------------------------------

_LAST = {}                                            # view layer key -> the names whose eye was off last time
_BUSY = [False]


def _eyes_off(view_layer):
    """Names of the parts whose eye is off: their own, or a folder's eye (a layer collection's hide_viewport)."""
    by_folder = set()

    def walk(lc, hidden):
        hidden = hidden or lc.hide_viewport
        if hidden and not lc.exclude:
            by_folder.update(o.name for o in lc.collection.objects)
        for ch in lc.children:
            walk(ch, hidden)
    walk(view_layer.layer_collection, False)
    out = set()
    for o in view_layer.objects:
        if o.type not in KINDS:
            continue
        try:
            if o.name in by_folder or o.hide_get(view_layer=view_layer):
                out.add(o.name)
        except (RuntimeError, TypeError):
            pass
    return out


def auto_on(scene):
    return bool(getattr(scene, 'mch_hidden_auto', True))


def sync(scene, view_layer, first=False):
    """Eyes turned off since last time: their cameras off (marked); eyes back on: the marked cameras on."""
    key = (scene.name, view_layer.name)
    now = _eyes_off(view_layer)
    before = set() if first else _LAST.get(key)
    _LAST[key] = now
    if before is None:                                # (the first look after loading: what is hidden now)
        before = set()
    went_off, came_on = now - before, before - now
    obs = bpy.data.objects
    _BUSY[0] = True
    try:
        for n in went_off:
            o = obs.get(n)
            if o is not None and not o.hide_render:
                o.hide_render = True
                o[MARK] = 1
        for n in came_on:
            o = obs.get(n)
            if o is not None and o.get(MARK):
                o.hide_render = False
                del o[MARK]
    finally:
        _BUSY[0] = False
    return len(went_off), len(came_on)


def _on_update(scene, depsgraph=None):
    if _BUSY[0] or not auto_on(scene):
        return
    try:
        ctx = bpy.context
        if getattr(ctx, 'mode', 'OBJECT') not in {'OBJECT'}:
            return                                    # (sculpting / editing: eyes are not touched there)
        vl = depsgraph.view_layer if depsgraph is not None else ctx.view_layer
        sync(scene, vl)
    except (ReferenceError, AttributeError, RuntimeError):
        pass


def _on_load(*_a):
    _LAST.clear()


def _auto_upd(self, context):
    sc = self if isinstance(self, bpy.types.Scene) else context.scene
    if sc.mch_hidden_auto:
        _LAST.pop((sc.name, context.view_layer.name), None)
        sync(sc, context.view_layer, first=True)
    else:
        render_again()


class MCH_OT_hidden_auto(bpy.types.Operator):
    """Auto: turning an eye off turns its camera off too (F12, Rendered view and Quick Render leave it out); the eye
    on again turns it back on"""
    bl_idname = 'mch.hidden_auto'
    bl_label = 'Hidden = No Render (Auto)'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.mch_hidden_auto = not context.scene.mch_hidden_auto
        return {'FINISHED'}


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
    auto = auto_on(context.scene)
    return [(('Auto: Hidden = No Render' if auto else 'Auto: Off'), ('op', 'mch.hidden_auto', {}), True),
            (f'No Render ({hid})', ('op', 'mch.hidden_no_render', {}), hid > 0),        # (the eye-off ones)
            (f'Render Again ({back})', ('op', 'mch.render_again', {}), back > 0)]


CLASSES = (MCH_OT_hidden_auto, MCH_OT_hidden_no_render, MCH_OT_render_again)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_hidden_auto = bpy.props.BoolProperty(
        name='Hidden = No Render (Auto)', default=True, update=_auto_upd,
        description='Turning an eye off turns its camera off too (F12, Rendered view and Quick Render leave it out); '
                    'the eye on again turns it back on')
    if _on_update not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_update)
    if _on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load)


def unregister():
    if _on_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_update)
    if _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
    if hasattr(bpy.types.Scene, 'mch_hidden_auto'):
        del bpy.types.Scene.mch_hidden_auto
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
