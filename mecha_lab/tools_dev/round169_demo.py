"""0.24.169 demo: Creature Hair's eight styles, each its own colour - Dreads (black), Tentacles (fox), Quills (white),
Strands (brown), Straight Hair (blonde), Perm (auburn), Beard (dark brown, on the chin), Animal Fur (fox) - on eight
heads; Perm and Beard mirrored from one side by the head's live Mirror.  Cycles, shaded and with the
wireframe.

    <blender python> round169_demo.py <out dir>
"""
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Euler, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'addon'))
import mecha_lab  # noqa: E402

OUT = sys.argv[-1]
os.makedirs(OUT, exist_ok=True)
mecha_lab.register()
from mecha_lab import core_geometry as cg, creature_hair as ch, creature_light as cl, symmetry  # noqa: E402

C = bpy.context
S = C.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
skin = bpy.data.materials.new('Skin')
skin.use_nodes = True
skin.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.62, 0.5, 0.42, 1)
skin.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.55
st = S.mch_hair
ROWS = (('STRAIGHT', 'BLONDE'), ('PERM', 'AUBURN'), ('BEARD', 'DARK_BROWN'), ('FUR', 'FOX'),   # (in front: the new)
        ('DREADS', 'BLACK'), ('TENTACLE', 'FOX'), ('QUILLS', 'WHITE'), ('STRANDS', 'BROWN'))
heads = []
for k, (style, colour) in enumerate(ROWS):
    x, y, z = (k % 4) * 3.2, (k // 4) * 4.5, 0.0      # (rows one behind the other: the rays from above / the front
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32, location=(x, y, z))   # hit their own)
    head = C.active_object
    head.name = f'Head {style.title()}'
    bpy.ops.object.shade_smooth()
    head.data.materials.append(skin)
    mirrored = style in ('PERM', 'BEARD')
    if mirrored:
        symmetry.set_mode(C, head, 'MIRROR')
        symmetry.mirror_mod(head).mirror_object = None      # (each head mirrored about its own middle, not the world's)
    st.style = style
    _k, _l, root, tip = next(c for c in ch.COLOUR_PRESETS if c[0] == colour)
    st.colour_mode, st.root_colour, st.tip_colour = 'OWN', root, tip
    if style == 'BEARD':                          # (the chin, seen from the front; one side - the Mirror makes the other)
        P = cg.OrthoProjector(Euler((math.pi / 2, 0.0, 0.0)).to_quaternion(), center=Vector((x, y, z)),
                              pixels_per_unit=100.0)
        loop = [[(500 + (0.38 + 0.34 * math.cos(t)) * 100, 500 + (-0.5 + 0.3 * math.sin(t)) * 100)
                 for t in np.linspace(0, 2 * math.pi, 36, endpoint=False)]]       # (the jaw, one side)
    else:
        P = cg.OrthoProjector(Quaternion(), center=Vector((x, y, z)), pixels_per_unit=100.0)
        if mirrored:
            loop = [[(500 + (0.35 + 0.3 * math.cos(t)) * 100, 500 + 0.45 * math.sin(t) * 100)
                     for t in np.linspace(0, 2 * math.pi, 36, endpoint=False)]]
        else:
            rad = 0.85 if style == 'FUR' else 0.55
            loop = [[(500 + rad * math.cos(t) * 100, 500 + rad * math.sin(t) * 100)
                     for t in np.linspace(0, 2 * math.pi, 48, endpoint=False)]]
    for o in C.selected_objects:
        o.select_set(False)
    head.select_set(True)
    C.view_layer.objects.active = head
    t0 = time.time()
    print(ch.perform(C, loop, P), f'{time.time() - t0:.1f} s')
    heads.append(head)

S.world = bpy.data.worlds.new('Before')
cl.apply(S, 'soft_studio')
sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
S.collection.objects.link(sun)
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(55), 0.0, math.radians(-25))
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
pb = wmat.node_tree.nodes['Principled BSDF']
pb.inputs['Base Color'].default_value = (1.0, 0.45, 0.05, 1)
pb.inputs['Emission Color'].default_value = (1.0, 0.45, 0.05, 1)
pb.inputs['Emission Strength'].default_value = 1.5
dg = C.evaluated_depsgraph_get()
wires = []
for src in [o for o in S.objects if o.type == 'MESH' and o.visible_get()]:
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


S.render.resolution_x, S.render.resolution_y = 1600, 1000
aim((4.8, -12.5, 6.5), (4.8, 2.4, -0.6), 40)
render('hair_all', 0.004)
S.render.resolution_x, S.render.resolution_y = 1400, 800
aim((4.8, -8.0, 1.6), (4.8, 0.0, -0.4), 45)                        # Straight, Perm, Beard, Fur up close
render('hair_close', 0.003)
