"""0.24.151 (user: "인간 바디 + 하이폴리곤으로 테스트"): Greeble Line on a high-poly human body (tools_dev/make_test_human.py,
Subdivision 5: about 0.94 M faces) - ribs across the chest, a line down the belly, one down a thigh, a band round the
upper arm (a closed loop).  The lines are given as points on the body (ray casts from the front / round the arm, as a
drag would give; the real drag: tests/gui/greeble_human_real_window.py).  Timings on this machine's CPU."""
import math
import os
import sys
import time

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools_dev'))
import make_test_human as mth  # noqa: E402

import mecha_lab
from mecha_lab import greeble_line as gl  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
t0 = time.time()
body = mth.build(5)
nf = len(body.data.polygons)
zs = np.empty(len(body.data.vertices) * 3, np.float32)
body.data.vertices.foreach_get('co', zs)
zs = zs.reshape(-1, 3)
check(f'a high-poly human body: {nf:,} faces, {np.ptp(zs[:, 2]):.2f} tall (made in {time.time() - t0:.1f} s)',
      nf > 900000 and 1.6 < np.ptp(zs[:, 2]) < 1.9)
C.view_layer.objects.active = body
body.select_set(True)
bpy.ops.mch.greeble_parts(action='STARTER')
st = gl.settings(S)
st.scale = 0.35
check('Starter Parts sized to the body (about 0.1 long), five in the list',
      len(gl.picked(st)) == 5 and 0.05 < gl.picked(st)[0].scale.x < 0.15, round(gl.picked(st)[0].scale.x, 3))

t0 = time.time()
caster = gl._caster(C, body)
hit0 = caster.ray_cast((0.0, -1.0, 1.3), (0.0, 1.0, 0.0))
t_build = time.time() - t0
t0 = time.time()
again = gl._caster(C, body)
hit1 = again.ray_cast((0.02, -1.0, 1.3), (0.0, 1.0, 0.0))
t_again = time.time() - t0
check(f'the surface for strokes on {nf:,} faces: the first look-up {t_build:.2f} s (Blender builds its search tree), '
      f'the next stroke {t_again * 1000:.1f} ms (the same tree)', hit0 is not None and hit1 is not None
      and t_build < 2.0 and t_again < 0.01)


def front(path, n=90):
    """A line drawn on the body seen from the front: (x, z) points -> rays from in front."""
    pts, nrm = [], []
    for t in np.linspace(0.0, 1.0, n):
        x, z = path(t)
        hit = caster.ray_cast((x, -1.0, z), (0.0, 1.0, 0.0))
        if hit is not None:
            pts.append(tuple(hit[0]))
            nrm.append(tuple(hit[1]))
    return np.array(pts), np.array(nrm)


def ring(c, axis, r, n=120):
    """A band round a limb: a circle about ``axis`` through ``c``, pressed onto the surface (nearest)."""
    a = Vector(axis).normalized()
    u = a.orthogonal().normalized()
    v = a.cross(u)
    pts, nrm = [], []
    for t in np.linspace(0.0, 2 * math.pi, n):
        q = Vector(c) + (u * math.cos(t) + v * math.sin(t)) * r
        loc, nr = caster.nearest(q)
        pts.append(tuple(loc))
        nrm.append(tuple(nr))
    return np.array(pts), np.array(nrm)


strokes = []
for i, z in enumerate(np.arange(1.24, 1.43, 0.035)):                 # ribs across the chest
    strokes.append((f'rib {i + 1}', front(lambda t, z=z: (-0.15 + 0.30 * t, z)), dict(order='RANDOM', rows=2, seed=int(z * 100))))
strokes.append(('belly', front(lambda t: (0.0, 1.05 + 0.35 * t)), dict(order='SEQ', rows=1)))
strokes.append(('thigh', front(lambda t: (0.11, 0.85 - 0.25 * t)), dict(order='RANDOM', rows=3, seed=5)))
sh, el = Vector((0.2, 0.0, 1.44)), Vector((0.33, 0.02, 1.18))
strokes.append(('arm band', ring(sh + (el - sh) * 0.7, el - sh, 0.08), dict(order='SEQ', rows=1)))
lines, times = [], []
for name, (p, n), cfg in strokes:
    for k, v in cfg.items():
        setattr(st, k, v)
    ob = gl.new_line(C, body, p, n, gl.picked(st), st)
    t0 = time.time()
    k = gl.rebuild(ob, C, caster)
    times.append(time.time() - t0)
    lines.append((name, ob, k, p))
counts = {name: k for name, _ob, k, _p in lines}
check(f'{len(lines)} lines drawn on the body, {sum(counts.values())} parts, each line redone in at most '
      f'{max(times) * 1000:.0f} ms', all(k > 0 for k in counts.values()) and max(times) < 0.3, counts)

# every part standing on the body: its bottom middle on the surface, its bottom corners close to it, up = the normal
worst_d, worst_corner, n_parts, ups, corners = 0.0, 0.0, 0, [], []
from mathutils import Quaternion  # noqa: E402
for name, ob, k, _p in lines:
    me = ob.data
    loc = np.array([tuple(v.co) for v in me.vertices])
    quats = [d.value for d in me.attributes['mch_rot'].data]
    scl = [Vector(d.vector) for d in me.attributes['mch_scale'].data]
    pk = [d.value for d in me.attributes['mch_pick'].data]
    parts = gl.line_parts(ob)
    for i in range(len(loc)):
        p = parts[pk[i]]
        bb = [Vector(c) for c in p.bound_box]
        lo = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
        hi = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
        m = Quaternion(quats[i]).to_matrix()

        def at(x, y, z):
            return Vector(loc[i]) + m @ Vector((x * scl[i].x, y * scl[i].y, z * scl[i].z))
        b = at((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z)
        hit, nr = caster.nearest(b)
        worst_d = max(worst_d, (hit - b).length)
        size = max((hi.x - lo.x) * scl[i].x, (hi.y - lo.y) * scl[i].y)
        part_corner = 0.0
        for cx in (lo.x, hi.x):
            for cy in (lo.y, hi.y):
                cpt = at(cx, cy, lo.z)
                cgap = (caster.nearest(cpt)[0] - cpt).length / size
                worst_corner = max(worst_corner, cgap)
                part_corner = max(part_corner, cgap)
        ups.append((m @ Vector((0, 0, 1))).dot(nr))
        corners.append(part_corner)
        n_parts += 1
ups = np.array(ups)
share = float(np.mean(ups > math.cos(math.radians(25))))
corners = np.array(corners)
flat = float(np.mean(corners < 0.15))
check(f'all {n_parts} parts standing on the body: bottom middles within {worst_d * 1000:.2f} mm of the surface',
      worst_d < 0.002)
check(f'... all four bottom corners within 15 % of a part\'s size from the surface for {flat * 100:.1f} % of them (rigid '
      f'parts: across the chest / shoulder crease up to {worst_corner * 100:.0f} %, {worst_corner * 35:.0f} mm on a 35 mm '
      f'part)', flat > 0.9)
check(f'... up = the surface normal within 25 deg for {share * 100:.1f} % of them (the rest sit across the chest / '
      f'shoulder crease: up = the surface under the whole part; worst {math.degrees(math.acos(ups.min())):.0f} deg)',
      share > 0.97)

band = next(ob for name, ob, _k, _p in lines if name == 'arm band')
c = sh + (el - sh) * 0.7
ax = (el - sh).normalized()
u = ax.orthogonal().normalized()
angs = sorted(math.degrees(math.atan2((Vector(v.co) - c).dot(ax.cross(u)), (Vector(v.co) - c).dot(u))) % 360
              for v in band.data.vertices)
gap = max([b - a for a, b in zip(angs, angs[1:])] + [360 - angs[-1] + angs[0]]) if angs else 360
check(f'the band round the upper arm: {len(angs)} parts all the way round (largest gap between them {gap:.0f} deg)',
      len(angs) >= 8 and gap < 60)

# drawing: the line redone as it grows (as the drag does every 50 ms)
p, n = strokes[0][1]
live = gl.new_line(C, body, p[:2], n[:2], gl.picked(st), st)
ts_ = []
for j in range(5, len(p), 5):
    gl.write_stroke(live, p[:j], n[:j])
    t0 = time.time()
    gl.rebuild(live, C, caster)
    ts_.append(time.time() - t0)
check(f'while drawing on {nf:,} faces: each live update {max(ts_) * 1000:.0f} ms at most', max(ts_) < 0.1)

# the body itself untouched; Apply one line
check('the body itself untouched (the lines are its children)', len(body.data.polygons) == nf
      and all(ob.parent is body for _n, ob, _k, _p in lines))
rib = lines[0][1]
for o in C.selected_objects:
    o.select_set(False)
rib.select_set(True)
C.view_layer.objects.active = rib
t0 = time.time()
r = bpy.ops.mch.greeble_apply()
check(f'Apply a line: real parts ({len(rib.data.polygons):,} faces) in {time.time() - t0:.2f} s',
      'FINISHED' in r and not gl.is_line(rib) and len(rib.data.polygons) > 0)

# the body changed (all of it 5 cm forward): the next stroke's surface is the changed one (never out of date)
co = np.empty(len(body.data.vertices) * 3, np.float32)
body.data.vertices.foreach_get('co', co)
co[1::3] -= 0.05
body.data.vertices.foreach_set('co', co)
body.data.update()
C.view_layer.update()
h_new = gl._caster(C, body).ray_cast((0.0, -1.0, 1.3), (0.0, 1.0, 0.0))
check('the body changed (5 cm forward): the next stroke lands on the changed surface',
      h_new is not None and abs((h_new[0].y - hit0[0].y) + 0.05) < 1e-3, (round(hit0[0].y, 4), h_new and round(h_new[0].y, 4)))
summary()
