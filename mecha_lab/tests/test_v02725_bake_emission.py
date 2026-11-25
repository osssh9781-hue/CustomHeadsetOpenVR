"""0.24.325 (user: "노말이랑 베이스 컬러, 러프니스, 범프, 메탈릭, 에미션 필요해"): Bake Maps bakes Emission too - the high's
materials' glow onto the low (sRGB, black where none), plugged into the baked material's Emission."""
import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import bake_highpoly as bk, bake_maps as bm

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
st = S.mch_bake
st.res, st.save = '256', False
st.normal = st.ao = st.color = False
check('Emission: a map of its own, off by default', 'EMIT' in bm.MAPS and bm.SUFFIX['EMIT'] == 'Emission' and not st.emit)

bpy.ops.mesh.primitive_ico_sphere_add(radius=1.0, subdivisions=2)
low = C.active_object
low.name = 'Glow'
glow = bpy.data.materials.new('GlowMat')
glow.use_nodes = True
b = glow.node_tree.nodes['Principled BSDF']
b.inputs['Emission Color'].default_value = (1.0, 0.25, 0.0, 1.0)
b.inputs['Emission Strength'].default_value = 1.0
low.data.materials.append(glow)
hp, _i = bk.build(C, low, target_faces=8000)
st.emit = True
info = bm.bake_pair(C, low, [hp], st)
img = bpy.data.images.get('Glow_Emission')
px = np.array(img.pixels[:]).reshape(-1, 4)
lit = px[px[:, 3] > 0.5]
lit = lit[lit[:, :3].sum(1) > 0.05]
mean = lit[:, :3].mean(0) if len(lit) else np.zeros(3)
check(f'Emission baked: the high\'s orange glow on the low (mean {np.round(mean, 2)})', info['maps'] == ['EMIT']
      and len(lit) > 0.2 * len(px) and mean[0] > 0.6 and mean[2] < 0.1)
check('... an sRGB image (a colour map)', img.colorspace_settings.name == 'sRGB')
mat = bpy.data.materials.get('Glow_Baked')
bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
check('... the baked material: Emission Color from the map, Strength 1', bsdf.inputs['Emission Color'].is_linked and
      bsdf.inputs['Emission Strength'].default_value == 1.0)
summary()
