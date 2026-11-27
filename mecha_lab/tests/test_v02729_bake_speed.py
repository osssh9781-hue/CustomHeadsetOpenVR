"""0.24.329 (user: "베이크가 아직도 너무 느려" + a review of the code): No High Poly - samples by need (Quality for a
shader with AO / Bevel nodes, 2 for one without), no glow -> the Emission map black without a bake, Roughness + Metallic
in one bake, the AO map capped by the Quality; High to Low - the curvature / height only when baked; Bake to Polypaint
on the GPU when it is on."""
import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import bake_maps as bm, bake_highpoly as bk

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
st = S.mch_bake
st.res, st.save, st.use_on_low = '256', False, False
check('Quality: Normal by default (8 / AO at most 32); Draft 4 / 16; High 16 / AO Samples',
      st.quality == 'NORMAL' and bm.QUALITY_SAMPLES == {'DRAFT': 4, 'NORMAL': 8, 'HIGH': 16}
      and bm.AO_CAP == {'DRAFT': 16, 'NORMAL': 32})

plain = bpy.data.materials.new('Plain')
plain.use_nodes = True
ray = bpy.data.materials.new('Ray')
ray.use_nodes = True
g = bpy.data.node_groups.new('EdgesG', 'ShaderNodeTree')
g.nodes.new('ShaderNodeAmbientOcclusion')
gn = ray.node_tree.nodes.new('ShaderNodeGroup')
gn.node_tree = g
check('AO / Bevel nodes found (inside a group too); none in a plain material',
      bm.has_ray_nodes([ray]) and not bm.has_ray_nodes([plain]))
check('glow: none in a plain Principled; an Emission Strength makes one',
      not bm.glows([plain]))
plain2 = plain.copy()
plain2.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 2.0
check('... (Emission Strength 2: it glows)', bm.glows([plain2]))

bpy.ops.mesh.primitive_cube_add(size=2.0)
ob = C.active_object
ob.name = 'Box'
ob.data.materials.append(plain)
for o in C.selected_objects:
    o.select_set(False)
ob.select_set(True)
C.view_layer.objects.active = ob
st.own = True
for k in ('normal', 'ao', 'color', 'rough', 'metal', 'emit', 'height', 'curv'):
    setattr(st, k, False)
st.emit = True
bm.run(C)
img = bpy.data.images['Box_Emission']
px = np.array(img.pixels[:]).reshape(-1, 4)
check('no glow anywhere: the Emission map black (filled, not baked)', float(px[:, :3].max()) == 0.0
      and float(px[:, 3].min()) == 1.0)

# High to Low, Metallic only: no height walk
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, location=(5, 0, 0))
lo = C.active_object
lo.data.materials.append(plain)
hp, _i = bk.build(C, lo, target_faces=5000)
st.own = False
st.emit = False
st.metal = True
seen = {}
real = bm._height


def spy(*a, **k):
    seen['height'] = True
    return real(*a, **k)


bm._height = spy
bm.bake_pair(C, lo, [hp], st)
check('High to Low, Metallic only: the height over the low not computed (it walked every point)', 'height' not in seen)
st.metal = False
st.height = True
bm.bake_pair(C, lo, [hp], st)
check('... Height asked: computed', seen.get('height') is True)
bm._height = real
st.height = False

# Bake to Polypaint: on the GPU when it is on
from mecha_lab import bake_material as bmat
used = []
real_gpu = bm.use_gpu
bm.use_gpu = lambda context: used.append(1) or False
try:
    bmat.bake_polypaint(C, [lo])
finally:
    bm.use_gpu = real_gpu
check('Bake to Polypaint asks for the GPU (this machine has none: CPU, the scene put back)', bool(used)
      and S.cycles.device == 'CPU')
summary()
