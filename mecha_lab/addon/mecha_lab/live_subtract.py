"""0.24.21 Alt + draw on a live Creature Plate / Plate Detail: that area is taken out of it, like a Boolean.

Each Alt outline is kept on the object (screen loops + the frozen view) and cut out again after every rebuild, so
the plate stays live: its sliders still work and the hole / notch stays where you drew it.  Apply keeps the mesh
as it is.
"""
from __future__ import annotations

import json

import bpy

from . import core_geometry as cg

KEY = 'mch_subtract'


def records(ob):
    try:
        raw = ob.get(KEY)
        return json.loads(raw) if raw else []
    except (TypeError, ValueError, ReferenceError):
        return []


def add(ob, loops, projector):
    from . import armor_plate as ap
    frozen = ap.freeze_projector(projector)
    if frozen is None:
        raise cg.CutError('This view cannot be saved for the cut.')
    recs = records(ob)
    recs.append({'loops': [[[float(x), float(y)] for x, y in lp] for lp in loops], 'proj': frozen})
    ob[KEY] = json.dumps(recs)


def clear(ob):
    if KEY in ob:
        del ob[KEY]


def apply(context, ob):
    """Cut every kept Alt outline out of the object's current mesh (after a rebuild)."""
    from . import armor_plate as ap
    recs = records(ob)
    if not recs or ob.type != 'MESH' or not ob.data.polygons:
        return 0
    done = 0
    for rec in recs:
        projector = ap.thaw_projector(rec['proj'])
        groups = cg.prepare_loops([[tuple(q) for q in lp] for lp in rec['loops']])
        near, far = cg.depth_planes(projector, cg.object_world_bounds([ob]), 'THROUGH')
        cutter = cg.link_temp_object(context, cg.build_cutter_mesh(groups, projector, near, far, 'MCH_SubCut'))
        try:
            me = cg.evaluate_boolean(context, ob, cutter, 'DIFFERENCE', solver='EXACT')
        finally:
            cg.remove_object_and_mesh(cutter)
        try:
            old = ob.data
            mats = list(old.materials)
            smooth = any(poly.use_smooth for poly in old.polygons)     # keep the plate's smooth shading
            old.clear_geometry()
            import bmesh
            bm = bmesh.new()
            try:
                bm.from_mesh(me)
                bm.to_mesh(old)
            finally:
                bm.free()
            if not old.materials and mats:
                for m in mats:
                    old.materials.append(m)
            cg.remove_cutter_attribute(old)
            if smooth:
                for poly in old.polygons:
                    poly.use_smooth = True
            old.update()
            done += 1
        finally:
            bpy.data.meshes.remove(me)
    return done


def _plate_kind(ob, mode):
    if ob is None:
        return False
    if mode == 'CPLATE':
        from . import creature_plate as cpl
        return bool(getattr(ob, 'mch_cplate', None) is not None and ob.mch_cplate.live and cpl.source(ob))
    from . import plate_detail as pd
    return bool(pd.is_detail(ob) and getattr(ob.mch_pdetail, 'live', False))


def pick(context, mode, loops, projector):
    """The live plate of this tool under the outline (the active one first if it is under it), else None."""
    probes = []
    for lp in loops:
        probes.append((sum(q[0] for q in lp) / len(lp), sum(q[1] for q in lp) / len(lp)))
        probes += list(lp[::max(1, len(lp) // 12)])
    dg = context.evaluated_depsgraph_get()
    counts = {}
    from mathutils import Vector
    for xy in probes:
        o, d = projector.ray(xy)
        o, d = Vector(o), Vector(d).normalized()
        for _k in range(16):
            hit, loc, _n, _i, hob, _m = context.scene.ray_cast(dg, o, d)
            if not hit or hob is None:
                break
            real = bpy.data.objects.get(hob.name)
            if _plate_kind(real, mode):
                counts[real.name] = counts.get(real.name, 0) + 1
                break
            o = loc + d * 1e-4
    act = context.active_object
    if act is not None and act.name in counts:
        return act
    if counts:
        return bpy.data.objects[max(counts, key=counts.get)]
    return None


def perform(context, mode, loops, projector):
    """Alt + draw: cut the outline out of the live plate under it.  Returns a report; raises cg.CutError."""
    ob = pick(context, mode, loops, projector)
    if ob is None and mode == 'CPLATE':
        from . import creature_plate as cpl      # 0.24.23 no live plate under it: engrave into the mesh
        return cpl.engrave(context, loops, projector)
    if ob is None:
        what = 'Creature Plate' if mode == 'CPLATE' else 'Plate Detail'
        raise cg.CutError(f'Alt + draw cuts a live {what}: draw over one (nothing was made).')
    before = records(ob)
    add(ob, loops, projector)
    try:
        if mode == 'CPLATE':
            from . import creature_plate as cpl
            cpl.rebuild(context, ob)
        else:
            from . import plate_detail as pd
            pd.rebuild(ob)
    except Exception:
        ob[KEY] = json.dumps(before)
        raise
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    return f'Cut out of "{ob.name}" ({len(records(ob))} cut{"s" if len(records(ob)) > 1 else ""}; it stays live)'
