"""0.24.95 Mech Shader: Base Color Hue / Saturation / Value (user: "베이스 컬러 컬러 조절 탭에 휴 · 새츄레이션 · 밸류
조절 탭도 넣어 줘"):

* three sliders under Base Color (the Mech page's Surface section and the N panel): Hue (-0.5 .. 0.5), Saturation
  (0 .. 2), Value (0 .. 2) - the base colour with its Base map; at 0 / 1 / 1 the material as before
* rendered (a red plastic, lit evenly): Saturation 0 grey, Hue 0.5 the opposite hue (cyan), Value 0.4 darker
* the Base map's colour goes through it too (Camo: Saturation 0 makes it grey)
* a Mech material made before (no HSV node): made anew on the next change; a preset puts them back to 0 / 1 / 1"""
import os
import tempfile

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import mech_shader as ms, mech_shader_ui as mu

fresh()
mecha_lab.register()
C = bpy.context
sc = C.scene
PX = 48

bpy.ops.mesh.primitive_plane_add(size=2.0)
part = C.active_object
part.rotation_euler = (1.5708, 0.0, 0.0)
bpy.ops.mch.mech_shader_apply(preset='PLASTIC_MATTE')
mat = part.active_material
st = mat.mch_mech
st.base_color = (0.6, 0.05, 0.05)
st.base_map = 'FLAT'
st.variation = 0.0
st.h_base = 0.0
st.roughness = 1.0
st.rough_amount = 0.0
w = bpy.data.worlds.new('W')
w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)
sc.world = w
cd = bpy.data.cameras.new('Cam')
cd.type = 'ORTHO'
cd.ortho_scale = 1.0
cam = bpy.data.objects.new('Cam', cd)
sc.collection.objects.link(cam)
cam.location, cam.rotation_euler = (0.0, -4.0, 0.0), (1.5708, 0.0, 0.0)
sc.camera = cam
sc.render.engine = 'CYCLES'
sc.cycles.samples = 8
sc.cycles.use_denoising = False
sc.render.resolution_x = sc.render.resolution_y = PX
sc.view_settings.view_transform = 'Standard'


def colour():
    p = os.path.join(tempfile.mkdtemp(), 'r.png')
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(p)
    a = np.array(img.pixels[:]).reshape(PX, PX, 4)[PX // 2 - 4:PX // 2 + 4, PX // 2 - 4:PX // 2 + 4, :3]
    bpy.data.images.remove(img)
    return a.reshape(-1, 3).mean(0)


rna = ms.MCH_PG_MechShader.bl_rna.properties
nd = mat.node_tree.nodes.get('mch:hsv:base')
check('Base Color Hue / Saturation / Value: three sliders (Hue -0.5 .. 0.5, Saturation and Value 0 .. 2) into a '
      'Hue / Saturation node after the base colour and its map', nd is not None and nd.inputs['Hue'].is_linked
      and rna['base_hue'].hard_min == -0.5 and rna['base_hue'].hard_max == 0.5 and rna['base_sat'].hard_max == 2.0
      and rna['base_val'].hard_max == 2.0 and (st.base_hue, st.base_sat, st.base_val) == (0.0, 1.0, 1.0)
      and ms.VERSION == 12)
red = colour()
st.base_sat = 0.0
grey = colour()
st.base_sat = 1.0
st.base_hue = 0.5
cyan = colour()
st.base_hue = 0.0
st.base_val = 0.4
dark = colour()
st.base_val = 1.0
check('Rendered: red as it was at 0 / 1 / 1; Saturation 0 grey; Hue 0.5 the opposite hue (cyan); Value 0.4 darker',
      red[0] > red[2] * 2.2 and abs(grey[0] - grey[2]) < 0.03 and cyan[2] > cyan[0] * 2 and cyan[1] > cyan[0] * 2
      and dark.sum() < red.sum() * 0.75,
      [np.round(c_, 3).tolist() for c_ in (red, grey, cyan, dark)])
st.base_map = 'CAMO'
camo = colour()
st.base_sat = 0.0
camo_grey = colour()
st.base_sat = 1.0
check('... the Base map\'s colour too (Camo: Saturation 0 makes it grey)', abs(camo_grey[0] - camo_grey[1]) < 0.03
      and abs(camo_grey[1] - camo_grey[2]) < 0.03, (np.round(camo, 3).tolist(), np.round(camo_grey, 3).tolist()))
its, _h = mu.content(C, 0.0, 276.0, 1.0)
props = [getattr(i, 'prop', '') for i in its]
check('The Mech page (Surface): Hue / Sat / Val right under Base Color',
      'base_color' in props and props[props.index('base_color') + 1:props.index('base_color') + 4]
      == ['base_hue', 'base_sat', 'base_val'], props[:12])
# a material from before
mat['mch_mech'] = 11
mat.node_tree.nodes.remove(mat.node_tree.nodes['mch:hsv:base'])
st.base_val = 0.9
check('A Mech material made before (no HSV node): made anew on the next change, the value in it',
      mat.get('mch_mech') == ms.VERSION and mat.node_tree.nodes.get('mch:hsv:base') is not None
      and abs(mat.node_tree.nodes['mch:base_val'].outputs[0].default_value - 0.9) < 1e-6)
st.base_hue, st.base_sat = 0.2, 1.5
st.preset = 'STEEL'
check('... a preset puts them back to 0 / 1 / 1', (st.base_hue, st.base_sat, st.base_val) == (0.0, 1.0, 1.0))
summary()
