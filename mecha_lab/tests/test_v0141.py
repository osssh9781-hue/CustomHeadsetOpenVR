"""0.14.1 Base Mesh Sketch First: draw = add to an orange sketch, Alt+draw =
subtract from it, Enter = mesh (Alt+Enter = cut into the mesh below)."""
import json
import sys
import types

from _harness import bpy, check, cube, fresh, non_manifold, select_only, summary, volume
from mathutils import Quaternion

import mecha_lab
from mecha_lab import base_mesh as bm_, core_geometry as cg, cut_engine as ce


def sq(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def item(op, loop, holes=()):
    return {'op': op, 'groups': [[loop, list(holes)]]}


def area(groups):
    return sum(cg.signed_area(o) + sum(cg.signed_area(h) for h in hs) for o, hs in groups)


g = bm_.sketch_regions([item('ADD', sq(0, 0, 2, 2)), item('ADD', sq(1, 1, 3, 3))])
check('two overlapping shapes merge into one outline (area 7)', len(g) == 1 and not g[0][1] and
      abs(area(g) - 7.0) < 1e-6, (len(g), area(g)))
check('merged outline keeps only its corners (8)', len(g[0][0]) == 8, len(g[0][0]))
g = bm_.sketch_regions([item('ADD', sq(0, 0, 4, 4)), item('SUB', sq(1, 1, 2, 2))])
check('Alt inside = a hole (area 15)', len(g) == 1 and len(g[0][1]) == 1 and abs(area(g) - 15.0) < 1e-6,
      (len(g), area(g)))
check('outer counter-clockwise, hole clockwise', cg.signed_area(g[0][0]) > 0 and cg.signed_area(g[0][1][0]) < 0)
g = bm_.sketch_regions([item('ADD', sq(0, 0, 4, 4)), item('SUB', sq(3, 1, 5, 2))])
check('Alt across the border = a notch (area 15)', len(g) == 1 and not g[0][1] and abs(area(g) - 15.0) < 1e-6)
g = bm_.sketch_regions([item('ADD', sq(0, 0, 4, 1)), item('SUB', sq(1.5, -1, 2.5, 2))])
check('Alt through the middle = two pieces', len(g) == 2 and abs(area(g) - 3.0) < 1e-6, (len(g), area(g)))
g = bm_.sketch_regions([item('ADD', sq(0, 0, 4, 4)), item('SUB', sq(1, 1, 3, 3)), item('ADD', sq(1.5, 1.5, 2.5, 2.5))])
check('order matters: adding inside a hole makes an island', len(g) == 2 and abs(area(g) - 13.0) < 1e-6,
      (len(g), area(g)))
g = bm_.sketch_regions([item('ADD', sq(0, 0, 1, 1)), item('SUB', sq(-1, -1, 2, 2))])
check('subtract everything = empty sketch', g == [])
g = bm_.sketch_regions([item('ADD', sq(0, 0, 4, 4), [list(reversed(sq(1, 1, 3, 3)))])])
check('a stroke that already has a hole keeps it', len(g) == 1 and len(g[0][1]) == 1 and abs(area(g) - 12) < 1e-6)
g = bm_.sketch_regions([item('ADD', sq(0, 0, 1, 1)), item('ADD', sq(1, 0, 2, 1))])
check('shapes sharing an edge become one outline', len(g) == 1 and abs(area(g) - 2.0) < 1e-6, len(g))

# ---- through the real stroke logic with a fake viewport
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
    def __init__(self, native='mecha.base_mesh'):
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


def E(type_, value='PRESS', x=500, y=500, alt=False):
    return types.SimpleNamespace(type=type_, value=value, mouse_x=x, mouse_y=y, alt=alt,
                                 shift=False, ctrl=False, oskey=False)


class Op(ce.StrokeLogic):
    def __init__(self):
        self.mode = 'BASE'
        self.reports = []

    def report(self, kind, msg):
        self.reports.append((tuple(kind), msg))


def rect(x0, y0, x1, y1, alt=False):
    ctx, op = Ctx(), Op()
    op.invoke(ctx, E('LEFTMOUSE', 'PRESS', x0, y0, alt))
    op.modal(ctx, E('MOUSEMOVE', 'NOTHING', (x0 + x1) // 2, (y0 + y1) // 2, alt))
    r = op.modal(ctx, E('LEFTMOUSE', 'RELEASE', x1, y1, alt))
    return r, (op.reports[-1][1] if op.reports else '')


fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'RECT'
S.mch_settings.mch_active_tool = 'BASE'
check('Sketch First is on by default', S.mch_base.sketch is True)
S.mch_base.profile = 'FLAT'
S.mch_base.height = 0.2
n0 = len(bpy.data.objects)
r, msg = rect(400, 400, 600, 600)                       # 2 x 2 units
check('draw = orange sketch, no mesh yet', r == {'FINISHED'} and len(bpy.data.objects) == n0 and
      bm_.sketch_data(S) is not None and 'Sketch' in msg, msg)
r, msg = rect(500, 500, 700, 700)                       # overlapping square
r, msg = rect(450, 450, 550, 550, alt=True)             # Alt = 1 x 1 hole
data = bm_.sketch_data(S)
check('Alt+draw subtracts from the sketch (3 shapes stored)', r == {'FINISHED'} and
      [it['op'] for it in data['items']] == ['ADD', 'ADD', 'SUB'], msg)
r, msg = rect(100, 100, 150, 150, alt=True)
check('Alt outside the sketch is allowed (nothing to remove)', r == {'FINISHED'})
bpy.ops.mch.base_sketch_undo()
check('Backspace removes the last shape', len(bm_.sketch_data(S)['items']) == 3)
res = bpy.ops.mch.base_sketch_commit(cutter=False)
new = [o for o in bpy.data.objects if o.name.startswith('MCH_Base')]
check('Enter: one live Base Mesh from the combined sketch', res == {'FINISHED'} and len(new) == 1 and
      non_manifold(new[0]) == 0 and new[0].mch_base.live)
check('mesh volume = (4 + 4 - 1 overlap - 1 hole) x height', abs(volume(new[0]) - 6.0 * 0.2) < 1e-4,
      volume(new[0]))
check('sketch cleared after the mesh is made', bm_.sketch_data(S) is None)
stored = json.loads(new[0].mch_base.outline)
check('the combined outline (with its hole) is stored for live rebuilds',
      len(stored['groups']) == 1 and len(stored['groups'][0]['holes']) == 1)
new[0].mch_base.profile = 'CHAMFER'
check('live rebuild of the sketched mesh still works', non_manifold(new[0]) == 0 and
      not new[0].mch_base.last_error, new[0].mch_base.last_error)

# Alt first: nothing to subtract from
r, msg = rect(400, 400, 600, 600, alt=True)
check('Alt as the first stroke: clear message, no sketch', bm_.sketch_data(S) is None and
      'Draw a shape first' in msg, msg)

# Alt+Enter: cut the sketch into the mesh below
fresh()
mecha_lab.register()
S = C.scene
S.mch_brush.shape = 'RECT'
S.mch_settings.mch_active_tool = 'BASE'
S.mch_base.profile, S.mch_base.height = 'FLAT', 0.5
hull = cube('Hull', size=4.0)
select_only(hull)
v0 = volume(hull)
rect(400, 400, 600, 600)
res = bpy.ops.mch.base_sketch_commit(cutter=True)
check('Alt+Enter: the sketch cuts a pocket into the mesh below', res == {'FINISHED'} and
      volume(hull) < v0 - 1.0 and non_manifold(hull) == 0 and [o.name for o in bpy.data.objects] == ['Hull'],
      (v0, volume(hull)))
rect(400, 400, 600, 600)
bpy.ops.mch.base_sketch_clear()
check('Esc clears the sketch', bm_.sketch_data(S) is None)

# everything subtracted -> Enter refuses, sketch kept
rect(400, 400, 500, 500)
rect(350, 350, 550, 550, alt=True)
res = bpy.ops.mch.base_sketch_commit()
check('empty sketch: Enter changes nothing and keeps the sketch', res == {'CANCELLED'} and
      bm_.sketch_data(S) is not None)
bpy.ops.mch.base_sketch_clear()

# instant mode = the old behaviour
S.mch_base.sketch = False
n0 = len(bpy.data.objects)
rect(700, 700, 800, 800)
check('Sketch First off: an outline becomes a mesh at once', len(bpy.data.objects) == n0 + 1 and
      bm_.sketch_data(S) is None)

from mecha_lab import workspace_ui as wui
keys = [k[0] for k in wui._tool_keymap('BASE')]
check('Base Mesh tool keys: Enter / Esc / Backspace for the sketch',
      'mch.base_sketch_key' in keys and 'mch.base_sketch_clear' in keys and 'mch.base_sketch_undo' in keys)
check('Cut tool keys unchanged (no sketch keys)', 'mch.base_sketch_key' not in [k[0] for k in wui._tool_keymap('CUT')])
check('Esc clears the sketch before it leaves the tool',
      keys.index('mch.base_sketch_clear') < keys.index('mch.exit_tool'))
add_c, sub_c = ce.stroke_color('BASE', False), ce.stroke_color('BASE', True)
check('0.14.4: Alt (subtract) line has its own colour, clearly different from the add line',
      sum(abs(x - y) for x, y in zip(add_c[:3], sub_c[:3])) > 0.4 and add_c[0] > 0.9 and sub_c[0] > 0.9 and
      sub_c[1] < add_c[1] - 0.2, (add_c, sub_c))
check('Cut colours unchanged', ce.stroke_color('CUT', False) == ce._COLORS['CUT'] and
      ce.stroke_color('CUT', True) == ce._COLORS['CUT_INV'] and ce.stroke_color('SPLIT', True) == ce._COLORS['SPLIT'])
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
