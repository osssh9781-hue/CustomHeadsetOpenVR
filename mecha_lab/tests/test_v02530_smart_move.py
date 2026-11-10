"""0.24.123 Smart Move (user: "오브젝트를 클릭해, 원하는 메시의 표면에 클릭하면 그 위치로 기존의 로테이션 값은 변하지 않고 가,
그 위치에서 3D 마우스로 그 오브젝트를 로테이션" / "회전축은 오리진 기준으로 하자"): the tool, its wiring, the maths and the
hold (place / 3D-mouse turn about the origin / Enter keeps / Esc puts back) driven with simulated events."""
import math
import os
import types

from _harness import bpy, check, fresh, summary
from mathutils import Euler, Matrix, Vector

import mecha_lab
from mecha_lab import (bottom_bar as bb, key_legend as kl, panel_capture as pcap, quick_hud as qh, smart_move as sm,
                       target_rules as tr, tool_state as ts, ui_tool_settings as uts)

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
st = S.mch_smart

# --- the tool ---------------------------------------------------------------------------------------------------------
row = ts.TOOL_BY_ID.get('SMART')
check('Smart Move is a tool: name, own icon, Blender tool id', row is not None and row[1] == 'Smart Move'
      and os.path.isfile(os.path.join(os.path.dirname(sm.__file__), 'icons', row[3] + '.png'))
      and row[5] == 'mecha.smart_move' and ts.NATIVE_TO_TOOL.get('mecha.smart_move') == 'SMART', row)
nums = list(ts._ENUM_NUMBERS.values())
check('... in the Move group after Silhouette Move, its own saved number (61), all numbers unique',
      any(name == 'Move' and ids.index('SMART') == ids.index('SMOVE') + 1 for name, ids in ts.TOOL_GROUPS if 'SMART' in ids)
      and dict((t[0], t[4]) for t in ts.TOOL_ENUM_ITEMS)['SMART'] == 61 and len(nums) == len(set(nums)))
check('... in the V pie under Move / Path / Silhouette; the bottom bar keeps its tools', 'SMART' in bb.PIE_SHARED['PRIMITIVE']
      and not any(t[0] == 'SMART' for t in bb.BAR_TOOLS))
check('... no Targets / Slow Line rows (nothing is drawn): own row + Move family', 'SMART' in tr.OWN_ROW and 'SMART' in tr.MOVE_TOOLS)
km = [(k[0], k[1]['type'], k[1]['value']) for k in sm.MCH_TOOL_smart_move.bl_keymap]
check('... keymap: HUD dots first, then the hold on LMB press, Esc leaves the tool when idle',
      km == [('mch.quick_hud_press', 'LEFTMOUSE', 'PRESS'), ('mch.smart_move', 'LEFTMOUSE', 'PRESS'), ('mch.exit_tool', 'ESC', 'PRESS')]
      and hasattr(bpy.types, 'MCH_OT_smart_move') and sm.MCH_TOOL_smart_move.bl_idname == 'mecha.smart_move', km)
check('... key legend says what the clicks, the 3D mouse, Enter and Esc do',
      any('3D mouse' in ln and 'origin' in ln for ln in kl.lines('SMART')) and any('Esc' in ln for ln in kl.lines('SMART')))
items = [p for _d, p in qh.items(C, 'SMART')]
check('... Quick HUD: Move / Size, axes, speed, push, lift', items == ['ndof_do', 'axes', 'speed', 'push', 'lift'], items)
st.push = 'OFF'
tree = pcap.capture(uts.DRAWERS['SMART'], C)
props = [n.prop for n in pcap.walk(tree) if n.kind == 'prop' and n.prop not in {'show_help', 'mch_ndof_parts', 'turn_single', 'ndof_do', 'show_axes'}
         and not n.prop.startswith('ax_')]
check('... panel: Turn Axes / Speed / Invert / Push / Lift (Push Speed only with a push; the how-to folded, the 3D Mouse '
      'View / Parts row)', not tree.opts.get('error') and props == ['axes', 'speed', 'invert', 'push', 'lift']
      and 'show_help' in [n.prop for n in pcap.walk(tree) if n.kind == 'prop'], (tree.opts.get('error'), props))
st.push = 'NORMAL'
tree = pcap.capture(uts.DRAWERS['SMART'], C)
check('... Push on: the Push Speed row', 'push_speed' in [n.prop for n in pcap.walk(tree) if n.kind == 'prop'])
groups = sm.top_bar_groups(C, 'SMART')
check('... top bar: 3D Mouse (Move / Size), Turn (Turntable / View / World / Local, Speed, Invert, One Axis), Push (+ X Y Z, Push Speed), Place (Lift)',
      [g[0] for g in groups] == ['3D Mouse', 'Turn', 'Push', 'Place'] and [c['label'] for c in groups[1][1]] == ['Turntable', 'View', 'World', 'Local', 'Speed', 'Invert', 'One Axis']
      and [c['label'] for c in groups[2][1]][3:6] == ['X', 'Y', 'Z'] and [c['label'] for c in groups[0][1]] == ['Move', 'Size']
      and 'Push Speed' in [c['label'] for c in groups[2][1]] and groups[3][1][0]['prop'] == 'lift', groups)
st.push = 'FREE'
check('defaults: Turntable axes (0.24.125: "약간 축이 돌아가 있어"), speed 1, no invert, push Free (0.24.124: "밀기도 넣어줘"), lift 0, '
      'the how-to folded', st.bl_rna.properties['axes'].default == 'TURNTABLE' and st.speed == 1.0 and not st.invert
      and st.bl_rna.properties['push'].default == 'FREE' and st.lift == 0.0 and not st.show_help)
st.axes = 'VIEW'          # (the checks below drive the View / World mappings explicitly)

# --- the maths --------------------------------------------------------------------------------------------------------
def near(a, b, tol=1e-5):
    return (Vector(a) - Vector(b)).length < tol


check('turn_axis WORLD: tilt = world X, twist (device up) = world Z, roll = world -Y (the front view)',
      near(sm.turn_axis((1, 0, 0), 'WORLD'), (1, 0, 0)) and near(sm.turn_axis((0, 1, 0), 'WORLD'), (0, 0, 1))
      and near(sm.turn_axis((0, 0, 1), 'WORLD'), (0, -1, 0)))
R = Euler((0.4, -0.3, 1.1)).to_matrix().to_4x4()
check('turn_axis VIEW: the device axis through the view (world = view^-1 @ v); no view = the front view',
      near(sm.turn_axis((0.2, 0.7, -0.1), 'VIEW', R), R.to_3x3().inverted() @ Vector((0.2, 0.7, -0.1)))
      and near(sm.turn_axis((0, 1, 0), 'VIEW', None), (0, 0, 1)))
# a view looking down at 60 deg, turned 35 deg (a turntable view: its horizon level) - Blender's view_matrix = world -> view
Vm = (Euler((math.radians(60), 0.0, math.radians(35))).to_matrix().to_4x4()).inverted()
vx = Vm.to_3x3().inverted() @ Vector((1, 0, 0))
vz = Vm.to_3x3().inverted() @ Vector((0, 0, 1))
vy = Vm.to_3x3().inverted() @ Vector((0, 1, 0))                   # the screen's up, in the world: tilted with the view
check('turn_axis TURNTABLE (the default): twist (device y) = round the WORLD up Z whatever the view (the View twist is round '
      'the screen\'s up, which this view tilts), tilt (device x) = round the view\'s horizontal, roll (device z) = round the view axis',
      near(sm.turn_axis((0, 1, 0), 'TURNTABLE', Vm), (0, 0, 1)) and abs(vx.z) < 1e-6 and near(sm.turn_axis((1, 0, 0), 'TURNTABLE', Vm), vx)
      and near(sm.turn_axis((0, 0, 1), 'TURNTABLE', Vm), vz) and 0.3 < vz.z < 0.95
      and near(sm.turn_axis((0, 1, 0), 'VIEW', Vm), vy) and 0.3 < vy.z < 0.95
      and near(sm.turn_axis((0, 1, 0), 'TURNTABLE', None), (0, 0, 1)),
      (tuple(sm.turn_axis((0, 1, 0), 'TURNTABLE', Vm)), tuple(vy), tuple(vz)))
check('turn_angle: |v| 1.0 = 360 deg, times the time delta (clamped to 0.1 s; 0 = 1/60) and Speed; Invert flips',
      abs(sm.turn_angle((0, 0.25, 0), 0.05) - 0.25 * 2 * math.pi * 0.05) < 1e-9
      and abs(sm.turn_angle((0, 0.25, 0), 1.0) - 0.25 * 2 * math.pi * 0.1) < 1e-9
      and abs(sm.turn_angle((0.25, 0, 0), 0.0) - 0.25 * 2 * math.pi / 60) < 1e-9
      and abs(sm.turn_angle((0, 0.25, 0), 0.05, 2.0) - 0.25 * 2 * math.pi * 0.1) < 1e-9
      and sm.turn_angle((0, 0.25, 0), 0.05, 1.0, True) < 0)
M = Matrix.Translation((2, 1, 3)) @ Euler((0.2, 0.1, 0.5)).to_matrix().to_4x4() @ Matrix.Diagonal((1, 1.5, 0.6, 1))
M2 = sm.rotate_about(M, (0, 0, 1), math.pi / 2, M.translation)
check('rotate_about its own origin: the origin stays, the part turns (local X -> +Y), the scale stays',
      near(M2.translation, M.translation) and near(M2.to_3x3() @ Vector((1, 0, 0)), Matrix.Rotation(math.pi / 2, 3, 'Z') @ (M.to_3x3() @ Vector((1, 0, 0))))
      and all(abs(a - b) < 1e-6 for a, b in zip(M2.to_scale(), M.to_scale())))
M3 = sm.rotate_about(M, (0, 0, 1), math.pi / 2, (0, 0, 0))
check('... about another pivot the origin goes round it; a zero axis / angle changes nothing',
      near(M3.translation, (-1, 2, 3)) and sm.rotate_about(M, (0, 0, 0), 1.0, (0, 0, 0)) == M and sm.rotate_about(M, (0, 0, 1), 0.0, (0, 0, 0)) == M)
P = sm.place(M, (5, -4, 0.5), (0, 0, 1), 0.25)
check('place: the origin goes to the point + Lift along the normal; rotation and scale untouched',
      near(P.translation, (5, -4, 0.75)) and all(abs(a - b) < 1e-9 for ra, rb in zip(P.to_3x3(), M.to_3x3()) for a, b in zip(ra, rb)))

# --- cast: through the held part to the surface behind ---------------------------------------------------------------
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=1)
slab = C.active_object
slab.name = 'Slab'
slab.scale = (12, 12, 0.6)
slab.location = (0, 0, -0.3)
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 2))
part = C.active_object
part.name = 'Part'
part.rotation_euler = (math.radians(20), 0, math.radians(35))
part.scale = (1, 1.5, 0.6)
C.view_layer.update()
dg = C.evaluated_depsgraph_get()
h1 = sm.cast(S, dg, (0, 0, 8), (0, 0, -1))
h2 = sm.cast(S, dg, (0, 0, 8), (0, 0, -1), skip={'Part'})
check('cast: the first mesh along the ray (the part), with skip = the held part the slab behind it (normal up)',
      h1 is not None and h1[2] is part and h2 is not None and h2[2] is slab and abs(h2[0].z) < 1e-4
      and near(h2[1], (0, 0, 1), 1e-4) and sm.cast(S, dg, (50, 50, 8), (0, 0, -1)) is None)
check('hit_under without a region (headless) is None, not an error', sm.hit_under(C, (10, 10)) is None)
check('selectable: a shown mesh yes, a hidden one no', sm.selectable(part) and not sm.selectable(None))


# --- the hold, driven with simulated events ----------------------------------------------------------------------------
class Ev:
    def __init__(self, type_, value='PRESS', ndof=None, x=100, y=100):
        self.type, self.value, self.ndof_motion = type_, value, ndof
        self.mouse_region_x, self.mouse_region_y = x, y
        self.shift = self.alt = self.ctrl = False


class Shim:
    def __init__(self):
        self.reports = []
        self.from_key = False

    def report(self, kind, msg):
        self.reports.append((kind, msg))


for name in ('_setup', '_hook', '_unhook', '_header', '_object', '_finish', '_place', '_ndof', '_target_for', 'invoke', 'modal'):
    setattr(Shim, name, getattr(sm.MCH_OT_smart_move, name))

S.mch_settings.mch_active_tool = 'SMART'            # (no native tool headless: the chosen tool is Smart Move)
check('the tool enum takes SMART and effective_tool reads it', ts.effective_tool(C) == 'SMART')
op = Shim()
check('a press on nothing (no surface under the mouse) passes through - Blender\'s click goes on',
      op.invoke(C, Ev('LEFTMOUSE')) == {'PASS_THROUGH'} and sm.ACTIVE[0] is None)


def hold(ob):
    op = Shim()
    op._setup()
    op.ob_name, op.orig = ob.name, ob.matrix_world.copy()
    sm.ACTIVE[0] = op
    return op


orig = part.matrix_world.copy()
hit_fake = [(Vector((-2, 1.5, 0)), Vector((0, 0, 1)), slab)]
real_hit_under = sm.hit_under
sm.hit_under = lambda context, xy, skip=(): hit_fake[0] if 'Part' in skip else (Vector((0, 0, 3)), Vector((0, 0, 1)), part)
try:
    op = hold(part)
    r = op.modal(C, Ev('LEFTMOUSE'))
    check('LMB on a surface while holding: the origin goes there, rotation and scale as before, the hit remembered',
          r == {'RUNNING_MODAL'} and near(part.matrix_world.translation, (-2, 1.5, 0))
          and all(abs(a - b) < 1e-9 for ra, rb in zip(part.matrix_world.to_3x3(), orig.to_3x3()) for a, b in zip(ra, rb))
          and op.last_hit is not None and near(op.last_hit[0], (-2, 1.5, 0)), (r, tuple(part.matrix_world.translation)))
    st.lift = 0.3
    op.modal(C, Ev('LEFTMOUSE'))
    check('... Lift: the origin sits that far off the surface along its normal', near(part.matrix_world.translation, (-2, 1.5, 0.3)))
    st.lift = 0.0
    before = part.matrix_world.copy()
    st.axes = 'WORLD'
    ndof = types.SimpleNamespace(rotation=Vector((0, 0.25, 0)), translation=Vector((0, 0, 0)), time_delta=0.1)
    r = op.modal(C, Ev('NDOF_MOTION', 'NOTHING', ndof))
    after = part.matrix_world
    turned = (after.to_3x3() @ before.to_3x3().inverted()).to_quaternion().angle     # (world side: the part is scaled)
    zturn = after.to_3x3() @ Vector((1, 0, 0))
    expect = Matrix.Rotation(0.25 * 2 * math.pi * 0.1, 3, 'Z') @ (before.to_3x3() @ Vector((1, 0, 0)))
    check('3D mouse twist while holding (World axes): the part turns 9 deg about world Z through its ORIGIN - the origin stays, '
          'the event is consumed (the view does not move)',
          r == {'RUNNING_MODAL'} and near(after.translation, before.translation) and abs(math.degrees(turned) - 9.0) < 0.01
          and near(zturn, expect, 1e-6) and abs(op.turned - math.radians(9)) < 1e-9, (r, math.degrees(turned)))
    st.invert = True
    op.modal(C, Ev('NDOF_MOTION', 'NOTHING', ndof))
    check('... Invert turns it back the other way', all(abs(a - b) < 1e-6 for ra, rb in zip(part.matrix_world.to_3x3(), before.to_3x3()) for a, b in zip(ra, rb)))
    st.invert = False
    st.speed = 2.0
    op.modal(C, Ev('NDOF_MOTION', 'NOTHING', ndof))
    turned = (part.matrix_world.to_3x3() @ before.to_3x3().inverted()).to_quaternion().angle
    check('... Speed 2: twice the turn', abs(math.degrees(turned) - 18.0) < 0.01, math.degrees(turned))
    st.speed = 1.0
    st.push = 'NORMAL'
    t0 = part.matrix_world.translation.copy()
    op.modal(C, Ev('NDOF_MOTION', 'NOTHING', types.SimpleNamespace(rotation=Vector((0, 0, 0)), translation=Vector((0, 0, 1)), time_delta=0.1)))
    check('... Push: Normal - pulling the cap up (z, 0.24.126) slides the part up the last surface normal (push speed x view distance x dt)',
          near(part.matrix_world.translation, t0 + Vector((0, 0, 1.0 * 0.5 * 0.1)), 1e-6), tuple(part.matrix_world.translation - t0))
    st.push = 'FREE'
    t0 = part.matrix_world.translation.copy()
    op.modal(C, Ev('NDOF_MOTION', 'NOTHING', types.SimpleNamespace(rotation=Vector((0, 0, 0)), translation=Vector((1, 0, 0)), time_delta=0.1)))
    check('... Push: Free (the default) - the cap pushed right slides the part along the view\'s right (no view: world X)',
          near(part.matrix_world.translation, t0 + Vector((1.0 * 0.5 * 0.1, 0, 0)), 1e-6), tuple(part.matrix_world.translation - t0))
    st.push = 'OFF'
    for et in ('MIDDLEMOUSE', 'WHEELUPMOUSE', 'NUMPAD_1', 'NDOF_BUTTON_FIT', 'MOUSEMOVE', 'G'):
        if op.modal(C, Ev(et)) != {'PASS_THROUGH'}:
            check(f'navigation / other keys pass through ({et})', False, et)
            break
    else:
        check('navigation (MMB, wheel, numpad, NDOF buttons, mouse moves) and other keys pass through', True)
    kept = part.matrix_world.copy()
    r = op.modal(C, Ev('RET'))
    check('Enter keeps: the hold ends, the part stays where it is', r == {'FINISHED'} and sm.ACTIVE[0] is None
          and part.matrix_world == kept)
    op = hold(part)
    op.modal(C, Ev('LEFTMOUSE'))
    moved = part.matrix_world.translation.copy()
    r = op.modal(C, Ev('ESC'))
    check('Esc puts it back: the part is where it was when the hold began', r == {'CANCELLED'} and sm.ACTIVE[0] is None
          and part.matrix_world == kept and not near(moved, kept.translation), (r, tuple(moved)))
    op = hold(part)
    r = op.modal(C, Ev('RIGHTMOUSE'))
    check('RMB / Space keep too', r == {'FINISHED'} and hold(part).modal(C, Ev('SPACE')) == {'FINISHED'})
    op = hold(part)
    S.mch_settings.mch_active_tool = 'CUT'
    r = op.modal(C, Ev('LEFTMOUSE'))
    check('the tool changed meanwhile (strip / pie / Q): the hold ends keeping the part as it is',
          r == {'FINISHED'} and sm.ACTIVE[0] is None)
    S.mch_settings.mch_active_tool = 'SMART'
    op = hold(part)
    bpy.data.objects.remove(part)
    check('the part gone meanwhile (undo / delete): the hold ends quietly', op.modal(C, Ev('LEFTMOUSE')) == {'FINISHED'})
finally:
    sm.hit_under = real_hit_under
    sm.ACTIVE[0] = None
summary()
