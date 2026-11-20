"""0.24.263 (user: "메크랑 크리쳐 말고 심플 메테리얼 하나 - 쉐이더 창처럼 나오는 건데 기본으로 프린시플처럼 작동하는 거"):
a Simple page beside Mech / Creature: New Simple Material puts a plain Principled material on the selected meshes; its
settings grouped like the shader panel go straight into the Principled node; an existing Principled material can be
taken over (its values read in); a socket fed by a texture is left alone."""
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import side_panel as sp, simple_material as sm  # noqa: E402

mecha_lab.register(); fresh()
C = bpy.context
S = C.scene
bpy.ops.mesh.primitive_cube_add(); a = C.active_object
bpy.ops.mesh.primitive_uv_sphere_add(location=(3, 0, 0)); b_ = C.active_object
a.select_set(True); b_.select_set(True)
check('the Simple tab sits beside Mech and Creature', list(sp.PAGES)[:3] == ['MATERIAL', 'CREATURE', 'SIMPLE'])
r = bpy.ops.mch.simple_material_new()
mat = a.active_material
check('New Simple Material: one plain Principled material on both selected meshes',
      r == {'FINISHED'} and mat is not None and mat is b_.active_material and sm.is_simple(mat) and sm.principled(mat) is not None)
st = mat.mch_simple
st.base_color = (0.9, 0.1, 0.05); st.metallic = 1.0; st.roughness = 0.2; st.emission = 3.0; st.coat = 0.5
n = sm.principled(mat)
check('the settings go straight into the Principled node (colour, metallic, roughness, emission, coat)',
      abs(n.inputs['Base Color'].default_value[0] - 0.9) < 1e-6 and n.inputs['Metallic'].default_value == 1.0
      and abs(n.inputs['Roughness'].default_value - 0.2) < 1e-6 and n.inputs['Emission Strength'].default_value == 3.0
      and n.inputs['Coat Weight'].default_value == 0.5)
st.alpha = 0.4
check('Alpha under 1: see-through (blended)', abs(n.inputs['Alpha'].default_value - 0.4) < 1e-6
      and getattr(mat, 'surface_render_method', 'BLENDED') == 'BLENDED')
tex = mat.node_tree.nodes.new('ShaderNodeTexNoise')
mat.node_tree.links.new(tex.outputs['Fac'], n.inputs['Roughness'])
st.roughness = 0.9
check('a socket fed by a texture is left alone', n.inputs['Roughness'].is_linked and abs(n.inputs['Roughness'].default_value - 0.2) < 1e-6)
# an existing material taken over
other = bpy.data.materials.new('Painted'); other.use_nodes = True
sm.principled(other).inputs['Metallic'].default_value = 0.7
sm.principled(other).inputs['Base Color'].default_value = (0.1, 0.4, 0.2, 1)
bpy.ops.mesh.primitive_cube_add(location=(6, 0, 0)); c = C.active_object; c.data.materials.append(other)
check('a plain material: "Use This Material" offered', not sm.is_simple(other) and bpy.ops.mch.simple_material_adopt.poll())
bpy.ops.mch.simple_material_adopt()
check('... taken over: its values read in', sm.is_simple(other) and abs(other.mch_simple.metallic - 0.7) < 1e-6
      and abs(other.mch_simple.base_color[1] - 0.4) < 1e-6)
C.window_manager.mch_side_page = 'SIMPLE'
items, h = sp.content(C, 'CUT', 0, 300, 1.0)
kinds = [(i.kind, i.label) for i in items]
check(f'the Simple page: a colour swatch, number bars, the sections ({len(items)} rows)',
      any(k_ == 'swatch' for k_, _l in kinds) and any(k_ == 'mini' for k_, _l in kinds)
      and any('SURFACE' in (l_ or '') for _k, l_ in kinds) and any('EMISSION' in (l_ or '') for _k, l_ in kinds))
# 0.24.264 (user: "심플 메테리얼에 메테리얼 링크 끊는 것도") a shared material: Break Material Link gives the selected their own copy
for o in list(C.selected_objects):
    o.select_set(False)
a.select_set(True); C.view_layer.objects.active = a
shared = a.active_material
check(f'a material shared by {sm.shared_count(shared)} objects: Break Material Link offered', sm.shared_count(shared) == 2
      and bpy.ops.mch.simple_material_single.poll())
bpy.ops.mch.simple_material_single()
check('... the selected one gets its own copy (still a Simple material), the other keeps the original',
      a.active_material is not shared and b_.active_material is shared and sm.is_simple(a.active_material)
      and abs(a.active_material.mch_simple.metallic - shared.mch_simple.metallic) < 1e-6)
a.active_material.mch_simple.base_color = (0.0, 1.0, 0.0)
check('... changing it no longer changes the other', abs(sm.principled(shared).inputs['Base Color'].default_value[1] - 0.1) < 1e-6)
summary()
