"""0.22.2 Surface Lasso for Armor Plate / Cloth Plate: outline points on the mesh (orbit
while drawing), Enter makes the live plate from it; Line mode = a band along the surface."""
import math
import sys
import types

from _harness import bpy, check, fresh, summary, sphere
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import armor_plate as ap, cloth_wrinkle as cw, core_geometry as cg, surface_lasso as sl

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
br = S.mch_brush
br.surface_mode = True
check('Surface for Armor Plate and Cloth Plate too', sl.enabled(C, 'PLATE') and sl.enabled(C, 'WRINKLE')
      and not sl.enabled(C, 'BASE'))
ball = sphere('Ball')
ball.scale = (1.5, 1.5, 1.5)
C.view_layer.update()
FRONT = cg.OrthoProjector(Quaternion((1, 0, 0), math.radians(90)))
SIDE = cg.OrthoProjector(Quaternion((0, 0, 1), math.radians(90)) @ Quaternion((1, 0, 0), math.radians(90)))
VIEW = [FRONT]
sl.make_projector = lambda region, rv3d: VIEW[0]


class Ctx:
    def __init__(self):
        self.area = types.SimpleNamespace(type='VIEW_3D', header_text_set=lambda t: None, tag_redraw=lambda: None)
        self.region = types.SimpleNamespace(width=1000, height=1000)
        self.region_data = object()

    scene = property(lambda self: bpy.context.scene)
    view_layer = property(lambda self: bpy.context.view_layer)
    selected_objects = property(lambda self: bpy.context.selected_objects)
    collection = property(lambda self: bpy.context.scene.collection)
    preferences = property(lambda self: bpy.context.preferences)

    def evaluated_depsgraph_get(self):
        return bpy.context.evaluated_depsgraph_get()


def draw(mode, front_pts, side_pts=()):
    ctx, op = Ctx(), sl.SurfaceLogic()
    VIEW[0] = FRONT
    op.start(ctx, front_pts[0], mode)
    for xy in front_pts[1:]:
        op.click(ctx, xy)
    VIEW[0] = SIDE                         # orbit while drawing: the outline wraps round the ball
    for xy in side_pts:
        op.click(ctx, xy)
    return ctx, op


# ---- Armor Plate across the front and around to the side
ctx, op = draw('PLATE', [(440, 450), (520, 450), (520, 560)], [(440, 560), (440, 450)])
check('outline points on the surface, seen from two sides', len(op.points) == 5
      and all(abs(p.length - 1.5) < 0.05 for p in op.world_points()), [round(p.length, 3) for p in op.world_points()])
n_obj = len(bpy.data.objects)
parts, msg = op.finish(ctx)
plate = C.view_layer.objects.active
check('Enter: a live Armor Plate from the surface outline', parts is not None and plate is not None
      and plate != ball and ap.is_plate_or_part(plate) and len(bpy.data.objects) > n_obj, msg)
if plate is not None and plate != ball:
    vs = [plate.matrix_world @ v.co for v in plate.data.vertices]
    on = sum(1 for v in vs if v.length > 1.45) / max(1, len(vs))
    check('plate sits on the ball, on the drawn side (front-right)', on > 0.9 and
          sum(v.y for v in vs) / len(vs) < -0.3 and sum(v.x for v in vs) / len(vs) > 0.1,
          (round(on, 2), round(sum(v.x for v in vs) / len(vs), 2), round(sum(v.y for v in vs) / len(vs), 2)))
    check('plate keeps its outline for live edits (HUD sliders)', ap.plate_source(plate) is not None)

# ---- Cloth Plate
ctx, op = draw('WRINKLE', [(430, 430), (570, 430), (570, 570), (430, 570)])
parts, msg = op.finish(ctx)
cloth = C.view_layer.objects.active
check('Enter: a live Cloth Plate from the surface outline', parts is not None and cw.is_wrinkle(cloth), msg)

# ---- Line mode: a band along the surface
br.line_mode = True
br.line_width = 0.2
ctx, op = draw('PLATE', [(420, 500), (500, 520), (580, 500)])
parts, msg = op.finish(ctx)
band = C.view_layer.objects.active
check('Line + Surface: an Armor Plate strip along the surface', parts is not None and ap.is_plate_or_part(band),
      msg)
if parts is not None:
    d = sorted(band.dimensions)
    check('strip about Line Width wide', d[1] < 0.45 and d[2] > 0.9, tuple(round(x, 3) for x in band.dimensions))
br.line_mode = False

# ---- too few points
ctx, op = draw('PLATE', [(450, 450), (550, 450)])
parts, msg = op.finish(ctx)
check('2 points (no Line): asks for 3', parts is None and '3 points' in msg)
check('view along the drawn area: centred, fits', all(0 < c < 1000 for p in op.world_points()
                                                       for c in op.surface_view(op.world_points(),
                                                                                [Vector((0, -1, 0))]).to_screen(p)))
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
