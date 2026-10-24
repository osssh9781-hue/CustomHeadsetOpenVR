"""0.23.16 Box Hide (from the HTML prototype): draw a shape over meshes to hide what is inside it.

* Non-destructive: every hidden mesh gets one Geometry Nodes modifier (``MCH_BoxHide``) that subtracts a
  hidden "hide volume" object (the drawn shapes pushed through the view, like the Cut cutter).
* Draw again = hide more (the volume grows), Alt + draw = restore that part (cut out of the volume).
* Cap (per mesh): ON = the cut is closed with new faces (a solid), OFF = an open hole (just hidden).
* Mirror X: every shape is also hidden on the other side of the mesh (its local X).
* Show All = remove the modifier (nothing was changed), Apply = make the hiding permanent.
"""
from __future__ import annotations

import bmesh
import bpy
from mathutils import Matrix

from . import core_geometry as cg

MOD = 'MCH_BoxHide'
GROUP = 'MCH_BoxHide'
COLL = 'MCH_BoxHide'
VOL_KEY = 'mch_hide_volume'          # on the volume object: the name of the mesh it hides
VERSION = 3          # 0.23.17: no Exact solver (46 s on 100k faces) - Manifold / Float, Open = the same cut, its cap faces deleted


def _link(g, a, b):
    g.links.new(a, b)


def build_group():
    g = bpy.data.node_groups.get(GROUP)
    if g is not None and g.get('mch_version') == VERSION:
        return g
    if g is None:
        g = bpy.data.node_groups.new(GROUP, 'GeometryNodeTree')
    g.nodes.clear()
    for item in list(g.interface.items_tree):
        g.interface.remove(item)
    g.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    g.interface.new_socket('Volume', in_out='INPUT', socket_type='NodeSocketObject')
    cap = g.interface.new_socket('Cap', in_out='INPUT', socket_type='NodeSocketBool')
    cap.default_value = True
    man = g.interface.new_socket('Manifold', in_out='INPUT', socket_type='NodeSocketBool')
    man.default_value = False
    eps = g.interface.new_socket('Epsilon', in_out='INPUT', socket_type='NodeSocketFloat')
    eps.default_value = 1e-5
    g.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = g.nodes
    gi = N.new('NodeGroupInput')
    go = N.new('NodeGroupOutput')
    info = N.new('GeometryNodeObjectInfo')
    info.transform_space = 'RELATIVE'
    _link(g, gi.outputs['Volume'], info.inputs['Object'])
    vol = info.outputs['Geometry']
    # Cap: a real cut closed with new faces - Manifold solver (fast) on closed meshes, Float otherwise
    booleans = {}
    for solver in ('MANIFOLD', 'FLOAT'):
        boo = N.new('GeometryNodeMeshBoolean')
        boo.operation = 'DIFFERENCE'
        boo.solver = solver
        _link(g, gi.outputs['Geometry'], boo.inputs['Mesh 1'])
        _link(g, vol, boo.inputs['Mesh 2'])
        booleans[solver] = boo
    pick = N.new('GeometryNodeSwitch')
    pick.input_type = 'GEOMETRY'
    _link(g, gi.outputs['Manifold'], pick.inputs['Switch'])
    _link(g, booleans['FLOAT'].outputs['Mesh'], pick.inputs['False'])
    _link(g, booleans['MANIFOLD'].outputs['Mesh'], pick.inputs['True'])
    # Open: the same cut, then the faces it made (they lie on the volume's surface) are deleted - an open hole
    prox = N.new('GeometryNodeProximity')
    prox.target_element = 'FACES'
    _link(g, vol, prox.inputs['Geometry'])
    on_vol = N.new('FunctionNodeCompare')
    on_vol.data_type = 'FLOAT'
    on_vol.operation = 'LESS_THAN'
    _link(g, prox.outputs['Distance'], on_vol.inputs['A'])
    _link(g, gi.outputs['Epsilon'], on_vol.inputs['B'])
    dele = N.new('GeometryNodeDeleteGeometry')
    dele.domain = 'FACE'
    _link(g, pick.outputs['Output'], dele.inputs['Geometry'])
    _link(g, on_vol.outputs['Result'], dele.inputs['Selection'])
    out = N.new('GeometryNodeSwitch')
    out.input_type = 'GEOMETRY'
    _link(g, gi.outputs['Cap'], out.inputs['Switch'])
    _link(g, dele.outputs['Geometry'], out.inputs['False'])
    _link(g, pick.outputs['Output'], out.inputs['True'])
    _link(g, out.outputs['Output'], go.inputs['Geometry'])
    g['mch_version'] = VERSION
    return g


def _ident(g, name):
    for item in g.interface.items_tree:
        if getattr(item, 'in_out', '') == 'INPUT' and item.name == name:
            return item.identifier
    raise KeyError(name)


def volume_of(ob):
    mod = ob.modifiers.get(MOD) if ob is not None else None
    if mod is None or mod.node_group is None:
        return None
    try:
        return cg.gn_get(mod, _ident(mod.node_group, 'Volume'))
    except KeyError:
        return None


def is_hidden(ob):
    return volume_of(ob) is not None


def get_cap(ob):
    mod = ob.modifiers.get(MOD)
    return bool(cg.gn_get(mod, _ident(mod.node_group, 'Cap'))) if mod is not None else True


def set_cap(ob, value):
    mod = ob.modifiers.get(MOD)
    if mod is None:
        return
    cg.gn_set(mod, _ident(mod.node_group, 'Cap'), bool(value))
    ob.update_tag()


def _collection(context):
    coll = bpy.data.collections.get(COLL)
    if coll is None:
        coll = bpy.data.collections.new(COLL)
    if coll.name not in context.scene.collection.children:
        try:
            context.scene.collection.children.link(coll)
        except RuntimeError:
            pass
    return coll


def _new_volume(context, target):
    me = bpy.data.meshes.new(f'MCH_Hide_{target.name}')
    vol = bpy.data.objects.new(f'MCH_Hide_{target.name}', me)
    _collection(context).objects.link(vol)
    vol.display_type = 'WIRE'
    vol.hide_render = True
    vol.hide_select = True
    vol[VOL_KEY] = target.name
    try:
        vol.hide_set(True)                 # hidden but still evaluated (the modifier reads it)
    except RuntimeError:
        pass
    return vol


def _ensure_modifier(target, vol, cap):
    mod = target.modifiers.get(MOD)
    g = build_group()
    if mod is None:
        mod = target.modifiers.new(MOD, 'NODES')
        mod.node_group = g
        cg.gn_set(mod, _ident(g, 'Cap'), bool(cap))
    elif mod.node_group is not g:
        mod.node_group = g
    cg.gn_set(mod, _ident(g, 'Volume'), vol)
    cg.gn_set(mod, _ident(g, 'Manifold'), cg.non_manifold_edge_count(target.data) == 0)
    size = max(target.dimensions) if max(target.dimensions) > 0 else 1.0
    cg.gn_set(mod, _ident(g, 'Epsilon'), size * 1e-4)
    target.update_tag()
    return mod


def _mirrored(bm_src, target):
    """The shape mirrored across the target's local X (world space in, world space out)."""
    mw = target.matrix_world
    flip = mw @ Matrix.Scale(-1.0, 4, (1.0, 0.0, 0.0)) @ mw.inverted_safe()
    bm = bm_src.copy()
    bm.transform(flip)
    bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    return bm


def _flat(me):
    for p in me.polygons:
        p.use_smooth = False


def _combine(context, vol, bm_add, op):
    """vol = vol (op) shape: UNION to hide more, DIFFERENCE to show again.  The volume stays one clean
    closed solid (the Manifold cut needs that); it is small, so the exact boolean here is quick."""
    me_add = bpy.data.meshes.new('MCH_Hide_shape')
    bm_add.to_mesh(me_add)
    if not vol.data.polygons:
        if op == 'UNION':
            old = vol.data
            vol.data = me_add
            if old.users == 0:
                bpy.data.meshes.remove(old)
            _flat(vol.data)
        else:
            bpy.data.meshes.remove(me_add)
        return
    other = cg.link_temp_object(context, me_add, 'MCH_Hide_shape')
    try:
        vol.hide_set(False)
        try:
            me, _solver = cg.boolean_result(context, vol, other, op, 'EXACT', False, allow_empty=True)
        finally:
            vol.hide_set(True)
    finally:
        cg.remove_object_and_mesh(other)
    old = vol.data
    vol.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    _flat(vol.data)


def _sharers(vol, skip):
    """Other meshes whose Box Hide reads the same volume (a Shift+D copy keeps the modifier and its volume)."""
    return [o for o in bpy.data.objects if o is not skip and o.type == 'MESH' and volume_of(o) is vol]


def _detach_sharers(context, vol, owner):
    """0.24.11 before the owner's volume changes, every copy sharing it gets its own volume (same shape), so
    hiding on one object never cuts its Shift+D duplicates too."""
    for o in _sharers(vol, owner):
        own = vol.copy()
        own.data = vol.data.copy()
        own.name = own.data.name = f'MCH_Hide_{o.name}'
        own[VOL_KEY] = o.name
        _collection(context).objects.link(own)
        try:
            own.hide_set(True)
        except RuntimeError:
            pass
        mod = o.modifiers.get(MOD)
        cg.gn_set(mod, _ident(mod.node_group, 'Volume'), own)
        o.update_tag()
    vol[VOL_KEY] = owner.name


def perform(context, targets, loops, projector, restore=False):
    """Hide (or with ``restore``, show again) the part of every target inside the drawn screen loops."""
    from . import cut_engine as ce
    if not targets:
        raise cg.CutError('Box Hide: draw over a mesh.')
    st = context.scene.mch_hide
    groups = cg.prepare_loops(loops)
    near, far = ce._planes(context, targets, projector, [g[0] for g in groups])
    shape_me = cg.build_cutter_mesh(groups, projector, near, far, 'MCH_Hide_Shape')
    done, untouched = [], []
    try:
        for t in targets:
            bm_shape = bmesh.new()
            bm_shape.from_mesh(shape_me)
            parts = [bm_shape]
            if st.mirror:
                parts.append(_mirrored(bm_shape, t))
            try:
                vol = volume_of(t)
                if vol is not None:
                    _detach_sharers(context, vol, t)
                if not restore:
                    if vol is None:
                        vol = _new_volume(context, t)
                    for bm_part in parts:
                        _combine(context, vol, bm_part, 'UNION')
                    _ensure_modifier(t, vol, st.cap)
                    done.append(t.name)
                    continue
                if vol is None:
                    untouched.append(t.name)
                    continue
                # restore: cut the drawn shape out of the hide volume
                for bm_part in parts:
                    _combine(context, vol, bm_part, 'DIFFERENCE')
                if not vol.data.polygons:
                    show_all(t)             # nothing hidden any more
                else:
                    t.update_tag()
                done.append(t.name)
            finally:
                for bm_part in parts:
                    bm_part.free()
    finally:
        bpy.data.meshes.remove(shape_me)
    verb = 'Restored' if restore else 'Hidden'
    msg = f'Box Hide: {verb} on {", ".join(done)}' if done else 'Box Hide: nothing hidden there'
    if untouched:
        msg += ' | nothing hidden on: ' + ', '.join(untouched)
    if st.mirror:
        msg += ' | Mirror X'
    return msg


def show_all(ob):
    """Remove the hiding (the mesh itself was never changed)."""
    vol = volume_of(ob)
    mod = ob.modifiers.get(MOD)
    if mod is not None:
        ob.modifiers.remove(mod)
    if vol is not None and not _sharers(vol, ob):      # a duplicate may still use it
        cg.remove_object_and_mesh(vol)
    ob.update_tag()


def apply(context, ob):
    """Make the hiding permanent: the modifier is applied (other modifiers stay)."""
    mod = ob.modifiers.get(MOD)
    if mod is None:
        return False
    vol = volume_of(ob)
    with context.temp_override(object=ob, active_object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    if vol is not None and not _sharers(vol, ob):
        cg.remove_object_and_mesh(vol)
    return True


def split_off(context, ob):
    """0.24.18 Split Off: the hidden part becomes a mesh of its own (like Split) and the rest keeps the hole;
    both are closed solids.  Returns the new object, or None."""
    vol = volume_of(ob)
    if vol is None:
        return None
    piece = ob.copy()
    piece.data = ob.data.copy()
    for coll in ob.users_collection:
        coll.objects.link(piece)
    mod = piece.modifiers.get(MOD)
    if mod is not None:
        piece.modifiers.remove(mod)
    piece.name = ob.name + '_Hidden'
    vol.hide_set(False)
    try:
        me, _solver = cg.boolean_result(context, piece, vol, 'INTERSECT', 'AUTO', False)
    except cg.CutError:
        cg.remove_object_and_mesh(piece)
        raise
    finally:
        vol.hide_set(True)
    old = piece.data
    if not me.materials:
        for m in old.materials:
            me.materials.append(m)
    piece.data = me
    me.name = piece.name
    if old.users == 0:
        bpy.data.meshes.remove(old)
    set_cap(ob, True)                     # the rest is closed too, like Split
    apply(context, ob)
    return piece


def _hidden_selected(context):
    obs = [o for o in context.selected_objects if o.type == 'MESH' and is_hidden(o)]
    if not obs:
        obs = [o for o in context.view_layer.objects if o.type == 'MESH' and is_hidden(o)]
    return obs


class MCH_PG_BoxHide(bpy.types.PropertyGroup):
    cap: bpy.props.BoolProperty(name='Cap', default=True,
                                description='Close the cut with new faces (a solid); off = an open hole')
    mirror: bpy.props.BoolProperty(name='Mirror X', default=False,
                                   description='Also hide the same part on the other side of the mesh (its local X)')


class MCH_OT_box_hide_show_all(bpy.types.Operator):
    """Show everything again (selected meshes, or all hidden ones when none is selected)"""
    bl_idname = 'mch.box_hide_show_all'
    bl_label = 'Show All'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obs = _hidden_selected(context)
        for o in obs:
            show_all(o)
        self.report({'INFO'}, f'Box Hide: shown again on {len(obs)} mesh(es)')
        return {'FINISHED'}


class MCH_OT_box_hide_apply(bpy.types.Operator):
    """Make the hiding permanent: the hidden parts are really removed"""
    bl_idname = 'mch.box_hide_apply'
    bl_label = 'Apply Box Hide'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        obs = _hidden_selected(context)
        n = sum(1 for o in obs if apply(context, o))
        self.report({'INFO'}, f'Box Hide applied on {n} mesh(es)')
        return {'FINISHED'}


class MCH_OT_box_hide_split(bpy.types.Operator):
    """Split the hidden parts off into meshes of their own (like Split): the rest keeps the hole"""
    bl_idname = 'mch.box_hide_split'
    bl_label = 'Split Off Hidden'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        made, failed = [], []
        for ob in _hidden_selected(context):
            try:
                piece = split_off(context, ob)
            except cg.CutError as ex:
                failed.append(f'{ob.name} ({ex})')
                continue
            if piece is not None:
                made.append(piece)
        if not made:
            self.report({'WARNING'}, 'Split Off: nothing hidden' + (' | ' + '; '.join(failed) if failed else ''))
            return {'CANCELLED'}
        for o in context.selected_objects:
            o.select_set(False)
        for o in made:
            o.select_set(True)
        context.view_layer.objects.active = made[0]
        msg = f'Box Hide: split off {len(made)} part(s): ' + ', '.join(o.name for o in made)
        if failed:
            msg += ' | failed: ' + '; '.join(failed)
        self.report({'WARNING'} if failed else {'INFO'}, msg)
        return {'FINISHED'}


class MCH_OT_box_hide_cap(bpy.types.Operator):
    """Cap on / off for the selected hidden meshes"""
    bl_idname = 'mch.box_hide_cap'
    bl_label = 'Cap'
    bl_options = {'REGISTER', 'UNDO'}
    value: bpy.props.BoolProperty(default=True)

    def execute(self, context):
        context.scene.mch_hide.cap = self.value
        for o in _hidden_selected(context):
            set_cap(o, self.value)
        return {'FINISHED'}


def draw(layout, context):
    st = context.scene.mch_hide
    box = layout.box()
    box.label(text='BOX HIDE', icon='HIDE_ON')
    col = box.column(align=True)
    col.scale_y = 0.85
    col.label(text='Draw over meshes: hide inside', icon='MOUSE_LMB_DRAG')
    col.label(text='Alt + draw: show that part again', icon='EVENT_ALT')
    cut = context.scene.mch_cut                       # 0.23.17 same Depth / Targets menu as Cut (shared)
    col = box.column(align=True)
    col.prop(cut, 'depth_mode', expand=True)
    if cut.depth_mode == 'SURFACE':
        col.prop(cut, 'depth')
    col.prop(cut, 'targets', expand=True)
    row = box.row(align=True)
    row.operator('mch.box_hide_cap', text='Cap', depress=st.cap).value = True
    row.operator('mch.box_hide_cap', text='Open', depress=not st.cap).value = False
    box.prop(st, 'mirror', icon='MOD_MIRROR', toggle=True)
    row = box.row(align=True)
    row.scale_y = 1.2
    row.operator('mch.box_hide_show_all', icon='HIDE_OFF')
    row.operator('mch.box_hide_apply', icon='CHECKMARK')
    box.operator('mch.box_hide_split', icon='MOD_EDGESPLIT')
    n = sum(1 for o in context.view_layer.objects if o.type == 'MESH' and is_hidden(o))
    if n:
        box.label(text=f'{n} mesh(es) with hidden parts', icon='INFO')


CLASSES = (MCH_PG_BoxHide, MCH_OT_box_hide_show_all, MCH_OT_box_hide_apply, MCH_OT_box_hide_split,
           MCH_OT_box_hide_cap)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_hide = bpy.props.PointerProperty(type=MCH_PG_BoxHide)


def unregister():
    if hasattr(bpy.types.Scene, 'mch_hide'):
        del bpy.types.Scene.mch_hide
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
