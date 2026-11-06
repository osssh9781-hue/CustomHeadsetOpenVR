"""0.24.107 Press / Base Mesh / Draw Array fixes from the v0.24.106 review.

- contact dots back to 8 / 18 / 11 px (x Dot Size x UI scale), no 3 / 7 px clamp
- a slowly started line: a press that has just begun turns back into the line (the part put back), and the line
  is cut (Split when the press result is Split)
- Grow: the selection stays as it was; the bottom follows the surface (it came out of the back of a thin, slanted part)
- Base Mesh: a Press Alt+draw sweep does not leak into later plain lines; a looping line sweeps; its width is the
  drawn width; Attach Ends kept; the depth guide bends the part instead of lifting it
- Draw Array: rebuilt from a timer pass (not inside the slider), in its own collection, only when something it
  depends on changed (also after undo), capped
"""
import math
import time

from _harness import bpy, check, cube, fresh, summary
from mathutils import Euler, Quaternion, Vector

import mecha_lab
from mecha_lab import along_curve as ac, base_mesh as bm_, core_geometry as cg, groups, lasso_line, press_cut as pc

fresh()
mecha_lab.register()
C = bpy.context
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)

# --- dots ------------------------------------------------------------------------------------------------------------
st = C.scene.mch_press
st.dot_size = 1.0
one = pc.dot_sizes(C)
st.dot_size = 3.0
three = pc.dot_sizes(C)
st.dot_size = 1.0
check('contact dots: 8 / 18 / 11 px at Dot Size 1 (v0.24.106: 3 / 7 / 4)', one == (8.0, 18.0, 11.0), one)
check('... Dot Size 3 makes them three times as big (v0.24.106 stopped growing above ~1.7)', three == (24.0, 54.0, 33.0), three)
tri = pc._dot_triangles([(0.0, 0.0)], 54.0)
rad = max(math.hypot(*v) for v in tri)
check('... and the disc is drawn that big (no 16 px cap)', abs(rad - 27.0) < 1e-4, rad)

# --- slow start of a line -------------------------------------------------------------------------------------------
C.scene.mch_settings.auto_apply = True
C.scene.mch_cut.depth_mode, C.scene.mch_cut.depth = 'THROUGH', 0.1
p = cube('P', size=2.0)
v0 = len(p.data.vertices)
xy = TOP.to_screen(Vector((0, 0, 1)))
press = pc.Press(C, p, pc.stamp_loops(C, xy, st), TOP, 'CUT', center=xy, spacing=6.0)
press.cut_to(C, pc.depth_at(st, press.size, 0.3))
check('(a press has begun: the part is cut)', len(p.data.vertices) != v0)


class Region:
    width, height = 1000, 1000

    def tag_redraw(self):
        pass


class Ev:
    def __init__(self, t, v, x, y):
        self.type, self.value = t, v
        self.mouse_region_x, self.mouse_region_y = x, y
        self.alt = self.shift = self.ctrl = False


class Shim:
    def report(self, kind, msg):
        self.reports.append((kind, msg))


for n in ('modal', '_press_to_draw', '_begin_draw', '_finish_draw', '_cleanup', '_end', '_update_red', '_begin_press'):
    setattr(Shim, n, getattr(pc.MCH_OT_press_unified, n))
op = Shim()
op.reports = []
op.state, op.down_time, op.anchor, op.pts = 'PRESS', time.perf_counter(), tuple(xy), [tuple(xy)]
op.press, op.region, op.projector, op.make_mesh = press, Region(), TOP, False   # (Alt held: the Line Cut)
op.timer = op.handle = op.handle_red = None
r = op.modal(C, Ev('MOUSEMOVE', 'NOTHING', xy[0] + 40, xy[1]))
check('a press moved on 40 px within the first moment turns into the drawn line', r == {'RUNNING_MODAL'} and op.state == 'DRAW')
check('... the part is put back as it was', len(p.data.vertices) == v0, len(p.data.vertices))
for k in range(1, 16):
    op.modal(C, Ev('MOUSEMOVE', 'NOTHING', xy[0] + 40 + k * 8, xy[1] + k * 3))
C.scene.mch_brush.line_width = 0.08
st.result = 'SPLIT'
n_obj = len(bpy.data.objects)
r = op.modal(C, Ev('LEFTMOUSE', 'RELEASE', xy[0] + 160, xy[1] + 45))
check('... let go: the line is cut, as a Split when the press result is Split (v0.24.106 always Cut)',
      r == {'FINISHED'} and len(bpy.data.objects) > n_obj, (r, op.reports[-1:] if op.reports else None))
st.result = 'CUT'
# 0.24.108 (user) gestures: plain drag = Base Mesh line whose section IS the stamp (as wide / tall as it shows on
# screen, resting on the surface); Alt + drag = Line Cut as wide as the stamp; plain hold = Grow; Alt + hold = Press
fresh()
C = bpy.context
st = C.scene.mch_press
st.shape, st.size = 'MCH_BUILTIN_M_OCTAGON', 40.0
p = cube('P', size=2.0)
C.scene.mch_settings.auto_apply = True
op2 = Shim()
op2.reports = []
xy0 = TOP.to_screen(Vector((-0.6, 0.0, 1.0)))
op2.state, op2.down_time, op2.anchor = 'DRAW', time.perf_counter(), tuple(xy0)
op2.pts = [tuple(TOP.to_screen(Vector((-0.6 + 1.2 * k / 12, 0.0, 1.0)))) for k in range(13)]
op2.press, op2.region, op2.projector, op2.make_mesh = None, Region(), TOP, True
op2.timer = op2.handle = op2.handle_red = None
before = set(bpy.data.objects.keys())
r = op2._finish_draw(C, op2.pts[-1])
new = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before]
span = 2 * 40.0 / 100.0                                       # the stamp's longer side in world units
ok = r == {'FINISHED'} and len(new) == 1
if ok:
    ob = new[0]
    pts3 = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    wy = max(q.y for q in pts3) - min(q.y for q in pts3)
    hz = max(q.z for q in pts3) - min(q.z for q in pts3)
    zlo = min(q.z for q in pts3)
check('plain drag: a Base Mesh line whose section is the stamp - as wide as the stamp on screen', ok and abs(wy - span) < span * 0.08,
      (r, len(new), round(wy, 3) if ok else None, span))
check('... and as tall as it (the stamp itself, not squashed to the Base height)', ok and abs(hz - span) < span * 0.12,
      round(hz, 3) if ok else None)
check('... standing on the surface (its lowest point just under the top face, not half buried)', ok and -0.03 < zlo - 1.0 < 0.005,
      round(zlo - 1.0, 3) if ok else None)
check('... the Base Mesh defaults are untouched by it', C.scene.mch_base.profile_sweep == 'OFF')

for o in list(bpy.data.objects):          # (0.24.109 the cut's depth starts at the first surface it meets: not the line's top)
    if o != p:
        bpy.data.objects.remove(o)
op3 = Shim()
op3.reports = []
op3.state, op3.down_time, op3.anchor = 'DRAW', time.perf_counter(), tuple(xy0)
op3.pts = list(op2.pts)
op3.press, op3.region, op3.projector, op3.make_mesh = None, Region(), TOP, False
op3.timer = op3.handle = op3.handle_red = None
C.scene.mch_cut.depth_mode, C.scene.mch_cut.depth, C.scene.mch_cut.depth_floor = 'SURFACE', 0.3, 'FLAT'
import bmesh as _bm


def vol(ob):
    bm = _bm.new()
    bm.from_mesh(ob.data)
    v = bm.calc_volume()
    bm.free()
    return v


v0 = vol(p)
st.result = 'CUT'
r = op3._finish_draw(C, op3.pts[-1])
removed = v0 - vol(p)
# 0.24.109 (user) the Line Cut is the stamp's section swept along the line, pressed in Max x the part's size: Max 1.0 on
# a 2 m part = through - a slot as wide as the stamp with flat ends (0.8 x 1.2 x 2), not the Cut tool's 0.3 band
exp = span * 1.2 * 2.0
check('Alt + drag: a Line Cut = the stamp swept along the line, Max x part size deep (1.0 x 2 m: through, flat ends)',
      r == {'FINISHED'} and abs(removed - exp) < exp * 0.08, (round(removed, 3), round(exp, 3)))
check('gestures in the operator: plain = make_mesh (Base line / Grow), Alt = cut (Line Cut / Press)',
      'self.make_mesh = not bool(event.alt)' in open(pc.__file__).read()
      and 'typ = GrowPress if self.make_mesh else Press' in open(pc.__file__).read())

check('a press held still is not turned into a line (late-drag window and distance)',
      pc.UNIFIED_LATE_DRAG_PX >= pc.UNIFIED_DRAG_PX and 0.3 <= pc.UNIFIED_LATE_DRAG_SEC <= 1.5
      and pc.UNIFIED_HOLD_SEC >= 0.2)

# --- Grow -------------------------------------------------------------------------------------------------------------
fresh()
C = bpy.context
st = C.scene.mch_press
TILT = cg.OrthoProjector(Euler((math.radians(55), 0, 0)).to_quaternion(), pixels_per_unit=100.0)
plate = cube('Plate', size=2.0)
plate.scale = (1.0, 1.0, 0.04)            # 0.08 thick
bpy.context.view_layer.update()
plate.select_set(True)
C.view_layer.objects.active = plate
xyg = TILT.to_screen(Vector((0, 0, 0.04)))
g = pc.GrowPress(C, plate, pc.stamp_loops(C, xyg, st), TILT, center=xyg, spacing=6.0)
ok = g.cut_to(C, 0.15)
g.finish(C)
grown = g.object
zs = [(grown.matrix_world @ v.co).z for v in grown.data.vertices] if grown else []
check('Grow makes its own part', ok and grown is not None, g.message)
check('... whose bottom stays in the plate (it came out of the back of a thin slanted part)', zs and min(zs) > -0.04 - 1e-3,
      min(zs) if zs else None)
check('... and the selection stays on the part (the next Press does not cut the grown mesh)',
      C.view_layer.objects.active == plate and plate.select_get() and not grown.select_get())

# --- Base Mesh sweep --------------------------------------------------------------------------------------------------
fresh()
C = bpy.context
bs = C.scene.mch_base
check('Base Mesh: the line cross-section setting is not carried from a live part', 'profile_sweep' not in bm_.CARRY_KEYS
      and 'section_width' not in bm_.CARRY_KEYS)
check('hull helper: a square, a straight line has none', len(bm_._hull([(0, 0), (1, 0), (1, 1), (0, 1), (0.5, 0.5)])) == 4
      and bm_._hull([(0, 0), (1, 1), (2, 2)]) is None)
loop_path = []
for i in range(60):                          # a figure eight: its band crosses itself
    a = i / 59 * 2 * math.pi
    loop_path.append((500 + 150 * math.sin(a), 500 + 90 * math.sin(2 * a)))
brush = C.scene.mch_brush
brush.line_width = 0.12
band = lasso_line.line_loop(C, TOP, loop_path, brush)
err = None
try:
    msg = bm_.perform_base(C, [band], TOP, cutter=False, path=loop_path, sweep_style='ALPHA', section_width=0.12)
except Exception as ex:          # noqa
    err = ex
ob = C.active_object
check('Press Alt+draw sweep along a line that loops over itself is made (it failed: "crosses itself")',
      err is None and ob is not None and ob.get(bm_.SWEEP_KEY) and len(ob.data.polygons) > 20, repr(err))
check('... its section is as wide as the drawn line', ob is not None and abs(ob.mch_base.section_width - 0.12) < 1e-6,
      ob.mch_base.section_width if ob else None)
ob.mch_base.height = ob.mch_base.height * 1.5          # a slider on the live part
check('... touching its sliders does not turn later plain lines into shape sweeps', bs.profile_sweep == 'OFF', bs.profile_sweep)

me = bpy.data.meshes.new('D')
me.from_pydata([(-1, 0, 0), (0, 0, 0), (1, 0, 0)], [], [])
bm_._depth_profile_mesh(me, {'axis': 0, 'points': [(-1, 5.0), (1, 5.0)]})
flat = [v.co.z for v in me.vertices]
bm_._depth_profile_mesh(me, {'axis': 0, 'points': [(-1, 4.5), (0, 5.5), (1, 4.5)]})
bent = [v.co.z for v in me.vertices]
check('depth guide: drawn above the part it no longer lifts it; its shape bends it',
      max(abs(z) for z in flat) < 1e-6 and bent[1] - bent[0] > 0.9 and abs(sum(bent) / 3) < 0.5, (flat, bent))

# --- Draw Array -------------------------------------------------------------------------------------------------------
fresh()
C = bpy.context
a, b = cube('A', size=0.5, loc=(0, 0, 0)), cube('B', size=0.5, loc=(1, 0, 0))
G = groups.create(C, [a, b], 'G')
cu = bpy.data.curves.new('Path', 'CURVE')
cu.dimensions = '3D'
sp = cu.splines.new('POLY')
sp.points.add(2)
for i, q in enumerate(((0, 3, 0), (5, 3, 0), (10, 4, 0))):
    sp.points[i].co = (*q, 1.0)
path = bpy.data.objects.new('Path', cu)
path['mch_path'] = True
C.scene.collection.objects.link(path)
ctrl = bpy.data.objects.new('G_DrawArray', None)
C.scene.collection.objects.link(ctrl)
pa = ctrl.mch_draw_array
pa.source, pa.path, pa.count = G, path, 4
pa.active = True
ac._draw_array_pass()
copies = [o for o in bpy.data.objects if o.get(ac.DRAW_TAG) == ctrl.name]
coll = bpy.data.collections.get(ctrl.get(ac.DRAW_COLL_KEY, ''))
check('Draw Array: 4 copies x (2 parts + a root), in their own collection', len(copies) == 12 and coll is not None
      and all(o.name in coll.objects for o in copies), (len(copies), coll and coll.name))
pa.count = 6
copies2 = [o for o in bpy.data.objects if o.get(ac.DRAW_TAG) == ctrl.name]
check('... a slider change does not rebuild inside the slider', len(copies2) == 12)
ac._draw_array_pass()
copies3 = [o for o in bpy.data.objects if o.get(ac.DRAW_TAG) == ctrl.name]
check('... the next timer pass does', len(copies3) == 18, len(copies3))
names = sorted(o.name for o in copies3)
ac._draw_array_pass()
check('... nothing changed: nothing rebuilt', sorted(o.name for o in bpy.data.objects if o.get(ac.DRAW_TAG) == ctrl.name) == names)
ctrl[ac.DRAW_BUILT_KEY] = 'something older'          # an undo step brought back copies of other settings
ac._draw_array_pass()
check('... copies that do not match the settings (after an undo) are rebuilt', ctrl[ac.DRAW_BUILT_KEY] != 'something older')
old_max = ac.DRAW_MAX_OBJECTS
ac.DRAW_MAX_OBJECTS = 30
pa.count = 50
ac._draw_array_pass()
n_cap = len([o for o in bpy.data.objects if o.get(ac.DRAW_TAG) == ctrl.name])
check('... a huge count is capped (copies x parts)', n_cap <= 30 and ctrl.get('mch_da_note'), (n_cap, ctrl.get('mch_da_note')))
ac.DRAW_MAX_OBJECTS = old_max
groups.enter_scope(C, G)
groups.auto_group_step(C)
pa.count = 3
ac._draw_array_pass()
for _ in range(4):
    groups.auto_group_step(C)
check('... rebuilt copies made while inside the group never join it',
      not any(o.parent == G for o in bpy.data.objects if o.get(ac.DRAW_TAG) == ctrl.name))
groups.clear_scope(C)
summary()
