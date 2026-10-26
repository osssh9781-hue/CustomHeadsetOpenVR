"""0.24.36 Base Mesh drawn with a line that runs off the mesh (its centre over empty space): it sits on the front
surface under the line, not back at the 3D cursor depth (it looked as if it was made behind)."""
import math

from _harness import bpy, check, fresh, summary
from mathutils import Euler, Vector

import mecha_lab
from mecha_lab import base_mesh as bm_, core_geometry as cg

mecha_lab.register()
fresh()
C = bpy.context
bpy.ops.mesh.primitive_cube_add(size=2.0)                       # front face at y = -1, 3D cursor at the centre
C.scene.cursor.location = (0, 0, 0)
FRONT = cg.OrthoProjector(Euler((math.radians(90), 0, 0)).to_quaternion(), center=Vector((0, 0, 0)),
                          pixels_per_unit=200.0, size=(1000, 1000))
scr = lambda x, z: (500 + x * 200, 500 + z * 200)
# a thin band from over the cube (x = -0.5) far out to the right (x = 3): its centre (x = 1.25) is off the cube
band = [scr(-0.5, 0.05), scr(3.0, 0.05), scr(3.0, -0.05), scr(-0.5, -0.05)]
groups = cg.prepare_loops([band])
q, found = bm_.anchor_hit(C, FRONT, groups[0][0])
check('the centre misses, so the front-most surface under the line is used', found is not None
      and abs(found[0].y + 1.0) < 1e-4, found and found[0])
origin = bm_.plane_frame(C, FRONT, groups)[0]
check('facing the view (Stick to Surface off): on the front face, not at the 3D cursor depth', abs(origin.y + 1.0) < 1e-4,
      origin)
sf = bm_.surface_frame(C, FRONT, groups, 0.2)
check('Stick to Surface on: also on the front face', sf is not None and abs(sf[0].y + 1.0) < 1e-4
      and abs(sf[3].dot(Vector((0, -1, 0))) - 1.0) < 1e-4, sf and sf[0])
inside = [scr(-0.3, 0.3), scr(0.3, 0.3), scr(0.3, -0.3), scr(-0.3, -0.3)]
q2, found2 = bm_.anchor_hit(C, FRONT, cg.prepare_loops([inside])[0][0])
check('an outline over the mesh: the centre as before', found2 is not None and math.dist(q2, scr(0, 0)) < 1e-6)
far = [scr(5, 5.1), scr(6, 5.1), scr(6, 5), scr(5, 5)]
check('nothing under it at all: back to the 3D cursor depth (as before)',
      bm_.anchor_hit(C, FRONT, cg.prepare_loops([far])[0][0])[1] is None
      and abs(bm_.plane_frame(C, FRONT, cg.prepare_loops([far]))[0].y) < 1e-4)
summary()
