"""0.24.95 Creature zones (user: "크리쳐도 이 라쏘 영역으로 재질 다르게 - 크리쳐 버전도 만들어 주고, 크리쳐 버전은 외곽에
에어브러시 버전, 텍스쳐 버전 만들어 줘"):

* a Paint Zone on a Creature Shader material (a box's flat front here - the edge measured on even light): markings - its colour over the skin's (Creature Shader 3: zone hubs),
  its own roughness; the edge Airbrush by default
* the Edge, rendered across the outline: Hard (a step), Airbrush (a smooth fade out past the lasso), Texture (the
  outline broken up: pushed out in some places, not in others) - what was drawn stays painted
* a creature colour texture for the zone (the colour goes grey: the texture as it is)
* Split Zone: Mech parts only; the Creature page: a Zones section (Paint Zone, the marking's sliders, Edge ...)
* the Mech zones have the Edge choice too"""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import creature_shader as cs, mech_shader as ms, mech_shader_ui as mu, zones as zn

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
RW = RH = 1000
PX = 100

w = bpy.data.worlds.new('W')
w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.8, 0.8, 0.8, 1.0)
S.world = w
bpy.ops.mesh.primitive_cube_add(size=2.0)                 # (a flat front: the edge measured on even light)
body = C.active_object
bpy.ops.mch.creature_apply(skin='HUMAN', condition='CLEAN')
mat = body.active_material
st = mat.mch_creature
st.mottle = 0.0
st.variation = 0.0
st.sss = 0.0
st.h_skin = st.h_detail = 0.0
st.cav_dark = st.ridge_light = 0.0
st.belly = 0.0
st.base_color = (0.75, 0.6, 0.5)
cd = bpy.data.cameras.new('Cam')
cam = bpy.data.objects.new('Cam', cd)
S.collection.objects.link(cam)
cam.location, cam.rotation_euler = (0.0, -6.0, 0.0), (math.radians(90), 0.0, 0.0)
S.camera = cam
C.view_layer.update()
vm = cam.matrix_world.inverted()
wm = cam.calc_matrix_camera(C.evaluated_depsgraph_get(), x=RW, y=RH)


def to_px(co):
    v = wm @ vm @ Vector((*co, 1.0))
    return ((v.x / v.w * 0.5 + 0.5) * RW, (v.y / v.w * 0.5 + 0.5) * RH)


R0 = 0.45
circle = [to_px((R0 * math.cos(t), -1.0, R0 * math.sin(t))) for t in [k * 2 * math.pi / 72 for k in range(72)]]


def render():
    S.render.engine = 'CYCLES'
    S.cycles.samples = 8
    S.cycles.use_denoising = False
    S.render.resolution_x = S.render.resolution_y = PX
    import os
    import tempfile
    p = os.path.join(tempfile.mkdtemp(), 'r.png')
    S.render.filepath = p
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(p)
    a = np.array(img.pixels[:]).reshape(PX, PX, 4)[..., :3]
    bpy.data.images.remove(img)
    return a


check('The Creature Shader has the zone hubs (mask, colour, roughness) and is version 3',
      cs.VERSION == 3 and all(mat.node_tree.nodes.get('mch:zone_' + k) is not None for k in ('mask', 'color', 'rough')))
base = render()
z = zn.add_paint_zone(C, body, circle, vm, wm, True, RW, RH, color=(0.05, 0.04, 0.03))
check('A Paint Zone on the creature: a marking - Airbrush edge, its roughness the skin\'s, linked into the hubs',
      z.edge == 'AIRBRUSH' and abs(z.roughness - st.roughness) < 1e-6 and z.line_height == 0.0
      and mat.node_tree.nodes['mch:zone_mask'].inputs[0].is_linked
      and mat.node_tree.nodes['mch:zone_rough'].inputs[0].is_linked)
# (pixel columns across the outline: the centre row, from the middle outwards)
c0 = PX // 2
edge_px = (to_px((R0, -1.0, 0.0))[0] - RW / 2) * PX / RW
face_px = (to_px((1.0, -1.0, 0.0))[0] - RW / 2) * PX / RW
xs = np.arange(int(c0 + edge_px - 12), int(c0 + face_px - 2))            # (up to the front face's own edge)


def profile(img):
    """0 = the marking's colour .. 1 = the skin's, along the row across the right edge."""
    lum = img[c0, xs].mean(1)
    inside, outside = img[c0, c0].mean(), base[c0, xs[-1]].mean()
    return (lum - inside) / max(outside - inside, 1e-6)


def width(p):
    """How many pixels the change from 10 % to 90 % takes."""
    return int(((p > 0.1) & (p < 0.9)).sum())


z.edge = 'HARD'
hard = render()
z.edge = 'AIRBRUSH'
z.edge_width = 20.0
soft = render()
inner = soft[c0, int(c0 + edge_px - 3)].mean()
ph, pa = profile(hard), profile(soft)
check('Rendered: the marking dark in the middle, the skin outside', hard[c0, c0].mean() < base[c0, c0].mean() * 0.4,
      (round(float(hard[c0, c0].mean()), 3), round(float(base[c0, c0].mean()), 3)))
check('... Hard: a step (the change within 2 px); Airbrush (Edge Width 20 %): a fade over several pixels, out past '
      'the lasso (just inside it still the marking)', width(ph) <= 2 and width(pa) >= 5
      and abs(inner - hard[c0, c0].mean()) < 0.04, (width(ph), width(pa), round(float(inner), 3)))
z.edge = 'TEXTURE'
z.edge_width = 8.0
tx = render()
ring_out = []
ring_in = []
for k in range(72):
    t = k * 2 * math.pi / 72
    for r, bucket in ((R0 * 1.12, ring_out), (R0 * 0.88, ring_in)):
        px, py = to_px((r * math.cos(t), -1.0, r * math.sin(t)))
        bucket.append(tx[int(py * PX / RH), int(px * PX / RW)].mean())
sk, mk = base[c0, xs[-1]].mean(), hard[c0, c0].mean()
dark_out = np.mean(np.array(ring_out) < (sk + mk) / 2)
light_in = np.mean(np.array(ring_in) > (sk + mk) / 2)
hard_out = []
for k in range(72):
    t = k * 2 * math.pi / 72
    px, py = to_px((R0 * 1.12 * math.cos(t), -1.0, R0 * 1.12 * math.sin(t)))
    hard_out.append(hard[int(py * PX / RH), int(px * PX / RW)].mean())
check('... Texture: the outline broken up - just outside it the marking reaches out in some places, not in others; '
      'just inside it all painted (Hard: none outside)', 0.08 < dark_out < 0.92 and light_in == 0.0
      and np.mean(np.array(hard_out) < (sk + mk) / 2) == 0.0, (round(float(dark_out), 2), round(float(light_in), 2)))
check('... its nodes: a noise pattern on the part, the Edge Scale on it',
      mat.node_tree.nodes.get('mchz:0:noise') is not None and mat.node_tree.nodes.get('mchz:0:esc') is not None)
z.edge = 'AIRBRUSH'
z.tex = 'RED_CLAY'
check('A colour texture for the marking: its picture on the part, the colour gone grey (the texture as it is)',
      mat.node_tree.nodes.get('mchz:0:tex') is not None and tuple(round(c, 3) for c in z.color) == (0.5, 0.5, 0.5)
      and mat.node_tree.nodes['mchz:0:tex'].image.name.startswith('RED_CLAY'))
tex_img = render()
mid = tex_img[c0 - 3:c0 + 4, c0 - 3:c0 + 4].reshape(-1, 3).mean(0)
check('... rendered: the middle the clay\'s red-brown (red over blue)', mid[0] > mid[2] * 1.3, np.round(mid, 3).tolist())
z.color = (0.5, 0.5, 0.5)
st.mud = 0.8
mud = render()
check('Conditions go over the marking (Mud 0.8: the middle changes)',
      float(np.abs(mud[c0, c0] - tex_img[c0, c0]).sum()) > 0.03)
st.mud = 0.0
try:
    zn.split_zone(C, body, circle, vm, wm, True, RW, RH)
    split_refused = False
except RuntimeError:
    split_refused = True
check('Split Zone: Mech parts only (refused on a creature)', split_refused)
for o in C.selected_objects:
    o.select_set(False)
body.select_set(True)
C.view_layer.objects.active = body
its, _h = mu.creature_page(C, 0.0, 276.0, 1.0)
props = {getattr(i, 'prop', '') for i in its}
btns = {i.label for i in its if i.kind == 'tbtn'}
check('The Creature page: Zones - Paint Zone (no Split), the marking\'s colour, texture, roughness, opacity, Edge, '
      'Edge Width, Delete', {'color', 'tex', 'tex_scale', 'roughness', 'opacity', 'edge', 'edge_width'} <= props
      and 'Paint Zone' in btns and 'Split Zone' not in btns and 'Delete' in btns)
cs.build(mat)
cs.sync(mat)
check('The Creature tree made anew: the zone linked back in', mat.node_tree.nodes['mch:zone_mask'].inputs[0].is_linked
      and mat.node_tree.nodes.get('mchz:0:tex') is not None)
# the Mech zones have the Edge too
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, -4))
part = C.active_object
bpy.ops.mch.mech_shader_apply(preset='PAINTED')
mz = zn.add_paint_zone(C, part, circle, vm, wm, True, RW, RH)
mz.edge = 'AIRBRUSH'
check('The Mech zones: the Edge choice too (Hard by default; Airbrush makes its width node)',
      part.active_material.node_tree.nodes.get('mchz:0:ew') is not None)
summary()
