"""0.24.183 Body Kit assets (user: "내가 만든 바디들 ... 팔다리 허벅지 이런 거 분리해서 내가 각각 조절" / "이걸 이용해서 슬라이더로
체형이랑 다리 길이 이런 것도 변경하고 싶어"): the user's two part-split bodies (Nomad sculpts, FBX) made light and stored in the
add-on - each part split left / right, its pivot where it meets its parent, its axis to its child's pivot.

    <blender python> body_kit_build.py <kit id> <fbx> [<kit id> <fbx> ...]

writes addon/mecha_lab/body_kits/<kit id>.npz: per part <name>_V (local coordinates round the pivot, the kit 1 tall), <name>_N
(face sizes), <name>_L (face corners); 'meta' a JSON string: the parts (slot, side, parent, pivot, axis end) in kit space.
"""
import json
import os
import sys

import bpy
import bmesh  # noqa: E402  (after bpy)
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'addon', 'mecha_lab', 'body_kits')

# the parts of each kit by their names in the user's FBX
NAMES = {
    'creature': {'PM3D_Cylinder3D1': 'Arm', 'PM3D_Sphere3D_1': 'Pelvis', 'PM3D_Sphere3D_2': 'Shin',
                 'PM3D_Sphere3D_3': 'Head', 'PM3D_Sphere3D_4': 'Foot', 'PM3D_Sphere3D_5': 'Hand',
                 'PM3D_Sphere3D_6': 'Knee', 'PM3D_Sphere3D_7': 'Thigh', 'PM3D_Sphere3D_8': 'Torso'},
    'human': {'Merged_찰흙 87': 'Pelvis', 'Merged_찰흙 88': 'Shin', 'Merged_찰흙 88_01': 'Knee',
              'Merged_찰흙 88_02': 'UpperArm', 'Merged_찰흙 88_03': 'Torso', 'Merged_찰흙 88_04': 'Thigh',
              'Merged_찰흙 88_05': 'Forearm', 'Merged_찰흙 88_06': 'Hand', 'Merged_찰흙 89': 'Foot'},
}
PARENT = {'Torso': 'Pelvis', 'Head': 'Torso', 'Arm': 'Torso', 'UpperArm': 'Torso', 'Forearm': 'UpperArm',
          'Hand': ('Forearm', 'Arm'), 'Thigh': 'Pelvis', 'Knee': 'Thigh', 'Shin': 'Knee', 'Foot': 'Shin'}
CENTRE = {'Pelvis', 'Torso', 'Head'}
# faces each part keeps (light, the sculpted forms still read)
FACES = {'Head': 7000, 'Torso': 14000, 'Pelvis': 3500, 'Arm': 5000, 'UpperArm': 3000, 'Forearm': 2500, 'Hand': 3500,
         'Thigh': 3500, 'Knee': 1200, 'Shin': 3000, 'Foot': 2500}
TORSO_WITH_HEAD = 18000


def islands(bm):
    bm.verts.ensure_lookup_table()
    lab = -np.ones(len(bm.verts), int)
    k = 0
    for v in bm.verts:
        if lab[v.index] >= 0:
            continue
        st = [v]
        lab[v.index] = k
        while st:
            x = st.pop()
            for e in x.link_edges:
                y = e.other_vert(x)
                if lab[y.index] < 0:
                    lab[y.index] = k
                    st.append(y)
        k += 1
    return lab


def piece(bm, keep):
    """A copy of bm with only the vertices in keep (bool per vertex)."""
    out = bm.copy()
    out.verts.ensure_lookup_table()
    bmesh.ops.delete(out, geom=[v for v in out.verts if not keep[v.index]], context='VERTS')
    return out


def decimate(bm, faces):
    me = bpy.data.meshes.new('tmp')
    bm.to_mesh(me)
    ob = bpy.data.objects.new('tmp', me)
    bpy.context.scene.collection.objects.link(ob)
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    if tris > faces:
        md = ob.modifiers.new('D', 'DECIMATE')
        md.ratio = faces / tris
    dg = bpy.context.evaluated_depsgraph_get()
    me2 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    out = bmesh.new()
    out.from_mesh(me2)
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    bpy.data.meshes.remove(me2)
    return out


def build(kit, path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    names = NAMES[kit]
    raw = {}
    for ob in bpy.data.objects:
        if ob.type != 'MESH' or ob.name not in names:
            continue
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bm.transform(ob.matrix_world)
        raw[names[ob.name]] = bm
    allv = np.concatenate([np.array([v.co[:] for v in bm.verts]) for bm in raw.values()])
    lo, hi = allv.min(0), allv.max(0)
    H = hi[2] - lo[2]
    shift = Vector((-(lo[0] + hi[0]) / 2, 0.0, -lo[2]))
    # split left / right, drop crumbs, normalise (1 tall, the feet on 0)
    parts = {}
    for slot, bm in raw.items():
        bmesh.ops.translate(bm, verts=bm.verts, vec=shift)
        bmesh.ops.scale(bm, verts=bm.verts, vec=(1 / H,) * 3)
        lab = islands(bm)
        V = np.array([v.co[:] for v in bm.verts])
        sizes = np.bincount(lab)
        big = sizes >= 0.02 * len(V)
        if slot in CENTRE:
            parts[slot] = piece(bm, big[lab])
        else:
            cx = np.array([V[lab == i, 0].mean() for i in range(len(sizes))])
            for side, sgn in (('L', 1), ('R', -1)):
                parts[f'{slot}.{side}'] = piece(bm, big[lab] & (cx[lab] * sgn > 0))
        bm.free()
    trees = {n: BVHTree.FromBMesh(bm) for n, bm in parts.items()}
    verts = {n: np.array([v.co[:] for v in bm.verts]) for n, bm in parts.items()}

    def slot_of(n):
        return n.split('.')[0]

    def side_of(n):
        return n.split('.')[1] if '.' in n else ''

    def parent_of(n):
        want = PARENT.get(slot_of(n))
        if not want:
            return None
        for w in (want if isinstance(want, tuple) else (want,)):
            for cand in (f'{w}.{side_of(n)}', w):
                if cand in parts:
                    return cand
        return None

    def contact(a, b, eps=0.006):
        """Where part a meets part b: the middle of the ring where a's surface crosses b's (a's vertices on b's
        surface), else of a's vertices nearest b."""
        V = verts[a]
        d = np.array([trees[b].find_nearest(Vector(p))[3] for p in V])
        ring = V[d < eps]
        if len(ring) < 12:
            ring = V[d <= np.quantile(d, 0.01)]
        return ring.mean(0)

    info = {}
    for n in parts:
        par = parent_of(n)
        info[n] = {'slot': slot_of(n), 'side': side_of(n), 'parent': par,
                   'pivot': (contact(n, par) if par else None)}
    # the root's pivot: between the hips
    hips = [info[n]['pivot'] for n in info if info[n]['slot'] == 'Thigh']
    root = [n for n in info if info[n]['parent'] is None][0]
    info[root]['pivot'] = np.mean(hips, axis=0) if hips else verts[root].mean(0)
    kids = {n: [m for m in info if info[m]['parent'] == n] for n in info}
    for n, d in info.items():
        P = np.array(d['pivot'])
        ks = kids[n]
        main = [m for m in ks if info[m]['slot'] in ('Torso', 'Knee', 'Shin', 'Foot', 'Hand', 'Forearm', 'Head')]
        if d['slot'] == 'Torso':
            arms = [info[m]['pivot'] for m in ks if info[m]['slot'] in ('Arm', 'UpperArm')]
            head = [info[m]['pivot'] for m in ks if info[m]['slot'] == 'Head']
            end = np.array(head[0]) if head else np.mean(arms, axis=0)
            if not head:
                end = np.array([P[0], end[1], end[2] + 0.02])
        elif main:
            end = np.array(info[main[0]]['pivot'])
        else:                                                   # a leaf: to its far end
            V = verts[n]
            c = V.mean(0)
            dirn = (c - P) / max(np.linalg.norm(c - P), 1e-9)
            a = (V - P) @ dirn
            far = V[a >= np.quantile(a, 0.97)].mean(0)
            end = far
        d['end'] = end
    for n, d in info.items():
        if d['side'] == 'L' and n.replace('.L', '.R') in info:
            e = info[n.replace('.L', '.R')]
            for key in ('pivot', 'end'):
                m = (np.array(d[key]) + np.array(e[key]) * (-1, 1, 1)) / 2
                d[key] = m
                e[key] = m * (-1, 1, 1)
    meta = {'kit': kit, 'height': 1.0, 'parts': []}
    arrays = {}
    for n, bm in parts.items():
        d = info[n]
        slot = d['slot']
        target = TORSO_WITH_HEAD if (slot == 'Torso' and 'Head' not in parts) else FACES[slot]
        light = decimate(bm, target)
        P = Vector(d['pivot'])
        bmesh.ops.translate(light, verts=light.verts, vec=-P)
        V = np.array([v.co[:] for v in light.verts], np.float32)
        light.verts.index_update()
        N = np.array([len(f.verts) for f in light.faces], np.int32)
        L = np.array([v.index for f in light.faces for v in f.verts], np.int32)
        arrays[f'{n}_V'] = V
        arrays[f'{n}_N'] = N
        arrays[f'{n}_L'] = L
        meta['parts'].append({'name': n, 'slot': slot, 'side': d['side'], 'parent': d['parent'],
                              'pivot': [round(float(x), 6) for x in d['pivot']],
                              'end': [round(float(x), 6) for x in d['end']]})
        print(f'{kit} {n:12s} faces {len(N):6d} pivot {np.round(d["pivot"], 3)} end {np.round(d["end"], 3)} '
              f'parent {d["parent"]}', flush=True)
        light.free()
    os.makedirs(OUT, exist_ok=True)
    np.savez_compressed(os.path.join(OUT, f'{kit}.npz'), meta=np.array(json.dumps(meta)), **arrays)
    print('saved', kit, sum(len(arrays[k]) for k in arrays if k.endswith('_N')), 'faces')


args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
for i in range(0, len(args) - 1, 2):
    build(args[i], args[i + 1])
