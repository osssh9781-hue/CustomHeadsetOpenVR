"""0.24.308 Cylinder - a hydraulic / linear actuator (user, with a photo of a mech's leg: "이건 나사잖아!! 내가 첨부한거처럼
원형 실린더랑 네모난 실린더로 만들어줘, 비율은 내가 조정 가능하게, 그리고 각 끝부분에 메카랑 연결되는 부분 쪽 나사가 있는 부분
크기 두께 나사 유무까지 조정되게").

Two objects on the 3D cursor, along Z: the Body (a round or square barrel, its end caps, the rear mount) and the
Rod (sliding out of it, the rod-end mount) - its origin at the rod end's pin (move it along Z to extend it).
Each end: an Eye (one plate with a hole) or a Clevis (a fork: two plates), its Size, Thickness, Hole and a Bolt
through it (a hex bolt and its nut) on or off.  Proportions: Length (pin to pin), Width, Depth (square), Body (its
share of the length), Rod (of the width), Caps, Corner Round, Body Bolts.  The sliders change the selected one."""
from __future__ import annotations

import json
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import mech_revolve as mr

TAG = 'mch_act'                  # on both objects: the actuator's id
PART = 'mch_act_part'            # 'BODY' / 'ROD'
PARAMS = 'mch_act_p'
_BUSY = [False]

SHAPES = (('ROUND', 'Round Body', 'A round barrel'), ('SQUARE', 'Square Body', 'A square housing (rounded corners)'))
ROD_SHAPES = (('ROUND', 'Round Rod', 'A round rod'), ('SQUARE', 'Square Rod', 'A square rod'))
MOUNTS = (('EYE', 'Eye Plate', 'One plate with a hole (a rod eye)'), ('CLEVIS', 'Clevis', 'A fork: two plates, the pin '
                                                                                   'through both'),
          ('NONE', 'None', 'No mount: a flat end'))


def _st(context):
    return context.scene.mch_actuator


END_KEYS = ('type', 'size', 'thick', 'hole', 'bolt')


def numbers(st):
    p = dict(shape=st.shape, L=st.length, W=st.width, depth=st.depth, body=st.body_share, rod=st.rod_ratio,
             rod_shape=st.rod_shape, cap=st.cap_ratio, flare=st.cap_flare, corner=st.corner, bolts=bool(st.body_bolts),
             segs=int(st.segments))
    for e in ('rear', 'front'):
        for k in END_KEYS:
            p[f'{e}_{k}'] = getattr(st, f'{e}_{k}')
    return p


# --- the parts -------------------------------------------------------------------------------------------------

def _tab_outline(size, neck, n):
    """The eye plate's outline round its hole's centre [(u, v)]: a disc (``size`` across) and a neck ``neck`` long
    toward +v, square sided; its two corners exactly."""
    s2 = size / 2
    angs = [2 * math.pi * j / n for j in range(n)]
    for c in (math.atan2(neck, s2), math.atan2(neck, -s2)):
        angs.append(c % (2 * math.pi))
    angs = sorted(set(round(a, 9) for a in angs))
    out = []
    for a in angs:
        ca, sa = math.cos(a), math.sin(a)
        r = s2
        if sa > 1e-9:
            t = neck / sa
            if abs(ca) > 1e-9:
                t = min(t, s2 / abs(ca))
            r = max(r, t)
        out.append((a, r))
    return out


def tab(bm, size, neck, thick, hole_r, n, M, mat=0):
    """An eye plate (extruded ``thick`` along w), its hole ``hole_r``; (u, v, w) mapped by ``M``."""
    ol = _tab_outline(size, neck, n)
    hole_r = min(hole_r, size * 0.42)
    vs = {}
    for side, w in (('a', -thick / 2), ('b', thick / 2)):
        vs[side] = [bm.verts.new(M @ Vector((r * math.cos(a), r * math.sin(a), w))) for a, r in ol]
        vs[side + 'h'] = [bm.verts.new(M @ Vector((hole_r * math.cos(a), hole_r * math.sin(a), w))) for a, _r in ol]
    m = len(ol)
    for j in range(m):
        k = (j + 1) % m
        for quad in ((vs['a'][j], vs['a'][k], vs['b'][k], vs['b'][j]),
                     (vs['bh'][j], vs['bh'][k], vs['ah'][k], vs['ah'][j]),
                     (vs['a'][k], vs['a'][j], vs['ah'][j], vs['ah'][k]),
                     (vs['b'][j], vs['b'][k], vs['bh'][k], vs['bh'][j])):
            f = bm.faces.new(quad)
            f.material_index = mat


def box(bm, lo, hi, M, mat=0):
    vs = []
    for x in (lo[0], hi[0]):
        for y in (lo[1], hi[1]):
            for z in (lo[2], hi[2]):
                vs.append(bm.verts.new(M @ Vector((x, y, z))))
    idx = ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3))
    for q in idx:
        f = bm.faces.new([vs[i] for i in q])
        f.material_index = mat


def mount(bm, p, end, z_pin, direction, segs):
    """An end's mount at ``z_pin`` (``direction``: +1 its neck going up to the body, -1 down) and its bolt.
    Returns how far along Z (from the pin) the body / rod starts."""
    kind = p[f'{end}_type']
    if kind == 'NONE':
        return 0.0
    size = p[f'{end}_size']
    t = p[f'{end}_thick']
    hole = min(p[f'{end}_hole'], size * 0.8) / 2
    neck = size * 0.45                             # (the pin to where the neck meets the body)
    ov = size * 0.05                               # (into the body a little: no gap)
    # (u, v, w) -> (Y, direction * Z, X) at the pin
    M = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, direction, 0, z_pin), (0, 0, 0, 1)))
    if kind == 'EYE':
        tab(bm, size, neck + ov, t, hole, max(24, segs), M)
        span = t
    else:
        gap = t
        for sgn in (-1, 1):
            Mw = M @ Matrix.Translation(Vector((0, 0, sgn * (gap / 2 + t / 2))))
            tab(bm, size, neck + ov, t, hole, max(24, segs), Mw)
        box(bm, (-size / 2, neck - t * 0.9, -(gap / 2 + t)), (size / 2, neck + ov, gap / 2 + t), M)
        span = gap + 2 * t
    if p[f'{end}_bolt']:                           # (a hex bolt through, its nut on the other side)
        sr = hole * 0.96
        hr, hh = hole * 1.9, hole * 1.15
        nh = hole * 1.0
        seg6 = max(36, int(math.ceil(segs / 12.0)) * 12)
        bp = mr.bolt_profile(sr, span + nh * 1.6, 'HEX', hr, hh, thread=True, pitch=max(sr * 0.35, 1e-4))
        mr.revolve(bm, bp, seg6, depth=sr * 0.12, pitch=max(sr * 0.35, 1e-4),
                   matrix=mr.frame(Vector((span / 2, 0, z_pin)), Vector((1, 0, 0))), mat=1)
        mr.revolve(bm, mr.nut_profile(sr * 1.0, hr, nh), seg6,
                   matrix=mr.frame(Vector((-span / 2, 0, z_pin)), Vector((-1, 0, 0))), mat=1)
    return neck


def layout(p):
    """Where things go along Z: (z0 body start, z1 body end (its gland's top), rod start, rod end, ...)."""
    L = max(p['L'], 1e-3)
    rear = 0.0 if p['rear_type'] == 'NONE' else p['rear_size'] * 0.45
    front = 0.0 if p['front_type'] == 'NONE' else p['front_size'] * 0.45
    span = max(L - rear - front, L * 0.2)
    Lb = span * min(max(p['body'], 0.15), 0.95)
    return dict(L=L, z0=rear, z1=rear + Lb, zr1=L - front, span=span, Lb=Lb)


def _sq_p(corner):
    return 2.0 + 28.0 * (1.0 - min(max(corner, 0.0), 1.0)) ** 2


def build_body(me, p):
    g = layout(p)
    bm = bmesh.new()
    try:
        segs = max(16, int(p['segs']))
        sh = 'S' if p['shape'] == 'SQUARE' else 'R'
        ys = p['depth'] if sh == 'S' else 1.0
        W = p['W']
        Rb = W / 2
        Rc = Rb * max(p['flare'], 0.5)
        rr = Rb * min(max(p['rod'], 0.05), 0.95)
        Rg = min(rr * 1.4, Rb * 0.98)
        z0, z1 = g['z0'], g['z1']
        gl = min(g['Lb'] * 0.06, W * 0.15)
        capL = min(g['Lb'] * min(max(p['cap'], 0.02), 0.45), (g['Lb'] - gl) * 0.45)
        zt = z1 - gl                                       # (the front cap's face; the gland above it)
        ch = min(capL * 0.18, W * 0.04)
        rsh = 'S' if p['rod_shape'] == 'SQUARE' else 'R'
        P = [(0.0, z0, 0.0, sh), (Rc - ch, z0, 0.0, sh), (Rc, z0 + ch, 0.0, sh), (Rc, z0 + capL - ch, 0.0, sh),
             (Rc - ch, z0 + capL, 0.0, sh), (Rb, z0 + capL, 0.0, sh), (Rb, zt - capL, 0.0, sh),
             (Rc - ch, zt - capL, 0.0, sh), (Rc, zt - capL + ch, 0.0, sh), (Rc, zt - ch, 0.0, sh),
             (Rc - ch, zt, 0.0, sh), (Rg, zt, 0.0, rsh), (Rg, z1, 0.0, rsh), (0.0, z1, 0.0, rsh)]
        mr.revolve(bm, P, segs, sq_p=_sq_p(p['corner']), yscale=ys)
        if p['bolts']:                                     # (bolt heads at the caps' corners)
            hr, hh = W * 0.055, W * 0.04
            k = 0.7
            for zf, d in ((z0, -1.0), (zt, 1.0)):
                for a in (45, 135, 225, 315):
                    ar = math.radians(a)
                    x, y = Rc * k * math.cos(ar), Rc * k * math.sin(ar) * ys
                    if sh == 'S':
                        x, y = Rc * k * math.copysign(0.78, math.cos(ar)), Rc * k * math.copysign(0.78, math.sin(ar)) * ys
                    mr.revolve(bm, mr.bolt_profile(hr * 0.5, 0.0, 'SOCKET', hr, hh), 36,
                               matrix=mr.frame(Vector((x, y, zf - d * hh * 0.15)), Vector((0, 0, d))), mat=1)
        mount(bm, p, 'rear', 0.0, 1, segs)
        mr.finish(bm)
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()


def build_rod(me, p):
    """The rod (its origin at the rod end's pin: z = L)."""
    g = layout(p)
    bm = bmesh.new()
    try:
        segs = max(16, int(p['segs']))
        W = p['W']
        Rb = W / 2
        rr = Rb * min(max(p['rod'], 0.05), 0.95)
        rsh = 'S' if p['rod_shape'] == 'SQUARE' else 'R'
        ys = p['depth'] if (rsh == 'S' and p['shape'] == 'SQUARE') else 1.0
        zr0 = g['z0'] + g['Lb'] * 0.35                    # (deep in the body: it slides)
        zr1 = g['zr1']
        c2 = min(W * 0.12, (zr1 - zr0) * 0.1)
        P = [(0.0, zr0, 0.0, rsh), (rr, zr0, 0.0, rsh), (rr, zr1 - c2, 0.0, rsh), (rr * 1.3, zr1 - c2, 0.0, rsh),
             (rr * 1.3, zr1 + p['front_size'] * 0.03, 0.0, rsh), (0.0, zr1 + p['front_size'] * 0.03, 0.0, rsh)]
        mr.revolve(bm, P, segs, sq_p=_sq_p(p['corner']), yscale=ys)
        mount(bm, p, 'front', g['L'], -1, segs)
        mr.finish(bm)
        bmesh.ops.translate(bm, verts=list(bm.verts), vec=Vector((0, 0, -g['L'])))
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()


# --- the objects ------------------------------------------------------------------------------------------------

def act_of(ob):
    return ob.get(TAG, '') if ob is not None and getattr(ob, 'type', '') == 'MESH' else ''


def parts_of(scene, aid):
    d = {}
    for o in scene.objects:
        if act_of(o) == aid:
            d[o.get(PART, '')] = o
    return d


def params(ob):
    try:
        return json.loads(ob.get(PARAMS, '{}'))
    except (TypeError, ValueError):
        return {}


def build(context, p, aid=None):
    scene = context.scene
    old = parts_of(scene, aid) if aid else {}
    if not aid:
        k = 1
        names = {act_of(o) for o in scene.objects}
        while f'Act{k}' in names:
            k += 1
        aid = f'Act{k}'
    body = old.get('BODY')
    rod0 = old.get('ROD')
    base = body.matrix_world.copy() if body is not None else Matrix.Translation(scene.cursor.location)
    slide = 0.0                                            # (how far the user slid the rod out: kept)
    if body is not None and rod0 is not None and rod0.parent is body:
        slide = rod0.matrix_basis.translation.z - layout(params(body) or p)['L']   # (its own: no stale world matrix)
    coll = body.users_collection[0] if body is not None and body.users_collection else context.collection
    out = {}
    for part, fn in (('BODY', build_body), ('ROD', build_rod)):
        ob = old.get(part)
        if ob is None:
            nm = f'MCH_{aid}_{part.title()}'
            ob = bpy.data.objects.new(nm, bpy.data.meshes.new(nm))
            coll.objects.link(ob)
        elif ob.mode == 'EDIT':
            out[part] = ob
            continue
        if ob.data.users > 1:
            ob.data = ob.data.copy()
        fn(ob.data, p)
        ob[TAG] = aid
        ob[PART] = part
        ob[PARAMS] = json.dumps(p)
        out[part] = ob
    body, rod = out['BODY'], out['ROD']
    if body.mode != 'EDIT' and body is not old.get('BODY'):
        body.matrix_world = base
    if rod.mode != 'EDIT':
        if rod.parent is not body:
            rod.parent = body
        rod.matrix_parent_inverse = Matrix.Identity(4)
        rod.matrix_basis = Matrix.Translation((0.0, 0.0, layout(p)['L'] + slide))
    return aid, out


def selected_acts(context):
    out = []
    for o in context.selected_objects:
        a = act_of(o)
        if a and a not in out:
            out.append(a)
    return out


def _update(self, context):
    if _BUSY[0]:
        return
    p = numbers(self)
    for aid in selected_acts(context):
        build(context, p, aid)


def _end_props(end, label, size, thick, hole):
    d = {}
    d[f'{end}_type'] = bpy.props.EnumProperty(name=f'{label} Mount', items=MOUNTS, default='CLEVIS' if end == 'rear'
                                              else 'EYE', update=_update)
    d[f'{end}_size'] = bpy.props.FloatProperty(name=f'{label} Size', default=size, min=0.002, soft_max=3.0,
                                               unit='LENGTH', update=_update,
                                               description='The mount\'s plate across (round its hole)')
    d[f'{end}_thick'] = bpy.props.FloatProperty(name=f'{label} Thickness', default=thick, min=0.001, soft_max=1.0,
                                                unit='LENGTH', update=_update, description='The plate\'s thickness')
    d[f'{end}_hole'] = bpy.props.FloatProperty(name=f'{label} Pin Hole', default=hole, min=0.001, soft_max=1.0,
                                               unit='LENGTH', update=_update,
                                               description='The hole (the bolt\'s diameter)')
    d[f'{end}_bolt'] = bpy.props.BoolProperty(name=f'{label} Bolt', default=True, update=_update,
                                              description='A hex bolt through it, its nut on the other side')
    return d


class MCH_PG_Actuator(bpy.types.PropertyGroup):
    __annotations__ = dict(
        shape=bpy.props.EnumProperty(name='Shape', items=SHAPES, default='ROUND', update=_update),
        length=bpy.props.FloatProperty(name='Length', default=2.0, min=0.01, soft_max=20.0, unit='LENGTH',
                                       update=_update, description='Pin to pin'),
        width=bpy.props.FloatProperty(name='Width', default=0.36, min=0.002, soft_max=5.0, unit='LENGTH',
                                      update=_update, description='The body across'),
        depth=bpy.props.FloatProperty(name='Depth', default=1.0, min=0.2, max=4.0, update=_update,
                                      description='Square: its depth, of the width'),
        body_share=bpy.props.FloatProperty(name='Body Share', default=0.6, min=0.15, max=0.95, subtype='FACTOR',
                                           update=_update, description='The body\'s share of the length (the rest: '
                                                                       'the rod out of it)'),
        rod_ratio=bpy.props.FloatProperty(name='Rod Width', default=0.42, min=0.05, max=0.95, subtype='FACTOR',
                                          update=_update, description='The rod across, of the width'),
        rod_shape=bpy.props.EnumProperty(name='Rod Shape', items=ROD_SHAPES, default='ROUND', update=_update),
        cap_ratio=bpy.props.FloatProperty(name='Caps', default=0.14, min=0.02, max=0.45, subtype='FACTOR',
                                          update=_update, description='The end caps\' length, of the body'),
        cap_flare=bpy.props.FloatProperty(name='Cap Size', default=1.12, min=0.6, max=2.0, update=_update,
                                          description='The end caps across, of the body'),
        corner=bpy.props.FloatProperty(name='Corner Round', default=0.25, min=0.0, max=1.0, subtype='FACTOR',
                                       update=_update, description='Square: how round its corners'),
        body_bolts=bpy.props.BoolProperty(name='Body Bolts', default=True, update=_update,
                                          description='Bolt heads at the end caps\' corners'),
        segments=bpy.props.IntProperty(name='Segments', default=48, min=12, max=256, update=_update),
        **_end_props('rear', 'Rear', 0.34, 0.1, 0.1),
        **_end_props('front', 'Rod End', 0.26, 0.12, 0.08),
    )


class MCH_OT_actuator_add(bpy.types.Operator):
    """A cylinder (a body and a rod sliding out of it, a mount and its bolt at each end) on the 3D cursor"""
    bl_idname = 'mch.actuator_add'
    bl_label = 'Summon Cylinder'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode != 'OBJECT':
            self.report({'WARNING'}, 'Cylinder: Object Mode only')
            return {'CANCELLED'}
        aid, obs = build(context, numbers(_st(context)))
        for o in context.selected_objects:
            o.select_set(False)
        for o in obs.values():
            o.select_set(True)
        context.view_layer.objects.active = obs['BODY']
        self.report({'INFO'}, f'{aid}: the sliders change it while selected; move the Rod along Z to extend it')
        return {'FINISHED'}


class MCH_OT_actuator_pick(bpy.types.Operator):
    """The sliders take the selected cylinder's numbers"""
    bl_idname = 'mch.actuator_pick'
    bl_label = 'Load From Selected'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        act = getattr(context, 'active_object', None)
        p = params(act) if act_of(act) else {}
        if not p:
            return {'CANCELLED'}
        st = _st(context)
        keys = dict(shape='shape', L='length', W='width', depth='depth', body='body_share', rod='rod_ratio',
                    rod_shape='rod_shape', cap='cap_ratio', flare='cap_flare', corner='corner', bolts='body_bolts',
                    segs='segments')
        for e in ('rear', 'front'):
            for k in END_KEYS:
                keys[f'{e}_{k}'] = f'{e}_{k}'
        _BUSY[0] = True
        try:
            for k, a in keys.items():
                if k in p:
                    setattr(st, a, p[k])
        finally:
            _BUSY[0] = False
        return {'FINISHED'}


class MCH_OT_actuator_plain(bpy.types.Operator):
    """Keep the selected cylinders as plain meshes (the sliders leave them alone after)"""
    bl_idname = 'mch.actuator_plain'
    bl_label = 'Make Plain'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        aids = selected_acts(context)
        if not aids:
            self.report({'WARNING'}, 'Make Plain: select a cylinder')
            return {'CANCELLED'}
        for aid in aids:
            for o in parts_of(context.scene, aid).values():
                for k in (TAG, PART, PARAMS):
                    if k in o.keys():
                        del o[k]
        return {'FINISHED'}


def draw(layout_, context):
    st = _st(context)
    box_ = layout_.box()
    box_.label(text='Cylinder')
    box_.row(align=True).prop(st, 'shape', expand=True)
    c = box_.column(align=True)
    for k in ('length', 'width'):
        c.prop(st, k)
    if st.shape == 'SQUARE':
        c.prop(st, 'depth')
        c.prop(st, 'corner')
    c = box_.column(align=True)
    c.label(text='Proportions')
    for k in ('body_share', 'rod_ratio', 'cap_ratio', 'cap_flare'):
        c.prop(st, k, slider=True)
    r = box_.row(align=True)
    r.prop(st, 'rod_shape', expand=True)
    box_.prop(st, 'body_bolts')
    for end, label in (('rear', 'Rear Mount'), ('front', 'Rod End Mount')):
        b = box_.box()
        b.label(text=label)
        b.row(align=True).prop(st, f'{end}_type', expand=True)
        if getattr(st, f'{end}_type') != 'NONE':
            c = b.column(align=True)
            for k in ('size', 'thick', 'hole'):
                c.prop(st, f'{end}_{k}', text=('Size', 'Thickness', 'Pin Hole')[('size', 'thick', 'hole').index(k)])
            c.prop(st, f'{end}_bolt', text='Bolt')
    box_.prop(st, 'segments')
    box_.operator('mch.actuator_add', icon='MESH_CYLINDER')
    act = getattr(context, 'active_object', None)
    if act is not None and act.select_get() and act_of(act):
        box_.label(text=f'{act_of(act)}: live - move its Rod along Z to extend it', icon='INFO')
        r = box_.row(align=True)
        r.operator('mch.actuator_pick', icon='IMPORT')
        r.operator('mch.actuator_plain', icon='CHECKMARK')
    else:
        box_.label(text='Select a cylinder: the sliders change it', icon='INFO')


class MCH_TOOL_actuator(bpy.types.WorkSpaceTool):
    """0.24.308 Cylinder (actuator): its own tool"""
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.cylinder_gen'
    bl_label = 'Cylinder'
    bl_description = ('Summon a cylinder (round or square body, a rod, a mount and bolt at each end) - select it and '
                      'the sliders change it; move its Rod along Z to extend it')
    bl_icon = 'ops.generic.select'
    bl_widget = None
    bl_keymap = (('view3d.select', {'type': 'LEFTMOUSE', 'value': 'CLICK'}, None),
                 ('view3d.select', {'type': 'LEFTMOUSE', 'value': 'CLICK', 'shift': True},
                  {'properties': [('toggle', True)]}))

    def draw_settings(context, layout, tool):
        region = getattr(context, 'region', None)
        if region is not None and region.type == 'TOOL_HEADER':
            return


CLASSES = (MCH_PG_Actuator, MCH_OT_actuator_add, MCH_OT_actuator_pick, MCH_OT_actuator_plain)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_actuator = bpy.props.PointerProperty(type=MCH_PG_Actuator)
    try:
        bpy.utils.register_tool(MCH_TOOL_actuator, separator=False, group=False)
    except (ValueError, RuntimeError, KeyError):
        pass


def unregister():
    try:
        bpy.utils.unregister_tool(MCH_TOOL_actuator)
    except (ValueError, RuntimeError, KeyError):
        pass
    try:
        del bpy.types.Scene.mch_actuator
    except AttributeError:
        pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
