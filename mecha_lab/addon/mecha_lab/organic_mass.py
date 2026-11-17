"""0.24.183 Creature Base Mesh 2 (user: "크리쳐 만들 때 쓸 베이스 메쉬인데 크리쳐 베이스 메쉬 2로 하자 이름은. 이건 내가
라쏘로 그리면 그 형태에 따라서 바위나 비늘, 버섯, 수정 그런 큰 덩어리의 오가닉한 물질 프리셋으로 설정할 수 있는 거야").

Draw an outline: a big organic lump in that shape - seen from where you drew it, its outline is the one you drew -
made of the matter you pick: Rock, Big Scale, Mushroom, Crystal, Coral, Bone, Shell, Lava Rock, Flesh, Ice, Sponge,
Bark.  Live (until Apply / Enter): every slider lays it again.

* the lump: the outline inflated (the Creature Base Mesh's Puff: wide parts thick, thin parts thin), Thickness and
  Back (a flat back for a lump on a wall or a body); a Big Scale a thin curved plate; a Crystal a cluster of six-sided
  crystals from the bottom of the outline out to it;
* then a Geometry Nodes modifier (``MCH Organic``): remeshed evenly (Resolution, Smooth) and the matter's surface -
  Lumps, Detail, and its Pattern (Rock: cracks, Coral: meandering grooves, Bone / Sponge: pores, Flesh: veins,
  Mushroom: gills under the cap and spots on it, Shell: ribs and growth rings, Big Scale: a keel and growth rings,
  Lava: glowing cracks, Bark: long fissures) with Pattern Scale / Width; its own material (two colours).
"""
from __future__ import annotations

import json
import math
import os
import time
import zlib

import bpy
import numpy as np
from bpy.props import EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, PointerProperty
from mathutils import Matrix, Vector

KEY = 'mch_omass'                 # on a live lump: its outline (local 2D) and how it sits (json)
DONE = 'mch_omass_done'
MOD = 'MCH Organic'
RD_ATTR = 'mch_rd'                 # on a lump's points: the distance to the outline (its edge - where the detail is)
TREE = 'MCH Organic'
TREE_VERSION = 6
COLLECTION = None
_BUSY = [False]
# 0.24.190 (user: "크리쳐 베이스 메쉬는 너무 느려 ... 새로 만든 요철 2 번"):
TREE_FILE = os.path.join(os.path.dirname(__file__), 'node_trees', 'omass_tree.blend')   # the node group ready-made
STORED = [True]                    # (a tool that makes that file turns it off: the group built here)
MESH_KEY = 'mch_omass_mesh'        # on a lump: what its base mesh was made from (the same again: not made again)
LIVE_RES = 0.55                    # while a slider is dragged: this share of the Resolution (the full one after)
_PENDING = {}                      # object name -> when its last live change was (its full mesh is still owed)

# (id, label, description, base, slider values, recipe weights, colours (a, b), material look)
#   base: PUFF (inflated lump) | PLATE (a thin curved plate) | CRYSTAL (a cluster)
#   weights: how much of each surface field the matter has (x Lumps / Detail / Pattern)
_F = dict(depth=1.0, back=0.0, lumps=0.0, detail=0.0, pattern=0.0, pattern_scale=1.0, pattern_width=1.0,
          resolution=70, smooth=0)
_FC = ((0.62, 0.6, 0.56), (0.2, 0.18, 0.16))
KINDS = (
    # 0.24.183 big forms (user: "이런 식으로 크게 형태가 들어간 요철로 바리에이션"): the outline kept, a flat bottom, the
    # edges stepped (the accent), the form big - fine texture only when picked (Surface)
    ('SHARD', 'Layered Shard', 'A big slanted top; the far edge falls in steps (like your sample)', 'FORM',
     dict(_F, depth=1.3, count=6, edge_steps=6, edge_width=0.75, jag=0.6, slope=0.4, turn=0.0), dict(), _FC,
     dict(rough=0.6)),
    ('TERRACE', 'Terraces', 'Stepped all round like strata, a flat top', 'FORM',
     dict(_F, depth=0.7, count=6, edge_steps=6, edge_width=1.0, jag=0.7, slope=0.0, turn=0.0), dict(), _FC,
     dict(rough=0.6)),
    ('FACETS', 'Big Facets', 'Cut in big flat facets round a peak, sharp ridges between them', 'FORM',
     dict(_F, depth=1.2, count=7, edge_steps=2, edge_width=0.3, jag=0.4, slope=0.0, turn=0.0), dict(), _FC,
     dict(rough=0.6)),
    ('CREST', 'Crest', 'A sharp ridge along its middle, its sides stepped', 'FORM',
     dict(_F, depth=1.4, count=6, edge_steps=4, edge_width=1.05, jag=0.5, slope=0.0, turn=0.0), dict(), _FC,
     dict(rough=0.6)),
    ('PLATES', 'Overlapping Plates', 'Big plates along its length, each tucked under the next', 'FORM',
     dict(_F, depth=0.8, count=5, edge_steps=3, edge_width=0.5, jag=0.5, slope=0.0, turn=0.0), dict(), _FC,
     dict(rough=0.6)),
    ('BLOCKS', 'Split Blocks', 'Big blocks, each its own height and tilt, deep cracks between', 'FORM',
     dict(_F, depth=0.8, count=7, edge_steps=2, edge_width=0.4, jag=0.5, slope=0.0, turn=0.0), dict(), _FC,
     dict(rough=0.6)),
    ('FOLDS', 'Big Folds', 'Big folds running along its length', 'FORM',
     dict(_F, depth=1.0, count=4, edge_steps=0, edge_width=0.5, jag=0.6, slope=0.0, turn=0.0), dict(), _FC,
     dict(rough=0.6)),
    ('TIERS', 'Tiers', 'A few thick rounded tiers, each set back to one side (a shelf fungus, a carapace)', 'FORM',
     dict(_F, depth=1.0, count=3, edge_steps=0, edge_width=0.25, jag=0.4, slope=0.0, turn=0.0), dict(), _FC,
     dict(rough=0.6)),
    # 0.24.183 (user, with creature figures: "내가 말한 건 이런 크리쳐들의 요철을 말한 거야 ... 오가닉한 표면으로 변환";
    # "너무 잘게 쪼개지는 게 아니라 내가 만든 메쉬의 형태를 유지하면서") creature reliefs: each as big as its pattern,
    # on the shape you drew - the shape kept
    ('BONEFLAKE', 'Bone Flakes', 'A bony carapace: layers lifting toward the tip, sharp edges, a few cracks', 'PUFF',
     dict(depth=0.85, back=0.85, lumps=0.3, detail=0.35, pattern=1.0, pattern_scale=1.0, pattern_width=1.0, count=8,
          resolution=200, smooth=1),
     dict(low=0.3, det=0.3, flake=1.0, crk=0.45), ((0.8, 0.76, 0.68), (0.28, 0.22, 0.17)), dict(rough=0.7)),
    ('KELOID', 'Keloid Plates', 'Lumpy raised plates, deep red cracks between them, wavy ridges on them', 'PUFF',
     dict(depth=0.85, back=0.85, lumps=0.3, detail=0.3, pattern=1.0, pattern_scale=1.0, pattern_width=1.0, count=8,
          resolution=200, smooth=1),
     dict(low=0.3, det=0.25, plate=1.0, wrinkle=0.6), ((0.56, 0.54, 0.53), (0.42, 0.03, 0.05)),
     dict(rough=0.6, plain=('wrinkle',))),
    ('HIDE', 'Rough Hide', 'A monster\'s thick hide: bumps big and small, deep wrinkles', 'PUFF',
     dict(depth=0.85, back=0.85, lumps=0.35, detail=0.5, pattern=1.0, pattern_scale=1.0, pattern_width=1.0, count=8,
          resolution=200, smooth=1),
     dict(low=0.35, det=0.5, bump=1.0, wrinkle=0.8), ((0.3, 0.3, 0.29), (0.09, 0.09, 0.09)), dict(rough=0.75)),
    ('WARTS', 'Warts', 'Round bubbles and warts in clusters', 'PUFF',
     dict(depth=0.85, back=0.85, lumps=0.25, detail=0.15, pattern=1.0, pattern_scale=0.75, pattern_width=1.0, count=8,
          resolution=200, smooth=1),
     dict(low=0.25, det=0.15, bump=1.6), ((0.42, 0.68, 0.34), (0.13, 0.28, 0.11)), dict(rough=0.5, sss=0.1)),
    ('SCALEROWS', 'Scale Rows', 'Rows of overlapping scales hanging down (a tail, a back)', 'PUFF',
     dict(depth=0.85, back=0.85, lumps=0.2, detail=0.2, pattern=1.0, pattern_scale=1.0, pattern_width=1.0, count=8,
          resolution=220, smooth=1),
     dict(low=0.2, det=0.2, shingle=1.0), ((0.33, 0.4, 0.27), (0.07, 0.09, 0.05)), dict(rough=0.45)),
    ('POLYPS', 'Coral Polyps', 'Star-shaped coral cups all over', 'PUFF',
     dict(depth=0.8, back=0.8, lumps=0.25, detail=0.2, pattern=1.0, pattern_scale=1.0, pattern_width=1.0, count=8,
          resolution=220, smooth=1),
     dict(low=0.25, det=0.2, polyp=1.0), ((0.64, 0.52, 0.34), (0.2, 0.12, 0.08)), dict(rough=0.7)),
    ('ROCK', 'Rock', 'A boulder: lumpy, chipped, cracked', 'PUFF',
     dict(depth=0.85, back=0.85, lumps=1.0, detail=1.0, pattern=1.0, pattern_scale=1.0, pattern_width=1.0, count=8,
          resolution=150, smooth=1),
     dict(low=1.0, det=1.0, crk=1.0), ((0.36, 0.34, 0.31), (0.16, 0.15, 0.14)), dict(rough=0.85)),
    ('SCALE', 'Big Scale', 'One big scale: a thick curved plate, a keel down the middle, growth rings', 'PLATE',
     dict(depth=1.0, back=0.4, lumps=0.25, detail=0.4, pattern=1.0, pattern_scale=1.0, pattern_width=1.0, count=8,
          resolution=170, smooth=2),
     dict(low=0.3, det=0.4, keel=1.0, ring=1.0), ((0.28, 0.33, 0.18), (0.1, 0.12, 0.06)), dict(rough=0.4)),
    ('MUSHROOM', 'Mushroom', 'Draw the mushroom (cap and stalk): gills under the cap, spots on it', 'PUFF',
     dict(depth=0.9, back=0.9, lumps=0.25, detail=0.3, pattern=1.0, pattern_scale=1.0, pattern_width=1.0, count=26,
          resolution=170, smooth=2),
     dict(low=0.3, det=0.3, gill=1.0, spot=1.0), ((0.62, 0.1, 0.05), (0.93, 0.88, 0.78)), dict(rough=0.55, sss=0.3)),
    ('CRYSTAL', 'Crystal', 'A crystal cluster: six-sided crystals from the bottom of the outline out to it', 'CRYSTAL',
     dict(depth=1.0, back=1.0, lumps=0.0, detail=0.0, pattern=1.0, pattern_scale=1.0, pattern_width=1.0, count=9,
          resolution=150, smooth=0),
     dict(), ((0.45, 0.2, 0.75), (0.85, 0.75, 1.0)), dict(rough=0.08, glass=0.85, flat=True)),
    ('CORAL', 'Coral', 'Brain coral: a dome of meandering ridges and grooves', 'PUFF',
     dict(depth=0.8, back=0.7, lumps=0.4, detail=0.3, pattern=1.0, pattern_scale=1.0, pattern_width=1.0, count=8,
          resolution=200, smooth=1),
     dict(low=0.15, det=0.2, wave=1.0), ((0.85, 0.62, 0.45), (0.45, 0.25, 0.18)), dict(rough=0.7, sss=0.15)),
    ('BONE', 'Bone', 'A bony lump: smooth, knobbly, small pores', 'PUFF',
     dict(depth=0.9, back=0.9, lumps=0.6, detail=0.3, pattern=0.7, pattern_scale=1.0, pattern_width=1.0, count=8,
          resolution=160, smooth=3),
     dict(low=0.6, det=0.25, pore=0.6), ((0.86, 0.8, 0.66), (0.55, 0.47, 0.34)), dict(rough=0.6, sss=0.1)),
    ('SHELL', 'Shell', 'A shell: ribs fanning out from the bottom of the outline, growth rings', 'PUFF',
     dict(depth=0.55, back=0.35, lumps=0.2, detail=0.3, pattern=1.0, pattern_scale=1.0, pattern_width=1.0, count=14,
          resolution=180, smooth=2),
     dict(low=0.2, det=0.3, rib=1.0, ring=0.6), ((0.88, 0.78, 0.66), (0.55, 0.36, 0.25)), dict(rough=0.35)),
    ('LAVA', 'Lava Rock', 'Cooled lava: ropey folds, glowing cracks', 'PUFF',
     dict(depth=0.8, back=0.8, lumps=1.0, detail=0.7, pattern=1.0, pattern_scale=1.3, pattern_width=0.55, count=8,
          resolution=170, smooth=1),
     dict(low=1.0, det=0.7, crk=1.3), ((0.08, 0.07, 0.07), (0.03, 0.03, 0.03)), dict(rough=0.9, glow=1.0)),
    ('FLESH', 'Veined Flesh', 'A fleshy mass: soft lobes, raised veins', 'PUFF',
     dict(depth=0.9, back=0.9, lumps=1.2, detail=0.25, pattern=1.0, pattern_scale=1.0, pattern_width=1.0, count=8,
          resolution=160, smooth=3),
     dict(low=1.2, det=0.2, vein=1.0), ((0.62, 0.3, 0.3), (0.35, 0.08, 0.12)), dict(rough=0.45, sss=0.4)),
    ('ICE', 'Ice', 'A chunk of ice: big flat facets, see-through', 'PUFF',
     dict(depth=0.85, back=0.85, lumps=0.8, detail=0.0, pattern=0.0, pattern_scale=1.0, pattern_width=1.0, count=8,
          resolution=26, smooth=0),
     dict(low=0.8), ((0.62, 0.82, 0.95), (0.85, 0.95, 1.0)), dict(rough=0.05, glass=0.9, flat=True)),
    ('SPONGE', 'Sponge', 'A sponge: holes all over', 'PUFF',
     dict(depth=0.85, back=0.85, lumps=0.5, detail=0.2, pattern=1.0, pattern_scale=1.5, pattern_width=1.5, count=8,
          resolution=200, smooth=1),
     dict(low=0.5, det=0.2, pore=1.4), ((0.85, 0.7, 0.3), (0.45, 0.33, 0.1)), dict(rough=0.9)),
    ('BARK', 'Bark', 'A knot of bark: long fissures along it (up the outline)', 'PUFF',
     dict(depth=0.85, back=0.85, lumps=0.5, detail=0.6, pattern=1.0, pattern_scale=1.0, pattern_width=1.0, count=8,
          resolution=170, smooth=1),
     dict(low=0.5, det=0.6, bark=1.0), ((0.3, 0.22, 0.15), (0.1, 0.07, 0.05)), dict(rough=0.9)),
)
KIND = {k[0]: k for k in KINDS}
KIND_ITEMS = [(k[0], k[1], k[2]) for k in KINDS]
PATTERN_NAME = {'ROCK': 'Cracks', 'SCALE': 'Keel / Rings', 'MUSHROOM': 'Gills / Spots', 'CRYSTAL': 'Crystal Size',
                'CORAL': 'Grooves', 'BONE': 'Pores', 'SHELL': 'Ribs / Rings', 'LAVA': 'Glowing Cracks',
                'FLESH': 'Veins', 'ICE': 'Facets', 'SPONGE': 'Holes', 'BARK': 'Fissures', 'BONEFLAKE': 'Flakes',
                'KELOID': 'Plates', 'HIDE': 'Bumps / Wrinkles', 'WARTS': 'Warts', 'SCALEROWS': 'Scales',
                'POLYPS': 'Polyps'}
COUNT_NAME = {'MUSHROOM': 'Gills', 'CRYSTAL': 'Crystals', 'SHELL': 'Ribs'}
FORM_COUNT = {'FACETS': 'Facets', 'PLATES': 'Plates', 'BLOCKS': 'Blocks', 'FOLDS': 'Folds', 'TIERS': 'Tiers'}
FIELDS = ('low', 'det', 'crk', 'wave', 'vein', 'pore', 'rib', 'ring', 'gill', 'keel', 'spot', 'bark', 'flake', 'plate',
          'bump', 'wrinkle', 'shingle', 'polyp')


def is_mass(ob):
    return ob is not None and ob.type == 'MESH' and bool(ob.get(KEY))


def active_mass(context):
    ob = getattr(context, 'active_object', None)
    return ob if is_mass(ob) else None


# ---- the lump (Python) --------------------------------------------------------------------------------------------

class _Stub:
    """What base_mesh.profile_field reads (the Creature Base Mesh's Puff)."""
    profile = 'PUFF'
    outline_smooth = 0.35
    resolution = 44
    rim = 0.5
    edge_round = 0.15
    puff = 1.0

    def __init__(self):
        from . import base_mesh
        self.rings = base_mesh.PUFF_RINGS


def hinge_axis(P2):
    """The outline's bottom point (its base: a shell's hinge, a scale's root, the crystals' foot) and the way from it
    to the outline's farthest point (unit)."""
    i = int(np.argmin(P2[:, 1]))
    h = P2[i]
    j = int(np.argmax(np.linalg.norm(P2 - h, axis=1)))
    a = P2[j] - h
    n = np.linalg.norm(a)
    return h, (a / n if n > 1e-12 else np.array([0.0, 1.0]))


def cap_centre(P2):
    """A mushroom's middle line: x of the widest row of the upper half, at the cap's underside height."""
    lo, hi = P2[:, 1].min(), P2[:, 1].max()
    mid = (lo + hi) * 0.5
    up = P2[P2[:, 1] >= mid]
    if not len(up):
        up = P2
    return np.array([float((up[:, 0].min() + up[:, 0].max()) * 0.5), float(lo + (hi - lo) * 0.55)])


def lump(P2, holes, pg):
    """(verts (n, 3), faces) of the outline ``P2`` (local 2D, CCW) inflated - Thickness, Back; PLATE: a thin plate
    bowed toward you."""
    from . import base_mesh
    outer = [tuple(map(float, q)) for q in P2]
    hl = [[tuple(map(float, q)) for q in h] for h in holes]
    boundary, pts, tris, nb, shape, natural, spacing = base_mesh.profile_field(outer, hl, _Stub())
    sh = np.asarray(shape, float)
    XY = np.asarray(pts, float)
    plate = KIND[pg.kind][3] == 'PLATE'
    top_h = natural * pg.depth * (0.32 if plate else 1.0)
    floor = max(spacing * 0.01, top_h * 0.004)
    if plate:
        zt = top_h * np.power(sh, 0.55)
        zb = -top_h * max(pg.back, 0.02) * 0.6 * sh
        size = float(np.ptp(XY, axis=0).max())
        c = XY.mean(0)
        r2 = ((XY - c) ** 2).sum(1) / max((size * 0.5) ** 2, 1e-12)
        bow = size * 0.12 * pg.depth * np.clip(1.0 - r2, -0.5, 1.0)     # (bowed toward you, the rim back)
        zt, zb = zt + bow, zb + bow
    else:
        zt = top_h * sh
        zb = -top_h * pg.back * sh
    zt = np.maximum(zt, floor * (sh > 0))
    zb = np.minimum(zb, -floor * (sh > 0))
    zt[:nb] = zb[:nb] = (bow[:nb] if plate else 0.0)
    n = len(XY)
    V = np.concatenate([np.c_[XY, zt], np.c_[XY[nb:], zb[nb:]]])
    idx_b = np.concatenate([np.arange(nb), n + np.arange(n - nb)])         # (bottom: the rim shared)
    T = np.asarray(tris, np.int64)
    F = np.concatenate([T, idx_b[T][:, ::-1]])
    from .creature_hair import outline_distance
    dist = outline_distance([tuple(q) for q in XY], outer)
    for h in hl:
        dist = np.minimum(dist, outline_distance([tuple(q) for q in XY], h))
    dist[:nb] = 0.0
    return V, F, np.concatenate([dist, dist[nb:]])


def crystals(P2, pg, seed):
    """(verts, faces): six-sided crystals from the outline's bottom out to it (Count of them, Pattern: their
    thickness), and small ones round the foot."""
    rng = np.random.default_rng(seed + 11)
    h, _ax = hinge_axis(P2)
    cen = P2.mean(0)
    size = float(np.ptp(P2, axis=0).max())
    foot = h + (cen - h) * 0.12
    d = np.linalg.norm(P2 - foot, axis=1)
    ang = np.arctan2(P2[:, 1] - foot[1], P2[:, 0] - foot[0])
    order = np.argsort(ang)
    cand = order[d[order] > size * 0.25]
    if not len(cand):
        cand = order
    n = max(int(pg.count), 1)
    picks = [int(cand[np.argmax(d[cand])])]                # (the farthest first, then spread round)
    while len(picks) < min(n, len(cand)):
        gap = np.min(np.abs(((ang[cand][:, None] - ang[picks][None, :]) + np.pi) % (2 * np.pi) - np.pi), axis=1)
        picks.append(int(cand[np.argmax(gap * (0.5 + d[cand] / d.max()))]))
    V, F = [], []
    thick = 0.16 * max(pg.pattern, 0.05) * (0.6 + 0.4 * pg.depth)

    def one(base, tip, r):
        ax = tip - base
        L = np.linalg.norm(ax)
        if L < 1e-9:
            return
        ax = ax / L
        u = np.cross(ax, (0.0, 0.0, 1.0) if abs(ax[2]) < 0.9 else (1.0, 0.0, 0.0))
        u /= np.linalg.norm(u)
        w = np.cross(ax, u)
        rot = rng.random() * math.pi / 3
        k0 = len(V)
        body = 0.74 + 0.1 * rng.random()
        for ring, (at, rr) in enumerate(((-r * 0.6, r * 0.9), (L * body, r))):
            for i in range(6):
                a = rot + i * math.pi / 3
                V.append(base + ax * at + (u * math.cos(a) + w * math.sin(a)) * rr)
        V.append(base + ax * L)
        F.append(list(range(k0 + 5, k0 - 1, -1)))
        for i in range(6):
            j = (i + 1) % 6
            F.append([k0 + i, k0 + j, k0 + 6 + j, k0 + 6 + i])
            F.append([k0 + 6 + i, k0 + 6 + j, k0 + 12])

    for q in picks:
        t = P2[q]
        tilt = (rng.random() - 0.5) * 1.3
        tip2 = foot + (t - foot) * (0.82 + 0.18 * rng.random())
        L2 = np.linalg.norm(tip2 - foot)
        tip = np.array([tip2[0], tip2[1], tilt * L2 * 0.6])
        one(np.array([foot[0], foot[1], 0.0]), tip, L2 * thick * (0.8 + 0.4 * rng.random()))
    for _k in range(max(2, n // 2)):                        # (small ones round the foot)
        a = rng.random() * math.pi * 2
        L = size * (0.08 + 0.12 * rng.random())
        dir3 = np.array([math.cos(a) * 0.6, abs(math.sin(a)) * 0.5 + 0.55, (rng.random() - 0.5) * 1.4])
        dir3 /= np.linalg.norm(dir3)
        b = np.array([foot[0], foot[1], 0.0]) + np.array([(rng.random() - 0.5) * size * 0.25, 0.0,
                                                           (rng.random() - 0.5) * size * 0.15])
        one(b, b + dir3 * L, L * thick * 1.1)
    return np.array(V, float).reshape(-1, 3), F


# ---- big forms (0.24.183 user, with a sample FBX: "이거랑 똑같이 하라는 게 아니라 이런 식으로 크게 형태가 들어간 요철로
# 바리에이션을 하라는 거지"; "각 엣지 부분에 포인트를 넣고") --------------------------------------------------------------

def size_of(P2):
    return float(np.ptp(np.asarray(P2, float), axis=0).max())


def _inside(P, poly):
    """Even-odd: which points ``P`` (n, 2) are inside ``poly`` (m, 2)."""
    A = np.asarray(poly, float)
    B = np.roll(A, -1, axis=0)
    out = np.zeros(len(P), bool)
    for i in range(0, len(P), 4096):
        q = P[i:i + 4096, None, :]
        cond = (A[None, :, 1] > q[..., 1]) != (B[None, :, 1] > q[..., 1])
        xint = A[None, :, 0] + (q[..., 1] - A[None, :, 1]) * (B[None, :, 0] - A[None, :, 0]) / \
            np.where(np.abs(B[None, :, 1] - A[None, :, 1]) < 1e-15, 1e-15, B[None, :, 1] - A[None, :, 1])
        out[i:i + 4096] = (cond & (q[..., 0] < xint)).sum(1) % 2 == 1
    return out


def _densify(loop, step):
    P = np.asarray(loop, float)
    Q = np.roll(P, -1, axis=0)
    out = []
    for a, b in zip(P, Q):
        n = max(1, int(np.ceil(np.linalg.norm(b - a) / step)))
        out += [a + (b - a) * (k / n) for k in range(n)]
    return np.array(out)


def _noise2(P, scale, seed):
    """A smooth noise -1 .. 1 at the points ``P`` (n, 2)."""
    from mathutils import noise
    off = Vector((seed * 7.31, seed * 3.17, seed * 1.93))
    return np.array([noise.noise(Vector((x * scale, y * scale, 0.0)) + off) for x, y in P])


RISER = 0.12                       # (a step's riser: this share of the step - steep, still a face)


def _frame(P2, pg):
    """(centre, across, along2, u range, v range) - across: the way a Shard rises / Folds run, turned by Turn."""
    c = P2.mean(0)
    _u, _s, vt = np.linalg.svd(P2 - c, full_matrices=False)
    along = vt[0]
    t = float(pg.turn)
    across = np.array([-along[1], along[0]])
    across = across * math.cos(t) + along * math.sin(t)
    along2 = np.array([across[1], -across[0]])
    uo, vo = (P2 - c) @ across, (P2 - c) @ along2
    return c, across, along2, (float(uo.min()), float(uo.max())), (float(vo.min()), float(vo.max()))


def form_fields(kind, XY, d, P2, pg, dmax):
    """The smooth fields a big form is made of at the points ``XY`` (each also linearly right along an edge, so the
    mesh can be cut along them): d, un / vn (0 .. 1 across / along), wob (noise), g (the rim's step parameter), fk
    (the form's own: Plates / Tiers / Blocks)."""
    size = float(np.ptp(P2, axis=0).max())
    c, across, along2, (u0, u1), (v0, v1) = _frame(P2, pg)
    un = ((XY - c) @ across - u0) / max(u1 - u0, 1e-9)
    vn = ((XY - c) @ along2 - v0) / max(v1 - v0, 1e-9)
    jag = float(pg.jag)
    wob = _noise2(XY, 6.0 / max(size, 1e-9), int(pg.seed)) if jag > 0 else np.zeros(len(XY))
    ew = max(float(pg.edge_width), 0.02) * dmax
    F = {'d': d, 'un': un, 'vn': vn, 'wob': wob, 'g': d / ew + jag * 0.22 * wob}
    n_ = max(int(pg.count), 1)
    if kind == 'PLATES':
        F['fk'] = vn * n_ + 0.25 * wob
    elif kind == 'TIERS':
        q = d / dmax
        F['fk'] = np.clip(q * 1.1 - (un - 0.5) * 0.5 * q, 0.0, 1.0) * n_
    elif kind == 'BLOCKS':
        seeds = _block_seeds(XY, d, dmax, pg)
        D = np.linalg.norm(XY[:, None, :] - seeds[None, :, :], axis=2)
        Ds = np.sort(D, axis=1)
        F['fk'] = (Ds[:, 1] - Ds[:, 0]) if D.shape[1] > 1 else np.full(len(XY), 1e9)
    return F


def _block_seeds(XY, d, dmax, pg):
    rng = np.random.default_rng(int(pg.seed) + 101)
    n_ = max(int(pg.count), 2)
    q = d / max(dmax, 1e-9)
    inside = XY[q > 0.15] if (q > 0.15).sum() > n_ else XY
    rs = np.random.default_rng(int(pg.seed) + 7)
    return inside[rs.choice(len(inside), size=min(n_, len(inside)), replace=False)] if len(inside) else XY[:1]


def form_cuts(kind, pg, dmax, size):
    """[(field, level)] the mesh is cut along: each step's riser (its foot and its top), and the form's own edges."""
    out = []
    ns = int(pg.edge_steps)
    for k in range(ns):
        out += [('g', (k + 1 - RISER) / ns), ('g', (k + 1.0) / ns)]
    n_ = max(int(pg.count), 1)
    if kind == 'PLATES':
        for k in range(-1, n_ + 2):
            out += [('fk', k - RISER), ('fk', float(k))]
    elif kind == 'TIERS':
        for k in range(n_):
            out += [('fk', float(k)), ('fk', k + 0.6)]
    elif kind == 'BLOCKS':
        w = size * 0.012 * max(float(pg.pattern_width), 0.1)
        out += [('fk', w * 0.25), ('fk', w)]
    elif kind == 'SHARD':
        out += [('un', 0.62 + 0.25 * float(pg.slope))]
    return out


def form_heights(kind, F, XY, P2, pg, dmax):
    """The top of a big form (0 .. 1) from its fields: the form's own shape capped by the stepped rim (Edge Steps over
    Edge Width - the edges' accent)."""
    seed = int(pg.seed)
    rng = np.random.default_rng(seed + 101)
    d, un, vn, wob = F['d'], F['un'], F['vn'], F['wob']
    q = d / max(dmax, 1e-9)
    n_ = max(int(pg.count), 1)
    if kind == 'SHARD':           # a slanted top rising across it to a crest near the far side, which falls in steps
        peak = 0.62 + 0.25 * float(pg.slope)
        form = np.where(un <= peak, 0.18 + 0.82 * un / peak, 1.0 - (un - peak) / max(1.0 - peak, 1e-6) * 0.15)
        form = form * (0.55 + 0.45 * np.clip(q * 2.2, 0.0, 1.0) ** 0.5)    # (its ends and sides rounded down)
    elif kind == 'TERRACE':       # only the stepped rim: strata all round, a flat top
        form = np.ones(len(XY))
    elif kind == 'FACETS':        # big flat facets: a pyramid of tilted planes round a peak
        k = max(n_, 3)
        ang = np.linspace(0, 2 * math.pi, k, endpoint=False) + rng.random(k) * (2 * math.pi / k) * 0.8
        peak = P2.mean(0) + (rng.random(2) - 0.5) * dmax * 0.4
        form = np.full(len(XY), 1e9)
        for a in ang:
            nrm = np.array([math.cos(a), math.sin(a)])
            reach = max(float(((P2 - peak) @ nrm).max()), dmax * 0.3)
            drop = 0.55 + 0.2 * rng.random()
            form = np.minimum(form, 1.0 - drop * np.maximum((XY - peak) @ nrm, 0.0) / reach)
    elif kind == 'CREST':         # a sharp ridge along the middle (the outline's middle line), straight sides
        form = np.clip(q, 0.0, 1.0)
    elif kind == 'PLATES':        # big plates along its length, each rising to its edge, then a steep drop
        x = F['fk']
        f = x - np.floor(x)
        rise = np.clip(f / (1.0 - RISER), 0.0, 1.0)
        fall = np.clip((f - (1.0 - RISER)) / RISER, 0.0, 1.0)
        prof = np.where(f < 1.0 - RISER, 0.55 + 0.45 * rise ** 0.7, 1.0 - 0.45 * fall)
        form = prof * np.clip(q * 1.6, 0.0, 1.0) ** 0.5
    elif kind == 'BLOCKS':        # big blocks, each its own height and tilt, deep cracks between them
        seeds = _block_seeds(XY, d, dmax, pg)
        D = np.linalg.norm(XY[:, None, :] - seeds[None, :, :], axis=2)
        i1 = np.argmin(D, axis=1)
        r2 = np.random.default_rng(seed + 202)
        hgt = 0.62 + 0.38 * r2.random(len(seeds))
        tilt = (r2.random((len(seeds), 2)) - 0.5) * (0.5 / max(dmax, 1e-9))
        form = hgt[i1] + ((XY - seeds[i1]) * tilt[i1]).sum(1)
        w = float(np.ptp(P2, axis=0).max()) * 0.012 * max(float(pg.pattern_width), 0.1)
        crack = np.clip(F['fk'] / w, 0.0, 1.0)
        form = np.clip(form - 0.35 * (1.0 - crack ** 0.6), 0.05, 1.0)
    elif kind == 'FOLDS':         # big folds running along its length, sharp-crested
        wv = np.abs(np.sin(math.pi * (un * n_ + 0.35 * wob)))
        form = np.clip(q * 1.4, 0.0, 1.0) ** 0.6 * (0.45 + 0.55 * wv ** 0.6)
    else:                         # TIERS: a few thick rounded tiers, each set back to one side (a shelf)
        s_ = F['fk']
        k_ = np.floor(s_ + 1e-9)
        fr = s_ - k_
        sm = np.clip(fr / 0.6, 0.0, 1.0)
        form = np.clip((k_ + np.sqrt(np.maximum(1.0 - (1.0 - sm) ** 2, 0.0))) / n_, 0.0, 1.0)
    # the rim: Edge Steps over Edge Width (0 steps: a smooth rise), each step's edge jagged
    st = np.clip(F['g'], 0.0, 1.0)
    ns = int(pg.edge_steps)
    if ns > 0:
        x = np.clip(F['g'], 0.0, 1.0) * ns
        k_ = np.floor(x + 1e-9)
        fr = x - k_
        st = (k_ + np.clip((fr - (1.0 - RISER)) / RISER, 0.0, 1.0)) / ns     # (a steep riser, a flat tread)
    else:
        st = st * st * (3.0 - 2.0 * st)
    wall = 0.03                                    # (no wall at the outline: it rises from its foot, as a shard)
    rim = wall + (1.0 - wall) * np.clip(st, 0.0, 1.0)
    top = np.maximum(np.minimum(form, rim), wall)
    return np.where(d > 1e-12, top, wall)


def form_mesh(P2, holes, pg, res=None):
    """(verts, faces, distance to the outline) of a big form, light (0.24.183 user: "너무 고밀도야, 가벼워야 돼"): the
    outline's area in coarse triangles, cut exactly along each step's riser and the form's own edges (so they stay
    crisp with few points), the top raised, the bottom flat (Back: rounded down too), a wall round the outline - and
    the flat parts merged into big faces afterwards (build)."""
    import bmesh
    from mathutils import geometry
    from .creature_hair import outline_distance
    from .plate_detail import cut_iso
    size = float(np.ptp(P2, axis=0).max())
    step = size / max(int(res if res is not None else pg.resolution), 20)
    loops = [_densify(P2, step * 0.5)] + [_densify(h, step * 0.5) for h in holes]
    lo, hi = P2.min(0), P2.max(0)
    xs = np.arange(lo[0] + step * 0.5, hi[0], step)
    ys = np.arange(lo[1] + step * 0.5, hi[1], step * 0.866)
    G = np.array([(x + (step * 0.5 if j % 2 else 0.0), y) for j, y in enumerate(ys) for x in xs]).reshape(-1, 2)
    keep = _inside(G, P2)
    for h in holes:
        keep &= ~_inside(G, h)
    G = G[keep]

    def dist(Q):
        dd = outline_distance([tuple(q) for q in Q], [tuple(q) for q in P2])
        for h in holes:
            dd = np.minimum(dd, outline_distance([tuple(q) for q in Q], [tuple(q) for q in h]))
        return dd
    if len(G):
        G = G[dist(G) > step * 0.45]
    verts = [Vector((float(x), float(y))) for lp in loops for x, y in lp] + [Vector((float(x), float(y))) for x, y in G]
    faces_in, off = [], 0
    for lp in loops:
        faces_in.append(list(range(off, off + len(lp))))
        off += len(lp)
    out = geometry.delaunay_2d_cdt(verts, [], faces_in, 3, step * 1e-3)
    V2 = np.array([tuple(v) for v in out[0]], float)
    T0 = [f for f in out[2] if len(f) == 3]
    d = dist(V2)
    d[d < step * 0.05] = 0.0
    dmax = max(float(d.max()), 1e-9)
    F = form_fields(pg.kind, V2, d, P2, pg, dmax)
    # cut along the steps' risers and the form's edges (exact lines: crisp with few points)
    bm = bmesh.new()
    lays = {name: bm.verts.layers.float.new('mch_f_' + name) for name in F}   # (layers first: a new layer drops
    bv = [bm.verts.new((float(x), float(y), 0.0)) for x, y in V2]                #  the points' handles)
    for name, lay in lays.items():
        for v, x in zip(bv, F[name]):
            v[lay] = float(x)
    for t in T0:
        try:
            bm.faces.new([bv[i] for i in t])
        except ValueError:
            pass
    carry = tuple(lays.values())
    for name, level in form_cuts(pg.kind, pg, dmax, size):
        if name in lays:
            cut_iso(bm, lays[name], level, 1e-7, carry)
    bm.verts.index_update()
    V2 = np.array([(v.co.x, v.co.y) for v in bm.verts])
    F = {name: np.array([v[lay] for v in bm.verts]) for name, lay in lays.items()}
    T = np.array([[v.index for v in f.verts] for f in bm.faces if len(f.verts) == 3], np.int64).reshape(-1, 3)
    bm.free()
    d = np.maximum(F['d'], 0.0)
    H = dmax * 1.5 * float(pg.depth)
    top = H * form_heights(pg.kind, F, V2, P2, pg, dmax)
    n = len(V2)
    bot = -float(pg.back) * top * 0.8
    V = np.concatenate([np.c_[V2, top], np.c_[V2, bot]])
    Fc = [tuple(t) for t in T] + [tuple(n + t[::-1]) for t in T]
    from collections import Counter
    cnt = Counter()
    for a, b_, c_ in T:
        for e in ((a, b_), (b_, c_), (c_, a)):
            cnt[(min(e), max(e))] += 1
    for a, b_, c_ in T:
        for x, y in ((a, b_), (b_, c_), (c_, a)):
            if cnt[(min(x, y), max(x, y))] == 1:
                Fc.append((y, x, n + x, n + y))
    return V, Fc, np.concatenate([d, d])


# ---- the surface (Geometry Nodes) ---------------------------------------------------------------------------------

def _menu(sock, value):
    try:
        sock.default_value = value
    except (TypeError, ValueError, AttributeError):
        pass


def _stored_tree(old):
    """The node group taken ready-made from the add-on's own file - or None (no file, another Blender's, an older
    group: then it is built)."""
    if not os.path.isfile(TREE_FILE):
        return None
    if old is not None:
        old.name = TREE + ' (old)'
    ng = None
    try:
        with bpy.data.libraries.load(TREE_FILE, link=False) as (src, dst):
            if TREE in src.node_groups:
                dst.node_groups = [TREE]
        ng = dst.node_groups[0] if dst.node_groups else None
    except (OSError, RuntimeError, ValueError, IndexError, AttributeError):
        ng = None
    if ng is None or ng.get('mch_v') != TREE_VERSION:
        if ng is not None:
            bpy.data.node_groups.remove(ng)
        if old is not None:
            old.name = TREE
        return None
    ng.name = TREE
    if old is not None and old.users == 0:
        bpy.data.node_groups.remove(old)
    return ng


def organic_tree():
    """The shared node group: remeshed evenly (or not: crystals), smoothed, the matter's surface along the normal;
    stores ``mch_om_var`` (big noise), ``mch_om_pat`` (its pattern: cracks, pores, gills...) and ``mch_om_spot``
    for the material."""
    from .creature_fur import _B, _socket
    ng = bpy.data.node_groups.get(TREE)
    if ng is not None and ng.get('mch_v') == TREE_VERSION:
        return ng
    got = _stored_tree(ng) if STORED[0] else None     # (ready-made: building its 670 nodes here takes 4 - 5 seconds)
    if got is not None:
        return got
    ng = bpy.data.node_groups.get(TREE)
    if ng is None:
        ng = bpy.data.node_groups.new(TREE, 'GeometryNodeTree')
    ng.nodes.clear()
    ng.interface.clear()
    _socket(ng, 'Geometry', 'GEOMETRY')
    for name, kind, default in (('Remesh', 'BOOL', True), ('Voxel', 'FLOAT', 0.01), ('Smooth', 'INT', 1),
                                ('Size', 'FLOAT', 1.0), ('Seed', 'FLOAT', 0.0), ('Pattern Scale', 'FLOAT', 1.0),
                                ('Pattern Width', 'FLOAT', 1.0), ('Count', 'FLOAT', 8.0), ('Flat', 'BOOL', False),
                                ('Hinge', 'VECTOR', (0.0, 0.0, 0.0)), ('Axis', 'VECTOR', (0.0, 1.0, 0.0)),
                                ('Centre', 'VECTOR', (0.0, 0.0, 0.0)), ('Material', 'MATERIAL', None)):
        _socket(ng, name, kind, default)
    for f in FIELDS:
        _socket(ng, 'W ' + f, 'FLOAT', 0.0)
    for f in FIELDS:                                  # (which fields colour the pattern: the cracks, not the ridges)
        _socket(ng, 'C ' + f, 'FLOAT', 0.0)
    # 0.24.183 (user: "그냥 우리 플레이트 디테일 4에 넣은 거랑 비슷하게 하는 게 좋을 듯, 각 엣지 부분에 포인트를 넣고"):
    # strongest at the edges (Rim, Center: how much in the middle) and the Plate Detail 4 surface
    for name, kind, default in (('Has Edge', 'BOOL', True), ('Rim', 'FLOAT', 0.3), ('Center', 'FLOAT', 0.6),
                                ('Rough', 'BOOL', False), ('Strength', 'FLOAT', 0.01), ('Feature', 'FLOAT', 0.05),
                                ('Chips', 'FLOAT', 0.0)):
        _socket(ng, name, kind, default)
    from .plate_rough import MIX_PROPS as _MIX
    for _p, sock, *_r in _MIX:
        _socket(ng, sock, 'FLOAT', 0.0)
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    b = _B(ng)
    gi = b.node('NodeGroupInput')
    go = b.node('NodeGroupOutput')
    I = gi.outputs
    # remeshed evenly
    m2v = b.node('GeometryNodeMeshToVolume')
    b.feed(m2v.inputs['Mesh'], I['Geometry'])
    _menu(m2v.inputs['Resolution Mode'], 'Size')
    b.feed(m2v.inputs['Voxel Size'], I['Voxel'])
    v2m = b.node('GeometryNodeVolumeToMesh')
    b.feed(v2m.inputs['Volume'], m2v.outputs['Volume'])
    _menu(v2m.inputs['Resolution Mode'], 'Size')
    b.feed(v2m.inputs['Voxel Size'], I['Voxel'])
    v2m.inputs['Threshold'].default_value = 0.3
    rsw = b.node('GeometryNodeSwitch', input_type='GEOMETRY')
    b.feed(rsw.inputs['Switch'], I['Remesh'])
    b.feed(rsw.inputs['False'], I['Geometry'])
    b.feed(rsw.inputs['True'], v2m.outputs['Mesh'])
    geo = rsw.outputs['Output']
    pos = b.node('GeometryNodeInputPosition').outputs['Position']
    blur = b.node('GeometryNodeBlurAttribute', data_type='FLOAT_VECTOR')
    b.feed(blur.inputs['Value'], pos)
    b.feed(blur.inputs['Iterations'], I['Smooth'])
    sp0 = b.node('GeometryNodeSetPosition')
    b.feed(sp0.inputs['Geometry'], geo)
    b.feed(sp0.inputs['Position'], blur.outputs['Value'])
    geo = sp0.outputs['Geometry']
    # the fields (position over Size, the seed as an offset)
    P = b.node('GeometryNodeInputPosition').outputs['Position']
    N = b.node('GeometryNodeInputNormal').outputs['Normal']
    sz = b.math('MAXIMUM', I['Size'], 1e-6)
    seedv = b.node('ShaderNodeCombineXYZ')
    b.feed(seedv.inputs[0], b.math('MULTIPLY', I['Seed'], 7.31))
    b.feed(seedv.inputs[1], b.math('MULTIPLY', I['Seed'], 3.17))
    b.feed(seedv.inputs[2], b.math('MULTIPLY', I['Seed'], 5.23))
    Q = b.vec('ADD', b.vec('SCALE', P, scale=b.math('DIVIDE', 1.0, sz)), seedv.outputs['Vector'])
    ps, pw = I['Pattern Scale'], I['Pattern Width']

    def noise(vec, scale, detail, rough=0.55, distortion=0.0):
        n = b.node('ShaderNodeTexNoise')
        b.feed(n.inputs['Vector'], vec)
        b.feed(n.inputs['Scale'], scale)
        n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = rough
        n.inputs['Distortion'].default_value = distortion
        return n.outputs['Factor']

    def voronoi(vec, scale, feature, rnd=1.0):
        n = b.node('ShaderNodeTexVoronoi', feature=feature)
        b.feed(n.inputs['Vector'], vec)
        b.feed(n.inputs['Scale'], scale)
        n.inputs['Randomness'].default_value = rnd
        return n.outputs['Distance']

    def smooth_band(x, width):
        """1 at 0, 0 from ``width`` on (smooth)."""
        t = b.math('MINIMUM', b.math('MAXIMUM', b.math('DIVIDE', x, b.math('MAXIMUM', width, 1e-6)), 0.0), 1.0)
        return b.math('SUBTRACT', 1.0, b.math('MULTIPLY', b.math('MULTIPLY', t, t),
                                              b.math('SUBTRACT', 3.0, b.math('MULTIPLY', t, 2.0))))

    nlow = b.math('SUBTRACT', noise(Q, 1.6, 2.0, 0.5), 0.5)
    ndet = b.math('SUBTRACT', noise(Q, b.math('MULTIPLY', ps, 9.0), 8.0, 0.62), 0.5)
    crk = smooth_band(voronoi(Q, b.math('MULTIPLY', ps, 3.0), 'DISTANCE_TO_EDGE', 0.9), b.math('MULTIPLY', pw, 0.045))
    wv = b.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='DIAGONAL')
    b.feed(wv.inputs['Vector'], Q)
    b.feed(wv.inputs['Scale'], b.math('MULTIPLY', ps, 3.2))
    wv.inputs['Distortion'].default_value = 7.0
    wv.inputs['Detail'].default_value = 1.5
    wv.inputs['Detail Scale'].default_value = 0.8
    wave = smooth_band(wv.outputs['Factor'], b.math('MULTIPLY', pw, 0.32))      # (1 in the meandering grooves)
    vein = smooth_band(b.math('ABSOLUTE', b.math('SUBTRACT', noise(Q, b.math('MULTIPLY', ps, 1.8), 1.0, 0.4), 0.5)),
                       b.math('MULTIPLY', pw, 0.016))
    pore = smooth_band(voronoi(Q, b.math('MULTIPLY', ps, 9.0), 'F1'), b.math('MULTIPLY', pw, 0.3))
    # round the hinge (shell / scale): the angle round it, the way from it
    rel = b.vec('SUBTRACT', P, I['Hinge'])
    ax = b.vec('NORMALIZE', I['Axis'])
    side = b.vec('CROSS_PRODUCT', (0.0, 0.0, 1.0), ax)
    along = b.vec('DOT_PRODUCT', rel, ax)
    across = b.vec('DOT_PRODUCT', rel, side)
    ang = b.math('ARCTAN2', across, along)
    rib = b.math('ADD', 0.5, b.math('MULTIPLY', 0.5, b.math('COSINE', b.math('MULTIPLY', ang, b.math('MULTIPLY',
                                                                                                    I['Count'], 2.0)))))
    dist = b.math('DIVIDE', b.vec('LENGTH', rel), sz)
    ring = b.math('ADD', 0.5, b.math('MULTIPLY', 0.5, b.math('SINE', b.math('MULTIPLY', dist,
                                                                            b.math('MULTIPLY', ps, 42.0)))))
    sepN = b.node('ShaderNodeSeparateXYZ')
    b.feed(sepN.inputs[0], N)
    front = b.math('MINIMUM', b.math('MAXIMUM', b.math('MULTIPLY', sepN.outputs['Z'], 3.0), 0.0), 1.0)
    keel = b.math('MULTIPLY', smooth_band(b.math('ABSOLUTE', b.math('DIVIDE', across, sz)),
                                          b.math('MULTIPLY', pw, 0.07)), front)
    keel = b.math('MULTIPLY', keel, b.math('MINIMUM', b.math('MULTIPLY', dist, 4.0), 1.0))
    # gills: round the cap's middle line (up = +Y), on the faces turned down
    relc = b.vec('SUBTRACT', P, I['Centre'])
    sepc = b.node('ShaderNodeSeparateXYZ')
    b.feed(sepc.inputs[0], relc)
    ang2 = b.math('ARCTAN2', sepc.outputs['Z'], sepc.outputs['X'])
    gill = smooth_band(b.math('ABSOLUTE', b.math('SINE', b.math('MULTIPLY', ang2, I['Count']))),
                       b.math('MULTIPLY', pw, 0.45))
    down = b.math('MINIMUM', b.math('MAXIMUM', b.math('MULTIPLY', b.math('SUBTRACT', b.math('MULTIPLY', sepN.outputs['Y'],
                                                                                             -1.0), 0.15), 3.0), 0.0), 1.0)
    below = b.math('LESS_THAN', sepc.outputs['Y'], 0.0)
    gill = b.math('MULTIPLY', b.math('MULTIPLY', gill, down), b.math('SUBTRACT', 1.0, b.math('MULTIPLY', below, 0.85)))
    upf = b.math('MINIMUM', b.math('MAXIMUM', b.math('MULTIPLY', b.math('SUBTRACT', sepN.outputs['Y'], 0.1), 3.0), 0.0), 1.0)
    f1 = voronoi(Q, b.math('MULTIPLY', ps, 4.5), 'F1', 0.8)                       # (a slice of 3D cells: a spot
    spot = b.math('MULTIPLY', smooth_band(b.math('MAXIMUM', b.math('SUBTRACT', f1, b.math('MULTIPLY', pw, 0.3)), 0.0),
                                          0.06), upf)                               #  where the cell is near: wide)
    # bark: long fissures up the outline (the cells stretched along +Y)
    st = b.node('ShaderNodeCombineXYZ')
    st.inputs[0].default_value, st.inputs[1].default_value, st.inputs[2].default_value = 5.0, 0.7, 5.0
    bark = smooth_band(voronoi(b.vec('MULTIPLY', Q, st.outputs['Vector']), b.math('MULTIPLY', ps, 1.6),
                               'DISTANCE_TO_EDGE', 1.0), b.math('MULTIPLY', pw, 0.07))
    # 0.24.183 creature reliefs - flakes: layers lifting toward the tip (a saw wave up the outline, broken by noise)
    flw = b.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Y', wave_profile='SAW')
    b.feed(flw.inputs['Vector'], Q)
    b.feed(flw.inputs['Scale'], b.math('MULTIPLY', ps, 4.0))
    flw.inputs['Distortion'].default_value = 9.0
    flw.inputs['Detail'].default_value = 3.0
    flw.inputs['Detail Scale'].default_value = 1.2
    patch = b.math('MINIMUM', b.math('MAXIMUM', b.math('MULTIPLY', b.math('SUBTRACT', noise(Q, 2.2, 2.0, 0.5), 0.35),
                                                         3.0), 0.15), 1.0)      # (some places flake more)
    flake = b.math('ADD', 0.5, b.math('MULTIPLY', b.math('SUBTRACT', flw.outputs['Factor'], 0.5), patch))
    # plates: big raised plates, cracks between them
    pvo = b.node('ShaderNodeTexVoronoi', feature='DISTANCE_TO_EDGE')
    b.feed(pvo.inputs['Vector'], Q)
    b.feed(pvo.inputs['Scale'], b.math('MULTIPLY', ps, 2.6))
    pvo.inputs['Randomness'].default_value = 0.9
    pvc = b.node('ShaderNodeTexVoronoi', feature='F1')          # (the same cells: each plate's own height)
    b.feed(pvc.inputs['Vector'], Q)
    b.feed(pvc.inputs['Scale'], b.math('MULTIPLY', ps, 2.6))
    pvc.inputs['Randomness'].default_value = 0.9
    pcs = b.node('FunctionNodeSeparateColor')
    b.feed(pcs.inputs[0], pvc.outputs['Color'])
    edge_t = b.math('MINIMUM', b.math('DIVIDE', pvo.outputs['Distance'], b.math('MULTIPLY', pw, 0.2)), 1.0)
    plate = b.math('MULTIPLY', b.math('SQRT', b.math('MAXIMUM', b.math('SUBTRACT', 1.0, b.math(
        'MULTIPLY', b.math('SUBTRACT', 1.0, edge_t), b.math('SUBTRACT', 1.0, edge_t))), 0.0)),
        b.math('ADD', 0.55, b.math('MULTIPLY', pcs.outputs[0], 0.45)))       # (round-shouldered, 55-100 % high)

    def dome(scale, r):
        t = b.math('MINIMUM', b.math('DIVIDE', voronoi(Q, scale, 'F1', 1.0), b.math('MAXIMUM', r, 1e-6)), 1.0)
        return b.math('SQRT', b.math('MAXIMUM', b.math('SUBTRACT', 1.0, b.math('MULTIPLY', t, t)), 0.0))
    # bumps: domes, big and small
    bump = b.math('MAXIMUM', dome(b.math('MULTIPLY', ps, 5.0), b.math('MULTIPLY', pw, 0.5)),
                  b.math('MULTIPLY', dome(b.math('MULTIPLY', ps, 11.0), b.math('MULTIPLY', pw, 0.45)), 0.55))
    # wrinkles: lines where a noise crosses its middle
    wrinkle = smooth_band(b.math('ABSOLUTE', b.math('SUBTRACT', noise(Q, b.math('MULTIPLY', ps, 3.2), 3.0, 0.55), 0.5)),
                          b.math('MULTIPLY', pw, 0.05))
    # shingles: rows of overlapping scales hanging down (up = +Y), every other row half a scale on
    axn = b.vec('NORMALIZE', I['Axis'])
    sdn = b.vec('CROSS_PRODUCT', (0.0, 0.0, 1.0), axn)
    u_ = b.math('MULTIPLY', b.vec('DOT_PRODUCT', Q, sdn), b.math('MULTIPLY', ps, 12.0))
    v_ = b.math('MULTIPLY', b.math('SUBTRACT', 0.0, b.vec('DOT_PRODUCT', Q, axn)), b.math('MULTIPLY', ps, 13.0))
    row = b.math('FLOOR', v_)
    fu = b.math('SUBTRACT', b.math('FRACT', b.math('ADD', u_, b.math('FRACT', b.math('MULTIPLY', row, 0.5)))), 0.5)
    fv = b.math('FRACT', v_)
    shingle = b.math('MULTIPLY', b.math('SUBTRACT', 1.0, fv), b.math('MAXIMUM', b.math(
        'SUBTRACT', 1.0, b.math('MULTIPLY', b.math('MULTIPLY', fu, fu), 2.8)), 0.0))
    # polyps: cups with a star of ridges in each
    pv = b.node('ShaderNodeTexVoronoi', feature='F1')
    b.feed(pv.inputs['Vector'], Q)
    b.feed(pv.inputs['Scale'], b.math('MULTIPLY', ps, 7.0))
    pve = b.node('ShaderNodeTexVoronoi', feature='DISTANCE_TO_EDGE')
    b.feed(pve.inputs['Vector'], Q)
    b.feed(pve.inputs['Scale'], b.math('MULTIPLY', ps, 7.0))
    cup = b.math('SUBTRACT', 1.0, smooth_band(pve.outputs['Distance'], b.math('MULTIPLY', pw, 0.28)))   # (0: wall)
    rel_p = b.node('ShaderNodeSeparateXYZ')
    b.feed(rel_p.inputs[0], b.vec('SUBTRACT', Q, pv.outputs['Position']))
    star = b.math('ADD', 0.5, b.math('MULTIPLY', 0.5, b.math('COSINE', b.math('MULTIPLY', b.math(
        'ARCTAN2', rel_p.outputs['Y'], rel_p.outputs['X']), 12.0))))
    polyp = b.math('SUBTRACT', b.math('MULTIPLY', b.math('SUBTRACT', 1.0, cup), 0.4),
                   b.math('MULTIPLY', cup, b.math('SUBTRACT', 0.85, b.math('MULTIPLY', star, b.math('MULTIPLY', cup, 0.5)))))
    terms = (('low', nlow, 0.12), ('det', ndet, 0.03), ('crk', crk, -0.03), ('wave', wave, -0.03),
             ('vein', vein, 0.012), ('pore', pore, -0.035), ('rib', rib, 0.022), ('ring', ring, 0.006),
             ('gill', gill, -0.035), ('keel', keel, 0.045), ('bark', bark, -0.04),
             ('flake', b.math('SUBTRACT', flake, 0.5), 0.04), ('plate', plate, 0.032), ('bump', bump, 0.03),
             ('wrinkle', wrinkle, -0.012), ('shingle', shingle, 0.03), ('polyp', polyp, 0.032))
    # the edge: a lump's distance to its outline (from the mesh it was made of); a converted mesh: its convex parts
    # (ridges, rims) count as edges
    rd_s = b.node('GeometryNodeSampleNearestSurface', data_type='FLOAT')
    b.feed(rd_s.inputs['Mesh'], I['Geometry'])
    b.feed(rd_s.inputs['Value'], b.attr(RD_ATTR).outputs['Attribute'])
    pb = b.node('GeometryNodeBlurAttribute', data_type='FLOAT_VECTOR')
    b.feed(pb.inputs['Value'], P)
    pb.inputs['Iterations'].default_value = 4
    convex = b.math('DIVIDE', b.vec('DOT_PRODUCT', b.vec('SUBTRACT', P, pb.outputs['Value']), N),
                    b.math('MULTIPLY', sz, 0.0025))
    rim = b.math('MAXIMUM', b.math('MULTIPLY', I['Rim'], sz), 1e-6)
    rd_c = b.math('MULTIPLY', rim, b.math('SUBTRACT', 1.0, b.math('MINIMUM', b.math('MAXIMUM', convex, 0.0), 1.0)))
    rsw2 = b.node('GeometryNodeSwitch', input_type='FLOAT')
    b.feed(rsw2.inputs['Switch'], I['Has Edge'])
    b.feed(rsw2.inputs['False'], rd_c)
    b.feed(rsw2.inputs['True'], rd_s.outputs['Value'])
    rd = rsw2.outputs['Output']
    edge_t = b.math('MINIMUM', b.math('DIVIDE', rd, rim), 1.0)
    at_edge = b.math('SUBTRACT', 1.0, b.math('MULTIPLY', b.math('MULTIPLY', edge_t, edge_t),
                                             b.math('SUBTRACT', 3.0, b.math('MULTIPLY', edge_t, 2.0))))
    amount = b.math('ADD', I['Center'], b.math('MULTIPLY', b.math('SUBTRACT', 1.0, I['Center']), at_edge))
    off = None
    for f, val, k in terms:
        t_ = b.math('MULTIPLY', b.math('MULTIPLY', val, I['W ' + f]), k)
        if f != 'low':
            t_ = b.math('MULTIPLY', t_, amount)
        off = t_ if off is None else b.math('ADD', off, t_)
    off = b.math('MULTIPLY', off, sz)
    rough_tex, chips = _rough(b, I, P, rd, rim)
    rough_on = b.node('GeometryNodeSwitch', input_type='FLOAT')
    b.feed(rough_on.inputs['Switch'], I['Rough'])
    rough_on.inputs['False'].default_value = 0.0
    b.feed(rough_on.inputs['True'], b.math('SUBTRACT', b.math('MULTIPLY', b.math('MULTIPLY', rough_tex, amount),
                                                               I['Strength']), chips))
    off = b.math('ADD', off, rough_on.outputs['Output'])
    sp = b.node('GeometryNodeSetPosition')
    b.feed(sp.inputs['Geometry'], geo)
    b.feed(sp.inputs['Offset'], b.vec('SCALE', N, scale=off))
    geo = sp.outputs['Geometry']
    # for the material (worked out where the points were before the offset: the same fields, stored)
    pat = None
    for f, val in (('crk', crk), ('pore', pore), ('gill', gill), ('vein', vein), ('bark', bark), ('wave', wave),
                   ('flake', b.math('MULTIPLY', b.math('SUBTRACT', 1.0, flake), 0.8)),
                   ('plate', b.math('SUBTRACT', 1.0, plate)), ('bump', b.math('MULTIPLY', b.math('SUBTRACT', 1.0, bump), 0.6)),
                   ('wrinkle', wrinkle), ('shingle', b.math('MULTIPLY', b.math('SUBTRACT', 1.0, shingle), 0.8)),
                   ('polyp', cup)):
        use = b.math('MULTIPLY', b.math('MINIMUM', b.math('MULTIPLY', I['W ' + f], 20.0), 1.0), I['C ' + f])
        t_ = b.math('MULTIPLY', val, use)
        pat = t_ if pat is None else b.math('MAXIMUM', pat, t_)
    rpat = b.node('GeometryNodeSwitch', input_type='FLOAT')
    b.feed(rpat.inputs['Switch'], I['Rough'])
    rpat.inputs['False'].default_value = 0.0
    b.feed(rpat.inputs['True'], b.math('MULTIPLY', b.math('MAXIMUM', b.math('SUBTRACT', 0.0, rough_tex), 0.0), amount))
    pat = b.math('MAXIMUM', pat, rpat.outputs['Output'])
    geo = b.store(geo, 'mch_om_pat', b.math('MINIMUM', b.math('MAXIMUM', pat, 0.0), 1.0))
    geo = b.store(geo, 'mch_om_var', b.math('ADD', nlow, 0.5))
    geo = b.store(geo, 'mch_om_spot', b.math('MULTIPLY', spot, b.math('MINIMUM', b.math('MULTIPLY', I['W spot'], 20.0),
                                                                     1.0)))
    smooth = b.node('GeometryNodeSetShadeSmooth')
    b.feed(smooth.inputs['Mesh'], geo)
    b.feed(smooth.inputs['Shade Smooth'], b.math('SUBTRACT', 1.0, I['Flat']))
    ea = b.node('GeometryNodeInputMeshEdgeAngle')
    sharp = b.node('GeometryNodeSetShadeSmooth', domain='EDGE')          # (steps, facets: crisp edges)
    b.feed(sharp.inputs['Mesh'], smooth.outputs['Mesh'])
    b.feed(sharp.inputs['Selection'], b.math('GREATER_THAN', ea.outputs['Unsigned Angle'], math.radians(35.0)))
    sharp.inputs['Shade Smooth'].default_value = False
    sm = b.node('GeometryNodeSetMaterial')
    b.feed(sm.inputs['Geometry'], sharp.outputs['Mesh'])
    b.feed(sm.inputs['Material'], I['Material'])
    b.feed(go.inputs[0], sm.outputs['Geometry'])
    ng['mch_v'] = TREE_VERSION
    return ng


def _rough(b, I, pos, rd, rim):
    """0.24.183 Plate Detail 4's rim texture on the lump (its channels: Bumps, Cells, Cracks, Wrinkles along the
    outline, Pits, Grain - about -1 .. 1, mixed) and Chips: bites in from the edge.  Returns (texture, chips depth)."""
    from .plate_rough import _clamp01, _map, _noise, _rgb, _seed, _voronoi, _when
    feat = b.math('MAXIMUM', I['Feature'], 1e-6)
    q = b.vec('SCALE', pos, scale=b.math('DIVIDE', 1.0, feat))
    seed = I['Seed']
    bumps = b.math('MULTIPLY', b.math('SUBTRACT', _noise(b, q, _seed(b, seed, 3), 1.0, 5.0, 0.55).outputs['Factor'],
                                      0.5), 2.4)
    edge_v = _voronoi(b, q, _seed(b, seed, 4), 1.0, 'DISTANCE_TO_EDGE').outputs['Distance']
    stones = b.math('SUBTRACT', b.math('MULTIPLY', b.math('SQRT', _clamp01(b, b.math('DIVIDE', edge_v, 0.4))), 2.0), 1.0)
    warp = _noise(b, q, _seed(b, seed, 5), 0.5, 2.0, 0.5).outputs['Color']
    qc = b.vec('ADD', b.vec('SCALE', q, scale=0.45), b.vec('SCALE', b.vec('SUBTRACT', warp, (0.5, 0.5, 0.5)), scale=0.8))
    crack_v = _voronoi(b, qc, _seed(b, seed, 6), 1.0, 'DISTANCE_TO_EDGE').outputs['Distance']
    crack_on = _clamp01(b, b.math('MULTIPLY', b.math('SUBTRACT', _noise(b, q, _seed(b, seed, 7), 0.3, 2.0, 0.5)
                                                  .outputs['Factor'], 0.38), 5.0))
    cracks = b.math('MULTIPLY', _map(b, crack_v, 0.0, 0.07, -1.0, 0.0, 'SMOOTHSTEP'), crack_on)
    spacing = b.math('MULTIPLY', feat, b.math('ADD', 0.38, b.math('MULTIPLY', _noise(b, q, _seed(b, seed, 12), 0.25, 1.0,
                                                                                   0.5).outputs['Factor'], 0.4)))
    wob = b.math('MULTIPLY', b.math('SUBTRACT', _noise(b, q, _seed(b, seed, 8), 0.7, 3.0, 0.55).outputs['Factor'], 0.5),
                 11.0)
    phase = b.math('ADD', b.math('MULTIPLY', b.math('DIVIDE', rd, spacing), 2 * math.pi), wob)
    fold = b.math('SQRT', b.math('ABSOLUTE', b.math('SINE', phase)))
    fold_on = _clamp01(b, b.math('MULTIPLY', b.math('SUBTRACT', _noise(b, q, _seed(b, seed, 9), 0.6, 2.0, 0.5)
                                                     .outputs['Factor'], 0.33), 3.5))
    wrinkles = b.math('MULTIPLY', b.math('SUBTRACT', b.math('MULTIPLY', fold, 2.0), 1.3), fold_on)
    pv = _voronoi(b, q, _seed(b, seed, 10), 1.5)
    prnd = _rgb(b, pv.outputs['Color'])
    pit_on = b.math('LESS_THAN', prnd[0], 0.45)
    radius = b.math('ADD', 0.15, b.math('MULTIPLY', prnd[1], 0.25))
    pits = b.math('MULTIPLY', _map(b, pv.outputs['Distance'], 0.0, radius, -1.0, 0.0, 'SMOOTHSTEP'), pit_on)
    grain = b.math('MULTIPLY', b.math('SUBTRACT', _noise(b, q, _seed(b, seed, 11), 3.5, 2.0, 0.6).outputs['Factor'],
                                      0.5), 2.4)
    tex = None
    for chan, sock in ((bumps, 'Bumps'), (stones, 'Cells'), (cracks, 'Cracks'), (wrinkles, 'Wrinkles'), (pits, 'Pits'),
                       (grain, 'Grain')):
        term = _when(b, I[sock], b.math('MULTIPLY', chan, I[sock]))
        tex = term if tex is None else b.math('ADD', tex, term)
    # chips: round bites and whole chunks taken in from the edge (as deep as 0.6 of the Rim, only near the edge)
    bite = _clamp01(b, b.math('MULTIPLY', b.math('SUBTRACT', _noise(b, q, _seed(b, seed, 1), 0.35, 3.0, 0.6)
                                                  .outputs['Factor'], 0.45), 4.0))
    cells = _rgb(b, _voronoi(b, q, _seed(b, seed, 2), 0.6).outputs['Color'])
    chunk = _clamp01(b, b.math('MULTIPLY', b.math('SUBTRACT', cells[0], 0.5), 2.5))
    near = _map(b, rd, 0.0, b.math('MULTIPLY', rim, 0.6), 1.0, 0.0, 'SMOOTHSTEP')
    chips = _when(b, I['Chips'], b.math('MULTIPLY', b.math('MULTIPLY', b.math('MULTIPLY', I['Chips'],
                                                                                   b.math('MULTIPLY', rim, 0.25)),
                                                                     b.math('MAXIMUM', bite, chunk)), near))
    return tex, chips


def stick(context, ob, V, d):
    """0.24.183 (user: "크리쳐 요철도 크리쳐 플레이트처럼 표면에 붙는 버튼도 하나 - 누르면 플레이트처럼, 안 누르면 베이스
    메쉬처럼") Stick to Surface: each point onto the part under it (straight down its own Z, the way it was drawn
    facing) - its bottom on the surface, its height off it along the surface's normal there."""
    from .mecha_holes import target_bvh
    tgt = bpy.data.objects.get(d.get('target', ''))
    if tgt is None or 'frame' not in d or not len(V):
        return V
    rel = Matrix(d['frame'])
    bvh = target_bvh(context, tgt, rel.inverted())
    size = float(np.ptp(V[:, :2], axis=0).max()) or 1.0
    out = V.copy()
    for i, (x, y, z) in enumerate(V):
        loc, nrm, _i, _dd = bvh.ray_cast(Vector((x, y, size * 2.0)), Vector((0.0, 0.0, -1.0)), size * 6.0)
        if loc is None:
            loc, nrm, _i, _dd = bvh.find_nearest(Vector((x, y, 0.0)))
        if loc is None:
            continue
        if nrm.z < 0:
            nrm = -nrm
        h = z if z > 0 else z * 0.25 - size * 0.002     # (the bottom a little into the part: no gap)
        out[i] = np.array(loc + nrm * h)
    return out


def material(ob):
    """The lump's own material (two colours by the big noise, the pattern darker - or glowing: Lava; spots: the
    Mushroom's; see-through: Ice / Crystal)."""
    pg = ob.mch_omass
    look = KIND[pg.kind][7]
    name = ob.get('mch_omass_mat', '')
    mat = bpy.data.materials.get(name) if name else None
    if mat is None:
        mat = bpy.data.materials.new('MCH Organic')
        ob['mch_omass_mat'] = mat.name
    mat.use_nodes = True
    nt = mat.node_tree
    if nt.get('mch_kind') != pg.kind or not nt.nodes.get('MCH Mix'):
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
        bs.name = 'MCH BSDF'
        nt.links.new(bs.outputs[0], out.inputs['Surface'])
        av = nt.nodes.new('ShaderNodeAttribute')
        av.attribute_name = 'mch_om_var'
        ap = nt.nodes.new('ShaderNodeAttribute')
        ap.attribute_name = 'mch_om_pat'
        asp = nt.nodes.new('ShaderNodeAttribute')
        asp.attribute_name = 'mch_om_spot'
        mix = nt.nodes.new('ShaderNodeMix')
        mix.data_type = 'RGBA'
        mix.name = 'MCH Mix'
        nt.links.new(av.outputs['Fac'], mix.inputs[0])
        dark = nt.nodes.new('ShaderNodeMix')
        dark.data_type = 'RGBA'
        dark.name = 'MCH Dark'
        nt.links.new(mix.outputs[2], dark.inputs[6])
        nt.links.new(ap.outputs['Fac'], dark.inputs[0])
        spotm = nt.nodes.new('ShaderNodeMix')
        spotm.data_type = 'RGBA'
        spotm.name = 'MCH Spot'
        nt.links.new(dark.outputs[2], spotm.inputs[6])
        nt.links.new(asp.outputs['Fac'], spotm.inputs[0])
        nt.links.new(spotm.outputs[2], bs.inputs['Base Color'])
        glow = nt.nodes.new('ShaderNodeMath')
        glow.operation = 'MULTIPLY'
        glow.name = 'MCH Glow'
        nt.links.new(ap.outputs['Fac'], glow.inputs[0])
        nt.links.new(glow.outputs[0], bs.inputs['Emission Strength'])
        nt['mch_kind'] = pg.kind
    bs = nt.nodes['MCH BSDF']
    a, c = tuple(pg.color_a) + (1.0,), tuple(pg.color_b) + (1.0,)
    nt.nodes['MCH Mix'].inputs[6].default_value = a
    nt.nodes['MCH Mix'].inputs[7].default_value = tuple(x * 0.5 + y * 0.5 for x, y in zip(a, c))
    nt.nodes['MCH Dark'].inputs[7].default_value = c
    nt.nodes['MCH Spot'].inputs[7].default_value = tuple(pg.color_b) + (1.0,)
    glow = float(look.get('glow', 0.0)) * pg.glow
    nt.nodes['MCH Glow'].inputs[1].default_value = 6.0 * glow
    try:
        bs.inputs['Emission Color'].default_value = (1.0, 0.32, 0.05, 1.0)
        bs.inputs['Roughness'].default_value = float(look.get('rough', 0.6))
        bs.inputs['Transmission Weight'].default_value = float(look.get('glass', 0.0))
        bs.inputs['Subsurface Weight'].default_value = float(look.get('sss', 0.0))
        bs.inputs['Subsurface Radius'].default_value = (0.2, 0.06, 0.04)
        bs.inputs['Subsurface Scale'].default_value = 0.03
    except KeyError:
        pass
    mat.diffuse_color = a
    return mat


def data(ob):
    try:
        return json.loads(ob.get(KEY, '{}'))
    except ValueError:
        return {}


def _mesh_key(P2, holes, pg, spec, live):
    """What a lump's base mesh is made from (a surface or colour slider is not in it: the mesh is kept)."""
    if pg.stick or spec[3] == 'CRYSTAL':
        return ''                                     # (on a part - it may have moved; crystals: quick anyway)
    crc = zlib.crc32(np.ascontiguousarray(P2).tobytes())
    for h in holes:
        crc = zlib.crc32(np.ascontiguousarray(h).tobytes(), crc)
    vals = [spec[3], crc, round(float(pg.depth), 6), round(float(pg.back), 6)]
    if spec[3] == 'FORM':
        vals += [pg.kind, int(pg.resolution), int(pg.edge_steps), round(float(pg.edge_width), 6),
                 round(float(pg.jag), 6), round(float(pg.slope), 6), round(float(pg.turn), 6), int(pg.seed),
                 int(pg.count), round(float(pg.pattern_width), 6), pg.surface == 'NONE', bool(pg.remesh), bool(live)]
    else:
        vals.append(spec[3] == 'PLATE')
    return repr(vals)


def _finish():
    """The full mesh of every lump whose slider has stopped (a timer)."""
    now = time.monotonic()
    for name, t in list(_PENDING.items()):
        if now - t >= 0.3:
            del _PENDING[name]
            ob = bpy.data.objects.get(name)
            if ob is not None and is_mass(ob):
                try:
                    build(ob, bpy.context)
                except Exception as ex:
                    print('Creature Base Mesh 2:', ex)
    return 0.1 if _PENDING else None


def settle(ob, context=None):
    """A lump still showing its quick (dragging) mesh: its full one now."""
    if _PENDING.pop(ob.name, None) is not None:
        build(ob, context or bpy.context)


def build(ob, context=None, live=False):
    """The lump again from its outline and sliders; returns the base mesh's face count.  A converted mesh (Click a
    Mesh) keeps its own mesh: only its surface is laid again.  ``live`` (a slider being dragged): quick - a form at a
    share of its Resolution and not merged light yet, a lump remeshed coarser; the full one follows (``_finish``)."""
    d = data(ob)
    pg = ob.mch_omass
    spec = KIND[pg.kind]
    me = ob.data
    if d.get('converted'):
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        if not len(co):
            return 0
        lo, hi = co.min(0), co.max(0)
        P2 = np.array([[lo[0], lo[1]], [hi[0], lo[1]], [hi[0], hi[1]], [lo[0], hi[1]]])
        size = float((hi - lo).max())
    else:
        P2 = np.asarray(d.get('outline', []), float)
        if len(P2) < 3:
            return 0
        holes = [np.asarray(h, float) for h in d.get('holes', [])]
        key = _mesh_key(P2, holes, pg, spec, live)
        same = bool(key) and ob.get(MESH_KEY) == key and len(me.vertices) > 0
        if same:
            pass                                      # (only its surface / colours changed: the base mesh stays)
        elif spec[3] == 'CRYSTAL':
            V, F = crystals(P2, pg, int(pg.seed))
            RD = np.full(len(V), 1e3)
        elif spec[3] == 'FORM':
            V, F, RD = form_mesh(P2, holes, pg, res=int(pg.resolution) * LIVE_RES if live else None)
        else:
            V, F, RD = lump(P2, holes, pg)
        if not same:
            V = stick(context, ob, np.asarray(V, float), d) if pg.stick else V
            me.clear_geometry()
            me.from_pydata([tuple(v) for v in V], [], [list(map(int, f)) for f in F])
            me.validate(clean_customdata=False)
            at = me.attributes.get(RD_ATTR) or me.attributes.new(RD_ATTR, 'FLOAT', 'POINT')
            if len(at.data) == len(RD):
                at.data.foreach_set('value', RD.astype(np.float32))
            ob[MESH_KEY] = key
        if spec[3] == 'FORM' and not same:            # (the wall's faces turned out, as the top's)
            import bmesh
            bm = bmesh.new()
            bm.from_mesh(me)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
            if pg.surface == 'NONE' and not pg.remesh and not live:
                # 0.24.183 (user: "너무 고밀도야, 가벼워야 돼") light: the flat and gently bent parts merged into big
                # faces (a tread, a slanted top, a facet: one face each) - only a fine surface keeps the fine points
                bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(5.0), use_dissolve_boundaries=False,
                                         verts=bm.verts[:], edges=bm.edges[:])
                bmesh.ops.dissolve_degenerate(bm, dist=size_of(P2) * 1e-5, edges=bm.edges[:])
                # (big hollow-sided faces split into convex ones: they draw, sculpt and boolean without trouble)
                bmesh.ops.connect_verts_concave(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
            bm.to_mesh(me)
            bm.free()
        me.update()
        size = float(np.ptp(P2, axis=0).max())
    mod = ob.modifiers.get(MOD)
    if mod is None:
        mod = ob.modifiers.new(MOD, 'NODES')
    if mod.node_group is None or mod.node_group.get('mch_v') != TREE_VERSION:
        mod.node_group = organic_tree()
    from . import geo_sculpt as gs
    w = spec[5]
    h, ax = hinge_axis(P2)
    cc = cap_centre(P2)
    look = spec[7]
    remesh = pg.remesh if (d.get('converted') or spec[3] == 'FORM') else spec[3] != 'CRYSTAL'
    vals = {'Remesh': remesh, 'Voxel': size / max(int(pg.resolution * (0.6 if live else 1.0)), 8), 'Smooth': int(pg.smooth),
            'Size': size, 'Seed': float(pg.seed % 997), 'Pattern Scale': float(pg.pattern_scale),
            'Pattern Width': float(pg.pattern_width), 'Count': float(pg.count),
            'Flat': bool(look.get('flat', False)) and (remesh or spec[3] == 'CRYSTAL'),
            'Hinge': (float(h[0]), float(h[1]), 0.0), 'Axis': (float(ax[0]), float(ax[1]), 0.0),
            'Centre': (float(cc[0]), float(cc[1]), 0.0), 'Material': material(ob)}
    surf = pg.surface != 'NONE'
    vals.update({'Has Edge': not d.get('converted'), 'Rough': surf, 'Rim': float(pg.r_rim),
                 'Center': float(pg.r_center), 'Strength': float(pg.r_strength) * size,
                 'Feature': float(pg.r_feature) * size, 'Chips': float(pg.r_chips)})
    for k, sock in (('r_bumps', 'Bumps'), ('r_cells', 'Cells'), ('r_cracks', 'Cracks'), ('r_wrinkles', 'Wrinkles'),
                    ('r_pits', 'Pits'), ('r_grain', 'Grain')):
        vals[sock] = float(getattr(pg, k))
    if surf and spec[3] == 'FORM' and not pg.remesh:
        vals['Remesh'] = False                        # (the form's own fine triangles carry it)
    scale_of = {'low': pg.lumps, 'det': pg.detail}
    nocol = set(spec[7].get('plain', ()))
    for f in FIELDS:
        vals['W ' + f] = float(w.get(f, 0.0)) * float(scale_of.get(f, pg.pattern))
        vals['C ' + f] = 0.0 if f in nocol else 1.0
    for k, v in vals.items():
        try:
            gs.set_input(mod, k, v)
        except (KeyError, AttributeError, TypeError):
            pass
    ob.update_tag()
    return len(me.polygons)


def _upd(self, context):
    if _BUSY[0]:
        return
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and is_mass(ob):
        live = not bpy.app.background                 # (in a window: quick now, the full mesh when the slider rests)
        try:
            build(ob, context, live=live)
        except Exception as ex:                       # (a slider never stops the window: said in the header)
            print('Creature Base Mesh 2:', ex)
        if live:
            _PENDING[ob.name] = time.monotonic()
            if not bpy.app.timers.is_registered(_finish):
                bpy.app.timers.register(_finish, first_interval=0.3)
        sc = getattr(context, 'scene', None)
        if sc is not None and hasattr(sc, 'mch_omass'):
            _BUSY[0] = True
            try:
                for k in LIVE:
                    setattr(sc.mch_omass, k, getattr(self, k))
            finally:
                _BUSY[0] = False


def _upd_kind(self, context):
    """A matter picked: its slider values and colours (then laid again)."""
    if _BUSY[0]:
        return
    spec = KIND[self.kind]
    _BUSY[0] = True
    try:
        for k, v in spec[4].items():
            setattr(self, k, v)
        if spec[3] != 'FORM':                         # (a lump: its pattern strongest at the edges, a little inside)
            self.r_rim, self.r_center = 0.3, 0.6
        self.color_a, self.color_b = spec[6]
        self.glow = 1.0
    finally:
        _BUSY[0] = False
    _upd(self, context)


LIVE = ('kind', 'stick', 'depth', 'back', 'lumps', 'detail', 'pattern', 'pattern_scale', 'pattern_width', 'count', 'resolution',
        'smooth', 'seed', 'color_a', 'color_b', 'glow', 'edge_steps', 'edge_width', 'jag', 'slope', 'turn', 'surface',
        'r_rim', 'r_center', 'r_strength', 'r_feature', 'r_chips', 'r_bumps', 'r_cells', 'r_cracks', 'r_wrinkles',
        'r_pits', 'r_grain')
SURF_LENGTHS = ('r_rim', 'r_strength', 'r_feature')        # (shares of the lump's size, as Plate Detail 4 saves them)
SURF_PLAIN = ('r_center', 'r_chips', 'r_bumps', 'r_cells', 'r_cracks', 'r_wrinkles', 'r_pits', 'r_grain')


_SURF = []


def _surface_items(_self, _context):
    """(kept: Blender needs the strings of a dynamic list to stay alive)"""
    if not _SURF:
        from . import plate_rough as pr
        _SURF.extend([('NONE', 'None', 'No fine texture: the big form as it is')] + [
            (pid, label, desc) for pid, label, desc, vals in pr.PRESETS if vals.get('r_style', 'ROUGH') == 'ROUGH'
            and pid not in {'BASALT', 'CLIFF'}])
    return _SURF
LIVE_CONVERT = ('remesh',)


class MCH_PG_OrganicMass(bpy.types.PropertyGroup):
    kind: EnumProperty(name='Form', items=KIND_ITEMS, default='SHARD', update=_upd_kind)
    depth: FloatProperty(name='Height', default=1.0, min=0.05, soft_max=2.0, max=4.0, update=_upd,
                         description='How thick it is toward you (1: about as thick as wide)')
    back: FloatProperty(name='Back', default=0.0, min=0.0, max=1.0, update=_upd,
                        description='The back: 1 as round as the front, 0 flat (a lump for a wall or a body)')
    lumps: FloatProperty(name='Lumps', default=0.0, min=0.0, soft_max=2.0, max=5.0, update=_upd,
                         description='Big bulges and dents all over it')
    detail: FloatProperty(name='Detail', default=0.0, min=0.0, soft_max=2.0, max=5.0, update=_upd,
                          description='Fine surface grain')
    pattern: FloatProperty(name='Pattern', default=1.0, min=0.0, soft_max=2.0, max=5.0, update=_upd,
                           description='The matter\'s own pattern: Rock cracks, Coral grooves, Bone / Sponge pores, Flesh '
                                       'veins, Mushroom gills and spots, Shell ribs, Big Scale keel, Bark fissures, '
                                       'Crystal: their thickness')
    pattern_scale: FloatProperty(name='Pattern Scale', default=1.0, min=0.1, soft_max=4.0, max=20.0, update=_upd,
                                 description='More, smaller (higher) or fewer, bigger cells / grooves / rings')
    pattern_width: FloatProperty(name='Pattern Width', default=1.0, min=0.1, soft_max=3.0, max=10.0, update=_upd,
                                 description='How wide the cracks / grooves / pores / ribs are')
    count: IntProperty(name='Count', default=6, min=2, soft_max=60, max=200, update=_upd,
                       description='Mushroom: gills; Shell: ribs; Crystal: crystals')
    resolution: IntProperty(name='Resolution', default=70, min=12, soft_max=320, max=600, update=_upd,
                            description='Points across it (more: finer surface, heavier; Ice: low for big facets)')
    smooth: IntProperty(name='Smooth', default=0, min=0, max=20, update=_upd,
                        description='Smoothed before its surface (softer)')
    seed: IntProperty(name='Seed', default=0, min=0, update=_upd)
    # 0.24.183 big forms
    edge_steps: IntProperty(name='Edge Steps', default=6, min=0, max=24, update=_upd,
                            description='The edges in steps (layers) - the accent at the edges; 0: a smooth rise')
    edge_width: FloatProperty(name='Edge Width', default=0.9, min=0.02, max=1.5, update=_upd,
                              description='How far in from the outline the steps go (1: to the middle)')
    jag: FloatProperty(name='Jagged', default=0.6, min=0.0, max=1.5, update=_upd,
                       description='The steps\' edges broken and wandering (0: even, like contour lines)')
    slope: FloatProperty(name='Slope', default=0.4, min=0.0, max=1.0, update=_upd,
                         description='Layered Shard: how much of the top is the one big slanted face')
    turn: FloatProperty(name='Turn', default=0.0, min=-math.pi, max=math.pi, subtype='ANGLE', update=_upd,
                        description='Which way it rises (Shard), the plates / folds run (turned round)')
    # 0.24.183 the fine texture on top (Plate Detail 4's): strongest at the edges
    surface: EnumProperty(name='Surface', items=_surface_items, update=_upd,
                          description='A Plate Detail 4 surface on the form (strongest at its edges)')
    r_rim: FloatProperty(name='Rim Width', default=0.15, min=0.0, max=2.0, update=_upd,
                         description='How far in from the edge the surface is strong (a share of its size)')
    r_center: FloatProperty(name='Center', default=0.2, min=0.0, max=1.0, update=_upd,
                            description='How much of the surface in the middle (1: as strong as at the edges)')
    r_strength: FloatProperty(name='Strength', default=0.01, min=0.0, max=0.5, precision=4, update=_upd,
                              description='How deep / high the surface goes (a share of its size)')
    r_feature: FloatProperty(name='Feature Size', default=0.03, min=0.001, max=1.0, precision=4, update=_upd,
                             description='Size of one lump / stone / pit (a share of its size)')
    r_chips: FloatProperty(name='Chips', default=0.0, min=0.0, max=1.0, update=_upd,
                           description='Bites taken in from the edge')
    r_bumps: FloatProperty(name='Bumps', default=0.0, min=-1.0, max=1.0, update=_upd)
    r_cells: FloatProperty(name='Cells', default=0.0, min=-1.0, max=1.0, update=_upd)
    r_cracks: FloatProperty(name='Cracks', default=0.0, min=-1.0, max=1.0, update=_upd)
    r_wrinkles: FloatProperty(name='Wrinkles', default=0.0, min=-1.0, max=1.0, update=_upd)
    r_pits: FloatProperty(name='Pits', default=0.0, min=-1.0, max=1.0, update=_upd)
    r_grain: FloatProperty(name='Grain', default=0.0, min=-1.0, max=1.0, update=_upd)
    stick: bpy.props.BoolProperty(name='Stick to Surface', default=False, update=_upd,
                                  description='On: it lies on the part under the outline and follows its curve (as '
                                              'Creature Plate); off: a base mesh of its own (flat bottom)')
    remesh: bpy.props.BoolProperty(name='Remesh', default=False, update=_upd,
                                   description='A converted mesh: remeshed evenly first (off: its own points, a '
                                               'dense sculpt kept as it is)')
    color_a: FloatVectorProperty(name='Color', subtype='COLOR', size=3, min=0.0, max=1.0, default=(0.62, 0.6, 0.56),
                                 update=_upd)
    color_b: FloatVectorProperty(name='Pattern Color', subtype='COLOR', size=3, min=0.0, max=1.0,
                                 default=(0.2, 0.18, 0.16), update=_upd,
                                 description='In the cracks / grooves / pores (Mushroom: the spots)')
    glow: FloatProperty(name='Glow', default=1.0, min=0.0, soft_max=3.0, max=20.0, update=_upd,
                        description='Lava Rock: how bright its cracks glow')


# ---- drawing --------------------------------------------------------------------------------------------------------

def perform(context, loops, projector):
    """The outline -> a live lump facing the view (where the drawing sits on a mesh, at its depth)."""
    from . import base_mesh
    from . import core_geometry as cg
    groups = cg.prepare_loops(loops)
    if not groups:
        raise cg.CutError('Draw a bigger outline')
    outer, holes = max(groups, key=lambda g: abs(cg.signed_area(g[0])))     # (a sketch: its biggest shape)
    origin, X, Y, N = base_mesh.plane_frame(context, projector, groups)

    def local(lp):
        out = []
        for q in lp:
            o, dvec = projector.ray(q)
            o, dvec = Vector(o), Vector(dvec)
            den = dvec.dot(N)
            if abs(den) < 1e-9:
                continue
            p = o + dvec * ((origin - o).dot(N) / den)
            out.append(((p - origin).dot(X), (p - origin).dot(Y)))
        return np.array(out, float).reshape(-1, 2)
    P2 = local(outer)
    if len(P2) < 3 or float(np.ptp(P2, axis=0).max()) < 1e-6:
        raise cg.CutError('Draw the outline facing you')
    c = (P2.max(0) + P2.min(0)) * 0.5
    P2 = P2 - c
    if cg.signed_area([tuple(q) for q in P2]) < 0:
        P2 = P2[::-1]
    H = []
    for h in holes:
        q = local(h) - c
        if len(q) >= 3:
            H.append((q if cg.signed_area([tuple(x) for x in q]) > 0 else q[::-1]).round(7).tolist())
    st = context.scene.mch_omass
    me = bpy.data.meshes.new(KIND[st.kind][1])
    ob = bpy.data.objects.new(KIND[st.kind][1], me)
    (context.collection or context.scene.collection).objects.link(ob)
    M = Matrix.Identity(4)
    org = origin + X * float(c[0]) + Y * float(c[1])
    for r in range(3):
        M[r][0], M[r][1], M[r][2], M[r][3] = X[r], Y[r], N[r], org[r]
    ob.matrix_world = M
    rec = dict(outline=P2.round(7).tolist(), holes=H)
    try:                                              # 0.24.183 the part under it (Stick to Surface lies on it)
        _q, found = base_mesh.anchor_hit(context, projector, outer)
    except (AttributeError, RuntimeError, TypeError):
        found = None
    if found is not None and found[2] is not None and found[2].type == 'MESH':
        tgt = bpy.data.objects.get(found[2].name) or found[2]
        rec.update(target=tgt.name, frame=[list(r) for r in (tgt.matrix_world.inverted() @ M)])
        if context.scene.mch_omass.stick:
            ob.parent = tgt
            ob.matrix_parent_inverse = tgt.matrix_world.inverted()
    ob[KEY] = json.dumps(rec)
    _BUSY[0] = True
    try:
        for k in LIVE:
            setattr(ob.mch_omass, k, getattr(st, k))
    finally:
        _BUSY[0] = False
    build(ob, context)
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    return (f'{ob.name}: {KIND[st.kind][1]} in the drawn outline (live: its sliders lay it again) - Enter: keep')


def apply_mass(ob, context=None):
    """Kept as it is: the modifier applied (a plain mesh), no longer live.  A converted mesh: only this modifier
    (its own others - a Mirror - stay)."""
    context = context or bpy.context
    settle(ob, context)                               # (never applied as its quick, dragging mesh)
    if data(ob).get('converted') and ob.modifiers.get(MOD) is not None:
        try:
            with context.temp_override(object=ob, active_object=ob):
                bpy.ops.object.modifier_apply(modifier=MOD)
            for k in (KEY,):
                if k in ob.keys():
                    del ob[k]
            ob[DONE] = 1
            return len(ob.data.polygons)
        except RuntimeError:
            pass
    dg = context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev, depsgraph=dg)
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    me.name = old.name
    if old.users == 0:
        bpy.data.meshes.remove(old)
    for k in (KEY,):
        if k in ob.keys():
            del ob[k]
    ob[DONE] = 1
    return len(me.polygons)


# ---- Click a Mesh: a mesh you made gets the matter's surface (its shape kept) ------------------------------------------

HOW = (('DRAW', 'Draw', 'Draw an outline: a new lump of the matter in that shape'),
       ('CLICK', 'Click a Mesh', 'Click a mesh you made: its surface becomes the matter, its shape kept (Alt + click: '
                                 'back)'))


def convert(context, ob, pg_from=None):
    """0.24.183 (user: "어차피 라쏘로 내가 대략적인 외관은 정하니까 이렇게 오가닉한 표면으로 변환시키고 싶어서") ``ob``
    gets the matter (the window's) on its surface - its own mesh kept under the modifier (Remesh off for a dense one:
    its sculpt kept as it is)."""
    pg_from = pg_from or context.scene.mch_omass
    if not is_mass(ob):
        ob[KEY] = json.dumps({'converted': True})
    _BUSY[0] = True
    try:
        for k in LIVE:
            setattr(ob.mch_omass, k, getattr(pg_from, k))
        ob.mch_omass.remesh = len(ob.data.vertices) < 150000
        if ob.mch_omass.remesh:
            ob.mch_omass.resolution = max(ob.mch_omass.resolution, 220)
    finally:
        _BUSY[0] = False
    build(ob, context)


def back_to_shape(ob):
    """The converted mesh as it was (the modifier taken off)."""
    mod = ob.modifiers.get(MOD)
    if mod is not None:
        ob.modifiers.remove(mod)
    for k in (KEY, 'mch_omass_mat'):
        if k in ob.keys():
            del ob[k]


def pick(context, xy):
    from bpy_extras import view3d_utils
    region, rv3d = context.region, context.region_data
    if region is None or rv3d is None:
        return None
    o = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
    d = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy)
    try:
        hit, _loc, _n, _i, ob, _m = context.scene.ray_cast(context.evaluated_depsgraph_get(), o, d)
    except (RuntimeError, TypeError):
        return None
    ob = getattr(ob, 'original', ob) if hit else None
    return ob if ob is not None and ob.type == 'MESH' else None


class MCH_OT_omass_click(bpy.types.Operator):
    """Click a mesh you made: its surface becomes the matter, its shape kept.  Alt + click: back"""
    bl_idname = 'mch.omass_click'
    bl_label = 'Creature Base Mesh 2: Click a Mesh'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    clear: bpy.props.BoolProperty(default=False, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            return {'PASS_THROUGH'}
        if getattr(context.scene, 'mch_omass_how', 'DRAW') == 'DRAW':
            return {'PASS_THROUGH'}                     # (drawn: the lasso has the press)
        ob = pick(context, (event.mouse_region_x, event.mouse_region_y))
        if ob is None:
            return {'PASS_THROUGH'}
        return self._do(context, ob)

    def _do(self, context, ob):
        if self.clear:
            if not data(ob).get('converted'):
                self.report({'INFO'}, f'{ob.name}: not a converted mesh')
                return {'CANCELLED'}
            back_to_shape(ob)
            msg = f'{ob.name}: back to its shape'
        else:
            if is_mass(ob) and not data(ob).get('converted'):
                ob.mch_omass.kind = context.scene.mch_omass.kind       # (a lump made here: just its matter)
            else:
                convert(context, ob)
            msg = (f'{ob.name}: {KIND[ob.mch_omass.kind][1]} on its surface, its shape kept (live; Alt + click: '
                   f'back; Enter: keep)')
        for o in context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        self.report({'INFO'}, msg)
        return {'FINISHED'}

    def execute(self, context):
        ob = getattr(context.view_layer.objects, 'active', None)
        if ob is None or ob.type != 'MESH':
            return {'CANCELLED'}
        return self._do(context, ob)


def apply_targets(context):
    sel = [o for o in getattr(context, 'selected_objects', []) or [] if is_mass(o)]
    return sel or ([active_mass(context)] if active_mass(context) is not None else [])


class MCH_OT_omass_apply(bpy.types.Operator):
    """The selected Creature Base Mesh 2 lumps kept as they are (a plain mesh, no longer live)"""
    bl_idname = 'mch.omass_apply'
    bl_label = 'Apply Creature Base Mesh 2'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and bool(apply_targets(context))

    def execute(self, context):
        obs = apply_targets(context)
        n = sum(apply_mass(o, context) for o in obs)
        self.report({'INFO'}, f'Kept: {", ".join(o.name for o in obs)} ({n:,} faces)')
        return {'FINISHED'}


def surface_values(pid):
    """A Plate Detail 4 preset's texture values (lengths as shares of the size)."""
    from . import plate_rough as pr
    v = pr.preset_values(pid)
    return {k: v[k] for k in SURF_LENGTHS + SURF_PLAIN if k in v}


class MCH_OT_omass_surface(bpy.types.Operator):
    """This surface (Plate Detail 4's) on the form: strongest at its edges"""
    bl_idname = 'mch.omass_surface'
    bl_label = 'Creature Base Mesh 2 Surface'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    preset: bpy.props.StringProperty(default='NONE')
    mine: bpy.props.StringProperty(default='', description='One of your Plate Detail 4 presets')

    def execute(self, context):
        ob = active_mass(context)
        vals = {}
        pid = self.preset
        if self.mine:
            from . import my_presets as mp
            from .plate_detail import MY_KIND
            got = mp.load_all().get(MY_KIND, {}).get(self.mine)
            if not got:
                return {'CANCELLED'}
            vals = {k: got[k] for k in SURF_LENGTHS + SURF_PLAIN if k in got}
            pid = got.get('r_preset', 'CONCRETE')
            if pid in {'BASALT', 'CLIFF'}:
                pid = 'STONE'
        elif pid != 'NONE':
            vals = surface_values(pid)
        for pg in ([context.scene.mch_omass] + ([ob.mch_omass] if ob is not None else [])):
            _BUSY[0] = True
            try:
                for k, v in vals.items():
                    setattr(pg, k, v)
                pg.surface = pid
            finally:
                _BUSY[0] = False
        if ob is not None:
            build(ob, context)
        return {'FINISHED'}


class MCH_OT_omass_kind(bpy.types.Operator):
    """This matter (the selected lump too): its sliders and colours"""
    bl_idname = 'mch.omass_kind'
    bl_label = 'Creature Base Mesh 2 Matter'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    kind: EnumProperty(items=KIND_ITEMS)

    def execute(self, context):
        ob = active_mass(context)
        context.scene.mch_omass.kind = self.kind
        if ob is not None:
            ob.mch_omass.kind = self.kind
        return {'FINISHED'}


def draw(layout, context):
    from . import panel_capture as pc
    st = context.scene.mch_omass
    ob = active_mass(context)
    pg = ob.mch_omass if ob is not None else st
    layout.row(align=True).prop(context.scene, 'mch_omass_how', expand=True)
    col = layout.column(align=True)
    conv = ob is not None and data(ob).get('converted')
    layout.prop(pg, 'stick', toggle=True, icon='SNAP_FACE')          # 0.24.183 plate-like / base mesh
    col.label(text=(f'{ob.name}: {KIND[pg.kind][1]} (live{", converted" if conv else ""})' if ob is not None else
                    'The next lump: pick its matter'))
    form = KIND[pg.kind][3] == 'FORM'

    def tiles(kinds):
        entries = []
        for kid, label, _d, *_r in kinds:
            path, icon = pc.thumb('omass', kid)
            entries.append((label, path, icon, pg.kind == kid, 'mch.omass_kind', {'kind': kid}))
        pc.tiles(layout, entries, columns=4, scale=3.0)
    layout.label(text='Big Forms')
    tiles([k for k in KINDS if k[3] == 'FORM'])
    col = layout.column(align=True)
    if form:
        col.label(text='Form')
        col.prop(pg, 'depth')
        col.prop(pg, 'edge_steps')
        col.prop(pg, 'edge_width', slider=True)
        col.prop(pg, 'jag', slider=True)
        if pg.kind in FORM_COUNT:
            col.prop(pg, 'count', text=FORM_COUNT[pg.kind])
        if pg.kind == 'SHARD':
            col.prop(pg, 'slope', slider=True)
        if pg.kind in {'SHARD', 'PLATES', 'FOLDS', 'CREST'}:
            col.prop(pg, 'turn')
        if pg.kind == 'BLOCKS':
            col.prop(pg, 'pattern_width', text='Crack Width')
        col.prop(pg, 'back', slider=True)
    else:
        col.label(text='Shape')
        for k in ('depth', 'back', 'lumps', 'detail'):
            col.prop(pg, k, slider=k != 'depth')
        col = layout.column(align=True)
        col.label(text=f'Pattern: {PATTERN_NAME.get(pg.kind, "")}')
        col.prop(pg, 'pattern', text=PATTERN_NAME.get(pg.kind, 'Pattern'))
        col.prop(pg, 'pattern_scale')
        col.prop(pg, 'pattern_width')
        if pg.kind in COUNT_NAME:
            col.prop(pg, 'count', text=COUNT_NAME[pg.kind])
    # the fine surface (Plate Detail 4's presets and yours), strongest at the edges
    box = layout.box()
    box.label(text='Surface (Plate Detail 4): ' + (pg.surface.title() if pg.surface != 'NONE' else 'none'))
    entries = [('None', '', 0, pg.surface == 'NONE', 'mch.omass_surface', {'preset': 'NONE'})]
    for pid, label, _d in _surface_items(None, context)[1:]:
        path, icon = pc.thumb('rough', pid)
        entries.append((label, path, icon, pg.surface == pid, 'mch.omass_surface', {'preset': pid}))
    pc.tiles(box, entries, columns=4, scale=2.4)
    from . import my_presets as mp
    from .plate_detail import MY_KIND
    mine = mp.names(MY_KIND)
    if mine:
        box.label(text='My Presets (Plate Detail 4)')
        g = box.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
        for name in mine:
            g.operator('mch.omass_surface', text=name).mine = name
    if pg.surface != 'NONE':
        c2 = box.column(align=True)
        for k in ('r_strength', 'r_feature', 'r_rim', 'r_center', 'r_chips', 'r_bumps', 'r_cells', 'r_cracks',
                  'r_wrinkles', 'r_pits', 'r_grain'):
            c2.prop(pg, k, slider=True)
    more = getattr(context.scene, 'mch_omass_more', False)
    layout.prop(context.scene, 'mch_omass_more', text='Lumps (rock, mushroom, crystal ...)', icon='TRIA_DOWN' if more
                else 'TRIA_RIGHT', emboss=False)
    if more:
        tiles([k for k in KINDS if k[3] != 'FORM'])
    col = layout.column(align=True)
    col.label(text='Mesh')
    if conv or form:
        col.prop(pg, 'remesh')
    col.prop(pg, 'resolution')
    if not form or pg.remesh:
        col.prop(pg, 'smooth')
    col.prop(pg, 'seed')
    col = layout.column(align=True)
    col.label(text='Colors')
    r = col.row(align=True)
    r.prop(pg, 'color_a', text='')
    r.prop(pg, 'color_b', text='')
    if pg.kind == 'LAVA':
        col.prop(pg, 'glow')
    if ob is not None:
        row = layout.row(align=True)
        if conv:
            o = row.operator('mch.omass_click', text='Back to Shape')
            o.clear = True
        row.operator('mch.omass_apply', text='Apply (Enter)', icon='CHECKMARK')
    col = layout.column(align=True)
    for line in (HELP if getattr(context.scene, 'mch_omass_how', 'DRAW') == 'DRAW' else HELP_CLICK):
        col.label(text=line)


HELP = ('Draw an outline: a big form in that shape (flat bottom)',
        'Seen from where you drew: the outline is its outline',
        'Select a lump: its sliders lay it again;  Enter: keep')
HELP_CLICK = ('Click a mesh you made: its surface becomes the matter',
              'Its shape kept (Remesh off: a dense sculpt as it is)',
              'Alt + click: back to its shape;  Enter: keep')

CLASSES = (MCH_PG_OrganicMass, MCH_OT_omass_apply, MCH_OT_omass_kind, MCH_OT_omass_click, MCH_OT_omass_surface)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_omass = PointerProperty(type=MCH_PG_OrganicMass)
    bpy.types.Object.mch_omass = PointerProperty(type=MCH_PG_OrganicMass)
    bpy.types.Scene.mch_omass_how = EnumProperty(name='How', items=HOW, default='DRAW')
    bpy.types.Scene.mch_omass_more = bpy.props.BoolProperty(name='More', default=False)


def unregister():
    for T, attr in ((bpy.types.Scene, 'mch_omass'), (bpy.types.Object, 'mch_omass'), (bpy.types.Scene, 'mch_omass_how'),
                    (bpy.types.Scene, 'mch_omass_more')):
        if hasattr(T, attr):
            delattr(T, attr)
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
