"""0.24.246 Auto Creature (user: "내가 작업했던 크리쳐들 - 리깅이랑 IK 프로시저럴 애니 가능해?" - "자동 크리쳐 모드").

Any creature, one mesh, any number of legs, arms, tails, tentacles - no template:

1. its shape is read as a tree: from the middle of the body the distance ALONG the surface is measured to every
   point; points at about the same distance that touch each other form a ring; the rings' middles, linked ring to
   ring, are the creature's middle lines (a Reeb graph).  Where they split is a shoulder / hip; where one ends is
   a tip.  Small bumps (spikes, fingers of detail) are pruned.
2. every branch that ends on the ground is a LEG: bones along its middle line, split where it bends (up to four),
   an IK target at its tip (its foot), a pole off its sharpest bend, the pole angle that keeps the rest pose still.
   Every other branch (tail, head, small arms, tentacles) is a CHAIN of bones that sways.  The branches between
   are the trunk (spine bones).
3. the mesh is bound (automatic weights; nearest bones where they fail - lumpy sculpts).

The rig is an ordinary Rig-tool rig (Edit Bones, Mirror, Bind, Auto Animation: the legs step in turn - neighbours
around the body opposite, so 4 legs trot-like, 6 legs tripod-like - the feet planted by IK, the body bobbing, the
chains swinging).  The analysis runs on a reduced copy (about 40k faces) - the full mesh is what gets bound.
"""
import heapq
import json
import math

import bpy
import numpy as np
from mathutils import Vector

GRAPH_FACES = 40000


# --- the mesh as a graph ------------------------------------------------------------------------------------------------

def mesh_graph(context, ob, faces=GRAPH_FACES):
    """(points (world), edges (n, 2), edge lengths) of ``ob`` as it shows, reduced to about ``faces`` faces."""
    dg = context.evaluated_depsgraph_get()
    tmp = None
    src = ob
    n = len(ob.evaluated_get(dg).data.polygons)
    if n > faces * 1.5:
        tmp = ob.copy()
        tmp.data = ob.data
        context.scene.collection.objects.link(tmp)
        m = tmp.modifiers.new('MCH Graph', 'DECIMATE')
        m.ratio = faces / float(n)
        dg = context.evaluated_depsgraph_get()
        src = tmp
    try:
        me = bpy.data.meshes.new_from_object(src.evaluated_get(dg), preserve_all_data_layers=False, depsgraph=dg)
    finally:
        if tmp is not None:
            bpy.data.objects.remove(tmp)
    try:
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        E = np.empty(len(me.edges) * 2, np.int64)
        me.edges.foreach_get('vertices', E)
    finally:
        bpy.data.meshes.remove(me)
    M = np.array(ob.matrix_world)
    V = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    E = E.reshape(-1, 2)
    L = np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1)
    return V, E, L


def _csr(n, E, L):
    a = np.concatenate([E[:, 0], E[:, 1]])
    b = np.concatenate([E[:, 1], E[:, 0]])
    w = np.concatenate([L, L])
    order = np.argsort(a, kind='stable')
    a, b, w = a[order], b[order], w[order]
    ptr = np.zeros(n + 1, np.int64)
    np.add.at(ptr, a + 1, 1)
    return np.cumsum(ptr), b, w


def dijkstra(n, csr, src):
    ptr, nb, w = csr
    dist = np.full(n, np.inf)
    pred = np.full(n, -1, np.int64)
    dist[src] = 0.0
    h = [(0.0, int(src))]
    ptr_l, nb_l, w_l = ptr.tolist(), nb.tolist(), w.tolist()
    dl = dist.tolist()
    pl = pred.tolist()
    while h:
        d, u = heapq.heappop(h)
        if d > dl[u]:
            continue
        for k in range(ptr_l[u], ptr_l[u + 1]):
            v = nb_l[k]
            nd = d + w_l[k]
            if nd < dl[v]:
                dl[v] = nd
                pl[v] = u
                heapq.heappush(h, (nd, v))
    return np.array(dl), np.array(pl)


def _labels(n, pairs):
    """Connected components over ``pairs`` (min-label propagation + pointer jumping)."""
    lab = np.arange(n)
    if not len(pairs):
        return lab
    a, b = pairs[:, 0], pairs[:, 1]
    while True:
        m = np.minimum(lab[a], lab[b])
        new = lab.copy()
        np.minimum.at(new, a, m)
        np.minimum.at(new, b, m)
        new = new[new]
        if np.array_equal(new, lab):
            return lab
        lab = new


# --- the shape as a tree ------------------------------------------------------------------------------------------------

def skeleton(V, E, L, bands=56, core=None):
    """The creature's middle lines.  Returns dict(nodes (centroids), parent, children, size, core, d, H).
    The middle of the body (the tree's root): the thickest ring of a first pass (the torso)."""
    if core is None:
        first = skeleton(V, E, L, bands, core=-1)
        k = int(np.argmax(first['radius'] * (first['band'] > 0)))
        c = first['nodes'][k]
        core = int(np.argmin(np.linalg.norm(V - c, axis=1)))
        return skeleton(V, E, L, bands, core=core)
    n = len(V)
    csr = _csr(n, E, L)
    # (the body's middle: halfway along the longest way across the surface - tip to tip)
    lo = np.lexsort((V[:, 0], V[:, 1], V[:, 2]))[0]
    d0, _p = dijkstra(n, csr, int(lo))
    d0[~np.isfinite(d0)] = -1
    A = int(np.argmax(d0))
    dA, pA = dijkstra(n, csr, A)
    dA2 = np.where(np.isfinite(dA), dA, -1)
    B = int(np.argmax(dA2))
    path, v = [], B
    while v != -1:
        path.append(v)
        v = int(pA[v])
    half = dA[B] / 2.0
    if core is None or core < 0:
        core = min(path, key=lambda u: abs(dA[u] - half))
    d, _pred = dijkstra(n, csr, int(core))
    ok = np.isfinite(d)
    dmax = float(d[ok].max())
    w = dmax / bands
    band = np.where(ok, np.floor(d / w), -1).astype(np.int64)
    same = (band[E[:, 0]] == band[E[:, 1]]) & (band[E[:, 0]] >= 0)
    lab = _labels(n, E[same])
    roots, inv = np.unique(lab[ok], return_inverse=True)
    idx = np.full(n, -1, np.int64)
    idx[np.nonzero(ok)[0]] = inv
    k = len(roots)
    cnt = np.bincount(inv, minlength=k).astype(np.float64)
    C = np.zeros((k, 3))
    for c in range(3):
        C[:, c] = np.bincount(inv, weights=V[ok][:, c], minlength=k) / np.maximum(cnt, 1)
    rad = np.bincount(inv, weights=np.linalg.norm(V[ok] - C[inv], axis=1), minlength=k) / np.maximum(cnt, 1)
    nband = np.zeros(k, np.int64)
    nband[inv] = band[ok]
    # links between rings of neighbouring bands
    cross = (band[E[:, 0]] >= 0) & (band[E[:, 1]] >= 0) & (np.abs(band[E[:, 0]] - band[E[:, 1]]) == 1)
    pa, pb = idx[E[cross, 0]], idx[E[cross, 1]]
    links = set()
    for x, y in zip(pa.tolist(), pb.tolist()):
        if x != y:
            links.add((min(x, y), max(x, y)))
    adj = [[] for _ in range(k)]
    for x, y in links:
        adj[x].append(y)
        adj[y].append(x)
    root = int(idx[core])
    parent = np.full(k, -1, np.int64)
    seen = {root}
    order = [root]
    q = [root]
    while q:
        u = q.pop(0)
        for v_ in sorted(adj[u], key=lambda t: nband[t]):
            if v_ not in seen and nband[v_] > nband[u]:
                seen.add(v_)
                parent[v_] = u
                order.append(v_)
                q.append(v_)
    children = [[] for _ in range(k)]
    for v_ in order:
        if parent[v_] >= 0:
            children[parent[v_]].append(v_)
    # the farthest point of each leaf's ring: the real tip
    tipp = {}
    for v_ in order:
        if not children[v_]:
            m = idx == v_
            pts = np.nonzero(m)[0]
            if len(pts):
                tipp[v_] = V[pts[np.argmax(d[pts])]]
    return dict(nodes=C, parent=parent, children=children, size=cnt, radius=rad, core=root, order=order, band=nband,
                tip=tipp, H=float(np.ptp(V[:, 2])), ground=float(V[:, 2].min()), V=V, w=w)


def segments(sk, min_len_share=0.1):
    """The tree cut where it splits: [(polyline (m, 3), start node, end node, is_leaf)], small side branches (a
    spike, a lump) pruned - a leaf branch shorter than ``min_len_share`` of the creature's size goes."""
    C, ch, par = sk['nodes'], sk['children'], sk['parent']
    size = max(sk['H'], float(np.ptp(sk['V'][:, 0])), float(np.ptp(sk['V'][:, 1])))
    keep = np.ones(len(C), bool)

    def chain_down(u):
        out = [u]
        while len([c for c in ch[out[-1]] if keep[c]]) == 1:
            out.append([c for c in ch[out[-1]] if keep[c]][0])
        return out
    changed = True
    while changed:                                   # (prune short leaf branches, again until none)
        changed = False
        for u in list(sk['order']):
            if not keep[u]:
                continue
            kids = [c for c in ch[u] if keep[c]]
            if len(kids) < 2:
                continue
            for c in kids:
                seg = chain_down(c)
                if any(len([g for g in ch[x] if keep[g]]) > 1 for x in seg):
                    continue
                ln = float(np.linalg.norm(np.diff(C[[u] + seg], axis=0), axis=1).sum())
                thick = float(np.mean(sk['radius'][seg])) if len(seg) else 1.0
                # (too short, or a lump - a limb is long for its thickness: a shoulder bulge is not)
                if ln < min_len_share * size or ln < 4.0 * thick or len(seg) < 4:
                    for x in seg:
                        keep[x] = False
                    stack = list(seg)
                    while stack:
                        x = stack.pop()
                        for g in ch[x]:
                            if keep[g]:
                                keep[g] = False
                                stack.append(g)
                    changed = True
    out = []
    root = sk['core']
    starts = [root]
    while starts:
        u = starts.pop()
        for c in [c for c in ch[u] if keep[c]]:
            seg = chain_down(c)
            last = seg[-1]
            leaf = not [g for g in ch[last] if keep[g]]
            pts = [C[u]] + [C[x] for x in seg]
            if leaf and last in sk['tip']:
                pts.append(sk['tip'][last])
            out.append((np.array(pts), u, last, leaf))
            if not leaf:
                starts.append(last)
    return out


def _resample(P, n):
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    u = np.concatenate([[0], np.cumsum(seg)])
    if u[-1] <= 1e-12:
        return np.repeat(P[:1], n + 1, axis=0)
    t = np.linspace(0, u[-1], n + 1)
    return np.stack([np.interp(t, u, P[:, k]) for k in range(3)], axis=1)


def _smooth(P, it=2):
    P = P.copy()
    for _ in range(it):
        P[1:-1] = 0.25 * P[:-2] + 0.5 * P[1:-1] + 0.25 * P[2:]
    return P


def joints_of(P, kind, size):
    """Joint points along a branch: a leg split where it bends (2 - 4 bones), a chain evenly."""
    from .rigging import bends
    P = _smooth(_resample(P, 40))
    L = float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum())
    if kind == 'LEG':
        # (up to two joints - three bones: more, nearly in line, and IK shuffles them; at least 15 % apart)
        bd = sorted(bends(P, 2, gap=6, lo=0.15, hi=0.88), key=lambda x: x[0])
        idx = [i for i, a in bd if a > 20.0]
        if not idx:
            idx = [len(P) // 2]
        pts = [P[0]] + [P[i] for i in idx] + [P[-1]]
        return np.array(pts), L
    nb = int(max(3, min(8, round(L / max(1e-6, 0.08 * size)))))
    return _resample(P, nb), L


# --- the rig --------------------------------------------------------------------------------------------------------------

def build(context, body):
    """The Auto Creature armature for ``body`` (not bound).  Returns (armature, info)."""
    from . import rigging as rg
    V, E, L = mesh_graph(context, body)
    sk = skeleton(V, E, L)
    segs = segments(sk)
    H, ground = sk['H'], sk['ground']
    size = max(H, float(np.ptp(V[:, 0])), float(np.ptp(V[:, 1])))
    arm = rg._new_armature(context, body.name + '_Rig')
    arm[rg.RIG_KEY] = 'AUTO'
    arm.data.display_type = 'STICK'                  # (long limbs: thick bones would hide the creature)
    arm[rg.BODY_KEY] = body.name
    core = sk['nodes'][sk['core']]
    legs, chains, trunk = [], [], []
    end_bone = {}                                    # tree node -> the bone that ends there
    with rg._Edit(context, arm) as ebs:
        rb = rg._bone(ebs, 'root', (core[0], core[1], ground), (core[0], core[1] - 0.15 * size, ground), deform=False)
        bb = rg._bone(ebs, 'body', core, core + np.array([0, 0, 0.06 * size]), rb)
        end_bone[sk['core']] = bb.name
        li = ci = ti = 0
        for P, u, last, leaf in segs:
            tipz = float(P[-1][2])
            onground = leaf and tipz - ground < 0.05 * H
            kind = 'LEG' if onground else ('CHAIN' if leaf else 'TRUNK')
            J, ln = joints_of(P, kind, size)
            if kind == 'LEG':
                li += 1
                base = f'leg{li}'
                legs.append(base)
            elif kind == 'CHAIN':
                ci += 1
                base = f'limb{ci}'
                chains.append(base)
            else:
                ti += 1
                base = f'trunk{ti}'
                trunk.append(base)
            parent = end_bone.get(u, bb.name)
            prev = parent
            names = []
            for i in range(len(J) - 1):
                b = rg._bone(ebs, f'{base}.{i + 1:02d}', J[i], J[i + 1], prev, connect=i > 0)
                names.append(b.name)
                prev = b.name
            end_bone[last] = prev
            if kind == 'LEG':
                tip = J[-1]
                fwd = np.array([0.0, -1.0, 0.0])
                foot = rg._bone(ebs, f'{base}.foot', tip, tip + fwd * 0.03 * size, prev, connect=True)
                # the pole: off the sharpest bend, the way the leg bends
                line_a, line_b = J[0], J[-1]
                mid = max(J[1:-1], key=lambda p: np.linalg.norm(np.cross(p - line_a, line_b - line_a))) if len(J) > 2 \
                    else 0.5 * (line_a + line_b)
                ab = line_b - line_a
                t = float((mid - line_a) @ ab / max(ab @ ab, 1e-12))
                off = mid - (line_a + t * ab)
                if np.linalg.norm(off) < 1e-4 * size:
                    off = np.array([0.0, -1.0, 0.0])
                off = off / np.linalg.norm(off) * 0.35 * ln
                lower = names[-1]
                rg._limb_ik_bones(ebs, lower, foot.name, tip, tip + fwd * 0.03 * size, mid, tuple(off), 'root')
    arm['mch_legs'] = json.dumps(legs)
    arm['mch_chains'] = json.dumps(chains)
    arm['mch_x0'] = float(core[0])
    offs = {}
    for base in legs:
        lower = sorted(n for n in arm.data.bones.keys() if n.startswith(base + '.') and n[len(base) + 1:].isdigit())[-1]
        b = arm.data.bones.get(lower + '_pole')
        if b is not None:
            offs[lower] = list(b.head_local - arm.data.bones[lower].head_local)
    arm['mch_pole_off'] = offs
    lens = []
    for base in legs:
        names = sorted(n for n in arm.data.bones.keys() if n.startswith(base + '.') and n[len(base) + 1:].isdigit())
        lower = names[-1]
        err, _deg = rg._limb_ik(context, arm, lower, base + '.foot', len(names))
        if len(names) > 2 and err > 0.01:
            # (three bones nearly in a plane: IK can shuffle them - the rest pose would move; the upper bone is
            #  left to follow the body, IK on the lower two)
            pb = arm.pose.bones[lower]
            for c in [c for c in pb.constraints if c.type in {'IK', 'COPY_ROTATION'}]:
                pb.constraints.remove(c)
            fb = arm.pose.bones[base + '.foot']
            for c in [c for c in fb.constraints if c.type == 'COPY_ROTATION']:
                fb.constraints.remove(c)
            rg._limb_ik(context, arm, lower, base + '.foot', 2)
        lens.append(sum(arm.data.bones[n].length for n in names))
    arm['mch_leg_len'] = float(np.min(lens)) if lens else 0.3 * H     # (the stride the shortest leg can make)
    rg.controls(arm)
    return arm, dict(legs=len(legs), chains=len(chains), trunk=len(trunk), bones=len(arm.data.bones),
                     graph_points=len(V))
