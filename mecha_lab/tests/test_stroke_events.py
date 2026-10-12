"""Simulated-event test of the Cut/Split stroke state machine.

The real operator class only adds Blender RNA on top of ``StrokeLogic``; here
the same logic is fed with fake events and a fake viewport.  This verifies the
P0 interaction rules (one cut per stroke = one undo step, Ctrl+Z / Esc /
Backspace, double-click without duplicate point, RMB single vs double, Space,
pass-through outside the viewport, tool/shape switching).

It is NOT a substitute for the Blender 5.0.2 GUI checklist: real event
ordering, double-click timing and popup behaviour must still be verified.
"""
import sys
import types

from _harness import bpy, check, cube, fresh, non_manifold, select_only, summary, volume
from mathutils import Quaternion

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce

TOP = cg.OrthoProjector(Quaternion())
CALLS = []
CLOCK = [100.0]

ce.make_projector = lambda region, rv3d: TOP
ce.add_draw_handler = lambda op: 'handle'
ce.remove_draw_handler = lambda h: None
ce.open_popup = lambda name: CALLS.append(('popup', name))
ce.exit_tool = lambda context: CALLS.append(('exit',))
ce._now = lambda: CLOCK[0]


class Region:
    type = 'WINDOW'
    x = y = 0
    width = height = 1000

    def tag_redraw(self):
        pass


class WM:
    def __init__(self):
        self.timers = 0

    def modal_handler_add(self, op):
        pass

    def event_timer_add(self, step, window=None):
        self.timers += 1
        return object()

    def event_timer_remove(self, timer):
        self.timers -= 1


class Ctx:
    def __init__(self, native='mecha.cut'):
        self.region = Region()
        self.area = types.SimpleNamespace(type='VIEW_3D', regions=[self.region], as_pointer=lambda: 2)
        self.region_data = object()
        self.space_data = types.SimpleNamespace(region_3d=self.region_data)
        self.window_manager = WM()
        self.window = types.SimpleNamespace(as_pointer=lambda: 1)
        self.mode = 'OBJECT'
        self.preferences = bpy.context.preferences
        self.native = native
        self.status = None
        ctx = self

        class Tools:
            def from_space_view3d_mode(self, mode, create=False):
                return types.SimpleNamespace(idname=ctx.native)

        self.workspace = types.SimpleNamespace(tools=Tools(), status_text_set=self._status)

    def _status(self, text):
        self.status = text

    scene = property(lambda self: bpy.context.scene)
    view_layer = property(lambda self: bpy.context.view_layer)
    selected_objects = property(lambda self: bpy.context.selected_objects)

    def evaluated_depsgraph_get(self):
        return bpy.context.evaluated_depsgraph_get()


def E(type_, value='PRESS', x=500, y=500, alt=False, shift=False, ctrl=False):
    return types.SimpleNamespace(type=type_, value=value, mouse_x=x, mouse_y=y, alt=alt,
                                 shift=shift, ctrl=ctrl, oskey=False)


class Op(ce.StrokeLogic):
    def __init__(self, mode='CUT'):
        self.mode = mode
        self.reports = []

    def report(self, kind, msg):
        self.reports.append((tuple(kind), msg))


def setup(shape='LASSO'):
    fresh()
    s = bpy.context.scene
    s.mch_settings.auto_apply = True
    s.mch_brush.shape = shape
    s.mch_brush.line_open = False
    t = cube('Target')
    select_only(t)
    CALLS.clear()
    CLOCK[0] += 10.0                       # separate scenarios in time (triple-click window)
    ce._TRIPLE_STATE.clear()
    return t


def click(op, ctx, x, y, **kw):
    r1 = op.modal(ctx, E('LEFTMOUSE', 'PRESS', x, y, **kw))
    if r1 != {'RUNNING_MODAL'}:
        return r1
    return op.modal(ctx, E('LEFTMOUSE', 'RELEASE', x, y, **kw))


mecha_lab.register()

# 1. Lasso: invoke + clicks + double-click => one FINISHED, no duplicate point
t = setup('LASSO')
ctx, op = Ctx(), Op()
check('lasso invoke starts modal', op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 450, 450)) == {'RUNNING_MODAL'})
op.modal(ctx, E('LEFTMOUSE', 'RELEASE', 450, 450))
click(op, ctx, 550, 450)
click(op, ctx, 550, 550)
op.modal(ctx, E('LEFTMOUSE', 'PRESS', 450, 550))
op.modal(ctx, E('LEFTMOUSE', 'RELEASE', 450, 550))
check('lasso has 4 points before confirm', len(op.pts) == 4, op.pts)
r = op.modal(ctx, E('LEFTMOUSE', 'DOUBLE_CLICK', 450, 550))
check('double-click confirms (FINISHED => one undo step)', r == {'FINISHED'}, (r, op.reports))
check('double-click did not add a point', len(op.pts) == 4)
check('lasso cut applied', abs(volume(t) - 6.0) < 1e-4 and non_manifold(t) == 0, volume(t))
check('status text cleared after stroke', ctx.status is None)

# 2. Ctrl+Z / Ctrl+Shift+Z / Backspace inside a stroke; empty => CANCELLED
t = setup('LASSO')
ctx, op = Ctx(), Op()
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 450, 450))
op.modal(ctx, E('LEFTMOUSE', 'RELEASE', 450, 450))
click(op, ctx, 550, 450)
click(op, ctx, 550, 550)
op.modal(ctx, E('Z', ctrl=True))
check('Ctrl+Z removes last point', len(op.pts) == 2)
op.modal(ctx, E('Z', ctrl=True, shift=True))
check('Ctrl+Shift+Z restores it', len(op.pts) == 3)
op.modal(ctx, E('BACK_SPACE'))
check('Backspace removes last point', len(op.pts) == 2)
op.modal(ctx, E('Z', ctrl=True))
r = op.modal(ctx, E('Z', ctrl=True))
check('Ctrl+Z on last point cancels the stroke (no undo step)', r == {'CANCELLED'})
check('mesh untouched after cancelled stroke', abs(volume(t) - 8.0) < 1e-4)

# 3. Esc cancels only the stroke
t = setup('LASSO')
ctx, op = Ctx(), Op()
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 450, 450))
click(op, ctx, 550, 450)
check('Esc -> CANCELLED', op.modal(ctx, E('ESC')) == {'CANCELLED'})
check('Esc leaves mesh untouched', abs(volume(t) - 8.0) < 1e-4)

# 4. Outside the viewport: pass-through, stroke kept (no Esc needed for UI)
t = setup('LASSO')
ctx, op = Ctx(), Op()
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 450, 450))
op.modal(ctx, E('LEFTMOUSE', 'RELEASE', 450, 450))
r1 = op.modal(ctx, E('LEFTMOUSE', 'PRESS', 1200, 500))
r2 = op.modal(ctx, E('MOUSEMOVE', 'NOTHING', 1300, 500))
check('click outside viewport passes through', r1 == {'PASS_THROUGH'} and r2 == {'PASS_THROUGH'})
check('stroke kept after outside click', len(op.pts) == 1)
check('wheel/MMB navigation passes through', op.modal(ctx, E('WHEELUPMOUSE')) == {'PASS_THROUGH'} and
      op.modal(ctx, E('MIDDLEMOUSE')) == {'PASS_THROUGH'})

# 5. Shape or tool switched while a stroke is pending => stroke discarded
t = setup('LASSO')
ctx, op = Ctx(), Op()
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 450, 450))
bpy.context.scene.mch_brush.shape = 'RECT'
check('shape change discards stroke', op.modal(ctx, E('MOUSEMOVE', 'NOTHING')) == {'CANCELLED'})
t = setup('LASSO')
ctx, op = Ctx(), Op()
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 450, 450))
ctx.native = 'builtin.select_box'
check('tool change discards stroke', op.modal(ctx, E('MOUSEMOVE', 'NOTHING')) == {'CANCELLED'})

# 6. RMB single => shape popup after the double-click interval, stroke kept
t = setup('LASSO')
ctx, op = Ctx(), Op()
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 450, 450))
check('RMB press is consumed', op.modal(ctx, E('RIGHTMOUSE')) == {'RUNNING_MODAL'})
op.modal(ctx, E('RIGHTMOUSE', 'RELEASE'))
op.modal(ctx, E('TIMER', 'NOTHING'))
check('no popup before double-click time', ('popup', ce.SHAPE_POPUP) not in CALLS)
CLOCK[0] += 1.0
r = op.modal(ctx, E('TIMER', 'NOTHING'))
check('popup opens after interval', ('popup', ce.SHAPE_POPUP) in CALLS and r == {'RUNNING_MODAL'})
check('stroke still alive after popup', len(op.pts) == 1 and ctx.window_manager.timers == 0)

# 7. RMB double => exit tool, no popup
t = setup('LASSO')
ctx, op = Ctx(), Op()
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 450, 450))
op.modal(ctx, E('RIGHTMOUSE'))
CLOCK[0] += 0.1
r = op.modal(ctx, E('RIGHTMOUSE', 'DOUBLE_CLICK'))
check('RMB double-click exits tool', r == {'CANCELLED'} and ('exit',) in CALLS and
      ('popup', ce.SHAPE_POPUP) not in CALLS)
check('timer cleaned after exit', ctx.window_manager.timers == 0)
t = setup('LASSO')
ctx, op = Ctx(), Op()
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 450, 450))
op.modal(ctx, E('RIGHTMOUSE'))
CLOCK[0] += 0.1
r = op.modal(ctx, E('RIGHTMOUSE', 'PRESS'))   # second PRESS without DOUBLE_CLICK flag
check('two RMB presses inside interval also exit', r == {'CANCELLED'} and ('exit',) in CALLS)

# 8. Space => tool popup, stroke cancelled (Space never confirms)
t = setup('LASSO')
ctx, op = Ctx(), Op()
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 450, 450))
r = op.modal(ctx, E('SPACE'))
check('Space opens tool popup and does not cut', r == {'CANCELLED'} and ('popup', ce.TOOL_POPUP) in CALLS
      and abs(volume(t) - 8) < 1e-4)

# 9. Rectangle drag; tiny drag = click = cancel
t = setup('RECT')
ctx, op = Ctx(), Op()
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 450, 450))
op.modal(ctx, E('MOUSEMOVE', 'NOTHING', 520, 520))
r = op.modal(ctx, E('LEFTMOUSE', 'RELEASE', 550, 550))
check('rect drag release cuts', r == {'FINISHED'} and abs(volume(t) - 6.0) < 1e-4, (r, op.reports))
t = setup('RECT')
ctx, op = Ctx(), Op()
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 450, 450))
check('rect click without drag cancels', op.modal(ctx, E('LEFTMOUSE', 'RELEASE', 451, 451)) == {'CANCELLED'})

# 10. Alt latch => keep inside
t = setup('CIRCLE')
ctx, op = Ctx(), Op()
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 500, 500, alt=True))
r = op.modal(ctx, E('LEFTMOUSE', 'RELEASE', 550, 500))
check('Alt circle keeps inside', r == {'FINISHED'} and volume(t) < 2.0, volume(t))

# 11. 2-point lasso => side pick stage, click removes that side
t = setup('LASSO')
ctx, op = Ctx(), Op()
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 500, 300))
op.modal(ctx, E('LEFTMOUSE', 'RELEASE', 500, 300))
click(op, ctx, 500, 700)
r = op.modal(ctx, E('RET'))
check('2 points + Enter => side stage', r == {'RUNNING_MODAL'} and op.stage == 'SIDE')
op.modal(ctx, E('MOUSEMOVE', 'NOTHING', 700, 500))
r = op.modal(ctx, E('LEFTMOUSE', 'PRESS', 700, 500))
check('side click removes +X half', r == {'FINISHED'} and max(v.co.x for v in t.data.vertices) < 1e-4)

# 12. Split mode through the same logic
t = setup('RECT')
ctx, op = Ctx('mecha.split'), Op('SPLIT')
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 450, 450))
r = op.modal(ctx, E('LEFTMOUSE', 'RELEASE', 550, 550))
check('split stroke creates piece', r == {'FINISHED'} and 'Target_Split' in bpy.data.objects)

# 13. Curve lasso: clicking a placed point cycles its rounding
t = setup('CURVE_LASSO')
ctx, op = Ctx(), Op()
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 430, 430))
op.modal(ctx, E('LEFTMOUSE', 'RELEASE', 430, 430))
click(op, ctx, 570, 430)
click(op, ctx, 570, 570)
click(op, ctx, 430, 570)
click(op, ctx, 570, 430)            # re-click point 1
check('re-click rounds point (level 1)', abs(op.rounds[1] - ce.ROUND_LEVELS[1]) < 1e-6, op.rounds)
click(op, ctx, 570, 430)
click(op, ctx, 570, 430)
click(op, ctx, 570, 430)
check('4 re-clicks cycle back to sharp', op.rounds[1] == 0.0, op.rounds)
click(op, ctx, 570, 570)
r = op.modal(ctx, E('RET'))
check('curve lasso confirm cuts', r == {'FINISHED'} and non_manifold(t) == 0 and volume(t) < 8, op.reports)

# 14. Failure => CANCELLED with message, mesh unchanged
t = setup('RECT')
ctx, op = Ctx(), Op()
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 10, 10))
r = op.modal(ctx, E('LEFTMOUSE', 'RELEASE', 60, 60))
check('miss => CANCELLED + warning, mesh unchanged', r == {'CANCELLED'} and op.reports and
      abs(volume(t) - 8) < 1e-4, op.reports)

# 15. No mesh under cursor and nothing selected => PASS_THROUGH
fresh()
bpy.context.scene.mch_brush.shape = 'LASSO'
ctx, op = Ctx(), Op()
check('no target => PASS_THROUGH', op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 500, 500)) == {'PASS_THROUGH'})

# 16. Idle RMB gate
CALLS.clear()


class Gate(ce.GateLogic):
    pass


ctx = Ctx()
g = Gate()
g.invoke(ctx, E('RIGHTMOUSE'))
check('gate passes other events', g.modal(ctx, E('MOUSEMOVE', 'NOTHING')) == {'PASS_THROUGH'})
CLOCK[0] += 1.0
check('gate single => popup', g.modal(ctx, E('TIMER', 'NOTHING')) == {'FINISHED'} and
      ('popup', ce.SHAPE_POPUP) in CALLS)
CALLS.clear()
g = Gate()
g.invoke(ctx, E('RIGHTMOUSE'))
check('gate double => exit', g.modal(ctx, E('RIGHTMOUSE', 'DOUBLE_CLICK')) == {'FINISHED'} and CALLS == [('exit',)])
check('gate timers cleaned', ctx.window_manager.timers == 0)

mecha_lab.unregister()
sys.exit(1 if summary() else 0)
