"""3D Print demo (0.24.164): the test human scaled to 200 mm tall for printing (Scale to Height), cut at the waist
(Peg: pegs on the legs, holes in the upper body) at the thighs (below the hands: a piece of the cut per leg, pins
on each) and at the neck (Dowel: holes in both, separate pins), the parts moved
apart to show the pins.  Cycles, shaded and with the wireframe; a wide view and a close look at the thigh cut.

    <blender python> print3d_demo.py <out dir>
"""
import math
import os
import sys
import time

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'addon'))
sys.path.insert(0, HERE)
import mecha_lab  # noqa: E402
import make_test_human as mth  # noqa: E402

OUT = sys.argv[-1]
os.makedirs(OUT, exist_ok=True)
mecha_lab.register()
from mecha_lab import creature_light as cl, print3d as p3  # noqa: E402

C = bpy.context
S = C.scene
human = mth.build(3)
for o in C.selected_objects:
    o.select_set(False)
human.select_set(True)
C.view_layer.objects.active = human
pg = S.mch_print
pg.fit_height = 200.0
bpy.ops.mch.print_scale_height()
C.view_layer.update()
sz = p3.size_of(C, [human])
print('scaled', [round(x * 1000, 1) for x in sz], 'mm')
bb = p3.world_bounds(C, [human])
z0 = bb[0].z
pg.pin_style = 'PEG'
pg.pin_count = 'AUTO'
pg.pin_auto = True
pg.clearance = 0.2
pg.gap = 0.0
t0 = time.time()
legs, upper, _pins, msg = p3.cut_with_pins(C, human, Vector((0, 0, z0 + 0.072)), Vector((0, 0, 1)))
print(msg, f'{time.time() - t0:.2f} s')
pg.pin_style = 'DOWEL'
t0 = time.time()
body, head, pins, msg = p3.cut_with_pins(C, upper, Vector((0, 0, z0 + 0.172)), Vector((0, 0, 1)))
print(msg, f'{time.time() - t0:.2f} s')
upper_parts = [body, head]
body.location.z += 0.03
head.location.z += 0.06
for p in pins:
    p.location.z += 0.045
C.view_layer.update()


def mat(name, rgb, rough=0.55):
    m = bpy.data.materials.new(name)
    pb = m.node_tree.nodes['Principled BSDF']
    pb.inputs['Base Color'].default_value = (*rgb, 1)
    pb.inputs['Roughness'].default_value = rough
    return m


plastic = mat('PLA', (0.72, 0.74, 0.78), 0.45)
pinmat = mat('Pin', (1.0, 0.45, 0.08), 0.4)
for o in (legs, body, head):
    o.data.materials.clear()
    o.data.materials.append(plastic)
for p in pins:
    p.data.materials.clear()
    p.data.materials.append(pinmat)
bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, 0, z0))
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
S.render.engine = 'CYCLES'
S.cycles.samples = 64
S.cycles.use_denoising = True
S.cycles.device = 'CPU'
S.render.image_settings.file_format = 'PNG'
wmat = mat('Wire', (1.0, 0.45, 0.05))
wmat.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (1.0, 0.45, 0.05, 1)
wmat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 1.5
wires = []
for src in (legs, body, head, *pins):
    me = src.data.copy()
    wo = bpy.data.objects.new(src.name + ' wire', me)
    S.collection.objects.link(wo)
    wo.matrix_world = src.matrix_world
    md = wo.modifiers.new('W', 'WIREFRAME')
    md.thickness = 0.00012
    md.use_replace = True
    md.use_even_offset = False
    me.materials.clear()
    me.materials.append(wmat)
    wires.append(wo)


def aim(loc, look, lens):
    cam.location = loc
    cam.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens


def render(name):
    for wire in (False, True):
        for wo in wires:
            wo.hide_render = not wire
        S.render.filepath = os.path.join(OUT, name + ('_wire' if wire else '_shaded') + '.png')
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print('saved', S.render.filepath, f'{time.time() - t0:.0f} s')


S.render.resolution_x, S.render.resolution_y = 900, 1100
aim((0.16, -0.36, z0 + 0.19), (0.0, 0.0, z0 + 0.135), 50)
render('print_wide')
S.render.resolution_x, S.render.resolution_y = 1100, 900
aim((0.06, -0.14, z0 + 0.13), (0.0, 0.0, z0 + 0.085), 55)            # the thighs: pegs below, holes above
render('print_cut')
