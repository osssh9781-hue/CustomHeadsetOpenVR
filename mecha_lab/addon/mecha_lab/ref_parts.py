"""0.24.95 Real Parts - exterior parts after real vehicles (user: "실제로 내가 말한 차랑 비행기 탱크를 자료 서치해서
부품을 그대로 만들어볼래?").  The Shapes page's **Real Parts** section: a vehicle, a part, Summon.

* **Lambo** (after the Lamborghini Aventador / Countach - flat faces, one angle repeated; 4.78 x 2.03 x 1.14 m,
  wheelbase 2.70): a side air intake (a wedge, its mouth facing forward-out, a deep pocket), a door skin (its long
  diagonal crease, the window sill bent in), a front fender (a hexagonal wheel arch, its top bent over into the
  bonnet), a headlight (a long angular lozenge swept back, its lens recessed), a rear wing (a blade on two struts
  between end plates)
* **911** (after the Porsche 911 - curved skins; 4.52 x 1.85 x 1.30 m, wheelbase 2.45): a front fender (rising above
  the bonnet, a round wheel arch), a rear fender (the wide hips), a ducktail engine lid (its rear edge kicked up), a
  round headlight (bezel, domed lens), a wing mirror (a teardrop, the glass recessed)
* **F-22** (after the F-22 Raptor - 42-degree edges; wing: leading edge 42, trailing edge -17 degrees, taper 0.17,
  aspect 2.36; fins canted 28 degrees): a caret intake (the trunk, its mouth swept both ways, a deep duct), the wing,
  a stabilator, a canted tail fin (knife edges), a 2D nozzle, the bubble canopy, the chined nose
* **Tank** (after the M1 Abrams - flat armour - and the T-72 - cast): the angular turret (cheeks angled back, the
  mantlet recess, the sides leaning in), a side skirt (its front edge slanted for the idler, the top flange bent in),
  a gun mantlet, the hull front (upper glacis long and shallow, the lower glacis, sponsons over the tracks), a cast
  turret (a low dome, its front thicker), a road wheel (tyre, dished disc, hub)

A part is its numbers (``d``) - the reference proportions, each moved a little on a summon (the slight randomness:
two summons of one part differ a little), more with Variations.  Every part is checked like every random shape (one
closed piece, normals out, flat faces flat); when it is not clean it is made again without its pockets, then without
its cuts / folds.  Panels (doors, fenders, skirts, wings) are as thick as the page's Thickness (of the panel's size).
"""
from __future__ import annotations

import json
import math

import bmesh
from mathutils import Matrix, Vector

from . import random_shapes as rs

VEHICLES = (('LAMBO', 'Lambo', 'Wedge supercar parts after the Lamborghini Aventador / Countach: flat faces, one '
                               'angle repeated'),
            ('P911', '911', 'Round sports-car parts after the Porsche 911: curved skins, round lamps'),
            ('F22', 'F-22', 'Stealth-fighter parts after the F-22 Raptor: 42-degree edges, knife edges, a bubble '
                            'canopy'),
            ('MBT', 'Tank', 'Tank parts after the M1 Abrams (flat armour) and the T-72 (cast, round)'))
PARTS = {
    'LAMBO': (('INTAKE', 'Side Intake', 'The air intake behind the door: a wedge, its mouth facing forward-out'),
              ('DOOR', 'Door', 'The door skin: its long diagonal crease, the window sill bent in'),
              ('FENDER', 'Front Fender', 'A hexagonal wheel arch, the top bent over into the bonnet'),
              ('LAMP', 'Headlight', 'A long angular lozenge swept back, its lens recessed'),
              ('WING', 'Rear Wing', 'A blade on two struts between end plates')),
    'P911': (('FENDER_F', 'Front Fender', 'Rising above the bonnet, a round wheel arch'),
             ('FENDER_R', 'Rear Fender', 'The wide hips over the rear wheel'),
             ('DUCKTAIL', 'Ducktail', 'The engine lid, its rear edge kicked up'),
             ('LAMP', 'Headlight', 'A round headlight: bezel, domed lens'),
             ('MIRROR', 'Mirror', 'A wing mirror: a teardrop, the glass recessed')),
    'F22': (('INTAKE', 'Intake', 'A caret intake: the trunk, its mouth swept both ways, a deep duct'),
            ('WING', 'Wing', 'Leading edge 42, trailing edge -17 degrees, knife edges'),
            ('STAB', 'Stabilator', 'The all-moving tail plane, its edges at the wing\'s angles'),
            ('FIN', 'Tail Fin', 'A vertical tail canted 28 degrees out'),
            ('NOZZLE', 'Nozzle', 'A 2D nozzle: its flaps closing in, the exhaust a deep box'),
            ('CANOPY', 'Canopy', 'The bubble canopy: a pointed front, long behind'),
            ('NOSE', 'Nose', 'The chined nose: a sharp chine all round, a rounded top')),
    'MBT': (('TURRET', 'Turret', 'An angular turret: cheeks angled back, the mantlet recess, the sides leaning in'),
            ('SKIRT', 'Side Skirt', 'Its front edge slanted for the idler, the top flange bent in'),
            ('MANTLET', 'Mantlet', 'A gun mantlet: a slab, its top and bottom sloped'),
            ('GLACIS', 'Hull Front', 'Upper glacis long and shallow, the lower glacis, sponsons over the tracks'),
            ('CAST', 'Cast Turret', 'A low cast dome, its front thicker'),
            ('WHEEL', 'Road Wheel', 'Tyre, dished disc, hub')),
}
PART_IDS = {v: tuple(p[0] for p in PARTS[v]) for v in PARTS}
PART_ITEMS = {v: (('ANY', 'Any', 'Any part of this vehicle'),) + PARTS[v] for v in PARTS}
CURVED = {('P911', 'FENDER_F'), ('P911', 'FENDER_R'), ('P911', 'DUCKTAIL'), ('P911', 'LAMP'), ('P911', 'MIRROR'),
          ('F22', 'CANOPY'), ('F22', 'NOSE'), ('MBT', 'CAST'), ('MBT', 'WHEEL')}
SIDE_PLATE_M = Matrix(((0, 0, -1, 0), (-1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))   # a side panel (outline x rearward,
#                                                         y up, its outer face -Z) -> outer face +X, forward +Y, up +Z


def label(vehicle, part):
    v = dict((k[0], k[1]) for k in VEHICLES).get(vehicle, vehicle)
    p = dict((k[0], k[1]) for k in PARTS.get(vehicle, ())).get(part, part)
    return f'{v} {p}'


# --- the reference numbers of each part (meters of the real part, scaled to the Size when made) ------------------

def _defaults(vehicle, part):
    """The part's numbers as the reference has them: floats or lists of floats (each moved a little on a summon,
    more by Variations) - the builders keep them in their ranges."""
    if vehicle == 'LAMBO':
        if part == 'INTAKE':
            return dict(L=1.05, H=0.5, W=0.32, yaw=38.0, pitch=8.0, mouth=0.42, inset=0.03, deep=0.24)
        if part == 'DOOR':
            return dict(L=1.25, H=0.58, lean=0.22, crease=[0.32, 0.62], crease_a=20.0, sill=0.86, sill_a=24.0)
        if part == 'FENDER':
            return dict(L=1.3, H=0.6, ac=0.0, aw=0.42, ah=0.42, nose=0.24, top_a=55.0, top_d=0.13)
        if part == 'LAMP':
            return dict(Wd=0.68, Ht=0.17, depth=0.34, sweep=34.0, tilt=28.0, lens=0.014, cut=0.32)
        if part == 'WING':
            return dict(B=0.82, C=0.33, z0=0.30, bt=0.04, et=0.02, ep=[0.16, 0.42], xs=0.30, sw=0.035, k=1.3)
    if vehicle == 'P911':
        if part == 'FENDER_F':
            return dict(L=1.15, zb=0.2, W=[0.86, 0.92, 0.92, 0.89, 0.80], ZT=[0.70, 0.71, 0.70, 0.68, 0.60],
                        tw=0.30, roll=[0.04, 0.05, 0.07, 0.1, 0.12], bulge=0.02, ac=0.02, ar=0.42, ah=0.4)
        if part == 'FENDER_R':
            return dict(L=1.45, zb=0.2, W=[0.80, 0.92, 0.955, 0.93, 0.86], ZT=[0.62, 0.74, 0.78, 0.77, 0.74],
                        tw=0.36, roll=[0.1, 0.08, 0.07, 0.06, 0.05], bulge=0.035, ac=-0.08, ar=0.43, ah=0.41)
        if part == 'DUCKTAIL':
            return dict(Ld=0.78, wf=0.55, wr=0.62, zf=0.95, zr=0.78, crown=0.05, lip=0.15, u0=0.72)
        if part == 'LAMP':
            return dict(R=0.1, depth=0.2, bezel=0.012, dome=0.035, back=0.65)
        if part == 'MIRROR':
            return dict(Lm=0.17, Wm=0.25, Hm=0.13, out=0.03, drop=0.015, glass=0.009, deep=0.012)
    if vehicle == 'F22':
        if part == 'INTAKE':
            return dict(Lt=1.25, Wb=0.56, Wt=0.68, Hi=0.72, Ho=0.62, sweep=42.0, rake=27.0, inset=0.05, deep=0.55)
        if part == 'WING':
            return dict(S=0.69, le=42.0, te=-17.0, kn=0.06)
        if part == 'STAB':
            return dict(S=0.62, le=42.0, te=-12.0, kn=0.07)
        if part == 'FIN':
            return dict(S=0.74, le=24.0, te=-20.0, kn=0.06, cant=28.0)
        if part == 'NOZZLE':
            return dict(Ln=1.0, Wn=1.1, Hf=1.0, Hr=0.52, mid=0.55, drop=0.03, inset=0.07, deep=0.55)
        if part == 'CANOPY':
            return dict(Lc=1.0, w=[0.10, 0.15, 0.17, 0.16, 0.10], h=[0.07, 0.15, 0.21, 0.19, 0.11], e=2.4)
        if part == 'NOSE':
            return dict(Ln=1.0, W=0.21, Ht=0.15, Hb=0.10, p=1.7, q=1.25, droop=0.03)
    if vehicle == 'MBT':
        if part == 'TURRET':
            return dict(Lt=1.0, Wt=0.62, Ht=0.2, cheek=0.6, mw=0.075, mr=0.1, rear=0.24, lean=0.9, roof=0.1)
        if part == 'SKIRT':
            return dict(L=1.0, H=0.12, front=0.09, rear=0.4, flange=0.76, fl_a=75.0)
        if part == 'MANTLET':
            return dict(Wm=0.62, Hm=0.4, Dm=0.32, top=0.2, bot=0.14, face=0.13)
        if part == 'GLACIS':
            return dict(Lg=1.05, Wu=1.15, Wl=0.7, Hs=0.18, Hg=0.36, run=0.62, low=50.0, low_h=0.4)
        if part == 'CAST':
            return dict(Wc=1.0, Dc=1.12, Hc=0.38, w=[1.0, 0.97, 0.85, 0.6], fwd=0.07, top=0.35, cut=0.06)
        if part == 'WHEEL':
            return dict(R=1.0, Wt=0.22, rim=0.86, dish=0.78, hub=0.3, cap=0.13, depth=0.06)
    raise KeyError((vehicle, part))


def _jitter(d, rng, rel):
    """Every number moved by up to ``rel`` of itself; a list (a profile along the part) moved as one, each of its
    points only a quarter as much on top (a fender's line stays a smooth line, not a wave)."""
    def j(v):
        if isinstance(v, list):
            f = 1.0 + rng.uniform(-rel, rel)
            return [round(x * f * (1.0 + rng.uniform(-rel, rel) * 0.25), 6) for x in v]
        if isinstance(v, float):
            return round(v * (1.0 + rng.uniform(-rel, rel)), 6)
        return v
    return {k: j(v) for k, v in d.items()}


def ref_params(rng, vehicle='LAMBO', part='ANY', thk=0.05):
    """The parameters of a real part (``part`` ANY: one of the vehicle's at random): its reference numbers, each a
    little off (a summon's slight randomness); ``thk``: a panel's thickness (of its size)."""
    if vehicle not in PART_IDS:
        vehicle = rng.choice(list(PART_IDS))
    if part not in PART_IDS[vehicle]:
        part = rng.choice(PART_IDS[vehicle])
    d = _jitter(_defaults(vehicle, part), rng, 0.06)
    d['thk'] = round(float(thk), 6)
    return {'family': 'REF', 'kind': vehicle, 'part': part, 'curved': (vehicle, part) in CURVED, 'sym': False,
            'd': d}


def vary(p, a, rng):
    """Parameters close to ``p`` (``a`` 0 - 1): each number moved up to 18 % x ``a`` (angles up to 5 degrees x
    ``a``); the vehicle and the part kept."""
    q = json.loads(json.dumps(p))
    d = q['d']
    for k, v in list(d.items()):
        if k == 'thk':
            continue
        if isinstance(v, list):                          # (a profile: moved as one, its points a little on top)
            f = 1.0 + rng.uniform(-0.18, 0.18) * a
            d[k] = [round(x * f * (1.0 + rng.uniform(-0.04, 0.04) * a), 6) for x in v]
        elif isinstance(v, float):
            if k in {'yaw', 'pitch', 'crease_a', 'sill_a', 'top_a', 'sweep', 'tilt', 'le', 'te', 'cant', 'rake',
                     'low', 'fl_a'}:
                d[k] = round(v + rng.uniform(-5.0, 5.0) * a, 6)
            else:
                d[k] = round(v * (1.0 + rng.uniform(-0.18, 0.18) * a), 6)
    return q


# --- helpers ---------------------------------------------------------------------------------------------------------

def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _side_solid(bm, pts, width, x0=0.0):
    """An outline seen from the side (s forward, z up) pushed across X from ``x0`` by ``width``."""
    rs._prism(bm, [tuple(q) for q in pts], width, 1.0, center=False)
    bmesh.ops.transform(bm, matrix=rs.SIDE_M, verts=list(bm.verts))     # (x -> Y, y -> Z, depth -> X)
    bmesh.ops.translate(bm, vec=(x0 + width / 2, 0.0, 0.0), verts=list(bm.verts))


def _front_solid(bm, pts, depth, y0=0.0):
    """An outline seen from the front (x right, z up) pushed back along -Y from ``y0`` by ``depth``."""
    rs._prism(bm, [tuple(q) for q in pts], depth, 1.0, center=False)
    bmesh.ops.transform(bm, matrix=rs.PLATE_M, verts=list(bm.verts))    # (x, -z, y): depth along Y
    bmesh.ops.translate(bm, vec=(0.0, y0 - depth / 2, 0.0), verts=list(bm.verts))


def _plan_solid(bm, pts, h, taper=1.0):
    """An outline seen from above (x right, y forward) pushed up from Z = 0 by ``h``, its top ``taper`` times as big
    (round the origin: each side stays flat)."""
    rs._prism(bm, [tuple(q) for q in pts], h, taper, center=False)
    bmesh.ops.translate(bm, vec=(0.0, 0.0, h / 2), verts=list(bm.verts))


def _mirror_half(right):
    """A symmetric outline from its right half (x >= 0, from the top of the centre line round to its bottom)."""
    return rs._clean([tuple(q) for q in right] + [(-x, y) for x, y in reversed(right)])


def _fold_line(bm, a, b, theta, keep_up=True):
    """Bend a panel lying in XY (its outer face -Z) along the line through ``a`` - ``b``: the part on the low side
    (``keep_up`` - else the high side) turns ``theta`` (radians, + toward +Z: in, behind the outer face).  The points
    on the line go to the mitre: each side stays flat."""
    A, B = Vector((a[0], a[1], 0.0)), Vector((b[0], b[1], 0.0))
    d = (B - A)
    if d.length < 1e-9 or abs(theta) < 1e-4:
        return
    d.normalize()
    u = Vector((d.y, -d.x, 0.0))
    if (u.y < 0) != keep_up:                             # (u: toward the side that bends)
        u = -u
    pos = u.dot(A)
    if not any(v.co.dot(u) > pos + 1e-4 for v in bm.verts):
        return
    P = u * pos
    bmesh.ops.bisect_plane(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces), dist=1e-6, plane_co=P,
                           plane_no=u)
    R = Matrix.Rotation(theta, 3, u.cross(Vector((0.0, 0.0, 1.0))))
    t2 = math.tan(theta / 2)
    lay = bm.verts.layers.int.get(rs.CREASE) or bm.verts.layers.int.new(rs.CREASE)
    for v in bm.verts:
        s = v.co.dot(u) - pos
        if s > 1e-6:
            v.co = P + R @ (v.co - P)
        elif s > -1e-6:
            v.co = v.co - u * (v.co.z * t2)
            v[lay] = 1


def _side_panel(bm, pts, t, folds=(), level=0):
    """A side panel: the outline (s forward, z up) ``t`` thick, bent along its fold lines [(a, b, theta, keep_up)],
    standing on the vehicle's right side (outer face +X)."""
    rs._prism(bm, [(-s, z) for s, z in pts], t, 1.0, center=False)
    if level < 2 and folds:
        for a, b, theta, up in folds:
            _fold_line(bm, (-a[0], a[1]), (-b[0], b[1]), theta, up)
        rs._split_twisted(bm)
    bmesh.ops.transform(bm, matrix=SIDE_PLATE_M, verts=list(bm.verts))


def _best_face(bm, direction, min_dot=0.5):
    bm.normal_update()
    n = Vector(direction).normalized()
    best, score = None, -1.0
    for f in bm.faces:
        dt = f.normal.dot(n)
        if dt < min_dot:
            continue
        sc = dt * f.calc_area() ** 0.5
        if sc > score:
            best, score = f, sc
    return best


def _pocket(bm, direction, inset, push):
    """The face looking most along ``direction`` (and big) inset ``inset`` and moved by ``push`` (a vector into the
    part - along the duct, so its walls stay inside the part): a duct, a recess (its floor flat, parallel to the
    face; each wall a flat parallelogram)."""
    f = _best_face(bm, direction)
    if f is None or inset <= 0:
        return
    bmesh.ops.inset_region(bm, faces=[f], thickness=inset, depth=0.0, use_even_offset=True)
    bmesh.ops.translate(bm, vec=Vector(push), verts=list(f.verts))


def _cut_at(bm, n, point, keep=0.4):
    """A flat cut through ``point``: what lies beyond it along ``n`` taken away."""
    v = Vector(n).normalized()
    return rs._cut(bm, [v.x, v.y, v.z, 0.0], keep, v.dot(Vector(point)))


def _lathe(bm, prof, segs, axis='Y'):
    """A body of revolution: ``prof`` [(radius, along)] round the ``axis``; a radius of 0 closes in a point."""
    n = max(12, int(segs))
    rings = []
    for r, a in prof:
        if r < 1e-6:
            co = [(0.0, a, 0.0)]
        else:
            co = [(r * math.cos(2 * math.pi * i / n), a, r * math.sin(2 * math.pi * i / n)) for i in range(n)]
        if axis == 'X':
            co = [(y, -x, z) for x, y, z in co]
        rings.append([bm.verts.new(c) for c in co])
    rs._loft(bm, rings)


def _cr(points, t):
    """A point on the Catmull-Rom curve through ``points`` (2D) at t (0 - 1)."""
    return (rs._spline([p[0] for p in points], t), rs._spline([p[1] for p in points], t))


def _resample(curve, n):
    """``n`` points spread evenly (by length) along the polyline ``curve``."""
    acc = [0.0]
    for p, q in zip(curve, curve[1:]):
        acc.append(acc[-1] + math.hypot(q[0] - p[0], q[1] - p[1]))
    tot = acc[-1] or 1.0
    out, j = [], 0
    for i in range(n):
        s = tot * i / (n - 1)
        while j < len(acc) - 2 and acc[j + 1] < s:
            j += 1
        seg = (acc[j + 1] - acc[j]) or 1.0
        u = (s - acc[j]) / seg
        p, q = curve[j], curve[j + 1]
        out.append((p[0] + (q[0] - p[0]) * u, p[1] + (q[1] - p[1]) * u))
    return out


def _skin(bm, grid, thk, outward):
    """A curved panel through the rows of points ``grid``, its outer side toward ``outward``, ``thk`` thick inward."""
    vs = [[bm.verts.new(q) for q in row] for row in grid]
    for a, b in zip(vs, vs[1:]):
        for j in range(len(a) - 1):
            bm.faces.new((a[j], a[j + 1], b[j + 1], b[j]))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    o = Vector(outward)
    if sum(f.normal.dot(o) * f.calc_area() for f in bm.faces) < 0:
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    bmesh.ops.solidify(bm, geom=list(bm.faces), thickness=thk)


def _panel_t(d, a, b):
    """A panel's thickness: the page's Thickness of its size (the root of its area - a long narrow skirt stays
    thin)."""
    return max(1e-4, d.get('thk', 0.05) * math.sqrt(max(1e-6, a * b)))


# --- Lambo -----------------------------------------------------------------------------------------------------------

def _lambo(bm, part, d, level):
    if part == 'INTAKE':                                 # a wedge seen from the side, its mouth cut facing forward-out
        L, H, W = d['L'], d['H'], d['W']
        pts = [(0.45 * L, 0.0), (-0.55 * L, 0.08 * H), (-0.6 * L, 0.85 * H), (-0.1 * L, H), (0.35 * L, 0.62 * H)]
        _side_solid(bm, pts, W)
        if level < 2:
            y, p = math.radians(_clamp(d['yaw'], 15, 70)), math.radians(_clamp(d['pitch'], -20, 30))
            n = Vector((math.sin(y), math.cos(y), math.sin(p))).normalized()
            bm = rs._cut(bm, [n.x, n.y, n.z, _clamp(d['mouth'], 0.2, 0.6)], 0.35)
            if level < 1:
                _pocket(bm, n, d['inset'] * L, (0.0, -d['deep'] * L, 0.0))
        return bm
    if part == 'DOOR':                                   # the door skin: the diagonal crease, the sill bent in
        L, H = d['L'], d['H']
        lean = _clamp(d['lean'], 0.05, 0.4) * L
        pts = [(0.5 * L, 0.0), (-0.5 * L, 0.03 * H), (-0.5 * L + lean, H), (0.42 * L, 0.94 * H), (0.53 * L, 0.5 * H)]
        c0, c1 = (_clamp(c, 0.12, 0.75) for c in d['crease'])
        s0 = _clamp(d['sill'], 0.7, 0.92)
        folds = [((0.7 * L, c0 * H), (-0.7 * L, c1 * H), math.radians(_clamp(d['crease_a'], 5, 40)), True),
                 ((0.7 * L, s0 * H), (-0.7 * L, (s0 + 0.06) * H), math.radians(_clamp(d['sill_a'], 5, 45)), False)]
        if c1 >= s0 - 0.04:                              # (the two lines never cross in the panel)
            folds = folds[:1]
        _side_panel(bm, pts, _panel_t(d, L, H), folds, level)
        return bm
    if part == 'FENDER':                                 # the front quarter: a hexagonal arch, its top bent over
        L, H = d['L'], d['H']
        aw = min(_clamp(d['aw'], 0.25, 0.46), 0.36 * L)
        ac = _clamp(d['ac'], -0.08, 0.08) * L
        ah = min(_clamp(d['ah'], 0.25, 0.48), 0.75 * H)
        nose = _clamp(d['nose'], 0.12, 0.35)
        pts = [(-0.5 * L, 0.0), (ac - aw, 0.0), (ac - 0.8 * aw, 0.72 * ah), (ac - 0.42 * aw, ah), (ac + 0.42 * aw, ah),
               (ac + 0.8 * aw, 0.72 * ah), (ac + aw, 0.0), (0.48 * L, 0.12 * H), (0.51 * L, nose * H + 0.12 * H),
               (0.3 * L, 0.86 * H), (-0.5 * L, H)]
        td = _clamp(d['top_d'], 0.06, 0.2) * H
        a, b = (0.3 * L, 0.86 * H - td), (-0.5 * L, H - td)        # (parallel to the top edge, ``td`` below it)

        def line_z(s):
            return a[1] + (s - a[0]) * (b[1] - a[1]) / (b[0] - a[0])
        folds = [(a, b, math.radians(_clamp(d['top_a'], 25, 80)), False)]
        if min(line_z(ac - 0.42 * aw), line_z(ac + 0.42 * aw)) < ah + 0.03 * H:   # (the bend never through the arch)
            folds = []
        _side_panel(bm, pts, _panel_t(d, L, H), folds, level)
        return bm
    if part == 'LAMP':                                   # a long angular lozenge, swept back, its lens recessed
        Wd, Ht, dep = d['Wd'], d['Ht'], d['depth']
        pts = [(0.0, 0.0), (0.74 * Wd, 0.05 * Ht), (Wd, 0.62 * Ht), (0.9 * Wd, Ht), (0.15 * Wd, 0.78 * Ht),
               (-0.06 * Wd, 0.4 * Ht)]
        _front_solid(bm, pts, dep)
        if level < 2:
            sw = math.radians(_clamp(d['sweep'], 15, 55))
            bm = _cut_at(bm, (math.sin(sw), math.cos(sw), 0.0), (0.12 * Wd, 0.0, 0.0), 0.35)
            tl = math.radians(_clamp(d['tilt'], 0, 50))
            bm = _cut_at(bm, (0.0, math.cos(tl), math.sin(tl)), (0.0, -0.02 * dep, 0.55 * Ht), 0.35)
            if level < 1:
                f = _best_face(bm, (0.35, 1.0, 0.25))
                if f is not None:
                    bmesh.ops.inset_region(bm, faces=[f], thickness=0.12 * Ht, depth=-abs(d['lens']) * Wd,
                                           use_even_offset=True)
        return bm
    # WING: a blade on two struts between end plates (front view pushed along the chord, the struts / plates cut)
    B, C, z0, bt, et = d['B'], d['C'], d['z0'], d['bt'], d['et']
    ep0, ep1 = d['ep']
    xs, sw = _clamp(d['xs'], 0.15, 0.6) * B / 0.82, d['sw']
    zt = z0 + bt
    ep0, ep1 = min(ep0, z0 - 0.04), max(ep1, zt + 0.04)
    right = [(0.0, zt), (B - et, zt), (B - et, ep1), (B, ep1), (B, ep0), (B - et, ep0), (B - et, z0), (xs + sw, z0),
             (xs + sw, 0.0), (xs, 0.0), (xs, z0), (0.0, z0)]
    _front_solid(bm, _mirror_half(right), C, C / 2)
    if level < 2:
        k = _clamp(d['k'], 0.6, 2.5)
        bm = _cut_at(bm, (0.0, 1.0, -k), (0.0, C / 2, z0 - 0.002), 0.3)       # (struts / plates: their fronts
        bm = _cut_at(bm, (0.0, -1.0, -k * 0.7), (0.0, -C / 2, z0 - 0.002), 0.3)   # and backs slanted)
        bm = _cut_at(bm, (0.0, 0.45, 1.0), (0.0, C / 2, zt - 0.45 * bt), 0.3)      # (the blade's nose)
        bm = _cut_at(bm, (0.0, -0.8, 1.0), (0.0, -C / 2, ep1 - 0.06), 0.3)         # (the plates' tops)
    return bm


# --- 911 -------------------------------------------------------------------------------------------------------------

def _fender_skin(bm, d, segs):
    """A 911 fender: sections from the side's bottom over the shoulder to the bonnet / lid edge, the widths and
    heights along its length (``W`` / ``ZT``, rear to front), the side bulging (``bulge``), the top falling in to its
    inner edge (``roll``), a round wheel arch out of its bottom (middle ``ac``, half length ``ar``, height ``ah``)."""
    L, zb, tw = d['L'], d['zb'], _clamp(d['tw'], 0.15, 0.5)
    ar = _clamp(d['ar'], 0.25, 0.48) * min(1.0, L / 0.95)
    ac = _clamp(d['ac'], -0.15, 0.15) * L
    nu, nv = max(36, int(segs * 1.2)), max(14, segs // 2)
    grid = []
    for i in range(nu):
        u = i / (nu - 1)
        s = -L / 2 + u * L
        W, zt, roll = rs._spline(d['W'], u), rs._spline(d['ZT'], u), max(0.0, rs._spline(d['roll'], u))
        ah = _clamp(d['ah'], 0.2, 0.9) * (zt - zb) / 0.5
        ah = min(ah, 0.8 * (zt - zb))
        ctrl = [(W - 0.03, zb), (W + d['bulge'], zb + 0.42 * (zt - zb)), (W - 0.015, zb + 0.84 * (zt - zb)),
                (W - 0.09, zt), (W - tw, zt - roll)]
        dense = [_cr(ctrl, k / 160) for k in range(161)]
        du = (s - ac) / ar
        zlo = zb + ah * math.sqrt(1.0 - du * du) if abs(du) < 1.0 else zb
        k0 = 0
        while k0 < len(dense) - 3 and dense[k0][1] < zlo and dense[k0 + 1][1] >= dense[k0][1]:
            k0 += 1
        sec = _resample(dense[k0:], nv)
        grid.append([(x, s, z) for x, z in sec])
    _skin(bm, grid, _panel_t(d, L, 0.5), (1.0, 0.0, 0.3))


def _p911(bm, part, d, level, segs):
    if part in {'FENDER_F', 'FENDER_R'}:
        _fender_skin(bm, d, segs)
        return bm
    if part == 'DUCKTAIL':                               # the engine lid: a crowned skin, its rear edge kicked up
        Ld, u0 = d['Ld'], _clamp(d['u0'], 0.5, 0.85)
        nu, nv = max(24, segs), max(16, segs // 2 + 1)
        grid = []
        for i in range(nu):
            u = i / (nu - 1)
            s = -u * Ld
            w = d['wf'] + (d['wr'] - d['wf']) * u
            k = max(0.0, (u - u0) / (1.0 - u0))
            zc = d['zf'] - (d['zf'] - d['zr']) * u ** 1.3 + d['lip'] * k * k
            row = []
            for j in range(nv):
                x = -w + 2 * w * j / (nv - 1)
                row.append((x, s, zc + d['crown'] * (1.0 - (x / w) ** 2) * (1.0 - 0.5 * k)))
            grid.append(row)
        _skin(bm, grid, _panel_t(d, Ld, 2 * d['wf']), (0.0, 0.0, 1.0))
        return bm
    if part == 'LAMP':                                   # a round headlight: housing, bezel ring, domed lens
        R, dep, bz, dome = d['R'], d['depth'], d['bezel'], d['dome']
        back = _clamp(d['back'], 0.4, 0.9)
        prof = [(0.0, -dep), (back * R, -dep), (0.86 * R, -0.55 * dep), (0.9 * R, -0.12 * dep), (R, -bz),
                (R * 1.0, 0.0), (0.95 * R, bz * 0.6), (0.9 * R, bz), (0.72 * R, bz + 0.45 * dome),
                (0.42 * R, bz + 0.85 * dome), (0.0, bz + dome)]
        _lathe(bm, prof, segs)
        return bm
    # MIRROR: a teardrop housing (the glass face at the back), its nose rounded, the glass recessed
    Lm, Wm, Hm = d['Lm'], d['Wm'], d['Hm']
    st = [(0.0, 1.0, 1.0, 0.0, 0.0), (0.08, 1.02, 1.03, 0.02, -0.01), (0.35, 0.97, 0.96, 0.08, -0.04),
          (0.62, 0.78, 0.8, 0.18, -0.12), (0.84, 0.48, 0.52, 0.28, -0.2), (0.96, 0.2, 0.24, 0.33, -0.24)]
    n = max(16, segs)
    e = 2.6
    rings = []
    for t, sx, sz, cx, cz in st:
        ring = []
        for i in range(n):
            a = 2 * math.pi * i / n
            c, s_ = math.cos(a), math.sin(a)
            ring.append(bm.verts.new((cx * d['out'] / 0.03 * Wm * 0.25 + sx * Wm / 2 * math.copysign(abs(c) ** (2 / e), c),
                                      t * Lm,
                                      cz * d['drop'] / 0.015 * Hm * 0.25 + sz * Hm / 2 * math.copysign(abs(s_) ** (2 / e), s_))))
        rings.append(ring)
    tip = st[-1]
    rings.append([bm.verts.new((tip[3] * d['out'] / 0.03 * Wm * 0.25, Lm, tip[4] * d['drop'] / 0.015 * Hm * 0.25))])
    rs._loft(bm, rings)
    if level < 1:
        f = _best_face(bm, (0.0, -1.0, 0.0), 0.95)
        if f is not None:
            bmesh.ops.inset_region(bm, faces=[f], thickness=d['glass'], depth=-abs(d['deep']), use_even_offset=True)
    return bm


# --- F-22 ------------------------------------------------------------------------------------------------------------

def _f22(bm, part, d, level, segs):
    if part == 'INTAKE':                                 # the trunk, its caret mouth swept in plan and side, a duct
        Lt, Wb, Wt, Hi, Ho = d['Lt'], d['Wb'], d['Wt'], d['Hi'], d['Ho']
        _front_solid(bm, [(0.0, 0.0), (Wb, 0.0), (Wt, Ho), (0.0, Hi)], Lt, 0.25 * Lt)
        if level < 2:
            sw, rk = math.radians(_clamp(d['sweep'], 25, 55)), math.radians(_clamp(d['rake'], 5, 45))
            n = Vector((math.tan(sw), 1.0, -math.tan(rk))).normalized()
            bm = _cut_at(bm, n, (0.0, 0.25 * Lt, Hi), 0.3)
            if level < 1:
                _pocket(bm, n, d['inset'] * Hi, (0.0, -d['deep'] * Lt, 0.0))
        return bm
    if part in {'WING', 'STAB', 'FIN'}:                  # a plate of knife edges (the Jet wing's machinery)
        le = _clamp(d['le'], 10, 65)
        te = _clamp(d['te'], -30, 30)
        S = _clamp(d['S'], 0.3, 1.2)
        tl, tt = math.tan(math.radians(le)), math.tan(math.radians(te))
        S = min(S, 0.88 / max(1e-6, tl - tt))            # (the tip keeps a chord)
        w = {'S': S, 'le': le, 'te': te, 't': _panel_t(d, 1.0, S), 'kn': d['kn']}
        bm = rs._wing(bm, w, level + 1 if level >= 1 else 0) or bm
        if part == 'FIN':                                # (the span up, canted out)
            bmesh.ops.transform(bm, matrix=Matrix(((0, 0, -1), (0, 1, 0), (1, 0, 0))).to_4x4(), verts=list(bm.verts))
            bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(_clamp(d['cant'], 0, 45)), 3, 'Y'),
                             verts=list(bm.verts))
        return bm
    if part == 'NOZZLE':                                 # side outline: the flaps closing in; the exhaust a deep box
        Ln, Wn, Hf, Hr = d['Ln'], d['Wn'], d['Hf'], d['Hr']
        mid = _clamp(d['mid'], 0.3, 0.75)
        dz = d['drop'] * Hf
        pts = [(0.0, -Hf / 2), (-mid * Ln, -0.48 * Hf), (-Ln, -Hr / 2 - dz), (-Ln, Hr / 2 - dz), (-mid * Ln, 0.48 * Hf),
               (0.0, Hf / 2)]
        _side_solid(bm, pts, Wn, -Wn / 2)
        if level < 1:
            _pocket(bm, (0.0, -1.0, 0.0), d['inset'] * Hf, (0.0, d['deep'] * Ln, 0.0))
        return bm
    if part == 'CANOPY':                                 # arch sections over a flat base: a pointed front, long behind
        Lc, e = d['Lc'], _clamp(d['e'], 1.6, 4.0)
        m = max(12, segs // 2)
        rows = 26
        rings = []
        for i in range(rows):
            t = (i / (rows - 1)) ** 0.85
            y = -Lc / 2 + t * Lc
            if i == rows - 1:
                rings.append([bm.verts.new((0.0, y, 0.0))])
                continue
            ws, hs = d['w'] + [0.0], d['h'] + [0.0]
            w, h = max(0.004, rs._spline(ws, t)), max(0.003, rs._spline(hs, t))
            ring = []
            for k in range(m + 1):
                a = math.pi * k / m
                c, s_ = math.cos(a), math.sin(a)
                ring.append(bm.verts.new((w * math.copysign(abs(c) ** (2 / e), c), y, h * abs(s_) ** (2 / e))))
            rings.append(ring)
        rs._loft(bm, rings)
        return bm
    # NOSE: chine sections (a rounded top, a flatter bottom, a sharp chine where they meet), to a point at the front
    Ln, W, Ht, Hb = d['Ln'], d['W'], d['Ht'], d['Hb']
    p_, q_ = _clamp(d['p'], 1.2, 3.0), _clamp(d['q'], 1.05, 2.5)
    k = max(6, segs // 4)
    rows = 22
    rings = []
    for i in range(rows):
        t = i / (rows - 1)
        y = t * Ln
        dz = -d['droop'] * t
        if i == rows - 1:
            rings.append([bm.verts.new((0.0, y, dz))])
            continue
        w = W * (1.0 - t)
        ht, hb = Ht * (1.0 - t) ** 0.75, Hb * (1.0 - t) ** 0.9
        right = [(w * j / k, ht * (1.0 - (j / k) ** p_)) for j in range(k + 1)]                 # (top -> chine)
        right += [(w * j / k, -hb * (1.0 - (j / k) ** q_)) for j in range(k - 1, -1, -1)]       # (chine -> bottom)
        ring = right + [(-x, z) for x, z in reversed(right[1:-1])]
        rings.append([bm.verts.new((x, y, z + dz)) for x, z in ring])
    rs._loft(bm, rings)
    return bm


# --- Tank ------------------------------------------------------------------------------------------------------------

def _mbt(bm, part, d, level, segs):
    if part == 'TURRET':                                 # M1: cheeks angled back, the mantlet recess, sides leaning in
        Lt, Wt, Ht = d['Lt'], d['Wt'], d['Ht']
        hw = Wt / 2
        mw, mr = _clamp(d['mw'], 0.03, 0.15) * Lt, _clamp(d['mr'], 0.03, 0.18) * Lt
        ch = _clamp(d['cheek'], 0.2, 0.6)
        right = [(0.0, 0.5 * Lt - mr), (mw, 0.5 * Lt - mr), (mw + 0.02 * Lt, 0.5 * Lt),
                 (hw * 0.9, 0.5 * Lt - ch * (hw * 0.9 - mw)), (hw, 0.5 * Lt - ch * (hw * 0.9 - mw) - 0.06 * Lt),
                 (hw, -0.36 * Lt), (hw - _clamp(d['rear'], 0.05, 0.5) * hw * 0.6, -0.5 * Lt), (0.0, -0.5 * Lt)]
        _plan_solid(bm, _mirror_half(right), Ht, _clamp(d['lean'], 0.75, 1.0))
        if level < 2:
            bm = _cut_at(bm, (0.0, 0.35, 1.0), (0.0, 0.5 * Lt - mr, Ht * (1.0 - _clamp(d['roof'], 0.0, 0.3))), 0.4)
        return bm
    if part == 'SKIRT':                                  # M1: the front edge slanted (the idler), the top flange in
        L, H = d['L'], d['H']
        fr, rr = _clamp(d['front'], 0.03, 0.2) * L, _clamp(d['rear'], 0.15, 0.7) * H
        pts = [(0.5 * L, H), (0.5 * L - fr, 0.0), (-0.47 * L, 0.0), (-0.5 * L, rr), (-0.5 * L, H)]
        fl = _clamp(d['flange'], 0.7, 0.93) * H
        folds = [((0.7 * L, fl), (-0.7 * L, fl), math.radians(_clamp(d['fl_a'], 30, 90)), False)]
        _side_panel(bm, pts, _panel_t(d, L, H), folds, level)
        return bm
    if part == 'MANTLET':                                # a slab: its top and bottom sloped back
        Wm, Hm, Dm = d['Wm'], d['Hm'], d['Dm']
        fc = d['face'] * Hm / 0.4
        pts = [(0.0, -Hm / 2), (fc * 0.75, -Hm / 2 + d['bot'] * Hm), (fc, Hm * 0.2), (fc * 0.4, Hm / 2),
               (-Dm, Hm / 2), (-Dm, -Hm / 2)]
        _side_solid(bm, pts, Wm, -Wm / 2)
        return bm
    if part == 'GLACIS':                                 # front view (sponsons over the tracks) pushed back, then
        Lg, Wu, Wl, Hs, Hg = d['Lg'], d['Wu'], d['Wl'], d['Hs'], d['Hg']   # the upper / lower glacis cut
        Hs = min(Hs, 0.8 * Hg)
        right = [(0.0, Hg), (Wu / 2, Hg), (Wu / 2, Hs), (Wl / 2, Hs), (Wl / 2, 0.0), (0.0, 0.0)]
        _front_solid(bm, _mirror_half(right), Lg, Lg / 2)
        if level < 2:
            lh = _clamp(d['low_h'], 0.1, 0.45) * Hg
            lo = math.radians(_clamp(d['low'], 20, 70))
            nose_y = Lg / 2 - 0.08 * Lg
            zn = lh + 0.02 * Hg
            run = _clamp(d['run'], 0.4, 0.9) * Lg      # (the upper glacis: long and shallow, from the nose back)
            bm = _cut_at(bm, (0.0, math.cos(lo), -math.sin(lo)), (0.0, nose_y, lh), 0.4)
            bm = _cut_at(bm, (0.0, Hg - zn, run), (0.0, nose_y, zn), 0.3)
        return bm
    if part == 'CAST':                                   # T-72: a low cast dome, its front thicker, a flat face cut
        w = [_clamp(v, 0.3, 1.2) for v in d['w']]
        fwd = d['fwd']
        q = dict(n=24, round=0.0, bulge=0.0, front='SIDE', back=1.0, W=d['Wc'], D=d['Dc'], L=d['Hc'], w=w,
                 d=[w[0], w[1] * 0.99, w[2] * 1.01, w[3]], y=[fwd, fwd * 0.9, fwd * 0.4, -fwd * 0.3], c0=0.0, cf0=0.9,
                 c1=_clamp(0.45, 0.2, 0.7), cf1=_clamp(d['top'], 0.15, 0.6), rows=10)
        rs.body(bm, q, segs)
        if level < 2:
            bm = rs._cut(bm, [0.0, 0.98, 0.2, _clamp(d['cut'], 0.02, 0.15)], 0.6)
        return bm
    # WHEEL: tyre, dished disc, hub (round the X axis, its outer face +X)
    R, Wt = d['R'], d['Wt']
    rim, dish, hub = _clamp(d['rim'], 0.7, 0.95) * R, _clamp(d['dish'], 0.5, 0.9) * R, _clamp(d['hub'], 0.15, 0.45) * R
    rim, dish = max(rim, dish + 0.03 * R), min(dish, rim - 0.03 * R)
    hw, cp, dp = Wt / 2, d['cap'] * R, d['depth'] * R
    prof = [(0.0, hw + cp), (hub * 0.55, hw + cp), (hub, hw + cp * 0.4), (hub * 1.1, hw - dp * 0.3),
            (dish, hw - dp), (rim, hw), (R * 0.97, hw), (R, hw * 0.8), (R, -hw * 0.8), (R * 0.97, -hw), (rim, -hw),
            (dish, -hw + dp), (hub * 1.1, -hw + dp * 0.3), (hub, -hw - cp * 0.2), (0.0, -hw - cp * 0.2)]
    _lathe(bm, prof, segs, 'X')
    return bm


# --- building --------------------------------------------------------------------------------------------------------

def build(p, segs=32, level=0):
    """The solid of real-part parameters ``p``; ``level`` 1: without its pockets / recesses, 2: without its cuts and
    folds too, 3: the same (the plain outline)."""
    bm = bmesh.new()
    v, part, d = p['kind'], p['part'], p['d']
    if v == 'LAMBO':
        bm = _lambo(bm, part, d, level)
    elif v == 'P911':
        bm = _p911(bm, part, d, level, segs)
    elif v == 'F22':
        bm = _f22(bm, part, d, level, segs)
    else:
        bm = _mbt(bm, part, d, level, segs)
    if p.get('curved'):
        rs._split_bent(bm)
    return bm
