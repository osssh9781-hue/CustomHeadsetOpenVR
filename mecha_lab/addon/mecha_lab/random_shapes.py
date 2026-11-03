"""0.24.95 Random Shapes (user: "박스를 꺼내면 랜덤 모양으로 나오게 하는 메뉴를 하나 만들어 주라 - 메테리얼 그런 거
있는 그 탭에다가 랜덤 다각 도형 소환 툴", then "다각형 소환 툴이랑 곡률이 들어간 도형 소환 툴"): the side panel's
**Shapes** page, two summon tools.

* **Summon Polygon** - a hard-surface block, all faces flat: **Block** (a box, some corners cut), **Prism** (3 - 10
  sides), **Wedge** (a ramp / a slope), **Step** (L, T, U, stairs, a notch), **Shard** (uneven sides, cut at angles);
  **Slices** (up to that many flat cuts at an angle), **Chamfer** (some edges cut flat), **Taper** (the top smaller)
* **Summon Curved** - shapes with curvature: **Rounded** (a block with round corners, its rims rounded now and then),
  **Cylinder** (a cylinder, a pill, an oval, tapered now and then), **Dome** (turned on a lathe: a dome, a capsule, a
  bullet, a cap, tiers, a spool), **Arch** (a bar bent round an arc), **Curve Ramp** (a slope with a round or hollow
  curve); **Slices**, **Fillet** (how round the rims), **Smooth** (segments round a full circle)
* **Mix** (each kind now and then), **Size** (the longest side), **Count** (several in a row to pick from)
* **Reroll Selected**: the selected random shapes get a new shape of their own family (each where it is - place,
  turn, size, materials kept)

Every shape is a clean closed solid (each edge between two faces, normals out, one piece) at the 3D cursor - ready
for the Cut / Boolean tools - its own hard lines in the Edge Memory (Sharp + crease): Polygon shapes flat shaded,
Curved ones smooth with the hard lines sharp.  The seed is kept on the object (``mch_rshape``) and shown in F9 (the
same seed = the same shapes)."""
from __future__ import annotations

import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

KINDS = (('MIX', 'Mix', 'Any of the kinds'),
         ('BLOCK', 'Block', 'A box, some of its corners cut off'),
         ('PRISM', 'Prism', 'A prism of 3 to 10 sides'),
         ('WEDGE', 'Wedge', 'A ramp / a slope seen from the side'),
         ('STEP', 'Step', 'L, T, U, stairs or a notch'),
         ('SHARD', 'Shard', 'Uneven sides, cut at angles'))
KIND_IDS = tuple(k[0] for k in KINDS[1:])
MIX_WEIGHTS = {'BLOCK': 3, 'PRISM': 2, 'WEDGE': 2, 'STEP': 2, 'SHARD': 2}
CURVE_KINDS = (('MIX', 'Mix', 'Any of the round kinds'),
               ('ROUNDED', 'Rounded', 'A block with round corners, its rims rounded now and then'),
               ('CYLINDER', 'Cylinder', 'A cylinder, a pill or an oval - tapered now and then'),
               ('DOME', 'Dome', 'Turned on a lathe: a dome, a capsule, a bullet, a cap, tiers, a spool'),
               ('ARCH', 'Arch', 'A bar bent round an arc: a bracket, a horseshoe'),
               ('RAMP', 'Curve Ramp', 'A slope seen from the side, its top a round or a hollow curve'))
CURVE_IDS = tuple(k[0] for k in CURVE_KINDS[1:])
CURVE_MIX = {'ROUNDED': 3, 'CYLINDER': 2, 'DOME': 2, 'ARCH': 2, 'RAMP': 2}
FAMILIES = (('POLY', 'Polygon', 'Flat faces only'), ('CURVE', 'Curved', 'Shapes with curvature'))
TAG = 'mch_rshape'                    # on the object: {'seed', 'kind', 'family'} - what Reroll looks for
NAME = 'MCH_Shape'
TRIES = 12
LAST = {'tries': 0}                  # (how many tries the last shape took - the tests read it)


# --- 2D outlines (counter-clockwise, about the origin) ------------------------------------------------------------

def _rect(w, d):
    return [(-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)]


def _cut_corners(pts, rng, n_cut, frac):
    """Some corners of a convex outline cut off (a chamfer of ``frac`` of the shorter side next to it)."""
    n = len(pts)
    which = set(rng.sample(range(n), min(n, n_cut)))
    out = []
    for i, p in enumerate(pts):
        if i not in which:
            out.append(p)
            continue
        a, c = Vector(pts[i - 1]), Vector(pts[(i + 1) % n])
        pv = Vector(p)
        la, lc = (a - pv).length, (c - pv).length
        t = frac * min(la, lc) * rng.uniform(0.6, 1.0)
        out.append(tuple(pv + (a - pv).normalized() * t))
        out.append(tuple(pv + (c - pv).normalized() * t))
    return out


def outline_block(rng):
    w, d = rng.uniform(0.55, 1.0), rng.uniform(0.45, 1.0)
    pts = _rect(w, d)
    n_cut = rng.choice((0, 1, 1, 2, 2, 4))
    return _cut_corners(pts, rng, n_cut, rng.uniform(0.18, 0.4)) if n_cut else pts


def outline_prism(rng, max_sides=10):
    n = rng.randint(3, max(3, max_sides))
    r = 0.5
    a0 = rng.uniform(0, 2 * math.pi / n)
    pts = [(r * math.cos(a0 + 2 * math.pi * i / n), r * math.sin(a0 + 2 * math.pi * i / n)) for i in range(n)]
    sx = rng.choice((1.0, 1.0, rng.uniform(0.6, 1.0)))
    return [(x * sx, y) for x, y in pts]


def outline_wedge(rng):
    """Seen from the side (x along, y up): a ramp, a trapezoid, a ramp with a flat top."""
    L, H = 1.0, rng.uniform(0.35, 0.8)
    v = rng.choice(('ramp', 'trap', 'flat', 'nose'))
    if v == 'ramp':
        lo = rng.uniform(0.0, 0.25) * H
        return [(0, 0), (L, 0), (L, H), (0, lo)] if lo > 0.02 else [(0, 0), (L, 0), (L, H)]
    if v == 'trap':
        a, b = rng.uniform(0.1, 0.35), rng.uniform(0.1, 0.35)
        return [(0, 0), (L, 0), (L - b * L, H), (a * L, H)]
    if v == 'flat':
        t = rng.uniform(0.3, 0.6)
        return [(0, 0), (L, 0), (L, H), (L * t, H), (0, H * rng.uniform(0.15, 0.45))]
    tip = rng.uniform(0.3, 0.6) * H                       # a nose: both ends sloped
    return [(0, tip * 0.4), (L * 0.2, 0), (L, 0), (L, H), (L * 0.35, H)]


def outline_step(rng):
    """Right-angled outlines with a corner or more going in."""
    w, d = 1.0, rng.uniform(0.55, 1.0)
    a, b = rng.uniform(0.3, 0.6), rng.uniform(0.3, 0.6)
    v = rng.choice(('L', 'T', 'U', 'stairs', 'notch'))
    if v == 'L':
        return [(0, 0), (w, 0), (w, d * b), (w * a, d * b), (w * a, d), (0, d)]
    if v == 'T':
        s = w * rng.uniform(0.25, 0.4)
        return [(w / 2 - s / 2, 0), (w / 2 + s / 2, 0), (w / 2 + s / 2, d * b), (w, d * b), (w, d), (0, d),
                (0, d * b), (w / 2 - s / 2, d * b)]
    if v == 'U':
        s = w * rng.uniform(0.2, 0.32)
        return [(0, 0), (w, 0), (w, d), (w - s, d), (w - s, d * b), (s, d * b), (s, d), (0, d)]
    if v == 'stairs':                                   # (steps going down to the left)
        n = rng.randint(2, 3)
        pts = [(0, 0), (w, 0), (w, d)]
        for s in range(n - 1, 0, -1):
            x = w * s / n
            pts += [(x, d * (s + 1) / n), (x, d * s / n)]
        pts.append((0, d / n))
        return pts
    nw, nd = w * rng.uniform(0.25, 0.45), d * rng.uniform(0.2, 0.4)       # a notch bitten out of one side
    c = rng.uniform(0.3, 0.7) * w
    return [(0, 0), (w, 0), (w, d), (c + nw / 2, d), (c + nw / 2, d - nd), (c - nw / 2, d - nd), (c - nw / 2, d),
            (0, d)]


def outline_shard(rng):
    """A convex outline of uneven sides (random corners round a circle, the hull)."""
    n = rng.randint(4, 7)
    angs = sorted(rng.uniform(0, 2 * math.pi) for _ in range(n))
    pts = [(math.cos(a) * rng.uniform(0.7, 1.0) * 0.5, math.sin(a) * rng.uniform(0.7, 1.0) * 0.5) for a in angs]
    return _hull(pts)


def _clean(pts, eps=1e-6):
    out = []
    for p in pts:
        if not out or (Vector(p) - Vector(out[-1])).length > eps:
            out.append(p)
    if len(out) > 2 and (Vector(out[0]) - Vector(out[-1])).length <= eps:
        out.pop()
    i = 0                                               # (straight corners dropped)
    while len(out) > 3 and i < len(out):
        a, b, c = Vector(out[i - 1]), Vector(out[i]), Vector(out[(i + 1) % len(out)])
        if abs((b - a).cross(c - b)) < 1e-9:
            out.pop(i)
        else:
            i += 1
    return out


def _hull(pts):
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


def _ccw(pts):
    s = sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1] for i in range(len(pts)))
    return pts if s > 0 else list(reversed(pts))


# --- the solid -----------------------------------------------------------------------------------------------------

def _prism(bm, pts, depth, taper=1.0):
    """The outline in XY (centred) pushed up along Z by ``depth``; the top ``taper`` times as big (round the centre:
    each side stays flat)."""
    pts = _ccw(pts)
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    lo = [bm.verts.new((x - cx, y - cy, -depth / 2)) for x, y in pts]
    hi = [bm.verts.new(((x - cx) * taper, (y - cy) * taper, depth / 2)) for x, y in pts]
    n = len(pts)
    bm.faces.new(list(reversed(lo)))
    bm.faces.new(hi)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))


def _closed(bm):
    return all(len(e.link_faces) == 2 for e in bm.edges) and all(f.calc_area() > 1e-9 for f in bm.faces)


def _islands(bm):
    seen, n = set(), 0
    for v in bm.verts:
        if v in seen:
            continue
        n += 1
        stack = [v]
        seen.add(v)
        while stack:
            w = stack.pop()
            for e in w.link_edges:
                o = e.other_vert(w)
                if o not in seen:
                    seen.add(o)
                    stack.append(o)
    return n


def _slice(bm, rng, keep_min=0.45):
    """One flat cut at an angle through the solid: the part beyond it gone, the hole closed with one face.  Returns
    the new solid (``bm`` freed) or ``bm`` itself when no cut kept at least ``keep_min`` of it in one piece."""
    vol0 = bm.calc_volume()
    for _t in range(6):
        n = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.3, 1.0)))
        if n.length < 0.2:
            continue
        n.normalize()
        work = bm.copy()
        d = [v.co.dot(n) for v in work.verts]
        lo, hi = min(d), max(d)
        off = hi - (hi - lo) * rng.uniform(0.1, 0.32)
        geom = list(work.verts) + list(work.edges) + list(work.faces)
        bmesh.ops.bisect_plane(work, geom=geom, dist=1e-6, plane_co=n * off, plane_no=n, clear_outer=True)
        open_e = [e for e in work.edges if len(e.link_faces) < 2]
        if open_e:
            bmesh.ops.holes_fill(work, edges=open_e, sides=0)
            bmesh.ops.remove_doubles(work, verts=list(work.verts), dist=1e-6)
            if _closed(work) and _islands(work) == 1 and work.calc_volume() > keep_min * vol0:
                bm.free()
                return work
        work.free()
    return bm


def _chamfer(bm, rng, amount, size):
    """Some edges cut flat (a chamfer, one segment)."""
    edges = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(40)]
    if not edges or amount <= 0:
        return
    pick = rng.sample(edges, max(1, int(len(edges) * rng.uniform(0.15, 0.45))))
    shortest = min(e.calc_length() for e in bm.edges)
    w = min(size * 0.06 * amount * rng.uniform(0.6, 1.2), shortest * 0.3)
    if w <= size * 1e-3:
        return
    bmesh.ops.bevel(bm, geom=pick, offset=w, offset_type='OFFSET', segments=1, profile=0.5, affect='EDGES',
                    clamp_overlap=True)


def _planar_ok(bm, tol=1e-4, quad_tol=None):
    """Every face of more than three corners flat (quads within ``quad_tol``: a round's strips may bend a hair)."""
    qt = tol if quad_tol is None else quad_tol
    for f in bm.faces:
        if len(f.verts) < 4:
            continue
        n, c = f.normal, f.calc_center_median()
        t = qt if len(f.verts) == 4 else tol
        if any(abs((v.co - c).dot(n)) > t for v in f.verts):
            return False
    return True


def build_poly(seed, kind='MIX', size=1.0, slices=2, chamfer=0.3, taper=0.3, max_sides=10):
    """A bmesh of one random Polygon shape (``seed`` decides it all), centred on the origin, its longest side ``size``.
    Returns (bm, the kind it became).  Every try is checked: closed, one piece, flat faces; the last fallback is the
    plain outline pushed up (always clean)."""
    rng = random.Random(seed)
    if kind == 'MIX':
        ks = list(MIX_WEIGHTS)
        kind = rng.choices(ks, weights=[MIX_WEIGHTS[k] for k in ks])[0]
    side = False
    if kind == 'BLOCK':
        pts, depth = outline_block(rng), rng.uniform(0.3, 1.0)
    elif kind == 'PRISM':
        pts, depth = outline_prism(rng, max_sides), rng.uniform(0.25, 1.0)
        side = rng.random() < 0.35                      # (a prism lying down: a beam)
    elif kind == 'WEDGE':
        pts, depth, side = outline_wedge(rng), rng.uniform(0.35, 0.9), True
    elif kind == 'STEP':
        pts, depth = outline_step(rng), rng.uniform(0.25, 0.8)
        side = rng.random() < 0.5
    else:
        pts, depth = outline_shard(rng), rng.uniform(0.3, 0.9)
    pts = _clean(pts)
    tp = 1.0
    if taper > 0 and kind in {'BLOCK', 'PRISM', 'SHARD'} and rng.random() < 0.55:
        tp = 1.0 - taper * rng.uniform(0.3, 0.8)
    n_sl = 0
    if slices > 0:
        n_sl = rng.randint(1 if kind == 'SHARD' else 0, slices)
    convex = kind in {'BLOCK', 'PRISM', 'SHARD'}
    sub = random.Random(rng.random())
    for attempt in range(TRIES + 1):
        bm = bmesh.new()
        _prism(bm, pts, depth, tp)
        if side:                                         # the outline seen from the side: stood up on its edge
            bmesh.ops.rotate(bm, verts=list(bm.verts), cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'X'))
        if attempt < TRIES:
            for _i in range(n_sl):
                bm = _slice(bm, sub, keep_min=0.5 if convex else 0.6)
            _chamfer(bm, sub, chamfer, 1.0)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        if _closed(bm) and _islands(bm) == 1 and _planar_ok(bm) and bm.calc_volume(signed=True) > 1e-6:
            break
        bm.free()
    LAST['tries'] = attempt
    _fit(bm, size)
    return bm, kind


# --- Curved shapes -------------------------------------------------------------------------------------------------

def _arc_n(turn, segs):
    """Segments for a round that turns by ``turn`` radians: as fine as ``segs`` round a full circle, at least 4 for a
    right angle (each step under the Edge Memory's 30 degrees - the round stays smooth, not lines)."""
    return max(2, math.ceil(turn / (2 * math.pi) * segs), math.ceil(turn / math.radians(22.5)))


def _fillet(pts, which, frac, segs):
    """The corners in ``which`` rounded: an arc touching both sides, ``frac`` of the shorter side next to it (0.5 at
    most: two rounds meet in the middle of a side).  A corner going in gets a hollow round."""
    m = len(pts)
    out = []
    for i, p in enumerate(pts):
        if i not in which:
            out.append(p)
            continue
        P, A, C = Vector(p), Vector(pts[i - 1]), Vector(pts[(i + 1) % m])
        u1, u2 = A - P, C - P
        l1, l2 = u1.length, u2.length
        if l1 < 1e-9 or l2 < 1e-9:
            out.append(p)
            continue
        u1.normalize()
        u2.normalize()
        th = math.acos(max(-1.0, min(1.0, u1.dot(u2))))
        if th < 1e-3 or th > math.pi - 1e-3:
            out.append(p)
            continue
        d = min(l1, l2) * min(frac, 0.5)
        ctr = P + (u1 + u2).normalized() * (d / math.cos(th / 2))
        t1, t2 = P + u1 * d, P + u2 * d
        a1 = math.atan2(t1.y - ctr.y, t1.x - ctr.x)
        a2 = math.atan2(t2.y - ctr.y, t2.x - ctr.x)
        da = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi        # (the short way round)
        r = (t1 - ctr).length
        n = _arc_n(abs(da), segs)
        out += [(ctr.x + r * math.cos(a1 + da * j / n), ctr.y + r * math.sin(a1 + da * j / n)) for j in range(n + 1)]
    return out


def _circle(rx, ry, segs, a0=0.0):
    return [(rx * math.cos(a0 + 2 * math.pi * i / segs), ry * math.sin(a0 + 2 * math.pi * i / segs))
            for i in range(segs)]


def outline_rounded(rng, segs):
    v = rng.choice(('rect', 'rect', 'stadium', 'L', 'D'))
    w, d = 1.0, rng.uniform(0.45, 0.9)
    if v == 'rect':
        pts = _rect(w, d)
        which = set(range(4)) if rng.random() < 0.5 else set(rng.sample(range(4), rng.randint(1, 3)))
        return _fillet(pts, which, rng.uniform(0.2, 0.5), segs)
    if v == 'stadium':
        return _fillet(_rect(w, d), {0, 1, 2, 3}, 0.5, segs)
    if v == 'D':
        return _fillet(_rect(w, d), {1, 2}, 0.5, segs)
    a, b = rng.uniform(0.35, 0.6), rng.uniform(0.35, 0.6)
    pts = [(0, 0), (w, 0), (w, d * b), (w * a, d * b), (w * a, d), (0, d)]
    return _fillet(pts, set(range(6)), rng.uniform(0.25, 0.45), segs)


def outline_cylinder(rng, segs):
    v = rng.choice(('circle', 'circle', 'oval', 'pill'))
    if v == 'circle':
        return _circle(0.5, 0.5, segs)
    if v == 'oval':
        return _circle(0.5, 0.5 * rng.uniform(0.55, 0.85), segs)
    return _fillet(_rect(1.0, rng.uniform(0.35, 0.6)), {0, 1, 2, 3}, 0.5, segs)


def outline_ramp(rng, segs):
    """Seen from the side (x along, y up): a quarter round, a hollow (cove) ramp, an S fairing, a round nose."""
    L, H = 1.0, rng.uniform(0.4, 0.85)
    v = rng.choice(('round', 'cove', 'scurve', 'nose'))
    n = _arc_n(math.pi / 2, segs)
    if v == 'round':                                         # (a quarter of an oval on a foot)
        foot = rng.uniform(0.0, 0.25) * H
        foot = foot if foot > 0.02 else 0.0
        arc = [(L * math.cos(math.pi / 2 * j / n), foot + (H - foot) * math.sin(math.pi / 2 * j / n))
               for j in range(n + 1)]
        return [(0, 0)] + ([(L, 0)] if foot else []) + arc
    if v == 'cove':                                          # (the top dips in)
        lo = rng.uniform(0.05, 0.3) * H
        arc = [(L * math.cos(math.pi / 2 * j / n), H - (H - lo) * math.sin(math.pi / 2 * j / n))
               for j in range(n + 1)]
        return [(0, 0), (L, 0)] + arc
    if v == 'scurve':
        lo = rng.uniform(0.1, 0.35) * H
        m = 2 * n
        top = [(L * (1 - j / m), lo + (H - lo) * (3 * (1 - j / m) ** 2 - 2 * (1 - j / m) ** 3)) for j in range(m + 1)]
        return [(0, 0), (L, 0)] + top
    pts = [(0, 0), (L, 0), (L, H), (0, H)]                  # a round nose: one end a half round
    return _fillet(pts, {2, 3}, 0.5, segs) if H < L else _fillet(pts, {0, 3}, 0.5, segs)


def _lathe(bm, prof, segs):
    """Turn a side profile [(radius, height)] (bottom to top) round Z: an end at radius 0 closes in a point, an end
    away from the axis with a flat face."""
    rings = []
    for r, z in prof:
        if r < 1e-6:
            rings.append([bm.verts.new((0.0, 0.0, z))])
        else:
            rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / segs), r * math.sin(2 * math.pi * i / segs), z))
                          for i in range(segs)])
    for a, b in zip(rings, rings[1:]):
        if len(a) == 1 and len(b) == 1:
            continue
        for i in range(segs):
            j = (i + 1) % segs
            if len(a) == 1:
                bm.faces.new((a[0], b[i], b[j]))
            elif len(b) == 1:
                bm.faces.new((a[i], a[j], b[0]))
            else:
                bm.faces.new((a[i], a[j], b[j], b[i]))
    if len(rings[0]) > 1:
        bm.faces.new(list(reversed(rings[0])))
    if len(rings[-1]) > 1:
        bm.faces.new(rings[-1])


def _quarter(r0, z0, r1, z1, n, bulge=True):
    """The points from (r0, z0) to (r1, z1) round a quarter of an oval (bulging out, or in)."""
    out = []
    for j in range(1, n + 1):
        t = math.pi / 2 * j / n
        if bulge:
            out.append((r1 + (r0 - r1) * math.cos(t), z0 + (z1 - z0) * math.sin(t)))
        else:
            out.append((r0 + (r1 - r0) * math.sin(t), z1 - (z1 - z0) * math.cos(t)))
    return out


def profile_dome(rng, segs):
    """A lathe profile [(r, z)] bottom to top (a flat bottom: it starts away from the axis; a round end: at it); and
    whether it may lie on its side."""
    n = _arc_n(math.pi / 2, segs)
    v = rng.choice(('dome', 'capsule', 'bullet', 'cap', 'tiers', 'spool'))
    R = 0.5
    if v == 'dome':
        h0 = rng.uniform(0.0, 0.4)
        return ([(R, 0)] + ([(R, h0)] if h0 > 0.02 else [])
                + _quarter(R, h0 if h0 > 0.02 else 0.0, 0.0, h0 + R * rng.uniform(0.6, 1.1), n)), False
    if v == 'capsule':
        h = rng.uniform(0.3, 1.2)
        bot = [(R * math.sin(math.pi / 2 * j / n), R - R * math.cos(math.pi / 2 * j / n)) for j in range(n + 1)]
        top = [(R * math.cos(math.pi / 2 * j / n), R + h + R * math.sin(math.pi / 2 * j / n)) for j in range(n + 1)]
        return bot + top, True
    if v == 'bullet':
        h = rng.uniform(0.3, 0.9)
        tip = rng.choice((0.0, rng.uniform(0.08, 0.2)))
        L = rng.uniform(0.6, 1.2)
        nose = [(tip + (R - tip) * (1 - (j / n) ** 1.6), h + L * j / n) for j in range(1, n + 1)]
        return [(R, 0), (R, h)] + nose, True
    if v == 'cap':
        rim, step = rng.uniform(0.04, 0.12), rng.uniform(0.75, 0.9)
        return [(R, 0), (R, rim), (R * step, rim)] + _quarter(R * step, rim, 0.0, rim + rng.uniform(0.12, 0.3), n), \
            False
    if v == 'tiers':                                        # a round base, a narrower tier on it, a low dome on top
        h1, r2, h2 = rng.uniform(0.15, 0.35), R * rng.uniform(0.45, 0.75), rng.uniform(0.25, 0.5)
        f = min(R - r2, h1) * 0.6                           # (the base's top rim rounded)
        c = r2 * 0.4
        return ([(R, 0), (R, h1 - f)] + _quarter(R, h1 - f, R - f, h1, n) + [(r2, h1), (r2, h1 + h2 - c)]
                + _quarter(r2, h1 + h2 - c, 0.0, h1 + h2, n)), False
    h = rng.uniform(0.5, 1.0)                               # a spool: hollow sides, flat ends
    waist = rng.uniform(0.55, 0.8)
    m = max(4, n * 2)
    return [(R * (1 - (1 - waist) * math.sin(math.pi * j / m)), h * j / m) for j in range(m + 1)], True


def arch(bm, rng, segs):
    """A bar of a (rounded) square section bent round an arc of 60 - 200 degrees."""
    w, h = rng.uniform(0.15, 0.35), rng.uniform(0.15, 0.4)
    sec = _rect(w, h)
    if rng.random() < 0.6:
        sec = _fillet(sec, set(range(4)) if rng.random() < 0.6 else {2, 3}, rng.uniform(0.2, 0.5), segs)
    sec = _ccw(_clean(sec))
    R = rng.uniform(0.25, 0.45) + w / 2
    A = math.radians(rng.uniform(60, 200))
    n = max(3, math.ceil(A / (2 * math.pi) * segs), math.ceil(A / math.radians(22.5)))
    rings = []
    for i in range(n + 1):
        a = A * i / n
        ca, sa = math.cos(a), math.sin(a)
        rings.append([bm.verts.new(((R + u) * ca, (R + u) * sa, v)) for u, v in sec])
    m = len(sec)
    for a, b in zip(rings, rings[1:]):
        for i in range(m):
            j = (i + 1) % m
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])


def _round_rims(bm, rng, amount, segs, both):
    """The rims of the top (and the bottom, ``both``) rounded: a bevel of round profile, ``amount`` of what fits."""
    if amount <= 0:
        return
    fs = [f for f in bm.faces if f.normal.z > 0.999] + ([f for f in bm.faces if f.normal.z < -0.999] if both else [])
    edges = list({e for f in fs for e in f.edges})
    if not edges:
        return
    zs = [v.co.z for v in bm.verts]
    hgt = max(zs) - min(zs)
    off = min(hgt * (0.45 if both else 0.9), 0.25) * amount * rng.uniform(0.5, 1.0)
    if off < 0.01 or off > hgt * 0.49 * (1 if both else 2):
        return
    bmesh.ops.bevel(bm, geom=edges, offset=off, offset_type='OFFSET', segments=_arc_n(math.pi / 2, segs),
                    profile=0.5, affect='EDGES', clamp_overlap=True)


def build_curve(seed, kind='MIX', size=1.0, slices=1, fillet=0.5, segs=32):
    """A bmesh of one random Curved shape, centred on the origin, its longest side ``size``.  (bm, the kind)."""
    rng = random.Random(seed)
    segs = max(8, int(segs))
    if kind == 'MIX':
        ks = list(CURVE_MIX)
        kind = rng.choices(ks, weights=[CURVE_MIX[k] for k in ks])[0]
    side = False
    pts = prof = None
    rims, both = 0.0, False
    tp = 1.0
    if kind == 'ROUNDED':
        pts, depth = outline_rounded(rng, segs), rng.uniform(0.25, 0.8)
        if fillet > 0 and rng.random() < 0.3 + 0.6 * fillet:
            rims, both = fillet, rng.random() < 0.4
    elif kind == 'CYLINDER':
        pts, depth = outline_cylinder(rng, segs), rng.uniform(0.2, 1.2)
        if rng.random() < 0.3:
            tp = rng.uniform(0.45, 0.85)
        if fillet > 0 and rng.random() < 0.3 + 0.6 * fillet:
            rims, both = fillet, rng.random() < 0.5
        side = rng.random() < 0.3
    elif kind == 'DOME':
        prof, side = profile_dome(rng, segs)
        side = side and rng.random() < 0.4
    elif kind == 'RAMP':
        pts, depth, side = outline_ramp(rng, segs), rng.uniform(0.35, 0.9), True
    else:                                                    # (an arch: lying flat or standing up, a gate)
        side = rng.random() < 0.5
    n_sl = rng.randint(0, slices) if slices > 0 else 0
    sub = random.Random(rng.random())
    if pts is not None:
        pts = _clean(pts)
    for attempt in range(TRIES + 1):
        bm = bmesh.new()
        if kind == 'ARCH':
            arch(bm, random.Random(seed + 1), segs)
        elif prof is not None:
            _lathe(bm, prof, segs)
        else:
            _prism(bm, pts, depth, tp)
            if attempt < TRIES and rims > 0:
                _round_rims(bm, sub, rims, segs, both)
        if side:
            bmesh.ops.rotate(bm, verts=list(bm.verts), cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'X'))
        if attempt < TRIES:
            for _i in range(n_sl):
                bm = _slice(bm, sub, keep_min=0.55)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        if (_closed(bm) and _islands(bm) == 1 and _planar_ok(bm, 1e-4, 2e-3)
                and bm.calc_volume(signed=True) > 1e-6):
            break
        bm.free()
    LAST['tries'] = attempt
    _fit(bm, size)
    return bm, kind


def build(seed, family='POLY', settings=None, size=None):
    """(bm, kind) of one random shape of ``family`` with the Shapes page's ``settings`` (None: the defaults)."""
    st = settings
    g = (lambda n, d: getattr(st, n, d)) if st is not None else (lambda n, d: d)
    sz = size or g('size', 1.0)
    if family == 'CURVE':
        return build_curve(seed, g('curve_kind', 'MIX'), sz, g('curve_slices', 1), g('fillet', 0.5),
                           g('segments', 32))
    return build_poly(seed, g('kind', 'MIX'), sz, g('slices', 2), g('chamfer', 0.3), g('taper', 0.3))


def _fit(bm, size):
    """Centred on the origin (its box), the longest side ``size``."""
    lo = Vector((min(v.co[i] for v in bm.verts) for i in range(3)))
    hi = Vector((max(v.co[i] for v in bm.verts) for i in range(3)))
    span = max(hi - lo) or 1.0
    s = size / span
    c = (lo + hi) / 2
    for v in bm.verts:
        v.co = (v.co - c) * s


def new_mesh(seed, settings, family='POLY', name=NAME, size=None):
    """A new mesh of one random shape: (mesh, kind).  Polygon: flat shaded; Curved: smooth, its hard lines sharp."""
    bm, kind = build(seed, family, settings, size)
    me = bpy.data.meshes.new(name)
    try:
        bm.to_mesh(me)
    finally:
        bm.free()
    me.polygons.foreach_set('use_smooth', [family == 'CURVE'] * len(me.polygons))
    try:
        from . import edge_memory
        edge_memory.mark_generated(me)               # (its own lines, like every part a tool makes: Sharp + crease)
    except Exception as ex:                          # (never in the way of the shape)
        print('Mecha: random shape edge memory:', ex)
    return me, kind


def is_shape(ob):
    return ob is not None and ob.type == 'MESH' and TAG in ob.keys()


def family_of(ob):
    try:
        f = str(ob[TAG].get('family', 'POLY'))
    except (AttributeError, KeyError, TypeError):
        f = 'POLY'
    return f if f in {'POLY', 'CURVE'} else 'POLY'


def _new_seed():
    return random.SystemRandom().randrange(1, 2 ** 31 - 1)


def _seed(base, i):
    return (base + i * 7919) % (2 ** 31 - 1) or 1


def layout_spots(count, gap):
    """Where ``count`` shapes go round the cursor: rows of 5 along X, the rows going back (-Y)."""
    cols = min(count, 5)
    rows = -(-count // cols)
    out = []
    for i in range(count):
        r, c = divmod(i, cols)
        out.append(Vector(((c - (cols - 1) / 2) * gap, -(r - (rows - 1) / 2) * gap, 0.0)))
    return out


# --- settings + operators ------------------------------------------------------------------------------------------

class MCH_PG_RandomShape(bpy.types.PropertyGroup):
    size: bpy.props.FloatProperty(name='Size', description='The longest side of a shape', default=1.0, min=0.01,
                                  soft_max=10.0, subtype='DISTANCE', unit='LENGTH')
    count: bpy.props.IntProperty(name='Count', description='How many shapes a Summon makes (in rows, to pick from)',
                                 default=1, min=1, max=25)
    # Polygon
    kind: bpy.props.EnumProperty(name='Polygon Kind', items=KINDS, default='MIX')
    slices: bpy.props.IntProperty(name='Slices', description='Up to this many flat cuts at an angle', default=2,
                                  min=0, max=4)
    chamfer: bpy.props.FloatProperty(name='Chamfer', description='Some edges cut flat: how wide', default=0.3,
                                     min=0.0, max=1.0, subtype='FACTOR')
    taper: bpy.props.FloatProperty(name='Taper', description='The top smaller than the bottom (now and then)',
                                   default=0.3, min=0.0, max=1.0, subtype='FACTOR')
    # Curved
    curve_kind: bpy.props.EnumProperty(name='Curved Kind', items=CURVE_KINDS, default='MIX')
    curve_slices: bpy.props.IntProperty(name='Slices', description='Up to this many flat cuts at an angle',
                                        default=1, min=0, max=4)
    fillet: bpy.props.FloatProperty(name='Fillet', description='How round the rims are (and how often)', default=0.5,
                                    min=0.0, max=1.0, subtype='FACTOR')
    segments: bpy.props.IntProperty(name='Smooth', description='Segments round a full circle (more = rounder)',
                                    default=32, min=8, max=128)


def _settings(context):
    return context.scene.mch_rshape


class MCH_OT_random_shape_add(bpy.types.Operator):
    """Summon a shape of a random form at the 3D cursor - Polygon (flat faces) or Curved (with curvature); the Shapes
    page's kind, Size, Count ..."""
    bl_idname = 'mch.random_shape_add'
    bl_label = 'Summon Random Shape'
    bl_options = {'REGISTER', 'UNDO'}
    family: bpy.props.EnumProperty(name='Family', items=FAMILIES, default='POLY')
    seed: bpy.props.IntProperty(name='Seed', description='The same seed makes the same shapes (0: new ones)',
                                default=0, min=0, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.scene is not None

    def execute(self, context):
        st = _settings(context)
        if self.seed == 0:
            self.seed = _new_seed()
        coll = context.collection if context.collection is not None else context.scene.collection
        base = context.scene.cursor.location.copy()
        made = []
        for i, off in enumerate(layout_spots(st.count, st.size * 1.6)):
            seed = _seed(self.seed, i)
            me, kind = new_mesh(seed, st, self.family)
            ob = bpy.data.objects.new(NAME, me)
            try:
                coll.objects.link(ob)
            except RuntimeError:
                context.scene.collection.objects.link(ob)
            ob.location = base + off
            ob[TAG] = {'seed': seed, 'kind': kind, 'family': self.family}
            made.append(ob)
        for o in context.selected_objects:
            o.select_set(False)
        for ob in made:
            ob.select_set(True)
        context.view_layer.objects.active = made[0]
        names = dict((k[0], k[1]) for k in KINDS + CURVE_KINDS)
        kinds = sorted({names.get(ob[TAG]['kind'], ob[TAG]['kind']) for ob in made})
        fam = 'curved' if self.family == 'CURVE' else 'polygon'
        self.report({'INFO'}, f'{len(made)} random {fam} shape{"s" if len(made) > 1 else ""}: {", ".join(kinds)}'
                              f' (seed {self.seed})')
        return {'FINISHED'}


class MCH_OT_random_shape_reroll(bpy.types.Operator):
    """The selected random shapes get a new random form, each of its own family (Polygon / Curved) and as big as it
    was, where it is (place, turn, scale, materials kept); the kind on the Shapes page decides what they become"""
    bl_idname = 'mch.random_shape_reroll'
    bl_label = 'Reroll Random Shapes'
    bl_options = {'REGISTER', 'UNDO'}
    seed: bpy.props.IntProperty(name='Seed', default=0, min=0, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and any(is_shape(o) for o in context.selected_objects)

    def execute(self, context):
        st = _settings(context)
        if self.seed == 0:
            self.seed = _new_seed()
        obs = [o for o in context.selected_objects if is_shape(o)]
        if not obs:
            self.report({'WARNING'}, 'Select a random shape (made with Summon) first')
            return {'CANCELLED'}
        n = 0
        for i, ob in enumerate(obs):
            seed = _seed(self.seed, i)
            old = ob.data
            if old.users > 1:
                continue                                 # (a linked copy: its twin would change too)
            fam = family_of(ob)
            dims = [max(v.co[a] for v in old.vertices) - min(v.co[a] for v in old.vertices) for a in range(3)] \
                if len(old.vertices) else [0.0]
            me, kind = new_mesh(seed, st, fam, old.name, size=max(dims) or None)   # (as big as the one it replaces)
            for m in old.materials:
                me.materials.append(m)
            ob.data = me
            if old.users == 0:
                bpy.data.meshes.remove(old)
            ob[TAG] = {'seed': seed, 'kind': kind, 'family': fam}
            n += 1
        if not n:
            self.report({'WARNING'}, 'Nothing rerolled (a shape shared by linked copies is left alone)')
            return {'CANCELLED'}
        self.report({'INFO'}, f'Rerolled {n} shape{"s" if n > 1 else ""} (seed {self.seed})')
        return {'FINISHED'}


class MCH_OT_random_shape_kind(bpy.types.Operator):
    """What the next random shapes of this family are (Summon, Reroll)"""
    bl_idname = 'mch.random_shape_kind'
    bl_label = 'Random Shape Kind'
    bl_options = {'INTERNAL'}
    family: bpy.props.EnumProperty(items=FAMILIES, default='POLY')
    kind: bpy.props.StringProperty(default='MIX')

    def execute(self, context):
        st = _settings(context)
        if self.family == 'CURVE':
            if self.kind in {k[0] for k in CURVE_KINDS}:
                st.curve_kind = self.kind
        elif self.kind in {k[0] for k in KINDS}:
            st.kind = self.kind
        return {'FINISHED'}


# --- the Shapes page (drawn side panel) and the sidebar panel -------------------------------------------------------

def page(context, x, width, k):
    """(items, content height) - the side panel's Shapes page, y measured down from 0 (as ``side_panel.content``)."""
    from . import side_panel as sp
    from . import mech_shader_ui as mu
    b = sp.Builder('SHAPES', x, width, k)
    st = _settings(context)
    obj_mode = context.mode == 'OBJECT'
    b.note(('note', 'A click: a new shape of a random form at the 3D cursor' if obj_mode else
            'Object Mode only (Tab out of Edit / Sculpt first)', False, None, None, None, True), x, width)
    mu.row(b, x, width, [mu.number(st, 'size', 'Size'), mu.number(st, 'count', 'Count')])

    def kinds(sx, sw, family, items, cur):
        cells = [mu._cell('tbtn', label, ('op', 'mch.random_shape_kind', {'family': family, 'kind': ident}),
                          on=cur == ident) for ident, label, _d in items]
        for i in range(0, len(cells), 3):
            mu.row(b, sx, sw, cells[i:i + 3])

    def poly(sx, sw):
        kinds(sx, sw, 'POLY', KINDS, st.kind)
        mu.row(b, sx, sw, [mu.number(st, 'slices', 'Slices')])
        mu.row(b, sx, sw, [mu.number(st, 'chamfer', 'Chamfer')])
        mu.row(b, sx, sw, [mu.number(st, 'taper', 'Taper')])
        mu.row(b, sx, sw, [mu._cell('tbtn', 'Summon Polygon', ('op', 'mch.random_shape_add', {'family': 'POLY'}),
                                    active=obj_mode)])
    mu.section(b, 'rs_poly', 'Polygon', x, width, poly)

    def curve(sx, sw):
        kinds(sx, sw, 'CURVE', CURVE_KINDS, st.curve_kind)
        mu.row(b, sx, sw, [mu.number(st, 'curve_slices', 'Slices')])
        mu.row(b, sx, sw, [mu.number(st, 'fillet', 'Fillet')])
        mu.row(b, sx, sw, [mu.number(st, 'segments', 'Smooth')])
        mu.row(b, sx, sw, [mu._cell('tbtn', 'Summon Curved', ('op', 'mch.random_shape_add', {'family': 'CURVE'}),
                                    active=obj_mode)])
    mu.section(b, 'rs_curve', 'Curved', x, width, curve)
    n = sum(1 for o in context.selected_objects if is_shape(o)) if obj_mode else 0
    mu.row(b, x, width, [mu._cell('tbtn', f'Reroll Selected ({n})' if n else 'Reroll Selected',
                                  ('op', 'mch.random_shape_reroll', {}), active=n > 0)])
    b.note(('note', 'Reroll: the selected random shapes, a new form each (own family, same place and size)', False,
            None, None, None, True), x, width)
    return b.out, -b.y


def draw(layout, context):
    """The same in Blender's sidebar (N, Mecha Lab tab)."""
    st = _settings(context)
    col = layout.column(align=True)
    col.prop(st, 'size')
    col.prop(st, 'count')
    box = layout.box()
    box.label(text='Polygon')
    c = box.column(align=True)
    c.prop(st, 'kind', text='')
    c.prop(st, 'slices')
    c.prop(st, 'chamfer')
    c.prop(st, 'taper')
    box.operator('mch.random_shape_add', text='Summon Polygon', icon='MESH_CUBE').family = 'POLY'
    box = layout.box()
    box.label(text='Curved')
    c = box.column(align=True)
    c.prop(st, 'curve_kind', text='')
    c.prop(st, 'curve_slices')
    c.prop(st, 'fillet')
    c.prop(st, 'segments')
    box.operator('mch.random_shape_add', text='Summon Curved', icon='MESH_CYLINDER').family = 'CURVE'
    layout.operator('mch.random_shape_reroll', text='Reroll Selected', icon='FILE_REFRESH')


class MCH_PT_random_shapes(bpy.types.Panel):
    bl_idname = 'MCH_PT_random_shapes'
    bl_label = 'Random Shapes'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Mecha Lab'
    bl_order = 82
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def draw(self, context):
        draw(self.layout, context)


CLASSES = (MCH_PG_RandomShape, MCH_OT_random_shape_add, MCH_OT_random_shape_reroll, MCH_OT_random_shape_kind,
           MCH_PT_random_shapes)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_rshape = bpy.props.PointerProperty(type=MCH_PG_RandomShape)


def unregister():
    if hasattr(bpy.types.Scene, 'mch_rshape'):
        del bpy.types.Scene.mch_rshape
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
