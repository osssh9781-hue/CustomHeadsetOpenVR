"""Non-destructive mesh mirrors and linked collection-instance symmetry rigs.

Independently authored for Mecha Lab. Blender 4.3+ APIs.
"""
import bpy
from mathutils import Matrix, Vector
from bpy.props import BoolProperty, EnumProperty, FloatProperty, PointerProperty

MOD_NAME = 'MCH_Mirror'
RIG_TAG = '_mch_collection_mirror_role'


def _mesh_filter(self, obj):
    return obj.type == 'MESH'


def _valid_collection(self, coll):
    return coll is not None


class MCH_PG_Mirror(bpy.types.PropertyGroup):
    space: EnumProperty(name='Axis Space', items=[
        ('WORLD', 'World', 'Mirror across global X/Y/Z planes'),
        ('LOCAL', 'Local', 'Mirror around the mesh object origin and local axes')], default='WORLD')
    center: EnumProperty(name='Mirror Plane Center', items=[
        ('ORIGIN', 'World Origin', 'Plane passes through (0, 0, 0)'),
        ('CURSOR', '3D Cursor', 'Use current cursor position; global axis directions remain unchanged')], default='ORIGIN')
    x: BoolProperty(name='X', default=True)
    y: BoolProperty(name='Y', default=False)
    z: BoolProperty(name='Z', default=False)
    bisect: BoolProperty(name='Bisect', default=False, description='Cut source geometry on selected mirror planes before mirroring')
    clipping: BoolProperty(name='Clipping', default=True, description='Prevent vertices crossing the mirror plane while editing')
    merge: BoolProperty(name='Merge', default=True)
    merge_distance: FloatProperty(name='Merge Distance', default=0.001, min=0.0, max=1.0, precision=5)
    source_collection: PointerProperty(name='Parts Collection', type=bpy.types.Collection)
    collection_axis: EnumProperty(name='Pair Axis', items=[
        ('X', 'World X', 'Reflect assembly instances across X plane'),
        ('Y', 'World Y', 'Reflect assembly instances across Y plane'),
        ('Z', 'World Z', 'Reflect assembly instances across Z plane')], default='X')
    collection_center: EnumProperty(name='Pair Center', items=[
        ('ORIGIN', 'World Origin', 'Use world (0,0,0) plane'),
        ('CURSOR', '3D Cursor', 'Use current cursor location as fixed mirror plane')], default='ORIGIN')
    collection_initial_offset: FloatProperty(
        name='Start Offset', default=1.0, min=0.001, soft_max=5.0,
        description='When cursor is on the mirror center, place MASTER this far onto the positive axis')


def _remove_unused_pivot(pivot):
    if pivot is None or pivot.name not in bpy.data.objects or not pivot.get('_mch_world_pivot'):
        return
    if not any(m.type == 'MIRROR' and m.mirror_object == pivot
               for ob in bpy.data.objects for m in ob.modifiers):
        bpy.data.objects.remove(pivot, do_unlink=True)


def _activate(context, ob):
    for selected in context.selected_objects:
        selected.select_set(False)
    if ob.hide_get():
        ob.hide_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob


class MCH_OT_mesh_mirror(bpy.types.Operator):
    bl_idname = 'mch.mesh_mirror'
    bl_label = 'Create / Update Mesh Mirror'
    bl_description = 'Add or update a live Mirror modifier; world mode uses a fixed world-aligned pivot Empty'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and bool(context.selected_objects) and any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        p = context.scene.mch_mirror
        if not any((p.x, p.y, p.z)):
            self.report({'WARNING'}, 'Enable at least one mirror axis')
            return {'CANCELLED'}
        count = 0
        scene = context.scene
        targets = [o for o in context.selected_objects if o.type == 'MESH' and o.library is None]
        for obj in targets:
            mod = obj.modifiers.get(MOD_NAME)
            if mod and mod.type != 'MIRROR':
                self.report({'WARNING'}, f'{obj.name}: existing name belongs to another modifier')
                continue
            old_pivot = mod.mirror_object if mod and mod.type == 'MIRROR' else None
            if mod is None:
                mod = obj.modifiers.new(MOD_NAME, 'MIRROR')
            if p.space == 'WORLD':
                pivot = old_pivot if old_pivot and old_pivot.get('_mch_world_pivot') else None
                if pivot is None:
                    pivot = bpy.data.objects.new(f'MCH World Pivot - {obj.name}', None)
                    scene.collection.objects.link(pivot)
                    pivot['_mch_world_pivot'] = True
                    pivot.empty_display_type = 'ARROWS'
                    pivot.empty_display_size = 0.16
                    pivot.hide_render = True
                pivot.matrix_world = Matrix.Translation(
                    Vector(scene.cursor.location) if p.center == 'CURSOR' else Vector((0, 0, 0)))
                mod.mirror_object = pivot
            else:
                mod.mirror_object = None
                _remove_unused_pivot(old_pivot)
            mod.use_axis[0] = p.x
            mod.use_axis[1] = p.y
            mod.use_axis[2] = p.z
            for index in range(3):
                mod.use_bisect_axis[index] = p.bisect and (p.x, p.y, p.z)[index]
            mod.use_clip = p.clipping
            mod.use_mirror_merge = p.merge
            mod.merge_threshold = p.merge_distance
            count += 1
        if count:
            self.report({'INFO'}, f'Live mirror updated on {count} mesh(es)')
            return {'FINISHED'}
        return {'CANCELLED'}


class MCH_OT_mesh_mirror_apply(bpy.types.Operator):
    bl_idname = 'mch.mesh_mirror_apply'
    bl_label = 'Apply Mesh Mirror'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return context.mode == 'OBJECT' and ob and ob.type == 'MESH' and ob.modifiers.get(MOD_NAME) is not None

    def execute(self, context):
        ob = context.active_object
        mod = ob.modifiers.get(MOD_NAME)
        if not mod or mod.type != 'MIRROR':
            self.report({'WARNING'}, 'No Mecha Lab Mirror modifier on active mesh')
            return {'CANCELLED'}
        if ob.library or (ob.data and ob.data.library):
            self.report({'ERROR'}, 'Linked library meshes cannot be applied directly')
            return {'CANCELLED'}
        helper = mod.mirror_object
        original_selected = list(context.selected_objects)
        active = context.view_layer.objects.active
        try:
            _activate(context, ob)
            from . import core_geometry
            core_geometry.apply_single_modifier(context, ob, mod, getattr(getattr(context.scene, 'mch_cut', None), 'shared_mesh', 'SINGLE'))
        except (RuntimeError, TypeError, ValueError) as exc:
            self.report({'ERROR'}, f'Mirror not applied: {exc}')
            return {'CANCELLED'}
        finally:
            for s in list(context.selected_objects):
                s.select_set(False)
            for s in original_selected:
                if s.name in bpy.data.objects:
                    s.select_set(True)
            if active and active.name in bpy.data.objects:
                context.view_layer.objects.active = active
        _remove_unused_pivot(helper)
        return {'FINISHED'}


class MCH_OT_mesh_mirror_remove(bpy.types.Operator):
    bl_idname = 'mch.mesh_mirror_remove'
    bl_label = 'Remove Mesh Mirror'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return bool(ob and ob.type == 'MESH' and ob.modifiers.get(MOD_NAME))

    def execute(self, context):
        obj = context.active_object
        mod = obj.modifiers.get(MOD_NAME)
        helper = mod.mirror_object if mod.type == 'MIRROR' else None
        obj.modifiers.remove(mod)
        _remove_unused_pivot(helper)
        return {'FINISHED'}


def _tagged_empty(scene, name, role):
    ob = bpy.data.objects.new(name, None)
    scene.collection.objects.link(ob)
    ob[RIG_TAG] = role
    ob.empty_display_size = 0.15
    ob.empty_display_type = 'SPHERE' if role == 'PIVOT' else 'PLAIN_AXES'
    ob.hide_render = True
    return ob


def _instance(scene, coll, name, role):
    ob = _tagged_empty(scene, name, role)
    ob.instance_type = 'COLLECTION'
    ob.instance_collection = coll
    return ob


class MCH_OT_collection_mirror(bpy.types.Operator):
    bl_idname = 'mch.collection_mirror'
    bl_label = 'Create Linked Collection Mirror'
    bl_description = 'Two linked collection instances; moving or rotating MASTER updates mirrored side using world-axis reflection'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.scene is not None

    def execute(self, context):
        s = context.scene
        p = s.mch_mirror
        coll = p.source_collection
        if not coll:
            self.report({'WARNING'}, 'Choose a source Collection first')
            return {'CANCELLED'}
        # Collection instances must never point to a collection containing the instance rig.
        # All rig controls live in the scene root, not inside source collection.
        if coll == s.collection:
            self.report({'ERROR'}, 'Cannot instance the scene root collection')
            return {'CANCELLED'}
        axis = 'XYZ'.index(p.collection_axis)
        center = Vector(s.cursor.location) if p.collection_center == 'CURSOR' else Vector((0, 0, 0))
        position = Vector(s.cursor.location)
        if (position - center).length < 1e-6:
            position[axis] += p.collection_initial_offset
        name = coll.name
        pivot = _tagged_empty(s, f'MCH {name} - Symmetry Center', 'PIVOT')
        pivot.location = center
        mirror_root = _tagged_empty(s, f'MCH {name} - Mirror Axis', 'REFLECTION')
        mirror_root.parent = pivot
        mirror_root.scale[axis] = -1.0
        mirror_root.hide_set(True)
        master = _instance(s, coll, f'MCH {name} - MASTER', 'MASTER')
        master.parent = pivot
        master.location = position - center
        master.rotation_euler = s.cursor.rotation_euler.copy()
        clone = _instance(s, coll, f'MCH {name} - MIRRORED', 'MIRRORED')
        clone.parent = mirror_root
        copy = clone.constraints.new('COPY_TRANSFORMS')
        copy.name = 'MCH_Symmetry_LiveLink'
        copy.target = master
        copy.owner_space = 'LOCAL'
        copy.target_space = 'LOCAL'
        copy.mix_mode = 'REPLACE'
        # Store object references as Blender native pointer properties (not fragile names).
        master['mch_mirror_axis'] = p.collection_axis
        _activate(context, master)
        context.view_layer.update()
        self.report({'INFO'}, 'Move/rotate MASTER instance; MIRRORED follows. Edit source collection to update both.')
        return {'FINISHED'}


class MCH_OT_collection_mirror_remove(bpy.types.Operator):
    bl_idname = 'mch.collection_mirror_remove'
    bl_label = 'Remove Collection Mirror Rig'
    bl_description = 'Remove only the generated mirror rig; source Collection and its mesh contents are left intact'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(context.active_object and context.active_object.get(RIG_TAG))

    def execute(self, context):
        ob = context.active_object
        role = ob.get(RIG_TAG)
        if role == 'PIVOT':
            pivot = ob
        elif role == 'REFLECTION':
            pivot = ob.parent
        elif role == 'MASTER':
            pivot = ob.parent
        elif role == 'MIRRORED':
            pivot = ob.parent.parent if ob.parent else None
        else:
            return {'CANCELLED'}
        if not pivot or pivot.get(RIG_TAG) != 'PIVOT':
            self.report({'WARNING'}, 'Could not locate generated symmetry rig')
            return {'CANCELLED'}
        owned = [o for o in bpy.data.objects if o.get(RIG_TAG) and
                 (o == pivot or o.parent == pivot or (o.parent and o.parent.parent == pivot))]
        for item in owned:
            bpy.data.objects.remove(item, do_unlink=True)
        self.report({'INFO'}, 'Mirror rig removed; source Collection preserved')
        return {'FINISHED'}


class MCH_PT_mirror(bpy.types.Panel):
    bl_icon = 'MOD_MIRROR'
    bl_parent_id = 'MCH_PT_main'
    bl_label = 'Mirror | World / Local / Collections'
    bl_idname = 'MCH_PT_mirror'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'


    @classmethod
    def poll(cls, context):
        from . import tool_state
        return tool_state.tool_is(context, 'MIRROR')

    def draw(self, context):
        layout = self.layout
        p = context.scene.mch_mirror
        layout.label(text='Mesh Mirror (non-destructive)')
        layout.prop(p, 'space', expand=True)
        if p.space == 'WORLD':
            layout.prop(p, 'center', expand=True)
        row = layout.row(align=True)
        row.prop(p, 'x', toggle=True)
        row.prop(p, 'y', toggle=True)
        row.prop(p, 'z', toggle=True)
        col = layout.column(align=True)
        col.prop(p, 'bisect')
        col.prop(p, 'clipping')
        col.prop(p, 'merge')
        if p.merge:
            col.prop(p, 'merge_distance')
        layout.operator('mch.mesh_mirror', text='CREATE / UPDATE MIRROR', icon='MOD_MIRROR')
        ob = context.active_object
        mod = ob.modifiers.get(MOD_NAME) if ob and ob.type == 'MESH' else None
        if mod and mod.type == 'MIRROR':
            box = layout.box()
            box.label(text='Active mirror: ' + ob.name)
            row = box.row(align=True)
            for i, axis in enumerate('XYZ'):
                row.prop(mod, 'use_axis', index=i, text=axis, toggle=True)
            box.prop(mod, 'use_clip')
            box.prop(mod, 'use_mirror_merge')
            row = box.row(align=True)
            row.operator('mch.mesh_mirror_apply', text='Apply', icon='CHECKMARK')
            row.operator('mch.mesh_mirror_remove', text='Remove', icon='X')
        layout.separator()
        layout.label(text='Linked Collection Mirror (live)')
        layout.prop(p, 'source_collection')
        layout.prop(p, 'collection_axis', expand=True)
        layout.prop(p, 'collection_center', expand=True)
        layout.prop(p, 'collection_initial_offset')
        layout.operator('mch.collection_mirror', text='CREATE COLLECTION PAIR', icon='OUTLINER_COLLECTION')
        layout.label(text='Move MASTER; opposite instance follows.')
        layout.label(text='Editing source Collection updates both.')
        if ob and ob.get(RIG_TAG):
            layout.operator('mch.collection_mirror_remove', text='Remove This Mirror Rig', icon='TRASH')


CLASSES = (
    MCH_PG_Mirror,
    MCH_OT_mesh_mirror, MCH_OT_mesh_mirror_apply, MCH_OT_mesh_mirror_remove,
    MCH_OT_collection_mirror, MCH_OT_collection_mirror_remove,
    MCH_PT_mirror,
)
