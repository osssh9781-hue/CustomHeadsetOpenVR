"""0.24.95 Creature parts (user picked "눈(젖은 각막 + 홍채), 이빨, 잇몸 · 혀, 발톱"):

* Teeth / Enamel, Gums / Tongue, Claw / Nail: Creature Shader presets, listed after the 14 skin types (saved files
  keep their skin type), shown under Parts
* the Eye: a material of its own for a separate eye object - its box is the eyeball (Generated coordinates: its
  origin and size do not matter), Looks Along = its front axis; iris, pupil (round / slit / horizontal), limbal ring,
  fibres, veins on the white, a wet cornea (clear coat), glow; 7 eyes (human brown / blue, reptile, cat, goat, glowing,
  undead / blind)
* the Material page: a Parts grid (4 balls) under the Creature Shader, the eye's own page"""
import os

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import creature_shader as cs, mech_shader_ui as mu

mecha_lab.register()
fresh()
C = bpy.context
OLD = ['HUMAN', 'REPTILE', 'SNAKE', 'AMPHIBIAN', 'HIDE', 'DRAGON', 'CHITIN', 'MEMBRANE', 'ALIEN', 'SHARK', 'RUBBER',
       'UNDEAD', 'DEMON', 'BONE']


def page():
    return mu.content(C, 0.0, 276.0, 1.0)


def heads(its):
    return {i.label.split('   ')[0]: i for i in its if i.kind == 'shead'}


check('Teeth, Gums / Tongue, Claw after the 14 skin types (old files keep theirs), 4 parts with the eye',
      list(cs.SKIN_IDS[:14]) == OLD and list(cs.SKIN_IDS[14:]) == ['TEETH', 'GUMS', 'CLAW']
      and [k for k, _n in cs.PARTS] == ['EYE', 'TEETH', 'GUMS', 'CLAW'])

bpy.ops.mesh.primitive_monkey_add()
head = C.active_object
r = bpy.ops.mch.creature_part(part='TEETH')
st = head.active_material.mch_creature
check('Teeth on a mesh: a Creature material, Teeth / Enamel (ivory, translucent tips, yellowed crevices), sized',
      r == {'FINISHED'} and cs.is_creature(head.active_material) and st.skin_type == 'TEETH' and st.sss > 0.2
      and st.sss_thin > 1.0 and abs(st.size - max(head.dimensions) / 2) < 1e-4)
its, _h = page()
ptiles = [i for i in its if i.kind == 'mtile' and i.action[:2] == ('op', 'mch.creature_part')]
check('... the creature page: Parts open (a part is on it) with 4 balls, each its icon; the skin types without '
      'the parts', 'PARTS' in heads(its) and len(ptiles) == 4
      and all(t.icon.startswith('file:') and os.path.isfile(t.icon[5:]) for t in ptiles)
      and len([i for i in its if i.kind == 'mtile' and i.prop == 'skin_type']) == 14)

bpy.ops.mesh.primitive_uv_sphere_add(radius=0.3, location=(3, 2, 1))
eye = C.active_object
r = bpy.ops.mch.creature_part(part='EYE')
emat = eye.active_material
est = emat.mch_eye
nodes = emat.node_tree.nodes
check('Eye on a sphere: an eye material (Human Brown), its own settings', r == {'FINISHED'} and cs.is_eye(emat)
      and not cs.is_creature(emat) and est.eye_type == 'HUMAN' and est.pupil_shape == 'ROUND')
check('... read from the eye\'s own box (Generated): looks along -Y by default',
      tuple(nodes['mch:axis_f'].inputs[i].default_value for i in range(3)) == (0.0, -1.0, 0.0)
      and any(n.type == 'TEX_COORD' and n.outputs['Generated'].is_linked for n in nodes))
est.front = '+X'
est.pupil_shape = 'SLIT'
check('... Looks Along +X / a slit pupil: the axis and the pupil\'s shape on the nodes at once',
      tuple(nodes['mch:axis_f'].inputs[i].default_value for i in range(3)) == (1.0, 0.0, 0.0)
      and abs(nodes['mch:pupil_ax'].outputs[0].default_value - 0.22) < 1e-6)
est.eye_type = 'GOAT'
check('Goat / Demon eye: a horizontal pupil, a big yellow iris', est.pupil_shape == 'HORIZONTAL'
      and est.iris_size > 0.7 and est.iris_color1[0] > est.iris_color1[2])
est.eye_type = 'GLOW'
bs = nodes['mch:bsdf']
check('Glowing eye: the iris glows (emission linked, strength 4)', est.glow == 4.0
      and bs.inputs['Emission Strength'].is_linked and nodes['mch:glow'].outputs[0].default_value == 4.0)
check('... the cornea: a clear wet coat (Coat Weight = Wet, roughness 0.02, IOR 1.376)',
      bs.inputs['Coat Weight'].is_linked and abs(bs.inputs['Coat Roughness'].default_value - 0.02) < 1e-6)
bpy.ops.mch.creature_step(prop='eye_type', step=1)
check('◀ ▶ step through the eyes', est.eye_type == 'MILKY' and est.pupil_size == 0.0)
its, _h = page()
etiles = [i for i in its if i.kind == 'mtile']
props = {getattr(i, 'prop', '') for i in its}
check('The eye\'s own page: Eyes (7 balls with icons), Iris & Pupil, White / Cornea / Glow',
      {'EYES', 'IRIS & PUPIL', 'WHITE, CORNEA & GLOW'} <= set(heads(its)) and len(etiles) == 7
      and all(t.icon.startswith('file:') and os.path.isfile(t.icon[5:]) for t in etiles)
      and {'front', 'iris_size', 'pupil_size', 'pupil_shape', 'iris_color1', 'limbal', 'veins', 'wet', 'glow'}
      <= props)
bpy.ops.mesh.primitive_cube_add(location=(0, -6, 0))
its, _h = page()
check('No material: the Creature Shader section has the Parts too (4 balls)',
      len([i for i in its if i.kind == 'mtile' and i.action[:2] == ('op', 'mch.creature_part')]) == 4)
summary()
