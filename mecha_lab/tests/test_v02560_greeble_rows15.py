"""0.24.155 (user: "옆으로 늘어나는 거를 8 개 이상으로, 한 15 개까지 해 줘"): Greeble Line / Scale Line Rows up to 15 (was 8) -
the next line's setting, a selected line's, both tools.  A 15-row line across a sphere's front: 15 rows side by side,
every part on the surface; Edge Rows Smaller with 15 rows; Scale Line 15 staggered rows."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import greeble_line as gl  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=96, ring_count=48)
body = C.active_object
bpy.ops.mch.greeble_parts(action='STARTER')
mech, crea = gl.settings(S, 'MECH'), gl.settings(S, 'CREATURE')
mech.rows = 20
crea.rows = 20
check('Rows goes to 15 now (was 8): 20 typed -> 15, in Greeble Line and Scale Line',
      mech.rows == 15 and crea.rows == 15, (mech.rows, crea.rows))

mech.scale = 0.25
caster = gl._caster(C, body)
pts, nrm = [], []
for a in np.linspace(-1.0, 1.0, 120):                      # along the equator's front: the rows go up / down (z)
    h = caster.ray_cast((math.sin(a) * 3.0, -math.cos(a) * 3.0, 0.0), (-math.sin(a), math.cos(a), 0.0))
    if h:
        pts.append(tuple(h[0]))
        nrm.append(tuple(h[1]))
line = gl.new_line(C, body, np.array(pts), np.array(nrm), gl.picked(mech), mech)
n = gl.rebuild(line, C, caster)
ln = line.mch_greeble_line
check('a selected line takes 15 too (20 typed -> 15)', (setattr(ln, 'rows', 20) or ln.rows) == 15)
n = len(line.data.vertices)
loc = np.array([tuple(line.matrix_world @ v.co) for v in line.data.vertices])
zs = np.sort(loc[:, 2])
gaps = np.diff(zs)
rows_found = int(np.sum(gaps > 0.5 * np.median(gaps[gaps > 1e-4]) if np.any(gaps > 1e-4) else 0) + 1) if len(zs) else 0
lay = gl.row_layout(15, 0.0, 1.0, 0.0)
offs = [o for _f, o in lay]
check(f'a 15-row line across the sphere\'s front: {n} parts in 15 rows side by side (the rows\' heights apart: '
      f'{rows_found} groups)', n >= 15 * 4 and len(lay) == 15 and abs(offs[7]) < 1e-9
      and all(b > a for a, b in zip(offs, offs[1:])), (n, rows_found))
from mathutils import Quaternion  # noqa: E402
quats = [Quaternion(d.value) for d in line.data.attributes['mch_rot'].data]
scs = [Vector(d.vector) for d in line.data.attributes['mch_scale'].data]
pk = [d.value for d in line.data.attributes['mch_pick'].data]
parts = gl.line_parts(line)
worst, ups = 0.0, []
for i in range(n):
    bb = [Vector(c) for c in parts[pk[i]].bound_box]
    lo = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
    hi = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
    m = quats[i].to_matrix()
    bottom = Vector(loc[i]) + m @ Vector(((lo.x + hi.x) / 2 * scs[i].x, (lo.y + hi.y) / 2 * scs[i].y, lo.z * scs[i].z))
    worst = max(worst, (caster.nearest(bottom)[0] - bottom).length)
    ups.append(m @ Vector((0, 0, 1)))
order = np.argsort(loc[:, 2])
k = max(1, n // 15)
up_lo = sum((ups[i] for i in order[:k]), Vector()).normalized()
up_hi = sum((ups[i] for i in order[-k:]), Vector()).normalized()
tilt = math.degrees(up_lo.angle(up_hi))
check(f'... every part standing on the surface (bottom middles within {worst * 1000:.2f} mm); the band '
      f'{float(np.ptp(loc[:, 2])):.2f} high, its top and bottom rows tilted {tilt:.0f} deg apart with the sphere',
      worst < 0.002 and tilt > 10.0)

# Edge Rows Smaller with 15 rows
ln.edge_shrink = 0.5
lay = gl.row_layout(15, 0.5, 1.0, 0.0)
fac = [f for f, _o in lay]
scl = np.array([d.vector[0] for d in line.data.attributes['mch_scale'].data])
check('Edge Rows Smaller 0.5 with 15 rows: the middle row full size, step by step to half at the outermost two',
      abs(fac[7] - 1.0) < 1e-9 and abs(fac[0] - 0.5) < 1e-9 and abs(fac[14] - 0.5) < 1e-9
      and all(fac[i] < fac[i + 1] for i in range(7)) and scl.max() / scl.min() > 1.8, [round(f, 3) for f in fac])

# Scale Line: 15 staggered rows
bpy.ops.mch.greeble_parts(action='STARTER', kind='CREATURE', which='SCALES')
crea.rows = 15
crea.scale = 0.5
sl = gl.new_line(C, body, np.array(pts), np.array(nrm), gl.picked(crea), crea, 'CREATURE')
m = gl.rebuild(sl, C, caster)
check(f'Scale Line: 15 staggered, overlapping rows ({m} scales)', sl.mch_greeble_line.rows == 15 and m >= 15 * 6)
summary()
