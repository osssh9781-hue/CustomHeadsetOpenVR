"""0.24.36 Cut Depth for line cuts: with From Surface a 2-point line (and a polyline) only cuts Cut Depth deep;
Through All still cuts all the way (the fast plane cut)."""
from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Quaternion

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion())                    # looking down -Z
S.mch_settings.auto_apply = True


def cube():
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    return C.active_object


def right_side(t, x0=0.05):
    """highest z of what is left on the removed side (x > x0), and the lowest"""
    zs = [(t.matrix_world @ v.co).z for v in t.data.vertices if (t.matrix_world @ v.co).x > x0]
    return (max(zs), min(zs)) if zs else (None, None)


cut = S.mch_cut
cut.depth_mode = 'THROUGH'
t = cube()
msg = ce.perform_line(C, 'CUT', [t], [(500, 300), (500, 700)], TOP, side_xy=(700, 500))
check('Through All, 2 points: the fast plane cut, all the way through', right_side(t) == (None, None)
      and 'Plane cut' in msg, (msg, right_side(t)))

cut.depth_mode = 'SURFACE'
cut.depth = 0.5
t = cube()
msg = ce.perform_line(C, 'CUT', [t], [(500, 300), (500, 700)], TOP, side_xy=(700, 500))
hi, lo = right_side(t)
check('From Surface, 2 points: only Cut Depth deep (a step, the bottom stays)', hi is not None
      and abs(hi - 0.5) < 1e-4 and abs(lo + 1.0) < 1e-4 and non_manifold(t) == 0, (msg, hi, lo))

t = cube()
cut.depth = 1.2
ce.perform_line(C, 'CUT', [t], [(500, 300), (520, 500), (500, 700)], TOP, side_xy=(700, 500))
hi, lo = right_side(t, 0.3)
check('From Surface, a polyline: Cut Depth too', hi is not None and abs(hi - (1.0 - 1.2)) < 1e-3, (hi, lo))
cut.depth_mode = 'THROUGH'
summary()
