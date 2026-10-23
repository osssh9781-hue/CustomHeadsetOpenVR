"""0.22.0 Line lasso (draw a line, the tool uses a band of Line Width around it) for
Cut / Split / Base Mesh / Armor Plate / Cloth Plate."""
import math
import sys
import types

from _harness import bpy, check, cube, fresh, non_manifold, summary, volume
from mathutils import Quaternion

import mecha_lab
from mecha_lab import cut_engine as ce, core_geometry as cg, lasso_line as ll, tool_state as ts

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


def lasso(points, finish='RET'):
    ctx, op = Ctx(), Op()
    if br.line_mode:
        # 0.24.20 Line mode: press, drag through the points, release applies (no Enter / double-click)
        op.invoke(ctx, E('LEFTMOUSE', 'PRESS', *points[0]))
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            for k in range(1, 21):
                t = k / 20
                op.modal(ctx, E('MOUSEMOVE', 'NOTHING', x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
        preview = (op.preview_closed(), op.preview_loops())
        r = op.modal(ctx, E('LEFTMOUSE', 'RELEASE', *points[-1]))
        return r, (op.reports[-1][1] if op.reports else ''), preview
    op.invoke(ctx, E('LEFTMOUSE', 'PRESS', *points[0]))
    op.modal(ctx, E('LEFTMOUSE', 'RELEASE', *points[0]))
    for x, y in points[1:]:
        op.modal(ctx, E('LEFTMOUSE', 'PRESS', x, y))
        op.modal(ctx, E('LEFTMOUSE', 'RELEASE', x, y))
    preview = (op.preview_closed(), op.preview_loops())
    r = op.modal(ctx, E(finish))
    return r, (op.reports[-1][1] if op.reports else ''), preview


def self_crossings(loop):
    n = len(loop)
    hits = 0
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            if ll._seg_hit(loop[i], loop[(i + 1) % n], loop[j], loop[(j + 1) % n]) is not None:
                hits += 1
    return hits


def area(loop):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(loop, loop[1:] + loop[:1]))) / 2


# ---- pure band
b = ll.band([(0, 0), (200, 0)], 20, 'ROUND')
check('band: straight line -> capsule area', abs(area(b) - (200 * 20 + math.pi * 100)) < 60, area(b))
b = ll.band([(0, 0), (200, 0)], 20, 'FLAT')
check('band: flat ends -> rectangle (+ the half-width ends)', abs(area(b) - 220 * 20) < 40, area(b))
zig = [(0, 0), (40, 60), (80, 0), (120, 60), (160, 0)]
b = ll.band(zig, 30, 'ROUND')
check('band: tight zigzag has no self crossings', len(b) > 10 and self_crossings(b) == 0, self_crossings(b))
check('band: tiny path -> nothing', ll.band([(0, 0)], 20) == [])
curl = [(100 * math.cos(a / 10), 100 * math.sin(a / 10)) for a in range(0, 50)]
b = ll.band(curl, 60)
check('band: curve with wide line stays simple', self_crossings(b) == 0, self_crossings(b))

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
br = S.mch_brush
br.shape = 'LASSO'
br.line_open = False
check('Line button props', hasattr(br, 'line_mode') and hasattr(br, 'line_width') and hasattr(br, 'line_caps'))
check('Line mode off by default', br.line_mode is False)
check('pixels per unit (ortho 100 px / m)', abs(ll.pixels_per_unit(C, VIEW[0], (500, 500)) - 100.0) < 1.0,
      ll.pixels_per_unit(C, VIEW[0], (500, 500)))

# ---- Armor Plate with a line: a strip, not an area
box = cube('Box', 4.0)
use_tool('PLATE')
br.line_mode = True
br.line_width = 0.4
br.line_caps = 'FLAT'
r, m, prev = lasso([(300, 500), (700, 500)])
check('line preview is a closed band', prev[0] is True and prev[1] and len(prev[1][0]) >= 4)
ob = C.active_object
check('Armor Plate from a 2-point line', r == {'FINISHED'} and ob is not None and ob != box, (r, m))
if ob is not None and ob != box:
    d = ob.dimensions
    check('plate strip is about Line Width wide', 0.3 < min(d.x, d.y) < 0.6 and max(d.x, d.y) > 3.5,
          tuple(round(x, 3) for x in d))
    bpy.data.objects.remove(ob)

# ---- Cloth Plate with a curve-ish line (4 points)
use_tool('WRINKLE')
r, m, prev = lasso([(300, 400), (450, 600), (550, 400), (700, 600)])
ob = C.active_object
check('Cloth Plate from a line', r == {'FINISHED'} and ob is not None and ob != box, (r, m))
if ob is not None and ob != box:
    bpy.data.objects.remove(ob)

# ---- Base Mesh with a line
use_tool('BASE')
S.mch_base.sketch = False
n0 = len(bpy.data.objects)
r, m, prev = lasso([(300, 300), (700, 700)])
check('Base Mesh from a line', r == {'FINISHED'} and len(bpy.data.objects) >= n0, (r, m))

# ---- 0.24.20 Plate Detail 1 / 2 / 3 with a line: a strip of detail along it
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
box = cube('Box', 4.0)
for tool in ('DETAIL', 'DETAIL2', 'DETAIL3'):
    use_tool(tool)
    n0 = len(bpy.data.objects)
    r, m, prev = lasso([(300, 500), (700, 500)])
    made = [o for o in bpy.data.objects if o != box]
    check(f'{tool} from a line (strip along it)', r == {'FINISHED'} and len(bpy.data.objects) > n0, (r, m))
    for o in made:
        bpy.data.objects.remove(o)

# ---- Cut: a groove through the box
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
box = cube('Box', 4.0)
for o in C.selected_objects:
    o.select_set(False)
box.select_set(True)
C.view_layer.objects.active = box
use_tool('CUT')
v0 = volume(box)
br.line_caps = 'ROUND'
r, m, prev = lasso([(250, 500), (750, 500)])
v1 = volume(box)
check('Cut with a line = groove (removes about width x length x depth)', r == {'FINISHED'} and v1 < v0
      and abs((v0 - v1) - 0.4 * 4.0 * 4.0) < 1.2, (r, m, round(v0, 3), round(v1, 3)))
check('cut box stays closed', non_manifold(box) == 0)

# ---- Line mode off: area again
br.line_mode = False
use_tool('PLATE')
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
box = cube('Box', 4.0)
r, m, prev = lasso([(300, 300), (700, 300), (700, 700), (300, 700)])
ob = C.active_object
check('Line off: lasso area as before', r == {'FINISHED'} and ob is not None and min(ob.dimensions.x,
                                                                                    ob.dimensions.y) > 3.0)
r, m, prev = lasso([(300, 300), (700, 300)])
check('Line off: 2 points still refused for Armor Plate', r == {'RUNNING_MODAL'} or 'closed' in m.lower(), (r, m))
check('Line only for lasso shapes', not ll.enabled(C, 'PLATE', 'RECT') and not ll.enabled(C, 'MASK', 'LASSO'))
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
