"""0.24.143 Creature Plate Feather (user: "스케일 옵션에서 한 가지 추가해서 깃털 버전 ... 메쉬가 어느 각도 이상 끊기는 부분의
지점에서 걍 일자로 빠지고 그 이후의 부분에서 리프트를 조절" / "거의 처음 부분 위주로 붙는 거 ... 그 붙는 길이만 조절" / "리지같이
가운데 날카로운 버전이랑 ... 깃털의 깃처럼 잇는 옵션"): on the body along Attach Length from the root, then straight out (it
does not follow the body where it turns away), Lift tilts the free part; Vane / Ridge / Shaft cross-sections."""
import math

from _harness import bpy, check, fresh, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, creature_plate as cpl, lasso_line as ll  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
br = S.mch_brush
br.line_mode, br.line_width, br.line_caps, br.line_taper = True, 0.5, 'POINT', 0.5
st = S.mch_cplate
TOP = Quaternion()
check('Creature Plate: a Feather shape with Vane / Ridge / Shaft, Attach Length; live keys',
      'FEATHER' in [i[0] for i in cpl.PROFILE_ITEMS] and [i[0] for i in cpl.FEATHER_STYLES] == ['VANE', 'RIDGE', 'SHAFT']
      and {'feather_style', 'attach'} <= set(cpl.LIVE_KEYS))


def lying_cylinder(y0):
    """A body whose top turns away: a cylinder lying along Y (top at z = 1, it falls away toward x = +-1)."""
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=1.0, depth=1.6, location=(0.0, y0, 0.0),
                                        rotation=(math.radians(90), 0, 0))
    bpy.ops.object.shade_smooth()
    return C.active_object


def plate(profile, y0, style='VANE', attach=0.3, lift=0.0):
    body = lying_cylinder(y0)
    P = cg.OrthoProjector(TOP, center=Vector((0, y0, 0)))
    path = [(500 - 80 + 175 * i / 29, 500) for i in range(30)]        # x = -0.8 .. 0.95: over the top and down its side
    st.profile, st.feather_style, st.attach, st.tip_lift, st.peak, st.end_peak = profile, style, attach, lift, 0.0, -1.0
    for o in C.selected_objects:
        o.select_set(False)
    body.select_set(True)
    C.view_layer.objects.active = body
    cpl.perform(C, ll.line_loops(C, P, path, br), P)
    ob = C.active_object
    return ob, [ob.matrix_world @ v.co for v in ob.data.vertices]


def low_at(vs, x, y0):
    """The plate's underside height near x (its middle line)."""
    zs = [v.z for v in vs if abs(v.x - x) < 0.05 and abs(v.y - y0) < 0.08]
    return min(zs) if zs else None


sc, vs_sc = plate('SCALE', 0.0)
fe, vs_fe = plate('FEATHER', 3.0)
z_sc, z_fe = low_at(vs_sc, 0.85, 0.0), low_at(vs_fe, 0.85, 3.0)
check('drawn over the top and down the side: the Scale bends down with the body, the Feather goes on straight out '
      '(much higher where the body has fallen away)', z_sc is not None and z_fe is not None and z_fe > z_sc + 0.25
      and z_sc < 0.65, (round(z_sc, 3), round(z_fe, 3)))
root = [v for v in vs_fe if v.x < -0.5 and abs(v.y - 3.0) < 0.08]
on_body = min(abs(math.hypot(v.x, v.z) - 1.0) for v in root)
check('... its start lies on the body (the root on the surface, as a scale)', on_body < 0.02, round(on_body, 4))
_lf, vs_lf = plate('FEATHER', 6.0, lift=0.4)
check('Lift tilts the free part up (its tip higher), the root stays', low_at(vs_lf, 0.85, 6.0) > z_fe + 0.15
      and abs(low_at(vs_lf, -0.7, 6.0) - low_at(vs_fe, -0.7, 3.0)) < 0.02,
      (round(low_at(vs_lf, 0.85, 6.0), 3), round(z_fe, 3)))
_lo, vs_lo = plate('FEATHER', 9.0, attach=0.7)
check('a longer Attach Length: more of it on the body (where it leaves comes later - lower there)',
      low_at(vs_lo, 0.6, 9.0) < low_at(vs_fe, 0.6, 3.0) - 0.05, (round(low_at(vs_lo, 0.6, 9.0), 3), round(low_at(vs_fe, 0.6, 3.0), 3)))
fe.mch_cplate.attach = 0.7
vs_live = [fe.matrix_world @ v.co for v in fe.data.vertices]
check('... and it is live (the slider rebuilds the plate)', abs(low_at(vs_live, 0.6, 3.0) - low_at(vs_lo, 0.6, 9.0)) < 0.03)


# cross-sections of the free part (Vane / Ridge / Shaft) on a box edge: drawn on the top, past the edge
def section(style, y0):
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(-1.0, y0, -1.0))
    body = C.active_object
    P = cg.OrthoProjector(TOP, center=Vector((0, y0, 0)))
    path = [(500 + (-80 + 300 * i / 29), 500) for i in range(30)]
    br.line_width = 0.8
    st.profile, st.feather_style, st.attach, st.tip_lift, st.peak, st.end_peak = 'FEATHER', style, 0.3, 0.0, 0.12, 0.08
    for o in C.selected_objects:
        o.select_set(False)
    body.select_set(True)
    C.view_layer.objects.active = body
    cpl.perform(C, ll.line_loops(C, P, path, br), P)
    ob = C.active_object
    vs = [ob.matrix_world @ v.co for v in ob.data.vertices if 1.25 < (ob.matrix_world @ v.co).x < 1.35]
    top = {}
    for v in vs:
        k = round((v.y - y0) / 0.02)
        top[k] = max(top.get(k, -9.0), v.z)
    half = max(abs(k) for k in top) or 1
    base = min(v.z for v in vs)
    mid = max(top[k] for k in top if abs(k) <= 1) - base
    q = [top[k] - base for k in top if 0.4 * half <= abs(k) <= 0.6 * half]
    quarter = sum(q) / len(q) if q else 0.0
    return mid, quarter, max(v.z for v in vs), min(v.z for v in vs)


secs = {s_: section(s_, 12.0 + 3 * i) for i, s_ in enumerate(('VANE', 'RIDGE', 'SHAFT'))}
check('past the box edge the free part is level (straight out, not down the box side)',
      all(abs(sec[3]) < 0.1 and abs(sec[2]) < 0.1 for sec in secs.values()), {k: (round(v[3], 3), round(v[2], 3)) for k, v in secs.items()})
ratio = {k: (v[1] / v[0]) if v[0] > 1e-6 else 0 for k, v in secs.items()}
check('cross-sections: Vane round (its quarter almost as high as its middle), Ridge a sharp middle, Shaft a thin vane '
      'with a narrow crest (the lowest quarter)', ratio['VANE'] > ratio['RIDGE'] > ratio['SHAFT'] + 0.1,
      {k: round(v, 3) for k, v in ratio.items()})

# 0.24.144 (user: "크리쳐 플레이트에서 왜 내가 전에 썼던 값이 적용이 돼서 안 나와?") the next plate: the last plate's style, its
# own sizes (Auto) - a size typed for the next plate is used once
for o in C.selected_objects:
    o.select_set(False)
first = fe                                                   # a live Feather from above
C.view_layer.objects.active = first
first.mch_cplate.edge_thickness = 0.2                        # sizes changed on that plate ...
first.mch_cplate.sink = 0.15
first.mch_cplate.feather_style = 'SHAFT'                     # ... and its style
first.mch_cplate.attach = 0.55
check('changing a live plate: its style goes on to the next plate (Shape, Feather, Attach), its sizes do not',
      st.profile == 'FEATHER' and st.feather_style == 'SHAFT' and abs(st.attach - 0.55) < 1e-6
      and st.edge_thickness == 0.0 and st.sink == 0.0, (st.feather_style, st.attach, st.edge_thickness, st.sink))
st.peak, st.tip_lift = 0.3, 0.2                              # typed with no plate live: for the next plate
nxt, _vs = plate('FEATHER', 30.0, style='SHAFT', attach=0.55, lift=0.2)
st.peak = 0.3
b = lying_cylinder(33.0)
P2 = cg.OrthoProjector(TOP, center=Vector((0, 33.0, 0)))
for o in C.selected_objects:
    o.select_set(False)
b.select_set(True)
C.view_layer.objects.active = b
cpl.perform(C, ll.line_loops(C, P2, [(500 - 80 + 175 * i / 29, 500) for i in range(30)], br), P2)
used = C.active_object
for o in C.selected_objects:
    o.select_set(False)
b2 = lying_cylinder(36.0)
P3 = cg.OrthoProjector(TOP, center=Vector((0, 36.0, 0)))
b2.select_set(True)
C.view_layer.objects.active = b2
cpl.perform(C, ll.line_loops(C, P3, [(500 - 80 + 175 * i / 29, 500) for i in range(30)], br), P3)
after = C.active_object
check('a Height typed for the next plate: that plate gets it; the plate after it is Auto again (not the old value)',
      abs(used.mch_cplate.peak - 0.3) < 1e-6 and abs(after.mch_cplate.peak - 0.3) > 1e-3 and st.peak == 0.0
      and after.mch_cplate.feather_style == 'SHAFT', (used.mch_cplate.peak, after.mch_cplate.peak, st.peak))
summary()
