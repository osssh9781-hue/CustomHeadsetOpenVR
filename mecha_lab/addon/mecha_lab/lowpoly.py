"""0.23.22 Low Poly from a sculpt (ZBrush / dense meshes) as a rough robot base mesh.

Make Low Poly: a copy of the selected mesh is voxel remeshed (closes holes, even density), reduced to about
``Faces`` faces and flat areas are merged into big faces (baked - so dragging the bevel stays fast).  The
original is kept, hidden.  Live on the copy: a Bevel on the edges sharper than ``Angle`` (Segments 1 =
chamfer, more = round, Profile) and Weighted Normals.  Re-make with other settings, or Apply.
"""
from __future__ import annotations

import math

import bpy
from bpy.props import FloatProperty, IntProperty

SRC_KEY = 'mch_lowpoly_source'
BEVEL = 'MCH_LP_Bevel'
NORMALS = 'MCH_LP_Normals'


class MCH_PG_LowPoly(bpy.types.PropertyGroup):
    detail: IntProperty(name='Detail', default=64, min=8, max=400,
                        description='Voxels across the longest side for the clean-up remesh (higher = more shape)')
    faces: IntProperty(name='Faces', default=3000, min=50, max=200000,
                       description='About this many faces before flat areas are merged')
    flat_angle: FloatProperty(name='Flat Merge', default=math.radians(4.0), min=0.0, max=math.radians(30.0),
                              subtype='ANGLE', description='Neighbouring faces closer than this become one big face')
    bevel_width: FloatProperty(name='Bevel Width', default=0.01, min=0.0, soft_max=0.2, precision=4,
                               description='Bevel width as a part of the mesh size')
    bevel_segments: IntProperty(name='Segments', default=1, min=1, max=12, description='1 = chamfer, more = round')
    bevel_angle: FloatProperty(name='Angle', default=math.radians(30.0), min=math.radians(1.0),
                               max=math.radians(180.0), subtype='ANGLE',
                               description='Only edges sharper than this get the bevel')


def is_lowpoly(ob):
    return ob is not None and ob.type == 'MESH' and SRC_KEY in ob


def _size(ob):
    d = ob.dimensions
    return max(max(d), 1e-6)


def _evaluated_copy(context, ob, mods):
    """Bake ``mods`` [(type, {attr: value})] on a temporary copy of ``ob``; returns the new mesh."""
    tmp = ob.copy()
    tmp.data = ob.data.copy()
    tmp.modifiers.clear()
    context.scene.collection.objects.link(tmp)
    try:
        for i, (kind, attrs) in enumerate(mods):
            m = tmp.modifiers.new(f'lp{i}', kind)
            for k, v in attrs.items():
                setattr(m, k, v)
        dg = context.evaluated_depsgraph_get()
        dg.update()
        me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg), preserve_all_data_layers=False, depsgraph=dg)
    finally:
        data = tmp.data
        bpy.data.objects.remove(tmp, do_unlink=True)
        if data.users == 0:
            bpy.data.meshes.remove(data)
    return me


def build_mesh(context, src, detail, faces, flat_angle):
    """The low poly mesh (object space of ``src``)."""
    voxel = _size(src) / max(8, detail)
    remeshed = _evaluated_copy(context, src, [('REMESH', {'mode': 'VOXEL', 'voxel_size': voxel})])
    tmp = bpy.data.objects.new('MCH_LP_tmp', remeshed)
    tmp.matrix_world = src.matrix_world.copy()
    context.scene.collection.objects.link(tmp)
    try:
        n = max(len(remeshed.polygons), 1)
        steps = [('DECIMATE', {'decimate_type': 'COLLAPSE', 'ratio': min(1.0, faces / n)})]
        if flat_angle > 0:
            steps.append(('DECIMATE', {'decimate_type': 'DISSOLVE', 'angle_limit': flat_angle}))
        me = _evaluated_copy(context, tmp, steps)
    finally:
        bpy.data.objects.remove(tmp, do_unlink=True)
        if remeshed.users == 0:
            bpy.data.meshes.remove(remeshed)
    return me


def _live_modifiers(ob, st):
    bev = ob.modifiers.get(BEVEL) or ob.modifiers.new(BEVEL, 'BEVEL')
    bev.limit_method = 'ANGLE'
    bev.angle_limit = st.bevel_angle
    bev.width = st.bevel_width * _size(ob) / max(max(ob.scale), 1e-9)
    bev.segments = st.bevel_segments
    bev.profile = 0.5
    bev.use_clamp_overlap = True
    bev.harden_normals = True
    wn = ob.modifiers.get(NORMALS) or ob.modifiers.new(NORMALS, 'WEIGHTED_NORMAL')
    wn.keep_sharp = True
    return bev, wn


def make(context, src, st):
    if src is None or src.type != 'MESH':
        raise RuntimeError('Select a mesh (your sculpt) first.')
    me = build_mesh(context, src, st.detail, st.faces, st.flat_angle)
    me.name = src.name + '_Low'
    ob = bpy.data.objects.new(src.name + '_Low', me)
    for coll in src.users_collection:
        coll.objects.link(ob)
    ob.matrix_world = src.matrix_world.copy()
    ob[SRC_KEY] = src.name
    for p in me.polygons:
        p.use_smooth = True
    _live_modifiers(ob, st)
    src.hide_set(True)
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    return ob


def remake(context, ob, st):
    src = bpy.data.objects.get(ob.get(SRC_KEY, ''))
    if src is None:
        raise RuntimeError('The original sculpt is gone; cannot re-make.')
    me = build_mesh(context, src, st.detail, st.faces, st.flat_angle)
    old = ob.data
    me.name = old.name
    ob.data = me
    for p in me.polygons:
        p.use_smooth = True
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return ob


def apply(context, ob):
    with context.temp_override(object=ob, active_object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
        for name in (BEVEL, NORMALS):
            if ob.modifiers.get(name) is not None:
                bpy.ops.object.modifier_apply(modifier=name)
    if SRC_KEY in ob:
        del ob[SRC_KEY]


class MCH_OT_lowpoly_make(bpy.types.Operator):
    """Low poly copy of the selected sculpt with a live Bevel / Chamfer (the original is kept, hidden)"""
    bl_idname = 'mch.lowpoly_make'
    bl_label = 'Make Low Poly'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        st = context.scene.mch_lowpoly
        ob = context.active_object
        try:
            if is_lowpoly(ob):
                remake(context, ob, st)
            else:
                ob = make(context, ob, st)
        except RuntimeError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, f'{ob.name}: {len(ob.data.polygons)} faces (low poly), live Bevel')
        return {'FINISHED'}


class MCH_OT_lowpoly_apply(bpy.types.Operator):
    """Make the bevel permanent (the low poly becomes an ordinary mesh)"""
    bl_idname = 'mch.lowpoly_apply'
    bl_label = 'Apply Low Poly'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return is_lowpoly(context.active_object)

    def execute(self, context):
        apply(context, context.active_object)
        return {'FINISHED'}


class MCH_OT_lowpoly_show_source(bpy.types.Operator):
    """Show / hide the original sculpt"""
    bl_idname = 'mch.lowpoly_show_source'
    bl_label = 'Show Original'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return is_lowpoly(context.active_object)

    def execute(self, context):
        src = bpy.data.objects.get(context.active_object.get(SRC_KEY, ''))
        if src is not None:
            src.hide_set(not src.hide_get())
        return {'FINISHED'}


def draw(layout, context):
    st = context.scene.mch_lowpoly
    ob = context.active_object
    box = layout.box()
    box.label(text='LOW POLY (sculpt -> base mesh)', icon='MOD_DECIM')
    col = box.column(align=True)
    col.prop(st, 'detail')
    col.prop(st, 'faces')
    col.prop(st, 'flat_angle')
    row = box.row(align=True)
    row.scale_y = 1.3
    row.operator('mch.lowpoly_make', text='Re-make Low Poly' if is_lowpoly(ob) else 'Make Low Poly',
                 icon='FILE_REFRESH' if is_lowpoly(ob) else 'MOD_DECIM')
    if not is_lowpoly(ob):
        box.label(text='Select your sculpt (ZBrush import) first', icon='INFO')
        return
    bev = ob.modifiers.get(BEVEL)
    if bev is not None:
        col = box.column(align=True)
        col.label(text=f'{len(ob.data.polygons)} faces | Bevel / Chamfer (live)')
        col.prop(bev, 'width')
        col.prop(bev, 'segments', text='Segments (1 = chamfer)')
        col.prop(bev, 'profile', slider=True)
        col.prop(bev, 'angle_limit', text='Edges sharper than')
    row = box.row(align=True)
    row.operator('mch.lowpoly_show_source', icon='HIDE_OFF')
    row.operator('mch.lowpoly_apply', icon='CHECKMARK')


CLASSES = (MCH_PG_LowPoly, MCH_OT_lowpoly_make, MCH_OT_lowpoly_apply, MCH_OT_lowpoly_show_source)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_lowpoly = bpy.props.PointerProperty(type=MCH_PG_LowPoly)


def unregister():
    if hasattr(bpy.types.Scene, 'mch_lowpoly'):
        del bpy.types.Scene.mch_lowpoly
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
