"""0.24.95 Decals (user picked "데칼 - 번호, 경고 줄무늬, 로고를 표면에 붙이는 기능"; "데칼 그냥 너가 만들자 - 데칼에 데미지
들어간 것도 쉐이더로 넣어 줘, 조절할 수 있게").

* the library (``decals/<ID>.png``, made by ``tools_dev/make_decals.py``): 24 two-tone decals - hazard stripes,
  chevrons, arrows, warning / high voltage / radiation signs, NO STEP, DANGER, CAUTION, EJECT, LIFT, FUEL, roundel,
  crosshair, vent slots, barcode, serial plate, star, rank stripes, dots, corner brackets, unit circle - white in the
  picture = Color 1, black = Color 2, so any colours; and Text decals (any letters / numbers, from a letter atlas)
* placing: click a decal ball, then click a part - a decal is a small dense plane on the part, wrapped onto its
  surface (Shrinkwrap, projected along the decal's normal - it follows curved surfaces) and parented to it (it moves
  with the part); G / R / S move it over the surface.  Mirror X (across the part), Apply (a plain mesh), Delete
* damage in the decal's shader, all sliders: Wear (chips, the Mech Shader's chip map), Edge Peel (the decal's border
  goes first), Scratches (the scratch map cuts lines through it), Dirt (grime over it), Fade (sun-bleached); Damage
  Scale and Seed - where the decal is gone the part shows through
* 0.24.95 (user: "추가 데칼이야! 이거도 추가해 줘") 30 full-colour Sci-Fi decals (``decals/SF_*.png`` + ``scifi.json``, from
  the user's pack by ``tools_dev/import_scifi_decals.py``): their own colours (sRGB) with Hue / Saturation / Value and
  a Tint; the same damage sliders"""
from __future__ import annotations

import json
import math
import os

import bmesh
import bpy
from bpy.props import BoolProperty, FloatProperty, FloatVectorProperty, PointerProperty, StringProperty
from mathutils import Matrix, Vector

from . import mech_shader as ms

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'decals')
KEY = 'mch_decal'
TEXT = 'TEXT'
# id: (label, width : height, colour 1, colour 2 (sRGB)) - as tools_dev/make_decals.py draws them
DECALS = {
    'HAZARD': ('Hazard Stripes', 2.0, (0.95, 0.75, 0.05), (0.05, 0.05, 0.05)),
    'HAZARD_RW': ('Red / White Stripes', 2.0, (0.85, 0.1, 0.08), (0.92, 0.92, 0.9)),
    'BARS': ('Two Bars', 2.0, (0.92, 0.92, 0.9), (0.05, 0.05, 0.05)),
    'CHEVRON': ('Chevrons', 2.0, (0.92, 0.92, 0.9), (0.05, 0.05, 0.05)),
    'ARROW': ('Arrow', 2.0, (0.92, 0.92, 0.9), (0.05, 0.05, 0.05)),
    'WARNING': ('Warning', 1.0, (0.95, 0.75, 0.05), (0.05, 0.05, 0.05)),
    'VOLTAGE': ('High Voltage', 1.0, (0.95, 0.75, 0.05), (0.05, 0.05, 0.05)),
    'RADIATION': ('Radiation', 1.0, (0.95, 0.75, 0.05), (0.05, 0.05, 0.05)),
    'NO_STEP': ('No Step', 2.5, (0.92, 0.92, 0.9), (0.05, 0.05, 0.05)),
    'DANGER': ('Danger', 2.5, (0.85, 0.1, 0.08), (0.95, 0.95, 0.93)),
    'CAUTION': ('Caution', 2.5, (0.95, 0.75, 0.05), (0.05, 0.05, 0.05)),
    'EJECT': ('Eject', 2.0, (0.95, 0.75, 0.05), (0.05, 0.05, 0.05)),
    'LIFT': ('Lift Point', 1.6, (0.92, 0.92, 0.9), (0.05, 0.05, 0.05)),
    'FUEL': ('Fuel', 1.0, (0.92, 0.92, 0.9), (0.85, 0.1, 0.08)),
    'ROUNDEL': ('Roundel', 1.0, (0.92, 0.92, 0.9), (0.1, 0.25, 0.6)),
    'CROSSHAIR': ('Crosshair', 1.0, (0.92, 0.92, 0.9), (0.05, 0.05, 0.05)),
    'VENT': ('Vent Slots', 1.6, (0.05, 0.05, 0.05), (0.3, 0.3, 0.3)),
    'BARCODE': ('Barcode', 2.0, (0.05, 0.05, 0.05), (0.92, 0.92, 0.9)),
    'SERIAL': ('Serial Plate', 2.2, (0.92, 0.92, 0.9), (0.05, 0.05, 0.05)),
    'STAR': ('Star', 1.0, (0.92, 0.92, 0.9), (0.05, 0.05, 0.05)),
    'RANK': ('Rank Stripes', 1.0, (0.95, 0.75, 0.05), (0.05, 0.05, 0.05)),
    'DOTS': ('Dot Grid', 1.0, (0.92, 0.92, 0.9), (0.05, 0.05, 0.05)),
    'CORNERS': ('Corner Brackets', 1.0, (0.92, 0.92, 0.9), (0.05, 0.05, 0.05)),
    'CIRCLE_NUM': ('Unit Circle', 1.0, (0.92, 0.92, 0.9), (0.05, 0.05, 0.05)),
}
# 0.24.95 (user: "너도 좀 더 바코드 같은 데칼 종류 더 만들어 줘") the Tech Marks - two-tone too (tools_dev/make_decals.py TECH)
_W, _K, _Y, _R = (0.92, 0.92, 0.9), (0.05, 0.05, 0.05), (0.95, 0.75, 0.05), (0.85, 0.1, 0.08)
TECH_MARKS = {
    'BARCODE_TALL': ('Barcode Label', 1.25, _K, _W),
    'BARCODE_STRIP': ('Barcode Strip', 4.0, _W, _K),
    'QR': ('QR Code', 1.0, _K, _W),
    'DATAMATRIX': ('Data Matrix', 1.0, _K, _W),
    'SERIAL_TAG': ('Serial Tag', 2.4, _W, (0.12, 0.12, 0.13)),
    'LOT_LABEL': ('Lot Label', 1.6, _K, _W),
    'RULER': ('Ruler', 6.0, _W, _K),
    'TICK_RING': ('Tick Ring', 1.0, _W, _K),
    'GAUGE': ('Gauge', 1.4, _W, _K),
    'TARGET': ('Reg. Target', 1.0, _W, _K),
    'TECH_TEXT': ('Tech Text', 3.2, _W, _K),
    'WARN_LABEL': ('Warning Label', 3.2, _Y, _K),
    'KEEP_CLEAR': ('Keep Clear', 2.5, _W, _K),
    'NUMBER': ('Stencil 07', 1.1, _W, _K),
    'HEXGRID': ('Hex Grid', 1.6, _W, _K),
    'DASHES': ('Dash Line', 8.0, _W, _K),
    'PINSTRIPE': ('Pinstripes', 8.0, _R, _W),
    'CHECKER': ('Checker Band', 6.0, _W, _K),
    'CIRCUIT': ('Circuit', 1.6, _W, _K),
    'POWER_CELL': ('Power Cell', 2.0, _W, _K),
    'ARROW_ROW': ('Arrow Row', 4.0, _Y, _K),
    'AXIS': ('Axis Mark', 1.0, _W, _R),
    'PANEL_ID': ('Panel ID', 1.5, _K, _W),
    'PERFORATION': ('Perforation', 2.0, _W, _K),
}
DECALS.update(TECH_MARKS)
TEXT_COLORS = ((0.92, 0.92, 0.9), (0.05, 0.05, 0.05))
VALUES = ('opacity', 'roughness', 'metallic', 'wear', 'peel', 'scratches', 'dirt', 'fade', 'damage_scale', 'seed',
          'hue', 'sat', 'val')
FRAME_UV = 'mch_frame'            # (0..1 across the whole decal: the border for Edge Peel, also for text decals)
_GLYPHS = [None]


def _load_colour():
    """0.24.95 the full-colour Sci-Fi decals: id -> (label, width : height), in the pack's order."""
    try:
        with open(os.path.join(DIR, 'scifi.json'), encoding='utf-8') as f:
            return {k: (v[0], float(v[1])) for k, v in json.load(f).items()}
    except (OSError, ValueError, KeyError, IndexError):
        return {}


COLOR_DECALS = _load_colour()


def known(ident):
    return ident == TEXT or ident in DECALS or ident in COLOR_DECALS


def is_full(ident):
    """A full-colour decal (its picture's own colours), not a two-tone mask."""
    return ident in COLOR_DECALS


def label_of(ident):
    return (COLOR_DECALS.get(ident) or DECALS.get(ident) or ('Decal',))[0]


def ratio_of(ident):
    return (COLOR_DECALS.get(ident) or DECALS.get(ident) or ('', 1.0))[1]


def image_path(ident):
    """The decal's picture: ``<id>.png`` (two-tone, the letters) or ``<id>.webp`` (0.24.95 the Sci-Fi ones)."""
    name = 'glyphs' if ident == TEXT else ident
    for ext in ('.png', '.webp'):
        p = os.path.join(DIR, name + ext)
        if os.path.isfile(p):
            return p
    return ''


def decal_image(ident):
    p = image_path(ident)
    if not p:
        return None
    img = bpy.data.images.load(p, check_existing=True)
    try:
        # (a two-tone mask: white = Color 1, black = Color 2 - data; a full-colour decal: its colours, sRGB)
        img.colorspace_settings.name = 'sRGB' if is_full(ident) else 'Non-Color'
        img.alpha_mode = 'STRAIGHT'
    except (TypeError, AttributeError):
        pass
    return img


def glyphs():
    if _GLYPHS[0] is None:
        with open(os.path.join(DIR, 'glyphs.json'), encoding='utf-8') as f:
            _GLYPHS[0] = json.load(f)
    return _GLYPHS[0]


def is_decal(ob):
    return ob is not None and getattr(ob, KEY, None) is not None and getattr(ob, KEY).is_decal


# -----------------------------------------------------------------------------
# the decal's mesh: a dense plane (it bends over the surface), UVs, a frame UV
# -----------------------------------------------------------------------------

def _grid(bm, uv, fr, rect, uvrect, frame, nx, ny):
    (x0, y0, x1, y1), (u0, v0, u1, v1), (fx0, fy0, fx1, fy1) = rect, uvrect, frame
    rows = []
    for j in range(ny + 1):
        t = j / ny
        rows.append([bm.verts.new((x0 + (x1 - x0) * i / nx, y0 + (y1 - y0) * t, 0.0)) for i in range(nx + 1)])
    for j in range(ny):
        for i in range(nx):
            f = bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
            for loop in f.loops:
                co = loop.vert.co
                s = (co.x - x0) / max(x1 - x0, 1e-9)
                t = (co.y - y0) / max(y1 - y0, 1e-9)
                loop[uv].uv = (u0 + (u1 - u0) * s, v0 + (v1 - v0) * t)
                loop[fr].uv = ((co.x - fx0) / max(fx1 - fx0, 1e-9), (co.y - fy0) / max(fy1 - fy0, 1e-9))


def decal_mesh(name, ident, text, h):
    """The decal's plane, ``h`` tall, centred on its origin, facing +Z."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')
    fr = bm.loops.layers.uv.new(FRAME_UV)
    if ident == TEXT:
        info = glyphs()
        cols, rows = info['cols'], info['rows']
        chars = [ch for ch in text.upper() if ch == ' ' or ch in info['glyphs']]
        widths = [info['space'] if ch == ' ' else info['glyphs'][ch]['width'] for ch in chars]
        total = sum(widths) * h
        frame = (-total / 2, -h / 2, total / 2, h / 2)
        x = -total / 2
        for ch, wd in zip(chars, widths):
            if ch != ' ':
                cx, cy = info['glyphs'][ch]['cell']
                u_c = (cx + 0.5) / cols
                half = wd / 2 / cols
                v1 = 1.0 - cy / rows
                _grid(bm, uv, fr, (x, -h / 2, x + wd * h, h / 2), (u_c - half, v1 - 1.0 / rows, u_c + half, v1),
                      frame, 3, 3)
            x += wd * h
    else:
        ratio = ratio_of(ident)
        w = h * ratio
        nx = max(6, round(10 * ratio))
        _grid(bm, uv, fr, (-w / 2, -h / 2, w / 2, h / 2), (0.0, 0.0, 1.0, 1.0), (-w / 2, -h / 2, w / 2, h / 2),
              nx, 10)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


# -----------------------------------------------------------------------------
# the decal's shader: two colours from the mask, damage cutting it away
# -----------------------------------------------------------------------------

def build_material(mat, img, h):
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    b = ms.Builder(nt)
    out = b.node('ShaderNodeOutputMaterial')
    bsdf = b.node('ShaderNodeBsdfPrincipled', 'mch:bsdf')
    b.link(bsdf.outputs['BSDF'], out.inputs['Surface'])
    v = {k: b.value(k) for k in VALUES + ('full',)}
    c = {k: b.rgb(k) for k in ('color1', 'color2', 'tint')}
    uvn = b.node('ShaderNodeUVMap')
    uvn.uv_map = 'UVMap'
    frn = b.node('ShaderNodeUVMap')
    frn.uv_map = FRAME_UV
    tex = b.node('ShaderNodeTexImage', 'mch:img:decal')
    tex.image = img
    tex.interpolation = 'Linear'
    tex.extension = 'CLIP'
    b.link(uvn.outputs['UV'], tex.inputs['Vector'])
    mask = tex.outputs['Color']
    # (the damage maps on the decal's own plane: Damage Scale x per decal height, moved by Seed)
    tc = b.node('ShaderNodeTexCoord')
    off = b.node('ShaderNodeCombineXYZ')
    b.link(b.math('MULTIPLY', v['seed'], 7.31), off.inputs[0])
    b.link(b.math('MULTIPLY', v['seed'], 3.17), off.inputs[1])
    unit = b.math('DIVIDE', v['damage_scale'], max(h, 1e-6))
    unit.node.name = 'mch:unit'
    vec = b.vmath('ADD', b.vmath('SCALE', tc.outputs['Object'], fac=unit), off.outputs['Vector'])

    def damage_map(name, slot, ident, scale):
        nd = b.node('ShaderNodeTexImage', 'mch:img:' + name)
        nd.image = ms.map_image(slot, ident, data=True)
        nd.extension = 'REPEAT'
        b.link(b.vmath('SCALE', vec, fac=scale), nd.inputs['Vector'])
        return nd.outputs['Color']
    chips = damage_map('chips', 'chip', 'FLAKES', 0.6)
    lines = damage_map('scratch', 'scratch', 'FINE', 0.5)
    grime = damage_map('dirt', 'dirt', 'GRIME', 0.4)
    # (Edge Peel: the decal's border goes first - 0 inside .. 1 at the edge, 15 % of the way in)
    sep = b.node('ShaderNodeSeparateXYZ')
    b.link(frn.outputs['UV'], sep.inputs['Vector'])
    d = b.math('MINIMUM', b.math('MINIMUM', sep.outputs['X'], b.math('SUBTRACT', 1.0, sep.outputs['X'])),
               b.math('MINIMUM', sep.outputs['Y'], b.math('SUBTRACT', 1.0, sep.outputs['Y'])))
    edge = b.maprange(d, 0.15, 0.0)
    chip_in = b.math('ADD', b.math('MULTIPLY', chips, 0.75), b.math('MULTIPLY', edge, b.math('MULTIPLY', v['peel'], 0.7)),
                     clamp=True)
    chip = b.threshold(chip_in, v['wear'], 0.06)
    scratch = b.threshold(lines, b.math('MULTIPLY', v['scratches'], 0.75), 0.05)
    gone = b.math('MAXIMUM', chip, scratch)
    alpha = b.math('MULTIPLY', b.math('MULTIPLY', tex.outputs['Alpha'], v['opacity']),
                   b.math('SUBTRACT', 1.0, gone), clamp=True)
    b.link(alpha, bsdf.inputs['Alpha'])
    col = b.mixc(mask, c['color2'], c['color1'])
    # (0.24.95 a full-colour decal: the picture's own colours x Tint; then Hue / Saturation / Value for either kind)
    col = b.mixc(v['full'], col, b.mixc(1.0, mask, c['tint'], 'MULTIPLY'))
    hsv = b.node('ShaderNodeHueSaturation', 'mch:hsv')
    b.link(v['hue'], hsv.inputs['Hue'])
    b.link(v['sat'], hsv.inputs['Saturation'])
    b.link(v['val'], hsv.inputs['Value'])
    b.link(col, hsv.inputs['Color'])
    col = hsv.outputs['Color']
    bw = b.node('ShaderNodeRGBToBW')
    b.link(col, bw.inputs['Color'])
    col = b.mixc(v['fade'], col, b.mixc(0.5, bw.outputs['Val'], (0.86, 0.85, 0.82, 1.0)))     # (sun-bleached)
    dirt = b.threshold(grime, v['dirt'], 0.2)
    col = b.mixc(b.math('MULTIPLY', dirt, 0.85), col, ms._lin((0.16, 0.12, 0.08)) + (1.0,))
    b.link(col, bsdf.inputs['Base Color'])
    b.link(b.mixf(dirt, v['roughness'], 0.88), bsdf.inputs['Roughness'])
    b.link(v['metallic'], bsdf.inputs['Metallic'])
    try:
        mat.surface_render_method = 'DITHERED'
    except (AttributeError, TypeError):
        pass
    mat[KEY] = 1
    return mat


def sync(ob):
    """The decal's settings into its material, its size and its distance from the surface."""
    if not is_decal(ob):
        return
    st = getattr(ob, KEY)
    mat = ob.active_material
    if mat is not None and mat.node_tree is not None:
        nodes = mat.node_tree.nodes
        for k in VALUES:
            nd = nodes.get('mch:' + k)
            if nd is not None:
                nd.outputs[0].default_value = float(getattr(st, k))
        nd = nodes.get('mch:full')
        if nd is not None:
            nd.outputs[0].default_value = 1.0 if is_full(st.kind) else 0.0
        for k in ('color1', 'color2', 'tint'):
            nd = nodes.get('mch:' + k)
            if nd is not None:
                nd.outputs[0].default_value = (*getattr(st, k), 1.0)
    sw = ob.modifiers.get('Decal Wrap')
    if sw is not None:
        sw.offset = st.offset * st.height
    if tuple(ob.scale) != (st.size,) * 3:
        ob.scale = (st.size,) * 3


def _update(self, context):
    sync(self.id_data)


def _s(name, default, lo=0.0, hi=1.0, desc=''):
    return FloatProperty(name=name, default=default, min=lo, max=hi, update=_update, description=desc)


class MCH_PG_Decal(bpy.types.PropertyGroup):
    is_decal: BoolProperty(default=False)
    kind: StringProperty(default='')
    text: StringProperty(default='')
    height: FloatProperty(default=0.1)
    color1: FloatVectorProperty(name='Color 1', subtype='COLOR', size=3, min=0.0, max=1.0, default=(0.8, 0.8, 0.78),
                                update=_update, description='The white of the decal picture')
    color2: FloatVectorProperty(name='Color 2', subtype='COLOR', size=3, min=0.0, max=1.0, default=(0.0, 0.0, 0.0),
                                update=_update, description='The black of the decal picture')
    tint: FloatVectorProperty(name='Tint', subtype='COLOR', size=3, min=0.0, max=1.0, default=(1.0, 1.0, 1.0),
                              update=_update, description='A full-colour decal\'s colours multiplied by this (white: as '
                              'drawn)')
    hue: _s('Hue', 0.5, desc='Turn the colours round the colour wheel (0.5: as they are)')
    sat: _s('Saturation', 1.0, 0.0, 2.0, 'Less / more colour (1: as they are)')
    val: _s('Value', 1.0, 0.0, 2.0, 'Darker / brighter (1: as they are)')
    opacity: _s('Opacity', 1.0)
    roughness: _s('Roughness', 0.45)
    metallic: _s('Metallic', 0.0)
    wear: _s('Wear', 0.0, desc='Chipped away (the Mech Shader\'s chip map) - the part shows through')
    peel: _s('Edge Peel', 0.0, desc='The decal\'s border goes first, as a sticker peels')
    scratches: _s('Scratches', 0.0, desc='Lines scratched through the decal')
    dirt: _s('Dirt', 0.0, desc='Grime over the decal')
    fade: _s('Fade', 0.0, desc='Sun-bleached: paler, less colour')
    damage_scale: _s('Damage Scale', 1.0, 0.1, 10.0, 'The damage pattern smaller (bigger number)')
    seed: _s('Seed', 0.0, 0.0, 100.0, 'Another damage pattern')
    size: _s('Size', 1.0, 0.05, 20.0, 'The decal bigger / smaller')
    offset: _s('Lift', 0.004, 0.0, 0.1, 'How far above the surface (x the decal\'s height) - more if it flickers')


# -----------------------------------------------------------------------------
# placing
# -----------------------------------------------------------------------------

def place(context, target, location, normal, ident, text='', right=None):
    """A decal ``ident`` (or TEXT ``text``) on ``target`` at ``location`` facing ``normal`` (world); ``right``: which
    way its width runs (default: across the view / world X).  Returns the decal object."""
    size = max(target.dimensions) or 1.0
    h = size * (0.07 if ident == TEXT else 0.16)
    label = f'Text "{text}"' if ident == TEXT else label_of(ident)
    me = decal_mesh('Decal ' + label, ident, text, h)
    ob = bpy.data.objects.new('Decal ' + label, me)
    cols = target.users_collection or (context.scene.collection,)
    cols[0].objects.link(ob)
    z = Vector(normal).normalized()
    x = Vector(right) if right is not None else Vector((1.0, 0.0, 0.0))
    x = x - z * x.dot(z)
    if x.length < 1e-4:
        x = Vector((0.0, 1.0, 0.0)) - z * z.y
    x.normalize()
    y = z.cross(x)
    rot = Matrix((x, y, z)).transposed().to_4x4()
    ob.matrix_world = Matrix.Translation(Vector(location) + z * h * 0.002) @ rot
    mat = bpy.data.materials.new('Decal ' + label)
    build_material(mat, decal_image(ident), h)
    me.materials.append(mat)
    sw = ob.modifiers.new('Decal Wrap', 'SHRINKWRAP')
    sw.target = target
    sw.wrap_method = 'PROJECT'
    sw.use_project_z = True
    sw.use_negative_direction = True
    sw.use_positive_direction = True
    sw.project_limit = h * 0.6                        # (only the surface under the decal, not one behind it)
    sw.cull_face = 'OFF'
    ob.parent = target
    ob.matrix_parent_inverse = target.matrix_world.inverted()
    ob.visible_shadow = False
    st = getattr(ob, KEY)
    st.is_decal, st.kind, st.text, st.height = True, ident, text, h
    if ident in DECALS or ident == TEXT:
        c1, c2 = TEXT_COLORS if ident == TEXT else DECALS[ident][2:4]
        st.color1, st.color2 = ms._lin(c1), ms._lin(c2)
    sync(ob)
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    return ob


def _ray(context, origin, direction):
    """The first mesh (not a decal) along the ray: (object, location, normal) or None."""
    dg = context.evaluated_depsgraph_get()
    o = Vector(origin)
    for _i in range(12):
        hit, loc, nrm, _idx, obj, _mx = context.scene.ray_cast(dg, o, direction)
        if not hit:
            return None
        if obj is not None and obj.type == 'MESH' and not is_decal(obj):
            return obj, loc, nrm
        o = loc + Vector(direction) * 1e-4
    return None


class MCH_OT_decal_place(bpy.types.Operator):
    """Place a decal: click a part (Esc / right click: cancel).  It wraps onto the surface and moves with the part"""
    bl_idname = 'mch.decal_place'
    bl_label = 'Place Decal'
    bl_options = {'REGISTER', 'UNDO'}
    decal: StringProperty(default='HAZARD')
    text: StringProperty(default='')
    target: StringProperty(default='')
    location: FloatVectorProperty(size=3)
    normal: FloatVectorProperty(size=3, default=(0.0, 0.0, 1.0))

    def _ident(self):
        return TEXT if self.text else self.decal

    def execute(self, context):
        target = bpy.data.objects.get(self.target)
        if target is None or target.type != 'MESH' or not known(self._ident()):
            self.report({'WARNING'}, 'Decal: no part to put it on')
            return {'CANCELLED'}
        ob = place(context, target, self.location, self.normal, self._ident(), self.text)
        self.report({'INFO'}, f'"{ob.name}" on {target.name}')
        return {'FINISHED'}

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, 'Decal: use it in the 3D view')
            return {'CANCELLED'}
        context.window.cursor_modal_set('CROSSHAIR')
        if not known(self._ident()):
            return {'CANCELLED'}
        what = f'"{self.text}"' if self.text else label_of(self.decal)
        context.area.header_text_set(f'Decal {what}: click a part to place it   (Esc / right click: cancel)')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _end(self, context):
        context.window.cursor_modal_restore()
        if context.area is not None:
            context.area.header_text_set(None)

    def modal(self, context, event):
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            self._end(context)
            return {'CANCELLED'}
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            from bpy_extras import view3d_utils
            region, rv3d = context.region, context.region_data
            if region is None or rv3d is None or region.type != 'WINDOW':
                return {'PASS_THROUGH'}
            co = (event.mouse_region_x, event.mouse_region_y)
            origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, co)
            direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, co)
            hit = _ray(context, origin, direction)
            if hit is None:
                return {'RUNNING_MODAL'}                  # (missed: keep waiting for a click on a part)
            obj, loc, nrm = hit
            right = rv3d.view_rotation @ Vector((1.0, 0.0, 0.0))
            place(context, obj, loc, nrm, self._ident(), self.text, right=right)
            self._end(context)
            return {'FINISHED'}
        return {'PASS_THROUGH'}                           # (orbit / zoom while choosing where)


class MCH_OT_decal_text(bpy.types.Operator):
    """A text decal: type the letters / numbers, then click a part"""
    bl_idname = 'mch.decal_text'
    bl_label = 'Text Decal'
    bl_options = {'REGISTER'}
    text: StringProperty(name='Text', default='UNIT 07')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if not self.text.strip():
            return {'CANCELLED'}
        return bpy.ops.mch.decal_place('INVOKE_DEFAULT', text=self.text.strip())


def _decals(context):
    return [o for o in context.selected_objects if is_decal(o)] or \
        ([context.active_object] if is_decal(context.active_object) else [])


class MCH_OT_decal_mirror(bpy.types.Operator):
    """Mirror the decal across its part's X (on / off)"""
    bl_idname = 'mch.decal_mirror'
    bl_label = 'Mirror Decal'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        n = 0
        for ob in _decals(context):
            m = ob.modifiers.get('Decal Mirror')
            if m is not None:
                ob.modifiers.remove(m)
            else:
                m = ob.modifiers.new('Decal Mirror', 'MIRROR')
                m.mirror_object = ob.parent
                m.use_axis = (True, False, False)
            n += 1
        return {'FINISHED'} if n else {'CANCELLED'}


class MCH_OT_decal_apply(bpy.types.Operator):
    """Make the decal a plain mesh (its wrap and mirror applied): it no longer follows the surface when moved"""
    bl_idname = 'mch.decal_apply'
    bl_label = 'Apply Decal'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        n = 0
        for ob in _decals(context):
            dg = context.evaluated_depsgraph_get()
            me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
            old = ob.data
            ob.modifiers.clear()
            ob.data = me
            if old.users == 0:
                bpy.data.meshes.remove(old)
            n += 1
        return {'FINISHED'} if n else {'CANCELLED'}


class MCH_OT_decal_delete(bpy.types.Operator):
    """Delete the selected decals"""
    bl_idname = 'mch.decal_delete'
    bl_label = 'Delete Decal'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obs = _decals(context)
        for ob in obs:
            mats = [m for m in ob.data.materials if m is not None]
            me = ob.data
            bpy.data.objects.remove(ob)
            if me.users == 0:
                bpy.data.meshes.remove(me)
            for m in mats:
                if m.users == 0:
                    bpy.data.materials.remove(m)
        return {'FINISHED'} if obs else {'CANCELLED'}


CLASSES = (MCH_PG_Decal, MCH_OT_decal_place, MCH_OT_decal_text, MCH_OT_decal_mirror, MCH_OT_decal_apply,
           MCH_OT_decal_delete)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Object.mch_decal = PointerProperty(type=MCH_PG_Decal)


def unregister():
    try:
        del bpy.types.Object.mch_decal
    except AttributeError:
        pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
