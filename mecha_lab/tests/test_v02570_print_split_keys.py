"""0.24.166 (user: "이거 보면 알듯이 핀 몸통이 큰 쪽이 메쉬에 붙는 거야 - 당연히 프린트 하면 알겠지만 갭이 무조건 있어야 되잖아,
그거도 상정해서 만들어 주고 - 우리 저번에 만들었던 메쉬 따라서 할 수 있는 스플릿으로 만들면 될 거 같아 같이 해서"): keys across any
Split.  ``keys_between`` finds the faces two parts share (a Split's lasso wall, a drawn line's bent cut, a straight
one) and puts keys there - the big end on the smaller part's mesh, the socket in the other a Fit Gap wider all round and
deeper; Print Cut's drag splits along the line as drawn (Split's line) and keys it; "Keys Between 2 Parts" keys any two
selected halves.  Measured on the meshes."""
import json
import math

import numpy as np
from _harness import bpy, check, fresh, summary
import bmesh  # noqa: E402  (after bpy)
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce, print3d as p3  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=1000.0)       # (looking down: 1000 px = 1 m, (500, 500) = origin)


def px(x, y):
    return (500 + x * 1000, 500 + y * 1000)


def closed(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    ok = not any(e.is_boundary for e in bm.edges) and all(e.is_manifold for e in bm.edges)
    v = abs(bm.calc_volume())
    bm.free()
    return ok, v


def world_co(o):
    C.view_layer.update()
    m = np.array(o.matrix_world)
    return np.array([v.co for v in o.data.vertices]) @ m[:3, :3].T + m[:3, 3]


def block(sx, sy, sz, name='Block'):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, sz / 2))
    ob = C.active_object
    ob.scale = (sx, sy, sz)
    with C.temp_override(object=ob, active_object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    ob.name = name
    return ob


def half_width(pts, c, n, x, z0, z1, reach):
    """A square's half width round the axis (c, n) between heights z0 - z1 above c (its sides along x)."""
    d = pts - c
    h = d @ n
    m = (h > z0) & (h < z1)
    q = d[m] - np.outer(h[m], n)
    y = np.cross(n, x)
    a, b_ = np.abs(q @ x), np.abs(q @ y)
    r_ = np.maximum(a, b_)
    r_ = r_[r_ < reach]
    return float(np.median(r_)) if len(r_) else 0.0


pg = S.mch_print
pg.pin_style, pg.pin_count, pg.pin_auto, pg.clearance = 'KEY', 'AUTO', True, 0.2
check('the window\'s gap is called Fit Gap (mm), 0.2 by default',
      pg.bl_rna.properties['clearance'].name == 'Fit Gap (mm)' and abs(pg.clearance - 0.2) < 1e-6)

# 1) the Split tool's line, bent (a V across a 160 x 60 x 80 mm block, seen from above): two parts touching along it
ob = block(0.16, 0.06, 0.08)
v0 = closed(ob)[1]
path = [px(-0.03, -0.06), px(0.01, 0.0), px(-0.03, 0.06)]           # (a V: the cut bends at the middle)
S.mch_cut.split_mode = 'NORMAL'
ce.perform_line(C, 'SPLIT', [ob], path, TOP, path[0])
parts = [o for o in bpy.data.objects if o.type == 'MESH']
a_, b_ = parts if len(parts) == 2 else (None, None)
bma, pieces = p3.shared_faces(C, a_, b_) if a_ else (None, [])
nfaces = sum(len(pc) for pc in pieces)
nrm = {tuple(np.round(np.array(f.normal), 3)) for pc in pieces for f in pc}
if bma is not None:
    bma.free()
check(f'a Split along a bent line: two parts, the faces they share found ({nfaces} faces, {len(nrm)} directions - the V\'s '
      f'two sides)', len(parts) == 2 and nfaces >= 2 and len(nrm) == 2, (len(parts), nfaces, nrm))
carrier, other = p3.key_carrier(a_, b_)
pins, msg = p3.keys_between(C, carrier, other)
(c1, va), (c2, vb) = closed(carrier), closed(other)
info = json.loads(carrier['mch_print_pins'])
check(f'...Keys Between: one key on the smaller part, closed parts ({msg})',
      c1 and c2 and len(info['pins']) == 1 and info['on'] == carrier.name and closed(carrier)[1] <= closed(other)[1] + 1e-4,
      (c1, c2, info['pins']))
c = np.array(info['pins'][0])
n = np.array(info['normals'][0])
x = np.array(info['axes'][0])
r, L, t = info['radius'], info['length'], info['clearance']
wa, wb = world_co(carrier), world_co(other)
stick = float(((wa - c) @ n).max())
check(f'...the key stands out of the smaller part {stick * 1000:.1f} mm (its length {L * 1000:.1f}) along the way the parts '
      f'come apart - straight out of the V ({np.round(n, 3).tolist()}), not along its side of the V (it would lock them)',
      abs(stick - L) < 1e-5 and abs(abs(n[0]) - 1.0) < 1e-3 and info['one_way'])
k0 = half_width(wa, c, n, x, -1e-6, 1e-6, r * 1.5)
s0 = half_width(wb, c, n, x, -1e-6, 1e-6, r * 1.6)
k1 = half_width(wa, c, n, x, L * 0.5, stick - 1e-6, r * 1.5)
deep = float(((wb - c) @ n)[np.linalg.norm(np.cross(wb - c, n), axis=1) < r * 1.6].max())
check(f'...its big end on the part\'s mesh ({k0 * 2000:.2f} mm), narrowing into the other ({k1 * 2000:.2f} mm)',
      k1 < k0 * 0.95, (k0, k1))
check(f'...the socket a gap wider all round ({s0 * 2000:.2f} mm: {(s0 - k0) * 1000:.2f} mm each side) and deeper '
      f'({deep * 1000:.1f} mm for a {L * 1000:.1f} mm key)', abs((s0 - k0) - t) < 2e-5 and abs(deep - (L + t)) < 1e-5,
      (k0, s0, deep))
check(f'...the key off the bend of the cut (in one side of the V), the volumes add up to the block '
      f'({(va + vb) * 1e6:.2f} cm3 vs {v0 * 1e6:.2f} - the gap\'s sliver out, nothing doubled)',
      (va + vb) <= v0 + 1e-9 and abs((va + vb) - v0) < v0 * 0.01, (va + vb, v0))

# 2) the Split tool's lasso round the block's end (seen from above): the cut a curved wall across it
ob = block(0.16, 0.06, 0.06)
ring = [px(0.09 + 0.05 * math.cos(a), 0.05 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 64, endpoint=False)]
ce.perform_closed(C, 'SPLIT', [ob], [ring], TOP)
parts = [o for o in bpy.data.objects if o.type == 'MESH']
pg.pin_style = 'PEG'
carrier, other = p3.key_carrier(*parts)
pins, msg = p3.keys_between(C, carrier, other)
info = json.loads(carrier['mch_print_pins'])
ns = np.array(info['normals'])
check(f'a lasso Split round the block\'s end (a curved cut): pegs on the end ({carrier.name}), all along the way it comes '
      f'off ({np.round(ns[0], 3).tolist()}), closed parts ({msg})', len(ns) == 2 and info['one_way']
      and all(abs(abs(nv[0]) - 1.0) < 1e-3 for nv in ns) and closed(carrier)[0] and closed(other)[0]
      and carrier.name.endswith('_Split'), (len(ns), ns.tolist()))
# ... a lasso through the middle (a round core: a plug in its hole) - each peg along the wall there, and a note
ob = block(0.12, 0.12, 0.06)
ring = [px(0.035 * math.cos(a), 0.035 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 48, endpoint=False)]
ce.perform_closed(C, 'SPLIT', [ob], [ring], TOP)
parts = [o for o in bpy.data.objects if o.type == 'MESH']
carrier, other = p3.key_carrier(*parts)
pins, msg = p3.keys_between(C, carrier, other)
info = json.loads(carrier['mch_print_pins'])
ns, cs = np.array(info['normals']), np.array(info['pins'])
radial = [abs(np.dot(nv[:2] / max(np.linalg.norm(nv[:2]), 1e-9), cc[:2] / max(np.linalg.norm(cc[:2]), 1e-9)))
          for nv, cc in zip(ns, cs)]
check(f'a round core through the block (it slides out along the view): each peg along the wall there (radial '
      f'{min(radial):.3f}) and a note to check it goes together ({msg})', not info['one_way'] and min(radial) > 0.99
      and 'wraps round' in msg)

# 3) two parts that do not touch: refused
ob = block(0.05, 0.05, 0.05)
bpy.ops.mesh.primitive_cube_add(size=0.05, location=(0.2, 0, 0.025))
far = C.active_object
try:
    p3.keys_between(C, ob, far)
    refused = False
except p3.PrintError as ex:
    refused = 'do not touch' in str(ex)
check('two parts that do not touch: refused, nothing changed', refused and len(ob.data.polygons) == 6)

# 4) Print Cut's drag: the line as drawn (Split's line), keys on the smaller part, the original hidden
pg.pin_style = 'KEY'
ob = block(0.16, 0.06, 0.08, 'Arm')
a, b, pins, msg = p3.cut_along_line(C, ob, path, TOP)
info = json.loads(a['mch_print_pins'])
check(f'Print Cut along a drawn (bent) line: "{a.name}" and "{b.name}", closed, one key, the original hidden ({msg})',
      closed(a)[0] and closed(b)[0] and len(info['pins']) == 1 and ob.hide_get() and a.get(p3.FROM_KEY) == 'Arm'
      and b.get(p3.FROM_KEY) == 'Arm', msg)
# 5) the two halves of a Split, selected: the button
ob = block(0.16, 0.06, 0.08)
ce.perform_line(C, 'SPLIT', [ob], [px(0.02, -0.06), px(0.02, 0.06)], TOP, px(0.02, -0.06))
two = [o for o in bpy.data.objects if o.type == 'MESH']
for o in C.selected_objects:
    o.select_set(False)
for o in two:
    o.select_set(True)
C.view_layer.objects.active = two[0]
r_ = bpy.ops.mch.print_keys()
info = json.loads(two[0]['mch_print_pins'])
small = min(two, key=lambda o: closed(o)[1])
check(f'"Keys Between 2 Parts" with a straight Split\'s halves selected: one key, on the smaller ({info["on"]})',
      'FINISHED' in r_ and len(info['pins']) == 1 and info['on'] == small.name)

# 6) a straight Print Cut near the top (Shift): the key on the smaller part - the top - pointing down into the rest
ob = block(0.08, 0.08, 0.1, 'Post')
neg, pos, pins, msg = p3.cut_with_pins(C, ob, (0, 0, 0.075), (0, 0, 1))
info = json.loads(pos['mch_print_pins'])
wt = world_co(pos)
check(f'a straight cut near the top: the key on the smaller top part ({info["on"]}), pointing down '
      f'({np.round(info["normal"], 3).tolist()}), below the cut {(0.075 - wt[:, 2].min()) * 1000:.1f} mm ({msg})',
      info['on'] == pos.name and info['normal'][2] < -0.999 and abs((0.075 - wt[:, 2].min()) - info['length']) < 1e-5)

# 7) a part with a material: its parts keep one slot each (not doubled by the key's boolean)
ob = block(0.08, 0.08, 0.1, 'Painted')
ob.data.materials.append(bpy.data.materials.new('Paint'))
neg, pos, pins, msg = p3.cut_with_pins(C, ob, (0, 0, 0.05), (0, 0, 1))
check(f'a part with one material: its two parts keep one slot each ({len(neg.data.materials)}, {len(pos.data.materials)})',
      len(neg.data.materials) == 1 and len(pos.data.materials) == 1)

mecha_lab.unregister()
summary()
