"""0.24.183 Body Kit pictures - Cycles.

    <blender python> round183_bodykit.py thumbs              the window's two tiles (icons/thumbs/bodykit_<kit>.png)
    <blender python> round183_bodykit.py show <out dir>      the kits as sculpted / shaped / with muscles, shaded + wire
"""
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'addon'))
import mecha_lab  # noqa: E402

args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
MODE = args[0] if args else 'thumbs'
OUT = args[1] if len(args) > 1 else os.path.join(HERE, '..', 'addon', 'mecha_lab', 'icons', 'thumbs')
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
mecha_lab.register()
from mecha_lab import body_kit as bk, muscle_gen as mg  # noqa: E402
C = bpy.context
S = C.scene
S.render.engine = 'CYCLES'
S.cycles.device = 'CPU'
S.cycles.use_denoising = True
S.world = bpy.data.worlds.new('W')
S.world.use_nodes = True
S.world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.16, 0.16, 0.18, 1)
sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
S.collection.objects.link(sun)
sun.data.energy = 3.2
sun.data.angle = math.radians(8)
sun.rotation_euler = (math.radians(52), 0.0, math.radians(-28))
fill = bpy.data.objects.new('Fill', bpy.data.lights.new('Fill', 'SUN'))
S.collection.objects.link(fill)
fill.data.energy = 0.8
fill.rotation_euler = (math.radians(70), 0.0, math.radians(150))
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
S.collection.objects.link(cam)
S.camera = cam
cam.data.type = 'ORTHO'


def look(loc, at, scale):
    cam.location = loc
    cam.rotation_euler = (Vector(at) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.ortho_scale = scale


def wire_pass(objs, path):
    W = bpy.data.materials.new('Wire')
    pb = W.node_tree.nodes['Principled BSDF']
    pb.inputs['Base Color'].default_value = (1.0, 0.45, 0.05, 1)
    pb.inputs['Emission Color'].default_value = (1.0, 0.45, 0.05, 1)
    pb.inputs['Emission Strength'].default_value = 1.5
    dg = C.evaluated_depsgraph_get()
    made = []
    for o in objs:
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), depsgraph=dg)
        wo = bpy.data.objects.new(o.name + ' wire', me)
        S.collection.objects.link(wo)
        wo.matrix_world = o.matrix_world
        md = wo.modifiers.new('W', 'WIREFRAME')
        md.use_replace = True
        md.thickness = 0.0014
        md.use_even_offset = False
        me.materials.clear()
        me.materials.append(W)
        made.append(wo)
        o.hide_render = True
    S.render.filepath = path
    bpy.ops.render.render(write_still=True)
    for wo in made:
        me = wo.data
        bpy.data.objects.remove(wo)
        bpy.data.meshes.remove(me)
    for o in objs:
        o.hide_render = False


if MODE == 'thumbs':
    S.cycles.samples = 32
    S.render.resolution_x = S.render.resolution_y = 128
    for kit in ('human', 'creature'):
        root = bk.make_kit(C, kit, height=1.8, location=(0, 0, 0))
        look((1.2, -6.0, 1.05), (0.0, 0.0, 0.92), 2.05)
        S.render.filepath = os.path.join(OUT, f'bodykit_{kit}.png')
        bpy.ops.render.render(write_still=True)
        for o in bk.parts_of(root):
            bpy.data.objects.remove(o)
else:
    S.cycles.samples = 48
    S.render.resolution_x, S.render.resolution_y = 2000, 1100
    rows = []
    # human: as sculpted / long legs + broad shoulders + build / posed; creature the same
    for i, (kit, x) in enumerate((('human', -3.0), ('human', -1.5), ('human', 0.0), ('creature', 1.5),
                                   ('creature', 3.0))):
        r = bk.make_kit(C, kit, height=1.8, location=(x, 0, 0))
        kp = r.mch_bodykit
        if i == 1:
            kp.legs, kp.shoulders, kp.build, kp.muscle, kp.definition = 1.18, 1.18, 1.1, 0.8, 0.6
        if i == 2:
            kp.arms, kp.torso, kp.hips, kp.build, kp.head = 1.1, 0.9, 1.15, 0.85, 1.1
            for o in bk.parts_of(r):
                n = bk.info(o)['name']
                if n == 'UpperArm.L':
                    o.rotation_euler = (math.radians(-35), math.radians(-25), 0)
                if n == 'Forearm.L':
                    o.rotation_euler = (math.radians(-70), 0, 0)
                if n == 'Thigh.R':
                    o.rotation_euler = (math.radians(-30), 0, 0)
                if n == 'Shin.R':
                    o.rotation_euler = (math.radians(40), 0, 0)
            bk.refresh(r)
        if i == 4:
            kp.legs, kp.arms, kp.muscle = 1.15, 1.1, 0.6
        rows.append(r)
    objs = [o for r in rows for o in bk.parts_of(r)]
    look((0.0, -12.0, 1.0), (0.0, 0.0, 1.0), 8.4)
    S.render.filepath = os.path.join(OUT, 'bodykit_shapes_shaded.png')
    bpy.ops.render.render(write_still=True)
    wire_pass(objs, os.path.join(OUT, 'bodykit_shapes_wire.png'))
    for o in objs:
        bpy.data.objects.remove(o)
    # muscles from the user's sculpts on both kits (front / back)
    made = []
    for kit, x in (('human', -1.1), ('creature', 1.1)):
        r = bk.make_kit(C, kit, height=1.8, location=(x, 0, 0))
        for o in bk.parts_of(r):
            d = bk.info(o)
            if d['slot'] in bk.PART_SETS and d['side'] in ('', 'L'):
                bk.put_muscles(C, o)
                tw = bk.twin(o)
                if tw is not None:
                    bk.put_muscles(C, tw)
        made += bk.parts_of(r)
    mus = [o for o in S.objects if mg.is_muscle(o)]
    print('muscles', len(mus), sum(len(o.data.polygons) for o in mus), 'faces', flush=True)
    for side, loc in (('front', (0.0, -12.0, 1.15)), ('back', (0.0, 12.0, 1.15))):
        look(loc, (0.0, 0.0, 1.15), 4.6)
        S.render.filepath = os.path.join(OUT, f'bodykit_muscles_{side}_shaded.png')
        bpy.ops.render.render(write_still=True)
        wire_pass(made + mus, os.path.join(OUT, f'bodykit_muscles_{side}_wire.png'))
print('done')
