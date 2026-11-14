"""0.24.165 (user: "지금 만드는 크리쳐 플레이트에 외곽에 가시 난 버전도 하나 만들면 좋겠다 - 외곽에만 랜덤하게"; asked where:
"Creature Plate 옵션"): Creature Plate's Edge Spikes - spikes along the outline only, at random places, pointing out
from it (Spike Angle up off the body), uneven by Random, another set by Seed; live (the plate's sliders), remembered for
the next plate.  Measured on the plate's mesh (the spikes' faces are tagged)."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Quaternion

import mecha_lab
from mecha_lab import core_geometry as cg, creature_plate as cp  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)        # (looking down: 100 px = 1, (500, 500) = origin)
R = 1.5
LOOP = [[(500 + R * 100 * math.cos(t), 500 + R * 100 * math.sin(t))
         for t in np.linspace(0, 2 * math.pi, 90, endpoint=False)]]

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_plane_add(size=8.0)
ground = C.active_object
st = S.mch_cplate
check('Creature Plate has Edge Spikes (count, length, angle, random, seed), live and remembered',
      {'spikes', 'spike_length', 'spike_angle', 'spike_random', 'spike_seed'} <= set(cp.LIVE_KEYS))


def make(spikes, **kw):
    st.profile = 'PUFF'
    st.spikes = spikes
    for k, v in kw.items():
        setattr(st, k, v)
    for o in C.selected_objects:
        o.select_set(False)
    ground.select_set(True)
    C.view_layer.objects.active = ground
    cp.perform(C, LOOP, TOP)
    return C.active_object


def spikes_of(ob):
    """[(root centre, tip)] of each spike (its tagged faces' vertices; the root ring = the lowest-index 8)."""
    me = ob.data
    at = me.attributes.get(cp.SPIKE_TAG)
    if at is None:
        return []
    tag = np.zeros(len(me.polygons), np.int32)
    at.data.foreach_get('value', tag)
    mw = np.array(ob.matrix_world)
    co = np.array([v.co for v in me.vertices]) @ mw[:3, :3].T + mw[:3, 3]
    vs = sorted({i for f, t in zip(me.polygons, tag) if t for i in f.vertices})
    out = []
    per = 3 * cp.SPIKE_SEGS + 1                         # (3 rings + the tip, made one spike after another)
    for k in range(0, len(vs) - per + 1, per):
        idx = vs[k:k + per]
        out.append((co[idx[:cp.SPIKE_SEGS]].mean(0), co[idx[-1]]))
    return out


plain = make(0)
check('Edge Spikes 0: a plain plate (no spikes)', not spikes_of(plain))
ob = make(12)
sp = spikes_of(ob)
roots = np.array([r for r, _t in sp])
tips = np.array([t for _r, t in sp])
rr = np.linalg.norm(roots[:, :2], axis=1)
rt = np.linalg.norm(tips[:, :2], axis=1)
check(f'Edge Spikes 12: 12 spikes ({cp.perform.__name__}: {len(ob.data.polygons)} faces)', len(sp) == 12, len(sp))
check(f'...their roots on the outline (at {rr.min():.2f} - {rr.max():.2f} from the middle, the outline at {R}), none '
      f'inside the plate', rr.min() > R * 0.85 and rr.max() < R * 1.05, (rr.min(), rr.max()))
check(f'...pointing out from it: the tips at {rt.min():.2f} - {rt.max():.2f} (out past the outline)', rt.min() > R * 1.02)
ang = np.sort(np.arctan2(roots[:, 1], roots[:, 0]))
gaps = np.diff(np.concatenate([ang, [ang[0] + 2 * math.pi]]))
check(f'...spread round the outline at random places (gaps {np.degrees(gaps.min()):.0f} - {np.degrees(gaps.max()):.0f} '
      f'degrees, not all 30)', gaps.max() < math.radians(80) and gaps.std() > math.radians(4), np.degrees(gaps).round(1).tolist())
lens = np.linalg.norm(tips - roots, axis=1)
check(f'...uneven lengths ({lens.min():.3f} - {lens.max():.3f})', lens.max() > lens.min() * 1.25)

# live: the plate's own sliders
p = ob.mch_cplate
p.spike_random = 0.0
sp0 = spikes_of(ob)
a0 = np.sort(np.arctan2([r[1] for r, _t in sp0], [r[0] for r, _t in sp0]))
g0 = np.diff(np.concatenate([a0, [a0[0] + 2 * math.pi]]))
l0 = [np.linalg.norm(t - r) for r, t in sp0]
check(f'...Random 0: evenly round it (gaps {np.degrees(g0.min()):.1f} - {np.degrees(g0.max()):.1f}), all as long',
      g0.std() < math.radians(2.0) and max(l0) - min(l0) < 1e-6 * 10 + max(l0) * 0.02)
p.spike_random = 0.6
p.spikes = 20
check('...the plate\'s Edge Spikes 12 -> 20: 20 spikes (rebuilt live)', len(spikes_of(ob)) == 20)
p.spike_angle = math.radians(90.0)
up = [(t - r) for r, t in spikes_of(ob)]
rise = np.mean([u[2] / np.linalg.norm(u) for u in up])
p.spike_angle = 0.0
flat = [(t - r) for r, t in spikes_of(ob)]
rise0 = np.mean([u[2] / np.linalg.norm(u) for u in flat])
check(f'...Spike Angle 90: up off the body (mean up {rise:.2f}); 0: out along it ({rise0:.2f})', rise > 0.75 and rise0 < 0.35,
      (rise, rise0))
p.spike_angle = math.radians(30.0)
before = np.array([r for r, _t in spikes_of(ob)])
p.spike_seed = 5
after = np.array([r for r, _t in spikes_of(ob)])
check('...Seed: another set (other places)', np.abs(before - after).max() > 0.05)
p.spike_length = 0.5
ls = [np.linalg.norm(t - r) for r, t in spikes_of(ob)]
check(f'...Spike Length 0.5: about that long ({min(ls):.2f} - {max(ls):.2f}, Random 0.6)', 0.3 < min(ls) and max(ls) < 0.7)
check('...remembered: the next plate starts with 20 spikes', st.spikes == 20)

# on a Scale (its tip lifts) and on a curved body: still on the outline
st.spike_length, st.spike_seed = 0.0, 0
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_uv_sphere_add(radius=4.0, segments=64, ring_count=32, location=(0, 0, -4.0 + 0.0))
ball = C.active_object
for o in C.selected_objects:
    o.select_set(False)
ball.select_set(True)
C.view_layer.objects.active = ball
st.profile, st.spikes = 'SCALE', 10
cp.perform(C, LOOP, TOP)
sc = C.active_object
sp = spikes_of(sc)
rr = np.array([np.linalg.norm(r[:2]) for r, _t in sp])
check(f'on a ball, Scale shape: 10 spikes on the outline ({rr.min():.2f} - {rr.max():.2f} from the middle, R {R}; the '
      f'scale\'s tip lifts off the ball along its tilted normal, a little outward)',
      len(sp) == 10 and rr.min() > R * 0.8 and rr.max() < R * 1.12, (len(sp), rr.round(3).tolist()))
bpy.ops.mch.cplate_apply()
check('Apply: a plain mesh with its spikes', not sc.mch_cplate.live and len(spikes_of(sc)) == 10)

mecha_lab.unregister()
summary()
