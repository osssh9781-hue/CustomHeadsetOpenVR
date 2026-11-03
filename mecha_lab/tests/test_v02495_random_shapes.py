"""0.24.95 Random Shapes - the side panel's Shapes page (user: "박스를 꺼내면 랜덤 모양으로 나오게", "다각형 소환 툴이랑
곡률이 들어간 도형 소환 툴", "콕핏스러운 곡률", "마음에 들면 그 도형 클릭하고 변주 주면 비슷한데 조금씩 다른 도형들",
"꼭 사각형이 아니라 더 다각형이어도 돼"):

* Summon Polygon / Summon Curved at the 3D cursor (Count in a row), each a clean closed solid, its parameters on it;
  Polygon flat shaded, Curved smooth with its folded lines sharp; Symmetric = the left half the mirror of the right
* the same seed: the same shapes (F9)
* Variations: close relatives of the selected shape next to it (same kind, a little different), again from one of them
* Reroll: a new form where the shape is (place, size, materials kept)
* Plate (user: "덩어리지만 약간 판떼기 버전도 - 두께가 얇은 판떼기"): thin plates of both families - a Polygon plate as
  thick as Thickness facing the front, a Curved plate curved both ways; Variations / Reroll keep a plate a plate
* a Polygon plate is bent (user: "판도 꺾여 있어야지"): its sides wrapped back, a V down the middle, its top / bottom
  edge bent - each part flat, the fold lines mitred
* Curved: Torso, flat-topped Pods (a rounded rim round a flat face), chisel cuts mirrored into a ridge
* the tab and the page; a Cut on a Curved shape works; 400 random shapes all clean"""
import random

import numpy as np
from _harness import bmesh, bpy, check, fresh, summary
from mathutils import Euler, Vector  # noqa: E402  (after bpy)

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce, random_shapes as rs, side_panel as sp

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
st = S.mch_rshape


def solid(ob):
    """(closed - every edge between two faces, one piece, the volume out)"""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    ok = rs._closed(bm) and rs._islands(bm) == 1 and bm.calc_volume(signed=True) > 0
    bm.free()
    return ok


def mirrored(ob, nd=4):
    co = {tuple(round(c, nd) for c in v.co) for v in ob.data.vertices}
    return all((-x, y, z) in co for x, y, z in co)


def longest(ob):
    co = np.array([v.co[:] for v in ob.data.vertices])
    return float((co.max(0) - co.min(0)).max())


def face_flat(ob, f):
    """the polygon's corners on its plane within FLAT_TOL of the shape's size"""
    co = np.array([ob.data.vertices[i].co[:] for i in f.vertices])
    n = np.array(f.normal[:])
    return float(np.abs((co - co.mean(0)) @ n).max()) <= rs.FLAT_TOL * longest(ob)


def shapes():
    return [o for o in S.objects if rs.is_shape(o)]


for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
S.cursor.location = (2.0, 1.0, 0.5)
st.count, st.size, st.kind = 3, 1.5, 'MIX'
r = bpy.ops.mch.random_shape_add(family='POLY', seed=11)
made = list(C.selected_objects)
check('Summon Polygon (Count 3): three shapes in a row round the 3D cursor, selected, each a clean closed solid of '
      'flat faces, its longest side the Size, its parameters on it',
      r == {'FINISHED'} and len(made) == 3 and all(rs.is_shape(o) and solid(o) for o in made)
      and all(abs(longest(o) - 1.5) < 1e-4 for o in made)
      and all(not any(p.use_smooth for p in o.data.polygons) for o in made)
      and abs(sum(o.location.x for o in made) / 3 - 2.0) < 1e-6 and all(abs(o.location.y - 1.0) < 1e-6 for o in made)
      and all(rs.params_of(o)['family'] == 'POLY' for o in made), [o.name for o in made])
first = [tuple(v.co) for v in made[0].data.vertices]
for o in made:
    bpy.data.objects.remove(o)
bpy.ops.mch.random_shape_add(family='POLY', seed=11)
again = sorted(C.selected_objects, key=lambda o: o.location.x)
check('... the same seed: the same shapes (F9 keeps them while you change the settings)',
      any([tuple(v.co) for v in o.data.vertices] == first for o in again))
for o in again:
    bpy.data.objects.remove(o)

st.count, st.size, st.curve_kind, st.curve_sym = 1, 2.0, 'POD', True
r = bpy.ops.mch.random_shape_add(family='CURVE', seed=5)
pod = C.active_object
me = pod.data
sharp = np.zeros(len(me.edges), bool)
if 'sharp_edge' in me.attributes:
    me.attributes['sharp_edge'].data.foreach_get('value', sharp)
check('Summon Curved (Pod): a clean closed solid, smooth shaded, symmetric (the left half the mirror of the right), '
      'its folded lines sharp (the flat cut\'s rim), the round rows not',
      r == {'FINISHED'} and solid(pod) and all(p.use_smooth for p in me.polygons) and mirrored(pod)
      and 0 < sharp.sum() < 0.5 * len(me.edges) and len(me.polygons) > 150 and rs.params_of(pod)['kind'] == 'POD',
      (len(me.polygons), int(sharp.sum()), len(me.edges)))
st.curve_sym = False
bpy.ops.mch.random_shape_add(family='CURVE', seed=8)
check('... Symmetric off: the shape made without the mirror (kept in its parameters)',
      not rs.params_of(C.active_object)['sym'])
bpy.data.objects.remove(C.active_object)
st.curve_sym = True

# Variations
mat = bpy.data.materials.new('Paint')
pod.data.materials.append(mat)
for o in C.selected_objects:
    o.select_set(False)
pod.select_set(True)
C.view_layer.objects.active = pod
st.var_count, st.var_amount = 4, 0.3
p0 = rs.params_of(pod)
r = bpy.ops.mch.random_shape_vary(seed=3)
vs = list(C.selected_objects)
spots = [v.location.copy() for v in vs]
check('Variations: four relatives next to it (in a row, none on another), selected; the shape you liked kept',
      r == {'FINISHED'} and len(vs) == 4 and pod.name in bpy.data.objects and pod not in vs
      and all(abs(s.y - pod.location.y) < 1e-6 and s.x > pod.location.x for s in spots)
      and min((a - b).length for i, a in enumerate(spots) for b in spots[i + 1:]) > max(pod.dimensions))
same = [rs.params_of(v) for v in vs]
check('... each the same kind, sides, cuts and symmetry; its numbers moved a little - not the same shape',
      all(q['kind'] == p0['kind'] and q['n'] == p0['n'] and len(q['cuts']) == len(p0['cuts']) and q['sym']
          for q in same) and all(q != p0 for q in same)
      and all(max(abs(a - b) for a, b in zip(q['w'], p0['w'])) < 0.2 for q in same))
check('... each a clean solid, symmetric, as big as the one it came from, its materials',
      all(solid(v) and mirrored(v) and abs(longest(v) - longest(pod)) < 1e-4 and v.data.materials[:] == [mat]
          for v in vs))
st.var_amount = 0.05
small = []
for amount in (0.05, 0.6):
    st.var_amount = amount
    for o in C.selected_objects:
        o.select_set(False)
    pod.select_set(True)
    C.view_layer.objects.active = pod
    bpy.ops.mch.random_shape_vary(seed=9)
    small.append(np.mean([np.mean([abs(a - b) for a, b in zip(rs.params_of(v)['d'], p0['d'])])
                          for v in C.selected_objects]))
check('... Amount: a small one moves the shape less than a big one', small[0] < small[1], [round(x, 4) for x in small])
st.var_amount = 0.3
child = vs[2]
for o in C.selected_objects:
    o.select_set(False)
child.select_set(True)
C.view_layer.objects.active = child
r = bpy.ops.mch.random_shape_vary(seed=4)
check('... and again from one of them (a family of shapes)',
      r == {'FINISHED'} and len(C.selected_objects) == 4 and all(solid(o) for o in C.selected_objects))

# Reroll
for o in C.selected_objects:
    o.select_set(False)
vs[0].select_set(True)
C.view_layer.objects.active = vs[0]
loc, size0, co0 = vs[0].location.copy(), longest(vs[0]), [tuple(v.co) for v in vs[0].data.vertices]
r = bpy.ops.mch.random_shape_reroll(seed=21)
check('Reroll: a new form where it was (place, size, materials, its family kept)',
      r == {'FINISHED'} and (vs[0].location - loc).length < 1e-9 and abs(longest(vs[0]) - size0) < 1e-4
      and [tuple(v.co) for v in vs[0].data.vertices] != co0 and vs[0].data.materials[:] == [mat]
      and rs.params_of(vs[0])['family'] == 'CURVE' and solid(vs[0]))

# the page
C.window_manager.mch_side_page = 'SHAPES'
its, _h = sp.content(C, None, 0.0, 276.0, 1.0)
labels = [i.label for i in its if i.kind == 'tbtn']
heads = [i.label for i in its if i.kind == 'shead']
vary_btn = next((i for i in its if i.kind == 'tbtn' and i.label == 'Variations'), None)
check('The Shapes page: Solid | Plate, Polygon (Mix Block Prism Wedge Step Shard, Summon Polygon), Curved (Mix Pod '
      'Shell Capsule Dome Cut Torso, Summon Curved), Variations (on: a random shape is selected), Reroll',
      all(n in labels for n in ('Solid', 'Plate', 'Block', 'Prism', 'Wedge', 'Step', 'Shard', 'Pod', 'Shell', 'Capsule',
                                'Dome Cut', 'Torso', 'Summon Polygon', 'Summon Curved'))
      and any(h.startswith('POLYGON') for h in heads) and any(h.startswith('CURVED') for h in heads)
      and vary_btn is not None and vary_btn.enabled and any(n.startswith('Reroll Selected') for n in labels),
      (labels, heads))
pod_btn = next(i for i in its if i.kind == 'tbtn' and i.label == 'Pod')
check('... the kind in use lit (blue)', pod_btn.on and pod_btn.action[:2] == ('op', 'mch.random_shape_kind'))
r = bpy.ops.mch.side_page(page='SHAPES')
tabs = [i for i in sp.items(C, 1200, 900, 1.0) if i.kind == 'ptab']
check('... its tab (Shapes) beside Mech / Creature / Decals / HDRI, lit when shown',
      r == {'FINISHED'} and any(t.label == 'Shapes' and t.on for t in tabs), [(t.label, t.on) for t in tabs])

st.form = 'PLATE'
its, _h = sp.content(C, None, 0.0, 276.0, 1.0)
check('... Plate on: lit, its Thickness bar shown', any(i.kind == 'tbtn' and i.label == 'Plate' and i.on for i in its)
      and any(getattr(i, 'prop', '') == 'plate_thk' for i in its))
st.form = 'SOLID'

# plates
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
S.cursor.location = (0.0, 0.0, 0.0)
st.form, st.plate_thk, st.size, st.count, st.kind, st.poly_sym = 'PLATE', 0.04, 2.0, 1, 'BLOCK', False
r = bpy.ops.mch.random_shape_add(family='POLY', seed=6)
pp = C.active_object
bm = bmesh.new()
bm.from_mesh(pp.data)
thick = bm.calc_volume() / (sum(f.calc_area() for f in bm.faces) / 2)
bm.free()
check('Plate (Polygon): a thin panel - as thick as Thickness x its size (volume / half its area), flat faces, a '
      'clean closed solid, "plate" in its parameters',
      r == {'FINISHED'} and solid(pp) and 0.02 * longest(pp) < thick < 0.055 * longest(pp)
      and rs.plate_of(rs.params_of(pp)) == 0.04 and not any(p.use_smooth for p in pp.data.polygons)
      and all(face_flat(pp, f) for f in pp.data.polygons), (round(thick, 4), round(longest(pp), 3)))
st.curve_kind, st.curve_sym = 'POD', True
r = bpy.ops.mch.random_shape_add(family='CURVE', seed=6)
cp = C.active_object
bm = bmesh.new()
bm.from_mesh(cp.data)
vol = bm.calc_volume()
area = sum(f.calc_area() for f in bm.faces)
bm.free()
check('Plate (Curved Pod): the front of the body as a thin curved plate - a clean closed solid, symmetric, smooth, '
      'thin (volume / half its area: about its thickness, a few % of its size)',
      r == {'FINISHED'} and solid(cp) and mirrored(cp, 3) and all(p.use_smooth for p in cp.data.polygons)
      and 0 < vol / (area / 2) < 0.08 * longest(cp), (round(vol / (area / 2), 4), round(longest(cp), 3)))
for o in C.selected_objects:
    o.select_set(False)
cp.select_set(True)
C.view_layer.objects.active = cp
st.form = 'SOLID'
bpy.ops.mch.random_shape_vary(seed=2)
vplates = list(C.selected_objects)
check('... its Variations plates too (whatever the page says now), each clean',
      len(vplates) == st.var_count and all(isinstance(rs.params_of(v).get('plate'), dict) and solid(v)
                                           for v in vplates))

import math  # noqa: E402


def bends(ob):
    """the angles (degrees) between the plate's big faces facing the same way, the largest"""
    big = sorted(ob.data.polygons, key=lambda f: -f.area)[:6]
    return max([math.degrees(a.normal.angle(b.normal)) for a in big for b in big
                if a.index != b.index and a.normal.dot(b.normal) > 0] or [0.0])


folded = flat = 0
st.form = 'PLATE'
for sd in range(1, 13):
    st.poly_sym = sd % 2 == 0
    bpy.ops.mch.random_shape_add(family='POLY', seed=100 + sd)
    o = C.active_object
    pf = rs.params_of(o)
    if pf['folds'] and solid(o) and bends(o) > 5 and all(face_flat(o, f) for f in o.data.polygons):
        folded += 1
    flat += bends(o) < 3
    bpy.data.objects.remove(o)
check('Polygon plates bent (wrapped sides, a V ridge, bent lips): 12 summoned - each with folds, its parts at an '
      'angle, every face flat (a twisted rim strip: triangles), a clean closed solid', folded == 12 and flat == 0,
      (folded, flat))
st.poly_sym = True
bpy.ops.mch.random_shape_add(family='POLY', seed=7)
sp_ = C.active_object
check('... a symmetric one: bent the same both sides', mirrored(sp_, 3) and bends(sp_) > 5 and solid(sp_))
st.var_amount = 0.4
bpy.ops.mch.random_shape_vary(seed=8)
check('... its Variations bent too (each its folds a little moved)',
      all(rs.params_of(v)['folds'] and bends(v) > 5 and solid(v) for v in C.selected_objects)
      and any(rs.params_of(v)['folds'] != rs.params_of(sp_)['folds'] for v in C.selected_objects))
st.form, st.poly_sym = 'SOLID', False
for o in C.selected_objects:
    o.select_set(False)
pp.select_set(True)
C.view_layer.objects.active = pp
bpy.ops.mch.random_shape_reroll(seed=5)
check('... Reroll keeps a plate a plate (as thick)', rs.plate_of(rs.params_of(pp)) == 0.04 and solid(pp))

# Curved: the new look
tops = []
for seed in range(1, 21):
    p = rs.curve_params(random.Random(seed), 'POD', 2, True)
    rows = [sc for _t, sc, _r in rs.body_rings(p, 32)]
    tops.append(min(rows[0], rows[-1]))
check('Curved Pod: a rounded box - its ends a rounded rim round a flat face (not closing to a point like an egg)',
      min(tops) > 0.3, [round(t, 2) for t in tops[:6]])
st.form, st.curve_kind = 'SOLID', 'TORSO'
bpy.ops.mch.random_shape_add(family='CURVE', seed=4)
tor = C.active_object
pt = rs.params_of(tor)
check('Curved Torso: wider at the top than the waist, the chest forward, a flat back; a clean symmetric solid',
      pt['kind'] == 'TORSO' and pt['w'][2] > pt['w'][0] and pt['y'][2] > 0.05 and pt['back'] < 0.85
      and solid(tor) and mirrored(tor))
chisel = 0
for seed in range(1, 41):
    p = rs.curve_params(random.Random(seed), 'DOMECUT', 3, True)
    chisel += any(c[0] > 0.2 and c[1] > 0.5 for c in p['cuts'])
check('... chisel cuts (to one side of the front, mirrored: a ridge down the middle) in many Dome Cuts',
      chisel >= 15, chisel)

# a Cut on a curved shape
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
S.cursor.location = (0.0, 0.0, 0.0)
st.count, st.size, st.curve_kind = 1, 2.0, 'CAPSULE'
bpy.ops.mch.random_shape_add(family='CURVE', seed=2)
cap = C.active_object
S.mch_settings.auto_apply = True
S.mch_cut.targets = 'SELECTED'
S.mch_cut.depth_mode = 'THROUGH'
S.mch_cut.edge_finish = S.mch_cut.gn_finish = 'NONE'
bm = bmesh.new()
bm.from_mesh(cap.data)
v0 = bm.calc_volume()
bm.free()
pr = cg.OrthoProjector(Euler((1.5707963, 0, 0)).to_quaternion(), pixels_per_unit=100.0)
cx, cy = pr.to_screen(Vector((0.0, 0.0, 0.0)))[:2]
msg = ce.perform_closed(C, 'CUT', [cap], [ce.rect_loop((cx - 20, cy - 20), (cx + 20, cy + 20))], pr)
bm = bmesh.new()
bm.from_mesh(cap.data)
v1 = bm.calc_volume()
bm.free()
check('A Cut through a Curved shape (Capsule): the hole taken away, the shape still one closed solid',
      0 < v1 < v0 - 0.01 and solid(cap), (round(v0, 3), round(v1, 3), msg[:60]))

# many
bad = []
for fam in ('POLY', 'CURVE'):
    for plate in (0.0, 0.05):
        for seed in range(1, 101):
            rng = random.Random(seed)
            p = (rs.poly_params(rng, 'MIX', 4, 1.0, 1.0, seed % 2 == 0, plate=plate) if fam == 'POLY'
                 else rs.curve_params(rng, 'MIX', 4, seed % 2 == 0, plate))
            bm, _k = rs.build(p, 32, 1.0)
            if not (rs._closed(bm) and rs._islands(bm) == 1 and bm.calc_volume(signed=True) > 0):
                bad.append((fam, plate, seed))
            bm.free()
check('400 random shapes (both families, solid and plate, every kind, the most slices / cuts / chamfer / taper, '
      'symmetric or not): every one a clean closed solid', not bad, bad[:5])
summary()
