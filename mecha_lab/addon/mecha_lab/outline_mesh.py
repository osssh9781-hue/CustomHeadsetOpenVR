"""0.24.173 An outline (2D, any units) filled with an even triangle mesh, fast (numpy + Blender's own Delaunay):
the Insect Wing and the Membrane (Creature Cloth) build on it.  The first ``nb`` points are the outline itself (in
loop order), the rest a staggered grid inside, none closer to the outline than about half the spacing."""
from __future__ import annotations

import math

import numpy as np
from mathutils import Vector
from mathutils.geometry import delaunay_2d_cdt


def resample(loop, step):
    """A closed loop with points about ``step`` apart (the drawn corners kept)."""
    P = np.asarray(loop, float)
    out = []
    n = len(P)
    for i in range(n):
        a, b = P[i], P[(i + 1) % n]
        d = float(np.linalg.norm(b - a))
        k = max(1, int(math.ceil(d / max(step, 1e-12))))
        for j in range(k):
            out.append(a + (b - a) * (j / k))
    return np.asarray(out, float)


def inside(Q, loops):
    """Even-odd: which points of ``Q`` (N x 2) are inside the loops."""
    Q = np.asarray(Q, float)
    res = np.zeros(len(Q), bool)
    for lp in loops:
        P = np.asarray(lp, float)
        A, B = P, np.roll(P, -1, axis=0)
        for k in range(0, len(Q), 20000):
            q = Q[k:k + 20000]
            x, y = q[:, 0:1], q[:, 1:2]
            ay, by = A[None, :, 1], B[None, :, 1]
            cross = (ay > y) != (by > y)
            with np.errstate(divide='ignore', invalid='ignore'):
                xi = A[None, :, 0] + (y - ay) * (B[None, :, 0] - A[None, :, 0]) / (by - ay)
            res[k:k + 20000] ^= (np.sum(cross & (x < xi), axis=1) % 2).astype(bool)
    return res


def seg_distance(Q, P, closed=True):
    """The distance of every point of ``Q`` to the polyline ``P``."""
    Q = np.asarray(Q, float)
    A = np.asarray(P, float)
    B = np.roll(A, -1, axis=0) if closed else A[1:]
    A = A if closed else A[:-1]
    out = np.full(len(Q), np.inf)
    AB = B - A
    L2 = np.maximum((AB * AB).sum(1), 1e-18)
    for k in range(0, len(Q), 4000):
        q = Q[k:k + 4000]
        t = np.clip(((q[:, None, :] - A[None]) * AB[None]).sum(2) / L2[None], 0.0, 1.0)
        d = q[:, None, :] - (A[None] + t[:, :, None] * AB[None])
        out[k:k + 4000] = np.sqrt((d * d).sum(2)).min(1)
    return out


def even_mesh(loop, spacing, max_points=60000, ring_as_is=False):
    """(points N x 2, triangles M x 3, nb): ``loop`` (one closed outline) filled evenly ``spacing`` apart.
    ``ring_as_is``: the loop is already spaced (its points kept as they are: the first ``nb``)."""
    P = np.asarray(loop, float)
    area = abs(0.5 * float(np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])))
    while area / (spacing * spacing * 0.866) > max_points:
        spacing *= 1.15
    ring = P if ring_as_is else resample(P, spacing * 0.6)
    nb = len(ring)
    lo, hi = ring.min(0), ring.max(0)
    ys = np.arange(lo[1] + spacing * 0.5, hi[1], spacing * 0.866)
    pts = []
    for r, y in enumerate(ys):
        xs = np.arange(lo[0] + spacing * (0.5 + 0.5 * (r % 2)), hi[0], spacing)
        pts.append(np.c_[xs, np.full(len(xs), y)])
    G = np.concatenate(pts) if pts else np.zeros((0, 2))
    if len(G):
        G = G[inside(G, [ring])]
    if len(G):
        G = G[seg_distance(G, ring) > spacing * 0.45]
    allp = np.concatenate([ring, G]) if len(G) else ring
    edges = [(i, (i + 1) % nb) for i in range(nb)]
    out_v, _e, out_f, out_vo, _eo, _fo = delaunay_2d_cdt([Vector(p) for p in allp], edges, [], 0, 1e-9, True)
    remap = np.full(len(out_v), -1, np.int64)
    for new_i, orig in enumerate(out_vo):
        if orig:
            remap[new_i] = orig[0]
    tris = np.array([f for f in out_f if len(f) == 3], np.int64).reshape(-1, 3)
    tris = remap[tris]
    tris = tris[(tris >= 0).all(1)]
    if len(tris):
        cen = allp[tris].mean(1)
        tris = tris[inside(cen, [ring])]
        a, b, c = allp[tris[:, 0]], allp[tris[:, 1]], allp[tris[:, 2]]
        ar = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
        keep = np.abs(ar) > 1e-14
        tris, ar = tris[keep], ar[keep]
        flip = ar < 0
        tris[flip] = tris[flip][:, [0, 2, 1]]
    return allp, tris, nb


def raster_lines(lo, hi, px, vlist):
    """Lines drawn into a height field over [lo, hi] (``px`` units a pixel): ``vlist`` = [(polyline N x 2, half-width
    per point N, closed)]; each line round in section, the thicker ones higher (0..1).  Returns H x W float32."""
    W = int(math.ceil((hi[0] - lo[0]) / px)) + 1
    H = int(math.ceil((hi[1] - lo[1]) / px)) + 1
    R = np.zeros((H, W), np.float32)
    if not vlist:
        return R
    rmax = max(float(max(np.max(r) for _p, r, _c in vlist)), 1e-12)
    for P, r, closed in vlist:
        P = np.asarray(P, float)
        r = np.asarray(r, float)
        if closed:
            P = np.r_[P, P[:1]]
            r = np.r_[r, r[:1]]
        for i in range(len(P) - 1):
            a, b = P[i], P[i + 1]
            ra = max(float(r[i]), float(r[i + 1]))
            x0 = max(int((min(a[0], b[0]) - ra - lo[0]) / px), 0)
            x1 = min(int((max(a[0], b[0]) + ra - lo[0]) / px) + 2, W)
            y0 = max(int((min(a[1], b[1]) - ra - lo[1]) / px), 0)
            y1 = min(int((max(a[1], b[1]) + ra - lo[1]) / px) + 2, H)
            if x1 <= x0 or y1 <= y0:
                continue
            gx = lo[0] + np.arange(x0, x1) * px
            gy = lo[1] + np.arange(y0, y1) * px
            X, Y = np.meshgrid(gx, gy)
            ab = b - a
            L2 = max(float(ab @ ab), 1e-18)
            t = np.clip(((X - a[0]) * ab[0] + (Y - a[1]) * ab[1]) / L2, 0.0, 1.0)
            rr = r[i] + (r[i + 1] - r[i]) * t
            dx, dy = X - (a[0] + t * ab[0]), Y - (a[1] + t * ab[1])
            q = 1.0 - (dx * dx + dy * dy) / np.maximum(rr * rr, 1e-18)
            prof = np.sqrt(np.clip(q, 0.0, 1.0)) * (rr / rmax)
            R[y0:y1, x0:x1] = np.maximum(R[y0:y1, x0:x1], prof.astype(np.float32))
    return R
