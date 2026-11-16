"""0.24.183 sculpted muscle shapes (user: "내가 하나짜리 근육이랑 두 개짜리 어깨 가슴 삼두 보내니까 사용해서 만들어 줘"):
the user's five sculpted muscles (Nomad, FBX) made light and stored with where each point sits on the muscle, so the
Muscle tool lays the same shape between the points clicked on a body.

    <blender python> muscle_templates_build.py <ana.fbx>

writes addon/mecha_lab/body_kits/muscles.npz - per shape <ID>_A (n, 3) its points' place, <ID>_N / <ID>_L its faces,
<ID>_lo the height of its underside (a grid), 'meta' a JSON string.

* LINE shapes (Muscle, Two Strands, Triceps): along its length t (0 at the end clicked first), across s and up v,
  both over its length; the underside lo(t).
* FAN shapes (Chest, Shoulder): its surface is near a sphere - u from its first corner to its second (the line it
  starts on), t from that line to its end (the tendon), v out from the sphere over its length; lo(u, t).
"""
import json
import math
import os
import sys

import bpy
import bmesh  # noqa: E402  (after bpy)
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'addon', 'mecha_lab', 'body_kits', 'muscles.npz')
SHAPES = {   # id: (object in the FBX, kind, faces kept)
    'SINGLE': ('PM3D_Sphere3D_1', 'LINE', 900),
    'DOUBLE': ('PM3D_Sphere3D_4', 'LINE', 1800),
    'TRICEPS': ('PM3D_Sphere3D_2', 'LINE', 2200),
    'PEC': ('PM3D_Sphere3D_6', 'FAN', 2600),
    'DELTOID': ('PM3D_Sphere3D_7', 'FAN', 3000),
}
SPREAD = 0.15            # a fan's tendon: as wide as this share of the line it starts on (the same where it is laid)
SPREADS = {'DELTOID': 0.45}   # (the shoulder's thick end: wider, its paths do not cross there)
U_RANGE, T_RANGE = (-0.8, 1.8), (-0.3, 1.45)


def light(ob, faces):
    me = ob.data
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    md = ob.modifiers.new('D', 'DECIMATE')
    md.ratio = min(faces / max(tris, 1), 1.0)
    dg = bpy.context.evaluated_depsgraph_get()
    me2 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    ob.modifiers.remove(md)
    bm = bmesh.new()
    bm.from_mesh(me2)
    bm.transform(ob.matrix_world)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.verts.index_update()
    V = np.array([v.co[:] for v in bm.verts])
    N = np.array([len(f.verts) for f in bm.faces], np.int32)
    L = np.array([v.index for f in bm.faces for v in f.verts], np.int32)
    bm.free()
    bpy.data.meshes.remove(me2)
    return V, N, L


def tips(V):
    """The three far points of a shape (the corners of the biggest triangle on its hull)."""
    rng = np.random.default_rng(1)
    dirs = rng.normal(size=(400, 3))
    dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
    P = V[np.unique(np.argmax(V @ dirs.T, axis=0))]
    best = None
    for i in range(len(P)):
        for j in range(i + 1, len(P)):
            dk = np.linalg.norm(P - P[i], axis=1) + np.linalg.norm(P - P[j], axis=1)
            k = int(np.argmax(dk))
            per = np.linalg.norm(P[i] - P[j]) + dk[k]
            if best is None or per > best[0]:
                best = (per, i, j, k)
    return P[best[1]], P[best[2]], P[best[3]]


def smooth_grid(G, have, passes=6):
    """Empty cells filled from their neighbours, then the grid softened."""
    G = G.copy()
    have = have.copy()
    for _ in range(200):
        if have.all():
            break
        P = np.pad(G, 1, mode='edge')
        H = np.pad(have.astype(float), 1, mode='constant')
        acc = np.zeros_like(G)
        cnt = np.zeros_like(G)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                acc += (P * H)[1 + di:1 + di + G.shape[0], 1 + dj:1 + dj + G.shape[1]]
                cnt += H[1 + di:1 + di + G.shape[0], 1 + dj:1 + dj + G.shape[1]]
        new = (~have) & (cnt > 0)
        G[new] = acc[new] / cnt[new]
        have = have | new
    for _ in range(passes):
        P = np.pad(G, 1, mode='edge')
        G = (P[1:-1, 1:-1] * 4 + P[:-2, 1:-1] + P[2:, 1:-1] + P[1:-1, :-2] + P[1:-1, 2:]) / 8.0
    return G


def line_shape(V):
    c = V.mean(0)
    X = V - c
    w, E = np.linalg.eigh(np.cov(X.T))
    E = E[:, ::-1]
    a, s, v = X @ E[:, 0], X @ E[:, 1], X @ E[:, 2]
    L = a.max() - a.min()
    t = (a - a.min()) / L
    # its start: the end that splits into heads (wider across) - else either
    w0 = np.ptp(s[t < 0.15]) if (t < 0.15).any() else 0
    w1 = np.ptp(s[t > 0.85]) if (t > 0.85).any() else 0
    if w1 > w0 * 1.15:
        t = 1.0 - t
        s = -s
    if v.max() < -v.min():                 # (its flatter side down)
        v = -v
        s = -s
    A = np.c_[t, s / L, v / L]
    nb = 41
    lo = np.zeros(nb)
    have = np.zeros(nb, bool)
    k = np.clip((t * (nb - 1)).round().astype(int), 0, nb - 1)
    for i in range(nb):
        m = k == i
        if m.any():
            lo[i] = (v[m] / L).min()
            have[i] = True
    lo = smooth_grid(lo[None, :], have[None, :], passes=2)[0]
    return A, lo, {'length': float(L)}


def _slerp(a, b, t):
    """Unit vectors a -> b (n, 3) at t (n,) - past 0 .. 1 too."""
    dot = np.clip((a * b).sum(-1), -1.0, 1.0)
    th = np.arccos(dot)[..., None]
    s = np.sin(th)
    t = np.asarray(t)[..., None]
    small = s < 1e-6
    k0 = np.where(small, 1 - t, np.sin((1 - t) * th) / np.where(small, 1, s))
    k1 = np.where(small, t, np.sin(t * th) / np.where(small, 1, s))
    out = a * k0 + b * k1
    return out / np.linalg.norm(out, axis=-1, keepdims=True)


def fan_sheet(dA, dB, dC, u, t, spread=None):
    O = _slerp(np.broadcast_to(dA, u.shape + (3,)), np.broadcast_to(dB, u.shape + (3,)), u)
    side = dB - dA
    side = side - dC * (side @ dC)
    side /= np.linalg.norm(side)
    span = math.acos(np.clip(dA @ dB, -1, 1))
    I = dC + side * ((u - 0.5) * (SPREAD if spread is None else spread) * span)[..., None]
    I /= np.linalg.norm(I, axis=-1, keepdims=True)
    return _slerp(O, I, t)


def fan_shape(V, order, spread=SPREAD):
    # the sphere it lies on
    M = np.c_[2 * V, np.ones(len(V))]
    sol = np.linalg.lstsq(M, (V ** 2).sum(1), rcond=None)[0]
    c = sol[:3]
    R = math.sqrt(sol[3] + c @ c)
    p = tips(V)
    pA, pB, pC = (p[i] for i in order)
    d = V - c
    r = np.linalg.norm(d, axis=1)
    dirs = d / r[:, None]
    dA, dB, dC = ((q - c) / np.linalg.norm(q - c) for q in (pA, pB, pC))
    # (u, t) of each point: the nearest on a grid, then a few Newton steps
    gu = np.linspace(*U_RANGE, 120)
    gt = np.linspace(*T_RANGE, 110)
    UU, TT = np.meshgrid(gu, gt, indexing='ij')
    G = fan_sheet(dA, dB, dC, UU, TT, spread).reshape(-1, 3)
    best = np.argmax(dirs @ G.T, axis=1)
    u = UU.ravel()[best].copy()
    t = TT.ravel()[best].copy()
    h = 1e-4

    def miss(u_, t_):
        return 1.0 - (fan_sheet(dA, dB, dC, u_, t_, spread) * dirs).sum(1)
    for _ in range(12):                               # (damped: a step kept only where it lands nearer)
        f = fan_sheet(dA, dB, dC, u, t, spread)
        fu = (fan_sheet(dA, dB, dC, u + h, t, spread) - f) / h
        ft = (fan_sheet(dA, dB, dC, u, t + h, spread) - f) / h
        r_ = dirs - f
        J = np.stack([fu, ft], -1)                    # (n, 3, 2)
        JtJ = np.einsum('nik,nil->nkl', J, J) + np.eye(2) * 1e-6
        Jtr = np.einsum('nik,ni->nk', J, r_)
        step = np.linalg.solve(JtJ, Jtr[..., None])[..., 0]
        step = np.clip(step, -0.05, 0.05)
        nu_t, nt_t = u + step[:, 0], t + step[:, 1]
        better = miss(nu_t, nt_t) < miss(u, t)
        u = np.where(better, nu_t, u)
        t = np.where(better, nt_t, t)
    err = np.degrees(np.arccos(np.clip((fan_sheet(dA, dB, dC, u, t, spread) * dirs).sum(1), -1, 1)))
    mid = (dA + dB) / np.linalg.norm(dA + dB)
    Lf = R * math.acos(np.clip(mid @ dC, -1, 1))       # (its length over the sphere: middle of its start -> end)
    v = (r - R) / Lf
    A = np.c_[u, t, v]
    nu_, nt_ = 15, 21
    lo = np.zeros((nu_, nt_))
    have = np.zeros((nu_, nt_), bool)
    iu = np.clip(((u - U_RANGE[0]) / (U_RANGE[1] - U_RANGE[0]) * (nu_ - 1)).round().astype(int), 0, nu_ - 1)
    it = np.clip(((t - T_RANGE[0]) / (T_RANGE[1] - T_RANGE[0]) * (nt_ - 1)).round().astype(int), 0, nt_ - 1)
    for i in range(nu_):
        for j in range(nt_):
            m = (iu == i) & (it == j)
            if m.any():
                lo[i, j] = v[m].min()
                have[i, j] = True
    lo = smooth_grid(lo, have, passes=4)
    print(f'   fit error: median {np.median(err):.3f} deg, max {err.max():.2f} deg; u {u.min():.2f}..{u.max():.2f} '
          f't {t.min():.2f}..{t.max():.2f}')
    return A, lo, {'length': float(Lf), 'radius': float(R), 'u_range': U_RANGE, 't_range': T_RANGE,
                   'spread': spread, 'width': float(R * math.acos(np.clip(dA @ dB, -1, 1)))}


ORDER = {'PEC': (0, 1, 2), 'DELTOID': (0, 1, 2)}    # (the tips as found: first corner, second corner, end)


def main(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    meta = {'shapes': {}}
    arrays = {}
    for sid, (name, kind, faces) in SHAPES.items():
        ob = bpy.data.objects[name]
        V, N, L = light(ob, faces)
        if kind == 'LINE':
            A, lo, info = line_shape(V)
        else:
            p = tips(V)
            # the end (tendon): the tip farthest from the other two's middle; the corners: the other two, the higher
            # one first (as sculpted, standing)
            far = [np.linalg.norm(p[i] - (p[(i + 1) % 3] + p[(i + 2) % 3]) / 2) for i in range(3)]
            e = int(np.argmax(far))
            a, b = [i for i in range(3) if i != e]
            if p[b][2] > p[a][2]:
                a, b = b, a
            A, lo, info = fan_shape(V, (a, b, e), SPREADS.get(sid, SPREAD))
        arrays[f'{sid}_A'] = A.astype(np.float32)
        arrays[f'{sid}_N'] = N
        arrays[f'{sid}_L'] = L
        arrays[f'{sid}_lo'] = np.asarray(lo, np.float32)
        meta['shapes'][sid] = dict(info, kind=kind)
        print(sid, kind, len(N), 'faces', {k: (round(v, 4) if isinstance(v, float) else v) for k, v in info.items()},
              flush=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    np.savez_compressed(OUT, meta=np.array(json.dumps(meta)), **arrays)
    print('saved', OUT)


args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
main(args[0])
