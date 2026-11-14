"""0.24.167 (user, on the 0.24.166 scales with their rounded wall: "이건 너무 인공물 같잖아"): Scale Line's built-in
scales organic - a pebble's round section (no wall, no flat top) thicker toward the root, an uneven outline, the line
round it a soft crease of uneven depth that fades out in places, no dent in the middle.  0.24.168 (user, circling the
lines on the scales: "저렇게 단차가 안 심했으면 좋겠어 - 두께 말고 이 라인"): the line a soft wide dip - no step, no
terrace, no swell beside it.  Measured on the meshes."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
import bmesh  # noqa: E402  (after bpy)

import mecha_lab
from mecha_lab import greeble_line as gl  # noqa: E402

fresh()
mecha_lab.register()
meshes = dict(gl._scale_meshes())
names = ['Scale Round', 'Scale Pointed', 'Scale Keeled', 'Scale Hex', 'Scale Scute']
ok_closed = []
for nm in names:
    bm = bmesh.new()
    bm.from_mesh(meshes[nm])
    ok_closed.append(all(e.is_manifold for e in bm.edges) and not any(not v.link_edges for v in bm.verts))
    bm.free()
check('the five built-in scales: closed meshes', all(ok_closed), ok_closed)


def rings(me):
    """The vertices by ring (the mesh is made ring by ring: rim first), as an array per ring."""
    co = np.array([v.co for v in me.vertices])
    return co


r = meshes['Scale Round']
co = rings(r)
seg = 40
rim = co[:seg]                                                    # (the first ring: the outline at the bottom)
ang = np.arctan2(rim[:, 1] / 0.42, rim[:, 0] / 0.5)
rad = np.hypot(rim[:, 0] / 0.5, rim[:, 1] / 0.42)
check(f'the outline uneven, not a drawn ellipse (radius {rad.min():.3f} - {rad.max():.3f} of it)',
      rad.max() - rad.min() > 0.03, (rad.min(), rad.max()))
# the section along the long axis: the root (back, -x) thicker than the tip (+x), a round edge (no wall: the ring
# above the rim is already in from it), the crease a dip before the top
nr = (len(co) - 1) // seg
prof = []
for side, i in (('tip', 0), ('root', seg // 2)):
    zs = [co[k * seg + i, 2] for k in range(nr)] + [co[-1, 2]]
    xs = [abs(co[k * seg + i, 0]) for k in range(nr)] + [0.0]
    prof.append((side, np.array(xs), np.array(zs)))
(_s1, xt, zt), (_s2, xr, zr) = prof
mid_t = float(np.interp(0.25, xt[::-1], zt[::-1]))
mid_r = float(np.interp(0.25, xr[::-1], zr[::-1]))
check(f'thicker toward the root: halfway out {mid_r * 1000:.0f} (root) vs {mid_t * 1000:.0f} (tip) thousandths', mid_r > mid_t * 1.1,
      (mid_r, mid_t))
wall = abs(xt[1] - xt[0]) < 1e-9 and zt[1] > 0
check(f'a round edge, no wall: the ring above the outline already {abs(xt[0] - xt[1]) * 1000:.1f} thousandths in',
      not wall and zt[1] > 0, (xt[:3], zt[:3]))
dips = [int(((z[1:-1] < z[:-2]) & (z[1:-1] < z[2:])).sum()) for _s, _x, z in prof]
check(f'0.24.168 the line no step: the section rises smoothly to the top - no pit, no terrace (pits: tip {dips[0]}, root '
      f'{dips[1]})', dips == [0, 0], dips)
top = co[-1, 2]
near = co[(nr - 1) * seg:nr * seg]
hi = near[int(np.argmax(near[:, 2]))]
check(f'no dent in the middle: the top {top * 1000:.1f} above the lowest of the ring round it ({near[:, 2].min() * 1000:.1f}); '
      f'the highest toward the root (x {hi[0]:.2f})', top > near[:, 2].min() and hi[0] < 0, (top, near[:, 2].min(), hi[0]))
# the crease uneven: the same scale built without its line - the difference is the crease, angle by angle
import bmesh as _bmesh  # noqa: E402
bm2 = _bmesh.new()
gl._dome(bm2, 0.5, 0.42, 0.12, seg=40, shape=lambda x, y: (x, y * (0.8 + 0.2 * x)), line=0.0,
         edge=0.12 * gl.SCALE_EDGE, organic=11)
co0 = np.array([v.co for v in bm2.verts])
bm2.free()
d = (co[:, 2] - co0[:, 2])[:nr * seg].reshape(nr, seg)
dip = -d.min(0)
check(f'the line there, uneven round the outline: {dip.min() * 1000:.1f} - {dip.max() * 1000:.1f} thousandths deep '
      f'(it fades out in places)', len(co) == len(co0) and dip.max() > 0.004 and dip.min() < 0.35 * dip.max(),
      (dip.min(), dip.max()))
rise = float((co[:, 2] - co0[:, 2]).max())
wide = int((d.min(0) < -0.25 * dip.max()).sum())
span = [int((d[:, i] < -0.25 * dip[i]).sum()) for i in range(seg) if dip[i] > 0.003]
check(f'...a soft dip only: nothing raised beside it (the most it lifts the surface: {rise * 1000:.2f} thousandths), '
      f'spread over {min(span) if span else 0} - {max(span) if span else 0} rings (not a sharp groove)',
      rise < 1e-6 and span and min(span) >= 5, (rise, span[:5] if span else span))

mecha_lab.unregister()
summary()
