"""Mecha Lab: snap/curvature-conform an existing mesh to a second mesh.

No processing during mouse movement. Each reprojection is an explicit command;
a shape key exposes an instant, non-destructive strength slider afterwards.
"""

import bpy
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from bpy.props import BoolProperty, EnumProperty, FloatProperty, PointerProperty

_KEY = 'MCH Surface Conform'


class MCH_PG_Conform(bpy.types.PropertyGroup):
    mode: EnumProperty(name='Method', items=[
        ('SNAP', 'Surface Snap', 'Move and rotate rigid piece onto surface'),
        ('WRAP', 'Surface Wrap', 'Bend the existing mesh across the target curvature, preserving local thickness'),
    ], default='WRAP')
    offset: FloatProperty(name='Surface Gap', description='Distance from target mesh along the target normal',
                          default=.01, soft_min=-.2, soft_max=.5, precision=4, unit='LENGTH')
    align_first: BoolProperty(name='Align Before Wrap', description='Place the source bottom center at the nearest surface point and rotate local Z to the normal', default=True)
    wrap_strength: FloatProperty(name='Deformation Strength', description='Blend source between undeformed and conformed shape key',default=1.0, min=0.0, max=1.0, subtype='FACTOR')
    max_dist: FloatProperty(name='Projection Limit', description='0 = automatic reach; limit on ray distance otherwise', default=0.0, min=0.0, soft_max=5.0, unit='LENGTH')


def _get_pair(context):
    target = context.view_layer.objects.active
    selected = [x for x in context.selected_objects if x.type == 'MESH']
    if target is None or target.type != 'MESH' or len(selected) != 2:
        raise ValueError('Select exactly 2 mesh objects; active/yellow mesh = target surface')
    source = next((x for x in selected if x != target), None)
    if source is None or source == target:
        raise ValueError('Source and target must be different mesh objects')
    return source, target


def _tree(context, target):
    # BVH is evaluated once; do not evaluate after introducing shape keys.
    try:
        return BVHTree.FromObject(target, context.evaluated_depsgraph_get())
    except Exception as exc:
        raise ValueError('Could not build target BVH: ' + str(exc)) from exc


def _nearest_world(target, tree, wpoint):
    inv = target.matrix_world.inverted_safe()
    co, normal, face, _ = tree.find_nearest(inv @ wpoint)
    if co is None:
        return None
    world_normal = (inv.transposed().to_3x3() @ normal).normalized()
    return target.matrix_world @ co, world_normal


def _cast_world(target, tree, world_origin, world_dir, reach):
    inv = target.matrix_world.inverted_safe()
    local_vec = inv.to_3x3() @ world_dir
    scale = local_vec.length
    if scale < 1e-10:
        return None
    co, normal, face, _ = tree.ray_cast(inv @ world_origin, local_vec / scale, reach * scale)
    if co is None:
        return None
    return target.matrix_world @ co, (inv.transposed().to_3x3() @ normal).normalized()


def _bottom_center_local(source):
    bbox = [Vector(corner) for corner in source.bound_box]
    if not bbox:
        return Vector((0.0, 0.0, 0.0))
    return Vector((sum(v.x for v in bbox) / len(bbox),
                   sum(v.y for v in bbox) / len(bbox),
                   min(v.z for v in bbox)))


def _snap(source, target, tree, gap):
    bottom_world = source.matrix_world @ _bottom_center_local(source)
    nearest = _nearest_world(target, tree, bottom_world)
    if not nearest:
        raise ValueError('Target has no raycastable triangles')
    p, normal = nearest
    # Rotate the *current* source local Z to the target surface normal.
    old_z = (source.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
    rotation = old_z.rotation_difference(normal).to_matrix().to_4x4()
    original = source.matrix_world.copy()
    source.matrix_world = Matrix.Translation(p + normal * gap) @ rotation @ Matrix.Translation(-bottom_world) @ original
    return p, normal


def _base_key_and_wrap(source):
    if source.data.users > 1:
        # Avoid secretly modifying another object sharing the same mesh datablock.
        source.data = source.data.copy()
    keys = source.data.shape_keys.key_blocks if source.data.shape_keys else None
    if keys and any(k.name not in ('Basis', _KEY) for k in keys):
        raise ValueError('This beta does not support sources with other shape keys; duplicate/apply them first')
    if not keys:
        source.shape_key_add(name='Basis', from_mix=False)
        source.shape_key_add(name=_KEY, from_mix=False)
    elif _KEY not in keys:
        source.shape_key_add(name=_KEY, from_mix=False)
    return source.data.shape_keys.key_blocks[_KEY]


def project_curvature(context, source, target, settings, allow_snap=True):
    """Create/recalculate a shape key, preserving vertical local distances.

    Projection direction is the source's aligned local +Z. A planar patch can
    bend around curved hull geometry without flattening all thickness to zero.
    If a ray misses the target, leave the corresponding vertex unchanged.
    """
    if source.type != 'MESH' or target.type != 'MESH' or len(source.data.vertices) == 0:
        raise ValueError('Source and target must contain mesh geometry')
    if source.data.shape_keys and any(k.name not in ('Basis', _KEY) for k in source.data.shape_keys.key_blocks):
        raise ValueError('Cannot wrap a mesh with existing unrelated shape keys')
    tree = _tree(context, target)
    if allow_snap and settings.align_first:
        anchor, axis = _snap(source, target, tree, settings.offset)
    else:
        base = source.matrix_world @ _bottom_center_local(source)
        nearest = _nearest_world(target, tree, base)
        if nearest is None:
            raise ValueError('The target mesh contains no valid surface')
        anchor, _normal = nearest
        axis = (source.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
    # Use the original (Basis) vertex coordinates to avoid cumulative distortion.
    key = _base_key_and_wrap(source)
    basis = source.data.shape_keys.key_blocks['Basis']
    mat = source.matrix_world.copy()
    inv = mat.inverted_safe()
    extent = max((target.dimensions.length + source.dimensions.length) * 2.0, 1.0)
    reach = settings.max_dist if settings.max_dist > 0 else extent
    reach = max(reach, .001)
    center = anchor + axis * settings.offset
    misses = 0
    for i, base in enumerate(basis.data):
        p = mat @ base.co
        height = (p - center).dot(axis)
        # Ray origins on a common half-space plane prevent large upper vertices
        # from sampling the wrong face. Project in the fixed oriented axis.
        start = p + axis * reach * .45
        hit = _cast_world(target, tree, start, -axis, reach)
        if hit:
            hit_point, normal = hit
            result = hit_point + normal * (height + settings.offset)
            key.data[i].co = inv @ result
        else:
            key.data[i].co = base.co
            misses += 1
    key.value = settings.wrap_strength
    source['mch_conform_target'] = target.name
    source['mch_conform_kind'] = 'WRAP'
    source['mch_conform_project_misses'] = misses
    return misses, len(basis.data)


class MCH_OT_surface_conform(bpy.types.Operator):
    bl_idname = 'mch.surface_conform'
    bl_label = 'Surface Snap / Wrap'
    bl_description = 'Two selected meshes: non-active source conforms to active/yellow target mesh'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(context.mode == 'OBJECT' and context.active_object and context.active_object.type == 'MESH')

    def execute(self, context):
        try:
            source, target = _get_pair(context)
            settings = context.scene.mch_conform
            if settings.mode == 'SNAP':
                _snap(source, target, _tree(context, target), settings.offset)
                source['mch_conform_target'] = target.name
                source['mch_conform_kind'] = 'SNAP'
                self.report({'INFO'}, 'Surface Snap: part aligned (rigid, no mesh deformation)')
            else:
                missed, count = project_curvature(context, source, target, settings)
                self.report({'WARNING' if missed else 'INFO'},
                            'Surface Wrap projected %d/%d vertices; strength via shape key' % (count - missed, count))
            for o in context.selected_objects:
                o.select_set(False)
            source.select_set(True)
            context.view_layer.objects.active = source
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}


class MCH_OT_surface_conform_reproject(bpy.types.Operator):
    bl_idname = 'mch.surface_conform_reproject'
    bl_label = 'Reproject Surface Wrap'
    bl_description = 'Recalculate the deformation shape key using the saved target, after adjusting offset or target shape'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        o = context.active_object
        return context.mode == 'OBJECT' and o and o.type == 'MESH' and o.get('mch_conform_kind') == 'WRAP'

    def execute(self, context):
        source = context.active_object
        target = bpy.data.objects.get(source.get('mch_conform_target', ''))
        if not target or target.type != 'MESH':
            self.report({'ERROR'}, 'Original wrap target no longer exists')
            return {'CANCELLED'}
        try:
            misses, count = project_curvature(context, source, target, context.scene.mch_conform, allow_snap=False)
            self.report({'WARNING' if misses else 'INFO'}, 'Reprojected %d/%d points' % (count - misses, count))
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}


class MCH_OT_surface_conform_clear(bpy.types.Operator):
    bl_idname = 'mch.surface_conform_clear'
    bl_label = 'Remove Surface Wrap'
    bl_description = 'Remove Mecha Lab deformation shape key; underlying mesh basis is preserved'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        o = context.active_object
        return context.mode == 'OBJECT' and o and o.type == 'MESH' and o.get('mch_conform_kind') == 'WRAP'

    def execute(self, context):
        o = context.active_object
        kb = o.data.shape_keys.key_blocks.get(_KEY) if o.data.shape_keys else None
        if kb:
            o.shape_key_remove(kb)
        for field in ('mch_conform_kind', 'mch_conform_target', 'mch_conform_project_misses'):
            if field in o:
                del o[field]
        self.report({'INFO'}, 'Surface Wrap shape key removed (object position remains)')
        return {'FINISHED'}


class MCH_PT_surface_conform(bpy.types.Panel):
    bl_parent_id = 'MCH_PT_main'
    bl_label = 'Surface Conform | Snap / Wrap'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    @classmethod
    def poll(cls, context):
        return bool(context.scene and hasattr(context.scene, 'mch_settings') and context.scene.mch_settings.mch_active_tool == 'SURFACE')

    def draw(self, context):
        layout = self.layout
        s = context.scene.mch_conform
        layout.label(text='Select 2 meshes; yellow active = surface', icon='SNAP_ON')
        layout.prop(s, 'mode', expand=True)
        layout.prop(s, 'offset', slider=True)
        if s.mode == 'WRAP':
            layout.prop(s, 'align_first')
            layout.prop(s, 'max_dist')
            layout.prop(s, 'wrap_strength', slider=True)
        layout.operator('mch.surface_conform', text='SNAP / WRAP TO ACTIVE', icon='MOD_SHRINKWRAP')
        ob = context.active_object
        if ob and ob.type == 'MESH' and ob.get('mch_conform_kind') == 'WRAP':
            layout.separator()
            layout.label(text='Editing: ' + ob.name)
            layout.label(text='Surface: ' + ob.get('mch_conform_target', '(missing)'))
            if ob.data.shape_keys:
                key = ob.data.shape_keys.key_blocks.get(_KEY)
                if key:
                    layout.prop(key, 'value', text='Live Bend Strength', slider=True)
            row = layout.row(align=True)
            row.operator('mch.surface_conform_reproject', text='REPROJECT', icon='FILE_REFRESH')
            row.operator('mch.surface_conform_clear', text='REMOVE', icon='X')
            layout.label(text='Reproject after modifying target/offset')
            layout.label(text='Heavy mesh: projection only on command')
        layout.label(text='Snap = rigid; Wrap = shape-key bend')
        layout.label(text='Separate meshes; Smart Fuse to merge')


CLASSES = (MCH_PG_Conform, MCH_OT_surface_conform, MCH_OT_surface_conform_reproject,
           MCH_OT_surface_conform_clear, MCH_PT_surface_conform)
