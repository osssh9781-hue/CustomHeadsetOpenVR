"""0.24.172 Feathers and real scales - light meshes for Feather Line and the Fur tool's Feathers / Scales.

    feathers (user: "깃털 탭도 만들어 줘, 이건 메쉬로 - 가벼운 메쉬, 깃털 모양 프리셋도 15 개 정도, 길이도 다양하게")
        a shaft (the rachis, raised) and two vanes either side, one surface of about 200 faces; the bare quill at the
        base, the vane's outline (where it is widest, the tip round / pointed / square, one vane wider than the
        other), the barbs' fringe along the edge, splits between barb groups, a notch near the tip (a flight
        feather's emargination), curved down / sideways / drooping, cupped across.  Origin at the quill's base, the
        length along +X, the vane's top up (+Z).  Points carry ``mch_feather_t`` (0 base .. 1 tip) for the colour.
    scales (user: "비늘도 좀 더 리얼하게, 지금은 너무 네모 동그라미 이래")
        closed meshes, thickest at the root and thin at the free edge where they overlap: a lizard's keeled scale, a
        fish's cycloid (growth rings) and ctenoid (a toothed back edge), a snake's belly scute, a dragon's shield
        (keel, serrated tip), a pangolin's (grooved, cupped), a crocodile's osteoderm (ridge, pits), a tubercle.
        Origin at the root edge, the free edge along +X.
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

T_ATTR = 'mch_feather_t'
Y_ATTR = 'mch_feather_y'            # (across, in the feather's lengths: the barbs' lines - instanced too)
C_ATTR = 'mch_feather_col'          # 0.24.173 each feather's own colours (a pattern: the kestrel's bands and spots)

# (id, label, spec) - L: length (x the Part Size), W: the widest half-width x L, calamus: the bare quill (share of L),
# widest: where along the vane it is widest, tip: ROUND / POINT / SQUARE, asym: the right vane wider (left narrower),
# fringe: (depth, count) of the barbs' fringe at the edge, splits: gaps between barb groups, notch: (side, at, depth),
# bend / sweep / droop: curved down / sideways / drooping at the tip, cup: the vane's edges down, shaft: the rachis'
# height x W, start: the vane begins this far along (a crest's bare shaft), eye: a round widening at the tip,
# asym_ramp: the asymmetry only from this far along (less at the base), fluff: (depth, up to) downy ragged barbs at the
# vane's base, pattern: its own colours (KESTREL), mirror: the narrow vane on the left (+Y)
FEATHERS = (
    ('CONTOUR', 'Contour', dict(L=0.7, W=0.24, calamus=0.1, widest=0.45, tip='ROUND', cup=0.12, bend=0.05)),
    ('COVERT', 'Covert', dict(L=0.5, W=0.3, calamus=0.08, widest=0.55, tip='ROUND', cup=0.15, bend=0.04)),
    ('PRIMARY', 'Primary', dict(L=1.6, W=0.13, calamus=0.1, widest=0.4, tip='POINT', asym=0.45, bend=0.08,
                                sweep=0.07, notch=('L', 0.62, 0.45), cup=0.06)),
    ('SECONDARY', 'Secondary', dict(L=1.2, W=0.17, calamus=0.1, widest=0.55, tip='SQUARE', asym=0.3, bend=0.06,
                                    cup=0.08)),
    ('TAIL', 'Tail', dict(L=1.4, W=0.12, calamus=0.08, widest=0.7, tip='SQUARE', bend=0.03, cup=0.05)),
    ('DOWN', 'Down', dict(L=0.35, W=0.4, calamus=0.15, widest=0.5, tip='ROUND', fringe=(0.6, 10), cup=0.45,
                          bend=0.15, shaft=0.03)),
    ('PLUME', 'Plume', dict(L=1.5, W=0.32, calamus=0.06, widest=0.6, tip='ROUND', fringe=(0.4, 18), droop=0.35,
                            cup=0.1)),
    ('BLADE', 'Blade', dict(L=1.0, W=0.08, calamus=0.05, widest=0.3, tip='POINT', bend=0.02, cup=0.0, shaft=0.6)),
    ('OWL', 'Owl', dict(L=0.9, W=0.26, calamus=0.08, widest=0.6, tip='ROUND', fringe=(0.2, 16), cup=0.12,
                        bend=0.05)),
    ('NOTCHED', 'Hawk Primary', dict(L=1.6, W=0.14, calamus=0.1, widest=0.35, tip='POINT', asym=0.35, bend=0.09,
                                     notch=('B', 0.55, 0.5), cup=0.06)),
    ('PHEASANT', 'Pheasant Tail', dict(L=2.2, W=0.07, calamus=0.05, widest=0.25, tip='POINT', bend=0.04, sweep=0.03,
                                       cup=0.04)),
    ('CREST', 'Crest', dict(L=0.8, W=0.16, calamus=0.05, start=0.55, widest=0.8, tip='ROUND', fringe=(0.4, 12),
                            bend=-0.12, cup=0.05)),
    ('RIBBON', 'Ribbon', dict(L=1.8, W=0.045, calamus=0.04, widest=0.5, tip='ROUND', wave=(0.35, 6), cup=0.0,
                              bend=0.05)),
    ('PEACOCK', 'Peacock Eye', dict(L=2.0, W=0.06, calamus=0.05, start=0.1, widest=0.85, tip='ROUND', eye=0.2,
                                    fringe=(0.45, 16), droop=0.12, cup=0.05)),
    ('SPLIT', 'Ragged', dict(L=0.8, W=0.22, calamus=0.1, widest=0.5, tip='ROUND', splits=5, fringe=(0.2, 20),
                             cup=0.1, bend=0.06)),
    # 0.24.173 (user's photo: a kestrel's tail feather - "이런 모양 깃털만 하나 추가"): long, the tip blunt and round, the
    # outer vane narrow (less so toward the base), a long bare quill, downy fluff at the vane's base; its own colours
    ('KESTREL', 'Kestrel Tail', dict(L=1.5, W=0.085, calamus=0.12, widest=0.4, tip='SQUARE', asym=0.55, asym_ramp=0.45,
                                     bend=0.03, sweep=0.015, cup=0.05, fluff=(0.55, 0.2),
                                     pattern='KESTREL', mirror=True)),
)
FEATHER_IDS = tuple(f[0] for f in FEATHERS)


def _vane_width(u, spec):
    """The vane's half-width (0..1 of its widest) at ``u`` (0 the vane's start .. 1 the tip)."""
    w0 = spec.get('widest', 0.5)
    if u <= w0:
        base = (u / max(w0, 1e-6)) ** 0.45
    else:
        v = (u - w0) / max(1.0 - w0, 1e-6)
        tip = spec.get('tip', 'ROUND')
        if tip == 'POINT':
            base = max(0.0, 1.0 - v) ** 0.85
        elif tip == 'SQUARE':
            base = 1.0 if v < 0.75 else math.sqrt(max(0.0, 1.0 - ((v - 0.75) / 0.25) ** 2))
        else:
            base = math.sqrt(max(0.0, 1.0 - v * v))
    eye = spec.get('eye', 0.0)
    if eye > 0:                                       # (a peacock's eye: the vane narrow, widening round at the tip)
        base = 0.35 * base + eye / max(spec['W'], 1e-6) * math.exp(-((u - 0.88) / 0.1) ** 2)
    wave = spec.get('wave')
    if wave:
        base *= 1.0 + wave[0] * math.sin(u * wave[1] * 2 * math.pi)
    return max(base, 0.0)


def _ss(e0, e1, x):
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0) if e1 != e0 else float(x >= e0)
    return t * t * (3.0 - 2.0 * t)


def _mix(c0, c1, f):
    return tuple(a + (b - a) * f for a, b in zip(c0, c1))


# colours in linear (a natural brown by default: dark at the base, lighter to the tip)
_BROWN = ((0.03, 0.022, 0.015), (0.11, 0.07, 0.04), (0.3, 0.22, 0.14))
_K_WHITE, _K_BLACK = (0.72, 0.68, 0.6), (0.012, 0.01, 0.009)
_K_RUFOUS, _K_PALE, _K_QUILL = (0.52, 0.19, 0.075), (0.62, 0.36, 0.2), (0.62, 0.55, 0.4)


def feather_colour(pattern, x, u, a):
    """The colour at ``x`` (0 the quill's end .. 1 the tip), ``u`` (along the vane, < 0 the bare quill), ``a`` (-1 the
    outer vane's edge .. 0 the shaft .. +1 the inner's)."""
    if pattern != 'KESTREL':
        return _mix(_BROWN[0], _BROWN[1], x / 0.45) if x < 0.45 else _mix(_BROWN[1], _BROWN[2], (x - 0.45) / 0.55)
    if u < 0:
        return _K_QUILL
    # the inner vane rufous (paler by the shaft), the base downy white
    c = _mix(_K_RUFOUS, _K_PALE, 1.0 - _ss(0.0, 0.25, abs(a)))
    if a < 0:                                         # (the outer vane: rufous low, white with black spots higher)
        w = _ss(0.36, 0.40, u)
        c = _mix(c, _K_WHITE, w)
        for su, r in ((0.43, 0.03), (0.56, 0.045)):               # (two black spots on it, roundish)
            d = math.hypot((u - su) / r, (a + 0.7) / 0.6)
            c = _mix(c, _K_BLACK, 1.0 - _ss(0.6, 1.15, d))
    c = _mix(c, _K_WHITE, 1.0 - _ss(0.04, 0.16, u))  # (downy white at the base)
    band = 0.70 + 0.04 * a if a >= 0 else 0.62       # (the black band near the tip, lower on the outer vane)
    c = _mix(c, _K_BLACK, _ss(band - 0.012, band + 0.012, u))
    tip = 0.925 + 0.02 * (1.0 - a * a)               # (the white tip, its edge curved)
    c = _mix(c, _K_WHITE, _ss(tip - 0.01, tip + 0.01, u))
    return c


def feather_mesh(spec, name='Feather', seed=1):
    """One feather (see the module) as a new mesh."""
    rng = random.Random(seed)
    L, W = 1.0, spec['W']                             # (unit length: the preset's L is set by the object's scale)
    fr = spec.get('fringe')
    ns = max(26, int(fr[1] * 2.2) + 4) if fr else 26  # (along: enough rows for the fringe's teeth; across each vane)
    nw = 4
    pattern = spec.get('pattern')
    if pattern:                                       # (a coloured pattern: rows enough for its bands and spots)
        ns, nw = 90, 6
    cal = spec.get('calamus', 0.08)
    start = max(cal, spec.get('start', 0.0))
    asym = spec.get('asym', 0.0)
    side = {'L': 1.0 - asym, 'R': 1.0 + asym * 0.6}
    ramp = spec.get('asym_ramp', 0.0)
    fluff = spec.get('fluff')
    fringe = spec.get('fringe')
    notch = spec.get('notch')
    splits = sorted(rng.uniform(0.25, 0.85) for _ in range(spec.get('splits', 0)))
    shaft_h = W * spec.get('shaft', 0.25)
    bm = bmesh.new()
    lt = bm.verts.layers.float.new(T_ATTR)
    ly = bm.verts.layers.float.new(Y_ATTR)
    lc = bm.verts.layers.float_color.new(C_ATTR)
    rows = []
    for i in range(ns + 1):
        x = i / ns
        u = (x - start) / max(1.0 - start, 1e-6)       # (along the vane)
        row = []
        for j in range(-nw, nw + 1):
            a = j / nw                                  # (-1 left edge .. 0 the shaft .. +1 right edge)
            sd = 'L' if a < 0 else 'R'
            if u < 0:                                   # (the bare quill: a thin strip)
                half = W * 0.06 * (1.0 - x / max(start, 1e-6) * 0.3)
            else:
                if ramp > 0:                            # (the outer vane narrow from ``ramp`` on, wider at the base)
                    k = 0.45 + 0.55 * min(1.0, u / ramp)
                    half = W * _vane_width(u, spec) * (1.0 - asym * k if sd == 'L' else 1.0 + asym * 0.6 * k)
                else:
                    half = W * _vane_width(u, spec) * side[sd]
                if fluff is not None and u < fluff[1] and abs(a) > 0.3:    # (downy barbs at the base: ragged)
                    half *= 1.0 - fluff[0] * (1.0 - u / fluff[1]) * rng.random() * (abs(a) - 0.3) / 0.7
                if notch is not None and notch[0] in (sd, 'B'):
                    half *= 1.0 - notch[2] * max(0.0, 1.0 - abs(u - notch[1]) / 0.12)
                if fringe is not None and abs(a) > 0.5:       # (the barbs' fringe: teeth toward the tip)
                    saw = (u * fringe[1] + (0.5 if sd == 'L' else 0.0)) % 1.0
                    half *= 1.0 - fringe[0] * ((abs(a) - 0.5) / 0.5) * saw
                half = max(half, W * 0.02)
            y = a * half
            z = -spec.get('cup', 0.1) * (a * a) * half      # (the vane's edges down: cupped)
            if j == 0:
                z += shaft_h * (1.0 - 0.7 * x)              # (the shaft raised)
            # curved along its length: down (bend), sideways (sweep), drooping at the tip (droop)
            z += -spec.get('bend', 0.0) * x * x - spec.get('droop', 0.0) * x ** 3
            y += spec.get('sweep', 0.0) * x * x
            if spec.get('mirror'):                      # (the narrow vane on the other side, as in the photo)
                y = -y
            v = bm.verts.new((x * L, y, z))
            v[lt] = x
            v[ly] = y / L
            v[lc] = (*feather_colour(pattern, x, u, a), 1.0)
            row.append(v)
        rows.append(row)
    gap_rows = set()
    for sp in splits:                                    # (a split between barb groups: a row of faces left out)
        i = int(round((start + sp * (1.0 - start)) * ns))
        gap_rows.add((min(max(i, 1), ns - 1), 'L' if rng.random() < 0.5 else 'R'))
    for i in range(ns):
        for j in range(2 * nw):
            sd = 'L' if j < nw else 'R'
            if (i, sd) in gap_rows and (j < nw - 1 or j > nw):
                continue
            bm.faces.new((rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if bm.faces and sum(f.normal.z for f in bm.faces) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me['mch_shape'] = 'FEATHER'
    return me


# ---- scales ---------------------------------------------------------------------------------------------------------
# (id, label, spec) - L / W: length (root to free edge) / width, H: thickness at the root, tip: ROUND / POINT / KITE /
# RECT, keel: a ridge along the middle (x H), rings: growth rings (count), teeth: a toothed free edge (count),
# grooves: grooves along it at the free edge (count), pits: dimples (strength), cup: the middle lower than the sides,
# cone: a cone (a tubercle), root_flat: the root edge (under the one before) straight, with ``lobes`` scallops;
# tip LEAF: wider toward the free edge, a small point there; HEX: a six-sided bead
SCALES = (
    ('KEELED', 'Keeled', dict(L=1.0, W=0.55, H=0.16, tip='POINT', keel=0.6)),
    ('CYCLOID', 'Cycloid (fish)', dict(L=1.0, W=0.95, H=0.08, tip='ROUND', rings=9, root_flat=0.32, lobes=4)),
    ('CTENOID', 'Ctenoid (fish)', dict(L=1.0, W=0.9, H=0.09, tip='ROUND', rings=7, teeth=11, root_flat=0.3, lobes=5)),
    ('VENTRAL', 'Belly Scute', dict(L=0.42, W=1.0, H=0.07, tip='RECT', bevel=0.25)),
    ('DRAGON', 'Dragon', dict(L=1.0, W=0.75, H=0.24, tip='KITE', keel=0.9, teeth=5)),
    ('PANGOLIN', 'Pangolin', dict(L=1.0, W=0.95, H=0.12, tip='LEAF', grooves=9, cup=0.35, root_flat=0.38)),
    ('OSTEODERM', 'Osteoderm', dict(L=0.8, W=0.62, H=0.22, tip='RECT', keel=0.7, pits=0.25, bevel=0.35)),
    ('TUBERCLE', 'Tubercle', dict(L=0.6, W=0.6, H=0.4, tip='HEX', cone=True, pits=0.15)),
)
SCALE_IDS = tuple(s[0] for s in SCALES)


def _outline(t, spec):
    """The scale's outline at angle ``t`` (0 = the free edge, +X): (x, y) about its middle, the length along x."""
    rx, ry = spec['L'] * 0.5, spec['W'] * 0.5
    c, s = math.cos(t), math.sin(t)
    tip = spec.get('tip', 'ROUND')
    if tip == 'RECT':                                 # (a rounded rectangle)
        p = 6.0
        r = 1.0 / ((abs(c) ** p + abs(s) ** p) ** (1.0 / p))
    elif tip == 'HEX':                                # (a six-sided bead, its corners a little round)
        a = (t % (math.pi / 3.0)) - math.pi / 6.0
        r = 1.0 + (math.cos(math.pi / 6.0) / math.cos(a) - 1.0) * 0.8
    else:
        r = 1.0
    x, y = rx * r * c, ry * r * s
    rf = spec.get('root_flat', 0.0)
    if rf and c < 0:                                  # (the root edge, under the scale before: straight, scalloped)
        x = max(x, -rx * (1.0 - rf))
        if x <= -rx * (1.0 - rf) + 1e-9:
            x -= rx * 0.07 * abs(math.sin((y / ry) * spec.get('lobes', 4) * math.pi * 0.5))
            y *= 1.0 + 0.08 * rf
    if tip == 'LEAF':                                 # (wider toward the free edge, a small point there)
        y *= 1.0 + 0.16 * c
        if c > 0:
            x *= 1.0 + 0.14 * c ** 10
    if tip == 'POINT' and c > 0:                      # (drawn to a point at the free edge)
        y *= 1.0 - 0.75 * c ** 2.5
    elif tip == 'KITE':                               # (a shield: broad at the root, a point at the free edge)
        y *= (1.0 - 0.8 * max(c, 0.0) ** 1.6) * (1.0 + 0.15 * max(-c, 0.0))
        x *= 1.0 + 0.15 * max(c, 0.0)
    teeth = spec.get('teeth', 0)
    if teeth and c > 0.35:                            # (a toothed free edge)
        k = (t / (2 * math.pi) * teeth * 4) % 1.0
        f = 1.0 - 0.08 * abs(2.0 * k - 1.0) * (c - 0.35) / 0.65
        x, y = x * f, y * f
    return x, y


def scale_mesh(spec, name='Scale', seg=36, rings=11, seed=1):
    """One scale (see the module) as a new closed mesh: a top surface over the outline, a flat bottom."""
    rng = random.Random(seed)
    H = spec['H']
    L = spec['L']
    bm = bmesh.new()
    pits = [(rng.uniform(-0.4, 0.4) * L, rng.uniform(-0.35, 0.35) * spec['W'], rng.uniform(0.04, 0.08) * L)
            for _ in range(10)] if spec.get('pits') else []

    def height(x, y, s):
        """The top's height over the bottom at (x, y) (about the middle), ``s`` 0 at the outline .. 1 the middle."""
        u = (x / L) + 0.5                              # (0 the root .. 1 the free edge)
        if spec.get('cone'):
            z = H * s ** 1.4
        else:
            z = H * (1.0 - 0.75 * u) * (1.0 - (1.0 - s) ** 2.2)      # (thick at the root, thin at the free edge)
            z *= 1.0 - spec.get('bevel', 0.0) * (1.0 - s) ** 3
        keel = spec.get('keel', 0.0)
        if keel:                                        # (a ridge along the middle, sharp-topped, rising to the free edge)
            z += H * keel * 0.55 * math.exp(-abs(y) / (spec['W'] * 0.06)) * (1.0 - (1.0 - s) ** 2) * (0.3 + 0.7 * u)
        cup = spec.get('cup', 0.0)
        if cup:
            z -= H * cup * math.exp(-(y / (spec['W'] * 0.3)) ** 2) * s * u
        rn = spec.get('rings', 0)
        if rn:                                          # (growth rings round the root, the grooves from it fanning out)
            rr = math.hypot(x + L * 0.5, y) / L
            z += H * 0.22 * (abs(math.sin(rr * rn * math.pi)) - 0.5) * min(1.0, s * 3.0)
            ang = math.atan2(y, x + L * 0.5)
            if u > 0.55:
                z -= H * 0.25 * max(0.0, math.cos(ang * 9.0)) ** 6 * (u - 0.55) / 0.45 * min(1.0, s * 3.0)
        gr = spec.get('grooves', 0)
        if gr and u > 0.35:                             # (grooves along it toward the free edge)
            z -= H * 0.35 * max(0.0, math.sin(y / spec['W'] * gr * math.pi)) ** 2 * (u - 0.35) / 0.65 * min(1.0, s * 3.0)
        for px, py, pr in pits:
            d = math.hypot(x - px, y - py)
            if d < pr:
                z -= H * spec['pits'] * (1.0 - d / pr) ** 2 * s
        return max(z, 0.0) + H * 0.02
    wob = [rng.uniform(-1.0, 1.0) for _ in range(5)]
    outline = []
    for k in range(seg):                                 # (a little uneven, as a grown scale is)
        t = 2 * math.pi * k / seg
        ox, oy = _outline(t, spec)
        f = 1.0 + 0.035 * sum(w * math.sin((i + 2) * t + i) for i, w in enumerate(wob)) / 2.0
        outline.append((ox * f, oy * f))
    grid = []
    for r in range(rings):                             # (rings from the outline in toward the middle)
        s = r / rings
        ring = []
        for (ox, oy) in outline:
            x, y = ox * (1.0 - s), oy * (1.0 - s)
            ring.append(bm.verts.new((x, y, height(x, y, s))))
        grid.append(ring)
    top = bm.verts.new((0.0, 0.0, height(0.0, 0.0, 1.0)))
    bottom = [bm.verts.new((ox, oy, 0.0)) for (ox, oy) in outline]
    for r in range(rings - 1):
        for k in range(seg):
            a, b = grid[r][k], grid[r][(k + 1) % seg]
            c, d = grid[r + 1][(k + 1) % seg], grid[r + 1][k]
            bm.faces.new((a, b, c, d))
    for k in range(seg):
        bm.faces.new((grid[-1][k], grid[-1][(k + 1) % seg], top))
        bm.faces.new((bottom[k], bottom[(k + 1) % seg], grid[0][(k + 1) % seg], grid[0][k]))   # (the rim)
    bm.faces.new(bottom[::-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    x0 = min(ox for ox, _oy in outline)
    bmesh.ops.translate(bm, verts=bm.verts[:], vec=Vector((-x0, 0.0, 0.0)))        # (the root edge at the origin)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me['mch_shape'] = 'SCALE'
    return me


# ---- materials ------------------------------------------------------------------------------------------------------

def feather_material():
    """``MCH Feather``: darker at the base, lighter to the tip (``mch_feather_t``), a little sheen."""
    m = bpy.data.materials.get('MCH Feather')
    if m is not None and m.get('mch_v') == 4:
        return m
    if m is None:
        m = bpy.data.materials.new('MCH Feather')
    m['mch_v'] = 4                                   # (2: the barbs from the feather's own attributes, 3: colours,
    #                                                    4: each feather's own colours - C_ATTR, else the ramp)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    pb = nt.nodes.new('ShaderNodeBsdfPrincipled')
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(pb.outputs[0], out.inputs['Surface'])
    at = nt.nodes.new('ShaderNodeAttribute')
    at.attribute_name, at.attribute_type = T_ATTR, 'GEOMETRY'
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.03, 0.022, 0.015, 1.0)       # (colours in linear: a natural brown,
    ramp.color_ramp.elements[1].color = (0.3, 0.22, 0.14, 1.0)          #  dark at the base, lighter to the tip)
    mid = ramp.color_ramp.elements.new(0.45)
    mid.color = (0.11, 0.07, 0.04, 1.0)
    nt.links.new(at.outputs['Fac'], ramp.inputs['Fac'])
    ac = nt.nodes.new('ShaderNodeAttribute')         # (its own colours where it has them - an older one: the ramp)
    ac.attribute_name, ac.attribute_type = C_ATTR, 'GEOMETRY'
    mx = nt.nodes.new('ShaderNodeMix')
    mx.data_type = 'RGBA'
    sock = {i.identifier: i for i in mx.inputs}
    nt.links.new(ac.outputs['Alpha'], sock['Factor_Float'])
    nt.links.new(ramp.outputs['Color'], sock['A_Color'])
    nt.links.new(ac.outputs['Color'], sock['B_Color'])
    nt.links.new(next(o for o in mx.outputs if o.identifier == 'Result_Color'), pb.inputs['Base Color'])
    pb.inputs['Roughness'].default_value = 0.55
    # the barbs: fine lines from the shaft out toward the tip either side (a V along it) - a bump, no extra mesh
    ay = nt.nodes.new('ShaderNodeAttribute')
    ay.attribute_name, ay.attribute_type = Y_ATTR, 'GEOMETRY'

    def math_(op, a, b=None):
        n = nt.nodes.new('ShaderNodeMath')
        n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, bpy.types.NodeSocket):
                nt.links.new(v, n.inputs[i])
            else:
                n.inputs[i].default_value = v
        return n.outputs[0]
    v = math_('SUBTRACT', at.outputs['Fac'], math_('MULTIPLY', math_('ABSOLUTE', ay.outputs['Fac']), 1.6))
    lines = math_('POWER', math_('ABSOLUTE', math_('SINE', math_('MULTIPLY', v, 380.0))), 0.6)
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.35
    bump.inputs['Distance'].default_value = 0.002
    nt.links.new(lines, bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], pb.inputs['Normal'])
    for sock, v in (('Sheen Weight', 0.15), ('Subsurface Weight', 0.0)):
        try:
            pb.inputs[sock].default_value = v
        except KeyError:
            pass
    m.diffuse_color = (0.3, 0.22, 0.15, 1.0)
    return m


def scale_material():
    m = bpy.data.materials.get('MCH Scale')
    if m is not None and m.get('mch_v') == 2:
        return m
    if m is None:
        m = bpy.data.materials.new('MCH Scale')
    m['mch_v'] = 2                                   # (2: darker, in linear colour)
    m.use_nodes = True
    pb = next(n for n in m.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled')
    pb.inputs['Base Color'].default_value = (0.055, 0.075, 0.03, 1.0)
    pb.inputs['Roughness'].default_value = 0.38
    try:
        pb.inputs['Coat Weight'].default_value = 0.3
    except KeyError:
        pass
    m.diffuse_color = (0.18, 0.24, 0.12, 1.0)
    return m


def feather_meshes():
    """[(name, mesh)] for the 16 feathers (each scaled to its preset length by its object - see ``FEATHER_LENGTHS``)."""
    out = []
    for i, (fid, label, spec) in enumerate(FEATHERS):
        me = feather_mesh(spec, f'Feather {label}', seed=i + 1)
        me.materials.append(feather_material())
        me['mch_shape_id'] = fid
        out.append((f'Feather {label}', me))
    return out


FEATHER_LENGTHS = {fid: spec['L'] for fid, _l, spec in FEATHERS}


def scale_meshes_real():
    out = []
    for i, (sid, label, spec) in enumerate(SCALES):
        me = scale_mesh(spec, f'Scale {label}', seed=i + 3)
        me.materials.append(scale_material())
        me['mch_shape_id'] = sid
        out.append((f'Scale {label}', me))
    return out
