"""0.24.52 Groups, the Substance 3D Modeler way.

- Group: the selected parts go into a new collection with a group handle (an Empty at their middle) as parent -
  move / turn / scale the handle and the whole group follows.  Groups can hold groups.
- Ungroup: the parts go back to where they were (their old collections), handle and collection removed.
- Merge: the group's meshes (modifiers baked) become one mesh.
- Enter / Exit (scope): inside a group everything else is shown as wire and cannot be selected.
- Repetition (non-destructive, linked): Mirror (X / Y / Z planes through the handle), Radial (Count copies round
  an axis of the handle) or Kaleido (both).  The copies are made by a Geometry Nodes object that shows the group's
  collection again, so editing a part changes every copy at once; switching it off removes them.  Apply makes
  the copies real objects.

Everything is plain Blender data (collections, an Empty, one helper object) so files open without the add-on.
"""
from __future__ import annotations

import json
import math

import bpy
from mathutils import Matrix, Vector

GROUP_KEY = 'mch_group'                  # on the handle: its collection's name
FROM_KEY = 'mch_group_from'              # on a member: the collections it came from (json)
CARRIER_KEY = 'mch_group_carrier'        # on the repetition object: the handle's name
SCOPE_KEY = 'mch_scope'                  # on the scene: the handle of the group we are in
SAVED_KEY = 'mch_scope_saved'            # on other objects while in a group: [hide_select, display_type]
MOD_NAME = 'MCH_GroupRepeat'
TREE_PREFIX = 'MCH Group Repeat | '


# --- finding --------------------------------------------------------------------------------------------------

def is_group(ob):
    return ob is not None and ob.type == 'EMPTY' and GROUP_KEY in ob


def group_of(ob):
    """The nearest group handle of ``ob`` (itself, a parent, or the group a repetition object belongs to)."""
    if ob is None:
        return None
    if CARRIER_KEY in ob:
        return bpy.data.objects.get(ob[CARRIER_KEY])
    o = ob
    while o is not None:
        if is_group(o):
            return o
        o = o.parent
    return None


def collection_of(g):
    return bpy.data.collections.get(g.get(GROUP_KEY, '')) if g is not None else None


def members(g):
    """Every object in the group (nested groups included), handles of nested groups too."""
    coll = collection_of(g)
    return list(coll.all_objects) if coll is not None else []


def carrier_of(g):
    return next((o for o in bpy.data.objects if o.get(CARRIER_KEY) == g.name), None) if g is not None else None


def _world_box(objs):
    pts = []
    for o in objs:
        if o.type in {'MESH', 'CURVE', 'SURFACE', 'FONT'}:
            pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
        else:
            pts.append(o.matrix_world.translation.copy())
    if not pts:
        return Vector(), Vector((1, 1, 1))
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return (lo + hi) / 2, hi - lo


# --- group / ungroup / merge ---------------------------------------------------------------------------------

def create(context, objs, name='Group'):
    """Group ``objs``; returns the handle."""
    objs = [o for o in objs if CARRIER_KEY not in o]
    if not objs:
        return None
    parent_coll = next(iter(objs[0].users_collection), context.scene.collection)
    outer = group_of(objs[0].parent) if objs[0].parent is not None else None   # not objs[0]: it may be a group
    if parent_coll.get(GROUP_KEY) is None and collection_of(outer) is not None:
        parent_coll = collection_of(outer)                        # grouping inside a group: nest there
    coll = bpy.data.collections.new(name)
    parent_coll.children.link(coll)
    centre, size = _world_box(objs)
    g = bpy.data.objects.new(coll.name, None)
    g.empty_display_type = 'CUBE'
    g.empty_display_size = max(0.05, max(size) * 0.55)
    g.show_in_front = True
    parent_coll.objects.link(g)
    g.matrix_world = Matrix.Translation(centre)
    if outer is not None:                      # a group inside a group follows the outer handle
        g.parent = outer
        g.matrix_world = Matrix.Translation(centre)
    g[GROUP_KEY] = coll.name
    coll[GROUP_KEY] = g.name
    picked = set(objs)
    for o in objs:
        if is_group(o):                        # a nested group: its collection moves under ours
            sub = collection_of(o)
            if sub is not None:
                for pc in [c for c in bpy.data.collections if sub.name in c.children]:
                    pc.children.unlink(sub)
                if sub.name in context.scene.collection.children:
                    context.scene.collection.children.unlink(sub)
                coll.children.link(sub)
        old = [c.name for c in o.users_collection]
        o[FROM_KEY] = json.dumps(old)
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
        if o.parent is None or o.parent not in picked:
            mw = o.matrix_world.copy()
            o.parent = g
            o.matrix_world = mw
    for o in context.selected_objects:
        o.select_set(False)
    g.select_set(True)
    context.view_layer.objects.active = g
    return g


def ungroup(context, g):
    """Parts back where they were; the handle, its collection and any repetition go."""
    if not is_group(g):
        return 0
    set_repeat(context, g, mode='OFF')
    coll = collection_of(g)
    home = next(iter(g.users_collection), context.scene.collection)
    n = 0
    for o in list(coll.objects) if coll else []:
        try:
            old = [bpy.data.collections.get(c) or (context.scene.collection if c == context.scene.collection.name
                                                   else None) for c in json.loads(o.get(FROM_KEY, '[]'))]
        except ValueError:
            old = []
        old = [c for c in old if c is not None and c != coll] or [home]
        coll.objects.unlink(o)
        for c in old:
            if o.name not in c.objects:
                c.objects.link(o)
        if FROM_KEY in o:
            del o[FROM_KEY]
        if o.parent == g:
            mw = o.matrix_world.copy()
            o.parent = g.parent
            o.matrix_world = mw
        n += 1
    if coll is not None:
        for sub in list(coll.children):            # nested groups move up
            coll.children.unlink(sub)
            home.children.link(sub)
        bpy.data.collections.remove(coll)
    if context.scene.get(SCOPE_KEY) == g.name:
        exit_scope(context)
    bpy.data.objects.remove(g, do_unlink=True)
    return n


def merge(context, g):
    """The group's meshes become one mesh (modifiers baked), still in the group."""
    meshes = [o for o in members(g) if o.type == 'MESH' and CARRIER_KEY not in o]
    if len(meshes) < 2:
        return None
    dg = context.evaluated_depsgraph_get()
    for o in meshes:
        if o.modifiers:
            me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
            old = o.data
            o.modifiers.clear()
            o.data = me
            if old.users == 0:
                bpy.data.meshes.remove(old)
    first = meshes[0]
    with context.temp_override(active_object=first, object=first, selected_objects=meshes,
                               selected_editable_objects=meshes):
        bpy.ops.object.join()
    return first


def select_group(context, g):
    for o in context.selected_objects:
        o.select_set(False)
    g.select_set(True)
    context.view_layer.objects.active = g


# --- scope -------------------------------------------------------------------------------------------------

def enter_scope(context, g):
    """Work inside ``g``: everything else shows as wire and cannot be picked."""
    if not is_group(g):
        return False
    exit_scope(context)
    inside = set(members(g)) | {g}
    for o in context.scene.objects:
        if o in inside or CARRIER_KEY in o:
            continue
        o[SAVED_KEY] = json.dumps([bool(o.hide_select), o.display_type])
        o.hide_select = True
        if o.type in {'MESH', 'CURVE', 'SURFACE', 'FONT'}:
            o.display_type = 'WIRE'
    context.scene[SCOPE_KEY] = g.name
    for o in context.selected_objects:
        o.select_set(False)
    for o in inside:
        if o.type == 'MESH':
            o.select_set(True)
            context.view_layer.objects.active = o
    return True


def exit_scope(context):
    scene = context.scene
    for o in scene.objects:
        saved = o.get(SAVED_KEY)
        if saved is None:
            continue
        try:
            hs, dt = json.loads(saved)
            o.hide_select = bool(hs)
            o.display_type = str(dt)
        except (TypeError, IndexError, ValueError):
            pass
        del o[SAVED_KEY]
    was = scene.get(SCOPE_KEY)
    if SCOPE_KEY in scene:
        del scene[SCOPE_KEY]
    g = bpy.data.objects.get(was) if was else None
    if g is not None:
        select_group(context, g)
    return was is not None


def scope(context):
    name = context.scene.get(SCOPE_KEY)
    return bpy.data.objects.get(name) if name else None


# --- repetition ----------------------------------------------------------------------------------------------

def repeat_mode(g):
    return g.get('mch_rep_mode', 'OFF') if g is not None else 'OFF'


def repeat_axes(g):
    a = g.get('mch_rep_axes', [1, 0, 0]) if g is not None else [1, 0, 0]
    return tuple(bool(v) for v in a)


def repeat_axis(g):
    return g.get('mch_rep_axis', 'Z') if g is not None else 'Z'


def repeat_count(g):
    return int(g.get('mch_rep_count', 6)) if g is not None else 6


def copy_matrices(mode, axes=(True, False, False), axis='Z', count=6):
    """The copies' transforms in the handle's frame (the original itself not included)."""
    mirrors = [Matrix.Identity(4)]
    if mode in {'MIRROR', 'KALEIDO'}:
        for i, on in enumerate(axes):
            if not on:
                continue
            flip = Matrix.Identity(4)
            flip[i][i] = -1.0
            mirrors += [flip @ m for m in mirrors]
    rots = [Matrix.Identity(4)]
    if mode in {'RADIAL', 'KALEIDO'}:
        n = max(2, int(count))
        rots = [Matrix.Rotation(2.0 * math.pi * k / n, 4, axis) for k in range(n)]
    out = []
    for r in rots:
        for m in mirrors:
            t = r @ m
            if not _is_identity(t):
                out.append(t)
    return out


def _is_identity(m):
    return all(abs(m[i][j] - (1.0 if i == j else 0.0)) < 1e-9 for i in range(4) for j in range(4))


def _tree(g, mats):
    """Geometry Nodes: the group's collection (relative to the handle) once per copy matrix."""
    name = TREE_PREFIX + g.name
    tree = bpy.data.node_groups.get(name)
    if tree is None:
        tree = bpy.data.node_groups.new(name, 'GeometryNodeTree')
        tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    tree.nodes.clear()
    nodes, links = tree.nodes, tree.links
    out = nodes.new('NodeGroupOutput')
    out.location = (900, 0)
    nodes.new('NodeGroupInput').location = (-600, 200)
    info = nodes.new('GeometryNodeCollectionInfo')
    info.location = (-400, 0)
    info.transform_space = 'RELATIVE'
    info.inputs['Collection'].default_value = collection_of(g)
    join = nodes.new('GeometryNodeJoinGeometry')
    join.location = (600, 0)
    for i, m in enumerate(mats):
        loc, rot, scale = _decompose(m)
        t = nodes.new('GeometryNodeTransform')
        t.location = (100, -i * 160)
        t.inputs['Translation'].default_value = loc
        t.inputs['Rotation'].default_value = rot
        t.inputs['Scale'].default_value = scale
        links.new(info.outputs['Instances'], t.inputs['Geometry'])
        links.new(t.outputs['Geometry'], join.inputs['Geometry'])
    links.new(join.outputs['Geometry'], out.inputs['Geometry'])
    return tree


def _decompose(m):
    """(translation, euler, scale) with a mirror kept as a negative scale (R @ S, S = diag(+-1))."""
    m3 = m.to_3x3()
    s = Vector((1.0, 1.0, 1.0))
    if m3.determinant() < 0:
        # find the mirror axis combination: R = M @ S^-1 must be a rotation
        for sx in (1, -1):
            for sy in (1, -1):
                for sz in (1, -1):
                    S = Matrix.Diagonal((sx, sy, sz))
                    r = m3 @ S
                    if r.determinant() > 0 and _orthonormal(r):
                        return m.translation.copy(), r.to_euler(), Vector((sx, sy, sz))
    return m.translation.copy(), m3.to_euler(), s


def _orthonormal(r):
    p = r @ r.transposed()
    return all(abs(p[i][j] - (1.0 if i == j else 0.0)) < 1e-6 for i in range(3) for j in range(3))


def set_repeat(context, g, mode=None, axes=None, axis=None, count=None):
    """Change the group's repetition; OFF removes the copies."""
    if not is_group(g):
        return None
    if mode is not None:
        g['mch_rep_mode'] = mode
    if axes is not None:
        g['mch_rep_axes'] = [int(bool(a)) for a in axes]
    if axis is not None:
        g['mch_rep_axis'] = axis
    if count is not None:
        g['mch_rep_count'] = max(2, min(64, int(count)))
    mode = repeat_mode(g)
    car = carrier_of(g)
    if mode == 'OFF':
        if car is not None:
            data = car.data
            bpy.data.objects.remove(car, do_unlink=True)
            if data is not None and data.users == 0:
                bpy.data.meshes.remove(data)
        tree = bpy.data.node_groups.get(TREE_PREFIX + g.name)
        if tree is not None:
            bpy.data.node_groups.remove(tree)
        return None
    mats = copy_matrices(mode, repeat_axes(g), repeat_axis(g), repeat_count(g))
    tree = _tree(g, mats)
    if car is None:
        me = bpy.data.meshes.new(g.name + ' Repetition')
        car = bpy.data.objects.new(g.name + ' Repetition', me)
        for c in g.users_collection:
            c.objects.link(car)
        car[CARRIER_KEY] = g.name
        car.parent = g
        car.matrix_parent_inverse = Matrix.Identity(4)
        car.matrix_basis = Matrix.Identity(4)
        car.hide_select = True
    mod = car.modifiers.get(MOD_NAME) or car.modifiers.new(MOD_NAME, 'NODES')
    mod.node_group = tree
    return car


def make_real(context, g):
    """Apply: every copy becomes real objects (linked mesh data), the repetition is switched off."""
    if not is_group(g) or repeat_mode(g) == 'OFF':
        return 0
    coll = collection_of(g)
    gm = g.matrix_world
    gi = gm.inverted_safe()
    mats = copy_matrices(repeat_mode(g), repeat_axes(g), repeat_axis(g), repeat_count(g))
    made = 0
    sources = [o for o in members(g) if o.type in {'MESH', 'CURVE'} and not is_group(o)]
    for i, m in enumerate(mats):
        world = gm @ m @ gi
        for o in sources:
            c = o.copy()
            c.parent = None
            c.matrix_world = world @ o.matrix_world
            coll.objects.link(c)
            mw = c.matrix_world.copy()
            c.parent = g
            c.matrix_world = mw
            made += 1
    set_repeat(context, g, mode='OFF')
    return made


# --- operators ------------------------------------------------------------------------------------------------

class MCH_OT_group(bpy.types.Operator):
    """Group the selected parts (one handle moves them all; Repetition, Enter / Exit in the Mecha Menu)"""
    bl_idname = 'mch.group'
    bl_label = 'Group'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and bool(context.selected_objects)

    def execute(self, context):
        g = create(context, list(context.selected_objects))
        if g is None:
            return {'CANCELLED'}
        self.report({'INFO'}, f'{g.name}: {len(members(g))} objects grouped')
        return {'FINISHED'}


class MCH_OT_group_action(bpy.types.Operator):
    """Ungroup / Merge / Enter / Exit / Select the group of the active object"""
    bl_idname = 'mch.group_action'
    bl_label = 'Group Action'
    bl_options = {'REGISTER', 'UNDO'}
    action: bpy.props.EnumProperty(items=[
        ('UNGROUP', 'Ungroup', 'The parts go back where they were'),
        ('MERGE', 'Merge', 'The group\'s meshes become one mesh'),
        ('ENTER', 'Enter', 'Work inside the group; the rest is wire and cannot be picked'),
        ('EXIT', 'Exit', 'Back out of the group'),
        ('SELECT', 'Select Group', 'Select the group handle (its Repetition card shows)')], default='SELECT')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        if self.action == 'EXIT':
            if not exit_scope(context):
                return {'CANCELLED'}
            return {'FINISHED'}
        g = group_of(context.active_object) or scope(context)
        if g is None:
            self.report({'WARNING'}, 'Not in a group')
            return {'CANCELLED'}
        if self.action == 'UNGROUP':
            n = ungroup(context, g)
            self.report({'INFO'}, f'Ungrouped {n} objects')
        elif self.action == 'MERGE':
            if merge(context, g) is None:
                self.report({'WARNING'}, 'A group needs two or more meshes to merge')
                return {'CANCELLED'}
        elif self.action == 'ENTER':
            enter_scope(context, g)
        else:
            select_group(context, g)
        return {'FINISHED'}


class MCH_OT_group_repeat(bpy.types.Operator):
    """Repetition of the active group: Off / Mirror / Radial / Kaleido (linked copies, non-destructive)"""
    bl_idname = 'mch.group_repeat'
    bl_label = 'Group Repetition'
    bl_options = {'REGISTER', 'UNDO'}
    mode: bpy.props.EnumProperty(items=[(m, m.title(), '') for m in ('OFF', 'MIRROR', 'RADIAL', 'KALEIDO')],
                                 default='MIRROR')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and group_of(context.active_object) is not None

    def execute(self, context):
        g = group_of(context.active_object)
        set_repeat(context, g, mode=self.mode)
        select_group(context, g)
        context.window_manager.mch_sym_card = g.name
        return {'FINISHED'}


CLASSES = (MCH_OT_group, MCH_OT_group_action, MCH_OT_group_repeat)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
