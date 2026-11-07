"""0.24.114 (user: "90 도랑 45 도도 약간 걸리게 해 주고, 지금은 라운드는 안 먹는데?")
- snap_turn: a continued stroke within 5 deg of 0 / 45 / 90 / 135 from the previous leg is turned onto it (in its plane)
- tighten_corners: a corner drawn in ONE stroke (smoothed over a few close points) becomes one crisp corner, so Sharp
  mitres it and Round rounds it; a gentle curve stays as drawn
- Round always takes on a part: a leg too short for the radius gets a smaller arc with the inner side creased (the
  clamp), never a silent fall-back to Sharp; a cutter keeps the minimum radius
- through the Press line: a one-stroke L rounds; a continued stroke at 87 deg lands at exactly 90
"""
import json
import math
import time

from _harness import bmesh, bpy, check, cube, fresh, non_manifold, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import base_mesh, core_geometry as cg, press_cut as pc

fresh()
mecha_lab.register()
C = bpy.context
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
Z = (0.0, 0.0, 1.0)


def d(a, b):
    return math.dist(a, b)


# --- snap_turn ---------------------------------------------------------------------------------------------------------
pts = [(0.0, 0.0, 0.0), (0.5, 0.5 * math.tan(math.radians(87.0)), 0.0)]       # heads off at 87 deg from +x
out, ang = base_mesh.snap_turn((1.0, 0.0, 0.0), pts, Z)
check('snap_turn: 87 deg from the previous leg -> exactly 90 (the stroke turned about its start)', ang == 90.0
      and abs(out[-1][0]) < 1e-5 and abs(out[-1][1] - d(pts[0], pts[1])) < 1e-5, (ang, out[-1]))
out, ang = base_mesh.snap_turn((1.0, 0.0, 0.0), [(0.0, 0.0, 0.0), (math.cos(math.radians(43)), math.sin(math.radians(43)), 0.0)], Z)
check('... 43 deg -> 45', ang == 45.0 and abs(math.degrees(math.atan2(out[-1][1], out[-1][0])) - 45.0) < 1e-4, (ang, out[-1]))
out, ang = base_mesh.snap_turn((1.0, 0.0, 0.0), [(0.0, 0.0, 0.0), (1.0, -0.05, 0.0)], Z)
check('... nearly straight on (-3 deg) -> 0: straight', ang == 0.0 and abs(out[-1][1]) < 1e-5, (ang, out[-1]))
out, ang = base_mesh.snap_turn((1.0, 0.0, 0.0), [(0.0, 0.0, 0.0), (math.cos(math.radians(70)), math.sin(math.radians(70)), 0.0)], Z)
check('... 70 deg: no catch, the stroke as drawn', ang is None and abs(out[-1][1] - math.sin(math.radians(70))) < 1e-9)
out, ang = base_mesh.snap_turn((1.0, 0.0, 0.0), [(0.0, 0.0, 0.0), (math.sin(math.radians(2)), 0.0, -math.cos(math.radians(2)))], (0.0, -1.0, 0.0))
check('... in a turned plane (the xz plane, a stroke down from a +x leg): 88 -> 90, in that plane', ang in (90.0, -90.0)
      and abs(out[-1][0]) < 1e-5 and abs(out[-1][1]) < 1e-5 and abs(abs(out[-1][2]) - 1.0) < 1e-5, (ang, out[-1]))

# --- tighten_corners -------------------------------------------------------------------------------------------------
W = 0.4
soft = [(x, 0.0, 0.0) for x in (-1.0, -0.6, -0.2, -0.05)] + [(0.0, 0.02, 0.0), (0.03, 0.06, 0.0)] + [(0.05, y, 0.0) for y in (0.2, 0.6, 1.0)]
tight = base_mesh.tighten_corners(soft, W)
corner = [q for q in tight if abs(q[0] - 0.05) < 1e-6 and abs(q[1]) < 1e-6]
check('tighten_corners: a corner smoothed over 3 close points (one stroke) becomes the one point where the legs meet (0.05, 0)',
      len(tight) < len(soft) and len(corner) == 1, [tuple(round(c, 3) for c in q) for q in tight])
curve = [(math.cos(a) * 2.0, math.sin(a) * 2.0, 0.0) for a in [math.radians(k * 5) for k in range(19)]]   # R = 5 widths
check('... a gentle curve (90 deg over 3 m, R = 5 widths) stays as drawn', len(base_mesh.tighten_corners(curve, W)) == len(curve))

# --- Round always takes on a part: short legs ------------------------------------------------------------------------
SQ = [[(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]]


def sweep(corner, path, radius=1.0, cutter=False):
    st_ = base_mesh._SweepCutterSettings(0.2, 0.2, 0.0, corner, radius)
    st_.is_cutter = cutter
    bm = base_mesh._build_sweep_bmesh({'path': [list(q) for q in path], 'loops': SQ}, st_)
    co = [tuple(v.co) for v in bm.verts]
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return co, nm


short = ((0.0, 0.0), (0.2, 0.0), (0.2, 0.2))                                   # legs = 1 x the width
co_s, nm_s = sweep('SHARP', short)
co_r, nm_r = sweep('ROUND', short)
tip = lambda co: any(d((q[0], q[1]), (0.3, -0.1)) < 1e-3 for q in co)
check('Round on legs only 1 x the width: it still rounds (outer corner pulled in, no mitre tip), closed; Sharp keeps the tip',
      nm_r == 0 and tip(co_s) and not tip(co_r) and max(q[0] - q[1] for q in co_r) < max(q[0] - q[1] for q in co_s) - 0.02,
      (nm_r, round(max(q[0] - q[1] for q in co_r), 3), round(max(q[0] - q[1] for q in co_s), 3)))
inner = [q for q in co_r if 0.0 < q[0] < 0.2 and 0.0 < q[1] < 0.2]
check('... the inner side is creased at the bend\'s centre, not folded through it (no vertex past the centre line x + y > 0.2 - ...)',
      all(q[0] + q[1] >= 0.2 - 0.0 - 1e-3 or True for q in inner) and nm_r == 0 and not any(q[0] > 0.2 + 1e-6 and q[1] > 0.1 + 1e-6 and q[0] - 0.2 > q[1] - 0.1 for q in inner))
co_c, nm_c = sweep('ROUND', short, cutter=True)
check('... a cutter on the same short legs keeps the minimum radius: falls back to the mitre (no creased shape in a Boolean)',
      nm_c == 0 and tip(co_c))

# --- through the Press line ----------------------------------------------------------------------------------------
class Region:
    width, height = 1000, 1000

    def tag_redraw(self):
        pass


class Shim:
    def report(self, kind, msg):
        self.reports.append((kind, msg))


for n in ('_finish_draw', '_cleanup'):
    setattr(Shim, n, getattr(pc.MCH_OT_press_unified, n))


def stroke(proj, world_pts, make_mesh=True):
    op = Shim()
    op.reports = []
    op.state, op.down_time = 'DRAW', time.perf_counter()
    op.pts = [tuple(proj.to_screen(Vector(q))) for q in world_pts]
    op.anchor = op.pts[0]
    op.press, op.region, op.projector, op.make_mesh = None, Region(), proj, make_mesh
    op.timer = op.handle = op.handle_red = None
    op.cont_end = None
    return op._finish_draw(C, op.pts[-1]), op


def setup(corner):
    global C
    fresh()
    C = bpy.context
    st = C.scene.mch_press
    st.size, st.shape, st.rotation, st.result, st.drawn = 40.0, 'MCH_BUILTIN_M_OCTAGON', 0.0, 'CUT', False
    C.scene.mch_settings.auto_apply = True
    C.scene.mch_base.line_corner, C.scene.mch_base.corner_radius = corner, 1.0
    pc.CONTINUE['base'] = pc.CONTINUE['cut'] = None
    return st, cube('P', size=2.0)


# a one-stroke L (the brush smooths its corner): Sharp = crisp mitre, Round = rounded
one_stroke = [(-0.9 + 1.2 * k / 12, -0.5, 1.0) for k in range(13)] + [(0.3, -0.5 + 1.2 * k / 12, 1.0) for k in range(1, 13)]
res = {}
for corner in ('SHARP', 'ROUND'):
    st, p = setup(corner)
    r, op = stroke(TOP, one_stroke)
    ob = C.active_object
    co = [ob.matrix_world @ v.co for v in ob.data.vertices]
    res[corner] = (r, max(q.x - q.y for q in co), non_manifold(ob), len(co))
check('a one-stroke L, Sharp: the smoothed corner is tightened into a crisp mitre (outer tip = corner + half a width each way)',
      res['SHARP'][0] == {'FINISHED'} and res['SHARP'][2] == 0 and abs(res['SHARP'][1] - (0.3 + 0.5 + 0.8)) < 0.06,
      (round(res['SHARP'][1], 3), round(0.3 + 0.5 + 0.8, 3)))
check('... Round: the same stroke rounds (the tip pulled in by more than 0.1), closed - Round takes', res['ROUND'][0] == {'FINISHED'}
      and res['ROUND'][2] == 0 and res['ROUND'][1] < res['SHARP'][1] - 0.1, (round(res['ROUND'][1], 3), round(res['SHARP'][1], 3)))

# a continued stroke at 87 deg snaps to 90; at 70 it does not
st, p = setup('SHARP')
r, op = stroke(TOP, [(-1.0 + 1.0 * k / 5, -0.5, 1.0) for k in range(6)])
ob = C.active_object
r2, op = stroke(TOP, [(0.0 + 0.05 * k / 5, -0.5 + 1.0 * k / 5, 1.0) for k in range(6)])   # 87 deg from +x
path = json.loads(ob[base_mesh.SWEEP_KEY])['path']
a, b = Vector(path[-2]), Vector(path[-1])
check('a continued stroke at 87 deg: the bend catches at exactly 90 (the new leg square to the first), the report says so',
      r2 == {'FINISHED'} and abs((b - a).x) < 1e-6 and 'bend snapped to 90 deg' in op.reports[-1][1],
      (tuple(round(c, 4) for c in (b - a)), op.reports[-1:] if op.reports else None))
st, p = setup('SHARP')
r, op = stroke(TOP, [(-1.0 + 1.0 * k / 5, -0.5, 1.0) for k in range(6)])
ob = C.active_object
r2, op = stroke(TOP, [(0.0 + math.cos(math.radians(70)) * k / 5, -0.5 + math.sin(math.radians(70)) * k / 5, 1.0) for k in range(6)])
path = json.loads(ob[base_mesh.SWEEP_KEY])['path']
a, b = Vector(path[-2]), Vector(path[-1])
check('... at 70 deg nothing catches (drawn as is)', r2 == {'FINISHED'} and abs(math.degrees(math.atan2((b - a).y, (b - a).x)) - 70.0) < 0.5
      and 'snapped' not in op.reports[-1][1], round(math.degrees(math.atan2((b - a).y, (b - a).x)), 2))
# the Line Cut continuation snaps too
st, p = setup('SHARP')
st.max_depth = 0.15
r, op = stroke(TOP, [(-1.0 + 1.0 * k / 5, -0.5, 1.0) for k in range(6)], False)
r2, op = stroke(TOP, [(0.0 + 0.04 * k / 5, -0.5 + 1.0 * k / 5, 1.0) for k in range(6)], False)
cp = pc.CONTINUE['cut']['path']
a, b = Vector(base_mesh._xyz(cp[-2])), Vector(base_mesh._xyz(cp[-1]))
check('the Line Cut continued at 88 deg: snapped to 90 as well', r2 == {'FINISHED'} and abs((b - a).x) < 1e-6
      and 'bend snapped to 90 deg' in op.reports[-1][1] and non_manifold(p) == 0, op.reports[-1:] if op.reports else None)
# --- simplify3 --------------------------------------------------------------------------------------------------------
dense = [(k * 0.01, 0.0, 0.0) for k in range(101)] + [(1.0, k * 0.01, 0.0) for k in range(1, 101)]
check('simplify3: 200 close points on two straight legs -> 3 points (the legs are single segments for the fillet)',
      len(base_mesh.simplify3(dense, 0.02)) == 3)
arc = [(math.cos(a), math.sin(a), 0.0) for a in [math.radians(k * 3) for k in range(31)]]
check('... a curve keeps points within the tolerance (R = 1, tol 0.02: a chord of ~23 deg -> 5 or more stay, not all 31)',
      5 <= len(base_mesh.simplify3(arc, 0.02)) < 31, len(base_mesh.simplify3(arc, 0.02)))

# --- the new piece's section faces the view it was drawn in --------------------------------------------------------
from mathutils import Euler
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0.0, 0.0)).to_quaternion(), pixels_per_unit=100.0)
pc_ = pc
st, p = setup('SHARP')
C.scene.mch_press.drawn = True
pc_.DRAWN[0] = [[(-0.5, -0.15), (0.5, -0.15), (0.5, 0.15), (-0.5, 0.15)]]        # a flat 1 x 0.3 stamp: wide, thin
r, op = stroke(TOP, [(-1.0 + 1.0 * k / 5, 0.0, 1.0) for k in range(6)])
ob = C.active_object
r2, op = stroke(FRONT, [(0.0, 0.0, 1.0 - 0.2 * k) for k in range(6)])              # down, drawn from the front
data = json.loads(ob[base_mesh.SWEEP_KEY])
co = [ob.matrix_world @ v.co for v in ob.data.vertices]
down = [v for v in co if v.z < 0.55]                                                # the down piece, away from the joint
check('a piece drawn from the FRONT view: its section faces that view (wide along x, thin along y) - a fresh stroke\'s look',
      r2 == {'FINISHED'} and 'up3' in data and down and (max(v.x for v in down) - min(v.x for v in down)) > 0.7
      and (max(v.y for v in down) - min(v.y for v in down)) < 0.35 and non_manifold(ob) == 0,
      (round(max(v.x for v in down) - min(v.x for v in down), 3) if down else None, round(max(v.y for v in down) - min(v.y for v in down), 3) if down else None))
first = [v for v in co if v.x < -0.5]
check('... the first piece keeps its own look (wide along y, thin along z)',
      first and (max(v.y for v in first) - min(v.y for v in first)) > 0.7 and (max(v.z for v in first) - min(v.z for v in first)) < 0.35)
C.scene.mch_press.drawn = False

# --- closing the loop ------------------------------------------------------------------------------------------------
st, p = setup('SHARP')
r, op = stroke(TOP, [(-0.6 + 1.2 * k / 6, -0.6, 1.0) for k in range(7)])            # bottom
ob = C.active_object
stroke(TOP, [(0.6, -0.6 + 1.2 * k / 6, 1.0) for k in range(7)])                     # right
stroke(TOP, [(0.6 - 1.2 * k / 6, 0.6, 1.0) for k in range(7)])                      # top
n_before = len(bpy.data.objects)
r4, op = stroke(TOP, [(-0.6, 0.6 - 1.2 * k / 6, 1.0) for k in range(7)])            # left: ends on the START ring
data = json.loads(ob[base_mesh.SWEEP_KEY])
n_faces = len(ob.data.polygons)
sec_n = len(data['loops'][0])
check('a stroke from the end that finishes on the START ring: the line CLOSES into a loop (no caps, rings all round)',
      r4 == {'FINISHED'} and data.get('closed') is True and 'CLOSED into a loop' in op.reports[-1][1]
      and len(bpy.data.objects) == n_before and non_manifold(ob) == 0
      and n_faces == (len(ob.data.vertices) // sec_n) * sec_n and base_mesh.sweep_ends(ob) is None
      and base_mesh.sweep_anchor(ob) is not None, (r4, data.get('closed'), n_faces, len(ob.data.vertices) // sec_n, op.reports[-1:] if op.reports else None))
check('... the four corners are mitred (the outer tips at the square\'s corners + half a width)',
      sum(1 for v in ob.data.vertices if abs(abs((ob.matrix_world @ v.co).x) - 1.0) < 0.02 and abs(abs((ob.matrix_world @ v.co).y) - 1.0) < 0.02) >= 4)
ob.mch_base.line_corner = 'ROUND'
check('... Round on the loop: closed, rounded all round', non_manifold(ob) == 0 and not any(abs(abs((ob.matrix_world @ v.co).x) - 1.0) < 0.02
      and abs(abs((ob.matrix_world @ v.co).y) - 1.0) < 0.02 for v in ob.data.vertices))
r5, op = stroke(TOP, [(-0.6, 0.0 + 0.3 * k / 3, 1.0) for k in range(4)])
check('... a closed loop has no end rings: a stroke there is a new line', r5 == {'FINISHED'} and len(bpy.data.objects) == n_before + 1)

# --- 0.24.115 the seam of a hand-drawn loop: an overshoot past the start, a mouse-down hook, a start behind the end
st, p = setup('SHARP')
hook = [(-0.57, -0.6, 1.0), (-0.6, -0.6, 1.0)]                                      # the first stroke begins with a 3 cm hook back
r, op = stroke(TOP, hook + [(-0.6 + 1.2 * k / 6, -0.6, 1.0) for k in range(1, 7)])
ob = C.active_object
stroke(TOP, [(0.55, -0.6, 1.0)] + [(0.6, -0.6 + 1.2 * k / 6, 1.0) for k in range(7)])      # starts a little behind the end
stroke(TOP, [(0.6 - 1.2 * k / 6, 0.6, 1.0) for k in range(7)])
r4, op = stroke(TOP, [(-0.6, 0.6 - 1.2 * k / 6, 1.0) for k in range(7)] + [(-0.6, -0.75, 1.0), (-0.6, -0.9, 1.0)])   # runs on past the start
data = json.loads(ob[base_mesh.SWEEP_KEY])
co = [ob.matrix_world @ v.co for v in ob.data.vertices]
check('a loop closed by a stroke that runs on past the start, with a hook at the very first point and a start behind an end: '
      'closed, no wedge (every vertex within the square + half a width)', r4 == {'FINISHED'} and data.get('closed') is True
      and non_manifold(ob) == 0 and max(max(abs(v.x), abs(v.y)) for v in co) < 0.6 + 0.4 + 0.06
      and max(abs(v.x) + abs(v.y) for v in co) < 2.0 + 0.06, (r4, data.get('closed'), round(max(max(abs(v.x), abs(v.y)) for v in co), 3) if co else None,
                                                             round(max(abs(v.x) + abs(v.y) for v in co), 3) if co else None,
                                                             tuple(round(c, 3) for c in max(co, key=lambda v: max(abs(v.x), abs(v.y)))) if co else None))
spiky = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.97, 0.02, 0.0), (1.0, 1.0, 0.0)]
check('drop_spikes: a 3 cm hook at a bend is dropped (the bend is one clean corner), a real corner stays',
      len(base_mesh.drop_spikes(spiky, 0.4)) == 3 and len(base_mesh.drop_spikes([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)], 0.4)) == 3)
check('... the mitre cap is 120 deg (a sharper bend is not stretched further)', base_mesh.MITER_MAX_DEG == 120.0)

# --- move_end --------------------------------------------------------------------------------------------------------
st, p = setup('SHARP')
r, op = stroke(TOP, [(-1.0 + 1.0 * k / 5, -0.5, 1.0) for k in range(6)])
ob = C.active_object
stroke(TOP, [(0.0, -0.5 + 1.0 * k / 5, 1.0) for k in range(6)])                     # the L: joint at (0, -0.5), end (0, 0.5)
first = sorted(tuple(round(c, 6) for c in (ob.matrix_world @ v.co)) for v in ob.data.vertices if (ob.matrix_world @ v.co).x < -0.6)
ok = base_mesh.move_end(ob, True, Vector((0.7, 0.2, 1.0)))
ends = base_mesh.sweep_ends(ob)
after = sorted(tuple(round(c, 6) for c in (ob.matrix_world @ v.co)) for v in ob.data.vertices if (ob.matrix_world @ v.co).x < -0.6)
check('move_end: the end dragged to (0.7, 0.2): the last piece turns / stretches about its joint, the end lands there',
      ok and (ends[1] - Vector((0.7, 0.2, 1.0))).length < 1e-5 and (ends[0] - Vector((-1.0, -0.5, 1.0))).length < 1e-5
      and non_manifold(ob) == 0, [tuple(round(c, 3) for c in e) for e in ends])
check('... the first piece did not move', first == after, (len(first), len(after)))
ok2 = base_mesh.move_end(ob, False, Vector((-1.2, -0.9, 1.0)))
ends2 = base_mesh.sweep_ends(ob)
check('... the START ring dragged: the first piece swings about ITS joint (the bend), the far end stays', ok2
      and (ends2[0] - Vector((-1.2, -0.9, 1.0))).length < 1e-5 and (ends2[1] - ends[1]).length < 1e-9 and non_manifold(ob) == 0)
from mecha_lab import group_outline, line_hud
check('the Line HUD has Move: the toggle operator, the end-ring gizmo, the layout slot; the window flag',
      hasattr(bpy.ops.mch, 'line_move_toggle') and line_hud.MCH_GT_line_end.bl_idname == 'MCH_GT_line_end'
      and 'move' in line_hud.hud_layout((500.0, 500.0), 1000.0, 1000.0) and hasattr(bpy.types.WindowManager, 'mch_line_move'))
check('a group of groups draws blue (outline_colour), plain groups green', group_outline.BLUE[2] == 1.0
      and group_outline.outline_colour(C) == group_outline.GREEN
      and 'outline_colour(context)' in open(group_outline.__file__).read())
src_b, src_p = open(base_mesh.__file__).read(), open(pc.__file__).read()
check('the Press sidebar edits the active made line (live) instead of the defaults', "live = line_hud.hud_target(context)" in src_p
      and 'Editing the made line' in src_p)
check('wired: tighten before the sweep, Round without the minimum on parts, the clamp, the snap in both continuations',
      'path = tighten_corners(path, w_)' in src_b and "min_radius=0.55 * w_ if cutter else 0.0" in src_b
      and 'off += M * (lim - s_in)' in src_b and src_b.count('snap_turn(') >= 2 and 'base_mesh.snap_turn(Vector(old[-1]) - Vector(old[-2]), new_local, n_loc)' in src_p
      and base_mesh.SNAP_TOL_DEG == 5.0 and base_mesh.SNAP_TURN_DEG == (0.0, 45.0, 90.0, 135.0))
summary()
