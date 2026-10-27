"""0.24.57 Base Mesh Line: Attach Ends - the start of the line sticks to the mesh where you began drawing, the end to
the mesh where you let go; Between: Smooth (the line smoothed, eased in and out) / As Drawn (exactly the drawn line,
rising evenly).  Live: the Between choice re-bends it."""
import inspect

from _harness import bpy, check, cube, fresh, non_manifold, summary
from mathutils import Quaternion

import mecha_lab
from mecha_lab import base_mesh as bm_, core_geometry as cg, cut_engine as ce, lasso_line

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
p = bm_.scene_defaults(C)
check('Attach Ends is off by default; Between: Smooth / As Drawn', not p.line_attach and p.attach_curve == 'SMOOTH'
      and {e.identifier for e in p.bl_rna.properties['attach_curve'].enum_items} == {'SMOOTH', 'DRAWN'})
check('Pure parts: the place along the line, the easing', abs(bm_.path_param([(0, 0), (10, 0)], (2.5, 3)) - 0.25)
      < 1e-9 and bm_.ease(0.25, 'DRAWN') == 0.25 and abs(bm_.ease(0.25, 'SMOOTH') - 0.15625) < 1e-9
      and bm_.ease(0.0, 'SMOOTH') == 0.0 and bm_.ease(1.0, 'SMOOTH') == 1.0)
a = cube('A', size=1.0, loc=(-2, 0, 0))
b = cube('B', size=1.0, loc=(2, 0, 1))
path = [(300 + 20 * i, 500) for i in range(21)]
S.mch_brush.line_mode = True
loop = lasso_line.line_loop(C, TOP, path, S.mch_brush, None)
att = (path, ce.surface_point(C, TOP, path[0]), ce.surface_point(C, TOP, path[-1]))
check('The ends: the meshes under the first and last point of the line', abs(att[1][2] - 0.5) < 1e-4
      and abs(att[2][2] - 1.5) < 1e-4)


def bottom(ob, x):
    zs = [(ob.matrix_world @ v.co).z for v in ob.data.vertices if abs((ob.matrix_world @ v.co).x - x) < 0.15]
    return min(zs) if zs else None


p.attach_curve = 'DRAWN'
msg = bm_.perform_base(C, [loop], TOP, attach=att)
ob = C.active_object
z = [bottom(ob, x) for x in (-2, -1, 0, 1, 2)]
check('As Drawn: the start on A (z 0.5), the end on B (z 1.5), rising evenly in between', 'Attach Ends: 2 of 2' in msg
      and abs(z[0] - 0.5) < 0.06 and abs(z[4] - 1.5) < 0.06 and abs((z[2] - z[0]) - (z[4] - z[2])) < 0.06
      and abs((z[3] - z[2]) - (z[2] - z[1])) < 0.02 and non_manifold(ob) == 0, (z, msg[-50:]))
ob.mch_base.attach_curve = 'SMOOTH'
zs = [bottom(ob, x) for x in (-2, -1, 0, 1, 2)]
check('Live: Between = Smooth re-bends it - the same ends, gentler near them (eased in and out)',
      abs(zs[0] - z[0]) < 0.05 and abs(zs[4] - z[4]) < 0.05 and (zs[1] - zs[0]) < (z[1] - z[0]) - 0.03, (z, zs))
ob.mch_base.height = ob.mch_base.height * 1.5
check('... and stays bent when another slider rebuilds it', abs(bottom(ob, 2) - zs[4]) < 0.03)


def worst_twist(me):
    """Largest distance of a face corner from its face plane (a twisted face shades broken)."""
    worst = 0.0
    for f in me.polygons:
        c, n = f.center, f.normal
        worst = max([worst] + [abs((me.vertices[i].co - c).dot(n)) for i in f.vertices])
    return worst


cap = [f for f in ob.data.polygons if abs(f.normal.z) > 0.5]
check('0.24.58 The top / bottom are cut into many small faces across the line, none twisted (no broken shading)',
      len(cap) >= 30 and worst_twist(ob.data) < 2e-3 and non_manifold(ob) == 0, (len(cap), worst_twist(ob.data)))
src = inspect.getsource(ce.StrokeLogic._line_attach)
check('The drawing tool: Line + Attach Ends (not Alt) passes the line and its two end points; Smooth smooths the line',
      'surface_point' in src and 'smooth_open' in src and '_line_attach(context, base_mesh)' in inspect.getsource(
          ce.StrokeLogic._execute_closed))
bpy.data.objects.remove(ob)
att2 = ([(450, 900), (500, 900), (550, 900)], None, None)
loop2 = lasso_line.line_loop(C, TOP, att2[0], S.mch_brush, None)
msg = bm_.perform_base(C, [loop2], TOP, attach=att2)
check('Nothing under the ends: made as before (flat)', 'Attach Ends: 0 of 2' in msg)
summary()
