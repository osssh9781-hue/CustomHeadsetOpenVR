"""0.24.72 Hard Edges (ZBrush shelf): find the hard edges of a decimated / quad-remeshed hard-surface part, crease them
and put a live, adjustable bevel on them.

Find Edges marks every edge whose faces meet at more than Angle (and open borders) as Sharp, gives it a full Crease
and a Bevel Weight; lone specks (a single short edge on its own) are left out.  Merge Flats first joins the near-flat
triangles between the hard edges into big faces (triangle meshes only - Decimate's output; quads from Quad Remesh
stay quads), so the bevel and the subdivision get clean faces.  Then, live and adjustable at any time (settings on
the ZBrush shelf, ``scene.mch_zb.he_*``):

* Bevel - on the marked edges (Outer Only: the convex ones, inside corners stay sharp), Width / Segments
  (1 = a chamfer) / Shape
* Subdivide - Catmull-Clark levels; creased edges stay sharp, the flat parts get more faces
* Weighted Normals - flat faces shade flat next to the bevels

Apply bakes the live modifiers into the mesh; Clear takes the marks and the live modifiers off.

0.24.73 Client Look (on by default): the mesh itself carries the hard look - no Sharp marks for Blender's display
and no custom normals (Weighted Normals off), so what Blender shows is what Maya / Max / ZBrush show.  The hard
edges are kept in an internal attribute; the support bevel + creased subdivision make them crisp with plain smooth
shading.  Apply then leaves a plain mesh: modifiers baked, no Sharp / Crease / Bevel Weight / custom normals,
every face smooth.

0.24.73 the bevel is as wide as Width asks wherever it fits: Blender's own overlap test (the one Clamp Overlap
runs) is done here edge by edge and only the bevel weights of the edges that would run over a neighbour are cut
down (``fit_weights``) - with Clamp alone one tight spot anywhere narrowed every bevel of the part (a Width of
1.2 % of the part came out as 0.1 %).  Edge Mesh (edge_mesh)
results also get Fit to Original: a Shrinkwrap onto the dense mesh they were made from, away from the hard edges.
"""
from __future__ import annotations

import math

import numpy as np

import bmesh
import bpy

from . import edge_memory as em

BEVEL = 'MCH_HE_Bevel'
SUBSURF = 'MCH_HE_Subdivide'
NORMALS = 'MCH_HE_Normals'
FIT = 'MCH_HE_Fit'              # 0.24.73 Edge Mesh: Shrinkwrap onto the dense original
LIVE = (BEVEL, SUBSURF, FIT, NORMALS)
KEY = 'mch_hard_edges'          # object: Find Edges ran on it (the live modifiers follow the shelf settings)
CONVEX = '.mch_he_convex'       # edge: the faces meet outward (Outer Only)
HARD = '.mch_he_hard'           # edge: a hard edge (kept here: with Client Look nothing is marked Sharp)
ROUND = '.mch_he_round'         # edge: Edge Mesh - how round the original is there (bevel width it matches)
PROBE_MAX = 30000               # set_live: up to this many polygons the bevel is test-run without Clamp Overlap
PROBE_TOL = 0.3                 # ... it overlaps when one of its points is further than this x Width off the surface
PROBE_ROUNDS = 6                # ... and the bevels around an overlap are halved this many times before Clamp goes on
INSIDE = 0.4                    # inside (concave) hard edges get this share of the bevel Width
FIT_SAFETY = 0.9                # fit_weights: an edge whose bevel would run over keeps this share of what fits
FIT_ROUNDS = 12
CHAMFER_SUPPORT = 0.12          # Chamfer: the support loops sit this share of the width in from each side
MATCH_MAX = 0.05                # Match Original: no edge's bevel wider than this x the part size
SRC = 'mch_he_source'           # object: the dense original (off-scene, kept by a fake user) Fit to Original uses
FIT_GROUP = 'mch_he_fit'        # point group: 1 = fit onto the original, 0 = stay (the hard edges)
FLAT = math.radians(1.0)        # Merge Flats: faces closer than this to flat are joined
FAST_MERGE = 20000              # ... from this many triangles the flat points are emptied by the engine first
SPECK = 0.02                    # a hard edge on its own shorter than this x the part size is not a hard edge
MAX_POLYS = 300000              # beyond this: Decimate / Quad Remesh first (a bevel on a DynaMesh would take ages)
NOTE = 'mch_he_note'            # object: 0.24.83 what set_live had to do about the bevel (width halved / dropped)
SOUND_ROUNDS = 3                # ... the bevel width is halved this many times when the bevel comes out broken


def _size(me):
    if not me.vertices:
        return 1.0
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    return max(float((co.max(0) - co.min(0)).max()), 1e-9)


def _convex(e):
    if len(e.link_faces) != 2:
        return True
    f1, f2 = e.link_faces
    return (f2.calc_center_median() - f1.calc_center_median()).dot(f1.normal) < 0.0


def _drop_specks(hard, size):
    """Hard edges minus the lone ones: a single short edge with no other hard edge at either end."""
    deg = {}
    for e in hard:
        for v in e.verts:
            deg[v.index] = deg.get(v.index, 0) + 1
    return [e for e in hard if not (deg[e.verts[0].index] == 1 and deg[e.verts[1].index] == 1
                                    and e.calc_length() < SPECK * size)]


def _empty_flats(ob, angle):
    """0.24.73 Merge Flats on a big triangle mesh: the points inside flat areas (every face around within FLAT, no
    hard edge) are taken away first by the decimation engine with every other point locked - the shape can't change
    (only flat points go) and Blender's dissolve then has a few big triangles to join instead of 200,000 (it took 30 s
    there).  Point attributes / UVs don't carry over; materials do.  Returns True when the mesh was replaced."""
    from . import edge_mesh as em
    from . import fast_decimate as fd
    me = ob.data
    if not fd.available() or getattr(me, 'shape_keys', None) is not None:
        return False
    V, T, mats = em._read(me)
    if len(T) < FAST_MERGE:
        return False
    V64 = V.astype(np.float64)
    n = np.cross(V64[T[:, 1]] - V64[T[:, 0]], V64[T[:, 2]] - V64[T[:, 0]])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-30)
    avg = np.zeros_like(V64)
    for k in range(3):
        np.add.at(avg, T[:, k], n)
    avg /= np.maximum(np.linalg.norm(avg, axis=1, keepdims=True), 1e-30)
    worst = np.ones(len(V))
    for k in range(3):
        np.minimum.at(worst, T[:, k], (n * avg[T[:, k]]).sum(1))
    lock = (worst < math.cos(FLAT)).astype(np.uint8)
    H = em.hard_lines(V64, T, angle)
    lock[H.ravel()] = 1
    lp, _o1, _o2, turn, _deg = em.line_points(V64, H)
    lock[lp[turn < FLAT]] = 0                # (points along a straight hard edge go too: along it nothing changes,
                                             # and kept they leave needle triangles that block the merge)
    if lock.all():
        return False
    oV, oT, _vs, fs = fd.run(V, T, 4, keep_borders=True, locked=lock)
    if len(oT) >= len(T):
        return False
    new = fd.fresh_like(me)
    try:
        for name in [a.name for a in new.attributes]:
            a = new.attributes.get(name)
            if a is not None and not name.startswith('.') and name not in ('position', 'material_index'):
                try:
                    new.attributes.remove(a)
                except RuntimeError:
                    pass
        fd.build_mesh(new, oV, oT)
        if len(new.materials) > 1:
            new.polygons.foreach_set('material_index', mats[fs].astype(np.int32))
    except Exception:
        bpy.data.meshes.remove(new)
        raise
    fd.swap_mesh(ob, new)
    return True


def find(ob, st):
    """Mark the hard edges of mesh object ``ob`` (Object Mode).  Returns (hard edges, polygons before, after)."""
    me = ob.data
    faces0 = len(me.polygons)
    if st.he_merge and faces0 >= FAST_MERGE:
        tri_share = sum(1 for _p in me.polygons if _p.loop_total == 3) / max(1, faces0) if faces0 < 2_000_000 else 1.0
        if tri_share > 0.5 and _empty_flats(ob, st.he_angle):
            me = ob.data
    size = _size(me)
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        hard = [e for e in bm.edges if len(e.link_faces) != 2 or e.calc_face_angle(0.0) > st.he_angle]
        hard = drop_short_lines(_drop_specks(hard, size), size)
        mem = bm.edges.layers.bool.get(em.ATTR)              # 0.24.95 Edge Memory: the edges a tool made are hard
        if mem is not None:                                  # whatever their angle (a shallow cut, a gentle boolean)
            hard = list({*hard, *(e for e in bm.edges if e[mem])})
        for e in bm.edges:
            e.smooth = True
        for e in hard:
            e.smooth = False
        tris = sum(len(f.verts) == 3 for f in bm.faces)
        if st.he_merge and tris > 0.5 * len(bm.faces):
            bmesh.ops.dissolve_limit(bm, angle_limit=FLAT, use_dissolve_boundaries=False, verts=bm.verts[:],
                                     edges=bm.edges[:], delimit={'SHARP', 'MATERIAL'})
        crease = bm.edges.layers.float.get('crease_edge') or bm.edges.layers.float.new('crease_edge')
        weight = bm.edges.layers.float.get('bevel_weight_edge') or bm.edges.layers.float.new('bevel_weight_edge')
        conv = bm.edges.layers.bool.get(CONVEX) or bm.edges.layers.bool.new(CONVEX)
        n = 0
        for e in bm.edges:
            h = not e.smooth
            c = _convex(e) if h else False
            n += h
            e[conv] = c
            e[crease] = 1.0 if h and st.he_crease else 0.0
            e[weight] = 1.0 if h and (c or not st.he_outer) else 0.0
        for f in bm.faces:
            f.smooth = True
        bm.to_mesh(me)
    finally:
        bm.free()
    hard = _edge_bool(me, 'sharp_edge')
    a = me.attributes.get(HARD) or me.attributes.new(HARD, 'BOOLEAN', 'EDGE')
    a.data.foreach_set('value', hard)
    marks(me, st)
    ob[KEY] = 1
    return n, faces0, len(me.polygons)


def fit_weights(me, w, width):
    """Bevel weights ``w`` (per edge) cut down where the bevel would run over a neighbouring edge at ``width``: the
    tests of Blender's Clamp Overlap (an edge squeezed to nothing between two bevels, a bevel sliding past the end of
    the edge next to it), per face corner, on the actual weights; only the edges taking part in an overlap get
    narrower (Clamp narrows all).  Returns the new weights."""
    w = np.asarray(w, np.float64).copy()
    if width <= 0 or not len(me.polygons) or not w.any():
        return w.astype(np.float32)
    nl = len(me.loops)
    lv = np.empty(nl, np.int64)
    le = np.empty(nl, np.int64)
    me.loops.foreach_get('vertex_index', lv)
    me.loops.foreach_get('edge_index', le)
    ls = np.empty(len(me.polygons), np.int64)
    lt = np.empty(len(me.polygons), np.int64)
    me.polygons.foreach_get('loop_start', ls)
    me.polygons.foreach_get('loop_total', lt)
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    pi_ = np.repeat(np.arange(len(ls)), lt)
    k = np.arange(nl) - ls[pi_]
    nxt = ls[pi_] + (k + 1) % lt[pi_]
    prv = ls[pi_] + (k - 1) % lt[pi_]
    eb, ea, ec = le, le[prv], le[nxt]                        # corner: edge B from vb to vc, A before it, C after
    vb, vc, va, vd = lv, lv[nxt], lv[prv], lv[nxt[nxt]]
    keep = (w[eb] > 0) | (w[ea] > 0) | (w[ec] > 0)            # (only corners next to a bevel can overlap)
    eb, ea, ec, vb, vc, va, vd = eb[keep], ea[keep], ec[keep], vb[keep], vc[keep], va[keep], vd[keep]

    def ang(p, q, r):                                          # angle at q
        u, v = co[p] - co[q], co[r] - co[q]
        c = (u * v).sum(1) / np.maximum(np.linalg.norm(u, axis=1) * np.linalg.norm(v, axis=1), 1e-30)
        return np.arccos(np.clip(c, -1.0, 1.0))
    th1, th2 = ang(va, vb, vc), ang(vb, vc, vd)
    s1, s2, t1, t2 = np.sin(th1), np.sin(th2), np.tan(th1), np.tan(th2)
    lb = np.linalg.norm(co[vb] - co[vc], axis=1)
    la = np.linalg.norm(co[va] - co[vb], axis=1)
    lc = np.linalg.norm(co[vd] - co[vc], axis=1)
    g, h = t1 * t2, s1 * s2
    for _r in range(FIT_ROUNDS):
        ka, kb, kc = w[ea], w[eb], w[ec]
        scale = np.ones(len(w))
        bad = False
        many = ((ka > 0).astype(int) + (kb > 0) + (kc > 0)) >= 2           # B squeezed between bevels
        den = g * (ka * s2 + kc * s1) + kb * h * (t1 + t2)
        with np.errstate(divide='ignore', invalid='ignore'):
            t = lb * g * h / den
        hit = many & (den != 0) & (t >= 0) & (t < width)
        if hit.any():
            bad = True
            f = FIT_SAFETY * t[hit] / width
            for e, kk in ((ea, ka), (eb, kb), (ec, kc)):
                m = kk[hit] > 0
                np.minimum.at(scale, e[hit][m], f[m])
        for lx, sx, kx in ((la, s1, ka), (lc, s2, kc)):                     # B's bevel slides past A / C
            m = (kb > 0) & (kx == 0)
            with np.errstate(divide='ignore', invalid='ignore'):
                t = lx * sx / kb
            hit = m & (t >= 0) & (t < width)
            if hit.any():
                bad = True
                np.minimum.at(scale, eb[hit], FIT_SAFETY * t[hit] / width)
        if not bad:
            break
        w *= scale
    return w.astype(np.float32)


def drop_short_lines(edges, size, share=None):
    """Hard edges minus the short pieces on their own: connected runs of hard edges shorter than ``share`` x the part
    size in all (a scratch of the decimation, not an edge of the part: its bevel shows as a mark on the face)."""
    share = 0.5 * SPECK if share is None else share
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for e in edges:
        a, b = find(e.verts[0].index), find(e.verts[1].index)
        if a != b:
            parent[a] = b
    total = {}
    for e in edges:
        r = find(e.verts[0].index)
        total[r] = total.get(r, 0.0) + e.calc_length()
    return [e for e in edges if total[find(e.verts[0].index)] >= share * size]


def _edge_faces(me):
    """For every edge: its first two faces (-1 when missing) and how many faces it has."""
    ne = len(me.edges)
    le = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get('edge_index', le)
    ls = np.empty(len(me.polygons), np.int64)
    me.polygons.foreach_get('loop_total', ls)
    lp = np.repeat(np.arange(len(me.polygons)), ls)
    o = np.argsort(le, kind='stable')
    le, lp = le[o], lp[o]
    cnt = np.bincount(le, minlength=ne)
    start = np.concatenate([[0], np.cumsum(cnt)[:-1]])
    f1 = np.where(cnt > 0, lp[np.minimum(start, len(lp) - 1)], -1) if len(lp) else np.full(ne, -1)
    f2 = np.where(cnt > 1, lp[np.minimum(start + 1, len(lp) - 1)], -1) if len(lp) else np.full(ne, -1)
    return f1, f2, cnt


def convex_edges(me):
    """Edges whose two faces meet outward (open / non-manifold edges count as outward)."""
    f1, f2, cnt = _edge_faces(me)
    cen = np.empty(len(me.polygons) * 3)
    me.polygons.foreach_get('center', cen)
    nrm = np.empty(len(me.polygons) * 3)
    me.polygons.foreach_get('normal', nrm)
    cen, nrm = cen.reshape(-1, 3), nrm.reshape(-1, 3)
    out = np.ones(len(me.edges), bool)
    two = cnt == 2
    a, b = f1[two], f2[two]
    out[two] = ((cen[b] - cen[a]) * nrm[a]).sum(1) < 0.0
    return out


def mark_pairs(me, pairs, crease=True, sharp=False):
    """Mark the edges joining point ``pairs`` (k, 2) hard: a full Crease, a Bevel Weight (Sharp too with ``sharp`` -
    off for Client Look); faces smooth."""
    ev = np.empty(len(me.edges) * 2, np.int64)
    me.edges.foreach_get('vertices', ev)
    ev = ev.reshape(-1, 2)
    n = max(len(me.vertices), 1)
    key = ev.min(1) * n + ev.max(1)
    pairs = np.asarray(pairs, np.int64).reshape(-1, 2)
    pk = pairs.min(1) * n + pairs.max(1) if len(pairs) else np.zeros(0, np.int64)
    hard = np.isin(key, pk)
    a = me.attributes.get(HARD) or me.attributes.new(HARD, 'BOOLEAN', 'EDGE')
    a.data.foreach_set('value', hard)
    a = me.attributes.get('sharp_edge') or me.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE')
    a.data.foreach_set('value', hard & sharp)
    conv = me.attributes.get(CONVEX) or me.attributes.new(CONVEX, 'BOOLEAN', 'EDGE')
    conv.data.foreach_set('value', hard & convex_edges(me))
    _set_edge_float(me, 'crease_edge', hard * (1.0 if crease else 0.0))
    _set_edge_float(me, 'bevel_weight_edge', hard.astype(np.float32))
    sm = np.ones(len(me.polygons), bool)
    me.polygons.foreach_set('use_smooth', sm)
    me.update()
    return int(hard.sum())


def _edge_bool(me, name):
    a = me.attributes.get(name)
    out = np.zeros(len(me.edges), bool)
    if a is not None and a.domain == 'EDGE':
        a.data.foreach_get('value', out)
    return out


def _set_edge_float(me, name, vals):
    a = me.attributes.get(name)
    if a is None or a.domain != 'EDGE' or a.data_type != 'FLOAT':
        if a is not None:
            me.attributes.remove(a)
        a = me.attributes.new(name, 'FLOAT', 'EDGE')
    a.data.foreach_set('value', vals.astype(np.float32))


def hard_flags(me):
    """The hard edges Find Edges / Quad Remesh found (older files: the Sharp marks)."""
    return _edge_bool(me, HARD if me.attributes.get(HARD) is not None else 'sharp_edge')


def marks(me, st):
    """Crease, bevel weight and (no Client Look) Sharp from the hard edges and the shelf settings (any mode).
    Returns the bevel Width the weights go with (more than the shelf's with Match Original)."""
    hard = hard_flags(me)
    conv = _edge_bool(me, CONVEX)
    _set_edge_float(me, 'crease_edge', hard * (1.0 if st.he_crease else 0.0))
    w = (hard & (conv | (not st.he_outer))).astype(np.float32)
    w[hard & ~conv] *= INSIDE                          # (inside corners: wide bevels fold over there)
    width = st.he_width
    rnd = me.attributes.get(ROUND)
    if getattr(st, 'he_match', False) and rnd is not None and rnd.domain == 'EDGE' and width > 0 and w.any():
        r = np.empty(len(me.edges), np.float32)        # 0.24.74 each edge as round as the original there: the
        rnd.data.foreach_get('value', r)               # shelf's Width is the least (a sharp edge keeps it)
        want = np.where(w > 0, np.maximum(w * width, np.minimum(r, MATCH_MAX * _size(me))), 0.0)
        width = max(width, float(want.max()))
        w = (want / width).astype(np.float32)
    if getattr(st, 'he_bevel', True):                  # 0.24.73 narrower only where it must be
        w = fit_weights(me, w, width)
    _set_edge_float(me, 'bevel_weight_edge', w)
    a = me.attributes.get('sharp_edge')
    if st.he_client:
        if a is not None:
            me.attributes.remove(a)
    else:
        if a is None:
            a = me.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE')
        a.data.foreach_set('value', hard)
    me.update()
    return width


def set_live(ob, st):
    """Add / update / remove the live Bevel, Subdivide and Weighted Normals of ``ob`` (in that order, last)."""
    mods = ob.modifiers
    width = marks(ob.data, st)
    bev = mods.get(BEVEL)
    if st.he_bevel:
        if bev is None:
            bev = mods.new(BEVEL, 'BEVEL')
        bev.affect = 'EDGES'
        bev.limit_method = 'WEIGHT'
        bev.edge_weight = 'bevel_weight_edge'
        bev.width = width
        if getattr(st, 'he_style', 'ROUND') == 'CHAMFER':      # 0.24.73 flat cut + support loops (stays flat
            _chamfer_profile(bev)                             # through Subdivide, edges of the cut stay crisp)
        else:
            bev.profile_type = 'SUPERELLIPSE'
            bev.segments = st.he_segments
            bev.profile = st.he_profile
        bev.use_clamp_overlap = True
        bev.harden_normals = st.he_normals
        bev.use_clamp_overlap = not _fits_unclamped(ob, bev)     # 0.24.73 (Clamp narrows every bevel of the part)
        _keep_sound(ob, bev)                                     # 0.24.83 a broken bevel: narrower, else none
    elif bev is not None:
        mods.remove(bev)
    sub = mods.get(SUBSURF)
    if st.he_subdiv > 0:
        if sub is None:
            sub = mods.new(SUBSURF, 'SUBSURF')
        sub.levels = sub.render_levels = st.he_subdiv
        sub.use_creases = True
        sub.boundary_smooth = 'PRESERVE_CORNERS'
    elif sub is not None:
        mods.remove(sub)
    fit = mods.get(FIT)
    src = source(ob)
    if src is not None and getattr(st, 'he_fit', True):
        if fit is None:
            fit = mods.new(FIT, 'SHRINKWRAP')
        fit.target = src
        fit.wrap_method = 'NEAREST_SURFACEPOINT'
        fit.vertex_group = FIT_GROUP if ob.vertex_groups.get(FIT_GROUP) is not None else ''
    elif fit is not None:
        mods.remove(fit)
    nrm = mods.get(NORMALS)
    if st.he_normals:
        if nrm is None:
            nrm = mods.new(NORMALS, 'WEIGHTED_NORMAL')
        nrm.keep_sharp = True
        nrm.mode = 'FACE_AREA'
    elif nrm is not None:
        mods.remove(nrm)
    ours = [m for m in (mods.get(n) for n in LIVE) if m is not None]
    for i, m in enumerate(ours):                     # ours at the end, in this order
        target = len(mods) - len(ours) + i
        k = list(mods).index(m)
        if k != target:
            mods.move(k, target)


def _probe_off(ob, bev):
    """Test-run the bevel of ``ob`` without Clamp Overlap (one segment, on a probe object sharing the mesh): the points
    of the result further than PROBE_TOL x Width off the surface (a one-segment bevel only slides points along the
    edges next to it - a bevel running past the end of an edge leaves the surface).  None when it can't be tested."""
    me = ob.data
    scene = getattr(bpy.context, 'scene', None)
    if scene is None:
        return None
    from mathutils.bvhtree import BVHTree
    tmp = bpy.data.objects.new('.mch_he_probe', me)
    try:
        scene.collection.objects.link(tmp)
        m = tmp.modifiers.new('probe', 'BEVEL')
        m.affect = 'EDGES'
        m.limit_method = 'WEIGHT'
        m.edge_weight = bev.edge_weight
        m.width = bev.width
        m.segments = 1
        m.use_clamp_overlap = False
        dg = bpy.context.evaluated_depsgraph_get()
        ev = tmp.evaluated_get(dg)
        out = ev.to_mesh()
        try:
            pts = [v.co.copy() for v in out.vertices]
        finally:
            ev.to_mesh_clear()
    except (RuntimeError, ReferenceError):
        return None
    finally:
        bpy.data.objects.remove(tmp)
    bvh = BVHTree.FromPolygons([v.co for v in me.vertices], [p.vertices for p in me.polygons])
    tol = PROBE_TOL * bev.width
    return [c for c in pts if (lambda h: h[0] is None or h[3] > tol)(bvh.find_nearest(c))]


def _fits_unclamped(ob, bev):
    """True when the bevel of ``ob`` overlaps nowhere without Clamp Overlap (Clamp narrows every bevel of the part to
    its tightest spot) - where the test run still runs over, the bevels around it are halved and it runs again."""
    me = ob.data
    if bev.width <= 0 or not len(me.polygons) or len(me.polygons) > PROBE_MAX:
        return False
    a = me.attributes.get(bev.edge_weight or 'bevel_weight_edge')
    if a is None or a.domain != 'EDGE':
        return False
    from mathutils.kdtree import KDTree
    w = np.empty(len(me.edges), np.float32)
    a.data.foreach_get('value', w)
    if not w.any():
        return True
    ev = np.empty(len(me.edges) * 2, np.int64)
    me.edges.foreach_get('vertices', ev)
    ev = ev.reshape(-1, 2)
    kd = KDTree(len(me.vertices))
    for v in me.vertices:
        kd.insert(v.co, v.index)
    kd.balance()
    for _r in range(PROBE_ROUNDS):
        off = _probe_off(ob, bev)
        if off is None:
            return False
        if not off:
            return True
        near = np.zeros(len(me.vertices), bool)
        for c in off:
            for _co, i, _d in kd.find_n(c, 3):
                near[i] = True
        ring = near[ev].any(1)                         # (the edges at those points, then one ring further)
        near[ev[ring].ravel()] = True
        w[near[ev].any(1)] *= 0.5
        a.data.foreach_set('value', w)
        me.update()
    return False


def _broken(ob):
    """(open or 3+-face edges, zero-area faces, edges, faces) of the evaluated mesh of ``ob`` (its live stack
    included)."""
    try:
        dg = bpy.context.evaluated_depsgraph_get()
        me = ob.evaluated_get(dg).data
        if not len(me.polygons):
            return 0, 0, 0, 0
        lv = np.empty(len(me.loops), np.int64)
        me.loops.foreach_get('edge_index', lv)
        cnt = np.bincount(lv, minlength=len(me.edges))
        area = np.empty(len(me.polygons), np.float32)
        me.polygons.foreach_get('area', area)
        return int((cnt != 2).sum()), int((area < 1e-12).sum()), len(me.edges), len(me.polygons)
    except (AttributeError, RuntimeError, ReferenceError, ValueError):
        return 0, 0, 0, 0


def _sound(ob, base_nm):
    """The bevel result is sound when it adds no more broken edges / zero-area faces than a few (the bevel modifier
    leaves the odd one where bevelled edges meet - that was always so and is harmless): over 8 or 0.1 % is broken."""
    nm, zero, ne, nf = _broken(ob)
    return nm - base_nm <= max(8, 0.001 * ne) and zero <= max(4, 0.001 * nf)


def _keep_sound(ob, bev):
    """0.24.83 The bevel modifier on a dense part with many hard edges (a DynaMesh / Decimate body: 2,000 hard edges,
    0.04 wide) came out broken - open edges, edges shared by 3+ faces, zero-area faces by the hundred - even with
    Clamp Overlap.  The result is checked; a broken one has its width halved (up to SOUND_ROUNDS times), and when
    that does not help the bevel is dropped: a clean mesh without a bevel beats a broken one.  The note is reported
    with Find Edges."""
    from . import core_geometry as cg
    ob.pop(NOTE, None)
    base_nm = cg.non_manifold_edge_count(ob.data)
    if _sound(ob, base_nm):
        return
    width0 = bev.width
    for _r in range(SOUND_ROUNDS):
        bev.width *= 0.5
        if _sound(ob, base_nm):
            ob[NOTE] = f'bevel width {width0:.4g} overlapped (broken faces), {bev.width:.4g} used'
            return
    ob.modifiers.remove(bev)
    ob[NOTE] = f'bevel {width0:.4g} wide overlaps here whatever the width - no bevel (Decimate / Quad Remesh lower first)'


def _chamfer_profile(bev):
    """Bevel profile for Chamfer: a straight cut with a support point near each side (3 segments)."""
    bev.profile_type = 'CUSTOM'
    bev.segments = 3
    cp = bev.custom_profile
    want = [(1.0, 0.0), (1.0 - CHAMFER_SUPPORT, CHAMFER_SUPPORT), (CHAMFER_SUPPORT, 1.0 - CHAMFER_SUPPORT), (0.0, 1.0)]
    have = sorted(((round(p.location[0], 4), round(p.location[1], 4)) for p in cp.points), reverse=True)
    if have != [(round(x, 4), round(y, 4)) for x, y in want]:
        while len(cp.points) > 2:                     # (the two ends stay: Blender keeps at least two)
            cp.points.remove(cp.points[1])
        cp.points.add(want[1][0], want[1][1])
        cp.points.add(want[2][0], want[2][1])
    for p in cp.points:
        p.handle_type_1 = p.handle_type_2 = 'VECTOR'
    cp.use_sample_straight_edges = True
    cp.update()


def plain_mesh(context, ob):
    """Client Look: no Sharp / Crease / Bevel Weight / custom normals, every face smooth - the mesh alone gives
    the look (the same in Maya / Max / ZBrush)."""
    me = ob.data
    for name in ('sharp_edge', 'crease_edge', 'bevel_weight_edge', HARD, CONVEX, ROUND, 'custom_normal'):
        a = me.attributes.get(name)
        if a is not None:
            me.attributes.remove(a)
    if getattr(me, 'has_custom_normals', False):
        try:
            with context.temp_override(object=ob, active_object=ob):
                bpy.ops.mesh.customdata_custom_splitnormals_clear()
        except RuntimeError:
            pass
    me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), bool))
    me.update()


def apply_live(context, ob, st=None):
    """Bake the live modifiers into the mesh (Object Mode); with Client Look the result is a plain mesh.  Returns how
    many modifiers."""
    n = 0
    with context.temp_override(object=ob, active_object=ob):
        for name in LIVE:
            if ob.modifiers.get(name) is not None:
                bpy.ops.object.modifier_apply(modifier=name)
                n += 1
    if n:
        from . import core_geometry as cg                  # 0.24.83 a doubled corner the bevel left: dissolved
        cg.tidy_result(ob.data, shards=False, slivers=False)
    if st is None or st.he_client:
        plain_mesh(context, ob)
    drop_source(ob)
    return n


def source(ob):
    """The dense original an Edge Mesh result was made from (None when there is none)."""
    try:
        src = ob.get(SRC)
    except (TypeError, ReferenceError):
        return None
    return src if isinstance(src, bpy.types.Object) and src.type == 'MESH' else None


def keep_source(ob, me):
    """Keep mesh ``me`` (the dense original) as the off-scene Fit to Original target of ``ob``: an object in no
    scene (never exported, never seen) kept by a fake user."""
    drop_source(ob)
    src = bpy.data.objects.new(ob.name + '_EdgeSource', me)
    src.use_fake_user = True
    src.matrix_world = ob.matrix_world.copy()
    ob[SRC] = src
    return src


def drop_source(ob):
    """The off-scene original goes (Apply / Clear: nothing needs it any more)."""
    src = source(ob)
    ob.pop(SRC, None)
    g = ob.vertex_groups.get(FIT_GROUP)
    if g is not None:
        ob.vertex_groups.remove(g)
    if src is None:
        return
    me = src.data
    src.use_fake_user = False
    if src.users == 0:
        bpy.data.objects.remove(src)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)


def clear(ob):
    """The hard-edge marks and the live modifiers off ``ob``."""
    for name in LIVE:
        m = ob.modifiers.get(name)
        if m is not None:
            ob.modifiers.remove(m)
    me = ob.data
    for name in ('sharp_edge', 'crease_edge', 'bevel_weight_edge', CONVEX, HARD, ROUND):
        a = me.attributes.get(name)
        if a is not None:
            me.attributes.remove(a)
    me.update()
    ob.pop(KEY, None)
    drop_source(ob)


def live_update(st, context):
    """A Hard Edges setting changed on the shelf: the active SubTool's live modifiers follow.  0.24.73 at a pace set
    by their cost while a slider is dragged (live_queue: the per-edge bevel fit and its test run on every step made
    a big mesh stutter); the object and the settings are looked up again when it runs (Ctrl+Z may have replaced
    them)."""
    ob = context.active_object
    if ob is not None and ob.type == 'MESH' and KEY in ob:
        from . import live_queue
        name = ob.name

        def run():
            o = bpy.data.objects.get(name)
            scene = bpy.context.scene
            if o is not None and o.type == 'MESH' and KEY in o and scene is not None and hasattr(scene, 'mch_zb'):
                set_live(o, scene.mch_zb)
        live_queue.queue(('hard_edges', name), run)
