"""0.24.308 Bolt Insert (user: "방금 만든 나사는 버리지 말구 나사가 들어가는 위치까지 그 근처를 원기둥으로 깍아주고 나사는
박히는 메뉴로 바꾸자, 나사는 육각도 있게, 그리고 깍이는 부분도 쳄퍼랑 베벨 아니면 그냥 깍이기").

Click on a mesh: a round pocket is cut into it there (a Boolean modifier on it, its cutter a hidden child of the
bolt - live), its rim Plain, Chamfered or Bevelled (rounded), and a bolt set in it - a Hex, Round or Socket head
on a threaded shank (the thread of the screw joint) going into the part.  The sliders change the selected bolts
and their pockets; moving a bolt moves its pocket.  Apply Cut makes the pockets real (the bolts stay).  Alt +
click removes the bolt (and its pocket) under the mouse.  The screw joint itself (layers screwed together) is in
this tool's window too (Screw Stack)."""
from __future__ import annotations

import json
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import mech_revolve as mr

TAG = 'mch_bolt'                # on a bolt: its numbers (JSON)
TARGET = 'mch_bolt_target'      # on a bolt: the part it is set in
CUTTER = 'mch_bolt_cutter'      # on a pocket's cutter: its bolt's name
APPLIED = 'mch_bolt_applied'    # on a bolt: its pocket made real
_BUSY = [False]

HEADS = (('HEX', 'Hex Head', 'A hexagon head'), ('ROUND', 'Round Head', 'A round (button) head'),
         ('SOCKET', 'Socket Head', 'A round cap, a hexagon hole in its top'))
POCKETS = (('ROUND', 'Round Pocket', 'A round pocket'), ('SQUARE', 'Square Pocket', 'A square pocket (its corners as '
                                                                                  'round as Corner Round)'))
EDGES = (('PLAIN', 'Plain Cut', 'The pocket cut straight'), ('CHAMFER', 'Chamfer', 'Its rim chamfered'),
         ('BEVEL', 'Bevel', 'Its rim rounded'))


def _st(context):
    return context.scene.mch_bolt


def numbers(st):
    return dict(head=st.head, size=st.size, head_h=st.head_height, shank_d=st.shank_d, shank_len=st.shank_len,
                thread=bool(st.thread), pitch=st.pitch, cut=bool(st.cut), depth=st.depth, clear=st.clearance,
                edge=st.edge, edge_size=st.edge_size, pshape=st.pocket_shape, pcorner=st.pocket_corner)


def _fix(p):
    q = dict(p)
    q.setdefault('pshape', 'ROUND')                 # (a bolt from 0.24.308 before the square pocket)
    q.setdefault('pcorner', 0.2)
    q['size'] = max(q['size'], 1e-4)
    q['shank_d'] = min(max(q['shank_d'], 1e-4), q['size'] * 0.95)
    q['depth'] = max(q['depth'], 0.0) if q['cut'] else 0.0
    q['edge_size'] = min(max(q['edge_size'], 0.0), q['depth'] * 0.9) if q['depth'] > 0 else 0.0
    return q


def bolt_mesh(me, p):
    """The bolt (its origin on the surface, Z out of it): its head's underside at the pocket's floor."""
    q = _fix(p)
    bm = bmesh.new()
    try:
        P = mr.bolt_profile(q['shank_d'] / 2, q['shank_len'], q['head'], q['size'] / 2, q['head_h'],
                            thread=q['thread'], pitch=max(q['pitch'], 1e-4))
        mr.revolve(bm, P, 36, depth=q['shank_d'] * 0.06 if q['thread'] else 0.0, pitch=max(q['pitch'], 1e-4),
                   matrix=Matrix.Translation((0, 0, -q['depth'])))
        mr.finish(bm, flat=True)                    # (a hard part: flat faces, no shading star on the head)
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()


def pocket_profile(q):
    """The cutter's section: a cylinder ``depth`` deep (the head's width and the clearance), its rim finished."""
    rp = q['size'] / 2 + q['clear']                 # (square: half its side)
    d = q['depth']
    top = max(d, q['size']) * 1.5
    e = q['edge_size']
    sh = 'S' if q['pshape'] == 'SQUARE' else 'R'
    P = [(0.0, -d, 0.0, 'R'), (rp, -d, 0.0, sh)]
    if q['edge'] == 'CHAMFER' and e > 0:
        P += [(rp, -e, 0.0, sh), (rp + e, 0.0, 0.0, sh), (rp + e, top, 0.0, sh)]
    elif q['edge'] == 'BEVEL' and e > 0:
        n = 8
        for i in range(n + 1):
            t = i / n * math.pi / 2
            P.append((rp + e - e * math.cos(t), -e + e * math.sin(t), 0.0, sh))
        P.append((rp + e, top, 0.0, sh))
    else:
        P.append((rp, top, 0.0, sh))
    P.append((0.0, top, 0.0, 'R'))
    return P


def pocket_sq_p(q):
    """How square (the superellipse power): Corner Round 0 - sharp, 1 - nearly round."""
    return 2.0 + 38.0 * (1.0 - min(max(q.get('pcorner', 0.2), 0.0), 1.0)) ** 2


def cutter_mesh(me, p):
    q = _fix(p)
    bm = bmesh.new()
    try:
        mr.revolve(bm, pocket_profile(q), 64, sq_p=pocket_sq_p(q))
        mr.finish(bm)
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()


def is_bolt(ob):
    return ob is not None and TAG in ob.keys()


def is_cutter(ob):
    return ob is not None and CUTTER in ob.keys()


def params(ob):
    try:
        return json.loads(ob.get(TAG, '{}'))
    except (TypeError, ValueError):
        return {}


def _mod_name(bolt):
    return f'MCH Bolt | {bolt.name}'


def cutter_of(bolt):
    return next((c for c in bolt.children if is_cutter(c)), None)


def target_of(context, bolt):
    return context.scene.objects.get(bolt.get(TARGET, '')) or bolt.parent


def set_cut(context, bolt, p):
    """The pocket (a Boolean on the part, its cutter under the bolt) - made, changed or taken away."""
    q = _fix(p)
    tgt = target_of(context, bolt)
    cut = cutter_of(bolt)
    want = q['cut'] and q['depth'] > 0 and not bolt.get(APPLIED) and tgt is not None and tgt.type == 'MESH'
    if not want:
        if tgt is not None and tgt.type == 'MESH':
            m = tgt.modifiers.get(_mod_name(bolt))
            if m is not None:
                tgt.modifiers.remove(m)
        if cut is not None:
            me = cut.data
            bpy.data.objects.remove(cut)
            if me.users == 0:
                bpy.data.meshes.remove(me)
        return None
    if cut is None:
        me = bpy.data.meshes.new('MCH_BoltCut')
        cut = bpy.data.objects.new('MCH_BoltCut', me)
        cut[CUTTER] = bolt.name
        for col in bolt.users_collection:
            col.objects.link(cut)
        cut.parent = bolt
        cut.matrix_parent_inverse = Matrix.Identity(4)
        cut.matrix_basis = Matrix.Identity(4)
        cut.display_type = 'WIRE'
        cut.hide_render = True
        try:
            cut.hide_set(True)
        except RuntimeError:
            pass
        cut.hide_select = True
    cutter_mesh(cut.data, p)
    m = tgt.modifiers.get(_mod_name(bolt))
    if m is None:
        m = tgt.modifiers.new(_mod_name(bolt), 'BOOLEAN')
        m.operation = 'DIFFERENCE'
        try:
            m.solver = 'EXACT'
        except TypeError:
            pass
    m.object = cut
    return cut


def rebuild(context, bolt, p):
    if bolt.mode == 'EDIT':
        return
    if bolt.data.users > 1:
        bolt.data = bolt.data.copy()
    bolt_mesh(bolt.data, p)
    bolt[TAG] = json.dumps(p)
    set_cut(context, bolt, p)


def place(context, target, loc, normal, p):
    """A bolt on ``target`` at ``loc`` (world), Z along ``normal``, and its pocket."""
    me = bpy.data.meshes.new('MCH_Bolt')
    ob = bpy.data.objects.new('MCH_Bolt', me)
    coll = target.users_collection[0] if target.users_collection else context.scene.collection
    coll.objects.link(ob)
    ob[TARGET] = target.name
    ob.parent = target
    ob.matrix_parent_inverse = target.matrix_world.inverted_safe()
    ob.matrix_world = mr.frame(loc, normal)
    rebuild(context, ob, p)
    return ob


def remove(context, bolt):
    p = params(bolt)
    p['cut'] = False
    set_cut(context, bolt, p)
    me = bolt.data
    bpy.data.objects.remove(bolt)
    if me.users == 0:
        bpy.data.meshes.remove(me)


def apply_cut(context, bolt):
    """The pocket made real in the part (its Boolean applied); the bolt stays."""
    tgt = target_of(context, bolt)
    m = tgt.modifiers.get(_mod_name(bolt)) if tgt is not None else None
    if m is None:
        return False
    with context.temp_override(object=tgt, active_object=tgt, selected_objects=[tgt]):
        bpy.ops.object.modifier_apply(modifier=m.name)
    bolt[APPLIED] = 1
    cut = cutter_of(bolt)
    if cut is not None:
        me = cut.data
        bpy.data.objects.remove(cut)
        if me.users == 0:
            bpy.data.meshes.remove(me)
    return True


def ray_hit(context, origin, direction, want_bolt=False):
    """The first mesh hit, bolts / pockets' cutters looked through (``want_bolt``: the first bolt hit)."""
    from . import target_rules
    dg = context.evaluated_depsgraph_get()
    o, d = Vector(origin), Vector(direction).normalized()
    for _ in range(32):
        hit, loc, nrm, _i, hob, _m = target_rules.scene_ray(context, dg, o, d)
        if not hit or hob is None:
            return None, None, None
        real = bpy.data.objects.get(hob.name)
        if real is not None and want_bolt and is_bolt(real):
            return real, loc, nrm
        if real is not None and real.type == 'MESH' and not is_bolt(real) and not is_cutter(real) and not want_bolt:
            if nrm.dot(d) > 0:
                nrm = -nrm
            return real, loc, nrm.normalized()
        o = loc + d * 1e-5
    return None, None, None


def selected_bolts(context):
    return [o for o in context.selected_objects if is_bolt(o)]


def _update(self, context):
    if _BUSY[0]:
        return
    p = numbers(self)
    for b in selected_bolts(context):
        rebuild(context, b, p)


class MCH_PG_Bolt(bpy.types.PropertyGroup):
    head: bpy.props.EnumProperty(name='Head', items=HEADS, default='HEX', update=_update)
    size: bpy.props.FloatProperty(name='Head Size', default=0.08, min=0.0005, soft_max=1.0, unit='LENGTH',
                                  update=_update, description='The head across (a hexagon: across its corners)')
    head_height: bpy.props.FloatProperty(name='Head Height', default=0.04, min=0.0002, soft_max=1.0, unit='LENGTH',
                                         update=_update)
    shank_d: bpy.props.FloatProperty(name='Shank', default=0.045, min=0.0002, soft_max=1.0, unit='LENGTH',
                                     update=_update, description='The threaded shank\'s diameter')
    shank_len: bpy.props.FloatProperty(name='Shank Length', default=0.12, min=0.0, soft_max=2.0, unit='LENGTH',
                                       update=_update, description='How far it goes into the part')
    thread: bpy.props.BoolProperty(name='Thread', default=True, update=_update)
    pitch: bpy.props.FloatProperty(name='Pitch', default=0.012, min=0.0005, soft_max=0.5, unit='LENGTH',
                                   update=_update)
    cut: bpy.props.BoolProperty(name='Cut Pocket', default=True, update=_update,
                                description='A round pocket cut into the part round the head (off: the head on the '
                                            'surface)')
    depth: bpy.props.FloatProperty(name='Pocket Depth', default=0.04, min=0.0, soft_max=1.0, unit='LENGTH',
                                   update=_update, description='How deep the pocket (the head sits on its floor)')
    clearance: bpy.props.FloatProperty(name='Pocket Gap', default=0.01, min=0.0, soft_max=0.5, unit='LENGTH',
                                       update=_update, description='The pocket this much wider than the head')
    pocket_shape: bpy.props.EnumProperty(name='Pocket', items=POCKETS, default='ROUND', update=_update)
    pocket_corner: bpy.props.FloatProperty(name='Pocket Corner', default=0.2, min=0.0, max=1.0, subtype='FACTOR',
                                           update=_update, description='Square pocket: how round its corners '
                                                                       '(turn the bolt to turn the pocket)')
    edge: bpy.props.EnumProperty(name='Rim', items=EDGES, default='CHAMFER', update=_update)
    edge_size: bpy.props.FloatProperty(name='Rim Size', default=0.01, min=0.0, soft_max=0.5, unit='LENGTH',
                                       update=_update, description='The chamfer / bevel on the pocket\'s rim')


class MCH_OT_bolt_insert(bpy.types.Operator):
    """Click: a bolt set into the surface under the mouse, a pocket cut round it.  Alt + click: remove the bolt"""
    bl_idname = 'mch.bolt_insert'
    bl_label = 'Bolt Insert'
    bl_options = {'REGISTER', 'UNDO'}
    remove: bpy.props.BoolProperty(default=False, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'

    def invoke(self, context, event):
        from bpy_extras import view3d_utils
        xy = (event.mouse_region_x, event.mouse_region_y)
        o = view3d_utils.region_2d_to_origin_3d(context.region, context.region_data, xy)
        d = view3d_utils.region_2d_to_vector_3d(context.region, context.region_data, xy)
        return self.run(context, o, d)

    def run(self, context, origin, direction):
        if self.remove:
            b, _l, _n = ray_hit(context, origin, direction, want_bolt=True)
            if b is None:
                return {'CANCELLED'}
            remove(context, b)
            return {'FINISHED'}
        tgt, loc, nrm = ray_hit(context, origin, direction)
        if tgt is None:
            self.report({'WARNING'}, 'Click on a mesh surface')
            return {'CANCELLED'}
        st = _st(context)
        from . import screw_stamp
        nrm = screw_stamp.area_normal(context, tgt, loc, nrm, st.size * 0.6)
        b = place(context, tgt, loc, nrm, numbers(st))
        for o_ in context.selected_objects:
            o_.select_set(False)
        b.select_set(True)
        context.view_layer.objects.active = b
        return {'FINISHED'}


class MCH_OT_bolt_apply(bpy.types.Operator):
    """Make the selected bolts' pockets real in their parts (the bolts stay)"""
    bl_idname = 'mch.bolt_apply'
    bl_label = 'Apply Cut'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bs = selected_bolts(context)
        n = sum(1 for b in bs if apply_cut(context, b))
        if not n:
            self.report({'WARNING'}, 'Apply Cut: select bolts with a live pocket')
            return {'CANCELLED'}
        self.report({'INFO'}, f'{n} pocket(s) cut')
        return {'FINISHED'}


class MCH_OT_bolt_pick(bpy.types.Operator):
    """The sliders take the selected bolt's numbers"""
    bl_idname = 'mch.bolt_pick'
    bl_label = 'Load From Selected'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        act = getattr(context, 'active_object', None)
        p = params(act) if is_bolt(act) else {}
        if not p:
            return {'CANCELLED'}
        st = _st(context)
        keys = dict(head='head', size='size', head_h='head_height', shank_d='shank_d', shank_len='shank_len',
                    thread='thread', pitch='pitch', cut='cut', depth='depth', clear='clearance', edge='edge',
                    edge_size='edge_size', pshape='pocket_shape', pcorner='pocket_corner')
        _BUSY[0] = True
        try:
            for k, a in keys.items():
                if k in p:
                    setattr(st, a, p[k])
        finally:
            _BUSY[0] = False
        return {'FINISHED'}


def draw(layout, context):
    st = _st(context)
    box = layout.box()
    box.label(text='Bolt Insert')
    box.label(text='Click a surface: a bolt in a pocket   Alt + click: remove', icon='MOUSE_LMB')
    box.row(align=True).prop(st, 'head', expand=True)
    c = box.column(align=True)
    for k in ('size', 'head_height', 'shank_d', 'shank_len'):
        c.prop(st, k)
    r = box.row(align=True)
    r.prop(st, 'thread')
    sub = r.row(align=True)
    sub.active = st.thread
    sub.prop(st, 'pitch')
    b = box.box()
    b.prop(st, 'cut')
    if st.cut:
        b.row(align=True).prop(st, 'pocket_shape', expand=True)
        if st.pocket_shape == 'SQUARE':
            b.prop(st, 'pocket_corner', slider=True)
        c = b.column(align=True)
        c.prop(st, 'depth')
        c.prop(st, 'clearance')
        b.row(align=True).prop(st, 'edge', expand=True)
        r = b.row(align=True)
        r.active = st.edge != 'PLAIN'
        r.prop(st, 'edge_size')
    n = len(selected_bolts(context))
    if n:
        box.label(text=f'{n} bolt(s) selected: live', icon='INFO')
        r = box.row(align=True)
        r.operator('mch.bolt_pick', icon='IMPORT')
        r.operator('mch.bolt_apply', icon='CHECKMARK')
    try:                                               # (the screw joint: layers screwed together)
        from . import cylinder_gen
        cylinder_gen.draw(layout, context)
    except (ImportError, AttributeError):
        pass


TOOL_KEYMAP = (
    ('mch.bolt_insert', {'type': 'LEFTMOUSE', 'value': 'CLICK'}, None),
    ('mch.bolt_insert', {'type': 'LEFTMOUSE', 'value': 'CLICK', 'alt': True}, {'properties': [('remove', True)]}),
)


class MCH_TOOL_bolt(bpy.types.WorkSpaceTool):
    """0.24.308 Bolt Insert"""
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.bolt_insert'
    bl_label = 'Bolt Insert'
    bl_description = ('Click a surface: a round pocket cut there (Plain / Chamfer / Bevel rim) and a bolt set in it '
                      '(Hex / Round / Socket, threaded).\nThe sliders change the selected bolts live; Alt + click '
                      'removes one')
    bl_icon = 'ops.generic.select'
    bl_widget = None
    bl_keymap = TOOL_KEYMAP

    def draw_settings(context, layout, tool):
        region = getattr(context, 'region', None)
        if region is not None and region.type == 'TOOL_HEADER':
            return


CLASSES = (MCH_PG_Bolt, MCH_OT_bolt_insert, MCH_OT_bolt_apply, MCH_OT_bolt_pick)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_bolt = bpy.props.PointerProperty(type=MCH_PG_Bolt)
    try:
        bpy.utils.register_tool(MCH_TOOL_bolt, separator=False, group=False)
    except (ValueError, RuntimeError, KeyError):
        pass


def unregister():
    try:
        bpy.utils.unregister_tool(MCH_TOOL_bolt)
    except (ValueError, RuntimeError, KeyError):
        pass
    try:
        del bpy.types.Scene.mch_bolt
    except AttributeError:
        pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
