"""0.24.95 Mech Shader (user: "메카닉 쉐이더 프리셋 - 플라스틱, 쇠, 페인트, 까진 페인트, 흙, 눈, 기스, 녹, 에미션, 천 - 슬라이더로,
러프니스 같은 맵은 각자 프리셋 10개 정도, 넘기면 바로바로 바뀌게"; "프로시저럴 말고 러프니스 맵이랑 베이스 맵 직접 만들어서"):
a material of layers whose patterns are texture maps made for it (mech_maps/, 10 per slot, seamless, box-projected),
material presets that set every slider and map, and steps that swap a map / preset at once."""
import os

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import mech_shader as ms
from mecha_lab.panel_capture import capture

mecha_lab.register()
fresh()
C = bpy.context

# ---- the maps: ten per slot, every one on disk, seamless
missing = [(s, k) for s in ms.MAP_KEYS for k, _l in ms.MAPS[s][3] if ms.map_path(s, k) is None]
missing += [('rust', k + '_mask') for k, _l in ms.MAPS['rust'][3] if ms.map_path('rust', k + '_mask') is None]
check('Ten maps per slot (Base, Roughness, Chips, Scratches, Rust colour + mask, Dirt, Snow, Emission, Weave), all '
      'on disk', all(len(ms.MAPS[s][3]) == 10 for s in ms.MAP_KEYS) and not missing, missing)
seam = []
for slot, ident in (('rough', 'SMUDGE'), ('base', 'MOTTLED'), ('dirt', 'MUD'), ('snow', 'PATCHY'), ('chip', 'BIG')):
    img = bpy.data.images.load(ms.map_path(slot, ident))
    w, h = img.size
    px = np.array(img.pixels[:]).reshape(h, w, 4)[..., 0]
    across = np.abs(px[:, 0] - px[:, -1]).mean()                 # (the wrap: last column next to the first)
    inside = np.abs(px[:, 1:] - px[:, :-1]).mean()               # (any two neighbouring columns)
    seam.append((slot, round(float(across), 4), round(float(inside), 4)))
check('... seamless: across the tile\'s edge the map changes no more than between any two neighbouring pixels',
      all(a <= 2.5 * i + 0.01 for _s, a, i in seam), seam)

# ---- apply to a bevelled block
bpy.ops.mesh.primitive_cube_add()
ob = C.active_object
ob.modifiers.new('b', 'BEVEL').width = 0.1
ob.modifiers['b'].segments = 3
ob.modifiers.new('s', 'SUBSURF').levels = 2
bpy.ops.object.convert(target='MESH')
r = bpy.ops.mch.mech_shader_apply(preset='CHIPPED')
mat = ob.active_material
st = mat.mch_mech
k = np.zeros(len(ob.data.vertices))
ob.data.attributes[ms.CURV].data.foreach_get('value', k)
co = np.array([v.co[:] for v in ob.data.vertices])
corner = np.abs(co).min(1) > 0.85                                # (points on the bevelled edges / corners)
flat = np.abs(co).max(1) > 0.99
flat &= (np.abs(co) > 0.99).sum(1) == 1
flat &= np.abs(co).min(1) < 0.5                                  # (the middle of a face)
check('Apply: a Mech material on the block (Chipped Paint), its edges measured: the bevels convex, the face middles '
      'flat', r == {'FINISHED'} and ms.is_mech(mat) and st.preset == 'CHIPPED' and k[corner].mean() > 0.5
      and np.abs(k[flat]).mean() < 0.1, (round(float(k[corner].mean()), 2), round(float(np.abs(k[flat]).mean()), 3)))
nodes = mat.node_tree.nodes
check('... every slot\'s map on its image node (box projection: no UVs needed), the data maps Non-Color',
      all(nodes['mch:img:' + s].image is not None and nodes['mch:img:' + s].projection == 'BOX'
          for s in ms.MAP_KEYS) and nodes['mch:img:rough'].image.colorspace_settings.name == 'Non-Color'
      and nodes['mch:img:base'].image.colorspace_settings.name == 'sRGB')
check('... the sliders in the nodes (Paint 1, Edge Wear 0.35)', abs(nodes['mch:paint'].outputs[0].default_value - 1.0)
      < 1e-6 and abs(nodes['mch:edge_wear'].outputs[0].default_value - 0.35) < 1e-6)

# ---- steps: a map / a preset swaps at once
before = nodes['mch:img:scratch'].image.name
bpy.ops.mch.mech_shader_step(prop='scratch_map', step=1)
check('Step the Scratches map: the next map is on the node at once', st.scratch_map == 'LONG'
      and nodes['mch:img:scratch'].image.name.startswith('LONG') and before.startswith('FINE'), (before,))
seen = set()
for _i in range(10):
    bpy.ops.mch.mech_shader_step(prop='rough_map', step=1)
    seen.add(nodes['mch:img:rough'].image.name)
check('... all ten Roughness maps in turn, back to the first', len(seen) == 10 and st.rough_map == 'SMUDGE', seen)
bpy.ops.mch.mech_shader_step(prop='rust_map', step=-1)
check('... the Rust map brings its own mask', nodes['mch:img:rust_mask'].image.name.startswith(st.rust_map + '_mask'))
names = []
for _i in range(len(ms.PRESETS)):
    bpy.ops.mch.mech_shader_step(prop='preset', step=1)
    names.append(st.preset)
check(f'Step through all {len(ms.PRESETS)} material presets: each sets its sliders and maps (plastic, metals, paint, '
      'chips, scratches, rust, dirt, snow, emission, cloth)', len(set(names)) == len(ms.PRESETS)
      and st.preset == 'CHIPPED')
st.preset = 'SNOWY'
check('Snowy Metal: snow on, the snow map on its node, metallic underneath', st.snow > 0.3
      and nodes['mch:img:snow'].image.name.startswith('PATCHY') and abs(nodes['mch:snow'].outputs[0].default_value
                                                                         - st.snow) < 1e-6)
st.preset = 'GLOW_SCRATCH'
check('Glowing Scratches: emission on the scratches (the source weights)', st.emission > 1
      and nodes['mch:emit_w_scratch'].outputs[0].default_value == 1.0
      and nodes['mch:emit_w_const'].outputs[0].default_value == 0.0)
st.preset = 'CLOTH'
check('Cloth Canvas: cloth on (weave + sheen), not metallic', st.cloth == 1.0 and st.metallic == 0.0
      and nodes['mch:img:weave'].image.name.startswith('CANVAS'))
st.roughness = 0.9
check('A slider moved: in the node at once', abs(nodes['mch:roughness'].outputs[0].default_value - 0.9) < 1e-6)
check('Preset colours picked on screen are stored linear (Steel\'s 0.56 grey -> about 0.27)',
      abs(dict((p[0], p[2]) for p in ms.PRESETS)['STEEL']['base_color'][0] - 0.274) < 0.01)

# ---- no Mech material yet: stepping the preset applies it
bpy.ops.mesh.primitive_uv_sphere_add(location=(4, 0, 0))
sp = C.active_object
bpy.ops.mch.mech_shader_step(prop='preset', step=1)
check('A mesh without one: stepping the preset puts a Mech material on it', ms.is_mech(sp.active_material))

# ---- the panel
root = capture(lambda layout, context: ms.draw(layout, context), C)


def walk(n):
    yield n
    for ch in n.children:
        yield from walk(ch)


props = {n.prop for n in walk(root) if n.kind == 'prop'}
check('Panel: the preset and every map with its slider (and Map Scale, Relief)',
      {'preset', 'base_map', 'rough_map', 'chip_map', 'scratch_map', 'rust_map', 'dirt_map', 'snow_map', 'emit_map',
       'weave_map', 'edge_wear', 'scratches', 'rust', 'rust_scratch', 'dirt', 'snow', 'emission', 'cloth',
       'roughness', 'map_scale', 'bump'} <= props, sorted(props))
summary()
