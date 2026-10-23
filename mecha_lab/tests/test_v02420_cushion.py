"""0.24.20 Base Mesh profile Cushion: the drawn outline becomes a soft cushion - puffy on both sides, pinched to a
seam around the edge; Height = total thickness, Edge Round = how puffy the rim is."""
from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Quaternion

import mecha_lab
from mecha_lab import base_mesh as bm_mod, core_geometry as cg

TOP = cg.OrthoProjector(Quaternion())
C = bpy.context
SQUARE = [(300, 300), (700, 300), (700, 700), (300, 700)]
mecha_lab.register()


def make(**kw):
    fresh()
    C.scene.cursor.location = (0, 0, 0)
    C.scene.mch_settings.mch_active_tool = 'BASE'
    s = C.scene.mch_base
    s.profile, s.sketch = 'CUSHION', False
    for k, v in kw.items():
        setattr(s, k, v)
    before = set(bpy.data.objects)
    msg = bm_mod.perform_base(C, [SQUARE], TOP)
    new = [o for o in bpy.data.objects if o not in before]
    return (new[0] if len(new) == 1 else None), msg


check('Cushion is a Base Mesh profile (not a Creature one)', 'CUSHION' in [p[0] for p in bm_mod.PROFILES]
      and 'CUSHION' not in bm_mod.CREATURE_PROFILES)
ob, msg = make(height=0.5, edge_round=0.15)
check('Cushion made, closed', ob is not None and non_manifold(ob) == 0, msg)
zs = [(ob.matrix_world @ v.co).z for v in ob.data.vertices]
check('Height = total thickness', abs((max(zs) - min(zs)) - 0.5) < 0.03, round(max(zs) - min(zs), 4))
check('puffy on both sides (symmetric about the drawn plane)', abs(max(zs) + min(zs)) < 0.02, (max(zs), min(zs)))
rim = [(ob.matrix_world @ v.co) for v in ob.data.vertices]
edge = [q.z for q in rim if max(abs(q.x), abs(q.y)) > 1.85]
check('pinched to a seam at the edge', edge and max(abs(z) for z in edge) < 0.12, max(abs(z) for z in edge or [0]))
mid = [q.z for q in rim if abs(q.x) < 0.5 and abs(q.y) < 0.5]
r_low = sorted(q.z for q in rim if 1.2 < abs(q.x) < 1.4 and abs(q.y) < 0.3)[-1]
ob.mch_base.edge_round = 0.5
rim2 = [(ob.matrix_world @ v.co) for v in ob.data.vertices]
r_high = sorted(q.z for q in rim2 if 1.2 < abs(q.x) < 1.4 and abs(q.y) < 0.3)[-1]
check('Edge Round: a bigger, puffier rim (lower toward the edge)', r_high < r_low - 0.01 and ob.mch_base.last_error == '',
      (r_low, r_high))
check('Edge Round: still closed', non_manifold(ob) == 0)
check('the middle is the fullest', mid and max(mid) >= max(zs) - 0.02)
ob.mch_base.height = 0.8
zs = [(ob.matrix_world @ v.co).z for v in ob.data.vertices]
check('Height slider rebuilds the cushion', abs((max(zs) - min(zs)) - 0.8) < 0.04)
try:
    bm_mod._perform_cutter(C, [(SQUARE, [])], None, C.scene.mch_base, None, None, [object()])
    check('Alt cutter refuses a cushion (no flat cap)', False)
except cg.CutError as ex:
    check('Alt cutter refuses a cushion (no flat cap)', 'Cushion' in str(ex), str(ex))
summary()
