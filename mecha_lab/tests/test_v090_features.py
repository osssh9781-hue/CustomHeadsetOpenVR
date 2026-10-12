"""v0.9.0: Mesh Curve fix + controls, SubD Plane, Radial rotation, Gap Split,
per-side split bevel, 2D outline corner preview (headless, simulated events)."""
import math
import sys
import types

from _harness import bpy, bmesh, check, cube, fresh, mesh_obj, non_manifold, select_only, summary, volume
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce, radial_array as ra, subd_plane as sp

C = bpy.context
TOP = cg.OrthoProjector(Quaternion())


def call(op, **kw):
    try:
        return op(**kw)
    except RuntimeError as ex:
        print('  (operator reported)', str(ex).splitlines()[0])
        return {'CANCELLED'}


def evaluated(ob):
    dg = C.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    co = [ob.matrix_world @ v.co for v in me.vertices]
    nf = len(me.polygons)
    ev.to_mesh_clear()
    return co, nf


mecha_lab.register()

# =============================================================================
# 1. Mesh Curve drawing logic (simulated events, real PathDrawLogic)
# =============================================================================
mecha_lab._path_ray = lambda region, rv3d, xy: TOP.ray(xy)
mecha_lab._path_to_screen = lambda region, rv3d, co: TOP.to_screen(co)


class Region:
    type = 'WINDOW'
    x = y = 0
    width = height = 1000


class PathOp(mecha_lab.PathDrawLogic):
    def __init__(self, kind='CURVE'):
        self.kind = kind
        self.reports = []

    def report(self, kind, msg):
        self.reports.append(msg)


class _PathCtx:
    """Fake context: viewport bits are fakes, everything else is the real bpy.context."""

    def __init__(self):
        region = Region()
        rv3d = types.SimpleNamespace(view_rotation=Quaternion())
        self.area = types.SimpleNamespace(type='VIEW_3D', regions=[region], header_text_set=lambda t: None)
        self.space_data = types.SimpleNamespace(region_3d=rv3d)
        self.window = None
        self.window_manager = types.SimpleNamespace(modal_handler_add=lambda op: None)

    def __getattr__(self, name):
        return getattr(C, name)


def path_ctx():
    return _PathCtx()


def E(t, v='PRESS', x=500, y=500, shift=False):
    return types.SimpleNamespace(type=t, value=v, mouse_x=x, mouse_y=y, shift=shift, alt=False, ctrl=False)


def types_of(op):
    return [bp.handle_left_type for bp in list(op._bpoints())[:op._points]]


fresh()
C.scene.mch_settings.path_draw_mode = 'POLY'
C.scene.mch_settings.path_point_type = 'VECTOR'
C.scene.mch_settings.profile_shape = 'ROUND'
ctx = path_ctx()
op = PathOp('CURVE')
check('mesh curve draw starts', op.invoke(ctx, E('LEFTMOUSE')) == {'RUNNING_MODAL'})
for x, y in ((400, 400), (500, 600), (600, 400), (700, 600)):
    op.modal(ctx, E('LEFTMOUSE', 'PRESS', x, y))
    op.modal(ctx, E('LEFTMOUSE', 'RELEASE', x, y))
check('polyline points are Straight (VECTOR) by default', types_of(op) == ['VECTOR'] * 4, types_of(op))
op.modal(ctx, E('LEFTMOUSE', 'PRESS', 500, 600))          # click an existing point
check('clicking an existing point makes it Smooth (no new point)', op._points == 4 and types_of(op)[1] == 'AUTO')
op.modal(ctx, E('LEFTMOUSE', 'DOUBLE_CLICK', 700, 600))   # double-click a point
check('double-clicking a point toggles it Smooth', types_of(op)[3] == 'AUTO' and op._points == 4)
op.modal(ctx, E('LEFTMOUSE', 'PRESS', 500, 600))
check('clicking again toggles back to Straight', types_of(op)[1] == 'VECTOR')
op.modal(ctx, E('S'))
op.modal(ctx, E('LEFTMOUSE', 'PRESS', 800, 400))
check('S switches new points to Smooth', types_of(op)[-1] == 'AUTO' and op._points == 5)
op.modal(ctx, E('BACK_SPACE'))
check('Backspace keeps the remaining point types', op._points == 4 and types_of(op)[3] == 'AUTO')
r = op.modal(ctx, E('RET'))
carrier = next((o for o in bpy.data.objects if o.get('mch_role') == 'CURVE'), None)
check('Enter creates the live Mesh Curve', r == {'FINISHED'} and carrier is not None, op.reports)
nodes = carrier.modifiers[0].node_group.nodes
check('new live nodes present (twist, profile rotation)', nodes.get('MCH_TWIST') and nodes.get('MCH_PROFILE_ROT'))

# Free draw -> smooth handles
fresh()
C.scene.mch_settings.path_draw_mode = 'FREE'
C.scene.mch_settings.path_sample_px = 10
ctx = path_ctx()
op = PathOp('CURVE')
op.invoke(ctx, E('LEFTMOUSE'))
op.modal(ctx, E('LEFTMOUSE', 'PRESS', 300, 500))
for k in range(1, 40):
    op.modal(ctx, E('MOUSEMOVE', 'NOTHING', 300 + 10 * k, 500 + 80 * math.sin(k / 6)))
op.modal(ctx, E('LEFTMOUSE', 'RELEASE', 690, 500))
check('free draw samples many points', op._points > 20, op._points)
check('free draw points are Smooth (AUTO), not straight', set(types_of(op)) == {'AUTO'}, set(types_of(op)))
C.scene.mch_settings.path_draw_mode = 'POLY'

# =============================================================================
# 2. Mesh Curve live controls (sweep)
# =============================================================================
fresh()
cu = bpy.data.curves.new('P', 'CURVE')
cu.dimensions = '3D'
spl = cu.splines.new('BEZIER')
spl.bezier_points.add(2)
for bp, co in zip(spl.bezier_points, [(0, 0, 0), (1, 1, 0), (2, 0, 0)]):
    bp.co = co
    bp.handle_left_type = bp.handle_right_type = 'VECTOR'
path = bpy.data.objects.new('P', cu)
C.scene.collection.objects.link(path)
path['mch_path'] = True
C.scene.mch_settings.profile_shape = 'ROUND'
car = mecha_lab.make_live(C, path, 'CURVE')
co_straight, _ = evaluated(car)
centre_x1 = [v for v in co_straight if abs(v.x - 1.0) < 0.05]
select_only(car)
r = call(bpy.ops.mch.path_handles_all, kind='AUTO')
co_smooth, _ = evaluated(car)
check('All Smooth works in Object Mode', r == {'FINISHED'} and all(bp.handle_left_type == 'AUTO' for bp in spl.bezier_points))
# With AUTO handles the sweep rounds the corner at (1,1): the peak drops below 1
near_mid_straight = [v for v in co_straight if 0.3 < v.x < 0.7]
near_mid_smooth = [v for v in co_smooth if abs(v.x - 0.5) < 0.04]
h_smooth = sum(v.y for v in near_mid_smooth) / max(1, len(near_mid_smooth))
check('straight (VECTOR) segments have no in-between rows', not near_mid_straight)
check('smooth points really curve the sweep (bulges above the straight segment y=0.5)',
      len(co_smooth) > len(co_straight) and near_mid_smooth and h_smooth > 0.55, h_smooth)
car.mch_live.resolution = 4
n4 = len(evaluated(car)[0])
car.mch_live.resolution = 32
n32 = len(evaluated(car)[0])
check('Curve Resolution controls the sweep density', n32 > n4 and cu.resolution_u == 32, (n4, n32))
car.mch_live.profile_segments = 6
n6 = len(evaluated(car)[0])
car.mch_live.profile_segments = 24
check('Profile Segments controls the round section', len(evaluated(car)[0]) == n6 * 4)
car.mch_live.shape = 'RECT'
base, _ = evaluated(car)
car.mch_live.rot_z = math.radians(45)
check('Rotation Z rotates the cross-section', max((a - b).length for a, b in zip(base, evaluated(car)[0])) > 0.005)
car.mch_live.rot_z = 0.0
car.mch_live.rot_x = math.radians(90)
check('Rotation X rotates the cross-section', max((a - b).length for a, b in zip(base, evaluated(car)[0])) > 0.005)
car.mch_live.rot_x = 0.0
car.mch_live.twist = math.pi
tw, _ = evaluated(car)
start_same = (tw[0] - base[0]).length < 1e-4
check('Twist turns the section along the path (start fixed, rest rotated)',
      start_same and max((a - b).length for a, b in zip(base, tw)) > 0.005)
# Live object made before v0.9 (no new nodes) is upgraded on first edit
grp = car.modifiers[0].node_group
grp.nodes.remove(grp.nodes['MCH_TWIST'])
car.mch_live.twist = 0.5
check('old live curve is rebuilt with the new nodes', car.modifiers[0].node_group.nodes.get('MCH_TWIST') is not None)
select_only(car)
check('bake still works', call(bpy.ops.mch.bake_live) == {'FINISHED'} and not car.modifiers)

# Curve array: rotation + twist of placed copies
fresh()
src = cube('Bolt', size=0.1)
src.scale = (3, 1, 1)
C.view_layer.update()
cu = bpy.data.curves.new('A', 'CURVE')
cu.dimensions = '3D'
spl = cu.splines.new('BEZIER')
spl.bezier_points.add(1)
spl.bezier_points[0].co = (0, 0, 0)
spl.bezier_points[1].co = (3, 0, 0)
for bp in spl.bezier_points:
    bp.handle_left_type = bp.handle_right_type = 'VECTOR'
apath = bpy.data.objects.new('A', cu)
C.scene.collection.objects.link(apath)
C.scene.mch_settings.array_spacing = 0.5
arr = mecha_lab.make_live(C, apath, 'ARRAY', source=src)
arr.modifiers[0].node_group.nodes['MCH_ARRAY_BAKE_SWITCH'].inputs['Switch'].default_value = True   # realize to inspect
a0, _ = evaluated(arr)
arr.mch_live.rot_z = math.radians(90)
a1, _ = evaluated(arr)
check('array Rotation Z turns every copy', len(a0) == len(a1) and max((p - q).length for p, q in zip(a0, a1)) > 0.05)
arr.mch_live.rot_z = 0.0
arr.mch_live.twist = math.pi
a2, _ = evaluated(arr)
check('array Twist changes copy orientation along the path', max((p - q).length for p, q in zip(a0, a2)) > 0.01)

kc = C.window_manager.keyconfigs.addon
dbl = [ki for km in kc.keymaps if km.name == 'Curve' for ki in km.keymap_items if ki.idname == 'mch.double_click_point']
check('Curve Edit Mode double-click keymap is ACTIVE (was inactive since v0.5.9)', dbl and all(k.active for k in dbl))

# =============================================================================
# 3. SubD Plane
# =============================================================================
fresh()
r = call(bpy.ops.mch.subd_plane_create)
pl = C.view_layer.objects.active
mods = [(m.name, m.type, getattr(m, 'subdivision_type', None)) for m in pl.modifiers]
check('SubD Plane created with Simple -> Catmull-Clark -> Solidify', r == {'FINISHED'} and mods == [
    (sp.MOD_SIMPLE, 'SUBSURF', 'SIMPLE'), (sp.MOD_CC, 'SUBSURF', 'CATMULL_CLARK'), (sp.MOD_SOLID, 'SOLIDIFY', None)], mods)
p = pl.mch_subd
p.simple_levels, p.cc_levels = 0, 0
_, f00 = evaluated(pl)
p.simple_levels = 2
_, f20 = evaluated(pl)
p.cc_levels = 3
_, f23 = evaluated(pl)
check('Simple and Catmull-Clark act together (independent sliders)', f00 < f20 < f23, (f00, f20, f23))
check('both levels written to their own modifier', pl.modifiers[sp.MOD_SIMPLE].levels == 2 and
      pl.modifiers[sp.MOD_CC].levels == 3)
check('levels limited to 0..5', type(p).bl_rna.properties['simple_levels'].hard_max == 5 and
      type(p).bl_rna.properties['cc_levels'].hard_max == 5)
p.thickness, p.offset = 0.1, 0.0
check('Solidify thickness/offset live', abs(pl.modifiers[sp.MOD_SOLID].thickness - 0.1) < 1e-6 and
      pl.modifiers[sp.MOD_SOLID].offset == 0.0)
check('modifiers visible in Edit Mode', all(m.show_in_editmode for m in pl.modifiers))
# Edit-mode modelling + crease
bpy.ops.object.mode_set(mode='EDIT')
bmx = bmesh.from_edit_mesh(pl.data)
bmx.edges.ensure_lookup_table()
for e in bmx.edges:
    e.select = False
bmx.edges[0].select = True
bmesh.ops.extrude_edge_only(bmx, edges=[bmx.edges[1]])
bmesh.update_edit_mesh(pl.data)
C.scene.mch_subd.crease_value = 0.8
r = call(bpy.ops.mch.subd_set_crease)
bpy.ops.object.mode_set(mode='OBJECT')
cre = pl.data.attributes.get('crease_edge')
check('edges can be extruded in Edit Mode, crease written to selected edges',
      r == {'FINISHED'} and len(pl.data.vertices) == 6 and cre and abs(max(d.value for d in cre.data) - 0.8) < 1e-6)
_, before_apply = evaluated(pl)
select_only(pl)
r = call(bpy.ops.mch.subd_apply_all)
check('Apply All bakes the stack in order', r == {'FINISHED'} and not pl.modifiers and len(pl.data.polygons) == before_apply,
      (len(pl.data.polygons), before_apply))
fresh()
cb = cube('Hull')
select_only(cb)
check('SubD stack can be added to an existing mesh', call(bpy.ops.mch.subd_adopt) == {'FINISHED'} and len(cb.modifiers) == 3)

# =============================================================================
# 4. Radial Array rotation controls
# =============================================================================


def edge_dirs(me_or_ob):
    me = me_or_ob.data if hasattr(me_or_ob, 'data') else me_or_ob
    out = set()
    for e in me.edges:
        d = me.vertices[e.vertices[1]].co - me.vertices[e.vertices[0]].co
        if d.length > 1e-6:
            d.normalize()
            if d.x < -1e-6 or (abs(d.x) < 1e-6 and (d.y < -1e-6 or (abs(d.y) < 1e-6 and d.z < 0))):
                d = -d
            out.add(tuple(round(c, 3) for c in d))
    return out


def make_radial(**props):
    fresh()
    C.scene.cursor.location = (0, 0, 0)
    s = cube('Tread', size=0.2, loc=(1.0, 0, 0))
    s.scale = (2, 0.5, 0.5)
    C.view_layer.update()
    select_only(s)
    C.scene.mch_settings.radial_count = 6
    call(bpy.ops.mch.radial_create)
    car = C.view_layer.objects.active
    for k, v in props.items():
        setattr(car.mch_radial, k, v)
    if car.modifiers[0].node_group.nodes.get('MCH_Radial_CopyRot') is None:
        car.mch_radial.copy_rot_x = car.mch_radial.copy_rot_x      # force upgrade
    car.modifiers[0].node_group.nodes['MCH_Radial_BakeSwitch'].inputs['Switch'].default_value = True
    return car


check('Rotate Each Copy defaults OFF (scene and object)', C.scene.mch_settings.bl_rna.properties['radial_follow'].default is False
      and ra.MCH_PG_Radial.bl_rna.properties['follow_circle'].default is False)
car = make_radial()
co, _ = evaluated(car)
check('copies keep the source orientation when Rotate Each Copy is OFF', car.mch_radial.follow_circle is False and
      len(co) == 48)
bm_dirs = set()
dg = C.evaluated_depsgraph_get()
me = car.evaluated_get(dg).to_mesh()
bm_dirs = edge_dirs(me)
car.evaluated_get(dg).to_mesh_clear()
check('OFF: all copies share the source axes (no tilt)', bm_dirs <= {(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)}, bm_dirs)
car.mch_radial.follow_circle = True
dg = C.evaluated_depsgraph_get()
me = car.evaluated_get(dg).to_mesh()
on_dirs = edge_dirs(me)
car.evaluated_get(dg).to_mesh_clear()
check('ON: copies turn along the ring (more edge directions)', len(on_dirs) > 3, len(on_dirs))
car = make_radial(ring_rot_x=math.radians(90))
co, _ = evaluated(car)
ys = [v.y for v in co]
zs = [v.z for v in co]
check('Ring Rotation X tilts the whole ring into the XZ plane', max(ys) - min(ys) < 0.3 and max(zs) - min(zs) > 1.5,
      (max(ys) - min(ys), max(zs) - min(zs)))
car = make_radial(copy_rot_z=math.radians(90))
dg = C.evaluated_depsgraph_get()
me = car.evaluated_get(dg).to_mesh()
longest = max((me.vertices[e.vertices[1]].co - me.vertices[e.vertices[0]].co for e in me.edges), key=lambda d: d.length)
car.evaluated_get(dg).to_mesh_clear()
check('Copy Rotation Z turns each copy in place (long axis now Y)', abs(longest.y) > abs(longest.x), longest)
car = make_radial(phase=math.radians(30))
co, _ = evaluated(car)
ang = math.degrees(math.atan2(sum(v.y for v in co[:8]) / 8, sum(v.x for v in co[:8]) / 8))
check('Start Angle moves the first copy', abs(ang - 30) < 1.0, ang)
grp = car.modifiers[0].node_group
grp.nodes.remove(grp.nodes['MCH_Radial_CopyRot'])
car.mch_radial.copy_rot_x = 0.1
check('old radial arrays are upgraded with rotation nodes', car.modifiers[0].node_group.nodes.get('MCH_Radial_CopyRot') is not None)
select_only(car)
check('radial bake still works', call(bpy.ops.mch.radial_bake) == {'FINISHED'} and len(car.data.vertices) == 48)

# =============================================================================
# 5. Gap Split + per-side bevel
# =============================================================================
SQUARE = [(450, 450), (550, 450), (550, 550), (450, 550)]


def split_reset():
    fresh()
    c = C.scene.mch_cut
    c.split_mode, c.gap_width, c.split_cap = 'NORMAL', 0.2, True
    c.side_a_finish = c.side_b_finish = 'NONE'
    c.side_a_width = c.side_b_width = 0.03
    C.scene.mch_settings.auto_apply = True
    c.depth_mode = 'THROUGH'
    t = cube('Target')
    select_only(t)
    return t


t = split_reset()
ce.perform_closed(C, 'SPLIT', [t], [SQUARE], TOP)
pc = bpy.data.objects['Target_Split']
check('Normal Split unchanged (volumes 6 + 2)', abs(volume(t) - 6) < 1e-4 and abs(volume(pc) - 2) < 1e-4)
t = split_reset()
C.scene.mch_cut.split_mode = 'GAP'
msg = ce.perform_closed(C, 'SPLIT', [t], [SQUARE], TOP)
pc = bpy.data.objects['Target_Split']
check('Gap Split removes a strip of Gap Width (piece 0.8², hole 1.2²)', abs(volume(pc) - 0.8 * 0.8 * 2) < 1e-3 and
      abs(volume(t) - (8 - 1.2 * 1.2 * 2)) < 1e-3, (volume(t), volume(pc), msg))
check('Gap Split parts are separate closed objects', non_manifold(t) == 0 and non_manifold(pc) == 0 and t != pc)
xs = [v.co.x for v in pc.data.vertices]
check('gap stays centred on the drawn outline', abs((max(xs) + min(xs)) / 2) < 1e-4 and abs(max(xs) - 0.4) < 1e-4)
t = split_reset()
C.scene.mch_cut.split_mode = 'GAP'
ce.perform_line(C, 'SPLIT', [t], [(500, 300), (500, 700)], TOP, side_xy=(500, 300))
pc = bpy.data.objects['Target_Split']
a_x = max(v.co.x for v in t.data.vertices)
b_x = min(v.co.x for v in pc.data.vertices)
check('straight Gap Split: two halves 0.2 apart, centred', abs(b_x - a_x - 0.2) < 1e-4 and abs(a_x + b_x) < 1e-4, (a_x, b_x))
check('straight Gap Split capped', non_manifold(t) == 0 and non_manifold(pc) == 0 and abs(volume(t) - 3.6) < 1e-4)
t = split_reset()
C.scene.mch_cut.split_mode = 'GAP'
ce.perform_line(C, 'SPLIT', [t], [(450, 300), (530, 500), (450, 700)], TOP, side_xy=(300, 500))
check('polyline Gap Split works', 'Target_Split' in bpy.data.objects and non_manifold(t) == 0)
t = split_reset()
C.scene.mch_cut.split_mode = 'GAP'
ce.perform_closed(C, 'SPLIT', [t], [ce.circle_loop((500, 500), (560, 500), 64)], TOP)
check('curved (circle) Gap Split closed', non_manifold(t) == 0 and non_manifold(bpy.data.objects['Target_Split']) == 0)
t = split_reset()
C.scene.mch_cut.split_mode = 'GAP'
C.scene.mch_cut.split_cap = False
ce.perform_closed(C, 'SPLIT', [t], [SQUARE], TOP)
check('Gap Split with Cap OFF leaves open shells', non_manifold(t) > 0)
t = split_reset()
C.scene.mch_cut.split_mode = 'GAP'
C.scene.mch_cut.gap_width = 1.5
v0 = len(t.data.vertices)
try:
    ce.perform_closed(C, 'SPLIT', [t], [SQUARE], TOP)
    check('too wide gap refused', False)
except cg.CutError as ex:
    check('too wide gap refused, mesh unchanged', len(t.data.vertices) == v0, ex)
t = split_reset()
C.scene.mch_cut.split_mode = 'GAP'
C.scene.mch_settings.auto_apply = False
try:
    ce.perform_closed(C, 'SPLIT', [t], [SQUARE], TOP)
    check('gap + live refused', False)
except cg.CutError as ex:
    check('Gap Split with Auto Apply OFF refused with message', 'Auto Apply' in str(ex))


def corners_intact(ob):
    co = {tuple(round(c, 5) for c in v.co) for v in ob.data.vertices}
    return {(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)} <= co


for mode in ('NORMAL', 'GAP'):
    t = split_reset()
    C.scene.mch_cut.split_mode = mode
    ce.perform_closed(C, 'SPLIT', [t], [SQUARE], TOP)
    plain_a, plain_b = len(t.data.polygons), len(bpy.data.objects['Target_Split'].data.polygons)
    t = split_reset()
    C.scene.mch_cut.split_mode = mode
    C.scene.mch_cut.side_a_finish = 'BEVEL'
    msg = ce.perform_closed(C, 'SPLIT', [t], [SQUARE], TOP)
    b = bpy.data.objects['Target_Split']
    check(f'{mode}: Side A bevel only (A rounded, B sharp)', len(t.data.polygons) > plain_a and
          len(b.data.polygons) == plain_b, (len(t.data.polygons), plain_a, len(b.data.polygons), plain_b, msg))
    check(f'{mode}: original cube corners untouched by the side bevel', corners_intact(t) and non_manifold(t) == 0)
t = split_reset()
C.scene.mch_cut.side_a_finish, C.scene.mch_cut.side_b_finish = 'BEVEL', 'CHAMFER'
C.scene.mch_cut.side_a_segments = 5
r = call(bpy.ops.mch.split_swap_sides)
c = C.scene.mch_cut
check('Swap Sides exchanges A/B settings', r == {'FINISHED'} and c.side_a_finish == 'CHAMFER' and
      c.side_b_finish == 'BEVEL' and c.side_b_segments == 5)
t = split_reset()
C.scene.mch_cut.side_b_finish = 'CHAMFER'
ce.perform_line(C, 'SPLIT', [t], [(500, 300), (500, 700)], TOP, side_xy=(500, 300))
b = bpy.data.objects['Target_Split']
check('plane split: Side B chamfered, Side A plain', len(b.data.polygons) > len(t.data.polygons))
t = split_reset()
C.scene.mch_cut.edge_finish = 'BEVEL'
C.scene.mch_cut.finish_width = 0.05
ce.perform_closed(C, 'CUT', [t], [SQUARE], TOP)
check('Cut Edge Finish unchanged by the Split side settings', len(t.data.polygons) > 12 and corners_intact(t))
C.scene.mch_cut.edge_finish = 'NONE'

# =============================================================================
# 6. 2D outline corners: Sharp / Chamfer / Round, width, segments, live preview
# =============================================================================
loop = [(400, 400), (600, 400), (600, 600), (400, 600)]
check('Sharp keeps the outline', ce.round_corners(loop, 20, 'NONE', 6) == loop)
ch = ce.round_corners(loop, 20, 'CHAMFER', 6)
check('Chamfer: two points per corner, cut back by Corner Width', len(ch) == 8 and
      abs(math.dist(ch[0], (400, 400)) - 20) < 1e-6)
rd6 = ce.round_corners(loop, 20, 'ROUND', 6)
rd12 = ce.round_corners(loop, 20, 'ROUND', 12)
check('Round: Corner Segments controls the arc', len(rd6) == 4 * 7 and len(rd12) == 4 * 13)
check('Corner Width controls the size', min(math.dist(p, (400, 400)) for p in ce.round_corners(loop, 40, 'ROUND', 6)) >
      min(math.dist(p, (400, 400)) for p in rd6))
tri = [(400, 400), (600, 400), (500, 420)]       # very sharp corner: width clamped to 45% of the edges
check('width is clamped on short edges (no overlap)', not cg.find_intersections([ce.round_corners(tri, 200, 'ROUND', 6)]))

# Live preview while drawing (real StrokeLogic with fake events)
ce.make_projector = lambda region, rv3d: TOP
ce.add_draw_handler = lambda op: 'h'
ce.remove_draw_handler = lambda h: None


class SRegion:
    type = 'WINDOW'
    x = y = 0
    width = height = 1000

    def tag_redraw(self):
        pass


def stroke_ctx():
    region = SRegion()
    tools = types.SimpleNamespace(from_space_view3d_mode=lambda m, create=False: types.SimpleNamespace(idname='mecha.cut'))
    return types.SimpleNamespace(
        region=region, area=types.SimpleNamespace(type='VIEW_3D', regions=[region], as_pointer=lambda: 7),
        region_data=object(), space_data=None, mode='OBJECT', preferences=C.preferences,
        window=types.SimpleNamespace(as_pointer=lambda: 8), scene=C.scene, view_layer=C.view_layer,
        selected_objects=C.selected_objects, collection=C.scene.collection,
        evaluated_depsgraph_get=C.evaluated_depsgraph_get,
        window_manager=types.SimpleNamespace(modal_handler_add=lambda op: None, event_timer_add=lambda *a, **k: object(),
                                             event_timer_remove=lambda t: None),
        workspace=types.SimpleNamespace(tools=tools, status_text_set=lambda t: None))


class SOp(ce.StrokeLogic):
    mode = 'CUT'

    def report(self, kind, msg):
        pass


def SE(t, v='PRESS', x=500, y=500):
    return types.SimpleNamespace(type=t, value=v, mouse_x=x, mouse_y=y, alt=False, shift=False, ctrl=False, oskey=False)


fresh()
t = cube('Target')
select_only(t)
b = C.scene.mch_brush
b.shape = 'LASSO'
for mode, expect in (('NONE', 3), ('CHAMFER', 6), ('ROUND', 3 * (b.outline_segments + 1))):
    b.outline_corner = mode
    b.outline_radius = 15
    sctx, sop = stroke_ctx(), SOp()
    ce._TRIPLE_STATE.clear()
    sop.invoke(sctx, SE('LEFTMOUSE', 'PRESS', 420, 420))
    sop.modal(sctx, SE('LEFTMOUSE', 'RELEASE', 420, 420))
    sop.modal(sctx, SE('LEFTMOUSE', 'PRESS', 580, 430))
    sop.modal(sctx, SE('LEFTMOUSE', 'RELEASE', 580, 430))
    sop.modal(sctx, SE('MOUSEMOVE', 'NOTHING', 520, 580))   # rubber-band point
    preview = sop.preview_loops()[0]
    check(f'live preview while drawing Lasso: {mode} corners ({expect} pts)', len(preview) == expect, len(preview))
    sop.modal(sctx, SE('ESC'))
b.shape = 'RECT'
b.outline_corner = 'ROUND'
sctx, sop = stroke_ctx(), SOp()
ce._TRIPLE_STATE.clear()
sop.invoke(sctx, SE('LEFTMOUSE', 'PRESS', 420, 420))
sop.modal(sctx, SE('MOUSEMOVE', 'NOTHING', 580, 560))
check('live preview while dragging a Rectangle shows rounded corners',
      len(sop.preview_loops()[0]) == 4 * (b.outline_segments + 1))
r = sop.modal(sctx, SE('LEFTMOUSE', 'RELEASE', 580, 560))
check('rounded-corner rectangle cut applied, closed', r == {'FINISHED'} and non_manifold(t) == 0 and volume(t) < 8)
b.outline_corner = 'NONE'

mecha_lab.unregister()
sys.exit(1 if summary() else 0)
