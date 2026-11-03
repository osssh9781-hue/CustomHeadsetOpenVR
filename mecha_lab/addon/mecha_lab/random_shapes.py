"""0.24.95 Random Shapes - base meshes to start mecha parts from (user: "박스를 꺼내면 랜덤 모양으로 나오게 하는 메뉴를
만들어 주라 - 메테리얼 있는 그 탭에다가", "다각형 소환 툴이랑 곡률이 들어간 도형 소환 툴", "약간의 랜덤성", "콕핏스러운
곡률 - 헬멧이나 가슴팍 같은 곡률, 헬멧 자체가 필요한 게 아니야", "마음에 들면 그 도형 클릭하고 변주 주면 비슷한데 조금씩
다른 도형들", "꼭 사각형이 아니라 더 다각형이어도 돼").  The side panel's **Shapes** page:

* **Summon Polygon** - flat faces only: **Block** (a box, corners cut), **Prism** (3 - 10 sides), **Wedge** (a slope
  seen from the side), **Step** (L, T, U, stairs, a notch), **Shard** (uneven sides); Slices (flat cuts at an angle),
  Chamfer (edges cut flat), Taper (the top smaller)
* **Summon Curved** - surfaces curved both ways, a section of 4 - 8 sides (rounded, its sides bulging, the back
  flatter) or round: **Pod** (a cockpit: a rounded box - a rounded rim round a flat top - its face cut flat),
  **Torso** (a chest: wide at the top, the chest bulging forward), **Shell** (a curved armour plate with a thickness -
  chest, shoulder, shin), **Capsule** (a limb segment), **Dome Cut** (a round mass with flat faces cut into it); the
  cuts often a chisel to one side of the front - mirrored: a ridge down the middle; Flat Cuts, Smooth
* **Solid / Plate** (user: "덩어리지만 약간 판떼기 버전도 - 두께가 얇은 판떼기"): Plate makes thin plates of both
  families (Thickness, of the plate's size): a Polygon plate is the outline as a panel facing the front, its rim
  slanted now and then, its edges trimmed at angles, bent (user: "판도 꺾여 있어야지": its sides wrapped back, a V down
  the middle or its top / bottom edge bent; each part flat, the fold lines mitred); a Curved plate is the front of the body - curved both ways as
  the body is - made thick inward, its outline trimmed
* **Symmetric** (each family): the left half the mirror of the right (a shape built on its centre line)
* **Real Parts** (user: "실제로 내가 말한 차랑 비행기 탱크를 자료 서치해서 부품을 그대로"): exterior parts after real
  vehicles - Lambo, 911, F-22, Tank (``ref_parts``) - a vehicle, a part, Summon Part
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
import os
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

KINDS = (('MIX', 'Mix', 'Any of the kinds'),
         ('BLOCK', 'Block', 'A box, some of its corners cut off'),
         ('PRISM', 'Prism', 'A prism of 3 to 10 sides'),
         ('WEDGE', 'Wedge', 'A ramp / a slope seen from the side'),
         ('STEP', 'Step', 'L, T, U, stairs or a notch'),
         ('SHARD', 'Shard', 'Uneven sides, cut at angles'),
         ('JET', 'Jet', 'Aircraft-like, one angle repeated: a chined fuselage / nose (solid), a swept wing or fin with '
                        'knife edges (plate)'),
         ('TANK', 'Tank', 'Tank parts, one slope repeated: a reactive-armour block, a turret cheek wedge, a gun '
                          'mantlet, a stowage box (solid); a side skirt, a track guard (plate)'),
         ('CAR', 'Car', 'Sports-car parts (Lamborghini-like, one angle repeated): a side air scoop, a rear wing, a '
                        'headlight housing (solid); a creased door panel, a fender with a hexagonal wheel arch, a '
                        'splitter fin (plate)'))
KIND_IDS = tuple(k[0] for k in KINDS[1:])
MIX_WEIGHTS = {'BLOCK': 3, 'PRISM': 2, 'WEDGE': 2, 'STEP': 2, 'SHARD': 2, 'JET': 2, 'TANK': 2, 'CAR': 2}
CURVE_KINDS = (('MIX', 'Mix', 'Any of the curved kinds'),
               ('POD', 'Pod', 'A cockpit / a torso: a bulging body of 4 - 8 sides, its face cut flat'),
               ('SHELL', 'Shell', 'A curved armour plate with a thickness: a chest, a shoulder, a shin plate'),
               ('CAPSULE', 'Capsule', 'A limb segment: an egg, a tapered capsule'),
               ('DOMECUT', 'Dome Cut', 'A round mass with flat faces cut into it, folded lines where two meet'),
               ('TORSO', 'Torso', 'A chest / a body: wide at the top, the chest bulging forward, a flat back'),
               ('JET', 'Jet', 'A blended fuselage: soft chines, a canopy rise, a pointed nose (a plate: its skin)'),
               ('TANK', 'Tank', 'Cast tank parts: a rounded mantlet, a cupola (solid); a cast armour skin, a curved '
                                'track guard (plate)'),
               ('CAR', 'Car', 'Sports-car parts (Porsche-like): a round headlight pod, a wing mirror, a front bumper '
                              '(solid); a fender with a round wheel arch, a hood (plate)'))
CURVE_IDS = tuple(k[0] for k in CURVE_KINDS[1:])
CURVE_MIX = {'POD': 3, 'SHELL': 2, 'CAPSULE': 2, 'DOMECUT': 3, 'TORSO': 3, 'JET': 2, 'TANK': 2, 'CAR': 2}
LEN_M = Matrix(((-1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))   # a body built along Z lying along Y
FORMS = (('SOLID', 'Solid', 'A solid mass'), ('PLATE', 'Plate', 'A thin plate of that shape (Thickness)'))
FAMILIES = (('POLY', 'Polygon', 'Flat faces only'), ('CURVE', 'Curved', 'Surfaces curved both ways'),
            ('REF', 'Real Parts', 'Exterior parts after real vehicles (Lambo, 911, F-22, tank)'))
TAG = 'mch_rshape'                    # on the object: its parameters (JSON) - what Variations / Reroll read
NAME = 'MCH_Shape'
LAST = {'level': 0}                  # (0: the shape as its parameters say; 1 - 3: without chamfers / cuts - tests)
SIDE_M = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))   # outline x -> Y, y -> Z, depth -> X
PLATE_M = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))  # a plate: facing the front (+Y)
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

def _prism(bm, pts, depth, taper=1.0, center=True):
    """The outline in XY (centred, unless not ``center``) pushed up along Z by ``depth``; the top ``taper`` times as
    big (round the centre: each side stays flat)."""
    pts = _ccw(pts)
    cx = sum(p[0] for p in pts) / len(pts) if center else 0.0
    cy = sum(p[1] for p in pts) / len(pts) if center else 0.0
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


def _cut(bm, plane, keep_min=0.5, off=None):
    """One flat cut: the plane ``plane`` = (nx, ny, nz, frac) takes ``frac`` of the solid's extent along its normal
    away, the hole closed with one flat face.  Returns the new solid (``bm`` freed), or ``bm`` itself when the cut
    would leave less than ``keep_min`` of it or two pieces.  ``off``: the plane's place along its normal (given)."""
    n = Vector(plane[:3])
    if n.length < 1e-6:
        return bm
    n.normalize()
    vol0 = bm.calc_volume()
    work = bm.copy()
    if off is None:
        d = [v.co.dot(n) for v in work.verts]
        lo, hi = min(d), max(d)
        off = hi - (hi - lo) * float(plane[3])
    geom = list(work.verts) + list(work.edges) + list(work.faces)
    bmesh.ops.bisect_plane(work, geom=geom, dist=1e-6, plane_co=n * off, plane_no=n, clear_outer=True)
    open_e = [e for e in work.edges if len(e.link_faces) < 2]
    if open_e:
        bmesh.ops.holes_fill(work, edges=open_e, sides=0)
        bmesh.ops.remove_doubles(work, verts=list(work.verts), dist=1e-5)
        if _closed(work) and _islands(work) == 1 and work.calc_volume() > keep_min * vol0:
            bm.free()
            return work
    work.free()
    return bm


def _cut_pair(bm, plane, keep_min=0.5):
    """A cut and its mirror image across X = 0, at the same place - both or neither (a shape symmetric already stays
    so)."""
    n = Vector(plane[:3])
    if n.length < 1e-6:
        return bm
    n.normalize()
    d = [v.co.dot(n) for v in bm.verts]
    lo, hi = min(d), max(d)
    off = hi - (hi - lo) * float(plane[3])
    if abs(n.x) <= 1e-6:
        return _cut(bm, plane, keep_min, off)
    vol0 = bm.calc_volume()
    work = bm.copy()
    one = _cut(work, plane, keep_min, off)
    if one is work:
        work.free()
        return bm
    two = _cut(one, [-plane[0], plane[1], plane[2], plane[3]], keep_min, off)
    if two is one or two.calc_volume() < keep_min * vol0:
        two.free()
        return bm
    bm.free()
    return two


def _chamfer(bm, seed, amount):
    """Some edges cut flat (one segment) - which ones: ``seed``."""
    if amount <= 0:
        return
    rng = random.Random(seed)
    bm.normal_update()
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
    bm.normal_update()                                   # (after a transform: the faces' normals as they are now)
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
        bm.normal_update()
        flat = math.radians(0.1)
        joins = [e for e in bm.edges if len(e.link_faces) == 2 and e.link_faces[0][lay] == e.link_faces[1][lay]
                 and e.calc_face_angle(1.0) < flat]
        if joins:
            bmesh.ops.dissolve_edges(bm, edges=joins, use_verts=True)
    bm.faces.layers.int.remove(lay)


def _split_bent(bm, tol=1e-4):
    """A face of more than four corners that is not flat (a cut through the bent strips of a round) made triangles."""
    bm.normal_update()
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
    bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=list(bm.edges))     # (a speck of a face a cut left)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    if bm.calc_volume(signed=True) < 0:                  # (a thin plate: the guess of its outside can go wrong)
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
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


def _plate_trim(rng, sym, frac=(0.06, 0.22)):
    """A cut across a plate's edge (its normal along the plate, a little tilted): a corner or a side trimmed at an
    angle - the plate's outline."""
    a = rng.uniform(0, 2 * math.pi)
    n = Vector((math.cos(a), math.sin(a), rng.uniform(-0.25, 0.25)))
    if sym:
        n.x = abs(n.x)
    n.normalize()
    return [round(n.x, 6), round(n.y, 6), round(n.z, 6), round(rng.uniform(*frac), 6)]


def poly_params(rng, kind='MIX', slices=2, chamfer=0.3, taper=0.3, sym=False, max_sides=10, plate=0.0):
    """Random Polygon parameters; ``plate`` > 0: a plate that thick (of a shape 1 across) - the outline as a thin
    panel facing the front, its rim slanted now and then, its edges trimmed at angles."""
    if kind not in KIND_IDS:
        ks = list(MIX_WEIGHTS)
        kind = rng.choices(ks, weights=[MIX_WEIGHTS[k] for k in ks])[0]
    if kind in DESIGN_KINDS:
        return design_params(rng, kind, plate, sym, chamfer)
    if plate > 0:
        return _poly_plate_params(rng, kind, slices, chamfer, sym, max_sides, plate)
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
    kinks = _rand_kinks(rng, rng.randint(1, 2)) if kind in {'BLOCK', 'PRISM', 'SHARD'} and rng.random() < 0.5 else []
    return {'family': 'POLY', 'kind': kind, 'sym': bool(sym), 'kinks': kinks,
            'outline': [[round(x, 6), round(y, 6)] for x, y in _clean(pts)],
            'depth': round(depth, 6), 'taper': round(tp, 6), 'side': side,
            'slices': [_rand_plane(rng, sym) for _ in range(n_sl)],
            'chamfer': [rng.randrange(1, 2 ** 31 - 1), round(chamfer if rng.random() < 0.8 else 0.0, 6)]}


def _poly_plate_params(rng, kind, slices, chamfer, sym, max_sides, plate):
    if kind not in KIND_IDS:
        ks = list(MIX_WEIGHTS)
        kind = rng.choices(ks, weights=[MIX_WEIGHTS[k] for k in ks])[0]
    pts = {'BLOCK': outline_block, 'WEDGE': outline_wedge, 'STEP': outline_step,
           'SHARD': outline_shard}.get(kind, lambda r: outline_prism(r, max_sides))(rng)
    tp = 1.0 - rng.uniform(0.03, 0.12) if rng.random() < 0.6 else 1.0     # (a slanted rim: a bevelled armour edge)
    n_sl = rng.randint(1, max(1, slices + 1)) if slices > 0 else 0
    folds = _plate_folds(rng, sym)
    kinks = _rand_kinks(rng, rng.randint(1, 3)) if kind != 'STEP' else []
    if sym and any(f[1] == 0 for f in folds):            # (a ridge down the middle: the top edge peaked on it)
        mid = _top_middle(_clean(pts))
        if mid is not None and rng.random() < 0.7:
            kinks = [[round(mid, 6), round(rng.uniform(0.015, 0.035), 6), 0.0]] + kinks
    return {'family': 'POLY', 'kind': kind, 'sym': bool(sym), 'plate': round(plate, 6),
            'outline': [[round(x, 6), round(y, 6)] for x, y in _clean(pts)],
            'depth': round(plate * rng.uniform(0.85, 1.15), 6), 'taper': round(tp, 6), 'side': False,
            'slices': [_plate_trim(rng, sym) for _ in range(n_sl)],
            'chamfer': [rng.randrange(1, 2 ** 31 - 1), round(chamfer if rng.random() < 0.7 else 0.0, 6)],
            'folds': folds, 'kinks': kinks}


FOLD_STYLES = {'wrap': 3, 'ridge': 2, 'ridge_wrap': 2, 'lips': 2}


def _plate_folds(rng, sym):
    """Where a plate is bent (user: "판도 꺾여 있어야지"): [direction of the line (radians), where across (-1 .. 1 of
    the plate's half width across the line; the part beyond it bends), angle (radians; + back, - forward)].  Wrap:
    the sides bent back (a plate round a body), ridge: a V down the middle, lips: the top / bottom edge bent; the
    lines of one plate parallel (no two cross in it)."""
    U = rng.uniform
    style = rng.choices(list(FOLD_STYLES), weights=list(FOLD_STYLES.values()))[0]
    up = math.pi / 2
    tilt = 0.0 if sym else U(-0.3, 0.3)
    out = []
    if style in {'wrap', 'ridge_wrap'}:
        a = U(0.3, 0.6)
        out.append([up + tilt, a, math.radians(U(15, 45))])
        if rng.random() < 0.35 and a < 0.55:             # (a second bend further out)
            out.append([up + tilt, U(a + 0.15, 0.9), math.radians(U(10, 30))])
        if not sym and rng.random() < 0.6:               # (the other side too)
            out.append([up + tilt, -U(0.3, 0.6), math.radians(U(15, 45))])
    if style in {'ridge', 'ridge_wrap'}:
        out.append([up + tilt, 0.0, math.radians(U(8, 22) * (1 if sym else 2))])
    if style == 'lips':
        for side in rng.sample((1, -1), rng.randint(1, 2)):
            out.append([0.0, side * U(0.4, 0.75), math.radians(U(20, 50) * (1 if rng.random() < 0.75 else -1))])
    return [[round(v, 6) for v in f] for f in out]


def _fold(bm, ang, frac, theta):
    """Bend the plate (lying in XY, its middle at Z = 0) along a line: direction ``ang``, ``frac`` of the half
    width across it from the middle; the part beyond the line turns ``theta`` about it (toward +Z: the back once the
    plate stands).  The points on the line go to the mitre (half way between the two sides' planes): each side stays
    flat."""
    d = Vector((math.cos(ang), math.sin(ang), 0.0))
    u = Vector((d.y, -d.x, 0.0))                         # (a line up the plate: its far side +X - the half kept
    vals = [v.co.dot(u) for v in bm.verts]               #  when the plate is made symmetric)
    lo, hi = min(vals), max(vals)
    pos = (lo + hi) / 2 + frac * (hi - lo) / 2
    if frac < 0:                                         # (the far side: away from the middle)
        u, pos = -u, -pos
    if not any(v.co.dot(u) > pos + 1e-4 for v in bm.verts) or abs(theta) < 1e-4:
        return
    P = u * pos
    bmesh.ops.bisect_plane(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces), dist=1e-6, plane_co=P,
                           plane_no=u)
    R = Matrix.Rotation(theta, 3, u.cross(Vector((0.0, 0.0, 1.0))))   # (about u x Z: u turns toward +Z)
    t2 = math.tan(theta / 2)
    lay = bm.verts.layers.int.get(CREASE) or bm.verts.layers.int.new(CREASE)
    for v in bm.verts:
        s = v.co.dot(u) - pos
        if s > 1e-6:
            v.co = P + R @ (v.co - P)
        elif s > -1e-6:
            v.co = v.co - u * (v.co.z * t2)
            v[lay] = 1


CREASE = '_mch_crease'                # (bmesh vertex flag: a point a fold moved onto its mitre)


def _split_twisted(bm, tol=1e-5):
    """A face of four corners or more on a fold line that the bend twisted (a thin rim, a chamfer across the line)
    made triangles; the faces away from the fold lines left as they are."""
    lay = bm.verts.layers.int.get(CREASE)
    if lay is None:
        return
    bm.normal_update()                                   # (moved points: the faces' normals as they are now)
    bent = []
    for f in bm.faces:
        if len(f.verts) > 3 and any(v[lay] for v in f.verts):
            n, c = f.normal, f.calc_center_median()
            if any(abs((v.co - c).dot(n)) > tol for v in f.verts):
                bent.append(f)
    if bent:
        bmesh.ops.triangulate(bm, faces=bent, quad_method='BEAUTY', ngon_method='BEAUTY')
    bm.verts.layers.int.remove(lay)


# --- kinked outlines (0.24.95 user: "지금 빨간 선처럼 일자인데, 내가 그린 노란 선처럼 꺾이는 부분도 랜덤으로") ----------

def _perimeter(pts):
    n = len(pts)
    lens = [(Vector(pts[(i + 1) % n]) - Vector(pts[i])).length for i in range(n)]
    return lens, sum(lens)


def _kink_once(pts, s, h, w, a):
    """One kink at perimeter position ``s`` (0 - 1): ``w`` 0 - a point ``h`` out (+) or in (-) of the edge (a V);
    ``w`` > 0 - a flat step that wide, its flanks at the shape's angle ``a`` (a bump or a notch).  ``h`` / ``w``:
    fractions of the perimeter.  None when it does not fit the edge or the outline would cross itself."""
    lens, per = _perimeter(pts)
    pos = (s % 1.0) * per
    i = 0
    while i < len(lens) - 1 and pos > lens[i]:
        pos -= lens[i]
        i += 1
    L = lens[i]
    if L < 1e-6:
        return None
    t, H, W = pos / L, h * per, w * per
    A, B = Vector(pts[i]), Vector(pts[(i + 1) % len(pts)])
    d = B - A
    nrm = Vector((d.y, -d.x)).normalized()               # (outward: the outline is counter-clockwise)
    if W <= 0:
        if not (0.2 <= t <= 0.8) or abs(H) > 0.3 * L:
            return None
        add = [(t, H)]
    else:
        e = abs(H) / math.tan(max(math.radians(20), min(math.radians(70), a)))
        ts = (t - (W / 2 + e) / L, t - W / 2 / L, t + W / 2 / L, t + (W / 2 + e) / L)
        if ts[0] < 0.08 or ts[3] > 0.92:
            return None
        add = list(zip(ts, (0.0, H, H, 0.0)))
    new = pts[:i + 1] + [tuple(A + d * tt + nrm * hh) for tt, hh in add] + pts[i + 1:]
    new = _clean(new)
    return new if len(new) >= 3 and _simple(new) else None


def _outline_kink(pts, kinks, a_deg=40.0):
    """The outline with its kinks, one after another (a kink that does not fit: left out)."""
    pts = _ccw([tuple(q) for q in pts])
    for s, h, w in kinks or ():
        new = _kink_once(pts, s, h, w, math.radians(a_deg))
        if new is not None:
            pts = new
    return pts


def _rand_kinks(rng, n):
    out = []
    for _i in range(n):
        h = rng.uniform(0.012, 0.04) * (1 if rng.random() < 0.65 else -1)
        out.append([round(rng.random(), 6), round(h, 6), round(0.0 if rng.random() < 0.4 else rng.uniform(0.02, 0.08), 6)])
    return out


def _top_middle(pts):
    """The perimeter position (0 - 1) where the outline's top edge crosses X = 0 (None if none does)."""
    pts = _ccw([tuple(q) for q in pts])
    lens, per = _perimeter(pts)
    best, acc = None, 0.0
    for i, L in enumerate(lens):
        A, B = pts[i], pts[(i + 1) % len(pts)]
        if (A[0] - 0.0) * (B[0] - 0.0) < 0:
            t = A[0] / (A[0] - B[0])
            y = A[1] + (B[1] - A[1]) * t
            if best is None or y > best[0]:
                best = (y, (acc + t * L) / per)
        acc += L
    return None if best is None else best[1]


# --- vehicle parts: Car (Lamborghini-like wedges / Porsche-like curves), Tank (0.24.95 user: "차체를 만드는 게 아니라
#     차의 외관의 파츠, 탱크도 그렇고") ------------------------------------------------------------------------------

FACE_M = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))   # an outline's +Z face to the front (+Y)


def _part_params(rng, kind, a, plate, sym):
    """Polygon Car / Tank parts: an outline (``pts``) pushed ``depth`` (along Z, or across X for a side outline,
    ``mode`` 'side'), its top ``tp`` smaller; cuts / rim / folds / kinks from the shape's angle ``a``."""
    U = rng.uniform
    t = math.radians(a)
    p = {'family': 'POLY', 'kind': kind, 'sym': True}
    if kind == 'CAR' and plate <= 0:
        part = rng.choice(('scoop', 'spoiler', 'lamp'))
        if part == 'scoop':                              # a side air intake: a wedge seen from the side, its mouth cut
            H = U(0.28, 0.42)
            pts = [(0, 0), (1, 0), (1, H * U(0.45, 0.7)), (U(0.25, 0.45), H), (0, H * U(0.75, 0.95))]
            d = dict(mode='side', pts=pts, depth=U(0.3, 0.5), cuts=[['cheek', U(0.05, 0.12)], ['canopy', U(0.1, 0.22)]],
                     kinks=_rand_kinks(rng, rng.randint(0, 1)))
        elif part == 'spoiler':                          # a rear wing: a thin blade, long across, its tips cut
            th = U(0.08, 0.14)
            pts = [(0, 0), (1, th * 0.25), (1, th * 0.6), (U(0.25, 0.4), th), (0, th * 0.55)]
            d = dict(mode='side', pts=pts, depth=U(3.0, 5.0), cuts=[['cheek', U(0.02, 0.06)]])
        else:                                            # a headlight housing: a pointed hexagon, a Y notch, a bevel
            h = U(0.3, 0.45)
            e = min(0.3, (h / 2) / math.tan(t))
            pts = [(-0.5 + e, -h / 2), (0.5 - e, -h / 2), (0.5, 0.0), (0.5 - e, h / 2), (-0.5 + e, h / 2), (-0.5, 0.0)]
            d = dict(mode='xy', face=True, pts=pts, depth=U(0.12, 0.22), tp=U(0.65, 0.85),
                     kinks=[[U(0.55, 0.7), -U(0.02, 0.04), U(0.02, 0.05)]])
            p['sym'] = False
    elif kind == 'CAR':
        part = rng.choice(('door', 'fender', 'fender', 'fin'))
        p['sym'] = False
        if part == 'door':                               # a long pointed panel, a sharp crease along it
            h = U(0.25, 0.42)
            e = min(0.3, (h / 2) / math.tan(t))
            pts = [(-0.5 + e, -h / 2), (0.5 - e, -h / 2), (0.5, 0.0), (0.5 - e, h / 2), (-0.5 + e, h / 2), (-0.5, 0.0)]
            p['folds'] = [[0.0, U(-0.3, 0.3), math.radians(U(12, 28))]]
            kinks = _rand_kinks(rng, rng.randint(1, 3))
        elif part == 'fender':                           # a panel with a hexagonal wheel arch in its bottom edge
            h, r = U(0.38, 0.55), U(0.2, 0.27)
            ad, ac = U(0.45, 0.7) * h, U(-0.15, 0.15)
            rf = r - ad / math.tan(t)
            rf = max(0.25 * r, rf)
            c = U(0.04, 0.1)
            pts = [(-0.5, -h / 2), (ac - r, -h / 2), (ac - rf, -h / 2 + ad), (ac + rf, -h / 2 + ad), (ac + r, -h / 2),
                   (0.5, -h / 2), (0.5, h / 2 - c), (0.5 - c, h / 2), (-0.5, h / 2)]
            p['folds'] = [[0.0, U(-0.7, -0.4), math.radians(U(10, 25))]]
            kinks = _rand_kinks(rng, rng.randint(0, 2))
        else:                                            # a splitter / diffuser fin, swept at the shape's angle
            h = U(0.25, 0.5)
            pts = [(-0.5, 0.0), (0.5, 0.0), (0.5 - h / math.tan(t), h), (-0.5 + U(0.0, 0.3), h)]
            kinks = _rand_kinks(rng, rng.randint(0, 1))
        d = dict(mode='xy', pts=pts, depth=plate, kinks=kinks, rim=plate * U(0.3, 0.6))
    elif plate <= 0:                                     # Tank parts, solid
        part = rng.choice(('era', 'cheek', 'mantlet', 'box'))
        if part == 'era':                                # a reactive-armour block: its face sloped
            W = U(0.45, 0.7)
            d = dict(mode='xy', pts=_rect(W, 1.0), depth=U(0.15, 0.28), cuts=[['canopy', U(0.15, 0.3)]],
                     rim=U(0.006, 0.014), kinks=_rand_kinks(rng, rng.randint(0, 1)))
        elif part == 'cheek':                            # a turret cheek module: an arrowhead, its top sloped
            W, fw = U(0.5, 0.8), U(0.05, 0.25)
            wd = min(0.45, (W / 2 - fw * W / 2) * math.tan(math.radians(90 - a)))
            pts = [(-W / 2, -0.5), (W / 2, -0.5), (W / 2, 0.5 - wd), (fw * W / 2, 0.5), (-fw * W / 2, 0.5),
                   (-W / 2, 0.5 - wd)]
            d = dict(mode='xy', pts=pts, depth=U(0.15, 0.25), tp=U(0.8, 0.92), cuts=[['canopy', U(0.15, 0.3)]],
                     rim=U(0.006, 0.014))
        elif part == 'mantlet':                          # a gun mantlet: a wide hexagon, its sides sloped back
            h = U(0.35, 0.55)
            e = min(0.3, (h / 2) / math.tan(t))
            pts = [(-0.5 + e, -h / 2), (0.5 - e, -h / 2), (0.5, 0.0), (0.5 - e, h / 2), (-0.5 + e, h / 2), (-0.5, 0.0)]
            d = dict(mode='xy', face=True, pts=pts, depth=U(0.25, 0.45), tp=U(0.6, 0.8), rim=U(0.004, 0.01))
        else:                                            # a stowage box: a lid edge chamfered
            d = dict(mode='xy', pts=_rect(U(0.35, 0.6), 1.0), depth=U(0.25, 0.45), rim=U(0.015, 0.03),
                     kinks=_rand_kinks(rng, rng.randint(0, 1)))
    else:                                                # Tank parts, plates
        part = rng.choice(('skirt', 'skirt', 'guard'))
        p['sym'] = False
        if part == 'skirt':                              # a side skirt: its corners at the shape's angle, a kinked edge
            h = U(0.28, 0.6)
            c1, c2, sl = U(0.1, 0.3) * h, U(0.0, 0.08) * h, rng.choice((0.0, U(0.05, 0.2))) * h
            pts = [(-0.5 + c1 / math.tan(t), -h / 2), (0.5 - c2, -h / 2 + sl), (0.5, -h / 2 + sl + c2), (0.5, h / 2 - c2),
                   (0.5 - c2, h / 2), (-0.5 + c2, h / 2), (-0.5, h / 2 - c2), (-0.5, -h / 2 + c1)]
            kinks = _rand_kinks(rng, rng.randint(1, 3))
            style = rng.choice(('lip', 'ridge', 'ridge', 'none'))
            if style == 'lip':
                p['folds'] = [[0.0, -U(0.55, 0.8), math.radians(U(15, 35))]]
            elif style == 'ridge':                       # (a V down the middle, the top edge peaked on it)
                p['folds'] = [[math.pi / 2, 0.0, math.radians(U(12, 28))]]
                mid = _top_middle(_clean(pts))
                if mid is not None:
                    kinks = [[mid, U(0.015, 0.035), 0.0]] + kinks
        else:                                            # a track guard: long, narrow, its ends bent back
            pts = _rect(1.0, U(0.15, 0.3))
            p['folds'] = [[math.pi / 2, U(0.6, 0.85), math.radians(U(20, 40))],
                          [math.pi / 2, -U(0.6, 0.85), math.radians(U(15, 35))]]
            kinks = _rand_kinks(rng, rng.randint(0, 1))
        d = dict(mode='xy', pts=pts, depth=plate, kinks=kinks, rim=plate * U(0.3, 0.7))
    d.update(a=a, form='part', part=part, pts=[[round(x, 6), round(y, 6)] for x, y in _clean(d['pts'])])
    p['d'] = d
    if plate > 0:
        p['plate'] = round(plate, 6)
    return _rounded(p)


def _part(bm, d, level):
    pts = _outline_kink(d['pts'], d.get('kinks') if level < 2 else None, d['a'])
    _prism(bm, pts, d['depth'], d.get('tp', 1.0))
    if d.get('mode') == 'side':
        bmesh.ops.transform(bm, matrix=SIDE_M, verts=list(bm.verts))
    if d.get('face'):
        bmesh.ops.transform(bm, matrix=FACE_M, verts=list(bm.verts))


# --- Jet / Tank: designed shapes - one angle repeated (0.24.95 user: "좀 더 리얼한 메카에 쓸 수 있도록 예쁘고 정교한 형태,
#     제트기나 탱크에 가까운 형태로") -------------------------------------------------------------------------------------
#
# What makes a jet or a tank look made, not random: few angles, repeated (a stealth jet's edges parallel, a tank's
# plates all at one slope).  Each shape here has its angle ``a``: every slope, sweep and cut comes from it.

DESIGN_KINDS = {'JET', 'TANK', 'CAR'}


def _design_plane(name, a):
    """The normal of a designed cut (``a`` in radians): its slope from the shape's one angle."""
    s, c = math.sin(a), math.cos(a)
    n = {'canopy': (0.0, s, c), 'chin': (0.0, s, -c), 'cheek': (c, s, 0.0), 'cheek_low': (c, s, -1.0),
         'tail': (0.0, -s, c), 'tail_low': (0.0, -s, -c), 'shoulder': (c, 0.0, s),
         'glacis_up': (0.0, math.sin(a / 2), math.cos(a / 2)), 'glacis_low': (0.0, s, -c),
         'rear': (0.0, -s, c), 'sponson': (s, 0.0, c)}[name]
    v = Vector(n).normalized()
    return [v.x, v.y, v.z]


def design_params(rng, kind, plate=0.0, sym=True, chamfer=0.3):
    """Random Jet / Tank parameters: ``d`` holds the shape's numbers (its angle ``a`` in degrees) - the cuts by name,
    their normals from ``a`` when built (a variation keeps them aligned)."""
    U = rng.uniform
    a = rng.choice((30.0, 35.0, 40.0, 45.0, 50.0)) + U(-2.0, 2.0)
    p = {'family': 'POLY', 'kind': kind, 'sym': True, 'chamfer': [rng.randrange(1, 2 ** 31 - 1), 0.0]}
    if kind == 'JET' and plate <= 0:                     # a chined fuselage / nose
        d = dict(a=a, form='body', L=1.0, W=U(0.32, 0.6), H=U(0.18, 0.32), hb=U(0.35, 0.55), zc=U(-0.05, 0.25),
                 bw=U(0.35, 0.7), tw=rng.choice((0.0, U(0.15, 0.45))),
                 st=[[0.0, U(0.75, 0.95), 0.0], [U(0.25, 0.45), 1.0, 0.0], [U(0.6, 0.75), U(0.65, 0.85), U(-0.1, 0.05)],
                     [1.0, U(0.12, 0.3), U(-0.25, 0.0)]])
        names = rng.sample(['canopy', 'chin', 'cheek', 'cheek_low', 'tail'], rng.randint(1, 3))
        d['cuts'] = [[nm, U(0.06, 0.16)] for nm in names]
    elif kind == 'JET':                                  # a swept wing / a fin, knife edges
        style = rng.choice(('delta', 'trapezoid', 'swept', 'cropped'))
        le, te = {'delta': (U(50, 62), U(-3, 3)), 'trapezoid': (U(35, 45), U(-18, 0)),
                  'swept': (U(30, 40), U(18, 30)), 'cropped': (U(40, 52), U(0, 10))}[style]
        d = dict(a=le, form='wing', S=U(0.7, 1.3), le=le, te=te, t=plate, kn=U(0.05, 0.1), style=style)
        p['sym'] = bool(sym)
    else:
        return _part_params(rng, kind, a, plate, sym)
    p['d'] = d
    if plate > 0:
        p['plate'] = round(plate, 6)
    return _rounded(p)


def _jet_body(bm, d):
    """A chined fuselage along Y (the nose at +Y): a hexagon section (the chine sharp at the sides, a flat bottom,
    a deck or a ridge on top), scaled at stations - the same shape each time (homothetic), so every facet is flat."""
    W, H, L = d['W'], d['H'], d['L']
    hb, ht = d['hb'] * H, (1 - d['hb']) * H
    zc = -hb + (d['zc'] + 0.5) * 0.5 * H
    cw, bw, tw = W / 2, d['bw'] * W / 2, d['tw'] * W / 2
    sec = [(-bw, -hb), (bw, -hb), (cw, zc)] + ([(tw, ht), (-tw, ht)] if tw > 0.01 else [(0.0, ht)]) + [(-cw, zc)]
    rings = []
    for yf, s, dz in d['st']:
        y = -L / 2 + yf * L
        rings.append([bm.verts.new((x * s, y, z * s + dz * H)) for x, z in sec])
    _loft(bm, rings)


def _wing(bm, d, level):
    """A swept plate in XY (root at X = 0, the leading edge at +Y), ``t`` thick; its leading / trailing / tip edges
    cut to knife edges on both faces (each cut through the edge's middle, ``kn`` in on the face)."""
    Cr, S = 1.0, d['S']
    tl, tt = math.tan(math.radians(d['le'])), math.tan(math.radians(d['te']))
    if Cr - S * (tl - tt) < 0.15 * Cr and tl - tt > 1e-6:
        S = (0.85 * Cr) / (tl - tt)
    yl, yt = Cr / 2 - S * tl, -Cr / 2 - S * tt
    pts = [(0.0, -Cr / 2), (S, yt), (S, yl), (0.0, Cr / 2)]
    t = d['t']
    _prism(bm, pts, t, 1.0, center=False)
    if level >= 2:
        return
    edges = [((0.0, Cr / 2), (S, yl), d['kn']), ((0.0, -Cr / 2), (S, yt), d['kn'] * 0.6), ((S, yt), (S, yl), d['kn'] * 0.4)]
    for (x0, y0), (x1, y1), kn in edges:
        e = Vector((x1 - x0, y1 - y0, 0.0))
        m = Vector((e.y, -e.x, 0.0)).normalized()
        if m.dot(Vector((x0 - S / 2, y0, 0.0))) < 0:     # (outward: away from the plate's middle)
            m = -m
        e0 = Vector((x0, y0, 0.0))
        for zs in (1, -1):
            n = (m * (t / 2) + Vector((0.0, 0.0, zs * kn))).normalized()
            bm = _cut(bm, [n.x, n.y, n.z, 0.0], 0.3, n.dot(e0))
    return bm


def _rim_chamfer(bm, w, axis=(0.0, 0.0, 1.0)):
    """The edges round the face looking along ``axis`` (+Z) chamfered ``w`` wide - a machined rim."""
    if w <= 0:
        return
    bm.normal_update()
    ax = Vector(axis)
    top = [f for f in bm.faces if f.normal.dot(ax) > 0.999]
    edges = list({e for f in top for e in f.edges})
    if edges:
        bmesh.ops.bevel(bm, geom=edges, offset=w, offset_type='OFFSET', segments=1, profile=0.5, affect='EDGES',
                        clamp_overlap=True)


def build_design(p, level=0):
    """The solid of Jet / Tank parameters ``p``; ``level`` 1: without its rim chamfer, 2: without its cuts."""
    d = p['d']
    a = math.radians(d['a'])
    bm = bmesh.new()
    form = d['form']
    if form == 'body':
        _jet_body(bm, d)
    elif form == 'wing':
        bm = _wing(bm, d, level) or bm
    else:
        _part(bm, d, level)
    if level < 2:
        for name, frac in d.get('cuts', ()):
            bm = _cut(bm, _design_plane(name, a) + [frac], 0.5)
    if level < 1:
        _rim_chamfer(bm, d.get('rim', 0.0), (0.0, 1.0, 0.0) if d.get('face') else (0.0, 0.0, 1.0))
    folds = p.get('folds') or ()
    if folds:
        for ang, frac, theta in sorted(folds, key=lambda f: -abs(f[1])):
            _fold(bm, ang, frac, theta)
        _split_twisted(bm)
    if p.get('plate'):
        bmesh.ops.transform(bm, matrix=PLATE_M, verts=list(bm.verts))
    if p.get('sym'):
        symmetrize(bm)
    return bm


def _vary_design(q, a, rng):
    d = q['d']
    if 'pts' in d:
        d['pts'] = _vary_outline(rng, d['pts'], 'PART', a * 0.6)
    if d.get('kinks'):
        d['kinks'] = [[k[0] + rng.uniform(-0.02, 0.02) * a, k[1] * (1 + rng.uniform(-0.25, 0.25) * a),
                       k[2] * (1 + rng.uniform(-0.25, 0.25) * a)] for k in d['kinks']]
    for k, v in list(d.items()):
        if k in {'a', 'le', 'te'}:
            d[k] = v + rng.uniform(-4.0, 4.0) * a
        elif k in {'t', 'L'}:
            continue
        elif isinstance(v, float):
            d[k] = max(0.0, v * (1 + rng.uniform(-0.15, 0.15) * a))
    if d.get('form') == 'wing':
        d['a'] = d['le']
    if 'st' in d:
        d['st'] = [[st[0], max(0.05, st[1] * (1 + rng.uniform(-0.12, 0.12) * a)), st[2] + rng.uniform(-0.04, 0.04) * a]
                   for st in d['st']]
    if 'cuts' in d:
        d['cuts'] = [[nm, max(0.02, min(0.4, fr + rng.uniform(-0.04, 0.04) * a))] for nm, fr in d['cuts']]


def build_poly(p, level=0):
    """The solid of Polygon parameters ``p``; ``level`` 1: without its chamfers, 2: without its slices too."""
    if p.get('kind') in DESIGN_KINDS and 'd' in p:
        return build_design(p, level)
    bm = bmesh.new()
    pts = _outline_kink(p['outline'], p.get('kinks') if level < 2 else None, 40.0)
    _prism(bm, pts, p['depth'], p['taper'])
    if p.get('side'):                                    # the outline seen from the side: X across it
        bmesh.ops.transform(bm, matrix=SIDE_M, verts=list(bm.verts))
    if level < 2:
        for pl in p.get('slices', ()):
            bm = _cut(bm, pl, 0.5)
    ch = p.get('chamfer') or (0, 0.0)
    if level < 1 and ch[1] > 0:
        _chamfer(bm, int(ch[0]), float(ch[1]))
    folds = p.get('folds') or ()
    if folds:                                            # (outermost first: an inner bend carries the outer ones)
        for ang, frac, theta in sorted(folds, key=lambda f: -abs(f[1])):
            _fold(bm, ang, frac, theta)
        _split_twisted(bm)
    if p.get('plate'):                                   # (a plate stands facing the front)
        bmesh.ops.transform(bm, matrix=PLATE_M, verts=list(bm.verts))
    if p.get('sym'):
        symmetrize(bm)
    return bm


# --- Curved: a section of 4 - 8 sides, rounded, its sides bulging ---------------------------------------------------

def section(n, rnd, bulge, front, segs, back=1.0):
    """The cross-section: a polygon of ``n`` sides (a corner or a side to the front, +Y), its corners rounded
    (``rnd`` 0 - 1: 1 round all along), its sides bulging out (``bulge``); symmetric about X = 0 with a point on it at
    the front and at the back (the first point: the front); in a box of -1 .. 1, the back half ``back`` times as
    deep (under 1: a flatter back - a cockpit / a chest on its frame).  ``n`` of 16 and more: round."""
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
    out = [[p.x / xm, (p.y - yc) / yh] for p in pts]
    for sign in (1, -1):                                 # (the front and the back point: exactly on the centre line)
        i = min((i for i in range(len(out)) if out[i][1] * sign > 0), key=lambda i: abs(out[i][0]))
        out[i][0] = 0.0
    out = [(x, y if y >= 0 else y * back) for x, y in out]
    first = max((i for i in range(len(out)) if out[i][0] == 0.0), key=lambda i: out[i][1])
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


def _rows(c0, c1, f0=0.0, f1=0.0, nrows=None):
    """(t, scale) along a body of round ends ``c0`` (bottom) / ``c1`` (top) - a quarter of an oval each, a step of
    15 degrees at most (the round stays smooth: under the Edge Memory's 30 degrees); an end closes in a point, or
    (``f0`` / ``f1`` > 0) on a flat face that much of the section across - a rounded rim round a flat top."""
    c0, c1 = max(0.0, c0), max(0.0, c1)
    f0, f1 = max(0.0, min(0.95, f0)), max(0.0, min(0.95, f1))
    if c0 + c1 > 0.9:
        k = 0.9 / (c0 + c1)
        c0, c1 = c0 * k, c1 * k
    rows = []
    k = 6
    if c0 > 0.01:
        rows += [(c0 * (1 - math.cos(math.pi / 2 * i / k)), f0 + (1 - f0) * math.sin(math.pi / 2 * i / k))
                 for i in range(k)]
    nb = max(2, int(round((1 - c0 - c1) * (nrows or CUT_ROWS))))
    rows += [(c0 + (1 - c0 - c1) * i / nb, 1.0) for i in range(nb + 1)]
    if c1 > 0.01:
        rows += [(1 - c1 + c1 * math.sin(math.pi / 2 * i / k), f1 + (1 - f1) * math.cos(math.pi / 2 * i / k))
                 for i in range(1, k + 1)]
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


def body_rings(p, segs):
    """[(t, scale, ring)] of a body along Z: the section scaled by the width / depth profiles, moved forward by the ``y``
    profile, its ends round (``c0`` / ``c1``: to a point, or to a flat face ``cf0`` / ``cf1`` across) or flat; a ring
    of one point where an end closes."""
    sec = section(p['n'], p['round'], p['bulge'], p['front'], segs, p.get('back', 1.0))
    W, D, L = p['W'], p['D'], p['L']
    out = []
    back = p.get('back', 1.0)
    for t, sc in _rows(p['c0'], p['c1'], p.get('cf0', 0.0), p.get('cf1', 0.0), p.get('rows')):
        w = max(0.05, _spline(p['w'], t)) * sc * W / 2
        dd = max(0.05, _spline(p['d'], t)) * sc * D / 2
        yo = _spline(p['y'], t) * D / 2
        if p.get('floor'):                               # (a flat floor: the bottom held where it is)
            yo += back * (dd - D / 2)
        z = t * L
        if sc < 1e-6:
            out.append((t, sc, [(0.0, yo, z)]))
            continue
        if p.get('cab'):                                 # a cabin / canopy over the shoulder line: its own height
            sh = p.get('sh', 0.15)                       # (along the length) and narrower toward its top
            ch = max(0.05, _spline(p['cab'], t))
            tw = p.get('tw', 0.7)
            ring = []
            for x, y in sec:
                if y <= sh:
                    ring.append((x * w, y * dd + yo, z))
                else:
                    f = min(1.0, (y - sh) / (1.0 - sh))
                    ring.append((x * w * (1.0 - (1.0 - tw) * f), (sh + (y - sh) * ch) * dd + yo, z))
            out.append((t, sc, ring))
            continue
        out.append((t, sc, [(x * w, y * dd + yo, z) for x, y in sec]))
    return out


def body(bm, p, segs):
    _loft(bm, [[bm.verts.new(c) for c in ring] for _t, _sc, ring in body_rings(p, segs)])


def plate_patch(bm, p, segs):
    """A curved plate: the front of the body (``plate['span']`` of the way round, rows ``t0`` .. ``t1``) - curved
    as the body is, both ways - made ``plate['thk']`` thick inward (of the patch's size)."""
    pl = p['plate']
    rings = [(t, r) for t, sc, r in body_rings(p, segs) if sc >= 0.5]   # (not where a round end closes in)
    sel = [r for t, r in rings if pl['t0'] - 1e-9 <= t <= pl['t1'] + 1e-9]
    if len(sel) < 3:
        sel = [r for _t, r in rings]
    m = len(sel[0])
    half = max(2, min(m // 2 - 2, int(round(m * pl['span'] / 2))))
    idx = [i % m for i in range(-half, half + 1)]        # (the front point in the middle: symmetric)
    P = [[Vector(r[i]) for i in idx] for r in sel]
    grid = [[bm.verts.new(q) for q in row] for row in P]
    for a, b in zip(grid, grid[1:]):
        for i in range(len(grid[0]) - 1):
            bm.faces.new((a[i], a[i + 1], b[i + 1], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    mid = sel[len(sel) // 2]
    axis_pt = sum((Vector(q) for q in mid), Vector()) / len(mid)
    if sum((f.calc_center_median() - axis_pt).dot(f.normal) for f in bm.faces) < 0:   # (the outside facing out)
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    co = [v.co for v in bm.verts]
    size = max(max(c[i] for c in co) - min(c[i] for c in co) for i in range(3))
    bmesh.ops.solidify(bm, geom=list(bm.faces), thickness=pl['thk'] * size)


def fender(bm, p, segs):
    """A fender skin: ``L`` 1 along Y, ``H`` up; bulging out (+X) over the wheel (``hip`` - most at the middle of its
    length and a little below its middle height), its top rolling in (``roll``), a round arch out of its bottom edge
    (``arch``: middle ``u``, half width ``r`` along, height ``h`` up); ``thk`` thick inward."""
    f = p['fender']
    H, ar = f['H'], f['arch']
    nu, nv = max(24, segs), max(10, segs // 3)

    def x_of(u, v):
        return f['hip'] * math.sin(math.pi * u) * max(0.0, 1.0 - ((v - 0.4) / 0.75) ** 2) - f['roll'] * max(0.0, v - 0.5) ** 2 * 4
    grid = []
    for i in range(nu):
        u = i / (nu - 1)
        du = (u - ar['u']) / ar['r']
        v0 = ar['h'] * math.sqrt(1.0 - du * du) if abs(du) < 1.0 else 0.0
        row = []
        for j in range(nv):
            v = v0 + (1.0 - v0) * j / (nv - 1)
            row.append(bm.verts.new((x_of(u, v), u - 0.5, v * H)))
        grid.append(row)
    for a, b in zip(grid, grid[1:]):
        for j in range(nv - 1):
            bm.faces.new((a[j], a[j + 1], b[j + 1], b[j]))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    if sum(fc.normal.x for fc in bm.faces) < 0:          # (the outside: +X)
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    bmesh.ops.solidify(bm, geom=list(bm.faces), thickness=f['thk'])


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


CUT_WEIGHTS = {                       # visor, chisel, cheek, chin, top, back, shoulder
    'POD': (4, 3, 2, 2, 1, 1, 0), 'DOMECUT': (3, 4, 3, 2, 0, 1, 0), 'TORSO': (1, 4, 1, 2, 0, 1, 3),
    'CAPSULE': (1, 1, 3, 1, 1, 2, 0), 'CAR': (0, 0, 1, 2, 0, 0, 0), 'JET': (0, 0, 1, 2, 0, 0, 0),
    'TANK': (3, 0, 1, 0, 0, 1, 0)}


def _curve_cut(rng, kind, sym):
    """A flat cut for a curved body of ``kind``: the face (visor), a chisel (to one side of the front - mirrored:
    a ridge down the middle), a cheek, the chin, the top, the back, a shoulder; a Shell's corners."""
    U = rng.uniform
    deep = 1.5 if kind == 'DOMECUT' else 1.0
    if kind == 'SHELL':
        n = (U(0.3, 1.0), U(-0.25, 0.25), U(0.3, 1.0) * rng.choice((-1, 1)))
        fr = U(0.05, 0.2)
    else:
        c = rng.choices(('visor', 'chisel', 'cheek', 'chin', 'top', 'back', 'shoulder'),
                        weights=CUT_WEIGHTS.get(kind, CUT_WEIGHTS['POD']))[0]
        if c == 'chisel':
            n, fr = (U(0.3, 0.7), 1.0, U(-0.3, 0.5)), U(0.08, 0.17) * deep
        elif c == 'shoulder':
            n, fr = (U(0.4, 0.9), U(-0.2, 0.3), 1.0), U(0.06, 0.15)
        elif c == 'visor':
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


def curve_params(rng, kind='MIX', cuts=2, sym=True, plate=0.0):
    """Random Curved parameters; ``plate`` > 0: a plate that thick (of the plate's size) - the front of the body,
    curved as it is, its outline trimmed at angles."""
    if kind not in CURVE_IDS:
        ks = list(CURVE_MIX)
        kind = rng.choices(ks, weights=[CURVE_MIX[k] for k in ks])[0]
    U = rng.uniform
    p = {'family': 'CURVE', 'kind': kind, 'sym': bool(sym)}
    if kind == 'SHELL':
        p.update(R=U(0.35, 0.9), thk=plate if plate > 0 else U(0.05, 0.12),
                 A=[U(60, 120), U(90, 150), U(60, 120)], L=U(0.6, 1.2), bend=U(0.0, 0.35))
        if plate > 0:
            p['plate'] = round(plate, 6)
        n_c = rng.randint(0, cuts) if cuts else 0
        p['cuts'] = [_curve_cut(rng, kind, sym) for _ in range(n_c)]
        return _rounded(p)
    if kind == 'POD':                                    # a cockpit: a rounded box, its face cut flat, a flat back
        p.update(n=rng.choice((4, 5, 6, 6, 8)), round=U(0.0, 0.35), bulge=U(0.05, 0.25),
                 front=rng.choice(('VERTEX', 'SIDE')), back=U(0.55, 0.9), W=1.0, D=U(0.7, 1.1), L=U(0.6, 1.0),
                 w=[U(0.75, 0.95), U(0.95, 1.05), U(0.9, 1.0), U(0.7, 0.9)],
                 d=[U(0.7, 0.9), U(0.95, 1.05), U(0.9, 1.0), U(0.65, 0.85)],
                 y=[U(-0.1, 0.0), U(0.0, 0.12), U(0.0, 0.1), U(-0.05, 0.05)],
                 c0=U(0.05, 0.15), cf0=U(0.6, 0.9), c1=U(0.12, 0.3), cf1=U(0.35, 0.75))
        n_c = rng.randint(2, cuts + 1) if cuts else 0
    elif kind == 'TORSO':                                # a chest: wide shoulders, the chest forward, a flat back
        p.update(n=rng.choice((5, 6, 6, 8)), round=U(0.05, 0.3), bulge=U(0.08, 0.25),
                 front='VERTEX' if rng.random() < 0.6 else 'SIDE', back=U(0.5, 0.8), W=1.0, D=U(0.55, 0.8),
                 L=U(0.8, 1.2), w=[U(0.5, 0.7), U(0.65, 0.85), U(0.95, 1.05), U(0.85, 1.0)],
                 d=[U(0.6, 0.8), U(0.75, 0.9), U(0.95, 1.05), U(0.7, 0.85)],
                 y=[0.0, U(0.02, 0.08), U(0.1, 0.2), U(0.0, 0.08)],
                 c0=U(0.0, 0.1), cf0=U(0.6, 0.9), c1=U(0.1, 0.25), cf1=U(0.3, 0.7))
        n_c = rng.randint(1, cuts + 1) if cuts else 0
    elif kind == 'CAPSULE':                              # a limb segment
        n = rng.choice((5, 6, 8, 24))
        p.update(n=n, round=U(0.15, 0.6) if n < 16 else 0.0, bulge=U(0.0, 0.2), front=rng.choice(('VERTEX', 'SIDE')),
                 back=U(0.75, 1.0), W=U(0.4, 0.7), D=U(0.4, 0.7), L=1.0,
                 w=[U(0.5, 0.8), U(0.85, 1.0), U(0.75, 0.95), U(0.45, 0.7)],
                 d=[U(0.5, 0.8), U(0.85, 1.0), U(0.75, 0.95), U(0.45, 0.7)],
                 y=[0.0, U(-0.1, 0.1), U(-0.05, 0.1), 0.0],
                 c0=U(0.08, 0.3), cf0=rng.choice((0.0, U(0.4, 0.8))), c1=U(0.1, 0.3), cf1=rng.choice((0.0, U(0.4, 0.8))))
        n_c = rng.randint(0, min(2, cuts)) if cuts else 0
    elif kind == 'JET':                                  # a blended fuselage (tail 0 .. nose 1): soft side chines
        p.update(n=4, round=U(0.3, 0.6), bulge=U(0.15, 0.3), front='VERTEX', back=U(0.6, 0.85),
                 W=U(0.3, 0.45), D=U(0.2, 0.3), L=1.0, axis='Y', floor=False, rows=24, sh=U(0.3, 0.5),
                 tw=U(0.4, 0.6), cab=[1.0, U(1.0, 1.1), U(1.5, 2.0), U(1.3, 1.7), U(0.8, 1.0)],
                 w=[U(0.75, 0.9), U(0.95, 1.05), U(0.9, 1.0), U(0.65, 0.8), U(0.35, 0.5)],
                 d=[U(0.6, 0.75), U(0.85, 0.95), U(0.95, 1.05), U(0.7, 0.85), U(0.4, 0.55)],
                 y=[0.0, 0.0, U(0.05, 0.15), U(0.0, 0.08), U(-0.15, -0.05)],
                 c0=U(0.02, 0.05), cf0=U(0.55, 0.75), c1=U(0.15, 0.28), cf1=0.0)
        n_c = rng.randint(0, 1) if cuts else 0
    elif kind in {'CAR', 'TANK'}:                        # vehicle parts (0.24.95 user: "차의 외관의 파츠, 탱크도 그렇고")
        return _curve_part_params(rng, kind, cuts, sym, plate)
    else:                                                # DOMECUT: a round mass, faces cut in, ridges where two meet
        p.update(n=rng.choice((5, 6, 7, 8)), round=U(0.15, 0.5), bulge=U(0.1, 0.3),
                 front='VERTEX' if rng.random() < 0.7 else 'SIDE', back=U(0.8, 1.0), W=1.0, D=U(0.95, 1.2),
                 L=U(0.75, 1.0), w=[U(0.85, 0.95), U(0.95, 1.05), U(0.9, 1.0), U(0.6, 0.8)],
                 d=[U(0.85, 0.95), U(0.95, 1.05), U(0.9, 1.0), U(0.6, 0.8)],
                 y=[U(0.0, 0.08), U(0.0, 0.08), 0.0, U(-0.08, 0.0)],
                 c0=rng.choice((0.0, U(0.03, 0.1))), cf0=0.85, c1=U(0.4, 0.65), cf1=U(0.0, 0.25))
        n_c = rng.randint(3, cuts + 2) if cuts else 0
    if plate > 0 and kind in {'JET', 'CAR'}:             # (a plate of a vehicle: its top skin - hood, roof, fender)
        p['plate'] = {'thk': round(plate, 6), 'span': U(0.2, 0.42), 't0': U(0.05, 0.45), 't1': U(0.6, 0.97)}
        p['cuts'] = [_curve_cut(rng, 'SHELL', sym) for _ in range(rng.randint(0, 2))]
        return _rounded(p)
    if plate > 0:                                        # (a plate: the front of the body, its own trims)
        p['plate'] = {'thk': round(plate, 6), 'span': U(0.25, 0.5), 't0': U(0.05, 0.3), 't1': U(0.7, 0.97)}
        n_t = rng.randint(1, cuts + 1) if cuts else 0
        p['cuts'] = [_curve_cut(rng, 'SHELL', sym) for _ in range(n_t)]
        return _rounded(p)
    p['cuts'] = [_curve_cut(rng, kind, sym) for _ in range(n_c)]
    return _rounded(p)


def _porsche_body(rng):
    """A curved sports car along its length (rear 0 .. nose 1) - the body the Car plates are taken from."""
    U = rng.uniform
    rp = U(0.38, 0.5)
    return dict(n=rng.choice((6, 8)), round=U(0.5, 0.85), bulge=U(0.08, 0.2), front='SIDE', back=U(0.45, 0.65),
                W=U(0.42, 0.5), D=U(0.16, 0.2), L=1.0, axis='Y', floor=True, rows=30, sh=U(0.05, 0.25), tw=U(0.55, 0.75),
                w=[U(0.84, 0.9), U(0.98, 1.06), U(0.86, 0.92), U(0.84, 0.9), U(0.92, 0.99), U(0.72, 0.82)],
                d=[U(0.85, 0.95), U(0.95, 1.05), U(0.95, 1.0), U(0.9, 0.98), U(0.8, 0.9), U(0.55, 0.7)],
                cab=[U(0.2, 0.35), U(0.45, 0.8) if rp < 0.44 else U(0.35, 0.5), U(1.7, 2.3), U(1.2, 1.7), U(0.25, 0.4),
                     U(0.12, 0.25)],
                y=[0.0] * 6, c0=U(0.03, 0.07), cf0=U(0.45, 0.7), c1=U(0.06, 0.12), cf1=U(0.25, 0.5))


def _curve_part_params(rng, kind, cuts, sym, plate):
    """Curved Car (Porsche-like) / Tank (cast) parts - each a body of the Curved machinery (``part`` names it)."""
    U = rng.uniform
    p = {'family': 'CURVE', 'kind': kind, 'sym': bool(sym)}
    n_c = 0
    if kind == 'CAR' and plate > 0:
        part = rng.choice(('fender', 'fender', 'hood'))
        p.update(_porsche_body(rng))
        if part == 'fender':                             # the side skin over a wheel (its hip), a round arch out of it
            p = {'family': 'CURVE', 'kind': kind, 'sym': False, 'part': part,
                 'fender': {'H': U(0.32, 0.5), 'hip': U(0.08, 0.16), 'roll': U(0.05, 0.14), 'thk': plate,
                            'arch': {'u': U(0.4, 0.6), 'r': U(0.26, 0.36), 'h': U(0.45, 0.7)}}}
            p['cuts'] = [_curve_cut(rng, 'SHELL', False) for _ in range(rng.randint(0, 1))]
            return _rounded(p)
        else:                                            # the hood: the top skin over the front
            p['plate'] = {'thk': plate, 'span': U(0.3, 0.45), 't0': U(0.55, 0.65), 't1': U(0.88, 0.97)}
        n_t = rng.randint(0, 1)
        p['cuts'] = [_curve_cut(rng, 'SHELL', p['sym']) for _ in range(n_t)]
        p['part'] = part
        return _rounded(p)
    if kind == 'CAR':
        part = rng.choice(('lamp', 'mirror', 'bumper'))
        if part == 'lamp':                               # a round headlight pod: a flat lens at its front
            p.update(n=24, round=0.0, bulge=0.0, front='SIDE', back=1.0, W=U(0.55, 0.75), D=U(0.5, 0.7), L=1.0,
                     axis='Y', rows=14, w=[U(0.7, 0.85), U(0.92, 1.0), 1.0, U(0.9, 1.0)],
                     d=[U(0.7, 0.85), U(0.92, 1.0), 1.0, U(0.9, 1.0)], y=[0.0] * 4,
                     c0=U(0.25, 0.4), cf0=0.0, c1=U(0.03, 0.07), cf1=U(0.65, 0.85))
        elif part == 'mirror':                           # a wing mirror: a teardrop, its glass face flat at the back
            n = rng.choice((8, 24))
            p.update(n=n, round=U(0.5, 0.9) if n < 16 else 0.0, bulge=0.1, front='SIDE', back=U(0.7, 1.0), W=1.0,
                     D=U(0.5, 0.7), L=U(0.6, 0.9), axis='Y', rows=14,
                     w=[U(0.85, 0.95), 1.0, U(0.85, 0.95), U(0.4, 0.6)], d=[U(0.85, 0.95), 1.0, U(0.8, 0.9), U(0.4, 0.6)],
                     y=[0.0] * 4, c0=U(0.03, 0.06), cf0=U(0.75, 0.9), c1=U(0.25, 0.4), cf1=0.0)
        else:                                            # a front bumper: wide, rounded, a flat back
            p.update(n=8, round=U(0.6, 0.85), bulge=U(0.1, 0.2), front='SIDE', back=U(0.2, 0.4), W=1.0,
                     D=U(0.3, 0.45), L=U(0.25, 0.4), w=[0.92, 1.0, 1.0, 0.92], d=[0.85, 1.0, 1.0, 0.85],
                     y=[0.0, 0.06, 0.06, 0.0], c0=U(0.1, 0.2), cf0=U(0.4, 0.7), c1=U(0.15, 0.3), cf1=U(0.4, 0.7))
            n_c = rng.randint(0, min(1, cuts))
    elif plate > 0:                                      # Tank plates
        part = rng.choice(('shell', 'guard'))
        if part == 'guard':                              # a curved track guard: a band of an arc, long
            p.update(band=True, R=U(0.8, 1.6), thk=plate, A=[U(30, 50), U(35, 60), U(30, 50)], L=1.0,
                     bend=U(0.05, 0.25), plate=round(plate, 6))
            p['cuts'] = [_curve_cut(rng, 'SHELL', sym) for _ in range(rng.randint(0, 2))]
            p['part'] = part
            return _rounded(p)
        p.update(n=8, round=U(0.6, 0.9), bulge=U(0.1, 0.25), front='SIDE', back=U(0.8, 1.0), W=1.0,
                 D=U(0.85, 1.1), L=U(0.3, 0.45), w=[1.0, U(0.95, 1.0), U(0.85, 0.95), U(0.6, 0.75)],
                 d=[1.0, U(0.95, 1.0), U(0.85, 0.95), U(0.6, 0.75)], y=[U(0.04, 0.1), U(0.06, 0.12), U(0.04, 0.08), 0.0],
                 c0=0.0, cf0=0.9, c1=U(0.4, 0.6), cf1=U(0.25, 0.5))
        p['plate'] = {'thk': plate, 'span': U(0.25, 0.5), 't0': U(0.05, 0.3), 't1': U(0.7, 0.97)}
        p['cuts'] = [_curve_cut(rng, 'SHELL', sym) for _ in range(rng.randint(1, 2))]
        p['part'] = part
        return _rounded(p)
    else:                                                # Tank parts, solid
        part = rng.choice(('mantlet', 'cupola'))
        if part == 'mantlet':                            # a cast mantlet: rounded, a flat back, the front forward
            p.update(n=rng.choice((6, 8)), round=U(0.4, 0.7), bulge=U(0.1, 0.25), front='SIDE', back=U(0.3, 0.5),
                     W=1.0, D=U(0.45, 0.7), L=U(0.4, 0.6), w=[0.9, 1.0, 1.0, 0.9], d=[0.8, 1.0, 1.0, 0.8],
                     y=[0.0, 0.1, 0.1, 0.0], c0=U(0.1, 0.2), cf0=0.6, c1=U(0.1, 0.2), cf1=0.6)
            n_c = rng.randint(0, min(1, cuts))
        else:                                            # a cupola: a low dome, a flat top, vision blocks cut in
            p.update(n=rng.choice((8, 10, 12)), round=U(0.5, 0.8), bulge=0.1, front='SIDE', back=1.0, W=1.0,
                     D=U(0.9, 1.0), L=U(0.35, 0.5), w=[1.0, 1.0, 0.95, 0.8], d=[1.0, 1.0, 0.95, 0.8], y=[0.0] * 4,
                     c0=0.0, cf0=0.9, c1=U(0.3, 0.5), cf1=U(0.35, 0.55))
            n_c = rng.randint(1, max(1, cuts + 1))
    p['cuts'] = [_curve_cut(rng, 'TANK' if kind == 'TANK' else 'CAR', sym) for _ in range(n_c)]
    p['part'] = part
    return _rounded(p)


def _rounded(p):
    """(the numbers kept short in the JSON)"""
    def r(v):
        if isinstance(v, float):
            return round(v, 6)
        if isinstance(v, list):
            return [r(x) for x in v]
        if isinstance(v, dict):
            return {k: r(x) for k, x in v.items()}
        return v
    return {k: r(v) for k, v in p.items()}


def build_curve(p, segs=32, level=0):
    """The solid of Curved parameters ``p``; ``level`` 2 and up: without its cuts."""
    bm = bmesh.new()
    plate = isinstance(p.get('plate'), dict)
    if p['kind'] == 'SHELL' or p.get('band'):
        shell(bm, p, segs)
    elif p.get('fender'):
        fender(bm, p, segs)
    elif plate:
        plate_patch(bm, p, segs)
    else:
        body(bm, p, segs)
    if level < 2:
        for pl in p.get('cuts', ()):
            if plate and p.get('sym'):                   # (a plate is built symmetric: its trims cut in pairs)
                bm = _cut_pair(bm, pl, 0.6)
            else:
                bm = _cut(bm, pl, 0.6 if p['kind'] == 'SHELL' or p.get('band') or p.get('fender') or plate else 0.55)
    if p.get('sym') and not plate:
        symmetrize(bm)
    _split_bent(bm)
    if p.get('axis') == 'Y':                             # (a vehicle: built along Z, lying along Y, its top up)
        bmesh.ops.transform(bm, matrix=LEN_M, verts=list(bm.verts))
    return bm


def build(p, segs=32, size=1.0):
    """(bm, kind) of the shape of parameters ``p``, its longest side ``size``: as they say, else without chamfers,
    else without cuts, else the plain body - the first one that is a clean solid (``LAST['level']``)."""
    ref = p.get('family') == 'REF'
    curved = p.get('family') == 'CURVE' or bool(ref and p.get('curved'))
    for level in range(4):
        if ref:                                          # (a real part: without its pockets, then its cuts / folds)
            from . import ref_parts
            bm = ref_parts.build(p, segs, level)
            if _valid(bm, curved):
                break
            if level < 3:
                bm.free()
            continue
        if curved and level == 1:                        # (no chamfers on a curved shape)
            continue
        bm = build_curve(p, segs, level) if curved else build_poly(p, level)
        if level == 3 and (p.get('sym') or p.get('folds')):   # (the plain body, not mirrored, flat: always clean)
            bm.free()
            q = dict(p, sym=False, folds=[])
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
    if p.get('family') == 'REF':                         # (a real part: its numbers moved, the part kept)
        from . import ref_parts
        return ref_parts.vary(p, a, rng)
    q = json.loads(json.dumps(p))
    sym = bool(q.get('sym'))
    if q.get('family') == 'CURVE' and q.get('fender'):
        fd = q['fender']
        for k in ('H', 'hip', 'roll'):
            fd[k] = _jit(rng, fd[k], 0.25, a, 0.01, 1.0)
        ar = fd['arch']
        ar['u'] = max(0.3, min(0.7, ar['u'] + rng.uniform(-0.06, 0.06) * a))
        ar['r'] = max(0.15, min(0.42, ar['r'] * (1 + rng.uniform(-0.2, 0.2) * a)))
        ar['h'] = max(0.25, min(0.8, ar['h'] * (1 + rng.uniform(-0.2, 0.2) * a)))
        q['cuts'] = [_vary_plane(rng, pl, a, False) for pl in q.get('cuts', ())]
        return _rounded(q)
    if q.get('family') == 'CURVE':
        if q['kind'] == 'SHELL' or q.get('band'):
            q['R'] = _jit(rng, q['R'], 0.3, a, 0.2, 2.0)
            q['thk'] = _jit(rng, q['thk'], 0.3, a, 0.005 if q.get('plate') else 0.02, 0.2)
            q['A'] = [_jit(rng, v, 0.25, a, 25.0, 175.0) for v in q['A']]
            q['L'] = _jit(rng, q['L'], 0.25, a, 0.3, 2.0)
            q['bend'] = max(0.0, min(0.6, q['bend'] + rng.uniform(-0.12, 0.12) * a))
        else:
            q['round'] = max(0.0, min(1.0, q['round'] + rng.uniform(-0.2, 0.2) * a)) if q['n'] < 16 else 0.0
            q['bulge'] = max(0.0, min(0.45, q['bulge'] + rng.uniform(-0.1, 0.1) * a))
            for k in ('W', 'D', 'L'):
                q[k] = _jit(rng, q[k], 0.2, a, 0.2, 3.0)
            for k in ('w', 'd', 'cab'):
                if k in q:
                    q[k] = [max(0.2 if k != 'cab' else 0.08, v + rng.uniform(-0.12, 0.12) * a) for v in q[k]]
            for k in ('sh', 'tw'):
                if k in q:
                    q[k] = max(0.02, min(0.9, q[k] + rng.uniform(-0.05, 0.05) * a))
            q['y'] = [v + rng.uniform(-0.05, 0.05) * a for v in q['y']]
            for k in ('c0', 'c1'):
                if q[k] > 0:
                    q[k] = max(0.02, min(0.7, q[k] + rng.uniform(-0.08, 0.08) * a))
            for k in ('cf0', 'cf1'):
                if q.get(k, 0.0) > 0:
                    q[k] = max(0.05, min(0.95, q[k] + rng.uniform(-0.1, 0.1) * a))
            if 'back' in q:
                q['back'] = max(0.4, min(1.0, q['back'] + rng.uniform(-0.1, 0.1) * a))
            pl = q.get('plate')
            if isinstance(pl, dict):
                pl['thk'] = _jit(rng, pl['thk'], 0.25, a, 0.005, 0.3)
                pl['span'] = max(0.15, min(0.6, pl['span'] + rng.uniform(-0.08, 0.08) * a))
                pl['t0'] = max(0.0, min(0.45, pl['t0'] + rng.uniform(-0.06, 0.06) * a))
                pl['t1'] = max(0.55, min(1.0, pl['t1'] + rng.uniform(-0.06, 0.06) * a))
        q['cuts'] = [_vary_plane(rng, pl, a, sym) for pl in q.get('cuts', ())]
        return _rounded(q)
    if q.get('kind') in DESIGN_KINDS and 'd' in q:
        _vary_design(q, a, rng)
        if q.get('folds'):
            q['folds'] = [[f[0], math.copysign(max(0.15, min(0.92, abs(f[1]) + rng.uniform(-0.08, 0.08) * a)), f[1]),
                           f[2] * (1 + rng.uniform(-0.25, 0.25) * a)] for f in q['folds']]
        return _rounded(q)
    q['outline'] = _vary_outline(rng, q['outline'], q['kind'], a)
    q['depth'] = _jit(rng, q['depth'], 0.2, a, 0.1, 2.0)
    if q['taper'] < 1.0:
        q['taper'] = max(0.3, min(1.0, q['taper'] + rng.uniform(-0.15, 0.15) * a))
    q['slices'] = [_vary_plane(rng, pl, a, sym) for pl in q.get('slices', ())]
    if q.get('kinks'):
        q['kinks'] = [[k[0] + rng.uniform(-0.02, 0.02) * a, k[1] * (1 + rng.uniform(-0.25, 0.25) * a),
                       k[2] * (1 + rng.uniform(-0.25, 0.25) * a)] for k in q['kinks']]
    ch = q.get('chamfer') or [1, 0.0]
    q['chamfer'] = [ch[0], max(0.0, min(1.0, ch[1] * (1 + rng.uniform(-0.3, 0.3) * a)))]
    if q.get('folds'):
        q['folds'] = [[f[0], (0.0 if f[1] == 0 else math.copysign(max(0.15, min(0.92, abs(f[1]) + rng.uniform(-0.08, 0.08)
                                                                                        * a)), f[1])),
                       f[2] * (1 + rng.uniform(-0.25, 0.25) * a)] for f in q['folds']]
    return _rounded(q)


# --- objects ---------------------------------------------------------------------------------------------------------

def new_params(rng, family, st, plate=None):
    """Random parameters of ``family`` with the Shapes page's settings ``st`` (None: the defaults); ``plate``: the
    thickness of a plate (None: the page's Solid / Plate choice)."""
    g = (lambda n, d: getattr(st, n, d)) if st is not None else (lambda n, d: d)
    if family == 'REF':                                  # (a real part: its panels as thick as Thickness)
        from . import ref_parts
        return ref_parts.ref_params(rng, g('ref_vehicle', 'LAMBO'), g('ref_part', 'ANY'), g('plate_thk', 0.05))
    if plate is None:
        plate = g('plate_thk', 0.05) if g('form', 'SOLID') == 'PLATE' else 0.0
    if family == 'CURVE':
        return curve_params(rng, g('curve_kind', 'MIX'), g('curve_cuts', 2), g('curve_sym', True), plate)
    return poly_params(rng, g('kind', 'MIX'), g('slices', 2), g('chamfer', 0.3), g('taper', 0.3), g('poly_sym', False),
                       plate=plate)


def plate_of(p):
    """The plate thickness of parameters ``p`` (0: a solid)."""
    pl = (p or {}).get('plate', 0.0)
    return float(pl['thk'] if isinstance(pl, dict) else pl or 0.0)


def new_mesh(p, segs=32, size=1.0, name=NAME):
    """A mesh of the shape of parameters ``p``: (mesh, kind)."""
    bm, kind = build(p, segs, size)
    me = bpy.data.meshes.new(name)
    try:
        bm.to_mesh(me)
    finally:
        bm.free()
    me.polygons.foreach_set('use_smooth', [p.get('family') == 'CURVE' or bool(p.get('curved'))] * len(me.polygons))
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
    return p if isinstance(p, dict) and p.get('family') in {'POLY', 'CURVE', 'REF'} else None


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

# --- live: the last Summon / Variations follow the page while they stay selected (0.24.95 user: "이거 쉐입 실시간으로
#     바뀌어야지") ----------------------------------------------------------------------------------------------------
# Like Blender's Adjust Last Operation, on the page itself: a setting changed (kind, Size, Count, Thickness, Slices,
# Chamfer, Symmetric, the vehicle / part, Amount, How Many ...) and the shapes the last Summon (or Variations) made are
# made again from the same seed with it - each object kept (place, turn, materials), a missing one added, a spare one
# taken away.  A shape deselected, edited (its mesh not the one made) or deleted is left as it is from then on.

LIVE = {}                     # mode ('summon' / 'vary'), family, seed, scene, view_layer, objs [(name, mesh, verts)],
#                               spots, base / src params, size
_PENDING = [False]
LIVE_PROPS = {
    'POLY': {'size', 'count', 'form', 'plate_thk', 'kind', 'poly_sym', 'slices', 'chamfer', 'taper'},
    'CURVE': {'size', 'count', 'form', 'plate_thk', 'curve_kind', 'curve_sym', 'curve_cuts', 'segments'},
    'REF': {'size', 'count', 'plate_thk', 'segments', 'ref_vehicle', 'ref_part'},
    'VARY': {'var_amount', 'var_count', 'segments'},
}


def _live_mark(context, mode, objs, **kw):
    """Remember what a Summon / Variations just made (for the live settings)."""
    LIVE.clear()
    LIVE.update(mode=mode, scene=context.scene.name, view_layer=context.view_layer.name,
                objs=[(o.name, o.data.name, len(o.data.vertices)) for o in objs],
                spots=[tuple(o.location) for o in objs], **kw)


def _live_hook(prop):
    def update(self, _context):
        if not LIVE or _PENDING[0]:
            return
        key = 'VARY' if LIVE.get('mode') == 'vary' else LIVE.get('family', 'POLY')
        if prop in LIVE_PROPS.get(key, ()):
            _PENDING[0] = True                        # (a slider dragged: one rebuild per moment, not per step)
            bpy.app.timers.register(_live_apply, first_interval=0.03)
    return update


def _live_apply():
    _PENDING[0] = False
    try:
        _live_run()
    except (ReferenceError, RuntimeError, KeyError, AttributeError, ValueError) as ex:
        print('Mecha: live shape update:', ex)
    return None


def _live_obj(entry, vl):
    """The live object of ``entry`` while it is as it was made and selected - else None."""
    ob = bpy.data.objects.get(entry[0])
    if ob is None or ob.type != 'MESH' or ob.data is None or ob.data.name != entry[1] \
            or len(ob.data.vertices) != entry[2]:
        return None
    try:
        return ob if ob.select_get(view_layer=vl) else None
    except (RuntimeError, ReferenceError):
        return None


def _live_put(ob, p, segs, size):
    """``ob`` the shape of ``p`` now (a new mesh; its materials kept)."""
    old = ob.data
    me, _kind = new_mesh(p, segs, size, old.name)
    for m in old.materials:
        me.materials.append(m)
    ob.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    _store(ob, p)


def _live_run():
    sc = bpy.data.scenes.get(LIVE.get('scene', ''))
    if sc is None:
        LIVE.clear()
        return
    vl = sc.view_layers.get(LIVE.get('view_layer', '')) or sc.view_layers[0]
    st = sc.mch_rshape
    vary_mode = LIVE['mode'] == 'vary'
    want = st.var_count if vary_mode else st.count
    entries, spots = list(LIVE['objs']), list(LIVE['spots'])
    obs = [_live_obj(e, vl) for e in entries]
    if not any(obs):
        LIVE.clear()
        return
    first = next(o for o in obs if o is not None)
    colls = list(first.users_collection) or [sc.collection]
    size = LIVE['size'] if vary_mode else st.size
    if vary_mode:
        src = LIVE['src']
        rng = random.Random(LIVE['seed'])
        gap = LIVE['gap']
    else:
        gap = st.size * 1.6
        new_spots = [LIVE['base'] + off for off in layout_spots(want, gap)]
    out_entries, out_spots = [], []
    for i in range(want):
        if vary_mode:
            for _t in range(6):                      # (as Variations makes them: the same draws, in order)
                q = vary(src, st.var_amount, rng)
                bm, _k = build(q, st.segments, size)
                bm.free()
                if LAST['level'] == 0:
                    break
            p = q
        else:
            p = new_params(random.Random(_seed(LIVE['seed'], i)), LIVE['family'], st)
        ob = obs[i] if i < len(obs) else None
        if i < len(entries) and ob is None:          # (left as it is: deselected / edited / deleted)
            out_entries.append(entries[i])
            out_spots.append(spots[i])
            continue
        if ob is None:                               # (one more: a new object where the row goes on)
            me, _kind = new_mesh(p, st.segments, size)
            for m in first.data.materials:
                me.materials.append(m)
            ob = bpy.data.objects.new(NAME, me)
            for c in colls:
                c.objects.link(ob)
            ob.matrix_world = first.matrix_world.copy()
            ob.location = (Vector(spots[-1]) + Vector((gap, 0.0, 0.0)) if vary_mode or not spots
                           else new_spots[i])
            _store(ob, p)
            ob.select_set(True, view_layer=vl)
        else:
            _live_put(ob, p, st.segments, size)
            if not vary_mode and i < len(spots) and (ob.location - Vector(spots[i])).length < 1e-6:
                ob.location = new_spots[i]           # (not moved since: to the row's new place)
        spots.append(tuple(ob.location)) if i >= len(spots) else None
        out_entries.append((ob.name, ob.data.name, len(ob.data.vertices)))
        out_spots.append(tuple(ob.location))
    for e, ob in zip(entries[want:], obs[want:]):     # (fewer now: the spare ones taken away)
        if ob is not None:
            me = ob.data
            bpy.data.objects.remove(ob)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
        else:
            out_entries.append(e)
            out_spots.append(spots[entries.index(e)])
    LIVE['objs'], LIVE['spots'] = out_entries, out_spots
    try:
        from . import ui_bars
        ui_bars.bump()
        for w in bpy.context.window_manager.windows:
            for a in w.screen.areas:
                if a.type == 'VIEW_3D':
                    a.tag_redraw()
    except (AttributeError, ReferenceError, ImportError):
        pass


ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shape_icons')


def shape_icon(name):
    """'file:<png>' of a thumbnail (``tools_dev/make_shape_icons.py``) - '' when there is none (a plain ball)."""
    p = os.path.join(ICON_DIR, name + '.png')
    return 'file:' + p if os.path.isfile(p) else ''


def _tile_to_selected(context, family):
    """0.24.95 (user: "썸네일 - 그거 선택하고 변경 가능하게") a thumbnail clicked: the selected shapes of its family
    become that kind / part (place, turn, size, materials kept) - unless they are the last Summon's, which follow the
    page live anyway.  How many changed."""
    if context.mode != 'OBJECT':
        return 0
    obs = [o for o in context.selected_objects if is_shape(o) and (params_of(o) or {}).get('family') == family]
    live = {e[0] for e in LIVE.get('objs', ())} if LIVE.get('mode') == 'summon' and LIVE.get('family') == family \
        else set()
    if not obs or any(o.name in live for o in obs):
        return 0
    return _reroll(context, obs, _new_seed(), follow_page=True)


def _ref_vehicle_items(_self, _context):
    from . import ref_parts
    return ref_parts.VEHICLES                            # (module constants: Blender keeps no copy of them)


def _ref_part_items(self, _context):
    from . import ref_parts
    return ref_parts.PART_ITEMS.get(getattr(self, 'ref_vehicle', 'LAMBO'), ref_parts.PART_ITEMS['LAMBO'])


def _ref_vehicle_set(self, context):
    try:
        self.ref_part = 'ANY'                            # (another vehicle: any of its parts until one is picked)
    except TypeError:
        pass
    _live_hook('ref_vehicle')(self, context)


class MCH_PG_RandomShape(bpy.types.PropertyGroup):
    size: bpy.props.FloatProperty(name='Size', description='The longest side of a new shape', default=1.0, min=0.01,
                                  soft_max=10.0, subtype='DISTANCE', unit='LENGTH',
        update=_live_hook('size'))
    count: bpy.props.IntProperty(name='Count', description='How many shapes a Summon makes (in rows, to pick from)',
                                 default=1, min=1, max=25,
        update=_live_hook('count'))
    form: bpy.props.EnumProperty(name='Form', items=FORMS, default='SOLID',
                                 description='A solid mass, or a thin plate of that shape (both families)',
        update=_live_hook('form'))
    plate_thk: bpy.props.FloatProperty(name='Thickness', description='How thick a plate is (of its size)',
                                       default=0.05, min=0.005, max=0.3, subtype='FACTOR',
        update=_live_hook('plate_thk'))
    # Polygon
    kind: bpy.props.EnumProperty(name='Polygon Kind', items=KINDS, default='MIX',
        update=_live_hook('kind'))
    poly_sym: bpy.props.BoolProperty(name='Symmetric', description='The left half the mirror of the right',
                                     default=False,
        update=_live_hook('poly_sym'))
    slices: bpy.props.IntProperty(name='Slices', description='Up to this many flat cuts at an angle', default=2,
                                  min=0, max=4,
        update=_live_hook('slices'))
    chamfer: bpy.props.FloatProperty(name='Chamfer', description='Some edges cut flat: how wide', default=0.3,
                                     min=0.0, max=1.0, subtype='FACTOR',
        update=_live_hook('chamfer'))
    taper: bpy.props.FloatProperty(name='Taper', description='The top smaller than the bottom (now and then)',
                                   default=0.3, min=0.0, max=1.0, subtype='FACTOR',
        update=_live_hook('taper'))
    # Curved
    curve_kind: bpy.props.EnumProperty(name='Curved Kind', items=CURVE_KINDS, default='MIX',
        update=_live_hook('curve_kind'))
    curve_sym: bpy.props.BoolProperty(name='Symmetric', description='The left half the mirror of the right',
                                      default=True,
        update=_live_hook('curve_sym'))
    curve_cuts: bpy.props.IntProperty(name='Flat Cuts', description='Up to this many flat faces cut into it',
                                      default=2, min=0, max=4,
        update=_live_hook('curve_cuts'))
    segments: bpy.props.IntProperty(name='Smooth', description='Points round a section (more = rounder, heavier)',
                                    default=32, min=12, max=96,
        update=_live_hook('segments'))
    # Real Parts
    ref_vehicle: bpy.props.EnumProperty(name='Vehicle', items=_ref_vehicle_items,
                                        description='The real vehicle the parts come from', update=_ref_vehicle_set)
    ref_part: bpy.props.EnumProperty(name='Part', items=_ref_part_items, update=_live_hook('ref_part'),
                                     description='Which part of the vehicle (Any: one of them at random)')
    # Variations
    var_amount: bpy.props.FloatProperty(name='Amount', description='How different the variations are', default=0.4,
                                        min=0.02, max=1.0, subtype='FACTOR',
        update=_live_hook('var_amount'))
    var_count: bpy.props.IntProperty(name='How Many', description='How many variations at a time', default=4, min=1,
                                     max=12,
        update=_live_hook('var_count'))


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
        _live_mark(context, 'summon', made, family=self.family, seed=self.seed, base=base.copy())
        names = dict((k[0], k[1]) for k in KINDS + CURVE_KINDS)
        if self.family == 'REF':
            from . import ref_parts
            kinds = sorted({ref_parts.label(params_of(o)['kind'], params_of(o)['part']) for o in made})
            self.report({'INFO'}, f'{len(made)} real part{"s" if len(made) > 1 else ""}: {", ".join(kinds)}'
                                  f' (seed {self.seed})')
            return {'FINISHED'}
        kinds = sorted({names.get(params_of(o)['kind'], '?') for o in made})
        fam = ('curved' if self.family == 'CURVE' else 'polygon') + (' plate' if st.form == 'PLATE' else '')
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
        _live_mark(context, 'vary', made, seed=self.seed, src=p, size=size, gap=gap)
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
        if self.seed == 0:
            self.seed = _new_seed()
        n = _reroll(context, [o for o in context.selected_objects if is_shape(o)], self.seed)
        if not n:
            self.report({'WARNING'}, 'Nothing rerolled (select a random shape; one shared by linked copies is left)')
            return {'CANCELLED'}
        self.report({'INFO'}, f'Rerolled {n} shape{"s" if n > 1 else ""} (seed {self.seed})')
        return {'FINISHED'}


def _reroll(context, obs, seed, follow_page=False):
    """The shapes ``obs`` a new form each from the page's settings, of their own family (a real part: of its vehicle -
    ``follow_page``: of the page's vehicle), as big as they were, where they are.  How many."""
    st = _settings(context)
    n = 0
    for i, ob in enumerate(obs):
        old = ob.data
        if old.users > 1:
            continue                                 # (a linked copy: its twin would change too)
        old_p = params_of(ob) or {}
        fam = old_p.get('family', 'POLY')
        if fam == 'REF':                             # (a real part: another of its vehicle - the page's part
            from . import ref_parts                  #  when the page shows that vehicle)
            veh = st.ref_vehicle if follow_page else old_p.get('kind', 'LAMBO')
            p = ref_parts.ref_params(random.Random(_seed(seed, i)), veh,
                                     st.ref_part if st.ref_vehicle == veh else 'ANY',
                                     old_p.get('d', {}).get('thk', st.plate_thk))
        else:
            p = new_params(random.Random(_seed(seed, i)), fam, st, plate=plate_of(old_p))   # (a plate
            #                                                                                     stays one)
        me, _kind = new_mesh(p, st.segments, _local_size(old) or st.size, old.name)
        for m in old.materials:
            me.materials.append(m)
        ob.data = me
        if old.users == 0:
            bpy.data.meshes.remove(old)
        _store(ob, p)
        n += 1
    return n


class MCH_OT_random_shape_form(bpy.types.Operator):
    """Summon solid masses or thin plates (both families)"""
    bl_idname = 'mch.random_shape_form'
    bl_label = 'Random Shape Form'
    bl_options = {'INTERNAL'}
    form: bpy.props.EnumProperty(items=FORMS, default='SOLID')

    def execute(self, context):
        _settings(context).form = self.form
        return {'FINISHED'}


class MCH_OT_random_shape_kind(bpy.types.Operator):
    """What the next random shapes of this family are (Summon, Reroll) - and the selected shapes of the family become
    it (the last Summon's change at once)"""
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
        _tile_to_selected(context, self.family)
        return {'FINISHED'}


class MCH_OT_random_shape_ref(bpy.types.Operator):
    """Which real vehicle / part the next Summon Part makes - and the selected real parts become it (the last
    Summon's change at once)"""
    bl_idname = 'mch.random_shape_ref'
    bl_label = 'Real Part'
    bl_options = {'INTERNAL'}
    vehicle: bpy.props.StringProperty(default='')
    part: bpy.props.StringProperty(default='')

    def execute(self, context):
        from . import ref_parts
        st = _settings(context)
        if self.vehicle in ref_parts.PART_IDS and self.vehicle != st.ref_vehicle:
            st.ref_vehicle = self.vehicle
        if self.part and (self.part == 'ANY' or self.part in ref_parts.PART_IDS.get(st.ref_vehicle, ())):
            st.ref_part = self.part
        _tile_to_selected(context, 'REF')
        return {'FINISHED'}


# --- the Shapes page (drawn side panel) and the sidebar panel --------------------------------------------------------

def page(context, x, width, k):
    """(items, content height) - the side panel's Shapes page, y measured down from 0 (as ``side_panel.content``)."""
    from . import side_panel as sp
    from . import mech_shader_ui as mu
    b = sp.Builder('SHAPES', x, width, k)
    st = _settings(context)
    obj_mode = context.mode == 'OBJECT'
    b.note(('note', 'Summon: a new base shape at the 3D cursor - a thumbnail picks its kind, the selected shapes '
            'become it; the last Summon follows every setting live' if obj_mode else
            'Object Mode only (leave Edit / Sculpt first)', False, None, None, None, True), x, width)
    mu.row(b, x, width, [mu.number(st, 'size', 'Size'), mu.number(st, 'count', 'Count')])
    mu.row(b, x, width, [mu._cell('tbtn', label, ('op', 'mch.random_shape_form', {'form': ident}), on=st.form == ident)
                         for ident, label, _d in FORMS])          # (0.24.95 user: "판떼기 버전도" - both families)
    if st.form == 'PLATE':
        mu.row(b, x, width, [mu.number(st, 'plate_thk', 'Thickness')])

    def kinds(sx, sw, family, items, cur):         # (0.24.95 thumbnails: a click = that kind, the selected change)
        tag = 'poly' if family == 'POLY' else 'curve'
        mu.grid(b, sx, sw, [(label, shape_icon(f'{tag}_{ident}'), cur == ident,
                             ('op', 'mch.random_shape_kind', {'family': family, 'kind': ident}), None, None)
                            for ident, label, _d in items])

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

    def real(sx, sw):                                    # (0.24.95 user: "실제로 내가 말한 차랑 비행기 탱크를 자료
        from . import ref_parts                          #  서치해서 부품을 그대로 만들어볼래?")
        vcells = [mu._cell('tbtn', label, ('op', 'mch.random_shape_ref', {'vehicle': ident}),
                           on=st.ref_vehicle == ident) for ident, label, _d in ref_parts.VEHICLES]
        for i in range(0, len(vcells), 3):               # (Lambo 911 Jet | Tank Heavy Mech Car Bot)
            mu.row(b, sx, sw, vcells[i:i + 3])
        mu.grid(b, sx, sw, [(label, shape_icon(f'ref_{st.ref_vehicle}_{ident}'), st.ref_part == ident,
                             ('op', 'mch.random_shape_ref', {'part': ident}), None, None)
                            for ident, label, _d in ref_parts.PART_ITEMS[st.ref_vehicle]])
        mu.row(b, sx, sw, [mu.number(st, 'plate_thk', 'Panel Thickness')])
        mu.row(b, sx, sw, [mu.number(st, 'segments', 'Smooth')])
        mu.row(b, sx, sw, [mu._cell('tbtn', 'Summon Part', ('op', 'mch.random_shape_add', {'family': 'REF'}),
                                    active=obj_mode)])
    mu.section(b, 'rs_real', 'Real Parts', x, width, real)

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
    r = layout.row(align=True)
    r.prop(st, 'form', expand=True)
    if st.form == 'PLATE':
        layout.prop(st, 'plate_thk')
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
    box.label(text='Real Parts')
    c = box.column(align=True)
    c.prop(st, 'ref_vehicle', text='')
    c.prop(st, 'ref_part', text='')
    c.prop(st, 'plate_thk', text='Panel Thickness')
    box.operator('mch.random_shape_add', text='Summon Part', icon='AUTO').family = 'REF'
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
           MCH_OT_random_shape_form, MCH_OT_random_shape_kind, MCH_OT_random_shape_ref, MCH_PT_random_shapes)


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
