"""0.24.95 the global Resolution on parts already made (user: "기존 부품도 해상도 다시 올리기", and the Final High
Poly export builds on it): every live part is made again with the current Resolution.  Base Mesh resamples its
stored outline (its curved runs x new / drawn Resolution, corners and straight edges kept - ``cg.reres_loop``); the
other tools rebuild from their settings, whose segment counts follow the Resolution.  Applied / frozen parts have
nothing to rebuild from and are left as they are (counted in the message)."""
from __future__ import annotations

import bpy

from . import tool_state as ts


def _pg(ob, name):
    return getattr(ob, name, None)


def kinds():
    """[(label, test(ob), rebuild(context, ob))] - the live parts that take the Resolution, geometry first, the
    modifier-only ones (Hollow) last so they sit on the new geometry."""
    from . import base_mesh as bm, cable, creature_plate as cpl, curve_tube as ct, edge_molding as emo
    from . import face_extract as fx, flower_plate as fp, hollow_shell as hs, mech_ridge as mr
    from . import plate_detail as pd, screw_stamp as ss, station_primitive as sp
    return [
        ('Base Mesh', lambda o: o.type == 'MESH' and bool(_pg(o, 'mch_base') and o.mch_base.live
                                                          and o.mch_base.outline), lambda c, o: bm.rebuild(o)),
        ('Plate', lambda o: o.type == 'MESH' and bool(_pg(o, 'mch_extract') and o.mch_extract.is_part
                                                      and o.mch_extract.region is not None), lambda c, o: fx.rebuild(o)),
        ('Tube', ct.is_tube, lambda c, o: ct.rebuild(o)),
        ('Cable', lambda o: o.type == 'CURVE' and bool(_pg(o, 'mch_cable') and o.mch_cable.active),
         lambda c, o: cable.rebuild_look(o)),
        ('Screw', ss.is_screw, lambda c, o: ss.rebuild(o)),
        ('Primitive', lambda o: o.type == 'MESH' and bool(_pg(o, 'mch_station') and o.mch_station.live),
         lambda c, o: sp.rebuild(o)),
        ('Molding', lambda o: o.type == 'MESH' and bool(_pg(o, 'mch_molding') and o.mch_molding.is_molding
                                                        and o.mch_molding.chains), lambda c, o: emo.rebuild(o)),
        ('Plate Detail', pd.is_detail, lambda c, o: pd.rebuild(o)),
        ('Ridge', lambda o: o.type == 'MESH' and mr.source(o) is not None, mr.rebuild),
        ('Creature Plate', lambda o: o.type == 'MESH' and cpl.source(o) is not None, cpl.rebuild),
        ('Flower Plate', lambda o: o.type == 'MESH' and fp.source(o) is not None, fp.rebuild),
        ('Hollow', lambda o: o.type == 'MESH' and bool(_pg(o, 'mch_hollow') and o.mch_hollow.active),
         lambda c, o: hs.sync(o)),
    ]


def live_kinds(ob):
    out = []
    for label, test, fn in kinds():
        try:
            ok = bool(test(ob))
        except Exception:                     # (a property group missing on this object type)
            ok = False
        if ok:
            out.append((label, fn))
    return out


def apply(context, obs):
    """Rebuild every live part in ``obs`` at the current Resolution.  Returns (counts {label: n}, left (names of
    meshes with nothing to rebuild), failed [text])."""
    counts, left, failed = {}, [], []
    for ob in obs:
        todo = live_kinds(ob)
        if not todo:
            if ob.type in {'MESH', 'CURVE'}:
                left.append(ob.name)
            continue
        for label, fn in todo:
            try:
                fn(context, ob)
                counts[label] = counts.get(label, 0) + 1
            except Exception as ex:
                failed.append(f'{ob.name}: {ex}')
    return counts, left, failed


def describe(counts, left, failed):
    pct = int(round(ts.res_scale() * 100))
    if counts:
        msg = f'Resolution {pct} %: ' + ', '.join(f'{n} {label}' for label, n in counts.items()) + ' rebuilt'
    else:
        msg = f'Resolution {pct} %: no live part to rebuild'
    if left:
        msg += f' | {len(left)} applied / plain mesh{"es" if len(left) != 1 else ""} kept as they are'
    if failed:
        msg += ' | failed: ' + '; '.join(failed[:3])
    return msg


class MCH_OT_apply_resolution(bpy.types.Operator):
    bl_idname = 'mch.apply_resolution'
    bl_label = 'Apply Resolution to Parts'
    bl_description = ('Make the selected parts again at the current Resolution (nothing selected: every part in the '
                      'scene) - Base Mesh outlines, bevels, tubes, plates, screws ... Applied parts are kept as they are')
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obs = list(context.selected_objects) or list(context.scene.objects)
        counts, left, failed = apply(context, obs)
        msg = describe(counts, left, failed)
        self.report({'WARNING'} if failed else {'INFO'}, msg)
        return {'FINISHED'}


classes = (MCH_OT_apply_resolution,)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
