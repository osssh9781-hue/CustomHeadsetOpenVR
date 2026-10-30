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
LAM, MU = 0.5, -0.53          # Taubin smoothing: shrink step, then the slightly bigger grow step that gives the volume back
#                               sizes: no frequency is ever amplified (a bigger grow step ran away between fixed
#                               lines on a pocket corner: +4 % of the part after four levels)
ITERS = 10                    # Taubin pairs per level
MAX_LEVELS = 4
TURN = math.radians(25.0)      # a hard line bending more than this at a point: that point is a corner
MIN_FACES = 4
INFO = {}                     # the last run, for the tests / message
STRIP = '.mch_bk_strip'       # face: made by the fillet bevel (free to round)
FLAT = '.mch_bk_flat'         # face: a true flat (every edge hard, coplanar with its neighbour, or next to a strip)
REGION = '.mch_bk_region'     # face: its coplanar region id on the source (rides through the subdivision)
PLANES = {}                   # flat region id -> (normal, offset): the plane it lies in
STRIP_PLANES = {}             # strip region id -> flat region ids whose planes its points never cross
FLAT_TOL = math.radians(1.0)
ANGLE_EPS = 1e-4              # hard_mask: 'more than the angle' with a margin, so exactly-30-degree bevel rows stay soft
BEVEL_TURN = math.radians(100.0)   # bevel_rows: a run of rows turning up to this is a bevel; more = a curved surface
BEVEL_NARROW = 0.25           # bevel_rows: a row's short side is under this share of its long side
FLAT_RATIO = 3.0              # a flat region is at least this much bigger (sqrt area) than any soft neighbour region


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
        ang = e_sorted[s2[d < math.cos(angle) - ANGLE_EPS]]      # (strictly more than the angle: a 2-segment
        if specks and len(ang):                                    # bevel's 30-degree rows are soft, not lines)
            ev = mio.read_edge_verts(me)
            deg = np.bincount(ev[ang].ravel(), minlength=len(me.vertices))
            lone = (deg[ev[ang, 0]] == 1) & (deg[ev[ang, 1]] == 1)
            ang = ang[~lone]
        hard[ang] = True
    if memory:
        hard |= em.marked(me)
    return hard


def bevel_rows(me, hard, narrow=BEVEL_NARROW, lo=math.radians(2.0), hi=math.radians(70.0)):
    """bool per edge: the long edges of bevel rows - a narrow quad (short side under ``narrow`` x its long side)
    whose two long edges both bend (between ``lo`` and ``hi``, so neither is flat nor already a hard edge's 90):
    a row of a modelled bevel / chamfer.  Those edges become lines, so the bevel keeps exactly the profile it was
    modelled with (the user: "a run of similar angles = a bevel").  Rows along existing hard edges count too."""
    from . import edge_memory as em
    from . import mesh_io as mio
    ne, nf = len(me.edges), len(me.polygons)
    out = np.zeros(ne, bool)
    if nf == 0:
        return out
    start, tot = mio.read_face_starts(me)
    quads = np.flatnonzero(np.asarray(tot) == 4)
    if not len(quads):
        return out
    ce = mio.read_corner_edges(me)
    co = mio.read_co(me)
    ev = mio.read_edge_verts(me)
    el = np.linalg.norm(co[ev[:, 0]] - co[ev[:, 1]], axis=1)
    st = np.asarray(start)[quads]
    e4 = np.stack([ce[st], ce[st + 1], ce[st + 2], ce[st + 3]], 1)        # the quad's edges in order
    l4 = el[e4]
    pairA = np.minimum(l4[:, 0], l4[:, 2])                                  # opposite pairs: (0,2) and (1,3)
    pairB = np.minimum(l4[:, 1], l4[:, 3])
    maxA = np.maximum(l4[:, 0], l4[:, 2])
    maxB = np.maximum(l4[:, 1], l4[:, 3])
    # dihedral per edge
    e_sorted, f_sorted, starts, ends = em._edge_faces(me)
    cnt = ends - starts
    s2 = starts[cnt == 2]
    nrm = np.empty(nf * 3, np.float32)
    me.polygons.foreach_get('normal', nrm)
    nrm = nrm.reshape(-1, 3)
    bend = np.zeros(ne)
    d = np.clip(np.einsum('ij,ij->i', nrm[f_sorted[s2]], nrm[f_sorted[s2 + 1]]), -1.0, 1.0)
    bend[e_sorted[s2]] = np.arccos(d)
    qa, qb = [], []                                                         # the row quads' two long edges
    for long_pair, short_max in (((0, 2), maxB), ((1, 3), maxA)):
        a, b = e4[:, long_pair[0]], e4[:, long_pair[1]]
        rows = (short_max < narrow * np.minimum(el[a], el[b])) & (bend[a] > lo) & (bend[a] < hi) & (bend[b] > lo) & (bend[b] < hi)
        qa.append(a[rows])
        qb.append(b[rows])
    qa, qb = np.concatenate(qa), np.concatenate(qb)
    if not len(qa):
        return out
    # rows sharing a long edge form a run; a run that turns up to BEVEL_TURN in all is a bevel (its rows held as
    # lines: the profile stays as modelled), a run that turns more is a curved surface - a 16-sided cylinder, a
    # half-pipe groove - and rounds
    nq = len(qa)
    comp = np.arange(nq)
    key = np.concatenate([qa, qb])
    qid = np.concatenate([np.arange(nq), np.arange(nq)])
    order = np.argsort(key, kind='stable')
    key, qid = key[order], qid[order]
    same = np.flatnonzero(key[1:] == key[:-1])                            # two rows on one long edge
    pa, pb = qid[same], qid[same + 1]
    for _ in range(64):
        before = comp.copy()
        lo_ = np.minimum(comp[pa], comp[pb])
        np.minimum.at(comp, pa, lo_)
        np.minimum.at(comp, pb, lo_)
        comp = comp[comp]
        if np.array_equal(comp, before):
            break
    _u, comp = np.unique(comp, return_inverse=True)
    nc = int(comp.max()) + 1
    # the turn of a run: every distinct long edge of its rows, once
    ek = np.unique(np.stack([np.concatenate([comp, comp]), np.concatenate([qa, qb])], 1), axis=0)
    turn = np.bincount(ek[:, 0], weights=bend[ek[:, 1]], minlength=nc)
    is_bevel = turn <= BEVEL_TURN
    sel = is_bevel[comp]
    out[qa[sel]] = True
    out[qb[sel]] = True
    return out


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


def flag_flats(me, hard, tol=FLAT_TOL, ratio=None):
    """Face flag FLAT: a face of a true flat.  Faces are grouped into coplanar regions (neighbours within ``tol``);
    a region is flat when every neighbouring region it meets across a soft edge (not hard, not coplanar, not a
    fillet strip) is much smaller than it - ``ratio`` x in size (sqrt of area).  A cube's top next to a bevel strip:
    flat (the strip rows are thin).  A facet of a curved surface next to facets of the same size: not flat - it
    rounds.  A region with no soft neighbour at all (every edge hard or a boundary) is flat.  Returns the count."""
    from . import edge_memory as em
    ratio = FLAT_RATIO if ratio is None else ratio
    nf = len(me.polygons)
    if nf == 0:
        return 0
    strip = _face_bool(me, STRIP)
    e_sorted, f_sorted, starts, ends = em._edge_faces(me)
    nrm = np.empty(nf * 3, np.float32)
    me.polygons.foreach_get('normal', nrm)
    nrm = nrm.reshape(-1, 3)
    area = np.empty(nf, np.float32)
    me.polygons.foreach_get('area', area)
    cnt = ends - starts
    two = np.flatnonzero(cnt == 2)
    s2 = starts[two]
    fa, fb = f_sorted[s2], f_sorted[s2 + 1]
    d = np.einsum('ij,ij->i', nrm[fa], nrm[fb])
    coplanar = d > math.cos(tol)
    # coplanar regions: label propagation over the coplanar pairs (no scipy here)
    region = np.arange(nf)
    pa, pb = fa[coplanar], fb[coplanar]
    for _ in range(64):
        lo = np.minimum(region[pa], region[pb])
        before = region.copy()
        np.minimum.at(region, pa, lo)
        np.minimum.at(region, pb, lo)
        region = region[region]                      # (pointer jumping: a few rounds settle any region)
        if np.array_equal(region, before):
            break
    _u, region = np.unique(region, return_inverse=True)
    nr = int(region.max()) + 1
    r_area = np.bincount(region, weights=area, minlength=nr)
    r_len = np.sqrt(np.maximum(r_area, 0.0))
    soft = ~coplanar & ~hard[e_sorted[s2]] & ~strip[fa] & ~strip[fb]
    ra, rb = region[fa[soft]], region[fb[soft]]
    biggest = np.zeros(nr)                            # the largest soft neighbour region of each region
    np.maximum.at(biggest, ra, r_len[rb])
    np.maximum.at(biggest, rb, r_len[ra])
    flat_region = r_len >= ratio * biggest             # (no soft neighbour: biggest 0 -> flat)
    ok_face = flat_region[region] & ~strip
    # the small regions a flat meets across a soft edge (bevel strip rows, corner patches, fillet rows) are strips:
    # they round but only ever shrink (Taubin's grow step overshoots on a tight patch between held rings)
    big_flat = np.zeros(nr)
    np.maximum.at(big_flat, ra, np.where(flat_region[rb], r_len[rb], 0.0))
    np.maximum.at(big_flat, rb, np.where(flat_region[ra], r_len[ra], 0.0))
    for _ in range(3):                                 # ... and the small regions next to those (corner patches)
        grown = big_flat.copy()
        is_strip = ~flat_region & (big_flat >= ratio * r_len)
        np.maximum.at(grown, ra, np.where(is_strip[rb], big_flat[rb], 0.0))
        np.maximum.at(grown, rb, np.where(is_strip[ra], big_flat[ra], 0.0))
        if np.array_equal(grown, big_flat):
            break
        big_flat = grown
    strip_region = ~flat_region & (big_flat >= ratio * r_len)
    # the planes of the flat regions, and for every strip region the flat planes it must never cross (its own
    # soft flat neighbours, and through neighbouring strips their flats): bake_mesh clamps the strip points to them
    cx = np.empty(nf * 3, np.float32)
    me.polygons.foreach_get('center', cx)
    cx = cx.reshape(-1, 3)
    pn = np.zeros((nr, 3))
    pc = np.zeros((nr, 3))
    for k in range(3):
        pn[:, k] = np.bincount(region, weights=nrm[:, k] * area, minlength=nr)
        pc[:, k] = np.bincount(region, weights=cx[:, k] * area, minlength=nr)
    ln = np.linalg.norm(pn, axis=1)
    pn[ln > 1e-12] /= ln[ln > 1e-12][:, None]
    pc[r_area > 0] /= r_area[r_area > 0][:, None]
    PLANES.clear()
    for r in np.flatnonzero(flat_region):
        PLANES[int(r)] = (pn[r].copy(), float(pn[r] @ pc[r]))
    touch = {}
    for a_, b_ in zip(ra.tolist(), rb.tolist()):
        touch.setdefault(a_, set()).add(b_)
        touch.setdefault(b_, set()).add(a_)
    STRIP_PLANES.clear()
    strip_ids = set(np.flatnonzero(strip_region).tolist()) | set(region[strip].tolist())
    for r in strip_ids:
        seen, frontier, flats = {r}, [r], set()
        for _ in range(3):                             # (a corner patch reaches its flats through the strip rows)
            nxt = []
            for q in frontier:
                for nb in touch.get(q, ()):
                    if nb in PLANES:
                        flats.add(nb)
                    elif nb in strip_ids and nb not in seen:
                        seen.add(nb)
                        nxt.append(nb)
            frontier = nxt
        if flats:
            STRIP_PLANES[int(r)] = sorted(flats)
    ra_ = me.attributes.get(REGION)
    if ra_ is not None and (ra_.domain != 'FACE' or ra_.data_type != 'INT'):
        me.attributes.remove(ra_)
        ra_ = None
    if ra_ is None:
        ra_ = me.attributes.new(REGION, 'INT', 'FACE')
    ra_.data.foreach_set('value', region.astype(np.int32))
    new_strip = strip_region[region] & ~strip
    if new_strip.any():
        st = me.attributes.get(STRIP)
        if st is not None and st.domain != 'FACE':
            me.attributes.remove(st)
            st = None
        if st is None:
            st = me.attributes.new(STRIP, 'BOOLEAN', 'FACE')
        st.data.foreach_set('value', strip | new_strip)
    more = np.flatnonzero(cnt > 2)                     # non-manifold: never a flat
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
    strip = _face_bool(me, STRIP)
    cv = mio.read_corner_verts(me)
    _start, tot = mio.read_face_starts(me)
    f_of = np.repeat(np.arange(nf), tot)
    nrm = np.empty(nf * 3, np.float32)
    me.polygons.foreach_get('normal', nrm)
    nrm = nrm.reshape(-1, 3).astype(np.float64)
    avg = np.zeros((nv, 3))
    keep = flat[f_of]                                     # only the flat faces round the point count: the ring where
    for k in range(3):                                    # a flat meets a fillet / bevel strip stays in the flat's plane
        avg[:, k] = np.bincount(cv[keep], weights=nrm[f_of[keep], k], minlength=nv)
    ln = np.linalg.norm(avg, axis=1)
    avg[ln > 1e-12] /= ln[ln > 1e-12][:, None]
    d = np.einsum('ij,ij->i', nrm[f_of], avg[cv])
    d = np.where(flat[f_of], d, 1.0)                      # a non-flat face round the point is ignored
    mind = np.ones(nv)
    np.minimum.at(mind, cv, d)
    planar = (mind > math.cos(tol)) & (ln > 1e-12)
    out[planar] = avg[planar]
    return out


def strip_points(me):
    """bool per point: every face round it is a fillet strip face (the strip's inside): those only shrink (no
    Taubin grow step), so the fillet rounds inward and never bulges past the flats it joins."""
    from . import mesh_io as mio
    nv = len(me.vertices)
    strip = _face_bool(me, STRIP)
    if not strip.any():
        return np.zeros(nv, bool)
    cv = mio.read_corner_verts(me)
    _start, tot = mio.read_face_starts(me)
    f_of = np.repeat(np.arange(len(me.polygons)), tot)
    allstrip = np.ones(nv, bool)
    np.logical_and.at(allstrip, cv, strip[f_of])
    has = np.zeros(nv, bool)
    has[cv] = True
    return allstrip & has


def corner_arrays(me):
    """(corner vertex, next corner's vertex round the face, face of each corner) for ``vertex_normals``."""
    from . import mesh_io as mio
    cv = mio.read_corner_verts(me)
    start, tot = mio.read_face_starts(me)
    nf = len(me.polygons)
    f_of = np.repeat(np.arange(nf), tot)
    idx = np.arange(len(cv))
    nxt = idx + 1
    last = np.asarray(start) + np.asarray(tot) - 1
    nxt[last] = np.asarray(start)
    return cv.astype(np.int64), cv[nxt].astype(np.int64), f_of


def vertex_normals(co, corners):
    """Area-weighted point normals from the current positions (Newell's face normals summed round each point)."""
    cv, cvn, f_of = corners
    nv = len(co)
    nf = int(f_of.max()) + 1 if len(f_of) else 0
    cr = np.cross(co[cv], co[cvn])
    fn = np.zeros((nf, 3))
    for k in range(3):
        fn[:, k] = np.bincount(f_of, weights=cr[:, k], minlength=nf)
    vn = np.zeros((nv, 3))
    for k in range(3):
        vn[:, k] = np.bincount(cv, weights=fn[f_of, k], minlength=nv)
    ln = np.linalg.norm(vn, axis=1)
    ok = ln > 1e-14
    vn[ok] /= ln[ok][:, None]
    return vn


def taubin(co, E, hard, iters=ITERS, lam=LAM, mu=MU, plane_n=None, shrink_only=None, corners=None):
    """Taubin-smoothed copy of ``co``: E = edges (m, 2), hard = bool per edge.  Points on hard lines slide along
    them, corners stay, points with a ``plane_n`` normal stay in that plane, ``shrink_only`` points skip the grow
    step (a fillet strip).  With ``corners`` (corner_arrays) a free point moves along its own normal only: no
    drift across the surface, so a flat next to a bevel strip stays where it is and the strip alone rounds (without
    it the ring between them slid into the strip and the box's edges bowed).  Returns (co, corners, line points)."""
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
        keep = line[v2]
        lv, lj1, lj2 = v2[keep], vj[f2][keep], vj[f2 + 1][keep]   # a line point and its two line neighbours
    else:
        lv = lj1 = lj2 = np.zeros(0, np.int64)
    free = ~corner

    # neighbours weighted by 1 / edge length (from the level's start): on a bevel row 0.9 long and 0.005 wide the
    # plain average sat near the far end of the row, a constant pull the Taubin pair never cancelled - the point
    # crept along its normal 0.004 per pair, 0.09 per level (the user's bevelled block)
    wl = 1.0 / np.maximum(np.linalg.norm(co[E[:, 0]] - co[E[:, 1]], axis=1), 1e-9)
    wsum = np.bincount(E[:, 0], weights=wl, minlength=nv) + np.bincount(E[:, 1], weights=wl, minlength=nv)

    def avg(c, EE, deg):
        s = np.zeros_like(c)
        for k in range(3):
            s[:, k] = (np.bincount(EE[:, 0], weights=wl * c[EE[:, 1], k], minlength=nv)
                       + np.bincount(EE[:, 1], weights=wl * c[EE[:, 0], k], minlength=nv))
        return s / np.maximum(wsum, 1e-12)[:, None]

    # the normals a free point moves along: from the positions at the START of the level, never re-measured while
    # smoothing - on a bevel strip 0.005 wide and 0.9 long, a move of 0.008 tilts the strip's faces by 60 degrees,
    # the "normal" swings into the strip's long direction and the big in-plane Laplacian pours into it (the user's
    # bevelled block: a bottom corner ran 0.5 away in one level)
    vn = vertex_normals(co, corners) if corners is not None else None
    for _ in range(iters):
        for w in (lam, mu):
            t = avg(co, E, deg_all)
            if len(lv):                                   # a line point: onto the chord between its two line
                p1, p2 = co[lj1], co[lj2]                 # neighbours, at the spot NEAREST to where it is (the
                dv = p2 - p1                              # chord's middle would drag it along a long edge - a
                l2 = np.einsum('ij,ij->i', dv, dv)        # Boolean sliver's - by half the part)
                u = np.clip(np.einsum('ij,ij->i', co[lv] - p1, dv) / np.maximum(l2, 1e-18), 0.0, 1.0)
                t[lv] = p1 + u[:, None] * dv
            d = t - co
            d[~free] = 0
            if vn is not None:                        # free points: along the normal only (no surface drift)
                along = np.einsum('ij,ij->i', d, vn)[:, None] * vn
                d = np.where(line[:, None], d, along)
            if plane_n is not None:
                d -= np.einsum('ij,ij->i', d, plane_n)[:, None] * plane_n
            if shrink_only is not None and w < 0:
                d[shrink_only] = 0
            co += w * d
    return co, int(corner.sum()), int(line.sum())


def _face_int(me, name):
    out = np.zeros(len(me.polygons), np.int32)
    a = me.attributes.get(name)
    if a is not None and a.domain == 'FACE':
        a.data.foreach_get('value', out)
    return out


def clamp_strips(me, co):
    """Strip points (bevel rows, corner patches, fillet rows) pushed back onto the planes of the flats they belong
    to when a smoothing step carried them past one: a bevelled box edge rounds inside its corner, never bulges
    out of the box.  Returns the number of points moved."""
    if not STRIP_PLANES:
        return 0
    from . import mesh_io as mio
    strip = _face_bool(me, STRIP)
    if not strip.any():
        return 0
    region = _face_int(me, REGION)
    cv = mio.read_corner_verts(me)
    _start, tot = mio.read_face_starts(me)
    f_of = np.repeat(np.arange(len(me.polygons)), tot)
    sel = strip[f_of]
    key = np.unique(region[f_of[sel]].astype(np.int64) * len(co) + cv[sel])
    reg = key // len(co)
    vert = key % len(co)
    moved = 0
    order = np.argsort(reg, kind='stable')
    reg, vert = reg[order], vert[order]
    starts = np.flatnonzero(np.r_[True, reg[1:] != reg[:-1]])
    ends = np.append(starts[1:], len(reg))
    for a, b in zip(starts, ends):
        planes = STRIP_PLANES.get(int(reg[a]))
        if not planes:
            continue
        vs = vert[a:b]
        for pid in planes:
            n, d = PLANES[pid]
            sd = co[vs] @ n - d
            out = sd > 1e-9
            if out.any():
                co[vs[out]] -= sd[out][:, None] * n
                moved += int(out.sum())
    return moved


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
    rows = bevel_rows(me, hard)
    n_rows = int((rows & ~hard).sum())
    hard = hard | rows
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
        co, corners, lines = taubin(co, E, sharp, iters, plane_n=planar_normals(me), corners=corner_arrays(me))
        clamp_strips(me, co)
        me.vertices.foreach_set('co', co.astype(np.float32).ravel())
        me.update()
    co, E, sharp = _arrays(me)
    co, corners, lines = taubin(co, E, sharp, iters, plane_n=planar_normals(me), corners=corner_arrays(me))
    clamp_strips(me, co)
    if src is not None:
        co = _reproject(co, src, 1.0 - max(0.0, min(1.0, rounding)))
        bpy.data.meshes.remove(src)
    me.vertices.foreach_set('co', co.astype(np.float32).ravel())
    for name in (STRIP, FLAT, REGION):
        a = me.attributes.get(name)
        if a is not None:
            me.attributes.remove(a)
    me.update()
    info = dict(faces0=faces0, faces=len(me.polygons), hard=n_hard, corners=corners, lines=lines,
                fillet_edges=n_fillet, flats=n_flat, bevel_rows=n_rows, levels=levels, seconds=time.time() - t0)
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
            f'({f["corners"]:,} corners fixed)' + (f', {f["bevel_rows"]:,} bevel row edges held' if f.get('bevel_rows') else '')
            + (f', fillet on {f["fillet_edges"]:,} edges' if f.get('fillet_edges') else '')
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
