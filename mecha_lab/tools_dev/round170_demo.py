"""0.24.170 demo: live Scale Lines / Greeble Lines with a material, NOT applied - three creature balls (skin):
1) a Scale Line with the parts' own material (as before), 2) the same with "Body's Material" (the creature's skin on
every scale), 3) a Scale Line with the Creature page's "Reptile Dry" and a Greeble Line with the Mech page's "Steel".
All still live (the window's sliders still change them).  Cycles, shaded and with the wireframe.

    <blender python> round170_demo.py <out dir>
"""
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'addon'))
import mecha_lab  # noqa: E402

OUT = sys.argv[-1]
os.makedirs(OUT, exist_ok=True)
mecha_lab.register()
from mecha_lab import (creature_light as cl, creature_shader as cs, geo_sculpt as gs, greeble_line as gl,  # noqa: E402
                       mech_shader as ms)

C = bpy.context
S = C.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
skin = bpy.data.materials.new('Skin')
pb = skin.node_tree.nodes['Principled BSDF']
pb.inputs['Base Color'].default_value = (0.55, 0.36, 0.28, 1)
pb.inputs['Roughness'].default_value = 0.55


def line(ball, which, kind, yy, span=1.0):
    gl.make_starters(C, ball, which)
    C.view_layer.update()
    stg = gl.settings(S, kind)
    pts, nrm = [], []
    for t in np.linspace(-span, span, 50):
        v = Vector((math.sin(t), yy, math.cos(t))).normalized()
        pts.append(tuple(v))                                          # (the ball's own space)
        nrm.append(tuple(v))
    ln = gl.new_line(C, ball, pts, nrm, gl.picked(stg), stg, kind)
    gl.rebuild(ln, C)
    return ln


balls, lines = [], []
for k in range(3):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32, location=(k * 2.8, 0.0, 0.0))
    ball = C.active_object
    ball.name = f'Creature {k + 1}'
    bpy.ops.object.shade_smooth()
    ball.data.materials.append(skin)
    balls.append(ball)
s1 = line(balls[0], 'SCALES', 'CREATURE', -0.55)                    # 1) the parts' own
s2 = line(balls[1], 'SCALES', 'CREATURE', -0.55)                    # 2) Body's Material (the window's button)
for o in C.selected_objects:
    o.select_set(False)
s2.select_set(True)
C.view_layer.objects.active = s2
print(bpy.ops.mch.greeble_material(action='BODY'))
s3 = line(balls[2], 'SCALES', 'CREATURE', -0.55)                    # 3) the Creature page's Reptile Dry
rep = cs.new_material('REPTILE', 'CLEAN')
getattr(rep, cs.KEY).size = cs.body_size([balls[2]])
ms.assign(C, [s3], rep)
g3 = line(balls[2], 'MECH', 'MECH', 0.15, span=0.9)                  # ... and a Greeble Line with the Mech page's Steel
ms.assign(C, [g3], ms.new_material('STEEL'))
for ln in (s1, s2, s3, g3):
    print(ln.name, 'live', gl.is_line(ln), 'material', getattr(gl.line_material(ln), 'name', "the parts' own"))

for cn in ('Scale Parts', 'Greeble Parts'):                         # (the parts' originals beside: not in the picture)
    if bpy.data.collections.get(cn):
        bpy.data.collections[cn].hide_render = True
S.world = bpy.data.worlds.new('Before')
cl.apply(S, 'soft_studio')
sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
S.collection.objects.link(sun)
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(50), 0.0, math.radians(-25))
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
S.collection.objects.link(cam)
S.camera = cam
cam.data.clip_start = 0.01
S.render.engine = 'CYCLES'
S.cycles.samples = 48
S.cycles.use_denoising = True
S.cycles.device = 'CPU'
S.render.image_settings.file_format = 'PNG'
wmat = bpy.data.materials.new('Wire')
wp = wmat.node_tree.nodes['Principled BSDF']
wp.inputs['Base Color'].default_value = (1.0, 0.45, 0.05, 1)
wp.inputs['Emission Color'].default_value = (1.0, 0.45, 0.05, 1)
wp.inputs['Emission Strength'].default_value = 1.5
# the wireframe copies: the lines realized for them only (the lines themselves stay live instances)
for ln in (s1, s2, s3, g3):
    gs.set_input(ln.modifiers['MCH Greeble'], 'Realize', True)
C.view_layer.update()
dg = C.evaluated_depsgraph_get()
wires = []
for src in [o for o in S.objects if o.type == 'MESH' and o.visible_get() and o.name in
            {b.name for b in balls} | {ln.name for ln in (s1, s2, s3, g3)}]:
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
    wires.append((wo, md))
for ln in (s1, s2, s3, g3):
    gs.set_input(ln.modifiers['MCH Greeble'], 'Realize', False)
C.view_layer.update()
print('still live after the wire copies:', [gl.is_line(ln) for ln in (s1, s2, s3, g3)])


def aim(loc, look, lens):
    cam.location = loc
    cam.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens


def render(name, thick):
    for wire in (False, True):
        for wo, md in wires:
            wo.hide_render = not wire
            md.thickness = thick
        S.render.filepath = os.path.join(OUT, name + ('_wire' if wire else '_shaded') + '.png')
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print('saved', S.render.filepath, f'{time.time() - t0:.0f} s')


S.render.resolution_x, S.render.resolution_y = 1800, 760
aim((2.8, -10.5, 5.2), (2.8, 0.0, 0.1), 40)
render('line_material_all', 0.003)
S.render.resolution_x, S.render.resolution_y = 1200, 900
aim((5.6, -3.0, 2.4), (5.6, 0.0, 0.55), 50)                          # 3) up close: Reptile Dry scales, Steel greebles
render('line_material_close', 0.002)
