"""0.24.180 demo, Cycles, shaded and wireframe:
  fill   - hair in a sculpted shape fills it to its outline (user: "좀 더 메쉬 외곽까지의 형태가 비슷한 게"): a head with a
           lock over the top, a fan-shaped bang and a ponytail bulging in the middle - left: the shapes; right: the hair
  groom  - the same hair, left as made; right: Gravity, a comb stroke down the side, Blonde (user: "머리카락 빗는 것도",
           "그래비티나 그런 게 왜 메쉬 머리카락에는 안 되는겨", "원래 기존에 있던 헤어 세팅 다 쓸 수 있으면")
  loops  - Edge Loop for the bevels (user: "엣지 루프 기능도 만들어 주라 - 베벨 말이지"), one click each: a box's top loop
           (Boolean Bevel chamfer), a cylinder's cap (round), a plate's hole rim (chamfer), an L step's low top (round,
           the inside corner left), a box's top loop with Geo Sculpt Chamfer

    <blender python> round180_demo.py <out dir>
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
ONLY = set(os.environ.get('ONLY', 'fill,groom,loops').split(','))
os.makedirs(OUT, exist_ok=True)
mecha_lab.register()
from mecha_lab import core_geometry as cg, creature_light as cl, creature_spike as cs  # noqa: E402
from mecha_lab import bool_bevel as bb, edge_runs, geo_sculpt as gs, hair_shape as hs  # noqa: E402
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



def tube(name, centre, rad_fn, mat_, ring=24, flat=1.0, side=None):
    bm = bmesh.new()
    rings = []
    for i, c in enumerate(centre):
        t = i / (len(centre) - 1)
        tan = (centre[min(i + 1, len(centre) - 1)] - centre[max(i - 1, 0)]).normalized()
        u = (Vector(side) - tan * tan.dot(Vector(side))).normalized() if side else tan.orthogonal().normalized()
        v = tan.cross(u)
        r = rad_fn(t)
        rings.append([bm.verts.new(c + (u * math.cos(a) * r + v * math.sin(a) * r * flat))
                      for a in np.linspace(0, 2 * math.pi, ring, endpoint=False)])
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(ring):
            bm.faces.new((a[k], a[(k + 1) % ring], b[(k + 1) % ring], b[k]))
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


def head_and_shapes(offset=Vector((0.0, 0.0, 0.0))):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32, location=offset)
    head = C.active_object
    head.name = 'Head'
    bpy.ops.object.shade_smooth()
    head.data.materials.append(mat('Skin', (0.55, 0.42, 0.36), 0.5))
    clay = mat('Clay', (0.5, 0.48, 0.45), 0.6)
    o = offset
    lock = lock_mesh('Lock', [p + o for p in bez([(0.0, 0.1, 0.9), (0.5, 0.0, 1.5), (1.4, 0.1, 0.9), (1.2, 0.2, -0.3)])],
                     0.22, 0.03, clay)
    fan = tube('Bang', [p + o for p in bez([(-0.45, -0.75, 0.62), (-0.55, -1.15, 0.45), (-0.55, -1.25, 0.0),
                                             (-0.5, -1.22, -0.45)])],
               lambda t: 0.08 + 0.32 * math.sin(min(t * 1.2, 1.0) * math.pi / 2) * (1 - 0.6 * max(t - 0.8, 0) / 0.2),
               clay, flat=0.2, side=(1.0, 0.0, 0.0))
    pony = tube('Ponytail', [p + o for p in bez([(-0.3, 0.8, 0.6), (-0.4, 1.3, 0.6), (-0.5, 1.55, 0.1), (-0.5, 1.45, -0.6),
                                                  (-0.45, 1.3, -1.1)])],
                lambda t: 0.06 + 0.24 * math.sin(t * math.pi) ** 0.8 * (1 - t * 0.3), clay)
    return head, [lock, fan, pony]


def hair_on(head, shapes):
    S.mch_hshape.count = 6000
    S.mch_hshape.root_color, S.mch_hshape.tip_color = (0.05, 0.03, 0.02), (0.35, 0.22, 0.12)
    out = []
    for sh in shapes:
        for o in C.selected_objects:
            o.select_set(False)
        hair, msg = hs.make(C, sh, head)
        print(msg)
        out.append(hair)
    return out


def scene_fill():
    clear()
    head_and_shapes(Vector((-3.4, 0.0, 0.0)))          # (left: the shapes as sculpted)
    head, shapes = head_and_shapes()
    hair_on(head, shapes)
    stage((-1.0, -9.0, 2.6), (-1.7, 0.0, 0.1), lens=38)
    shoot('hair_fill', thick=0.002)


def scene_groom():
    clear()
    h0, s0 = head_and_shapes(Vector((-3.4, 0.0, 0.0)))
    hair_on(h0, s0)                                    # (left: as made)
    head, shapes = head_and_shapes()
    hairs = hair_on(head, shapes)
    for hr in hairs:
        p = hr.mch_hshape
        p.gravity = 0.55
        C.view_layer.objects.active = hr
        bpy.ops.mch.hair_shape_colour(preset='BLONDE')
    # a comb stroke down the lock's side (as the Comb tool stores it), toward -x / down
    lock_hair = hairs[0]
    cache = hs._CACHE[lock_hair.name]
    G = cache['Gf']
    c0 = G[:, G.shape[1] // 2].mean(0)
    stroke = {'m': 'C', 's': 0.9, 'v': [0.0, 1.0, 0.0],
              'p': [list(c0 + np.array([0.06 * k, 0.0, -0.05 * k])) + [0.6, 0.0, -0.8] + [0.45] for k in range(8)]}
    import json
    lock_hair[hs.COMBS] = json.dumps([stroke])
    for hr in hairs:
        hs.rebuild(hr)
    stage((-1.0, -9.0, 2.6), (-1.7, 0.0, 0.1), lens=38)
    shoot('hair_groom', thick=0.002)


def scene_loops():
    clear()
    st = S.mch_bool_bevel
    st.edge_loop = True
    steel = mat('Steel', (0.32, 0.35, 0.38), 0.4, 0.6)
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(-4.5, 0.0, 0.0))
    bx = C.active_object
    bx.data.materials.append(steel)
    st.profile, st.width = 'CHAMFER', 0.25
    print(bb.perform(C, bx, [(0.0, -0.9, 1.0)], whole=True, reach=0.08, loop=True))
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=1.0, depth=2.0, location=(-1.5, 0.0, 0.0))
    cy = C.active_object
    cy.data.materials.append(steel)
    st.profile, st.width, st.segments = 'ROUND', 0.25, 10
    print(bb.perform(C, cy, [(0.0, -0.95, 1.0)], whole=True, reach=0.08, loop=True))
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(1.5, 0.0, 0.0))
    pl = C.active_object
    pl.scale = (1.0, 0.25, 1.0)
    bpy.ops.object.transform_apply(location=False, scale=True)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(1.5, 0.0, 0.0))
    hole = C.active_object
    hole.scale = (0.9, 1.0, 0.7)
    m = pl.modifiers.new('B', 'BOOLEAN')
    m.object, m.solver = hole, 'EXACT'
    C.view_layer.objects.active = pl
    bpy.ops.object.modifier_apply(modifier='B')
    bpy.data.objects.remove(hole)
    pl.data.materials.clear()
    pl.data.materials.append(steel)
    st.profile, st.width = 'CHAMFER', 0.12
    print(bb.perform(C, pl, [(0.0, -0.25, 0.4)], whole=True, reach=0.08, loop=True))
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(4.5, 0.0, 0.0))
    lo = C.active_object
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(4.5, 1.0, 1.0))
    hi_ = C.active_object
    hi_.scale = (1.0, 0.5, 2.0)
    bpy.ops.object.transform_apply(location=False, scale=True)
    mm = lo.modifiers.new('U', 'BOOLEAN')
    mm.object, mm.operation, mm.solver = hi_, 'UNION', 'EXACT'
    C.view_layer.objects.active = lo
    bpy.ops.object.modifier_apply(modifier='U')
    bpy.data.objects.remove(hi_)
    lo.data.materials.clear()
    lo.data.materials.append(steel)
    st.profile, st.width = 'ROUND', 0.25
    print(bb.perform(C, lo, [(0.0, -0.95, 1.0)], whole=True, reach=0.08, loop=True))
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 4.0, 0.0))
    gb = C.active_object
    gb.data.materials.append(mat('Geo', (0.45, 0.3, 0.22), 0.45, 0.3))
    got = gs.pick_run(gb, (0.0, -0.9, 1.0), 0.1, loop=True)
    gs.mark_edges(gb, 'CHAMFER', got[1], 0.18)
    stage((0.0, -12.0, 7.0), (0.0, 1.0, 0.0), lens=36)
    shoot('bevel_edge_loop', thick=0.0012)


for _nm in ('fill', 'groom', 'loops'):
    if _nm in ONLY:
        globals()['scene_' + _nm]()
print('done')
