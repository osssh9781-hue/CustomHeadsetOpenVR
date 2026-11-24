"""0.24.309 (user: "실린더는 양 끝부분에 반대쪽에 달릴 부분도 만들어줘, 경첩인 거니깐, 그리고 실린더에 스프링 옵션도"): each end's
bracket (the other half of the hinge: a Clevis round an Eye, a tongue between a Clevis' plates, on a base plate with
bolts) - an object of its own at the pin, the pin bolt through both; a coil spring between a seat on the body and one
under the rod end, stretching as the rod moves out."""
import numpy as np
from _harness import bpy, bmesh, check, fresh, summary

import mecha_lab
from mecha_lab import actuator_gen as ag

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene


def open_edges(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    n = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return n


def W(ob):
    C.view_layer.update()
    return np.array([(ob.matrix_world @ v.co)[:] for v in ob.data.vertices])


st = S.mch_actuator
st.length, st.width = 2.0, 0.36
st.rear_type, st.rear_size, st.rear_thick, st.rear_hole = 'CLEVIS', 0.34, 0.1, 0.1
st.front_type, st.front_size, st.front_thick, st.front_hole = 'EYE', 0.26, 0.12, 0.08
S.cursor.location = (0, 0, 0)
bpy.ops.mch.actuator_add()
parts = ag.parts_of(S, ag.act_of(C.active_object))
br, bf = parts.get('BRACKET_REAR'), parts.get('BRACKET_FRONT')
check('two brackets (objects of their own, not children: they go on the mech)', br is not None and bf is not None
      and br.parent is None and bf.parent is None)
check('... closed meshes', open_edges(br) == 0 and open_edges(bf) == 0)
Wr, Wf = W(br), W(bf)
check('the rear bracket: below the rear pin (away from the cylinder), the front one above the rod end\'s pin',
      Wr[:, 2].max() < 0.34 / 2 + 1e-4 and Wr[:, 2].min() < -0.2 and Wf[:, 2].min() > 2.0 - 0.26 / 2 - 1e-4 and
      Wf[:, 2].max() > 2.2)
check('their origins at the pins (hinge round them)', br.matrix_world.translation.length < 1e-6 and
      abs(bf.matrix_world.translation.z - 2.0) < 1e-6)
# the clevis end's tongue between its plates: thinner than the gap (the hinge gap each side)
near = Wr[(Wr[:, 2] < -0.05) & (Wr[:, 2] > -0.2)]
check(f'rear (Clevis end): its bracket a tongue {np.ptp(near[:, 0]):.3f} thick - the gap 0.1 less the hinge gap twice',
      abs(np.ptp(near[:, 0]) - (0.1 - 2 * 0.005)) < 1e-4)
nearf = Wf[(Wf[:, 2] > 2.05) & (Wf[:, 2] < 2.15)]
check(f'front (Eye end): its bracket a clevis round it ({np.ptp(nearf[:, 0]):.3f} across: the eye 0.12 + gaps + two '
      f'plates)', abs(np.ptp(nearf[:, 0]) - ((0.12 + 0.01) + 2 * 0.12)) < 1e-4)
rod = parts['ROD']
Wrod = W(rod)
pinz = Wrod[np.abs(Wrod[:, 2] - 2.0) < 0.05]
check('the rod end\'s bolt reaches through the bracket\'s plates too', np.ptp(pinz[:, 0]) > (0.12 + 0.01) + 2 * 0.12)
check('the base plate: Base Plate wide, at least 1.45 x the hinge (its corner bolts clear of the fork)',
      abs(np.ptp(Wf[:, 1]) - max(0.26 * 1.8, 0.37 * 1.45)) < 1e-3, np.ptp(Wf[:, 1]))
st.front_base = 0.7
check('Base Plate live', abs(np.ptp(W(bf)[:, 1]) - 0.7) < 1e-3)
# moved onto the mech: stays when the sliders change
br.location = (0.5, 0.5, -1.0)
st.width = 0.4
C.view_layer.update()
check('a bracket you moved stays where you put it', (br.matrix_world.translation - __import__('mathutils').Vector((0.5, 0.5, -1.0))).length < 1e-6)
st.length = 2.4
C.view_layer.update()
check('... one you did not follows its pin (Length 2.4)', abs(bf.matrix_world.translation.z - 2.4) < 1e-6)
st.rear_bracket = False
check('Rear Bracket off: gone', ag.parts_of(S, ag.act_of(rod)).get('BRACKET_REAR') is None)

# spring
for o in C.selected_objects:
    o.select_set(False)
for o in ag.parts_of(S, ag.act_of(rod)).values():
    o.select_set(True)
st.spring = True
parts = ag.parts_of(S, ag.act_of(rod))
sp = parts.get('SPRING')
check('Spring: a coil round it (a child of the body, stretched to the rod)', sp is not None and sp.parent == parts['BODY']
      and sp.constraints.get('MCH Spring Stretch') is not None and len(sp.data.polygons) > 200)
Ws = W(sp)
za, zb, hs, Rs = ag.spring_seats(ag.numbers(st))
check(f'... from the body\'s seat ({za:.3f}) to the rod\'s ({zb:.3f}), round the body',
      abs(Ws[:, 2].min() - za) < 0.03 and abs(Ws[:, 2].max() - zb) < 0.03 and
      np.hypot(Ws[:, 0], Ws[:, 1]).max() < Rs + 1e-3 and np.hypot(Ws[:, 0], Ws[:, 1]).min() > 0.2 * 0.9)
top0 = Ws[:, 2].max()
rod.location.z += 0.3
Ws = W(sp)
check(f'the rod moved out 0.3: the spring stretches with it (its top {top0:.3f} -> {Ws[:, 2].max():.3f})',
      abs(Ws[:, 2].max() - (top0 + 0.3)) < 0.01 and abs(Ws[:, 2].min() - za) < 0.03)
n0 = len(sp.data.polygons)
st.spring_coils = 14
check('Coils live', len(sp.data.polygons) > n0)
st.spring = False
check('Spring off: the coil and its empty gone', ag.parts_of(S, ag.act_of(rod)).get('SPRING') is None and
      ag.parts_of(S, ag.act_of(rod)).get('SPRING_END') is None)

# 0.24.310 (user's photo: "이런 부분 말이야"): a Ball Joint end, an Arm bracket
for o in C.selected_objects:
    o.select_set(False)
S.cursor.location = (5, 0, 0)
st.rear_bracket = True
st.front_type, st.front_bracket, st.front_bstyle = 'BALL', True, 'ARM'
st.front_size, st.front_thick, st.front_hole = 0.26, 0.1, 0.08
st.front_arm_len, st.front_arm_t, st.front_arm_w, st.front_arm_turn = 0.7, 0.12, 0.3, 0.0
bpy.ops.mch.actuator_add()
p2 = ag.parts_of(S, ag.act_of(C.active_object))
rod2, bf2 = p2['ROD'], p2['BRACKET_FRONT']
check('Ball Joint end + Arm bracket: closed meshes', open_edges(rod2) == 0 and open_edges(bf2) == 0)
Wr2 = W(rod2)
pin = Wr2[np.abs(Wr2[:, 2] - 2.4) < 0.15]
rb = ag.ball_r(ag.numbers(st), 'front')
check(f'... the ball in the eye ({rb:.3f} round, {ag.ball_w(ag.numbers(st), "front"):.2f} wide along the pin)',
      np.any(np.abs(np.hypot(pin[:, 1], pin[:, 2] - 2.4) - rb) < rb * 0.05))
Wb2 = W(bf2)
check(f'the arm: out along Y Arm Length past the joint ({Wb2[:, 1].max() - 0.0:.3f})',
      abs(Wb2[:, 1].max() - 0.7) < 1e-3 and abs(Wb2[:, 1].min() + 0.26 * 0.6) < 0.2)
near2 = Wb2[(Wb2[:, 2] > 2.4 + 0.02) & (Wb2[:, 2] < 2.4 + 0.15)]
check('... its clevis round the ball (the gap: the ball\'s width + the hinge gap twice)',
      abs(np.ptp(near2[:, 0]) - max(0.3, (0.16 + 0.012) + 2 * 0.1 * 1.05)) < 0.02 or
      abs(np.ptp(near2[:, 0]) - ((0.16 + 0.012) + 2 * 0.1)) < 1e-3, np.ptp(near2[:, 0]))
for o in p2.values():
    o.select_set(True)
st.front_arm_turn = 90.0
Wb2 = W(bf2)
check('Arm Turn 90: the arm goes out along X instead', np.ptp(Wb2[:, 0]) > 0.7 and np.ptp(Wb2[:, 1]) < 0.4)
st.front_bstyle = 'PLATE'
check('Base Plate again: closed', open_edges(bf2) == 0)

# 0.24.311 (user's reference photo: a spring round the rod, toothed seats, a cage of posts)
for o in C.selected_objects:
    o.select_set(False)
S.cursor.location = (10, 0, 0)
st.front_type, st.front_bstyle = 'EYE', 'PLATE'
st.spring, st.spring_place, st.spring_size, st.spring_wire, st.spring_coils = True, 'ROD', 0.9, 0.08, 5
st.seat_style, st.seat_teeth, st.cage_posts = 'CASTLE', 10, 0
bpy.ops.mch.actuator_add()
p3 = ag.parts_of(S, ag.act_of(C.active_object))
body3, rod3, sp3 = p3['BODY'], p3['ROD'], p3['SPRING']
g = ag.layout(ag.numbers(st))
Ws3 = W(sp3)
check(f'Round the Rod: the spring starts on the gland ({g["z1"]:.3f}), round the rod only',
      abs(Ws3[:, 2].min() - g['z1'] - ag.spring_seats(ag.numbers(st))[2]) < 0.02 and
      np.hypot(Ws3[:, 0] - 10, Ws3[:, 1]).max() < 0.36 * 0.9 / 2 + 0.03)
check('... closed meshes (toothed seats)', open_edges(body3) == 0 and open_edges(rod3) == 0)
Wb3 = W(body3)
ring = Wb3[np.abs(Wb3[:, 2] - g['z1']) < 0.05]
rr_ = np.hypot(ring[:, 0] - 10, ring[:, 1])
outer = rr_[rr_ > rr_.max() * 0.8]
check(f'Toothed Seat: its rim in and out ({outer.min():.3f} .. {outer.max():.3f}: the gaps 12 % in)',
      abs(outer.min() / outer.max() - 0.88) < 0.02)
for o in p3.values():
    o.select_set(True)
st.seat_style = 'CUP'
check('Cup Seat: closed', open_edges(body3) == 0 and open_edges(rod3) == 0)
n0 = len(body3.data.polygons)
st.cage_posts, st.cage_len = 4, 0.15
check('Cage Posts 4: posts and a ring under the lower seat', len(body3.data.polygons) > n0 + 40 and
      open_edges(body3) == 0)
za_ = ag.spring_seats(ag.numbers(st))[0]
check(f'... round the rod: the seat raised over the cage (the cage from the gland up to it, not into the body)',
      abs(za_ - (g['z1'] + 2 * ag.spring_seats(ag.numbers(st))[2] + 0.15)) < 1e-4 and abs(W(sp3)[:, 2].min() - za_) < 0.03)
st.spring_place = 'BODY'
check('Round the Body again: the seat on the body', abs(W(sp3)[:, 2].min() - ag.spring_seats(ag.numbers(st))[0]) < 0.03)
summary()
