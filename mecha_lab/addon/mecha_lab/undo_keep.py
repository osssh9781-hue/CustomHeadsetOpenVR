"""0.24.65 Ctrl+Z undoes what you did (a stroke, a cut, DynaMesh, a new part ...), never the settings you chose.

Two things made Ctrl+Z take settings back:
    - every click / drag on a setting in the drawn UI was an undo step of its own,
    - undoing an operation brings the whole scene back to the step before it - the tool settings too, also the ones
      changed after that step (Blender's global undo).
``is_setting`` tells the drawn UI which values are settings (no undo step for them), and ``snapshot`` /
``restore`` (run by tool_state's undo / redo handlers) put the settings back as they were just before Ctrl+Z:
    - every tool's settings on the Scene (``scene.mch_*``: numbers, switches, choices - written straight into their
      storage, so no update runs and nothing is rebuilt); a group that is editing a live part right now (its
      ``live`` / ``active`` switch on) is left to the undo, its values belong to that part,
    - the sculpt settings of the ZBrush screen: brush size / strength (unified), symmetry, cavity auto masking, and
      the active brush's own settings (spacing, stroke, Focal Shift curve, LazyMouse, Accu, alpha ...).
"""
from __future__ import annotations

import bpy

SIMPLE = {'BOOLEAN', 'INT', 'FLOAT', 'ENUM'}
SKIP = {'active', 'live', 'live_last_cut', 'mch_enabled'}
UNIFIED = ('size', 'unprojected_radius', 'strength', 'color', 'secondary_color', 'use_unified_size',
           'use_unified_strength', 'use_unified_color', 'use_locked_size')
SCULPT = ('use_symmetry_x', 'use_symmetry_y', 'use_symmetry_z')
BRUSH = ('size', 'unprojected_radius', 'strength', 'spacing', 'stroke_method', 'direction', 'use_smooth_stroke',
         'smooth_stroke_factor', 'smooth_stroke_radius', 'use_frontface', 'use_accumulate', 'use_pressure_size',
         'use_pressure_strength', 'cursor_color_add', 'cursor_color_subtract', 'use_primary_overlay')
_SNAP = {}


def _live(pg):
    return any(isinstance(getattr(pg, n, None), bool) and getattr(pg, n) for n in ('live', 'active'))


def is_setting(data):
    """A value that is a setting (tool / brush / view), not part of the model: no undo step of its own."""
    if data is None:
        return False
    types = tuple(t for t in (getattr(bpy.types, n, None) for n in (
        'Brush', 'UnifiedPaintSettings', 'ToolSettings', 'Paint', 'View3DOverlay', 'View3DShading', 'SpaceView3D',
        'AddonPreferences', 'MeshAutomaskingSettings')) if t is not None)
    if isinstance(data, types):
        return True
    return isinstance(data, bpy.types.PropertyGroup) and isinstance(getattr(data, 'id_data', None),
                                                                    bpy.types.Scene) and not _live(data)


def _groups(scene):
    for prop in scene.bl_rna.properties:
        if prop.type == 'POINTER' and prop.identifier.startswith('mch_'):
            pg = getattr(scene, prop.identifier, None)
            if isinstance(pg, bpy.types.PropertyGroup):
                yield prop.identifier, pg


def _keys(pg):
    for p in pg.bl_rna.properties:
        if p.type in SIMPLE and not p.is_readonly and p.identifier not in SKIP and \
                not getattr(p, 'is_hidden', False) and not getattr(p, 'is_skip_save', False):
            yield p.identifier


def _raw(pg, key):
    v = pg.get(key)
    return v.to_list() if hasattr(v, 'to_list') else v


def _plain(v):
    return tuple(v) if hasattr(v, '__len__') and not isinstance(v, str) else v


def _brush_key(b):
    return (b.name, b.library.filepath if b.library is not None else '') if b is not None else None


def snapshot(scene):
    _SNAP.clear()
    if scene is None:
        return
    _SNAP['scene'] = scene.name
    groups = {}
    for name, pg in _groups(scene):
        if not _live(pg):
            groups[name] = {k: _raw(pg, k) for k in _keys(pg)}
    _SNAP['groups'] = groups
    ts = scene.tool_settings
    sc = getattr(ts, 'sculpt', None)
    if sc is None:
        return
    u = getattr(sc, 'unified_paint_settings', None) or getattr(ts, 'unified_paint_settings', None)
    if u is not None:
        _SNAP['unified'] = {a: _plain(getattr(u, a)) for a in UNIFIED if hasattr(u, a)}
    _SNAP['sculpt'] = {a: getattr(sc, a) for a in SCULPT if hasattr(sc, a)}
    am = getattr(sc, 'mesh_automasking_settings', None) or sc
    if hasattr(am, 'use_automasking_cavity'):
        _SNAP['cavity'] = bool(am.use_automasking_cavity)
    b = sc.brush
    if b is not None:
        from . import zb_sculpt
        tex = b.texture
        slot = b.texture_slot
        _SNAP['brush'] = {
            'key': _brush_key(b), 'vals': {a: _plain(getattr(b, a)) for a in BRUSH if hasattr(b, a)},
            'focal': int(b[zb_sculpt.FOCAL_KEY]) if zb_sculpt.FOCAL_KEY in b.keys() else None,
            'preset': b.curve_distance_falloff_preset,
            'texture': (tex.name, tex.library.filepath if tex.library is not None else '') if tex else None,
            'slot': (tuple(slot.scale), slot.angle, slot.map_mode, bool(getattr(slot, 'use_rake', False)))
            if slot is not None else None}


def _find_texture(key):
    name, lib = key
    for t in bpy.data.textures:
        if t.name == name and (t.library.filepath if t.library is not None else '') == lib:
            return t
    return None


def restore(scene):
    """Put the settings back as they were just before Ctrl+Z / Ctrl+Shift+Z; the names of what changed."""
    if scene is None or _SNAP.get('scene') != scene.name:
        return []
    changed = []
    for name, keep in _SNAP.get('groups', {}).items():
        pg = getattr(scene, name, None)
        if pg is None or _live(pg):
            continue
        for key, v in keep.items():
            try:
                if v is None:
                    if key in pg.keys():
                        del pg[key]
                        changed.append(f'{name}.{key}')
                elif _raw(pg, key) != v:
                    pg[key] = v                          # (straight into the storage: no update, no rebuild)
                    changed.append(f'{name}.{key}')
            except (TypeError, KeyError, ValueError, OverflowError):
                pass
    ts = scene.tool_settings
    sc = getattr(ts, 'sculpt', None)
    if sc is None:
        return changed

    def put(owner, vals, tag):
        for a, v in vals.items():
            try:
                if _plain(getattr(owner, a)) != v:
                    setattr(owner, a, v)
                    changed.append(f'{tag}.{a}')
            except (TypeError, AttributeError, ValueError):
                pass
    u = getattr(sc, 'unified_paint_settings', None) or getattr(ts, 'unified_paint_settings', None)
    if u is not None:
        put(u, _SNAP.get('unified', {}), 'unified')
    put(sc, _SNAP.get('sculpt', {}), 'sculpt')
    am = getattr(sc, 'mesh_automasking_settings', None) or sc
    if 'cavity' in _SNAP and hasattr(am, 'use_automasking_cavity'):
        put(am, {'use_automasking_cavity': _SNAP['cavity']}, 'automask')
    keep = _SNAP.get('brush')
    b = sc.brush
    if keep and b is not None and _brush_key(b) == keep['key']:
        put(b, keep['vals'], 'brush')
        from . import zb_sculpt
        if keep['focal'] is not None:
            if b.curve_distance_falloff_preset != 'CUSTOM' or b.get(zb_sculpt.FOCAL_KEY) != keep['focal']:
                zb_sculpt.set_focal_curve(b, keep['focal'])
                changed.append('brush.focal')
        elif b.curve_distance_falloff_preset != keep['preset']:
            put(b, {'curve_distance_falloff_preset': keep['preset']}, 'brush')
        tex = _find_texture(keep['texture']) if keep['texture'] else None
        if (keep['texture'] is None and b.texture is not None) or (tex is not None and b.texture != tex):
            b.texture = tex
            changed.append('brush.texture')
        if keep['slot'] is not None and b.texture_slot is not None:
            scale, angle, mode, rake = keep['slot']
            slot = b.texture_slot
            if tuple(slot.scale) != scale or slot.angle != angle or slot.map_mode != mode or slot.use_rake != rake:
                for attr, val in (('scale', scale), ('angle', angle), ('map_mode', mode), ('use_rake', rake)):
                    try:                               # (0.24.69 a map mode the brush cannot take now - e.g. no
                        setattr(slot, attr, val)       # texture: no Area Plane - stopped the whole restore)
                    except (TypeError, ValueError, AttributeError):
                        pass
                changed.append('brush.slot')
    return changed
