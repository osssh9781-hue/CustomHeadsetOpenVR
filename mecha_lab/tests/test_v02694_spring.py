"""0.24.294 Spring Generator (user: "직선 어레이 메뉴처럼 스프링 제네레이터도 - 그으면 스프링, 두께 · 폭은 추후에 정해서
엔터나 어플라이로 확정"): draw a line -> a live coil spring; Width / Wire / Coils ... change it after; Apply keeps it."""
import math

from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import spring_gen as sg, tool_state as ts, target_rules as tr

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
from mecha_lab import core_geometry as cg
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)


def bbox(ob):
    C.view_layer.update()
    vs = [ob.matrix_world @ v.co for v in ob.data.vertices]
    lo = Vector([min(v[i] for v in vs) for i in range(3)])
    hi = Vector([max(v[i] for v in vs) for i in range(3)])
    return lo, hi


check('Spring is a tool (list, Curves group, enum 88, a shape tool, its own panel / workspace tool)',
      'SPRING' in ts.TOOL_BY_ID and 'SPRING' in dict(ts.TOOL_GROUPS)['Curves'] and ts._ENUM_NUMBERS['SPRING'] == 88
      and 'SPRING' in ts.SHAPE_TOOLS and ts.TOOL_BY_ID['SPRING'][5] == 'mecha.spring')
S.cursor.location = (0, 0, 0)
msg = sg.perform(C, [(300, 500), (700, 500)], 'LASSO', TOP)          # a line 4 units long, on the cursor plane
ob = C.active_object
check('a line -> a live spring, active and selected, Auto width / wire', sg.is_spring(ob) and ob.select_get()
      and abs(ob.mch_spring.width - 4 * sg.AUTO_WIDTH) < 1e-4 and abs(ob.mch_spring.wire - ob.mch_spring.width * sg.AUTO_WIRE) < 1e-5
      and 'Enter' in msg, (msg, ob and ob.mch_spring.width))
lo, hi = bbox(ob)
w = ob.mch_spring.width
check('... 4 long along the line, as wide as Width across', abs((hi.x - lo.x) - 4.0) < 0.02
      and abs((hi.y - lo.y) - w) < w * 0.05 and abs((hi.z - lo.z) - w) < w * 0.05, (lo, hi, w))
check('... a closed (watertight) mesh', non_manifold(ob) == 0 and len(ob.data.polygons) > 100, len(ob.data.polygons))
f0 = len(ob.data.polygons)
ob.mch_spring.width = 1.0
lo, hi = bbox(ob)
check('Width changed after drawing: rebuilt 1.0 wide, same length', abs((hi.y - lo.y) - 1.0) < 0.05
      and abs((hi.x - lo.x) - 4.0) < 0.02, (lo, hi))
ob.mch_spring.wire = 0.1
lo, hi = bbox(ob)
check('Wire 0.1: still 1.0 outside (the wire inside the width)', abs((hi.y - lo.y) - 1.0) < 0.05, (lo, hi))
ob.mch_spring.coils = 4
f4 = len(ob.data.polygons)
ob.mch_spring.coils = 12
check('Coils 4 -> 12: more turns (more faces)', len(ob.data.polygons) > f4 * 1.6, (f4, len(ob.data.polygons)))


def x_turns(ob):
    """How many times the wire's centre line crosses the top (y > 0, z near 0 is not needed): count sign changes of
    the ring centres' y."""
    m = len(sg.profile(ob.mch_spring))
    ys = []
    vs = ob.data.vertices
    for i in range(0, len(vs) - m + 1, m):
        ys.append(sum(vs[i + k].co.y for k in range(m)) / m)
    return sum(1 for a, b in zip(ys, ys[1:]) if a < 0 <= b)


ob.mch_spring.end_coils = 0.0
n12 = x_turns(ob)
check('... 12 coils = about 12 turns of the wire', 11 <= n12 <= 13, n12)
ob.mch_spring.end_coils = 1.0
d = sg._data(ob)
vs = [v.co for v in ob.data.vertices]
check('Closed Ends: the end turns tight (the wire\'s first turn within ~2 wires of the end)',
      min(v.x for v in vs) > -0.06 and max(v.x for v in vs) < 4.06)
ob.mch_spring.end_width = 0.5
m = len(sg.profile(ob.mch_spring))
vs = ob.data.vertices
near_end = [v.co for v in vs if v.co.x > 3.6]
near_start = [v.co for v in vs if v.co.x < 0.4]
re_ = max(abs(v.y) for v in near_end)
rs = max(abs(v.y) for v in near_start)
check('End Width 0.5: a cone (the far end about half as wide)', re_ < rs * 0.7, (rs, re_))
ob.mch_spring.end_width = 1.0
for prof in ('SQUARE', 'FLAT', 'ROUND'):
    ob.mch_spring.profile = prof
    check(f'wire profile {prof}: closed mesh', non_manifold(ob) == 0 and len(ob.data.polygons) > 50)
ob.mch_spring.hand = 'LEFT'
check('Left hand: closed', non_manifold(ob) == 0)
ob.mch_spring.path = 'FOLLOW'
ob.mch_spring.path = 'STRAIGHT'
check('Path changed and back: still a 4-long spring', abs((bbox(ob)[1].x - bbox(ob)[0].x) - 4.0) < 0.05)
bpy.ops.mch.spring_apply()
check('Apply (Enter): no longer live, the mesh kept', not sg.is_spring(ob) and len(ob.data.polygons) > 50)
nf = len(ob.data.polygons)
ob.mch_spring.coils = 3
check('... settings no longer change it', len(ob.data.polygons) == nf)
# a curved drawing, Follow
S.mch_spring.path = 'FOLLOW'
arc = [(500 + 200 * math.cos(a), 500 + 200 * math.sin(a)) for a in (math.pi * k / 30 for k in range(31))]
sg.perform(C, arc, 'STROKE', TOP)
ob2 = C.active_object
lo, hi = bbox(ob2)
w2 = ob2.mch_spring.width
check('Follow: a spring bent along a half circle (axis 4 wide, 2 tall; + its width)', sg.is_spring(ob2)
      and abs((hi.x - lo.x) - (4.0 + w2)) < 0.15 and abs((hi.y - lo.y) - (2.0 + w2 / 2)) < 0.15
      and non_manifold(ob2) == 0, (lo, hi, w2))
S.mch_spring.path = 'STRAIGHT'
# from one part to another: both ends on parts -> end to end in 3D
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-2, 0, 0))
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(2, 0, 1.0))
S.mch_spring.width = 0.3
sg.perform(C, [(300, 500), (700, 500)], 'LASSO', TOP)
ob3 = C.active_object
C.view_layer.update()
d3 = sg._data(ob3)
p0 = ob3.matrix_world @ Vector(d3['path'][0])
p1 = ob3.matrix_world @ Vector(d3['path'][-1])
check('both ends on parts: from the top of one (z 0.5) to the top of the other (z 1.5)', d3.get('ends3d')
      and abs(p0.z - 0.5) < 1e-3 and abs(p1.z - 1.5) < 1e-3 and abs(ob3.mch_spring.width - 0.3) < 1e-6, (p0, p1))
S.mch_spring.width = 0.0
summary()
