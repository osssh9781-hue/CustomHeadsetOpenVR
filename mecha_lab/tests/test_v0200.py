"""0.20.0 Cloth Wrinkle: lasso on a mesh -> separate cloth layer with
procedural Geometry Nodes wrinkles (Padding / Denim / Leather), live inputs
(type, strength, scale, direction, seed, detail, edge soft, thickness), HUD,
Apply / Remove."""
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
from mecha_lab import cloth_wrinkle as cw, tool_state as ts
S.mch_settings.mch_active_tool = 'WRINKLE'
MODE[0], NATIVE[0] = 'WRINKLE', 'mecha.cloth_wrinkle'
check('Cloth Wrinkle is a lasso tool of its own', ts.TOOL_BY_ID['WRINKLE'][5] == 'mecha.cloth_wrinkle' and
      'WRINKLE' in ts.SHAPE_TOOLS and ts.NATIVE_TO_TOOL['mecha.cloth_wrinkle'] == 'WRINKLE')
ng = cw.build_group()
check('wrinkle node group built with its inputs', ng.bl_idname == 'GeometryNodeTree' and
      all(cw._ident(n) for n, *_r in cw.INPUTS))
box = cube('Box', 4.0)
nv = len(box.data.vertices)
S.mch_wrinkle.wtype = 'DENIM'
r, m = lasso([(300, 350), (700, 350), (700, 650), (300, 650)])
ob = C.active_object
check('lasso: a separate live cloth layer, the box unchanged', r == {'FINISHED'} and cw.is_wrinkle(ob) and
      len(box.data.vertices) == nv and 'Denim' in m, m)


def heights(o):
    dg = C.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    mw = ev.matrix_world
    zs = [(mw @ v.co).z for v in me.vertices]
    n = len(me.polygons)
    ev.to_mesh_clear()
    return zs, n


zs, nf = heights(ob)
check('wrinkles really move the surface (not flat)', max(zs) - min(zs) > 0.02 and min(zs) > 1.99, (min(zs), max(zs)))
sig = {}
for i, t in enumerate(cw.TYPE_IDS):
    cw.set_input(ob, 'Type', i)
    sig[t] = sorted(round(z, 4) for z in heights(ob)[0])
check('Padding / Denim / Leather are different patterns', len({tuple(v) for v in sig.values()}) == 3)
cw.set_input(ob, 'Type', 1)
base = sorted(round(z, 4) for z in heights(ob)[0])
bpy.ops.mch.wrinkle_reroll()
check('Reroll: new seed, new wrinkles', cw.get_input(ob, 'Seed') == 2 and
      sorted(round(z, 4) for z in heights(ob)[0]) != base)
d0 = sorted(round(z, 4) for z in heights(ob)[0])
cw.slider_spec(C, 'direction')[4](45)
check('Direction slider turns the folds', abs(math.degrees(cw.get_input(ob, 'Direction')) - 45) < 1e-3 and
      sorted(round(z, 4) for z in heights(ob)[0]) != d0)
z1 = heights(ob)[0]
cw.slider_spec(C, 'strength')[4](0)
z2 = heights(ob)[0]
thick = ob.modifiers[cw.MOD_SHELL].thickness
check('Strength 0: flat cloth layer (only its thickness)', max(z2) - min(z2) < max(z1) - min(z1) and
      max(z2) - min(z2) < thick * 1.1 + 1e-3, (max(z2) - min(z2), thick))
cw.slider_spec(C, 'strength')[4](40)
cw.slider_spec(C, 'detail')[4](2)
check('Detail: more faces', heights(ob)[1] > nf)
cw.slider_spec(C, 'detail')[4](1)
cw.slider_spec(C, 'edge')[4](0)
bpy.ops.mch.wrinkle_type(step=1)
check('type arrows change the live layer', int(cw.get_input(ob, 'Type')) == cw.TYPE_IDS.index(S.mch_wrinkle.wtype))
zl0 = min(heights(ob)[0])
cw.slider_spec(C, 'lift')[4](100)
zl1 = min(heights(ob)[0])
check('Height slider lifts the whole cloth layer', zl1 > zl0 + 0.1, (zl0, zl1))
cw.slider_spec(C, 'lift')[4](2)
dz0 = max(heights(ob)[0]) - min(heights(ob)[0])
cw.slider_spec(C, 'strength')[4](80)
dz1 = max(heights(ob)[0]) - min(heights(ob)[0])
check('Depth slider: deeper wrinkles', dz1 > dz0, (dz0, dz1))
select_only(ob)
nlive = heights(ob)[1]
bpy.ops.mch.make_highpoly()
hpo = C.active_object
check('Make High Poly on a live wrinkle layer: denser plain copy, same wrinkles, the layer stays live',
      hpo.get('mch_highpoly_src') == ob.name and len(hpo.modifiers) == 0 and len(hpo.data.polygons) > nlive and
      cw.is_wrinkle(ob) and int(cw.get_input(ob, 'Detail')) == 1, (nlive, len(hpo.data.polygons)))
ob.hide_set(False)
select_only(ob)
lay = cw.hud_layout([(400, 300), (600, 500)], 1600, 900)
check('HUD right of the layer: Apply, Remove, type arrows + reroll, sliders',
      lay['apply'][0] > 600 and lay['apply'][1] > lay['cancel'][1] > lay['prev'][1] > lay['slider_lift'][1] >
      lay['slider_strength'][1])
res = bpy.ops.mch.wrinkle_apply()
check('Apply: plain mesh with the wrinkles baked', res == {'FINISHED'} and not cw.is_wrinkle(ob) and
      len(ob.modifiers) == 0 and len(ob.data.polygons) >= nf)
r, m = lasso([(350, 400), (500, 400), (500, 550), (350, 550)])
name = C.active_object.name
bpy.ops.mch.wrinkle_remove()
check('Remove: the layer is deleted', name not in bpy.data.objects)
check('HUD registered', 'bl_rna' in cw.MCH_GGT_wrinkle_hud.__dict__)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
