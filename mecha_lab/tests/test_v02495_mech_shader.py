"""0.24.95 Mech Shader (user: "메카닉 쉐이더 프리셋 - 플라스틱, 쇠, 페인트, 까진 페인트, 흙, 눈, 기스, 녹, 에미션, 천 - 슬라이더로,
러프니스 같은 맵은 각자 프리셋 10개 정도, 넘기면 바로바로 바뀌게"; "프로시저럴 말고 러프니스 맵이랑 베이스 맵 직접 만들어서"):
a material of layers whose patterns are texture maps made for it (mech_maps/, 10 per slot, seamless, box-projected),
material presets that set every slider and map, and steps that swap a map / preset at once.
Then (user: "범프맵 연결해서 하이트 조절하게 해 주고 좀 더 리얼하게 해 줘, 그리고 HDRI도 깔아서"): every Base map has a
height map of its own, each layer a Height slider (scratch depth, chip depth, rust / dirt / snow thickness, weave
relief) into one Bump node, a Clear Coat, AO crevices, and one of Blender's built-in HDRIs as the scene's world."""
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
missing += [('base', k + '_height') for k, _l in ms.MAPS['base'][3] if ms.map_path('base', k + '_height') is None]
check('Ten maps per slot (Base + its height map, Roughness, Chips, Scratches, Rust colour + mask, Dirt, Snow, Emission, Weave), all '
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
# coarse flats (boolean / Simple-subdivided parts): a big flat face is only a few points from its bevel - the wear must
# not run across it.  Before: 93 % of the mech test part's area read as an edge (the paint all chipped off).
bpy.ops.mesh.primitive_cube_add(location=(0, 6, 0))
cq = C.active_object
cq.modifiers.new('b', 'BEVEL').width = 0.03
cq.modifiers['b'].segments = 3
sub = cq.modifiers.new('s', 'SUBSURF')
sub.subdivision_type, sub.levels = 'SIMPLE', 2
bpy.ops.object.convert(target='MESH')
ms.store_curvature(cq.data)
kq = np.zeros(len(cq.data.vertices))
cq.data.attributes[ms.CURV].data.foreach_get('value', kq)
cqo = np.array([v.co[:] for v in cq.data.vertices])
on_bevel = (np.abs(cqo) > 0.975).sum(1) >= 2
mid = ((np.abs(cqo) > 0.999).sum(1) == 1) & (np.abs(cqo).min(1) < 0.9)
check('Coarse flat faces (bevel + Simple subdivision): the faces read flat (before: up to a full edge), the bevels '
      'clearly more', np.abs(kq[mid]).max() < 0.15 and kq[on_bevel].mean() > max(0.12, 3 * np.abs(kq[mid]).mean()),
      (round(float(np.abs(kq[mid]).max()), 3), round(float(kq[on_bevel].mean()), 2), int(mid.sum())))
bpy.ops.mesh.primitive_cube_add(location=(0, 9, 0))
lp = C.active_object
ms.store_curvature(lp.data)
kl = np.zeros(8)
lp.data.attributes[ms.CURV].data.foreach_get('value', kl)
check('... a low-poly cube (8 points, sharp): its corners are full edges', kl.min() > 0.99, kl.round(2).tolist())
for o in (cq, lp):
    bpy.data.objects.remove(o)
for o in C.selected_objects:
    o.select_set(False)
ob.select_set(True)
C.view_layer.objects.active = ob
nodes = mat.node_tree.nodes
check('... every slot\'s map on its image node (box projection: no UVs needed), the data maps Non-Color',
      all(nodes['mch:img:' + s].image is not None and nodes['mch:img:' + s].projection == 'BOX'
          for s in ms.MAP_KEYS) and nodes['mch:img:rough'].image.colorspace_settings.name == 'Non-Color'
      and nodes['mch:img:base'].image.colorspace_settings.name == 'sRGB')
check('... the Base map\'s height map on its own node (Non-Color)', nodes['mch:img:base_h'].image is not None
      and nodes['mch:img:base_h'].image.name.startswith(st.base_map + '_height')
      and nodes['mch:img:base_h'].image.colorspace_settings.name == 'Non-Color')
bump = next(n for n in nodes if n.bl_idname == 'ShaderNodeBump')
check('... one Bump node into the BSDF\'s Normal, its Height fed (the layers\' heights)',
      bump.inputs['Height'].is_linked and nodes['mch:bsdf'].inputs['Normal'].links
      and nodes['mch:bsdf'].inputs['Normal'].links[0].from_node == bump)
check('... the fixed maps on their nodes (dust, grime streaks, colour variation)',
      all(nodes['mch:img:' + k].image is not None for k in ms.FIXED), [k for k in ms.FIXED])
check('... brushed metal: Anisotropic and a world-space Tangent wired',
      nodes['mch:bsdf'].inputs['Anisotropic'].is_linked and nodes['mch:bsdf'].inputs['Tangent'].links[0].from_node
      == nodes['mch:tangent'] and nodes['mch:tangent'].convert_to == 'WORLD')
check('... Clear Coat and AO crevices wired', nodes['mch:bsdf'].inputs['Coat Weight'].is_linked
      and nodes['mch:ao_node'].bl_idname == 'ShaderNodeAmbientOcclusion'
      and nodes['mch:ao'].bl_idname == 'ShaderNodeValue' and nodes['mch:ao_node'].outputs['AO'].is_linked)
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
st.h_weave, st.bump, st.coat = 0.33, 2.5, 0.8
check('... the Height sliders too (Weave Height, Height, Clear Coat)',
      abs(nodes['mch:h_weave'].outputs[0].default_value - 0.33) < 1e-6
      and abs(nodes['mch:bump'].outputs[0].default_value - 2.5) < 1e-6
      and abs(nodes['mch:coat'].outputs[0].default_value - 0.8) < 1e-6)
st.base_map = 'CAST'
check('... a Base map step brings its own height map', nodes['mch:img:base_h'].image.name.startswith('CAST_height'))
spec = dict((p[0], p[2]) for p in ms.PRESETS)
check('Metals at measured reflectance: Steel about 0.56, Aluminium about 0.91 (linear), Brass yellow, Copper red',
      abs(spec['STEEL']['base_color'][0] - 0.56) < 0.03 and spec['BRUSHED']['base_color'][0] > 0.78
      and spec['BRASS']['base_color'][2] < spec['BRASS']['base_color'][0] * 0.6
      and spec['COPPER']['base_color'][0] > spec['COPPER']['base_color'][1] > spec['COPPER']['base_color'][2],
      [tuple(round(x, 2) for x in spec[k]['base_color']) for k in ('STEEL', 'BRUSHED', 'BRASS', 'COPPER')])
check('Chipped paint in layers: paint, a primer band, then metal (Chipped / Battle Worn); Camo shows its pattern in '
      'the paint; Muddy gathers its mud low', spec['CHIPPED']['primer'] > 0 and spec['BATTLE']['primer'] > 0
      and spec['CAMO']['paint_pattern'] == 1.0 and spec['MUDDY']['dirt_low'] > 0.5)
st.preset = 'CARBON'
check('Carbon Fibre: its weave finer (Map Scale 2); the next preset puts Map Scale back',
      st.map_scale == 2.0 and abs(mat.node_tree.nodes['mch:map_scale'].outputs[0].default_value - 2.0) < 1e-6)
st.preset = 'PAINTED'
check('... (Painted Metal: Map Scale 1)', st.map_scale == 1.0)
check('... Brushed Aluminium brushed, Dirty Metal dusty and streaked', spec['BRUSHED']['aniso'] > 0.5
      and spec['DIRTY']['dust'] > 0 and spec['DIRTY']['streaks'] > 0)
mat['mch_mech'] = 3
nodes.remove(nodes['mch:tangent'])
st.dust = 0.5
check('A Mech material from before (node layout 3): made anew at the next change',
      mat['mch_mech'] == ms.VERSION and mat.node_tree.nodes.get('mch:tangent') is not None)
nodes = mat.node_tree.nodes

# ---- 0.24.95 (user: "베이스 컬러, 러프니스, 메탈릭, 유리 재질, 알파 다 만질 수 있게"; "스노우가 너무 칼같이 떨어지는 거
# 같고, 흙도 안에 낀 거 / 바깥에 위에 묻은 거 / 아래 묻은 거 슬라이드로")
st.preset = 'GLASS'
bs = mat.node_tree.nodes['mch:bsdf']
check('Glass: see-through (Transmission wired, IOR 1.5), metallic 0, EEVEE refraction on the material',
      bs.inputs['Transmission Weight'].is_linked and bs.inputs['IOR'].is_linked and st.glass == 1.0
      and st.metallic == 0.0 and getattr(mat, 'use_raytrace_refraction', True))
st.preset = 'HOLO'
check('Hologram: Alpha 0.35 (wired), the material blends (EEVEE: smooth see-through)', bs.inputs['Alpha'].is_linked
      and abs(st.alpha - 0.35) < 1e-6 and mat.surface_render_method == 'BLENDED')
st.preset = 'STEEL'
check('... a plain preset: solid again (no refraction, dithered)', st.glass == 0.0 and st.alpha == 1.0
      and not getattr(mat, 'use_raytrace_refraction', False) and mat.surface_render_method == 'DITHERED')
st.glass, st.ior, st.alpha = 0.6, 1.33, 0.8
nd = mat.node_tree.nodes
check('... Glass / IOR / Alpha sliders in the nodes at once', abs(nd['mch:glass'].outputs[0].default_value - 0.6) < 1e-6
      and abs(nd['mch:ior'].outputs[0].default_value - 1.33) < 1e-6
      and abs(nd['mch:alpha'].outputs[0].default_value - 0.8) < 1e-6)
st.snow_soft, st.dirt_top, st.dirt_low, st.dirt = 0.45, 0.3, 0.4, 0.2
check('Snow Softness and the three dirts (in crevices / on top / from below) in the nodes',
      abs(nd['mch:snow_soft'].outputs[0].default_value - 0.45) < 1e-6
      and abs(nd['mch:dirt_top'].outputs[0].default_value - 0.3) < 1e-6
      and abs(nd['mch:dirt_low'].outputs[0].default_value - 0.4) < 1e-6
      and abs(nd['mch:dirt'].outputs[0].default_value - 0.2) < 1e-6)
check('... Muddy Paint: mud low, on top and in the crevices', spec['MUDDY']['dirt_low'] > 0.5
      and spec['MUDDY']['dirt_top'] > 0 and spec['MUDDY']['dirt'] > 0)
st.preset = 'CLOTH'

# ---- no Mech material yet: stepping the preset applies it
bpy.ops.mesh.primitive_uv_sphere_add(location=(4, 0, 0))
sp = C.active_object
bpy.ops.mch.mech_shader_step(prop='preset', step=1)
check('A mesh without one: stepping the preset puts a Mech material on it', ms.is_mech(sp.active_material))

# ---- the HDRI: Blender's own, the scene's world only when asked, Off gives the old one back
sc = C.scene
old = bpy.data.worlds.new('my world')
sc.world = old
files = ms.hdri_files()
check('Blender\'s built-in HDRIs found (city, courtyard, forest, interior, night, studio, sunrise, sunset)',
      len(files) >= 8 and 'courtyard.exr' in files, files)
sc.mch_mech_hdri = 'courtyard.exr'
check('... picking one does not change the scene\'s world by itself', sc.world == old)
r = bpy.ops.mch.mech_hdri(action='SET')
w = sc.world
env = w.node_tree.nodes['mch:env']
check('Set HDRI: the scene\'s world is the HDRI (Environment Texture of courtyard.exr)', r == {'FINISHED'}
      and ms.hdri_world(sc) == w and env.image is not None and env.image.filepath.endswith('courtyard.exr'))
sc.mch_mech_hdri_strength, sc.mch_mech_hdri_rot = 2.0, 1.0
check('... Strength / Rotation move it at once', abs(w.node_tree.nodes['mch:bg'].inputs['Strength'].default_value - 2)
      < 1e-6 and abs(w.node_tree.nodes['mch:map'].inputs['Rotation'].default_value[2] - 1.0) < 1e-6)
bpy.ops.mch.mech_hdri(action='SET', step=1)
check('... the arrow steps to the next HDRI', sc.mch_mech_hdri == 'forest.exr'
      and w.node_tree.nodes['mch:env'].image.filepath.endswith('forest.exr') and sc.world == w)
# 0.24.95 (user: "hdri 파일은 다운받아서 폴더에 넣어 놓고 그거 연결해서 불러오게, 블러를 넣어 주는 거야"): a folder of
# the user's own, blur behind the model
import shutil
import tempfile
from mecha_lab import workspace_ui
mine = tempfile.mkdtemp(prefix='mch_hdri_')
shutil.copy(os.path.join(ms.hdri_dir(), 'sunset.exr'), os.path.join(mine, 'my_sky.exr'))
real_pref = workspace_ui.pref
workspace_ui.pref = lambda name, default=True: mine if name == 'hdri_folder' else real_pref(name, default)
try:
    ids = [i[0] for i in ms._hdri_items(None, C)]
    check('HDRI Folder (Preferences, also in the HDRI box): its files listed first (*), the built-in ones after',
          ids[0] == 'U:my_sky.exr' and 'courtyard.exr' in ids, ids[:3])
    sc.mch_mech_hdri = 'U:my_sky.exr'
    r = bpy.ops.mch.mech_hdri(action='SET')
    env = sc.world.node_tree.nodes['mch:env']
    check('... Set HDRI on one: the scene\'s world shows that file', r == {'FINISHED'}
          and os.path.normcase(bpy.path.abspath(env.image.filepath)) == os.path.normcase(os.path.join(mine, 'my_sky.exr')))
    nt = sc.world.node_tree
    sc.mch_mech_hdri_blur = 0.6
    eb = nt.nodes['mch:env_blur']
    check('Background Blur: the camera sees a blurred copy (smaller, kept in the file), the lighting the sharp HDRI',
          eb.image is not None and eb.image.name == ms.BLUR_IMAGE and eb.image.size[0] < env.image.size[0]
          and nt.nodes['mch:blur_on'].outputs[0].default_value == 1.0 and eb.image.packed_file is not None,
          (eb.image and tuple(eb.image.size), tuple(env.image.size)))
    sc.mch_mech_hdri_blur = 0.0
    check('... Blur 0: the sharp HDRI behind the model again', nt.nodes['mch:blur_on'].outputs[0].default_value == 0.0)
finally:
    workspace_ui.pref = real_pref
    shutil.rmtree(mine, ignore_errors=True)
bpy.ops.mch.mech_hdri(action='OFF')
check('Off: the world the scene had is back', sc.world == old)

# ---- the panel
root = capture(lambda layout, context: ms.draw(layout, context), C)


def walk(n):
    yield n
    for ch in n.children:
        yield from walk(ch)


props = {n.prop for n in walk(root) if n.kind == 'prop'}
check('Panel: the preset, every map with its slider and Height, Clear Coat, AO, Map Scale and the HDRI',
      {'preset', 'base_map', 'rough_map', 'chip_map', 'scratch_map', 'rust_map', 'dirt_map', 'snow_map', 'emit_map',
       'weave_map', 'edge_wear', 'scratches', 'rust', 'rust_scratch', 'dirt', 'snow', 'emission', 'cloth',
       'roughness', 'map_scale', 'bump', 'h_base', 'h_scratch', 'h_chip', 'h_rust', 'h_dirt', 'h_snow', 'h_weave',
       'coat', 'ao', 'aniso', 'dust', 'streaks', 'variation', 'primer', 'primer_color', 'paint_pattern',
       'dirt_low', 'glass', 'alpha', 'snow_soft', 'dirt_top', 'mch_mech_hdri_blur', 'mch_mech_hdri', 'mch_mech_hdri_strength',
       'mch_mech_hdri_rot'} <= props, sorted(props))
summary()
