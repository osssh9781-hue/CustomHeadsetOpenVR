"""0.24.325 (user: "베이크 하이폴리 안 하고는 못 해?"): Bake Maps - No High Poly: a mesh's own material baked onto its own
UVs (Normal from its shader's bump, Color, Roughness, Metallic, Emission, AO); Height / Curvature left out; its
materials kept in the file."""
import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import bake_maps as bm

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
st = S.mch_bake
st.res, st.save, st.ao_samples = '256', False, 8
check('No High Poly: off by default (as before)', not st.own)

bpy.ops.mesh.primitive_cube_add(size=2.0)
ob = C.active_object
ob.name = 'Gun'
while ob.data.uv_layers:
    ob.data.uv_layers.remove(ob.data.uv_layers[0])
m = bpy.data.materials.new('Proc')
m.use_nodes = True
nt = m.node_tree
b = nt.nodes['Principled BSDF']
chk = nt.nodes.new('ShaderNodeTexChecker')
chk.inputs['Scale'].default_value = 4.0
chk.inputs['Color1'].default_value = (1.0, 0.3, 0.0, 1.0)
chk.inputs['Color2'].default_value = (0.02, 0.02, 0.02, 1.0)
nt.links.new(chk.outputs['Color'], b.inputs['Base Color'])
nt.links.new(chk.outputs['Fac'], b.inputs['Metallic'])
b.inputs['Roughness'].default_value = 0.3
b.inputs['Emission Color'].default_value = (0.0, 1.0, 0.0, 1.0)
b.inputs['Emission Strength'].default_value = 1.0
bump = nt.nodes.new('ShaderNodeBump')
nt.links.new(chk.outputs['Fac'], bump.inputs['Height'])
nt.links.new(bump.outputs['Normal'], b.inputs['Normal'])
ob.data.materials.append(m)
for o in C.selected_objects:
    o.select_set(False)
ob.select_set(True)
C.view_layer.objects.active = ob
try:
    bm.pairs(C)
    refused = False
except RuntimeError:
    refused = True
check('No High Poly off: one mesh alone still asks for a high (as before)', refused)
st.own = True
check('No High Poly on: the selected mesh pairs with itself', bm.pairs(C) == [(ob, [])])
st.normal = st.ao = st.color = st.rough = st.metal = st.emit = st.height = True
msg = bm.run(C)
info = bm.LAST
check(f'baked: {", ".join(info["maps"])}; Height left out (needs a high) - {msg[:80]}',
      info['maps'] == ['NORMAL', 'AO', 'COLOR', 'ROUGH', 'METAL', 'EMIT'] and info['skipped'] == ['HEIGHT']
      and 'needs a high poly' in msg)
check('... UVs made (it had none)', info['uv'] == 'smart' and len(ob.data.uv_layers) == 1)


def raw(kind):
    img = bpy.data.images.get(f'Gun_{bm.SUFFIX[kind]}')
    return np.array(img.pixels[:]).reshape(-1, 4)[:, :3]


COVER = raw('EMIT')[:, 1] > 0.05                       # (the pixels the UVs cover: the green glow everywhere)


def px(kind):
    return raw(kind)[COVER]


col = px('COLOR')
check('Color: the checker\'s two colours (orange - on the metal squares too - and near black)', (col[:, 0] > 0.8).mean() > 0.2 and
      (col.sum(1) < 0.6).mean() > 0.2, str(np.round([(col[:, 0] > 0.8).mean(), (col.sum(1) < 0.6).mean()], 2)))
met = px('METAL')
check('Metallic: 0 / 1 squares (its Metallic glowed)', (met[:, 0] > 0.9).mean() > 0.2 and (met[:, 0] < 0.1).mean() > 0.2)
rough = px('ROUGH')
check(f'Roughness: 0.3 ({rough[:, 0].mean():.2f})', abs(rough[:, 0].mean() - 0.3) < 0.05)
em = px('EMIT')
check('Emission: green', em[:, 1].mean() > 0.8 and em[:, 0].mean() < 0.1)
nrm = px('NORMAL')
check('Normal: its shader\'s bump shows (not all flat blue)', np.ptp(nrm[:, 0]) > 0.1)
check('the material in its slot: the baked one; the original kept in the file (fake user)',
      ob.material_slots[0].material.name == 'Gun_Baked' and bpy.data.materials.get('Proc') is not None
      and bpy.data.materials['Proc'].use_fake_user)
check('... no bake node left in the original', not any(n.name.startswith('.MCH Bake') for n in m.node_tree.nodes))

# 0.24.326 (user, the Remesh window's Retopo + Bake box: "어디 있어?") the same there: No High Poly + 2 Bake
from mecha_lab import retopo_bake as rb
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(5, 0, 0))
ob2 = C.active_object
ob2.name = 'Gun2'
ob2.data.materials.append(m)
for o in C.selected_objects:
    o.select_set(False)
ob2.select_set(True)
C.view_layer.objects.active = ob2
st.normal = st.ao = st.rough = st.metal = st.emit = st.height = False
st.color = True
check('Retopo + Bake box: No High Poly on -> the selected mesh is ready for 2 Bake (no Retopo)',
      rb.own_meshes(C) == [ob2] and bpy.ops.mch.retopo_bake.poll())
r = bpy.ops.mch.retopo_bake('EXEC_DEFAULT')
img2 = bpy.data.images.get('Gun2_Color')
check('... 2 Bake: its own material baked onto it', r == {'FINISHED'} and img2 is not None and
      ob2.material_slots[0].material.name == 'Gun2_Baked')
st.own = False
check('No High Poly off: nothing to bake there without a low (as before)', rb.own_meshes(C) == [])
summary()
