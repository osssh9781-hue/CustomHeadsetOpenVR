"""0.13.2 armor presets: Curved Plate profile + Shoulder/Knee, Upper Arm/Thigh,
Forearm/Shin, Torso, Helmet."""
import math
import sys

from _harness import bpy, bmesh, check, fresh, non_manifold, summary

import mecha_lab
from mecha_lab import station_primitive as sp, station_sweep as ss

S = ss.station
p = S(width_l=0.1, width_r=0.1, height_top=0.06, height_bot=0.01, thick_l=1.0, thick_r=1.0, ridge_h=0.0)
lp = ss.profile_loop('ARC', p, 8)
check('Curved Plate: same vertex count as the other profiles (can morph)',
      len(lp) == len(ss.profile_loop('ROUNDED', p, 8)))
n_top = len(lp) // 2
crown = max(y for x, y in lp)
check('Curved Plate: crown height at the centre, edges at the base', abs(crown - 0.06) < 1e-9 and
      abs(min(y for x, y in lp[:n_top])) < 1e-9)
R = (0.1 ** 2 + 0.06 ** 2) / (2 * 0.06)
inner = lp[len(lp) - n_top:]
d = [abs(math.hypot(x, y - (0.06 - R)) - (R - 0.01)) for x, y in inner]
check('Curved Plate: even thickness (inner surface = outer arc minus the thickness)', max(d) < 1e-6, max(d))
lp2 = ss.profile_loop('ARC', dict(p, height_top=0.16), 8)
check('tall crown (helmet) stays valid', max(y for x, y in lp2) > 0.159)
for name in ss.ARMOR_PRESETS:
    r = ss.build(ss.preset(name))
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in r['verts']]
    for f in r['faces']:
        try:
            bm.faces.new([vs[i] for i in f])
        except ValueError:
            pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=1e-7)
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    xs = [v.co.x for v in bm.verts]
    check(f'armor {name}: closed shell, no warnings, human-scale size ({max(xs) - min(xs):.2f} m wide)',
          nm == 0 and not r['warnings'] and 0.05 < max(xs) - min(xs) < 0.6, (nm, r['warnings']))
    bm.free()
fresh()
mecha_lab.register()
C = bpy.context
for key, _l, _d in sp.ARMOR_ITEMS:
    res = bpy.ops.mch.station_create(preset=key)
    ob = C.active_object
    check(f'Blender: {key} created live, closed', res == {'FINISHED'} and sp.is_live(ob) and non_manifold(ob) == 0)
left0 = min(v.co.x for v in ob.data.vertices)
ob.mch_station.stations[2].width_l = 0.2
check('armor preset stays editable (left width 0.12 -> 0.2 widens the left side)',
      min(v.co.x for v in ob.data.vertices) < left0 - 0.05, (left0, min(v.co.x for v in ob.data.vertices)))
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
