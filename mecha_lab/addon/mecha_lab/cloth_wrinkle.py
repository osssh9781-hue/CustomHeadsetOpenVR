"""0.20 Cloth Wrinkle: draw a lasso on a mesh -> a separate cloth layer with
procedural wrinkles (Geometry Nodes, live until Apply).

The patch is built like an Armor Plate (new clean faces laid on the surface,
the mesh you drew on is never changed), then put in its own frame (local Z =
the average surface normal) so the node group can work in the tangent plane:

    Padding   quilted pillows between stitched seams (diamond quilting)
    Denim     thin sharp creases bunching up, with small secondary folds
    Leather   few thick, round, heavy folds

Inputs (HUD sliders, all live): Type, Strength, Scale, Direction, Seed,
Detail (subdivision), Edge Soft (wrinkles fade out toward the border),
Thickness (cloth layer).  Apply bakes it to a plain mesh.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from bpy.props import EnumProperty, IntProperty
from mathutils import Matrix, Vector

from . import core_geometry as cg

GROUP = 'MCH_ClothWrinkle'
MOD = 'MCH_Wrinkle'
MOD_SHELL = 'MCH_WrinkleShell'
COLL = 'Cloth Wrinkles'
EDGE_ATTR = 'mch_edge_dist'
TYPES = (('PADDING', 'Padding', 'Puffy padded panel, soft folds from the seams (pattern: stitched channels)'),
         ('DENIM', 'Denim', 'Little puff, many long thin creases running in from the border'),
         ('LEATHER', 'Leather', 'Medium puff, few thick heavy folds from the border'))
TYPE_IDS = tuple(t[0] for t in TYPES)
# name, socket, default, min, max
INPUTS = (('Type', 'NodeSocketInt', 0, 0, 2),
          ('Strength', 'NodeSocketFloat', 0.03, -1.0, 1.0),
          ('Scale', 'NodeSocketFloat', 0.25, 0.001, 100.0),
          ('Direction', 'NodeSocketFloat', 0.0, -10.0, 10.0),
          ('Seed', 'NodeSocketInt', 1, 0, 100000),
          ('Detail', 'NodeSocketInt', 1, 0, 3),
          ('Edge Soft', 'NodeSocketFloat', 0.1, 0.0, 100.0),
          ('Lift', 'NodeSocketFloat', 0.0, -100.0, 100.0),
          # 0.20.1 padded panel: the border stays on the surface, the panel puffs up, seams pinch it
          ('Puff', 'NodeSocketFloat', 0.0, -100.0, 100.0),
          ('Puff Width', 'NodeSocketFloat', 0.1, 0.0001, 100.0),
          ('Roll', 'NodeSocketFloat', 0.0, -100.0, 100.0),
          ('Roll Width', 'NodeSocketFloat', 0.05, 0.0001, 100.0),
          ('Pinch', 'NodeSocketFloat', 0.0, -100.0, 100.0),
          ('Pinch Spacing', 'NodeSocketFloat', 0.05, 0.0001, 100.0),
          ('Pinch Length', 'NodeSocketFloat', 0.1, 0.0001, 100.0),
          ('Stitch', 'NodeSocketFloat', 0.0, -100.0, 100.0),
          ('Stitch Inset', 'NodeSocketFloat', 0.02, 0.0, 100.0),
          ('Stitch Length', 'NodeSocketFloat', 0.01, 0.0001, 100.0),
          ('Bend', 'NodeSocketFloat', 0.8, 0.0, 10.0),
          ('Sections', 'NodeSocketInt', 1, 1, 24),
          ('Section Turn', 'NodeSocketFloat', 0.0, -6.3, 6.3),
          ('Section Shape', 'NodeSocketInt', 0, 0, 4),
          ('Section Bend', 'NodeSocketFloat', 0.25, 0.0, 2.0),
          ('Section Start', 'NodeSocketFloat', 0.0, -1.0, 2.0),
          ('Section End', 'NodeSocketFloat', 1.0, -1.0, 2.0),
          ('Section Move', 'NodeSocketFloat', 0.0, -2.0, 2.0),
          ('Section Height', 'NodeSocketFloat', 1.0, 0.0, 10.0),
          ('Fold Sharp', 'NodeSocketFloat', 1.6, 0.3, 30.0),
          ('Fan', 'NodeSocketFloat', 9.0, 0.0, 60.0),
          ('Fold Tilt', 'NodeSocketFloat', 0.0, -1.45, 1.45),
          ('Tilt Random', 'NodeSocketFloat', 0.6, 0.0, 1.45),
          ('Length Random', 'NodeSocketFloat', 1.0, 0.0, 1.0),
          ('Variety', 'NodeSocketFloat', 1.0, 0.0, 1.0),
          ('Fan Mix', 'NodeSocketFloat', 0.6, 0.0, 1.0),
          ('Center Fade', 'NodeSocketFloat', 0.3, 0.0001, 100.0),
          ('Patchiness', 'NodeSocketFloat', 0.6, 0.0, 1.0),
          ('Trim', 'NodeSocketInt', 0, 0, 3),
          ('Trim Width', 'NodeSocketFloat', 0.03, 0.0001, 100.0),
          ('Trim Height', 'NodeSocketFloat', 0.01, -100.0, 100.0),
          ('Gravity', 'NodeSocketFloat', 0.0, 0.0, 5.0),
          ('Fold Asymmetry', 'NodeSocketFloat', 0.75, 0.0, 1.0),
          ('Fold Thinness', 'NodeSocketFloat', 0.0, 0.0, 1.0),
          ('Fold Direction', 'NodeSocketInt', 0, 0, 2),
          ('Skin', 'NodeSocketInt', 0, 0, 6),
          ('Skin Scale', 'NodeSocketFloat', 0.06, 0.0001, 100.0),
          ('Skin Depth', 'NodeSocketFloat', 0.01, -100.0, 100.0),
          ('Skin Random', 'NodeSocketFloat', 1.0, 0.0, 1.0),
          ('Edge Shrink', 'NodeSocketFloat', 0.6, 0.0, 3.0),
          ('Shrink Width', 'NodeSocketFloat', 0.15, 0.0001, 100.0),
          ('Skin Edge', 'NodeSocketInt', 0, 0, 3),
          ('Skin Edge Width', 'NodeSocketFloat', 0.06, 0.0001, 100.0),
          ('Skin Edge Height', 'NodeSocketFloat', 0.004, -100.0, 100.0),
          # 0.23.5 organic scale edges + an irregular shrink border
          ('Skin Organic', 'NodeSocketFloat', 0.8, 0.0, 3.0),
          ('Skin Irregular', 'NodeSocketFloat', 0.7, 0.0, 2.0))
TRIMS = (('NONE', 'No Trim', 'Plain border'),
         ('PIPING', 'Piping', 'Round cord along the border'),
         ('BINDING', 'Binding', 'Flat band folded over the border, stitched'),
         ('WELT', 'Welt', 'Raised flat strip just inside the border'))
TRIM_IDS = tuple(t[0] for t in TRIMS)
FOLD_ROOM = 'mch_fold_room'
FOLD_H = 'mch_foldh'           # long folds: height field written by fold_lines()    # distance to where the nearest border point jumps (corners): folds fade there
SEC_U = 'mch_sec_u'            # 0..1 along the long side (local X): stitched sections across it
SEC_LEN = 'mch_sec_len'        # length of the long side
EDGE_U = 'mch_edge_u'          # arc length along the border of the nearest border point
EDGE_LEN = 'mch_edge_len'      # length of that border loop (keeps seam patterns seamless)
VERSION = 40


# -----------------------------------------------------------------------------
# Node group
# -----------------------------------------------------------------------------


def _math(nodes, links, op, a=None, b=None, va=None, vb=None, clamp=False):
    n = nodes.new('ShaderNodeMath')
    n.operation = op
    n.use_clamp = clamp
    for i, (src, val) in enumerate(((a, va), (b, vb))):
        if src is not None:
            links.new(src, n.inputs[i])
        elif val is not None:
            n.inputs[i].default_value = val
    return n.outputs[0]


def _vor(N, L, vec, scale, rand, feature='F1'):
    v = N.new('ShaderNodeTexVoronoi')
    v.voronoi_dimensions = '2D'
    v.feature = feature
    L.new(vec, v.inputs['Vector'])
    L.new(scale, v.inputs['Scale'])
    L.new(rand, v.inputs['Randomness'])
    return v


def _skin_pattern(N, L, I, P, freq, rnd):
    """The skin patterns at one cell frequency (0..1-ish heights), picked by Skin (1..6)."""
    def smooth(x, lo, hi):
        mr = N.new('ShaderNodeMapRange')
        mr.interpolation_type = 'SMOOTHSTEP'
        L.new(x, mr.inputs['Value'])
        mr.inputs['From Min'].default_value = lo
        mr.inputs['From Max'].default_value = hi
        return mr.outputs['Result']

    def noise(scale, detail=2.0):
        n = N.new('ShaderNodeTexNoise')
        n.inputs['Detail'].default_value = detail
        L.new(P, n.inputs['Vector'])
        L.new(scale, n.inputs['Scale'])
        return n.outputs['Fac']

    def pillow(vec, f, groove=0.12, radius=0.62):
        """0.23.6 a plump scale: a round dome from the distance to the scale's own centre (smooth
        inside the cell - no ridges to the corners) cut by a narrow groove at the cell edge"""
        f1 = _vor(N, L, vec, f, rnd, 'F1')
        e = _vor(N, L, vec, f, rnd, 'DISTANCE_TO_EDGE').outputs['Distance']
        r2 = _math(N, L, 'POWER', _math(N, L, 'DIVIDE', f1.outputs['Distance'], vb=radius), vb=2.0)
        dome = _math(N, L, 'SQRT', _math(N, L, 'MAXIMUM', _math(N, L, 'SUBTRACT', va=1.0, b=r2), vb=0.0))
        c = N.new('FunctionNodeSeparateColor')
        L.new(f1.outputs['Color'], c.inputs[0])
        own = _math(N, L, 'ADD', va=0.8, b=_math(N, L, 'MULTIPLY', c.outputs[0], vb=0.35))
        return _math(N, L, 'MULTIPLY', _math(N, L, 'MULTIPLY', dome, smooth(e, 0.0, groove)), own)

    def mix(a_, b_, w):
        return _math(N, L, 'ADD', a_, _math(N, L, 'MULTIPLY', _math(N, L, 'SUBTRACT', b_, a_), w))
    # 1 crocodile (flank): plump pillow scales, big ones in clusters with small ones filling in,
    #   a fine pebbled grain on top
    big = pillow(P, _math(N, L, 'MULTIPLY', freq, vb=0.8))
    small = _math(N, L, 'MULTIPLY', pillow(P, _math(N, L, 'MULTIPLY', freq, vb=1.7), 0.14), vb=0.7)
    clus = smooth(noise(_math(N, L, 'MULTIPLY', freq, vb=0.3)), 0.47, 0.56)
    grain = _math(N, L, 'MULTIPLY', _math(N, L, 'SUBTRACT', noise(_math(N, L, 'MULTIPLY', freq, vb=7.0), 3.0),
                                          vb=0.5), vb=0.12)
    scales = mix(small, big, clus)
    croc = _math(N, L, 'ADD', scales, _math(N, L, 'MULTIPLY', grain, smooth(scales, 0.1, 0.5)))
    # 2 dragon (bearded dragon): small round pebbly scales + scattered sharp cone spikes
    peb = pillow(P, _math(N, L, 'MULTIPLY', freq, vb=1.4), 0.16, 0.52)
    sf = _math(N, L, 'MULTIPLY', freq, vb=0.42)
    sp = _vor(N, L, P, sf, rnd, 'F1')
    spc = N.new('FunctionNodeSeparateColor')
    L.new(sp.outputs['Color'], spc.inputs[0])
    pick = _math(N, L, 'GREATER_THAN', spc.outputs[1], vb=0.7)        # ~30 % of the coarse cells
    rad = _math(N, L, 'ADD', va=0.22, b=_math(N, L, 'MULTIPLY', spc.outputs[0], vb=0.14))
    cone = _math(N, L, 'POWER', _math(N, L, 'SUBTRACT', va=1.0, b=_math(N, L, 'DIVIDE', sp.outputs['Distance'], rad,
                                                                         clamp=True)), vb=1.7)
    spike = _math(N, L, 'MULTIPLY', _math(N, L, 'MULTIPLY', cone, pick),
                  _math(N, L, 'ADD', va=1.6, b=_math(N, L, 'MULTIPLY', spc.outputs[2], vb=1.4)))
    dragon = _math(N, L, 'ADD', _math(N, L, 'MULTIPLY', peb, vb=0.7), spike)
    # 3 godzilla: big flat plates, sharp grooves, each plate its own height
    gf = _math(N, L, 'MULTIPLY', freq, vb=0.55)
    e3 = _vor(N, L, P, gf, rnd, 'DISTANCE_TO_EDGE').outputs['Distance']
    c3 = N.new('FunctionNodeSeparateColor')
    L.new(_vor(N, L, P, gf, rnd, 'F1').outputs['Color'], c3.inputs[0])
    godz = _math(N, L, 'MULTIPLY', _math(N, L, 'DIVIDE', e3, vb=0.035, clamp=True),
                 _math(N, L, 'ADD', va=0.75, b=_math(N, L, 'MULTIPLY', c3.outputs[0], vb=0.5)))
    # 4 toad: warts of random size + rough grain
    f4 = _vor(N, L, P, freq, rnd, 'F1')
    c4 = N.new('FunctionNodeSeparateColor')
    L.new(f4.outputs['Color'], c4.inputs[0])
    rad = _math(N, L, 'ADD', va=0.18, b=_math(N, L, 'MULTIPLY', c4.outputs[0], vb=0.38))
    wart = _math(N, L, 'POWER', _math(N, L, 'SUBTRACT', va=1.0, b=_math(N, L, 'DIVIDE', f4.outputs['Distance'], rad,
                                                                         clamp=True)), vb=1.6)
    no = N.new('ShaderNodeTexNoise')
    no.inputs['Detail'].default_value = 4.0
    L.new(P, no.inputs['Vector'])
    L.new(_math(N, L, 'MULTIPLY', freq, vb=5.0), no.inputs['Scale'])
    toad = _math(N, L, 'ADD', wart, _math(N, L, 'MULTIPLY', _math(N, L, 'SUBTRACT', no.outputs['Fac'], vb=0.5), vb=0.5))
    # 5 elephant: crack network (two sizes) in a soft lumpy skin
    e5a = _vor(N, L, P, _math(N, L, 'MULTIPLY', freq, vb=0.7), rnd, 'DISTANCE_TO_EDGE').outputs['Distance']
    e5b = _vor(N, L, P, _math(N, L, 'MULTIPLY', freq, vb=1.9), rnd, 'DISTANCE_TO_EDGE').outputs['Distance']
    crack = _math(N, L, 'ADD', _math(N, L, 'MULTIPLY', _math(N, L, 'SUBTRACT', va=1.0, b=_math(
        N, L, 'DIVIDE', e5a, vb=0.06, clamp=True)), vb=0.8), _math(N, L, 'MULTIPLY', _math(
            N, L, 'SUBTRACT', va=1.0, b=_math(N, L, 'DIVIDE', e5b, vb=0.05, clamp=True)), vb=0.4))
    no5 = N.new('ShaderNodeTexNoise')
    no5.inputs['Detail'].default_value = 2.0
    L.new(P, no5.inputs['Vector'])
    L.new(_math(N, L, 'MULTIPLY', freq, vb=0.6), no5.inputs['Scale'])
    eleph = _math(N, L, 'SUBTRACT', _math(N, L, 'MULTIPLY', no5.outputs['Fac'], vb=0.8), crack)
    # 6 crocodile back: rows of rectangular scutes, each with a keel ridge along the middle
    sep = N.new('ShaderNodeSeparateXYZ')
    L.new(P, sep.inputs[0])
    gx = _math(N, L, 'MULTIPLY', sep.outputs['X'], _math(N, L, 'MULTIPLY', freq, vb=0.8))
    gy = _math(N, L, 'MULTIPLY', sep.outputs['Y'], _math(N, L, 'MULTIPLY', freq, vb=0.9))
    fx, fy = _math(N, L, 'FRACT', gx), _math(N, L, 'FRACT', gy)
    ex = _math(N, L, 'MINIMUM', fx, _math(N, L, 'SUBTRACT', va=1.0, b=fx))
    ey = _math(N, L, 'MINIMUM', fy, _math(N, L, 'SUBTRACT', va=1.0, b=fy))
    eg = _math(N, L, 'MINIMUM', ex, ey)
    wn = N.new('ShaderNodeTexWhiteNoise')
    wn.noise_dimensions = '2D'
    cid = N.new('ShaderNodeCombineXYZ')
    L.new(_math(N, L, 'FLOOR', gx), cid.inputs[0])
    L.new(_math(N, L, 'FLOOR', gy), cid.inputs[1])
    L.new(cid.outputs[0], wn.inputs['Vector'])
    cell_r = wn.outputs['Value']
    plate = _math(N, L, 'MULTIPLY', _math(N, L, 'SQRT', _math(N, L, 'DIVIDE', eg, vb=0.3, clamp=True)),
                  _math(N, L, 'ADD', va=0.75, b=_math(
        N, L, 'MULTIPLY', cell_r, vb=0.4)))
    keel = _math(N, L, 'POWER', _math(N, L, 'SUBTRACT', va=1.0, b=_math(N, L, 'MULTIPLY', _math(
        N, L, 'ABSOLUTE', _math(N, L, 'SUBTRACT', fx, vb=0.5)), vb=4.5), clamp=True), vb=1.3)
    keel_on = smooth(cell_r, 0.15, 0.3)                                 # most scutes carry a keel
    gr = _math(N, L, 'MULTIPLY', _math(N, L, 'SUBTRACT', noise(_math(N, L, 'MULTIPLY', freq, vb=6.0), 3.0),
                                       vb=0.5), vb=0.1)
    cback = _math(N, L, 'ADD', _math(N, L, 'ADD', plate, _math(N, L, 'MULTIPLY', _math(
        N, L, 'MULTIPLY', keel, keel_on), _math(N, L, 'MULTIPLY', smooth(eg, 0.0, 0.25), vb=1.1))),
        _math(N, L, 'MULTIPLY', gr, plate))
    sw = N.new('GeometryNodeIndexSwitch')
    sw.data_type = 'FLOAT'
    while len(sw.index_switch_items) < 7:
        sw.index_switch_items.new()
    L.new(I['Skin'], sw.inputs['Index'])
    sw.inputs[1].default_value = 0.0
    for k, src in enumerate((croc, dragon, godz, toad, eleph, cback)):
        L.new(src, sw.inputs[k + 2])
    return sw.outputs[0]


def _skin_height(N, L, I, Db):
    """0.23.4 Creature skin: scales / warts / cracks inside, skin grain along the border (height in metres)."""
    pos = N.new('GeometryNodeInputPosition').outputs[0]
    seed = N.new('ShaderNodeCombineXYZ')
    L.new(_math(N, L, 'MULTIPLY', I['Seed'], vb=3.17), seed.inputs[0])
    L.new(_math(N, L, 'MULTIPLY', I['Seed'], vb=-1.93), seed.inputs[1])
    pv = N.new('ShaderNodeVectorMath')
    pv.operation = 'ADD'
    L.new(pos, pv.inputs[0])
    L.new(seed.outputs[0], pv.inputs[1])
    # organic: bend the scale edges with a low noise (~ one scale wavelength)
    sz = _math(N, L, 'MAXIMUM', I['Skin Scale'], vb=1e-6)
    wn = N.new('ShaderNodeTexNoise')
    wn.inputs['Detail'].default_value = 1.5
    L.new(pv.outputs[0], wn.inputs['Vector'])
    L.new(_math(N, L, 'DIVIDE', va=0.9, b=sz), wn.inputs['Scale'])
    wc = N.new('ShaderNodeVectorMath')
    wc.operation = 'SUBTRACT'
    L.new(wn.outputs['Color'], wc.inputs[0])
    wc.inputs[1].default_value = (0.5, 0.5, 0.5)
    ws = N.new('ShaderNodeVectorMath')
    ws.operation = 'SCALE'
    L.new(wc.outputs[0], ws.inputs[0])
    L.new(_math(N, L, 'MULTIPLY', _math(N, L, 'MULTIPLY', I['Skin Organic'], sz), vb=0.5), ws.inputs['Scale'])
    pw = N.new('ShaderNodeVectorMath')
    pw.operation = 'ADD'
    L.new(pv.outputs[0], pw.inputs[0])
    L.new(ws.outputs[0], pw.inputs[1])
    P = pw.outputs[0]
    # irregular shrink border: two smooth noises move the border line in and out (~ Shrink Width)
    jit = None
    for sc_, amp in ((1.7, 1.0), (0.6, 1.4)):
        en = N.new('ShaderNodeTexNoise')
        en.inputs['Detail'].default_value = 2.0
        L.new(pv.outputs[0], en.inputs['Vector'])
        L.new(_math(N, L, 'DIVIDE', va=sc_, b=sz), en.inputs['Scale'])
        j = _math(N, L, 'MULTIPLY', _math(N, L, 'SUBTRACT', en.outputs['Fac'], vb=0.5), vb=amp)
        jit = j if jit is None else _math(N, L, 'ADD', jit, j)
    Dj = _math(N, L, 'ADD', Db, _math(N, L, 'MULTIPLY', _math(N, L, 'MULTIPLY', jit, I['Skin Irregular']),
                                      _math(N, L, 'MAXIMUM', I['Shrink Width'], vb=1e-6)))
    # scales get smaller near the border: a clean pattern at the normal size blends into a clean finer one
    near = _math(N, L, 'SUBTRACT', va=1.0, b=_math(N, L, 'DIVIDE', Dj, _math(N, L, 'MAXIMUM', I['Shrink Width'],
                                                                             vb=1e-6), clamp=True))
    near = _math(N, L, 'MULTIPLY', near, _math(N, L, 'MULTIPLY', near, _math(N, L, 'SUBTRACT', va=3.0, b=_math(
        N, L, 'MULTIPLY', near, vb=2.0))))
    f0 = _math(N, L, 'DIVIDE', va=1.0, b=_math(N, L, 'MAXIMUM', I['Skin Scale'], vb=1e-6))
    f1 = _math(N, L, 'MULTIPLY', f0, _math(N, L, 'ADD', va=1.0, b=_math(N, L, 'MULTIPLY', I['Edge Shrink'], vb=1.5)))
    rnd = _math(N, L, 'MULTIPLY', I['Skin Random'], vb=1.0)
    p_in = _skin_pattern(N, L, I, P, f0, rnd)
    p_edge = _skin_pattern(N, L, I, P, f1, rnd)
    mixed = _math(N, L, 'ADD', p_in, _math(N, L, 'MULTIPLY', _math(N, L, 'SUBTRACT', p_edge, p_in), near))
    freq = f0
    skin = _math(N, L, 'MULTIPLY', mixed, I['Skin Depth'])
    # border skin grain (instead of the cloth trim): fine lines / skin folds / pebbles along the edge
    ew = _math(N, L, 'MAXIMUM', I['Skin Edge Width'], vb=1e-6)
    band = _math(N, L, 'SUBTRACT', va=1.0, b=_math(N, L, 'DIVIDE', Db, ew, clamp=True))
    band2 = _math(N, L, 'MULTIPLY', band, band)
    ph = _math(N, L, 'DIVIDE', Db, ew)
    grain = _math(N, L, 'MULTIPLY', _math(N, L, 'SINE', _math(N, L, 'MULTIPLY', ph, vb=2 * math.pi * 7.0)), band2)
    folds = _math(N, L, 'MULTIPLY', _math(N, L, 'ABSOLUTE', _math(N, L, 'SINE', _math(
        N, L, 'MULTIPLY', ph, vb=math.pi * 2.5))), _math(N, L, 'POWER', band, vb=0.6))
    peb = _vor(N, L, P, _math(N, L, 'MULTIPLY', freq, vb=2.5), rnd, 'F1').outputs['Distance']
    pebble = _math(N, L, 'MULTIPLY', _math(N, L, 'SUBTRACT', va=1.0, b=_math(N, L, 'DIVIDE', peb, vb=0.45, clamp=True)),
                   band)
    ew_sw = N.new('GeometryNodeIndexSwitch')
    ew_sw.data_type = 'FLOAT'
    while len(ew_sw.index_switch_items) < 4:
        ew_sw.index_switch_items.new()
    L.new(I['Skin Edge'], ew_sw.inputs['Index'])
    ew_sw.inputs[1].default_value = 0.0
    for k, src in enumerate((grain, folds, pebble)):
        L.new(src, ew_sw.inputs[k + 2])
    return _math(N, L, 'ADD', skin, _math(N, L, 'MULTIPLY', ew_sw.outputs[0], I['Skin Edge Height']))


def build_group():
    """The wrinkle node group (rebuilt when an older version is found)."""
    ng = bpy.data.node_groups.get(GROUP)
    if ng is not None and ng.get('mch_version') == VERSION:
        return ng
    if ng is None:
        ng = bpy.data.node_groups.new(GROUP, 'GeometryNodeTree')
    ng.nodes.clear()
    ng.interface.clear()
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    for name, sock, default, lo, hi in INPUTS:
        it = ng.interface.new_socket(name, in_out='INPUT', socket_type=sock)
        it.default_value = default
        it.min_value, it.max_value = lo, hi
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gin = N.new('NodeGroupInput')
    gout = N.new('NodeGroupOutput')
    I = {name: gin.outputs[name] for name, *_r in INPUTS}

    sub = N.new('GeometryNodeSubdivideMesh')
    L.new(gin.outputs['Geometry'], sub.inputs['Mesh'])
    L.new(I['Detail'], sub.inputs['Level'])

    # tangent-plane coordinates: rotate around local Z by Direction, divide by Scale, seed offset
    pos = N.new('GeometryNodeInputPosition')
    rot = N.new('ShaderNodeVectorRotate')
    rot.rotation_type = 'Z_AXIS'
    L.new(pos.outputs[0], rot.inputs['Vector'])
    # 0.20.1 the seed also picks the flow direction, and the folds bend across the panel (Bend)
    rnd = N.new('FunctionNodeRandomValue')
    rnd.data_type = 'FLOAT'
    sock = {i.identifier: i for i in rnd.inputs}
    sock['Min_001'].default_value = -math.pi / 2          # the FLOAT min / max (names repeat per type)
    sock['Max_001'].default_value = math.pi / 2
    zero = N.new('FunctionNodeInputInt')
    zero.integer = 0
    L.new(zero.outputs[0], rnd.inputs['ID'])
    L.new(I['Seed'], rnd.inputs['Seed'])
    flow = N.new('ShaderNodeVectorMath')
    flow.operation = 'SCALE'
    L.new(pos.outputs[0], flow.inputs[0])
    L.new(_math(N, L, 'DIVIDE', va=0.18, b=_math(N, L, 'MAXIMUM', I['Scale'], vb=1e-6)), flow.inputs['Scale'])
    fseed = N.new('ShaderNodeCombineXYZ')
    L.new(_math(N, L, 'MULTIPLY', I['Seed'], vb=5.31), fseed.inputs[2])
    fvec = N.new('ShaderNodeVectorMath')
    fvec.operation = 'ADD'
    L.new(flow.outputs[0], fvec.inputs[0])
    L.new(fseed.outputs[0], fvec.inputs[1])
    fno = N.new('ShaderNodeTexNoise')
    fno.inputs['Scale'].default_value = 1.0
    fno.inputs['Detail'].default_value = 1.0
    L.new(fvec.outputs[0], fno.inputs['Vector'])
    bend = _math(N, L, 'MULTIPLY', _math(N, L, 'SUBTRACT', fno.outputs['Fac'], vb=0.5),
                 _math(N, L, 'MULTIPLY', I['Bend'], vb=3.0))
    ang = _math(N, L, 'ADD', _math(N, L, 'ADD', I['Direction'], {o.identifier: o for o in rnd.outputs}['Value_001']), bend)
    L.new(_math(N, L, 'MULTIPLY', ang, vb=-1.0), rot.inputs['Angle'])
    inv_s = _math(N, L, 'DIVIDE', vb=None, va=1.0, b=I['Scale'])
    scl = N.new('ShaderNodeVectorMath')
    scl.operation = 'SCALE'
    L.new(rot.outputs[0], scl.inputs[0])
    L.new(inv_s, scl.inputs['Scale'])
    seedv = N.new('ShaderNodeCombineXYZ')
    sx = _math(N, L, 'MULTIPLY', I['Seed'], vb=17.123)
    sy = _math(N, L, 'MULTIPLY', I['Seed'], vb=-9.731)
    L.new(sx, seedv.inputs[0])
    L.new(sy, seedv.inputs[1])
    uv = N.new('ShaderNodeVectorMath')
    uv.operation = 'ADD'
    L.new(scl.outputs[0], uv.inputs[0])
    L.new(seedv.outputs[0], uv.inputs[1])
    sep = N.new('ShaderNodeSeparateXYZ')
    L.new(uv.outputs[0], sep.inputs[0])
    X, Y = sep.outputs[0], sep.outputs[1]

    def noise(vec, scale, detail=2.0, rough=0.5):
        n = N.new('ShaderNodeTexNoise')
        n.inputs['Scale'].default_value = scale
        n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = rough
        L.new(vec, n.inputs['Vector'])
        return n.outputs['Fac']

    # ---- Padding: stitched channels that follow the outline (tubes between seam lines), soft folds
    k = 2.0 * math.pi
    dch = N.new('GeometryNodeInputNamedAttribute')
    dch.data_type = 'FLOAT'
    dch.inputs['Name'].default_value = EDGE_ATTR
    chan = _math(N, L, 'DIVIDE', dch.outputs['Attribute'], _math(N, L, 'MAXIMUM', I['Scale'], vb=1e-6))
    tube = _math(N, L, 'POWER', _math(N, L, 'ABSOLUTE', _math(N, L, 'SINE', _math(N, L, 'MULTIPLY', chan,
                                                                                    vb=math.pi))), vb=0.4)
    pad = _math(N, L, 'ADD', tube, _math(N, L, 'MULTIPLY', noise(uv.outputs[0], 1.5, 2.0), vb=0.12))

    # ---- Denim: thin sharp creases across X, wobbling, + small folds
    warp = _math(N, L, 'MULTIPLY', _math(N, L, 'SUBTRACT', noise(uv.outputs[0], 0.7, 3.0), vb=0.5), vb=4.0)
    phase = _math(N, L, 'ADD', _math(N, L, 'MULTIPLY', X, vb=k * 1.1), warp)
    crease = _math(N, L, 'POWER', _math(N, L, 'ABSOLUTE', _math(N, L, 'SINE', phase)), vb=4.0)
    amp = noise(uv.outputs[0], 0.5, 1.0)                                   # bunching: some creases stronger
    small = _math(N, L, 'MULTIPLY', noise(uv.outputs[0], 5.0, 3.0, 0.55), vb=0.15)
    den = _math(N, L, 'ADD', _math(N, L, 'MULTIPLY', crease, _math(N, L, 'MULTIPLY', amp, vb=1.6)), small)

    # ---- Leather: few thick round folds
    lwarp = _math(N, L, 'MULTIPLY', _math(N, L, 'SUBTRACT', noise(uv.outputs[0], 0.45, 2.0), vb=0.5), vb=2.5)
    lphase = _math(N, L, 'ADD', _math(N, L, 'MULTIPLY', X, vb=k * 0.55), lwarp)
    lfold = _math(N, L, 'MULTIPLY', _math(N, L, 'ADD', _math(N, L, 'SINE', lphase), vb=1.0), vb=0.5)
    lfold = _math(N, L, 'POWER', lfold, vb=1.3)
    lea = _math(N, L, 'MULTIPLY', _math(N, L, 'ADD', lfold, _math(N, L, 'MULTIPLY', noise(uv.outputs[0], 2.0, 2.0),
                                                                    vb=0.1)), vb=2.2)

    sw = N.new('GeometryNodeIndexSwitch')
    sw.data_type = 'FLOAT'
    while len(sw.index_switch_items) < 3:                # the node starts with 2 items
        sw.index_switch_items.new()
    L.new(I['Type'], sw.inputs['Index'])
    for i, src in enumerate((pad, den, lea)):
        L.new(src, sw.inputs[i + 1])

    # fade toward the border (distance attribute written at creation)
    attr = N.new('GeometryNodeInputNamedAttribute')
    attr.data_type = 'FLOAT'
    attr.inputs['Name'].default_value = EDGE_ATTR
    soft = _math(N, L, 'MAXIMUM', I['Edge Soft'], vb=1e-6)
    t = _math(N, L, 'DIVIDE', attr.outputs['Attribute'], soft, clamp=True)
    mask = _math(N, L, 'MULTIPLY', t, _math(N, L, 'SUBTRACT', va=3.0, b=_math(N, L, 'MULTIPLY', t, vb=2.0)))
    mask = _math(N, L, 'MULTIPLY', mask, t)                                  # smoothstep 3t^2 - 2t^3

    # the all-over pattern is strongest near the border and fades toward the middle (Center Fade),
    # with random weaker patches (Patchiness)
    tcf = _math(N, L, 'DIVIDE', attr.outputs['Attribute'], _math(N, L, 'MAXIMUM', I['Center Fade'], vb=1e-6),
                clamp=True)
    cfade = _math(N, L, 'SUBTRACT', va=1.0, b=_math(N, L, 'MULTIPLY', _math(N, L, 'MULTIPLY', _math(
        N, L, 'MULTIPLY', tcf, tcf), _math(N, L, 'SUBTRACT', va=3.0, b=_math(N, L, 'MULTIPLY', tcf, vb=2.0))), vb=0.85))
    pv = N.new('ShaderNodeVectorMath')
    pv.operation = 'SCALE'
    L.new(pos.outputs[0], pv.inputs[0])
    L.new(_math(N, L, 'DIVIDE', va=0.18, b=_math(N, L, 'MAXIMUM', I['Scale'], vb=1e-6)), pv.inputs['Scale'])
    pva = N.new('ShaderNodeVectorMath')
    pva.operation = 'ADD'
    L.new(pv.outputs[0], pva.inputs[0])
    L.new(seedv.outputs[0], pva.inputs[1])
    pn = noise(pva.outputs[0], 1.0, 2.0)
    pst = _math(N, L, 'MULTIPLY', _math(N, L, 'SUBTRACT', pn, vb=0.38), vb=4.0, clamp=True)
    patch = _math(N, L, 'SUBTRACT', va=1.0, b=_math(N, L, 'MULTIPLY', _math(N, L, 'SUBTRACT', va=1.0, b=pst),
                                                    I['Patchiness']))
    h = _math(N, L, 'MULTIPLY', _math(N, L, 'MULTIPLY', sw.outputs[0], I['Strength']),
              _math(N, L, 'MULTIPLY', mask, _math(N, L, 'MULTIPLY', cfade, patch)))
    h = _math(N, L, 'ADD', h, I['Lift'])                                     # layer height above the surface

    def named(name):
        a = N.new('GeometryNodeInputNamedAttribute')
        a.data_type = 'FLOAT'
        a.inputs['Name'].default_value = name
        return a.outputs['Attribute']
    Db, Ub, LP = attr.outputs['Attribute'], named(EDGE_U), named(EDGE_LEN)
    LPs = _math(N, L, 'MAXIMUM', LP, vb=1e-6)
    # sections: stitched seams across the long side, each cell puffs up on its own
    nsec = _math(N, L, 'MAXIMUM', I['Sections'], vb=1.0)
    # 0.20.2 sections can turn (Section Turn) and the seams can be straight / wave / zigzag / chevron / arc
    sp_ = N.new('ShaderNodeSeparateXYZ')
    L.new(pos.outputs[0], sp_.inputs[0])
    ca, sa = _math(N, L, 'COSINE', I['Section Turn']), _math(N, L, 'SINE', I['Section Turn'])
    s_ax = _math(N, L, 'ADD', _math(N, L, 'MULTIPLY', sp_.outputs[0], ca), _math(N, L, 'MULTIPLY', sp_.outputs[1], sa))
    t_ax = _math(N, L, 'SUBTRACT', _math(N, L, 'MULTIPLY', sp_.outputs[1], ca),
                 _math(N, L, 'MULTIPLY', sp_.outputs[0], sa))

    def stat(field):
        st_ = N.new('GeometryNodeAttributeStatistic')
        st_.data_type = 'FLOAT'
        st_.domain = 'POINT'
        L.new(sub.outputs['Mesh'], st_.inputs['Geometry'])
        L.new(field, st_.inputs['Attribute'])
        return st_.outputs['Min'], st_.outputs['Max']
    smin, smax = stat(s_ax)
    tmin, tmax = stat(t_ax)
    slen = _math(N, L, 'MAXIMUM', _math(N, L, 'SUBTRACT', smax, smin), vb=1e-6)
    # the sectioned stretch: Start .. End of the panel length, all moved by Section Move
    s0 = _math(N, L, 'ADD', I['Section Start'], I['Section Move'])
    s1 = _math(N, L, 'ADD', I['Section End'], I['Section Move'])
    span = _math(N, L, 'MAXIMUM', _math(N, L, 'SUBTRACT', s1, s0), vb=1e-4)
    cellw = _math(N, L, 'DIVIDE', _math(N, L, 'MULTIPLY', slen, span), nsec)
    tc = _math(N, L, 'SUBTRACT', t_ax, _math(N, L, 'MULTIPLY', _math(N, L, 'ADD', tmin, tmax), vb=0.5))
    thalf = _math(N, L, 'MAXIMUM', _math(N, L, 'MULTIPLY', _math(N, L, 'SUBTRACT', tmax, tmin), vb=0.5), vb=1e-6)
    tn = _math(N, L, 'DIVIDE', tc, thalf)                                   # -1 .. 1 across
    amp = _math(N, L, 'MULTIPLY', cellw, I['Section Bend'])
    wave = _math(N, L, 'SINE', _math(N, L, 'MULTIPLY', tn, vb=math.pi * 2.0))
    zig = _math(N, L, 'SUBTRACT', _math(N, L, 'MULTIPLY', _math(N, L, 'ABSOLUTE', _math(N, L, 'SUBTRACT', _math(
        N, L, 'FRACT', _math(N, L, 'ADD', _math(N, L, 'MULTIPLY', tn, vb=1.5), vb=0.25)), vb=0.5)), vb=4.0), vb=1.0)
    chev = _math(N, L, 'SUBTRACT', _math(N, L, 'ABSOLUTE', tn), vb=0.5)
    arc = _math(N, L, 'SUBTRACT', _math(N, L, 'MULTIPLY', tn, tn), vb=0.5)
    shp = N.new('GeometryNodeIndexSwitch')
    shp.data_type = 'FLOAT'
    while len(shp.index_switch_items) < 5:
        shp.index_switch_items.new()
    L.new(I['Section Shape'], shp.inputs['Index'])
    shp.inputs[1].default_value = 0.0
    for i_, src in enumerate((wave, zig, chev, arc)):
        L.new(src, shp.inputs[i_ + 2])
    s_shift = _math(N, L, 'ADD', _math(N, L, 'SUBTRACT', _math(N, L, 'SUBTRACT', s_ax, smin), _math(N, L, 'MULTIPLY',
                                                                                                s0, slen)),
                    _math(N, L, 'MULTIPLY', shp.outputs[0], amp))
    su_ = _math(N, L, 'DIVIDE', s_shift, cellw)
    fr = _math(N, L, 'SUBTRACT', _math(N, L, 'FRACT', su_), vb=0.5)
    ds = _math(N, L, 'MULTIPLY', _math(N, L, 'SUBTRACT', va=0.5, b=_math(N, L, 'ABSOLUTE', fr)), cellw)
    # only seams strictly inside the panel (not a seam line on the very end)
    inside = _math(N, L, 'MULTIPLY', _math(N, L, 'GREATER_THAN', su_, vb=0.5),
                   _math(N, L, 'LESS_THAN', su_, _math(N, L, 'SUBTRACT', nsec, vb=0.5)))
    ds = _math(N, L, 'ADD', ds, _math(N, L, 'MULTIPLY', _math(N, L, 'SUBTRACT', va=1.0, b=inside), vb=1e6))
    ds = _math(N, L, 'ADD', ds, _math(N, L, 'MULTIPLY', _math(N, L, 'LESS_THAN', nsec, vb=1.5), vb=1e6))
    # an edge trim takes the outer band: puff and folds start inside it
    has_trim = _math(N, L, 'GREATER_THAN', I['Trim'], vb=0.5)
    tw = _math(N, L, 'MULTIPLY', I['Trim Width'], has_trim)
    Db_in = _math(N, L, 'MAXIMUM', _math(N, L, 'SUBTRACT', Db, tw), vb=0.0)
    D = _math(N, L, 'MINIMUM', Db_in, ds)                  # puff / stitching see the section seams too
    U = Ub

    def gauss(x, w):                                    # exp(-(x / w)^2)
        q = _math(N, L, 'DIVIDE', x, _math(N, L, 'MAXIMUM', w, vb=1e-6))
        return _math(N, L, 'EXPONENT', _math(N, L, 'MULTIPLY', _math(N, L, 'MULTIPLY', q, q), vb=-1.0))

    def seam_freq(spacing):                             # 2 pi * round(L / spacing) / L  (seamless on the border)
        sp = _math(N, L, 'MAXIMUM', spacing, vb=1e-6)
        cnt = _math(N, L, 'MAXIMUM', _math(N, L, 'ROUND', _math(N, L, 'DIVIDE', LPs, sp)), vb=1.0)
        return _math(N, L, 'DIVIDE', _math(N, L, 'MULTIPLY', cnt, vb=k), LPs)

    # puff: rounded rise from the border to full height at Puff Width (quarter circle)
    # inside quilted sections every cell is its own round cushion (full puff at the cell middle)
    near_seam = _math(N, L, 'LESS_THAN', ds, vb=1e5)      # inside the sectioned stretch (smooth, no switch line)
    pwid = _math(N, L, 'MAXIMUM', I['Puff Width'], vb=1e-6)
    cellp = _math(N, L, 'MINIMUM', pwid, _math(N, L, 'MULTIPLY', cellw, vb=0.5))
    pden = _math(N, L, 'ADD', pwid, _math(N, L, 'MULTIPLY', near_seam, _math(N, L, 'SUBTRACT', cellp, pwid)))
    tp = _math(N, L, 'DIVIDE', D, _math(N, L, 'MAXIMUM', pden, vb=1e-6), clamp=True)
    # round dome with a finite slope at the seam (a quarter circle stood up vertically there and aliased)
    prof = _math(N, L, 'SUBTRACT', va=1.0, b=_math(N, L, 'POWER', _math(N, L, 'SUBTRACT', va=1.0, b=tp), vb=2.4))
    # Section Height: how much the quilted cells puff (x the panel puff)
    pamp = _math(N, L, 'MULTIPLY', I['Puff'], _math(N, L, 'ADD', va=1.0, b=_math(
        N, L, 'MULTIPLY', near_seam, _math(N, L, 'SUBTRACT', I['Section Height'], vb=1.0))))
    h = _math(N, L, 'ADD', h, _math(N, L, 'MULTIPLY', prof, pamp))
    # edge roll: a padded bulge along the border
    h = _math(N, L, 'ADD', h, _math(N, L, 'MULTIPLY', gauss(_math(N, L, 'SUBTRACT', D, I['Roll Width']),
                                                         _math(N, L, 'MULTIPLY', I['Roll Width'], vb=0.6)), I['Roll']))
    # seam pinch: folds running in from the border, fading inward (the seam line itself stays clean)
    pw = N.new('ShaderNodeCombineXYZ')
    L.new(_math(N, L, 'DIVIDE', U, _math(N, L, 'MAXIMUM', I['Pinch Spacing'], vb=1e-6)), pw.inputs[0])
    L.new(_math(N, L, 'DIVIDE', D, _math(N, L, 'MAXIMUM', I['Pinch Length'], vb=1e-6)), pw.inputs[1])
    L.new(_math(N, L, 'MULTIPLY', I['Seed'], vb=3.17), pw.inputs[2])
    pwarp = _math(N, L, 'MULTIPLY', _math(N, L, 'SUBTRACT', noise(pw.outputs[0], 0.35, 1.0), vb=0.5), vb=2.5)
    # 0.20.1 radial folds: every Fold Spacing along the border a pinch point; folds fan out from it -
    # thin and tight at the border, wider as they spread inward (rays: angle = along / depth)
    # 0.20.2 individual folds: a start point every ~Fold Spacing along the border (jittered); each fold
    # runs inward at its own angle (Fold Tilt +- Tilt Random), its own length and strength, thin at the
    # start and wider inward (Fan = how much it widens).  Neighbouring folds may cross.
    spc = _math(N, L, 'MAXIMUM', I['Pinch Spacing'], vb=1e-6)
    cnt = _math(N, L, 'MAXIMUM', _math(N, L, 'ROUND', _math(N, L, 'DIVIDE', LPs, spc)), vb=1.0)
    sx = _math(N, L, 'DIVIDE', LPs, cnt)
    base = _math(N, L, 'FLOOR', _math(N, L, 'DIVIDE', U, sx))

    def srand(kid, lo, hi, salt):
        rv = N.new('FunctionNodeRandomValue')
        rv.data_type = 'FLOAT'
        sk = {i.identifier: i for i in rv.inputs}
        sk['Min_001'].default_value, sk['Max_001'].default_value = lo, hi
        L.new(kid, sk['ID'])
        L.new(_math(N, L, 'ADD', I['Seed'], vb=salt), sk['Seed'])
        return {o.identifier: o for o in rv.outputs}['Value_001']

    def mixv(v, amount):                                   # 1 + (v - 1) * amount
        return _math(N, L, 'ADD', va=1.0, b=_math(N, L, 'MULTIPLY', _math(N, L, 'SUBTRACT', v, vb=1.0), amount))
    # 0.20.2 long folds: real fold lines made in Python (fold_lines) - start on the border, run inward
    # at their own angle up to just short of the far side; distance to the nearest line + its position
    # along the line give a thin start, a wider middle and a fading end
    # long folds: heights computed per point in Python (fold_lines, all folds summed - crossings blend)
    pinch = named(FOLD_H)
    # fans mixed in at random places along the border: several thin folds spreading from one point
    sxf = _math(N, L, 'DIVIDE', LPs, _math(N, L, 'MAXIMUM', _math(N, L, 'ROUND', _math(N, L, 'DIVIDE', LPs,
                                                                                       _math(N, L, 'MULTIPLY', spc,
                                                                                             vb=2.6))), vb=1.0))
    ucf = _math(N, L, 'ADD', _math(N, L, 'DIVIDE', U, sxf), vb=0.31)
    cellf = _math(N, L, 'SUBTRACT', _math(N, L, 'FRACT', _math(N, L, 'ADD', ucf, vb=0.5)), vb=0.5)
    fid = _math(N, L, 'FLOOR', _math(N, L, 'ADD', ucf, vb=0.5))
    thf = _math(N, L, 'DIVIDE', _math(N, L, 'MULTIPLY', cellf, sxf),
                _math(N, L, 'ADD', Db_in, _math(N, L, 'MULTIPLY', sxf, vb=0.25)))
    phf = _math(N, L, 'ADD', _math(N, L, 'MULTIPLY', thf, _math(N, L, 'MULTIPLY', I['Fan'],
                                                                 srand(fid, 1.2, 2.6, 131.0))), pwarp)
    wavf = _math(N, L, 'POWER', _math(N, L, 'MULTIPLY', _math(N, L, 'ADD', _math(N, L, 'COSINE', phf), vb=1.0), vb=0.5),
                 _math(N, L, 'MAXIMUM', I['Fold Sharp'], vb=0.3))
    lenff = _math(N, L, 'MULTIPLY', I['Pinch Length'], srand(fid, 0.3, 1.2, 137.0))
    envf = _math(N, L, 'POWER', _math(N, L, 'SUBTRACT', va=1.0, b=_math(N, L, 'DIVIDE', Db_in,
                                                                         _math(N, L, 'MAXIMUM', lenff, vb=1e-6),
                                                                         clamp=True)), vb=1.3)
    winf = _math(N, L, 'POWER', _math(N, L, 'MAXIMUM', _math(N, L, 'COSINE', _math(N, L, 'MULTIPLY', cellf,
                                                                                    vb=math.pi)), vb=0.0), vb=0.7)
    presf = _math(N, L, 'MULTIPLY', _math(N, L, 'SUBTRACT', srand(fid, 0.0, 1.0, 139.0), vb=0.55), vb=8.0, clamp=True)
    fan = _math(N, L, 'MULTIPLY', _math(N, L, 'MULTIPLY', wavf, envf), _math(N, L, 'MULTIPLY', winf, presf))
    # short fans fade where folds from two borders would meet (middle line)
    froom = _math(N, L, 'DIVIDE', named(FOLD_ROOM), _math(N, L, 'MAXIMUM', _math(N, L, 'MULTIPLY', sx, vb=0.5),
                                                          vb=1e-6), clamp=True)
    fan = _math(N, L, 'MULTIPLY', fan, _math(N, L, 'MULTIPLY', froom, _math(N, L, 'SUBTRACT', va=3.0,
                                                                             b=_math(N, L, 'MULTIPLY', froom, vb=2.0))))
    pinch = _math(N, L, 'MAXIMUM', pinch, _math(N, L, 'MULTIPLY', fan, I['Fan Mix']))
    pseam = _math(N, L, 'DIVIDE', Db_in, _math(N, L, 'MAXIMUM', _math(N, L, 'MULTIPLY', sx, vb=0.15), vb=1e-6),
                  clamp=True)
    pinch = _math(N, L, 'MULTIPLY', _math(N, L, 'SUBTRACT', pinch, vb=0.06), pseam)
    h = _math(N, L, 'ADD', h, _math(N, L, 'MULTIPLY', pinch, I['Pinch']))
    # stitching: a sunken seam line at Stitch Inset with raised thread stitches along it
    sl = _math(N, L, 'MAXIMUM', I['Stitch Length'], vb=1e-6)
    off = _math(N, L, 'SUBTRACT', Db_in, I['Stitch Inset'])          # stitches follow the border only
    groove = gauss(off, _math(N, L, 'MULTIPLY', sl, vb=0.3))
    # long thread dashes with short gaps (a running stitch), narrow across the seam
    dash = _math(N, L, 'MULTIPLY', _math(N, L, 'ADD', _math(N, L, 'SINE', _math(N, L, 'MULTIPLY', U, seam_freq(sl))),
                                         vb=0.55), vb=6.0, clamp=True)
    thread = _math(N, L, 'MULTIPLY', dash, gauss(off, _math(N, L, 'MULTIPLY', sl, vb=0.1)))
    stitch = _math(N, L, 'SUBTRACT', _math(N, L, 'MULTIPLY', thread, vb=0.9), groove)
    h = _math(N, L, 'ADD', h, _math(N, L, 'MULTIPLY', stitch, I['Stitch']))
    # section seams: a clean pressed-in line between the cushions
    sgw = _math(N, L, 'MAXIMUM', _math(N, L, 'MULTIPLY', cellw, vb=0.08), vb=1e-5)
    h = _math(N, L, 'SUBTRACT', h, _math(N, L, 'MULTIPLY', gauss(ds, sgw), _math(N, L, 'MULTIPLY', I['Puff'], vb=0.12)))
    # edge trim (finishing): piping cord / binding band / welt strip
    twp = _math(N, L, 'MAXIMUM', I['Trim Width'], vb=1e-6)
    half = _math(N, L, 'MULTIPLY', twp, vb=0.5)
    q = _math(N, L, 'DIVIDE', _math(N, L, 'SUBTRACT', Db, half), half)
    piping = _math(N, L, 'SQRT', _math(N, L, 'MAXIMUM', _math(N, L, 'SUBTRACT', va=1.0, b=_math(N, L, 'MULTIPLY', q, q)),
                                       vb=0.0))
    bedge = _math(N, L, 'DIVIDE', _math(N, L, 'SUBTRACT', twp, Db), _math(N, L, 'MULTIPLY', twp, vb=0.18), clamp=True)
    bstitch = gauss(_math(N, L, 'SUBTRACT', Db, _math(N, L, 'MULTIPLY', twp, vb=0.72)),
                    _math(N, L, 'MULTIPLY', twp, vb=0.06))
    binding = _math(N, L, 'SUBTRACT', bedge, _math(N, L, 'MULTIPLY', bstitch, vb=0.35))
    wq = _math(N, L, 'ABSOLUTE', _math(N, L, 'DIVIDE', _math(N, L, 'SUBTRACT', Db, _math(N, L, 'MULTIPLY', twp,
                                                                                       vb=0.9)), half))
    welt = _math(N, L, 'DIVIDE', _math(N, L, 'SUBTRACT', va=1.0, b=wq), vb=0.25, clamp=True)
    tsw = N.new('GeometryNodeIndexSwitch')
    tsw.data_type = 'FLOAT'
    while len(tsw.index_switch_items) < 4:
        tsw.index_switch_items.new()
    L.new(I['Trim'], tsw.inputs['Index'])
    tsw.inputs[1].default_value = 0.0
    for i, src in enumerate((piping, binding, welt)):
        L.new(src, tsw.inputs[i + 2])
    h = _math(N, L, 'ADD', h, _math(N, L, 'MULTIPLY', tsw.outputs[0], I['Trim Height']))
    h = _math(N, L, 'ADD', h, _skin_height(N, L, I, Db))
    nrm = N.new('GeometryNodeInputNormal')
    off = N.new('ShaderNodeVectorMath')
    off.operation = 'SCALE'
    L.new(nrm.outputs[0], off.inputs[0])
    L.new(h, off.inputs['Scale'])
    # 0.23.2 Gravity: the raised parts (puffs, folds) slide / sag toward world down, more where they are higher
    selfo = N.new('GeometryNodeSelfObject')
    oinfo = N.new('GeometryNodeObjectInfo')
    L.new(selfo.outputs[0], oinfo.inputs['Object'])
    inv = N.new('FunctionNodeInvertRotation')
    L.new(oinfo.outputs['Rotation'], inv.inputs[0])
    rv = N.new('FunctionNodeRotateVector')
    L.new(inv.outputs[0], rv.inputs['Rotation'])
    rv.inputs['Vector'].default_value = (0.0, 0.0, -1.0)
    down = rv.outputs[0]
    dn = N.new('ShaderNodeVectorMath')
    dn.operation = 'DOT_PRODUCT'
    L.new(down, dn.inputs[0])
    L.new(nrm.outputs[0], dn.inputs[1])
    nproj = N.new('ShaderNodeVectorMath')
    nproj.operation = 'SCALE'
    L.new(nrm.outputs[0], nproj.inputs[0])
    L.new(dn.outputs['Value'], nproj.inputs['Scale'])
    tang = N.new('ShaderNodeVectorMath')
    tang.operation = 'SUBTRACT'
    L.new(down, tang.inputs[0])
    L.new(nproj.outputs[0], tang.inputs[1])
    sagdir = N.new('ShaderNodeVectorMath')                     # mostly along the surface, a little straight down
    sagdir.operation = 'ADD'
    L.new(tang.outputs[0], sagdir.inputs[0])
    down02 = N.new('ShaderNodeVectorMath')
    down02.operation = 'SCALE'
    L.new(down, down02.inputs[0])
    down02.inputs['Scale'].default_value = 0.25
    L.new(down02.outputs[0], sagdir.inputs[1])
    sag = N.new('ShaderNodeVectorMath')
    sag.operation = 'SCALE'
    L.new(sagdir.outputs[0], sag.inputs[0])
    edge_keep = _math(N, L, 'DIVIDE', Db, _math(N, L, 'MAXIMUM', I['Puff Width'], vb=1e-5), clamp=True)
    L.new(_math(N, L, 'MULTIPLY', _math(N, L, 'MULTIPLY', _math(N, L, 'MAXIMUM', h, vb=0.0), I['Gravity']),
                _math(N, L, 'MULTIPLY', edge_keep, vb=0.5)), sag.inputs['Scale'])
    tot = N.new('ShaderNodeVectorMath')
    tot.operation = 'ADD'
    L.new(off.outputs[0], tot.inputs[0])
    L.new(sag.outputs[0], tot.inputs[1])
    setp = N.new('GeometryNodeSetPosition')
    L.new(sub.outputs['Mesh'], setp.inputs['Geometry'])
    L.new(tot.outputs[0], setp.inputs['Offset'])
    smooth = N.new('GeometryNodeSetShadeSmooth')
    L.new(setp.outputs[0], smooth.inputs['Geometry'])
    L.new(smooth.outputs[0], gout.inputs['Geometry'])
    ng['mch_version'] = VERSION
    return ng


# -----------------------------------------------------------------------------
# Modifier inputs
# -----------------------------------------------------------------------------


def _ident(name):
    ng = build_group()
    for it in ng.interface.items_tree:
        if getattr(it, 'in_out', '') == 'INPUT' and it.name == name:
            return it.identifier
    raise KeyError(name)


def get_input(ob, name):
    mod = ob.modifiers.get(MOD)
    return None if mod is None else mod[_ident(name)]


SIZE_INPUTS = {'Strength', 'Scale', 'Edge Soft', 'Lift', 'Puff', 'Puff Width', 'Roll', 'Roll Width', 'Pinch',
               'Pinch Spacing', 'Pinch Length', 'Stitch', 'Stitch Inset', 'Stitch Length', 'Trim Width', 'Trim Height',
               'Center Fade', 'Skin Scale', 'Skin Depth', 'Shrink Width', 'Skin Edge Width', 'Skin Edge Height'}


INPUT_NAMES = {n for n, *_r in INPUTS}
FOLD_INPUTS = {'Pinch Spacing', 'Pinch Length', 'Fold Tilt', 'Tilt Random', 'Length Random', 'Variety', 'Seed',
               'Fan', 'Trim', 'Trim Width', 'Fold Sharp', 'Fold Asymmetry', 'Fold Thinness', 'Fold Direction'}


def fold_lines(ob):
    """0.20.2 the long folds as real lines in the panel frame (loose points / edges in the panel mesh):
    a start every ~Fold Spacing along the border (jittered), running inward at Fold Tilt +- Tilt Random,
    random length up to just short of the far side, random strength; attributes along each line:
    mch_ft (0 start .. 1 end), mch_fw (width: thin start, wider inward), mch_famp (strength)."""
    import random
    mod = ob.modifiers.get(MOD)
    if mod is None:
        return None
    gi = lambda n: get_input(ob, n)
    size = float(ob.get('mch_wrinkle_size', 1.0)) or 1.0
    spacing = max(float(gi('Pinch Spacing')), size * 0.005)
    length = max(float(gi('Pinch Length')), 1e-6)
    tilt, trand = float(gi('Fold Tilt')), float(gi('Tilt Random'))
    lrand, variety, growth = float(gi('Length Random')), float(gi('Variety')), float(gi('Fan'))
    inset = float(gi('Trim Width')) if int(gi('Trim')) > 0 else 0.0
    try:
        asym = min(1.0, max(0.0, float(gi('Fold Asymmetry'))))
        thin = min(1.0, max(0.0, float(gi('Fold Thinness'))))
        fdir = int(gi('Fold Direction'))
    except (KeyError, TypeError, ValueError, AttributeError):
        asym, thin, fdir = 0.0, 0.0, 2
    # 0.23.4 which side folds over: the upper side (world up seen on the panel), lower, or random
    up3 = ob.matrix_world.inverted().to_3x3() @ Vector((0.0, 0.0, 1.0))
    up2 = Vector((up3.x, up3.y))
    up2 = up2.normalized() if up2.length > 0.15 else None
    rng = random.Random(int(gi('Seed')) * 7919 + 13)
    me = ob.data
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        loops = _border_loops(bm)
        # inward direction of every border edge (toward its face), in the panel plane
        loops2d, edges = [], []
        for lp in loops:
            pts = [Vector((v.co.x, v.co.y)) for v in lp]
            loops2d.append([tuple(p) for p in pts])
            for i in range(len(lp)):
                a, b = lp[i], lp[(i + 1) % len(lp)]
                e = bm.edges.get((a, b))
                if e is None or not e.link_faces:
                    continue
                fc = e.link_faces[0].calc_center_median()
                mid = (a.co + b.co) / 2
                t2 = Vector((b.co.x - a.co.x, b.co.y - a.co.y))
                if t2.length < 1e-12:
                    continue
                t2.normalize()
                nrm = Vector((-t2.y, t2.x))
                if nrm.dot(Vector((fc.x - mid.x, fc.y - mid.y))) < 0:
                    nrm = -nrm
                edges.append((Vector((a.co.x, a.co.y)), Vector((b.co.x, b.co.y)), nrm))
    finally:
        bm.free()
    total = sum((b - a).length for a, b, _n in edges)
    verts, eds, ftv, fwv, fav = [], [], [], [], []
    if total > 0:
        n = max(1, int(round(total / spacing)))
        step = total / n
        marks = sorted(((i + rng.uniform(0.15, 0.85)) * step) for i in range(n))
        acc, ei = 0.0, 0
        for m in marks:
            while ei < len(edges) - 1 and acc + (edges[ei][1] - edges[ei][0]).length < m:
                acc += (edges[ei][1] - edges[ei][0]).length
                ei += 1
            a, b, nrm = edges[ei]
            seg = (b - a).length or 1e-9
            p0 = a.lerp(b, min(1.0, max(0.0, (m - acc) / seg)))
            ang = max(-1.3, min(1.3, tilt + rng.uniform(-1.0, 1.0) * trand))
            d = Vector((nrm.x * math.cos(ang) - nrm.y * math.sin(ang), nrm.x * math.sin(ang) + nrm.y * math.cos(ang)))
            ln = length * (1.0 + (rng.uniform(0.15, 2.2) - 1.0) * lrand)
            amp = 1.0 + (rng.uniform(0.25, 1.4) - 1.0) * variety
            if rng.random() < 0.22 * variety:
                amp *= 0.15                                            # some places almost empty
            bend = rng.uniform(-0.35, 0.35)
            side = 1.0 if rng.random() < 0.5 else -1.0                # which side folds over (steep side)
            if up2 is not None and fdir in (0, 1):
                pl = Vector((-d.y, d.x)).dot(up2)                       # steep side toward up (0) / down (1)
                if abs(pl) > 0.2:
                    side = -1.0 if pl > 0 else 1.0
                    if fdir == 1:
                        side = -side
            start = p0 + d * inset
            # stop just short of the far side (march inside the outline)
            free = 0.0
            stp = max(spacing * 0.25, 1e-4)
            while free < ln:
                q = start + d * (free + stp)
                if not cg.point_in_loops(tuple(q), loops2d):
                    break
                free += stp
            ln = min(ln, max(0.0, free - stp * 2.0))
            if ln < spacing * 0.3:
                continue
            perp = Vector((-d.y, d.x))
            base = len(verts)
            k = max(24, int(ln / max(spacing * 0.12, 1e-6)))     # dense: the width / fade read smoothly
            k = min(k, 120)
            for j in range(k + 1):
                t = j / k
                q = start + d * (ln * t) + perp * (bend * ln * t * t)
                verts.append((q.x, q.y, 0.0))
                ftv.append(t)
                fwv.append((spacing * 0.06 * (1.0 - 0.92 * thin) + ln * t * growth * 0.03) * (1.0 - 0.65 * thin))
                fav.append(amp * side)
                if j:
                    eds.append((base + j - 1, base + j))
    # heights on the panel points: every fold adds a tube (thin start, wider inward, fading end)
    import numpy as np
    sharp = max(0.1, float(gi('Fold Sharp')) * 0.35)
    xy = np.array([(v.co.x, v.co.y) for v in me.vertices], dtype=np.float64)
    total = np.zeros(len(xy))
    fold = []
    cur = []
    # the panel resolution limits how thin a fold can be (thinner than ~1.3 edges reads as beads)
    if len(me.edges):
        el = np.array([(me.vertices[e.vertices[0]].co - me.vertices[e.vertices[1]].co).length for e in me.edges
                       if not e.is_loose][:4000] or [0.0])
        min_w = float(np.median(el)) * 1.3
    else:
        min_w = 0.0
    fwv = [max(w_, min_w) for w_ in fwv]
    sw = 1.0 - 0.72 * asym          # steep (folded-over) side: narrow wall
    gw = 1.0 + 0.9 * asym           # gentle side: long slope
    for i, (vx, vy, _z) in enumerate(verts):
        cur.append((vx, vy, ftv[i], fwv[i], fav[i]))
        if ftv[i] >= 1.0 - 1e-9:
            fold.append(cur)
            cur = []
    for pts in fold:
        P = np.array([(p[0], p[1]) for p in pts])
        T = np.array([p[2] for p in pts])
        W = np.array([p[3] for p in pts])
        amp = abs(pts[0][4])
        side = 1.0 if pts[0][4] >= 0 else -1.0
        A, B = P[:-1], P[1:]
        AB = B - A
        L2 = np.maximum((AB * AB).sum(1), 1e-18)
        # cull: only points near this fold's box
        lo = P.min(0) - W.max() * 2.2
        hi = P.max(0) + W.max() * 2.2
        sel = np.where((xy[:, 0] >= lo[0]) & (xy[:, 0] <= hi[0]) & (xy[:, 1] >= lo[1]) & (xy[:, 1] <= hi[1]))[0]
        if not len(sel):
            continue
        X = xy[sel][:, None, :]
        tt = np.clip(((X - A[None]) * AB[None]).sum(2) / L2[None], 0.0, 1.0)
        C = A[None] + tt[..., None] * AB[None]
        d2 = ((X - C) ** 2).sum(2)
        j = d2.argmin(1)
        r = np.arange(len(sel))
        dist = np.sqrt(d2[r, j])
        ft = T[j] + (T[j + 1] - T[j]) * tt[r, j]
        w = W[j] + (W[j + 1] - W[j]) * tt[r, j]
        # 0.23.3 asymmetric section: signed side of the fold line -> steep folded wall / long soft slope
        Xs = xy[sel]
        cr = (AB[j, 0] * (Xs[:, 1] - C[r, j, 1]) - AB[j, 1] * (Xs[:, 0] - C[r, j, 0])) * side
        steep = cr < 0
        u = dist / np.maximum(w, 1e-9)
        us = u / sw
        ug = u / gw
        prof_s = np.clip(1.0 - us ** 4, 0.0, 1.0) ** max(0.3, sharp * 0.6)
        crease = -0.22 * asym * np.exp(-((us - 1.05) / 0.35) ** 2)
        prof_g = np.clip(1.0 - ug, 0.0, 1.0) ** 2 * (3.0 - 2.0 * np.clip(1.0 - ug, 0.0, 1.0)) \
            if asym > 0 else np.clip(1.0 - ug ** 2, 0.0, 1.0) ** sharp
        sym = np.clip(1.0 - u ** 2, 0.0, 1.0) ** sharp
        prof = np.where(steep, prof_s + crease, prof_g)
        prof = sym * (1.0 - asym) + prof * asym
        st_ = np.clip(ft / 0.06, 0.0, 1.0)
        env = st_ * st_ * (1.0 - ft) ** 1.2
        total[sel] += amp * prof * env
    total = 1.25 * (1.0 - np.exp(-total / 1.25))         # crossings add up softly, never blow up
    att = me.attributes.get(FOLD_H) or me.attributes.new(FOLD_H, 'FLOAT', 'POINT')
    att.data.foreach_set('value', total.astype(np.float32).tolist() if len(total) else [])
    me.update()
    ob.update_tag(refresh={'OBJECT', 'DATA'})
    return len(fold)


def _remove_helper(ob):
    """(0.20.2 early builds used a helper object; the folds now live in the panel mesh.)"""
    name = ob.get('mch_folds_obj')
    h = bpy.data.objects.get(name) if name else None
    if h is not None:
        me = h.data
        bpy.data.objects.remove(h)
        if me.users == 0:
            bpy.data.meshes.remove(me)


def set_input(ob, name, value):
    """Set a node-group input on the layer and make the viewport re-evaluate NOW
    (writing a modifier ID property alone does not tag the depsgraph).  The value
    is remembered for the next Cloth Plate (relative to this one's size)."""
    mod = ob.modifiers.get(MOD)
    if mod is None:
        return
    mod[_ident(name)] = value
    from . import last_used
    size = float(ob.get('mch_wrinkle_size', 0.0) or 0.0)
    if size > 0 and name in INPUT_NAMES:
        # the same numbers next time (not scaled by size); creature skin remembers its own set
        last_used.remember('creature' if is_creature(ob) else 'wrinkle', name, value)
    if name in FOLD_INPUTS and size > 0:
        fold_lines(ob)                          # the long fold lines follow spacing / tilt / length / seed
    try:
        mod.node_group.interface_update(bpy.context)
    except (AttributeError, TypeError, RuntimeError):
        pass
    ob.update_tag(refresh={'OBJECT', 'DATA'})
    try:
        ob.data.update_tag()
    except AttributeError:
        pass
    try:
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                if area.type in {'VIEW_3D', 'PROPERTIES'}:
                    area.tag_redraw()
    except (AttributeError, TypeError, ReferenceError):
        pass


# Type = character of the panel (fractions of the patch size): puff, puff width, folds from the border
# (depth, spacing, length, sharpness), stitching
PRESETS = {
    'PADDING': dict(Puff=0.075, PuffW=0.4, Pinch=0.028, Spacing=0.09, Length=0.45, Sharp=1.6, Stitch=0.002, Fan=6.0),
    'DENIM': dict(Puff=0.012, PuffW=0.12, Pinch=0.026, Spacing=0.075, Length=0.7, Sharp=2.5, Stitch=0.0015,
                  Fan=4.0),
    'LEATHER': dict(Puff=0.025, PuffW=0.16, Pinch=0.04, Spacing=0.12, Length=0.55, Sharp=1.2, Stitch=0.002, Fan=8.0),
}


TRIM_PRESETS = {'NONE': (0.03, 0.0), 'PIPING': (0.022, 0.011), 'BINDING': (0.045, 0.006), 'WELT': (0.04, 0.008)}

# 0.23.4 Creature Skin (sizes are parts of the panel size)
SKINS = (('CROC', 'Crocodile', 'Plump round scales, big and small, with grooves'),
         ('DRAGON', 'Dragon', 'Small pebbly scales with scattered sharp spikes'),
         ('GODZILLA', 'Godzilla', 'Big flat plates with sharp grooves'),
         ('TOAD', 'Toad', 'Rough warty skin'),
         ('ELEPHANT', 'Elephant', 'Cracked, lumpy hide'),
         ('CROC_BACK', 'Croc Back', 'Rows of rectangular scutes with a keel ridge'))
SKIN_IDS = tuple(k[0] for k in SKINS)
SKIN_EDGES = (('NONE', 'No Edge', ''), ('GRAIN', 'Skin Grain', 'Fine lines along the border'),
              ('FOLDS', 'Skin Folds', 'Soft folds along the border'), ('PEBBLE', 'Pebbles', 'Small bumps along the border'))
CREATURE = {
    'CROC': dict(Skin=1, Scale=0.07, Depth=0.012, Shrink=0.7, ShrinkW=0.12, Edge=2, EdgeW=0.08, EdgeH=0.004),
    'DRAGON': dict(Skin=2, Scale=0.06, Depth=0.014, Shrink=0.9, ShrinkW=0.2, Edge=1, EdgeW=0.07, EdgeH=0.002),
    'GODZILLA': dict(Skin=3, Scale=0.12, Depth=0.01, Shrink=0.6, ShrinkW=0.25, Edge=3, EdgeW=0.08, EdgeH=0.004),
    'TOAD': dict(Skin=4, Scale=0.045, Depth=0.012, Shrink=0.5, ShrinkW=0.2, Edge=3, EdgeW=0.06, EdgeH=0.004),
    'ELEPHANT': dict(Skin=5, Scale=0.1, Depth=0.01, Shrink=0.4, ShrinkW=0.2, Edge=1, EdgeW=0.1, EdgeH=0.003),
    'CROC_BACK': dict(Skin=6, Scale=0.1, Depth=0.014, Shrink=0.5, ShrinkW=0.2, Edge=2, EdgeW=0.08, EdgeH=0.004),
}


def is_creature(ob):
    return bool(ob is not None and ob.get('mch_creature'))


def apply_creature(ob, skin, size=None):
    """Creature Skin: the skin pattern + border grain; the cloth features (puff, seams, stitching, trim) off."""
    size = size or float(ob.get('mch_wrinkle_size', 1.0)) or 1.0
    pr = CREATURE[skin]
    ob['mch_creature'] = skin
    set_input(ob, 'Skin', pr['Skin'])
    set_input(ob, 'Skin Scale', pr['Scale'] * size)
    set_input(ob, 'Skin Depth', pr['Depth'] * size)
    set_input(ob, 'Edge Shrink', pr['Shrink'])
    set_input(ob, 'Shrink Width', pr['ShrinkW'] * size)
    set_input(ob, 'Skin Edge', pr['Edge'])
    set_input(ob, 'Skin Edge Width', pr['EdgeW'] * size)
    set_input(ob, 'Skin Edge Height', pr['EdgeH'] * size)
    for name, v in (('Puff', 0.012 * size), ('Puff Width', 0.12 * size), ('Pinch', 0.0), ('Stitch', 0.0),
                    ('Trim', 0), ('Fan Mix', 0.0), ('Strength', 0.0), ('Roll', 0.0), ('Sections', 1)):
        set_input(ob, name, v)


def apply_trim(ob, trim, size=None):
    size = size or float(ob.get('mch_wrinkle_size', 1.0)) or 1.0
    w, h = TRIM_PRESETS[trim]
    set_input(ob, 'Trim', TRIM_IDS.index(trim))
    set_input(ob, 'Trim Width', w * size)
    set_input(ob, 'Trim Height', h * size)


def apply_preset(ob, wtype, size=None):
    size = size or float(ob.get('mch_wrinkle_size', 1.0)) or 1.0
    pr = PRESETS[wtype]
    set_input(ob, 'Type', TYPE_IDS.index(wtype))
    for name, key in (('Puff', 'Puff'), ('Puff Width', 'PuffW'), ('Pinch', 'Pinch'), ('Pinch Spacing', 'Spacing'),
                      ('Pinch Length', 'Length'), ('Stitch', 'Stitch')):
        set_input(ob, name, pr[key] * size)
    set_input(ob, 'Fold Sharp', pr['Sharp'])
    set_input(ob, 'Fan', pr['Fan'])


def is_wrinkle(ob):
    return ob is not None and ob.type == 'MESH' and ob.modifiers.get(MOD) is not None and bool(ob.get('mch_wrinkle'))


def active_wrinkle(context):
    ob = getattr(context, 'active_object', None)
    return ob if is_wrinkle(ob) else None


# -----------------------------------------------------------------------------
# Create
# -----------------------------------------------------------------------------


def _border_loops(bm):
    """Border vertex loops of the patch (ordered)."""
    nxt = {}
    for e in bm.edges:
        if e.is_boundary:
            a, b = e.verts
            nxt.setdefault(a, []).append(b)
            nxt.setdefault(b, []).append(a)
    seen, loops = set(), []
    for start in list(nxt):
        if start in seen:
            continue
        lp, prev, cur = [start], None, start
        seen.add(start)
        while True:
            cands = [w for w in nxt[cur] if w is not prev and w not in seen]
            if not cands:
                break
            prev, cur = cur, cands[0]
            lp.append(cur)
            seen.add(cur)
        if len(lp) >= 3:
            loops.append(lp)
    return loops


def _edge_distances(bm):
    """Straight distance of every vertex to the patch border (resampled border,
    nearest point), the border arc length there, that loop's length, and the
    'fold room': distance to where the nearest border point jumps (corners,
    middle line) - folds fade out there instead of breaking into spikes."""
    import heapq
    from mathutils.kdtree import KDTree
    loops = _border_loops(bm)
    lens = sorted(e.calc_length() for e in bm.edges) or [1.0]
    step = max(lens[len(lens) // 2] / 3.0, 1e-6)
    samples = []                                         # (co, arc, loop length, loop index)
    for li, lp in enumerate(loops):
        pts = [v.co.copy() for v in lp]
        total = sum((pts[(i + 1) % len(pts)] - pts[i]).length for i in range(len(pts)))
        acc = 0.0
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            seg = (b - a).length
            n = max(1, int(seg / step))
            for j in range(n):
                t = j / n
                samples.append((a.lerp(b, t), acc + seg * t, total, li))
            acc += seg
    dist = {v: 1e6 for v in bm.verts}
    u = {v: 0.0 for v in bm.verts}
    ln = {v: 1.0 for v in bm.verts}
    owner = {v: -1 for v in bm.verts}
    if samples:
        kd = KDTree(len(samples))
        for i, sm in enumerate(samples):
            kd.insert(sm[0], i)
        kd.balance()
        for v in bm.verts:
            _co, i, d = kd.find(v.co)
            co, a, total, li = samples[i]
            dist[v], u[v], ln[v], owner[v] = (0.0 if v.is_boundary else d), a, total, li
    # jumps of the nearest border point between neighbours
    seeds = set()
    for e in bm.edges:
        a, b = e.verts
        if owner[a] != owner[b]:
            seeds.update((a, b))
            continue
        du = abs(u[a] - u[b])
        du = min(du, ln[a] - du)
        if du > 3.0 * e.calc_length() + step:
            seeds.update((a, b))
    room = {v: 1e6 for v in bm.verts}
    heap = []
    for v in seeds:
        room[v] = 0.0
        heap.append((0.0, v.index, v))
    heapq.heapify(heap)
    while heap:
        d, _i, v = heapq.heappop(heap)
        if d > room[v]:
            continue
        for e in v.link_edges:
            w = e.other_vert(v)
            nd = d + e.calc_length()
            if nd < room[w]:
                room[w] = nd
                heapq.heappush(heap, (nd, w.index, w))
    return dist, u, ln, room


def perform_wrinkle(context, loops, projector, wtype=None):
    """Lasso -> new cloth wrinkle layer.  Returns a report; raises cg.CutError
    with the scene unchanged."""
    from . import armor_plate as ap
    from . import last_used
    scene = context.scene
    st = scene.mch_wrinkle
    last = last_used.recall('wrinkle')            # what was used last time (read before this one writes)
    groups = cg.prepare_loops(loops)
    target = ap.pick_surface(context, projector, groups)
    if target is None:
        raise cg.CutError('Draw the wrinkles over a mesh.')
    pts, tris, _nb = ap.screen_patch(groups, st.spacing)
    if not tris:
        raise cg.CutError('The outline is too small.')
    bvh, _wv, _polys = ap._target_bvh(context, target)
    cos, nrms, missing = ap.project_patch(pts, projector, bvh)
    cen = sum(cos, Vector()) / len(cos)
    n = sum(nrms, Vector())
    n = n.normalized() if n.length > 1e-9 else -projector.view_dir
    t = n.orthogonal().normalized()
    # long side of the patch = local X (Direction 0 runs the folds across it)
    flat = [(c - cen) - n * (c - cen).dot(n) for c in cos]
    sxx = sum(f.dot(t) ** 2 for f in flat)
    b0 = n.cross(t)
    syy = sum(f.dot(b0) ** 2 for f in flat)
    sxy = sum(f.dot(t) * f.dot(b0) for f in flat)
    ang = 0.5 * math.atan2(2 * sxy, sxx - syy)
    x = (t * math.cos(ang) + b0 * math.sin(ang)).normalized()
    y = n.cross(x).normalized()
    frame = Matrix.Identity(4)
    for r in range(3):
        frame[r][0], frame[r][1], frame[r][2], frame[r][3] = x[r], y[r], n[r], cen[r]
    inv = frame.inverted()
    size = max((max(f.length for f in flat) * 2.0), 1e-6)
    cos_l = [inv @ c for c in cos]
    nrm_l = [(inv.to_3x3() @ nn).normalized() for nn in nrms]
    region = ap.build_region(pts, tris, cos_l, nrm_l, quads=True)
    bm = bmesh.new()
    try:
        bm.from_mesh(region)
        bm.verts.ensure_lookup_table()
        dist, uu, ll, rm = _edge_distances(bm)
        rvals = [min(rm[v], 1e6) for v in bm.verts]
        vals = [min(dist.get(v, 0.0), 1e6) for v in bm.verts]
        x0 = min(v.co.x for v in bm.verts)
        x1 = max(v.co.x for v in bm.verts)
        sec = [(v.co.x - x0) / max(x1 - x0, 1e-9) for v in bm.verts]
        slen = [x1 - x0] * len(bm.verts)
        uvals = [uu[v] for v in bm.verts]
        lvals = [ll[v] for v in bm.verts]
        bm.to_mesh(region)
    finally:
        bm.free()
    for name, data in ((EDGE_ATTR, vals), (EDGE_U, uvals), (EDGE_LEN, lvals), (SEC_U, sec), (SEC_LEN, slen),
                       (FOLD_ROOM, rvals)):
        attr = region.attributes.new(name, 'FLOAT', 'POINT')
        attr.data.foreach_set('value', data)
    region.name = target.name + '_Wrinkle'
    for mat in target.data.materials:
        region.materials.append(mat)
    ob = bpy.data.objects.new(region.name, region)
    from . import face_extract as fx
    fx._parts_collection(context, COLL).objects.link(ob)
    ob.matrix_world = frame
    ob['mch_wrinkle'] = target.name
    mod = ob.modifiers.new(MOD, 'NODES')
    mod.node_group = build_group()
    wtype = wtype or st.wtype
    set_input(ob, 'Type', TYPE_IDS.index(wtype))
    set_input(ob, 'Strength', size * st.strength if st.pattern else 0.0)
    set_input(ob, 'Scale', size * st.scale)
    set_input(ob, 'Edge Soft', size * 0.03)
    set_input(ob, 'Center Fade', size * 0.3)
    set_input(ob, 'Seed', 1)
    set_input(ob, 'Detail', 2)
    set_input(ob, 'Sections', st.sections)
    set_input(ob, 'Lift', size * st.lift)
    # padded panel defaults (0.20.1): puff from the border, edge roll, seam pinch folds, stitching
    for name, frac in (('Roll', st.roll), ('Roll Width', 0.04), ('Stitch Inset', 0.045), ('Stitch Length', 0.05)):
        set_input(ob, name, size * frac)
    apply_preset(ob, wtype, size)
    apply_trim(ob, st.trim, size)
    shell = ob.modifiers.new(MOD_SHELL, 'SOLIDIFY')
    shell.thickness = size * st.thickness
    shell.offset = 1.0
    shell.use_even_offset = False          # even offset shot spikes out of steep folds (trim next to the puff)
    shell.use_quality_normals = True
    ob['mch_wrinkle_size'] = size
    # last used options (0.20.2): the new panel starts as the previous one was left - but a type / trim
    # picked in the panel since then wins over the remembered one
    if int(last.get('Type', TYPE_IDS.index(wtype))) != TYPE_IDS.index(wtype):
        for k in ('Type', 'Puff', 'Puff Width', 'Pinch', 'Pinch Spacing', 'Pinch Length', 'Stitch', 'Fold Sharp', 'Fan'):
            last.pop(k, None)
    if int(last.get('Trim', TRIM_IDS.index(st.trim))) != TRIM_IDS.index(st.trim):
        for k in ('Trim', 'Trim Width', 'Trim Height'):
            last.pop(k, None)
    for name, v in last.items():
        if name == '_thickness':
            shell.thickness = float(v)
        else:
            try:
                set_input(ob, name, v)
            except KeyError:
                pass
    if getattr(st, 'creature', False):
        apply_creature(ob, st.skin, size)
        for name, v in last_used.recall('creature').items():
            try:
                set_input(ob, name, v)
            except KeyError:
                pass
        if int(get_input(ob, 'Skin')) != CREATURE[st.skin]['Skin']:
            apply_creature(ob, st.skin, size)
    fold_lines(ob)
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    extra = f' | {len(missing)} point(s) past the surface edge' if missing else ''
    if getattr(st, 'creature', False):
        return f'Creature skin "{ob.name}" on {target.name} ({dict((a, b) for a, b, _c in SKINS)[st.skin]}){extra}'
    pat = dict((a, b) for a, b, _c in TYPES)[wtype] if st.pattern else 'no pattern'
    return f'Cloth plate "{ob.name}" on {target.name} (padded panel, {pat}){extra}'


def dense_mesh(context, ob, extra=2, limit=1_500_000):
    """High Poly of a live layer: the same wrinkles with a finer Detail (no subdivision blur)."""
    if not is_wrinkle(ob):
        return None
    old = int(get_input(ob, 'Detail'))
    dg = context.evaluated_depsgraph_get()
    base = len(ob.evaluated_get(dg).data.polygons) or 1
    lv = old
    while lv < min(3, old + extra) and base * 4 ** (lv + 1 - old) <= limit:
        lv += 1
    try:
        set_input(ob, 'Detail', lv)
        dg = context.evaluated_depsgraph_get()
        dg.update()
        return bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    finally:
        set_input(ob, 'Detail', old)


def apply_wrinkle(context, ob):
    dg = context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    old = ob.data
    ob.modifiers.clear()
    _remove_helper(ob)
    ob.data = me
    me.name = old.name
    for key in ('mch_wrinkle', 'mch_wrinkle_size', 'mch_folds_obj'):
        if key in ob:
            del ob[key]
    if old.users == 0:
        bpy.data.meshes.remove(old)


# -----------------------------------------------------------------------------
# Settings / operators
# -----------------------------------------------------------------------------


class MCH_PG_Wrinkle(bpy.types.PropertyGroup):
    wtype: EnumProperty(name='Type', items=TYPES, default='PADDING',
                        description='Character of the panel: puff and the folds from the border (also the optional '
                                    'all-over pattern)')
    pattern: bpy.props.BoolProperty(name='Surface Pattern', default=False,
                                    description='Also cover the whole panel with the chosen pattern')
    trim: EnumProperty(name='Edge Trim', items=TRIMS, default='NONE',
                       description='Finishing along the border: piping cord, binding band or welt strip')
    sections: IntProperty(name='Sections', default=1, min=1, max=24,
                          description='Stitched seams across the long side: each section puffs up on its own')
    puff: bpy.props.FloatProperty(name='Puff', default=0.05, soft_min=-0.1, soft_max=0.3,
                                  description='How much the panel puffs up inside its border (part of the size)')
    roll: bpy.props.FloatProperty(name='Edge Roll', default=0.0, soft_min=-0.05, soft_max=0.1,
                                  description='Padded bulge along the border (part of the size)')
    pinch: bpy.props.FloatProperty(name='Seam Folds', default=0.014, soft_min=0.0, soft_max=0.08,
                                   description='Folds pulled in from the border seams (part of the size)')
    stitch: bpy.props.FloatProperty(name='Stitching', default=0.002, soft_min=0.0, soft_max=0.02,
                                    description='Stitched seam line along the border (part of the size)')
    spacing: IntProperty(name='Face Size (px)', default=8, min=3, max=40,
                         description='Mesh density of the cloth layer on screen (smaller = finer wrinkles)')
    strength: bpy.props.FloatProperty(name='Pattern Depth', default=0.02, soft_min=-0.2, soft_max=0.2,
                                      description='Wrinkle depth (part of the patch size)')
    scale: bpy.props.FloatProperty(name='Scale', default=0.07, min=0.005, soft_max=1.0,
                                   description='Wrinkle spacing (part of the patch size)')
    thickness: bpy.props.FloatProperty(name='Thickness', default=0.01, min=0.0, soft_max=0.1,
                                       description='Cloth layer thickness (part of the patch size)')
    lift: bpy.props.FloatProperty(name='Height', default=0.002, soft_min=-0.05, soft_max=0.2,
                                  description='Height of the cloth layer above the surface (part of the patch size)')
    creature: bpy.props.BoolProperty(name='Creature Skin', default=False,
                                     description='Creature Skin brush: scales / warts / cracks instead of cloth')
    skin: EnumProperty(name='Skin', items=SKINS, default='CROC', description='Creature skin preset')


class MCH_OT_wrinkle_skin(bpy.types.Operator):
    """Creature Skin: next skin (Crocodile / Dragon / Godzilla / Toad / Elephant)"""
    bl_idname = 'mch.wrinkle_skin'
    bl_label = 'Creature Skin Type'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    step: IntProperty(default=1)

    @classmethod
    def poll(cls, context):
        return active_wrinkle(context) is not None

    def execute(self, context):
        ob = active_wrinkle(context)
        cur = ob.get('mch_creature') if is_creature(ob) else None
        i = SKIN_IDS.index(cur) if cur in SKIN_IDS else -self.step
        nxt = SKIN_IDS[(i + self.step) % len(SKIN_IDS)]
        apply_creature(ob, nxt)
        context.scene.mch_wrinkle.skin = nxt
        self.report({'INFO'}, 'Creature skin: ' + dict((a, b) for a, b, _c in SKINS)[nxt])
        return {'FINISHED'}


class MCH_OT_wrinkle_skin_edge(bpy.types.Operator):
    """Creature Skin: border finishing (none / skin grain / skin folds / pebbles)"""
    bl_idname = 'mch.wrinkle_skin_edge'
    bl_label = 'Skin Edge'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return active_wrinkle(context) is not None

    def execute(self, context):
        ob = active_wrinkle(context)
        set_input(ob, 'Skin Edge', (int(get_input(ob, 'Skin Edge')) + 1) % len(SKIN_EDGES))
        return {'FINISHED'}


class MCH_OT_creature_brush(bpy.types.Operator):
    """Creature brush: Skin (Cloth Plate with scales / warts / cracks) or Shell (Armor Plate carapace)"""
    bl_idname = 'mch.creature_brush'
    bl_label = 'Creature Brush'
    bl_options = {'INTERNAL'}
    kind: EnumProperty(items=[('SKIN', 'Skin', ''), ('SHELL', 'Shell', '')], default='SKIN')

    def execute(self, context):
        from .workspace_ui import activate_mecha_tool
        # activate first: picking the plain tool switches the creature layer off
        if self.kind == 'SKIN':
            activate_mecha_tool(context, 'WRINKLE')
            context.scene.mch_wrinkle.creature = True
        else:
            activate_mecha_tool(context, 'PLATE')
            context.scene.mch_plate.creature = True
        self.report({'INFO'}, 'Creature ' + self.kind.title() + ': draw on the mesh')
        return {'FINISHED'}


class MCH_OT_wrinkle_type(bpy.types.Operator):
    """Next wrinkle type: Padding > Denim > Leather (the selected layer changes at once)"""
    bl_idname = 'mch.wrinkle_type'
    bl_label = 'Wrinkle Type'
    bl_options = {'REGISTER', 'UNDO'}
    step: IntProperty(default=1, options={'SKIP_SAVE'})

    def execute(self, context):
        st = context.scene.mch_wrinkle
        i = (TYPE_IDS.index(st.wtype) + self.step) % len(TYPE_IDS)
        st.wtype = TYPE_IDS[i]
        ob = active_wrinkle(context)
        if ob is not None:
            apply_preset(ob, st.wtype)
        return {'FINISHED'}


class MCH_OT_wrinkle_trim(bpy.types.Operator):
    """Next edge trim: none > piping > binding > welt (the selected panel changes at once)"""
    bl_idname = 'mch.wrinkle_trim'
    bl_label = 'Edge Trim'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        st = context.scene.mch_wrinkle
        st.trim = TRIM_IDS[(TRIM_IDS.index(st.trim) + 1) % len(TRIM_IDS)]
        ob = active_wrinkle(context)
        if ob is not None:
            apply_trim(ob, st.trim)
        return {'FINISHED'}


SECTION_SHAPES = ('Straight', 'Wave', 'Zigzag', 'Chevron', 'Arc')


class MCH_OT_wrinkle_seam(bpy.types.Operator):
    """Section seam shape: straight > wave > zigzag > chevron > arc"""
    bl_idname = 'mch.wrinkle_seam'
    bl_label = 'Section Seam Shape'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return active_wrinkle(context) is not None

    def execute(self, context):
        ob = active_wrinkle(context)
        set_input(ob, 'Section Shape', (int(get_input(ob, 'Section Shape')) + 1) % len(SECTION_SHAPES))
        if int(get_input(ob, 'Sections')) < 2:
            set_input(ob, 'Sections', 3)
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# User presets (saved in config/mecha_lab/last_used.json, kept across Blender sessions)
# -----------------------------------------------------------------------------


def capture(ob):
    vals = {n: get_input(ob, n) for n in INPUT_NAMES}
    m = ob.modifiers.get(MOD_SHELL)
    if m is not None:
        vals['_thickness'] = m.thickness
    return {k: (float(v) if isinstance(v, float) else v) for k, v in vals.items()}


def user_presets():
    from . import last_used
    return last_used.data().setdefault('cloth_presets', {})


def apply_values(ob, vals):
    for k, v in vals.items():
        if k == '_thickness':
            m = ob.modifiers.get(MOD_SHELL)
            if m is not None:
                m.thickness = float(v)
        elif k in INPUT_NAMES:
            set_input(ob, k, v)


class MCH_OT_wrinkle_preset_save(bpy.types.Operator):
    """Save the selected Cloth Plate's values as a preset of your own (exact numbers)"""
    bl_idname = 'mch.wrinkle_preset_save'
    bl_label = 'Save Cloth Preset'
    bl_options = {'REGISTER'}
    name: bpy.props.StringProperty(name='Preset Name', default='My Cloth')

    @classmethod
    def poll(cls, context):
        return active_wrinkle(context) is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        from . import last_used
        name = self.name.strip() or 'My Cloth'
        user_presets()[name] = capture(active_wrinkle(context))
        last_used.save()
        self.report({'INFO'}, f'Cloth preset "{name}" saved')
        return {'FINISHED'}


class MCH_OT_wrinkle_preset_load(bpy.types.Operator):
    """Use a saved preset: on the selected Cloth Plate and for the next ones"""
    bl_idname = 'mch.wrinkle_preset_load'
    bl_label = 'Load Cloth Preset'
    bl_options = {'REGISTER', 'UNDO'}
    name: bpy.props.StringProperty(default='')

    def execute(self, context):
        from . import last_used
        vals = user_presets().get(self.name)
        if vals is None:
            self.report({'WARNING'}, f'No preset "{self.name}"')
            return {'CANCELLED'}
        ob = active_wrinkle(context)
        if ob is not None:
            apply_values(ob, vals)
        st = context.scene.mch_wrinkle               # type / trim of the preset become the panel choice too
        st.wtype = TYPE_IDS[max(0, min(2, int(vals.get('Type', TYPE_IDS.index(st.wtype)))))]
        st.trim = TRIM_IDS[max(0, min(3, int(vals.get('Trim', TRIM_IDS.index(st.trim)))))]
        sec = last_used.data().setdefault('wrinkle', {})
        sec.clear()
        sec.update(vals)                       # the next Cloth Plate starts with it too
        last_used.save()
        self.report({'INFO'}, f'Cloth preset "{self.name}"')
        return {'FINISHED'}


class MCH_OT_wrinkle_preset_delete(bpy.types.Operator):
    """Delete a saved Cloth preset"""
    bl_idname = 'mch.wrinkle_preset_delete'
    bl_label = 'Delete Cloth Preset'
    bl_options = {'REGISTER'}
    name: bpy.props.StringProperty(default='')

    def execute(self, context):
        from . import last_used
        user_presets().pop(self.name, None)
        last_used.save()
        return {'FINISHED'}


class MCH_MT_wrinkle_presets(bpy.types.Menu):
    bl_idname = 'MCH_MT_wrinkle_presets'
    bl_label = 'Cloth Presets'

    def draw(self, context):
        layout = self.layout
        names = sorted(user_presets())
        if not names:
            layout.label(text='No presets yet: Save Preset first')
        for n in names:
            layout.operator('mch.wrinkle_preset_load', text=n, icon='PRESET').name = n
        layout.separator()
        layout.operator('mch.wrinkle_preset_save', text='Save Preset...', icon='ADD')
        if names:
            sub = layout.column()
            for n in names:
                sub.operator('mch.wrinkle_preset_delete', text='Delete ' + n, icon='TRASH').name = n


class MCH_OT_wrinkle_presets_menu(bpy.types.Operator):
    """Your saved Cloth presets (load / save / delete)"""
    bl_idname = 'mch.wrinkle_presets_menu'
    bl_label = 'Cloth Presets'
    bl_options = {'INTERNAL'}

    def execute(self, context):
        bpy.ops.wm.call_menu(name=MCH_MT_wrinkle_presets.bl_idname)
        return {'FINISHED'}


class MCH_OT_wrinkle_reset(bpy.types.Operator):
    """Reset the Cloth Plate settings (and the selected panel) to the defaults"""
    bl_idname = 'mch.wrinkle_reset'
    bl_label = 'Reset Cloth Plate'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from . import last_used
        last_used.forget('wrinkle')
        st = context.scene.mch_wrinkle
        for name in st.bl_rna.properties.keys():
            if name not in {'rna_type', 'name'}:
                st.property_unset(name)
        ob = active_wrinkle(context)
        if ob is not None:
            size = float(ob.get('mch_wrinkle_size', 1.0)) or 1.0
            for name, _sock, default, _lo, _hi in INPUTS:
                set_input(ob, name, default)
            set_input(ob, 'Edge Soft', size * 0.03)
            set_input(ob, 'Center Fade', size * 0.3)
            set_input(ob, 'Scale', size * st.scale)
            set_input(ob, 'Detail', 2)
            set_input(ob, 'Lift', size * st.lift)
            set_input(ob, 'Strength', 0.0)
            set_input(ob, 'Stitch Inset', size * 0.045)
            set_input(ob, 'Stitch Length', size * 0.05)
            set_input(ob, 'Roll Width', size * 0.04)
            apply_preset(ob, st.wtype, size)
            apply_trim(ob, st.trim, size)
            m = ob.modifiers.get(MOD_SHELL)
            if m is not None:
                m.thickness = size * st.thickness
        self.report({'INFO'}, 'Cloth Plate settings reset')
        return {'FINISHED'}


class MCH_OT_wrinkle_reroll(bpy.types.Operator):
    """New random wrinkles (next seed)"""
    bl_idname = 'mch.wrinkle_reroll'
    bl_label = 'Reroll Wrinkles'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return active_wrinkle(context) is not None

    def execute(self, context):
        ob = active_wrinkle(context)
        set_input(ob, 'Seed', int(get_input(ob, 'Seed')) + 1)
        return {'FINISHED'}


class MCH_OT_wrinkle_apply(bpy.types.Operator):
    """Apply: the cloth layer becomes a plain mesh with the current wrinkles"""
    bl_idname = 'mch.wrinkle_apply'
    bl_label = 'Apply Wrinkles'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return active_wrinkle(context) is not None

    def execute(self, context):
        apply_wrinkle(context, active_wrinkle(context))
        return {'FINISHED'}


class MCH_OT_wrinkle_remove(bpy.types.Operator):
    """Remove the cloth layer you just drew"""
    bl_idname = 'mch.wrinkle_remove'
    bl_label = 'Remove Wrinkles'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return active_wrinkle(context) is not None

    def execute(self, context):
        ob = active_wrinkle(context)
        target = bpy.data.objects.get(ob.get('mch_wrinkle', ''))
        _remove_helper(ob)
        me = ob.data
        bpy.data.objects.remove(ob)
        if me.users == 0:
            bpy.data.meshes.remove(me)
        if target is not None and target.name in context.view_layer.objects:
            target.select_set(True)
            context.view_layer.objects.active = target
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# HUD
# -----------------------------------------------------------------------------

HUD_BUTTONS = (('apply', 'CHECKMARK', 'mch.wrinkle_apply', {}, 'Apply'),
               ('cancel', 'X', 'mch.wrinkle_remove', {}, 'Remove'),
               ('prev', 'TRIA_LEFT', 'mch.wrinkle_type', {'step': -1}, 'Previous type'),
               ('next', 'TRIA_RIGHT', 'mch.wrinkle_type', {'step': 1}, 'Next type'),
               ('reroll', 'FILE_REFRESH', 'mch.wrinkle_reroll', {}, 'New random wrinkles'),
               ('trim', 'MOD_EDGESPLIT', 'mch.wrinkle_trim', {}, 'Edge trim: none / piping / binding / welt'),
               ('reset', 'LOOP_BACK', 'mch.wrinkle_reset', {}, 'Reset to the defaults'),
               ('seam', 'IPO_SINE', 'mch.wrinkle_seam', {}, 'Section seam shape'),
               ('presets', 'PRESET', 'mch.wrinkle_presets_menu', {}, 'Your presets (load / save / delete)'),
               ('save', 'FILE_TICK', 'mch.wrinkle_preset_save', {}, 'Save these values as a preset'),
               ('skin', 'OUTLINER_OB_FORCE_FIELD', 'mch.wrinkle_skin', {'step': 1}, 'Creature skin type'),
               ('skin_edge', 'MOD_EDGESPLIT', 'mch.wrinkle_skin_edge', {}, 'Skin edge finishing'))
# key, label, input / modifier field, lo, hi, kind
SLIDERS = (('random', 'Randomness', 'Variety', 0, 100, 'RAND'),
           ('lift', 'Height', 'Lift', -50, 200, 'SIZE'),
           ('gravity', 'Gravity', 'Gravity', 0, 500, 'PCT'),
           ('skin_scale', 'Scale Size', 'Skin Scale', 2, 500, 'SIZE'),
           ('skin_depth', 'Skin Depth', 'Skin Depth', -50, 80, 'SIZE'),
           ('skin_random', 'Skin Random', 'Skin Random', 0, 100, 'PCT'),
           ('shrink', 'Edge Shrink', 'Edge Shrink', 0, 300, 'PCT'),
           ('shrink_w', 'Shrink Width', 'Shrink Width', 2, 200, 'SIZE'),
           ('skin_organic', 'Organic', 'Skin Organic', 0, 300, 'PCT'),
           ('skin_irregular', 'Edge Irregular', 'Skin Irregular', 0, 200, 'PCT'),
           ('skin_edge_w', 'Skin Edge Width', 'Skin Edge Width', 2, 200, 'SIZE'),
           ('skin_edge_h', 'Skin Edge Height', 'Skin Edge Height', -40, 40, 'SIZE'),
           ('sections', 'Sections', 'Sections', 1, 12, 'INT'),
           ('sec_turn', 'Section Turn', 'Section Turn', -180, 180, 'DEG'),
           ('sec_height', 'Section Height', 'Section Height', 0, 500, 'PCT'),
           ('sec_bend', 'Seam Bend', 'Section Bend', 0, 150, 'PCT'),
           ('sec_start', 'Section Start', 'Section Start', -50, 150, 'PCT'),
           ('sec_end', 'Section End', 'Section End', -50, 150, 'PCT'),
           ('sec_move', 'Section Move', 'Section Move', -150, 150, 'PCT'),
           ('puff', 'Puff', 'Puff', -100, 300, 'SIZE'),
           ('puff_w', 'Puff Width', 'Puff Width', 5, 500, 'SIZE'),
           ('roll', 'Edge Roll', 'Roll', -50, 100, 'SIZE'),
           ('pinch', 'Seam Folds', 'Pinch', 0, 80, 'SIZE'),
           ('pinch_sp', 'Fold Spacing', 'Pinch Spacing', 5, 200, 'SIZE'),
           ('pinch_len', 'Fold Length', 'Pinch Length', 10, 2000, 'SIZE'),
           ('sharp', 'Fold Sharp', 'Fold Sharp', 30, 3000, 'PCT'),
           ('fan', 'Fan', 'Fan', 0, 4000, 'PCT'),
           ('tilt', 'Fold Tilt', 'Fold Tilt', -80, 80, 'DEG'),
           ('tilt_rand', 'Tilt Random', 'Tilt Random', 0, 80, 'DEG'),
           ('len_rand', 'Length Random', 'Length Random', 0, 100, 'PCT'),
           ('variety', 'Variety', 'Variety', 0, 100, 'PCT'),
           ('fan_mix', 'Fan Mix', 'Fan Mix', 0, 100, 'PCT'),
           ('asym', 'Fold Asymmetry', 'Fold Asymmetry', 0, 100, 'PCT'),
           ('thin', 'Fold Thinness', 'Fold Thinness', 0, 100, 'PCT'),
           ('stitch', 'Stitching', 'Stitch', 0, 20, 'SIZE'),
           ('trim_w', 'Trim Width', 'Trim Width', 2, 200, 'SIZE'),
           ('trim_h', 'Trim Height', 'Trim Height', -50, 80, 'SIZE'),
           ('strength', 'Pattern', 'Strength', -100, 100, 'SIZE'),
           ('center_fade', 'Center Fade', 'Center Fade', 5, 600, 'SIZE'),
           ('patchy', 'Patchiness', 'Patchiness', 0, 100, 'PCT'),
           ('scale', 'Scale', 'Scale', 1, 100, 'SIZE'),
           ('direction', 'Direction', 'Direction', -180, 180, 'DEG'),
           ('bend', 'Bend', 'Bend', 0, 300, 'PCT'),
           ('detail', 'Detail', 'Detail', 0, 3, 'INT'),
           ('thickness', 'Thickness', 'THICK', 0, 50, 'SIZE'))


def slider_spec(context, key, ob=None):
    ob = ob or active_wrinkle(context)
    label, name, lo, hi, kind = next((l, nm, a, b, k) for kk, l, nm, a, b, k in SLIDERS if kk == key)
    size = float(ob.get('mch_wrinkle_size', 1.0)) or 1.0
    if name == 'THICK':
        mod = ob.modifiers.get(MOD_SHELL)
        cur = mod.thickness if mod else 0.0
        v = int(round(cur / size * 1000.0))

        def setter(val):
            m = ob.modifiers.get(MOD_SHELL)
            if m is not None:
                m.thickness = val / 1000.0 * size
                from . import last_used
                last_used.remember('wrinkle', '_thickness', m.thickness)
        return label, v, lo, hi, setter, f'{label}  {cur:.3f}'
    cur = get_input(ob, name)
    if kind == 'DEG':
        v = int(round(math.degrees(cur)))
        return label, v, lo, hi, (lambda val: set_input(ob, name, math.radians(val))), f'{label}  {v} deg'
    if kind == 'RAND':                      # one slider: angle / length / strength randomness together
        v = int(round(float(cur) * 100.0))

        def setter(val):
            r = val / 100.0
            set_input(ob, 'Tilt Random', 0.9 * r)
            set_input(ob, 'Length Random', r)
            set_input(ob, 'Variety', r)
        return label, v, lo, hi, setter, f'{label}  {v} %'
    if kind == 'PCT':
        v = int(round(cur * 100.0))
        return label, v, lo, hi, (lambda val: set_input(ob, name, val / 100.0)), f'{label}  {v} %'
    if kind == 'INT':
        v = int(cur)
        return label, v, lo, hi, (lambda val: set_input(ob, name, int(val))), f'{label}  {v}'
    v = int(round(cur / size * 1000.0))
    return label, v, lo, hi, (lambda val: set_input(ob, name, val / 1000.0 * size)), f'{label}  {cur:.3f}'


SKIN_KEYS = ('skin_scale', 'skin_depth', 'skin_random', 'shrink', 'shrink_w', 'skin_organic', 'skin_irregular',
             'skin_edge_w', 'skin_edge_h')
CREATURE_KEYS = ('lift', 'gravity', 'puff', 'puff_w') + SKIN_KEYS + ('scale', 'strength')


def slider_keys(ob):
    """Sliders shown in the popup: creature skin or cloth."""
    if is_creature(ob):
        return CREATURE_KEYS
    return tuple(k[0] for k in SLIDERS if k[0] not in SKIN_KEYS)


def hud_layout(screen_pts, region_w, region_h, btn=30.0, gap=6.0, slider_w=104.0, slider_h=20.0, keys=None):
    pts = [p for p in screen_pts if p is not None]
    if not pts:
        return {}
    keys = [k[0] for k in SLIDERS] if keys is None else list(keys)
    step = btn + gap
    room = max(slider_h + gap, region_h - step * 5 - btn)
    per_col = max(1, int(room // (slider_h + gap)))
    cols = max(1, -(-len(keys) // per_col))
    per_col = -(-len(keys) // cols)
    x = min(max(max(p[0] for p in pts) + btn * 1.2, btn), region_w - (slider_w + gap) * cols - btn)
    total = step * 5 + (slider_h + gap) * per_col
    top = min(max((max(p[1] for p in pts) + min(p[1] for p in pts)) / 2 + total / 2, total), region_h - btn)
    out = {'apply': (x, top), 'cancel': (x, top - step), 'prev': (x, top - 2 * step),
           'next': (x + step, top - 2 * step), 'reroll': (x + 2 * step, top - 2 * step),
           'trim': (x, top - 3 * step), 'reset': (x + step, top - 3 * step), 'seam': (x + 2 * step, top - 3 * step),
           'presets': (x + 3 * step, top - 3 * step), 'save': (x + 4 * step, top - 3 * step),
           'skin': (x, top - 4 * step), 'skin_edge': (x + step, top - 4 * step)}
    y0 = top - 5 * step
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
    ob = active_wrinkle(context)
    region, rv3d = context.region, context.region_data
    if ob is None:
        release_anchor('wrinkle')
        return None, {}
    if region is None or rv3d is None:
        return None, {}
    from bpy_extras import view3d_utils
    ui = context.preferences.system.ui_scale
    pts = []
    for c in ob.bound_box:
        q = view3d_utils.location_3d_to_region_2d(region, rv3d, ob.matrix_world @ Vector(c))
        pts.append(None if q is None else (q[0] / ui, q[1] / ui))
    keys = slider_keys(ob)
    return ob, anchored('wrinkle', ob.name + '/' + str(len(keys)), region,
                        hud_layout(pts, region.width / ui, region.height / ui, keys=keys))


class MCH_GT_wrinkle_slider(bpy.types.Gizmo):
    bl_idname = 'MCH_GT_wrinkle_slider'
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
        step = 20.0 if self.key in {'detail', 'sections'} else 3.0
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
            from . import last_used
            last_used.save()                       # kept right away (not only every 20 s)
            try:
                bpy.ops.ed.undo_push(message='Wrinkle ' + self.key)
            except RuntimeError:
                pass


class MCH_GGT_wrinkle_hud(bpy.types.GizmoGroup):
    bl_idname = 'MCH_GGT_wrinkle_hud'
    bl_label = 'Cloth Wrinkle HUD'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and active_wrinkle(context) is not None

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
            gz = self.gizmos.new(MCH_GT_wrinkle_slider.bl_idname)
            gz.key = key
            gz.color = (0.24, 0.27, 0.32)
            gz.alpha = 0.95
            gz.color_highlight = (0.36, 0.40, 0.47)
            gz.alpha_highlight = 1.0
            gz.use_draw_scale = False
            self.items['slider_' + key] = gz

    def draw_prepare(self, context):
        _ob, lay = _hud_current(context)
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


_label_handle = None


def _draw_labels():
    try:
        context = bpy.context
        ob, lay = _hud_current(context)
        if ob is None or not lay:
            return
        import blf
        ui = context.preferences.system.ui_scale
        blf.size(0, 11 * ui)
        tname = TYPES[max(0, min(2, int(get_input(ob, 'Type'))))][1]
        trim = TRIMS[max(0, min(3, int(get_input(ob, 'Trim'))))][1]
        seam = SECTION_SHAPES[max(0, min(4, int(get_input(ob, 'Section Shape'))))]
        for key, text in (('apply', 'Apply'), ('cancel', 'Remove'), ('reroll', tname),
                          ('seam', trim + '  |  Seams: ' + seam)):
            x, y = lay[key]
            blf.color(0, *((1.0, 0.62, 0.16) if key == 'apply' else (0.85, 0.87, 0.9)), 1.0)
            blf.position(0, (x + 21) * ui, (y - 4) * ui, 0)
            blf.draw(0, text)
        if 'skin' in lay:
            x, y = lay['skin_edge']
            label = (dict((a, b) for a, b, _c in SKINS).get(ob.get('mch_creature'), 'Creature Skin')
                     + '  |  ' + SKIN_EDGES[max(0, min(3, int(get_input(ob, 'Skin Edge'))))][1]) \
                if is_creature(ob) else 'Creature Skin'
            blf.color(0, 0.85, 0.87, 0.9, 1.0)
            blf.position(0, (x + 21) * ui, (y - 4) * ui, 0)
            blf.draw(0, label)
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


def draw(layout, context):
    st = context.scene.mch_wrinkle
    box = layout.box()
    hdr = box.row(align=True)
    hdr.label(text='CLOTH PLATE: draw on a mesh', icon='MOD_CLOTH')
    hdr.operator('mch.wrinkle_reset', text='', icon='LOOP_BACK')
    pr = box.row(align=True)
    pr.menu('MCH_MT_wrinkle_presets', text='My Presets', icon='PRESET')
    pr.operator('mch.wrinkle_preset_save', text='', icon='ADD')
    cr = box.row(align=True)
    cr.prop(st, 'creature', toggle=True, icon='OUTLINER_OB_FORCE_FIELD')
    if st.creature:
        box.row(align=True).prop(st, 'skin', expand=True)
        box.label(text='Creature Skin: scales shrink toward the border, skin grain on the edge (popup sliders)')
    box.row(align=True).prop(st, 'wtype', expand=True)
    box.label(text='Edge Trim')
    box.row(align=True).prop(st, 'trim', expand=True)
    col = box.column(align=True)
    col.prop(st, 'lift', slider=True)
    col.prop(st, 'sections')
    box.prop(st, 'pattern', toggle=True, text='All-over Pattern (optional)')
    col = box.column(align=True)
    col.active = st.pattern
    col.prop(st, 'strength', slider=True)
    col.prop(st, 'scale', slider=True)
    c2 = box.column(align=True)
    c2.prop(st, 'thickness', slider=True)
    c2.prop(st, 'spacing')
    ob = active_wrinkle(context)
    if ob is not None:
        sub = box.box()
        sub.label(text=f'LIVE: {ob.name} (until Apply)', icon='MOD_CLOTH')
        mod = ob.modifiers.get(MOD)
        c = sub.column(align=True)
        for name, *_r in INPUTS:
            c.prop(mod, f'["{_ident(name)}"]', text=name)
        r = sub.row(align=True)
        r.scale_y = 1.3
        r.operator('mch.wrinkle_apply', text='Apply', icon='CHECKMARK')
        r.operator('mch.wrinkle_remove', text='Remove', icon='X')
    c = box.column(align=True)
    c.scale_y = 0.8
    c.label(text='Draw a lasso on a mesh: a separate cloth layer', icon='INFO')
    c.label(text='Wrinkles are Geometry Nodes: change them live')
    c.label(text='Apply bakes; the mesh you draw on is not changed')


CLASSES = (MCH_PG_Wrinkle, MCH_OT_wrinkle_preset_save, MCH_OT_wrinkle_preset_load, MCH_OT_wrinkle_preset_delete,
           MCH_MT_wrinkle_presets, MCH_OT_wrinkle_presets_menu, MCH_OT_wrinkle_type, MCH_OT_wrinkle_trim, MCH_OT_wrinkle_seam, MCH_OT_wrinkle_reset, MCH_OT_wrinkle_reroll, MCH_OT_wrinkle_apply, MCH_OT_wrinkle_remove,
           MCH_GT_wrinkle_slider, MCH_GGT_wrinkle_hud, MCH_OT_wrinkle_skin, MCH_OT_wrinkle_skin_edge,
           MCH_OT_creature_brush)


def register():
    global _label_handle
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_wrinkle = bpy.props.PointerProperty(type=MCH_PG_Wrinkle)
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
    if hasattr(bpy.types.Scene, 'mch_wrinkle'):
        del bpy.types.Scene.mch_wrinkle
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
