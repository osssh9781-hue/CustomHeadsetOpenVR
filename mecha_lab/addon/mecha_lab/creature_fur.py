"""0.24.157 Fur (user: "털도 방법이 있니? 내가 지정한 영역에 털이 생겼으면 좋겠는데 기장, 곱슬, 끝이 모이는지, 중력, 두께랑 팁
두께" ... "색은 폴리페인트에서 가져오는 것도 넣어 주고 지오메트리 노드로 해 볼까 봐").

Draw an area on a body with the shared lasso (every shape, Line too): fur grows there - a live hair Curves object made
by Geometry Nodes (thousands of strands stay light; Cycles / EEVEE render them as hair).  The area is a weight on the
body's points (attribute ``mch_fur_<id>``), so the fur follows the body when it changes; Edge Soft blurs its border.

    draw            add to the selected fur's area (a fur of that body), else a new fur
    Alt + draw      take the area away from the selected fur
    New Fur         the next draw makes a new fur (its own settings)

Strands: Density (per square metre: more area, more strands), Length (+ Random), Lie Down (0 = standing out of the skin, 1 = flat along it) and
Flow Angle (which way they lie: 0 = down the body, turned about the skin), Gravity (bends them down toward the tip),
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
TREE_VERSION = 5
MOD = 'MCH Fur'
MAT = 'MCH Fur'
AREA_KEY = 'mch_fur_area'          # on a fur object: the body attribute that holds its area
FUR_KEY = 'mch_fur'                # on a fur object (1)
NEW_KEY = 'mch_fur_new'            # window manager flag: the next draw makes a new fur
COLLECTION = 'Creature Fur'

# (prop, socket name, socket type, default, min, max) - the values each fur keeps (its modifier's inputs)
LIVE = (
    ('density', 'Density', 'FLOAT', 20000.0, 1.0, 2000000.0),
    ('length', 'Length', 'FLOAT', 0.05, 0.0005, 5.0),
    ('length_random', 'Length Random', 'FLOAT', 0.35, 0.0, 0.95),
    ('lie', 'Lie Down', 'FLOAT', 0.55, 0.0, 1.0),
    ('flow', 'Flow Angle', 'FLOAT', 0.0, -2 * math.pi, 2 * math.pi),
    ('gravity', 'Gravity', 'FLOAT', 0.4, 0.0, 5.0),
    ('curl', 'Curl', 'FLOAT', 0.0, 0.0, 3.0),
    ('curl_turns', 'Curl Turns', 'FLOAT', 2.0, 0.0, 20.0),
    ('frizz', 'Frizz', 'FLOAT', 0.15, 0.0, 2.0),
    ('clump', 'Clump', 'FLOAT', 0.25, 0.0, 1.0),
    ('clump_size', 'Clump Size', 'INT', 12, 1, 500),
    ('root_thick', 'Root Thickness', 'FLOAT', 0.0008, 0.00001, 0.05),
    ('tip_thick', 'Tip Thickness', 'FLOAT', 0.00012, 0.0, 0.05),
    ('segments', 'Segments', 'INT', 8, 2, 64),
    ('edge_soft', 'Edge Soft', 'INT', 3, 0, 60),
    ('use_polypaint', 'Use Polypaint', 'BOOL', True, None, None),
    ('root_color', 'Root Color', 'COLOR', (0.32, 0.22, 0.14, 1.0), None, None),
    ('tip_color', 'Tip Color', 'COLOR', (0.75, 0.62, 0.45, 1.0), None, None),
    ('tip_blend', 'Tip Blend', 'FLOAT', 0.25, 0.0, 1.0),
    ('display', 'Viewport %', 'FLOAT', 1.0, 0.0, 1.0),
    ('seed', 'Seed', 'INT', 0, 0, 100000),
)
LIVE_NAMES = {p: s for p, s, *_r in LIVE}
DESCS = {
    'density': 'Strands per square metre of the area (20000: 2 a square centimetre) - more area, more strands',
    'length': 'A strand\'s length',
    'length_random': 'Some strands shorter (0.35: down to 65 %)',
    'lie': 'How flat the fur lies: 0 standing straight out of the skin, 1 flat along it',
    'flow': 'Which way the fur lies: 0 down the body, turned about the skin by this angle',
    'gravity': 'Bends the strands down toward their tips',
    'curl': 'Curls round each strand (how wide)',
    'curl_turns': 'How many turns along a strand',
    'frizz': 'A small random wobble along each strand',
    'clump': 'Tips gathered into tufts (1: the tips meet)',
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
          'GEOMETRY': 'NodeSocketGeometry'}[kind]
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
    _socket(ng, 'Color Attribute', 'STRING')
    _socket(ng, 'Material', 'MATERIAL')
    for _p, name, kind, default, lo, hi in LIVE:
        _socket(ng, name, kind, default, lo, hi)
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
    body = b.store(oi.outputs['Geometry'], 'mch_fur_w', b.math('MULTIPLY', blur.outputs['Value'], w0))  # (soft inside:
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
    ang = I['Flow Angle']
    f = b.vec('ADD', b.vec('SCALE', f, scale=b.math('COSINE', ang)),
              b.vec('SCALE', b.vec('CROSS_PRODUCT', n_, f), scale=b.math('SINE', ang)))
    lie = b.math('MULTIPLY', I['Lie Down'], math.pi / 2)
    d0 = b.vec('NORMALIZE', b.vec('ADD', b.vec('SCALE', n_, scale=b.math('COSINE', lie)),
                                  b.vec('SCALE', f, scale=b.math('SINE', lie))))
    d = b.vec('ADD', d0, b.vec('SCALE', down, scale=b.math('MULTIPLY', I['Gravity'], t)))
    wv = b.vec('NORMALIZE', b.vec('CROSS_PRODUCT', n_, f))
    vv = b.vec('CROSS_PRODUCT', d0, wv)
    ph = b.math('ADD', b.math('MULTIPLY', b.math('MULTIPLY', I['Curl Turns'], t), 2 * math.pi),
                b.math('MULTIPLY', b.attr('mch_ph').outputs['Attribute'], 2 * math.pi))
    curl = b.vec('SCALE', b.vec('ADD', b.vec('SCALE', wv, scale=b.math('COSINE', ph)),
                                b.vec('SCALE', vv, scale=b.math('SINE', ph))), scale=I['Curl'])
    noise = b.node('ShaderNodeTexNoise', noise_dimensions='4D')
    p0 = b.attr('mch_p0', 'FLOAT_VECTOR').outputs['Attribute']
    b.feed(noise.inputs['Vector'], b.vec('SCALE', p0, scale=40.0))
    b.feed(noise.inputs['W'], b.math('MULTIPLY', t, 9.0))                   # (a few wobbles along a strand)
    noise.inputs['Scale'].default_value = 1.0
    fr = b.vec('SCALE', b.vec('SUBTRACT', noise.outputs['Color'], (0.5, 0.5, 0.5)),
               scale=b.math('MULTIPLY', b.math('MULTIPLY', I['Frizz'], 5.0), b.math('ADD', b.math('MULTIPLY', t, 0.7), 0.3)))
    dirn = b.vec('NORMALIZE', b.vec('ADD', b.vec('ADD', d, curl), fr))
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
    k = b.math('MULTIPLY', I['Clump'], b.math('POWER', t, 1.3))
    sp2 = b.node('GeometryNodeSetPosition')
    b.feed(sp2.inputs['Geometry'], shaped)
    b.feed(sp2.inputs['Position'], b.mix_vec(k, b.node('GeometryNodeInputPosition').outputs['Position'],
                                             gpos.outputs['Value']))
    geo = sp2.outputs['Geometry']

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


def area_points(context, body, loops, projector):
    """Indices of the body's points inside the drawn outline(s) that the view sees: facing it and not behind another
    part of the body (a depth grid of rays through the outline)."""
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
    P = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    Nn = no.reshape(-1, 3) @ np.linalg.inv(M[:3, :3])
    Nn /= np.maximum(np.linalg.norm(Nn, axis=1), 1e-12)[:, None]
    xy, front = _screen(projector, P)
    allpts = [q for outer, holes in groups for lp in [outer] + list(holes) for q in lp]
    x0, y0 = math.floor(min(q[0] for q in allpts)) - 1, math.floor(min(q[1] for q in allpts)) - 1
    x1, y1 = math.ceil(max(q[0] for q in allpts)) + 1, math.ceil(max(q[1] for q in allpts)) + 1
    W, H = max(1, int(x1 - x0)), max(1, int(y1 - y0))
    mask = np.zeros((H, W), np.float32)
    for outer, holes in groups:
        loops_ = [[(q[0] - x0, q[1] - y0) for q in lp] for lp in [outer] + list(holes)]
        mask = np.maximum(mask, zones.fill_polygon(loops_, W, H, ss=1))
    ix, iy = np.floor(xy[:, 0] - x0).astype(int), np.floor(xy[:, 1] - y0).astype(int)
    inb = front & (ix >= 0) & (iy >= 0) & (ix < W) & (iy < H)
    inside = np.zeros(n, bool)
    inside[inb] = mask[iy[inb], ix[inb]] > 0.5
    eye = np.array(projector.eye, float)
    if getattr(projector, 'is_perspective', False):
        tow = eye - P
    else:
        tow = np.broadcast_to(-np.array(projector.view_dir, float), P.shape)
    facing = np.einsum('ij,ij->i', Nn, tow) > 0.0
    cand = np.nonzero(inside & facing)[0]
    if not len(cand):
        return cand
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
    cx = np.clip(((xy[cand, 0] - x0) / step).astype(int), 0, gw - 1)
    cy = np.clip(((xy[cand, 1] - y0) / step).astype(int), 0, gh - 1)
    bb = np.ptp(P, axis=0)
    tol = max(float(np.linalg.norm(bb)) * 0.02, 1e-6)
    vd = _depth(projector, P[cand])
    gd = grid[cy, cx]
    seen = vd <= gd + tol
    # the grid says hidden, or its ray missed the body (a cell on the silhouette): a ray at the point itself decides
    # (a cell over a steep / grazing surface spans a lot of depth - only the point's own ray is sure)
    for j in np.nonzero(~seen | np.isinf(gd))[0]:
        seen[j] = False
        o, d = projector.ray((float(xy[cand[j], 0]), float(xy[cand[j], 1])))
        ok, loc, _nrm, _i = ev.ray_cast(Mi @ Vector(o), (M3 @ Vector(d)).normalized())
        if not ok or _depth(projector, np.array([tuple(body.matrix_world @ loc)]))[0] >= vd[j] - tol:
            seen[j] = True
    return cand[seen]


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
    for prop, name, kind, *_r in LIVE:
        v = getattr(pg, prop)
        gs.set_input(mod, name, tuple(v) if kind == 'COLOR' else v)
    body = ob.parent
    if body is not None:
        gs.set_input(mod, 'Color Attribute', color_attr_name(body))


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
    mat = fur_material()
    data.materials.append(mat)
    mod = ob.modifiers.new(MOD, 'NODES')
    mod.node_group = fur_tree()
    gs.set_input(mod, 'Body', body)
    gs.set_input(mod, 'Area', ob[AREA_KEY])
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
    idx = area_points(context, body, loops, projector)
    if not len(idx) and not erase:
        raise cg.CutError('No surface of the body facing the view inside the outline')
    made = cur is None
    if made:
        cur = new_fur(context, body, context.scene.mch_fur)
    inside = paint_area(body, cur[AREA_KEY], idx, 0.0 if erase else 1.0)
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
    return f'{cur.name} on {body.name}: {what} - {inside:,} points of the body in its area, {n:,} strands'


def apply_fur(context, ob):
    """The fur as real hair curves (the modifier applied): comb / cut them with Blender's hair tools."""
    with context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
        bpy.ops.object.modifier_apply(modifier=MOD)
    ob[FUR_KEY] = 0
    return ob


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
        'clump_size': 60, 'root_thick': 0.005, 'tip_thick': 0.005, 'segments': 32, 'edge_soft': 20}
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
            if prop == 'flow':
                kw.update(subtype='ANGLE')
            if prop in {'display'}:
                kw.update(subtype='FACTOR')
            out[prop] = FloatProperty(**kw)
    return out


class MCH_PG_Fur(bpy.types.PropertyGroup):
    __annotations__ = _props(_upd_obj)


class MCH_OT_fur_new(bpy.types.Operator):
    """The next draw makes a new fur (with its own settings) instead of adding to the selected one"""
    bl_idname = 'mch.fur_new'
    bl_label = 'New Fur'
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        setattr(context.window_manager, NEW_KEY, True)
        self.report({'INFO'}, 'Fur: the next area you draw is a new fur')
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
    for group, props in (('Strands', ('density', 'length', 'length_random', 'segments', 'display')),
                         ('Shape', ('lie', 'flow', 'gravity', 'curl', 'curl_turns', 'frizz', 'clump', 'clump_size')),
                         ('Thickness', ('root_thick', 'tip_thick')),
                         ('Area', ('edge_soft', 'seed'))):
        col = layout.column(align=True)
        col.label(text=group)
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
        'Draw again: more area on the selected fur',
        'Alt + draw: take area away;  New Fur: a second fur')

CLASSES = (MCH_PG_Fur, MCH_OT_fur_new, MCH_OT_fur_apply)


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
