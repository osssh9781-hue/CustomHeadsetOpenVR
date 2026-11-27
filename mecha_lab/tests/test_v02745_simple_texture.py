"""0.24.345 (user: "심플 메테리얼에 베이스 컬러에 텍스처 불러올 수 있게 해 주고 그 소스로 범프랑 러프니스도 다 조절할 수
있게"): a picture on the Simple material's Base Color (Scale / Rotation / UV or Box, Tint / Brightness / Contrast / Hue /
Saturation / Value); its grey makes the Roughness (Amount, Dark / Light, Invert) and the Bump (Strength, Distance,
Invert); Remove Texture puts the sliders back."""
import os
import tempfile

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import bake_maps as bm, side_panel as sp, simple_material as sm

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
# a test picture: a checker of light / dark squares with a colour
W = 64
yy, xx = np.mgrid[0:W, 0:W]
chk = (((xx // 8) + (yy // 8)) % 2).astype(np.float32)
px = np.zeros((W, W, 4), np.float32)
px[..., 0] = 0.2 + 0.7 * chk
px[..., 1] = 0.3 + 0.4 * chk
px[..., 2] = 0.1
px[..., 3] = 1
img0 = bpy.data.images.new('chk', W, W)
img0.pixels.foreach_set(px.ravel())
path = os.path.join(tempfile.mkdtemp(), 'checker.png')
img0.filepath_raw = path
img0.file_format = 'PNG'
img0.save()

bpy.ops.mesh.primitive_cube_add()
cube = C.active_object
bpy.ops.mch.simple_material_new()
mat = cube.active_material
st = mat.mch_simple
st.roughness = 0.5
r = bpy.ops.mch.simple_tex_load('EXEC_DEFAULT', filepath=path)
n = sm.principled(mat)
nd = mat.node_tree.nodes


def src(sock):
    return n.inputs[sock].links[0].from_node.name if n.inputs[sock].is_linked else None


check(f'Load Texture: the picture on the Base Color ({src("Base Color")}), its grey on the Roughness '
      f'({src("Roughness")}) and the Bump ({src("Normal")}); UVs used (the cube has them)',
      r == {'FINISHED'} and st.tex_image is not None and src('Base Color') == 'mchs:tint'
      and src('Roughness') == 'mchs:rough_amount' and src('Normal') == 'mchs:bump' and st.tex_proj == 'UV')
st.tex_scale = 3.0
st.rough_from, st.rough_to = 0.2, 0.9
st.rough_invert = True
st.bump_strength = 0.6
st.tex_tint = (1.0, 0.5, 0.5)
mr = nd['mchs:rough_range']
check('the sliders go straight into the nodes (scale, roughness Dark / Light inverted, bump strength, tint)',
      abs(nd['mchs:map'].inputs['Scale'].default_value[0] - 3.0) < 1e-6
      and abs(mr.inputs['To Min'].default_value - 0.9) < 1e-6 and abs(mr.inputs['To Max'].default_value - 0.2) < 1e-6
      and abs(nd['mchs:bump'].inputs['Strength'].default_value - 0.6) < 1e-6
      and abs(nd['mchs:tint'].inputs['B'].default_value[1] - 0.5) < 1e-6)
# what it bakes to (our own engine evaluates the material): colour, roughness and the bump follow the picture
st.tex_scale = 1.0
st.rough_invert = False
bst = S.mch_bake
bst.res = '256'
bst.own, bst.fast, bst.own_one = True, True, False
bst.normal = bst.color = bst.rough = True
bst.ao = bst.metal = bst.curv = bst.height = bst.emit = False
bst.save = bst.use_on_low = False
for o in S.objects:
    o.select_set(False)
cube.select_set(True)
C.view_layer.objects.active = cube
info = bm.bake_pair(C, cube, [], bst)


def grab(k):
    return np.array(bpy.data.images[f'{cube.name}_{bm.SUFFIX[k]}'].pixels[:]).reshape(256, 256, 4)[..., :3]


col, rgh, nrm = grab('COLOR'), grab('ROUGH'), grab('NORMAL')
check(f'baked: the colour, the roughness ({rgh[..., 0].min():.2f}..{rgh[..., 0].max():.2f}) and the normal map '
      f'(tilt {np.abs(nrm[..., :2] - 0.5).max():.2f}) all follow the picture ({info.get("fast")})',
      col[..., 0].std() > 0.05 and rgh[..., 0].max() - rgh[..., 0].min() > 0.3 and
      np.abs(nrm[..., :2] - 0.5).max() > 0.05 and set(info.get('fast') or []) >= {'COLOR', 'ROUGH', 'NORMAL'})
st.rough_on = False
check('Roughness from Texture off: the Roughness slider back (0.5)',
      not n.inputs['Roughness'].is_linked and abs(n.inputs['Roughness'].default_value - 0.5) < 1e-6)
st.bump_on = False
check('Bump from Texture off: no bump', not n.inputs['Normal'].is_linked and nd.get('mchs:bump') is None)
st.rough_on = st.bump_on = True
C.window_manager.mch_side_page = 'SIMPLE'
items, _h = sp.content(C, 'CUT', 0, 300, 1.0)
labels = [i.label or '' for i in items]
check('the Simple page has a Texture section: Change / Remove, the roughness and bump controls',
      any('TEXTURE' in l_.upper() for l_ in labels) and 'Remove Texture' in labels and 'Change Texture' in labels)
st.base_color = (0.1, 0.6, 0.2)
bpy.ops.mch.simple_tex_remove()
check('Remove Texture: the sliders back in charge (Base Color / Roughness), our nodes gone',
      not n.inputs['Base Color'].is_linked and abs(n.inputs['Base Color'].default_value[1] - 0.6) < 1e-6
      and not n.inputs['Roughness'].is_linked and not any(x.name.startswith('mchs:') for x in nd))
# no UVs: Box
bpy.ops.mesh.primitive_cube_add(location=(4, 0, 0))
c2 = C.active_object
c2.data.uv_layers.remove(c2.data.uv_layers[0])
bpy.ops.mch.simple_material_new()
bpy.ops.mch.simple_tex_load('EXEC_DEFAULT', filepath=path)
check('a mesh without UVs: Box projection (no UVs needed)', c2.active_material.mch_simple.tex_proj == 'BOX'
      and c2.active_material.node_tree.nodes['mchs:image'].projection == 'BOX')
summary()
