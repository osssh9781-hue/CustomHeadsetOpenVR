"""0.24.84 Re-Fix: one button - DynaMesh at a picked resolution, then a clean Decimate / Quad Remesh - so a part
worked over (self-crossing sculpt, live stack, broken cuts) is a clean light solid again.  Also self_overlaps counts
real crossings only (faces that merely touch along a boolean seam are not crossings)."""
import math

from _harness import bpy, check, cube, fresh, non_manifold, summary
import bmesh
import numpy as np
from mathutils import Vector

import mecha_lab
from mecha_lab import core_geometry as cg, refix

mecha_lab.register()
fresh()
C = bpy.context
zb = C.scene.mch_zb


def select(ob):
    for o in C.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    C.view_layer.objects.active = ob


# --- self_overlaps: a cube with a boolean hole touches itself along seams, it does not cross itself ---------------
bpy.ops.mesh.primitive_cube_add(size=2.0)
body = C.active_object
bpy.ops.mesh.primitive_cylinder_add(radius=0.3, depth=5.0, location=(0.3, 0.2, 0), vertices=16)
cyl = C.active_object
m = body.modifiers.new('b', 'BOOLEAN')
m.object, m.operation, m.solver = cyl, 'DIFFERENCE', 'EXACT'
with C.temp_override(object=body, active_object=body):
    bpy.ops.object.modifier_apply(modifier='b')
bpy.data.objects.remove(cyl)
m = body.modifiers.new('bv', 'BEVEL')
m.width, m.segments = 0.05, 2
with C.temp_override(object=body, active_object=body):
    bpy.ops.object.modifier_apply(modifier='bv')
check('self_overlaps: a bevelled body with a bolt hole (seams, T-junctions, coplanar neighbours) crosses itself nowhere',
      cg.self_overlaps(body.data) == 0, cg.self_overlaps(body.data))

# a thin plate pushed through itself: noise along the normals bigger than its thickness
bpy.ops.mesh.primitive_grid_add(size=2.0, x_subdivisions=30, y_subdivisions=30)
plate = C.active_object
plate.name = 'Plate'
m = plate.modifiers.new('s', 'SOLIDIFY')
m.thickness = 0.02
with C.temp_override(object=plate, active_object=plate):
    bpy.ops.object.modifier_apply(modifier='s')
me = plate.data
co = np.empty(len(me.vertices) * 3)
me.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
co[:, 2] += 0.08 * np.sin(co[:, 0] * 9) * np.sin(co[:, 1] * 7) * (co[:, 2] > -0.001)   # only the top side moves
me.vertices.foreach_set('co', co.ravel())
me.update()
cross0 = cg.self_overlaps(me)
check('... a thin plate whose top was sculpted through its bottom crosses itself (many pairs)', cross0 > 50, cross0)

# --- Re-Fix: Decimate finish ---------------------------------------------------------------------------------------
select(plate)
zb.refix_finish, zb.refix_faces = 'DECIMATE', 0
check('auto faces: what the part has, 2,000 .. 40,000', refix.auto_faces(plate) == 2000 and refix.auto_faces(body) == 2000)
check('DynaMesh points for the result: 8 per face, 120k .. 500k (250k before a Quad Remesh)',
      refix.points_for(2000, 'DECIMATE') == 120000 and refix.points_for(40000, 'DECIMATE') == 320000
      and refix.points_for(100000, 'DECIMATE') == 500000 and refix.points_for(40000, 'QUAD') == 250000)
msg = refix.run(C, plate, zb)
check('Re-Fix (Decimate) on the crossing plate: one closed solid, no crossings left (the faces raised while a wall was '
      'thinner than the triangles: 2,000 > 4,000 / 8,000), says so',
      non_manifold(plate) == 0 and 1200 <= len(plate.data.polygons) <= 9000 and cg.self_overlaps(plate.data) == 0
      and 'self-crossings' in msg and 'open edges 0 > 0' in msg, (msg, len(plate.data.polygons), cg.self_overlaps(plate.data)))

# --- Re-Fix: Quad Remesh finish, a part with a live stack (Box Hide) -------------------------------------------------
from mecha_lab import box_hide as bh
select(body)
zb.refix_finish, zb.refix_faces = 'QUAD', 3000
_src = open(__file__.replace('test_v02507_refix.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])      # noqa: S102  (the stroke driver: Ctx, Op, E, MODE, NATIVE)
from mecha_lab import tool_state as ts
MODE[0], NATIVE[0] = 'HIDE', ts.TOOL_BY_ID['HIDE'][5]
C.scene.mch_settings.mch_active_tool = 'HIDE'
C.scene.mch_brush.shape = 'LASSO'
C.scene.mch_hide.cap = True
r, m_ = lasso([(450, 450), (560, 450), (560, 560), (450, 560)])
check('a Box Hide is live on the body before Re-Fix', r == {'FINISHED'} and bh.is_hidden(body), (r, m_))
dg = C.evaluated_depsgraph_get()
hidden_faces = len(body.evaluated_get(dg).data.polygons)
msg = refix.run(C, body, zb)
quads = sum(1 for p in body.data.polygons if len(p.vertices) == 4)
check('Re-Fix (Quad Remesh) with a live Box Hide: the hiding is applied first (said), the result is closed, mostly '
      'quads, about 3,000 faces', 'live step(s) applied first' in msg and not body.modifiers and non_manifold(body) == 0
      and quads > 0.6 * len(body.data.polygons) and 1500 <= len(body.data.polygons) <= 6000, (msg, len(body.data.polygons), quads))
# the hidden pocket stayed hidden (applied): a ray through the pocket hits lower than the top
hit, loc, *_ = body.ray_cast(Vector((0.05, 0.05, 5)), Vector((0, 0, -1)))
check('... the hidden column is gone from the mesh now (a ray through it misses the top)', not hit or loc.z < 0.9, (hit, hit and loc.z))

# --- the action / Mesh Tools entries -----------------------------------------------------------------------------
from mecha_lab import mesh_tools, zb_sculpt
check("Mesh Tools and the ZBrush action know 'REFIX' (heavy: a safety save first)",
      'REFIX' in mesh_tools.ACTIONS and 'REFIX' in mesh_tools.HEAVY and 'REFIX' in zb_sculpt.RISKY
      and "action == 'REFIX'" in open(zb_sculpt.__file__).read())
check('the shelf settings: Finish (Decimate / Quad Remesh) and Faces (0 = Auto)',
      zb.bl_rna.properties['refix_finish'].enum_items.keys() == ['DECIMATE', 'QUAD'] and zb.bl_rna.properties['refix_faces'].default == 0)
select(plate)
zb.refix_finish, zb.refix_faces = 'DECIMATE', 1500
msg = mesh_tools.run_one(C, plate, zb, 'REFIX')
r = bpy.ops.mch.mesh_tool(action='REFIX')
check('Mesh Tools > Re-Fix runs on the selected mesh (Object Mode): closed, Faces 1,500 asked (raised when a wall is thinner)',
      r == {'FINISHED'} and 'asked 1,500' in msg and non_manifold(plate) == 0, (r, msg, len(plate.data.polygons)))
summary()
