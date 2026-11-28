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
import bpy
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
            for ci in range(1, len(chain) - 1):
                r = chain[ci]
                us, uw, _es = frames[r]
                # (into the face, square to the chain there: the frame's direction is averaged with the next face's
                # and its rows ran over this face's side)
                run = chain[ci + 1].co - chain[ci - 1].co
                u = nrm.cross(run)
                u = u.normalized() if u.length > 1e-15 else (uw if s == 2 else us)
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
            _undo(bm, new, rows, d)
            continue
        if not all(_flat_ok(g, nrm) for g in new):    # 0.24.365 (a low-poly tube: rows across a curved face
            _undo(bm, new, rows, d)                   #  folded the rest of it over - long spikes): left as it was,
                                                      #  for the triangles below
            if DEBUG:
                LAST['inset_undone'] = LAST.get('inset_undone', 0) + 1
            continue
        bm.faces.remove(f)
        made += len(new)
        if len(new[-1].verts) > 4:
            queue.append(new[-1])                     # (the rest of the face: another chain of it, if any)
    return made


def _undo(bm, new, rows, d):
    """The faces an inset made taken away again, with the edges and the row points only they used."""
    edges = {e for g in new if g.is_valid for e in g.edges}
    for g in new:
        if g.is_valid:
            bm.faces.remove(g)
    for e in edges:
        if e.is_valid and not e.link_faces:
            bm.edges.remove(e)
    for r in rows[1:]:
        for v in r[1:-1]:
            if v.is_valid and not v.link_edges:
                d.pop(v, None)
                bm.verts.remove(v)


def _flat_ok(f, nrm):
    """The face lies the way ``nrm`` faces and does not fold over itself (its triangles all face that way)."""
    from mathutils.geometry import tessellate_polygon
    pts = [v.co for v in f.verts]
    if len(pts) < 3:
        return False
    try:
        tris = tessellate_polygon([pts])
    except (ValueError, TypeError):
        return False
    area = 0.0
    for a, b, c in tris:
        n = (pts[b] - pts[a]).cross(pts[c] - pts[a])
        if n.dot(nrm) < -1e-12:
            return False
        area += n.length
    return area > 1e-20


def _profile(a, c, b, t, mode, wt):
    if mode == 'CHAMFER':
        return a.lerp(b, t)
    u = 1.0 - t
    w0, w1, w2 = u * u, 2.0 * t * u * wt, t * t
    return (a * w0 + c * w1 + b * w2) / (w0 + w1 + w2)


EXACT = '.mch_fin_exact'   # (the faces the finish made: edge_memory.finish_band reads them, no geometry guessing)
LOCAL_MIN = 50_000         # a part this dense: the band round the rim taken out, finished on its own and put back


COARSE = 1.5   # the part's edges at the rim this many widths long (median): a low-poly part - the Sweep instead


def coarse(mesh, width):
    """0.24.365 (user's low-poly tube: the band crossed faces wider than itself and the moved points bent them into
    long spikes) the part is coarse round the rim: the median length of the old surface's edges at the rim is over
    ``COARSE`` widths.  Surface moves points, so it needs a dense mesh; a low-poly part gets the Sweep."""
    import numpy as np
    from . import region_cut as rc
    a = mesh.attributes.get(cg.CUTTER_ATTR)
    if a is None or a.domain != 'FACE' or not len(mesh.polygons):
        return False
    co, tot, start, vi = rc.arrays(mesh)
    flag = np.zeros(len(tot), bool)
    a.data.foreach_get('value', flag)
    lm = np.repeat(flag, tot)
    on_cut = np.zeros(len(co), bool)
    on_cut[vi[lm]] = True
    on_old = np.zeros(len(co), bool)
    on_old[vi[~lm]] = True
    rim = on_cut & on_old
    if not rim.any():
        return False
    # the old surface's edges (face corners in order) with one end on the rim and the other off it
    nxt = np.arange(len(vi)) + 1
    ends = start + tot
    nxt[ends - 1] = start
    a0, a1 = vi[~lm], vi[nxt][~lm]
    keep = rim[a0] ^ rim[a1]
    if not keep.any():
        return False
    ln = np.linalg.norm(co[a0[keep]] - co[a1[keep]], axis=1)
    return float(np.median(ln)) > COARSE * width


def finish(mesh, mode='CHAMFER', width=0.01, segments=3):
    """Chamfer / round the cut's rim on ``mesh`` (object space) by moving the points round it onto the profile."""
    LAST.clear()
    if mode not in {'CHAMFER', 'BEVEL'} or width <= 0 or mesh.attributes.get(cg.CUTTER_ATTR) is None:
        return 0
    if len(mesh.polygons) >= LOCAL_MIN:
        try:
            got = _finish_local(mesh, mode, width, segments)
        except (RuntimeError, ValueError, AttributeError, TypeError, IndexError, MemoryError) as ex:
            print('Mecha: surface bevel (local):', ex)
            got = None
        if got is not None:
            return got
    return _finish_mesh(mesh, mode, width, segments)


def _finish_mesh(mesh, mode, width, segments):
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


def _finish_local(mesh, mode, width, segments):
    """0.24.364 (a dense part: reading / writing all of it and the whole-part tidy after took most of the time) the
    faces round the rim - every face with a point within the width plus two edges of it, and two rings more - taken
    out as a small mesh, finished and tidied there, and put back (``region_cut.replace_faces``: the band's border
    points stay where they are).  Returns the rim edges finished, or None when the local path cannot be used."""
    import numpy as np
    from . import region_cut as rc
    co, tot, start, vi = rc.arrays(mesh)
    nf = len(tot)
    a = mesh.attributes.get(cg.CUTTER_ATTR)
    if a is None or a.domain != 'FACE':
        return None
    flag = np.zeros(nf, bool)
    a.data.foreach_get('value', flag)
    if not flag.any() or flag.all():
        return 0
    lm = np.repeat(flag, tot)
    on_cut = np.zeros(len(co), bool)
    on_cut[vi[lm]] = True
    on_old = np.zeros(len(co), bool)
    on_old[vi[~lm]] = True
    rimv = np.flatnonzero(on_cut & on_old)
    if not len(rimv):
        return 0
    # the longest edge at the rim (a wall face from the cutter can be long: its far end is then taken too)
    ev = np.empty(len(mesh.edges) * 2, np.int64)
    mesh.edges.foreach_get('vertices', ev)
    ev = ev.reshape(-1, 2)
    at_rim = np.zeros(len(co), bool)
    at_rim[rimv] = True
    re = ev[at_rim[ev[:, 0]] | at_rim[ev[:, 1]]]
    elen = float(np.linalg.norm(co[re[:, 0]] - co[re[:, 1]], axis=1).max()) if len(re) else 0.0
    rad = width + 2.0 * min(elen, 4.0 * width)
    # points within ``rad`` of a rim point (a grid of ``rad`` cells: a point looks at its cell and the 26 round it)
    cell = max(rad, 1e-12)
    rk = np.floor(co[rimv] / cell).astype(np.int64)
    keys = set(map(tuple, rk.tolist()))
    pk = np.floor(co / cell).astype(np.int64)
    near = np.zeros(len(co), bool)
    offs = [(i, j, k) for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1)]
    karr = np.array(sorted(keys), np.int64)
    span = int(max(1, (np.abs(pk).max() if len(pk) else 0) + 2)) * 2 + 1
    def code(x):
        return (x[:, 0] * span + x[:, 1]) * span + x[:, 2]
    kc = np.sort(code(karr + 0))
    for o in offs:
        c = code(pk + np.array(o, np.int64))
        pos = np.searchsorted(kc, c)
        pos[pos >= len(kc)] = 0
        near |= kc[pos] == c
    cand = np.flatnonzero(near)
    if len(cand):
        tree = KDTree(len(rimv))
        for i, p in zip(range(len(rimv)), co[rimv].tolist()):
            tree.insert(p, i)
        tree.balance()
        keep = np.fromiter((tree.find(p)[2] <= rad for p in co[cand].tolist()), bool, len(cand))
        near[:] = False
        near[cand[keep]] = True
    fmask = np.maximum.reduceat(near[vi].astype(np.int8), start).astype(bool)
    for _ring in range(2):
        vm = np.zeros(len(co), bool)
        vm[vi[np.repeat(fmask, tot)]] = True
        fmask = np.maximum.reduceat(vm[vi].astype(np.int8), start).astype(bool)
    if fmask.sum() > 0.5 * nf:
        return None                                  # (most of the part: no gain)
    size = float(np.linalg.norm(np.ptp(co, axis=0))) or 1.0
    was_region = rc.untouched(mesh) > 0               # (a High Poly cut's result, tidied in its stitch)
    ex = mesh.attributes.get(EXACT)
    if ex is not None and (ex.domain != 'FACE' or ex.data_type != 'INT'):
        mesh.attributes.remove(ex)
        ex = None
    if ex is None:
        mesh.attributes.new(EXACT, 'INT', 'FACE')    # (carried out and back by the sub-mesh)
    sub, _used = rc.extract_faces(mesh, fmask, 'MCH_SurfBevel')
    sub0 = sub.copy()                                 # (the tidy then looks only at what the finish changed)
    try:
        n = _finish_mesh(sub, mode, width, segments)
        if not n:
            ex = mesh.attributes.get(EXACT)
            if ex is not None:
                mesh.attributes.remove(ex)
            return 0
        try:
            cg.tidy_result(sub, size, before=sub0, flip=False)
        except (RuntimeError, ValueError, AttributeError, IndexError, MemoryError):
            pass
        if not rc.replace_faces(mesh, fmask, sub, size):
            ex = mesh.attributes.get(EXACT)
            if ex is not None:
                mesh.attributes.remove(ex)
            return None
    finally:
        bpy.data.meshes.remove(sub)
        bpy.data.meshes.remove(sub0)
    # a High Poly cut's result stays one (its own faces first, in order; the region and the band both tidied): the
    # cut's tidy after skips it as before.  Any other cut's result: its tidy runs as before
    if was_region:
        rc.LAST_REGION.update(name=mesh.name, faces=len(mesh.polygons), untouched=int((~fmask).sum()))
    LAST['local'] = int(fmask.sum())
    return n


SNAP = 0.04                              # a line this near a point (share of the edge): the point taken as on it
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

    eps = 1e-7                                       # (in shares of the width)

    # 1b 0.24.365 (user's low-poly tube; a through cut's walls, rim to rim) an edge the lines cross between its ends
    #    - one passing through the band with both ends outside it, or leaving it with both ends on a rim: points
    #    where the lines cross it, so the faces split there (it was never cut, and the moved points bent its faces)
    def fill_d(v):
        if v not in d:
            nb = R.near(v.co)
            sv = side_of(v)
            d[v], side[v], near[v] = rel(nb), (sv if sv > 0 else 1), nb

    def split_crossings(edges):
        n_new = 0
        for e in list(edges):
            if not e.is_valid or e in rim_e:
                continue
            a, b = e.verts
            fill_d(a)
            fill_d(b)
            ln = e.calc_length()
            if ln < 0.6 * w:
                continue                              # (a short edge: its ends tell; the pass below splits it)
            steps = max(8, min(96, int(ln / max(1e-12, 0.2 * w)) + 1))
            rs = [d[a]] + [rel(R.near(a.co.lerp(b.co, k / steps))) for k in range(1, steps)] + [d[b]]
            ts = []
            for L in levels:
                for k in range(steps):
                    r0, r1 = rs[k] - L, rs[k + 1] - L
                    if r0 * r1 >= 0 or (k == 0 and abs(r0) < eps) or (k == steps - 1 and abs(r1) < eps):
                        continue
                    lo, hi = k / steps, (k + 1) / steps
                    for _i in range(18):              # (bisection on the edge)
                        m = 0.5 * (lo + hi)
                        rm = rel(R.near(a.co.lerp(b.co, m))) - L
                        if (rm < 0) == (r0 < 0):
                            lo = m
                        else:
                            hi = m
                    t = 0.5 * (lo + hi)
                    if SNAP < t < 1 - SNAP:
                        ts.append((t, L))
            if not ts:
                continue
            # (a crossing next to an end the regular pass below handles; only crossings inside the edge here)
            if all((rs[0] - L) * (rs[-1] - L) < 0 for _t, L in ts) and len(ts) == 1:
                continue
            lf = e.link_faces
            sv = 2 if lf and all(f[layer] for f in lf) else 1
            ts.sort()
            cur_e, cur_v, done = e, a, 0.0
            for t, L in ts:
                fac = (t - done) / (1.0 - done)
                ne, nv = bmesh.utils.edge_split(cur_e, cur_v, fac)
                d[nv], side[nv], near[nv] = L, sv, R.near(nv.co)
                cur_e = ne if b in ne.verts else cur_e
                cur_v, done = nv, t
                n_new += 1
        return n_new

    LAST['dips'] = split_crossings({e for v in list(d) if d[v] < 1.0 for f in v.link_faces for e in f.edges})

    # 2 the mesh cut along lines at an even distance from the rim (the levels above)

    def cut_pass(scope, big=5):
        """Every edge in ``scope`` crossing a line split there, the faces joined across (up to ``big`` points)."""
        n_cut = 0
        for s in (1, 2):
            for L in levels:
                touched = set()
                for e in [e for e in scope() if e.is_valid]:
                    a, b = e.verts
                    if a not in d or b not in d or side[a] not in (0, s) or side[b] not in (0, s):
                        continue
                    da, db = d[a], d[b]
                    if (da - L) * (db - L) >= 0 or abs(da - db) < 1e-15:
                        continue
                    fac = (L - da) / (db - da)
                    if fac <= SNAP or fac >= 1 - SNAP:
                        # (the line passes next to a point: that point taken as on the line - a split there leaves a
                        # sliver face the tidy then has to find)
                        v = a if fac <= SNAP else b
                        if v not in rimset and side[v] == s:
                            d[v] = L
                            touched.update(v.link_faces)
                        continue
                    _ne, nv = bmesh.utils.edge_split(e, a, fac)
                    d[nv], side[nv] = L, s
                    near[nv] = R.near(nv.co)
                    touched.update(nv.link_faces)
                    n_cut += 1
                for f in touched:
                    if not f.is_valid or len(f.verts) > big:
                        continue                      # (a big face: the inset below)
                    for va, vb in _pairs(f, d, side, s, L, eps):
                        if not (va.is_valid and vb.is_valid):
                            continue
                        ff = [g for g in va.link_faces if g in vb.link_faces]
                        if not ff or any(vb in e.verts for e in va.link_edges if e in ff[0].edges):
                            continue                  # (already joined by an edge of the face)
                        try:
                            bmesh.utils.face_split(ff[0], va, vb)
                        except (ValueError, RuntimeError):
                            pass
        return n_cut

    LAST['cuts'] = cut_pass(lambda: {e for v in list(d) for e in v.link_edges})
    LAST['inset'] = _inset_wide(bm, layer, rimset, rim_e, frames, R, levels, d, side, near, eps)

    # 2b 0.24.365 (user's low-poly tube: long side faces leaning in spikes) a face still across a line - a long face
    #    of a low-poly part the steps above could not split (its points are moved on one side of the line only, and
    #    the whole face leaned) - cut into triangles, which always split cleanly along the line, and cut again
    def straddles(f):
        for v in f.verts:
            fill_d(v)
        ds = [d[v] for v in f.verts]
        lo, hi = min(ds), max(ds)
        if any(lo < L - eps and hi > L + eps for L in levels):
            return True
        # (all its points in the band, its middle out of it: a wall face from rim to rim)
        return lo < 1.0 - eps and rel(R.near(f.calc_center_median())) > 1.0 + 1e-3
    wide = [f for f in {f for v in list(d) if d[v] < 1.0 - eps for f in v.link_faces}
            if f.is_valid and len(f.verts) > 3 and straddles(f)]
    if wide:
        tri = bmesh.ops.triangulate(bm, faces=wide, quad_method='BEAUTY', ngon_method='BEAUTY')
        LAST['straddled'] = len(tri['faces'])
        LAST['dips'] += split_crossings({e for f in tri['faces'] if f.is_valid for e in f.edges})
        LAST['cuts'] += cut_pass(lambda: {e for v in list(d) for e in v.link_edges}, big=12)

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
    ex = bm.faces.layers.int.get(EXACT)
    if ex is None:
        ex = bm.faces.layers.int.new(EXACT)
    for v in new_co:
        for f in v.link_faces:
            f[ex] = 1
    LAST['maxmove'] = round(mv / w, 3)
    if DEBUG:
        big.sort(reverse=True)
        LAST['big'] = [(round(b[0], 3),) + b[1:] for b in big[:12]]
        LAST['sides'] = {k: sum(1 for b in big if b[2] == k) for k in (0, 1, 2)}
    return len(rim) if moved else 0
