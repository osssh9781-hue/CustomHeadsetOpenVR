"""0.24.171 demo: (1) a Fur drawn on the right of a head and bent toward the screen's left (Bend), applied; the same
turned over with Flip (the world's X plane: now on the left - the fur itself, no copy); the same mirrored with Alt+X's
mirror (hair curves now take it) - both sides; Creature Hair bent toward the view's right; (2) Vacuum Pack - Blender's
cloth sucked onto the selected parts: a head (Suzanne on a neck) in a cloth, five parts in clear plastic.  Cycles,
shaded and with the wireframe.

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
import mecha_lab  # noqa: E402

OUT = sys.argv[-1]
os.makedirs(OUT, exist_ok=True)
mecha_lab.register()
from mecha_lab import (actions_menu as am, cloth_drape as cd, core_geometry as cg, creature_fur as cf,  # noqa: E402
                       creature_hair as ch, creature_light as cl, mirror_tools as mt, vacuum_pack as vpk)

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
groups = {'fur': [], 'vac': []}
PART = os.environ.get('DEMO_PART', 'all')            # (all / vac: the vacuum packs only)
# ---- (1) Fur: one side + Bend; Flip; Alt+X mirror -------------------------------------------------------------
def fur_part():
    st = S.mch_fur
    st.density, st.length, st.gravity, st.lie, st.frizz, st.clump, st.spread = 9000.0, 0.75, 2.2, 0.4, 0.05, 0.35, 0.15
    st.root_thick, st.tip_thick, st.use_polypaint = 0.006, 0.0015, False
    st.root_color, st.tip_color, st.tip_blend = (0.03, 0.025, 0.02, 1), (0.5, 0.42, 0.33, 1), 0.5
    st.bend = 0.0
    furs = []
    for k in range(3):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=96, ring_count=48, location=(0.0, 0.0, 0.0))
        h = C.active_object
        h.name = ('Head original', 'Head flipped', 'Head mirrored')[k]
        bpy.ops.object.shade_smooth()
        h.data.materials.append(skin)
        FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)
        loop = [[FRONT.to_screen(Vector((0.5 + 0.22 * math.cos(t), -2.0, 0.35 + 0.35 * math.sin(t))))
                 for t in np.linspace(0, 2 * math.pi, 48, endpoint=False)]]
        select(h)
        print(cf.perform(C, loop, FRONT))
        fur = C.active_object
        fur.mch_fur.bend_dir = (-1.0, 0.0, 0.0)                        # (Bend "Left" from the front view)
        fur.mch_fur.bend_at, fur.mch_fur.bend = 0.45, math.radians(55)
        cf.apply_fur(C, fur)                                            # (the user's case: an applied fur)
        if k == 1:
            print('Flip:', am.flip_objects(C, [fur], 0), 'object(s)')    # (the world's X plane: right -> left)
        if k == 2:
            mt.setup_curves_mirror(fur, S.mch_mirror, S, axes=(True, False, False))
            lg = mt.MirrorLeanLogic()
            lg.p, lg.target_names, lg.axes, lg.flips, lg.pivot_name = S.mch_mirror, [fur.name], [True, False, False], [False] * 3, None
            print(lg.finish_apply(C))
        furs.append((h, fur))
    # (moved apart after: the flip / mirror used the world's plane through the origin)
    for k, (h, fur) in enumerate(furs):
        h.location.x += (k - 1.5) * 2.7
        fur.parent = h                                                  # (the fur stays on its head)
        groups['fur'] += [h, fur]
    C.view_layer.update()
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=96, ring_count=48, location=(0.0, 0.0, 0.0))
    h4 = C.active_object
    h4.name = 'Head hair bend'
    bpy.ops.object.shade_smooth()
    h4.data.materials.append(skin)
    S.mch_hair.style, S.mch_hair.count, S.mch_hair.colour_mode = 'STRAIGHT', 220, 'OWN'
    _k, _l, root, tip = next(c for c in ch.COLOUR_PRESETS if c[0] == 'AUBURN')
    S.mch_hair.root_colour, S.mch_hair.tip_colour, S.mch_hair.bend = root, tip, 0.0
    select(h4)
    print(ch.perform(C, [[FRONT.to_screen(Vector((0.55 * math.cos(t), -2.0, 0.55 + 0.3 * math.sin(t))))
                          for t in np.linspace(0, 2 * math.pi, 48, endpoint=False)]], FRONT))
    hair = C.active_object
    hair.mch_hair.bend_dir = (1.0, 0.0, 0.0)                            # (Bend "Right" from the front view)
    hair.mch_hair.bend_at, hair.mch_hair.bend_soft, hair.mch_hair.bend = 0.45, 0.35, math.radians(70)
    ch.apply(hair)
    hair.parent = h4
    h4.location.x = 1.5 * 2.7
    groups['fur'] += [h4, hair]
    C.view_layer.update()


if PART == 'all':
    fur_part()
# ---- (2) Vacuum Pack ----------------------------------------------------------------------------------------------
vs = S.mch_vacuum
cdst = cd.settings(C)
cdst.thickness = 0.0
base = Vector((-2.2, 9.0, 0.0))
bpy.ops.mesh.primitive_monkey_add(size=1.0, location=base + Vector((0, 0, 0.5)))
mk = C.active_object
mk.modifiers.new('S', 'SUBSURF').levels = 2
bpy.ops.object.shade_smooth()
mk.data.materials.append(skin)
bpy.ops.mesh.primitive_cylinder_add(radius=0.18, depth=1.0, location=base + Vector((0, 0.08, -0.35)))
neck = C.active_object
neck.data.materials.append(skin)
select(mk, neck)
vs.points, vs.frames, vs.film, vs.gather = 9000, 60, 'CLOTH', 'NONE'
t0 = time.time()
print(vpk.perform(C))
while cd.step(C):
    pass
print(cd.confirm(C), f'{time.time() - t0:.0f} s')
head_film = bpy.data.objects.get('Vacuum Pack')
head_film.name = 'Vacuum Cloth Head'
groups['vac'] += [mk, neck, head_film]
parts = []
base2 = Vector((2.0, 9.0, -0.85))
for maker, kw, rgb in ((bpy.ops.mesh.primitive_uv_sphere_add, dict(radius=0.45, segments=48, ring_count=24, location=(-0.55, 0, 0.45)), (0.6, 0.08, 0.05)),
                       (bpy.ops.mesh.primitive_torus_add, dict(major_radius=0.35, minor_radius=0.12, location=(0.35, 0.1, 0.13)), (0.7, 0.55, 0.08)),
                       (bpy.ops.mesh.primitive_cone_add, dict(radius1=0.25, depth=0.7, location=(0.25, -0.35, 0.35)), (0.08, 0.2, 0.6)),
                       (bpy.ops.mesh.primitive_cube_add, dict(size=0.4, location=(-0.1, 0.45, 0.2)), (0.1, 0.45, 0.12)),
                       (bpy.ops.mesh.primitive_cylinder_add, dict(radius=0.12, depth=0.9, location=(0.65, 0.45, 0.45), rotation=(0.4, 0.3, 0)), (0.4, 0.4, 0.42))):
    kw['location'] = tuple(Vector(kw['location']) + base2)
    maker(**kw)
    o = C.active_object
    o.data.materials.append(mat('Part', rgb, 0.45))
    parts.append(o)
select(*parts)
vs.points, vs.frames, vs.film, vs.bag = 9000, 60, 'CLEAR', 0.7
t0 = time.time()
print(vpk.perform(C))
while cd.step(C):
    pass
print(cd.confirm(C), f'{time.time() - t0:.0f} s')
groups['vac'] += parts + [bpy.data.objects.get('Vacuum Pack')]

# ---- scene -----------------------------------------------------------------------------------------------------------
bpy.ops.mesh.primitive_plane_add(size=60.0, location=(0, 0, -1.0))
floor = C.active_object
floor.data.materials.append(mat('Floor', (0.5, 0.5, 0.52), 0.7))
S.world = bpy.data.worlds.new('Before')
cl.apply(S, 'soft_studio')
sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
S.collection.objects.link(sun)
sun.data.energy = 3.5
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


if PART == 'all':
    S.render.resolution_x, S.render.resolution_y = 1800, 640
    aim((0.0, -11.5, 0.9), (0.0, 0.0, -0.15), 40)                  # the fur: original / flipped / mirrored, the hair
    render('fur_flip_mirror_bend', 0.004)
S.render.resolution_x, S.render.resolution_y = 1100, 1000
aim((-1.2, 5.0, 0.9), (-2.2, 9.0, 0.0), 45)                        # the head in a cloth
render('vacuum_cloth_head', 0.003)
S.render.resolution_x, S.render.resolution_y = 1200, 900
aim((3.6, 6.4, 1.3), (2.0, 9.0, -0.6), 45)                         # five parts in clear plastic
render('vacuum_plastic', 0.003)
