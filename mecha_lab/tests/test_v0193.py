"""0.19.3 Sketch First for every lasso tool: draw outlines into a sketch,
Alt+draw subtracts, Enter applies the tool once with the combined outline
(Cut, Split, Armor Plate); one Sketch button next to the shapes."""
import math
import sys
import types

from _harness import bpy, check, cube, fresh, non_manifold, select_only, summary, volume
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import cut_engine as ce, core_geometry as cg, lasso_sketch as ls, workspace_ui as wui

# ---- through the real stroke logic
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


def lasso(points, alt=False):
    ctx, op = Ctx(), Op()
    op.invoke(ctx, E('LEFTMOUSE', 'PRESS', *points[0], alt=alt))
    op.modal(ctx, E('LEFTMOUSE', 'RELEASE', *points[0], alt=alt))
    for x, y in points[1:]:
        op.modal(ctx, E('LEFTMOUSE', 'PRESS', x, y, alt=alt))
        op.modal(ctx, E('LEFTMOUSE', 'RELEASE', x, y, alt=alt))
    r = op.modal(ctx, E('RET', alt=alt))
    return r, (op.reports[-1][1] if op.reports else '')


fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
check('Sketch is off by default for Cut / Split / Plate', not S.mch_brush.sketch_first)
check('lasso tools get Enter / Alt+Enter / Backspace / Esc for the sketch',
      all(any(k[0] == 'mch.lasso_sketch_key' for k in wui._tool_keymap(m)) for m in ('CUT', 'SPLIT', 'PLATE')))

# ---- Cut with a sketch
S.mch_settings.mch_active_tool = 'CUT'
MODE[0], NATIVE[0] = 'CUT', 'mecha.cut'
S.mch_settings.auto_apply = True
S.mch_cut.depth_mode = 'THROUGH' if 'THROUGH' in [i.identifier for i in S.mch_cut.bl_rna.properties['depth_mode'].enum_items] else S.mch_cut.depth_mode
box = cube('Box', 4.0)
select_only(box)
ls.set_on(C, True)
check('Sketch button switches every lasso tool (Base Mesh too)', S.mch_brush.sketch_first and S.mch_base.sketch)
nv = len(box.data.vertices)
v0 = volume(box)
r1, m1 = lasso([(350, 350), (550, 350), (550, 550), (350, 550)])
r2, m2 = lasso([(450, 450), (650, 450), (650, 650), (450, 650)])
check('drawing adds outlines to the sketch, the mesh is not cut yet', len(box.data.vertices) == nv and
      ls.data(S) is not None and len(ls.data(S)['items']) == 2, (m1, m2))
r3, m3 = lasso([(480, 380), (520, 380), (520, 420), (480, 420)], alt=True)
check('Alt+draw subtracts from the sketch', ls.data(S)['items'][-1]['op'] == 'SUB' and 'subtracted' in m3, m3)
bpy.ops.mch.lasso_sketch_undo()
check('Backspace removes the last outline', len(ls.data(S)['items']) == 2)
loops, proj = ls.screen_loops(ls.data(S))
check('two overlapping squares become one outline (8 corners) in the first view',
      len(loops) == 1 and len(loops[0]) == 8, [len(l) for l in loops])
res = bpy.ops.mch.lasso_sketch_commit()
v1 = volume(box)
check('Enter: the tool runs once with the combined outline, sketch cleared',
      res == {'FINISHED'} and ls.data(S) is None and v1 < v0 - 0.1 and non_manifold(box) == 0, (v0, v1))

# ---- Armor Plate with a sketch (subtract a notch)
S.mch_settings.mch_active_tool = 'PLATE'
MODE[0], NATIVE[0] = 'PLATE', 'mecha.armor_plate'
fresh()
mecha_lab.register()
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
S.mch_settings.mch_active_tool = 'PLATE'
ls.set_on(C, True)
box = cube('Box', 4.0)
r, m = lasso([(300, 300), (700, 300), (700, 700), (300, 700)])
r, m = lasso([(450, 600), (550, 600), (550, 760), (450, 760)], alt=True)
check('plate sketch: nothing made yet', all(not getattr(o, 'mch_extract', None) or not o.mch_extract.is_part
                                             for o in bpy.data.objects))
res = bpy.ops.mch.lasso_sketch_commit()
plate = C.active_object
check('Enter: one plate with the notch cut out of its outline', res == {'FINISHED'} and plate.mch_extract.is_part and
      non_manifold(plate) == 0 and ls.data(S) is None)
ys = [(plate.matrix_world @ v.co) for v in plate.mch_extract.region.vertices]
inside_notch = [p for p in ys if abs(p.x) < 0.45 and p.y > 1.05]
check('... the notch area is empty', not inside_notch, len(inside_notch))
r, m = lasso([(320, 320), (400, 320), (400, 400), (320, 400)])
bpy.ops.mch.lasso_sketch_clear()
check('Esc clears the sketch', ls.data(S) is None)
ls.set_on(C, False)
r, m = lasso([(320, 320), (420, 320), (420, 420), (320, 420)])
check('Sketch off: the plate is made at once again', r == {'FINISHED'} and 'Armor plate' in m, m)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
