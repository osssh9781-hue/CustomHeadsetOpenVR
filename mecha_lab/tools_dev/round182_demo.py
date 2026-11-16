"""0.24.182 demo, Cycles, shaded and wireframe: Plate Detail 4's creature presets (user: "크리쳐 작업할 때 디테일 넣으려구
- 오마카세로") drawn on a creature's back - Croc Osteoderm, Dragon Hide, Turtle Shell, Rhino Hide, Barnacle Crust,
Insect Chitin, Elephant Skin, Armadillo Bands, Snake Scales (Detail 4: the wireframe fits in memory).

    <blender python> round182_demo.py <out dir>
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
S.render.engine = 'CYCLES'
S.cycles.samples = 48
S.cycles.use_denoising = True
S.cycles.device = 'CPU'
S.render.resolution_x, S.render.resolution_y = 1400, 900


def mat(name, rgb, rough=0.5, metal=0.0):
    m = bpy.data.materials.new(name)
    pb = m.node_tree.nodes['Principled BSDF']
    pb.inputs['Base Color'].default_value = (*rgb, 1)
    pb.inputs['Roughness'].default_value = rough
    pb.inputs['Metallic'].default_value = metal
    return m


WIRE = mat('Wire', (1.0, 0.45, 0.05))
WIRE.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (1.0, 0.45, 0.05, 1)
WIRE.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 1.5
for _o in list(bpy.data.objects):                   # (the default scene's cube, camera, light)
    bpy.data.objects.remove(_o)
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=160, ring_count=80)
back = C.active_object
back.name = 'Back'
back.scale = (3.4, 2.2, 0.9)
bpy.ops.object.transform_apply(scale=True)
bpy.ops.object.shade_smooth()
back.data.materials.append(mat('Hide', (0.2, 0.19, 0.17), 0.6))
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)


def blob(cx, cy, rx, ry, n=64, k=3, wob=0.08, seed=0):
    ph = seed * 1.7
    return [[(500 + (cx + rx * math.cos(a) * (1 + wob * math.sin(k * a + ph))) * 100,
              500 + (cy + ry * math.sin(a)) * 100) for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]]


plate_m = mat('Plate', (0.36, 0.33, 0.29), 0.55)
spots = [('CROC', -2.0, 0.85), ('DRAGON', 0.0, 1.0), ('TURTLE', 2.0, 0.85),
         ('RHINO', -2.2, -0.4), ('BARNACLE', -0.6, -0.15), ('CHITIN', 0.95, -0.2), ('ELEPHANT', 2.35, -0.45),
         ('ARMADILLO', -1.1, -1.35), ('SNAKE', 1.2, -1.35)]
for i, (pid, x, y) in enumerate(spots):
    for o in C.selected_objects:
        o.select_set(False)
    C.view_layer.objects.active = None
    bpy.ops.mch.pdetail_rough_preset(preset=pid)
    before = set(S.objects)
    pd.perform(C, blob(x, y, 0.62, 0.5, seed=i), TOP, 'DETAIL4')
    for o in set(S.objects) - before:
        if pd.is_detail(o):
            o.data.materials.clear()
            o.data.materials.append(plate_m)
            o.mch_pdetail.r_detail = 4.0              # (the window's Detail: lighter, so the wireframe fits in memory)
            dg_ = C.evaluated_depsgraph_get()
            print('plate', pid, o.name, len(o.evaluated_get(dg_).data.polygons), flush=True)
if os.environ.get('COUNT_ONLY'):
    sys.exit(0)
S.world = bpy.data.worlds.new('W')
cl.apply(S, 'soft_studio')
sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
S.collection.objects.link(sun)
sun.data.energy = 2.2
sun.rotation_euler = (math.radians(62), 0.0, math.radians(-35))
S.view_settings.exposure = -1.4
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
S.collection.objects.link(cam)
S.camera = cam
cam.location = (0.0, -6.2, 6.0)
cam.rotation_euler = (Vector((0.0, -0.1, 0.4)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = 44
for wire in (False, True):
    made = []
    if wire:
        dg = C.evaluated_depsgraph_get()
        for src in [o for o in S.objects if o.type == 'MESH' and not o.name.endswith(' wire')]:
            me = bpy.data.meshes.new_from_object(src.evaluated_get(dg), depsgraph=dg)
            wo = bpy.data.objects.new(src.name + ' wire', me)
            S.collection.objects.link(wo)
            wo.matrix_world = src.matrix_world
            md = wo.modifiers.new('W', 'WIREFRAME')
            md.use_replace = True
            md.thickness = 0.0008
            me.materials.clear()
            me.materials.append(WIRE)
            made.append(wo)
    S.render.filepath = os.path.join(OUT, f'creature_presets_{"wire" if wire else "shaded"}.png')
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print('saved', S.render.filepath, f'{time.time() - t0:.0f} s', flush=True)
    for wo in made:
        me = wo.data
        bpy.data.objects.remove(wo)
        bpy.data.meshes.remove(me)
print('done')
