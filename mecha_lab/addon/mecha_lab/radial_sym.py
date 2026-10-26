"""0.24.33 Point Radial Symmetry: click a point - the selected meshes repeat round it (Count copies), turning about
the active mesh's own X / Y / Z axis through that point.

It works like the Mirror: an Array modifier per mesh (object offset = a hidden helper turned one step round the
pivot), so it stays live - Count / Axis change at once.  0.24.38: the pivot and axis picked first stay put - turning or
moving a mesh turns only that mesh (its copies are re-placed round the same pivot), moving the pivot moves all.
While it is on:
* new parts you draw (Base Mesh, Creature Base, Armor / Creature Plate, Surface Draw, Cloth Brush) get the same
  symmetry,
* Cut / Split cut every copy: the cutter is repeated round the pivot (draw on any copy).
Apply makes the copies real, Remove takes the symmetry away.  ``step_matrix`` and ``rotations`` are pure.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty, PointerProperty
from bpy_extras import view3d_utils
from mathutils import Matrix, Vector

MOD_NAME = 'MCH_RadialSym'
HELPER_KEY = 'mch_rsym_helper'
AXES = [('X', 'X', 'Turn about the local X axis'), ('Y', 'Y', 'Turn about the local Y axis'),
        ('Z', 'Z', 'Turn about the local Z axis')]
CREATORS = {'BASE', 'CBASE', 'PLATE', 'CPLATE', 'SDRAW', 'FLOWER'}


# -----------------------------------------------------------------------------
# pure parts
# -----------------------------------------------------------------------------


def step_matrix(pivot, axis, count, k=1):
    """World 4x4: k steps of 360 / count round ``axis`` through ``pivot``."""
    ang = 2.0 * math.pi * k / max(1, count)
    return (Matrix.Translation(pivot) @ Matrix.Rotation(ang, 4, Vector(axis).normalized())
            @ Matrix.Translation(-Vector(pivot)))


def rotations(pivot, axis, count):
    return [step_matrix(pivot, axis, count, k) for k in range(count)]


# -----------------------------------------------------------------------------
# scene state
# -----------------------------------------------------------------------------


def _update(self, context):
    if self.active:
        refresh(context)


R0_KEY = 'mch_rsym_r0'          # a mesh's distance from the axis when Distance was 0


def radial(st, ob):
    """(radial vector from the axis to ob's origin, axis point, axis direction) in the scene."""
    p = st.pivot.matrix_world.translation
    a = axis_world(st).normalized()
    v = ob.matrix_world.translation - p
    return v - a * v.dot(a), p, a


def _distance_update(self, context):
    """0.24.38 Distance: every mesh slides straight away from (or toward) the axis - its copies with it."""
    if not self.active or self.pivot is None:
        return
    for ob in members(context):
        r, _p, _a = radial(self, ob)
        if R0_KEY not in ob:
            ob[R0_KEY] = r.length - self.distance_prev
        want = max(0.0, ob[R0_KEY] + self.distance)
        d = r.normalized() if r.length > 1e-9 else Vector((1.0, 0.0, 0.0))
        ob.matrix_world = Matrix.Translation(d * (want - r.length)) @ ob.matrix_world
        sync(self, ob)
    self.distance_prev = self.distance


class MCH_PG_RadialSym(bpy.types.PropertyGroup):
    active: BoolProperty(default=False, options={'HIDDEN'})
    pivot: PointerProperty(type=bpy.types.Object)
    count: IntProperty(name='Count', default=6, min=2, max=128, update=_update,
                       description='How many copies round the point')
    axis: EnumProperty(name='Axis', items=AXES, default='Z', update=_update,
                       description="Turn about this axis of the mesh you picked (through the point)")
    distance: bpy.props.FloatProperty(name='Distance', default=0.0, soft_min=-1.0, soft_max=1.0, unit='LENGTH',
                                      precision=4, update=_distance_update,
                                      description='Move the meshes (and so every copy) away from the axis (+) or '
                                                  'closer to it (-)')
    distance_prev: bpy.props.FloatProperty(default=0.0, options={'HIDDEN'})


def axis_world(st):
    piv = st.pivot
    k = {'X': 0, 'Y': 1, 'Z': 2}[st.axis]
    return piv.matrix_world.to_3x3().normalized().col[k].copy()


def members(context):
    return [o for o in context.scene.objects if o.type == 'MESH' and o.modifiers.get(MOD_NAME) is not None]


def _helper(ob):
    name = ob.get(HELPER_KEY)
    h = bpy.data.objects.get(name) if name else None
    if h is None:
        h = bpy.data.objects.new('MCH_RS_' + ob.name, None)
        h.empty_display_type = 'ARROWS'
        h.empty_display_size = 0.1
        for coll in ob.users_collection:
            coll.objects.link(h)
        h.parent = ob
        h.matrix_parent_inverse = Matrix.Identity(4)
        h.hide_set(True)
        h.hide_render = True
        ob[HELPER_KEY] = h.name
    return h


def helper_basis(st, ob):
    """The helper's matrix (in ob's space) that turns ob one step round the FIXED pivot / axis (scene space)."""
    mw = ob.matrix_world
    return mw.inverted_safe() @ step_matrix(st.pivot.matrix_world.translation, axis_world(st), st.count) @ mw


def sync(st, ob):
    """0.24.38 Keep ob's copies round the pivot picked first: after ob is moved / turned (or the pivot is moved),
    only ob turns - the axis stays where it was clicked.  Returns True when the helper was changed."""
    name = ob.get(HELPER_KEY)
    h = bpy.data.objects.get(name) if name else None
    if h is None or st.pivot is None:
        return False
    want = helper_basis(st, ob)
    cur = h.matrix_basis
    if all(abs(want[r][c] - cur[r][c]) < 1e-6 for r in range(4) for c in range(4)):
        return False
    h.matrix_basis = want
    return True


_SYNC_BUSY = [False]


@bpy.app.handlers.persistent
def _on_depsgraph(scene, depsgraph):
    """A member or the pivot moved / turned: re-place the copies round the fixed pivot."""
    if _SYNC_BUSY[0]:
        return
    st = getattr(scene, 'mch_rsym', None)
    if st is None or not st.active or st.pivot is None:
        return
    try:
        moved = {u.id.original.name for u in depsgraph.updates
                 if isinstance(u.id, bpy.types.Object) and u.is_updated_transform}
    except (AttributeError, ReferenceError):
        return
    if not moved:
        return
    _SYNC_BUSY[0] = True
    try:
        everything = st.pivot.name in moved
        for ob in scene.objects:
            if ob.type == 'MESH' and ob.modifiers.get(MOD_NAME) is not None and (everything or ob.name in moved):
                sync(st, ob)
                if R0_KEY in ob:                   # moved by hand: Distance counts from the new place
                    r, _p, _a = radial(st, ob)
                    r0 = r.length - st.distance
                    if abs(ob[R0_KEY] - r0) > 1e-7:
                        ob[R0_KEY] = r0
    except (AttributeError, ReferenceError, RuntimeError):
        pass
    finally:
        _SYNC_BUSY[0] = False


def adopt(context, ob):
    """Give ob the symmetry of the scene (Array modifier + its helper)."""
    st = context.scene.mch_rsym
    if not st.active or st.pivot is None or ob is None or ob.type != 'MESH' or ob == st.pivot:
        return False
    h = _helper(ob)
    h.matrix_basis = helper_basis(st, ob)
    mod = ob.modifiers.get(MOD_NAME) or ob.modifiers.new(MOD_NAME, 'ARRAY')
    mod.fit_type = 'FIXED_COUNT'
    mod.count = st.count
    mod.use_relative_offset = False
    mod.use_constant_offset = False
    mod.use_object_offset = True
    mod.offset_object = h
    mod.use_merge_vertices = False
    return True


def refresh(context):
    for ob in members(context):
        adopt(context, ob)


def setup(context, point, ref=None):
    """Start the symmetry at ``point`` (axes from ``ref``, else the world) on the selected meshes."""
    st = context.scene.mch_rsym
    piv = st.pivot
    if piv is None:
        piv = bpy.data.objects.new('MCH_RadialPivot', None)
        piv.empty_display_type = 'SPHERE'
        piv.empty_display_size = 0.15
        (context.collection or context.scene.collection).objects.link(piv)
        st.pivot = piv
    rot = ref.matrix_world.to_quaternion() if ref is not None else Matrix.Identity(3).to_quaternion()
    piv.matrix_world = Matrix.Translation(point) @ rot.to_matrix().to_4x4()
    for ob in members(context):            # a new centre: Distance starts from where the meshes are now
        if R0_KEY in ob:
            del ob[R0_KEY]
    st.active = False
    st.distance_prev = 0.0
    st.distance = 0.0
    st.active = True
    done = 0
    for ob in [o for o in context.selected_objects if o.type == 'MESH' and o != piv]:
        done += adopt(context, ob)
    return done


def remove(context, apply_mods=False):
    st = context.scene.mch_rsym
    for ob in members(context):
        mod = ob.modifiers.get(MOD_NAME)
        if apply_mods:
            with context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
                bpy.ops.object.modifier_apply(modifier=mod.name)
        else:
            ob.modifiers.remove(mod)
        h = bpy.data.objects.get(ob.get(HELPER_KEY, ''))
        if h is not None:
            bpy.data.objects.remove(h, do_unlink=True)
        if HELPER_KEY in ob:
            del ob[HELPER_KEY]
        if R0_KEY in ob:
            del ob[R0_KEY]
    if st.pivot is not None:
        bpy.data.objects.remove(st.pivot, do_unlink=True)
    st.pivot = None
    st.active = False


def after_create(context, mode):
    """Called after a drawing tool made something: the new part gets the symmetry too."""
    st = getattr(context.scene, 'mch_rsym', None)
    if st is None or not st.active or mode not in CREATORS:
        return ''
    ob = context.active_object
    if ob is not None and ob.type == 'MESH' and ob.modifiers.get(MOD_NAME) is None and adopt(context, ob):
        return f' | Radial Symmetry x{st.count}'
    return ''


def replicate_cutter(context, targets, cutter):
    """Cut on a radially symmetric mesh: the cutter repeated round the pivot, so every copy is cut (whichever copy
    the shape was drawn on)."""
    st = getattr(context.scene, 'mch_rsym', None)
    if cutter is None or st is None or not st.active or st.pivot is None:
        return cutter
    if not any(t.modifiers.get(MOD_NAME) is not None for t in targets):
        return cutter
    mw = cutter.matrix_world
    bm = bmesh.new()
    try:
        src = bmesh.new()
        src.from_mesh(cutter.data)
        src.transform(mw)
        for r in rotations(st.pivot.matrix_world.translation, axis_world(st), st.count):
            part = src.copy()
            part.transform(r)
            tmp = bpy.data.meshes.new('_rsym_tmp')
            part.to_mesh(tmp)
            part.free()
            bm.from_mesh(tmp)
            bpy.data.meshes.remove(tmp)
        src.free()
        bm.transform(mw.inverted_safe())
        bm.to_mesh(cutter.data)
    finally:
        bm.free()
    cutter.data.update()
    return cutter


# -----------------------------------------------------------------------------
# operators / panel
# -----------------------------------------------------------------------------


class MCH_OT_radial_sym(bpy.types.Operator):
    """Click a point: the selected meshes repeat round it (Radial Symmetry); Esc / right click = cancel"""
    bl_idname = 'mch.radial_sym'
    bl_label = 'Point Radial Symmetry'
    bl_options = {'REGISTER', 'UNDO'}
    point: bpy.props.FloatVectorProperty(size=3, options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        n = setup(context, Vector(self.point), context.active_object if context.active_object
                  and context.active_object.type == 'MESH' else None)
        self.report({'INFO'}, f'Radial Symmetry x{context.scene.mch_rsym.count} on {n} mesh(es) - '
                              'new Base Mesh / plates get it too, Cut cuts every copy')
        return {'FINISHED'}

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            return self.execute(context)
        context.window_manager.modal_handler_add(self)
        context.area.header_text_set('Radial Symmetry: click the centre point (on a surface or at the 3D cursor '
                                     'depth)   Esc / right click: cancel')
        context.window.cursor_modal_set('CROSSHAIR')
        return {'RUNNING_MODAL'}

    def _end(self, context):
        context.area.header_text_set(None)
        context.window.cursor_modal_restore()

    def modal(self, context, event):
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'} or event.type.startswith('NDOF'):
            return {'PASS_THROUGH'}
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            region, rv3d = context.region, context.region_data
            mouse = (event.mouse_region_x, event.mouse_region_y)
            o = view3d_utils.region_2d_to_origin_3d(region, rv3d, mouse)
            d = view3d_utils.region_2d_to_vector_3d(region, rv3d, mouse)
            hit, loc, _n, _i, _ob, _m = context.scene.ray_cast(context.evaluated_depsgraph_get(), o, d)
            if not hit:
                loc = view3d_utils.region_2d_to_location_3d(region, rv3d, mouse, context.scene.cursor.location)
            self.point = loc
            self._end(context)
            return self.execute(context)
        if event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self._end(context)
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}


class MCH_OT_radial_sym_add(bpy.types.Operator):
    bl_idname = 'mch.radial_sym_add'
    bl_label = 'Add Selected'
    bl_description = 'Give the selected meshes the radial symmetry too'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.mch_rsym.active

    def execute(self, context):
        for ob in context.selected_objects:
            adopt(context, ob)
        return {'FINISHED'}


class MCH_OT_radial_sym_update(bpy.types.Operator):
    bl_idname = 'mch.radial_sym_update'
    bl_label = 'Update'
    bl_description = 'After moving / turning the pivot or the meshes: the copies follow'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.mch_rsym.active

    def execute(self, context):
        refresh(context)
        return {'FINISHED'}


class MCH_OT_radial_sym_end(bpy.types.Operator):
    bl_idname = 'mch.radial_sym_end'
    bl_label = 'End Radial Symmetry'
    bl_options = {'REGISTER', 'UNDO'}
    apply: BoolProperty(default=False)

    @classmethod
    def poll(cls, context):
        return context.scene.mch_rsym.active

    def execute(self, context):
        remove(context, self.apply)
        return {'FINISHED'}


def draw(layout, context):
    st = context.scene.mch_rsym
    row = layout.row()
    row.scale_y = 1.4
    row.operator('mch.radial_sym', text='Pick Centre Point' if not st.active else 'Pick a New Centre',
                 icon='PIVOT_CURSOR')
    if not st.active:
        layout.label(text='Select meshes, then click the centre', icon='INFO')
        layout.prop(st, 'count')
        return
    box = layout.box()
    box.label(text=f'Radial Symmetry x{st.count}: {len(members(context))} mesh(es)', icon='MOD_ARRAY')
    box.prop(st, 'count')
    box.row(align=True).prop(st, 'axis', expand=True)
    box.prop(st, 'distance')                       # 0.24.38 how far from the axis
    row = box.row(align=True)
    row.operator('mch.radial_sym_add', icon='ADD')
    row.operator('mch.radial_sym_update', icon='FILE_REFRESH')
    row = box.row(align=True)
    row.operator('mch.radial_sym_end', text='Apply', icon='CHECKMARK').apply = True
    row.operator('mch.radial_sym_end', text='Remove', icon='X').apply = False
    col = layout.column(align=True)
    col.scale_y = 0.8
    for line in ('Draw a Base Mesh / plate: it repeats too', 'Cut on any copy: every copy is cut'):
        col.label(text=line)


CLASSES = (MCH_PG_RadialSym, MCH_OT_radial_sym, MCH_OT_radial_sym_add, MCH_OT_radial_sym_update,
           MCH_OT_radial_sym_end)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_rsym = PointerProperty(type=MCH_PG_RadialSym)
    if _on_depsgraph not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph)


def unregister():
    while _on_depsgraph in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph)
    try:
        del bpy.types.Scene.mch_rsym
    except AttributeError:
        pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
