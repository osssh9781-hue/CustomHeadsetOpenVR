"""0.24.95 Edge Memory: the edges a tool MADE are remembered on the mesh, so later steps (Hard Edges, Bake High
Poly, Export to ZBrush, Fast Decimate) do not have to guess them from face angles.

Every cut-type tool (Cut, Line Cut, Base Mesh subtract, Box Hide Split / Apply, Boolean, Plate Detail, placed
primitives) ends with ``core_geometry.remove_cutter_attribute``: the faces the cutter made carry the cutter flag until
then.  Right before the flag goes, ``mark_cut_borders`` turns it into edge marks:

    * the border edges between cutter faces and original faces (the cut's outline), and
    * the edges inside the cutter faces where two of them meet at a real angle (a box cutter's floor / wall lines),

each marked on three edge layers at once: ``mch_hard`` (this module's own mark, the one later tools read), the
Sharp flag (shading) and a full crease (Subdivision; the ZBrush export turns creases into polygroups).

``marked(me)`` is the bool array later tools read; ``mark_edges`` is for tools that know their edges (a plate's rim)
and ``transfer`` carries the marks over a remesh (DynaMesh / Quad Remesh make a new mesh: the new edges nearest to
the old marked lines get the marks).
"""
from __future__ import annotations

import math

import numpy as np

ATTR = '.mch_hard'                # edge BOOLEAN: a remembered hard edge (internal name: Blender's voxel remesh
#                                   'Preserve Attributes' would otherwise smear it over EVERY new edge)
INNER_ANGLE = math.radians(30.0)  # two cutter faces meeting at more than this = a line of the cut itself
TRANSFER_TOL = 0.015              # transfer: an edge of the new mesh within this x mesh size of an old marked line


def _edge_attr(me, name, dtype='BOOLEAN'):
    a = me.attributes.get(name)
    if a is not None and a.domain != 'EDGE':
        me.attributes.remove(a)
        a = None
    if a is None:
        a = me.attributes.new(name, dtype, 'EDGE')
    return a


STAMP_N = 'mch_hard_n'            # mesh property: how many edges were marked when the marks were written
STAMP_E = 'mch_hard_e'            # mesh property: how many edges the mesh had then
SMEAR = 3                         # marks grown past SMEAR x (stamp + 8) with another edge count ...
SMEAR_SHARE = 0.5                 # ... and onto more than this share of all edges = a remesh smeared them


def _stamp(me, n):
    try:
        me[STAMP_N] = int(n)
        me[STAMP_E] = int(len(me.edges))
    except (TypeError, AttributeError):
        pass


def _smeared(me, n):
    """True when the marks cannot be the ones written: Blender's voxel remesh 'Preserve Attributes' copies the
    attribute onto EVERY nearby new edge (a 12-edge cube came back with all 20,172 edges marked)."""
    n0 = me.get(STAMP_N)
    e0 = me.get(STAMP_E)
    if n0 is None or e0 is None:
        return False
    ne = len(me.edges)
    # (a subdivision also grows the marks - legitimately, the split edges keep them - but never onto most edges)
    return ne != int(e0) and n > SMEAR * (int(n0) + 8) and n > SMEAR_SHARE * ne


def marked(me):
    """bool per edge: remembered hard edges (all False when the mesh has no memory, or the marks were smeared by
    a remesh - those are dropped)."""
    out = np.zeros(len(me.edges), bool)
    a = me.attributes.get(ATTR)
    if a is not None and a.domain == 'EDGE' and len(a.data) == len(out):
        a.data.foreach_get('value', out)
        if _smeared(me, int(out.sum())):
            clear(me)
            out[:] = False
    return out


def count(me):
    return int(marked(me).sum())


def has_memory(me):
    a = me.attributes.get(ATTR)
    if a is None or a.domain != 'EDGE':
        return False
    return bool(marked(me).any()) or me.get(STAMP_N) == 0


def mark_edges(me, mask, sharp=True, crease=True, add=True):
    """Mark the edges where ``mask`` (bool per edge, or edge indices) is set: mch_hard + Sharp + crease 1.0.
    ``add`` keeps the marks already there.  Returns the number of marked edges afterwards."""
    ne = len(me.edges)
    m = np.zeros(ne, bool)
    mask = np.asarray(mask)
    if mask.dtype == bool:
        m[:len(mask)] = mask[:ne]
    elif mask.size:
        m[mask.astype(np.int64)] = True
    if add:
        m |= marked(me)
    a = _edge_attr(me, ATTR)
    a.data.foreach_set('value', m)
    _stamp(me, int(m.sum()))
    if sharp:
        s = _edge_attr(me, 'sharp_edge')
        cur = np.zeros(ne, bool)
        s.data.foreach_get('value', cur)
        s.data.foreach_set('value', cur | m)
    if crease:
        c = _edge_attr(me, 'crease_edge', 'FLOAT')
        cur = np.zeros(ne, np.float32)
        c.data.foreach_get('value', cur)
        c.data.foreach_set('value', np.where(m, 1.0, cur).astype(np.float32))
    me.update()
    return int(m.sum())


def clear(me):
    """The memory off the mesh (the Sharp / crease it set stay: they are ordinary mesh data)."""
    a = me.attributes.get(ATTR)
    if a is not None:
        me.attributes.remove(a)
    for k in (STAMP_N, STAMP_E):
        if k in me:
            del me[k]


def _edge_faces(me):
    """(edge index per corner sorted by edge, face per corner in the same order, starts, ends): the faces round
    each edge without Python loops."""
    from . import mesh_io as mio
    ce = mio.read_corner_edges(me)
    _start, tot = mio.read_face_starts(me)
    f_of = np.repeat(np.arange(len(me.polygons)), tot)
    order = np.argsort(ce, kind='stable')
    e_sorted = ce[order]
    f_sorted = f_of[order]
    first = np.ones(len(e_sorted), bool)
    first[1:] = e_sorted[1:] != e_sorted[:-1]
    starts = np.flatnonzero(first)
    ends = np.append(starts[1:], len(e_sorted))
    return e_sorted, f_sorted, starts, ends


def mark_cut_borders(me, cutter_attr='mch_cutter_face', inner_angle=INNER_ANGLE, old_co=None):
    """The cutter flag (faces) turned into edge marks: cutter / original borders + the cutter's own creases.
    ``old_co`` (0.24.95): the part's points before the cut - every edge sharper than a miter with a point the cut
    made is a line too (a random-holes stress test: the cutter flag can be lost whole - an Edge Finish, a
    line groove through earlier holes - and the rim of that cut came out unmarked).  Returns the number of edges
    marked now (0 when there is nothing to go by, or nothing was cut)."""
    from . import mesh_io as mio
    attr = me.attributes.get(cutter_attr)
    nf = len(me.polygons)
    fin = me.attributes.get(FIN_BAND)
    has_fin = fin is not None and fin.domain == 'FACE' and len(fin.data) == nf
    has_old = old_co is not None and len(old_co) > 0
    if nf == 0 or len(me.edges) == 0 or ((attr is None or attr.domain != 'FACE') and not has_fin and not has_old):
        return 0
    cut = np.zeros(nf, bool)
    if attr is not None and attr.domain == 'FACE':
        attr.data.foreach_get('value', cut)
    if (not cut.any() or cut.all()) and not has_fin and not has_old:
        return 0
    e_sorted, f_sorted, starts, ends = _edge_faces(me)
    two = (ends - starts) == 2
    s2 = starts[two]
    ea = e_sorted[s2]
    fa, fb = f_sorted[s2], f_sorted[s2 + 1]
    if cut.any() and not cut.all():
        ca, cb = cut[fa], cut[fb]
        hard = ca != cb
        both = ca & cb
    else:                                            # (no usable flag: the band and the new points decide)
        hard = np.zeros(len(ea), bool)
        both = hard.copy()
    nrm = np.empty(nf * 3, np.float32)
    me.polygons.foreach_get('normal', nrm)
    nrm = nrm.reshape(-1, 3)
    d = np.einsum('ij,ij->i', nrm[fa], nrm[fb])
    hard |= both & (d < math.cos(inner_angle))
    sharp = d < math.cos(FIN_MITER)
    cv = start = tot = None
    if has_fin or has_old:
        cv = mio.read_corner_verts(me)
        start, tot = mio.read_face_starts(me)
    if has_fin:
        # 0.24.95 an Edge Finish band (the cutter flag is mixed there): its border is a line (marked when it was
        # made too - the result tidy may have moved it round a sliver since); inside it only a real corner is a line,
        # the rows of a round stay soft; and round the cut (two rings of faces from the cutter's and the band's) every
        # edge sharper than a miter is a line - where a groove leaves the part the bevel mixed the flags of the wall
        # and the part's side, and that corner came out unmarked
        band = np.zeros(nf, bool)
        fin.data.foreach_get('value', band)
        inside = band[fa] & band[fb]
        hard[inside] = d[inside] < math.cos(FIN_ROW)
        hard |= band[fa] != band[fb]
        near = cut | band
        for _ring in range(2):
            pts = np.zeros(len(me.vertices), bool)
            pts[cv[np.repeat(near, tot)]] = True
            near = np.add.reduceat(pts[cv].astype(np.int32), start) > 0
        hard |= near[fa] & near[fb] & sharp
    if has_old:
        co = mio.read_co(me)
        q = (float(np.linalg.norm(np.ptp(old_co, axis=0))) or 1.0) * 1e-6
        made = ~np.isin(_pos_keys(co, q), _pos_keys(np.asarray(old_co, np.float64), q))
        ev = mio.read_edge_verts(me)[ea]               # (an edge with a point the cut made - not every edge of a face
        hard |= (made[ev[:, 0]] | made[ev[:, 1]]) & sharp   # it touched: a cube's own rims stay as they were)
    idx = ea[hard]
    if not len(idx):
        return 0
    mark_edges(me, idx)
    return int(len(idx))


# ---- 0.24.95 Edge Finish bands (user: ZBrush CreasePG + Divide crumpled the parts cut with Line Cut + Chamfer /
# Bevel - "특정 부분이 크리즈가 안 생기나봐").  The finish replaces the cut's rim by a band of new faces before the
# cut is committed; the cutter flag on those faces is mixed (Blender's bevel copies it from either side), so
# ``mark_cut_borders`` left the band's border with the old surface unmarked: 2,004 of 4,798 hard edges on a plate
# cut with Line Cut + Chamfer, and the top, the band and the wall became ONE polygroup in ZBrush (no crease there,
# so Divide rounded it and the long fan triangles carried the bend across the whole face).
# Now the band is found by geometry (faces with a new point whose centre left the surface the finish started from),
# its two borders are marked, and its inner rows stay soft (a real corner inside it - a miter - is still a line).
FIN_BAND = '.mch_fin_band'        # face BOOLEAN: the faces an Edge Finish carved (until the cut is committed)
FIN_MITER = math.radians(50.0)    # round the cut, two faces meeting at more than this = a line
FIN_ROW = math.radians(40.0)      # inside a band: up to this a row of a round (soft); more - a miter, a chamfer's edge


def finish_snapshot(me):
    """What ``finish_band`` compares with: the points, a copy of the mesh (its surface), the marked lines and the
    edges before an Edge Finish runs.  The copy is ``finish_marks``'s to remove."""
    from . import mesh_io as mio
    return mio.read_co(me), me.copy(), lines(me), mio.read_edge_verts(me)


def _drop_snapshot(snap):
    try:
        if snap is not None and snap[1] is not None and snap[1].users == 0:
            import bpy
            bpy.data.meshes.remove(snap[1])
    except (ReferenceError, RuntimeError):
        pass


def _pos_keys(co, q):
    k = np.round(co / q).astype(np.int64)
    return (k[:, 0] * 73856093) ^ (k[:, 1] * 19349663) ^ (k[:, 2] * 83492791)


def _pair_keys(ka, kb):
    return np.minimum(ka, kb) * 1000003 + np.maximum(ka, kb)


def _restore_lines(me, seg, co, new_pt, q, size, old_co=None, old_ev=None):
    """A step that rebuilds faces (the finish round its band, the result tidy dissolving the slivers it leaves)
    brings their edges back without the marks they had - the part's own corner next to a groove's end lost its
    crease.  An unmarked edge that is an old marked edge again (same two points), or lies along one (both ends and
    its middle on the old line, running along it: a piece of it, or two pieces joined), gets its mark back.  Returns
    the number restored.  ``old_co`` / ``old_ev``: the mesh before the step - only the edges it made are looked
    at (an edge that was there and unmarked stays so; 0.83 s -> a few ms on a 124k-face cut)."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    from . import mesh_io as mio
    seg = np.asarray(seg, np.float64).reshape(-1, 2, 3)
    if not len(seg) or not len(me.edges):
        return 0
    ev = mio.read_edge_verts(me)
    mk = marked(me)
    keys = _pos_keys(co, q)
    ka, kb = _pos_keys(seg[:, 0], q), _pos_keys(seg[:, 1], q)
    pair = _pair_keys(keys[ev[:, 0]], keys[ev[:, 1]])
    same = ~mk & np.isin(pair, _pair_keys(ka, kb))
    out = list(np.flatnonzero(same))
    ok_pt = new_pt | np.isin(keys, np.concatenate([ka, kb]))   # (a new point, or one that was on a marked line)
    cand = ~mk & ~same & ok_pt[ev[:, 0]] & ok_pt[ev[:, 1]]
    if old_co is not None and old_ev is not None and len(old_ev):
        ok = _pos_keys(np.asarray(old_co, np.float64), q)
        cand &= ~np.isin(pair, _pair_keys(ok[old_ev[:, 0]], ok[old_ev[:, 1]]))
    cand = np.flatnonzero(cand)
    if len(cand):
        tol = 2e-6 * size
        pts = co[ev[cand]].reshape(-1, 3)              # (only the marked lines round the edges looked at)
        lo, hi = pts.min(0) - 2 * tol, pts.max(0) + 2 * tol
        near = ((np.minimum(seg[:, 0], seg[:, 1]) <= hi) & (np.maximum(seg[:, 0], seg[:, 1]) >= lo)).all(1)
        seg = seg[near]
        cand = cand if len(seg) else cand[:0]
    if len(cand):
        verts, polys = [], []
        for i, (a, b) in enumerate(seg):              # (thin triangles: "nearest point on a marked line")
            d = b - a
            side = np.cross(d, (0.0, 0.0, 1.0) if abs(d[2]) < 0.9 * np.linalg.norm(d) else (1.0, 0.0, 0.0))
            n = np.linalg.norm(side)
            side = side / n * 1e-7 * size if n > 0 else np.array([0.0, 0.0, 1e-7 * size])
            verts += [Vector(a), Vector(b), Vector(b + side)]
            polys.append((3 * i, 3 * i + 1, 3 * i + 2))
        tree = BVHTree.FromPolygons(verts, polys, all_triangles=True)
        for ei in cand:
            a, b = co[ev[ei, 0]], co[ev[ei, 1]]
            d = b - a
            ln = np.linalg.norm(d)
            if ln < 1e-12:
                continue
            hits = [tree.find_nearest(Vector(p), tol) for p in (a, b, 0.5 * (a + b))]
            if any(h[0] is None for h in hits):
                continue
            for idx in {hits[0][2], hits[1][2]}:
                sd = seg[idx][1] - seg[idx][0]
                ls = np.linalg.norm(sd)
                if ls > 1e-12 and abs(float(np.dot(d, sd))) / (ln * ls) > 0.999:
                    out.append(ei)
                    break
    if out:
        mark_edges(me, np.array(out, np.int64))
    return len(out)


def finish_band(me, snap, width):
    """After an Edge Finish on ``me`` (``snap`` = ``finish_snapshot`` from before it): the old marks the finish
    dropped put back (``_restore_lines``), the band it carved flagged and its borders marked.  Returns the number of
    band faces."""
    import bmesh
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    from . import mesh_io as mio
    old_co, old_me, old_seg, old_ev = snap
    nf = len(me.polygons)
    if nf == 0 or not len(old_co):
        return 0
    co = mio.read_co(me)
    size = float(np.linalg.norm(np.ptp(old_co, axis=0))) or 1.0
    q = size * 1e-6
    new_pt = ~np.isin(_pos_keys(co, q), _pos_keys(old_co, q))
    _restore_lines(me, old_seg, co, new_pt, q, size, old_co, old_ev)
    cv = mio.read_corner_verts(me)
    start, tot = mio.read_face_starts(me)
    cand = np.flatnonzero(np.add.reduceat(new_pt[cv].astype(np.int32), start) > 0)
    if not len(cand):
        return 0
    # the faces' own triangles (the middle of a big C-shaped top face is not on it - it lies over the hole or the
    # groove, and the whole face was taken for band): a face is band only when none of its triangles' centres is on
    # the surface the finish started from
    me.calc_loop_triangles()
    nt = len(me.loop_triangles)
    tv = np.empty(nt * 3, np.int64)
    me.loop_triangles.foreach_get('vertices', tv)
    tp = np.empty(nt, np.int64)
    me.loop_triangles.foreach_get('polygon_index', tp)
    is_cand = np.zeros(nf, bool)
    is_cand[cand] = True
    ti = np.flatnonzero(is_cand[tp])
    tc = co[tv.reshape(-1, 3)[ti]].mean(1)
    bm = bmesh.new()                              # (the surface before, built in C: a Python list of 120k faces
    try:                                          #  took 0.5 s per cut)
        bm.from_mesh(old_me)
        bvh = BVHTree.FromBMesh(bm)
    finally:
        bm.free()
    tol = max(2e-6 * size, 1e-4 * width)
    on = np.zeros(nf, bool)
    for t, c in zip(tp[ti], tc):
        if on[t]:
            continue
        hit = bvh.find_nearest(Vector(c))
        if hit[3] is not None and hit[3] <= tol:
            on[t] = True
    band = is_cand & ~on
    if not band.any():
        return 0
    a = me.attributes.get(FIN_BAND)
    if a is not None and a.domain == 'FACE' and len(a.data) == nf:
        had = np.zeros(nf, bool)
        a.data.foreach_get('value', had)
        band |= had
    elif a is not None:
        me.attributes.remove(a)
        a = None
    if a is None:
        a = me.attributes.new(FIN_BAND, 'BOOLEAN', 'FACE')
    a.data.foreach_set('value', band)
    e_sorted, f_sorted, starts, ends = _edge_faces(me)
    s2 = starts[(ends - starts) == 2]
    fa, fb = f_sorted[s2], f_sorted[s2 + 1]
    border = e_sorted[s2][band[fa] != band[fb]]
    if len(border):
        mark_edges(me, border)
    return int(band.sum())


def carry_marks(old_me, new_me):
    """The marks of ``old_me`` put onto the edges of ``new_me`` (a Boolean result of it, same space) that lie along
    its marked lines and were made by the step (``_restore_lines``).  Returns the number marked."""
    from . import mesh_io as mio
    seg = lines(old_me)
    if not len(seg) or not len(new_me.edges):
        return 0
    old_co = mio.read_co(old_me)
    co = mio.read_co(new_me)
    size = float(np.linalg.norm(np.ptp(old_co, axis=0))) or 1.0
    q = size * 1e-6
    return _restore_lines(new_me, seg, co, ~np.isin(_pos_keys(co, q), _pos_keys(old_co, q)), q, size, old_co,
                          mio.read_edge_verts(old_me))


def keep_marks(me, fn):
    """Run ``fn`` (a step that rebuilds faces of ``me``: the cut's result tidy) and put back the marks it dropped
    (``_restore_lines``).  Returns fn's result."""
    from . import mesh_io as mio
    try:
        seg = lines(me)
        old_co = mio.read_co(me) if len(seg) else None
        old_ev = mio.read_edge_verts(me) if len(seg) else None
    except Exception as ex:                    # (memory is a bonus: never fail a cut over it)
        print('Mecha: edge memory (keep):', ex)
        return fn()
    r = fn()
    if old_co is not None and len(old_co) and len(me.edges):
        try:
            co = mio.read_co(me)
            size = float(np.linalg.norm(np.ptp(old_co, axis=0))) or 1.0
            q = size * 1e-6
            _restore_lines(me, seg, co, ~np.isin(_pos_keys(co, q), _pos_keys(old_co, q)), q, size, old_co, old_ev)
        except Exception as ex:
            print('Mecha: edge memory (keep):', ex)
    return r


def finish_marks(me, fn, width):
    """Run the Edge Finish ``fn`` on ``me`` and remember the band it carved (``finish_band``).  Returns fn's
    result."""
    try:
        snap = finish_snapshot(me)
    except Exception as ex:                    # (memory is a bonus: never fail a cut over it)
        print('Mecha: edge memory (finish):', ex)
        return fn()
    try:
        n = fn()
        if n:
            try:
                finish_band(me, snap, width)
            except Exception as ex:
                print('Mecha: edge memory (finish band):', ex)
        return n
    finally:
        _drop_snapshot(snap)


def lines(me, mask=None):
    """The marked edges as world-free segments (n, 2, 3) in mesh space, for drawing / transfer."""
    from . import mesh_io as mio
    m = marked(me) if mask is None else np.asarray(mask, bool)
    ev = mio.read_edge_verts(me)[m]
    co = mio.read_co(me)
    return co[ev]


def mesh_size(me):
    from . import mesh_io as mio
    co = mio.read_co(me)
    return float(np.linalg.norm(co.max(0) - co.min(0))) if len(co) else 1.0


def transfer(old_me, new_me, tol=TRANSFER_TOL):
    """Marks carried from ``old_me`` to ``new_me`` (a remesh of it): an edge of the new mesh whose both ends lie
    within ``tol`` x size of an old marked segment, and whose direction follows it, is marked.  Returns the number
    of edges marked on the new mesh."""
    return transfer_segments(lines(old_me), mesh_size(old_me), new_me, tol)


def transfer_segments(seg, size, new_me, tol=TRANSFER_TOL):
    """``transfer`` from the old marked lines as segments (n, 2, 3) (``lines``) and the old mesh size: for a tool
    that swaps the mesh out before the new one exists (Fast Decimate)."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    from . import mesh_io as mio
    seg = np.asarray(seg, np.float64).reshape(-1, 2, 3)
    if not len(seg) or not len(new_me.edges):
        return 0
    tol = tol * size
    # the old marked lines as thin triangles so a BVH can answer "nearest point on any marked line"
    verts, polys = [], []
    up = np.array([0.0, 0.0, 1e-5 * size])
    for i, (a, b) in enumerate(seg):
        d = b - a
        side = np.cross(d, up if abs(d[2]) < 0.9 * np.linalg.norm(d) else np.array([1e-5 * size, 0, 0]))
        n = np.linalg.norm(side)
        side = side / n * 1e-6 * size if n > 0 else up
        verts += [Vector(a), Vector(b), Vector(b + side)]
        polys.append((3 * i, 3 * i + 1, 3 * i + 2))
    tree = BVHTree.FromPolygons(verts, polys, all_triangles=True)
    nco = mio.read_co(new_me)
    nev = mio.read_edge_verts(new_me)
    near = np.zeros(len(nco), bool)
    which = -np.ones(len(nco), np.int64)
    for i, p in enumerate(nco):
        loc, _n, idx, dist = tree.find_nearest(Vector(p), tol)
        if loc is not None:
            near[i] = True
            which[i] = idx
    cand = near[nev[:, 0]] & near[nev[:, 1]]
    if not cand.any():
        return 0
    # direction check: the edge must run along its segment, not across the line
    ci = np.flatnonzero(cand)
    ok = np.zeros(len(ci), bool)
    for k, ei in enumerate(ci):
        a, b = nev[ei]
        d = nco[b] - nco[a]
        ln = np.linalg.norm(d)
        if ln < 1e-12:
            continue
        for s in (seg[which[a]], seg[which[b]]):       # (at a corner the two ends sit on different lines)
            sd = s[1] - s[0]
            ls = np.linalg.norm(sd)
            if ls > 1e-12 and abs(float(np.dot(d, sd)) / (ln * ls)) > 0.7:
                ok[k] = True
                break
    idx = ci[ok]
    if not len(idx):
        return 0
    return mark_edges(new_me, idx)


def describe(me):
    n = count(me)
    return f'{n:,} remembered edge{"s" * (n != 1)}' if n else 'no remembered edges'


def remember(me):
    """Before a remesh that works in place (voxel remesh): (segments, size) of the marks, or None."""
    try:
        if not count(me):
            return None
        kept = lines(me), mesh_size(me)
        clear(me)                                    # (nothing for the remesh to smear: restore marks it afresh)
        return kept
    except Exception:
        return None


def restore(me, kept):
    """After it: the marks back onto the new edges (``remember``'s result).  Returns the edges marked."""
    if kept is None:
        return 0
    try:
        seg, size = kept
        return transfer_segments(seg, size, me)
    except Exception as ex:
        print('Mecha: edge memory restore:', ex)
        return 0


GEN_ANGLE = math.radians(30.0)   # a generated part: faces meeting at more than this = a line the tool made


def geometry_mask(me, angle=GEN_ANGLE, specks=True):
    """bool per edge from the geometry alone: boundary / non-manifold edges and the edges whose two faces meet at
    more than ``angle`` (a lone such edge with no hard neighbour at either end dropped when ``specks``)."""
    from . import mesh_io as mio
    ne, nf = len(me.edges), len(me.polygons)
    out = np.zeros(ne, bool)
    if ne == 0 or nf == 0:
        return out
    e_sorted, f_sorted, starts, ends = _edge_faces(me)
    cnt = ends - starts
    out[e_sorted[starts[cnt != 2]]] = True
    s2 = starts[cnt == 2]
    nrm = np.empty(nf * 3, np.float32)
    me.polygons.foreach_get('normal', nrm)
    nrm = nrm.reshape(-1, 3)
    d = np.einsum('ij,ij->i', nrm[f_sorted[s2]], nrm[f_sorted[s2 + 1]])
    ang = e_sorted[s2[d < math.cos(angle) - 1e-4]]      # (strictly more than the angle: a 2-segment bevel's 30-degree rows stay soft)
    if specks and len(ang):
        ev = mio.read_edge_verts(me)
        deg = np.bincount(ev[ang].ravel(), minlength=len(me.vertices))
        lone = (deg[ev[ang, 0]] == 1) & (deg[ev[ang, 1]] == 1)
        ang = ang[~lone]
    out[ang] = True
    return out


def mark_generated(me, angle=GEN_ANGLE):
    """The marks of a part a tool just built or rebuilt (plates, Base Mesh, ridges, screws, molding, patches):
    its rim (boundary) and its own creases - exact here, because the geometry is the tool's clean output.  Replaces
    the old marks (a rebuild makes new geometry).  Returns the number marked."""
    try:
        m = geometry_mask(me, angle)
    except Exception as ex:
        print('Mecha: edge memory (generated):', ex)
        return 0
    if not m.any():
        clear(me)
        return 0
    return mark_edges(me, m, add=False)


# ---- 0.24.95 live parts: the marks on the FINAL shape (user: "아머 플레이트 할 때 나오는 메시들도 엣지 부분에 크리즈
# 남겨 줄래?") ----------------------------------------------------------------------------------------------------
# A plate's own mesh is marked (``mark_generated``), but its Bevel / Solidify modifiers make new edges after that:
# the bevel's border lines and the shell's corner edges came out uncreased, and the creases of a beveled edge were
# copied onto every row INSIDE the round strip.  This node group (last on the stack) marks the result again with
# the same rule as ``mark_generated`` - open edges, faces meeting at more than the angle, the plate's own surface
# lines (``mch_crease``) - as crease 1.0 + the Edge Memory mark, and clears the crease everywhere else.
CREASE_GROUP = 'MCH Edge Crease'
CREASE_MOD = 'MCH_EdgeCrease'
CREASE_VER = 1


def _compare_inputs(node, kind):
    """The A / B sockets of a Compare node for ``kind`` (older Blender lists every type's pair, newer only the
    set type's)."""
    want = {'FLOAT': 'VALUE', 'INT': 'INT'}[kind]
    socks = [i for i in node.inputs if i.type == want and getattr(i, 'enabled', True)]
    if len(socks) < 2:
        socks = [i for i in node.inputs if i.type == want]
    return socks[0], socks[1]


def crease_group():
    import bpy
    ng = bpy.data.node_groups.get(CREASE_GROUP)
    if ng is not None and ng.get('mch_ver') == CREASE_VER:
        return ng
    if ng is None:
        ng = bpy.data.node_groups.new(CREASE_GROUP, 'GeometryNodeTree')
    else:
        ng.nodes.clear()
        ng.interface.clear()
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ang = ng.interface.new_socket('Angle', in_out='INPUT', socket_type='NodeSocketFloat')
    ang.subtype = 'ANGLE'
    ang.default_value = GEN_ANGLE + 1e-4
    ang.min_value = 0.0
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi = N.new('NodeGroupInput')
    go = N.new('NodeGroupOutput')
    angle = N.new('GeometryNodeInputMeshEdgeAngle')
    nb = N.new('GeometryNodeInputMeshEdgeNeighbors')
    steep = N.new('FunctionNodeCompare')
    steep.data_type = 'FLOAT'
    steep.operation = 'GREATER_THAN'
    a, b = _compare_inputs(steep, 'FLOAT')
    L.new(angle.outputs['Unsigned Angle'], a)
    L.new(gi.outputs['Angle'], b)
    open_ = N.new('FunctionNodeCompare')
    open_.data_type = 'INT'
    open_.operation = 'NOT_EQUAL'
    a, b = _compare_inputs(open_, 'INT')
    L.new(nb.outputs['Face Count'], a)
    b.default_value = 2
    lines = N.new('GeometryNodeInputNamedAttribute')
    lines.data_type = 'FLOAT'
    lines.inputs['Name'].default_value = 'mch_crease'
    on_line = N.new('FunctionNodeCompare')
    on_line.data_type = 'FLOAT'
    on_line.operation = 'GREATER_THAN'
    a, b = _compare_inputs(on_line, 'FLOAT')
    L.new(lines.outputs['Attribute'], a)
    b.default_value = 0.5
    or1 = N.new('FunctionNodeBooleanMath')
    or1.operation = 'OR'
    L.new(steep.outputs['Result'], or1.inputs[0])
    L.new(open_.outputs['Result'], or1.inputs[1])
    or2 = N.new('FunctionNodeBooleanMath')
    or2.operation = 'OR'
    L.new(or1.outputs['Boolean'], or2.inputs[0])
    L.new(on_line.outputs['Result'], or2.inputs[1])
    crease = N.new('GeometryNodeStoreNamedAttribute')
    crease.data_type = 'FLOAT'
    crease.domain = 'EDGE'
    crease.inputs['Name'].default_value = 'crease_edge'
    L.new(gi.outputs['Geometry'], crease.inputs['Geometry'])
    L.new(or2.outputs['Boolean'], crease.inputs['Value'])
    mark = N.new('GeometryNodeStoreNamedAttribute')
    mark.data_type = 'BOOLEAN'
    mark.domain = 'EDGE'
    mark.inputs['Name'].default_value = ATTR
    L.new(crease.outputs['Geometry'], mark.inputs['Geometry'])
    L.new(or2.outputs['Boolean'], mark.inputs['Value'])
    L.new(mark.outputs['Geometry'], go.inputs['Geometry'])
    for k, n in enumerate((gi, angle, nb, lines, steep, open_, on_line, or1, or2, crease, mark, go)):
        n.location = (k * 180 - 900, 0)
    ng['mch_ver'] = CREASE_VER
    return ng


def sync_crease_modifier(ob, on):
    """The crease node group last on ``ob``'s modifier stack when ``on`` (a part whose own modifiers make edges),
    removed when not.  Returns the modifier or None."""
    mod = ob.modifiers.get(CREASE_MOD)
    if not on:
        if mod is not None:
            ob.modifiers.remove(mod)
        return None
    try:
        if mod is None:
            mod = ob.modifiers.new(CREASE_MOD, 'NODES')
        if mod.node_group is None or mod.node_group.name != CREASE_GROUP or mod.node_group.get('mch_ver') != CREASE_VER:
            mod.node_group = crease_group()
        mod.show_expanded = False
        last = len(ob.modifiers) - 1
        i = ob.modifiers.find(CREASE_MOD)
        if i != last:
            ob.modifiers.move(i, last)
        return mod
    except Exception as ex:                       # (an unexpected node layout: the base marks stay, the part is still made)
        print('Mecha: edge crease modifier:', ex)
        if ob.modifiers.get(CREASE_MOD) is not None:
            ob.modifiers.remove(ob.modifiers[CREASE_MOD])
        return None
