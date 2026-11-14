"""0.24.163 (user: "약간 주상절리 같은 절벽 스타일도 하나 만들어 줘 - 그건 긋는 방향 따라 높은 곳이 대각선으로 달라지게"):
Plate Detail 4's Columnar Basalt preset - real basalt columns (Voronoi cells, 5 - 7 sided prisms) on the surface under
the outline, rising along the way the outline was drawn (low where it started, high at the far end); Slope, Turn, Flip,
Height Random, Column Size, Joint Gap, Edge Round, Top Tilt; live until Apply.  Outlines through a fixed top view.
The real clicks: tests/gui/basalt_real_window.py."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
import bmesh  # noqa: E402  (after bpy)
from mathutils import Quaternion

import mecha_lab
from mecha_lab import core_geometry as cg, live_subtract as lsub, plate_detail as pd, plate_rough as pr  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)        # (looking down: 100 px = 1, (500, 500) = origin)
check('the Columnar Basalt preset (the 11th of Plate Detail 4): real columns, not the rough rim',
      len(pr.PRESETS) == 11 and pr.preset_values('BASALT')['r_style'] == 'COLUMNS'
      and pr.preset_values('CONCRETE')['r_style'] == 'ROUGH')


def ellipse(cx, cy, rx, ry, start=0.0, n=64):
    a = np.linspace(0, 2 * math.pi, n, endpoint=False) + start
    return [[(500 + (cx + rx * math.cos(t)) * 100, 500 + (cy + ry * math.sin(t)) * 100) for t in a]]


def pick(ob):
    for o in C.selected_objects:
        o.select_set(False)
    if ob is not None:
        ob.select_set(True)
    C.view_layer.objects.active = ob


def make(target, loop, preset='BASALT'):
    pick(None)
    bpy.ops.mch.pdetail_rough_preset(preset=preset)
    pick(target)
    pd.perform(C, loop, TOP, 'DETAIL4')
    return C.active_object


def tops(ob):
    """(x, y, z) of each column's top (the faces facing up, above the surface)."""
    me = ob.data
    return np.array([tuple(f.center) for f in me.polygons if f.normal.z > 0.95 and f.center.z > 1e-3])


def pieces(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    seen, k = set(), 0
    for v in bm.verts:
        if v in seen:
            continue
        k += 1
        st = [v]
        seen.add(v)
        while st:
            x = st.pop()
            for e in x.link_edges:
                w = e.other_vert(x)
                if w not in seen:
                    seen.add(w)
                    st.append(w)
    bm.free()
    return k


def corr(a, b):
    return float(np.corrcoef(a, b)[0, 1])


def rebuild(ob):
    pd._rebuild_timer()                 # (the slider's debounce timer, run now: no event loop here)
    return ob


for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_plane_add(size=10.0)
ground = C.active_object
a = make(ground, ellipse(-2.0, 0, 1.3, 0.8, start=math.pi))      # drawn from the left end
p = a.mch_pdetail
T = tops(a)
side = [f for f in a.data.polygons if abs(f.normal.z) < 0.05]
check(f'drawn on a plane: basalt columns ({len(T)} of them, 5 - 7 sided, straight up: {len(side):,} side faces '
      f'vertical), no Rough Rim modifier, live', pd.is_detail(a) and p.r_style == 'COLUMNS' and len(T) > 60
      and a.modifiers.get(pr.MOD) is None and len(side) > len(T) * 4 and pieces(a) == len(T))
sides_per = [len(f.vertices) for f in a.data.polygons if f.normal.z > 0.95 and f.center.z > 1e-3]
nb = np.bincount(sides_per, minlength=9)
check(f'...the columns 5 - 7 sided, not a perfect honeycomb (5: {nb[5]}, 6: {nb[6]}, 7: {nb[7]}, others {len(sides_per) - nb[5:8].sum()})',
      nb[5:8].sum() > 0.9 * len(sides_per) and nb[6] < 0.85 * len(sides_per) and nb[5] + nb[7] > 0.12 * len(sides_per),
      [int(x) for x in nb])
c1 = corr(T[:, 0], T[:, 2])
check(f'...drawn from the left: they rise to the right (height vs x correlation {c1:.2f}), from '
      f'{T[:, 2].min() * 1000:.0f} to {T[:, 2].max() * 1000:.0f} mm (Height {p.r_height * 1000:.0f} mm)',
      c1 > 0.8 and T[:, 2].max() > 0.8 * p.r_height and T[:, 2].min() < 0.4 * p.r_height, c1)
b = make(ground, ellipse(2.0, 0, 1.3, 0.8, start=0.0))           # drawn from the right end
Tb = tops(b)
c2 = corr(Tb[:, 0], Tb[:, 2])
check(f'the same outline drawn from the right: they rise to the left ({c2:.2f})', c2 < -0.8, c2)
c = make(ground, ellipse(0.0, 2.6, 1.3, 0.8, start=-math.pi / 2))  # drawn from the bottom
Tc = tops(c)
cy_, cx_ = corr(Tc[:, 1], Tc[:, 2]), corr(Tc[:, 0], Tc[:, 2])
check(f'drawn from the bottom of a wide outline: they rise toward its far top corner - a diagonal (height vs y {cy_:.2f}, '
      f'vs x {cx_:.2f})', cy_ > 0.4 and abs(cx_) > 0.3, (cy_, cx_))
for o in (b, c):
    bpy.data.objects.remove(o)

# the values (live: rebuilt once the slider stops)
pick(a)
p.r_flip = True
check('a value change waits for the slider to stop (one rebuild queued)', a.name in pd._PENDING)
rebuild(a)
cf = corr(tops(a)[:, 0], tops(a)[:, 2])
check(f'Flip: high where it started instead ({c1:.2f} -> {cf:.2f})', cf < -0.8, cf)
p.r_flip = False
p.r_turn = math.radians(90)
rebuild(a)
Tt = tops(a)
check(f'Turn 90: rising across instead (vs x {corr(Tt[:, 0], Tt[:, 2]):.2f}, vs y {corr(Tt[:, 1], Tt[:, 2]):.2f})',
      abs(corr(Tt[:, 0], Tt[:, 2])) < 0.4 and abs(corr(Tt[:, 1], Tt[:, 2])) > 0.7)
p.r_turn = 0.0
p.r_slope = 0.0
p.r_hrand = 0.0
p.r_tilt = 0.0
rebuild(a)
T0 = tops(a)
check(f'Slope 0, Height Random 0, Top Tilt 0: every column as tall as Height ({T0[:, 2].mean() * 1000:.1f} mm, spread '
      f'{np.ptp(T0[:, 2]) * 1000:.2f} mm)', np.ptp(T0[:, 2]) < 0.002 * p.r_height + 1e-5
      and abs(T0[:, 2].mean() - p.r_height) < 0.05 * p.r_height, (np.ptp(T0[:, 2]), T0[:, 2].mean(), p.r_height))
p.r_hrand = 0.5
rebuild(a)
check(f'Height Random 0.5: the columns differ ({np.std(tops(a)[:, 2]) / p.r_height:.0%} of Height)',
      np.std(tops(a)[:, 2]) > 0.1 * p.r_height)
p.r_slope, p.r_hrand, p.r_tilt = 0.85, 0.3, math.radians(5)
n0 = len(tops(rebuild(a)))
f0 = len(a.data.polygons)
p.r_feature *= 0.5
n1 = len(tops(rebuild(a)))
check(f'Column Size halved: about 4 x the columns ({n0} -> {n1})', n1 > 2.8 * n0, (n0, n1))
p.r_feature *= 2.0
rebuild(a)
r0 = p.r_round
p.r_round = 0.0
rebuild(a)
check(f'Edge Round 0: no chamfer ring on the tops (faces {f0:,} -> {len(a.data.polygons):,})', len(a.data.polygons) < f0 * 0.8)
p.r_round = r0
rebuild(a)
# remembered: the next one is Columnar Basalt with the edited Slope
p.r_slope = 0.5
rebuild(a)
pick(ground)
pd.perform(C, ellipse(0.0, -2.5, 0.8, 0.6, start=math.pi), TOP, 'DETAIL4')
nx = C.active_object
check('the next plate starts from it: Columnar Basalt, Slope 0.5', nx.mch_pdetail.r_style == 'COLUMNS'
      and abs(nx.mch_pdetail.r_slope - 0.5) < 1e-6 and nx.modifiers.get(pr.MOD) is None)
bpy.data.objects.remove(nx)

# a rough preset on it: the rough plate again (its modifier), and back
pick(a)
bpy.ops.mch.pdetail_rough_preset(preset='CONCRETE')
check('the Concrete preset on it: a rough-rim plate again (the modifier back)', p.r_style == 'ROUGH'
      and a.modifiers.get(pr.MOD) is not None)
bpy.ops.mch.pdetail_rough_preset(preset='BASALT')
check('...and Columnar Basalt again: columns, no modifier, still rising to the right',
      p.r_style == 'COLUMNS' and a.modifiers.get(pr.MOD) is None and corr(tops(a)[:, 0], tops(a)[:, 2]) > 0.8)

# Alt over it: a hole; Apply
n_before = len(tops(a))
msg = lsub.perform(C, 'DETAIL', [ellipse(-2.0, 0, 0.35, 0.3)[0]], TOP, tool='DETAIL4')
co = np.array([v.co for v in a.data.vertices])
inner = (np.hypot((co[:, 0] + 2.0) / 0.3, co[:, 1] / 0.25) < 1.0)
check(f'Alt + draw on it: that area cut out, still live ({msg})', 'Cut out' in msg and inner.sum() == 0 and pd.is_detail(a))
pick(a)
nf = len(a.data.polygons)
bpy.ops.mch.pdetail_apply()
check('Apply: a plain mesh as it is', not pd.is_detail(a) and len(a.data.polygons) == nf and not a.modifiers)

# on a curved surface: the columns stand on it, all parallel
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_uv_sphere_add(radius=3.0, segments=64, ring_count=32, location=(0, 0, -3.0))
ball = C.active_object
s_ = make(ball, ellipse(0.0, 0.0, 1.2, 0.8, start=math.pi))
co = np.array([v.co for v in s_.data.vertices])                   # (the ball's own space: the plate is parented to it)
rad = np.linalg.norm(co, axis=1)
sides = [f.normal for f in s_.data.polygons if abs(f.normal.z) < 0.05]
col_ = s_.mch_pdetail.r_feature
check(f'on a sphere: the columns stand on it - all parallel ({len(sides):,} vertical sides), so on its sloping part a '
      f'foot goes into it, never more than a column\'s width (deepest {3.0 - rad.min():.3f}, Column Size {col_:.3f}); '
      f'rising to the right ({corr(tops(s_)[:, 0], tops(s_)[:, 2]):.2f})',
      3.0 - col_ < rad.min() < 3.0 and len(sides) > 200 and corr(tops(s_)[:, 0], tops(s_)[:, 2]) > 0.6)

# Alt over a plain mesh: engraved as columns
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=8, location=(0, 0, -4))
cube = C.active_object


def vol(o):
    bm_ = bmesh.new()
    bm_.from_mesh(o.data)
    v = bm_.calc_volume()
    bm_.free()
    return v


v0 = vol(cube)
pick(cube)
msg = lsub.perform(C, 'DETAIL', ellipse(0.0, 0.0, 1.0, 0.7, start=math.pi), TOP, tool='DETAIL4')
check(f'Alt over a plain mesh: the columns engraved into it ({msg}; {v0 - vol(cube):.3f} m3 out)',
      'Engraved' in msg and vol(cube) < v0 and len(bpy.data.objects) == 1)

mecha_lab.unregister()
summary()
