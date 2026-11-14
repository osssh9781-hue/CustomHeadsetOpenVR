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
TREE_V = 1
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


INPUTS = (  # (socket, kind, default, min, max)
    ('Size', 'NodeSocketFloat', 1.0, 1e-4, 1e6),
    ('Hug', 'NodeSocketFloat', 0.55, 0.0, 1.0),
    ('Gap', 'NodeSocketFloat', 0.003, 0.0, 0.1),
    ('Detail', 'NodeSocketInt', 160, 40, 600),
    ('Creases', 'NodeSocketFloat', 0.5, 0.0, 1.0),
    ('Crease Size', 'NodeSocketFloat', 0.04, 0.002, 0.2),
    ('Seed', 'NodeSocketInt', 0, 0, 100000),
    ('Material', 'NodeSocketMaterial', None, None, None),
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
    # creases on the spans: thin ridges along the tension (the distance's slope along the film runs from contact to
    # contact), their phase warped and their strength broken up by noise
    pos = b.pos()
    nrm = b.node('GeometryNodeInputNormal').outputs[0]
    cgrad = b.node('GeometryNodeGridGradient')                        # (the coarse grid: its band reaches the spans)
    b.feed(cgrad.inputs[0], coarse.outputs[0])
    d = b.sample(coarse.outputs[0], pos)
    gr = b.sample(cgrad.outputs[0], pos, 'VECTOR')
    gt = b.vec('SUBTRACT', gr, b.vec('SCALE', nrm, scale=b.vec('DOT_PRODUCT', gr, nrm)))
    tmag = b.vec('LENGTH', gt)
    across0 = b.vec('CROSS_PRODUCT', nrm, gt)
    ab = b.node('GeometryNodeBlurAttribute', data_type='FLOAT_VECTOR')    # (the direction smoothed over the film: long
    b.feed(ab.inputs['Value'], across0)                                    #  even creases, not crumples)
    ab.inputs['Iterations'].default_value = 24
    ab.inputs['Weight'].default_value = 1.0
    across = b.vec('NORMALIZE', ab.outputs['Value'])
    span = b.remap(b.math('SUBTRACT', d, gap), b.math('MULTIPLY', vc, 0.3), b.math('MULTIPLY', vc, 1.8), smooth=True)
    csz = b.math('MULTIPLY', I['Crease Size'], size)
    nz = b.node('ShaderNodeTexNoise', noise_dimensions='4D')
    b.feed(nz.inputs['Vector'], b.vec('SCALE', pos, scale=b.math('DIVIDE', 1.0, b.math('MULTIPLY', csz, 5.0))))
    b.feed(nz.inputs['W'], I['Seed'])
    nz.inputs['Scale'].default_value = 1.0
    nz.inputs['Detail'].default_value = 3.0
    warp = b.math('MULTIPLY', b.math('SUBTRACT', nz.outputs['Fac'], 0.5), 1.2)
    s = b.math('ADD', b.math('DIVIDE', b.vec('DOT_PRODUCT', pos, across), csz), warp)
    ridge = b.math('POWER', b.math('SUBTRACT', 1.0, b.math('ABSOLUTE', b.math('SINE', b.math('MULTIPLY', s, math.pi)))), 4.0)
    nz2 = b.node('ShaderNodeTexNoise', noise_dimensions='4D')
    b.feed(nz2.inputs['Vector'], b.vec('SCALE', pos, scale=b.math('DIVIDE', 1.0, b.math('MULTIPLY', csz, 3.0))))
    b.feed(nz2.inputs['W'], b.math('ADD', I['Seed'], 7.3))
    nz2.inputs['Scale'].default_value = 1.0
    keep = b.remap(nz2.outputs['Fac'], 0.45, 0.62, smooth=True)          # (creases break off and start again)
    h = b.math('MULTIPLY', b.math('MULTIPLY', ridge, keep), b.math('MULTIPLY', span, b.math('MINIMUM', b.math('MULTIPLY', tmag, 3.0), 1.0)))
    h = b.math('MULTIPLY', h, b.math('MULTIPLY', b.math('MULTIPLY', I['Creases'], csz), 0.3))
    sp = b.node('GeometryNodeSetPosition')
    b.feed(sp.inputs['Geometry'], geo)
    b.feed(sp.inputs['Offset'], b.vec('SCALE', nrm, scale=h))
    geo = push_out(b, sp.outputs[0], fine.outputs[0], grad.outputs[0], gap)
    sm = b.node('GeometryNodeSetMaterial')                             # (the film's slot 1 material, kept in step)
    b.feed(sm.inputs['Geometry'], geo)
    b.feed(sm.inputs['Material'], I['Material'])
    sh = b.node('GeometryNodeSetShadeSmooth')
    b.feed(sh.inputs['Geometry'], sm.outputs[0])
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

def film_material(kind):
    name = 'MCH Vacuum Film - ' + dict((k, l) for k, l, _d in FILMS).get(kind, 'Clear Plastic')
    m = bpy.data.materials.get(name)
    if m is not None:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    pb = m.node_tree.nodes.get('Principled BSDF')
    vals = {'CLEAR': dict(col=(0.92, 0.94, 0.96), rough=0.06, trans=0.93, coat=0.4, view=(0.82, 0.88, 0.95, 0.35)),
            'MILKY': dict(col=(0.86, 0.87, 0.89), rough=0.28, trans=0.6, coat=0.2, view=(0.85, 0.86, 0.88, 0.75)),
            'BLACK': dict(col=(0.018, 0.018, 0.02), rough=0.16, trans=0.0, coat=0.7, view=(0.03, 0.03, 0.035, 1.0))}[kind]
    if pb is not None:
        for sock, v in (('Base Color', (*vals['col'], 1.0)), ('Roughness', vals['rough']),
                        ('Transmission Weight', vals['trans']), ('Coat Weight', vals['coat']), ('IOR', 1.45)):
            try:
                pb.inputs[sock].default_value = v
            except (KeyError, TypeError):
                pass
    m.diffuse_color = vals['view']
    m.roughness = vals['rough']
    try:
        m.surface_render_method = 'DITHERED'
    except (AttributeError, TypeError):
        pass
    m['mch_vacuum_film'] = kind
    return m


# ---- the live settings -----------------------------------------------------------------------------------------------

def push(ob):
    """The film's settings into its modifier."""
    from . import geo_sculpt as gs
    mod = ob.modifiers.get(MOD) if ob is not None else None
    if mod is None or mod.node_group is None:
        return
    p = ob.mch_vacuum
    for sock, v in (('Size', float(ob.get('mch_vacuum_size', 1.0))), ('Hug', p.hug), ('Gap', p.gap / 100.0),
                    ('Detail', int(p.detail)), ('Creases', p.creases), ('Crease Size', p.crease_size / 100.0),
                    ('Seed', int(p.seed))):
        try:
            gs.set_input(mod, sock, v)
        except (KeyError, AttributeError, TypeError):
            pass
    mat = film_material(p.film)
    mats = ob.data.materials
    if not len(mats):
        mats.append(mat)
    elif ob.get('mch_vacuum_mat') != p.film:       # (a Film preset picked: its material; one from a page stays)
        mats[0] = mat
    ob['mch_vacuum_mat'] = p.film
    sync_material(ob)
    ob.update_tag()


def sync_material(ob):
    """The film's node Material = its first slot's (a Film preset, a Mech / Creature page preset, Blender's own slot).
    Returns True when it changed."""
    from . import geo_sculpt as gs
    mod = ob.modifiers.get(MOD)
    if mod is None or mod.node_group is None:
        return False
    m = next((s.material for s in ob.material_slots if s.material is not None), None)
    try:
        if gs.get_input(mod, 'Material') != m:
            gs.set_input(mod, 'Material', m)
            return True
    except (KeyError, AttributeError, TypeError):
        pass
    return False


@bpy.app.handlers.persistent
def _material_watch(_scene, _depsgraph=None):
    try:
        obs = bpy.context.scene.objects
    except AttributeError:
        return
    for ob in obs:
        if ob.get(KEY):
            sync_material(ob)


_BUSY = [False]
LIVE = ('hug', 'gap', 'detail', 'creases', 'crease_size', 'seed', 'film')


def _upd(self, context):
    if _BUSY[0]:
        return
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and is_film(ob):
        push(ob)
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
    detail: IntProperty(name='Detail', default=160, min=40, soft_max=320, max=600, update=_upd,
                        description='How fine the film is (steps across the parts\' size; more = finer, slower)')
    creases: FloatProperty(name='Creases', default=0.5, min=0.0, max=1.0, update=_upd,
                           description='Thin sharp creases where the film spans between the parts (the tension lines)')
    crease_size: FloatProperty(name='Crease Spacing %', default=4.0, min=0.3, max=15.0, update=_upd,
                               description='How far apart the creases are (a share of the size, in %)')
    seed: IntProperty(name='Seed', default=0, min=0, update=_upd, description='Another random set of creases')
    film: EnumProperty(name='Film', items=FILMS, default='CLEAR', update=_upd)


# ---- operators ------------------------------------------------------------------------------------------------------

def perform(context, parts=None):
    """The selected meshes sealed in one film (a new live object).  Returns (film, report)."""
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
    mod = film.modifiers.new(MOD, 'NODES')
    mod.node_group = build_tree(f'{TREE} - {film.name}', parts)
    _BUSY[0] = True
    try:
        for k in LIVE:
            setattr(film.mch_vacuum, k, getattr(st, k))
    finally:
        _BUSY[0] = False
    push(film)
    for o in context.selected_objects:
        o.select_set(False)
    film.select_set(True)
    context.view_layer.objects.active = film
    t0 = time.time()
    dg = context.evaluated_depsgraph_get()
    n = len(film.evaluated_get(dg).data.vertices)
    msg = (f'Vacuum Pack round {len(parts)} part(s): {n:,} film points ({time.time() - t0:.1f} s) - live: Hug, Gap, '
           f'Creases in the window; Apply makes it a plain mesh')
    return film, msg


def apply_film(context, film):
    mod = film.modifiers.get(MOD)
    ng = mod.node_group if mod else None
    with context.temp_override(object=film, active_object=film, selected_objects=[film]):
        bpy.ops.object.modifier_apply(modifier=MOD)
    from . import greeble_line
    greeble_line._only_used_slots(film.data)            # (the film's material only - no empty slot before it)
    if KEY in film:
        del film[KEY]
    if ng is not None and ng.users == 0:
        bpy.data.node_groups.remove(ng)


class MCH_OT_vacuum_pack(bpy.types.Operator):
    """Seal the selected meshes in one plastic film (vacuum packing): pulled flat onto them, taut over the gaps, thin
    creases where it spans; live - Hug, Gap, Creases, Film in the window"""
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


class MCH_OT_vacuum_apply(bpy.types.Operator):
    """The selected Vacuum Pack as a plain mesh (no longer live)"""
    bl_idname = 'mch.vacuum_apply'
    bl_label = 'Apply Vacuum Pack'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and active_film(context) is not None

    def execute(self, context):
        film = active_film(context)
        try:
            apply_film(context, film)
        except RuntimeError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, f'{film.name}: a plain mesh ({len(film.data.polygons):,} faces)')
        return {'FINISHED'}


def draw(layout, context):
    """The Vacuum Pack box (in the Cloth Drape window)."""
    film = active_film(context)
    p = film.mch_vacuum if film is not None else context.scene.mch_vacuum
    box = layout.box()
    box.label(text='Vacuum Pack: the selected meshes sealed in one film', icon='MOD_SHRINKWRAP')
    if film is not None:
        box.label(text=f'{film.name}: live round {len(film_parts(film))} part(s)', icon='MODIFIER')
    else:
        box.operator('mch.vacuum_pack', text='Vacuum Pack Selected', icon='MOD_SHRINKWRAP')
    box.row(align=True).prop(p, 'film', expand=True)
    col = box.column(align=True)
    col.prop(p, 'hug', slider=True)
    col.prop(p, 'creases', slider=True)
    col.prop(p, 'crease_size', slider=True)
    col.prop(p, 'gap', slider=True)
    col.prop(p, 'detail')
    col.prop(p, 'seed')
    if film is not None:
        box.operator('mch.vacuum_apply', text='Apply (a plain mesh)', icon='CHECKMARK')


CLASSES = (MCH_PG_Vacuum, MCH_OT_vacuum_pack, MCH_OT_vacuum_apply)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_vacuum = PointerProperty(type=MCH_PG_Vacuum)
    bpy.types.Object.mch_vacuum = PointerProperty(type=MCH_PG_Vacuum)
    if _material_watch not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_material_watch)


def unregister():
    if _material_watch in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_material_watch)
    for attr in ('mch_vacuum',):
        for T in (bpy.types.Scene, bpy.types.Object):
            if hasattr(T, attr):
                delattr(T, attr)
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
