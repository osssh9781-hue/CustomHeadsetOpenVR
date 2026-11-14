"""0.24.165 (user, with photos of a Dovetail Key add-on - an arm cut, square keys sticking out of the cuts - and, asked
what to take from it, "네모난 도브테일 키"; "레퍼런스로 준 거 참고해서 해 줘"): Print Cut's Key - a square key on one
part, narrowing to its tip (the tip chamfered), lying along its piece of the cut, and a square socket a Clearance
wider all round in the other part; square, so Auto puts one on each piece.  Measured on the parts' meshes."""
import json
import math

import numpy as np
from _harness import bpy, check, fresh, summary
import bmesh  # noqa: E402  (after bpy)

import mecha_lab
from mecha_lab import print3d as p3  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
check('Print Cut has a Key style next to Peg and Dowel',
      [i.identifier for i in S.mch_print.bl_rna.properties['pin_style'].enum_items] == ['PEG', 'DOWEL', 'KEY'])


def closed(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    ok = not any(e.is_boundary for e in bm.edges) and all(e.is_manifold for e in bm.edges)
    v = bm.calc_volume()
    bm.free()
    return ok, v


def world_co(o):
    C.view_layer.update()
    m = np.array(o.matrix_world)
    co = np.array([v.co for v in o.data.vertices])
    return co @ m[:3, :3].T + m[:3, 3]


def block(sx, sy, sz):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, sz / 2))
    ob = C.active_object
    ob.scale = (sx, sy, sz)
    C.view_layer.update()
    with C.temp_override(object=ob, active_object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return ob


# a 120 x 60 x 100 mm block cut through its middle, Key, Auto
ob = block(0.12, 0.06, 0.1)
pg = S.mch_print
pg.pin_style, pg.pin_count, pg.pin_auto, pg.clearance = 'KEY', 'AUTO', True, 0.2
neg, pos, pins, msg = p3.cut_with_pins(C, ob, (0, 0, 0.05), (0, 0, 1))
(c1, v1), (c2, v2) = closed(neg), closed(pos)
info = json.loads(neg['mch_print_pins'])
check(f'a 120 x 60 mm block cut with Key: two closed parts, one key (square: it cannot turn), no separate pins ({msg})',
      c1 and c2 and len(info['pins']) == 1 and not pins and info['style'] == 'KEY', (c1, c2, info['pins']))
ax = np.array(info['axes'][0])
check(f'...the key lies along its piece of the cut (the block\'s long way: axis {np.round(ax, 3).tolist()}), in its '
      f'middle ({np.round(np.array(info["pins"][0][:2]) * 1000, 1).tolist()} mm)',
      abs(abs(ax[0]) - 1.0) < 1e-3 and np.linalg.norm(info['pins'][0][:2]) < 0.004)
r, L, t = info['radius'], info['length'], info['clearance']
cen = np.array(info['pins'][0])
wn, wp = world_co(neg), world_co(pos)
top = wn[:, 2].max()
check(f'...the key sticks out of the lower part {(top - 0.05) * 1000:.1f} mm (its length {L * 1000:.1f} mm), '
      f'{2 * r * 1000:.1f} mm wide at the cut', abs((top - 0.05) - L) < 1e-6 and 2 * r > 0.004)


def half_width(pts, z_lo, z_hi):
    """Half width of the square at the centre between z_lo and z_hi (its corners: |a| and |b| the same)."""
    m = pts[(pts[:, 2] > z_lo) & (pts[:, 2] < z_hi)]
    m = m[np.linalg.norm(m[:, :2] - cen[:2], axis=1) < r * 3]
    d = m[:, :2] - cen[:2]
    a = np.abs(d @ ax[:2])
    b = np.abs(d @ np.array([-ax[1], ax[0]]))
    return float(np.median(np.maximum(a, b))) if len(m) else 0.0


k0 = half_width(wn, 0.05 - 1e-6, 0.05 + 1e-6)                                 # (the key's ring at the cut)
s0 = half_width(wp, 0.05 - 1e-6, 0.05 + 1e-6)                                 # (the socket's mouth)
k1 = half_width(wn, 0.05 + L * 0.5, top - 1e-6)                               # (the key near its tip)
check(f'...square socket a Clearance wider all round: key {k0 * 2000:.2f} mm, socket {s0 * 2000:.2f} mm '
      f'({(s0 - k0) * 1000:.2f} mm each side)', abs((s0 - k0) - t) < 2e-5, (k0, s0, t))
check(f'...the key narrows to its tip ({k0 * 2000:.2f} -> {k1 * 2000:.2f} mm, like a dovetail key)',
      k1 < k0 * 0.95 and k1 > k0 * (1 - p3.KEY_TAPER) * 0.9, (k0, k1))
deep = wp[:, 2][np.linalg.norm(wp[:, :2] - cen[:2], axis=1) < r * 1.6].max()          # (its floor's corners)
check(f'...the socket goes {(deep - 0.05) * 1000:.1f} mm in (the key {L * 1000:.1f} + Clearance)',
      abs((deep - 0.05) - (L + t)) < 1e-5)
check(f'...the parts\' volumes still add up to the block (the key in, its socket out: {(v1 + v2) * 1e6:.1f} cm3 vs 720)',
      abs((v1 + v2) - 0.00072) < 0.00072 * 0.01, (v1, v2))

# a cut with two pieces (two legs): a key on each; Count 2: two keys apart
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bm = bmesh.new()
for x in (-0.05, 0.05):
    res = bmesh.ops.create_cube(bm, size=0.04)
    bmesh.ops.translate(bm, verts=res['verts'], vec=(x, 0, 0.02))
me = bpy.data.meshes.new('Legs')
bm.to_mesh(me)
bm.free()
legs = bpy.data.objects.new('Legs', me)
S.collection.objects.link(legs)
neg, pos, pins, msg = p3.cut_with_pins(C, legs, (0, 0, 0.02), (0, 0, 1))
cx = [c[0] for c in json.loads(neg['mch_print_pins'])['pins']]
check(f'two legs: a key on each ({msg})', len(cx) == 2 and min(cx) < 0 < max(cx))
ob = block(0.16, 0.06, 0.1)
pg.pin_count = '2'
neg, pos, pins, msg = p3.cut_with_pins(C, ob, (0, 0, 0.05), (0, 0, 1))
info = json.loads(neg['mch_print_pins'])
ps = np.array(info['pins'])
check(f'Count 2: two keys, apart ({msg})', len(ps) == 2 and np.linalg.norm(ps[0, :2] - ps[1, :2]) > 3 * info['radius'])

# set by hand: Width / Length in mm
ob = block(0.12, 0.06, 0.1)
pg.pin_count, pg.pin_auto, pg.pin_diameter, pg.pin_length = '1', False, 10.0, 12.0
neg, pos, pins, msg = p3.cut_with_pins(C, ob, (0, 0, 0.05), (0, 0, 1))
info = json.loads(neg['mch_print_pins'])
check(f'Auto Size off: Width 10 mm, Length 12 mm ({msg})',
      abs(info['radius'] - 0.005) < 1e-9 and abs(info['length'] - 0.012) < 1e-9 and closed(neg)[0] and closed(pos)[0])

# a slanted cut (the reference's arm): the key along the cut's normal
ob = block(0.06, 0.06, 0.2)
pg.pin_auto, pg.pin_count = True, 'AUTO'
n = np.array((0.0, math.sin(math.radians(30)), math.cos(math.radians(30))))
neg, pos, pins, msg = p3.cut_with_pins(C, ob, (0, 0, 0.1), tuple(n))
info = json.loads(neg['mch_print_pins'])
wn = world_co(neg)
tipd = float(((wn - np.array((0, 0, 0.1))) @ n).max())
check(f'a slanted cut (30 degrees): the key stands out along the cut\'s normal {tipd * 1000:.1f} mm, closed parts ({msg})',
      abs(tipd - info['length']) < 1e-5 and closed(neg)[0] and closed(pos)[0])

mecha_lab.unregister()
summary()
