"""0.24.73 Live rebuilds at a steady pace (code review R10): a slider drag sends an update for every pixel; Base Mesh
and Face Extract rebuilt the whole part on each of them (Plate Detail already waited for the slider to stop).

``queue(key, fn)``: ``fn()`` runs soon - at most once every ``interval`` while updates keep coming (the part follows
the drag), and once more after the last one (the exact final value).  The interval follows the rebuild's own cost
(twice its last run time, at least MIN_INTERVAL), so a heavy part doesn't fill every frame with rebuilds.  Ctrl+Z /
Ctrl+Shift+Z / loading a file drop what is waiting (it belongs to the state being left).  Without a window (tests,
command line) ``fn`` runs at once.  ``fn`` should look its object up by name: an object reference kept across Ctrl+Z
points at freed memory.
"""
from __future__ import annotations

import time

import bpy

MIN_INTERVAL = 0.05
MAX_INTERVAL = 0.5
SLOW = 0.12              # 0.24.95 Fast Preview: a part whose full rebuild takes longer is remade at the Preview
SETTLE = 0.35            # Resolution while the drag goes on, and at the full one this long after the last update
_PENDING = {}            # key -> fn
_COST = {}               # key -> seconds the last run took
_LAST = {}               # key -> when it last ran
_ARMED = [False]
_FULL = {}               # key -> fn: remade at the Preview Resolution, waiting for its full-Resolution run
_FULLCOST = {}           # key -> seconds the last full-Resolution run took
_TOUCH = {}              # key -> when the last update came


def queue(key, fn):
    if bpy.app.background:
        fn()
        return
    _TOUCH[key] = time.perf_counter()
    _PENDING[key] = fn
    if not _ARMED[0]:
        _ARMED[0] = True
        bpy.app.timers.register(_tick, first_interval=_wait(key))


def _interval(key):
    return min(MAX_INTERVAL, max(MIN_INTERVAL, 2.0 * _COST.get(key, 0.0)))


def _wait(key):
    return max(0.0, _LAST.get(key, 0.0) + _interval(key) - time.perf_counter())


def _run(key, fn, draft=False):
    from . import tool_state as ts
    t = time.perf_counter()
    ts.DRAFT[0] = draft
    try:
        fn()
    except Exception as ex:                          # (a failed rebuild never stops the queue)
        print('Mecha Lab live rebuild:', key, ex)
    finally:
        ts.DRAFT[0] = False
    _COST[key] = time.perf_counter() - t
    _LAST[key] = time.perf_counter()
    if not draft:
        _FULLCOST[key] = _COST[key]


def _wants_draft(key):
    """0.24.95 Fast Preview: on, lower than the Resolution, and this part is slow at the full one."""
    from . import tool_state as ts
    return ts.draft_differs() and _FULLCOST.get(key, 0.0) > SLOW


def _tick():
    _ARMED[0] = False
    todo = list(_PENDING.items())
    _PENDING.clear()
    for key, fn in todo:
        if _wants_draft(key):
            _run(key, fn, draft=True)
            _FULL[key] = fn
            if not bpy.app.timers.is_registered(_settle):
                bpy.app.timers.register(_settle, first_interval=SETTLE)
        else:
            _FULL.pop(key, None)
            _run(key, fn)
    return None


def _settle():
    """The drag stopped (no update for SETTLE): the parts shown at the Preview Resolution are made at the full one."""
    now = time.perf_counter()
    for key, fn in list(_FULL.items()):
        if key in _PENDING or now - _TOUCH.get(key, 0.0) < SETTLE:
            continue
        _FULL.pop(key, None)
        _run(key, fn)
    return SETTLE * 0.5 if _FULL else None


def flush():
    """Run everything waiting now, at the full Resolution (before an Apply / export, and in tests)."""
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    if bpy.app.timers.is_registered(_settle):
        bpy.app.timers.unregister(_settle)
    _ARMED[0] = False
    todo = dict(_FULL)
    todo.update(_PENDING)
    _FULL.clear()
    _PENDING.clear()
    for key, fn in todo.items():
        _run(key, fn)


def drop(*_args):
    _PENDING.clear()
    _FULL.clear()
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    if bpy.app.timers.is_registered(_settle):
        bpy.app.timers.unregister(_settle)
    _ARMED[0] = False


_drop = bpy.app.handlers.persistent(drop)
_HANDLERS = ('undo_pre', 'redo_pre', 'load_pre')


def register():
    for name in _HANDLERS:
        lst = getattr(bpy.app.handlers, name)
        if _drop not in lst:
            lst.append(_drop)


def unregister():
    drop()
    for name in _HANDLERS:
        lst = getattr(bpy.app.handlers, name)
        while _drop in lst:
            lst.remove(_drop)
