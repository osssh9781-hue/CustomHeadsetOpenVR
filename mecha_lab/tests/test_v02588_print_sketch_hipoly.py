"""0.24.177 (user: "그 3d 프린트 메뉴 하이폴도 되게 해 주고 스케치 모드도 되게 해 줘, 너무 한 번에 그어야 되는디?"):
- Print Cut Sketch: the cut line drawn in pieces (each drag a piece, joined end to end whichever way round), Enter cuts
  along them all, Backspace takes the last piece off, Esc clears; one straight piece: the plane cut;
- a heavy part (300 k triangles and more) shows its Light Copy (10 %) in the viewport: the print parts are made from
  the part itself (before: from the copy - 327 k faces -> 18 k + 16 k), its halves do not carry its copy, and the keys
  go in (before: "do not touch along a cut"); a line cut puts the part through Fix Mesh once (before: twice)."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Euler, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, light_copies as lc, mesh_fix, print3d as p3  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)


def px(x, z):
    return tuple(FRONT.to_screen(Vector((x, -3.0, z))))


def unselect():
    for o in C.selected_objects:
        o.select_set(False)
    C.view_layer.objects.active = None


bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=6, radius=1.0)
ball = C.active_object
ball.name = 'Ball'
unselect()
# the line in three pieces - the second drawn backwards, the third before the first
line = [(x, 0.1 + 0.25 * math.sin(x * 2.2)) for x in np.linspace(-1.5, 1.5, 61)]
pieces = [line[20:41], line[40:61][::-1], line[0:21]]
p3.sketch_clear()
for k, pc in enumerate(pieces):
    p3.sketch_add(C, [px(x, z) for x, z in pc], False, FRONT, Vector((0, 0, 0)))
joined = p3.sketch_path()
first = np.array(joined[0])
last = np.array(joined[-1])
ends = sorted([px(*line[0]), px(*line[-1])])
check(f'three pieces (one backwards, one before the first) joined into one line end to end ({len(joined)} points, '
      f'from {np.round(first).tolist()} to {np.round(last).tolist()})', p3.sketch_count() == 3
      and sorted([tuple(np.round(first)), tuple(np.round(last))]) == [tuple(np.round(e)) for e in ends])
r = bpy.ops.mch.print_cut_sketch(action='LAST')
check(f'Backspace: the last piece off ({p3.sketch_count()} left)', r == {'FINISHED'} and p3.sketch_count() == 2)
p3.sketch_add(C, [px(x, z) for x, z in pieces[2]], False, FRONT, Vector((0, 0, 0)))
r = bpy.ops.mch.print_cut_sketch(action='CUT')
parts = [o for o in S.objects if o.get(p3.FROM_KEY) == 'Ball' and o.type == 'MESH' and not o.get(p3.PIN_KEY)]
info = parts[0].get('mch_print_pins') if parts else None
check(f'Enter: cut along the whole line - two parts ({[o.name for o in parts]}), keys between them, the sketch gone',
      r == {'FINISHED'} and len(parts) == 2 and info and p3.sketch_count() == 0 and not ball.visible_get())
r = bpy.ops.mch.print_cut_sketch(action='CLEAR')
check('Esc with nothing sketched: passes on (leaves the tool as before); Enter with nothing: passes on',
      p3.sketch_count() == 0)
# one straight piece: the plane cut
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(4.0, 0.0, 0.0))
box = C.active_object
box.name = 'Box'
unselect()
p3.sketch_add(C, [px(3.2, 0.1), px(4.8, 0.1)], True, FRONT, Vector((4.0, 0.0, 0.0)))
msg = p3.sketch_commit(C)
bparts = [o for o in S.objects if o.get(p3.FROM_KEY) == 'Box' and not o.get(p3.PIN_KEY)]
check(f'one straight piece: the plane cut ({msg[:60]}...)', len(bparts) == 2 and 'into 2 parts' in msg)
# a heavy part showing its Light Copy
for o in list(S.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=8, radius=1.2)        # 327,680 faces
heavy = C.active_object
heavy.name = 'Heavy'
lc.make_now(heavy, C)
lc._mod(heavy).show_viewport = True
unselect()
C.view_layer.update()
shown = len(heavy.evaluated_get(C.evaluated_depsgraph_get()).data.polygons)
a, b, _pins, msg = p3.cut_with_pins(C, heavy, Vector((0, 0, 0.1)), Vector((0, 0, 1)))
check(f'a heavy part showing its Light Copy ({len(heavy.data.polygons):,} faces, {shown:,} shown): the plane cut '
      f'makes its parts from the part itself ({len(a.data.polygons):,} + {len(b.data.polygons):,} faces)',
      shown < 50_000 and len(a.data.polygons) > 120_000 and len(b.data.polygons) > 120_000)
for o in (a, b):
    bpy.data.objects.remove(o)
for o in [o for o in S.objects if o.get(p3.PIN_KEY)]:
    bpy.data.objects.remove(o)
heavy.hide_set(False)
lc._mod(heavy).show_viewport = True
C.view_layer.update()
path = [px(x, 0.15 + 0.12 * math.sin(x * 3)) for x in np.linspace(-1.6, 1.6, 40)]
a2, b2, _p2, msg2 = p3.cut_along_line(C, heavy, p3._simplify(path), FRONT)
mods = [m.name for o in (a2, b2) for m in o.modifiers]
check(f'... and along a drawn line: its halves the part itself ({len(a2.data.polygons):,} + {len(b2.data.polygons):,}), '
      f'not carrying its Light Copy ({mods}), the keys in ({msg2[:70]}...)',
      len(a2.data.polygons) > 120_000 and len(b2.data.polygons) > 120_000 and not mods and 'between' in msg2)
# Fix Mesh once for a line cut of an open part
for o in list(S.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_monkey_add(size=2.0)
mk = C.active_object
unselect()
calls = []
_fm = mesh_fix.fix_mesh


def counting(*a_, **k_):
    calls.append(1)
    return _fm(*a_, **k_)


mesh_fix.fix_mesh = counting
try:
    p3.cut_along_line(C, mk, p3._simplify([px(x, 0.1 + 0.1 * math.sin(x * 3)) for x in np.linspace(-1.6, 1.6, 30)]), FRONT)
finally:
    mesh_fix.fix_mesh = _fm
check(f'a line cut of an open part: Fix Mesh once ({len(calls)} times; before: twice)', len(calls) == 1)
summary()
