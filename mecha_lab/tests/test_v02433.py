"""0.24.32 Quad Cloth: Edit Mode quads of a retopo -> Cloth (simulated, pinned, body as collider), Rib Knit (snug,
ridged), Padding (a pillow per quad, seams stay); source faces only hidden, the body left as it was."""
import math

from _harness import bpy, check, fresh, summary
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import mecha_lab
from mecha_lab import quad_cloth as qc

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene

check('rib wave: ridge 1, groove 0', abs(qc.rib_wave(0) - 1) < 1e-9 and abs(qc.rib_wave(0.5)) < 1e-9)
check('pillow: 0 on the seam, 1 in the middle', qc.pillow_weight(0, 2) == 0.0 and abs(qc.pillow_weight(2, 2) - 1) < 1e-9)

# body: a capsule-ish column; retopo: a quad tube round it (a "shirt")
bpy.ops.mesh.primitive_cylinder_add(radius=0.3, depth=1.6, vertices=32, location=(0, 0, 0.8))
body = C.active_object
body.name = 'Body'
bpy.ops.mesh.primitive_cylinder_add(radius=0.34, depth=0.9, vertices=32, end_fill_type='NOTHING', location=(0, 0, 1.0))
retopo = C.active_object
retopo.name = 'Retopo'
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.subdivide(number_cuts=8)
bpy.ops.object.mode_set(mode='OBJECT')
nq = len(retopo.data.polygons)


def select(pred):
    for o in C.selected_objects:
        o.select_set(False)
    retopo.select_set(True)
    C.view_layer.objects.active = retopo
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(retopo.data)
    n = 0
    for f in bm.faces:
        s = (not f.hide) and pred(retopo.matrix_world @ f.calc_center_median())
        f.select_set(s)
        n += s
    bmesh.update_edit_mesh(retopo.data)
    return n


bvh = BVHTree.FromObject(body, C.evaluated_depsgraph_get())
st = S.mch_quad_cloth
st.body = body
# nothing selected -> clear message
select(lambda c: False)
try:
    qc.perform(C, 'CLOTH')
    check('nothing selected: a clear message', False)
except qc.QuadClothError as ex:
    check('nothing selected: a clear message', 'Select' in str(ex), str(ex))
# rib: the top band
n_rib = select(lambda c: c.z > 1.38)
before = {p.index for p in retopo.data.polygons}
ob, msg = qc.perform(C, 'RIB')
check('Rib: new object, quads kept, source faces hidden', ob.name.endswith('_Rib') and 'quads' in msg
      and sum(p.hide for p in retopo.data.polygons) == n_rib, msg)
d = [bvh.find_nearest(body.matrix_world.inverted() @ (ob.matrix_world @ v.co))[3] for v in ob.data.vertices]
check('Rib: snug on the body (close) with ridges (distance varies)', max(d) < 0.05 and max(d) - min(d) > 0.002,
      (min(d), max(d)))
check('Rib: thickness is a Solidify modifier', any(m.type == 'SOLIDIFY' for m in ob.modifiers))
# padding: the middle
n_pad = select(lambda c: 0.75 < c.z <= 1.38)
ob, msg = qc.perform(C, 'PADDING')
check('Padding: each quad split (more verts)', len(ob.data.vertices) > n_pad * 4, (len(ob.data.vertices), n_pad))
d = [bvh.find_nearest(body.matrix_world.inverted() @ (ob.matrix_world @ v.co))[3] for v in ob.data.vertices]
check('Padding: pillows stand out from the seams', max(d) - min(d) > 0.01, (min(d), max(d)))
# cloth: the rest, pinned where it joins the padding (seam)
n_cl = select(lambda c: c.z <= 0.75)
st.frames = 25
z0 = min((retopo.matrix_world @ v.co).z for v in retopo.data.vertices)
ob, msg = qc.perform(C, 'CLOTH')
check('Cloth: simulated and pinned at the join', 'pinned' in msg and ob.name.endswith('_Cloth'), msg)
zs = [(ob.matrix_world @ v.co).z for v in ob.data.vertices]
check('Cloth: it fell / got longer (gravity + extra length)', min(zs) < z0 - 0.005, (min(zs), z0))
inside = sum(1 for v in ob.data.vertices
             if Vector(((ob.matrix_world @ v.co).x, (ob.matrix_world @ v.co).y)).length < 0.29
             and 0.0 < (ob.matrix_world @ v.co).z < 1.6)
check('Cloth: stays out of the body', inside == 0, inside)
check('Cloth: no cloth / pin left on it, the body unchanged', not any(m.type == 'CLOTH' for m in ob.modifiers)
      and not ob.vertex_groups and not body.modifiers)
check('the source mesh keeps all its faces (only hidden)', len(retopo.data.polygons) == nq
      and all(p.hide for p in retopo.data.polygons))
check('Quad Cloth in Edit Mode panel + face menus', hasattr(bpy.types, 'MCH_PT_quad_cloth')
      and bpy.ops.mch.quad_cloth is not None)
summary()
