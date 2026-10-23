"""0.24.29 Creature Hair: roots spread in the drawn scalp area, Dreads / Tentacles / Quills / Strands on a mannequin
head (closed tubes, rings in slot 2, falling down, out of the body), live sliders, Apply, tool wiring."""
import math
import os
import random

from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Euler, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, creature_hair as ch, tool_state as ts, workspace_ui as wsui

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene

sq = [(0, 0), (100, 0), (100, 100), (0, 100)]
pts = ch.root_points(sq, 40, 1)
check('roots: about Count points, all inside the area', 30 <= len(pts) <= 52 and all(0 <= x <= 100 and 0 <= y <= 100
      for x, y in pts), len(pts))
check('roots: same seed = same points', ch.root_points(sq, 40, 1) == pts and ch.root_points(sq, 40, 2) != pts)
check('tube radius: thinner toward the tip, rope ridges vary it round', ch.tube_radius(1.0, 0, 1, 0.8, 0, 0, 10)
      < ch.tube_radius(0.0, 0, 1, 0.8, 0, 0, 10) and ch.tube_radius(0.5, 0.3, 1, 0, 0.2, 0, 10)
      != ch.tube_radius(0.5, 0.9, 1, 0, 0.2, 0, 10))
path = ch.strand_path(Vector((0, 0, 1)), Vector((0, 0, 1)), 2.0, 20, 0.5, 1.0, 0.0, random.Random(1))
check('a strand rises along the normal, then gravity bends it down', path[1].z > 1.0 and path[-1].z < path[5].z
      and len(path) == 21)


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
BACK = cg.OrthoProjector(Euler((math.radians(90), 0, math.pi)).to_quaternion())
SCALP = [[(466, 790), (534, 790), (530, 824), (500, 830), (470, 824)]]
from mathutils.bvhtree import BVHTree
bvh = BVHTree.FromPolygons([v.co for v in body.data.vertices], [tuple(p.vertices) for p in body.data.polygons])
made = {}
for style in ('DREADS', 'TENTACLE', 'QUILLS', 'STRANDS'):
    S.mch_hair.style = style
    msg = ch.perform(C, SCALP, BACK)
    ob = C.active_object
    made[style] = ob
    zs = [(ob.matrix_world @ v.co).z for v in ob.data.vertices]
    check(f'{style}: live hair on the body, closed tubes', ch.live_hair(C) == ob and 'on Body' in msg
          and non_manifold(ob) == 0, (msg, non_manifold(ob)))
    made[style] = (ob, min(zs), max(zs))
check('Dreads fall well below the head (to the back / shoulders)', made['DREADS'][1] < 1.5, made['DREADS'][1])
check('Quills stand up (little gravity): stay above the head bottom', made['QUILLS'][1] > 2.4, made['QUILLS'][1])
ob = made['DREADS'][0]
mi = {p.material_index for p in ob.data.polygons}
check('Dreads have rings in material slot 2 (own colour)', mi == {0, 1} and len(ob.data.materials) == 2
      and ob.data.materials[1].name.startswith('MCH Hair Rings'), (mi, [m.name for m in ob.data.materials]))
inside = 0
for v in list(ob.data.vertices)[::11]:
    w = ob.matrix_world @ v.co
    if w.z > 2.45:
        continue                     # the roots are meant to sit a little in the scalp (no gap there)
    loc, n, _i, _d = bvh.find_nearest(w)
    if loc is not None and (w - loc).dot(n) < -0.02:
        inside += 1
check('below the head the dreads do not go into the body (shoulders / back)', inside == 0, inside)
for o in C.selected_objects:
    o.select_set(False)
ob.select_set(True)
C.view_layer.objects.active = ob
n0 = len(ob.data.polygons)
ob.mch_hair.count = 12
check('Count is live (fewer strands)', len(ob.data.polygons) < n0 and ob.mch_hair.last_error == '', (n0, len(ob.data.polygons)))
ob.mch_hair.rings = 0
check('Rings 0: no slot-2 faces', {p.material_index for p in ob.data.polygons} == {0})
ob.mch_hair.count = 30
ob.mch_hair.rings = 0


def spread_below(o, z):
    vs = [o.matrix_world @ v.co for v in o.data.vertices]
    low = [v for v in vs if v.z < z]
    return max(v.x for v in low) - min(v.x for v in low)


ob.mch_hair.straight = 0.0
loose = spread_below(ob, 1.0)
ob.mch_hair.straight = 1.0
plumb = spread_below(ob, 1.0)
check('Straight: the strands hang straighter (less sideways spread below the shoulders)', plumb < loose * 0.95
      and non_manifold(ob) == 0, (loose, plumb))
ob.mch_hair.rope = 0.4
ob.mch_hair.wave = 1.0
check('rope / wave still closed', non_manifold(ob) == 0)
r = bpy.ops.mch.hair_apply()
check('Apply: plain mesh', 'FINISHED' in r and ch.SRC_KEY not in ob)
try:
    ch.perform(C, [[(10, 10), (40, 10), (40, 30), (10, 30)]], BACK)
    check('drawing next to the head: a clear message', False)
except cg.CutError as ex:
    check('drawing next to the head: a clear message', 'head' in str(ex), str(ex))
check('Creature Hair is in the tool list with its icon', 'HAIR' in ts.TOOL_BY_ID and os.path.isfile(
    os.path.join(os.path.dirname(mecha_lab.__file__), 'icons', 'hair.png')))
check('Enter applies live hair', ('hair_apply', 'Creature Hair') in wsui.ENTER_APPLY)
from mecha_lab import cut_engine as ce
check('the drawing tool sends Hair outlines to the generator', 'creature_hair.perform' in open(ce.__file__).read())
summary()
