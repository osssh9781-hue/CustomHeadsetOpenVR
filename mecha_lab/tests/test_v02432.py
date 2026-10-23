"""0.24.32 Hood + Scarf: drawn round the head / neck (front view) -> live, closed cloth pieces off the body.
Hood: every style, smooth oval face opening toward the viewer, Peak at the back, cowl down over the shoulders, Turn.
Scarf: every style (wraps, tails, front drape), drawn height, Wraps / Tail Length live, Apply, tool wiring."""
import math

from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Euler, Vector
from mathutils.bvhtree import BVHTree

import mecha_lab
from mecha_lab import core_geometry as cg, hood_gen as hg, scarf_gen as sg, tool_state as ts, workspace_ui as wsui

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene

sec = sg.ring_section(8, 2.0, 1.0)
check('scarf section: an oval Height x Thickness', abs(max(u for u, v in sec) - 2.0) < 1e-6
      and abs(max(v for u, v in sec) - 1.0) < 1e-6)
w = sg.tail_widths(5, 0.4)
check('tail taper: full width at the top, narrower at the end', w[0] == 1.0 and abs(w[-1] - 0.6) < 1e-6)
f = Vector((0, -1, 0))
check('hood direction: theta 0 / phi 90 = the front, phi 0 = up',
      (hg.direction(0, math.pi / 2, f) - f).length < 1e-6 and (hg.direction(1.0, 0, f) - Vector((0, 0, 1))).length < 1e-6)


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
HOOD = [[(455, 745), (545, 745), (552, 800), (540, 835), (500, 845), (460, 835), (448, 800)]]
SCARF = [[(470, 738), (530, 738), (530, 760), (470, 760)]]
HEAD = Vector((0, -0.06, 2.88))
bvh = BVHTree.FromPolygons([v.co for v in body.data.vertices], [tuple(p.vertices) for p in body.data.polygons])


def world(o):
    return [o.matrix_world @ v.co for v in o.data.vertices]


def sunk(o, depth=0.03):
    n = 0
    for v in world(o)[::7]:
        loc, nrm, _i, _d = bvh.find_nearest(v)
        if loc is not None and (v - loc).dot(nrm) < -depth:
            n += 1
    return n


for st in hg.STYLES:
    S.mch_hood.style = st
    msg = hg.perform(C, HOOD, FRONT)
    ob = C.active_object
    check(f'hood {st}: a live hood on the body, closed mesh, off the head', hg.live_hood(C) == ob and 'on Body' in msg
          and non_manifold(ob) == 0 and sunk(ob) == 0, (msg, non_manifold(ob), sunk(ob)))
    vs = world(ob)
    # the face stays uncovered: a ray from the viewer at the face centre hits the head, not the hood
    o, d = FRONT.ray((500, 790))
    hood_bvh = BVHTree.FromPolygons(vs, [tuple(p.vertices) for p in ob.data.polygons])
    hh = hood_bvh.ray_cast(Vector(o), Vector(d))
    bh = bvh.ray_cast(Vector(o), Vector(d))
    check(f'hood {st}: the face opening looks at the viewer', bh[0] is not None and (hh[0] is None or hh[3] > bh[3]),
          (hh[3], bh[3]))
    check(f'hood {st}: covers the back of the head', max(v.y for v in vs) > HEAD.y + 0.36
          and max(v.z for v in vs) > HEAD.z + 0.3)
    if st == 'CLOAK':
        cloak = ob
        check('cloak hood: the cowl reaches down over the shoulders', min(v.z for v in vs) < 2.25, min(v.z for v in vs))
    else:
        bpy.data.objects.remove(ob)
for o in C.selected_objects:
    o.select_set(False)
cloak.select_set(True)
C.view_layer.objects.active = cloak


def back_top(o):
    return max(v.y for v in world(o) if v.z > HEAD.z + 0.1)


back0 = back_top(cloak)
cloak.mch_hood.peak = 2.0
check('Peak is live (the back top goes further back)', back_top(cloak) > back0 + 0.05
      and cloak.mch_hood.last_error == '', (back0, back_top(cloak)))
cloak.mch_hood.turn = math.pi
o, d = FRONT.ray((500, 790))
hb = BVHTree.FromPolygons(world(cloak), [tuple(p.vertices) for p in cloak.data.polygons]).ray_cast(Vector(o), Vector(d))
check('Turn 180: the opening goes to the back (the face is covered)', hb[0] is not None and hb[3] < bvh.ray_cast(
    Vector(o), Vector(d))[3])
r = bpy.ops.mch.hood_apply()
check('hood Apply: plain mesh', 'FINISHED' in r and hg.SRC_KEY not in cloak)
bpy.data.objects.remove(cloak)

for st in sg.STYLES:
    S.mch_scarf.style = st
    msg = sg.perform(C, SCARF, FRONT)
    ob = C.active_object
    vs = world(ob)
    check(f'scarf {st}: a live scarf, closed mesh, off the body', sg.live_scarf(C) == ob and 'on Body' in msg
          and non_manifold(ob) == 0 and sunk(ob) == 0, (msg, non_manifold(ob), sunk(ob)))
    ring = [v for v in vs if v.z > 2.3]
    check(f'scarf {st}: wraps all round the neck', min(v.y for v in ring) < -0.2 and max(v.y for v in ring) > 0.2
          and min(v.x for v in ring) < -0.2 and max(v.x for v in ring) > 0.2)
    if sg.STYLES[st]['ends'] == 'NONE':
        check(f'scarf {st}: no ends - stays at the neck', min(v.z for v in vs) > 2.0, min(v.z for v in vs))
    else:
        check(f'scarf {st}: the ends hang down the chest', min(v.z for v in vs) < 1.9, min(v.z for v in vs))
    if st == 'WRAP':
        wrap = ob
    else:
        bpy.data.objects.remove(ob)
for o in C.selected_objects:
    o.select_set(False)
wrap.select_set(True)
C.view_layer.objects.active = wrap
n0 = len(wrap.data.polygons)
low0 = min(v.z for v in world(wrap))
wrap.mch_scarf.wraps = 3
check('Wraps is live (one more tube)', len(wrap.data.polygons) > n0 and non_manifold(wrap) == 0)
wrap.mch_scarf.tail_len = 7.0
check('Tail Length is live (the tails hang lower)', min(v.z for v in world(wrap)) < low0 - 0.3
      and sunk(wrap) == 0 and wrap.mch_scarf.last_error == '')
wrap.mch_scarf.ends = 'NONE'
check('Ends None: only the wraps', min(v.z for v in world(wrap)) > 2.0)
r = bpy.ops.mch.scarf_apply()
check('scarf Apply: plain mesh', 'FINISHED' in r and sg.SRC_KEY not in wrap)
for mod in (hg, sg):
    try:
        mod.perform(C, [[(10, 10), (40, 10), (40, 30), (10, 30)]], FRONT)
        check(f'{mod.__name__}: drawing next to the body - a clear message', False)
    except cg.CutError as ex:
        check(f'{mod.__name__}: drawing next to the body - a clear message', 'Draw round' in str(ex), str(ex))
check('Hood and Scarf are in the tool list', 'HOOD' in ts.TOOL_BY_ID and 'SCARF' in ts.TOOL_BY_ID)
check('Enter applies a live hood / scarf', ('hood_apply', 'Hood') in wsui.ENTER_APPLY
      and ('scarf_apply', 'Scarf') in wsui.ENTER_APPLY)
summary()
