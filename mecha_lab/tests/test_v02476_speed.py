"""0.24.73 Code review phase 2 (speed / correctness): Quad Patch distances in blocks (R05), Curve Repeat sees every
change (R06), lost hard edges counted (R09), live rebuilds at a steady pace (R10), Merge Flats on big meshes."""
import math
import time

import numpy as np

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import curve_tube as ct, hard_edges as he, live_queue as lq, quad_remesh as qr

mecha_lab.register()
fresh()
C = bpy.context
zb = C.scene.mch_zb

# --- R05: point x segment distances / inside test in blocks ---------------------------------------------------------
rng = np.random.default_rng(7)
pts = rng.uniform(-1, 1, (3000, 2))
ang = np.linspace(0, 2 * math.pi, 401)
ring = np.stack([np.cos(ang), np.sin(ang)], 1) * 0.8
segs = np.stack([ring[:-1], ring[1:]], 1)
full = qr._seg_dist_block(pts, segs)
check('Quad Patch: distances in blocks are exactly the all-at-once ones (a fraction of the memory)',
      np.array_equal(qr._seg_dist(pts, segs), full), float(np.abs(qr._seg_dist(pts, segs) - full).max()))
inside = qr._inside(pts, segs)
want = np.linalg.norm(pts, axis=1) < 0.8
check('... the inside test in blocks agrees with the circle (border points aside)',
      (inside == want)[np.abs(np.linalg.norm(pts, axis=1) - 0.8) > 0.01].all())
try:
    qr._seg_dist(pts, segs[:0])
    empty = ''
except ValueError as ex:
    empty = str(ex)
check('... no outline at all is an error, not a silent infinity', 'no outline' in empty, empty)

# --- R09: hard edges all gone = all lost ---------------------------------------------------------------------------
from mathutils import Vector  # noqa: E402
bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16)
smooth = C.active_object
src_edges = [(Vector((0, 0, 0)), Vector((1, 0, 0))), (Vector((0, 0, 0)), Vector((0, 1, 0)))]
miss = qr._edge_miss(src_edges, smooth.data, 0.1, math.radians(30))
check('Quad quality: a result with none of the source\'s hard edges counts them all lost (it said 0 lost)',
      abs(miss - 20.0) < 1e-6, miss)

# --- R06: Curve Repeat change detection --------------------------------------------------------------------------
bpy.ops.mesh.primitive_grid_add(x_subdivisions=4, y_subdivisions=4)
src = C.active_object
dg = C.evaluated_depsgraph_get()
s0 = ct._source_sig(src, dg)
v = src.data.vertices
v[6].co.z += 0.1
v[12].co.z -= 0.1                                   # (same summed size, same bounds as before)
src.data.update()
dg = C.evaluated_depsgraph_get()
check('Curve Repeat: one point up and another down by the same amount is a change (the summed size missed it)',
      ct._source_sig(src, dg) != s0)

# --- R10: live rebuild queue ----------------------------------------------------------------------------------------
ran = []
lq.queue(('t', 'a'), lambda: ran.append('a'))
check('Live rebuilds: without a window they run at once (tests / command line)', ran == ['a'])
lq._PENDING[('t', 'b')] = lambda: ran.append('b')
lq._PENDING[('t', 'c')] = lambda: ran.append('c')
lq.drop()
check('... Ctrl+Z / file load drop what is waiting', not lq._PENDING and ran == ['a'])
lq._PENDING[('t', 'b')] = lambda: ran.append('b')
lq._PENDING[('t', 'b')] = lambda: ran.append('b2')          # (a second update replaces the first: one rebuild)
lq.flush()
check('... a burst of updates for one part is one rebuild with the last value; flush runs it now',
      ran == ['a', 'b2'] and not lq._PENDING, ran)
lq._COST[('t', 'x')] = 0.2
check('... the pace follows the rebuild cost (twice its time, 0.05 .. 0.5 s)',
      abs(lq._interval(('t', 'x')) - 0.4) < 1e-9 and lq._interval(('t', 'new')) == lq.MIN_INTERVAL)
check('... Base Mesh and Face Extract go through it', 'live_queue' in open(
    mecha_lab.__path__[0] + '/base_mesh.py').read() and 'live_queue' in open(mecha_lab.__path__[0] + '/face_extract.py').read())

# --- Merge Flats on a big triangle mesh ------------------------------------------------------------------------------
bpy.ops.mesh.primitive_cube_add()
cube = C.active_object
m = cube.modifiers.new('s', 'SUBSURF')
m.subdivision_type = 'SIMPLE'
m.levels = 6
with C.temp_override(object=cube, active_object=cube):
    bpy.ops.object.modifier_apply(modifier='s')
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.quads_convert_to_tris()
bpy.ops.object.mode_set(mode='OBJECT')
zb.he_merge = True
zb.he_angle = math.radians(30)
t = time.perf_counter()
n, f0, f1 = he.find(cube, zb)
dt = time.perf_counter() - t
co = np.array([v.co for v in cube.data.vertices])
check('Find Edges + Merge Flats on 49k triangles: the flat points emptied by the engine first (dissolve alone: ~7 s '
      'here, ~30 s at 196k), the same result - a box of 6 faces, 12 hard edges', f1 == 6 and n == 12 and dt < 5.0
      and np.allclose(np.abs(co), 1.0), (f0, f1, n, round(dt, 2)))

summary()
