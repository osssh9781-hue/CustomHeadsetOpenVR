"""Weathering demo (0.24.158): shapes made with the add-on's own Base Mesh / Creature Base Mesh (outlines given through
a top view, as the lasso gives them), each clicked with a Weathering tool: a block with snow on its top, a dust layer on
another, a dirt mound at their feet, leaves piled on the ground.  Cycles, shaded and with the wireframe.

    <blender python> weathering_demo.py <out dir>
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
from mecha_lab import base_mesh, core_geometry as cg, creature_light as cl, weathering as wx  # noqa: E402

C = bpy.context
S = C.scene
for o in list(S.objects):
    bpy.data.objects.remove(o)
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)


def blob(cx, cy, rx, ry, wob=0.15, n=48, k=3):
    return [[(500 + (cx + rx * math.cos(a) * (1 + wob * math.sin(k * a))) * 100,
              500 + (cy + ry * math.sin(a) * (1 + wob * math.cos(k * a + 1))) * 100) for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]]


def rect(x0, y0, x1, y1):
    return [[(500 + x * 100, 500 + y * 100) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]]


def shape(loops, creature=False, z=0.0, **base):
    pg = S.mch_cbase if creature else S.mch_base
    prev = S.mch_settings.mch_active_tool
    S.mch_settings.mch_active_tool = 'CBASE' if creature else 'BASE'
    pg.sketch = False
    for k, v in base.items():
        setattr(pg, k, v)
    before = set(bpy.data.objects)
    base_mesh.perform_base(C, loops, TOP)
    S.mch_settings.mch_active_tool = prev
    return [o for o in bpy.data.objects if o not in before][0]          # (on the surface under the outline already)


def mat(name, rgb, rough=0.5, metal=0.0):
    m = bpy.data.materials.new(name)
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (*rgb, 1)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    return m


def weather(ob, kind, **values):
    for k, v in values.items():
        setattr(wx.pg_of(S, kind), k, v)
    for o in C.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    C.view_layer.objects.active = ob
    t0 = time.time()
    r = bpy.ops.mch.weather_click('EXEC_DEFAULT', kind=kind)
    print(ob.name, kind, r, f'{time.time() - t0:.2f} s')


bpy.ops.mesh.primitive_plane_add(size=14.0)
ground = C.active_object
ground.data.materials.append(mat('Ground', (0.16, 0.16, 0.17), 0.8))
steel = mat('Painted Steel', (0.18, 0.24, 0.2), 0.45, 0.6)
block = shape(rect(-1.4, -0.7, 0.2, 0.7), profile='CHAMFER', height=1.4, bevel_width=0.08)
block.data.materials.append(steel)
block2 = shape(rect(0.8, -0.5, 2.2, 0.5), profile='CHAMFER', height=0.8, bevel_width=0.06)
block2.data.materials.append(steel)
snow = shape(blob(-0.6, 0.0, 0.75, 0.62, 0.12), creature=True, z=1.38, profile='PUFF', peak=0.12)
dust = shape(blob(1.5, 0.0, 0.62, 0.42, 0.1), z=0.8, profile='FLAT', height=0.015)
dirt = shape(blob(-0.3, -1.25, 1.25, 0.5, 0.2), profile='DOME', height=0.25)
leaves = shape(blob(1.7, -1.35, 1.1, 0.6, 0.25, k=4), profile='FLAT', height=0.01)
weather(snow, 'SNOW')
weather(dust, 'DUST', thickness=0.6)
weather(dirt, 'DIRT')
weather(leaves, 'LEAVES', density=500.0, leaf_size=0.07, pile=0.8, autumn=0.75)

S.world = bpy.data.worlds.new('Before')
cl.apply(S, 'soft_studio')
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
S.collection.objects.link(cam)
S.camera = cam
cam.data.lens = 42
look = Vector((0.3, -0.4, 0.55))
cam.location = (2.6, -6.2, 3.4)
cam.rotation_euler = (look - cam.location).to_track_quat('-Z', 'Y').to_euler()
S.render.engine = 'CYCLES'
S.cycles.samples = 64
S.cycles.use_denoising = True
S.cycles.device = 'CPU'
S.render.resolution_x, S.render.resolution_y = 1100, 800
S.render.image_settings.file_format = 'PNG'

wmat = mat('Wire', (1.0, 0.45, 0.05), 0.5)
wmat.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (1.0, 0.45, 0.05, 1)
wmat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 1.5
dg = C.evaluated_depsgraph_get()
wires = []
for src in (block, block2, snow, dust, dirt, leaves):
    if src is leaves:
        wx.pg_of(src, 'LEAVES').show_base = True
    me = bpy.data.meshes.new_from_object(src.evaluated_get(dg), depsgraph=dg)
    wo = bpy.data.objects.new(src.name + ' wire', me)
    S.collection.objects.link(wo)
    wo.matrix_world = src.matrix_world
    md = wo.modifiers.new('W', 'WIREFRAME')
    md.thickness = 0.004
    md.use_replace = True
    md.use_even_offset = False
    me.materials.clear()
    me.materials.append(wmat)
    wires.append(wo)
for name, wire in (('weathering_shaded', False), ('weathering_wire', True)):
    for wo in wires:
        wo.hide_render = not wire
    S.render.filepath = os.path.join(OUT, name + '.png')
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print('saved', S.render.filepath, f'{time.time() - t0:.0f} s')
