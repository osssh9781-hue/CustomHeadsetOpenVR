"""Prototype (numpy) of the field-aligned quad remesher; the add-on runs its C port, tools_dev/native/mquad.c
(quad_field.py).  Field-aligned quads with the Instant Meshes formulas (Jakob, Tarini, Panozzo, Sorkine-Hornung 2015).

levels  - the dense mesh decimated by Mecha Lab's engine in even-spacing mode (fine ... coarse)
field   - 4-RoSy orientation + 4-PoSy position, Gauss-Seidel by colour with the paper's sequential accumulation,
          hard edges constrain both (direction along the crease, lattice line on the crease, corners pinned)
extract - collapse edges with zero lattice offset (sorted by error, never across an existing unit edge), unit
          edges become quad edges, degenerate triangles dropped, faces walked quads first, holes filled."""
import math
import time

import numpy as np

_rng = np.random.default_rng(1)


def normalize(v):
    l = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(l, 1e-30)


def dot(a, b):
    return np.einsum('ij,ij->i', a, b)


class Level:
    def __init__(self, V, F, crease_deg=30.0, min_chain=0.0):
        self.V = V.astype(np.float64)
        F = self.F = F.astype(np.int64)
        n = self.n = len(V)
        p0, p1, p2 = self.V[F[:, 0]], self.V[F[:, 1]], self.V[F[:, 2]]
        fn = np.cross(p1 - p0, p2 - p0)
        fa = 0.5 * np.linalg.norm(fn, axis=1)
        N = np.zeros((n, 3))
        A = np.zeros(n)
        for k in range(3):
            np.add.at(N, F[:, k], fn)
            np.add.at(A, F[:, k], fa / 3)
        self.N = normalize(N)
        self.A = A
        self.area = fa.sum()
        e = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
        fi = np.tile(np.arange(len(F)), 3)
        s = np.sort(e, 1)
        key = s[:, 0] * n + s[:, 1]
        order = np.argsort(key, kind='stable')
        key, s, fi = key[order], s[order], fi[order]
        first = np.r_[True, key[1:] != key[:-1]]
        self.E = s[first]
        starts = np.nonzero(first)[0]
        counts = np.diff(np.r_[starts, len(key)])
        fnu = normalize(fn)
        crease = counts != 2
        two = counts == 2
        fa_, fb_ = fi[starts[two]], fi[starts[two] + 1]
        crease[two] = dot(fnu[fa_], fnu[fb_]) < math.cos(math.radians(crease_deg))
        if min_chain > 0 and crease.any():
            ce0 = self.E[crease]
            par = np.arange(n)

            def fnd(x):
                while par[x] != x:
                    par[x] = par[par[x]]
                    x = par[x]
                return x
            for a_, b_ in ce0.tolist():
                ra, rb = fnd(a_), fnd(b_)
                if ra != rb:
                    par[rb] = ra
            root = np.array([fnd(a_) for a_ in ce0[:, 0].tolist()])
            ln = np.linalg.norm(self.V[ce0[:, 0]] - self.V[ce0[:, 1]], axis=1)
            tot = np.zeros(n)
            np.add.at(tot, root, ln)
            idx = np.nonzero(crease)[0]
            crease[idx[tot[root] < min_chain]] = False
        self.crease = crease
        cd = np.zeros((n, 3))
        cnt = np.zeros(n, np.int64)
        ce = self.E[crease]
        d = normalize(self.V[ce[:, 1]] - self.V[ce[:, 0]])
        for k, sgn in ((0, 1.0), (1, -1.0)):
            idx = ce[:, k]
            dd = d * sgn
            flip = dot(cd[idx], dd) < 0
            dd[flip] *= -1
            np.add.at(cd, idx, dd)
            np.add.at(cnt, idx, 1)
        self.ccount = cnt
        self.cdir = normalize(cd - self.N * dot(cd, self.N)[:, None])
        self.on_crease = cnt == 2
        self.crease_v = cnt > 0
        self.corner = (cnt == 1) | (cnt > 2)
        self.cq_fixed = (cnt == 1) | (cnt == 2)        # orientation constrained to the crease direction
        a = np.concatenate([self.E[:, 0], self.E[:, 1]])
        b = np.concatenate([self.E[:, 1], self.E[:, 0]])
        o = np.argsort(a, kind='stable')
        self.nb = b[o]
        self.starts = np.searchsorted(a[o], np.arange(n + 1))
        color = np.full(n, -1, np.int64)
        st, nb = self.starts, self.nb
        for v in _rng.permutation(n):
            used = set(color[nb[st[v]:st[v + 1]]].tolist())
            c = 0
            while c in used:
                c += 1
            color[v] = c
        self.colors = []
        for c in range(color.max() + 1):
            vc = np.nonzero(color == c)[0]
            deg = st[vc + 1] - st[vc]
            slots = []
            for k in range(int(deg.max())):
                sel = np.nonzero(deg > k)[0]
                slots.append((sel, nb[st[vc[sel]] + k]))
            self.colors.append((vc, slots))


# ---- Instant Meshes building blocks (extrinsic, 4-RoSy / 4-PoSy) ----------------------------------------------------

def compat_orient(q0, n0, q1, n1):
    A = (q0, np.cross(n0, q0))
    B = (q1, np.cross(n1, q1))
    s = np.stack([dot(A[0], B[0]), dot(A[0], B[1]), dot(A[1], B[0]), dot(A[1], B[1])], 1)
    k = np.argmax(np.abs(s), 1)
    a, b = k // 2, k % 2
    Aa = np.where((a == 0)[:, None], A[0], A[1])
    Bb = np.where((b == 0)[:, None], B[0], B[1])
    sg = np.sign(s[np.arange(len(k)), k])
    sg[sg == 0] = 1.0
    return Aa, Bb * sg[:, None]


def middle_point(p0, n0, p1, n1):
    n0p0, n0p1, n1p0, n1p1 = dot(n0, p0), dot(n0, p1), dot(n1, p0), dot(n1, p1)
    n0n1 = dot(n0, n1)
    den = 1.0 / (1.0 - n0n1 * n0n1 + 1e-4)
    l0 = 2.0 * (n0p1 - n0p0 - n0n1 * (n1p0 - n1p1)) * den
    l1 = 2.0 * (n1p0 - n1p1 - n0n1 * (n0p1 - n0p0)) * den
    return 0.5 * (p0 + p1) - 0.25 * (n0 * l0[:, None] + n1 * l1[:, None])


def floor_index(o, q, t, p, h):
    d = p - o
    return np.floor(dot(q, d) / h), np.floor(dot(t, d) / h)


def round4(o, q, n, p, h):
    t = np.cross(n, q)
    d = p - o
    return o + q * (np.round(dot(q, d) / h) * h)[:, None] + t * (np.round(dot(t, d) / h) * h)[:, None]


_CI = np.array([0, 1, 0, 1], float)
_CJ = np.array([0, 0, 1, 1], float)


def compat_pos(p0, n0, q0, o0, p1, n1, q1, o1, h, index=False):
    """Lattice points of o0 and o1 nearest each other around the middle of the edge (and the error)."""
    t0, t1 = np.cross(n0, q0), np.cross(n1, q1)
    mid = middle_point(p0, n0, p1, n1)
    a0, b0 = floor_index(o0, q0, t0, mid, h)
    a1, b1 = floor_index(o1, q1, t1, mid, h)
    # 4 x 4 corner pairs
    A = o0[:, None, :] + (q0[:, None, :] * (a0[:, None] + _CI[None])[:, :, None]
                          + t0[:, None, :] * (b0[:, None] + _CJ[None])[:, :, None]) * h
    B = o1[:, None, :] + (q1[:, None, :] * (a1[:, None] + _CI[None])[:, :, None]
                          + t1[:, None, :] * (b1[:, None] + _CJ[None])[:, :, None]) * h
    dd = ((A[:, :, None, :] - B[:, None, :, :]) ** 2).sum(3).reshape(len(o0), 16)
    k = np.argmin(dd, 1)
    i, j = k // 4, k % 4
    r = np.arange(len(o0))
    if index:
        s0 = np.stack([a0 + _CI[i], b0 + _CJ[i]], 1)
        s1 = np.stack([a1 + _CI[j], b1 + _CJ[j]], 1)
        return s0.astype(np.int64), s1.astype(np.int64), dd[r, k]
    return A[r, i], B[r, j]


# ---- field solve -------------------------------------------------------------------------------------------------

def smooth_orientation(L, Q, iters):
    N = L.N
    cq = L.cdir
    fix = L.cq_fixed
    for _ in range(iters):
        for vc, slots in L.colors:
            s = Q[vc].copy()
            ws = np.zeros(len(vc))
            nv = N[vc]
            for sel, js in slots:
                ni = nv[sel]
                a, b = compat_orient(s[sel], ni, Q[js], N[js])
                x = a * ws[sel][:, None] + b
                x -= ni * dot(ni, x)[:, None]
                s[sel] = normalize(x)
                ws[sel] += 1.0
            f = fix[vc]
            if f.any():
                _a, b = compat_orient(s[f], nv[f], cq[vc[f]], nv[f])
                s[f] = normalize(b - nv[f] * dot(nv[f], b)[:, None])
            Q[vc] = s
    return Q


def smooth_position(L, Q, O, h, iters):
    N, P = L.N, L.V
    cq = L.cdir
    cre, cor = L.on_crease | (L.ccount == 1), L.corner & (L.ccount != 1)
    for _ in range(iters):
        for vc, slots in L.colors:
            s = O[vc].copy()
            ws = np.zeros(len(vc))
            nv, pv, qv = N[vc], P[vc], Q[vc]
            for sel, js in slots:
                ni, pi = nv[sel], pv[sel]
                a, b = compat_pos(pi, ni, qv[sel], s[sel], P[js], N[js], Q[js], O[js], h)
                w = ws[sel][:, None]
                x = (a * w + b) / (w + 1.0)
                x -= ni * dot(ni, x - pi)[:, None]
                s[sel] = x
                ws[sel] += 1.0
            c = cre[vc]
            if c.any():                                  # lattice line on the crease
                d = pv[c] - s[c]
                cc = cq[vc[c]]
                d -= cc * dot(cc, d)[:, None]
                s[c] += d
            s = round4(s, qv, nv, pv, h)
            k = cor[vc]
            s[k] = pv[k]
            O[vc] = s
    return O


def nearest(src, dst):
    """For each point of dst the index of the nearest point of src."""
    from mathutils.kdtree import KDTree
    kd = KDTree(len(src))
    for k, p in enumerate(src.tolist()):
        kd.insert(p, k)
    kd.balance()
    return np.array([kd.find(p)[1] for p in dst.tolist()])


def solve(levels, h, orient_iters, pos_iters, log=print):
    """levels[0] fine ... levels[-1] coarsest; iterations per level, fine first.  Orientation over all levels first,
    then position (as Instant Meshes does)."""
    maps = [nearest(levels[k + 1].V, levels[k].V) for k in range(len(levels) - 1)]
    Q = None
    t0 = time.perf_counter()
    for li in range(len(levels) - 1, -1, -1):
        L = levels[li]
        if Q is None:
            Q = normalize(np.cross(L.N, _rng.normal(size=L.V.shape)))
        else:
            Q = Q[maps[li]]
            Q = normalize(Q - L.N * dot(L.N, Q)[:, None])
        Q = smooth_orientation(L, Q, orient_iters[li])
        if li:
            levels[li].Q = Q.copy()
    t1 = time.perf_counter()
    O = None
    for li in range(len(levels) - 1, -1, -1):
        L = levels[li]
        Ql = L.Q if li else Q
        if O is None:
            O = L.V.copy()
        else:
            O = O[maps[li]]
            O = O - L.N * dot(L.N, O - L.V)[:, None]
        O = smooth_position(L, Ql, O, h, pos_iters[li])
    log(f'  field: orientation {t1 - t0:.2f}s, position {time.perf_counter() - t1:.2f}s')
    return Q, O


# ---- extraction ----------------------------------------------------------------------------------------------------

def extract(L, Q, O, h, log=print):
    N, P = L.N, L.V
    i, j = L.E[:, 0], L.E[:, 1]
    qa, qb = compat_orient(Q[i], N[i], Q[j], N[j])
    s0, s1, err = compat_pos(P[i], N[i], qa, O[i], P[j], N[j], qb, O[j], h, index=True)
    ad = np.abs(s0 - s1)
    keep = ~((ad.max(1) > 1) | ((ad[:, 0] == 1) & (ad[:, 1] == 1)))
    col = keep & (ad.sum(1) == 0)
    uni = keep & ~col
    n = L.n
    adj = [set() for _ in range(n)]
    for a, b in zip(i[uni].tolist(), j[uni].tolist()):
        adj[a].add(b)
        adj[b].add(a)
    parent = list(range(n))

    def find(x):
        r = x
        while parent[r] != r:
            r = parent[r]
        while parent[x] != r:
            parent[x], x = r, parent[x]
        return r
    ncol = [0] * n
    order = np.argsort(err[col], kind='stable')
    ci, cj = i[col][order].tolist(), j[col][order].tolist()
    conflicts = 0
    for a, b in zip(ci, cj):
        ra, rb = find(a), find(b)
        if ra == rb:
            continue
        if any(find(x) == rb for x in adj[ra]):          # already one lattice step apart: keep both
            conflicts += 1
            continue
        parent[rb] = ra
        adj[ra] |= adj[rb]
        adj[rb] = set()
        ncol[ra] += ncol[rb] + 1
    roots = np.array([find(x) for x in range(n)])
    rep = np.nonzero(roots == np.arange(n))[0]
    ncol = np.array(ncol)
    avg = ncol[rep].mean()
    alive = rep[ncol[rep] > avg / 10.0]
    cid = np.full(n, -1)
    cid[alive] = np.arange(len(alive))
    vc = cid[roots]
    nc = len(alive)
    w = np.exp(-((O - P) ** 2).sum(1) / (h * h) * 9.0)
    ok = vc >= 0
    pos = np.zeros((nc, 3))
    nrm = np.zeros((nc, 3))
    ws = np.zeros(nc)
    np.add.at(pos, vc[ok], O[ok] * w[ok, None])
    np.add.at(nrm, vc[ok], N[ok] * w[ok, None])
    np.add.at(ws, vc[ok], w[ok])
    pos /= np.maximum(ws, 1e-30)[:, None]
    nrm = normalize(nrm)
    # crease / corner clusters (for the final relax)
    kind = np.zeros(nc, np.int64)
    np.maximum.at(kind, vc[ok], np.where(L.corner[ok] & (L.ccount[ok] != 1), 2, np.where(L.crease_v[ok], 1, 0)))
    cadj = [set() for _ in range(nc)]
    for r in alive.tolist():
        a = cid[r]
        for x in adj[r]:
            b = vc[x]
            if b >= 0 and b != a:
                cadj[a].add(b)
                cadj[b].add(a)
    log(f'  extract: {len(ci):,} collapses ({conflicts} conflicts), {nc:,} points, '
        f'{sum(len(c) for c in cadj) // 2:,} edges')
    remove_degenerate(cadj, pos, h)
    return faces_from_graph(cadj, pos, nrm, kind, log)


def remove_degenerate(adj, pos, h):
    """A point sitting on an edge (j, k) of its neighbours j and k: drop the edge (j, k)."""
    thresh = 0.3 * h
    for _round in range(5):
        cand = []
        for i in range(len(adj)):
            pi = pos[i]
            for jj in adj[i]:
                pj = pos[jj]
                for kk in adj[jj]:
                    if kk == i or kk not in adj[i] or jj > kk:
                        continue
                    pk = pos[kk]
                    a = np.linalg.norm(pj - pk)
                    b = np.linalg.norm(pi - pj)
                    c = np.linalg.norm(pi - pk)
                    if a > max(b, c):
                        s = 0.5 * (a + b + c)
                        hh = 2.0 * math.sqrt(max(s * (s - a) * (s - b) * (s - c), 0.0)) / max(a, 1e-30)
                        if hh < thresh:
                            cand.append((hh, i, jj, kk))
        if not cand:
            return
        cand.sort()
        changed = False
        for _hh, i, jj, kk in cand:
            if kk in adj[jj] and jj in adj[i] and kk in adj[i]:
                adj[jj].discard(kk)
                adj[kk].discard(jj)
                changed = True
        if not changed:
            return


def corner_deg(v0, v1, v2):
    d0, d1 = v0 - v1, v2 - v1
    cs = d0 @ d1 / max(np.linalg.norm(d0) * np.linalg.norm(d1), 1e-30)
    return math.degrees(math.acos(max(-1.0, min(1.0, cs))))


def join_tris(pos, faces, max_dev=40.0, max_bend=35.0):
    """Neighbouring triangles whose union is a good quad become that quad (best first)."""
    tri = [k for k, f in enumerate(faces) if len(f) == 3]
    edge = {}
    for k in tri:
        f = faces[k]
        for m in range(3):
            edge.setdefault(frozenset((f[m], f[(m + 1) % 3])), []).append(k)
    cand = []
    cb = math.cos(math.radians(max_bend))
    for e, ks in edge.items():
        if len(ks) != 2:
            continue
        f1, f2 = faces[ks[0]], faces[ks[1]]
        m = next(m for m in range(3) if frozenset((f1[m], f1[(m + 1) % 3])) == e)
        x0, x1, x2 = f1[m], f1[(m + 1) % 3], f1[(m + 2) % 3]
        y = next(v for v in f2 if v not in e)
        q = [x0, y, x1, x2]
        n1 = np.cross(pos[x1] - pos[x0], pos[x2] - pos[x0])
        n2 = np.cross(pos[x0] - pos[x1], pos[y] - pos[x1])
        if n1 @ n2 < cb * np.linalg.norm(n1) * np.linalg.norm(n2):
            continue
        dev = max(abs(corner_deg(pos[q[k - 1]], pos[q[k]], pos[q[(k + 1) % 4]]) - 90.0) for k in range(4))
        if dev < max_dev:
            cand.append((dev, ks[0], ks[1], q))
    cand.sort(key=lambda c: c[0])
    gone = set()
    new = []
    for _d, a, b, q in cand:
        if a in gone or b in gone:
            continue
        gone.update((a, b))
        new.append(q)
    return [f for k, f in enumerate(faces) if k not in gone] + new, len(new)


def faces_from_graph(adj, pos, nrm, kind, log=print):
    nc = len(adj)
    # neighbours clockwise round each point (in its tangent plane)
    nbr = []
    for c in range(nc):
        lst = list(adj[c])
        if not lst:
            nbr.append([])
            continue
        n = nrm[c]
        s = np.cross(n, [1.0, 0, 0]) if abs(n[0]) < 0.9 else np.cross(n, [0, 1.0, 0])
        s /= np.linalg.norm(s)
        t = np.cross(n, s)
        d = pos[lst] - pos[c]
        ang = np.arctan2(d @ t, d @ s)
        nbr.append([lst[k] for k in np.argsort(-ang)])
    index = [{b: k for k, b in enumerate(nb)} for nb in nbr]
    used = [[False] * len(nb) for nb in nbr]

    def walk(cur, ci, size):
        init = cur
        res = []
        while True:
            if used[cur][ci] or (size and len(res) + 1 > size):
                return None
            res.append((cur, ci))
            nxt = nbr[cur][ci]
            k = index[nxt].get(cur)
            if k is None or len(nbr[nxt]) == 1:
                return None
            cur, ci = nxt, (k + 1) % len(nbr[nxt])
            if cur == init:
                if size and len(res) != size:
                    return None
                return res
            if len(res) > 64:
                return None

    P = [p for p in pos]
    faces = []
    stats = {}

    def fill(loop):
        vs = [c for c, _k in loop]
        while len(vs) > 2:
            if len(vs) == 4 or len(vs) == 3:
                faces.append(vs)
                return
            if len(vs) > 5:                       # cut off the best-shaped quad
                best, bi = None, 0
                for st in range(len(vs)):
                    sc = 0.0
                    for k in range(4):
                        v0, v1, v2 = (P[vs[(st + k + m) % len(vs)]] for m in range(3))
                        d0, d1 = v0 - v1, v2 - v1
                        cs = d0 @ d1 / max(np.linalg.norm(d0) * np.linalg.norm(d1), 1e-30)
                        sc += abs(math.degrees(math.acos(max(-1.0, min(1.0, cs)))) - 90.0)
                    if best is None or sc < best:
                        best, bi = sc, st
                q = [vs[(bi + k) % len(vs)] for k in range(4)]
                faces.append(q)
                drop = {(bi + 1) % len(vs), (bi + 2) % len(vs)}
                vs = [v for k, v in enumerate(vs) if k not in drop]
                continue
            # 5: centre point, 5 triangles -> better: split into a quad + a triangle at the best corner
            best, bi = None, 0
            for st in range(5):
                q = [vs[(st + k) % 5] for k in range(4)]
                sc = 0.0
                for k in range(4):
                    v0, v1, v2 = P[q[k]], P[q[(k + 1) % 4]], P[q[(k + 2) % 4]]
                    d0, d1 = v0 - v1, v2 - v1
                    cs = d0 @ d1 / max(np.linalg.norm(d0) * np.linalg.norm(d1), 1e-30)
                    sc += abs(math.degrees(math.acos(max(-1.0, min(1.0, cs)))) - 90.0)
                t = (P[vs[(st + 3) % 5]], P[vs[(st + 4) % 5]], P[vs[st]])
                sc += sum(abs(corner_deg(t[k - 1], t[k], t[(k + 1) % 3]) - 60.0) for k in range(3))
                if best is None or sc < best:
                    best, bi = sc, st
            faces.append([vs[(bi + k) % 5] for k in range(4)])
            faces.append([vs[(bi + 3) % 5], vs[(bi + 4) % 5], vs[bi]])
            return

    for size in (4, 3, 5, 6, 7, 8):
        for c in range(nc):
            for k in range(len(nbr[c])):
                r = walk(c, k, size)
                if r is None:
                    continue
                for a, b in r:
                    used[a][b] = True
                stats[size] = stats.get(size, 0) + 1
                fill(r)
    holes = 0
    for c in range(nc):                              # what is left: holes up to 16 sides
        for k in range(len(nbr[c])):
            r = walk(c, k, 0)
            if r is None or len(r) > 16:
                continue
            for a, b in r:
                used[a][b] = True
            holes += 1
            fill(r)
    log(f'  faces walked {dict(sorted(stats.items()))}, holes filled {holes}')
    return pos, faces, kind


def relax(pos, faces, kind, snap, iters=2):
    """Laplacian on the surface: crease points only along crease neighbours, corners stay; snap() projects back."""
    nc = len(pos)
    nb = [set() for _ in range(nc)]
    for f in faces:
        for k in range(len(f)):
            a, b = f[k], f[(k + 1) % len(f)]
            nb[a].add(b)
            nb[b].add(a)
    for _ in range(iters):
        new = pos.copy()
        for c in range(nc):
            if kind[c] == 2 or not nb[c]:
                continue
            if kind[c] == 1:
                ns = [x for x in nb[c] if kind[x] >= 1]
                if len(ns) != 2:
                    continue
            else:
                ns = list(nb[c])
            new[c] = pos[ns].mean(0)
        pos = snap(new, kind)
    return pos


def split_all(pos, faces, kind, sharp_deg=30.0):
    """Every face into quads (quad -> 4, triangle -> 3, n-gon -> n): edge midpoints + face centre.  Midpoints of
    sharp edges are crease points (kind 1)."""
    fn = []
    for f in faces:
        p = pos[f]
        n = np.zeros(3)
        for k in range(len(f)):
            n += np.cross(p[k], p[(k + 1) % len(f)])
        fn.append(n / max(np.linalg.norm(n), 1e-30))
    ef = {}
    for fi, f in enumerate(faces):
        for k in range(len(f)):
            ef.setdefault(frozenset((f[k], f[(k + 1) % len(f)])), []).append(fi)
    cs = math.cos(math.radians(sharp_deg))
    newpos = list(pos)
    newkind = list(kind)
    emap = {}

    def mid(a, b):
        key = frozenset((a, b))
        if key not in emap:
            fs = ef[key]
            sharp = len(fs) != 2 or fn[fs[0]] @ fn[fs[1]] < cs
            emap[key] = len(newpos)
            newpos.append((pos[a] + pos[b]) * 0.5)
            newkind.append(1 if sharp else 0)
        return emap[key]
    out = []
    for f in faces:
        n = len(f)
        c = len(newpos)
        newpos.append(pos[f].mean(0))
        newkind.append(0)
        m = [mid(f[k], f[(k + 1) % n]) for k in range(n)]
        for k in range(n):
            out.append([f[k], m[k], c, m[k - 1]])
    return np.array(newpos), out, np.array(newkind)
