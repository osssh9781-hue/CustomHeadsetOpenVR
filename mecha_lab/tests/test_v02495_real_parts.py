"""0.24.95 Real Parts - the Shapes page's exterior parts after real vehicles (user: "실제로 내가 말한 차랑 비행기 탱크를
자료 서치해서 부품을 그대로 만들어볼래?"):

* every part of every vehicle (Lambo, 911, F-22, Tank) summoned at the 3D cursor: a clean closed solid (one piece,
  normals out, flat faces flat), its longest side the Size, its parameters on it; flat shaded when angular, smooth
  when curved; the symmetric ones (turret, hull front, mantlet, nozzle, rear wing, canopy, nose, round lamp) the
  left half the mirror of the right
* the reference shows: the F-22 wing's leading edge swept about 42 degrees, its trailing edge forward; the Lambo
  front fender's wheel arch a hexagon with a flat top; the tank's side skirt long and low, its top flange bent in
* the same seed: the same part; another seed: the same part a little different (the slight randomness)
* Variations / Reroll keep the vehicle (and Variations the part); a panel as thick as Thickness
* the page (Real Parts: vehicles, parts, Summon Part); 300 random parts and variations all clean"""
import math
import random

import numpy as np
from _harness import bmesh, bpy, check, fresh, summary

import mecha_lab
from mecha_lab import random_shapes as rs, ref_parts as rp, side_panel as sp

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
st = S.mch_rshape


def solid(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    ok = (rs._closed(bm) and rs._islands(bm) == 1 and bm.calc_volume(signed=True) > 0
          and rs._planar_ok(bm, rs.FLAT_TOL * longest(ob), quads=not rs.params_of(ob).get('curved')))
    bm.free()
    return ok


def co(ob):
    return np.array([v.co[:] for v in ob.data.vertices])


def longest(ob):
    c = co(ob)
    return float((c.max(0) - c.min(0)).max())


def mirrored(ob, tol=2e-3):
    c = co(ob)
    m = c * np.array([-1.0, 1.0, 1.0])
    from mathutils.kdtree import KDTree
    kd = KDTree(len(c))
    for i, p in enumerate(c):
        kd.insert(p, i)
    kd.balance()
    return all(kd.find(p)[2] < tol * longest(ob) for p in m)


def clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)


SYM = {('LAMBO', 'WING'), ('P911', 'LAMP'), ('F22', 'NOZZLE'), ('F22', 'CANOPY'), ('F22', 'NOSE'), ('MBT', 'TURRET'),
       ('MBT', 'MANTLET'), ('MBT', 'GLACIS'), ('MBT', 'CAST')}     # (the road wheel turns round X: its hub out +X)

# every part, summoned
clear()
S.cursor.location = (1.0, 2.0, 0.0)
st.size, st.count, st.plate_thk = 1.5, 1, 0.05
made, bad, shade, asym = {}, [], [], []
for v in rp.PART_IDS:
    for part in rp.PART_IDS[v]:
        bpy.ops.mch.random_shape_ref(vehicle=v)
        bpy.ops.mch.random_shape_ref(part=part)
        r = bpy.ops.mch.random_shape_add(family='REF', seed=5)
        ob = C.active_object
        p = rs.params_of(ob)
        made[(v, part)] = ob
        if not (r == {'FINISHED'} and p and p['family'] == 'REF' and p['kind'] == v and p['part'] == part
                and solid(ob) and abs(longest(ob) - 1.5) < 1e-4 and rs.LAST['level'] == 0):
            bad.append((v, part))
        smooth = all(f.use_smooth for f in ob.data.polygons)
        flat = not any(f.use_smooth for f in ob.data.polygons)
        if not (smooth if (v, part) in rp.CURVED else flat):
            shade.append((v, part))
        if (v, part) in SYM and not mirrored(ob):
            asym.append((v, part))
check(f'Real Parts: every part of every vehicle ({sum(len(x) for x in rp.PART_IDS.values())}: Lambo, 911, F-22, '
      'Tank) summoned - a clean closed solid as it is meant (no pocket / cut left out), flat faces flat, its longest '
      'side the Size, the vehicle and part in its parameters', not bad, bad)
check('... flat shaded when angular (Lambo, F-22 panels, Abrams), smooth when curved (911, canopy, nose, cast '
      'turret, wheel)', not shade, shade)
check('... the symmetric ones (rear wing, round lamp, nozzle, canopy, nose, turret, mantlet, hull front, cast '
      'turret): the left half the mirror of the right', not asym, asym)

# the reference shows
w = made[('F22', 'WING')]
c = co(w)
x0, x1 = c[:, 0].min(), c[:, 0].max()
root = c[np.abs(c[:, 0] - x0) < 0.02 * longest(w)]
tip = c[np.abs(c[:, 0] - x1) < 0.02 * longest(w)]
le = math.degrees(math.atan2(root[:, 1].max() - tip[:, 1].max(), x1 - x0))
te = math.degrees(math.atan2(root[:, 1].min() - tip[:, 1].min(), x1 - x0))
check('F-22 wing as the reference: leading edge swept about 42 degrees, the trailing edge swept forward (-17)',
      36.0 < le < 48.0 and -24.0 < te < -10.0, (round(le, 1), round(te, 1)))
fd = made[('LAMBO', 'FENDER')]
c = co(fd)
low = c[c[:, 2] < c[:, 2].min() + 0.01 * longest(fd)]
gap = np.diff(np.sort(np.unique(np.round(low[:, 1], 4))))
check('Lambo front fender: the wheel arch out of its bottom edge (the bottom in two pieces, the arch between)',
      gap.size > 0 and gap.max() > 0.3 * longest(fd), round(float(gap.max()) if gap.size else 0.0, 3))
sk = made[('MBT', 'SKIRT')]
dims = sorted(sk.dimensions)
c = co(sk)
check('Tank side skirt: long and low (the M1\'s 7.6 x 0.9 m), its top flange bent in (wider at the top than the '
      'panel is thick)', dims[2] > 5.5 * dims[1]
      and np.ptp(c[c[:, 2] > c[:, 2].max() - 0.01 * longest(sk)][:, 0]) > 1.5 * np.ptp(c[c[:, 2] < 0.3 * c[:, 2].max()
                                                                                         + c[:, 2].min() * 0.7][:, 0]),
      [round(d, 3) for d in dims])

# 0.24.95 (user: "아머드 코어 스타일 에셋도 50 개 만들어 줘")
ac = rp.PART_IDS['ARMORED']
groups = {k[0] for k in ac}
check('AC Style: 50 parts - heads, cores, arms, legs, reverse joint, quad / tank, boosters, weapons, back units, '
      'armour - each with its thumbnail', len(ac) == 50 and groups == {'H', 'C', 'A', 'L', 'R', 'Q', 'T', 'B', 'W', 'U', 'M'}
      and all(rs.shape_icon(f'ref_ARMORED_{k}').startswith('file:') for k in ac), (len(ac), sorted(groups)))
mp = made[('ARMORED', 'W_MISSILE')]
check('... the missile pod: six tubes pushed into its front (the grid of recesses), still one clean solid',
      solid(mp) and len(mp.data.polygons) >= 5 + 6 * 5, len(mp.data.polygons))

# the same seed / another seed
clear()
bpy.ops.mch.random_shape_ref(vehicle='P911')
bpy.ops.mch.random_shape_ref(part='FENDER_R')
bpy.ops.mch.random_shape_add(family='REF', seed=9)
a = co(C.active_object)
bpy.ops.mch.random_shape_add(family='REF', seed=9)
b = co(C.active_object)
bpy.ops.mch.random_shape_add(family='REF', seed=10)
c2 = co(C.active_object)
check('The same seed: the same part; another seed: the same part a little different (a summon\'s slight '
      'randomness), as many points', a.shape == b.shape and np.abs(a - b).max() < 1e-6 and a.shape == c2.shape
      and 1e-3 < np.abs(a - c2).max() < 0.25, round(float(np.abs(a - c2).max()), 4) if a.shape == c2.shape else '')

# Variations / Reroll
clear()
mat = bpy.data.materials.new('paint')
bpy.ops.mch.random_shape_ref(vehicle='F22')
bpy.ops.mch.random_shape_ref(part='INTAKE')
bpy.ops.mch.random_shape_add(family='REF', seed=3)
src = C.active_object
src.data.materials.append(mat)
st.var_count, st.var_amount = 4, 0.5
r = bpy.ops.mch.random_shape_vary(seed=4)
vs = list(C.selected_objects)
ps = [rs.params_of(o) for o in vs]
check('Variations of a real part: four relatives, each the same vehicle and part, a clean solid, not the same, its '
      'materials', r == {'FINISHED'} and len(vs) == 4 and all(q['kind'] == 'F22' and q['part'] == 'INTAKE' for q in ps)
      and all(solid(o) for o in vs) and all(q['d'] != rs.params_of(src)['d'] for q in ps)
      and all(o.data.materials[:] == [mat] for o in vs), [q['part'] for q in ps])
st.ref_vehicle = 'LAMBO'                              # (the page shows another vehicle - set, not clicked)
for o in C.selected_objects:
    o.select_set(False)
vs[0].select_set(True)
C.view_layer.objects.active = vs[0]
r = bpy.ops.mch.random_shape_reroll(seed=8)
q = rs.params_of(vs[0])
check('Reroll of a real part: another part of its own vehicle (F-22 kept, the page showing Lambo), clean',
      r == {'FINISHED'} and q['family'] == 'REF' and q['kind'] == 'F22' and solid(vs[0]), (q['kind'], q['part']))

# 0.24.95 thumbnails (user: "썸네일 - 그거 선택하고 변경 가능하게") and the last Summon live
q0 = rs.params_of(vs[0])
loc0 = vs[0].location.copy()
st.ref_vehicle, st.ref_part = 'MBT', 'TURRET'
n = rs._reroll(C, [vs[0]], 77, follow_page=True)
check('A selected real part clicked while placing a thumbnail (the swap): it becomes that part - the page\'s vehicle '
      'and part - where it was', n == 1 and rs.params_of(vs[0])['kind'] == 'MBT'
      and rs.params_of(vs[0])['part'] == 'TURRET' and solid(vs[0]) and (vs[0].location - loc0).length < 1e-9,
      (q0['kind'], rs.params_of(vs[0])['part']))
from mathutils import Vector  # noqa: E402
pt, nrm = Vector((1.0, 2.0, 0.5)), Vector((0.0, -0.6, 0.8)).normalized()
rs.place_pose(vs[0], pt, nrm, 0.3)
C.view_layer.update()
lowest = min(((vs[0].matrix_world @ v.co) - pt).dot(nrm) for v in vs[0].data.vertices)
up = (vs[0].matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
check('Placing like an asset: the part stands on the surface point - its up along the surface normal, its lowest '
      'point on the surface', abs(lowest) < 1e-5 and (up - nrm).length < 1e-5, (round(lowest, 6), tuple(up)))
clear()
st.count = 2
bpy.ops.mch.random_shape_add(family='REF', seed=4)
live = list(C.selected_objects)
bpy.ops.mch.random_shape_ref(part='SKIRT')
rs._live_apply() if rs._PENDING[0] else None
st.count = 3
rs._live_apply() if rs._PENDING[0] else None
check('The last Summon live: another part clicked - both become it at once; Count 3 - one more next to them',
      all(rs.params_of(o)['part'] == 'SKIRT' for o in live) and len(C.selected_objects) == 3
      and all(solid(o) for o in C.selected_objects), [rs.params_of(o)['part'] for o in C.selected_objects])
st.count = 1

# a panel as thick as Thickness
clear()
vol = []
for t in (0.03, 0.06):
    st.plate_thk = t
    bpy.ops.mch.random_shape_ref(vehicle='MBT')
    bpy.ops.mch.random_shape_ref(part='SKIRT')
    bpy.ops.mch.random_shape_add(family='REF', seed=2)
    bm = bmesh.new()
    bm.from_mesh(C.active_object.data)
    vol.append(bm.calc_volume() / (sum(f.calc_area() for f in bm.faces) / 2))
    bm.free()
st.plate_thk = 0.05
check('A panel (the skirt) as thick as Thickness: twice the Thickness, twice as thick', 1.7 < vol[1] / vol[0] < 2.3,
      [round(x, 5) for x in vol])

# the page
C.window_manager.mch_side_page = 'SHAPES'
bpy.ops.mch.random_shape_ref(vehicle='MBT')
its, _h = sp.content(C, None, 0.0, 276.0, 1.0)
labels = [i.label for i in its if i.kind in {'tbtn', 'mtile'}]        # (0.24.95 parts as thumbnails)
heads = [i.label for i in its if i.kind == 'shead']
tank = next((i for i in its if i.kind == 'tbtn' and i.label == 'Tank' and i.action[1] == 'mch.random_shape_ref'), None)
check('The page: Real Parts (Lambo 911 Jet Tank, the vehicle in use lit; its parts and Any; Panel Thickness; '
      'Summon Part)', any(h.startswith('REAL PARTS') for h in heads)
      and all(n in labels for n in ('Lambo', '911', 'Jet', 'Tank', 'Any', 'Turret', 'Side Skirt', 'Road Wheel',
                                    'Summon Part')) and tank is not None and tank.on
      and any(getattr(i, 'prop', '') == 'plate_thk' for i in its), (labels, heads))
bpy.ops.mch.random_shape_ref(vehicle='LAMBO')
check('... another vehicle: Any part until one is picked', st.ref_part == 'ANY')

# many
bad = []
for seed in range(300):
    rng = random.Random(seed)
    p = rp.ref_params(rng, 'ANY', 'ANY', rng.uniform(0.01, 0.12))
    for q in (p, rs.vary(p, 1.0, rng)):
        bm, _k = rs.build(q, 24 + seed % 3 * 8, 1.0)
        if not (rs._closed(bm) and rs._islands(bm) == 1 and bm.calc_volume(signed=True) > 0) or rs.LAST['level']:
            bad.append((q['kind'], q['part'], seed, rs.LAST['level']))
        bm.free()
check('300 random real parts (any vehicle, any part, any Thickness) and a variation of each at Amount 1: every one a '
      'clean closed solid as it is meant', not bad, bad[:6])
summary()
