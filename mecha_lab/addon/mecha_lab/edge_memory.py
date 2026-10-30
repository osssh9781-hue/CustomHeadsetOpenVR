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


def mark_cut_borders(me, cutter_attr='mch_cutter_face', inner_angle=INNER_ANGLE):
    """The cutter flag (faces) turned into edge marks: cutter / original borders + the cutter's own creases.
    Returns the number of edges marked now (0 when there is no flag, or nothing was cut)."""
    attr = me.attributes.get(cutter_attr)
    nf = len(me.polygons)
    if attr is None or attr.domain != 'FACE' or nf == 0 or len(me.edges) == 0:
        return 0
    cut = np.zeros(nf, bool)
    attr.data.foreach_get('value', cut)
    if not cut.any() or cut.all():
        return 0
    e_sorted, f_sorted, starts, ends = _edge_faces(me)
    two = (ends - starts) == 2
    s2 = starts[two]
    ea = e_sorted[s2]
    fa, fb = f_sorted[s2], f_sorted[s2 + 1]
    ca, cb = cut[fa], cut[fb]
    border = ca != cb
    both = ca & cb
    hard = border.copy()
    if both.any():
        nrm = np.empty(nf * 3, np.float32)
        me.polygons.foreach_get('normal', nrm)
        nrm = nrm.reshape(-1, 3)
        d = np.einsum('ij,ij->i', nrm[fa[both]], nrm[fb[both]])
        hard[np.flatnonzero(both)[d < math.cos(inner_angle)]] = True
    idx = ea[hard]
    if not len(idx):
        return 0
    mark_edges(me, idx)
    return int(len(idx))


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
    ang = e_sorted[s2[d < math.cos(angle)]]
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
