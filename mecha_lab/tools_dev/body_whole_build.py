"""0.24.187 one-piece bodies (user: "크리쳐 바디 하나 더 보낼 테니까 그것도 아까 인물 한 것처럼 리깅해서 넣어 줘, 그리고 기존에 보낸
크리쳐도 리깅해 주고"): each body made light and stored whole WITH its bones and each point's bone.

    <blender python> body_whole_build.py human <body044.fbx> 2
    <blender python> body_whole_build.py creature <body033.fbx> 2
    <blender python> body_whole_build.py creature2 <bpy055.fbx> 4
    (the last number: how many un-subdivide steps make it light)

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


def read(path, faces=FACES, unsub=0):
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
    if unsub:                                         # (a clean all-quad retopo: its own coarser levels, quads kept)
        md.decimate_type = 'UNSUBDIV'
        md.iterations = unsub
    else:
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
    if 'knee' in marks:                               # (found along the leg's own middle line: where it bends)
        knee = np.array(marks['knee'], float)
    # the arm: the shoulder joint inside the body's top corner over the armpit, the elbow as the knee
    top = V[(V[:, 0] > 0) & (V[:, 2] > armpit) & (V[:, 2] < armpit + 0.1)]
    xq = float(np.quantile(top[:, 0], 0.9))
    cap = V[(V[:, 0] > xq - 0.05) & (V[:, 2] > armpit) & (V[:, 2] < armpit + 0.22)]
    rise = float(cap[:, 2].max()) - armpit            # (how high the shoulder stands over the armpit)
    # the joint high in the shoulder (under its top), so little of it lies above to sink into the neck when lifted
    sh = np.array([xq - max(0.035, 0.4 * rise), top[:, 1].mean(), armpit + max(0.035, 0.6 * rise)])
    print('shoulder: armpit', round(armpit, 3), 'rise', round(rise, 3), 'joint', np.round(sh, 3))
    ar = arm[arm[:, 2] > wrist[2] + 0.02]
    ax = (wrist - sh) / np.linalg.norm(wrist - sh)
    off = np.linalg.norm((ar - sh) - np.outer((ar - sh) @ ax, ax), axis=1)
    tt = (ar - sh) @ ax / np.linalg.norm(wrist - sh)
    ok = (tt > 0.3) & (tt < 0.7)
    elbow = ar[ok][np.argmax(off[ok])] if ok.any() else (sh + wrist) * 0.5
    if 'elbow' in marks:
        elbow = np.array(marks['elbow'], float)
    # the body: its middle line up from the pelvis; the neck where it is narrowest above the shoulders
    cen = np.array([[0.0, P[:, 1].mean(), z] for z, P, _c in body])
    wid = np.array([np.ptp(P[:, 0]) for _z, P, _c in body])
    zb = cen[:, 2]
    up = zb > sh[2] + 0.02
    i_n = np.nonzero(up)[0][np.argmin(wid[up][:max(3, int(up.sum() * 0.6))])]
    neck_mid = cen[i_n]
    # the body in three (user: the chest down to under the ribs, the waist, the pelvis like briefs - its edge the
    # groin's V): heights between the crotch and the shoulders
    def mid_at(z):
        return np.array([0.0, float(np.interp(z, zb, cen[:, 1])), z])
    span = sh[2] - crotch
    pel_lo, pel = mid_at(crotch - 0.02), mid_at(crotch + 0.36 * span)
    pel_lo[1] = pel[1]
    waist_top = mid_at(crotch + 0.6 * span)
    chest_top = mid_at(sh[2] + 0.02)
    # the groin's line (front view): from the crotch up and out to the hip's side - above it the pelvis, below the leg
    zB = crotch + 0.6 * (pel[2] - crotch)
    wB = float(min(body, key=lambda b_: abs(b_[0] - zB))[1][:, 0].max())
    gA = np.array([0.015, 0.0, crotch])
    gu = np.array([wB - 0.015, 0.0, zB - crotch])
    gu /= np.linalg.norm(gu)
    gN = np.array([gu[2], 0.0, -gu[0]])               # (down and out: the leg's side)
    near = V[(V[:, 0] > 0.01) & (V[:, 0] < wB + 0.01) & (V[:, 2] < zB + 0.03) & (V[:, 2] > crotch - 0.08) &
             (np.abs((V - gA) @ gN) < 0.012)]
    if len(near) > 8:
        hip = near.mean(0)
    # the head: ALL of it (user: the back of the skull and the jaw too) - cut from under the chin back up to the nape.
    # The side outline down the body's middle: the front falls back sharply under the chin; the back is most hollow
    # at the nape.
    ztop = float(V[:, 2].max())
    Cn = V[np.abs(V[:, 0]) < 0.03]
    prof = []
    for z in np.arange(ztop - 0.003, chest_top[2] - 0.12, -0.006):
        m = np.abs(Cn[:, 2] - z) < 0.004
        if m.sum() >= 3:
            prof.append((z, float(Cn[m, 1].min()), float(Cn[m, 1].max())))
    prof = np.array(prof)
    n_hd = int((prof[:, 0] > chest_top[2]).sum())
    i_sn = int(np.argmin(prof[:max(3, int(n_hd * 0.75)), 1]))   # (the face's most forward point)
    fw = -prof[:, 1] - prof[:, 0]                     # (how far forward-and-down each slice's front reaches)
    i_ch = i_sn                                       # (the chin: the face's lowest forward point - after it the
    for i in range(i_sn + 1, len(prof)):              #  outline falls back to the throat)
        if fw[i] >= fw[i_ch]:
            i_ch = i
        elif fw[i] < fw[i_ch] - 0.012:
            break
    chin = np.array([0.0, prof[i_ch, 1], prof[i_ch, 0] - 0.003])
    # the cut runs on a slant (user: "대각선으로"): from under the chin UP to the skull's base at the back - under its
    # backmost point by a bit over half of what lies above that point
    z_np = chin[2] + 0.45 * (ztop - chin[2])
    i_np = int(np.argmin(np.abs(prof[:, 0] - z_np)))
    nape = np.array([0.0, prof[i_np, 2], prof[i_np, 0]])
    Hc = V[V[:, 2] > min(chin[2], nape[2]) + 0.4 * (ztop - min(chin[2], nape[2]))].mean(0)
    Hc[0] = 0.0
    e_ = nape - chin
    hN = np.array([0.0, -e_[2], e_[1]])
    hN /= np.linalg.norm(hN)
    head_base = (chin + nape) * 0.5
    if float((Hc - head_base) @ hN) < 0:
        hN = -hN
    Hd = V[(V[:, 2] > min(chin[2], nape[2]) - 0.03) & ((V - head_base) @ hN > 0)]
    head_end = head_base + hN * float(((Hd - head_base) @ hN).max()) * 0.95
    print('head: chin', np.round(chin, 3), 'nape', np.round(nape, 3), 'top', round(ztop, 3))
    fingers = V[(V[:, 0] > 0) & (np.linalg.norm(V - wrist, axis=1) < 0.2) & (V[:, 2] < wrist[2])]
    tip = fingers[np.argmax(np.linalg.norm(fingers - wrist, axis=1))] if len(fingers) else wrist - (0, 0, 0.08)
    if 'tip' in marks:                                # (the longest finger's end, found along the skin)
        tip = np.array(marks['tip'], float)
    hand_end = wrist + (tip - wrist) * 0.6
    L_ = {'Pelvis': (pel_lo, pel), 'Waist': (pel, waist_top), 'Chest': (waist_top, chest_top),
          'Neck': (chest_top, head_base), 'Head': (head_base, head_end),
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
    def along_chain(v, names_):
        """Which bone of a chain: past each joint in turn - a cut ACROSS the limb there (square to the two bones'
        middle direction), so a boundary lies at the joint all the way round."""
        k_ = 0
        for j in range(len(names_) - 1):
            a1, b1 = bones[names_[j]]
            a2, b2 = bones[names_[j + 1]]
            nrm = (b1 - a1) / np.linalg.norm(b1 - a1) + (b2 - a2) / np.linalg.norm(b2 - a2)
            if float((v - b1) @ nrm) > 0:
                k_ = j + 1
            else:
                break
        return names_[k_]
    d_ua, t_ua = seg_d(V, 'UpperArm.L')               # (how thick the upper arm is round its middle)
    m_ua = (np.abs(t_ua - 0.6) < 0.15) & (V[:, 0] > 0) & (d_ua < 0.09)
    arm_r = float(np.quantile(d_ua[m_ua], 0.5)) if m_ua.sum() > 8 else 0.03
    out = []
    counts = {}
    for vi, v in enumerate(V):
        cn = own.get(vi, 'trunk')
        sx = 1.0 if v[0] > 0 else -1.0
        side_g = float((v - gA * (sx, 1, 1)) @ (gN * (sx, 1, 1)))      # (which side of the groin's line)
        if cn.startswith('leg') and side_g < 0:
            cn = 'trunk'
        elif cn == 'trunk' and side_g > 0 and v[2] < zB and abs(v[0]) > 0.015:
            cn = 'legL' if v[0] > 0 else 'legR'
        elif cn.startswith('arm'):                    # (the arm: all that lies OUT from the shoulder joint - the
            a_, b_ = bones['Shoulder.' + cn[-1]]      #  shoulder muscle over it goes up with the arm, not the body)
            dr = (b_ - a_) / np.linalg.norm(b_ - a_)
            if float((v - b_) @ dr) < -0.25 * rise:
                cn = 'trunk'
            elif v[2] < b_[2] - 0.2 * rise:           # (under the joint, on the body's side of the arm and standing off
                ua, ub = bones['UpperArm.' + cn[-1]]  #  its bone: the chest's / the back's edge by the armpit)
                uab = ub - ua
                tq = float((v - ua) @ uab) / float(uab @ uab)
                q_ = ua + uab * min(max(tq, 0.0), 1.0)
                if tq < 0.22 and float((v - q_) @ dr) < 0 and float(np.linalg.norm(v - q_)) > 1.4 * arm_r:
                    cn = 'trunk'
        if cn == 'trunk' and abs(v[0]) > 0.02 and v[2] > armpit:    # (the shoulder's top out past its joint: the arm's)
            a_, b_ = bones['Shoulder.L' if v[0] > 0 else 'Shoulder.R']
            dr = (b_ - a_) / np.linalg.norm(b_ - a_)
            if float((v - b_) @ dr) > -0.1 * rise and v[2] > b_[2] - 0.2 * rise:    # (the cap over the joint only -
                cn = 'armL' if v[0] > 0 else 'armR'                                 #  not the ribs' side under it)
        if cn != 'trunk':
            best = along_chain(v, chains[cn])
        elif float((v - head_base) @ hN) > 0 and v[2] > min(chin[2], nape[2]) - 0.05 and \
                float(np.linalg.norm(v - head_base)) < (ztop - min(chin[2], nape[2])) * 1.6:
            best = 'Head'
        else:
            best = along_chain(v, ['Pelvis', 'Waist', 'Chest', 'Neck'])
            if best in ('Chest', 'Neck') and abs(v[0]) > 0.004 and v[2] > sh[2] - 0.25 * rise:
                sn = 'Shoulder.L' if v[0] > 0 else 'Shoulder.R'    # (the collarbones' share: only the shoulders' TOP -
                if float(seg_d(v[None], sn)[0][0]) < float(seg_d(v[None], best)[0][0]):    # the chest and the
                    best = sn                                                              # shoulder blades stay)
        out.append(best)
        counts[cn] = counts.get(cn, 0) + 1
    print('limbs', counts)
    return bones, out


def finger_tree(V, nb, region, src, minfrac):
    """Over a patch of skin (``region``), how far each point is from ``src`` ALONG THE SKIN, and the pieces that
    stand apart coming back from the far ends until they meet (fingers): ([{m, b, t, tip}], d, the farthest)."""
    import heapq
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
    return found, d, dmax


def middle_line(V, nb, region, src, nbins=70):
    """A limb's middle line: the skin's rings at equal distances along it (from ``src``), each ring's centre."""
    import heapq
    d = {i: 0.0 for i in src}
    hp = [(0.0, i) for i in src]
    heapq.heapify(hp)
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
    ids = np.array(sorted(d))
    dv = np.array([d[i] for i in ids])
    bins = np.minimum((dv / max(dv.max(), 1e-9) * nbins).astype(int), nbins - 1)
    P = [V[ids[bins == q]].mean(0) for q in range(nbins) if (bins == q).sum() >= 4]
    P = np.array(P)
    out = P.copy()                                    # (smoothed a little)
    for i in range(len(P)):
        out[i] = P[max(0, i - 2):i + 3].mean(0)
    return out


def bend_at(P, i, k=6):
    a, b = P[i] - P[max(0, i - k)], P[min(len(P) - 1, i + k)] - P[i]
    c = float(a @ b) / max(float(np.linalg.norm(a) * np.linalg.norm(b)), 1e-12)
    return float(np.degrees(np.arccos(min(max(c, -1.0), 1.0))))


def refine_joints(V, N, L, bones, lab, marks):
    """The knee, the ankle and the elbow where the limb really bends (user's marks: the boundaries at the joints):
    along each limb's middle line the sharpest turn - a straight limb: its middle."""
    nb = [[] for _ in V]
    k = 0
    for n_ in N:
        n_ = int(n_)
        f = [int(x) for x in L[k:k + n_]]
        for a, b in zip(f, f[1:] + f[:1]):
            nb[a].append(b)
            nb[b].append(a)
        k += n_
    out = {}
    # the leg: from the hip down to the toes
    region = {i for i, x in enumerate(lab) if x in ('Thigh.L', 'Shin.L', 'Foot.L')}
    a_, b_ = bones['Thigh.L']
    dr = (b_ - a_) / np.linalg.norm(b_ - a_)
    src = [i for i in region if float((V[i] - a_) @ dr) < 0.02]
    if len(src) > 4:
        P = middle_line(V, nb, region, src)
        n = len(P)
        rng = range(int(n * 0.55), int(n * 0.93))
        top_b = max(bend_at(P, i, 4) for i in rng)
        ia = next(i for i in rng if bend_at(P, i, 4) >= top_b * 0.6)   # (where the turn at the ankle BEGINS)
        hi = max(int(n * 0.25) + 1, min(int(n * 0.6), ia - int(n * 0.15)))
        ik = max(range(int(n * 0.25), hi), key=lambda i: bend_at(P, i) * (1.0 - 1.5 * abs(i / ia - 0.5)))
        ka = bend_at(P, ik)
        out['knee'], out['ankle'] = P[ik], P[ia]
        if ka < 12.0:                                 # (a straight leg on a flat foot: the ankle a little under the
            ank = np.array(marks['ankle'], float)     #  shin's narrowest, the knee half way from the hip to it)
            i2 = int(np.argmin(np.abs(P[:, 2] - ank[2] * 0.75)))
            out['ankle'] = P[i2]
            ik = int(np.argmin(np.abs(P[:, 2] - (a_[2] + P[i2][2]) * 0.5)))
            out['knee'] = P[ik]
            ia = i2
        print('leg: knee at', round(ik / n, 2), f'({ka:.0f} deg)', np.round(P[ik], 3), 'ankle at', round(ia / n, 2),
              f'({bend_at(P, ia):.0f} deg)', np.round(P[ia], 3))
    # the arm: from the shoulder down to the wrist
    region = {i for i, x in enumerate(lab) if x in ('UpperArm.L', 'Forearm.L', 'Hand.L')}
    a_, b_ = bones['UpperArm.L']
    dr = (b_ - a_) / np.linalg.norm(b_ - a_)
    src = [i for i in region if float((V[i] - a_) @ dr) < 0.02]
    if len(src) > 4:
        P = middle_line(V, nb, region, src)
        iw = int(np.argmin(np.linalg.norm(P - np.array(marks['wrist'], float), axis=1)))
        if iw > 12:
            ie = max(range(int(iw * 0.3), int(iw * 0.7)), key=lambda i: bend_at(P, i, 5) * (1.0 - 1.5 * abs(i / iw - 0.5)))
            ea = bend_at(P, ie, 5)
            if ea < 30.0:                             # (no clear bend: half way)
                ie = int(round(iw * 0.5))
            out['elbow'] = P[ie]
            print('arm: elbow at', round(ie / max(iw, 1), 2), f'({ea:.0f} deg)', np.round(P[ie], 3))
    return out


def refine_wrist(V, N, L, bones, lab):
    """The wrist from the fingers: on the forearm + hand, the fingers found (where they part: the knuckles), and from
    the knuckles back a palm's length (a palm about 1.3 x a finger) - there the ring of skin round the wrist."""
    nb = [[] for _ in V]
    k = 0
    for n_ in N:
        n_ = int(n_)
        f = [int(x) for x in L[k:k + n_]]
        for a, b in zip(f, f[1:] + f[:1]):
            nb[a].append(b)
            nb[b].append(a)
        k += n_
    region = {i for i, x in enumerate(lab) if x in ('Forearm.L', 'Hand.L')}
    a_, b_ = bones['Forearm.L']
    ab = b_ - a_
    src = [i for i in region if float((V[i] - a_) @ ab) / float(ab @ ab) < 0.15]
    if len(src) < 4:
        return None
    found, d, dmax = finger_tree(V, nb, region, src, 0.07)
    found = sorted(found, key=lambda f: f['b'] - f['t'])[:6]
    if len(found) < 2:
        return None
    knuckle = float(np.median([f['b'] for f in found]))
    finger = float(np.median([f['t'] - f['b'] for f in found]))
    w = max(knuckle - finger * 1.3, dmax * 0.2)
    ring = [i for i in region if abs(d[i] - w) < 0.008]
    print('wrist from the fingers:', len(found), 'fingers, about', round(finger, 3), 'long; knuckles at', round(knuckle, 3),
          'of', round(dmax, 3), '-> wrist at', round(w, 3), 'ring', len(ring))
    far = max(found, key=lambda f: f['t'])['tip']
    return (V[ring].mean(0), V[far].copy()) if len(ring) > 5 else None

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
    for slot, pre, nseg, minfrac, mindot in (('Hand', 'Finger', 3, 0.11, -0.3),):
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
        found, d, dmax = finger_tree(V, nb, region, src, minfrac)
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
            grp = lambda x: 'a' if x[:4] in ('Hand', 'Fing', 'Fore') else 'f' if x[:4] in ('Foot', 'Toes', 'Shin') else x  # noqa: E731
            if grp(new) != grp(lab[i]):               # (the thigh's skin beside the hand stays the thigh's)
                continue
            moved += new != lab[i]
            lab[int(i)] = new
    print('right side: points given their twin\'s bone', moved)
    return recs


def auto_marks(V, ankle_z=(0.15, 0.32)):
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
    # the wrist: along the forearm's own line (an arm held out slants - level slices cut it askew), where it is
    # thinnest before the hand widens
    A = np.concatenate([P for _z, P in arm])
    lowA = A[A[:, 2] < np.median(A[:, 2])]
    c_ = lowA.mean(0)
    _u, _s, vt = np.linalg.svd(lowA - c_, full_matrices=False)
    axv = vt[0] * (-1.0 if vt[0][2] > 0 else 1.0)     # (toward the fingertips)
    t_ = (lowA - c_) @ axv
    t_ = (t_ - t_.min()) / np.ptp(t_)
    rad_ = np.linalg.norm((lowA - c_) - np.outer((lowA - c_) @ axv, axv), axis=1)
    prof = []                                         # (how WIDE it is along it: the forearm narrows to the wrist,
    for q in np.arange(0.15, 0.86, 0.02):             #  then the palm widens)
        m_ = np.abs(t_ - q) < 0.03
        if m_.sum() > 8:
            cen = lowA[m_].mean(0)
            res = (lowA[m_] - cen) - np.outer((lowA[m_] - cen) @ axv, axv)
            sv = np.linalg.svd(res, full_matrices=False)[1]
            prof.append((float(q), float(sv[0] / np.sqrt(m_.sum())), cen))
    best = None                                       # (from the fingers back: the palm's widest, then the
    palm = [p_ for p_ in prof if 0.62 <= p_[0] <= 0.9]   #  narrowest before it - the wrist)
    if palm:
        pk = max(palm, key=lambda x: x[1])[0]
        back = [p_ for p_ in prof if pk - 0.26 <= p_[0] < pk]
        if back:
            w_ = min(back, key=lambda x: x[1])
            best = (w_[1], w_[2])
    if best is None and prof:
        mid = [p_ for p_ in prof if 0.3 <= p_[0] <= 0.7] or prof
        best = min(((p_[1], p_[2]) for p_ in mid), key=lambda x: x[0])
    wrist = best[1] if best is not None else narrow(arm, tip + (top - tip) * 0.2, tip + (top - tip) * 0.6)
    ankle = narrow(leg, *ankle_z)
    low = R[(R[:, 2] < 0.04) & (R[:, 0] < wrist[0] + 0.05)]
    toe = low[low[:, 1] <= np.quantile(low[:, 1], 0.5)].mean(0)
    return {'wrist': wrist, 'ankle': ankle, 'toe': toe}


def main(kind, path, extra=None):
    """Each body: the user's all-quad retopo, one closed mesh - its own coarser levels taken (quads kept), its joints
    found on it."""
    V, N, L = read(path, unsub=int(extra or 0))
    print('faces', len(N), 'quads', int((N == 4).sum()))
    V, shift, H = normalise(V)
    marks = auto_marks(V, (0.03, 0.12) if kind == 'human' else (0.15, 0.32))
    print('marks', {k: np.round(v, 3) for k, v in marks.items()})
    bones, lab = found_bones(V, N, L, marks)
    w2 = refine_wrist(V, N, L, bones, lab)
    if w2 is not None:
        marks['wrist'], marks['tip'] = w2
        print('marks', {k: np.round(v, 3) for k, v in marks.items()})
        bones, lab = found_bones(V, N, L, marks)
    marks.update(refine_joints(V, N, L, bones, lab, marks))
    bones, lab = found_bones(V, N, L, marks)
    meta_extra = {'marks': {k: [round(float(x), 5) for x in v] for k, v in marks.items()}}
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
        bm.verts.index_update()                       # (a closing face must not tie the hand to the leg again)
        bad = [f for f in bm.faces if {1, 2} <= {int(cls[v.index]) for v in f.verts}]
        if bad:
            bmesh.ops.delete(bm, geom=bad, context='FACES_ONLY')
            print('closing faces across the cut removed', len(bad))
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
    # each point's weights worked out now and stored (half a minute a body: not when the user adds one)
    sys.path.insert(0, os.path.join(HERE, '..', 'addon'))
    from mecha_lab import body_whole as bw
    Eset, k = set(), 0
    for n_ in N:
        n_ = int(n_)
        f = [int(x) for x in L[k:k + n_]]
        for a_, b_ in zip(f, f[1:] + f[:1]):
            Eset.add((min(a_, b_), max(a_, b_)))
        k += n_
    bn = {r_['name']: (np.array(r_['head'], float), np.array(r_['tail'], float), r_['parent'], r_['slot'], r_['side'])
          for r_ in rec}
    dgt = {r_['name']: (r_['z'], r_['u'], r_['seg']) for r_ in rec if 'z' in r_}
    Wt, _nm = bw.skin_weights(V, np.array(sorted(Eset), np.int64), B.astype(np.int64), bn, dgt)
    WI, WW = bw.pack_weights(Wt)
    print('weights stored: strongest 4 a point; the rest dropped at most', round(float(1 - np.sort(Wt, 1)[:, -4:].sum(1).min()), 3))
    Qv = np.round((V - blo) / (bhi - blo) * 65535).astype(np.uint16)
    np.savez_compressed(os.path.join(OUT, f'{kind}_whole.npz'), meta=np.array(json.dumps(dict(kit=kind, bones=rec,
                                                                                              **meta_extra))),
                        Body_box=np.array([blo, bhi], np.float32), Body_N=N, Body_B=B,
                        **bw.pack_mesh(Qv, L, WI, WW))
    print('saved', kind, len(N), 'faces')


args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
main(args[0], args[1], args[2] if len(args) > 2 else None)
