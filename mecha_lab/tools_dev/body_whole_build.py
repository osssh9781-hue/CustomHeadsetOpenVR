"""0.24.187 one-piece bodies (user: "크리쳐 바디 하나 더 보낼 테니까 그것도 아까 인물 한 것처럼 리깅해서 넣어 줘, 그리고 기존에 보낸
크리쳐도 리깅해 주고"): each body made light and stored whole WITH its bones and each point's bone.

    <blender python> body_whole_build.py human <body02.fbx>
    <blender python> body_whole_build.py creature <body.fbx>            (the part-split creature's whole body)
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
    leg, arm, body = [], [], []
    for z in zs:
        m = np.abs(R[:, 2] - z) < 0.006
        if m.sum() < 6:
            continue
        P = R[m]
        cl = clusters(P[:, 0])
        if z < crotch:                                # (below the crotch: the leg is the inner clump)
            inner = cl[0][2]
            leg.append(P[inner].mean(0))
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
    ok = (tt > 0.25) & (tt < 0.75)
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
    # each point's bone: the nearest one it can see (a fingertip beside the thigh does not see the thigh's bone)
    tris, k = [], 0
    for n_ in N:
        for q in range(1, n_ - 1):
            tris.append((int(L[k]), int(L[k + q]), int(L[k + q + 1])))
        k += n_
    bvh = BVHTree.FromPolygons([tuple(v) for v in V], tris)
    names = list(bones)
    A = np.array([bones[n][0] for n in names])
    B = np.array([bones[n][1] for n in names])
    out = []
    for v in V:
        ab = B - A
        t = np.clip(((v - A) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-12), 0.0, 1.0)
        Q = A + ab * t[:, None]
        d = np.linalg.norm(Q - v, axis=1)
        for j, n in enumerate(names):                 # (the other side's limbs: out of reach)
            if (n.endswith('.L') and v[0] < -0.004) or (n.endswith('.R') and v[0] > 0.004):
                d[j] = 1e3
        pick = None
        for j in np.argsort(d)[:4]:
            dv = Vector(Q[j] - v)
            if dv.length < 1e-6:
                pick = j
                break
            hit = bvh.ray_cast(Vector(v) + dv.normalized() * 0.002, dv.normalized(), dv.length - 0.002)
            if hit[0] is None:
                pick = j
                break
        out.append(names[int(pick if pick is not None else np.argmin(d))])
    return bones, out


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
    else:
        bones, lab = kit_bones(kind, V)
        meta_extra = {}
    names = []
    for base in ORDER:
        for sd in (('L', 'R') if base in SIDED else ('',)):
            names.append(base + ('.' + sd if sd else ''))
    rec = []
    for n in names:
        base, _d, sd = n.partition('.')
        par = PARENT.get(base)
        rec.append({'name': n, 'slot': base, 'side': sd, 'parent': None if par is None else (
            par + '.' + sd if par in SIDED else par),
            'head': [round(float(x), 6) for x in bones[n][0]], 'tail': [round(float(x), 6) for x in bones[n][1]]})
        print(f'{kind} {n:12s} {np.round(bones[n][0], 3)} -> {np.round(bones[n][1], 3)}')
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
