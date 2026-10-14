"""0.23.4 Creature Shell: Armor Plate made into a creature carapace.

The Shell button (bottom toolbar) is the Armor Plate tool with this layer on:
every new plate gets a live Geometry Nodes modifier (baked by the plate's Apply)
    Facets      hard random facets (each cell tilts its own way) - a bony, chipped look
    Bulge       lumpy, swollen surface (size = Bulge Size)
    Lift N/E/S/W  the plate edge on that side rises off the body (Lift Height / Width)
    Gravity     the raised parts sag toward world down
The plate's own popup (profile, chamfer, rims ...) still works; the Shell popup
sits on the other side of the plate.  ``build_group`` is tested headless.
"""
from __future__ import annotations

import math

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty
from mathutils import Matrix, Vector

GROUP = 'MCH_CreatureShell'
MOD = 'MCH_Shell'
VERSION = 12
INPUTS = (('Detail', 'NodeSocketInt', 5, 0, 6),
          ('Facets', 'NodeSocketFloat', 0.02, -100.0, 100.0),
          ('Facet Size', 'NodeSocketFloat', 0.2, 0.0001, 100.0),
          ('Bulge', 'NodeSocketFloat', 0.03, -100.0, 100.0),
          ('Bulge Size', 'NodeSocketFloat', 0.35, 0.0001, 100.0),
          ('Lift N', 'NodeSocketFloat', 0.0, 0.0, 1.0),
          ('Lift E', 'NodeSocketFloat', 0.0, 0.0, 1.0),
          ('Lift S', 'NodeSocketFloat', 0.0, 0.0, 1.0),
          ('Lift W', 'NodeSocketFloat', 0.0, 0.0, 1.0),
          ('Lift Height', 'NodeSocketFloat', 0.06, -100.0, 100.0),
          ('Lift Width', 'NodeSocketFloat', 0.35, 0.01, 1.0),
          ('Gravity', 'NodeSocketFloat', 0.0, 0.0, 5.0),
          ('Seed', 'NodeSocketInt', 1, 0, 100000),
          ('Up', 'NodeSocketVector', (0.0, 0.0, 1.0), -1.0, 1.0),
          ('U', 'NodeSocketVector', (1.0, 0.0, 0.0), -1.0, 1.0),
          ('V', 'NodeSocketVector', (0.0, 1.0, 0.0), -1.0, 1.0),
          # 0.23.5 (appended: the earlier sockets keep their identifiers)
          ('Organic', 'NodeSocketFloat', 1.0, 0.0, 3.0),
          ('Edge Shrink', 'NodeSocketFloat', 0.8, 0.0, 1.0),
          ('Shrink Width', 'NodeSocketFloat', 0.3, 0.0001, 100.0),
          ('Edge Irregular', 'NodeSocketFloat', 0.7, 0.0, 2.0))
SIZE_INPUTS = {'Facets', 'Facet Size', 'Bulge', 'Bulge Size', 'Lift Height', 'Shrink Width'}
DEFAULTS = {'Facets': 0.007, 'Facet Size': 0.2, 'Bulge': 0.006, 'Bulge Size': 0.35, 'Lift Height': 0.05,
            'Shrink Width': 0.14}


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


def _v(N, L, op, a=None, b=None, scale=None):
    n = N.new('ShaderNodeVectorMath')
    n.operation = op
    if a is not None:
        L.new(a, n.inputs[0])
    if b is not None:
        L.new(b, n.inputs[1])
    if scale is not None:
        L.new(scale, n.inputs['Scale'])
    return n.outputs['Value'] if op == 'DOT_PRODUCT' else n.outputs[0]


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
        it.default_value = default
        if sock != 'NodeSocketVector':
            it.min_value, it.max_value = lo, hi
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gin = N.new('NodeGroupInput')
    gout = N.new('NodeGroupOutput')
    I = {name: gin.outputs[name] for name, *_r in INPUTS}
    sub = N.new('GeometryNodeSubdivideMesh')
    L.new(gin.outputs['Geometry'], sub.inputs['Mesh'])
    L.new(I['Detail'], sub.inputs['Level'])
    pos = N.new('GeometryNodeInputPosition').outputs[0]
    u = _v(N, L, 'DOT_PRODUCT', pos, I['U'])
    v = _v(N, L, 'DOT_PRODUCT', pos, I['V'])
    nrm = N.new('GeometryNodeInputNormal').outputs[0]
    top = _m(N, L, 'DIVIDE', _m(N, L, 'SUBTRACT', _v(N, L, 'DOT_PRODUCT', nrm, I['Up']), vb=0.05), vb=0.35,
             clamp=True)
    seedx = _m(N, L, 'MULTIPLY', I['Seed'], vb=7.31)
    q = N.new('ShaderNodeCombineXYZ')
    L.new(_m(N, L, 'ADD', u, seedx), q.inputs[0])
    L.new(_m(N, L, 'ADD', v, _m(N, L, 'MULTIPLY', I['Seed'], vb=-3.17)), q.inputs[1])
    Q = q.outputs[0]
    fsz = _m(N, L, 'MAXIMUM', I['Facet Size'], vb=1e-6)
    fs = _m(N, L, 'DIVIDE', va=1.0, b=fsz)
    # organic: bend the cell edges with a low noise (domain warp ~ one cell wavelength)
    wn = N.new('ShaderNodeTexNoise')
    wn.inputs['Detail'].default_value = 1.5
    L.new(Q, wn.inputs['Vector'])
    L.new(_m(N, L, 'MULTIPLY', fs, vb=0.9), wn.inputs['Scale'])
    wc = _v(N, L, 'SUBTRACT', wn.outputs['Color'])
    wc.node.inputs[1].default_value = (0.5, 0.5, 0.5)
    wofs = _v(N, L, 'SCALE', wc, scale=_m(N, L, 'MULTIPLY', _m(N, L, 'MULTIPLY', I['Organic'], fsz), vb=0.5))
    Qw = _v(N, L, 'ADD', Q, wofs)

    def facet_field(scale, amp, groove=0.22):
        """every Voronoi cell a hard plate: a flat tilted top that drops into a groove at the cell
        edge (height stays continuous - no cliffs to tear thin triangles)"""
        vor = N.new('ShaderNodeTexVoronoi')
        vor.voronoi_dimensions = '2D'
        vor.feature = 'F1'
        L.new(Qw, vor.inputs['Vector'])
        L.new(scale, vor.inputs['Scale'])
        rel = N.new('ShaderNodeSeparateXYZ')
        L.new(_v(N, L, 'SUBTRACT', _v(N, L, 'SCALE', Qw, scale=scale), vor.outputs['Position']), rel.inputs[0])
        col = N.new('FunctionNodeSeparateColor')
        L.new(vor.outputs['Color'], col.inputs[0])
        tilt = _m(N, L, 'ADD', _m(N, L, 'MULTIPLY', _m(N, L, 'SUBTRACT', col.outputs[0], vb=0.5), rel.outputs['X']),
                  _m(N, L, 'MULTIPLY', _m(N, L, 'SUBTRACT', col.outputs[1], vb=0.5), rel.outputs['Y']))
        ved = N.new('ShaderNodeTexVoronoi')
        ved.voronoi_dimensions = '2D'
        ved.feature = 'DISTANCE_TO_EDGE'
        L.new(Qw, ved.inputs['Vector'])
        L.new(scale, ved.inputs['Scale'])
        mr = N.new('ShaderNodeMapRange')
        mr.interpolation_type = 'SMOOTHSTEP'
        L.new(ved.outputs['Distance'], mr.inputs['Value'])
        mr.inputs['From Min'].default_value = 0.0
        mr.inputs['From Max'].default_value = groove
        raw = _m(N, L, 'MAXIMUM', _m(N, L, 'ADD', _m(N, L, 'ADD', _m(N, L, 'MULTIPLY', tilt, vb=1.4), vb=1.0),
                                     _m(N, L, 'MULTIPLY', _m(N, L, 'SUBTRACT', col.outputs[2], vb=0.5), vb=0.5)),
                 vb=0.3)
        return _m(N, L, 'MULTIPLY', _m(N, L, 'MULTIPLY', mr.outputs['Result'], raw), vb=amp), col.outputs[2]

    f0, _r0 = facet_field(fs, 1.0)                               # wide plates inside
    f1, _r1 = facet_field(_m(N, L, 'MULTIPLY', fs, vb=1.6), 0.62, 0.28)
    f2, _r2 = facet_field(_m(N, L, 'MULTIPLY', fs, vb=2.6), 0.4, 0.34)  # narrow at the border
    # distance to the plate's side walls (where the top surface ends), roughened
    border = N.new('GeometryNodeSeparateGeometry')
    border.domain = 'POINT'
    L.new(sub.outputs['Mesh'], border.inputs['Geometry'])
    side_wall = _m(N, L, 'LESS_THAN', _m(N, L, 'ABSOLUTE', _v(N, L, 'DOT_PRODUCT', nrm, I['Up'])), vb=0.4)
    L.new(side_wall, border.inputs['Selection'])              # not the underside: it lies right below
    prox = N.new('GeometryNodeProximity')
    prox.target_element = 'POINTS'
    L.new(border.outputs['Selection'], prox.inputs[0])
    en = N.new('ShaderNodeTexNoise')
    en.inputs['Detail'].default_value = 2.0
    L.new(Q, en.inputs['Vector'])
    L.new(_m(N, L, 'MULTIPLY', fs, vb=1.7), en.inputs['Scale'])
    sw = _m(N, L, 'MAXIMUM', I['Shrink Width'], vb=1e-6)
    # irregular border line: two smooth noises (a cell-wise random jump would leave cliffs)
    en2 = N.new('ShaderNodeTexNoise')
    en2.inputs['Detail'].default_value = 1.0
    L.new(Q, en2.inputs['Vector'])
    L.new(_m(N, L, 'MULTIPLY', fs, vb=0.6), en2.inputs['Scale'])
    jit = _m(N, L, 'ADD', _m(N, L, 'MULTIPLY', _m(N, L, 'SUBTRACT', en.outputs['Fac'], vb=0.5), vb=1.0),
             _m(N, L, 'MULTIPLY', _m(N, L, 'SUBTRACT', en2.outputs['Fac'], vb=0.5), vb=1.4))
    # the noise moves the border line in and out (by up to ~Shrink Width), the inside stays wide
    dist = _m(N, L, 'ADD', prox.outputs['Distance'], _m(N, L, 'MULTIPLY', _m(N, L, 'MULTIPLY', jit, I['Edge Irregular']), sw))
    near = _m(N, L, 'SUBTRACT', va=1.0, b=_m(N, L, 'DIVIDE', dist, sw, clamp=True))
    t = _m(N, L, 'MULTIPLY', near, I['Edge Shrink'])

    def ramp(x, lo, hi):
        mr = N.new('ShaderNodeMapRange')
        mr.interpolation_type = 'SMOOTHSTEP'
        L.new(x, mr.inputs['Value'])
        mr.inputs['From Min'].default_value = lo
        mr.inputs['From Max'].default_value = hi
        return mr.outputs['Result']
    w1, w2 = ramp(t, 0.18, 0.4), ramp(t, 0.58, 0.8)

    def mix(a_, b_, w):
        return _m(N, L, 'ADD', a_, _m(N, L, 'MULTIPLY', _m(N, L, 'SUBTRACT', b_, a_), w))
    facet = _m(N, L, 'MULTIPLY', mix(mix(f0, f1, w1), f2, w2), I['Facets'])
    # bulge: soft lumps
    no = N.new('ShaderNodeTexNoise')
    no.inputs['Detail'].default_value = 2.0
    L.new(Q, no.inputs['Vector'])
    L.new(_m(N, L, 'DIVIDE', va=1.0, b=_m(N, L, 'MAXIMUM', I['Bulge Size'], vb=1e-6)), no.inputs['Scale'])
    bulge = _m(N, L, 'MULTIPLY', _m(N, L, 'DIVIDE', _m(N, L, 'MAXIMUM', _m(N, L, 'SUBTRACT', no.outputs['Fac'],
                                                                          vb=0.38), vb=0.0), vb=0.3), I['Bulge'])
    hsurf = _m(N, L, 'MULTIPLY', _m(N, L, 'ADD', facet, bulge), top)
    # edge lift N / E / S / W from the plate extents along U / V
    def stat(field):
        st = N.new('GeometryNodeAttributeStatistic')
        st.data_type = 'FLOAT'
        L.new(sub.outputs['Mesh'], st.inputs['Geometry'])
        L.new(field, st.inputs['Attribute'])
        return st.outputs['Min'], st.outputs['Max']
    umin, umax = stat(u)
    vmin, vmax = stat(v)
    wu = _m(N, L, 'MAXIMUM', _m(N, L, 'MULTIPLY', _m(N, L, 'SUBTRACT', umax, umin), I['Lift Width']), vb=1e-6)
    wv = _m(N, L, 'MAXIMUM', _m(N, L, 'MULTIPLY', _m(N, L, 'SUBTRACT', vmax, vmin), I['Lift Width']), vb=1e-6)

    def side(a, b, w, on):
        t = _m(N, L, 'DIVIDE', _m(N, L, 'SUBTRACT', a, b), w, clamp=True)
        return _m(N, L, 'MULTIPLY', _m(N, L, 'MULTIPLY', t, t), on)
    lift = _m(N, L, 'ADD', _m(N, L, 'ADD', side(v, _m(N, L, 'SUBTRACT', vmax, wv), wv, I['Lift N']),
                                side(_m(N, L, 'ADD', vmin, wv), v, wv, I['Lift S'])),
              _m(N, L, 'ADD', side(u, _m(N, L, 'SUBTRACT', umax, wu), wu, I['Lift E']),
                 side(_m(N, L, 'ADD', umin, wu), u, wu, I['Lift W'])))
    lift = _m(N, L, 'MULTIPLY', _m(N, L, 'MINIMUM', lift, vb=1.0), I['Lift Height'])
    h = _m(N, L, 'ADD', hsurf, lift)
    off = _v(N, L, 'SCALE', I['Up'], scale=h)
    # gravity: the raised parts sag toward world down (mostly along the plate)
    selfo = N.new('GeometryNodeSelfObject')
    oinfo = N.new('GeometryNodeObjectInfo')
    L.new(selfo.outputs[0], oinfo.inputs['Object'])
    inv = N.new('FunctionNodeInvertRotation')
    L.new(oinfo.outputs['Rotation'], inv.inputs[0])
    rv = N.new('FunctionNodeRotateVector')
    L.new(inv.outputs[0], rv.inputs['Rotation'])
    rv.inputs['Vector'].default_value = (0.0, 0.0, -1.0)
    down = rv.outputs[0]
    tang = _v(N, L, 'SUBTRACT', down, _v(N, L, 'SCALE', I['Up'], scale=_v(N, L, 'DOT_PRODUCT', down, I['Up'])))
    sag = _v(N, L, 'SCALE', _v(N, L, 'ADD', tang, _v(N, L, 'SCALE', down, scale=_m(N, L, 'ADD', va=0.25, vb=0.0))),
             scale=_m(N, L, 'MULTIPLY', _m(N, L, 'MAXIMUM', h, vb=0.0), _m(N, L, 'MULTIPLY', I['Gravity'], vb=0.5)))
    setp = N.new('GeometryNodeSetPosition')
    L.new(sub.outputs['Mesh'], setp.inputs['Geometry'])
    L.new(_v(N, L, 'ADD', off, sag), setp.inputs['Offset'])
    L.new(setp.outputs[0], gout.inputs['Geometry'])
    ng['mch_version'] = VERSION
    return ng


def _ident(name):
    ng = build_group()
    for it in ng.interface.items_tree:
        if getattr(it, 'in_out', '') == 'INPUT' and it.name == name:
            return it.identifier
    raise KeyError(name)


def is_shell(ob):
    return ob is not None and ob.type == 'MESH' and ob.modifiers.get(MOD) is not None


def get_input(ob, name):
    return ob.modifiers[MOD][_ident(name)]


def set_input(ob, name, value):
    mod = ob.modifiers.get(MOD)
    if mod is None:
        return
    mod[_ident(name)] = value
    from . import last_used
    if name not in {'Up', 'U', 'V'}:
        last_used.remember('shell', name, value if not isinstance(value, (list, tuple)) else list(value))
    try:
        mod.node_group.interface_update(bpy.context)
    except (AttributeError, TypeError, RuntimeError):
        pass
    ob.update_tag()
    try:
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
    except AttributeError:
        pass


def attach(ob, up_world, size=1.0):
    """Add the Creature Shell modifier to a plate; ``up_world`` = the plate's outward direction."""
    build_group()
    mod = ob.modifiers.get(MOD) or ob.modifiers.new(MOD, 'NODES')
    mod.node_group = bpy.data.node_groups[GROUP]
    up = (ob.matrix_world.inverted().to_3x3() @ Vector(up_world)).normalized()
    uu = up.orthogonal().normalized()
    vv = up.cross(uu).normalized()
    mod[_ident('Up')] = tuple(up)
    mod[_ident('U')] = tuple(uu)
    mod[_ident('V')] = tuple(vv)
    for name, frac in DEFAULTS.items():
        mod[_ident(name)] = frac * size
    from . import last_used
    for name, val in last_used.recall('shell').items():
        try:
            mod[_ident(name)] = val
        except (KeyError, TypeError):
            pass
    ob['mch_shell_size'] = size
    return mod


# -----------------------------------------------------------------------------
# HUD (left of the plate) + panel
# -----------------------------------------------------------------------------

HUD_BUTTONS = (('lift_n', 'TRIA_UP', 'Lift N'), ('lift_e', 'TRIA_RIGHT', 'Lift E'),
               ('lift_s', 'TRIA_DOWN', 'Lift S'), ('lift_w', 'TRIA_LEFT', 'Lift W'),
               ('reroll', 'FILE_REFRESH', 'New random facets'))
SLIDERS = (('facets', 'Facets', 'Facets', -100, 300, 'SIZE'), ('facet_size', 'Facet Size', 'Facet Size', 2, 1000, 'SIZE'),
           ('organic', 'Organic', 'Organic', 0, 300, 'PCT'),
           ('shrink', 'Edge Shrink', 'Edge Shrink', 0, 100, 'PCT'),
           ('shrink_w', 'Shrink Width', 'Shrink Width', 5, 1000, 'SIZE'),
           ('irregular', 'Edge Irregular', 'Edge Irregular', 0, 200, 'PCT'),
           ('bulge', 'Bulge', 'Bulge', -100, 400, 'SIZE'), ('bulge_size', 'Bulge Size', 'Bulge Size', 5, 2000, 'SIZE'),
           ('lift_h', 'Lift Height', 'Lift Height', -300, 600, 'SIZE'),
           ('lift_w', 'Lift Width', 'Lift Width', 1, 100, 'PCT'),
           ('gravity', 'Gravity', 'Gravity', 0, 500, 'PCT'), ('detail', 'Detail', 'Detail', 0, 6, 'INT'))


def slider_spec(ob, key):
    label, name, lo, hi, kind = next((l, n, a, b, k) for kk, l, n, a, b, k in SLIDERS if kk == key)
    cur = get_input(ob, name)
    if kind == 'INT':
        return label, int(cur), lo, hi, (lambda v: set_input(ob, name, int(v))), f'{label}  {int(cur)}'
    if kind == 'PCT':
        v = int(round(cur * 100))
        return label, v, lo, hi, (lambda v: set_input(ob, name, v / 100.0)), f'{label}  {v} %'
    size = max(1e-6, float(ob.get('mch_shell_size', 1.0)))
    v = int(round(cur / size * 1000))
    return label, v, lo, hi, (lambda v: set_input(ob, name, v / 1000.0 * size)), f'{label}  {cur:.3f}'


class MCH_OT_shell_option(bpy.types.Operator):
    """Creature Shell: lift a side off the body / new random facets"""
    bl_idname = 'mch.shell_option'
    bl_label = 'Creature Shell Option'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    option: EnumProperty(items=[('LIFT_N', 'N', ''), ('LIFT_E', 'E', ''), ('LIFT_S', 'S', ''), ('LIFT_W', 'W', ''),
                                ('REROLL', 'Reroll', ''), ('ADD', 'Add Shell', ''), ('REMOVE', 'Remove Shell', '')])

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.type == 'MESH'

    def execute(self, context):
        ob = context.active_object
        if self.option == 'ADD':
            from . import armor_plate as ap
            src = ap.plate_source(ob) or {}
            size = float(src.get('size', max(ob.dimensions) or 1.0))
            rv3d = getattr(context, 'region_data', None)
            up = (rv3d.view_rotation @ Vector((0, 0, 1))) if rv3d is not None else Vector((0, 0, 1))
            attach(ob, up, size)
            return {'FINISHED'}
        if not is_shell(ob):
            return {'CANCELLED'}
        if self.option == 'REMOVE':
            ob.modifiers.remove(ob.modifiers[MOD])
        elif self.option == 'REROLL':
            set_input(ob, 'Seed', int(get_input(ob, 'Seed')) + 1)
        else:
            name = 'Lift ' + self.option[-1]
            set_input(ob, name, 0.0 if float(get_input(ob, name)) > 0.5 else 1.0)
        return {'FINISHED'}


def hud_layout(screen_pts, region_w, region_h, btn=30.0, gap=6.0, slider_w=104.0, slider_h=20.0):
    pts = [p for p in screen_pts if p is not None]
    if not pts:
        return {}
    step = btn + gap
    x = max(min(min(p[0] for p in pts) - btn * 1.2 - slider_w, region_w - slider_w - btn), btn)
    total = step * 2 + (slider_h + gap) * len(SLIDERS)
    top = min(max((max(p[1] for p in pts) + min(p[1] for p in pts)) / 2 + total / 2, total), region_h - btn)
    out = {}
    for i, (name, *_r) in enumerate(HUD_BUTTONS):
        out[name] = (x + i * step, top)
    y = top - step
    for key, *_r in SLIDERS:
        out['slider_' + key] = (x - btn / 2 + slider_w / 2, y + btn / 2 - slider_h / 2)
        y -= slider_h + gap
    return out


def _current(context):
    ob = context.active_object
    if context.mode != 'OBJECT' or not is_shell(ob) or context.region is None or context.region_data is None:
        return None, {}
    from bpy_extras import view3d_utils
    ui = context.preferences.system.ui_scale
    pts = []
    for c in ob.bound_box:
        q = view3d_utils.location_3d_to_region_2d(context.region, context.region_data, ob.matrix_world @ Vector(c))
        pts.append(None if q is None else (q[0] / ui, q[1] / ui))
    return ob, hud_layout(pts, context.region.width / ui, context.region.height / ui)


class MCH_GT_shell_slider(bpy.types.Gizmo):
    bl_idname = 'MCH_GT_shell_slider'
    __slots__ = ('shape', 'init_x', 'init_value', 'key')

    def setup(self):
        if not hasattr(self, 'shape'):
            from .primitive_hud import _RECT
            self.shape = self.new_custom_shape('TRIS', _RECT)

    def draw(self, context):
        self.draw_custom_shape(self.shape)

    def draw_select(self, context, select_id):
        self.draw_custom_shape(self.shape, select_id=select_id)

    def invoke(self, context, event):
        self.init_x = event.mouse_region_x
        self.init_value = slider_spec(context.active_object, self.key)[1]
        return {'RUNNING_MODAL'}

    def modal(self, context, event, tweak):
        from .primitive_hud import slider_value
        ob = context.active_object
        spec = slider_spec(ob, self.key)
        v = slider_value(self.init_value, event.mouse_region_x - self.init_x,
                         step_px=20.0 if self.key == 'detail' else 2.0, lo=spec[2], hi=spec[3])
        if v != spec[1]:
            spec[4](v)
        if context.area:
            context.area.header_text_set(slider_spec(ob, self.key)[5])
        return {'RUNNING_MODAL'}

    def exit(self, context, cancel):
        if context.area:
            context.area.header_text_set(None)
        if cancel:
            slider_spec(context.active_object, self.key)[4](self.init_value)
        else:
            try:
                bpy.ops.ed.undo_push(message='Creature Shell ' + self.key)
            except RuntimeError:
                pass


class MCH_GGT_shell_hud(bpy.types.GizmoGroup):
    bl_idname = 'MCH_GGT_shell_hud'
    bl_label = 'Creature Shell HUD'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and is_shell(context.active_object)

    def setup(self, context):
        self.items = {}
        for name, icon, _label in HUD_BUTTONS:
            gz = self.gizmos.new('GIZMO_GT_button_2d')
            gz.icon = icon
            gz.draw_options = {'BACKDROP', 'OUTLINE'}
            gz.target_set_operator('mch.shell_option').option = name.upper() if name != 'reroll' else 'REROLL'
            gz.color = (0.17, 0.19, 0.23)
            gz.alpha = 0.92
            gz.color_highlight = (0.32, 0.35, 0.41)
            gz.alpha_highlight = 1.0
            self.items[name] = gz
        for key, *_r in SLIDERS:
            gz = self.gizmos.new(MCH_GT_shell_slider.bl_idname)
            gz.key = key
            gz.color = (0.30, 0.22, 0.16)
            gz.alpha = 0.95
            gz.color_highlight = (0.45, 0.33, 0.24)
            gz.alpha_highlight = 1.0
            gz.use_draw_scale = False
            self.items['slider_' + key] = gz

    def draw_prepare(self, context):
        ob, lay = _current(context)
        ui = context.preferences.system.ui_scale
        for name, gz in self.items.items():
            pos = lay.get(name)
            gz.hide = pos is None
            if pos is None:
                continue
            if name.startswith('slider_'):
                gz.matrix_basis = Matrix.Translation((pos[0] * ui, pos[1] * ui, 0.0)) @ Matrix.Diagonal(
                    (52.0 * ui, 10.0 * ui, 1.0, 1.0))
                continue
            gz.scale_basis = 15.0
            gz.matrix_basis[0][3] = pos[0] * ui
            gz.matrix_basis[1][3] = pos[1] * ui
            if name.startswith('lift_') and ob is not None:
                on = float(get_input(ob, 'Lift ' + name[-1].upper())) > 0.5
                gz.color = (1.0, 0.62, 0.16) if on else (0.17, 0.19, 0.23)


_label_handle = None


def _draw_labels():
    try:
        context = bpy.context
        ob, lay = _current(context)
        if ob is None or not lay:
            return
        import blf
        ui = context.preferences.system.ui_scale
        blf.size(0, 11 * ui)
        x, y = lay['lift_n']
        blf.color(0, 1.0, 0.62, 0.16, 1.0)
        blf.position(0, (x - 15) * ui, (y + 22) * ui, 0)
        blf.draw(0, 'CREATURE SHELL  (lift edges N E S W)')
        for key, *_r in SLIDERS:
            x, y = lay['slider_' + key]
            text = slider_spec(ob, key)[5]
            w, _h = blf.dimensions(0, text)
            blf.color(0, 1, 1, 1, 1)
            blf.position(0, x * ui - w / 2, (y - 4) * ui, 0)
            blf.draw(0, text)
    except Exception:            # never break viewport drawing
        pass


def draw(layout, context):
    ob = context.active_object
    box = layout.box()
    box.label(text='CREATURE SHELL', icon='MESH_ICOSPHERE')
    st = context.scene.mch_plate
    box.prop(st, 'creature', toggle=True, text='Shell on new plates')
    if ob is None or ob.type != 'MESH':
        return
    if not is_shell(ob):
        box.operator('mch.shell_option', text='Add Shell to this plate', icon='ADD').option = 'ADD'
        return
    r = box.row(align=True)
    for side in 'NESW':
        on = float(get_input(ob, 'Lift ' + side)) > 0.5
        r.operator('mch.shell_option', text=side, depress=on).option = 'LIFT_' + side
    r.operator('mch.shell_option', text='', icon='FILE_REFRESH').option = 'REROLL'
    mod = ob.modifiers[MOD]
    c = box.column(align=True)
    for name, *_r in INPUTS:
        if name in {'Up', 'U', 'V', 'Seed'} or name.startswith('Lift ') and len(name) == 6:
            continue
        c.prop(mod, f'["{_ident(name)}"]', text=name)
    box.operator('mch.shell_option', text='Remove Shell', icon='X').option = 'REMOVE'


class MCH_PT_shell(bpy.types.Panel):
    bl_idname = 'MCH_PT_shell'
    bl_label = 'Creature Shell'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Mecha Lab'
    bl_order = 74

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, 'mch_plate') and (is_shell(context.active_object)
                                                        or getattr(context.scene.mch_plate, 'creature', False))

    def draw(self, context):
        draw(self.layout, context)


CLASSES = (MCH_OT_shell_option, MCH_GT_shell_slider, MCH_GGT_shell_hud, MCH_PT_shell)


def register():
    global _label_handle
    for c in CLASSES:
        bpy.utils.register_class(c)
    if not bpy.app.background and _label_handle is None:
        _label_handle = bpy.types.SpaceView3D.draw_handler_add(_draw_labels, (), 'WINDOW', 'POST_PIXEL')


def unregister():
    global _label_handle
    if _label_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_label_handle, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _label_handle = None
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
