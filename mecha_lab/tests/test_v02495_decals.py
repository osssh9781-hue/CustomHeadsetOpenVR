"""0.24.95 Decals (user picked "데칼 - 번호, 경고 줄무늬, 로고를 표면에 붙이는 기능"; "데칼 그냥 너가 만들자 - 데칼에 데미지
들어간 것도 쉐이더로 넣어 줘, 조절할 수 있게"):

* 24 two-tone decals (white = Color 1, black = Color 2) + Text decals (a letter atlas)
* a decal wraps onto the part's surface (Shrinkwrap along its normal) and is parented to it; Mirror X, Apply, Delete
* damage in its shader: Wear (chips), Edge Peel, Scratches, Dirt, Fade, Damage Scale, Seed - all sliders
* the Material page: a Decals section (a ball each, Text Decal...), a decal's own page"""
import math
import os

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import decals as dc, mech_shader_ui as mu

mecha_lab.register()
fresh()
C = bpy.context


def page():
    return mu.content(C, 0.0, 276.0, 1.0)


def heads(its):
    return {i.label.split('   ')[0]: i for i in its if i.kind == 'shead'}


def evaluated_co(ob):
    dg = C.evaluated_depsgraph_get()
    me = ob.evaluated_get(dg).to_mesh()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    mw = np.array(ob.matrix_world)
    co = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
    ob.evaluated_get(dg).to_mesh_clear()
    return co


icons = os.path.join(os.path.dirname(dc.__file__), 'mech_icons')
missing = [k for k in dc.DECALS if not os.path.isfile(os.path.join(dc.DIR, k + '.png'))
           or not os.path.isfile(os.path.join(icons, f'decal_{k}.png'))]
check('24 decals on disk (picture + ball icon) and the letter atlas for Text decals',
      len(dc.DECALS) == 24 and not missing and os.path.isfile(os.path.join(dc.DIR, 'glyphs.png'))
      and len(dc.glyphs()['glyphs']) >= 40, missing)

# ---- on a curved part: it wraps onto the surface
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32)
ball = C.active_object
ball.name = 'Ball'
r = bpy.ops.mch.decal_place(decal='HAZARD', target='Ball', location=(0, -1, 0), normal=(0, -1, 0))
dec = C.active_object
st = dec.mch_decal
check('Place: a Hazard Stripes decal on the ball (active, parented to it, no shadow)', r == {'FINISHED'}
      and dc.is_decal(dec) and dec.parent == ball and st.kind == 'HAZARD' and not dec.visible_shadow)
sw = dec.modifiers.get('Decal Wrap')
check('... wrapped onto the surface: Shrinkwrap, projected along its normal both ways, onto the ball',
      sw is not None and sw.type == 'SHRINKWRAP' and sw.target == ball and sw.wrap_method == 'PROJECT'
      and sw.use_negative_direction and sw.use_positive_direction)
co = evaluated_co(dec)
rad = np.linalg.norm(co, axis=1)
lift = st.offset * st.height
check('... every point of it on the curved surface (a flat plane bent round the ball: distance from the centre '
      '1 + lift)', np.abs(rad - (1.0 + lift)).max() < 0.004, (round(float(rad.min()), 4), round(float(rad.max()), 4)))
width = co[:, 0].max() - co[:, 0].min()
check('... sized to the part (16 % of it tall, Hazard 2 : 1 wide)', abs(st.height - 0.32) < 0.01
      and abs(width - 2 * st.height) < 0.05, (round(st.height, 3), round(float(width), 3)))
mat = dec.active_material
nodes = mat.node_tree.nodes
bs = nodes['mch:bsdf']
check('... its shader: the picture (white = Color 1, black = Color 2), see-through where the picture is empty',
      nodes['mch:img:decal'].image.name.startswith('HAZARD') and bs.inputs['Alpha'].is_linked
      and bs.inputs['Base Color'].is_linked and abs(nodes['mch:color1'].outputs[0].default_value[1]
                                                    - st.color1[1]) < 1e-6)
ball.location.x = 5.0
C.view_layer.update()
check('... moves with the part', abs(dec.matrix_world.translation.x - 5.0) < 1e-4)
ball.location.x = 0.0

# ---- colours and damage: sliders into the shader
st.color1 = (0.1, 0.6, 0.9)
st.wear, st.peel, st.scratches, st.dirt, st.fade = 0.4, 0.5, 0.3, 0.2, 0.25
check('Colours and damage: the sliders on the shader at once (Color 1, Wear, Edge Peel, Scratches, Dirt, Fade)',
      abs(nodes['mch:color1'].outputs[0].default_value[2] - 0.9) < 1e-6
      and all(abs(nodes['mch:' + k].outputs[0].default_value - getattr(st, k)) < 1e-6
              for k in ('wear', 'peel', 'scratches', 'dirt', 'fade')))
check('... the damage from the Mech Shader\'s own maps (chips, scratches, grime) on the decal\'s plane',
      all(nodes['mch:img:' + k].image is not None for k in ('chips', 'scratch', 'dirt'))
      and nodes['mch:img:chips'].image.name.startswith('FLAKES'))
st.size = 2.0
check('Size: the decal twice as big', tuple(round(s, 4) for s in dec.scale) == (2.0, 2.0, 2.0))
st.size = 1.0

# ---- text decal
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 6, 0))
box = C.active_object
box.name = 'Box'
r = bpy.ops.mch.decal_place(text='UNIT 07', target='Box', location=(0, 5, 0.3), normal=(0, -1, 0))
tdec = C.active_object
uv = np.empty(len(tdec.data.loops) * 2)
tdec.data.uv_layers['UVMap'].data.foreach_get('uv', uv)
check('Text decal "UNIT 07": one letter patch per letter (6, a space between), its letters from the atlas',
      r == {'FINISHED'} and tdec.mch_decal.kind == dc.TEXT and len(tdec.data.polygons) == 6 * 9
      and tdec.active_material.node_tree.nodes['mch:img:decal'].image.name.startswith('glyphs')
      and uv.min() >= 0.0 and uv.max() <= 1.0)
check('... on the box\'s face, facing out', abs(tdec.matrix_world.to_3x3().col[2].y + 1.0) < 1e-4)

# ---- mirror / apply / delete
r = bpy.ops.mch.decal_mirror()
check('Mirror X: a Mirror across the part', r == {'FINISHED'} and tdec.modifiers.get('Decal Mirror') is not None
      and tdec.modifiers['Decal Mirror'].mirror_object == box)
bpy.ops.mch.decal_mirror()
n_before = len(evaluated_co(dec))
for o in C.selected_objects:
    o.select_set(False)
dec.select_set(True)
C.view_layer.objects.active = dec
r = bpy.ops.mch.decal_apply()
check('Apply: a plain mesh where it was wrapped (no modifiers, the same points)', r == {'FINISHED'}
      and not dec.modifiers and len(dec.data.vertices) == n_before
      and np.abs(np.linalg.norm(evaluated_co(dec), axis=1) - (1.0 + lift)).max() < 0.004)

# ---- the page
its, _h = page()
props = {getattr(i, 'prop', '') for i in its}
check('A decal\'s page: Look (Color 1 / 2, opacity, roughness, metallic), Damage (wear, edge peel, scratches, dirt, '
      'fade, scale, seed), Size & Place, Mirror X / Apply / Delete',
      {'LOOK', 'DAMAGE', 'SIZE & PLACE'} <= set(heads(its))
      and {'color1', 'color2', 'wear', 'peel', 'scratches', 'dirt', 'fade', 'damage_scale', 'seed', 'size'} <= props
      and {'Mirror X', 'Apply', 'Delete'} <= {i.label for i in its if i.kind == 'tbtn'})
bpy.ops.mesh.primitive_cone_add(location=(0, -8, 0))
its, _h = page()
from mecha_lab import side_panel as sp  # noqa: E402
folded_first = not heads(its)['DECALS'].on
sp.toggle_fold('MATERIAL:decals', True)                  # (a click on its title)
its, _h = page()
dtiles = [i for i in its if i.kind == 'mtile' and i.action[:2] == ('op', 'mch.decal_place')]
check('Other parts: a Decals section (starts folded) - opened, a ball each (24, its icon) + Text Decal...',
      folded_first and len(dtiles) == 24 and all(t.icon.startswith('file:') for t in dtiles)
      and any(i.kind == 'tbtn' and i.label == 'Text Decal...' for i in its))
for o in C.selected_objects:
    o.select_set(False)
tdec.select_set(True)
C.view_layer.objects.active = tdec
name = tdec.name
r = bpy.ops.mch.decal_delete()
check('Delete: the decal and its material gone', r == {'FINISHED'} and name not in bpy.data.objects
      and not any(m.name.startswith('Decal Text') for m in bpy.data.materials))
summary()
