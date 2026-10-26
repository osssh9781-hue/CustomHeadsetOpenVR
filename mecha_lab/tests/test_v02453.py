"""0.24.37 Base Mesh Invert: the height grows back, away from you, from where you draw (instead of toward you);
with Stick to Surface too; off = as before."""
import math

from _harness import bpy, check, fresh, summary
from mathutils import Euler, Vector

import mecha_lab
from mecha_lab import base_mesh as bm_, core_geometry as cg

mecha_lab.register()
fresh()
C = bpy.context
FRONT = cg.OrthoProjector(Euler((math.radians(90), 0, 0)).to_quaternion(), center=Vector((0, 0, 0)),
                          pixels_per_unit=200.0, size=(1000, 1000))          # looking +Y, the viewer at -Y
scr = lambda x, z: (500 + x * 200, 500 + z * 200)
SQ = [[scr(-0.3, -0.3), scr(0.3, -0.3), scr(0.3, 0.3), scr(-0.3, 0.3)]]
p = bm_.scene_defaults(C)
p.sketch = False
p.height = 0.5
check('Invert is a Base Mesh option, off by default', hasattr(p, 'invert_height') and not p.invert_height)


def made(invert, stick):
    p.invert_height, p.surface_align = invert, stick
    bm_.perform_base(C, SQ, FRONT)
    ob = C.active_object
    ys = [(ob.matrix_world @ v.co).y for v in ob.data.vertices]
    LAST[0] = ob
    return min(ys), max(ys)


LAST = [None]


def drop():
    bpy.data.objects.remove(LAST[0])


bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 1.0, 0))             # front face at y = 0
cube = C.active_object
lo, hi = made(False, True)
check('normal, on the surface: grows toward you (from y = 0 to -0.5)', abs(lo + 0.5) < 0.02 and hi > -0.02 and hi < 0.03,
      (lo, hi))
drop()
lo, hi = made(True, True)
check('Invert, on the surface: grows back into the mesh (from y = 0 to +0.5)', abs(hi - 0.5) < 0.02 and lo > -0.03,
      (lo, hi))
drop()
bpy.data.objects.remove(cube)
C.scene.cursor.location = (0, 0, 0)
lo, hi = made(False, False)
check('normal, nothing under it: from the 3D cursor depth toward you', abs(lo + 0.5) < 0.02 and abs(hi) < 0.02, (lo, hi))
drop()
lo, hi = made(True, False)
check('Invert, nothing under it: from the 3D cursor depth back', abs(hi - 0.5) < 0.02 and abs(lo) < 0.02, (lo, hi))
ob = C.active_object
xs = sorted({round((ob.matrix_world @ v.co).x, 3) for v in ob.data.vertices})
zs = sorted({round((ob.matrix_world @ v.co).z, 3) for v in ob.data.vertices})
check('the outline stays where it was drawn (not mirrored)', abs(xs[0] + 0.3) < 0.02 and abs(xs[-1] - 0.3) < 0.02
      and abs(zs[0] + 0.3) < 0.02 and abs(zs[-1] - 0.3) < 0.02)
from _harness import non_manifold
check('a closed solid, faces pointing out', non_manifold(ob) == 0 and ob.data.polygons[0] is not None)
p.invert_height = False
summary()
