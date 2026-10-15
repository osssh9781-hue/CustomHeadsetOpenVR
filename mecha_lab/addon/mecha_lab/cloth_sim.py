"""0.23.8 Cloth Sim: a light Geometry Nodes cloth simulation (simulation zone, position based).

Every frame (Steps sub steps): gravity -> keep every edge at its rest length (Iterations
Jacobi passes over the neighbours) -> bending (smooths the small kinks) -> collide with
the body (Collider, kept Thickness away along its surface normal) -> pinned points stay.
Slack makes the cloth longer than the space it sits in, so it buckles into real folds.

``simulate`` plays the frames and bakes the result into the mesh (the modifier goes away),
so the scene keeps a plain mesh.  Pure Geometry Nodes - tested headless.
"""
from __future__ import annotations

import bpy

GROUP = 'MCH_ClothSim'
MOD = 'MCH_ClothSim'
VERSION = 3
MAXV = 8                     # neighbours per point the constraints look at (quads / triangles: 4 .. 8)
EDGE_ATTR = 'mch_edge_dist'  # border distance written by the Cloth Plate
INPUTS = (('Collider', 'NodeSocketObject', None, None, None),
          ('Gravity', 'NodeSocketFloat', 9.8, 0.0, 100.0),
          ('Steps', 'NodeSocketInt', 4, 1, 20),
          ('Iterations', 'NodeSocketInt', 8, 1, 40),
          ('Stiffness', 'NodeSocketFloat', 1.0, 0.0, 1.0),
          ('Bend', 'NodeSocketFloat', 0.25, 0.0, 1.0),
          ('Slack', 'NodeSocketFloat', 0.12, 0.0, 1.0),
          ('Thickness', 'NodeSocketFloat', 0.01, 0.0, 10.0),
          ('Damping', 'NodeSocketFloat', 0.06, 0.0, 1.0),
          ('Friction', 'NodeSocketFloat', 0.6, 0.0, 1.0),
          ('Pin Mode', 'NodeSocketInt', 1, 0, 2),          # 0 none, 1 border, 2 top band (world up)
          ('Pin Width', 'NodeSocketFloat', 0.05, 0.0, 100.0))
PIN_MODES = (('NONE', 'None', 'Nothing pinned: the cloth falls onto the body'),
             ('BORDER', 'Border', 'The border stays where it is (a sewn-on panel)'),
             ('TOP', 'Top', 'A band at the top stays (a hanging sleeve / skirt)'))


def _m(N, L, op, a=None, b=None, va=None, vb=None, clamp=False):
    n = N.new('ShaderNodeMath')
    n.operation = op
    n.use_clamp = clamp
    for i, (src, val) in enumerate(((a, va), (b, vb))):
        if src is not None:
            L.new(src, n.inputs[i])
        elif val is not None:
            n.inputs[i].default_value = val
    return n.outputs[0]


def _v(N, L, op, a=None, b=None, scale=None, vb=None):
    n = N.new('ShaderNodeVectorMath')
    n.operation = op
    if a is not None:
        L.new(a, n.inputs[0])
    if b is not None:
        L.new(b, n.inputs[1])
    elif vb is not None:
        n.inputs[1].default_value = vb
    if scale is not None:
        L.new(scale, n.inputs['Scale'])
    if op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE'):
        return n.outputs['Value']
    return n.outputs['Vector']


def _named(N, L, name, dtype='FLOAT'):
    n = N.new('GeometryNodeInputNamedAttribute')
    n.data_type = dtype
    n.inputs['Name'].default_value = name
    return n


def _store(N, L, geo, name, value, dtype='FLOAT', domain='POINT'):
    n = N.new('GeometryNodeStoreNamedAttribute')
    n.data_type = dtype
    n.domain = domain
    L.new(geo, n.inputs['Geometry'])
    n.inputs['Name'].default_value = name
    L.new(value, n.inputs['Value'])
    return n.outputs['Geometry']


def _setpos(N, L, geo, pos):
    n = N.new('GeometryNodeSetPosition')
    L.new(geo, n.inputs['Geometry'])
    L.new(pos, n.inputs['Position'])
    return n.outputs['Geometry']


def _sample(N, L, geo, value, index, dtype='FLOAT_VECTOR', domain='POINT'):
    n = N.new('GeometryNodeSampleIndex')
    n.data_type = dtype
    n.domain = domain
    L.new(geo, n.inputs['Geometry'])
    L.new(value, n.inputs['Value'])
    L.new(index, n.inputs['Index'])
    return n.outputs[0]


def _mix_v(N, L, a, b, w):
    """a + (b - a) * w  (w a float field)"""
    return _v(N, L, 'ADD', a, _v(N, L, 'SCALE', _v(N, L, 'SUBTRACT', b, a), scale=w))


def _zone(N, kind):
    zi = N.new('GeometryNode%sInput' % kind)
    zo = N.new('GeometryNode%sOutput' % kind)
    zi.pair_with_output(zo)
    return zi, zo


def build_group():
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
        if default is not None:
            it.default_value = default
            it.min_value, it.max_value = lo, hi
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gin, gout = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
    I = {name: gin.outputs[name] for name, *_r in INPUTS}
    pos = N.new('GeometryNodeInputPosition').outputs[0]
    idx = N.new('GeometryNodeInputIndex').outputs[0]

    # ---- set-up (first frame): rest lengths (x Slack), start positions, pin weights, zero velocity
    ev = N.new('GeometryNodeInputMeshEdgeVertices')
    elen = _v(N, L, 'DISTANCE', ev.outputs['Position 1'], ev.outputs['Position 2'])
    geo = _store(N, L, gin.outputs['Geometry'], 'mch_rest', _m(N, L, 'MULTIPLY', elen, _m(
        N, L, 'ADD', va=1.0, b=I['Slack'])), domain='EDGE')
    geo = _store(N, L, geo, 'mch_p0', pos, 'FLOAT_VECTOR')
    zero = N.new('ShaderNodeCombineXYZ').outputs[0]
    geo = _store(N, L, geo, 'mch_vel', zero, 'FLOAT_VECTOR')
    # pins: border (Cloth Plate border distance) or a top band (world up)
    bd = _named(N, L, EDGE_ATTR)
    pw = _m(N, L, 'MAXIMUM', I['Pin Width'], vb=1e-6)
    pin_border = _m(N, L, 'MULTIPLY', _m(N, L, 'SUBTRACT', va=1.0, b=_m(N, L, 'DIVIDE', bd.outputs['Attribute'], pw,
                                                                          clamp=True)), bd.outputs['Exists'])
    selfo = N.new('GeometryNodeSelfObject')
    so = N.new('GeometryNodeObjectInfo')
    L.new(selfo.outputs[0], so.inputs['Object'])
    tp = N.new('FunctionNodeTransformPoint')
    L.new(pos, tp.inputs['Vector'])
    L.new(so.outputs['Transform'], tp.inputs['Transform'])
    wz = N.new('ShaderNodeSeparateXYZ')
    L.new(tp.outputs[0], wz.inputs[0])
    st = N.new('GeometryNodeAttributeStatistic')
    st.data_type = 'FLOAT'
    L.new(gin.outputs['Geometry'], st.inputs['Geometry'])
    L.new(wz.outputs['Z'], st.inputs['Attribute'])
    pin_top = _m(N, L, 'GREATER_THAN', wz.outputs['Z'], _m(N, L, 'SUBTRACT', st.outputs['Max'], I['Pin Width']))
    psw = N.new('GeometryNodeIndexSwitch')
    psw.data_type = 'FLOAT'
    while len(psw.index_switch_items) < 3:
        psw.index_switch_items.new()
    L.new(I['Pin Mode'], psw.inputs['Index'])
    psw.inputs[1].default_value = 0.0
    L.new(pin_border, psw.inputs[2])
    L.new(pin_top, psw.inputs[3])
    geo = _store(N, L, geo, 'mch_pin', psw.outputs[0])

    # world down in object space
    inv = N.new('FunctionNodeInvertRotation')
    L.new(so.outputs['Rotation'], inv.inputs[0])
    rv = N.new('FunctionNodeRotateVector')
    L.new(inv.outputs[0], rv.inputs['Rotation'])
    rv.inputs['Vector'].default_value = (0.0, 0.0, -1.0)
    down = rv.outputs[0]
    # collider in this object's space
    col = N.new('GeometryNodeObjectInfo')
    col.transform_space = 'RELATIVE'
    L.new(I['Collider'], col.inputs['Object'])
    cgeo = col.outputs['Geometry']

    sim_in, sim_out = _zone(N, 'Simulation')
    L.new(geo, sim_in.inputs['Geometry'])
    dts = _m(N, L, 'DIVIDE', sim_in.outputs['Delta Time'], _m(N, L, 'MAXIMUM', I['Steps'], vb=1.0))
    step_in, step_out = _zone(N, 'Repeat')
    L.new(I['Steps'], step_in.inputs['Iterations'])
    L.new(sim_in.outputs['Geometry'], step_in.inputs['Geometry'])
    g = step_in.outputs['Geometry']
    pin = _named(N, L, 'mch_pin').outputs['Attribute']
    p0 = _named(N, L, 'mch_p0', 'FLOAT_VECTOR').outputs['Attribute']
    vel = _named(N, L, 'mch_vel', 'FLOAT_VECTOR').outputs['Attribute']
    # integrate
    v1 = _v(N, L, 'ADD', _v(N, L, 'SCALE', vel, scale=_m(N, L, 'SUBTRACT', va=1.0, b=I['Damping'])),
            _v(N, L, 'SCALE', down, scale=_m(N, L, 'MULTIPLY', I['Gravity'], dts)))
    g = _store(N, L, g, 'mch_prev', pos, 'FLOAT_VECTOR')
    pred = _mix_v(N, L, _v(N, L, 'ADD', pos, _v(N, L, 'SCALE', v1, scale=dts)), p0, pin)
    g = _setpos(N, L, g, pred)
    # constraints
    it_in, it_out = _zone(N, 'Repeat')
    L.new(I['Iterations'], it_in.inputs['Iterations'])
    L.new(g, it_in.inputs['Geometry'])
    cg_ = it_in.outputs['Geometry']
    rest = _named(N, L, 'mch_rest').outputs['Attribute']
    corr = None
    total = None
    for j in range(MAXV):
        eov = N.new('GeometryNodeEdgesOfVertex')
        eov.inputs['Sort Index'].default_value = j
        L.new(idx, eov.inputs['Vertex Index'])
        total = eov.outputs['Total']
        valid = _m(N, L, 'LESS_THAN', _m(N, L, 'ADD', va=float(j), vb=0.0), total)
        ei = eov.outputs['Edge Index']
        a = _sample(N, L, cg_, ev.outputs['Vertex Index 1'], ei, 'INT', 'EDGE')
        b = _sample(N, L, cg_, ev.outputs['Vertex Index 2'], ei, 'INT', 'EDGE')
        r = _sample(N, L, cg_, rest, ei, 'FLOAT', 'EDGE')
        is_a = N.new('FunctionNodeCompare')
        is_a.data_type = 'INT'
        is_a.operation = 'EQUAL'
        L.new(a, is_a.inputs[2])
        L.new(idx, is_a.inputs[3])
        oth = N.new('GeometryNodeSwitch')
        oth.input_type = 'INT'
        L.new(is_a.outputs[0], oth.inputs['Switch'])
        L.new(a, oth.inputs['False'])
        L.new(b, oth.inputs['True'])
        op_ = _sample(N, L, cg_, pos, oth.outputs[0])
        d = _v(N, L, 'SUBTRACT', op_, pos)
        ln = _m(N, L, 'MAXIMUM', _v(N, L, 'LENGTH', d), vb=1e-9)
        k = _m(N, L, 'MULTIPLY', _m(N, L, 'SUBTRACT', va=1.0, b=_m(N, L, 'DIVIDE', r, ln)), valid)
        c = _v(N, L, 'SCALE', d, scale=_m(N, L, 'MULTIPLY', k, vb=0.5))
        corr = c if corr is None else _v(N, L, 'ADD', corr, c)
    cnt = _m(N, L, 'MAXIMUM', _m(N, L, 'MINIMUM', total, vb=float(MAXV)), vb=1.0)
    pn = _v(N, L, 'ADD', pos, _v(N, L, 'SCALE', corr, scale=_m(N, L, 'DIVIDE', _m(
        N, L, 'MULTIPLY', I['Stiffness'], vb=1.6), cnt)))
    pn = _mix_v(N, L, pn, p0, pin)
    cg2 = _setpos(N, L, cg_, pn)
    # collision: stay Thickness outside the body surface
    near = N.new('GeometryNodeProximity')
    near.target_element = 'FACES'
    L.new(cgeo, near.inputs[0])
    L.new(pos, near.inputs['Source Position'])
    sns = N.new('GeometryNodeSampleNearestSurface')
    sns.data_type = 'FLOAT_VECTOR'
    L.new(cgeo, sns.inputs['Mesh'])
    L.new(N.new('GeometryNodeInputNormal').outputs[0], sns.inputs['Value'])
    L.new(pos, sns.inputs['Sample Position'])
    nq = _v(N, L, 'NORMALIZE', sns.outputs['Value'])
    sd = _v(N, L, 'DOT_PRODUCT', _v(N, L, 'SUBTRACT', pos, near.outputs['Position']), nq)
    push = _m(N, L, 'MAXIMUM', _m(N, L, 'SUBTRACT', I['Thickness'], sd), vb=0.0)
    has_col = N.new('GeometryNodeAttributeDomainSize')
    L.new(cgeo, has_col.inputs['Geometry'])
    push = _m(N, L, 'MULTIPLY', push, _m(N, L, 'GREATER_THAN', has_col.outputs['Point Count'], vb=0.5))
    # friction: where it touches, most of the sliding along the body is taken back
    prev_i = _named(N, L, 'mch_prev', 'FLOAT_VECTOR').outputs['Attribute']
    disp = _v(N, L, 'SUBTRACT', pos, prev_i)
    tang = _v(N, L, 'SUBTRACT', disp, _v(N, L, 'SCALE', nq, scale=_v(N, L, 'DOT_PRODUCT', disp, nq)))
    touch = _m(N, L, 'GREATER_THAN', push, vb=0.0)
    fric = _v(N, L, 'SCALE', tang, scale=_m(N, L, 'MULTIPLY', _m(N, L, 'MULTIPLY', touch, I['Friction']), vb=-1.0))
    cg2 = _setpos(N, L, cg2, _v(N, L, 'ADD', _v(N, L, 'ADD', pos, _v(N, L, 'SCALE', nq, scale=push)), fric))
    L.new(cg2, it_out.inputs['Geometry'])
    g = it_out.outputs['Geometry']
    # bending (once per step): only the part of the neighbours' average along the normal - it irons
    # out kinks without shrinking the cloth in its own plane
    blur = N.new('GeometryNodeBlurAttribute')
    blur.data_type = 'FLOAT_VECTOR'
    L.new(pos, blur.inputs['Value'])
    blur.inputs['Iterations'].default_value = 1
    nrm = N.new('GeometryNodeInputNormal').outputs[0]
    off = _v(N, L, 'SUBTRACT', blur.outputs['Value'], pos)
    offn = _v(N, L, 'SCALE', nrm, scale=_v(N, L, 'DOT_PRODUCT', off, nrm))
    pb = _v(N, L, 'ADD', pos, _v(N, L, 'SCALE', offn, scale=_m(N, L, 'MULTIPLY', I['Bend'], _m(
        N, L, 'SUBTRACT', va=1.0, b=pin))))
    g = _setpos(N, L, g, pb)
    # velocity from the move
    prev = _named(N, L, 'mch_prev', 'FLOAT_VECTOR').outputs['Attribute']
    # (the first frame has Delta Time 0: the set-up moves are not a velocity)
    inv_dt = _m(N, L, 'MULTIPLY', _m(N, L, 'DIVIDE', va=1.0, b=_m(N, L, 'MAXIMUM', dts, vb=1e-6)),
                _m(N, L, 'GREATER_THAN', dts, vb=1e-6))
    g = _store(N, L, g, 'mch_vel', _v(N, L, 'SCALE', _v(N, L, 'SUBTRACT', pos, prev), scale=inv_dt), 'FLOAT_VECTOR')
    L.new(g, step_out.inputs['Geometry'])
    L.new(step_out.outputs['Geometry'], sim_out.inputs['Geometry'])
    L.new(sim_out.outputs['Geometry'], gout.inputs['Geometry'])
    ng['mch_version'] = VERSION
    return ng


def _ident(name):
    ng = build_group()
    for it in ng.interface.items_tree:
        if getattr(it, 'in_out', '') == 'INPUT' and it.name == name:
            return it.identifier
    raise KeyError(name)


def has_sim(ob):
    return ob is not None and ob.type == 'MESH' and ob.modifiers.get(MOD) is not None


def attach(ob, collider=None, first=True, **values):
    """Add the cloth sim modifier (first in the stack: the procedural layers see the simulated shape)."""
    build_group()
    mod = ob.modifiers.get(MOD) or ob.modifiers.new(MOD, 'NODES')
    mod.node_group = bpy.data.node_groups[GROUP]
    if collider is not None:
        mod[_ident('Collider')] = collider
    for k, v in values.items():
        mod[_ident(k)] = v
    if first:
        ob.modifiers.move(ob.modifiers.find(mod.name), 0)
    return mod


def set_input(ob, name, value):
    ob.modifiers[MOD][_ident(name)] = value
    ob.update_tag()


def get_input(ob, name):
    return ob.modifiers[MOD][_ident(name)]


def simulate(context, ob, frames=40, bake=True):
    """Play the simulation ``frames`` frames from the scene start and (bake) keep the result as the mesh."""
    scene = context.scene
    keep = scene.frame_current
    start = scene.frame_start
    for f in range(start, start + frames + 1):
        scene.frame_set(f)
    if not bake:
        return None
    dg = context.evaluated_depsgraph_get()
    mod = ob.modifiers[MOD]
    # evaluate only up to the sim (later layers stay live)
    later = [m for m in ob.modifiers if m != mod]
    shown = [(m, m.show_viewport) for m in later]
    for m in later:
        m.show_viewport = False
    try:
        dg.update()
        ev = ob.evaluated_get(dg)
        me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    finally:
        for m, s in shown:
            m.show_viewport = s
    old = ob.data
    ob.data = me
    me.name = old.name
    ob.modifiers.remove(mod)
    for name in ('mch_rest', 'mch_p0', 'mch_vel', 'mch_pin', 'mch_prev'):
        a = me.attributes.get(name)
        if a is not None:
            me.attributes.remove(a)
    if old.users == 0:
        bpy.data.meshes.remove(old)
    scene.frame_set(keep)
    return me


# -----------------------------------------------------------------------------
# Operator: simulate the selected cloth layers (or any mesh) on their body and bake
# -----------------------------------------------------------------------------

def collider_for(ob):
    """The body a cloth layer was drawn on (Cloth Plate / Armor Plate source), or None."""
    name = ob.get('mch_wrinkle') if hasattr(ob, 'get') else None
    if isinstance(name, str) and name in bpy.data.objects:
        return bpy.data.objects[name]
    p = getattr(ob, 'mch_extract', None)
    src = getattr(p, 'source', None) if p is not None else None
    return src


class MCH_OT_cloth_sim(bpy.types.Operator):
    """Cloth Sim (Geometry Nodes): let the selected cloth layers fall and fold on their body, then bake
    the result into the mesh (the procedural layers on top stay live)"""
    bl_idname = 'mch.cloth_sim'
    bl_label = 'Cloth Sim'
    bl_options = {'REGISTER', 'UNDO'}
    frames: bpy.props.IntProperty(name='Frames', default=50, min=1, max=1000,
                                  description='How long the cloth falls / settles before the bake')
    slack: bpy.props.FloatProperty(name='Slack', default=0.15, min=0.0, max=1.0, subtype='FACTOR',
                                   description='Extra cloth length: more slack, more folds')
    gravity: bpy.props.FloatProperty(name='Gravity', default=9.8, min=0.0, max=100.0)
    bend: bpy.props.FloatProperty(name='Bend', default=0.3, min=0.0, max=1.0, subtype='FACTOR',
                                  description='Stiffness against bending: high = big soft folds, low = many small')
    pin_mode: bpy.props.EnumProperty(name='Pin', items=PIN_MODES, default='BORDER')
    pin_width: bpy.props.FloatProperty(name='Pin Width', default=0.03, min=0.0, soft_max=1.0, unit='LENGTH')
    keep_folds: bpy.props.BoolProperty(name='Keep procedural folds', default=False,
                                       description='Keep the drawn-in folds (Pinch 1 / 2) on top of the simulated ones')

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        done = 0
        for ob in [o for o in context.selected_objects if o.type == 'MESH']:
            col = collider_for(ob)
            attach(ob, col, Gravity=self.gravity, Slack=self.slack, Bend=self.bend,
                   **{'Pin Mode': [m[0] for m in PIN_MODES].index(self.pin_mode), 'Pin Width': self.pin_width,
                      'Thickness': max(ob.dimensions) * 0.004 if col is not None else 0.0})
            if not self.keep_folds:
                try:
                    from . import cloth_wrinkle as cw
                    if cw.is_wrinkle(ob):
                        cw.set_input(ob, 'Pinch', 0.0)
                        cw.set_input(ob, 'Pinch 2', 0.0)
                except (ImportError, KeyError):
                    pass
            simulate(context, ob, self.frames, bake=True)
            done += 1
        self.report({'INFO'}, f'Cloth Sim: {done} layer(s) simulated {self.frames} frames and baked')
        return {'FINISHED'}


CLASSES = (MCH_OT_cloth_sim,)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
