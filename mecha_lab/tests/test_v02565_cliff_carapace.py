"""0.24.163 (user, with two photos: a sea cliff - "절벽의 옆면 같은 돌의 깊이 차이가 윗면에 있어야" - and a rock creature's
carapace - "테두리 부분이 외곽 라인 잡듯이 조금 튀어나오고 가운데는 다시 볼록하게 ... 내부는 디테일이 많으면 안 돼, 외곽 부분만
라인, 내부는 릿지 같고"; "높이는 동서남북 기준으로 돌릴 수 있게"): Plate Detail 4's Layered Cliff (a sea cliff's face on the
top: rock plates stacked one on another, set back inward, wavy outlines - the user's sketch "바위 옆 단면이 판이
겹겹" - rising toward a compass direction) and Creature
Carapace (a raised lip along the outline with lines on it, a groove inside, the middle a smooth ridge).  Measured on the
evaluated mesh; outlines through a fixed top view.  The real clicks: tests/gui/basalt_real_window.py."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Quaternion

import mecha_lab
from mecha_lab import core_geometry as cg, plate_detail as pd, plate_rough as pr  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)        # (looking down: 100 px = 1, (500, 500) = origin)


def ellipse(cx, cy, rx, ry, n=72):
    a = np.linspace(0, 2 * math.pi, n, endpoint=False)
    return [[(500 + (cx + rx * math.cos(t)) * 100, 500 + (cy + ry * math.sin(t)) * 100) for t in a]]


def pick(ob):
    for o in C.selected_objects:
        o.select_set(False)
    if ob is not None:
        ob.select_set(True)
    C.view_layer.objects.active = ob


def make(target, loop, preset):
    pick(None)
    bpy.ops.mch.pdetail_rough_preset(preset=preset)
    pick(target)
    pd.perform(C, loop, TOP, 'DETAIL4')
    return C.active_object


def ev(ob):
    me = ob.evaluated_get(C.evaluated_depsgraph_get()).data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    out = {'co': co.reshape(-1, 3)}
    for nm in (pr.TOP_ATTR, pr.D_ATTR, pr.OUT_ATTR):
        at = me.attributes.get(nm)
        a = np.empty(len(me.vertices), np.float32)
        at.data.foreach_get('value', a)
        out[nm] = a
    return out


def corr(a, b):
    return float(np.corrcoef(a, b)[0, 1])


for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_plane_add(size=12.0)
ground = C.active_object

# Layered Cliff
cl = make(ground, ellipse(-2.5, 0, 1.8, 1.1), 'CLIFF')
p = cl.mch_pdetail
e = ev(cl)
top = (e[pr.TOP_ATTR] > 0.5) & (e[pr.D_ATTR] > p.r_ramp * 1.2)
z = e['co'][top, 2]
check(f'Layered Cliff: a live plate with the rough plate\'s modifier, style Cliff (strata, the compass) - top from '
      f'{z.min() * 1000:.0f} to {z.max() * 1000:.0f} mm', pd.is_detail(cl) and p.r_style == 'CLIFF'
      and cl.modifiers.get(pr.MOD) is not None and z.max() > p.r_height * 0.8)
xs = e['co'][top]
cx = corr(xs[:, 0], xs[:, 2])
check(f'...rising toward the compass direction (east by default: height vs x {cx:.2f})', cx > 0.3, cx)
# stacked plates (user's sketch: "바위 옆 단면이 판이 겹겹"): the top in steps Plate Thickness high - most of it at a
# whole number of plates (tilted a little) - the outermost plate one thick at the outline, higher plates set back inward
lay = p.r_layer


def levels(e_):
    t_ = (e_[pr.TOP_ATTR] > 0.5)
    zz = e_['co'][t_, 2]
    return zz, e_[pr.D_ATTR][t_]


zz, dd = levels(e)
hist, edges_ = np.histogram(zz, bins=int(max(zz.max() / (lay * 0.1), 10)))
peaks = int(((hist[1:-1] > hist[:-2]) & (hist[1:-1] > hist[2:]) & (hist[1:-1] > len(zz) * 0.01)).sum())
check(f'...plates stacked: the top\'s heights gather at {peaks} levels (about every Plate Thickness, '
      f'{lay * 1000:.0f} mm), not spread evenly', peaks >= 3, peaks)
ring = (dd > lay * 0.7) & (dd < lay * 1.5)               # (in from the outline: Chips bite up to about half a plate)
inner = dd > p.r_ramp * 0.8
h_ring, h_in = float(np.median(zz[ring])), float(np.median(zz[inner]))
check(f'...the outermost plate about one thick at the outline ({h_ring * 1000:.0f} mm, Plate Thickness {lay * 1000:.0f} mm), '
      f'the plates set back inward stand higher ({h_in * 1000:.0f} mm)', 0.4 * lay < h_ring < 1.6 * lay and h_in > 3 * lay,
      (h_ring, h_in))
p.r_layer = lay * 0.5
zz2, _dd2 = levels(ev(cl))
hist2, _e2 = np.histogram(zz2, bins=int(max(zz2.max() / (lay * 0.05), 10)))
peaks2 = int(((hist2[1:-1] > hist2[:-2]) & (hist2[1:-1] > hist2[2:]) & (hist2[1:-1] > len(zz2) * 0.005)).sum())
check(f'...Plate Thickness halved: more, thinner plates ({peaks} -> {peaks2} levels)', peaks2 > peaks, (peaks, peaks2))
p.r_layer = lay
h_a = ev(cl)['co'][top, 2]
p.r_depth = p.r_depth * 2.0
h_b = ev(cl)['co'][top, 2]
check(f'...Wavy Outlines: the plates\' outlines change ({np.abs(h_a - h_b).mean() * 1000:.1f} mm on average)',
      np.abs(h_a - h_b).mean() > 0.1 * lay)
p.r_depth = p.r_depth * 0.5
for key, axis, sign in (('N', 1, 1), ('W', 0, -1)):
    pick(cl)
    bpy.ops.mch.pdetail_compass(direction=key)
    e2 = ev(cl)
    t2 = (e2[pr.TOP_ATTR] > 0.5) & (e2[pr.D_ATTR] > p.r_ramp * 1.2)
    c2 = corr(e2['co'][t2, axis], e2['co'][t2, 2]) * sign
    check(f'...the {key} button: rising toward {"-+"[sign > 0]}{"xy"[axis]} ({c2:.2f})', c2 > 0.3, c2)
p.r_slope = 0.0
dip0, dep0 = p.r_dip, p.r_depth
p.r_dip = 0.0                                                       # (and the plates not tilted, not wavy: level)
p.r_depth = 0.0
e3 = ev(cl)
t3 = (e3[pr.TOP_ATTR] > 0.5) & (e3[pr.D_ATTR] > p.r_ramp * 1.2)
check(f'...Slope 0, Plate Tilt 0, Wavy 0: level (height vs x {corr(e3["co"][t3, 0], e3["co"][t3, 2]):.2f}, vs y {corr(e3["co"][t3, 1], e3["co"][t3, 2]):.2f})',
      abs(corr(e3['co'][t3, 0], e3['co'][t3, 2])) < 0.3 and abs(corr(e3['co'][t3, 1], e3['co'][t3, 2])) < 0.3)
p.r_dip, p.r_depth = dip0, dep0
pick(cl)
n_ev = len(cl.evaluated_get(C.evaluated_depsgraph_get()).data.polygons)
bpy.ops.mch.pdetail_apply()
check('...Apply: a plain mesh as it was', not pd.is_detail(cl) and len(cl.data.polygons) == n_ev)

# Creature Carapace
ca = make(ground, ellipse(2.5, 0, 1.8, 1.1), 'CARAPACE')
q = ca.mch_pdetail
e = ev(ca)
tp = e[pr.TOP_ATTR] > 0.5
d = e[pr.D_ATTR]
zc = e['co'][:, 2]
w = q.r_ramp
deep = d[tp].max()


def at(lo, hi):
    m = tp & (d >= lo) & (d < hi)
    return float(np.median(zc[m]))


lip, groove, mid, crest = at(0.85 * w, 1.15 * w), at(2.0 * w, 2.4 * w), at(0.45 * deep, 0.55 * deep), at(0.92 * deep, deep + 1)
check(f'Creature Carapace: a raised lip along the outline ({lip * 1000:.0f} mm), a groove inside it ({groove * 1000:.0f} mm), '
      f'then up again to the middle ({mid * 1000:.0f} -> {crest * 1000:.0f} mm)', q.r_profile == 'CARAPACE'
      and lip > groove * 1.2 and crest > mid > groove and crest > lip, (lip, groove, mid, crest))
r = e[pr.OUT_ATTR]
rim = tp & (d < q.r_rim * 0.6) & (d > w * 0.3)
inside = tp & (d > q.r_rim * 2.0)
check(f'...lines only along the outline: texture std at the rim {np.std(r[rim]):.3f}, inside {np.std(r[inside]):.4f} '
      f'(clean inside)', np.std(r[rim]) > 0.05 and np.std(r[inside]) < 0.1 * np.std(r[rim]), (np.std(r[rim]), np.std(r[inside])))
# the middle a ridge: a crest along the outline's middle line - halfway in, lower than a round dome would be
q.r_ridge = 0.0
e0 = ev(ca)
mid0 = float(np.median(e0['co'][:, 2][tp & (d >= 0.45 * deep) & (d < 0.55 * deep)]))
check(f'...Ridge 0.8: the middle a crest (halfway in {mid * 1000:.0f} mm; Ridge 0, a round dome: {mid0 * 1000:.0f} mm, '
      'the crest the same)', mid < mid0 - 0.01 * q.size * 0.02, (mid, mid0))
q.r_ridge = 0.8
q.r_lip = 0.0
e1 = ev(ca)
g1 = float(np.median(e1['co'][:, 2][tp & (d >= 2.0 * w) & (d < 2.4 * w)]))
check(f'...Lip 0: no groove (inside the lip {groove * 1000:.0f} -> {g1 * 1000:.0f} mm)', g1 > groove * 1.3, (groove, g1))

mecha_lab.unregister()
summary()
