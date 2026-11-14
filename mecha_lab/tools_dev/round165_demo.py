"""0.24.165 demo: the user's notes on 0.24.164 - Layered Cliff in lines down the cliff, Creature Carapace with a thin
lip, Creature Plate with Edge Spikes, Scale Line's scales with a line round their outline, Print Cut's square Key (the
test human 200 mm tall, cut at the thighs and the neck with keys).  Cycles, shaded and with the wireframe.

    <blender python> round165_demo.py <out dir>
"""
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'addon'))
sys.path.insert(0, HERE)
import mecha_lab  # noqa: E402
import make_test_human as mth  # noqa: E402

OUT = sys.argv[-1]
os.makedirs(OUT, exist_ok=True)
mecha_lab.register()
from mecha_lab import (core_geometry as cg, creature_light as cl, creature_plate as cp, greeble_line as gl,  # noqa: E402
                       plate_detail as pd, print3d as p3)

C = bpy.context
S = C.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)        # (looking down: 100 px = 1, (500, 500) = origin)


def ring(cx, cy, rx, ry, n=80):
    a = np.linspace(0, 2 * math.pi, n, endpoint=False)
    return [[(500 + (cx + rx * math.cos(t)) * 100, 500 + (cy + ry * math.sin(t)) * 100) for t in a]]


def pick(ob):
    for o in C.selected_objects:
        o.select_set(False)
    if ob is not None:
        ob.select_set(True)
    C.view_layer.objects.active = ob


def mat(name, rgb, rough=0.55):
    m = bpy.data.materials.new(name)
    pb = m.node_tree.nodes['Principled BSDF']
    pb.inputs['Base Color'].default_value = (*rgb, 1)
    pb.inputs['Roughness'].default_value = rough
    return m


stone = mat('Stone', (0.55, 0.53, 0.5), 0.8)
skin = mat('Skin', (0.42, 0.45, 0.4), 0.6)
pla = mat('PLA', (0.72, 0.74, 0.78), 0.45)
ground_m = mat('Ground', (0.2, 0.2, 0.21), 0.8)

# 1) Plate Detail 4: Layered Cliff and Creature Carapace on a slab
bpy.ops.mesh.primitive_plane_add(size=14.0, location=(0, 0, 0))
slab = C.active_object
slab.data.materials.append(ground_m)
made = {}
for key, cx, cy, preset in (('cliff', -3.0, 0.0, 'CLIFF'), ('cara', 3.0, 0.0, 'CARAPACE')):
    pick(None)
    bpy.ops.mch.pdetail_rough_preset(preset=preset)
    pick(slab)
    print(pd.perform(C, ring(cx, cy, 2.2, 1.4), TOP, 'DETAIL4'))
    made[key] = C.active_object
    made[key].data.materials.clear()
    made[key].data.materials.append(stone)

# 2) Creature Plate with Edge Spikes, and a Scale Line - on balls behind
bpy.ops.mesh.primitive_uv_sphere_add(radius=2.0, segments=96, ring_count=48, location=(-3.0, 6.0, 0.0))
ball_a = C.active_object
bpy.ops.object.shade_smooth()
bpy.ops.mesh.primitive_uv_sphere_add(radius=2.0, segments=96, ring_count=48, location=(3.0, 6.0, 0.0))
ball_b = C.active_object
bpy.ops.object.shade_smooth()
for b_ in (ball_a, ball_b):
    b_.data.materials.append(skin)
st = S.mch_cplate
P = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0, center=Vector((0, 0, 0)))
for prof, cx, cy, n in (('PUFF', -3.6, 5.6, 14), ('SCALE', -2.3, 6.6, 9)):
    st.profile, st.spikes, st.peak, st.end_peak = prof, n, 0.0, -1.0
    pick(ball_a)
    print(cp.perform(C, [[(500 + (cx + (0.75 if prof == 'PUFF' else 0.6) * math.cos(t)) * 100,
                           500 + (cy + (0.5 if prof == 'PUFF' else 0.38) * math.sin(t)) * 100)
                          for t in np.linspace(0, 2 * math.pi, 70, endpoint=False)]], P))
    C.active_object.data.materials.clear()
    C.active_object.data.materials.append(skin)
scales = gl.make_starters(C, ball_b, 'SCALES')
for s_ in scales:
    s_.data.materials.append(skin)
    s_.hide_render = True                                 # (the parts beside the model: hidden in the shots)
    s_.hide_set(True)
stg = gl.settings(S, 'CREATURE')
pts, nrm = [], []
for t in np.linspace(-1.1, 1.1, 60):                      # an arc over the ball (its space)
    v = Vector((math.sin(t) * 2.0, -0.35, math.cos(t) * 2.0))
    v = v.normalized() * 2.0
    pts.append(tuple(v))
    nrm.append(tuple(v.normalized()))
line = gl.new_line(C, ball_b, pts, nrm, gl.picked(stg), stg, 'CREATURE')
gl.rebuild(line, C)
print('scale line applied', gl.apply_line(C, line))     # (a plain mesh: its wireframe can be shown)
# the five scales big, to see their line (beside the ball)
for i, s_ in enumerate(scales):
    big = bpy.data.objects.new(s_.name + ' big', s_.data)
    S.collection.objects.link(big)
    big.scale = (0.9, 0.9, 0.9)
    big.location = (6.4, 3.6 + i * 1.1, 0.0)

# 3) Print Cut with Keys: the test human 200 mm tall, cut at the thighs and the neck
human = mth.build(3, clear=False)                         # (the scene kept)
pick(human)
S.mch_print.fit_height = 200.0
bpy.ops.mch.print_scale_height()
C.view_layer.update()
bb = p3.world_bounds(C, [human])
z0 = bb[0].z
human.location += Vector((0.0, -6.0, -z0)) - Vector((0, 0, 0))
C.view_layer.update()
bb = p3.world_bounds(C, [human])
z0 = bb[0].z
pg = S.mch_print
pg.pin_style, pg.pin_count, pg.pin_auto, pg.clearance, pg.gap = 'KEY', 'AUTO', True, 0.2, 0.0
legs, upper, _k, msg = p3.cut_with_pins(C, human, Vector((0, -6.0, z0 + 0.072)), Vector((0, 0, 1)))
print(msg)
body, head, _k2, msg2 = p3.cut_with_pins(C, upper, Vector((0, -6.0, z0 + 0.172)), Vector((0, 0, 1)))
print(msg2)
body.location.z += 0.03
head.location.z += 0.06
for o in (legs, body, head):
    o.data.materials.clear()
    o.data.materials.append(pla)
C.view_layer.update()

# light, camera, the wire copies
S.world = bpy.data.worlds.new('Before')
cl.apply(S, 'soft_studio')
sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
S.collection.objects.link(sun)
sun.data.energy = 3.5
sun.rotation_euler = (math.radians(55), 0.0, math.radians(-35))
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
S.collection.objects.link(cam)
S.camera = cam
cam.data.clip_start = 0.001                              # (the close-ups are 0.1 m from the parts)
S.render.engine = 'CYCLES'
S.cycles.samples = 48
S.cycles.use_denoising = True
S.cycles.device = 'CPU'
S.render.image_settings.file_format = 'PNG'
wmat = mat('Wire', (1.0, 0.45, 0.05))
wmat.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (1.0, 0.45, 0.05, 1)
wmat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 1.5
dg = C.evaluated_depsgraph_get()
wires = []
for src in [o for o in S.objects if o.type == 'MESH' and o.visible_get() and o is not slab and not o.hide_render]:
    me = bpy.data.meshes.new_from_object(src.evaluated_get(dg), depsgraph=dg)
    wo = bpy.data.objects.new(src.name + ' wire', me)
    S.collection.objects.link(wo)
    wo.matrix_world = src.matrix_world
    md = wo.modifiers.new('W', 'WIREFRAME')
    md.use_replace = True
    md.use_even_offset = False
    me.materials.clear()
    me.materials.append(wmat)
    wo.hide_render = True
    wires.append((wo, md, src))


def aim(loc, look, lens):
    cam.location = loc
    cam.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens


def render(name, thick):
    for wire in (False, True):
        for wo, md, _src in wires:
            wo.hide_render = not wire
            md.thickness = thick
        S.render.filepath = os.path.join(OUT, name + ('_wire' if wire else '_shaded') + '.png')
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print('saved', S.render.filepath, f'{time.time() - t0:.0f} s')


S.render.resolution_x, S.render.resolution_y = 1000, 700
aim((-3.0 - 5.4, -0.9, 2.6), (-2.6, 0.0, 0.25), 38)                # the cliff from its low (west) side: lines down it
render('cliff', 0.006)
aim((3.0, -4.4, 3.2), (3.0, 0.0, 0.1), 40)                        # the carapace
render('carapace', 0.006)
aim((-3.0, 0.4, 3.8), (-3.0, 6.0, 1.2), 42)                       # the plates with Edge Spikes
render('spikes', 0.004)
aim((3.6, 1.6, 3.4), (3.6, 5.6, 1.1), 40)                         # the Scale Line + the five scales big
render('scales', 0.003)
S.render.resolution_x, S.render.resolution_y = 800, 1000
aim((0.16, -6.0 - 0.36, z0 + 0.19), (0.0, -6.0, z0 + 0.135), 50)   # the human cut with keys
render('keys', 0.00012)
S.render.resolution_x, S.render.resolution_y = 1000, 800
aim((0.06, -6.0 - 0.13, z0 + 0.135), (0.0, -6.0, z0 + 0.085), 55)  # the thighs: the keys below, the sockets above
render('keys_close', 0.00008)
aim((0.05, -6.0 - 0.10, z0 + 0.03), (0.0, -6.0, z0 + 0.105), 55)   # from below: the square sockets in the body
render('sockets', 0.00008)
