"""0.22.1 Surface Lasso (points on the mesh, orbit while drawing, split along the loop
with a gap), Q = Select <-> last tool / Shift+Q = pie, humanoid torso / head removed."""
import math
import sys
import types

from _harness import bpy, check, cube, cylinder, fresh, non_manifold, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, surface_lasso as sl, robot_base as rb

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
br = S.mch_brush
check('Surface toggle + gap props, off by default', hasattr(br, 'surface_mode') and br.surface_mode is False
      and br.surface_gap > 0)
check('Surface for Cut / Split (+ plates since 0.22.2)', {'CUT', 'SPLIT'} <= sl.MODES and 'BASE' not in sl.MODES)
br.surface_mode = True
check('enabled for Cut and Split, not Base Mesh', sl.enabled(C, 'CUT') and sl.enabled(C, 'SPLIT')
      and not sl.enabled(C, 'BASE'))
br.surface_mode = False

arm = cylinder('Arm', segments=32, radius=0.5, depth=4.0)
FRONT = cg.OrthoProjector(Quaternion((1, 0, 0), math.radians(90)))
BACK = cg.OrthoProjector(Quaternion((0, 0, 1), math.radians(180)) @ Quaternion((1, 0, 0), math.radians(90)))
VIEW = [FRONT]
sl.make_projector = lambda region, rv3d: VIEW[0]


class Ctx:
    def __init__(self):
        self.area = types.SimpleNamespace(type='VIEW_3D', header_text_set=lambda t: None, tag_redraw=lambda: None)
        self.region = types.SimpleNamespace(width=1000, height=1000)
        self.region_data = object()

    scene = property(lambda self: bpy.context.scene)
    view_layer = property(lambda self: bpy.context.view_layer)

    def evaluated_depsgraph_get(self):
        return bpy.context.evaluated_depsgraph_get()


class Op(sl.SurfaceLogic):
    pass


ctx, op = Ctx(), Op()
ok = op.start(ctx, (470, 500), 'SPLIT')
check('first click sticks to the mesh', ok and op.target is not None and op.target.name == 'Arm')
op.click(ctx, (530, 500))
w_before = [tuple(round(c, 5) for c in p) for p in op.world_points()]
VIEW[0] = BACK                                   # orbit to the back while drawing
w_after = [tuple(round(c, 5) for c in p) for p in op.world_points()]
check('points stay on the mesh when the view turns (stored in 3D)', w_before == w_after and len(w_after) == 2)
check('front points are on the front surface', all(p[1] < -0.3 for p in w_after), w_after)
op.click(ctx, (470, 500))
op.click(ctx, (530, 500))
pts = op.world_points()
check('back points on the back surface', len(pts) == 4 and pts[2][1] > 0.3 and pts[3][1] > 0.3, pts)
lines = op.world_lines()
on_surface = all(abs(math.hypot(p.x, p.y) - 0.5) < 0.03 for ln in lines for p in ln)
check('lines follow the surface (around the side, not through)', on_surface and len(lines) == 3)
op.move(ctx, (520, 520))
check('hover segment to the mouse', len(op.world_lines()) == 4)
# drag a point along the surface
VIEW[0] = FRONT
r = op.click(ctx, (530, 500))
op.move(ctx, (530, 540))
op.release()
check('drag a point: it moves along the surface', r == 'DRAG' and op.world_points()[1].z > 0.3,
      tuple(op.world_points()[1]))
op.drag = None
op.points[1] = op.target.ray(*FRONT.ray((530, 500)))
op._rebuild()
op.undo_point()
check('Backspace removes the last point', len(op.points) == 3)
VIEW[0] = BACK
op.click(ctx, (530, 500))          # back-left again -> 4 points around
n_pts = len(op.points)
parts, msg = op.finish(ctx)
check('Enter: closes and splits the arm into 2 parts', parts is not None and len(parts) == 2, (msg, n_pts))
if parts and len(parts) == 2:
    zmax = [max((o.matrix_world @ v.co).z for v in o.data.vertices) for o in parts]
    zmin = [min((o.matrix_world @ v.co).z for v in o.data.vertices) for o in parts]
    top, bot = (0, 1) if zmin[0] > zmin[1] else (1, 0)
    check('cut near the loop height, with a gap', abs(zmin[top] - zmax[bot]) > 0.0003 and abs(zmin[top]) < 0.6,
          (zmin[top], zmax[bot]))
    check('both parts closed (printable)', all(non_manifold(o) == 0 for o in parts),
          [non_manifold(o) for o in parts])
    check('original object kept as the bigger part', parts[0].name == 'Arm')

# a loop that does not go around: nothing changes
box = cube('Box', 2.0, loc=(5, 0, 0))
TOP = cg.OrthoProjector(Quaternion(), center=Vector((5, 0, 0)))
VIEW[0] = TOP
ctx, op = Ctx(), Op()
op.start(ctx, (450, 450), 'SPLIT')
for xy in ((550, 450), (550, 550), (450, 550)):
    op.click(ctx, xy)
nv = len(box.data.vertices)
parts, msg = op.finish(ctx)
check('loop only on the top face: reported, mesh unchanged', len(parts) == 1 and 'around' in msg
      and len(box.data.vertices) == nv, msg)
check('less than 3 points: not finished', Op().finish if True else None)
ctx, op = Ctx(), Op()
op.start(ctx, (480, 480), 'SPLIT')
parts, msg = op.finish(ctx)
check('2 points -> asks for more', parts is None and '3 points' in msg)
check('click in empty space starts nothing', Op().start(ctx, (5, 5), 'SPLIT') is False)

# Q / Shift+Q
wm = C.window_manager
items = [(i.idname, i.type, i.shift) for kc in (wm.keyconfigs.addon,) if kc for km in kc.keymaps
         for i in km.keymap_items if i.idname in {'mch.tool_pie', 'mch.toggle_last_tool'}]
check('Q = Select <-> last tool, Shift+Q = pie', ('mch.toggle_last_tool', 'Q', False) in items
      and ('mch.tool_pie', 'Q', True) in items, items)
# humanoid torso / head gone from the generator UI
check('humanoid parts: no torso / head', not {'TORSO', 'CHEST', 'PELVIS', 'HEAD'} & set(rb.UI_PARTS['HUMANOID']))
check('operator registered', hasattr(bpy.ops.mch, 'surface_lasso'))
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
