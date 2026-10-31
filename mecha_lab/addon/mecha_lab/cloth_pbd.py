"""0.24.92 A small position-based cloth (numpy), the way Blender's sculpt Cloth brush / Cloth Filter works:

    every step the points move on with their velocity (damped) and the forces of the step (gravity, a filter
    such as Scale or Pinch), then a few Jacobi passes pull the edges back to their rest length (structural),
    the points across each edge to theirs (bending), every point a little toward where it started (the goal:
    Silhouette Keep) and the pinned points all the way back (mask / boundary).

Scaling the cloth down with the edges keeping their length is what crumples it: the fabric that no longer fits
folds.  Pure numpy, no Blender objects: ``Cloth`` takes point coordinates and the faces' corner indices (any
polygon), so it is tested headless and runs in Object Mode on the mesh itself.

Cost: a 25k-point tube with 50k structural + 50k bending constraints, 5 passes - about 15 ms a step.
"""
from __future__ import annotations

import math

import numpy as np


def edges_of(faces_vi, faces_start, faces_tot):
    """Unique (a < b) edges of the faces + for each edge the two 'across' points (one per side, -1 when open):
    the corner before / after the edge in each face, for the bending pairs."""
    n = len(faces_start)
    f_of = np.repeat(np.arange(n), faces_tot)
    nxt = np.arange(len(faces_vi)) + 1
    ends = faces_start + faces_tot - 1
    nxt[ends] = faces_start
    a, b = faces_vi, faces_vi[nxt]
    lo, hi = np.minimum(a, b), np.maximum(a, b)
    key = lo.astype(np.int64) * (int(faces_vi.max()) + 1) + hi
    order = np.argsort(key, kind='stable')
    key_s = key[order]
    first = np.ones(len(key_s), bool)
    first[1:] = key_s[1:] != key_s[:-1]
    uniq_idx = order[first]
    edges = np.stack([lo[uniq_idx], hi[uniq_idx]], 1)
    # the across points: the corner of each face that is neither edge end, picked as the corner after b (nxt of nxt)
    nxt2 = nxt[nxt]
    far = faces_vi[nxt2]
    grp = np.cumsum(first) - 1                   # edge id per sorted corner
    far_s = far[order]
    pairs = -np.ones((len(edges), 2), np.int64)
    pos_in_grp = np.arange(len(key_s)) - np.searchsorted(grp, grp, side='left')
    sel0 = pos_in_grp == 0
    sel1 = pos_in_grp == 1
    pairs[grp[sel0], 0] = far_s[sel0]
    pairs[grp[sel1], 1] = far_s[sel1]
    return edges, pairs, f_of


def ring_pairs(edges, n, rings=(2, 3, 4)):
    """Point pairs at graph distance exactly r for r in ``rings``: a BFS from every point over the edge graph.
    Returns {r: (M, 2) int64 (a < b)}."""
    nb = [[] for _ in range(n)]
    for a, b in np.asarray(edges, np.int64).tolist():
        nb[a].append(b)
        nb[b].append(a)
    R = max(rings)
    out = {r: [] for r in rings}
    for u in range(n):
        seen = {u}
        frontier = [u]
        for r in range(1, R + 1):
            nxt = []
            for v in frontier:
                for w in nb[v]:
                    if w not in seen:
                        seen.add(w)
                        nxt.append(w)
            if r in rings:
                out[r].extend((u, w) for w in nxt if w > u)
            frontier = nxt
    return {r: np.array(v, np.int64).reshape(-1, 2) for r, v in out.items()}


def tethers(co, edges, pinned, scale=1.0):
    """Long-range attachments for ``Cloth.tether``: every free point tied to its nearest pinned point along the
    cloth (multi-source Dijkstra over the edges), the limit = that distance x ``scale``.  Returns (idx, anchor, max)
    or None when nothing is pinned."""
    import heapq
    co = np.asarray(co, np.float64)
    n = len(co)
    pinned = np.nonzero(np.asarray(pinned) >= 1.0)[0]
    if not len(pinned) or not len(edges):
        return None
    w = np.linalg.norm(co[edges[:, 1]] - co[edges[:, 0]], axis=1)
    adj = [[] for _ in range(n)]
    for (a, b), l in zip(edges.tolist(), w.tolist()):
        adj[a].append((b, l))
        adj[b].append((a, l))
    dist = np.full(n, np.inf)
    src = np.full(n, -1, np.int64)
    heap = []
    for p in pinned.tolist():
        dist[p] = 0.0
        src[p] = p
        heap.append((0.0, p))
    heapq.heapify(heap)
    while heap:
        d, v = heapq.heappop(heap)
        if d > dist[v]:
            continue
        for u, l in adj[v]:
            nd = d + l
            if nd < dist[u]:
                dist[u] = nd
                src[u] = src[v]
                heapq.heappush(heap, (nd, u))
    free = np.nonzero((src >= 0) & (dist > 0))[0]
    if not len(free):
        return None
    return free, src[free], dist[free] * float(scale)


class Cloth:
    def __init__(self, co, faces_vi, faces_start, faces_tot, mass=None, bend=0.5, keep=0.0, pin=None):
        self.co = np.array(co, np.float64)
        self.init = self.co.copy()
        self.prev = self.co.copy()
        n = len(self.co)
        edges, pairs, _f = edges_of(np.asarray(faces_vi, np.int64), np.asarray(faces_start, np.int64),
                                    np.asarray(faces_tot, np.int64))
        self.edges = edges
        ok = (pairs[:, 0] >= 0) & (pairs[:, 1] >= 0) & (pairs[:, 0] != pairs[:, 1])
        self.bends = pairs[ok]
        self.rest_e = np.linalg.norm(self.co[edges[:, 1]] - self.co[edges[:, 0]], axis=1)
        self.rest_b = np.linalg.norm(self.co[self.bends[:, 1]] - self.co[self.bends[:, 0]], axis=1)
        self.scale_e = 1.0
        self.scale_b = 1.0
        self.bend = float(bend)
        self.keep = np.full(n, float(keep)) if np.isscalar(keep) else np.asarray(keep, np.float64)
        self.pin = np.zeros(n) if pin is None else np.clip(np.asarray(pin, np.float64), 0.0, 1.0)
        self.mass = np.ones(n) if mass is None else np.asarray(mass, np.float64)
        self.deg_e = np.bincount(edges.ravel(), minlength=n).astype(np.float64)
        self.deg_b = np.bincount(self.bends.ravel(), minlength=n).astype(np.float64)
        self.n = n

    # -- constraints --------------------------------------------------------------------------------------------
    sor = 1.0            # over-relaxation of the Jacobi passes (1.5 - 1.8: the edges hold their length with fewer passes)

    def _project(self, pairs, rest, strength, max_move=None):
        """One Jacobi pass of the length constraints ``pairs`` toward ``rest``: every point gets the mean of the
        corrections its constraints ask for (the mass-weighted split between the two ends).  ``max_move`` caps the
        pull of one pass in length units (a seam a body-width apart must not tunnel through the collider)."""
        if not len(pairs):
            return
        a, b = pairs[:, 0], pairs[:, 1]
        d = self.co[b] - self.co[a]
        length = np.linalg.norm(d, axis=1)
        length[length < 1e-12] = 1e-12
        corr = (length - rest) / length * strength * self.sor
        np.clip(corr, -0.5, 0.5, out=corr)          # (a pass never moves an end more than half the edge: no fling)
        if max_move is not None:
            lim = max_move / length
            np.clip(corr, -lim, lim, out=corr)
        wa = 1.0 / self.mass[a]
        wb = 1.0 / self.mass[b]
        ws = wa + wb
        da = d * (corr * wa / ws)[:, None]
        db = -d * (corr * wb / ws)[:, None]
        acc = np.zeros_like(self.co)
        for k in range(3):
            acc[:, k] = np.bincount(a, weights=da[:, k], minlength=self.n) + np.bincount(b, weights=db[:, k], minlength=self.n)
        deg = np.bincount(a, minlength=self.n) + np.bincount(b, minlength=self.n)
        deg = np.maximum(deg, 1)
        self.co += acc / deg[:, None]

    def set_far(self, rings=(2, 3, 4), strengths=(1.0, 0.8, 0.6)):
        """The wide bending constraints: every pair of points exactly r edges apart (r in ``rings``) keeps its
        rest distance with the given strength.  A BFS from every point over the edge graph (python sets: about
        0.15 s per 10k points)."""
        pairs = ring_pairs(self.edges, self.n, rings)
        self.far = [(pairs[r], np.linalg.norm(self.co[pairs[r][:, 1]] - self.co[pairs[r][:, 0]], axis=1), float(st))
                    for r, st in zip(rings, strengths) if len(pairs[r])]
        return sum(len(f[0]) for f in self.far)

    def jitter(self, amount, seed=1):
        """A little random offset (x ``amount``): a perfectly regular surface needs it to start folding."""
        rng = np.random.default_rng(seed)
        self.co += rng.normal(0.0, amount, self.co.shape) * (1.0 - self.pin)[:, None]     # (pinned points stay)
        self.prev = self.co.copy()

    collide = None       # optional callback(cloth) run after every constraint pass: pushes points out of a collider
    smooth = 0.0         # a Laplacian pull toward the neighbours' mean per pass: the folds come out broad and
    #                      soft instead of a quilt of cell-sized creases (the 2-ring bending alone is too weak)

    def _smooth(self, amount):
        a, b = self.edges[:, 0], self.edges[:, 1]
        acc = np.zeros_like(self.co)
        for k in range(3):
            acc[:, k] = np.bincount(a, weights=self.co[b, k], minlength=self.n) + np.bincount(b, weights=self.co[a, k], minlength=self.n)
        mean = acc / np.maximum(self.deg_e, 1)[:, None]
        self.co += (mean - self.co) * amount

    max_step = 0.0       # a point moves at most this far per frame (0 = no cap): a pole fan's thin triangles
    #                      can otherwise throw a point off in one frame
    floor = None         # (down (3,), level): no point goes further down than ``level`` along ``down`` - the cloth
    #                      cannot hang below the lowest pinned ring (Stop at Pins)
    far = None           # [(pairs, rest, strength), ...] wide bending: points 2, 3, 4 edges apart keep their distance,
    #                      so the cloth cannot crumple cell by cell and buckles into folds a few cells wide instead
    far_scale = 1.0      # x the far strengths (the Wrinkles slider)
    sew = None           # (M, 2) point pairs pulled together (rest length 0): the seams between pattern pieces
    sew_strength = 1.0   # how hard per pass (ramped up over the first frames by the caller)
    sew_pbd = True       # the seams as plain length-0 constraints here; off when the caller pulls them its own way
    tether = None        # 0.24.95 (idx, anchor, max): long-range attachments - a point can be no farther from its
    #                      nearest pinned point than ``max`` (the rest distance along the cloth): a cloth hung from
    #                      one edge (a cape) cannot stretch like rubber however few the constraint passes

    def apply_tether(self):
        if self.tether is not None:
            idx, anc, mx = self.tether
            d = self.co[idx] - self.co[anc]
            ln = np.linalg.norm(d, axis=1)
            over = ln > mx
            if np.any(over):
                i = idx[over]
                self.co[i] = self.co[anc[over]] + d[over] * (mx[over] / ln[over])[:, None]

    tack = None          # 0.24.95 (idx, target, w): tack pins (Marvelous Designer's tack).  Each tacked point is a pin
    #                      whose anchor walks to its body point a small step per pass (w ramps the step 0 -> 1); the
    #                      collider runs after every step and the anchor follows where it put the point, so the pin
    #                      walks ROUND the body (never through a shoulder) and the cloth hangs from it on the way
    tack_anchor = None

    def apply_tack(self):
        if self.tack is None:
            return
        idx, tgt, w = self.tack
        if self.tack_anchor is None:
            self.tack_anchor = self.co[idx].copy()
            self.pin[idx] = 1.0
        a = self.tack_anchor
        if w > 0.0:
            mv = tgt - a
            ln = np.linalg.norm(mv, axis=1)
            cap = self.max_step * 0.3 if self.max_step > 0 else float('inf')
            near = ln <= cap * 0.5
            a[near] = tgt[near]
            far = ~near
            if np.any(far):
                a[far] += mv[far] * (np.minimum(ln[far], cap) * min(1.0, w) / ln[far])[:, None]
        self.init[idx] = a
        self.co[idx] = a

    def tack_follow(self):
        """(after the collider) the anchors follow where the collider put the tacked points: outside the body"""
        if self.tack is not None and self.tack_anchor is not None:
            idx = self.tack[0]
            self.tack_anchor = self.co[idx].copy()
            self.init[idx] = self.tack_anchor

    hold = None          # 0.24.95 (idx, weight, target): the grabbed points are held at ``target`` by ``weight``
    #                      every pass (the user drags the cloth out of the body while it drapes)

    def apply_hold(self):
        if self.hold is not None:
            idx, w, tgt = self.hold
            self.co[idx] = self.co[idx] * (1.0 - w)[:, None] + tgt * w[:, None]

    def step(self, force=None, gravity=None, damping=0.1, iterations=5, keep_rate=0.3):
        """One frame: velocity + forces, then the constraint passes.  ``force`` (N, 3) a per-point push for this
        step (a filter), ``gravity`` (3,) per step.  Pinned points are put back by their pin weight."""
        before = self.co.copy()
        vel = (self.co - self.prev) * (1.0 - damping)
        if self.max_step > 0:
            ln = np.linalg.norm(vel, axis=1)
            over = ln > self.max_step
            if np.any(over):
                vel[over] *= (self.max_step / ln[over])[:, None]
        self.prev = self.co.copy()
        self.co = self.co + vel
        if gravity is not None:
            self.co += np.asarray(gravity, np.float64)[None, :]
        if force is not None:
            self.co += force
        for _ in range(iterations):
            self._project(self.edges, self.rest_e * self.scale_e, 1.0)
            if self.bend > 0 and len(self.bends):
                self._project(self.bends, self.rest_b * self.scale_b, self.bend)
            if self.far and self.far_scale > 0:
                sc = float(np.mean(self.scale_e)) if np.ndim(self.scale_e) else float(self.scale_e)
                for pairs, rest, strength in self.far:
                    self._project(pairs, rest * sc, strength * self.far_scale)
            if self.sew is not None and len(self.sew) and self.sew_strength > 0 and self.sew_pbd:
                self._project(self.sew, np.zeros(len(self.sew)), self.sew_strength,
                              max_move=self.max_step * 0.5 if self.max_step > 0 else None)
            if self.smooth > 0:
                self._smooth(self.smooth)
            if np.any(self.keep > 0):
                self.co += (self.init - self.co) * (self.keep * keep_rate / iterations)[:, None]
            if np.any(self.pin > 0):        # (a pin holds its point where it started: Blender's mask)
                self.co = self.co * (1.0 - self.pin)[:, None] + self.init * self.pin[:, None]
            self.apply_hold()
            self.apply_tack()
            self.apply_tether()
            if self.collide is not None:
                self.collide(self)
                self.tack_follow()
        if self.max_step > 0:
            d = self.co - before
            ln = np.linalg.norm(d, axis=1)
            over = ln > self.max_step * 2.0
            if np.any(over):
                self.co[over] = before[over] + d[over] * (self.max_step * 2.0 / ln[over])[:, None]
        if self.floor is not None:
            self.clamp_floor()
        self.apply_hold()                   # (the grabbed points follow the hand whatever the frame cap)
        return self.co

    def clamp_floor(self):
        down, level = self.floor
        down = np.asarray(down, np.float64)
        depth = self.co @ down
        over = depth > level
        if np.any(over):
            self.co[over] -= down[None, :] * (depth[over] - level)[:, None]

    # -- filters ------------------------------------------------------------------------------------------------
    def scale_force(self, amount, centre=None, mask=None):
        """The Scale filter: every point toward the centre by ``amount`` of its offset (negative = out)."""
        c = self.co.mean(0) if centre is None else np.asarray(centre, np.float64)
        f = (c - self.co) * amount
        if mask is not None:
            f *= mask[:, None]
        return f

    def toward_force(self, target, amount, mask=None):
        """A push toward per-point targets (N, 3) by ``amount`` of the way (the lines' pinch)."""
        f = (np.asarray(target, np.float64) - self.co) * amount
        if mask is not None:
            f *= mask[:, None]
        return f


# -----------------------------------------------------------------------------
# 0.24.92 a light collider: a signed-distance grid round a point cloud with normals
# -----------------------------------------------------------------------------


class GridCollider:
    """The collider surface baked once into a narrow-band signed-distance grid: every cell within ``band`` cells
    of a collider point holds the distance to the tangent plane of its nearest collider point; after that a
    query is a trilinear look-up (numpy, no per-point Python), whatever the size of the collider or the cloth.
    Cells outside the band count as far outside (no push).

    Built without a per-cell search: every point splats its plane into the cells round it (``np.minimum.at`` keeps
    the nearest point per cell), so a 40k-point proxy bakes in well under a second.

    ``points`` (M, 3) + ``normals`` (M, 3): the collider surface (a decimated proxy is fine - the planes bridge
    the coarse faces).  ``cell``: the grid spacing (about the proxy's edge length).  ``band``: cells each way."""

    FAR = 1e9

    def __init__(self, points, normals, cell, band=3):
        P = np.asarray(points, np.float64)
        N = np.asarray(normals, np.float64)
        self.cell = float(cell)
        self.band = int(band)
        lo = P.min(0) - (band + 1) * cell
        hi = P.max(0) + (band + 1) * cell
        dims = np.maximum(np.ceil((hi - lo) / cell).astype(int) + 1, 2)
        self.origin = lo
        self.dims = dims
        self.strides = np.array([dims[1] * dims[2], dims[2], 1], np.int64)
        total = int(dims[0] * dims[1] * dims[2])
        ijk = np.floor((P - lo) / cell).astype(np.int64)
        r = np.arange(-band, band + 1)
        off = np.stack(np.meshgrid(r, r, r, indexing='ij'), -1).reshape(-1, 3)
        best = np.full(total, np.inf)
        sdf = np.full(total, self.FAR, np.float32)
        grad = np.zeros((total, 3), np.float32)
        step = max(1, 2_000_000 // len(off))                  # points per chunk (memory: chunk x offsets)
        for s0 in range(0, len(P), step):
            pi = np.arange(s0, min(s0 + step, len(P)))
            cells = (ijk[pi, None, :] + off[None, :, :]).reshape(-1, 3)
            src = np.repeat(pi, len(off))
            ok = np.all((cells >= 0) & (cells < dims), axis=1)
            cells, src = cells[ok], src[ok]
            flat = (cells * self.strides).sum(1)
            centre = lo + (cells + 0.5) * cell
            d2 = ((centre - P[src]) ** 2).sum(1)
            np.minimum.at(best, flat, d2)
            win = d2 <= best[flat]
            fw, sw = flat[win], src[win]
            sdf[fw] = ((centre[win] - P[sw]) * N[sw]).sum(1)
            grad[fw] = N[sw]
        self.sdf = sdf
        self.grad = grad
        self.cells = int(np.count_nonzero(np.isfinite(best)))

    def _corners(self, co):
        f = (np.asarray(co, np.float64) - self.origin) / self.cell - 0.5
        i0 = np.floor(f).astype(np.int64)
        t = (f - i0).astype(np.float32)
        inside = np.all((i0 >= 0) & (i0 + 1 < self.dims), axis=1)
        base = (np.clip(i0, 0, self.dims - 2) * self.strides).sum(1)
        ws, idxs = [], []
        tx, ty, tz = t[:, 0], t[:, 1], t[:, 2]
        for dx in (0, 1):
            wx = tx if dx else 1.0 - tx
            for dy in (0, 1):
                wy = wx * (ty if dy else 1.0 - ty)
                for dz in (0, 1):
                    ws.append(wy * (tz if dz else 1.0 - tz))
                    idxs.append(base + (dx * self.strides[0] + dy * self.strides[1] + dz))
        return inside, ws, idxs

    def inward(self, co):
        """(distance, unit direction toward the surface) of each point - the pull of a wrap.  Points outside
        the band get no direction (zeros)."""
        inside, ws, idxs = self._corners(co)
        d = np.zeros(len(co), np.float32)
        g = np.zeros((len(co), 3), np.float32)
        for w, idx in zip(ws, idxs):
            d += w * self.sdf[idx]
            g += w[:, None] * self.grad[idx]
        d[~inside] = self.FAR
        ln = np.linalg.norm(g, axis=1)
        ok = (ln > 1e-9) & inside & (d < self.FAR)
        out = np.zeros((len(co), 3))
        out[ok] = -g[ok] / ln[ok][:, None]
        return d, out

    def distance(self, co):
        """The signed distance of each point (FAR outside the band / the grid): a trilinear look-up."""
        inside, ws, idxs = self._corners(co)
        d = np.zeros(len(co), np.float32)
        for w, idx in zip(ws, idxs):
            d += w * self.sdf[idx]
        d[~inside] = self.FAR
        return d

    def push(self, co, margin, touch_at=1.5):
        """Points closer than ``margin`` are moved out along the gradient to ``margin`` (in place; the gradient is
        looked up only for them).  Returns the mask of points touching (closer than ``touch_at`` x margin)."""
        inside, ws, idxs = self._corners(co)
        d = np.zeros(len(co), np.float32)
        for w, idx in zip(ws, idxs):
            d += w * self.sdf[idx]
        d[~inside] = self.FAR
        hit = np.nonzero(d < margin)[0]
        if len(hit):
            g = np.zeros((len(hit), 3), np.float32)
            for w, idx in zip(ws, idxs):
                g += w[hit, None] * self.grad[idx[hit]]
            g = g.astype(np.float64)
            ln = np.linalg.norm(g, axis=1)
            ln[ln < 1e-9] = 1.0
            co[hit] += g / ln[:, None] * (margin - d[hit])[:, None]
        return d < margin * touch_at


# 0.24.95 the collider as a point cloud that covers the FACES too (a flat face with points only at its corners was a
# hole in the grid: the cloth fell through the user's recessed floor)
SMOOTH_COS = math.cos(math.radians(35.0))   # surface_samples: a corner normal this close to the face blends in
PHONG = 0.75                  # surface_samples: how far the samples move onto the curved (Phong) patch, 0 = flat facets
MAX_SAMPLES = 600_000           # surface_samples: at most this many extra points on the body's faces


def fan_triangles(vi, start, tot):
    """Triangles (n, 3) from polygon corner arrays (each polygon fanned from its first corner)."""
    vi, start, tot = np.asarray(vi, np.int64), np.asarray(start, np.int64), np.asarray(tot, np.int64)
    out = []
    for k in range(1, int(tot.max()) - 1 if len(tot) else 0):
        sel = tot > k + 1
        out.append(np.stack([vi[start[sel]], vi[start[sel] + k], vi[start[sel] + k + 1]], 1))
    return np.concatenate(out) if out else np.zeros((0, 3), np.int64)


def surface_samples(me, co, nrm, near, spacing, lo=None, hi=None, limit=MAX_SAMPLES, tris=None):
    """The body as a point cloud for the collider: its points (``co``, ``nrm`` - possibly lifted by the tubes) plus
    points spread over every face bigger than ``spacing`` (barycentric grids on the loop triangles, the triangle's
    normal), so a flat face is solid between its corners.  ``near`` picks the body points that count; a triangle
    with any near corner is sampled.  Returns (points, normals)."""
    co = np.asarray(co, np.float64)
    nrm = np.asarray(nrm, np.float64)
    pts = [co[near]]
    nms = [nrm[near]]
    if tris is None:                                     # from the mesh ...
        me.calc_loop_triangles()
        nt = len(me.loop_triangles)
        if nt == 0 or spacing <= 0:
            return np.concatenate(pts), np.concatenate(nms)
        T = np.empty(nt * 3, np.int32)
        me.loop_triangles.foreach_get('vertices', T)
        T = T.reshape(-1, 3).astype(np.int64)
    else:                                                # ... or given (a proxy's polygons, fanned)
        T = np.asarray(tris, np.int64).reshape(-1, 3)
        if len(T) == 0 or spacing <= 0:
            return np.concatenate(pts), np.concatenate(nms)
    keep = near[T].any(1)
    if lo is not None and hi is not None:                # a big face whose corners are all far away still counts
        tlo = np.minimum.reduce([co[T[:, 0]], co[T[:, 1]], co[T[:, 2]]])   # when it crosses the cloth's region
        thi = np.maximum.reduce([co[T[:, 0]], co[T[:, 1]], co[T[:, 2]]])
        keep |= np.all((thi >= lo) & (tlo <= hi), axis=1)
    T = T[keep]
    if not len(T):
        return np.concatenate(pts), np.concatenate(nms)
    A, B, Cc = co[T[:, 0]], co[T[:, 1]], co[T[:, 2]]
    fn = np.cross(B - A, Cc - A)
    ln = np.linalg.norm(fn, axis=1)
    ok = ln > 1e-18
    fn[ok] /= ln[ok][:, None]
    # the sample's normal: the corners' point normals blended (a coarse CURVED body then reads as a smooth surface,
    # not as its facets - the cloth showed the facet rings), except at a corner whose point normal is far off the
    # face (a box edge / corner: there the face normal stays, so the flat stays flat up to its edge)
    cn = []
    for k in range(3):
        vn = nrm[T[:, k]]
        agree = np.einsum('ij,ij->i', vn, fn) > SMOOTH_COS
        cn.append(np.where(agree[:, None], vn, fn))
    longest = np.maximum.reduce([np.linalg.norm(B - A, axis=1), np.linalg.norm(Cc - B, axis=1), np.linalg.norm(A - Cc, axis=1)])
    n_div = np.ceil(longest / spacing).astype(np.int64)
    total = int(np.maximum(n_div - 1, 0).astype(np.int64).__mul__(np.maximum(n_div - 2, 0)).sum() // 2)
    if total > limit:                                    # too many: a coarser grid on EVERY face (never a face left out)
        spacing *= math.sqrt(total / limit)
        n_div = np.ceil(longest / spacing).astype(np.int64)
    big = np.flatnonzero((n_div >= 3) & ok)              # (a triangle under 3 steps across has no inside point)
    for n in np.unique(n_div[big]):
        tris = big[n_div[big] == n]
        i, j = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing='ij')
        m = (i + j <= n) & (i > 0) & (j > 0) & (i + j < n)    # strictly inside (the edges / corners are the points)
        u = (i[m] / n).astype(np.float64)
        v = (j[m] / n).astype(np.float64)
        if not len(u):
            continue
        w0, w1, w2 = (1 - u - v)[None, :, None], u[None, :, None], v[None, :, None]
        P = (A[tris][:, None, :] * w0 + B[tris][:, None, :] * w1 + Cc[tris][:, None, :] * w2).reshape(-1, 3)
        # Phong tessellation: the sample moved onto the curved patch the corner normals describe (its projections
        # onto the three corners' tangent planes, blended) - a coarse curved body reads as the smooth surface it
        # stands for, not as its facets; at a hard corner the "normal" is the face's own, so a flat stays flat
        if PHONG > 0:
            curved = np.zeros_like(P)
            for k, (V, Nk) in enumerate(((A, cn[0]), (B, cn[1]), (Cc, cn[2]))):
                Vt = np.repeat(V[tris], len(u), axis=0)
                Nt = np.repeat(Nk[tris], len(u), axis=0)
                wk = (w0, w1, w2)[k].reshape(1, -1, 1)
                proj = P - np.einsum('ij,ij->i', P - Vt, Nt)[:, None] * Nt
                curved += (np.repeat(wk, len(tris), axis=0).reshape(-1, 1)) * proj
            P = (1.0 - PHONG) * P + PHONG * curved
        Nn = (cn[0][tris][:, None, :] * w0 + cn[1][tris][:, None, :] * w1 + cn[2][tris][:, None, :] * w2).reshape(-1, 3)
        nl = np.linalg.norm(Nn, axis=1)
        bad = nl < 1e-9
        Nn[~bad] /= nl[~bad][:, None]
        if bad.any():
            Nn[bad] = np.repeat(fn[tris], len(u), axis=0)[bad]
        pts.append(P)
        nms.append(Nn)
    return np.concatenate(pts), np.concatenate(nms)

