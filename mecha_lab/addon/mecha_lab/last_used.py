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
import re
import shutil

import bpy
from bpy.app.handlers import persistent

FILE = 'last_used.json'
PG_NAMES = ('mch_brush', 'mch_cut', 'mch_base', 'mch_plate', 'mch_wrinkle', 'mch_random', 'mch_mirror')
_DATA = None
_DIRTY = False
# 0.24.183 (user: "내가 만든 클로스 프리셋 다 지웠어?"): what this Blender changed since it last wrote the file - only
# that is written over what the file holds then, so a second Blender open at the same time (its own copy read when
# it started) no longer writes your presets saved in the first one away; a preset is a single entry of its section
_TOUCHED = set()
_ITEMS = {}                       # (section, name) -> the value, or _GONE
_GONE = object()
OTHER_ROOT = [None]               # (a test points it elsewhere: the folder that holds the Blender versions' folders)


def _path():
    try:
        d = bpy.utils.user_resource('CONFIG', path='mecha_lab', create=True)
    except (TypeError, ValueError, RuntimeError, OSError):
        return None
    return os.path.join(d, FILE) if d else None


def _read(p):
    with open(p, 'r', encoding='utf-8') as f:
        d = json.load(f)
    return d if isinstance(d, dict) else None


def _load_disk():
    """(the file's data, where from: 'file' | 'backup' | 'none' | 'unreadable').  0.24.183 an unreadable file (a
    Blender closed while writing it) is never taken for an empty one: its backup (the version before) is read, and
    it is kept aside as ``last_used.json.unreadable`` before anything is written over it."""
    p = _path()
    if not p:
        return {}, 'none'
    try:
        d = _read(p)
        if d is not None:
            return d, 'file'
    except FileNotFoundError:
        pass
    except (OSError, ValueError):
        try:
            if not os.path.exists(p + '.unreadable'):
                shutil.copy2(p, p + '.unreadable')
        except OSError:
            pass
    try:
        d = _read(p + '.bak')
        if d is not None:
            return d, 'backup'
    except (OSError, ValueError):
        pass
    return {}, ('unreadable' if os.path.exists(p) else 'none')


def data():
    global _DATA
    if _DATA is None:
        _DATA = _load_disk()[0]
    return _DATA


def touch(section):
    """``section`` of data() was changed in place: written with the next save."""
    global _DIRTY
    _TOUCHED.add(section)
    _DIRTY = True


def set_item(section, name, value):
    """One entry of a section (a preset) saved or (``value`` None) deleted - written right away, the other entries
    as the file has them then (saved by another Blender meanwhile: kept)."""
    sec = data().setdefault(section, {})
    if value is None:
        sec.pop(name, None)
        _ITEMS[(section, name)] = _GONE
    else:
        sec[name] = value
        _ITEMS[(section, name)] = value
    save()


def save():
    """The file as it is now, with what this Blender changed put over it (written whole to a new file first, then
    swapped in: a Blender closed half-way leaves the old file; the version before kept as ``last_used.json.bak``)."""
    global _DIRTY, _DATA
    p = _path()
    if not p:
        return
    disk, src = _load_disk()
    mine = data()
    for k in _TOUCHED:
        if k in mine:
            disk[k] = json.loads(json.dumps(mine[k]))
        else:
            disk.pop(k, None)
    for (sec, name), v in _ITEMS.items():
        s = disk.get(sec)
        if not isinstance(s, dict):
            s = disk[sec] = {}
        if v is _GONE:
            s.pop(name, None)
        else:
            s[name] = json.loads(json.dumps(v))
    tmp = p + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(disk, f, indent=1)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        if src == 'file':
            try:
                shutil.copy2(p, p + '.bak')
            except OSError:
                pass
        os.replace(tmp, p)
    except OSError:
        return
    _TOUCHED.clear()
    _ITEMS.clear()
    _DIRTY = False
    _DATA = disk                   # (what other Blenders saved meanwhile is seen here now too)


def remember(section, key, value):
    """Remember one value of a live result (call when the user changes it)."""
    global _DIRTY
    sec = data().setdefault(section, {})
    if sec.get(key) != value:
        sec[key] = value
        _TOUCHED.add(section)
        _DIRTY = True


def recall(section):
    return dict(data().get(section, {}))


def forget(section):
    global _DIRTY
    if section in data():
        del data()[section]
        _TOUCHED.add(section)
        _DIRTY = True


def other_versions(section):
    """0.24.183 {Blender version: {name: value}} - ``section`` as the other Blender versions on this computer keep it
    (each version has its own config folder: presets saved in 5.0 are not in 5.2's).  Read only."""
    p = _path()
    root = OTHER_ROOT[0]
    me = None
    if root is None:
        if not p:
            return {}
        verdir = os.path.dirname(os.path.dirname(os.path.dirname(p)))      # (<root>/<version>/config/mecha_lab/..)
        root, me = os.path.dirname(verdir), os.path.basename(verdir)
    out = {}
    try:
        names = os.listdir(root)
    except OSError:
        return {}
    for v in sorted(names, key=_version_key):
        if v == me or not re.match(r'^\d+\.\d+$', v):
            continue
        q = os.path.join(root, v, 'config', 'mecha_lab', FILE)
        if p and os.path.abspath(q) == os.path.abspath(p):
            continue
        d = None
        for f in (q, q + '.bak'):
            try:
                d = _read(f)
            except (OSError, ValueError):
                d = None
            if d is not None:
                break
        sec = (d or {}).get(section)
        if isinstance(sec, dict) and sec:
            out[v] = sec
    return out


def _version_key(v):
    try:
        return tuple(int(x) for x in v.split('.'))
    except ValueError:
        return (0,)


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
                _TOUCHED.add('_scene')
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
