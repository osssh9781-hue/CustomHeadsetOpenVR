"""Plate Detail 4 (Rough Rim) demo (0.24.161): the ten presets drawn on a slab (outlines through a top view, as the
lasso gives them), each with its name; then a close look at Broken Concrete and Creature Skin.  Cycles, shaded and with
the wireframe (a wireframe shader on the plates: the plates are dense, a wireframe modifier would be millions of faces).

    <blender python> rough_plate_demo.py <out dir>
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

COLOURS = {'CONCRETE': (0.55, 0.55, 0.53), 'BROKEN': (0.5, 0.5, 0.48), 'STONE': (0.42, 0.4, 0.36),
           'COBBLE': (0.46, 0.42, 0.37), 'LAVA': (0.13, 0.12, 0.11), 'SKIN': (0.45, 0.36, 0.3),
           'SCALY': (0.26, 0.33, 0.22), 'WARTY': (0.38, 0.35, 0.2), 'BARK': (0.27, 0.18, 0.12),
           'ERODED': (0.66, 0.53, 0.38)}


def mat(name, rgb, rough=0.75):
    m = bpy.data.materials.new(name)
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (*rgb, 1)
    p.inputs['Roughness'].default_value = rough
    return m


def plate_mat(name, rgb, wire=False):
    """The colour darkened in the hollows of the rim texture (the plate's mch_rough attribute); ``wire``: the
    triangle edges drawn orange on it (a Wireframe node)."""
    m = mat(name, rgb)
    nt = m.node_tree
    p = nt.nodes['Principled BSDF']
    at = nt.nodes.new('ShaderNodeAttribute')
    at.attribute_name = pr.OUT_ATTR
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = -0.6
    mr.inputs['From Max'].default_value = 0.3
    mr.inputs['To Min'].default_value = 0.45
    mr.inputs['To Max'].default_value = 1.05
    nt.links.new(at.outputs['Fac'], mr.inputs['Value'])
    mul = nt.nodes.new('ShaderNodeMix')
    mul.data_type = 'RGBA'
    mul.blend_type = 'MULTIPLY'
    mul.inputs['Factor'].default_value = 1.0
    mul.inputs[6].default_value = (*rgb, 1)
    nt.links.new(mr.outputs['Result'], mul.inputs[7])
    col = mul.outputs[2]
    if wire:
        wf = nt.nodes.new('ShaderNodeWireframe')
        wf.use_pixel_size = True
        wf.inputs['Size'].default_value = 0.6
        mix = nt.nodes.new('ShaderNodeMix')
        mix.data_type = 'RGBA'
        nt.links.new(wf.outputs['Fac'], mix.inputs['Factor'])
        nt.links.new(col, mix.inputs[6])
        mix.inputs[7].default_value = (1.0, 0.45, 0.05, 1)
        col = mix.outputs[2]
        p.inputs['Emission Color'].default_value = (1.0, 0.45, 0.05, 1)
        nt.links.new(wf.outputs['Fac'], p.inputs['Emission Strength'])
    nt.links.new(col, p.inputs['Base Color'])
    return m


def blob(cx, cy, rx, ry, wob=0.12, n=72, k=3):
    return [[(500 + (cx + rx * math.cos(a) * (1 + wob * math.sin(k * a))) * 100,
              500 + (cy + ry * math.sin(a) * (1 + wob * math.cos(k * a + 1))) * 100)
             for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]]


bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, -0.15))
slab = C.active_object
slab.name = 'Slab'
slab.scale = (13.0, 7.2, 0.3)
bpy.ops.object.transform_apply(scale=True)
slab.data.materials.append(mat('Slab', (0.11, 0.115, 0.125), 0.6))
plates = {}
for i, pid in enumerate(pr.PRESET_IDS):
    cx, cy = -4.6 + (i % 5) * 2.3, 1.35 - (i // 5) * 2.75
    for o in C.selected_objects:
        o.select_set(False)
    C.view_layer.objects.active = None
    bpy.ops.mch.pdetail_rough_preset(preset=pid)                    # (nothing selected: for the next plate)
    C.view_layer.objects.active = slab
    t0 = time.time()
    msg = pd.perform(C, blob(cx, cy, 0.95, 0.82, k=3 + i % 3), TOP, 'DETAIL4')
    ob = C.active_object
    ob.data.materials.clear()
    ob.data.materials.append(plate_mat(pid, COLOURS[pid]))
    plates[pid] = ob
    dg = C.evaluated_depsgraph_get()
    print(msg, len(ob.evaluated_get(dg).data.polygons), 'faces', f'{time.time() - t0:.2f} s')
    bpy.ops.object.text_add(location=(cx - 0.95, cy - 1.32, 0.005))
    tx = C.active_object
    tx.data.body = pr.PRESETS[i][1]
    tx.data.size = 0.24
    tx.data.materials.append(mat('Label', (0.85, 0.85, 0.85), 0.5))

S.world = bpy.data.worlds.new('Before')
cl.apply(S, 'soft_studio')
sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
S.collection.objects.link(sun)
sun.data.energy = 3.5
sun.data.angle = math.radians(3)
sun.rotation_euler = (math.radians(58), 0.0, math.radians(-38))      # (low: the rim texture casts shadows)
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


def render(name, wire):
    for pid, ob in plates.items():
        ob.data.materials[0] = plate_mat(pid + (' wire' if wire else ''), COLOURS[pid], wire)
    S.render.filepath = os.path.join(OUT, name + '.png')
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print('saved', S.render.filepath, f'{time.time() - t0:.0f} s')


if not os.environ.get('ROUGH_DEMO_CLOSE_ONLY'):
    aim((0.0, -9.4, 7.6), (0.0, -0.45, 0.0), 31)
    S.render.resolution_x, S.render.resolution_y = 1800, 1000
    render('rough_grid_shaded', False)
    render('rough_grid_wire', True)
aim((-3.45, -5.3, 3.7), (-3.45, -0.1, 0.0), 36)        # Concrete, Broken Concrete behind; Creature Skin, Scaly Hide in front
S.render.resolution_x, S.render.resolution_y = 1800, 1000
render('rough_close_shaded', False)
render('rough_close_wire', True)
