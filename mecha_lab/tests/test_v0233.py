"""0.23.3: asymmetric cloth folds (steep folded side + long soft side, Fold Asymmetry),
Fold Thinness (limited by the panel resolution - no beads), Mesh Curve IK."""
import math
import sys

from _harness import bpy, check, fresh, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import cloth_wrinkle as cw, curve_tube as ct

# ---- IK (pure)
pts = [Vector((0, 0, 0)), Vector((1, 0, 0)), Vector((2, 0, 0)), Vector((3, 0, 0))]
lens = [1.0, 1.0, 1.0]


def seglens(p):
    return [(p[k + 1] - p[k]).length for k in range(len(p) - 1)]


out = ct.ik_drag(pts, 3, Vector((2.0, 1.5, 0)), pin_root=True)
check('IK: segment lengths kept', all(abs(a - b) < 1e-4 for a, b in zip(seglens(out), lens)), seglens(out))
check('IK: root pinned', (out[0] - pts[0]).length < 1e-9)
check('IK: tip reaches a reachable target', (out[3] - Vector((2.0, 1.5, 0))).length < 1e-3, tuple(out[3]))
out = ct.ik_drag(pts, 3, Vector((10, 0, 5)), pin_root=True)
check('IK: unreachable target -> chain stretches toward it', all(abs(a - 1) < 1e-6 for a in seglens(out))
      and (Vector((10, 0, 5)) - out[0]).normalized().dot((out[3] - out[0]).normalized()) > 0.99)
out = ct.ik_drag(pts, 1, Vector((0.6, 0.8, 0)), pin_root=True)
check('IK: dragging a middle point pulls the rest like a rope', all(abs(a - 1) < 1e-6 for a in seglens(out))
      and (out[1] - Vector((0.6, 0.8, 0))).length < 1e-3 and (out[0] - pts[0]).length < 1e-9)
out = ct.ik_drag(pts, 0, Vector((-2, 0, 0)), pin_root=False)
check('IK unpinned: the whole chain follows', all(abs(a - 1) < 1e-6 for a in seglens(out))
      and (out[0] - Vector((-2, 0, 0))).length < 1e-9 and out[3].x < 3.0)

fresh()
mecha_lab.register()
C = bpy.context
ob = ct.new_tube(C, Vector((0, 0, 0)))
ob.mch_tube.live = False
ct.set_points(ob, [(p, 1.0) for p in pts])
ob.mch_tube.live = True
ct.rebuild(ob)
C.view_layer.objects.active = ob
bpy.ops.mch.tube_toggle(option='IK')
check('IK toggle (bar button)', ob.mch_tube.ik is True and any(b[0] == 'ik' for b in ct.TUBE_BUTTONS))
check('IK pin option, default on', ob.mch_tube.ik_pin is True)

# ---- folds
check('Fold Asymmetry + Fold Thinness inputs and HUD sliders',
      all(any(n == k for n, *_r in cw.INPUTS) for k in ('Fold Asymmetry', 'Fold Thinness'))
      and {'asym', 'thin'} <= {k[0] for k in cw.SLIDERS} and {'Fold Asymmetry', 'Fold Thinness'} <= cw.FOLD_INPUTS)
check('Fold Sharp range widened', next(r for r in cw.INPUTS if r[0] == 'Fold Sharp')[4] >= 30)
src = open(cw.__file__).read()
check('asymmetric section: steep side + crease + soft side in the fold field',
      'prof_s' in src and 'crease' in src and 'prof_g' in src)
check('fold width floor from the panel resolution (no beads)', 'min_w' in src)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
