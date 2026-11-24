"""0.24.321 Detail Boost for Quad Remesh (user: "쿼드 플로우에 세밀한 면은 좀더 면을 분배 가능하게 옵션을 추가하는 버튼").

The remesher lays quads of one size everywhere; a small groove or a thin chamfer needs more of them, the big flat sides
do not.  After the remesh, the quads where the result misses the original surface (the original's points farther off
the quad than a share of the quad size - ``Detail Boost`` sets the share) and the quads over a marked Detail Area
(``mch_detail`` on the original's points, from Mark Detail Area) are split 3 x 3, their neighbours get transition
quads (3-refinement templates: a quad becomes quads only, no triangles added), and every new point is put on the original
surface, then evened out a little (and put on it again).  So the detail comes back where it was lost, the rest keeps
its count.  Triangles touched (Mostly Quads leaves a few) get 6 quads + 1 triangle; faces with more sides only get their
sides split.

Templates (corners a b c d of a quad; a marked point gets its edges split in thirds next to it):
  1 marked corner        -> 3 quads           2 marked side by side -> 5 quads       2 opposite -> 5 quads
  3 / 4 marked           -> all 4 marked: 9 quads (only a 3-marked quad spreads a mark)
  triangle: 1 marked -> 2 quads + 1 triangle, 2 -> 4 quads + 1 triangle, 3 -> 6 quads + 1 triangle
"""
from __future__ import annotations

import math

import numpy as np

import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ATTR = 'mch_detail'             # a point attribute on the original: 1 = this area gets the finer quads
SAMPLE_MAX = 200000             # original points looked at for the miss (spread evenly over them)
RELAX = 3                       # smoothing passes on the new inside points (each put back on the surface)


def miss_tolerance(strength, h):
    """How far (object space) the original may be off a quad before the quad is split: Detail Boost 1 -> 3 % of the
    quad size, 0.5 -> 17 %, 0.1 -> 28 %."""
    s = max(0.0, min(1.0, float(strength)))
    return h * (0.03 + 0.28 * (1.0 - s))


def face_miss(bm, V, h, tol):
    """The faces of ``bm`` the original points ``V`` (n, 3) are farther off than ``tol``: a set of face indices."""
    bm.faces.ensure_lookup_table()
    tree = BVHTree.FromBMesh(bm)
    n = len(V)
    step = max(1, n // SAMPLE_MAX)
    out = set()
    for p in V[::step]:
        hit = tree.find_nearest(Vector(p))
        if hit[0] is not None and hit[3] > tol:
            out.add(hit[2])
    return out


def _spread(bm, marked):
    """Marks spread until every face fits a template: only a quad with 3 marked corners gets the 4th (every other
    case has its own template - 0.24.321 a triangle spreading its marks filled a whole Mostly Quads sphere)."""
    changed = True
    while changed:
        changed = False
        for f in bm.faces:
            vs = f.verts
            if len(vs) != 4:
                continue
            k = sum(v.index in marked for v in vs)
            if k == 3:
                for v in vs:
                    marked.add(v.index)
                changed = True


def refine(me, V, T, h, strength=0.0, use_area=True):
    """Split the quads of ``me`` (in place) where they miss the original (points ``V``, triangles ``T``) or lie on
    a marked Detail Area.  Returns (faces before, faces after, quads that were split)."""
    V = np.asarray(V, np.float32).reshape(-1, 3)
    T = np.asarray(T, np.int32).reshape(-1, 3)
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        before = len(bm.faces)
        hit_faces = set()
        if strength > 0.0:
            hit_faces |= face_miss(bm, V, h, miss_tolerance(strength, h))
        if use_area:
            lay = bm.verts.layers.float.get(ATTR)
            if lay is not None:
                hit_faces |= {f.index for f in bm.faces if any(v[lay] > 0.5 for v in f.verts)}
        if not hit_faces:
            return before, before, 0
        marked = set()
        for i in hit_faces:
            for v in bm.faces[i].verts:
                marked.add(v.index)
        _spread(bm, marked)
        verts = list(bm.verts)
        faces = [(f, [v.index for v in f.verts]) for f in bm.faces if any(v.index in marked for v in f.verts)]
        # the edges split: thirds next to each marked end (both ends: two points)
        ekeys = {}
        for e in list(bm.edges):
            a, b = e.verts
            ma, mb = a.index in marked, b.index in marked
            if not (ma or mb):
                continue
            ia, ib = a.index, b.index
            if ma and mb:
                _ne, p1 = bmesh.utils.edge_split(e, a, 1.0 / 3.0)
                e2 = next(x for x in p1.link_edges if x.other_vert(p1) is b)
                _ne, p2 = bmesh.utils.edge_split(e2, p1, 0.5)
                pts = [p1, p2]
            else:
                near = a if ma else b
                _ne, p = bmesh.utils.edge_split(e, near, 1.0 / 3.0)
                pts = [p]
            ekeys[(ia, ib)] = pts
            ekeys[(ib, ia)] = list(reversed(pts))
        new_pts = [p for k, v in ekeys.items() if k[0] < k[1] for p in v]
        inner = []

        def side(i, j):
            return ekeys.get((i, j), [])

        def lerp4(c, u, v):
            return (c[0] * (1 - u) * (1 - v) + c[1] * u * (1 - v) + c[2] * u * v + c[3] * (1 - u) * v)

        def nv(co):
            x = bm.verts.new(co)
            inner.append(x)
            return x
        made = 0
        kill = []
        for f, ids in faces:
            n = len(ids)
            m = [i in marked for i in ids]
            cs = [verts[i] for i in ids]
            new_faces = []
            if n == 4:
                k = sum(m)
                if k == 0:
                    continue
                r = 0
                opposite = k == 2 and m[0] == m[2]
                if k == 1 or opposite:
                    r = m.index(True)
                elif k == 2:
                    r = next(j for j in range(4) if m[j] and m[(j + 1) % 4])
                c = [cs[(r + j) % 4] for j in range(4)]
                ci = [ids[(r + j) % 4] for j in range(4)]
                P = [x.co.copy() for x in c]
                if k == 4:
                    s0, s1, s2, s3 = side(ci[0], ci[1]), side(ci[1], ci[2]), side(ci[2], ci[3]), side(ci[3], ci[0])
                    G = [[None] * 4 for _ in range(4)]                 # G[row v][col u]
                    G[0] = [c[0], s0[0], s0[1], c[1]]
                    G[3] = [c[3], s2[1], s2[0], c[2]]
                    G[1][0], G[2][0] = s3[1], s3[0]
                    G[1][3], G[2][3] = s1[0], s1[1]
                    for vv in (1, 2):
                        for uu in (1, 2):
                            G[vv][uu] = nv(lerp4(P, uu / 3.0, vv / 3.0))
                    for vv in range(3):
                        for uu in range(3):
                            new_faces.append([G[vv][uu], G[vv][uu + 1], G[vv + 1][uu + 1], G[vv + 1][uu]])
                elif opposite:                                         # c0 and c2: two corners + 3
                    pab, pda = side(ci[0], ci[1])[0], side(ci[0], ci[3])[0]
                    pcd, pbc = side(ci[2], ci[3])[0], side(ci[2], ci[1])[0]
                    qa = nv(lerp4(P, 1 / 3.0, 1 / 3.0))
                    qc = nv(lerp4(P, 2 / 3.0, 2 / 3.0))
                    new_faces += [[c[0], pab, qa, pda], [c[2], pcd, qc, pbc], [pab, c[1], pbc, qc],
                                  [pcd, c[3], pda, qa], [pab, qc, pcd, qa]]
                elif k == 1:
                    p = side(ci[0], ci[1])[0]
                    s = side(ci[0], ci[3])[0]
                    q = nv(lerp4(P, 1 / 3.0, 1 / 3.0))
                    new_faces += [[c[0], p, q, s], [p, c[1], c[2], q], [q, c[2], c[3], s]]
                else:                                                  # two side by side: c0, c1
                    p1, p2 = side(ci[0], ci[1])
                    t = side(ci[1], ci[2])[0]
                    s = side(ci[0], ci[3])[0]
                    q1 = nv(lerp4(P, 1 / 3.0, 0.45))
                    q2 = nv(lerp4(P, 2 / 3.0, 0.3))
                    new_faces += [[c[0], p1, q1, s], [p1, p2, q2, q1], [p2, c[1], t, q2], [q1, q2, t, c[2]],
                                  [s, q1, c[2], c[3]]]
            elif n == 3 and all(m):
                cen = (cs[0].co + cs[1].co + cs[2].co) / 3.0
                M = [nv(cen + (x.co - cen) / 3.0) for x in cs]
                for j in range(3):
                    a, b = ids[j], ids[(j + 1) % 3]
                    e1, e2 = side(a, b)
                    prev = side(ids[(j - 1) % 3], a)[1]
                    new_faces.append([cs[j], e1, M[j], prev])
                    new_faces.append([e1, e2, M[(j + 1) % 3], M[j]])
                new_faces.append([M[0], M[1], M[2]])
            elif n == 3:
                # 0.24.321 a triangle with one or two marked corners: quads + one triangle, its marks kept to itself
                k = sum(m)
                r = m.index(True) if k == 1 else next(j for j in range(3) if m[j] and m[(j + 1) % 3])
                c = [cs[(r + j) % 3] for j in range(3)]
                ci = [ids[(r + j) % 3] for j in range(3)]
                P = [x.co.copy() for x in c]
                if k == 1:
                    p, s_ = side(ci[0], ci[1])[0], side(ci[0], ci[2])[0]
                    q = nv((P[0] * 4 + P[1] + P[2]) / 6.0)
                    new_faces += [[c[0], p, q, s_], [p, c[1], c[2], q], [q, c[2], s_]]
                else:                                                  # c0, c1 marked
                    p1, p2 = side(ci[0], ci[1])
                    t, s_ = side(ci[1], ci[2])[0], side(ci[0], ci[2])[0]
                    q1 = nv((P[0] * 3 + P[1] + P[2]) / 5.0)
                    q2 = nv((P[1] * 3 + P[0] + P[2]) / 5.0)
                    new_faces += [[c[0], p1, q1, s_], [p1, p2, q2, q1], [p2, c[1], t, q2], [q1, q2, t, c[2]],
                                  [s_, q1, c[2]]]
            else:
                continue                                               # (more sides: only its sides split)
            for vs in new_faces:
                try:
                    bm.faces.new(vs, f)
                except ValueError:
                    pass
            kill.append(f)
            made += 1
        if kill:
            bmesh.ops.delete(bm, geom=kill, context='FACES_ONLY')
        # the new points onto the original, the inside ones evened out
        tree = BVHTree.FromPolygons([tuple(p) for p in V.tolist()], T.tolist(), all_triangles=True)
        moving = new_pts + inner

        def snap(vs):
            for x in vs:
                hit = tree.find_nearest(x.co)
                if hit[0] is not None:
                    x.co = hit[0]
        snap(moving)
        for _ in range(RELAX):
            cos = []
            for x in inner:
                nb = [e.other_vert(x).co for e in x.link_edges]
                cos.append(sum(nb, Vector()) / len(nb) if nb else x.co.copy())
            for x, co in zip(inner, cos):
                x.co = co
            snap(inner)
        bm.normal_update()
        after = len(bm.faces)
        bm.to_mesh(me)
        me.update()
        return before, after, made
    finally:
        bm.free()


def mark_area(me, selected_only=True, value=1.0):
    """Mark Detail Area: the selected points (Edit Mode selection) of ``me`` get ``mch_detail`` = ``value``.  Returns
    how many."""
    a = me.attributes.get(ATTR)
    if a is None:
        a = me.attributes.new(ATTR, 'FLOAT', 'POINT')
    vals = np.zeros(len(me.vertices), np.float32)
    a.data.foreach_get('value', vals)
    sel = np.zeros(len(me.vertices), bool)
    me.vertices.foreach_get('select', sel)
    vals[sel] = value
    a.data.foreach_set('value', vals)
    me.update()
    return int(sel.sum())


def area_count(me):
    a = me.attributes.get(ATTR)
    if a is None or a.domain != 'POINT':
        return 0
    vals = np.zeros(len(me.vertices), np.float32)
    a.data.foreach_get('value', vals)
    return int((vals > 0.5).sum())
