"""0.24.20 Base Mesh / Creature Base Mesh Bend: a made (live) shape bends along its main axis - Bend Up / Down
(both ends rise or drop) and Bend Sideways (a banana seen from above), Bend Direction turns the axis.
Bend Style Band = an even arc, Angle = a sharp mitred fold (both sides straight, Corner Round rounds its outer
tip); Bend Position moves the bend."""
import math

from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Quaternion

import mecha_lab
from mecha_lab import base_mesh as bm_mod, core_geometry as cg

TOP = cg.OrthoProjector(Quaternion())                  # 100 px = 1 unit
C = bpy.context
STRIP = [(300, 460), (700, 460), (700, 540), (300, 540)]      # 4 x 0.8, long along X


def make(tool, profile):
    C.scene.mch_settings.mch_active_tool = tool
    s = C.scene.mch_cbase if tool == 'CBASE' else C.scene.mch_base
    s.profile = profile
    if tool == 'BASE':
        s.sketch = False
    before = set(bpy.data.objects)
    bm_mod.perform_base(C, [STRIP], TOP)
    new = [o for o in bpy.data.objects if o not in before]
    return new[0] if len(new) == 1 else None


def world_z(ob):
    return [(ob.matrix_world @ v.co) for v in ob.data.vertices]


mecha_lab.register()

# pure helpers
check('bend_coords: no bend = same point', bm_mod.bend_coords(0.3, 0.1, 0.2, 1.0, 0.0, 0.0) == (0.3, 0.1, 0.2))
u, w, z = bm_mod.bend_coords(1.0, 0.0, 0.0, 1.0, math.pi, 0.0)
r = 2.0 / math.pi
check('bend_coords: 180 deg up turns the end straight up (a half circle)', abs(u - r) < 1e-9 and abs(z - r) < 1e-9,
      (u, z))
d, _c = bm_mod.bend_axis_dir([([(0, 0), (4, 0), (4, 1), (0, 1)], [])])
check('bend axis = the long side of the outline', abs(abs(d[0]) - 1.0) < 1e-6, d)

for tool, profile in (('BASE', 'FLAT'), ('BASE', 'BEVEL'), ('BASE', 'DOME'), ('CBASE', 'PUFF')):
    fresh()
    C.scene.cursor.location = (0, 0, 0)
    ob = make(tool, profile)
    check(f'{profile}: made', ob is not None)
    if ob is None:
        continue
    p = ob.mch_base
    n0 = len(ob.data.vertices)
    pts = world_z(ob)
    z0 = max(q.z for q in pts) - min(q.z for q in pts)
    y0 = max(q.y for q in pts) - min(q.y for q in pts)
    p.bend_up = math.radians(90)
    pts = world_z(ob)
    ends = [q.z for q in pts if abs(q.x) > 1.6]
    mid = [q.z for q in pts if abs(q.x) < 0.2]
    check(f'{profile}: Bend Up lifts both ends', p.last_error == '' and ends and mid and min(ends) > min(mid) + 0.3,
          (p.last_error, round(min(ends or [0]), 3), round(min(mid or [0]), 3)))
    check(f'{profile}: bent shape stays closed', non_manifold(ob) == 0, non_manifold(ob))
    p.bend_up = math.radians(-90)
    pts = world_z(ob)
    ends = [q.z for q in pts if abs(q.x) > 1.6]
    mid = [q.z for q in pts if abs(q.x) < 0.2]
    check(f'{profile}: Bend Down drops both ends', ends and mid and max(ends) < max(mid) - 0.3)
    p.bend_up = 0.0
    p.bend_side = math.radians(90)
    pts = world_z(ob)
    z1 = max(q.z for q in pts) - min(q.z for q in pts)
    y1 = max(q.y for q in pts) - min(q.y for q in pts)
    check(f'{profile}: Bend Sideways curves it in plan, thickness unchanged',
          y1 > y0 + 0.3 and abs(z1 - z0) < 1e-3 * max(1.0, z0) + 1e-4, (round(y0, 3), round(y1, 3), z0, z1))
    check(f'{profile}: sideways bent shape stays closed', non_manifold(ob) == 0)
    p.bend_side = 0.0
    check(f'{profile}: bend back to 0 = the straight shape again', len(ob.data.vertices) == n0,
          (n0, len(ob.data.vertices)))

# Angle: a sharp fold
a = math.radians(30)
l0 = bm_mod._fold(1e-9, 0.3, 0.1, a)
r0 = bm_mod._fold(-1e-9, 0.3, 0.1, a)
check('Angle fold: both sides meet on the joint (no gap)', abs(l0[0] - r0[0]) < 1e-6 and abs(l0[1] - r0[1]) < 1e-6,
      (l0, r0))
q1, q2, q3 = (bm_mod._fold(s_, 0.3, 0.1, a) for s_ in (0.5, 1.0, 2.0))
slope = lambda p1, p2: (p2[1] - p1[1]) / (p2[0] - p1[0])
check('Angle fold: one side stays straight at the fold angle', abs(slope(q1, q2) - slope(q2, q3)) < 1e-9
      and abs(slope(q1, q2) - math.tan(a)) < 1e-9)
# Corner Round: the outer tip of the fold is rounded, the rest is the sharp fold
a, rng, rho = math.radians(45), (0.0, 0.2), 0.06
t = bm_mod.fold_tangent(rho, a)
check('Corner Round 0 = the sharp fold', bm_mod.fold_round(0.5, 0.0, 0.1, a, rng, 0.0) == bm_mod._fold(0.5, 0.0, 0.1, a))
check('Corner Round: past the round nothing changes', bm_mod.fold_round(t + 0.01, 0.0, 0.1, a, rng, rho)
      == bm_mod._fold(t + 0.01, 0.0, 0.1, a))
e0, e1 = bm_mod.fold_round(t - 1e-9, 0.0, 0.1, a, rng, rho), bm_mod._fold(t, 0.0, 0.1, a)
check('Corner Round: starts smoothly where the round begins', math.dist(e0, e1) < 1e-6, (e0, e1))
sharp, rounded = bm_mod._fold(0.0, 0.0, 0.1, a), bm_mod.fold_round(0.0, 0.0, 0.1, a, rng, rho)
check('Corner Round: the outer tip moves in (rounded off)', abs(rounded[0]) < 1e-9 and rounded[1] > sharp[1] + 0.005,
      (sharp, rounded))
check('Corner Round: the inner face stays sharp', bm_mod.fold_round(0.0, 0.2, 0.1, a, rng, rho)
      == bm_mod._fold(0.0, 0.2, 0.1, a))
l_, r_ = bm_mod.fold_round(-0.01, 0.0, 0.1, a, rng, rho), bm_mod.fold_round(0.01, 0.0, 0.1, a, rng, rho)
check('Corner Round: both sides of the round match', abs(l_[0] + r_[0]) < 1e-9 and abs(l_[1] - r_[1]) < 1e-9)
for tool, profile in (('BASE', 'FLAT'), ('BASE', 'BEVEL'), ('CBASE', 'PUFF')):
    fresh()
    C.scene.cursor.location = (0, 0, 0)
    ob = make(tool, profile)
    if ob is None:
        check(f'{profile} Angle: made', False)
        continue
    p = ob.mch_base
    p.bend_style = 'ANGLE'
    p.bend_up = math.radians(90)
    pts = world_z(ob)
    top = sorted((q for q in pts if q.x > 0.4), key=lambda q: q.x)
    top_z = {}
    for q in top:                              # highest point per x column: the top edge of one straight side
        k = round(q.x, 2)
        top_z[k] = max(top_z.get(k, -9), q.z)
    ks = sorted(top_z)
    straight = profile != 'FLAT' or all(abs((top_z[ks[i + 1]] - top_z[ks[i]]) / max(ks[i + 1] - ks[i], 1e-9) - 1.0) < 0.05
                                        for i in range(len(ks) - 1) if ks[i + 1] - ks[i] > 0.05)
    ends = [q.z for q in pts if abs(q.x) > 1.4]
    mid = [q.z for q in pts if abs(q.x) < 0.1]
    check(f'{profile} Angle: ends lift, closed', p.last_error == '' and min(ends) > min(mid) + 0.5
          and non_manifold(ob) == 0, (p.last_error, non_manifold(ob)))
    check(f'{profile} Angle: the side past the fold is straight (45 deg each side)', straight)
    p.bend_up = 0.0
    p.bend_side = math.radians(60)
    check(f'{profile} Angle sideways: closed', p.last_error == '' and non_manifold(ob) == 0)
    p.bend_round = 1.0
    check(f'{profile} Angle sideways, full Corner Round: closed', p.last_error == '' and non_manifold(ob) == 0)
    p.bend_side, p.bend_up = 0.0, math.radians(-120)
    check(f'{profile} Angle down, full Corner Round: closed', p.last_error == '' and non_manifold(ob) == 0)
    p.bend_up, p.bend_round = 0.0, 0.3
    p.bend_side = 0.0
fresh()
ob = make('BASE', 'FLAT')
p = ob.mch_base
p.bend_style, p.bend_up = 'ANGLE', math.radians(90)
pts = world_z(ob)
low0 = min(pts, key=lambda q: q.z).x
p.bend_pos = 0.5
pts = world_z(ob)
low1 = min(pts, key=lambda q: q.z).x
check('Bend Position moves the fold along the length', low1 > low0 + 0.6, (round(low0, 3), round(low1, 3)))

fresh()
ob = make('BASE', 'FLAT')
check('new shapes start straight', ob is not None and ob.mch_base.bend_up == 0.0 and ob.mch_base.bend_side == 0.0)
summary()
