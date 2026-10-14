"""0.21 Robot Base Mesh: random, adjustable base meshes for robot parts.

Categories x styles (4):
    Humanoid  - Sleek (smooth, tapered, muscle-like volumes)
              - Rugged (faceted, chamfered, extra plates)
    Industrial - Sleek (clean cylinders / rounded boxes, joint discs)
               - Rugged (boxy chassis, pistons, struts, vents)
Parts: Head, Torso, Shoulder, Upper Arm, Forearm, Thigh, Calf, Foot (Upper Arm /
Thigh and Forearm / Calf share a builder with their own proportions), or a
whole body (every part a separate object, left and right separate).

Every part is live until Apply: length, width, thickness, taper, bulge,
roundness, resolution, details, variation, seed, and a live Bevel modifier
(width, segments, angle).  The shapes are built in Python (bmesh) - Geometry
Nodes has no bevel - and rebuilt on every change.

``build_part`` is pure (returns verts / faces) and tested headless.
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty
from mathutils import Matrix, Vector

COLL = 'Robot Base'
MOD_BEVEL = 'MCH_RobotBevel'
CATEGORIES = (('HUMANOID', 'Humanoid', 'Human-like robot'), ('INDUSTRIAL', 'Industrial', 'Industrial robot'))
STYLES = (('SLEEK', 'Sleek', 'Refined: smooth, tapered volumes'), ('RUGGED', 'Rugged', 'Chunky: faceted, extra plates'))
PARTS = (('HEAD', 'Head', ''), ('TORSO', 'Torso', ''), ('SHOULDER', 'Shoulder', ''),
         ('UPPER_ARM', 'Upper Arm', ''), ('FOREARM', 'Forearm', ''), ('THIGH', 'Thigh', ''),
         ('CALF', 'Calf', ''), ('FOOT', 'Foot', ''))
PART_IDS = tuple(p[0] for p in PARTS)

# default size per part (length = main axis, width = X, depth = Y), metres for a ~1.8 m robot
DEFAULTS = {
    'HEAD': (0.28, 0.20, 0.24), 'TORSO': (0.62, 0.42, 0.26), 'SHOULDER': (0.16, 0.20, 0.20),
    'UPPER_ARM': (0.244, 0.100, 0.115), 'FOREARM': (0.257, 0.096, 0.080), 'THIGH': (0.405, 0.178, 0.181),
    'CALF': (0.42, 0.13, 0.14), 'FOOT': (0.26, 0.11, 0.08),
}


# -----------------------------------------------------------------------------
# Geometry helpers (pure: lists of verts / faces)
# -----------------------------------------------------------------------------


class Builder:
    def __init__(self):
        self.verts, self.faces = [], []

    def add(self, verts, faces):
        o = len(self.verts)
        self.verts += [tuple(v) for v in verts]
        self.faces += [tuple(i + o for i in f) for f in faces]

    def transform(self, start, mat):
        for i in range(start, len(self.verts)):
            self.verts[i] = tuple(mat @ Vector(self.verts[i]))


def superellipse(n, sx, sy, power, phase=0.0):
    pts = []
    e = 2.0 / max(power, 0.5)
    for i in range(n):
        a = 2.0 * math.pi * i / n + phase
        c, s = math.cos(a), math.sin(a)
        pts.append((sx * math.copysign(abs(c) ** e, c), sy * math.copysign(abs(s) ** e, s)))
    return pts


def end_point(kind, sides, a, power):
    """Unit outline point at angle ``a`` for one end shape.  Polygons put a flat side to the
    front (+Y); a square fills the -1..1 box like the boxy style does."""
    c, s = math.cos(a), math.sin(a)
    if kind == 'ROUND':
        return c, s
    if kind in {'SQUARE', 'POLYGON'}:
        k = 4 if kind == 'SQUARE' else max(3, int(sides))
        seg = 2.0 * math.pi / k
        rel = (a - (math.pi / 2 + math.pi / k)) % seg            # corners at pi/2 + pi/k + j * seg
        r = math.cos(math.pi / k) / math.cos(rel - seg / 2)
        r /= math.cos(math.pi / k) if kind == 'SQUARE' else math.sqrt(math.cos(math.pi / k))
        return r * c, r * s
    e = 2.0 / max(power, 0.5)                                  # STYLE: superellipse from roundness
    return math.copysign(abs(c) ** e, c), math.copysign(abs(s) ** e, s)


def ends_ring(ring, ends):
    """Ring count / phase so polygon corners of both ends fall on ring vertices."""
    ks = [4 if kind == 'SQUARE' else max(3, int(n)) for kind, n in (ends['bottom'], ends['top'])
          if kind in {'SQUARE', 'POLYGON'}]
    if not ks:
        return ring, None
    m = 1
    for k in ks:
        m = m * 2 * k // math.gcd(m, 2 * k)
    if m > 96:
        m = 2 * max(ks)
    ring = max(m, int(math.ceil(ring / m)) * m)
    return ring, math.pi / 2 + math.pi / ks[0]


def loft(sections, ring, power, caps=True, phase=None, ends=None, span=None):
    """Solid through cross sections [(z, sx, sy, ox, oy)] (superellipse rings, Z up).
    ``ends``: {'bottom': (kind, sides), 'top': (kind, sides), 'mid': 0..1} morphs the outline
    from the lowest section (bottom) to the highest (top); ``span`` = (z_bottom, z_top)."""
    if ends is not None and ends['bottom'][0] == 'STYLE' and ends['top'][0] == 'STYLE':
        ends = None
    if ends is not None:
        ring, ph = ends_ring(ring, ends)
        phase = ph if ph is not None and phase is None else phase
    phase = math.pi / ring if phase is None else phase
    verts, faces = [], []
    zs = [sec[0] for sec in sections]
    z0, z1 = span if span is not None else (min(zs), max(zs))
    for z, sx, sy, ox, oy in sections:
        sx, sy = max(sx, 1e-4), max(sy, 1e-4)
        if ends is None:
            for x, y in superellipse(ring, sx, sy, power, phase):
                verts.append((x + ox, y + oy, z))
            continue
        t = min(1.0, max(0.0, (z - z0) / (z1 - z0))) if abs(z1 - z0) > 1e-9 else 0.0
        mid = min(0.95, max(0.05, ends.get('mid', 0.5)))
        w = t ** (math.log(0.5) / math.log(mid))
        w = w * w * (3.0 - 2.0 * w)
        for i in range(ring):
            a = 2.0 * math.pi * i / ring + phase
            bx, by = end_point(ends['bottom'][0], ends['bottom'][1], a, power)
            tx, ty = end_point(ends['top'][0], ends['top'][1], a, power)
            verts.append((sx * (bx + (tx - bx) * w) + ox, sy * (by + (ty - by) * w) + oy, z))
    ns = len(sections)
    for k in range(ns - 1):
        for i in range(ring):
            a, b = k * ring + i, k * ring + (i + 1) % ring
            faces.append((a, b, b + ring, a + ring))
    if caps:
        faces.append(tuple(reversed(range(ring))))
        faces.append(tuple((ns - 1) * ring + i for i in range(ring)))
    if ns > 1 and sections[0][0] > sections[-1][0]:      # sections run downward: keep normals outward
        faces = [tuple(reversed(f)) for f in faces]
    return verts, faces


def box(cx, cy, cz, sx, sy, sz):
    v = [(cx + x * sx / 2, cy + y * sy / 2, cz + z * sz / 2) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return v, f


def cylinder(cx, cy, cz, r, h, n=16, axis='Z'):
    verts, faces = loft([(-h / 2, r, r, 0, 0), (h / 2, r, r, 0, 0)], n, 2.0)
    rot = {'Z': Matrix.Identity(3), 'X': Matrix.Rotation(math.pi / 2, 3, 'Y'),
           'Y': Matrix.Rotation(math.pi / 2, 3, 'X')}[axis]
    verts = [tuple(rot @ Vector(v) + Vector((cx, cy, cz))) for v in verts]
    return verts, faces


# -----------------------------------------------------------------------------
# Part builders
# -----------------------------------------------------------------------------


def _style(p):
    """(superellipse power, ring resolution, rugged?) from the settings."""
    rugged = p['style'] == 'RUGGED'
    # roundness 1 = round, 0 = boxy
    rnd = p['roundness']
    power = 2.0 + (1.0 - rnd) * (10.0 if p['category'] == 'INDUSTRIAL' else 6.0)
    base = 8 if rugged else 16
    ring = max(4, int(round(base * (0.5 + p['resolution']))))
    if rugged:
        ring = max(4, ring - ring % 4)
    return power, ring, rugged


END_SHAPES = (('STYLE', 'Style', 'Follow Roundness'), ('ROUND', 'Round', 'Circle / cylinder end'),
              ('SQUARE', 'Square', 'Square end'), ('POLYGON', 'Polygon', 'Polygon end (set the sides)'))
END_IDS = tuple(e[0] for e in END_SHAPES)


def part_ends(p):
    """End shapes of the main volume (bottom -> top; foot: heel -> toe) or None."""
    bot = (p.get('bottom_shape', 'STYLE'), p.get('bottom_sides', 6))
    top = (p.get('top_shape', 'STYLE'), p.get('top_sides', 6))
    if bot[0] == 'STYLE' and top[0] == 'STYLE':
        return None
    return {'bottom': bot, 'top': top, 'mid': p.get('shape_mid', 0.5)}


def _more(secs, ends, n=6):
    """Extra in-between sections (linear) so an end-shape morph has room to change."""
    if ends is None:
        return secs
    out = []
    for a, b in zip(secs, secs[1:]):
        for i in range(n):
            t = i / n
            out.append(tuple(x + (y - x) * t for x, y in zip(a, b)))
    out.append(secs[-1])
    return out


# humanoid limb shape defaults (0.21.1), measured from a Genesis 9 forearm segment:
# elbow 9.2 x 7.7, wrist 5.3 x 5.3 (length 24.6) - flat to ~30 %, then tapering; a muscle groove
LIMB_SHAPES = {
    # forearm: elbow 9.2 x 7.7 -> wrist 5.3 x 5.3 over 24.6, flat to ~30 % then tapering, a muscle groove
    'FOREARM': dict(bottom_w=0.58, bottom_d=0.69, taper_start=0.3, bulge=0.15, bulge_pos=0.2, bulge_offset=0.0,
                    split=0.0, split_angle=math.radians(90), groove=0.35, groove_angle=math.radians(70), ridge=0.0,
                    ridge_angle=math.radians(200), twist=0.0, bow=0.0, bow_angle=math.radians(90), notch=0.015,
                    notch_width=0.5, slant=math.radians(10), top_slant=0.0),
    # upper arm: 9.6 (side) x 11.0 (front-back) -> 8.2 x 8.4 over 23.4, flat to ~40 %, grooves on both sides
    'UPPER_ARM': dict(bottom_w=0.85, bottom_d=0.76, taper_start=0.42, bulge=0.2, bulge_pos=0.3, bulge_offset=0.2,
                      split=0.25, split_angle=0.0, groove=0.0, groove_angle=math.radians(0), ridge=0.0,
                      ridge_angle=math.radians(270), twist=0.0, bow=0.0, bow_angle=math.radians(90), notch=0.0,
                      notch_width=0.5, slant=0.0, top_slant=0.0),
    # thigh: 17.1 x 17.4 below the hip cut -> knee 11.4 x 12.4 over 38.8, hip end cut on a slant
    'THIGH': dict(bottom_w=0.67, bottom_d=0.71, taper_start=0.3, bulge=0.15, bulge_pos=0.3, bulge_offset=0.2,
                  split=0.15, split_angle=0.0, groove=0.2, groove_angle=math.radians(180), ridge=0.0,
                  ridge_angle=math.radians(270), twist=0.0, bow=0.0, bow_angle=math.radians(90), notch=0.0,
                  notch_width=0.5, slant=0.0, top_slant=math.radians(25)),
    'CALF': dict(bottom_w=0.55, bottom_d=0.5, taper_start=0.35, bulge=0.6, bulge_pos=0.3, bulge_offset=-0.6,
                 split=0.2, split_angle=math.radians(90), groove=0.15, groove_angle=math.radians(270), ridge=0.0,
                 ridge_angle=math.radians(90), twist=0.0, bow=0.0, bow_angle=math.radians(90), notch=0.0,
                 notch_width=0.5, slant=0.0, top_slant=0.0),
}
LIMB_KEYS = tuple(LIMB_SHAPES['FOREARM'])


def _dent(a, a0, width):
    d = (a - a0 + math.pi) % (2.0 * math.pi) - math.pi
    return math.exp(-(d / width) ** 2)


def limb_mesh(p, ring, power, rugged, ends=None, jit=None):
    """Humanoid limb base mesh hanging from z = 0 (top) to z = -L (bottom): quad rings around,
    flat end caps (concentric quads + small fan).  Every shape term is a slider."""
    g = dict(LIMB_SHAPES.get(p['part'], LIMB_SHAPES['FOREARM']))
    g.update({k: p[k] for k in LIMB_KEYS if k in p})
    L, W, D = p['length'], p['width'], p['depth']
    jit = jit or (lambda x, amount=0.0: x)
    if ends is not None and ends['bottom'][0] == 'STYLE' and ends['top'][0] == 'STYLE':
        ends = None
    phase = math.pi / ring
    if ends is not None:
        ring, ph = ends_ring(ring, ends)
        phase = ph if ph is not None else phase
    nl = (6 + int(round(8 * p['resolution']))) if rugged else (10 + int(round(18 * p['resolution'])))
    ts = g['taper_start']
    bw, bd = jit(g['bottom_w'], 0.08), jit(g['bottom_d'], 0.08)
    W, D = jit(W, 0.05), jit(D, 0.05)
    bpos = min(0.95, max(0.05, jit(g['bulge_pos'], 0.15)))
    notch_d, notch_w = g['notch'] * L, max(0.05, g['notch_width']) * W / 2
    tan_s = math.tan(max(-1.3, min(1.3, g['slant'])))
    tan_t = math.tan(max(-1.3, min(1.3, g['top_slant'])))
    bow = g['bow'] * L * 0.1
    bx, by = math.cos(g['bow_angle']), math.sin(g['bow_angle'])

    def outline(t):
        u = 0.0 if t <= ts else (t - ts) / max(1e-6, 1.0 - ts)
        u = u * u * (3.0 - 2.0 * u)
        gb = math.exp(-((t - bpos) / 0.22) ** 2)
        grow = 1.0 + g['bulge'] * 0.25 * gb
        w = W * (1.0 + (bw - 1.0) * u) * grow
        d = D * (1.0 + (bd - 1.0) * u) * grow
        ox = bow * math.sin(math.pi * t) * bx
        oy = bow * math.sin(math.pi * t) * by + g['bulge_offset'] * g['bulge'] * 0.12 * D * gb
        tw = g['twist'] * t
        if ends is not None:
            mid = min(0.95, max(0.05, ends.get('mid', 0.5)))
            e = (1.0 - t) ** (math.log(0.5) / math.log(mid))          # 0 at top end, 1 at bottom end
            e = e * e * (3.0 - 2.0 * e)
        pts = []
        for i in range(ring):
            a = 2.0 * math.pi * i / ring + phase
            if ends is None:
                ux, uy = end_point('STYLE', 0, a, power)
            else:
                tx, ty = end_point(ends['top'][0], ends['top'][1], a, power)
                qx, qy = end_point(ends['bottom'][0], ends['bottom'][1], a, power)
                ux, uy = qx + (tx - qx) * e, qy + (ty - qy) * e
            sa = g['split_angle']
            m = 1.0 - g['split'] * 0.22 * (_dent(a, sa, 0.6) + _dent(a, sa + math.pi, 0.6))
            m -= g['groove'] * 0.3 * _dent(a, g['groove_angle'], 0.5) * (1.0 - 0.6 * t)
            m += g['ridge'] * 0.15 * _dent(a, g['ridge_angle'], 0.18)
            x, y = ux * w / 2 * m, uy * d / 2 * m
            c, s_ = math.cos(tw), math.sin(tw)
            pts.append((x * c - y * s_ + ox, x * s_ + y * c + oy))
        return pts

    def zof(t, x):
        z = -L * t
        if notch_d > 0 and t < 0.3:                                  # V notch across the top end
            v = max(0.0, 1.0 - abs(x) / notch_w)
            z -= notch_d * v * (1.0 - t / 0.3)
        if tan_s and t > 0.7:                                        # slanted bottom cut
            z += tan_s * x * (t - 0.7) / 0.3
        if tan_t and t < 0.35:                                       # slanted top cut (hip)
            z += tan_t * x * (1.0 - t / 0.35)
        return z

    verts, faces = [], []
    rings = []
    for k in range(nl + 1):
        t = k / nl
        start = len(verts)
        for x, y in outline(t):
            verts.append((x, y, zof(t, x)))
        rings.append(start)
    for k in range(nl):
        a0, a1 = rings[k], rings[k + 1]
        for i in range(ring):
            j = (i + 1) % ring
            faces.append((a0 + i, a1 + i, a1 + j, a0 + j))

    def cap(t, top):
        outer = outline(t)
        cx = sum(q[0] for q in outer) / ring
        cy = sum(q[1] for q in outer) / ring
        prev = rings[0] if top else rings[-1]
        for sc in (0.62, 0.28):
            start = len(verts)
            for x, y in outer:
                xx, yy = cx + (x - cx) * sc, cy + (y - cy) * sc
                verts.append((xx, yy, zof(t, xx)))
            for i in range(ring):
                j = (i + 1) % ring
                f = (prev + i, prev + j, start + j, start + i)
                faces.append(f if top else tuple(reversed(f)))
            prev = start
        verts.append((cx, cy, zof(t, cx)))
        c = len(verts) - 1
        for i in range(ring):
            j = (i + 1) % ring
            f = (prev + i, prev + j, c)
            faces.append(f if top else tuple(reversed(f)))
    cap(0.0, True)
    cap(1.0, False)
    return verts, faces


def build_part(p):
    """verts, faces of one part from a settings dict (pure).  Main axis: Z for head / torso /
    limbs (limbs hang down from the joint at z = 0), Y for the foot (toe forward)."""
    rng = random.Random(int(p['seed']) * 97 + PART_IDS.index(p['part']))
    var = p['variation']

    def jit(x, amount=0.18):
        return x * (1.0 + rng.uniform(-amount, amount) * var)
    L, W, D = p['length'], p['width'], p['depth']
    taper, bulge = p['taper'], p['bulge']
    power, ring, rugged = _style(p)
    industrial = p['category'] == 'INDUSTRIAL'
    E = part_ends(p)
    b = Builder()
    part = p['part']
    if part in {'UPPER_ARM', 'THIGH', 'FOREARM', 'CALF'}:
        lower = part in {'FOREARM', 'CALF'}
        top_w, bot_w = W, W * (1.0 - 0.45 * taper)
        top_d, bot_d = D, D * (1.0 - 0.4 * taper)
        if industrial:
            # strut: straight box / cylinder with joint discs, pistons alongside
            n = 3 if E is None else 8
            secs = [(-L * t, jit(top_w + (bot_w - top_w) * t, 0.08) / 2, jit(top_d + (bot_d - top_d) * t, 0.08) / 2,
                     0, 0) for t in (0.08 + 0.84 * i / (n - 1) for i in range(n))]
            b.add(*loft(secs, ring, power, ends=E))
            jr = max(W, D) * 0.42
            b.add(*cylinder(0, 0, -L * 0.04, jr, W * 1.05, ring + 4, 'X'))
            b.add(*cylinder(0, 0, -L * 0.96, jr * (0.9 if lower else 0.85), W * 0.95, ring + 4, 'X'))
            if p['details']:
                pr = W * (0.1 if rugged else 0.07)
                side = 1 if rng.random() > 0.5 else -1
                b.add(*cylinder(0, side * (D * 0.5 + pr * 1.2), -L * 0.5, pr, L * 0.62, 10))
                b.add(*cylinder(0, side * (D * 0.5 + pr * 1.2), -L * 0.32, pr * 1.6, L * 0.3, 10))
                if rugged:
                    b.add(*box(0, -side * D * 0.52, -L * 0.5, W * 0.6, D * 0.12, L * 0.4))
        else:
            # anatomical limb (0.21.1): cross-section sliders, no joints
            peak = p.get('bulge_pos', 0.3)
            b.add(*limb_mesh(p, ring, power, rugged, E, jit))
            if p['details'] and rugged:
                b.add(*box(0, D * 0.42, -L * peak, W * 0.7, D * 0.18, L * 0.32))
                b.add(*box(W * 0.45, 0, -L * 0.6, W * 0.16, D * 0.6, L * 0.28))
            elif p['details']:
                b.add(*loft([(-L * (peak - 0.12), W * 0.38, D * 0.06, 0, D * 0.5),
                             (-L * (peak + 0.18), W * 0.3, D * 0.05, 0, D * 0.48)], ring, power))
    elif part == 'TORSO':
        if industrial:
            span = (0.0, L * 0.95)
            b.add(*loft(_more([(0, jit(W * 0.42) / 2, jit(D * 0.8) / 2, 0, 0),
                               (L * 0.18, W * 0.5 / 2, D * 0.85 / 2, 0, 0)], E),
                        ring, power, ends=E, span=span))                                  # pelvis block
            b.add(*loft(_more([(L * 0.3, jit(W * 0.86) / 2, D / 2, 0, 0), (L * 0.95, jit(W) / 2, jit(D) / 2, 0, 0)], E),
                        ring, power, ends=E, span=span))                                  # chassis
            b.add(*cylinder(0, 0, L * 0.24, W * 0.12, L * 0.16, ring))                    # spine joint
            if p['details']:
                b.add(*cylinder(0, D * 0.5, L * 0.62, W * 0.16, D * 0.2, ring + 4, 'Y'))  # power core
                if rugged:
                    for k in (-1, 1):
                        b.add(*box(k * W * 0.32, -D * 0.52, L * 0.6, W * 0.2, D * 0.16, L * 0.5))   # back packs
                    for i in range(4):
                        b.add(*box(0, D * 0.52, L * (0.36 + 0.04 * i), W * 0.5, D * 0.04, L * 0.015))  # vents
        else:
            prof = [(0.0, 0.72, 0.85), (0.12, 0.78, 0.9), (0.3, 0.6 + 0.1 * (1 - taper), 0.78), (0.5, 0.82, 0.92),
                    (0.72, 1.0, 1.0), (0.88, 0.98 + 0.08 * bulge, 0.92), (0.97, 0.55, 0.62), (1.0, 0.3, 0.38)]
            if rugged:
                prof = prof[::1]
            secs = [(L * t, jit(W * sx, 0.05) / 2, jit(D * sy, 0.05) / 2, 0, D * 0.04 * math.sin(math.pi * t))
                    for t, sx, sy in prof]
            b.add(*loft(secs, ring, power, ends=E))
            if p['details']:
                if rugged:
                    for k in (-1, 1):
                        b.add(*box(k * W * 0.2, D * 0.45, L * 0.74, W * 0.34, D * 0.16, L * 0.26))  # chest plates
                    b.add(*box(0, D * 0.4, L * 0.38, W * 0.4, D * 0.14, L * 0.16))                # abs plate
                else:
                    b.add(*loft([(L * 0.6, W * 0.36, D * 0.05, 0, D * 0.47), (L * 0.86, W * 0.42, D * 0.05, 0, D * 0.46)],
                                ring, power))                                                       # chest plate
    elif part == 'HEAD':
        if industrial:
            b.add(*loft([(0, W * 0.3, D * 0.3, 0, 0), (L * 0.15, W * 0.32, D * 0.32, 0, 0)], ring, 2.0 + (power - 2) * 0.5))
            b.add(*loft(_more([(L * 0.2, jit(W) / 2, jit(D) / 2, 0, 0), (L * 0.85, jit(W) / 2, jit(D) / 2, 0, 0),
                               (L, W * (0.42 if not rugged else 0.48), D * (0.42 if not rugged else 0.48), 0, 0)], E),
                        ring, power, ends=E))
            if p['details']:
                b.add(*cylinder(0, D * 0.5, L * 0.58, W * 0.14, D * 0.12, ring + 4, 'Y'))       # sensor lens
                if rugged:
                    b.add(*box(W * 0.3, 0, L * 1.05, W * 0.06, D * 0.06, L * 0.25))           # antenna
                    for i in range(3):
                        b.add(*box(0, D * 0.51, L * (0.3 + 0.05 * i), W * 0.5, D * 0.03, L * 0.02))
        else:
            prof = [(0.0, 0.42, 0.42, 0.0), (0.18, 0.5, 0.55, 0.02), (0.3, 0.86, 0.9, 0.05), (0.55, 1.0, 1.0, 0.03),
                    (0.8, 0.95, 0.95, 0.0), (0.93, 0.7, 0.72, -0.02), (1.0, 0.25, 0.28, -0.03)]
            secs = [(L * t, jit(W * sx, 0.05) / 2, jit(D * sy, 0.05) / 2, 0, D * oy) for t, sx, sy, oy in prof]
            b.add(*loft(secs, ring, power, ends=E))
            if p['details']:
                if rugged:
                    b.add(*box(0, D * 0.42, L * 0.36, W * 0.72, D * 0.22, L * 0.18))          # jaw guard
                    for k in (-1, 1):
                        b.add(*box(k * W * 0.5, 0, L * 0.55, W * 0.1, D * 0.4, L * 0.22))     # ear blocks
                else:
                    b.add(*loft([(L * 0.5, W * 0.38, D * 0.06, 0, D * 0.5), (L * 0.68, W * 0.4, D * 0.06, 0, D * 0.49)],
                                ring, power))                                               # visor
    elif part == 'SHOULDER':
        if industrial:
            b.add(*cylinder(0, 0, 0, max(W, D) * 0.5, W * 0.9, ring + 4, 'X'))              # joint housing
            b.add(*cylinder(W * 0.5, 0, 0, max(W, D) * 0.36, W * 0.2, ring + 4, 'X'))      # disc
            if p['details'] and rugged:
                b.add(*box(0, 0, max(W, D) * 0.55, W * 1.1, D * 1.1, L * 0.25))           # top guard
        else:
            layers = 3 if rugged else 1
            for k in range(layers):
                s = 1.0 - 0.14 * k
                n = 6
                secs = []
                for i in range(n + 1):
                    t = i / n
                    rr = math.sin(max(0.05, 1 - t) * math.pi / 2) ** 0.6
                    secs.append((L * (t * 0.9 - 0.1) + k * L * 0.12, jit(W * s * rr * (1 + 0.15 * bulge)) / 2,
                                 jit(D * s * rr) / 2, W * 0.08 * k, 0))
                b.add(*loft(secs, ring, power, ends=E))
    elif part == 'FOOT':
        # built along Z (heel at 0, toe at L) then turned so the toe points to +Y
        start = len(b.verts)
        if industrial:
            b.add(*loft(_more([(0, W / 2, D * 0.5, 0, D * 0.15), (L * 0.75, W / 2, D * 0.45, 0, D * 0.1)], E),
                        ring, power, ends=E))
            toes = 3 if rugged else 2
            for i in range(toes):
                x = (i - (toes - 1) / 2) * W / toes
                b.add(*box(x, -D * 0.05, L * 0.88, W / toes * 0.86, D * 0.45, L * 0.24))
            if p['details']:
                b.add(*cylinder(0, D * 0.75, L * 0.25, W * 0.28, W * 0.9, ring, 'X'))     # ankle joint
        else:
            prof = [(0.0, 0.8, 0.9, 0.05), (0.2, 0.95, 1.0, 0.0), (0.5, 1.0, 0.75, -0.1), (0.8, 0.95, 0.5, -0.22),
                    (1.0, 0.7 * (1 - 0.3 * taper), 0.32, -0.3)]
            secs = [(L * t, jit(W * sx, 0.05) / 2, jit(D * sy, 0.05) / 2, 0, D * oy) for t, sx, sy, oy in prof]
            b.add(*loft(secs, ring, power, ends=E))
            if p['details'] and rugged:
                b.add(*box(0, -D * 0.48, L * 0.5, W * 1.05, D * 0.14, L * 0.9))             # sole
        b.transform(start, Matrix.Rotation(-math.pi / 2, 3, 'X'))                         # Z -> +Y (toe forward)
    if p.get('side') == 'RIGHT':
        b.verts = [(-x, y, z) for x, y, z in b.verts]
        b.faces = [tuple(reversed(f)) for f in b.faces]
    return b.verts, b.faces


# -----------------------------------------------------------------------------
# Live objects
# -----------------------------------------------------------------------------


def _settings(rp):
    return {k: getattr(rp, k) for k in ('category', 'style', 'part', 'side', 'seed', 'variation', 'length', 'width',
                                        'depth', 'taper', 'bulge', 'roundness', 'resolution', 'details',
                                        'bottom_shape', 'top_shape', 'bottom_sides', 'top_sides', 'shape_mid')
            + LIMB_KEYS}


def rebuild(ob):
    rp = ob.mch_robot
    verts, faces = build_part(_settings(rp))
    bm = bmesh.new()
    try:
        vs = [bm.verts.new(v) for v in verts]
        for f in faces:
            try:
                bm.faces.new([vs[i] for i in f])
            except ValueError:
                pass
        bm.normal_update()
        bm.to_mesh(ob.data)
    finally:
        bm.free()
    me = ob.data
    for poly in me.polygons:
        poly.use_smooth = rp.style == 'SLEEK'
    try:
        me.set_sharp_from_angle(angle=rp.bevel_angle + 0.05)
    except (AttributeError, TypeError):
        pass
    me.update()
    mod = ob.modifiers.get(MOD_BEVEL)
    if rp.bevel_width > 0:
        if mod is None:
            mod = ob.modifiers.new(MOD_BEVEL, 'BEVEL')
        mod.limit_method = 'ANGLE'
        mod.angle_limit = rp.bevel_angle
        mod.width = rp.bevel_width
        mod.segments = rp.bevel_segments
        mod.use_clamp_overlap = True
        mod.harden_normals = False
    elif mod is not None:
        ob.modifiers.remove(mod)


def _update(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and self.live and ob.type == 'MESH':
        rebuild(ob)


def _p(prop, **kw):
    kw.setdefault('update', _update)
    return prop(**kw)


class MCH_PG_RobotPart(bpy.types.PropertyGroup):
    live: BoolProperty(default=False, options={'HIDDEN'})
    category: _p(EnumProperty, name='Category', items=CATEGORIES, default='HUMANOID')
    style: _p(EnumProperty, name='Style', items=STYLES, default='SLEEK')
    part: _p(EnumProperty, name='Part', items=PARTS, default='TORSO')
    side: _p(EnumProperty, name='Side', items=[('CENTER', 'Center', ''), ('LEFT', 'Left', ''), ('RIGHT', 'Right', '')],
             default='CENTER')
    seed: _p(IntProperty, name='Seed', default=1, min=0)
    variation: _p(FloatProperty, name='Randomness', default=0.5, min=0.0, max=1.0, subtype='FACTOR',
                  description='How much the seed changes the proportions')
    length: _p(FloatProperty, name='Length', default=0.5, min=0.01, soft_max=3.0, unit='LENGTH')
    width: _p(FloatProperty, name='Width', default=0.3, min=0.005, soft_max=2.0, unit='LENGTH')
    depth: _p(FloatProperty, name='Thickness', default=0.2, min=0.005, soft_max=2.0, unit='LENGTH',
              description='Front-to-back thickness')
    taper: _p(FloatProperty, name='Taper', default=0.4, min=-1.0, max=1.0,
              description='Thinner toward the far end (- = thicker)')
    bulge: _p(FloatProperty, name='Bulge', default=0.5, min=0.0, max=2.0, description='Muscle-like volume')
    roundness: _p(FloatProperty, name='Roundness', default=0.6, min=0.0, max=1.0, subtype='FACTOR',
                  description='0 = boxy, 1 = round sections')
    resolution: _p(FloatProperty, name='Resolution', default=0.5, min=0.0, max=2.0,
                   description='Number of sides around the shape')
    details: _p(BoolProperty, name='Details', default=True, description='Extra plates, pistons, lenses, joints')
    bottom_shape: _p(EnumProperty, name='Bottom Shape', items=END_SHAPES, default='STYLE',
                     description='Outline at the bottom end (foot: heel)')
    top_shape: _p(EnumProperty, name='Top Shape', items=END_SHAPES, default='STYLE',
                  description='Outline at the top end (foot: toe); the shape morphs between the two')
    bottom_sides: _p(IntProperty, name='Bottom Sides', default=6, min=3, max=16)
    top_sides: _p(IntProperty, name='Top Sides', default=6, min=3, max=16)
    # humanoid limb shape (0.21.1)
    bottom_w: _p(FloatProperty, name='Bottom Width', default=0.58, min=0.1, max=2.5, subtype='FACTOR',
                 description='Width at the bottom end (wrist / ankle side) relative to the top')
    bottom_d: _p(FloatProperty, name='Bottom Thickness', default=0.69, min=0.1, max=2.5, subtype='FACTOR',
                 description='Thickness at the bottom end relative to the top')
    taper_start: _p(FloatProperty, name='Taper Start', default=0.3, min=0.0, max=0.95, subtype='FACTOR',
                    description='Where along the length it starts getting thinner')
    bulge_pos: _p(FloatProperty, name='Bulge Position', default=0.2, min=0.05, max=0.95, subtype='FACTOR')
    bulge_offset: _p(FloatProperty, name='Bulge Front/Back', default=0.0, min=-1.0, max=1.0,
                     description='+ = muscle swells to the front, - = to the back')
    split: _p(FloatProperty, name='Muscle Split', default=0.0, min=0.0, max=1.5,
              description='Pinch on two opposite sides: two muscle masses')
    split_angle: _p(FloatProperty, name='Split Angle', default=math.radians(90), subtype='ANGLE',
                    description='0 = pinch at the sides, 90 = pinch front and back')
    groove: _p(FloatProperty, name='Groove', default=0.35, min=0.0, max=1.5, description='Long dent between muscles')
    groove_angle: _p(FloatProperty, name='Groove Angle', default=math.radians(70), subtype='ANGLE')
    ridge: _p(FloatProperty, name='Ridge', default=0.0, min=0.0, max=2.0, description='Raised line along the length')
    ridge_angle: _p(FloatProperty, name='Ridge Angle', default=math.radians(200), subtype='ANGLE')
    twist: _p(FloatProperty, name='Twist', default=0.0, min=math.radians(-180), max=math.radians(180),
              subtype='ANGLE', description='Cross section turns along the length')
    bow: _p(FloatProperty, name='Bend', default=0.0, min=-1.0, max=1.0, description='Curve the limb')
    bow_angle: _p(FloatProperty, name='Bend Direction', default=math.radians(90), subtype='ANGLE')
    notch: _p(FloatProperty, name='Top Notch', default=0.015, min=0.0, max=0.3, subtype='FACTOR',
              description='V cut across the top end (depth, share of the length)')
    notch_width: _p(FloatProperty, name='Notch Width', default=0.5, min=0.05, max=1.0, subtype='FACTOR')
    slant: _p(FloatProperty, name='Bottom Slant', default=math.radians(10), min=math.radians(-60),
              max=math.radians(60), subtype='ANGLE', description='Tilt of the bottom cut')
    top_slant: _p(FloatProperty, name='Top Slant', default=0.0, min=math.radians(-60), max=math.radians(60),
                  subtype='ANGLE', description='Tilt of the top cut (e.g. thigh at the hip)')
    shape_mid: _p(FloatProperty, name='Shape Change', default=0.5, min=0.05, max=0.95, subtype='FACTOR',
                  description='Where the outline is half way between bottom and top shape')
    bevel_width: _p(FloatProperty, name='Bevel', default=0.006, min=0.0, soft_max=0.1, precision=4, unit='LENGTH')
    bevel_segments: _p(IntProperty, name='Bevel Segments', default=2, min=1, max=12,
                       description='1 = chamfer, more = round bevel')
    bevel_angle: _p(FloatProperty, name='Bevel Angle', default=math.radians(30.0), min=math.radians(1.0),
                    max=math.radians(180.0), subtype='ANGLE', description='Edges sharper than this get the bevel')


class MCH_PG_RobotSettings(bpy.types.PropertyGroup):
    category: EnumProperty(name='Category', items=CATEGORIES, default='HUMANOID')
    style: EnumProperty(name='Style', items=STYLES, default='SLEEK')
    seed: IntProperty(name='Seed', default=1, min=0)
    variation: FloatProperty(name='Randomness', default=0.5, min=0.0, max=1.0, subtype='FACTOR')
    details: BoolProperty(name='Details', default=False, description='Extra plates / pistons (off = plain base)')
    scale: FloatProperty(name='Scale', default=1.0, min=0.05, soft_max=5.0, description='Overall robot size')


def style_defaults(category, style, part):
    """Taper / bulge / roundness / bevel per category + style."""
    hum = category == 'HUMANOID'
    sleek = style == 'SLEEK'
    d = dict(taper=0.45 if hum else 0.15, bulge=(0.7 if sleek else 0.4) if hum else 0.0,
             roundness=(0.85 if sleek else 0.3) if hum else (0.55 if sleek else 0.05),
             resolution=0.8 if sleek else 0.5, bevel_segments=3 if sleek else 1,
             bevel_angle=math.radians(30.0 if sleek else 40.0))
    if hum and part in LIMB_SHAPES:
        d['roundness'] = 0.97 if sleek else 0.45
    L, W, D = DEFAULTS[part]
    d['bevel_width'] = min(W, D) * (0.02 if sleek else 0.05)
    return d


def create_part(context, part, category, style, seed=1, variation=0.5, details=True, side='CENTER',
                location=None, scale=1.0, name=None):
    L, W, D = DEFAULTS[part]
    if category == 'INDUSTRIAL':
        W, D = W * 1.12, D * 1.12
    me = bpy.data.meshes.new(name or f'Robot_{part.title()}')
    ob = bpy.data.objects.new(me.name, me)
    coll = bpy.data.collections.get(COLL)
    if coll is None:
        coll = bpy.data.collections.new(COLL)
        context.scene.collection.children.link(coll)
    coll.objects.link(ob)
    ob.location = location if location is not None else context.scene.cursor.location.copy()
    rp = ob.mch_robot
    rp.live = False
    rp.part, rp.category, rp.style, rp.side = part, category, style, side
    rp.seed, rp.variation, rp.details = seed, variation, details
    rp.length, rp.width, rp.depth = L * scale, W * scale, D * scale
    for k, v in style_defaults(category, style, part).items():
        setattr(rp, k, v * scale if k == 'bevel_width' else v)
    for k, v in LIMB_SHAPES.get(part, {}).items():
        setattr(rp, k, v)
    rp.live = True
    rebuild(ob)
    return ob


# joint layout of a 1.8 m robot: (part, side, location)
BODY = (('TORSO', 'CENTER', (0, 0, 0.95)), ('HEAD', 'CENTER', (0, 0.01, 1.6)),
        ('SHOULDER', 'LEFT', (0.25, 0, 1.47)), ('SHOULDER', 'RIGHT', (-0.25, 0, 1.47)),
        ('UPPER_ARM', 'LEFT', (0.27, 0, 1.44)), ('UPPER_ARM', 'RIGHT', (-0.27, 0, 1.44)),
        ('FOREARM', 'LEFT', (0.27, 0, 1.19)), ('FOREARM', 'RIGHT', (-0.27, 0, 1.19)),
        ('THIGH', 'LEFT', (0.11, 0, 0.93)), ('THIGH', 'RIGHT', (-0.11, 0, 0.93)),
        ('CALF', 'LEFT', (0.11, 0, 0.52)), ('CALF', 'RIGHT', (-0.11, 0, 0.52)),
        ('FOOT', 'LEFT', (0.11, -0.05, 0.02)), ('FOOT', 'RIGHT', (-0.11, -0.05, 0.02)))


def create_body(context, category, style, seed=1, variation=0.5, details=True, scale=1.0):
    origin = context.scene.cursor.location.copy()
    made = []
    for part, side, loc in BODY:
        ob = create_part(context, part, category, style, seed, variation, details, side,
                         origin + Vector(loc) * scale, scale,
                         name=f'Robot_{part.title()}' + ('' if side == 'CENTER' else '_' + side[0]))
        made.append(ob)
    return made


def is_part(ob):
    return ob is not None and ob.type == 'MESH' and getattr(ob, 'mch_robot', None) is not None and ob.mch_robot.live


def active_part(context):
    ob = getattr(context, 'active_object', None)
    return ob if is_part(ob) else None


# -----------------------------------------------------------------------------
# Operators
# -----------------------------------------------------------------------------


class MCH_OT_robot_add(bpy.types.Operator):
    """Add a robot base mesh part (or the whole body) at the 3D cursor"""
    bl_idname = 'mch.robot_add'
    bl_label = 'Add Robot Base'
    bl_options = {'REGISTER', 'UNDO'}
    part: EnumProperty(items=list(PARTS) + [('BODY', 'Whole Body', 'Every part, left and right separate')],
                       default='BODY')

    def execute(self, context):
        st = context.scene.mch_robot_settings
        for o in context.selected_objects:
            o.select_set(False)
        if self.part == 'BODY':
            made = create_body(context, st.category, st.style, st.seed, st.variation, st.details, st.scale)
        else:
            made = [create_part(context, self.part, st.category, st.style, st.seed, st.variation, st.details,
                                scale=st.scale)]
        for o in made:
            o.select_set(True)
        context.view_layer.objects.active = made[0]
        self.report({'INFO'}, f'Robot base: {len(made)} part(s)')
        return {'FINISHED'}


def _targets(context):
    obs = [o for o in context.selected_objects if is_part(o)]
    a = active_part(context)
    if a is not None and a not in obs:
        obs.append(a)
    return obs


class MCH_OT_robot_reroll(bpy.types.Operator):
    """New random shape (next seed) for the selected robot parts"""
    bl_idname = 'mch.robot_reroll'
    bl_label = 'Reroll Robot Part'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(_targets(context))

    def execute(self, context):
        for o in _targets(context):
            o.mch_robot.seed += 1
        return {'FINISHED'}


class MCH_OT_robot_toggle(bpy.types.Operator):
    """Switch style (sleek / rugged), category (humanoid / industrial) or details on the selected parts"""
    bl_idname = 'mch.robot_toggle'
    bl_label = 'Robot Part Option'
    bl_options = {'REGISTER', 'UNDO'}
    option: EnumProperty(items=[('STYLE', 'Style', ''), ('CATEGORY', 'Category', ''), ('DETAILS', 'Details', ''),
                                ('BOTTOM', 'Bottom Shape', 'Next bottom end shape'),
                                ('TOP', 'Top Shape', 'Next top end shape')],
                         default='STYLE')

    @classmethod
    def poll(cls, context):
        return bool(_targets(context))

    def execute(self, context):
        for o in _targets(context):
            rp = o.mch_robot
            if self.option == 'DETAILS':
                rp.details = not rp.details
                continue
            if self.option in {'BOTTOM', 'TOP'}:
                prop = 'bottom_shape' if self.option == 'BOTTOM' else 'top_shape'
                setattr(rp, prop, END_IDS[(END_IDS.index(getattr(rp, prop)) + 1) % len(END_IDS)])
                continue
            rp.live = False
            if self.option == 'STYLE':
                rp.style = 'RUGGED' if rp.style == 'SLEEK' else 'SLEEK'
            else:
                rp.category = 'INDUSTRIAL' if rp.category == 'HUMANOID' else 'HUMANOID'
            scale = rp.length / DEFAULTS[rp.part][0]
            for k, v in style_defaults(rp.category, rp.style, rp.part).items():
                setattr(rp, k, v * scale if k == 'bevel_width' else v)
            rp.live = True
            rebuild(o)
        return {'FINISHED'}


class MCH_OT_robot_apply(bpy.types.Operator):
    """Apply: the robot part becomes a plain mesh (bevel applied, no more live changes)"""
    bl_idname = 'mch.robot_apply'
    bl_label = 'Apply Robot Part'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(_targets(context))

    def execute(self, context):
        obs = _targets(context)
        dg = context.evaluated_depsgraph_get()
        for o in obs:
            me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), depsgraph=dg)
            old = o.data
            o.modifiers.clear()
            o.data = me
            me.name = old.name
            o.mch_robot.live = False
            if old.users == 0:
                bpy.data.meshes.remove(old)
        self.report({'INFO'}, f'Applied {len(obs)} robot part(s)')
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# HUD
# -----------------------------------------------------------------------------

HUD_BUTTONS = (('apply', 'CHECKMARK', 'mch.robot_apply', {}, 'Apply'),
               ('reroll', 'FILE_REFRESH', 'mch.robot_reroll', {}, 'New random shape'),
               ('style', 'MOD_BEVEL', 'mch.robot_toggle', {'option': 'STYLE'}, 'Sleek / Rugged'),
               ('category', 'OUTLINER_OB_ARMATURE', 'mch.robot_toggle', {'option': 'CATEGORY'},
                'Humanoid / Industrial'),
               ('details', 'MODIFIER', 'mch.robot_toggle', {'option': 'DETAILS'}, 'Details on / off'),
               ('bottom', 'TRIA_DOWN_BAR', 'mch.robot_toggle', {'option': 'BOTTOM'}, 'Bottom shape'),
               ('top', 'TRIA_UP_BAR', 'mch.robot_toggle', {'option': 'TOP'}, 'Top shape'))
# key, label, prop, lo, hi, kind (LEN: mm, PCT: x100, DEG)
SLIDERS = (('length', 'Length', 'length', 10, 3000, 'LEN'), ('width', 'Width', 'width', 5, 2000, 'LEN'),
           ('depth', 'Thickness', 'depth', 5, 2000, 'LEN'), ('taper', 'Taper', 'taper', -100, 100, 'PCT'),
           ('bulge', 'Bulge', 'bulge', 0, 200, 'PCT'), ('roundness', 'Roundness', 'roundness', 0, 100, 'PCT'),
           ('resolution', 'Resolution', 'resolution', 0, 200, 'PCT'),
           ('variation', 'Randomness', 'variation', 0, 100, 'PCT'),
           ('bevel', 'Bevel', 'bevel_width', 0, 100, 'LEN'), ('bevel_seg', 'Bevel Segments', 'bevel_segments', 1, 12, 'INT'),
           ('bevel_angle', 'Bevel Angle', 'bevel_angle', 1, 180, 'DEG'),
           ('bottom_sides', 'Bottom Sides', 'bottom_sides', 3, 16, 'INT'),
           ('top_sides', 'Top Sides', 'top_sides', 3, 16, 'INT'),
           ('shape_mid', 'Shape Change', 'shape_mid', 5, 95, 'PCT'),
           ('bottom_w', 'Bottom Width', 'bottom_w', 10, 250, 'PCT'),
           ('bottom_d', 'Bottom Thickness', 'bottom_d', 10, 250, 'PCT'),
           ('taper_start', 'Taper Start', 'taper_start', 0, 95, 'PCT'),
           ('bulge_pos', 'Bulge Position', 'bulge_pos', 5, 95, 'PCT'),
           ('bulge_offset', 'Bulge Front/Back', 'bulge_offset', -100, 100, 'PCT'),
           ('split', 'Muscle Split', 'split', 0, 150, 'PCT'),
           ('groove', 'Groove', 'groove', 0, 150, 'PCT'),
           ('groove_angle', 'Groove Angle', 'groove_angle', -180, 360, 'DEG'),
           ('ridge', 'Ridge', 'ridge', 0, 200, 'PCT'),
           ('ridge_angle', 'Ridge Angle', 'ridge_angle', -180, 360, 'DEG'),
           ('twist', 'Twist', 'twist', -180, 180, 'DEG'),
           ('bow', 'Bend', 'bow', -100, 100, 'PCT'),
           ('bow_angle', 'Bend Direction', 'bow_angle', -180, 360, 'DEG'),
           ('notch', 'Top Notch', 'notch', 0, 30, 'PCT'),
           ('notch_width', 'Notch Width', 'notch_width', 5, 100, 'PCT'),
           ('slant', 'Bottom Slant', 'slant', -60, 60, 'DEG'),
           ('split_angle', 'Split Angle', 'split_angle', -180, 360, 'DEG'),
           ('top_slant', 'Top Slant', 'top_slant', -60, 60, 'DEG'))
LIMB_SLIDERS = ('length', 'width', 'depth', 'bottom_w', 'bottom_d', 'taper_start', 'bulge', 'bulge_pos', 'bulge_offset',
                'split', 'split_angle', 'groove', 'groove_angle', 'ridge', 'ridge_angle', 'twist', 'bow', 'bow_angle', 'notch',
                'notch_width', 'slant', 'top_slant', 'roundness', 'resolution', 'variation', 'bevel', 'bevel_seg', 'bevel_angle',
                'bottom_sides', 'top_sides', 'shape_mid')
OTHER_SLIDERS = tuple(k[0] for k in SLIDERS if k[0] not in LIMB_SLIDERS or k[0] in
                      {'length', 'width', 'depth', 'bulge', 'roundness', 'resolution', 'variation', 'bevel',
                       'bevel_seg', 'bevel_angle', 'bottom_sides', 'top_sides', 'shape_mid'})


def is_limb(rp):
    return rp.category == 'HUMANOID' and rp.part in LIMB_SHAPES


def slider_keys(rp):
    return LIMB_SLIDERS if is_limb(rp) else OTHER_SLIDERS


def slider_spec(context, key, ob=None):
    ob = ob or active_part(context)
    rp = ob.mch_robot
    label, prop, lo, hi, kind = next((l, pr, a, b, k) for kk, l, pr, a, b, k in SLIDERS if kk == key)
    cur = getattr(rp, prop)
    if kind == 'LEN':
        v = int(round(cur * 1000.0))
        return label, v, lo, hi, (lambda val: setattr(rp, prop, val / 1000.0)), f'{label}  {cur:.3f} m'
    if kind == 'DEG':
        v = int(round(math.degrees(cur)))
        return label, v, lo, hi, (lambda val: setattr(rp, prop, math.radians(val))), f'{label}  {v} deg'
    if kind == 'INT':
        return label, int(cur), lo, hi, (lambda val: setattr(rp, prop, int(val))), f'{label}  {int(cur)}'
    v = int(round(cur * 100.0))
    return label, v, lo, hi, (lambda val: setattr(rp, prop, val / 100.0)), f'{label}  {v} %'


def hud_layout(screen_pts, region_w, region_h, btn=30.0, gap=6.0, slider_w=104.0, slider_h=20.0, keys=None):
    pts = [p for p in screen_pts if p is not None]
    if not pts:
        return {}
    keys = [k[0] for k in SLIDERS] if keys is None else list(keys)
    step = btn + gap
    room = max(slider_h + gap, region_h - step * 3 - btn * 1.5)
    per_col = max(1, int(room // (slider_h + gap)))
    cols = max(1, -(-len(keys) // per_col))
    per_col = -(-len(keys) // cols)
    x = min(max(max(p[0] for p in pts) + btn * 1.2, btn), region_w - (slider_w + gap) * cols - btn)
    total = step * 3 + (slider_h + gap) * per_col
    top = min(max((max(p[1] for p in pts) + min(p[1] for p in pts)) / 2 + total / 2, total), region_h - btn)
    out = {'apply': (x, top)}
    for i, k in enumerate(('reroll', 'style', 'category', 'details')):
        out[k] = (x + i * step, top - step)
    out['bottom'], out['top'] = (x, top - 2 * step), (x + step, top - 2 * step)
    y0 = top - 3 * step
    for i, key in enumerate(keys):
        c, r = divmod(i, per_col)
        out['slider_' + key] = (x - btn / 2 + slider_w / 2 + c * (slider_w + gap),
                                y0 - r * (slider_h + gap) + btn / 2 - slider_h / 2)
    return out


def _hud_current(context):
    from .primitive_hud import anchored, release_anchor
    try:
        from . import tool_state as ts
        if context.mode != 'OBJECT' or not ts.is_mecha_workspace(getattr(context, 'workspace', None)):
            return None, {}
    except (AttributeError, TypeError):
        return None, {}
    ob = active_part(context)
    region, rv3d = context.region, context.region_data
    if ob is None:
        release_anchor('robot')
        return None, {}
    if region is None or rv3d is None:
        return None, {}
    from bpy_extras import view3d_utils
    ui = context.preferences.system.ui_scale
    pts = []
    for c in ob.bound_box:
        q = view3d_utils.location_3d_to_region_2d(region, rv3d, ob.matrix_world @ Vector(c))
        pts.append(None if q is None else (q[0] / ui, q[1] / ui))
    return ob, anchored('robot', ob.name + ('/limb' if is_limb(ob.mch_robot) else ''), region,
                        hud_layout(pts, region.width / ui, region.height / ui, keys=slider_keys(ob.mch_robot)))


class MCH_GT_robot_slider(bpy.types.Gizmo):
    bl_idname = 'MCH_GT_robot_slider'
    __slots__ = ('shape', 'init_x', 'init_value', 'key')

    def setup(self):
        if not hasattr(self, 'shape'):
            from .primitive_hud import _RECT
            self.shape = self.new_custom_shape('TRIS', _RECT)

    def draw(self, context):
        self.draw_custom_shape(self.shape)

    def draw_select(self, context, select_id):
        self.draw_custom_shape(self.shape, select_id=select_id)

    def invoke(self, context, event):
        self.init_x = event.mouse_region_x
        self.init_value = slider_spec(context, self.key)[1]
        return {'RUNNING_MODAL'}

    def modal(self, context, event, tweak):
        from .primitive_hud import slider_value
        spec = slider_spec(context, self.key)
        step = 20.0 if self.key in {'bevel_seg', 'bottom_sides', 'top_sides'} else (
            1.0 if self.key.endswith('angle') or self.key in {'twist', 'slant', 'notch'} else 2.0)
        v = slider_value(self.init_value, event.mouse_region_x - self.init_x, step_px=step, lo=spec[2], hi=spec[3])
        if v != spec[1]:
            spec[4](v)
        if context.area:
            context.area.header_text_set(slider_spec(context, self.key)[5])
        return {'RUNNING_MODAL'}

    def exit(self, context, cancel):
        if context.area:
            context.area.header_text_set(None)
        if cancel:
            slider_spec(context, self.key)[4](self.init_value)
        else:
            try:
                bpy.ops.ed.undo_push(message='Robot ' + self.key)
            except RuntimeError:
                pass


class MCH_GGT_robot_hud(bpy.types.GizmoGroup):
    bl_idname = 'MCH_GGT_robot_hud'
    bl_label = 'Robot Base HUD'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and active_part(context) is not None

    def setup(self, context):
        self.items = {}
        for name, icon, op, props, _label in HUD_BUTTONS:
            gz = self.gizmos.new('GIZMO_GT_button_2d')
            gz.icon = icon
            gz.draw_options = {'BACKDROP', 'OUTLINE'}
            t = gz.target_set_operator(op)
            for k, v in props.items():
                setattr(t, k, v)
            gz.color = (1.0, 0.62, 0.16) if name == 'apply' else (0.17, 0.19, 0.23)
            gz.alpha = 0.92
            gz.color_highlight = (0.32, 0.35, 0.41)
            gz.alpha_highlight = 1.0
            self.items[name] = gz
        for key, *_r in SLIDERS:
            gz = self.gizmos.new(MCH_GT_robot_slider.bl_idname)
            gz.key = key
            gz.color = (0.24, 0.27, 0.32)
            gz.alpha = 0.95
            gz.color_highlight = (0.36, 0.40, 0.47)
            gz.alpha_highlight = 1.0
            gz.use_draw_scale = False
            self.items['slider_' + key] = gz

    def draw_prepare(self, context):
        ob, lay = _hud_current(context)
        ui = context.preferences.system.ui_scale
        for name, gz in self.items.items():
            pos = lay.get(name)
            gz.hide = pos is None
            if pos is None:
                continue
            if name.startswith('slider_'):
                gz.matrix_basis = Matrix.Translation((pos[0] * ui, pos[1] * ui, 0.0)) @ Matrix.Diagonal(
                    (52.0 * ui, 10.0 * ui, 1.0, 1.0))
                continue
            gz.scale_basis = 15.0
            gz.matrix_basis[0][3] = pos[0] * ui
            gz.matrix_basis[1][3] = pos[1] * ui
            if name == 'details' and ob is not None:
                gz.color = (1.0, 0.62, 0.16) if ob.mch_robot.details else (0.17, 0.19, 0.23)


_label_handle = None


def _draw_labels():
    try:
        context = bpy.context
        ob, lay = _hud_current(context)
        if ob is None or not lay:
            return
        import blf
        ui = context.preferences.system.ui_scale
        rp = ob.mch_robot
        blf.size(0, 11 * ui)
        x, y = lay['apply']
        blf.color(0, 1.0, 0.62, 0.16, 1.0)
        blf.position(0, (x + 21) * ui, (y - 4) * ui, 0)
        blf.draw(0, 'Apply')
        x, y = lay['details']
        blf.color(0, 0.85, 0.87, 0.9, 1.0)
        blf.position(0, (x + 21) * ui, (y - 4) * ui, 0)
        cat = dict((a, b) for a, b, _c in CATEGORIES)[rp.category]
        sty = dict((a, b) for a, b, _c in STYLES)[rp.style]
        blf.draw(0, f'{cat} | {sty} | {dict((a, b) for a, b, _c in PARTS)[rp.part]}')
        x, y = lay['top']
        names = dict((a, b) for a, b, _c in END_SHAPES)
        blf.position(0, (x + 21) * ui, (y - 4) * ui, 0)
        blf.draw(0, f'Bottom {names[rp.bottom_shape]}  ->  Top {names[rp.top_shape]}')
        for key, *_r in SLIDERS:
            if 'slider_' + key not in lay:
                continue
            x, y = lay['slider_' + key]
            text = slider_spec(context, key, ob)[5]
            w, _h = blf.dimensions(0, text)
            blf.color(0, 1.0, 1.0, 1.0, 1.0)
            blf.position(0, x * ui - w / 2, (y - 4) * ui, 0)
            blf.draw(0, text)
    except Exception:          # never break viewport drawing
        pass


# -----------------------------------------------------------------------------
# Panel
# -----------------------------------------------------------------------------


def draw(layout, context):
    st = context.scene.mch_robot_settings
    box = layout.box()
    box.label(text='ROBOT BASE MESH', icon='OUTLINER_OB_ARMATURE')
    box.row(align=True).prop(st, 'category', expand=True)
    box.row(align=True).prop(st, 'style', expand=True)
    r = box.row(align=True)
    r.prop(st, 'seed')
    r.prop(st, 'variation', slider=True)
    r = box.row(align=True)
    r.prop(st, 'scale')
    r.prop(st, 'details', toggle=True)
    grid = box.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
    grid.scale_y = 1.2
    for pid, label, _d in PARTS:
        grid.operator('mch.robot_add', text=label).part = pid
    box.operator('mch.robot_add', text='Whole Body (all parts)', icon='OUTLINER_OB_ARMATURE').part = 'BODY'
    ob = active_part(context)
    if ob is not None:
        rp = ob.mch_robot
        sub = box.box()
        sub.label(text=f'LIVE: {ob.name} (until Apply)', icon='OUTLINER_OB_ARMATURE')
        sub.row(align=True).prop(rp, 'category', expand=True)
        sub.row(align=True).prop(rp, 'style', expand=True)
        c = sub.column(align=True)
        limb = is_limb(rp)
        for prop in ('length', 'width', 'depth') + (() if limb else ('taper',)) + ('bulge', 'roundness', 'resolution',
                                                                                  'variation'):
            c.prop(rp, prop, slider=prop in {'roundness', 'variation'})
        if limb:
            c = sub.column(align=True)
            c.label(text='Limb Shape (top = elbow / knee side)')
            for prop in ('bottom_w', 'bottom_d', 'taper_start', 'bulge_pos', 'bulge_offset', 'split', 'split_angle',
                         'groove', 'groove_angle', 'ridge', 'ridge_angle', 'twist', 'bow', 'bow_angle', 'notch',
                         'notch_width', 'slant', 'top_slant'):
                c.prop(rp, prop, slider=True)
        rr = sub.row(align=True)
        rr.prop(rp, 'seed')
        rr.operator('mch.robot_reroll', text='', icon='FILE_REFRESH')
        rr.prop(rp, 'details', toggle=True)
        c = sub.column(align=True)
        c.label(text='End Shapes (bottom -> top)')
        r2 = c.row(align=True)
        r2.prop(rp, 'bottom_shape', text='')
        if rp.bottom_shape == 'POLYGON':
            r2.prop(rp, 'bottom_sides', text='Sides')
        r2 = c.row(align=True)
        r2.prop(rp, 'top_shape', text='')
        if rp.top_shape == 'POLYGON':
            r2.prop(rp, 'top_sides', text='Sides')
        c.prop(rp, 'shape_mid', slider=True)
        c = sub.column(align=True)
        c.prop(rp, 'bevel_width')
        c.prop(rp, 'bevel_segments')
        c.prop(rp, 'bevel_angle')
        a = sub.row()
        a.scale_y = 1.3
        a.operator('mch.robot_apply', text='Apply', icon='CHECKMARK')


class MCH_PT_robot_base(bpy.types.Panel):
    bl_idname = 'MCH_PT_robot_base'
    bl_label = 'Robot Base Mesh'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Mecha Lab'
    bl_order = 70

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, 'mch_robot_settings')

    def draw(self, context):
        draw(self.layout, context)


CLASSES = (MCH_PG_RobotPart, MCH_PG_RobotSettings, MCH_OT_robot_add, MCH_OT_robot_reroll, MCH_OT_robot_toggle,
           MCH_OT_robot_apply, MCH_GT_robot_slider, MCH_GGT_robot_hud, MCH_PT_robot_base)


def register():
    global _label_handle
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Object.mch_robot = bpy.props.PointerProperty(type=MCH_PG_RobotPart)
    bpy.types.Scene.mch_robot_settings = bpy.props.PointerProperty(type=MCH_PG_RobotSettings)
    if not bpy.app.background and _label_handle is None:
        _label_handle = bpy.types.SpaceView3D.draw_handler_add(_draw_labels, (), 'WINDOW', 'POST_PIXEL')


def unregister():
    global _label_handle
    if _label_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_label_handle, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _label_handle = None
    for attr, owner in (('mch_robot', bpy.types.Object), ('mch_robot_settings', bpy.types.Scene)):
        if hasattr(owner, attr):
            delattr(owner, attr)
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
