"""Fur demo (0.24.157): the test human with tiger-stripe polypaint and three furs drawn on it (the areas given as
outlines in pixels through a front view, as the Fur tool's lasso gives them): short striped fur over the chest and
belly (colour from the polypaint; three areas of one fur, each its own tilt - the middle straight down, the sides down
and out), pointed tufts on the forearms (Tip Gather - 0.24.160), fuller fur (Volume, Spread), a long clumped mane round the neck and shoulders, curly fleece on the upper arms.
Cycles, shaded and with the body's wireframe.

    <blender python> fur_demo.py <out dir>
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
sys.path.insert(0, HERE)
import mecha_lab  # noqa: E402
import make_test_human as mth  # noqa: E402

OUT = sys.argv[-1]
os.makedirs(OUT, exist_ok=True)
mecha_lab.register()
from mecha_lab import core_geometry as cg, creature_fur as cf, creature_light as cl  # noqa: E402

C = bpy.context
S = C.scene
human = mth.build(4)
me = human.data
co = np.empty(len(me.vertices) * 3, np.float32)
me.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
ca = me.color_attributes.new('Polypaint', 'FLOAT_COLOR', 'POINT')
stripe = np.sin(co[:, 2] * 38.0 + np.sin(co[:, 0] * 14.0) * 1.6) > 0.45
belly = (np.abs(co[:, 0]) < 0.09) & (co[:, 1] < 0)
base = np.where(belly[:, None], [[0.85, 0.8, 0.7, 1]], [[0.8, 0.36, 0.06, 1]])
ca.data.foreach_set('color', np.where(stripe[:, None] & ~belly[:, None], [[0.03, 0.025, 0.02, 1]], base)
                    .astype(np.float32).ravel())
me.color_attributes.active_color = ca
skin = bpy.data.materials.new('Skin')
skin.use_nodes = True
pb = skin.node_tree.nodes['Principled BSDF']
at = skin.node_tree.nodes.new('ShaderNodeAttribute')
at.attribute_name = 'Polypaint'
skin.node_tree.links.new(at.outputs['Color'], pb.inputs['Base Color'])
pb.inputs['Roughness'].default_value = 0.6
me.materials.append(skin)
C.view_layer.objects.active = human

FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), center=Vector((0.0, 0.0, 1.3)),
                          pixels_per_unit=500.0)          # (500 px = 1 m, (500, 500) = x 0, z 1.3)


def px(x, z):
    return 500 + x * 500, 500 + (z - 1.3) * 500


def poly(points):
    return [[px(x, z) for x, z in points]]


def ellipse(cx, cz, rx, rz, n=48):
    return poly([(cx + rx * math.cos(a), cz + rz * math.sin(a)) for a in np.linspace(0, 2 * math.pi, n, endpoint=False)])


def fur(area, **values):
    st = S.mch_fur
    for k, v in values.items():
        setattr(st, k, v)
    setattr(C.window_manager, cf.NEW_KEY, True)
    t0 = time.time()
    msg = cf.perform(C, area, FRONT)
    ob = C.active_object
    print(msg, f'({time.time() - t0:.2f} s)')
    return ob


furs = []
furs.append(fur(poly([(-0.07, 1.42), (0.07, 1.42), (0.07, 1.0), (-0.07, 1.0)]),     # chest and belly: Area 1 the
                density=110000.0, length=0.05, length_random=0.4, lie=math.radians(70), flow=0.0, gravity=0.3, curl=0.0,
                frizz=0.3, clump=0.25, clump_size=10, root_thick=0.0007, tip_thick=0.00008, segments=6,
                edge_soft=3, use_polypaint=True, tip_blend=0.15, tip_color=(0.95, 0.85, 0.65, 1.0)))
furs.append(fur(poly([(-0.22, 1.62), (0.22, 1.62), (0.23, 1.47), (0.1, 1.44), (-0.1, 1.44), (-0.23, 1.47)]),
                density=40000.0, length=0.16, length_random=0.35, lie=math.radians(50), gravity=1.6, curl=0.0, frizz=0.35,
                clump=0.55, clump_size=25, root_thick=0.0011, tip_thick=0.0001, segments=12, edge_soft=4,
                use_polypaint=False, root_color=(0.05, 0.035, 0.025, 1.0), tip_color=(0.55, 0.32, 0.12, 1.0),
                tip_blend=0.7))                                                   # the mane: long, clumped
for side in (1, -1):                                                              # upper arms: curly fleece
    furs.append(fur(ellipse(side * 0.27, 1.3, 0.07, 0.1), density=60000.0, length=0.05, length_random=0.3, lie=math.radians(32),
                    gravity=0.2, curl=0.9, curl_turns=3.0, frizz=0.15, clump=0.3, clump_size=8, root_thick=0.0009,
                    tip_thick=0.0003, segments=20, edge_soft=2, use_polypaint=False,
                    root_color=(0.82, 0.78, 0.7, 1.0), tip_color=(0.95, 0.93, 0.88, 1.0), tip_blend=0.5))
# (0.24.159) the chest fur's sides: two more areas of the same fur, each its own tilt - down and out from the middle
# (a V), less flat than the middle; drawn with the chest fur selected, then each area's Lie Down / Flow Angle set
chest = furs[0]
for side in (-1, 1):
    for o in C.selected_objects:
        o.select_set(False)
    chest.select_set(True)
    C.view_layer.objects.active = chest
    cf.perform(C, poly([(side * 0.07, 1.42), (side * 0.18, 1.42), (side * 0.16, 1.0), (side * 0.07, 1.0)]), FRONT)
    part = cf.current_part(chest)
    part.lie = math.radians(55)
    part.flow = math.radians(side * 55)
# (0.24.160) pointed tufts on the forearms: a small area each, its Tip Gather - the tips to one point at the end of
# its tilt
for side in (1, -1):
    t_ = fur(ellipse(side * 0.37, 1.07, 0.05, 0.06), density=60000.0, length=0.13, length_random=0.25,
             lie=math.radians(65), flow=0.0, gravity=0.2, curl=0.0, frizz=0.1, clump=0.0, root_thick=0.0012,
             tip_thick=0.0001, segments=10, edge_soft=2, use_polypaint=True, tip_blend=0.6,
             tip_color=(0.05, 0.04, 0.03, 1.0))
    cf.current_part(t_).gather = 0.85
    furs.append(t_)
print('chest areas', [(p_.name, round(math.degrees(p_.lie)), round(math.degrees(p_.flow))) for p_ in chest.mch_fur.parts])
total = sum(cf.strands(o) for o in furs)
print('furs', len(furs), 'strands', total)

S.world = bpy.data.worlds.new('Before')
cl.apply(S, 'soft_studio')
cs = cl.settings(S)
cs.floor = 'FADE'
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
S.collection.objects.link(cam)
S.camera = cam
cam.data.lens = 60
look = Vector((0.0, -0.05, 1.3))
cam.location = (0.75, -1.6, 1.5)
cam.rotation_euler = (look - cam.location).to_track_quat('-Z', 'Y').to_euler()
S.render.engine = 'CYCLES'
S.cycles.samples = 64
S.cycles.use_denoising = True
S.cycles.device = 'CPU'
S.render.resolution_x, S.render.resolution_y = 900, 1000
S.render.image_settings.file_format = 'PNG'

wmat = bpy.data.materials.new('Wire')
wmat.use_nodes = True
wp = wmat.node_tree.nodes['Principled BSDF']
wp.inputs['Base Color'].default_value = (1.0, 0.45, 0.05, 1)
wp.inputs['Emission Color'].default_value = (1.0, 0.45, 0.05, 1)
wp.inputs['Emission Strength'].default_value = 1.5
wme = human.data.copy()
wo = bpy.data.objects.new('Human wire', wme)
S.collection.objects.link(wo)
wo.matrix_world = human.matrix_world
md = wo.modifiers.new('W', 'WIREFRAME')
md.thickness = 0.0008
md.use_replace = True
md.use_even_offset = False
wme.materials.clear()
wme.materials.append(wmat)
for name, wire in (('fur_shaded', False), ('fur_wire', True)):
    wo.hide_render = not wire
    S.render.filepath = os.path.join(OUT, name + '.png')
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print('saved', S.render.filepath, f'{time.time() - t0:.0f} s')
# (0.24.159) a close look at the chest: the three areas' tilts - the middle straight down, the sides down and out
cam.data.lens = 50
look = Vector((0.0, -0.12, 1.22))
cam.location = (0.12, -0.78, 1.3)
cam.rotation_euler = (look - cam.location).to_track_quat('-Z', 'Y').to_euler()
S.render.resolution_x, S.render.resolution_y = 900, 900
for name, wire in (('fur_chest_shaded', False), ('fur_chest_wire', True)):
    wo.hide_render = not wire
    S.render.filepath = os.path.join(OUT, name + '.png')
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print('saved', S.render.filepath, f'{time.time() - t0:.0f} s')
