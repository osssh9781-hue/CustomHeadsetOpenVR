"""0.24.95 The Creature Shader (user: "크리쳐 작업할 때 방금 만든 메카닉 메테리얼처럼 크리쳐 전용으로" - "베이스 컬러랑
스컬핑은 내가 해 놓으니까 지저분한 진흙이나 더스트, SSS 마스크 그런 거"; "지브러시에서 수정 파일 가져오면 마스크를 다시 칠해야
했어" - so nearly everything comes from the shape, not painted masks).

* the base colour is the mesh's polypaint (its colour attribute - ZBrush's polypaint comes in with the FBX / OBJ);
  Polypaint 0 = the Base Color (and a Mottle pattern over it)
* the skin: a relief map (the user's creature maps, ``creature_maps/skin``) + a finer detail map, roughness, a clear
  coat, iridescence (thin film), crevices darker / ridges lighter (the mesh's convexity ``mch_curv``, as the Mech
  Shader - measured at the wear width, so a dense sculpt's folds read)
* SSS: an amount, a colour, a radius, more where the body is thin (Cycles: ambient occlusion from inside)
* layers on top, all from the shape: mud (in crevices / on top / low on the body - feet), dust (on what faces up),
  soot, snow, frost (in crevices), moss, fresh blood, dried blood, slime, wet, scars, rot, weathering (faded ridges),
  glow in the crevices (lava, alien)
* two kinds of presets, as the Mech Shader's material / edge wear: 14 Skin Types (what the skin is) and 12 Conditions
  (what is on it) - "Reptile Dry + Swamp Feet"
* hand masks: a point attribute ``mch_cm_<layer>`` (painted later) adds its layer there - none needed for the rest"""
from __future__ import annotations

import os

import bpy
from bpy.props import EnumProperty, FloatProperty, FloatVectorProperty, PointerProperty, StringProperty

from . import mech_shader as ms

KEY = 'mch_creature'
VERSION = 2                      # (2: Belly, Seed)
CMAP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'creature_maps')
# the user's creature maps (greyscale, seamless): slot -> [(id, label)]
CMAPS = {
    'skin': [('PORES', 'Pores'), ('WRINKLES', 'Fine Wrinkles'), ('HIDE', 'Thick Hide'), ('SCALES_S', 'Small Scales'),
             ('SCALES_L', 'Large Scales'), ('SNAKE', 'Snake Scales'), ('SCUTES', 'Croc Scutes'),
             ('WARTS', 'Toad Warts'), ('DENTICLES', 'Shark Skin'), ('CHITIN', 'Chitin'),
             ('MEMBRANE', 'Membrane Veins'), ('HORN', 'Horn / Bone')],
    'mottle': [('BLOTCH', 'Blotches'), ('FRECKLES', 'Freckles'), ('VEINS', 'Veins'), ('SPOTS', 'Leopard Spots'),
               ('STRIPES', 'Tiger Stripes'), ('MARBLE', 'Frog Marble'), ('BRUISE', 'Bruises'), ('ROT', 'Rot')],
    'organic': [('BLOOD', 'Blood'), ('BLOOD_DRY', 'Dried Blood'), ('SLIME', 'Slime'), ('DRIPS', 'Drips'),
                ('MOSS', 'Moss'), ('ALGAE', 'Algae'), ('MUD_CRACK', 'Cracked Mud'), ('SCARS', 'Scars')],
    # 0.24.95 the user's colour textures ("내가 챗지피티로 뽑아 온 베이스 컬러들"): a layer's own colour, sRGB
    'color': [('WET_MUD', 'Wet Mud'), ('CRACKED_MUD', 'Cracked Mud'), ('RED_CLAY', 'Red Clay'),
              ('DARK_SOIL', 'Dark Soil'), ('SANDY_SOIL', 'Sandy Soil'), ('PALE_DUST', 'Pale Dust'),
              ('ASH_DUST', 'Ash Dust'), ('OCHRE_DUST', 'Ochre Dust'), ('FRESH_BLOOD', 'Fresh Blood'),
              ('DRIED_BLOOD', 'Dried Blood'), ('CLOTTED_BLOOD', 'Clotted Blood'), ('CLEAR_MUCUS', 'Clear Mucus'),
              ('GREEN_SLIME', 'Green Slime'), ('AMBER_MUCUS', 'Amber Mucus'), ('PEELING_SKIN', 'Peeling Skin'),
              ('SCALY_KERATIN', 'Scaly Keratin'), ('GREEN_MOSS', 'Green Moss'), ('DRY_MOSS', 'Dry Moss'),
              ('LICHEN', 'Lichen'), ('ALGAE_FILM', 'Algae Film')],
}
# 0.24.95 (user: "베이스 컬러 쓰는 것들은 휴 · 세츄레이션 · 벨류로 조절하면 좋을 것 같으니까 슬라이드도"): the layers whose
# colour can be a colour texture ('<layer>_tex': Flat = the colour swatch) and has Hue / Saturation / Value
TEX_LAYERS = ('base', 'mud', 'dust', 'blood', 'blood_dry', 'slime', 'moss')
# (tiles per unit on a creature 2 units tall; x the layer's own Scale.  0.24.95 user: "이끼 크기가 너무 커" - the moss
#  photo's sprigs were as big as a leg at 0.6: 3.0)
TEX_TILES = {'base': 0.5, 'mud': 0.5, 'dust': 0.8, 'blood': 0.6, 'blood_dry': 0.6, 'slime': 0.6, 'moss': 3.0}
# the image nodes: name -> (creature map 'c' / Mech Shader map 'm', slot, id (None: from a setting), tiles per unit)
IMAGES = {
    'skin': ('c', 'skin', None, 0.5), 'detail': ('c', 'skin', None, 1.5), 'mottle': ('c', 'mottle', None, 0.35),
    'mud': ('m', 'dirt', 'MUD', 0.6), 'crack': ('c', 'organic', 'MUD_CRACK', 0.5), 'dust': ('m', 'dirt', 'DUST', 1.0),
    'soot': ('m', 'dirt', 'SOOT', 0.6), 'snow': ('m', 'snow', 'POWDER', 0.8), 'frost': ('m', 'snow', 'FROST', 1.5),
    'blood': ('c', 'organic', 'BLOOD', 0.6), 'blood_dry': ('c', 'organic', 'BLOOD_DRY', 0.6),
    'slime': ('c', 'organic', 'SLIME', 0.8), 'drips': ('c', 'organic', 'DRIPS', 0.6),
    'moss': ('c', 'organic', 'MOSS', 0.7), 'algae': ('c', 'organic', 'ALGAE', 0.5),
    'scars': ('c', 'organic', 'SCARS', 0.7), 'rot': ('c', 'mottle', 'ROT', 0.6), 'veins': ('c', 'mottle', 'VEINS', 0.6),
    'vary': ('m', 'rough', 'PATCHY', 0.3),
}
IMAGES.update({'tex_' + k: ('t', 'color', None, t) for k, t in TEX_TILES.items()})
MAP_PROPS = {'skin': 'skin_map', 'detail': 'detail_map', 'mottle': 'mottle_map'}
MASK = 'mch_cm_'                 # + layer: a painted mask (point attribute 0..1) adds that layer there
MASK_LAYERS = ('mud', 'dust', 'soot', 'snow', 'moss', 'blood', 'slime', 'wet', 'sss', 'glow')

_lin = ms._lin
# ---- every setting's default (colours as picked on screen, sRGB; the conditions all off)
BASE = dict(
    base_color=(0.62, 0.5, 0.42), polypaint=0.0, roughness=0.5, rough_var=0.3, ridge_gloss=0.0, coat=0.0, irid=0.0,
    sss=0.2, sss_color=(1.0, 0.4, 0.25), sss_radius=0.02, sss_thin=0.8, thick=0.08,
    cav_dark=0.4, cav_color=(0.45, 0.25, 0.22), ridge_light=0.15, ridge_color=(0.86, 0.8, 0.7), ao=0.6,
    variation=0.25, mottle=0.0, mottle_color=(0.3, 0.22, 0.16), mottle_scale=1.0,
    skin_scale=1.0, h_skin=0.5, h_detail=0.15, bump=1.0, map_scale=1.0, low_reach=0.35, size=1.0,
    belly=0.0, belly_color=(0.78, 0.7, 0.52), seed=0.0,
    rot=0.0, rot_color=(0.2, 0.22, 0.1), glow=0.0, glow_color=(1.0, 0.35, 0.05), glow_power=5.0,
    # conditions
    mud=0.0, mud_top=0.0, mud_low=0.0, mud_color=(0.22, 0.17, 0.11), mud_wet=0.3, mud_cake=0.0, h_mud=0.6,
    dust=0.0, dust_color=(0.62, 0.57, 0.5), soot=0.0, soot_color=(0.035, 0.032, 0.03), snow=0.0, frost=0.0,
    moss=0.0, moss_color=(0.2, 0.3, 0.08), h_moss=0.5, blood=0.0, blood_color=(0.36, 0.015, 0.012),
    blood_dry=0.0, blood_dry_color=(0.13, 0.03, 0.02), slime=0.0, slime_color=(0.5, 0.55, 0.32), wet=0.0,
    scars=0.0, scar_color=(0.72, 0.5, 0.45), fade=0.0,
    skin_map='PORES', detail_map='WRINKLES', mottle_map='BLOTCH')
for _k in TEX_LAYERS:
    BASE.update({_k + '_tex': 'FLAT', _k + '_hue': 0.0, _k + '_sat': 1.0, _k + '_val': 1.0, _k + '_scale': 1.0})
COND_KEYS = ('mud', 'mud_top', 'mud_low', 'mud_color', 'mud_wet', 'mud_cake', 'h_mud', 'dust', 'dust_color', 'soot',
             'soot_color', 'snow', 'frost', 'moss', 'moss_color', 'h_moss', 'blood', 'blood_color', 'blood_dry',
             'blood_dry_color', 'slime', 'slime_color', 'wet', 'scars', 'scar_color', 'fade', 'low_reach') + tuple(
    k + sfx for k in TEX_LAYERS if k != 'base' for sfx in ('_tex', '_hue', '_sat', '_val', '_scale'))
SKIN_KEYS = tuple(k for k in BASE if k not in COND_KEYS and k not in ('polypaint', 'map_scale', 'bump', 'size',
                                                                          'seed'))
# 0.24.95 Stack (a Condition added on top of the one there): the amounts take the larger, a layer's colour / texture /
# settings come along only when the added Condition uses that layer
AMOUNTS = ('mud', 'mud_top', 'mud_low', 'dust', 'soot', 'snow', 'frost', 'moss', 'blood', 'blood_dry', 'slime', 'wet',
           'scars', 'fade')


def _owner(k):
    for prefix, owners in (('blood_dry', ('blood_dry',)), ('blood', ('blood',)), ('mud', ('mud', 'mud_top', 'mud_low')),
                           ('h_mud', ('mud', 'mud_top', 'mud_low')), ('low_reach', ('mud_low', 'moss')),
                           ('dust', ('dust',)), ('soot', ('soot',)), ('moss', ('moss',)), ('h_moss', ('moss',)),
                           ('slime', ('slime',)), ('scar', ('scars',))):
        if k.startswith(prefix):
            return owners
    return ()
SLIDERS = tuple(k for k in BASE if not k.endswith(('_map', '_tex')))


def _c(**kw):
    d = dict(BASE)
    d.update(kw)
    return {k: (_lin(v) if k.endswith('color') else v) for k, v in d.items()}


# A. Skin Types: what the skin is
SKINS = [
    ('HUMAN', 'Human Skin', _c(base_color=(0.8, 0.6, 0.5), roughness=0.45, sss=0.35, sss_color=(1.0, 0.35, 0.18),
                               sss_radius=0.02, skin_map='PORES', detail_map='WRINKLES', skin_scale=3.0, h_skin=0.25,
                               h_detail=0.15, cav_dark=0.25, cav_color=(0.6, 0.3, 0.28), ridge_light=0.1, coat=0.05,
                               mottle=0.15, mottle_map='FRECKLES', mottle_color=(0.55, 0.35, 0.25))),
    ('REPTILE', 'Reptile Dry', _c(base_color=(0.45, 0.48, 0.32), roughness=0.7, rough_var=0.4, sss=0.05, belly=0.35,
                                  skin_map='SCALES_S', detail_map='PORES', h_skin=0.7, cav_dark=0.6, ridge_light=0.35,
                                  ridge_color=(0.85, 0.82, 0.65), mottle=0.3, mottle_map='BLOTCH',
                                  mottle_color=(0.3, 0.32, 0.2))),
    ('SNAKE', 'Snake Glossy', _c(base_color=(0.5, 0.45, 0.3), roughness=0.25, coat=0.4, sss=0.05, skin_map='SNAKE',
                                 belly=0.3,
                                 detail_map='PORES', h_skin=0.6, h_detail=0.05, cav_dark=0.5, ridge_light=0.2,
                                 mottle=0.45, mottle_map='SPOTS', mottle_color=(0.18, 0.14, 0.08), irid=0.15)),
    ('AMPHIBIAN', 'Amphibian Wet', _c(base_color=(0.42, 0.55, 0.25), roughness=0.12, coat=0.8, sss=0.45, belly=0.4,
                                      belly_color=(0.8, 0.76, 0.5),
                                      sss_color=(0.9, 0.8, 0.4), sss_radius=0.03, skin_map='WARTS', h_skin=0.55,
                                      h_detail=0.05, mottle=0.4, mottle_map='MARBLE', mottle_color=(0.2, 0.25, 0.1),
                                      cav_dark=0.3)),
    ('HIDE', 'Thick Hide', _c(base_color=(0.42, 0.4, 0.38), roughness=0.85, sss=0.0, skin_map='HIDE',
                              detail_map='WRINKLES', h_skin=0.9, h_detail=0.3, cav_dark=0.7, ridge_light=0.25,
                              skin_scale=0.6, ridge_color=(0.75, 0.72, 0.66))),
    ('DRAGON', 'Dragon Scales', _c(base_color=(0.35, 0.12, 0.08), roughness=0.4, coat=0.35, sss=0.05, belly=0.3,
                                   belly_color=(0.7, 0.5, 0.3),
                                   skin_map='SCALES_L', detail_map='PORES', h_skin=0.8, cav_dark=0.65, ridge_light=0.45,
                                   ridge_color=(0.9, 0.7, 0.4), ridge_gloss=0.2, irid=0.1)),
    ('CHITIN', 'Insect Chitin', _c(base_color=(0.15, 0.12, 0.08), roughness=0.2, coat=0.7, irid=0.7, sss=0.0,
                                   skin_map='CHITIN', detail_map='PORES', h_skin=0.5, h_detail=0.05, cav_dark=0.5,
                                   ridge_gloss=0.1, ridge_light=0.1)),
    ('MEMBRANE', 'Membrane / Wing', _c(base_color=(0.55, 0.35, 0.3), roughness=0.45, sss=0.8,
                                       sss_color=(1.0, 0.3, 0.2), sss_radius=0.05, sss_thin=1.5, skin_map='MEMBRANE',
                                       h_skin=0.35, h_detail=0.1, cav_dark=0.3)),
    ('ALIEN', 'Slime / Alien', _c(base_color=(0.35, 0.45, 0.4), roughness=0.1, coat=1.0, sss=0.6,
                                  sss_color=(0.5, 1.0, 0.7), sss_radius=0.04, skin_map='WARTS', h_skin=0.35,
                                  glow=0.25, glow_color=(0.3, 1.0, 0.6), glow_power=3.0, mottle=0.3,
                                  mottle_map='VEINS', mottle_color=(0.2, 0.35, 0.3), cav_dark=0.35)),
    ('SHARK', 'Shark / Fish', _c(base_color=(0.45, 0.5, 0.55), roughness=0.45, rough_var=0.2, coat=0.2, sss=0.1,
                                 belly=0.55, belly_color=(0.86, 0.86, 0.83),
                                 skin_map='DENTICLES', skin_scale=2.0, h_skin=0.3, h_detail=0.05, irid=0.1,
                                 cav_dark=0.3)),
    ('RUBBER', 'Smooth Rubber', _c(base_color=(0.45, 0.5, 0.55), roughness=0.2, coat=0.6, sss=0.3,
                                   sss_color=(0.9, 0.6, 0.5), skin_map='PORES', skin_scale=2.0, h_skin=0.1,
                                   h_detail=0.03, cav_dark=0.2, ridge_light=0.05)),
    ('UNDEAD', 'Undead / Rot', _c(base_color=(0.5, 0.52, 0.42), roughness=0.55, sss=0.15, sss_color=(0.6, 0.7, 0.4),
                                  skin_map='WRINKLES', h_skin=0.5, cav_dark=0.6, cav_color=(0.25, 0.2, 0.1), rot=0.45,
                                  rot_color=(0.18, 0.2, 0.08), mottle=0.35, mottle_map='BRUISE',
                                  mottle_color=(0.35, 0.25, 0.35))),
    ('DEMON', 'Demon / Lava', _c(base_color=(0.12, 0.06, 0.05), roughness=0.6, sss=0.0, skin_map='HIDE',
                                 detail_map='PORES', h_skin=0.8, cav_dark=0.4, glow=0.5, glow_color=(1.0, 0.35, 0.05),
                                 glow_power=8.0, ridge_light=0.1, ridge_color=(0.5, 0.35, 0.3))),
    ('BONE', 'Bone / Horn / Claw', _c(base_color=(0.8, 0.74, 0.6), roughness=0.5, ridge_gloss=0.35, sss=0.05,
                                      sss_color=(1.0, 0.8, 0.6), skin_map='HORN', detail_map='PORES', h_skin=0.4,
                                      cav_dark=0.6, cav_color=(0.35, 0.25, 0.15), ridge_light=0.2)),
]
# B. Conditions: what is on it (only COND_KEYS)
CONDITIONS = [
    ('CLEAN', 'Clean', _c()),
    ('DUSTY', 'Dusty', _c(dust=0.7, fade=0.1, dust_tex='PALE_DUST')),
    ('SWAMP', 'Swamp Feet', _c(mud_low=0.85, low_reach=0.5, mud=0.35, mud_wet=0.8, mud_color=(0.16, 0.13, 0.08),
                               h_mud=0.5, wet=0.25, moss=0.2, mud_tex='WET_MUD', moss_tex='ALGAE_FILM')),
    ('MUD_CAKED', 'Mud Caked', _c(mud=0.55, mud_top=0.35, mud_low=0.6, mud_cake=0.3, mud_wet=0.2,
                                  mud_color=(0.3, 0.24, 0.17), h_mud=0.9, mud_tex='CRACKED_MUD')),
    ('RAIN', 'Rain Wet', _c(wet=0.75)),
    ('SLIMY', 'Slimy', _c(slime=0.75, wet=0.35, slime_tex='GREEN_SLIME')),
    ('BLOODY', 'Bloody', _c(blood=0.35, blood_dry=0.4, scars=0.4, blood_tex='FRESH_BLOOD',
                            blood_dry_tex='DRIED_BLOOD')),
    ('DESERT', 'Desert Dry', _c(dust=0.35, dust_color=(0.75, 0.65, 0.5), fade=0.4, mud=0.2, mud_cake=0.3, mud_wet=0.0,
                                mud_color=(0.6, 0.5, 0.38), dust_tex='PALE_DUST', mud_tex='CRACKED_MUD')),
    ('SNOW', 'Snow / Frost', _c(snow=0.45, frost=0.4)),
    ('OLD', 'Old / Weathered', _c(fade=0.5, scars=0.2)),
    ('SOOTY', 'Sooty / Burnt', _c(soot=0.55)),
    ('MOSSY', 'Moss / Algae', _c(moss=0.5, h_moss=0.6, wet=0.15, moss_tex='GREEN_MOSS')),
]
SKIN_IDS = tuple(s[0] for s in SKINS)
COND_IDS = tuple(s[0] for s in CONDITIONS)
_SYNCING = [False]


def cmap_path(slot, ident):
    for ext in ('.jpg', '.png'):
        p = os.path.join(CMAP_DIR, slot, ident + ext)
        if os.path.isfile(p):
            return p
    return None


def cmap_image(slot, ident):
    """A creature map as a Blender image (loaded once, shared): Non-Color (heights, masks), the colour textures sRGB."""
    p = cmap_path(slot, ident)
    if p is None:
        return None
    img = bpy.data.images.load(p, check_existing=True)
    want = 'sRGB' if slot == 'color' else 'Non-Color'
    try:
        if img.colorspace_settings.name != want:
            img.colorspace_settings.name = want
    except TypeError:
        pass
    return img


def _image_for(st, name):
    src, slot, ident, _t = IMAGES[name]
    if src == 't':                                   # (a layer's colour texture - none when it is Flat)
        ident = getattr(st, name[4:] + '_tex')
        return None if ident == 'FLAT' else cmap_image('color', ident)
    if ident is None:
        ident = getattr(st, MAP_PROPS[name])
    return cmap_image(slot, ident) if src == 'c' else ms.map_image(slot, ident, data=True)


# -----------------------------------------------------------------------------
# the node tree
# -----------------------------------------------------------------------------

def build(mat):
    """The Creature Shader node tree in ``mat`` (made anew)."""
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    b = ms.Builder(nt)
    out = b.node('ShaderNodeOutputMaterial')
    bsdf = b.node('ShaderNodeBsdfPrincipled', 'mch:bsdf')
    b.link(bsdf.outputs['BSDF'], out.inputs['Surface'])
    try:
        bsdf.subsurface_method = 'RANDOM_WALK'
    except (AttributeError, TypeError):
        pass
    tc = b.node('ShaderNodeTexCoord')
    v = {k: b.value(k, 0.0) for k in SLIDERS if not k.endswith('color')}
    c = {k: b.rgb(k) for k in SLIDERS if k.endswith('color')}
    img = {}
    # (everything measured on a creature 2 units tall: Size = the creature's size / 2, set when the shader is put on -
    #  the maps as many times across a body of any size, the SSS / thin / crevice distances with it)
    unit = b.math('DIVIDE', v['map_scale'], b.math('MAXIMUM', v['size'], 1e-4))
    # (0.24.95 Seed: every map moved - the same preset, a different creature)
    off = b.node('ShaderNodeCombineXYZ', 'mch:seed_offset')
    for i, f in enumerate((17.31, -9.73, 5.17)):
        b.link(b.math('MULTIPLY', v['seed'], f), off.inputs[i])
    obj = b.vmath('ADD', tc.outputs['Object'], off.outputs['Vector'])
    for name, (_src, _slot, _id, tiles) in IMAGES.items():
        sc = b.math('MULTIPLY', unit, tiles)
        if name in ('skin', 'detail'):
            sc = b.math('MULTIPLY', sc, v['skin_scale'])
        elif name == 'mottle':
            sc = b.math('MULTIPLY', sc, v['mottle_scale'])
        elif name.startswith('tex_'):                # (a colour texture: its layer's own Scale)
            sc = b.math('MULTIPLY', sc, v[name[4:] + '_scale'])
        sc.node.name = 'mch:scale:' + name
        img[name] = b.image(name, b.vmath('SCALE', obj, fac=sc)).outputs['Color']

    def painted(layer):                              # (a hand-painted mask: 0 where none is painted / no attribute)
        nd = b.node('ShaderNodeAttribute', 'mch:mask:' + layer)
        nd.attribute_type = 'GEOMETRY'
        nd.attribute_name = MASK + layer
        return nd.outputs['Fac']

    def mx(*socks):
        s = socks[0]
        for o in socks[1:]:
            s = b.math('MAXIMUM', s, o)
        return s

    def add(*terms):                                 # (sum of (socket, weight)), clamped
        s = None
        for sock, wgt in terms:
            t = b.math('MULTIPLY', sock, wgt) if wgt != 1.0 else sock
            s = t if s is None else b.math('ADD', s, t)
        return b.math('ADD', s, 0.0, clamp=True)

    # ---- the shape: crevices / ridges (the convexity + AO), up, low on the body, thin
    att = b.node('ShaderNodeAttribute', 'mch:curv')
    att.attribute_type = 'GEOMETRY'
    att.attribute_name = ms.CURV
    curv = att.outputs['Factor']
    ridge = b.math('MULTIPLY', curv, 1.0, clamp=True)
    cav = b.math('MULTIPLY', curv, -1.0, clamp=True)
    aon = b.node('ShaderNodeAmbientOcclusion', 'mch:ao_node')
    aon.samples = 16
    b.link(b.math('MULTIPLY', v['size'], 0.15), aon.inputs['Distance'])
    cav = b.math('MAXIMUM', cav, b.math('MULTIPLY', b.maprange(aon.outputs['AO'], 0.95, 0.35), v['ao']))
    geo = b.node('ShaderNodeNewGeometry')
    nsep = b.node('ShaderNodeSeparateXYZ')
    b.link(geo.outputs['Normal'], nsep.inputs['Vector'])
    nz = nsep.outputs['Z']
    top = b.math('MAXIMUM', nz, 0.0)
    side = b.math('SUBTRACT', 1.0, b.math('ABSOLUTE', nz))
    gsep = b.node('ShaderNodeSeparateXYZ')
    b.link(tc.outputs['Generated'], gsep.inputs['Vector'])
    low = b.maprange(gsep.outputs['Z'], v['low_reach'], 0.0)              # (the feet 1 .. Low Reach up 0)
    thick = b.node('ShaderNodeAmbientOcclusion', 'mch:thick_ao')            # (Cycles: from inside - thin parts)
    thick.inside = True
    thick.samples = 16
    b.link(b.math('MULTIPLY', v['thick'], v['size']), thick.inputs['Distance'])
    thin = b.maprange(thick.outputs['AO'], 0.9, 0.3)

    # ---- the layers' masks (each its amount; a painted mask adds it there)
    mottle = b.threshold(img['mottle'], v['mottle'], 0.25)
    rot = b.threshold(add((cav, 0.5), (img['rot'], 0.6)), v['rot'], 0.2)
    scars = b.threshold(img['scars'], b.math('MULTIPLY', v['scars'], 0.8), 0.12)
    bdry = b.threshold(add((cav, 0.55), (img['blood_dry'], 0.6)), v['blood_dry'], 0.15)
    moss = mx(b.threshold(add((cav, 0.5), (low, 0.4), (img['moss'], 0.5), (img['algae'], 0.2)), v['moss'], 0.2),
              painted('moss'))
    m_cav = b.threshold(add((cav, 0.7), (img['mud'], 0.45)), v['mud'], 0.15)
    m_top = b.threshold(add((top, 0.65), (img['mud'], 0.5)), v['mud_top'], 0.2)
    m_low = b.threshold(add((low, 0.75), (img['mud'], 0.45)), v['mud_low'], 0.2)
    mud = b.math('MULTIPLY', mx(m_cav, m_top, m_low, painted('mud')), 0.95)
    blood = mx(b.threshold(add((img['blood'], 0.8), (cav, 0.3), (b.math('MULTIPLY', img['drips'], side), 0.35)),
                           v['blood'], 0.12), painted('blood'))
    slime = mx(b.threshold(add((cav, 0.6), (img['slime'], 0.5)), v['slime'], 0.15), painted('slime'))
    soot = mx(b.threshold(add((top, 0.35), (img['soot'], 0.6), (ridge, 0.15)), v['soot'], 0.2), painted('soot'))
    dust = mx(b.threshold(add((top, 0.6), (img['dust'], 0.5)), v['dust'], 0.2), painted('dust'))
    frost = b.threshold(add((cav, 0.6), (img['frost'], 0.5)), v['frost'], 0.15)
    snow = mx(b.threshold_s(add((nz, 0.8), (img['snow'], 0.3)), b.math('MULTIPLY', v['snow'], 1.1), 0.25),
              painted('snow'))
    wet = b.math('ADD', v['wet'], painted('wet'), clamp=True)
    glow = mx(b.threshold(add((cav, 0.8), (img['veins'], 0.4)), v['glow'], 0.2), painted('glow'))

    # ---- colour: the polypaint (or Base Color), mottle, uneven, crevices darker / ridges lighter, then the layers
    use = {k: b.value('use_' + k) for k in TEX_LAYERS}      # (1: the layer's colour is its colour texture)

    def hsv(col, layer):                                     # (0.24.95 Hue / Saturation / Value of a layer's colour)
        nd = b.node('ShaderNodeHueSaturation', 'mch:hsv:' + layer)
        b.link(b.math('ADD', v[layer + '_hue'], 0.5), nd.inputs['Hue'])
        b.link(v[layer + '_sat'], nd.inputs['Saturation'])
        b.link(v[layer + '_val'], nd.inputs['Value'])
        nd.inputs['Fac'].default_value = 1.0
        b.link(col, nd.inputs['Color'])
        return nd.outputs['Color']

    def tex(layer, flat):                                    # (the swatch, or the colour texture; then its HSV)
        return hsv(b.mixc(use[layer], flat, img['tex_' + layer]), layer)
    pp = b.node('ShaderNodeVertexColor', 'mch:pp_attr')                # ('' = the mesh's default colour attribute)
    col = b.mixc(v['polypaint'], b.mixc(use['base'], c['base_color'], img['tex_base']), pp.outputs['Color'])
    col = hsv(col, 'base')                                   # (the polypaint too: one place to shift the whole colour)
    # (0.24.95 Belly: the underside lighter, as most animals - only where there is no polypaint)
    belly = b.math('MULTIPLY', b.maprange(nz, 0.15, -0.55),
                   b.math('MULTIPLY', v['belly'], b.math('SUBTRACT', 1.0, v['polypaint'])))
    col = b.mixc(belly, col, c['belly_color'])
    col = b.mixc(mottle, col, c['mottle_color'])
    col = b.vmath('SCALE', col, fac=b.math('ADD', 1.0, b.math('MULTIPLY', b.math('SUBTRACT', img['vary'], 0.5),
                                                              v['variation'])))
    # (weathered: faded on the ridges, darker in the crevices)
    cav_k = b.math('MULTIPLY', cav, b.math('ADD', v['cav_dark'], b.math('MULTIPLY', v['fade'], 0.4)), clamp=True)
    col = b.mixc(cav_k, col, b.mixc(1.0, col, c['cav_color'], 'MULTIPLY'))
    col = b.mixc(b.math('MULTIPLY', ridge, v['ridge_light']), col, b.mixc(0.5, col, c['ridge_color']))
    bw = b.node('ShaderNodeRGBToBW')
    b.link(col, bw.inputs['Color'])
    faded = b.mixc(0.35, bw.outputs['Val'], (0.78, 0.74, 0.68, 1.0))
    col = b.mixc(b.math('MULTIPLY', v['fade'], b.math('ADD', 0.45, b.math('MULTIPLY', ridge, 0.8)), clamp=True),
                 col, faded)
    col = b.mixc(scars, col, c['scar_color'])
    col = b.mixc(rot, col, c['rot_color'])
    col = b.mixc(bdry, col, tex('blood_dry', c['blood_dry_color']))
    col = b.mixc(moss, col, tex('moss', b.vmath('SCALE', c['moss_color'],
                                                fac=b.math('ADD', 0.6, b.math('MULTIPLY', img['moss'], 0.6)))))
    mud_col = tex('mud', b.vmath('SCALE', c['mud_color'], fac=b.math('ADD', 0.6, b.math('MULTIPLY', img['mud'], 0.6))))
    mud_col = b.vmath('SCALE', mud_col, fac=b.mixf(v['mud_cake'], 1.0, b.math('ADD', 0.35,
                                                                              b.math('MULTIPLY', img['crack'], 0.75))))
    mud_col = b.vmath('SCALE', mud_col, fac=b.math('SUBTRACT', 1.0, b.math('MULTIPLY', v['mud_wet'], 0.35)))
    col = b.mixc(mud, col, mud_col)
    col = b.mixc(blood, col, tex('blood', c['blood_color']))
    col = b.mixc(b.math('MULTIPLY', slime, b.math('ADD', 0.4, b.math('MULTIPLY', use['slime'], 0.35))), col,
                 tex('slime', c['slime_color']))
    col = b.mixc(b.math('MULTIPLY', soot, 0.92), col, c['soot_color'])
    col = b.mixc(b.math('MULTIPLY', dust, 0.85), col, tex('dust', c['dust_color']))
    col = b.mixc(b.math('MULTIPLY', frost, 0.8), col, (0.82, 0.88, 0.95, 1.0))
    col = b.mixc(snow, col, (0.88, 0.9, 0.94, 1.0))
    col = b.vmath('SCALE', col, fac=b.math('SUBTRACT', 1.0, b.math('MULTIPLY', wet, 0.22)))     # (wet: darker)
    b.link(col, bsdf.inputs['Base Color'])

    # ---- roughness
    r = b.math('ADD', v['roughness'], b.math('MULTIPLY', v['rough_var'], b.math('SUBTRACT', img['skin'], 0.5)),
               clamp=True)
    r = b.math('SUBTRACT', r, b.math('MULTIPLY', ridge, v['ridge_gloss']), clamp=True)   # (horn: polished bumps)
    r = b.mixf(rot, r, 0.3)
    r = b.mixf(bdry, r, 0.55)
    r = b.mixf(moss, r, 0.9)
    r = b.mixf(mud, r, b.mixf(v['mud_wet'], 0.9, 0.35))
    r = b.mixf(blood, r, 0.12)
    r = b.mixf(slime, r, 0.04)
    r = b.mixf(soot, r, 0.85)
    r = b.mixf(dust, r, 0.92)
    r = b.mixf(frost, r, 0.35)
    r = b.mixf(snow, r, 0.6)
    r = b.math('MULTIPLY', r, b.math('SUBTRACT', 1.0, b.math('MULTIPLY', wet, 0.75)))
    b.link(r, bsdf.inputs['Roughness'])
    b.put(bsdf.inputs['Metallic'], 0.0)
    dry = mx(dust, soot, snow, moss, bdry, b.math('MULTIPLY', mud, b.math('SUBTRACT', 1.0, v['mud_wet'])))
    coat = add((v['coat'], 1.0), (wet, 1.0), (slime, 1.0), (blood, 0.6))
    b.link(b.math('MULTIPLY', coat, b.math('SUBTRACT', 1.0, dry)), bsdf.inputs['Coat Weight'])
    bsdf.inputs['Coat Roughness'].default_value = 0.05
    if 'Thin Film Thickness' in bsdf.inputs:                                  # (iridescence: chitin, fish)
        b.link(b.math('MULTIPLY', b.math('MULTIPLY', v['irid'], b.math('SUBTRACT', 1.0, dry)), 600.0),
               bsdf.inputs['Thin Film Thickness'])
        bsdf.inputs['Thin Film IOR'].default_value = 1.45

    # ---- SSS: more where the body is thin, none under mud / dust / snow
    covered = mx(mud, dust, snow, soot, moss, bdry)
    sss = b.math('MULTIPLY', v['sss'], b.math('ADD', 1.0, b.math('MULTIPLY', thin, v['sss_thin'])))
    sss = b.math('MULTIPLY', mx(sss, painted('sss')), b.math('SUBTRACT', 1.0, covered), clamp=True)
    b.link(sss, bsdf.inputs['Subsurface Weight'])
    b.link(c['sss_color'], bsdf.inputs['Subsurface Radius'])
    b.link(b.math('MULTIPLY', v['sss_radius'], v['size']), bsdf.inputs['Subsurface Scale'])

    # ---- relief: the skin + its detail, scars cut in, mud / moss / snow stand out
    h = b.math('MULTIPLY', b.math('SUBTRACT', img['skin'], 0.5), v['h_skin'])
    h = b.math('ADD', h, b.math('MULTIPLY', b.math('SUBTRACT', img['detail'], 0.5), v['h_detail']))
    h = b.math('ADD', h, b.math('MULTIPLY', scars, -0.25))
    h = b.math('ADD', h, b.math('MULTIPLY', b.math('MULTIPLY', mud, b.math('ADD', b.math('MULTIPLY', img['mud'], 0.5),
                                                                         b.math('ADD', 0.4, b.math('MULTIPLY', img['crack'],
                                                                                                   v['mud_cake'])))),
                                v['h_mud']))
    h = b.math('ADD', h, b.math('MULTIPLY', b.math('MULTIPLY', moss, img['moss']), v['h_moss']))
    h = b.math('ADD', h, b.math('MULTIPLY', snow, b.math('ADD', b.math('MULTIPLY', img['snow'], 0.35), 0.45)))
    h = b.math('ADD', h, b.math('MULTIPLY', bdry, 0.12))
    h = b.math('ADD', h, b.math('MULTIPLY', dust, b.math('MULTIPLY', img['dust'], 0.2)))
    bump = b.node('ShaderNodeBump', 'mch:bumpnode')
    b.put(bump.inputs['Strength'], b.math('MINIMUM', v['bump'], 1.0))
    b.link(b.math('MULTIPLY', v['size'], 0.05), bump.inputs['Distance'])
    b.link(b.math('MULTIPLY', h, b.math('MAXIMUM', v['bump'], 1.0)), bump.inputs['Height'])
    b.link(bump.outputs['Normal'], bsdf.inputs['Normal'])
    b.link(c['glow_color'], bsdf.inputs['Emission Color'])
    b.link(b.math('MULTIPLY', glow, v['glow_power']), bsdf.inputs['Emission Strength'])
    mat[KEY] = VERSION
    return mat


def is_creature(mat):
    return mat is not None and bool(mat.get(KEY)) and mat.node_tree is not None \
        and mat.node_tree.nodes.get('mch:bsdf') is not None


def sync(mat):
    """The settings into the nodes (a slider moved, a map / preset stepped: at once)."""
    if not is_creature(mat):
        return
    if mat.get(KEY, 0) < VERSION:
        build(mat)
    st = getattr(mat, KEY)
    nodes = mat.node_tree.nodes
    for k in SLIDERS:
        nd = nodes.get('mch:' + k)
        if nd is None:
            continue
        val = getattr(st, k)
        nd.outputs[0].default_value = (*val, 1.0) if k.endswith('color') else float(val)
    for k in TEX_LAYERS:
        nd = nodes.get('mch:use_' + k)
        if nd is not None:
            nd.outputs[0].default_value = 0.0 if getattr(st, k + '_tex') == 'FLAT' else 1.0
    for name in IMAGES:
        nd = nodes.get('mch:img:' + name)
        if nd is not None:
            im = _image_for(st, name)
            if nd.image != im:
                nd.image = im


def _apply(mat, spec, keys, prop, ident):
    st = getattr(mat, KEY)
    _SYNCING[0] = True
    try:
        for k in keys:
            setattr(st, k, spec[k])
        if getattr(st, prop) != ident:
            setattr(st, prop, ident)
    finally:
        _SYNCING[0] = False
    sync(mat)


def apply_skin(mat, ident):
    """A Skin Type: everything but the conditions (and Polypaint / Map Scale / Height, which stay)."""
    spec = next((s[2] for s in SKINS if s[0] == ident), None)
    if spec is None:
        return False
    _apply(mat, spec, SKIN_KEYS, 'skin_type', ident)
    return True


def apply_condition(mat, ident, stack=None):
    """A Condition: only the layers on top (mud, dust, blood ...) - the skin stays.  ``stack`` (default: the material's
    Stack switch): added on top of what is there - the amounts the larger, a layer's colour / texture / settings only
    from a Condition that uses that layer (Clean still clears)."""
    spec = next((s[2] for s in CONDITIONS if s[0] == ident), None)
    if spec is None:
        return False
    st = getattr(mat, KEY)
    if stack is None:
        stack = st.cond_stack
    if stack and ident != 'CLEAN':
        merged = {}
        for k in COND_KEYS:
            cur = getattr(st, k)
            if k in AMOUNTS:
                merged[k] = max(float(cur), spec[k])
            elif any(spec[a] > 0.0 for a in _owner(k)):
                merged[k] = spec[k]
            else:
                merged[k] = tuple(cur) if k.endswith('color') else cur
        spec = merged
    _apply(mat, spec, COND_KEYS, 'condition', ident)
    return True


# -----------------------------------------------------------------------------
# settings
# -----------------------------------------------------------------------------

def _update(self, context):
    if not _SYNCING[0]:
        sync(self.id_data)


def _skin_update(self, context):
    if not _SYNCING[0]:
        apply_skin(self.id_data, self.skin_type)


def _cond_update(self, context):
    if not _SYNCING[0]:
        apply_condition(self.id_data, self.condition)


def _color(name, key, desc=''):
    return FloatVectorProperty(name=name, subtype='COLOR', size=3, min=0.0, max=1.0, default=_lin(BASE[key]),
                               update=_update, description=desc)


def _s(name, key, lo=0.0, hi=1.0, desc=''):
    return FloatProperty(name=name, default=BASE[key], min=lo, max=hi, update=_update, description=desc)


def _maps(slot):
    return [(k, n, f'{slot.title()} map: {n}') for k, n in CMAPS[slot]]


class MCH_PG_CreatureShader(bpy.types.PropertyGroup):
    skin_type: EnumProperty(name='Skin Type', items=[(k, n, n) for k, n, _s in SKINS], default='HUMAN',
                            update=_skin_update, description='What the skin is (everything but the conditions)')
    condition: EnumProperty(name='Condition', items=[(k, n, n) for k, n, _s in CONDITIONS], default='CLEAN',
                            update=_cond_update, description='What is on the skin (mud, dust, blood ...)')
    cond_stack: bpy.props.BoolProperty(name='Stack Conditions', default=False,
                                       description='A Condition is added on top of the one there (mud + blood ...) '
                                                   'instead of replacing it - Clean clears')
    belly: _s('Belly', 'belly', desc='The underside lighter, as most animals (only where there is no polypaint)')
    belly_color: _color('Belly Color', 'belly_color')
    seed: _s('Seed', 'seed', 0.0, 1000.0, 'Every map moved: the same preset, a different creature')
    polypaint: _s('Polypaint', 'polypaint', desc='The mesh\'s polypaint (colour attribute - ZBrush polypaint comes in '
                                                'with the FBX / OBJ) as the colour: 1, the Base Color: 0')
    base_color: _color('Base Color', 'base_color', 'The colour where there is no polypaint')
    roughness: _s('Roughness', 'roughness')
    rough_var: _s('Roughness Variation', 'rough_var', desc='The skin map makes the roughness uneven')
    ridge_gloss: _s('Ridge Gloss', 'ridge_gloss', desc='Ridges / bumps polished smoother (horn, claws)')
    coat: _s('Clear Coat', 'coat', desc='A glossy wet / oily coat')
    irid: _s('Iridescence', 'irid', desc='Colours shifting with the angle (chitin, fish) - thin film')
    sss: _s('SSS', 'sss', desc='Light through the skin (subsurface scattering)')
    sss_color: _color('SSS Color', 'sss_color', 'How far each colour goes through (skin: red the farthest)')
    sss_radius: _s('SSS Radius', 'sss_radius', 0.0, 1.0, 'How far the light goes through (scene units)')
    sss_thin: _s('More Where Thin', 'sss_thin', 0.0, 3.0, 'Extra SSS where the body is thin - ears, fins, wings '
                                                        '(Cycles)')
    thick: _s('Thin Below', 'thick', 0.001, 1.0, 'What counts as thin (scene units)')
    cav_dark: _s('Crevices Darker', 'cav_dark')
    cav_color: _color('Crevice Tint', 'cav_color')
    ridge_light: _s('Ridges Lighter', 'ridge_light')
    ridge_color: _color('Ridge Color', 'ridge_color')
    ao: _s('Crevice AO', 'ao', desc='Crevices found by ambient occlusion too')
    variation: _s('Variation', 'variation', desc='The colour a little uneven')
    mottle: _s('Mottle', 'mottle', desc='A pattern of a second colour (the Mottle map)')
    mottle_color: _color('Mottle Color', 'mottle_color')
    mottle_scale: _s('Mottle Scale', 'mottle_scale', 0.05, 20.0)
    skin_scale: _s('Skin Scale', 'skin_scale', 0.05, 20.0, 'The skin maps repeated more (bigger = finer)')
    h_skin: _s('Skin Height', 'h_skin', 0.0, 3.0)
    h_detail: _s('Detail Height', 'h_detail', 0.0, 3.0)
    bump: _s('Height', 'bump', 0.0, 4.0, 'All the bump at once')
    map_scale: _s('Map Scale', 'map_scale', 0.05, 20.0, 'Every map repeated more (bigger = finer)')
    size: _s('Creature Size', 'size', 0.001, 1000.0, 'The creature\'s size / 2 (set when the shader is put on): the maps, '
                                                    'SSS and crevices look the same on a creature of any size')
    low_reach: _s('Low Reach', 'low_reach', 0.02, 1.0, 'How high up "low on the body" goes (mud from below)')
    rot: _s('Rot', 'rot', desc='Rotting patches in the crevices')
    rot_color: _color('Rot Color', 'rot_color')
    glow: _s('Glow', 'glow', desc='Glow from the crevices (lava, alien)')
    glow_color: _color('Glow Color', 'glow_color')
    glow_power: _s('Glow Strength', 'glow_power', 0.0, 50.0)
    mud: _s('Mud in Crevices', 'mud')
    mud_top: _s('Mud on Top', 'mud_top')
    mud_low: _s('Mud from Below', 'mud_low', desc='Mud low on the body - feet and legs')
    mud_color: _color('Mud Color', 'mud_color')
    mud_wet: _s('Mud Wetness', 'mud_wet')
    mud_cake: _s('Caked / Cracked', 'mud_cake', desc='Dried mud cracking into plates')
    h_mud: _s('Mud Height', 'h_mud', 0.0, 3.0)
    dust: _s('Dust', 'dust', desc='Dust on what faces up')
    dust_color: _color('Dust Color', 'dust_color')
    soot: _s('Soot', 'soot')
    soot_color: _color('Soot Color', 'soot_color')
    snow: _s('Snow', 'snow')
    frost: _s('Frost', 'frost', desc='Frost in the crevices')
    moss: _s('Moss', 'moss', desc='Moss / algae in the crevices and low on the body')
    moss_color: _color('Moss Color', 'moss_color')
    h_moss: _s('Moss Height', 'h_moss', 0.0, 3.0)
    blood: _s('Fresh Blood', 'blood')
    blood_color: _color('Blood Color', 'blood_color')
    blood_dry: _s('Dried Blood', 'blood_dry', desc='Dried blood in the crevices')
    blood_dry_color: _color('Dried Blood Color', 'blood_dry_color')
    slime: _s('Slime', 'slime', desc='Slime in the crevices and folds')
    slime_color: _color('Slime Color', 'slime_color')
    wet: _s('Wet', 'wet', desc='The whole skin wet')
    scars: _s('Scars', 'scars')
    scar_color: _color('Scar Color', 'scar_color')
    fade: _s('Weathered', 'fade', desc='Faded, bleached ridges, darker crevices')
    skin_map: EnumProperty(name='Skin Map', items=_maps('skin'), default=BASE['skin_map'], update=_update)
    # 0.24.95 each colour layer: its colour texture (Flat = the swatch) + Hue / Saturation / Value
    for _k, _n in (('base', 'Skin'), ('mud', 'Mud'), ('dust', 'Dust'), ('blood', 'Blood'), ('blood_dry', 'Dried Blood'),
                   ('slime', 'Slime'), ('moss', 'Moss')):
        __annotations__[_k + '_tex'] = EnumProperty(
            name=f'{_n} Texture', items=[('FLAT', 'Flat Color', 'The colour swatch')] + _maps('color'), default='FLAT',
            update=_update, description=f'{_n}: a colour texture (Flat = the colour swatch)')
        __annotations__[_k + '_hue'] = FloatProperty(name='Hue', default=0.0, min=-0.5, max=0.5, update=_update,
                                                     description=f'{_n}: shift the hue')
        __annotations__[_k + '_sat'] = FloatProperty(name='Saturation', default=1.0, min=0.0, max=2.0, update=_update,
                                                     description=f'{_n}: 0 grey .. 1 as it is .. 2 stronger')
        __annotations__[_k + '_val'] = FloatProperty(name='Value', default=1.0, min=0.0, max=2.0, update=_update,
                                                     description=f'{_n}: darker .. 1 as it is .. brighter')
        __annotations__[_k + '_scale'] = FloatProperty(name='Texture Scale', default=1.0, min=0.05, max=20.0,
                                                       update=_update,
                                                       description=f'{_n}: the texture repeated more (bigger = finer)')
    del _k, _n
    detail_map: EnumProperty(name='Detail Map', items=_maps('skin'), default=BASE['detail_map'], update=_update)
    mottle_map: EnumProperty(name='Mottle Map', items=_maps('mottle'), default=BASE['mottle_map'], update=_update)


def active_creature(context):
    ob = getattr(context, 'active_object', None)
    mat = getattr(ob, 'active_material', None) if ob is not None else None
    return mat if is_creature(mat) else None


def body_size(objs):
    """Half the largest size of the meshes (world): 1 for a creature 2 units tall."""
    d = max((max(o.dimensions) for o in objs if o is not None and o.type == 'MESH'), default=2.0)
    return max(d / 2.0, 1e-3)


def has_polypaint(objs):
    return any(o is not None and o.type == 'MESH' and len(o.data.color_attributes) for o in objs)


def new_material(skin='HUMAN', condition='CLEAN', name=None, polypaint=False):
    label = dict((k, n) for k, n, _s in SKINS).get(skin, skin)
    mat = bpy.data.materials.new(name or 'Creature ' + label)
    build(mat)
    st = getattr(mat, KEY)
    _SYNCING[0] = True
    try:
        st.polypaint = 1.0 if polypaint else 0.0
    finally:
        _SYNCING[0] = False
    apply_skin(mat, skin)
    apply_condition(mat, condition)
    return mat


class MCH_OT_creature_apply(bpy.types.Operator):
    """A new Creature Shader material on the selected meshes: their polypaint as the colour (when they have one),
    their crevices / ridges measured"""
    bl_idname = 'mch.creature_apply'
    bl_label = 'Apply Creature Shader'
    bl_options = {'REGISTER', 'UNDO'}
    skin: StringProperty(default='')
    condition: StringProperty(default='')

    def execute(self, context):
        obs = ms._targets(context)
        if not obs:
            self.report({'WARNING'}, 'Creature Shader: select a mesh')
            return {'CANCELLED'}
        cur = active_creature(context)
        st = getattr(cur, KEY) if cur is not None else None
        skin = self.skin or (st.skin_type if st else context.scene.mch_creature_skin)
        cond = self.condition or (st.condition if st else 'CLEAN')
        mat = new_material(skin, cond, polypaint=has_polypaint(obs))
        getattr(mat, KEY).size = body_size(obs)
        n = ms.assign(context, obs, mat)
        ms._look(context)
        pp = ' - polypaint as the colour' if getattr(mat, KEY).polypaint > 0 else ''
        self.report({'INFO'}, f'Creature Shader "{mat.name}" on {n} mesh(es){pp}')
        return {'FINISHED'}


class MCH_OT_creature_step(bpy.types.Operator):
    """Next / previous of this list (the material changes at once)"""
    bl_idname = 'mch.creature_step'
    bl_label = 'Creature Shader Step'
    bl_options = {'REGISTER', 'UNDO'}
    prop: StringProperty(default='skin_type')
    step: bpy.props.IntProperty(default=1)

    def execute(self, context):
        mat = active_creature(context)
        if mat is None:
            if self.prop != 'skin_type':
                return {'CANCELLED'}
            sc = context.scene
            i = SKIN_IDS.index(sc.mch_creature_skin) if sc.mch_creature_skin in SKIN_IDS else 0
            sc.mch_creature_skin = SKIN_IDS[(i + self.step) % len(SKIN_IDS)]
            return bpy.ops.mch.creature_apply(skin=sc.mch_creature_skin) if ms._targets(context) else {'FINISHED'}
        st = getattr(mat, KEY)
        items = [i.identifier for i in st.bl_rna.properties[self.prop].enum_items]
        cur = getattr(st, self.prop)
        setattr(st, self.prop, items[(items.index(cur) + self.step) % len(items)])
        return {'FINISHED'}


CLASSES = (MCH_PG_CreatureShader, MCH_OT_creature_apply, MCH_OT_creature_step)


def register():
    for cl in CLASSES:
        bpy.utils.register_class(cl)
    bpy.types.Material.mch_creature = PointerProperty(type=MCH_PG_CreatureShader)
    bpy.types.Scene.mch_creature_skin = EnumProperty(name='Creature Skin Type', items=[(k, n, n) for k, n, _s in SKINS],
                                                     default='HUMAN')


def unregister():
    for attr, owner in (('mch_creature', bpy.types.Material), ('mch_creature_skin', bpy.types.Scene)):
        try:
            delattr(owner, attr)
        except AttributeError:
            pass
    for cl in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cl)
        except RuntimeError:
            pass
