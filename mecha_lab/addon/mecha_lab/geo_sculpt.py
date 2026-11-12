"""0.24.142 Geo Sculpt: sculpt brushes on a plain (not DynaMeshed) part in the Mecha Lab, faked with Geometry Nodes.

User: "다이나 메쉬 안 한 메쉬에서 지오메트리 노드로 그런 척하게 해 달라구" / "이런 지오메트리 스컬핑은 한 창으로 묶어서 만들고
그거 눌러서 작동할 때는 지브러시 창처럼 S 눌러서 브러시 크기 조정하는 게 좋겠어" / "플랫은 알트 누르면 튀어나와야 되고" /
(the line brush) "내가 그은 만큼만 적용되게 하고 싶어".

One tool (Geo Sculpt) with its brushes in one window (the side panel):

    Standard  Clay  Clay Buildup  Flat  Move  Smooth  Edge Line  Chamfer  Round

How it works (nothing is written into the part until Apply):
  * every stroke is kept as points (an edge chain) in a small stroke mesh of its own - the part's local space, so the
    sculpt follows the part - with per point: stroke, radius, strength (Alt: negative), kind, move, normal, fade
  * the part's "MCH Geo Sculpt" Geometry Nodes modifier subdivides only the faces within reach of a stroke (the level
    from Detail, a face budget caps it), then adds the strokes in order (a repeat zone): Standard = a bell along the
    normal, Clay = a flat-topped band, Clay Buildup = filled up to a plane (Alt: dug down), Flat = cut down to
    the plane under the brush (along a corner: a flat facet; Alt: a raised flat pad), Move = the grab point dragged, Smooth = blurred, Edge Line = in the band
    along the drawn line each side becomes flat (the straight chord to the band's edge) and the points slide onto the
    line, so the edge is exactly where it was drawn - only as far as it goes, its ends fade (Alt: an inward edge),
    Panel Line = a groove along the line, flat floor and straight walls, crisp the same way (Alt: a raised rib)
  * Chamfer / Round mark the part's own hard edges along the stroke with the brush radius as width (Bevel modifiers by
    edge weight, before the sculpt layer); Alt takes it off
  * S = Draw Size at the cursor (move the mouse left / right, click / S = keep, right click / Esc = back), U = Intensity,
    Alt = invert, Shift = Smooth, Ctrl+Z = the last stroke back (one undo step per stroke)
  * Apply bakes the bevels + the layer into the part (T junctions where the subdivided region meets the rest are welded,
    so the part stays closed for the Cut tools); Clear removes everything.

Everything a test needs is plain here (``add_stroke``, ``mark_bevel``, ``apply``, ``clear``, ``node_group``); the
operators only add the mouse.
"""
from __future__ import annotations

import math

import bmesh
import bpy
import numpy as np
from bpy.props import EnumProperty, FloatProperty, IntProperty
from mathutils import Vector
from mathutils.bvhtree import BVHTree

MOD = 'MCH Geo Sculpt'
GROUP = 'MCH Geo Sculpt'
GROUP_VERSION = 16
PART_KEY = 'mch_geo_part'           # on the stroke object: the part it belongs to
CHAMFER_MOD, ROUND_MOD = 'MCH Geo Chamfer', 'MCH Geo Round'
BEVEL_MODS = {'CHAMFER': CHAMFER_MOD, 'ROUND': ROUND_MOD}
BEVEL_ATTR = {'CHAMFER': 'mch_geo_chamfer', 'ROUND': 'mch_geo_round'}   # (+ '_w': the widths as drawn)
ROUND_SEGMENTS = 5
HARD_ANGLE = math.radians(30.0)
FACE_BUDGET = 400000                # the subdivided region never gets more faces than this
KIND = {'STANDARD': 0, 'CLAY': 1, 'MOVE': 2, 'BUILDUP': 3, 'SMOOTH': 4, 'FLAT': 5, 'EDGE': 6, 'PANEL': 7}
LINE_KINDS = ('EDGE', 'PANEL')
PANEL_FLOOR = 0.35                  # a Panel Line's flat floor: this share of the band's half width
EDGE_FULL = 0.55                    # an Edge Line is fully flat inside this share of its band, then blends back
BRUSHES = (
    ('STANDARD', 'Standard', 'A soft bump along the surface (Alt: a dent)'),
    ('CLAY', 'Clay', 'A flat-topped band of clay (Alt: carved in)'),
    ('BUILDUP', 'Clay Buildup', 'Fills the surface up to a plane over the stroke - strokes build up flat (Alt: dug down)'),
    ('FLAT', 'Flat', 'Cuts what stands above the plane under the brush down to it - along a corner: a flat facet '
                     'across it; over bumps: trimmed (Alt: a flat pad pops out)'),
    ('MOVE', 'Move', 'Grab the surface and drag it'),
    ('SMOOTH', 'Smooth', 'Smooths the surface (Shift with any brush)'),
    ('EDGE', 'Edge Line', 'Draw a line: it becomes a crisp edge exactly where you drew it, only as far as you drew it '
                          '- in a band as wide as the brush both sides go flat (Alt: an inward edge)'),
    ('PANEL', 'Panel Line', 'Draw a line: a panel line along it - a groove with a flat floor and straight walls, as wide '
                            'as the brush, only as far as you drew it (Alt: a raised rib)'),
    ('CHAMFER', 'Chamfer', 'Stroke along a hard edge of the part: it is chamfered, as wide as the brush (Alt: taken off)'),
    ('ROUND', 'Round', 'Stroke along a hard edge of the part: it is rounded, as wide as the brush (Alt: taken off)'),
)
BRUSH_ROWS = (('STANDARD', 'CLAY', 'BUILDUP'), ('FLAT', 'MOVE', 'SMOOTH'), ('EDGE', 'PANEL'), ('CHAMFER', 'ROUND'))
BRUSH_COLOUR = {'STANDARD': (1.0, 0.62, 0.15, 0.95), 'CLAY': (1.0, 0.62, 0.15, 0.95), 'BUILDUP': (1.0, 0.62, 0.15, 0.95),
                'FLAT': (0.35, 0.8, 1.0, 0.95), 'MOVE': (0.6, 1.0, 0.45, 0.95), 'SMOOTH': (0.85, 0.85, 0.9, 0.9),
                'EDGE': (1.0, 0.35, 0.35, 0.95), 'PANEL': (1.0, 0.35, 0.35, 0.95), 'CHAMFER': (0.95, 0.4, 1.0, 0.95), 'ROUND': (0.95, 0.4, 1.0, 0.95)}
POINT_ATTRS = (('stroke', 'INT'), ('radius', 'FLOAT'), ('strength', 'FLOAT'), ('kind', 'INT'),
               ('move', 'FLOAT_VECTOR'), ('normal', 'FLOAT_VECTOR'), ('fade', 'FLOAT'))
_CURSOR = [None]


# -----------------------------------------------------------------------------
# settings
# -----------------------------------------------------------------------------

def _redraw(self=None, context=None):
    wm = getattr(bpy.context, 'window_manager', None)
    for w in getattr(wm, 'windows', ()):
        for a in w.screen.areas:
            if a.type == 'VIEW_3D':
                a.tag_redraw()


class MCH_PG_GeoSculpt(bpy.types.PropertyGroup):
    brush: EnumProperty(name='Brush', items=[(b[0], b[1], b[2]) for b in BRUSHES], default='STANDARD', update=_redraw)
    size_px: IntProperty(name='Draw Size', description='The brush radius on screen (S + move the mouse at the cursor, '
                         'like ZBrush) - Edge Line: the band\'s half width, Chamfer / Round: the bevel width',
                         default=60, min=3, max=1200, soft_max=500, subtype='PIXEL', update=_redraw)
    intensity: FloatProperty(name='Intensity', description='How strong a stroke is (U at the cursor)', default=0.5,
                             min=0.01, max=2.0, soft_max=1.0, update=_redraw)


def settings(context=None):
    scene = getattr(context or bpy.context, 'scene', None)
    return getattr(scene, 'mch_geo', None)


# -----------------------------------------------------------------------------
# the Geometry Nodes layer
# -----------------------------------------------------------------------------

def node_group():
    """The 'MCH Geo Sculpt' node group (built once; rebuilt when GROUP_VERSION changes)."""
    ng = bpy.data.node_groups.get(GROUP)
    if ng is not None and ng.get('mch_ver') == GROUP_VERSION and ng.bl_idname == 'GeometryNodeTree':
        return ng
    if ng is not None:
        ng.name = GROUP + ' (old)'
    ng = _build()
    ng['mch_ver'] = GROUP_VERSION
    return ng


def _build():
    ng = bpy.data.node_groups.new(GROUP, 'GeometryNodeTree')
    io = ng.interface
    io.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    io.new_socket('Strokes', in_out='INPUT', socket_type='NodeSocketObject')
    s = io.new_socket('Detail', in_out='INPUT', socket_type='NodeSocketFloat')
    s.default_value = 0.02
    s.min_value = 0.0005
    s = io.new_socket('Max Level', in_out='INPUT', socket_type='NodeSocketInt')
    s.default_value = 6
    s.min_value, s.max_value = 0, 8
    io.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links

    def node(t, **kw):
        n = N.new(t)
        for k, v in kw.items():
            setattr(n, k, v)
        return n

    def link(a, b):
        L.new(a, b)

    def math_(op, a=None, b=None, c=None):
        m = node('ShaderNodeMath', operation=op)
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                m.inputs[i].default_value = v
            else:
                link(v, m.inputs[i])
        return m.outputs[0]

    def vmath(op, a=None, b=None, scale=None):
        m = node('ShaderNodeVectorMath', operation=op)
        if a is not None:
            link(a, m.inputs[0])
        if b is not None:
            link(b, m.inputs[1])
        if scale is not None:
            if isinstance(scale, (int, float)):
                m.inputs['Scale'].default_value = scale
            else:
                link(scale, m.inputs['Scale'])
        return m.outputs['Value'] if op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE') else m.outputs['Vector']

    def named(name, typ='FLOAT'):
        a = node('GeometryNodeInputNamedAttribute', data_type=typ)
        a.inputs['Name'].default_value = name
        return a.outputs['Attribute']

    def pos():
        return node('GeometryNodeInputPosition').outputs[0]

    def stat(geo, value, typ='FLOAT'):
        s_ = node('GeometryNodeAttributeStatistic', data_type=typ, domain='POINT')
        link(geo, s_.inputs['Geometry'])
        link(value, s_.inputs['Attribute'])
        return s_

    def bool_(op, a, b=None):
        m = node('FunctionNodeBooleanMath', operation=op)
        link(a, m.inputs[0])
        if b is not None:
            link(b, m.inputs[1])
        return m.outputs[0]

    def switch(kind, cond, false, true):
        sw = node('GeometryNodeSwitch', input_type=kind)
        link(cond, sw.inputs['Switch'])
        for sock, v in (('False', false), ('True', true)):
            if isinstance(v, (int, float, tuple)):
                sw.inputs[sock].default_value = v
            else:
                link(v, sw.inputs[sock])
        return sw.outputs['Output']

    gi = node('NodeGroupInput')
    go = node('NodeGroupOutput')
    info = node('GeometryNodeObjectInfo')
    info.transform_space = 'ORIGINAL'
    link(gi.outputs['Strokes'], info.inputs['Object'])
    strokes = info.outputs['Geometry']
    detail = gi.outputs['Detail']
    # --- the region: faces with a corner within reach of a stroke ----------------------------------------------------
    rmax = stat(strokes, named('radius'))
    mmax = stat(strokes, vmath('LENGTH', named('move', 'FLOAT_VECTOR')))
    reach = math_('ADD', math_('MULTIPLY', rmax.outputs['Max'], 1.2), mmax.outputs['Max'])
    prox = node('GeometryNodeProximity', target_element='EDGES')
    link(strokes, prox.inputs[0])
    proxp = node('GeometryNodeProximity', target_element='POINTS')
    link(strokes, proxp.inputs[0])
    dmin = math_('MINIMUM', prox.outputs['Distance'], proxp.outputs['Distance'])
    near_pt = math_('LESS_THAN', dmin, reach)
    # the part's hard edges (sharp, Edge Memory, or folded more than 30 degrees) - kept sharp in the region
    ang0 = node('GeometryNodeInputMeshEdgeAngle')
    hard0 = bool_('OR', bool_('OR', math_('GREATER_THAN', ang0.outputs['Unsigned Angle'], HARD_ANGLE),
                              named('sharp_edge', 'BOOLEAN')), named('mch_hard', 'BOOLEAN'))
    mark = node('GeometryNodeStoreNamedAttribute', data_type='BOOLEAN', domain='EDGE')
    mark.inputs['Name'].default_value = '.mch_geo_hard'
    link(gi.outputs['Geometry'], mark.inputs['Geometry'])
    link(hard0, mark.inputs['Value'])
    part = mark.outputs['Geometry']
    # the region: faces with a corner or the centre within reach, or the face a stroke point lies on (a stroke in the
    # middle of a big face), and one ring of faces more (a big face beside the stroke)
    nf = node('GeometryNodeSampleNearest', domain='FACE')
    link(part, nf.inputs['Geometry'])
    st_fi = node('GeometryNodeStoreNamedAttribute', data_type='INT', domain='POINT')
    st_fi.inputs['Name'].default_value = 'fi'
    link(strokes, st_fi.inputs['Geometry'])
    link(nf.outputs['Index'], st_fi.inputs['Value'])
    fi_near = node('GeometryNodeSampleNearest', domain='POINT')
    link(st_fi.outputs['Geometry'], fi_near.inputs['Geometry'])
    fi_val = node('GeometryNodeSampleIndex', data_type='INT', domain='POINT')
    link(st_fi.outputs['Geometry'], fi_val.inputs['Geometry'])
    link(named('fi', 'INT'), fi_val.inputs['Value'])
    link(fi_near.outputs['Index'], fi_val.inputs['Index'])
    own = node('FunctionNodeCompare', data_type='INT', operation='EQUAL')
    link(fi_val.outputs['Value'], own.inputs['A'])
    link(node('GeometryNodeInputIndex').outputs[0], own.inputs['B'])
    corner = node('GeometryNodeFieldOnDomain', domain='POINT', data_type='FLOAT')
    link(near_pt, corner.inputs[0])
    sel0 = bool_('OR', bool_('OR', math_('GREATER_THAN', corner.outputs[0], 0.0), near_pt), own.outputs['Result'])
    has_pts = math_('GREATER_THAN', node_count := node('GeometryNodeAttributeDomainSize', component='MESH').outputs['Point Count'], 0.0)
    link(strokes, node_count.node.inputs['Geometry'])
    sel0 = bool_('AND', sel0, has_pts)
    keep_sel = node('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='FACE')
    keep_sel.inputs['Name'].default_value = '.mch_geo_sel'
    link(part, keep_sel.inputs['Geometry'])
    link(sel0, keep_sel.inputs['Value'])
    ring_p = node('GeometryNodeFieldOnDomain', domain='FACE', data_type='FLOAT')
    link(named('.mch_geo_sel'), ring_p.inputs[0])
    keep_p = node('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='POINT')
    keep_p.inputs['Name'].default_value = '.mch_geo_selp'
    link(keep_sel.outputs['Geometry'], keep_p.inputs['Geometry'])
    link(ring_p.outputs[0], keep_p.inputs['Value'])
    ring_f = node('GeometryNodeFieldOnDomain', domain='POINT', data_type='FLOAT')
    link(named('.mch_geo_selp'), ring_f.inputs[0])
    sep = node('GeometryNodeSeparateGeometry', domain='FACE')
    link(keep_p.outputs['Geometry'], sep.inputs['Geometry'])
    link(math_('GREATER_THAN', ring_f.outputs[0], 0.0), sep.inputs['Selection'])
    region, rest = sep.outputs['Selection'], sep.outputs['Inverted']
    # --- the region subdivided: the level from its longest edge and Detail, capped by Max Level and the face budget ---
    ev = node('GeometryNodeInputMeshEdgeVertices')
    emax = node('GeometryNodeAttributeStatistic', data_type='FLOAT', domain='EDGE')
    link(region, emax.inputs['Geometry'])
    link(vmath('DISTANCE', ev.outputs['Position 1'], ev.outputs['Position 2']), emax.inputs['Attribute'])
    lvl = math_('CEIL', math_('LOGARITHM', math_('DIVIDE', emax.outputs['Max'], detail), 2.0))
    fcount = node('GeometryNodeAttributeDomainSize', component='MESH')
    link(region, fcount.inputs['Geometry'])
    budget = math_('FLOOR', math_('LOGARITHM', math_('DIVIDE', float(FACE_BUDGET),
                                                     math_('MAXIMUM', fcount.outputs['Face Count'], 1.0)), 4.0))
    lvl = math_('MINIMUM', math_('MINIMUM', math_('MAXIMUM', lvl, 0.0), gi.outputs['Max Level']), math_('MAXIMUM', budget, 0.0))
    # the region subdivided twice with the same level (the same points): linear (the part's exact shape) and
    # Catmull-Clark (smooth like the smooth-shaded part - linear showed its facets), its hard edges creased and their
    # points pinned.  Smooth in the region, ramping to the exact shape across its outermost faces (no stroke reaches
    # them): no seam against the untouched rest, the rest of the part exactly as it was
    bnd = node('GeometryNodeFieldOnDomain', domain='EDGE', data_type='FLOAT')
    link(math_('COMPARE', node('GeometryNodeInputMeshEdgeNeighbors').outputs['Face Count'], 1.0, 0.1), bnd.inputs[0])
    keepb = node('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='POINT')
    keepb.inputs['Name'].default_value = '.mch_geo_b'
    link(region, keepb.inputs['Geometry'])
    link(math_('GREATER_THAN', bnd.outputs[0], 0.0), keepb.inputs['Value'])
    region = keepb.outputs['Geometry']
    lin = node('GeometryNodeSubdivideMesh')
    link(region, lin.inputs['Mesh'])
    link(lvl, lin.inputs['Level'])
    eflag = named('.mch_geo_hard', 'BOOLEAN')
    vflag = node('GeometryNodeFieldOnDomain', domain='EDGE', data_type='FLOAT')
    link(eflag, vflag.inputs[0])
    cc = node('GeometryNodeSubdivisionSurface')
    link(region, cc.inputs['Mesh'])
    link(lvl, cc.inputs['Level'])
    link(eflag, cc.inputs['Edge Crease'])
    link(math_('GREATER_THAN', vflag.outputs[0], 0.0), cc.inputs['Vertex Crease'])
    cc_pos = node('GeometryNodeSampleIndex', data_type='FLOAT_VECTOR', domain='POINT')
    link(cc.outputs['Mesh'], cc_pos.inputs['Geometry'])
    link(pos(), cc_pos.inputs['Value'])
    link(node('GeometryNodeInputIndex').outputs[0], cc_pos.inputs['Index'])
    wsm = node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP', clamp=True)
    link(named('.mch_geo_b'), wsm.inputs['Value'])
    wsm.inputs['From Min'].default_value = 1.0
    wsm.inputs['From Max'].default_value = 0.0
    blend = node('GeometryNodeSetPosition')
    link(lin.outputs['Mesh'], blend.inputs['Geometry'])
    link(vmath('SCALE', vmath('SUBTRACT', cc_pos.outputs['Value'], pos()), scale=wsm.outputs['Result']), blend.inputs['Offset'])
    sub = blend
    keepn = node('GeometryNodeStoreNamedAttribute', data_type='FLOAT_VECTOR', domain='POINT')
    keepn.inputs['Name'].default_value = '.mch_geo_n'
    link(sub.outputs['Geometry'], keepn.inputs['Geometry'])
    link(node('GeometryNodeInputNormal').outputs[0], keepn.inputs['Value'])
    # --- every stroke in turn (a repeat zone) --------------------------------------------------------------------------
    smax = stat(strokes, named('stroke', 'INT'))
    rin = node('GeometryNodeRepeatInput')
    rout = node('GeometryNodeRepeatOutput')
    rin.pair_with_output(rout)
    rout.repeat_items.new('INT', 'Index')
    cnt = node('GeometryNodeAttributeDomainSize', component='MESH')
    link(strokes, cnt.inputs['Geometry'])
    iters = switch('INT', math_('GREATER_THAN', cnt.outputs['Point Count'], 0.0), 0, math_('ADD', smax.outputs['Max'], 1.0))
    link(iters, rin.inputs['Iterations'])
    link(keepn.outputs['Geometry'], rin.inputs['Geometry'])
    rin.inputs['Index'].default_value = 0
    cur = rin.outputs['Geometry']
    eq = node('FunctionNodeCompare', data_type='INT', operation='EQUAL')
    link(named('stroke', 'INT'), eq.inputs['A'])
    link(rin.outputs['Index'], eq.inputs['B'])
    one = node('GeometryNodeSeparateGeometry', domain='POINT')
    link(strokes, one.inputs['Geometry'])
    link(eq.outputs['Result'], one.inputs['Selection'])
    st = one.outputs['Selection']
    r = stat(st, named('radius')).outputs['Mean']
    k = stat(st, named('kind', 'INT')).outputs['Mean']
    strength = stat(st, named('strength')).outputs['Mean']
    mvec = stat(st, named('move', 'FLOAT_VECTOR'), 'FLOAT_VECTOR').outputs['Mean']
    k_abs = math_('MINIMUM', math_('ABSOLUTE', strength), 1.0)
    sp = node('GeometryNodeProximity', target_element='EDGES')
    link(st, sp.inputs[0])
    spp = node('GeometryNodeProximity', target_element='POINTS')
    link(st, spp.inputs[0])
    ecount = node('GeometryNodeAttributeDomainSize', component='MESH')
    link(st, ecount.inputs['Geometry'])
    has_e = math_('GREATER_THAN', ecount.outputs['Edge Count'], 0.0)
    dist = switch('FLOAT', has_e, spp.outputs['Distance'], sp.outputs['Distance'])
    near = switch('VECTOR', has_e, spp.outputs['Position'], sp.outputs['Position'])
    t = math_('DIVIDE', dist, r)
    nrm = named('.mch_geo_n', 'FLOAT_VECTOR')
    # Standard: a bell (1 - t^2)^2 along the normal;  Clay: a flat top (full inside 0.55 r);  Move: the bell x the drag
    one_m_t2 = math_('MAXIMUM', math_('SUBTRACT', 1.0, math_('MULTIPLY', t, t)), 0.0)
    bell = math_('MULTIPLY', one_m_t2, one_m_t2)
    clay = node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP', clamp=True)
    link(t, clay.inputs['Value'])
    clay.inputs['From Min'].default_value = 1.0
    clay.inputs['From Max'].default_value = 0.55
    std_off = vmath('SCALE', nrm, scale=math_('MULTIPLY', math_('MULTIPLY', bell, strength), math_('MULTIPLY', r, 0.5)))
    clay_off = vmath('SCALE', nrm, scale=math_('MULTIPLY', math_('MULTIPLY', clay.outputs['Result'], strength),
                                               math_('MULTIPLY', r, 0.3)))
    mv_off = vmath('SCALE', mvec, scale=bell)
    # Clay Buildup: the plane = the stroke's mean point + its mean normal x (strength x radius x 0.5); what is below it
    # inside a hard footprint (full to 0.6 r, gone at r, its edge roughened a little) is filled up to it (Alt: dug down)
    pmean = stat(st, pos(), 'FLOAT_VECTOR').outputs['Mean']
    pn = vmath('NORMALIZE', stat(st, named('normal', 'FLOAT_VECTOR'), 'FLOAT_VECTOR').outputs['Mean'])
    target = vmath('ADD', pmean, vmath('SCALE', pn, scale=math_('MULTIPLY', math_('MULTIPLY', strength, r), 0.5)))
    below = vmath('DOT_PRODUCT', vmath('SUBTRACT', target, pos()), pn)
    noise = node('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 9.0
    noise.inputs['Detail'].default_value = 4.0
    rough_t = math_('ADD', t, math_('MULTIPLY', math_('SUBTRACT', noise.outputs['Fac'], 0.5), 0.08))
    foot = node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP', clamp=True)
    link(rough_t, foot.inputs['Value'])
    foot.inputs['From Min'].default_value = 1.0
    foot.inputs['From Max'].default_value = 0.6
    sgn = math_('SIGN', strength)
    fill = math_('MULTIPLY', math_('MULTIPLY', math_('MAXIMUM', math_('MULTIPLY', below, sgn), 0.0), sgn), foot.outputs['Result'])
    bld_off = vmath('SCALE', pn, scale=fill)
    # Flat: one plane per stroke - the mean point and mean normal of the surface under the brush (its whole footprint,
    # like ZBrush's Flatten / Planar).  What stands above it is cut down to it, nothing is filled: stroked along a
    # corner it cuts a flat facet across the corner (the footprint's mean lies inside it), over bumps it trims them.
    # Alt (strength < 0): the plane lifted by |strength| x radius x 0.35 and every point in the footprint goes to it -
    # a flat pad pops out.
    in_foot = math_('LESS_THAN', t, 1.0)
    fp = node('GeometryNodeAttributeStatistic', data_type='FLOAT_VECTOR', domain='POINT')
    link(cur, fp.inputs['Geometry'])
    link(in_foot, fp.inputs['Selection'])
    link(pos(), fp.inputs['Attribute'])
    fnm = node('GeometryNodeAttributeStatistic', data_type='FLOAT_VECTOR', domain='POINT')
    link(cur, fnm.inputs['Geometry'])
    link(in_foot, fnm.inputs['Selection'])
    link(node('GeometryNodeInputNormal').outputs[0], fnm.inputs['Attribute'])
    fn = vmath('NORMALIZE', fnm.outputs['Mean'])
    alt_flat = math_('LESS_THAN', strength, 0.0)
    lift = math_('MULTIPLY', math_('MULTIPLY', math_('MAXIMUM', math_('MULTIPLY', strength, -1.0), 0.0), r), 0.35)
    flat_plane = vmath('ADD', fp.outputs['Mean'], vmath('SCALE', fn, scale=lift))
    flat_d = vmath('DOT_PRODUCT', vmath('SUBTRACT', flat_plane, pos()), fn)
    flat_move = switch('FLOAT', alt_flat, math_('MINIMUM', flat_d, 0.0), flat_d)        # (cut only / a pad: both ways)
    flat_k = switch('FLOAT', alt_flat, math_('MINIMUM', math_('MULTIPLY', k_abs, 2.0), 1.0), k_abs)
    flat_foot = node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP', clamp=True)
    link(t, flat_foot.inputs['Value'])
    flat_foot.inputs['From Min'].default_value = 1.0
    flat_foot.inputs['From Max'].default_value = 0.85
    flat_off = vmath('SCALE', fn, scale=math_('MULTIPLY', math_('MULTIPLY', flat_move, flat_foot.outputs['Result']), flat_k))
    # Edge Line: L = the nearest point of the line, nL its normal there, fade (0 at the line's ends); h = height over
    # L's tangent plane, s = the distance from the line along it; B = the surface a band's width out on this side.
    # Inside the band each side goes flat (the straight chord L -> B), the line's profile is added (Edge Line: a ridge,
    # Panel Line: a groove) and the points slide sideways onto the crease lines.  The line is resampled finely when it
    # is stored (resample_line) and read between its points, so nL / fade change smoothly along it.
    near_i = node('GeometryNodeSampleNearest', domain='POINT')
    link(st, near_i.inputs['Geometry'])
    # (nL and fade interpolated along the segment the nearest point lies on - read at the nearest stored point alone
    # they stepped point to point: a ripple in the fade at the line's ends)
    def at(value, idx, typ='FLOAT'):
        si = node('GeometryNodeSampleIndex', data_type=typ, domain='POINT', clamp=True)
        link(st, si.inputs['Geometry'])
        link(value, si.inputs['Value'])
        link(idx, si.inputs['Index'])
        return si.outputs['Value']
    i_ = near_i.outputs['Index']
    i_next, i_prev = math_('ADD', i_, 1.0), math_('SUBTRACT', i_, 1.0)
    p_i, p_n, p_p = at(pos(), i_, 'FLOAT_VECTOR'), at(pos(), i_next, 'FLOAT_VECTOR'), at(pos(), i_prev, 'FLOAT_VECTOR')

    def param(p_other):
        seg = vmath('SUBTRACT', p_other, p_i)
        return math_('DIVIDE', vmath('DOT_PRODUCT', vmath('SUBTRACT', near, p_i), seg),
                     math_('MAXIMUM', vmath('DOT_PRODUCT', seg, seg), 1e-12))
    u_n, u_p = param(p_n), param(p_p)
    fwd = math_('GREATER_THAN', u_n, u_p)
    u = math_('MINIMUM', math_('MAXIMUM', switch('FLOAT', fwd, u_p, u_n), 0.0), 1.0)
    f_i, f_o = at(named('fade'), i_), switch('FLOAT', fwd, at(named('fade'), i_prev), at(named('fade'), i_next))
    fade = math_('ADD', f_i, math_('MULTIPLY', math_('SUBTRACT', f_o, f_i), u))
    n_i = at(named('normal', 'FLOAT_VECTOR'), i_, 'FLOAT_VECTOR')
    n_o = switch('VECTOR', fwd, at(named('normal', 'FLOAT_VECTOR'), i_prev, 'FLOAT_VECTOR'),
                 at(named('normal', 'FLOAT_VECTOR'), i_next, 'FLOAT_VECTOR'))
    nl = vmath('NORMALIZE', vmath('ADD', n_i, vmath('SCALE', vmath('SUBTRACT', n_o, n_i), scale=u)))
    d = vmath('SUBTRACT', pos(), near)
    h = vmath('DOT_PRODUCT', d, nl)
    svec = vmath('SUBTRACT', d, vmath('SCALE', nl, scale=h))
    s_len = vmath('LENGTH', svec)
    sdir = vmath('NORMALIZE', svec)
    bpos = vmath('ADD', near, vmath('SCALE', sdir, scale=r))
    surf = node('GeometryNodeSampleNearestSurface', data_type='FLOAT_VECTOR')
    link(cur, surf.inputs['Mesh'])
    link(pos(), surf.inputs['Value'])
    link(bpos, surf.inputs['Sample Position'])
    db = vmath('SUBTRACT', surf.outputs['Value'], near)
    hb = vmath('DOT_PRODUCT', db, nl)
    sb = math_('MAXIMUM', vmath('LENGTH', vmath('SUBTRACT', db, vmath('SCALE', nl, scale=hb))), 1e-7)
    slope = math_('DIVIDE', hb, sb)                          # the chord L -> B: height per unit out from the line
    inband = math_('LESS_THAN', t, 1.0)
    u = math_('MINIMUM', t, 1.0)
    sgn = math_('SIGN', strength)
    k_abs2 = math_('ABSOLUTE', strength)
    is_panel = math_('COMPARE', k, float(KIND['PANEL']), 0.1)
    # the points slide sideways so they crowd on the crease lines (zero slope there: ZBrush's pinch) - the edge runs
    # along the drawn line itself, not between grid points.  Edge Line: creases at the line and the band's edge;
    # Panel Line: at the groove's floor edge (PANEL_FLOOR x r) and the band's edge.
    # (Edge Line: s' = r u^2 (2 - u) - crowded at the line, even again at the band's edge: the edge is the line, the
    # surface flows back into its own curve outward; Panel Line: crowded at its floor edge and at the shoulder)
    edge_s = math_('MULTIPLY', math_('MULTIPLY', math_('MULTIPLY', u, u), math_('SUBTRACT', 2.0, u)), r)
    a_ = PANEL_FLOOR
    v_ = math_('MINIMUM', math_('DIVIDE', u, a_), 1.0)
    inner = math_('MULTIPLY', math_('MULTIPLY', r, a_), math_('SUBTRACT', math_('MULTIPLY', v_, 2.0), math_('MULTIPLY', v_, v_)))
    sm2 = node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP', clamp=True)
    link(u, sm2.inputs['Value'])
    sm2.inputs['From Min'].default_value = a_
    sm2.inputs['From Max'].default_value = 1.0
    outer = math_('MULTIPLY', r, math_('ADD', a_, math_('MULTIPLY', 1.0 - a_, sm2.outputs['Result'])))
    panel_s = switch('FLOAT', math_('LESS_THAN', u, a_), outer, inner)
    s_new0 = switch('FLOAT', is_panel, edge_s, panel_s)
    s_new = math_('ADD', s_len, math_('MULTIPLY', math_('SUBTRACT', s_new0, s_len), fade))
    un = math_('DIVIDE', s_new, r)
    # the heights: both sides flat (the chord) + Edge Line: the line lifted (Alt: pressed in) |k| x r x 0.3, falling
    # straight to the band's edge;  Panel Line: a groove |k| x r x 0.5 deep, flat floor, straight walls (Alt: a rib)
    ridge = math_('MULTIPLY', math_('MULTIPLY', math_('MULTIPLY', sgn, k_abs2), math_('MULTIPLY', r, 0.3)),
                  math_('MAXIMUM', math_('SUBTRACT', 1.0, un), 0.0))
    wall = math_('MINIMUM', math_('DIVIDE', math_('MAXIMUM', math_('SUBTRACT', 1.0, un), 0.0), 1.0 - a_), 1.0)
    groove = math_('MULTIPLY', math_('MULTIPLY', math_('MULTIPLY', sgn, k_abs2), math_('MULTIPLY', r, -0.5)), wall)
    prof = switch('FLOAT', is_panel, ridge, groove)
    h_new = math_('ADD', math_('MULTIPLY', slope, s_new), prof)
    # Edge Line: full inside EDGE_FULL of the band, blending back to the surface's own height out to the band's edge
    # (no seam where the band ends);  Panel Line: full to its shoulder.  (h + slope x the sideways slide: the
    # surface's height where the point now is)
    blend_out = node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP', clamp=True)
    link(u, blend_out.inputs['Value'])
    blend_out.inputs['From Min'].default_value = 1.0
    blend_out.inputs['From Max'].default_value = EDGE_FULL
    w_in = switch('FLOAT', is_panel, blend_out.outputs['Result'], 1.0)
    h_here = math_('ADD', h, math_('MULTIPLY', slope, math_('SUBTRACT', s_new, s_len)))
    h_fin = math_('ADD', h_here, math_('MULTIPLY', math_('SUBTRACT', h_new, h_here), math_('MULTIPLY', fade, w_in)))
    target = vmath('ADD', vmath('ADD', near, vmath('SCALE', nl, scale=h_fin)), vmath('SCALE', sdir, scale=s_new))
    edge_off = vmath('SCALE', vmath('SUBTRACT', target, pos()), scale=inband)
    pick = node('GeometryNodeIndexSwitch', data_type='VECTOR')
    while len(pick.index_switch_items) < 8:
        pick.index_switch_items.new()
    link(math_('ROUND', k), pick.inputs['Index'])
    for i, off in ((0, std_off), (1, clay_off), (2, mv_off), (3, bld_off), (5, flat_off), (6, edge_off), (7, edge_off)):
        link(off, pick.inputs[i + 1])
    # a Flat cut (or pad top) is a plane: the points put on it are flagged and faces all on it are shaded flat, so the
    # facet reads crisp; a later stroke that moves a point (any other brush) clears its flag
    is_flat_k = math_('COMPARE', k, float(KIND['FLAT']), 0.1)
    full_w = math_('GREATER_THAN', flat_foot.outputs['Result'], 0.999)
    on_plane = bool_('AND', bool_('AND', is_flat_k, full_w),
                     bool_('OR', alt_flat, math_('LESS_THAN', flat_d, -1e-6)))
    smooth_k = math_('COMPARE', k, float(KIND['SMOOTH']), 0.1)
    moved = math_('GREATER_THAN', vmath('LENGTH', pick.outputs['Output']), 1e-7)
    moved_other = bool_('AND', bool_('NOT', is_flat_k), bool_('OR', moved, smooth_k))
    flag = node('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='POINT')
    flag.inputs['Name'].default_value = '.mch_geo_flat'
    link(cur, flag.inputs['Geometry'])
    link(switch('FLOAT', moved_other, math_('MAXIMUM', named('.mch_geo_flat'), on_plane), 0.0), flag.inputs['Value'])
    cur = flag.outputs['Geometry']
    setp = node('GeometryNodeSetPosition')
    link(cur, setp.inputs['Geometry'])
    link(pick.outputs['Output'], setp.inputs['Offset'])
    # Smooth: positions blurred (more passes for a bigger brush / finer Detail), mixed in by the bell
    blur = node('GeometryNodeBlurAttribute', data_type='FLOAT_VECTOR')
    link(pos(), blur.inputs['Value'])
    ratio = math_('DIVIDE', r, detail)
    link(math_('MINIMUM', math_('MAXIMUM', math_('ROUND', math_('MULTIPLY', math_('MULTIPLY', ratio, ratio), 0.5)), 4.0), 80.0),
         blur.inputs['Iterations'])
    sm_off = vmath('SCALE', vmath('SUBTRACT', blur.outputs['Value'], pos()), scale=math_('MULTIPLY', bell, k_abs))
    setp_s = node('GeometryNodeSetPosition')
    link(cur, setp_s.inputs['Geometry'])
    link(sm_off, setp_s.inputs['Offset'])
    done = switch('GEOMETRY', math_('COMPARE', k, 4.0, 0.1), setp.outputs['Geometry'], setp_s.outputs['Geometry'])
    link(done, rout.inputs['Geometry'])
    link(math_('ADD', rin.outputs['Index'], 1.0), rout.inputs['Index'])
    geo = rout.outputs['Geometry']
    smooth = node('GeometryNodeSetShadeSmooth', domain='FACE')
    link(geo, smooth.inputs['Geometry'])
    # (Edge / Panel Line bands are not shaded flat: the points crowded on a line's creases make the smooth shading
    # crisp there.  A Flat brush's facets are: all their points lie on its plane)
    flat_face = node('GeometryNodeFieldOnDomain', domain='FACE', data_type='FLOAT')
    link(named('.mch_geo_flat'), flat_face.inputs[0])
    link(math_('LESS_THAN', flat_face.outputs[0], 0.999), smooth.inputs['Shade Smooth'])
    sharp = node('GeometryNodeSetShadeSmooth', domain='EDGE')
    link(smooth.outputs['Geometry'], sharp.inputs['Geometry'])
    link(bool_('NOT', named('.mch_geo_hard', 'BOOLEAN')), sharp.inputs['Shade Smooth'])
    join = node('GeometryNodeJoinGeometry')
    link(sharp.outputs['Geometry'], join.inputs[0])
    link(rest, join.inputs[0])
    merge = node('GeometryNodeMergeByDistance')
    merge.inputs['Distance'].default_value = 1e-5
    link(join.outputs['Geometry'], merge.inputs['Geometry'])
    drop = node('GeometryNodeRemoveAttribute')
    link(merge.outputs['Geometry'], drop.inputs['Geometry'])
    drop.inputs['Name'].default_value = '.mch_geo_n'
    drop2 = node('GeometryNodeRemoveAttribute')
    link(drop.outputs['Geometry'], drop2.inputs['Geometry'])
    drop2.inputs['Name'].default_value = '.mch_geo_hard'
    last = drop2.outputs['Geometry']
    for name in ('.mch_geo_flat', '.mch_geo_sel', '.mch_geo_selp', '.mch_geo_b'):
        dr = node('GeometryNodeRemoveAttribute')
        link(last, dr.inputs['Geometry'])
        dr.inputs['Name'].default_value = name
        last = dr.outputs['Geometry']
    link(last, go.inputs['Geometry'])
    return ng


def _socket_ident(ng, name):
    return next(it.identifier for it in ng.interface.items_tree
                if getattr(it, 'name', '') == name and getattr(it, 'in_out', '') == 'INPUT')


def _input(mod, name):
    """(the modifier's input holder, 'value') for ``name`` - Blender 5.2's GN modifier inputs."""
    ident = _socket_ident(mod.node_group, name)
    try:
        return getattr(mod.properties.inputs, ident), 'value'
    except AttributeError:
        return mod, f'["{ident}"]'


def get_input(mod, name):
    holder, prop = _input(mod, name)
    return getattr(holder, prop) if prop == 'value' else mod[_socket_ident(mod.node_group, name)]


def set_input(mod, name, value):
    holder, prop = _input(mod, name)
    if prop == 'value':
        holder.value = value
    else:
        mod[_socket_ident(mod.node_group, name)] = value


# -----------------------------------------------------------------------------
# the layer on a part
# -----------------------------------------------------------------------------

def layer(ob):
    """The part's Geo Sculpt modifier (or None)."""
    mod = getattr(ob, 'modifiers', {}).get(MOD) if ob is not None else None
    return mod if mod is not None and mod.type == 'NODES' else None


def strokes_of(ob):
    mod = layer(ob)
    if mod is None or mod.node_group is None:
        return None
    try:
        return get_input(mod, 'Strokes')
    except (StopIteration, AttributeError, KeyError):
        return None


def _mean_scale(ob):
    s = ob.matrix_world.to_scale()
    return max((abs(s.x) + abs(s.y) + abs(s.z)) / 3.0, 1e-9)


def default_detail(ob):
    """Detail (local units) for a new layer: the part's size / 160."""
    try:
        dims = [d / max(abs(s), 1e-9) for d, s in zip(ob.dimensions, ob.matrix_world.to_scale())]
    except (AttributeError, TypeError):
        dims = [1.0]
    return max(max(dims) / 160.0, 1e-4)


def _place_after_bevels(ob):
    mods = list(ob.modifiers)
    names = [m.name for m in mods]
    if MOD not in names:
        return
    want = max([names.index(n) for n in BEVEL_MODS.values() if n in names] + [-1]) + 1
    have = names.index(MOD)
    if have < want:
        try:
            ob.modifiers.move(have, want - 1 if want - 1 > have else want)
        except (RuntimeError, TypeError, AttributeError):
            pass


def ensure_layer(ob):
    """The part's layer + its own stroke object (a copy made when a duplicate still shares its original's)."""
    mod = layer(ob)
    if mod is None:
        mod = ob.modifiers.new(MOD, 'NODES')
        mod.node_group = node_group()
        set_input(mod, 'Detail', default_detail(ob))
        mod.show_in_editmode = False
    elif mod.node_group is None or mod.node_group.get('mch_ver') != GROUP_VERSION:
        mod.node_group = node_group()
    sob = strokes_of(ob)
    if sob is None or sob.type != 'MESH':
        me = bpy.data.meshes.new(f'{ob.name} (geo strokes)')
        sob = bpy.data.objects.new(f'{ob.name} (geo strokes)', me)     # (not in the scene: only the layer reads it)
        sob[PART_KEY] = ob.name
        set_input(mod, 'Strokes', sob)
    elif sob.get(PART_KEY) != ob.name and any(strokes_of(o) == sob for o in bpy.data.objects
                                              if o != ob and o.get(PART_KEY) is None and layer(o) is not None):
        sob = sob.copy()                                              # a duplicate: its own strokes from now on
        sob.data = sob.data.copy()
        sob.name = sob.data.name = f'{ob.name} (geo strokes)'
        sob[PART_KEY] = ob.name
        set_input(mod, 'Strokes', sob)
    _place_after_bevels(ob)
    return mod, sob


def read_strokes(sob):
    """{'co': (n,3), 'edges': (m,2), attr: array} of the stroke mesh."""
    me = sob.data
    n = len(me.vertices)
    out = {'co': np.zeros((n, 3), np.float32), 'edges': np.zeros((len(me.edges), 2), np.int32)}
    if n:
        me.vertices.foreach_get('co', out['co'].ravel())
    if len(me.edges):
        me.edges.foreach_get('vertices', out['edges'].ravel())
    for name, typ in POINT_ATTRS:
        width = 3 if typ == 'FLOAT_VECTOR' else 1
        arr = np.zeros(n * width, np.int32 if typ == 'INT' else np.float32)
        a = me.attributes.get(name)
        if a is not None and n:
            a.data.foreach_get('vector' if width == 3 else 'value', arr)
        elif name == 'fade':
            arr[:] = 1.0
        out[name] = arr.reshape(n, 3) if width == 3 else arr
    return out


def write_strokes(sob, data):
    me = sob.data
    me.clear_geometry()
    co = np.asarray(data['co'], np.float32).reshape(-1, 3)
    edges = np.asarray(data['edges'], np.int32).reshape(-1, 2)
    me.vertices.add(len(co))
    me.edges.add(len(edges))
    if len(co):
        me.vertices.foreach_set('co', co.ravel())
    if len(edges):
        me.edges.foreach_set('vertices', edges.ravel())
    for name, typ in POINT_ATTRS:
        a = me.attributes.get(name) or me.attributes.new(name, typ, 'POINT')
        arr = np.asarray(data[name], np.int32 if typ == 'INT' else np.float32)
        if len(co):
            a.data.foreach_set('vector' if typ == 'FLOAT_VECTOR' else 'value', arr.ravel())
    me.update()


def stroke_count(ob):
    sob = strokes_of(ob)
    if sob is None or not len(sob.data.vertices):
        return 0
    return len(set(read_strokes(sob)['stroke'].tolist()))


def fade_along(pts, radius):
    """0 at a line's ends, 1 from 0.6 radius in (smoothstep): the Edge Line only goes as far as it was drawn."""
    pts = np.asarray(pts, float)
    if len(pts) < 2:
        return np.ones(len(pts), np.float32)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    run = np.concatenate([[0.0], np.cumsum(seg)])
    end = np.minimum(run, run[-1] - run) / max(radius * 0.6, 1e-9)
    x = np.clip(end, 0.0, 1.0)
    return (x * x * (3 - 2 * x)).astype(np.float32)


def resample_line(pts, normals, step):
    """A polyline at even ``step`` spacing, its normals interpolated (an Edge Line's nearest point / normal / fade
    are read at its nearest STORED point: finely spaced, they change smoothly - no ripples across the band)."""
    pts = np.asarray(pts, float).reshape(-1, 3)
    normals = np.asarray(normals, float).reshape(-1, 3)
    if len(pts) < 2:
        return pts, normals
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    run = np.concatenate([[0.0], np.cumsum(seg)])
    total = run[-1]
    if total <= 0:
        return pts[:1], normals[:1]
    n = int(min(max(math.ceil(total / max(step, 1e-9)), 1), 4000)) + 1
    at = np.linspace(0.0, total, n)
    out = np.c_[[np.interp(at, run, pts[:, i]) for i in range(3)]].T
    nrm = np.c_[[np.interp(at, run, normals[:, i]) for i in range(3)]].T
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
    return out, nrm


def smooth_normals(normals, half):
    """Normals averaged over +-half points along a line (a hit normal is its triangle's; along a line it jumps from
    facet to facet - the Edge Line's sides would step with it)."""
    n = np.asarray(normals, float).reshape(-1, 3)
    if len(n) < 3 or half < 1:
        return n
    pad = np.vstack([np.repeat(n[:1], half, 0), n, np.repeat(n[-1:], half, 0)])
    c = np.cumsum(np.vstack([np.zeros((1, 3)), pad]), axis=0)
    out = (c[2 * half + 1:] - c[:-(2 * half + 1)]) / (2 * half + 1)
    return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-12)


def append_stroke(data, kind, pts, normals, radius, strength, move=(0.0, 0.0, 0.0)):
    """Adds one stroke to ``data`` (read_strokes' dict); returns its index."""
    if kind in LINE_KINDS:
        pts, normals = resample_line(pts, normals, radius * 0.03)
        normals = smooth_normals(normals, 16)
    pts = np.asarray(pts, np.float32).reshape(-1, 3)
    normals = np.asarray(normals, np.float32).reshape(-1, 3)
    sid = int(data['stroke'].max()) + 1 if len(data['stroke']) else 0
    base = len(data['co'])
    n = len(pts)
    data['co'] = np.vstack([data['co'], pts])
    if n > 1:
        e = np.c_[np.arange(base, base + n - 1), np.arange(base + 1, base + n)].astype(np.int32)
        data['edges'] = np.vstack([data['edges'], e])
    k = KIND[kind]
    fade = fade_along(pts, radius) if kind in LINE_KINDS else np.ones(n, np.float32)
    for name, vals in (('stroke', np.full(n, sid)), ('radius', np.full(n, radius)), ('strength', np.full(n, strength)),
                       ('kind', np.full(n, k)), ('move', np.tile(np.asarray(move, np.float32), (n, 1))),
                       ('normal', normals), ('fade', fade)):
        data[name] = np.concatenate([data[name], np.asarray(vals, data[name].dtype).reshape((n,) + data[name].shape[1:])])
    return sid


def drop_stroke(data, sid):
    keep = data['stroke'] != sid
    remap = -np.ones(len(keep), np.int64)
    remap[keep] = np.arange(int(keep.sum()))
    out = {k: v[keep] for k, v in data.items() if k not in ('edges',)}
    e = data['edges']
    if len(e):
        ok = keep[e[:, 0]] & keep[e[:, 1]]
        out['edges'] = remap[e[ok]].astype(np.int32)
    else:
        out['edges'] = e
    return out


def add_stroke(ob, kind, pts, normals, radius, strength, move=(0.0, 0.0, 0.0)):
    """A stroke in the part's LOCAL space (points, normals, radius); Chamfer / Round mark edges instead."""
    if kind in BEVEL_MODS:
        return mark_bevel(ob, kind, pts, radius, remove=strength < 0)
    _mod, sob = ensure_layer(ob)
    data = read_strokes(sob)
    sid = append_stroke(data, kind, pts, normals, radius, strength, move)
    write_strokes(sob, data)
    return sid


def undo_last(ob):
    sob = strokes_of(ob)
    if sob is None or not len(sob.data.vertices):
        return False
    data = read_strokes(sob)
    write_strokes(sob, drop_stroke(data, int(data['stroke'].max())))
    return True


# -----------------------------------------------------------------------------
# Chamfer / Round: the part's own hard edges along the stroke, weighted for a Bevel modifier
# -----------------------------------------------------------------------------

def hard_edges(me):
    """Edge indices that are hard: sharp, Edge Memory, or folded more than 30 degrees."""
    n = len(me.edges)
    hard = np.zeros(n, bool)
    for name in ('sharp_edge', 'mch_hard'):
        a = me.attributes.get(name)
        if a is not None and a.domain == 'EDGE' and a.data_type == 'BOOLEAN' and n:
            v = np.zeros(n, bool)
            a.data.foreach_get('value', v)
            hard |= v
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.edges.ensure_lookup_table()
    for e in bm.edges:
        if len(e.link_faces) == 2:
            try:
                if e.calc_face_angle() > HARD_ANGLE:
                    hard[e.index] = True
            except ValueError:
                pass
    bm.free()
    return hard


def edges_along(me, pts, radius):
    """The hard edges a stroke runs along: near it (within 0.7 radius) at two or more stroke points, the stroke going
    the edge's way there (not just crossing it)."""
    pts = np.asarray(pts, float).reshape(-1, 3)
    if not len(me.edges) or not len(pts):
        return []
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    ev = np.zeros(len(me.edges) * 2, np.int64)
    me.edges.foreach_get('vertices', ev)
    ev = ev.reshape(-1, 2)
    a, b = co[ev[:, 0]], co[ev[:, 1]]
    d = b - a
    dd = np.maximum((d * d).sum(1), 1e-18)
    if len(pts) > 1:
        tan = np.gradient(pts, axis=0)
        tan /= np.maximum(np.linalg.norm(tan, axis=1, keepdims=True), 1e-12)
    else:
        tan = None
    hard = hard_edges(me)
    out = []
    for i in np.nonzero(hard)[0]:
        tt = np.clip(((pts - a[i]) * d[i]).sum(1) / dd[i], 0.0, 1.0)
        dist = np.linalg.norm(a[i] + tt[:, None] * d[i] - pts, axis=1)
        near = (dist < radius * 0.7) & (tt > 1e-3) & (tt < 1 - 1e-3)
        if tan is None:
            if near.any():
                out.append(int(i))
            continue
        if near.sum() < 2:
            continue
        cos = np.abs((tan[near] * (d[i] / math.sqrt(dd[i]))).sum(1))
        if (cos > 0.6).mean() >= 0.5:
            out.append(int(i))
    return out


def _bevel_mod(ob, kind):
    name = BEVEL_MODS[kind]
    mod = ob.modifiers.get(name)
    if mod is None:
        mod = ob.modifiers.new(name, 'BEVEL')
        mod.limit_method = 'WEIGHT'
        mod.edge_weight = BEVEL_ATTR[kind]
        mod.segments = 1 if kind == 'CHAMFER' else ROUND_SEGMENTS
        mod.profile = 0.5
        mod.harden_normals = False
        mod.miter_outer = 'MITER_ARC' if kind == 'ROUND' else 'MITER_SHARP'
        # before the sculpt layer (the layer sculpts the bevelled surface) and before anything the part already had
        # after its base (mirror, light copy ...): first in the stack, chamfer before round
        idx = 1 if kind == 'ROUND' and ob.modifiers.get(CHAMFER_MOD) is not None else 0
        try:
            ob.modifiers.move(len(ob.modifiers) - 1, idx)
        except (RuntimeError, TypeError, AttributeError):
            pass
    return mod


def _sync_bevel(ob, kind):
    """The drawn widths ('<attr>_w') as weights 0..1 on the modifier's attribute, the modifier width = the widest."""
    me = ob.data
    raw = me.attributes.get(BEVEL_ATTR[kind] + '_w')
    w = np.zeros(len(me.edges), np.float32)
    if raw is not None and len(me.edges):
        raw.data.foreach_get('value', w)
    wmax = float(w.max()) if len(w) else 0.0
    a = me.attributes.get(BEVEL_ATTR[kind]) or me.attributes.new(BEVEL_ATTR[kind], 'FLOAT', 'EDGE')
    if len(me.edges):
        a.data.foreach_set('value', (w / wmax) if wmax > 0 else w)
    mod = ob.modifiers.get(BEVEL_MODS[kind])
    if wmax <= 0:
        if mod is not None:
            ob.modifiers.remove(mod)
        for name in (BEVEL_ATTR[kind], BEVEL_ATTR[kind] + '_w'):
            at = me.attributes.get(name)
            if at is not None:
                me.attributes.remove(at)
        return None
    mod = _bevel_mod(ob, kind)
    mod.width = wmax
    _place_after_bevels(ob)
    return mod


def mark_bevel(ob, kind, pts, radius, remove=False):
    """Chamfer / Round the part's hard edges along a stroke (local space) as wide as ``radius``; remove: taken off
    (both kinds).  Returns the number of edges changed."""
    me = ob.data
    idx = edges_along(me, pts, radius)
    if not idx:
        return 0
    kinds = tuple(BEVEL_MODS) if remove else (kind,)
    for kd in kinds:
        name = BEVEL_ATTR[kd] + '_w'
        raw = me.attributes.get(name) or me.attributes.new(name, 'FLOAT', 'EDGE')
        w = np.zeros(len(me.edges), np.float32)
        raw.data.foreach_get('value', w)
        if remove:
            w[idx] = 0.0
        else:
            w[idx] = radius
        raw.data.foreach_set('value', w)
    if not remove:                                    # an edge is either chamfered or rounded
        other = 'ROUND' if kind == 'CHAMFER' else 'CHAMFER'
        o = me.attributes.get(BEVEL_ATTR[other] + '_w')
        if o is not None:
            w = np.zeros(len(me.edges), np.float32)
            o.data.foreach_get('value', w)
            w[idx] = 0.0
            o.data.foreach_set('value', w)
        kinds = (kind, other)
    for kd in kinds:
        _sync_bevel(ob, kd)
    me.update()
    return len(idx)


# -----------------------------------------------------------------------------
# Apply / Clear
# -----------------------------------------------------------------------------

def has_any(ob):
    return ob is not None and (layer(ob) is not None or any(ob.modifiers.get(n) for n in BEVEL_MODS.values()))


def weld_t_junctions(bm, eps=1e-6):
    """Open edges with another open edge's vertex lying on them (the subdivided region beside the untouched rest)
    are split there and welded: the part is closed again."""
    for _round in range(4):
        bm.verts.ensure_lookup_table()
        open_e = [e for e in bm.edges if len(e.link_faces) == 1]
        if not open_e:
            return 0
        ov = list({v for e in open_e for v in e.verts})
        if not ov:
            return 0
        co = np.array([v.co for v in ov])
        splits = 0
        for e in open_e:
            a, b = e.verts[0].co, e.verts[1].co
            d = np.array(b - a)
            dd = float(d @ d)
            if dd < 1e-20:
                continue
            tt = ((co - np.array(a)) @ d) / dd
            near = np.linalg.norm(np.array(a) + np.outer(tt, d) - co, axis=1)
            idx = np.nonzero((tt > 1e-6) & (tt < 1 - 1e-6) & (near < eps * max(math.sqrt(dd), 1.0) * 1e3))[0]
            if not len(idx):
                continue
            order = idx[np.argsort(tt[idx])]
            cur_e, cur_a, t0 = e, e.verts[0], 0.0
            for j in order:
                f = (tt[j] - t0) / (1.0 - t0)
                ne, nv = bmesh.utils.edge_split(cur_e, cur_a, f)
                nv.co = ov[j].co.copy()
                t0 = tt[j]
                cur_a = nv
                cur_e = ne if nv in ne.verts and e.verts[1] in ne.verts else cur_e
                splits += 1
        if not splits:
            return 0
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=eps * 10)
    return 1


def apply(context, ob):
    """Bakes the bevels + the layer into the part (in stack order), welds the region's seam, drops the strokes."""
    from . import core_geometry as cg
    sob = strokes_of(ob)
    names = [m.name for m in ob.modifiers if m.name in (CHAMFER_MOD, ROUND_MOD, MOD)]
    for name in names:
        mod = ob.modifiers.get(name)
        if mod is not None:
            cg.apply_single_modifier(context, ob, mod)
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    weld_t_junctions(bm)
    bm.to_mesh(me)
    bm.free()
    for kd in BEVEL_MODS:
        for name in (BEVEL_ATTR[kd], BEVEL_ATTR[kd] + '_w'):
            a = me.attributes.get(name)
            if a is not None:
                me.attributes.remove(a)
    me.update()
    _drop_strokes(sob)
    return len(names)


def _drop_strokes(sob):
    if sob is None:
        return
    if any(strokes_of(o) == sob for o in bpy.data.objects if o != sob):
        return
    me = sob.data
    try:
        bpy.data.objects.remove(sob)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
    except (ReferenceError, RuntimeError):
        pass


def clear(ob):
    """Every stroke and bevel off the part (nothing of it was ever written into the part's mesh)."""
    sob = strokes_of(ob)
    mod = layer(ob)
    if mod is not None:
        ob.modifiers.remove(mod)
    _drop_strokes(sob)
    me = ob.data
    for kd in BEVEL_MODS:
        m = ob.modifiers.get(BEVEL_MODS[kd])
        if m is not None:
            ob.modifiers.remove(m)
        for name in (BEVEL_ATTR[kd], BEVEL_ATTR[kd] + '_w'):
            a = me.attributes.get(name)
            if a is not None:
                me.attributes.remove(a)
    me.update()


# -----------------------------------------------------------------------------
# the mouse: cast onto the part, the brush radius
# -----------------------------------------------------------------------------

def px_per_world(region, rv3d, at):
    from bpy_extras import view3d_utils
    c = view3d_utils.location_3d_to_region_2d(region, rv3d, at)
    if c is None:
        return 100.0
    a = view3d_utils.region_2d_to_location_3d(region, rv3d, c, at)
    b = view3d_utils.region_2d_to_location_3d(region, rv3d, (c[0] + 100.0, c[1]), at)
    return 100.0 / max((a - b).length, 1e-9)


def pick_part(context, xy):
    """(object, world hit, world normal) under the mouse - a mesh part - or None."""
    from bpy_extras import view3d_utils
    region, rv3d = context.region, context.region_data
    if region is None or rv3d is None:
        return None
    o = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
    d = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy)
    try:
        hit, loc, nrm, _i, ob, _m = context.scene.ray_cast(context.evaluated_depsgraph_get(), o, d)
    except (RuntimeError, AttributeError, TypeError):
        return None
    if not hit or ob is None:
        return None
    ob = getattr(ob, 'original', ob)
    if ob.type != 'MESH' or ob.get(PART_KEY) is not None:
        return None
    return ob, loc, nrm


class SurfaceCaster:
    """The part as it is when a stroke starts (its layer included, without the light copy), in its local space."""

    def __init__(self, context, ob):
        from . import light_copies
        self.ob = ob
        self.mw = ob.matrix_world.copy()
        self.mi = self.mw.inverted_safe()
        dg = context.evaluated_depsgraph_get()
        ev = light_copies.full(ob, dg)
        me = ev.to_mesh()
        try:
            verts = [v.co.copy() for v in me.vertices]
            polys = [tuple(p.vertices) for p in me.polygons]
        finally:
            ev.to_mesh_clear()
        self.bvh = BVHTree.FromPolygons(verts, polys) if polys else None

    def cast(self, context, xy):
        from bpy_extras import view3d_utils
        if self.bvh is None:
            return None
        region, rv3d = context.region, context.region_data
        o = self.mi @ view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
        d = (self.mi.to_3x3() @ view3d_utils.region_2d_to_vector_3d(region, rv3d, xy)).normalized()
        loc, nrm, _i, _dist = self.bvh.ray_cast(o, d)
        if loc is None:
            return None
        return loc, nrm.normalized()

    def nearest(self, p):
        if self.bvh is None:
            return None
        loc, nrm, _i, _d = self.bvh.find_nearest(Vector(p))
        return (loc, nrm.normalized()) if loc is not None else None


def smooth_line(pts, caster, passes=2):
    """A drawn line's hand jitter evened out lightly (it should follow the line as drawn), its ends kept, back onto
    the surface."""
    p = np.asarray(pts, float)
    if len(p) < 3:
        return p, None
    for _ in range(passes):
        q = p.copy()
        q[1:-1] = 0.25 * p[:-2] + 0.5 * p[1:-1] + 0.25 * p[2:]
        p = q
    out, nrm = [], []
    for x in p:
        hit = caster.nearest(x) if caster is not None else None
        if hit is None:
            out.append(x)
            nrm.append((0.0, 0.0, 1.0))
        else:
            out.append(tuple(hit[0]))
            nrm.append(tuple(hit[1]))
    return np.asarray(out), np.asarray(nrm)


# -----------------------------------------------------------------------------
# operators
# -----------------------------------------------------------------------------

def _hover(context):
    wm = context.window_manager
    return tuple(getattr(wm, 'mch_ui_hover', (-1.0, -1.0)))


def tool_active(context):
    from . import tool_state as ts
    try:
        return ts.effective_tool(context) == 'GSCULPT'
    except (AttributeError, KeyError, TypeError):
        return False


def _circle(cx, cy, r, colour, width=2.0, dashed=False):
    from . import ui_gpu as ug
    pts = ug.circle_pts(cx, cy, r, n=64)
    if dashed:
        segs = []
        for i in range(0, len(pts) - 1, 2):
            segs.append((pts[i], pts[i + 1]))
        ug.lines(segs, colour, width)
    else:
        ug.polyline(pts, colour, width, closed=True)


def draw_cursor():
    """The brush circle at the mouse while the Geo Sculpt tool is on (its colour = the brush)."""
    context = bpy.context
    try:
        if not tool_active(context) or context.region is None or context.region.type != 'WINDOW':
            return
        st = settings(context)
        if st is None or MCH_OT_geo_size.RUNNING[0] or MCH_OT_geo_stroke.RUNNING[0]:
            return
        x, y = _hover(context)
        if x < 0:
            return
        _circle(x, y, st.size_px, BRUSH_COLOUR.get(st.brush, (1, 1, 1, 0.9)), 1.5)
    except (ReferenceError, AttributeError, RuntimeError):
        pass


def _draw_stroke(op, context):
    try:
        if context.region is None or context.region != op.region:
            return
        st = settings(context)
        x, y = op.mouse
        col = BRUSH_COLOUR.get(op.brush, (1, 1, 1, 0.9))
        _circle(x, y, op.r_px, col, 2.0, dashed=op.invert)
        if op.brush in ('EDGE', 'PANEL', 'CHAMFER', 'ROUND') and len(op.screen) > 1:
            from . import ui_gpu as ug
            ug.polyline(op.screen, col, 2.0)
        del st
    except (ReferenceError, AttributeError, RuntimeError):
        pass


class MCH_OT_geo_stroke(bpy.types.Operator):
    """Geo Sculpt stroke: drag on a part with the brush (Alt: invert, Shift: Smooth).  The part's mesh is not touched
    - the sculpt lives in its Geo Sculpt layer until Apply"""
    bl_idname = 'mch.geo_stroke'
    bl_label = 'Geo Sculpt Stroke'
    bl_options = {'REGISTER', 'UNDO'}
    RUNNING = [None]

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'

    def invoke(self, context, event):
        st = settings(context)
        xy = (event.mouse_region_x, event.mouse_region_y)
        hit = pick_part(context, xy)
        if st is None or hit is None:
            return {'PASS_THROUGH'}
        ob, loc, _n = hit
        self.ob = ob
        self.brush = 'SMOOTH' if event.shift and st.brush not in BEVEL_MODS else st.brush
        self.invert = bool(event.alt)
        self.region = context.region
        self.mouse = xy
        self.screen = [xy]
        try:
            self.caster = SurfaceCaster(context, ob)
        except (RuntimeError, AttributeError, ReferenceError):
            return {'PASS_THROUGH'}
        first = self.caster.cast(context, xy)
        if first is None:
            return {'PASS_THROUGH'}
        self.r_px = float(st.size_px)
        ppw = px_per_world(context.region, context.region_data, loc)
        self.radius = (self.r_px / ppw) / _mean_scale(ob)          # local units
        self.strength = st.intensity * (-1.0 if self.invert else 1.0)
        self.pts, self.nrm = [tuple(first[0])], [tuple(first[1])]
        self.grab_world = Vector(loc)
        self.move = Vector((0.0, 0.0, 0.0))
        try:
            context.view_layer.objects.active = ob
            ob.select_set(True)
        except (RuntimeError, ReferenceError):
            pass
        if self.brush not in BEVEL_MODS:
            _mod, self.sob = ensure_layer(ob)
            self.before = read_strokes(self.sob)
        else:
            self.sob, self.before = None, None
        self._live()
        self._handle = bpy.types.SpaceView3D.draw_handler_add(_draw_stroke, (self, context), 'WINDOW', 'POST_PIXEL')
        MCH_OT_geo_stroke.RUNNING[0] = self
        context.window_manager.modal_handler_add(self)
        context.area.header_text_set(f'Geo Sculpt: {dict((b[0], b[1]) for b in BRUSHES)[self.brush]}'
                                     f'{"  (Alt: inverted)" if self.invert else ""}   release = keep, Esc = undo the stroke')
        return {'RUNNING_MODAL'}

    def _spacing(self):
        return self.radius * (0.08 if self.brush in LINE_KINDS else 0.2)

    def _live(self):
        """The stroke so far shown by the layer (Chamfer / Round: on release)."""
        if self.sob is None:
            return
        data = {k: v.copy() for k, v in self.before.items()}
        if self.brush == 'MOVE':
            append_stroke(data, 'MOVE', self.pts[:1], self.nrm[:1], self.radius, 1.0, tuple(self.move))
        else:
            append_stroke(data, self.brush, self.pts, self.nrm, self.radius, self.strength)
        write_strokes(self.sob, data)

    def _end(self, context):
        if getattr(self, '_handle', None) is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            self._handle = None
        MCH_OT_geo_stroke.RUNNING[0] = None
        if context.area:
            context.area.header_text_set(None)
            context.area.tag_redraw()

    def modal(self, context, event):
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            xy = (event.mouse_region_x, event.mouse_region_y)
            self.mouse = xy
            if self.brush == 'MOVE':
                from bpy_extras import view3d_utils
                w = view3d_utils.region_2d_to_location_3d(context.region, context.region_data, xy, self.grab_world)
                self.move = self.caster.mi.to_3x3() @ (w - self.grab_world)
                self._live()
            else:
                hit = self.caster.cast(context, xy)
                if hit is not None and (Vector(hit[0]) - Vector(self.pts[-1])).length >= self._spacing():
                    self.pts.append(tuple(hit[0]))
                    self.nrm.append(tuple(hit[1]))
                    self.screen.append(xy)
                    self._live()
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            return self._finish(context)
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            if self.sob is not None:
                write_strokes(self.sob, self.before)
            self._end(context)
            return {'CANCELLED'}
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM', 'NDOF_MOTION'}:
            return {'PASS_THROUGH'}
        return {'RUNNING_MODAL'}

    def _finish(self, context):
        self._end(context)
        if self.brush in BEVEL_MODS:
            n = mark_bevel(self.ob, self.brush, self.pts, self.radius, remove=self.invert)
            if not n:
                self.report({'INFO'}, 'No hard edge along that stroke (stroke along an edge of the part)')
                return {'CANCELLED'}
            return {'FINISHED'}
        if self.brush in LINE_KINDS and len(self.pts) >= 3:
            p, n = smooth_line(self.pts, self.caster)
            self.pts, self.nrm = [tuple(x) for x in p], [tuple(x) for x in n]
        self._live()
        return {'FINISHED'}


class MCH_OT_geo_size(bpy.types.Operator):
    """S: Draw Size at the cursor (like ZBrush) - move the mouse left / right; click / S / Enter = keep, right click /
    Esc = back.  U: Intensity the same way"""
    bl_idname = 'mch.geo_size'
    bl_label = 'Geo Sculpt Draw Size'
    bl_options = {'INTERNAL'}
    target: EnumProperty(items=[('SIZE', 'Draw Size', ''), ('INTENSITY', 'Intensity', '')], default='SIZE',
                         options={'SKIP_SAVE'})
    RUNNING = [None]

    def invoke(self, context, event):
        st = settings(context)
        if st is None or context.area is None or context.area.type != 'VIEW_3D':
            return {'PASS_THROUGH'}
        self.region = context.region
        self.at = (event.mouse_region_x, event.mouse_region_y)
        self.x0 = event.mouse_region_x
        self.start = (st.size_px, st.intensity)
        self._handle = bpy.types.SpaceView3D.draw_handler_add(_draw_size, (self, context), 'WINDOW', 'POST_PIXEL')
        MCH_OT_geo_size.RUNNING[0] = self
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def value_for(self, x):
        size0, k0 = self.start
        dx = x - self.x0
        if self.target == 'SIZE':
            return int(min(max(round(size0 * math.exp(dx * 0.006)), 3), 1200))
        return float(min(max(k0 + dx * 0.004, 0.01), 2.0))

    def _end(self, context):
        if self._handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            self._handle = None
        MCH_OT_geo_size.RUNNING[0] = None
        if context.area:
            context.area.tag_redraw()

    def modal(self, context, event):
        st = settings(context)
        if event.type == 'MOUSEMOVE':
            v = self.value_for(event.mouse_region_x)
            if self.target == 'SIZE':
                st.size_px = v
            else:
                st.intensity = v
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}
        if event.value == 'PRESS' and event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER', 'SPACE', 'S', 'U'}:
            self._end(context)
            return {'FINISHED'}
        if event.value == 'PRESS' and event.type in {'RIGHTMOUSE', 'ESC'}:
            st.size_px, st.intensity = self.start
            self._end(context)
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}


def _draw_size(op, context):
    """The ZBrush-like popup at the cursor: Draw Size / Intensity sliders (the one being set lit), the brush circle."""
    from . import ui_gpu as ug
    try:
        if context.region != op.region:
            return
        st = settings(context)
        x, y = op.at
        _circle(x, y, st.size_px, BRUSH_COLOUR.get(st.brush, (1, 1, 1, 0.9)), 2.0)
        w, h = 210.0, 26.0
        bx, by = x + 18.0, y + 30.0
        ug.rounded_rect(bx - 6, by - 6, w + 12, 2 * h + 16, 6.0, (0.08, 0.08, 0.09, 0.92))
        for i, (label, frac, val, key) in enumerate((
                ('Draw Size', min(st.size_px / 500.0, 1.0), f'{st.size_px}', 'SIZE'),
                ('Intensity', min(st.intensity, 1.0), f'{st.intensity:.2f}', 'INTENSITY'))):
            yy = by + (1 - i) * (h + 4)
            on = key == op.target
            ug.rounded_rect(bx, yy, w, h, 4.0, (0.18, 0.18, 0.2, 1.0))
            ug.rounded_rect(bx, yy, max(w * frac, 4.0), h, 4.0, (1.0, 0.55, 0.1, 0.95) if on else (0.4, 0.4, 0.45, 1.0))
            ug.text(bx + 8, yy + h / 2, label, 12, (1, 1, 1, 1))
            ug.text(bx + w - 8, yy + h / 2, val, 12, (1, 1, 1, 1), align='RIGHT')
    except (ReferenceError, AttributeError, RuntimeError):
        pass


class MCH_OT_geo_brush(bpy.types.Operator):
    """Pick a Geo Sculpt brush"""
    bl_idname = 'mch.geo_brush'
    bl_label = 'Geo Sculpt Brush'
    bl_options = {'INTERNAL'}
    brush: EnumProperty(items=[(b[0], b[1], b[2]) for b in BRUSHES], default='STANDARD')

    def execute(self, context):
        settings(context).brush = self.brush
        return {'FINISHED'}


def _target(context):
    ob = context.active_object
    return ob if ob is not None and ob.type == 'MESH' and has_any(ob) else None


class MCH_OT_geo_apply(bpy.types.Operator):
    """Bake the Geo Sculpt (bevels + strokes) into the active part's mesh"""
    bl_idname = 'mch.geo_apply'
    bl_label = 'Apply Geo Sculpt'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _target(context) is not None

    def execute(self, context):
        ob = _target(context)
        try:
            n = apply(context, ob)
        except Exception as ex:        # (a CutError / RuntimeError from the bake: the part is left as it was)
            self.report({'ERROR'}, str(ex).splitlines()[0] if str(ex) else type(ex).__name__)
            return {'CANCELLED'}
        self.report({'INFO'}, f'Geo Sculpt applied to {ob.name} ({n} layer(s))')
        return {'FINISHED'}


class MCH_OT_geo_clear(bpy.types.Operator):
    """Remove every Geo Sculpt stroke and bevel from the active part (its mesh was never changed)"""
    bl_idname = 'mch.geo_clear'
    bl_label = 'Clear Geo Sculpt'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _target(context) is not None

    def execute(self, context):
        clear(_target(context))
        return {'FINISHED'}


class MCH_OT_geo_undo_last(bpy.types.Operator):
    """Remove the active part's last Geo Sculpt stroke"""
    bl_idname = 'mch.geo_undo_last'
    bl_label = 'Undo Last Stroke'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and strokes_of(ob) is not None and len(strokes_of(ob).data.vertices) > 0

    def execute(self, context):
        undo_last(context.active_object)
        return {'FINISHED'}


def _in_tool_header(context):
    region = getattr(context, 'region', None)
    return region is not None and region.type == 'TOOL_HEADER'


class MCH_TOOL_geo_sculpt(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.geo_sculpt'
    bl_label = 'Mecha Geo Sculpt'
    bl_description = ('Sculpt brushes on a plain part (no DynaMesh): Standard, Clay, Clay Buildup, Flat, Move, Smooth, '
                      'Edge Line, Panel Line, Chamfer, Round.\nS: Draw Size, U: Intensity at the cursor.  Alt: invert, '
                      'Shift: Smooth')
    bl_icon = 'ops.sculpt.draw'
    bl_widget = None
    bl_keymap = (
        ('mch.geo_stroke', {'type': 'LEFTMOUSE', 'value': 'PRESS'}, None),
        ('mch.geo_stroke', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'alt': True}, None),
        ('mch.geo_stroke', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'shift': True}, None),
        ('mch.geo_size', {'type': 'S', 'value': 'PRESS'}, {'properties': [('target', 'SIZE')]}),
        ('mch.geo_size', {'type': 'U', 'value': 'PRESS'}, {'properties': [('target', 'INTENSITY')]}),
        ('mch.geo_size', {'type': 'F', 'value': 'PRESS'}, {'properties': [('target', 'SIZE')]}),   # (Blender's key too)
        ('mch.exit_tool', {'type': 'ESC', 'value': 'PRESS'}, None),
    )

    def draw_settings(context, layout, tool):
        if _in_tool_header(context):
            return
        draw(layout, context)


# -----------------------------------------------------------------------------
# the window (side panel)
# -----------------------------------------------------------------------------

HELP = ('Drag on a part.  S: Draw Size, U: Intensity (at the cursor)',
        'Alt: invert (Flat: a raised pad, Panel Line: a rib)  Shift: Smooth',
        'Ctrl+Z: the last stroke back.  The mesh changes only on Apply')


def draw(layout, context):
    st = settings(context)
    if st is None:
        return
    col = layout.column(align=True)
    col.label(text='Brushes')
    for ids in BRUSH_ROWS:
        row = col.row(align=True)
        for b in ids:
            row.prop_enum(st, 'brush', b)
    col = layout.column(align=True)
    col.prop(st, 'size_px', text='Draw Size  (S)')
    col.prop(st, 'intensity', text='Intensity  (U)')
    ob = context.active_object
    mod = layer(ob) if ob is not None else None
    if mod is not None and mod.node_group is not None:
        try:
            holder, prop = _input(mod, 'Detail')
            col.prop(holder, prop, text='Detail')
        except (StopIteration, AttributeError, TypeError):
            pass
    if ob is not None and has_any(ob):
        col = layout.column(align=True)
        col.label(text=f'{ob.name}: {stroke_count(ob)} stroke(s)')
        row = col.row(align=True)
        row.operator('mch.geo_undo_last', text='Undo Last')
        row.operator('mch.geo_clear', text='Clear')
        row.operator('mch.geo_apply', text='Apply')
    col = layout.column(align=True)
    for line in HELP:
        col.label(text=line)


CLASSES = (MCH_PG_GeoSculpt, MCH_OT_geo_stroke, MCH_OT_geo_size, MCH_OT_geo_brush, MCH_OT_geo_apply, MCH_OT_geo_clear,
           MCH_OT_geo_undo_last)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_geo = bpy.props.PointerProperty(type=MCH_PG_GeoSculpt)
    try:
        bpy.utils.register_tool(MCH_TOOL_geo_sculpt, after={'mecha.smart_move'}, group=False)
    except (ValueError, RuntimeError, KeyError):
        try:
            bpy.utils.register_tool(MCH_TOOL_geo_sculpt, separator=True, group=False)
        except (ValueError, RuntimeError):
            pass
    if _CURSOR[0] is None and not bpy.app.background:
        _CURSOR[0] = bpy.types.SpaceView3D.draw_handler_add(draw_cursor, (), 'WINDOW', 'POST_PIXEL')


def unregister():
    if _CURSOR[0] is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_CURSOR[0], 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _CURSOR[0] = None
    try:
        bpy.utils.unregister_tool(MCH_TOOL_geo_sculpt)
    except (ValueError, RuntimeError, KeyError):
        pass
    if hasattr(bpy.types.Scene, 'mch_geo'):
        del bpy.types.Scene.mch_geo
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass

