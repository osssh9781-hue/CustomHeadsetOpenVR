"""0.24.166 demo: keys across any Split (the user's Dovetail Key reference: an arm cut off at the shoulder, square
keys).  The test human 200 mm tall: the Split tool's lasso round the right arm (seen from the front) takes it off at
the shoulder - Keys Between the two parts: a square key on the arm (its big end on the arm), the socket in the body a
Fit Gap wider; then Print Cut along a bent line (a V) across both thighs - a key on each.  And Scale Line's scales with
their rounded edge.  Cycles, shaded and with the wireframe.

    <blender python> round166_demo.py <out dir>
"""
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Euler, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'addon'))
sys.path.insert(0, HERE)
import mecha_lab  # noqa: E402
import make_test_human as mth  # noqa: E402

OUT = sys.argv[-1]
os.makedirs(OUT, exist_ok=True)
mecha_lab.register()
from mecha_lab import (core_geometry as cg, creature_light as cl, cut_engine as ce, greeble_line as gl,  # noqa: E402
                       print3d as p3)

C = bpy.context
S = C.scene
human = mth.build(3)
for o in C.selected_objects:
    o.select_set(False)
human.select_set(True)
C.view_layer.objects.active = human
S.mch_print.fit_height = 200.0
bpy.ops.mch.print_scale_height()
C.view_layer.update()
bb = p3.world_bounds(C, [human])
human.location -= Vector((0.0, (bb[0].y + bb[1].y) / 2, bb[0].z))
C.view_layer.update()
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0.0, 0.0)).to_quaternion(), center=Vector((0.0, 0.0, 0.1)),
                          pixels_per_unit=5000.0)


def px(x, z):
    return FRONT.to_screen(Vector((x, 0.0, z)))


pg = S.mch_print
pg.pin_style, pg.pin_count, pg.pin_auto, pg.clearance, pg.gap = 'KEY', 'AUTO', True, 0.2, 0.0
S.mch_cut.split_mode = 'NORMAL'
S.mch_cut.depth_mode = 'THROUGH'
# 1) the Split tool's lasso round the right arm (from the front): off at the shoulder, under the armpit
lasso = [px(0.016, 0.182), px(0.0275, 0.134), px(0.03, 0.06), px(0.075, 0.06), px(0.075, 0.182)]
print(ce.perform_closed(C, 'SPLIT', [human], [lasso], FRONT))
arm = next(o for o in S.objects if o.name.endswith('_Split'))
carrier, other = p3.key_carrier(arm, human)
pins, msg = p3.keys_between(C, carrier, other)
print(msg)
arm.location.x += 0.022
# 2) Print Cut along a bent line (a V) across both thighs
legs_path = [px(-0.03, 0.074), px(0.0, 0.064), px(0.03, 0.074)]
A, B, _p, msg2 = p3.cut_along_line(C, human, legs_path, FRONT)
print(msg2)
lower = min((A, B), key=lambda o: p3._volume(o))
lower.location.z -= 0.022
C.view_layer.update()

# 3) Scale Line's five built-in scales, big on the floor: their rounded edges
bigs = []
for k, (nm, me) in enumerate(gl._scale_meshes()):
    o = bpy.data.objects.new(nm, me)
    S.collection.objects.link(o)
    o.scale = (0.03, 0.03, 0.03)
    o.location = (0.22 + (k % 3) * 0.034, -0.02 + (k // 3) * 0.034, -0.03)        # (on the floor)
    bigs.append(o)
ball = line = None


def mat(name, rgb, rough=0.5):
    m = bpy.data.materials.new(name)
    pb = m.node_tree.nodes['Principled BSDF']
    pb.inputs['Base Color'].default_value = (*rgb, 1)
    pb.inputs['Roughness'].default_value = rough
    return m


pla = mat('PLA', (0.72, 0.74, 0.78), 0.45)
skin = mat('Skin', (0.42, 0.45, 0.4), 0.6)
for o in S.objects:
    if o.type == 'MESH' and o.visible_get():
        o.data.materials.clear()
        o.data.materials.append(skin if o in bigs else pla)
bpy.ops.mesh.primitive_plane_add(size=2.0, location=(0, 0, -0.03))
floor_z = -0.03
floor = C.active_object
floor.data.materials.append(mat('Bed', (0.12, 0.12, 0.13), 0.7))
S.world = bpy.data.worlds.new('Before')
cl.apply(S, 'soft_studio')
sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
S.collection.objects.link(sun)
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(50), 0.0, math.radians(-30))
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
S.collection.objects.link(cam)
S.camera = cam
cam.data.clip_start = 0.001
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
for src in [o for o in S.objects if o.type == 'MESH' and o.visible_get() and o is not floor and not o.hide_render]:
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
    wires.append((wo, md, max(abs(v) for v in src.matrix_world.to_scale())))


def aim(loc, look, lens):
    cam.location = loc
    cam.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens


def render(name, thick):
    for wire in (False, True):
        for wo, md, sc in wires:
            wo.hide_render = not wire
            md.thickness = thick / max(sc, 1e-9)               # (in the object's own units)
        S.render.filepath = os.path.join(OUT, name + ('_wire' if wire else '_shaded') + '.png')
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print('saved', S.render.filepath, f'{time.time() - t0:.0f} s')


S.render.resolution_x, S.render.resolution_y = 800, 1000
aim((0.12, -0.36, 0.17), (0.01, 0.0, 0.11), 50)                     # the figure: the arm off, the legs down
render('figure', 0.00012)
S.render.resolution_x, S.render.resolution_y = 1000, 800
aim((0.11, -0.10, 0.19), (0.03, 0.0, 0.15), 50)                     # the shoulder: the key on the arm, the socket
render('shoulder', 0.00008)
aim((0.05, -0.12, 0.085), (0.0, 0.0, 0.06), 50)                     # the thighs: a key on each
render('thighs', 0.00008)
aim((0.255, -0.085, floor_z + 0.035), (0.255, 0.0, floor_z + 0.002), 50)   # the scales' rounded edges
render('scales', 0.00008)
