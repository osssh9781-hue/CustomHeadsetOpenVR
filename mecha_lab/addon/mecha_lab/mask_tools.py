"""Mecha Lab mask (v0.5.9 prototype, now driven by the shared shape tools): drawn *face* masks and raised extraction.

A face-mask is topological (whole polygon faces), not an exact projected stencil.
Masking only visible polygons is intentional; protection from booleans is NOT
provided by this implementation. None of these operations alters the source
geometry, apart from adding a face-domain integer attribute on its mesh data.
"""
import bpy
import bmesh
from . import core_geometry as cg

MASK_ATTR = 'mch_mask'


def mask_attr(mesh):
    attr = mesh.attributes.get(MASK_ATTR)
    if attr is None:
        attr = mesh.attributes.new(name=MASK_ATTR, type='INT', domain='FACE')
    if attr.domain != 'FACE' or attr.data_type != 'INT':
        raise ValueError('Existing mch_mask attribute must be FACE/INT')
    return attr


def mask_indices(obj):
    attr = obj.data.attributes.get(MASK_ATTR)
    if not attr:
        return set()
    return {i for i, a in enumerate(attr.data) if a.value > 0}


def selected_face_mesh(source, indexes, name):
    """Return a separate patch mesh, preserving the source local coordinates."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    try:
        bm.from_mesh(source.data)
        bm.faces.ensure_lookup_table()
        bm.faces.index_update()
        remove = [f for f in bm.faces if f.index not in indexes]
        if remove:
            bmesh.ops.delete(bm, geom=remove, context='FACES')
        bm.verts.ensure_lookup_table()
        loose = [v for v in bm.verts if not v.link_faces]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context='VERTS')
        if not bm.faces:
            raise ValueError('Mask contains no faces')
        bm.to_mesh(mesh)
        mesh.update()
        for material in source.data.materials:
            mesh.materials.append(material)
        return mesh
    except Exception:
        bpy.data.meshes.remove(mesh)
        raise
    finally:
        bm.free()


def clear_preview(source):
    name = source.get('mch_mask_preview')
    if name:
        ob = bpy.data.objects.get(name)
        if ob and ob.get('mch_preview_source') == source.name:
            bpy.data.objects.remove(ob, do_unlink=True)
        if 'mch_mask_preview' in source:
            del source['mch_mask_preview']


def refresh_preview(context, source):
    clear_preview(source)
    indexes = mask_indices(source)
    if not indexes:
        return
    mesh = selected_face_mesh(source, indexes, source.name + '_MaskGuideMesh')
    preview = bpy.data.objects.new(source.name + '_MASK_GUIDE', mesh)
    context.collection.objects.link(preview)
    preview.matrix_world = source.matrix_world.copy()
    preview.display_type = 'WIRE'
    preview.show_in_front = True
    preview.hide_render = True
    preview['mch_preview_source'] = source.name
    source['mch_mask_preview'] = preview.name
    preview.hide_select = True


def _ray_mask_face(obj, projector, xy):
    """Get the first visible *source* mesh polygon under a screen pixel."""
    origin, direction = projector.ray(xy)
    inv = obj.matrix_world.inverted_safe()
    hit, _loc, _normal, face_idx = obj.ray_cast(
        inv @ origin, (inv.to_3x3() @ direction).normalized())
    return face_idx if hit else None


def _write_mask(context, obj, hit_faces, erase=False):
    """Write an object-local face mask; return (changed, total)."""
    if not hit_faces:
        return 0, len(mask_indices(obj))
    if obj.data.users > 1:
        obj.data = obj.data.copy()
    attr = mask_attr(obj.data)
    change_to = 0 if erase else 1
    changed = 0
    for i in hit_faces:
        if 0 <= i < len(attr.data) and attr.data[i].value != change_to:
            attr.data[i].value = change_to
            changed += 1
    if changed:
        obj.data.update()
        refresh_preview(context, obj)
    return changed, len(mask_indices(obj))


def apply_mask_loops(context, obj, loops, projector, erase=False):
    """Paint intersected visible faces, not just polygon CENTERS.

    Important: this is still a face-domain mask. A tiny shape painted onto a
    single giant quad selects the whole quad. No false claim of a precise mask.
    """
    if not loops:
        return 0, len(mask_indices(obj))
    x0 = min(p[0] for lp in loops for p in lp)
    y0 = min(p[1] for lp in loops for p in lp)
    x1 = max(p[0] for lp in loops for p in lp)
    y1 = max(p[1] for lp in loops for p in lp)
    selected = set()
    # Preserve exact selection of dense mesh polygons whose centers lie inside.
    world = obj.matrix_world
    for face in obj.data.polygons:
        xy = projector.to_screen(world @ face.center)
        if xy is None or not (x0 <= xy[0] <= x1 and y0 <= xy[1] <= y1):
            continue
        if cg.point_in_loops(xy, loops) and _ray_mask_face(obj, projector, xy) == face.index:
            selected.add(face.index)
    # Cover large polygons whose CENTERS are outside a small drawn outline.
    # Cap probes to ~30 x 30 to keep a single stroke responsive.
    width = max(x1 - x0, 1.0)
    height = max(y1 - y0, 1.0)
    nx = max(1, min(30, int(width / 14) + 1))
    ny = max(1, min(30, int(height / 14) + 1))
    for i in range(nx):
        for j in range(ny):
            xy = (x0 + (i + 0.5) * width / nx, y0 + (j + 0.5) * height / ny)
            if cg.point_in_loops(xy, loops):
                face = _ray_mask_face(obj, projector, xy)
                if face is not None:
                    selected.add(face)
    return _write_mask(context, obj, selected, erase)


def apply_mask_stroke(context, obj, points, projector, radius=18.0, erase=False):
    """Circular paint-brush samples along an OPEN path (not a closed lasso)."""
    import math
    if not points:
        return 0, len(mask_indices(obj))
    radius = max(1.0, float(radius))
    offsets = [(0.0, 0.0)]
    # Two rings to cover the interior of the circular brush dab.
    for frac, count in ((0.45, 8), (0.85, 12)):
        for j in range(count):
            angle = 2 * math.pi * j / count
            offsets.append((radius * frac * math.cos(angle),
                            radius * frac * math.sin(angle)))
    selected = set()
    for a, b in zip(points, points[1:]):
        count = max(1, int(math.ceil(math.dist(a, b) / max(3.0, radius * 0.35))))
        for n in range(count + 1):
            u = n / count
            x, y = (a[0] * (1 - u) + b[0] * u,
                    a[1] * (1 - u) + b[1] * u)
            for dx, dy in offsets:
                hit = _ray_mask_face(obj, projector, (x + dx, y + dy))
                if hit is not None:
                    selected.add(hit)
    if len(points) == 1:
        for dx, dy in offsets:
            hit = _ray_mask_face(obj, projector, (points[0][0] + dx, points[0][1] + dy))
            if hit is not None:
                selected.add(hit)
    return _write_mask(context, obj, selected, erase)


class MCH_OT_draw_mask(bpy.types.Operator):
    """v0.5.9 compatibility: drawing a mask is now the native Mask tool."""
    bl_idname = 'mch.draw_mask'
    bl_label = 'Mask Tool'
    bl_description = 'Activate the Mecha Mask tool (shared shapes; Alt erases)'
    bl_options = {'INTERNAL'}

    def execute(self, context):
        # v1.0: Mask is hidden (did not work reliably); data and code are kept.
        self.report({'WARNING'}, 'Mask is hidden in Mecha Lab 1.0 (saved mask data is kept)')
        return {'CANCELLED'}


class MCH_OT_mask_from_selection(bpy.types.Operator):
    bl_idname = 'mch.mask_selected_faces'
    bl_label = 'Save Selected Faces as Mask'
    bl_description = 'Capture face selection from Edit Mode into persistent mask for extraction'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        source = context.active_object
        bm = bmesh.from_edit_mesh(source.data)
        bm.faces.ensure_lookup_table()
        bm.faces.index_update()
        indices = {f.index for f in bm.faces if f.select}
        bpy.ops.object.mode_set(mode='OBJECT')
        if not indices:
            self.report({'WARNING'}, 'No selected faces')
            return {'CANCELLED'}
        if source.data.users > 1:
            source.data = source.data.copy()
        a = mask_attr(source.data)
        for i in indices: a.data[i].value = 1
        source.data.update()
        refresh_preview(context, source)
        self.report({'INFO'}, f'Added {len(indices)} masked faces')
        return {'FINISHED'}


class MCH_OT_mask_clear(bpy.types.Operator):
    bl_idname = 'mch.mask_clear'
    bl_label = 'Clear Face Mask'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        o = context.active_object
        if o.data.users > 1: o.data = o.data.copy()
        a = o.data.attributes.get(MASK_ATTR)
        if a:
            o.data.attributes.remove(a)
            o.data.update()
        clear_preview(o)
        return {'FINISHED'}


class MCH_OT_mask_extract(bpy.types.Operator):
    bl_idname = 'mch.mask_extract'
    bl_label = 'Extract / Raise Mask'
    bl_description = 'Extract masked faces as a separate object and raise them outward using editable Solidify thickness'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        src = context.active_object
        indexes = mask_indices(src)
        if not indexes:
            self.report({'WARNING'}, 'No masked faces on active mesh; first Draw Mask or Save Selected Faces')
            return {'CANCELLED'}
        try:
            mesh = selected_face_mesh(src, indexes, src.name + '_ExtractedMesh')
            obj = bpy.data.objects.new(src.name + '_RaisedMask', mesh)
            context.collection.objects.link(obj)
            obj.matrix_world = src.matrix_world.copy()
            mod = obj.modifiers.new('MCH_MaskExtrude', 'SOLIDIFY')
            mod.thickness = context.scene.mch_settings.mch_mask_thickness
            mod.offset = 1.0
            mod.use_even_offset = True
            mod.use_rim = True
            obj['mch_mask_source'] = src.name
            obj['mch_mask_extract'] = True
            for old in context.selected_objects:
                old.select_set(False)
            obj.select_set(True)
            context.view_layer.objects.active = obj
            self.report({'INFO'}, f'Raised {len(indexes)} faces; editable thickness in Solidify')
            return {'FINISHED'}
        except Exception as ex:
            self.report({'ERROR'}, 'Extract failed: ' + str(ex))
            return {'CANCELLED'}


CLASSES = (MCH_OT_draw_mask, MCH_OT_mask_from_selection, MCH_OT_mask_clear, MCH_OT_mask_extract)
