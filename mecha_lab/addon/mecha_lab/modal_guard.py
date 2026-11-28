"""0.24.349 a safety net for every Mecha Lab modal tool (user: "성능이랑 안정성").

When Python code inside an operator's ``modal()`` raises, Blender drops the operator at once - without calling its
``cancel()`` - so whatever it had put up stayed behind: its viewport drawing (a stale outline, or an error printed
at every redraw), its timer (redraws and wake-ups forever), a modal cursor, a header text.  ``install()`` wraps each
Mecha Lab operator's ``modal`` so that on such an error the tool's own ``cancel()`` runs (it knows what it made), and
any draw handler / timer kept on the operator itself is removed too; the error is printed (with where) and reported.

Nothing changes while a tool works normally: the wrapper only calls through (one Python call more per event)."""
from __future__ import annotations

import time
import traceback

import bpy

_WRAPPED = {}                 # class -> its own modal (put back by uninstall)
ERRORS = []                   # (time, operator idname, message) of the errors caught - for tests and Debug
SPACES = ('SpaceView3D', 'SpaceImageEditor', 'SpaceNodeEditor', 'SpaceSequenceEditor', 'SpaceClipEditor')
REGIONS = ('WINDOW', 'UI', 'HEADER', 'TOOL_HEADER')


def _remove_handle(h):
    """A draw handler of unknown space / region: off (False when it was not one)."""
    for sp in SPACES:
        st = getattr(bpy.types, sp, None)
        if st is None:
            continue
        for rg in REGIONS:
            try:
                st.draw_handler_remove(h, rg)
                return True
            except (ValueError, TypeError, RuntimeError):
                continue
    return False


def _is_capsule(v):
    return type(v).__name__ == 'PyCapsule'


def cleanup(op, context):
    """What the operator ``op`` left up: its cancel(), then draw handlers / timers kept on it, cursor, texts."""
    done = []
    if hasattr(type(op), 'cancel'):
        try:
            type(op).cancel(op, context)
            done.append('cancel')
        except Exception:                                 # noqa: BLE001  (its own cleanup failed too: go on)
            traceback.print_exc()
    try:
        items = list(vars(op).items())
    except TypeError:
        items = []
    wm = getattr(context, 'window_manager', None) or bpy.context.window_manager
    for k, v in items:
        try:
            if _is_capsule(v) and _remove_handle(v):
                done.append(k)
                setattr(op, k, None)
            elif isinstance(v, bpy.types.Timer):
                wm.event_timer_remove(v)
                done.append(k)
                setattr(op, k, None)
        except (ReferenceError, ValueError, TypeError, RuntimeError, AttributeError):
            pass
    try:
        win = getattr(context, 'window', None)
        if win is not None:
            win.cursor_modal_restore()
        if getattr(context, 'area', None) is not None:
            context.area.header_text_set(None)
            context.area.tag_redraw()
        if getattr(context, 'workspace', None) is not None:
            context.workspace.status_text_set(None)
    except (ReferenceError, AttributeError, RuntimeError, TypeError):
        pass
    return done


def _wrap(cls, fn):
    def modal(self, context, event):
        try:
            return fn(self, context, event)
        except Exception as ex:                           # noqa: BLE001  (any error: the tool ends cleanly)
            idname = getattr(cls, 'bl_idname', cls.__name__)
            print(f'[Mecha Lab] {idname} stopped by an error - cleaned up after it:')
            traceback.print_exc()
            done = cleanup(self, context)
            ERRORS.append((time.time(), idname, f'{type(ex).__name__}: {ex}', done))
            del ERRORS[:-20]
            try:
                self.report({'ERROR'}, f'{getattr(cls, "bl_label", idname)} stopped: {type(ex).__name__}: {ex}')
            except (ReferenceError, RuntimeError, AttributeError):
                pass
            return {'CANCELLED'}
    modal.__wrapped__ = fn
    modal.__doc__ = fn.__doc__
    return modal


def _ours(cls):
    return 'mecha_lab' in (getattr(cls, '__module__', '') or '')


def install(classes=None):
    """Wrap the ``modal`` of every registered Mecha Lab operator (once).  Returns how many."""
    if classes is None:
        classes = [c for c in bpy.types.Operator.__subclasses__() if _ours(c)]
        seen = set(classes)
        stack = list(classes)
        while stack:                                       # (sub-classes of our operators too)
            for s in stack.pop().__subclasses__():
                if s not in seen and _ours(s):
                    seen.add(s)
                    classes.append(s)
                    stack.append(s)
    n = 0
    for cls in classes:
        fn = cls.__dict__.get('modal')
        if fn is None or cls in _WRAPPED or getattr(fn, '__wrapped__', None) is not None:
            continue
        _WRAPPED[cls] = fn
        cls.modal = _wrap(cls, fn)
        n += 1
    return n


def uninstall():
    for cls, fn in list(_WRAPPED.items()):
        try:
            cls.modal = fn
        except (AttributeError, TypeError):
            pass
    _WRAPPED.clear()
