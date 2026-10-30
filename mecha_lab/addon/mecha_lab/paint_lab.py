"""0.24.93 Paint Lab: the polypaint screen - a photo as a stencil / brush texture (hue · saturation · contrast ·
brightness · rotation, Q shows / hides the stencil), an eyedropper that reads the POLYPAINT colour (not the
screen), masks from the polypaint's brightness, from the mesh's edges and from cavities, and a viewport look in
which the colours read true.

The workspace / drawn shelf live in paint_ui.py; this module is the data + the actions (headless-testable).

Why the look is what it is (checked against Blender 5.2's colour management):
    - **Paint** (default): Solid shading, Studio light "paint.sl" (Blender's own light rig for painting: a soft
      key, no coloured fill, weak specular), colour = the colour attribute, specular highlights OFF, cavity /
      shadow / outline OFF, and the view transform **Standard** (AgX / Filmic compress and desaturate bright
      colours: a pure red polypaint shows as a dull brick under AgX).  Lit, so the form reads, but the colour of
      a lit face is the painted value.
    - **Exact**: the same with Flat lighting - every pixel IS the painted value (no shading at all).
    - **Material**: Material Preview with Blender's studio HDRI "studio.exr" (neutral grey studio, no colour cast),
      world opacity 0 (a grey backdrop), the active material's base colour from the colour attribute through a
      Principled BSDF with roughness 0.6 / specular 0.3 (little highlight), view transform **Khronos PBR
      Neutral** (the transform made for product / colour fidelity).
"""
from __future__ import annotations

import os

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from mathutils import Vector

from . import mesh_io as mio
from . import paint_lab_core as pc

ACCENT = (0.20, 0.72, 0.86, 1.0)             # the Paint Lab screen: cyan (the ZBrush screen is orange)
ACCENT_FILL = (0.12, 0.48, 0.60, 1.0)
PAINT_BRUSHES = ('Paint', 'PaintSoft', 'PaintSquare', 'PaintBlend', 'Smear', 'Blur')   # the paint brush shelf
STENCIL_IMAGE = 'MCH_PaintStencil'           # the adjusted copy of the photo the brush uses
STENCIL_TEX = 'MCH_PaintStencilTex'          # the image texture on the brush
MASK_ATTR = '.sculpt_mask'
PAINT_MAT = 'MCH_PaintLook'
LOOKS = [('PAINT', 'Paint', 'Solid, paint studio light, colour attribute, Standard view transform: lit, true colour'),
         ('EXACT', 'Exact', 'Flat: every pixel is the painted value'),
         ('MATERIAL', 'Material', 'Material Preview, neutral studio HDRI, Khronos PBR Neutral: the colour under real light')]


# -----------------------------------------------------------------------------
# settings
# -----------------------------------------------------------------------------

def _photo_changed(self, context):
    schedule_rebake(context)


def _stencil_changed(self, context):
    apply_mapping(context)


class MCH_PG_PaintLab(bpy.types.PropertyGroup):
    photo: PointerProperty(name='Photo', type=bpy.types.Image, description='The photo / texture used as the stencil and brush texture',
                           update=_photo_changed)
    hue: FloatProperty(name='Hue', description='Hue shift of the photo (degrees)', default=0.0, min=-180.0, max=180.0, update=_photo_changed)
    saturation: FloatProperty(name='Saturation', default=1.0, min=0.0, max=3.0, update=_photo_changed)
    contrast: FloatProperty(name='Contrast', default=1.0, min=0.0, max=3.0, update=_photo_changed)
    brightness: FloatProperty(name='Brightness', default=0.0, min=-1.0, max=1.0, update=_photo_changed)
    flip_x: BoolProperty(name='Flip X', default=False, update=_photo_changed)
    flip_y: BoolProperty(name='Flip Y', default=False, update=_photo_changed)
    angle: FloatProperty(name='Rotation', description='The stencil / texture turned (degrees)', default=0.0, min=-180.0, max=180.0,
                         subtype='ANGLE', update=_stencil_changed)
    stencil_on: BoolProperty(name='Stencil', description='Q: the photo shown over the view as a stencil you paint through; off = the photo is the brush texture (drag plane)',
                             default=False, update=_stencil_changed)
    mask_black: FloatProperty(name='Black', description='Polypaint brightness at and below this is unmasked', default=0.0, min=0.0, max=1.0)
    mask_white: FloatProperty(name='White', description='Polypaint brightness at and above this is fully masked', default=1.0, min=0.0, max=1.0)
    mask_invert: BoolProperty(name='Invert', default=False)
    edge_angle: FloatProperty(name='Edge Angle', description='A fold this sharp (degrees) is masked', default=30.0, min=1.0, max=120.0)
    edge_soft: FloatProperty(name='Soft', description='The mask fades in over this many degrees below the angle', default=15.0, min=0.0, max=90.0)
    edge_grow: IntProperty(name='Grow', description='The edge band widened by this many rings of points', default=1, min=0, max=10)
    cavity_int: IntProperty(name='Cavity', default=50, min=0, max=100)
    cavity_blur: IntProperty(name='Blur', default=2, min=0, max=10)
    look: EnumProperty(name='Look', items=LOOKS, default='PAINT')


def settings(context=None):
    return getattr((context or bpy.context).scene, 'mch_paint', None)


# -----------------------------------------------------------------------------
# the screen: Sculpt Mode in the MECHA LAB tab with the paint flag on (the ZBrush screen's keys, nav and popups
# stay; the shelves, the brushes, the accent colour and Q / Alt+click change)
# -----------------------------------------------------------------------------

def flag(context=None):
    wm = (context or bpy.context).window_manager
    return bool(getattr(wm, 'mch_paint_on', False))


def set_flag(context, value):
    wm = (context or bpy.context).window_manager
    try:
        wm.mch_paint_on = bool(value)
    except AttributeError:
        pass


def on(context=None):
    """Is the Paint Lab screen up: the ZBrush screen (Sculpt Mode in the MECHA LAB tab, ZBrush style) + the flag."""
    from . import zb_sculpt as zs
    context = context or bpy.context
    return flag(context) and zs.on(context)


def enter(context):
    """Into Paint Lab: the flag, a colour attribute on the mesh, the Paint brush, the Paint look."""
    from . import zb_sculpt as zs
    set_flag(context, True)
    ob = context.active_object
    if ob is not None and ob.type == 'MESH':
        was = ob.mode
        if was != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        ensure_polypaint(ob)
        if was != 'OBJECT':
            bpy.ops.object.mode_set(mode=was)
    if zs.zb_name(zs.brush(context)) not in PAINT_BRUSHES:
        zs.activate(context, 'Paint')
    apply_mapping(context)
    try:
        apply_look(context)
    except Exception as ex:          # noqa: BLE001  (a missing studio light must not stop the switch)
        print('[Mecha Lab] Paint Lab look:', ex)
    return True


def leave(context):
    """Out of Paint Lab (to ZBRUSH or MECHA LAB): the flag off, the stencil mapping off the brush."""
    set_flag(context, False)
    b = active_brush(context)
    if b is not None and b.texture_slot.map_mode == 'STENCIL':
        b.texture_slot.map_mode = 'VIEW_PLANE'
    return True


def draw_paint_shelf(layout, context):
    """The Paint Lab left shelf as an ordinary panel drawer (panel_capture reads it, side_panel draws it)."""
    st = settings(context)
    if st is None:
        layout.label(text='Paint Lab settings missing')
        return
    box = layout.box()
    box.label(text='Photo / Stencil')
    r = box.row()
    r.operator('mch.paint_load_photo', text='Load Photo', icon='IMAGE_DATA')
    r.operator('mch.paint_stencil', text='Stencil (Q)', icon='MOD_MASK', depress=st.stencil_on).action = 'TOGGLE'
    box.label(text=(st.photo.name if st.photo is not None else 'no photo: Load Photo, or pick a Texture (B)'))
    box.prop(st, 'hue', slider=True)
    box.prop(st, 'saturation', slider=True)
    box.prop(st, 'contrast', slider=True)
    box.prop(st, 'brightness', slider=True)
    box.prop(st, 'angle', slider=True)
    r = box.row()
    r.prop(st, 'flip_x', toggle=True)
    r.prop(st, 'flip_y', toggle=True)
    r.operator('mch.paint_stencil', text='Fit', icon='FULLSCREEN_ENTER').action = 'FIT'
    box = layout.box()
    box.label(text='Color')
    box.operator('mch.paint_eyedrop', text='Eyedrop polypaint (Alt + click)', icon='EYEDROPPER')
    r = box.row()
    r.operator('mch.zb_action', text='SwitchColor').action = 'SWITCH_COLOR'
    r.operator('mch.zb_action', text='FillColor').action = 'FILL_COLOR'
    box = layout.box()
    box.label(text='Mask by Brightness')
    r = box.row()
    r.prop(st, 'mask_black', slider=True)
    r.prop(st, 'mask_white', slider=True)
    r = box.row()
    r.operator('mch.paint_mask', text='By Brightness', icon='COLOR').kind = 'VALUE'
    r.prop(st, 'mask_invert', toggle=True)
    box = layout.box()
    box.label(text='Mask by Edges / Cavity')
    r = box.row()
    r.prop(st, 'edge_angle')
    r.prop(st, 'edge_soft')
    r.prop(st, 'edge_grow')
    r = box.row()
    r.operator('mch.paint_mask', text='By Edges', icon='MOD_EDGESPLIT').kind = 'EDGE'
    r.operator('mch.paint_mask', text='By Cavity', icon='MOD_SMOOTH').kind = 'CAVITY'
    r = box.row()
    r.prop(st, 'cavity_int', slider=True)
    r.prop(st, 'cavity_blur')
    r = box.row()
    r.operator('mch.paint_mask', text='Invert').kind = 'INVERT'
    r.operator('mch.paint_mask', text='Clear').kind = 'CLEAR'
    box = layout.box()
    box.label(text='Look')
    r = box.row()
    for kind, label, _d in LOOKS:
        r.operator('mch.paint_look', text=label, depress=(st.look == kind)).kind = kind


# -----------------------------------------------------------------------------
# the photo -> the adjusted stencil image -> the brush texture
# -----------------------------------------------------------------------------

def read_pixels(img):
    """(H, W, 4) float32 of a Blender image."""
    w, h = img.size
    if w == 0 or h == 0:
        return np.zeros((0, 0, 4), np.float32)
    buf = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(buf)
    return buf.reshape(h, w, 4)


def write_pixels(img, rgba):
    h, w = rgba.shape[:2]
    if tuple(img.size) != (w, h):
        img.scale(w, h)
    img.pixels.foreach_set(np.ascontiguousarray(rgba, np.float32).ravel())
    img.update()


def _stencil_dir():
    d = bpy.utils.user_resource('DATAFILES', path=os.path.join('mecha_lab', 'paint_stencil'), create=True)
    os.makedirs(d, exist_ok=True)
    return d


def _stencil_files():
    d = _stencil_dir()
    return os.path.join(d, 'paint_stencil.png'), os.path.join(d, 'paint_stencil.blend')


def _save_png(rgba, path):
    """``rgba`` (H, W, 4) float written as a PNG (through a throw-away local image)."""
    h, w = rgba.shape[:2]
    img = bpy.data.images.new('MCH_PaintStencil_tmp', w, h, alpha=True)
    try:
        img.pixels.foreach_set(np.ascontiguousarray(rgba, np.float32).ravel())
        img.filepath_raw = path
        img.file_format = 'PNG'
        img.save()
    finally:
        bpy.data.images.remove(img)
    if not os.path.isfile(path):
        raise RuntimeError(f'Paint Lab: could not write {path}')


def stencil_texture():
    """The image texture the brush uses, LINKED from a small .blend of the add-on's own (Blender's Essentials
    brushes are linked data and take a linked texture only - the alphas work the same way).  Its image is the
    PNG the adjusted photo is written to; a rebake rewrites the PNG and reloads the image."""
    png, lib = _stencil_files()
    for t in bpy.data.textures:
        if t.library is not None and t.name == STENCIL_TEX and \
                os.path.normcase(bpy.path.abspath(t.library.filepath)) == os.path.normcase(lib):
            return t
    if not os.path.isfile(lib) or not os.path.isfile(png):
        if not os.path.isfile(png):
            _save_png(np.ones((64, 64, 4), np.float32) * 0.5, png)
        img = bpy.data.images.load(png, check_existing=False)
        img.name = STENCIL_IMAGE
        t = bpy.data.textures.new(STENCIL_TEX, 'IMAGE')
        t.image = img
        t.extension = 'CLIP'
        try:
            bpy.data.libraries.write(lib, {t}, path_remap='ABSOLUTE', fake_user=True)
        finally:
            bpy.data.textures.remove(t)
            bpy.data.images.remove(img)
    with bpy.data.libraries.load(lib, link=True) as (_src, dst):
        dst.textures = [STENCIL_TEX]
    return dst.textures[0] if dst.textures and dst.textures[0] is not None else None


def stencil_image(create=True):
    t = stencil_texture() if create else bpy.data.textures.get(STENCIL_TEX)
    return t.image if t is not None else None


def rebake(context=None):
    """The adjusted copy of the photo (hue / saturation / contrast / brightness / flips) written to the stencil
    PNG and reloaded into the brush's (linked) texture image.  Returns that image or None (no photo)."""
    st = settings(context)
    if st is None or st.photo is None:
        return None
    src = read_pixels(st.photo)
    if src.size == 0:
        return None
    out = pc.adjust(src, hue=st.hue, saturation=st.saturation, contrast=st.contrast, brightness=st.brightness,
                    flip_x=st.flip_x, flip_y=st.flip_y)
    png, _lib = _stencil_files()
    _save_png(out, png)
    tex = stencil_texture()
    if tex is None or tex.image is None:
        return None
    tex.image.reload()
    return tex.image


_PENDING = {'rebake': False}


def schedule_rebake(context=None):
    """Slider drags fire many updates: one rebake a little later (a 2k photo takes a few tenths of a second)."""
    if _PENDING['rebake']:
        return
    _PENDING['rebake'] = True

    def go():
        _PENDING['rebake'] = False
        try:
            rebake()
        except Exception as ex:          # noqa: BLE001  (a timer must not raise)
            print('[Mecha Lab] Paint Lab rebake:', ex)
        return None
    try:
        bpy.app.timers.register(go, first_interval=0.15)
    except Exception:                     # (no timers headless in some builds: do it now)
        go()


def active_brush(context=None):
    from . import zb_sculpt as zs
    return zs.brush(context)


def apply_mapping(context=None):
    """The brush's texture slot: the stencil image, STENCIL mapping when Stencil is on (Q), else the photo as a
    plain brush texture on the view plane; the rotation on both."""
    import math
    st = settings(context)
    b = active_brush(context)
    if st is None or b is None:
        return False
    slot = b.texture_slot
    slot.texture = stencil_texture() if st.photo is not None else None
    slot.map_mode = 'STENCIL' if st.stencil_on else 'VIEW_PLANE'
    slot.angle = math.radians(st.angle) if isinstance(st.angle, (int, float)) and abs(st.angle) > 7 else float(st.angle)
    return True


def fit_stencil(context, region=None):
    """The stencil placed in the middle of the view at the photo's aspect, a comfortable size."""
    st = settings(context)
    b = active_brush(context)
    if st is None or b is None or st.photo is None:
        return False
    region = region or getattr(context, 'region', None)
    w, h = (region.width, region.height) if region is not None else (1000, 800)
    iw, ih = st.photo.size
    if iw == 0 or ih == 0:
        return False
    scale = 0.45 * min(w / iw, h / ih)
    b.stencil_pos = (w * 0.5, h * 0.5)
    b.stencil_dimension = (iw * scale, ih * scale)
    return True


def load_photo(context, filepath):
    """The file loaded as the photo (an Image datablock), the stencil baked and put on the brush."""
    img = bpy.data.images.load(filepath, check_existing=True)
    st = settings(context)
    st.photo = img
    rebake(context)
    apply_mapping(context)
    return img


# -----------------------------------------------------------------------------
# the eyedropper: the polypaint colour under the mouse
# -----------------------------------------------------------------------------

def colour_attribute(me):
    """The mesh's active colour attribute (polypaint) or None."""
    ca = me.color_attributes
    if not len(ca):
        return None
    return ca.active_color or ca[0]


def read_colours(me, att=None):
    """(N, 4) point colours of the mesh (corner colours averaged onto the points); None without polypaint."""
    att = att or colour_attribute(me)
    if att is None:
        return None
    n = len(att.data)
    buf = np.empty(n * 4, np.float32)
    att.data.foreach_get('color', buf)
    cols = buf.reshape(n, 4).astype(np.float64)
    if att.domain == 'CORNER':
        cols = pc.corner_to_point(cols, mio.read_corner_verts(me), len(me.vertices))
    return cols


def sample_polypaint(ob, face_index, location_local):
    """The painted colour at a hit: the colour of the hit face's corner / point nearest the hit (not a blend of
    the lit pixels on screen).  Returns (r, g, b) or None."""
    me = ob.data
    att = colour_attribute(me)
    if att is None or face_index < 0 or face_index >= len(me.polygons):
        return None
    poly = me.polygons[face_index]
    loc = Vector(location_local)
    best, best_d = None, None
    for li, vi in zip(poly.loop_indices, poly.vertices):
        d = (me.vertices[vi].co - loc).length_squared
        if best_d is None or d < best_d:
            best_d, best = d, (li if att.domain == 'CORNER' else vi)
    c = att.data[best].color
    return (float(c[0]), float(c[1]), float(c[2]))


def eyedrop(context, mouse_xy, region=None, rv3d=None):
    """Ray from the mouse; the polypaint colour at the hit set as the brush colour.  Returns the colour or None."""
    from bpy_extras import view3d_utils
    from . import target_rules
    from . import zb_sculpt as zs
    region = region or context.region
    rv3d = rv3d or context.region_data
    if region is None or rv3d is None:
        return None
    o = view3d_utils.region_2d_to_origin_3d(region, rv3d, mouse_xy)
    d = view3d_utils.region_2d_to_vector_3d(region, rv3d, mouse_xy).normalized()
    dg = context.evaluated_depsgraph_get()
    hit, loc, _n, idx, ob, _m = target_rules.scene_ray(context, dg, o, d)
    if not hit or ob is None:
        return None
    real = bpy.data.objects.get(ob.name) or ob
    if real.type != 'MESH':
        return None
    col = sample_polypaint(real, idx, real.matrix_world.inverted_safe() @ Vector(loc))
    if col is None:
        return None
    set_brush_colour(context, col)
    return col


def set_brush_colour(context, rgb):
    from . import zb_sculpt as zs
    u = zs.unified(context)
    b = zs.brush(context)
    if u is not None and getattr(u, 'use_unified_color', False):
        u.color = rgb
    elif b is not None:
        b.color = rgb
    return True


def brush_colour(context):
    from . import zb_sculpt as zs
    u = zs.unified(context)
    b = zs.brush(context)
    if u is not None and getattr(u, 'use_unified_color', False):
        return tuple(u.color)
    return tuple(b.color) if b is not None else (1.0, 1.0, 1.0)


# -----------------------------------------------------------------------------
# masks
# -----------------------------------------------------------------------------

def read_mask(me):
    att = me.attributes.get(MASK_ATTR)
    if att is None:
        return np.zeros(len(me.vertices), np.float32)
    v = np.empty(len(me.vertices), np.float32)
    att.data.foreach_get('value', v)
    return v


def write_mask(me, values):
    att = me.attributes.get(MASK_ATTR)
    if att is None:
        att = me.attributes.new(MASK_ATTR, 'FLOAT', 'POINT')
    att.data.foreach_set('value', np.ascontiguousarray(np.clip(values, 0.0, 1.0), np.float32))
    me.update()
    return att


def _refresh_sculpt(context, ob):
    """A mask written to the mesh data shows in Sculpt Mode after a mode round trip."""
    if ob is None or ob.mode != 'SCULPT':
        return
    try:
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.mode_set(mode='SCULPT')
    except RuntimeError:
        pass


def mask_by_value(context, ob, st=None):
    """Mask from the polypaint's brightness (ZBrush Mask By Intensity): Black .. White range, Invert."""
    st = st or settings(context)
    me = ob.data
    cols = read_colours(me)
    if cols is None:
        return None
    m = pc.value_mask(cols, st.mask_black, st.mask_white, st.mask_invert)
    was = ob.mode
    if was == 'SCULPT':
        bpy.ops.object.mode_set(mode='OBJECT')
    write_mask(me, m)
    if was == 'SCULPT':
        bpy.ops.object.mode_set(mode='SCULPT')
    return float(m.mean())


def mask_by_edges(context, ob, st=None):
    """Mask on the mesh's folds (edge angle), soft fade, grown by rings."""
    st = st or settings(context)
    me = ob.data
    co = mio.read_co(me)
    vi = mio.read_corner_verts(me)
    start, tot = mio.read_face_starts(me)
    m = pc.edge_mask(co, vi.astype(np.int64), start.astype(np.int64), tot.astype(np.int64), len(co),
                     angle=st.edge_angle, soft=st.edge_soft)
    if st.edge_grow > 0:
        m = pc.grow_mask(m, vi.astype(np.int64), start.astype(np.int64), tot.astype(np.int64), len(co), st.edge_grow)
    if st.mask_invert:
        m = 1.0 - m
    was = ob.mode
    if was == 'SCULPT':
        bpy.ops.object.mode_set(mode='OBJECT')
    write_mask(me, m)
    if was == 'SCULPT':
        bpy.ops.object.mode_set(mode='SCULPT')
    return float(m.mean())


def mask_by_cavity(context, ob, st=None):
    """Blender's own cavity mask (needs Sculpt Mode)."""
    st = st or settings(context)
    if ob.mode != 'SCULPT':
        bpy.ops.object.mode_set(mode='SCULPT')
    bpy.ops.sculpt.mask_from_cavity(mix_mode='MIX', mix_factor=1.0, settings_source='OPERATOR',
                                    factor=st.cavity_int / 100.0, blur_steps=st.cavity_blur, invert=st.mask_invert)
    return True


def mask_clear(context, ob):
    was = ob.mode
    if was == 'SCULPT':
        bpy.ops.object.mode_set(mode='OBJECT')
    write_mask(ob.data, np.zeros(len(ob.data.vertices), np.float32))
    if was == 'SCULPT':
        bpy.ops.object.mode_set(mode='SCULPT')
    return True


# -----------------------------------------------------------------------------
# the look: colours that read true
# -----------------------------------------------------------------------------

def _set_enum(obj, prop, *candidates):
    for c in candidates:
        try:
            setattr(obj, prop, c)
            return c
        except TypeError:
            continue
    return None


def paint_material(ob):
    """A material whose base colour is the colour attribute (Principled, roughness 0.6, specular 0.3)."""
    mat = bpy.data.materials.get(PAINT_MAT)
    if mat is None:
        mat = bpy.data.materials.new(PAINT_MAT)
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if bsdf is not None:
            attr = nt.nodes.new('ShaderNodeVertexColor')
            attr.location = (bsdf.location.x - 300, bsdf.location.y)
            nt.links.new(attr.outputs['Color'], bsdf.inputs['Base Color'])
            if 'Roughness' in bsdf.inputs:
                bsdf.inputs['Roughness'].default_value = 0.6
            for name in ('Specular IOR Level', 'Specular'):
                if name in bsdf.inputs:
                    bsdf.inputs[name].default_value = 0.3
                    break
    if ob is not None and ob.type == 'MESH':
        att = colour_attribute(ob.data)
        node = next((n for n in mat.node_tree.nodes if n.type == 'VERTEX_COLOR'), None)
        if node is not None and att is not None:
            node.layer_name = att.name
        if not ob.data.materials:
            ob.data.materials.append(mat)
        elif ob.data.materials[0] is not mat and all(m is None or m.name != PAINT_MAT for m in ob.data.materials):
            ob.data.materials.append(mat)
            ob.active_material_index = len(ob.data.materials) - 1
    return mat


def apply_look(context, kind=None, space=None):
    """The viewport + colour management for painting.  Returns what was set (dict)."""
    st = settings(context)
    kind = kind or (st.look if st is not None else 'PAINT')
    sc = context.scene
    vs = sc.view_settings
    done = dict(kind=kind)
    if space is None:
        area = getattr(context, 'area', None)
        space = area.spaces.active if area is not None and area.type == 'VIEW_3D' else None
    sh = space.shading if space is not None else sc.display.shading
    if kind in ('PAINT', 'EXACT'):
        sh.type = 'SOLID'
        sh.light = 'STUDIO' if kind == 'PAINT' else 'FLAT'
        if kind == 'PAINT':
            done['studio_light'] = _set_enum(sh, 'studio_light', 'paint.sl', 'Default')
        sh.color_type = 'VERTEX'
        sh.show_specular_highlight = False
        sh.show_cavity = False
        sh.show_shadows = False
        sh.show_object_outline = False
        done['view_transform'] = _set_enum(vs, 'view_transform', 'Standard')
    else:
        sh.type = 'MATERIAL'
        sh.use_scene_world = False
        sh.use_scene_lights = False
        done['studio_light'] = _set_enum(sh, 'studio_light', 'studio.exr', 'interior.exr', 'forest.exr')
        sh.studiolight_background_alpha = 0.0
        sh.studiolight_intensity = 1.0
        done['view_transform'] = _set_enum(vs, 'view_transform', 'Khronos PBR Neutral', 'Standard')
        ob = context.view_layer.objects.active
        if ob is not None and ob.type == 'MESH':
            paint_material(ob)
    _set_enum(vs, 'look', 'None')
    vs.exposure = 0.0
    vs.gamma = 1.0
    if st is not None and st.look != kind:
        st.look = kind
    return done


def ensure_polypaint(ob):
    """A colour attribute to paint into (white), active, when the mesh has none."""
    me = ob.data
    if colour_attribute(me) is None:
        att = me.color_attributes.new('Color', 'FLOAT_COLOR', 'POINT')
        n = len(att.data)
        att.data.foreach_set('color', np.ones(n * 4, np.float32))
        me.color_attributes.active_color = att
        me.update()
        return att
    return colour_attribute(me)


# -----------------------------------------------------------------------------
# operators
# -----------------------------------------------------------------------------

class MCH_OT_paint_load_photo(bpy.types.Operator):
    """Load a photo / texture file as the Paint Lab stencil + brush texture"""
    bl_idname = 'mch.paint_load_photo'
    bl_label = 'Load Photo'
    bl_options = {'REGISTER', 'UNDO'}
    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default='*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.exr;*.bmp;*.tga;*.webp', options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if not self.filepath or not os.path.exists(self.filepath):
            self.report({'WARNING'}, 'Paint Lab: no file')
            return {'CANCELLED'}
        img = load_photo(context, self.filepath)
        fit_stencil(context)
        self.report({'INFO'}, f'Paint Lab: photo "{img.name}" {img.size[0]}x{img.size[1]}')
        return {'FINISHED'}


class MCH_OT_paint_stencil(bpy.types.Operator):
    """Q: the photo shown as a stencil over the view (paint through it) / hidden (the photo is then the plain brush texture)"""
    bl_idname = 'mch.paint_stencil'
    bl_label = 'Stencil On / Off'
    bl_options = {'REGISTER'}
    action: EnumProperty(items=[('TOGGLE', 'Toggle', ''), ('ON', 'On', ''), ('OFF', 'Off', ''), ('FIT', 'Fit', '')], default='TOGGLE')

    def execute(self, context):
        st = settings(context)
        if st is None:
            return {'CANCELLED'}
        if self.action == 'FIT':
            fit_stencil(context)
            return {'FINISHED'}
        st.stencil_on = (not st.stencil_on) if self.action == 'TOGGLE' else self.action == 'ON'
        if st.stencil_on:
            fit_stencil(context)
        return {'FINISHED'}


class MCH_OT_paint_eyedrop(bpy.types.Operator):
    """Pick the POLYPAINT colour under the mouse as the brush colour (the painted value, not the lit pixel)"""
    bl_idname = 'mch.paint_eyedrop'
    bl_label = 'Polypaint Eyedropper'
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        col = eyedrop(context, (event.mouse_region_x, event.mouse_region_y))
        if col is None:
            self.report({'WARNING'}, 'Paint Lab: no polypaint under the mouse')
            return {'CANCELLED'}
        self.report({'INFO'}, 'colour %.2f %.2f %.2f' % col)
        return {'FINISHED'}


class MCH_OT_paint_mask(bpy.types.Operator):
    """Paint Lab masks: from the polypaint's brightness, from the mesh's edges, from cavities; clear"""
    bl_idname = 'mch.paint_mask'
    bl_label = 'Paint Mask'
    bl_options = {'REGISTER', 'UNDO'}
    kind: EnumProperty(items=[('VALUE', 'By Brightness', ''), ('EDGE', 'By Edges', ''), ('CAVITY', 'By Cavity', ''),
                              ('CLEAR', 'Clear', ''), ('INVERT', 'Invert', '')], default='VALUE')

    @classmethod
    def poll(cls, context):
        ob = context.view_layer.objects.active
        return ob is not None and ob.type == 'MESH'

    def execute(self, context):
        ob = context.view_layer.objects.active
        if self.kind == 'VALUE':
            r = mask_by_value(context, ob)
            if r is None:
                self.report({'WARNING'}, 'Paint Lab: the mesh has no polypaint yet')
                return {'CANCELLED'}
            self.report({'INFO'}, f'Mask by brightness: {r * 100:.0f} % masked')
        elif self.kind == 'EDGE':
            r = mask_by_edges(context, ob)
            self.report({'INFO'}, f'Mask by edges: {r * 100:.0f} % masked')
        elif self.kind == 'CAVITY':
            mask_by_cavity(context, ob)
        elif self.kind == 'CLEAR':
            mask_clear(context, ob)
        else:
            was = ob.mode
            if was == 'SCULPT':
                bpy.ops.object.mode_set(mode='OBJECT')
            write_mask(ob.data, 1.0 - read_mask(ob.data))
            if was == 'SCULPT':
                bpy.ops.object.mode_set(mode='SCULPT')
        return {'FINISHED'}


class MCH_OT_paint_look(bpy.types.Operator):
    """The viewport set so the painted colours read true (Paint: lit · Exact: flat · Material: neutral HDRI)"""
    bl_idname = 'mch.paint_look'
    bl_label = 'Paint Look'
    bl_options = {'REGISTER'}
    kind: EnumProperty(items=LOOKS, default='PAINT')

    def execute(self, context):
        done = apply_look(context, self.kind)
        self.report({'INFO'}, f'Paint Lab look: {done}')
        return {'FINISHED'}


CLASSES = (MCH_PG_PaintLab, MCH_OT_paint_load_photo, MCH_OT_paint_stencil, MCH_OT_paint_eyedrop, MCH_OT_paint_mask,
           MCH_OT_paint_look)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_paint = PointerProperty(type=MCH_PG_PaintLab)
    bpy.types.WindowManager.mch_paint_on = BoolProperty(default=False, options={'SKIP_SAVE'})


def unregister():
    if hasattr(bpy.types.Scene, 'mch_paint'):
        del bpy.types.Scene.mch_paint
    if hasattr(bpy.types.WindowManager, 'mch_paint_on'):
        del bpy.types.WindowManager.mch_paint_on
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
