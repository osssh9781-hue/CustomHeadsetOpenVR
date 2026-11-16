"""0.24.180 Hair in a sculpted shape (user: "메쉬에서 만드는 머리카락 좋긴 한데 좀 더 메쉬 외곽까지의 형태가 비슷한 게
좋을 거 같아", "머리카락 양도 조절 가능하게", "머리카락 빗는 것도 만들어 주고", "그래비티나 그런 게 왜 메쉬 머리카락에는
안 되는겨", "원래 기존에 있던 헤어 세팅 다 쓸 수 있으면 좋겠어"):

* the hair fills the shape to its outline - a fan-shaped bang and a ponytail bulging in the middle (traced from the
  roots alone the strands stayed as close as the roots: a third of the outline was filled);
* Amount live (no tracing again);
* the Fur tool's values: Length, Gravity (out of the head), Bend, Tip Gather, Volume, Clump Size, Viewport %, polypaint
  (painted on the shape) and the colour presets;
* the comb: a stroke turns the strands the way it went (kept through Amount, Clear takes it off, Alt: back)."""
import json
import math
import time

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

import bmesh  # noqa: E402
import mecha_lab
from mecha_lab import creature_fur as cf, hair_shape as hs  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32)
head = C.active_object
head.name = 'Head'
HB = BVHTree.FromPolygons([tuple(v.co) for v in head.data.vertices], [tuple(f.vertices) for f in head.data.polygons])


def dense(P, n=60):
    P = [Vector(p) for p in P]
    seg = list(zip(P[:-1], P[1:]))
    L = [(b - a).length for a, b in seg]
    tot = sum(L)
    out = []
    for i in range(n):
        s = tot * i / (n - 1)
        for (a, b), l_ in zip(seg, L):
            if s <= l_ + 1e-9:
                out.append(a.lerp(b, s / l_))
                break
            s -= l_
    return out


def tube(name, centre, rad_fn, ring=20, flat=1.0, side=None):
    bm = bmesh.new()
    rings = []
    for i, c in enumerate(centre):
        t = i / (len(centre) - 1)
        tan = (centre[min(i + 1, len(centre) - 1)] - centre[max(i - 1, 0)]).normalized()
        u = (Vector(side) - tan * tan.dot(Vector(side))).normalized() if side else tan.orthogonal().normalized()
        v = tan.cross(u)
        r = rad_fn(t)
        rings.append([bm.verts.new(c + (u * math.cos(a) * r + v * math.sin(a) * r * flat))
                      for a in np.linspace(0, 2 * math.pi, ring, endpoint=False)])
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(ring):
            bm.faces.new((a[k], a[(k + 1) % ring], b[(k + 1) % ring], b[k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    S.collection.objects.link(ob)
    return ob


def strands(ob, evaluated=False):
    if evaluated:
        dg = C.evaluated_depsgraph_get()
        d = ob.evaluated_get(dg).data
    else:
        d = ob.data
    P = np.empty(len(d.points) * 3, np.float32)
    d.attributes['position'].data.foreach_get('vector', P)
    M = np.array(ob.matrix_world)
    seg = ob.mch_hshape.segments
    return (P.reshape(-1, 3).astype(float) @ M[:3, :3].T + M[:3, 3]).reshape(-1, seg, 3)


def coverage(hair, shape):
    W = strands(hair)
    D = np.concatenate([hs.resample(s, len(s) * 4) for s in W])
    kd = KDTree(len(D))
    for i, p in enumerate(D):
        kd.insert(Vector(p), i)
    kd.balance()
    me = shape.data
    me.calc_loop_triangles()
    V = np.array([tuple(shape.matrix_world @ v.co) for v in me.vertices])
    T = np.array([tuple(t.vertices) for t in me.loop_triangles])
    rng = np.random.default_rng(3)
    p0, p1, p2 = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    area = np.linalg.norm(np.cross(p1 - p0, p2 - p0), axis=1) / 2
    pick = rng.choice(len(T), size=2000, p=area / area.sum())
    u, v = rng.random(2000), rng.random(2000)
    f = u + v > 1
    u[f], v[f] = 1 - u[f], 1 - v[f]
    smp = p0[pick] + (p1[pick] - p0[pick]) * u[:, None] + (p2[pick] - p0[pick]) * v[:, None]
    size = float(np.ptp(V, axis=0).max())
    dist = []
    for q in smp:
        loc, nrm, _i, _d = HB.find_nearest(Vector(q))
        if (Vector(q) - loc).dot(nrm) < size * 0.01:  # (the part sunk in the head: not to be covered)
            continue
        dist.append(kd.find(Vector(q))[2] / size)
    bvh = BVHTree.FromPolygons([tuple(p) for p in V], [tuple(t) for t in T])
    out = sum(1 for p in D[::7] if (lambda r: r[0] is not None and (Vector(p) - r[0]).dot(r[1]) > size * 0.02)(
        bvh.find_nearest(Vector(p)))) / len(D[::7])
    return float((np.array(dist) < 0.02).mean()), out


def in_head(W):
    n = 0
    flat = W.reshape(-1, 3)[::5]
    for q in flat:
        loc, nrm, _i, _d = HB.find_nearest(Vector(q))
        n += (Vector(q) - loc).dot(nrm) < -0.01
    return n / len(flat)


def make(shape):
    for o in C.selected_objects:
        o.select_set(False)
    shape.select_set(True)
    C.view_layer.objects.active = shape
    hair, _msg = hs.make(C, shape)
    return hair


S.mch_hshape.count = 4000
fan = tube('Fan', dense([(0.0, -0.85, 0.55), (0.0, -1.12, 0.35), (0.0, -1.2, 0.0), (0.0, -1.18, -0.45)]),
           lambda t: 0.1 + 0.45 * math.sin(min(t * 1.2, 1.0) * math.pi / 2) * (1 - 0.6 * max(t - 0.8, 0) / 0.2),
           flat=0.18, side=(1.0, 0.0, 0.0))
pony = tube('Pony', dense([(0.0, 0.85, 0.55), (0.0, 1.25, 0.6), (0.0, 1.5, 0.2), (0.0, 1.45, -0.5), (0.0, 1.3, -1.0)]),
            lambda t: 0.06 + 0.24 * math.sin(t * math.pi) ** 0.8 * (1 - t * 0.3))
hf = make(fan)
cov_f, out_f = coverage(hf, fan)
hp = make(pony)
cov_p, out_p = coverage(hp, pony)
check(f'filled to the outline: a fan-shaped bang - {cov_f:.0%} of its outline has hair within 2 % of its size (traced '
      f'from the roots alone: 35 %), a ponytail bulging in the middle {cov_p:.0%} (38 %); hair out of the shape '
      f'{out_f:.1%} / {out_p:.1%}', cov_f > 0.9 and cov_p > 0.9 and out_f < 0.03 and out_p < 0.04)
hf.hide_set(True)
# Amount: live
p = hp.mch_hshape
traced = hs._CACHE[hp.name]['strands']
t0 = time.perf_counter()
p.count = 12000
hs.rebuild(hp)
t_amt = time.perf_counter() - t0
check(f'Amount 4000 -> 12000: {len(hp.data.curves):,} strands in {t_amt * 1000:.0f} ms, nothing traced again',
      len(hp.data.curves) == 12000 and hs._CACHE[hp.name]['strands'] is traced and t_amt < 1.0)
p.count = 3000
hs.rebuild(hp)
W0 = strands(hp)
L0 = np.linalg.norm(np.diff(W0, axis=1), axis=2).sum(1)
# Gravity
in0 = in_head(W0)
p.gravity = 1.0
hs.rebuild(hp)
W1 = strands(hp)
L1 = np.linalg.norm(np.diff(W1, axis=1), axis=2).sum(1)
in1 = in_head(W1)
check(f'Gravity 1: the tips down (z {np.median(W0[:, -1, 2]):.2f} -> {np.median(W1[:, -1, 2]):.2f}), each strand as '
      f'long ({np.median(L0):.3f} -> {np.median(L1):.3f}), none into the head (points in it {in0:.1%} -> {in1:.1%}: '
      f'the roots sunk in it)', np.median(W1[:, -1, 2]) < np.median(W0[:, -1, 2]) - 0.2
      and abs(np.median(L1) / np.median(L0) - 1) < 0.03 and in1 <= in0 + 0.005)
p.gravity = 0.0
# Length
p.length = 1.4
hs.rebuild(hp)
L2 = np.linalg.norm(np.diff(strands(hp), axis=1), axis=2).sum(1)
p.length = 0.5
hs.rebuild(hp)
L3 = np.linalg.norm(np.diff(strands(hp), axis=1), axis=2).sum(1)
check(f'Length 1.4: longer ({np.median(L2) / np.median(L0):.2f} x), 0.5: shorter ({np.median(L3) / np.median(L0):.2f} x)',
      1.25 < np.median(L2) / np.median(L0) < 1.5 and 0.42 < np.median(L3) / np.median(L0) < 0.58)
p.length = 1.0
# Bend toward +x
p.bend_dir, p.bend, p.bend_at, p.bend_soft = (1.0, 0.0, 0.0), math.radians(90), 0.3, 0.35
hs.rebuild(hp)
W4 = strands(hp)
check(f'Bend 90 toward +x (from 0.3 along): the tips to +x ({np.mean(W0[:, -1, 0]):.2f} -> {np.mean(W4[:, -1, 0]):.2f}), '
      f'the roots where they were ({np.abs(W4[:, 0] - W0[:, 0]).max():.4f})',
      np.mean(W4[:, -1, 0]) > np.mean(W0[:, -1, 0]) + 0.3 and np.abs(W4[:, 0] - W0[:, 0]).max() < 1e-4)
p.bend = 0.0
# Tip Gather, Volume, Clump Size
p.gather = 1.0
hs.rebuild(hp)
sp_g = float(np.linalg.norm(strands(hp)[:, -1] - strands(hp)[:, -1].mean(0), axis=1).mean())
sp_0 = float(np.linalg.norm(W0[:, -1] - W0[:, -1].mean(0), axis=1).mean())
p.gather = 0.0
p.volume = 1.0
hs.rebuild(hp)
W5 = strands(hp)
mid0 = W0.mean(0)
r0 = float(np.linalg.norm(W0 - mid0, axis=2)[:, 12].mean())
r5 = float(np.linalg.norm(W5 - W5.mean(0), axis=2)[:, 12].mean())
p.volume = 0.0
def to_tufts(T, n):                                     # (each tip: how far from the nearest of the tufts' tips)
    G_ = hs._CACHE[hp.name]['Gf']
    M_ = np.array(hp.matrix_world)
    cen = G_[:n, -1] @ M_[:3, :3].T + M_[:3, 3]
    return float(np.median(np.linalg.norm(T[:, None, :] - cen[None, :, :], axis=2).min(1)))


p.clump = 0.0
hs.rebuild(hp)
loose = to_tufts(strands(hp)[:, -1], 50)
p.clump, p.clump_size = 1.0, 60
hs.rebuild(hp)
tight = to_tufts(strands(hp)[:, -1], 50)
p.clump, p.clump_size = 0.6, 3
check(f'Tip Gather 1: the tips meet (spread {sp_0:.3f} -> {sp_g:.4f} - what is left: Frizz's wobble, left on); Volume 1: fuller (half way: '
      f'{r0:.3f} -> {r5:.3f} from the middle); Clump 1, Clump Size 60 (50 tufts): each tip at its tuft\'s '
      f'({loose:.3f} -> {tight:.4f} from the nearest tuft tip)', sp_g < sp_0 * 0.15 and r5 > r0 * 1.2
      and tight < loose * 0.15)
# Viewport %
p.display = 0.25
hs.rebuild(hp)
nv = len(hp.evaluated_get(C.evaluated_depsgraph_get()).data.curves)
check(f'Viewport 25 %: {nv} of {len(hp.data.curves)} strands drawn in the viewport (all render: the modifier '
      f'drops them in the viewport only)', abs(nv / len(hp.data.curves) - 0.25) < 0.04
      and hp.modifiers.get(hs.VIEW_MOD) is not None)
p.display = 1.0
hs.rebuild(hp)
check('Viewport 100 %: the modifier taken off', hp.modifiers.get(hs.VIEW_MOD) is None)
# comb: a stroke (as the Comb tool stores it) down the ponytail's back side toward -y
hs.rebuild(hp)
Wb = strands(hp)
cache = hs._CACHE[hp.name]
G = cache['Gf']
inv = np.array(hp.matrix_world.inverted())
c0 = G[:, 8].mean(0)
stroke = {'m': 'C', 's': 0.9, 'v': [1.0, 0.0, 0.0],
          'p': [list(c0 + np.array([0.0, 0.0, -0.06 * k])) + [0.0, -1.0, 0.0] + [0.6] for k in range(8)]}
hp[hs.COMBS] = json.dumps([stroke])
hs.rebuild(hp)
Wc = strands(hp)
moved_y = float(np.mean(Wc[:, -1, 1] - Wb[:, -1, 1]))
Lc = np.linalg.norm(np.diff(Wc, axis=1), axis=2).sum(1)
Lb = np.linalg.norm(np.diff(Wb, axis=1), axis=2).sum(1)
check(f'Comb: a stroke toward -y turns the strands that way (tips {moved_y:+.3f} in y), the roots stay '
      f'({np.abs(Wc[:, 0] - Wb[:, 0]).max():.4f}), each as long ({np.median(Lb):.3f} -> {np.median(Lc):.3f})',
      moved_y < -0.1 and np.abs(Wc[:, 0] - Wb[:, 0]).max() < 1e-4 and abs(np.median(Lc) / np.median(Lb) - 1) < 0.03)
p.count = 6000
hs.rebuild(hp)
Wd = strands(hp)
check(f'... kept through Amount 6000 (tips {np.mean(Wd[:3000, -1, 1] - Wb[:, -1, 1]):+.3f} in y)',
      np.mean(Wd[:3000, -1, 1] - Wb[:, -1, 1]) < -0.1)
p.count = 3000
hp[hs.COMBS] = json.dumps([stroke, dict(stroke, m='R'), dict(stroke, m='R'), dict(stroke, m='R')])
hs.rebuild(hp)
back = float(np.mean(strands(hp)[:, -1, 1] - Wb[:, -1, 1]))
C.view_layer.objects.active = hp
r = bpy.ops.mch.hair_shape_comb_clear()
gone = float(np.abs(strands(hp) - Wb).max())
check(f'Alt (back as it was) over it three times: nearly back (tips {moved_y:+.3f} -> {back:+.3f}); Clear Comb ({r}): '
      f'as before ({gone:.5f})', abs(back) < abs(moved_y) * 0.35 and r == {'FINISHED'} and gone < 1e-4
      and hs.COMBS not in hp)
# polypaint on the shape, colour presets
att = fan.data.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT')
fan.data.color_attributes.active_color = att
for i, v in enumerate(fan.data.vertices):
    att.data[i].color = (0.9, 0.05, 0.05, 1.0) if v.co.x < 0.0 else (0.05, 0.05, 0.9, 1.0)
hf.hide_set(False)
C.view_layer.objects.active = hf
hf.mch_hshape.tip_blend = 0.0
hs.rebuild(hf, force_trace=True)
col = np.empty(len(hf.data.points) * 4, np.float32)
hf.data.attributes['mch_fur_col'].data.foreach_get('color', col)
col = col.reshape(-1, hf.mch_hshape.segments, 4)
Wf = strands(hf)
left = Wf[:, 12, 0] < -0.1
right = Wf[:, 12, 0] > 0.1
red_l = float((col[left, 12, 0] > 0.5).mean())
blue_r = float((col[right, 12, 2] > 0.5).mean())
r = bpy.ops.mch.hair_shape_colour(preset='BLONDE')
col2 = np.empty(len(hf.data.points) * 4, np.float32)
hf.data.attributes['mch_fur_col'].data.foreach_get('color', col2)
from mecha_lab import creature_hair as ch  # noqa: E402
blonde = next(c for c in ch.COLOUR_PRESETS if c[0] == 'BLONDE')
check(f'Use Polypaint: the colour painted on the shape - red on its left ({red_l:.0%} of the strands there), blue on '
      f'its right ({blue_r:.0%}); the Blonde preset ({r}): its root colour, paint off',
      red_l > 0.9 and blue_r > 0.9 and r == {'FINISHED'} and not hf.mch_hshape.use_polypaint
      and np.allclose(col2.reshape(-1, 4)[0, :3], blonde[2], atol=1e-3))
# the Fur tool's values: all there (but the ones for an area drawn on skin)
fur_keys = {k for k, *_r in cf.LIVE}
area_only = {'lie', 'flow', 'part_soft', 'edge_soft'}
renamed = {'density': 'count', 'tip_thick': 'tip_thin'}
have = set(hs.MCH_PG_HairShape.__annotations__)
missing = sorted(k for k in fur_keys - area_only if renamed.get(k, k) not in have)
check(f'the Fur tool\'s values on the mesh hair too (Density -> Amount, Tip Thickness a share of the root\'s); left '
      f'out: {sorted(area_only)} (the tilt of an area drawn on the skin - here the shape and the comb set it); '
      f'missing {missing}', not missing)
summary()
