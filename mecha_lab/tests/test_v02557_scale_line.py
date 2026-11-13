"""0.24.151 (user: "그리블 라인을 크리쳐 탭도 만들어 줘, 비늘 전용이나 디테일 전용으로 만들자"): Scale Line - Greeble Line's
creature twin in the Creature tools, with its own parts list and settings: Scale Parts (five scale shapes, laid
overlapping in staggered rows with a slight lean) or Detail Parts (spike, bump, nub, fin, warts, scattered).  On the
high-poly test human (0.94 M faces); the lines given as points on it (a real drag: tests/gui/scale_line_real_window.py)."""
import math
import os
import sys

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Quaternion, Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools_dev'))
import make_test_human as mth  # noqa: E402

import mecha_lab
from mecha_lab import greeble_line as gl, tool_state as ts, ui_tool_settings as uts  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
check('the tool: Scale Line in the Creature tools, its icon, its window (the creature kind)',
      'CGREEBLE' in ts.TOOL_BY_ID and 'CGREEBLE' in dict(ts.TOOL_GROUPS)['Creature']
      and os.path.isfile(os.path.join(os.path.dirname(gl.__file__), 'icons', 'cgreeble.png'))
      and uts.DRAWERS.get('CGREEBLE') is not None and hasattr(S, 'mch_cgreeble'))
body = mth.build(5)
C.view_layer.objects.active = body
body.select_set(True)
mech, crea = gl.settings(S, 'MECH'), gl.settings(S, 'CREATURE')
bpy.ops.mch.greeble_parts(action='STARTER')                     # (Greeble Line's machine parts)
r = bpy.ops.mch.greeble_parts(action='STARTER', kind='CREATURE', which='SCALES')
scales = gl.picked(crea)
check('Scale Parts: five scale shapes beside the body (sized to it, half the machine parts), Scale Line\'s own list',
      'FINISHED' in r and [o.name.split('.')[0] for o in scales] == ['Scale Round', 'Scale Pointed', 'Scale Keeled',
                                                                     'Scale Hex', 'Scale Scute']
      and len(gl.picked(mech)) == 5 and not set(scales) & set(gl.picked(mech))
      and abs(scales[0].scale.x - gl.picked(mech)[0].scale.x * 0.5) < 1e-6, [o.name for o in scales])
check('... with the scale settings: overlap (Gap -0.3), 3 staggered rows, a 10 deg lean, sunk a quarter',
      abs(crea.gap + 0.3) < 1e-6 and crea.rows == 3 and crea.stagger and abs(math.degrees(crea.tilt) - 10) < 1e-3
      and abs(crea.sink - 0.25) < 1e-6 and mech.rows == 1 and not mech.stagger)

caster = gl._caster(C, body)
pts, nrm = [], []
for x in np.linspace(-0.12, 0.12, 80):                       # across the chest
    h = caster.ray_cast((x, -1.0, 1.32), (0.0, 1.0, 0.0))
    if h:
        pts.append(tuple(h[0]))
        nrm.append(tuple(h[1]))
pts, nrm = np.array(pts), np.array(nrm)
line = gl.new_line(C, body, pts, nrm, scales, crea, 'CREATURE')
n = gl.rebuild(line, C, caster)
ln = line.mch_greeble_line
check(f'a Scale Line across the chest (0.24 m): {n} scales in 3 rows, its kind CREATURE, named Scale Line', n >= 18
      and ln.kind == 'CREATURE' and line.name.startswith('Scale Line'))

me = line.data
loc = np.array([tuple(v.co) for v in me.vertices])
q = [Quaternion(d.value) for d in me.attributes['mch_rot'].data]
pk = [d.value for d in me.attributes['mch_pick'].data]
# rows: the across offset of each scale from the line (sign of the side) -> 3 rows; along positions per row
t_dir = Vector(tuple(pts[-1] - pts[0])).normalized()
along = loc @ np.array(tuple(t_dir))
up = Vector((0, 0, 1))
across = np.array([(Vector(p) - Vector(tuple(pts[0]))).dot(up) for p in loc])
rows = np.digitize(across, np.quantile(across, [1 / 3, 2 / 3]))
row_pos = [np.sort(along[rows == k]) for k in range(3)]
steps = [float(np.median(np.diff(rp))) for rp in row_pos if len(rp) > 2]
L_mean = float(np.mean(steps)) / 0.7                          # (Gap -0.3: a step is 0.7 x a scale's length)
shift = abs(float(np.median(row_pos[1][:5] - row_pos[0][:5])))
check('... overlapping: each row\'s scales 0.7 of a scale\'s length apart (Gap -0.3)', len(steps) == 3
      and max(steps) / min(steps) < 1.25, [round(s_, 4) for s_ in steps])
check('... staggered: the middle row half a step along from the others', abs(shift - 0.5 * np.mean(steps)) <
      0.25 * np.mean(steps), (round(shift, 4), round(float(np.mean(steps)), 4)))
leans = []
for i in range(len(loc)):
    hit = caster.nearest(Vector(loc[i]))
    leans.append(math.degrees(math.acos(max(-1.0, min(1.0, (q[i].to_matrix() @ Vector((0, 0, 1))).dot(hit[1]))))))
check(f'... each scale leaning about 10 deg (median {np.median(leans):.1f}) - shingles', 6.0 < np.median(leans) < 16.0)

# changing it remembers into Scale Line's settings, not Greeble Line's
for o in C.selected_objects:
    o.select_set(False)
line.select_set(True)
C.view_layer.objects.active = line
ln.rows = 2
check('the line changed (Rows 2): Scale Line\'s next line has Rows 2, Greeble Line\'s untouched',
      crea.rows == 2 and mech.rows == 1 and len(line.data.vertices) < n)

# Detail Parts: their own settings, scattered
r = bpy.ops.mch.greeble_parts(action='STARTER', kind='CREATURE', which='DETAILS')
det = gl.picked(crea)
check('Detail Parts: spike, bump, nub, fin, warts - ticked instead of the scales; scattered settings (Gap 0.5, '
      'any turn, size varied)', 'FINISHED' in r and [o.name.split('.')[0] for o in det] == [
          'Detail Spike', 'Detail Bump', 'Detail Nub', 'Detail Fin', 'Detail Warts']
      and abs(crea.gap - 0.5) < 1e-6 and crea.rows == 1 and not crea.stagger
      and abs(crea.turn_random - math.pi) < 1e-6 and crea.scale_random > 0.3)
pts2, nrm2 = [], []
for z in np.linspace(1.05, 1.42, 80):                        # down the belly
    h = caster.ray_cast((0.0, -1.0, z), (0.0, 1.0, 0.0))
    if h:
        pts2.append(tuple(h[0]))
        nrm2.append(tuple(h[1]))
line2 = gl.new_line(C, body, np.array(pts2), np.array(nrm2), det, crea, 'CREATURE')
n2 = gl.rebuild(line2, C, caster)
worst = max((caster.nearest(Vector(v.co))[0] - Vector(v.co)).length for v in line2.data.vertices)
check(f'a detail line down the belly: {n2} details, every one on the body (origins within {worst * 1000:.1f} mm)',
      n2 > 3 and worst < 0.01)
dg = C.evaluated_depsgraph_get()
inst = [i for i in dg.object_instances if i.is_instance and i.parent and i.parent.original in (line, line2)]
check('both lines are instances of the built-in parts (light until Apply)', len(inst) == len(line.data.vertices) +
      len(line2.data.vertices))
summary()
