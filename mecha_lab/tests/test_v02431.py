"""0.24.31 Clothing: a top and pants drawn over a body (front view) become closed garments from the body surface
(front and back), off the body, top over pants (Layer), Fit / Wrinkles live, Apply, tool wiring."""
import math
import os

from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Euler, Vector
from mathutils.bvhtree import BVHTree

import mecha_lab
from mecha_lab import clothing_gen as cl, core_geometry as cg, tool_state as ts, workspace_ui as wsui

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene

co = [Vector((0, 0, 0)), Vector((1, 0, 0)), Vector((0.5, 3, 0))]
r = cl.relax(co, [[1, 2], [0, 2], [0, 1]], {0}, 1)
check('relax: a fixed point stays, the others move toward their neighbours', r[0] == co[0] and r[2].y < 3)


def mannequin():
    parts = []

    def add(op, **kw):
        op(**kw)
        parts.append(C.active_object)
        return parts[-1]
    tor = add(bpy.ops.mesh.primitive_uv_sphere_add, radius=1, segments=40, ring_count=20, location=(0, 0, 1.25))
    tor.scale = (0.36, 0.22, 0.5)
    add(bpy.ops.mesh.primitive_uv_sphere_add, radius=0.12, segments=24, ring_count=12, location=(0, -0.02, 1.86))
    add(bpy.ops.mesh.primitive_cylinder_add, radius=0.06, depth=0.2, location=(0, 0, 1.72))
    add(bpy.ops.mesh.primitive_cylinder_add, radius=0.085, depth=0.95, location=(0, 0, 1.6), rotation=(0, math.pi / 2, 0))
    for sx in (-1, 1):
        add(bpy.ops.mesh.primitive_cylinder_add, radius=0.06, depth=0.7, location=(sx * 0.48, 0, 1.25))
        add(bpy.ops.mesh.primitive_cylinder_add, radius=0.09, depth=0.95, location=(sx * 0.14, 0, 0.48))
    for o in C.selected_objects:
        o.select_set(False)
    for o in parts:
        o.select_set(True)
    C.view_layer.objects.active = parts[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.join()
    body = C.active_object
    body.name = 'Body'
    body.scale = (3, 3, 3)
    body.location = (0, 0, -2.7)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return body



body = mannequin()
m = body.modifiers.new('r', 'REMESH')
m.mode, m.voxel_size = 'VOXEL', 0.05
C.view_layer.objects.active = body
bpy.ops.object.modifier_apply(modifier='r')
FRONT = cg.OrthoProjector(Euler((math.radians(90), 0, 0)).to_quaternion())
TOP = [[(425, 745), (575, 745), (680, 730), (700, 610), (650, 600), (620, 680), (615, 400), (385, 400), (380, 680),
        (350, 600), (300, 610), (320, 730)]]
PANTS = [[(400, 480), (600, 480), (585, 250), (515, 250), (503, 400), (497, 400), (485, 250), (415, 250)]]
bvh = BVHTree.FromPolygons([v.co for v in body.data.vertices], [tuple(p.vertices) for p in body.data.polygons])
made = {}
for kind, loop in (('TSHIRT', TOP), ('PANTS', PANTS)):
    S.mch_clothing.kind = kind
    msg = cl.perform(C, loop, FRONT)
    ob = C.active_object
    made[kind] = ob
    check(f'{kind}: a live garment on the body, closed mesh', cl.live_garment(C) == ob and 'on Body' in msg
          and non_manifold(ob) == 0, (msg, non_manifold(ob)))
    vs = [ob.matrix_world @ v.co for v in ob.data.vertices]
    check(f'{kind}: covers front and back (seen through)', min(v.y for v in vs) < -0.3 and max(v.y for v in vs) > 0.3)
    inside = 0
    for v in vs[::13]:
        loc, n, _i, _d = bvh.find_nearest(v)
        if loc is not None and (v - loc).dot(n) < -0.03:
            inside += 1
    check(f'{kind}: stays off the body', inside == 0, inside)
top, pants = made['TSHIRT'], made['PANTS']
zs = [(top.matrix_world @ v.co).z for v in top.data.vertices]
check('the top reaches up to the shoulders, the pants down the legs', max(zs) > 2.0
      and min((pants.matrix_world @ v.co).z for v in pants.data.vertices) < -2.0)
check('a top is layer 1 (over pants, layer 0)', top.mch_clothing.layer == 1 and pants.mch_clothing.layer == 0)
for o in C.selected_objects:
    o.select_set(False)
top.select_set(True)
C.view_layer.objects.active = top


def mean_dist(o):
    tot = 0.0
    vs = [o.matrix_world @ v.co for v in o.data.vertices][::17]
    for v in vs:
        loc, _n, _i, d = bvh.find_nearest(v)
        tot += d
    return tot / len(vs)


d0 = mean_dist(top)
top.mch_clothing.fit = 0.05
check('Fit is live (looser = further from the body)', mean_dist(top) > d0 + 0.05 and top.mch_clothing.last_error == '',
      (d0, mean_dist(top)))
top.mch_clothing.wrinkles = 1.2
check('more wrinkles: still a closed mesh', non_manifold(top) == 0)
r = bpy.ops.mch.clothing_apply()
check('Apply: plain mesh', 'FINISHED' in r and cl.SRC_KEY not in top)
try:
    cl.perform(C, [[(10, 10), (40, 10), (40, 30), (10, 30)]], FRONT)
    check('drawing next to the body: a clear message', False)
except cg.CutError as ex:
    check('drawing next to the body: a clear message', 'body' in str(ex), str(ex))
check('Clothing is in the tool list', 'GARMENT' in ts.TOOL_BY_ID)
check('Enter applies a live garment', ('clothing_apply', 'Clothing') in wsui.ENTER_APPLY)
summary()
