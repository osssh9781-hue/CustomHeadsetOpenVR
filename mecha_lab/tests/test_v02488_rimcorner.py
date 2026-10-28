"""0.24.77 GN Chamfer / Bevel on a cut that runs out over the part's edge (a line / band cut through a plate): where
the rim turns from the face down the side, the profiles just before and after the corner lay behind the corner's own,
the swept band folded back there and the Boolean left a thin spike at both ends of the cut.  They are trimmed to the
corner now.  And an open / broken part takes an Exact difference without Self Intersection on the whole part (~3x
faster), the old way only when that result fell apart."""
import math

from _harness import bpy, check, fresh, non_manifold, summary
import bmesh
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce, lasso_line as ll, rim_sweep as rs

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
S.mch_settings.auto_apply = True
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)


def scr(x, y):
    return (500 + x * 100, 500 + y * 100)


def plate(hole=False):
    """An egg-shaped plate 0.1 thick (like a cut armour part), its top at z 0.1."""
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    pts = [(math.cos(2 * math.pi * i / 48) * (1 + 0.15 * math.sin(2 * math.pi * i / 48)),
            0.7 * math.sin(2 * math.pi * i / 48)) for i in range(48)]
    bm = bmesh.new()
    f = bm.faces.new([bm.verts.new((x, y, 0)) for x, y in pts])
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    for v in [e for e in r['geom'] if isinstance(e, bmesh.types.BMVert)]:
        v.co.z += 0.1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    if hole:                                    # an open part: one side face gone
        side = next(f for f in bm.faces if abs(f.normal.z) < 0.1 and f.calc_center_median().x > 0.9)
        bm.faces.remove(side)
    me = bpy.data.meshes.new('Plate')
    bm.to_mesh(me)
    ob = bpy.data.objects.new('Plate', me)
    S.collection.objects.link(ob)
    C.view_layer.objects.active = ob
    ob.select_set(True)
    return ob


def tips(ob, lim=0.45):
    """Points where the surface comes to a needle (the corners' angles add up to less than ``lim`` x 180 degrees)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    out = []
    for v in bm.verts:
        if v.link_faces and all(e.is_manifold for e in v.link_edges):
            if sum(lp.calc_angle() for lp in v.link_loops) < lim * math.pi:
                out.append(tuple(round(c, 3) for c in v.co))
    bm.free()
    return out


def band_cut(ob, finish):
    cut = S.mch_cut
    cut.depth_mode, cut.gn_finish, cut.gn_width, cut.gn_segments = 'THROUGH', finish, 0.03, 3
    path = [scr(-0.3 + 0.6 * i / 20, -1.0 + 2.0 * i / 20) for i in range(21)]
    return ce.perform_closed(C, 'CUT', [ob], [ll.band(path, 16)], TOP, False)


used = []
real_sweep = rs._sweep
rs._sweep = lambda me, n, fast: used.append(fast) or real_sweep(me, n, fast)
real_trim = rs.trim_corners

rs.trim_corners = lambda *a, **k: 0             # how it was
ob = plate()
band_cut(ob, 'CHAMFER')
before = tips(ob)
check('(before) A band cut through a plate with GN Chamfer: needle points at the cut\'s ends (the folded band)',
      len(before) >= 1, before)
rs.trim_corners = real_trim

for finish in ('CHAMFER', 'BEVEL'):
    used.clear()
    ob = plate()
    msg = band_cut(ob, finish)
    check(f'GN {finish.title()}: the profiles at the corners are trimmed, no needle point left, the part closed',
          rs.LAST.get('trimmed', 0) >= 2 and not tips(ob) and non_manifold(ob) == 0 and f'GN {finish.title()}' in msg,
          (rs.LAST.get('trimmed'), tips(ob), msg))
    check(f'... and its band no longer crosses itself: straight into the Manifold difference (was the Exact '
          f'self-union first)', used == ['band', 'direct'], used)

# trim_corners alone: a rim running along +x that turns down (-z) at x = 0 (a cut coming out over the part's side)
bm = bmesh.new()
vs = [bm.verts.new((x, 0, 0)) for x in (0.1, 0.05, 0.02, 0.01)] + [bm.verts.new((0, 0, 0))] + \
     [bm.verts.new((0, 0, -z)) for z in (0.01, 0.02, 0.05, 0.1)]
edges = [bm.edges.new((a, b)) for a, b in zip(vs, vs[1:])]
bm.verts.index_update()
W = 0.03
prof = {}
for v in vs:                                    # the wall-side profile point: W into the wall from each edge
    p = v.co
    if v.co.z == 0 and v.co.x > 0:
        prof[v.index] = [p + Vector((0, 0, -W))]
    elif v.co.x == 0 and v.co.z < 0:
        prof[v.index] = [p + Vector((W, 0, 0))]
    else:
        prof[v.index] = [p + Vector((W, 0, -W))]          # the corner: mitred
n = rs.trim_corners(edges, prof, W)
q = {('x' if v.co.z == 0 else 'z', round(v.co.x - v.co.z, 3)): prof[v.index][0] for v in vs}
near = [q[('x', 0.02)], q[('x', 0.01)], q[('z', 0.01)], q[('z', 0.02)]]
check('trim_corners: the points closer than the width to the corner go to (just past) the corner\'s point, the ones '
      'further away stay', n == 4 and all((p - Vector((W, 0, -W))).length < 0.002 for p in near)
      and (q[('x', 0.05)] - Vector((0.05, 0, -W))).length < 1e-9 and (q[('z', 0.1)] - Vector((W, 0, -0.1))).length < 1e-9,
      (n, {k: tuple(round(c, 3) for c in v) for k, v in q.items()}))
for v in vs:                                    # a hole's corner (the profiles spread out): nothing moves
    prof[v.index] = [v.co + Vector((-W, 0, W))]
check('... a turn the other way (the offsets spread): nothing is moved', rs.trim_corners(edges, prof, W) == 0)
bm.free()

# an open / broken part
used.clear()
ob = plate(hole=True)
nm0 = non_manifold(ob)
msg = band_cut(ob, 'CHAMFER')
check('An open part: the Exact difference without Self Intersection on the part (not the old all-Exact way)',
      used == ['open'] and 'GN Chamfer' in msg and nm0 > 0 and non_manifold(ob) <= nm0 + 8, (used, nm0, non_manifold(ob)))
check('... the Cut says it is not one clean solid and to Fix Mesh first', 'Fix Mesh' in msg, msg)
used.clear()
real_fair = rs._fair
rs._fair = lambda *a: False                     # as if that result fell apart
ob = plate(hole=True)
msg = band_cut(ob, 'CHAMFER')
check('... a result that fell apart: the old way is tried too (the one with fewer broken edges kept)',
      used == ['open', False] and 'GN Chamfer' in msg and len(ob.data.polygons) > 100, (used, msg))
rs._fair = real_fair
rs._sweep = real_sweep

fresh()
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_grid_add(x_subdivisions=4, y_subdivisions=4)
g = C.active_object
check('The "not one clean solid" hint names Fix Mesh and Remesh', 'Fix Mesh' in cg.overlap_hint(g, (0, 16))
      and 'Remesh' in cg.overlap_hint(g, (0, 16)))
summary()
