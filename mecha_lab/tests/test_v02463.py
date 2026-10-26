"""0.24.42 Path Move: (1) Extend / Separate Tube only move a section about the brush size - a small brush on a big
plate (its whole cross-section) makes that drag a Stretch with the brush size instead of sweeping the whole plate;
(2) the path never turns tighter than the section (no folded, torn rings)."""
import math
import types

from _harness import bpy, check, fresh, summary
from mathutils import Matrix, Vector

import mecha_lab
from mecha_lab import concept_move as cm

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
st = S.mch_concept

# (2) relax: a sharp corner is opened up to the section radius, the ends stay
P = [Vector((0.1 * i, 0, 0)) for i in range(10)] + [Vector((0.9, 0.1 * k, 0)) for k in range(1, 10)]
R = 0.4
before = min(cm.turn_radius(P[i - 1], P[i], P[i + 1]) for i in range(1, len(P) - 1))
Q = cm.relax_path(P, R)
after = min(cm.turn_radius(Q[i - 1], Q[i], Q[i + 1]) for i in range(1, len(Q) - 1))
check('a 90 degree corner in the path: opened up so no turn is tighter than the section', before < 0.1 and after >= R * 0.999
      and (Q[0] - P[0]).length < 1e-9 and (Q[-1] - P[-1]).length < 1e-9 and len(Q) == len(P), (before, after))
check('a straight path stays as it is', all((a - b).length < 1e-12 for a, b in zip(cm.relax_path(P[:10], R), P[:10])))
check('section radius = the farthest section point from its centre',
      abs(cm.section_radius({'centre': Vector(), 'loop': [Vector((1, 0, 0)), Vector((0, 2, 0))]}) - 2.0) < 1e-9)


# (1) the drag decision on a wide plate: grab its end with a small vs a big brush
bpy.ops.mesh.primitive_cube_add(size=1.0, scale=(3.0, 1.0, 0.1))
plate = C.active_object
bpy.ops.object.transform_apply(scale=True)
st.lock_size = True


def drag(radius):
    st.radius_world = radius
    me = types.SimpleNamespace(ob=plate, mwi=Matrix(), mref=Matrix(), hit=Vector((1.4, 0, 0)),
                               local_hit=Vector((1.4, 0, 0)), info=None, method_now=None, preview_ob=None,
                               trail=[Vector((1.4, 0, 0)), Vector((1.6, 0, 0)), Vector((1.8, 0, 0))])
    for name in ('_section_offsets', '_brush_local', '_method', '_to_local', '_section_preview', '_drop_preview'):
        setattr(me, name, types.MethodType(getattr(cm.MCH_OT_concept_path, name), me))
    st.path_method = 'EXTEND'
    me._section_preview(C)
    out = (me._method(C), bool(me.info))
    me._drop_preview()
    return out


check('small brush on the wide plate end: not the whole plate - this drag becomes a Stretch (brush size)',
      drag(0.1) == ('STRETCH', False), drag(0.1))
check('a brush about as big as the plate end: Extend as before (the section is swept)',
      drag(0.4) == ('EXTEND', True), drag(0.4))
st.lock_size = False
summary()
