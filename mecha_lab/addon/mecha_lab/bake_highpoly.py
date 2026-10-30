"""0.24.95 Bake High Poly: a dense copy for baking (retopo + normal bake) - the hard edges stay EXACTLY where they are,
the faces between them are subdivided and rounded, so a decimated / cut part's flat facets no longer show in the bake.

Why not Make High Poly (support bevel + Catmull-Clark)?  On a triangle mesh (Decimate, cuts) Catmull-Clark turns
uneven triangles into lumps, a crease line with one gap rounds the whole corner, and a bevel on tiny edges breaks.
This one has no such inputs:

    1. the hard edges: Edge Memory first (the edges a tool made, whatever their angle), then the face angle for the
       rest (an imported part has no memory yet);
    2. optional **fillet**: a small round bevel on the hard edges (a bake likes a little edge width: a razor edge
       bakes to nothing) - its strip is left free so the rounding makes it a true fillet;
    3. midpoint subdivision ``levels`` times (4x faces each) - every face type, no topology change;
    4. after each level, Taubin smoothing (no shrinkage): the points inside a face region move, a point ON a hard
       line slides along the line only, a corner (3+ lines, or a line end) never moves;
    5. **rounding**: 100 = the smoothed surface, 0 = the subdivided original exactly (every point put back on the
       original faces), in between a blend.

The result is a new object ``<name>_BakeHP`` in the ``BakeHP`` collection, the original hidden (never changed).
``levels`` comes from the target face count (``levels_for``).  Pure helpers (``hard_mask``, ``levels_for``,
``taubin``) are tested headless; ``build`` on the user's parts in the real-window check.
"""
from __future__ import annotations

import math
import time

import bmesh
import bpy
import numpy as np

COLL = 'BakeHP'
SRC_KEY = 'mch_bakehp_src'
LAM, MU = 0.5, -0.53          # Taubin smoothing: shrink step, then the grow step that gives the volume back
ITERS = 10                    # Taubin pairs per level
MAX_LEVELS = 4
TURN = math.radians(25.0)      # a hard line bending more than this at a point: that point is a corner
MIN_FACES = 4
INFO = {}                     # the last run, for the tests / message
STRIP = '.mch_bk_strip'       # face: made by the fillet bevel (free to round)
FLAT = '.mch_bk_flat'         # face: a true flat (every edge hard, coplanar with its neighbour, or next to a strip)
FLAT_TOL = math.radians(1.0)


def hard_mask(me, angle=math.radians(30.0), memory=True, specks=True):
    """bool per edge: the edges Bake High Poly keeps fixed - Edge Memory marks, boundary edges and the edges whose two
    faces meet at more than ``angle``.  ``specks`` drops a lone angle edge whose ends touch no other hard edge."""
    from . import edge_memory as em
    from . import mesh_io as mio
    ne = len(me.edges)
    nf = len(me.polygons)
    hard = np.zeros(ne, bool)
    if ne == 0:
        return hard
    if nf:
        e_sorted, f_sorted, starts, ends = em._edge_faces(me)
        cnt = ends - starts
        hard[e_sorted[starts[cnt != 2]]] = True                 # boundary / non-manifold
        two = cnt == 2
        s2 = starts[two]
        nrm = np.empty(nf * 3, np.float32)
        me.polygons.foreach_get('normal', nrm)
        nrm = nrm.reshape(-1, 3)
        d = np.einsum('ij,ij->i', nrm[f_sorted[s2]], nrm[f_sorted[s2 + 1]])
        ang = e_sorted[s2[d < math.cos(angle)]]
        if specks and len(ang):
            ev = mio.read_edge_verts(me)
            deg = np.bincount(ev[ang].ravel(), minlength=len(me.vertices))
            lone = (deg[ev[ang, 0]] == 1) & (deg[ev[ang, 1]] == 1)
            ang = ang[~lone]
        hard[ang] = True
    if memory:
        hard |= em.marked(me)
    return hard


def levels_for(faces, target, max_levels=MAX_LEVELS):
    """Subdivision levels so ``faces`` x 4^levels reaches ``target`` (never more than max_levels, at least 1)."""
    faces = max(1, int(faces))
    if target <= faces:
        return 1
    return int(min(max_levels, max(1, math.ceil(math.log(target / faces, 4)))))


def _arrays(me):
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    ne = len(me.edges)
    ev = np.empty(ne * 2, np.int32)
    me.edges.foreach_get('vertices', ev)
    sharp = np.zeros(ne, bool)
    a = me.attributes.get('sharp_edge')
    if a is not None:
        a.data.foreach_get('value', sharp)
    return co.reshape(-1, 3).astype(np.float64), ev.reshape(-1, 2).astype(np.int64), sharp


def _face_bool(me, name):
    out = np.zeros(len(me.polygons), bool)
    a = me.attributes.get(name)
    if a is not None and a.domain == 'FACE':
        a.data.foreach_get('value', out)
    return out


def flag_flats(me, hard, tol=FLAT_TOL):
    """Face flag FLAT: a face that is a true flat - every edge of it is a hard line, or coplanar with the face
    across it, or next to a fillet strip, or a boundary.  A facet of a curved surface (its neighbour a few degrees
    off, no hard line between) is NOT flat: it may round.  Returns the number of flat faces."""
    from . import edge_memory as em
    nf = len(me.polygons)
    if nf == 0:
        return 0
    strip = _face_bool(me, STRIP)
    e_sorted, f_sorted, starts, ends = em._edge_faces(me)
    nrm = np.empty(nf * 3, np.float32)
    me.polygons.foreach_get('normal', nrm)
    nrm = nrm.reshape(-1, 3)
    ok_face = np.ones(nf, bool) & ~strip
    cnt = ends - starts
    two = np.flatnonzero(cnt == 2)
    s2 = starts[two]
    fa, fb = f_sorted[s2], f_sorted[s2 + 1]
    d = np.einsum('ij,ij->i', nrm[fa], nrm[fb])
    ok_edge = (d > math.cos(tol)) | hard[e_sorted[s2]]
    # fa is fine with this edge if ok_edge, or the face across it is a strip (and the same for fb)
    bad_a = ~(ok_edge | strip[fb])
    bad_b = ~(ok_edge | strip[fa])
    ok_face[fa[bad_a]] = False
    ok_face[fb[bad_b]] = False
    more = np.flatnonzero(cnt > 2)                       # non-manifold: never a flat
    for k in more:
        ok_face[f_sorted[starts[k]:ends[k]]] = False
    a = me.attributes.get(FLAT)
    if a is not None and a.domain != 'FACE':
        me.attributes.remove(a)
        a = None
    if a is None:
        a = me.attributes.new(FLAT, 'BOOLEAN', 'FACE')
    a.data.foreach_set('value', ok_face)
    return int(ok_face.sum())


def planar_normals(me, tol=FLAT_TOL):
    """(nv, 3): the normal of the plane a point lies in when EVERY face round it is a flagged flat (flag_flats) and
    they agree, zeros elsewhere.  Those points only move inside their plane: flats stay flat while a fillet strip
    next to them is free, and a faceted curve (not flagged) rounds."""
    from . import mesh_io as mio
    nv, nf = len(me.vertices), len(me.polygons)
    out = np.zeros((nv, 3))
    if nf == 0:
        return out
    flat = _face_bool(me, FLAT)
    if not flat.any():
        return out
    cv = mio.read_corner_verts(me)
    _start, tot = mio.read_face_starts(me)
    f_of = np.repeat(np.arange(nf), tot)
    nrm = np.empty(nf * 3, np.float32)
    me.polygons.foreach_get('normal', nrm)
    nrm = nrm.reshape(-1, 3).astype(np.float64)
    avg = np.zeros((nv, 3))
    for k in range(3):
        avg[:, k] = np.bincount(cv, weights=nrm[f_of, k], minlength=nv)
    ln = np.linalg.norm(avg, axis=1)
    avg[ln > 1e-12] /= ln[ln > 1e-12][:, None]
    d = np.einsum('ij,ij->i', nrm[f_of], avg[cv])
    d = np.where(flat[f_of], d, -2.0)                    # a non-flat face round the point: not planar
    mind = np.ones(nv)
    np.minimum.at(mind, cv, d)
    planar = (mind > math.cos(tol)) & (ln > 1e-12)
    out[planar] = avg[planar]
    return out


def taubin(co, E, hard, iters=ITERS, lam=LAM, mu=MU, plane_n=None):
    """Taubin-smoothed copy of ``co``: E = edges (m, 2), hard = bool per edge.  Points on hard lines slide along
    them, corners stay, points with a ``plane_n`` normal stay in that plane.  Returns (co, corners, line points)."""
    co = np.array(co, np.float64)
    nv = len(co)
    Eh = E[hard]
    deg_all = np.bincount(E.ravel(), minlength=nv).astype(np.float64)
    deg_h = np.bincount(Eh.ravel(), minlength=nv).astype(np.float64)
    corner = (deg_h >= 3) | (deg_h == 1)
    line = deg_h == 2
    if line.any() and len(Eh):                      # a line point where the line TURNS is a corner too (the corner
        vi = np.concatenate([Eh[:, 0], Eh[:, 1]])   # of a cut outline on a flat face has only 2 hard edges)
        vj = np.concatenate([Eh[:, 1], Eh[:, 0]])
        order = np.argsort(vi, kind='stable')
        vi, vj = vi[order], vj[order]
        first = np.flatnonzero(np.r_[True, vi[1:] != vi[:-1]])
        v2 = vi[first][deg_h[vi[first]] == 2]
        f2 = first[deg_h[vi[first]] == 2]
        d1 = co[vj[f2]] - co[v2]
        d2 = co[vj[f2 + 1]] - co[v2]
        n1 = np.linalg.norm(d1, axis=1)
        n2 = np.linalg.norm(d2, axis=1)
        okn = (n1 > 1e-12) & (n2 > 1e-12)
        cs = np.full(len(v2), -1.0)
        cs[okn] = np.einsum('ij,ij->i', d1[okn], d2[okn]) / (n1[okn] * n2[okn])
        turn = v2[cs > -math.cos(TURN)]
        corner[turn] = True
        line[turn] = False
    free = ~corner

    def avg(c, EE, deg):
        s = np.zeros_like(c)
        for k in range(3):
            s[:, k] = (np.bincount(EE[:, 0], weights=c[EE[:, 1], k], minlength=nv)
                       + np.bincount(EE[:, 1], weights=c[EE[:, 0], k], minlength=nv))
        return s / np.maximum(deg, 1)[:, None]

    for _ in range(iters):
        for w in (lam, mu):
            t = avg(co, E, deg_all)
            if len(Eh):
                th = avg(co, Eh, deg_h)
                t[line] = th[line]
            d = t - co
            d[~free] = 0
            if plane_n is not None:
                d -= np.einsum('ij,ij->i', d, plane_n)[:, None] * plane_n
            co += w * d
    return co, int(corner.sum()), int(line.sum())


def _subdivide(me):
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=1, use_grid_fill=True)
        bm.to_mesh(me)
    finally:
        bm.free()


def _fillet(me, hard, width):
    """A small round bevel on the hard edges; the strip's edges are left free (no Sharp) so the rounding makes
    it a fillet.  Returns the number of edges beveled."""
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        strip = bm.faces.layers.bool.get(STRIP) or bm.faces.layers.bool.new(STRIP)   # (made BEFORE the bevel: a
        bm.edges.ensure_lookup_table()                                                # layer added after it leaves
        edges = [bm.edges[i] for i in np.flatnonzero(hard) if len(bm.edges[i].link_faces) == 2]   # the result's
        if not edges:                                                                 # faces pointing at old data)
            return 0
        res = bmesh.ops.bevel(bm, geom=edges, offset=width, offset_type='OFFSET', segments=2, profile=0.5,
                              affect='EDGES', clamp_overlap=True, loop_slide=True)
        for f in res.get('faces', []):
            if f.is_valid:
                f[strip] = True
                for e in f.edges:
                    e.smooth = True
        bm.to_mesh(me)
        return len(edges)
    finally:
        bm.free()


def _mesh_size(me):
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    return float(np.linalg.norm(co.max(0) - co.min(0))) if len(co) else 0.0


def _reproject(co, src_me, blend):
    """Every point blended towards its nearest point on ``src_me`` (blend 1 = exactly on it)."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    verts = [v.co for v in src_me.vertices]
    polys = [list(p.vertices) for p in src_me.polygons]
    tree = BVHTree.FromPolygons(verts, polys, all_triangles=False)
    out = co.copy()
    for i in range(len(co)):
        loc, _n, _i, _d = tree.find_nearest(Vector(co[i]))
        if loc is not None:
            out[i] = np.array(loc) * blend + co[i] * (1.0 - blend)
    return out


def _evaluated_copy(context, ob):
    """The object's mesh with its modifiers applied, as a new Mesh (attributes kept)."""
    dg = context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    me.name = ob.data.name + '_BakeHP'
    return me


def _collection(context):
    coll = bpy.data.collections.get(COLL)
    if coll is None:
        coll = bpy.data.collections.new(COLL)
    if coll.name not in context.scene.collection.children and not any(
            coll.name in c.children for c in bpy.data.collections):
        context.scene.collection.children.link(coll)
    return coll


def bake_mesh(me, levels, rounding=1.0, fillet=0.0, angle=math.radians(30.0), iters=ITERS):
    """``me`` subdivided + rounded IN PLACE (a copy the caller made).  Returns dict(faces0, faces, hard, corners,
    lines, fillet_edges, levels, seconds)."""
    t0 = time.time()
    faces0 = len(me.polygons)
    hard = hard_mask(me, angle)
    n_hard = int(hard.sum())
    a = me.attributes.get('sharp_edge') or me.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE')
    a.data.foreach_set('value', hard)                       # (bmesh carries Sharp through the subdivision)
    n_fillet = 0
    size = _mesh_size(me)
    if fillet > 0.0 and size > 0.0:
        n_fillet = _fillet(me, hard, fillet * size)
        co, E, hard = _arrays(me)                            # (the mesh changed: the Sharp flags are the hard mask now)
    n_flat = flag_flats(me, hard)
    src = me.copy() if rounding < 0.999 else None            # the surface the points go back to
    corners = lines = 0
    for _ in range(levels):
        _subdivide(me)
        co, E, sharp = _arrays(me)
        co, corners, lines = taubin(co, E, sharp, iters, plane_n=planar_normals(me))
        me.vertices.foreach_set('co', co.astype(np.float32).ravel())
        me.update()
    co, E, sharp = _arrays(me)
    co, corners, lines = taubin(co, E, sharp, iters, plane_n=planar_normals(me))
    if src is not None:
        co = _reproject(co, src, 1.0 - max(0.0, min(1.0, rounding)))
        bpy.data.meshes.remove(src)
    me.vertices.foreach_set('co', co.astype(np.float32).ravel())
    for name in (STRIP, FLAT):
        a = me.attributes.get(name)
        if a is not None:
            me.attributes.remove(a)
    me.update()
    info = dict(faces0=faces0, faces=len(me.polygons), hard=n_hard, corners=corners, lines=lines,
                fillet_edges=n_fillet, flats=n_flat, levels=levels, seconds=time.time() - t0)
    INFO.clear()
    INFO.update(info)
    return info


def build(context, ob, target_faces=1_000_000, rounding=1.0, fillet=0.0, angle=math.radians(30.0)):
    """The BakeHP copy of mesh object ``ob``: (new object, info).  Raises RuntimeError when it can't."""
    from . import budget
    from . import core_geometry as cg
    if ob.type != 'MESH' or len(ob.data.polygons) < MIN_FACES:
        raise RuntimeError('needs a mesh with faces')
    me = _evaluated_copy(context, ob)
    try:
        faces0 = len(me.polygons)
        levels = levels_for(faces0, target_faces)
        while levels > 1:
            ok, _why = budget.faces_fit(faces0 * 4 ** levels)
            if ok:
                break
            levels -= 1
        ok, why = budget.faces_fit(faces0 * 4 ** levels)
        if not ok:
            raise RuntimeError(why)
        try:
            cg.drop_custom_normals(me)
        except (RuntimeError, AttributeError):
            pass
        info = bake_mesh(me, levels, rounding, fillet, angle)
    except Exception:
        bpy.data.meshes.remove(me)
        raise
    for mat in ob.data.materials:
        me.materials.append(mat)
    me.shade_smooth()
    hp = bpy.data.objects.new(ob.name + '_BakeHP', me)
    hp.matrix_world = ob.matrix_world.copy()
    hp[SRC_KEY] = ob.name
    _collection(context).objects.link(hp)
    ob.hide_set(True)
    for o in context.selected_objects:
        o.select_set(False)
    hp.select_set(True)
    context.view_layer.objects.active = hp
    return hp, info


def describe(info):
    f = info
    return (f'Bake High Poly: {f["faces0"]:,} -> {f["faces"]:,} faces (x4^{f["levels"]}), {f["hard"]:,} hard edges kept '
            f'({f["corners"]:,} corners fixed)' + (f', fillet on {f["fillet_edges"]:,} edges' if f.get('fillet_edges') else '')
            + f', {f["seconds"]:.1f} s')


def run(context, ob, zb):
    """From the shelf / Mesh Tools settings (``scene.mch_zb``).  Returns the message."""
    hp, info = build(context, ob, target_faces=int(zb.bk_target) * 1000, rounding=zb.bk_rounding / 100.0,
                     fillet=zb.bk_fillet / 100.0, angle=zb.he_angle)
    return describe(info) + f' -> {hp.name} (original hidden)'


def is_bake(ob):
    return ob is not None and ob.type == 'MESH' and SRC_KEY in ob


def draw_rows(col, zb, op):
    """The rows shared by the ZBrush shelf and Mesh Tools: ``op(row, text, action)`` draws the button."""
    r = col.row(align=True)
    op(r, 'Bake High Poly', 'BAKE_HP')
    r.prop(zb, 'bk_target', text='Target (k)')
    r = col.row(align=True)
    r.prop(zb, 'bk_rounding', slider=True)
    r.prop(zb, 'bk_fillet')
