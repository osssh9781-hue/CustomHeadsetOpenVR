"""0.24.171 Vacuum Pack (user: "클로스 드레이프에서 진공팩마냥 내가 선택한 거 감싸 주는 것도 만들어 주라"; on Wrap This Mesh's
result, small crumples all over and a ragged rim: "결과가 별로라네"; "주름이 하나도 안 생기잖아!!" with a photo of shrink film
over a figure; "왜 시뮬을 안 하고 이렇게 해?" with a photo of a cloth pulled tight over a face): the selected meshes put
in ONE bag and the air sucked out - a cloth simulation (Cloth Drape's), not a made-up surface.

    the bag      a loose closing round all the parts (a signed distance grid grown and shrunk: it spans the gaps), an
                 even mesh of about Points points - the cloth
    the sim      Blender's own cloth: the bag's air pressure below zero (it is sucked in from wherever it is and
                 stops on the parts - copies of them as colliders, the parts themselves untouched), stiff to
                 stretch and soft to squeeze (the extra cloth buckles into folds), Tightness shrinks it a little,
                 Folds sets the bending (fine sharp folds .. broad soft ones), hardly any gravity
    the gather   (optional) the cloth round the gather point (a click on the mesh, or the bag's lowest point)
                 pinned and drawn gently toward a knot there: the folds lean toward it

Space runs / pauses it (Cloth Drape's own Space), Enter keeps the cloth as it is (a plain mesh; Cloth Drape's Thickness:
its Solidify), Esc drops it.  Afterwards the colliders go and the scene's frame is put back.
"""
from __future__ import annotations

import json
import math
import time

import bpy
from bpy.props import EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, PointerProperty
from mathutils import Vector

KEY = 'mch_vacuum'                 # on a film: the names of the parts it is sealed round (json)
MOD = 'MCH Vacuum'
TREE = 'MCH Vacuum'
TREE_V = 3
DIR_ATTR, W_ATTR, K_ATTR = 'mch_vac_dir', 'mch_vac_w', 'mch_vac_k'   # (the fine creases' direction, strength, scale)
FILMS = (('CLEAR', 'Clear Plastic', 'A clear glossy vacuum bag'),
         ('MILKY', 'Milky Plastic', 'A frosted, half see-through film'),
         ('BLACK', 'Black Latex', 'Opaque glossy black latex'),
         ('CLOTH', 'Cloth', 'A matte fabric (a cloth pulled over it)'))


# ---- the parts -------------------------------------------------------------------------------------------------------

def is_film(ob):
    return ob is not None and bool(ob.get(KEY))


def film_parts(ob):
    try:
        names = json.loads(ob.get(KEY) or '[]')
    except (TypeError, ValueError):
        names = []
    return [bpy.data.objects[n] for n in names if n in bpy.data.objects]


def pick_parts(context):
    """The selected meshes to seal (films never)."""
    return [o for o in context.selected_objects if o.type == 'MESH' and not is_film(o) and o.visible_get()]


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

FILM_V = 8


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
    vals = {'CLEAR': dict(col=(0.92, 0.94, 0.96), rough=0.05, trans=0.9, coat=0.4, view=(0.82, 0.88, 0.95, 0.4)),
            'MILKY': dict(col=(0.86, 0.87, 0.89), rough=0.25, trans=0.55, coat=0.2, view=(0.85, 0.86, 0.88, 0.8)),
            'BLACK': dict(col=(0.018, 0.018, 0.02), rough=0.14, trans=0.0, coat=0.7, view=(0.03, 0.03, 0.035, 1.0)),
            'CLOTH': dict(col=(0.55, 0.5, 0.44), rough=0.85, trans=0.0, coat=0.0, view=(0.55, 0.5, 0.44, 1.0))}[kind]
    for sock, v in (('Base Color', (*vals['col'], 1.0)), ('Roughness', vals['rough']),
                    ('Transmission Weight', vals['trans']), ('Coat Weight', vals['coat']), ('IOR', 1.45)):
        try:
            pb.inputs[sock].default_value = v
        except (KeyError, TypeError):
            pass
    if kind == 'CLOTH':
        try:
            pb.inputs['Sheen Weight'].default_value = 0.4
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


# ---- the bag --------------------------------------------------------------------------------------------------------

def bag_mesh(context, parts, loose, points):
    """The bag round ``parts`` (world space): a closing of them all (Bag: 0 tight round each, 1 one loose bag round
    the lot) lifted a little off them, of about ``points`` points.  A new mesh."""
    size = bounds_size(context, parts)
    tmp_me = bpy.data.meshes.new('MCH Vacuum Bag')
    tmp = bpy.data.objects.new('MCH Vacuum Bag', tmp_me)
    context.scene.collection.objects.link(tmp)
    ng = build_tree(f'{TREE} - bag', parts)
    mod = tmp.modifiers.new(MOD, 'NODES')
    mod.node_group = ng
    from . import geo_sculpt as gs
    try:
        detail = 80
        me = None
        good = None                                     # (the last bag that came out - 0.24.185: a finer try can
        for _try in range(4):                           # come out empty on thin shapes; then a detail between)
            for sock, v in (('Size', size), ('Hug', 1.0 - 0.75 * loose), ('Gap', 0.035), ('Detail', int(detail)),
                            ('Creases', 0.0), ('Crease Size', 0.04), ('Seed', 0), ('Over Parts', 0.0),
                            ('Center', (0.0, 0.0, 0.0)), ('E1', (1.0, 0.0, 0.0)), ('E2', (0.0, 1.0, 0.0))):
                gs.set_input(mod, sock, v)
            dg = context.evaluated_depsgraph_get()
            dg.update()
            me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg), depsgraph=dg)
            n = len(me.vertices)
            if n == 0:
                bpy.data.meshes.remove(me)
                me = None
                if good is None:
                    break
                detail = (detail + good[1]) * 0.5       # (too fine: half way back to the one that worked)
                continue
            if good is not None:
                bpy.data.meshes.remove(good[0])
            good = (me, detail)
            if abs(n - points) < points * 0.25:
                break
            detail = max(20, min(600, detail * math.sqrt(points / n)))
        me = good[0] if good is not None else bpy.data.meshes.new('MCH Vacuum Bag empty')
    finally:
        bpy.data.objects.remove(tmp)
        if tmp_me.users == 0:
            bpy.data.meshes.remove(tmp_me)
        if ng.users == 0:
            bpy.data.node_groups.remove(ng)
    for a in [a for a in me.attributes if a.name.startswith('mch_vac_')]:
        me.attributes.remove(a)
    me.materials.clear()
    return me


# ---- settings -------------------------------------------------------------------------------------------------------

def _restart(self, context):
    """A Vacuum Pack slider changed while its cloth is out: the cloth set up again with it (as Cloth Drape's do)."""
    from . import cloth_drape as cd
    if cd.sim_active() and cd.SIM.get('mode') == 'VACUUM':
        try:
            sim_restart(context)
            cd.SIM['running'] = False
        except Exception as ex:                       # (never break the slider)
            print('Vacuum Pack:', ex)


class MCH_PG_Vacuum(bpy.types.PropertyGroup):
    bag: FloatProperty(name='Bag', default=0.5, min=0.0, max=1.0,
                       description='The bag it starts as: 0 close round each part, 1 one loose bag round them all '
                                   '(more cloth to suck in: more folds)')
    pressure: FloatProperty(name='Suction', default=80.0, min=5.0, max=200.0, subtype='PERCENTAGE', update=_restart,
                            description='How hard the air is sucked out (how deep into the hollows it is pulled)')
    tight: FloatProperty(name='Tightness', default=6.0, min=0.0, max=30.0, subtype='PERCENTAGE', update=_restart,
                         description='How much the cloth shrinks while it is sucked in (pulled taut over the high points)')
    folds: FloatProperty(name='Folds', default=55.0, min=0.0, max=100.0, subtype='PERCENTAGE', update=_restart,
                         description='0: broad soft folds (a stiff film); 100: many fine sharp folds (a thin cloth)')
    gravity: FloatProperty(name='Gravity', default=5.0, min=0.0, max=200.0, subtype='PERCENTAGE', update=_restart,
                           description='How much the cloth sags while it is sucked in')
    points: IntProperty(name='Points', default=6000, min=1000, soft_max=40000, max=200000,
                        description='About how many points the cloth has (more: finer folds, slower)')
    frames: IntProperty(name='Frames', default=60, min=10, max=600, update=_restart,
                        description='How many frames Space runs')
    self_collide: bpy.props.BoolProperty(name='Self Collision', default=False, update=_restart,
                                         description='The folds never pass through each other (slower)')
    gather: EnumProperty(name='Gather', items=(('NONE', 'No Gather', 'Only sucked in'),
                                               ('AUTO', 'Bottom', 'Drawn gently toward the bag\'s lowest point'),
                                               ('PICKED', 'Picked Point', 'Drawn gently toward where you clicked on '
                                                                          'the mesh (Pick Gather Point)')),
                         default='NONE')
    gather_point: FloatVectorProperty(name='Gather Point', size=3, subtype='XYZ', options={'HIDDEN'})
    gather_size: FloatProperty(name='Gather Size', default=6.0, min=1.0, max=20.0, subtype='PERCENTAGE',
                               description='How much of the cloth round the gather point is pinned and drawn in')
    collider_faces: IntProperty(name='Collider Faces', default=120000, min=5000, max=2000000,
                                description='A heavy part collides as a lighter copy of about this many faces')
    film: EnumProperty(name='Film', items=FILMS, default='CLOTH')


# ---- operators ------------------------------------------------------------------------------------------------------

# ---- the session (Blender's own cloth, run by Cloth Drape's Space / Enter / Esc) ----------------------------------

CLOTH_MOD = 'MCH Vacuum Cloth'
COLL = 'MCH Vacuum Colliders'


def _sim():
    from . import cloth_drape as cd
    return cd.SIM


def _colliders(context, parts, faces, gap):
    """Collision copies of the parts (lighter when heavy) - the parts themselves are not touched."""
    from . import collider_proxy as cpx
    coll = bpy.data.collections.get(COLL)
    if coll is None:
        coll = bpy.data.collections.new(COLL)
    if coll.name not in context.scene.collection.children:
        context.scene.collection.children.link(coll)
    out = []
    for o in parts:
        me, temp = cpx.proxy_mesh(context, o, faces)
        if not temp:
            me = me.copy()
        c = bpy.data.objects.new(f'{o.name} - vacuum collider', me)
        coll.objects.link(c)
        c.matrix_world = o.matrix_world.copy()
        c.modifiers.new('Collision', 'COLLISION')
        c.collision.thickness_outer = gap
        c.collision.cloth_friction = 5.0
        c.display_type = 'WIRE'
        c.hide_render = True
        c.hide_select = True
        out.append(c)
    return out


def cloth_settings(film, vp, size):
    """The Vacuum Pack's sliders on the bag's Cloth modifier."""
    cm = film.modifiers.get(CLOTH_MOD)
    if cm is None:
        return
    cs = cm.settings
    cs.quality = 5
    cs.mass = 0.05
    cs.air_damping = 2.0
    cs.tension_stiffness = 40.0                       # (stiff to stretch, soft to squeeze: the extra cloth buckles)
    cs.compression_stiffness = 2.0
    cs.shear_stiffness = 5.0
    cs.bending_stiffness = 1.0 * (0.03 ** (vp.folds / 100.0))
    cs.use_pressure = True
    cs.uniform_pressure_force = -20.0 * vp.pressure / 100.0
    cs.shrink_min = vp.tight / 100.0
    cs.effector_weights.gravity = vp.gravity / 100.0
    if film.vertex_groups.get('MCH Gather') is not None:
        cs.vertex_group_mass = 'MCH Gather'
        cs.pin_stiffness = 1.0
    cc = cm.collision_settings
    cc.collision_quality = 3                          # (a sharp tip / a thin ear never slips between the points)
    cc.distance_min = max(size * 0.004, 1e-4)
    cc.use_self_collision = vp.self_collide
    cc.self_distance_min = max(size * 0.0015, 1e-4)


def _gather(film, me, vp, frame0):
    """The cloth round the gather point pinned and drawn gently toward a knot just outside it (a shape key keyed
    over the first frames: the pinned points follow it)."""
    import numpy as np
    co = np.array([v.co for v in me.vertices])
    size = float(np.linalg.norm(co.max(0) - co.min(0)))
    if vp.gather == 'PICKED':
        k = int(np.argmin(np.linalg.norm(co - np.array(vp.gather_point), axis=1)))
        out = co[k] - co.mean(0)
    else:
        k = int(np.argmin(co[:, 2]))
        out = np.array([0.0, 0.0, -1.0])
    out = out / max(np.linalg.norm(out), 1e-12)
    rg = size * vp.gather_size / 100.0
    idx = np.nonzero(np.linalg.norm(co - co[k], axis=1) <= rg)[0]
    knot = co[k] + out * rg * 0.3
    vg = film.vertex_groups.new(name='MCH Gather')
    vg.add([int(i) for i in idx], 1.0, 'REPLACE')
    film.shape_key_add(name='Basis')
    key = film.shape_key_add(name='MCH Gather')
    for i in idx:
        key.data[int(i)].co = tuple(knot + (co[i] - knot) * 0.55)
    key.value = 0.0
    key.keyframe_insert('value', frame=frame0)
    key.value = 1.0
    key.keyframe_insert('value', frame=frame0 + 25)
    return len(idx)


def perform(context, bag=None):
    """The selected meshes in one bag, ready to be sucked in (Space).  Returns a report."""
    from . import cloth_drape as cd
    from . import core_geometry as cg
    if cd.sim_active():
        raise cg.CutError('Cloth Drape: keep (Enter) or drop (Esc) the cloth you have first')
    parts = pick_parts(context)
    if not parts:
        raise cg.CutError('Vacuum Pack: select the meshes to seal in the bag')
    vp = context.scene.mch_vacuum
    size = bounds_size(context, parts)
    me = bag if bag is not None else bag_mesh(context, parts, vp.bag, vp.points)   # (bag: one made by the caller)
    if not len(me.vertices):
        bpy.data.meshes.remove(me)
        raise cg.CutError('Vacuum Pack: the bag came out empty')
    for p in me.polygons:
        p.use_smooth = True
    me.name = 'Vacuum Pack'
    film = bpy.data.objects.new('Vacuum Pack', me)
    coll = parts[0].users_collection[0] if parts[0].users_collection else context.scene.collection
    coll.objects.link(film)
    film[KEY] = json.dumps([o.name for o in parts])
    me.materials.append(film_material(vp.film))
    frame0 = context.scene.frame_current
    gathered = _gather(film, me, vp, frame0) if vp.gather != 'NONE' else 0
    cols = _colliders(context, parts, vp.collider_faces, max(size * 0.004, 1e-4))
    cm = film.modifiers.new(CLOTH_MOD, 'CLOTH')
    cm.point_cache.frame_start = frame0
    cm.point_cache.frame_end = frame0 + vp.frames
    cloth_settings(film, vp, size)
    for o in context.selected_objects:
        o.select_set(False)
    film.select_set(True)
    context.view_layer.objects.active = film
    SIM = _sim()
    SIM.clear()
    SIM.update(mode='VACUUM', ob=film.name, target=parts[0].name, parts=[o.name for o in parts],
               colliders=[c.name for c in cols], frame0=frame0, size=size, running=False, done=False, want=None,
               sess=dict(frame=0, frames=vp.frames, points=len(me.vertices)))
    g = f', gathered at {"the picked point" if vp.gather == "PICKED" else "the bottom"} ({gathered} points)' if gathered else ''
    return (f'Vacuum Pack round {len(parts)} part(s): {len(me.vertices):,} cloth points{g} - Space: suck the air out '
            f'· Enter keep · Esc drop')


def sim_step(context):
    SIM = _sim()
    sess = SIM.get('sess')
    if sess is None:
        return False
    if sess['frame'] >= sess['frames']:
        SIM['running'] = False
        SIM['done'] = True
        return False
    sess['frame'] += 1
    context.scene.frame_set(SIM['frame0'] + sess['frame'])
    return True


def _cleanup(context):
    SIM = _sim()
    for n in SIM.get('colliders', ()):
        c = bpy.data.objects.get(n)
        if c is not None:
            me = c.data
            bpy.data.objects.remove(c)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
    coll = bpy.data.collections.get(COLL)
    if coll is not None and not coll.objects:
        bpy.data.collections.remove(coll)
    if 'frame0' in SIM:
        context.scene.frame_set(SIM['frame0'])


def sim_keep(context):
    """The cloth kept as it is now: a plain mesh (with Cloth Drape's Thickness its Solidify)."""
    from . import cloth_drape as cd
    SIM = _sim()
    film = bpy.data.objects.get(SIM.get('ob', ''))
    if film is None:
        SIM.clear()
        return 'nothing to keep'
    dg = context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(film.evaluated_get(dg), depsgraph=dg)
    old = film.data
    cm = film.modifiers.get(CLOTH_MOD)
    if cm is not None:
        film.modifiers.remove(cm)
    if old.shape_keys is not None:
        film.shape_key_clear()
    me.name = old.name
    film.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    vg = film.vertex_groups.get('MCH Gather')
    if vg is not None:
        film.vertex_groups.remove(vg)
    frame = SIM['sess']['frame']
    size = SIM.get('size', 1.0)
    _cleanup(context)
    if KEY in film:
        del film[KEY]
    thick = cd.add_thickness(film, size, cd.settings(context))
    SIM.clear()
    return (f'Vacuum Pack: kept at frame {frame} ({len(me.vertices):,} points)' +
            (' + Thickness (its Solidify)' if thick else ''))


def sim_drop(context):
    SIM = _sim()
    film = bpy.data.objects.get(SIM.get('ob', ''))
    _cleanup(context)
    if film is not None:
        me = film.data
        bpy.data.objects.remove(film)
        if me.users == 0:
            bpy.data.meshes.remove(me)
    SIM.clear()
    return 'Vacuum Pack: dropped'


def sim_restart(context):
    """Back to the bag (frame one), the sliders taken again."""
    SIM = _sim()
    film = bpy.data.objects.get(SIM.get('ob', ''))
    if film is None:
        return False
    vp = context.scene.mch_vacuum
    context.scene.frame_set(SIM['frame0'])
    cm = film.modifiers.get(CLOTH_MOD)
    if cm is not None:
        cm.point_cache.frame_end = SIM['frame0'] + vp.frames
    cloth_settings(film, vp, SIM.get('size', 1.0))
    SIM['sess'].update(frame=0, frames=vp.frames)
    SIM.update(done=False, running=True)
    return True


def sim_status():
    SIM = _sim()
    sess = SIM.get('sess') or {}
    f, n = sess.get('frame', 0), sess.get('frames', 0)
    if SIM.get('done'):
        return f'Vacuum Pack done: frame {f} / {n}  (Enter keep · Esc drop · Space again)'
    return (f'Vacuum Pack {"sucking in" if SIM.get("running") else "ready"}: frame {f} / {n}  '
            f'(Space {"pause" if SIM.get("running") else "suck in"} · Enter keep · Esc drop)')


class MCH_OT_vacuum_pack(bpy.types.Operator):
    """Put the selected meshes in one bag and suck the air out (Blender's cloth simulation): Space runs it, Enter
    keeps it, Esc drops it"""
    bl_idname = 'mch.vacuum_pack'
    bl_label = 'Vacuum Pack Selected'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and bool(pick_parts(context))

    def execute(self, context):
        from . import core_geometry as cg
        try:
            msg = perform(context)
        except (cg.CutError, ValueError, RuntimeError) as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class MCH_OT_vacuum_gather_pick(bpy.types.Operator):
    """Click on the mesh where the cloth is drawn together (the knot: the tension folds run toward it); Esc cancels"""
    bl_idname = 'mch.vacuum_gather_pick'
    bl_label = 'Pick Gather Point'
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, 'Pick Gather Point: in the 3D View')
            return {'CANCELLED'}
        context.window_manager.modal_handler_add(self)
        context.window.cursor_modal_set('CROSSHAIR')
        context.workspace.status_text_set('Vacuum Pack: click on the mesh where the cloth gathers  |  Esc: cancel')
        return {'RUNNING_MODAL'}

    def _end(self, context):
        try:
            context.window.cursor_modal_restore()
            context.workspace.status_text_set(None)
        except (AttributeError, RuntimeError):
            pass

    def modal(self, context, event):
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            self._end(context)
            return {'CANCELLED'}
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            from bpy_extras import view3d_utils
            region, rv = context.region, context.region_data
            xy = (event.mouse_region_x, event.mouse_region_y)
            o = view3d_utils.region_2d_to_origin_3d(region, rv, xy)
            d = view3d_utils.region_2d_to_vector_3d(region, rv, xy)
            hit, loc, _n, _i, _ob, _m = context.scene.ray_cast(context.evaluated_depsgraph_get(), o, d)
            if not hit:
                self.report({'INFO'}, 'Pick Gather Point: click on the mesh')
                return {'RUNNING_MODAL'}
            vp = context.scene.mch_vacuum
            vp.gather_point = loc
            vp.gather = 'PICKED'
            self._end(context)
            self.report({'INFO'}, f'Gather point set ({loc.x:.2f}, {loc.y:.2f}, {loc.z:.2f})')
            return {'FINISHED'}
        return {'PASS_THROUGH'}


def draw(layout, context):
    """The Vacuum Pack box (in the Cloth Drape window)."""
    from . import cloth_drape as cd
    vp = context.scene.mch_vacuum
    box = layout.box()
    box.label(text='Vacuum Pack: the selected meshes in one bag, the air sucked out', icon='MOD_SHRINKWRAP')
    live = cd.sim_active() and cd.SIM.get('mode') == 'VACUUM'
    if live:
        box.label(text='Space: suck the air out  ·  Enter: keep  ·  Esc: drop', icon='PLAY')
    else:
        box.operator('mch.vacuum_pack', text='Vacuum Pack Selected', icon='MOD_SHRINKWRAP')
    r = box.row(align=True)
    r.prop(vp, 'gather', expand=True)
    box.operator('mch.vacuum_gather_pick', text='Pick Gather Point (click on the mesh)', icon='EYEDROPPER')
    col = box.column(align=True)
    for k in ('pressure', 'tight', 'folds', 'gravity'):
        col.prop(vp, k, slider=True)
    if vp.gather != 'NONE':
        col.prop(vp, 'gather_size', slider=True)
    col.prop(vp, 'self_collide')
    col = box.column(align=True)
    col.prop(vp, 'bag', slider=True)
    col.prop(vp, 'points')
    col.prop(vp, 'frames')
    col.prop(vp, 'collider_faces')
    box.row(align=True).prop(vp, 'film', expand=True)


CLASSES = (MCH_PG_Vacuum, MCH_OT_vacuum_pack, MCH_OT_vacuum_gather_pick)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_vacuum = PointerProperty(type=MCH_PG_Vacuum)


def unregister():
    if hasattr(bpy.types.Scene, 'mch_vacuum'):
        del bpy.types.Scene.mch_vacuum
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
