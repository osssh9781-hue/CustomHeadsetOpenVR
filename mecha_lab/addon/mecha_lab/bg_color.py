"""0.24.137 Background Colour (user: "HDRI 는 다른 애드온 쓸 거라 배경만 내가 원하는 색으로 바꿀 수 있게 해 주라, 너가
만든 게 너무 무거워").

The camera sees one colour; the scene's world - an HDRI from any add-on, or anything else - still lights the parts and
shows in their reflections.  Three small nodes go into the scene's world: Light Path (Is Camera Ray) mixes the world's
own shader with a Background of the colour.  Renders, Quick Render and the Rendered viewport all use the world, so they
all show it.  Solid view too (an option): the 3D views' own background set to the same colour (their old setting kept
and put back).

Off: the three nodes removed and the world's own shader linked to its output again - nothing else in the world is
touched.  Another add-on rebuilding its world drops the nodes: Background Colour then reads Off (press it again).

0.24.138 (user: "백그라운드 이미지가 안 보여", "뒤에 넣는 스튜디오 이미지들 다 어디 갔어?") Picture: a studio backdrop
(the add-on's 68) or one of the user's pictures behind the model instead of the colour - the frame's window
coordinates, Fill / Fit (the colour round a fitted picture), Brightness / Contrast; on any world, like the colour.
Material Preview Too: Material Preview shows the scene's world (Blender's own studio light otherwise hides it).
"""
from __future__ import annotations

import json
import os

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, StringProperty

N_PATH, N_BG, N_MIX = 'MCH BG Path', 'MCH BG Colour', 'MCH BG Mix'
N_COORD, N_MAP, N_PIC, N_BC, N_ALPHA = 'MCH BG Coord', 'MCH BG Map', 'MCH BG Picture', 'MCH BG Bright', 'MCH BG Alpha'
N_BW, N_RAMP, N_RMIX = 'MCH BG Ramp Value', 'MCH BG Ramp', 'MCH BG Ramp Mix'      # 0.24.140 the Colour Ramp back
PIC_NODES = (N_COORD, N_MAP, N_PIC, N_BC, N_ALPHA, N_BW, N_RAMP, N_RMIX)
NODES = (N_PATH, N_BG, N_MIX) + PIC_NODES
STOPS = 'mch_bg_ramp_stops'        # on the settings: the ramp's colours, kept while the picture nodes are out
DARK, LIGHT = (0.02, 0.022, 0.028, 1.0), (0.92, 0.92, 0.92, 1.0)
VIEW_KEY = 'mch_bg_view'
MAT_KEY = 'mch_bg_matview'
OWN = 'mch_bg_own'                 # on a picture this loaded (let go when another is picked and nothing uses it)
DEFAULT_PICTURE = 'B:white_sweep_land.jpg'


def _upd_color(self, context):
    set_color(context.scene)


def _upd_solid(self, context):
    update_views(context.scene)


def _upd_mat(self, context):
    update_material_views(context.scene)


class MCH_PG_Background(bpy.types.PropertyGroup):
    color: FloatVectorProperty(name='Background', subtype='COLOR', size=3, min=0.0, max=1.0,
                               default=(0.18, 0.18, 0.18), update=_upd_color,
                               description='The colour the camera sees behind the parts (the world still lights them)')
    solid_too: BoolProperty(name='Solid View Too', default=False, update=_upd_solid,
                            description='The 3D views\' own background (Solid / Material Preview) in the same colour')
    # 0.24.138 a picture behind the model (the studio backdrops come back)
    mode: EnumProperty(name='Behind the Model', items=[('COLOR', 'Colour', 'One colour'),
                                                       ('IMAGE', 'Picture', 'A studio backdrop or one of your pictures')],
                       default='COLOR', update=_upd_color)
    image: StringProperty(name='Picture', default='', update=_upd_color,
                          description='The picture behind the model (a studio backdrop or one of yours)')
    fit: EnumProperty(name='Fit', items=[('FILL', 'Fill', 'The frame covered (the picture\'s edges cut off)'),
                                         ('FIT', 'Fit', 'The whole picture (the colour round it)')],
                      default='FILL', update=_upd_color)
    bright: FloatProperty(name='Brightness', default=0.0, soft_min=-1.0, soft_max=1.0, update=_upd_color,
                          description='The picture lighter / darker')
    contrast: FloatProperty(name='Contrast', default=0.0, soft_min=-1.0, soft_max=1.0, update=_upd_color,
                            description='The picture\'s contrast (-1 flat, 0 as it is, 1 twice as much)')
    ramp: BoolProperty(name='Colour Ramp', default=False, update=_upd_color,
                       description='The picture\'s dark and light parts take the ramp\'s colours (Dark / Light, Edit '
                       'Ramp… for more stops)')
    material_too: BoolProperty(name='Material Preview Too', default=True, update=_upd_mat,
                               description='Material Preview shows the scene\'s world (your HDRI and the background) '
                               'instead of Blender\'s own studio light')


def settings(scene):
    return getattr(scene, 'mch_bg', None)


def picture_ident(scene):
    """The picture in use: the setting, else the one the old HDRI page had (0.24.95 - 0.24.136), else the white
    studio sweep."""
    st = settings(scene)
    if st is not None and st.image:
        return st.image
    old = getattr(scene, 'mch_mech_hdri_bg_image', '')
    return old or DEFAULT_PICTURE


def picture_path(scene):
    from . import backdrops
    p = backdrops.path(picture_ident(scene))
    return p if p and os.path.isfile(p) else ''


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
    migrate(scene)
    w = _world(scene)
    nt = w.node_tree
    out = _output(nt)
    if out is None:
        out = nt.nodes.new('ShaderNodeOutputWorld')
        out.location = (300, 0)
    surf = out.inputs['Surface']
    src = surf.links[0].from_socket if surf.links else None
    for name in NODES:                                 # (leftovers of an earlier time: rebuilt)
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
    update_material_views(scene)
    st = settings(scene)
    if st is not None and st.mode == 'IMAGE':
        return 'Background Picture on: the camera sees the picture, the world still lights the parts'
    return 'Background Colour on: the camera sees the colour, the world still lights the parts'


def remove(scene):
    """The three nodes out, the world's own shader back on its output."""
    w = getattr(scene, 'world', None)
    nt = getattr(w, 'node_tree', None)
    if nt is not None:
        mix, out = nt.nodes.get(N_MIX), _output(nt)
        src = mix.inputs[1].links[0].from_socket if mix is not None and mix.inputs[1].links else None
        linked = out is not None and any(l.from_node == mix for l in out.inputs['Surface'].links)
        pic = nt.nodes.get(N_PIC)
        img = pic.image if pic is not None else None
        _save_stops(scene, nt)
        for name in NODES:
            n = nt.nodes.get(name)
            if n is not None:
                nt.nodes.remove(n)
        _let_go(img)
        if src is not None and out is not None and linked and not out.inputs['Surface'].links:
            nt.links.new(src, out.inputs['Surface'])
    update_views(scene, force_off=True)
    update_material_views(scene, force_off=True)
    return 'Background off: the world as it was'


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
        _picture_sync(scene, nt, bg)
    update_views(scene)


# ---- the picture behind the model ---------------------------------------------------------------------------------

def _let_go(img):
    try:
        if img is not None and img.get(OWN) and img.users == 0:
            bpy.data.images.remove(img)
    except (ReferenceError, RuntimeError):
        pass


def _mix_in(node, ident):
    return next(s for s in node.inputs if s.identifier == ident)


def _picture_nodes(nt, bg):
    """Window coordinates -> fitted -> the picture -> brightness / contrast -> the colour where it has no pixels."""
    nd, lk = nt.nodes, nt.links
    x, y = bg.location
    coord = nd.new('ShaderNodeTexCoord')
    mp = nd.new('ShaderNodeMapping')
    mp.vector_type = 'POINT'
    pic = nd.new('ShaderNodeTexImage')
    pic.extension = 'CLIP'
    pic.interpolation = 'Linear'
    bc = nd.new('ShaderNodeBrightContrast')
    al = nd.new('ShaderNodeMix')
    al.data_type = 'RGBA'
    for n, name, dx in ((coord, N_COORD, -1100), (mp, N_MAP, -900), (pic, N_PIC, -700), (bc, N_BC, -440),
                        (al, N_ALPHA, -240)):
        n.name = n.label = name
        n.location = (x + dx, y - 360)
    lk.new(coord.outputs['Window'], mp.inputs['Vector'])
    lk.new(mp.outputs['Vector'], pic.inputs['Vector'])
    lk.new(pic.outputs['Color'], bc.inputs['Color'])
    lk.new(pic.outputs['Alpha'], _mix_in(al, 'Factor_Float'))
    # (0.24.95 / 0.24.140 user: "사진에 컬러램프 기능 - 대비랑 색 같은 거 내가 조절", "왜 컬러램프 조정하는 거 뺐어?")
    bw = nd.new('ShaderNodeRGBToBW')
    ramp = nd.new('ShaderNodeValToRGB')
    rmix = nd.new('ShaderNodeMix')
    rmix.data_type = 'RGBA'
    for n, name, dx in ((bw, N_BW, -440), (ramp, N_RAMP, -300), (rmix, N_RMIX, -60)):
        n.name = n.label = name
        n.location = (x + dx, y - 640)
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, DARK
    els[1].position, els[1].color = 1.0, LIGHT
    lk.new(bc.outputs['Color'], bw.inputs['Color'])
    lk.new(bw.outputs['Val'], ramp.inputs['Fac'])
    lk.new(bc.outputs['Color'], _mix_in(rmix, 'A_Color'))
    lk.new(ramp.outputs['Color'], _mix_in(rmix, 'B_Color'))
    lk.new(next(o for o in rmix.outputs if o.identifier == 'Result_Color'), _mix_in(al, 'B_Color'))
    lk.new(next(o for o in al.outputs if o.identifier == 'Result_Color'), bg.inputs['Color'])


def _save_stops(scene, nt):
    """The ramp's colours onto the settings (the picture nodes go out: Colour, off)."""
    st = settings(scene)
    rn = nt.nodes.get(N_RAMP) if nt is not None else None
    if st is None or rn is None:
        return
    st[STOPS] = json.dumps([[e.position, list(e.color)] for e in rn.color_ramp.elements])


def _load_stops(scene, rn):
    """The ramp's colours from the settings, else from the old HDRI page's ramp (0.24.95 - 0.24.136)."""
    st = settings(scene)
    stops = None
    try:
        stops = json.loads(st[STOPS]) if st is not None and STOPS in st.keys() else None
    except (TypeError, ValueError):
        stops = None
    if stops is None:
        try:
            from . import backdrops
            old = backdrops.ramp_node(scene)
            if old is not None:
                stops = [[e.position, list(e.color)] for e in old.color_ramp.elements]
        except (ImportError, AttributeError, ReferenceError):
            stops = None
    if not stops:
        return
    els = rn.color_ramp.elements
    while len(els) > max(2, len(stops)):
        els.remove(els[-1])
    while len(els) < len(stops):
        els.new(1.0)
    for e, (pos, col) in zip(els, stops):
        e.position = pos
        e.color = col


def migrate(scene):
    """0.24.140 once: the old HDRI page's picture settings (Fit, Brightness, Contrast, Colour Ramp) carried over."""
    st = settings(scene)
    if st is None or st.get('mch_migrated'):
        return
    st['mch_migrated'] = 1
    if getattr(scene, 'mch_mech_hdri_bg_mode', 'COLOR') != 'IMAGE':
        return
    st.fit = getattr(scene, 'mch_mech_hdri_bg_fit', 'FILL')
    st.bright = float(getattr(scene, 'mch_mech_hdri_bg_bright', 0.0))
    st.contrast = float(getattr(scene, 'mch_mech_hdri_bg_contrast', 0.0))
    st.ramp = bool(getattr(scene, 'mch_mech_hdri_bg_ramp', False))


def ramp_node(scene):
    """The background picture's Colour Ramp node in the scene's world, or None."""
    w = getattr(scene, 'world', None)
    nt = getattr(w, 'node_tree', None)
    return nt.nodes.get(N_RAMP) if nt is not None else None


def _picture_sync(scene, nt, bg):
    """Picture mode with a picture that exists: the chain in (the picture loaded, fitted to the render frame);
    else the chain out (the colour)."""
    from . import backdrops
    st = settings(scene)
    path = picture_path(scene) if st is not None and st.mode == 'IMAGE' else ''
    pic = nt.nodes.get(N_PIC)
    if not path:
        img = pic.image if pic is not None else None
        _save_stops(scene, nt)
        for name in PIC_NODES:
            n = nt.nodes.get(name)
            if n is not None:
                nt.nodes.remove(n)
        _let_go(img)
        return
    if any(nt.nodes.get(n) is None for n in PIC_NODES):
        for name in PIC_NODES:
            n = nt.nodes.get(name)
            if n is not None:
                nt.nodes.remove(n)
        _picture_nodes(nt, bg)
        _load_stops(scene, nt.nodes.get(N_RAMP))
        pic = nt.nodes.get(N_PIC)
    old = pic.image
    if old is None or os.path.normcase(bpy.path.abspath(old.filepath)) != os.path.normcase(path):
        known = {i.name for i in bpy.data.images}
        img = bpy.data.images.load(path, check_existing=True)
        if img.name not in known:
            img[OWN] = True
        pic.image = img
        _let_go(old)
    img = pic.image
    ia = (img.size[0] / img.size[1]) if img.size[0] and img.size[1] else backdrops.aspect(path)
    sx, sy = backdrops.fit_scale(backdrops.frame_aspect(scene), ia, st.fit)
    # 0.24.141 (user: "뎁스 오브 필드 넣으면 왜 배경 부분이 하얘져?" - a render with a light frame round the picture):
    # depth of field (and the pixel filter) sends some camera rays just past the frame's edge, where a clipped picture
    # has nothing and the Colour showed through.  Fill: the picture's edge carried on outwards; Fit: clipped (the
    # Colour round the whole picture is the point)
    pic.extension = 'EXTEND' if st.fit == 'FILL' else 'CLIP'
    mp = nt.nodes.get(N_MAP)
    mp.inputs['Scale'].default_value = (sx, sy, 1.0)
    mp.inputs['Location'].default_value = (0.5 - 0.5 * sx, 0.5 - 0.5 * sy, 0.0)
    bc = nt.nodes.get(N_BC)
    bc.inputs['Bright'].default_value = float(st.bright)
    bc.inputs['Contrast'].default_value = float(st.contrast)
    _mix_in(nt.nodes.get(N_RMIX), 'Factor_Float').default_value = 1.0 if st.ramp else 0.0
    _mix_in(nt.nodes.get(N_ALPHA), 'A_Color').default_value = (*st.color, 1.0)


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


def update_material_views(scene, force_off=False):
    """Material Preview Too on (and the background on): the 3D views' Material Preview uses the scene's world (their
    own setting kept on the screen and put back)."""
    st = settings(scene)
    want = bool(st is not None and st.material_too and on(scene) and not force_off)
    for scr, idx, sp in _views():
        sh = sp.shading
        try:
            keep = json.loads(scr[MAT_KEY]) if MAT_KEY in scr.keys() else {}
        except (TypeError, ValueError):
            keep = {}
        if want:
            if idx not in keep:
                keep[idx] = bool(sh.use_scene_world)
            sh.use_scene_world = True
            scr[MAT_KEY] = json.dumps(keep)
        elif idx in keep:
            sh.use_scene_world = bool(keep.pop(idx))
            if keep:
                scr[MAT_KEY] = json.dumps(keep)
            elif MAT_KEY in scr.keys():
                del scr[MAT_KEY]


class MCH_OT_bg_picture(bpy.types.Operator):
    """Put this picture behind the model (the Render tab's Background) - the world (your HDRI) still lights it"""
    bl_idname = 'mch.bg_picture'
    bl_label = 'Background Picture'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    ident: StringProperty(default='', options={'SKIP_SAVE'})
    mode: StringProperty(default='', options={'SKIP_SAVE'})

    def execute(self, context):
        sc = context.scene
        st = settings(sc)
        if st is None:
            return {'CANCELLED'}
        if self.mode in {'COLOR', 'IMAGE'} and not self.ident:
            st.mode = self.mode                      # (Colour / Picture: the background on as well)
        else:
            from . import backdrops
            p = backdrops.path(self.ident)
            if not p or not os.path.isfile(p):
                self.report({'WARNING'}, f'Background: no picture "{self.ident}"')
                return {'CANCELLED'}
            st.image = self.ident
            st.mode = 'IMAGE'
        msg = apply(sc) if not on(sc) else (set_color(sc) or 'Background: ' + (
            os.path.basename(picture_path(sc)) if st.mode == 'IMAGE' else 'colour'))
        self.report({'INFO'}, msg)
        try:
            from . import side_panel
            side_panel.dirty()
        except (ImportError, AttributeError):
            pass
        return {'FINISHED'}


class MCH_OT_bg_ramp(bpy.types.Operator):
    """Edit the background picture's Colour Ramp - its colours and where they sit (add stops for more colours): the
    picture's dark parts take the left colour, its light parts the right one"""
    bl_idname = 'mch.bg_ramp'
    bl_label = 'Background Colour Ramp'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def invoke(self, context, event):
        if ramp_node(context.scene) is None:
            self.report({'WARNING'}, 'Colour Ramp: put a background picture on first (Render tab, Background)')
            return {'CANCELLED'}
        if bpy.app.background:
            return self.execute(context)
        return context.window_manager.invoke_popup(self, width=340)

    def draw(self, context):
        lay = self.layout
        lay.label(text='Background picture - Colour Ramp')
        node = ramp_node(context.scene)
        if node is not None:
            lay.template_color_ramp(node, 'color_ramp', expand=True)
        lay.label(text='Left: the picture\'s dark parts   Right: its light parts')

    def execute(self, context):
        return {'FINISHED'}


class MCH_OT_bg_fit(bpy.types.Operator):
    """The picture: Fill (the frame covered, its edges cut) or Fit (the whole picture, the colour round it)"""
    bl_idname = 'mch.bg_fit'
    bl_label = 'Background Fit'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    fit: StringProperty(default='FILL', options={'SKIP_SAVE'})

    def execute(self, context):
        st = settings(context.scene)
        if st is None or self.fit not in {'FILL', 'FIT'}:
            return {'CANCELLED'}
        st.fit = self.fit
        return {'FINISHED'}


class MCH_OT_bg_color(bpy.types.Operator):
    """Background: the camera sees your colour or picture, the world (your HDRI add-on) still lights the parts.
    Again: off, the world as it was"""
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


CLASSES = (MCH_PG_Background, MCH_OT_bg_color, MCH_OT_bg_picture, MCH_OT_bg_fit, MCH_OT_bg_ramp)


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
