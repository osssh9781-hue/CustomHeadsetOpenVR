"""0.19.0 Armor Plate live: Face Size 120 by default (light plates), the plate
stays live until Apply (outline + view saved), HUD sliders change height /
chamfer / bevel / face size at once, Apply bakes, Remove deletes; Plate in the
quick menu and bottom toolbar."""
import json
import math
import sys
import types

from _harness import bpy, bmesh, check, cube, fresh, non_manifold, select_only, sphere, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import armor_plate as ap, bottom_bar as bb, core_geometry as cg, cut_engine as ce, tool_state as ts

# ---- through the real stroke logic (fake viewport, top view)
TOP = cg.OrthoProjector(Quaternion())
ce.make_projector = lambda region, rv3d: TOP
ce.add_draw_handler = lambda op: 'handle'
ce.remove_draw_handler = lambda h: None
ce.open_popup = lambda name: None
ce.exit_tool = lambda context: None


class Region:
    type = 'WINDOW'
    x = y = 0
    width = height = 1000

    def tag_redraw(self):
        pass


class WM:
    def modal_handler_add(self, op):
        pass

    def event_timer_add(self, step, window=None):
        return object()

    def event_timer_remove(self, timer):
        pass


class Ctx:
    def __init__(self, native='mecha.armor_plate'):
        self.region = Region()
        self.area = types.SimpleNamespace(type='VIEW_3D', regions=[self.region], as_pointer=lambda: 2)
        self.region_data = object()
        self.space_data = types.SimpleNamespace(region_3d=self.region_data)
        self.window_manager = WM()
        self.window = types.SimpleNamespace(as_pointer=lambda: 1)
        self.mode = 'OBJECT'
        self.preferences = bpy.context.preferences
        tools = types.SimpleNamespace(from_space_view3d_mode=lambda mode, create=False:
                                      types.SimpleNamespace(idname=native))
        self.workspace = types.SimpleNamespace(tools=tools, status_text_set=lambda text: None)

    scene = property(lambda self: bpy.context.scene)
    view_layer = property(lambda self: bpy.context.view_layer)
    selected_objects = property(lambda self: bpy.context.selected_objects)
    collection = property(lambda self: bpy.context.scene.collection)

    def evaluated_depsgraph_get(self):
        return bpy.context.evaluated_depsgraph_get()


def E(type_, value='PRESS', x=500, y=500, ctrl=False):
    return types.SimpleNamespace(type=type_, value=value, mouse_x=x, mouse_y=y, alt=False,
                                 shift=False, ctrl=ctrl, oskey=False)


class Op(ce.StrokeLogic):
    def __init__(self):
        self.mode = 'PLATE'
        self.reports = []

    def report(self, kind, msg):
        self.reports.append((tuple(kind), msg))


def lasso(points, wheel=0):
    ctx, op = Ctx(), Op()
    op.invoke(ctx, E('LEFTMOUSE', 'PRESS', *points[0]))
    op.modal(ctx, E('LEFTMOUSE', 'RELEASE', *points[0]))
    for k in range(wheel):
        op.modal(ctx, E('WHEELDOWNMOUSE', 'PRESS', *points[0]))
    for x, y in points[1:]:
        op.modal(ctx, E('LEFTMOUSE', 'PRESS', x, y))
        op.modal(ctx, E('LEFTMOUSE', 'RELEASE', x, y))
    r = op.modal(ctx, E('RET'))
    return r, (op.reports[-1][1] if op.reports else '')


fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
S.mch_settings.mch_active_tool = 'PLATE'
check('Face Size defaults to 120 px', S.mch_plate.spacing == 120)
check('Armor Plate in the quick menu and the bottom toolbar',
      'PLATE' in ts.QUICK_TOOLS and any(t[0] == 'PLATE' and t[5] == 'PLATE' for t in bb.BAR_TOOLS))

box = cube('Box', 4.0)
outline = [(300, 300), (700, 300), (700, 650), (300, 650)]
S.mch_plate.preset = 'CHAMFER'
r, msg = lasso(outline)
plate = C.active_object
n120 = len(plate.mch_extract.region.polygons)
check('default plate: few clean faces', r == {'FINISHED'} and 0 < n120 <= 40 and non_manifold(plate) == 0, (n120, msg))
src = ap.plate_source(plate)
check('outline + view saved on the plate until Apply', src is not None and src['spacing'] == 120 and
      len(src['loops'][0]) == 4 and ap.pending_plate(C) is plate)
check('frozen view gives the same rays', all((ap.thaw_projector(src['proj']).ray(q)[0] - TOP.ray(q)[0]).length < 1e-6
                                             for q in outline))
reg_name = plate.mch_extract.region.name
S.mch_plate.spacing = 30
n30 = len(plate.mch_extract.region.polygons)
check('Face Size changed: the plate is rebuilt live with more faces', n30 > n120 * 2 and
      ap.plate_source(plate)['spacing'] == 30 and non_manifold(plate) == 0, (n120, n30))
check('old region mesh removed', reg_name not in bpy.data.meshes or bpy.data.meshes[reg_name] is
      plate.mch_extract.region)
zs = [(box.matrix_world @ v.co).z for v in plate.mch_extract.region.vertices]
check('rebuilt plate still on the box top', all(abs(z - 2.0) < 1e-4 for z in zs))
spec = ap.slider_spec(C, 'spacing')
spec[4](120)
check('Face Size slider rebuilds too', len(plate.mch_extract.region.polygons) == n120 and S.mch_plate.spacing == 120)
top0 = max(v.co.z for v in plate.data.vertices)
h = ap.slider_spec(C, 'height')
h[4](h[1] * 3)
top1 = max(v.co.z for v in plate.data.vertices)
check('Height slider: the plate gets taller at once', top1 > top0 + 1e-3, (top0, top1))
ch = ap.slider_spec(C, 'chamfer')
ch[4](40)
check('Chamfer slider sets the chamfer (live part)', abs(plate.mch_extract.chamfer_width - 0.04 * src['size']) < 1e-6
      and non_manifold(plate) == 0)
bv = ap.slider_spec(C, 'bevel')
bv[4](10)
check('Bevel slider sets the bevel', plate.mch_extract.bevel_width > 0)
before = S.mch_plate.preset
bpy.ops.mch.plate_cycle(step=1)
check('profile arrows step the profile of the live plate', S.mch_plate.preset != before and non_manifold(plate) == 0)
lay = ap.hud_layout([(400, 300), (600, 500)], 1600, 900)
check('HUD right of the plate: Apply, Remove, profile arrows, then 4 sliders',
      lay['apply'][0] > 600 and lay['apply'][1] > lay['cancel'][1] > lay['prev'][1] > lay['slider_height'][1] >
      lay['slider_chamfer'][1] > lay['slider_bevel'][1] > lay['slider_spacing'][1] and lay['next'][0] > lay['prev'][0])
nf = len(plate.data.polygons)
res = bpy.ops.mch.plate_apply()
check('Apply: plain mesh with the same shape, not live any more', res == {'FINISHED'} and
      ap.plate_source(plate) is None and not plate.mch_extract.is_part and len(plate.modifiers) == 0 and
      len(plate.data.polygons) >= nf and ap.pending_plate(C) is None)
S.mch_plate.spacing = 40
check('after Apply, Face Size no longer touches it', len(plate.data.polygons) >= nf)

r, msg = lasso([(350, 350), (500, 350), (500, 500), (350, 500)])
p2 = C.active_object
name2 = p2.name
res = bpy.ops.mch.plate_cancel()
check('Remove: the drawn plate is deleted, the mesh it was drawn on selected', res == {'FINISHED'} and
      name2 not in bpy.data.objects and C.active_object in (box, plate), (res, C.active_object, msg))
# 0.19.1: a live plate -> High Poly copy (for the FBX hand-off)
r, msg = lasso([(320, 320), (680, 320), (680, 620), (320, 620)])
p3 = C.active_object
n3 = len(p3.data.polygons)
select_only(p3)
bpy.ops.mch.make_highpoly()
h3 = C.active_object
check('High Poly of a plate: dense, closed, the plate itself kept', h3.get('mch_highpoly_src') == p3.name and
      len(h3.data.polygons) > n3 * 8 and non_manifold(h3) == 0 and len(p3.data.polygons) == n3,
      (n3, len(h3.data.polygons), non_manifold(h3)))
check('HUD registered', 'bl_rna' in ap.MCH_GGT_plate_hud.__dict__ and 'bl_rna' in ap.MCH_GT_plate_slider.__dict__)

# real viewport projection frozen (perspective): the same rays as the live view
class RV:
    pass
rv = RV()
from mathutils import Matrix
view = Matrix.Translation((0, 0, -10))
proj = Matrix(((1.5, 0, 0, 0), (0, 1.5, 0, 0), (0, 0, -1.002, -0.2002), (0, 0, -1, 0)))
rv.perspective_matrix = proj @ view
pr = types.SimpleNamespace(rv3d=rv, region=types.SimpleNamespace(width=1000, height=1000), is_perspective=True,
                           eye=Vector((0, 0, 10)), view_dir=Vector((0, 0, -1)))
fz = ap.FrozenProjector(ap.freeze_projector(pr))
o, d = fz.ray((500, 500))
o2, d2 = fz.ray((1000, 500))
check('frozen perspective view: centre ray straight down, edge ray tilted',
      (d - Vector((0, 0, -1))).length < 1e-6 and d2.x > 0.3 and (o - Vector((0, 0, 10))).length < 1e-6)
sp = fz.to_screen(Vector((0, 0, 0)))
check('frozen view projects back to the screen', abs(sp[0] - 500) < 1e-6 and abs(sp[1] - 500) < 1e-6)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
