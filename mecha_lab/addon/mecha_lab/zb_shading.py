"""0.24.76 The hard look on the ZBrush screen.

Sculpt Mode draws every smooth face with smooth point normals: it ignores the edges marked Sharp (Blender's own limit -
Object Mode honours them, Sculpt Mode never did).  A Make Quad / Quad Remesh part (smooth faces, its cut edges Sharp)
looked soft and blotchy as soon as the ZBrush screen came up.

``apply`` (Object Mode, just before Sculpt Mode on the ZBrush screen): the smooth faces along a Sharp edge are set
flat, so that part looks as hard as in Object Mode.  ``restore`` (back in Object Mode): exactly those faces are smooth
again - the mesh as it was.  Which faces were changed is kept on the object (KEY), so a save / reload or a Ctrl+Z
that lands on a state with them flat is put back too (``tick``, from the ZBrush screen watcher).  When the faces
changed in between (DynaMesh, Remesh ...) there is nothing to put back.
"""
from __future__ import annotations

import bpy
import numpy as np

KEY = 'mch_zb_flat'          # face indices set flat (int array)
KEY_N = 'mch_zb_flat_n'      # the face count then (a changed mesh: nothing to put back)
KEY_NEW = 'mch_zb_flat_new'  # True: there was no sharp_face attribute before (removed again)


def _bools(attr, n):
    out = np.zeros(n, bool)
    if attr is not None and n:
        attr.data.foreach_get('value', out)
    return out


def apply(ob):
    """Set the smooth faces along Sharp edges flat (Object Mode).  Returns how many faces changed."""
    if ob is None or ob.type != 'MESH' or KEY in ob or ob.mode != 'OBJECT':
        return 0
    me = ob.data
    nf, ne = len(me.polygons), len(me.edges)
    se_attr = me.attributes.get('sharp_edge')
    if not nf or se_attr is None or se_attr.domain != 'EDGE' or se_attr.data_type != 'BOOLEAN':
        return 0
    se = _bools(se_attr, ne)
    if not se.any():
        return 0
    sf_attr = me.attributes.get('sharp_face')
    if sf_attr is not None and (sf_attr.domain != 'FACE' or sf_attr.data_type != 'BOOLEAN'):
        return 0
    sf = _bools(sf_attr, nf)
    le = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get('edge_index', le)
    total = np.empty(nf, np.int32)
    me.polygons.foreach_get('loop_total', total)
    start = np.empty(nf, np.int32)
    me.polygons.foreach_get('loop_start', start)
    order = np.argsort(start, kind='stable')
    face_of_loop = np.repeat(order, total[order])         # (loops are stored face after face)
    touch = np.zeros(nf, bool)
    np.logical_or.at(touch, face_of_loop, se[le])
    faces = np.flatnonzero(touch & ~sf)
    if not len(faces):
        return 0
    new = sf_attr is None
    if new:
        sf_attr = me.attributes.new('sharp_face', 'BOOLEAN', 'FACE')
    sf[faces] = True
    sf_attr.data.foreach_set('value', sf)
    me.update()
    ob[KEY] = [int(f) for f in faces]
    ob[KEY_N] = nf
    ob[KEY_NEW] = new
    return len(faces)


def restore(ob):
    """Those faces smooth again (Object Mode).  True when something was put back."""
    if ob is None or ob.type != 'MESH' or KEY not in ob or ob.mode == 'SCULPT':
        return False
    faces = list(ob[KEY])
    n = ob.get(KEY_N, -1)
    new = bool(ob.get(KEY_NEW, False))
    for k in (KEY, KEY_N, KEY_NEW):
        if k in ob:
            del ob[k]
    me = ob.data
    attr = me.attributes.get('sharp_face')
    if len(me.polygons) != n or attr is None:
        return False                          # (other faces now: DynaMesh / Remesh ... - nothing to put back)
    if new:
        me.attributes.remove(attr)
    else:
        sf = _bools(attr, n)
        sf[np.asarray(faces, np.int64)] = False
        attr.data.foreach_set('value', sf)
    me.update()
    return True


def wanted():
    """Only with the ZBrush style (the Blender style stays as Blender has it)."""
    from . import zb_sculpt
    try:
        return zb_sculpt.style() == 'ZBRUSH'
    except (AttributeError, ReferenceError):
        return False


def enter(ob):
    """About to go into Sculpt Mode (from Object Mode) on the ZBrush screen."""
    if wanted():
        try:
            apply(ob)
        except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError) as ex:
            print('[Mecha Lab] ZBrush shading:', ex)


def tick(context=None):
    """Objects left flat outside Sculpt Mode (left another way, an undo, a reload): put back.  True if any."""
    done = False
    for ob in bpy.data.objects:
        try:
            if KEY in ob and ob.mode == 'OBJECT' and restore(ob):
                done = True
        except (AttributeError, ReferenceError, RuntimeError, TypeError):
            continue
    return done
