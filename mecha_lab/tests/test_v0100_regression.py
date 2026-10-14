"""v0.10 regression / acceptance (docs/04 A + D), headless with simulated events.

B04 double-click anywhere / start click (also when the OS sends no
DOUBLE_CLICK), B05 Mesh Curve single toggle, B06 PNG R rotate, B07 Split Gap
confirm paths, B03 Smart Fuse x10, B01 Mirror matrix, B08 Mask hidden, B10
bevel clamp notes, F01 multi-target + Boolean active = cutter, F02 Base Mesh
Bevel Sides / Alt cutter / session auto apply, Alt invert, Select / Move, V /
Shift+A menus, F08 stabilizer.

Not a GUI test: real Windows event timing still needs the manual checklist.
"""
import math
import random
import sys
import types

from _harness import bpy, bmesh, check, cube, fresh, mesh_obj, non_manifold, select_only, summary, volume
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import (base_mesh, core_geometry as cg, cut_engine as ce, cut_presets, stabilizer,
                       tool_state as ts, workspace_ui as wui)

TOP = cg.OrthoProjector(Quaternion())
CALLS = []
CLOCK = [1000.0]
ce.make_projector = lambda region, rv3d: TOP
ce.add_draw_handler = lambda op: 'handle'
ce.remove_draw_handler = lambda h: None
ce.open_popup = lambda name: CALLS.append(('popup', name))
ce.exit_tool = lambda context: CALLS.append(('exit',))
ce._now = lambda: CLOCK[0]
C = bpy.context


class Region:
    type = 'WINDOW'
    x = y = 0
    width = height = 1000

    def tag_redraw(self):
        pass


class WM:
    def __init__(self):
        self.timers = 0

    def modal_handler_add(self, op):
        pass

    def event_timer_add(self, step, window=None):
        self.timers += 1
        return object()

    def event_timer_remove(self, timer):
        self.timers -= 1


class Ctx:
    def __init__(self, native='mecha.cut'):
        self.region = Region()
        self.area = types.SimpleNamespace(type='VIEW_3D', regions=[self.region], as_pointer=lambda: 2)
        self.region_data = object()
        self.space_data = types.SimpleNamespace(region_3d=self.region_data)
        self.window_manager = WM()
        self.window = types.SimpleNamespace(as_pointer=lambda: 1)
        self.mode = 'OBJECT'
        self.preferences = bpy.context.preferences
        self.native = native
        ctx = self

        class Tools:
            def from_space_view3d_mode(self, mode, create=False):
                return types.SimpleNamespace(idname=ctx.native)
        self.workspace = types.SimpleNamespace(tools=Tools(), status_text_set=lambda t: None)

    scene = property(lambda self: bpy.context.scene)
    view_layer = property(lambda self: bpy.context.view_layer)
    selected_objects = property(lambda self: bpy.context.selected_objects)
    collection = property(lambda self: bpy.context.scene.collection)

    def evaluated_depsgraph_get(self):
        return bpy.context.evaluated_depsgraph_get()


def E(t, v='PRESS', x=500, y=500, alt=False, shift=False, ctrl=False):
    return types.SimpleNamespace(type=t, value=v, mouse_x=x, mouse_y=y, alt=alt, shift=shift, ctrl=ctrl,
                                 oskey=False)


class Op(ce.StrokeLogic):
    def __init__(self, mode='CUT'):
        self.mode = mode
        self.reports = []

    def report(self, kind, msg):
        self.reports.append((tuple(kind), msg))


def setup(shape='LASSO', n_targets=1, tool='CUT'):
    fresh()
    s = C.scene
    s.mch_settings.auto_apply = True
    s.mch_settings.mch_active_tool = tool
    s.mch_brush.shape = shape
    s.mch_brush.line_open = False
    s.mch_cut.targets = 'SELECTED'
    ts_ = [cube(f'T{i}', loc=(0, 0, 0) if i == 0 else (0, 0, 3 * i)) for i in range(n_targets)]
    select_only(*ts_)
    CALLS.clear()
    CLOCK[0] += 10.0
    return ts_


def tick(dt=0.05):
    CLOCK[0] += dt


def click(op, ctx, x, y, **kw):
    r = op.modal(ctx, E('LEFTMOUSE', 'PRESS', x, y, **kw))
    if r != {'RUNNING_MODAL'}:
        return r
    return op.modal(ctx, E('LEFTMOUSE', 'RELEASE', x, y, **kw))


def start_lasso(ctx, op, pts):
    op.invoke(ctx, E('LEFTMOUSE', 'PRESS', *pts[0]))
    op.modal(ctx, E('LEFTMOUSE', 'RELEASE', *pts[0]))
    for x, y in pts[1:]:
        tick(0.6)
        click(op, ctx, x, y)


fresh()
mecha_lab.register()
SQUARE = [(450, 450), (560, 450), (560, 560), (450, 560)]

# =============================================================================
# B04 Lasso closing
# =============================================================================
t, = setup()
ctx, op = Ctx(), Op()
start_lasso(ctx, op, SQUARE)
tick(0.1)
r = click(op, ctx, 450, 560)        # second PRESS on the last point, NO DOUBLE_CLICK event
check('B04 own double-click (PRESS,PRESS, no DOUBLE_CLICK) far from start closes & applies',
      r == {'FINISHED'} and volume(t) < 8.0 - 1e-6 and non_manifold(t) == 0, (r, volume(t)))
check('B04 no duplicate point / zero-length edge', len(op.pts) == 4, op.pts)

t, = setup()
ctx, op = Ctx(), Op()
start_lasso(ctx, op, SQUARE)
tick(0.6)
r = op.modal(ctx, E('LEFTMOUSE', 'PRESS', 400, 505))       # far from start: just a new point
check('B04 slow second click = new point (not a close)', r == {'RUNNING_MODAL'} and len(op.pts) == 5)
op.modal(ctx, E('LEFTMOUSE', 'RELEASE', 400, 505))
tick(0.1)
r = op.modal(ctx, E('LEFTMOUSE', 'DOUBLE_CLICK', 400, 505))
check('B04 DOUBLE_CLICK event anywhere closes & applies', r == {'FINISHED'} and volume(t) < 8.0,
      (r, volume(t), op.reports[-1:]))

t, = setup()
ctx, op = Ctx(), Op()
start_lasso(ctx, op, SQUARE)
tick(0.6)
sc = ce.ui_scale(C)
r = click(op, ctx, 450 + int(11 * sc), 452)      # 11 px from the start point (old radius was 9)
check('B04 click near the start point (scaled radius) closes & applies', r == {'FINISHED'} and volume(t) < 8.0,
      r)

t, = setup('CURVE_LASSO')
ctx, op = Ctx(), Op()
start_lasso(ctx, op, SQUARE)
tick(0.6)
rounds_before = list(op.rounds)
r1 = op.modal(ctx, E('LEFTMOUSE', 'PRESS', 560, 450))     # edit click on an existing point
op.modal(ctx, E('LEFTMOUSE', 'RELEASE', 560, 450))
tick(0.1)
r2 = op.modal(ctx, E('LEFTMOUSE', 'DOUBLE_CLICK', 560, 450))
op.modal(ctx, E('LEFTMOUSE', 'RELEASE', 560, 450))
check('Curve Lasso: double-click on a point being edited does NOT close the shape',
      r1 == {'RUNNING_MODAL'} and r2 == {'RUNNING_MODAL'} and abs(volume(t) - 8.0) < 1e-6)
check('Curve Lasso: the two edit clicks stepped the point twice (straight -> soft -> medium)', op.rounds[1] == 0.25 and
      rounds_before[1] == 0.0, op.rounds)
r = op.modal(ctx, E('RET', 'PRESS', 500, 500))
check('Curve Lasso: Enter still confirms', r == {'FINISHED'} and volume(t) < 8.0)

t, = setup()
ctx, op = Ctx(), Op()
start_lasso(ctx, op, SQUARE)
r = op.modal(ctx, E('ESC', 'PRESS'))
check('Esc: stroke dropped, back to Select, mesh untouched', r == {'CANCELLED'} and ('exit',) in CALLS and
      abs(volume(t) - 8.0) < 1e-6)

t, = setup()
ctx, op = Ctx(), Op()
start_lasso(ctx, op, SQUARE)
r = op.modal(ctx, E('TAB', 'PRESS'))
check('Tab while drawing: stroke dropped and Tab passed to Blender (Edit Mode)',
      r == {'CANCELLED', 'PASS_THROUGH'} and abs(volume(t) - 8.0) < 1e-6)

# =============================================================================
# 0.11.1: Cut / Split basics + Alt invert / Ctrl centre restored (no Alt mode switch)
# =============================================================================
t, = setup('RECT')
ctx, op = Ctx(), Op()
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 450, 450))
op.modal(ctx, E('MOUSEMOVE', 'NOTHING', 500, 500))
r = op.modal(ctx, E('LEFTMOUSE', 'RELEASE', 550, 550))
check('0.11.1 #1 Rectangle Cut on a plain cube', r == {'FINISHED'} and abs(volume(t) - (8 - 1 * 1 * 2)) < 1e-3 and
      non_manifold(t) == 0, (volume(t), op.reports[-1:]))
t, = setup('LASSO')
ctx, op = Ctx(), Op()
start_lasso(ctx, op, SQUARE)
r = op.modal(ctx, E('RET', 'PRESS'))
check('0.11.1 #2 Lasso Cut', r == {'FINISHED'} and volume(t) < 8 - 1e-3 and non_manifold(t) == 0)
t, = setup('CURVE_LASSO')
ctx, op = Ctx(), Op()
start_lasso(ctx, op, SQUARE)
r = op.modal(ctx, E('RET', 'PRESS'))
check('0.11.1 #2 Curve Lasso Cut', r == {'FINISHED'} and volume(t) < 8 - 1e-3 and non_manifold(t) == 0)
t, = setup('RECT', tool='SPLIT')
ctx, op = Ctx('mecha.split'), Op('SPLIT')
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 450, 450))
op.modal(ctx, E('MOUSEMOVE', 'NOTHING', 500, 500))
r = op.modal(ctx, E('LEFTMOUSE', 'RELEASE', 550, 550))
piece = bpy.data.objects.get('T0_Split')
check('0.11.1 #3 Split separates the mesh into two closed parts', r == {'FINISHED'} and piece is not None and
      abs(volume(t) + volume(piece) - 8.0) < 1e-3 and non_manifold(piece) == 0)
t, = setup('CIRCLE')
ctx, op = Ctx(), Op()
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 500, 500, alt=True))
r = op.modal(ctx, E('LEFTMOUSE', 'RELEASE', 550, 500, alt=True))
check('0.11.1 #4 Alt at the press = keep inside (no drag threshold, no mode switch)', r == {'FINISHED'} and
      volume(t) < 2.0 and ('exit',) not in CALLS, volume(t))
t, = setup('CIRCLE')
ctx, op = Ctx(), Op()
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 500, 500))
op.modal(ctx, E('LEFT_ALT', 'PRESS'))
r = op.modal(ctx, E('LEFTMOUSE', 'RELEASE', 550, 500, alt=True))
check('0.11.1 #4 Alt pressed during the drag also inverts', r == {'FINISHED'} and volume(t) < 2.0)
t, = setup('LASSO')
ctx, op = Ctx(), Op()
start_lasso(ctx, op, SQUARE[:3])
tick(0.6)
r1 = click(op, ctx, 450, 560, alt=True)
check('0.11.1 Alt+click on a lasso point: point added + inverted, stays in the tool', r1 == {'RUNNING_MODAL'} and
      len(op.pts) == 4 and op.alt_latch and ('exit',) not in CALLS)
r = op.modal(ctx, E('RET', 'PRESS'))
check('...Alt lasso keeps the inside', r == {'FINISHED'} and 1.5 < volume(t) < 3.5, volume(t))
t, = setup('RECT')
ctx, op = Ctx(), Op()
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 500, 500))
op.modal(ctx, E('LEFT_CTRL', 'PRESS'))
r = op.modal(ctx, E('LEFTMOUSE', 'RELEASE', 550, 550, ctrl=True))
check('0.11.1 #5 Ctrl+drag draws from the centre (100 px square around the press)', r == {'FINISHED'} and
      abs(volume(t) - (8 - 1.0 * 1.0 * 2)) < 1e-3, volume(t))
t, = setup('LASSO')
ctx, op = Ctx(), Op()
start_lasso(ctx, op, [(380, 500), (620, 500)])
tick(0.6)
r = op.modal(ctx, E('RET', 'PRESS'))
r = click(op, ctx, 500, 580, alt=True)
check('2-point line: Alt+click on a side keeps that side (v0.9.3)', r == {'FINISHED'} and 3.9 < volume(t) < 4.1,
      volume(t))
# Select / Move while a stroke is pending: the stroke ends safely, re-entry starts fresh
t, = setup('LASSO')
ctx, op = Ctx(), Op()
start_lasso(ctx, op, SQUARE[:3])
ctx.native = 'builtin.move'                         # what mch.select_move switches to
r = op.modal(ctx, E('MOUSEMOVE', 'NOTHING', 300, 300))
check('0.11.1 #7 Select / Move during a stroke: stroke cancelled, nothing cut', r == {'CANCELLED'} and
      abs(volume(t) - 8.0) < 1e-6)
ctx2, op2 = Ctx(), Op()
op2.invoke(ctx2, E('LEFTMOUSE', 'PRESS', 450, 450))
check('0.11.1 #8 re-entering Cut starts a fresh stroke', op2.pts == [(450.0, 450.0)] and op2.stage == 'POINTS' and
      not op2.alt_latch)
start = op2.pts[:]
for x, y in SQUARE[1:]:
    tick(0.6)
    click(op2, ctx2, x, y)
r = op2.modal(ctx2, E('RET', 'PRESS'))
check('0.11.1 #8 ...and cuts normally', r == {'FINISHED'} and volume(t) < 8 - 1e-3)
check('0.11.1 Alt mode-switch code removed', not hasattr(ce.StrokeLogic, '_modal_altwait') and
      not hasattr(ce.StrokeLogic, '_alt_begin_drag') and 'MCH_OT_alt_click_return' not in dir(bpy.types))
# live primitive (empty base mesh, Geometry Nodes): used to say "would delete the whole object"
fresh()
bpy.ops.mch.primitive_create(kind='BOX')
box = C.active_object
C.view_layer.update()
r = ce.perform_closed(C, 'CUT', [box], [ce.rect_loop((470, 470), (530, 530))], TOP)
check('0.11.1 Cut on a live MCH_Box works (primitive baked first, reported)', 'baked' in r and len(box.data.polygons) > 6
      and non_manifold(box) == 0 and not box.modifiers, r)
fresh()
cb = cube('C')
try:
    ce.perform_closed(C, 'CUT', [cb], [ce.rect_loop((300, 300), (700, 700))], TOP)
    msg = ''
except cg.CutError as ex:
    msg = str(ex)
check('0.11.2 shape over the whole object: refused, says so, with facts (coverage, px, view, Alt, version)',
      'covers the whole of "C"' in msg and '8/8 vertices' in msg and 'Alt/invert off' in msg and
      ('Mecha Lab ' + '.'.join(map(str, mecha_lab.bl_info['version']))) in msg and 'ORTHO' in msg and abs(volume(cb) - 8.0) < 1e-6, msg)
try:
    ce.perform_closed(C, 'CUT', [cb], [ce.rect_loop((10, 10), (60, 60))], TOP, invert=True)
    msg = ''
except cg.CutError as ex:
    msg = str(ex)
check('0.11.2 Alt cut beside the object: "does not intersect", Alt shown', 'does not intersect' in msg and
      'Alt/invert ON' in msg and '0/8' in msg and abs(volume(cb) - 8.0) < 1e-6, msg)
# Cut while the object is in Edit Mode (Tab passes through since 0.11.0): used to fail in to_mesh()
fresh()
cb = cube('C')
select_only(cb)
C.view_layer.objects.active = cb
bpy.ops.object.mode_set(mode='EDIT')
try:
    r = ce.perform_closed(C, 'CUT', [cb], [ce.rect_loop((450, 450), (550, 550))], TOP)
except Exception as ex:
    r = f'ERROR {ex}'
check('0.11.2 Cut from Edit Mode: back to Object Mode and cut', cb.mode == 'OBJECT' and r.startswith('Cut') and
      volume(cb) < 8 - 1e-3, r)
fresh()
cb = cube('C')
select_only(cb)
C.view_layer.objects.active = cb
bpy.ops.object.mode_set(mode='EDIT')
try:
    r = ce.perform_closed(C, 'SPLIT', [cb], [ce.rect_loop((450, 300), (550, 700))], TOP)
except Exception as ex:
    r = f'ERROR {ex}'
check('0.11.2 Split from Edit Mode', cb.mode == 'OBJECT' and r.startswith('Split'), r)
bpy.ops.object.select_all(action='DESELECT')

# =============================================================================
# B07 Split Gap: Enter / start click / double-click
# =============================================================================
for how in ('enter', 'start', 'double'):
    t, = setup()
    C.scene.mch_cut.split_mode = 'GAP'
    C.scene.mch_cut.gap_width = 0.1
    ctx, op = Ctx('mecha.split'), Op('SPLIT')
    C.scene.mch_settings.mch_active_tool = 'SPLIT'
    start_lasso(ctx, op, SQUARE)
    tick(0.6)
    if how == 'enter':
        r = op.modal(ctx, E('RET', 'PRESS'))
    elif how == 'start':
        r = click(op, ctx, 452, 451)
    else:
        click(op, ctx, 470, 470)
        tick(0.1)
        r = click(op, ctx, 470, 470)
    piece = bpy.data.objects.get('T0_Split')
    check(f'B07 Gap Split confirmed by {how}', r == {'FINISHED'} and piece is not None and
          non_manifold(t) == 0 and non_manifold(piece) == 0, r)
    if piece is not None:
        check(f'B07 ({how}) gap removed material', volume(t) + volume(piece) < 8.0 - 0.01)

t, = setup()
C.scene.mch_cut.split_mode = 'GAP'
C.scene.mch_cut.gap_width = 0.1
C.scene.mch_brush.line_open = True
ctx, op = Ctx('mecha.split'), Op('SPLIT')
C.scene.mch_settings.mch_active_tool = 'SPLIT'
start_lasso(ctx, op, [(380, 500), (500, 520), (620, 500)])
tick(0.6)
r = click(op, ctx, 381, 500)
check('B07 open-line (F) Gap Split: clicking the start point confirms', r == {'FINISHED'} and
      bpy.data.objects.get('T0_Split') is not None, r)

# =============================================================================
# F01 multi-target Cut / Split, failure preservation
# =============================================================================
ts3 = setup(n_targets=3)
ctx, op = Ctx(), Op()
start_lasso(ctx, op, SQUARE)
r = op.modal(ctx, E('RET', 'PRESS'))
check('F01 one stroke cuts all 3 selected meshes', r == {'FINISHED'} and all(volume(o) < 8.0 - 1e-6 for o in ts3),
      [round(volume(o), 3) for o in ts3])
ts3 = setup(n_targets=3)
ts3[2].location.x = 50       # out of the drawn shape
C.view_layer.update()
ctx, op = Ctx('mecha.split'), Op('SPLIT')
C.scene.mch_settings.mch_active_tool = 'SPLIT'
start_lasso(ctx, op, SQUARE)
r = op.modal(ctx, E('RET', 'PRESS'))
msg = op.reports[-1][1] if op.reports else ''
check('F01 split: 2 hit targets split, the third untouched and reported', r == {'FINISHED'} and
      'T0_Split' in bpy.data.objects and 'T1_Split' in bpy.data.objects and abs(volume(ts3[2]) - 8.0) < 1e-6 and
      'T2' in msg, msg)

# =============================================================================
# F01 Boolean: A, B selected, C active = cutter
# =============================================================================
fresh()
a, b = cube('A'), cube('B', loc=(0, 0, 4))
c = mesh_obj('C', lambda bm: bmesh.ops.create_cube(bm, size=1.0), loc=(0.8, 0.8, 2))
c.scale = (1, 1, 6)
C.view_layer.update()
select_only(c, a, b)                 # C is active (yellow)
C.scene.mch_settings.keep_cutter = True
r = bpy.ops.mch.boolean(operation='DIFFERENCE')
check('Boolean: C (active) is the single cutter, A and B are both cut',
      r == {'FINISHED'} and volume(a) < 8.0 - 1e-3 and volume(b) < 8.0 - 1e-3, (volume(a), volume(b)))
check('Boolean: cutter C kept (Keep Cutter) and unchanged', 'C' in bpy.data.objects and abs(volume(c) - 6.0) < 1e-4)
fresh()
a = cube('A')
far = cube('Far', loc=(30, 0, 0))
c = cube('C', size=1.0, loc=(0.8, 0.8, 0.8))
select_only(c, a, far)
C.scene.mch_settings.keep_cutter = False
r = bpy.ops.mch.boolean(operation='INTERSECT')
check('Boolean INTERSECT on 2 targets with one active cutter', r == {'FINISHED'} and volume(a) < 1.0 + 1e-4)

# =============================================================================
# B01 Mirror: world / local / cursor x X / Y / Z, multi, change, apply, remove
# =============================================================================
fresh()
p = C.scene.mch_mirror
results = []
for space in ('WORLD', 'LOCAL'):
    for center in (('ORIGIN', 'CURSOR') if space == 'WORLD' else ('ORIGIN',)):
        for axis in 'XYZ':
            fresh()
            p = C.scene.mch_mirror
            o1 = cube('M1', size=1.0, loc=(2, 2, 2))
            o2 = cube('M2', size=1.0, loc=(4, 2, 2))
            C.scene.cursor.location = (1, 0, 0)
            select_only(o1, o2)
            p.space, p.x, p.y, p.z = space, axis == 'X', axis == 'Y', axis == 'Z'
            if space == 'WORLD':
                p.center = center
            p.merge = False
            ok = bpy.ops.mch.mesh_mirror() == {'FINISHED'}
            ok &= all(o.modifiers.get('MCH_Mirror') for o in (o1, o2))
            dg = C.evaluated_depsgraph_get()
            ev = o1.evaluated_get(dg)
            nv = len(ev.data.vertices)
            ok &= nv == 16
            results.append((space, center, axis, ok))
check('B01 Mirror create on 2 meshes: world origin / world cursor / local x X Y Z',
      all(r[3] for r in results), [r for r in results if not r[3]])
fresh()
o1, o2 = cube('M1', size=1.0, loc=(2, 0, 0)), cube('M2', size=1.0, loc=(4, 0, 0))
select_only(o1, o2)
p = C.scene.mch_mirror
p.space, p.center, p.x, p.y, p.z, p.merge = 'WORLD', 'ORIGIN', True, False, False, False
bpy.ops.mch.mesh_mirror()
p.y = True
bpy.ops.mch.mesh_mirror()          # change = update
check('B01 Mirror update changes axes on both', all(tuple(o.modifiers['MCH_Mirror'].use_axis) == (True, True, False)
                                                    for o in (o1, o2)))
r = bpy.ops.mch.mesh_mirror_apply()
check('B01 Mirror apply on all selected', r == {'FINISHED'} and len(o1.data.vertices) == 32 and
      len(o2.data.vertices) == 32 and not o1.modifiers and not o2.modifiers)
check('B01 world pivots removed after apply', not [o for o in bpy.data.objects if o.get('_mch_world_pivot')])
o3 = cube('M3', size=1.0, loc=(6, 0, 0))
select_only(o3)
bpy.ops.mch.mesh_mirror()
r = bpy.ops.mch.mesh_mirror_remove()
check('B01 Mirror remove keeps geometry', r == {'FINISHED'} and not o3.modifiers and len(o3.data.vertices) == 8)
coll = bpy.data.collections.new('Parts')
C.scene.collection.children.link(coll)
part = cube('Arm', size=1.0, loc=(2, 0, 0))
for cl in part.users_collection:
    cl.objects.unlink(part)
coll.objects.link(part)
p.source_collection = coll
r = bpy.ops.mch.collection_mirror()
master = C.active_object
check('B01 Collection Mirror rig created', r == {'FINISHED'} and master.get('_mch_collection_mirror_role') == 'MASTER')
r = bpy.ops.mch.collection_mirror_remove()
check('B01 Collection Mirror rig removed, source kept', r == {'FINISHED'} and 'Arm' in bpy.data.objects and
      not [o for o in bpy.data.objects if o.get('_mch_collection_mirror_role')])

# =============================================================================
# B03 Smart Fuse x10
# =============================================================================
fresh()
ok = True
for i in range(10):
    a = cube(f'FA{i}', loc=(i * 5, 0, 0))
    b = cube(f'FB{i}', size=1.2, loc=(i * 5 + 0.9, 0.3, 0.2))
    select_only(b, a)       # a active (fuse keeps the active object)
    select_only(a, b)
    ok &= bpy.ops.mch.smart_fuse() == {'FINISHED'}
    if i % 3 == 2:
        ok &= bpy.ops.mch.smart_fuse_cancel() == {'FINISHED'}
    else:
        ok &= bpy.ops.mch.smart_fuse_confirm() == {'FINISHED'}
check('B03 Smart Fuse 10x create + confirm/cancel all succeed', ok)
check('B03 no orphan Smart Fuse node groups left',
      not [g for g in bpy.data.node_groups if g.name.startswith('MCH Smart Fuse')],
      [g.name for g in bpy.data.node_groups])
a, b = cube('PA', loc=(80, 0, 0)), cube('PB', size=1.2, loc=(80.9, 0.3, 0.2))
select_only(a, b)
bpy.ops.mch.smart_fuse()
x, y = cube('NA', loc=(90, 0, 0)), cube('NB', size=1.2, loc=(90.9, 0.3, 0.2))
select_only(x, y)
from mecha_lab import fuse_target_from_context
check('B03 pending preview elsewhere does not hijack the panel', fuse_target_from_context(C) is None)
check('B03 a second fuse can be created while another preview is pending', bpy.ops.mch.smart_fuse() == {'FINISHED'})
bpy.ops.mch.smart_fuse_confirm()
for m in list(a.modifiers):
    a.modifiers.remove(m)           # e.g. undo / manual removal leaves the flag stale
select_only(a, cube('PC', size=1.2, loc=(80.9, -0.3, 0.2)))
check('B03 stale fuse flag repaired automatically', bpy.ops.mch.smart_fuse() == {'FINISHED'})

# =============================================================================
# B05 Mesh Curve: one physical double-click = one toggle
# =============================================================================
fresh()
mecha_lab._path_ray = lambda region, rv3d, xy: TOP.ray(xy)
mecha_lab._path_to_screen = lambda region, rv3d, co: TOP.to_screen(co)


class PathOp(mecha_lab.PathDrawLogic):
    kind = 'CURVE'

    def report(self, *a):
        pass


class PCtx:
    def __init__(self):
        self.region = Region()
        self.area = types.SimpleNamespace(type='VIEW_3D', regions=[self.region], header_text_set=lambda t: None)
        self.space_data = types.SimpleNamespace(region_3d=types.SimpleNamespace(
            view_rotation=Quaternion(), view_perspective='ORTHO'))
        self.window_manager = WM()
        self.window = types.SimpleNamespace(cursor_modal_set=lambda c: None, cursor_modal_restore=lambda: None)
        self.preferences = bpy.context.preferences

    def __getattr__(self, name):
        return getattr(bpy.context, name)


pctx, pop = PCtx(), PathOp()
C.scene.mch_settings.path_point_type = 'VECTOR'
C.scene.mch_settings.path_draw_mode = 'POLY'
pop.invoke(pctx, E('LEFTMOUSE', 'PRESS'))
for x, y in ((400, 500), (500, 600), (600, 500)):
    tick(0.6)
    pop.modal(pctx, E('LEFTMOUSE', 'PRESS', x, y))
    pop.modal(pctx, E('LEFTMOUSE', 'RELEASE', x, y))
bp = pop._bpoints()[1]
check('B05 new points start Straight (VECTOR)', bp.handle_left_type == 'VECTOR')
tick(0.6)
pop.modal(pctx, E('LEFTMOUSE', 'PRESS', 500, 600))
pop.modal(pctx, E('LEFTMOUSE', 'RELEASE', 500, 600))
tick(0.1)
pop.modal(pctx, E('LEFTMOUSE', 'DOUBLE_CLICK', 500, 600))
check('B05 double-click a point (PRESS + DOUBLE_CLICK) = Smooth, not toggled back', bp.handle_left_type == 'AUTO')
tick(0.6)
pop.modal(pctx, E('LEFTMOUSE', 'PRESS', 600, 500))
pop.modal(pctx, E('LEFTMOUSE', 'RELEASE', 600, 500))
tick(0.1)
pop.modal(pctx, E('LEFTMOUSE', 'PRESS', 600, 500))       # system without DOUBLE_CLICK
check('B05 double-click as two PRESS events = one toggle', pop._bpoints()[2].handle_left_type == 'AUTO')
tick(0.8)
pop.modal(pctx, E('LEFTMOUSE', 'PRESS', 600, 500))
check('B05 a later separate click toggles back to Straight', pop._bpoints()[2].handle_left_type == 'VECTOR')
pop.modal(pctx, E('RET', 'PRESS'))

# =============================================================================
# B06 PNG stamp: R rotates while drawing; preview == executed shape
# =============================================================================
NORM = [[(-0.5, -0.5), (0.5, -0.5), (0.5, -0.1), (-0.1, -0.1), (-0.1, 0.5), (-0.5, 0.5)]]   # L shape
cut_presets.load_loops = lambda stem: NORM
t, = setup('CUSTOM')
C.scene.mch_brush.custom_rotation = 0.0
C.scene.mch_brush.custom_drag_rotate = False
ctx, op = Ctx(), Op()
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 500, 500))
op.modal(ctx, E('MOUSEMOVE', 'NOTHING', 560, 500))
op.modal(ctx, E('R', 'PRESS', 560, 500))
check('B06 R while drawing rotates the stamp 15°', abs(math.degrees(C.scene.mch_brush.custom_rotation) - 15) < 1e-4)
op.modal(ctx, E('R', 'PRESS', 560, 500, shift=True))
op.modal(ctx, E('R', 'PRESS', 560, 500))
op.modal(ctx, E('R', 'PRESS', 560, 500))
check('B06 Shift+R rotates back', abs(math.degrees(C.scene.mch_brush.custom_rotation) - 30) < 1e-4)
preview = op.preview_loops()
executed = op._current_loops(False, False)
check('B06 preview outline == executed cutter outline (rotated)',
      len(preview) == len(executed) and all(math.dist(a, b) < 1e-9 for pa, pb in zip(preview, executed)
                                            for a, b in zip(pa, pb)))
r = op.modal(ctx, E('LEFTMOUSE', 'RELEASE', 560, 500))
check('B06 rotated stamp cut applied (closed result)', r == {'FINISHED'} and non_manifold(t) == 0 and volume(t) < 8)
check('B06 idle R operator only for PNG shapes', ce.MCH_OT_stamp_rotate.poll(C))
C.scene.mch_brush.shape = 'LASSO'
check('B06 idle R falls through to Blender for other shapes', not ce.MCH_OT_stamp_rotate.poll(C))

# =============================================================================
# B10 bevel: large width is reported when clamped
# =============================================================================
t, = setup('RECT')
cutp = C.scene.mch_cut
cutp.edge_finish, cutp.finish_width, cutp.finish_clamp = 'BEVEL', 3.0, True
ctx, op = Ctx(), Op()
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 450, 450))
op.modal(ctx, E('MOUSEMOVE', 'NOTHING', 550, 550))
r = op.modal(ctx, E('LEFTMOUSE', 'RELEASE', 550, 550))
msg = op.reports[-1][1] if op.reports else ''
check('B10 huge Edge Finish width: applied and the limit is reported', r == {'FINISHED'} and 'limited to' in msg and
      non_manifold(t) == 0, msg)
t, = setup('RECT')
cutp = C.scene.mch_cut
cutp.edge_finish, cutp.finish_width = 'BEVEL', 0.05
ctx, op = Ctx(), Op()
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 450, 450))
op.modal(ctx, E('MOUSEMOVE', 'NOTHING', 550, 550))
op.modal(ctx, E('LEFTMOUSE', 'RELEASE', 550, 550))
msg = op.reports[-1][1] if op.reports else ''
check('B10 normal width: no limit note', 'limited' not in msg and 'BEVEL' in msg, msg)
cutp.edge_finish = 'NONE'
check('B10 width slider range raised (soft max 2.0)',
      ts.MCH_PG_Cut.bl_rna.properties['finish_width'].soft_max >= 2.0)

# =============================================================================
# B08 Mask hidden, data kept
# =============================================================================
check('B08 Mask not in the tool list / Space / V', 'MASK' not in [t[0] for t in ts.VISIBLE_TOOLS] and
      'MASK' not in ts.QUICK_TOOLS)
from bl_ui.space_toolsystem_common import ToolSelectPanelHelper
tools = ToolSelectPanelHelper._tool_class_from_space_type('VIEW_3D')._tools.get('OBJECT', [])
ids = [getattr(x, 'idname', '') for x in tools if x is not None]
check('B08 mecha.mask toolbar tool not registered (Cut/Split/Base Mesh are)',
      'mecha.mask' not in ids and {'mecha.cut', 'mecha.split', 'mecha.base_mesh'} <= set(ids), ids)
fresh()
m = cube('Masked')
attr = m.data.attributes.new('mch_mask', 'INT', 'FACE')
attr.data[0].value = 1
vg = m.vertex_groups.new(name='MCH_Mask_Group')
C.scene.mch_settings.mch_active_tool = 'MASK'           # value from an old file
check('B08 old file with Mask active shows Cut instead', ts.effective_tool(C) == 'CUT')
mecha_lab.unregister()
mecha_lab.register()
check('B08 saved mask attribute and vertex group untouched by register cycles',
      m.data.attributes.get('mch_mask') is not None and m.data.attributes['mch_mask'].data[0].value == 1 and
      m.vertex_groups.get('MCH_Mask_Group') is not None)
check('B08 mask operators still registered (compatibility)', hasattr(bpy.ops.mch, 'mask_extract'))

# =============================================================================
# F02 Base Mesh: Bevel Sides, Both widths, Alt+drag cutter, session auto apply, migration
# =============================================================================


def make_base(sides, profile='BEVEL', link=True, w_top=0.05, w_bot=0.05, seg=3):
    fresh()
    p = C.scene.mch_base
    p.profile, p.height, p.bevel_sides, p.bevel_link = profile, 0.4, sides, link
    p.bevel_width, p.bevel_width_bottom, p.bevel_segments, p.bevel_segments_bottom = w_top, w_bot, seg, seg
    base_mesh.perform_base(C, [ce.rect_loop((400, 400), (600, 600))], TOP)
    return C.active_object


def z_extent_of_bevel(ob):
    """(top rim bevelled?, bottom rim bevelled?) from vertex heights."""
    zs = sorted({round(v.co.z, 5) for v in ob.data.vertices})
    return zs[-2] < zs[-1] - 1e-6 and len([z for z in zs if z > 0.2]) > 1, \
        len([z for z in zs if z < 0.2]) > 1


combo_ok = []
for profile in ('FLAT', 'CHAMFER', 'BEVEL', 'DOME'):
    for sides in ('TOP', 'BOTTOM', 'BOTH', 'NONE'):
        try:
            ob = make_base(sides, profile)
            ok = non_manifold(ob) == 0 and volume(ob) > 0
        except cg.CutError as ex:
            ok = False
        combo_ok.append((profile, sides, ok))
check('F02 every profile x Bevel Sides combination builds a closed solid', all(c[2] for c in combo_ok),
      [c for c in combo_ok if not c[2]])
top_b, bot_b = z_extent_of_bevel(make_base('TOP'))
check('F02 Top Only: top bevelled, bottom sharp', top_b and not bot_b, (top_b, bot_b))
top_b, bot_b = z_extent_of_bevel(make_base('BOTTOM'))
check('F02 Bottom Only: bottom bevelled, top sharp', bot_b and not top_b, (top_b, bot_b))
top_b, bot_b = z_extent_of_bevel(make_base('BOTH'))
check('F02 Both: top and bottom bevelled', top_b and bot_b)
top_b, bot_b = z_extent_of_bevel(make_base('NONE'))
check('F02 None: flat and sharp', not top_b and not bot_b)
ob = make_base('BOTH', link=False, w_top=0.12, w_bot=0.03)
zs = sorted({round(v.co.z, 5) for v in ob.data.vertices})
check('F02 Both with different top / bottom widths', abs((zs[-1] - zs[-2]) - 0.12) < 0.03 or
      abs(max(z for z in zs) - 0.4) < 1e-6 and min(z for z in zs if z > 0) <= 0.035, zs)
check('F02 flip: Top -> Bottom, Bottom -> Top, None stays',
      base_mesh.side_values(types.SimpleNamespace(bevel_sides='TOP', bevel_width=1, bevel_segments=2,
                                                  bevel_link=True), True)[0] == 'BOTTOM' and
      base_mesh.side_values(types.SimpleNamespace(bevel_sides='BOTTOM', bevel_width=1, bevel_segments=2,
                                                  bevel_link=True), True)[0] == 'TOP' and
      base_mesh.side_values(types.SimpleNamespace(bevel_sides='NONE', bevel_width=1, bevel_segments=2,
                                                  bevel_link=True), True)[0] == 'NONE')
sv = base_mesh.side_values(types.SimpleNamespace(bevel_sides='BOTH', bevel_width=0.2, bevel_segments=5,
                                                 bevel_width_bottom=0.05, bevel_segments_bottom=1,
                                                 bevel_link=False), True)
check('F02 flip Both: top / bottom settings swapped', sv[1] == (0.05, 1) and sv[2] == (0.2, 5), sv)

# Alt (latched at the press) cutter through the real stroke logic
fresh()
t = cube('Hull', size=2.0)
select_only(t)
pb = C.scene.mch_base
pb.profile, pb.height, pb.bevel_sides, pb.bevel_width = 'CHAMFER', 0.5, 'TOP', 0.1
C.scene.mch_brush.shape = 'RECT'
C.scene.mch_settings.mch_active_tool = 'BASE'
pb.sketch = False                  # 0.14.1: instant mode keeps Alt+drag = cutter
ctx, op = Ctx('mecha.base_mesh'), Op('BASE')
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 450, 450, alt=True))
op.modal(ctx, E('MOUSEMOVE', 'NOTHING', 500, 500, alt=True))
r = op.modal(ctx, E('LEFTMOUSE', 'RELEASE', 550, 550, alt=True))
msg = op.reports[-1][1] if op.reports else ''
check('F02 Alt+drag Base Mesh = Boolean Difference pocket into the hull', r == {'FINISHED'} and
      volume(t) < 8.0 - 0.1 and non_manifold(t) == 0 and 'cutter' in msg, (msg, volume(t)))
check('F02 Alt+drag leaves no cutter / new object behind', [o.name for o in bpy.data.objects] == ['Hull'])
check('F02 Alt+drag cutter used the flipped side (Top -> Bottom)', 'Bottom' in msg, msg)
hull_top = max(v.co.z for v in t.data.vertices)
chamfer_z = sorted({round(v.co.z, 4) for v in t.data.vertices if abs(v.co.x) < 0.55 and abs(v.co.y) < 0.55})
check('F02 pocket opening chamfered at the surface (flipped bevel lands on the opening)',
      any(0.85 < z < 0.999 for z in chamfer_z), chamfer_z)

# session auto apply: only this session's live Base Meshes
fresh()
old = make_base('TOP')            # created before "entering" the tool again
C.scene['mch_base_session'] = []  # tool (re)entered: new session
pb = C.scene.mch_base
base_mesh.perform_base(C, [ce.rect_loop((300, 300), (380, 380))], TOP)
new = C.active_object
other = cube('UserObj', loc=(9, 0, 0))
mod = other.modifiers.new('UserBevel', 'BEVEL')
frozen = base_mesh.auto_apply_session(C)
check('F02 leaving the tool applies (freezes) only the session result', frozen == [new.name] and
      not new.mch_base.live and old.mch_base.live)
check('F02 user modifiers on other objects untouched', other.modifiers.get('UserBevel') is not None)
check('F02 auto apply keeps the geometry', non_manifold(new) == 0 and volume(new) > 0)
# leaving the workspace tab applies the session too
fresh()
C.scene['mch_base_session'] = []
base_mesh.perform_base(C, [ce.rect_loop((300, 300), (380, 380))], TOP)
tabbed = C.active_object
C.scene['mch_base_session_ws'] = 'MECHA LAB'
check('tab watch: still in MECHA LAB -> nothing applied', base_mesh.check_tab_left(C, ['MECHA LAB']) == [] and
      tabbed.mch_base.live)
check('tab watch: switched to another tab -> session applied',
      base_mesh.check_tab_left(C, ['Layout']) == [tabbed.name] and not tabbed.mch_base.live)
check('tab watch: session cleared afterwards', not C.scene.get('mch_base_session'))
# migration of the old option
fresh()
p = C.scene.mch_base
p.bottom_too = True
if 'bevel_sides' in p:
    del p['bevel_sides']
base_mesh._migrate_on_load()
check('F02 old "Bevel Bottom Too" migrates to Both', p.bevel_sides == 'BOTH')

# =============================================================================
# Menus / keys
# =============================================================================
kc = C.window_manager.keyconfigs.addon
items = [(ki.idname, ki.type, ki.value, ki.alt) for km in kc.keymaps for ki in km.keymap_items] if kc else []
shift_q = {(ki.idname, ki.shift) for km in kc.keymaps for ki in km.keymap_items if ki.type == 'Q'} if kc else set()
check('Q toggle / V tool pie registered (gated), N free', ('mch.tool_pie', 'V', 'PRESS', False) in items
      and ('mch.toggle_last_tool', False) in shift_q
      and not any(i[1] == 'N' for i in items), items)
check('0.11.3 Select / Move hotkey (F, MECHA LAB only) registered and editable',
      ('mch.select_move_key', 'F', 'PRESS', False) in items and hasattr(bpy.ops.mch, 'select_move'))
check('0.11.1 no Alt+click keymap left', not any(i[0] == 'mch.alt_click_return' for i in items))
check('Shift+A: Mecha Lab submenu appended to the Add menu',
      wui.draw_add_menu in bpy.types.VIEW3D_MT_add._dyn_ui_initialize())
check('Quick menu = the six core tools + Armor Plate (0.19)', ts.QUICK_TOOLS == ('CUT', 'BOOLEAN', 'BASE', 'SUBD', 'SPLIT', 'RADIAL', 'PLATE'))
check('no Alt+MMB binding (cancelled by the user)', not any(i[1] == 'MIDDLEMOUSE' and i[3] for i in items))
fake = types.SimpleNamespace(scene=C.scene, workspace=types.SimpleNamespace(
    tools=types.SimpleNamespace(from_space_view3d_mode=lambda m, create=False: types.SimpleNamespace(
        idname='mecha.cut'))))
C.scene.mch_settings.mch_active_tool = 'MIRROR'
C.scene.mch_settings['mch_native_at_choice'] = 'mecha.cut'
check('tool list switch that the toolbar could not follow: panel shows the chosen tool',
      ts.effective_tool(fake) == 'MIRROR')
C.scene.mch_settings['mch_native_at_choice'] = 'builtin.select_box'
check('a later toolbar click on Cut wins again', ts.effective_tool(fake) == 'CUT')

# =============================================================================
# F08 Stabilizer
# =============================================================================


class B:
    stab_enable = True
    stab_strength = 0.0
    stab_radius = 0.0
    stroke_spacing = 1.0


def run_stab(strength, radius, noise=6.0, n=200, rate=1 / 120.0, seed=3, speed=480.0):
    b = B()
    b.stab_strength, b.stab_radius = strength, radius
    st = stabilizer.LazyStabilizer(b)
    rng = random.Random(seed)
    t = 0.0
    st.reset((0.0, 500.0), t)
    out = []
    for i in range(n):
        t += rate
        cursor = (t * speed, 500.0 + rng.uniform(-noise, noise))     # same mouse speed at any event rate
        out.append((cursor, st.update(cursor, t)))
    return out, st


def jitter(out):
    ys = [p[1] for _c, p in out[40:]]
    return math.sqrt(sum((y - 500.0) ** 2 for y in ys) / len(ys))


def lag(out):
    return sum(c[0] - p[0] for c, p in out[40:]) / len(out[40:])


j0, j1, j2 = jitter(run_stab(0, 0)[0]), jitter(run_stab(40, 0)[0]), jitter(run_stab(90, 0)[0])
l0, l1, l2 = lag(run_stab(0, 0)[0]), lag(run_stab(40, 0)[0]), lag(run_stab(90, 0)[0])
check('F08 Strength up -> less tremor', j0 > j1 > j2, (round(j0, 2), round(j1, 2), round(j2, 2)))
check('F08 Strength up -> more lag (slower follow)', l0 <= l1 < l2, (round(l0, 1), round(l1, 1), round(l2, 1)))
a_fast, _ = run_stab(60, 0, rate=1 / 240.0, n=400, noise=0)
a_slow, _ = run_stab(60, 0, rate=1 / 60.0, n=100, noise=0)
lag_fast = a_fast[-1][0][0] - a_fast[-1][1][0]
lag_slow = a_slow[-1][0][0] - a_slow[-1][1][0]
check('F08 dt-aware: same lag behind the mouse at 240 Hz and 60 Hz events (time constant)',
      abs(lag_fast - lag_slow) < 0.2 * max(lag_fast, lag_slow), (round(lag_fast, 1), round(lag_slow, 1)))
b = B()
b.stab_strength, b.stab_radius = 0.0, 30.0
st = stabilizer.LazyStabilizer(b)
st.reset((100.0, 100.0), 0.0)
inside = [st.update((100.0 + dx, 100.0 + dy), 0.01 * k) for k, (dx, dy) in
          enumerate(((10, 0), (-20, 5), (0, 25), (15, -15)), 1)]
check('F08 Lazy Radius: cursor inside the circle -> line point does not move',
      all(math.dist(p, (100.0, 100.0)) < 1e-9 for p in inside))
p = st.update((200.0, 100.0), 1.0)
check('F08 Lazy Radius: outside -> pulled along, staying on the circle edge', abs(math.dist(p, (200.0, 100.0)) - 30.0)
      < 1e-6, p)
end = st.finish((210.0, 100.0), 4.0)
check('F08 release: catches up smoothly to the release point, no long jump, no double point',
      math.dist(end[-1], (210.0, 100.0)) < 1e-9 and math.dist(p, end[0]) <= 4.0 + 1e-6 and
      all(math.dist(end[i], end[i + 1]) <= 4.0 + 1e-6 for i in range(len(end) - 1)) and
      len(end) == len({(round(x, 6), round(y, 6)) for x, y in end}), end[-4:])
b.stab_enable = False
check('F08 OFF -> not active', not stabilizer.LazyStabilizer(b).active)
b.stab_enable, b.stab_strength, b.stab_radius = True, 0.0, 0.0
check('F08 0 % and 0 px -> not active (exact old path)', not stabilizer.LazyStabilizer(b).active)


def free_draw(stab_on, strength=70.0, radius=15.0, seed=5, mode='CUT', native='mecha.cut', tool='CUT'):
    t, = setup('STROKE', tool=tool)
    br = C.scene.mch_brush
    br.stab_enable, br.stab_strength, br.stab_radius, br.stroke_spacing = stab_on, strength, radius, 4.0
    br.stroke_smooth = 0
    ctx, op = Ctx(native), Op(mode)
    rng = random.Random(seed)
    pts = [(500 + 70 * math.cos(a), 500 + 70 * math.sin(a))
           for a in (2 * math.pi * i / 120 for i in range(121))]
    first = tuple(int(v) for v in pts[0])
    op.invoke(ctx, E('LEFTMOUSE', 'PRESS', *first))
    events = [(float(first[0]), float(first[1]))]
    for x, y in pts[1:]:
        tick(1 / 120.0)
        ev = (int(x + rng.uniform(-4, 4)), int(y + rng.uniform(-4, 4)))
        events.append((float(ev[0]), float(ev[1])))
        op.modal(ctx, E('MOUSEMOVE', 'NOTHING', *ev))
        if stab_on:
            op.modal(ctx, E('TIMER', 'NOTHING'))
    xs, ys = pts[-1]
    raw = list(op.pts)
    r = op.modal(ctx, E('LEFTMOUSE', 'RELEASE', int(xs), int(ys)))
    op.events = events
    return t, op, r, raw


def roughness(pts):
    """Mean absolute turning angle between consecutive segments."""
    ang = []
    for i in range(1, len(pts) - 1):
        a = math.atan2(pts[i][1] - pts[i - 1][1], pts[i][0] - pts[i - 1][0])
        b = math.atan2(pts[i + 1][1] - pts[i][1], pts[i + 1][0] - pts[i][0])
        ang.append(abs((b - a + math.pi) % (2 * math.pi) - math.pi))
    return sum(ang) / len(ang)


t_off, op_off, r_off, raw_off = free_draw(False)
t_on, op_on, r_on, raw_on = free_draw(True)
check('F08 Free Draw Cut with stabilizer ON: applied, closed result', r_on == {'FINISHED'} and non_manifold(t_on) == 0
      and volume(t_on) < 8.0)
check('F08 stabilized stroke is smoother than the raw one (same shaky input)',
      roughness(raw_on) < roughness(raw_off), (round(roughness(raw_on), 3), round(roughness(raw_off), 3)))
old_rule = [op_off.events[0]]
for e in op_off.events[1:]:
    if math.dist(old_rule[-1], e) >= 4.0:      # v0.9.3 Free Draw sampling
        old_rule.append(e)
check('F08 OFF: Free Draw samples are exactly the v0.9.3 rule', raw_off == old_rule, (len(raw_off), len(old_rule)))
for mode, native, tool in (('SPLIT', 'mecha.split', 'SPLIT'), ('BASE', 'mecha.base_mesh', 'BASE')):
    tt, opx, rx, _raw = free_draw(True, mode=mode, native=native, tool=tool)
    obs = [o for o in bpy.data.objects if o.type == 'MESH']
    check(f'F08 stabilizer reused by {mode}: valid closed result', rx == {'FINISHED'} and
          all(non_manifold(o) == 0 for o in obs), [o.name for o in obs])

mecha_lab.unregister()
sys.exit(1 if summary() else 0)
