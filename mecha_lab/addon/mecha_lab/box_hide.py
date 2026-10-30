"""0.23.16 Box Hide (from the HTML prototype): draw a shape over meshes to hide what is inside it.

* Non-destructive: every hidden mesh gets one Geometry Nodes modifier (``MCH_BoxHide``) that subtracts a
  hidden "hide volume" object (the drawn shapes pushed through the view, like the Cut cutter).
* Draw again = hide more (the volume grows), Alt + draw = restore that part (cut out of the volume).
* Cap (per mesh): ON = the cut is closed with new faces (a solid), OFF = an open hole (just hidden).
* Mirror X: every shape is also hidden on the other side of the mesh (its local X).
* 0.24.58 Follow Symmetry: on a part with a live Mirror / Radial the shape is hidden on every symmetric copy too
  (the hiding comes after the Mirror in the stack, so it used to hide only the side you drew on).
* Show All = remove the modifier (nothing was changed), Apply = make the hiding permanent.
"""
from __future__ import annotations

import bmesh
import bpy
from mathutils import Matrix, Vector

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


def _manifold_in(target, mod):
    """0.24.81 Is the geometry that reaches the Box Hide modifier one closed solid?  It was read off the base mesh:
    with a live Mirror before it (Follow Symmetry) the mirrored mesh has a seam of doubled edges, the Manifold
    solver got non-manifold input and gave nothing back - the whole part vanished.  The modifiers before it are
    evaluated and looked at."""
    idx = target.modifiers.find(mod.name)
    before = [m for m in target.modifiers[:idx] if m.show_viewport] if idx > 0 else []
    if not before:
        return cg.non_manifold_edge_count(target.data) == 0
    saved = [(m, m.show_viewport) for m in target.modifiers]
    try:
        for m, _show in saved:
            m.show_viewport = m in before
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
        me = target.evaluated_get(dg).data
        return cg.non_manifold_edge_count(me) == 0
    except (RuntimeError, ReferenceError, AttributeError):
        return False
    finally:
        for m, show in saved:
            m.show_viewport = show


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
    cg.gn_set(mod, _ident(g, 'Manifold'), _manifold_in(target, mod))
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


def _transformed(bm_src, mat):
    """The shape moved by ``mat`` (world space in, world space out); a reflection keeps it outward facing."""
    bm = bm_src.copy()
    bm.transform(mat)
    if mat.to_3x3().determinant() < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    return bm


def symmetry_copies(context, target):
    """World matrices of every symmetric copy of ``target`` besides itself: its live Mirror (all axis combinations)
    and, when it repeats round the Radial Symmetry centre, every turn (and turn x mirror, Kaleido)."""
    mats = [Matrix.Identity(4)] + cg.mirror_reflections(target)
    from . import radial_sym
    st = getattr(context.scene, 'mch_rsym', None)
    if st is not None and st.active and st.pivot is not None and target.modifiers.get(radial_sym.MOD_NAME):
        turns = radial_sym.rotations(st.pivot.matrix_world.translation, radial_sym.axis_world(st), st.count)
        mats = [r @ m for r in turns for m in mats]
    ident = Matrix.Identity(4)
    out = []
    for m in mats:
        if all(abs(m[i][j] - ident[i][j]) < 1e-6 for i in range(4) for j in range(4)):
            continue
        out.append(m)
    return out


def _flat(me):
    for p in me.polygons:
        p.use_smooth = False


UNIONS_KEY = 'mch_hide_unions'          # 0.24.83 how many shapes went into the volume (each one a little deeper)


def _stretched(planes, f):
    """The near / far planes pushed apart by ``f`` of their distance: a shape whose caps are not coplanar with the
    ones already in the volume (the Exact union of two prisms on the same caps came back non-manifold - the second
    Box Hide on a part, or a strip over a hidden part, failed)."""
    near, far = planes
    d = far - near
    return near - d * f, far + d * f


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
            try:                               # 0.24.83 AUTO: Manifold on two clean prisms (coplanar caps are
                me, _solver = cg.boolean_result(context, vol, other, op, 'AUTO', False, allow_empty=True)  # fine), Exact after
            except cg.CutError:
                # 0.24.83 coplanar caps / an edge on an edge: the shape grown by a hair and tried once more
                bm = bmesh.new()
                bm.from_mesh(other.data)
                c = sum((v.co for v in bm.verts), Vector()) / max(1, len(bm.verts))
                bmesh.ops.scale(bm, vec=(1.003, 1.003, 1.003), space=Matrix.Translation(-c), verts=bm.verts[:])
                bm.to_mesh(other.data)
                bm.free()
                me, _solver = cg.boolean_result(context, vol, other, op, 'AUTO', False, allow_empty=True)
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
    cut = context.scene.mch_cut
    groups = cg.prepare_loops(loops)
    near, far = ce._planes(context, targets, projector, [g[0] for g in groups])
    from . import mesh_fix
    fixed = mesh_fix.auto_fix(context, targets, 'Box Hide') if not restore else {}   # 0.24.81 a broken part first
    done, untouched, followed = [], [], []
    shapes = []
    try:
        for t in targets:
            planes = (near, far)
            if cut.depth_mode == 'SURFACE' and len(targets) > 1:      # 0.24.83 a pocket from each part's own surface
                planes = ce.own_pocket(context, t, groups, projector, cut) or planes
            vol0 = volume_of(t)
            k = int(vol0.get(UNIONS_KEY, 0)) if vol0 is not None else 0
            if vol0 is not None and vol0.data.polygons:
                planes = _stretched(planes, 0.004 * (k + 1))          # 0.24.83 not coplanar with the shapes in there
            shape_me = cg.build_cutter_mesh(groups, projector, *planes, 'MCH_Hide_Shape')
            shapes.append(shape_me)
            bm_shape = bmesh.new()
            bm_shape.from_mesh(shape_me)
            parts = [bm_shape]
            copies = symmetry_copies(context, t) if st.follow_symmetry else []
            parts += [_transformed(bm_shape, m) for m in copies]
            if st.mirror and not copies:
                parts.append(_mirrored(bm_shape, t))
            if copies:
                followed.append(len(copies))
            try:
                vol = volume_of(t)
                if vol is not None:
                    _detach_sharers(context, vol, t)
                if not restore:
                    if vol is None:
                        vol = _new_volume(context, t)
                    for bm_part in parts:
                        _combine(context, vol, bm_part, 'UNION')
                    vol[UNIONS_KEY] = k + 1
                    _ensure_modifier(t, vol, st.cap)
                    done.append(t.name)
                    continue
                if vol is None:
                    untouched.append(t.name)
                    continue
                # restore: cut the drawn shape out of the hide volume
                for bm_part in parts:
                    _combine(context, vol, bm_part, 'DIFFERENCE')
                vol[UNIONS_KEY] = k + 1
                if not vol.data.polygons:
                    show_all(t)             # nothing hidden any more
                else:
                    t.update_tag()
                done.append(t.name)
            finally:
                for bm_part in parts:
                    bm_part.free()
    finally:
        for shape_me in shapes:
            bpy.data.meshes.remove(shape_me)
    verb = 'Restored' if restore else 'Hidden'
    msg = f'Box Hide: {verb} on {", ".join(done)}' if done else 'Box Hide: nothing hidden there'
    if untouched:
        msg += ' | nothing hidden on: ' + ', '.join(untouched)
    if followed:
        msg += f' | also on {max(followed)} symmetric cop{"y" if max(followed) == 1 else "ies"}'
    elif st.mirror:
        msg += ' | Mirror X'
    return msg + mesh_fix.auto_fix_note(fixed)


def show_all(ob):
    """Remove the hiding (the mesh itself was never changed)."""
    vol = volume_of(ob)
    mod = ob.modifiers.get(MOD)
    if mod is not None:
        ob.modifiers.remove(mod)
    if vol is not None and not _sharers(vol, ob):      # a duplicate may still use it
        cg.remove_object_and_mesh(vol)
    ob.update_tag()


def _flag_volume(vol):
    """0.24.95 the volume's faces carry the cutter flag, so the faces it leaves on the part are known and become
    Edge Memory marks (the Boolean node passes face attributes through)."""
    if vol is None or vol.type != 'MESH' or not len(vol.data.polygons):
        return
    me = vol.data
    attr = me.attributes.get(cg.CUTTER_ATTR)
    if attr is None or attr.domain != 'FACE':
        if attr is not None:
            me.attributes.remove(attr)
        attr = me.attributes.new(cg.CUTTER_ATTR, 'BOOLEAN', 'FACE')
    attr.data.foreach_set('value', [True] * len(me.polygons))


def apply(context, ob):
    """Make the hiding permanent: the modifier is applied (other modifiers stay)."""
    mod = ob.modifiers.get(MOD)
    if mod is None:
        return False
    vol = volume_of(ob)
    _flag_volume(vol)
    with context.temp_override(object=ob, active_object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    cg.remove_cutter_attribute(ob.data)          # 0.24.95 -> Edge Memory marks on the hole's edges
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
    _flag_volume(vol)
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
    cg.remove_cutter_attribute(me)        # 0.24.95 -> Edge Memory marks on the piece's cut edges
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
                                   description='Also hide the same part on the other side of the mesh (its local X) - '
                                               'for meshes without a live Mirror')
    follow_symmetry: bpy.props.BoolProperty(name='Follow Symmetry', default=True,
                                            description='On a part with a live Mirror / Radial Symmetry: the same part '
                                                        'is hidden on every symmetric copy too')


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
    row = box.row(align=True)
    row.prop(st, 'follow_symmetry', icon='MOD_MIRROR', toggle=True)
    row.prop(st, 'mirror', toggle=True)
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
