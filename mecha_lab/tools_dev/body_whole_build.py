"""0.24.187 one-piece bodies (user: "크리쳐 바디 하나 더 보낼 테니까 그것도 아까 인물 한 것처럼 리깅해서 넣어 줘, 그리고 기존에 보낸
크리쳐도 리깅해 주고"): each body made light and stored whole WITH its bones and each point's bone.

    <blender python> body_whole_build.py human <body02.fbx>
    <blender python> body_whole_build.py creature <body06.fbx>          (no parts: the joints and the wrists / ankles found)
    <blender python> body_whole_build.py creature2 <body4.fbx> <hand.fbx>   (no parts: the joints found on the mesh;
                                                                          hand.fbx: its palms / soles mark wrists, ankles)

writes addon/mecha_lab/body_kits/<kind>_whole.npz: Body_Q / Body_box (16-bit points), Body_N, Body_L, Body_B (each
point's bone, an index into the bones), 'meta' (JSON: the bones - name, slot, side, parent, head, tail).
"""
import json
import math
import os
import sys

import bpy
import bmesh  # noqa: E402
import numpy as np
from mathutils import Vector, kdtree
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'addon', 'mecha_lab', 'body_kits')
FACES = 40000
SIDED = ('Shoulder', 'UpperArm', 'Forearm', 'Hand', 'Thigh', 'Shin', 'Foot')
ORDER = ('Pelvis', 'Waist', 'Chest', 'Neck', 'Head', 'Shoulder', 'UpperArm', 'Forearm', 'Hand', 'Thigh', 'Shin', 'Foot')
PARENT = {'Waist': 'Pelvis', 'Chest': 'Waist', 'Neck': 'Chest', 'Head': 'Neck', 'Shoulder': 'Chest',
          'UpperArm': 'Shoulder', 'Forearm': 'UpperArm', 'Hand': 'Forearm', 'Thigh': 'Pelvis', 'Shin': 'Thigh',
          'Foot': 'Shin'}


def read(path, faces=FACES):
    """(V, face sizes, corners, bmesh) of every mesh of the file joined, light; raw coordinates."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    obs = [o for o in bpy.data.objects if o.type == 'MESH']
    bm = bmesh.new()
    for ob in obs:
        me = ob.data.copy()
        me.transform(ob.matrix_world)
        bm.from_mesh(me)
    me = bpy.data.meshes.new('all')
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new('all', me)
    bpy.context.scene.collection.objects.link(ob)
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    md = ob.modifiers.new('D', 'DECIMATE')
    md.ratio = min(faces / tris, 1.0)
    dg = bpy.context.evaluated_depsgraph_get()
    m2 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    V = np.array([v.co[:] for v in m2.vertices])
    N = np.array([len(p.vertices) for p in m2.polygons], np.uint8)
    L = np.array([i for p in m2.polygons for i in p.vertices], np.int32)
    return V, N, L


def normalise(V):
    lo, hi = V.min(0), V.max(0)
    H = hi[2] - lo[2]
    shift = np.array([(lo[0] + hi[0]) / 2, 0.0, lo[2]])
    return (V - shift) / H, shift, H


def kit_bones(kit, V):
    """The bones from a part-split kit's joints (the same sculpt) and each point's bone from the part it lies on."""
    with np.load(os.path.join(OUT, kit + '.npz'), allow_pickle=False) as z:
        parts = {p['name']: dict(p) for p in json.loads(str(z['meta']))['parts']}
        for n in parts:
            if n + '_Q' in z:
                lo, hi = z[n + '_box'].astype(np.float64)
                parts[n]['V'] = z[n + '_Q'].astype(np.float64) / 65535.0 * (hi - lo) + lo + np.array(parts[n]['pivot'])
            else:
                parts[n]['V'] = z[n + '_V'].astype(np.float64) + np.array(parts[n]['pivot'])

    def P(name, key):
        return np.array(parts[name][key], float)
    has_head = 'Head' in parts
    one_arm = 'Arm.L' in parts
    bones = {}
    tp, te = P('Torso', 'pivot'), P('Torso', 'end')
    neck0 = tp + (te - tp) * 0.74 if has_head else te            # (where the neck starts)
    mid = tp + (neck0 - tp) * 0.45
    bones['Pelvis'] = (P('Pelvis', 'pivot'), P('Pelvis', 'end'))
    bones['Waist'] = (tp, mid)
    bones['Chest'] = (mid, neck0)
    if has_head:
        bones['Neck'] = (neck0, P('Head', 'pivot'))
        bones['Head'] = (P('Head', 'pivot'), P('Head', 'end'))
    else:
        hb = np.array([0.0, te[1] - 0.008, 0.868])
        bones['Neck'] = (te, hb)
        bones['Head'] = (hb, np.array([0.0, te[1] - 0.02, V[:, 2].max() - 0.01]))
    elbow = {}
    for sd in ('L', 'R'):
        s = '.' + sd
        arm = 'Arm' + s if one_arm else 'UpperArm' + s
        a0 = P(arm, 'pivot')
        bones['Shoulder' + s] = (np.array([a0[0] * 0.22, a0[1] - 0.01, a0[2] + 0.012]), a0)
        if one_arm:                                   # (a one-piece arm: its elbow in the middle of its length)
            w = P(arm, 'end')
            ax = (w - a0) / np.linalg.norm(w - a0)
            t = (parts[arm]['V'] - a0) @ ax / np.linalg.norm(w - a0)
            e = parts[arm]['V'][(t > 0.44) & (t < 0.52)].mean(0)
            elbow[sd] = (e, ax)
            bones['UpperArm' + s] = (a0, e)
            bones['Forearm' + s] = (e, w)
        else:
            bones['UpperArm' + s] = (a0, P(arm, 'end'))
            bones['Forearm' + s] = (P('Forearm' + s, 'pivot'), P('Forearm' + s, 'end'))
        bones['Hand' + s] = (P('Hand' + s, 'pivot'), P('Hand' + s, 'end'))
        km = (P('Knee' + s, 'pivot') + P('Knee' + s, 'end')) * 0.5
        bones['Thigh' + s] = (P('Thigh' + s, 'pivot'), km)
        bones['Shin' + s] = (km, P('Foot' + s, 'pivot'))
        bones['Foot' + s] = (P('Foot' + s, 'pivot'), P('Foot' + s, 'end'))
    # each point's bone: the part it lies on
    pts, lab = [], []
    for n, p in parts.items():
        st = max(1, len(p['V']) // 4000)
        pts.append(p['V'][::st])
        lab += [n] * len(p['V'][::st])
    pts = np.concatenate(pts)
    kd = kdtree.KDTree(len(pts))
    for i, q in enumerate(pts):
        kd.insert(q, i)
    kd.balance()
    out = []
    for v in V:
        part = lab[kd.find(v)[1]]
        base, _d, sd = part.partition('.')
        s = ('.' + sd) if sd else ''
        if base == 'Knee':
            m_ = bones['Shin' + s][0]
            base = 'Shin' if float((v - m_) @ (bones['Shin' + s][1] - m_)) > 0 else 'Thigh'
        elif base == 'Arm':
            e, ax = elbow[sd]
            base = 'Forearm' if float((v - e) @ ax) > 0 else 'UpperArm'
        elif base == 'Torso':
            nk0, nk1 = bones['Neck']
            if not has_head and v[2] > nk1[2]:
                base = 'Head'
            elif float((v - nk0) @ (nk1 - nk0)) > 0 and abs(v[0]) < 0.06:
                base = 'Neck'
            else:
                base = 'Chest' if float((v - mid) @ (neck0 - mid)) > 0 else 'Waist'
                if abs(v[0]) > 0.03:
                    sd2 = 'L' if v[0] > 0 else 'R'
                    a_, b_ = bones['Shoulder.' + sd2]
                    ab = b_ - a_
                    tt = min(max(float((v - a_) @ ab) / float(ab @ ab), 0.0), 1.0)
                    if float(np.linalg.norm(v - (a_ + ab * tt))) < 0.062 and tt > 0.25 and v[2] > a_[2] - 0.09:
                        base, s = 'Shoulder', '.' + sd2
        out.append(base + s)
    return bones, out


def clusters(x, gap=0.012):
    """Sorted 1D values split where they jump: [(lo, hi, indices)]."""
    o = np.argsort(x)
    xs = x[o]
    cut = np.nonzero(np.diff(xs) > gap)[0]
    out, a = [], 0
    for c in list(cut) + [len(xs) - 1]:
        out.append((xs[a], xs[c], o[a:c + 1]))
        a = c + 1
    return out


def found_bones(V, N, L, marks):
    """No parts: the joints found on the mesh (it stands, arms down beside it) - slices up it, the limbs the clumps
    beside the body's own; ``marks``: {'wrist', 'ankle', 'toe'} points (left side) from the user's palm / sole parts."""
    R = V[V[:, 0] > 0]
    zs = np.linspace(0.02, 0.98, 97)
    # the crotch: the lowest height where the body's middle is filled
    mid_n = np.array([((np.abs(V[:, 0]) < 0.008) & (np.abs(V[:, 2] - z) < 0.006)).sum() for z in zs])
    crotch = float(zs[np.nonzero((mid_n > 4) & (zs > 0.2))[0][0]])
    wrist, ankle, toe = (np.array(marks[k], float) for k in ('wrist', 'ankle', 'toe'))
    leg, arm, body, leg_sl = [], [], [], []
    for z in zs:
        m = np.abs(R[:, 2] - z) < 0.006
        if m.sum() < 6:
            continue
        P = R[m]
        cl = clusters(P[:, 0])
        if z < crotch:                                # (below the crotch: the leg is the inner clump)
            inner = cl[0][2]
            leg.append(P[inner].mean(0))
            leg_sl.append((z, float(cl[0][1]), len(cl), float(R[:, 0][m].max())))
            if len(cl) > 1 and z > wrist[2] - 0.02:
                arm.append(P[cl[-1][2]].mean(0))
        else:
            body.append((z, P[cl[0][2]], cl))
            if len(cl) > 1:
                arm.append(P[cl[-1][2]].mean(0))
    leg = np.array(leg)
    arm = np.array([a for a in arm if a[2] >= wrist[2] - 0.01])
    armpit = arm[:, 2].max()                          # (the highest slice where the arm is still its own clump)
    # the leg: hip above the crotch on its line, the knee where it stands furthest off the hip - ankle line
    hip = np.array([leg[-1][0] * 0.9, leg[-1][1], crotch + 0.035])
    lg = leg[leg[:, 2] > ankle[2] + 0.02]
    ax = (ankle - hip) / np.linalg.norm(ankle - hip)
    off = np.linalg.norm((lg - hip) - np.outer((lg - hip) @ ax, ax), axis=1)
    tt = (lg - hip) @ ax / np.linalg.norm(ankle - hip)
    ok = (tt > 0.4) & (tt < 0.75)
    knee = lg[ok][np.argmax(off[ok])]
    # the arm: the shoulder joint inside the body's top corner over the armpit, the elbow as the knee
    top = V[(V[:, 0] > 0) & (V[:, 2] > armpit) & (V[:, 2] < armpit + 0.1)]
    sh = np.array([np.quantile(top[:, 0], 0.9) - 0.035, top[:, 1].mean(), armpit + 0.035])
    ar = arm[arm[:, 2] > wrist[2] + 0.02]
    ax = (wrist - sh) / np.linalg.norm(wrist - sh)
    off = np.linalg.norm((ar - sh) - np.outer((ar - sh) @ ax, ax), axis=1)
    tt = (ar - sh) @ ax / np.linalg.norm(wrist - sh)
    ok = (tt > 0.3) & (tt < 0.7)
    elbow = ar[ok][np.argmax(off[ok])] if ok.any() else (sh + wrist) * 0.5
    # the body: its middle line up from the pelvis; the neck where it is narrowest above the shoulders
    cen = np.array([[0.0, P[:, 1].mean(), z] for z, P, _c in body])
    wid = np.array([np.ptp(P[:, 0]) for _z, P, _c in body])
    zb = cen[:, 2]
    up = zb > sh[2] + 0.02
    i_n = np.nonzero(up)[0][np.argmin(wid[up][:max(3, int(up.sum() * 0.6))])]
    neck_mid = cen[i_n]
    pel = np.array([0.0, np.interp(crotch + 0.035, zb, cen[:, 1]), crotch + 0.035])
    chest_top = np.array([0.0, np.interp(sh[2] + 0.02, zb, cen[:, 1]), sh[2] + 0.02])
    waist_top = pel + (chest_top - pel) * 0.5
    waist_top[1] = np.interp(waist_top[2], zb, cen[:, 1])
    head_base = neck_mid + (neck_mid - chest_top) * 0.35
    Hd = V[V[:, 2] > head_base[2] - 0.01]
    far = Hd[np.argmax(np.linalg.norm(Hd - head_base, axis=1))]
    fingers = V[(V[:, 0] > 0) & (np.linalg.norm(V - wrist, axis=1) < 0.2) & (V[:, 2] < wrist[2])]
    tip = fingers[np.argmax(np.linalg.norm(fingers - wrist, axis=1))] if len(fingers) else wrist - (0, 0, 0.08)
    hand_end = wrist + (tip - wrist) * 0.6
    L_ = {'Pelvis': (pel - (0, 0, 0.05), pel), 'Waist': (pel, waist_top), 'Chest': (waist_top, chest_top),
          'Neck': (chest_top, head_base), 'Head': (head_base, head_base + (far - head_base) * 0.9),
          'Shoulder.L': (np.array([sh[0] * 0.25, sh[1] - 0.005, sh[2] + 0.01]), sh), 'UpperArm.L': (sh, elbow),
          'Forearm.L': (elbow, wrist), 'Hand.L': (wrist, hand_end), 'Thigh.L': (hip, knee), 'Shin.L': (knee, ankle),
          'Foot.L': (ankle, toe)}
    bones = {}
    for n, (a, b) in L_.items():
        bones[n] = (np.array(a, float), np.array(b, float))
        if n.endswith('.L'):
            bones[n[:-1] + 'R'] = (np.array(a, float) * (-1, 1, 1), np.array(b, float) * (-1, 1, 1))
    # each point's bone.  First which LIMB it is of, along the skin: from a ring of skin round the middle of each limb
    # bone and from the body's middle line, every point takes the limb it is nearest to OVER THE SURFACE (a hand
    # hanging beside the thigh is far from it that way) - then, within the limb, the bone nearest to it.
    import heapq
    nb = [[] for _ in V]
    k = 0
    for n_ in N:
        n_ = int(n_)
        f = [int(x) for x in L[k:k + n_]]
        for a_, b_ in zip(f, f[1:] + f[:1]):
            nb[a_].append(b_)
            nb[b_].append(a_)
        k += n_

    def seg_d(P, n):
        a_, b_ = bones[n]
        ab = b_ - a_
        t = ((P - a_) @ ab) / float(ab @ ab)
        return np.linalg.norm(P - (a_ + np.outer(np.clip(t, 0, 1), ab)), axis=1), t
    VNs = np.zeros_like(V)
    k = 0
    for n_ in N:
        n_ = int(n_)
        f = L[k:k + n_]
        VNs[f] += np.cross(V[f[1]] - V[f[0]], V[f[2]] - V[f[0]])
        k += n_
    chains = {'trunk': ['Pelvis', 'Waist', 'Chest', 'Neck', 'Head', 'Shoulder.L', 'Shoulder.R']}
    for sd in 'LR':
        chains['arm' + sd] = [f'{b}.{sd}' for b in ('UpperArm', 'Forearm', 'Hand')]
        chains['leg' + sd] = [f'{b}.{sd}' for b in ('Thigh', 'Shin', 'Foot')]
    seed = {}
    for cn, bl in chains.items():
        if cn == 'trunk':
            zlo, zhi = bones['Pelvis'][0][2], bones['Head'][1][2]
            for i in np.nonzero((np.abs(V[:, 0]) < 0.02) & (V[:, 2] > zlo))[0]:
                seed[int(i)] = cn
            continue
        sgn = 1.0 if cn.endswith('L') else -1.0
        for n in bl:
            d_, t_ = seg_d(V, n)
            a_, b_ = bones[n]
            Qn = a_ + np.outer(np.clip(t_, 0, 1), b_ - a_)
            behind = ((V - Qn) * VNs).sum(1) > 0      # (its own skin: the bone lies behind it - not the flank's beside)
            m = (np.abs(t_ - 0.5) < 0.2) & (V[:, 0] * sgn > 0) & (d_ < 0.09) & behind
            if m.sum() < 8:
                continue
            lim = np.quantile(d_[m], 0.25) * 1.6
            for i in np.nonzero(m & (d_ <= lim))[0]:
                seed[int(i)] = cn
    for z_, P_, _cl in body:                          # (the body's own skin where the arm hangs apart beside it)
        xm = float(P_[:, 0].max()) - 0.004
        for i in np.nonzero((np.abs(V[:, 2] - z_) < 0.006) & (np.abs(V[:, 0]) < xm))[0]:
            if len(_cl) > 1:
                seed[int(i)] = 'trunk'
    arm_low = min(float(V[i, 2]) for i, c_ in seed.items() if c_.startswith('arm')) - 0.03
    for z_, xhi, ncl, _xm in leg_sl:                  # (the leg's own skin where the hand hangs APART beside it, and
        if ncl > 1 or z_ < arm_low:                   #  below the hands: sure to be the leg's)
            for i in np.nonzero((np.abs(V[:, 2] - z_) < 0.006) & (np.abs(V[:, 0]) <= xhi + 1e-6))[0]:
                seed[int(i)] = 'legL' if V[i, 0] > 0 else 'legR'
    VNu = VNs / np.maximum(np.linalg.norm(VNs, axis=1), 1e-12)[:, None]
    dist = {i: 0.0 for i in seed}
    own = dict(seed)
    hp = [(0.0, i) for i in seed]
    heapq.heapify(hp)
    while hp:
        da, a_ = heapq.heappop(hp)
        if da > dist.get(a_, 1e9):
            continue
        for b_ in nb[a_]:
            # (over a sharp fold - where a hand lies grown onto the thigh - is a long way round)
            db = da + float(np.linalg.norm(V[a_] - V[b_])) * (25.0 if float(VNu[a_] @ VNu[b_]) < 0.35 else 1.0)
            if db < dist.get(b_, 1e9):
                dist[b_] = db
                own[b_] = own[a_]
                heapq.heappush(hp, (db, b_))
    # a hand grown onto the thigh: which skin there is the thigh's, which the hand's - by the thigh's own surface
    # (how far out it lies round the thigh bone, read from the leg's sure skin above and below): on it, the thigh's;
    # standing out from it, the hand's
    moved = [0, 0]
    for sd in 'LR':
        a_, b_ = bones['Thigh.' + sd]
        ax = (b_ - a_) / np.linalg.norm(b_ - a_)
        e1 = np.cross(ax, [0.0, 1.0, 0.0])
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(ax, e1)
        rel = V - a_
        tl = rel @ ax
        rv = rel - np.outer(tl, ax)
        rr = np.linalg.norm(rv, axis=1)
        th = np.arctan2(rv @ e2, rv @ e1)
        emb = np.stack([tl, 0.05 * np.cos(th), 0.05 * np.sin(th)], 1)
        sure = [i for i, c_ in seed.items() if c_ == 'leg' + sd and -0.05 < tl[i] < 0.3]
        if len(sure) < 20:
            continue
        kd = kdtree.KDTree(len(sure))
        for j, i in enumerate(sure):
            kd.insert(emb[i], j)
        kd.balance()
        sgn = 1.0 if sd == 'L' else -1.0
        for vi in np.nonzero((V[:, 0] * sgn > 0) & (tl > -0.03) & (tl < 0.28) & (rr < 0.14))[0]:
            vi = int(vi)
            cn = own.get(vi, 'trunk')
            if vi in seed or cn == 'trunk':
                continue
            ref = float(np.mean([rr[sure[j]] for _c, j, _d in kd.find_n(emb[vi], 6)]))
            if cn == 'arm' + sd and rr[vi] <= ref + 0.005:
                own[vi] = 'leg' + sd
                moved[0] += 1
            elif cn == 'leg' + sd and rr[vi] > ref + 0.008:
                own[vi] = 'arm' + sd
                moved[1] += 1
    print('at the thigh: skin given back to the leg', moved[0], ', to the hand', moved[1])
    out = []
    counts = {}
    for vi, v in enumerate(V):
        cn = own.get(vi, 'trunk')
        if cn != 'trunk':                             # (before the limb's first joint: the body's)
            a_, b_ = bones[chains[cn][0]]
            if float((v - a_) @ (b_ - a_)) < 0:
                cn = 'trunk'
        best, bd = None, 1e9
        for n in chains[cn]:
            if (n.endswith('.L') and v[0] < -0.004) or (n.endswith('.R') and v[0] > 0.004):
                continue
            d_ = float(seg_d(v[None], n)[0][0])
            if d_ < bd:
                best, bd = n, d_
        out.append(best)
        counts[cn] = counts.get(cn, 0) + 1
    print('limbs', counts)
    return bones, out


def add_digits(V, N, L, bones, lab):
    """Fingers and toes (user: "손이나 발 쪽도 세부적으로 조절 가능하게 리깅을"): found on the mesh - over the hand (foot),
    how far each point is from the wrist ALONG THE SKIN; the far ends are the tips, and coming back from them the
    fingers are the pieces that stay apart until they meet at the webs.  Each finger: 3 bones (a toe: 2), its points
    theirs.  The left side is found, the right is its mirror.  Returns the digits' records (for the meta)."""
    import heapq
    nb = [[] for _ in V]
    k = 0
    for n_ in N:
        n_ = int(n_)
        f = [int(x) for x in L[k:k + n_]]
        for a, b in zip(f, f[1:] + f[:1]):
            nb[a].append(b)
            nb[b].append(a)
        k += n_
    VN = np.zeros_like(V)                              # (each point's outward direction)
    k = 0
    for n_ in N:
        n_ = int(n_)
        f = L[k:k + n_]
        VN[f] += np.cross(V[f[1]] - V[f[0]], V[f[2]] - V[f[0]])
        k += n_
    recs = []
    for slot, pre, nseg, minfrac, mindot in (('Hand', 'Finger', 3, 0.2, -0.3),):
        name = slot + '.L'
        head, tail = bones[name]
        ln = float(np.linalg.norm(tail - head))
        dirv = (tail - head) / ln
        region = {i for i, x in enumerate(lab) if x == name}
        if slot == 'Hand':                            # (fingertips beside the thigh got another bone: back to the hand)
            hops = {i: 0 for i in region}
            st = list(region)
            own = sorted(region)
            kd0 = kdtree.KDTree(len(own))
            for j, i in enumerate(own):
                kd0.insert(V[i], j)
            kd0.balance()
            while st:
                a = st.pop()
                for b in nb[a]:
                    if b in hops or V[b, 0] <= 0 or float((V[b] - head) @ dirv) <= 0 or hops[a] >= 0 or \
                            float(np.linalg.norm(V[b] - head)) > 3.2 * ln:
                        continue
                    near = kd0.find_range(V[b], 0.02)
                    if not near:
                        continue
                    cen = np.mean([V[own[j]] for _c, j, _d in near], 0)
                    if float((cen - V[b]) @ VN[b]) > 0:   # (it faces the hand: the thigh's skin beside it, not the hand's)
                        continue
                    hops[b] = hops[a] + 1
                    st.append(b)
            region = set(hops)
            for i in region:
                lab[i] = name
        along = {i: float((V[i] - head) @ dirv) for i in region}
        src = [i for i in region if along[i] < 0.12 * ln] or sorted(region, key=along.get)[:max(4, len(region) // 20)]
        d = {i: 0.0 for i in src}
        hp = [(0.0, i) for i in src]
        while hp:
            da, a = heapq.heappop(hp)
            if da > d.get(a, 1e9):
                continue
            for b in nb[a]:
                if b in region:
                    db = da + float(np.linalg.norm(V[a] - V[b]))
                    if db < d.get(b, 1e9):
                        d[b] = db
                        heapq.heappush(hp, (db, b))
        for i in region:
            d.setdefault(i, 0.0)
        dmax = max(d.values())
        minlen = dmax * minfrac
        par, comp, done, found = {}, {}, set(), []

        def find(a):
            while par[a] != a:
                par[a] = par[par[a]]
                a = par[a]
            return a
        for v in sorted(region, key=d.get, reverse=True):
            par[v] = v
            comp[v] = {'birth': d[v], 'tip': v, 'm': [v], 'trunk': False}
            done.add(v)
            for w in nb[v]:
                if w not in done:
                    continue
                ra, rb = find(v), find(w)
                if ra == rb:
                    continue
                A, B = comp[ra], comp[rb]
                lv = d[v]
                sa = (not A['trunk']) and A['birth'] - lv > minlen
                sb = (not B['trunk']) and B['birth'] - lv > minlen
                trunk = A['trunk'] or B['trunk']
                for C, sc, other in ((A, sa, sb or B['trunk']), (B, sb, sa or A['trunk'])):
                    if sc and other:                  # (two fingers meet, or a finger meets the hand: it ends here)
                        found.append({'m': list(C['m']), 'b': lv, 't': C['birth'], 'tip': C['tip']})
                        trunk = True
                if len(A['m']) < len(B['m']):
                    ra, rb, A, B = rb, ra, B, A
                A['m'] += B['m']
                if B['birth'] > A['birth']:
                    A['birth'], A['tip'] = B['birth'], B['tip']
                A['trunk'] = trunk
                par[rb] = ra
                del comp[rb]
        print(slot, 'region', len(region), 'sources', len(src), 'far', round(dmax, 4), 'bone', round(ln, 4), 'pieces', [(round(f['t'] - f['b'], 3), len(f['m'])) for f in found])
        digits = []
        for f in found:
            M = np.array(f['m'])
            fr = (np.array([d[i] for i in M]) - f['b']) / max(f['t'] - f['b'], 1e-9)
            J = []
            for q in range(nseg + 1):
                m = (fr < 0.14) if q == 0 else (fr > 0.9) if q == nseg else (np.abs(fr - q / nseg) < 0.1)
                if not m.any():
                    m = np.abs(fr - q / nseg) < 0.25
                J.append(V[M[m]].mean(0))
            J[-1] = J[-1] + (J[-1] - J[-2]) * 0.15
            vec = J[-1] - J[0]
            if float(vec @ dirv) / max(float(np.linalg.norm(vec)), 1e-9) < mindot:
                continue                              # (the heel is not a toe)
            digits.append({'M': M, 'fr': fr, 'J': J, 'len': f['t'] - f['b']})
        digits = sorted(digits, key=lambda g: -g['len'])[:6]
        if not digits:
            print(slot, 'no digits found')
            continue
        fing = set(int(i) for g in digits for i in g['M'])
        palm = np.array([V[i] for i in region if i not in fing] or [V[i] for i in region])
        _u, _s, vt = np.linalg.svd(palm - palm.mean(0), full_matrices=False)
        if slot == 'Hand':                            # (the palm's inside: where the fingers lean)
            nrm = vt[2] - dirv * float(vt[2] @ dirv)
            nrm /= np.linalg.norm(nrm)
            lean = sum(float((g['J'][-1] - g['J'][0]) @ nrm) for g in digits)
            if lean < 0 or (abs(lean) < 1e-4 and nrm[1] > 0):
                nrm = -nrm
        else:                                         # (toes curl down)
            nrm = np.array([0.0, 0.0, -1.0])
        lat = np.cross(dirv, nrm)
        base_c = np.mean([g['J'][0] for g in digits], 0)
        us = np.array([float((g['J'][0] - base_c) @ lat) for g in digits])
        order = np.argsort(us)
        umax = max(float(np.abs(us).max()), 1e-9)
        for rank, gi in enumerate(order):
            g = digits[gi]
            seg = np.clip((g['fr'] * nseg).astype(int), 0, nseg - 1)
            for q in range(nseg):
                bn = f'{pre}{rank + 1}{"abc"[q]}'
                for i in g['M'][seg == q]:
                    lab[int(i)] = bn + '.L'
                for sd, mir in (('L', np.array([1.0, 1.0, 1.0])), ('R', np.array([-1.0, 1.0, 1.0]))):
                    bones[f'{bn}.{sd}'] = (g['J'][q] * mir, g['J'][q + 1] * mir)
                    recs.append({'name': f'{bn}.{sd}', 'slot': pre, 'side': sd,
                                 'parent': (f'{pre}{rank + 1}{"abc"[q - 1]}.{sd}' if q else f'{slot}.{sd}'),
                                 'z': [round(float(x), 4) for x in nrm * mir], 'u': round(float(us[gi] / umax), 3),
                                 'seg': q})
        print(slot, 'digits', len(digits), 'lengths', [round(float(g['len']), 3) for g in digits], 'points',
              [len(g['M']) for g in digits])
    # the toes: the foot's front as one piece on its own bone (the sculpts' toes sit too close to tell apart)
    head, tail = bones['Foot.L']
    ln = float(np.linalg.norm(tail - head))
    dirv = (tail - head) / ln
    ball = head + dirv * ln * 0.62
    for i, x in enumerate(lab):
        if x == 'Foot.L' and float((V[i] - ball) @ dirv) > 0:
            lab[i] = 'Toes.L'
    for sd, mir in (('L', np.array([1.0, 1.0, 1.0])), ('R', np.array([-1.0, 1.0, 1.0]))):
        bones[f'Toes.{sd}'] = (ball * mir, (tail + dirv * ln * 0.12) * mir)
        recs.append({'name': f'Toes.{sd}', 'slot': 'Toe', 'side': sd, 'parent': f'Foot.{sd}', 'z': [0.0, 0.0, -1.0],
                     'u': 0.0, 'seg': 0})
    # the right side: each point takes its mirror twin's bone on the left (hands and feet)
    left = [i for i, x in enumerate(lab) if x.endswith('.L') and x.split('.')[0].rstrip('abc').rstrip('0123456789') in
            ('Hand', 'Foot', 'Finger', 'Toe', 'Toes')]
    kd = kdtree.KDTree(len(left))
    for j, i in enumerate(left):
        kd.insert(V[i] * (-1.0, 1.0, 1.0), j)
    kd.balance()
    moved = 0
    for i in np.nonzero(V[:, 0] < 0)[0]:
        _co, j, dist = kd.find(V[i])
        if dist < 0.006:
            new = lab[left[j]][:-1] + 'R'
            moved += new != lab[i]
            lab[int(i)] = new
    print('right side: points given their twin\'s bone', moved)
    return recs


def auto_marks(V):
    """The wrist, the ankle and the toes found on a whole body (no palm / sole parts to mark them): the arm's and the
    leg's narrowest slice near their ends, the foot's front on the floor."""
    R = V[V[:, 0] > 0]
    zs = np.linspace(0.02, 0.98, 97)
    mid_n = np.array([((np.abs(V[:, 0]) < 0.008) & (np.abs(V[:, 2] - z) < 0.006)).sum() for z in zs])
    crotch = float(zs[np.nonzero((mid_n > 4) & (zs > 0.2))[0][0]])
    arm, leg = [], []
    for z in zs:
        P = R[np.abs(R[:, 2] - z) < 0.006]
        if len(P) < 6:
            continue
        cl = clusters(P[:, 0])
        if z < crotch:
            leg.append((z, P[cl[0][2]]))
            if len(cl) > 1:
                arm.append((z, np.concatenate([P[c[2]] for c in cl[1:]])))
        elif len(cl) > 1:
            arm.append((z, P[cl[-1][2]]))

    def narrow(sl, z0, z1):
        best = None
        for z, P in sl:
            if z0 <= z <= z1:
                a = float(np.ptp(P[:, 0]) * np.ptp(P[:, 1]))
                if best is None or a < best[0]:
                    best = (a, P.mean(0))
        return best[1]
    az = [z for z, _p in arm]
    tip, top = min(az), max(az)
    wrist = narrow(arm, tip + (top - tip) * 0.2, tip + (top - tip) * 0.6)
    ankle = narrow(leg, 0.15, 0.32)
    low = R[(R[:, 2] < 0.04) & (R[:, 0] < wrist[0] + 0.05)]
    toe = low[low[:, 1] <= np.quantile(low[:, 1], 0.5)].mean(0)
    return {'wrist': wrist, 'ankle': ankle, 'toe': toe}


def main(kind, path, extra=None):
    V, N, L = read(path)
    V, shift, H = normalise(V)
    if kind == 'creature2':
        Vh, _n, _l = read(extra, faces=10 ** 9)
        Vh = (Vh - shift) / H                          # (the palms and soles: where the body's hands and feet are)
        R = Vh[Vh[:, 0] > 0]
        palm = R[R[:, 2] > 0.3]
        sole = R[R[:, 2] < 0.2]
        top = lambda P, q=0.9: P[P[:, 2] >= np.quantile(P[:, 2], q)].mean(0)     # noqa: E731
        marks = {'wrist': top(palm), 'ankle': top(sole, 0.93),
                 'toe': sole[sole[:, 2] <= np.quantile(sole[:, 2], 0.25)].mean(0)}
        bones, lab = found_bones(V, N, L, marks)
        meta_extra = {'marks': {k: [round(float(x), 5) for x in v] for k, v in marks.items()}}
    elif kind == 'creature':                          # (body06.fbx: one mesh, no parts - its joints found on it)
        marks = auto_marks(V)
        print('marks', {k: np.round(v, 3) for k, v in marks.items()})
        bones, lab = found_bones(V, N, L, marks)
        meta_extra = {'marks': {k: [round(float(x), 5) for x in v] for k, v in marks.items()}}
    else:
        bones, lab = kit_bones(kind, V)
        meta_extra = {}
    names = []
    for base in ORDER:
        for sd in (('L', 'R') if base in SIDED else ('',)):
            names.append(base + ('.' + sd if sd else ''))
    # a hand sculpted touching the thigh is grown onto it: the faces between them cut, or the skin there would stretch
    low = {'Thigh', 'Shin', 'Foot', 'Pelvis', 'Waist'}
    def klass(x):
        return 1 if x.split('.')[0] in ('Forearm', 'Hand') else 2 if x.split('.')[0] in low else 0

    def near_bone(v, names_):
        best, bd = names_[0], 1e9
        for n in names_:
            a_, b_ = bones[n]
            ab = b_ - a_
            q = a_ + ab * min(max(float((v - a_) @ ab) / float(ab @ ab), 0.0), 1.0)
            d_ = float(np.linalg.norm(v - q))
            if d_ < bd:
                best, bd = n, d_
        return best
    nbv = [set() for _ in V]
    k = 0
    for n_ in N:
        n_ = int(n_)
        f = [int(x) for x in L[k:k + n_]]
        for a_, b_ in zip(f, f[1:] + f[:1]):
            nbv[a_].add(b_)
            nbv[b_].add(a_)
        k += n_
    flipped = 0
    for _it in range(4):                              # (a stray point of the hand's in the thigh's skin, or the other
        for i in range(len(V)):                       #  way round, would pull a strand: it takes its neighbours' side)
            c = klass(lab[i])
            if c == 0 or not nbv[i]:
                continue
            other = sum(1 for j in nbv[i] if klass(lab[j]) == 3 - c)
            if other * 2 > len(nbv[i]):
                sd = 'L' if V[i, 0] > 0 else 'R'
                lab[i] = near_bone(V[i], [f'Thigh.{sd}', f'Shin.{sd}'] if c == 1 else [f'Hand.{sd}', f'Forearm.{sd}'])
                flipped += 1
    print('stray points put on their neighbours\' side', flipped)
    cls = np.array([klass(x) for x in lab])
    keepN, keepL, k, cut = [], [], 0, 0
    for n_ in N:
        n_ = int(n_)
        f = L[k:k + n_]
        k += n_
        c = cls[f]
        if (c == 1).any() and (c == 2).any():
            cut += 1
            continue
        keepN.append(n_)
        keepL.extend(int(x) for x in f)
    print('faces cut between the hands and the legs', cut)
    N, L = np.array(keepN, np.uint8), np.array(keepL, np.int32)
    if cut:                                           # (the cut's open rims closed: the thigh whole, the finger capped)
        bm = bmesh.new()
        vs = [bm.verts.new(v) for v in V]
        k = 0
        for n_ in N:
            n_ = int(n_)
            try:
                bm.faces.new([vs[int(i)] for i in L[k:k + n_]])
            except ValueError:
                pass
            k += n_
        seen, small = set(), []                       # (crumbs left loose by the cut: gone)
        for v0 in bm.verts:
            if v0 in seen:
                continue
            comp, st = [v0], [v0]
            seen.add(v0)
            while st:
                a_ = st.pop()
                for e in a_.link_edges:
                    b_ = e.other_vert(a_)
                    if b_ not in seen:
                        seen.add(b_)
                        comp.append(b_)
                        st.append(b_)
            if 1 < len(comp) < 80:
                small += comp
        if small:
            bmesh.ops.delete(bm, geom=list({f for v in small for f in v.link_faces}), context='FACES_ONLY')
            print('crumbs removed: points', len(small))
        before = len(bm.faces)
        bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
        bm.normal_update()
        bm.verts.index_update()
        N = np.array([len(f.verts) for f in bm.faces], np.uint8)
        L = np.array([v.index for f in bm.faces for v in f.verts], np.int32)
        print('rims closed: faces', before, '->', len(bm.faces))
        bm.free()
    digit_recs = add_digits(V, N, L, bones, lab)
    rec = []
    for n in names:
        base, _d, sd = n.partition('.')
        par = PARENT.get(base)
        rec.append({'name': n, 'slot': base, 'side': sd, 'parent': None if par is None else (
            par + '.' + sd if par in SIDED else par),
            'head': [round(float(x), 6) for x in bones[n][0]], 'tail': [round(float(x), 6) for x in bones[n][1]]})
        print(f'{kind} {n:12s} {np.round(bones[n][0], 3)} -> {np.round(bones[n][1], 3)}')
    for r_ in digit_recs:
        n = r_['name']
        rec.append(dict(r_, head=[round(float(x), 6) for x in bones[n][0]], tail=[round(float(x), 6) for x in bones[n][1]]))
        names.append(n)
    idx = {n: i for i, n in enumerate(names)}
    B = np.array([idx[x] for x in lab], np.uint8)
    print(kind, 'points per bone', {n: int((B == i).sum()) for n, i in idx.items()})
    blo, bhi = V.min(0), V.max(0)
    np.savez_compressed(os.path.join(OUT, f'{kind}_whole.npz'), meta=np.array(json.dumps(dict(kit=kind, bones=rec,
                                                                                              **meta_extra))),
                        Body_Q=np.round((V - blo) / (bhi - blo) * 65535).astype(np.uint16),
                        Body_box=np.array([blo, bhi], np.float32), Body_N=N, Body_L=L.astype(np.uint16), Body_B=B)
    print('saved', kind, len(N), 'faces')


args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
main(args[0], args[1], args[2] if len(args) > 2 else None)
