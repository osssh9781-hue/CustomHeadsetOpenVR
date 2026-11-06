"""0.24.108 Press Cut: the Follow floor on a creased part no longer fails, and Grow comes out on a click anywhere.

- (user's screenshot: "Cutter is not watertight (degenerate outline)") Floor = Follow (the default) on a part with
  steps / creases under the stamp: the fold lines' ends now sit exactly on outline points (no T-junction between the
  far cap and the walls) - every one of the twelve cases that failed cuts, and cuts cleanly
- (user: "그냥 그로우 할 때 뷰포트에 클릭해도 그냥 나오게 해줘") Grow with nothing under the stamp: the stamp comes out as a
  mesh on the 3D cursor's plane facing the view; a tap on a part brings it out a visible quarter of the stamp's width
  at once, holding adds height as before
"""
import math
import random

from _harness import bmesh, bpy, check, cube, fresh, non_manifold, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, press_cut as pc

fresh()
mecha_lab.register()
C = bpy.context
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)


def creased(seed):
    """A 2 m box whose top is a 15 x 15 grid with random steps (+-6 cm, 12 cm): creases everywhere."""
    fresh()
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    ob = bpy.context.active_object
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=14, use_grid_fill=True)
    random.seed(seed)
    for v in bm.verts:
        if v.co.z > 0.99:
            v.co.z += random.choice((0.0, 0.0, 0.06, -0.06, 0.12))
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def vol(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    v = bm.calc_volume()
    bm.free()
    return v


# --- Follow on creases ---------------------------------------------------------------------------------------------
fails, slow, tj = [], [], 0
for trial in range(12):
    ob = creased(trial)
    C = bpy.context
    st = C.scene.mch_press
    random.seed(trial)
    st.shape = random.choice(['MCH_BUILTIN_M_OCTAGON', 'MCH_BUILTIN_PENTAGON', 'MCH_BUILTIN_M_SQUARE_NOTCH',
                              'MCH_BUILTIN_M_CORNER_CHAMFER', 'MCH_BUILTIN_PILLS3'])
    st.size = random.choice((30.0, 55.0, 90.0))
    st.floor_mode = 'FOLLOW'
    st.rotation = random.uniform(0, 1.0)
    C.scene.mch_settings.auto_apply = True
    xy = TOP.to_screen(Vector((random.uniform(-0.5, 0.5), random.uniform(-0.5, 0.5), 1.0)))
    v0 = vol(ob)
    pr = pc.Press(C, ob, pc.stamp_loops(C, xy, st), TOP, 'CUT', center=xy, angle=st.rotation, spacing=6.0, follow=True)
    # every fold end is an outline point (what the T-junction fix guarantees)
    loops, folds = pr.loops, pr.sfloor.folds or []
    verts = {(round(q[0], 6), round(q[1], 6)) for lp in loops for q in lp}
    for a_, b_ in folds:
        for e in (a_, b_):
            if (round(e[0], 6), round(e[1], 6)) in verts:
                continue
            d_min = 1e9
            for lp in loops:
                for p_, q_ in zip(lp, lp[1:] + lp[:1]):
                    dx, dy = q_[0] - p_[0], q_[1] - p_[1]
                    l2 = dx * dx + dy * dy or 1e-12
                    t_ = max(0.0, min(1.0, ((e[0] - p_[0]) * dx + (e[1] - p_[1]) * dy) / l2))
                    d_min = min(d_min, math.dist(e, (p_[0] + t_ * dx, p_[1] + t_ * dy)))
            if d_min < 0.3:
                tj += 1
    ok = pr.cut_to(C, 0.25)
    if not ok or non_manifold(ob) != 0 or vol(ob) >= v0 - 1e-6:
        fails.append((trial, st.shape, st.size, pr.message[:60]))
    pr.finish(C)
check('Follow floor on a creased part: 12 random stamps / places all cut (6 of 6 failed before: "not watertight")',
      not fails, fails)
check('... no fold end lies on an outline edge away from its points (the T-junction that broke the cutter)', tj == 0, tj)

# --- Grow on a click anywhere ----------------------------------------------------------------------------------------
fresh()
C = bpy.context
st = C.scene.mch_press
st.shape, st.size, st.grow_edge, st.grow_top = 'MCH_BUILTIN_M_OCTAGON', 40.0, 'SHARP', 'FLAT'
C.scene.cursor.location = (0.0, 0.0, 0.0)
xy = TOP.to_screen(Vector((2.5, 1.5, 0.0)))          # nothing there
g = pc.GrowPress(C, None, pc.stamp_loops(C, xy, st), TOP, center=xy, spacing=6.0)
tap = pc.press_depth(g, st, 0.0)
ok = g.cut_to(C, tap)
g.finish(C)
ob = g.object
co = [ob.matrix_world @ v.co for v in ob.data.vertices] if ob else []
check('Grow with nothing under the stamp: a mesh on the 3D cursor plane, under the mouse', ok and ob is not None
      and non_manifold(ob) == 0 and abs(sum(v.x for v in co) / len(co) - 2.5) < 0.05 and abs(min(v.z for v in co)) < 0.02,
      (round(sum(v.x for v in co) / len(co), 3) if co else None, round(min(v.z for v in co), 3) if co else None))
span = 2 * 40.0 / 100.0
check('... a tap brings it out a quarter of the stamp\'s width (not a hair)', abs(tap - pc.GROW_TAP * span) < 1e-6
      and abs((max(v.z for v in co) - min(v.z for v in co)) - tap) < 0.03, (round(tap, 3), round(max(v.z for v in co) - min(v.z for v in co), 3)))
held = pc.press_depth(g, st, 2.0)
check('... holding adds height (Speed x seconds x size) up to Max', held > tap and held <= g.size * st.max_depth + 1e-9)
C.scene.cursor.location = (0.0, 0.0, 0.7)
g2 = pc.GrowPress(C, None, pc.stamp_loops(C, xy, st), TOP, center=xy, spacing=6.0)
g2.cut_to(C, pc.press_depth(g2, st, 0.0))
z2 = min((g2.object.matrix_world @ v.co).z for v in g2.object.data.vertices)
check('... on the cursor\'s own depth', abs(z2 - 0.7) < 0.02, round(z2, 3))

p = cube('P', size=2.0)
xy = TOP.to_screen(Vector((0, 0, 1.0)))
gp = pc.GrowPress(C, p, pc.stamp_loops(C, xy, st), TOP, center=xy, spacing=6.0)
tap_p = pc.press_depth(gp, st, 0.0)
check('on a part a tap is the same quarter of the stamp (the part size only sets how fast holding grows)',
      abs(tap_p - pc.GROW_TAP * span) < 1e-6 and pc.press_depth(gp, st, 1.0) > tap_p, (round(tap_p, 3), span))
pr = pc.Press(C, p, pc.stamp_loops(C, xy, st), TOP, 'CUT', center=xy, spacing=6.0)
check('a Press (cut) still starts at Start x the part size', abs(pc.press_depth(pr, st, 0.0) - pc.depth_at(st, pr.size, 0.0)) < 1e-9)
src = open(pc.__file__).read()
check('wired: the unified press lets Grow go on with no part under the stamp', 'if target is None and not self.make_mesh:' in src
      and src.count('press_depth(') >= 4)
summary()
