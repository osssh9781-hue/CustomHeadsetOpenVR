"""0.22.0 Detail Stamp: your own detail meshes, stuck onto a surface with the mouse.

Presets
    Select a mesh whose ORIGIN sits on its bottom (the side that touches the
    surface, local +Z pointing away from it) and press "Add Selected as Preset".
    Each preset is saved as its own small .blend in Blender's config folder
    (config/mecha_lab/details/<name>.blend), so it is there in every file.
    Delete removes that file.  Nothing else in your Blender settings changes.

Stamping (N panel > Mecha Lab > Detail Stamp > Start, or the operator)
    The preset follows the mouse, stuck to the surface under it and turned to
    its normal, sunk a little into the mesh (Sink, share of the detail height).
    Left click   place it right there (no Apply needed) and keep going
    Ctrl+Wheel   turn around the normal      Shift+Wheel  size
    Alt+Wheel    sink deeper / shallower     Right click / Esc  stop
    Mouse wheel and middle mouse still move the view.

``place_matrix`` / ``stamp`` are pure enough to test headless.
"""
from __future__ import annotations

import math
import os
import re

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, StringProperty
from mathutils import Matrix, Vector

FOLDER = 'details'
PREVIEW_NAME = 'MCH_DetailPreview'
COLL = 'Mecha Details'
_ITEMS = []              # keeps enum item strings alive (Blender requirement)


# -----------------------------------------------------------------------------
# Preset library (one .blend per preset)
# -----------------------------------------------------------------------------


def folder(create=True):
    try:
        d = bpy.utils.user_resource('CONFIG', path=os.path.join('mecha_lab', FOLDER), create=create)
    except (TypeError, ValueError, RuntimeError, OSError):
        return None
    return d or None


def safe_name(name):
    name = re.sub(r'[^\w\- ]+', '_', (name or '').strip())[:48].strip()
    return name or 'Detail'


def preset_names():
    d = folder(create=False)
    if not d or not os.path.isdir(d):
        return []
    return sorted(f[:-6] for f in os.listdir(d) if f.endswith('.blend'))


def preset_path(name):
    d = folder()
    return os.path.join(d, safe_name(name) + '.blend') if d else None


def add_preset(context, ob, name=None):
    """Save ``ob`` (modifiers and scale / rotation baked, origin kept) as a preset. Returns the name."""
    if ob is None or ob.type != 'MESH':
        raise ValueError('Select a mesh object for the preset')
    name = safe_name(name or ob.name)
    path = preset_path(name)
    if path is None:
        raise ValueError('No config folder for presets')
    dg = context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    rs = ob.matrix_world.to_3x3().to_4x4()                 # rotation + scale, origin stays the attach point
    me.transform(rs)
    me.name = 'MCH_DETAIL_' + name
    try:
        bpy.data.libraries.write(path, {me}, fake_user=True)
    finally:
        bpy.data.meshes.remove(me)
    return name


def delete_preset(name):
    path = preset_path(name)
    if path and os.path.exists(path):
        os.remove(path)
        return True
    return False


def load_mesh(name):
    """The preset mesh (appended once per file, reused afterwards)."""
    key = 'MCH_DETAIL_' + safe_name(name)
    me = bpy.data.meshes.get(key)
    if me is not None:
        return me
    path = preset_path(name)
    if not path or not os.path.exists(path):
        return None
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.meshes = [m for m in src.meshes if m == key] or list(src.meshes[:1])
    me = dst.meshes[0] if dst.meshes else None
    if me is not None:
        me.name = key
        me.use_fake_user = False
    return me


def _preset_items(self, context):
    _ITEMS.clear()
    for n in preset_names():
        _ITEMS.append((n, n, f'Detail preset {n}'))
    if not _ITEMS:
        _ITEMS.append(('NONE', '(no presets yet)', 'Select a mesh and press Add Selected as Preset'))
    return _ITEMS


# -----------------------------------------------------------------------------
# Placement
# -----------------------------------------------------------------------------


def mesh_height(me):
    zs = [v.co.z for v in me.vertices]
    return max(zs) - min(min(zs), 0.0) if zs else 0.0


def place_matrix(hit, normal, view_up, angle=0.0, scale=1.0, sink=0.0, height=0.0):
    """World matrix: local +Z along ``normal`` at ``hit``, turned by ``angle`` around it,
    sunk ``sink`` x height into the surface."""
    z = Vector(normal).normalized()
    up = Vector(view_up)
    x = up.cross(z)
    if x.length < 1e-6:
        x = Vector((1, 0, 0)).cross(z) if abs(z.x) < 0.9 else Vector((0, 1, 0)).cross(z)
    x.normalize()
    y = z.cross(x)
    rot = Matrix((x, y, z)).transposed() @ Matrix.Rotation(angle, 3, 'Z')
    loc = Vector(hit) - z * (sink * height * scale)
    return Matrix.Translation(loc) @ rot.to_4x4() @ Matrix.Diagonal((scale, scale, scale, 1.0))


def stamp(context, me, matrix, join_to=None):
    """Place one detail (a copy of the preset mesh) with ``matrix``; returns the object
    (or the target when joined)."""
    coll = bpy.data.collections.get(COLL)
    if coll is None:
        coll = bpy.data.collections.new(COLL)
        context.scene.collection.children.link(coll)
    name = me.name.replace('MCH_DETAIL_', '') or 'Detail'
    ob = bpy.data.objects.new(name, me.copy())
    coll.objects.link(ob)
    ob.matrix_world = matrix
    if join_to is not None and join_to.type == 'MESH':
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(join_to.data)
        tmp = ob.data.copy()
        tmp.transform(join_to.matrix_world.inverted() @ ob.matrix_world)
        bm.from_mesh(tmp)
        bm.to_mesh(join_to.data)
        bm.free()
        bpy.data.meshes.remove(tmp)
        old = ob.data
        bpy.data.objects.remove(ob)
        if old.users == 0:
            bpy.data.meshes.remove(old)
        join_to.data.update()
        return join_to
    return ob


def surface_hit(context, origin, direction, skip=()):
    """First surface hit along the ray, skipping the preview / given objects."""
    dg = context.evaluated_depsgraph_get()
    o = Vector(origin)
    d = Vector(direction).normalized()
    for _ in range(12):
        ok, loc, nrm, _i, ob, _m = context.scene.ray_cast(dg, o, d)
        if not ok:
            return None
        if ob is not None and (ob.name in skip or ob.name.startswith(PREVIEW_NAME)):
            o = loc + d * 1e-4
            continue
        if nrm.dot(d) > 0:
            nrm = -nrm
        return loc, nrm, ob
    return None


# -----------------------------------------------------------------------------
# Settings / operators
# -----------------------------------------------------------------------------


class MCH_PG_DetailStamp(bpy.types.PropertyGroup):
    preset: EnumProperty(name='Preset', items=_preset_items)
    new_name: StringProperty(name='Name', default='', description='Preset name (empty = object name)')
    sink: FloatProperty(name='Sink', default=0.08, min=-1.0, max=1.0, subtype='FACTOR',
                        description='How far the detail goes into the surface (share of its height)')
    scale: FloatProperty(name='Size', default=1.0, min=0.01, soft_max=10.0)
    angle: FloatProperty(name='Turn', default=0.0, subtype='ANGLE')
    join: BoolProperty(name='Join to Surface', default=False,
                       description='Add each detail into the mesh it was placed on (off = separate objects)')


class MCH_OT_detail_preset_add(bpy.types.Operator):
    """Save the selected mesh as a Detail Stamp preset (origin = the bottom that touches the surface)"""
    bl_idname = 'mch.detail_preset_add'
    bl_label = 'Add Selected as Preset'
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.type == 'MESH'

    def execute(self, context):
        st = context.scene.mch_detail
        try:
            name = add_preset(context, context.active_object, st.new_name or None)
        except (ValueError, OSError, RuntimeError) as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        st.new_name = ''
        try:
            st.preset = name
        except TypeError:
            pass
        self.report({'INFO'}, f'Detail preset "{name}" saved')
        return {'FINISHED'}


class MCH_OT_detail_preset_delete(bpy.types.Operator):
    """Delete the chosen Detail Stamp preset file"""
    bl_idname = 'mch.detail_preset_delete'
    bl_label = 'Delete Preset'
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        name = context.scene.mch_detail.preset
        if name and name != 'NONE' and delete_preset(name):
            self.report({'INFO'}, f'Deleted preset "{name}"')
            return {'FINISHED'}
        return {'CANCELLED'}


def make_projector(region, rv3d):
    from . import core_geometry as cg
    return cg.Projector(region, rv3d)


class StampLogic:
    """Modal stamping (plain class so it can be driven headless; the operator below uses it)."""

    def _preview(self, context):
        ob = bpy.data.objects.get(self.preview_name)
        if ob is None:
            ob = bpy.data.objects.new(PREVIEW_NAME, self.mesh)
            context.scene.collection.objects.link(ob)
            ob.display_type = 'SOLID'
            ob.show_wire = True
            ob.hide_select = True
            self.preview_name = ob.name
        return ob

    def _update(self, context, xy):
        st = context.scene.mch_detail
        proj = make_projector(context.region, context.region_data)
        origin, direction = proj.ray(xy)
        hit = surface_hit(context, origin, direction, skip={self.preview_name})
        ob = self._preview(context)
        if hit is None:
            ob.hide_viewport = True
            self.hit = None
            return
        loc, nrm, target = hit
        o2, d2 = proj.ray((xy[0], xy[1] + 10.0))
        up = (Vector(o2) + Vector(d2)) - (Vector(origin) + Vector(direction))
        if up.length < 1e-9:
            up = Vector((0, 0, 1))
        ob.hide_viewport = False
        ob.matrix_world = place_matrix(loc, nrm, up, st.angle, st.scale, st.sink, self.height)
        self.hit = (loc, nrm, target.name if target else '')

    def _place(self, context):
        if self.hit is None:
            return None
        st = context.scene.mch_detail
        ob = bpy.data.objects.get(self.preview_name)
        target = bpy.data.objects.get(self.hit[2]) if st.join else None
        placed = stamp(context, self.mesh, ob.matrix_world.copy(), join_to=target)
        self.count += 1
        return placed

    def _finish(self, context):
        ob = bpy.data.objects.get(self.preview_name)
        if ob is not None:
            bpy.data.objects.remove(ob)
        if context.area:
            context.area.header_text_set(None)
        try:
            context.window.cursor_modal_restore()
        except (AttributeError, RuntimeError):
            pass

    def _header(self, context):
        st = context.scene.mch_detail
        if context.area:
            context.area.header_text_set(
                f'Detail Stamp: {self.preset}  |  Click: place ({self.count})  |  Ctrl+Wheel: turn '
                f'{math.degrees(st.angle):.0f}  |  Shift+Wheel: size {st.scale:.2f}  |  Alt+Wheel: sink '
                f'{st.sink * 100:.0f} %  |  Right click / Esc: done')

    def invoke(self, context, event):
        st = context.scene.mch_detail
        self.preset = self.preset or st.preset
        self.mesh = load_mesh(self.preset) if self.preset and self.preset != 'NONE' else None
        if self.mesh is None:
            self.report({'WARNING'}, 'No detail preset: select a mesh and press Add Selected as Preset')
            return {'CANCELLED'}
        if context.area is None or context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, 'Use Detail Stamp in the 3D View')
            return {'CANCELLED'}
        self.height = mesh_height(self.mesh)
        self.preview_name = ''
        self.hit = None
        self.count = 0
        self._update(context, (event.mouse_region_x, event.mouse_region_y))
        context.window_manager.modal_handler_add(self)
        try:
            context.window.cursor_modal_set('CROSSHAIR')
        except (AttributeError, RuntimeError):
            pass
        self._header(context)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        st = context.scene.mch_detail
        xy = (event.mouse_region_x, event.mouse_region_y)
        if event.type in {'MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM', 'NDOF_MOTION'}:
            return {'PASS_THROUGH'}
        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            step = 1 if event.type == 'WHEELUPMOUSE' else -1
            if event.ctrl:
                st.angle += math.radians(15) * step
            elif event.shift:
                st.scale = max(0.01, st.scale * (1.1 if step > 0 else 1 / 1.1))
            elif event.alt:
                st.sink = min(1.0, max(-1.0, st.sink + 0.02 * step))
            else:
                return {'PASS_THROUGH'}
            self._update(context, xy)
            self._header(context)
            return {'RUNNING_MODAL'}
        if event.type == 'MOUSEMOVE':
            self._update(context, xy)
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self._update(context, xy)
            if self._place(context) is not None:
                self._header(context)
            return {'RUNNING_MODAL'}
        if event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self._finish(context)
            self.report({'INFO'}, f'Detail Stamp: {self.count} placed')
            return {'FINISHED'} if self.count else {'CANCELLED'}
        return {'RUNNING_MODAL'}


class MCH_OT_detail_stamp(StampLogic, bpy.types.Operator):
    """Stick the preset detail to the surface under the mouse; click places it (keeps going)"""
    bl_idname = 'mch.detail_stamp'
    bl_label = 'Detail Stamp'
    bl_options = {'REGISTER', 'UNDO'}

    preset: StringProperty(default='', options={'SKIP_SAVE'})


def draw(layout, context):
    st = context.scene.mch_detail
    box = layout.box()
    box.label(text='DETAIL STAMP', icon='STICKY_UVS_LOC')
    box.prop(st, 'preset', text='')
    r = box.row()
    r.scale_y = 1.4
    r.operator('mch.detail_stamp', text='Start Stamping', icon='BRUSH_DATA')
    c = box.column(align=True)
    c.prop(st, 'sink', slider=True)
    c.prop(st, 'scale')
    c.prop(st, 'angle')
    c.prop(st, 'join')
    sub = box.box()
    sub.label(text='Presets (origin = bottom of the detail)')
    rr = sub.row(align=True)
    rr.prop(st, 'new_name', text='')
    rr.operator('mch.detail_preset_add', text='Add Selected', icon='ADD')
    sub.operator('mch.detail_preset_delete', text='Delete Preset', icon='TRASH')


class MCH_PT_detail_stamp(bpy.types.Panel):
    bl_idname = 'MCH_PT_detail_stamp'
    bl_label = 'Detail Stamp'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Mecha Lab'
    bl_order = 75

    @classmethod
    def poll(cls, context):
        from . import tool_state as ts
        return hasattr(context.scene, 'mch_detail') and ts.sidebar_select(context)

    def draw(self, context):
        draw(self.layout, context)


CLASSES = (MCH_PG_DetailStamp, MCH_OT_detail_preset_add, MCH_OT_detail_preset_delete, MCH_OT_detail_stamp,
           MCH_PT_detail_stamp)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_detail = bpy.props.PointerProperty(type=MCH_PG_DetailStamp)


def unregister():
    if hasattr(bpy.types.Scene, 'mch_detail'):
        del bpy.types.Scene.mch_detail
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
