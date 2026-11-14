"""0.24.161 Plate Detail 4 (Rough Rim): a raised plate whose outer rim is rough like concrete, stone or creature
skin - the detail strongest at the drawn outline and fading inward.

Draw a closed outline on a mesh -> a live plate on the surface under it (like Plate Detail 2 / 3).  The plate's
shape and its texture are a Geometry Nodes modifier, so every value changes at once until Apply:

* the base (made once from the outline, Python): the surface patch under the outline as a closed shell - a top
  layer on the surface, a bottom layer just under it, a skirt between - every point with its distance to the
  outline (``mch_rd``), whether it is on top (``mch_rtop``) and the surface normal there (``mch_rup``);
* the modifier: the shell subdivided (as fine as the texture needs), the top raised along the normal - a profile
  from the outline (Height, Edge Width, Edge shape), then the rim texture added: Bumps (lumps), Cells (rounded
  stones / scales), Cracks, Wrinkles (folds running along the outline), Pits (holes; minus = warts), Grain - each
  a mix amount, strongest within Rim Width of the outline, Center = how much of it inside; Chips breaks pieces
  off the edge (the outline eaten in, in round bites and in chunks).

Ten presets set the whole mix (Concrete, Broken Concrete, Rough Stone, Cobblestone, Lava Rock, Creature Skin,
Scaly Hide, Warty Hide, Bark, Eroded); every value can be changed after.
"""
from __future__ import annotations

import math

import bmesh
import bpy
import numpy as np

from .creature_fur import _B, _socket

MOD = 'MCH Rough Rim'
TREE = 'MCH Rough Rim'
TREE_VERSION = 5
D_ATTR = 'mch_rd'              # distance to the outline (object units)
TOP_ATTR = 'mch_rtop'          # 1 on the top layer, 0 on the bottom layer
UP_ATTR = 'mch_rup'            # the surface normal under the point
OUT_ATTR = 'mch_rough'         # the rim texture there (+ raised, - sunk) - for a material
MAX_FACES = 900_000
SINK_FRAC = 0.001              # where the plate comes down to nothing it goes this x its size under its top's start
                               # (the base top is 0.0004 x size above the surface, the bottom 0.0016 x size under it)            # the subdivided plate stays below this (the Detail is lowered for a big one)

PROFILES = (('ROUND', 'Round', 'The edge rises in a soft S (flat at the foot and at the top)'),
            ('DOME', 'Dome', 'Steep at the foot, rounding over into the top (stone, lumps)'),
            ('CHAMFER', 'Chamfer', 'A straight slope'))
PROFILE_INDEX = {p[0]: i for i, p in enumerate(PROFILES)}

# (prop, socket, label, description) - lengths (object units, scale with the drawn size)
LENGTH_PROPS = (
    ('r_height', 'Height', 'Height', 'Height of the plate above the surface', 0.2),
    ('r_ramp', 'Edge Width', 'Edge Width', 'How far in from the outline the plate reaches its full height (small = '
                                           'a steep slab edge, big = a soft mound)', 0.3),
    ('r_rim', 'Rim Width', 'Rim Width', 'How far in from the outline the texture is strong (it fades inward)', 0.5),
    ('r_strength', 'Strength', 'Strength', 'How deep / high the texture goes', 0.05),
    ('r_feature', 'Feature Size', 'Feature Size', 'Size of one lump / stone / pit of the texture', 0.2),
)   # (prop, socket, label, description, slider range: a drag across the slider; a bigger value drags as fast as it is big)
# (prop, socket, label, description, min, max) - the mix (no unit)
MIX_PROPS = (
    ('r_bumps', 'Bumps', 'Bumps', 'Rough lumps (stone, rock)', -1.0, 1.0),
    ('r_cells', 'Cells', 'Cells', 'Rounded stones / scales packed side by side (minus = dimples)', -1.0, 1.0),
    ('r_cracks', 'Cracks', 'Cracks', 'Thin cracks running through', -1.0, 1.0),
    ('r_wrinkles', 'Wrinkles', 'Wrinkles', 'Folds running along the outline (skin, bark)', -1.0, 1.0),
    ('r_pits', 'Pits', 'Pits', 'Holes (concrete air pockets, lava pores); minus = warts', -1.0, 1.0),
    ('r_grain', 'Grain', 'Grain', 'Fine grain all over', -1.0, 1.0),
)

# Presets: lengths as FRACTIONS of the drawn size, the rest as they are
PRESETS = (
    ('CONCRETE', 'Concrete', 'Cast slab: a firm edge with small chips, air pockets and grain along the rim',
     dict(r_height=0.025, r_ramp=0.012, r_profile='ROUND', r_rim=0.13, r_center=0.1, r_strength=0.008,
          r_feature=0.025, r_bumps=0.3, r_cells=0.0, r_cracks=0.3, r_wrinkles=0.0, r_pits=0.9, r_grain=0.4,
          r_chips=0.45)),
    ('BROKEN', 'Broken Concrete', 'Big chunks broken off the edge, cracks running in',
     dict(r_height=0.03, r_ramp=0.01, r_profile='ROUND', r_rim=0.18, r_center=0.05, r_strength=0.01,
          r_feature=0.04, r_bumps=0.3, r_cells=0.0, r_cracks=0.85, r_wrinkles=0.0, r_pits=0.4, r_grain=0.3,
          r_chips=1.0)),
    ('STONE', 'Rough Stone', 'Rounded lumps and chiselled hollows, a few bites out of the edge',
     dict(r_height=0.035, r_ramp=0.05, r_profile='DOME', r_rim=0.2, r_center=0.25, r_strength=0.022,
          r_feature=0.05, r_bumps=1.0, r_cells=0.0, r_cracks=0.35, r_wrinkles=0.0, r_pits=0.2, r_grain=0.3,
          r_chips=0.35)),
    ('COBBLE', 'Cobblestone', 'Rounded stones with grooves between them along the rim',
     dict(r_height=0.03, r_ramp=0.04, r_profile='DOME', r_rim=0.2, r_center=0.1, r_strength=0.016,
          r_feature=0.045, r_bumps=0.25, r_cells=1.0, r_cracks=0.3, r_wrinkles=0.0, r_pits=0.0, r_grain=0.2,
          r_chips=0.2)),
    ('LAVA', 'Lava Rock', 'Porous: full of pits and bubbles, lumpy',
     dict(r_height=0.03, r_ramp=0.03, r_profile='DOME', r_rim=0.22, r_center=0.35, r_strength=0.016,
          r_feature=0.04, r_bumps=0.6, r_cells=0.0, r_cracks=0.15, r_wrinkles=0.0, r_pits=1.0, r_grain=0.5,
          r_chips=0.4)),
    ('SKIN', 'Creature Skin', 'Soft folds along the edge, creases between them, fine pores',
     dict(r_height=0.03, r_ramp=0.08, r_profile='ROUND', r_rim=0.2, r_center=0.15, r_strength=0.009,
          r_feature=0.03, r_bumps=0.3, r_cells=0.0, r_cracks=0.3, r_wrinkles=1.0, r_pits=0.3, r_grain=0.25,
          r_chips=0.0)),
    ('SCALY', 'Scaly Hide', 'Small raised scales packed along the rim',
     dict(r_height=0.025, r_ramp=0.06, r_profile='ROUND', r_rim=0.18, r_center=0.2, r_strength=0.007,
          r_feature=0.018, r_bumps=0.2, r_cells=1.0, r_cracks=0.2, r_wrinkles=0.2, r_pits=0.0, r_grain=0.15,
          r_chips=0.0)),
    ('WARTY', 'Warty Hide', 'Warts and lumps of many sizes, toad-like',
     dict(r_height=0.03, r_ramp=0.07, r_profile='DOME', r_rim=0.22, r_center=0.3, r_strength=0.018,
          r_feature=0.035, r_bumps=0.5, r_cells=0.0, r_cracks=0.0, r_wrinkles=0.2, r_pits=-1.0, r_grain=0.3,
          r_chips=0.0)),
    ('BARK', 'Bark', 'Deep ridges and furrows running along the edge, split by cracks',
     dict(r_height=0.03, r_ramp=0.04, r_profile='ROUND', r_rim=0.22, r_center=0.2, r_strength=0.016,
          r_feature=0.04, r_bumps=0.35, r_cells=0.0, r_cracks=0.6, r_wrinkles=1.0, r_pits=0.0, r_grain=0.3,
          r_chips=0.3)),
    ('ERODED', 'Eroded', 'Worn sandstone: soft hollows and smoothed bites out of the edge',
     dict(r_height=0.035, r_ramp=0.06, r_profile='ROUND', r_rim=0.25, r_center=0.15, r_strength=0.016,
          r_feature=0.06, r_bumps=0.7, r_cells=0.0, r_cracks=0.0, r_wrinkles=0.4, r_pits=0.5, r_grain=0.1,
          r_chips=0.5)),
    # 0.24.163 (user: "주상절리 같은 절벽 스타일도 - 긋는 방향 따라 높은 곳이 대각선으로 달라지게"): real columns, not a texture
    ('BASALT', 'Columnar Basalt', 'Basalt columns (주상절리): a cliff of 5 - 7 sided columns, rising along the way the '
     'outline was drawn - low where it started, high at the far end',
     dict(r_style='COLUMNS', r_height=0.18, r_feature=0.05, r_slope=0.85, r_hrand=0.3, r_gap=0.003, r_round=0.0025,
          r_tilt=math.radians(5.0), r_turn=0.0, r_flip=False)),
)
PRESET_IDS = tuple(p[0] for p in PRESETS)
COLUMN_LENGTHS = ('r_gap', 'r_round')       # (0.24.163 Columnar Basalt's lengths - not modifier inputs)
LENGTHS = tuple(p[0] for p in LENGTH_PROPS) + COLUMN_LENGTHS
PLAIN = ('r_profile', 'r_center', 'r_chips', 'r_seed', 'r_detail', 'r_preset', 'r_style', 'r_slope', 'r_hrand', 'r_tilt',
         'r_turn', 'r_flip') + tuple(p[0] for p in MIX_PROPS)
COLUMN_DEFAULT = dict(next(p[3] for p in PRESETS if p[0] == 'BASALT'))
DEFAULT = dict(COLUMN_DEFAULT, **PRESETS[0][3], r_style='ROUGH', r_seed=0, r_detail=6.0, r_preset='CONCRETE')


def preset_values(pid):
    """Every value a preset sets (a rough one: style Rough; Columnar Basalt: style Columns)."""
    return dict({'r_style': 'ROUGH'}, **next((p[3] for p in PRESETS if p[0] == pid), PRESETS[0][3]), r_preset=pid)


# -----------------------------------------------------------------------------
# The base shell (Python, once per outline)
# -----------------------------------------------------------------------------

def build_base(region_me, embed, lift, name='MCH_PlateRough'):
    """The patch under the outline as a closed shell (top on the surface, bottom ``embed`` under it, a skirt),
    with the distance to the outline, top / bottom and the surface normal on every point.  Returns (mesh, mean
    edge length of the patch)."""
    from .plate_detail import _boundary_loop, _seg_arrays, dist_to_segments
    bm = bmesh.new()
    try:
        bm.from_mesh(region_me)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        loops = _boundary_loop(bm)
        if not loops or not bm.faces:
            raise ValueError('empty region')
        A, B = _seg_arrays(loops)
        bm.normal_update()
        bm.verts.index_update()
        co = np.array([tuple(v.co) for v in bm.verts])
        nrm = np.array([tuple(v.normal) for v in bm.verts])
        dist = dist_to_segments(co, A, B)
        edge = float(np.mean([e.calc_length() for e in bm.edges])) if bm.edges else 0.0
        n = len(co)
        out = np.concatenate([co + nrm * lift, co + nrm * (lift - embed)])
        faces = []
        for f in bm.faces:
            idx = [v.index for v in f.verts]
            faces.append(idx)
            faces.append([n + i for i in reversed(idx)])
        for e in bm.edges:
            if len(e.link_faces) == 1:
                a, b = (v.index for v in e.verts)
                faces.append([a, b, n + b, n + a])                      # (turned the right way below)
    finally:
        bm.free()
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(c) for c in out], [], faces)
    me.validate()
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.to_mesh(me)
    finally:
        bm.free()
    for nm, typ, vals, field in ((D_ATTR, 'FLOAT', np.concatenate([dist, dist]), 'value'),
                                 (TOP_ATTR, 'FLOAT', np.concatenate([np.ones(n), np.zeros(n)]), 'value'),
                                 (UP_ATTR, 'FLOAT_VECTOR', np.concatenate([nrm, nrm]).ravel(), 'vector')):
        at = me.attributes.new(nm, typ, 'POINT')
        at.data.foreach_set(field, np.asarray(vals, np.float32).ravel())
    me.shade_smooth()
    me.update()
    return me, edge


# -----------------------------------------------------------------------------
# 0.24.163 Columnar Basalt (주상절리): real columns, not a texture
# -----------------------------------------------------------------------------

MAX_COLUMNS = 4000                 # (a smaller Column Size than this allows on a big plate is made bigger)


def _cells(seeds, inside):
    """Voronoi cells of the seeds marked ``inside`` (2D, from a Delaunay triangulation: each cell = the circumcentres
    of its triangles round its seed).  Returns {seed index: [(x, y), ...] counter-clockwise}."""
    from mathutils import Vector, geometry
    out = geometry.delaunay_2d_cdt([Vector(q) for q in seeds], [], [], 0, 1e-9, True)
    verts, tris, orig = out[0], out[2], out[3]
    to_in = {}
    for k, ids in enumerate(orig):
        for i in ids:
            to_in.setdefault(k, i)
    V = np.array([tuple(v) for v in verts])
    around = {}
    for t in tris:
        a, b, c = V[t[0]], V[t[1]], V[t[2]]
        d = 2.0 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]))
        if abs(d) < 1e-14:
            continue
        a2, b2, c2 = a @ a, b @ b, c @ c
        cc = ((a2 * (b[1] - c[1]) + b2 * (c[1] - a[1]) + c2 * (a[1] - b[1])) / d,
              (a2 * (c[0] - b[0]) + b2 * (a[0] - c[0]) + c2 * (b[0] - a[0])) / d)
        for k in t:
            i = to_in.get(k)
            if i is not None and inside[i]:
                around.setdefault(i, []).append(cc)
    cells = {}
    for i, cs in around.items():
        if len(cs) < 3:
            continue
        sx, sy = seeds[i]
        cs.sort(key=lambda q: math.atan2(q[1] - sy, q[0] - sx))
        cells[i] = cs
    return cells


def _inside_poly(px, py, poly):
    """Point-in-polygon for many points (numpy, even-odd)."""
    inside = np.zeros(len(px), bool)
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        cross = (y1 > py) != (y2 > py)
        with np.errstate(divide='ignore', invalid='ignore'):
            xi = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
        inside ^= cross & (px < xi)
    return inside


def stroke_dir(region_me, loops, projector, target):
    """0.24.163 "긋는 방향따라": the way the outline was drawn, on the surface (target space) - from where it started
    toward the outline point farthest from there.  None if it cannot be found."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    try:
        lp = list(loops[0])
        s0 = lp[0]
        s1 = max(lp, key=lambda q: (q[0] - s0[0]) ** 2 + (q[1] - s0[1]) ** 2)
    except (IndexError, TypeError):
        return None
    bvh = BVHTree.FromPolygons([v.co for v in region_me.vertices], [tuple(f.vertices) for f in region_me.polygons])
    inv = target.matrix_world.inverted()
    hits = []
    for xy in (s0, s1):
        o, d = projector.ray(xy)
        o = inv @ Vector(o)
        d = (inv.to_3x3() @ Vector(d)).normalized()
        loc, _n, _i, _dist = bvh.ray_cast(o, d)
        if loc is None:                                  # (the outline's own point is on the patch's border)
            loc, _n, _i, _dist = bvh.find_nearest(o + d * ((Vector(region_me.vertices[0].co) - o).dot(d)))
        if loc is None:
            return None
        hits.append(loc)
    v = hits[1] - hits[0]
    return tuple(v) if v.length > 1e-9 else None


def build_columns(p, region_me, name, embed, lift=0.0):
    """0.24.163 Columnar Basalt: the patch under the outline as basalt columns - Voronoi cells (mostly 5 - 7 sided, the
    seeds a jittered hexagon grid of Column Size), each a straight prism along the surface's mean normal, its foot
    following the surface (sunk ``embed`` into it), its top flat (Top Tilt: a little tilted at random, Edge Round: a
    chamfer), Joint Gap between them.  Its height rises along the way the outline was drawn (``p.r_dir``; Turn / Flip):
    Slope 0 all as tall as Height, Slope 1 from nothing where the drawing started to Height at the far end; Height
    Random varies each."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    from .plate_detail import _boundary_loop
    bm = bmesh.new()
    try:
        bm.from_mesh(region_me)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        loops = _boundary_loop(bm)
        if not loops or not bm.faces:
            raise ValueError('empty region')
        nrm = Vector()
        cen = Vector()
        area = 0.0
        for f in bm.faces:
            a = f.calc_area()
            nrm += f.normal * a
            cen += f.calc_center_median() * a
            area += a
        cen /= max(area, 1e-12)
        if nrm.length < 1e-9:
            raise ValueError('flat region has no direction')
        nrm.normalize()
        outline = max(loops, key=len)
        out3 = [v.co.copy() for v in outline]
    finally:
        bm.free()
    u = nrm.orthogonal().normalized()
    dvec = Vector(getattr(p, 'r_dir', (0.0, 0.0, 0.0)))
    dvec = dvec - nrm * dvec.dot(nrm)
    if dvec.length > 1e-9:
        u = dvec.normalized()
    w = nrm.cross(u).normalized()
    turn = float(getattr(p, 'r_turn', 0.0)) + (math.pi if getattr(p, 'r_flip', False) else 0.0)
    ramp = (u * math.cos(turn) + w * math.sin(turn)).normalized()      # (the way the columns rise)
    poly = [((q - cen).dot(u), (q - cen).dot(w)) for q in out3]
    P = np.array(poly)
    lo, hi = P.min(0), P.max(0)
    col = max(float(p.r_feature), 1e-6)
    area2 = float((hi - lo).prod())
    col = max(col, math.sqrt(area2 / MAX_COLUMNS))                       # (never more than MAX_COLUMNS columns)
    rng = np.random.default_rng(int(p.r_seed) * 7919 + 17)
    dy = col * math.sqrt(3.0) / 2.0
    xs = np.arange(lo[0] - 2 * col, hi[0] + 2 * col, col)
    ys = np.arange(lo[1] - 2 * dy, hi[1] + 2 * dy, dy)
    gx, gy = np.meshgrid(xs, ys)
    gx = gx + (np.arange(len(ys))[:, None] % 2) * col * 0.5
    seeds = np.stack([gx.ravel(), gy.ravel()], 1)
    seeds = seeds + rng.uniform(-0.3, 0.3, seeds.shape) * col             # (not a perfect honeycomb: 5 - 7 sided)
    inside = _inside_poly(seeds[:, 0], seeds[:, 1], poly)
    cells = _cells(seeds, inside)
    if not cells:
        raise ValueError('outline too small for one column')
    bvh = BVHTree.FromPolygons([v.co for v in region_me.vertices], [tuple(f.vertices) for f in region_me.polygons])
    far = float(np.abs(P).max()) * 4.0 + 1.0

    def ground(x, y):
        o = cen + u * x + w * y + nrm * far
        loc, _n, _i, _d = bvh.ray_cast(o, -nrm)
        if loc is None:
            loc, _n, _i, _d = bvh.find_nearest(cen + u * x + w * y)
        return (loc - cen).dot(nrm)
    cxy = np.array([seeds[i] for i in cells])
    rx = cxy[:, 0] * ramp.dot(u) + cxy[:, 1] * ramp.dot(w)
    t = (rx - rx.min()) / max(rx.max() - rx.min(), 1e-9)                 # (0 where the drawing started, 1 at the far end)
    H = float(p.r_height)
    slope = float(p.r_slope)
    hr = float(p.r_hrand)
    gap = float(p.r_gap)
    rnd = float(p.r_round)
    tilt = float(p.r_tilt)
    verts, faces, colr = [], [], []
    for k, (i, cell) in enumerate(cells.items()):
        c = np.array(cell)
        sx, sy = c.mean(0)
        rr = rng.random(3)
        h = H * (1.0 - slope + slope * t[k]) * (1.0 + hr * (rr[0] - 0.5) * 2.0)
        if h <= H * 0.01:
            continue
        # the joint: the cell shrunk toward its middle by half the gap
        d = c - (sx, sy)
        rad = np.linalg.norm(d, axis=1)
        inr = max(min(rad) * 0.85, 1e-9)
        sh = max(0.0, 1.0 - gap * 0.5 / inr)
        c = (sx, sy) + d * sh
        foot = min(ground(x, y) for x, y in list(c) + [(sx, sy)]) - embed
        base_h = ground(sx, sy)
        ang = rr[1] * 2 * math.pi
        tt = math.tan(tilt * rr[2])
        top = [base_h + h + ((x - sx) * math.cos(ang) + (y - sy) * math.sin(ang)) * tt for x, y in c]
        r_in = min(rnd, inr * sh * 0.45, h * 0.45)
        n = len(c)
        b0 = len(verts)
        for x, y in c:                                                     # foot (on the surface)
            verts.append(cen + u * x + w * y + nrm * min(foot, ground(x, y) - embed))
        for (x, y), z in zip(c, top):                                      # the top edge (under the chamfer)
            verts.append(cen + u * x + w * y + nrm * (z - r_in))
        faces.append([b0 + j for j in reversed(range(n))])
        for j in range(n):
            j2 = (j + 1) % n
            faces.append([b0 + j, b0 + j2, b0 + n + j2, b0 + n + j])
        if r_in > 1e-7:
            f_in = max(0.0, 1.0 - r_in / (inr * sh))
            t0 = len(verts)
            for (x, y), z in zip(c, top):
                verts.append(cen + u * (sx + (x - sx) * f_in) + w * (sy + (y - sy) * f_in) + nrm * z)
            for j in range(n):
                j2 = (j + 1) % n
                faces.append([b0 + n + j, b0 + n + j2, t0 + j2, t0 + j])
            faces.append([t0 + j for j in range(n)])
            colr += [rr[0]] * (3 * n)
        else:
            faces.append([b0 + n + j for j in range(n)])
            colr += [rr[0]] * (2 * n)
    if not faces:
        raise ValueError('no column tall enough')
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v + nrm * lift) for v in verts], [], faces)
    me.validate()
    at = me.attributes.new('mch_column', 'FLOAT', 'POINT')               # (each column its own random 0 - 1: a material can
    at.data.foreach_set('value', np.asarray(colr, np.float32))           #  vary the stone with it)
    me.shade_flat()
    me.update()
    return me


# -----------------------------------------------------------------------------
# The node group
# -----------------------------------------------------------------------------

def _inputs(ng):
    _socket(ng, 'Geometry', 'GEOMETRY')
    _socket(ng, 'Level', 'INT', 3, 0, 7)
    _socket(ng, 'Profile', 'INT', 0, 0, 2)
    for _p, sock, *_r in LENGTH_PROPS:
        _socket(ng, sock, 'FLOAT', 0.01, 0.0, 100.0)
    _socket(ng, 'Center', 'FLOAT', 0.1, 0.0, 1.0)
    _socket(ng, 'Chips', 'FLOAT', 0.0, 0.0, 1.0)
    for _p, sock, _l, _d, lo, hi in MIX_PROPS:
        _socket(ng, sock, 'FLOAT', 0.0, lo, hi)
    _socket(ng, 'Seed', 'INT', 0, 0, 100000)
    _socket(ng, 'Lift', 'FLOAT', 0.0, -100.0, 100.0)
    _socket(ng, 'Sink', 'FLOAT', 0.0, 0.0, 100.0)
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')


def _map(b, value, lo, hi, to_lo, to_hi, interp='LINEAR'):
    n = b.node('ShaderNodeMapRange', data_type='FLOAT', interpolation_type=interp)
    for i, v in enumerate((value, lo, hi, to_lo, to_hi)):
        b.feed(n.inputs[i], v)
    n.clamp = True
    return n.outputs['Result']


def _noise(b, q, w, scale=1.0, detail=4.0, rough=0.55):
    """3D noise at ``q`` (1 = one feature) shifted by the seed vector ``w``."""
    n = b.node('ShaderNodeTexNoise', noise_dimensions='3D')
    b.feed(n.inputs['Vector'], b.vec('ADD', q, w))
    n.inputs['Scale'].default_value = scale
    n.inputs['Detail'].default_value = detail
    n.inputs['Roughness'].default_value = rough
    return n


def _voronoi(b, q, w, scale=1.0, feature='F1'):
    n = b.node('ShaderNodeTexVoronoi', voronoi_dimensions='3D', feature=feature)
    b.feed(n.inputs['Vector'], b.vec('ADD', q, w))
    n.inputs['Scale'].default_value = scale
    n.inputs['Randomness'].default_value = 1.0
    return n


def _rgb(b, col):
    s = b.node('FunctionNodeSeparateColor')
    b.feed(s.inputs[0], col)
    return s.outputs


def _clamp01(b, v):
    return b.math('MINIMUM', b.math('MAXIMUM', v, 0.0), 1.0)


def _when(b, weight, field):
    """``field`` only when ``weight`` is not 0, else 0 (the field is then never worked out: a channel at 0 costs
    nothing)."""
    sw = b.node('GeometryNodeSwitch', input_type='FLOAT')
    b.feed(sw.inputs['Switch'], b.math('GREATER_THAN', b.math('ABSOLUTE', weight), 1e-6))
    b.feed(sw.inputs['False'], 0.0)
    b.feed(sw.inputs['True'], field)
    return sw.outputs['Output']


def _seed(b, seed, k):
    """A seed vector for channel ``k`` (each channel its own pattern)."""
    c = b.node('ShaderNodeCombineXYZ')
    for i, f in enumerate((13.37, 7.71, 3.19)):
        b.feed(c.inputs[i], b.math('ADD', b.math('MULTIPLY', seed, f), 31.7 * k + 5.3 * i))
    return c.outputs['Vector']


def _profile(b, I, d2):
    ramp = b.math('MAXIMUM', I['Edge Width'], 1e-6)
    t = _clamp01(b, b.math('DIVIDE', d2, ramp))
    p_round = _map(b, t, 0.0, 1.0, 0.0, 1.0, 'SMOOTHERSTEP')
    p_dome = b.math('SINE', b.math('MULTIPLY', t, math.pi / 2))
    prof = b.math('ADD', b.math('ADD',
                                b.math('MULTIPLY', p_round, b.math('COMPARE', I['Profile'], 0.0, 0.5)),
                                b.math('MULTIPLY', p_dome, b.math('COMPARE', I['Profile'], 1.0, 0.5))),
                  b.math('MULTIPLY', t, b.math('COMPARE', I['Profile'], 2.0, 0.5)))
    return b.math('MULTIPLY', I['Height'], prof)


D2_ATTR = 'mch_rd2'            # (inside the node group only) the distance to the eaten outline


def _store_sel(b, geo, name, value, sel):
    n = b.node('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='POINT')
    b.feed(n.inputs['Geometry'], geo)
    b.feed(n.inputs['Selection'], sel)
    b.feed(n.inputs['Name'], name)
    b.feed(n.inputs['Value'], value)
    return n.outputs['Geometry']


def _build(b, I):
    """The subdivided shell; on its top: 1) the eaten outline stored, 2) the rim texture stored, 3) raised by the
    profile + texture; then all of it moved by Lift.  Each costly field is worked out once, on the top only."""
    sub = b.node('GeometryNodeSubdivideMesh')
    b.feed(sub.inputs['Mesh'], I['Geometry'])
    b.feed(sub.inputs['Level'], I['Level'])
    geo = sub.outputs['Mesh']

    d = b.attr(D_ATTR).outputs['Attribute']
    is_top = b.math('GREATER_THAN', b.attr(TOP_ATTR).outputs['Attribute'], 0.5)
    up = b.attr(UP_ATTR, 'FLOAT_VECTOR').outputs['Attribute']
    pos = b.node('GeometryNodeInputPosition').outputs['Position']
    feat = b.math('MAXIMUM', I['Feature Size'], 1e-6)
    q = b.vec('SCALE', pos, scale=b.math('DIVIDE', 1.0, feat))       # (1 = one feature)
    rim = b.math('MAXIMUM', I['Rim Width'], 1e-6)
    ramp = b.math('MAXIMUM', I['Edge Width'], 1e-6)
    seed = I['Seed']

    # 1) Chips: the outline eaten in - round bites (a slow noise) and whole chunks (half of the Voronoi cells)
    bite = _clamp01(b, b.math('MULTIPLY', b.math('SUBTRACT', _noise(b, q, _seed(b, seed, 1), 0.35, 3.0, 0.6)
                                                  .outputs['Factor'], 0.45), 4.0))
    cells = _rgb(b, _voronoi(b, q, _seed(b, seed, 2), 0.6).outputs['Color'])
    chunk = _clamp01(b, b.math('MULTIPLY', b.math('SUBTRACT', cells[0], 0.5), 2.5))
    eat = b.math('MULTIPLY', b.math('MULTIPLY', I['Chips'], b.math('MULTIPLY', rim, 0.6)), b.math('MAXIMUM', bite, chunk))
    geo = _store_sel(b, geo, D2_ATTR, b.math('SUBTRACT', d, _when(b, I['Chips'], eat)), is_top)
    d2 = b.attr(D2_ATTR).outputs['Attribute']

    # 2) the texture channels (about -1 .. 1 each), each only when its mix is not 0
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
    # folds along the outline: their spacing changes slowly, they wander and break into pieces (not even rings)
    spacing = b.math('MULTIPLY', feat, b.math('ADD', 0.38, b.math('MULTIPLY', _noise(b, q, _seed(b, seed, 12), 0.25, 1.0,
                                                                                   0.5).outputs['Factor'], 0.4)))
    wob = b.math('MULTIPLY', b.math('SUBTRACT', _noise(b, q, _seed(b, seed, 8), 0.7, 3.0, 0.55).outputs['Factor'], 0.5),
                 11.0)
    phase = b.math('ADD', b.math('MULTIPLY', b.math('DIVIDE', d, spacing), 2 * math.pi), wob)
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
    # strongest at the outline, Center inside; only where the plate is (from the outline over a third of the edge)
    m = _map(b, d2, 0.0, rim, 1.0, 0.0, 'SMOOTHSTEP')
    amount = b.math('ADD', I['Center'], b.math('MULTIPLY', b.math('SUBTRACT', 1.0, I['Center']), m))
    foot = _clamp01(b, b.math('DIVIDE', d2, b.math('MAXIMUM', b.math('MULTIPLY', ramp, 0.35), 1e-6)))
    geo = _store_sel(b, geo, OUT_ATTR, b.math('MULTIPLY', b.math('MULTIPLY', tex, amount), foot), is_top)
    rough = b.attr(OUT_ATTR).outputs['Attribute']

    # 3) raised: the profile from the eaten outline + the texture (never under the surface); where it comes down to
    #    nothing (a chip, the foot) it goes on down just under the surface - the surface shows there, not a thin film
    #    of the plate on it
    h = b.math('MAXIMUM', b.math('ADD', _profile(b, I, d2), b.math('MULTIPLY', rough, I['Strength'])), 0.0)
    low = b.math('MAXIMUM', b.math('MULTIPLY', I['Height'], 0.03), 1e-7)
    h = b.math('ADD', h, b.math('MULTIPLY', I['Sink'], b.math('SUBTRACT', _clamp01(b, b.math('DIVIDE', h, low)), 1.0)))
    sp = b.node('GeometryNodeSetPosition')
    b.feed(sp.inputs['Geometry'], geo)
    b.feed(sp.inputs['Selection'], is_top)
    b.feed(sp.inputs['Offset'], b.vec('SCALE', up, scale=h))
    geo = sp.outputs['Geometry']
    lift = b.node('GeometryNodeSetPosition')
    b.feed(lift.inputs['Geometry'], geo)
    b.feed(lift.inputs['Offset'], b.vec('SCALE', up, scale=I['Lift']))
    rm = b.node('GeometryNodeRemoveAttribute')
    b.feed(rm.inputs['Geometry'], lift.outputs['Geometry'])
    b.feed(rm.inputs['Name'], D2_ATTR)
    return rm.outputs['Geometry']


def tree():
    ng = bpy.data.node_groups.get(TREE)
    if ng is not None and ng.get('mch_v') == TREE_VERSION:
        return ng
    if ng is None:
        ng = bpy.data.node_groups.new(TREE, 'GeometryNodeTree')
    ng.nodes.clear()
    ng.interface.clear()
    _inputs(ng)
    b = _B(ng)
    gi = b.node('NodeGroupInput')
    go = b.node('NodeGroupOutput')
    b.feed(go.inputs[0], _build(b, gi.outputs))
    ng['mch_v'] = TREE_VERSION
    return ng


# -----------------------------------------------------------------------------
# The modifier on a live plate
# -----------------------------------------------------------------------------

def level_for(p, faces):
    """Subdivision level: about ``r_detail`` faces across one feature, kept under MAX_FACES."""
    edge = max(getattr(p, 'r_cell', 0.0), 1e-9)
    want = edge * max(p.r_detail, 0.5) / max(p.r_feature, 1e-9)
    lv = max(0, int(math.ceil(math.log2(max(want, 1.0)))))
    while lv > 0 and faces * 4 ** lv > MAX_FACES:
        lv -= 1
    return min(lv, 7)


def values(p, faces):
    """Modifier input values for settings ``p``."""
    v = {'Level': level_for(p, faces), 'Profile': PROFILE_INDEX.get(p.r_profile, 0), 'Center': float(p.r_center),
         'Chips': float(p.r_chips), 'Seed': int(p.r_seed), 'Lift': float(p.lift),
         'Sink': float(p.size) * SINK_FRAC}
    for prop, sock, *_r in LENGTH_PROPS:
        v[sock] = float(getattr(p, prop))
    for prop, sock, *_r in MIX_PROPS:
        v[sock] = float(getattr(p, prop))
    return v


def ensure(ob):
    mod = ob.modifiers.get(MOD)
    if mod is None or mod.type != 'NODES':
        mod = ob.modifiers.new(MOD, 'NODES')
    if mod.node_group is not tree():
        mod.node_group = tree()
    return mod


def push(ob, p=None):
    from . import geo_sculpt as gs
    p = p if p is not None else ob.mch_pdetail
    mod = ensure(ob)
    for name, val in values(p, len(ob.data.polygons)).items():
        gs.set_input(mod, name, val)
    return mod


def evaluated(context, p, base_me):
    """The finished plate mesh for settings ``p`` (a temporary object; the caller owns the mesh)."""
    ob = bpy.data.objects.new('MCH_RoughEval', base_me)
    context.scene.collection.objects.link(ob)
    try:
        push(ob, p)
        dg = context.evaluated_depsgraph_get()
        return bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    finally:
        bpy.data.objects.remove(ob)


def bake(context, ob):
    """Apply: the modifier made real; the helper attributes dropped."""
    if ob.modifiers.get(MOD) is not None:
        with context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
            bpy.ops.object.modifier_apply(modifier=MOD)
    me = ob.data
    for nm in (D_ATTR, TOP_ATTR, UP_ATTR):
        at = me.attributes.get(nm)
        if at is not None:
            me.attributes.remove(at)
