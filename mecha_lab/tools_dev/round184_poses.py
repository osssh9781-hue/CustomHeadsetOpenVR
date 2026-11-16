"""0.24.184 Body Kit poses and sizes (Daz-like: sliders, sizes, joints) - Cycles.

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


S.cycles.samples = 48
S.render.resolution_x, S.render.resolution_y = 2200, 1000
rows = []
SETS = (('human', 'CROUCH', {}), ('human', 'REACH', {'arm_size': 1.15}), ('creature', 'HUNCH', {'arm_size': 1.35, 'head': 0.85}),
        ('creature', 'POUNCE', {'leg_size': 1.2, 'hands': 1.3}), ('creature', 'ARMS_OUT', {'arm_size': 0.8, 'leg_size': 1.25}))
for i, (kit, pose, vals) in enumerate(SETS):
    r = bk.make_kit(C, kit, height=1.8, location=((i - 2) * 1.9, 0, 0))
    for k, v in vals.items():
        setattr(r.mch_bodykit, k, v)
    bk.set_pose(r, pose)
    rows.append(r)
objs = [o for r in rows for o in bk.parts_of(r)]
for side, loc in (('front', (5.0, -12.0, 2.2)), ('side', (12.0, -4.0, 2.2))):
    look(loc, (0.0, 0.0, 0.85), 10.0)
    S.render.filepath = os.path.join(OUT, f'poses_{side}_shaded.png')
    bpy.ops.render.render(write_still=True)
    wire_pass(objs, os.path.join(OUT, f'poses_{side}_wire.png'))
print('done')
