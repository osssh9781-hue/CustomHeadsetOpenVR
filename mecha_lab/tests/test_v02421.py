"""0.24.21 Creature Base Mesh / Creature Plate start at Resolution 15; with Sketch on, a Free Draw outline becomes
an editable lasso (drag points, Enter applies); Sculpt brush tiles (Sculpt Mode on the selected mesh, back to Object
with Select / Move)."""
import math
import os
import sys
import types

from _harness import bmesh, bpy, check, cube, fresh, non_manifold, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import base_mesh as bm_mod, cut_engine as ce, core_geometry as cg, lasso_line as ll, lasso_sketch as ls
from mecha_lab import tool_state as ts, workspace_ui as wsui

VIEW = [cg.OrthoProjector(Quaternion())]
ce.make_projector = lambda region, rv3d: VIEW[0]
ce.add_draw_handler = lambda op: 'handle'
ce.remove_draw_handler = lambda h: None
ce.open_popup = lambda name: None
ce.exit_tool = lambda context: None
NATIVE = ['mecha.armor_plate']


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
    def __init__(self):
        self.region = Region()
        self.area = types.SimpleNamespace(type='VIEW_3D', regions=[self.region], as_pointer=lambda: 2)
        self.region_data = object()
        self.space_data = types.SimpleNamespace(region_3d=self.region_data)
        self.window_manager = WM()
        self.window = types.SimpleNamespace(as_pointer=lambda: 1)
        self.mode = 'OBJECT'
        self.preferences = bpy.context.preferences
        tools = types.SimpleNamespace(from_space_view3d_mode=lambda mode, create=False:
                                      types.SimpleNamespace(idname=NATIVE[0]))
        self.workspace = types.SimpleNamespace(tools=tools, status_text_set=lambda text: None)

    scene = property(lambda self: bpy.context.scene)
    view_layer = property(lambda self: bpy.context.view_layer)
    selected_objects = property(lambda self: bpy.context.selected_objects)
    collection = property(lambda self: bpy.context.scene.collection)

    def evaluated_depsgraph_get(self):
        return bpy.context.evaluated_depsgraph_get()


def E(type_, value='PRESS', x=500, y=500, alt=False):
    return types.SimpleNamespace(type=type_, value=value, mouse_x=x, mouse_y=y, alt=alt, shift=False, ctrl=False,
                                 oskey=False)


MODE = ['PLATE']


class Op(ce.StrokeLogic):
    def __init__(self):
        self.mode = MODE[0]
        self.reports = []

    def report(self, kind, msg):
        self.reports.append((tuple(kind), msg))




def use_tool(tool):
    S.mch_settings.mch_active_tool = tool
    MODE[0], NATIVE[0] = tool, ts.TOOL_BY_ID[tool][5]


mecha_lab.register()
fresh()
C = bpy.context
S = C.scene

# Resolution 15 to start
bm_mod.init_creature_defaults(S)
check('Creature Base Mesh starts at Resolution 15', S.mch_cbase.resolution == 15, S.mch_cbase.resolution)
check('Base Mesh keeps its own Resolution (28)', S.mch_base.resolution == 28, S.mch_base.resolution)
check('Creature Plate starts at Resolution 15', S.mch_cplate.resolution == 15, S.mch_cplate.resolution)
S.mch_cbase.resolution = 22
bm_mod.init_creature_defaults(S)
check('set only once (your own value stays)', S.mch_cbase.resolution == 22)

# Free Draw + Sketch -> editable lasso
br = S.mch_brush
br.shape = 'STROKE'
br.line_mode = False
box = cube('Box', 4.0)
use_tool('PLATE')
br.sketch_first = True
ctx, op = Ctx(), Op()
circle = [(500 + 150 * math.cos(t), 500 + 150 * math.sin(t)) for t in [i * 2 * math.pi / 60 for i in range(61)]]
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', *circle[0]))
for x, y in circle[1:]:
    op.modal(ctx, E('MOUSEMOVE', 'NOTHING', x, y))
r = op.modal(ctx, E('LEFTMOUSE', 'RELEASE', *circle[-1]))
check('Sketch on: releasing Free Draw does not apply yet (stays editable)', 'RUNNING_MODAL' in r and op.stage == 'POINTS'
      and op.shape == 'LASSO', (r, op.stage, op.shape))
n = len(op.pts)
check('the outline is a handful of lasso points (easy to edit)', 6 <= n <= 60, n)
check('nothing made yet', ls.data(S) is None and len(bpy.data.objects) == 1)
p0 = op.pts[n // 2]                                # (the first point would close the lasso)
op.modal(ctx, E('LEFTMOUSE', 'PRESS', *p0))
op.modal(ctx, E('MOUSEMOVE', 'NOTHING', p0[0] + 40, p0[1]))
op.modal(ctx, E('LEFTMOUSE', 'RELEASE', p0[0] + 40, p0[1]))
moved = any(math.dist(q, (p0[0] + 40, p0[1])) < 2 for q in op.pts)
check('drag a point to adjust the outline', moved and len(op.pts) == n, (len(op.pts), n))
r = op.modal(ctx, E('RET'))
check('Enter applies: the outline goes into the sketch', r == {'FINISHED'} and ls.data(S) is not None,
      (r, op.reports[-1][1] if op.reports else ''))
ls.clear(S) if hasattr(ls, 'clear') else None
br.sketch_first = False
ctx, op = Ctx(), Op()
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', *circle[0]))
for x, y in circle[1:]:
    op.modal(ctx, E('MOUSEMOVE', 'NOTHING', x, y))
r = op.modal(ctx, E('LEFTMOUSE', 'RELEASE', *circle[-1]))
check('Sketch off: Free Draw applies on release as before', r == {'FINISHED'}, r)

# Sculpt brushes
lib = os.path.join(bpy.utils.system_resource('DATAFILES'), 'assets', 'brushes', 'essentials_brushes-mesh_sculpt.blend')
check('Blender\'s sculpt brush library is there', os.path.isfile(lib), lib)
if os.path.isfile(lib):
    with bpy.data.libraries.load(lib) as (src, dst):
        names = set(src.brushes)
    for label, asset, stem, _fb in wsui.SCULPT_BRUSHES:
        check(f'sculpt tile {label}: Blender has the "{asset}" brush', asset in names)
icons = os.path.join(os.path.dirname(mecha_lab.__file__), 'icons')
check('sculpt tiles have pictures', all(os.path.isfile(os.path.join(icons, b[2] + '.png')) for b in wsui.SCULPT_BRUSHES))
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
check('no mesh: the sculpt tiles wait for one', wsui.sculpt_target(C) is None)
ob = cube('Body', 2.0)
for o in C.selected_objects:
    o.select_set(False)
ob.select_set(True)
C.view_layer.objects.active = None
check('a selected mesh is the sculpt target even when not active', wsui.sculpt_target(C) == ob)
C.view_layer.objects.active = ob
r = bpy.ops.mch.sculpt_brush(brush='Clay Strips')
check('a sculpt tile goes to Sculpt Mode on the mesh', 'FINISHED' in r and C.mode == 'SCULPT', (r, C.mode))
bpy.ops.object.mode_set(mode='OBJECT')

# Line Taper / pen Pressure / [ ] width
check('Taper: full width in the middle, a point at the ends', ll.taper_factor(0.5, 1.0) == 1.0
      and ll.taper_factor(0.0, 1.0) == 0.0 and 0 < ll.taper_factor(0.1, 1.0) < 1)
check('Taper 0: even width', ll.taper_factor(0.0, 0.0) == 1.0)
def area(lp):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(lp, lp[1:] + lp[:1]))) / 2
def width_at(lp, x):
    ys = []
    for a, b in zip(lp, lp[1:] + lp[:1]):
        if (a[0] - x) * (b[0] - x) <= 0 and a[0] != b[0]:
            t = (x - a[0]) / (b[0] - a[0])
            ys.append(a[1] + (b[1] - a[1]) * t)
    return max(ys) - min(ys) if len(ys) >= 2 else 0.0
path = [(100 + 10 * i, 500) for i in range(81)]
even = ll.band(path, 40, 'ROUND')
tap = ll.band(path, 40, 'ROUND', taper=1.0)
check('a tapered line is pointed at the ends, full in the middle', width_at(tap, 120) < 0.5 * width_at(even, 120)
      and abs(width_at(tap, 500) - width_at(even, 500)) < 3 and area(tap) < area(even),
      (round(width_at(tap, 120), 1), round(width_at(even, 120), 1), round(width_at(tap, 500), 1)))
prof = ll.pressure_profile(path, [0.2 + 0.8 * i / 80 for i in range(81)])
pr = ll.band(path, 40, 'ROUND', pressure=prof)
check('pen pressure: light = thin, hard = wide', width_at(pr, 150) < width_at(pr, 850) * 0.5,
      (round(width_at(pr, 150), 1), round(width_at(pr, 850), 1)))
br.line_width = 0.02
ce.step_line_width(C, 1.15)
w1 = br.line_width
ce.step_line_width(C, 1 / 1.15)
check('] bigger / [ smaller Line Width', w1 > 0.02 and abs(br.line_width - 0.02) < 1e-9)
check('[ / ] keys in the drawing tools', any(k[0] == 'mch.line_width_step' and k[1]['type'] == 'LEFT_BRACKET'
                                            for k in wsui._tool_keymap('CPLATE')))
br.line_mode, br.shape = True, 'STROKE'
use_tool('CPLATE')
ctx, op = Ctx(), Op()
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 300, 500))
w0 = br.line_width
op.modal(ctx, E('RIGHT_BRACKET'))
check('] while drawing changes the width too', br.line_width > w0)
op.modal(ctx, E('ESC'))
br.line_mode = False

# a mesh that is not one solid (overlapping parts joined): Split explains why it breaks
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
a = cube('A', 2.0)
b = cube('B', 2.0)
b.location = (2.0, 0.0, 0.0)                     # touching faces: merged they become an inside wall
for o in C.selected_objects:
    o.select_set(False)
a.select_set(True)
b.select_set(True)
C.view_layer.objects.active = a
bpy.ops.object.join()
j = C.active_object
bm = bmesh.new()
bm.from_mesh(j.data)
bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
bm.to_mesh(j.data)
bm.free()
multi, open_ = cg.overlap_edges(j)
check('parts joined with an inside wall: found as not one solid (edges with 3+ faces)', multi > 0, (multi, open_))
c = cube('Clean', 2.0)
check('a clean cube is one solid', cg.overlap_edges(c) == (0, 0), cg.overlap_edges(c))
hint = cg.overlap_hint(j, (12, 3))
check('the message says why and what to do (Remesh first)', '12 edges' in hint and 'holes' in hint and 'Remesh' in hint)

# Taper / Pressure are on-off buttons
br.line_taper_on, br.line_taper, br.line_width = False, 1.0, 0.4
TOPP = cg.OrthoProjector(Quaternion())
off = ll.line_loop(C, TOPP, path, br)
br.line_taper_on = True
on = ll.line_loop(C, TOPP, path, br)
check('Taper button off = even width (the amount is kept), on = pointed', area(on) < area(off) * 0.8,
      (round(area(off)), round(area(on))))
br.line_taper_on = False
check('Pressure is a button too (off by default)', br.line_pressure is False)

# Alt + draw cuts a live Creature Plate / Plate Detail (it stays live)
from mecha_lab import creature_plate as cpl, live_subtract as lsub, plate_detail as pdm
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_uv_sphere_add(radius=3, segments=64, ring_count=32, location=(0, 0, -2.6))
body = C.active_object
cpl.perform(C, [[(300, 300), (700, 300), (700, 700), (300, 700)]], TOPP)
plate = C.active_object
n0 = len(plate.data.polygons)
def first_hit(xy):
    o, d = TOPP.ray(xy)
    hit, loc, _n, _i, hob, _m = C.scene.ray_cast(C.evaluated_depsgraph_get(), Vector(o), Vector(d))
    return hob.name if hit else None
check('the plate covers the middle before', first_hit((500, 500)) == plate.name)
msg = lsub.perform(C, 'CPLATE', [[(450, 450), (550, 450), (550, 550), (450, 550)]], TOPP)
check('Alt + draw: that area is cut out of the Creature Plate (a hole)', first_hit((500, 500)) == body.name
      and first_hit((350, 500)) == plate.name, (msg, first_hit((500, 500))))
plate.mch_cplate.peak = plate.mch_cplate.peak * 1.5
check('it stays live: a slider rebuilds it and the hole stays', first_hit((500, 500)) == body.name
      and plate.mch_cplate.last_error == '' if hasattr(plate.mch_cplate, 'last_error') else first_hit((500, 500)) == body.name)
msg = lsub.perform(C, 'CPLATE', [[(650, 250), (760, 250), (760, 360), (650, 360)]], TOPP)
check('a second Alt outline over the edge = a notch', first_hit((690, 320)) == body.name and len(lsub.records(plate)) == 2)
try:
    lsub.perform(C, 'CPLATE', [[(900, 900), (950, 900), (950, 950)]], TOPP)
    check('Alt over no plate: nothing made, a clear message', False)
except cg.CutError as ex:
    check('Alt over no plate: nothing made, a clear message', 'Alt' in str(ex), str(ex))
cpl.apply(plate)
check('Apply keeps the cut mesh, drops the kept outlines', lsub.KEY not in plate and first_hit((500, 500)) == body.name)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
box = cube('Box', 4.0)
pdm.perform(C, [[(300, 300), (700, 300), (700, 700), (300, 700)]], TOPP, 'DETAIL3')
det = C.active_object
check('Plate Detail made', pdm.is_detail(det))
lsub.perform(C, 'DETAIL', [[(450, 450), (550, 450), (550, 550), (450, 550)]], TOPP)
check('Alt + draw cuts a Plate Detail too', first_hit((500, 500)) == box.name and first_hit((350, 500)) == det.name,
      first_hit((500, 500)))
summary()
