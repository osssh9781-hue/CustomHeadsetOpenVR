"""0.24.95 The Creature Shader (user: "크리쳐 전용으로 - 베이스 컬러랑 스컬핑은 내가 해 놓으니까 지저분한 진흙이나
더스트, SSS 마스크 그런 거"; "지브러시에서 수정 파일 가져오면 마스크를 다시 칠해야 했어"; the colour textures "내가 챗지피티로
뽑아 온 베이스 컬러들 - 휴 · 세츄레이션 · 벨류로 조절하게 슬라이드도"):

* the polypaint (colour attribute) is the colour when the mesh has one; otherwise the Base Color (or a texture)
* 14 Skin Types (what the skin is) and 12 Conditions (what is on it), each only its own settings
* every layer from the shape (crevices / ridges measured on the mesh, what faces up, low on the body, thin) - and a
  painted mask attribute ``mch_cm_<layer>`` adds a layer where painted
* the colour layers (skin, mud, dust, blood, dried blood, slime, moss): a colour texture (Flat = the swatch) and
  Hue / Saturation / Value
* sized to the creature: maps, SSS, crevice distances the same on a creature of any size
* its own page on the Material page of the side panel (the skin types and conditions as balls)"""
import os

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import creature_shader as cs, mech_shader_ui as mu

mecha_lab.register()
fresh()
C = bpy.context


def select(*obs):
    for o in C.selected_objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    C.view_layer.objects.active = obs[0]


def monkey(name, size=2.0):
    bpy.ops.mesh.primitive_monkey_add(size=size)
    ob = C.active_object
    ob.name = name
    return ob


def page():
    return mu.content(C, 0.0, 276.0, 1.0)


# ---- the maps
missing = [(slot, k) for slot, items in cs.CMAPS.items() for k, _n in items if cs.cmap_path(slot, k) is None]
check('Every creature map on disk: skin 12, mottle 8, organic 8, colour textures 20',
      [len(cs.CMAPS[s]) for s in ('skin', 'mottle', 'organic', 'color')] == [12, 8, 8, 20] and not missing, missing)
check('14 Skin Types, 12 Conditions; a Condition sets only the layers on top, a Skin Type everything else',
      len(cs.SKINS) == 14 and len(cs.CONDITIONS) == 12 and not set(cs.SKIN_KEYS) & set(cs.COND_KEYS)
      and 'polypaint' not in cs.SKIN_KEYS and 'size' not in cs.SKIN_KEYS)

# ---- on a mesh without polypaint
ob = monkey('Head')
select(ob)
r = bpy.ops.mch.creature_apply(skin='REPTILE', condition='SWAMP')
mat = ob.active_material
st = mat.mch_creature
nodes = mat.node_tree.nodes
check('Apply: a Creature material (Reptile Dry + Swamp Feet), no polypaint on the mesh: Polypaint 0',
      r == {'FINISHED'} and cs.is_creature(mat) and st.skin_type == 'REPTILE' and st.condition == 'SWAMP'
      and st.polypaint == 0.0, (r, mat.name))
check('... the crevices / ridges measured on the mesh (mch_curv), the shader reads them',
      ob.data.attributes.get('mch_curv') is not None and nodes['mch:curv'].attribute_name == 'mch_curv')
check('... sized to the creature (Size = half its largest dimension)', abs(st.size - max(ob.dimensions) / 2) < 1e-4,
      round(st.size, 3))
empty = [n.name for n in nodes if n.type == 'TEX_IMAGE' and n.image is None and not n.name.startswith('mch:img:tex_')]
check('... every map on its node', not empty, empty)
bs = nodes['mch:bsdf']
check('... SSS, coat, thin film, glow and the bump wired into the BSDF',
      all(bs.inputs[n].is_linked for n in ('Subsurface Weight', 'Subsurface Radius', 'Subsurface Scale', 'Coat Weight',
                                           'Thin Film Thickness', 'Emission Strength', 'Normal', 'Base Color')))
check('Swamp Feet: mud from below on, its colour the Wet Mud texture (sRGB), algae for the moss',
      st.mud_low > 0.4 and st.mud_tex == 'WET_MUD' and nodes['mch:img:tex_mud'].image.name.startswith('WET_MUD')
      and nodes['mch:img:tex_mud'].image.colorspace_settings.name == 'sRGB'
      and nodes['mch:use_mud'].outputs[0].default_value == 1.0 and st.moss_tex == 'ALGAE_FILM')

# ---- skin type vs condition
st.skin_type = 'DRAGON'
check('A Skin Type keeps the Condition (Dragon Scales: the mud of Swamp Feet stays)', st.skin_map == 'SCALES_L'
      and st.condition == 'SWAMP' and st.mud_low > 0.4)
st.condition = 'BLOODY'
check('A Condition keeps the skin (Bloody: blood on, the mud gone, still Dragon Scales)', st.blood > 0.0
      and st.mud_low == 0.0 and st.skin_map == 'SCALES_L' and st.blood_tex == 'FRESH_BLOOD'
      and st.blood_dry_tex == 'DRIED_BLOOD')
st.condition = 'CLEAN'
check('Clean: every layer off, every texture Flat', all(getattr(st, k) == 0.0 for k in
                                                        ('mud', 'mud_top', 'mud_low', 'dust', 'soot', 'snow', 'frost',
                                                         'moss', 'blood', 'blood_dry', 'slime', 'wet', 'scars'))
      and all(getattr(st, k + '_tex') == 'FLAT' for k in cs.TEX_LAYERS if k != 'base')
      and nodes['mch:use_mud'].outputs[0].default_value == 0.0 and nodes['mch:img:tex_mud'].image is None)

# ---- colour textures + Hue / Saturation / Value
st.base_tex = 'SCALY_KERATIN'
st.base_hue, st.base_sat, st.base_val = 0.1, 0.5, 1.3
hsv = nodes['mch:hsv:base']
check('A colour texture for the skin (Scaly Keratin) and its Hue / Saturation / Value (user: "휴 · 세츄레이션 · '
      '벨류로 조절")', nodes['mch:img:tex_base'].image.name.startswith('SCALY_KERATIN')
      and nodes['mch:use_base'].outputs[0].default_value == 1.0
      and abs(nodes['mch:base_hue'].outputs[0].default_value - 0.1) < 1e-6
      and abs(nodes['mch:base_sat'].outputs[0].default_value - 0.5) < 1e-6
      and abs(nodes['mch:base_val'].outputs[0].default_value - 1.3) < 1e-6
      and all(hsv.inputs[n].is_linked for n in ('Hue', 'Saturation', 'Value', 'Color')))
check('... every colour layer has them (skin, mud, dust, blood, dried blood, slime, moss)',
      all(nodes.get('mch:hsv:' + k) is not None and nodes.get('mch:img:tex_' + k) is not None for k in cs.TEX_LAYERS)
      and all(hasattr(st, k + sfx) for k in cs.TEX_LAYERS for sfx in ('_tex', '_hue', '_sat', '_val')))
st.base_tex = 'FLAT'
check('... Flat: back to the colour swatch', nodes['mch:use_base'].outputs[0].default_value == 0.0
      and nodes['mch:img:tex_base'].image is None)

# ---- polypaint
ob2 = monkey('Painted')
ob2.location.x = 4
col = ob2.data.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT')
col.data.foreach_set('color', np.tile([0.2, 0.5, 0.1, 1.0], len(ob2.data.vertices)).astype(np.float32))
select(ob2)
bpy.ops.mch.creature_apply(skin='HUMAN', condition='CLEAN')
check('A mesh with polypaint (a colour attribute - ZBrush polypaint in the FBX): Polypaint 1, the paint is the colour',
      ob2.active_material.mch_creature.polypaint == 1.0
      and ob2.active_material.node_tree.nodes['mch:pp_attr'].outputs['Color'].is_linked)

# ---- a painted mask adds its layer, nothing else needs painting
m2 = ob2.active_material
masks = {n.attribute_name for n in m2.node_tree.nodes if n.type == 'ATTRIBUTE' and n.name.startswith('mch:mask:')}
check('Hand masks: the shader reads mch_cm_<layer> for mud, dust, soot, snow, moss, blood, slime, wet, SSS, glow '
      '(no attribute = nothing painted)', masks == {cs.MASK + k for k in cs.MASK_LAYERS}, sorted(masks))

# ---- size
big = monkey('Big', size=40.0)
big.location.x = 60
select(big)
bpy.ops.mch.creature_apply(skin='HIDE')
bst = big.active_material.mch_creature
check('A creature 20 x bigger: Size 20 x, so the maps, SSS and crevices look the same', abs(bst.size / st.size - 20.0)
      < 0.05, (round(bst.size, 2), round(st.size, 2)))

# ---- stepping
select(ob)
for _i in range(len(cs.SKINS)):
    bpy.ops.mch.creature_step(prop='skin_type', step=1)
check('◀ ▶ step through the skin types (all 14, back to the first)', st.skin_type == 'DRAGON')
bpy.ops.mch.creature_step(prop='mud_tex', step=1)
check('... and through a layer\'s colour textures', st.mud_tex == 'WET_MUD')

# ---- the Material page
its, h = page()
heads = {i.label.split('   ')[0] for i in its if i.kind == 'shead'}
tiles = [i for i in its if i.kind == 'mtile']
check('Material page of a Creature material: its own sections (skin types, conditions, colour, skin, SSS, crevices, '
      'the layers)', {'SKIN TYPES', 'CONDITIONS', 'COLOR', 'SKIN', 'SSS', 'CREVICES & RIDGES', 'MUD', 'DUST', 'BLOOD',
                      'SLIME & WET', 'MOSS', 'SNOW & FROST', 'SOOT', 'ROT & WEATHERING', 'GLOW',
                      'HEIGHT & DETAIL'} <= heads, sorted(heads))
check('... the skin types and conditions as balls (26), each with its icon file, the one in use blue',
      len(tiles) == 26 and all(t.icon.startswith('file:') and os.path.isfile(t.icon[5:]) for t in tiles)
      and sorted(t.label for t in tiles if t.on) == sorted(['Dragon Scales', 'Clean']),
      [t.label for t in tiles if not t.icon])
props = {getattr(i, 'prop', '') for i in its}
check('... the colour rows: polypaint, texture stepper, swatch, Hue / Saturation / Value bars',
      {'polypaint', 'base_tex', 'base_color', 'base_hue', 'base_sat', 'base_val'} <= props)
st.mud = 0.4
its, h = page()
props = {getattr(i, 'prop', '') for i in its}
check('... a layer in use opens with its texture + Hue / Saturation / Value (Mud 0.4)',
      {'mud', 'mud_tex', 'mud_color', 'mud_hue', 'mud_sat', 'mud_val', 'mud_cake'} <= props)
cube_ob = bpy.data.objects.new('Plain', bpy.data.meshes.new('plain'))
C.scene.collection.objects.link(cube_ob)
bpy.ops.mesh.primitive_cube_add(location=(0, -8, 0))
plain = C.active_object
select(plain)
its, h = page()
ctiles = [i for i in its if i.kind == 'mtile' and i.action[:2] == ('op', 'mch.creature_apply')]
check('No material: the Mech presets and a Creature Shader section (14 skin-type balls - a click applies one)',
      len(ctiles) == 14 and any(i.kind == 'shead' and i.label.startswith('CREATURE SHADER') for i in its))

# ---- unlink works for a creature material
a = monkey('A')
b2 = monkey('B')
select(a, b2)
bpy.ops.mch.creature_apply(skin='HUMAN')
shared = a.active_material
select(b2)
r = bpy.ops.mch.mech_shader_unlink()
check('Unlink: a part with a shared Creature material gets its own copy', r == {'FINISHED'}
      and b2.active_material != shared and a.active_material == shared and cs.is_creature(b2.active_material))
summary()
