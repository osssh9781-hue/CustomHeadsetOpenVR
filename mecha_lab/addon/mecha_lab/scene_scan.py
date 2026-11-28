"""0.24.349 (user: "성능이랑 안정성") the few objects a depsgraph handler cares about (live tubes, lofts, greeble
lines, rigs, hair with a view-width modifier ...) without looking at every object of the scene at every update.

Each handler used to walk ``scene.objects`` on every depsgraph update - with 2,000 objects that was ~4 ms an update
(the add-on tripled the cost of a move / sculpt step).  ``candidates`` keeps the names that passed the test and
walks the whole scene again only when the scene's object count changed, after an undo / load, or once ``MAX_AGE``
has passed (an object turned into one of them by a setting, not a new object, is picked up within that time); the
kept ones are tested again each call (a cheap test of a few objects), so one that stopped being one drops out at
once."""
from __future__ import annotations

import time

import bpy
from bpy.app.handlers import persistent

MAX_AGE = 1.0
_CACHE = {}                 # (key, scene name) -> (object count, time, [names])


def candidates(key, scene, test, depsgraph=None):
    """The scene's objects for which ``test(ob)`` is true (a list; the scene walked only now and then).  With the
    update's ``depsgraph`` the objects it updated are tested too - one just turned into one counts at once."""
    try:
        objs = scene.objects
        n = len(objs)
    except (ReferenceError, AttributeError):
        return []
    ck = (key, scene.name)
    hit = _CACHE.get(ck)
    now = time.monotonic()
    if hit is None or hit[0] != n or now - hit[1] > MAX_AGE:
        out = []
        for ob in objs:
            try:
                if test(ob):
                    out.append(ob)
            except (ReferenceError, AttributeError, RuntimeError):
                continue
        _CACHE[ck] = (n, now, [o.name for o in out])
        return out
    out = []
    names = list(hit[2])
    if depsgraph is not None:
        from . import undo_guard
        if not undo_guard.quiet():
            try:
                for u in depsgraph.updates:
                    idb = u.id
                    if isinstance(idb, bpy.types.Object):
                        nm = idb.original.name
                        if nm not in names:
                            names.append(nm)
            except (ReferenceError, AttributeError, RuntimeError):
                pass
    for name in names:
        ob = objs.get(name)
        try:
            if ob is not None and test(ob):
                out.append(ob)
        except (ReferenceError, AttributeError, RuntimeError):
            continue
    if len(out) != len(hit[2]) or any(o.name not in hit[2] for o in out):
        _CACHE[ck] = (n, hit[1], [o.name for o in out])
    return out


def forget(*_a):
    _CACHE.clear()


@persistent
def _on_reset(*_a):
    _CACHE.clear()


_LISTS = ('load_post', 'undo_post', 'redo_post')


def register():
    for nm in _LISTS:
        lst = getattr(bpy.app.handlers, nm)
        if _on_reset not in lst:
            lst.append(_on_reset)


def unregister():
    for nm in _LISTS:
        lst = getattr(bpy.app.handlers, nm)
        while _on_reset in lst:
            lst.remove(_on_reset)
    _CACHE.clear()
