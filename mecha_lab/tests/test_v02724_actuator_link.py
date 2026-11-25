"""0.24.324 (user: "실린더 메뉴 위 아래 판 홀 크기 사이즈 이런 거 각 쌍끼리 동시에 조절되게 해 줘, 그리고 전체 사이즈 조절
슬라이드도, 그리고 바닥 판 없이 깔끔하게 홀까지만 붙는 버전도 옵션"): Link Ends, Overall Size, the Ears Only bracket."""
import bmesh
import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import actuator_gen as ag

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
st = S.mch_actuator


def W(ob):
    C.view_layer.update()
    return np.array([(ob.matrix_world @ v.co)[:] for v in ob.data.vertices])


def open_edges(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    n = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return n


check('defaults: Link Ends off, Overall Size 1 (as before)', not st.link_ends and st.overall == 1.0)
f0 = st.front_size
st.rear_size = 0.4
check('Link Ends off: the other end stays', st.front_size == f0)
st.link_ends = True
check('Link Ends on: the Rod End takes the Rear\'s (size, thickness, pin hole, bracket style ...)',
      all(getattr(st, f'front_{k}') == getattr(st, f'rear_{k}') for k in ag.LINK_KEYS))
check('... not the mount type', st.rear_type == 'CLEVIS' and st.front_type == 'EYE')
st.rear_hole = 0.07
st.front_thick = 0.09
st.rear_bstyle = 'ARM'
check('... a change on either end: both (Pin Hole, Thickness, Bracket Style)', st.front_hole == st.rear_hole
      and abs(st.rear_hole - 0.07) < 1e-6 and abs(st.rear_thick - 0.09) < 1e-6 and st.front_bstyle == 'ARM')
st.rear_bstyle = 'PLATE'
st.link_ends = False
st.rear_size = 0.34
check('Link Ends off again: separate', abs(st.front_size - 0.4) < 1e-6 and abs(st.rear_size - 0.34) < 1e-6)
st.front_size = 0.26

# Overall Size
S.cursor.location = (0, 0, 0)
bpy.ops.mch.actuator_add()
parts = ag.parts_of(S, ag.act_of(C.active_object))
body = parts['BODY']
w0 = np.ptp(W(body)[:, 0])
rod_top0 = W(parts['ROD'])[:, 2].max()
for o in C.selected_objects:
    o.select_set(False)
for o in parts.values():
    o.select_set(True)
st.overall = 2.0
parts = ag.parts_of(S, ag.act_of(body))
check(f'Overall Size 2: the body twice as wide ({w0:.3f} -> {np.ptp(W(body)[:, 0]):.3f}), the rod end twice as far',
      abs(np.ptp(W(body)[:, 0]) - 2 * w0) < 1e-3 and abs(W(parts['ROD'])[:, 2].max() - 2 * rod_top0) < 2e-3)
check('... numbers: every length x2 (mounts too), the shares as they were',
      abs(ag.numbers(st)['front_hole'] - 2 * st.front_hole) < 1e-9 and ag.numbers(st)['body'] == st.body_share)
st.overall = 1.0
check('Overall Size 1: back', abs(np.ptp(W(body)[:, 0]) - w0) < 1e-3)

# Ears Only
for o in C.selected_objects:
    o.select_set(False)
S.cursor.location = (5, 0, 0)
st.rear_bracket = st.front_bracket = True
st.rear_bstyle = st.front_bstyle = 'BARE'
bpy.ops.mch.actuator_add()
parts = ag.parts_of(S, ag.act_of(C.active_object))
br, bf = parts['BRACKET_REAR'], parts['BRACKET_FRONT']
check('Ears Only: both brackets closed meshes', open_edges(br) == 0 and open_edges(bf) == 0)
Wf = W(bf)
L = st.length
reach = st.front_size * 0.8
check(f'... the Rod End\'s (a clevis round the eye): its foot {reach:.3f} past the pin, no plate wider than the ears',
      abs(Wf[:, 2].max() - (L + reach)) < 1e-4 and np.ptp(Wf[:, 1]) < st.front_size + 1e-4, (Wf[:, 2].max(), np.ptp(Wf[:, 1])))
Wr = W(br)
check('... the Rear\'s (a tongue): just the ear, as wide as the mount', abs(Wr[:, 2].min() + st.rear_size * 0.8) < 1e-4
      and np.ptp(Wr[:, 1]) < st.rear_size + 1e-4)
check('... reach (what lies on the surface when clicked onto one): the ears\' foot',
      abs(ag.reach(ag.numbers(st), 'front') - reach) < 1e-9)
n_plate = len(bf.data.polygons)
for o in C.selected_objects:
    o.select_set(False)
for o in parts.values():
    o.select_set(True)
st.front_bstyle = 'PLATE'
check('Base Plate again: more (the plate and its bolts)', len(bf.data.polygons) > n_plate and open_edges(bf) == 0)
summary()
