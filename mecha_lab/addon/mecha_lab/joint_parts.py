"""0.24.95 Joints (user: "메카닉 관절 부분도 한 30 개 만들어 줘"): 30 mechanical joint parts - Real Parts' vehicle
**Joints**, read with the AC Style kit (``ac_parts``: outlines pushed, two-view cuts, lathes, cuts, pockets, grids,
spikes, plates, grooves).

* turned (smooth): joint drum, disc stack, rotary hub, ball joint, ball socket, piston, shock absorber, linear
  actuator, hydraulic ram, turntable, shaft coupling, pivot pin, wrist rotator, shoulder rotator, bellows boot, track
  roller
* angular (flat): clevis fork, hinge tongue, knuckle plate, link arm, elbow housing, knee housing, hip block, yoke,
  ankle fork, mount bracket, spine segment, neck segments, servo housing, gear (a smaller one stacked on it)

Turned parts run along the axis named (X: a hinge's pin across the part, Y: a ram front to back, Z: up); forks open
upward (their pin across X)."""
from __future__ import annotations

import math

from . import ac_parts as ac

H = ac.H


def _zig(r_hi, r_lo, a0, a1, n):
    """A ridged run of a lathe profile: ``n`` ridges from ``a0`` to ``a1`` (a coil, the folds of a boot)."""
    out = []
    for i in range(2 * n + 1):
        a = a0 + (a1 - a0) * i / (2 * n)
        out.append((r_hi if i % 2 else r_lo, a))
    return out


def _arc(cx, cy, r, a0, a1, n):
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n))
            for i in range(n + 1)]


def _round_top(w, h, n=6):
    """A side outline: a bar ``w`` wide (y) and ``h`` high (z) to the middle of its round top (a tongue, a lug)."""
    r = w / 2
    return [(-r, 0.0), (r, 0.0)] + _arc(0.0, h, r, 0.0, math.pi, n)[:-1] + [(-r, h)]


def _bone(L, r, t, n=6):
    """A dog-bone side outline: two round ends (radius ``r``) ``L`` apart along y, joined by a bar ``2 t`` high."""
    c = L / 2
    a = math.asin(min(0.95, t / r))
    right = _arc(c, 0.0, r, -math.pi + a, math.pi - a, 2 * n)            # (round the far end, from below to above)
    left = _arc(-c, 0.0, r, a, 2 * math.pi - a, 2 * n)                 # (round the near end, from above to below)
    return right + left


def _gear(n, ro, ri, tw=0.45):
    """A gear outline (x, z): ``n`` flat-topped teeth from ``ri`` to ``ro``."""
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n
        da = math.pi / n
        for ang, r in ((a - da * 0.5, ri), (a - da * tw * 0.5, ro), (a + da * tw * 0.5, ro), (a + da * 0.5, ri)):
            out.append((r * math.cos(ang), 0.35 + r * math.sin(ang)))
    return out


def _hull_pill(r1, z1, r2, z2, n=8):
    """A tapered pill outline (y, z): round ends of radius ``r1`` at height ``z1`` and ``r2`` at ``z2``."""
    pts = _arc(0.0, z1, r1, math.pi, 2 * math.pi, n) + _arc(0.0, z2, r2, 0.0, math.pi, n)
    return ac._hull(pts)


PI = math.pi
# (id, label, description, curved, recipe)
PARTS = (
    # ---- turned
    ('J_DRUM', 'Joint Drum', 'A joint drum round X: flanged ends, a ridge round its middle', True,
     [('lathe', [(0, 0.16), (0.12, 0.16), (0.13, 0.14), (0.2, 0.13), (0.2, 0.05), (0.17, 0.04), (0.17, -0.04),
                 (0.2, -0.05), (0.2, -0.13), (0.13, -0.14), (0.12, -0.16), (0, -0.16)], 'X')]),
    ('J_STACK', 'Disc Stack', 'Bearing discs stacked round X, the widest in the middle', True,
     [('lathe', [(0, 0.2), (0.1, 0.2), (0.1, 0.16), (0.18, 0.16), (0.18, 0.08), (0.12, 0.08), (0.12, 0.04),
                 (0.22, 0.04), (0.22, -0.04), (0.12, -0.04), (0.12, -0.08), (0.18, -0.08), (0.18, -0.16),
                 (0.1, -0.16), (0.1, -0.2), (0, -0.2)], 'X')]),
    ('J_HUB', 'Rotary Hub', 'A stepped rotary hub standing up Z', True,
     [('lathe', [(0, 0.14), (0.06, 0.14), (0.07, 0.12), (0.12, 0.11), (0.13, 0.08), (0.22, 0.07), (0.24, 0.04),
                 (0.24, 0.0), (0, 0.0)], 'Z')]),
    ('J_BALL', 'Ball Joint', 'A ball on a neck over a collar', True,
     [('lathe', [(0, 0.42)] + [(0.14 * math.sin(a), 0.31 + 0.11 * math.cos(a)) for a in
                                (0.5, 0.9, 1.3, 1.7, 2.1, 2.5)] +
       [(0.05, 0.18), (0.05, 0.12), (0.14, 0.11), (0.16, 0.08), (0.16, 0.02), (0.13, 0.0), (0, 0.0)], 'Z')]),
    ('J_SOCKET', 'Ball Socket', 'A ball sitting in a socket cup', True,
     [('lathe', [(0, 0.27), (0.07, 0.26), (0.11, 0.22), (0.12, 0.18), (0.17, 0.17), (0.19, 0.15), (0.19, 0.04),
                 (0.16, 0.0), (0, 0.0)], 'Z')]),
    ('J_PISTON', 'Piston', 'A rod out of a sleeve, front to back (Y)', True,
     [('lathe', [(0, 0.5), (0.04, 0.5), (0.04, 0.12), (0.08, 0.12), (0.09, 0.1), (0.09, -0.42), (0.07, -0.45),
                 (0.07, -0.5), (0, -0.5)], 'Y')]),
    ('J_SHOCK', 'Shock Absorber', 'A rod, a coil round the sleeve, end caps', True,
     [('lathe', [(0, 0.5), (0.03, 0.5), (0.03, 0.26), (0.09, 0.25), (0.09, 0.22)] + _zig(0.105, 0.075, 0.2, -0.3, 6)
       + [(0.09, -0.32), (0.09, -0.4), (0.06, -0.42), (0.06, -0.5), (0, -0.5)], 'Y')]),
    ('J_ACTUATOR', 'Linear Actuator', 'A long sleeve, a thin rod, its end cap', True,
     [('lathe', [(0, 0.55), (0.035, 0.55), (0.035, 0.2), (0.06, 0.2), (0.07, 0.18), (0.07, -0.45), (0.09, -0.47),
                 (0.09, -0.55), (0, -0.55)], 'Y')]),
    ('J_RAM', 'Hydraulic Ram', 'A big cylinder, its gland, a rod, an end knob', True,
     [('lathe', [(0, 0.45), (0.07, 0.45), (0.08, 0.43), (0.08, 0.38), (0.05, 0.37), (0.05, 0.05), (0.12, 0.04),
                 (0.13, 0.02), (0.13, -0.4), (0.15, -0.42), (0.15, -0.48), (0, -0.48)], 'Y')]),
    ('J_TURNTABLE', 'Turntable', 'A wide flat turntable, stepped', True,
     [('lathe', [(0, 0.1), (0.2, 0.1), (0.22, 0.08), (0.3, 0.07), (0.32, 0.04), (0.32, 0.0), (0, 0.0)], 'Z')]),
    ('J_COUPLING', 'Shaft Coupling', 'Two flanges on a shaft, round X', True,
     [('lathe', [(0, 0.25), (0.05, 0.25), (0.05, 0.12), (0.12, 0.12), (0.12, 0.05), (0.08, 0.04), (0.08, -0.04),
                 (0.12, -0.05), (0.12, -0.12), (0.05, -0.12), (0.05, -0.25), (0, -0.25)], 'X')]),
    ('J_PIN', 'Pivot Pin', 'A pin with a head at each end, round X', True,
     [('lathe', [(0, 0.22), (0.09, 0.22), (0.1, 0.2), (0.1, 0.17), (0.05, 0.16), (0.05, -0.16), (0.1, -0.17),
                 (0.1, -0.2), (0.09, -0.22), (0, -0.22)], 'X')]),
    ('J_WRIST', 'Wrist Rotator', 'A short rotator, its waist ringed', True,
     [('lathe', [(0, 0.2), (0.1, 0.2), (0.12, 0.17), (0.12, 0.1), (0.1, 0.08), (0.14, 0.06), (0.14, -0.06),
                 (0.1, -0.08), (0.12, -0.1), (0.12, -0.17), (0.1, -0.2), (0, -0.2)], 'Y')]),
    ('J_ROTATOR', 'Shoulder Rotator', 'A body with a wide mounting flange, round X', True,
     [('lathe', [(0, 0.2), (0.18, 0.2), (0.2, 0.18), (0.2, 0.12), (0.3, 0.11), (0.32, 0.08), (0.32, 0.03),
                 (0.22, 0.02), (0.22, -0.15), (0.18, -0.18), (0, -0.18)], 'X')]),
    ('J_BELLOWS', 'Bellows Boot', 'A folded rubber boot round a joint (Y)', True,
     [('lathe', [(0, 0.34), (0.08, 0.34), (0.08, 0.3)] + _zig(0.13, 0.09, 0.28, -0.28, 5)
       + [(0.08, -0.3), (0.08, -0.34), (0, -0.34)], 'Y')]),
    ('J_ROLLER', 'Track Roller', 'A wheel with two flanges and a hub, round X', True,
     [('lathe', [(0, 0.16), (0.06, 0.16), (0.06, 0.12), (0.22, 0.12), (0.24, 0.1), (0.24, 0.06), (0.2, 0.05),
                 (0.2, -0.05), (0.24, -0.06), (0.24, -0.1), (0.22, -0.12), (0.06, -0.12), (0.06, -0.16),
                 (0, -0.16)], 'X')]),
    # ---- angular
    ('J_CLEVIS', 'Clevis Fork', 'A fork: two lugs, their tops faceted round, a pin boss in each', False,
     [('front', H([(0, 0.15), (0.1, 0.15), (0.1, 0.5), (0.2, 0.5), (0.2, 0.0), (0, 0.0)]), 0.3),
      ('cut', (0, 0.7, 0.7), 0.12), ('cut', (0, -0.7, 0.7), 0.12), ('cut', (0, 0.92, 0.38), 0.05),
      ('cut', (0, -0.92, 0.38), 0.05), ('pocket', (1, 0, 0), 0.35, 0.025), ('mirror',)]),
    ('J_TONGUE', 'Hinge Tongue', 'A tongue with a round end, a pin boss on each side', False,
     [('side', _round_top(0.24, 0.32), 0.12), ('spike', (1, 0, 0), (1, 0.5, 0.8), 0.04, 0.45, (0.0, 0.0, 0.06)),
      ('mirror',), ('cutpair', (0.7, 0, -0.7), 0.06)]),
    ('J_KNUCKLE', 'Knuckle Plate', 'A tapered plate: a big round end and a small one, recessed', False,
     [('side', _hull_pill(0.16, 0.0, 0.1, 0.45), 0.1), ('pocket', (1, 0, 0), 0.3, 0.02), ('mirror',)]),
    ('J_LINK', 'Link Arm', 'A dog-bone link: round ends, a recess along it', False,
     [('side', _bone(0.7, 0.11, 0.06), 0.08), ('pocket', (1, 0, 0), 0.3, 0.015), ('mirror',)]),
    ('J_ELBOW_H', 'Elbow Housing', 'An angular housing over an elbow: a plate on its outside, a groove', False,
     [('xs', [(0.0, 0.0), (0.14, 0.04), (0.2, 0.18), (0.16, 0.32), (0.0, 0.38), (-0.16, 0.32), (-0.22, 0.16),
              (-0.14, 0.04)],
       [(-0.12, 0.0), (0.12, 0.0), (0.16, 0.2), (0.12, 0.38), (-0.12, 0.38), (-0.16, 0.2)], None),
      ('armor', (1, 0, 0), (1, 0.5, 0.5), 0.6, 0.04, 1.1, 0.04), ('slot', (0, 1, 0), None, (0, 0, 1), 0.5, 0.08,
                                                                       0.02)]),
    ('J_KNEE_H', 'Knee Housing', 'A knee housing: a cap jutting forward, side caps', False,
     [('xs', [(-0.16, 0.0), (0.12, 0.0), (0.22, 0.12), (0.24, 0.26), (0.12, 0.4), (-0.12, 0.4), (-0.2, 0.22)],
       [(-0.14, 0.0), (0.14, 0.0), (0.17, 0.2), (0.12, 0.4), (-0.12, 0.4), (-0.17, 0.2)], None),
      ('spike', (0, 1, 0), (0.5, 1, 0.5), 0.08, 0.4, (0.0, 0.0, 0.03)),
      ('raise', (1, 0, 0), (1, 0.5, 0.5), 0.25, 0.04), ('mirror',)]),
    ('J_HIP', 'Hip Block', 'A hip block: side ears, an axle boss out of each', False,
     [('front', H([(0, 0.3), (0.18, 0.3), (0.22, 0.26), (0.34, 0.24), (0.36, 0.2), (0.36, 0.06), (0.34, 0.02),
                   (0.22, 0.0), (0, 0.0)]), 0.3),
      ('spike', (1, 0, 0), (1, 0.5, 0.45), 0.06, 0.6, (0.0, 0.0, 0.0)), ('mirror',),
      ('cut', (0, 0.7, 0.7), 0.15), ('slot', (0, 1, 0), None, (1, 0, 0), 0.5, 0.06, 0.02)]),
    ('J_YOKE', 'Yoke', 'A universal-joint yoke: a fork on a shaft', False,
     [('front', H([(0, 0.35), (0.06, 0.35), (0.06, 0.6), (0.16, 0.6), (0.16, 0.25), (0.05, 0.18), (0.05, 0.0),
                   (0, 0.0)]), 0.18),
      ('cut', (0, 0.7, 0.7), 0.06), ('cut', (0, -0.7, 0.7), 0.06), ('cutpair', (0.7, 0.7, 0), 0.08),
      ('cutpair', (0.7, -0.7, 0), 0.08)]),
    ('J_ANKLE_F', 'Ankle Fork', 'A deep fork flaring to a wide base', False,
     [('front', H([(0, 0.2), (0.08, 0.2), (0.08, 0.55), (0.17, 0.55), (0.2, 0.1), (0.26, 0.0), (0, 0.0)]), 0.35),
      ('cut', (0, 0.7, 0.7), 0.1), ('cut', (0, -0.7, 0.7), 0.1), ('pocket', (1, 0, 0.2), 0.3, 0.02),
      ('mirror',)]),
    ('J_BRACKET', 'Mount Bracket', 'An L bracket: bolt holes in its foot and its upright', False,
     [('side', [(-0.25, 0.0), (0.25, 0.0), (0.25, 0.06), (-0.17, 0.06), (-0.17, 0.4), (-0.25, 0.4)], 0.3),
      ('grid', (0, 0, 1), 2, 1, 0.3, 0.02), ('grid', (0, 1, 0), 1, 2, 0.3, 0.02),
      ('cutpair', (0.7, 0, 0.7), 0.05)]),
    ('J_SPINE', 'Spine Segment', 'A vertebra-like segment: a body, two wings', False,
     [('front', H([(0, 0.3), (0.05, 0.3), (0.08, 0.2), (0.3, 0.16), (0.32, 0.1), (0.12, 0.06), (0.1, 0.0),
                   (0, 0.0)]), 0.18),
      ('cutpair', (0.5, 0.86, 0), 0.08), ('cut', (0, 0.6, 0.8), 0.08)]),
    ('J_NECK', 'Neck Segments', 'Stacked octagonal rings, a neck or a waist', False,
     [('loftz', ac._OCT, [(0.0, 1.0), (0.08, 1.0), (0.1, 0.78), (0.18, 0.78), (0.2, 1.0), (0.28, 1.0),
                          (0.3, 0.78), (0.38, 0.78), (0.4, 1.0), (0.48, 1.0)])]),
    ('J_SERVO', 'Servo Housing', 'A box, an output boss on one side, vents', False,
     [('front', H([(0, 0.3), (0.2, 0.3), (0.2, 0.0), (0, 0.0)]), 0.25),
      ('spike', (1, 0, 0), (1, 0.5, 0.55), 0.08, 0.55, (0.0, 0.0, 0.0)), ('grid', (0, 1, 0), 3, 1, 0.25, 0.015),
      ('cutpair', (0.7, 0.7, 0), 0.05)]),
    ('J_GEAR', 'Gear', 'A gear: twelve teeth, a smaller gear stacked on its face', False,
     [('front', _gear(12, 0.3, 0.25), 0.1), ('spike', (0, 1, 0), None, 0.05, 0.5, (0.0, 0.0, 0.0))]),
)
SPECS = {p[0]: p[4] for p in PARTS}
CURVED = {p[0] for p in PARTS if p[3]}


def defaults(part):
    return ac.defaults(part)


def build(bm, part, d, level, segs):
    return ac.build(bm, part, d, level, segs, SPECS)
