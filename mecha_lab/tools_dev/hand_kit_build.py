"""0.24.187 hand / foot builder parts (user: "손바닥 발바닥, 그리고 사용할 손가락 프리셋 엄지, (검지 중지), 약지 이렇게 보냈는데 ... 각각
개수랑 길이 두께 조절하면 좋을 것 같고"): the user's palm, sole and three fingers made light, each in its own frame.

    <blender python> hand_kit_build.py <hand.fbx>

writes addon/mecha_lab/body_kits/hand_parts.npz - per part <name>_V (float32), <name>_N, <name>_L; 'meta' (JSON).
Frames (the body 1 tall; the left side's piece kept, the right is its mirror):
  palm / sole: origin the wrist (ankle), Y along it to where the fingers start, Z its flat side's normal, X across.
  a finger: origin its root (the rounded end), Y along it to the tip, Z the palm's normal, X across.
"""
import json
import os
import sys

import bpy
import bmesh
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'addon', 'mecha_lab', 'body_kits', 'hand_parts.npz')
BODY_H = 0.722                                       # (body4.fbx's height: the parts were made on it)
NAMES = {'012': ('Palm', 5000), '013': ('Sole', 6000), '015': ('Finger', 1200), '016': ('Long', 1200),
         '017': ('Thumb', 1400)}


def light(ob, faces):
    """(V, N, L) of the object's x > 0 piece, light, world coordinates."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.transform(ob.matrix_world)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.x < 0], context='VERTS')
    me = bpy.data.meshes.new('p')
    bm.to_mesh(me)
    bm.free()
    o2 = bpy.data.objects.new('p', me)
    bpy.context.scene.collection.objects.link(o2)
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    md = o2.modifiers.new('D', 'DECIMATE')
    md.ratio = min(faces / tris, 1.0)
    dg = bpy.context.evaluated_depsgraph_get()
    m2 = bpy.data.meshes.new_from_object(o2.evaluated_get(dg), depsgraph=dg)
    V = np.array([v.co[:] for v in m2.vertices]) / BODY_H
    N = np.array([len(p.vertices) for p in m2.polygons], np.uint8)
    L = np.array([i for p in m2.polygons for i in p.vertices], np.uint16)
    return V, N, L


def axes(P):
    c = P.mean(0)
    _u, _s, vt = np.linalg.svd(P - c, full_matrices=False)
    return c, vt


def main(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    raw = {}
    for ob in list(bpy.data.objects):
        if ob.type == 'MESH':
            name, faces = NAMES[ob.name[-3:]]
            raw[name] = light(ob, faces)
    out, meta = {}, {}
    front = np.array([0.0, -1.0, 0.0])
    frames = {}
    for base in ('Palm', 'Sole'):
        V, N, L = raw[base]
        c, vt = axes(V)
        top = V[V[:, 2] >= np.quantile(V[:, 2], 0.95)].mean(0)      # (the wrist / ankle: its top)
        y = vt[0] * np.sign(vt[0] @ (c - top))
        z = vt[2] - y * (vt[2] @ y)
        z /= np.linalg.norm(z)
        if z @ front < 0:
            z = -z
        x = np.cross(y, z)
        t = (V - top) @ y
        org = top + y * (t.min() - (top - top) @ y)   # (the origin: on its axis, at its very start)
        org = top + y * t.min()
        A = np.stack([(V - org) @ x, (V - org) @ y, (V - org) @ z], 1)
        f = front - y * (front @ y)
        f /= np.linalg.norm(f)
        turn = float(np.arctan2(np.cross(f, z) @ y, f @ z))          # (round Y, from the front to its normal)
        frames[base] = (org, x, y, z)
        out[base + '_V'], out[base + '_N'], out[base + '_L'] = A.astype(np.float32), N, L
        meta[base] = {'turn': round(turn, 4), 'size': [round(float(v), 5) for v in np.ptp(A, 0)],
                      'lo': [round(float(v), 5) for v in A.min(0)], 'hi': [round(float(v), 5) for v in A.max(0)]}
        print(base, 'size', np.round(np.ptp(A, 0), 4), 'turn', round(np.degrees(turn), 1), 'faces', len(N))
    org, px, py, pz = frames['Palm']
    face, thumb_x = 0.0, 0.0
    for fn in ('Finger', 'Long', 'Thumb'):
        V, N, L = raw[fn]
        c, vt = axes(V)
        y = vt[0]
        t = (V - c) @ y
        e0, e1 = V[t < np.quantile(t, 0.06)].mean(0), V[t > np.quantile(t, 0.94)].mean(0)
        pc = org + py * meta['Palm']['size'][1] * 0.5
        root, tip = (e0, e1) if np.linalg.norm(e0 - pc) < np.linalg.norm(e1 - pc) else (e1, e0)
        y = (tip - root) / np.linalg.norm(tip - root)
        z = pz - y * (pz @ y)
        z /= np.linalg.norm(z)
        x = np.cross(y, z)
        o = root
        A = np.stack([(V - o) @ x, (V - o) @ y, (V - o) @ z], 1)
        ln = float(A[:, 1].max())
        # where it sits on the palm (the palm's frame) and where it points
        rp = [float((root - org) @ a) for a in (px, py, pz)]
        dp = [float(y @ a) for a in (px, py, pz)]
        # how it curves: its middle off the root - tip line, toward the palm's normal (+) or away
        midm = A[np.abs(A[:, 1] - ln * 0.5) < ln * 0.08].mean(0)
        tipm = A[A[:, 1] > ln * 0.92].mean(0)
        out[fn + '_V'], out[fn + '_N'], out[fn + '_L'] = A.astype(np.float32), N, L
        meta[fn] = {'length': round(ln, 5), 'thick': round(float(np.ptp(A[:, 0])), 5), 'at': [round(v, 5) for v in rp],
                    'dir': [round(v, 4) for v in dp], 'tip': [round(float(v), 5) for v in tipm]}
        if fn == 'Thumb':
            thumb_x = rp[0] - meta['Palm']['size'][0] * 0.0
        face += dp[2]
        print(fn, 'length', round(ln, 4), 'size', np.round(np.ptp(A, 0), 4), 'at', np.round(rp, 4), 'dir',
              np.round(dp, 3), 'mid', np.round(midm, 4), 'faces', len(N))
    meta['face'] = 1.0 if face >= 0 else -1.0          # (the fingers lean to this side of the palm: its inside)
    mid_x = (meta['Palm']['lo'][0] + meta['Palm']['hi'][0]) * 0.5
    meta['thumb_side'] = 1.0 if thumb_x >= mid_x else -1.0
    print('face', meta['face'], 'thumb side', meta['thumb_side'], 'palm lo/hi', meta['Palm']['lo'], meta['Palm']['hi'])
    np.savez_compressed(OUT, meta=np.array(json.dumps(meta)), **out)
    print('saved', os.path.getsize(OUT))


args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
main(args[0])
