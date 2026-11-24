"""0.24.308 (user, a mech leg photo: "원형 실린더랑 네모난 실린더로 만들어줘, 비율은 내가 조정 가능하게, 각 끝부분에 메카랑
연결되는 부분 쪽 나사가 있는 부분 크기 두께 나사 유무까지" / "방금 만든 나사는 버리지 말구 ... 원기둥으로 깍아주고 나사는 박히는
메뉴로 ... 육각도 ... 쳄퍼랑 베벨 아니면 그냥 깍이기"): Cylinder = an actuator (body + rod, Eye / Clevis mounts with bolts);
Bolt Insert = a pocket cut + a threaded bolt; the Screw Stack kept (in the Bolt Insert window)."""
import math

import numpy as np
from _harness import bpy, bmesh, check, fresh, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import actuator_gen as ag, bolt_insert as bi, cylinder_gen as cy, tool_state as ts
from mecha_lab import ui_tool_settings as uts

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene

check('Cylinder: the actuator now (its window), Bolt Insert a tool of its own (Surface detail, beside Screw Stamp, '
      'enum 94)', uts.DRAWERS.get('CYLGEN') is not None and ts.TOOL_BY_ID['BOLT'][5] == 'mecha.bolt_insert'
      and ts._ENUM_NUMBERS['BOLT'] == 94 and ts._ENUM_NUMBERS['CYLGEN'] == 93
      and dict(ts.TOOL_GROUPS)['Surface detail'].index('BOLT') == dict(ts.TOOL_GROUPS)['Surface detail'].index('SCREW') + 1
      and 'BOLT' in uts.DRAWERS)
check('the enum numbers stay unique', len(set(ts._ENUM_NUMBERS.values())) == len(ts._ENUM_NUMBERS))


def open_edges(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    n = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return n


def W(ob):
    return np.array([(ob.matrix_world @ v.co)[:] for v in ob.data.vertices])


st = S.mch_actuator
st.length, st.width, st.body_share, st.rod_ratio = 2.0, 0.36, 0.6, 0.42
S.cursor.location = (0, 0, 0)
bpy.ops.mch.actuator_add()
parts = ag.parts_of(S, ag.act_of(C.active_object))
body, rod = parts.get('BODY'), parts.get('ROD')
check('Summon Cylinder: a Body and a Rod (the rod a child of the body), both selected',
      body is not None and rod is not None and rod.parent == body and body.select_get() and rod.select_get())
check(f'... closed meshes (body {open_edges(body)}, rod {open_edges(rod)} open edges)',
      open_edges(body) == 0 and open_edges(rod) == 0)
Wb, Wr = W(body), W(rod)
check('pin to pin = Length: the rear pin at the cursor, the rod end\'s pin at 2.0 (the rod\'s origin)',
      abs(rod.matrix_world.translation.z - 2.0) < 1e-6 and Wb[:, 2].min() < 0 and Wr[:, 2].max() > 2.0)
rb = np.hypot(Wb[:, 0], Wb[:, 1])
check('Width 0.36: the barrel 0.36 across (the caps a little more)',
      np.any(np.abs(rb - 0.18) < 1e-4) and abs(np.hypot(Wb[:, 0], Wb[:, 1])[np.abs(Wb[:, 2] - 1.0) < 0.05].max() - 0.18) < 0.03)
f_round = len(body.data.polygons)
st.shape = 'SQUARE'
Wb = W(body)
mid = Wb[(Wb[:, 2] > 0.3) & (Wb[:, 2] < 1.2)]
check('Square: a square housing (its corners out past the round one)', open_edges(body) == 0 and
      np.hypot(mid[:, 0], mid[:, 1]).max() > 0.18 * 1.2)
st.depth = 1.5
Wb = W(body)
mid = Wb[(Wb[:, 2] > 0.3) & (Wb[:, 2] < 1.2)]
check('Depth 1.5: deeper than wide', np.ptp(mid[:, 1]) > np.ptp(mid[:, 0]) * 1.35)
st.shape, st.depth = 'ROUND', 1.0
L0 = W(body)[:, 2].max()
st.body_share = 0.4
check('Body Share 0.4: a shorter body (more rod out)', W(body)[:, 2].max() < L0 - 0.2)
st.rod_ratio = 0.7
Wr = W(rod)
mr_ = Wr[Wr[:, 2] < 1.6]
check('Rod Width 0.7: a thicker rod', abs(np.hypot(mr_[:, 0], mr_[:, 1]).max() - 0.18 * 0.7) < 2e-3)

# the mounts
st.rear_type, st.rear_bolt = 'CLEVIS', True
nb = len(body.data.polygons)
st.rear_bolt = False
check('Rear Bolt off: the bolt and its nut gone', len(body.data.polygons) < nb and open_edges(body) == 0)
st.rear_bolt = True
w0 = np.ptp(W(body)[W(body)[:, 2] < 0.05][:, 0])
st.rear_thick = 0.2
w1 = np.ptp(W(body)[W(body)[:, 2] < 0.05][:, 0])
check(f'Rear Thickness: the clevis wider ({w0:.3f} -> {w1:.3f})', w1 > w0 + 0.15)
st.rear_size = 0.5
check('Rear Size: the plates bigger', np.ptp(W(body)[W(body)[:, 2] < 0.0][:, 1]) > 0.45)
for typ in ('EYE', 'CLEVIS', 'NONE'):
    st.rear_type = typ
    st.front_type = typ
    check(f'{typ} mounts: closed', open_edges(body) == 0 and open_edges(rod) == 0)
st.rear_type, st.front_type = 'NONE', 'NONE'
check('None: the body starts at the pin (a flat end; only its cap bolts\' heads below)', -0.03 < W(body)[:, 2].min() < 1e-4, W(body)[:, 2].min())
st.rear_type, st.front_type = 'CLEVIS', 'EYE'
st.front_hole = 0.06
hole_pts = W(rod)
check('Rod End Pin Hole: the bolt through it follows (its shank 0.06 across)', open_edges(rod) == 0)

# the rod slid out stays slid out
rod.location.z += 0.3
st.width = 0.4
C.view_layer.update()
check('the rod moved out 0.3 stays out after a slider change', abs(rod.matrix_world.translation.z - 2.3) < 1e-5,
      rod.matrix_world.translation.z)
st.length = 3.0
C.view_layer.update()
check('Length 3: the rod\'s pin at 3 (+ the 0.3 slid out)', abs(rod.matrix_world.translation.z - 3.3) < 1e-5)
body.select_set(False)
rod.select_set(False)
st.width = 0.2
wb_ = W(body)
check('an unselected cylinder stays (still 0.4 wide)', abs(np.hypot(wb_[:, 0], wb_[:, 1])[(wb_[:, 2] > 0.4) & (wb_[:, 2] < 1.2)].min() - 0.2) < 0.03)

# --- Bolt Insert ---------------------------------------------------------------------------------------------------
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(10, 0, 0))
part = C.active_object
v0 = abs(sum(p.area for p in part.data.polygons))
bs = S.mch_bolt
bs.head, bs.size, bs.head_height, bs.shank_d, bs.shank_len = 'HEX', 0.3, 0.12, 0.16, 0.5
bs.cut, bs.depth, bs.clearance, bs.edge, bs.edge_size = True, 0.15, 0.03, 'PLAIN', 0.03
b = bi.place(C, part, Vector((10, 0, 1)), Vector((0, 0, 1)), bi.numbers(bs))
check('a bolt on the top face: a child of the part, its pocket a Boolean on it', b.parent == part and
      part.modifiers.get(bi._mod_name(b)) is not None and bi.cutter_of(b) is not None)


def ev_verts(ob):
    dg = C.evaluated_depsgraph_get()
    e = ob.evaluated_get(dg)
    me = e.to_mesh()
    V = np.array([(ob.matrix_world @ v.co)[:] for v in me.vertices])
    e.to_mesh_clear()
    return V


V = ev_verts(part)
floor = V[(np.hypot(V[:, 0] - 10, V[:, 1]) < 0.1)][:, 2]
check(f'the pocket: its floor 0.15 down, 0.18 across (the head 0.15 + the gap 0.03)',
      len(floor) and abs(floor.min() - 0.85) < 1e-3 and
      abs((lambda r_: r_[r_ < 0.5].max())(np.hypot(V[:, 0] - 10, V[:, 1])[np.abs(V[:, 2] - 1.0) < 1e-3]) - 0.18) < 2e-3)
Vb = W(b)
check('the bolt: its head on the pocket\'s floor, the shank on into the part, the head a hexagon',
      abs(Vb[:, 2].max() - (0.85 + 0.12)) < 1e-3 and abs(Vb[:, 2].min() - (0.85 - 0.5)) < 1e-3 and
      open_edges(b) == 0)
top = Vb[np.abs(Vb[:, 2] - 0.85) < 1e-4]
rr = np.hypot(top[:, 0] - 10, top[:, 1])
rr = rr[rr > 0.1]                                  # (the head's underside ring, the shank aside)
check('... hex: its corners at 0.15, its flats at 0.13', abs(rr.max() - 0.15) < 1e-3 and abs(rr.min() - 0.15 * math.cos(math.pi / 6)) < 2e-3)
for e in ('CHAMFER', 'BEVEL'):
    sel = [o for o in C.selected_objects]
    for o in sel:
        o.select_set(False)
    b.select_set(True)
    bs.edge = e
    V = ev_verts(part)
    rim = np.hypot(V[:, 0] - 10, V[:, 1])[np.abs(V[:, 2] - 1.0) < 1e-4]
    check(f'Rim {e}: the pocket\'s rim opened out by the rim size (0.18 -> 0.21 at the top)',
          abs(rim[rim < 0.5].max() - 0.21) < 3e-3, rim[rim < 0.5].max())
bs.edge = 'PLAIN'
bs.pocket_shape, bs.pocket_corner = 'SQUARE', 0.0
V = ev_verts(part)
top_ = V[np.abs(V[:, 2] - 1.0) < 1e-4]
top_ = top_[np.hypot(top_[:, 0] - 10, top_[:, 1]) < 0.5]
check(f'Square Pocket: a square (its corner out at 0.18 x 0.18 from the middle - a round one: 0.18 at most)',
      abs(np.abs(top_[:, 0] - 10).max() - 0.18) < 3e-3 and np.hypot(top_[:, 0] - 10, top_[:, 1]).max() > 0.18 * 1.35,
      np.hypot(top_[:, 0] - 10, top_[:, 1]).max())
fl = V[np.abs(V[:, 2] - 0.85) < 1e-4]
check('... as deep (its floor 0.15 down)', len(fl) > 3)
bs.pocket_corner = 1.0
V = ev_verts(part)
top_ = V[np.abs(V[:, 2] - 1.0) < 1e-4]
check('Pocket Corner 1: nearly round again', np.hypot(top_[:, 0] - 10, top_[:, 1])[np.hypot(top_[:, 0] - 10, top_[:, 1]) < 0.5].max() < 0.18 * 1.1)
bs.pocket_shape = 'ROUND'
bs.head = 'SOCKET'
check('Socket head: closed', open_edges(b) == 0)
bs.head = 'ROUND'
check('Round head: closed', open_edges(b) == 0)
bs.thread = False
check('Thread off: closed', open_edges(b) == 0)
bs.cut = False
check('Cut Pocket off: the Boolean and its cutter gone (the head on the surface)',
      part.modifiers.get(bi._mod_name(b)) is None and bi.cutter_of(b) is None and abs(W(b)[:, 2].max() - 1.12) < 1e-3)
bs.cut = True
check('... on again', part.modifiers.get(bi._mod_name(b)) is not None)
# moving the bolt moves its pocket
b.location.x += 0.3
V = ev_verts(part)
check('the bolt moved: its pocket goes with it', np.any((np.hypot(V[:, 0] - 10.3, V[:, 1]) < 0.05) & (V[:, 2] < 0.9)))
nf = len(part.data.polygons)
C.view_layer.objects.active = b
bpy.ops.mch.bolt_apply()
check('Apply Cut: the pocket real in the part, the Boolean / cutter gone, the bolt stays',
      len(part.data.polygons) > nf and part.modifiers.get(bi._mod_name(b)) is None and bi.cutter_of(b) is None
      and bpy.data.objects.get(b.name) is not None)
b2 = bi.place(C, part, Vector((9.5, 0, 1)), Vector((0, 0, 1)), bi.numbers(bs))
nm = b2.name
bi.remove(C, b2)
check('remove: the bolt and its pocket gone', bpy.data.objects.get(nm) is None and
      not any(m.name.startswith('MCH Bolt | ' + nm) for m in part.modifiers))

# the screw stack kept
S.cursor.location = (-10, 0, 0)
bpy.ops.mch.cylinder_add()
check('the Screw Stack (0.24.307) still there (in the Bolt Insert window)', len(cy.layers_of(S, cy.stack_of(C.active_object))) >= 1)
summary()
