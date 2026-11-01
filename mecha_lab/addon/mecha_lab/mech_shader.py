"""0.24.95 Mech Shader (user: "메카닉 쉐이더 프리셋 만들어 주라 - 플라스틱, 쇠, 페인트, 페인트 조금 까진 쇠, 위에 흙 묻은 거,
눈 묻은 거, 기스 난 거, 쇠 질감 여러 가지, 그리고 에미션, 기스 난 거에 녹슨 거 보이는 거 - 슬라이더로 조절 가능하게, 그리고
천, 러프니스 조정, 러프니스나 저런 맵 같은 거는 각자 프리셋 있어서 한 10개 정도, 내가 넘기면 바로바로 바뀌게"; then "프로시저럴
말고 너가 러프니스 맵이랑 베이스 맵 직접 만들어서 해 줘").

One material of layers, each a mask times a look, every pattern a texture MAP (``mech_maps/<slot>/<id>.png|jpg``,
512 px, seamless, made by ``tools_dev/make_mech_maps.py``) put on the part with box projection (object space: no UVs
needed):

    base (colour x a Base map, metallic, roughness + a Roughness map)
    paint (coverage) - chipped at the edges (Edge Wear x a Chips map) and through the scratches (a Scratches map)
    rust (Rust colour map, its own mask map, in the crevices and in the scratches / chips: Rust in Scratches)
    dirt (in the crevices, a Dirt map), snow (on what faces up, a Snow map), emission (an Emission map, or the
    edges / panel lines / scratches), cloth (a Weave map + sheen)

Ten maps per slot; a step to the next map swaps one image in the material's nodes - it changes at once.  The material
presets (Steel, Chipped Paint, Rusty Scratches, Snowy Metal, Cloth Canvas ...) set every slider and map.  Edges and
crevices come from the mesh (``store_curvature``: the ``mch_curv`` attribute; Cycles adds the Bevel node's edges).
"""
from __future__ import annotations

import math
import os

import bpy
import numpy as np
from bpy.props import EnumProperty, FloatProperty, FloatVectorProperty, PointerProperty, StringProperty

KEY = 'mch_mech'                    # the material's settings (PropertyGroup on bpy.types.Material)
CURV = 'mch_curv'
VERSION = 4                          # (the node tree's layout: an older one is made anew)
MAP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mech_maps')

# slot -> (label, tiles per unit (x Map Scale), colour map (sRGB) or data, [(id, label)])
MAPS = {
    'base': ('Base', 1.5, True, [('FLAT', 'Flat'), ('MOTTLED', 'Mottled'), ('BRUSHED', 'Brushed'),
                                 ('CAST', 'Cast / Pitted'), ('FORGED', 'Forged'), ('HEAT', 'Heat Tint'),
                                 ('PATINA', 'Patina'), ('PEEL', 'Orange Peel'), ('CARBON', 'Carbon Fibre'),
                                 ('CAMO', 'Camo')]),
    'rough': ('Roughness', 1.5, False, [('CLEAN', 'Clean'), ('FINE', 'Fine Noise'), ('SMUDGE', 'Smudges'),
                                        ('FINGER', 'Fingerprints'), ('BRUSHED', 'Brushed'), ('PATCHY', 'Patchy'),
                                        ('GRUNGE', 'Grunge'), ('WATER', 'Water Spots'), ('STREAKS', 'Rain Streaks'),
                                        ('WORN', 'Worn Polish')]),
    'chip': ('Chips', 1.5, False, [('SOFT', 'Soft Wear'), ('FLAKES', 'Flakes'), ('BIG', 'Big Chips'),
                                   ('DOTS', 'Dots'), ('CRACKED', 'Cracked'), ('PEEL', 'Peeling'),
                                   ('SCUFF', 'Scuffs'), ('GRAIN', 'Fine Grain'), ('BLOTCH', 'Blotches'),
                                   ('EDGE', 'Edges Only')]),
    'scratch': ('Scratches', 0.9, False, [('FINE', 'Fine'), ('LONG', 'Long Lines'), ('CROSS', 'Cross Hatch'),
                                          ('RANDOM', 'Random'), ('DEEP', 'Deep Gouges'), ('SWIRL', 'Swirls'),
                                          ('SCUFFED', 'Scuffed'), ('VERTICAL', 'Vertical'), ('CLAW', 'Claw Marks'),
                                          ('MICRO', 'Micro')]),
    'rust': ('Rust', 1.5, True, [('SPOTS', 'Spots'), ('PATCHES', 'Patches'), ('STREAKS', 'Run Streaks'),
                                 ('PITTED', 'Pitted'), ('FLAKY', 'Flaky'), ('HEAVY', 'Heavy'), ('EDGES', 'At Edges'),
                                 ('BLOOM', 'Bloom'), ('FINE', 'Fine Dust'), ('WATERLINE', 'Water Line')]),
    'dirt': ('Dirt', 1.2, False, [('DUST', 'Dust'), ('MUD', 'Mud'), ('SPLASH', 'Splashes'), ('GRIME', 'Grime'),
                                  ('STREAKS', 'Drips'), ('SOOT', 'Soot'), ('OIL', 'Oil Stains'), ('SAND', 'Sand'),
                                  ('CAKED', 'Caked'), ('SMEAR', 'Smears')]),
    'snow': ('Snow', 1.0, False, [('POWDER', 'Powder'), ('PATCHY', 'Patchy'), ('FROST', 'Frost'),
                                  ('DRIFT', 'Drifts'), ('CRUST', 'Crust'), ('SLUSH', 'Slush'), ('FLAKES', 'Flakes'),
                                  ('HEAVY', 'Heavy'), ('ICE', 'Ice'), ('WIND', 'Wind Blown')]),
    'emit': ('Emission', 1.5, False, [('FULL', 'Whole'), ('EDGES', 'Edges'), ('CREVICES', 'Panel Lines'),
                                      ('SCRATCH', 'Scratches'), ('STRIPES', 'Stripes'), ('GRID', 'Grid Lines'),
                                      ('CIRCUIT', 'Circuit'), ('DOTS', 'Dots'), ('HEX', 'Hex Grid'),
                                      ('CRACKS', 'Glowing Cracks')]),
    'weave': ('Weave', 2.0, False, [('CANVAS', 'Canvas'), ('DENIM', 'Denim'), ('NYLON', 'Nylon'),
                                    ('RIPSTOP', 'Ripstop'), ('WOOL', 'Wool'), ('FELT', 'Felt'),
                                    ('QUILT', 'Quilted'), ('LEATHER', 'Leather'), ('KNIT', 'Knit'),
                                    ('MESH', 'Mesh Net')]),
}
MAP_KEYS = tuple(MAPS)
# what each emission map glows on: (constant, edges, crevices, scratches, its own image)
# maps the material always uses (not stepped): dust on what faces up, grime streaks down the walls, a broad colour
# variation - (slot, map, tiles per unit)
FIXED = {'dust': ('dirt', 'DUST', 1.0), 'streak': ('dirt', 'STREAKS', 1.0), 'vary': ('rough', 'PATCHY', 0.35)}
EMIT_SOURCE = {'FULL': (1, 0, 0, 0, 0), 'EDGES': (0, 1, 0, 0, 0), 'CREVICES': (0, 0, 1, 0, 0),
               'SCRATCH': (0, 0, 0, 1, 0)}

# ---- material presets: every slider + the maps
BASE = dict(base_color=(0.77, 0.78, 0.78), metallic=1.0, roughness=0.35, rough_amount=0.35, paint=0.0,
            paint_color=(0.55, 0.06, 0.04), paint_rough=0.45, edge_wear=0.0, scratches=0.0, rust=0.0,
            rust_scratch=0.0, rust_color=(1.0, 1.0, 1.0), dirt=0.0, dirt_color=(0.16, 0.12, 0.08), snow=0.0,
            emission=0.0, emit_color=(0.1, 0.7, 1.0), cloth=0.0, bump=1.0, coat=0.0, ao=0.5,
            h_base=0.3, h_scratch=0.6, h_chip=0.5, h_rust=0.6, h_dirt=0.4, h_snow=0.7, h_weave=0.7,
            aniso=0.0, dust=0.0, streaks=0.0, variation=0.3,
            base_map='MOTTLED', rough_map='SMUDGE', chip_map='FLAKES', scratch_map='FINE', rust_map='PATCHES',
            dirt_map='GRIME', snow_map='POWDER', emit_map='EDGES', weave_map='CANVAS')


def _lin(c):
    """A colour picked on screen (sRGB) as the scene-linear value Blender's colour properties hold."""
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)


BASE = {k: (_lin(v) if k.endswith('color') else v) for k, v in BASE.items()}


def _m(**kw):
    d = dict(BASE)
    d.update({k: (_lin(v) if k.endswith('color') else v) for k, v in kw.items()})
    return d


PRESETS = [
    ('PLASTIC', 'Glossy Plastic', _m(coat=0.3, h_base=0.15, variation=0.1, base_color=(0.85, 0.85, 0.82), metallic=0.0,
                                     roughness=0.25, rough_amount=0.15, base_map='FLAT', rough_map='FINE')),
    ('PLASTIC_MATTE', 'Matte Plastic', _m(h_base=0.3, base_color=(0.12, 0.13, 0.14), metallic=0.0, roughness=0.6,
                                          rough_amount=0.25, base_map='FLAT', rough_map='GRUNGE')),
    ('RUBBER', 'Rubber', _m(h_base=0.4, base_color=(0.04, 0.04, 0.045), metallic=0.0, roughness=0.85, rough_amount=0.2,
                            base_map='FLAT', rough_map='FINE')),
    ('STEEL', 'Steel', _m(h_base=0.25, base_color=(0.77, 0.78, 0.78), roughness=0.3, base_map='MOTTLED',
                          rough_map='SMUDGE')),
    ('BRUSHED', 'Brushed Aluminium', _m(h_base=0.1, aniso=0.75, base_color=(0.91, 0.92, 0.92), roughness=0.3,
                                        rough_amount=0.45, base_map='BRUSHED', rough_map='BRUSHED')),
    ('GUNMETAL', 'Gunmetal', _m(h_base=0.2, coat=0.15, base_color=(0.42, 0.43, 0.45), roughness=0.38,
                                base_map='MOTTLED', rough_map='FINGER')),
    ('CAST', 'Cast Iron', _m(h_base=0.9, bump=1.2, dust=0.25, base_color=(0.62, 0.62, 0.62), roughness=0.65,
                             rough_amount=0.45, base_map='CAST', rough_map='GRUNGE')),
    ('FORGED', 'Forged Steel', _m(h_base=1.0, bump=1.2, base_color=(0.7, 0.7, 0.71), roughness=0.4, base_map='FORGED',
                                  rough_map='WORN')),
    ('HEAT', 'Exhaust Metal', _m(h_base=0.2, streaks=0.3, base_color=(0.8, 0.78, 0.75), roughness=0.35, base_map='HEAT',
                                 rough_map='SMUDGE')),
    ('BRASS', 'Brass', _m(h_base=0.3, base_color=(0.96, 0.88, 0.62), roughness=0.3, base_map='MOTTLED',
                          rough_map='SMUDGE')),
    ('COPPER', 'Copper Patina', _m(h_base=0.6, base_color=(0.98, 0.8, 0.72), roughness=0.35, base_map='PATINA',
                                   rough_map='PATCHY')),
    ('CARBON', 'Carbon Fibre', _m(coat=1.0, h_base=0.5, base_color=(0.3, 0.3, 0.32), metallic=0.0, roughness=0.2,
                                  base_map='CARBON', rough_map='CLEAN')),
    ('PAINTED', 'Painted Metal', _m(coat=0.35, h_base=0.25, paint=1.0, paint_color=(0.62, 0.62, 0.6), paint_rough=0.42,
                                    base_map='PEEL', rough_map='FINE')),
    ('CAMO', 'Camo Paint', _m(h_base=0.2, paint=1.0, paint_color=(0.36, 0.4, 0.26), paint_rough=0.6, base_map='CAMO',
                              rough_map='GRUNGE', edge_wear=0.15)),
    ('CHIPPED', 'Chipped Paint', _m(coat=0.2, h_chip=0.7, paint=1.0, paint_color=(0.75, 0.55, 0.08), edge_wear=0.35,
                                    chip_map='FLAKES', scratches=0.15)),
    ('SCRATCHED', 'Scratched Metal', _m(h_scratch=0.7, roughness=0.32, scratches=0.6, scratch_map='RANDOM',
                                        rough_map='SMUDGE')),
    ('RUSTY', 'Rusty Scratches', _m(h_rust=0.7, paint=1.0, paint_color=(0.2, 0.28, 0.2), edge_wear=0.25, scratches=0.55,
                                    rust=0.15, rust_scratch=0.85, scratch_map='FINE', rust_map='SPOTS')),
    ('RUSTED', 'Rusted Steel', _m(h_rust=0.9, bump=1.3, base_color=(0.5, 0.5, 0.5), roughness=0.6, rust=0.7,
                                  rust_map='HEAVY', dirt=0.3, streaks=0.5)),
    ('DIRTY', 'Dirty Metal', _m(h_dirt=0.5, roughness=0.45, dirt=0.55, dirt_map='GRIME', scratches=0.2, streaks=0.45,
                                dust=0.35)),
    ('MUDDY', 'Muddy Paint', _m(h_dirt=0.9, bump=1.2, dust=0.25, paint=1.0, paint_color=(0.35, 0.38, 0.28),
                                edge_wear=0.2, dirt=0.75, dirt_map='MUD')),
    ('SNOWY', 'Snowy Metal', _m(h_snow=0.9, paint=1.0, paint_color=(0.18, 0.2, 0.24), edge_wear=0.15, snow=0.55,
                                snow_map='PATCHY')),
    ('BATTLE', 'Battle Worn', _m(bump=1.2, paint=1.0, paint_color=(0.42, 0.45, 0.4), edge_wear=0.4, scratches=0.45,
                                 rust=0.25, rust_scratch=0.6, dirt=0.4, chip_map='BIG', streaks=0.35, dust=0.25)),
    ('EMISSIVE', 'Emissive Panel', _m(coat=0.2, paint=1.0, paint_color=(0.08, 0.09, 0.1), emission=6.0,
                                      emit_color=(0.1, 0.75, 1.0), emit_map='CREVICES')),
    ('CIRCUIT', 'Glowing Circuit', _m(coat=0.3, paint=1.0, paint_color=(0.05, 0.06, 0.07), emission=5.0,
                                      emit_color=(0.2, 1.0, 0.4), emit_map='CIRCUIT')),
    ('GLOW_SCRATCH', 'Glowing Scratches', _m(paint=1.0, paint_color=(0.1, 0.1, 0.11), scratches=0.5, emission=8.0,
                                             emit_color=(1.0, 0.35, 0.05), emit_map='SCRATCH')),
    ('CLOTH', 'Cloth Canvas', _m(h_weave=0.9, base_color=(0.36, 0.33, 0.24), metallic=0.0, roughness=0.8,
                                 rough_amount=0.2, cloth=1.0, base_map='FLAT', weave_map='CANVAS')),
    ('CLOTH_DENIM', 'Cloth Denim', _m(h_weave=0.9, base_color=(0.12, 0.17, 0.3), metallic=0.0, roughness=0.75,
                                      cloth=1.0, base_map='MOTTLED', weave_map='DENIM')),
    ('CLOTH_NYLON', 'Cloth Nylon', _m(h_weave=0.7, base_color=(0.08, 0.09, 0.1), metallic=0.0, roughness=0.55,
                                      cloth=1.0, base_map='FLAT', weave_map='RIPSTOP')),
    ('CLOTH_PADDED', 'Cloth Padded', _m(h_weave=1.0, bump=1.5, base_color=(0.25, 0.28, 0.2), metallic=0.0,
                                        roughness=0.75, cloth=1.0, base_map='FLAT', weave_map='QUILT', dirt=0.25,
                                        dirt_map='DUST')),
    ('LEATHER', 'Leather', _m(h_weave=0.8, base_color=(0.22, 0.12, 0.07), metallic=0.0, roughness=0.55, cloth=0.6,
                              base_map='MOTTLED', weave_map='LEATHER')),
]
PRESET_IDS = tuple(p[0] for p in PRESETS)
SLIDERS = tuple(k for k in BASE if not k.endswith('_map'))
MAP_PROPS = {k: k + '_map' for k in MAP_KEYS}
_SYNCING = [False]


def map_path(slot, ident):
    """The file of map ``ident`` of ``slot`` (.png or .jpg) - None when missing."""
    for ext in ('.png', '.jpg'):
        p = os.path.join(MAP_DIR, slot, ident + ext)
        if os.path.isfile(p):
            return p
    return None


def map_image(slot, ident, mask=False, data=False):
    """The map as a Blender image (loaded once, shared), colour space set: data maps Non-Color."""
    p = map_path(slot, ident + ('_mask' if mask else ''))
    if p is None:
        return None
    img = bpy.data.images.load(p, check_existing=True)
    want = 'sRGB' if (MAPS[slot][2] and not mask and not data) else 'Non-Color'
    try:
        if img.colorspace_settings.name != want:
            img.colorspace_settings.name = want
    except TypeError:
        pass
    return img


# -----------------------------------------------------------------------------
# a tiny node graph builder
# -----------------------------------------------------------------------------

class Builder:
    def __init__(self, nt):
        self.nt = nt
        self.n = 0

    def node(self, kind, name=None):
        nd = self.nt.nodes.new(kind)
        nd.location = (200 * (self.n % 12), -160 * (self.n // 12))
        self.n += 1
        if name:
            nd.name = nd.label = name
        return nd

    def link(self, out, inp):
        self.nt.links.new(out, inp)

    def put(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.link(v, sock)
        elif v is not None:
            sock.default_value = v

    def math(self, op, a, b=None, clamp=False):
        nd = self.node('ShaderNodeMath')
        nd.operation = op
        nd.use_clamp = clamp
        self.put(nd.inputs[0], a)
        if b is not None:
            self.put(nd.inputs[1], b)
        return nd.outputs[0]

    def vmath(self, op, a, b=None, fac=None):
        nd = self.node('ShaderNodeVectorMath')
        nd.operation = op
        self.put(nd.inputs[0], a)
        if b is not None:
            self.put(nd.inputs[1], b)
        if fac is not None:
            self.put(nd.inputs['Scale'], fac)
        if op in {'DOT_PRODUCT', 'LENGTH', 'DISTANCE'}:
            return nd.outputs['Value']
        return nd.outputs['Vector']

    def _mix(self, kind, fac, a, b, blend='MIX'):
        nd = self.node('ShaderNodeMix')
        nd.data_type = kind
        nd.clamp_factor = True
        if kind == 'RGBA':
            nd.blend_type = blend
        sock = {s.identifier: s for s in nd.inputs}
        suffix = 'Float' if kind == 'FLOAT' else 'Color'
        self.put(sock['Factor_Float'], fac)
        self.put(sock['A_' + suffix], a)
        self.put(sock['B_' + suffix], b)
        return next(s for s in nd.outputs if s.identifier == 'Result_' + suffix)

    def mixf(self, fac, a, b):
        return self._mix('FLOAT', fac, a, b)

    def mixc(self, fac, a, b, blend='MIX'):
        return self._mix('RGBA', fac, a, b, blend)

    def maprange(self, v, lo, hi, to_lo=0.0, to_hi=1.0):
        nd = self.node('ShaderNodeMapRange')
        nd.clamp = True
        self.put(nd.inputs['Value'], v)
        self.put(nd.inputs[1], lo)
        self.put(nd.inputs[2], hi)
        self.put(nd.inputs[3], to_lo)
        self.put(nd.inputs[4], to_hi)
        return nd.outputs['Result']

    def value(self, name, v=0.0):
        nd = self.node('ShaderNodeValue', 'mch:' + name)
        nd.outputs[0].default_value = v
        return nd.outputs[0]

    def rgb(self, name, c=(1.0, 1.0, 1.0)):
        nd = self.node('ShaderNodeRGB', 'mch:' + name)
        nd.outputs[0].default_value = (*c, 1.0)
        return nd.outputs[0]

    def image(self, name, vector):
        """A box-projected map (its image is set by ``sync``)."""
        nd = self.node('ShaderNodeTexImage', 'mch:img:' + name)
        nd.projection = 'BOX'
        nd.projection_blend = 0.3
        nd.extension = 'REPEAT'
        nd.interpolation = 'Linear'
        self.link(vector, nd.inputs['Vector'])
        return nd

    def threshold(self, v, amount, soft):
        """Nothing (amount 0) .. everything (amount 1): ``v`` (0..1) cut at 1 - amount, ``soft`` wide.  ``v`` is
        squeezed under 1 - soft first, so amount 0 really is none."""
        v = self.math('MULTIPLY', v, 1.0 - soft - 1e-3, clamp=True)
        top = self.math('SUBTRACT', 1.0, amount)
        return self.maprange(v, self.math('SUBTRACT', top, soft), top)


# -----------------------------------------------------------------------------
# the material
# -----------------------------------------------------------------------------

def build(mat):
    """The Mech Shader node tree in ``mat`` (made anew)."""
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    b = Builder(nt)
    out = b.node('ShaderNodeOutputMaterial')
    bsdf = b.node('ShaderNodeBsdfPrincipled', 'mch:bsdf')
    b.link(bsdf.outputs['BSDF'], out.inputs['Surface'])
    tc = b.node('ShaderNodeTexCoord')
    gscale = b.value('map_scale', 1.0)
    maps = {}
    for slot in MAP_KEYS:
        sc = b.math('MULTIPLY', gscale, MAPS[slot][1])
        sc.node.name = 'mch:scale:' + slot
        vec = b.vmath('SCALE', tc.outputs['Object'], fac=sc)
        maps[slot] = b.image(slot, vec)
        if slot == 'rust':
            maps['rust_mask'] = b.image('rust_mask', vec)
        if slot == 'base':
            maps['base_h'] = b.image('base_h', vec)
    for name, (slot, _ident, tiles) in FIXED.items():         # (dust, grime streaks, colour variation: one map each)
        sc = b.math('MULTIPLY', gscale, tiles)
        sc.node.name = 'mch:scale:' + name
        maps[name] = b.image(name, b.vmath('SCALE', tc.outputs['Object'], fac=sc))
    img = {k: nd.outputs['Color'] for k, nd in maps.items()}
    v = {k: b.value(k) for k in ('metallic', 'roughness', 'rough_amount', 'paint', 'paint_rough', 'edge_wear',
                                 'scratches', 'rust', 'rust_scratch', 'dirt', 'snow', 'emission', 'cloth', 'bump',
                                 'edge_width', 'coat', 'ao', 'h_base', 'h_scratch', 'h_chip', 'h_rust', 'h_dirt',
                                 'h_snow', 'h_weave', 'aniso', 'dust', 'streaks', 'variation')}
    c = {k: b.rgb(k) for k in ('base_color', 'paint_color', 'rust_color', 'dirt_color', 'emit_color')}
    w = {k: b.value('emit_w_' + k) for k in ('const', 'edge', 'cav', 'scratch', 'pattern')}
    # edges / crevices: the mesh's convexity (mch_curv) + Cycles' Bevel normal
    att = b.node('ShaderNodeAttribute', 'mch:curv')
    att.attribute_type = 'GEOMETRY'
    att.attribute_name = CURV
    curv = att.outputs['Factor']
    geo = b.node('ShaderNodeNewGeometry')
    bev = b.node('ShaderNodeBevel', 'mch:bevel')
    bev.samples = 8
    b.put(bev.inputs['Radius'], v['edge_width'])
    bev_edge = b.math('MULTIPLY', b.math('SUBTRACT', 1.0, b.vmath('DOT_PRODUCT', bev.outputs['Normal'],
                                                                  geo.outputs['Normal'])), 12.0, clamp=True)
    edge = b.math('MAXIMUM', b.math('MULTIPLY', curv, 1.0, clamp=True), bev_edge)
    cav = b.math('MULTIPLY', curv, -1.0, clamp=True)
    aon = b.node('ShaderNodeAmbientOcclusion', 'mch:ao_node')
    aon.samples = 16
    aon.inputs['Distance'].default_value = 0.15
    occl = b.maprange(aon.outputs['AO'], 0.95, 0.35)                      # (open 0 .. tucked in 1)
    cav = b.math('MAXIMUM', cav, b.math('MULTIPLY', occl, v['ao']))
    up = b.node('ShaderNodeSeparateXYZ')
    b.link(geo.outputs['Normal'], up.inputs['Vector'])
    nz = up.outputs['Z']
    # masks
    chip = b.threshold(b.math('ADD', b.math('MULTIPLY', edge, 0.65), b.math('MULTIPLY', img['chip'], 0.35),
                              clamp=True), v['edge_wear'], 0.04)
    scratch = b.threshold(img['scratch'], b.math('MULTIPLY', v['scratches'], 0.75), 0.05)
    bare = b.math('MAXIMUM', chip, scratch)
    paint = b.math('MULTIPLY', v['paint'], b.math('SUBTRACT', 1.0, bare), clamp=True)
    # (the rust's edge broken up by the fine dust map: real rust eats in ragged, not in clean blobs)
    rust_base = b.threshold(b.math('ADD', b.math('ADD', b.math('MULTIPLY', cav, 0.5),
                                                 b.math('MULTIPLY', img['rust_mask'], 0.6)),
                                   b.math('MULTIPLY', b.math('SUBTRACT', img['dust'], 0.5), 0.3), clamp=True),
                            v['rust'], 0.12)
    rust_in = b.math('MULTIPLY', b.math('MULTIPLY', bare, v['rust_scratch']),
                     b.math('ADD', 0.45, b.math('MULTIPLY', img['rust_mask'], 0.55)), clamp=True)
    rust = b.math('MAXIMUM', rust_base, rust_in)
    dirt = b.math('MULTIPLY', b.threshold(b.math('ADD', b.math('MULTIPLY', cav, 0.55),
                                                 b.math('MULTIPLY', img['dirt'], 0.6), clamp=True),
                                          v['dirt'], 0.12), 0.92)
    snow = b.threshold(b.math('ADD', b.math('MULTIPLY', nz, 0.8), b.math('MULTIPLY', img['snow'], 0.3), clamp=True),
                       b.math('MULTIPLY', v['snow'], 1.1), 0.06)
    side = b.math('SUBTRACT', 1.0, b.math('ABSOLUTE', nz))                # (walls 1, floors / tops 0)
    streak = b.threshold(b.math('MULTIPLY', b.math('ADD', b.math('MULTIPLY', img['streak'], 0.85),
                                                   b.math('MULTIPLY', cav, 0.3)), side, clamp=True),
                         v['streaks'], 0.25)
    streak = b.math('MULTIPLY', streak, b.math('SUBTRACT', 1.0, snow))
    dust = b.threshold(b.math('ADD', b.math('MULTIPLY', b.math('MAXIMUM', nz, 0.0), 0.6),
                              b.math('MULTIPLY', img['dust'], 0.5), clamp=True), v['dust'], 0.2)
    dust = b.math('MULTIPLY', b.math('MULTIPLY', dust, 0.85), b.math('SUBTRACT', 1.0, snow))
    worn = b.math('MULTIPLY', b.math('MULTIPLY', edge, v['edge_wear']), b.math('SUBTRACT', 1.0, paint))
    cloth = v['cloth']
    weave = img['weave']
    # colour: base x its map (the map is about 0.5 grey: x2), scratches bright, paint, rust, dirt, snow
    base_col = b.vmath('SCALE', b.mixc(1.0, c['base_color'], img['base'], 'MULTIPLY'), fac=2.0)
    base_col = b.mixc(b.math('MULTIPLY', scratch, v['metallic']), base_col,
                      b.mixc(0.4, base_col, (1.0, 1.0, 1.0, 1.0)))
    base_col = b.mixc(b.math('MULTIPLY', cloth, 0.45), base_col,
                      b.mixc(weave, b.mixc(0.5, base_col, (0.0, 0.0, 0.0, 1.0)), base_col))
    paint_col = b.mixc(0.35, c['paint_color'],
                       b.vmath('SCALE', b.mixc(1.0, c['paint_color'], img['base'], 'MULTIPLY'), fac=2.0))
    col = b.mixc(paint, base_col, paint_col)
    rust_col = b.mixc(1.0, img['rust'], c['rust_color'], 'MULTIPLY')
    col = b.mixc(rust, col, rust_col)
    col = b.mixc(dirt, col, b.mixc(0.5, c['dirt_color'], b.mixc(1.0, c['dirt_color'], img['dirt'], 'MULTIPLY')))
    # (worn edges of bare metal polished a little brighter; the whole surface a little uneven - nothing is one colour)
    col = b.mixc(b.math('MULTIPLY', worn, b.math('MULTIPLY', v['metallic'], 0.35)), col,
                 b.vmath('SCALE', col, fac=1.35))
    col = b.vmath('SCALE', col, fac=b.math('ADD', 1.0, b.math('MULTIPLY', b.math('SUBTRACT', img['vary'], 0.5),
                                                              b.math('MULTIPLY', v['variation'], 1.2))))
    streak_col = b.mixc(b.math('MULTIPLY', v['rust'], 1.5), b.vmath('SCALE', c['dirt_color'], fac=4.0),
                        b.mixc(1.0, _lin((0.5, 0.24, 0.1)) + (1.0,), c['rust_color'], 'MULTIPLY'))
    col = b.mixc(b.math('MULTIPLY', streak, 0.6), col, b.mixc(1.0, col, streak_col, 'MULTIPLY'))
    col = b.mixc(dust, col, _lin((0.6, 0.57, 0.52)) + (1.0,))
    col = b.mixc(snow, col, (0.88, 0.9, 0.94, 1.0))
    b.link(col, bsdf.inputs['Base Color'])
    keep = b.math('MULTIPLY', b.math('SUBTRACT', 1.0, paint),
                  b.math('MULTIPLY', b.math('SUBTRACT', 1.0, rust),
                         b.math('MULTIPLY', b.math('SUBTRACT', 1.0, dirt), b.math('SUBTRACT', 1.0, snow))))
    keep = b.math('MULTIPLY', keep, b.math('SUBTRACT', 1.0, b.math('MAXIMUM', dust, b.math('MULTIPLY', streak, 0.5))))
    b.link(b.math('MULTIPLY', b.math('MULTIPLY', v['metallic'], keep), b.math('SUBTRACT', 1.0, cloth)),
           bsdf.inputs['Metallic'])
    # roughness: the base + its map, the paint's own, rougher scratches, rust / dirt / snow, cloth
    var = b.math('MULTIPLY', v['rough_amount'], b.math('SUBTRACT', img['rough'], 0.5))
    r = b.math('ADD', v['roughness'], var, clamp=True)
    r = b.mixf(paint, r, b.math('ADD', v['paint_rough'], b.math('MULTIPLY', var, 0.5), clamp=True))
    r = b.math('ADD', r, b.math('MULTIPLY', scratch, 0.18), clamp=True)
    r = b.math('SUBTRACT', r, b.math('MULTIPLY', worn, 0.2), clamp=True)          # (rubbed edges: polished)
    r = b.mixf(rust, r, b.math('ADD', 0.72, b.math('MULTIPLY', img['rust_mask'], 0.25)))
    r = b.mixf(dirt, r, 0.93)
    r = b.mixf(b.math('MULTIPLY', streak, 0.6), r, 0.8)
    r = b.mixf(dust, r, 0.92)
    r = b.mixf(snow, r, 0.55)
    r = b.mixf(b.math('MULTIPLY', cloth, 0.6), r, b.math('ADD', 0.7, b.math('MULTIPLY', weave, 0.25)))
    b.link(r, bsdf.inputs['Roughness'])
    b.put(bsdf.inputs['Sheen Weight'], b.math('MULTIPLY', cloth, 0.45))
    bsdf.inputs['Sheen Roughness'].default_value = 0.5
    unbroken = b.math('MULTIPLY', b.math('SUBTRACT', 1.0, scratch),
                      b.math('MULTIPLY', b.math('SUBTRACT', 1.0, rust),
                             b.math('MULTIPLY', b.math('SUBTRACT', 1.0, dirt), b.math('SUBTRACT', 1.0, snow))))
    unbroken = b.math('MULTIPLY', unbroken, b.math('SUBTRACT', 1.0, b.math('MAXIMUM', dust, streak)))
    b.link(b.math('MULTIPLY', v['coat'], unbroken), bsdf.inputs['Coat Weight'])
    # brushed metal: the highlight stretched across the brush lines.  The maps' lines run along the image's v, which
    # box projection lays along z on the walls and along x on top: the tangent is the image's u (object y, or x on
    # the walls facing y), taken to world space
    on = b.node('ShaderNodeSeparateXYZ')
    b.link(tc.outputs['Normal'], on.inputs['Vector'])
    ay = b.math('ABSOLUTE', on.outputs['Y'])
    faces_y = b.math('MULTIPLY', b.math('GREATER_THAN', ay, b.math('ABSOLUTE', on.outputs['X'])),
                     b.math('GREATER_THAN', ay, b.math('ABSOLUTE', on.outputs['Z'])))
    tan = b.node('ShaderNodeVectorTransform', 'mch:tangent')
    tan.vector_type, tan.convert_from, tan.convert_to = 'VECTOR', 'OBJECT', 'WORLD'
    b.link(b.mixc(faces_y, (0.0, 1.0, 0.0, 1.0), (1.0, 0.0, 0.0, 1.0)), tan.inputs['Vector'])
    b.link(tan.outputs['Vector'], bsdf.inputs['Tangent'])
    b.link(b.math('MULTIPLY', v['aniso'], b.math('MULTIPLY', b.math('SUBTRACT', 1.0, paint), keep)),
           bsdf.inputs['Anisotropic'])
    b.link(b.math('ADD', 0.04, b.math('MULTIPLY', var, 0.3), clamp=True), bsdf.inputs['Coat Roughness'])
    # relief: scratches / chips cut in, rust / snow / weave stand out, the roughness map a little
    # relief: every layer its own height (the Base map's height map, scratches / chips cut in, rust / dirt / snow /
    # weave stand out), all x Height
    h = b.math('MULTIPLY', b.math('SUBTRACT', img['base_h'], 0.5), v['h_base'])
    h = b.math('ADD', h, b.math('MULTIPLY', scratch, b.math('MULTIPLY', v['h_scratch'], -1.0)))
    h = b.math('ADD', h, b.math('MULTIPLY', b.math('MULTIPLY', chip, b.math('ADD', 0.3, b.math('MULTIPLY', v['paint'],
                                                                                            0.7))),
                                b.math('MULTIPLY', v['h_chip'], -1.0)))
    h = b.math('ADD', h, b.math('MULTIPLY', b.math('MULTIPLY', rust, b.math('ADD', img['rust_mask'], 0.2)),
                                v['h_rust']))
    h = b.math('ADD', h, b.math('MULTIPLY', b.math('MULTIPLY', dirt, b.math('ADD', img['dirt'], 0.3)), v['h_dirt']))
    h = b.math('ADD', h, b.math('MULTIPLY', b.math('MULTIPLY', snow, b.math('ADD', b.math('MULTIPLY', img['snow'], 0.5),
                                                                        0.6)), v['h_snow']))
    h = b.math('ADD', h, b.math('MULTIPLY', b.math('MULTIPLY', cloth, weave), v['h_weave']))
    h = b.math('ADD', h, b.math('MULTIPLY', dust, b.math('MULTIPLY', img['dust'], 0.25)))
    bump = b.node('ShaderNodeBump', 'mch:bumpnode')
    b.put(bump.inputs['Strength'], b.math('MINIMUM', v['bump'], 1.0))
    bump.inputs['Distance'].default_value = 0.004
    b.link(b.math('MULTIPLY', h, b.math('MAXIMUM', v['bump'], 1.0)), bump.inputs['Height'])
    b.link(bump.outputs['Normal'], bsdf.inputs['Normal'])
    # emission: the map's mask (constant / edges / crevices / scratches / its own image)
    em = b.math('ADD', b.math('ADD', w['const'], b.math('MULTIPLY', w['edge'], edge)),
                b.math('ADD', b.math('MULTIPLY', w['cav'], cav),
                       b.math('ADD', b.math('MULTIPLY', w['scratch'], scratch),
                              b.math('MULTIPLY', w['pattern'], img['emit']))), clamp=True)
    b.link(c['emit_color'], bsdf.inputs['Emission Color'])
    b.link(b.math('MULTIPLY', em, v['emission']), bsdf.inputs['Emission Strength'])
    mat['mch_mech'] = VERSION
    return mat


def is_mech(mat):
    return mat is not None and bool(mat.get('mch_mech')) and mat.node_tree is not None \
        and mat.node_tree.nodes.get('mch:bsdf') is not None


def sync(mat):
    """The material's settings written into its nodes (a slider moved / a map stepped: at once)."""
    if not is_mech(mat):
        return
    if mat.get('mch_mech', 0) < VERSION:                          # (an older Mech Shader: made anew)
        build(mat)
    st = getattr(mat, KEY)
    nodes = mat.node_tree.nodes

    def setv(name, val):
        nd = nodes.get('mch:' + name)
        if nd is not None:
            nd.outputs[0].default_value = (*val, 1.0) if isinstance(val, tuple) else val
    for k in SLIDERS:
        val = getattr(st, k)
        setv(k, tuple(val) if k.endswith('color') else float(val))
    setv('map_scale', float(st.map_scale))
    setv('edge_width', float(st.edge_width))
    for slot in MAP_KEYS:
        ident = getattr(st, MAP_PROPS[slot])
        nd = nodes.get('mch:img:' + slot)
        if nd is not None:
            img = map_image(slot, ident)
            if nd.image != img:
                nd.image = img
        if slot == 'base':
            nd = nodes.get('mch:img:base_h')
            if nd is not None:
                img = map_image('base', ident + '_height', data=True)
                if nd.image != img:
                    nd.image = img
        if slot == 'rust':
            nd = nodes.get('mch:img:rust_mask')
            if nd is not None:
                img = map_image(slot, ident, mask=True)
                if nd.image != img:
                    nd.image = img
    for name, (slot, ident, _tiles) in FIXED.items():
        nd = nodes.get('mch:img:' + name)
        if nd is not None and nd.image is None:
            nd.image = map_image(slot, ident, data=True)
    src = EMIT_SOURCE.get(st.emit_map, (0, 0, 0, 0, 1))
    for k, val in zip(('const', 'edge', 'cav', 'scratch', 'pattern'), src):
        setv('emit_w_' + k, float(val))


def apply_preset(mat, ident):
    """Every slider and map of a material preset (one sync at the end)."""
    spec = next((p[2] for p in PRESETS if p[0] == ident), None)
    if spec is None:
        return False
    st = getattr(mat, KEY)
    _SYNCING[0] = True
    try:
        for k, val in spec.items():
            setattr(st, k, val)
        if st.preset != ident:
            st.preset = ident
    finally:
        _SYNCING[0] = False
    sync(mat)
    return True


# -----------------------------------------------------------------------------
# edges and crevices from the mesh
# -----------------------------------------------------------------------------

WEAR_WIDTH = 0.025          # a rounding this tight (x the mesh's size) counts as a full edge / crevice


SHARP_SIN = 0.34            # an edge leaving a point's tangent plane by more than ~20 degrees: a hard corner


def store_curvature(me, smooth=4, width=WEAR_WIDTH):
    """Each point's convexity (+1 an edge, -1 a crevice, 0 flat or gently curved) into the float point attribute
    ``mch_curv``.  Along each of its edges: a neighbour L away dropping h below the tangent plane bends 2h / L^2
    = 1 / radius, times ``width`` x the mesh's size (a rounding that tight or tighter is a full edge, a big gentle
    dome stays clean), capped at 1 - or a full edge / crevice at once when the edge leaves the plane steeply (a hard
    corner, even on a low-poly part).  Capped per edge BEFORE the average (a tight bevel's huge bend no longer
    outweighs the flat around it), then smoothed ``smooth`` times over neighbours within about the wear width only
    (a long edge of a coarse face passes nothing on - before, a big flat face a few points from its bevel read as all
    edge).  Returns the number of points."""
    nv = len(me.vertices)
    if nv == 0 or not len(me.edges):
        return 0
    co = np.empty(nv * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    nrm = np.empty(nv * 3)
    me.vertex_normals.foreach_get('vector', nrm)
    nrm = nrm.reshape(-1, 3)
    ev = np.empty(len(me.edges) * 2, np.int64)
    me.edges.foreach_get('vertices', ev)
    ev = ev.reshape(-1, 2)
    d = co[ev[:, 1]] - co[ev[:, 0]]
    l2 = np.einsum('ij,ij->i', d, d)
    ok = l2 > 1e-18
    d, ev2, l2 = d[ok], ev[ok], l2[ok]
    ln = np.sqrt(l2)
    size = float(np.linalg.norm(co.max(0) - co.min(0))) or 1.0
    reach = width * size

    def bend(nd):                                     # nd: the neighbour's height over the tangent plane
        k = np.clip(-2.0 * nd / l2 * reach, -1.0, 1.0)
        return np.where(np.abs(nd) > SHARP_SIN * ln, -np.sign(nd), k)
    ka = bend(np.einsum('ij,ij->i', nrm[ev2[:, 0]], d))               # (b below a's tangent plane: convex at a)
    kb = bend(-np.einsum('ij,ij->i', nrm[ev2[:, 1]], d))
    acc = np.zeros(nv)
    cnt = np.zeros(nv)
    np.add.at(acc, ev2[:, 0], ka)
    np.add.at(acc, ev2[:, 1], kb)
    np.add.at(cnt, ev2[:, 0], 1)
    np.add.at(cnt, ev2[:, 1], 1)
    k = np.clip(acc / np.maximum(cnt, 1), -1.0, 1.0)
    w = np.exp(-(ln / reach) ** 2)
    wn = np.zeros(nv)
    np.add.at(wn, ev2[:, 0], w)
    np.add.at(wn, ev2[:, 1], w)
    for _ in range(max(0, int(smooth))):
        s = np.zeros(nv)
        np.add.at(s, ev2[:, 0], w * k[ev2[:, 1]])
        np.add.at(s, ev2[:, 1], w * k[ev2[:, 0]])
        k = (k + s) / (1.0 + wn)
    k = k.astype(np.float32)
    att = me.attributes.get(CURV)
    if att is not None and (att.domain != 'POINT' or att.data_type != 'FLOAT'):
        me.attributes.remove(att)
        att = None
    if att is None:
        att = me.attributes.new(CURV, 'FLOAT', 'POINT')
    att.data.foreach_set('value', k)
    me.update()
    return nv


# -----------------------------------------------------------------------------
# settings
# -----------------------------------------------------------------------------

def _update(self, context):
    if _SYNCING[0]:
        return
    mat = self.id_data
    sync(mat)


def _preset_update(self, context):
    if _SYNCING[0]:
        return
    apply_preset(self.id_data, self.preset)


def _map_items(slot):
    return [(k, label, f'{MAPS[slot][0]} map: {label}') for k, label in MAPS[slot][3]]


def _color(name, default):
    return FloatVectorProperty(name=name, subtype='COLOR', size=3, min=0.0, max=1.0, default=default,
                               update=_update)


def _slider(name, default, lo=0.0, hi=1.0, desc=''):
    return FloatProperty(name=name, default=default, min=lo, max=hi, update=_update, description=desc)


class MCH_PG_MechShader(bpy.types.PropertyGroup):
    preset: EnumProperty(name='Preset', items=[(k, n, n) for k, n, _s in PRESETS], default='STEEL',
                         update=_preset_update)
    base_color: _color('Base Color', BASE['base_color'])
    metallic: _slider('Metallic', 1.0, desc='0 = plastic / paint underneath, 1 = metal')
    roughness: _slider('Roughness', 0.35)
    rough_amount: _slider('Roughness Map', 0.25, desc='How much the roughness map varies the roughness')
    paint: _slider('Paint', 0.0, desc='Paint coverage (0 = bare material)')
    paint_color: _color('Paint Color', BASE['paint_color'])
    paint_rough: _slider('Paint Roughness', 0.45)
    edge_wear: _slider('Edge Wear', 0.0, desc='Paint chipped off the edges (and the Chips map)')
    scratches: _slider('Scratches', 0.0)
    rust: _slider('Rust', 0.0, desc='Rust in the crevices (and the Rust map)')
    rust_scratch: _slider('Rust in Scratches', 0.0, desc='Rust showing in the scratches and chips')
    rust_color: _color('Rust Tint', BASE['rust_color'])
    dirt: _slider('Dirt', 0.0)
    dirt_color: _color('Dirt Color', BASE['dirt_color'])
    snow: _slider('Snow', 0.0, desc='Snow on what faces up')
    emission: _slider('Emission', 0.0, 0.0, 50.0, desc='Glow strength')
    emit_color: _color('Emission Color', BASE['emit_color'])
    cloth: _slider('Cloth', 0.0, desc='Fabric: weave relief + sheen, never metallic')
    bump: _slider('Height', 1.0, 0.0, 4.0, desc='All the bump at once (the layers\' heights below x this)')
    h_base: _slider('Base Height', 0.3, desc='Bump of the Base map\'s own height map (pits, dents, brush lines, '
                                            'orange peel, carbon weave)')
    h_scratch: _slider('Scratch Depth', 0.6, desc='How deep the scratches cut in')
    h_chip: _slider('Chip Depth', 0.5, desc='The paint\'s thickness at the chipped edges')
    h_rust: _slider('Rust Height', 0.6, desc='How much the rust flakes stand out')
    h_dirt: _slider('Dirt Height', 0.4, desc='How thick the dirt / mud is caked on')
    h_snow: _slider('Snow Height', 0.7, desc='How thick the snow lies')
    h_weave: _slider('Weave Height', 0.7, desc='Relief of the cloth weave')
    aniso: _slider('Brushed', 0.0, desc='Anisotropic highlight of bare metal, stretched across the brush lines '
                                        '(Cycles)')
    dust: _slider('Dust', 0.0, desc='Fine dust settled on what faces up')
    streaks: _slider('Grime Streaks', 0.0, desc='Dirt / rust run down the walls (rust tints them)')
    variation: _slider('Variation', 0.3, desc='The surface a little uneven in colour, as nothing real is one colour')
    coat: _slider('Clear Coat', 0.0, desc='A glossy coat over the surface (lacquered paint, carbon), broken by '
                                          'scratches, rust, dirt, snow')
    ao: _slider('Crevice AO', 0.5, desc='Crevices found by ambient occlusion too (dirt / rust gather there)')
    map_scale: _slider('Map Scale', 1.0, 0.05, 20.0, desc='Every map repeated more (bigger number = finer)')
    edge_width: _slider('Edge Width (Cycles)', 0.02, 0.0, 0.5, desc='Cycles: how wide the Bevel finds edges')
    base_map: EnumProperty(name='Base Map', items=_map_items('base'), default='MOTTLED', update=_update)
    rough_map: EnumProperty(name='Roughness Map', items=_map_items('rough'), default='SMUDGE', update=_update)
    chip_map: EnumProperty(name='Chips Map', items=_map_items('chip'), default='FLAKES', update=_update)
    scratch_map: EnumProperty(name='Scratches Map', items=_map_items('scratch'), default='FINE', update=_update)
    rust_map: EnumProperty(name='Rust Map', items=_map_items('rust'), default='PATCHES', update=_update)
    dirt_map: EnumProperty(name='Dirt Map', items=_map_items('dirt'), default='GRIME', update=_update)
    snow_map: EnumProperty(name='Snow Map', items=_map_items('snow'), default='POWDER', update=_update)
    emit_map: EnumProperty(name='Emission Map', items=_map_items('emit'), default='EDGES', update=_update)
    weave_map: EnumProperty(name='Weave Map', items=_map_items('weave'), default='CANVAS', update=_update)


def active_mech(context):
    ob = getattr(context, 'active_object', None)
    mat = getattr(ob, 'active_material', None) if ob is not None else None
    return mat if is_mech(mat) else None


def new_material(preset='STEEL', name=None):
    label = dict((k, n) for k, n, _s in PRESETS).get(preset, preset)
    mat = bpy.data.materials.new(name or 'Mech ' + label)
    build(mat)
    apply_preset(mat, preset)
    return mat


def assign(context, objs, mat, edges=True):
    """``mat`` on every mesh of ``objs`` (its first slot) and their convexity stored.  Returns how many."""
    n = 0
    for ob in objs:
        if ob is None or ob.type != 'MESH':
            continue
        if ob.data.materials:
            ob.data.materials[0] = mat
        else:
            ob.data.materials.append(mat)
        ob.active_material_index = 0
        if edges:
            mode = ob.mode
            try:
                if mode == 'EDIT':
                    bpy.ops.object.mode_set(mode='OBJECT')
                store_curvature(ob.data)
            finally:
                if mode == 'EDIT':
                    bpy.ops.object.mode_set(mode='EDIT')
        n += 1
    return n


def _targets(context):
    obs = [o for o in context.selected_objects if o.type == 'MESH']
    ob = context.active_object
    if ob is not None and ob.type == 'MESH' and ob not in obs:
        obs.append(ob)
    return obs


class MCH_OT_mech_shader_apply(bpy.types.Operator):
    """A new Mech Shader material on the selected meshes (the preset shown), their edges / crevices measured"""
    bl_idname = 'mch.mech_shader_apply'
    bl_label = 'Apply Mech Shader'
    bl_options = {'REGISTER', 'UNDO'}
    preset: StringProperty(default='')

    def execute(self, context):
        obs = _targets(context)
        if not obs:
            self.report({'WARNING'}, 'Mech Shader: select a mesh')
            return {'CANCELLED'}
        cur = active_mech(context)
        preset = self.preset or (getattr(cur, KEY).preset if cur is not None else
                                 context.scene.mch_mech_preset)
        mat = new_material(preset)
        n = assign(context, obs, mat)
        _look(context)
        self.report({'INFO'}, f'Mech Shader "{mat.name}" on {n} mesh(es)')
        return {'FINISHED'}


class MCH_OT_mech_shader_step(bpy.types.Operator):
    """Next / previous preset of this list (the material changes at once)"""
    bl_idname = 'mch.mech_shader_step'
    bl_label = 'Mech Shader Step'
    bl_options = {'REGISTER', 'UNDO'}
    prop: StringProperty(default='preset')
    step: bpy.props.IntProperty(default=1)

    def execute(self, context):
        mat = active_mech(context)
        if mat is None:
            if self.prop != 'preset':
                return {'CANCELLED'}
            ids = PRESET_IDS
            sc = context.scene
            i = ids.index(sc.mch_mech_preset) if sc.mch_mech_preset in ids else 0
            sc.mch_mech_preset = ids[(i + self.step) % len(ids)]
            return bpy.ops.mch.mech_shader_apply(preset=sc.mch_mech_preset) if _targets(context) else {'FINISHED'}
        st = getattr(mat, KEY)
        items = [i.identifier for i in st.bl_rna.properties[self.prop].enum_items]
        cur = getattr(st, self.prop)
        setattr(st, self.prop, items[(items.index(cur) + self.step) % len(items)])
        return {'FINISHED'}


class MCH_OT_mech_shader_edges(bpy.types.Operator):
    """Measure the edges and crevices again (after the mesh changed): edge wear, rust and dirt follow them"""
    bl_idname = 'mch.mech_shader_edges'
    bl_label = 'Update Edges'
    bl_options = {'REGISTER', 'UNDO'}
    smooth: bpy.props.IntProperty(default=4, min=0, max=60)

    def execute(self, context):
        n = 0
        for ob in _targets(context):
            mode = ob.mode
            if mode == 'EDIT':
                bpy.ops.object.mode_set(mode='OBJECT')
            store_curvature(ob.data, smooth=self.smooth)
            if mode == 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')
            n += 1
        self.report({'INFO'}, f'Mech Shader: edges measured on {n} mesh(es)')
        return {'FINISHED'}


def _look(context):
    """The viewport in Material Preview (the shader shows) - only when it is in Solid."""
    for sp in _views(context):
        if sp.shading.type == 'SOLID':
            sp.shading.type = 'MATERIAL'


def _views(context):
    screen = getattr(context, 'screen', None)
    for area in screen.areas if screen else []:
        if area.type == 'VIEW_3D':
            for sp in area.spaces:
                if sp.type == 'VIEW_3D':
                    yield sp


# -----------------------------------------------------------------------------
# HDRI: one of Blender's own studio-light worlds (datafiles/studiolights/world/*.exr) as the scene's world
# -----------------------------------------------------------------------------

WORLD = 'MCH HDRI'
_HDRI_ITEMS = []


def hdri_dir():
    return bpy.utils.system_resource('DATAFILES', path=os.path.join('studiolights', 'world')) or ''


def hdri_files():
    try:
        return sorted(f for f in os.listdir(hdri_dir()) if f.lower().endswith(('.exr', '.hdr')))
    except OSError:
        return []


def _hdri_items(self, context):
    if not _HDRI_ITEMS:                                   # (kept: Blender needs the strings to stay alive)
        _HDRI_ITEMS.extend((f, os.path.splitext(f)[0].title(), f'Blender\'s built-in HDRI {f}')
                           for f in hdri_files())
        if not _HDRI_ITEMS:
            _HDRI_ITEMS.append(('NONE', 'None', 'No built-in HDRI found'))
    return _HDRI_ITEMS


def hdri_world(scene):
    """The scene's world when it is the Mech Shader HDRI, else None."""
    w = scene.world
    return w if w is not None and w.get('mch_hdri') else None


def hdri_sync(scene):
    """The HDRI world's image / strength / rotation from the scene's settings.  Returns the world or None."""
    w = hdri_world(scene)
    if w is None:
        return None
    nt = w.node_tree
    env, bg, mp = nt.nodes.get('mch:env'), nt.nodes.get('mch:bg'), nt.nodes.get('mch:map')
    if env is None or bg is None or mp is None:
        return None
    path = os.path.join(hdri_dir(), scene.mch_mech_hdri)
    if os.path.isfile(path) and (env.image is None or os.path.normcase(bpy.path.abspath(env.image.filepath))
                                 != os.path.normcase(path)):
        env.image = bpy.data.images.load(path, check_existing=True)
    bg.inputs['Strength'].default_value = scene.mch_mech_hdri_strength
    mp.inputs['Rotation'].default_value[2] = scene.mch_mech_hdri_rot
    w.cycles_visibility.camera = scene.mch_mech_hdri_show
    return w


def set_hdri(context):
    """The scene's world becomes the HDRI (the one it had is remembered for Off); Material Preview shows it."""
    sc = context.scene
    path = os.path.join(hdri_dir(), sc.mch_mech_hdri)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    w = hdri_world(sc)
    if w is None:
        w = bpy.data.worlds.get(WORLD)
        if w is None or not w.get('mch_hdri'):
            w = bpy.data.worlds.new(WORLD)
        w['mch_hdri'] = 1
        w['mch_prev_world'] = sc.world.name if sc.world is not None else ''
        w.use_nodes = True
        nt = w.node_tree
        nt.nodes.clear()
        tc = nt.nodes.new('ShaderNodeTexCoord')
        mp = nt.nodes.new('ShaderNodeMapping')
        mp.name = 'mch:map'
        env = nt.nodes.new('ShaderNodeTexEnvironment')
        env.name = 'mch:env'
        bg = nt.nodes.new('ShaderNodeBackground')
        bg.name = 'mch:bg'
        out = nt.nodes.new('ShaderNodeOutputWorld')
        for i, n in enumerate((tc, mp, env, bg, out)):
            n.location = (-900 + 250 * i, 0)
        nt.links.new(tc.outputs['Generated'], mp.inputs['Vector'])
        nt.links.new(mp.outputs['Vector'], env.inputs['Vector'])
        nt.links.new(env.outputs['Color'], bg.inputs['Color'])
        nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
        sc.world = w
    hdri_sync(sc)
    for sp in _views(context):
        if sp.shading.type == 'SOLID':
            sp.shading.type = 'MATERIAL'
        sp.shading.use_scene_world = True
    return w


def hdri_off(context):
    """The world the scene had before Set HDRI back; Material Preview back on its own studio light."""
    sc = context.scene
    w = hdri_world(sc)
    if w is None:
        return False
    sc.world = bpy.data.worlds.get(w.get('mch_prev_world', '')) or None
    for sp in _views(context):
        sp.shading.use_scene_world = False
    return True


def _hdri_update(self, context):
    hdri_sync(context.scene)


class MCH_OT_mech_hdri(bpy.types.Operator):
    """Light the scene with one of Blender's built-in HDRIs (the scene's world becomes it; Off gives the old one
back).  The arrows step to the next HDRI"""
    bl_idname = 'mch.mech_hdri'
    bl_label = 'Set HDRI'
    bl_options = {'REGISTER', 'UNDO'}
    action: EnumProperty(items=[('SET', 'Set', ''), ('OFF', 'Off', '')], default='SET')
    step: bpy.props.IntProperty(default=0)

    def execute(self, context):
        sc = context.scene
        if self.action == 'OFF':
            if not hdri_off(context):
                self.report({'INFO'}, 'HDRI: the scene\'s world is not the Mech Shader HDRI')
            return {'FINISHED'}
        if self.step:
            ids = [i[0] for i in _hdri_items(None, context)]
            cur = sc.mch_mech_hdri
            sc.mch_mech_hdri = ids[((ids.index(cur) if cur in ids else 0) + self.step) % len(ids)]
        try:
            set_hdri(context)
        except FileNotFoundError as ex:
            self.report({'WARNING'}, f'HDRI: not found ({ex})')
            return {'CANCELLED'}
        return {'FINISHED'}


def _row(layout, data, prop, label=None, map_slot=None):
    r = layout.row(align=True)
    r.operator('mch.mech_shader_step', text='', icon='TRIA_LEFT').prop = prop
    op = r.operator('mch.mech_shader_step', text='', icon='TRIA_RIGHT')
    op.prop = prop
    op.step = 1
    r.prop(data, prop, text=label or '')
    return r


def _map_row(layout, st, slot):
    """[<] [>] the map's name: a step swaps the map at once."""
    r = layout.row(align=True)
    a = r.operator('mch.mech_shader_step', text='', icon='TRIA_LEFT')
    a.prop, a.step = MAP_PROPS[slot], -1
    nxt = r.operator('mch.mech_shader_step', text='', icon='TRIA_RIGHT')
    nxt.prop, nxt.step = MAP_PROPS[slot], 1
    r.prop(st, MAP_PROPS[slot], text=MAPS[slot][0])


def draw(layout, context):
    sc = context.scene
    box = layout.box()
    box.label(text='Mech Shader', icon='MATERIAL')
    mat = active_mech(context)
    if mat is None:
        r = box.row(align=True)
        left = r.operator('mch.mech_shader_step', text='', icon='TRIA_LEFT')
        left.prop, left.step = 'preset', -1
        right = r.operator('mch.mech_shader_step', text='', icon='TRIA_RIGHT')
        right.prop, right.step = 'preset', 1
        r.prop(sc, 'mch_mech_preset', text='')
        box.operator('mch.mech_shader_apply', icon='CHECKMARK').preset = ''
        box.label(text='Select meshes, then Apply (or step the preset)')
        return
    st = getattr(mat, KEY)
    r = box.row(align=True)
    left = r.operator('mch.mech_shader_step', text='', icon='TRIA_LEFT')
    left.prop, left.step = 'preset', -1
    right = r.operator('mch.mech_shader_step', text='', icon='TRIA_RIGHT')
    right.prop, right.step = 'preset', 1
    r.prop(st, 'preset', text='')
    box.label(text=mat.name)
    col = box.column(align=True)
    col.prop(st, 'base_color')
    col.prop(st, 'metallic', slider=True)
    col.prop(st, 'roughness', slider=True)
    col.prop(st, 'coat', slider=True)
    col.prop(st, 'aniso', slider=True)
    _map_row(col, st, 'base')
    col.prop(st, 'h_base', slider=True)
    col.prop(st, 'variation', slider=True)
    for slot, amount, extra, height in (
            ('rough', 'rough_amount', (), None),
            ('chip', 'edge_wear', ('paint', 'paint_color', 'paint_rough'), 'h_chip'),
            ('scratch', 'scratches', (), 'h_scratch'), ('rust', 'rust', ('rust_scratch', 'rust_color'), 'h_rust'),
            ('dirt', 'dirt', ('dirt_color', 'dust', 'streaks'), 'h_dirt'), ('snow', 'snow', (), 'h_snow'),
            ('emit', 'emission', ('emit_color',), None), ('weave', 'cloth', (), 'h_weave')):
        sub = box.column(align=True)
        for e in extra:
            sub.prop(st, e, slider=not e.endswith('color'))
        sub.prop(st, amount, slider=True)
        _map_row(sub, st, slot)
        if height:
            sub.prop(st, height, slider=True)
    col = box.column(align=True)
    col.prop(st, 'bump', slider=True)
    col.prop(st, 'ao', slider=True)
    col.prop(st, 'map_scale')
    col.prop(st, 'edge_width')
    r = box.row(align=True)
    r.operator('mch.mech_shader_edges', icon='MOD_EDGESPLIT')
    r.operator('mch.mech_shader_apply', text='New Copy', icon='DUPLICATE').preset = st.preset
    draw_hdri(layout, context)


def draw_hdri(layout, context):
    sc = context.scene
    box = layout.box()
    on = hdri_world(sc) is not None
    box.label(text='HDRI' + (' (on)' if on else ''), icon='WORLD')
    r = box.row(align=True)
    a = r.operator('mch.mech_hdri', text='', icon='TRIA_LEFT')
    a.action, a.step = 'SET', -1
    b = r.operator('mch.mech_hdri', text='', icon='TRIA_RIGHT')
    b.action, b.step = 'SET', 1
    r.prop(sc, 'mch_mech_hdri', text='')
    col = box.column(align=True)
    col.prop(sc, 'mch_mech_hdri_strength')
    col.prop(sc, 'mch_mech_hdri_rot')
    col.prop(sc, 'mch_mech_hdri_show')
    r = box.row(align=True)
    r.operator('mch.mech_hdri', text='Set HDRI', icon='WORLD').action = 'SET'
    r.operator('mch.mech_hdri', text='Off', icon='X').action = 'OFF'


class MCH_PT_mech_shader(bpy.types.Panel):
    bl_idname = 'MCH_PT_mech_shader'
    bl_label = 'Mech Shader'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Mecha Lab'
    bl_order = 80

    @classmethod
    def poll(cls, context):
        from . import tool_state as ts
        return context.mode in {'OBJECT', 'SCULPT'} and ts.sidebar_select(context)

    def draw(self, context):
        draw(self.layout, context)


CLASSES = (MCH_PG_MechShader, MCH_OT_mech_shader_apply, MCH_OT_mech_shader_step, MCH_OT_mech_shader_edges,
           MCH_OT_mech_hdri, MCH_PT_mech_shader)
SCENE_PROPS = ('mch_mech_preset', 'mch_mech_hdri', 'mch_mech_hdri_strength', 'mch_mech_hdri_rot',
               'mch_mech_hdri_show')


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Material.mch_mech = PointerProperty(type=MCH_PG_MechShader)
    T = bpy.types.Scene
    T.mch_mech_preset = EnumProperty(name='Mech Shader Preset', items=[(k, n, n) for k, n, _s in PRESETS],
                                     default='STEEL')
    T.mch_mech_hdri = EnumProperty(name='HDRI', items=_hdri_items, update=_hdri_update,
                                   description='Blender\'s built-in HDRIs (Set HDRI makes it the scene\'s world)')
    T.mch_mech_hdri_strength = FloatProperty(name='Strength', default=1.0, min=0.0, soft_max=5.0,
                                             update=_hdri_update)
    T.mch_mech_hdri_rot = FloatProperty(name='Rotation', subtype='ANGLE', default=0.0, update=_hdri_update)
    T.mch_mech_hdri_show = bpy.props.BoolProperty(name='Show Background (Cycles)', default=True,
                                                  update=_hdri_update,
                                                  description='Cycles: the camera sees the HDRI behind the model')


def unregister():
    for attr, owner in [('mch_mech', bpy.types.Material)] + [(p, bpy.types.Scene) for p in SCENE_PROPS]:
        try:
            delattr(owner, attr)
        except AttributeError:
            pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
