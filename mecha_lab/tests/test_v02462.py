"""0.24.42 Armor Plate Alt + draw: the plate it would make, turned the other way (mirrored through the surface into
the mesh) and carved out with a Boolean - a recess as deep as the plate is tall, its profile as the walls; no
plate object is left."""
import math

from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Quaternion, Vector
from mathutils.bvhtree import BVHTree

import mecha_lab
from mecha_lab import armor_plate as ap, core_geometry as cg, cut_engine as ce

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
plane = BVHTree.FromPolygons([Vector((-5, -5, 0)), Vector((5, -5, 0)), Vector((5, 5, 0)), Vector((-5, 5, 0))],
                             [(0, 1, 2, 3)])
pts = ap.mirrored_into([Vector((0, 0, 0.3)), Vector((1, 0, -0.001)), Vector((0, 1, 0.0))], plane, 0.01)
check('mirror through the surface: 0.3 above -> 0.3 below; on / just under the surface -> a hair above',
      abs(pts[0].z + 0.3) < 1e-6 and abs(pts[1].z - 0.011) < 1e-6 and abs(pts[2].z - 0.01) < 1e-6,
      [tuple(p) for p in pts])

LOOP = [(500 + 55 * math.cos(a), 500 + 45 * math.sin(a)) for a in (2 * math.pi * k / 48 for k in range(48))]
bpy.ops.mesh.primitive_cube_add(size=2.0)
ref = C.active_object
ap.perform_plate(C, [LOOP], TOP)
part = C.active_object
C.view_layer.update()
height = max((part.matrix_world @ v.co).z for v in part.data.vertices) - 1.0
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=2.0)
cube = C.active_object
n0 = len(bpy.data.objects)
msg = ap.perform_plate_carve(C, [LOOP], TOP)
C.view_layer.update()
hit, loc, _n, _i, ob, _m = S.ray_cast(C.evaluated_depsgraph_get(), Vector((0, 0, 5)), Vector((0, 0, -1)))
check('Alt: carved into the cube, closed, no plate object left', 'carved' in msg and non_manifold(cube) == 0
      and len(bpy.data.objects) == n0 and ob == cube, (msg, non_manifold(cube), len(bpy.data.objects)))
check('... the recess is as deep as the plate would be tall', height > 0.01 and abs((1.0 - loc.z) - height) < height * 0.2,
      (height, 1.0 - loc.z))
far = S.ray_cast(C.evaluated_depsgraph_get(), Vector((0.85, 0.85, 5)), Vector((0, 0, -1)))[1]
check('... outside the drawn shape the top is untouched', abs(far.z - 1.0) < 1e-5, far.z)
src = open(ce.__file__).read()
check('the Armor Plate tool sends Alt + draw here (and a plain draw still makes a plate)',
      "self.mode == 'PLATE' and self.inverted()" in src and 'perform_plate_carve' in src)
summary()
