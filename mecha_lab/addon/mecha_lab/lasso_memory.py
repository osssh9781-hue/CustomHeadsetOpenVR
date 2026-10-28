"""0.24.78 Lasso settings per tool: the shape and its options, the corners, Line and Slow Line you set in one tool
stay with that tool - switching to another tool brings back what you set there (a tool used for the first time
starts with what you had).

The settings are the Mecha brush (``mch_brush``) that every drawing tool shares; on a tool change the old tool's
values are kept and the new tool's put back.  They are saved in the file (``KEY`` on the scene, written on save) and
are left out of undo (kept here in Python), so a Ctrl+Z does not swap them back.  Preferences > Lasso Settings per
Tool turns it off (one shared set again, as before).
"""
from __future__ import annotations

import json

import bpy
from bpy.app.handlers import persistent

from . import tool_state as ts

KEY = 'mch_tool_lasso'
OWNER = 'mch_tool_lasso_owner'      # the tool the brush held the settings of when the file was saved
PROPS = ('shape', 'circle_segments', 'curve_resolution', 'curve_smoothness', 'outline_corner', 'outline_radius',
         'outline_segments', 'stroke_smooth', 'stroke_spacing', 'stroke_simplify', 'mask_brush_radius',
         'custom_size', 'custom_rotation', 'custom_drag_rotate', 'line_open', 'line_mode', 'line_width', 'line_caps',
         'line_taper_on', 'line_taper', 'line_pressure', 'stab_enable', 'stab_strength', 'stab_radius', 'stab_guide')
TICK = 0.2

_STORE = {}         # scene name -> {tool: {prop: value}}  (names: an undo can give the scene a new address)
_LAST = {}          # scene name -> the tool the brush holds the settings of


def enabled():
    from .workspace_ui import pref
    return bool(pref('lasso_per_tool', True))


def values(brush):
    out = {}
    for p in PROPS:
        try:
            v = getattr(brush, p)
        except AttributeError:
            continue
        out[p] = v if isinstance(v, (bool, int, float, str)) else None
    return {p: v for p, v in out.items() if v is not None}


def apply(brush, vals):
    for p, v in vals.items():
        if p not in PROPS:
            continue
        try:
            if getattr(brush, p) != v:
                setattr(brush, p, v)
        except (AttributeError, TypeError, ValueError):
            continue


def store(scene):
    """{tool: {prop: value}} of ``scene`` (read from the file the first time)."""
    key = scene.name_full
    if key not in _STORE:
        data = {}
        try:
            raw = scene.get(KEY)
            if raw:
                data = {t: dict(v) for t, v in json.loads(raw).items() if isinstance(v, dict)}
        except (TypeError, ValueError):
            data = {}
        _STORE[key] = data
    return _STORE[key]


def sync(context=None):
    """The tool changed since the last look: keep the old tool's lasso settings, put the new tool's back.  True when
    something was put back."""
    context = context or bpy.context
    scene = getattr(context, 'scene', None)
    brush = getattr(scene, 'mch_brush', None)
    if brush is None or not enabled():
        return False
    try:
        tool = ts.effective_tool(context)
    except (AttributeError, KeyError, TypeError, ReferenceError):
        return False
    key = scene.name_full
    last = _LAST.get(key)
    if last == tool:
        return False
    st = store(scene)
    _LAST[key] = tool
    if last is None:                          # first look (a file opened, the add-on started)
        owner = scene.get(OWNER, '')
        if owner and owner != tool:           # the brush is still the tool's it was saved with
            if owner in ts.SHAPE_TOOLS:
                st[owner] = values(brush)
        elif tool in ts.SHAPE_TOOLS:          # ... the tool in use (or nothing saved yet)
            st[tool] = values(brush)
            return False
        if tool in ts.SHAPE_TOOLS and tool in st:
            apply(brush, st[tool])
            return True
        return False
    if last in ts.SHAPE_TOOLS:
        st[last] = values(brush)
    if tool in ts.SHAPE_TOOLS and tool in st:
        apply(brush, st[tool])
        return True
    return False


def forget(scene=None):
    """Drop what is kept (tests / a reset): the next look starts again."""
    if scene is None:
        _STORE.clear()
        _LAST.clear()
    else:
        _STORE.pop(scene.name_full, None)
        _LAST.pop(scene.name_full, None)


def _tick():
    try:
        if sync() and bpy.context.screen is not None:
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    except (AttributeError, RuntimeError, ReferenceError, TypeError):
        pass
    return TICK


@persistent
def _on_save_pre(*_args):
    for scene in bpy.data.scenes:
        key = scene.name_full
        if key not in _STORE and not enabled():
            continue
        brush = getattr(scene, 'mch_brush', None)
        st = store(scene)
        last = _LAST.get(key)
        if brush is not None and last in ts.SHAPE_TOOLS:
            st[last] = values(brush)
        try:
            scene[KEY] = json.dumps(st)
            if last:
                scene[OWNER] = last
        except (TypeError, ValueError, AttributeError):
            pass


@persistent
def _on_load_post(*_args):
    forget()


def register():
    for lst, fn in ((bpy.app.handlers.save_pre, _on_save_pre), (bpy.app.handlers.load_post, _on_load_post)):
        if fn not in lst:
            lst.append(fn)
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=1.0, persistent=True)


def unregister():
    for lst, fn in ((bpy.app.handlers.save_pre, _on_save_pre), (bpy.app.handlers.load_post, _on_load_post)):
        if fn in lst:
            lst.remove(fn)
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    forget()
