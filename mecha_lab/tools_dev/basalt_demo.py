"""Columnar Basalt demo (0.24.163): three Plate Detail 4 outlines drawn on a rocky ground through a top view, each
started at a different end - from the left, from the right, from the near bottom corner - so each cliff of basalt
columns rises its own way (low where the drawing started, high at the far end).  Cycles, shaded and with the
wireframe, a wide view and a close one.

    <blender python> basalt_demo.py <out dir>
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
import mecha_lab  # noqa: E402

OUT = sys.argv[-1]
os.makedirs(OUT, exist_ok=True)
mecha_lab.register()
from mecha_lab import core_geometry as cg, creature_light as cl, plate_detail as pd  # noqa: E402

C = bpy.context
S = C.scene
for o in list(S.objects):
    bpy.data.objects.remove(o)
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)       # (looking down: 100 px = 1, (500, 500) = origin)


def blob(cx, cy, rx, ry, start, k=3, wob=0.12, n=72):
    a = np.linspace(0, 2 * math.pi, n, endpoint=False) + start
    return [[(500 + (cx + rx * math.cos(t) * (1 + wob * math.sin(k * t))) * 100,
              500 + (cy + ry * math.sin(t) * (1 + wob * math.cos(k * t + 1))) * 100) for t in a]]


bpy.ops.mesh.primitive_plane_add(size=14.0)
ground = C.active_object
bpy.ops.object.modifier_add(type='SUBSURF')
ground.modifiers[-1].levels = 5
ground.modifiers[-1].subdivision_type = 'SIMPLE'
bpy.ops.object.modifier_apply(modifier=ground.modifiers[-1].name)
for v in ground.data.vertices:                                       # (a gently uneven ground)
    v.co.z = 0.08 * math.sin(v.co.x * 0.9) * math.cos(v.co.y * 1.1)
gm = bpy.data.materials.new('Ground')
gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.24, 0.25, 0.21, 1)
gm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.9
ground.data.materials.append(gm)
bm_ = bpy.data.materials.new('Basalt')
nt = bm_.node_tree
pb = nt.nodes['Principled BSDF']
at = nt.nodes.new('ShaderNodeAttribute')
at.attribute_name = 'mch_column'
mix = nt.nodes.new('ShaderNodeMix')
mix.data_type = 'RGBA'
nt.links.new(at.outputs['Fac'], mix.inputs['Factor'])
mix.inputs[6].default_value = (0.06, 0.06, 0.065, 1)
mix.inputs[7].default_value = (0.2, 0.19, 0.175, 1)
nt.links.new(mix.outputs[2], pb.inputs['Base Color'])
pb.inputs['Roughness'].default_value = 0.7
cliffs = []
for name, loop in (('from the left', blob(-2.6, 0.6, 1.9, 1.1, math.pi)),
                   ('from the right', blob(2.4, 1.0, 1.5, 1.0, 0.0, k=4)),
                   ('from the near corner', blob(0.2, -2.0, 1.7, 1.1, -math.pi * 0.75, k=5))):
    for o in C.selected_objects:
        o.select_set(False)
    C.view_layer.objects.active = None
    bpy.ops.mch.pdetail_rough_preset(preset='BASALT')
    C.view_layer.objects.active = ground
    t0 = time.time()
    msg = pd.perform(C, loop, TOP, 'DETAIL4')
    ob = C.active_object
    ob.data.materials.clear()
    ob.data.materials.append(bm_)
    cliffs.append(ob)
    print(name, msg, f'{time.time() - t0:.2f} s')

S.world = bpy.data.worlds.new('Before')
cl.apply(S, 'soft_studio')
sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
S.collection.objects.link(sun)
sun.data.energy = 3.5
sun.data.angle = math.radians(2)
sun.rotation_euler = (math.radians(52), 0.0, math.radians(-35))
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
S.collection.objects.link(cam)
S.camera = cam
S.render.engine = 'CYCLES'
S.cycles.samples = 64
S.cycles.use_denoising = True
S.cycles.device = 'CPU'
S.render.image_settings.file_format = 'PNG'
wmat = bpy.data.materials.new('Wire')
wp = wmat.node_tree.nodes['Principled BSDF']
wp.inputs['Base Color'].default_value = (1.0, 0.45, 0.05, 1)
wp.inputs['Emission Color'].default_value = (1.0, 0.45, 0.05, 1)
wp.inputs['Emission Strength'].default_value = 1.5
wires = []
for ob in cliffs:
    me = ob.data.copy()
    wo = bpy.data.objects.new(ob.name + ' wire', me)
    S.collection.objects.link(wo)
    wo.matrix_world = ob.matrix_world
    md = wo.modifiers.new('W', 'WIREFRAME')
    md.thickness = 0.006
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


S.render.resolution_x, S.render.resolution_y = 1400, 900
aim((0.4, -10.5, 6.2), (0.0, -0.2, 0.4), 34)
render('basalt_wide')
aim((-0.6, -6.2, 2.3), (-2.4, 0.6, 0.55), 40)
render('basalt_close')
