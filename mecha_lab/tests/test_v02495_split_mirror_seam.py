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

# 0.24.95 (user: "미러 안 했는데도 스플릿이 깨져", their part open in many places): a part with a big hole Fix Mesh
# leaves (an open bottom) - the Split / Cut came out with no cut walls (the piece just the surface inside the outline,
# the part open there too).  Now the Boolean sees the hole shut (temporary faces, taken out again): the walls are there,
# and the results are open only where the part was (the bottom plane)


def open_box(bm):
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= 1.6
        v.co.y *= 1.2
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=4, use_grid_fill=True)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().z < -0.2], context='FACES')


def off_plane(me, z):
    bm = bmesh.new()
    bm.from_mesh(me)
    n = sum(1 for e in bm.edges if not e.is_manifold and e.calc_length() > 1e-5
            and not all(abs(v.co.z - z) < 1e-4 for v in e.verts))
    bm.free()
    return n


rows = []
from _harness import mesh_obj
for mode, kw in (('SPLIT', {}), ('SPLIT', {'depth_mode': 'SURFACE', 'depth': 0.2}), ('CUT', {})):
    for c in ((0.6, 0.3, 0.5), (0.0, 0.2, 0.5)):
        fresh()
        C.scene.mch_settings.auto_apply = True
        for k, v in kw.items():
            setattr(C.scene.mch_cut, k, v)
        p = mesh_obj('P', open_box)
        rim_z = min(v.co.z for v in p.data.vertices)
        msg = ce.perform_closed(C, mode, [p], [square(ANG, c, 0.3)], ANG)
        piece = bpy.data.objects.get('P_Split')
        rows.append((mode, c, off_plane(p.data, rim_z), off_plane(piece.data, rim_z) if piece else None,
                     'mch_temp_cap' in p.data.attributes or bool(piece and 'mch_temp_cap' in piece.data.attributes),
                     len([m for m in bpy.data.meshes if m.name.endswith('_mch_cap')]), msg[:20]))
check('A part open at the bottom (a big hole Fix Mesh leaves): Split (Through / From Surface) and Cut have their cut '
      'walls - open edges only on the bottom plane where it was open; the piece kept; no temporary faces left',
      all(r[2] == 0 and (r[0] == 'CUT' or r[3] == 0) and not r[4] and r[5] == 0 for r in rows)
      and all(r[3] is not None for r in rows if r[0] == 'SPLIT'), rows)

# ... but an open SHEET (a flat plate, a bowl, a cloth) is cut as the sheet it is - no temporary cap (it would add walls
# across it): a hole over 40 % of its surface (a bowl: 50 %), or no volume shut in


def plate(bm):
    bmesh.ops.create_grid(bm, x_segments=6, y_segments=6, size=1.0)


def bowl(bm):
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=1.0)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z > 0.01], context='VERTS')


fresh()
caps = {}
for name, b in (('open box', open_box), ('plate', plate), ('bowl', bowl)):
    ob = mesh_obj(name, b)
    got = ce._temp_capped(ob)
    caps[name] = got is not None
    if got is not None:
        bpy.data.meshes.remove(got)
fresh()
C.scene.mch_settings.auto_apply = True
p = mesh_obj('P', plate)
f0 = len(p.data.polygons)
msg = ce.perform_closed(C, 'CUT', [p], [square(TOP, (0.2, 0.1, 0), 0.3)], TOP)
zs = {round(v.co.z, 6) for v in p.data.vertices}
check('... an open sheet is not capped (a flat plate, a bowl - the box with a hole is); a plate cut Through gets a '
      'hole and stays a flat sheet (no walls)',
      caps == {'open box': True, 'plate': False, 'bowl': False} and zs == {0.0} and 'Cut: P' in msg
      and 'mch_temp_cap' not in p.data.attributes, (caps, f0, len(p.data.polygons), sorted(zs)[:4], msg[:30]))
summary()
