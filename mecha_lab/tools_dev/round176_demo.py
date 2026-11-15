"""0.24.176 demo (user: "곤충 날개도 크리쳐 클로스처럼 메쉬에 붙게 할 수 있어?", "벌레 날개도 처음 선 긋는 부분이 벌레
날개 [뿌리] 되게 해 줘"): a dragonfly - head, thorax, abdomen (three meshes, not joined); four Insect Wings drawn from
above, each started over the thorax (its root there) - the part over the thorax sits on it, the wings its children.  Left:
as drawn; right: the thorax moved up and rolled 25 deg - the wings with it.  Cycles, shaded (top) and wireframe (bottom).

    <blender python> round176_demo.py <out dir>
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
import mecha_lab  # noqa: E402

OUT = sys.argv[-1]
os.makedirs(OUT, exist_ok=True)
mecha_lab.register()
from mecha_lab import core_geometry as cg, creature_light as cl, insect_wing as iw  # noqa: E402

C = bpy.context
S = C.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
TOP = cg.OrthoProjector(Euler((0, 0, 0)).to_quaternion(), pixels_per_unit=200.0)


def mat(name, rgb, rough=0.4, metal=0.0):
    m = bpy.data.materials.new(name)
    pb = m.node_tree.nodes['Principled BSDF']
    pb.inputs['Base Color'].default_value = (*rgb, 1)
    pb.inputs['Roughness'].default_value = rough
    pb.inputs['Metallic'].default_value = metal
    return m


def part(name, loc, scale, rgb):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32, location=loc)
    ob = C.active_object
    ob.name = name
    ob.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.shade_smooth()
    ob.data.materials.append(mat(name, rgb, 0.35, 0.3))
    return ob


thorax = part('Thorax', (0.0, 0.0, 0.0), (0.22, 0.32, 0.2), (0.05, 0.18, 0.12))
head = part('Head', (0.0, 0.42, 0.02), (0.17, 0.13, 0.13), (0.04, 0.12, 0.09))
abdomen = part('Abdomen', (0.0, -1.25, -0.02), (0.07, 0.95, 0.07), (0.05, 0.16, 0.12))
C.view_layer.update()


def wing(side, y0, L, Wd, sweep):
    """A wing from the thorax (started there) out to ``side`` (+1 right / -1 left), seen from above."""
    n = 40
    lead = [(side * (0.05 + L * i / (n - 1)), y0 + 0.03 * L * math.sin(math.pi * i / (n - 1)) - sweep * (i / (n - 1)) ** 2)
            for i in range(n)]
    trail = [(side * (0.05 + L * (1 - i / (n - 1))),
              y0 - Wd * math.sin(math.pi * (1 - i / (n - 1))) ** 0.7 - sweep * (1 - i / (n - 1)) ** 2) for i in range(n)]
    pts = lead + trail[1:]
    return [[TOP.to_screen(Vector((x, y, 3.0))) for x, y in pts]]


S.mch_wing.preset = 'DRAGONFLY'
wings = []
for side in (1, -1):
    for y0, L, Wd, sw in ((0.16, 1.55, 0.3, 0.08), (-0.06, 1.45, 0.38, 0.18)):
        for o in C.selected_objects:
            o.select_set(False)
        print(iw.perform(C, wing(side, y0, L, Wd, sw), TOP))
        wings.append(C.active_object)
print('parents', [(w.name, w.parent and w.parent.name) for w in wings])
S.world = bpy.data.worlds.new('Before')
cl.apply(S, 'soft_studio')
sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
S.collection.objects.link(sun)
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(35), 0.0, math.radians(-25))
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
S.collection.objects.link(cam)
S.camera = cam
cam.location = (2.2, -3.2, 3.0)
cam.rotation_euler = (Vector((0.0, -0.35, 0.15)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = 38
S.render.engine = 'CYCLES'
S.cycles.samples = 48
S.cycles.use_denoising = True
S.cycles.device = 'CPU'
S.render.resolution_x, S.render.resolution_y = 1200, 900
wmat = mat('Wire', (1.0, 0.45, 0.05))
wmat.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (1.0, 0.45, 0.05, 1)
wmat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 1.5


def shoot(tag):
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
                me.materials.append(wmat)
                made.append(wo)
        S.render.filepath = os.path.join(OUT, f'wing_stick_{tag}_{"wire" if wire else "shaded"}.png')
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print('saved', S.render.filepath, f'{time.time() - t0:.0f} s')
        for wo in made:
            me = wo.data
            bpy.data.objects.remove(wo)
            bpy.data.meshes.remove(me)


shoot('drawn')
thorax.location = (0.0, 0.0, 0.25)
thorax.rotation_euler = (0.0, math.radians(25), 0.0)            # (rolled round its length)
C.view_layer.update()
shoot('moved')
