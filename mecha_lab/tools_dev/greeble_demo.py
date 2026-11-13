"""Greeble Line demo (0.24.150): a dark torso with machine parts packed along lines drawn on it (the starter parts),
shaded and with the wireframe.

    <blender python> greeble_demo.py <out dir>
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'addon'))
import mecha_lab  # noqa: E402

OUT = sys.argv[-1]
os.makedirs(OUT, exist_ok=True)
mecha_lab.register()
from mecha_lab import creature_light as cl, geo_sculpt as gs, greeble_line as gl  # noqa: E402

C = bpy.context
S = C.scene
for o in list(S.objects):
    bpy.data.objects.remove(o)

# a torso: a stretched sphere, smooth
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=96, ring_count=48, location=(0, 0, 1.3))
body = C.active_object
body.scale = (0.75, 0.48, 1.15)
bpy.ops.object.transform_apply(scale=True)
bpy.ops.object.shade_smooth()
skin = bpy.data.materials.new('Dark Skin')
pb = skin.node_tree.nodes['Principled BSDF']
pb.inputs['Base Color'].default_value = (0.025, 0.025, 0.028, 1)
pb.inputs['Roughness'].default_value = 0.32
body.data.materials.append(skin)

st = gl.settings(S)
C.view_layer.objects.active = body
starters = gl.make_starters(C, body)
metal = bpy.data.materials.new('Dark Metal')
pm = metal.node_tree.nodes['Principled BSDF']
pm.inputs['Base Color'].default_value = (0.06, 0.06, 0.065, 1)
pm.inputs['Metallic'].default_value = 0.85
pm.inputs['Roughness'].default_value = 0.3
for o in starters:
    o.data.materials.append(metal)
st.hide_parts = True

caster = gs.SurfaceCaster(C, body)


def surface_line(fn, n=160):
    """A line on the torso: fn(t) -> a point in front of it, pressed onto the surface (nearest)."""
    pts, nrm = [], []
    for t in np.linspace(0.0, 1.0, n):
        hit = caster.nearest(Vector(fn(t)) + Vector((0.0, 0.0, 1.3)))   # (fn: about the torso's middle)
        if hit is not None:
            pts.append(tuple(hit[0]))
            nrm.append(tuple(hit[1]))
    return np.array(pts), np.array(nrm)


lines = []
# ribs across the chest (arcs at many heights, packed), a spine down the middle, diagonals over the shoulders
for k, z in enumerate(np.linspace(0.6, -0.55, 12)):
    half = 1.05 - 0.35 * abs(z - 0.05)
    lines.append((lambda t, z=z, h=half: (0.9 * math.sin(-h + 2 * h * t), -0.9 * math.cos(-h + 2 * h * t), z),
                  dict(order='RANDOM', scale=0.32, scale_random=0.3, rows=2, row_gap=0.0, flip_random=True,
                       turn_random=0.0, seed=k)))
lines.append((lambda t: (0.0, -0.9, 0.8 - 1.5 * t), dict(order='SEQ', scale=0.5, rows=1, seed=20)))
lines.append((lambda t: (-0.7 + 0.55 * t, -0.9, 0.95 - 0.25 * t), dict(order='RANDOM', scale=0.3, rows=3, seed=21)))
lines.append((lambda t: (0.7 - 0.55 * t, -0.9, 0.95 - 0.25 * t), dict(order='RANDOM', scale=0.3, rows=3, seed=22)))
made = []
for fn, cfg in lines:
    for k_, v in cfg.items():
        setattr(st, k_, v)
    p, n = surface_line(fn)
    ob = gl.new_line(C, body, p, n, gl.picked(st), st)
    gl.rebuild(ob, C, caster)
    made.append(ob)
print('lines', len(made), 'parts', sum(len(o.data.vertices) for o in made))

# light, camera
S.world = bpy.data.worlds.new('Before')
cl.apply(S, 'low_key')
cs = cl.settings(S)
cs.fill = 2.0
cs.floor = 'FADE'
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
S.collection.objects.link(cam)
S.camera = cam
cam.data.lens = 55
cam.location = (1.2, -4.6, 1.6)
cam.rotation_euler = (Vector((0, 0, 1.3)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
S.render.engine = 'CYCLES'
S.cycles.samples = 48
S.cycles.use_denoising = True
S.cycles.device = 'CPU'
S.render.resolution_x, S.render.resolution_y = 720, 900
S.render.image_settings.file_format = 'PNG'

# the wireframe version: wire copies of everything (the lines realized for it)
wmat = bpy.data.materials.new('Wire')
wmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (1.0, 0.45, 0.05, 1)
wmat.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (1.0, 0.45, 0.05, 1)
wmat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 2.0
dg = C.evaluated_depsgraph_get()
wires = []
for src in [body] + made:
    gs.set_input(src.modifiers['MCH Greeble'], 'Realize', True) if gl.is_line(src) else None
dg = C.evaluated_depsgraph_get()
dg.update()
for src in [body] + made:
    me = bpy.data.meshes.new_from_object(src.evaluated_get(dg), depsgraph=dg)
    wo = bpy.data.objects.new(src.name + ' wire', me)
    S.collection.objects.link(wo)
    wo.matrix_world = src.matrix_world
    md = wo.modifiers.new('W', 'WIREFRAME')
    md.thickness = 0.0025
    md.use_replace = True
    md.use_even_offset = False
    me.materials.clear()
    me.materials.append(wmat)
    wires.append(wo)
for src in made:
    gs.set_input(src.modifiers['MCH Greeble'], 'Realize', False)
for name, wire in (('greeble_shaded', False), ('greeble_wire', True)):
    for wo in wires:
        wo.hide_render = not wire
    S.render.filepath = os.path.join(OUT, name + '.png')
    bpy.ops.render.render(write_still=True)
    print('saved', S.render.filepath)
