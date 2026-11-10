"""0.24.124 (user: "밀기도 넣어줘 / 스마트 무브는 모든 툴에 넣어줘 / 자른 메쉬를 컨셉무브로 움직이면 메쉬가 깨지는데 / 스탬프 쓸 때는
R 누르고 하면 돌아가게 / 프레스 컷에 플레이트 버튼 ... 라인은 스탬프로 표면에 / 기능 설명은 접을 수 있게")
  1. Smart Move in any tool: E (the part under the mouse, else the selected one), the 3D mouse on the selected part
     (corner card 3D MOUSE: Parts), push on by default
  2. Concept Move on a cut part: the big faces round the hole are sliced before the pull (a grid bump, no sliver fan)
  3. R + the 3D mouse turns the stamp
  4. Press Cut Plate result: Armor / Creature - Lasso = that plate tool's stroke, Line = the stamp's section laid on the
     surface, press = the stamp as a plate
  5. the key legend card folds; the Smart Move how-to folds"""
import inspect
import json
import math
import types

from _harness import bpy, check, fresh, summary
import bmesh  # noqa: E402
from mathutils import Euler, Quaternion, Vector  # noqa: E402

import mecha_lab
from mecha_lab import (base_mesh, concept_move as cm, core_geometry as cg, cut_engine as ce, key_legend as kl,
                       press_cut as pc, quick_hud as qh, smart_move as sm, tool_state as ts, top_bar as tb, zb_ui as zu)
from mecha_lab.ui_gpu import ui_factor

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
WM = C.window_manager
W, H = 2560, 1440


class Ctx:
    region = types.SimpleNamespace(width=W, height=H, x=0, y=0, type='WINDOW')
    area = None
    region_data = object()

    def __getattr__(self, n):
        return getattr(bpy.context, n)


CTX = Ctx()
TOP = cg.OrthoProjector(Quaternion())


def near(a, b, tol=1e-5):
    return (Vector(a) - Vector(b)).length < tol


# --- 1. Smart Move everywhere ------------------------------------------------------------------------------------------
kc = WM.keyconfigs.addon
km = kc.keymaps.get('Object Mode') if kc is not None else None
items = [(i.idname, i.type, bool(getattr(i.properties, 'from_key', False))) for i in km.keymap_items] if km else []
check('E in any Mecha tool = Smart Move (from_key) and the 3D mouse goes through mch.smart_ndof - the Object Mode add-on keymap',
      ('mch.smart_move', 'E', True) in items and any(i[0] == 'mch.smart_ndof' and i[1] == 'NDOF_MOTION' for i in items),
      [i for i in items if i[0].startswith('mch.smart')])
st = S.mch_smart
check('push on by default (Free), the how-to folded, E ends a hold too, the operators registered',
      st.bl_rna.properties['push'].default == 'FREE' and not st.show_help and 'E' in sm.CONFIRM_TYPES
      and hasattr(bpy.types, 'MCH_OT_smart_ndof') and hasattr(bpy.types, 'MCH_OT_ndof_parts') and hasattr(WM, 'mch_ndof_parts'))

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=1)
slab = C.active_object
slab.name = 'Slab'
slab.scale = (12, 12, 0.6)
slab.location = (0, 0, -0.3)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 1.5))
part = C.active_object
part.name = 'Part'
part.scale = (1, 1.5, 0.6)
for o in (slab, part):
    o.select_set(False)
part.select_set(True)
C.view_layer.objects.active = part
C.view_layer.update()


class Shim:
    def __init__(self, from_key=False):
        self.reports = []
        self.from_key = from_key

    def report(self, kind, msg):
        self.reports.append((kind, msg))


for name in ('_setup', '_hook', '_unhook', '_header', '_object', '_finish', '_place', '_ndof', '_target_for', 'invoke', 'modal'):
    setattr(Shim, name, getattr(sm.MCH_OT_smart_move, name))
check('E with nothing under the mouse (headless: no region) holds the SELECTED active part; a press (the tool) needs the mouse on one',
      Shim(True)._target_for(C, (10, 10)) is part and Shim(False)._target_for(C, (10, 10)) is None)
part.select_set(False)
check('... nothing selected: nothing to hold', Shim(True)._target_for(C, (10, 10)) is None)
part.select_set(True)
real_ws = sm.mecha_workspace
sm.mecha_workspace = lambda c: False
check('E outside MECHA LAB passes through (Blender\'s E)', Shim(True).invoke(C, types.SimpleNamespace(mouse_region_x=5, mouse_region_y=5)) == {'PASS_THROUGH'})
sm.mecha_workspace = lambda c: True
m0 = part.matrix_world.copy()
data = types.SimpleNamespace(rotation=Vector((0.0, 0.25, 0.0)), translation=Vector((1.0, 0.0, 0.0)), time_delta=0.1, progress='IN_PROGRESS')
ang, step = sm.ndof_apply(part, data, st, None)
turn = (part.matrix_world.to_3x3() @ m0.to_3x3().inverted()).to_quaternion()
check('ndof_apply (push Free): 9 deg about the origin (device twist = world Z without a view) AND a slide along the device '
      'x (world X): push speed 0.5 x view distance 1 x 0.1 s = 0.05',
      abs(math.degrees(ang) - 9.0) < 1e-6 and abs(math.degrees(turn.angle) - 9.0) < 0.01 and abs(abs(turn.axis.z) - 1.0) < 1e-4
      and (part.matrix_world.translation - m0.translation - Vector((0.05, 0, 0))).length < 1e-6 and (step - Vector((0.05, 0, 0))).length < 1e-6)
part.matrix_world = m0
# 0.24.126 (user: "안쪽이랑 바깥쪽으로 … 안 되네" / "xyz 축에 토글") the push axes under a view looking down 60 deg, turned 35 deg
Vm = (Euler((math.radians(60), 0.0, math.radians(35))).to_matrix().to_4x4()).inverted()
right, forward, up = sm.push_axes('TURNTABLE', Vm)
vz = (Vm.to_3x3().inverted() @ Vector((0, 0, 1))).normalized()
check('push_axes TURNTABLE: push down / pull up = the WORLD\'s up (it went along the line of sight before), forward / back along '
      'the ground where the view looks, left / right level - all unit, the first two horizontal',
      near(up, (0, 0, 1)) and abs(right.z) < 1e-6 and abs(forward.z) < 1e-6 and abs(right.length - 1) < 1e-6
      and abs(forward.length - 1) < 1e-6 and forward.dot(Vector((-vz.x, -vz.y, 0)).normalized()) > 0.99
      and abs(right.dot(forward)) < 1e-6, (tuple(right), tuple(forward), tuple(up)))
r2, f2, u2 = sm.push_axes('VIEW', Vm)
check('... VIEW: the view\'s own axes (push = towards you, the old way); no view / WORLD: X, Y, Z',
      near(u2, vz) and 0.3 < u2.z < 0.95 and sm.push_axes('WORLD', Vm) == sm.push_axes('TURNTABLE', None)
      and near(sm.push_axes('TURNTABLE', None)[1], (0, 1, 0)))
rv_fake = types.SimpleNamespace(view_matrix=Vm, view_distance=2.0)
st.axes, st.push, st.push_speed = 'TURNTABLE', 'FREE', 0.5
d_push = types.SimpleNamespace(rotation=Vector((0, 0, 0)), translation=Vector((0.0, 0.0, 1.0)), time_delta=0.1, progress='IN_PROGRESS')
t0 = part.matrix_world.translation.copy()
sm.ndof_apply(part, d_push, st, rv_fake)
step_up = part.matrix_world.translation - t0
part.matrix_world = m0
st.push_z = False
sm.ndof_apply(part, d_push, st, rv_fake)
step_none = part.matrix_world.translation - m0.translation
st.push_z = True
st.ax_ud_rev = True
part.matrix_world = m0
sm.ndof_apply(part, d_push, st, rv_fake)
step_inv = part.matrix_world.translation - m0.translation
st.ax_ud_rev = False
st.ax_ud_speed = 2.0
part.matrix_world = m0
sm.ndof_apply(part, d_push, st, rv_fake)
step_fast = part.matrix_world.translation - m0.translation
st.ax_ud_speed = 1.0
st.ax_ud_on = False
part.matrix_world = m0
sm.ndof_apply(part, d_push, st, rv_fake)
step_off = part.matrix_world.translation - m0.translation
st.ax_ud_on = True
part.matrix_world = m0
check('a pull on the cap (z) under that view lifts the part straight up (2 x 0.5 x 0.1 = 0.1); Push Axes Z off: it stays; the axis '
      'table: Up / Down Reverse = down, Speed 2 = twice, Active off = nothing',
      near(step_up, (0, 0, 0.1), 1e-6) and step_none.length < 1e-9 and near(step_inv, (0, 0, -0.1), 1e-6)
      and near(step_fast, (0, 0, 0.2), 1e-6) and step_off.length < 1e-9,
      (tuple(step_up), tuple(step_none), tuple(step_inv), tuple(step_fast), tuple(step_off)))
d_turn = types.SimpleNamespace(rotation=Vector((0.25, 0.0, 0.0)), translation=Vector((0, 0, 0)), time_delta=0.1, progress='IN_PROGRESS')
st.ax_tilt_on = False
ang0, _s = sm.ndof_apply(part, d_turn, st, rv_fake)
st.ax_tilt_on = True
ang1, _s = sm.ndof_apply(part, d_turn, st, rv_fake)
part.matrix_world = m0
check('the axis table: Tilt Active off - a tilt of the cap turns nothing; on - 9 deg', abs(ang0) < 1e-9 and abs(math.degrees(ang1) - 9.0) < 1e-6)
check('the table has the six cap motions x Active / Speed / Reverse, folded by default',
      [k for k, _l, _d in sm.AXES] == ['lr', 'fb', 'ud', 'tilt', 'spin', 'roll'] and not st.show_axes
      and all(hasattr(st, f'ax_{k}_{suf}') for k, _l, _d in sm.AXES for suf in ('on', 'speed', 'rev'))
      and sm.axis_gain(st, 'spin') == 1.0)
st.axes = 'TURNTABLE'
# 0.24.126 Smart Size (user: "사이즈 조절도 3D 마우스로 … 로컬이랑 월드 축 선택")
part.rotation_euler = (0.0, 0.0, math.radians(30))
part.scale = (1.0, 1.5, 0.6)
C.view_layer.update()
mr = part.matrix_world.copy()
d_x = types.SimpleNamespace(rotation=Vector((0, 0, 0)), translation=Vector((1.0, 0.0, 0.0)), time_delta=0.1, progress='IN_PROGRESS')
check('size_factors: a full push along x for 0.1 s at Size Speed 1 = x 2^0.1 on X only; a twist = all three; X off = nothing on X',
      all(abs(a - b) < 1e-9 for a, b in zip(sm.size_factors(d_x, st, 0.1), (2 ** 0.1, 1.0, 1.0)))
      and all(abs(a - 2 ** 0.05) < 1e-9 for a in sm.size_factors(types.SimpleNamespace(rotation=Vector((0, 0.5, 0)), translation=Vector((0, 0, 0))), st, 0.1)))
st.push_x = False
check('... X off', sm.size_factors(d_x, st, 0.1) == (1.0, 1.0, 1.0))
st.push_x = True
st.ndof_do, st.size_space = 'SIZE', 'LOCAL'
sm.size_apply(part, d_x, st)
ml = part.matrix_world
check('Smart Size LOCAL on a part turned 30 deg: its own X grows 2^0.1, Y / Z and the rotation stay, the origin stays',
      abs(ml.to_scale().x - 1.0 * 2 ** 0.1) < 1e-6 and abs(ml.to_scale().y - 1.5) < 1e-6 and abs(ml.to_scale().z - 0.6) < 1e-6
      and near(ml.translation, mr.translation) and abs(math.degrees(ml.to_euler().z) - 30.0) < 1e-4, (tuple(ml.to_scale()), tuple(ml.to_euler())))
part.matrix_world = mr
st.size_space = 'WORLD'
d_z = types.SimpleNamespace(rotation=Vector((0, 0, 0)), translation=Vector((0.0, 0.0, 1.0)), time_delta=0.1, progress='IN_PROGRESS')
sm.size_apply(part, d_z, st)
mw = part.matrix_world
check('Smart Size WORLD: a pull (z) scales along the world Z about the origin - the part gets 2^0.1 taller, X / Y as they were, origin fixed',
      abs(mw.to_scale().z - 0.6 * 2 ** 0.1) < 1e-6 and abs(mw.to_scale().x - 1.0) < 1e-6 and abs(mw.to_scale().y - 1.5) < 1e-6
      and near(mw.translation, mr.translation), tuple(mw.to_scale()))
part.matrix_world = mr
ev_x = types.SimpleNamespace(type='NDOF_MOTION', value='NOTHING', ndof_motion=d_x)
op = Shim()
op._setup()
op.ob_name, op.orig = part.name, part.matrix_world.copy()
op.t_start = 0.0
op.tool0 = ts.effective_tool(C)
st.ndof_do, st.size_space = 'MOVE', 'LOCAL'
r_s = op.modal(C, types.SimpleNamespace(type='S', value='PRESS', mouse_region_x=5, mouse_region_y=5, is_repeat=False, shift=False, alt=False, ctrl=False, ndof_motion=None))
after_s = st.ndof_do
op.modal(C, ev_x)
sized = abs(part.matrix_world.to_scale().x - 2 ** 0.1) < 1e-6 and near(part.matrix_world.translation, mr.translation)
op.modal(C, types.SimpleNamespace(type='S', value='PRESS', mouse_region_x=5, mouse_region_y=5, is_repeat=False, shift=False, alt=False, ctrl=False, ndof_motion=None))
check('holding: S switches the 3D mouse to Size (the next event scales, the origin stays), S again back to Move',
      r_s == {'RUNNING_MODAL'} and after_s == 'SIZE' and sized and st.ndof_do == 'MOVE', (r_s, after_s, tuple(part.matrix_world.to_scale())))
op.modal(C, types.SimpleNamespace(type='ESC', value='PRESS', mouse_region_x=5, mouse_region_y=5, is_repeat=False, shift=False, alt=False, ctrl=False, ndof_motion=None))
part.select_set(True)                       # (the shim's Esc restored an empty "selection before the hold")
C.view_layer.objects.active = part
part.matrix_world = mr
st.ndof_do = 'SIZE'
st.size_space = 'LOCAL'
WM.mch_ndof_parts = True
sm.mecha_workspace = lambda c: True
r_p = sm.MCH_OT_smart_ndof.invoke(Shim(), C, ev_x)
check('3D MOUSE Parts + Size: the selected part is scaled in any tool', r_p == {'FINISHED'} and abs(part.matrix_world.to_scale().x - 2 ** 0.1) < 1e-6)
WM.mch_ndof_parts = False
st.ndof_do = 'MOVE'
# 0.24.126 Local turn axes + One Axis (user: "로컬 축이나 월드 축에 종속되서 돌려지는 버전")
part.matrix_world = mr
R = mr.to_3x3().normalized()
ax_l = sm.turn_axis((0, 1, 0), 'LOCAL', Vm, mr)
ax_t = sm.turn_axis((1, 0, 0), 'LOCAL', Vm, mr)
check('turn_axis LOCAL: a twist turns round the part\'s own Z, a tilt round its own X (the part turned 30 deg)',
      near(ax_l, R @ Vector((0, 0, 1))) and near(ax_t, R @ Vector((1, 0, 0))) and abs(ax_t.x - math.cos(math.radians(30))) < 1e-6)
st.axes = 'LOCAL'
st.turn_single = True
d_mix = types.SimpleNamespace(rotation=Vector((0.1, 0.25, 0.05)), translation=Vector((0, 0, 0)), time_delta=0.1, progress='IN_PROGRESS')
ang_m, _s = sm.ndof_apply(part, d_mix, st, rv_fake)
turn_m = (part.matrix_world.to_3x3() @ mr.to_3x3().inverted()).to_quaternion()
check('One Axis: of a mixed cap motion only the strongest (the twist) turns - 9 deg about the part\'s own Z, nothing else',
      abs(math.degrees(ang_m) - 9.0) < 1e-6 and abs(math.degrees(turn_m.angle) - 9.0) < 0.01 and abs(abs(turn_m.axis.dot(R @ Vector((0, 0, 1)))) - 1.0) < 1e-4,
      (math.degrees(ang_m), math.degrees(turn_m.angle), tuple(turn_m.axis)))
check('dominant keeps one component', near(sm.dominant((0.1, -0.3, 0.2)), (0.0, -0.3, 0.0)))
st.turn_single = False
st.axes = 'TURNTABLE'
part.matrix_world = m0
part.rotation_euler = (0, 0, 0)
part.scale = (1, 1.5, 0.6)
C.view_layer.update()
m0 = part.matrix_world.copy()
ev = types.SimpleNamespace(type='NDOF_MOTION', value='NOTHING', ndof_motion=data)
WM.mch_ndof_parts = False
r0 = sm.MCH_OT_smart_ndof.invoke(Shim(), C, ev)
WM.mch_ndof_parts = True
r1 = sm.MCH_OT_smart_ndof.invoke(Shim(), C, ev)
moved = (part.matrix_world.translation - m0.translation).length
part.matrix_world = m0
sm.ACTIVE[0] = object()
r2 = sm.MCH_OT_smart_ndof.invoke(Shim(), C, ev)
sm.ACTIVE[0] = None
part.select_set(False)
r3 = sm.MCH_OT_smart_ndof.invoke(Shim(), C, ev)
part.select_set(True)
check('mch.smart_ndof: 3D MOUSE View -> passes through (the view turns as always); Parts -> the selected part moves and the event '
      'is consumed; a Smart Move hold running or nothing selected -> passes through',
      r0 == {'PASS_THROUGH'} and r1 == {'FINISHED'} and abs(moved - 0.05) < 1e-6 and r2 == {'PASS_THROUGH'} and r3 == {'PASS_THROUGH'},
      (r0, r1, moved, r2, r3))
WM.mch_ndof_parts = False
sm.mecha_workspace = real_ws
bpy.ops.mch.ndof_parts(on=True)
check('the corner card op sets it', WM.mch_ndof_parts)
bpy.ops.mch.ndof_parts(on=False)
K = ui_factor(CTX, CTX.region)
its = zu.corner_items(CTX, W, H, K)
labels = [i.label for i in its if i.kind == 'glabel']
seg = {(i.label, i.action[1] if i.action else ''): i for i in its if i.kind == 'seg'}
cx, cy, cw, ch = zu.corner_box(CTX, W, H, K)
check('corner card (MECHA LAB): a 3D MOUSE row View | Parts under VIEW, View on; the card holds all rows',
      labels[-2:] == ['VIEW', '3D MOUSE'] and seg[('View', 'mch.ndof_parts')].on and not seg[('Parts', 'mch.ndof_parts')].on
      and seg[('Parts', 'mch.ndof_parts')].action[2] == {'on': True}
      and all(cy - 0.5 <= i.y and i.y + i.h <= cy + ch + 0.5 for i in its if i.kind != 'card'), labels)

# --- 2. Concept Move on a cut part ------------------------------------------------------------------------------------


def stats(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    sl = 0
    for f in bm.faces:
        if len(f.verts) == 3:
            a, b, c = [v.co for v in f.verts]
            try:
                angs = [(b - a).angle(c - a), (a - b).angle(c - b), (a - c).angle(b - c)]
            except ValueError:
                angs = [0.0]
            if min(angs) < math.radians(5):
                sl += 1
    crease = ob.data.attributes.get('crease_edge')
    nc = sum(1 for d in crease.data if d.value > 0.5) if crease is not None else 0
    out = (len(bm.verts), len(bm.faces), nm, sl, nc, bm.calc_volume(signed=True))
    bm.free()
    return out


def cut_box():
    bpy.ops.mesh.primitive_cube_add(size=2)
    b = C.active_object
    b.scale = (2.0, 1.2, 0.5)
    bpy.ops.object.transform_apply(scale=True)
    loops = [[(500 + 60 * math.cos(a), 500 + 40 * math.sin(a)) for a in (2 * math.pi * i / 24 for i in range(24))]]
    ce.perform_closed(C, 'CUT', [b], loops, TOP)
    return b


for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
box = cut_box()
s0 = stats(box)
mv = {'centre': (0.0, 0.0, 0.5), 'delta': (0.0, 0.0, 0.5), 'radius': 1.2, 'falloff': 'CLAY', 'mirror': False, 'shape': 'SPHERE', 'hardness': 0.5}
# the old way (no slicing): the fan
cm.generate(box.data, cm.move_field(mv))
s_old = stats(box)
bpy.data.objects.remove(box)
box = cut_box()
n = cm.prepare_region(box.data, [(0.0, 0.0, 0.5)], 1.2)
s_prep = stats(box)
cm.generate(box.data, cm.move_field(mv))
s_new = stats(box)
check('a part cut by the Cut tool pulled with Concept Move the old way: a fan of long slivers from the hole\'s rim',
      s_old[3] >= 30 and s_old[2] == 0, s_old)
check('prepare_region slices the faces the brush reaches (planes along the axes, a third of the reach apart): the mesh stays '
      'manifold, the volume the same, the edge marks kept',
      n >= 6 and s_prep[2] == 0 and abs(s_prep[5] - s0[5]) < 1e-6 and s_prep[4] >= s0[4] and s_prep[1] > s0[1] * 3, (n, s0, s_prep))
check('... the same pull after it: a grid bump - a fraction of the slivers, manifold, the part raised',
      s_new[3] <= s_old[3] * 0.4 and s_new[2] == 0 and s_new[5] > s0[5] + 0.5, (s_old[3], s_new[3]))
src = inspect.getsource(cm.apply_moves) + inspect.getsource(cm.MCH_OT_concept_path._run)
check('wired: Concept Move (apply_moves) and Path Move (_run) prepare the region before generating', src.count('prepare_region(') == 2)
bpy.data.objects.remove(box)
bpy.ops.mesh.primitive_cube_add(size=2)
dense = C.active_object
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.subdivide(number_cuts=20)
bpy.ops.object.mode_set(mode='OBJECT')
nf = len(dense.data.polygons)
check('a dense part is left alone (its faces are already smaller than the slice step)',
      cm.prepare_region(dense.data, [(0.0, 0.0, 1.0)], 0.6) == 0 and len(dense.data.polygons) == nf)
check('... and Mirror X slices round the mirrored grab point too', cm.move_centres(dict(mv, mirror=True, centre=(1.0, 0.2, 0.5))) == [(1.0, 0.2, 0.5), (-1.0, 0.2, 0.5)])

# --- 3. R + the 3D mouse turns the stamp ------------------------------------------------------------------------------
pr = S.mch_press
pr.rotation = 0.0


class TurnShim:
    def __init__(self):
        self.owner, self.prop, self.start, self.x0, self.ndof_off = pr, 'rotation', 0.0, 100, 0.0
        self.region = types.SimpleNamespace(tag_redraw=lambda: None)
        self.reports = []

    def report(self, kind, msg):
        self.reports.append((kind, msg))

    def _end(self):
        pass


TurnShim.modal = pc.MCH_OT_stamp_turn.modal
op = TurnShim()
nd = types.SimpleNamespace(type='NDOF_MOTION', value='NOTHING', mouse_x=100, ctrl=False, shift=False, is_repeat=False,
                           ndof_motion=types.SimpleNamespace(rotation=Vector((0.0, 0.25, 0.0)), translation=Vector((0, 0, 0)), time_delta=0.1))
r = op.modal(C, nd)
a1 = math.degrees(pr.rotation)
mm = types.SimpleNamespace(type='MOUSEMOVE', value='NOTHING', mouse_x=100, ctrl=False, shift=False, is_repeat=False)
op.modal(C, mm)
a2 = math.degrees(pr.rotation)
mm.mouse_x = 110
op.modal(C, mm)
a3 = math.degrees(pr.rotation)
check('R held + a 3D-mouse twist turns the stamp 9 deg (the Smart Move pace); the mouse then turns on from there (+4 deg for 10 px)',
      r == {'RUNNING_MODAL'} and abs(a1 - 9.0) < 0.01 and abs(a2 - 9.0) < 0.01 and abs(a3 - 13.0) < 0.01, (r, a1, a2, a3))
S.mch_smart.invert = True
nd.mouse_x = 110                                   # (a real NDOF event carries the mouse where it is now)
op.modal(C, nd)
check('... Smart Move\'s Invert turns it the other way', abs(math.degrees(pr.rotation) - 4.0) < 0.01, math.degrees(pr.rotation))
S.mch_smart.invert = False
pr.rotation = 0.0

# --- 4. Press Cut Plate result ----------------------------------------------------------------------------------------
ids = [e.identifier for e in pr.bl_rna.properties['result'].enum_items]
check('Press result: Cut / Split / Armor Plate / Creature Plate', ids == ['CUT', 'SPLIT', 'PLATE', 'CPLATE'])
check('lasso_stroke_mode: Cut / Split -> the Base Mesh lasso, a plate -> that plate tool\'s',
      [pc.lasso_stroke_mode(types.SimpleNamespace(result=r_)) for r_ in ids] == ['BASE', 'BASE', 'PLATE', 'CPLATE']
      and pc.plate_result(types.SimpleNamespace(result='CPLATE')) and not pc.plate_result(types.SimpleNamespace(result='CUT')))
kmp = [(k[0], (k[2] or {}).get('properties')) for k in pc.TOOL_KEYMAP]
names = [k[0] for k in kmp]
stroke_modes = [dict(p)['mode'] for n_, p in kmp if n_ == 'mch.cut_stroke' and p and ('press_lasso', True) in p]
check('the Press keymap binds the plate tools\' strokes (mode PLATE / CPLATE, press_lasso, plain + Alt) with the Base one, all '
      'before the Press tool\'s own press', stroke_modes == ['BASE', 'BASE', 'PLATE', 'PLATE', 'CPLATE', 'CPLATE']
      and max(i for i, n_ in enumerate(names) if n_ == 'mch.cut_stroke' and i < names.index('mch.press_unified')) < names.index('mch.press_unified'))
src_ce = inspect.getsource(ce.StrokeLogic.invoke)
check('the gate: a press_lasso stroke runs only when its mode is the one the result asks for',
      'press_cut.lasso_stroke_mode(st_) != self.mode' in src_ce)
pr.draw_mode = 'LASSO'
pr.result = 'PLATE'
S.mch_settings.mch_active_tool = 'PRESS'
ok_plate = base_mesh.sketch_tool_ok(C)
pr.result = 'CUT'
ok_base = base_mesh.sketch_tool_ok(C)
pr.draw_mode = 'LINE'
check('the Base Mesh sketch keys (Enter ...) serve Press Lasso only with the Base lasso (Cut / Split), not a plate lasso',
      ok_base and not ok_plate)
orig_eff = tb.ts.effective_tool
tb.ts.effective_tool = lambda _c: 'PRESS'
try:
    groups = dict((g[0], g[1]) for g in tb.groups(C, 'PRESS'))
finally:
    tb.ts.effective_tool = orig_eff
check('the Press top bar: a Plate group Armor | Creature (the result), the Press group keeps Cut | Split',
      [c['label'] for c in groups.get('Plate', [])] == ['Armor', 'Creature'] and groups['Plate'][0]['prop'] == 'result'
      and [c['label'] for c in groups['Press'][:2]] == ['Cut', 'Split'], [c['label'] for c in groups.get('Plate', [])])
check('the key legend tells it', any('Plate' in ln and 'surface' in ln for ln in kl.lines('PRESS')))
# the Line: the stamp's section laid on a sphere
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_uv_sphere_add(radius=2.0, segments=48, ring_count=24)
sph = C.active_object
sph.name = 'Sphere'
pr.shape = 'MCH_BUILTIN_M_OCTAGON'
pr.result = 'PLATE'
o1, _d = TOP.ray((500, 500))
o2, _d = TOP.ray((600, 500))
ppu = 100.0 / (Vector(o2) - Vector(o1)).length
span = 60.0 / ppu
pts = [(500 + 120 * math.cos(a), 500 + 120 * math.sin(a)) for a in (math.radians(t) for t in range(-60, 61, 6))]
before = set(bpy.data.objects.keys())
msg = pc.surface_sweep(C, pr, pts, TOP, span)
line = [bpy.data.objects[n_] for n_ in set(bpy.data.objects.keys()) - before][0]
data = json.loads(line[base_mesh.SWEEP_KEY])
mw = line.matrix_world
rs = [(mw @ v.co).length for v in line.data.vertices]
bm = bmesh.new()
bm.from_mesh(line.data)
nm = sum(1 for e in bm.edges if not e.is_manifold)
vol = bm.calc_volume(signed=True)
bm.free()
check('Press + Plate, Line: the stamp\'s section swept along the stroke laid ON the sphere - a live swept part (SWEEP data with '
      'surface + per-point ups), every ring standing on the surface: all points between the surface (sunk a hair) and one '
      'section above it, closed',
      data.get('surface') == 'Sphere' and len(data['path3']) == len(data['up3']) >= 10 and min(rs) > 2.0 - 0.1 * span
      and max(rs) < 2.0 + 1.1 * span and max(rs) > 2.0 + 0.5 * span and nm == 0 and vol > 0 and 'Plate line on Sphere' in msg,
      (msg[:80], min(rs), max(rs), nm))
n0 = len(line.data.vertices)
line.mch_base.line_detail = 2.0
rs2 = [(line.matrix_world @ v.co).length for v in line.data.vertices]
check('... live: more detail rebuilds it on the surface', len(line.data.vertices) > n0 and min(rs2) > 2.0 - 0.1 * span and max(rs2) < 2.0 + 1.1 * span)
check('... the sweep keeps every surface point (no corner simplifying) and takes the stored ups',
      "if len(path) > 3 and not surface:" in inspect.getsource(base_mesh._build_sweep_bmesh) and 'nearest_attrs(stations, orig, ups)' in inspect.getsource(base_mesh._build_sweep_bmesh))
# the press: the stamp as a plate (the unified operator's plate press)


class PressShim:
    def __init__(self):
        self.anchor, self.projector, self.state, self.make_mesh = (500.0, 500.0), TOP, 'WAIT', True
        self.timer = self.handle = self.handle_red = None
        self.region = types.SimpleNamespace(tag_redraw=lambda: None)
        self.reports = []

    def report(self, kind, msg):
        self.reports.append((kind, msg))


for name in ('_plate_press', '_cleanup'):
    setattr(PressShim, name, getattr(pc.MCH_OT_press_unified, name))
before = set(bpy.data.objects.keys())
op = PressShim()
r = op._plate_press(C)
new = [bpy.data.objects[n_] for n_ in set(bpy.data.objects.keys()) - before]
check('Press + Plate, a press: the stamp outline at the press point becomes an Armor Plate on the sphere (no hold)',
      r == {'FINISHED'} and len(new) == 1 and 'Plate' in new[0].name and new[0].type == 'MESH' and len(new[0].data.polygons) > 0
      and op.state == 'DONE', (r, [o.name for o in new], op.reports[-1:]))
pr.result = 'CPLATE'
before = set(bpy.data.objects.keys())
op = PressShim()
op.anchor = (420.0, 520.0)
r = op._plate_press(C)
new = [bpy.data.objects[n_] for n_ in set(bpy.data.objects.keys()) - before]
check('... Creature Plate too', r == {'FINISHED'} and len(new) == 1 and 'Creature' in new[0].name, (r, [o.name for o in new]))
src_m = inspect.getsource(pc.MCH_OT_press_unified.modal)
check('wired: the hold timer and the quick tap go to the plate press with a plate result (Alt = the cut as before)',
      src_m.count('return self._plate_press(context)') == 2 and 'self.make_mesh and plate_result(' in src_m)
pr.result = 'CUT'

# --- 5. the folds -----------------------------------------------------------------------------------------------------
real_st = kl._stroke_tool
kl._stroke_tool = lambda c: 'CUT'
try:
    WM.mch_legend_min = False
    b1 = kl.box(CTX)
    x0, y0, w_, h1, rows1, _kw = b1
    hit_title = kl.title_hit(CTX, x0 + w_ / 2, y0 + h1 - 10)
    hit_body = kl.title_hit(CTX, x0 + w_ / 2, y0 + 10)
    on_card = kl.card_hit(CTX, x0 + w_ / 2, y0 + 10)
    kl.toggle(CTX)
    b2 = kl.box(CTX)
    check('the key legend card: a click on its title line folds it to the title (one row, a small card); the body is not the button',
          hit_title and not hit_body and on_card and WM.mch_legend_min and len(b2[4]) == 1 and b2[3] < h1 * 0.4 and b2[2] < w_,
          (hit_title, hit_body, len(rows1), len(b2[4]), h1, b2[3]))
    kl.toggle(CTX)
    check('... and opens again', not WM.mch_legend_min and len(kl.box(CTX)[4]) == len(rows1))
    check('a press on the card never starts a stroke (over_ui) and the title click is caught before the bars',
          qh.over_ui(CTX, x0 + w_ / 2, y0 + 10) and 'key_legend.title_hit' in inspect.getsource(qh.MCH_OT_quick_hud_press.invoke)
          and hasattr(bpy.types, 'MCH_OT_legend_fold'))
finally:
    kl._stroke_tool = real_st
    WM.mch_legend_min = False
check('the legend COMMON rows name E', any('E   Smart Move' in ln for ln in kl.COMMON))
summary()
