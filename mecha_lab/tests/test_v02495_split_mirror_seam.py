"""0.24.95 Split holes with a live Mirror (user: "스플릿만 하면 메쉬가 구멍 나"): the base mesh came out closed, the
mirrored part open - points the cut made a hair off the mirror plane (inside the Mirror's Bisect / Merge distance,
0.001, not on it) were half kept by the Bisect and welded to their own reflection.  ``mirror_seam_clear`` moves the
cut's new points out of that band; the part's own points are never moved.

Checks count open edges of the evaluated (mirrored) mesh longer than 1e-5 (a zero-length edge the Mirror's weld
leaves is not a hole)."""
import math

import numpy as np
from _harness import bmesh, bpy, check, cube, cylinder, fresh, sphere, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce, symmetry as sy

mecha_lab.register()
C = bpy.context
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
ANG = cg.OrthoProjector(Quaternion((1, 0, 0), math.radians(35)) @ Quaternion((0, 0, 1), math.radians(25)),
                        pixels_per_unit=100.0)


def open_edges(ob):
    dg = C.evaluated_depsgraph_get()
    e = ob.evaluated_get(dg)
    me = e.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    n = sum(1 for x in bm.edges if not x.is_manifold and x.calc_length() > 1e-5)
    bm.free()
    e.to_mesh_clear()
    return n


def square(proj, c, r):
    cx, cy = proj.to_screen(Vector(c))
    r *= 100
    return [(cx - r, cy - r), (cx + r, cy - r), (cx + r, cy + r), (cx - r, cy + r)]


def ring(proj, c, r, n=24):
    cx, cy = proj.to_screen(Vector(c))
    return [(cx + r * 100 * math.cos(2 * math.pi * i / n), cy + r * 100 * math.sin(2 * math.pi * i / n))
            for i in range(n)]


def split(make, proj, lasso, mode='SPLIT', **settings):
    fresh()
    C.scene.mch_settings.auto_apply = True
    for k, v in settings.items():
        setattr(C.scene.mch_cut, k, v)
    p = make()
    sy.set_mode(C, p, 'MIRROR')
    before = open_edges(p)
    msg = ce.perform_closed(C, mode, [p], [lasso(proj)], proj)
    piece = bpy.data.objects.get('P_Split')
    return before, open_edges(p), (open_edges(piece) if piece else 0), msg


CASES = [
    ('a sphere, a square from the centre line, seen at an angle', lambda: sphere('P'), ANG,
     lambda pr: square(pr, (0.4, 0.0, 0), 0.4), {}),
    ('... High Poly on', lambda: sphere('P'), ANG, lambda pr: square(pr, (0.4, 0.0, 0), 0.4), {'hipoly': True}),
    ('... Side A / B Chamfer, from the top', lambda: sphere('P'), TOP, lambda pr: square(pr, (0.4, 0.0, 0), 0.4),
     {'side_a_finish': 'CHAMFER', 'side_b_finish': 'CHAMFER', 'side_a_width': 0.03, 'side_b_width': 0.03}),
    ('... Side A / B Bevel, a circle across the centre', lambda: sphere('P'), TOP,
     lambda pr: ring(pr, (0.0, 0.1, 0), 0.5),
     {'side_a_finish': 'BEVEL', 'side_b_finish': 'BEVEL', 'side_a_width': 0.03, 'side_b_width': 0.03}),
    ('a cylinder, GN Chamfer, a circle across the centre at an angle', lambda: cylinder('P', segments=24), ANG,
     lambda pr: ring(pr, (0.0, 0.1, 0), 0.5), {'gn_finish': 'CHAMFER', 'gn_width': 0.03}),
    ('a sphere, Gap Split + Side Chamfer / Bevel at an angle', lambda: sphere('P'), ANG,
     lambda pr: square(pr, (0.4, 0.0, 0), 0.4),
     {'split_mode': 'GAP', 'gap_width': 0.05, 'side_a_finish': 'CHAMFER', 'side_b_finish': 'BEVEL',
      'side_a_width': 0.02, 'side_b_width': 0.02}),
]
for name, make, proj, lasso, kw in CASES:
    b0, a, b, msg = split(make, proj, lasso, **kw)
    check(f'Split with a live Mirror - {name}: the mirrored part and the mirrored piece closed (no open edge)',
          b0 == 0 and a == 0 and b == 0 and 'plit: P' in msg, (b0, a, b, msg[:80]))

b0, a, _b, msg = split(lambda: sphere('P'), ANG, lambda pr: square(pr, (0.4, 0.0, 0), 0.4), mode='CUT')
check('Cut with a live Mirror, the same square: closed too (the same path)', b0 == 0 and a == 0 and 'Cut: P' in msg,
      (b0, a, msg[:80]))

# the part's own points a hair off the plane (a seam the Merge welds) are left where they are
fresh()
C.scene.mch_settings.auto_apply = True
p = cube('P', size=2.0)
for v in p.data.vertices:                          # (the -X side moved onto +0.0004: a seam 0.4 mm off the plane)
    if v.co.x < 0:
        v.co.x = 0.0004
p.data.update()
sy.set_mode(C, p, 'MIRROR')
seam = sorted(tuple(round(c, 7) for c in v.co) for v in p.data.vertices if abs(v.co.x - 0.0004) < 1e-7)
ce.perform_closed(C, 'SPLIT', [p], [square(TOP, (0.5, 0.0, 0), 0.25)], TOP)
after = sorted(tuple(round(c, 7) for c in v.co) for v in p.data.vertices if abs(v.co.x - 0.0004) < 1e-7)
check('... the part\'s own points 0.4 mm off the mirror plane (welded by the Mirror) are not moved by a cut',
      len(seam) == 4 and after == seam, (len(seam), len(after)))

# the helper on its own: a new point inside the band moves out to twice the distance, one on the plane stays
fresh()
p = cube('P', size=2.0)
sy.set_mode(C, p, 'MIRROR')
me = p.data.copy()
me.vertices[0].co.x = 0.0006
me.vertices[1].co.x = 0.0
moved = cg.mirror_seam_clear(p, me, None)
xs = np.array([v.co.x for v in me.vertices])
check('mirror_seam_clear: a new point 0.6 mm off the plane moved out to 2 mm, a point on the plane left on it',
      moved == 1 and abs(xs[0] - 0.002) < 1e-6 and xs[1] == 0.0, (moved, round(float(xs[0]), 6), float(xs[1])))
for m in list(p.modifiers):
    p.modifiers.remove(m)
me2 = p.data.copy()
me2.vertices[0].co.x = 0.0006
check('... a part with no live Mirror: nothing moved', cg.mirror_seam_clear(p, me2, None) == 0
      and abs(me2.vertices[0].co.x - 0.0006) < 1e-9)
summary()
