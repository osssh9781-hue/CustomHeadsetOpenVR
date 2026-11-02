"""0.24.95 Shader conveniences (user picked: "상태 겹치기, 내 프리셋 저장, 배 · 등 색 자동, 랜덤 시드, 약한 상태 3 개 보강"):

* Stack Conditions: a Condition added on top (Bloody + Mud Caked), the amounts the larger, a layer's colour / texture
  only from a Condition that uses it; Clean still clears
* My Presets: the Mech / Creature settings saved under a name (a JSON in Blender's config folder - here a temp file),
  put back on another material, deleted; nothing is written until Save
* Belly: the underside lighter where there is no polypaint
* Seed: every map moved (the same preset, a different creature)
* Dusty, Swamp Feet, Slimy stronger (seen weak on the creature body render)"""
import json
import os
import tempfile

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import creature_shader as cs, mech_shader as ms, mech_shader_ui as mu, my_presets as mp

mecha_lab.register()
fresh()
C = bpy.context
TMP = tempfile.mkdtemp()
mp.PATH[0] = os.path.join(TMP, 'my_presets.json')        # (never the user's own file)


def select(*obs):
    for o in C.selected_objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    C.view_layer.objects.active = obs[0]


def heads(its):
    return {i.label.split('   ')[0]: i for i in its if i.kind == 'shead'}


bpy.ops.mesh.primitive_monkey_add()
ob = C.active_object
bpy.ops.mch.creature_apply(skin='REPTILE', condition='BLOODY')
mat = ob.active_material
st = mat.mch_creature
nodes = mat.node_tree.nodes

# ---- stacking
st.cond_stack = True
st.condition = 'MUD_CAKED'
check('Stack: Bloody + Mud Caked - the blood stays (and its textures), the mud comes on top with its own texture',
      st.blood > 0.3 and st.blood_dry > 0.3 and st.blood_tex == 'FRESH_BLOOD' and st.mud > 0.5
      and st.mud_tex == 'CRACKED_MUD' and st.condition == 'MUD_CAKED', (st.blood, st.mud, st.mud_tex))
st.condition = 'DUSTY'
check('... + Dusty: three on top of each other (the larger amounts kept)', st.blood > 0.3 and st.mud > 0.5
      and st.dust > 0.69 and st.mud_tex == 'CRACKED_MUD' and st.dust_tex == 'PALE_DUST')
st.condition = 'CLEAN'
check('... Clean still clears everything', st.blood == 0.0 and st.mud == 0.0 and st.dust == 0.0)
st.cond_stack = False
st.condition = 'BLOODY'
st.condition = 'MUD_CAKED'
check('Stack off: a Condition replaces the one there (as before)', st.blood == 0.0 and st.mud > 0.5)
check('... the Material page: a "Stack - add on top" switch in Conditions',
      any(getattr(i, 'prop', '') == 'cond_stack' for i in mu.content(C, 0.0, 276.0, 1.0)[0]))

# ---- stronger conditions
spec = dict((k, s) for k, _n, s in cs.CONDITIONS)
check('Dusty / Swamp Feet / Slimy stronger: dust 0.7, mud from below 0.85 reaching half way up (Low Reach is the '
      'Condition\'s now) + wet, slime 0.75 + wet', spec['DUSTY']['dust'] >= 0.7 and spec['SWAMP']['mud_low'] >= 0.85
      and spec['SWAMP']['low_reach'] >= 0.5 and spec['SWAMP']['wet'] > 0 and spec['SLIMY']['slime'] >= 0.75
      and spec['SLIMY']['wet'] > 0 and 'low_reach' in cs.COND_KEYS and 'low_reach' not in cs.SKIN_KEYS)

# ---- belly + seed
st.skin_type = 'SHARK'
check('Belly: Shark / Fish has a pale underside (0.55), only where there is no polypaint (x (1 - Polypaint))',
      st.belly >= 0.5 and nodes['mch:belly'].outputs[0].default_value == st.belly
      and nodes['mch:belly_color'].outputs[0].default_value[0] > 0.6)
off = nodes['mch:seed_offset']
st.seed = 7.0
check('Seed: every map moved (a vector added to the object coordinates before the maps)',
      off.inputs[0].is_linked and nodes['mch:seed'].outputs[0].default_value == 7.0
      and all(n.inputs['Vector'].is_linked for n in nodes if n.type == 'TEX_IMAGE'))
st.skin_type = 'HUMAN'
check('... a Skin Type keeps the Seed (it is this creature\'s, not the look)', st.seed == 7.0)
its, _h = mu.content(C, 0.0, 276.0, 1.0)
props = {getattr(i, 'prop', '') for i in its}
check('... on the page: Belly + its colour (Color), Seed (Height & Detail)', {'belly', 'belly_color'} <= props)

# ---- My Presets
check('My Presets: nothing saved yet - no file written, the section says how',
      not os.path.exists(mp.PATH[0]) and mp.names('creature') == [] and 'MY PRESETS' in heads(its))
st.mud = 0.42
st.base_hue = 0.12
r = bpy.ops.mch.my_preset_save(name='Swamp Lizard')
check('Save: the creature\'s settings under a name, in the JSON (not its size)', r == {'FINISHED'}
      and mp.names('creature') == ['Swamp Lizard'] and abs(mp.load_all()['creature']['Swamp Lizard']['mud'] - 0.42)
      < 1e-6 and 'size' not in mp.load_all()['creature']['Swamp Lizard'])
bpy.ops.mesh.primitive_uv_sphere_add(location=(4, 0, 0))
other = C.active_object
bpy.ops.mch.creature_apply(skin='DEMON', condition='CLEAN')
ost = other.active_material.mch_creature
r = bpy.ops.mch.my_preset_apply(name='Swamp Lizard')
check('... applied on another creature: its settings (mud 0.42, hue 0.12, Human skin) - its own size kept',
      r == {'FINISHED'} and abs(ost.mud - 0.42) < 1e-6 and abs(ost.base_hue - 0.12) < 1e-6
      and ost.skin_type == 'HUMAN' and abs(ost.size - max(other.dimensions) / 2) < 1e-4
      and abs(other.active_material.node_tree.nodes['mch:mud'].outputs[0].default_value - 0.42) < 1e-6)
its, _h = mu.content(C, 0.0, 276.0, 1.0)
tiles = [i for i in its if i.kind == 'mtile' and i.action[:2] == ('op', 'mch.my_preset_apply')]
check('... a ball for it in My Presets', [t.label for t in tiles] == ['Swamp Lizard'])
# a mech one, kept apart
bpy.ops.mesh.primitive_cube_add(location=(0, 5, 0))
cube = C.active_object
bpy.ops.mch.mech_shader_apply(preset='CHIPPED')
mst = cube.active_material.mch_mech
mst.edge_wear = 0.77
bpy.ops.mch.my_preset_save(name='My Chips')
bpy.ops.mch.mech_shader_apply(preset='STEEL')
mst = cube.active_material.mch_mech
bpy.ops.mch.my_preset_apply(name='My Chips')
check('Mech presets too, kept apart from the creature ones (Chipped Paint with Edge Wear 0.77 back on a Steel '
      'material)', mp.names('mech') == ['My Chips'] and mp.names('creature') == ['Swamp Lizard']
      and abs(mst.edge_wear - 0.77) < 1e-6 and mst.paint == 1.0)
r = bpy.ops.mch.my_preset_delete(name='My Chips')
check('Delete: gone from the file', r == {'FINISHED'} and mp.names('mech') == []
      and 'My Chips' not in json.load(open(mp.PATH[0]))['mech'])
summary()
