"""0.24.349 Ctrl+Z / Ctrl+Shift+Z / file load: one shared "stay out" window for every depsgraph handler that reads
``depsgraph.updates`` (user: "어떤 기능들은 랜덤하게 컨트롤 z 누르면 꺼지니까").

Right after an undo the depsgraph's update list can still point at IDs the undo freed; reading them (``u.id``,
``u.id.original``) crashed Blender - a crash Python cannot catch (0.24.3 user crash log; until now only Curve Tube
and Loft stayed out).  ``quiet()`` is True from the undo / load until a moment after it: a handler then reads no
update list and, instead, its caches are simply dropped (``on_undo`` callbacks - the undone state may differ from
what they held anyway)."""
from __future__ import annotations

import time

import bpy
from bpy.app.handlers import persistent

QUIET_AFTER = 0.3            # seconds the update lists are left alone after an undo / redo / load
_UNTIL = [0.0]
_CLEARS = []
COUNT = {'undo': 0}


def quiet():
    """True while depsgraph update lists must not be read (an undo / load just happened or is happening)."""
    return time.monotonic() < _UNTIL[0]


def on_undo(fn):
    """``fn()`` runs after each undo / redo / load (drop a cache).  Returns fn (a decorator)."""
    if fn not in _CLEARS:
        _CLEARS.append(fn)
    return fn


@persistent
def _pre(*_a):
    _UNTIL[0] = time.monotonic() + 5.0          # (during it; the post below shortens it)


@persistent
def _post(*_a):
    COUNT['undo'] += 1
    _UNTIL[0] = time.monotonic() + QUIET_AFTER
    for fn in list(_CLEARS):
        try:
            fn()
        except Exception:                          # noqa: BLE001  (a cache that would not clear: the next one)
            pass


_LISTS = ('undo_pre', 'redo_pre', 'load_pre', 'undo_post', 'redo_post', 'load_post')


def register():
    for nm in _LISTS:
        lst = getattr(bpy.app.handlers, nm)
        fn = _pre if nm.endswith('_pre') else _post
        if fn not in lst:
            lst.insert(0, fn)                      # (first: before any other handler of ours looks)


def unregister():
    for nm in _LISTS:
        lst = getattr(bpy.app.handlers, nm)
        for fn in (_pre, _post):
            while fn in lst:
                lst.remove(fn)
