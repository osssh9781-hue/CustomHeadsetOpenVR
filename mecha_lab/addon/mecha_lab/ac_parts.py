"""0.24.95 AC Style parts (user: "아머드 코어 스타일 에셋도 50 개 만들어 줘"): 50 modular mech parts in the style of the
Armored Core games - angular layered armour, slits, boosters, weapons - base shapes of the kind, none of its machines
copied.  Real Parts' vehicle **AC Style**.

Each part is a short recipe (``SPECS``) for a small kit of steps, read in order:

* ``side`` outline (y forward, z up) pushed across X; ``front`` outline (x, z) pushed along Y; ``plan`` outline (x, y)
  pushed up Z (its top ``taper`` times as big); ``loft`` / ``loftz`` one ring scaled at stations along Y / Z (each
  face flat); ``lathe`` a profile turned round X / Y / Z; ``plate`` a thin outline facing the front, bent (``folds``)
* ``cut`` / ``cutpair`` a flat cut (a pair: mirrored across X), ``pocket`` the face looking that way inset and pushed
  in (a visor, a hatch, a muzzle), ``grid`` that face split into n x m cells each pushed in (missile tubes, vents,
  lenses), ``mirror`` the left half made the right one's mirror

A summon moves the part's proportions (``sx`` / ``sy`` / ``sz``), its cuts and its pockets a little - Variations more.
"""
from __future__ import annotations

import math

import bmesh
from mathutils import Matrix, Vector


def H(right):
    """A symmetric outline from its right half (x >= 0, top of the centre line round to its bottom)."""
    from . import random_shapes as rs              # (made at import: ``ref_parts`` imports this module)
    return rs._clean([tuple(q) for q in right] + [(-x, y) for x, y in reversed(right)])


def _ring(n, rx, ry, a0=0.0):
    return [(rx * math.cos(a0 + 2 * math.pi * i / n), ry * math.sin(a0 + 2 * math.pi * i / n)) for i in range(n)]


def _stadium(L, h, n=8):
    """A side outline with round ends (a track unit)."""
    r = h / 2
    c = L / 2 - r
    pts = [(c + r * math.cos(-math.pi / 2 + math.pi * i / n), r + r * math.sin(-math.pi / 2 + math.pi * i / n))
           for i in range(n + 1)]
    pts += [(-c + r * math.cos(math.pi / 2 + math.pi * i / n), r + r * math.sin(math.pi / 2 + math.pi * i / n))
            for i in range(n + 1)]
    return pts


def _comb(w, base, top, n):
    """A front outline: a block with ``n`` fins standing on it (a radiator)."""
    pts = [(-w / 2, 0.0), (w / 2, 0.0)]
    p = w / n
    for i in range(n):
        x = w / 2 - i * p
        pts += [(x, top), (x - p / 2, top), (x - p / 2, base), (x - p, base)]
    return pts


_OCT = [(0.2 * math.cos(math.pi / 8 + i * math.pi / 4), 0.2 * math.sin(math.pi / 8 + i * math.pi / 4)) for i in range(8)]
_SQ = [(0.12, 0.1), (0.1, 0.12), (-0.1, 0.12), (-0.12, 0.1), (-0.12, -0.1), (-0.1, -0.12), (0.1, -0.12), (0.12, -0.1)]
PI2 = math.pi / 2

# (id, label, description, curved, recipe)
PARTS = (
    # ---- heads
    ('H_SENSOR', 'Sensor Head', 'A wedge head: brow and chin sloped, a visor slit between', False,
     [('plan', H([(0, 0.3), (0.08, 0.3), (0.2, 0.12), (0.2, -0.2), (0.12, -0.3), (0, -0.3)]), 0.22, 0.85),
      ('cut', (0, 0.55, 0.83), 0.18), ('cut', (0, 0.6, -0.8), 0.22), ('pocket', (0, 1, 0), 0.25, 0.04)]),
    ('H_MONO', 'Mono-Eye Head', 'An octagonal head, its top cut, a round-ish eye bay', False,
     [('plan', _OCT, 0.24, 0.8), ('cut', (0, 0.4, 0.92), 0.15), ('pocket', (0, 1, 0), 0.3, 0.05)]),
    ('H_ANTENNA', 'Antenna Head', 'A head with a tall crest blade and a visor', False,
     [('front', H([(0, 0.42), (0.03, 0.42), (0.05, 0.26), (0.16, 0.24), (0.2, 0.12), (0.14, 0), (0, 0)]), 0.36),
      ('cut', (0, 0.6, -0.8), 0.2), ('cutpair', (0.7, 0.7, 0), 0.1), ('pocket', (0, 1, 0), 0.3, 0.03)]),
    ('H_WIDE', 'Wide Visor Head', 'A flat wide head, a long visor band', False,
     [('front', H([(0, 0.2), (0.3, 0.18), (0.34, 0.1), (0.28, 0), (0, 0)]), 0.3), ('cut', (0, 0.7, 0.7), 0.2),
      ('pocket', (0, 1, 0), 0.25, 0.03)]),
    ('H_CREST', 'Crest Head', 'A swept head with a raised crest, cheeks cut', False,
     [('side', [(0.25, 0), (-0.2, 0), (-0.25, 0.15), (-0.12, 0.32), (0, 0.36), (0.1, 0.2), (0.28, 0.12)], 0.3),
      ('cutpair', (0.8, 0.3, 0.5), 0.12), ('pocket', (0, 1, 0.2), 0.3, 0.03)]),
    ('H_BOX', 'Box Head', 'A box head, its corners cut, three lenses', False,
     [('plan', H([(0, 0.2), (0.18, 0.2), (0.18, -0.2), (0, -0.2)]), 0.26, 0.9), ('cutpair', (0.6, 0.8, 0), 0.12),
      ('cut', (0, 0.5, 0.86), 0.12), ('grid', (0, 1, 0), 3, 1, 0.22, 0.03)]),
    # ---- cores
    ('C_LIGHT', 'Light Core', 'A narrow chest, its front keeled, a hatch', False,
     [('front', H([(0, 0.8), (0.22, 0.8), (0.34, 0.62), (0.3, 0.2), (0.16, 0), (0, 0)]), 0.5),
      ('cutpair', (0.6, 0.8, 0), 0.16), ('cut', (0, 0.6, 0.8), 0.1), ('pocket', (0, 1, 0), 0.25, 0.05)]),
    ('C_HEAVY', 'Heavy Core', 'A wide armoured chest, layered front, a deep panel', False,
     [('front', H([(0, 0.9), (0.4, 0.9), (0.5, 0.7), (0.5, 0.25), (0.38, 0), (0, 0)]), 0.7),
      ('cutpair', (0.5, 0.85, 0.2), 0.14), ('cut', (0, 0.7, -0.7), 0.1), ('pocket', (0, 1, 0), 0.22, 0.05)]),
    ('C_MID', 'Mid Core', 'A hexagonal chest, a V keel, a bay', False,
     [('front', H([(0, 0.85), (0.3, 0.85), (0.45, 0.6), (0.42, 0.3), (0.26, 0), (0, 0)]), 0.6),
      ('cutpair', (0.7, 0.7, 0), 0.2), ('cut', (0, 0.6, 0.8), 0.12), ('pocket', (0, 1, 0), 0.2, 0.04)]),
    ('C_HATCH', 'Cockpit Core', 'A chest seen from the side: a sloped hatch in its front', False,
     [('side', [(0.32, 0.1), (-0.3, 0), (-0.32, 0.8), (0, 0.9), (0.3, 0.7), (0.36, 0.4)], 0.8),
      ('cutpair', (0.7, 0.5, 0), 0.12), ('pocket', (0, 1, 0.3), 0.25, 0.05)]),
    ('C_VENT', 'Vent Core', 'A chest with four vent slots across it', False,
     [('front', H([(0, 0.8), (0.35, 0.8), (0.42, 0.5), (0.36, 0), (0, 0)]), 0.55), ('cut', (0, 0.5, 0.86), 0.15),
      ('grid', (0, 1, 0), 4, 1, 0.25, 0.05)]),
    ('C_BACK', 'Core Back Plate', 'A back plate wrapping round, its sides bent', False,
     [('plate', H([(0, 0.8), (0.3, 0.78), (0.42, 0.5), (0.38, 0.1), (0.2, 0), (0, 0)]),
       [(PI2, 0.6, math.radians(25))]), ('mirror',)]),
    # ---- arms
    ('A_UPPER', 'Upper Arm', 'A chamfered square upper arm, its shoulder end cut, a panel', False,
     [('loftz', _SQ, [(0.0, 1.0), (0.8, 0.85)]), ('cut', (0.6, 0, 0.8), 0.1), ('pocket', (1, 0, 0), 0.25, 0.03)]),
    ('A_FORE_L', 'Light Forearm', 'A slim hexagonal forearm, a panel on top', False,
     [('loft', _ring(6, 0.14, 0.12), [(-0.45, 1.0), (0.45, 0.75)]), ('cut', (0, 0.6, 0.8), 0.08),
      ('pocket', (0, 0, 1), 0.3, 0.03)]),
    ('A_FORE_H', 'Heavy Forearm', 'A heavy forearm with an armour hump', False,
     [('side', [(0.45, 0.05), (-0.45, 0), (-0.45, 0.3), (-0.1, 0.38), (0.35, 0.3), (0.48, 0.18)], 0.36),
      ('cutpair', (0.7, 0, 0.7), 0.12), ('cut', (0, 0.8, -0.6), 0.08), ('pocket', (0, 0, 1), 0.25, 0.03)]),
    ('A_SHOULDER', 'Angular Pauldron', 'An angular shoulder block, its outer top cut', False,
     [('side', [(0.35, 0), (0.38, 0.22), (0.2, 0.36), (-0.2, 0.36), (-0.38, 0.2), (-0.36, 0)], 0.4),
      ('cut', (0.7, 0, 0.7), 0.2), ('cut', (0.7, 0.5, 0.5), 0.12)]),
    ('A_ELBOW', 'Elbow Joint', 'A joint drum turned round X', True,
     [('lathe', [(0, 0.15), (0.13, 0.15), (0.17, 0.11), (0.17, -0.11), (0.13, -0.15), (0, -0.15)], 'X')]),
    ('A_HAND', 'Fist Block', 'A fist: a block, its knuckles grooved', False,
     [('front', H([(0, 0.22), (0.14, 0.22), (0.16, 0.1), (0.12, 0), (0, 0)]), 0.24), ('cut', (0, 0.7, 0.7), 0.15),
      ('grid', (0, 1, 0), 4, 1, 0.15, 0.02)]),
    # ---- legs (biped)
    ('L_THIGH', 'Thigh', 'A tapered hexagonal thigh, the knee and hip cut', False,
     [('loftz', _ring(6, 0.18, 0.15), [(0.0, 0.75), (1.0, 1.0)]), ('cut', (0, 0.75, -0.66), 0.14),
      ('cut', (0.6, 0, 0.8), 0.12), ('pocket', (0, 1, 0), 0.2, 0.03)]),
    ('L_KNEE', 'Knee Guard', 'A knee guard: a pointed block', False,
     [('side', [(0.12, 0), (0.18, 0.2), (0.1, 0.42), (-0.05, 0.45), (-0.1, 0.2), (-0.08, 0)], 0.3),
      ('cutpair', (0.7, 0.7, 0), 0.12), ('cut', (0, 0.6, 0.8), 0.08)]),
    ('L_SHIN', 'Shin', 'A long angular shin, a panel down its front', False,
     [('side', [(0.16, 0), (0.2, 0.6), (0.12, 1.0), (-0.14, 1.0), (-0.2, 0.5), (-0.12, 0)], 0.3),
      ('cutpair', (0.7, 0.6, 0), 0.1), ('pocket', (0, 1, 0), 0.2, 0.03)]),
    ('L_FOOT', 'Foot', 'A biped foot: the toe sloped, its corners cut', False,
     [('side', [(-0.4, 0), (0.55, 0), (0.6, 0.1), (0.2, 0.25), (-0.25, 0.3), (-0.45, 0.18)], 0.38),
      ('cutpair', (0.6, 0.8, 0), 0.12), ('cutpair', (0.6, -0.8, 0), 0.06)]),
    ('L_SKIRT', 'Hip Skirt', 'A hip skirt plate wrapping round', False,
     [('plate', H([(0, 0.45), (0.3, 0.42), (0.35, 0.05), (0, 0)]), [(PI2, 0.65, math.radians(28))]), ('mirror',)]),
    ('L_ANKLE', 'Ankle Joint', 'A joint drum with a hub', True,
     [('lathe', [(0, 0.12), (0.08, 0.12), (0.1, 0.09), (0.16, 0.07), (0.16, -0.07), (0.1, -0.09), (0.08, -0.12),
                 (0, -0.12)], 'X')]),
    # ---- reverse joint
    ('R_THIGH', 'RJ Thigh', 'A reverse-joint thigh: a strut leaning forward', False,
     [('side', [(0.1, 0), (0.3, 0.05), (0.05, 0.9), (-0.15, 0.85)], 0.3), ('cutpair', (0.7, 0, 0.7), 0.1)]),
    ('R_SHIN', 'RJ Shin', 'A reverse-joint shin: a strut leaning back', False,
     [('side', [(-0.1, 0), (0.1, 0), (-0.25, 0.95), (-0.45, 0.9)], 0.26), ('cutpair', (0.7, 0.7, 0), 0.1)]),
    ('R_FOOT', 'RJ Foot', 'A reverse-joint foot: a long pointed toe', False,
     [('plan', H([(0, 0.5), (0.08, 0.5), (0.22, 0.2), (0.2, -0.2), (0, -0.25)]), 0.12, 0.85),
      ('cut', (0, 0.6, 0.8), 0.2)]),
    # ---- quad / tank
    ('Q_LEG', 'Quad Leg', 'A tetrapod leg strut', False,
     [('side', [(0, 0), (0.12, 0.05), (0.6, 0.55), (0.55, 0.65), (-0.05, 0.15)], 0.22),
      ('cutpair', (0.7, 0, 0.7), 0.12)]),
    ('T_TREAD', 'Tread Unit', 'A track unit: round ends, a panel on its side', False,
     [('side', _stadium(1.2, 0.35), 0.3), ('pocket', (1, 0, 0), 0.2, 0.03)]),
    ('T_HULL', 'Tank Hull Armor', 'A tank-leg hull: upper and lower front sloped', False,
     [('front', H([(0, 0.4), (0.45, 0.4), (0.55, 0.2), (0.5, 0), (0, 0)]), 0.9), ('cut', (0, 0.3, 0.95), 0.15),
      ('cut', (0, 0.7, -0.7), 0.15)]),
    # ---- boosters
    ('B_BACK', 'Back Booster', 'A booster block, twin nozzles at its back', False,
     [('front', H([(0, 0.5), (0.3, 0.5), (0.38, 0.3), (0.3, 0), (0, 0)]), 0.3),
      ('grid', (0, -1, 0), 2, 1, 0.2, 0.15)]),
    ('B_NOZZLE', 'Thruster Nozzle', 'A bell nozzle turned round Y', True,
     [('lathe', [(0, 0.2), (0.11, 0.2), (0.12, 0.08), (0.15, -0.06), (0.2, -0.22), (0.18, -0.24), (0.13, -0.1),
                 (0.09, 0.0), (0, 0.02)], 'Y')]),
    ('B_SIDE', 'Side Booster Pod', 'A hexagonal pod, a nozzle in its back', False,
     [('loft', _ring(6, 0.12, 0.1), [(-0.4, 0.75), (0.0, 1.0), (0.4, 0.7)]), ('pocket', (0, -1, 0), 0.2, 0.2)]),
    ('B_WING', 'Wing Booster', 'A swept booster wing', False,
     [('plan', [(0, 0.1), (0.8, -0.2), (0.8, -0.32), (0, -0.45)], 0.04, 1.0), ('cut', (0.3, 0.9, 0.5), 0.05)]),
    ('B_OVERED', 'Overed Booster', 'A big booster: six nozzles in its back', False,
     [('front', H([(0, 0.6), (0.5, 0.55), (0.6, 0.3), (0.5, 0), (0, 0)]), 0.35),
      ('grid', (0, -1, 0), 3, 2, 0.2, 0.12)]),
    # ---- weapons (muzzle +Y)
    ('W_RIFLE', 'Rifle', 'A rifle: stock, grip, magazine, barrel', False,
     [('side', [(-0.55, 0), (-0.3, 0.04), (-0.12, 0.04), (-0.14, -0.14), (-0.06, -0.14), (-0.03, 0.04), (0.06, 0.04),
                (0.08, -0.12), (0.15, -0.12), (0.15, 0.04), (0.25, 0.04), (0.25, 0.07), (0.62, 0.07), (0.62, 0.12),
                (0.25, 0.12), (0.22, 0.16), (-0.3, 0.16), (-0.55, 0.12)], 0.07), ('cutpair', (0.8, 0, 0.6), 0.06)]),
    ('W_SHOTGUN', 'Shotgun', 'A shotgun: a thick short barrel, a pump', False,
     [('side', [(-0.5, 0), (-0.28, 0.04), (-0.1, 0.04), (-0.12, -0.12), (-0.04, -0.12), (-0.01, 0.04), (0.22, 0.04),
                (0.24, 0), (0.4, 0), (0.42, 0.05), (0.52, 0.06), (0.52, 0.15), (0.2, 0.15), (0.18, 0.18),
                (-0.28, 0.18), (-0.5, 0.13)], 0.09), ('cutpair', (0.8, 0, 0.6), 0.06)]),
    ('W_GATLING', 'Gatling', 'A rotary gun turned round Y, its bore at the front', True,
     [('lathe', [(0, -0.4), (0.13, -0.4), (0.15, -0.25), (0.13, -0.05), (0.09, 0), (0.09, 0.5), (0.11, 0.52),
                 (0.11, 0.56), (0.06, 0.56), (0.06, 0.45), (0, 0.45)], 'Y')]),
    ('W_BAZOOKA', 'Bazooka', 'A launcher tube, its rear flared, a deep bore', True,
     [('lathe', [(0, -0.55), (0.15, -0.55), (0.12, -0.42), (0.1, -0.3), (0.1, 0.42), (0.13, 0.52), (0.08, 0.52),
                 (0.08, 0.0), (0, 0.0)], 'Y')]),
    ('W_MISSILE', 'Missile Pod', 'A box of six missile tubes', False,
     [('front', H([(0, 0.4), (0.3, 0.4), (0.3, 0), (0, 0)]), 0.45), ('grid', (0, 1, 0), 3, 2, 0.2, 0.15)]),
    ('W_GRENADE', 'Grenade Launcher', 'A fat launcher, a grip, its muzzle bored', False,
     [('side', [(-0.4, 0), (-0.05, 0), (-0.07, -0.13), (0.02, -0.13), (0.04, 0), (0.6, 0), (0.6, 0.24), (0.05, 0.26),
                (-0.4, 0.2)], 0.16), ('pocket', (0, 1, 0), 0.3, 0.25)]),
    ('W_BLADE', 'Laser Blade', 'A handle, an emitter and a blade thinning to its tip', False,
     [('side', [(-0.3, 0), (0, 0), (0.04, 0.03), (0.9, 0.05), (0.96, 0.085), (0.9, 0.12), (0.04, 0.14), (0, 0.17),
                (-0.3, 0.17)], 0.08), ('cutpair', (0.95, 0.3, 0), 0.35)]),
    ('W_PILE', 'Pile Bunker', 'A heavy block, a spike out of its front', False,
     [('side', [(-0.4, 0), (0.2, 0), (0.2, 0.06), (0.55, 0.08), (0.62, 0.1), (0.55, 0.12), (0.2, 0.14), (0.2, 0.2),
                (-0.4, 0.2)], 0.22), ('cutpair', (0.7, 0, 0.7), 0.12)]),
    ('W_SHIELD', 'Shield', 'A shield plate: a ridge down it, its sides bent back', False,
     [('plate', H([(0, 0.8), (0.25, 0.75), (0.32, 0.3), (0.2, 0), (0, -0.06)]),
       [(PI2, 0.7, math.radians(25)), (PI2, 0.0, math.radians(12))]), ('mirror',)]),
    ('W_SNIPER', 'Sniper Rifle', 'A long rifle: a scope on top, a long barrel', False,
     [('side', [(-0.6, 0), (-0.35, 0.04), (-0.18, 0.04), (-0.2, -0.13), (-0.12, -0.13), (-0.09, 0.04), (0, 0.04),
                (0.02, -0.1), (0.08, -0.1), (0.08, 0.04), (0.2, 0.04), (0.2, 0.075), (0.95, 0.075), (0.95, 0.11),
                (0.2, 0.11), (0.18, 0.15), (0.05, 0.15), (0.05, 0.22), (-0.12, 0.22), (-0.12, 0.15), (-0.35, 0.15),
                (-0.6, 0.12)], 0.06)]),
    # ---- back units
    ('U_MISSILE', 'Missile Launcher Unit', 'A back unit: eight tubes in its sloped face', False,
     [('front', H([(0, 0.32), (0.34, 0.32), (0.4, 0.18), (0.36, 0), (0, 0)]), 0.55), ('cut', (0, 0.6, 0.8), 0.2),
      ('grid', (0, 0.6, 0.8), 4, 2, 0.18, 0.1)]),
    ('U_RADAR', 'Radar Dome', 'A radar dome on a short neck', True,
     [('lathe', [(0, 0.3), (0.12, 0.29), (0.22, 0.22), (0.27, 0.1), (0.28, 0), (0.18, 0), (0.1, -0.12), (0, -0.12)],
       'Z')]),
    ('U_CANNON', 'Back Cannon', 'A long cannon on a block, its muzzle bored', False,
     [('side', [(-0.4, 0), (0, 0), (0, 0.07), (0.85, 0.08), (0.85, 0.16), (0, 0.17), (-0.06, 0.26), (-0.4, 0.26)],
       0.22), ('pocket', (0, 1, 0), 0.25, 0.15)]),
    # ---- armour
    ('M_PLATE', 'Armor Plate', 'An armour plate, its top lip bent', False,
     [('plate', [(-0.35, 0), (0.35, 0), (0.42, 0.3), (0.3, 0.55), (-0.32, 0.5)], [(0.0, -0.7, math.radians(25))])]),
    ('M_RADIATOR', 'Radiator Fins', 'A radiator: fins standing on a block', False,
     [('front', _comb(0.8, 0.3, 0.55, 8), 0.35)]),
)
SPECS = {p[0]: p[4] for p in PARTS}
CURVED = {p[0] for p in PARTS if p[3]}


def defaults(_part):
    return dict(sx=1.0, sy=1.0, sz=1.0, cut=1.0, pocket=1.0, thk=0.04)


def _size(bm):
    co = [v.co for v in bm.verts]
    return max(max(c[i] for c in co) - min(c[i] for c in co) for i in range(3)) if co else 1.0


def _grid(bm, direction, n1, n2, frac, depth):
    """The face looking along ``direction`` split into ``n1`` x ``n2`` cells (cuts across it), each pushed in."""
    from . import ref_parts as rp
    f = rp._best_face(bm, direction, 0.9)
    if f is None:
        return
    n = f.normal.copy()
    p0 = f.calc_center_median()
    u = Vector((0.0, 0.0, 1.0)).cross(n)
    if u.length < 0.3:
        u = Vector((1.0, 0.0, 0.0)).cross(n)
    u.normalize()
    v = n.cross(u).normalized()
    du = [(x.co - p0).dot(u) for x in f.verts]
    dv = [(x.co - p0).dot(v) for x in f.verts]
    box = (min(du), max(du), min(dv), max(dv))

    def cells():
        out = []
        for g in bm.faces:
            c = g.calc_center_median() - p0
            if g.normal.dot(n) > 0.999 and abs(c.dot(n)) < 1e-6 and box[0] - 1e-6 <= c.dot(u) <= box[1] + 1e-6 \
                    and box[2] - 1e-6 <= c.dot(v) <= box[3] + 1e-6:
                out.append(g)
        return out
    for axis, cnt, lo, hi in ((u, n1, box[0], box[1]), (v, n2, box[2], box[3])):
        for i in range(1, int(cnt)):
            cs = cells()
            geom = list({e for g in cs for e in g.edges}) + list({x for g in cs for x in g.verts}) + cs
            bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-6, plane_co=p0 + axis * (lo + (hi - lo) * i / cnt),
                                   plane_no=axis)
    cs = cells()
    if not cs:
        return
    w = min((hi - lo) / max(1, c) for lo, hi, c in ((box[0], box[1], n1), (box[2], box[3], n2)))
    bmesh.ops.inset_individual(bm, faces=cs, thickness=frac * w, depth=-abs(depth), use_even_offset=True)


def build(bm, part, d, level, segs):
    """The solid of AC part ``part`` with its numbers ``d`` (``level`` 1: no pockets, 2: no cuts / folds either)."""
    from . import random_shapes as rs
    from . import ref_parts as rp
    sx, sy, sz = d['sx'], d['sy'], d['sz']
    for op in SPECS[part]:
        k = op[0]
        if k == 'side':
            rp._side_solid(bm, [(y * sy, z * sz) for y, z in op[1]], op[2] * sx, -op[2] * sx / 2)
        elif k == 'front':
            rp._front_solid(bm, [(x * sx, z * sz) for x, z in op[1]], op[2] * sy, op[2] * sy / 2)
        elif k == 'plan':
            h = op[2] if op[2] > 0.05 else d['thk']
            rp._plan_solid(bm, [(x * sx, y * sy) for x, y in op[1]], h * sz if op[2] > 0.05 else h, op[3])
        elif k in {'loft', 'loftz'}:
            rings = []
            for t, s in op[2]:
                if k == 'loft':
                    rings.append([(x * s * sx, t * sy, z * s * sz) for x, z in op[1]])
                else:
                    rings.append([(x * s * sx, y * s * sy, t * sz) for x, y in op[1]])
            rp._ring_loft(bm, rings)
        elif k == 'lathe':
            axis = op[2]
            ra = {'X': (0.5 * (sy + sz), sx), 'Y': (0.5 * (sx + sz), sy), 'Z': (0.5 * (sx + sy), sz)}[axis]
            prof = [(r * ra[0], a * ra[1]) for r, a in op[1]]
            if axis == 'Z':
                rp._lathe(bm, prof, segs, 'Y')
                bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=Matrix.Rotation(PI2, 3, 'X'),
                                 verts=list(bm.verts))
            else:
                rp._lathe(bm, prof, segs, axis)
        elif k == 'plate':
            rs._prism(bm, [(x * sx, y * sz) for x, y in op[1]], d['thk'], 1.0, center=False)
            if level < 2:
                for ang, frac, theta in sorted(op[2], key=lambda f: -abs(f[1])):
                    rs._fold(bm, ang, frac, theta)
                rs._split_twisted(bm)
            bmesh.ops.transform(bm, matrix=rs.PLATE_M, verts=list(bm.verts))
        elif k == 'mirror':
            rs.symmetrize(bm)
        elif k == 'cut' and level < 2:
            bm = rs._cut(bm, [*op[1], op[2] * d['cut']], 0.35)
        elif k == 'cutpair' and level < 2:
            bm = rs._cut_pair(bm, [*op[1], op[2] * d['cut']], 0.35)
        elif k == 'pocket' and level < 1:
            rp._inset_push(bm, rp._best_face(bm, op[1], 0.9), op[2], op[3] * d['pocket'] * _size(bm))
        elif k == 'grid' and level < 1:
            _grid(bm, op[1], op[2], op[3], op[4], op[5] * d['pocket'] * _size(bm))
    return bm
