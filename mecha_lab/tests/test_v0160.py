"""0.16.0 Armor Plate: lasso on a mesh -> separate plate made of NEW clean faces
(no retopology), Face Extract profile engine, wheel = profile."""
import math
import sys
import types

from _harness import bpy, bmesh, check, cube, fresh, non_manifold, select_only, sphere, summary, volume
from mathutils import Quaternion, Vector
from mathutils.bvhtree import BVHTree

import mecha_lab
from mecha_lab import armor_plate as ap, core_geometry as cg, cut_engine as ce, tool_state as ts

# ---- 2D patch
sq = [(100, 100), (300, 100), (300, 250), (100, 250)]
r = ap.resample_loop(sq, 10)
check('outline resampled every few px, the drawn corners kept', all(c in r for c in sq) and len(r) > 60)
pts, tris, nb = ap.screen_patch(cg.prepare_loops([sq]), 14)
check('patch: boundary first, then an even inner grid', nb == len(ap.resample_loop(sq, 7)) and len(pts) > nb + 50)
check('all triangles counter-clockwise, none degenerate',
      all((pts[b][0] - pts[a][0]) * (pts[c][1] - pts[a][1]) - (pts[b][1] - pts[a][1]) * (pts[c][0] - pts[a][0]) > 0
          for a, b, c in tris))
area = sum(abs((pts[b][0] - pts[a][0]) * (pts[c][1] - pts[a][1]) - (pts[b][1] - pts[a][1]) * (pts[c][0] - pts[a][0]))
           / 2 for a, b, c in tris)
check('triangles cover exactly the drawn area', abs(area - 200 * 150) < 1.0, area)
hole = [(170, 150), (170, 200), (230, 200), (230, 150)]
pts2, tris2, _ = ap.screen_patch(cg.prepare_loops([sq, hole]), 14)
area2 = sum(abs((pts2[b][0] - pts2[a][0]) * (pts2[c][1] - pts2[a][1]) - (pts2[b][1] - pts2[a][1]) *
                (pts2[c][0] - pts2[a][0])) / 2 for a, b, c in tris2)
check('a hole in the outline stays open', abs(area2 - (30000 - 60 * 50)) < 1.0, area2)
big = [(0, 0), (4000, 0), (4000, 4000), (0, 4000)]
pb, tb, _ = ap.screen_patch(cg.prepare_loops([big]), 4)
check('huge outline: face size grows to keep the plate light', len(pb) < ap.MAX_POINTS * 1.3, len(pb))
v = ap.preset_values('CHAMFER', 2.0)
check('profiles scale with the plate (Auto Size)', abs(v['extract_height'] - 0.08) < 1e-9 and
      abs(v['chamfer_angle'] - math.radians(45)) < 1e-9 and v['bevel_width'] == 0.0)
check('manual size keeps the user values', 'extract_height' not in ap.preset_values('CHAMFER', 2.0, auto=False))
check('a dozen profiles', len(ap.PRESETS) >= 12)

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
check('Armor Plate is a tool of its own', ts.TOOL_BY_ID['PLATE'][5] == 'mecha.armor_plate' and
      ts.NATIVE_TO_TOOL['mecha.armor_plate'] == 'PLATE')

# low-poly box: 6 faces only - the plate must still follow the drawn outline exactly
box = cube('Box', 4.0)
nv = len(box.data.vertices)
outline = [(380, 400), (600, 380), (640, 520), (520, 640), (400, 600)]
S.mch_plate.preset = 'CHAMFER'
r, msg = lasso(outline)
plate = C.active_object
check('lasso on a 6-face box: a separate plate object', r == {'FINISHED'} and plate is not box and
      plate.mch_extract.is_part and 'Armor plate' in msg, msg)
check('the box is not changed', len(box.data.vertices) == nv and len(bpy.data.objects['Box'].data.polygons) == 6)
reg = plate.mch_extract.region
check('the plate is made of NEW faces (many, mostly quads), not the box faces',
      len(reg.polygons) > 30 and sum(1 for p in reg.polygons if len(p.vertices) == 4) > len(reg.polygons) * 0.5,
      len(reg.polygons))
bm = bmesh.new()
bm.from_mesh(reg)
edge_pts = [box.matrix_world @ e.verts[0].co for e in bm.edges if e.is_boundary]
bm.free()
segs = [(outline[i], outline[(i + 1) % len(outline)]) for i in range(len(outline))]
off = max(min(ap._seg_dist(TOP.to_screen(p), a, b) for a, b in segs) for p in edge_pts)
check('plate edge = the drawn line (within 0.1 px)', off < 0.1, off)
zs = [(box.matrix_world @ v.co).z for v in reg.vertices]
check('plate lies on the box top', all(abs(z - 2.0) < 1e-4 for z in zs), (min(zs), max(zs)))
check('plate solid is closed and stands up from the surface',
      non_manifold(plate) == 0 and max(v.co.z for v in plate.data.vertices) > 2.0 + 1e-3)
check('chamfer profile scaled to the plate', 0.0 < plate.mch_extract.chamfer_width < 0.2)

# second plate over the first one: it goes on the box, not on the plate
r2, msg2 = lasso([(420, 420), (560, 420), (560, 560), (420, 560)])
check('drawing over a plate puts the new plate on the mesh below', r2 == {'FINISHED'} and 'on Box' in msg2, msg2)

# wheel while drawing = next profile
S.mch_plate.preset = 'FLAT'
r3, msg3 = lasso([(430, 430), (520, 430), (520, 520), (430, 520)], wheel=2)
check('mouse wheel while drawing steps through the profiles', S.mch_plate.preset == ap.PRESET_IDS[2] and
      ap.PRESETS[2][1] in msg3, (S.mch_plate.preset, msg3))

# curved surface (sphere): new faces sit on it
fresh()
mecha_lab.register()
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_settings.mch_active_tool = 'PLATE'
ball = sphere('Ball')
ball.scale = (3, 3, 3)
C.view_layer.update()
r, msg = lasso([(420, 420), (580, 420), (580, 580), (420, 580)])
plate = C.active_object
dg = C.evaluated_depsgraph_get()
me = ball.evaluated_get(dg).to_mesh()
bvh = BVHTree.FromPolygons([ball.matrix_world @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
ball.evaluated_get(dg).to_mesh_clear()
d = max(bvh.find_nearest(plate.matrix_world @ v.co)[3] for v in plate.mch_extract.region.vertices)
check('on a round surface the new faces lie on it', r == {'FINISHED'} and d < 1e-3 and non_manifold(plate) == 0, d)
bpy.ops.mch.plate_preset(preset='ROUND')
check('profile button changes the selected plate live', plate.mch_extract.bevel_width > 0 and
      non_manifold(plate) == 0)
r, msg = lasso([(60, 60), (160, 60), (160, 160), (60, 160)])
check('outline off the mesh: clear message, nothing made', r != {'FINISHED'} or 'Armor plate' not in msg)
r, msg = lasso([(600, 470), (900, 470), (900, 530), (600, 530)])
check('outline partly past the edge: still a plate, the report says so', r == {'FINISHED'} and 'past the surface' in msg,
      msg)

from mecha_lab import workspace_ui as wui
keys = wui._tool_keymap('PLATE')
check('Armor Plate tool draws with the shared lasso', any(k[0] == 'mch.cut_stroke' and
                                                          ('mode', 'PLATE') in k[2]['properties'] for k in keys))
check('draw colour of its own', ce.stroke_color('PLATE', False) != ce.stroke_color('CUT', False))
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
