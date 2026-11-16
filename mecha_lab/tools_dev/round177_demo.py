"""0.24.177 demo, Cycles, shaded and wireframe:
  molding - Edge Molding in Object Mode (user: "엣지 몰딩은 작동이 되긴 하는 거야?"): a line dragged across a hull and a
            ring drawn on it (moldings on its surface), a box clicked (along its 12 edges), a plate clicked (round its rim)
  mirror  - a Plate Detail 4 (rough rim) mirrored with the lean mirror (user: "미러가 개무거운데 좀 더 가볍고 빠르게")
  spikes  - Creature Spike Length (user: "크리쳐 스파이크는 길이 조절 좀 넣어 줘"): Length 1 / 2.5 / 2.5 + Random 0.6
  print   - Print Cut Sketch (user: "3d 프린트 ... 스케치 모드도 되게 해 줘"): a line drawn in three pieces, Enter - the
            ball cut along it, pegs in one half, holes in the other (the halves pulled apart)

    <blender python> round177_demo.py <out dir>
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

OUT = sys.argv[-1]
ONLY = set(os.environ.get('ONLY', 'molding,mirror,spikes,print').split(','))
os.makedirs(OUT, exist_ok=True)
mecha_lab.register()
from mecha_lab import core_geometry as cg, creature_light as cl, creature_spike as cs  # noqa: E402
from mecha_lab import edge_molding as em, mirror_tools as mt, plate_detail as pd, print3d as p3  # noqa: E402

C = bpy.context
S = C.scene
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)   # (looking +Y)


def px(x, z):
    return tuple(FRONT.to_screen(Vector((x, -6.0, z))))


def mat(name, rgb, rough=0.4, metal=0.0):
    m = bpy.data.materials.new(name)
    pb = m.node_tree.nodes['Principled BSDF']
    pb.inputs['Base Color'].default_value = (*rgb, 1)
    pb.inputs['Roughness'].default_value = rough
    pb.inputs['Metallic'].default_value = metal
    return m


def unselect():
    for o in C.selected_objects:
        o.select_set(False)
    C.view_layer.objects.active = None


def clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)


def stage(cam_loc, look, lens=40):
    S.world = bpy.data.worlds.new('W')
    cl.apply(S, 'soft_studio')
    sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
    S.collection.objects.link(sun)
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(40), 0.0, math.radians(-30))
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    S.collection.objects.link(cam)
    S.camera = cam
    cam.location = cam_loc
    cam.rotation_euler = (Vector(look) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens


S.render.engine = 'CYCLES'
S.cycles.samples = 40
S.cycles.use_denoising = True
S.cycles.device = 'CPU'
S.render.resolution_x, S.render.resolution_y = 1200, 900
WIRE = mat('Wire', (1.0, 0.45, 0.05))
WIRE.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (1.0, 0.45, 0.05, 1)
WIRE.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 1.5


def shoot(tag, thick=0.0012):
    for wire in (False, True):
        made = []
        if wire:
            dg = C.evaluated_depsgraph_get()
            for src in [o for o in S.objects if o.type == 'MESH' and o.visible_get() and not o.name.endswith(' wire')]:
                me = bpy.data.meshes.new_from_object(src.evaluated_get(dg), depsgraph=dg)
                wo = bpy.data.objects.new(src.name + ' wire', me)
                S.collection.objects.link(wo)
                wo.matrix_world = src.matrix_world
                md = wo.modifiers.new('W', 'WIREFRAME')
                md.use_replace = True
                md.thickness = thick
                me.materials.clear()
                me.materials.append(WIRE)
                made.append(wo)
        S.render.filepath = os.path.join(OUT, f'{tag}_{"wire" if wire else "shaded"}.png')
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print('saved', S.render.filepath, f'{time.time() - t0:.0f} s', flush=True)
        for wo in made:
            me = wo.data
            bpy.data.objects.remove(wo)
            bpy.data.meshes.remove(me)


# --- 1 Edge Molding -------------------------------------------------------------------------------------------------
def scene_molding():
    clear()
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    hull = C.active_object
    hull.name = 'Hull'
    hull.scale = (2.4, 1.6, 1.2)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=7)
    bpy.ops.object.mode_set(mode='OBJECT')
    hull.data.materials.append(mat('Hull', (0.32, 0.35, 0.38), 0.45, 0.6))
    bpy.ops.mesh.primitive_cube_add(size=0.9, location=(2.4, 0.0, 0.0))
    box = C.active_object
    box.name = 'Box'
    box.data.materials.append(mat('Box', (0.3, 0.33, 0.36), 0.45, 0.6))
    bpy.ops.mesh.primitive_plane_add(size=0.9, location=(-2.35, 0.1, 0.0), rotation=(math.pi / 2, 0, 0))
    plate = C.active_object
    plate.name = 'Plate'
    plate.data.materials.append(mat('Plate', (0.3, 0.33, 0.36), 0.45, 0.6))
    S.mch_molding.width, S.mch_molding.height, S.mch_molding.profile = 0.06, 0.035, 'CHAMFER'
    moldings = []
    unselect()
    ob, msg = em.perform_line(C, [px(x, 0.28 + 0.12 * math.sin(2.6 * x)) for x in np.linspace(-1.05, 1.05, 70)], FRONT)
    print(msg)
    moldings.append(ob)
    unselect()
    ob, msg = em.perform_line(C, [px(-0.35 + 0.42 * math.cos(t), -0.2 + 0.22 * math.sin(t))
                                  for t in np.linspace(0, 2 * math.pi, 64, endpoint=False)], FRONT, closed=True)
    print(msg)
    moldings.append(ob)
    S.mch_molding.profile = 'ROUND'
    S.mch_molding.width, S.mch_molding.height = 0.07, 0.035
    unselect()
    ob, msg = em.perform_click(C, px(2.4, 0.1), FRONT)
    print(msg)
    moldings.append(ob)
    unselect()
    ob, msg = em.perform_click(C, px(-2.35, 0.1), FRONT)
    print(msg)
    moldings.append(ob)
    brass = mat('Molding', (0.85, 0.55, 0.18), 0.3, 0.9)
    for m in moldings:
        m.data.materials.append(brass)
    stage((2.2, -7.0, 3.6), (0.0, 0.0, -0.1), lens=38)
    shoot('molding')


# --- 2 Mirror on a Plate Detail 4 -------------------------------------------------------------------------------------
def scene_mirror():
    clear()
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=96, ring_count=48)
    ball = C.active_object
    ball.name = 'Hull'
    bpy.ops.object.shade_smooth()
    ball.data.materials.append(mat('Hull', (0.3, 0.33, 0.36), 0.4, 0.6))
    unselect()
    print(pd.perform(C, [[px(0.42 + 0.3 * math.cos(t), 0.12 + 0.36 * math.sin(t))
                          for t in np.linspace(0, 2 * math.pi, 48, endpoint=False)]], FRONT, tool='DETAIL4'))
    det = C.active_object
    det.data.materials.clear()
    det.data.materials.append(mat('Rough', (0.42, 0.4, 0.37), 0.8))


    class _Reg:
        x = y = 0
        width, height = 1600, 900


    unselect()
    det.select_set(True)
    C.view_layer.objects.active = det
    op = mt.MirrorLeanLogic()
    op.start(C, _Reg(), FRONT, (800, 450))
    op.point_at = lambda *_a: False
    op.axes, op.flips = [True, False, False], [False, False, False]
    op._apply_live(S)
    print(op.finish_live(S))
    unselect()
    stage((0.0, -4.6, 1.2), (0.0, 0.0, 0.05), lens=45)
    shoot('mirror', thick=0.0006)


# --- 3 Creature Spike Length ------------------------------------------------------------------------------------------
def scene_spikes():
    clear()
    st = S.mch_spike
    st.use_fin, st.use_horn, st.use_hook, st.use_notch = False, True, False, False
    st.size, st.size_random, st.lean, st.lean_random, st.turn_random = 0.18, 0.0, 0.0, 0.0, 0.0
    spk = mat('Spike', (0.85, 0.8, 0.68), 0.5)
    skin = mat('Skin', (0.25, 0.3, 0.22), 0.6)
    for i, (length, rnd) in enumerate(((1.0, 0.0), (2.5, 0.0), (2.5, 0.6))):
        x0 = (i - 1) * 2.6
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.8, segments=64, ring_count=32, location=(x0, 0.0, 0.0))
        b = C.active_object
        bpy.ops.object.shade_smooth()
        b.data.materials.append(skin)
        st.length, st.length_random = length, rnd
        unselect()
        print(cs.perform(C, [px(x0 + x, 0.25) for x in np.linspace(-0.55, 0.55, 30)], FRONT))
        sp = C.active_object
        sp.data.materials.clear()
        sp.data.materials.append(spk)
    st.length, st.length_random = 1.0, 0.0
    stage((0.0, -5.5, 7.5), (0.0, -0.7, 0.0), lens=40)         # (from above: the spikes stand out toward -Y)
    shoot('spikes', thick=0.001)


# --- 4 Print Cut Sketch ------------------------------------------------------------------------------------------------
def scene_print():
    clear()
    R = 0.06                                                    # (print-sized: 12 cm across, the keys 8 mm)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5, radius=R)
    ball = C.active_object
    ball.name = 'Ball'
    ball.data.materials.append(mat('Print', (0.2, 0.45, 0.8), 0.45))
    unselect()
    proj = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0 / R)
    line = [(x * R, (0.1 + 0.25 * math.sin(x * 2.2)) * R) for x in np.linspace(-1.5, 1.5, 61)]
    p3.sketch_clear()
    for piece in (line[20:41], line[40:61][::-1], line[0:21]):
        p3.sketch_add(C, [tuple(proj.to_screen(Vector((x, -6.0 * R, z)))) for x, z in piece], False, proj,
                      Vector((0, 0, 0)))
    print(p3.sketch_commit(C))
    parts = [o for o in S.objects if o.get(p3.FROM_KEY) == 'Ball' and not o.get(p3.PIN_KEY)]
    C.view_layer.update()
    for o in parts:                                   # (pulled apart: the upper half up and turned to show its face)
        if sum((o.matrix_world @ Vector(c)).z for c in o.bound_box) / 8 > 0.1 * R:
            o.location.z += 0.75 * R
    stage((2.4 * R, -5.0 * R, 3.6 * R), (0.0, 0.0, 0.2 * R), lens=42)
    S.camera.data.clip_start = 0.001
    shoot('print_sketch', thick=0.00005)


for _nm in ('molding', 'mirror', 'spikes', 'print'):
    if _nm in ONLY:
        globals()['scene_' + _nm]()
print('done')
