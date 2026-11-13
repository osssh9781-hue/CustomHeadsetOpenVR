"""Greeble / Scale Line stamps demo (0.24.154): parts made from outlines (as Shift + draw makes them - the outlines given
in pixels through a front view), laid along lines on a dark torso: machine stamps (Chamfer L, Bevel hexagon, Dome
capsule) across the chest, creature stamps (a pointed Puff scale, a Ridge leaf) in overlapping rows over the belly; the
stamps themselves standing beside it.  Shaded and with the wireframe.

    <blender python> greeble_stamp_demo.py <out dir>
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Euler, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'addon'))
import mecha_lab  # noqa: E402

OUT = sys.argv[-1]
os.makedirs(OUT, exist_ok=True)
mecha_lab.register()
from mecha_lab import core_geometry as cg, creature_light as cl, geo_sculpt as gs, greeble_line as gl  # noqa: E402

C = bpy.context
S = C.scene
for o in list(S.objects):
    bpy.data.objects.remove(o)

bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=96, ring_count=48, location=(0, 0, 1.3))
body = C.active_object
body.scale = (0.75, 0.48, 1.15)
bpy.ops.object.transform_apply(scale=True)
bpy.ops.object.shade_smooth()


def mat(name, rgb, metal=0.0, rough=0.35):
    m = bpy.data.materials.new(name)
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (*rgb, 1)
    p.inputs['Metallic'].default_value = metal
    p.inputs['Roughness'].default_value = rough
    return m


body.data.materials.append(mat('Dark Skin', (0.025, 0.025, 0.028), rough=0.32))
metal = mat('Dark Metal', (0.07, 0.07, 0.075), metal=0.85, rough=0.3)
scale_m = mat('Scale', (0.16, 0.035, 0.03), rough=0.28)
C.view_layer.objects.active = body
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), center=Vector((0, 0, 1.3)),
                          pixels_per_unit=400.0)                   # (400 px = 1 m)


def px(points, cx=500, cy=500):
    return [[(cx + x, cy + y) for x, y in points]]


def ellipse(rx, ry, n=40, point=0.0):
    out = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        if point > 0 and math.cos(t) > 0:
            x *= 1.0 + point * math.cos(t) ** 4
            y *= 1.0 - 0.6 * math.cos(t) ** 4
        out.append((x, y))
    return out


mech, crea = gl.settings(S, 'MECH'), gl.settings(S, 'CREATURE')
stamps = []
for prof, outline, alone in (('CHAMFER', [(-24, -14), (24, -14), (24, 0), (4, 0), (4, 14), (-24, 14)], True),
                             ('BEVEL', [(18 * math.cos(a), 16 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 7)[:-1]],
                              False),
                             ('DOME', ellipse(26, 9, 32), False)):
    mech.stamp_profile, mech.stamp_alone = prof, alone
    mech.stamp_height = 0.35
    ob, msg = gl.make_stamp(C, px(outline, 500, 560), FRONT, 'MECH')     # (drawn over the chest)
    ob.data.materials.append(metal)
    stamps.append(ob)
    print(msg)
for prof, outline, alone in (('PUFF', ellipse(16, 11, 36, point=0.9), True), ('RIDGE', ellipse(15, 7, 36, point=1.2), False)):
    crea.stamp_profile, crea.stamp_alone = prof, alone
    crea.stamp_height = 0.22
    ob, msg = gl.make_stamp(C, px(outline, 500, 380), FRONT, 'CREATURE')  # (drawn over the belly)
    ob.data.materials.append(scale_m)
    stamps.append(ob)
    print(msg)
for k, v in gl.PRESETS['SCALES'].items():
    setattr(crea, k, v)

caster = gs.SurfaceCaster(C, body)


def surface_line(fn, n=160):
    pts, nrm = [], []
    for t in np.linspace(0.0, 1.0, n):
        hit = caster.nearest(Vector(fn(t)) + Vector((0.0, 0.0, 1.3)))
        if hit is not None:
            pts.append(tuple(hit[0]))
            nrm.append(tuple(hit[1]))
    return np.array(pts), np.array(nrm)


made = []
for k, z in enumerate(np.linspace(0.62, 0.05, 6)):                 # machine ribs across the chest
    half = 1.0 - 0.3 * abs(z - 0.3)
    for kk, v in dict(order='RANDOM', scale=1.0, scale_random=0.15, rows=2, row_gap=0.05, gap=0.08, flip_random=True,
                      turn_random=0.0, seed=k, sink=0.05).items():
        setattr(mech, kk, v)
    p, n = surface_line(lambda t, z=z, h=half: (0.9 * math.sin(-h + 2 * h * t), -0.9 * math.cos(-h + 2 * h * t), z))
    ob = gl.new_line(C, body, p, n, gl.picked(mech), mech)
    gl.rebuild(ob, C, caster)
    made.append(ob)
for k, z in enumerate(np.linspace(-0.12, -0.62, 4)):                # scale rows over the belly
    half = 0.95 - 0.3 * abs(z + 0.3)
    crea.seed = 30 + k
    p, n = surface_line(lambda t, z=z, h=half: (0.9 * math.sin(-h + 2 * h * t), -0.9 * math.cos(-h + 2 * h * t), z))
    ob = gl.new_line(C, body, p, n, gl.picked(crea), crea, 'CREATURE')
    gl.rebuild(ob, C, caster)
    made.append(ob)
print('lines', len(made), 'parts', sum(len(o.data.vertices) for o in made),
      'stamps', [(o.name, o.mch_base.profile, tuple(round(v, 3) for v in o.dimensions)) for o in stamps])

S.world = bpy.data.worlds.new('Before')
cl.apply(S, 'low_key')
cs = cl.settings(S)
cs.fill = 2.0
cs.floor = 'FADE'
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
S.collection.objects.link(cam)
S.camera = cam
cam.data.lens = 50
look = Vector((0.75, 0.0, 1.3))
cam.location = (2.2, -5.4, 1.75)
cam.rotation_euler = (look - cam.location).to_track_quat('-Z', 'Y').to_euler()
S.render.engine = 'CYCLES'
S.cycles.samples = 48
S.cycles.use_denoising = True
S.cycles.device = 'CPU'
S.render.resolution_x, S.render.resolution_y = 1000, 900
S.render.image_settings.file_format = 'PNG'

wmat = bpy.data.materials.new('Wire')
wmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (1.0, 0.45, 0.05, 1)
wmat.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (1.0, 0.45, 0.05, 1)
wmat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 2.0
for src in made:
    gs.set_input(src.modifiers['MCH Greeble'], 'Realize', True)
dg = C.evaluated_depsgraph_get()
dg.update()
wires = []
for src in [body] + made + stamps:
    me = bpy.data.meshes.new_from_object(src.evaluated_get(dg), depsgraph=dg)
    wo = bpy.data.objects.new(src.name + ' wire', me)
    S.collection.objects.link(wo)
    wo.matrix_world = src.matrix_world
    md = wo.modifiers.new('W', 'WIREFRAME')
    md.thickness = 0.0018
    md.use_replace = True
    md.use_even_offset = False
    me.materials.clear()
    me.materials.append(wmat)
    wires.append(wo)
for src in made:
    gs.set_input(src.modifiers['MCH Greeble'], 'Realize', False)
lo = Vector((min(o.matrix_world.translation.x for o in stamps), 0.0, min(o.matrix_world.translation.z for o in stamps)))
hi = Vector((max(o.matrix_world.translation.x for o in stamps), 0.0, max(o.matrix_world.translation.z for o in stamps)))
VIEWS = {   # (name: camera place, where it looks, lens, resolution)
    'lines': ((0.75, -3.0, 1.75), Vector((0.0, -0.35, 1.3)), 60, (1000, 900)),
    'stamps': (((lo + hi) * 0.5 + Vector((0.12, -0.75, 0.25))), (lo + hi) * 0.5 + Vector((0.0, 0.0, 0.0)), 60, (700, 900)),
}
for view, (at, look, lens, res) in VIEWS.items():
    cam.location = at
    cam.data.lens = lens
    cam.rotation_euler = (Vector(look) - Vector(at)).to_track_quat('-Z', 'Y').to_euler()
    S.render.resolution_x, S.render.resolution_y = res
    for name, wire in ((f'stamp_{view}_shaded', False), (f'stamp_{view}_wire', True)):
        for wo in wires:
            wo.hide_render = not wire
        S.render.filepath = os.path.join(OUT, name + '.png')
        bpy.ops.render.render(write_still=True)
        print('saved', S.render.filepath)
