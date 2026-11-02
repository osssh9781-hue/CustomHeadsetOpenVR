"""0.24.95 Bake to Polypaint (user: "폴리페인트로 구워 줘"):

* the material's colour (no light) into a point colour layer "Baked Color" (float) - a Mech part with a blue Paint Zone
  on red paint: the zone's points blue, the rest red; it becomes the active layer
* the materials put back exactly (no node left over, the output fed as before), the scene's engine / samples and
  the selection as they were
* a creature with polypaint: the layer the Creature Shader reads (the default one) stays as it was; Mud baked in
* a plain Principled material (its colour); a material with no Principled (its diffuse colour)
* two meshes at once (the operator); the Mech / Creature pages: a Bake section
* ZBrush Send's OBJ: the active colour layer (the bake) as vertex colours"""
import math
import os
import tempfile

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import bake_material as bk, mech_shader_ui as mu, zbrush_bridge as zb, zones as zn

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
RW = RH = 1000


def colours(ob, layer=bk.LAYER):
    att = ob.data.color_attributes[layer]
    a = np.empty(len(att.data) * 4, np.float32)
    att.data.foreach_get('color', a)
    return a.reshape(-1, 4)[:, :3]


def points(ob):
    co = np.empty(len(ob.data.vertices) * 3)
    ob.data.vertices.foreach_get('co', co)
    return co.reshape(-1, 3)


def select(*obs):
    for o in C.selected_objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    C.view_layer.objects.active = obs[0]


# ---- a Mech part: red paint, a blue Paint Zone on its front
bpy.ops.mesh.primitive_cube_add(size=2.0)
part = C.active_object
part.name = 'Part'
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.subdivide(number_cuts=24)
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.mch.mech_shader_apply(preset='PAINTED')
mat = part.active_material
st = mat.mch_mech
st.paint_color = (0.6, 0.05, 0.04)
st.edge_wear = st.scratches = st.dirt = st.rust = 0.0
cd = bpy.data.cameras.new('Cam')
cam = bpy.data.objects.new('Cam', cd)
S.collection.objects.link(cam)
cam.location, cam.rotation_euler = (0.0, -6.0, 0.0), (math.radians(90), 0.0, 0.0)
C.view_layer.update()
vm = cam.matrix_world.inverted()
wm = cam.calc_matrix_camera(C.evaluated_depsgraph_get(), x=RW, y=RH)


def to_px(co):
    v = wm @ vm @ Vector((*co, 1.0))
    return ((v.x / v.w * 0.5 + 0.5) * RW, (v.y / v.w * 0.5 + 0.5) * RH)


zn.add_paint_zone(C, part, [to_px(c) for c in ((-0.5, -1, -0.5), (0.5, -1, -0.5), (0.5, -1, 0.5), (-0.5, -1, 0.5))],
                  vm, wm, True, RW, RH, color=(0.05, 0.15, 0.7))
S.render.engine = 'BLENDER_EEVEE'
S.cycles.samples = 77
nodes_before = sorted(n.name for n in mat.node_tree.nodes)
links_before = len(mat.node_tree.links)
select(part)
info = bk.bake_polypaint(C, [part])
col = colours(part)
co = points(part)
front = (np.abs(co[:, 1] + 1) < 1e-4) & (np.abs(co[:, 0]) < 0.4) & (np.abs(co[:, 2]) < 0.4)
side = np.abs(co[:, 0] - 1) < 1e-4
att = part.data.color_attributes[bk.LAYER]
check('Bake to Polypaint (a Mech part): a point colour layer "Baked Color" (float), the active one', info[0][1] ==
      len(part.data.vertices) and att.domain == 'POINT' and att.data_type == 'FLOAT_COLOR'
      and part.data.color_attributes.active_color_name == bk.LAYER)
fb, sr = col[front].mean(0), col[side].mean(0)
check('... the zone\'s points blue, the rest red (the paint): the material\'s own colour, no light',
      fb[2] > fb[0] * 3 and sr[0] > sr[2] * 3 and front.sum() > 50, (np.round(fb, 3).tolist(), np.round(sr, 3).tolist()))
out = next(n for n in mat.node_tree.nodes if n.type == 'OUTPUT_MATERIAL')
check('... the material as it was (no node left over, the output fed by its BSDF)',
      sorted(n.name for n in mat.node_tree.nodes) == nodes_before and len(mat.node_tree.links) == links_before
      and out.inputs['Surface'].links[0].from_node.name == 'mch:bsdf')
check('... the scene as it was (engine, samples, the selection)', S.render.engine == 'BLENDER_EEVEE'
      and S.cycles.samples == 77 and C.active_object == part and part.select_get())

# ---- a creature with polypaint
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=48, ring_count=24, location=(4, 0, 0))
crea = C.active_object
pp = crea.data.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT')
pp.data.foreach_set('color', np.tile([0.1, 0.5, 0.1, 1.0], len(pp.data)).astype(np.float32))
crea.data.color_attributes.render_color_index = crea.data.color_attributes.find('Col')
bpy.ops.mch.creature_apply(skin='REPTILE', condition='CLEAN')
cst = crea.active_material.mch_creature
cst.polypaint = 1.0
cst.mottle = cst.variation = cst.belly = 0.0
r = bpy.ops.mch.bake_polypaint()
g = colours(crea).mean(0)
check('A creature with polypaint: baked (the green polypaint through the shader)', r == {'FINISHED'} and g[1] > g[0]
      and g[1] > g[2], np.round(g, 3).tolist())
check('... the layer the Creature Shader reads (the default, "Col") stays the default and as it was',
      crea.data.color_attributes.default_color_name == 'Col' and np.allclose(colours(crea, 'Col').mean(0),
                                                                              (0.1, 0.5, 0.1), atol=1e-6))
cst.mud = 0.9
bpy.ops.mch.bake_polypaint()
m = colours(crea).mean(0)
check('... Mud 0.9 baked in (browner: less green than before), the same layer written over',
      m[1] < g[1] * 0.85 and len([a for a in crea.data.color_attributes if a.name == bk.LAYER]) == 1,
      np.round(m, 3).tolist())

# ---- plain materials
bpy.ops.mesh.primitive_ico_sphere_add(location=(8, 0, 0))
plain = C.active_object
pm = bpy.data.materials.new('Green')
pm.use_nodes = True
pm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.1, 0.6, 0.15, 1.0)
plain.data.materials.append(pm)
bpy.ops.mesh.primitive_ico_sphere_add(location=(8, 4, 0))
diff = C.active_object
dm = bpy.data.materials.new('Diffuse Only')
dm.use_nodes = True
nt = dm.node_tree
nt.nodes.remove(nt.nodes['Principled BSDF'])
dfn = nt.nodes.new('ShaderNodeBsdfDiffuse')
dfn.inputs['Color'].default_value = (0.7, 0.3, 0.05, 1.0)
nt.links.new(dfn.outputs['BSDF'], nt.nodes['Material Output'].inputs['Surface'])
diff.data.materials.append(dm)
select(plain, diff)
r = bpy.ops.mch.bake_polypaint()
pg, dg = colours(plain).mean(0), colours(diff).mean(0)
check('Two meshes at once: a plain Principled material (its green 0.1 / 0.6 / 0.15) and one with no Principled (its '
      'diffuse colour 0.7 / 0.3 / 0.05)', r == {'FINISHED'} and np.allclose(pg, (0.1, 0.6, 0.15), atol=0.01)
      and np.allclose(dg, (0.7, 0.3, 0.05), atol=0.03), (np.round(pg, 3).tolist(), np.round(dg, 3).tolist()))

# ---- the pages, the ZBrush OBJ
select(part)
its, _h = mu.content(C, 0.0, 276.0, 1.0)
heads = {i.label.split('   ')[0]: i for i in its if i.kind == 'shead'}
check('The Mech page: a Bake section (open once baked) - Bake to Polypaint, Show Polypaint',
      'BAKE' in heads and heads['BAKE'].on and {'Bake to Polypaint', 'Show Polypaint'} <= {i.label for i in its
                                                                                           if i.kind == 'tbtn'})
select(crea)
its, _h = mu.creature_page(C, 0.0, 276.0, 1.0)
check('... and on the Creature page', any(i.kind == 'tbtn' and i.label == 'Bake to Polypaint' for i in its))
tmp = zb.export_copy(C, crea, False)
path = os.path.join(tempfile.mkdtemp(), 'c.obj')
select(tmp)
bpy.ops.wm.obj_export(filepath=path, export_selected_objects=True, export_colors=True, export_materials=False)
v = next(ln for ln in open(path) if ln.startswith('v '))
check('ZBrush Send\'s copy keeps the bake as the active colour layer; the OBJ carries it (v x y z r g b)',
      tmp.data.color_attributes.active_color_name == bk.LAYER and len(v.split()) == 7, v.strip())
bpy.data.objects.remove(tmp)
summary()
