"""0.24.95 Isotropic remesh of an open triangle patch (Botsch & Kobbelt): every edge brought close to one target
length, so a cloth made from it has even triangles (Drape Mask: the masked faces, decimated, then evened out).

One pass = split the edges longer than 4/3 L, collapse the ones shorter than 4/5 L (never making an edge longer
than 4/3 L, never pulling the rim inward), flip edges toward valence 6 (4 on the rim), then a tangential
relaxation with every inside point put back on the reference surface.  The rim points stay where they are
(new rim points are the midpoints of rim edges).
"""
from __future__ import annotations

import math

import bmesh
import numpy as np
from mathutils import Vector

HI = 4.0 / 3.0
LO = 4.0 / 5.0
RELAX = 0.5


def target_length(area, points):
    """The edge length that gives about ``points`` points on ``area`` with equilateral triangles."""
    return math.sqrt(2.0 * max(area, 1e-12) / (math.sqrt(3.0) * max(points, 3)))


def _split_long(bm, hi):
    for _ in range(4):
        long = [e for e in bm.edges if e.calc_length() > hi]
        if not long:
            return
        bmesh.ops.subdivide_edges(bm, edges=long, cuts=1, use_grid_fill=False)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3], quad_method='BEAUTY',
                              ngon_method='BEAUTY')


def _neighbours(v):
    return {e.other_vert(v) for e in v.link_edges}


def _collapse_short(bm, lo, hi):
    """Collapse the short edges, an independent set per pass (no two collapses share a neighbourhood), all welded
    in one bmesh call (one op per edge was the slow part: 5 s a pass on 4k points)."""
    short = sorted((e for e in bm.edges if e.calc_length() < lo), key=lambda e: e.calc_length())
    touched = set()
    weld = {}
    for e in short:
        a, b = e.verts
        if a in touched or b in touched:
            continue
        ba, bb = a.is_boundary, b.is_boundary
        if ba and bb and not e.is_boundary:
            continue                                    # an inside edge between two rim points: would pinch the patch
        na, nb = _neighbours(a), _neighbours(b)
        if len(na & nb) != (1 if e.is_boundary else 2):
            continue                                    # the link condition: the collapse would break the surface
        if ba and not bb:
            keep, gone, co = a, b, a.co.copy()
        elif bb and not ba:
            keep, gone, co = b, a, b.co.copy()
        else:
            keep, gone, co = a, b, (a.co + b.co) * 0.5
        ring = (na | nb) - {a, b}
        if any((n.co - co).length > hi for n in ring):
            continue                                    # (no new long edge)
        ok = True                                       # (no face turns over)
        for v in (a, b):
            for f in v.link_faces:
                if a in f.verts and b in f.verts:
                    continue
                pts = [co if w is v else w.co for w in f.verts]
                if (pts[1] - pts[0]).cross(pts[2] - pts[0]).dot(f.normal) <= 0.0:
                    ok = False
                    break
            if not ok:
                break
        if not ok:
            continue
        touched.update(ring | {a, b})
        keep.co = co
        weld[gone] = keep
    if weld:
        bmesh.ops.weld_verts(bm, targetmap=weld)
    return len(weld)


def _valence_target(v):
    return 4 if v.is_boundary else 6


def _flip(bm):
    for e in list(bm.edges):
        if not e.is_valid or e.is_boundary or len(e.link_faces) != 2:
            continue
        a, b = e.verts
        f1, f2 = e.link_faces
        if len(f1.verts) != 3 or len(f2.verts) != 3:
            continue
        c = next(v for v in f1.verts if v not in (a, b))
        d = next(v for v in f2.verts if v not in (a, b))
        if c == d or d in _neighbours(c):
            continue
        val = {v: len(v.link_edges) for v in (a, b, c, d)}
        before = sum(abs(val[v] - _valence_target(v)) for v in (a, b, c, d))
        after = (abs(val[a] - 1 - _valence_target(a)) + abs(val[b] - 1 - _valence_target(b)) +
                 abs(val[c] + 1 - _valence_target(c)) + abs(val[d] + 1 - _valence_target(d)))
        if after >= before:
            continue
        n = f1.normal + f2.normal                        # (the new triangles must face the same way)
        t1 = (a.co - c.co).cross(d.co - c.co)
        t2 = (d.co - c.co).cross(b.co - c.co)
        if t1.dot(n) * t2.dot(n) <= 0.0 or min(val[a], val[b]) <= 3:
            continue
        bmesh.utils.edge_rotate(e, True)


def _relax(bm, project):
    bm.normal_update()
    moves = []
    for v in bm.verts:
        if v.is_boundary or not v.link_edges:
            continue
        nb = _neighbours(v)
        q = sum((w.co for w in nb), Vector()) / len(nb)
        d = q - v.co
        n = v.normal
        moves.append((v, v.co + (d - n * d.dot(n)) * RELAX))
    for v, p in moves:
        v.co = project(p) if project is not None else p


def remesh(bm, length, project=None, iters=5):
    """Even out the triangle patch ``bm`` (in place) to edges of about ``length``.  ``project(Vector) -> Vector``
    puts a point back on the reference surface (None: no projection)."""
    hi, lo = length * HI, length * LO
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    for _ in range(iters):
        _split_long(bm, hi)
        for _k in range(4):
            bm.normal_update()
            if not _collapse_short(bm, lo, hi):
                break
        bmesh.ops.dissolve_degenerate(bm, dist=length * 1e-4, edges=bm.edges[:])
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        _flip(bm)
        _relax(bm, project)
    return bm


def edge_stats(bm):
    """(median, max, max / median) of the edge lengths."""
    el = np.array([e.calc_length() for e in bm.edges])
    if not len(el):
        return 0.0, 0.0, 0.0
    med = float(np.median(el))
    return med, float(el.max()), float(el.max() / max(med, 1e-12))
