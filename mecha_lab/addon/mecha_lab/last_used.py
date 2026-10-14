"""0.20.2 Last used options: the next use of a tool starts with what you used last.

* Live results (Cloth Plate inputs, Armor Plate profile / lines / rims) are
  remembered when you change them, relative to the size of that piece, and
  applied to the next one you draw (``remember`` / ``recall``).
* Tool settings (Mecha scene settings) are kept in a small JSON file in
  Blender's config folder (config/mecha_lab/last_used.json) and filled into a
  NEW, unsaved file - files you open are never changed.

Nothing here touches Blender's own preferences.
"""
from __future__ import annotations

import json
import os

import bpy
from bpy.app.handlers import persistent

FILE = 'last_used.json'
PG_NAMES = ('mch_brush', 'mch_cut', 'mch_base', 'mch_plate', 'mch_wrinkle', 'mch_random', 'mch_mirror')
_DATA = None
_DIRTY = False


def _path():
    try:
        d = bpy.utils.user_resource('CONFIG', path='mecha_lab', create=True)
    except (TypeError, ValueError, RuntimeError, OSError):
        return None
    return os.path.join(d, FILE) if d else None


def data():
    global _DATA
    if _DATA is None:
        _DATA = {}
        p = _path()
        if p and os.path.exists(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    _DATA = json.load(f) or {}
            except (OSError, ValueError):
                _DATA = {}
    return _DATA


def save():
    global _DIRTY
    p = _path()
    if not p:
        return
    try:
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(data(), f, indent=1)
        _DIRTY = False
    except OSError:
        pass


def remember(section, key, value):
    """Remember one value of a live result (call when the user changes it)."""
    global _DIRTY
    sec = data().setdefault(section, {})
    if sec.get(key) != value:
        sec[key] = value
        _DIRTY = True


def recall(section):
    return dict(data().get(section, {}))


def forget(section):
    global _DIRTY
    if section in data():
        del data()[section]
        _DIRTY = True


# -----------------------------------------------------------------------------
# Tool settings (scene property groups)
# -----------------------------------------------------------------------------


def _pg_values(pg):
    out = {}
    for prop in pg.bl_rna.properties:
        k = prop.identifier
        if k in {'rna_type', 'name'} or prop.type in {'POINTER', 'COLLECTION'} or getattr(prop, 'is_readonly', False):
            continue
        try:
            v = getattr(pg, k)
        except AttributeError:
            continue
        if isinstance(v, (bool, int, float, str)):
            out[k] = v
        elif hasattr(v, '__len__') and all(isinstance(x, (int, float, bool)) for x in v):
            out[k] = list(v)
    return out


def store_scene(scene):
    global _DIRTY
    if scene is None:
        return
    pgs = data().setdefault('_scene', {})
    for name in PG_NAMES:
        pg = getattr(scene, name, None)
        if pg is not None:
            vals = _pg_values(pg)
            if pgs.get(name) != vals:
                pgs[name] = vals
                _DIRTY = True


def restore_scene(scene):
    """Fill the remembered tool settings into ``scene`` (used for new files only)."""
    pgs = data().get('_scene', {})
    for name, vals in pgs.items():
        pg = getattr(scene, name, None)
        if pg is None:
            continue
        for k, v in vals.items():
            try:
                setattr(pg, k, v)
            except (AttributeError, TypeError, ValueError):
                pass


@persistent
def _on_load_pre(*_args):
    try:
        store_scene(bpy.context.scene)
        save()
    except (AttributeError, RuntimeError):
        pass


@persistent
def _on_load_post(*_args):
    try:
        # a new file in the Blender window starts with the last used settings (not in background /
        # command line runs, which need the plain defaults)
        if not bpy.data.filepath and not bpy.app.background:
            restore_scene(bpy.context.scene)
    except (AttributeError, RuntimeError):
        pass


@persistent
def _on_save_pre(*_args):
    try:
        store_scene(bpy.context.scene)
        save()
    except (AttributeError, RuntimeError):
        pass


def _tick():
    try:
        store_scene(bpy.context.scene)
        if _DIRTY:
            save()
    except (AttributeError, RuntimeError, ReferenceError):
        pass
    return 20.0


def register():
    for lst, fn in ((bpy.app.handlers.load_pre, _on_load_pre), (bpy.app.handlers.load_post, _on_load_post),
                    (bpy.app.handlers.save_pre, _on_save_pre)):
        if fn not in lst:
            lst.append(fn)
    if not bpy.app.background and not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=20.0, persistent=True)


def unregister():
    for lst, fn in ((bpy.app.handlers.load_pre, _on_load_pre), (bpy.app.handlers.load_post, _on_load_post),
                    (bpy.app.handlers.save_pre, _on_save_pre)):
        if fn in lst:
            lst.remove(fn)
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    if _DIRTY:
        save()
