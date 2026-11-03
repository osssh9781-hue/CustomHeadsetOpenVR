"""0.24.95 Over My Material + the Overall section + the Project Scale (user: "내가 이미 만들어 놓은 메테리얼에 우리가
만든 메테리얼 연결해서 그 위에 우리가 만든 재질 얹어서", "언링크 버튼은 가장 밑에 전체 헤이트랑 전체 스케일 조정하는 칸에도 -
크리쳐 메테리얼도", "크리쳐 메테리얼에도 가장 밑에다가 전체 조정", "한 프로젝트 할 때는 전부 비슷한 스케일 - 전체적으로 조정,
오브젝트 스케일 쓰면"):

* a part with a material of the user's own: the Mech page / the Creature page offer Layer Over My Material
* Layer Over (Mech): a copy of their material ("<name> + Mech") on the part - their material itself unchanged (kept in
  the file), their nodes in the copy, one Material Output: their surface mixed with ours (chips / scratches / rust /
  dirt / snow), ours a Mech material (its page, its sliders); made anew (an older layout) their nodes stay
* its page: says it is over theirs + Back to Mine, the Surface "under your material", no Paint section
* Unlink in the Overall section at the bottom (Mech and Creature), next to Height / Map Scale; the Creature page has
  the Overall section too
* Back to Mine: their own material back on the part; Layer Over (Creature) the same with the conditions
* the Project Scale: every Mech / Creature material's maps at once; Follow Object Scale on / off into each"""
import json

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import creature_shader as cs, material_overlay as mo, mech_shader as ms, mech_shader_ui as mu

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add()
ob = C.active_object
user = bpy.data.materials.new('My Red')
nt = user.node_tree
bs = nt.nodes['Principled BSDF']
bs.inputs['Base Color'].default_value = (0.8, 0.05, 0.03, 1.0)
noise = nt.nodes.new('ShaderNodeTexNoise')
nt.links.new(noise.outputs['Fac'], bs.inputs['Roughness'])
ob.data.materials.append(user)
before = (sorted(n.name for n in nt.nodes), len(nt.links))


def labels(its, kind='tbtn'):
    return [i.label for i in its if i.kind == kind]


its, _h = mu.content(C, 0.0, 276.0, 1.0)
check('A part with a material of your own: the Mech page offers Layer Over My Material',
      'Layer Over My Material' in labels(its), labels(its))
its, _h = mu.creature_page(C, 0.0, 276.0, 1.0)
check('... and the Creature page', 'Layer Over My Material' in labels(its), labels(its))

r = bpy.ops.mch.material_over(kind='MECH', preset='')
mat = ob.active_material
tree = mat.node_tree
outs = [n for n in tree.nodes if n.bl_idname == 'ShaderNodeOutputMaterial']
mix = tree.nodes.get('mch:over_mix')
check('Layer Over (Mech): a copy "<name> + Mech" on the part - a Mech material over yours (yours unchanged, kept in '
      'the file)', r == {'FINISHED'} and mat.name == 'My Red + Mech' and ms.is_mech(mat) and mo.is_over(mat)
      and (sorted(n.name for n in nt.nodes), len(nt.links)) == before and user.use_fake_user
      and mo.source_of(mat) == user)
check('... your nodes in it, one Material Output: your surface mixed with ours (where no chip / scratch / rust / dirt '
      '/ snow covers it)', all(tree.nodes.get(n) for n in json.loads(mat[mo.NODES])) and len(outs) == 1
      and mix is not None and mix.inputs[2].links[0].from_node.name == 'Principled BSDF'
      and mix.inputs[1].links[0].from_node.name == 'mch:bsdf'
      and mix.inputs[0].links[0].from_node.name == 'mch:over_vis'
      and tree.nodes['mch:over_vis'].outputs[0].links and outs[0].inputs['Surface'].is_linked,
      [n.name for n in outs])
mat['mch_mech'] = 1                                   # (an older layout: made anew on the next sync)
getattr(mat, ms.KEY).edge_wear = 0.4
check('... made anew (an older layout): your nodes stay, ours over them again',
      mat['mch_mech'] == ms.VERSION and all(mat.node_tree.nodes.get(n) for n in json.loads(mat[mo.NODES]))
      and mat.node_tree.nodes.get('mch:over_mix') is not None
      and len([n for n in mat.node_tree.nodes if n.bl_idname == 'ShaderNodeOutputMaterial']) == 1)

its, _h = mu.content(C, 0.0, 276.0, 1.0)
heads = labels(its, 'shead')
check('Its page: says it is over yours + Back to Mine; the Surface "under your material", no Paint section',
      'Back to Mine' in labels(its) and any(h.startswith('SURFACE - UNDER YOUR MATERIAL') for h in heads)
      and not any(h.startswith('PAINT') for h in heads), heads)
check('... the Overall section at the very bottom: Height, Map Scale, the Project Scale - and Unlink there too',
      heads[-1].startswith('OVERALL') and labels(its).count('Unlink') == 2
      and any(getattr(i, 'prop', '') == 'mch_map_scale' for i in its)
      and any(getattr(i, 'prop', '') == 'map_scale' for i in its), heads[-3:])

bpy.ops.mesh.primitive_cube_add(location=(3.0, 0.0, 0.0))
ob2 = C.active_object
ob2.data.materials.append(mat)
r = bpy.ops.mch.mech_shader_unlink()
m2 = ob2.active_material
check('Unlink on a laid-over material: its own copy, still over yours (your nodes in it)',
      r == {'FINISHED'} and m2 != mat and mo.is_over(m2) and m2.node_tree.nodes.get('mch:over_mix') is not None
      and all(m2.node_tree.nodes.get(n) for n in json.loads(m2[mo.NODES])))
bpy.data.objects.remove(ob2)
C.view_layer.objects.active = ob
ob.select_set(True)
r = bpy.ops.mch.material_over_back()
check('Back to Mine: your own material back on the part', r == {'FINISHED'} and ob.active_material == user)

r = bpy.ops.mch.material_over(kind='CREATURE', preset='')
cm = ob.active_material
check('Layer Over (Creature): "<name> + Creature", a Creature material over yours (the conditions on top)',
      r == {'FINISHED'} and cm.name == 'My Red + Creature' and cs.is_creature(cm) and mo.is_over(cm)
      and cm.node_tree.nodes.get('mch:over_mix') is not None and getattr(cm, cs.KEY).condition == mo.DEFAULT_COND)
its, _h = mu.creature_page(C, 0.0, 276.0, 1.0)
heads = labels(its, 'shead')
check('The Creature page: Back to Mine, and the Overall section at its bottom (Height, Map Scale, the Project Scale, '
      'Unlink)', 'Back to Mine' in labels(its) and heads[-1].startswith('OVERALL') and labels(its).count('Unlink') == 2
      and any(getattr(i, 'prop', '') == 'mch_map_scale' for i in its), heads[-3:])

# the Project Scale / Follow Object Scale
plain = ms.new_material('STEEL')
crea = cs.new_material('HUMAN')
S.mch_map_scale = 2.5
vals = [m.node_tree.nodes['mch:project_scale'].outputs[0].default_value for m in (plain, crea, cm)]
check('The Project Scale: every Mech / Creature material\'s maps at once (a plain Mech, a Creature, a laid-over one)',
      all(abs(v - 2.5) < 1e-6 for v in vals), vals)
S.mch_obj_scale = False
vals = [m.node_tree.nodes['mch:obj_scale'].outputs[0].default_value for m in (plain, crea, cm)]
check('Follow Object Scale off: each material\'s maps on the plain object coordinates', all(v == 0.0 for v in vals),
      vals)
S.mch_obj_scale, S.mch_map_scale = True, 1.0
nd = plain.node_tree.nodes['mch:obj_axes']
check('... on (the default): the maps x the object\'s own scale (its axes taken to the world)',
      plain.node_tree.nodes['mch:obj_scale'].outputs[0].default_value == 1.0
      and all(s.is_linked for s in nd.inputs[:3]))
summary()
