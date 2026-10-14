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
check('lasso: a separate live cloth plate, the box unchanged', r == {'FINISHED'} and cw.is_wrinkle(ob) and
      len(box.data.vertices) == nv and 'Cloth plate' in m, m)
cw.set_input(ob, 'Detail', 1)


def zat(o, pick):
    dg = C.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    mw = ev.matrix_world
    pts = [mw @ v.co for v in me.vertices]
    ev.to_mesh_clear()
    return max(p_.z for p_ in pts if pick(p_))


cw.apply_preset(ob, 'PADDING')
centre = zat(ob, lambda q: abs(q.x) < 0.5 and abs(q.y) < 0.5)
rim = zat(ob, lambda q: abs(q.x) > 1.9 and abs(q.y) < 0.5)
check('padded panel: the middle puffs up, the border stays near the surface', centre > rim + 0.05,
      (centre, rim))
for nm in ('Puff', 'Pinch', 'Stitch'):
    assert cw.get_input(ob, nm) > 0, nm
check('defaults: puff, border folds and stitching on, no all-over pattern',
      cw.get_input(ob, 'Strength') == 0.0)
cw.apply_preset(ob, 'DENIM')
check('Denim puffs much less than Padding', cw.get_input(ob, 'Puff') < 0.5 * cw.PRESETS['PADDING']['Puff'] *
      ob['mch_wrinkle_size'])
cw.set_input(ob, 'Strength', 0.12)


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


def flow_angle(o):
    # dominant fold direction: correlation of height with x / y gradients over the top
    dg = C.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    import collections
    gx = gy = 0.0
    for e in me.edges:
        a, b = me.vertices[e.vertices[0]].co, me.vertices[e.vertices[1]].co
        d = b - a
        if d.length < 1e-9:
            continue
        dz = abs(b.z - a.z) / d.length
        gx += dz * abs(d.x) / d.length
        gy += dz * abs(d.y) / d.length
    ev.to_mesh_clear()
    return gx / max(gy, 1e-9)


saved = {nm: cw.get_input(ob, nm) for nm in ('Puff', 'Roll', 'Pinch', 'Stitch')}
for nm in saved:
    cw.set_input(ob, nm, 0.0)
cw.set_input(ob, 'Bend', 0.0)
angs = set()
for sd in range(1, 6):
    cw.set_input(ob, 'Seed', sd)
    angs.add(round(flow_angle(ob), 2))
check('different seeds = different fold directions (not always the same line)', len(angs) >= 3, angs)
for nm, v_ in saved.items():
    cw.set_input(ob, nm, v_)
cw.set_input(ob, 'Seed', 2)
d0 = sorted(round(z, 4) for z in heights(ob)[0])
cw.slider_spec(C, 'direction')[4](45)
check('Direction slider turns the folds', abs(math.degrees(cw.get_input(ob, 'Direction')) - 45) < 1e-3 and
      sorted(round(z, 4) for z in heights(ob)[0]) != d0)
z1 = heights(ob)[0]
cw.slider_spec(C, 'strength')[4](0)
for nm in ('Puff', 'Roll', 'Pinch', 'Stitch'):
    cw.set_input(ob, nm, 0.0)
z2 = heights(ob)[0]
thick = ob.modifiers[cw.MOD_SHELL].thickness
check('Strength 0: flat cloth layer (only its thickness)', max(z2) - min(z2) < max(z1) - min(z1) and
      max(z2) - min(z2) < thick * 1.1 + 1e-3, (max(z2) - min(z2), thick))
cw.slider_spec(C, 'strength')[4](40)
cw.slider_spec(C, 'puff')[4](50)
cw.slider_spec(C, 'detail')[4](2)
check('Detail: more faces', heights(ob)[1] > nf)
cw.slider_spec(C, 'detail')[4](1)
cw.set_input(ob, 'Edge Soft', 0.0)
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
t0 = sorted(round(z, 4) for z in heights(ob)[0])
cw.slider_spec(C, 'tilt')[4](35)
check('Fold Tilt slider leans the folds', abs(math.degrees(cw.get_input(ob, 'Fold Tilt')) - 35) < 1e-3 and
      sorted(round(z, 4) for z in heights(ob)[0]) != t0)
cw.set_input(ob, 'Fold Tilt', 0.0)
for nm in ('Puff', 'Stitch', 'Strength', 'Roll'):
    cw.set_input(ob, nm, 0.0)
cw.set_input(ob, 'Pinch', 0.05)
cw.set_input(ob, 'Variety', 0.0)
cw.set_input(ob, 'Length Random', 0.0)


def mid_var(o):
    dg = C.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    mw = ev.matrix_world
    zz = [(mw @ v.co).z for v in me.vertices if abs((mw @ v.co).x) < 0.8 and abs((mw @ v.co).y) < 0.6 and
          (mw @ v.co).z > 2.0 + ob.modifiers[cw.MOD_SHELL].thickness * 0.5]
    ev.to_mesh_clear()
    return max(zz) - min(zz) if zz else 0.0


cw.set_input(ob, 'Pinch Length', ob['mch_wrinkle_size'] * 0.05)
short = mid_var(ob)
cw.set_input(ob, 'Pinch Length', ob['mch_wrinkle_size'] * 1.5)
long_ = mid_var(ob)
check('long Fold Length: the folds reach into the middle', long_ > short + 0.005, (short, long_))
bpy.ops.mch.wrinkle_reset()
bpy.ops.mch.wrinkle_trim()
check('Edge Trim button: none -> piping on the live panel', int(cw.get_input(ob, 'Trim')) == 1 and
      S.mch_wrinkle.trim == 'PIPING' and cw.get_input(ob, 'Trim Height') > 0)
zt = heights(ob)[0]
cw.set_input(ob, 'Sections', 3)
check('Sections: 3 stitched cells change the panel', sorted(round(z, 4) for z in heights(ob)[0]) !=
      sorted(round(z, 4) for z in zt))
z3 = sorted(round(z, 4) for z in heights(ob)[0])
cw.slider_spec(C, 'sec_turn')[4](45)
z4 = sorted(round(z, 4) for z in heights(ob)[0])
check('Section Turn rotates the seams', z4 != z3)
bpy.ops.mch.wrinkle_seam()
check('seam shape button: straight -> wave', int(cw.get_input(ob, 'Section Shape')) == 1 and
      sorted(round(z, 4) for z in heights(ob)[0]) != z4)
for _i in range(3):
    bpy.ops.mch.wrinkle_seam()
check('... zigzag, chevron, arc', int(cw.get_input(ob, 'Section Shape')) == 4)
zs0 = sorted(round(z, 4) for z in heights(ob)[0])
cw.slider_spec(C, 'sec_end')[4](40)
zs1 = sorted(round(z, 4) for z in heights(ob)[0])
cw.slider_spec(C, 'sec_move')[4](55)
zs2 = sorted(round(z, 4) for z in heights(ob)[0])
check('Section End / Move: the sections sit only in part of the panel and can slide', zs0 != zs1 != zs2 and
      abs(cw.get_input(ob, 'Section Move') - 0.55) < 1e-6)
cw.slider_spec(C, 'random')[4](20)
check('Randomness slider sets angle / length / strength randomness together',
      abs(cw.get_input(ob, 'Variety') - 0.2) < 1e-6 and abs(cw.get_input(ob, 'Length Random') - 0.2) < 1e-6 and
      abs(cw.get_input(ob, 'Tilt Random') - 0.18) < 1e-6)
cw.slider_spec(C, 'random')[4](100)
check('long folds are real lines: a height field on the panel', ob.data.attributes.get(cw.FOLD_H) is not None and
      max(v.value for v in ob.data.attributes[cw.FOLD_H].data) > 0.2)
lr0 = sorted(round(z, 4) for z in heights(ob)[0])
cw.slider_spec(C, 'len_rand')[4](0)
check('Length Random 0 vs 100 differ', sorted(round(z, 4) for z in heights(ob)[0]) != lr0)
cw.set_input(ob, 'Pinch Length', 0.0001)
bpy.ops.mch.wrinkle_reset()
check('Reset: settings and the live panel back to the defaults', S.mch_wrinkle.trim == 'NONE' and
      int(cw.get_input(ob, 'Sections')) == 1 and int(cw.get_input(ob, 'Trim')) == 0 and
      cw.get_input(ob, 'Pinch Length') > 0.01)
lay = cw.hud_layout([(400, 300), (600, 500)], 1600, 900)
check('HUD right of the layer: Apply, Remove, type arrows + reroll, sliders',
      lay['apply'][0] > 600 and lay['apply'][1] > lay['cancel'][1] > lay['prev'][1] > lay['trim'][1] >
      lay['slider_lift'][1] > lay['slider_strength'][1] and 'reset' in lay)
res = bpy.ops.mch.wrinkle_apply()
check('Apply: plain mesh with the wrinkles baked', res == {'FINISHED'} and not cw.is_wrinkle(ob) and
      len(ob.modifiers) == 0 and len(ob.data.polygons) >= nf)
r, m = lasso([(350, 400), (500, 400), (500, 550), (350, 550)])
name = C.active_object.name
bpy.ops.mch.wrinkle_remove()
check('Remove: the layer is deleted', name not in bpy.data.objects)
# last used options: the next panel starts as the last one was left
r, m = lasso([(320, 380), (640, 380), (640, 620), (320, 620)])
o1 = C.active_object
cw.set_input(o1, 'Fold Tilt', 0.5)
cw.set_input(o1, 'Puff', o1['mch_wrinkle_size'] * 0.21)
r, m = lasso([(330, 390), (630, 390), (630, 610), (330, 610)])
o2 = C.active_object
check('last used: the next Cloth Plate keeps tilt and puff (relative to its size)',
      o2 is not o1 and abs(cw.get_input(o2, 'Fold Tilt') - 0.5) < 1e-6 and
      abs(cw.get_input(o2, 'Puff') / o2['mch_wrinkle_size'] - 0.21) < 1e-4)
from mecha_lab import last_used as lu
S.mch_wrinkle.sections = 5
lu.store_scene(S)
S.mch_wrinkle.sections = 1
lu.restore_scene(S)
check('tool settings are remembered for a new file', S.mch_wrinkle.sections == 5)
check('HUD registered', 'bl_rna' in cw.MCH_GGT_wrinkle_hud.__dict__)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
