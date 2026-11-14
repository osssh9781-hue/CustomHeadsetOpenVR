"""0.24.171 Vacuum Pack (user: "클로스 드레이프에서 진공팩마냥 내가 선택한 거 감싸 주는 것도 만들어 주라" - and on what Wrap
This Mesh made, a body covered in small crumples with a ragged rim: "결과가 별로라네"): the selected meshes sealed in
ONE plastic film, live (Geometry Nodes on a new "Vacuum Pack" object).

A vacuum-sealed film is pulled flat onto everything it can touch and stays taut over what it cannot: it spans narrow
gaps and hollows, sags into wide ones with a round fillet, and gathers into a few thin, sharp creases where it spans.
That is a morphological closing of the parts with a ball:

    the parts -> a signed distance grid (OpenVDB, coarse) -> grown by R, shrunk by R (gaps narrower than ~2 R bridged,
    concave corners filled with radius R) -> the film surface at Gap -> subdivided to the Detail -> snapped onto the
    parts where it nearly touches them and kept off them everywhere (a fine distance grid) -> creases on the spans:
    thin ridges running from contact to contact (the tension lines), broken up at random.

Hug sets R: 0 a loose bag (big spans), 1 pulled into nearly every hollow.  The parts stay as they are (the film is
its own object; move a part and the film follows).  Apply: a plain mesh.
"""
from __future__ import annotations

import json
import math
import time

import bpy
from bpy.props import EnumProperty, FloatProperty, IntProperty, PointerProperty
from mathutils import Vector

KEY = 'mch_vacuum'                 # on a film: the names of the parts it is sealed round (json)
MOD = 'MCH Vacuum'
TREE = 'MCH Vacuum'
TREE_V = 3
DIR_ATTR, W_ATTR, K_ATTR = 'mch_vac_dir', 'mch_vac_w', 'mch_vac_k'   # (the fine creases' direction, strength, scale)
FILMS = (('CLEAR', 'Clear Plastic', 'A clear glossy vacuum bag'),
         ('MILKY', 'Milky Plastic', 'A frosted, half see-through film'),
         ('BLACK', 'Black Latex', 'Opaque glossy black latex'))


# ---- the parts -------------------------------------------------------------------------------------------------------

def is_film(ob):
    return ob is not None and bool(ob.get(KEY))


def film_parts(ob):
    try:
        names = json.loads(ob.get(KEY) or '[]')
    except (TypeError, ValueError):
        names = []
    return [bpy.data.objects[n] for n in names if n in bpy.data.objects]


def active_film(context):
    ob = getattr(context.view_layer.objects, 'active', None)
    return ob if is_film(ob) else None


def pick_parts(context):
    """The selected meshes to seal (films never)."""
    return [o for o in context.selected_objects if o.type == 'MESH' and not is_film(o) and o.visible_get()]


def parts_center(film, parts):
    """The middle of the parts' bounds, in the film's own space (the creases run out from it)."""
    pts = [o.matrix_world @ Vector(c) for o in parts for c in o.bound_box]
    if not pts:
        return (0.0, 0.0, 0.0)
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return tuple(film.matrix_world.inverted_safe() @ ((lo + hi) / 2.0))


def parts_axes(film, parts):
    """Two directions across the parts' flattest side (their bounds' thinnest axis is the one the creases turn
    round), in the film's own space."""
    pts = [o.matrix_world @ Vector(c) for o in parts for c in o.bound_box]
    ext = [max(p[i] for p in pts) - min(p[i] for p in pts) for i in range(3)] if pts else [1, 1, 1]
    k = min(range(3), key=lambda i: ext[i])
    e = [Vector([1.0 if j == i else 0.0 for j in range(3)]) for i in range(3) if i != k]
    R = film.matrix_world.to_3x3().inverted_safe()
    return tuple((R @ e[0]).normalized()), tuple((R @ e[1]).normalized())


def bounds_size(context, objs):
    """The diagonal of the parts' world bounds (evaluated)."""
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    if not pts:
        return 1.0
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return max((hi - lo).length, 1e-4)


# ---- the node group --------------------------------------------------------------------------------------------------

class _B:
    def __init__(self, ng):
        self.ng, self.N, self.L = ng, ng.nodes, ng.links

    def node(self, kind, **props):
        n = self.N.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def feed(self, inp, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.L.new(v, inp)
        else:
            inp.default_value = v

    def math(self, op, a, b=None):
        n = self.node('ShaderNodeMath', operation=op)
        self.feed(n.inputs[0], a)
        if b is not None:
            self.feed(n.inputs[1], b)
        return n.outputs[0]

    def vec(self, op, a, b=None, scale=None):
        n = self.node('ShaderNodeVectorMath', operation=op)
        self.feed(n.inputs[0], a)
        if b is not None:
            self.feed(n.inputs[1], b)
        if scale is not None:
            self.feed(n.inputs['Scale'], scale)
        out = n.outputs['Value'] if op in {'DOT_PRODUCT', 'LENGTH', 'DISTANCE'} else n.outputs['Vector']
        return out

    def remap(self, v, a0, a1, b0=0.0, b1=1.0, smooth=False):
        n = self.node('ShaderNodeMapRange', clamp=True)
        if smooth:
            n.interpolation_type = 'SMOOTHSTEP'
        self.feed(n.inputs['Value'], v)
        self.feed(n.inputs['From Min'], a0)
        self.feed(n.inputs['From Max'], a1)
        self.feed(n.inputs['To Min'], b0)
        self.feed(n.inputs['To Max'], b1)
        return n.outputs['Result']

    def sample(self, grid, pos, kind='FLOAT'):
        n = self.node('GeometryNodeSampleGrid', data_type=kind)
        self.feed(n.inputs['Grid'], grid)
        self.feed(n.inputs['Position'], pos)
        return n.outputs[0]

    def pos(self):
        return self.node('GeometryNodeInputPosition').outputs[0]

    def store(self, geo, name, value, kind='FLOAT'):
        n = self.node('GeometryNodeStoreNamedAttribute', data_type=kind, domain='POINT')
        self.feed(n.inputs['Geometry'], geo)
        n.inputs['Name'].default_value = name
        self.feed(n.inputs['Value'], value)
        return n.outputs['Geometry']


INPUTS = (  # (socket, kind, default, min, max)
    ('Size', 'NodeSocketFloat', 1.0, 1e-4, 1e6),
    ('Hug', 'NodeSocketFloat', 0.55, 0.0, 1.0),
    ('Gap', 'NodeSocketFloat', 0.003, 0.0, 0.1),
    ('Detail', 'NodeSocketInt', 120, 40, 600),
    ('Creases', 'NodeSocketFloat', 0.5, 0.0, 1.0),
    ('Crease Size', 'NodeSocketFloat', 0.04, 0.002, 0.2),
    ('Seed', 'NodeSocketInt', 0, 0, 100000),
    ('Over Parts', 'NodeSocketFloat', 0.25, 0.0, 1.0),
    ('Center', 'NodeSocketVector', None, None, None),
    ('E1', 'NodeSocketVector', None, None, None),
    ('E2', 'NodeSocketVector', None, None, None),
)


def build_tree(name, parts):
    """The film's node group (its own: the parts are in it, an Object Info each)."""
    ng = bpy.data.node_groups.get(name)
    if ng is None:
        ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng.nodes.clear()
    ng.interface.clear()
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    for nm, kind, default, lo, hi in INPUTS:
        s = ng.interface.new_socket(nm, in_out='INPUT', socket_type=kind)
        if default is not None:
            s.default_value = default
        if lo is not None and hasattr(s, 'min_value'):
            s.min_value, s.max_value = lo, hi
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    b = _B(ng)
    gi = b.node('NodeGroupInput')
    go = b.node('NodeGroupOutput')
    I = gi.outputs
    join = b.node('GeometryNodeJoinGeometry')
    for ob in parts:
        oi = b.node('GeometryNodeObjectInfo', transform_space='RELATIVE')
        oi.inputs['Object'].default_value = ob
        b.L.new(oi.outputs['Geometry'], join.inputs[0])
    size = I['Size']
    gap = b.math('MULTIPLY', I['Gap'], size)                              # (Gap, Crease Size: shares of the size)
    vf = b.math('DIVIDE', size, b.math('MAXIMUM', I['Detail'], 10.0))      # (the fine voxel: the film's detail)
    # R: Hug 0 = half the size (a loose bag), 1 = 1.5 % of it (into nearly every hollow)
    R = b.math('MULTIPLY', b.math('MULTIPLY', size, 0.5), b.math('POWER', 10.0, b.math('MULTIPLY', I['Hug'], -1.5)))
    vc = b.math('MAXIMUM', b.math('MULTIPLY', vf, 2.0), b.math('DIVIDE', R, 5.0))     # (the coarse voxel)
    fine = b.node('GeometryNodeMeshToSDFGrid')
    b.feed(fine.inputs['Mesh'], join.outputs[0])
    b.feed(fine.inputs['Voxel Size'], vf)
    fine.inputs['Band Width'].default_value = 4
    coarse = b.node('GeometryNodeMeshToSDFGrid')
    b.feed(coarse.inputs['Mesh'], join.outputs[0])
    b.feed(coarse.inputs['Voxel Size'], vc)
    b.feed(coarse.inputs['Band Width'], b.math('ADD', b.math('DIVIDE', R, vc), 4.0))
    grow = b.node('GeometryNodeSDFGridOffset')
    b.feed(grow.inputs[0], coarse.outputs[0])
    b.feed(grow.inputs['Distance'], R)
    shrink = b.node('GeometryNodeSDFGridOffset')
    b.feed(shrink.inputs[0], grow.outputs[0])
    b.feed(shrink.inputs['Distance'], b.math('MULTIPLY', R, -1.0))
    # the closing (coarse) as a surface, back onto the fine grid, joined with the parts themselves: the spans from the
    # closing, every tip and corner the coarse grid rounded off from the parts (both grids the same: the fine one)
    cmesh = b.node('GeometryNodeGridToMesh')
    b.feed(cmesh.inputs[0], shrink.outputs[0])
    cmesh.inputs['Threshold'].default_value = 0.0                     # (its own surface: the default 0.1 grew it)
    csub = b.node('GeometryNodeSubdivisionSurface')
    b.feed(csub.inputs['Mesh'], cmesh.outputs[0])
    csub.inputs['Level'].default_value = 1
    cfine = b.node('GeometryNodeMeshToSDFGrid')
    b.feed(cfine.inputs['Mesh'], csub.outputs['Mesh'])
    b.feed(cfine.inputs['Voxel Size'], vf)
    cfine.inputs['Band Width'].default_value = 4
    union = b.node('GeometryNodeSDFGridBoolean', operation='UNION')     # (Union: its second input takes them all)
    b.L.new(fine.outputs[0], union.inputs[1])
    b.L.new(cfine.outputs[0], union.inputs[1])
    g2m = b.node('GeometryNodeGridToMesh')
    b.feed(g2m.inputs[0], union.outputs[0])
    b.feed(g2m.inputs['Threshold'], gap)
    geo = g2m.outputs[0]
    grad = b.node('GeometryNodeGridGradient')
    b.feed(grad.inputs[0], fine.outputs[0])
    blur = b.node('GeometryNodeBlurAttribute', data_type='FLOAT_VECTOR')       # (the voxel steps smoothed away)
    b.feed(blur.inputs['Value'], b.pos())
    blur.inputs['Iterations'].default_value = 2
    blur.inputs['Weight'].default_value = 0.5
    sp0 = b.node('GeometryNodeSetPosition')
    b.feed(sp0.inputs['Geometry'], geo)
    b.feed(sp0.inputs['Position'], blur.outputs['Value'])
    geo = push_out(b, sp0.outputs[0], fine.outputs[0], grad.outputs[0], gap)
    # creases (user, a photo of shrink film over a figure: "이런 식으로 주름이 생겨야 돼" - long creases radiating out from
    # it across the film): lines along the tension - the distance's slope along the film runs away from the parts -
    # smoothed over the film so they run long and even; the bigger ones in the geometry (strongest where the film
    # spans, lighter over the parts), the fine ones in the film's material (a bump from the attributes stored here: no
    # heavier mesh for them)
    pos = b.pos()
    nrm = b.node('GeometryNodeInputNormal').outputs[0]
    d = b.sample(coarse.outputs[0], pos)                               # (the coarse grid: its band reaches the spans)
    # (the lines run straight out from the middle of the pack, as in the photo: their place is the angle round the
    # pack's flattest axis (E1 x E2), so each one is a ray - over the spans and on over the parts alike)
    v = b.vec('SUBTRACT', pos, I['Center'])
    x = b.vec('DOT_PRODUCT', v, I['E1'])
    y = b.vec('DOT_PRODUCT', v, I['E2'])
    r = b.math('SQRT', b.math('ADD', b.math('MULTIPLY', x, x), b.math('MULTIPLY', y, y)))
    theta = b.math('ARCTAN2', y, x)
    span = b.remap(b.math('SUBTRACT', d, gap), b.math('MULTIPLY', vc, 0.3), b.math('MULTIPLY', vc, 1.8), smooth=True)
    base = b.math('ADD', I['Over Parts'], b.math('MULTIPLY', span, b.math('SUBTRACT', 1.0, I['Over Parts'])))
    csz = b.math('MULTIPLY', I['Crease Size'], size)
    mid = b.remap(r, b.math('MULTIPLY', csz, 1.5), b.math('MULTIPLY', csz, 4.0), smooth=True)   # (none at the middle)
    wgt = b.math('MULTIPLY', base, b.math('MULTIPLY', mid, I['Creases']))
    # (strongest where the film spans; Over Parts: how much of it runs on over the parts themselves)
    nlines = b.math('ROUND', b.math('DIVIDE', b.math('MULTIPLY', size, 2.2), csz))   # (about Crease Spacing apart at a
    nz = b.node('ShaderNodeTexNoise', noise_dimensions='4D')                        #  third of the size out)
    b.feed(nz.inputs['Vector'], b.vec('SCALE', pos, scale=b.math('DIVIDE', 1.0, b.math('MULTIPLY', csz, 10.0))))
    b.feed(nz.inputs['W'], I['Seed'])
    nz.inputs['Scale'].default_value = 1.0
    nz.inputs['Detail'].default_value = 3.0
    warp = b.math('MULTIPLY', b.math('SUBTRACT', nz.outputs['Fac'], 0.5), 3.0)       # (the lines wave and bunch)
    s = b.math('ADD', b.math('MULTIPLY', b.math('DIVIDE', theta, 2 * math.pi), nlines), warp)
    ridge = b.math('POWER', b.math('SUBTRACT', 1.0, b.math('ABSOLUTE', b.math('SINE', b.math('MULTIPLY', s, math.pi)))), 3.0)
    line = b.math('FLOOR', b.math('ADD', s, 0.5))                                  # (which crease this is)
    wn = b.node('FunctionNodeRandomValue', data_type='FLOAT')                     # (each its own strength: a few deep,
    b.feed(wn.inputs['ID'], line)                                                  #  many faint)
    b.feed(wn.inputs['Seed'], b.math('ADD', I['Seed'], 11.0))
    amp = b.math('ADD', 0.3, b.math('MULTIPLY', wn.outputs['Value'], 0.7))
    nz2 = b.node('ShaderNodeTexNoise', noise_dimensions='4D')                      # (and its own stretches along: it
    cxr = b.node('ShaderNodeCombineXYZ')                                           #  starts and stops)
    b.feed(cxr.inputs[0], b.math('DIVIDE', r, b.math('MULTIPLY', csz, 6.0)))
    b.feed(nz2.inputs['Vector'], cxr.outputs[0])
    b.feed(nz2.inputs['W'], b.math('ADD', b.math('MULTIPLY', line, 1.37), I['Seed']))
    nz2.inputs['Scale'].default_value = 1.0
    keep = b.remap(nz2.outputs['Fac'], 0.3, 0.48, smooth=True)
    h = b.math('MULTIPLY', b.math('MULTIPLY', ridge, b.math('MULTIPLY', keep, amp)),
               b.math('MULTIPLY', wgt, b.math('MULTIPLY', csz, 1.1)))
    cxy = b.node('ShaderNodeCombineXYZ')                                   # (for the material: the way round, unit)
    b.feed(cxy.inputs[0], b.math('DIVIDE', x, b.math('MAXIMUM', r, 1e-6)))
    b.feed(cxy.inputs[1], b.math('DIVIDE', y, b.math('MAXIMUM', r, 1e-6)))
    b.feed(cxy.inputs[2], b.math('DIVIDE', r, b.math('MULTIPLY', csz, 6.0)))         # (how far out, for the stretches)
    across = cxy.outputs[0]
    sp = b.node('GeometryNodeSetPosition')
    b.feed(sp.inputs['Geometry'], geo)
    b.feed(sp.inputs['Offset'], b.vec('SCALE', nrm, scale=h))
    geo = push_out(b, sp.outputs[0], fine.outputs[0], grad.outputs[0], gap)
    geo = b.store(geo, DIR_ATTR, across, 'FLOAT_VECTOR')                  # (for the material's fine creases)
    geo = b.store(geo, W_ATTR, wgt, 'FLOAT')
    geo = b.store(geo, K_ATTR, b.math('MULTIPLY', nlines, 2.5), 'FLOAT')    # (the fine lines: about 2 between big ones)
    sh = b.node('GeometryNodeSetShadeSmooth')
    b.feed(sh.inputs['Geometry'], geo)
    b.L.new(sh.outputs[0], go.inputs[0])
    ng['mch_v'] = TREE_V
    return ng


def push_out(b, geo, fine, grad, gap, passes=2):
    """Every film point at least Gap off the parts (along the distance's slope), nothing pulled in."""
    for _k in range(passes):
        d = b.sample(fine, b.pos())
        g = b.vec('NORMALIZE', b.sample(grad, b.pos(), 'VECTOR'))
        under = b.math('MAXIMUM', b.math('SUBTRACT', gap, d), 0.0)
        sp = b.node('GeometryNodeSetPosition')
        b.feed(sp.inputs['Geometry'], geo)
        b.feed(sp.inputs['Offset'], b.vec('SCALE', g, scale=under))
        geo = sp.outputs[0]
    return geo


# ---- the film material ---------------------------------------------------------------------------------------------

FILM_V = 6


def _crease_bump(nt, strength):
    """The fine creases in the shader (a Bump): the film's own lines - along the direction stored on it (the
    tension), its strength and scale from the attributes - sharp thin ridges, broken up; feeds the BSDF's normal."""
    N, L = nt.nodes, nt.links
    tc = N.new('ShaderNodeTexCoord')
    adir = N.new('ShaderNodeAttribute')
    adir.attribute_name, adir.attribute_type = DIR_ATTR, 'GEOMETRY'
    aw = N.new('ShaderNodeAttribute')
    aw.attribute_name, aw.attribute_type = W_ATTR, 'GEOMETRY'
    ak = N.new('ShaderNodeAttribute')
    ak.attribute_name, ak.attribute_type = K_ATTR, 'GEOMETRY'

    def m(op, a, b=None):
        n = N.new('ShaderNodeMath')
        n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, bpy.types.NodeSocket):
                L.new(v, n.inputs[i])
            else:
                n.inputs[i].default_value = v
        return n.outputs[0]
    sep = N.new('ShaderNodeSeparateXYZ')
    L.new(adir.outputs['Vector'], sep.inputs[0])
    nz = N.new('ShaderNodeTexNoise')
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    nz.inputs['Scale'].default_value = 6.0
    nz.inputs['Detail'].default_value = 2.0
    warp = m('MULTIPLY', m('SUBTRACT', nz.outputs['Fac'], 0.5), 2.5)
    theta = m('ARCTAN2', sep.outputs['Y'], sep.outputs['X'])               # (the way round the pack's middle)
    s = m('ADD', m('MULTIPLY', m('DIVIDE', theta, 2 * math.pi), ak.outputs['Fac']), m('MULTIPLY', warp, 1.6))
    ridge = m('POWER', m('SUBTRACT', 1.0, m('ABSOLUTE', m('SINE', m('MULTIPLY', s, math.pi)))), 8.0)
    line = m('FLOOR', m('ADD', s, 0.5))
    wn = N.new('ShaderNodeTexWhiteNoise')                                  # (each line its own strength)
    wn.noise_dimensions = '1D'
    L.new(line, wn.inputs['W'])
    amp = m('ADD', 0.25, m('MULTIPLY', wn.outputs['Value'], 0.75))
    nz2 = N.new('ShaderNodeTexNoise')                                      # (and its own stretches along)
    nz2.noise_dimensions = '2D'
    cx = N.new('ShaderNodeCombineXYZ')
    L.new(sep.outputs['Z'], cx.inputs[0])
    L.new(m('MULTIPLY', line, 1.37), cx.inputs[1])
    L.new(cx.outputs[0], nz2.inputs['Vector'])
    nz2.inputs['Scale'].default_value = 2.0
    gate = N.new('ShaderNodeMapRange')
    gate.clamp = True
    L.new(nz2.outputs['Fac'], gate.inputs['Value'])
    gate.inputs['From Min'].default_value, gate.inputs['From Max'].default_value = 0.32, 0.5
    h = m('MULTIPLY', m('MULTIPLY', ridge, m('MULTIPLY', gate.outputs['Result'], amp)), aw.outputs['Fac'])
    bump = N.new('ShaderNodeBump')
    bump.name = 'Creases'
    bump.inputs['Strength'].default_value = strength
    bump.inputs['Distance'].default_value = 0.02
    L.new(h, bump.inputs['Height'])
    return bump, h


def film_material(kind):
    name = 'MCH Vacuum Film - ' + dict((k, l) for k, l, _d in FILMS).get(kind, 'Clear Plastic')
    m = bpy.data.materials.get(name)
    if m is not None and m.get('mch_vac_v') == FILM_V:
        return m
    if m is None:
        m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    pb = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(pb.outputs[0], out.inputs['Surface'])
    vals = {'CLEAR': dict(col=(0.92, 0.94, 0.96), rough=0.05, trans=0.93, coat=0.4, view=(0.82, 0.88, 0.95, 0.35)),
            'MILKY': dict(col=(0.86, 0.87, 0.89), rough=0.25, trans=0.6, coat=0.2, view=(0.85, 0.86, 0.88, 0.75)),
            'BLACK': dict(col=(0.018, 0.018, 0.02), rough=0.14, trans=0.0, coat=0.7, view=(0.03, 0.03, 0.035, 1.0))}[kind]
    for sock, v in (('Base Color', (*vals['col'], 1.0)), ('Roughness', vals['rough']),
                    ('Transmission Weight', vals['trans']), ('Coat Weight', vals['coat']), ('IOR', 1.45)):
        try:
            pb.inputs[sock].default_value = v
        except (KeyError, TypeError):
            pass
    bump, h = _crease_bump(nt, 1.0)
    nt.links.new(bump.outputs['Normal'], pb.inputs['Normal'])
    # the creases catch the light: whiter and less see-through along them (the photo's white streaks)
    white = nt.nodes.new('ShaderNodeMix')
    white.data_type = 'RGBA'
    fac = nt.nodes.new('ShaderNodeMath')
    fac.operation = 'MULTIPLY'
    nt.links.new(h, fac.inputs[0])
    fac.inputs[1].default_value = 0.9 if kind != 'BLACK' else 0.3
    nt.links.new(fac.outputs[0], white.inputs['Factor'])
    white.inputs['A'].default_value = (*vals['col'], 1.0)
    white.inputs['B'].default_value = (1.0, 1.0, 1.0, 1.0) if kind != 'BLACK' else (0.12, 0.12, 0.13, 1.0)
    nt.links.new(white.outputs['Result'], pb.inputs['Base Color'])
    if vals['trans'] > 0:
        tr = nt.nodes.new('ShaderNodeMapRange')
        tr.clamp = True
        nt.links.new(h, tr.inputs['Value'])
        tr.inputs['To Min'].default_value = vals['trans']
        tr.inputs['To Max'].default_value = vals['trans'] * 0.35
        nt.links.new(tr.outputs['Result'], pb.inputs['Transmission Weight'])
    try:
        nt.links.new(bump.outputs['Normal'], pb.inputs['Coat Normal'])
    except KeyError:
        pass
    m.diffuse_color = vals['view']
    m.roughness = vals['rough']
    try:
        m.surface_render_method = 'DITHERED'
    except (AttributeError, TypeError):
        pass
    m['mch_vacuum_film'] = kind
    m['mch_vac_v'] = FILM_V
    return m


# ---- baking the film ------------------------------------------------------------------------------------------------
# (user: "너무 무겁지 않아?" - live, the film was worked out again on every change of the parts, a sculpt stroke on one
# of them included: now it is a plain mesh made once; a setting changed makes it again (once the slider rests), Re-pack
# takes the parts as they are now)

def bake(context, film):
    """The film worked out from its parts and settings (a Geometry Nodes pass) and kept as its mesh (attributes for the
    fine creases with it).  Returns the number of points."""
    parts = film_parts(film)
    if not parts:
        return len(film.data.vertices)
    p = film.mch_vacuum
    ng = build_tree(f'{TREE} - {film.name}', parts)
    mod = film.modifiers.get(MOD) or film.modifiers.new(MOD, 'NODES')
    mod.node_group = ng
    from . import geo_sculpt as gs
    for sock, v in (('Size', float(film.get('mch_vacuum_size', 1.0))), ('Hug', p.hug), ('Gap', p.gap / 100.0),
                    ('Detail', int(p.detail)), ('Creases', p.creases), ('Crease Size', p.crease_size / 100.0),
                    ('Seed', int(p.seed)), ('Over Parts', p.over_parts), ('Center', parts_center(film, parts)),
                    ('E1', parts_axes(film, parts)[0]), ('E2', parts_axes(film, parts)[1])):
        gs.set_input(mod, sock, v)
    old = film.data
    mats = [m for m in old.materials if m is not None] or [film_material(p.film)]
    try:                                               # (the parts taken into the film's own space: Relative)
        dg = context.evaluated_depsgraph_get()
        dg.update()
        me = bpy.data.meshes.new_from_object(film.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    finally:
        film.modifiers.remove(mod)
        if ng.users == 0:
            bpy.data.node_groups.remove(ng)
    me.name = old.name
    me.materials.clear()
    for m in mats[:1]:
        me.materials.append(m)
    if len(me.polygons):
        me.polygons.foreach_set('material_index', [0] * len(me.polygons))
    film.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    film.update_tag()
    return len(me.vertices)


_BUSY = [False]
LIVE = ('hug', 'gap', 'detail', 'creases', 'crease_size', 'seed', 'film', 'over_parts')
_PENDING = {}                       # film name -> time of its last change


def _flush():
    """The timer: films whose settings have rested a moment made again."""
    now = time.time()
    due = [n for n, t in _PENDING.items() if now - t >= 0.35]
    for n in due:
        _PENDING.pop(n, None)
        ob = bpy.data.objects.get(n)
        if ob is not None and is_film(ob):
            try:
                bake(bpy.context, ob)
            except (RuntimeError, ReferenceError, AttributeError) as ex:
                print('Vacuum Pack:', ex)
    return 0.1 if _PENDING else None


def _schedule(ob):
    if bpy.app.background:                          # (no timers there: at once)
        bake(bpy.context, ob)
        return
    _PENDING[ob.name] = time.time()
    if not bpy.app.timers.is_registered(_flush):
        bpy.app.timers.register(_flush, first_interval=0.1)


def _upd(self, context):
    if _BUSY[0]:
        return
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and is_film(ob):
        if ob.get('mch_vacuum_mat') != self.film:     # (a Film preset picked: its material)
            mats = ob.data.materials
            if len(mats):
                mats[0] = film_material(self.film)
            else:
                mats.append(film_material(self.film))
            ob['mch_vacuum_mat'] = self.film
        _schedule(ob)
        sc = getattr(context, 'scene', None)
        if sc is not None and hasattr(sc, 'mch_vacuum'):             # (the next pack starts like this one)
            _BUSY[0] = True
            try:
                for k in LIVE:
                    setattr(sc.mch_vacuum, k, getattr(self, k))
            finally:
                _BUSY[0] = False


class MCH_PG_Vacuum(bpy.types.PropertyGroup):
    hug: FloatProperty(name='Hug', default=0.55, min=0.0, max=1.0, update=_upd,
                       description='How far the film is pulled into hollows and gaps: 0 a loose bag spanning everything, '
                                   '1 sucked into nearly every hollow')
    gap: FloatProperty(name='Gap %', default=0.3, min=0.0, max=5.0, update=_upd,
                       description='How far the film stays off the parts (a share of their size, in %)')
    detail: IntProperty(name='Detail', default=120, min=40, soft_max=300, max=600, update=_upd,
                        description='How fine the film is (steps across the parts\' size; more = finer, heavier)')
    creases: FloatProperty(name='Creases', default=0.8, min=0.0, max=1.0, update=_upd,
                           description='Creases running out from the parts across the film (the tension lines): the big '
                                       'ones in the mesh, the fine ones in the film\'s material')
    crease_size: FloatProperty(name='Crease Spacing %', default=2.5, min=0.5, max=15.0, update=_upd,
                               description='How far apart the big creases are (a share of the size, in %)')
    seed: IntProperty(name='Seed', default=0, min=0, update=_upd, description='Another random set of creases')
    over_parts: FloatProperty(name='Creases Over Parts', default=0.25, min=0.0, max=1.0, update=_upd,
                              description='How much the creases run on over the parts themselves (0: only where the film '
                                          'spans between them)')
    film: EnumProperty(name='Film', items=FILMS, default='CLEAR', update=_upd)


# ---- operators ------------------------------------------------------------------------------------------------------

def perform(context, parts=None):
    """The selected meshes sealed in one film (a new object, its settings kept).  Returns (film, report)."""
    parts = parts if parts is not None else pick_parts(context)
    if not parts:
        raise ValueError('Vacuum Pack: select the meshes to seal in the film')
    st = context.scene.mch_vacuum
    size = bounds_size(context, parts)
    me = bpy.data.meshes.new('Vacuum Pack')
    film = bpy.data.objects.new('Vacuum Pack', me)
    coll = parts[0].users_collection[0] if parts[0].users_collection else context.scene.collection
    coll.objects.link(film)
    film[KEY] = json.dumps([o.name for o in parts])
    film['mch_vacuum_size'] = size
    _BUSY[0] = True
    try:
        for k in LIVE:
            setattr(film.mch_vacuum, k, getattr(st, k))
    finally:
        _BUSY[0] = False
    me.materials.append(film_material(st.film))
    film['mch_vacuum_mat'] = st.film
    t0 = time.time()
    n = bake(context, film)
    for o in context.selected_objects:
        o.select_set(False)
    film.select_set(True)
    context.view_layer.objects.active = film
    msg = (f'Vacuum Pack round {len(parts)} part(s): {n:,} film points ({time.time() - t0:.1f} s) - Hug, Creases, Gap '
           f'in the window remake it; Re-pack after moving a part; Enter / Apply: a plain mesh')
    return film, msg


def apply_film(context, film):
    """The film a plain mesh: its settings and its parts' names dropped (the sliders no longer remake it)."""
    _PENDING.pop(film.name, None)
    for k in (KEY, 'mch_vacuum_size', 'mch_vacuum_mat'):
        if k in film:
            del film[k]


class MCH_OT_vacuum_pack(bpy.types.Operator):
    """Seal the selected meshes in one plastic film (vacuum packing): pulled flat onto them, taut over the gaps,
    creases running out across it"""
    bl_idname = 'mch.vacuum_pack'
    bl_label = 'Vacuum Pack Selected'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and bool(pick_parts(context))

    def execute(self, context):
        try:
            _film, msg = perform(context)
        except (ValueError, RuntimeError) as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class MCH_OT_vacuum_repack(bpy.types.Operator):
    """The selected Vacuum Pack made again round its parts as they are now (after moving or sculpting them)"""
    bl_idname = 'mch.vacuum_repack'
    bl_label = 'Re-pack'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and active_film(context) is not None

    def execute(self, context):
        film = active_film(context)
        t0 = time.time()
        n = bake(context, film)
        self.report({'INFO'}, f'{film.name}: packed again - {n:,} points ({time.time() - t0:.1f} s)')
        return {'FINISHED'}


class MCH_OT_vacuum_apply(bpy.types.Operator):
    """The selected Vacuum Pack(s) as a plain mesh (the sliders no longer remake it)"""
    bl_idname = 'mch.vacuum_apply'
    bl_label = 'Apply Vacuum Pack'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and bool(apply_targets(context))

    def execute(self, context):
        obs = apply_targets(context)
        for film in obs:
            apply_film(context, film)
        self.report({'INFO'}, 'Vacuum Pack applied: ' + ', '.join(f'{o.name} ({len(o.data.polygons):,} faces)' for o in obs))
        return {'FINISHED'}


def apply_targets(context):
    """The films Enter / Apply takes: the selected ones, else the active one."""
    sel = [o for o in getattr(context, 'selected_objects', []) or [] if is_film(o)]
    if sel:
        return sel
    ob = active_film(context)
    return [ob] if ob is not None else []


def draw(layout, context):
    """The Vacuum Pack box (in the Cloth Drape window)."""
    film = active_film(context)
    p = film.mch_vacuum if film is not None else context.scene.mch_vacuum
    box = layout.box()
    box.label(text='Vacuum Pack: the selected meshes sealed in one film', icon='MOD_SHRINKWRAP')
    if film is not None:
        box.label(text=f'{film.name}: round {len(film_parts(film))} part(s) - the sliders remake it', icon='MODIFIER')
        r = box.row(align=True)
        r.operator('mch.vacuum_repack', text='Re-pack (the parts as they are now)', icon='FILE_REFRESH')
    else:
        box.operator('mch.vacuum_pack', text='Vacuum Pack Selected', icon='MOD_SHRINKWRAP')
    box.row(align=True).prop(p, 'film', expand=True)
    col = box.column(align=True)
    col.prop(p, 'hug', slider=True)
    col.prop(p, 'creases', slider=True)
    col.prop(p, 'crease_size', slider=True)
    col.prop(p, 'over_parts', slider=True)
    col.prop(p, 'gap', slider=True)
    col.prop(p, 'detail')
    col.prop(p, 'seed')
    if film is not None:
        box.operator('mch.vacuum_apply', text='Apply (a plain mesh)  Enter', icon='CHECKMARK')


CLASSES = (MCH_PG_Vacuum, MCH_OT_vacuum_pack, MCH_OT_vacuum_repack, MCH_OT_vacuum_apply)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_vacuum = PointerProperty(type=MCH_PG_Vacuum)
    bpy.types.Object.mch_vacuum = PointerProperty(type=MCH_PG_Vacuum)


def unregister():
    if bpy.app.timers.is_registered(_flush):
        bpy.app.timers.unregister(_flush)
    for attr in ('mch_vacuum',):
        for T in (bpy.types.Scene, bpy.types.Object):
            if hasattr(T, attr):
                delattr(T, attr)
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
