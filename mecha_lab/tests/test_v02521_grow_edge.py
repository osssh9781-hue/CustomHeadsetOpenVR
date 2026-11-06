"""0.24.108 Press Cut Alt + hold (Grow): the top edge of what grows out - Sharp / Chamfer / Bevel / Round (dome)
(user: "프레스컷에도 뺄 때 챔퍼랑 베벨 그리고 원형도 넣어 줄래?").

A round stamp grown 0.3 out of the top of a 2 m box, seen from the top: each edge kind keeps a closed solid; Sharp
has a flat top as wide as the stamp; Chamfer / Bevel pull the top in by about Edge Size x the height (Bevel in
several steps); Round is a dome (highest in the middle, falling to the rim); the setting is in the top bar and the
sidebar; the bevel never goes past half the stamp's width.
"""
import math

from _harness import bmesh, bpy, check, cube, fresh, non_manifold, sphere, summary
from mathutils import Euler, Quaternion, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, press_cut as pc, top_bar

src = open(top_bar.__file__).read()

fresh()
mecha_lab.register()
C = bpy.context
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
H = 0.3


def grow(edge, size=0.35, segs=4, stamp='MCH_BUILTIN_M_OCTAGON', part='cube', proj=None):
    fresh()
    st = C.scene.mch_press
    st.shape = stamp
    st.size = 50.0
    st.grow_edge, st.grow_edge_size, st.grow_edge_segments = edge, size, segs
    p = cube('P', size=2.0) if part == 'cube' else sphere('P')
    proj = proj or TOP
    xy = proj.to_screen(Vector((0, 0, 1)))
    g = pc.GrowPress(C, p, pc.stamp_loops(C, xy, st), proj, center=xy, spacing=6.0)
    ok = g.cut_to(C, 0.1)
    ok = g.cut_to(C, H) and ok                  # (a second step: the bevel is made again at the new height)
    g.finish(C)
    ob = g.object
    co = [ob.matrix_world @ v.co for v in ob.data.vertices]
    return g, ob, co, ok


def top_radius(co, z, tol=1e-3):
    rs = [math.hypot(v.x, v.y) for v in co if abs(v.z - z) < tol]
    return max(rs) if rs else 0.0


g, ob, co, ok = grow('SHARP')
ztop = max(v.z for v in co)
r_sharp = top_radius(co, ztop)
check('Sharp: grown, a closed solid, flat top as wide as the stamp', ok and non_manifold(ob) == 0
      and abs(ztop - (1.0 + H)) < 0.02 and r_sharp > 0.4, (round(ztop, 3), round(r_sharp, 3)))
n_sharp = len(ob.data.polygons)

g, ob, co, ok = grow('CHAMFER', size=0.35)
ztop = max(v.z for v in co)
r_ch = top_radius(co, ztop)
off = g.bevel_offset(H)
check('Chamfer: a closed solid, the top pulled in by about Edge Size x height', ok and non_manifold(ob) == 0
      and abs(off - 0.35 * H) < 0.02 and abs((r_sharp - r_ch) - off) < 0.03, (round(off, 3), round(r_sharp - r_ch, 3)))
slant = [p for p in ob.data.polygons if 0.55 < (ob.matrix_world.to_3x3() @ p.normal).normalized().z < 0.85]
check('... one flat cut: a ring of 45 degree faces round the top', len(slant) >= 20, len(slant))
n_ch = len(ob.data.polygons)

g, ob, co, ok = grow('BEVEL', size=0.35, segs=4)
ztop = max(v.z for v in co)
check('Bevel: a closed solid, the rim rounded in several steps (more faces than Chamfer), smooth shaded',
      ok and non_manifold(ob) == 0 and len(ob.data.polygons) > n_ch and any(p.use_smooth for p in ob.data.polygons),
      len(ob.data.polygons))
mid_z = [v.z for v in co if abs(math.hypot(v.x, v.y) - (r_sharp - off * 0.3)) < 0.03 and v.z > 1.0 + H * 0.4]
check('... the rounded rim lies between the top and the side', mid_z and min(mid_z) < ztop - 1e-3, mid_z[:3])

g, ob, co, ok = grow('ROUND')
ztop = max(v.z for v in co)
centre = max((v for v in co if v.z > 1.0), key=lambda v: v.z)
rim = [v.z for v in co if abs(math.hypot(v.x, v.y) - r_sharp) < 0.03 and v.z > 1.0 - 1e-3]
half = [v.z for v in co if abs(math.hypot(v.x, v.y) - r_sharp * 0.5) < 0.04 and v.z > 1.0]
check('Round: a closed dome - highest in the middle', ok and non_manifold(ob) == 0 and abs(ztop - (1.0 + H)) < 0.03
      and math.hypot(centre.x, centre.y) < r_sharp * 0.35, (round(ztop, 3), round(math.hypot(centre.x, centre.y), 3)))
check('... falling to the rim (rim near the surface, half way up between)', rim and max(rim) < 1.0 + H * 0.2
      and half and 1.0 + H * 0.5 < sum(half) / len(half) < ztop, (max(rim) if rim else None,
                                                                    sum(half) / len(half) if half else None))
check('... smooth shaded', all(p.use_smooth for p in ob.data.polygons))
check('dome profile: 0 at the rim, 1 in the middle, round in between', pc.dome_height(0) == 0.0 and pc.dome_height(1) == 1.0
      and 0.85 < pc.dome_height(0.5) < 0.9)

g, ob, co, ok = grow('BEVEL', size=0.9, segs=3)
check('a very big bevel is held to about half the stamp\'s width (no folded top)', ok and non_manifold(ob) == 0
      and g.bevel_offset(H) <= 0.45 * g.inradius + 1e-6 and g.inradius > 0.3, (round(g.bevel_offset(H), 3), round(g.inradius, 3)))

# 0.24.108 (user: "튀어 나올 때 바깥면 안 찌그러져?") Top: Flat - the outer face does not copy the surface's bumps
import random


def bumpy(amp, seed=1):
    """2 m box, its top face subdivided 40 x 40 and displaced by +-amp (a rough sculpted surface)."""
    fresh()
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    ob = C.active_object
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    top = [f for f in bm.faces if f.normal.z > 0.9]
    bmesh.ops.subdivide_edges(bm, edges=list({e for f in top for e in f.edges}), cuts=40, use_grid_fill=True)
    random.seed(seed)
    for v in bm.verts:
        if v.co.z > 0.99 and abs(v.co.x) < 0.99 and abs(v.co.y) < 0.99:
            v.co.z += random.uniform(-amp, amp)
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def grow_on(ob, top, edge='SHARP'):
    st = C.scene.mch_press
    st.shape, st.size, st.grow_edge, st.grow_top = 'MCH_BUILTIN_M_OCTAGON', 50.0, edge, top
    xy = TOP.to_screen(Vector((0, 0, 1)))
    g = pc.GrowPress(C, ob, pc.stamp_loops(C, xy, st), TOP, center=xy, spacing=6.0)
    ok = g.cut_to(C, H)
    co = [g.object.matrix_world @ v.co for v in g.object.data.vertices]
    n = len(co) // 2
    return ok, g.object, [v.z for v in co[:n]], [v.z for v in co[n:]]


ok, ob, bottom, top_f = grow_on(bumpy(0.08), 'FOLLOW')
spread_follow = max(top_f) - min(top_f)
ok2, ob2, bottom2, top_fl = grow_on(bumpy(0.08), 'FLAT')
spread_flat = max(top_fl) - min(top_fl)
check('Top Follow on a bumpy surface (+-0.08): the outer face copies the bumps (that was the only way before)',
      ok and 0.1 < spread_follow < 0.2, round(spread_follow, 3))
check('Top Flat (default): the outer face is one flat plane, resting on the highest bump + the height, a closed solid',
      ok2 and spread_flat < 1e-4 and abs(min(top_fl) - (max(bottom2) + H)) < 0.02 and non_manifold(ob2) == 0,
      (round(spread_flat, 4), round(min(top_fl) - max(bottom2), 3)))
check('... the default is Flat', C.scene.mch_press.bl_rna.properties['grow_top'].default == 'FLAT')
ok3, ob3, _b, top_r = grow_on(bumpy(0.08), 'FLAT', 'ROUND')
check('... Flat + Round: a dome of the full height on that plane, closed', ok3 and non_manifold(ob3) == 0
      and abs((max(top_r) - min(top_r)) - H) < 0.02, round(max(top_r) - min(top_r), 3))
check('top bar: Flat / Follow next to the edge kinds', "_enum_segs(pr, 'grow_top', (('FLAT', 'Flat'), ('FOLLOW', 'Follow')))" in src)

TILT = cg.OrthoProjector(Euler((math.radians(35), 0, 0)).to_quaternion(), pixels_per_unit=100.0)
res = {}
for edge in ('SHARP', 'CHAMFER', 'BEVEL', 'ROUND'):
    for stamp in ('MCH_BUILTIN_M_SQUARE_NOTCH', 'MCH_BUILTIN_PENTAGON'):
        g, ob, co, ok = grow(edge, stamp=stamp, part='sphere', proj=TILT)
        res[(edge, stamp[12:])] = (ok, non_manifold(ob) if ob else -1)
check('on a sphere seen at a slant, with a notched / pointed stamp: every edge kind gives a closed solid',
      all(ok and nm == 0 for ok, nm in res.values()), res)
st = C.scene.mch_press
st.grow_edge = 'BEVEL'
try:
    import mecha_lab.tool_state as ts
    groups = top_bar.groups(C, 'PRESS') if hasattr(top_bar, 'groups') else None
except Exception:      # noqa
    groups = None
check('top bar: a "Grow" group with Sharp / Chamfer / Bevel / Round, Edge size and Segs',
      "out.append(('Grow', grow))" in src and "'grow_edge_size'" in src and "'grow_edge_segments'" in src)
check('sidebar: the Grow Edge box', "Hold: Grow Edge" in open(pc.__file__).read())
summary()
