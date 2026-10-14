"""0.19.2: plate surface lines (center / cross / random creases, real sharp
edges), High Poly of a plate = the same plate rebuilt densely (shape kept, also
after Apply), points past the surface edge no longer spike, Q pie has Plate,
cut edge Bevel / Chamfer sliders under the lasso settings."""
import math
import sys
import types

from _harness import bpy, bmesh, check, cube, cylinder, fresh, non_manifold, select_only, summary
from mathutils import Euler, Quaternion, Vector
from mathutils.bvhtree import BVHTree

import mecha_lab
from mecha_lab import armor_plate as ap, bottom_bar as bb, cut_engine as ce, core_geometry as cg, panel_gen as pg

# ---- pure
pts = [(x * 0.1, y * 0.03) for x in range(-20, 21) for y in range(-10, 11)]
ln = pg.facet_lines('CENTER', 3, 1, 0.0, pts, 2.0)
check('center line runs along the long side', len(ln) == 1 and abs(math.sin(ln[0][2])) < 1e-6)
check('cross = two perpendicular lines', len(pg.facet_lines('CROSS', 3, 1, 0.0, pts, 2.0)) == 2)
r1 = pg.facet_lines('RANDOM', 4, 7, 0.0, pts, 2.0)
check('random: count lines, same seed = same lines, new seed = new lines',
      len(r1) == 4 and r1 == pg.facet_lines('RANDOM', 4, 7, 0.0, pts, 2.0) and r1 != pg.facet_lines('RANDOM', 4, 8, 0.0, pts, 2.0))
check('tent field: 1 on the line, 0 far away', abs(pg.facet_value(ln, 0.5, 0.0, 1.0) - 1.0) < 1e-9 and
      pg.facet_value(ln, 0.0, 5.0, 1.0) == 0.0)
check('Plate stacked in the Q pie (Base slot)', bb.PIE_SHARED.get('BASE') == ('PLATE',))

src = open(mecha_lab.__file__.replace('__init__.py', 'ui_tool_settings.py')).read()
check('edge finish sliders under the lasso settings', 'def draw_edge_finish' in src and "draw_edge_finish(box, context, mode)" in src)

# ---- through the real stroke logic
VIEW = [cg.OrthoProjector(Quaternion())]
ce.make_projector = lambda region, rv3d: VIEW[0]
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
                                      types.SimpleNamespace(idname='mecha.armor_plate'))
        self.workspace = types.SimpleNamespace(tools=tools, status_text_set=lambda text: None)

    scene = property(lambda self: bpy.context.scene)
    view_layer = property(lambda self: bpy.context.view_layer)
    selected_objects = property(lambda self: bpy.context.selected_objects)
    collection = property(lambda self: bpy.context.scene.collection)

    def evaluated_depsgraph_get(self):
        return bpy.context.evaluated_depsgraph_get()


def E(type_, value='PRESS', x=500, y=500):
    return types.SimpleNamespace(type=type_, value=value, mouse_x=x, mouse_y=y, alt=False, shift=False, ctrl=False,
                                 oskey=False)


class Op(ce.StrokeLogic):
    def __init__(self):
        self.mode = 'PLATE'
        self.reports = []

    def report(self, kind, msg):
        self.reports.append((tuple(kind), msg))


def lasso(points):
    ctx, op = Ctx(), Op()
    op.invoke(ctx, E('LEFTMOUSE', 'PRESS', *points[0]))
    op.modal(ctx, E('LEFTMOUSE', 'RELEASE', *points[0]))
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
tid, t = bb.chosen_tool(C)
check('Tool Active button: knows the chosen tool (Armor Plate), registered', tid == 'PLATE' and
      'bl_rna' in bb.MCH_GGT_tool_active.__dict__ and 'bl_rna' in bb.MCH_OT_tool_active.__dict__)
fake = types.SimpleNamespace(region=types.SimpleNamespace(x=40, height=900),
                             area=types.SimpleNamespace(regions=[types.SimpleNamespace(type='TOOLS', x=0, width=40)]),
                             preferences=C.preferences)
bx, by = bb.active_button_pos(fake)
check('... placed right of Blender\'s toolbar, upper left', 0 < bx < 120 and by > 600, (bx, by))
box = cube('Box', 4.0)
r, msg = lasso([(250, 380), (750, 380), (750, 620), (250, 620)])
plate = C.active_object
p = plate.mch_extract
top0 = max(v.co.z for v in plate.data.vertices)
bpy.ops.mch.plate_lines()
check('Lines button: center crease on', p.facet_style == 'CENTER' and non_manifold(plate) == 0)


def crease_z(ob):
    cr = ob.data.attributes.get('mch_crease')
    if cr is None:
        return []
    return [ob.data.vertices[i].co.z for k, e in enumerate(ob.data.edges) if cr.data[k].value > 0.5
            for i in e.vertices]


zs = [v.co.z for v in plate.data.vertices]
mid = crease_z(plate)
xs = [plate.data.vertices[i].co.x for k, e in enumerate(plate.data.edges)
      if plate.data.attributes['mch_crease'].data[k].value > 0.5 for i in e.vertices] if mid else [0]
check('the crease runs across the plate (long side), highest line on the plate', mid and max(mid) > top0 + 1e-3 and
      abs(max(zs) - max(mid)) < 1e-6 and max(xs) - min(xs) > 3.0, (top0, max(mid) if mid else None))
sharp = plate.data.attributes.get('sharp_edge')
crease = plate.data.attributes.get('mch_crease')
nsharp = sum(1 for i, e in enumerate(plate.data.edges) if crease and crease.data[i].value > 0.5 and sharp.data[i].value)
check('the crease is a real sharp edge, even on the light plate', nsharp >= 2, nsharp)
spec = ap.slider_spec(C, 'crease')
spec[4](-80)
mid2 = crease_z(plate)
check('Crease slider below 0: a valley instead of a ridge', abs(p.facet_depth + 0.8) < 1e-6 and mid2 and
      max(mid2) < top0 - 1e-3)
spec[4](60)
bpy.ops.mch.plate_lines(reroll=True)
check('Reroll: random lines', p.facet_style == 'RANDOM' and non_manifold(plate) == 0)
seed = p.facet_seed
bpy.ops.mch.plate_lines(reroll=True)
check('Reroll again: next seed', p.facet_seed == seed + 1 and non_manifold(plate) == 0)
lay = ap.hud_layout([(400, 300), (600, 500)], 1600, 900)
check('HUD: lines + reroll row above the sliders, Crease slider',
      lay['prev'][1] > lay['lines'][1] > lay['slider_height'][1] and 'slider_crease' in lay)

# High Poly of a live plate: same plate, small faces, no subdivision blobs
p.facet_style = 'CENTER'
nlow = len(plate.data.polygons)
select_only(plate)
bpy.ops.mch.make_highpoly(plate_detail=10)
hp = C.active_object
bb_low = [plate.matrix_world @ Vector(c) for c in plate.bound_box]
bb_hp = [hp.matrix_world @ Vector(c) for c in hp.bound_box]
check('High Poly of a plate: much denser, closed', len(hp.data.polygons) > nlow * 4 and non_manifold(hp) == 0,
      (nlow, len(hp.data.polygons)))
check('... with the same outline and height (shape kept)', max((a - b).length for a, b in zip(bb_low, bb_hp)) < 0.02)
zh = [v.co.z for v in hp.data.vertices]
check('... and the same crease height', abs(max(zh) - max(v.co.z for v in plate.data.vertices)) < 1e-3)
plate.hide_set(False)
select_only(plate)
bpy.ops.mch.plate_apply()
check('Apply keeps the outline for High Poly later', ap.plate_hp_data(plate) is not None and ap.plate_source(plate) is None)
select_only(plate)
bpy.ops.mch.make_highpoly(plate_detail=12)
hp2 = C.active_object
check('High Poly after Apply: still the dense plate rebuild', len(hp2.data.polygons) > nlow * 3 and non_manifold(hp2) == 0)

# popups stay where they first appeared
from mecha_lab import primitive_hud as ph
class RG:
    width, height = 1000, 800
    def as_pointer(self):
        return 77
rg = RG()
a1 = ph.anchored('t', 'Plate', rg, {'apply': (600, 400), 'end_add': (500, 300)}, follow=('end_add',))
a2 = ph.anchored('t', 'Plate', rg, {'apply': (700, 450), 'end_add': (520, 330)}, follow=('end_add',))
check('popup stays put while the shape changes (glued end buttons still follow)',
      a2['apply'] == (600, 400) and a2['end_add'] == (520, 330))
a3 = ph.anchored('t', 'Other', rg, {'apply': (700, 450)})
ph.release_anchor('t')
a4 = ph.anchored('t', 'Plate', rg, {'apply': (710, 460)})
check('another object, or after the popup closed: placed fresh', a3['apply'] == (700, 450) and a4['apply'] == (710, 460))

# Reset Axis / Origin to Geometry / Origin to 3D Cursor (under the Tool Active button)
cb = cube('Tidy', 2.0, loc=(3, 0, 0))
cb.rotation_euler = (0.3, 0.2, 0.5)
C.view_layer.update()
before = sorted(tuple(round(c, 4) for c in cb.matrix_world @ v.co) for v in cb.data.vertices)
select_only(cb)
bpy.ops.mch.object_tidy(action='RESET_AXIS')
C.view_layer.update()
after = sorted(tuple(round(c, 4) for c in cb.matrix_world @ v.co) for v in cb.data.vertices)
check('Reset Axis: rotation 0, the shape stays in place', tuple(cb.rotation_euler) == (0, 0, 0) and
      max(max(abs(a - b) for a, b in zip(p_, q_)) for p_, q_ in zip(before, after)) < 1e-3)
S.cursor.location = (5, 1, 2)
bpy.ops.mch.object_tidy(action='ORIGIN_CURSOR')
check('Origin to 3D Cursor', (cb.location - Vector((5, 1, 2))).length < 1e-5)
bpy.ops.mch.object_tidy(action='ORIGIN_GEOMETRY')
check('Origin to Geometry: back to the middle of the box', (cb.location - Vector((3, 0, 0))).length < 1e-4, tuple(cb.location))
pos = bb.tidy_positions(fake)
check('three buttons stacked under the Tool Active button', len(pos) == 3 and all(abs(x - bx) < 1e-6 for x, _y in pos)
      and by > pos[0][1] > pos[1][1] > pos[2][1])
bpy.data.objects.remove(cb)

# narrow neck / sharp notch with a huge chamfer + bevel (Soft Cloth on a face): no crumpled faces
def flipped_top(ob, h):
    me = ob.data
    bad = tot = 0
    for f in me.polygons:
        zs_ = [me.vertices[i].co.z for i in f.vertices]
        if min(zs_) > 2.0 + h * 0.3:
            tot += 1
            if f.normal.z < -0.05:
                bad += 1
    return bad, tot


for o in [o for o in bpy.data.objects if o is not box]:
    bpy.data.objects.remove(o)
select_only(box)
S.mch_plate.preset = 'CLOTH'
U = [(250, 300), (750, 300), (750, 700), (650, 700), (650, 400), (560, 400), (520, 650), (470, 400), (350, 400),
     (350, 700), (250, 700)]
r, msg = lasso(U)
pu = C.active_object
pu.mch_extract.bevel_width = 0.45
pu.mch_extract.chamfer_width = 0.45
pu.mch_extract.extract_height = 0.6
bad, tot = flipped_top(pu, 0.6)
check('narrow U + sharp notch with a huge bevel / chamfer: no crumpled (flipped) top faces',
      r == {'FINISHED'} and tot > 0 and bad == 0 and non_manifold(pu) == 0, (bad, tot, pu.mch_extract.notes))
check('... the report says where the edge band was narrowed', 'narrowed' in pu.mch_extract.notes, pu.mch_extract.notes)

# outline past a cylinder silhouette: no spikes
fresh()
mecha_lab.register()
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
S.mch_settings.mch_active_tool = 'PLATE'
VIEW[0] = cg.OrthoProjector(Euler((math.radians(60), 0, math.radians(20))).to_quaternion(), pixels_per_unit=120)
cyl = cylinder('Cyl', segments=32, radius=3.0, depth=4.0)
r, msg = lasso([(560, 391), (736, 449), (727, 967), (586, 939)])
pl = C.active_object
reg = pl.mch_extract.region
o = [VIEW[0].to_screen(pl.matrix_world @ v.co) for v in reg.vertices]
eye_depth = [(pl.matrix_world @ v.co).dot(VIEW[0].view_dir) for v in reg.vertices]
me = cyl.data
bvh = BVHTree.FromPolygons([v.co for v in me.vertices], [tuple(q.vertices) for q in me.polygons])
hits = [bvh.find_nearest(v.co)[3] for v in reg.vertices]
check('outline partly past the cylinder: a plate, report says so', r == {'FINISHED'} and 'past the surface' in msg, msg)
ppu = VIEW[0].ppu
slope = 0.0
for e in reg.edges:
    a, b = e.vertices
    ds = math.dist(o[a], o[b]) / ppu
    if ds > 1e-6:
        slope = max(slope, abs(eye_depth[a] - eye_depth[b]) / ds)
check("points past the edge: no spike (no steep jump in depth between neighbours)", slope < 2.5, slope)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
