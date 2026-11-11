"""0.24.137 Background Colour (user: "HDRI 는 다른 애드온 쓸 거라 배경만 내가 원하는 색으로 바꿀 수 있게 해 주라, 너가
만든 게 너무 무거워").

The camera sees one colour; the scene's world - an HDRI from any add-on, or anything else - still lights the parts and
shows in their reflections.  Three small nodes go into the scene's world: Light Path (Is Camera Ray) mixes the world's
own shader with a Background of the colour.  Renders, Quick Render and the Rendered viewport all use the world, so they
all show it.  Solid view too (an option): the 3D views' own background set to the same colour (their old setting kept
and put back).

Off: the three nodes removed and the world's own shader linked to its output again - nothing else in the world is
touched.  Another add-on rebuilding its world drops the nodes: Background Colour then reads Off (press it again).
"""
from __future__ import annotations

import json

import bpy
from bpy.props import BoolProperty, FloatVectorProperty

N_PATH, N_BG, N_MIX = 'MCH BG Path', 'MCH BG Colour', 'MCH BG Mix'
VIEW_KEY = 'mch_bg_view'


def _upd_color(self, context):
    set_color(context.scene)


def _upd_solid(self, context):
    update_views(context.scene)


class MCH_PG_Background(bpy.types.PropertyGroup):
    color: FloatVectorProperty(name='Background', subtype='COLOR', size=3, min=0.0, max=1.0,
                               default=(0.18, 0.18, 0.18), update=_upd_color,
                               description='The colour the camera sees behind the parts (the world still lights them)')
    solid_too: BoolProperty(name='Solid View Too', default=False, update=_upd_solid,
                            description='The 3D views\' own background (Solid / Material Preview) in the same colour')


def settings(scene):
    return getattr(scene, 'mch_bg', None)


def _output(nt):
    outs = [n for n in nt.nodes if n.bl_idname == 'ShaderNodeOutputWorld']
    return next((n for n in outs if getattr(n, 'is_active_output', False)), outs[0] if outs else None)


def on(scene):
    """Is the colour in the scene's world (our Mix linked to the world's output)?"""
    w = getattr(scene, 'world', None)
    nt = getattr(w, 'node_tree', None)
    if nt is None:
        return False
    mix, out = nt.nodes.get(N_MIX), _output(nt)
    if mix is None or out is None:
        return False
    return any(l.from_node == mix for l in out.inputs['Surface'].links)


def _world(scene):
    w = scene.world
    if w is None:
        w = bpy.data.worlds.new('World')
        scene.world = w
    try:
        if not w.use_nodes:
            w.use_nodes = True
    except AttributeError:
        pass
    return w


def apply(scene):
    """The colour into the scene's world (an existing world kept as it is - its shader goes through our Mix)."""
    if on(scene):
        set_color(scene)
        return 'Background Colour is on'
    w = _world(scene)
    nt = w.node_tree
    out = _output(nt)
    if out is None:
        out = nt.nodes.new('ShaderNodeOutputWorld')
        out.location = (300, 0)
    surf = out.inputs['Surface']
    src = surf.links[0].from_socket if surf.links else None
    for name in (N_PATH, N_BG, N_MIX):                 # (leftovers of an earlier time: rebuilt)
        n = nt.nodes.get(name)
        if n is not None:
            nt.nodes.remove(n)
    path = nt.nodes.new('ShaderNodeLightPath')
    path.name = path.label = N_PATH
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.name = bg.label = N_BG
    mix = nt.nodes.new('ShaderNodeMixShader')
    mix.name = mix.label = N_MIX
    x, y = out.location
    path.location, bg.location, mix.location = (x - 420, y + 260), (x - 420, y - 160), (x - 180, y)
    lk = nt.links
    lk.new(path.outputs['Is Camera Ray'], mix.inputs['Fac'])
    if src is not None:
        lk.new(src, mix.inputs[1])
    lk.new(bg.outputs['Background'], mix.inputs[2])
    lk.new(mix.outputs['Shader'], surf)
    set_color(scene)
    update_views(scene)
    return 'Background Colour on: the camera sees the colour, the world still lights the parts'


def remove(scene):
    """The three nodes out, the world's own shader back on its output."""
    w = getattr(scene, 'world', None)
    nt = getattr(w, 'node_tree', None)
    if nt is not None:
        mix, out = nt.nodes.get(N_MIX), _output(nt)
        src = mix.inputs[1].links[0].from_socket if mix is not None and mix.inputs[1].links else None
        linked = out is not None and any(l.from_node == mix for l in out.inputs['Surface'].links)
        for name in (N_PATH, N_BG, N_MIX):
            n = nt.nodes.get(name)
            if n is not None:
                nt.nodes.remove(n)
        if src is not None and out is not None and linked and not out.inputs['Surface'].links:
            nt.links.new(src, out.inputs['Surface'])
    update_views(scene, force_off=True)
    return 'Background Colour off: the world as it was'


def set_color(scene):
    st = settings(scene)
    w = getattr(scene, 'world', None)
    nt = getattr(w, 'node_tree', None)
    if st is None or nt is None:
        return
    bg = nt.nodes.get(N_BG)
    if bg is not None:
        bg.inputs['Color'].default_value = (*st.color, 1.0)
        bg.inputs['Strength'].default_value = 1.0
    update_views(scene)


# ---- Solid view too: the 3D views' own background -----------------------------------------------------------------

def _views():
    out = []
    for win in getattr(bpy.context.window_manager, 'windows', ()):
        for i, area in enumerate(win.screen.areas):
            if area.type == 'VIEW_3D':
                sp = area.spaces.active
                if sp is not None and sp.type == 'VIEW_3D':
                    out.append((win.screen, str(i), sp))
    return out


def update_views(scene, force_off=False):
    """Solid view too on (and the colour on): the views' background = the colour (their own kept on the screen);
    else their own background back."""
    st = settings(scene)
    want = bool(st is not None and st.solid_too and on(scene) and not force_off)
    for scr, idx, sp in _views():
        sh = sp.shading
        try:
            keep = json.loads(scr[VIEW_KEY]) if VIEW_KEY in scr.keys() else {}
        except (TypeError, ValueError):
            keep = {}
        if want:
            if idx not in keep:
                keep[idx] = [sh.background_type, list(sh.background_color)]
            sh.background_type = 'VIEWPORT'
            sh.background_color = st.color
            scr[VIEW_KEY] = json.dumps(keep)
        elif idx in keep:
            typ, col = keep.pop(idx)
            try:
                sh.background_type = typ
                sh.background_color = col
            except (TypeError, ValueError):
                pass
            if keep:
                scr[VIEW_KEY] = json.dumps(keep)
            elif VIEW_KEY in scr.keys():
                del scr[VIEW_KEY]


class MCH_OT_bg_color(bpy.types.Operator):
    """Background Colour: the camera sees your colour, the world (your HDRI add-on) still lights the parts.  Again:
    off, the world as it was"""
    bl_idname = 'mch.bg_color'
    bl_label = 'Background Colour'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        msg = remove(context.scene) if on(context.scene) else apply(context.scene)
        self.report({'INFO'}, msg)
        try:
            from . import side_panel
            side_panel.dirty()
        except (ImportError, AttributeError):
            pass
        return {'FINISHED'}


CLASSES = (MCH_PG_Background, MCH_OT_bg_color)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_bg = bpy.props.PointerProperty(type=MCH_PG_Background)


def unregister():
    if hasattr(bpy.types.Scene, 'mch_bg'):
        del bpy.types.Scene.mch_bg
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
