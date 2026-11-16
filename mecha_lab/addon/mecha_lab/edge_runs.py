"""0.24.178 the hard edges of a part as runs you can pick (user: "선을 긋는 게 아니라 내가 선택할 수 있는 엣지들을 보여주는 게
나을 거 같고"): Geo Sculpt's Chamfer / Round and the Boolean Bevel tool show them over the part under the mouse, the run
nearest the mouse lit; a click takes that run.

A run = hard edges (sharp, Edge Memory, or faces folded more than 30 degrees) joined end to end where they go on nearly
straight (less than 40 degrees turn) - one side of a box, the rim of a round hole, a panel line.  Everything is in the
part's local space and read from its own mesh (not its modifiers); kept per mesh until the mesh changes.
"""
from __future__ import annotations

import math

import bpy
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree

HARD_ANGLE = math.radians(30.0)
TURN = math.radians(40.0)              # (two hard edges at a point: one run when the line turns less than this)
_CACHE = {}


class Runs:
    """The runs of one mesh: ``co`` (N x 3), ``edges`` (hard edge index -> (a, b)), ``run_of`` (edge -> run),
    ``paths`` (run -> its points in order), ``closed`` (run -> a loop), ``edge_ids`` (run -> its edges in order)."""

    def __init__(self, me):
        """0.24.179 (user: "버벅이니까") read with numpy in one go - no BMesh, no Python loop over every edge."""
        n = len(me.vertices)
        co = np.empty(n * 3, np.float64)
        me.vertices.foreach_get('co', co)
        self.co = co.reshape(-1, 3)
        self.version = 0
        self.batch = None
        nE, nP, nL = len(me.edges), len(me.polygons), len(me.loops)
        ev = np.empty(nE * 2, np.int64)
        me.edges.foreach_get('vertices', ev)
        ev = ev.reshape(-1, 2)
        pn = np.empty(nP * 3, np.float64)
        me.polygons.foreach_get('normal', pn)
        pn = pn.reshape(-1, 3)
        ls = np.empty(nP, np.int64)
        lt = np.empty(nP, np.int64)
        me.polygons.foreach_get('loop_start', ls)
        me.polygons.foreach_get('loop_total', lt)
        lv = np.empty(nL, np.int64)
        le = np.empty(nL, np.int64)
        me.loops.foreach_get('vertex_index', lv)
        me.loops.foreach_get('edge_index', le)
        lp = np.repeat(np.arange(nP), lt)                       # (the face of each corner)
        nxt = ls[lp] + (np.arange(nL) - ls[lp] + 1) % lt[lp]    # (the next corner round the face)
        order = np.argsort(le, kind='stable')
        cnt = np.bincount(le, minlength=nE)
        first = np.concatenate([[0], np.cumsum(cnt)[:-1]])
        two = np.nonzero(cnt == 2)[0]
        l1, l2 = order[first[two]], order[first[two] + 1]
        dot = np.clip((pn[lp[l1]] * pn[lp[l2]]).sum(1), -1.0, 1.0)
        hard_mask = np.zeros(nE, bool)
        hard_mask[two[np.arccos(dot) > HARD_ANGLE]] = True
        for name in ('sharp_edge', 'mch_hard'):
            at = me.attributes.get(name)
            if at is not None and at.domain == 'EDGE' and at.data_type == 'BOOLEAN' and nE:
                v = np.zeros(nE, bool)
                at.data.foreach_get('value', v)
                hard_mask |= v
        hard_mask &= cnt == 2
        pos = np.full(nE, -1, np.int64)
        pos[two] = np.arange(len(two))
        hard = set(int(i) for i in np.nonzero(hard_mask)[0])
        hi = np.nonzero(hard_mask)[0]
        k = pos[hi]
        L1, L2 = l1[k], l2[k]
        P1, P2 = lp[L1], lp[L2]

        def inward(L, P):
            d = self.co[lv[nxt[L]]] - self.co[lv[L]]
            w = np.cross(pn[P], d)
            return w / np.maximum(np.linalg.norm(w, axis=1, keepdims=True), 1e-12)
        I1, I2 = inward(L1, P1), inward(L2, P2)
        N = pn[P1] + pn[P2]
        N = N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
        # 0.24.180 (edge loops) the faces either side of each two-face edge that is not hard: the flat areas
        soft = two[~hard_mask[two]]
        ks = pos[soft]
        self._soft = (lp[l1[ks]], lp[l2[ks]])
        self._nP = nP
        self._labels = None
        self.edges = {int(e): (int(ev[e, 0]), int(ev[e, 1])) for e in hi}
        self.normal = {int(e): N[j] for j, e in enumerate(hi)}
        self.faces = {int(e): [(pn[P1[j]], I1[j], int(P1[j])), (pn[P2[j]], I2[j], int(P2[j]))]
                      for j, e in enumerate(hi)}
        # at each point: hard edges that go on nearly straight are joined (each edge to its straightest partner)
        at = {}
        for i, (a, b) in self.edges.items():
            at.setdefault(a, []).append(i)
            at.setdefault(b, []).append(i)
        link = {i: {} for i in hard}           # edge -> {point: the edge it goes on into there}
        for v, es in at.items():
            if len(es) < 2:
                continue
            pairs = []
            for x in range(len(es)):
                for y in range(x + 1, len(es)):
                    turn = math.pi - _angle(self._away(es[x], v), self._away(es[y], v))
                    if turn < TURN:
                        pairs.append((turn, es[x], es[y]))
            used = set()
            for _t, ex, ey in sorted(pairs):
                if ex in used or ey in used:
                    continue
                used.update((ex, ey))
                link[ex][v] = ey
                link[ey][v] = ex
        self.run_of = {}
        self.paths, self.closed, self.edge_ids = [], [], []
        for seed in sorted(hard):
            if seed in self.run_of:
                continue
            # back to an end of the run (an edge with a free point), or round a loop to the seed again
            e, came = seed, None
            closed = False
            for _guard in range(len(hard) + 1):
                a, b = self.edges[e]
                free = [v for v in (a, b) if v not in link[e]]
                if free and e != seed or (free and came is None):
                    break
                nxt_v = next((v for v in (a, b) if v in link[e] and link[e][v] != came), None)
                if nxt_v is None:
                    break
                came, e = e, link[e][nxt_v]
                if e == seed:
                    closed = True
                    break
            start = seed if closed else e
            a, b = self.edges[start]
            if closed:
                v0 = a
            else:
                v0 = a if a not in link[start] else b
            rid = len(self.paths)
            verts, order = [v0], []
            e, v = start, v0
            for _guard in range(len(hard) + 1):
                if e in self.run_of:
                    break
                self.run_of[e] = rid
                order.append(e)
                ea, eb = self.edges[e]
                v = eb if ea == v else ea
                verts.append(v)
                e = link[e].get(v)
                if e is None:
                    break
            if closed and len(verts) > 2 and verts[-1] == verts[0]:
                verts.pop()
            else:
                closed = False
            self.paths.append(verts)
            self.closed.append(closed)
            self.edge_ids.append(order)
        ids = list(self.edges)
        self._ids = np.array(ids, np.int64)
        if ids:
            ab = np.array([self.edges[i] for i in ids], np.int64)
            self._a, self._b = self.co[ab[:, 0]], self.co[ab[:, 1]]
            self.kd = KDTree(len(ids))
            for k, (pa, pb) in enumerate(zip(self._a, self._b)):
                self.kd.insert(Vector((pa + pb) / 2), k)
            self.kd.balance()
            self._half = float(np.max(np.linalg.norm(self._b - self._a, axis=1))) / 2
        else:
            self.kd = None
            self._half = 0.0

    def labels(self):
        """0.24.180 each face's flat area (faces joined across edges that are not hard) - worked out once."""
        if self._labels is not None:
            return self._labels
        nP = self._nP
        a, b = self._soft
        lab = -np.ones(nP, np.int64)
        if nP:
            src = np.concatenate([a, b])
            dst = np.concatenate([b, a])
            order = np.argsort(src, kind='stable')
            nb = dst[order].tolist()
            start = np.concatenate([[0], np.cumsum(np.bincount(src, minlength=nP))]).tolist()
            k = 0
            for f0 in range(nP):
                if lab[f0] >= 0:
                    continue
                lab[f0] = k
                stack = [f0]
                while stack:
                    f = stack.pop()
                    for g in nb[start[f]:start[f + 1]]:
                        if lab[g] < 0:
                            lab[g] = k
                            stack.append(g)
                k += 1
        self._labels = lab
        return lab

    def loop(self, e, p=None, view=None):
        """0.24.180 (user: "엣지 루프 기능도 만들어 주라 - 베벨 말이지") the edge loop through the hard edge ``e``: the
        hard edges round the flat area on the side of ``e`` the point ``p`` (local, near it) is on - the outline of
        that face area through ``e`` (a box's top: its four edges; a cylinder's cap: its rim; an area with a hole:
        the hole's rim or the outline, whichever ``e`` is on).  ``p`` on the edge itself (a shown edge picked off the
        part): the side whose face looks toward ``view`` (the view's direction, local).  [hard edge ids]"""
        if e not in self.faces:
            return [e]
        fa = self.faces[e]
        side = 0
        if p is not None:
            a, b = self.edges[e]
            A, B = self.co[a], self.co[b]
            d = B - A
            t = float(np.clip(np.dot(np.asarray(p, float) - A, d) / max(np.dot(d, d), 1e-18), 0.0, 1.0))
            q = np.asarray(p, float) - (A + d * t)
            if float(np.linalg.norm(q)) < 1e-7 * max(float(np.linalg.norm(d)), 1e-9) and view is not None:
                v = np.asarray(view, float)
                side = 0 if float(-v @ fa[0][0]) >= float(-v @ fa[1][0]) else 1
            else:
                side = 0 if float(q @ fa[0][1]) >= float(q @ fa[1][1]) else 1
        lab = self.labels()
        area = lab[fa[side][2]]
        ids = self._ids
        if not len(ids):
            return [e]
        if not hasattr(self, '_hf'):
            self._hf = np.array([[self.faces[int(i)][0][2], self.faces[int(i)][1][2]] for i in ids], np.int64)
        on = (lab[self._hf[:, 0]] == area) ^ (lab[self._hf[:, 1]] == area)
        cand = {int(i) for i in ids[on]}
        if e not in cand:
            return [e]
        at = {}
        for i in cand:
            for v in self.edges[i]:
                at.setdefault(v, []).append(i)
        out, seen, stack = [], {e}, [e]
        while stack:
            i = stack.pop()
            out.append(i)
            for v in self.edges[i]:
                for j in at.get(v, ()):
                    if j not in seen:
                        seen.add(j)
                        stack.append(j)
        return out

    def loop_parts(self, edges):
        """The runs a loop's edges lie on, each with the stretch of it in the loop: [(run, s0, s1)]."""
        by = {}
        for i in edges:
            by.setdefault(self.run_of[i], []).append(i)
        out = []
        for rid, es in by.items():
            total = self.arc(rid, self.co[self.paths[rid][:1]])[1]
            if len(es) == len(self.edge_ids[rid]) or self.closed[rid]:
                out.append((rid, 0.0, total))
                continue
            pts = self.co[[v for i in es for v in self.edges[i]]]
            s, _t = self.arc(rid, pts)
            out.append((rid, float(s.min()), float(s.max())))
        return out

    def _away(self, e, v):
        a, b = self.edges[e]
        o = b if a == v else a
        return self.co[o] - self.co[v]

    def nearest(self, p, reach, slack=None):
        """(run, edge, distance) of the hard edge nearest ``p`` (local) within ``reach``, or None.  ``slack``: {edge:
        width} - a bevelled edge counts that much nearer (its corner is cut away: the mouse is on its bevel, which
        can lie nearer another edge)."""
        if self.kd is None:
            return None
        p = np.asarray(p, float)
        best = None
        extra = max(slack.values()) if slack else 0.0
        for _c, k, _d in self.kd.find_range(Vector(p), reach + extra + self._half):
            a, b = self._a[k], self._b[k]
            d = b - a
            t = float(np.clip(np.dot(p - a, d) / max(np.dot(d, d), 1e-18), 0.0, 1.0))
            e = int(self._ids[k])
            dist = float(np.linalg.norm(a + t * d - p)) - (slack.get(e, 0.0) if slack else 0.0)
            if dist <= reach and (best is None or dist < best[2]):
                best = (self.run_of[e], e, dist)
        return best

    def polyline(self, rid):
        P = self.co[self.paths[rid]]
        if self.closed[rid]:
            P = np.vstack([P, P[:1]])
        return P

    def arc(self, rid, pts):
        """Arc length along the run of the nearest point to each of ``pts`` (local); and the run's length."""
        P = self.polyline(rid)
        seg = P[1:] - P[:-1]
        L = np.linalg.norm(seg, axis=1)
        s0 = np.concatenate([[0.0], np.cumsum(L)])
        out = []
        for p in np.asarray(pts, float).reshape(-1, 3):
            t = np.clip(((p - P[:-1]) * seg).sum(1) / np.maximum((seg * seg).sum(1), 1e-18), 0.0, 1.0)
            q = P[:-1] + t[:, None] * seg
            k = int(np.argmin(np.linalg.norm(q - p, axis=1)))
            out.append(float(s0[k] + t[k] * L[k]))
        return np.array(out), float(s0[-1])


def _angle(a, b):
    la, lb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if la < 1e-12 or lb < 1e-12:
        return 0.0
    return math.acos(max(-1.0, min(1.0, float(np.dot(a, b)) / (la * lb))))


_DIRTY = set()                         # meshes whose geometry changed since their runs were read


def _key(me):
    """Cheap (every mouse move): the mesh's counts; a change of its points comes from the depsgraph (``_DIRTY``)."""
    return (me.as_pointer(), len(me.vertices), len(me.edges), len(me.polygons))


def get(ob):
    """The runs of ``ob``'s own mesh (kept until it changes)."""
    return get_mesh(ob.data)


def get_mesh(me):
    """The runs of a mesh (kept until it changes)."""
    key = _key(me)
    hit = _CACHE.get(me.name)
    if hit is not None and hit[0] == key and me.name not in _DIRTY:
        return hit[1]
    _DIRTY.discard(me.name)
    r = Runs(me)
    if len(_CACHE) > 16:
        _CACHE.clear()
    _CACHE[me.name] = (key, r)
    return r


def clear():
    _CACHE.clear()


@bpy.app.handlers.persistent
def _on_update(scene, depsgraph):
    try:
        for u in depsgraph.updates:
            if u.is_updated_geometry and isinstance(u.id, bpy.types.Object):
                ob = u.id.original
                if ob.type == 'MESH' and ob.data is not None and ob.data.name in _CACHE:
                    _DIRTY.add(ob.data.name)
    except (ReferenceError, AttributeError, RuntimeError):
        pass


def register():
    if _on_update not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_update)


def unregister():
    if _on_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_update)
    _CACHE.clear()


def draw_all(ob, runs, colour, width=1.5):
    """Every hard edge of ``ob`` (one GPU batch, kept while the part and its place stay the same)."""
    import gpu
    from gpu_extras.batch import batch_for_shader
    key = (tuple(tuple(r) for r in ob.matrix_world), len(runs.edges))
    if runs.batch is None or runs.batch[0] != key:
        segs = world_segs(ob, runs)
        if not segs:
            return
        sh = _shader()
        runs.batch = (key, sh, batch_for_shader(sh, 'LINES', {'pos': [tuple(p) for s_ in segs for p in s_]}))
    _key_, sh, batch = runs.batch
    gpu.state.blend_set('ALPHA')
    gpu.state.depth_test_set('LESS_EQUAL')
    gpu.state.depth_mask_set(False)
    try:
        if 'POLYLINE' in getattr(sh, 'name', 'POLYLINE'):
            try:
                region = bpy.context.region
                sh.uniform_float('viewportSize', (region.width, region.height))
                sh.uniform_float('lineWidth', width)
            except (ValueError, AttributeError):
                pass
        else:
            gpu.state.line_width_set(width)
        sh.uniform_float('color', colour)
        batch.draw(sh)
    finally:
        gpu.state.depth_test_set('NONE')
        gpu.state.blend_set('NONE')


# --- drawing (POST_VIEW, world space) ----------------------------------------------------------------------------

def _shader():
    import gpu
    try:
        return gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
    except (ValueError, SystemError):
        return gpu.shader.from_builtin('UNIFORM_COLOR')


def draw_lines(segs, colour, width=2.0, xray=False):
    """World segments [(a, b), ...] as lines (hidden behind the part unless ``xray``)."""
    if not segs:
        return
    import gpu
    from gpu_extras.batch import batch_for_shader
    sh = _shader()
    coords = [tuple(p) for s in segs for p in s]
    batch = batch_for_shader(sh, 'LINES', {'pos': coords})
    gpu.state.blend_set('ALPHA')
    gpu.state.depth_test_set('NONE' if xray else 'LESS_EQUAL')
    gpu.state.depth_mask_set(False)
    try:
        if 'POLYLINE' in getattr(sh, 'name', 'POLYLINE'):
            try:
                region = bpy.context.region
                sh.uniform_float('viewportSize', (region.width, region.height))
                sh.uniform_float('lineWidth', width)
            except (ValueError, AttributeError):
                pass
        else:
            gpu.state.line_width_set(width)
        sh.uniform_float('color', colour)
        batch.draw(sh)
    finally:
        gpu.state.depth_test_set('NONE')
        gpu.state.blend_set('NONE')


def world_segs(ob, runs, edge_ids=None, lift=None):
    """World segments of the hard edges (all, or ``edge_ids``), lifted a little off the surface (so the depth test
    keeps the ones in sight)."""
    mw = ob.matrix_world
    ids = list(runs.edges) if edge_ids is None else [e for e in edge_ids if e in runs.edges]
    if lift is None:
        lift = (float(np.ptp(runs.co, axis=0).max()) if len(runs.co) else 1.0) * 0.002
    out = []
    for e in ids:
        a, b = runs.edges[e]
        n = runs.normal[e] * lift
        out.append((mw @ Vector(runs.co[a] + n), mw @ Vector(runs.co[b] + n)))
    return out


def portion_segs(ob, runs, rid, s0, s1, lift=None):
    """World segments of a run between arc lengths ``s0`` and ``s1``."""
    P = runs.polyline(rid)
    L = np.linalg.norm(P[1:] - P[:-1], axis=1)
    acc = np.concatenate([[0.0], np.cumsum(L)])
    pts = []
    for k in range(len(L)):
        a, b = acc[k], acc[k + 1]
        if b < s0 or a > s1 or L[k] < 1e-12:
            continue
        t0, t1 = max(s0, a), min(s1, b)
        pts.append((P[k] + (P[k + 1] - P[k]) * ((t0 - a) / L[k]), P[k] + (P[k + 1] - P[k]) * ((t1 - a) / L[k])))
    mw = ob.matrix_world
    if lift is None:
        lift = float(np.ptp(runs.co, axis=0).max()) * 0.003 if len(runs.co) else 0.0
    ns = [runs.normal[e] for e in runs.edge_ids[rid]] or [np.zeros(3)]
    n = np.mean(ns, axis=0)
    n = n / max(np.linalg.norm(n), 1e-12) * lift
    return [(mw @ Vector(pa + n), mw @ Vector(pb + n)) for pa, pb in pts]
