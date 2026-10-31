"""0.24.95 Edge Finish bands keep their creases (user, ZBrush CreasePG + Divide: "특정 부분이 크리즈가 안 생기나봐 -
컷 라인 써서 자른 거"): a cut with Chamfer / Bevel replaced its rim by a band whose border with the old surface was
left unmarked, so the top, the band and the wall became one ZBrush polygroup and Divide crumpled it.  Now the band's
two borders are marked, its inner rows stay soft, and no hard edge ends up inside one polygroup."""
import math

import numpy as np
from _harness import bmesh, bpy, check, fresh, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce, edge_memory as em, lasso_line as ll, zbrush_bridge as zb

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
S.mch_settings.auto_apply = True
S.mch_cut.targets = 'ACTIVE'
PPU = 100.0
TOP = cg.OrthoProjector(Quaternion(), center=Vector((0, 0, 0)), pixels_per_unit=PPU)


def P(x, y):
    return (500 + x * PPU, 500 + y * PPU)


def plate():
    me = bpy.data.meshes.new('plate')
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * 3, v.co.y * 1.6, v.co.z * 0.1))
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new('Plate', me)
    S.collection.objects.link(ob)
    for o in C.selected_objects:
        o.select_set(False)
    C.view_layer.objects.active = ob
    ob.select_set(True)
    em.mark_generated(me)
    return ob


def angles(me):
    e_s, f_s, st, en = em._edge_faces(me)
    s2 = st[(en - st) == 2]
    nrm = np.empty(len(me.polygons) * 3, np.float32)
    me.polygons.foreach_get('normal', nrm)
    nrm = nrm.reshape(-1, 3)
    fa, fb = f_s[s2], f_s[s2 + 1]
    ang = np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', nrm[fa], nrm[fb]), -1, 1)))
    return e_s[s2], fa, fb, ang


def unmarked(me, lo=50.0):
    e, _fa, _fb, ang = angles(me)
    return int(((ang > lo) & ~em.marked(me)[e]).sum())


def group_leaks(ob, lo=50.0):
    """hard edges (> lo degrees) inside one polygroup of the ZBrush export copy (= not creased by CreasePG)."""
    tmp = zb.export_copy(C, ob, False)
    try:
        ids, n, _nb = zb.crease_regions(tmp.data)
        _e, fa, fb, ang = angles(tmp.data)
        return int(((ids[fa] == ids[fb]) & (ang > lo)).sum()), n
    finally:
        me = tmp.data
        bpy.data.objects.remove(tmp)
        bpy.data.meshes.remove(me)


def line_cut(ob, pts):
    S.mch_brush.line_width = 0.05
    loop = ll.line_loop(C, TOP, [P(*p) for p in pts], S.mch_brush)
    return ce.perform_closed(C, 'CUT', [ob], [loop], TOP)


def hole(ob, cx, cy, r):
    lg = ce.StrokeLogic.__new__(ce.StrokeLogic)
    lg.brush, lg.shape, lg.anchor = S.mch_brush, 'CIRCLE', P(cx, cy)
    return ce.perform_closed(C, 'CUT', [ob], [lg._drag_loops(P(cx + r, cy), False, False)[0]], TOP)


CURVE = [(-1.8 + 0.1 * i, -1.0 + 0.09 * i + 0.002 * i * i) for i in range(25)]
cut = S.mch_cut

# ---- the finish helper on its own: a Chamfer on a plain Cut ---------------------------------------------------
for mode in ('CHAMFER', 'BEVEL'):
    fresh()
    S = C.scene
    S.mch_settings.auto_apply = True
    cut = S.mch_cut
    cut.targets = 'ACTIVE'
    cut.edge_finish, cut.finish_width, cut.finish_segments = mode, 0.01, 3
    ob = plate()
    r = line_cut(ob, CURVE)
    me = ob.data
    check(f'Line Cut + {mode}: the cut is finished ({r.split("|")[-1].strip()[:40]})', mode in r, r)
    check(f'... no edge sharper than 50 degrees is left unmarked (before: Chamfer 3, Bevel 14 - where the groove '
          f'leaves the part)', unmarked(me) == 0, unmarked(me))
    check('... the band flag is gone once the cut is committed (only the marks stay)',
          me.attributes.get(em.FIN_BAND) is None and me.attributes.get(cg.CUTTER_ATTR) is None)
    if mode == 'BEVEL':
        e, _fa, _fb, ang = angles(me)
        mk = em.marked(me)[e]
        rows = (ang > 22) & (ang < 38)            # (a 3-segment round on a 90-degree rim: 30-degree rows inside,
        border = (ang > 8) & (ang < 20)           #  15-degree joints at its two borders)
        check('... Bevel: its borders marked (before: 0.1 % of its 15-degree joints with the top and the wall - so the '
              'top, the round and the wall were one ZBrush polygroup), its inner rows soft (Divide rounds inside the '
              'band only)',
              border.sum() > 0 and mk[border].mean() > 0.7 and rows.sum() > 0 and mk[rows].mean() < 0.1,
              (int(border.sum()), float(mk[border].mean()) if border.any() else None,
               int(rows.sum()), float(mk[rows].mean()) if rows.any() else None))
    hole(ob, 0.6, 0.2, 0.3)
    hole(ob, -0.4, -0.45, 0.25)                    # (this one crosses the groove's band)
    if mode == 'CHAMFER':
        l40, _n = group_leaks(ob, 40.0)
        check('... Chamfer: its 45-degree borders split the polygroups too (a big C-shaped top face, whose middle lies '
              'over the groove, was taken for band and its border left soft: 367 such edges on a test plate)',
              l40 <= 8, l40)
    leaks, n = group_leaks(ob)
    check(f'... + 2 holes (one through the groove\'s band): ZBrush polygroups ({n}) hold the hard edges on their '
          f'borders - at most a few left inside one polygroup, on the tiny faces where the groove leaves the part\'s '
          f'side', leaks <= 8, leaks)

# ---- the GN Edge finish (rim sweep) path ---------------------------------------------------------------------
fresh()
S = C.scene
S.mch_settings.auto_apply = True
cut = S.mch_cut
cut.targets = 'ACTIVE'
cut.edge_finish = 'NONE'
cut.gn_finish, cut.gn_width, cut.gn_segments = 'CHAMFER', 0.01, 1
ob = plate()
r = line_cut(ob, CURVE)
check('GN Edge Chamfer (swept band): no edge sharper than 50 degrees left unmarked (before: 37 - the sweep\'s '
      'Boolean and the result tidy rebuilt the part\'s corners without their marks)', unmarked(ob.data) == 0
      and 'GN' in r, (unmarked(ob.data), r))

# ---- finish_band itself: the band found by geometry ----------------------------------------------------------
me = bpy.data.meshes.new('cube')
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=2.0)
bm.to_mesh(me)
snap = em.finish_snapshot(me)
bm.edges.ensure_lookup_table()
top = [e for e in bm.edges if all(abs(v.co.z - 1) < 1e-6 for v in e.verts)]
bmesh.ops.bevel(bm, geom=top + list({v for e in top for v in e.verts}), offset=0.1, segments=3, affect='EDGES')
bm.to_mesh(me)
bm.free()
nb = em.finish_band(me, snap, 0.1)
check('finish_band: the 3-row round of a cube\'s top rim found as the band (its 4 x 3 rows; the top, the 4 walls '
      'and the bottom not)', nb == 12 and len(me.polygons) == 18, (nb, len(me.polygons)))
e, fa, fb, ang = angles(me)
band = np.zeros(len(me.polygons), bool)
me.attributes[em.FIN_BAND].data.foreach_get('value', band)
mk = em.marked(me)[e]
check('... its borders with the top and the walls are marked, nothing inside it',
      mk[band[fa] != band[fb]].all() and not mk[band[fa] & band[fb]].any())
summary()
