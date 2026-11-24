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
summary()
