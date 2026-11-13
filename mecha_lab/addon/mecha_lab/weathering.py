"""0.24.158 Weathering (user: "웨더링 메뉴도 새로 만들자 - 흙이나 먼지, 나뭇잎, 눈 ... 내가 만든 메쉬를 클릭하면 그걸 그런 흙, 먼지,
나뭇잎, 눈 같은 형태로 바꿔 주는 거야, 그 영역을 - 베이스 메쉬, 크리쳐 메쉬, 플레이트들, 서페이스 드로우로 만든 것에").

Four tools in the Weathering group: Dirt, Dust, Leaves, Snow.  Click a mesh (a shape made with Base Mesh, Creature
Base Mesh, a plate, Surface Draw ... - or any mesh) and it becomes that: a live Geometry Nodes modifier ``MCH Weather``
at the end of its stack, so the shape stays editable under it (a live Base Mesh's sliders still work) and its values
change any time.  Alt + click: back to the shape (the modifier removed).  Apply (the window): real geometry.

    Dirt     the shape lumpy (noise, as large as the shape), clods and crumbs scattered over it, brown
    Dust     a thin soft layer: the shape smoothed and puffed a little, a fine grain, dusty grey
    Leaves   leaves scattered over the shape, piled, turned, tilted, green to autumn colours; the shape under them
             as dark soil (Show Base) or hidden
    Snow     the shape smoothed, puffed (more on its top), soft lumps, snow white with blue shadows

Sizes are shares of the shape's own size (its bounding box diagonal) - the same values suit a pebble or a hill;
Leaves are in real sizes (Leaf Size, Density per square metre).  The colours are point / instance attributes
(``mch_w_col``, ``mch_leaf_col``) read by the shared materials ``MCH Dirt`` / ``MCH Dust`` / ``MCH Snow`` /
``MCH Leaf`` / ``MCH Soil``.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, PointerProperty
from mathutils import Vector

from .creature_fur import _B, _socket

MOD = 'MCH Weather'
KEY = 'mch_weather'                 # on a weathered object: its kind
TREE_VERSION = 4
LEAF_COLL = 'MCH Leaf Shapes'
KINDS = ('DIRT', 'DUST', 'LEAVES', 'SNOW')
TOOL_OF = {'DIRT': 'WDIRT', 'DUST': 'WDUST', 'LEAVES': 'WLEAF', 'SNOW': 'WSNOW'}
KIND_OF = {v: k for k, v in TOOL_OF.items()}
LABEL = {'DIRT': 'Dirt', 'DUST': 'Dust', 'LEAVES': 'Leaves', 'SNOW': 'Snow'}

# (prop, socket, kind, default, min, max, soft_max, description) per weathering
SPEC = {
    'DIRT': (
        ('detail', 'Detail', 'INT', 1, 0, 5, None, 'Subdivisions of the shape (rebuilt evenly first) before it is made lumpy'),
        ('lumps', 'Lumps', 'FLOAT', 0.35, 0.0, 3.0, 1.0, 'How lumpy (a share of the shape\'s size)'),
        ('lump_scale', 'Lump Scale', 'FLOAT', 5.0, 0.1, 100.0, 20.0, 'How many lumps across the shape'),
        ('crumbs', 'Crumbs', 'FLOAT', 1.2, 0.0, 10.0, 3.0, 'Clods and crumbs scattered over it'),
        ('crumb_size', 'Crumb Size', 'FLOAT', 0.012, 0.001, 0.5, 0.1, 'A crumb\'s size (a share of the shape\'s size)'),
        ('color_a', 'Color A', 'COLOR', (0.075, 0.05, 0.032, 1.0), None, None, None, 'The dark soil'),
        ('color_b', 'Color B', 'COLOR', (0.2, 0.135, 0.08, 1.0), None, None, None, 'The light soil'),
        ('seed', 'Seed', 'INT', 0, 0, 100000, None, 'Another random mix'),
    ),
    'DUST': (
        ('detail', 'Detail', 'INT', 1, 0, 5, None, 'Subdivisions (smoothed)'),
        ('thickness', 'Thickness', 'FLOAT', 0.3, 0.0, 3.0, 1.0, 'How far the layer puffs out (a share of the shape\'s size)'),
        ('softness', 'Softness', 'INT', 4, 0, 60, 20, 'The shape smoothed out (more: softer)'),
        ('grain', 'Grain', 'FLOAT', 0.3, 0.0, 3.0, 1.0, 'A fine grain over it'),
        ('color_a', 'Color A', 'COLOR', (0.36, 0.33, 0.28, 1.0), None, None, None, 'The darker dust'),
        ('color_b', 'Color B', 'COLOR', (0.58, 0.54, 0.47, 1.0), None, None, None, 'The lighter dust'),
        ('seed', 'Seed', 'INT', 0, 0, 100000, None, 'Another random mix'),
    ),
    'LEAVES': (
        ('density', 'Density', 'FLOAT', 400.0, 1.0, 50000.0, 3000.0, 'Leaves per square metre of the shape'),
        ('leaf_size', 'Leaf Size', 'FLOAT', 0.06, 0.001, 3.0, 0.3, 'A leaf\'s length'),
        ('size_random', 'Size Random', 'FLOAT', 0.4, 0.0, 0.95, None, 'Some leaves smaller'),
        ('pile', 'Pile', 'FLOAT', 0.6, 0.0, 10.0, 3.0, 'How high they pile (x a leaf\'s size)'),
        ('tilt', 'Tilt', 'FLOAT', 0.45, 0.0, 1.5708, None, 'Leaves tilted off the surface at random'),
        ('autumn', 'Autumn', 'FLOAT', 0.65, 0.0, 1.0, None, '0 green, 1 all autumn colours (yellow, orange, brown)'),
        ('show_base', 'Show Base', 'BOOL', True, None, None, None, 'The shape under the leaves as dark soil (off: hidden)'),
        ('base_color', 'Base Color', 'COLOR', (0.05, 0.036, 0.024, 1.0), None, None, None, 'The soil under the leaves'),
        ('seed', 'Seed', 'INT', 0, 0, 100000, None, 'Another random mix'),
    ),
    'SNOW': (
        ('detail', 'Detail', 'INT', 1, 0, 5, None, 'Subdivisions (smoothed; the shape rebuilt evenly first)'),
        ('puff', 'Puff', 'FLOAT', 0.4, 0.0, 3.0, 1.5, 'How far the snow puffs out - more on its top (a share of the size)'),
        ('smooth', 'Smooth', 'INT', 6, 0, 80, 30, 'The shape rounded off (more: softer, like settled snow)'),
        ('lumps', 'Lumps', 'FLOAT', 0.25, 0.0, 3.0, 1.0, 'Soft lumps (a share of the shape\'s size)'),
        ('lump_scale', 'Lump Scale', 'FLOAT', 3.0, 0.1, 100.0, 20.0, 'How many lumps across the shape'),
        ('color_a', 'Color A', 'COLOR', (0.93, 0.95, 0.98, 1.0), None, None, None, 'The snow'),
        ('color_b', 'Color B', 'COLOR', (0.72, 0.8, 0.92, 1.0), None, None, None, 'Its blue shade'),
        ('seed', 'Seed', 'INT', 0, 0, 100000, None, 'Another random mix'),
    ),
}
MATS = {'DIRT': 'MCH Dirt', 'DUST': 'MCH Dust', 'LEAVES': 'MCH Soil', 'SNOW': 'MCH Snow'}


# ---- node groups ---------------------------------------------------------------------------------------------------

def _inputs(ng, kind):
    _socket(ng, 'Geometry', 'GEOMETRY')
    for prop, name, typ, default, lo, hi, _soft, _d in SPEC[kind]:
        _socket(ng, name, typ, default, lo, hi)
    _socket(ng, 'Material', 'MATERIAL')
    if kind == 'LEAVES':
        ng.interface.new_socket('Leaves', in_out='INPUT', socket_type='NodeSocketCollection')
        _socket(ng, 'Realize', 'BOOL', False)          # (Apply: the leaves made real first)
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')


def _diag(b, geo):
    bb = b.node('GeometryNodeBoundBox')
    b.feed(bb.inputs['Geometry'], geo)
    return b.math('MAXIMUM', b.vec('DISTANCE', bb.outputs['Max'], bb.outputs['Min']), 1e-6)


def _even(b, geo, size):
    """A closed shape rebuilt evenly first (a voxel remesh, the voxels from its thinnest side): a flat Base Mesh's top is
    a fan of long triangles that puffs into ridges and a ruffled rim otherwise.  An open shape (a band, a sheet) is
    kept as it is (a volume needs a closed one)."""
    bb = b.node('GeometryNodeBoundBox')
    b.feed(bb.inputs['Geometry'], geo)
    ext = b.node('ShaderNodeSeparateXYZ')
    b.feed(ext.inputs[0], b.vec('SUBTRACT', bb.outputs['Max'], bb.outputs['Min']))
    thin = b.math('MINIMUM', b.math('MINIMUM', ext.outputs['X'], ext.outputs['Y']), ext.outputs['Z'])
    vox = b.math('MAXIMUM', b.math('DIVIDE', size, 160.0), b.math('MINIMUM', b.math('DIVIDE', size, 90.0),
                                                                 b.math('DIVIDE', thin, 3.0)))
    m2v = b.node('GeometryNodeMeshToVolume')
    b.feed(m2v.inputs['Mesh'], geo)
    try:
        m2v.inputs['Resolution Mode'].default_value = 'Size'
    except (KeyError, TypeError):
        pass
    b.feed(m2v.inputs['Voxel Size'], vox)
    b.feed(m2v.inputs['Interior Band Width'], b.math('MULTIPLY', vox, 2.0))
    v2m = b.node('GeometryNodeVolumeToMesh')
    b.feed(v2m.inputs['Volume'], m2v.outputs['Volume'])
    nb = b.node('GeometryNodeInputMeshEdgeNeighbors')
    st = b.node('GeometryNodeAttributeStatistic', data_type='FLOAT', domain='EDGE')
    b.feed(st.inputs['Geometry'], geo)
    b.feed(st.inputs['Attribute'], nb.outputs['Face Count'])
    closed = b.node('FunctionNodeBooleanMath', operation='AND')
    b.feed(closed.inputs[0], b.math('GREATER_THAN', st.outputs['Min'], 1.5))     # (every edge between two faces)
    b.feed(closed.inputs[1], b.math('LESS_THAN', st.outputs['Max'], 2.5))
    sw = b.node('GeometryNodeSwitch', input_type='GEOMETRY')
    b.feed(sw.inputs['Switch'], closed.outputs[0])
    b.feed(sw.inputs['False'], geo)
    b.feed(sw.inputs['True'], v2m.outputs['Mesh'])
    return sw.outputs['Output']


def _noise(b, scale_by, scale, seed, detail=4.0, rough=0.55):
    """A noise Factor field over the object, ``scale`` across ``scale_by`` (the shape's size), offset by the seed."""
    n = b.node('ShaderNodeTexNoise', noise_dimensions='4D')
    pos = b.node('GeometryNodeInputPosition').outputs['Position']
    b.feed(n.inputs['Vector'], b.vec('SCALE', pos, scale=b.math('DIVIDE', scale, scale_by)))
    b.feed(n.inputs['W'], b.math('MULTIPLY', seed, 1.618))
    n.inputs['Scale'].default_value = 1.0
    n.inputs['Detail'].default_value = detail
    n.inputs['Roughness'].default_value = rough
    return n.outputs['Factor']


def _color(b, geo, f, a, c):
    return b.store(geo, 'mch_w_col', b.mix_col(f, a, c), 'FLOAT_COLOR')


def _finish(b, geo, mat, smooth=True):
    if smooth:
        ss = b.node('GeometryNodeSetShadeSmooth')
        b.feed(ss.inputs['Mesh'], geo)
        geo = ss.outputs['Mesh']
    sm = b.node('GeometryNodeSetMaterial')
    b.feed(sm.inputs['Geometry'], geo)
    b.feed(sm.inputs['Material'], mat)
    return sm.outputs['Geometry']


def _dirt(b, I):
    geo = I['Geometry']
    size = _diag(b, geo)
    sub = b.node('GeometryNodeSubdivideMesh')
    b.feed(sub.inputs['Mesh'], _even(b, geo, size))
    b.feed(sub.inputs['Level'], I['Detail'])
    nrm = b.node('GeometryNodeInputNormal').outputs['Normal']
    big = _noise(b, size, I['Lump Scale'], I['Seed'], 5.0, 0.6)
    fine = _noise(b, size, b.math('MULTIPLY', I['Lump Scale'], 6.0), b.math('ADD', I['Seed'], 9.0), 3.0, 0.5)
    amt = b.math('MULTIPLY', b.math('MULTIPLY', I['Lumps'], 0.06), size)
    off = b.math('MULTIPLY', b.math('ADD', b.math('SUBTRACT', big, 0.5), b.math('MULTIPLY', b.math('SUBTRACT', fine, 0.5), 0.35)),
                 b.math('MULTIPLY', amt, 2.0))
    sp = b.node('GeometryNodeSetPosition')
    b.feed(sp.inputs['Geometry'], sub.outputs['Mesh'])
    b.feed(sp.inputs['Offset'], b.vec('SCALE', nrm, scale=off))
    ground = _color(b, sp.outputs['Geometry'], fine, I['Color A'], I['Color B'])
    # clods and crumbs: flattened lumps on the surface (not underneath)
    dist = b.node('GeometryNodeDistributePointsOnFaces', distribute_method='RANDOM')
    b.feed(dist.inputs['Mesh'], ground)
    up = b.node('ShaderNodeSeparateXYZ')
    b.feed(up.inputs[0], b.node('GeometryNodeInputNormal').outputs['Normal'])
    b.feed(dist.inputs['Selection'], b.math('GREATER_THAN', up.outputs['Z'], -0.2))
    b.feed(dist.inputs['Density'], b.math('DIVIDE', b.math('MULTIPLY', I['Crumbs'], 1500.0), b.math('MULTIPLY', size, size)))
    b.feed(dist.inputs['Seed'], I['Seed'])
    ico = b.node('GeometryNodeMeshIcoSphere')
    ico.inputs['Radius'].default_value = 1.0
    ico.inputs['Subdivisions'].default_value = 1
    idx = b.node('GeometryNodeInputIndex').outputs['Index']
    r = b.random(idx, b.math('ADD', I['Seed'], 3.0), 0.35, 1.25)
    rad = b.math('MULTIPLY', b.math('MULTIPLY', I['Crumb Size'], size), r)
    sc = b.node('ShaderNodeCombineXYZ')
    b.feed(sc.inputs[0], rad)
    b.feed(sc.inputs[1], b.math('MULTIPLY', rad, b.random(idx, b.math('ADD', I['Seed'], 4.0), 0.6, 1.1)))
    b.feed(sc.inputs[2], b.math('MULTIPLY', rad, 0.55))
    rot = b.node('FunctionNodeAlignRotationToVector', axis='Z')
    b.feed(rot.inputs['Vector'], dist.outputs['Normal'])
    iop = b.node('GeometryNodeInstanceOnPoints')
    b.feed(iop.inputs['Points'], dist.outputs['Points'])
    b.feed(iop.inputs['Instance'], ico.outputs['Mesh'])
    b.feed(iop.inputs['Rotation'], rot.outputs['Rotation'])
    b.feed(iop.inputs['Scale'], sc.outputs['Vector'])
    crumbs = b.store(iop.outputs['Instances'], 'mch_w_col',
                     b.mix_col(b.random(b.node('GeometryNodeInputIndex').outputs['Index'], b.math('ADD', I['Seed'], 5.0)),
                               I['Color A'], I['Color B']), 'FLOAT_COLOR', 'INSTANCE')
    real = b.node('GeometryNodeRealizeInstances')
    b.feed(real.inputs['Geometry'], crumbs)
    join = b.node('GeometryNodeJoinGeometry')
    b.feed(join.inputs[0], real.outputs['Geometry'])
    b.feed(join.inputs[0], ground)
    return _finish(b, join.outputs['Geometry'], I['Material'])


def _dust(b, I):
    geo = I['Geometry']
    size = _diag(b, geo)
    sub = b.node('GeometryNodeSubdivisionSurface')
    b.feed(sub.inputs['Mesh'], _even(b, geo, size))
    b.feed(sub.inputs['Level'], I['Detail'])
    blur = b.node('GeometryNodeBlurAttribute', data_type='FLOAT_VECTOR')
    b.feed(blur.inputs['Value'], b.node('GeometryNodeInputPosition').outputs['Position'])
    b.feed(blur.inputs['Iterations'], I['Softness'])
    sp0 = b.node('GeometryNodeSetPosition')
    b.feed(sp0.inputs['Geometry'], sub.outputs['Mesh'])
    b.feed(sp0.inputs['Position'], blur.outputs['Value'])
    nrm = b.node('GeometryNodeInputNormal').outputs['Normal']
    soft = _noise(b, size, 4.0, I['Seed'], 3.0, 0.5)
    grain = _noise(b, size, 60.0, b.math('ADD', I['Seed'], 7.0), 2.0, 0.6)
    off = b.math('ADD', b.math('MULTIPLY', b.math('MULTIPLY', b.math('MULTIPLY', I['Thickness'], 0.03), size),
                               b.math('ADD', 0.6, b.math('MULTIPLY', soft, 0.8))),
                 b.math('MULTIPLY', b.math('MULTIPLY', b.math('SUBTRACT', grain, 0.5), b.math('MULTIPLY', I['Grain'], 0.004)), size))
    sp = b.node('GeometryNodeSetPosition')
    b.feed(sp.inputs['Geometry'], sp0.outputs['Geometry'])
    b.feed(sp.inputs['Offset'], b.vec('SCALE', nrm, scale=off))
    geo = _color(b, sp.outputs['Geometry'], b.math('ADD', b.math('MULTIPLY', soft, 0.7), b.math('MULTIPLY', grain, 0.3)),
                 I['Color A'], I['Color B'])
    return _finish(b, geo, I['Material'])


def _snow(b, I):
    geo = I['Geometry']
    size = _diag(b, geo)
    sub = b.node('GeometryNodeSubdivisionSurface')
    b.feed(sub.inputs['Mesh'], _even(b, geo, size))
    b.feed(sub.inputs['Level'], I['Detail'])
    blur = b.node('GeometryNodeBlurAttribute', data_type='FLOAT_VECTOR')
    b.feed(blur.inputs['Value'], b.node('GeometryNodeInputPosition').outputs['Position'])
    b.feed(blur.inputs['Iterations'], I['Smooth'])
    sp0 = b.node('GeometryNodeSetPosition')
    b.feed(sp0.inputs['Geometry'], sub.outputs['Mesh'])
    b.feed(sp0.inputs['Position'], blur.outputs['Value'])
    nrm = b.node('GeometryNodeInputNormal').outputs['Normal']
    up = b.node('ShaderNodeSeparateXYZ')
    b.feed(up.inputs[0], nrm)
    top = b.math('ADD', 0.35, b.math('MULTIPLY', b.math('MAXIMUM', up.outputs['Z'], 0.0), 0.65))   # (more on its top)
    lump = _noise(b, size, I['Lump Scale'], I['Seed'], 3.0, 0.45)
    off = b.math('ADD', b.math('MULTIPLY', b.math('MULTIPLY', b.math('MULTIPLY', I['Puff'], 0.05), size), top),
                 b.math('MULTIPLY', b.math('MULTIPLY', b.math('SUBTRACT', lump, 0.5), b.math('MULTIPLY', I['Lumps'], 0.08)), size))
    sp = b.node('GeometryNodeSetPosition')
    b.feed(sp.inputs['Geometry'], sp0.outputs['Geometry'])
    b.feed(sp.inputs['Offset'], b.vec('SCALE', nrm, scale=off))
    shade = b.math('SUBTRACT', 1.0, b.math('MAXIMUM', up.outputs['Z'], 0.0))     # (the sides / under: the blue shade)
    geo = _color(b, sp.outputs['Geometry'], b.math('MULTIPLY', shade, 0.8), I['Color A'], I['Color B'])
    return _finish(b, geo, I['Material'])


def _leaves(b, I):
    geo = I['Geometry']
    dist = b.node('GeometryNodeDistributePointsOnFaces', distribute_method='RANDOM')
    b.feed(dist.inputs['Mesh'], geo)
    b.feed(dist.inputs['Density'], I['Density'])
    b.feed(dist.inputs['Seed'], I['Seed'])
    pts = b.store(dist.outputs['Points'], 'mch_n', dist.outputs['Normal'], 'FLOAT_VECTOR')
    idx = b.node('GeometryNodeInputIndex').outputs['Index']
    align = b.node('FunctionNodeAlignRotationToVector', axis='Z')
    b.feed(align.inputs['Vector'], b.attr('mch_n', 'FLOAT_VECTOR').outputs['Attribute'])
    spin = b.node('FunctionNodeAxisAngleToRotation')
    spin.inputs['Axis'].default_value = (0.0, 0.0, 1.0)
    b.feed(spin.inputs['Angle'], b.random(idx, b.math('ADD', I['Seed'], 1.0), 0.0, 2 * math.pi))
    tilt_ax = b.node('ShaderNodeCombineXYZ')
    b.feed(tilt_ax.inputs[0], b.random(idx, b.math('ADD', I['Seed'], 2.0), -1.0, 1.0))
    b.feed(tilt_ax.inputs[1], b.random(idx, b.math('ADD', I['Seed'], 3.0), -1.0, 1.0))
    tilt = b.node('FunctionNodeAxisAngleToRotation')
    b.feed(tilt.inputs['Axis'], b.vec('NORMALIZE', b.vec('ADD', tilt_ax.outputs['Vector'], (1e-4, 0.0, 0.0))))
    b.feed(tilt.inputs['Angle'], b.math('MULTIPLY', I['Tilt'], b.random(idx, b.math('ADD', I['Seed'], 4.0))))
    r1 = b.node('FunctionNodeRotateRotation', rotation_space='LOCAL')
    b.feed(r1.inputs['Rotation'], align.outputs['Rotation'])
    b.feed(r1.inputs['Rotate By'], spin.outputs['Rotation'])
    r2 = b.node('FunctionNodeRotateRotation', rotation_space='LOCAL')
    b.feed(r2.inputs['Rotation'], r1.outputs['Rotation'])
    b.feed(r2.inputs['Rotate By'], tilt.outputs['Rotation'])
    s = b.math('MULTIPLY', I['Leaf Size'], b.math('SUBTRACT', 1.0, b.math(
        'MULTIPLY', I['Size Random'], b.random(idx, b.math('ADD', I['Seed'], 5.0)))))
    ci = b.node('GeometryNodeCollectionInfo', transform_space='ORIGINAL')
    b.feed(ci.inputs['Collection'], I['Leaves'])
    ci.inputs['Separate Children'].default_value = True
    ci.inputs['Reset Children'].default_value = True
    iop = b.node('GeometryNodeInstanceOnPoints')
    b.feed(iop.inputs['Points'], pts)
    b.feed(iop.inputs['Instance'], ci.outputs['Instances'])
    iop.inputs['Pick Instance'].default_value = True
    ri = b.node('FunctionNodeRandomValue', data_type='INT')
    ins = {x.name: x for x in b._on(ri.inputs)}
    ins['Min'].default_value = 0
    ins['Max'].default_value = 99
    b.feed(ins['ID'], idx)
    b.feed(ins['Seed'], b.math('ADD', I['Seed'], 6.0))
    b.feed(iop.inputs['Instance Index'], b._on(ri.outputs)[0])
    b.feed(iop.inputs['Rotation'], r2.outputs['Rotation'])
    b.feed(iop.inputs['Scale'], s)
    # piled: each leaf lifted off the surface by a random share of Pile leaf sizes
    lift = b.node('GeometryNodeTranslateInstances')
    b.feed(lift.inputs['Instances'], iop.outputs['Instances'])
    iidx = b.node('GeometryNodeInputIndex').outputs['Index']
    b.feed(lift.inputs['Translation'], b.vec('SCALE', b.attr('mch_n', 'FLOAT_VECTOR').outputs['Attribute'], scale=b.math(
        'MULTIPLY', b.math('MULTIPLY', I['Pile'], I['Leaf Size']),
        b.math('POWER', b.random(iidx, b.math('ADD', I['Seed'], 7.0)), 1.6))))
    try:
        lift.inputs['Local Space'].default_value = False
    except KeyError:
        pass
    # colours: green to yellow / orange / brown by Autumn
    ra = b.random(iidx, b.math('ADD', I['Seed'], 8.0))
    rb = b.random(iidx, b.math('ADD', I['Seed'], 9.0))
    autumn = b.mix_col(rb, b.mix_col(ra, (0.75, 0.55, 0.06, 1.0), (0.62, 0.2, 0.03, 1.0)), (0.28, 0.14, 0.05, 1.0))
    green = b.mix_col(ra, (0.12, 0.3, 0.05, 1.0), (0.32, 0.42, 0.08, 1.0))
    is_aut = b.math('LESS_THAN', b.random(iidx, b.math('ADD', I['Seed'], 10.0)), I['Autumn'])
    leaves = b.store(lift.outputs['Instances'], 'mch_leaf_col', b.mix_col(is_aut, green, autumn), 'FLOAT_COLOR', 'INSTANCE')
    base = b.store(geo, 'mch_w_col', I['Base Color'], 'FLOAT_COLOR')
    base = _finish(b, base, I['Material'], smooth=False)
    sw = b.node('GeometryNodeSwitch', input_type='GEOMETRY')
    b.feed(sw.inputs['Switch'], I['Show Base'])
    b.feed(sw.inputs['True'], base)
    join = b.node('GeometryNodeJoinGeometry')
    b.feed(join.inputs[0], leaves)
    b.feed(join.inputs[0], sw.outputs['Output'])
    real = b.node('GeometryNodeRealizeInstances')
    b.feed(real.inputs['Geometry'], join.outputs['Geometry'])
    sw2 = b.node('GeometryNodeSwitch', input_type='GEOMETRY')
    b.feed(sw2.inputs['Switch'], I['Realize'])
    b.feed(sw2.inputs['False'], join.outputs['Geometry'])
    b.feed(sw2.inputs['True'], real.outputs['Geometry'])
    return sw2.outputs['Output']


BUILD = {'DIRT': _dirt, 'DUST': _dust, 'LEAVES': _leaves, 'SNOW': _snow}


def tree(kind):
    name = f'MCH Weather {LABEL[kind]}'
    ng = bpy.data.node_groups.get(name)
    if ng is not None and ng.get('mch_v') == TREE_VERSION:
        return ng
    if ng is None:
        ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng.nodes.clear()
    ng.interface.clear()
    _inputs(ng, kind)
    b = _B(ng)
    gi = b.node('NodeGroupInput')
    go = b.node('NodeGroupOutput')
    out = BUILD[kind](b, gi.outputs)
    b.feed(go.inputs[0], out)
    ng['mch_v'] = TREE_VERSION
    return ng


# ---- materials, the leaf shapes ------------------------------------------------------------------------------------

def _material(name, attr, kind_of_attr, rough, extra=None):
    mat = bpy.data.materials.get(name)
    if mat is not None and mat.get('mch_v') == 2:
        return mat
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    at = nt.nodes.new('ShaderNodeAttribute')
    at.attribute_type = kind_of_attr
    at.attribute_name = attr
    at.location = (-500, 0)
    pb = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(at.outputs['Color'], pb.inputs['Base Color'])
    pb.inputs['Roughness'].default_value = rough
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (300, 0)
    nt.links.new(pb.outputs[0], out.inputs['Surface'])
    if extra:
        extra(nt, pb, at)
    mat['mch_v'] = 2
    return mat


def _snow_extra(nt, pb, at):
    for k, v in (('Subsurface Weight', 0.3), ('Subsurface Scale', 0.02), ('Coat Weight', 0.15)):
        if k in pb.inputs:
            pb.inputs[k].default_value = v
    if 'Subsurface Radius' in pb.inputs:
        pb.inputs['Subsurface Radius'].default_value = (1.0, 1.0, 1.2)


def _leaf_extra(nt, pb, at):
    for k, v in (('Transmission Weight', 0.15), ('Sheen Weight', 0.1)):
        if k in pb.inputs:
            pb.inputs[k].default_value = v


def material(kind):
    if kind == 'DIRT':
        return _material('MCH Dirt', 'mch_w_col', 'GEOMETRY', 0.92)
    if kind == 'DUST':
        return _material('MCH Dust', 'mch_w_col', 'GEOMETRY', 1.0)
    if kind == 'SNOW':
        return _material('MCH Snow', 'mch_w_col', 'GEOMETRY', 0.42, _snow_extra)
    return _material('MCH Soil', 'mch_w_col', 'GEOMETRY', 0.95)


def _leaf_both(nt, pb, at):
    """The leaf colour from the instancer (live leaves) or from the mesh itself (applied: realized leaves carry it)."""
    _leaf_extra(nt, pb, at)
    ag = nt.nodes.new('ShaderNodeAttribute')
    ag.attribute_type = 'GEOMETRY'
    ag.attribute_name = 'mch_leaf_col'
    ag.location = (-500, -220)
    add = nt.nodes.new('ShaderNodeMix')
    add.data_type = 'RGBA'
    add.blend_type = 'ADD'
    add.location = (-250, -100)
    ins = [x for x in add.inputs if x.enabled]
    ins[0].default_value = 1.0
    nt.links.new(at.outputs['Color'], ins[1])
    nt.links.new(ag.outputs['Color'], ins[2])
    nt.links.new([x for x in add.outputs if x.enabled][0], pb.inputs['Base Color'])


def leaf_material():
    m = _material('MCH Leaf', 'mch_leaf_col', 'INSTANCER', 0.55, _leaf_both)
    m.use_backface_culling = False
    return m


def _leaf_mesh(name, outline, fold=0.18, bend=0.25):
    """A leaf about 1 long along X (stem end at -0.5), lying on Z = 0, folded along its midrib and bent."""
    bm = bmesh.new()
    pts = [bm.verts.new((x, y, abs(y) * fold + (x * x) * bend * 0.3)) for x, y in outline]
    mid = [bm.verts.new((x, 0.0, (x * x) * bend * 0.3)) for x in (-0.45, -0.15, 0.15, 0.45)]
    bm.verts.ensure_lookup_table()
    try:
        bm.faces.new(pts)
    except ValueError:
        pass
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    for v in mid:
        bm.verts.remove(v)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def leaf_collection():
    """The leaf shapes (oval, maple, long, round) in a collection not linked to the scene (only instanced)."""
    coll = bpy.data.collections.get(LEAF_COLL)
    if coll is not None and len(coll.objects) >= 4:
        return coll
    if coll is None:
        coll = bpy.data.collections.new(LEAF_COLL)
    mat = leaf_material()
    shapes = []
    n = 24
    oval = []
    for i in range(n):                                   # (pointed at the tip, round at the stem)
        t = 2 * math.pi * i / n
        x, y = 0.5 * math.cos(t), 0.22 * math.sin(t)
        if x > 0:
            y *= 1.0 - 0.55 * (x / 0.5) ** 2
        oval.append((x, y))
    shapes.append(('Leaf Oval', oval))
    maple = []
    for i in range(40):                                  # (five lobes)
        t = 2 * math.pi * i / 40
        r = 0.32 + 0.16 * max(0.0, math.cos(5 * (t - math.pi))) ** 2
        maple.append((0.1 + r * math.cos(t), r * math.sin(t)))
    shapes.append(('Leaf Maple', maple))
    long_ = [(0.5 * math.cos(2 * math.pi * i / n), 0.09 * math.sin(2 * math.pi * i / n)) for i in range(n)]
    shapes.append(('Leaf Long', long_))
    rnd = [(0.33 * math.cos(2 * math.pi * i / n), 0.3 * math.sin(2 * math.pi * i / n)) for i in range(n)]
    shapes.append(('Leaf Round', rnd))
    for name, outline in shapes:
        if name in coll.objects:
            continue
        me = _leaf_mesh(name, outline)
        me.materials.append(mat)
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
    return coll


# ---- the weathered object ------------------------------------------------------------------------------------------

def kind_of(ob):
    k = ob.get(KEY) if ob is not None else None
    return k if k in KINDS else None


def pg_of(holder, kind):
    return getattr(holder, 'mch_w' + kind.lower(), None)


def push(ob):
    from . import geo_sculpt as gs
    kind = kind_of(ob)
    mod = ob.modifiers.get(MOD)
    pg = pg_of(ob, kind) if kind else None
    if mod is None or pg is None:
        return
    for prop, name, typ, *_r in SPEC[kind]:
        v = getattr(pg, prop)
        gs.set_input(mod, name, tuple(v) if typ == 'COLOR' else v)


def apply(context, ob, kind):
    """``ob`` becomes ``kind`` (live): the modifier at the end of its stack, the values of the next one."""
    from . import geo_sculpt as gs
    if ob is None or ob.type != 'MESH':
        return None
    mod = ob.modifiers.get(MOD)
    if mod is None:
        mod = ob.modifiers.new(MOD, 'NODES')
    mod.node_group = tree(kind)
    gs.set_input(mod, 'Material', material(kind))
    if kind == 'LEAVES':
        gs.set_input(mod, 'Leaves', leaf_collection())
    ob[KEY] = kind
    src, dst = pg_of(context.scene, kind), pg_of(ob, kind)
    _BUSY[0] = True
    try:
        for prop, *_r in SPEC[kind]:
            setattr(dst, prop, getattr(src, prop))
    finally:
        _BUSY[0] = False
    push(ob)
    return mod


def remove(ob):
    mod = ob.modifiers.get(MOD)
    if mod is not None:
        ob.modifiers.remove(mod)
    if KEY in ob:
        del ob[KEY]


def bake(context, ob):
    """The weathering as real geometry (the modifier applied; the leaves made real)."""
    from . import geo_sculpt as gs
    mod = ob.modifiers.get(MOD)
    if kind_of(ob) == 'LEAVES' and mod is not None:
        gs.set_input(mod, 'Realize', True)
    with context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
        bpy.ops.object.modifier_apply(modifier=MOD)
    if KEY in ob:
        del ob[KEY]


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


def active(context, kind=None):
    ob = getattr(context.view_layer.objects, 'active', None)
    k = kind_of(ob)
    return ob if k is not None and (kind is None or k == kind) else None


# ---- settings, operators, the window -------------------------------------------------------------------------------

_BUSY = [False]


def _upd(self, context):
    if _BUSY[0]:
        return
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and kind_of(ob):
        push(ob)
        kind = kind_of(ob)
        sc = getattr(context, 'scene', None)
        if sc is not None and pg_of(sc, kind) is not None and pg_of(ob, kind) == self:
            _BUSY[0] = True
            try:
                for prop, *_r in SPEC[kind]:              # (the values go on to the next one)
                    setattr(pg_of(sc, kind), prop, getattr(self, prop))
            finally:
                _BUSY[0] = False


def _make_pg(kind):
    ann = {}
    for prop, name, typ, default, lo, hi, soft, desc in SPEC[kind]:
        if typ == 'INT':
            kw = dict(name=name, default=default, min=lo, max=hi, update=_upd, description=desc)
            if soft is not None:
                kw['soft_max'] = soft
            ann[prop] = IntProperty(**kw)
        elif typ == 'BOOL':
            ann[prop] = BoolProperty(name=name, default=default, update=_upd, description=desc)
        elif typ == 'COLOR':
            ann[prop] = FloatVectorProperty(name=name, default=default, size=4, subtype='COLOR', min=0.0, max=1.0,
                                            update=_upd, description=desc)
        else:
            kw = dict(name=name, default=default, min=lo, max=hi, update=_upd, description=desc)
            if soft is not None:
                kw['soft_max'] = soft
            if prop == 'leaf_size':
                kw['unit'] = 'LENGTH'
            if prop == 'tilt':
                kw['subtype'] = 'ANGLE'
            ann[prop] = FloatProperty(**kw)
    return type(f'MCH_PG_Weather{LABEL[kind]}', (bpy.types.PropertyGroup,), {'__annotations__': ann})


PGS = {k: _make_pg(k) for k in KINDS}


class MCH_OT_weather_click(bpy.types.Operator):
    """Click a mesh: it becomes dirt / dust / leaves / snow (the tool's).  Alt + click: back to the shape"""
    bl_idname = 'mch.weather_click'
    bl_label = 'Weathering'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    kind: EnumProperty(items=[(k, LABEL[k], '') for k in KINDS], default='DIRT', options={'SKIP_SAVE'})
    clear: BoolProperty(default=False, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            return {'PASS_THROUGH'}
        ob = pick(context, (event.mouse_region_x, event.mouse_region_y))
        if ob is None:
            return {'PASS_THROUGH'}                     # (empty space: the usual click)
        return self._do(context, ob)

    def _do(self, context, ob):
        if self.clear:
            if kind_of(ob) is None:
                self.report({'INFO'}, f'{ob.name}: no weathering on it')
                return {'CANCELLED'}
            remove(ob)
            msg = f'{ob.name}: back to the shape (weathering taken off)'
        else:
            apply(context, ob, self.kind)
            msg = f'{ob.name}: {LABEL[self.kind]} (live - its values in the window; Alt + click: back to the shape)'
        for o in context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        self.report({'INFO'}, msg)
        try:
            from . import side_panel
            side_panel.dirty()
        except (ImportError, AttributeError):
            pass
        return {'FINISHED'}

    def execute(self, context):
        ob = getattr(context.view_layer.objects, 'active', None)
        if ob is None or ob.type != 'MESH':
            return {'CANCELLED'}
        return self._do(context, ob)


class MCH_OT_weather_bake(bpy.types.Operator):
    """The selected weathering as real geometry (not live any more)"""
    bl_idname = 'mch.weather_bake'
    bl_label = 'Apply Weathering'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return active(context) is not None

    def execute(self, context):
        ob = active(context)
        try:
            bake(context, ob)
        except RuntimeError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, f'{ob.name}: real geometry ({len(ob.data.polygons):,} faces)')
        return {'FINISHED'}


def draw(layout, context, kind):
    ob = active(context, kind)
    pg = pg_of(ob, kind) if ob is not None else pg_of(context.scene, kind)
    col = layout.column(align=True)
    col.label(text=f'{ob.name}: {LABEL[kind]} (live)' if ob is not None else f'The next {LABEL[kind].lower()}')
    for prop, *_r in SPEC[kind]:
        col.prop(pg, prop)
    row = layout.row(align=True)
    if ob is not None:
        o = row.operator('mch.weather_click', text='Back to Shape')
        o.clear = True
        row.operator('mch.weather_bake', text='Apply')
    col = layout.column(align=True)
    for line in (f'Click a mesh: it becomes {LABEL[kind].lower()}', 'Alt + click: back to the shape',
                 'Made with Base Mesh, plates, Surface Draw ... stays live under it'):
        col.label(text=line)


def _keymap(kind):
    return (('mch.weather_click', {'type': 'LEFTMOUSE', 'value': 'PRESS'}, {'properties': [('kind', kind)]}),
            ('mch.weather_click', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'alt': True},
             {'properties': [('kind', kind), ('clear', True)]}),
            ('mch.exit_tool', {'type': 'ESC', 'value': 'PRESS'}, None))


def _tool(kind, desc):
    def draw_settings(context, layout, tool):
        region = getattr(context, 'region', None)
        if region is not None and region.type == 'TOOL_HEADER':
            return
        draw(layout, context, kind)
    return type(f'MCH_TOOL_weather_{kind.lower()}', (bpy.types.WorkSpaceTool,), {
        'bl_space_type': 'VIEW_3D', 'bl_context_mode': 'OBJECT', 'bl_idname': f'mecha.weather_{kind.lower()}',
        'bl_label': f'Mecha {LABEL[kind]}', 'bl_description': desc, 'bl_icon': 'ops.generic.select_paint',
        'bl_widget': None, 'bl_keymap': _keymap(kind), 'draw_settings': staticmethod(draw_settings)})


TOOLS = (
    _tool('DIRT', 'Click a mesh: it becomes dirt - lumpy, clods and crumbs over it, brown.\nAlt + click: back to the shape'),
    _tool('DUST', 'Click a mesh: it becomes a soft dust layer.\nAlt + click: back to the shape'),
    _tool('LEAVES', 'Click a mesh: leaves piled over it (green to autumn).\nAlt + click: back to the shape'),
    _tool('SNOW', 'Click a mesh: it becomes snow - smoothed, puffed, white.\nAlt + click: back to the shape'),
)
CLASSES = tuple(PGS.values()) + (MCH_OT_weather_click, MCH_OT_weather_bake)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    for k, cls in PGS.items():
        setattr(bpy.types.Scene, 'mch_w' + k.lower(), PointerProperty(type=cls))
        setattr(bpy.types.Object, 'mch_w' + k.lower(), PointerProperty(type=cls))
    prev = 'mecha.creature_fur'
    for t in TOOLS:
        try:
            bpy.utils.register_tool(t, after={prev}, group=False)
        except (ValueError, RuntimeError, KeyError):
            try:
                bpy.utils.register_tool(t, separator=True, group=False)
            except (ValueError, RuntimeError):
                pass
        prev = t.bl_idname


def unregister():
    for t in reversed(TOOLS):
        try:
            bpy.utils.unregister_tool(t)
        except (ValueError, RuntimeError, KeyError):
            pass
    for k in KINDS:
        for holder in (bpy.types.Scene, bpy.types.Object):
            try:
                delattr(holder, 'mch_w' + k.lower())
            except AttributeError:
                pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
