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

    def _project(self, pairs, rest, strength):
        """One Jacobi pass of the length constraints ``pairs`` toward ``rest``: every point gets the mean of the
        corrections its constraints ask for (the mass-weighted split between the two ends)."""
        if not len(pairs):
            return
        a, b = pairs[:, 0], pairs[:, 1]
        d = self.co[b] - self.co[a]
        length = np.linalg.norm(d, axis=1)
        length[length < 1e-12] = 1e-12
        corr = (length - rest) / length * strength * self.sor
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

    def jitter(self, amount, seed=1):
        """A little random offset (x ``amount``): a perfectly regular surface needs it to start folding."""
        rng = np.random.default_rng(seed)
        self.co += rng.normal(0.0, amount, self.co.shape)
        self.prev = self.co.copy()

    smooth = 0.0         # a Laplacian pull toward the neighbours' mean per pass: the folds come out broad and
    #                      soft instead of a quilt of cell-sized creases (the 2-ring bending alone is too weak)

    def _smooth(self, amount):
        a, b = self.edges[:, 0], self.edges[:, 1]
        acc = np.zeros_like(self.co)
        for k in range(3):
            acc[:, k] = np.bincount(a, weights=self.co[b, k], minlength=self.n) + np.bincount(b, weights=self.co[a, k], minlength=self.n)
        mean = acc / np.maximum(self.deg_e, 1)[:, None]
        self.co += (mean - self.co) * amount

    def step(self, force=None, gravity=None, damping=0.1, iterations=5, keep_rate=0.3):
        """One frame: velocity + forces, then the constraint passes.  ``force`` (N, 3) a per-point push for this
        step (a filter), ``gravity`` (3,) per step.  Pinned points are put back by their pin weight."""
        before = self.co.copy()
        vel = (self.co - self.prev) * (1.0 - damping)
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
            if self.smooth > 0:
                self._smooth(self.smooth)
            if np.any(self.keep > 0):
                self.co += (self.init - self.co) * (self.keep * keep_rate / iterations)[:, None]
            if np.any(self.pin > 0):
                self.co = self.co * (1.0 - self.pin)[:, None] + before * self.pin[:, None]
        return self.co

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
