"""0.24.181 thumbnails (user: "플레이트 디테일 ... 다른 프리셋도 좀 많이 만들어 주라, 그리고 거기에 썸네일도 좀 만들어 줘, 그
다른 스케일 관련이나 깃털 같은 것도"): each Plate Detail 4 preset as it comes out (a plate drawn on a slab, Cycles), each
feather and each scale shape - into ``addon/mecha_lab/icons/thumbs/`` (rough_<ID>.png, feather_<ID>.png,
scale_<ID>.png), 192 px.

    <blender python> make_thumbs181.py [rough] [feathers] [scales] [ONLY=<ID>,...]
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Euler, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'addon'))
import mecha_lab  # noqa: E402

OUT = os.path.join(HERE, '..', 'addon', 'mecha_lab', 'icons', 'thumbs')
os.makedirs(OUT, exist_ok=True)
args = [a for a in sys.argv[sys.argv.index('--') + 1:]] if '--' in sys.argv else sys.argv[1:]
WHAT = {a for a in args if a in ('rough', 'feathers', 'scales')} or {'rough', 'feathers', 'scales'}
ONLY = set(os.environ.get('ONLY', '').split(',')) - {''}
mecha_lab.register()
from mecha_lab import core_geometry as cg, creature_shapes as cs, plate_detail as pd, plate_rough as pr  # noqa: E402
C = bpy.context
S = C.scene
S.render.engine = 'CYCLES'
S.cycles.samples = 28
S.cycles.use_denoising = True
S.cycles.device = 'CPU'
S.render.resolution_x = S.render.resolution_y = 192
S.render.film_transparent = False
S.view_settings.view_transform = 'Standard'


def clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)


def mat(name, rgb, rough=0.5, metal=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    pb = m.node_tree.nodes['Principled BSDF']
    pb.inputs['Base Color'].default_value = (*rgb, 1)
    pb.inputs['Roughness'].default_value = rough
    pb.inputs['Metallic'].default_value = metal
    return m


def stage(cam_loc, look, ortho=None, lens=50):
    w = bpy.data.worlds.get('Thumb') or bpy.data.worlds.new('Thumb')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.045, 0.047, 0.052, 1.0)
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
    S.world = w
    for name, rot, energy in (('Key', (math.radians(62), 0.0, math.radians(-38)), 2.4),
                              ('Rim', (math.radians(72), 0.0, math.radians(150)), 0.9)):
        L = bpy.data.objects.new(name, bpy.data.lights.new(name, 'SUN'))
        S.collection.objects.link(L)
        L.rotation_euler = rot
        L.data.energy = energy
        L.data.angle = math.radians(8)
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    S.collection.objects.link(cam)
    S.camera = cam
    cam.location = cam_loc
    cam.rotation_euler = (Vector(look) - Vector(cam_loc)).to_track_quat('-Z', 'Y').to_euler()
    if ortho:
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = ortho
    else:
        cam.data.lens = lens


def shoot(path):
    S.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('saved', path, flush=True)


TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)


def blob(rx, ry, n=64, k=3, wob=0.08):
    return [[(500 + rx * math.cos(a) * (1 + wob * math.sin(k * a)) * 100, 500 + ry * math.sin(a) * 100)
             for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]]


if 'rough' in WHAT:
    slab_m = mat('Slab', (0.05, 0.055, 0.06), 0.7)
    plate_m = mat('Plate', (0.3, 0.285, 0.27), 0.55)
    for pid, label, _d, _v in pr.PRESETS:
        if ONLY and pid not in ONLY:
            continue
        clear()
        bpy.ops.mesh.primitive_plane_add(size=4.0)
        slab = C.active_object
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.subdivide(number_cuts=60)
        bpy.ops.object.mode_set(mode='OBJECT')
        slab.data.materials.append(slab_m)
        for o in C.selected_objects:
            o.select_set(False)
        C.view_layer.objects.active = None
        bpy.ops.mch.pdetail_rough_preset(preset=pid)
        pd.perform(C, blob(1.15, 0.95), TOP, 'DETAIL4')
        plate = next((o for o in S.objects if pd.is_detail(o)), None)
        if plate is not None:
            plate.data.materials.clear()
            plate.data.materials.append(plate_m)
        stage((0.0, -2.2, 2.05), (0.0, -0.05, 0.0), lens=46)
        shoot(os.path.join(OUT, f'rough_{pid}.png'))

if 'feathers' in WHAT or 'scales' in WHAT:
    for kind in ('feathers', 'scales'):
        if kind not in WHAT:
            continue
        items = cs.feather_meshes() if kind == 'feathers' else cs.scale_meshes_real()
        for name, me in items:
            sid = me['mch_shape_id']
            if ONLY and sid not in ONLY:
                continue
            clear()
            ob = bpy.data.objects.new(name, me)
            S.collection.objects.link(ob)
            from mathutils import Matrix
            co = np.array([tuple(v.co) for v in me.vertices])
            ctr = (co.min(0) + co.max(0)) / 2
            me.transform(Matrix.Translation(Vector(-ctr)))          # (centred on its own middle)
            co = co - ctr
            size = float(np.ptp(co[:, :2], axis=0).max())
            if kind == 'feathers':           # (lying flat: seen from above, along the picture's diagonal)
                long_x = np.ptp(co[:, 0]) >= np.ptp(co[:, 1])
                me.transform(Matrix.Rotation(math.radians(45.0 if long_x else -45.0), 4, 'Z'))
                co2 = np.array([tuple(v.co) for v in me.vertices])
                size = float(np.ptp(co2[:, :2], axis=0).max())
                stage((0.0, 0.0, 6.0), (0.0, 0.0, 0.0), ortho=size * 1.1)
            else:                             # (a scale seen a little from the side: its relief)
                stage((0.0, -size * 1.35, size * 1.25), (0.0, 0.0, 0.0), ortho=size * 1.25)
            shoot(os.path.join(OUT, f'{kind[:-1]}_{sid}.png'))
print('done')
