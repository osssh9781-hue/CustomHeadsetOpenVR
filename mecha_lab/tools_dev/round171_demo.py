"""0.24.171 demo: (1) a Fur drawn on one side of a head, bent toward the screen's left (Bend), applied - and the same
mirrored with Alt+X's mirror (hair curves now take it) and baked; (2) Creature Hair's Bend toward a side of the view;
(3) Vacuum Pack: five parts sealed in one clear film, the test human in black latex.  Cycles, shaded and with the
wireframe.

    <blender python> round171_demo.py <out dir>
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
from mecha_lab import (core_geometry as cg, creature_fur as cf, creature_hair as ch, creature_light as cl,  # noqa: E402
                       mirror_tools as mt, vacuum_pack as vp)

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


def select(*obs):
    for o in C.selected_objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    C.view_layer.objects.active = obs[0]


skin = mat('Skin', (0.55, 0.38, 0.3), 0.55)
# ---- (1) Fur: one side, bent; then mirrored --------------------------------------------------------------------
heads = []
for k, x in enumerate((-1.3, 1.3)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=96, ring_count=48, location=(x, 0.0, 0.0))
    h = C.active_object
    h.name = ('Head before', 'Head after')[k]
    bpy.ops.object.shade_smooth()
    h.data.materials.append(skin)
    heads.append(h)
    FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), center=Vector((x, 0, 0)), pixels_per_unit=200.0)
    st = S.mch_fur
    st.density, st.length, st.gravity, st.lie, st.frizz, st.clump, st.spread = 9000.0, 0.75, 2.2, 0.4, 0.05, 0.35, 0.15
    st.root_thick, st.tip_thick, st.use_polypaint = 0.006, 0.0015, False
    st.root_color, st.tip_color, st.tip_blend = (0.03, 0.025, 0.02, 1), (0.5, 0.42, 0.33, 1), 0.5
    st.bend, st.bend_at, st.bend_soft = 0.0, 0.45, 0.4
    loop = [[FRONT.to_screen(Vector((x + 0.5 + 0.22 * math.cos(t), -2.0, 0.35 + 0.35 * math.sin(t))))
             for t in np.linspace(0, 2 * math.pi, 48, endpoint=False)]]
    select(h)
    print(cf.perform(C, loop, FRONT))
    fur = C.active_object
    fur.mch_fur.bend_dir = (-1.0, 0.0, 0.0)                        # (Bend "Left" from the front view)
    fur.mch_fur.bend = math.radians(55)
    cf.apply_fur(C, fur)                                            # (the user's case: an applied fur)
    if k == 1:
        mt.setup_curves_mirror(fur, S.mch_mirror, S, axes=(True, False, False), center=Vector((x, 0.0, 0.0)))
        lg = mt.MirrorLeanLogic()
        lg.p, lg.target_names, lg.axes, lg.flips, lg.pivot_name = S.mch_mirror, [fur.name], [True, False, False], [False] * 3, None
        print(lg.finish_apply(C))
        print('mirrored fur curves', len(fur.data.curves))
# ---- (2) Creature Hair: Bend toward a side of the view -----------------------------------------------------------
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=96, ring_count=48, location=(4.2, 0.0, 0.0))
h3 = C.active_object
h3.name = 'Head hair bend'
bpy.ops.object.shade_smooth()
h3.data.materials.append(skin)
F3 = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), center=Vector((4.2, 0, 0)), pixels_per_unit=200.0)
S.mch_hair.style = 'STRAIGHT'
S.mch_hair.count = 220
S.mch_hair.colour_mode = 'OWN'
_k, _l, root, tip = next(c for c in ch.COLOUR_PRESETS if c[0] == 'AUBURN')
S.mch_hair.root_colour, S.mch_hair.tip_colour = root, tip
S.mch_hair.bend = 0.0
select(h3)
print(ch.perform(C, [[F3.to_screen(Vector((4.2 + 0.55 * math.cos(t), -2.0, 0.55 + 0.3 * math.sin(t))))
                      for t in np.linspace(0, 2 * math.pi, 48, endpoint=False)]], F3))
hair = C.active_object
hair.mch_hair.bend_dir = (1.0, 0.0, 0.0)                            # (Bend "Right" from the front view)
hair.mch_hair.bend_at, hair.mch_hair.bend_soft = 0.45, 0.35
hair.mch_hair.bend = math.radians(70)
# ---- (3) Vacuum Pack -----------------------------------------------------------------------------------------------
parts = []
base = Vector((-1.0, 4.5, -1.0))
for maker, kw, rgb in ((bpy.ops.mesh.primitive_uv_sphere_add, dict(radius=0.45, segments=48, ring_count=24, location=(-0.55, 0, 0.45)), (0.6, 0.08, 0.05)),
                       (bpy.ops.mesh.primitive_torus_add, dict(major_radius=0.35, minor_radius=0.12, location=(0.35, 0.1, 0.13)), (0.7, 0.55, 0.08)),
                       (bpy.ops.mesh.primitive_cone_add, dict(radius1=0.25, depth=0.7, location=(0.25, -0.35, 0.35)), (0.08, 0.2, 0.6)),
                       (bpy.ops.mesh.primitive_cube_add, dict(size=0.4, location=(-0.1, 0.45, 0.2)), (0.1, 0.45, 0.12)),
                       (bpy.ops.mesh.primitive_cylinder_add, dict(radius=0.12, depth=0.9, location=(0.65, 0.45, 0.45), rotation=(0.4, 0.3, 0)), (0.4, 0.4, 0.42))):
    kw['location'] = tuple(Vector(kw['location']) + base)
    maker(**kw)
    o = C.active_object
    o.data.materials.append(mat('Part', rgb, 0.45))
    parts.append(o)
select(*parts)
S.mch_vacuum.hug, S.mch_vacuum.creases, S.mch_vacuum.film = 0.55, 0.6, 'CLEAR'
film1, msg = vp.perform(C)
print(msg)
human = mth.build(3, clear=False)
human.location = (3.6, 4.6, -1.0)
human.scale = (5.0, 5.0, 5.0)
C.view_layer.update()
human.data.materials.clear()
human.data.materials.append(mat('Human', (0.6, 0.6, 0.62), 0.5))
select(human)
S.mch_vacuum.hug, S.mch_vacuum.creases, S.mch_vacuum.film = 0.6, 0.6, 'BLACK'
film2, msg = vp.perform(C)
print(msg)

# ---- scene -----------------------------------------------------------------------------------------------------------
bpy.ops.mesh.primitive_plane_add(size=40.0, location=(0, 0, -1.0))
floor = C.active_object
floor.data.materials.append(mat('Floor', (0.5, 0.5, 0.52), 0.7))
S.world = bpy.data.worlds.new('Before')
cl.apply(S, 'soft_studio')
sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
S.collection.objects.link(sun)
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(50), 0.0, math.radians(-30))
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
S.collection.objects.link(cam)
S.camera = cam
cam.data.clip_start = 0.01
S.render.engine = 'CYCLES'
S.cycles.samples = 40
S.cycles.use_denoising = True
S.cycles.device = 'CPU'
S.render.image_settings.file_format = 'PNG'
wmat = mat('Wire', (1.0, 0.45, 0.05))
wmat.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (1.0, 0.45, 0.05, 1)
wmat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 1.5
dg = C.evaluated_depsgraph_get()
wires = []
for src in [o for o in S.objects if o.type == 'MESH' and o.visible_get() and o is not floor]:
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
    wires.append((wo, md, max(abs(v) for v in src.matrix_world.to_scale())))


def aim(loc, look, lens):
    cam.location = loc
    cam.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens


def render(name, thick):
    for wire in (False, True):
        for wo, md, sc in wires:
            wo.hide_render = not wire
            md.thickness = thick / max(sc, 1e-9)
        S.render.filepath = os.path.join(OUT, name + ('_wire' if wire else '_shaded') + '.png')
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print('saved', S.render.filepath, f'{time.time() - t0:.0f} s')


S.render.resolution_x, S.render.resolution_y = 1600, 760
aim((1.45, -9.5, 1.0), (1.45, 0.0, -0.25), 42)                   # the fur before / after Alt+X, the hair's bend
render('fur_mirror_bend', 0.004)
S.render.resolution_x, S.render.resolution_y = 1500, 900
aim((1.3, -1.6, 2.9), (1.3, 4.9, -0.4), 36)                       # the vacuum packs
render('vacuum_pack', 0.0025)
