"""0.24.95 Decals (user picked "데칼 - 번호, 경고 줄무늬, 로고를 표면에 붙이는 기능"; "데칼 그냥 너가 만들자 - 데칼에 데미지
들어간 것도 쉐이더로 넣어 줘, 조절할 수 있게"):

* 24 two-tone decals (white = Color 1, black = Color 2) + Text decals (a letter atlas)
* a decal wraps onto the part's surface (Shrinkwrap along its normal) and is parented to it; Mirror X, Apply, Delete
* damage in its shader: Wear (chips), Edge Peel, Scratches, Dirt, Fade, Damage Scale, Seed - all sliders
* the Material page: a Decals section (a ball each, Text Decal...), a decal's own page
* 0.24.95 (user: "추가 데칼이야! 이거도 추가해 줘 / 이건 데칼 탭으로 가자!"): the user's 30 Sci-Fi decals in full colour
  (their own colours, sRGB; Tint, Hue / Saturation / Value), the Decals page of its own (the library + the selected
  decal's settings); the Mech page with a decal selected points to it"""
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
    return mu.decal_page(C, 0.0, 276.0, 1.0)                 # (0.24.95 the Decals page of its own)


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

# ---- a full-colour Sci-Fi decal (the user's pack)
check('30 Sci-Fi decals (the user\'s pack, full colour): picture + ball icon each, sizes from the pictures (Hazard '
      'Stripe long and thin)', len(dc.COLOR_DECALS) == 30 and all(
          dc.image_path(kk).endswith('.webp') and os.path.isfile(os.path.join(icons, f'decal_{kk}.png'))
          for kk in dc.COLOR_DECALS) and dc.COLOR_DECALS['SF_HAZARD_STRIPE'][1] > 5.0
      and abs(dc.COLOR_DECALS['SF_RADIATION'][1] - 1.0) < 0.05)
r = bpy.ops.mch.decal_place(decal='SF_HAZARD_STRIPE', target='Box', location=(0, 5, -0.4), normal=(0, -1, 0))
sdec = C.active_object
sst = sdec.mch_decal
snodes = sdec.active_material.node_tree.nodes
img = snodes['mch:img:decal'].image
sco = evaluated_co(sdec)
check('Place the Hazard Stripe: its own colours (the picture sRGB, with its alpha, the full-colour switch on), the '
      'plane as long as the picture', r == {'FINISHED'} and sst.kind == 'SF_HAZARD_STRIPE'
      and img.colorspace_settings.name == 'sRGB' and img.channels == 4 and img.file_format == 'WEBP'
      and snodes['mch:full'].outputs[0].default_value == 1.0
      and abs((sco[:, 0].max() - sco[:, 0].min()) / sst.height - dc.COLOR_DECALS['SF_HAZARD_STRIPE'][1]) < 0.1,
      (img.colorspace_settings.name, round(float(sco[:, 0].max() - sco[:, 0].min()), 3), round(sst.height, 3)))
check('... the two-tone ones stay a mask (their picture Non-Color, the switch off)',
      nodes['mch:full'].outputs[0].default_value == 0.0 if 'mch:full' in nodes else True)
sst.hue, sst.sat, sst.val = 0.3, 0.5, 1.4
sst.tint = (1.0, 0.5, 0.5)
hsv = snodes['mch:hsv']
check('... Hue / Saturation / Value and Tint on the shader at once', hsv.inputs['Hue'].is_linked
      and abs(snodes['mch:hue'].outputs[0].default_value - 0.3) < 1e-6
      and abs(snodes['mch:sat'].outputs[0].default_value - 0.5) < 1e-6
      and abs(snodes['mch:val'].outputs[0].default_value - 1.4) < 1e-6
      and abs(snodes['mch:tint'].outputs[0].default_value[1] - 0.5) < 1e-6)
its, _h = page()
props = {getattr(i, 'prop', '') for i in its}
check('... its page: Tint + Hue / Sat / Val (no Color 1 / 2), the damage the same',
      {'tint', 'hue', 'sat', 'val', 'wear', 'peel'} <= props and not {'color1', 'color2'} & props)
sst.wear = 0.5
check('... damage on it too (Wear cuts its alpha)', abs(snodes['mch:wear'].outputs[0].default_value - 0.5) < 1e-6)
bpy.ops.mch.decal_delete()

# ---- the page
for o in C.selected_objects:
    o.select_set(False)
dec.select_set(True)
C.view_layer.objects.active = dec
its, _h = page()
props = {getattr(i, 'prop', '') for i in its}
check('A decal\'s page: Look (Color 1 / 2, opacity, roughness, metallic), Damage (wear, edge peel, scratches, dirt, '
      'fade, scale, seed), Size & Place, Mirror X / Apply / Delete',
      {'LOOK', 'DAMAGE', 'SIZE & PLACE'} <= set(heads(its))
      and {'color1', 'color2', 'wear', 'peel', 'scratches', 'dirt', 'fade', 'damage_scale', 'seed', 'size'} <= props
      and {'Mirror X', 'Apply', 'Delete'} <= {i.label for i in its if i.kind == 'tbtn'})
folded = [h for h, i in heads(its).items() if h in ('SCI-FI SIGNS', 'TWO-TONE') and not i.on]
check('... and the library under it, folded', sorted(folded) == ['SCI-FI SIGNS', 'TWO-TONE'], folded)
mits, _h = mu.content(C, 0.0, 276.0, 1.0)
go = next((i for i in mits if i.kind == 'tbtn' and i.action[:2] == ('op', 'mch.side_page')), None)
check('The Mech page with a decal selected: says its settings are on the Decals page, a button to it (no decal '
      'rows there)', go is not None and go.action[2] == {'page': 'DECALS'} and not any(
          getattr(i, 'prop', '') in ('wear', 'peel') for i in mits))
from mecha_lab import side_panel as sp, ui_bars  # noqa: E402
ui_bars.run(C, go)
check('... a click on it shows the Decals page', sp.page(C) == 'DECALS')
bpy.ops.mesh.primitive_cone_add(location=(0, -8, 0))
its, _h = page()
hd = heads(its)
dtiles = [i for i in its if i.kind == 'mtile' and i.action[:2] == ('op', 'mch.decal_place')]
check('The Decals page with a part selected: the library open - Sci-Fi Signs (30) and Two-Tone (24), a ball each '
      'with its icon, + Text Decal...', hd['SCI-FI SIGNS'].on and hd['TWO-TONE'].on and len(dtiles) == 54
      and all(t.icon.startswith('file:') and os.path.isfile(t.icon[5:]) for t in dtiles)
      and any(i.kind == 'tbtn' and i.label == 'Text Decal...' for i in its))
mits, _h = mu.content(C, 0.0, 276.0, 1.0)
cits, _h = mu.creature_page(C, 0.0, 276.0, 1.0)
check('... the Mech and Creature pages no decal balls any more',
      not any(i.kind == 'mtile' and i.action[:2] == ('op', 'mch.decal_place') for i in mits + cits))
tabs = [i for i in sp.items(C, 1200, 900, 1.0) if i.kind == 'ptab']
check('Tabs: Tool | Mech | Creature | Decals | HDRI (each wide enough for its name)',
      [t.label for t in tabs] == ['Tool', 'Mech', 'Creature', 'Decals', 'HDRI']
      and all(t.w > 6.5 * len(t.label) + 6 for t in tabs), [(t.label, round(t.w)) for t in tabs])
for o in C.selected_objects:
    o.select_set(False)
tdec.select_set(True)
C.view_layer.objects.active = tdec
name = tdec.name
r = bpy.ops.mch.decal_delete()
check('Delete: the decal and its material gone', r == {'FINISHED'} and name not in bpy.data.objects
      and not any(m.name.startswith('Decal Text') for m in bpy.data.materials))
summary()
