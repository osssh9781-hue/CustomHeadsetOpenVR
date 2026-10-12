"""Headless geometry regression for Cut / Split (no GUI events involved).

The interactive operator turns mouse input into screen loops; here the same
``perform_*`` functions are driven with deterministic projectors.
"""
import math
import sys
import time

from _harness import (bpy, check, cube, cylinder, fresh, non_manifold, select_only, sphere,
                      summary, volume, mesh_obj, bmesh)
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce

TIMINGS = []


class PerspProjector:
    """Pinhole camera looking down -Z from ``eye`` (tests perspective frustums)."""

    def __init__(self, eye=Vector((0.0, 0.0, 6.0)), focal=900.0, size=(1000, 1000)):
        self.eye = Vector(eye)
        self.f = focal
        self.size = size
        self.view_dir = Vector((0, 0, -1))
        self.is_perspective = True

    def ray(self, xy):
        d = Vector(((xy[0] - self.size[0] / 2) / self.f, (xy[1] - self.size[1] / 2) / self.f, -1.0)).normalized()
        return self.eye.copy(), d

    def to_screen(self, co):
        v = Vector(co) - self.eye
        if v.z >= 0:
            return None
        return (self.size[0] / 2 + self.f * v.x / -v.z, self.size[1] / 2 + self.f * v.y / -v.z)


TOP = cg.OrthoProjector(Quaternion())                                   # looking down -Z
OBLIQUE = cg.OrthoProjector(Quaternion((1, 0, 0), math.radians(35)) @ Quaternion((0, 0, 1), math.radians(25)))
C = bpy.context


def call(op, **kw):
    """Run an operator; ERROR reports raise in background mode -> return {'CANCELLED'}."""
    try:
        return op(**kw)
    except RuntimeError as ex:
        print('  (operator reported)', str(ex).splitlines()[0])
        return {'CANCELLED'}


def timed(label, fn):
    t0 = time.perf_counter()
    out = fn()
    TIMINGS.append((label, (time.perf_counter() - t0) * 1000.0))
    return out


def corners_intact(ob, size=1.0):
    co = {tuple(round(c, 5) for c in v.co) for v in ob.data.vertices}
    want = {(x, y, z) for x in (-size, size) for y in (-size, size) for z in (-size, size)}
    return want <= co


def reset():
    fresh()
    s = C.scene
    s.mch_settings.auto_apply = True
    s.mch_cut.depth_mode = 'THROUGH'
    s.mch_cut.edge_finish = 'NONE'
    s.mch_cut.shared_mesh = 'SINGLE'
    s.mch_cut.targets = 'ACTIVE'


mecha_lab.register()
SQUARE = [(450, 450), (550, 450), (550, 550), (450, 550)]

# 1. Each shape cuts a manifold cube into a manifold result -----------------
shapes = {
    'lasso': [(430, 430), (580, 440), (560, 560), (470, 590), (440, 520)],
    'rect': ce.rect_loop((440, 450), (560, 560)),
    'circle': ce.circle_loop((500, 500), (560, 500), 64),
    'ellipse': ce.ellipse_loop((430, 460), (570, 540), 64),
    'curve_lasso': ce.curve_lasso_spline([(430, 430), (570, 430), (570, 570), (430, 570)], [False, False, True, False], [None] * 4, 10),
    'lasso_round_corners': ce.round_corners([(430, 430), (580, 440), (560, 560), (470, 590)], 20, 'ROUND', 6),
    'rect_chamfer_corners': ce.round_corners(ce.rect_loop((440, 450), (560, 560)), 15, 'CHAMFER'),
    'stroke': cg.trim_closing_overlap([(500 + 70 * math.cos(a / 20), 500 + 50 * math.sin(a / 20)) for a in range(0, 140)]),
    'custom_star': ce.custom_loops([[[0.5 * math.cos(-math.pi / 2 + i * math.pi / 5) * (1 if i % 2 == 0 else 0.45),
                                     0.5 * math.sin(-math.pi / 2 + i * math.pi / 5) * (1 if i % 2 == 0 else 0.45)]
                                    for i in range(10)]], (500, 500), 70, 0.3),
}
for name, loop in shapes.items():
    reset()
    t = cube('Target')
    select_only(t)
    v0 = volume(t)
    msg = timed(f'cut {name}', lambda: ce.perform_closed(C, 'CUT', [t], [loop] if not isinstance(loop[0][0], (list, tuple)) else loop, TOP))
    check(f'cut {name}: manifold', non_manifold(t) == 0, non_manifold(t))
    check(f'cut {name}: volume reduced', volume(t) < v0 - 1e-4, (v0, volume(t)))
    check(f'cut {name}: no temp objects left', all(not o.name.startswith('MCH_Cutter') for o in bpy.data.objects))
    check(f'cut {name}: cutter attribute removed', t.data.attributes.get(cg.CUTTER_ATTR) is None)

# 2. Square hole volume is exact; Alt keeps inside ----------------------------
reset()
t = cube('Target')
ce.perform_closed(C, 'CUT', [t], [SQUARE], TOP)
check('square through-hole volume = 8 - 1*2', abs(volume(t) - 6.0) < 1e-4, volume(t))
reset()
t = cube('Target')
ce.perform_closed(C, 'CUT', [t], [SQUARE], TOP, invert=True)
check('Alt (keep inside) volume = 1*2', abs(volume(t) - 2.0) < 1e-4, volume(t))

# 3. Split keeps both parts --------------------------------------------------
reset()
t = cube('Target')
ce.perform_closed(C, 'SPLIT', [t], [SQUARE], TOP)
piece = bpy.data.objects.get('Target_Split')
check('split: piece created', piece is not None)
if piece:
    check('split: volumes sum to original', abs(volume(t) + volume(piece) - 8.0) < 1e-4,
          (volume(t), volume(piece)))
    check('split: both manifold (capped)', non_manifold(t) == 0 and non_manifold(piece) == 0)
reset()
C.scene.mch_cut.split_cap = False
t = cube('Target')
ce.perform_closed(C, 'SPLIT', [t], [SQUARE], TOP)
piece = bpy.data.objects.get('Target_Split')
check('split no-cap: open shells', non_manifold(t) > 0 and piece is not None and non_manifold(piece) > 0)
C.scene.mch_cut.split_cap = True

# 4. Edge finish touches only new edges -------------------------------------
for mode in ('BEVEL', 'CHAMFER'):
    reset()
    C.scene.mch_cut.edge_finish = mode
    C.scene.mch_cut.finish_width = 0.05
    t = cube('Target')
    n_before = len(t.data.polygons)
    ce.perform_closed(C, 'CUT', [t], [SQUARE], TOP)
    check(f'edge finish {mode}: manifold', non_manifold(t) == 0)
    check(f'edge finish {mode}: original cube corners untouched', corners_intact(t))
    check(f'edge finish {mode}: rim beveled (more faces)', len(t.data.polygons) > 12, len(t.data.polygons))

# 5. Shared mesh (Alt+D) ------------------------------------------------------
for policy in ('SINGLE', 'ALL'):
    reset()
    C.scene.mch_cut.shared_mesh = policy
    t = cube('Target')
    twin = t.copy()
    twin.location = (5, 0, 0)
    C.scene.collection.objects.link(twin)
    check(f'shared ({policy}): starts multi-user', t.data.users == 2)
    ce.perform_closed(C, 'CUT', [t], [SQUARE], TOP)
    if policy == 'SINGLE':
        check('shared SINGLE: target cut, twin untouched',
              abs(volume(t) - 6.0) < 1e-4 and abs(volume(twin) - 8.0) < 1e-4 and t.data != twin.data)
    else:
        check('shared ALL: both instances cut, still linked',
              abs(volume(twin) - 6.0) < 1e-4 and t.data == twin.data)

# 6. v0.5.9 regression: Boolean operator on a multi-user mesh ------------------
reset()
t = cube('Target')
twin = t.copy()
twin.location = (5, 0, 0)
C.scene.collection.objects.link(twin)
cutter = cube('Cutter', size=1.0, loc=(1, 1, 1))
select_only(t, cutter)
r = bpy.ops.mch.boolean(operation='DIFFERENCE')
check('mch.boolean on Alt+D mesh succeeds', r == {'FINISHED'} and non_manifold(t) == 0, r)
check('mch.boolean: twin untouched', abs(volume(twin) - 8.0) < 1e-4)

# 7. Existing modifier stack preserved (cut goes into base mesh) -------------
reset()
t = cube('Target')
bev = t.modifiers.new('Bevel', 'BEVEL')
arr = t.modifiers.new('Array', 'ARRAY')
ce.perform_closed(C, 'CUT', [t], [SQUARE], TOP)
check('modifier stack kept', [m.name for m in t.modifiers] == ['Bevel', 'Array'])
check('modifiers still enabled', bev.show_viewport and arr.show_viewport)
check('base mesh cut', abs(volume(t) - 6.0) < 1e-4)

# 8. Failure cases leave the mesh unchanged ------------------------------------
reset()
t = cube('Target')
before = (len(t.data.vertices), len(t.data.polygons))
try:
    ce.perform_closed(C, 'CUT', [t], [[(10, 10), (60, 10), (60, 60)]], TOP)
    check('miss raises', False)
except cg.CutError as ex:
    check('miss raises CutError, mesh unchanged', (len(t.data.vertices), len(t.data.polygons)) == before, ex)
try:
    ce.perform_closed(C, 'CUT', [t], [[(400, 400), (600, 600), (600, 450), (400, 620)]], TOP)
    check('self-intersection raises', False)
except cg.CutError as ex:
    check('self-intersecting outline refused', 'crosses itself' in str(ex), ex)
try:
    ce.perform_closed(C, 'CUT', [t], [ce.rect_loop((300, 300), (700, 700))], TOP, invert=False)
    check('delete-all refused', False)
except cg.CutError as ex:
    check('cut removing everything refused', 'whole object' in str(ex), ex)
check('mesh unchanged after failures', (len(t.data.vertices), len(t.data.polygons)) == before)
check('no leaked cutter objects', [o.name for o in bpy.data.objects] == ['Target'])
t.data.shape_keys or t.shape_key_add(name='Basis')
try:
    ce.perform_closed(C, 'CUT', [t], [SQUARE], TOP)
    check('shape keys refused', False)
except cg.CutError as ex:
    check('shape keys refused with message', 'shape keys' in str(ex), ex)

# 9. Line cuts ---------------------------------------------------------------
reset()
t = cube('Target')
ce.perform_line(C, 'CUT', [t], [(500, 300), (500, 700)], TOP, side_xy=(700, 500))
check('2-point plane cut removes clicked half', abs(volume(t) - 4.0) < 1e-4 and non_manifold(t) == 0, volume(t))
check('plane cut removed +X side', max(v.co.x for v in t.data.vertices) < 1e-4)
reset()
t = cube('Target')
ce.perform_line(C, 'CUT', [t], [(500, 300), (500, 700)], TOP, side_xy=(700, 500), invert=True)
check('Alt plane cut keeps clicked half', min(v.co.x for v in t.data.vertices) > -1e-4)
reset()
t = cube('Target')
ce.perform_line(C, 'SPLIT', [t], [(500, 300), (500, 700)], TOP, side_xy=(500, 300))
piece = bpy.data.objects.get('Target_Split')
check('2-point split: two capped halves', piece is not None and abs(volume(t) - 4) < 1e-4 and
      abs(volume(piece) - 4) < 1e-4 and non_manifold(t) == 0 and non_manifold(piece) == 0)
reset()
t = cube('Target')
ce.perform_line(C, 'CUT', [t], [(450, 300), (520, 500), (450, 700)], TOP, side_xy=(300, 500))
check('polyline open cut: manifold, removed left part', non_manifold(t) == 0 and volume(t) < 8 and
      min(v.co.x for v in t.data.vertices) > -0.6, volume(t))
reset()
t = cube('Target')
try:
    ce.perform_line(C, 'CUT', [t], [(10, 10), (60, 20)], TOP, side_xy=(0, 0))
    check('line miss refused', False)
except cg.CutError as ex:
    check('line that misses refused', 'does not cross' in str(ex), ex)

# 10. Oblique view, non-uniform scale, rotation -------------------------------
reset()
t = cube('Target')
t.scale = (1.5, 0.6, 1.0)
t.rotation_euler = (0.3, 0.2, 0.5)
C.view_layer.update()
ce.perform_closed(C, 'CUT', [t], [ce.circle_loop((500, 500), (540, 500), 48)], OBLIQUE)
check('oblique view + non-uniform scale: manifold', non_manifold(t) == 0)
C.scene.mch_cut.edge_finish = 'BEVEL'
C.scene.mch_cut.finish_width = 0.02
ce.perform_closed(C, 'CUT', [t], [ce.rect_loop((380, 380), (420, 470))], OBLIQUE)
check('second cut with bevel on scaled object: manifold', non_manifold(t) == 0)

# 11. Perspective frustum -----------------------------------------------------
reset()
t = cube('Target')
P = PerspProjector()
ce.perform_closed(C, 'CUT', [t], [ce.circle_loop((500, 500), (560, 500), 64)], P)
top_r = max(math.hypot(v.co.x, v.co.y) for v in t.data.vertices if abs(v.co.z - 1) < 1e-4 and math.hypot(v.co.x, v.co.y) < 0.9)
bot_r = max(math.hypot(v.co.x, v.co.y) for v in t.data.vertices if abs(v.co.z + 1) < 1e-4 and math.hypot(v.co.x, v.co.y) < 0.9)
check('perspective: manifold', non_manifold(t) == 0)
check('perspective: hole follows view rays (wider at far side)', bot_r > top_r * 1.2, (top_r, bot_r))

# 12. Surface depth pocket ---------------------------------------------------
reset()
C.scene.mch_cut.depth_mode = 'SURFACE'
C.scene.mch_cut.depth = 0.3
t = cube('Target')
ce.perform_closed(C, 'CUT', [t], [SQUARE], TOP)
removed = 8.0 - volume(t)
check('surface pocket depth 0.3 -> volume 1*0.3', abs(removed - 0.3) < 0.02, removed)
check('surface pocket manifold', non_manifold(t) == 0)

# 13. Other targets / multi targets -------------------------------------------
for builder, label in ((lambda: cylinder('Cyl', segments=8), 'low-poly cylinder'),
                       (lambda: sphere('Sphere'), 'uv sphere')):
    reset()
    t = builder()
    v0 = volume(t)
    ce.perform_closed(C, 'CUT', [t], [ce.ellipse_loop((450, 420), (560, 580), 64)], OBLIQUE)
    check(f'{label}: manifold result', non_manifold(t) == 0 and volume(t) < v0)
reset()
grid = mesh_obj('Shell', lambda bm: bmesh.ops.create_grid(bm, x_segments=10, y_segments=10, size=1.0))
ce.perform_closed(C, 'CUT', [grid], [SQUARE], TOP)
check('open shell (non-manifold source) is cut', len(grid.data.polygons) < 100)
reset()
C.scene.mch_cut.targets = 'SELECTED'
a = cube('A', loc=(-0.6, 0, 0))
b = cube('B', size=1.0, loc=(4, 0, 0))
select_only(a, b)
ce.perform_closed(C, 'CUT', [a, b], [SQUARE], TOP)
check('multi-target: hit target cut, missed target untouched', volume(a) < 8 and abs(volume(b) - 1.0) < 1e-4)

# 14. Live mode + finalize -----------------------------------------------------
reset()
C.scene.mch_settings.auto_apply = False
t = cube('Target')
select_only(t)
ce.perform_closed(C, 'CUT', [t], [SQUARE], TOP)
live = bpy.data.objects.get('MCH_Cut_Live')
check('live: cutter object kept', live is not None)
check('live: boolean modifier on target', any(m.type == 'BOOLEAN' and m.object == live for m in t.modifiers))
check('live: base mesh not changed yet', abs(volume(t) - 8.0) < 1e-4)
select_only(live)
r = bpy.ops.mch.cut_finalize()
check('live finalize applied', r == {'FINISHED'} and abs(volume(t) - 6.0) < 1e-4, r)
check('live finalize removed cutter + modifier', 'MCH_Cut_Live' not in bpy.data.objects and not t.modifiers)

# 15. Mask ---------------------------------------------------------------------
reset()
t = mesh_obj('Plate', lambda bm: bmesh.ops.create_grid(bm, x_segments=8, y_segments=8, size=1.0))
changed, total = mecha_lab.mask_tools.apply_mask_loops(C, t, [SQUARE], TOP, erase=False)
check('mask: faces added inside square', changed > 0 and total == changed, (changed, total))
changed2, total2 = mecha_lab.mask_tools.apply_mask_loops(C, t, [SQUARE], TOP, erase=True)
check('mask: Alt erase clears them', total2 == 0 and changed2 == changed)

# 16. Smart Fuse ---------------------------------------------------------------
reset()
a = cube('FuseA')
b = cylinder('FuseB', segments=24, radius=0.6, depth=3.0, loc=(0.9, 0, 0))
b.rotation_euler = (math.radians(90), 0, 0)
C.view_layer.update()
select_only(a, b)
r = call(bpy.ops.mch.smart_fuse)
check('smart fuse: overlapping meshes accepted', r == {'FINISHED'}, r)
r = bpy.ops.mch.smart_fuse_confirm()
check('smart fuse confirm applied', r == {'FINISHED'} and 'FuseB' not in bpy.data.objects, r)
check('smart fuse result manifold', non_manifold(a) == 0, non_manifold(a))
check('smart fuse result: no leftover modifiers', not a.modifiers)
reset()
a = cube('FuseA')
b = cube('FuseB', loc=(5, 0, 0))
select_only(a, b)
r = call(bpy.ops.mch.smart_fuse)
check('smart fuse: separate meshes refused safely', r == {'CANCELLED'} and not a.modifiers and
      not b.hide_get(), r)
reset()
a = cube('FuseA')
b = cube('FuseB', loc=(2, 0, 0))     # exactly touching faces
select_only(a, b)
r = call(bpy.ops.mch.smart_fuse)
check('smart fuse: touching-only result reported (no crash)', r in ({'CANCELLED'}, {'FINISHED'}), r)
if r == {'FINISHED'}:
    bpy.ops.mch.smart_fuse_cancel()
check('smart fuse: objects restored after touching case', not a.modifiers and 'FuseB' in bpy.data.objects)

mecha_lab.unregister()
print('\nTIMINGS (ms, headless, includes depsgraph eval):')
for label, ms in TIMINGS:
    print(f'  {label:<22} {ms:8.1f}')
sys.exit(1 if summary() else 0)
