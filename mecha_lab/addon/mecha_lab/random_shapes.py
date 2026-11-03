"""0.24.95 Random Shapes - base meshes to start mecha parts from (user: "박스를 꺼내면 랜덤 모양으로 나오게 하는 메뉴를
만들어 주라 - 메테리얼 있는 그 탭에다가", "다각형 소환 툴이랑 곡률이 들어간 도형 소환 툴", "약간의 랜덤성", "콕핏스러운
곡률 - 헬멧이나 가슴팍 같은 곡률, 헬멧 자체가 필요한 게 아니야", "마음에 들면 그 도형 클릭하고 변주 주면 비슷한데 조금씩
다른 도형들", "꼭 사각형이 아니라 더 다각형이어도 돼").  The side panel's **Shapes** page:

* **Summon Polygon** - flat faces only: **Block** (a box, corners cut), **Prism** (3 - 10 sides), **Wedge** (a slope
  seen from the side), **Step** (L, T, U, stairs, a notch), **Shard** (uneven sides); Slices (flat cuts at an angle),
  Chamfer (edges cut flat), Taper (the top smaller)
* **Summon Curved** - surfaces curved both ways, a section of 4 - 8 sides (rounded, its sides bulging) or round:
  **Pod** (a cockpit / torso: bulging, its face cut flat), **Shell** (a curved armour plate with a thickness - chest,
  shoulder, shin), **Capsule** (a limb segment: an egg, a tapered capsule), **Dome Cut** (a round mass with flat faces
  cut into it and folded lines where two meet); Flat Cuts, Smooth (segments round)
* **Symmetric** (each family): the left half the mirror of the right (a shape built on its centre line)
* **Variations**: the selected shape you like -> several close relatives next to it, a little different each
  (Amount: how much); pick one of those and vary again.  **Reroll**: the selected shapes a new form each

A shape is its parameters (outline, proportions, profile along its length, the cuts ...): kept on the object
(``mch_rshape``, JSON) - Variations move them a little, the same parameters always make the same shape.  Every shape
is checked: one closed piece (each edge between two faces), normals out, its flat faces flat - else the same shape
without its chamfers / cuts.  Polygon shapes are flat shaded; Curved ones smooth with the folded lines (over 30
degrees) sharp - the Edge Memory's marks (Sharp + crease), as every part a tool makes."""
from __future__ import annotations

import json
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
CURVE_KINDS = (('MIX', 'Mix', 'Any of the curved kinds'),
               ('POD', 'Pod', 'A cockpit / a torso: a bulging body of 4 - 8 sides, its face cut flat'),
               ('SHELL', 'Shell', 'A curved armour plate with a thickness: a chest, a shoulder, a shin plate'),
               ('CAPSULE', 'Capsule', 'A limb segment: an egg, a tapered capsule'),
               ('DOMECUT', 'Dome Cut', 'A round mass with flat faces cut into it, folded lines where two meet'))
CURVE_IDS = tuple(k[0] for k in CURVE_KINDS[1:])
CURVE_MIX = {'POD': 3, 'SHELL': 2, 'CAPSULE': 2, 'DOMECUT': 3}
FAMILIES = (('POLY', 'Polygon', 'Flat faces only'), ('CURVE', 'Curved', 'Surfaces curved both ways'))
TAG = 'mch_rshape'                    # on the object: its parameters (JSON) - what Variations / Reroll read
NAME = 'MCH_Shape'
LAST = {'level': 0}                  # (0: the shape as its parameters say; 1 - 3: without chamfers / cuts - tests)
SIDE_M = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))   # outline x -> Y, y -> Z, depth -> X
CUT_ROWS = 12                        # (rows along a curved body, its round ends apart)


# --- 2D outlines (Polygon) -----------------------------------------------------------------------------------------

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




def _simple(pts):
    """No two sides of the outline cross."""
    n = len(pts)

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            c, d = pts[j], pts[(j + 1) % n]
            if (cross(a, b, c) * cross(a, b, d) < 0) and (cross(c, d, a) * cross(c, d, b) < 0):
                return False
    return True


# --- the solid -------------------------------------------------------------------------------------------------------

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
    return (len(bm.faces) > 3 and all(len(e.link_faces) == 2 for e in bm.edges)
            and all(f.calc_area() > 1e-9 for f in bm.faces))


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


def _cut(bm, plane, keep_min=0.5):
    """One flat cut: the plane ``plane`` = (nx, ny, nz, frac) takes ``frac`` of the solid's extent along its normal
    away, the hole closed with one flat face.  Returns the new solid (``bm`` freed), or ``bm`` itself when the cut
    would leave less than ``keep_min`` of it or two pieces."""
    n = Vector(plane[:3])
    if n.length < 1e-6:
        return bm
    n.normalize()
    vol0 = bm.calc_volume()
    work = bm.copy()
    d = [v.co.dot(n) for v in work.verts]
    lo, hi = min(d), max(d)
    off = hi - (hi - lo) * float(plane[3])
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


def _chamfer(bm, seed, amount):
    """Some edges cut flat (one segment) - which ones: ``seed``."""
    if amount <= 0:
        return
    rng = random.Random(seed)
    edges = [e for e in bm.edges if len(e.link_faces) == 2 and e.is_convex
             and e.calc_face_angle(0.0) > math.radians(40)
             and all(o.is_convex for v in e.verts for o in v.link_edges)]   # (outer corners only: a chamfer
    #                                                                          meeting an inner corner bends faces)
    if not edges:
        return
    pick = rng.sample(edges, max(1, int(len(edges) * rng.uniform(0.15, 0.45))))
    shortest = min(e.calc_length() for e in bm.edges)
    w = min(0.06 * amount * rng.uniform(0.6, 1.2), shortest * 0.3)
    if w <= 1e-3:
        return
    bmesh.ops.bevel(bm, geom=pick, offset=w, offset_type='OFFSET', segments=1, profile=0.5, affect='EDGES',
                    clamp_overlap=True)


def symmetrize(bm):
    """The left half (-X) made the mirror of the right one: cut at X = 0, the right half kept, mirrored, welded; a
    face split by the centre line one face again where its two halves are flat together.  (A face across the line is
    cut in triangles first - a concave face with a corner on the line lost itself in the cut - and joined again.)"""
    lay = bm.faces.layers.int.new('_mch_of')
    for i, f in enumerate(bm.faces):
        f[lay] = i + 1
    across = [f for f in bm.faces if len(f.verts) > 3 and min(v.co.x for v in f.verts) < -1e-6
              and max(v.co.x for v in f.verts) > 1e-6]
    if across:
        bmesh.ops.triangulate(bm, faces=across, quad_method='BEAUTY', ngon_method='BEAUTY')
    geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
    bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-6, plane_co=(0, 0, 0), plane_no=(1, 0, 0), clear_inner=True)
    for v in bm.verts:
        if abs(v.co.x) < 1e-6:
            v.co.x = 0.0
    inside = [f for f in bm.faces if all(v.co.x == 0.0 for v in f.verts)]      # (a face on the centre plane)
    if inside:
        bmesh.ops.delete(bm, geom=inside, context='FACES_ONLY')
    loose = [e for e in bm.edges if not e.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context='EDGES')
    if bm.faces:
        ret = bmesh.ops.duplicate(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces))
        nv = [g for g in ret['geom'] if isinstance(g, bmesh.types.BMVert)]
        nf = [g for g in ret['geom'] if isinstance(g, bmesh.types.BMFace)]
        for v in nv:
            v.co.x = -v.co.x
        bmesh.ops.reverse_faces(bm, faces=nf)
        bmesh.ops.remove_doubles(bm, verts=[v for v in bm.verts if v.co.x == 0.0], dist=1e-6)
        flat = math.radians(0.1)
        joins = [e for e in bm.edges if len(e.link_faces) == 2 and e.link_faces[0][lay] == e.link_faces[1][lay]
                 and e.calc_face_angle(1.0) < flat]
        if joins:
            bmesh.ops.dissolve_edges(bm, edges=joins, use_verts=True)
    bm.faces.layers.int.remove(lay)


def _split_bent(bm, tol=1e-4):
    """A face of more than four corners that is not flat (a cut through the bent strips of a round) made triangles."""
    bent = []
    for f in bm.faces:
        if len(f.verts) > 4:
            n, c = f.normal, f.calc_center_median()
            if any(abs((v.co - c).dot(n)) > tol for v in f.verts):
                bent.append(f)
    if bent:
        bmesh.ops.triangulate(bm, faces=bent, quad_method='BEAUTY', ngon_method='BEAUTY')


def _planar_ok(bm, tol=1e-4, quads=True):
    """Every face of more than three corners flat (``quads`` False: the quads of a round are left out)."""
    for f in bm.faces:
        k = len(f.verts)
        if k < 4 or (k == 4 and not quads):
            continue
        n, c = f.normal, f.calc_center_median()
        if any(abs((v.co - c).dot(n)) > tol for v in f.verts):
            return False
    return True


FLAT_TOL = 2e-3                     # (of a shape 1 across: a chamfer's face may lean a hair - 0.2 % - still flat)


def _valid(bm, curved):
    if not bm.verts:
        return False
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return (_closed(bm) and _islands(bm) == 1 and _planar_ok(bm, FLAT_TOL, quads=not curved)
            and bm.calc_volume(signed=True) > 1e-6)


def _fit(bm, size):
    """Centred on the origin (its box), the longest side ``size``."""
    lo = Vector((min(v.co[i] for v in bm.verts) for i in range(3)))
    hi = Vector((max(v.co[i] for v in bm.verts) for i in range(3)))
    span = max(hi - lo) or 1.0
    s = size / span
    c = (lo + hi) / 2
    c.x = 0.0 if abs(c.x) < 1e-6 * span else c.x        # (a symmetric shape stays on its centre line)
    for v in bm.verts:
        v.co = (v.co - c) * s


# --- Polygon parameters ----------------------------------------------------------------------------------------------

def _rand_plane(rng, sym, frac=(0.1, 0.32), zlo=-0.3):
    while True:
        n = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(zlo, 1.0)))
        if n.length > 0.2:
            break
    if sym:
        n.x = abs(n.x)                                   # (the right half is the one kept)
    n.normalize()
    return [round(n.x, 6), round(n.y, 6), round(n.z, 6), round(rng.uniform(*frac), 6)]


def poly_params(rng, kind='MIX', slices=2, chamfer=0.3, taper=0.3, sym=False, max_sides=10):
    if kind not in KIND_IDS:
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
    tp = 1.0
    if taper > 0 and kind in {'BLOCK', 'PRISM', 'SHARD'} and rng.random() < 0.55:
        tp = 1.0 - taper * rng.uniform(0.3, 0.8)
    n_sl = rng.randint(1 if kind == 'SHARD' else 0, slices) if slices > 0 else 0
    return {'family': 'POLY', 'kind': kind, 'sym': bool(sym),
            'outline': [[round(x, 6), round(y, 6)] for x, y in _clean(pts)],
            'depth': round(depth, 6), 'taper': round(tp, 6), 'side': side,
            'slices': [_rand_plane(rng, sym) for _ in range(n_sl)],
            'chamfer': [rng.randrange(1, 2 ** 31 - 1), round(chamfer if rng.random() < 0.8 else 0.0, 6)]}


def build_poly(p, level=0):
    """The solid of Polygon parameters ``p``; ``level`` 1: without its chamfers, 2: without its slices too."""
    bm = bmesh.new()
    _prism(bm, [tuple(q) for q in p['outline']], p['depth'], p['taper'])
    if p.get('side'):                                    # the outline seen from the side: X across it
        bmesh.ops.transform(bm, matrix=SIDE_M, verts=list(bm.verts))
    if level < 2:
        for pl in p.get('slices', ()):
            bm = _cut(bm, pl, 0.5)
    ch = p.get('chamfer') or (0, 0.0)
    if level < 1 and ch[1] > 0:
        _chamfer(bm, int(ch[0]), float(ch[1]))
    if p.get('sym'):
        symmetrize(bm)
    return bm


# --- Curved: a section of 4 - 8 sides, rounded, its sides bulging ---------------------------------------------------

def section(n, rnd, bulge, front, segs):
    """The cross-section: a polygon of ``n`` sides (a corner or a side to the front, +Y), its corners rounded
    (``rnd`` 0 - 1: 1 round all along), its sides bulging out (``bulge``); symmetric about X = 0 with a point on it at
    the front and at the back (the first point: the front); in a box of -1 .. 1.  ``n`` of 16 and more: round."""
    n = max(3, int(n))
    step = 2 * math.pi / n
    a0 = math.pi / 2 if front == 'VERTEX' else math.pi / 2 - step / 2
    V = [Vector((math.cos(a0 - j * step), math.sin(a0 - j * step))) for j in range(n)]       # (clockwise)
    d = max(0.0, min(0.45, rnd * 0.5))
    per = max(4, int(round(segs / n)))
    nc = max(2, 2 * int(round(per * d))) if d > 1e-6 else 0   # (even counts: a corner's / a side's middle is a point)
    ns = max(2, per - nc)
    ns += ns % 2

    def side(j, s):
        A, B = V[j], V[(j + 1) % n]
        out = ((A + B) / 2).normalized()
        return A.lerp(B, s) + out * ((A - B).length * bulge * 0.5 * 4 * s * (1 - s))
    pts = []
    for j in range(n):
        if nc:                                           # (the corner: from the side before to this one)
            P0, P2, C = side(j - 1, 1 - d), side(j, d), V[j]
            for i in range(nc):
                u = i / nc
                pts.append((1 - u) ** 2 * P0 + 2 * u * (1 - u) * C + u * u * P2)
        for i in range(ns):
            pts.append(side(j, d + (1 - 2 * d) * i / ns))
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    xm = max(abs(x) for x in xs) or 1.0
    yc, yh = (max(ys) + min(ys)) / 2, ((max(ys) - min(ys)) / 2) or 1.0
    out = [(0.0 if abs(p.x) < 1e-9 else p.x / xm, (p.y - yc) / yh) for p in pts]
    first = max(range(len(out)), key=lambda i: (out[i][0] == 0.0, out[i][1]))
    return out[first:] + out[:first]


def _spline(vals, t):
    """A smooth curve through ``vals`` spread evenly over t = 0 .. 1 (Catmull-Rom, the ends held)."""
    n = len(vals) - 1
    x = max(0.0, min(1.0, t)) * n
    i = min(int(x), n - 1)
    u = x - i
    p0, p1, p2, p3 = vals[max(i - 1, 0)], vals[i], vals[i + 1], vals[min(i + 2, n)]
    return 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u
                  + (-p0 + 3 * p1 - 3 * p2 + p3) * u * u * u)


def _rows(c0, c1):
    """(t, scale) along a body of round ends ``c0`` (bottom) / ``c1`` (top) - a quarter of an oval each, a step of
    15 degrees at most (the round stays smooth: under the Edge Memory's 30 degrees)."""
    c0, c1 = max(0.0, c0), max(0.0, c1)
    if c0 + c1 > 0.9:
        k = 0.9 / (c0 + c1)
        c0, c1 = c0 * k, c1 * k
    rows = []
    k = 6
    if c0 > 0.01:
        rows += [(c0 * (1 - math.cos(math.pi / 2 * i / k)), math.sin(math.pi / 2 * i / k)) for i in range(k)]
    nb = max(2, int(round((1 - c0 - c1) * CUT_ROWS)))
    rows += [(c0 + (1 - c0 - c1) * i / nb, 1.0) for i in range(nb + 1)]
    if c1 > 0.01:
        rows += [(1 - c1 + c1 * math.sin(math.pi / 2 * i / k), math.cos(math.pi / 2 * i / k)) for i in range(1, k + 1)]
    return rows


def _loft(bm, rings):
    """Quads between rings of the same count (a ring of one point: a round end closing there); a flat face at an
    open end."""
    m = max(len(r) for r in rings)
    for a, b in zip(rings, rings[1:]):
        if len(a) == 1 and len(b) == 1:
            continue
        for i in range(m):
            j = (i + 1) % m
            if len(a) == 1:
                bm.faces.new((a[0], b[j], b[i]))
            elif len(b) == 1:
                bm.faces.new((a[i], a[j], b[0]))
            else:
                bm.faces.new((a[i], a[j], b[j], b[i]))
    if len(rings[0]) > 1:
        bm.faces.new(rings[0])
    if len(rings[-1]) > 1:
        bm.faces.new(list(reversed(rings[-1])))


def body(bm, p, segs):
    """A body along Z: the section scaled by the width / depth profiles, moved forward by the ``y`` profile, its ends
    round (``c0`` / ``c1``) or flat."""
    sec = section(p['n'], p['round'], p['bulge'], p['front'], segs)
    W, D, L = p['W'], p['D'], p['L']
    rings = []
    for t, sc in _rows(p['c0'], p['c1']):
        w = max(0.05, _spline(p['w'], t)) * sc * W / 2
        dd = max(0.05, _spline(p['d'], t)) * sc * D / 2
        yo = _spline(p['y'], t) * D / 2
        z = t * L
        if sc < 1e-6:
            rings.append([bm.verts.new((0.0, yo, z))])
        else:
            rings.append([bm.verts.new((x * w, y * dd + yo, z)) for x, y in sec])
    _loft(bm, rings)


def shell(bm, p, segs):
    """A curved plate along Z: a band of an arc (radius ``R``, ``thk`` thick, ``A`` degrees across - at the bottom,
    the middle, the top), facing +Y, its ends bending back (``bend``)."""
    m = max(4, 2 * int(round(segs / 4)))
    R, thk, L = p['R'], p['thk'], p['L']
    a0, a1, a2 = p['A']
    rings = []
    for i in range(CUT_ROWS + 5):
        t = i / (CUT_ROWS + 4)
        A = math.radians(max(20.0, a0 * (1 - t) * (1 - 2 * t) + 4 * a1 * t * (1 - t) + a2 * t * (2 * t - 1)))
        yb = -p['bend'] * ((2 * t - 1) ** 2) * L * 0.5
        z = t * L
        ring = []
        for rr, rev in ((R + thk, False), (R, True)):
            for k in range(m + 1):
                kk = m - k if rev else k
                a = math.pi / 2 - A / 2 + A * kk / m
                ring.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a) - R + yb, z)))
        rings.append(ring)
    _loft(bm, rings)


def _curve_cut(rng, kind, sym):
    """A flat cut for a curved body of ``kind``: the face (visor), a cheek, the chin, the top, the back; a Shell's
    corners."""
    U = rng.uniform
    deep = 1.6 if kind == 'DOMECUT' else 1.0
    if kind == 'SHELL':
        n = (U(0.3, 1.0), U(-0.25, 0.25), U(0.3, 1.0) * rng.choice((-1, 1)))
        fr = U(0.05, 0.2)
    else:
        c = rng.choices(('visor', 'cheek', 'chin', 'top', 'back'),
                        weights=(4, 3, 2, 1, 1) if kind != 'CAPSULE' else (1, 3, 1, 1, 2))[0]
        if c == 'visor':
            n, fr = (0.0, 1.0, U(-0.3, 0.9)), U(0.07, 0.18) * deep
        elif c == 'cheek':
            n, fr = (U(0.6, 1.0), U(0.2, 0.8), U(-0.4, 0.4)), U(0.05, 0.13) * deep
        elif c == 'chin':
            n, fr = (0.0, U(0.3, 0.8), -1.0), U(0.08, 0.18) * deep
        elif c == 'top':
            n, fr = (0.0, U(-0.3, 0.3), 1.0), U(0.05, 0.14)
        else:
            n, fr = (0.0, -1.0, U(-0.3, 0.5)), U(0.05, 0.14)
    nx = n[0] if sym else n[0] * rng.choice((-1, 1))
    v = Vector((nx, n[1], n[2])).normalized()
    return [round(v.x, 6), round(v.y, 6), round(v.z, 6), round(fr, 6)]


def curve_params(rng, kind='MIX', cuts=2, sym=True):
    if kind not in CURVE_IDS:
        ks = list(CURVE_MIX)
        kind = rng.choices(ks, weights=[CURVE_MIX[k] for k in ks])[0]
    U = rng.uniform
    p = {'family': 'CURVE', 'kind': kind, 'sym': bool(sym)}
    if kind == 'SHELL':
        p.update(R=U(0.35, 0.9), thk=U(0.05, 0.12), A=[U(60, 120), U(90, 150), U(60, 120)], L=U(0.6, 1.2),
                 bend=U(0.0, 0.35))
        n_c = rng.randint(0, cuts) if cuts else 0
    else:
        if kind == 'POD':
            p.update(n=rng.choice((4, 5, 6, 6, 7, 8)), round=U(0.0, 0.4), bulge=U(0.08, 0.3),
                     front=rng.choice(('VERTEX', 'SIDE')), W=1.0, D=U(0.6, 1.0), L=U(0.6, 1.1),
                     w=[U(0.6, 0.95), U(0.9, 1.05), U(0.85, 1.0), U(0.55, 0.9)],
                     d=[U(0.6, 0.9), U(0.9, 1.05), U(0.85, 1.0), U(0.5, 0.85)],
                     y=[0.0, U(0.0, 0.15), U(0.0, 0.12), U(-0.1, 0.05)],
                     c0=rng.choice((0.0, U(0.05, 0.2))), c1=U(0.15, 0.45))
            n_c = rng.randint(1, cuts) if cuts else 0
        elif kind == 'CAPSULE':
            n = rng.choice((5, 6, 8, 24))
            p.update(n=n, round=U(0.2, 0.8) if n < 16 else 0.0, bulge=U(0.0, 0.2), front=rng.choice(('VERTEX', 'SIDE')),
                     W=U(0.4, 0.7), D=U(0.4, 0.7), L=1.0,
                     w=[U(0.5, 0.8), U(0.85, 1.0), U(0.75, 0.95), U(0.45, 0.7)],
                     d=[U(0.5, 0.8), U(0.85, 1.0), U(0.75, 0.95), U(0.45, 0.7)],
                     y=[0.0, U(-0.1, 0.1), U(-0.05, 0.1), 0.0],
                     c0=rng.choice((0.0, U(0.08, 0.3))), c1=U(0.1, 0.3))
            n_c = rng.randint(0, min(1, cuts)) if cuts else 0
        else:                                            # DOMECUT
            p.update(n=rng.choice((5, 6, 7, 8, 10)), round=U(0.15, 0.7), bulge=U(0.1, 0.35),
                     front='VERTEX' if rng.random() < 0.7 else 'SIDE', W=1.0, D=U(0.9, 1.2), L=U(0.75, 1.0),
                     w=[U(0.8, 0.95), U(0.95, 1.05), U(0.9, 1.0), U(0.6, 0.85)],
                     d=[U(0.8, 0.95), U(0.95, 1.05), U(0.9, 1.0), U(0.6, 0.85)],
                     y=[U(0.0, 0.1), U(0.0, 0.1), 0.0, U(-0.1, 0.0)],
                     c0=rng.choice((0.0, U(0.03, 0.1))), c1=U(0.4, 0.7))
            n_c = rng.randint(2, max(2, cuts + 1)) if cuts else 0
    p['cuts'] = [_curve_cut(rng, kind, sym) for _ in range(n_c)]
    return _rounded(p)


def _rounded(p):
    """(the numbers kept short in the JSON)"""
    def r(v):
        if isinstance(v, float):
            return round(v, 6)
        if isinstance(v, list):
            return [r(x) for x in v]
        return v
    return {k: r(v) for k, v in p.items()}


def build_curve(p, segs=32, level=0):
    """The solid of Curved parameters ``p``; ``level`` 2 and up: without its cuts."""
    bm = bmesh.new()
    if p['kind'] == 'SHELL':
        shell(bm, p, segs)
    else:
        body(bm, p, segs)
    if level < 2:
        for pl in p.get('cuts', ()):
            bm = _cut(bm, pl, 0.6 if p['kind'] == 'SHELL' else 0.55)
    if p.get('sym'):
        symmetrize(bm)
    _split_bent(bm)
    return bm


def build(p, segs=32, size=1.0):
    """(bm, kind) of the shape of parameters ``p``, its longest side ``size``: as they say, else without chamfers,
    else without cuts, else the plain body - the first one that is a clean solid (``LAST['level']``)."""
    curved = p.get('family') == 'CURVE'
    for level in range(4):
        if curved and level == 1:                        # (no chamfers on a curved shape)
            continue
        bm = build_curve(p, segs, level) if curved else build_poly(p, level)
        if level == 3 and p.get('sym'):                  # (the plain body, not mirrored: always clean)
            bm.free()
            q = dict(p, sym=False)
            bm = build_curve(q, segs, 2) if curved else build_poly(q, 2)
        if _valid(bm, curved):
            break
        if level < 3:
            bm.free()
    LAST['level'] = level
    _fit(bm, size)
    return bm, p['kind']


# --- Variations ------------------------------------------------------------------------------------------------------

def _jit(rng, v, rel, a, lo=None, hi=None):
    v = v * (1.0 + rng.uniform(-rel, rel) * a)
    if lo is not None:
        v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return v


def _vary_plane(rng, pl, a, sym, spin=0.35):
    n = Vector(pl[:3]) + Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * spin * a
    if n.length < 1e-3:
        n = Vector(pl[:3])
    if sym and pl[0] >= 0:
        n.x = abs(n.x) if pl[0] > 1e-6 else 0.0          # (a cut on the centre line stays on it)
    n.normalize()
    return [round(n.x, 6), round(n.y, 6), round(n.z, 6),
            round(max(0.03, min(0.4, pl[3] + rng.uniform(-0.06, 0.06) * a)), 6)]


def _vary_outline(rng, pts, kind, a):
    if kind == 'STEP':                                   # (right angles kept: each column / row moves as one)
        def remap(vals):
            u = sorted(set(vals))
            out, last = {}, None
            for x in u:
                nx = x + rng.uniform(-0.07, 0.07) * a
                if last is not None:
                    nx = max(nx, last + 0.05)
                out[x], last = nx, nx
            return out
        mx, my = remap([p[0] for p in pts]), remap([p[1] for p in pts])
        return [[mx[p[0]], my[p[1]]] for p in pts]
    for _t in range(8):
        q = [(p[0] + rng.uniform(-0.06, 0.06) * a, p[1] + rng.uniform(-0.06, 0.06) * a) for p in pts]
        if kind in {'BLOCK', 'PRISM', 'SHARD'}:
            q = _hull(q)
        q = _clean(q)
        if len(q) >= 3 and _simple(q):
            return [[x, y] for x, y in q]
    return [list(p) for p in pts]


def vary(p, amount, rng):
    """Parameters close to ``p``: each number moved a little (``amount`` 0 - 1: how much), the kind, the number of
    sides and of cuts kept."""
    a = max(0.0, min(1.0, amount))
    q = json.loads(json.dumps(p))
    sym = bool(q.get('sym'))
    if q.get('family') == 'CURVE':
        if q['kind'] == 'SHELL':
            q['R'] = _jit(rng, q['R'], 0.3, a, 0.2, 1.5)
            q['thk'] = _jit(rng, q['thk'], 0.3, a, 0.02, 0.2)
            q['A'] = [_jit(rng, v, 0.25, a, 25.0, 175.0) for v in q['A']]
            q['L'] = _jit(rng, q['L'], 0.25, a, 0.3, 2.0)
            q['bend'] = max(0.0, min(0.6, q['bend'] + rng.uniform(-0.12, 0.12) * a))
        else:
            q['round'] = max(0.0, min(1.0, q['round'] + rng.uniform(-0.2, 0.2) * a)) if q['n'] < 16 else 0.0
            q['bulge'] = max(0.0, min(0.45, q['bulge'] + rng.uniform(-0.1, 0.1) * a))
            for k in ('W', 'D', 'L'):
                q[k] = _jit(rng, q[k], 0.2, a, 0.2, 3.0)
            for k in ('w', 'd'):
                q[k] = [max(0.2, v + rng.uniform(-0.12, 0.12) * a) for v in q[k]]
            q['y'] = [v + rng.uniform(-0.05, 0.05) * a for v in q['y']]
            for k in ('c0', 'c1'):
                if q[k] > 0:
                    q[k] = max(0.02, min(0.7, q[k] + rng.uniform(-0.08, 0.08) * a))
        q['cuts'] = [_vary_plane(rng, pl, a, sym) for pl in q.get('cuts', ())]
        return _rounded(q)
    q['outline'] = _vary_outline(rng, q['outline'], q['kind'], a)
    q['depth'] = _jit(rng, q['depth'], 0.2, a, 0.1, 2.0)
    if q['taper'] < 1.0:
        q['taper'] = max(0.3, min(1.0, q['taper'] + rng.uniform(-0.15, 0.15) * a))
    q['slices'] = [_vary_plane(rng, pl, a, sym) for pl in q.get('slices', ())]
    ch = q.get('chamfer') or [1, 0.0]
    q['chamfer'] = [ch[0], max(0.0, min(1.0, ch[1] * (1 + rng.uniform(-0.3, 0.3) * a)))]
    return _rounded(q)


# --- objects ---------------------------------------------------------------------------------------------------------

def new_params(rng, family, st):
    """Random parameters of ``family`` with the Shapes page's settings ``st`` (None: the defaults)."""
    g = (lambda n, d: getattr(st, n, d)) if st is not None else (lambda n, d: d)
    if family == 'CURVE':
        return curve_params(rng, g('curve_kind', 'MIX'), g('curve_cuts', 2), g('curve_sym', True))
    return poly_params(rng, g('kind', 'MIX'), g('slices', 2), g('chamfer', 0.3), g('taper', 0.3), g('poly_sym', False))


def new_mesh(p, segs=32, size=1.0, name=NAME):
    """A mesh of the shape of parameters ``p``: (mesh, kind)."""
    bm, kind = build(p, segs, size)
    me = bpy.data.meshes.new(name)
    try:
        bm.to_mesh(me)
    finally:
        bm.free()
    me.polygons.foreach_set('use_smooth', [p.get('family') == 'CURVE'] * len(me.polygons))
    try:
        from . import edge_memory
        edge_memory.mark_generated(me)               # (its own lines, like every part a tool makes: Sharp + crease)
    except Exception as ex:                          # (never in the way of the shape)
        print('Mecha: random shape edge memory:', ex)
    return me, kind


def is_shape(ob):
    return ob is not None and getattr(ob, 'type', '') == 'MESH' and TAG in ob.keys()


def params_of(ob):
    try:
        p = json.loads(ob[TAG])
    except (KeyError, TypeError, ValueError):
        return None
    return p if isinstance(p, dict) and p.get('family') in {'POLY', 'CURVE'} else None


def _store(ob, p):
    ob[TAG] = json.dumps(p, separators=(',', ':'))


def _new_seed():
    return random.SystemRandom().randrange(1, 2 ** 31 - 1)


def _seed(base, i):
    return (base + i * 7919) % (2 ** 31 - 1) or 1


def _local_size(me):
    if not len(me.vertices):
        return 0.0
    return max(max(v.co[a] for v in me.vertices) - min(v.co[a] for v in me.vertices) for a in range(3))


def layout_spots(count, gap):
    """Where ``count`` shapes go round the cursor: rows of 5 along X, the rows going back (-Y)."""
    cols = min(count, 5)
    rows = -(-count // cols)
    out = []
    for i in range(count):
        r, c = divmod(i, cols)
        out.append(Vector(((c - (cols - 1) / 2) * gap, -(r - (rows - 1) / 2) * gap, 0.0)))
    return out


def _free_row(context, start, gap, count):
    """Spots for ``count`` shapes in a row along +X from ``start`` - a row further back (-Y) while one of them would
    land on another random shape."""
    others = [o.matrix_world.translation for o in context.scene.objects if is_shape(o)]
    for r in range(12):
        spots = [start + Vector(((i + 1) * gap, -r * gap, 0.0)) for i in range(count)]
        if not any((s - o).length < gap * 0.5 for s in spots for o in others):
            return spots
    return spots


def _link_like(context, ob, src=None):
    colls = list(src.users_collection) if src is not None else []
    if not colls:
        colls = [context.collection if context.collection is not None else context.scene.collection]
    for c in colls:
        try:
            c.objects.link(ob)
        except RuntimeError:
            pass
    if not ob.users_collection:
        context.scene.collection.objects.link(ob)


def _select_only(context, obs):
    for o in context.selected_objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    if obs:
        context.view_layer.objects.active = obs[0]


# --- settings + operators --------------------------------------------------------------------------------------------

class MCH_PG_RandomShape(bpy.types.PropertyGroup):
    size: bpy.props.FloatProperty(name='Size', description='The longest side of a new shape', default=1.0, min=0.01,
                                  soft_max=10.0, subtype='DISTANCE', unit='LENGTH')
    count: bpy.props.IntProperty(name='Count', description='How many shapes a Summon makes (in rows, to pick from)',
                                 default=1, min=1, max=25)
    # Polygon
    kind: bpy.props.EnumProperty(name='Polygon Kind', items=KINDS, default='MIX')
    poly_sym: bpy.props.BoolProperty(name='Symmetric', description='The left half the mirror of the right',
                                     default=False)
    slices: bpy.props.IntProperty(name='Slices', description='Up to this many flat cuts at an angle', default=2,
                                  min=0, max=4)
    chamfer: bpy.props.FloatProperty(name='Chamfer', description='Some edges cut flat: how wide', default=0.3,
                                     min=0.0, max=1.0, subtype='FACTOR')
    taper: bpy.props.FloatProperty(name='Taper', description='The top smaller than the bottom (now and then)',
                                   default=0.3, min=0.0, max=1.0, subtype='FACTOR')
    # Curved
    curve_kind: bpy.props.EnumProperty(name='Curved Kind', items=CURVE_KINDS, default='MIX')
    curve_sym: bpy.props.BoolProperty(name='Symmetric', description='The left half the mirror of the right',
                                      default=True)
    curve_cuts: bpy.props.IntProperty(name='Flat Cuts', description='Up to this many flat faces cut into it',
                                      default=2, min=0, max=4)
    segments: bpy.props.IntProperty(name='Smooth', description='Points round a section (more = rounder, heavier)',
                                    default=32, min=12, max=96)
    # Variations
    var_amount: bpy.props.FloatProperty(name='Amount', description='How different the variations are', default=0.3,
                                        min=0.02, max=1.0, subtype='FACTOR')
    var_count: bpy.props.IntProperty(name='How Many', description='How many variations at a time', default=4, min=1,
                                     max=12)


def _settings(context):
    return context.scene.mch_rshape


class MCH_OT_random_shape_add(bpy.types.Operator):
    """Summon a shape of a random form at the 3D cursor - Polygon (flat faces) or Curved (curved both ways); the
    Shapes page's kind, Size, Count ..."""
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
        base = context.scene.cursor.location.copy()
        made = []
        for i, off in enumerate(layout_spots(st.count, st.size * 1.6)):
            p = new_params(random.Random(_seed(self.seed, i)), self.family, st)
            me, _kind = new_mesh(p, st.segments, st.size)
            ob = bpy.data.objects.new(NAME, me)
            _link_like(context, ob)
            ob.location = base + off
            _store(ob, p)
            made.append(ob)
        _select_only(context, made)
        names = dict((k[0], k[1]) for k in KINDS + CURVE_KINDS)
        kinds = sorted({names.get(params_of(o)['kind'], '?') for o in made})
        fam = 'curved' if self.family == 'CURVE' else 'polygon'
        self.report({'INFO'}, f'{len(made)} random {fam} shape{"s" if len(made) > 1 else ""}: {", ".join(kinds)}'
                              f' (seed {self.seed})')
        return {'FINISHED'}


class MCH_OT_random_shape_vary(bpy.types.Operator):
    """Variations of the selected random shape you like: close relatives next to it, a little different each (the
    Shapes page's Amount and How Many) - pick one of them and vary again"""
    bl_idname = 'mch.random_shape_vary'
    bl_label = 'Random Shape Variations'
    bl_options = {'REGISTER', 'UNDO'}
    seed: bpy.props.IntProperty(name='Seed', description='The same seed makes the same variations (0: new ones)',
                                default=0, min=0, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and is_shape(getattr(context, 'active_object', None))

    def execute(self, context):
        st = _settings(context)
        src = context.active_object
        p = params_of(src) if is_shape(src) else None
        if p is None:
            self.report({'WARNING'}, 'Select a random shape (made with Summon) first')
            return {'CANCELLED'}
        if self.seed == 0:
            self.seed = _new_seed()
        rng = random.Random(self.seed)
        size = _local_size(src.data) or st.size
        gap = max(max(src.dimensions), 1e-3) * 1.4
        spots = _free_row(context, src.matrix_world.translation.copy(), gap, st.var_count)
        made = []
        for spot in spots:
            for _t in range(6):                          # (a variation that builds clean as it is)
                q = vary(p, st.var_amount, rng)
                bm, _k = build(q, st.segments, size)
                bm.free()
                if LAST['level'] == 0:
                    break
            me, _kind = new_mesh(q, st.segments, size)
            for m in src.data.materials:
                me.materials.append(m)
            ob = bpy.data.objects.new(NAME, me)
            _link_like(context, ob, src)
            ob.matrix_world = src.matrix_world.copy()
            ob.location = spot
            _store(ob, q)
            made.append(ob)
        _select_only(context, made)
        self.report({'INFO'}, f'{len(made)} variation{"s" if len(made) > 1 else ""} of {src.name} '
                              f'(Amount {round(st.var_amount * 100)} %, seed {self.seed})')
        return {'FINISHED'}


class MCH_OT_random_shape_reroll(bpy.types.Operator):
    """The selected random shapes get a new random form each, of their own family (Polygon / Curved) and as big as
    they were, where they are (place, turn, scale, materials kept); the kind on the Shapes page decides what they
    become"""
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
        n = 0
        for i, ob in enumerate(obs):
            old = ob.data
            if old.users > 1:
                continue                                 # (a linked copy: its twin would change too)
            fam = (params_of(ob) or {}).get('family', 'POLY')
            p = new_params(random.Random(_seed(self.seed, i)), fam, st)
            me, _kind = new_mesh(p, st.segments, _local_size(old) or st.size, old.name)
            for m in old.materials:
                me.materials.append(m)
            ob.data = me
            if old.users == 0:
                bpy.data.meshes.remove(old)
            _store(ob, p)
            n += 1
        if not n:
            self.report({'WARNING'}, 'Nothing rerolled (select a random shape; one shared by linked copies is left)')
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


# --- the Shapes page (drawn side panel) and the sidebar panel --------------------------------------------------------

def page(context, x, width, k):
    """(items, content height) - the side panel's Shapes page, y measured down from 0 (as ``side_panel.content``)."""
    from . import side_panel as sp
    from . import mech_shader_ui as mu
    b = sp.Builder('SHAPES', x, width, k)
    st = _settings(context)
    obj_mode = context.mode == 'OBJECT'
    b.note(('note', 'A click: a new base shape of a random form at the 3D cursor' if obj_mode else
            'Object Mode only (leave Edit / Sculpt first)', False, None, None, None, True), x, width)
    mu.row(b, x, width, [mu.number(st, 'size', 'Size'), mu.number(st, 'count', 'Count')])

    def kinds(sx, sw, family, items, cur):
        cells = [mu._cell('tbtn', label, ('op', 'mch.random_shape_kind', {'family': family, 'kind': ident}),
                          on=cur == ident) for ident, label, _d in items]
        for i in range(0, len(cells), 3):
            mu.row(b, sx, sw, cells[i:i + 3])

    def poly(sx, sw):
        kinds(sx, sw, 'POLY', KINDS, st.kind)
        mu.row(b, sx, sw, [mu.prop_cell(st, 'poly_sym', 'Symmetric')])
        mu.row(b, sx, sw, [mu.number(st, 'slices', 'Slices')])
        mu.row(b, sx, sw, [mu.number(st, 'chamfer', 'Chamfer')])
        mu.row(b, sx, sw, [mu.number(st, 'taper', 'Taper')])
        mu.row(b, sx, sw, [mu._cell('tbtn', 'Summon Polygon', ('op', 'mch.random_shape_add', {'family': 'POLY'}),
                                    active=obj_mode)])
    mu.section(b, 'rs_poly', 'Polygon', x, width, poly)

    def curve(sx, sw):
        kinds(sx, sw, 'CURVE', CURVE_KINDS, st.curve_kind)
        mu.row(b, sx, sw, [mu.prop_cell(st, 'curve_sym', 'Symmetric')])
        mu.row(b, sx, sw, [mu.number(st, 'curve_cuts', 'Flat Cuts')])
        mu.row(b, sx, sw, [mu.number(st, 'segments', 'Smooth')])
        mu.row(b, sx, sw, [mu._cell('tbtn', 'Summon Curved', ('op', 'mch.random_shape_add', {'family': 'CURVE'}),
                                    active=obj_mode)])
    mu.section(b, 'rs_curve', 'Curved', x, width, curve)

    def variations(sx, sw):
        act = getattr(context, 'active_object', None)
        ok = obj_mode and is_shape(act)
        b.note(('note', f'Of "{act.name}": close relatives next to it' if ok else
                'Select a shape you like (made here), then Variations', False, None, None, None, True), sx, sw)
        mu.row(b, sx, sw, [mu.number(st, 'var_amount', 'Amount'), mu.number(st, 'var_count', 'How Many')])
        mu.row(b, sx, sw, [mu._cell('tbtn', 'Variations', ('op', 'mch.random_shape_vary', {}), active=ok)])
        n = sum(1 for o in context.selected_objects if is_shape(o)) if obj_mode else 0
        mu.row(b, sx, sw, [mu._cell('tbtn', f'Reroll Selected ({n})' if n else 'Reroll Selected',
                                    ('op', 'mch.random_shape_reroll', {}), active=n > 0)])
    mu.section(b, 'rs_vary', 'Variations', x, width, variations)
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
    c.prop(st, 'poly_sym')
    c.prop(st, 'slices')
    c.prop(st, 'chamfer')
    c.prop(st, 'taper')
    box.operator('mch.random_shape_add', text='Summon Polygon', icon='MESH_CUBE').family = 'POLY'
    box = layout.box()
    box.label(text='Curved')
    c = box.column(align=True)
    c.prop(st, 'curve_kind', text='')
    c.prop(st, 'curve_sym')
    c.prop(st, 'curve_cuts')
    c.prop(st, 'segments')
    box.operator('mch.random_shape_add', text='Summon Curved', icon='MESH_UVSPHERE').family = 'CURVE'
    box = layout.box()
    box.label(text='Variations')
    c = box.column(align=True)
    c.prop(st, 'var_amount')
    c.prop(st, 'var_count')
    box.operator('mch.random_shape_vary', text='Variations', icon='MOD_ARRAY')
    box.operator('mch.random_shape_reroll', text='Reroll Selected', icon='FILE_REFRESH')


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


CLASSES = (MCH_PG_RandomShape, MCH_OT_random_shape_add, MCH_OT_random_shape_vary, MCH_OT_random_shape_reroll,
           MCH_OT_random_shape_kind, MCH_PT_random_shapes)


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
