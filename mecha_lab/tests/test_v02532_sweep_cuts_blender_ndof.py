"""0.24.127
  1. (user: "이거 컷이 안돼" - an S-shaped Press line) a cut on a LIVE swept line vanished at the line's next rebuild
     (thickness, Detail, a ring moved, a stroke continued).  The cutter is remembered and the cut done again after
     every rebuild; a Press hold keeps only its last depth; applying the line drops the memory; a Split applies the line.
  2. (user: "그냥 기존 블렌더 화면 이동이랑 똑같이 맞춰줘") Turn Axes "Blender" (the default): the part moves the way the
     scene moves under Blender's own 3D-mouse navigation (turntable / trackball, sign, sensitivities, dead zone).
  3. (user: "내가 보낸 이미지랑 똑같은 썸네일 넣어서 설정창을 좀 분리해 줘") the 3D Mouse Settings window with the
     cap-motion pictures; the Smart Move panel keeps the essentials + a button."""
import inspect
import math
import types

from _harness import bpy, check, fresh, summary
import bmesh  # noqa: E402
from mathutils import Euler, Quaternion, Vector  # noqa: E402

import mecha_lab
from mecha_lab import (base_mesh, core_geometry as cg, cut_engine as ce, lasso_line, panel_capture as pcap,
                       press_cut as pc, smart_move as sm, ui_tool_settings as uts)

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion())


def near(a, b, tol=1e-5):
    return (Vector(a) - Vector(b)).length < tol


def vol(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    v = round(bm.calc_volume(signed=True), 4)
    n = len(bm.faces)
    bm.free()
    return v, n


def sweep_cut_meshes():
    return [m.name for m in bpy.data.meshes if m.name.startswith('MCH_SweepCut')]


# --- 1. cuts on a live swept line survive its rebuilds --------------------------------------------------------------
pr, cut, brush = S.mch_press, S.mch_cut, S.mch_brush
pr.shape = 'MCH_BUILTIN_M_ROUND_PANEL'
pr.size = 22.0
S.mch_base.line_corner, S.mch_base.line_up, S.mch_base.line_end = 'ROUND', 'BEND', 'ROUND'
pts = [(400 + 150 * math.cos(t), 420 + 150 * math.sin(t)) for t in (math.radians(a) for a in range(200, 500, 6))]
pts += [(pts[-1][0] - 1.4 * k, pts[-1][1] + 2.4 * k) for k in range(1, 120, 4)]


def make_line():
    stamp_px = 44.0
    ppu = lasso_line.pixels_per_unit(C, TOP, pts[0])
    span = stamp_px / ppu
    loops = lasso_line.line_loops(C, TOP, pts, brush, width_px=stamp_px)
    base_mesh.perform_base(C, loops, TOP, cutter=False, attach=None, path=pts, sweep_style='ALPHA',
                           section_width=span, section_height=span, section_rest=True, section_rotation=0.0)
    return C.active_object


for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
line = make_line()
check('a Press line is a live swept line', base_mesh.is_live_sweep(line) and base_mesh.sweep_cuts(line) == [])
v0 = vol(line)
cx, cy = pts[30]
circle = [[(cx + 26 * math.cos(a), cy + 26 * math.sin(a)) for a in (2 * math.pi * i / 24 for i in range(24))]]
msg = ce.perform_closed(C, 'CUT', [line], circle, TOP)
v1 = vol(line)
mem = base_mesh.sweep_cuts(line)
check('the Cut tool on the live line cuts it and remembers the cutter (world-space mesh, kept with a fake user)',
      v1[0] < v0[0] - 0.02 and len(mem) == 1 and mem[0][1] == 'DIFFERENCE' and bpy.data.meshes.get(mem[0][0]) is not None
      and bpy.data.meshes[mem[0][0]].use_fake_user and 'Cut' in msg, (v0, v1, mem))
line.mch_base.line_detail = 1.5
v2 = vol(line)
check('a Detail tweak rebuilds the line - the cut is done again (it vanished before)', v2[1] > v1[1] and abs(v2[0] - v1[0]) < 0.01, (v1, v2))
line.mch_base.line_detail = 1.0
check('... back at Detail 1 the same cut line', abs(vol(line)[0] - v1[0]) < 1e-3)
xy = pts[60]
lp = pc.stamp_loops(C, xy, pr)
target = pc.press_target(C, TOP, xy, lp)
press = pc.Press(C, target, lp, TOP, 'CUT', center=xy, angle=0.0, curve=(0.0, 0.0), spacing=3.0, follow=True, level=False, tilt=(0.0, 0.0))
press.cut_to(C, 0.1)
press.cut_to(C, 0.2)
press.cut_to(C, 0.3)
press.finish(C)
mem = base_mesh.sweep_cuts(line)
v3 = vol(line)
check('a Press hold (three depths, each cut again from the part as it was) leaves ONE memory for the press (+ the first cut)',
      len(mem) == 2 and len(sweep_cut_meshes()) == 2 and v3[0] < v1[0] - 0.005, (len(mem), sweep_cut_meshes(), v3))
line.mch_base.line_detail = 2.0
v4 = vol(line)
check('... both cuts come back after another rebuild', abs(v4[0] - v3[0]) < 0.01 and v4[1] > v3[1], (v3, v4))
press2 = pc.Press(C, target, lp, TOP, 'CUT', center=xy, angle=0.0, curve=(0.0, 0.0), spacing=3.0, follow=True, level=False, tilt=(0.0, 0.0))
press2.cut_to(C, 0.15)
press2.cancel(C)
check('a cancelled press (Esc) leaves no memory of its own', len(base_mesh.sweep_cuts(line)) == 2 and len(sweep_cut_meshes()) == 2)
line.mch_base.live = False
check('applying the line (live off) drops the memory and its cutter meshes', base_mesh.sweep_cuts(line) == [] and sweep_cut_meshes() == []
      and abs(vol(line)[0] - v4[0]) < 1e-6)
line2 = make_line()
msg = ce.perform_closed(C, 'SPLIT', [line2], circle, TOP)
check('a Split on a live line applies it first (two parts are not rebuilt) and remembers nothing',
      not line2.mch_base.live and base_mesh.sweep_cuts(line2) == [] and 'Split' in msg, msg[:60])
# the Line Cut (Alt + drag in Press) on a live line remembers too
line3 = make_line()
v5 = vol(line3)
size = pc.part_size(line3)
span = 44.0 / lasso_line.pixels_per_unit(C, TOP, pts[0])
section, bottom = pc.line_cut_section(C, pr, size * 0.5, span, eps=0.003 * size)
seg = [(pts[30][0] - 40, pts[30][1] - 30), (pts[30][0] + 40, pts[30][1] + 30)]
loops_seg = lasso_line.line_loops(C, TOP, seg, brush, width_px=44.0)
_groups, frame, local_path = base_mesh.sweep_frame(C, loops_seg, TOP, seg)
msg = base_mesh.sweep_cut(C, frame, local_path, section, span, span, bottom, [line3], 'CUT')
v6 = vol(line3)
check('the Line Cut (the stamp\'s section swept) on a live line cuts and remembers', v6[0] < v5[0] - 0.005 and len(base_mesh.sweep_cuts(line3)) == 1, (v5, v6, msg[:60]))
line3.mch_base.line_detail = 1.4
check('... and survives a rebuild', abs(vol(line3)[0] - v6[0]) < 0.01)
src = inspect.getsource(base_mesh.rebuild)
check('wired: rebuild redoes the remembered cuts; the live flag off drops them', '_replay_sweep_cuts(ob)' in src
      and 'update=_live_changed' in inspect.getsource(base_mesh.MCH_PG_BaseMesh))
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)

# --- 2. Turn Axes "Blender" ----------------------------------------------------------------------------------------
st = S.mch_smart
check('Blender (like the view) is the default turn-axes mode, first in the list',
      st.bl_rna.properties['axes'].default == 'BLENDER'
      and [e.identifier for e in st.bl_rna.properties['axes'].enum_items][:2] == ['BLENDER', 'TURNTABLE'])
pr_b = sm.blender_ndof_prefs()
check('Blender\'s 3D-mouse preferences are read with defaults when missing (this bpy has no NDOF)',
      set(pr_b) == {'orbit', 'pan', 'method', 'mode', 'dead', 'zoom_invert'} and pr_b['orbit'] > 0 and pr_b['method'] in {'TURNTABLE', 'TRACKBALL'})
Vm = (Euler((math.radians(60), 0.0, math.radians(35))).to_matrix().to_4x4()).inverted()
rv = types.SimpleNamespace(view_matrix=Vm, view_distance=2.0)
P = {'orbit': 1.0, 'pan': 1.0, 'method': 'TURNTABLE', 'mode': 'OBJECT', 'dead': 0.0, 'zoom_invert': False}
axis, ang, step = sm.blender_motion((0, 0, 0), (0, 0.5, 0), 0.1, rv, P)
check('turntable, Object mode: a twist turns round the WORLD up by time x value x orbit (Blender\'s formula), the Object '
      'sign (the scene follows the hand)', axis is not None and abs(abs(axis.z) - 1.0) < 1e-5 and abs(ang - 0.05) < 1e-5
      and (axis.z * ang) < 0, (tuple(axis) if axis else None, ang))
vx = (Vm.to_3x3().inverted() @ Vector((1, 0, 0))).normalized()
axis, ang, _s = sm.blender_motion((0, 0, 0), (0.5, 0, 0), 0.1, rv, P)
check('... a tilt turns round the view\'s horizontal; a roll does nothing in turntable',
      abs(abs(axis.dot(vx)) - 1.0) < 1e-5 and abs(ang - 0.05) < 1e-5 and sm.blender_motion((0, 0, 0), (0, 0, 0.5), 0.1, rv, P)[0] is None)
P2 = dict(P, method='TRACKBALL')
axis, ang, _s = sm.blender_motion((0, 0, 0), (0, 0, 0.5), 0.1, rv, P2)
vz = (Vm.to_3x3().inverted() @ Vector((0, 0, 1))).normalized()
check('... trackball: round the device vector through the view (a roll = the view axis), the angle positive (the axis carries '
      'the sign)', abs(abs(axis.dot(vz)) - 1.0) < 1e-5 and abs(ang - 0.05) < 1e-5 and ang > 0)
_a, _g, step = sm.blender_motion((1.0, 0, 0), (0, 0, 0), 0.1, rv, P)
check('pan: the view\'s own axes x view distance x time x sensitivity (push right = along the view\'s right, 2 x 0.1 = 0.2)',
      abs(step.length - 0.2) < 1e-6 and abs(abs(step.normalized().dot(vx)) - 1.0) < 1e-6)
_a, _g, step_fly = sm.blender_motion((1.0, 0, 0), (0, 0, 0), 0.1, rv, dict(P, mode='FLY'))
check('... Fly mode: the other way (the scene moves against the hand there)', near(step_fly, -step, 1e-6))
_a, _g, step_d = sm.blender_motion((0.1, 0, 0), (0, 0.1, 0), 0.1, rv, dict(P, dead=0.2))
check('... the dead zone swallows small values', step_d.length == 0.0 and sm.blender_motion((0, 0, 0), (0, 0.1, 0), 0.1, rv, dict(P, dead=0.2))[0] is None)
check('no view: nothing (the callers fall back to the front-view mapping)', sm.blender_motion((1, 0, 0), (0, 1, 0), 0.1, None)[0] is None)
# through ndof_apply on a part
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 1))
part = C.active_object
m0 = part.matrix_world.copy()
st.axes, st.push, st.speed = 'BLENDER', 'FREE', 1.0
data = types.SimpleNamespace(rotation=Vector((0, 0.5, 0)), translation=Vector((1.0, 0, 0)), time_delta=0.1, progress='IN_PROGRESS')
ang, step = sm.ndof_apply(part, data, st, rv)
turn = (part.matrix_world.to_3x3() @ m0.to_3x3().inverted()).to_quaternion()
check('ndof_apply in Blender mode: the part turns 0.05 rad round the world up and slides 0.2 along the view\'s right (prefs: '
      'Blender defaults here)', abs(abs(math.degrees(turn.angle)) - math.degrees(0.05)) < 0.01 and abs(abs(turn.axis.z) - 1) < 1e-4
      and abs(step.length - 0.2) < 1e-6 and (part.matrix_world.translation - m0.translation - step).length < 1e-6,
      (math.degrees(turn.angle), tuple(step)))
part.matrix_world = m0
st.push_x = st.push_y = False
ang, step = sm.ndof_apply(part, data, st, rv)
check('... the Push Axes X / Y / Z toggles still gate the slide', abs(step.x) < 1e-9 and abs(step.y) < 1e-9)
st.push_x = st.push_y = True
part.matrix_world = m0

# --- 3. the settings window and the compact panel ----------------------------------------------------------------
check('the 3D Mouse Settings window exists (an operator dialog) and the six cap-motion pictures load (the icon id itself is 0 '
      'in this background Blender)', hasattr(bpy.types, 'MCH_OT_ndof_settings') and all(sm.axis_icon_loads(k) for k, _l, _d in sm.AXES)
      and 'invoke_props_dialog' in inspect.getsource(sm.MCH_OT_ndof_settings.invoke))
tree = pcap.capture(uts.DRAWERS['SMART'], C)
props = [n.prop for n in pcap.walk(tree) if n.kind == 'prop']
ops = [getattr(n, 'operator', getattr(n, 'op', '')) for n in pcap.walk(tree) if n.kind == 'op']
check('the Smart Move panel keeps the essentials (Does, Turn Axes, Speed, Push, Lift) and a Settings button; the table, push '
      'axes, size speed, invert and One Axis live in the window', not tree.opts.get('error')
      and 'axes' in props and 'push' in props and 'lift' in props and 'ax_lr_on' not in props and 'invert' not in props
      and ('mch.ndof_settings' in ops or 'mch.ndof_settings' in inspect.getsource(sm.draw)), (props, ops))
src_t = inspect.getsource(sm.top_bar_groups)
check('the top bar: Blender first among the turn axes, a Settings... cell', "('BLENDER', 'Blender')" in src_t and "'mch.ndof_settings'" in src_t)
# --- 4. (user: "왜 크리쳐 베이스가 안 나와?") Enter in the Creature Base Mesh tool makes the sketch ------------------------
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
S.mch_settings.mch_active_tool = 'CBASE'
keys_ok = {}
for tool in ('BASE', 'CBASE', 'PRESS', 'CUT'):
    S.mch_settings.mch_active_tool = tool
    S.mch_press.draw_mode, S.mch_press.result = 'LASSO', 'CUT'
    keys_ok[tool] = base_mesh.sketch_tool_ok(C)
check('the sketch keys (Enter / Alt+Enter / Esc / Backspace) work in Base Mesh, Creature Base Mesh and Press Lasso, not in Cut',
      keys_ok == {'BASE': True, 'CBASE': True, 'PRESS': True, 'CUT': False}, keys_ok)
S.mch_settings.mch_active_tool = 'CBASE'
base_mesh.sketch_clear(S)
loop = [(300 + math.cos(a) * 120, 300 + math.sin(a) * 80) for a in [i * math.tau / 24 for i in range(24)]]   # screen pixels
msg = base_mesh.sketch_add(C, [loop], cg.OrthoProjector(Quaternion()))
before = set(bpy.data.objects.keys())
r = bpy.ops.mch.base_sketch_commit('EXEC_DEFAULT')
made = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before if bpy.data.objects[n].type == 'MESH']
check('a Creature Base Mesh sketch + the commit (what Enter runs) makes a rounded part (Puff)',
      'FINISHED' in r and len(made) == 1 and len(made[0].data.polygons) > 50 and made[0].dimensions.z > 0.05
      and made[0].mch_base.profile in base_mesh.CREATURE_PROFILES,
      (r, msg, [(o.name, len(o.data.polygons), tuple(round(d, 2) for d in o.dimensions), o.mch_base.profile) for o in made]))
summary()
