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

import bpy
import numpy as np
from bpy.props import EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, PointerProperty
from mathutils import Matrix, Vector

KEY = 'mch_omass'                 # on a live lump: its outline (local 2D) and how it sits (json)
DONE = 'mch_omass_done'
MOD = 'MCH Organic'
TREE = 'MCH Organic'
TREE_VERSION = 2
COLLECTION = None
_BUSY = [False]

# (id, label, description, base, slider values, recipe weights, colours (a, b), material look)
#   base: PUFF (inflated lump) | PLATE (a thin curved plate) | CRYSTAL (a cluster)
#   weights: how much of each surface field the matter has (x Lumps / Detail / Pattern)
KINDS = (
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
    ('FLESH', 'Flesh', 'A fleshy mass: soft lobes, raised veins', 'PUFF',
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
                'FLESH': 'Veins', 'ICE': 'Facets', 'SPONGE': 'Holes', 'BARK': 'Fissures'}
COUNT_NAME = {'MUSHROOM': 'Gills', 'CRYSTAL': 'Crystals', 'SHELL': 'Ribs'}
FIELDS = ('low', 'det', 'crk', 'wave', 'vein', 'pore', 'rib', 'ring', 'gill', 'keel', 'spot', 'bark')


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
    return V, F


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


# ---- the surface (Geometry Nodes) ---------------------------------------------------------------------------------

def _menu(sock, value):
    try:
        sock.default_value = value
    except (TypeError, ValueError, AttributeError):
        pass


def organic_tree():
    """The shared node group: remeshed evenly (or not: crystals), smoothed, the matter's surface along the normal;
    stores ``mch_om_var`` (big noise), ``mch_om_pat`` (its pattern: cracks, pores, gills...) and ``mch_om_spot``
    for the material."""
    from .creature_fur import _B, _socket
    ng = bpy.data.node_groups.get(TREE)
    if ng is not None and ng.get('mch_v') == TREE_VERSION:
        return ng
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
    terms = (('low', nlow, 0.12), ('det', ndet, 0.03), ('crk', crk, -0.03), ('wave', wave, -0.03),
             ('vein', vein, 0.012), ('pore', pore, -0.035), ('rib', rib, 0.022), ('ring', ring, 0.006),
             ('gill', gill, -0.035), ('keel', keel, 0.045), ('bark', bark, -0.04))
    off = None
    for f, val, k in terms:
        t_ = b.math('MULTIPLY', b.math('MULTIPLY', val, I['W ' + f]), k)
        off = t_ if off is None else b.math('ADD', off, t_)
    off = b.math('MULTIPLY', off, sz)
    sp = b.node('GeometryNodeSetPosition')
    b.feed(sp.inputs['Geometry'], geo)
    b.feed(sp.inputs['Offset'], b.vec('SCALE', N, scale=off))
    geo = sp.outputs['Geometry']
    # for the material (worked out where the points were before the offset: the same fields, stored)
    pat = None
    for f, val in (('crk', crk), ('pore', pore), ('gill', gill), ('vein', vein), ('bark', bark), ('wave', wave)):
        use = b.math('MINIMUM', b.math('MULTIPLY', I['W ' + f], 20.0), 1.0)
        t_ = b.math('MULTIPLY', val, use)
        pat = t_ if pat is None else b.math('MAXIMUM', pat, t_)
    geo = b.store(geo, 'mch_om_pat', b.math('MINIMUM', b.math('MAXIMUM', pat, 0.0), 1.0))
    geo = b.store(geo, 'mch_om_var', b.math('ADD', nlow, 0.5))
    geo = b.store(geo, 'mch_om_spot', b.math('MULTIPLY', spot, b.math('MINIMUM', b.math('MULTIPLY', I['W spot'], 20.0),
                                                                     1.0)))
    smooth = b.node('GeometryNodeSetShadeSmooth')
    b.feed(smooth.inputs['Mesh'], geo)
    b.feed(smooth.inputs['Shade Smooth'], b.math('SUBTRACT', 1.0, I['Flat']))
    sm = b.node('GeometryNodeSetMaterial')
    b.feed(sm.inputs['Geometry'], smooth.outputs['Mesh'])
    b.feed(sm.inputs['Material'], I['Material'])
    b.feed(go.inputs[0], sm.outputs['Geometry'])
    ng['mch_v'] = TREE_VERSION
    return ng


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


def build(ob, context=None):
    """The lump again from its outline and sliders; returns the base mesh's face count."""
    d = data(ob)
    P2 = np.asarray(d.get('outline', []), float)
    if len(P2) < 3:
        return 0
    holes = [np.asarray(h, float) for h in d.get('holes', [])]
    pg = ob.mch_omass
    spec = KIND[pg.kind]
    if spec[3] == 'CRYSTAL':
        V, F = crystals(P2, pg, int(pg.seed))
    else:
        V, F = lump(P2, holes, pg)
    me = ob.data
    me.clear_geometry()
    me.from_pydata([tuple(v) for v in V], [], [list(map(int, f)) for f in F])
    me.validate(clean_customdata=False)
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
    vals = {'Remesh': spec[3] != 'CRYSTAL', 'Voxel': size / max(int(pg.resolution), 8), 'Smooth': int(pg.smooth),
            'Size': size, 'Seed': float(pg.seed % 997), 'Pattern Scale': float(pg.pattern_scale),
            'Pattern Width': float(pg.pattern_width), 'Count': float(pg.count), 'Flat': bool(look.get('flat', False)),
            'Hinge': (float(h[0]), float(h[1]), 0.0), 'Axis': (float(ax[0]), float(ax[1]), 0.0),
            'Centre': (float(cc[0]), float(cc[1]), 0.0), 'Material': material(ob)}
    scale_of = {'low': pg.lumps, 'det': pg.detail}
    for f in FIELDS:
        vals['W ' + f] = float(w.get(f, 0.0)) * float(scale_of.get(f, pg.pattern))
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
        try:
            build(ob, context)
        except Exception as ex:                       # (a slider never stops the window: said in the header)
            print('Creature Base Mesh 2:', ex)
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
        self.color_a, self.color_b = spec[6]
        self.glow = 1.0
    finally:
        _BUSY[0] = False
    _upd(self, context)


LIVE = ('kind', 'depth', 'back', 'lumps', 'detail', 'pattern', 'pattern_scale', 'pattern_width', 'count', 'resolution',
        'smooth', 'seed', 'color_a', 'color_b', 'glow')


class MCH_PG_OrganicMass(bpy.types.PropertyGroup):
    kind: EnumProperty(name='Matter', items=KIND_ITEMS, default='ROCK', update=_upd_kind)
    depth: FloatProperty(name='Thickness', default=0.85, min=0.05, soft_max=2.0, max=4.0, update=_upd,
                         description='How thick it is toward you (1: about as thick as wide)')
    back: FloatProperty(name='Back', default=0.85, min=0.0, max=1.0, update=_upd,
                        description='The back: 1 as round as the front, 0 flat (a lump for a wall or a body)')
    lumps: FloatProperty(name='Lumps', default=1.0, min=0.0, soft_max=2.0, max=5.0, update=_upd,
                         description='Big bulges and dents all over it')
    detail: FloatProperty(name='Detail', default=1.0, min=0.0, soft_max=2.0, max=5.0, update=_upd,
                          description='Fine surface grain')
    pattern: FloatProperty(name='Pattern', default=1.0, min=0.0, soft_max=2.0, max=5.0, update=_upd,
                           description='The matter\'s own pattern: Rock cracks, Coral grooves, Bone / Sponge pores, Flesh '
                                       'veins, Mushroom gills and spots, Shell ribs, Big Scale keel, Bark fissures, '
                                       'Crystal: their thickness')
    pattern_scale: FloatProperty(name='Pattern Scale', default=1.0, min=0.1, soft_max=4.0, max=20.0, update=_upd,
                                 description='More, smaller (higher) or fewer, bigger cells / grooves / rings')
    pattern_width: FloatProperty(name='Pattern Width', default=1.0, min=0.1, soft_max=3.0, max=10.0, update=_upd,
                                 description='How wide the cracks / grooves / pores / ribs are')
    count: IntProperty(name='Count', default=8, min=2, soft_max=60, max=200, update=_upd,
                       description='Mushroom: gills; Shell: ribs; Crystal: crystals')
    resolution: IntProperty(name='Resolution', default=150, min=12, soft_max=320, max=600, update=_upd,
                            description='Points across it (more: finer surface, heavier; Ice: low for big facets)')
    smooth: IntProperty(name='Smooth', default=1, min=0, max=20, update=_upd,
                        description='Smoothed before its surface (softer)')
    seed: IntProperty(name='Seed', default=0, min=0, update=_upd)
    color_a: FloatVectorProperty(name='Color', subtype='COLOR', size=3, min=0.0, max=1.0, default=(0.36, 0.34, 0.31),
                                 update=_upd)
    color_b: FloatVectorProperty(name='Pattern Color', subtype='COLOR', size=3, min=0.0, max=1.0,
                                 default=(0.16, 0.15, 0.14), update=_upd,
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
    ob[KEY] = json.dumps(dict(outline=P2.round(7).tolist(), holes=H))
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
    """Kept as it is: the modifier applied (a plain mesh), no longer live."""
    dg = (context or bpy.context).evaluated_depsgraph_get()
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
    col = layout.column(align=True)
    col.label(text=f'{ob.name}: {pg.kind.title()} (live)' if ob is not None else 'The next lump: pick its matter')
    entries = []
    for kid, label, _d, *_r in KINDS:
        path, icon = pc.thumb('omass', kid)
        entries.append((label, path, icon, pg.kind == kid, 'mch.omass_kind', {'kind': kid}))
    pc.tiles(layout, entries, columns=4, scale=3.0)
    col = layout.column(align=True)
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
    col = layout.column(align=True)
    col.label(text='Mesh')
    col.prop(pg, 'resolution')
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
        layout.operator('mch.omass_apply', text='Apply (Enter)', icon='CHECKMARK')
    col = layout.column(align=True)
    for line in HELP:
        col.label(text=line)


HELP = ('Draw an outline: a lump of that matter in its shape',
        'Seen from where you drew: the outline is its outline',
        'Select a lump: its sliders lay it again;  Enter: keep')

CLASSES = (MCH_PG_OrganicMass, MCH_OT_omass_apply, MCH_OT_omass_kind)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_omass = PointerProperty(type=MCH_PG_OrganicMass)
    bpy.types.Object.mch_omass = PointerProperty(type=MCH_PG_OrganicMass)


def unregister():
    for T in (bpy.types.Scene, bpy.types.Object):
        if hasattr(T, 'mch_omass'):
            delattr(T, 'mch_omass')
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
