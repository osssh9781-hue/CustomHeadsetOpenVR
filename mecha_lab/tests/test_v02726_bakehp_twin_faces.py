"""0.24.325 (user's GUNGUN.blend: Bake High Poly closed Blender): a face doubled back to back (two faces on the same
points) crashed BMesh's grid-fill subdivision - the twin goes first; the high is made."""
import bmesh
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import bake_highpoly as bk

fresh()
mecha_lab.register()
C = bpy.context

bpy.ops.mesh.primitive_cube_add(size=2.0)
ob = C.active_object
bm = bmesh.new()
bm.from_mesh(ob.data)
bm.faces.ensure_lookup_table()
f = bm.faces[0]
bm.faces.new(list(reversed(f.verts)))                  # (its twin, back to back - as in the user's part)
bm.to_mesh(ob.data)
bm.free()
check('setup: a cube with one face doubled (7 faces)', len(ob.data.polygons) == 7)
b2 = bmesh.new()
b2.from_mesh(ob.data)
n = bk.drop_twin_faces(b2)
check('drop_twin_faces: the twin goes (one left)', n == 1 and len(b2.faces) == 6)
b2.free()
hp, info = bk.build(C, ob, target_faces=20000)
check(f'Bake High Poly on it: made, no crash ({len(hp.data.polygons)} faces)', hp is not None and
      len(hp.data.polygons) > 1000)
check('... the part itself untouched (still its 7 faces)', len(ob.data.polygons) == 7)
summary()
