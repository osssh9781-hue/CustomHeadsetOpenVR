"""0.24.157 Fur (user: "털도 방법이 있니? 내가 지정한 영역에 털이 생겼으면 좋겠는데 기장, 곱슬, 끝이 모이는지, 중력, 두께랑 팁
두께" ... "색은 폴리페인트에서 가져오는 것도 넣어 주고 지오메트리 노드로 해 볼까 봐").

Draw an area on a body with the shared lasso (every shape, Line too): fur grows there - a live hair Curves object made
by Geometry Nodes (thousands of strands stay light; Cycles / EEVEE render them as hair).  The area is a weight on the
body's points (attribute ``mch_fur_<id>``), so the fur follows the body when it changes; Edge Soft blurs its border.

    draw            add to the selected fur's area (a fur of that body), else a new fur
    Alt + draw      take the area away from the selected fur
    New Fur         the next draw makes a new fur (its own settings)

Strands: Density (per square metre: more area, more strands), Length (+ Random), Lie Down (the angle from the skin's normal: 0 standing out, 90 flat) and
Flow Angle (which way they tilt, turned round the normal: 0 = down the body) - 0.24.159 (user: "노말 방향으로 기울기를 내가
조정하면 안 빗어도 되잖아" -> "영역마다 기울기 기억") each area drawn keeps its own Lie Down / Flow Angle (pick it in the
window, change it: only that part; Part Soft blends the borders), Gravity (bends them down toward the tip),
Curl (+ Turns), Frizz (small random wobble), Clump (tips gathered into tufts of about Clump Size strands), Root /
Tip Thickness, Segments.  Colour: the body's polypaint (its colour attribute, sampled at each root) or a Root Colour,
going to the Tip Colour by Tip Blend.  Viewport %: the share drawn in the viewport (all of them render).

The geometry is built in the node group ``MCH Fur`` (one for every fur; each fur's modifier holds its values): the
body's area -> points (Distribute Points on Faces, Density x the area weight) -> a line per point ->
directions summed along each strand (Accumulate Field: lie, flow, gravity, curl, frizz) -> clumped to the nearest
guide strand -> radius root to tip -> colour attribute ``mch_fur_col`` (the material ``MCH Fur`` reads it).
"""
from __future__ import annotations

import math
import uuid

import bpy
import numpy as np
from bpy.props import BoolProperty, FloatProperty, FloatVectorProperty, IntProperty
from mathutils import Matrix, Vector

from . import core_geometry as cg

TREE = 'MCH Fur'
TREE_VERSION = 12                  # 0.24.171 Bend
MOD = 'MCH Fur'
MAT = 'MCH Fur'
AREA_KEY = 'mch_fur_area'          # on a fur object: the body attribute that holds its area
FUR_KEY = 'mch_fur'                # on a fur object (1)
NEW_KEY = 'mch_fur_new'            # window manager flag: the next draw makes a new fur
COLLECTION = 'Creature Fur'
PART_KEY = 'mch_fur_parts'         # on a fur object: the body attribute naming each point's area (1, 2 ...; 0 none)
LIE_KEY = 'mch_fur_lies'           # ... its tilt from the normal there (radians)
FLOW_KEY = 'mch_fur_flows'         # ... which way it tilts there ((cos, sin, 0) of the Flow Angle)
LOOK_KEY = 'mch_fur_looks'         # 0.24.160 ... its Curl, Clump, Tip Gather there (a vector)

# (prop, socket name, socket type, default, min, max) - the values each fur keeps (its modifier's inputs)
LIVE = (
    ('density', 'Density', 'FLOAT', 40000.0, 1.0, 2000000.0),
    ('length', 'Length', 'FLOAT', 0.05, 0.0005, 5.0),
    ('length_random', 'Length Random', 'FLOAT', 0.35, 0.0, 0.95),
    ('lie', 'Lie Down', 'FLOAT', math.radians(50), 0.0, math.pi / 2),
    ('flow', 'Flow Angle', 'FLOAT', 0.0, -2 * math.pi, 2 * math.pi),
    ('volume', 'Volume', 'FLOAT', 0.5, 0.0, 1.0),
    ('spread', 'Spread', 'FLOAT', 0.3, 0.0, 1.0),
    ('gravity', 'Gravity', 'FLOAT', 0.4, 0.0, 5.0),
    ('curl', 'Curl', 'FLOAT', 0.0, 0.0, 3.0),
    ('curl_turns', 'Curl Turns', 'FLOAT', 2.0, 0.0, 20.0),
    ('frizz', 'Frizz', 'FLOAT', 0.15, 0.0, 2.0),
    ('clump', 'Clump', 'FLOAT', 0.25, 0.0, 1.0),
    ('clump_size', 'Clump Size', 'INT', 12, 1, 500),
    ('gather', 'Tip Gather', 'FLOAT', 0.0, 0.0, 1.0),
    ('root_thick', 'Root Thickness', 'FLOAT', 0.001, 0.00001, 0.05),
    ('tip_thick', 'Tip Thickness', 'FLOAT', 0.00015, 0.0, 0.05),
    ('segments', 'Segments', 'INT', 8, 2, 64),
    ('edge_soft', 'Edge Soft', 'INT', 3, 0, 60),
    ('part_soft', 'Part Soft', 'INT', 3, 0, 60),
    ('use_polypaint', 'Use Polypaint', 'BOOL', True, None, None),
    ('root_color', 'Root Color', 'COLOR', (0.32, 0.22, 0.14, 1.0), None, None),
    ('tip_color', 'Tip Color', 'COLOR', (0.75, 0.62, 0.45, 1.0), None, None),
    ('tip_blend', 'Tip Blend', 'FLOAT', 0.25, 0.0, 1.0),
    ('display', 'Viewport %', 'FLOAT', 1.0, 0.0, 1.0),
    ('seed', 'Seed', 'INT', 0, 0, 100000),
    # 0.24.171 (user: "머리카락을 내가 보는 뷰포트 방향에서 꺾을 수 있게 밴드 옵션") toward a side of the view
    ('bend', 'Bend', 'FLOAT', 0.0, 0.0, math.pi),
    ('bend_at', 'Bend At', 'FLOAT', 0.3, 0.0, 0.95),
    ('bend_soft', 'Bend Soft', 'FLOAT', 0.35, 0.0, 1.0),
)
LIVE_NAMES = {p: s for p, s, *_r in LIVE}
DESCS = {
    'density': 'Strands per square metre of the area (20000: 2 a square centimetre) - more area, more strands',
    'length': 'A strand\'s length',
    'length_random': 'Some strands shorter (0.35: down to 65 %)',
    'lie': 'The tilt from the skin\'s normal: 0 standing straight out of the skin, 90 flat on it (the selected area\'s)',
    'flow': 'Which way it tilts, turned round the normal: 0 down the body (the selected area\'s)',
    'part_soft': 'Between areas tilted differently: blended over this many rings of points (0: a sharp border)',
    'volume': 'Fuller fur: the strands rise off the skin at the root and bend over into their tilt toward the tip',
    'spread': 'Fuller fur: each strand\'s tilt and direction a little different, at random',
    'gather': 'The area\'s tips gathered to one point - the end of its tilt (a tuft / a point); the selected area\'s',
    'gravity': 'Bends the strands down toward their tips',
    'curl': 'Curls round each strand (how wide) - the selected area\'s',
    'curl_turns': 'How many turns along a strand',
    'frizz': 'A small random wobble along each strand',
    'clump': 'Tips gathered into tufts (1: the tips meet) - the selected area\'s',
    'clump_size': 'About how many strands in a tuft',
    'root_thick': 'A strand\'s thickness at the skin',
    'tip_thick': 'A strand\'s thickness at its tip',
    'segments': 'Points along a strand (more: smoother curls)',
    'edge_soft': 'The area\'s border thinned out softly (0: a hard edge)',
    'use_polypaint': 'The colour at each root from the body\'s polypaint (its colour attribute); off: Root Color',
    'root_color': 'The colour at the root (when not from the polypaint)',
    'tip_color': 'The colour the strands go to at their tips (by Tip Blend)',
    'tip_blend': 'How far the tips go to the Tip Color (0: the root colour all along)',
    'display': 'The share of strands drawn in the viewport (all of them render)',
    'seed': 'Another random mix',
    'bend': 'How far the strands turn toward the bend direction (a side of the view, set by the buttons; 0 = none)',
    'bend_at': 'Where along the strands they bend (0 = at the root, 0.9 = near the tip)',
    'bend_soft': '0 = a sharp kink, 1 = a long smooth curve',
}


# ---- the node group ------------------------------------------------------------------------------------------------

class _B:
    """A small node-tree writer: values are sockets (linked) or constants (set)."""

    def __init__(self, ng):
        self.ng, self.N, self.L = ng, ng.nodes, ng.links
        self.x = 0

    def node(self, kind, **props):
        n = self.N.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        n.location = (self.x, 0)
        self.x += 30
        return n

    def feed(self, inp, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.L.new(v, inp)
        elif v is not None:
            inp.default_value = v

    def math(self, op, a, b=None, c=None):
        n = self.node('ShaderNodeMath', operation=op)
        self.feed(n.inputs[0], a)
        if b is not None:
            self.feed(n.inputs[1], b)
        if c is not None:
            self.feed(n.inputs[2], c)
        return n.outputs[0]

    def vec(self, op, a, b=None, scale=None):
        n = self.node('ShaderNodeVectorMath', operation=op)
        self.feed(n.inputs[0], a)
        if b is not None:
            self.feed(n.inputs[1], b)
        if scale is not None:
            self.feed(n.inputs['Scale'], scale)
        return n.outputs['Value'] if op in {'DOT_PRODUCT', 'LENGTH', 'DISTANCE'} else n.outputs['Vector']

    def attr(self, name, kind='FLOAT'):
        n = self.node('GeometryNodeInputNamedAttribute', data_type=kind)
        self.feed(n.inputs['Name'], name)
        return n

    def store(self, geo, name, value, kind='FLOAT', domain='POINT'):
        n = self.node('GeometryNodeStoreNamedAttribute', data_type=kind, domain=domain)
        self.feed(n.inputs['Geometry'], geo)
        self.feed(n.inputs['Name'], name)
        self.feed(n.inputs['Value'], value)
        return n.outputs['Geometry']

    @staticmethod
    def _on(sockets):
        return [x for x in sockets if getattr(x, 'enabled', True) and not getattr(x, 'is_unavailable', False)]

    def random(self, ident, seed, lo=0.0, hi=1.0):
        n = self.node('FunctionNodeRandomValue', data_type='FLOAT')
        ins = {x.name: x for x in self._on(n.inputs)}
        ins['Min'].default_value = lo
        ins['Max'].default_value = hi
        self.feed(ins['ID'], ident)
        self.feed(ins['Seed'], seed)
        return self._on(n.outputs)[0]

    def _mix(self, kind, f, a, b):
        n = self.node('ShaderNodeMix', data_type=kind)
        ins = self._on(n.inputs)                          # (Factor, A, B of that type)
        self.feed(ins[0], f)
        self.feed(ins[1], a)
        self.feed(ins[2], b)
        return self._on(n.outputs)[0]

    def mix_vec(self, f, a, b):
        return self._mix('VECTOR', f, a, b)

    def mix_col(self, f, a, b):
        return self._mix('RGBA', f, a, b)

    def imath(self, op, a, b):
        try:
            n = self.node('FunctionNodeIntegerMath', operation=op)
        except RuntimeError:
            return self.math(op, a, b)
        self.feed(n.inputs[0], a)
        self.feed(n.inputs[1], b)
        return n.outputs[0]


def _socket(ng, name, kind, default=None, lo=None, hi=None):
    st = {'INT': 'NodeSocketInt', 'FLOAT': 'NodeSocketFloat', 'BOOL': 'NodeSocketBool', 'COLOR': 'NodeSocketColor',
          'OBJECT': 'NodeSocketObject', 'STRING': 'NodeSocketString', 'MATERIAL': 'NodeSocketMaterial',
          'GEOMETRY': 'NodeSocketGeometry', 'VECTOR': 'NodeSocketVector'}[kind]
    s = ng.interface.new_socket(name, in_out='INPUT', socket_type=st)
    if default is not None:
        s.default_value = default
    if lo is not None and hasattr(s, 'min_value'):
        s.min_value, s.max_value = lo, hi
    return s


def fur_tree():
    """The shared node group (made once, rebuilt when TREE_VERSION changes)."""
    ng = bpy.data.node_groups.get(TREE)
    if ng is not None and ng.get('mch_v') == TREE_VERSION:
        return ng
    if ng is None:
        ng = bpy.data.node_groups.new(TREE, 'GeometryNodeTree')
    ng.nodes.clear()
    ng.interface.clear()
    _socket(ng, 'Geometry', 'GEOMETRY')
    _socket(ng, 'Body', 'OBJECT')
    _socket(ng, 'Area', 'STRING')
    _socket(ng, 'Lie Attr', 'STRING')
    _socket(ng, 'Flow Attr', 'STRING')
    _socket(ng, 'Look Attr', 'STRING')
    _socket(ng, 'Part Attr', 'STRING')
    _socket(ng, 'Color Attribute', 'STRING')
    _socket(ng, 'Material', 'MATERIAL')
    for _p, name, kind, default, lo, hi in LIVE:
        _socket(ng, name, kind, default, lo, hi)
    _socket(ng, 'Bend Dir', 'VECTOR', (1.0, 0.0, 0.0))             # (0.24.171 in the body's space)
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    b = _B(ng)
    gi = b.node('NodeGroupInput')
    go = b.node('NodeGroupOutput')
    I = gi.outputs

    # the body and its area (blurred: Edge Soft)
    oi = b.node('GeometryNodeObjectInfo', transform_space='ORIGINAL')
    b.feed(oi.inputs['Object'], I['Body'])
    w0 = b.attr(I['Area']).outputs['Attribute']
    blur = b.node('GeometryNodeBlurAttribute', data_type='FLOAT')
    b.feed(blur.inputs['Value'], w0)
    b.feed(blur.inputs['Iterations'], I['Edge Soft'])
    body = b.store(oi.outputs['Geometry'], 'mch_fur_w', b.math('MULTIPLY', blur.outputs['Value'], w0))
    # (0.24.159 each area's own tilt: taken below, from the area's own points)  # (soft inside:
    #                                                                                   never past what was drawn)
    w = b.attr('mch_fur_w').outputs['Attribute']
    density = I['Density']
    dist = b.node('GeometryNodeDistributePointsOnFaces', distribute_method='RANDOM')
    b.feed(dist.inputs['Mesh'], body)
    b.feed(dist.inputs['Selection'], b.math('GREATER_THAN', w, 0.0001))
    b.feed(dist.inputs['Density'], density)
    b.feed(dist.inputs['Seed'], I['Seed'])
    # each point kept by the area's weight at it (the weight read where the point is, not over the whole face): a
    # face on the area's border gets fur only toward its inside corners - the border follows the drawn line
    pts = b.store(dist.outputs['Points'], 'mch_fn', dist.outputs['Normal'], 'FLOAT_VECTOR')
    thin = b.node('GeometryNodeDeleteGeometry', domain='POINT')
    b.feed(thin.inputs['Geometry'], pts)
    b.feed(thin.inputs['Selection'], b.math('GREATER_THAN', b.random(b.node('GeometryNodeInputIndex').outputs['Index'],
                                                                     b.math('ADD', I['Seed'], 71.0)), w))
    pts = thin.outputs['Geometry']
    idx = b.node('GeometryNodeInputIndex').outputs['Index']
    pos = b.node('GeometryNodeInputPosition').outputs['Position']
    pts = b.store(pts, 'mch_p0', pos, 'FLOAT_VECTOR')
    pts = b.store(pts, 'mch_i', idx, 'INT')
    # 0.24.159 each area's own tilt (Lie Down, Flow Angle) a point of the body: the area cut out of the body, blended
    # there between areas (Part Soft), each root taking the nearest area point's - points outside the area never
    # count (on a face across the area's border they would tilt the roots there); a fur with none stored (before
    # 0.24.159) uses its Lie Down / Flow Angle everywhere
    lraw = b.attr(I['Lie Attr'])
    fraw = b.attr(I['Flow Attr'], 'FLOAT_VECTOR')
    cut = b.node('GeometryNodeSeparateGeometry', domain='POINT')
    b.feed(cut.inputs['Geometry'], body)
    b.feed(cut.inputs['Selection'], b.math('GREATER_THAN', w0, 0.0))
    lblur = b.node('GeometryNodeBlurAttribute', data_type='FLOAT')
    b.feed(lblur.inputs['Value'], lraw.outputs['Attribute'])
    b.feed(lblur.inputs['Iterations'], I['Part Soft'])
    fblur = b.node('GeometryNodeBlurAttribute', data_type='FLOAT_VECTOR')
    b.feed(fblur.inputs['Value'], fraw.outputs['Attribute'])
    b.feed(fblur.inputs['Iterations'], I['Part Soft'])
    kraw = b.attr(I['Look Attr'], 'FLOAT_VECTOR')                          # (0.24.160 Curl, Clump, Tip Gather)
    kblur = b.node('GeometryNodeBlurAttribute', data_type='FLOAT_VECTOR')
    b.feed(kblur.inputs['Value'], kraw.outputs['Attribute'])
    b.feed(kblur.inputs['Iterations'], I['Part Soft'])
    amesh = b.store(cut.outputs['Selection'], 'mch_tl', lblur.outputs['Value'])
    amesh = b.store(amesh, 'mch_tf', fblur.outputs['Value'], 'FLOAT_VECTOR')
    amesh = b.store(amesh, 'mch_tk', kblur.outputs['Value'], 'FLOAT_VECTOR')
    amesh = b.store(amesh, 'mch_tp', b.attr(I['Part Attr'], 'INT').outputs['Attribute'], 'INT')
    nearest = b.node('GeometryNodeSampleNearest', domain='POINT')
    b.feed(nearest.inputs['Geometry'], amesh)
    b.feed(nearest.inputs['Sample Position'], b.node('GeometryNodeInputPosition').outputs['Position'])
    sl = b.node('GeometryNodeSampleIndex', data_type='FLOAT', domain='POINT')
    b.feed(sl.inputs['Geometry'], amesh)
    b.feed(sl.inputs['Value'], b.attr('mch_tl').outputs['Attribute'])
    b.feed(sl.inputs['Index'], nearest.outputs['Index'])
    sf = b.node('GeometryNodeSampleIndex', data_type='FLOAT_VECTOR', domain='POINT')
    b.feed(sf.inputs['Geometry'], amesh)
    b.feed(sf.inputs['Value'], b.attr('mch_tf', 'FLOAT_VECTOR').outputs['Attribute'])
    b.feed(sf.inputs['Index'], nearest.outputs['Index'])
    gflow = b.node('ShaderNodeCombineXYZ')
    b.feed(gflow.inputs[0], b.math('COSINE', I['Flow Angle']))
    b.feed(gflow.inputs[1], b.math('SINE', I['Flow Angle']))
    lsw = b.node('GeometryNodeSwitch', input_type='FLOAT')
    b.feed(lsw.inputs['Switch'], lraw.outputs['Exists'])
    b.feed(lsw.inputs['False'], I['Lie Down'])
    b.feed(lsw.inputs['True'], sl.outputs['Value'])
    fsw = b.node('GeometryNodeSwitch', input_type='VECTOR')
    b.feed(fsw.inputs['Switch'], fraw.outputs['Exists'])
    b.feed(fsw.inputs['False'], gflow.outputs['Vector'])
    b.feed(fsw.inputs['True'], sf.outputs['Value'])
    pts = b.store(pts, 'mch_fur_lie', lsw.outputs['Output'])
    pts = b.store(pts, 'mch_fur_fl', fsw.outputs['Output'], 'FLOAT_VECTOR')
    sk = b.node('GeometryNodeSampleIndex', data_type='FLOAT_VECTOR', domain='POINT')
    b.feed(sk.inputs['Geometry'], amesh)
    b.feed(sk.inputs['Value'], b.attr('mch_tk', 'FLOAT_VECTOR').outputs['Attribute'])
    b.feed(sk.inputs['Index'], nearest.outputs['Index'])
    glook = b.node('ShaderNodeCombineXYZ')
    b.feed(glook.inputs[0], I['Curl'])
    b.feed(glook.inputs[1], I['Clump'])
    b.feed(glook.inputs[2], I['Tip Gather'])
    ksw = b.node('GeometryNodeSwitch', input_type='VECTOR')
    b.feed(ksw.inputs['Switch'], kraw.outputs['Exists'])
    b.feed(ksw.inputs['False'], glook.outputs['Vector'])
    b.feed(ksw.inputs['True'], sk.outputs['Value'])
    pts = b.store(pts, 'mch_fur_look', ksw.outputs['Output'], 'FLOAT_VECTOR')
    spart = b.node('GeometryNodeSampleIndex', data_type='INT', domain='POINT')
    b.feed(spart.inputs['Geometry'], amesh)
    b.feed(spart.inputs['Value'], b.attr('mch_tp', 'INT').outputs['Attribute'])
    b.feed(spart.inputs['Index'], nearest.outputs['Index'])
    pts = b.store(pts, 'mch_fur_part', spart.outputs['Value'], 'INT')
    pp = b.attr(I['Color Attribute'], 'FLOAT_COLOR')
    use_pp = b.node('FunctionNodeBooleanMath', operation='AND')
    b.feed(use_pp.inputs[0], I['Use Polypaint'])
    b.feed(use_pp.inputs[1], pp.outputs['Exists'])
    sw = b.node('GeometryNodeSwitch', input_type='RGBA')
    b.feed(sw.inputs['Switch'], use_pp.outputs[0])
    b.feed(sw.inputs['False'], I['Root Color'])
    b.feed(sw.inputs['True'], pp.outputs['Attribute'])
    pts = b.store(pts, 'mch_rc', sw.outputs['Output'], 'FLOAT_COLOR')
    pts = b.store(pts, 'mch_lr', b.random(idx, I['Seed']))                    # (length random)
    pts = b.store(pts, 'mch_ph', b.random(idx, b.math('ADD', I['Seed'], 17.0)))   # (curl phase)
    frac = b.math('DIVIDE', 1.0, b.math('MAXIMUM', I['Clump Size'], 1.0))
    guide = b.node('FunctionNodeBooleanMath', operation='OR')
    b.feed(guide.inputs[0], b.math('LESS_THAN', b.random(idx, b.math('ADD', I['Seed'], 31.0)), frac))
    b.feed(guide.inputs[1], b.math('LESS_THAN', idx, 0.5))                    # (at least one guide)
    pts = b.store(pts, 'mch_g', guide.outputs[0], 'BOOLEAN')

    # a line per point, Segments long
    line = b.node('GeometryNodeCurvePrimitiveLine')
    line.inputs['End'].default_value = (0.0, 0.0, 1.0)
    rs = b.node('GeometryNodeResampleCurve')
    b.feed(rs.inputs['Curve'], line.outputs['Curve'])
    try:
        rs.inputs['Mode'].default_value = 'Count'
    except (KeyError, TypeError, AttributeError):
        pass
    b.feed(rs.inputs['Count'], b.math('ADD', I['Segments'], 1.0))
    iop = b.node('GeometryNodeInstanceOnPoints')
    b.feed(iop.inputs['Points'], pts)
    b.feed(iop.inputs['Instance'], rs.outputs['Curve'])
    real = b.node('GeometryNodeRealizeInstances')
    b.feed(real.inputs['Geometry'], iop.outputs['Instances'])
    curves = real.outputs['Geometry']

    # the shape: directions summed along each strand
    t = b.node('GeometryNodeSplineParameter').outputs['Factor']
    cop = b.node('GeometryNodeCurveOfPoint')
    b.feed(cop.inputs['Point Index'], b.node('GeometryNodeInputIndex').outputs['Index'])
    cidx, kin = cop.outputs['Curve Index'], cop.outputs['Index in Curve']
    n_ = b.vec('NORMALIZE', b.attr('mch_fn', 'FLOAT_VECTOR').outputs['Attribute'])
    inv = b.node('FunctionNodeInvertMatrix')
    b.feed(inv.inputs['Matrix'], oi.outputs['Transform'])
    td = b.node('FunctionNodeTransformDirection')
    td.inputs['Direction'].default_value = (0.0, 0.0, -1.0)
    b.feed(td.inputs['Transform'], inv.outputs['Matrix'])
    down = b.vec('NORMALIZE', td.outputs['Direction'])                        # (world down, in the body's space)
    f0 = b.vec('SUBTRACT', down, b.vec('SCALE', n_, scale=b.vec('DOT_PRODUCT', down, n_)))
    side = b.vec('CROSS_PRODUCT', n_, (1.0, 0.0, 0.0))
    f = b.vec('NORMALIZE', b.vec('ADD', f0, b.vec('SCALE', side, scale=0.002)))  # (flat on the skin, down it)
    # the area's direction: turned round the normal by its Flow Angle ((cos, sin) at the point, blended)
    cs = b.node('ShaderNodeSeparateXYZ')
    b.feed(cs.inputs[0], b.vec('NORMALIZE', b.vec('ADD', b.attr('mch_fur_fl', 'FLOAT_VECTOR').outputs['Attribute'],
                                                    (1e-6, 0.0, 0.0))))
    f = b.vec('ADD', b.vec('SCALE', f, scale=cs.outputs['X']),
              b.vec('SCALE', b.vec('CROSS_PRODUCT', n_, f), scale=cs.outputs['Y']))
    # 0.24.160 Spread: each strand's direction turned a little round the normal and its tilt a little more / less
    sid = b.attr('mch_i', 'INT').outputs['Attribute']
    turn = b.math('MULTIPLY', b.random(sid, b.math('ADD', I['Seed'], 41.0), -1.0, 1.0), b.math('MULTIPLY', I['Spread'], 0.9))
    f = b.vec('ADD', b.vec('SCALE', f, scale=b.math('COSINE', turn)),
              b.vec('SCALE', b.vec('CROSS_PRODUCT', n_, f), scale=b.math('SINE', turn)))
    lie_s = b.math('ADD', b.attr('mch_fur_lie').outputs['Attribute'], b.math(
        'MULTIPLY', b.random(sid, b.math('ADD', I['Seed'], 43.0), -1.0, 1.0), b.math('MULTIPLY', I['Spread'], 0.5)))
    lie_s = b.math('MINIMUM', b.math('MAXIMUM', lie_s, 0.0), math.pi / 2)       # (an angle from the normal)
    # 0.24.160 Volume: the strand rises off the skin at its root and bends over into its tilt toward the tip
    lie_root = b.math('MULTIPLY', lie_s, b.math('SUBTRACT', 1.0, b.math('MULTIPLY', I['Volume'], 0.85)))
    lie = b.math('ADD', lie_root, b.math('MULTIPLY', b.math('SUBTRACT', lie_s, lie_root), b.math('POWER', t, 0.6)))
    look = b.node('ShaderNodeSeparateXYZ')
    b.feed(look.inputs[0], b.attr('mch_fur_look', 'FLOAT_VECTOR').outputs['Attribute'])
    d0 = b.vec('NORMALIZE', b.vec('ADD', b.vec('SCALE', n_, scale=b.math('COSINE', lie)),
                                  b.vec('SCALE', f, scale=b.math('SINE', lie))))
    d = b.vec('ADD', d0, b.vec('SCALE', down, scale=b.math('MULTIPLY', I['Gravity'], t)))
    wv = b.vec('NORMALIZE', b.vec('CROSS_PRODUCT', n_, f))
    vv = b.vec('CROSS_PRODUCT', d0, wv)
    ph = b.math('ADD', b.math('MULTIPLY', b.math('MULTIPLY', I['Curl Turns'], t), 2 * math.pi),
                b.math('MULTIPLY', b.attr('mch_ph').outputs['Attribute'], 2 * math.pi))
    curl = b.vec('SCALE', b.vec('ADD', b.vec('SCALE', wv, scale=b.math('COSINE', ph)),
                                b.vec('SCALE', vv, scale=b.math('SINE', ph))), scale=look.outputs['X'])
    noise = b.node('ShaderNodeTexNoise', noise_dimensions='4D')
    p0 = b.attr('mch_p0', 'FLOAT_VECTOR').outputs['Attribute']
    b.feed(noise.inputs['Vector'], b.vec('SCALE', p0, scale=40.0))
    b.feed(noise.inputs['W'], b.math('MULTIPLY', t, 9.0))                   # (a few wobbles along a strand)
    noise.inputs['Scale'].default_value = 1.0
    fr = b.vec('SCALE', b.vec('SUBTRACT', noise.outputs['Color'], (0.5, 0.5, 0.5)),
               scale=b.math('MULTIPLY', b.math('MULTIPLY', I['Frizz'], 5.0), b.math('ADD', b.math('MULTIPLY', t, 0.7), 0.3)))
    dirn = b.vec('NORMALIZE', b.vec('ADD', b.vec('ADD', d, curl), fr))
    # 0.24.171 Bend: from Bend At on, each piece turned toward Bend Dir by up to Bend (never past it), eased in over
    # Bend Soft of the strand
    bx = b.math('MINIMUM', b.math('MAXIMUM', b.math('DIVIDE', b.math('SUBTRACT', t, I['Bend At']),
                                                     b.math('MAXIMUM', I['Bend Soft'], 0.001)), 0.0), 1.0)
    bw = b.math('MULTIPLY', b.math('MULTIPLY', bx, bx), b.math('SUBTRACT', 3.0, b.math('MULTIPLY', bx, 2.0)))
    bdir = b.vec('NORMALIZE', I['Bend Dir'])
    bcos = b.math('MINIMUM', b.math('MAXIMUM', b.vec('DOT_PRODUCT', dirn, bdir), -1.0), 1.0)
    bang = b.math('MINIMUM', b.math('MULTIPLY', I['Bend'], bw), b.math('ARCCOSINE', bcos))
    brot = b.node('ShaderNodeVectorRotate', rotation_type='AXIS_ANGLE')
    b.feed(brot.inputs['Vector'], dirn)
    b.feed(brot.inputs['Axis'], b.vec('NORMALIZE', b.vec('CROSS_PRODUCT', dirn, bdir)))
    b.feed(brot.inputs['Angle'], bang)
    dirn = brot.outputs['Vector']
    ln = b.math('MULTIPLY', I['Length'], b.math('SUBTRACT', 1.0, b.math(
        'MULTIPLY', I['Length Random'], b.attr('mch_lr').outputs['Attribute'])))
    seg = b.vec('SCALE', dirn, scale=b.math('DIVIDE', ln, b.math('MAXIMUM', I['Segments'], 1.0)))
    acc = b.node('GeometryNodeAccumulateField', data_type='FLOAT_VECTOR', domain='POINT')
    b.feed(acc.inputs['Value'], seg)
    b.feed(acc.inputs['Group ID'], cidx)
    sp = b.node('GeometryNodeSetPosition')
    b.feed(sp.inputs['Geometry'], curves)
    b.feed(sp.inputs['Position'], b.vec('ADD', p0, acc.outputs['Trailing']))
    shaped = sp.outputs['Geometry']

    # clumps: each strand's points pulled toward the nearest guide strand's, more toward the tip
    sep = b.node('GeometryNodeSeparateGeometry', domain='POINT')
    b.feed(sep.inputs['Geometry'], pts)
    b.feed(sep.inputs['Selection'], b.attr('mch_g', 'BOOLEAN').outputs['Attribute'])
    near = b.node('GeometryNodeSampleNearest', domain='POINT')
    b.feed(near.inputs['Geometry'], sep.outputs['Selection'])
    b.feed(near.inputs['Sample Position'], p0)
    gid = b.node('GeometryNodeSampleIndex', data_type='INT', domain='POINT')
    b.feed(gid.inputs['Geometry'], sep.outputs['Selection'])
    b.feed(gid.inputs['Value'], b.attr('mch_i', 'INT').outputs['Attribute'])
    b.feed(gid.inputs['Index'], near.outputs['Index'])
    gpt = b.imath('ADD', b.imath('MULTIPLY', gid.outputs['Value'], b.imath('ADD', I['Segments'], 1)), kin)   # (integers: exact)
    gpos = b.node('GeometryNodeSampleIndex', data_type='FLOAT_VECTOR', domain='POINT')
    b.feed(gpos.inputs['Geometry'], shaped)
    b.feed(gpos.inputs['Value'], b.node('GeometryNodeInputPosition').outputs['Position'])
    b.feed(gpos.inputs['Index'], gpt)
    k = b.math('MULTIPLY', look.outputs['Y'], b.math('POWER', t, 1.3))            # (the area's Clump)
    sp2 = b.node('GeometryNodeSetPosition')
    b.feed(sp2.inputs['Geometry'], shaped)
    b.feed(sp2.inputs['Position'], b.mix_vec(k, b.node('GeometryNodeInputPosition').outputs['Position'],
                                             gpos.outputs['Value']))
    geo = sp2.outputs['Geometry']

    # 0.24.160 Tip Gather: each area's tips to one point - the mean of that area's tips (the end of its tilt); the
    # strand moved more toward its tip (its root stays), as much as the area's Tip Gather
    segs1 = b.imath('ADD', I['Segments'], 1)
    cindex = b.node('GeometryNodeInputIndex').outputs['Index']                # (on the curve domain: the curve)
    tip_c = b.node('GeometryNodeSampleIndex', data_type='FLOAT_VECTOR', domain='POINT')
    b.feed(tip_c.inputs['Geometry'], geo)
    b.feed(tip_c.inputs['Value'], b.node('GeometryNodeInputPosition').outputs['Position'])
    b.feed(tip_c.inputs['Index'], b.imath('ADD', b.imath('MULTIPLY', cindex, segs1), I['Segments']))
    part_c = b.attr('mch_fur_part', 'INT').outputs['Attribute']
    acc_t = b.node('GeometryNodeAccumulateField', data_type='FLOAT_VECTOR', domain='CURVE')
    b.feed(acc_t.inputs['Value'], tip_c.outputs['Value'])
    b.feed(acc_t.inputs['Group ID'], part_c)
    acc_n = b.node('GeometryNodeAccumulateField', data_type='FLOAT', domain='CURVE')
    acc_n.inputs[0].default_value = 1.0
    for inp in acc_n.inputs:
        if inp.name == 'Value' and inp.enabled:
            inp.default_value = 1.0
    b.feed(acc_n.inputs['Group ID'], part_c)
    mean_tip = b.vec('SCALE', acc_t.outputs['Total'], scale=b.math('DIVIDE', 1.0, b.math('MAXIMUM', acc_n.outputs['Total'], 1.0)))
    own_tip = b.node('GeometryNodeSampleIndex', data_type='FLOAT_VECTOR', domain='POINT')
    b.feed(own_tip.inputs['Geometry'], geo)
    b.feed(own_tip.inputs['Value'], b.node('GeometryNodeInputPosition').outputs['Position'])
    b.feed(own_tip.inputs['Index'], b.imath('ADD', b.imath('MULTIPLY', cidx, segs1), I['Segments']))
    ease = b.math('MULTIPLY', b.math('MULTIPLY', t, t), b.math('SUBTRACT', 3.0, b.math('MULTIPLY', t, 2.0)))
    sp3 = b.node('GeometryNodeSetPosition')
    b.feed(sp3.inputs['Geometry'], geo)
    b.feed(sp3.inputs['Offset'], b.vec('SCALE', b.vec('SUBTRACT', mean_tip, own_tip.outputs['Value']),
                                       scale=b.math('MULTIPLY', look.outputs['Z'], ease)))
    geo = sp3.outputs['Geometry']

    # thickness, colour, viewport share, material
    rad = b.node('GeometryNodeSetCurveRadius')
    b.feed(rad.inputs['Curve'], geo)
    b.feed(rad.inputs['Radius'], b.math('MULTIPLY', b.math(
        'ADD', b.math('MULTIPLY', I['Root Thickness'], b.math('SUBTRACT', 1.0, t)),
        b.math('MULTIPLY', I['Tip Thickness'], t)), 0.5))
    rc = b.attr('mch_rc', 'FLOAT_COLOR').outputs['Attribute']
    tipc = b.mix_col(I['Tip Blend'], rc, I['Tip Color'])
    geo = b.store(rad.outputs['Curve'], 'mch_fur_col', b.mix_col(t, rc, tipc), 'FLOAT_COLOR')
    dele = b.node('GeometryNodeDeleteGeometry', domain='CURVE')
    b.feed(dele.inputs['Geometry'], geo)
    hide = b.node('FunctionNodeBooleanMath', operation='AND')
    b.feed(hide.inputs[0], b.node('GeometryNodeIsViewport').outputs['Is Viewport'])
    b.feed(hide.inputs[1], b.math('GREATER_THAN', b.random(b.node('GeometryNodeInputIndex').outputs['Index'],
                                                            b.math('ADD', I['Seed'], 53.0)), I['Viewport %']))
    b.feed(dele.inputs['Selection'], hide.outputs[0])
    sm = b.node('GeometryNodeSetMaterial')
    b.feed(sm.inputs['Geometry'], dele.outputs['Geometry'])
    b.feed(sm.inputs['Material'], I['Material'])
    b.feed(go.inputs[0], sm.outputs['Geometry'])
    ng['mch_v'] = TREE_VERSION
    return ng


def fur_material():
    """``MCH Fur``: the strand colour from the ``mch_fur_col`` attribute - Principled Hair (Cycles), Principled
    (EEVEE)."""
    mat = bpy.data.materials.get(MAT)
    if mat is not None and mat.get('mch_v') == 1:
        return mat
    if mat is None:
        mat = bpy.data.materials.new(MAT)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    at = nt.nodes.new('ShaderNodeAttribute')
    at.attribute_type = 'GEOMETRY'
    at.attribute_name = 'mch_fur_col'
    at.location = (-500, 0)
    hair = nt.nodes.new('ShaderNodeBsdfHairPrincipled')
    hair.location = (-150, 150)
    try:
        hair.parametrization = 'COLOR'
    except (AttributeError, TypeError):
        pass
    nt.links.new(at.outputs['Color'], hair.inputs['Color'])
    for k, v in (('Roughness', 0.35), ('Radial Roughness', 0.4), ('Coat', 0.0)):
        if k in hair.inputs:
            hair.inputs[k].default_value = v
    pb = nt.nodes.new('ShaderNodeBsdfPrincipled')
    pb.location = (-150, -250)
    nt.links.new(at.outputs['Color'], pb.inputs['Base Color'])
    pb.inputs['Roughness'].default_value = 0.55
    oc = nt.nodes.new('ShaderNodeOutputMaterial')
    oc.target = 'CYCLES'
    oc.location = (200, 150)
    nt.links.new(hair.outputs[0], oc.inputs['Surface'])
    oe = nt.nodes.new('ShaderNodeOutputMaterial')
    oe.target = 'EEVEE'
    oe.location = (200, -250)
    nt.links.new(pb.outputs[0], oe.inputs['Surface'])
    mat.diffuse_color = (0.45, 0.33, 0.22, 1.0)
    mat['mch_v'] = 1
    return mat


# ---- the area on the body ------------------------------------------------------------------------------------------

def _screen(projector, P):
    """(n, 2) region pixels and (n,) in-front flags for world points ``P`` (n, 3)."""
    if hasattr(projector, 'rv3d') and hasattr(projector, 'region'):
        M = np.array(projector.rv3d.perspective_matrix, float)
        h = np.c_[P, np.ones(len(P))] @ M.T
        wv = h[:, 3]
        ok = wv > 1e-9
        ws = np.where(ok, wv, 1.0)
        xy = np.c_[(h[:, 0] / ws + 1.0) * 0.5 * projector.region.width,
                   (h[:, 1] / ws + 1.0) * 0.5 * projector.region.height]
        return xy, ok
    if hasattr(projector, 'rot') and hasattr(projector, 'ppu'):
        R = np.array(projector.rot, float)
        d = P - np.array(projector.center, float)
        xy = np.c_[projector.size[0] / 2 + d @ R[:, 0] * projector.ppu, projector.size[1] / 2 + d @ R[:, 1] * projector.ppu]
        return xy, np.ones(len(P), bool)
    out = [projector.to_screen(Vector(p)) for p in P]
    return (np.array([o if o is not None else (-1e9, -1e9) for o in out], float),
            np.array([o is not None for o in out], bool))


def _depth(projector, P):
    eye = np.array(projector.eye, float)
    if getattr(projector, 'is_perspective', False):
        return np.linalg.norm(P - eye, axis=1)
    return (P - eye) @ np.array(projector.view_dir, float)


def body_mirrors(body):
    """0.24.171 the body's live Mirror(s) as world reflections: [(4x4 matrix, cut)] - one for every combination of its
    planes; ``cut`` when every plane of it bisects (only the kept side of the body's own mesh shows)."""
    out = []
    if body is None or body.type != 'MESH':
        return out
    for m in body.modifiers:
        if m.type != 'MIRROR' or not m.show_viewport:
            continue
        axes = [i for i in range(3) if m.use_axis[i]]
        if not axes:
            continue
        Mo = np.array((m.mirror_object or body).matrix_world, float)
        try:
            Mi = np.linalg.inv(Mo)
        except np.linalg.LinAlgError:
            continue
        for k in range(1, 1 << len(axes)):
            sub = [a for j, a in enumerate(axes) if k >> j & 1]
            S = np.eye(4)
            for a in sub:
                S[a, a] = -1.0
            out.append((Mo @ S @ Mi, all(m.use_bisect_axis[a] for a in sub)))
    return out


def area_points(context, body, loops, projector, mirrors=None):
    """Indices of the body's points inside the drawn outline(s) that the view sees: facing it and not behind another
    part of the body (a depth grid of rays through the outline).  0.24.171 ``mirrors`` (``body_mirrors``): the points
    whose mirror image is inside too - an outline drawn on the side the body's live Mirror makes (no points of the
    body's own there, or cut away by its Bisect) paints the side it is made from (user: "왜 아직 머리카락 미러가 안 돼")."""
    from . import zones
    groups = cg.prepare_loops(loops)
    me = body.data
    n = len(me.vertices)
    if n == 0 or not groups:
        return np.zeros(0, int)
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get('co', co)
    no = np.empty(n * 3, np.float32)
    me.vertex_normals.foreach_get('vector', no)
    M = np.array(body.matrix_world, float)
    P0 = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    N0 = no.reshape(-1, 3) @ np.linalg.inv(M[:3, :3])
    N0 /= np.maximum(np.linalg.norm(N0, axis=1), 1e-12)[:, None]
    allpts = [q for outer, holes in groups for lp in [outer] + list(holes) for q in lp]
    x0, y0 = math.floor(min(q[0] for q in allpts)) - 1, math.floor(min(q[1] for q in allpts)) - 1
    x1, y1 = math.ceil(max(q[0] for q in allpts)) + 1, math.ceil(max(q[1] for q in allpts)) + 1
    W, H = max(1, int(x1 - x0)), max(1, int(y1 - y0))
    mask = np.zeros((H, W), np.float32)
    for outer, holes in groups:
        loops_ = [[(q[0] - x0, q[1] - y0) for q in lp] for lp in [outer] + list(holes)]
        mask = np.maximum(mask, zones.fill_polygon(loops_, W, H, ss=1))
    eye = np.array(projector.eye, float)
    # the depth grid: rays through the outline every ``step`` px (about 6000 at most)
    step = max(2.0, math.sqrt(W * H / 6000.0))
    gw, gh = int(W / step) + 1, int(H / step) + 1
    grid = np.full((gh, gw), np.inf)
    dg = context.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg)
    Mi = body.matrix_world.inverted()
    M3 = Mi.to_3x3()
    for gy in range(gh):
        for gx in range(gw):
            sx, sy = x0 + (gx + 0.5) * step, y0 + (gy + 0.5) * step      # (every cell: a point inside the outline
            o, d = projector.ray((sx, sy))                                  #  can sit in a cell centred outside it)
            ok, loc, _nrm, _i = ev.ray_cast(Mi @ Vector(o), (M3 @ Vector(d)).normalized())
            if ok:
                grid[gy, gx] = _depth(projector, np.array([tuple(body.matrix_world @ loc)]))[0]
    bb = np.ptp(P0, axis=0)
    tol = max(float(np.linalg.norm(bb)) * 0.02, 1e-6)

    def pick(P, Nn):
        xy, front = _screen(projector, P)
        ix, iy = np.floor(xy[:, 0] - x0).astype(int), np.floor(xy[:, 1] - y0).astype(int)
        inb = front & (ix >= 0) & (iy >= 0) & (ix < W) & (iy < H)
        inside = np.zeros(n, bool)
        inside[inb] = mask[iy[inb], ix[inb]] > 0.5
        if getattr(projector, 'is_perspective', False):
            tow = eye - P
        else:
            tow = np.broadcast_to(-np.array(projector.view_dir, float), P.shape)
        facing = np.einsum('ij,ij->i', Nn, tow) > 0.0
        cand = np.nonzero(inside & facing)[0]
        if not len(cand):
            return cand
        cx = np.clip(((xy[cand, 0] - x0) / step).astype(int), 0, gw - 1)
        cy = np.clip(((xy[cand, 1] - y0) / step).astype(int), 0, gh - 1)
        vd = _depth(projector, P[cand])
        gd = grid[cy, cx]
        seen = vd <= gd + tol
        # the grid says hidden, or its ray missed the body (a cell on the silhouette): a ray at the point itself
        # decides (a cell over a steep / grazing surface spans a lot of depth - only the point's own ray is sure)
        for j in np.nonzero(~seen | np.isinf(gd))[0]:
            seen[j] = False
            o, d = projector.ray((float(xy[cand[j], 0]), float(xy[cand[j], 1])))
            ok, loc, _nrm, _i = ev.ray_cast(Mi @ Vector(o), (M3 @ Vector(d)).normalized())
            if not ok or _depth(projector, np.array([tuple(body.matrix_world @ loc)]))[0] >= vd[j] - tol:
                seen[j] = True
        return cand[seen]

    direct = pick(P0, N0)
    if not mirrors:
        return direct
    out = set(int(i) for i in direct)
    loose = []
    for R, cut in mirrors:
        Pr = P0 @ R[:3, :3].T + R[:3, 3]
        Nr = N0 @ np.linalg.inv(R[:3, :3])
        Nr /= np.maximum(np.linalg.norm(Nr, axis=1), 1e-12)[:, None]
        mi = pick(Pr, Nr)
        if cut:                      # (the body's own points on the far side are cut away: its kept side paints)
            out |= set(int(i) for i in mi)
        else:                        # (not cut: both sides show - only when none of its own points were drawn on)
            loose.append(mi)
    if not len(direct):
        for mi in loose:
            out |= set(int(i) for i in mi)
    return np.array(sorted(out), int)


def flip_area(fur, axis=0):
    """0.24.171 Flip of a live fur (user: "머리는 월드 기준 x축으로 뒤집는 것도 되게"): its area moved across the world's
    plane through the origin - every point of the body with fur gives it (its area, tilt, curl ...) to the body's point
    nearest its mirror image, the side it was on cleared; the Flow Angle turned the other way, the Bend direction
    mirrored.  Returns True when it moved."""
    from mathutils.kdtree import KDTree
    body = fur.parent
    if body is None or body.type != 'MESH' or not fur.get(AREA_KEY):
        return False
    me = body.data
    n = len(me.vertices)
    a = me.attributes.get(fur[AREA_KEY])
    if a is None or n == 0:
        return False
    w = np.zeros(n, np.float32)
    a.data.foreach_get('value', w)
    src = np.nonzero(w > 0.0)[0]
    if not len(src):
        return False
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3).astype(float)
    M = np.array(body.matrix_world, float)
    R = np.eye(4)
    R[axis, axis] = -1.0
    L = np.linalg.inv(M) @ R @ M                      # (the world's mirror in the body's own space)
    img = co[src] @ L[:3, :3].T + L[:3, 3]
    kd = KDTree(n)
    for i, c in enumerate(co):
        kd.insert(c, i)
    kd.balance()
    ev = np.empty(len(me.edges) * 2, np.int32)
    me.edges.foreach_get('vertices', ev)
    ev = ev.reshape(-1, 2)
    near = float(np.median(np.linalg.norm(co[ev[:, 0]] - co[ev[:, 1]], axis=1))) * 1.5 if len(ev) else 1e-3
    dst = np.full(len(src), -1, np.int64)
    for k, q in enumerate(img):
        _c, j, dist = kd.find(q)
        if j is not None and dist <= near:
            dst[k] = j
    ok = dst >= 0
    if not ok.any():
        return False
    s_, d_ = src[ok], dst[ok]
    w2 = np.zeros(n, np.float32)
    w2[d_] = w[s_]
    a.data.foreach_set('value', w2)
    pa = me.attributes.get(fur.get(PART_KEY, ''))
    if pa is not None and pa.data_type == 'INT':
        ids = np.zeros(n, np.int32)
        pa.data.foreach_get('value', ids)
        ids2 = np.zeros(n, np.int32)
        ids2[d_] = ids[s_]
        pa.data.foreach_set('value', ids2)
    for key in (LIE_KEY, FLOW_KEY, LOOK_KEY):
        at = me.attributes.get(fur.get(key, '')) if fur.get(key) else None
        if at is None:
            continue
        if at.data_type == 'FLOAT':
            v = np.empty(n, np.float32)
            at.data.foreach_get('value', v)
            v[d_] = v[s_].copy()
            at.data.foreach_set('value', v)
        else:
            v = np.empty(n * 3, np.float32)
            at.data.foreach_get('vector', v)
            v = v.reshape(-1, 3)
            moved = v[s_].copy()
            if key == FLOW_KEY:
                moved[:, 1] *= -1.0                   # (the tilt turned the other way round the normal: mirrored)
            v[d_] = moved
            at.data.foreach_set('vector', v.ravel())
    pg = fur.mch_fur
    for part in pg.parts:                             # (each area's own Flow Angle: the mirrored way)
        _BUSY[0] = True
        try:
            part.flow = -part.flow
        finally:
            _BUSY[0] = False
    bd = list(pg.bend_dir)
    bd[axis] = -bd[axis]
    _BUSY[0] = True
    try:
        pg.bend_dir = bd
    finally:
        _BUSY[0] = False
    me.update()
    push(fur)
    fur.update_tag()
    return True


def paint_area(body, name, idx, value):
    """The body's area weight ``name`` set to ``value`` at the points ``idx``.  Returns how many are in the area."""
    me = body.data
    a = me.attributes.get(name)
    if a is None or a.domain != 'POINT' or a.data_type != 'FLOAT':
        if a is not None:
            me.attributes.remove(a)
        a = me.attributes.new(name, 'FLOAT', 'POINT')
    w = np.zeros(len(me.vertices), np.float32)
    a.data.foreach_get('value', w)
    w[idx] = value
    a.data.foreach_set('value', w)
    me.update()
    return int(np.sum(w > 0.5))


# ---- the fur object ------------------------------------------------------------------------------------------------

def is_fur(ob):
    return ob is not None and bool(ob.get(FUR_KEY))


def fur_body(ob):
    return ob.parent if is_fur(ob) else None


def active_fur(context):
    ob = getattr(context.view_layer.objects, 'active', None)
    try:
        return ob if is_fur(ob) and ob.select_get() else None
    except (RuntimeError, ReferenceError):
        return None


def color_attr_name(body):
    """The body's polypaint: its active colour attribute (or the first one), '' when it has none."""
    me = body.data
    try:
        ca = me.color_attributes.active_color
        if ca is not None:
            return ca.name
        if len(me.color_attributes):
            return me.color_attributes[0].name
    except AttributeError:
        pass
    return ''


def push(ob):
    """The fur object's settings into its modifier."""
    from . import geo_sculpt as gs
    mod = ob.modifiers.get(MOD)
    pg = getattr(ob, 'mch_fur', None)
    if mod is None or pg is None:
        return
    if mod.node_group is not None and mod.node_group.name.startswith(TREE) and \
            mod.node_group.get('mch_v') != TREE_VERSION:
        mod.node_group = fur_tree()                   # (0.24.171 an older fur: the new graph - Bend)
    for prop, name, kind, *_r in LIVE:
        v = getattr(pg, prop)
        try:
            gs.set_input(mod, name, tuple(v) if kind == 'COLOR' else v)
        except (KeyError, AttributeError, TypeError):
            pass
    body = ob.parent
    if body is not None:
        gs.set_input(mod, 'Color Attribute', color_attr_name(body))
        try:                                          # (kept after the graph is rebuilt: its inputs start over)
            gs.set_input(mod, 'Body', body)
            if ob.get(AREA_KEY):
                gs.set_input(mod, 'Area', ob[AREA_KEY])
            gs.set_input(mod, 'Material', fur_material())
            d = body.matrix_world.to_3x3().inverted_safe() @ Vector(pg.bend_dir)
            gs.set_input(mod, 'Bend Dir', tuple(d.normalized()) if d.length > 1e-9 else (1.0, 0.0, 0.0))
        except (KeyError, AttributeError, TypeError):
            pass
    if ob.get(PART_KEY) and not ob.get(LOOK_KEY):     # (a fur from 0.24.159: its areas' look name now)
        ob[LOOK_KEY] = ob[AREA_KEY].replace('mch_fur_', 'mch_flook_')
    for key, sock in ((LIE_KEY, 'Lie Attr'), (FLOW_KEY, 'Flow Attr'), (LOOK_KEY, 'Look Attr'), (PART_KEY, 'Part Attr')):
        if ob.get(key):
            try:
                gs.set_input(mod, sock, ob[key])
            except (KeyError, AttributeError, TypeError):
                pass


def new_fur(context, body, pg_from):
    """A fur object on ``body`` (its child, the body's space), its own area attribute; values from ``pg_from``."""
    from . import geo_sculpt as gs
    data = bpy.data.hair_curves.new('Fur')
    ob = bpy.data.objects.new('Fur', data)
    coll = bpy.data.collections.get(COLLECTION)
    if coll is None:
        coll = bpy.data.collections.new(COLLECTION)
    if coll.name not in context.scene.collection.children:
        context.scene.collection.children.link(coll)
    coll.objects.link(ob)
    ob.parent = body
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = Matrix.Identity(4)
    try:
        data.surface = body
    except (AttributeError, TypeError):
        pass
    ob[FUR_KEY] = 1
    ob[AREA_KEY] = 'mch_fur_' + uuid.uuid4().hex[:8]
    ob[PART_KEY] = ob[AREA_KEY].replace('mch_fur_', 'mch_fpart_')
    ob[LIE_KEY] = ob[AREA_KEY].replace('mch_fur_', 'mch_flie_')
    ob[FLOW_KEY] = ob[AREA_KEY].replace('mch_fur_', 'mch_fflow_')
    ob[LOOK_KEY] = ob[AREA_KEY].replace('mch_fur_', 'mch_flook_')
    mat = fur_material()
    data.materials.append(mat)
    mod = ob.modifiers.new(MOD, 'NODES')
    mod.node_group = fur_tree()
    gs.set_input(mod, 'Body', body)
    gs.set_input(mod, 'Area', ob[AREA_KEY])
    gs.set_input(mod, 'Lie Attr', ob[LIE_KEY])
    gs.set_input(mod, 'Flow Attr', ob[FLOW_KEY])
    gs.set_input(mod, 'Material', mat)
    _BUSY[0] = True
    try:
        for prop, *_r in LIVE:
            setattr(ob.mch_fur, prop, getattr(pg_from, prop))
    finally:
        _BUSY[0] = False
    push(ob)
    return ob


def strands(ob, context=None):
    """How many strands the fur has now (evaluated, all of them - not the viewport share)."""
    context = context or bpy.context
    dg = context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    try:
        return len(ev.data.curves)
    except AttributeError:
        return 0


def perform(context, loops, projector, erase=False):
    """The shared lasso's outline -> the fur area (see the module)."""
    from . import base_mesh
    screen_groups = cg.prepare_loops(loops)
    if not screen_groups:
        raise cg.CutError('Draw a bigger area')
    cur = active_fur(context)
    wm = context.window_manager
    if getattr(wm, NEW_KEY, False):
        cur = None
    _q, found = base_mesh.anchor_hit(context, projector, screen_groups[0][0])
    body = found[2] if found is not None else None
    if body is None and cur is not None:
        body = cur.parent
    if body is None or body.type != 'MESH':
        raise cg.CutError('Draw the area on a mesh (the body the fur grows on)')
    if cur is not None and cur.parent != body:
        cur = None                                    # (another body: a new fur there)
    if erase and cur is None:
        raise cg.CutError('Alt + draw takes area away from the selected fur - select a fur first')
    idx = area_points(context, body, loops, projector, body_mirrors(body))    # (0.24.171 its live Mirror's side too)
    if not len(idx) and not erase:
        raise cg.CutError('No surface of the body facing the view inside the outline')
    made = cur is None
    if made:
        cur = new_fur(context, body, context.scene.mch_fur)
    inside = paint_area(body, cur[AREA_KEY], idx, 0.0 if erase else 1.0)
    if not erase:
        part = current_part(cur)                      # (0.24.159 this area keeps the tilt it was drawn with -
        g = cur.mch_fur                               #  0.24.160 and its Curl, Clump, Tip Gather)
        if part is not None:
            add_part(cur, idx, part.lie, part.flow, part.curl, part.clump, part.gather)
        else:
            add_part(cur, idx, g.lie, g.flow, g.curl, g.clump, g.gather)
    push(cur)                                         # (the body's polypaint name, if it changed)
    try:
        setattr(wm, NEW_KEY, False)
    except (AttributeError, TypeError):
        pass
    for o in context.selected_objects:
        o.select_set(False)
    cur.select_set(True)
    context.view_layer.objects.active = cur
    cur.update_tag()
    context.view_layer.update()
    n = strands(cur, context)
    what = 'new fur' if made else ('area taken away' if erase else 'area added')
    tail = '' if erase else f' (Area {cur.mch_fur.part_index + 1}: its own Lie Down / Flow Angle)'
    return f'{cur.name} on {body.name}: {what} - {inside:,} points of the body in its area, {n:,} strands{tail}'


def apply_fur(context, ob):
    """The fur as real hair curves (the modifier applied): comb / cut them with Blender's hair tools."""
    with context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
        bpy.ops.object.modifier_apply(modifier=MOD)
    ob[FUR_KEY] = 0
    return ob


# ---- areas: each drawn area its own tilt (0.24.159) ------------------------------------------------------------------

def _point_attr(me, name, kind, fill):
    """The body's point attribute ``name`` (made, filled with ``fill``, when it is not there)."""
    a = me.attributes.get(name)
    if a is not None and (a.domain != 'POINT' or a.data_type != kind):
        me.attributes.remove(a)
        a = None
    if a is None:
        a = me.attributes.new(name, kind, 'POINT')
        n = len(me.vertices)
        if kind == 'INT':
            a.data.foreach_set('value', np.full(n, int(fill), np.int32))
        elif kind == 'FLOAT':
            a.data.foreach_set('value', np.full(n, float(fill), np.float32))
        else:
            a.data.foreach_set('vector', np.tile(np.array(fill, np.float32), n))
    return a


def part_ids(fur):
    """Which area (1, 2 ...; 0 none) each point of the body belongs to."""
    me = fur.parent.data
    a = me.attributes.get(fur.get(PART_KEY, ''))
    ids = np.zeros(len(me.vertices), np.int32)
    if a is not None and a.data_type == 'INT':
        a.data.foreach_get('value', ids)
    return ids


def part_sizes(fur):
    """Points of each area that still have fur (the area's weight), area number -> count."""
    ids = part_ids(fur)
    me = fur.parent.data
    w = np.zeros(len(me.vertices), np.float32)
    a = me.attributes.get(fur.get(AREA_KEY, ''))
    if a is not None:
        a.data.foreach_get('value', w)
    live = ids[(w > 0.0) & (ids > 0)]
    return {int(k): int(v) for k, v in zip(*np.unique(live, return_counts=True))} if len(live) else {}


def write_part(fur, k):
    """Area ``k`` (0-based)'s tilt into its points of the body."""
    me = fur.parent.data
    part = fur.mch_fur.parts[k]
    sel = part_ids(fur) == k + 1
    la = _point_attr(me, fur[LIE_KEY], 'FLOAT', part.lie)
    fa = _point_attr(me, fur[FLOW_KEY], 'FLOAT_VECTOR', (math.cos(part.flow), math.sin(part.flow), 0.0))
    lv = np.empty(len(me.vertices), np.float32)
    la.data.foreach_get('value', lv)
    lv[sel] = part.lie
    la.data.foreach_set('value', lv)
    fv = np.empty(len(me.vertices) * 3, np.float32)
    fa.data.foreach_get('vector', fv)
    fv = fv.reshape(-1, 3)
    fv[sel] = (math.cos(part.flow), math.sin(part.flow), 0.0)
    fa.data.foreach_set('vector', fv.ravel())
    if not fur.get(LOOK_KEY):
        fur[LOOK_KEY] = fur[AREA_KEY].replace('mch_fur_', 'mch_flook_')
    g = fur.mch_fur                                    # (0.24.160 Curl, Clump, Tip Gather; first time: the fur's own)
    ka = _point_attr(me, fur[LOOK_KEY], 'FLOAT_VECTOR', (g.curl, g.clump, 0.0))
    kv = np.empty(len(me.vertices) * 3, np.float32)
    ka.data.foreach_get('vector', kv)
    kv = kv.reshape(-1, 3)
    kv[sel] = (part.curl, part.clump, part.gather)
    ka.data.foreach_set('vector', kv.ravel())
    me.update()
    push(fur)
    fur.update_tag()


def add_part(fur, idx, lie, flow, curl=None, clump=None, gather=0.0):
    """A new area of the fur at the body's points ``idx`` with this tilt (and Curl, Clump, Tip Gather - 0.24.160; the
    last drawn wins where they overlap)."""
    if not fur.get(PART_KEY):                         # (a fur from before 0.24.159: its names now)
        fur[PART_KEY] = fur[AREA_KEY].replace('mch_fur_', 'mch_fpart_')
        fur[LIE_KEY] = fur[AREA_KEY].replace('mch_fur_', 'mch_flie_')
        fur[FLOW_KEY] = fur[AREA_KEY].replace('mch_fur_', 'mch_fflow_')
        from . import geo_sculpt as gs
        mod = fur.modifiers.get(MOD)
        if mod is not None:
            gs.set_input(mod, 'Lie Attr', fur[LIE_KEY])
            gs.set_input(mod, 'Flow Attr', fur[FLOW_KEY])
    me = fur.parent.data
    pa = _point_attr(me, fur[PART_KEY], 'INT', 0)
    _point_attr(me, fur[LIE_KEY], 'FLOAT', lie)                   # (first time: every point this tilt)
    _point_attr(me, fur[FLOW_KEY], 'FLOAT_VECTOR', (math.cos(flow), math.sin(flow), 0.0))
    pg = fur.mch_fur
    part = pg.parts.add()
    k = len(pg.parts)
    part.name = f'Area {k}'
    _BUSY[0] = True
    try:
        part.lie, part.flow = lie, flow
        part.curl = pg.curl if curl is None else curl
        part.clump = pg.clump if clump is None else clump
        part.gather = gather
        pg.part_index = k - 1
    finally:
        _BUSY[0] = False
    ids = part_ids(fur)
    ids[np.asarray(idx, int)] = k
    pa.data.foreach_set('value', ids)
    write_part(fur, k - 1)
    return part


def current_part(fur):
    pg = fur.mch_fur
    return pg.parts[pg.part_index] if 0 <= pg.part_index < len(pg.parts) else None


def _upd_part(self, context):
    """An area's Lie Down / Flow Angle changed: its points of the body, and the next area / fur start from it."""
    if _BUSY[0]:
        return
    fur = self.id_data
    if not isinstance(fur, bpy.types.Object) or not is_fur(fur) or fur.parent is None:
        return
    pg = fur.mch_fur
    k = next((i for i, p in enumerate(pg.parts) if p == self), None)
    if k is None:
        return
    write_part(fur, k)
    _BUSY[0] = True
    try:
        sc = getattr(context, 'scene', None)
        for holder in (pg, getattr(sc, 'mch_fur', None)):
            if holder is not None:
                holder.lie, holder.flow = self.lie, self.flow
                holder.curl, holder.clump, holder.gather = self.curl, self.clump, self.gather
    finally:
        _BUSY[0] = False


class MCH_PG_FurPart(bpy.types.PropertyGroup):
    lie: FloatProperty(name='Lie Down', default=math.radians(50), min=0.0, max=math.pi / 2, subtype='ANGLE',
                       update=_upd_part, description=DESCS['lie'])
    flow: FloatProperty(name='Flow Angle', default=0.0, min=-2 * math.pi, max=2 * math.pi, subtype='ANGLE',
                        update=_upd_part, description=DESCS['flow'])
    curl: FloatProperty(name='Curl', default=0.0, min=0.0, max=3.0, soft_max=2.0, update=_upd_part,
                        description=DESCS['curl'])
    clump: FloatProperty(name='Clump', default=0.25, min=0.0, max=1.0, update=_upd_part, description=DESCS['clump'])
    gather: FloatProperty(name='Tip Gather', default=0.0, min=0.0, max=1.0, update=_upd_part,
                          description=DESCS['gather'])


class MCH_OT_fur_part(bpy.types.Operator):
    """Pick this area of the selected fur: the Lie Down / Flow Angle sliders are its (change them: only this part)"""
    bl_idname = 'mch.fur_part'
    bl_label = 'Fur Area'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    index: IntProperty(default=0, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return active_fur(context) is not None

    def execute(self, context):
        pg = active_fur(context).mch_fur
        if not 0 <= self.index < len(pg.parts):
            return {'CANCELLED'}
        pg.part_index = self.index
        try:
            from . import side_panel
            side_panel.dirty()
        except (ImportError, AttributeError):
            pass
        return {'FINISHED'}


# ---- settings ------------------------------------------------------------------------------------------------------

_BUSY = [False]


def _upd_obj(self, context):
    if _BUSY[0]:
        return
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and is_fur(ob):
        push(ob)
        sc = getattr(context, 'scene', None)                # (the values go on to the next fur too)
        if sc is not None and hasattr(sc, 'mch_fur'):
            _BUSY[0] = True
            try:
                for prop, *_r in LIVE:
                    setattr(sc.mch_fur, prop, getattr(self, prop))
            finally:
                _BUSY[0] = False


SOFT = {'density': 100000.0, 'length': 0.3, 'gravity': 3.0, 'curl': 2.0, 'curl_turns': 10.0, 'frizz': 1.0,
        'clump_size': 60, 'root_thick': 0.005, 'tip_thick': 0.005, 'segments': 32, 'edge_soft': 20, 'part_soft': 20}
# (the slider's range: a drag across it a usable step - Length up to 0.3, not the 5 it can be typed to)


def _props(update):
    out = {}
    for prop, name, kind, default, lo, hi in LIVE:
        d = DESCS.get(prop, '')
        if kind == 'INT':
            kw = dict(name=name, default=default, min=lo, max=hi, update=update, description=d)
            if prop in SOFT:
                kw['soft_max'] = SOFT[prop]
            out[prop] = IntProperty(**kw)
        elif kind == 'BOOL':
            out[prop] = BoolProperty(name=name, default=default, update=update, description=d)
        elif kind == 'COLOR':
            out[prop] = FloatVectorProperty(name=name, default=default, size=4, subtype='COLOR', min=0.0, max=1.0,
                                            update=update, description=d)
        else:
            kw = dict(name=name, default=default, min=lo, max=hi, update=update, description=d)
            if prop in SOFT:
                kw['soft_max'] = SOFT[prop]
            if prop in {'length', 'root_thick', 'tip_thick'}:
                kw.update(unit='LENGTH', precision=5 if 'thick' in prop else 4)
            if prop in {'flow', 'lie', 'bend'}:
                kw.update(subtype='ANGLE')
            if prop in {'display'}:
                kw.update(subtype='FACTOR')
            out[prop] = FloatProperty(**kw)
    return out


class MCH_PG_Fur(bpy.types.PropertyGroup):
    __annotations__ = {**_props(_upd_obj),
                       'parts': bpy.props.CollectionProperty(type=MCH_PG_FurPart),
                       'part_index': IntProperty(default=0, min=0),
                       # 0.24.171 the bend direction (world; set from the view by the side buttons)
                       'bend_dir': FloatVectorProperty(name='Bend Direction', size=3, default=(1.0, 0.0, 0.0),
                                                       options={'HIDDEN'}, update=_upd_obj),
                       'bend_side': bpy.props.StringProperty(default='', options={'HIDDEN'})}


class MCH_OT_fur_new(bpy.types.Operator):
    """The next draw makes a new fur (with its own settings) instead of adding to the selected one"""
    bl_idname = 'mch.fur_new'
    bl_label = 'New Fur'
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        setattr(context.window_manager, NEW_KEY, True)
        self.report({'INFO'}, 'Fur: the next area you draw is a new fur')
        return {'FINISHED'}


class MCH_OT_fur_bend(bpy.types.Operator):
    """Bend the fur toward this side of the view you are looking through (the selected fur and the next)"""
    bl_idname = 'mch.fur_bend'
    bl_label = 'Fur Bend Toward'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    side: bpy.props.StringProperty(default='RIGHT')

    def execute(self, context):
        from . import creature_hair as ch
        ob = active_fur(context)
        d = None if self.side == 'OFF' else ch.view_direction(context, self.side)
        if self.side != 'OFF' and d is None:
            self.report({'WARNING'}, 'Bend: no 3D view to take the direction from')
            return {'CANCELLED'}
        for pg in [context.scene.mch_fur] + ([ob.mch_fur] if ob is not None else []):
            _BUSY[0] = True
            try:
                if self.side == 'OFF':
                    pg.bend = 0.0
                    pg.bend_side = ''
                else:
                    pg.bend_dir = tuple(d)
                    pg.bend_side = self.side
                    if pg.bend < 1e-6:
                        pg.bend = math.radians(60.0)      # (a first click: a bend you can see)
            finally:
                _BUSY[0] = False
        if ob is not None:
            push(ob)
            ob.update_tag()
        lab = dict(ch.BEND_SIDES).get(self.side, 'No Bend')
        self.report({'INFO'}, f'Fur bend: {lab}' + (f' - {ob.name}' if ob is not None else ' (the next fur)'))
        return {'FINISHED'}


class MCH_OT_fur_apply(bpy.types.Operator):
    """The selected fur as real hair curves (Blender's hair tools can comb / cut them); not live any more"""
    bl_idname = 'mch.fur_apply'
    bl_label = 'Apply Fur'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return active_fur(context) is not None

    def execute(self, context):
        ob = active_fur(context)
        n = strands(ob, context)
        try:
            apply_fur(context, ob)
        except RuntimeError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, f'{ob.name}: {n:,} real hair curves')
        return {'FINISHED'}


def draw(layout, context):
    """The window: the selected fur's values (live), else the next fur's."""
    ob = active_fur(context)
    pg = ob.mch_fur if ob is not None else context.scene.mch_fur
    col = layout.column(align=True)
    if ob is not None:
        col.label(text=f'{ob.name} on {ob.parent.name if ob.parent else "?"}: {strands(ob, context):,} strands (live)')
    else:
        col.label(text='The next fur')
    # 0.24.159 the tilt: each area drawn its own (pick an area, change it: only that part)
    col = layout.column(align=True)
    part = current_part(ob) if ob is not None else None
    if ob is not None and len(pg.parts):
        sizes = part_sizes(ob)
        col.label(text='Areas (each its own tilt, curl, clump, tip gather - pick one)')
        for i, p_ in enumerate(pg.parts):
            if sizes.get(i + 1, 0) == 0:
                continue                                  # (an area taken away all over)
            o = col.operator('mch.fur_part', text=f'{p_.name}   {math.degrees(p_.lie):.0f}\u00b0  dir '
                                                   f'{math.degrees(p_.flow):.0f}\u00b0', depress=(i == pg.part_index))
            o.index = i
    else:
        col.label(text='The next area')
    tilt = part if part is not None else pg
    for k_ in ('lie', 'flow', 'curl', 'clump', 'gather'):          # (0.24.160 Curl, Clump, Tip Gather the area's too)
        col.prop(tilt, k_)
    col.prop(pg, 'part_soft')
    for group, props in (('Strands', ('density', 'length', 'length_random', 'segments', 'display')),
                         ('Shape', ('volume', 'spread', 'gravity', 'curl_turns', 'frizz', 'clump_size')),
                         ('Bend', ()),
                         ('Thickness', ('root_thick', 'tip_thick')),
                         ('Area', ('edge_soft', 'seed'))):
        col = layout.column(align=True)
        col.label(text=group)
        if group == 'Bend':                            # 0.24.171 toward a side of the view you look through
            from . import creature_hair as ch
            col.label(text='(toward a side of the view you look through)')
            for keys in (ch.BEND_SIDES[:4], ch.BEND_SIDES[4:] + (('OFF', 'No Bend'),)):
                r = col.row(align=True)
                for key, label in keys:
                    on = (pg.bend > 0 and pg.bend_side == key) if key != 'OFF' else pg.bend <= 0
                    r.operator('mch.fur_bend', text=label, depress=on).side = key
            col.prop(pg, 'bend')
            if pg.bend > 0:
                col.prop(pg, 'bend_at')
                col.prop(pg, 'bend_soft')
        for p in props:
            col.prop(pg, p)
    col = layout.column(align=True)
    col.label(text='Color')
    col.prop(pg, 'use_polypaint')
    body = ob.parent if ob is not None else getattr(context.view_layer.objects, 'active', None)
    if pg.use_polypaint:
        name = color_attr_name(body) if body is not None and body.type == 'MESH' else ''
        col.label(text=f'Polypaint: {name}' if name else 'No polypaint on the body: Root Color')
    if not pg.use_polypaint or ob is None or not color_attr_name(ob.parent):
        col.prop(pg, 'root_color')
    col.prop(pg, 'tip_color')
    col.prop(pg, 'tip_blend')
    row = layout.row(align=True)
    row.operator('mch.fur_new', text='New Fur')
    if ob is not None:
        row.operator('mch.fur_apply', text='Apply')
    col = layout.column(align=True)
    for line in HELP:
        col.label(text=line)


HELP = ('Draw an area on a body: fur grows there',
        'Draw again: another area of the selected fur (its own tilt)',
        'Alt + draw: take area away;  New Fur: a second fur')

CLASSES = (MCH_PG_FurPart, MCH_PG_Fur, MCH_OT_fur_new, MCH_OT_fur_bend, MCH_OT_fur_apply, MCH_OT_fur_part)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_fur = bpy.props.PointerProperty(type=MCH_PG_Fur)
    bpy.types.Object.mch_fur = bpy.props.PointerProperty(type=MCH_PG_Fur)
    setattr(bpy.types.WindowManager, NEW_KEY, BoolProperty(default=False, options={'SKIP_SAVE'}))



def unregister():
    for attr, holder in (('mch_fur', bpy.types.Scene), ('mch_fur', bpy.types.Object), (NEW_KEY, bpy.types.WindowManager)):
        try:
            delattr(holder, attr)
        except AttributeError:
            pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
