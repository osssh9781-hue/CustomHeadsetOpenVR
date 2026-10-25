"""0.24.33 Jungle Gym prototype: crawl along a lattice of bars (step by screen direction, wheel = depth,
going back erases), magnet / corner shaping, closed flat loop = Base Mesh, else a live tube; F9 path (execute)."""
import json
import math

from _harness import bpy, check, fresh, summary
from mathutils import Matrix, Vector

import mecha_lab
from mecha_lab import jungle_gym as jg

mecha_lab.register()
fresh()
C = bpy.context

check('nice step: 1 / 2 / 5 values', (jg.nice_step(0.13), jg.nice_step(0.3), jg.nice_step(0.04), jg.nice_step(7))
      == (0.1, 0.2, 0.05, 5.0), (jg.nice_step(0.13), jg.nice_step(0.3), jg.nice_step(0.04), jg.nice_step(7)))

F = (Vector((0, 0, 0)), Matrix.Identity(3), 0.1)
front = lambda co: Vector((500 + co.x * 1000, 500 + co.z * 1000))           # looking along +Y, 1 m = 1000 px
scr = lambda x, z: (500 + x * 1000, 500 + z * 1000)

path = [(0, 0, 0)]
jg.crawl(path, scr(0.35, 0), front, F)
check('crawl right: one node per bar passed (0.6 of the way)', path == [(0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0)],
      path)
jg.crawl(path, scr(0.1, 0), front, F)
check('going back erases the line', path == [(0, 0, 0), (1, 0, 0)], path)
jg.crawl(path, scr(0.1, 0.25), front, F)
check('then up: climbs the vertical bars', path[-1] == (1, 0, 2) and len(path) == 4, path)
check('front view: no step into depth (bars too short on screen)', all(n[1] == 0 for n in path))

path = [(0, 0, 0)]
jg.crawl(path, scr(0.3, 0.3), front, F, jg.WITH_45)
check('45 degrees: a diagonal drag goes across the cells', path == [(0, 0, 0), (1, 0, 1), (2, 0, 2), (3, 0, 3)], path)
path = [(0, 0, 0)]
jg.crawl(path, scr(0.3, 0.02), front, F, jg.WITH_45)
check('45 on: a straight drag still goes straight', path == [(0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0)], path)
path = [(0, 0, 0)]
jg.crawl(path, scr(0.2, 0.0), front, F, jg.WITH_45)
jg.crawl(path, scr(0.4, 0.2), front, F, jg.WITH_45)
check('straight then 45: the turn shows in the points', len(jg.path_points(F, path)) == 3, path)
check('45 degree bars: 12, two axes each', len(jg.DIAGONALS) == 12 and all(sum(map(abs, o)) == 2 for o in jg.DIAGONALS))
ang = lambda co: Vector((500 + (co.x - 0.6 * co.y) * 1000, 500 + (co.z - 0.4 * co.y) * 1000))
path = [(0, 0, 0)]
jg.crawl(path, ang(Vector((0, 0.3, 0))), ang, F)
check('angled view: dragging along the depth bars climbs in depth', path[-1] == (0, 3, 0), path)

check('wheel: away / toward along the bars most along the view',
      jg.depth_offset(F, Vector((0, 1, 0)), False) == (0, 1, 0)
      and jg.depth_offset(F, Vector((0, 1, 0)), True) == (0, -1, 0)
      and jg.depth_offset(F, Vector((0.2, -0.1, -0.97)), False) == (0, 0, -1))

sq = [(0, 0, 0), (1, 0, 0), (2, 0, 0), (2, 0, 1), (2, 0, 2), (1, 0, 2), (0, 0, 2), (0, 0, 1), (0, 0, 0)]
p0 = jg.path_points(F, sq, closed=True)
check('magnet 1, corner 0: just the corners of the bars', len(p0) == 4, [tuple(round(c, 3) for c in p) for p in p0])
p1 = jg.path_points(F, sq, corner=1.0, closed=True)
mid = p1[1]
check('corner 1: each turn becomes a rounded arc (3 points, the middle cut in)', len(p1) == 12
      and 0.0 < mid.x < 0.1 and 0.0 < mid.z < 0.1, [tuple(round(c, 3) for c in p) for p in p1[:3]])
raw = [Vector((0.05 * i, 0, 0.03)) for i in range(5)]
pm = jg.path_points(F, [(0, 0, 0), (1, 0, 0), (2, 0, 0)], raw=raw, magnet=0.5)
check('magnet 0.5: half way between the bars and the free stroke', all(abs(p.z - 0.015) < 1e-6 for p in pm), [p.z for p in pm])

check('flat loop detected', jg.planar_axis(sq) == 1 and jg.planar_axis([(0, 0, 0), (1, 0, 0), (1, 1, 1)]) is None)
l1, n1 = jg.lattice_lines((0, 0, 0))
l2, n2 = jg.lattice_lines((500, -40, 9000))
check('the drawn lattice is a small block wherever you are (light)', len(n1) == len(n2) < 100 and len(l1) == len(l2) < 250,
      (len(n1), len(l1)))
d = jg.draw_data(F, (0, 0, 0), sq[:3], p0, True)
check('45 on: 12 faint orange half bars are drawn too', len(d[7]) == 24)
check('draw data: bars in pairs with a colour each', len(d[0]) == len(d[1]) and len(d[0]) % 2 == 0 and len(d[2]) == len(n1))
ax = jg.axis_bars(F, (2, 0, 1))
ends = {tuple(round(c, 6) for c in ax[i + 1]) for i in range(0, len(ax), 2)}
check('orange X / Y / Z: the 6 bars out of the node you are on', len(ax) == 12
      and all(tuple(round(c, 6) for c in ax[i]) == (0.2, 0.0, 0.1) for i in range(0, 12, 2))
      and (0.3, 0.0, 0.1) in ends and (0.2, -0.1, 0.1) in ends and (0.2, 0.0, 0.2) in ends, sorted(ends))


def run(nodes, **kw):
    before = set(bpy.data.objects)
    res = bpy.ops.mch.gym_draw('EXEC_DEFAULT', nodes=json.dumps([list(n) for n in nodes]), frame_step=0.1,
                               view_dir=(0, 1, 0), **kw)
    return res, [o for o in bpy.data.objects if o not in before]


res, new = run([(0, 0, 0), (1, 0, 0), (2, 0, 0), (2, 0, 1), (2, 1, 1)])
tube = new[0] if new else None
check('open line = a live tube along the bars', res == {'FINISHED'} and tube is not None and tube.mch_tube.live
      and len(tube.data.vertices) > 0 and tube.mch_tube.spline == 'LINEAR', (res, new))
check('tube thickness = Thickness x spacing', tube is not None and abs(tube.mch_tube.radius - 0.015) < 1e-6)
res, new = run([(0, 0, 0), (1, 0, 0), (2, 0, 0), (2, 0, 1)], corner=0.6, magnet=0.8)
check('rounded / free line = a smooth tube', res == {'FINISHED'} and new and new[0].mch_tube.spline == 'SMOOTH')
res, new = run(sq)
base = new[0] if new else None
check('closed flat loop = a live Base Mesh', res == {'FINISHED'} and base is not None and base.mch_base.live
      and len(base.data.polygons) > 0, (res, new))
if base is not None:
    xs = [(base.matrix_world @ v.co) for v in base.data.vertices]
    check('Base Mesh sits on the loop (0.2 x 0.2 on the X/Z layer) and grows toward the viewer (-Y)',
          abs(max(v.x for v in xs) - min(v.x for v in xs) - 0.2) < 1e-3 and min(v.y for v in xs) < -1e-4
          and max(v.y for v in xs) < 1e-4, (min(v.y for v in xs), max(v.y for v in xs)))
res, new = run(sq, make='TUBE')
check('Make = Tube: a closed loop tube', res == {'FINISHED'} and new and new[0].mch_tube.closed)
res, new = run([(0, 0, 0)])
check('a single node makes nothing (scene untouched)', res == {'CANCELLED'} and not new)

# Follow Body: the lattice sticks to a body, the line wraps round it
from mathutils.bvhtree import BVHTree
bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=1.0, location=(0, 0, 0))
body = C.active_object
body.name = 'GymBody'
bvh = jg.body_bvh(C, body, True)
FB = (Vector((0, 0, 0)), Matrix.Identity(3), 0.1, jg.Body(bvh, 0.05, body.name))
pn = jg.node_world(FB, (0, 0, 15))
check('Follow Body: a node sits on the body, lifted by the offset', abs(pn.length - 1.05) < 0.01, pn.length)
arc = [(0, j, 12) for j in range(-8, 9)]
wp = jg.path_points(FB, arc)
rr = [p.length for p in wp]
check('the line is laid on the body in short pieces (wraps the curve, never through it)',
      len(wp) > len(jg.corners_only([jg.node_world(FB, n) for n in arc])) and min(rr) > 1.03 and max(rr) < 1.07,
      (len(wp), min(rr), max(rr)))
res, new = run(arc, body=body.name, lift=0.5)
tb = new[0] if new else None
if tb is not None:
    vr = [(tb.matrix_world @ v.co).length for v in tb.data.vertices]
check('Follow Body tube: wraps the body without sinking into it', res == {'FINISHED'} and tb is not None
      and min(vr) > 1.0 and max(vr) < 1.12, (res, min(vr) if tb else None, max(vr) if tb else None))
res2, new2 = run(arc, body=body.name, lift=3.0)
if new2:
    vr2 = [(new2[0].matrix_world @ v.co).length for v in new2[0].data.vertices]
check('Lift (F9 / wheel): further off the body', res2 == {'FINISHED'} and new2 and min(vr2) > 1.25, min(vr2) if new2 else None)
ring = [(i, 0, k) for i, k in [(12, 0), (12, 12), (0, 12), (-12, 12), (-12, 0), (-12, -12), (0, -12), (12, -12), (12, 0)]]
res, new = run(ring, body=body.name, lift=0.5)
check('closed loop on a body = a closed tube round it (not a flat Base Mesh)', res == {'FINISHED'} and new
      and getattr(new[0], 'mch_tube', None) is not None and new[0].mch_tube.closed)
check('Follow Body is on by default', C.scene.mch_gym.follow_body is True)
check('tool keymap: drag draws, mouse move shows the bars, R turns',
      {k[0] for k in jg.MCH_TOOL_jungle_gym.bl_keymap} == {'mch.gym_draw', 'mch.gym_hover', 'mch.gym_turn'})
check('45 degrees is on by default', C.scene.mch_gym.diagonals is True)
st = C.scene.mch_gym
bpy.ops.mch.gym_turn(angle=math.radians(15))
check('R turns the bars 15 degrees', abs(math.degrees(st.turn) - 15) < 1e-4)
try:
    mecha_lab.unregister()
    mecha_lab.register()
    ok = hasattr(bpy.ops.mch, 'gym_draw') and hasattr(C.scene, 'mch_gym')
except Exception as e:          # noqa: BLE001
    ok = repr(e)
check('unregister / register again', ok is True, ok)
summary()
