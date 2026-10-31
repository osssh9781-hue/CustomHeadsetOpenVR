"""0.24.95 Bake Maps (user: "우리 만든 거 내가 베이크도 할 수 있게 베이킹 툴도 만들어 주라, 우리 거 리메시나 그런 거 한
거 말이야"): a part and its Bake High Poly copy find each other; Cycles Selected to Active bakes Normal / AO / Color onto
the part; the scene is put back as it was; the part gets a material with the maps."""
import inspect
import os
import tempfile

import numpy as np
from _harness import bpy, check, fresh, select_only, summary

import mecha_lab
from mecha_lab import bake_highpoly as bk, bake_maps as bm, mesh_tools, zb_ui

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
st = S.mch_bake
st.res, st.ao_samples, st.save = '256', 16, False

# the "low": a faceted ball (no UVs), its own material; the "high": Bake High Poly of it (round)
bpy.ops.mesh.primitive_ico_sphere_add(radius=1.0, subdivisions=2)
low = C.active_object
low.name = 'Part'
while low.data.uv_layers:
    low.data.uv_layers.remove(low.data.uv_layers[0])
paint = bpy.data.materials.new('PartPaint')
paint.use_nodes = True
low.data.materials.append(paint)
n_nodes = len(paint.node_tree.nodes)
hp, _info = bk.build(C, low, target_faces=20000)
hco = np.array([v.co[:] for v in hp.data.vertices])           # detail only the high has: ripples round the ball
hco += hco / np.linalg.norm(hco, axis=1)[:, None] * (0.03 * np.sin(14.0 * hco[:, 2]))[:, None]
hp.data.vertices.foreach_set('co', hco.ravel())
hp.data.update()
check('setup: the part and its BakeHP copy (the part hidden, the copy selected)', bk.is_bake(hp) and hp[bk.SRC_KEY] == 'Part'
      and low.hide_get() and hp.select_get())

# ---- which meshes
select_only(hp)
check('pairs: the BakeHP copy alone selected -> its part is the low, the copy the high', bm.pairs(C) == [(low, [hp])])
low.hide_set(False)
select_only(low)
check('pairs: the part alone selected -> its BakeHP copy is the high', bm.pairs(C) == [(low, [hp])])
low.select_set(True)
hp.select_set(True)
check('pairs: both selected -> one pair (not two)', bm.pairs(C) == [(low, [hp])])
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(5, 0, 0))
lone = C.active_object
select_only(lone)
try:
    bm.pairs(C)
    refused = False
except RuntimeError as ex:
    refused = 'select' in str(ex)
check('pairs: a mesh with no copy and nothing else selected -> refused with a hint', refused)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(5, 0, 0))
other = C.active_object
other.select_set(True)
lone.select_set(True)
C.view_layer.objects.active = lone
check('pairs: the classic way - the active mesh is the low, the other selected the high', bm.pairs(C) == [(lone, [other])])

# ---- the bake
engine0 = S.render.engine
samples0 = S.cycles.samples
bake0 = (S.render.bake.cage_extrusion, S.render.bake.max_ray_distance, S.render.bake.use_selected_to_active, S.render.bake.margin)
world0 = S.world
low.hide_set(True)
select_only(hp)
msg = bm.run(C)
info = dict(bm.LAST)
check('Bake Maps on the BakeHP copy: Normal + AO baked onto the part, Smart UV made (it had none)',
      info['maps'] == ['NORMAL', 'AO'] and info['low'] == 'Part' and info['highs'] == [hp.name] and info['uv'] == 'smart'
      and len(low.data.uv_layers) == 1, msg)
nimg = bpy.data.images.get('Part_Normal')
aimg = bpy.data.images.get('Part_AO')
check('... images "<part>_Normal" / "_AO" at Size (256), non-colour data, packed (the .blend is not saved)',
      nimg is not None and aimg is not None and tuple(nimg.size) == (256, 256) and nimg.colorspace_settings.name == 'Non-Color'
      and aimg.colorspace_settings.name == 'Non-Color' and nimg.packed_file is not None and aimg.packed_file is not None)
N = np.array(nimg.pixels[:]).reshape(256, 256, 4)[..., :3]
A = np.array(aimg.pixels[:]).reshape(256, 256, 4)[..., 0]
inside = A > 0.02                                          # (baked pixels; outside the islands + margin stays black)
check('... the maps cover the UV islands (a good share of the image), AO of a ball is light (nothing shades it)',
      inside.mean() > 0.3 and A[inside].mean() > 0.85, (inside.mean(), A[inside].mean()))
nn = N[inside]
check('... the normal map: blue up (tangent space), red / green vary (the high\'s ripples), no empty pixels',
      nn[:, 2].mean() > 0.85 and nn[:, 0].std() > 0.01 and nn[:, 1].std() > 0.01 and np.linalg.norm(nn * 2 - 1, axis=1).min() > 0.5,
      (nn.mean(0), nn.std(0)))
check('The scene is put back: engine, samples, bake settings, no world left behind, the temporary bake material and ray cage gone',
      S.render.engine == engine0 and S.cycles.samples == samples0 and S.world == world0 and bm.TARGET_MAT not in bpy.data.materials
      and bm.CAGE not in bpy.data.objects and bm.CAGE not in bpy.data.meshes
      and (S.render.bake.cage_extrusion, S.render.bake.max_ray_distance, S.render.bake.use_selected_to_active, S.render.bake.margin) == bake0)
check('Show Low: the part shown, selected and active, the copy hidden', not low.hide_get() and low.select_get()
      and C.view_layer.objects.active == low and hp.hide_get())
mat = low.material_slots[0].material
nt = mat.node_tree
bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
nmap = next((n for n in nt.nodes if n.type == 'NORMAL_MAP'), None)
check('Use on Low: the part gets "Part_Baked" - the normal map into the BSDF normal, AO x base colour into Base Color',
      mat.name == 'Part_Baked' and nmap is not None and bsdf.inputs['Normal'].is_linked and bsdf.inputs['Base Color'].is_linked
      and any(n.type == 'TEX_IMAGE' and n.image == aimg for n in nt.nodes) and any(n.type == 'TEX_IMAGE' and n.image == nimg for n in nt.nodes))
check('... the part\'s own material is not edited (still there, same nodes) - and the BakeHP copy keeps it',
      bpy.data.materials.get('PartPaint') is not None and len(paint.node_tree.nodes) == n_nodes and hp.material_slots[0].material == paint)
check('Smooth Low: the part is smooth shaded (a ball: no edge bent past 60 degrees, so no sharp edges)',
      all(p.use_smooth for p in low.data.polygons) and info['sharp'] == 0)

# ---- again: the same images, the UVs kept; Color from the high's material
b = next(n for n in paint.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
b.inputs['Base Color'].default_value = (0.8, 0.05, 0.05, 1.0)
st.color = True
select_only(low)
bm.run(C)
check('Bake again (the part alone selected): the same images (no ".001"), the UVs kept',
      bm.LAST['uv'] == 'kept' and not any(i.name.startswith('Part_Normal.') for i in bpy.data.images)
      and len(low.data.uv_layers) == 1 and bm.LAST['maps'] == ['NORMAL', 'AO', 'COLOR'])
cimg = bpy.data.images['Part_Color']
Cc = np.array(cimg.pixels[:]).reshape(256, 256, 4)[..., :3][inside]
check('Color: the high\'s base colour (red) baked, sRGB', cimg.colorspace_settings.name == 'sRGB'
      and Cc[:, 0].mean() > 2 * Cc[:, 1].mean() and Cc[:, 0].mean() > 2 * Cc[:, 2].mean(), tuple(Cc.mean(0)))
st.color = False

# ---- DirectX: green flipped
g_gl = N[..., 1][inside]
st.green = 'DIRECTX'
select_only(low)
bm.run(C)
g_dx = np.array(bpy.data.images['Part_Normal'].pixels[:]).reshape(256, 256, 4)[..., 1][inside]
dev = np.abs(g_gl - 0.5) > 0.03
check('Green DirectX: the green channel flipped (1 - OpenGL\'s)', dev.sum() > 50 and np.abs(g_dx[dev] - (1.0 - g_gl[dev])).mean() < 0.03,
      (int(dev.sum()), np.abs(g_dx[dev] - (1.0 - g_gl[dev])).mean()))
gm = bpy.data.materials['Part_Baked'].node_tree
check('... and the material flips it back for Blender (Separate / 1 - G / Combine before the Normal Map)',
      any(n.type == 'SEPRGB' or n.bl_idname == 'ShaderNodeSeparateColor' for n in gm.nodes)
      and any(n.bl_idname == 'ShaderNodeCombineColor' for n in gm.nodes))
st.green = 'OPENGL'

# ---- Others Shade AO
bpy.ops.mesh.primitive_cube_add(size=3.0, location=(2.15, 0, 0))     # a wall right next to the ball
wall = C.active_object
wall.name = 'Wall'
st.ao_distance = 40.0
select_only(low)
bm.run(C)
a_off = np.array(bpy.data.images['Part_AO'].pixels[:]).reshape(256, 256, 4)[..., 0][inside].mean()
st.ao_others = True
select_only(low)
bm.run(C)
a_on = np.array(bpy.data.images['Part_AO'].pixels[:]).reshape(256, 256, 4)[..., 0][inside].mean()
check('Others Shade AO off: a wall next to the part does not darken its AO; on: it does', a_on < a_off - 0.02 and a_off > 0.85, (a_off, a_on))
check('... the wall is put back to render (hide_render off again)', not wall.hide_render)
st.ao_others = False
bpy.data.objects.remove(wall)

# ---- Save PNGs next to a saved .blend
tmp = tempfile.mkdtemp(prefix='mch_bake_')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(tmp, 'bake_test.blend'))
low = bpy.data.objects['Part']
st.save = True
select_only(low)
msg = bm.run(C)
png = os.path.join(tmp, 'bake_maps', 'Part_Normal.png')
img = bpy.data.images['Part_Normal']
check('Save PNGs (the .blend saved): the maps written to //bake_maps/ next to it, the images point there (not packed)',
      os.path.isfile(png) and os.path.isfile(os.path.join(tmp, 'bake_maps', 'Part_AO.png')) and img.filepath.startswith('//bake_maps')
      and img.packed_file is None, (msg, img.filepath))

# ---- the operator + the panels
select_only(low)
r = bpy.ops.mch.bake_maps()
check('The operator mch.bake_maps runs (Object Mode)', r == {'FINISHED'})
check('In the Mecha Lab tab (Mesh Tools) and the ZBrush tab, under Bake High Poly',
      'bake_maps.draw' in inspect.getsource(mesh_tools.draw) and 'bake_maps.draw' in inspect.getsource(zb_ui)
      and "'mch.bake_maps'" in inspect.getsource(bm.draw))
summary()
