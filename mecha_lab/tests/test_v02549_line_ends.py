"""0.24.143 (user: "아머 플레이트, 서페이스 드로우, 플레이트 디테일 시리즈, 크리쳐 플레이트에 모두 끝부분 뾰족해지고 끝부분이 둥글어지는
테이퍼? 그 옵션 넣어 줘"): Line Ends Round / Flat / Pointed for every Line-mode plate tool (the band's outline), and
Surface Draw's own Ends Square / Round / Pointed (+ Taper), live."""
import math

from _harness import bpy, check, fresh, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import armor_plate as ap, core_geometry as cg, lasso_line as ll, surface_draw as sd, tool_state as ts  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
br = S.mch_brush
P = cg.OrthoProjector(Quaternion())


def area(loop):
    return 0.5 * abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(loop, loop[1:] + loop[:1])))


def width_near(loop, x):
    ys = [p[1] for p in loop if abs(p[0] - x) < 6]
    return (max(ys) - min(ys)) if ys else 0.0


path = [(200 + i * 15, 500) for i in range(41)]           # a straight line 600 px long
items = [i.identifier for i in br.bl_rna.properties['line_caps'].enum_items]
check('Line Ends: Round, Flat and Pointed', items == ['ROUND', 'FLAT', 'POINT'], items)
br.line_mode, br.line_width, br.line_taper_on, br.line_taper = True, 0.4, False, 0.6
loops = {}
for cap in ('ROUND', 'FLAT', 'POINT'):
    br.line_caps = cap
    loops[cap] = ll.line_loops(C, P, path, br)[0]
check('Pointed: the band thins to points (its tips narrow, much less area); Round: round tips past the line\'s ends; '
      'Flat: square', area(loops['POINT']) < 0.8 * area(loops['ROUND']) and width_near(loops['POINT'], 205) < 0.3 * width_near(loops['FLAT'], 205)
      and min(p[0] for p in loops['ROUND']) < 200 - 15 and area(loops['FLAT']) > area(loops['ROUND']) > area(loops['POINT']),
      {k: round(area(v)) for k, v in loops.items()})
check('ends_of: Pointed = round tips + the Taper Amount; the old Taper button still thins Round / Flat',
      ll.ends_of(type('B', (), {'line_caps': 'POINT', 'line_taper': 0.6, 'line_taper_on': False})()) == ('ROUND', 0.6)
      and ll.ends_of(type('B', (), {'line_caps': 'FLAT', 'line_taper': 0.6, 'line_taper_on': True})()) == ('FLAT', 0.6)
      and ll.ends_of(type('B', (), {'line_caps': 'ROUND', 'line_taper': 0.6, 'line_taper_on': False})()) == ('ROUND', 0.0))
# a Line-mode Armor Plate with Pointed ends on a body
bpy.ops.mesh.primitive_uv_sphere_add(radius=9.0, segments=96, ring_count=48, location=(0, 0, -8.4))
body = C.active_object
br.line_caps = 'POINT'
plate_loops = ll.line_loops(C, P, path, br)
ap.perform_plate(C, plate_loops, P)
plate = C.active_object
xs = [v.co.x for v in plate.data.vertices]
dg = C.evaluated_depsgraph_get()
pv = [plate.matrix_world @ v.co for v in plate.evaluated_get(dg).data.vertices]


def plate_width_at(x):
    ys = [v.y for v in pv if abs(v.x - x) < 0.08]
    return (max(ys) - min(ys)) if ys else 0.0


check('an Armor Plate drawn in Line mode with Pointed ends: narrow at its tips, full width in the middle',
      plate is not body and plate_width_at(0.0) > 0.3 and plate_width_at(-2.9) < 0.5 * plate_width_at(0.0),
      (round(plate_width_at(-2.9), 3), round(plate_width_at(0.0), 3)))
# Surface Draw: Ends Square / Round / Pointed
lens = [0.1 * i for i in range(21)]
sq, rd, pt = (sd.outline_factors(lens, 0.4, e, 0.6) for e in ('SQUARE', 'ROUND', 'POINT'))
check('Surface Draw outline: Square keeps the width to the ends; Round a half circle over the last half width; '
      'Pointed thins to (almost) a point', all(f == 1.0 for f in sq) and rd[0] < 0.05 and abs(rd[1] - math.sqrt(1 - 0.5 ** 2)) < 1e-6
      and rd[10] == 1.0 and pt[0] < 0.05 and 0.05 < pt[3] < 1.0 and pt[10] == 1.0, (rd[:3], pt[:4]))
st = S.mch_sdraw
st.join, st.width, st.height, st.profile, st.ends = False, 0.4, 0.1, 'SQUARE', 'POINT'
for o in C.selected_objects:
    o.select_set(False)
body.select_set(True)
C.view_layer.objects.active = body
sd.perform(C, [(200 + i * 15, 300) for i in range(41)], P)
band = C.active_object


def band_width_at(ob, x):
    vs = [ob.matrix_world @ v.co for v in ob.data.vertices]
    ys = [v.y for v in vs if abs(v.x - x) < 0.06]
    return (max(ys) - min(ys)) if ys else 0.0


w_tip, w_mid = band_width_at(band, -2.95), band_width_at(band, 0.0)
check('a Surface Draw band with Pointed ends: thin at its tips, the full width in the middle',
      band.get(sd.SRC_KEY) and w_mid > 0.35 and w_tip < 0.4 * w_mid, (round(w_tip, 3), round(w_mid, 3)))
band.mch_sdraw.ends = 'SQUARE'
check('... Ends is live: Square - the band rebuilt with full-width ends', band_width_at(band, -2.95) > 0.35,
      round(band_width_at(band, -2.95), 3))

# 0.24.145 (user: "마이너스 테이퍼도 만들어 줘") a minus Taper: the ends flare out instead
check('Taper Amount goes below 0', br.bl_rna.properties['line_taper'].hard_min <= -1.0 and st.bl_rna.properties['taper'].hard_min <= -1.0)
check('taper_factor: a minus taper is 1 in the middle, 1 + |taper| at the very ends',
      ll.taper_factor(0.5, -0.6) == 1.0 and abs(ll.taper_factor(0.0, -0.6) - 1.6) < 1e-9 and 1.0 < ll.taper_factor(0.1, -0.6) < 1.6)
br.line_caps, br.line_taper = 'POINT', -0.8
flared = ll.line_loops(C, P, path, br)[0]
check('a line with Pointed ends and a minus Taper: wider at its ends than in its middle (flared)',
      width_near(flared, 230) > 1.3 * width_near(flared, 500), (round(width_near(flared, 230)), round(width_near(flared, 500))))
band.mch_sdraw.ends, band.mch_sdraw.taper = 'POINT', -0.8
check('Surface Draw: Pointed Ends with a minus Taper - the band\'s ends flare out (live)',
      band_width_at(band, -2.9) > 1.3 * band_width_at(band, 0.0), (round(band_width_at(band, -2.9), 3), round(band_width_at(band, 0.0), 3)))
summary()
