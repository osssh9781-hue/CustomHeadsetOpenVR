"""0.24.95 Lasso Zone tool (user: "라쏘도 컷이나 이런 거처럼 위에 막대에 옵션 다 넣어 줘 - 스케치랑 라인 이런 거 다"):
the zones drawn with the shared lasso of the drawing tools (cut_engine), so every top-bar option works for them.

* the tool: hidden from the tool list (the Mech / Creature page's Paint Zone / Split Zone switch it on), a shape tool,
  Line, Sketch, Surface, Targets, Slow Line - the top bar shows Shape, Corners, Zone [Paint][Split], Draw, Surface,
  Target (no Open Line: a zone needs an area)
* through the real stroke logic (an orthographic view from above): clicked Lasso -> a Paint Zone where it was drawn;
  Corners Round -> the corners rounded off; Line -> a stripe zone (Line Width); Sketch: an outline minus a smaller one
  + Enter -> one zone with a hole (rendered: the hole the part's paint, the ring the zone's); Split + Sketch of two
  islands -> one zone material on the faces of both
* the zone goes on the part under the outline (the active one when covered, else the other zoned part - it becomes
  the active one); over no part / Split on a creature: refused, nothing made
* any lasso view: a Sketch's frozen view, the test view - the zone's projection the same as the view's
* the Mech page buttons switch the tool on (Paint / Split)"""
import math
import types

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Matrix, Quaternion, Vector

import mecha_lab
from mecha_lab import (armor_plate as ap, core_geometry as cg, cut_engine as ce, lasso_line, lasso_sketch as ls,
                       mech_shader_ui as mu, surface_lasso, target_rules, tool_state as ts, top_bar, workspace_ui as wui,
                       zones as zn)

VIEW = [cg.OrthoProjector(Quaternion())]          # (from above: px (500, 500) = world (0, 0), 100 px per unit)
ce.make_projector = lambda region, rv3d: VIEW[0]
ce.add_draw_handler = lambda op: 'handle'
ce.remove_draw_handler = lambda h: None
ce.open_popup = lambda name: None
ce.exit_tool = lambda context: None
NATIVE = ['mecha.lasso_zone']


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
        self.workspace = types.SimpleNamespace(tools=tools, status_text_set=lambda text: None,
                                               get=lambda k, d=None: d)

    scene = property(lambda self: bpy.context.scene)
    view_layer = property(lambda self: bpy.context.view_layer)
    selected_objects = property(lambda self: bpy.context.selected_objects)
    active_object = property(lambda self: bpy.context.view_layer.objects.active)
    collection = property(lambda self: bpy.context.scene.collection)

    def evaluated_depsgraph_get(self):
        return bpy.context.evaluated_depsgraph_get()


def E(type_, value='PRESS', x=500, y=500, alt=False):
    return types.SimpleNamespace(type=type_, value=value, mouse_x=x, mouse_y=y, mouse_region_x=x, mouse_region_y=y,
                                 alt=alt, shift=False, ctrl=False, oskey=False)


class Op(ce.StrokeLogic):
    def __init__(self):
        self.mode = 'ZONE'
        self.reports = []

    def report(self, kind, msg):
        self.reports.append((tuple(kind), msg))


def lasso(points, alt=False):
    """Clicked corners + Enter, through the real stroke logic."""
    ctx, op = Ctx(), Op()
    op.invoke(ctx, E('LEFTMOUSE', 'PRESS', *points[0], alt=alt))
    op.modal(ctx, E('LEFTMOUSE', 'RELEASE', *points[0], alt=alt))
    for x, y in points[1:]:
        op.modal(ctx, E('LEFTMOUSE', 'PRESS', x, y, alt=alt))
        op.modal(ctx, E('LEFTMOUSE', 'RELEASE', x, y, alt=alt))
    r = op.modal(ctx, E('RET', alt=alt))
    return r, (op.reports[-1][1] if op.reports else '')


def square(c, r):
    return [(c[0] - r, c[1] - r), (c[0] + r, c[1] - r), (c[0] + r, c[1] + r), (c[0] - r, c[1] + r)]


def mask_at(z, x, y):
    """The zone's mask (0..1, 0.5 on the outline) at view pixel (x, y)."""
    img = z.mask
    w, h = img.size
    a = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(a)
    a = a.reshape(h, w, 4)
    return float(a[int(y * h / 1000.0), int(x * w / 1000.0), 0])


def select(*obs):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]


fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
br = S.mch_brush

# ---- the tool
check('The Lasso Zone tool: a shape tool with Line, Sketch, Surface, Targets (Slow Line); hidden from the tool list '
      '(the Mech / Creature page switches it on); its own Blender tool',
      'ZONE' in ts.TOOL_BY_ID and 'ZONE' in ts.HIDDEN_TOOLS and 'ZONE' in ts.SHAPE_TOOLS and 'ZONE' in lasso_line.MODES
      and 'ZONE' in ls.MODES and 'ZONE' in surface_lasso.MODES and 'ZONE' in target_rules.PICKING
      and wui.MCH_TOOL_lasso_zone in wui.NATIVE_TOOLS and ts.TOOL_BY_ID['ZONE'][5] == 'mecha.lasso_zone'
      and any(k[0] == 'mch.lasso_sketch_key' for k in wui._tool_keymap('ZONE')))
br.shape = 'LASSO'
gs = top_bar.groups(Ctx(), 'ZONE')
heads = {g[0]: [c['label'] for c in g[1]] for g in gs}
flat = [c['label'] for g in gs for c in g[1]]
check('... its top bar: Shape (7), Lasso, Corners (in the same place as every drawing tool), Zone [Paint][Split], '
      'Draw [Line][Sketch][Slow Line], Surface, Target', [g[0] for g in gs][:4] == ['Shape', 'Lasso', 'Corners', 'Zone']
      and len(heads.get('Shape', ())) >= 7 and heads.get('Zone') == ['Paint', 'Split']
      and heads.get('Corners', [])[:3] == ['Sharp', 'Round', 'Chamfer']
      and {'Line', 'Sketch', 'Slow Line'} <= set(heads.get('Draw', ())) and 'Surface' in flat
      and heads.get('Target') == ['Auto', 'Selected', 'Active'], heads)

# ---- a Mech part seen from above (its top at z = 1: px 400 .. 600)
bpy.ops.mesh.primitive_cube_add(size=2.0)
part = C.active_object
part.name = 'Part'
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.subdivide(number_cuts=19)
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.mch.mech_shader_apply(preset='PAINTED')
mat = part.active_material
st = mat.mch_mech
st.edge_wear = st.scratches = st.dirt = st.rust = 0.0
st.paint_color = (0.6, 0.6, 0.6)

S.mch_zone_kind = 'PAINT'
r, msg = lasso(square((500, 500), 60))
zs = mat.mch_zones
check('Clicked Lasso + Enter (the real stroke logic): a Paint Zone where it was drawn (its distance field: inside '
      'over 0.5 - 60 px in 0.81 -, far outside 0, the outline 0.5)', r == {'FINISHED'} and len(zs) == 1
      and abs(mask_at(zs[0], 500, 500) - (0.5 + 60 / 192)) < 0.02 and mask_at(zs[0], 300, 300) < 0.01
      and abs(mask_at(zs[0], 440.5, 500) - 0.5) < 0.03, (r, msg, round(mask_at(zs[0], 500, 500), 3)))
z0 = zs[0]
V, W, persp, rw, rh = zn.view_of(VIEW[0])
p = Vector((0.3, -0.2, 1.0))
ndc = W @ V @ p.to_4d()
want = VIEW[0].to_screen(p)
check('... its projection the view\'s (a point on the top: the same pixel)', not persp and (rw, rh) == (1000, 1000)
      and abs((ndc.x / ndc.w * 0.5 + 0.5) * 1000 - want[0]) < 1e-3 and abs((ndc.y / ndc.w * 0.5 + 0.5) * 1000 - want[1])
      < 1e-3)

br.outline_corner = 'ROUND'
br.outline_radius = 40.0
lasso(square((500, 500), 60))
z1 = zs[1]
check('Corners Round (40 px): the zone\'s corners rounded off (the sharp one\'s corner inside, this one\'s outside), '
      'the sides\' middles the same', mask_at(z0, 444, 444) > 0.5 and mask_at(z1, 444, 444) < 0.5
      and mask_at(z1, 444, 500) > 0.5, (round(mask_at(z0, 444, 444), 2), round(mask_at(z1, 444, 444), 2)))
br.outline_corner = 'NONE'

br.line_mode = True
br.line_width = 0.3                                # (30 px in this view)
br.line_caps = 'FLAT'
lasso([(420, 520), (580, 520)])
z2 = zs[2]
check('Line (Width 0.3 = 30 px): a stripe zone along the clicked line - on it inside (15 px in), 25 px off it '
      'outside (10 px out)', len(zs) == 3 and abs(mask_at(z2, 500, 520) - (0.5 + 15 / 192)) < 0.02
      and abs(mask_at(z2, 500, 545) - (0.5 - 10 / 192)) < 0.02 and mask_at(z2, 500, 495) < 0.5,
      (round(mask_at(z2, 500, 520), 2), round(mask_at(z2, 500, 545), 2)))
br.line_mode = False

br.sketch_first = True
lasso(square((500, 500), 80))
lasso(square((500, 500), 30), alt=True)
check('Sketch: drawing adds outlines (no zone yet), Alt + draw subtracts', len(zs) == 3 and ls.data(S) is not None
      and ls.data(S)['mode'] == 'ZONE' and ls.data(S)['items'][-1]['op'] == 'SUB')
res = bpy.ops.mch.lasso_sketch_commit()
z3 = zs[3] if len(zs) > 3 else None
check('... Enter: one zone - the outline minus the hole (the middle outside: 30 px out; the ring inside: 25 px in; '
      'outside it out), the sketch cleared', res == {'FINISHED'} and z3 is not None
      and abs(mask_at(z3, 500, 500) - (0.5 - 30 / 192)) < 0.02 and abs(mask_at(z3, 445, 500) - (0.5 + 25 / 192)) < 0.02
      and mask_at(z3, 600, 600) < 0.5 and ls.data(S) is None)
br.sketch_first = False
# rendered: the hole the part's paint, the ring the zone's (the other zones hidden)
for z in zs:
    z.opacity = 0.0
z3.opacity = 1.0
z3.color = (0.05, 0.15, 0.7)
z3.line_height = 0.0
cd = bpy.data.cameras.new('Cam')
cd.type = 'ORTHO'
cd.ortho_scale = 2.4
cam = bpy.data.objects.new('Cam', cd)
S.collection.objects.link(cam)
cam.location = (0.0, 0.0, 6.0)
S.camera = cam
w = bpy.data.worlds.new('W')
w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.8, 0.8, 0.8, 1.0)
S.world = w
S.render.engine = 'CYCLES'
S.cycles.samples = 8
S.cycles.use_denoising = False
S.render.resolution_x = S.render.resolution_y = 120
import os
import tempfile
path = os.path.join(tempfile.mkdtemp(), 'r.png')
S.render.filepath = path
bpy.ops.render.render(write_still=True)
img = bpy.data.images.load(path)
px = np.array(img.pixels[:]).reshape(120, 120, 4)[..., :3]
bpy.data.images.remove(img)
mid, ring = px[60, 60], px[60, 60 - int(55 / 100 / 2.4 * 120)]
check('... rendered (from above): the hole the part\'s grey paint, the ring the zone\'s blue',
      abs(mid[0] - mid[2]) < 0.06 and ring[2] > ring[0] * 1.6 and ring[0] < mid[0] * 0.7,
      (np.round(mid, 3).tolist(), np.round(ring, 3).tolist()))

# ---- Split with a Sketch of two islands
S.mch_zone_kind = 'SPLIT'
br.sketch_first = True
lasso(square((450, 450), 25))
lasso(square((555, 555), 25))
res = bpy.ops.mch.lasso_sketch_commit()
br.sketch_first = False
me = part.data
zm = part.material_slots[-1].material if len(part.material_slots) > 1 else None
idx = len(part.material_slots) - 1
inz = [p_.center for p_ in me.polygons if p_.material_index == idx]
from collections import Counter
cnt = Counter(k for p_ in me.polygons for k in p_.edge_keys)
check('Split + a Sketch of two islands: one zone material on the top faces inside both, the mesh still closed',
      res == {'FINISHED'} and zm is not None and zm.mch_zone_parent == mat
      and any(c.x < 0 and c.y < 0 for c in inz) and any(c.x > 0 and c.y > 0 for c in inz)
      and all(abs(c.z - 1.0) < 1e-4 and abs(c.x) < 1.0 and abs(c.y) < 1.0 for c in inz)
      and all(v == 2 for v in cnt.values()), (res, len(inz)))
part.active_material_index = 0

# ---- which part
S.mch_zone_kind = 'PAINT'
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(3.5, 0.0, 0.0))
other = C.active_object
other.name = 'Other'
bpy.ops.mch.mech_shader_apply(preset='PAINTED')
select(part)
n_before = len(other.active_material.mch_zones)
r, msg = lasso(square((850, 500), 40))
check('Drawn over another Mech part (the first one active): the zone goes on that one, which becomes the active part',
      len(other.active_material.mch_zones) == n_before + 1 and C.view_layer.objects.active == other, msg)
nz = len(mat.mch_zones) + len(other.active_material.mch_zones)
r, msg = lasso(square((150, 850), 30))
check('... over no part: refused (a warning), nothing made', len(mat.mch_zones) + len(other.active_material.mch_zones)
      == nz and 'part' in msg.lower(), msg)
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 3.5, 0.0))
crea = C.active_object
bpy.ops.mch.creature_apply(skin='HUMAN', condition='CLEAN')
S.mch_zone_kind = 'SPLIT'
r, msg = lasso(square((500, 850), 40))
check('... Split on a creature: refused (Paint only), the mesh as it was',
      len(crea.material_slots) == 1 and 'creature' in msg.lower(), msg)
S.mch_zone_kind = 'PAINT'
r, msg = lasso(square((500, 850), 40))
check('... Paint on a creature: a marking', len(crea.active_material.mch_zones) == 1, msg)

# ---- a Sketch's frozen view (perspective): the zone's projection the view's
cdp = bpy.data.cameras.new('P')
camp = bpy.data.objects.new('P', cdp)
S.collection.objects.link(camp)
camp.location, camp.rotation_euler = (1.0, -5.0, 2.0), (math.radians(70), 0.0, math.radians(10))
C.view_layer.update()
vm = camp.matrix_world.inverted()
wm = camp.calc_matrix_camera(C.evaluated_depsgraph_get(), x=800, y=600)
eye = camp.matrix_world.translation
fp = ap.FrozenProjector({'pers': [list(r_) for r_ in (wm @ vm)], 'w': 800, 'h': 600, 'persp': True,
                         'eye': list(eye), 'dir': list(camp.matrix_world.to_3x3() @ Vector((0, 0, -1)))})
V, W, persp, rw, rh = zn.view_of(fp)
errs = []
for q in (Vector((0.2, 0.1, 0.9)), Vector((-0.7, 0.5, -0.3)), Vector((1.0, -1.0, 1.0))):
    a, b = W @ V @ q.to_4d(), fp.to_screen(q)
    errs.append(max(abs((a.x / a.w * 0.5 + 0.5) * rw - b[0]), abs((a.y / a.w * 0.5 + 0.5) * rh - b[1])))
d_view = -(V @ Vector((0.0, 0.0, 0.0))).z
check('A Sketch\'s frozen (perspective) view: the zone\'s view + window the same projection, the depth the distance '
      'along the view', persp and (rw, rh) == (800, 600) and max(errs) < 1e-3
      and abs(d_view - (Vector((0, 0, 0)) - eye).dot(camp.matrix_world.to_3x3() @ Vector((0, 0, -1)))) < 1e-4,
      [round(e, 5) for e in errs])
near, far = zn._depth_range(part, Matrix.Translation((0.0, 0.0, -0.0)), persp=False)
check('An orthographic view whose eye sits inside the part: its depth range is not cut at 0', near < 0 < far,
      (round(near, 3), round(far, 3)))

# ---- the Mech page
select(part)
its, _h = mu.content(C, 0.0, 276.0, 1.0)
acts = {i.label: i.action for i in its if i.kind == 'tbtn' and i.label in {'Paint Zone', 'Split Zone'}}
check('The Mech page: Paint Zone / Split Zone switch the Lasso Zone tool on',
      acts.get('Paint Zone') == ('op', 'mch.zone_tool', {'kind': 'PAINT'})
      and acts.get('Split Zone') == ('op', 'mch.zone_tool', {'kind': 'SPLIT'}), acts)
r = bpy.ops.mch.zone_tool(kind='SPLIT')
check('... Split Zone: the tool chosen, drawing Split Zones', r == {'FINISHED'} and S.mch_zone_kind == 'SPLIT'
      and S.mch_settings.mch_active_tool == 'ZONE')
summary()
