"""0.24.307 Cylinder (user: "실린더 메뉴 만들어주라 두께랑 그런거 수정하고 위아래 레이어 분리되게 만들어주라" /
"연결 부위도 나사 박히는 부분 내가 사이즈 조정 가능하게").

A cylinder stood on the 3D cursor (its axis up, Z) in Layers stacked one on the other, each layer an object of its
own; where two layers meet they screw together: the lower one has a threaded neck on its top, the upper one the
threaded hole for it in its bottom (the same helix, the hole a Clearance wider - a 3D print fit).

* Diameter, Height, Wall (0: solid; more: hollow layers, the neck a tube into the one below), Segments.
* Layers (1 - 6), Split At (two layers: where they part), Gap (the layers pulled apart to see the joint).
* Thread Size (the neck's diameter), Thread Length, Pitch, Thread Depth, Clearance; Thread off: a plain peg.

While a layer of a cylinder is selected the sliders rebuild the whole stack at once.  Make Plain: the layers are
kept as ordinary meshes (the sliders leave them alone after)."""
from __future__ import annotations

import json
import math

import bmesh
import bpy

TAG = 'mch_cyl'                 # on each layer: the stack's id
IDX = 'mch_cyl_i'               # its place in the stack (0: the bottom)
PARAMS = 'mch_cyl_p'            # the stack's numbers (JSON)
_BUSY = [False]


def _st(context):
    return context.scene.mch_cylinder


def numbers(st):
    return dict(D=st.diameter, H=st.height, T=st.wall, segs=int(st.segments), n=int(st.layers), split=st.split,
                gap=st.gap, thread=bool(st.thread), td=st.thread_size, L=st.thread_length, pitch=st.pitch,
                depth=st.thread_depth, c=st.clearance)


def _fix(p):
    """The numbers made to fit together (the neck inside the wall, the thread inside the neck ...)."""
    q = dict(p)
    R = max(1e-4, q['D'] / 2)
    H = max(1e-4, q['H'])
    n = max(1, int(q['n']))
    T = max(0.0, min(q['T'], R * 0.45))
    rt_max = R - T - max(R * 0.04, 1e-4) if T > 0 else R * 0.92
    depth = max(0.0, min(q['depth'], R * 0.2)) if q['thread'] else 0.0
    c = max(0.0, min(q['c'], R * 0.1))
    rt = max(R * 0.05, min(q['td'] / 2 - depth, rt_max - depth - c))     # (the neck's root radius)
    hl = H / n if n > 2 else H * (min(max(q['split'], 0.1), 0.9) if n == 2 else 1.0)
    L = max(1e-4, min(q['L'], hl * 0.8, H / n * 0.8 if n > 2 else hl * 0.8))
    if n == 2:
        L = min(L, H * (1.0 - min(max(q['split'], 0.1), 0.9)) * 0.8)
    q.update(R=R, H=H, n=n, T=T, depth=depth, c=c, rt=rt, L=L, pitch=max(1e-4, q['pitch']))
    return q


def bounds(q):
    """[(z0, z1)] of each layer, bottom first (assembled, no gap)."""
    n, H = q['n'], q['H']
    if n == 2:
        s = H * min(max(q['split'], 0.1), 0.9)
        return [(0.0, s), (s, H)]
    return [(H * i / n, H * (i + 1) / n) for i in range(n)]


def _thread_pts(r, za, zb, q, w=1.0):
    """Points up (or down) a threaded wall from ``za`` to ``zb``: (r, z, weight) - the weight fades out a pitch from
    either end (the wall plain where it meets the next face)."""
    if not q['thread'] or q['depth'] <= 0:
        return [(r, za, 0.0), (r, zb, 0.0)]
    lo, hi = min(za, zb), max(za, zb)
    k = max(2, int(math.ceil(abs(zb - za) / (q['pitch'] / 6.0))))
    out = []
    for i in range(k + 1):
        z = za + (zb - za) * i / k
        f = min(z - lo, hi - z) / max(q['pitch'] * 0.75, 1e-9)
        out.append((r, z, w * max(0.0, min(1.0, f))))
    return out


def profile(q, i):
    """Layer ``i``'s cross-section [(radius, z, thread weight)] from the axis at its bottom round to the axis at its
    top (radius 0: on the axis; two axis points in a row: two surfaces - the outside and a closed hollow inside)."""
    z0, z1 = bounds(q)[i]
    R, T, rt, L, c = q['R'], q['T'], q['rt'], q['L'], q['c']
    female = i > 0
    male = i < q['n'] - 1
    rf = rt + c                                   # (the hole's root: the neck's, a clearance wider)
    Lm = max(1e-4, L - c)                         # (the neck a clearance shorter than the hole is deep)
    hollow = T > 0
    P = []
    # its bottom
    if female:
        P.append((0.0, z0 + L, 0.0) if not hollow else (rf, z0 + L, 0.0))
        P += _thread_pts(rf, z0 + L, z0, q)
        P.append((R, z0, 0.0))
    else:
        P += [(0.0, z0, 0.0), (R, z0, 0.0)]
    P.append((R, z1, 0.0))
    # its top
    if male:
        P.append((rt, z1, 0.0))
        P += _thread_pts(rt, z1, z1 + Lm, q)
        if hollow:
            ri = max(rt - T, rt * 0.3)
            P += [(ri, z1 + Lm, 0.0), (ri, z1 - T, 0.0)]
        else:
            P.append((0.0, z1 + Lm, 0.0))
    else:
        P.append((0.0, z1, 0.0))
        if hollow:
            P.append((0.0, z1 - T, 0.0))
    if hollow:                                    # (the inside: the roof, down the wall, the floor)
        top_in = z1 - T
        bot_in = z0 + L if female else z0 + T      # (a hole below: the inside opens into it)
        if top_in - bot_in < T * 0.5:             # (too short a layer to be hollow: solid)
            return profile(dict(q, T=0.0), i)
        P.append((R - T, top_in, 0.0))
        P.append((R - T, bot_in, 0.0))
        if not female:
            P.append((0.0, bot_in, 0.0))
    return P


def _tri(x):
    f = x - math.floor(x)
    return 1.0 - abs(2.0 * f - 1.0)


def build_layer(me, q, i):
    """Layer ``i``'s mesh (its origin at its own bottom: z0 at 0) into ``me``."""
    P = profile(q, i)
    z0 = bounds(q)[i][0]
    segs = max(12, int(q['segs']))
    closed = P[0][0] > 1e-9                       # (a ring all round: the loop joined)
    bm = bmesh.new()
    try:
        rings = []
        for r, z, w in P:
            if r < 1e-9:
                rings.append([bm.verts.new((0.0, 0.0, z - z0))])
                continue
            ring = []
            for j in range(segs):
                a = 2 * math.pi * j / segs
                rr = r + (w * q['depth'] * _tri(z / q['pitch'] - a / (2 * math.pi)) if w > 0 else 0.0)
                ring.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), z - z0)))
            rings.append(ring)
        pairs = list(zip(rings, rings[1:])) + ([(rings[-1], rings[0])] if closed else [])
        for a_, b_ in pairs:
            if len(a_) == 1 and len(b_) == 1:
                continue
            for j in range(segs):
                k = (j + 1) % segs
                try:
                    if len(a_) == 1:
                        bm.faces.new((a_[0], b_[k], b_[j]))
                    elif len(b_) == 1:
                        bm.faces.new((a_[j], a_[k], b_[0]))
                    else:
                        bm.faces.new((a_[j], a_[k], b_[k], b_[j]))
                except ValueError:
                    pass
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-7)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        for f in bm.faces:
            f.smooth = True
        for e in bm.edges:                         # (the corners sharp, the round and the thread smooth)
            if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(50):
                e.smooth = False
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()


# --- the stack --------------------------------------------------------------------------------------------------

def stack_of(ob):
    return ob.get(TAG, '') if ob is not None and getattr(ob, 'type', '') == 'MESH' else ''


def layers_of(scene, sid):
    obs = [o for o in scene.objects if stack_of(o) == sid]
    return sorted(obs, key=lambda o: int(o.get(IDX, 0)))


def params(ob):
    try:
        return json.loads(ob.get(PARAMS, '{}'))
    except (TypeError, ValueError):
        return {}


def build_stack(context, p, sid=None, base=None):
    """The stack of numbers ``p`` (``sid``: rebuilt in place - its layers' meshes replaced, layers added / taken
    away for the Layers count; ``base``: where its bottom stands)."""
    q = _fix(p)
    scene = context.scene
    old = layers_of(scene, sid) if sid else []
    if base is None:
        base = old[0].matrix_world.copy() if old else None
    if not sid:
        sid = 'Cyl'
        k = 1
        names = {stack_of(o) for o in scene.objects}
        while f'{sid}{k}' in names:
            k += 1
        sid = f'{sid}{k}'
    from mathutils import Matrix, Vector
    if base is None:
        base = Matrix.Translation(scene.cursor.location)
    out = []
    coll = old[0].users_collection[0] if old and old[0].users_collection else context.collection
    for i in range(q['n']):
        if i < len(old):
            ob = old[i]
            if ob.mode == 'EDIT':
                out.append(ob)
                continue
            if ob.data.users > 1:
                ob.data = ob.data.copy()
        else:
            me = bpy.data.meshes.new(f'MCH_{sid}_{i + 1}')
            ob = bpy.data.objects.new(f'MCH_{sid}_{i + 1}', me)
            coll.objects.link(ob)
            for src in old[:1]:                       # (the new layer wears the bottom one's material)
                for m in src.data.materials:
                    ob.data.materials.append(m)
        build_layer(ob.data, q, i)
        ob[TAG] = sid
        ob[IDX] = i
        ob[PARAMS] = json.dumps(p)
        z0 = bounds(q)[i][0] + q['gap'] * i
        ob.matrix_world = base @ Matrix.Translation(Vector((0.0, 0.0, z0)))
        out.append(ob)
    for ob in old[q['n']:]:
        me = ob.data
        bpy.data.objects.remove(ob)
        if me.users == 0:
            bpy.data.meshes.remove(me)
    return sid, out


def selected_stacks(context):
    sids = []
    for o in context.selected_objects:               # (selected only: an active layer left unselected stays)
        s = stack_of(o)
        if s and s not in sids:
            sids.append(s)
    return sids


def _update(self, context):
    if _BUSY[0]:
        return
    p = numbers(self)
    for sid in selected_stacks(context):
        build_stack(context, p, sid)


class MCH_PG_Cylinder(bpy.types.PropertyGroup):
    diameter: bpy.props.FloatProperty(name='Diameter', default=1.0, min=0.002, soft_max=5.0, unit='LENGTH',
                                      update=_update)
    height: bpy.props.FloatProperty(name='Height', default=1.2, min=0.002, soft_max=10.0, unit='LENGTH',
                                    update=_update)
    wall: bpy.props.FloatProperty(name='Wall', default=0.0, min=0.0, soft_max=1.0, unit='LENGTH', update=_update,
                                  description='The wall\'s thickness (0: solid; more: hollow layers)')
    segments: bpy.props.IntProperty(name='Segments', default=64, min=12, max=512, update=_update,
                                    description='Steps round it')
    layers: bpy.props.IntProperty(name='Layers', default=2, min=1, max=6, update=_update,
                                  description='How many layers stacked (each an object of its own, screwed together)')
    split: bpy.props.FloatProperty(name='Split At', default=0.5, min=0.1, max=0.9, subtype='FACTOR', update=_update,
                                   description='Two layers: where they part (of the height)')
    gap: bpy.props.FloatProperty(name='Gap', default=0.0, min=0.0, soft_max=2.0, unit='LENGTH', update=_update,
                                 description='The layers pulled apart (to see the joint; 0: screwed together)')
    thread: bpy.props.BoolProperty(name='Thread', default=True, update=_update,
                                   description='The joint screwed (off: a plain peg in a hole)')
    thread_size: bpy.props.FloatProperty(name='Thread Size', default=0.6, min=0.002, soft_max=5.0, unit='LENGTH',
                                         update=_update, description='The threaded neck\'s diameter')
    thread_length: bpy.props.FloatProperty(name='Thread Length', default=0.2, min=0.002, soft_max=5.0, unit='LENGTH',
                                           update=_update, description='How long the neck (how deep the hole)')
    pitch: bpy.props.FloatProperty(name='Pitch', default=0.06, min=0.002, soft_max=1.0, unit='LENGTH',
                                   update=_update, description='One turn of the thread climbs this much')
    thread_depth: bpy.props.FloatProperty(name='Thread Depth', default=0.025, min=0.0, soft_max=0.5, unit='LENGTH',
                                          update=_update, description='How far the thread stands out')
    clearance: bpy.props.FloatProperty(name='Clearance', default=0.004, min=0.0, soft_max=0.1, unit='LENGTH',
                                       update=_update,
                                       description='The hole this much wider (and deeper) than the neck - a fit for '
                                                   '3D printing (0: exactly the neck)')


class MCH_OT_cylinder_add(bpy.types.Operator):
    """A cylinder in layers screwed together, standing on the 3D cursor - its sliders change it while selected"""
    bl_idname = 'mch.cylinder_add'
    bl_label = 'Summon Cylinder'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode != 'OBJECT':
            self.report({'WARNING'}, 'Cylinder: Object Mode only')
            return {'CANCELLED'}
        sid, obs = build_stack(context, numbers(_st(context)))
        for o in context.selected_objects:
            o.select_set(False)
        for o in obs:
            o.select_set(True)
        context.view_layer.objects.active = obs[0]
        self.report({'INFO'}, f'{sid}: {len(obs)} layer(s) - the sliders change it while selected')
        return {'FINISHED'}


class MCH_OT_cylinder_plain(bpy.types.Operator):
    """Keep the selected cylinders' layers as plain meshes (the sliders leave them alone after)"""
    bl_idname = 'mch.cylinder_plain'
    bl_label = 'Make Plain'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        sids = selected_stacks(context)
        act = getattr(context, 'active_object', None)
        if not sids and stack_of(act):
            sids = [stack_of(act)]
        if not sids:
            self.report({'WARNING'}, 'Make Plain: select a layer of a cylinder')
            return {'CANCELLED'}
        for sid in sids:
            for o in layers_of(context.scene, sid):
                for k in (TAG, IDX, PARAMS):
                    if k in o.keys():
                        del o[k]
        return {'FINISHED'}


class MCH_OT_cylinder_pick(bpy.types.Operator):
    """The sliders take this cylinder's numbers (to change it from where it is)"""
    bl_idname = 'mch.cylinder_pick'
    bl_label = 'Load From Selected'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        act = getattr(context, 'active_object', None)
        p = params(act) if stack_of(act) else {}
        if not p:
            return {'CANCELLED'}
        load(context, p)
        return {'FINISHED'}


def load(context, p):
    st = _st(context)
    keys = dict(D='diameter', H='height', T='wall', segs='segments', n='layers', split='split', gap='gap',
                thread='thread', td='thread_size', L='thread_length', pitch='pitch', depth='thread_depth',
                c='clearance')
    _BUSY[0] = True
    try:
        for k, attr in keys.items():
            if k in p:
                setattr(st, attr, p[k])
    finally:
        _BUSY[0] = False


def draw(layout, context):
    st = _st(context)
    box = layout.box()
    box.label(text='Cylinder')
    c = box.column(align=True)
    for k in ('diameter', 'height', 'wall', 'segments'):
        c.prop(st, k)
    c = box.column(align=True)
    c.label(text='Layers')
    for k in ('layers', 'split', 'gap'):
        c.prop(st, k)
    c = box.column(align=True)
    c.label(text='Screw Joint')
    c.prop(st, 'thread')
    for k in ('thread_size', 'thread_length', 'pitch', 'thread_depth', 'clearance'):
        r = c.row(align=True)
        r.active = st.thread or k in {'thread_size', 'thread_length', 'clearance'}
        r.prop(st, k)
    box.operator('mch.cylinder_add', icon='MESH_CYLINDER')
    act = getattr(context, 'active_object', None)
    sid = stack_of(act) if act is not None and act.select_get() else ''
    if sid:
        box.label(text=f'{sid}: live ({len(layers_of(context.scene, sid))} layers)', icon='INFO')
        r = box.row(align=True)
        r.operator('mch.cylinder_pick', icon='IMPORT')
        r.operator('mch.cylinder_plain', icon='CHECKMARK')
    else:
        box.label(text='Select a layer: the sliders change its cylinder', icon='INFO')


class MCH_TOOL_cylinder(bpy.types.WorkSpaceTool):
    """0.24.307 Cylinder: its own tool (the window: its sliders)"""
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.cylinder_gen'
    bl_label = 'Cylinder'
    bl_description = ('Summon a cylinder in layers screwed together (Diameter, Height, Wall, Layers, Thread Size / '
                      'Length / Pitch / Depth / Clearance) - select a layer and the sliders change it')
    bl_icon = 'ops.generic.select'
    bl_widget = None
    bl_keymap = (('view3d.select', {'type': 'LEFTMOUSE', 'value': 'CLICK'}, None),
                 ('view3d.select', {'type': 'LEFTMOUSE', 'value': 'CLICK', 'shift': True},
                  {'properties': [('toggle', True)]}))

    def draw_settings(context, layout, tool):
        region = getattr(context, 'region', None)
        if region is not None and region.type == 'TOOL_HEADER':
            return


CLASSES = (MCH_PG_Cylinder, MCH_OT_cylinder_add, MCH_OT_cylinder_plain, MCH_OT_cylinder_pick)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_cylinder = bpy.props.PointerProperty(type=MCH_PG_Cylinder)
    try:
        bpy.utils.register_tool(MCH_TOOL_cylinder, separator=False, group=False)
    except (ValueError, RuntimeError, KeyError):
        pass


def unregister():
    try:
        bpy.utils.unregister_tool(MCH_TOOL_cylinder)
    except (ValueError, RuntimeError, KeyError):
        pass
    try:
        del bpy.types.Scene.mch_cylinder
    except AttributeError:
        pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
