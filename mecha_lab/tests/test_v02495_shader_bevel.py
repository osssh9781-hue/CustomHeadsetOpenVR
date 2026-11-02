"""0.24.95 Mech Shader: the shading Bevel (user: "메테리얼 탭에 베벨도 넣어 줄래? 쉐이더 노말 쪽에 베벨 - 조금 베벨, 중간
베벨, 많이 베벨을 프리셋으로 넣고 맘에 안 들면 세부 조정하게 슬라이더까지"):

* a Bevel section on the Mech page: Off / Small / Medium / Large (lit: the one in use) + Radius and Samples sliders;
  the N panel too
* Cycles' Bevel node into the bump's normal - linked only while the radius is above 0 (off: no cost)
* rendered (a cube's edge, lit from one side): without it the two faces meet in a step; with it a soft band across the
  edge, as wide as the radius
* the material preset does not touch it; a Mech material made before: made anew on the next change"""
import math
import os
import tempfile

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import mech_shader as ms, mech_shader_ui as mu

fresh()
mecha_lab.register()
C = bpy.context
sc = C.scene
PX = 160

bpy.ops.mesh.primitive_cube_add(size=2.0, rotation=(0.0, 0.0, math.radians(45)))
part = C.active_object
bpy.ops.mch.mech_shader_apply(preset='PLASTIC_MATTE')
mat = part.active_material
st = mat.mch_mech
st.base_color = (0.6, 0.6, 0.6)
st.base_map = 'FLAT'
st.variation = st.h_base = 0.0
nt = mat.node_tree
bev, bump = nt.nodes.get('mch:bevel_look'), nt.nodes.get('mch:bumpnode')
check('A Bevel node for the shading (apart from the one that finds the edges for the wear), not linked while off',
      bev is not None and bev.type == 'BEVEL' and not bump.inputs['Normal'].is_linked and ms.bevel_preset(st) == 'OFF'
      and ms.VERSION >= 13)
r = bpy.ops.mch.mech_bevel(preset='LARGE')
check('Large: its radius / samples, its normal into the bump\'s (under the bump: the wear and bumps still on top)',
      r == {'FINISHED'} and abs(st.bevel_radius - 0.03) < 1e-6 and st.bevel_samples == 12 and bev.samples == 12
      and bump.inputs['Normal'].is_linked and bump.inputs['Normal'].links[0].from_node == bev
      and ms.bevel_preset(st) == 'LARGE')
bpy.ops.mch.mech_bevel(preset='SMALL')
small = (st.bevel_radius, ms.bevel_preset(st))
bpy.ops.mch.mech_bevel(preset='MEDIUM')
medium = (st.bevel_radius, ms.bevel_preset(st))
check('... Small / Medium: smaller radii (4 / 12 mm), each one lit as the one in use',
      abs(small[0] - 0.004) < 1e-6 and small[1] == 'SMALL' and abs(medium[0] - 0.012) < 1e-6 and medium[1] == 'MEDIUM',
      (small, medium))
st.bevel_radius = 0.02
check('... the Radius slider fine-tunes it (Custom), into the node', ms.bevel_preset(st) == 'CUSTOM'
      and abs(bev.inputs['Radius'].default_value - 0.02) < 1e-6)
bpy.ops.mch.mech_bevel(preset='OFF')
check('... Off: unlinked again', not bump.inputs['Normal'].is_linked and st.bevel_radius == 0.0)

# rendered: a cube's vertical edge, a sun from one side
sun_d = bpy.data.lights.new('Sun', 'SUN')
sun_d.energy = 4.0
sun = bpy.data.objects.new('Sun', sun_d)
sc.collection.objects.link(sun)
sun.rotation_euler = (math.radians(90), 0.0, math.radians(-80))
w = bpy.data.worlds.new('W')
w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.05, 0.05, 0.05, 1.0)
sc.world = w
cd = bpy.data.cameras.new('Cam')
cd.type = 'ORTHO'
cd.ortho_scale = 1.0
cam = bpy.data.objects.new('Cam', cd)
sc.collection.objects.link(cam)
cam.location, cam.rotation_euler = (0.0, -6.0, 0.0), (math.radians(90), 0.0, 0.0)
sc.camera = cam
sc.render.engine = 'CYCLES'
sc.cycles.samples = 24
sc.cycles.use_denoising = False
sc.render.resolution_x = sc.render.resolution_y = PX
sc.view_settings.view_transform = 'Standard'


def profile():
    p = os.path.join(tempfile.mkdtemp(), 'r.png')
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(p)
    a = np.array(img.pixels[:]).reshape(PX, PX, 4)[PX // 2 - 10:PX // 2 + 10, :, :3].mean(axis=(0, 2))
    bpy.data.images.remove(img)
    return a                                   # (brightness along a row through the middle, across the edge)


def band(a):
    """How many pixels the change from one face to the other takes (10 % .. 90 %)."""
    lo, hi = a[10:PX // 2 - 25].mean(), a[PX // 2 + 25:-10].mean()
    t = (a - lo) / (hi - lo if abs(hi - lo) > 1e-6 else 1e-6)
    return int(((t > 0.1) & (t < 0.9)).sum()), round(float(lo), 3), round(float(hi), 3)


sharp = band(profile())
st.bevel_radius = 0.1                          # (10 cm on this 2 m cube: about 14 px across in this view)
st.bevel_samples = 16
round_ = band(profile())
st.bevel_radius = 0.25
rounder = band(profile())
check('Rendered (Cycles, the edge lit from one side): sharp - the faces meet in a step; Bevel 10 cm - a soft band '
      'across the edge; 25 cm - wider still', sharp[0] <= 3 and round_[0] >= sharp[0] + 2
      and rounder[0] >= round_[0] + 3 and abs(sharp[1] - sharp[2]) > 0.1, (sharp, round_, rounder))
st.bevel_radius = 0.1
# the page, the N panel
for o in C.selected_objects:
    o.select_set(False)
part.select_set(True)
C.view_layer.objects.active = part
its, _h = mu.content(C, 0.0, 276.0, 1.0)
heads = {i.label.split('   ')[0]: i for i in its if i.kind == 'shead'}
btns = [i.label for i in its if i.kind == 'tbtn' and i.action[:2] == ('op', 'mch.mech_bevel')]
props = {getattr(i, 'prop', '') for i in its}
check('The Mech page: a Bevel section (open while on) - Off / Small / Medium / Large, Radius, Samples',
      'BEVEL' in heads and heads['BEVEL'].on and btns == ['Off', 'Small', 'Medium', 'Large']
      and {'bevel_radius', 'bevel_samples'} <= props, (list(heads), btns))
# the material preset keeps it; a material from before
st.preset = 'STEEL'
check('... a material preset keeps the Bevel', abs(st.bevel_radius - 0.1) < 1e-6
      and mat.node_tree.nodes['mch:bumpnode'].inputs['Normal'].is_linked)
mat['mch_mech'] = 12
mat.node_tree.nodes.remove(mat.node_tree.nodes['mch:bevel_look'])
st.bevel_radius = 0.05
check('A Mech material made before (no Bevel node): made anew on the next change, the Bevel in it',
      mat.get('mch_mech') == ms.VERSION and mat.node_tree.nodes.get('mch:bevel_look') is not None
      and abs(mat.node_tree.nodes['mch:bevel_look'].inputs['Radius'].default_value - 0.05) < 1e-6
      and mat.node_tree.nodes['mch:bumpnode'].inputs['Normal'].is_linked)
summary()
