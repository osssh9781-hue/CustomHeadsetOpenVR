"""0.24.167 demo (user: "이건 너무 인공물 같잖아" - the scales): Scale Line's built-in scales, organic - a pebble's round
section thicker at the root, an uneven outline, a soft uneven crease round it.  Three Scale Lines over a ball and the
five scales beside it; Cycles, shaded and with the wireframe.

    <blender python> round167_demo.py <out dir>
"""
import os
import sys
import math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'addon'))
import bpy
import numpy as np
from mathutils import Vector
import mecha_lab
mecha_lab.register()
from mecha_lab import greeble_line as gl
C = bpy.context; S = C.scene
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_uv_sphere_add(radius=2.0, segments=96, ring_count=48, location=(0, 0, 0))
ball = C.active_object; bpy.ops.object.shade_smooth()
scales = gl.make_starters(C, ball, 'SCALES')
for s_ in scales: s_.hide_render = True; s_.hide_set(True)
stg = gl.settings(S, 'CREATURE')
for yy in (-0.6, -0.15, 0.3):
    pts, nrm = [], []
    for t in np.linspace(-1.0, 1.0, 60):
        v = Vector((math.sin(t) * 2.0, yy, math.cos(t) * 2.0)).normalized() * 2.0
        pts.append(tuple(v)); nrm.append(tuple(v.normalized()))
    line = gl.new_line(C, ball, pts, nrm, gl.picked(stg), stg, 'CREATURE')
    gl.rebuild(line, C)
    gl.apply_line(C, line)
for i, (nm, me) in enumerate(gl._scale_meshes()):
    o = bpy.data.objects.new(nm + ' big', me); S.collection.objects.link(o)
    o.location = (3.2, -1.6 + i * 1.0, 0.0); o.scale = (0.85, 0.85, 0.85)
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam')); S.collection.objects.link(cam); S.camera = cam
cam.location = (2.4, -5.6, 3.0); cam.rotation_euler = (Vector((1.4, 0, 1.0)) - cam.location).to_track_quat('-Z', 'Y').to_euler(); cam.data.lens = 40
S.render.engine = 'CYCLES'; S.cycles.samples = 24; S.cycles.use_denoising = True; S.cycles.device = 'CPU'
S.world = bpy.data.worlds.new('W'); S.world.color = (0.3, 0.3, 0.32)
sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN')); S.collection.objects.link(sun)
sun.data.energy = 4.0; sun.rotation_euler = (math.radians(50), 0, math.radians(-30))
S.render.resolution_x, S.render.resolution_y = 1400, 800
wmat = bpy.data.materials.new('Wire')
pb = wmat.node_tree.nodes['Principled BSDF']
pb.inputs['Base Color'].default_value = (1.0, 0.45, 0.05, 1)
pb.inputs['Emission Color'].default_value = (1.0, 0.45, 0.05, 1)
pb.inputs['Emission Strength'].default_value = 1.5
dg = C.evaluated_depsgraph_get()
wires = []
for src_ in [o for o in S.objects if o.type == 'MESH' and o.visible_get() and not o.hide_render]:
    me = bpy.data.meshes.new_from_object(src_.evaluated_get(dg), depsgraph=dg)
    wo = bpy.data.objects.new(src_.name + ' wire', me)
    S.collection.objects.link(wo)
    wo.matrix_world = src_.matrix_world
    md = wo.modifiers.new('W', 'WIREFRAME')
    md.thickness = 0.006 / max(abs(v) for v in src_.matrix_world.to_scale())
    md.use_replace = True
    md.use_even_offset = False
    me.materials.clear()
    me.materials.append(wmat)
    wires.append(wo)
OUT = sys.argv[-1]
os.makedirs(OUT, exist_ok=True)
for wire in (False, True):
    for wo in wires:
        wo.hide_render = not wire
    S.render.filepath = os.path.join(OUT, 'scales' + ('_wire' if wire else '_shaded') + '.png')
    bpy.ops.render.render(write_still=True)
    print('saved', S.render.filepath)
