"""0.24.33 Surface Draw / Cloth Brush: a band (or cloth strip) along a line drawn on a mesh; every stroke keeps the
first width and height; crossing strokes do not pile up; strokes join into one live object."""
import math

from _harness import bpy, check, fresh, summary
import bmesh
from mathutils import Euler, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, surface_draw as sd, tool_state as ts, ui_tool_settings as uts

mecha_lab.register()
fresh()
C = bpy.context
check('tools in the list with settings', {'SDRAW', 'CLOTHB'} <= {t[0] for t in ts.VISIBLE_TOOLS}
      and {'SDRAW', 'CLOTHB'} <= set(uts.DRAWERS) and {'SDRAW', 'CLOTHB'} <= ts.SHAPE_TOOLS)
h = sd.cross_heights('BEVEL', 9, 0.3)
check('Bevel (round edge) profile: 0 at the edges, 1 in the middle', h[0] == 0.0 and h[-1] == 0.0 and h[4] == 1.0 and h[3] == 1.0)
check('Ridge / Round / Bevel profiles', sd.cross_heights('RIDGE', 5)[2] == 1.0 and sd.cross_heights('RIDGE', 5)[1] == 0.5
      and abs(sd.cross_heights('ROUND', 3)[1] - 1.0) < 1e-9 and sd.cross_heights('CHAMFER', 5, 0.5)[1] == 1.0
      and sd.cross_heights('CHAMFER', 5, 0.5)[0] == 0.0)
check('Square (default): straight sides - full height right to the edge', sd.cross_heights('SQUARE', 7) == [1.0] * 7
      and sd.MCH_PG_SurfaceDraw.bl_rna.properties['profile'].default == 'SQUARE')
check('fill edge: Square full at the outline, Chamfer / Bevel rise from 0', sd.edge_height('SQUARE', 0.0, 1, 5) == 1.0
      and sd.edge_height('CHAMFER', 0.5, 1, 5) == 0.5 and sd.edge_height('BEVEL', 0.0, 1, 5) == 0.0
      and 0.5 < sd.edge_height('BEVEL', 0.5, 1, 5) < 1.0 and sd.edge_height('BEVEL', 2.0, 1, 5) == 1.0)
e = sd.end_factors([0, 1, 2, 3, 4, 5, 6], 2.0)
check('round ends: 0 at both ends, full in the middle', e[0] == 0 and e[-1] == 0 and e[3] == 1.0 and 0 < e[1] < 1)

bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=1.0)
body = C.active_object
body.name = 'Body'
proj = cg.OrthoProjector(Euler((math.radians(90), 0, 0)).to_quaternion(), center=Vector((0, 0, 0)),
                         pixels_per_unit=200.0, size=(1000, 1000))
scr = lambda x, z: (500 + x * 200, 500 + z * 200)
st = C.scene.mch_sdraw
st.width, st.height = 0.0, 0.0
C.scene.mch_brush.line_width = 0.1
line1 = [scr(-0.5 + 0.05 * i, 0.0) for i in range(21)]
msg = sd.perform(C, line1, proj, 'BAND')
ob = C.active_object
check('first stroke: a live band on the body, width from the Line Width', sd.source(ob) is not None
      and ob.mch_sdraw.live and abs(st.width - 0.1) < 1e-6 and abs(st.height - 0.1 / 3) < 1e-6, (msg, st.width))


def closed(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    ok = len(bm.faces) > 0 and all(e.is_manifold for e in bm.edges)
    bm.free()
    return ok


def radii(o):
    return [(o.matrix_world @ v.co).length for v in o.data.vertices]


r = radii(ob)
check('the band is a closed solid', closed(ob.data))
check('it stands Height above the surface (no more)', abs(max(r) - (1 + st.height)) < st.height * 0.15, max(r))
line2 = [scr(0.0, -0.5 + 0.05 * i) for i in range(21)]
sd.perform(C, line2, proj, 'BAND')
ob2 = C.active_object
r2 = radii(ob2)
check('a second stroke joins the same object', ob2 == ob and len(sd.source(ob)['strokes']) == 2)
check('crossing the first band: still the same height (does not pile up)', max(r2) < 1 + st.height * 1.15, max(r2))
check('Keep First Size: the width and height stayed', abs(st.width - 0.1) < 1e-6 and abs(ob.mch_sdraw.width - 0.1) < 1e-6)
ob.mch_sdraw.profile = 'ROUND'
check('live: the shape changes all strokes', closed(ob.data) and len(sd.source(ob)['strokes']) == 2)
ob.mch_sdraw.height = 0.08
check('live: height', abs(max(radii(ob)) - 1.08) < 0.015, max(radii(ob)))
C.view_layer.objects.active = ob
bpy.ops.mch.sdraw_pop()
check('Remove Last Stroke', len(sd.source(ob)['strokes']) == 1)

# Fill Area: a closed lasso filled at the same height (Square / Chamfer / Bevel edges)
st.fill = True
sq = [scr(-0.25, -0.75), scr(0.25, -0.75), scr(0.25, -0.35), scr(-0.25, -0.35)]
msg = sd.perform_fill(C, [sq], proj, 'BAND')
fo = C.active_object
src = sd.source(fo)
check('Fill Area: the area joins the same live object', fo == ob and len(src.get('fills', [])) == 1, msg)
check('the filled area is a closed solid with everything else', closed(fo.data))
fo.mch_sdraw.profile = 'SQUARE'
fill = src['fills'][0]
top_square = max((Vector(c) + Vector(n) * fo.mch_sdraw.height).length for c, n in zip(fill['cos'], fill['nrms']))
check('Square fill: as high as the strokes (Height), straight walls at the outline', closed(fo.data)
      and abs(max(radii(fo)) - (1 + fo.mch_sdraw.height)) < fo.mch_sdraw.height * 0.2, max(radii(fo)))
fo.mch_sdraw.profile = 'CHAMFER'
check('Chamfer fill rebuilds (closed)', closed(fo.data))
C.view_layer.objects.active = fo
bpy.ops.mch.sdraw_pop()
check('Remove Last Stroke takes the fill (the last thing) away', len(sd.source(fo).get('fills', [])) == 0
      and len(sd.source(fo)['strokes']) == 1)
from mecha_lab import cut_engine as ce
class Fake:
    mode, shape = 'SDRAW', 'LASSO'
check('cut engine: with Fill Area a lasso is an area, without it a line', ce.MCH_OT_cut_stroke._fill_area(Fake()) is True)
st.fill = False
check('... and off again', ce.MCH_OT_cut_stroke._fill_area(Fake()) is False)

cl = C.scene.mch_clothb
cl.width, cl.height = 0.0, 0.0
sd.perform(C, [scr(-0.4 + 0.04 * i, 0.4) for i in range(21)], proj, 'CLOTH')
co = C.active_object
check('Cloth Brush: its own live object (kind Cloth)', co != ob and co.mch_sdraw.kind == 'CLOTH' and closed(co.data))
rc = radii(co)
check('the cloth lies on the surface, puffed a little (thin)', min(rc) > 0.995 and max(rc) < 1 + cl.height * 3.0,
      (min(rc), max(rc)))
n1 = len(co.data.vertices)
sd.perform(C, [scr(-0.4 + 0.04 * i, 0.55) for i in range(21)], proj, 'CLOTH')
check('a second cloth stroke: same object, same size', C.active_object == co and len(co.data.vertices) > n1
      and abs(cl.width - 0.1) < 1e-6)
co.mch_sdraw.folds = 3.0
check('live: folds', closed(co.data))
C.view_layer.objects.active = co
bpy.ops.mch.sdraw_apply()
check('Apply: plain mesh', sd.source(co) is None and not co.mch_sdraw.live)
try:
    sd.perform(C, [scr(3, 3), scr(3.2, 3)], proj, 'BAND')
    ok = False
except cg.CutError:
    ok = True
check('a line off the mesh: tells, makes nothing', ok)
summary()
