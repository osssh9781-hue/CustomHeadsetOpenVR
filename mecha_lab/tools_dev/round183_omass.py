"""0.24.183 Creature Base Mesh 2 (user: "라쏘로 그리면 그 형태에 따라서 바위나 비늘, 버섯, 수정 그런 큰 덩어리의 오가닉한
물질 프리셋"): every matter drawn in an outline that suits it, through a front view - Cycles.

    <blender python> round183_omass.py grid <out dir>     the twelve side by side, shaded and wireframe
    <blender python> round183_omass.py thumbs             the window's picture tiles (icons/thumbs/omass_<ID>.png)
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

args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
MODE = args[0] if args else 'grid'
OUT = args[1] if len(args) > 1 else os.path.join(HERE, '..', 'addon', 'mecha_lab', 'icons', 'thumbs')
os.makedirs(OUT, exist_ok=True)
mecha_lab.register()
from mecha_lab import core_geometry as cg, creature_light as cl, organic_mass as om  # noqa: E402
C = bpy.context
S = C.scene
S.render.engine = 'CYCLES'
S.cycles.device = 'CPU'
S.cycles.use_denoising = True
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)


def dense(pts, n=120):
    P = np.array(pts + pts[:1], float)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    t = np.linspace(0.0, s[-1], n, endpoint=False)
    return list(zip(np.interp(t, s, P[:, 0]), np.interp(t, s, P[:, 1])))


def radial(rfun, sx=1.0, sz=1.0, n=120, floor=None):
    out = []
    for a in np.linspace(0, 2 * math.pi, n, endpoint=False):
        r = rfun(a)
        z = r * math.sin(a) * sz
        if floor is not None:
            z = max(z, floor)
        out.append((r * math.cos(a) * sx, z))
    return out


def mushroom():
    cap = [(0.75 * math.cos(a), 0.22 + 0.48 * math.sin(a)) for a in np.linspace(0, math.pi, 40)]
    under = [(-0.62, 0.1), (-0.3, 0.08), (-0.16, 0.06), (-0.17, -0.35), (-0.24, -0.6), (0.24, -0.6), (0.17, -0.35),
             (0.16, 0.06), (0.3, 0.08), (0.62, 0.1)]
    return dense(cap + under, 160)


def crystal():
    pts = []
    k = 9
    for i in range(k * 2 + 1):
        a = math.radians(-12 + (204 * i) / (k * 2))
        r = 0.85 if i % 2 == 0 else 0.42
        r *= 1.0 - 0.18 * abs(math.cos(a))
        pts.append((r * math.cos(a), -0.35 + r * math.sin(a) * 1.15))
    pts += [(-0.5, -0.55), (0.5, -0.55)][::-1]
    return dense(pts, 160)


def shell():
    pts = [(-0.14, -0.6), (0.14, -0.6)]
    for th in np.linspace(math.radians(22), math.radians(158), 90):
        r = 1.05 + 0.035 * math.sin(th * 30)
        pts.append((r * math.cos(th), -0.6 + r * math.sin(th) * 0.95))
    return dense(pts, 160)


def ice():
    rng = np.random.default_rng(4)
    a = np.sort(rng.random(8) * 2 * math.pi)
    return dense([(float(math.cos(x) * (0.55 + 0.25 * rng.random())), float(math.sin(x) * (0.5 + 0.2 * rng.random())))
                  for x in a], 120)


def bark():
    return radial(lambda a: 1.0, sx=1.0, sz=1.0, n=1) if False else [
        (0.42 * math.copysign(abs(math.cos(a)) ** 0.45, math.cos(a)) * (1 + 0.06 * math.sin(5 * a)),
         0.8 * math.copysign(abs(math.sin(a)) ** 0.45, math.sin(a))) for a in np.linspace(0, 2 * math.pi, 120,
                                                                                              endpoint=False)]


def tail():
    top = [(x, 0.32 * (1 - (x + 1.0) / 2.0) ** 0.8 + 0.05 * math.sin(x * 3)) for x in np.linspace(-1.0, 1.0, 60)]
    bot = [(x, -0.3 * (1 - (x + 1.0) / 2.0) ** 0.8 + 0.04 * math.sin(x * 3)) for x in np.linspace(1.0, -1.0, 60)]
    return top + bot


SHAPES = {
    'BONEFLAKE': radial(lambda a: 0.75 * (1 + 0.18 * math.cos(a - 1.2) + 0.06 * math.sin(3 * a)), sz=0.8),
    'KELOID': radial(lambda a: 0.72 * (1 + 0.08 * math.sin(3 * a) + 0.05 * math.cos(5 * a))),
    'HIDE': radial(lambda a: 0.7 * (1 + 0.12 * math.sin(2 * a + 0.5) + 0.05 * math.sin(4 * a)), sx=1.1),
    'WARTS': [(0.95 * math.cos(a) * (1 - 0.2 * math.sin(a)), 0.38 * math.sin(a) * (1 + 0.25 * math.cos(a)))
              for a in np.linspace(0, 2 * math.pi, 120, endpoint=False)],
    'SCALEROWS': tail(),
    'POLYPS': radial(lambda a: 0.8 * (1 + 0.05 * math.sin(5 * a)), sz=0.7, floor=-0.25),
    'ROCK': radial(lambda a: 0.72 * (1 + 0.12 * math.sin(3 * a) + 0.06 * math.sin(5 * a + 1)), floor=-0.48),
    'SCALE': [(0.55 * math.sin(t) * (1 - 0.45 * math.cos(t)), 0.78 * math.cos(t)) for t in
              np.linspace(0, 2 * math.pi, 120, endpoint=False)],
    'MUSHROOM': mushroom(),
    'CRYSTAL': crystal(),
    'CORAL': radial(lambda a: 0.8 * (1 + 0.05 * math.sin(4 * a)), sz=0.75, floor=-0.2),
    'BONE': [(0.75 * math.cos(a), 0.22 * math.sin(a) * (1 + 1.3 * abs(math.cos(a)) ** 6))
             for a in np.linspace(0, 2 * math.pi, 140, endpoint=False)],
    'SHELL': shell(),
    'LAVA': radial(lambda a: 0.7 * (1 + 0.1 * math.sin(2 * a) + 0.08 * math.sin(5 * a)), sx=1.15, floor=-0.42),
    'FLESH': radial(lambda a: 0.62 * (1 + 0.16 * math.sin(4 * a) + 0.05 * math.sin(7 * a))),
    'ICE': ice(),
    'SPONGE': radial(lambda a: 0.6 * (1 + 0.1 * math.sin(3 * a)), sx=0.75, sz=1.3),
    'BARK': bark(),
}


def px(x, z):
    return tuple(FRONT.to_screen(Vector((x, -3.0, z))))


def make(kid, x0=0.0, z0=0.0):
    S.mch_omass.kind = kid
    loop = [[px(x0 + x, z0 + z) for x, z in SHAPES[kid]]]
    for o in C.selected_objects:
        o.select_set(False)
    C.view_layer.objects.active = None
    om.perform(C, loop, FRONT)
    return C.active_object


def clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)


def lights(energy=2.6):
    S.world = bpy.data.worlds.new('W')
    cl.apply(S, 'soft_studio')
    sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
    S.collection.objects.link(sun)
    sun.data.energy = energy
    sun.data.angle = math.radians(6)
    sun.rotation_euler = (math.radians(55), 0.0, math.radians(-32))


def camera(loc, look, lens=50):
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    S.collection.objects.link(cam)
    S.camera = cam
    cam.location = loc
    cam.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens


clear()
if MODE == 'thumbs':
    S.cycles.samples = 32
    S.render.resolution_x = S.render.resolution_y = 192
    S.view_settings.exposure = -1.0
    lights()
    camera((0.9, -3.6, 0.75), (0.0, 0.0, 0.0), lens=58)
    only = set(os.environ.get('ONLY', '').split(',')) - {''}
    for kid, *_r in om.KINDS:
        if only and kid not in only:
            continue
        ob = make(kid)
        S.render.filepath = os.path.join(OUT, f'omass_{kid}.png')
        bpy.ops.render.render(write_still=True)
        print('saved', S.render.filepath, flush=True)
        bpy.data.objects.remove(ob)
else:
    S.cycles.samples = 64
    S.render.resolution_x, S.render.resolution_y = 1600, 1000
    S.view_settings.exposure = -1.2
    lights()
    only = [k for k in os.environ.get('ONLY', '').split(',') if k]
    kinds = [k[0] for k in om.KINDS if not only or k[0] in only]
    cols = 4 if len(kinds) > 6 else 3
    for i, kid in enumerate(kinds):
        x0 = (i % cols - (cols - 1) / 2) * 2.0
        z0 = ((len(kinds) - 1) // cols / 2.0 - i // cols) * 2.0
        ob = make(kid, x0, z0)
        dg = C.evaluated_depsgraph_get()
        print(kid, len(ob.evaluated_get(dg).data.polygons), flush=True)
    rows = (len(kinds) + cols - 1) // cols
    camera((1.2 * cols / 4, -11.5 * max(cols / 4, rows / 3), 1.2), (0.0, 0.0, 0.0), lens=48)
    WIRE = bpy.data.materials.new('Wire')
    pb = WIRE.node_tree.nodes['Principled BSDF']
    pb.inputs['Base Color'].default_value = (1.0, 0.45, 0.05, 1)
    pb.inputs['Emission Color'].default_value = (1.0, 0.45, 0.05, 1)
    pb.inputs['Emission Strength'].default_value = 1.5
    for wire in (False, True):
        made = []
        if wire:
            dg = C.evaluated_depsgraph_get()
            for src in [o for o in S.objects if om.is_mass(o)]:
                me = bpy.data.meshes.new_from_object(src.evaluated_get(dg), depsgraph=dg)
                wo = bpy.data.objects.new(src.name + ' wire', me)
                S.collection.objects.link(wo)
                wo.matrix_world = src.matrix_world
                md = wo.modifiers.new('W', 'WIREFRAME')
                md.use_replace = True
                md.thickness = 0.0025
                me.materials.clear()
                me.materials.append(WIRE)
                made.append(wo)
                src.hide_render = True
        else:
            for src in S.objects:
                src.hide_render = False
        S.render.filepath = os.path.join(OUT, f'omass_{"wire" if wire else "shaded"}.png')
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print('saved', S.render.filepath, f'{time.time() - t0:.0f} s', flush=True)
        for wo in made:
            me = wo.data
            bpy.data.objects.remove(wo)
            bpy.data.meshes.remove(me)
print('done')
