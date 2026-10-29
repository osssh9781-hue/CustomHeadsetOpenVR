"""0.24.34 Targets for every tool (like Cut): Auto Target / Selected Only / Active.

One setting (Scene.mch_cut.targets, the same row as in the Cut panel) decides which meshes a tool may draw on or
pick under the mouse:

* Auto Target: whatever mesh is under the mouse / the drawn shape (as before).
* Selected Only: only the selected meshes - anything else in front is looked through.
* Active: only the active mesh.

A selected live part (a plate, band, cape ... made by a tool) also lets its base mesh through, so after a stroke
(the new part becomes the selection) the next stroke still lands on the same mesh.

``scene_ray`` is ``Scene.ray_cast`` that skips meshes the setting leaves out.
"""
from __future__ import annotations

import json

import bpy
from mathutils import Matrix, Vector

# tools whose panel already has the row (Cut / Split / Box Hide) or their own targets (Concept / Path Move)
OWN_ROW = {'CUT', 'SPLIT', 'HIDE', 'CMOVE', 'CPATH', 'SMOVE'}
# viewport tools that draw on / pick a mesh under the mouse: these get the row in their panel
PICKING = {'SDRAW', 'BASE', 'CBASE', 'PLATE', 'CPLATE', 'BELT', 'SPIKE', 'SCALES', 'SBRUSH', 'BRIDGE', 'FLOWER',
           'SCURVE', 'CAPE', 'SCAPE', 'HAIR', 'GARMENT', 'HOOD', 'SCARF', 'DETAIL', 'DETAIL2', 'DETAIL3', 'SCREW', 'WRINKLE', 'CDRAPE', 'WLINES',
           'PRIMITIVE', 'MASK', 'TUBE', 'TUBE_SAME', 'DRAW', 'CABLE'}


def mode(context):
    cut = getattr(context.scene, 'mch_cut', None)
    return getattr(cut, 'targets', 'AUTO') if cut is not None else 'AUTO'


def _bases(ob):
    """Names of the meshes a generated part was drawn on (its source's 'target')."""
    out = []
    try:
        keys = list(ob.keys())
    except (TypeError, AttributeError, ReferenceError):
        return out
    for k in keys:
        if not (k.startswith('mch_') and (k.endswith('_src') or k.endswith('_source'))):
            continue
        v = ob.get(k)
        try:
            data = json.loads(v) if isinstance(v, str) else None
        except ValueError:
            data = None
        if isinstance(data, dict) and isinstance(data.get('target'), str):
            out.append(data['target'])
    for group, attr in (('mch_extract', 'source'), ('mch_live', 'target'), ('mch_live', 'source')):
        try:                                      # Armor Plate / Face Extract parts, live sweeps
            src = getattr(getattr(ob, group, None), attr, None)
        except (AttributeError, ReferenceError):
            src = None
        if src is not None and src.type == 'MESH':
            out.append(src.name)
    try:
        if ob.parent is not None and ob.parent.type == 'MESH':
            out.append(ob.parent.name)
    except (AttributeError, ReferenceError):
        pass
    return out


def allowed(context):
    """None = every mesh (Auto Target), else the set of object names a tool may use."""
    how = mode(context)
    if how == 'AUTO':
        return None
    if how == 'ACTIVE':
        ob = context.view_layer.objects.active
        picked = [ob] if ob is not None else []
    else:
        picked = list(context.selected_objects)
    names = set()
    for ob in picked:
        if ob is None or ob.type != 'MESH':
            continue
        names.add(ob.name)
        names.update(_bases(ob))
    return names


def ok(context, ob, names=None):
    """May a tool use this object?"""
    if names is None:
        names = allowed(context)
        if names is None:
            return True
    try:
        return ob.name in names or ob.get('mch_preview_source') in names
    except (AttributeError, ReferenceError):
        return False


def scene_ray(context, depsgraph, origin, direction, distance=None):
    """Scene.ray_cast, looking through the meshes the Targets setting leaves out."""
    kw = {} if distance is None else {'distance': distance}
    names = allowed(context)
    if names is None:
        return context.scene.ray_cast(depsgraph, origin, direction, **kw)
    o, d = Vector(origin), Vector(direction).normalized()
    left = distance
    for _ in range(64):
        res = context.scene.ray_cast(depsgraph, o, d, **({} if left is None else {'distance': left}))
        hit, loc, _n, _i, ob, _m = res
        if not hit or ob is None:
            return res
        real = bpy.data.objects.get(ob.name) or ob
        if ok(context, real, names):
            return res
        if left is not None:
            left -= (Vector(loc) - o).length + 1e-4
            if left <= 0:
                break
        o = Vector(loc) + d * 1e-4
    return False, Vector(), Vector(), -1, None, Matrix()


def label(context):
    return {'AUTO': '', 'SELECTED': 'only the selected meshes', 'ACTIVE': 'only the active mesh'}.get(mode(context), '')
