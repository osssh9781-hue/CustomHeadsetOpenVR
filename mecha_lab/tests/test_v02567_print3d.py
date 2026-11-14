"""0.24.164 (user: "3D 프린팅 전용 기능도 하나 만들어 줘 - 사이즈 측정이랑, 사이즈는 수직 수평으로 잴 수 있는 거, 그리고 컷하고 그
사이에 연결 핀 넣어 주는 거"): the 3D Print tools.  Measure: length / horizontal / vertical, locks, kept and removed;
the part's size, the build volume, Scale to Height.  Cut: two closed parts, connection pins across the cut (Peg: a peg
and a hole a Clearance wider; Dowel: holes in both and separate pins), Auto: two on each piece of the cut.  The real
drags: tests/gui/print3d_real_window.py."""
import math
import os

import numpy as np
from _harness import bpy, check, fresh, summary
import bmesh  # noqa: E402  (after bpy)
from mathutils import Vector

import mecha_lab
from mecha_lab import print3d as p3, tool_state as ts, ui_tool_settings as uts  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
icons = os.path.join(os.path.dirname(p3.__file__), 'icons')
check('the 3D Print group: Print Measure and Print Cut - tools with icons and windows',
      dict(ts.TOOL_GROUPS).get('3D Print') == ('PMEASURE', 'PCUT')
      and all(os.path.isfile(os.path.join(icons, ts.TOOL_BY_ID[t][3] + '.png')) for t in ('PMEASURE', 'PCUT'))
      and all(uts.DRAWERS.get(t) is not None for t in ('PMEASURE', 'PCUT')))

# measures
L, H, V = p3.components((0, 0, 0), (0.03, 0.04, 0.12))
check(f'a measure: length {L * 1000:.0f} mm, horizontal {H * 1000:.0f} mm, vertical {V * 1000:.0f} mm',
      abs(L - 0.13) < 1e-6 and abs(H - 0.05) < 1e-6 and abs(V - 0.12) < 1e-6)
a, b = Vector((0, 0, 0)), Vector((0.03, 0.04, 0.12))
check('Shift: straight vertical (above the start) or horizontal (level with it); X / Y / Z: along that axis',
      (p3.constrain(a, b, 'V') - Vector((0, 0, 0.12))).length < 1e-6 and abs(p3.constrain(a, b, 'H').z) < 1e-12
      and (p3.constrain(a, b, 'H') - Vector((0.03, 0.04, 0))).length < 1e-6
      and (p3.constrain(a, b, 'Y') - Vector((0, 0.04, 0))).length < 1e-6)
check('shown in mm (the window\'s unit), cm, inches', p3.fmt(C, 0.123) == '123.0 mm' and (
    setattr(S.mch_print, 'unit', 'CM') or p3.fmt(C, 0.123) == '12.30 cm') and (
    setattr(S.mch_print, 'unit', 'IN') or p3.fmt(C, 0.0254) == '1.00 in'))
S.mch_print.unit = 'MM'
p3.add_measure(S, a, b)
p3.add_measure(S, (1, 0, 0), (1, 0, 0.5))
check('measures kept with the scene', len(p3.measures(S)) == 2)
bpy.ops.mch.print_clear_measures()
check('Clear Measures', len(p3.measures(S)) == 0)

# size, the printer, scale to height
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
box = C.active_object
box.scale = (0.12, 0.08, 0.3)
C.view_layer.update()
sz = p3.size_of(C, [box])
check(f'the selected part\'s size: {sz.x * 1000:.0f} x {sz.y * 1000:.0f} x {sz.z * 1000:.0f} mm',
      abs(sz.x - 0.12) < 1e-6 and abs(sz.y - 0.08) < 1e-6 and abs(sz.z - 0.3) < 1e-6)
straight, turned = p3.fits(C, sz)
check('300 mm tall: too big for a 220 x 220 x 250 printer', not straight and not turned)
S.mch_print.fit_height = 200.0
box.select_set(True)
C.view_layer.objects.active = box
bpy.ops.mch.print_scale_height()
C.view_layer.update()
sz2 = p3.size_of(C, [box])
check(f'Scale to Height 200 mm: {sz2.x * 1000:.1f} x {sz2.y * 1000:.1f} x {sz2.z * 1000:.1f} mm (in proportion, bottom '
      f'where it was), it fits now', abs(sz2.z - 0.2) < 1e-5 and abs(sz2.x / sz2.z - 0.4) < 1e-5
      and all(p3.fits(C, sz2)[:1]) and abs(p3.world_bounds(C, [box])[0].z + 0.15) < 1e-5)


def closed(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    ok = not any(e.is_boundary for e in bm.edges) and not any(not e.is_manifold for e in bm.edges)
    v = bm.calc_volume()
    bm.free()
    return ok, v


def world_co(o):
    C.view_layer.update()                       # (the parts' origins were just moved)
    m = np.array(o.matrix_world)
    co = np.array([v.co for v in o.data.vertices])
    return co @ m[:3, :3].T + m[:3, 3]


# Cut with pins: a 100 mm cube through its middle, horizontally
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0, 0, 0.05))
cube = C.active_object
S.mch_print.pin_style = 'PEG'
S.mch_print.pin_count = 'AUTO'
S.mch_print.pin_auto = True
S.mch_print.clearance = 0.2                                     # (mm)
neg, pos, pins, msg = p3.cut_with_pins(C, cube, (0, 0, 0.05), (0, 0, 1))
(c1, v1), (c2, v2) = closed(neg), closed(pos)
check(f'a 100 mm cube cut through its middle: two closed parts, the original kept hidden ({msg})',
      c1 and c2 and cube.hide_get() and neg.get(p3.FROM_KEY) == cube.name and not pins)
wn, wp = world_co(neg), world_co(pos)
peg_top = wn[:, 2].max()
check(f'...the lower part carries the pegs: up to {peg_top * 1000:.1f} mm (the cut at 50), the upper part has the holes',
      peg_top > 0.05 + 0.005 and wp[:, 2].min() >= 0.05 - 1e-6)
# the pegs: two (Auto), their radius and the holes' radius - the Clearance between (at the pin centres the cut noted)
import json  # noqa: E402
info = json.loads(neg['mch_print_pins'])
centres = [np.array(c[:2]) for c in info['pins']]
L_, t_ = info['length'], info['clearance']
band_n = wn[(wn[:, 2] > 0.0505) & (wn[:, 2] < peg_top - 1e-4)]                   # (the peg's ring under its chamfer)
band_p = wp[(wp[:, 2] > 0.0505) & (wp[:, 2] < 0.05 + L_ + t_ + 1e-4)]             # (the hole's floor ring)


def ring_r(pts, c, r0):
    d = np.linalg.norm(pts[:, :2] - c, axis=1)
    near = d[d < r0 * 1.6]
    return float(np.median(near)) if len(near) else 0.0


rp = np.mean([ring_r(band_n, c, info['radius']) for c in centres])
rh = np.mean([ring_r(band_p, c, info['radius']) for c in centres])
check(f'...Auto: two pins (it cannot turn), {rp * 2000:.1f} mm wide; the holes {rh * 2000:.1f} mm - {(rh - rp) * 1000:.2f} mm '
      f'clearance all round', len(centres) == 2 and abs((rh - rp) - 0.0002) < 0.00004
      and np.linalg.norm(centres[0] - centres[1]) > 3.5 * info['radius'], (len(centres), rp, rh))
check(f'...the parts\' volumes add up to the cube (+ the pegs - the holes: {(v1 + v2) * 1e6:.1f} cm3 vs 1000)',
      abs((v1 + v2) - 0.001) < 0.00002, (v1, v2))

# Dowel: holes in both, separate pins
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0, 0, 0.05))
cube = C.active_object
S.mch_print.pin_style = 'DOWEL'
S.mch_print.pin_count = '3'
S.mch_print.pin_auto = False
S.mch_print.pin_diameter = 6.0                                  # (mm)
S.mch_print.pin_length = 16.0
neg, pos, pins, msg = p3.cut_with_pins(C, cube, (0, 0, 0.05), (0, 0, 1))
(c1, v1), (c2, v2) = closed(neg), closed(pos)
pc = [closed(p) for p in pins]
pz = [world_co(p)[:, 2] for p in pins]
check(f'Dowel, 3 pins, 6 mm x 16 mm: holes in both parts (both lighter than half the cube), 3 separate closed pins '
      f'across the cut ({msg})', c1 and c2 and v1 < 0.0005 and v2 < 0.0005 and len(pins) == 3 and all(ok for ok, _v in pc)
      and all(z.min() < 0.05 < z.max() for z in pz) and all(abs((z.max() - z.min()) - (0.016 - 0.0002)) < 1e-5 for z in pz))

# a part whose cut has two pieces (two legs): pins on each piece
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bm = bmesh.new()
for x in (-0.05, 0.05):
    r = bmesh.ops.create_cube(bm, size=0.04)
    bmesh.ops.translate(bm, verts=r['verts'], vec=(x, 0, 0.02))
me = bpy.data.meshes.new('Legs')
bm.to_mesh(me)
bm.free()
legs = bpy.data.objects.new('Legs', me)
S.collection.objects.link(legs)
S.mch_print.pin_style = 'PEG'
S.mch_print.pin_count = 'AUTO'
S.mch_print.pin_auto = True
neg, pos, pins, msg = p3.cut_with_pins(C, legs, (0, 0, 0.02), (0, 0, 1))
wn = world_co(neg)
peg = wn[wn[:, 2] > 0.0205]
check(f'a part whose cut has two pieces (two legs): pegs on each piece ({msg})',
      (peg[:, 0] < 0).any() and (peg[:, 0] > 0).any())

# a cut that misses
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=0.1)
try:
    p3.cut_with_pins(C, C.active_object, (0, 0, 1.0), (0, 0, 1))
    missed = False
except p3.PrintError as ex:
    missed = 'misses' in str(ex)
check('a cut that misses the part: refused, nothing made', missed and len(bpy.data.objects) == 1)

# the window's middle cut
bpy.ops.mch.print_cut_axis(axis='X')
check('Cut Through the Middle (vertical X): two parts', len([o for o in bpy.data.objects if o.get(p3.FROM_KEY)]) == 2)

mecha_lab.unregister()
check('unregisters', not hasattr(bpy.types.Scene, 'mch_print'))
summary()
