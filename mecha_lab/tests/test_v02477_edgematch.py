"""0.24.74 Edge Mesh: Match Original (each edge's bevel as round as the original there), Auto Detail (the count from a
Tolerance), the decimation engine no longer folds slivers over their neighbours."""
import math
import os

import numpy as np

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import edge_mesh as em, fast_decimate as fd, hard_edges as he, zb_sculpt as zs

ENG = os.environ.get('MCH_ENGINE')                  # (an older engine build to compare with)
if ENG:
    fd.lib_name = lambda: ENG
mecha_lab.register()
fresh()
C = bpy.context
zb = C.scene.mch_zb


def select(o):
    for x in C.selected_objects:
        x.select_set(False)
    o.select_set(True)
    C.view_layer.objects.active = o


def dense(o, levels=5):
    m = o.modifiers.new('s', 'SUBSURF')
    m.subdivision_type = 'SIMPLE'
    m.levels = levels
    with C.temp_override(object=o, active_object=o):
        bpy.ops.object.modifier_apply(modifier='s')
    select(o)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.quads_convert_to_tris()
    bpy.ops.object.mode_set(mode='OBJECT')
    return o


R = {(1, 1): 0.0, (-1, 1): 0.006, (-1, -1): 0.015}    # corner (x, y sign) -> radius of its vertical edge


def fillet_block(name):
    """A 1.0 x 0.6 x 0.4 block, its vertical edges rounded with known radii (one left sharp), made dense."""
    import bmesh
    bpy.ops.mesh.primitive_cube_add()
    o = C.active_object
    o.name = name
    o.scale = (0.5, 0.3, 0.2)
    bpy.ops.object.transform_apply(scale=True)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    for (sx, sy), r in R.items():
        if r <= 0:
            continue
        es = [e for e in bm.edges if all(abs(v.co.x - sx * 0.5) < 1e-6 and abs(v.co.y - sy * 0.3) < 1e-6
                                         for v in e.verts)]
        bmesh.ops.bevel(bm, geom=es, offset=r, segments=12, profile=0.5, affect='EDGES', clamp_overlap=False)
    bm.to_mesh(o.data)
    bm.free()
    return dense(o)


def edge_float(me, name):
    out = np.zeros(len(me.edges), np.float32)
    a = me.attributes.get(name)
    if a is not None:
        a.data.foreach_get('value', out)
    return out


def corner_round(me, sx, sy):
    """Largest matched width among the hard edges along the vertical edge at corner (sx, sy)."""
    co = np.array([v.co for v in me.vertices])
    ev = np.array([e.vertices for e in me.edges])
    mid = 0.5 * (co[ev[:, 0]] + co[ev[:, 1]])
    k = he.hard_flags(me) & (np.abs(mid[:, 0] - sx * 0.5) < 0.06) & (np.abs(mid[:, 1] - sy * 0.3) < 0.06) \
        & (np.abs(mid[:, 2]) < 0.15)
    r = edge_float(me, he.ROUND)
    return float(r[k].max()) if k.any() else -1.0, int(k.sum())


def folds(V, T):
    """Edges between two well-shaped triangles facing opposite ways (a fold, not a sliver's noise)."""
    V = np.asarray(V, np.float64)
    E, f1, f2, cnt = em._tri_edges(T, len(V))
    n = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    a = np.linalg.norm(n, axis=1)
    n /= np.maximum(a[:, None], 1e-30)
    L = np.max([np.linalg.norm(V[T[:, i]] - V[T[:, (i + 1) % 3]], axis=1) for i in range(3)], 0)
    ok = a > 1e-3 * L ** 2
    two = (cnt == 2) & ok[f1] & ok[np.maximum(f2, 0)]
    return int(((n[f1[two]] * n[f2[two]]).sum(1) < -0.5).sum())


# --- Match Original: measured from the dense original -------------------------------------------------------------
zb.em_auto = False
zb.em_detail = 300                                  # (light enough that each rounded corner is one hard edge)
zb.he_width = 0.002
zb.he_segments = 2
zb.he_style = 'ROUND'
zb.he_subdiv = 2
zb.he_match = True
blk = fillet_block('Block')
em.build(C, blk, zb)
me = blk.data
sharp, n0 = corner_round(me, 1, 1)
r2, n2 = corner_round(me, -1, 1)
r4, n4 = corner_round(me, -1, -1)
check('Match Original: the corner that is sharp on the original reads ~0 (under a tenth of the Width)',
      n0 > 0 and 0.0 <= sharp < 0.1 * zb.he_width, (sharp, n0))
check('... the rounded corners read wider than Width, the rounder one more (radius 0.006 / 0.015: the bevel width '
      'that rounds them like that)', zb.he_width < r2 < r4 < 0.03 and 0.3 * 0.006 < r2 < 1.5 * 0.006, (r2, r4))
top = he.hard_flags(me) & (np.abs(np.array([0.5 * (me.vertices[e.vertices[0]].co.z + me.vertices[e.vertices[1]].co.z)
                                            for e in me.edges]) - 0.2) < 1e-3)
check('... the sharp top edges read ~0 too', top.any() and float(np.median(edge_float(me, he.ROUND)[top])) < 1e-4)
bev = blk.modifiers[he.BEVEL]
w = edge_float(me, 'bevel_weight_edge')
hard = he.hard_flags(me)
check('... the bevel is as wide as the roundest edge; the sharp ones keep Width (their weight = Width / that)',
      abs(bev.width - max(zb.he_width, float(edge_float(me, he.ROUND)[hard].max()))) < 1e-6
      and abs(float(np.median(w[top])) - zb.he_width / bev.width) < 0.02, (bev.width, float(np.median(w[top]))))
zb.he_match = False
check('... Match Original off: one Width for all again', abs(bev.width - zb.he_width) < 1e-9
      and abs(float(np.median(edge_float(me, 'bevel_weight_edge')[top])) - 1.0) < 0.02, bev.width)
zb.he_match = True
n = he.apply_live(C, blk, zb)
check('... Apply: the measured widths go with the other marks', blk.data.attributes.get(he.ROUND) is None)

# --- Auto Detail ----------------------------------------------------------------------------------------------------
bpy.ops.mesh.primitive_cube_add(location=(3, 0, 0))
box = dense(C.active_object)
blk2 = fillet_block('Block2')
blk2.location.x = 6
V, T, _m = em._read(box.data)
nb, _s = em.auto_detail(V, T, 0.00006 * 2.0, math.radians(30))
V, T, _m = em._read(blk2.data)
nk, start = em.auto_detail(V, T, 0.00006 * 1.0, math.radians(30))
check('Auto Detail: a plain box goes right down (nothing to lose), the rounded block keeps more', nb <= 150 and nk > 3 * nb,
      (nb, nk))
nk2, _s = em.auto_detail(V, T, 0.00006 * 1.0 * 4, math.radians(30))
check('... a 4x looser Tolerance: fewer triangles', nk2 < nk, (nk2, nk))
check('... it hands on the step at least 8x the count found (the last steps then run exactly like Detail = count)',
      len(start[1]) >= em.ADAPT_FROM * nk or len(start[1]) == len(T), (len(start[1]), nk))
zb.em_auto = True
zb.em_tolerance = 0.006
src2 = blk2.data.copy()
select(blk2)
msg = em.build(C, blk2, zb)
blk2.data.calc_loop_triangles()
auto_n = len(blk2.data.loop_triangles)
check('... on the object: Detail is set to the count found (the light mesh has about that many before the flats '
      'are joined), the message says Auto', '(Auto)' in msg and abs(auto_n - zb.em_detail) <= 0.15 * zb.em_detail,
      (msg, auto_n, zb.em_detail))
blk3 = bpy.data.objects.new('Block3', src2)          # (the same dense mesh)
C.scene.collection.objects.link(blk3)
select(blk3)
zb.em_auto = False
em.build(C, blk3, zb)
blk3.data.calc_loop_triangles()
check('... the same as Edge Mesh by hand with that Detail', len(blk3.data.loop_triangles) == auto_n,
      (len(blk3.data.loop_triangles), auto_n))
found = zb.em_detail
zb.em_auto = True
zs.run(C, 'EM_DOUBLE')
check('... Double: twice the count found, by hand (Auto off)', not zb.em_auto and zb.em_detail == 2 * found,
      (zb.em_auto, zb.em_detail, found))

# --- engine: slivers ------------------------------------------------------------------------------------------------
from mecha_lab import robot_base as rb  # noqa: E402
ob = rb.create_part(C, 'TORSO', 'INDUSTRIAL', 'RUGGED', seed=72, variation=0.8, details=True, location=(0, 3, 0))
dg = C.evaluated_depsgraph_get()
tor = bpy.data.objects.new('Torso', bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg))
C.scene.collection.objects.link(tor)
bpy.data.objects.remove(ob)
dense(tor, 3)                                       # (its n-gons split simply: rows of points on one line - slivers)
V, T, _m = em._read(tor.data)
Vp, Tp, _m, _st = em.progressive(V, T, 3000, math.radians(30))
f = folds(Vp, Tp)
check('Decimate engine: slivers (three points on a line, their normal is noise) no longer let a collapse fold faces '
      'over their neighbours (a robot torso: 6 folds before)', f <= 2, (f, len(T), len(Tp)))

summary()
