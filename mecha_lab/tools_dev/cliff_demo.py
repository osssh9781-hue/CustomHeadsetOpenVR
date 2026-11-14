"""Rock styles demo (0.24.163): Plate Detail 4's new styles on a rocky ground (outlines through a top view, as the lasso
gives them) - Layered Cliff (a sea cliff's face on the top: slanted strata slabs, joints; rising toward the north),
Columnar Basalt (rising toward the east), Creature Carapace (a raised lip along the outline with lines on it, a groove,
the middle a smooth ridge).  Cycles, shaded and with the wireframe (a wireframe shader: the cliff / carapace are dense),
a wide view and close ones.

    <blender python> cliff_demo.py <out dir>
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
from mecha_lab import core_geometry as cg, creature_light as cl, plate_detail as pd, plate_rough as pr  # noqa: E402

C = bpy.context
S = C.scene
for o in list(S.objects):
    bpy.data.objects.remove(o)
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)       # (looking down: 100 px = 1, (500, 500) = origin)


def blob(cx, cy, rx, ry, k=3, wob=0.12, n=72):
    a = np.linspace(0, 2 * math.pi, n, endpoint=False)
    return [[(500 + (cx + rx * math.cos(t) * (1 + wob * math.sin(k * t))) * 100,
              500 + (cy + ry * math.sin(t) * (1 + wob * math.cos(k * t + 1))) * 100) for t in a]]


def mat(name, rgb, rough=0.8, wire=False, attr=None):
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    pb = nt.nodes['Principled BSDF']
    pb.inputs['Roughness'].default_value = rough
    col = None
    if attr == 'mch_column':
        at = nt.nodes.new('ShaderNodeAttribute')
        at.attribute_name = attr
        mx = nt.nodes.new('ShaderNodeMix')
        mx.data_type = 'RGBA'
        nt.links.new(at.outputs['Fac'], mx.inputs['Factor'])
        mx.inputs[6].default_value = tuple(c * 0.55 for c in rgb) + (1,)
        mx.inputs[7].default_value = (*rgb, 1)
        col = mx.outputs[2]
    elif attr:
        at = nt.nodes.new('ShaderNodeAttribute')
        at.attribute_name = attr
        mr = nt.nodes.new('ShaderNodeMapRange')
        mr.inputs['From Min'].default_value = -0.8
        mr.inputs['From Max'].default_value = 0.5
        mr.inputs['To Min'].default_value = 0.4
        mr.inputs['To Max'].default_value = 1.1
        nt.links.new(at.outputs['Fac'], mr.inputs['Value'])
        mx = nt.nodes.new('ShaderNodeMix')
        mx.data_type = 'RGBA'
        mx.blend_type = 'MULTIPLY'
        mx.inputs['Factor'].default_value = 1.0
        mx.inputs[6].default_value = (*rgb, 1)
        nt.links.new(mr.outputs['Result'], mx.inputs[7])
        col = mx.outputs[2]
    if col is None:
        pb.inputs['Base Color'].default_value = (*rgb, 1)
    if wire:
        wf = nt.nodes.new('ShaderNodeWireframe')
        wf.use_pixel_size = True
        wf.inputs['Size'].default_value = 0.7
        mix = nt.nodes.new('ShaderNodeMix')
        mix.data_type = 'RGBA'
        nt.links.new(wf.outputs['Fac'], mix.inputs['Factor'])
        if col is not None:
            nt.links.new(col, mix.inputs[6])
        else:
            mix.inputs[6].default_value = (*rgb, 1)
        mix.inputs[7].default_value = (1.0, 0.45, 0.05, 1)
        col = mix.outputs[2]
        pb.inputs['Emission Color'].default_value = (1.0, 0.45, 0.05, 1)
        nt.links.new(wf.outputs['Fac'], pb.inputs['Emission Strength'])
    if col is not None:
        nt.links.new(col, pb.inputs['Base Color'])
    return m


bpy.ops.mesh.primitive_plane_add(size=16.0)
ground = C.active_object
bpy.ops.object.modifier_add(type='SUBSURF')
ground.modifiers[-1].levels = 5
ground.modifiers[-1].subdivision_type = 'SIMPLE'
bpy.ops.object.modifier_apply(modifier=ground.modifiers[-1].name)
for v in ground.data.vertices:                                       # (a gently uneven ground)
    v.co.z = 0.06 * math.sin(v.co.x * 0.9) * math.cos(v.co.y * 1.1)
ground.data.materials.append(mat('Ground', (0.23, 0.25, 0.2), 0.9))
LOOK = {'CLIFF': ((0.5, 0.47, 0.41), 'mch_rough'), 'BASALT': ((0.2, 0.19, 0.18), 'mch_column'),
        'CARAPACE': ((0.15, 0.15, 0.14), 'mch_rough')}
plates = {}
for preset, compass, loop in (('CLIFF', 'N', blob(-3.0, 0.8, 2.2, 1.5)),
                              ('BASALT', 'E', blob(1.6, 1.4, 1.6, 1.1, k=4)),
                              ('CARAPACE', 'E', blob(0.6, -2.2, 1.9, 1.15, k=5))):
    for o in C.selected_objects:
        o.select_set(False)
    C.view_layer.objects.active = None
    bpy.ops.mch.pdetail_rough_preset(preset=preset)
    bpy.ops.mch.pdetail_compass(direction=compass)
    C.view_layer.objects.active = ground
    t0 = time.time()
    msg = pd.perform(C, loop, TOP, 'DETAIL4')
    ob = C.active_object
    plates[preset] = ob
    print(preset, compass, msg, f'{time.time() - t0:.2f} s',
          len(ob.evaluated_get(C.evaluated_depsgraph_get()).data.polygons), 'faces')

S.world = bpy.data.worlds.new('Before')
cl.apply(S, 'soft_studio')
sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
S.collection.objects.link(sun)
sun.data.energy = 3.5
sun.data.angle = math.radians(2)
sun.rotation_euler = (math.radians(62), 0.0, math.radians(-50))      # (low: the relief casts shadows)
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
S.collection.objects.link(cam)
S.camera = cam
S.render.engine = 'CYCLES'
S.cycles.samples = 64
S.cycles.use_denoising = True
S.cycles.device = 'CPU'
S.render.image_settings.file_format = 'PNG'


def aim(loc, look, lens):
    cam.location = loc
    cam.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens


def render(name):
    for wire in (False, True):
        for key, ob in plates.items():
            rgb, attr = LOOK[key]
            ob.data.materials.clear() if ob.data.materials else None
            m = mat(key + (' wire' if wire else ''), rgb, 0.75, wire, attr)
            if ob.data.materials:
                ob.data.materials[0] = m
            else:
                ob.data.materials.append(m)
        S.render.filepath = os.path.join(OUT, name + ('_wire' if wire else '_shaded') + '.png')
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print('saved', S.render.filepath, f'{time.time() - t0:.0f} s')


S.render.resolution_x, S.render.resolution_y = 1400, 900
aim((0.3, -10.5, 6.4), (-0.4, -0.2, 0.3), 32)
render('rock_wide')
aim((-1.4, -3.2, 2.0), (-3.0, 0.9, 0.3), 38)                         # the cliff, from the south-east: its slabs
render('rock_cliff')
aim((2.9, -4.6, 1.7), (0.6, -2.2, 0.05), 40)                         # the carapace
render('rock_carapace')
