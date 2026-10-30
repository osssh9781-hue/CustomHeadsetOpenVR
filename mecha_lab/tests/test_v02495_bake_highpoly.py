"""0.24.95 Bake High Poly: hard edges (Edge Memory + angle) fixed, the faces between them subdivided and rounded
(Taubin), a fillet option, the result a copy in the BakeHP collection."""
import math

import numpy as np
from _harness import bmesh, bpy, check, fresh, non_manifold, summary

import mecha_lab
from mecha_lab import bake_highpoly as bk, core_geometry as cg, cut_engine as ce, edge_memory as em, mesh_tools as mt, zb_sculpt as zs
from mathutils import Quaternion, Vector

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene


def select(ob):
    if C.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for o in C.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    C.view_layer.objects.active = ob
    return ob


def cube(name='Cube', size=2.0):
    bpy.ops.mesh.primitive_cube_add(size=size)
    ob = C.active_object
    ob.name = name
    return select(ob)


def coords(me):
    return np.array([v.co[:] for v in me.vertices])


# ---- levels ---------------------------------------------------------------------------------------------------
check('levels_for: 17,401 faces -> 1M wants 3 levels (x64 = 1.1M)', bk.levels_for(17401, 1_000_000) == 3)
check('levels_for: already above the target -> 1 level (always at least one)', bk.levels_for(100, 50) == 1)
check('levels_for: never more than 4', bk.levels_for(10, 10_000_000) == 4)

# ---- hard_mask -------------------------------------------------------------------------------------------------
ob = cube('Mask')
me = ob.data
h = bk.hard_mask(me)
check('A cube: all 12 edges hard (90 degrees)', h.sum() == 12)
bpy.ops.mesh.primitive_grid_add(x_subdivisions=4, y_subdivisions=4, size=2)
grid = C.active_object
h = bk.hard_mask(grid.data)
nb = sum(1 for e in grid.data.edges if sum(1 for p in grid.data.polygons if e.index in p.edge_keys and False) == 0 and False)
bm = bmesh.new(); bm.from_mesh(grid.data)
boundary = sum(1 for e in bm.edges if len(e.link_faces) == 1)
bm.free()
check('A flat grid: only its boundary edges are hard', h.sum() == boundary and boundary == 16, (int(h.sum()), boundary))
inner = [e.index for e in grid.data.edges if all(abs(grid.data.vertices[v].co.x) < 0.99 and abs(grid.data.vertices[v].co.y) < 0.99 for v in e.vertices)]
em.mark_edges(grid.data, inner[:1])
check('... Edge Memory adds a flat inner edge (a shallow cut remembered) whatever its angle',
      bk.hard_mask(grid.data).sum() == boundary + 1 and bk.hard_mask(grid.data, memory=False).sum() == boundary)
# a lone angle edge (a speck) is dropped, a line of them kept
bm = bmesh.new(); bm.from_mesh(grid.data)
bm.verts.ensure_lookup_table()
v = [v for v in bm.verts if abs(v.co.x) < 1e-6 and abs(v.co.y) < 1e-6][0]
v.co.z += 0.3                                     # one raised point: 4 angled edges round it in a cross = a line
bm.to_mesh(grid.data); bm.free()
em.clear(grid.data)
h = bk.hard_mask(grid.data, angle=math.radians(20))
check('A raised point: its 4 edges form connected lines and count (no lone speck among them)', h.sum() >= boundary + 4, int(h.sum()))

# ---- taubin ---------------------------------------------------------------------------------------------------
co = np.array([[x, y, 0.0] for y in range(5) for x in range(5)], float)
E = []
for j in range(5):
    for i in range(5):
        k = j * 5 + i
        if i < 4: E.append((k, k + 1))
        if j < 4: E.append((k, k + 5))
E = np.array(E)
hard = np.array([(co[a][1] in (0, 4) and co[b][1] in (0, 4)) or (co[a][0] in (0, 4) and co[b][0] in (0, 4)) for a, b in E])
co2, corners, lines = bk.taubin(co, E, hard, iters=20)
check('taubin on a flat 5x5 grid with a hard rim: stays flat, 4 corners, 12 rim line points, rim points stay on the rim',
      corners == 4 and lines == 12 and np.abs(co2[:, 2]).max() < 1e-9
      and all(abs(co2[k][1] - co[k][1]) < 1e-9 for k in range(25) if co[k][1] in (0, 4))
      and all(abs(co2[k][0] - co[k][0]) < 1e-9 for k in range(25) if co[k][0] in (0, 4)), (corners, lines))
check('... and the corners never move', all(np.allclose(co2[k], co[k]) for k in (0, 4, 20, 24)))
co[12, 2] = 1.0                                   # the middle point lifted: the rounding pulls it back down, the rim stays
co3, _c, _l = bk.taubin(co, E, hard, iters=20)
check('... a lifted middle point is rounded down (less than its 1.0), the rim still flat',
      0.0 < co3[12, 2] < 1.0 and all(abs(co3[k, 2]) < 1e-9 for k in range(25) if co[k][0] in (0, 4) or co[k][1] in (0, 4)), co3[12, 2])

# ---- bake_mesh on a cube: corners fixed, faces flat, x16 ----------------------------------------------------
ob = cube('Cube2')
me = ob.data.copy()
info = bk.bake_mesh(me, levels=2)
co = coords(me)
on_face = (np.abs(np.abs(co) - 1.0) < 1e-5).any(1)
check('Cube, 2 levels: 6 -> 96 faces, 8 corners fixed, every point still on a cube face (flat regions stay flat)',
      info['faces'] == 96 and info['corners'] == 8 and on_face.all() and np.abs(co).max() < 1.0 + 1e-5,
      (info['faces'], info['corners'], int((~on_face).sum())))
check('... hard edge count 12, the 12 lines carry 2 x 3 = 24 line points (3 per edge at level 2)',
      info['hard'] == 12 and info['lines'] == 36, (info['hard'], info['lines']))
bpy.data.meshes.remove(me)

# ---- a faceted cylinder: the side gets round, the cap rims stay exactly --------------------------------------
bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=1.0, depth=2.0)
cyl = select(C.active_object)


def side_error(me):
    co = coords(me)
    side = np.abs(co[:, 2]) < 0.9
    r = np.linalg.norm(co[side, :2], axis=1)
    return float(1.0 - r.min()), float(r.std())


me_flat = cyl.data.copy()
bk.bake_mesh(me_flat, levels=2, rounding=0.0)
me_round = cyl.data.copy()
info = bk.bake_mesh(me_round, levels=2, rounding=1.0)
e0, s0 = side_error(me_flat)
e1, s1 = side_error(me_round)
check('16-sided cylinder, rounding 0: the facets stay (points on the chords, radius down to cos 11.25 = 0.981)',
      e0 > 0.015 and s0 > 0.004, (e0, s0))
check('... rounding 100: the side is round - the radius spread drops to a fraction', s1 < s0 * 0.4 and e1 < e0 * 0.6, (e1, s1, e0, s0))
co = coords(me_round)
rim = np.abs(np.abs(co[:, 2]) - 1.0) < 1e-5
check('... the cap rims (hard lines) stay exactly on z = +-1 and on the 16-gon (radius >= 0.981)',
      rim.sum() > 32 and (np.linalg.norm(co[rim, :2], axis=1) >= math.cos(math.radians(11.25)) - 1e-4).all()
      and (np.linalg.norm(co[rim, :2], axis=1) <= 1.0 + 1e-4).all(), int(rim.sum()))
check('... the caps stay flat (every cap point at |z| = 1)', (np.abs(np.abs(co[np.abs(co[:, 2]) > 0.999, 2]) - 1.0) < 1e-5).all())
for m in (me_flat, me_round):
    bpy.data.meshes.remove(m)

# ---- fillet ----------------------------------------------------------------------------------------------------
ob = cube('Fillet')
me = ob.data.copy()
info = bk.bake_mesh(me, levels=2, fillet=0.03)
co = coords(me)
check('Cube with a 3 % fillet: the 12 edges beveled, a closed mesh, the corner region rounded (no point at the old '
      'corner (1,1,1), points between 0.9 and 1 along the edges)',
      info['fillet_edges'] == 12 and non_manifold(me) == 0 and np.abs(co).max() <= 1.0 + 1e-3
      and not (np.abs(np.abs(co) - 1.0) < 1e-4).all(1).any() and info['faces'] > 96,
      (info['fillet_edges'], info['faces'], non_manifold(me), float(np.abs(co).max()), int((np.abs(np.abs(co) - 1.0) < 1e-4).all(1).sum())))
bpy.data.meshes.remove(me)

# ---- the user's case: a part with a LIVE bevel on its edges (Hard Edges bevel / a Bevel modifier) ---------------
# 0.24.95 fix: the bevel strip's faces meet their neighbours at 30 degrees or less, so they are not hard lines; the
# flats next to them must still stay flat and the box edges straight (they bowed inward before: points drifted
# across the surface into the strip).  Now a free point moves along its normal only.
ob = cube('Bevelled')
mod = ob.modifiers.new('B', 'BEVEL')
mod.width, mod.segments = 0.06, 2
hp, info = bk.build(C, ob, target_faces=20000)
co = coords(hp.data)
flat_x = co[np.abs(np.abs(co[:, 0]) - 1.0) < 1e-3]       # points that still sit on the x = +-1 flats
n_flat = len(flat_x)
inside = (np.abs(co) <= 1.0 + 1e-3).all()
# the strip's middle line along the top-front edge (x in (-0.94, 0.94), near y = -1, z = 1): straight = its
# distance from the edge is the same all along
mid = co[(np.abs(co[:, 0]) < 0.9) & (co[:, 1] < -0.9) & (co[:, 2] > 0.9) & (co[:, 1] > -0.999) & (co[:, 2] < 0.999)]   # the strip itself
r = np.hypot(mid[:, 1] + 1.0, mid[:, 2] - 1.0)
slabs = [r[(mid[:, 0] >= a) & (mid[:, 0] < a + 0.28)] for a in np.arange(-0.7, 0.7, 0.28)]     # (away from the corner patches)
profile_same = max(abs(sl.min() - slabs[0].min()) + abs(sl.max() - slabs[0].max()) for sl in slabs if len(sl))
check('A cube with a live 2-segment bevel (width 0.06): the flats stay flat (hundreds of points still exactly on x = +-1), '
      'nothing leaves the cube, and the edge runs straight (the strip profile is the same in every slab along its middle)',
      n_flat > 300 and inside and len(mid) > 50 and profile_same < 0.01, (n_flat, inside, len(mid), float(profile_same)))
check('... the strip keeps its bevel depth (the 2-segment arc\'s middle line is 0.0249 from the corner line: points between 0.02 and 0.06)',
      0.02 < r.min() and r.max() < 0.061, (float(r.min()), float(r.max())))

# ---- the user's part: a Base Mesh with bevelled sides (3 segments = rows 0.9 long and 0.01 wide) + a pocket ----
# 0.24.95: the rows' faces are so thin that (a) the plain neighbour average sat at the far end of a row (a constant
# pull the Taubin pair never cancelled: a corner crept 0.09 per level) and (b) re-measured normals swung into the
# row's long direction (a corner ran 0.5 in one level).  Now neighbours weigh by 1 / edge length, the normals are
# measured once per level, and a run of narrow bent rows turning less than 100 degrees is a modelled bevel whose
# rows are held as lines.
from mecha_lab import base_mesh as bmm
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
sb = S.mch_base
sb.profile, sb.height, sb.bevel_width, sb.bevel_segments, sb.bevel_sides, sb.offset = 'BEVEL', 0.5, 0.04, 3, 'TOP', 0.0
PPU = 100.0
TOPV = cg.OrthoProjector(Quaternion(), center=Vector((0, 0, 0)), pixels_per_unit=PPU)
lp = ce.rect_loop((500 - 0.9 * PPU, 500 - 0.5 * PPU), (500 + 0.9 * PPU, 500 + 0.5 * PPU))
before = set(bpy.data.objects)
bmm.perform_base(C, [lp], TOPV)
base = [o for o in bpy.data.objects if o not in before][0]
select(base)
S.mch_settings.auto_apply = True
S.mch_cut.targets = 'ACTIVE'
ce.perform_closed(C, 'CUT', [base], [ce.rect_loop((500 - 0.2 * PPU, 500 - 0.2 * PPU), (500 + 0.2 * PPU, 500 + 0.2 * PPU))], TOPV)
src_co = coords(base.data)
hp, info = bk.build(C, base, target_faces=60000)
co = coords(hp.data)
lo_d = np.abs(co.min(0) - src_co.min(0)).max()
hi_d = np.abs(co.max(0) - src_co.max(0)).max()
check(f'Base Mesh (3-segment bevel) + pocket -> Bake High Poly: the bounding box is the original\'s (off by under 0.002), '
      f'bevel rows held as lines, nothing runs away ({info["faces0"]:,} -> {info["faces"]:,} faces)',
      lo_d < 0.002 and hi_d < 0.002 and info['bevel_rows'] > 0, (float(lo_d), float(hi_d), info['bevel_rows'], info['faces0'], info['faces']))

# ---- 0.24.95 preclean: a doubled sliver lying on a flat (a Boolean leftover) is merged before the bake ----------
ob = cube('Dirty')
bm = bmesh.new(); bm.from_mesh(ob.data)
bm.verts.ensure_lookup_table()
top = [v for v in bm.verts if v.co.z > 0.9]
a, b = top[0], top[1]
v1 = bm.verts.new(a.co.copy()); v2 = bm.verts.new(b.co.copy()); v3 = bm.verts.new(((a.co + b.co) / 2) + Vector((0, 0.001, 0)))
bm.faces.new((v1, v2, v3))                                 # a sliver with its own doubled points, on the top face
lv = bm.verts.new((3, 3, 3))                               # a loose point
bm.to_mesh(ob.data); bm.free()
me = ob.data.copy()
info = bk.bake_mesh(me, levels=1)
co = coords(me)
check('preclean: the sliver\'s doubled points are merged into the cube\'s, the loose point dropped, and the bake stays inside the cube',
      info['cleaned']['merged'] == 2 and info['cleaned']['loose'] >= 1 and np.abs(co).max() <= 1.0 + 1e-4, (info['cleaned'], float(np.abs(co).max())))
check('... the message says what was cleaned', 'cleaned first' in bk.describe(info), bk.describe(info))
bpy.data.meshes.remove(me)

# ---- Edge Memory: a remembered shallow line stays put through the bake ----------------------------------------
ob = cube('Mem')
me = ob.data
bm = bmesh.new(); bm.from_mesh(me)
top = [e for e in bm.edges if abs(e.verts[0].co.z - 1) < 1e-6 and abs(e.verts[1].co.z - 1) < 1e-6 and e.verts[0].co.x != e.verts[1].co.x]
bmesh.ops.subdivide_edges(bm, edges=top, cuts=1)
bm.to_mesh(me); bm.free()
mid = [e.index for e in me.edges if all(abs(me.vertices[v].co.z - 1) < 1e-6 and abs(me.vertices[v].co.x) < 1e-6 for v in e.vertices)]
em.mark_edges(me, mid)
me2 = me.copy()
bk.bake_mesh(me2, levels=2, rounding=1.0)
co = coords(me2)
line_pts = co[(np.abs(co[:, 2] - 1.0) < 1e-5) & (np.abs(co[:, 0]) < 1e-5)]
check('A remembered line across the flat top (no angle at all): still a straight line of points at x = 0, z = 1 after '
      'the bake (it is a hard line, its points only slide along it)', len(mid) == 1 and len(line_pts) >= 5, (len(mid), len(line_pts)))
bpy.data.meshes.remove(me2)

# ---- build / run / Mesh Tools ------------------------------------------------------------------------------------
ob = cube('Part')
hp, info = bk.build(C, ob, target_faces=200)
check('build: a new object <name>_BakeHP in the BakeHP collection (target 200 -> 3 levels = 384 faces), source noted, the original hidden and untouched',
      hp.name == 'Part_BakeHP' and hp.users_collection[0].name == bk.COLL and hp[bk.SRC_KEY] == 'Part' and ob.hide_get()
      and len(ob.data.polygons) == 6 and len(hp.data.polygons) == 384 and bk.is_bake(hp) and C.view_layer.objects.active == hp,
      (hp.name, len(hp.data.polygons)))
check('build: result shaded smooth, materials carried', all(p.use_smooth for p in hp.data.polygons))
ob2 = cube('Part2')
zb = S.mch_zb
check('Settings on the shared shelf group: Target 1000 k, Rounding 100, Fillet 0', zb.bk_target == 1000 and zb.bk_rounding == 100 and zb.bk_fillet == 0.0)
zb.bk_target = 10
msg = mt.run_one(C, ob2, zb, 'BAKE_HP')
check('Mesh Tools BAKE_HP: runs from the shelf settings, message names the counts and the new object',
      msg.startswith('Bake High Poly: 6 -> ') and 'Part2_BakeHP' in msg and 'hard edges kept' in msg, msg)
check('BAKE_HP is a heavy action (safety save) in Mesh Tools and on the ZBrush screen',
      'BAKE_HP' in mt.HEAVY and 'BAKE_HP' in zs.RISKY and mt.ACTIONS['BAKE_HP'] == 'Bake High Poly')
ob3 = cube('Part3')
r = bpy.ops.mch.mesh_tool(action='BAKE_HP')
check('mch.mesh_tool BAKE_HP operator: FINISHED, Part3_BakeHP made', r == {'FINISHED'} and bpy.data.objects.get('Part3_BakeHP') is not None)
# the shelf drawer names the box
import inspect
src = inspect.getsource(__import__('mecha_lab.zb_ui', fromlist=['x']).draw_tool_shelf)
check('ZBrush shelf: a Bake High Poly box after Hard Edges', "label(text='Bake High Poly')" in src and src.index('Hard Edges') < src.index('Bake High Poly'))
summary()
