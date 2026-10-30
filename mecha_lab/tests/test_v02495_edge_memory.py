"""0.24.95 Edge Memory: the edges a cut-type tool makes are remembered on the mesh (mch_hard + Sharp + crease) so
Hard Edges / Bake High Poly / Export use them instead of guessing from face angles."""
import math

import numpy as np
from _harness import bmesh, bpy, check, fresh, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import box_hide as bh, core_geometry as cg, cut_engine as ce, edge_memory as em, hard_edges as he

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
S.mch_settings.auto_apply = True
PPU = 100.0
TOP = cg.OrthoProjector(Quaternion(), center=Vector((0, 0, 0)), pixels_per_unit=PPU)
S.mch_cut.targets = 'ACTIVE'



def P(x, y):
    return (500 + x * PPU, 500 + y * PPU)


def rect(cx, cy, w, h):
    return ce.rect_loop(P(cx - w / 2, cy - h / 2), P(cx + w / 2, cy + h / 2))


def select(ob):
    if C.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for o in C.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    C.view_layer.objects.active = ob
    return ob


def cube(name, size=2.0):
    bpy.ops.mesh.primitive_cube_add(size=size)
    ob = C.active_object
    ob.name = name
    return select(ob)


def flag_faces(me, idx):
    a = me.attributes.get(cg.CUTTER_ATTR) or me.attributes.new(cg.CUTTER_ATTR, 'BOOLEAN', 'FACE')
    v = [False] * len(me.polygons)
    for i in idx:
        v[i] = True
    a.data.foreach_set('value', v)


def top_face(me):
    return max(range(len(me.polygons)), key=lambda i: me.polygons[i].center.z)


def front_face(me):
    return min(range(len(me.polygons)), key=lambda i: me.polygons[i].center.y)


# ---- the marks themselves -------------------------------------------------------------------------------------
ob = cube('Unit')
me = ob.data
check('A fresh mesh has no memory', not em.has_memory(me) and em.count(me) == 0 and em.describe(me) == 'no remembered edges')
flag_faces(me, [top_face(me)])
n = em.mark_cut_borders(me)
sharp = np.zeros(len(me.edges), bool); me.attributes['sharp_edge'].data.foreach_get('value', sharp)
crease = np.zeros(len(me.edges), np.float32); me.attributes['crease_edge'].data.foreach_get('value', crease)
check('One cutter face (the top): its 4 border edges are marked, Sharp and creased 1.0',
      n == 4 and em.count(me) == 4 and sharp.sum() == 4 and (crease == 1.0).sum() == 4
      and np.array_equal(em.marked(me), sharp), (n, int(sharp.sum()), crease.tolist()))
flag_faces(me, [top_face(me), front_face(me)])
n = em.mark_cut_borders(me)
check('Top + front cutter faces: 6 border edges + the 90-degree line between the two cutter faces = 7 marks (adds to '
      'the 4 from before: 7 in all, the 4 lie inside)', n == 7 and em.count(me) == 7, (n, em.count(me)))
flag_faces(me, list(range(len(me.polygons))))
n = em.mark_cut_borders(me)
check('Every face flagged (a cutter object itself): nothing marked, the memory untouched', n == 0 and em.count(me) == 7)
cg.remove_cutter_attribute(me)
check('remove_cutter_attribute keeps the memory and drops the flag',
      me.attributes.get(cg.CUTTER_ATTR) is None and em.count(me) == 7)
em.clear(me)
check('clear: the memory goes, Sharp / crease stay as mesh data', not em.has_memory(me) and me.attributes.get('sharp_edge') is not None)

# mark_edges with indices, and add=False
em.mark_edges(me, [0, 1], sharp=False, crease=False)
em.mark_edges(me, np.array([2]))
check('mark_edges: indices add up (0, 1 then 2 = 3)', em.count(me) == 3 and set(np.flatnonzero(em.marked(me))) == {0, 1, 2})
em.mark_edges(me, [5], add=False)
check('mark_edges add=False replaces', em.count(me) == 1 and em.marked(me)[5])
bpy.data.objects.remove(ob)

# ---- a real Cut (finish NONE) remembers its outline ------------------------------------------------------------
ob = cube('Cut', 2.0)
faces0 = len(ob.data.polygons)
ce.perform_closed(C, 'CUT', [ob], [rect(0.0, 0.0, 1.0, 1.0)], TOP)
me = ob.data
n_cut = em.count(me)
check('Cut (a 1x1 pocket through a 2-cube): the cutter flag is gone and the pocket edges are remembered '
      '(the two 4-edge outlines on top and bottom + the 4 walls x 2 corners = at least 12)',
      me.attributes.get(cg.CUTTER_ATTR) is None and n_cut >= 12 and len(me.polygons) > faces0, (n_cut, len(me.polygons)))
# the remembered edges really are the pocket: every one touches a point inside the 1x1 column
co = np.array([v.co[:] for v in me.vertices])
ev = np.array([e.vertices[:] for e in me.edges])
mk = em.marked(me)
inside = (np.abs(co[ev[mk]][:, :, 0]) <= 0.5001).all(1) & (np.abs(co[ev[mk]][:, :, 1]) <= 0.5001).all(1)
check('... and all of them lie on the pocket (|x|,|y| <= 0.5)', inside.all(), int((~inside).sum()))
# a second cut adds marks and keeps the first ones
ce.perform_closed(C, 'CUT', [ob], [rect(0.0, 0.0, 1.6, 0.3)], TOP)
check('A second Cut adds its outline and keeps the first (marks grow)', em.count(ob.data) > n_cut, (n_cut, em.count(ob.data)))

# ---- Hard Edges uses the memory whatever the angle --------------------------------------------------------------
ob2 = cube('Shallow', 2.0)
me2 = ob2.data
# a shallow step: the top face raised by a hair on one half -> a 2-degree fold, far under the 30-degree angle
bm = bmesh.new(); bm.from_mesh(me2)
bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if abs(e.verts[0].co.z - 1) < 1e-6 and abs(e.verts[1].co.z - 1) < 1e-6
                                     and e.verts[0].co.x != e.verts[1].co.x], cuts=1)
bm.to_mesh(me2); bm.free()
flag_faces(me2, [i for i, p in enumerate(me2.polygons) if p.center.z > 0.99 and p.center.x > 0])
em.mark_cut_borders(me2); cg.remove_cutter_attribute(me2)
n_mem = em.count(me2)
for v in me2.vertices:
    if v.co.z > 0.99 and v.co.x > 0.1:
        v.co.z += 0.02
me2.update()
hard_st = type('St', (), {})()
for k, v in dict(he_angle=math.radians(30), he_merge=False, he_crease=True, he_outer=False, he_bevel=False,
                 he_client=False, he_width=0.0, he_match=False).items():
    setattr(hard_st, k, v)
n_found, _f0, _f1 = he.find(ob2, hard_st)
flags = he.hard_flags(me2)
check('Hard Edges on a 2-degree step: the angle alone would miss it, the remembered edges make it hard',
      n_mem > 0 and (flags & em.marked(me2)).sum() == n_mem, (n_mem, int(flags.sum()), int((flags & em.marked(me2)).sum())))
bpy.data.objects.remove(ob2)

# ---- Box Hide: Apply and Split Off remember the hole's edges ---------------------------------------------------
ob3 = cube('Hide', 2.0)
bh.perform(C, [ob3], [rect(0.5, 0.0, 0.6, 0.6)], TOP)
check('Box Hide drawn: the part is hidden live (modifier)', bh.is_hidden(ob3))
piece = bh.split_off(C, ob3)
check('Split Off: the piece exists and remembers its cut edges', piece is not None and em.count(piece.data) > 0,
      em.count(piece.data) if piece else None)
check('... and the rest (the hole applied) remembers the hole\'s edges too, the cutter flag gone from both',
      em.count(ob3.data) > 0 and ob3.data.attributes.get(cg.CUTTER_ATTR) is None
      and piece.data.attributes.get(cg.CUTTER_ATTR) is None, em.count(ob3.data))
ob4 = cube('Hide2', 2.0)
bh.perform(C, [ob4], [rect(-0.5, 0.0, 0.6, 0.6)], TOP)
bh.apply(C, ob4)
check('Box Hide Apply alone: the hole\'s edges remembered', not bh.is_hidden(ob4) and em.count(ob4.data) > 0, em.count(ob4.data))

# ---- transfer over a remesh --------------------------------------------------------------------------------------
ob5 = cube('Src', 2.0)
me5 = ob5.data
flag_faces(me5, [top_face(me5)]); em.mark_cut_borders(me5); cg.remove_cutter_attribute(me5)
bpy.ops.mesh.primitive_cube_add(size=2.0)
dense = C.active_object
bm = bmesh.new(); bm.from_mesh(dense.data)
bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=7, use_grid_fill=True)
bm.to_mesh(dense.data); bm.free()
n_t = em.transfer(me5, dense.data)
co = np.array([v.co[:] for v in dense.data.vertices]); ev = np.array([e.vertices[:] for e in dense.data.edges])
mk = em.marked(dense.data)
on_top_rim = (np.abs(co[ev[mk]][:, :, 2] - 1.0) < 1e-5).all(1) & ((np.abs(np.abs(co[ev[mk]][:, :, 0]) - 1.0) < 1e-5).all(1)
                                                                   | (np.abs(np.abs(co[ev[mk]][:, :, 1]) - 1.0) < 1e-5).all(1))
check('transfer onto a dense cube (8x8 per side): the top rim is found again - 32 edges, every one on the rim',
      n_t == 32 and mk.sum() == 32 and on_top_rim.all(), (n_t, int(mk.sum()), int((~on_top_rim).sum())))

# ---- Fast Decimate keeps the remembered edges, DynaMesh / Quad Remesh get them back -----------------------------
from mecha_lab import fast_decimate as fd, mesh_tools as mt


def pocket_cube(name):
    ob = cube(name, 2.0)
    ce.perform_closed(C, 'CUT', [ob], [rect(0.0, 0.0, 1.0, 1.0)], TOP)
    bm = bmesh.new(); bm.from_mesh(ob.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    for _ in range(3):
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=1, use_grid_fill=True)
    bm.to_mesh(ob.data); bm.free()
    return ob


def on_pocket(me):
    """share of the marked edges whose both ends lie on the pocket's outline lines (x or y = +-0.5 and z = +-1, or
    a vertical corner x,y = +-0.5)."""
    co = np.array([v.co[:] for v in me.vertices]); ev = np.array([e.vertices[:] for e in me.edges]); mk = em.marked(me)
    if not mk.any():
        return 0.0
    p = co[ev[mk]]
    half = np.abs(np.abs(p[:, :, :2]) - 0.5) < 1e-3
    top = np.abs(np.abs(p[:, :, 2]) - 1.0) < 1e-3
    ok = (half.any(2) & (np.abs(p[:, :, :2]) <= 0.5 + 1e-3).all(2) & (top | half.all(2))).all(1)
    return float(ok.mean())


if fd.available():
    ob = pocket_cube('Dec')
    n0 = em.count(ob.data)
    tris0 = len(ob.data.polygons)
    msg = fd.decimate_object(ob, 10.0)
    n1 = em.count(ob.data)
    check(f'Fast Decimate to 10 % of a dense pocket cube ({tris0:,} tris): the remembered edges are kept as lines and '
          f'marked again on the result', n0 > 0 and n1 >= 12 and 'remembered edges kept' in msg, (n0, n1, msg))
    check('... and every one of them lies on the pocket outline (the lines did not drift)', on_pocket(ob.data) > 0.95, on_pocket(ob.data))
    ob = pocket_cube('Dec2')
    em.clear(ob.data)
    fd.decimate_object(ob, 10.0)
    check('(without memory the same decimation marks nothing: the marks come only from the memory)', em.count(ob.data) == 0)
else:
    print('SKIP Fast Decimate engine not available here')

ob = pocket_cube('Dyna')
n0 = em.count(ob.data)
S.mch_zb.points = 30                                  # (thousand points)
msg = mt.run_one(C, ob, S.mch_zb, 'DYNAMESH')
n1 = em.count(ob.data)
check('DynaMesh (voxel remesh) of the pocket cube: the marks come back onto the new mesh\'s edges along the old lines',
      n0 > 0 and n1 > 0 and 'remembered edges back' in msg, (n0, n1, msg))
check('... all of them near the pocket outline (within 1.5 % of the size)', on_pocket(ob.data) > 0.0 and
      em.count(ob.data) < len(ob.data.edges) * 0.2, (on_pocket(ob.data), em.count(ob.data), len(ob.data.edges)))
ob = pocket_cube('Swap')
new = ob.data.copy()
em.clear(new)                                         # (a plain copy would carry the marks itself)
k = fd.swap_mesh(ob, new)
check('swap_mesh carries the memory onto a new mesh that has none (every remesh that swaps meshes: Quad Remesh, '
      'Re-Fix, Hard Edges)', k > 0 and em.count(ob.data) == k, k)

# ---- the ZBrush export reads the marks (crease 1.0 -> polygroup regions) --------------------------------------
from mecha_lab import zbrush_bridge as zbb
ob = cube('Exp', 2.0)
ce.perform_closed(C, 'CUT', [ob], [rect(0.0, 0.0, 1.0, 1.0)], TOP)
ids, n_regions, n_creased = zbb.crease_regions(ob.data)
check('Export to ZBrush: the remembered cut edges are creases, so "Creases as Polygroups" splits the part at them '
      '(the pocket cube: more than one region, 12+ creased edges)', n_regions > 1 and n_creased >= 12, (n_regions, n_creased))
summary()
