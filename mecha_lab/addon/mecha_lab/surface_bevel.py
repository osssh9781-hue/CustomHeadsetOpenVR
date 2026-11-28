"""0.24.364 Surface Bevel (user: "베벨이랑 챔퍼도 더 좋고 빠르게" -> research: 3ds Max 2027 Smart Bevel): the cut's
rim chamfered / rounded WITHOUT a second boolean.

* The rim: the edges between the cut's faces (``mch_cutter_face``) and the old surface.
* On each side (the old surface, the cut wall) every point near the rim gets its distance from the rim, and the mesh is
  cut along the line at ``width`` from it (and, for a round on a coarse mesh, along lines in between) - the band's
  borders are clean lines at an even distance, however the boolean's slivers run.
* The points between the two lines are moved onto the profile: from the line on the surface, round the corner, to the
  line on the wall - straight (Chamfer) or an arc touching both (Bevel).  The mesh keeps its points (no faces deleted,
  no new boolean): a dense sculpt gets a dense, smooth round, nothing opens.

Same contract as ``rim_sweep.finish``: returns the number of rim edges finished (0 = mesh unchanged).
"""
from __future__ import annotations

import math

import bmesh
from mathutils import Vector
from mathutils.kdtree import KDTree

from . import core_geometry as cg

LAST = {}
DEBUG = False


def _rim_frames(rim, layer):
    """Per rim point: (surface direction, wall direction) away from the rim, in each side's face plane, averaged
    over its rim edges (length-weighted)."""
    acc = {}
    for e in rim:
        f0, f1 = e.link_faces
        fs, fw = (f1, f0) if f0[layer] else (f0, f1)
        a, b = e.verts
        t = b.co - a.co
        ln = t.length
        if ln < 1e-15:
            continue
        t /= ln
        out = []
        for f in (fs, fw):
            lp = next(l for l in f.loops if l.edge == e)
            run = lp.link_loop_next.vert.co - lp.vert.co   # (the face's winding: its inside is to the left)
            u = f.normal.cross(run)
            if u.length < 1e-15:
                break
            out.append(u.normalized())
        if len(out) < 2:
            continue
        for v in (a, b):
            s = acc.setdefault(v, [Vector(), Vector(), []])
            s[0] += out[0] * ln
            s[1] += out[1] * ln
            s[2].append(e)
    frames = {}
    for v, (us, uw, es) in acc.items():
        if us.length > 1e-12 and uw.length > 1e-12:
            frames[v] = (us.normalized(), uw.normalized(), es)
    return frames


class _Rim:
    """Nearest point on the rim polyline, with the side directions and the band's width there (interpolated along
    the rim edge)."""

    def __init__(self, frames, widths=None, w=1.0):
        self.verts = list(frames)
        self.frames = frames
        self.widths = widths if widths is not None else {}
        self.w = w
        self.kd = KDTree(len(self.verts))
        for i, v in enumerate(self.verts):
            self.kd.insert(v.co, i)
        self.kd.balance()

    def width(self, v):
        return self.widths.get(v, self.w)

    def near(self, p):
        """(distance, point, surface direction, wall direction, width)"""
        best = None
        for _co, i, _d in self.kd.find_n(p, 3):
            v = self.verts[i]
            us, uw, es = self.frames[v]
            wv = self.width(v)
            cand = [(v.co.copy(), us, uw, wv)]
            for e in es:
                o = e.other_vert(v)
                fo = self.frames.get(o)
                if fo is None:
                    continue
                d = o.co - v.co
                ll = d.length_squared
                if ll < 1e-24:
                    continue
                s = max(0.0, min(1.0, (p - v.co).dot(d) / ll))
                cand.append((v.co + d * s, (us * (1 - s) + fo[0] * s).normalized(),
                             (uw * (1 - s) + fo[1] * s).normalized(), wv * (1 - s) + self.width(o) * s))
            for c, a, b, wl in cand:
                dd = (p - c).length
                if best is None or dd < best[0]:
                    best = (dd, c, a, b, wl)
        return best


def _pairs(f, d, side, s, L, tol):
    """The points of face ``f`` on the line at ``L``, paired across the band's part of the face: going round the
    face, two line points with only band points (nearer than ``L``) between them."""
    vs = list(f.verts)
    n = len(vs)
    on = [i for i, v in enumerate(vs) if v in d and side[v] in (0, s) and abs(d[v] - L) <= tol]
    if len(on) < 2:
        return []
    if len(on) == 2:
        return [(vs[on[0]], vs[on[1]])]
    out = []
    for k, i in enumerate(on):
        j = on[(k + 1) % len(on)]
        mid = [vs[(i + m) % n] for m in range(1, (j - i) % n)]
        if mid and all(v in d and d[v] < L for v in mid):
            out.append((vs[i], vs[j]))
    return out


def _walk(loop, i, step, levels, d, tol):
    """From the chain's end ``loop[i]`` along the face's border (``step`` = -1 back, +1 on): the point on each line
    (``levels``) and the points between.  Returns ([(level point, [points between it and the one before])], index
    after the last) or None when the border leaves the band before the last line."""
    n = len(loop)
    out = []
    between = []
    k = i
    for L in levels:
        while True:
            k = (k + step) % n
            if k == i:
                return None
            v = loop[k]
            dv = d.get(v)
            if dv is None:
                return None
            if abs(dv - L) <= tol:
                out.append((v, between))
                between = []
                break
            if dv > L:
                return None
            between.append(v)
    return out, k


def _inset_wide(bm, layer, rimset, rim_e, frames, R, levels, d, side, near, tol):
    """A face round the rim wider than the band (a cut wall: a few big faces from the cutter; a low-poly surface):
    rows of points parallel to its rim edges at each line's distance, joined to the points where its border crosses
    the lines - strips along the rim, the rest of the face beyond the last row.  Returns the faces made."""
    w = levels[-1]
    made = 0
    M = len(levels)
    queue = [f for f in {f for v in rimset for f in v.link_faces} if len(f.verts) > 4]
    while queue:
        f = queue.pop()
        if not f.is_valid:
            continue
        loop = list(f.verts)
        n = len(loop)
        on = [loop[k] in rimset and loop[(k + 1) % n] in rimset and
              any(e in rim_e for e in loop[k].link_edges if loop[(k + 1) % n] in e.verts) for k in range(n)]
        if all(on) or not any(on):
            continue
        starts = [k for k in range(n) if on[k] and not on[k - 1]]
        chains = []
        ok = True
        for k0 in starts:
            m = 0
            while on[(k0 + m) % n]:
                m += 1
            ch = [loop[(k0 + j) % n] for j in range(m + 1)]
            bk = _walk(loop, k0 % n, -1, levels, d, tol)
            fw = _walk(loop, (k0 + m) % n, 1, levels, d, tol)
            if bk is None or fw is None:
                ok = False
                if DEBUG:
                    LAST.setdefault('why', []).append(('walk', n, m))
                break
            chains.append((k0, m, ch, bk, fw))
        if not ok or not chains:
            continue
        k0, m, chain, back, fwd = chains[0]
        prev = [p for p, _b in back[0]]
        pbet = [list(reversed(b)) for _p, b in back[0]]          # (in the face's own order)
        nxt = [p for p, _b in fwd[0]]
        nbet = [b for _p, b in fwd[0]]
        used = set(chain) | set(prev) | set(nxt) | {v for b in pbet + nbet for v in b}
        if len(used) != len(chain) + len(prev) + len(nxt) + sum(len(b) for b in pbet + nbet):
            continue                                  # (the two walks met: a face no wider than the band)
        others = set()                                # (the face's other chains and their walks: done after this one)
        for _k, _m, ch, bk, fw in chains[1:]:
            others |= set(ch) | {p for p, _b in bk[0] + fw[0]} | {v for _p, b in bk[0] + fw[0] for v in b}
        if others & used:
            continue
        rest = [v for v in loop if v not in used and v not in others]
        if (not rest and not others) or any(d.get(v, w) < w - tol for v in rest):
            if DEBUG:
                LAST.setdefault('why', []).append(('rest', n, m, len(rest), ''.join(
                    'R' if v in rimset else ('C' if v in chain else ('p' if v in used else
                    ('x' if v not in d else str(min(9, int(10 * d[v])))))) for v in loop)))
            continue
        s = 2 if f[layer] else 1
        nrm = f.normal.copy()
        rows = [chain]
        for j, L in enumerate(levels):
            row = [prev[j]]
            for r in chain[1:-1]:
                us, uw, _es = frames[r]
                u = uw if s == 2 else us
                wr = R.width(r)
                p = r.co + u * (L * wr)
                p -= nrm * (p - r.co).dot(nrm)
                nv = bm.verts.new(p)
                d[nv], side[nv] = L, s
                near[nv] = (L * wr, r.co.copy(), us, uw, wr)
                row.append(nv)
            row.append(nxt[j])
            rows.append(row)
        new = []
        try:
            for j in range(1, M + 1):
                a, b = rows[j], rows[j - 1]
                for k in range(m):
                    poly = [a[k]] + (pbet[j - 1] if k == 0 else []) + [b[k], b[k + 1]] + \
                        (nbet[j - 1] if k == m - 1 else []) + [a[k + 1]]
                    new.append(bm.faces.new(poly, f))
            i_p = loop.index(prev[-1])
            outer = []
            k = (loop.index(nxt[-1]) + 1) % n
            while k != i_p:
                outer.append(loop[k])
                k = (k + 1) % n
            new.append(bm.faces.new([prev[-1]] + rows[M][1:-1] + [nxt[-1]] + outer, f))
        except ValueError:
            for g in new:
                bm.faces.remove(g)
            for r in rows[1:]:
                for v in r[1:-1]:
                    if not v.link_faces:
                        bm.verts.remove(v)
            continue
        bm.faces.remove(f)
        made += len(new)
        if len(new[-1].verts) > 4:
            queue.append(new[-1])                     # (the rest of the face: another chain of it, if any)
    return made


def _profile(a, c, b, t, mode, wt):
    if mode == 'CHAMFER':
        return a.lerp(b, t)
    u = 1.0 - t
    w0, w1, w2 = u * u, 2.0 * t * u * wt, t * t
    return (a * w0 + c * w1 + b * w2) / (w0 + w1 + w2)


def finish(mesh, mode='CHAMFER', width=0.01, segments=3):
    """Chamfer / round the cut's rim on ``mesh`` (object space) by moving the points round it onto the profile."""
    LAST.clear()
    if mode not in {'CHAMFER', 'BEVEL'} or width <= 0 or mesh.attributes.get(cg.CUTTER_ATTR) is None:
        return 0
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        layer = cg._face_flag_layer(bm)
        if layer is None:
            return 0
        rim = cg._rim_edges(bm, layer)
        if not rim:
            return 0
        n = _finish_bm(bm, layer, rim, mode, width, max(1, int(segments)))
        if n:
            bm.normal_update()
            bm.to_mesh(mesh)
            mesh.update()
        return n
    finally:
        bm.free()


CREASE = math.cos(math.radians(35.0))   # two faces of one side meeting sharper than this: a crease


def _room(rimset, frames, R, side_of, w):
    """The band's room at each rim point: the nearest crease running along the rim (not away from it: a pocket's
    corner edges run down from the rim) on either side, x 0.9, then made to change no faster than the rim runs (a
    width tapering at 45 degrees along it); ``w`` where there is none within it."""
    import heapq
    seen = {v: 0.0 for v in rimset}
    stack = list(rimset)
    room = {v: w for v in rimset}
    while stack:
        v = stack.pop()
        if seen[v] >= w:
            continue
        for e in v.link_edges:
            o = e.other_vert(v)
            if o in seen:
                continue
            so = side_of(o)
            if so <= 0:
                continue
            nb = R.near(o.co)
            seen[o] = nb[0]
            out = o.co - nb[1]
            stop = False
            if out.length > 1e-15:
                out.normalize()
                for x in o.link_edges:
                    lf = x.link_faces
                    if len(lf) != 2 or bool(lf[0].normal.dot(lf[1].normal) >= CREASE):
                        continue
                    if x.calc_length() < 0.25 * w or min(lf[0].calc_area(), lf[1].calc_area()) < 0.02 * w * w:
                        continue                        # (a boolean's sliver, not a crease of the part)
                    t = x.verts[1].co - x.verts[0].co
                    if t.length < 1e-15 or abs(t.normalized().dot(out)) > 0.7:
                        continue                        # (a crease running away from the rim)
                    stop = True
                    break
            if stop:
                _co, i, _dd = R.kd.find(nb[1])
                rv = R.verts[i]
                room[rv] = min(room[rv], 0.9 * nb[0])
                continue
            stack.append(o)
    # (no faster than 45 degrees along the rim: a short wall's narrowing eased out to the full width)
    heap = [(r, id(v), v) for v, r in room.items() if r < w]
    heapq.heapify(heap)
    while heap:
        r, _i, v = heapq.heappop(heap)
        if r > room[v]:
            continue
        for e in frames[v][2]:
            o = e.other_vert(v)
            if o not in room:
                continue
            ro = r + e.calc_length()
            if ro < room[o]:
                room[o] = ro
                heapq.heappush(heap, (ro, id(o), o))
    return room


def _finish_bm(bm, layer, rim, mode, w, segments):
    frames = _rim_frames(rim, layer)
    if not frames:
        return 0
    R = _Rim(frames)
    rimset = set(frames)

    def side_of(v):
        fl = [bool(f[layer]) for f in v.link_faces]
        if not fl:
            return -1
        return 2 if all(fl) else (1 if not any(fl) else 0)

    # how far each side goes before a crease running along the rim (a pocket's floor, a hard edge of the part): the
    # band stays on the flat of it - narrower where a side is shorter than ``w`` (a shallow pocket wall), eased
    room = _room(rimset, frames, R, side_of, w)
    small = 0.05 * w
    if all(r < small for r in room.values()):
        LAST['skipped'] = 'no room: the rim\'s sides are shorter than 5 % of the width'
        return 0
    if min(room.values()) < w:
        LAST['narrowed'] = min(room.values())
    room = {v: (r if r >= small else 0.0) for v, r in room.items()}
    R = _Rim(frames, room, w)
    # the lines, as shares of the width there (1 = the band's border); a round on a coarse mesh: lines between
    lens = [e.calc_length() for e in rim]
    edge = sorted(lens)[len(lens) // 2] if lens else w
    levels = [1.0]
    if mode == 'BEVEL':
        m = max(1, int(math.ceil(segments / 2.0)))
        if edge > 0.6 * w / m:
            levels = [k / m for k in range(1, m + 1)]

    def rel(nb):                                     # (a point's distance as a share of the width there)
        return nb[0] / nb[4] if nb[4] > 1e-12 else 1e9
    # 0 a long edge leaving the rim (a cut wall of one face, rim to rim) gets points on those lines first: its
    #   ends both sit on a rim (distance 0), so no line would cross it
    d, side, near = {}, {}, {}
    rim_e = set(rim)
    inserted = 0
    for v in list(rimset):
        wv = R.width(v)
        if wv <= 0:
            continue
        for e in list(v.link_edges):
            if e in rim_e or not e.is_valid:
                continue
            o = e.other_vert(v)
            ln = e.calc_length()
            limit = 0.5 * ln if o in rimset else ln - 1e-6 * ln
            if ln <= wv * 1.05 and o not in rimset:
                continue
            s = 2 if all(f[layer] for f in e.link_faces) else (1 if not any(f[layer] for f in e.link_faces) else 0)
            if s == 0:
                continue
            cur_e, cur_v, done = e, v, 0.0
            for L in levels:
                at = L * wv
                if at >= limit - 1e-9 * ln:
                    break
                fac = (at - done) / (ln - done)
                ne, nv = bmesh.utils.edge_split(cur_e, cur_v, fac)
                d[nv], side[nv] = L, s
                near[nv] = R.near(nv.co)
                inserted += 1
                cur_e = ne if o in ne.verts else cur_e
                cur_v, done = nv, at
    LAST['inserted'] = inserted
    # 1 the points round the rim, per side, with their distance (flood from the rim, stops past ``w``)
    for v in rimset:
        d[v], side[v], near[v] = 0.0, 0, (0.0, v.co.copy(), frames[v][0], frames[v][1], R.width(v))
    stack = list(rimset) + [v for v in d if v not in rimset]
    reach = 1.0
    while stack:
        v = stack.pop()
        if d[v] >= reach:
            continue
        for e in v.link_edges:
            o = e.other_vert(v)
            if o in d:
                continue
            s = side_of(o)
            if s <= 0:
                if o in rimset:
                    continue
                s = 1                                # (a point on both sides off the rim: the surface's)
            nb = R.near(o.co)
            d[o], side[o], near[o] = rel(nb), s, nb
            stack.append(o)
    LAST['band'] = len(d)

    # 2 the mesh cut along lines at an even distance from the rim (the levels above)
    eps = 1e-7                                       # (in shares of the width)
    cuts = 0
    for s in (1, 2):
        for L in levels:
            touched = set()
            for e in [e for e in {e for v in d if side[v] in (0, s) for e in v.link_edges}]:
                a, b = e.verts
                if a not in d or b not in d or side[a] not in (0, s) or side[b] not in (0, s):
                    continue
                da, db = d[a], d[b]
                if (da - L) * (db - L) >= 0 or abs(da - db) < 1e-15:
                    continue
                fac = (L - da) / (db - da)
                if fac <= 1e-6 or fac >= 1 - 1e-6:
                    continue
                _ne, nv = bmesh.utils.edge_split(e, a, fac)
                d[nv], side[nv] = L, s
                near[nv] = R.near(nv.co)
                touched.update(nv.link_faces)
                cuts += 1
            for f in touched:
                if not f.is_valid or len(f.verts) > 5:
                    continue                          # (a big face: the inset below)
                for va, vb in _pairs(f, d, side, s, L, eps):
                    if not (va.is_valid and vb.is_valid):
                        continue
                    ff = [g for g in va.link_faces if g in vb.link_faces]
                    if not ff or any(vb in e.verts for e in va.link_edges if e in ff[0].edges):
                        continue                      # (already joined by an edge of the face)
                    try:
                        bmesh.utils.face_split(ff[0], va, vb)
                    except (ValueError, RuntimeError):
                        pass
    LAST['cuts'] = cuts
    LAST['inset'] = _inset_wide(bm, layer, rimset, rim_e, frames, R, levels, d, side, near, eps)

    # 3 the points inside the band onto the profile (surface line -> round the corner -> wall line)
    moved = 0
    new_co = {}
    for v, dv in d.items():
        if dv >= 1.0 - 1e-9:
            continue
        s = side[v]
        _dd, c, us, uw, wl = near[v][:5]
        if wl <= 0:
            continue
        cosang = max(-1.0, min(1.0, us.dot(uw)))
        theta = math.acos(cosang)                      # (the corner's angle: 90 deg for a cut straight down)
        if theta > math.radians(170):
            continue                                   # (flat: no corner to round)
        wt = math.sin(0.5 * theta)
        a, b = c + us * wl, c + uw * wl
        if s == 0:
            t, r = 0.5, Vector()
        elif s == 1:
            t = 0.5 * (1.0 - dv)
            r = (v.co - (c + us * (dv * wl))) * dv     # (the surface's own bend kept, all of it at the line)
        else:
            t = 0.5 + 0.5 * dv
            r = (v.co - (c + uw * (dv * wl))) * dv
        new_co[v] = _profile(a, c, b, t, mode, wt) + r
    mv = 0.0
    big = []
    for v, co in new_co.items():
        mv = max(mv, (co - v.co).length)
        big.append(((co - v.co).length / w, round(d[v], 3), side[v], tuple(round(x, 3) for x in v.co)))
        v.co = co
        moved += 1
    LAST['moved'] = moved
    LAST['maxmove'] = round(mv / w, 3)
    if DEBUG:
        big.sort(reverse=True)
        LAST['big'] = [(round(b[0], 3),) + b[1:] for b in big[:12]]
        LAST['sides'] = {k: sum(1 for b in big if b[2] == k) for k in (0, 1, 2)}
    return len(rim) if moved else 0
