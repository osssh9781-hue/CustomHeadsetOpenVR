"""0.24.349 modal_guard in a real window (run with --enable-event-simulate): a modal tool whose modal() raises.
Without the guard its draw handler and timer stay (drawn / firing after the tool died); with it they are gone and
cancel() ran.  Prints PASS / FAIL lines and quits."""
import sys
import os
import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'addon'))
COUNT = {'draw': 0, 'cancel': 0}
RES = []


def check(name, ok, detail=''):
    RES.append(ok)
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -- {detail}' if detail else ''))


def _draw():
    COUNT['draw'] += 1


def make(name):
    class Op(bpy.types.Operator):
        bl_idname = f'mch.guardtest_{name}'
        bl_label = 'Guard Test'

        def invoke(self, context, event):
            self._h = bpy.types.SpaceView3D.draw_handler_add(_draw, (), 'WINDOW', 'POST_PIXEL')
            self._timer = context.window_manager.event_timer_add(0.05, window=context.window)
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}

        def modal(self, context, event):
            if event.type == 'MOUSEMOVE':
                raise RuntimeError('boom')
            return {'PASS_THROUGH'}

        def cancel(self, context):
            COUNT['cancel'] += 1
    Op.__name__ = f'MCH_OT_guardtest_{name}'
    Op.__module__ = 'mecha_lab.guardtest'
    return Op


def run_case(guard, then):
    from mecha_lab import modal_guard as mg
    cls = make('on' if guard else 'off')
    bpy.utils.register_class(cls)
    if guard:
        mg.install([cls])
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == 'VIEW_3D')
    region = next(r for r in area.regions if r.type == 'WINDOW')
    with bpy.context.temp_override(window=win, area=area, region=region):
        getattr(bpy.ops.mch, cls.bl_idname.split('.')[1])('INVOKE_DEFAULT')
    COUNT['draw'] = 0
    COUNT['cancel'] = 0
    x, y = area.x + area.width // 2, area.y + area.height // 2
    win.event_simulate('MOUSEMOVE', 'NOTHING', x=x, y=y)
    win.event_simulate('MOUSEMOVE', 'NOTHING', x=x + 5, y=y + 5)

    def after():
        a = COUNT['draw']
        with bpy.context.temp_override(window=win, area=area, region=region):
            bpy.ops.wm.redraw_timer(type='DRAW', iterations=5)
        drawn_after = COUNT['draw'] - a
        then(guard, drawn_after, COUNT['cancel'], mg.ERRORS[:])
        return None
    bpy.app.timers.register(after, first_interval=0.5)


def start():
    import mecha_lab  # noqa: F401
    from mecha_lab import modal_guard as mg  # noqa: F401

    def second(guard, drawn, cancels, errs):
        check('with the guard: the dead tool draws no more', drawn == 0, drawn)
        check('with the guard: its cancel() ran', cancels == 1, cancels)
        check('with the guard: the error is recorded', any('boom' in e[2] for e in errs), errs[-1:] if errs else errs)
        print(f'{sum(RES)}/{len(RES)} passed')
        bpy.ops.wm.quit_blender()

    def first(guard, drawn, cancels, errs):
        check('without the guard: Blender leaves the draw handler behind (the problem is real)', drawn > 0, drawn)
        check('without the guard: cancel() is not called', cancels == 0, cancels)
        run_case(True, second)
    run_case(False, first)
    return None


bpy.app.timers.register(start, first_interval=1.0)
