"""0.24.174 demo (Cycles, shaded and with the wireframe):
(1) Thinner at Edge - the Fur tool's scales and feathers on four bodies: off (left of each pair), on (right of it);
(2) Scale Line with the Fur tool's real scales - Dragon (Taper End), Pangolin (Taper Start + End), Osteoderm (none);
(3) Insect Wing veins on curved / fan / lobed outlines - before (the straight root-tip frame, top) and now (bottom);
(4) Weathering drawn like Armor Plate - Dirt, Dust, Leaves, Snow areas drawn on a ground (and over a rock);
(5) Creature Cloth drawn with Surface on four separate bone meshes (not joined), fallen, kept with Thickness.

    <blender python> round174_demo.py <out dir>         (DEMO_ONLY=edge|scale|wing|weather|membrane, DEMO_FAST=1)
"""
import math
import os
import sys
import time
import types

import bpy
import bmesh
import numpy as np
from mathutils import Euler, Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'addon'))
import mecha_lab  # noqa: E402

OUT = sys.argv[-1]
os.makedirs(OUT, exist_ok=True)
mecha_lab.register()
from mecha_lab import (cloth_drape as cd, core_geometry as cg, creature_fur as cf, creature_light as cl,  # noqa: E402
                       creature_membrane as cm, greeble_line as gl, insect_wing as iw, skin_cover as sc,
                       surface_lasso as sl, weathering as wt)

C = bpy.context
S = C.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
FAST = os.environ.get('DEMO_FAST') == '1'
ONLY = os.environ.get('DEMO_ONLY', '')
TOP = cg.OrthoProjector(Euler((0, 0, 0)).to_quaternion(), pixels_per_unit=200.0)          # (looking down -Z)
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)


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


def tag(group):
    for o in S.objects:
        if 'demo' not in o.keys():
            o['demo'] = group


def ring(cx, cz, rx, rz, y=-5.0, n=64):
    return [[FRONT.to_screen(Vector((cx + rx * math.cos(t), y, cz + rz * math.sin(t))))
             for t in np.linspace(0, 2 * math.pi, n, endpoint=False)]]


def body(name, loc, scale, rgb, seg=96):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=seg, ring_count=seg // 2, location=loc)
    ob = C.active_object
    ob.name = name
    ob.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.shade_smooth()
    ob.data.materials.append(mat(name + ' Skin', rgb, 0.5))
    return ob


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


# ---- (1) Thinner at Edge -------------------------------------------------------------------------------------------
if ONLY in ('', 'edge'):
    for k, (grow, shape, x, thin, rgb) in enumerate((('SCALES', 'CYCLOID', -3.4, False, (0.16, 0.2, 0.12)),
                                                      ('SCALES', 'CYCLOID', -1.1, True, (0.16, 0.2, 0.12)),
                                                      ('FEATHERS', 'CONTOUR', 1.1, False, (0.4, 0.3, 0.2)),
                                                      ('FEATHERS', 'CONTOUR', 3.4, True, (0.4, 0.3, 0.2)))):
        b = body(f'Body {k + 1}', (x, 0.0, 0.0), (1.0, 1.0, 1.0), rgb)
        C.view_layer.update()
        if grow == 'SCALES':
            ob = cover(grow, [shape], ring(x, 0.05, 0.78, 0.78), size=2.4, spacing=0.42, side_spacing=0.55,
                       lift=math.radians(9))
        else:
            ob = cover(grow, [shape], ring(x, 0.05, 0.78, 0.78), size=4.0, spacing=0.3, side_spacing=0.6,
                       lift=math.radians(5), size_random=0.15)
        ob.mch_cover.edge_thin = thin
        print('edge', ob.name, 'thin', thin, len(ob.data.vertices))
        sc.apply_cover(C, ob)
    tag('edge')

# ---- (2) Scale Line: the Fur tool's scales, Taper ------------------------------------------------------------------
if ONLY in ('', 'scale'):
    B0 = Vector((0.0, 0.0, -10.0))
    tail = body('Tail', B0, (3.2, 0.8, 0.8), (0.2, 0.22, 0.15), seg=128)
    C.view_layer.update()
    Mi = tail.matrix_world.inverted()

    def surface_line(z_off, x0, x1, n=40):
        pts, nrm = [], []
        for x in np.linspace(x0, x1, n):
            o = Mi @ Vector((x, -5.0, B0.z + z_off))
            ok, loc, nn, _i = tail.ray_cast(o, Vector((0.0, 1.0, 0.0)))
            if ok:
                pts.append(tuple(loc))
                nrm.append(tuple(nn.normalized()))
        return pts, nrm

    st = gl.settings(S, 'CREATURE')
    for scale_id, z_off, te, ts_ in (('DRAGON', 0.42, 0.8, 0.0), ('PANGOLIN', 0.0, 0.7, 0.7),
                                      ('OSTEODERM', -0.42, 0.0, 0.0)):
        select(tail)
        print(scale_id, bpy.ops.mch.scale_pick(scale=scale_id))
        st.taper_end, st.taper_start, st.scale_random = te, ts_, 0.0
        pts, nrm = surface_line(z_off, -2.6, 2.6)
        ln = gl.new_line(C, tail, pts, nrm, gl.picked(st), st, 'CREATURE')
        print(scale_id, 'line:', gl.rebuild(ln, C), 'scales, taper', te, ts_)
    for ln in [o for o in S.objects if gl.is_line(o)]:
        gl.apply_line(C, ln)
    tag('scale')

# ---- (3) Insect Wing on curved outlines: before / now ---------------------------------------------------------------


def banana(x0, z0, s=1.0):
    a, b = [], []
    for i in range(60):
        t = i / 59
        an = math.radians(-20 + 80 * t)
        w_ = 0.2 * math.sin(math.pi * t) ** 0.7 + 0.02
        cx, cz = 1.25 * math.sin(an), 1.25 * (1 - math.cos(an))
        nx_, nz_ = -math.sin(an), math.cos(an)
        a.append((cx + nx_ * w_ * 0.3, cz + nz_ * w_ * 0.3))
        b.append((cx - nx_ * w_, cz - nz_ * w_))
    return [(x0 + s * x, z0 + s * z) for x, z in a + b[::-1]]


def fan(x0, z0, s=1.0):
    pts = [(0.0, 0.0)]
    for i in range(50):
        an = math.radians(15 + 70 * i / 49)
        r = 1.35 * (1.0 - 0.06 * math.cos(math.pi * i / 49 * 2))
        pts.append((r * math.cos(an), r * math.sin(an) - 0.55))
    pts.append((0.06, -0.02))
    return [(x0 + s * x, z0 + s * z) for x, z in pts]


def lobed(x0, z0, s=1.0):
    top = [(1.6 * t, 0.05 * math.sin(math.pi * t)) for t in np.linspace(0, 1, 40)]
    bot = [(1.6 * t, -(0.32 * math.sin(math.pi * t) ** 0.6) * (1.0 + 0.22 * math.sin(3 * math.pi * t * 2)))
           for t in np.linspace(1, 0, 60)]
    return [(x0 + s * x, z0 + s * z) for x, z in top + bot[1:-1]]


if ONLY in ('', 'wing'):
    W0 = Vector((0.0, 0.0, -20.0))
    HF = iw.HFrame
    for row, (zrow, frame) in enumerate(((1.2, iw.Frame), (-1.6, HF))):
        iw.HFrame = frame                        # (top row: the straight frame of 0.24.173, bottom: now)
        for col, (shape, preset, xc) in enumerate(((banana, 'DRAGONFLY', -3.2), (fan, 'P_LACEWING', -0.6),
                                                   (lobed, 'P_BROAD', 1.9))):
            S.mch_wing.preset = preset
            outline = shape(xc, W0.z + zrow)
            select()
            print(iw.perform(C, [[FRONT.to_screen(Vector((x, -5.0, z))) for x, z in outline]], FRONT))
            w = C.active_object
            iw.apply_wing(w)                     # (kept: a plain mesh - not laid again with the other frame)
    iw.HFrame = HF
    tag('wing')

# ---- (4) Weathering drawn like Armor Plate ----------------------------------------------------------------------------
if ONLY in ('', 'weather'):
    G0 = Vector((20.0, 0.0, -30.0))
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=120, y_subdivisions=60, size=1.0, location=G0)
    ground = C.active_object
    ground.name = 'Ground'
    ground.scale = (8.0, 4.0, 1.0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    rng = np.random.default_rng(3)
    for v in ground.data.vertices:
        v.co.z += 0.04 * math.sin(v.co.x * 2.1) * math.cos(v.co.y * 1.7) + 0.01 * rng.random()
    bpy.ops.object.shade_smooth()
    ground.data.materials.append(mat('Ground Earth', (0.32, 0.27, 0.2), 0.9))
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=0.6, location=G0 + Vector((1.9, 0.6, 0.05)))
    rock = C.active_object
    rock.name = 'Rock'
    rock.scale = (1.3, 1.0, 0.7)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    rock.data.materials.append(mat('Rock', (0.35, 0.35, 0.36), 0.8))
    C.view_layer.update()
    for kind, (cx, cy, rx, ry) in (('DIRT', (-2.6, -0.4, 1.0, 0.7)), ('DUST', (-0.6, 0.6, 0.8, 0.6)),
                                   ('LEAVES', (0.0, -1.0, 0.9, 0.55)), ('SNOW', (1.9, 0.5, 1.2, 0.9))):
        loop = [TOP.to_screen(Vector((G0.x + cx + rx * math.cos(t) * (1 + 0.12 * math.sin(3 * t)),
                                      G0.y + cy + ry * math.sin(t), G0.z + 3.0)))
                for t in np.linspace(0, 2 * math.pi, 64, endpoint=False)]
        select()
        print(wt.perform(C, [loop], TOP, kind))
    tag('weather')

# ---- (5) Creature Cloth with Surface on separate bone meshes -----------------------------------------------------------
if ONLY in ('', 'membrane'):
    M0 = Vector((40.0, 0.0, 0.0))
    bone_mat = mat('Bone', (0.36, 0.3, 0.25), 0.5)

    def bone(name, a_, b_, r0, r1):
        A, B = M0 + Vector(a_), M0 + Vector(b_)
        bm = bmesh.new()
        m_ = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=r0, radius2=r1, depth=(B - A).length)
        bmesh.ops.rotate(bm, verts=m_['verts'], cent=(0, 0, 0), matrix=(B - A).to_track_quat('Z', 'Y').to_matrix())
        bmesh.ops.translate(bm, verts=m_['verts'], vec=(A + B) / 2)
        bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=r0 * 1.15, matrix=Matrix.Translation(A))
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        for p in me.polygons:
            p.use_smooth = True
        ob = bpy.data.objects.new(name, me)
        S.collection.objects.link(ob)
        ob.data.materials.append(bone_mat)
        return ob

    bones = {'Arm': ((-0.2, 0, 1.0), (1.4, 0, 1.2), 0.07, 0.05), 'Finger 1': ((1.4, 0, 1.2), (2.9, 0, 0.6), 0.045, 0.02),
             'Finger 2': ((1.4, 0, 1.2), (2.4, 0, -0.3), 0.045, 0.02),
             'Finger 3': ((1.4, 0, 1.2), (1.3, 0, -0.6), 0.045, 0.02)}
    for nm, (a_, b_, r0, r1) in bones.items():
        bone(nm, a_, b_, r0, r1)
    C.view_layer.update()
    VIEW = [FRONT]
    sl.make_projector = lambda region, rv3d: VIEW[0]

    class Ctx:
        def __init__(self):
            self.area = types.SimpleNamespace(type='VIEW_3D', header_text_set=lambda t: None, tag_redraw=lambda: None)
            self.region = types.SimpleNamespace(width=1000, height=1000)
            self.region_data = object()

        scene = property(lambda self: bpy.context.scene)
        view_layer = property(lambda self: bpy.context.view_layer)
        selected_objects = property(lambda self: bpy.context.selected_objects)

        def evaluated_depsgraph_get(self):
            return bpy.context.evaluated_depsgraph_get()

    class Op(sl.SurfaceLogic):
        pass

    def on(nm, t):
        a_, b_ = bones[nm][0], bones[nm][1]
        p = M0 + Vector(a_).lerp(Vector(b_), t)
        return tuple(FRONT.to_screen(Vector((p.x, -3.0, p.z))))

    S.mch_membrane.style = 'CLOTH'
    S.mch_membrane.preset = 'DRAGON'
    S.mch_membrane.detail = 70
    ctx, op = Ctx(), Op()
    print('start', op.start(ctx, on('Arm', 0.05), 'MEMBRANE'))
    for q in (on('Arm', 0.5), on('Arm', 0.95), on('Finger 1', 0.5), on('Finger 1', 0.97), on('Finger 2', 0.97),
              on('Finger 3', 0.97), on('Finger 3', 0.4)):
        op.click(ctx, q)
    print('owners', [op.target.owner_at(p) for p, _n in op.points])
    print(op.finish(ctx))
    while cd.step(C):
        pass
    print(cd.confirm(C))
    tag('membrane')

for c_ in bpy.data.collections:
    if c_.name.startswith('MCH Cover') or c_.name.endswith('Parts'):
        c_.hide_render = True
for o in list(S.objects):
    if o.type == 'MESH' and gl.STAMP_TAG in o.keys():
        o.hide_render = True

# ---- scene ---------------------------------------------------------------------------------------------------------
S.world = bpy.data.worlds.new('Before')
cl.apply(S, 'soft_studio')
sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
S.collection.objects.link(sun)
sun.data.energy = 3.2
sun.rotation_euler = (math.radians(40), 0.0, math.radians(-30))
back = bpy.data.objects.new('Back', bpy.data.lights.new('Back', 'SUN'))
S.collection.objects.link(back)
back.data.energy = 2.5
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
SOURCES = [o for o in S.objects if o.type == 'MESH' and o.visible_get() and not o.hide_render
           and not any(c.hide_render for c in o.users_collection)]


def make_wires(group):
    """The wireframe copies of one group's meshes (only that group: the others' would fill the memory)."""
    dg = C.evaluated_depsgraph_get()
    out = []
    for src in SOURCES:
        if src.get('demo') != group:
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
        o.hide_render = o.get('demo') != group
    print(group, 'shown:', [o.name for o in SOURCES if not o.hide_render])
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


if ONLY in ('', 'edge'):
    S.render.resolution_x, S.render.resolution_y = 1600, 560
    aim((0.0, -8.0, 0.3), (0.0, 0.0, 0.0), 50, ortho=9.4)
    render('thinner_at_edge', 0.0012, 'edge')
if ONLY in ('', 'scale'):
    S.render.resolution_x, S.render.resolution_y = 1500, 600
    aim((0.0, -8.0, -9.4), (0.0, 0.0, -10.0), 50, ortho=7.2)
    render('scale_line_taper', 0.0012, 'scale')
if ONLY in ('', 'wing'):
    S.render.resolution_x, S.render.resolution_y = 1500, 1000
    aim((-0.3, -8.0, -20.0), (-0.3, 0.0, -20.0), 50, ortho=8.4)
    render('wing_follows_shape', 0.0012, 'wing')
if ONLY in ('', 'weather'):
    S.render.resolution_x, S.render.resolution_y = 1500, 850
    aim((20.0, -6.8, -25.6), (19.8, 0.0, -30.0), 40)
    render('weathering_drawn', 0.0015, 'weather')
if ONLY in ('', 'membrane'):
    S.render.resolution_x, S.render.resolution_y = 1400, 900
    aim((41.4, -6.5, 1.6), (41.4, 0.0, 0.3), 45)
    render('surface_membrane', 0.002, 'membrane')
