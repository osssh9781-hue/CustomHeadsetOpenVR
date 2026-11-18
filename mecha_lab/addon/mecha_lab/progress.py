"""0.24.242 A progress card for long jobs (user: "돌릴 때 팝업으로 진행상황 볼 수 있게 - 게이지 차면서 퍼센트로 숫자 뜨게").

A job is a generator: it does its work in steps and yields ``(fraction 0..1, what it is doing)`` between them; its
``return`` value is the result.  ``start`` runs it from a modal operator - one step per timer tick, the viewport
drawn between the steps - with a card in the middle of the view: the title, a bar filling up, the percent, the
step and the seconds so far.  Esc stops it (the generator is closed: its ``finally`` blocks put things back).
Without a window (background, tests) the whole job runs at once.
"""
import time

import bpy

STATE = {}               # title, frac, label, t0 while a job runs
JOBS = []                # [(title, generator, done callback)] waiting for the modal operator
_handle = None


def running():
    return bool(STATE)


def run_now(gen):
    """The whole job at once.  Returns its result."""
    try:
        while True:
            next(gen)
    except StopIteration as ex:
        return ex.value


def start(context, title, gen, done=None):
    """Run ``gen`` with the progress card (or at once when there is no window).  ``done(result)`` after it.
    Returns 'RUNNING' or the result."""
    win = getattr(context, 'window', None)
    if bpy.app.background or win is None:
        res = run_now(gen)
        if done is not None:
            done(res)
        return res
    JOBS.append((title, gen, done))
    _set(title, 0.0, 'Starting ...')
    bpy.ops.mch.progress_job('INVOKE_DEFAULT')
    return 'RUNNING'


def _set(title, frac, label):
    if not STATE:
        STATE['t0'] = time.monotonic()
    STATE.update(title=title, frac=max(0.0, min(1.0, float(frac))), label=label)
    _redraw()


def _clear():
    STATE.clear()
    _redraw()


def _redraw():
    try:
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    except (AttributeError, ReferenceError, RuntimeError):
        pass


def _draw():
    if not STATE:
        return
    try:
        from . import ui_gpu as G
        context = bpy.context
        region = context.region
        if region is None or region.type != 'WINDOW':
            return
        k = G.ui_factor(context, region)
        w, h = min(560 * k, region.width - 40 * k), 150 * k
        x = (region.width - w) / 2
        y = region.height * 0.55
        G.rounded_rect(x, y, w, h, 18 * k, (0.085, 0.087, 0.095, 0.97))
        G.text(x + 24 * k, y + h - 30 * k, G.fit(STATE.get('title', ''), 16 * k, w - 150 * k), 16 * k, G.TEXT)
        pct = int(round(STATE.get('frac', 0.0) * 100))
        G.text(x + w - 24 * k, y + h - 30 * k, f'{pct}%', 20 * k, G.TEXT, 'RIGHT')
        bx, by, bw, bh = x + 24 * k, y + 58 * k, w - 48 * k, 16 * k
        G.rounded_rect(bx, by, bw, bh, bh / 2, (0.24, 0.245, 0.27, 1.0))
        f = STATE.get('frac', 0.0)
        if f > 0:
            G.rounded_rect(bx, by, max(bh, bw * f), bh, bh / 2, G.ACCENT)
        secs = time.monotonic() - STATE.get('t0', time.monotonic())
        G.text(x + 24 * k, y + 30 * k, G.fit(STATE.get('label', ''), 12 * k, w - 170 * k), 12 * k, G.TEXT_DIM)
        G.text(x + w - 24 * k, y + 30 * k, f'{secs:.0f} s   Esc: stop', 12 * k, G.TEXT_DIM, 'RIGHT')
        G.done()
    except Exception:
        pass


class MCH_OT_progress_job(bpy.types.Operator):
    """Run the waiting job step by step with the progress card"""
    bl_idname = 'mch.progress_job'
    bl_label = 'Working'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def invoke(self, context, event):
        if not JOBS:
            return {'CANCELLED'}
        self.title, self.gen, self.done = JOBS.pop(0)
        self.timer = context.window_manager.event_timer_add(0.02, window=context.window)
        self.ticks = 0
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _end(self, context):
        try:
            context.window_manager.event_timer_remove(self.timer)
        except (ValueError, AttributeError):
            pass
        _clear()

    def modal(self, context, event):
        if event.type == 'ESC' and event.value == 'PRESS':
            try:
                self.gen.close()
            except Exception:
                pass
            self._end(context)
            self.report({'WARNING'}, f'{self.title}: stopped')
            return {'CANCELLED'}
        if event.type != 'TIMER':
            return {'RUNNING_MODAL'}
        self.ticks += 1
        if self.ticks < 3:                               # (the card drawn once before the first heavy step)
            return {'RUNNING_MODAL'}
        try:
            frac, label = next(self.gen)
            _set(self.title, frac, label)
            return {'RUNNING_MODAL'}
        except StopIteration as ex:
            res = ex.value
        except RuntimeError as ex:
            self._end(context)
            self.report({'WARNING'}, f'{self.title}: {ex}')
            return {'CANCELLED'}
        except Exception as ex:                          # (never a stuck card)
            self._end(context)
            self.report({'ERROR'}, f'{self.title}: {ex!r}')
            return {'CANCELLED'}
        self._end(context)
        if self.done is not None:
            try:
                msg = self.done(res)
                if msg:
                    self.report({'INFO'}, msg)
            except Exception as ex:
                self.report({'WARNING'}, str(ex))
        return {'FINISHED'}


def register():
    global _handle
    bpy.utils.register_class(MCH_OT_progress_job)
    if not bpy.app.background and _handle is None:
        _handle = bpy.types.SpaceView3D.draw_handler_add(_draw, (), 'WINDOW', 'POST_PIXEL')


def unregister():
    global _handle
    if _handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_handle, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _handle = None
    STATE.clear()
    JOBS.clear()
    bpy.utils.unregister_class(MCH_OT_progress_job)
