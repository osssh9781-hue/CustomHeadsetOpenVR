"""0.24.163 (user, with a screenshot of "The outline crosses itself" warning: "타블렛으로 하면 이런 경고 - 마우스로 하면
되는데"): a pen stroke runs past its start, hooks as the pen lifts, knots on a wobble - small loops where the outline
crosses itself.  Every outline is now untangled first (the closing overshoot trimmed, small loops cut off at their
crossing); only a real figure 8 (two big loops) is still refused.  Then a real Cut and a Plate Detail 4 from such an
outline.  The real drag: tests/gui/pen_overshoot_real_window.py."""
import math

from _harness import bpy, check, fresh, summary
import bmesh  # noqa: E402  (after bpy)
from mathutils import Quaternion

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce, plate_detail as pd  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context


def circle(cx, cy, r, a0=0.0, a1=2 * math.pi, step=6.0):
    n = max(8, int(r * (a1 - a0) / step))
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def area_of(loops):
    g = cg.prepare_loops(loops)
    return abs(cg.signed_area(g[0][0])), len(g)


base = circle(500, 500, 200)
clean_area, _n = area_of([base[:-1]])
over = circle(500, 500, 200, 0.0, 2 * math.pi + 0.25)                # past the start
hook = base[:-1] + [(700, 470), (712, 488), (695, 492)]              # a hook as the pen lifts
knot = base[:40] + [(base[40][0] + 6, base[40][1] - 2), (base[40][0] + 2, base[40][1] - 8),
                    (base[40][0] - 3, base[40][1] + 4)] + base[40:-1]   # a tiny knot on a wobble
for name, lp in (('run past its start', over), ('a hook as the pen lifts', hook), ('a tiny knot on a wobble', knot)):
    try:
        a, n = area_of([lp])
        ok = n == 1 and abs(a - clean_area) < 0.01 * clean_area
        detail = (a, clean_area)
    except cg.CutError as ex:
        ok, detail = False, str(ex)
    check(f'a pen outline that crosses itself - {name}: accepted, the shape as drawn (area {detail})', ok, detail)
lobes = [(500 + 200 * math.cos(t), 500 + 120 * math.sin(t)) for t in [i * 2 * math.pi / 90 for i in range(90)]]
second = [(860 + 160 * math.cos(t + math.pi), 500 - 100 * math.sin(t + math.pi)) for t in [i * 2 * math.pi / 70 for i in range(70)]]
fig8 = lobes[:45] + second + lobes[45:]                              # two big loops joined across each other
refused = False
try:
    cg.prepare_loops([fig8])
except cg.CutError as ex:
    refused = 'figure 8' in str(ex) or 'crosses itself' in str(ex)
check('a real figure 8 (two big loops) is still refused, with a message that says so', refused)

# a real Cut with the overshooting outline
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=6.0, location=(0, 0, -3.0))
cube = C.active_object
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)        # (looking down: 100 px = 1, (500, 500) = origin)


def vol(o):
    b = bmesh.new()
    b.from_mesh(o.data)
    v = b.calc_volume()
    b.free()
    return v


v0 = vol(cube)
C.scene.mch_cut.depth_mode = 'THROUGH'
msg = ce.perform_closed(C, 'CUT', [cube], [over], TOP)
check(f'Cut with the overshooting outline: cut (the hole through it, {v0 - vol(cube):.2f} m3 out; {msg})',
      vol(cube) < v0 - 6.0, (v0, vol(cube), msg))

# a Plate Detail 4 with the hooked outline
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_plane_add(size=8.0)
ground = C.active_object
for o in C.selected_objects:
    o.select_set(False)
C.view_layer.objects.active = ground
msg = pd.perform(C, [hook], TOP, 'DETAIL4')
check(f'Plate Detail 4 with the hooked outline: made ({msg})', pd.is_detail(C.active_object), msg)

mecha_lab.unregister()
summary()
