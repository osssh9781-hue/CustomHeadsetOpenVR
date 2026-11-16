"""0.24.179 demo, Cycles, shaded and wireframe:
  hair    - hair in a sculpted shape (user: "털 모양 스컬핑에 맞춰서 머리카락" - "따로 만든 메쉬", "결 시작 부분은 내가 찍어
            주는 게"): a head and two locks sculpted as their own meshes (one bent over the head, one hanging down the
            side); the hair fills them following them (left: the locks; right: the hair)
  pop     - Face Pop (user: "내가 선택한 면이 튀어나오게"): a faceted rock, a dozen faces popped out (Each Face, Taper)
  corners - Boolean Bevel corners (user: "저 베벨이 만나야 되는 거 아니여?"): a block - its bottom front edge rounded, then
            its right front edge chamfered: they meet; a step - its low top edge and its tall front edge rounded: no block
            left in the corner

    <blender python> round179_demo.py <out dir>
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
ONLY = set(os.environ.get('ONLY', 'hair,pop,corners').split(','))
os.makedirs(OUT, exist_ok=True)
mecha_lab.register()
from mecha_lab import core_geometry as cg, creature_light as cl, creature_spike as cs  # noqa: E402
from mecha_lab import bool_bevel as bb, face_pop as fp, hair_shape as hs  # noqa: E402
import bmesh  # noqa: E402

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




def lock_mesh(name, centre, r0, r1, mat_):
    bm = bmesh.new()
    rings = []
    for i, c in enumerate(centre):
        t = i / (len(centre) - 1)
        tan = (centre[min(i + 1, len(centre) - 1)] - centre[max(i - 1, 0)]).normalized()
        u = tan.orthogonal().normalized()
        v = tan.cross(u)
        r = r0 + (r1 - r0) * t ** 1.3
        rings.append([bm.verts.new(c + (u * math.cos(a) * 1.3 + v * math.sin(a) * 0.8) * r)
                      for a in np.linspace(0, 2 * math.pi, 20, endpoint=False)])
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(20):
            bm.faces.new((a[k], a[(k + 1) % 20], b[(k + 1) % 20], b[k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    S.collection.objects.link(ob)
    me.materials.append(mat_)
    for p in me.polygons:
        p.use_smooth = True
    return ob


def bez(P, n=60):
    P = [Vector(p) for p in P]
    out = []
    for i in range(n):
        t = i / (n - 1)
        q = list(P)
        while len(q) > 1:
            q = [a.lerp(b, t) for a, b in zip(q[:-1], q[1:])]
        out.append(q[0])
    return out


def scene_hair():
    clear()
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32)
    head = C.active_object
    head.name = 'Head'
    bpy.ops.object.shade_smooth()
    head.data.materials.append(mat('Skin', (0.55, 0.42, 0.36), 0.5))
    clay = mat('Clay', (0.5, 0.48, 0.45), 0.6)
    locks = [lock_mesh('Lock A', bez([(0.0, -0.2, 0.9), (0.5, -0.3, 1.5), (1.4, -0.2, 0.9), (1.2, -0.1, -0.3)]),
                       0.22, 0.03, clay),
             lock_mesh('Lock B', bez([(-0.3, -0.5, 0.75), (-1.0, -0.9, 0.9), (-1.3, -0.9, -0.2), (-1.0, -0.7, -1.0)]),
                       0.2, 0.03, clay)]
    left = [o for o in S.objects]
    shift = Vector((-3.2, 0.0, 0.0))                  # (the locks as sculpted, on the left; the hair on the right)
    for o in left:
        c = o.copy()
        c.data = o.data.copy()
        S.collection.objects.link(c)
        c.location += shift
    S.mch_hshape.count = 5000
    S.mch_hshape.root_color, S.mch_hshape.tip_color = (0.05, 0.03, 0.02), (0.35, 0.22, 0.12)
    for lk, start in zip(locks, (None, None)):
        for o in C.selected_objects:
            o.select_set(False)
        print(hs.make(C, lk, head, starts=start)[1])
    stage((0.0, -9.5, 1.4), (-1.6, 0.0, 0.2), lens=40)
    shoot('hair_shape', thick=0.002)


def scene_pop():
    clear()
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1.0)
    rock = C.active_object
    rock.name = 'Rock'
    rock.scale = (1.3, 1.0, 0.8)
    bpy.ops.object.transform_apply(scale=True)
    rock.data.materials.append(mat('Rock', (0.36, 0.34, 0.31), 0.85))
    S.mch_pop.height, S.mch_pop.taper, S.mch_pop.each = 0.12, 0.35, True
    rng = np.random.default_rng(4)
    faces = [p.index for p in rock.data.polygons if p.normal.y < -0.2 or p.normal.z > 0.4]
    pick = rng.choice(faces, size=min(18, len(faces)), replace=False)
    fp.set_faces(rock, pick, True, S.mch_pop)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1.0, location=(3.0, 0.0, 0.0))
    rock2 = C.active_object
    rock2.scale = (1.3, 1.0, 0.8)
    bpy.ops.object.transform_apply(scale=True)
    rock2.data.materials.append(mat('Rock2', (0.36, 0.34, 0.31), 0.85))
    S.mch_pop.height, S.mch_pop.taper, S.mch_pop.each = 0.2, 0.15, False
    faces2 = [p.index for p in rock2.data.polygons if p.normal.y < -0.5 and p.normal.z > -0.2]
    fp.set_faces(rock2, faces2, True, S.mch_pop)
    stage((1.5, -6.0, 3.2), (1.5, 0.0, 0.0), lens=42)
    shoot('face_pop', thick=0.0015)


def scene_corners():
    clear()
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    bx = C.active_object
    bx.data.materials.append(mat('Block', (0.32, 0.35, 0.38), 0.4, 0.6))
    st = S.mch_bool_bevel
    st.profile, st.width, st.segments = 'ROUND', 0.3, 10
    print(bb.perform(C, bx, [(0.0, -1.0, -1.0)], whole=True, reach=0.05))
    st.profile = 'CHAMFER'
    print(bb.perform(C, bx, [(1.0, -1.0, 0.0)], whole=True, reach=0.05))
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(3.2, 0.0, -0.5))
    stp = C.active_object
    stp.scale = (2.0, 1.4, 1.0)
    bpy.ops.object.transform_apply(location=False, scale=True)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(3.95, 0.0, 0.0))
    tall = C.active_object
    tall.scale = (0.5, 1.4, 2.0)
    bpy.ops.object.transform_apply(location=False, scale=True)
    m = stp.modifiers.new('U', 'BOOLEAN')
    m.object, m.operation, m.solver = tall, 'UNION', 'EXACT'
    C.view_layer.objects.active = stp
    bpy.ops.object.modifier_apply(modifier='U')
    bpy.data.objects.remove(tall)
    stp.data.materials.clear()
    stp.data.materials.append(mat('Step', (0.32, 0.35, 0.38), 0.4, 0.6))
    st.profile, st.width = 'ROUND', 0.18
    mi = stp.matrix_world.inverted()
    print(bb.perform(C, stp, [tuple(mi @ Vector((3.0, -0.7, 0.0)))], whole=True, reach=0.05))
    print(bb.perform(C, stp, [tuple(mi @ Vector((3.7, -0.7, 0.5)))], whole=True, reach=0.05))
    stage((2.4, -7.0, 2.8), (1.6, 0.0, -0.1), lens=40)
    shoot('bevel_corners', thick=0.0015)


for _nm in ('hair', 'pop', 'corners'):
    if _nm in ONLY:
        globals()['scene_' + _nm]()
print('done')
