"""0.24.183 (user: "우리 헤어 기능에 가생이로 갈수록 짧아지는 것도 만들었나? 없으면 만들어 줘"): Edge Short - the
strands shorter toward the border of where they grow, Edge Width how far in - in all three hair tools:
* Fur (Geometry Nodes): each root's distance to the drawn area's border (its points with one outside next to them);
* Hair in a sculpted shape: each root's distance to the root area's border (the hairline where the shape leaves
  the head), kept short inside a tuft (Clump);
* Creature Hair: each root's distance to the outline you drew.
0 = as before (the same strands); no strand is dropped; an area with no border (all round the body) stays long."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Euler, Vector

import bmesh  # noqa: E402
import mecha_lab
from mecha_lab import core_geometry as cg, creature_fur as cf, creature_hair as ch, hair_shape as hs  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)


def px(x, z):
    return FRONT.to_screen(Vector((x, -2.0, z)))


def blob(cx, cz, r):
    return [[px(cx + r * math.cos(a), cz + r * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 64, endpoint=False)]]


def select(ob):
    for o in C.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    C.view_layer.objects.active = ob


def curves(ob, evaluated=True):
    d = ob.evaluated_get(C.evaluated_depsgraph_get()).data if evaluated else ob.data
    P = np.empty(len(d.points) * 3, np.float32)
    d.attributes['position'].data.foreach_get('vector', P)
    off = np.empty(len(d.curves), np.int32)
    d.curves.foreach_get('first_point_index', off)
    n = np.diff(np.append(off, len(d.points)))
    P = P.reshape(-1, 3).astype(float)
    M = np.array(ob.matrix_world)
    P = P @ M[:3, :3].T + M[:3, 3]
    out = [P[a:a + k] for a, k in zip(off, n)]
    return out


def lengths(strs):
    return np.array([np.linalg.norm(np.diff(s, axis=0), axis=1).sum() for s in strs])


bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=160, ring_count=80)
body = C.active_object
body.name = 'Body'

# ---- Fur --------------------------------------------------------------------------------------------------------
st = S.mch_fur
st.density, st.length, st.length_random, st.clump, st.frizz, st.gravity = 6000.0, 0.1, 0.0, 0.0, 0.0, 0.0
st.volume, st.spread, st.edge_soft, st.gather, st.curl = 0.0, 0.0, 0, 0.0, 0.0
select(body)
cf.perform(C, blob(0.0, 0.0, 0.55), FRONT)
fur = C.active_object
f = fur.mch_fur
check('Fur: Edge Short is off on a new fur (0) and in its window', f.edge_short == 0.0 and
      fur.modifiers[cf.MOD].node_group.get('mch_v') == cf.TREE_VERSION)
F0 = curves(fur)
L0 = lengths(F0)
roots = np.array([s[0] for s in F0])
check(f'... off: every strand as long ({len(F0):,} strands, {L0.min():.4f} - {L0.max():.4f})',
      len(F0) > 500 and np.ptp(L0) < 1e-3, (L0.min(), L0.max()))
# the area's border points (in the area, a point outside it next to them), and each root's distance to them
me = body.data
w = np.empty(len(me.vertices), np.float32)
me.attributes[fur[cf.AREA_KEY]].data.foreach_get('value', w)
ev = np.empty(len(me.edges) * 2, np.int64)
me.edges.foreach_get('vertices', ev)
ev = ev.reshape(-1, 2)
inn = w > 0.5
rim = np.zeros(len(w), bool)
cross = inn[ev[:, 0]] != inn[ev[:, 1]]
rim[ev[cross].ravel()] = True
rim &= inn
co = np.empty(len(me.vertices) * 3, np.float32)
me.vertices.foreach_get('co', co)
B = co.reshape(-1, 3)[rim].astype(float)
dist = np.array([np.linalg.norm(B - r, axis=1).min() for r in roots])
f.edge_short, f.edge_width = 1.0, 0.5
F1 = curves(fur)
L1 = lengths(F1)
want = np.array([cf.edge_factor(d, dist.max(), 1.0, 0.5) for d in dist]) * 0.1
err = np.abs(L1 - want)
edge = dist < dist.max() * 0.1
mid = dist > dist.max() * 0.5
check(f'Fur Edge Short 1: no strand dropped ({len(F1):,}); at the border {np.median(L1[edge]):.4f} long, from half '
      f'way in {np.median(L1[mid]):.4f} (Length 0.1)', len(F1) == len(F0) and np.median(L1[edge]) < 0.03 and
      np.median(L1[mid]) > 0.098)
check(f'... each strand as long as its distance to the border says (off by {np.median(err):.4f} median, '
      f'{np.percentile(err, 95):.4f} at 95 %)', np.median(err) < 0.004 and np.percentile(err, 95) < 0.012)
f.edge_width = 1.0
L2 = lengths(curves(fur))
check(f'Edge Width 1: shorter all the way to the middle (median {np.median(L1):.4f} -> {np.median(L2):.4f})',
      np.median(L2) < np.median(L1) - 0.008 and L2.max() > 0.098)
f.edge_short = 0.5
L3 = lengths(curves(fur))
check(f'Edge Short 0.5: the edge strands half as short ({np.median(L3[edge]):.4f})',
      0.045 < np.median(L3[edge]) < 0.065)
f.edge_short = 0.0
L4 = lengths(curves(fur))
check('Edge Short back to 0: as before', np.abs(L4 - L0).max() < 1e-5)
# an area all round the body: no border - all as long
f.edge_short = 1.0
w_all = np.ones(len(me.vertices), np.float32)
me.attributes[fur[cf.AREA_KEY]].data.foreach_set('value', w_all)
me.update()
L5 = lengths(curves(fur))
check(f'an area with no border (all round the body): all as long ({L5.min():.4f})', len(L5) and L5.min() > 0.099)
me.attributes[fur[cf.AREA_KEY]].data.foreach_set('value', w)
me.update()
f.edge_short = 0.0

# ---- Hair in a sculpted shape -------------------------------------------------------------------------------------
fur.hide_set(True)


def tube(name, centre, rad_fn, ring=24):
    bm = bmesh.new()
    rings = []
    for i, c in enumerate(centre):
        t = i / (len(centre) - 1)
        tan = (centre[min(i + 1, len(centre) - 1)] - centre[max(i - 1, 0)]).normalized()
        u = tan.orthogonal().normalized()
        v = tan.cross(u)
        r = rad_fn(t)
        rings.append([bm.verts.new(c + (u * math.cos(a) + v * math.sin(a)) * r)
                      for a in np.linspace(0, 2 * math.pi, ring, endpoint=False)])
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(ring):
            bm.faces.new((a[k], a[(k + 1) % ring], b[(k + 1) % ring], b[k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me_ = bpy.data.meshes.new(name)
    bm.to_mesh(me_)
    bm.free()
    ob = bpy.data.objects.new(name, me_)
    S.collection.objects.link(ob)
    return ob


cen = [Vector((0.0, 0.0, 0.75)).lerp(Vector((0.0, 0.0, 1.9)), i / 30) for i in range(31)]
lock = tube('Lock', cen, lambda t: 0.32 * (1 - 0.5 * t))       # (a thick lock standing on the top of the head)
select(lock)
S.mch_hshape.count = 3000
hair, _msg = hs.make(C, lock)
p = hair.mch_hshape
p.frizz, p.length_random, p.curl = 0.0, 0.0, 0.0
hs.rebuild(hair)
cache = hs._CACHE[hair.name]
ed = cache.get('edge')
a = hs._analysed(C, lock, p.body, starts=[])
check(f'Hair in Shape: the root area\'s border found ({len(a["root_border"])} points, where the lock leaves the '
      f'head) and each traced strand\'s way to it', len(a['root_border']) > 20 and ed is not None and
      len(ed) == len(cache['strands']) and ed.max() > 0)
H0 = curves(hair, evaluated=False)
HL0 = lengths(H0)
p.edge_short, p.edge_width = 1.0, 0.6
hs.rebuild(hair)                              # (the window's change: rebuilt a moment later, by a timer)
H1 = curves(hair, evaluated=False)
HL1 = lengths(H1)
nT = len(cache['strands'])
r = HL1[:nT] / np.maximum(HL0[:nT], 1e-9)
near, deep = ed < ed.max() * 0.15, ed > ed.max() * 0.7
check(f'Edge Short 1: no strand dropped ({len(H1):,}); the traced strands by the hairline {np.median(r[near]):.0%} as '
      f'long, deep in the lock {np.median(r[deep]):.0%}', len(H1) == len(H0) and np.median(r[near]) < 0.35 and
      np.median(r[deep]) > 0.9)
corr = float(np.corrcoef(ed, r)[0, 1])
check(f'... the shorter the nearer the border (correlation {corr:.2f})', corr > 0.75)
rk = HL1[nT:] / np.maximum(HL0[nT:], 1e-9)
kid_want = hs.edge_share(ed, 1.0, 0.6)[np.arange(nT, len(H1)) % nT]
check(f'... the strands made beside them as short as theirs, Clump {p.clump:.1f} not pulling them long again '
      f'(off by {np.median(np.abs(rk - kid_want)):.2f})', np.median(np.abs(rk - kid_want)) < 0.08)
p.edge_short = 0.0
hs.rebuild(hair)
H2 = curves(hair, evaluated=False)
check('Edge Short 0: as before', np.abs(lengths(H2) - HL0).max() < 1e-5)
hair.hide_set(True)

# ---- Creature Hair -------------------------------------------------------------------------------------------------
sq = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
d_ = ch.outline_distance([(50.0, 50.0), (10.0, 50.0), (50.0, 97.0), (0.0, 0.0)], sq)
check('Creature Hair: a root\'s distance to the outline', np.allclose(d_, [50.0, 10.0, 3.0, 0.0]), list(d_))
hst = S.mch_hair
hst.style = 'QUILLS'
hst.count, hst.length_random, hst.wave, hst.gravity = 60, 0.0, 0.0, 0.0
select(body)
ch.perform(C, blob(0.0, 0.0, 0.5), FRONT)
hr = C.active_object
hp = hr.mch_hair


def islands(ob):
    m = ob.data
    n = len(m.vertices)
    par = np.arange(n)

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    e = np.empty(len(m.edges) * 2, np.int64)
    m.edges.foreach_get('vertices', e)
    for a_, b_ in e.reshape(-1, 2):
        ra, rb = find(a_), find(b_)
        if ra != rb:
            par[ra] = rb
    lab = np.array([find(i) for i in range(n)])
    t = np.empty(n, np.float32)
    m.attributes[ch.T_ATTR].data.foreach_get('value', t)
    c = np.empty(n * 3, np.float32)
    m.vertices.foreach_get('co', c)
    c = c.reshape(-1, 3)
    out = []
    for k in np.unique(lab):
        sel = lab == k
        if not (t[sel] < 0.02).any():
            continue                                # (a ring, not a strand)
        rt, tp = c[sel & (t < 0.02)].mean(0), c[sel & (t > 0.98)].mean(0)
        out.append((rt, np.linalg.norm(tp - rt)))
    out.sort(key=lambda q: (round(q[0][0], 4), round(q[0][2], 4)))
    return out


I0 = islands(hr)
hp.edge_short, hp.edge_width = 1.0, 0.6
I1 = islands(hr)
ok = len(I0) == len(I1) and len(I0) > 20
ratio = np.array([b[1] / max(a_[1], 1e-9) for a_, b in zip(I0, I1)]) if ok else np.zeros(1)
rr = np.array([math.hypot(a_[0][0], a_[0][2]) for a_ in I0]) if ok else np.zeros(1)
corr2 = float(np.corrcoef(0.5 - rr, ratio)[0, 1]) if ok else 0.0
check(f'Creature Hair Edge Short 1: {len(I1)} strands kept; by the outline {ratio[rr > 0.4].mean():.0%} as long, in '
      f'the middle {ratio[rr < 0.15].mean():.0%}; the nearer the outline the shorter (correlation {corr2:.2f})',
      ok and ratio[rr > 0.4].mean() < 0.5 and ratio[rr < 0.15].mean() > 0.9 and corr2 > 0.75)
hp.edge_short = 0.0
I2 = islands(hr)
check('Edge Short 0: as before', len(I2) == len(I0) and all(abs(a_[1] - b[1]) < 1e-5 for a_, b in zip(I0, I2)))


# ---- the windows show it ---------------------------------------------------------------------------------------------
class Rec:
    def __init__(self):
        self.props = []

    def __getattr__(self, name):
        def f_(*a, **k):
            if name == 'prop' and len(a) > 1:
                self.props.append(a[1])
            return self
        return f_

    def __setattr__(self, k, v):
        if k == 'props':
            object.__setattr__(self, k, v)


rec = Rec()
select(fur)
fur.hide_set(False)
try:
    cf.draw(rec, C)
except Exception as ex:                      # noqa: BLE001
    print('fur draw', ex)
r2 = Rec()
hair.hide_set(False)
select(hair)
try:
    hs.draw(r2, C, hair)
except Exception as ex:                      # noqa: BLE001
    print('hair draw', ex)
r3 = Rec()
select(hr)
hp.edge_short = 0.3
try:
    ch.draw(r3, C)
except Exception as ex:                      # noqa: BLE001
    print('creature hair draw', ex)
check('the windows: Edge Short / Edge Width in Fur, Hair in Shape and Creature Hair',
      {'edge_short', 'edge_width'} <= set(rec.props) and {'edge_short', 'edge_width'} <= set(r2.props) and
      {'edge_short', 'edge_width'} <= set(r3.props), (rec.props[:30], r2.props[:30], r3.props[:30]))

mecha_lab.unregister()
import sys  # noqa: E402
sys.exit(1 if summary() else 0)
