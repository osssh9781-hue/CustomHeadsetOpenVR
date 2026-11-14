"""0.24.172 demo: (1) the 15 feathers and the 8 real scales side by side (top view); (2) a bird-like body - the Fur
tool's Feathers tab on its back and side (Contour feathers lying toward the tail), Feather Lines along its side
(Primary, Longer to End) and across its tail (Tail feathers, Longer at Start and Length Random); (3) a creature limb
- the Fur tool's Scales tab: Keeled scales on top, Dragon scales on a patch, Belly Scutes underneath.  All applied
(Enter), Cycles, shaded and with the wireframe.

    <blender python> round172_demo.py <out dir>
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
from mecha_lab import (core_geometry as cg, creature_fur as cf, creature_light as cl, creature_shapes as cs,  # noqa
                       greeble_line as gl, skin_cover as sc)

C = bpy.context
S = C.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
FAST = os.environ.get('DEMO_FAST') == '1'


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
    C.view_layer.objects.active = obs[0] if obs else None


def label(text, loc, size=0.12):
    cu = bpy.data.curves.new(text, 'FONT')
    cu.body = text
    cu.size = size
    cu.align_x = 'CENTER'
    ob = bpy.data.objects.new('Label ' + text, cu)
    S.collection.objects.link(ob)
    ob.location = loc
    ob.data.materials.append(LABEL)
    return ob


LABEL = mat('Label', (0.05, 0.05, 0.05), 0.6)
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)


def ring(cx, cz, rx, rz, y=-5.0, n=64):
    return [[FRONT.to_screen(Vector((cx + rx * math.cos(t), y, cz + rz * math.sin(t))))
             for t in np.linspace(0, 2 * math.pi, n, endpoint=False)]]


# ---- (1) the shapes board ---------------------------------------------------------------------------------------------
BOARD = Vector((0.0, 0.0, -30.0))
x = 0.0
for k, (name, me) in enumerate(cs.feather_meshes()):
    sid = me['mch_shape_id']
    ob = bpy.data.objects.new(name, me)
    S.collection.objects.link(ob)
    L = cs.FEATHER_LENGTHS.get(sid, 1.0)
    ob.rotation_euler = (0.0, 0.0, math.radians(90))            # (quill at the bottom, tip up the board)
    ob.scale = (L, L, L)
    ob.location = BOARD + Vector((k * 0.42 - 2.94, -1.2, 0.0))
    label(name.replace('Feather ', ''), BOARD + Vector((k * 0.42 - 2.94, -1.42, -0.115)), 0.07)
for k, (name, me) in enumerate(cs.scale_meshes_real()):
    ob = bpy.data.objects.new(name, me)
    S.collection.objects.link(ob)
    ob.rotation_euler = (0.0, 0.0, math.radians(90))
    ob.scale = (0.55, 0.55, 0.55)
    ob.location = BOARD + Vector((k * 0.8 - 2.8, -2.35, 0.0))
    label(name.replace('Scale ', ''), BOARD + Vector((k * 0.8 - 2.8, -2.6, -0.115)), 0.08)
bpy.ops.mesh.primitive_plane_add(size=9.0, location=BOARD + Vector((0, -1.3, -0.12)))
board = C.active_object
board.data.materials.append(mat('Board', (0.75, 0.74, 0.72), 0.8))

# ---- (2) a bird-like body ----------------------------------------------------------------------------------------------
skin = mat('Bird Skin', (0.25, 0.2, 0.17), 0.6)
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=128, ring_count=64, location=(0.0, 0.0, 0.0))
bird = C.active_object
bird.name = 'Bird'
bird.scale = (1.5, 0.8, 0.85)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
bpy.ops.object.shade_smooth()
bird.data.materials.append(skin)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, segments=64, ring_count=32, location=(-1.65, 0.0, 0.55))
head = C.active_object
head.name = 'Bird Head'
bpy.ops.object.shade_smooth()
head.data.materials.append(skin)
bpy.ops.mesh.primitive_cone_add(radius1=0.14, depth=0.42, location=(-2.25, 0.0, 0.5), rotation=(0, math.radians(-90), 0))
beak = C.active_object
beak.data.materials.append(mat('Beak', (0.75, 0.55, 0.12), 0.4))


def cover(grow, shapes, area, **kw):
    st = S.mch_cover
    st.grow = grow
    for k_, v in kw.items():
        setattr(st, k_, v)
    st.shapes_json = '["' + '","'.join(shapes) + '"]'
    setattr(C.window_manager, cf.NEW_KEY, True)
    select()
    print(cf.perform(C, area, FRONT))
    return C.active_object


def lie_to(ob, toward):
    """Flow Angle so the free ends point ``toward`` (world) on average."""
    best = None
    for ang in (0, 90, -90, 180):
        ob.mch_cover.flow = math.radians(ang)
        q = np.empty(len(ob.data.vertices) * 4, np.float32)
        ob.data.attributes['mch_rot'].data.foreach_get('value', q)
        from mathutils import Quaternion
        d = np.mean([np.array(Quaternion(qq) @ Vector((1, 0, 0))) for qq in q.reshape(-1, 4)], axis=0) @ np.array(toward)
        if best is None or d > best[0]:
            best = (d, ang)
    ob.mch_cover.flow = math.radians(best[1])
    return best[1]


back = cover('FEATHERS', ['CONTOUR', 'COVERT'], ring(-0.05, 0.2, 1.38, 0.68), size=5.0, spacing=0.25, side_spacing=0.6,
             lift=math.radians(5), size_random=0.2, turn_random=math.radians(8))
print('back feathers flow', lie_to(back, (1.0, 0.0, -0.25)))
neck = cover('FEATHERS', ['DOWN', 'CONTOUR'], ring(-1.6, 0.5, 0.45, 0.43), size=8.0, spacing=0.25, side_spacing=0.6,
             lift=math.radians(5))
print('head feathers flow', lie_to(neck, (1.0, 0.0, -0.3)))
# a raised wing: an arm from the shoulder up and back, feathers along it (Primary: Longer to End)
sh, tip = Vector((-0.45, -0.55, 0.55)), Vector((0.55, -0.62, 2.05))
axis = (tip - sh).normalized()
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=48, ring_count=24, location=(sh + tip) / 2)
arm = C.active_object
arm.name = 'Wing Arm'
arm.scale = ((tip - sh).length / 2, 0.11, 0.08)
arm.rotation_euler = (0.0, -math.atan2(axis.z, axis.x), 0.0)
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
bpy.ops.object.shade_smooth()
arm.data.materials.append(skin)


def feather_line(fid, target, pts, nrm, **kw):
    st = gl.settings(S, 'FEATHER')
    select(target)
    bpy.ops.mch.feather_pick(feather=fid)
    for k_, v in kw.items():
        setattr(st, k_, v)
    loc = [tuple(target.matrix_world.inverted() @ Vector(p_)) for p_ in pts]
    ln = gl.new_line(C, target, loc, nrm, gl.picked(st), st, 'FEATHER')
    print(fid, 'line:', gl.rebuild(ln, C), 'feathers')
    return ln


pts = [sh + (tip - sh) * (0.06 + 0.92 * i / 19) + Vector((0.0, -0.1, 0.0)) for i in range(20)]
nrm = [(0.0, -1.0, 0.0)] * len(pts)
TURN = float(os.environ.get('DEMO_TURN', '-75'))
prim = feather_line('PRIMARY', arm, pts, nrm, length=3.2, width=3.2, grow_end=1.6, grow_start=0.0, length_random=0.1,
                    scale=1.0, gap=-0.75, turn=math.radians(TURN), tilt=math.radians(-4), rows=1)
cov_ = feather_line('COVERT', arm, [p_ + Vector((0.0, -0.012, 0.0)) for p_ in pts], nrm, length=1.4, width=1.3,
                    grow_end=0.5, grow_start=0.0, length_random=0.1, scale=1.0, gap=-0.5, turn=math.radians(TURN),
                    tilt=math.radians(-4), rows=1)
# the tail: a line across the back end, Tail feathers (a little random in length)
tpts, tn = [], []
for i in range(13):
    yy = -0.36 + 0.06 * i
    xx = 1.18
    zz = 0.85 * math.sqrt(max(0.0, 1 - (xx / 1.5) ** 2 - (yy / 0.8) ** 2))
    tpts.append((xx, yy, zz))
    tn.append(tuple((Vector((xx / 1.5 ** 2, yy / 0.8 ** 2, zz / 0.85 ** 2))).normalized()))
tail = feather_line('TAIL', bird, tpts, tn, length=4.0, width=2.0, grow_end=0.0, grow_start=0.0, length_random=0.2,
                    scale=1.0, gap=-0.5, turn=math.radians(-90), tilt=math.radians(-40), rows=1)

from mathutils import Quaternion  # noqa: E402
for ln_ in (prim, tail):
    q_ = np.empty(len(ln_.data.vertices) * 4, np.float32)
    ln_.data.attributes['mch_rot'].data.foreach_get('value', q_)
    co_ = np.empty(len(ln_.data.vertices) * 3, np.float32)
    ln_.data.vertices.foreach_get('co', co_)
    ax = np.mean([np.array(ln_.matrix_world.to_3x3() @ (Quaternion(qq) @ Vector((1, 0, 0)))) for qq in q_.reshape(-1, 4)], 0)
    print('DIR', ln_.name, 'long axis', np.round(ax, 2), 'at', np.round((np.array(ln_.matrix_world) @ np.r_[co_.reshape(-1, 3).mean(0), 1])[:3], 2))
# ---- (3) a creature limb with scales -----------------------------------------------------------------------------------
LIMB = Vector((0.0, 0.0, -12.0))
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=128, ring_count=64, location=LIMB)
limb = C.active_object
limb.name = 'Limb'
limb.scale = (2.4, 0.75, 0.75)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
bpy.ops.object.shade_smooth()
limb.data.materials.append(mat('Limb Skin', (0.18, 0.2, 0.12), 0.5))
keel = cover('SCALES', ['KEELED'], ring(-0.4, LIMB.z + 0.2, 1.9, 0.5), size=2.4, spacing=0.42, side_spacing=0.55, lift=math.radians(9))
print('keeled flow', lie_to(keel, (1.0, 0.0, 0.0)))
drag_ = cover('SCALES', ['DRAGON'], ring(1.35, LIMB.z + 0.1, 0.55, 0.45), size=2.6, spacing=0.45, side_spacing=0.6, lift=math.radians(12))
print('dragon flow', lie_to(drag_, (1.0, 0.0, 0.0)))
belly = cover('SCALES', ['VENTRAL'], ring(-0.2, LIMB.z - 0.48, 1.8, 0.2), size=3.0, spacing=0.4, side_spacing=0.7, lift=math.radians(4),
              size_random=0.05)
print('belly flow', lie_to(belly, (1.0, 0.0, 0.0)))

# ---- Enter: all applied ------------------------------------------------------------------------------------------------
for ob in [o for o in S.objects if sc.is_cover(o)]:
    sc.apply_cover(C, ob)
for ob in [o for o in S.objects if gl.is_line(o)]:
    gl.apply_line(C, ob)
for c_ in ('MCH Cover Feathers', 'MCH Cover Scales', 'Feather Parts'):
    if bpy.data.collections.get(c_):
        bpy.data.collections[c_].hide_render = True
for o in list(S.objects):
    if o.type == 'MESH' and gl.STAMP_TAG in o.keys():
        o.hide_render = True
print('faces:', {o.name: len(o.data.polygons) for o in S.objects if o.type == 'MESH' and o.name.startswith(('Feathers', 'Scales'))})

# ---- scene -------------------------------------------------------------------------------------------------------------
S.world = bpy.data.worlds.new('Before')
cl.apply(S, 'soft_studio')
sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
S.collection.objects.link(sun)
sun.data.energy = 3.5
sun.rotation_euler = (math.radians(45), 0.0, math.radians(-35))
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
S.collection.objects.link(cam)
S.camera = cam
cam.data.clip_start = 0.01
S.render.engine = 'CYCLES'
S.cycles.samples = 12 if FAST else 40
S.cycles.use_denoising = True
S.cycles.device = 'CPU'
S.render.image_settings.file_format = 'PNG'
wmat = mat('Wire', (1.0, 0.45, 0.05))
wmat.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (1.0, 0.45, 0.05, 1)
wmat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 1.5
SOURCES = [o for o in S.objects if o.type == 'MESH' and o.visible_get() and not o.hide_render
           and not any(c.hide_render for c in o.users_collection)]


def group_of(o):
    z = o.matrix_world.translation.z
    return 'board' if z < -20 else 'limb' if z < -5 else 'bird'


def make_wires(group):
    """The wireframe copies of one group's meshes (only that group: the others' would fill the memory)."""
    dg = C.evaluated_depsgraph_get()
    out = []
    for src in SOURCES:
        if src is board or group_of(src) != group:
            continue
        me = bpy.data.meshes.new_from_object(src.evaluated_get(dg), depsgraph=dg)
        wo = bpy.data.objects.new(src.name + ' wire', me)
        S.collection.objects.link(wo)
        wo.matrix_world = src.matrix_world
        md = wo.modifiers.new('W', 'WIREFRAME')
        md.use_replace = True
        md.use_even_offset = False
        me.materials.clear()
        me.materials.append(wmat)
        out.append((wo, md, max(abs(v) for v in src.matrix_world.to_scale())))
    return out


def aim(loc, look, lens, ortho=None):
    cam.location = loc
    cam.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens
    cam.data.type = 'ORTHO' if ortho else 'PERSP'
    if ortho:
        cam.data.ortho_scale = ortho


def render(name, thick, group):
    for o in SOURCES:                                  # (only this group's objects: less memory)
        o.hide_render = group_of(o) != group and o is not board or (o is board and group != 'board')
    print(group, 'shown:', [(o.name, round(o.matrix_world.translation.z, 1)) for o in SOURCES if not o.hide_render])
    for wire in (False, True):
        wires = make_wires(group) if wire else []
        for wo, md, sc_ in wires:
            md.thickness = thick / max(sc_, 1e-9)
        S.render.filepath = os.path.join(OUT, name + ('_wire' if wire else '_shaded') + '.png')
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print('saved', S.render.filepath, f'{time.time() - t0:.0f} s')
        for wo, _md, _s in wires:
            me = wo.data
            bpy.data.objects.remove(wo)
            bpy.data.meshes.remove(me)


ONLY = os.environ.get('DEMO_ONLY', '')
if ONLY in ('', 'board'):
    S.render.resolution_x, S.render.resolution_y = 1600, 760
    aim(BOARD + Vector((0.0, -1.35, 8.0)), BOARD + Vector((0.0, -1.35, 0.0)), 50, ortho=6.6)
    render('shapes_board', 0.0025, 'board')
if ONLY in ('', 'bird'):
    S.render.resolution_x, S.render.resolution_y = 1400, 900
    aim((-0.6, -7.4, 1.9), (0.15, 0.0, 0.75), 40)
    render('bird_feathers', 0.0018, 'bird')
if ONLY in ('', 'limb'):
    S.render.resolution_x, S.render.resolution_y = 1400, 760
    aim((0.6, -5.6, LIMB.z + 1.2), (0.2, 0.0, LIMB.z), 45)
    render('limb_scales', 0.0015, 'limb')
