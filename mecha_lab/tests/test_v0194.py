"""0.19.4: tall plates rise along the average direction (no fanning out on a
shoulder), crease height follows the plate size (not its height), line width
/ position / turn, edge rims per side (N / E / S / W)."""
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
S.mch_settings.mch_active_tool = 'PLATE'
MODE[0], NATIVE[0] = 'PLATE', 'mecha.armor_plate'
from mecha_lab import armor_plate as ap, panel_gen as pg
check('flat band in the line field', pg.facet_value([(0, 0, 0.0, 1.0)], 0.0, 0.2, 1.0, 0.3) == 1.0 and
      pg.facet_value([(0, 0, 0.0, 1.0)], 0.0, 0.8, 1.0, 0.3) < 1.0)
ln = pg.facet_lines('CENTER', 1, 1, 0.0, [(x * 0.1, y * 0.03) for x in range(-20, 21) for y in range(-10, 11)], 2.0,
                    offset=0.5)
check('Line Position moves the line across', abs(ln[0][1] - 0.5) < 1e-6, ln)
box = cube('Box', 4.0)
S.mch_plate.preset = 'FLAT'
S.mch_plate.spacing = 40
r, m = lasso([(250, 380), (750, 380), (750, 620), (250, 620)])
pl = C.active_object
p = pl.mch_extract
p.extract_height = 0.2
p.facet_style = 'CENTER'
p.facet_depth = 0.5


def crease_top(ob):
    cr = ob.data.attributes.get('mch_crease')
    return max(ob.data.vertices[i].co.z for k, e in enumerate(ob.data.edges) if cr.data[k].value > 0.5
               for i in e.vertices)


c1 = crease_top(pl) - 2.0 - 0.2
p.extract_height = 1.0
c2 = crease_top(pl) - 2.0 - 1.0
check('crease height does not grow with the plate height', abs(c1 - c2) < 1e-3 and c1 > 0.01, (c1, c2))
p.extract_height = 0.2
p.facet_width = 0.3
zs = sorted({round(pl.data.vertices[i].co.z, 4) for k, e in enumerate(pl.data.edges)
             if pl.data.attributes['mch_crease'].data[k].value > 0.5 for i in e.vertices})
ys = sorted({round(pl.data.vertices[i].co.y, 3) for k, e in enumerate(pl.data.edges)
             if pl.data.attributes['mch_crease'].data[k].value > 0.5 for i in e.vertices})
check('Line Width: a flat raised strip with two sharp edges', len(zs) == 1 and len(ys) >= 2 and ys[-1] - ys[0] > 0.2,
      (zs, ys))
spec = ap.slider_spec(C, 'line_turn')
spec[4](30)
check('Line Turn slider (degrees)', abs(math.degrees(p.facet_rotation) - 30) < 1e-4 and non_manifold(pl) == 0)
p.facet_style = 'NONE'
p.facet_rotation = 0.0
# rims
base_n = max(v.co.z for v in pl.data.vertices if v.co.y > 1.0)
bpy.ops.mch.plate_rim(side='N')
north = max(v.co.z for v in pl.data.vertices if v.co.y > 1.0)
south = max(v.co.z for v in pl.data.vertices if v.co.y < -1.0)
mid = max(v.co.z for v in pl.data.vertices if abs(v.co.y) < 0.3 and abs(v.co.x) < 0.5)
check('N rim: only the north border rises', p.rim_n and north > base_n + 0.01 and abs(south - base_n) < 1e-3 and
      abs(mid - base_n) < 1e-3, (base_n, north, south, mid))
for k in 'ESW':
    bpy.ops.mch.plate_rim(side=k)
tops = {k: max(v.co.z for v in pl.data.vertices if f(v.co)) for k, f in
        (('N', lambda c: c.y > 1.0), ('S', lambda c: c.y < -1.0), ('E', lambda c: c.x > 2.3), ('W', lambda c: c.x < -2.3))}
check('all four on: the whole border rises, the middle stays', all(t > base_n + 0.01 for t in tops.values()) and
      abs(max(v.co.z for v in pl.data.vertices if abs(v.co.y) < 0.3 and abs(v.co.x) < 0.5) - base_n) < 1e-3 and
      non_manifold(pl) == 0, tops)
for k in 'NESW':
    bpy.ops.mch.plate_rim(side=k)              # all off again
flat_top = max(v.co.z for v in pl.data.vertices)
bpy.ops.mch.plate_rim(side='RANDOM')
zs_r = [v.co.z for v in pl.data.vertices]
check('Random rim pieces: some border parts rise, not all', p.rim_random and max(zs_r) > flat_top + 0.01 and
      non_manifold(pl) == 0)
sig = sorted(round(z, 4) for z in zs_r)
bpy.ops.mch.plate_rim(side='RANDOM')
check('pressed again: new random pieces', p.rim_seed == 2 and sorted(round(v.co.z, 4) for v in pl.data.vertices) != sig)
before = sorted(round(v.co.z, 4) for v in pl.data.vertices)
bpy.ops.mch.plate_rim(side='PROFILE')
check('rim edge: chamfer -> bevel changes the slope', p.rim_profile == 'BEVEL' and
      sorted(round(v.co.z, 4) for v in pl.data.vertices) != before)
ap.slider_spec(C, 'rim_slope')[4](80)
check('Rim Slope slider', abs(p.rim_slope - 0.8) < 1e-6 and non_manifold(pl) == 0)
lay = ap.hud_layout([(400, 300), (600, 500)], 1600, 900)
check('HUD: N E S W row and rim sliders', all(k in lay for k in ('rim_n', 'rim_e', 'rim_s', 'rim_w', 'rim_rand', 'rim_prof',
                                                                  'slider_rim_height', 'slider_rim_width',
                                                                  'slider_rim_slope')))
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
