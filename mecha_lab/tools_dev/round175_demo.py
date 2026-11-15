"""0.24.175 demo (user: "이거 -180 까지 틸트 되게 해 줘"): three Feather Lines along an arm, the same feather (Primary,
Turn -75 like the user's), Tilt 0 / -90 / -180 (top to bottom).  Cycles, shaded and with the wireframe.

    <blender python> round175_demo.py <out dir>
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
from mecha_lab import creature_light as cl, greeble_line as gl  # noqa: E402

C = bpy.context
S = C.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)


def mat(name, rgb, rough=0.5):
    m = bpy.data.materials.new(name)
    pb = m.node_tree.nodes['Principled BSDF']
    pb.inputs['Base Color'].default_value = (*rgb, 1)
    pb.inputs['Roughness'].default_value = rough
    return m


def label(text, loc, size=0.16):
    cu = bpy.data.curves.new(text, 'FONT')
    cu.body = text
    cu.size = size
    ob = bpy.data.objects.new('Label ' + text, cu)
    S.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (math.pi / 2, 0.0, 0.0)
    ob.data.materials.append(LABEL)
    return ob


LABEL = mat('Label', (0.04, 0.04, 0.04), 0.6)
st = gl.settings(S, 'FEATHER')
arms = []
for k, tilt in enumerate((0, -90, -180)):
    z = 1.6 - k * 1.6
    bpy.ops.mesh.primitive_cylinder_add(radius=0.09, depth=3.2, location=(0.0, 0.0, z), rotation=(0, math.pi / 2, 0))
    arm = C.active_object
    arm.name = f'Arm {tilt}'
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)   # (the line's points: its own space)
    bpy.ops.object.shade_smooth()
    arm.data.materials.append(mat(arm.name, (0.3, 0.24, 0.16), 0.5))
    arms.append(arm)
    C.view_layer.update()
    for o in C.selected_objects:
        o.select_set(False)
    arm.select_set(True)
    C.view_layer.objects.active = arm
    bpy.ops.mch.feather_pick(feather='PRIMARY')
    st.turn, st.tilt, st.scale, st.gap, st.scale_random = math.radians(-75), math.radians(tilt), 1.5, -0.6, 0.0
    pts = [(x, -0.09, 0.0) for x in np.linspace(-1.45, 1.45, 30)]
    nrm = [(0.0, -1.0, 0.0)] * len(pts)
    ln = gl.new_line(C, arm, pts, nrm, gl.picked(st), st, 'FEATHER')
    print('tilt', tilt, gl.rebuild(ln, C), 'feathers')
    gl.apply_line(C, ln)
    label(f'Tilt {tilt}', (-2.75, -0.3, z - 0.05))
for c_ in bpy.data.collections:
    if c_.name.startswith('MCH Cover') or (c_.name.endswith('Parts') and c_.name != 'Mechanical Parts'):
        c_.hide_render = True
for o in list(S.objects):
    if o.type == 'MESH' and gl.STAMP_TAG in o.keys():
        o.hide_render = True
S.world = bpy.data.worlds.new('Before')
cl.apply(S, 'soft_studio')
sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
S.collection.objects.link(sun)
sun.data.energy = 3.2
sun.rotation_euler = (math.radians(40), 0.0, math.radians(-30))
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
S.collection.objects.link(cam)
S.camera = cam
cam.location = (0.2, -7.0, 1.2)
cam.rotation_euler = (Vector((0.2, 0.0, 0.0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = 40
S.render.engine = 'CYCLES'
S.cycles.samples = 40
S.cycles.use_denoising = True
S.cycles.device = 'CPU'
S.render.resolution_x, S.render.resolution_y = 1400, 1000
wmat = mat('Wire', (1.0, 0.45, 0.05))
wmat.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (1.0, 0.45, 0.05, 1)
wmat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 1.5
SOURCES = [o for o in S.objects if o.type == 'MESH' and o.visible_get() and not o.hide_render
           and not any(c.hide_render for c in o.users_collection)]
for wire in (False, True):
    wires = []
    if wire:
        dg = C.evaluated_depsgraph_get()
        for src in SOURCES:
            me = bpy.data.meshes.new_from_object(src.evaluated_get(dg), depsgraph=dg)
            wo = bpy.data.objects.new(src.name + ' wire', me)
            S.collection.objects.link(wo)
            wo.matrix_world = src.matrix_world
            md = wo.modifiers.new('W', 'WIREFRAME')
            md.use_replace = True
            md.thickness = 0.0015
            me.materials.clear()
            me.materials.append(wmat)
            wires.append(wo)
    S.render.filepath = os.path.join(OUT, 'feather_tilt' + ('_wire' if wire else '_shaded') + '.png')
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print('saved', S.render.filepath, f'{time.time() - t0:.0f} s')
    for wo in wires:
        me = wo.data
        bpy.data.objects.remove(wo)
        bpy.data.meshes.remove(me)
