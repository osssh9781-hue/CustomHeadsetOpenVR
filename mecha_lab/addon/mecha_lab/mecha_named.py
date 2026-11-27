"""0.24.336 Rig > Mecha by Names (user: "메카닉 리깅 ... 내가 항상 팔다리 몸통 골반 머리 이렇게 나눠 놓으니까 ... 나누고 이름
변경하면 그걸로 각 조인트 연결하는 리깅 만들어 줄래? IK 로").

The parts are named by what they are; the rig follows the names, not guesses:

    Pelvis / Hip / 골반                    Torso / Chest / Body / Spine / 몸통 / 가슴
    Neck / 목                              Head / 머리
    Shoulder / 어깨          (each side)   UpperArm / Arm / 위팔 / 상완 / 팔         (each side)
    Forearm / LowerArm / 아래팔 / 하완      Hand / 손
    Thigh / UpperLeg / Leg / 허벅지 / 다리   Shin / Calf / LowerLeg / 정강이 / 종아리
    Foot / 발

Side: .L / .R, _L / _R, Left / Right, 왼 / 오른, 좌 / 우 anywhere in the name - or, without one, which side of the
body the part is on (+X = the left of a body facing -Y).  Case, spaces, '_', '-', '.' and Blender's .001 endings do
not matter; several parts with the same name go on the same bone (armour plates on the forearm: "Forearm.L",
"Forearm.L.001", "Forearm_L_plate").  A part whose name says nothing rides the bone of the named part it is nearest.

Each joint is where the two parts meet (the middle of where they touch, or of their closest points).  Bones: root,
pelvis, torso, neck, head, shoulder / upper_arm / forearm / hand, thigh / shin / foot (.L / .R) - the ones the parts
have.  IK on the arms (hand target, elbow pole behind) and the legs (foot target, knee pole in front); a dead straight
limb gets its middle joint a hair bent so the IK knows which way.  The rig is a Mecha rig: Turn Limit, Link,
Auto Animation (the legs walk), the Unreal export all work on it."""
from __future__ import annotations

import json
import re

import bpy
import numpy as np

# role -> keywords (checked longest first; the first role whose keyword is in the name wins)
ROLES = (
    ('forearm', ('forearm', 'lowerarm', 'lower_arm', 'armlower', '아래팔', '하완', '전완')),
    ('upper_arm', ('upperarm', 'upper_arm', 'armupper', '위팔', '상완', '윗팔')),
    ('shin', ('shin', 'calf', 'lowerleg', 'lower_leg', 'legslower', '정강이', '종아리', '아랫다리')),
    ('thigh', ('thigh', 'upperleg', 'upper_leg', '허벅지', '윗다리')),
    ('shoulder', ('shoulder', 'clavicle', '어깨')),
    ('pelvis', ('pelvis', 'hips', 'hip', 'waist', '골반', '허리')),
    ('neck', ('neck', '목')),
    ('head', ('head', '머리')),
    ('hand', ('hand', 'fist', '손')),
    ('foot', ('foot', 'feet', '발')),
    ('spine', ('abdomen', 'belly', 'stomach', 'spine', 'abs', '복부', '배')),
    ('torso', ('torso', 'chest', 'body', 'trunk', '몸통', '가슴', '상체')),
    ('upper_arm', ('arm', '팔')),
    ('thigh', ('leg', '다리')),
)
SIDED = {'shoulder', 'upper_arm', 'forearm', 'hand', 'thigh', 'shin', 'foot'}
ARM = ('shoulder', 'upper_arm', 'forearm', 'hand')
LEG = ('thigh', 'shin', 'foot')
PARENT = {'spine': 'pelvis', 'torso': 'spine', 'neck': 'torso', 'head': 'neck', 'shoulder': 'torso', 'upper_arm': 'shoulder',
          'forearm': 'upper_arm', 'hand': 'forearm', 'thigh': 'pelvis', 'shin': 'thigh', 'foot': 'shin'}


def _clean(name):
    return re.sub(r'\.\d{3}$', '', name)


def tokens(name):
    """The words of a name: camelCase split, any of ' _-.' and digits apart, lower case."""
    n = _clean(name)
    n = re.sub(r'([a-z])([A-Z])', r'\1 \2', n)
    return [t for t in re.split(r'[^0-9a-zA-Z\uac00-\ud7a3]+|\d+', n.lower()) if t]


def side_of(name):
    """'L' / 'R' / None from the name."""
    tk = tokens(name)
    n = _clean(name)
    if any(t in {'l', 'left', 'lt'} for t in tk) or '왼' in n or '좌' in n:
        return 'L'
    if any(t in {'r', 'right', 'rt'} for t in tk) or '오른' in n or '우' in n:
        return 'R'
    return None


def role_of(name):
    """The body part the name says, or None.  A long English key may be inside a word (UpperArm, LeftForearm); a
    short one must be a word of its own ("Armor" is not an arm); a Korean one anywhere."""
    tk = tokens(name)
    joined = ''.join(tk)
    n = _clean(name)
    for role, keys in ROLES:
        for k in keys:
            if re.match(r'[\uac00-\ud7a3]', k):
                if k in n:
                    return role
            elif len(k) >= 6 or '_' in k:
                if k.replace('_', '') in joined:
                    return role
            elif k in tk:
                return role
    return None


def bone_name(role, side):
    return f'{role}.{side}' if role in SIDED else role


def read_names(context, parts):
    """{bone name: [parts]} and [parts no name fits], the sides of unsided limb parts from where they are."""
    from . import rigging as rg
    groups, unknown = {}, []
    pts = {p.name: rg.world_points(context, p) for p in parts}
    mid = [p for p in parts if role_of(p.name) in {'pelvis', 'torso', 'neck', 'head'}]
    allc = np.concatenate([pts[p.name] for p in (mid or parts) if len(pts[p.name])]) if parts else np.zeros((1, 3))
    x0 = float(0.5 * (allc[:, 0].min() + allc[:, 0].max())) if len(allc) else 0.0
    for p in parts:
        r = role_of(p.name)
        if r is None:
            unknown.append(p)
            continue
        s = None
        if r in SIDED:
            s = side_of(p.name)
            if s is None:
                W = pts[p.name]
                s = 'L' if (len(W) and float(W[:, 0].mean()) > x0) else 'R'
        groups.setdefault(bone_name(r, s), []).append(p)
    return groups, unknown, pts, x0


def _surface(context, objs):
    """A BVH of the parts' surfaces (world space)."""
    from mathutils.bvhtree import BVHTree
    V, F, base = [], [], 0
    dg = context.evaluated_depsgraph_get()
    for o in objs:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        try:
            M = o.matrix_world
            V.extend(M @ v.co for v in me.vertices)
            F.extend([base + i for i in p.vertices] for p in me.polygons)
            base += len(me.vertices)
        finally:
            ev.to_mesh_clear()
    return BVHTree.FromPolygons(V, F) if F else None


def _meet(A, tree_b, tol, apart=None):
    """Where the child part (its points ``A``) meets its parent (``tree_b``, its surface): the middle of the child's
    points on or inside the parent (or the nearest ones) and of their places on the parent's surface.  Farther apart
    than ``apart`` (the parts laid out apart, not put together): the child's own end nearest the parent."""
    from mathutils import Vector
    sa = A[:: max(1, len(A) // 3000)]
    near_pts, d = [], []
    for v in sa:
        hit = tree_b.find_nearest(Vector(v))
        if hit[0] is None:
            d.append(np.inf)
            near_pts.append(v)
            continue
        inside = (Vector(v) - hit[0]).dot(hit[1]) < 0
        d.append(0.0 if inside else hit[3])
        near_pts.append(np.array(hit[0]))
    d = np.array(d)
    near_pts = np.array(near_pts)
    dmin = float(d.min())
    if apart is not None and dmin > apart:
        end = sa[d <= dmin + 0.1 * float(np.ptp(sa, axis=0).max())]
        return end.mean(0)
    k = d <= dmin + tol
    return 0.5 * (sa[k].mean(0) + near_pts[k].mean(0))


def build(context, parts, seamless=False):
    """The rig for the named parts.  ``seamless``: the parts bent by weights (the same at both sides of every cut,
    blended over the joints) - the cuts never open; else each part rides its bone stiff.  Returns (armature, report)."""
    from . import rigging as rg
    parts = [p for p in parts if p.type == 'MESH']
    groups, unknown, pts, x0 = read_names(context, parts)
    if not groups:
        raise RuntimeError('No part is named as a body part (Pelvis, Torso, Head, UpperArm.L, Thigh.R ...)')
    G = {b: np.concatenate([pts[p.name] for p in ps if len(pts[p.name])]) for b, ps in groups.items()}
    allV = np.concatenate(list(G.values()))
    ground = float(allV[:, 2].min())
    size = float(np.ptp(allV, axis=0).max()) or 1.0
    tol = 0.01 * size

    def role(b):
        return b.split('.')[0]

    def side(b):
        return b.split('.')[1] if '.' in b else None

    def parent_of(b):
        """The nearest named bone up the body (a missing link skipped: no shoulder - the arm on the torso)."""
        r, s = role(b), side(b)
        p = PARENT.get(r)
        while p is not None:
            cand = bone_name(p, s) if p in SIDED else p
            if cand in G:
                return cand
            p = PARENT.get(p)
        core = [c for c in ('pelvis', 'spine', 'torso') if c in G]
        if core and r == core[0]:
            return None                          # (the body's own root: the lowest of pelvis / spine / torso)
        for top in ('torso', 'spine', 'pelvis'):  # (no pelvis: the legs on the torso, and so on)
            if top in G and top != b:
                return top
        return None
    parent = {b: parent_of(b) for b in G}
    heads, tails = {}, {}
    trees = {}
    for b in G:
        P = parent[b]
        W = G[b]
        if P is None:
            heads[b] = 0.5 * (W.min(0) + W.max(0))
            continue
        if P not in trees:
            trees[P] = _surface(context, groups[P])
        heads[b] = _meet(W, trees[P], tol, 0.05 * size) if trees[P] is not None else 0.5 * (W.min(0) + W.max(0))
    kids = {b: [k for k, p in parent.items() if p == b] for b in G}
    for b in G:
        W, h = G[b], heads[b]
        r = role(b)
        ks = [k for k in kids[b] if role(k) in {'torso', 'neck', 'head', 'upper_arm', 'forearm', 'hand', 'shin',
                                                 'foot'} and (r != 'torso' or role(k) in {'neck', 'head'})]
        if r == 'pelvis':                        # (up: toward the spine / torso)
            t = heads['spine'] if 'spine' in G else heads['torso'] if 'torso' in G else h + np.array([0, 0, 0.15 * size])
        elif r == 'spine':
            t = heads['torso'] if 'torso' in G else np.array([h[0], h[1], W[:, 2].max()])
        elif r == 'torso':
            t = heads[ks[0]] if ks else np.array([h[0], h[1], W[:, 2].max()])
        elif r in {'head'}:
            t = np.array([h[0], h[1], max(W[:, 2].max(), h[2] + 1e-3)])
        elif r == 'foot':                         # (to the toe: the farthest point forward, low)
            low = W[W[:, 2] <= W[:, 2].min() + 0.3 * max(np.ptp(W[:, 2]), 1e-6)]
            t = low[np.argmin(low[:, 1])]
            t = np.array([t[0], t[1], h[2] if h[2] - ground < 0.5 * np.ptp(W[:, 2]) else t[2]])
        elif ks:
            t = np.mean([heads[k] for k in ks], axis=0)
        else:                                     # (a tip: its farthest point)
            t = W[np.argmax(np.linalg.norm(W - h, axis=1))]
        if np.linalg.norm(t - h) < 1e-3 * size:
            t = h + np.array([0, 0, 0.05 * size])
        heads[b], tails[b] = h, t
    # limbs: (upper, lower, end) bones and the way the middle joint bends
    limbs = []
    for s in ('L', 'R'):
        for up, lo, end, bend in (('upper_arm', 'forearm', 'hand', (0.0, 1.0, 0.0)),
                                  ('thigh', 'shin', 'foot', (0.0, -1.0, 0.0))):
            u, l_, e = f'{up}.{s}', f'{lo}.{s}', f'{end}.{s}'
            if u in G and l_ in G and e in G:
                limbs.append((u, l_, e, np.array(bend)))
    for u, l_, e, bend in limbs:                 # (a limb not bent the way it bends - knee forward, elbow back -
        a, m, f = heads[u], heads[l_], heads[e]  #  its middle joint a hair that way, so the IK knows)
        ab = f - a
        t = float((m - a) @ ab / max(ab @ ab, 1e-12))
        off = m - (a + t * ab)
        if float(off @ bend) < 0.02 * np.linalg.norm(ab):
            heads[l_] = m + bend * (0.03 * np.linalg.norm(ab) - float(off @ bend))
            tails[u] = heads[l_]
    ob = rg._new_armature(context, 'Mecha_Rig')
    ob[rg.RIG_KEY] = 'MECHA'
    ob['mch_named'] = True
    body = 'pelvis' if 'pelvis' in G else ('torso' if 'torso' in G else next(iter(G)))
    ob['mch_body_bone'] = body
    ob['mch_x0'] = x0
    order = sorted(G, key=lambda b: (0 if parent[b] is None else 1, len(_chain(b, parent))))
    with rg._Edit(context, ob) as ebs:
        c = heads[body]
        rg._bone(ebs, 'root', (c[0], c[1], ground), (c[0], c[1] - 0.15 * size, ground), deform=False)
        for b in order:
            rg._bone(ebs, b, heads[b], tails[b], 'root')
        for b in order:
            if parent[b] is not None:
                ebs[b].parent = ebs[parent[b]]
        for u, l_, e, bend in limbs:
            f = ebs[e]
            mid = heads[l_]
            ab = heads[e] - heads[u]
            tt = float((mid - heads[u]) @ ab / max(ab @ ab, 1e-12))
            off = mid - (heads[u] + tt * ab)
            if float(off @ bend) < 0.5 * np.linalg.norm(off) or np.linalg.norm(off) < 1e-6:
                off = bend                       # (the pole the way the joint bends, not off to a side)
            off = off / np.linalg.norm(off) * 0.5 * float(np.linalg.norm(ab))
            rg._limb_ik_bones(ebs, l_, e, f.head.copy(), f.tail.copy(), mid, tuple(off), 'root')
    if not seamless:
        for b, ps in groups.items():
            for p in ps:
                rg.attach(p, ob, b)
    # the unnamed parts: on the bone of the named part nearest them
    from mathutils.kdtree import KDTree
    kd_src = [(b, v) for b, W in G.items() for v in W[:: max(1, len(W) // 800)]]
    kd = KDTree(len(kd_src))
    for i, (_b, v) in enumerate(kd_src):
        kd.insert(v, i)
    kd.balance()
    rode = {}
    for p in unknown:
        W = pts[p.name]
        if not len(W):
            continue
        votes = {}
        for v in W[:: max(1, len(W) // 200)]:
            _c, i, _d = kd.find(v)
            votes[kd_src[i][0]] = votes.get(kd_src[i][0], 0) + 1
        b = max(votes, key=votes.get)
        if not seamless:
            rg.attach(p, ob, b)
        rode[p.name] = b
    offs = {}
    for u, l_, e, _bend in limbs:
        pb = ob.data.bones.get(l_ + '_pole')
        if pb is not None:
            offs[l_] = list(pb.head_local - ob.data.bones[l_].head_local)
    ob['mch_pole_off'] = offs
    errs = {}
    for u, l_, e, _bend in limbs:
        errs[e] = rg._limb_ik(context, ob, l_, e, 2)
    ob['mch_ik_err'] = {k: float(v[0]) for k, v in errs.items()}
    legs = [e for _u, _l, e, _b in limbs if e.startswith('foot')]
    ob['mch_legs'] = json.dumps(legs)
    lens = [float(np.linalg.norm(heads[e] - heads[u])) for u, _l, e, _b in limbs if e.startswith('foot')]
    ob['mch_leg_len'] = float(min(lens)) if lens else 0.3 * size
    rg.controls(ob)
    if seamless:
        owner = {p.name: b for b, ps in groups.items() for p in ps}
        owner.update(rode)
        skin(context, ob, parts, owner)
    return ob, dict(bones=sorted(G), parts={b: [p.name for p in ps] for b, ps in groups.items()}, rode=rode,
                    ik=[e for _u, _l, e, _b in limbs])


def skin(context, arm, parts, owner, blend=None):
    """0.24.337 (user: a body cut into parts "티 안 나게") the parts bent smoothly with their cuts shut: each part on its
    own bone, and near a cut blended with the bone of the part on the other side - half and half on the cut itself (the
    same on both sides: the cut never opens), its own bone again ``blend`` away (a smooth fall-off).  No bone that is
    merely near (a hand hanging by the thigh) pulls on a part.  The parts stay separate objects (Armature modifier)."""
    from mathutils.kdtree import KDTree
    pts = {p.name: np.array([p.matrix_world @ v.co for v in p.data.vertices]) for p in parts}
    allp = np.concatenate([v for v in pts.values() if len(v)])
    H = float(np.ptp(allp[:, 2])) or 1.0
    blend = blend if blend is not None else 0.04 * H
    tol = 1e-4 * H
    trees = {}
    for p in parts:
        kd = KDTree(len(pts[p.name]))
        for i, v in enumerate(pts[p.name]):
            kd.insert(v, i)
        kd.balance()
        trees[p.name] = kd
    # the cut points of each part, by the part (bone) on the other side
    cuts = {p.name: {} for p in parts}
    for p in parts:
        lo, hi = pts[p.name].min(0) - tol, pts[p.name].max(0) + tol
        for q in parts:
            if q is p or owner.get(q.name) == owner.get(p.name):
                continue
            ql, qh = pts[q.name].min(0), pts[q.name].max(0)
            if (ql > hi).any() or (qh < lo).any():
                continue
            shared = [v for v in pts[p.name] if trees[q.name].find(v)[2] < tol]
            if shared:
                cuts[p.name].setdefault(owner[q.name], []).extend(shared)
    for p in parts:
        own = owner[p.name]
        mw = p.matrix_world.copy()
        for m in [m for m in p.modifiers if m.type == 'ARMATURE']:
            p.modifiers.remove(m)
        names = {own} | set(cuts[p.name])
        for vg in [vg for vg in p.vertex_groups if vg.name in names or vg.name in arm.data.bones]:
            p.vertex_groups.remove(vg)
        vgs = {n: p.vertex_groups.new(name=n) for n in names}
        P = pts[p.name]
        share = {}
        for n, S_ in cuts[p.name].items():
            kd = KDTree(len(S_))
            for i, v in enumerate(S_):
                kd.insert(v, i)
            kd.balance()
            d = np.array([kd.find(v)[2] for v in P])
            t = np.clip(d / blend, 0.0, 1.0)
            share[n] = 0.5 * (1.0 - (3 * t * t - 2 * t * t * t))        # (half on the cut, none blend away)
        rest = np.ones(len(P))
        for n, w in share.items():
            rest -= w
        rest = np.maximum(rest, 0.0)
        tot = rest + sum(share.values()) if share else rest
        for i in range(len(P)):
            vgs[own].add([i], float(rest[i] / tot[i]), 'REPLACE')
            for n, w in share.items():
                if w[i] > 1e-4:
                    vgs[n].add([i], float(w[i] / tot[i]), 'REPLACE')
        m = p.modifiers.new('Armature', 'ARMATURE')
        m.object = arm
        p.parent = arm
        p.parent_type = 'OBJECT'
        p.matrix_parent_inverse = arm.matrix_world.inverted()
        p.matrix_world = mw
        from . import rigging as rg
        p[rg.PART_KEY] = own
    return 'cuts'


def name_by_place(context, parts):
    """0.24.337 (the user's BODY_TEST: a body cut into 16 parts named Body_Split_001_Split ...) the parts named by
    where they are on a body standing up, facing -Y: the middle ones from the top - head, neck, chest (torso), belly
    (spine), hips (pelvis); each side's ones from the body out - the legs (below the hips) thigh, shin, foot; the arms
    shoulder, upper arm, forearm, hand.  A part with a piece on each side and none across the middle (both feet in
    one) is split in two first.  Returns {old name: new name}."""
    from . import rigging as rg
    import bmesh
    parts = [p for p in parts if p.type == 'MESH']
    allp = np.concatenate([rg.world_points(context, p) for p in parts])
    x0 = 0.5 * (allp[:, 0].min() + allp[:, 0].max())
    W = float(np.ptp(allp[:, 0])) or 1.0
    # (both sides in one part: split)
    out = []
    for p in parts:
        V = rg.world_points(context, p)
        if not len(V) or V[:, 0].min() > x0 - 0.02 * W or V[:, 0].max() < x0 + 0.02 * W:
            out.append(p)
            continue
        bm = bmesh.new()
        bm.from_mesh(p.data)
        bm.verts.ensure_lookup_table()
        M = p.matrix_world
        isl, seen = [], set()
        for v in bm.verts:
            if v.index in seen:
                continue
            stack, comp = [v], []
            seen.add(v.index)
            while stack:
                u = stack.pop()
                comp.append(u.index)
                for e in u.link_edges:
                    w = e.other_vert(u)
                    if w.index not in seen:
                        seen.add(w.index)
                        stack.append(w)
            isl.append(comp)
        xs = [np.mean([(M @ bm.verts[i].co).x for i in c]) for c in isl]
        cross = any(min((M @ bm.verts[i].co).x for i in c) < x0 - 0.02 * W < x0 + 0.02 * W
                    < max((M @ bm.verts[i].co).x for i in c) for c in isl)
        bm.free()
        if cross or not (any(x > x0 for x in xs) and any(x < x0 for x in xs)):
            out.append(p)
            continue
        right = {i for c, x in zip(isl, xs) if x < x0 for i in c}
        q = p.copy()
        q.data = p.data.copy()
        for coll in p.users_collection:
            coll.objects.link(q)
        for ob_, keep_right in ((p, False), (q, True)):
            bm = bmesh.new()
            bm.from_mesh(ob_.data)
            bm.verts.ensure_lookup_table()
            gone = [bm.verts[i] for i in range(len(bm.verts)) if (i in right) != keep_right]
            bmesh.ops.delete(bm, geom=gone, context='VERTS')
            bm.to_mesh(ob_.data)
            bm.free()
        out += [p, q]
    parts = out
    info = {}
    for p in parts:
        V = rg.world_points(context, p)
        c = 0.5 * (V.min(0) + V.max(0))
        info[p.name] = dict(c=c, lo=V.min(0), hi=V.max(0), n=len(V))
    mid = [p for p in parts if abs(info[p.name]['c'][0] - x0) < 0.05 * W]
    side = [p for p in parts if p not in mid]
    names = {}
    mid.sort(key=lambda p: -info[p.name]['c'][2])
    roles_mid = []
    if mid:
        roles_mid.append('Head')
        rest = mid[1:]
        if rest:
            wid = {p.name: float(info[p.name]['hi'][0] - info[p.name]['lo'][0]) for p in rest}
            if len(rest) >= 2 and wid[rest[0].name] < 0.6 * max(wid.values()):
                roles_mid.append('Neck')
            n_left = len(rest) - (len(roles_mid) - 1)
            tail = ['Chest', 'Belly', 'Pelvis'] if n_left >= 3 else (['Chest', 'Pelvis'] if n_left == 2 else ['Chest'])
            extra = n_left - len(tail)
            roles_mid += tail[:1] + ['Chest'] * max(0, extra) + tail[1:]
    for p, r in zip(mid, roles_mid):
        names[p.name] = r
    pel = next((p for p in mid if names.get(p.name) == 'Pelvis'), mid[-1] if mid else None)
    hip_z = float(info[pel.name]['c'][2]) if pel is not None else float(np.median(allp[:, 2]))
    hip_half = (0.5 * float(info[pel.name]['hi'][0] - info[pel.name]['lo'][0]) if pel is not None else 0.25 * W)
    torso_c = np.array([x0, float(np.mean(allp[:, 1])), hip_z])
    chest = next((p for p in mid if names.get(p.name) == 'Chest'), None)
    chest_c = info[chest.name]['c'] if chest is not None else torso_c
    for sd, keep in (('L', lambda x: x > x0), ('R', lambda x: x < x0)):
        mine = [p for p in side if keep(info[p.name]['c'][0])]
        # (legs: under the hips AND within the hips' width - hands hanging down beside the thighs are outside it)
        legs = [p for p in mine if info[p.name]['c'][2] < hip_z and abs(info[p.name]['c'][0] - x0) < hip_half * 1.6]
        arms = [p for p in mine if p not in legs]
        legs.sort(key=lambda p: -info[p.name]['c'][2])
        arms.sort(key=lambda p: np.linalg.norm(info[p.name]['c'] - chest_c))
        for p, r in zip(legs, {1: ['Thigh'], 2: ['Thigh', 'Shin']}.get(len(legs), ['Thigh', 'Shin', 'Foot']
                                                                         + ['Foot'] * (len(legs) - 3))):
            names[p.name] = f'{r}.{sd}'
        a_roles = {1: ['UpperArm'], 2: ['UpperArm', 'Forearm'], 3: ['UpperArm', 'Forearm', 'Hand']}.get(
            len(arms), ['Shoulder', 'UpperArm', 'Forearm', 'Hand'] + ['Hand'] * (len(arms) - 4))
        for p, r in zip(arms, a_roles):
            names[p.name] = f'{r}.{sd}'
    done = {}
    used = {}
    for p in parts:
        new = names.get(p.name)
        if new is None:
            continue
        k = used.get(new, 0)
        used[new] = k + 1
        old = p.name
        p.name = new if k == 0 else f'{new}.{k:03d}'
        done[old] = p.name
    return done


def _chain(b, parent):
    out = []
    while b is not None and b not in out:
        out.append(b)
        b = parent.get(b)
    return out


def draw_help(layout):
    col = layout.column(align=True)
    col.label(text='Name the parts (any of these; .L / .R or Left / Right):', icon='INFO')
    for t in ('Pelvis, Torso (Chest), Neck, Head',
              'Shoulder, UpperArm, Forearm, Hand',
              'Thigh, Shin, Foot',
              '골반 몸통 목 머리 / 어깨 위팔 아래팔 손 / 허벅지 정강이 발'):
        col.label(text='   ' + t)
