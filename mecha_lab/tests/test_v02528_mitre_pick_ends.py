"""0.24.121 (user's pentagon pictures + requests)
- a Sharp mitre at a bend reaches back on its inner side; stations nearer than that (even samples, hand kinks) fold
  their ring through it and the wall showed a notch - they are cleared now (mitre_clearance)
- a loop closed from a view where the start sits at another depth: the depth is spread along the whole closing piece
  (no hairpin at the end); a non-flat Bend loop's transport twist is spread round the loop (a clean seam)
- the R turn preview shows the DRAWN stamp
- Pick: insert_joint anywhere on the line (a new blue ring), ends stay ends; Ends Flat / Round; Detail; negative taper
"""
import json
import math
import time

from _harness import bmesh, bpy, check, fresh, non_manifold, summary
from mathutils import Euler, Quaternion, Vector

import mecha_lab
from mecha_lab import base_mesh, core_geometry as cg, line_hud, press_cut as pc

fresh()
mecha_lab.register()
C = bpy.context
PPU = 300.0
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=PPU)
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0.0, 0.0)).to_quaternion(), pixels_per_unit=PPU)
RIGHT = cg.OrthoProjector(Euler((math.pi / 2, 0.0, math.pi / 2)).to_quaternion(), pixels_per_unit=PPU)
PENT = [[(0.5 * math.cos(math.tau * k / 5 + math.pi / 2), 0.5 * math.sin(math.tau * k / 5 + math.pi / 2)) for k in range(5)]]
SQ = [[(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]]


class Region:
    width, height = 2000, 1400

    def tag_redraw(self):
        pass


class Shim:
    def report(self, kind, msg):
        self.reports.append((kind, msg))


for n in ('_finish_draw', '_cleanup'):
    setattr(Shim, n, getattr(pc.MCH_OT_press_unified, n))


def stroke(proj, world_pts):
    op = Shim()
    op.reports = []
    op.state, op.down_time = 'DRAW', time.perf_counter()
    op.pts = [tuple(proj.to_screen(Vector(q))) for q in world_pts]
    op.anchor = op.pts[0]
    op.press, op.region, op.projector, op.make_mesh = None, Region(), proj, True
    op.timer = op.handle = op.handle_red = None
    op.cont_end = None
    return op._finish_draw(C, op.pts[-1]), op


def setup(corner='SHARP', up='BEND', size=33.6, pent=True):
    global C
    fresh()
    C = bpy.context
    st = C.scene.mch_press
    st.size, st.rotation, st.result = size, 0.0, 'CUT'
    if pent:
        st.drawn = True
        pc.DRAWN[0] = PENT
    else:
        st.drawn, st.shape = False, 'MCH_BUILTIN_M_OCTAGON'
    C.scene.mch_settings.auto_apply = True
    C.scene.mch_base.line_corner, C.scene.mch_base.corner_radius, C.scene.mch_base.line_up = corner, 1.0, up
    pc.CONTINUE['base'] = pc.CONTINUE['cut'] = None
    return st


def dense(a, b, step=2.0 / PPU):
    a, b = Vector(a), Vector(b)
    n = max(1, int((b - a).length / step))
    return [tuple(a + (b - a) * (k / n)) for k in range(n + 1)]


def ring_folds(co, nn, closed=False):
    """Consecutive rings (nn verts each, creation order): pairs where a vertex goes BACKWARDS along the centreline."""
    rings = [co[i:i + nn] for i in range(0, len(co) - len(co) % nn, nn)]
    cents = [sum(r, Vector()) / len(r) for r in rings]
    pairs = list(zip(range(len(rings)), range(1, len(rings)))) + ([(len(rings) - 1, 0)] if closed else [])
    folds = 0
    for i, j in pairs:
        t = cents[j] - cents[i]
        if t.length < 1e-9:
            continue
        t.normalize()
        if any((rings[j][k] - rings[i][k]).dot(t) < -1e-6 for k in range(nn)):
            folds += 1
    return folds, len(rings)


def ob_folds(ob, closed=False):
    d = json.loads(ob[base_mesh.SWEEP_KEY])
    nn = len(d['loops'][0])
    co = [v.co.copy() for v in ob.data.vertices]
    return ring_folds(co, nn, closed)


# --- 1. the mitre clearance in the builder --------------------------------------------------------------------------
def build(path, corner='SHARP'):
    st_ = base_mesh._SweepCutterSettings(0.224, 0.224, 0.0, corner, 1.0)
    st_.is_cutter = False
    bm = base_mesh._build_sweep_bmesh({'path': [list(q) for q in path], 'loops': SQ}, st_)
    co = [v.co.copy() for v in bm.verts]
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return co, nm


for legs, turn in (((0.223, 0.317), 90.0), ((0.25, 0.35), 60.0), ((0.5, 0.5), 120.0)):
    a = math.radians(180.0 - turn)
    path = ((0.0, 0.0), (legs[0], 0.0), (legs[0] + legs[1] * math.cos(math.pi - a), legs[1] * math.sin(math.pi - a)))
    co, nm = build(path)
    folds, nr = ring_folds(co, 4)
    check(f'Sharp {turn:.0f} deg bend, legs {legs} (not multiples of the sample step): no ring folds back through the mitre, closed',
          folds == 0 and nm == 0 and nr >= 3, (folds, nm, nr))
co, nm = build(((0.0, 0.0), (0.223, 0.0), (0.223, 0.317)), 'ROUND')
folds, nr = ring_folds(co, 4)
check('... Round on the same legs still arcs (many rings), closed, no folds', folds == 0 and nm == 0 and nr >= 8, (folds, nm, nr))

# --- 2. the user's pentagon L (a continued one-stroke L, Sharp + Bend, thickness 0.224) -----------------------------
st = setup()
r1, _ = stroke(TOP, dense((-2.0, 0.0, 0.0), (0.0, 0.0, 0.0)))
ob = C.active_object
rad = 8.0 / PPU
arc = [(rad - rad * math.cos(x), 1.2 - rad + rad * math.sin(x), 0.0) for x in [math.radians(k * 15) for k in range(1, 6)]]
r2, op2 = stroke(TOP, dense((0.0, 0.0, 0.0), (0.0, 1.2 - rad, 0.0)) + arc + dense((rad, 1.2, 0.0), (1.5, 1.2, 0.0)))
folds, nr = ob_folds(ob)
check('pentagon stamp, Sharp + Bend: a first stroke then a one-stroke L from its end (a hand-like rounded corner): both '
      '90 deg corners mitred clean - no notch (no ring folded back), closed',
      r1 == {'FINISHED'} and r2 == {'FINISHED'} and folds == 0 and non_manifold(ob) == 0 and nr >= 20,
      (r2, folds, nr, non_manifold(ob), op2.reports[-1][1][:60] if op2.reports else None))
check('... width 0.224 as drawn, two bends only (joint + corner)', abs(ob.mch_base.section_width - 0.224) < 0.01
      and len(json.loads(ob[base_mesh.SWEEP_KEY]).get('path3') or json.loads(ob[base_mesh.SWEEP_KEY])['path']) <= 8)

# --- 3. closing a loop from a view where the start sits at another depth -------------------------------------------
st = setup()
stroke(TOP, dense((0.0, 0.0, 0.0), (2.0, 0.0, 0.0)))
ob = C.active_object
stroke(FRONT, dense((2.0, 0.0, 0.0), (2.0, 0.0, 1.0)))                                   # up 1 m
stroke(TOP, dense((2.0, 0.0, 1.0), (2.0, 2.0, 1.0)))                                     # round the top, 1 m up
stroke(TOP, dense((2.0, 2.0, 1.0), (0.0, 2.0, 1.0)))
wob = [(0.0, 2.0 - 2.0 * k / 8, 1.0) for k in range(9)]                                 # back over the start (1 m below)
for k in range(1, 8):
    wob[k] = (0.03 * (-1) ** k, wob[k][1], 1.0)                                          # a wobbly hand
r3, op3 = stroke(TOP, wob)
d = json.loads(ob[base_mesh.SWEEP_KEY])
p3 = [tuple(q) for q in d.get('path3') or d['path']]
z0 = p3[0][2]                                                                             # (object-local: the start's z)
joints = d.get('joints', [])
last_j = max(j for j in joints if j < len(p3) - 1) if joints else 1
closing = p3[last_j:]
s_, ramp_ok = 0.0, True
total = sum(math.dist(closing[k], closing[k + 1]) for k in range(len(closing) - 1)) + math.dist(closing[-1], p3[0])
dz = closing[0][2] - z0
for k in range(1, len(closing)):
    s_ += math.dist(closing[k - 1], closing[k])
    want_z = closing[0][2] - dz * s_ / max(total, 1e-9)
    if abs(closing[k][2] - want_z) > 0.06:
        ramp_ok = False
folds, nr = ob_folds(ob, closed=True)
check('a loop closed from the top view while the start lies 1 m below the stroke\'s plane: CLOSED, the depth spread '
      'evenly along the whole closing piece (z falls with arc length, no hairpin at the end), no folds, watertight',
      r3 == {'FINISHED'} and d.get('closed') is True and abs(dz - 1.0) < 0.05 and ramp_ok and folds == 0 and non_manifold(ob) == 0,
      (r3, d.get('closed'), round(dz, 3), [tuple(round(c, 2) for c in q) for q in closing][:6], folds, non_manifold(ob)))

# --- 4. the transport twist of a non-flat Bend loop is spread round it ----------------------------------------------
def seam_and_twist(path, fr):
    n = len(path)
    out = []
    for i in range(n):
        j = (i + 1) % n
        T = fr[j][0].cross(fr[j][1])
        Vc = (fr[i][1] - T * fr[i][1].dot(T)).normalized()
        out.append(math.degrees(math.atan2(Vc.cross(fr[j][1]).dot(T), Vc.dot(fr[j][1]))))
    return out


saddle = [(2.0 * math.cos(a), 2.0 * math.sin(a), 0.6 * math.sin(2 * a)) for a in [math.tau * k / 24 for k in range(24)]]
tw = seam_and_twist(saddle, base_mesh.sweep_frames(saddle, None, closed=True))
check('a 24-point saddle loop carried round (Bend): the seam twist is spread - at most 0.5 deg between ANY two rings, '
      'the seam included (was all of it at the seam)', max(abs(t) for t in tw) < 0.5, (round(max(abs(t) for t in tw), 2), round(sum(tw), 2)))
flat_sq = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 2.0, 0.0), (0.0, 2.0, 0.0)]
tw0 = seam_and_twist(flat_sq, base_mesh.sweep_frames(flat_sq, None, closed=True))
check('... a flat square loop is untouched (no twist anywhere)', max(abs(t) for t in tw0) < 1e-3)
st = setup()
stroke(TOP, dense((0.0, 0.0, 0.0), (2.0, 0.0, 0.0)))
ob = C.active_object
stroke(FRONT, dense((2.0, 0.0, 0.0), (2.0, 0.0, 1.5)))
stroke(RIGHT, dense((2.0, 0.0, 1.5), (2.0, 1.5, 1.5)))
r4, op4 = stroke(TOP, dense((2.0, 1.5, 1.5), (0.0, 0.0, 1.5)))
folds, nr = ob_folds(ob, closed=True)
check('a four-view 3D loop with sharp corners (the user\'s case): closes, watertight, no ring folds through a mitre',
      r4 == {'FINISHED'} and json.loads(ob[base_mesh.SWEEP_KEY]).get('closed') is True and folds == 0 and non_manifold(ob) == 0,
      (r4, folds, non_manifold(ob), op4.reports[-1][1][:70] if op4.reports else None))

# --- 5. the R turn preview shows the drawn stamp ---------------------------------------------------------------------
st = setup()
check('turn_loops: with a drawn stamp the R turn shows THAT outline, not the saved shape; without one the saved shape',
      pc.turn_loops(st, st.shape) is pc.DRAWN[0] and (setattr(st, 'drawn', False) or pc.turn_loops(st, st.shape) is not pc.DRAWN[0]))
src_p = open(pc.__file__).read()
check('... wired into the turn operator', 'self.norm = turn_loops(owner, stem)' in src_p)

# --- 6. Pick: insert_joint, Ends, Detail, negative taper ---------------------------------------------------------------
st = setup(pent=False)
stroke(TOP, dense((-2.0, 0.0, 0.0), (2.0, 0.0, 0.0), step=0.2))
ob = C.active_object
n0 = len(ob.data.vertices)
got = base_mesh.insert_joint(ob, Vector((0.3, 0.0, 0.0)))
d = json.loads(ob[base_mesh.SWEEP_KEY])
check('Pick (insert_joint) in the middle of a straight line: a new path point on the line, a joint there (a blue ring), '
      'the mesh unchanged in shape', got == (1, False) and len(d['path']) == 3 and abs(d['path'][1][0] - 0.3) < 1e-4
      and d.get('joints') == [1] and len(base_mesh.sweep_joints(ob)) == 1 and non_manifold(ob) == 0, (got, d['path'], d.get('joints')))
mv = base_mesh.move_joint(ob, 1, Vector((0.3, 0.6, 0.0)))
d = json.loads(ob[base_mesh.SWEEP_KEY])
check('... dragged: the line bends there (a V), the ends stay, closed', mv and abs(d['path'][1][1] - 0.6) < 1e-4
      and d['path'][0] == [-2.0, 0.0] and d['path'][2] == [2.0, 0.0] and non_manifold(ob) == 0)
got_e = base_mesh.insert_joint(ob, Vector((1.995, 0.0, 0.0)))
got_s = base_mesh.insert_joint(ob, Vector((-1.995, 0.0, 0.0)))
check('... picked within 2 % of an end: that END is grabbed (no new joint)', got_e == (2, True) and got_s == (0, True)
      and json.loads(ob[base_mesh.SWEEP_KEY]).get('joints') == [1], (got_e, got_s))
st = setup(pent=False)                                              # a fresh straight line for Detail / Ends / taper
stroke(TOP, dense((-2.0, 0.0, 0.0), (2.0, 0.0, 0.0), step=0.2))
ob = C.active_object
w_ = float(ob.mch_base.section_width)
n1 = len(ob.data.vertices)
ob.mch_base.line_detail = 3.0
n3 = len(ob.data.vertices)
ob.mch_base.line_detail = 1.0
check('Detail 3 x: about three times the rings along the line, closed', n3 > 2.2 * n1 and len(ob.data.vertices) == n1
      and non_manifold(ob) == 0, (n1, n3))
co = [ob.matrix_world @ v.co for v in ob.data.vertices]
x_flat = (min(v.x for v in co), max(v.x for v in co))
ob.mch_base.line_end = 'ROUND'
co = [ob.matrix_world @ v.co for v in ob.data.vertices]
tris = sum(1 for f in ob.data.polygons if len(f.vertices) == 3)
check('Ends Round: a dome past each end (out by about half the section), watertight, fans onto two poles; Flat ended at the path',
      non_manifold(ob) == 0 and abs(x_flat[0] + 2.0) < 1e-3 and abs(x_flat[1] - 2.0) < 1e-3
      and min(v.x for v in co) < -2.0 - 0.3 * w_ and max(v.x for v in co) > 2.0 + 0.3 * w_ and tris >= 2 * 8,
      (tuple(round(c, 3) for c in x_flat), round(min(v.x for v in co), 3), round(max(v.x for v in co), 3), round(w_, 3), tris))
ob.mch_base.line_end = 'FLAT'
ob.mch_base.section_taper = -0.6
co = [ob.matrix_world @ v.co for v in ob.data.vertices]
left = [v for v in co if v.x < -1.9]
mid = [v for v in co if abs(v.x) < 0.15]
span = lambda vs: max(v.y for v in vs) - min(v.y for v in vs)
check('End Taper below 0: the ends grow, the middle keeps its size, closed',
      left and mid and span(left) > 1.3 * span(mid) and abs(span(mid) - w_) < 0.15 * w_
      and non_manifold(ob) == 0 and C.scene.mch_base.bl_rna.properties['section_taper'].hard_min <= -1.0,
      (round(span(left), 3) if left else None, round(span(mid), 3) if mid else None, round(w_, 3)))
ob.mch_base.section_taper = 0.0

# --- 7. the HUD wiring --------------------------------------------------------------------------------------------------
lay = line_hud.hud_layout((500.0, 500.0), 1000.0, 1000.0, round_on=True)
icons = {e.identifier for e in bpy.types.UILayout.bl_rna.functions['label'].parameters['icon'].enum_items}
check('the Line HUD has Pick and Ends dots under Move / Section, a Detail slider under the thickness one, their operators, '
      'the window flag, the path gizmo; icons exist',
      all(k in lay for k in ('pick', 'ends', 'detail')) and lay['ends'][1] < lay['section'][1] < lay['pick'][1] < lay['move'][1]
      and lay['detail'][1] < lay['radius'][1] < lay['thick'][1] and hasattr(bpy.ops.mch, 'line_pick_toggle')
      and hasattr(bpy.ops.mch, 'line_end_toggle') and hasattr(bpy.types.WindowManager, 'mch_line_pick')
      and line_hud.MCH_GT_line_path.bl_idname == 'MCH_GT_line_path' and 'MCH_GT_line_path' in str(line_hud.CLASSES)
      and {'PIVOT_CURSOR', 'MESH_CYLINDER', 'MESH_CAPSULE'} <= icons, lay)
lay_b = line_hud.hud_layout((500.0, 5.0), 1000.0, 1000.0)
check('... the five-dot column stays inside the region at the bottom edge', lay_b['ends'][1] >= line_hud.BTN / 2, lay_b['ends'])
check('... a new stroke turns Pick off like Move; the sidebar and Line Section box show Detail and Ends; keys carried',
      'context.window_manager.mch_line_pick = False' in src_p and "section.prop(base, 'line_detail', slider=True)" in src_p
      and "row.prop(p, 'line_end', expand=True)" in open(mecha_lab.ui_tool_settings.__file__).read()
      and 'line_detail' in base_mesh.SETTING_KEYS and 'line_end' in base_mesh.CARRY_KEYS)
summary()
