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
VERSION = 1


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
    eps = g.interface.new_socket('Epsilon', in_out='INPUT', socket_type='NodeSocketFloat')
    eps.default_value = 1e-5
    g.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = g.nodes
    gi = N.new('NodeGroupInput')
    go = N.new('NodeGroupOutput')
    info = N.new('GeometryNodeObjectInfo')
    info.transform_space = 'RELATIVE'
    _link(g, gi.outputs['Volume'], info.inputs['Object'])
    boo = N.new('GeometryNodeMeshBoolean')
    boo.operation = 'DIFFERENCE'
    boo.solver = 'EXACT'
    boo.inputs['Self Intersection'].default_value = True
    _link(g, gi.outputs['Geometry'], boo.inputs['Mesh 1'])
    _link(g, info.outputs['Geometry'], boo.inputs['Mesh 2'])
    # Cap OFF: the faces the cut made lie on the volume's surface - delete them (an open hole)
    prox = N.new('GeometryNodeProximity')
    prox.target_element = 'FACES'
    _link(g, info.outputs['Geometry'], prox.inputs['Geometry'])
    near = N.new('FunctionNodeCompare')
    near.data_type = 'FLOAT'
    near.operation = 'LESS_THAN'
    _link(g, prox.outputs['Distance'], near.inputs['A'])
    _link(g, gi.outputs['Epsilon'], near.inputs['B'])
    nocap = N.new('FunctionNodeBooleanMath')
    nocap.operation = 'NOT'
    _link(g, gi.outputs['Cap'], nocap.inputs[0])
    sel = N.new('FunctionNodeBooleanMath')
    sel.operation = 'AND'
    _link(g, near.outputs['Result'], sel.inputs[0])
    _link(g, nocap.outputs['Boolean'], sel.inputs[1])
    dele = N.new('GeometryNodeDeleteGeometry')
    dele.domain = 'FACE'
    _link(g, boo.outputs['Mesh'], dele.inputs['Geometry'])
    _link(g, sel.outputs['Boolean'], dele.inputs['Selection'])
    _link(g, dele.outputs['Geometry'], go.inputs['Geometry'])
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
        return mod[_ident(mod.node_group, 'Volume')]
    except KeyError:
        return None


def is_hidden(ob):
    return volume_of(ob) is not None


def get_cap(ob):
    mod = ob.modifiers.get(MOD)
    return bool(mod[_ident(mod.node_group, 'Cap')]) if mod is not None else True


def set_cap(ob, value):
    mod = ob.modifiers.get(MOD)
    if mod is None:
        return
    mod[_ident(mod.node_group, 'Cap')] = bool(value)
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
        mod[_ident(g, 'Cap')] = bool(cap)
    elif mod.node_group is not g:
        mod.node_group = g
    mod[_ident(g, 'Volume')] = vol
    size = max(target.dimensions) if max(target.dimensions) > 0 else 1.0
    mod[_ident(g, 'Epsilon')] = size * 1e-4
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


def _append(vol, bm_add):
    bm = bmesh.new()
    try:
        bm.from_mesh(vol.data)
        tmp = bpy.data.meshes.new('MCH_Hide_tmp')
        try:
            bm_add.to_mesh(tmp)
            bm.from_mesh(tmp)
        finally:
            bpy.data.meshes.remove(tmp)
        bm.to_mesh(vol.data)
    finally:
        bm.free()
    vol.data.update()


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
                if not restore:
                    if vol is None:
                        vol = _new_volume(context, t)
                    for bm_part in parts:
                        _append(vol, bm_part)
                    _ensure_modifier(t, vol, st.cap)
                    done.append(t.name)
                    continue
                if vol is None:
                    untouched.append(t.name)
                    continue
                # restore: cut the drawn shape out of the hide volume
                rest_me = bpy.data.meshes.new('MCH_Hide_Restore')
                joined = bmesh.new()
                for bm_part in parts:
                    tmp = bpy.data.meshes.new('MCH_Hide_tmp')
                    bm_part.to_mesh(tmp)
                    joined.from_mesh(tmp)
                    bpy.data.meshes.remove(tmp)
                joined.to_mesh(rest_me)
                joined.free()
                rest = cg.link_temp_object(context, rest_me, 'MCH_Hide_Restore')
                try:
                    vol.hide_set(False)
                    try:
                        me, _solver = cg.boolean_result(context, vol, rest, 'DIFFERENCE', 'EXACT', False,
                                                        allow_empty=True)
                    finally:
                        vol.hide_set(True)
                finally:
                    cg.remove_object_and_mesh(rest)
                old = vol.data
                vol.data = me
                if old.users == 0:
                    bpy.data.meshes.remove(old)
                if not me.polygons:
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
    if vol is not None:
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
    if vol is not None:
        cg.remove_object_and_mesh(vol)
    return True


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
    row = box.row(align=True)
    row.operator('mch.box_hide_cap', text='Cap', depress=st.cap).value = True
    row.operator('mch.box_hide_cap', text='Open', depress=not st.cap).value = False
    box.prop(st, 'mirror', icon='MOD_MIRROR', toggle=True)
    row = box.row(align=True)
    row.scale_y = 1.2
    row.operator('mch.box_hide_show_all', icon='HIDE_OFF')
    row.operator('mch.box_hide_apply', icon='CHECKMARK')
    n = sum(1 for o in context.view_layer.objects if o.type == 'MESH' and is_hidden(o))
    if n:
        box.label(text=f'{n} mesh(es) with hidden parts', icon='INFO')


CLASSES = (MCH_PG_BoxHide, MCH_OT_box_hide_show_all, MCH_OT_box_hide_apply, MCH_OT_box_hide_cap)


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
