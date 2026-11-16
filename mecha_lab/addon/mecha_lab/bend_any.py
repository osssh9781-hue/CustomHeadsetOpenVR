"""0.24.180 Bend any part, later (user, the Base Mesh window's Bend card: "내가 만든 오브젝트를 나중에 내가 벤드로 휠 수
있는 거 만들어 줄래, 각도나 이런 거 다 조절 가능하게? 여기 있는 메뉴 다 넣어 줘"): the same card for any mesh part -
Band / Angle, Bend Up / Down, Bend Sideways, Bend Position, Bend Direction (+ Angle: Fold Width) - live: a Geometry
Nodes modifier at the end of its stack (what is live on it stays live), Remove takes it off, Freeze makes the part a
plain mesh as shown.

The bend works in the part's own frame, measured when it is added (the part as it was then): its length the longest
side (turned round the up side by Bend Direction), up its thinnest side, bent round its middle thickness (the inside
squeezed, the outside stretched - like the Base Mesh's).  Band: evenly all along (the Position the spot that stays
put); Angle: in a short span at the Position (Fold Width), both sides straight.  Up / Down then Sideways.

Each bend: over its span [r0, r1] (along the length, from the bend spot) the curvature k = angle / (r1 - r0); a
point (u along, z off the middle) -> uc = clamp(u, r0, r1), phi = k uc, the arc point (uc sin phi / phi,
uc (1 - cos phi) / phi), then on straight by u - uc along the tangent and z along the normal there.
"""
from __future__ import annotations

import json
import math

import bpy
import numpy as np
from bpy.props import EnumProperty, FloatProperty, PointerProperty, StringProperty

MOD = 'MCH_Bend'
TREE = 'MCH Bend'
TREE_V = 1


class _B:
    def __init__(self, ng):
        self.N, self.L = ng.nodes, ng.links

    def feed(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.L.new(v, sock)
        else:
            sock.default_value = v

    def m(self, op, a, b=None):
        n = self.N.new('ShaderNodeMath')
        n.operation = op
        self.feed(n.inputs[0], a)
        if b is not None:
            self.feed(n.inputs[1], b)
        return n.outputs[0]

    def v(self, op, a, b=None, scale=None):
        n = self.N.new('ShaderNodeVectorMath')
        n.operation = op
        self.feed(n.inputs[0], a)
        if b is not None:
            self.feed(n.inputs[1], b)
        if scale is not None:
            self.feed(n.inputs['Scale'], scale)
        return n.outputs['Value' if op in ('DOT_PRODUCT', 'LENGTH') else 'Vector']

    def clamp(self, x, lo, hi):
        n = self.N.new('ShaderNodeClamp')
        self.feed(n.inputs['Value'], x)
        self.feed(n.inputs['Min'], lo)
        self.feed(n.inputs['Max'], hi)
        return n.outputs[0]


def _bend(b, u, z, ang, r0, r1, h):
    """One bend in the (u, z) plane: (u', z')."""
    span = b.m('MAXIMUM', b.m('SUBTRACT', r1, r0), 1e-9)
    k = b.m('DIVIDE', ang, span)
    uc = b.clamp(u, r0, r1)
    phi = b.m('MULTIPLY', k, uc)
    ps = b.m('ADD', phi, 1e-7)
    sn, cs = b.m('SINE', phi), b.m('COSINE', phi)
    au = b.m('DIVIDE', b.m('MULTIPLY', uc, b.m('SINE', ps)), ps)
    az = b.m('DIVIDE', b.m('MULTIPLY', uc, b.m('SUBTRACT', 1.0, b.m('COSINE', ps))), ps)
    t = b.m('SUBTRACT', u, uc)
    zz = b.m('SUBTRACT', z, h)
    u2 = b.m('ADD', au, b.m('SUBTRACT', b.m('MULTIPLY', t, cs), b.m('MULTIPLY', zz, sn)))
    z2 = b.m('ADD', h, b.m('ADD', az, b.m('ADD', b.m('MULTIPLY', t, sn), b.m('MULTIPLY', zz, cs))))
    return u2, z2


def node_group():
    ng = bpy.data.node_groups.get(TREE)
    if ng is not None and ng.get('mch_v') == TREE_V:
        return ng
    if ng is None:
        ng = bpy.data.node_groups.new(TREE, 'GeometryNodeTree')
    ng.nodes.clear()
    for s_ in list(ng.interface.items_tree):
        ng.interface.remove(s_)
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    for name in ('Origin', 'Length Dir', 'Width Dir', 'Up Dir'):
        ng.interface.new_socket(name, in_out='INPUT', socket_type='NodeSocketVector')
    for name in ('Up Angle', 'Side Angle', 'From', 'To', 'Mid Up', 'Mid Side'):
        ng.interface.new_socket(name, in_out='INPUT', socket_type='NodeSocketFloat')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    b = _B(ng)
    gi = b.N.new('NodeGroupInput')
    go = b.N.new('NodeGroupOutput')
    pos = b.N.new('GeometryNodeInputPosition').outputs[0]
    d = b.v('SUBTRACT', pos, gi.outputs['Origin'])
    u = b.v('DOT_PRODUCT', d, gi.outputs['Length Dir'])
    w = b.v('DOT_PRODUCT', d, gi.outputs['Width Dir'])
    z = b.v('DOT_PRODUCT', d, gi.outputs['Up Dir'])
    r0, r1 = gi.outputs['From'], gi.outputs['To']
    u1, z1 = _bend(b, u, z, gi.outputs['Up Angle'], r0, r1, gi.outputs['Mid Up'])
    u2, w2 = _bend(b, u1, w, gi.outputs['Side Angle'], r0, r1, gi.outputs['Mid Side'])
    p = b.v('ADD', gi.outputs['Origin'], b.v('SCALE', gi.outputs['Length Dir'], scale=u2))
    p = b.v('ADD', p, b.v('SCALE', gi.outputs['Width Dir'], scale=w2))
    p = b.v('ADD', p, b.v('SCALE', gi.outputs['Up Dir'], scale=z1))
    sp = b.N.new('GeometryNodeSetPosition')
    b.L.new(gi.outputs['Geometry'], sp.inputs['Geometry'])
    b.L.new(p, sp.inputs['Position'])
    b.L.new(sp.outputs['Geometry'], go.inputs['Geometry'])
    ng['mch_v'] = TREE_V
    return ng


def _upd(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object):
        push(ob)


class MCH_PG_BendAny(bpy.types.PropertyGroup):
    style: EnumProperty(name='Bend Style', default='SMOOTH', update=_upd,
                        items=(('SMOOTH', 'Band', 'Bends evenly along the whole length, like a band'),
                               ('ANGLE', 'Angle', 'A fold at one spot, the two sides stay straight')))
    up: FloatProperty(name='Bend Up / Down', default=0.0, min=math.radians(-300), max=math.radians(300),
                      subtype='ANGLE', update=_upd, description='Bend along its length: + both ends rise, - both drop')
    side: FloatProperty(name='Bend Sideways', default=0.0, min=math.radians(-300), max=math.radians(300),
                        subtype='ANGLE', update=_upd,
                        description='Bend along its length to the left / right (like a banana seen from above)')
    pos: FloatProperty(name='Bend Position', default=0.0, min=-0.9, max=0.9, subtype='FACTOR', update=_upd,
                       description='Where along the length it bends (0 = the middle; Angle: where the fold is)')
    axis: FloatProperty(name='Bend Direction', default=0.0, min=math.radians(-90), max=math.radians(90),
                        subtype='ANGLE', update=_upd,
                        description='Turn the bend direction (0 = along the longest side of the part)')
    fold: FloatProperty(name='Fold Width', default=0.12, min=0.005, max=0.8, subtype='FACTOR', update=_upd,
                        description='Angle: how long the fold is (a share of the length; small = sharp)')
    frame: StringProperty(default='', options={'HIDDEN'})


def has(ob):
    return ob is not None and ob.type == 'MESH' and ob.modifiers.get(MOD) is not None


def _measure(context, ob):
    """The part's frame as it is now (its modifiers, not a bend of ours): centre, the 3 axes by size, the corners."""
    from . import light_copies as lc
    mod = ob.modifiers.get(MOD)
    was = mod.show_viewport if mod is not None else None
    if mod is not None:
        mod.show_viewport = False
    try:
        dg = context.evaluated_depsgraph_get()
        dg.update()
        ev = lc.full(ob, dg)
        me = ev.to_mesh()
        try:
            co = np.empty(len(me.vertices) * 3, np.float64)
            me.vertices.foreach_get('co', co)
        finally:
            ev.to_mesh_clear()
    finally:
        if mod is not None:
            mod.show_viewport = was
    co = co.reshape(-1, 3)
    if not len(co):
        co = np.zeros((1, 3))
    lo, hi = co.min(0), co.max(0)
    ext = hi - lo
    order = np.argsort(ext)                           # (thinnest, middle, longest)
    return {'centre': list((lo + hi) / 2), 'up': int(order[0]), 'width': int(order[1]), 'length': int(order[2]),
            'pts': co[:: max(1, len(co) // 4000)].tolist()}


def _frame(ob):
    try:
        return json.loads(ob.mch_bend.frame or '{}')
    except ValueError:
        return {}


def push(ob):
    """The values into the modifier: the frame turned by Bend Direction, the span (Band: all along; Angle: Fold
    Width at the Position), the middle thickness."""
    mod = ob.modifiers.get(MOD)
    fr = _frame(ob)
    if mod is None or not fr:
        return
    from . import geo_sculpt as gs
    p = ob.mch_bend
    E = np.eye(3)
    L0, W0, Z = E[fr['length']], E[fr['width']], E[fr['up']]
    ca, sa = math.cos(p.axis), math.sin(p.axis)
    U = L0 * ca + W0 * sa
    W = np.cross(Z, U)
    if float(np.dot(W, W0)) < 0 and abs(sa) < 1e-9:
        W = -W
    C = np.array(fr['centre'])
    pts = np.array(fr['pts'])
    d = pts - C
    us, ws, zs = d @ U, d @ W, d @ Z
    lo, hi = float(us.min()), float(us.max())
    half = max((hi - lo) / 2.0, 1e-9)
    mid = (lo + hi) / 2.0 + p.pos * half
    O = C + U * mid
    if p.style == 'ANGLE':
        s = max(p.fold * (hi - lo) / 2.0, 1e-6)
        r0, r1 = -s, s
    else:
        r0, r1 = lo - mid, hi - mid
    vals = {'Origin': tuple(O), 'Length Dir': tuple(U), 'Width Dir': tuple(W), 'Up Dir': tuple(Z),
            'Up Angle': float(p.up), 'Side Angle': float(p.side), 'From': float(r0), 'To': float(r1),
            'Mid Up': float((zs.min() + zs.max()) / 2.0), 'Mid Side': float((ws.min() + ws.max()) / 2.0)}
    for k, v in vals.items():
        gs.set_input(mod, k, v)
    ob.update_tag()


def add(context, ob):
    """A live bend on ``ob`` (at the end of its stack), measured as it is now."""
    if has(ob):
        return ob.modifiers[MOD]
    ob.mch_bend.frame = json.dumps(_measure(context, ob))
    mod = ob.modifiers.new(MOD, 'NODES')
    mod.node_group = node_group()
    push(ob)
    return mod


def remove(ob):
    mod = ob.modifiers.get(MOD)
    if mod is not None:
        ob.modifiers.remove(mod)
    ob.mch_bend.frame = ''


def apply(context, ob):
    """Freeze (also the Live Stack's Apply): the part as shown, a plain mesh - everything on it applied."""
    from . import light_copies as lc
    dg = context.evaluated_depsgraph_get()
    dg.update()
    me = bpy.data.meshes.new_from_object(lc.full(ob, dg), preserve_all_data_layers=True, depsgraph=dg)
    old = ob.data
    me.name = old.name
    if not len(me.materials):
        for mt in old.materials:
            me.materials.append(mt)
    for m in list(ob.modifiers):
        ob.modifiers.remove(m)
    ob.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    ob.mch_bend.frame = ''
    return True


class MCH_OT_bend_add(bpy.types.Operator):
    """Bend the selected part (live): Band / Angle, Up / Down, Sideways, Position, Direction - at the end of its stack,
    so what is live on it stays live"""
    bl_idname = 'mch.bend_add'
    bl_label = 'Bend'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obs = [o for o in context.selected_objects if o.type == 'MESH'] or (
            [context.active_object] if context.active_object is not None and context.active_object.type == 'MESH'
            else [])
        if not obs:
            self.report({'WARNING'}, 'Select a part first')
            return {'CANCELLED'}
        for ob in obs:
            add(context, ob)
        self.report({'INFO'}, f'Bend on {len(obs)} part{"s" if len(obs) != 1 else ""} - its values in the Live Stack')
        return {'FINISHED'}


class MCH_OT_bend_remove(bpy.types.Operator):
    """Take the bend off the selected part"""
    bl_idname = 'mch.bend_remove'
    bl_label = 'Remove Bend'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ob = context.active_object
        if not has(ob):
            return {'CANCELLED'}
        remove(ob)
        return {'FINISHED'}


class MCH_OT_bend_freeze(bpy.types.Operator):
    """Freeze: the part as shown (bent), a plain mesh - everything live on it applied"""
    bl_idname = 'mch.bend_freeze'
    bl_label = 'Freeze'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ob = context.active_object
        if not has(ob):
            return {'CANCELLED'}
        apply(context, ob)
        self.report({'INFO'}, f'"{ob.name}" frozen: a plain mesh, bent')
        return {'FINISHED'}


def draw(layout, context, ob=None):
    """The Bend card (the Base Mesh window's): on any part."""
    ob = ob if ob is not None else context.active_object
    if ob is None or ob.type != 'MESH':
        return
    col = layout.column(align=True)
    col.label(text='Bend')
    if not has(ob):
        col.operator('mch.bend_add', text='Bend', icon='MOD_SIMPLEDEFORM')
        return
    p = ob.mch_bend
    row = col.row(align=True)
    row.prop_enum(p, 'style', 'SMOOTH')
    row.prop_enum(p, 'style', 'ANGLE')
    col.prop(p, 'up')
    col.prop(p, 'side')
    col.prop(p, 'pos')
    col.prop(p, 'axis')
    if p.style == 'ANGLE':
        col.prop(p, 'fold')
    row = col.row(align=True)
    row.operator('mch.bend_remove', text='Remove Bend')
    row.operator('mch.bend_freeze', text='Freeze')


CLASSES = (MCH_PG_BendAny, MCH_OT_bend_add, MCH_OT_bend_remove, MCH_OT_bend_freeze)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Object.mch_bend = PointerProperty(type=MCH_PG_BendAny)


def unregister():
    if hasattr(bpy.types.Object, 'mch_bend'):
        del bpy.types.Object.mch_bend
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
