"""Prototype: a Geometry Nodes 'sculpt layer' on a low-poly part (no DynaMesh): strokes stored as edge chains with
attributes (stroke, radius, strength, kind 0 Standard / 1 Clay / 2 Move, move vector), the region near them subdivided
and displaced, the rest of the mesh untouched."""
import math, os, sys
import bpy, bmesh
import numpy as np
from mathutils import Vector

OUT = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.read_factory_settings(use_empty=True)
S = bpy.context.scene


def node_group():
    ng = bpy.data.node_groups.new('MCH Sculpt Layer', 'GeometryNodeTree')
    io = ng.interface
    io.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    io.new_socket('Strokes', in_out='INPUT', socket_type='NodeSocketObject')
    s = io.new_socket('Detail', in_out='INPUT', socket_type='NodeSocketFloat'); s.default_value = 0.02
    s = io.new_socket('Max Level', in_out='INPUT', socket_type='NodeSocketInt'); s.default_value = 6
    io.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    def node(t, **kw):
        n = N.new(t)
        for k, v in kw.items():
            setattr(n, k, v)
        return n
    def math_(op, a=None, b=None, c=None):
        m = node('ShaderNodeMath', operation=op)
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                m.inputs[i].default_value = v
            else:
                L.new(v, m.inputs[i])
        return m.outputs[0]
    def vmath(op, a=None, b=None, scale=None):
        m = node('ShaderNodeVectorMath', operation=op)
        if a is not None: L.new(a, m.inputs[0])
        if b is not None: L.new(b, m.inputs[1])
        if scale is not None:
            if isinstance(scale, (int, float)):
                m.inputs['Scale'].default_value = scale
            else:
                L.new(scale, m.inputs['Scale'])
        return m
    gi = node('NodeGroupInput'); go = node('NodeGroupOutput')
    info = node('GeometryNodeObjectInfo'); info.transform_space = 'ORIGINAL'
    L.new(gi.outputs['Strokes'], info.inputs['Object'])
    strokes = info.outputs['Geometry']
    pos = node('GeometryNodeInputPosition').outputs[0]
    # --- the region: faces whose centre or a corner is within reach of a stroke ------------------------------------
    rad_attr = node('GeometryNodeInputNamedAttribute', data_type='FLOAT'); rad_attr.inputs['Name'].default_value = 'radius'
    rmax = node('GeometryNodeAttributeStatistic', data_type='FLOAT', domain='POINT')
    L.new(strokes, rmax.inputs['Geometry']); L.new(rad_attr.outputs['Attribute'], rmax.inputs['Attribute'])
    mv_attr = node('GeometryNodeInputNamedAttribute', data_type='FLOAT_VECTOR'); mv_attr.inputs['Name'].default_value = 'move'
    mvlen = vmath('LENGTH', mv_attr.outputs['Attribute'])
    mmax = node('GeometryNodeAttributeStatistic', data_type='FLOAT', domain='POINT')
    L.new(strokes, mmax.inputs['Geometry']); L.new(mvlen.outputs['Value'], mmax.inputs['Attribute'])
    reach = math_('ADD', math_('MULTIPLY', rmax.outputs['Max'], 1.15), mmax.outputs['Max'])
    prox = node('GeometryNodeProximity'); prox.target_element = 'EDGES'
    L.new(strokes, prox.inputs[0])
    proxp = node('GeometryNodeProximity'); proxp.target_element = 'POINTS'
    L.new(strokes, proxp.inputs[0])
    dmin = math_('MINIMUM', prox.outputs['Distance'], proxp.outputs['Distance'])
    near_pt = math_('LESS_THAN', dmin, reach)
    ev_face = node('GeometryNodeFieldOnDomain', domain='FACE', data_type='FLOAT')
    L.new(near_pt, ev_face.inputs[0])
    sel_face = math_('GREATER_THAN', ev_face.outputs[0], 0.0)
    sep = node('GeometryNodeSeparateGeometry', domain='FACE')
    L.new(gi.outputs['Geometry'], sep.inputs['Geometry']); L.new(sel_face, sep.inputs['Selection'])
    region, rest = sep.outputs['Selection'], sep.outputs['Inverted']
    # --- subdivide the region: the level from its longest edge and Detail --------------------------------------------
    ev = node('GeometryNodeInputMeshEdgeVertices')
    elen = vmath('DISTANCE', ev.outputs['Position 1'], ev.outputs['Position 2'])
    emax = node('GeometryNodeAttributeStatistic', data_type='FLOAT', domain='EDGE')
    L.new(region, emax.inputs['Geometry']); L.new(elen.outputs['Value'], emax.inputs['Attribute'])
    lvl = math_('CEIL', math_('LOGARITHM', math_('DIVIDE', emax.outputs['Max'], gi.outputs['Detail']), 2.0))
    lvl = math_('MINIMUM', math_('MAXIMUM', lvl, 0.0), gi.outputs['Max Level'])
    sub = node('GeometryNodeSubdivideMesh')
    L.new(region, sub.inputs['Mesh']); L.new(lvl, sub.inputs['Level'])
    geo = sub.outputs['Mesh']
    # the normal before any move, kept
    keepn = node('GeometryNodeStoreNamedAttribute', data_type='FLOAT_VECTOR', domain='POINT'); keepn.inputs['Name'].default_value = 'mch_n'
    L.new(geo, keepn.inputs['Geometry']); L.new(node('GeometryNodeInputNormal').outputs[0], keepn.inputs['Value'])
    geo = keepn.outputs['Geometry']
    # --- every stroke in turn: its offset added (a repeat zone) ------------------------------------------------------
    sid = node('GeometryNodeInputNamedAttribute', data_type='INT'); sid.inputs['Name'].default_value = 'stroke'
    smax = node('GeometryNodeAttributeStatistic', data_type='FLOAT', domain='POINT')
    L.new(strokes, smax.inputs['Geometry']); L.new(sid.outputs['Attribute'], smax.inputs['Attribute'])
    rin = node('GeometryNodeRepeatInput'); rout = node('GeometryNodeRepeatOutput'); rin.pair_with_output(rout)
    rout.repeat_items.new('INT', 'Index')
    L.new(math_('ADD', smax.outputs['Max'], 1.0), rin.inputs['Iterations'])
    L.new(geo, rin.inputs['Geometry'])
    rin.inputs['Index'].default_value = 0
    # this stroke's points
    sid2 = node('GeometryNodeInputNamedAttribute', data_type='INT'); sid2.inputs['Name'].default_value = 'stroke'
    eq = node('FunctionNodeCompare', data_type='INT', operation='EQUAL')
    L.new(sid2.outputs['Attribute'], eq.inputs['A']); L.new(rin.outputs['Index'], eq.inputs['B'])
    one = node('GeometryNodeSeparateGeometry', domain='POINT')
    L.new(strokes, one.inputs['Geometry']); L.new(eq.outputs['Result'], one.inputs['Selection'])
    st = one.outputs['Selection']
    def stat(name, typ='FLOAT'):
        a = node('GeometryNodeInputNamedAttribute', data_type=typ); a.inputs['Name'].default_value = name
        s_ = node('GeometryNodeAttributeStatistic', data_type=typ, domain='POINT')
        L.new(st, s_.inputs['Geometry']); L.new(a.outputs['Attribute'], s_.inputs['Attribute'])
        return s_.outputs['Mean']
    r, k, strength, mvec = stat('radius'), stat('kind'), stat('strength'), stat('move', 'FLOAT_VECTOR')
    sp = node('GeometryNodeProximity'); sp.target_element = 'EDGES'
    L.new(st, sp.inputs[0])
    spp = node('GeometryNodeProximity'); spp.target_element = 'POINTS'
    L.new(st, spp.inputs[0])
    ecount = node('GeometryNodeAttributeDomainSize', component='MESH'); L.new(st, ecount.inputs['Geometry'])
    has_e = math_('GREATER_THAN', ecount.outputs['Edge Count'], 0.0)
    dsw = node('GeometryNodeSwitch', input_type='FLOAT')
    L.new(has_e, dsw.inputs['Switch']); L.new(spp.outputs['Distance'], dsw.inputs['False']); L.new(sp.outputs['Distance'], dsw.inputs['True'])
    t = math_('DIVIDE', dsw.outputs['Output'], r)
    # Standard: a smooth bell (1 - t^2)^2;  Clay: a flat top (1 inside 0.55 r, smooth to 0 at r), capped;  Move: bell
    # around the grab point (the stroke's first point) along the drag
    one_m_t2 = math_('MAXIMUM', math_('SUBTRACT', 1.0, math_('MULTIPLY', t, t)), 0.0)
    bell = math_('MULTIPLY', one_m_t2, one_m_t2)
    clay = node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP', clamp=True)
    L.new(t, clay.inputs['Value']); clay.inputs['From Min'].default_value = 1.0; clay.inputs['From Max'].default_value = 0.55
    n_attr = node('GeometryNodeInputNamedAttribute', data_type='FLOAT_VECTOR'); n_attr.inputs['Name'].default_value = 'mch_n'
    std_off = vmath('SCALE', n_attr.outputs['Attribute'], scale=math_('MULTIPLY', math_('MULTIPLY', bell, strength), r))
    clay_off = vmath('SCALE', n_attr.outputs['Attribute'], scale=math_('MULTIPLY', math_('MULTIPLY', clay.outputs['Result'], strength), math_('MULTIPLY', r, 0.45)))
    mv_off = vmath('SCALE', mvec, scale=bell)
    # Clay Buildup: the plane = the stroke's mean point + its mean normal x (strength x radius x 0.5); points below it
    # inside a hard footprint (full to 0.8 r, gone at r, its edge roughened by noise) are filled up to it
    ppos = node('GeometryNodeInputPosition')
    pstat = node('GeometryNodeAttributeStatistic', data_type='FLOAT_VECTOR', domain='POINT')
    L.new(st, pstat.inputs['Geometry']); L.new(ppos.outputs[0], pstat.inputs['Attribute'])
    pn = vmath('NORMALIZE', stat('normal', 'FLOAT_VECTOR'))
    lift = vmath('SCALE', pn.outputs['Vector'], scale=math_('MULTIPLY', math_('MULTIPLY', strength, r), 0.5))
    target = vmath('ADD', pstat.outputs['Mean'], lift.outputs['Vector'])
    below = vmath('DOT_PRODUCT', vmath('SUBTRACT', target.outputs['Vector'], node('GeometryNodeInputPosition').outputs[0]).outputs['Vector'],
                  pn.outputs['Vector'])
    noise = node('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = 9.0; noise.inputs['Detail'].default_value = 4.0
    rough_t = math_('ADD', t, math_('MULTIPLY', math_('SUBTRACT', noise.outputs['Fac'], 0.5), 0.35))
    foot = node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP', clamp=True)
    L.new(rough_t, foot.inputs['Value']); foot.inputs['From Min'].default_value = 1.0; foot.inputs['From Max'].default_value = 0.8
    fill = math_('MULTIPLY', math_('MAXIMUM', below.outputs['Value'], 0.0), foot.outputs['Result'])
    bld_off = vmath('SCALE', pn.outputs['Vector'], scale=fill)
    pick = node('GeometryNodeIndexSwitch', data_type='VECTOR'); pick.index_switch_items.new(); pick.index_switch_items.new()
    L.new(math_('ROUND', k), pick.inputs['Index'])
    L.new(std_off.outputs['Vector'], pick.inputs[1]); L.new(clay_off.outputs['Vector'], pick.inputs[2]); L.new(mv_off.outputs['Vector'], pick.inputs[3])
    L.new(bld_off.outputs['Vector'], pick.inputs[4])
    setp = node('GeometryNodeSetPosition')
    L.new(rin.outputs['Geometry'], setp.inputs['Geometry']); L.new(pick.outputs['Output'], setp.inputs['Offset'])
    L.new(setp.outputs['Geometry'], rout.inputs['Geometry'])
    L.new(math_('ADD', rin.outputs['Index'], 1.0), rout.inputs['Index'])
    geo = rout.outputs['Geometry']
    join = node('GeometryNodeJoinGeometry')
    L.new(geo, join.inputs[0]); L.new(rest, join.inputs[0])
    merge = node('GeometryNodeMergeByDistance'); merge.inputs['Distance'].default_value = 1e-5
    L.new(join.outputs['Geometry'], merge.inputs['Geometry'])
    smooth = node('GeometryNodeSetShadeSmooth', domain='FACE'); L.new(merge.outputs['Geometry'], smooth.inputs['Geometry'])
    ang = node('GeometryNodeInputMeshEdgeAngle')
    flat_e = math_('GREATER_THAN', ang.outputs['Unsigned Angle'], math.radians(30))
    sharp = node('GeometryNodeSetShadeSmooth', domain='EDGE'); L.new(smooth.outputs['Geometry'], sharp.inputs['Geometry'])
    nt = node('FunctionNodeBooleanMath', operation='NOT'); L.new(flat_e, nt.inputs[0])
    L.new(nt.outputs[0], sharp.inputs['Shade Smooth'])
    L.new(sharp.outputs['Geometry'], go.inputs['Geometry'])
    return ng


# a low-poly mecha part: a box with chamfered edges
me = bpy.data.meshes.new('Part'); bm = bmesh.new()
bmesh.ops.create_cube(bm, size=2.0)
bmesh.ops.bevel(bm, geom=list(bm.verts) + list(bm.edges), offset=0.12, segments=1, affect='EDGES', profile=0.5,
                clamp_overlap=True)
bm.to_mesh(me); bm.free()
part = bpy.data.objects.new('Part', me); S.collection.objects.link(part)
import bmesh as _b
_bm = _b.new(); _bm.from_mesh(me); print('open edges', sum(1 for e in _bm.edges if not e.is_manifold)); _bm.free()
print('base faces', len(me.polygons))
# strokes: Standard across the front, Clay zigzag on top, Move pulling a top corner outwards
pts, edges, sid, rad, strg, kind, mv, nrm = [], [], [], [], [], [], [], []
def stroke(points, i, r, s, k, m=(0, 0, 0), n=(0, 0, 1)):
    base = len(pts)
    for j, p in enumerate(points):
        pts.append(p); sid.append(i); rad.append(r); strg.append(s); kind.append(k); mv.append(m); nrm.append(n)
        if j: edges.append((base + j - 1, base + j))
stroke([(x, -1.0, 0.2 * math.sin(x * 3)) for x in np.linspace(-0.7, 0.7, 15)], 0, 0.18, 0.35, 0, n=(0, -1, 0))  # Standard
# the top, left: Clay (two passes)
stroke([(-0.85 + 0.035 * j, -0.45 + 0.35 * j / 17, 1.0) for j in range(18)], 1, 0.13, 1.0, 1)
stroke([(-0.80 + 0.035 * j, -0.38 + 0.35 * j / 17, 1.0) for j in range(18)], 2, 0.12, 1.0, 1)
# the top, right: a Standard bump, then Clay Buildup (three passes) over and round it - filled up to its plane
stroke([(0.45, -0.2, 1.0)], 3, 0.16, 0.9, 0)
stroke([(0.15 + 0.04 * j, -0.45 + 0.03 * j, 1.0) for j in range(16)], 4, 0.16, 1.0, 3)
stroke([(0.15 + 0.04 * j, -0.30 + 0.03 * j, 1.0) for j in range(16)], 5, 0.16, 1.0, 3)
stroke([(0.15 + 0.04 * j, -0.15 + 0.03 * j, 1.0) for j in range(16)], 6, 0.16, 1.6, 3)
stroke([(0.55, 0.62, 1.0)], 7, 0.3, 1.0, 2, (0.0, 0.0, 0.3))                                            # Move
sme = bpy.data.meshes.new('Strokes'); sme.from_pydata(pts, edges, [])
for name, typ, vals, key in (('stroke', 'INT', sid, 'value'), ('radius', 'FLOAT', rad, 'value'), ('strength', 'FLOAT', strg, 'value'),
                             ('kind', 'INT', kind, 'value'), ('move', 'FLOAT_VECTOR', mv, 'vector'),
                             ('normal', 'FLOAT_VECTOR', nrm, 'vector')):
    a = sme.attributes.new(name, typ, 'POINT')
    a.data.foreach_set(key, np.array(vals, dtype=np.float32 if typ != 'INT' else np.int32).ravel())
sob = bpy.data.objects.new('Part (sculpt strokes)', sme)
mod = part.modifiers.new('MCH Sculpt Layer', 'NODES'); mod.node_group = node_group()
ident = next(it.identifier for it in mod.node_group.interface.items_tree if getattr(it, 'name', '') == 'Strokes' and it.in_out == 'INPUT')
getattr(mod.properties.inputs, ident).value = sob
dg = bpy.context.evaluated_depsgraph_get(); ev = part.evaluated_get(dg)
print('evaluated faces', len(ev.data.polygons), 'base still', len(part.data.polygons))
# render: the shaded part + its wireframe (a copy of the evaluated mesh with a thin dark Wireframe)
mat = bpy.data.materials.new('Clay'); mat.use_nodes = True
mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.55, 0.5, 0.45, 1)
part.data.materials.append(mat)
wme = bpy.data.meshes.new_from_object(ev); wob = bpy.data.objects.new('Wire', wme); wob.matrix_world = part.matrix_world
S.collection.objects.link(wob)
wm = wob.modifiers.new('W', 'WIREFRAME'); wm.thickness = 0.004; wm.use_replace = True
wmat = bpy.data.materials.new('WireM'); wmat.use_nodes = True
wmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.02, 0.02, 0.03, 1)
wme.materials.clear(); wme.materials.append(wmat)
cam_d = bpy.data.cameras.new('C'); cam = bpy.data.objects.new('C', cam_d); S.collection.objects.link(cam); S.camera = cam
cam.location = (1.2, -3.0, 4.6)
cam.rotation_euler = (Vector((0, 0, 0.1)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
for loc, e in (((3, -3, 5), 800), ((-4, -2, 2), 300)):
    ld = bpy.data.lights.new('L', 'AREA'); ld.energy = e; ld.size = 3
    lo = bpy.data.objects.new('L', ld); lo.location = loc; S.collection.objects.link(lo)
    lo.rotation_euler = (Vector((0, 0, 0)) - lo.location).to_track_quat('-Z', 'Y').to_euler()
w = bpy.data.worlds.new('W'); S.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.05, 0.05, 0.06, 1)
S.render.engine = 'CYCLES'; S.cycles.samples = 48; S.cycles.device = 'CPU'
S.render.resolution_x, S.render.resolution_y = 1200, 800
for name, wire in (('gn_sculpt_shaded', False), ('gn_sculpt_wire', True)):
    wob.hide_render = not wire
    S.render.filepath = os.path.join(OUT, name + '.png')
    bpy.ops.render.render(write_still=True)
print('DONE')
