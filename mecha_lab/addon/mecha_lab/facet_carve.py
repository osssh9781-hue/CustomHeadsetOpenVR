"""0.24.76 Facet carve: a Cut Ramp / Base Mesh carve (Alt: Height / Ramp) over a bent, faceted surface is cut with
one plane per flat facet under the outline - the floor parallel to each facet, a sharp crease where two facets
meet - instead of a dense grid laid on the surface with smoothed normals (that left a dirty floor at the bend and
thousands of faces).

* One convex or one concave patch (any number of facets, corners of 3+ included), or a strip of facets with mixed
  folds that run right across the outline.
* Facets steeper than 60 degrees to the view get no floor of their own (their neighbours' floors run over them).
* Steep Edges (``settings.steep``): EVEN = every facet the full depth across it (near a steep side the groove runs
  further down it); LIMIT = the same depth along the view everywhere, as on the facet seen most straight (a facet
  turned away from the view gets less - a shallower groove down a steep side, as before).
* Ramp Soft: the floor still follows each facet exactly, with rows of points across the ramp (the eased slope) and
  a few points near the walls (the rounded sides) instead of a full grid.
* Anything else (a curved / dense surface, more than MAX_FACETS facets, Chamfer / Bevel edge profile, Through, a
  Boolean that fails with this cutter) -> the old carve (``carve`` returns False).
``LAST`` = what the last carve did (for the report / tests)."""
import math
import time

import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import delaunay_2d_cdt

MAX_FACETS = 48
PLANE_DEG = 0.5            # faces within this angle (and on the same plane) are one facet
EDGE_ON = 0.12             # |view . normal| below this: a face seen edge-on (a silhouette, nothing of its own)
GRAZE = 0.5                # below this (steeper than 60 deg to the view) a facet still counts for the surface but
                           # gets no floor plane of its own - its neighbours' floors run over it (a near-vertical
                           # facet's floor met the side walls at a grazing angle: the Boolean broke)
BAND = (0.25, 0.5, 0.75, 1.0)   # Ramp Soft: points at these parts of the rounded side band
STEEP_ITEMS = [
    ('EVEN', 'Even', 'Across a bent edge every face gets the full depth, measured across that face (near a steep '
                     'side the groove runs further down it)'),
    ('LIMIT', 'Limit', 'The same depth along your view everywhere (as on the face you look at most straight): faces '
                       'turned away get less - a shallower groove down a steep side, like the old carve')]
LAST = {}                  # path ('facet' / 'old'), reason, facets, faces, seconds
ENABLED = True             # (tests: False = always the old carve)


class Fallback(Exception):
    pass


# --- 2D helpers -------------------------------------------------------------------------------------------------

def _inside(poly, q):
    x, y = q
    c = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-300) + xi:
            c = not c
        j = i
    return c


def _in_shape(outer, holes, q):
    return _inside(outer, q) and not any(_inside(h, q) for h in holes)


def _frac_inside(a, b, outer, holes, n=24):
    k = 0
    for i in range(n):
        t = (i + 0.5) / n
        if _in_shape(outer, holes, (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)):
            k += 1
    return k / n


def _seg_d(p, a, b):
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    ll = dx * dx + dy * dy
    t = 0.0 if ll < 1e-18 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / ll))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


def _edge_dist(loops, p):
    return min(_seg_d(p, lp[i - 1], lp[i]) for lp in loops for i in range(len(lp)))


def _line_cross(loops, p, u):
    """Parameters s where the line p + s u crosses the loops, sorted."""
    out = []
    for lp in loops:
        for i in range(len(lp)):
            a, b = lp[i - 1], lp[i]
            ex, ey = b[0] - a[0], b[1] - a[1]
            den = u[0] * ey - u[1] * ex
            if abs(den) < 1e-12:
                continue
            wx, wy = a[0] - p[0], a[1] - p[1]
            s = (wx * ey - wy * ex) / den
            r = (wx * u[1] - wy * u[0]) / den
            if 0.0 <= r < 1.0:
                out.append(s)
    return sorted(out)


# --- projection -------------------------------------------------------------------------------------------------

def _ray(projector, x):
    o, d = projector.ray(tuple(x))
    return Vector(o), Vector(d).normalized()


def _t_plane(projector, x, pco, pno):
    o, d = _ray(projector, x)
    den = d.dot(pno)
    if abs(den) < 1e-12:
        raise Fallback('ray parallel to a facet')
    return (pco - o).dot(pno) / den


def _plane_line_point(c1, n1, c2, n2):
    u = n1.cross(n2)
    d1, d2 = n1.dot(c1), n2.dot(c2)
    return (u.cross(n1) * d2 + n2.cross(u) * d1) / u.length_squared


def _root(g, ext):
    """A zero of g(tau) near 0 (|tau| < ext / 2): bracket it stepping out both ways (steps doubling from
    ext / 256), then Illinois regula falsi."""
    g0 = g(0.0)
    if g0 == 0.0:
        return 0.0
    br = None
    prev = {1.0: (0.0, g0), -1.0: (0.0, g0)}
    st = ext / 256.0
    while st <= ext * 0.5 + 1e-12:
        for sgn in (1.0, -1.0):
            t = sgn * st
            gt = g(t)
            if (gt > 0) != (g0 > 0):
                br = (prev[sgn][0], t, prev[sgn][1], gt)
                break
            prev[sgn] = (t, gt)
        if br:
            break
        st *= 2.0
    if br is None:
        return None
    a, b, ga, gb = br
    side = 0
    for _it in range(80):
        c = (a * gb - b * ga) / (gb - ga)
        gc = g(c)
        if abs(b - a) < 1e-7 * ext or gc == 0.0:
            return c
        if (gc > 0) == (gb > 0):
            b, gb = c, gc
            if side == -1:
                ga *= 0.5
            side = -1
        else:
            a, ga = c, gc
            if side == 1:
                gb *= 0.5
            side = 1
    return 0.5 * (a + b)


def _smooth01(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


class _Near:
    """The view with each ray starting next to the part (mathutils vectors are single precision: from an origin
    1000 units away the depths along the rays were only good to ~1e-4)."""

    def __init__(self, proj, ref, radius):
        self.base, self.ref, self.radius = proj, Vector(ref), radius
        self.is_perspective = getattr(proj, 'is_perspective', False)

    def ray(self, xy):
        o, d = self.base.ray(tuple(xy))
        o, d = Vector(o), Vector(d).normalized()
        if not self.is_perspective:
            o = o + d * ((self.ref - o).dot(d) - self.radius)        # just in front of the part
        return o, d

    def to_screen(self, co):
        return self.base.to_screen(co)


class Facet:
    def __init__(self, idx, faces, co, no):
        self.idx, self.faces, self.co, self.no = idx, faces, co, no
        self.floor = None              # (point, normal) of the carved floor plane (straight depth only)


def _facets(bm, seeds, size, owner, start, limit):
    """Flood each seed face over neighbours on the same plane -> facets (``owner`` face -> facet index)."""
    cosmax = math.cos(math.radians(PLANE_DEG))
    tol = size * 1e-5
    out = []
    for f0 in seeds:
        if f0.index in owner:
            continue
        no = f0.normal.normalized()
        co = f0.calc_center_median()
        fac = Facet(start + len(out), [], co, no)
        stack = [f0]
        owner[f0.index] = fac.idx
        while stack:
            f = stack.pop()
            fac.faces.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index in owner:
                        continue
                    if g.normal.dot(no) >= cosmax and abs((g.calc_center_median() - co).dot(no)) <= tol:
                        owner[g.index] = fac.idx
                        stack.append(g)
        out.append(fac)
        if start + len(out) > limit:
            raise Fallback(f'more than {limit} facets under the outline (a curved surface)')
    return out


class Plan:
    """The strip of facets under one outline and how deep the floor is at each screen point."""

    def __init__(self, target, outer, holes, projector, height, ramp, lift, res=20, steep='EVEN'):
        mw = target.matrix_world
        box = [mw @ Vector(c) for c in target.bound_box]
        mid = sum(box, Vector()) / 8.0
        self.proj = _Near(projector, mid, max((q - mid).length for q in box) * 1.5 + 1e-3)
        self.outer = [tuple(q) for q in outer]
        self.holes = [[tuple(q) for q in h] for h in holes]
        self.loops = [self.outer] + self.holes
        self.height, self.lift = height, lift
        self.ramp = ramp
        self.soft = ramp[3] if ramp is not None and len(ramp) > 3 else 0.0
        self.res = res
        a = np.array([q for lp in self.loops for q in lp[-1:] + lp[:-1]], float)   # each outline side a -> b
        b = np.array([q for lp in self.loops for q in lp], float)
        self._sa, self._sd = a, b - a
        self._sl = np.maximum((self._sd * self._sd).sum(1), 1e-18)
        self._memo = {}                  # screen point -> every facet's floor depth along its ray (``_tv``)
        bm = bmesh.new()
        bm.from_mesh(target.data)
        bm.transform(target.matrix_world)
        bm.normal_update()
        bm.faces.ensure_lookup_table()
        try:
            self._find(bm)
        finally:
            bm.free()
        vd = _ray(self.proj, ((self.bbox[0] + self.bbox[1]) * 0.5, (self.bbox[2] + self.bbox[3]) * 0.5))[1]
        for f in self.facets:
            f.steep = abs(f.no.dot(vd)) < GRAZE
        self.flat = [f for f in self.facets if not f.steep]    # the facets with a floor of their own
        if not self.flat:
            raise Fallback('only steep facets under the outline')
        self._depth_share(vd, steep)
        if self.mode == 'seq' and len(self.flat) != len(self.facets):
            raise Fallback('a steep facet among mixed folds')
        self._depth_setup()
        if self.soft <= 0.0:             # floor planes: point . normal, normal
            self._pn = np.array([f.floor[0].dot(f.floor[1]) for f in self.facets])
            self._no = np.array([tuple(f.floor[1]) for f in self.facets])
        else:                            # the facet planes, moved down by depth x m
            self._pn = np.array([f.co.dot(f.no) for f in self.facets])
            self._no = np.array([tuple(f.no) for f in self.facets])
            self._m = np.array([f.m for f in self.facets])

    def _depth_share(self, vd, steep):
        """f.m = the part of the depth taken across each facet: 1 (EVEN), or (LIMIT) the same depth along the view
        everywhere - as deep along the view as on the facet seen most straight (that one keeps 1, a facet turned
        away from the view gets |n . view| / that one's: a shallower groove down a steep side)."""
        top = max([abs(f.no.dot(vd)) for f in self.flat] or [1.0])
        for f in self.facets:
            f.m = 1.0 if steep != 'LIMIT' else min(1.0, abs(f.no.dot(vd)) / max(top, 1e-6))

    # -- facets ----------------------------------------------------------------------------------------------
    def _find(self, bm):
        proj, outer, holes = self.proj, self.outer, self.holes
        lo = Vector([min(v.co[k] for v in bm.verts) for k in range(3)])
        hi = Vector([max(v.co[k] for v in bm.verts) for k in range(3)])
        self.size = size = (hi - lo).length
        bvh = BVHTree.FromBMesh(bm)
        xs = [q[0] for q in outer]
        ys = [q[1] for q in outer]
        self.bbox = (min(xs), max(xs), min(ys), max(ys))
        ext = max(max(xs) - min(xs), max(ys) - min(ys))
        step = ext / 48.0
        samples = []
        for lp in self.loops:
            for i in range(len(lp)):
                a, b = lp[i - 1], lp[i]
                n = max(1, int(math.dist(a, b) / step))
                samples += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n)]
        y = min(ys) + step * 0.5
        while y < max(ys):
            x = min(xs) + step * 0.5
            while x < max(xs):
                if _in_shape(outer, holes, (x, y)):
                    samples.append((x, y))
                x += step
            y += step
        seeds, seen, ratios, hits = [], set(), [], []
        prev = None
        for x in samples:
            o, d = _ray(proj, x)
            loc, _nrm, fi, _dist = bvh.ray_cast(o, d)
            if loc is None:
                prev = None
                continue
            if prev is not None and math.dist(prev[0], x) > 1e-9:
                ratios.append((loc - prev[1]).length / math.dist(prev[0], x))
            prev = (x, loc)
            f = bm.faces[fi]
            if f.normal.dot(d) > EDGE_ON:
                raise Fallback('a back face under the outline (open / inside out mesh)')
            if f.normal.dot(d) > -EDGE_ON:
                continue                      # seen edge-on: the neighbours' floors run over it (no plane of its own)
            # a second, short cast from just in front of the hit (a view ray starts far away: the first hit is
            # only float-precise to ~1e-4)
            near = bvh.ray_cast(loc - d * (size * 0.02), d, size * 0.04)
            if near[0] is not None:
                loc = near[0]
            hits.append((x, (loc - o).dot(d)))
            if fi not in seen:
                seen.add(fi)
                seeds.append(f)
        if not seeds:
            raise Fallback('nothing under the outline')
        ratios.sort()
        self.k = ratios[len(ratios) // 2] if ratios else 1.0          # scene units per pixel (about)
        owner = {}
        facets = _facets(bm, seeds, size, owner, 0, MAX_FACETS)
        # folds: mesh edges between two facets whose picture crosses the outline (a face never hit = a narrow
        # facet the samples missed: added)
        while True:
            folds, added = {}, False
            for fac in list(facets):
                for f in fac.faces:
                    for e in f.edges:
                        if len(e.link_faces) != 2:
                            continue
                        g = e.link_faces[0] if e.link_faces[1] is f else e.link_faces[1]
                        if owner.get(g.index) == fac.idx:
                            continue
                        a = proj.to_screen(e.verts[0].co)
                        b = proj.to_screen(e.verts[1].co)
                        if a is None or b is None or _frac_inside(a, b, outer, holes) <= 0.0:
                            continue
                        if g.index not in owner:
                            _o, d = _ray(proj, a)
                            if g.normal.dot(d) > -EDGE_ON:
                                continue                  # a silhouette (nothing else may be seen past it)
                            facets += _facets(bm, [g], size, owner, len(facets), MAX_FACETS)
                            added = True
                            break
                        j = owner[g.index]
                        key = (min(fac.idx, j), max(fac.idx, j))
                        folds.setdefault(key, []).append((a, b, e))
                    if added:
                        break
                if added:
                    break
            if not added:
                break
        # convex / concave
        conv = {}
        for (i, j), segs in folds.items():
            e = segs[0][2]
            s = (e.verts[0].co + e.verts[1].co) * 0.5
            q = next(g.calc_center_median() for g in e.link_faces if owner.get(g.index) == j)
            conv[(i, j)] = (q - s).dot(facets[i].no) < 0.0
        cv = list(conv.values())
        mode = 'max' if all(cv) else ('min' if not any(cv) else 'seq')
        self.folds = folds
        if mode == 'seq':
            order = self._strip(facets, folds, bvh)
        else:
            # all folds bend the same way: the surface is the deepest (convex) / shallowest (concave) of the facet
            # planes, corners of 3+ facets included - checked on every sample that hit the part
            order = [f.idx for f in facets]
            pick = max if mode == 'max' else min
            for x, t in hits:
                te = pick(_t_plane(proj, x, f.co, f.no) for f in facets)
                if abs(te - t) > size * 1e-4:
                    self.debug = (x, te, t, [(f.idx, tuple(f.no), _t_plane(proj, x, f.co, f.no)) for f in facets])
                    raise Fallback('the surface under the outline is not one convex / concave patch')
        self.facets, self.order, self.conv = facets, order, conv
        # all folds convex: the floor is the deepest facet floor everywhere (exact for a convex patch, also where
        # a narrow facet's floor is swallowed by its neighbours); all concave: the shallowest; mixed: in a row
        self.mode = mode

    def _strip(self, facets, folds, bvh):
        """Mixed folds: the facets must lie in a row (each touching at most two others) and every fold must run
        right across the outline.  Returns the order."""
        nb = {f.idx: set() for f in facets}
        for i, j in folds:
            nb[i].add(j)
            nb[j].add(i)
        ends = [k for k, s in nb.items() if len(s) <= 1]
        if any(len(s) > 2 for s in nb.values()) or not ends:
            raise Fallback('mixed folds meet inside the outline (a corner of 3+ facets)')
        order = [ends[0]]
        while True:
            nxt = [k for k in nb[order[-1]] if k not in order]
            if not nxt:
                break
            order.append(nxt[0])
        if len(order) != len(facets):
            raise Fallback('the facets under the outline are not joined')
        for (i, j), segs in folds.items():
            fi, fj = facets[i], facets[j]
            u = fi.no.cross(fj.no)
            if u.length < 1e-9:
                raise Fallback('two facets on parallel planes')
            A, B = self._line_screen(_plane_line_point(fi.co, fi.no, fj.co, fj.no), u)
            chord = self._seen_chord(bvh, A, B)
            covered = sum(math.dist(a, b) * _frac_inside(a, b, self.outer, self.holes) for a, b, _e in segs)
            if chord <= 1e-9 or covered < 0.97 * chord:
                raise Fallback('a fold ends inside the outline')
        return order

    def _line_screen(self, p0, u):
        """A 3D line as a long screen segment through the outline's box (picked near the middle of the view: a
        perspective view has no picture of points behind the eye)."""
        x0, x1, y0, y1 = self.bbox
        ext = max(x1 - x0, y1 - y0)
        mid = Vector(((x0 + x1) * 0.5, (y0 + y1) * 0.5))
        u = u.normalized()
        o, d = _ray(self.proj, tuple(mid))
        w0 = p0 - o
        b, dd, e = u.dot(d), u.dot(w0), d.dot(w0)
        den = 1.0 - b * b
        q = p0 + u * ((b * e - dd) / den if den > 1e-12 else 0.0)
        r = self.size * 0.05
        A = self.proj.to_screen(q - u * r)
        B = self.proj.to_screen(q + u * r)
        if A is None or B is None or math.dist(A, B) < 1e-9:
            raise Fallback('a fold runs along the view')
        A, B = Vector(A), Vector(B)
        dv = (B - A).normalized()
        c = A + dv * (mid - A).dot(dv)
        return tuple(c - dv * 2.0 * ext), tuple(c + dv * 2.0 * ext)

    def _seen_chord(self, bvh, A, B, n=300):
        """Screen length of line A-B inside the outline where the part is under it (past a silhouette nothing
        is carved, so a fold may end there)."""
        x0, x1, y0, y1 = self.bbox
        ab = (B[0] - A[0], B[1] - A[1])
        L = math.hypot(*ab)
        u = (ab[0] / L, ab[1] / L)
        ts = [(q[0] - A[0]) * u[0] + (q[1] - A[1]) * u[1] for q in ((x0, y0), (x1, y0), (x0, y1), (x1, y1))]
        ta, tb = min(ts), max(ts)
        k = 0
        for i in range(n):
            t = ta + (tb - ta) * (i + 0.5) / n
            q = (A[0] + u[0] * t, A[1] + u[1] * t)
            if _in_shape(self.outer, self.holes, q):
                o, d = _ray(self.proj, q)
                if bvh.ray_cast(o, d)[0] is not None:
                    k += 1
        return (tb - ta) * k / n

    # -- depth ------------------------------------------------------------------------------------------------
    def _depth_setup(self):
        H, L = self.height, self.lift
        self.rg = None
        if self.ramp is not None:
            a, b, length = self.ramp[:3]
            ax, ay = a
            dx, dy = b[0] - ax, b[1] - ay
            ln = math.hypot(dx, dy)
            if ln > 1e-9:
                nx, ny = -dy / ln, dx / ln
                cx = sum(q[0] for q in self.outer) / len(self.outer)
                cy = sum(q[1] for q in self.outer) / len(self.outer)
                if (cx - ax) * nx + (cy - ay) * ny < 0:
                    nx, ny = -nx, -ny
                far = max((q[0] - ax) * nx + (q[1] - ay) * ny for q in self.outer)
                reach = max(far * max(0.05, min(1.0, length)), 1e-9)
                self.rg = (ax, ay, nx, ny, reach)
        if self.soft > 1e-6 and self.rg is not None:
            x0, x1, y0, y1 = self.bbox
            best = 0.0
            n = 40
            for i in range(n):
                for j in range(n):
                    q = (x0 + (x1 - x0) * (i + 0.5) / n, y0 + (y1 - y0) * (j + 0.5) / n)
                    if _in_shape(self.outer, self.holes, q):
                        best = max(best, self.edist(q))
            self.deepest_px = best
            self.reach2_px = max(best * 0.6 * self.soft, 1e-9)
        else:
            self.soft = 0.0
            # straight depth: each facet's floor is a plane (exact, also in a perspective view)
            x0, x1, y0, y1 = self.bbox
            tri = [(x0, y0), (x1, y0), (x0, y1)]
            for f in self.facets:
                pts = []
                for x in tri:
                    o, d = _ray(self.proj, x)
                    c = o + d * _t_plane(self.proj, x, f.co, f.no)
                    pts.append(c - f.no * (self.depth(x) * f.m))
                nrm = (pts[1] - pts[0]).cross(pts[2] - pts[0])
                if nrm.length < 1e-15:
                    raise Fallback('flat floor plane')
                nrm.normalize()
                f.floor = (pts[0], nrm if nrm.dot(f.no) > 0 else -nrm)

    def edist(self, x):
        """Screen distance from x to the outline (and holes)."""
        w = np.array((x[0], x[1])) - self._sa
        t = np.clip((w * self._sd).sum(1) / self._sl, 0.0, 1.0)
        r = w - self._sd * t[:, None]
        return float(math.sqrt((r * r).sum(1).min()))

    def f_lin(self, x):
        ax, ay, nx, ny, reach = self.rg
        return 1.0 - ((x[0] - ax) * nx + (x[1] - ay) * ny) / reach

    def depth(self, x):
        H, L = self.height, self.lift
        if self.rg is None:
            return H
        f = self.f_lin(x)
        if self.soft <= 0.0:
            return (H + L) * f - L                     # unclamped: past the reach it only rises off the surface
        f = max(0.0, min(1.0, f))
        s = self.soft
        eased = (1.0 - s) * f + s * _smooth01(f)
        side = _smooth01(self.edist(x) / self.reach2_px)
        return (H + L) * eased * (1.0 + (side - 1.0) * s * (1.0 - f)) - L

    def _tv(self, x):
        """Along the view ray at screen x: how far to the floor of every facet (array by facet index; inf where
        the ray runs along it)."""
        key = (float(x[0]), float(x[1]))
        t = self._memo.get(key)
        if t is None:
            o, d = _ray(self.proj, key)
            den = self._no @ np.array(d)
            num = self._pn - self._no @ np.array(o)
            if self.soft > 0.0:
                num = num - self.depth(key) * self._m
            with np.errstate(divide='ignore', invalid='ignore'):
                t = np.where(np.abs(den) < 1e-12, np.inf, num / np.where(den == 0.0, 1.0, den))
            self._memo[key] = t
        return t

    def tf(self, f, x):
        """Along the view ray: how far to the floor of facet ``f`` at screen x."""
        t = float(self._tv(x)[f.idx])
        if not math.isfinite(t):
            raise Fallback('ray parallel to a facet')
        return t

    def side(self, k, x):
        """> 0: x is on the order[k + 1] side of crease k (convex fold: the deeper floor wins, concave: the
        shallower)."""
        i, j = self.order[k], self.order[k + 1]
        c = self.conv[(i, j)] if (i, j) in self.conv else self.conv[(j, i)]
        dt = self.tf(self.facets[j], x) - self.tf(self.facets[i], x)
        return dt if c else -dt

    def label(self, x):
        if self.mode != 'seq':
            tv = self._tv(x)
            ts = [(float(tv[f.idx]), f.idx) for f in self.flat]
            return (max(ts) if self.mode == 'max' else min(ts))[1]
        lab = None
        n = len(self.order)
        for k in range(n):
            if (k == 0 or self.side(k - 1, x) > 0) and (k == n - 1 or self.side(k, x) < 0):
                if lab is not None:
                    return None
                lab = self.order[k]
        return lab

    def t_ideal(self, x):
        lab = self.label(x)
        return None if lab is None else (self.tf(self.facets[lab], x), self.facets[lab])

    # -- creases ----------------------------------------------------------------------------------------------
    def pairs(self):
        """Facet pairs whose floors meet inside the outline: the neighbours in the strip, and (max / min) any
        two that meet where a facet between them is swallowed."""
        if self.mode == 'seq':
            return [(self.order[k], self.order[k + 1]) for k in range(len(self.order) - 1)]
        out = {k for k in self.folds if not (self.facets[k[0]].steep or self.facets[k[1]].steep)}
        if len(self.flat) < 3 and len(self.flat) == len(self.facets):
            return sorted(out)
        x0, x1, y0, y1 = self.bbox
        n = 48
        grid = {}
        for i in range(n + 1):
            for j in range(n + 1):
                q = (x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * j / n)
                if _in_shape(self.outer, self.holes, q):
                    grid[(i, j)] = self.label(q)
        self._adj = {}                   # pair -> screen points where its two labels touch on the grid
        for (i, j), a in grid.items():
            for di, dj in ((1, 0), (0, 1), (1, 1), (1, -1)):
                b = grid.get((i + di, j + dj))
                if b is not None and b != a:
                    out.add((min(a, b), max(a, b)))
                    self._adj.setdefault((min(a, b), max(a, b)), []).append(
                        (x0 + (x1 - x0) * (i + di * 0.5) / n, y0 + (y1 - y0) * (j + dj * 0.5) / n))
        seen, res = set(), []
        for a, b in out:
            k = (min(a, b), max(a, b))
            if k not in seen:
                seen.add(k)
                res.append((a, b))
        return res

    def creases(self, pairs=None):
        """Screen polylines where two facets' floors meet - only where those two ARE the floor (with many facets,
        full lines for every pair crossed each other everywhere: tens of thousands of slivers)."""
        x0, x1, y0, y1 = self.bbox
        ext = max(x1 - x0, y1 - y0)
        mid = Vector(((x0 + x1) * 0.5, (y0 + y1) * 0.5))
        corners = [Vector((x0, y0)), Vector((x1, y0)), Vector((x0, y1)), Vector((x1, y1))]
        tol = self.height * 1e-3
        out = []
        for i, j in (self.pairs() if pairs is None else pairs):
            fi, fj = self.facets[i], self.facets[j]
            if self.soft <= 0.0:
                Pi, Ni = fi.floor
                Pj, Nj = fj.floor
            else:            # a first guess: the floors as planes at the depth in the middle of the outline
                dm = self.depth(tuple(mid))
                Pi, Ni, Pj, Nj = fi.co - fi.no * (dm * fi.m), fi.no, fj.co - fj.no * (dm * fj.m), fj.no
            u = Ni.cross(Nj)
            if u.length < 1e-12:
                raise Fallback('parallel floors')
            A, B = self._line_screen(_plane_line_point(Pi, Ni, Pj, Nj), u)
            A, B = Vector(A), Vector(B)
            dv = (B - A).normalized()
            w = Vector((-dv.y, dv.x))
            c = A + dv * (mid - A).dot(dv)
            # only across the outline's box (and a little past it: the CDT keeps the part inside)
            sa = min((q - c).dot(dv) for q in corners) - 0.1 * ext
            sb = max((q - c).dot(dv) for q in corners) + 0.1 * ext
            step = max(self.reach2_px / 4.0, ext / 40.0) if self.soft > 0.0 else ext / 48.0
            n = max(2, int(math.ceil((sb - sa) / step)))
            near = None
            adj = getattr(self, '_adj', {}).get((min(i, j), max(i, j)))
            if self.soft > 0.0 and self.mode != 'seq' and adj:
                # (solved only near where the two touch on the label grid: elsewhere a third floor is deeper /
                # shallower and the point is thrown away below - with 40 facets that was most of the time)
                near = [(Vector(q) - c).dot(dv) for q in adj]
                win = 3.0 * ext / 48.0 + 1.5 * (sb - sa) / n
            pts = []
            for m in range(n + 1):
                s0 = c + dv * (sa + (sb - sa) * m / n)
                if self.soft <= 0.0:
                    pts.append(tuple(s0))
                    continue
                if near is not None and min(abs(sa + (sb - sa) * m / n - q) for q in near) > win:
                    pts.append(None)
                    continue
                # Ramp Soft: the depth bends, so does the crease - solved point by point across the first guess
                g = lambda tau: self.tf(fj, tuple(s0 + w * tau)) - self.tf(fi, tuple(s0 + w * tau))
                tau = _root(g, ext)
                pts.append(None if tau is None else tuple(s0 + w * tau))
            # keep the runs where these two floors are the floor (+ one step past each end, to reach the corners
            # where a third one takes over)
            if self.mode == 'seq':
                keep = [q is not None for q in pts]
            else:
                others = [f for f in self.flat if f.idx not in (i, j)]
                keep = []
                for q in pts:
                    if q is None:
                        keep.append(False)
                        continue
                    ti = self.tf(fi, q)
                    tv = self._tv(q)
                    if not others:
                        keep.append(True)
                    elif self.mode == 'max':
                        keep.append(ti >= max(float(tv[f.idx]) for f in others) - tol)
                    else:
                        keep.append(ti <= min(float(tv[f.idx]) for f in others) + tol)
            grow = list(keep)
            for k, on in enumerate(keep):
                if on:
                    for kk in (k - 1, k + 1):
                        if 0 <= kk < len(pts) and pts[kk] is not None:
                            grow[kk] = True
            run = []
            for k, on in enumerate(grow + [False]):
                if on:
                    run.append(pts[k])
                elif run:
                    if len(run) >= 2:
                        out.append([run[0], run[-1]] if self.soft <= 0.0 else run)
                    run = []
        return out

    # -- Ramp Soft rows ---------------------------------------------------------------------------------------
    def soft_points(self):
        """Rows across the ramp (constraint lines) and points near the walls on each row (free points)."""
        if self.soft <= 0.0:
            return [], []
        ax, ay, nx, ny, reach = self.rg
        tol = 0.003 * (20.0 / max(8, self.res)) ** 2
        dl = math.sqrt(8.0 * tol / (6.0 * self.soft))
        n = max(3, int(math.ceil(1.0 / dl)))
        x0, x1, y0, y1 = self.bbox
        ext = max(x1 - x0, y1 - y0)
        u = (-ny, nx)
        rows, pts = [], []
        for r in range(n + 1):
            f = r / n
            off = (1.0 - f) * reach
            p = (ax + nx * off, ay + ny * off)
            cs = _line_cross(self.loops, p, u)
            if len(cs) < 2:
                continue
            rows.append([(p[0] - u[0] * 3 * ext, p[1] - u[1] * 3 * ext), (p[0] + u[0] * 3 * ext, p[1] + u[1] * 3 * ext)])
            for s_in, s_out in zip(cs[0::2], cs[1::2]):
                span = s_out - s_in
                for end, sgn in ((s_in, 1.0), (s_out, -1.0)):
                    for q in BAND:
                        want = q * self.reach2_px
                        lo_, hi_ = 0.0, span * 0.5
                        q_at = lambda t: (p[0] + u[0] * (end + sgn * t), p[1] + u[1] * (end + sgn * t))
                        if self.edist(q_at(hi_)) < want:
                            continue
                        for _it in range(30):
                            m = 0.5 * (lo_ + hi_)
                            if self.edist(q_at(m)) < want:
                                lo_ = m
                            else:
                                hi_ = m
                        pts.append(q_at(0.5 * (lo_ + hi_)))
        # the shallow end: a row right where the ramp reaches the surface (past it nothing more is carved)
        return rows, pts


def _triangulate(P, pairs):
    """CDT of the outline, the creases of ``pairs`` (and the Ramp Soft rows / points), each triangle labelled
    with the facet whose floor it is on.  Returns (screen verts, triangles, labels)."""
    x0, x1, y0, y1 = P.bbox
    ext = max(x1 - x0, y1 - y0)
    coords = []
    edges = []
    for lp in P.loops:
        base = len(coords)
        coords += lp
        edges += [(base + i, base + (i + 1) % len(lp)) for i in range(len(lp))]
    lines = P.creases(pairs)
    rows, free = P.soft_points()
    for pl in lines + rows:
        base = len(coords)
        coords += pl
        edges += [(base + i, base + i + 1) for i in range(len(pl) - 1)]
    # free points (Ramp Soft side band, they sit on the rows) not too near a crease / the outline: no slivers
    keep_d = ext / 400.0
    cons = [(lp[i - 1], lp[i]) for lp in P.loops for i in range(len(lp))]
    cons += [(pl[i], pl[i + 1]) for pl in lines for i in range(len(pl) - 1)]
    for q in free:
        if min(_seg_d(q, a, b) for a, b in cons) > keep_d:
            coords.append(q)
    oV, _oE, oF, _oVo, _oEo, _oFo = delaunay_2d_cdt(coords, edges, [list(range(len(P.outer)))], 1, 1e-7 * ext, True)
    oV = [tuple(q) for q in oV]
    tris, labels = [], []
    for tri in oF:
        if len(tri) != 3:
            continue
        x = tuple(sum(oV[v][c] for v in tri) / 3.0 for c in range(2))
        if not _inside(P.outer, x) or any(_inside(h, x) for h in P.holes):
            continue                 # (many crease lines can close cells outside the outline: the CDT keeps them)
        lab = P.label(x)
        if lab is None:
            raise Fallback('the floor pieces do not fit (creases cross inside the outline)')
        tris.append(tri)
        labels.append(lab)
    return oV, tris, labels


def build_cutter(P, clear):
    """(verts, faces) of the cutter (world): floor = each facet's own plane / offset surface with creases, walls
    along the view rays, a lid well above the surface.  Two floors that meet where no crease was drawn get one
    (and the triangulation is done again)."""
    proj = P.proj
    pairs = {tuple(sorted(k)) for k in P.pairs()}
    tol = P.height * 1e-3
    for _round in range(4):
        oV, tris, labels = _triangulate(P, sorted(pairs))
        new = set()
        edge_lab = {}
        for tri, lab in zip(tris, labels):
            for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                k = (min(a, b), max(a, b))
                other = edge_lab.get(k)
                if other is not None and other != lab:
                    pr = (min(lab, other), max(lab, other))
                    fa, fb = P.facets[pr[0]], P.facets[pr[1]]
                    if any(abs(P.tf(fa, oV[v]) - P.tf(fb, oV[v])) > tol for v in k) and pr not in pairs:
                        new.add(pr)
                edge_lab[k] = lab
        if not new:
            break
        pairs |= new
    inc = {}
    for tri, lab in zip(tris, labels):
        for v in tri:
            inc.setdefault(v, set()).add(lab)
    tf, worst = {}, 0.0
    for v, labs in inc.items():
        ts = [P.tf(P.facets[lab], oV[v]) for lab in labs]
        worst = max(worst, max(ts) - min(ts))
        tf[v] = sum(ts) / len(ts)
    if worst > P.height * 0.05:
        raise Fallback(f'floor pieces do not meet at a crease ({worst:.3g})')
    # the lid: one depth along the rays, above every facet's plane at every point (outside the material)
    no = np.array([tuple(f.no) for f in P.facets])
    cn = np.array([f.co.dot(f.no) for f in P.facets])
    tl = math.inf
    for v in inc:
        o, d = _ray(proj, oV[v])
        den = no @ np.array(d)
        if np.abs(den).min() < 1e-12:
            raise Fallback('ray parallel to a facet')
        tl = min(tl, float(((cn - no @ np.array(o)) / den).min()))
    tl -= clear
    verts, faces = [], []
    fl, li = {}, {}
    for v in inc:
        o, d = _ray(proj, oV[v])
        fl[v] = len(verts)
        verts.append(o + d * max(tf[v], tl + clear * 0.05))
        li[v] = len(verts)
        verts.append(o + d * tl)
    # each face's group: faces of one group lie on one plane and become one polygon (the floor of one facet -
    # not with Ramp Soft, its floor bends -, the lid, the wall along one outline side)
    x0, x1, y0, y1 = P.bbox
    eps = 1e-6 * max(x1 - x0, y1 - y0)
    sides = [(lp[i - 1], lp[i]) for lp in P.loops for i in range(len(lp))]
    on = {}
    for v in inc:
        on[v] = {k for k, (a, b) in enumerate(sides) if _seg_d(oV[v], a, b) < eps}
    groups = []
    cnt = set()
    for tri, lab in zip(tris, labels):
        faces.append(tuple(fl[v] for v in tri))
        groups.append(('F', lab) if P.soft <= 0.0 else None)
        faces.append(tuple(li[v] for v in reversed(tri)))
        groups.append(('L',))
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            cnt.add((a, b))
    for (a, b) in cnt:
        if (b, a) not in cnt:
            faces.append((fl[b], fl[a], li[a], li[b]))
            common = on[a] & on[b]
            groups.append(('W', min(common)) if common else None)
    return verts, faces, worst, groups


def merge_groups(verts, faces, groups):
    """Faces of one group (on one plane by construction) -> one polygon: few faces however many creases cut the
    floor into slivers."""
    bm = bmesh.new()
    try:
        bv = [bm.verts.new(q) for q in verts]
        gid = {}
        for f, g in zip(faces, groups):
            try:
                face = bm.faces.new([bv[k] for k in f])
            except ValueError:
                continue
            if g is not None:
                gid[face] = g
        inner = [e for e in bm.edges if len(e.link_faces) == 2 and e.link_faces[0] in gid
                 and gid.get(e.link_faces[0]) == gid.get(e.link_faces[1])]
        if inner:
            bmesh.ops.dissolve_edges(bm, edges=inner, use_verts=True, use_face_split=False)
        bm.verts.ensure_lookup_table()
        return [v.co.copy() for v in bm.verts], [tuple(v.index for v in f.verts) for f in bm.faces]
    finally:
        bm.free()


def merge_planar(verts, faces, deg=0.02):
    """Triangles on one plane -> one polygon.  Each polygon is grown from a seed triangle and only takes
    triangles on the seed's own plane (a gently bent Ramp Soft floor stays as it is - an angle test between
    neighbours alone would chain it into bent polygons)."""
    bm = bmesh.new()
    try:
        bv = [bm.verts.new(q) for q in verts]
        for f in faces:
            try:
                bm.faces.new([bv[k] for k in f])
            except ValueError:
                pass
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-9)
        bm.normal_update()
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        size = max((v.co - bm.verts[0].co).length for v in bm.verts) or 1.0
        cosmax = math.cos(math.radians(deg))
        group = {}
        for f0 in bm.faces:
            if f0.index in group:
                continue
            n0, c0 = f0.normal.copy(), f0.verts[0].co.copy()
            group[f0.index] = f0.index
            stack = [f0]
            while stack:
                f = stack.pop()
                for e in f.edges:
                    for g in e.link_faces:
                        if g.index in group:
                            continue
                        if g.normal.dot(n0) >= cosmax and all(abs((v.co - c0).dot(n0)) < size * 1e-6 for v in g.verts):
                            group[g.index] = f0.index
                            stack.append(g)
        inner = [e for e in bm.edges if len(e.link_faces) == 2
                 and group[e.link_faces[0].index] == group[e.link_faces[1].index]]
        if inner:
            bmesh.ops.dissolve_edges(bm, edges=inner, use_verts=True, use_face_split=False)
        bm.verts.ensure_lookup_table()
        return [v.co.copy() for v in bm.verts], [tuple(v.index for v in f.verts) for f in bm.faces]
    finally:
        bm.free()


def carve(context, target, groups, projector, settings, height, ramp=None):
    """Carve ``groups`` (screen outlines) into ``target`` with facet floors.  True when done; False when this
    surface / setting is not for it (the caller runs the old carve - the mesh is unchanged)."""
    from . import cape_gen
    from . import core_geometry as cg
    from . import surface_draw as sd
    t0 = time.perf_counter()
    LAST.clear()
    reason = None
    if not ENABLED:
        reason = 'off'
    elif getattr(settings, 'profile', 'SQUARE') != 'SQUARE':
        reason = settings.profile
    elif projector is None:
        reason = 'no view'
    parts, nfac = [], []
    if reason is None:
        try:
            _bvh, lo, hi = cape_gen._body(context, target)
            clear = max(height * 0.6, (hi - lo).length * 0.01)
            res = int(round(getattr(settings, 'fine', 20 / 28.0) * 28))
            steep = getattr(settings, 'steep', 'EVEN')
            for outer, holes in groups:
                P = Plan(target, outer, holes, projector, height, ramp, height * 0.04, res, steep)
                verts, faces, _w, fgroups = build_cutter(P, clear)
                verts, faces = merge_groups(verts, faces, fgroups)
                if P.soft > 0.0:              # the bent Ramp Soft floor: still one polygon per flat strip
                    verts, faces = merge_planar(verts, faces)
                parts.append((verts, faces))
                nfac.append(len(P.facets))
        except Fallback as ex:
            reason = str(ex)
    if reason is None:
        try:
            sd.carve_parts(context, target, parts)
        except cg.CutError as ex:                        # (the mesh is unchanged on an error)
            reason = 'Boolean: ' + str(ex).splitlines()[0][:80]
    dt = time.perf_counter() - t0
    if reason is not None:
        LAST.update(path='old', reason=reason, seconds=dt)
        return False
    LAST.update(path='facet', reason=None, facets=nfac, faces=sum(len(f) for _v, f in parts), seconds=dt)
    return True
