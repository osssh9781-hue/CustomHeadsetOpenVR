"""0.24.173 demo: (1) the kestrel's tail feather (the user's photo) on its own and eleven of it fanned as a tail;
(2) a dragonfly from above - four Insect Wings drawn beside its body (Dragonfly), and the six presets + the four
photo patterns (the user's black-and-white wings) in rows;
(3) a dragon's wing - Creature Cloth drawn over its bones (an arm, three fingers): pinned on them, the rest fallen
(Blender's cloth, pins only), kept with Thickness: Taut Skin + Dragon skin; Hanging Cloth + Bat skin.  Cycles, shaded and with the wireframe.

    <blender python> round173_demo.py <out dir>
"""
import math
import os
import sys
import time

import bpy
import bmesh
import numpy as np
from mathutils import Euler, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'addon'))
import mecha_lab  # noqa: E402

OUT = sys.argv[-1]
os.makedirs(OUT, exist_ok=True)
mecha_lab.register()
from mecha_lab import (cloth_drape as cd, core_geometry as cg, creature_light as cl, creature_membrane as cm,  # noqa
                       creature_shapes as cs, greeble_line as gl, insect_wing as iw)

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


TOP = cg.OrthoProjector(Euler((0, 0, 0)).to_quaternion(), pixels_per_unit=200.0)          # (looking down -Z)
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)

# ---- (1) the kestrel's tail -------------------------------------------------------------------------------------------
K0 = Vector((15.0, 0.0, -20.0))             # (beside, not under the dragonfly: its wings are drawn from above)
fm = dict((me['mch_shape_id'], (n, me)) for n, me in cs.feather_meshes())
n_, me_ = fm['KESTREL']
kf = bpy.data.objects.new('Kestrel Tail (single)', me_)
S.collection.objects.link(kf)
L = cs.FEATHER_LENGTHS['KESTREL']
kf.scale = (L, L, L)
kf.rotation_euler = (0, 0, math.radians(90))
kf.location = K0 + Vector((-1.25, -0.8, 0.0))
for i in range(11):                                     # (a fanned tail of them: as on the bird)
    a = math.radians(-36 + 72 * i / 10)
    o = bpy.data.objects.new(f'Kestrel Tail {i}', me_)
    S.collection.objects.link(o)
    o.scale = (L, L, L)
    o.rotation_euler = (0.0, 0.0, a)
    o.location = K0 + Vector((-0.75, 0.0, 0.004 * abs(i - 5)))
bpy.ops.mesh.primitive_plane_add(size=8.0, location=K0 + Vector((0.0, 0.0, -0.06)))
board = C.active_object
board.data.materials.append(mat('Board', (0.06, 0.06, 0.065), 0.8))

# ---- (2) a dragonfly ------------------------------------------------------------------------------------------------
D0 = Vector((0.0, 0.0, -10.0))
body_m = mat('Dragonfly Body', (0.02, 0.08, 0.12), 0.25)
parts = []
for loc, sc in (((0.0, 0.55, 0.0), (0.14, 0.16, 0.12)), ((0.0, 0.3, 0.0), (0.12, 0.2, 0.11)),
                ((0.0, -0.55, 0.0), (0.045, 0.75, 0.045))):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=48, ring_count=24, location=D0 + Vector(loc))
    o = C.active_object
    o.scale = sc
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.shade_smooth()
    o.data.materials.append(body_m)
    parts.append(o)
thorax = parts[1]
S.cursor.location = D0
S.mch_wing.preset = 'DRAGONFLY'


def wing_outline(root, tip, width, bulge=0.7, n=60, side=1):
    """A dragonfly wing (top view): a straight leading edge, a bulging trailing edge; drawn from the root."""
    root, tip = np.array(root, float), np.array(tip, float)
    ax = tip - root
    L_ = np.linalg.norm(ax)
    ax /= L_
    pp = np.array([-ax[1], ax[0]]) * side
    pts_ = [root + ax * L_ * t + pp * 0.02 * L_ * math.sin(math.pi * t) for t in np.linspace(0, 1, n)]
    pts_ += [root + ax * L_ * t - pp * width * math.sin(math.pi * t) ** bulge * (1 - 0.2 * t)
             for t in np.linspace(1, 0, n)[1:-1]]
    return [[TOP.to_screen(Vector((x, y, D0.z))) for x, y in pts_]]


wings = []
for side in (1, -1):
    for k, (y0, ang, w_) in enumerate(((0.38, 8, 0.2), (0.24, -12, 0.25))):
        a = math.radians(ang)
        root = (0.1 * side, y0)
        tip = (side * (0.1 + 1.25 * math.cos(a)), y0 + 1.25 * math.sin(a))
        S.mch_wing.bend, S.mch_wing.twist = math.radians(14), math.radians(-12 * side)     # (from the root)
        msg = iw.perform(C, wing_outline(root, tip, w_, side=-side if k == 0 else -side), TOP)
        wings.append(C.active_object)
        print(msg)
for w in wings:
    iw.apply_wing(w)
# the six presets in a row
R0 = Vector((0.0, -1.6, -10.0))
ALL = [p[0] for p in iw.PRESETS] + [p[0] for p in iw.wp.PHOTOS]
S.mch_wing.bend = S.mch_wing.twist = 0.0
for k, pid in enumerate(ALL):
    S.mch_wing.preset = pid
    x0 = -3.0 + (k % 4) * 1.55
    y0 = R0.y - (k // 4) * 0.45
    msg = iw.perform(C, [[TOP.to_screen(Vector((x, y, D0.z))) for x, y in
                          [(x0 + 1.4 * t, y0 + 0.01 * math.sin(math.pi * t)) for t in np.linspace(0, 1, 40)] +
                          [(x0 + 1.4 * t, y0 - 0.3 * math.sin(math.pi * t) ** 0.7) for t in np.linspace(1, 0, 40)[1:-1]]]],
                     TOP)
    iw.apply_wing(C.active_object)
    print(pid, msg)
bpy.ops.mesh.primitive_plane_add(size=12.0, location=D0 + Vector((0, -1.0, -0.12)))
board2 = C.active_object
board2.data.materials.append(mat('Board 2', (0.55, 0.56, 0.5), 0.8))

# ---- (3) a dragon's wing: Creature Cloth over the bones -------------------------------------------------------------
M0 = Vector((0.0, 0.0, 0.0))


def bones_mesh(name, origin):
    bm = bmesh.new()
    for a_, b_, rr in (((0, 0, 1.0), (1.4, 0, 1.2), 0.07), ((1.4, 0, 1.2), (2.6, 0, 0.3), 0.045),
                       ((1.4, 0, 1.2), (2.0, 0, -0.35), 0.045), ((1.4, 0, 1.2), (1.2, 0, -0.55), 0.045)):
        A, B = Vector(a_), Vector(b_)
        m = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=rr, radius2=rr * 0.55, depth=(B - A).length)
        bmesh.ops.rotate(bm, verts=m['verts'], cent=(0, 0, 0), matrix=(B - A).to_track_quat('Z', 'Y').to_matrix())
        bmesh.ops.translate(bm, verts=m['verts'], vec=(A + B) / 2)
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=rr * 1.25,
                                  matrix=__import__('mathutils').Matrix.Translation(B))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    S.collection.objects.link(ob)
    ob.location = origin
    ob.data.materials.append(mat(name + ' bone', (0.35, 0.3, 0.25), 0.5))
    return ob


membranes = []
for k, (preset, style, x_off) in enumerate((('DRAGON', 'TAUT', 0.0), ('BAT', 'CLOTH', 3.6))):
    bones = bones_mesh(f'{preset.title()} Wing Bones', Vector((x_off, 0.0, 0.0)))
    C.view_layer.update()
    outline = [(0.05, 1.0), (0.7, 1.1), (1.4, 1.2), (2.0, 0.75), (2.6, 0.3), (2.3, 0.05), (2.0, -0.35), (1.65, -0.35),
               (1.2, -0.55), (0.8, -0.3), (0.3, 0.2), (0.05, 0.55)]
    ring = []
    for i in range(len(outline)):
        x0, z0 = outline[i]
        x1, z1 = outline[(i + 1) % len(outline)]
        for j in range(8):
            ring.append((x_off + x0 + (x1 - x0) * j / 8, -3.0, z0 + (z1 - z0) * j / 8))
    S.mch_membrane.style = style                       # (Taut Skin / Hanging Cloth)
    S.mch_membrane.preset = preset
    S.mch_membrane.detail = 70
    print(cm.perform(C, [[FRONT.to_screen(Vector(p)) for p in ring]], FRONT))
    mem = C.active_object
    # (turned a little toward the camera after it is drawn: a wing half open - its bones and it together)
    while cd.step(C):
        pass
    print(cd.confirm(C))
    membranes.append((bones, mem))
for bones, _m in membranes:
    bones.rotation_euler = (0.0, 0.0, math.radians(-25))
bpy.ops.mesh.primitive_plane_add(size=30.0, location=(2.0, 0.0, -1.2))
floor = C.active_object
floor.data.materials.append(mat('Floor', (0.45, 0.45, 0.47), 0.8))
for c_ in ('Feather Parts', 'MCH Cover Feathers'):
    if bpy.data.collections.get(c_):
        bpy.data.collections[c_].hide_render = True

# ---- scene ---------------------------------------------------------------------------------------------------------
S.world = bpy.data.worlds.new('Before')
cl.apply(S, 'soft_studio')
sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
S.collection.objects.link(sun)
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(40), 0.0, math.radians(-30))
back = bpy.data.objects.new('Back', bpy.data.lights.new('Back', 'SUN'))
S.collection.objects.link(back)
back.data.energy = 4.0
back.rotation_euler = (math.radians(-70), 0.0, math.radians(160))
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
BOARDS = {board, board2, floor}
SOURCES = [o for o in S.objects if o.type == 'MESH' and o.visible_get() and not o.hide_render
           and not any(c.hide_render for c in o.users_collection)]


def group_of(o):
    z = o.matrix_world.translation.z
    return 'kestrel' if z < -15 else 'insect' if z < -5 else 'membrane'


def make_wires(group):
    dg = C.evaluated_depsgraph_get()
    out = []
    for src in SOURCES:
        if src in BOARDS or group_of(src) != group:
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
    for o in SOURCES:
        o.hide_render = (group_of(o) != group) if o not in BOARDS else (group_of(o) != group)
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
if ONLY in ('', 'kestrel'):
    S.render.resolution_x, S.render.resolution_y = 1400, 760
    aim(K0 + Vector((-0.1, 0.0, 6.0)), K0 + Vector((-0.1, 0.0, 0.0)), 50, ortho=3.3)
    render('kestrel_tail', 0.0012, 'kestrel')
if ONLY in ('', 'insect'):
    S.render.resolution_x, S.render.resolution_y = 1400, 1100
    aim(D0 + Vector((0.0, -1.05, 8.0)), D0 + Vector((0.0, -1.05, 0.0)), 50, ortho=6.6)
    render('insect_wings', 0.0012, 'insect')
if ONLY in ('', 'membrane'):
    S.render.resolution_x, S.render.resolution_y = 1500, 800
    aim((2.4, -7.5, 1.6), (2.6, 0.0, 0.35), 40)
    render('dragon_membrane', 0.002, 'membrane')
