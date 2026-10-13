"""Mesh Along Curve: Curve Deform and Curve Array (live, non-destructive).

Curve Deform  - Curve modifier on the mesh; Deform Axis +-X/Y/Z, Start Offset,
                Rotation and Scale move the mesh along / around the curve.
Curve Array   - repeats a source mesh along a curve on a separate "array"
                object: Rigid = Geometry Nodes instances (count / spacing / fit,
                start / end trim, follow tangent, align axis, rotation offset,
                scale, reverse); Deform = Array (fit curve or count) + Curve
                modifiers so every segment bends with the curve.
Placement     - Free / World X / World Y / World Z.  A world mode moves the
                curve's BASE LINE onto that world axis through the origin; the
                control points stay free to bend.  Changeable any time.
Editing the curve (Edit Mode, Bezier handles) updates everything live.
"""
from __future__ import annotations

import math

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, PointerProperty
from mathutils import Matrix, Vector

MOD_DEFORM = 'MCH_AlongCurve'
MOD_ARRAY = 'MCH_CurveArray'
MOD_ARRAY_MOD = 'MCH_CurveArray_Array'
MOD_ARRAY_CURVE = 'MCH_CurveArray_Curve'
COLL_ARRAYS = 'Curve Arrays'
AXIS_ROT = {'X': Matrix.Identity(4), 'Y': Matrix.Rotation(math.pi / 2, 4, 'Z'),
            'Z': Matrix.Rotation(-math.pi / 2, 4, 'Y')}
AXES = [('POS_X', '+X', ''), ('NEG_X', '-X', ''), ('POS_Y', '+Y', ''), ('NEG_Y', '-Y', ''),
        ('POS_Z', '+Z', ''), ('NEG_Z', '-Z', '')]
_AXIS_VEC = {'POS_X': Vector((1, 0, 0)), 'NEG_X': Vector((-1, 0, 0)), 'POS_Y': Vector((0, 1, 0)),
             'NEG_Y': Vector((0, -1, 0)), 'POS_Z': Vector((0, 0, 1)), 'NEG_Z': Vector((0, 0, -1))}


# =============================================================================
# Curves and placement
# =============================================================================


def new_curve(context, name, length=4.0, points=5, start=Vector()):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.resolution_u = 24
    spl = cu.splines.new('BEZIER')
    spl.bezier_points.add(points - 1)
    for i, bp in enumerate(spl.bezier_points):
        bp.co = (length * i / (points - 1), 0.0, 0.0)
        bp.handle_left_type = bp.handle_right_type = 'AUTO'
    ob = bpy.data.objects.new(name, cu)
    (context.collection or context.scene.collection).objects.link(ob)
    ob.location = start
    return ob


def apply_placement(curve, mode):
    """World axis: base line (local +X) on that world axis through the origin
    (the coordinate along the axis is kept).  Free: unchanged."""
    if mode == 'FREE':
        return
    axis = {'WORLD_X': 0, 'WORLD_Y': 1, 'WORLD_Z': 2}[mode]
    along = curve.matrix_world.translation[axis]
    loc = Vector((0.0, 0.0, 0.0))
    loc[axis] = along
    curve.matrix_world = Matrix.Translation(loc) @ AXIS_ROT['XYZ'[axis]]
    curve['mch_placement'] = mode


def _place_update(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and ob.type == 'CURVE':
        apply_placement(ob, self.placement)


class MCH_PG_CurvePlace(bpy.types.PropertyGroup):
    placement: EnumProperty(name='Curve Placement', items=[
        ('FREE', 'Free', 'Anywhere in world space'), ('WORLD_X', 'World X', 'Base line on the world X axis'),
        ('WORLD_Y', 'World Y', 'Base line on the world Y axis'), ('WORLD_Z', 'World Z', 'Base line on the world Z axis')],
        default='FREE', update=_place_update)


# =============================================================================
# Curve Deform
# =============================================================================


def _deform_update(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and self.active:
        sync_deform(ob)


def _pd(prop, **kw):
    kw.setdefault('update', _deform_update)
    return prop(**kw)


class MCH_PG_CurveDeform(bpy.types.PropertyGroup):
    active: BoolProperty(default=False, options={'HIDDEN'})
    curve: PointerProperty(type=bpy.types.Object, name='Curve', poll=lambda s, o: o.type == 'CURVE')
    rest: FloatVectorProperty(size=16, options={'HIDDEN'})
    axis: _pd(EnumProperty, name='Deform Axis', items=AXES, default='POS_X')
    start_offset: _pd(FloatProperty, name='Start Offset', default=0.0, unit='LENGTH',
                      description='Slide the mesh along the curve')
    rotation: _pd(FloatProperty, name='Rotation', default=0.0, subtype='ANGLE', description='Roll around the curve')
    scale: _pd(FloatProperty, name='Scale', default=1.0, min=0.001, soft_max=10.0)
    stretch: _pd(BoolProperty, name='Stretch', default=False, description='Curve "Stretch": fill the curve length')


def _flat(m):
    return [m[r][c] for r in range(4) for c in range(4)]


def _mat(v):
    return Matrix([v[0:4], v[4:8], v[8:12], v[12:16]])


def sync_deform(ob):
    p = ob.mch_deform_curve
    curve = p.curve
    mod = ob.modifiers.get(MOD_DEFORM)
    if curve is None:
        return
    if mod is None:
        mod = ob.modifiers.new(MOD_DEFORM, 'CURVE')
    mod.object = curve
    mod.deform_axis = p.axis
    curve.data.use_stretch = p.stretch
    curve.data.use_deform_bounds = p.stretch
    a = _AXIS_VEC[p.axis]
    rest = _mat(p.rest)
    xf = Matrix.Translation(a * p.start_offset) @ Matrix.Rotation(p.rotation, 4, a) @ \
        Matrix.Diagonal((p.scale, p.scale, p.scale, 1.0))
    # the mesh stays in the curve's space: its transform drives the mapping
    ob.matrix_world = curve.matrix_world @ xf @ rest


class MCH_OT_curve_deform(bpy.types.Operator):
    bl_idname = 'mch.curve_deform'
    bl_label = 'Deform Along Curve'
    bl_description = ('Bend the selected meshes along the selected curve (or a new curve along the mesh). '
                      'Edit the curve handles to reshape them live')
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        d = context.scene.mch_deform_curve
        meshes = [o for o in context.selected_objects if o.type == 'MESH']
        curve = next((o for o in context.selected_objects if o.type == 'CURVE'), None)
        if curve is None:
            ob = meshes[0]
            bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
            lo = Vector((min(v.x for v in bb), sum(v.y for v in bb) / 8, sum(v.z for v in bb) / 8))
            length = max(max(v.x for v in bb) - lo.x, 0.1)
            curve = new_curve(context, 'MCH_DeformCurve', length=length * 1.5, start=lo)
            curve.mch_place.placement = context.scene.mch_place.placement
        for ob in meshes:
            p = ob.mch_deform_curve
            p.active = False
            p.curve = curve
            p.axis, p.start_offset, p.rotation, p.scale, p.stretch = d.axis, d.start_offset, d.rotation, d.scale, \
                d.stretch
            p.rest = _flat(curve.matrix_world.inverted_safe() @ ob.matrix_world)
            p.active = True
            sync_deform(ob)
        context.scene.mch_curve_last = meshes[0]
        self.report({'INFO'}, f'{len(meshes)} mesh(es) follow "{curve.name}"')
        return {'FINISHED'}


# =============================================================================
# Curve Array
# =============================================================================


def _array_update(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and self.active:
        sync_array(ob)


def _pa(prop, **kw):
    kw.setdefault('update', _array_update)
    return prop(**kw)


class MCH_PG_CurveArray(bpy.types.PropertyGroup):
    active: BoolProperty(default=False, options={'HIDDEN'})
    source: _pa(PointerProperty, type=bpy.types.Object, name='Object', poll=lambda s, o: o.type == 'MESH')
    curve: _pa(PointerProperty, type=bpy.types.Object, name='Curve', poll=lambda s, o: o.type == 'CURVE')
    count_mode: _pa(EnumProperty, name='Count Mode', items=[
        ('COUNT', 'Count', 'Fixed number of copies over the curve'),
        ('SPACING', 'Spacing', 'A copy every Spacing units'),
        ('FIT', 'Fit Curve', 'As many copies as fit (copy size x spacing factor)')], default='FIT')
    count: _pa(IntProperty, name='Count', default=8, min=1, max=10000)
    spacing: _pa(FloatProperty, name='Spacing', default=0.5, min=0.001, soft_max=10.0, unit='LENGTH',
                 description='Spacing mode: distance. Fit mode: gap added to the copy size')
    start_offset: _pa(FloatProperty, name='Start Offset', default=0.0, min=0.0, max=1.0, subtype='FACTOR')
    end_offset: _pa(FloatProperty, name='End Offset', default=0.0, min=0.0, max=1.0, subtype='FACTOR')
    scale: _pa(FloatProperty, name='Global Scale', default=1.0, min=0.001, soft_max=10.0)
    rotation: _pa(FloatVectorProperty, name='Rotation Offset', size=3, subtype='EULER')
    follow: _pa(BoolProperty, name='Follow Tangent', default=True)
    align_axis: _pa(EnumProperty, name='Align Axis', items=[('X', 'X', ''), ('Y', 'Y', ''), ('Z', 'Z', '')],
                    default='X', description='Axis of the source mesh that points along the curve')
    mode: _pa(EnumProperty, name='Mode', items=[('RIGID', 'Rigid', 'Copies keep their shape'),
                                                 ('DEFORM', 'Deform', 'Copies bend with the curve')], default='RIGID')
    reverse: _pa(BoolProperty, name='Reverse Direction', default=False)


def _source_length(src, axis):
    k = 'XYZ'.index(axis)
    vs = [Vector(c) for c in src.bound_box]
    return max(max(v[k] for v in vs) - min(v[k] for v in vs), 1e-4) * max(src.scale[k], 1e-6)


def _array_group(ob):
    from . import output_group, object_info
    p = ob.mch_curve_array
    name = 'MCH CurveArray | ' + ob.name
    old = bpy.data.node_groups.get(name)
    if old is not None:
        bpy.data.node_groups.remove(old)
    g, out = output_group(name)
    curve = object_info(g, p.curve, 'MCH_CURVE')
    geo = curve.outputs['Geometry']
    if p.reverse:
        rev = g.nodes.new('GeometryNodeReverseCurve')
        g.links.new(geo, rev.inputs['Curve'])
        geo = rev.outputs['Curve']
    trim = g.nodes.new('GeometryNodeTrimCurve')
    trim.mode = 'FACTOR'
    trim.inputs[2].default_value = min(p.start_offset, 0.999)          # Start (factor)
    trim.inputs[3].default_value = max(1.0 - p.end_offset, p.start_offset + 0.001)   # End (factor)
    g.links.new(geo, trim.inputs['Curve'])
    pts = g.nodes.new('GeometryNodeCurveToPoints')
    if p.count_mode == 'COUNT':
        pts.mode = 'COUNT'
        pts.inputs['Count'].default_value = p.count
    else:
        pts.mode = 'LENGTH'
        step = p.spacing if p.count_mode == 'SPACING' else _source_length(p.source, p.align_axis) * p.scale + p.spacing
        pts.inputs['Length'].default_value = max(step, 1e-4)
    g.links.new(trim.outputs['Curve'], pts.inputs['Curve'])
    src = object_info(g, p.source, 'MCH_SOURCE', relative=False)
    inst = g.nodes.new('GeometryNodeInstanceOnPoints')
    g.links.new(pts.outputs['Points'], inst.inputs['Points'])
    g.links.new(src.outputs['Geometry'], inst.inputs['Instance'])
    if p.follow:
        g.links.new(pts.outputs['Rotation'], inst.inputs['Rotation'])
    inst.inputs['Scale'].default_value = (p.scale, p.scale, p.scale)
    fix = {'X': (0.0, 0.0, 0.0), 'Y': (0.0, 0.0, -math.pi / 2), 'Z': (0.0, math.pi / 2, 0.0)}[p.align_axis]
    rot1 = g.nodes.new('GeometryNodeRotateInstances')
    rot1.inputs['Rotation'].default_value = fix
    rot1.inputs['Local Space'].default_value = True
    g.links.new(inst.outputs['Instances'], rot1.inputs['Instances'])
    rot2 = g.nodes.new('GeometryNodeRotateInstances')
    rot2.inputs['Rotation'].default_value = tuple(p.rotation)
    rot2.inputs['Local Space'].default_value = True
    g.links.new(rot1.outputs['Instances'], rot2.inputs['Instances'])
    # light instances while editing; Apply flips the switch to real geometry
    real = g.nodes.new('GeometryNodeRealizeInstances')
    sw = g.nodes.new('GeometryNodeSwitch')
    sw.name = 'MCH_REALIZE'
    sw.input_type = 'GEOMETRY'
    sw.inputs['Switch'].default_value = False
    g.links.new(rot2.outputs['Instances'], real.inputs['Geometry'])
    g.links.new(rot2.outputs['Instances'], sw.inputs['False'])
    g.links.new(real.outputs['Geometry'], sw.inputs['True'])
    g.links.new(sw.outputs['Output'], out.inputs['Geometry'])
    return g


def set_realize(ob, state):
    mod = ob.modifiers.get(MOD_ARRAY)
    if mod is not None and mod.node_group is not None:
        sw = mod.node_group.nodes.get('MCH_REALIZE')
        if sw is not None:
            sw.inputs['Switch'].default_value = state
            ob.update_tag()


def sync_array(ob):
    p = ob.mch_curve_array
    if p.source is None or p.curve is None:
        return
    for name in (MOD_ARRAY, MOD_ARRAY_MOD, MOD_ARRAY_CURVE):
        m = ob.modifiers.get(name)
        if m is not None:
            ob.modifiers.remove(m)
    if p.mode == 'RIGID':
        if ob.data is not None and len(ob.data.vertices):
            ob.data.clear_geometry()
        if 'mch_src' in ob:
            del ob['mch_src']
        mod = ob.modifiers.new(MOD_ARRAY, 'NODES')
        mod.node_group = _array_group(ob)
        ob.matrix_world = p.curve.matrix_world.copy()
    else:
        # bending copies: the array object carries the source mesh itself
        src = p.source
        if ob.get('mch_src') != src.name or not len(ob.data.vertices):
            old = ob.data
            ob.data = src.data.copy()
            ob['mch_src'] = src.name
            if old is not None and old.users == 0:
                bpy.data.meshes.remove(old)
        arr = ob.modifiers.new(MOD_ARRAY_MOD, 'ARRAY')
        k = 'XYZ'.index(p.align_axis)
        rel = [0.0, 0.0, 0.0]
        rel[k] = 1.0 + p.spacing / max(_source_length(src, p.align_axis), 1e-6) if p.count_mode != 'SPACING' else \
            p.spacing / max(_source_length(src, p.align_axis), 1e-6)
        arr.relative_offset_displace = rel
        if p.count_mode == 'COUNT':
            arr.fit_type = 'FIXED_COUNT'
            arr.count = p.count
        else:
            arr.fit_type = 'FIT_CURVE'
            arr.curve = p.curve
        cm = ob.modifiers.new(MOD_ARRAY_CURVE, 'CURVE')
        cm.object = p.curve
        cm.deform_axis = {'X': 'POS_X', 'Y': 'POS_Y', 'Z': 'POS_Z'}[p.align_axis] if not p.reverse else \
            {'X': 'NEG_X', 'Y': 'NEG_Y', 'Z': 'NEG_Z'}[p.align_axis]
        length = p.curve.data.splines[0].calc_length() if p.curve.data.splines else 0.0
        a = Vector((0, 0, 0))
        a[k] = length * p.start_offset
        ob.matrix_world = p.curve.matrix_world @ Matrix.Translation(a) @ \
            Matrix.Diagonal((p.scale, p.scale, p.scale, 1.0))


class MCH_OT_curve_array(bpy.types.Operator):
    bl_idname = 'mch.curve_array'
    bl_label = 'Curve Array'
    bl_description = 'Repeat the active mesh along the selected curve (live, separate object)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        from .face_extract import _parts_collection
        d = context.scene.mch_curve_array
        meshes = [o for o in context.selected_objects if o.type == 'MESH' and not o.mch_curve_array.active]
        curve = next((o for o in context.selected_objects if o.type == 'CURVE'), None)
        if curve is None:
            curve = new_curve(context, 'MCH_ArrayCurve', length=6.0, start=context.scene.cursor.location.copy())
            curve.mch_place.placement = context.scene.mch_place.placement
        made = []
        for src in meshes:
            me = bpy.data.meshes.new('MCH_CurveArray')
            ob = bpy.data.objects.new(src.name + '_CurveArray', me)
            _parts_collection(context, COLL_ARRAYS).objects.link(ob)
            p = ob.mch_curve_array
            for key in ('count_mode', 'count', 'spacing', 'start_offset', 'end_offset', 'scale', 'rotation', 'follow',
                        'align_axis', 'mode', 'reverse'):
                setattr(p, key, getattr(d, key))
            p.source = src
            p.curve = curve
            p.active = True
            sync_array(ob)
            made.append(ob)
        if not made:
            self.report({'WARNING'}, 'Select the mesh to repeat (and optionally the curve)')
            return {'CANCELLED'}
        context.scene.mch_curve_last = made[-1]
        self.report({'INFO'}, f'{len(made)} curve array(s) on "{curve.name}"')
        return {'FINISHED'}


def active_along(context):
    ob = context.active_object
    for cand in (ob, getattr(context.scene, 'mch_curve_last', None)):
        if cand is None or cand.name not in bpy.data.objects:
            continue
        if cand.mch_curve_array.active or cand.mch_deform_curve.active:
            return cand
    return None


class MCH_OT_along_finish(bpy.types.Operator):
    bl_idname = 'mch.along_finish'
    bl_label = 'Apply / Reset'
    bl_options = {'REGISTER', 'UNDO'}

    action: EnumProperty(items=[('APPLY', 'Apply', 'Bake into a mesh'), ('RESET', 'Reset', 'Remove / restore')])

    @classmethod
    def poll(cls, context):
        return active_along(context) is not None

    def execute(self, context):
        ob = active_along(context)
        dg = context.evaluated_depsgraph_get()
        if self.action == 'APPLY':
            set_realize(ob, True)
            dg = context.evaluated_depsgraph_get()
            dg.update()
            me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
            mw = ob.matrix_world.copy()
            for m in list(ob.modifiers):
                if m.name.startswith(('MCH_AlongCurve', 'MCH_CurveArray')):
                    ob.modifiers.remove(m)
            old = ob.data
            ob.data = me
            ob.matrix_world = mw
            if old.users == 0:
                bpy.data.meshes.remove(old)
        else:
            if ob.mch_curve_array.active:
                bpy.data.objects.remove(ob)
                self.report({'INFO'}, 'Curve array removed')
                return {'FINISHED'}
            p = ob.mch_deform_curve
            m = ob.modifiers.get(MOD_DEFORM)
            if m is not None:
                ob.modifiers.remove(m)
            if p.curve is not None:
                ob.matrix_world = p.curve.matrix_world @ _mat(p.rest)
        ob.mch_curve_array.active = False
        ob.mch_deform_curve.active = False
        return {'FINISHED'}


def draw(layout, context):
    ob = active_along(context)
    sc = context.scene
    box = layout.box()
    box.label(text='Curve Placement (new curves)', icon='CURVE_BEZCURVE')
    box.row(align=True).prop(sc.mch_place, 'placement', expand=True)
    act = context.active_object
    if act is not None and act.type == 'CURVE':
        box.label(text='Selected curve: ' + act.name)
        box.row(align=True).prop(act.mch_place, 'placement', expand=True)
    row = layout.row(align=True)
    row.scale_y = 1.4
    row.operator('mch.curve_deform', icon='MOD_CURVE')
    row.operator('mch.curve_array', icon='MOD_ARRAY')
    layout.label(text='Select mesh(es) + optional curve (else a new curve)', icon='INFO')
    if ob is not None and ob.mch_deform_curve.active:
        p = ob.mch_deform_curve
        box = layout.box()
        box.label(text='CURVE DEFORM: ' + ob.name, icon='MOD_CURVE')
        box.prop(p, 'curve')
        box.prop(p, 'axis')
        col = box.column(align=True)
        col.prop(p, 'start_offset')
        col.prop(p, 'rotation')
        col.prop(p, 'scale')
        box.prop(p, 'stretch')
    elif ob is not None and ob.mch_curve_array.active:
        draw_array_settings(layout.box(), ob.mch_curve_array, 'CURVE ARRAY: ' + ob.name)
    else:
        draw_array_settings(layout.box(), sc.mch_curve_array, 'Defaults for the next Curve Array')
    if ob is not None:
        row = layout.row(align=True)
        row.operator('mch.along_finish', text='Apply', icon='CHECKMARK').action = 'APPLY'
        row.operator('mch.along_finish', text='Reset', icon='LOOP_BACK').action = 'RESET'


def draw_array_settings(box, p, title):
    box.label(text=title, icon='MOD_ARRAY')
    if p.active:
        box.prop(p, 'source')
        box.prop(p, 'curve')
    box.row(align=True).prop(p, 'mode', expand=True)
    box.row(align=True).prop(p, 'count_mode', expand=True)
    col = box.column(align=True)
    if p.count_mode == 'COUNT':
        col.prop(p, 'count')
    col.prop(p, 'spacing')
    col.prop(p, 'start_offset', slider=True)
    col.prop(p, 'end_offset', slider=True)
    col.prop(p, 'scale')
    box.prop(p, 'rotation')
    row = box.row(align=True)
    row.prop(p, 'follow', toggle=True)
    row.prop(p, 'reverse', toggle=True)
    box.row(align=True).prop(p, 'align_axis', expand=True)


CLASSES = (MCH_PG_CurvePlace, MCH_PG_CurveDeform, MCH_PG_CurveArray, MCH_OT_curve_deform, MCH_OT_curve_array,
           MCH_OT_along_finish)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Object.mch_place = PointerProperty(type=MCH_PG_CurvePlace)
    bpy.types.Scene.mch_place = PointerProperty(type=MCH_PG_CurvePlace)
    bpy.types.Object.mch_deform_curve = PointerProperty(type=MCH_PG_CurveDeform)
    bpy.types.Scene.mch_deform_curve = PointerProperty(type=MCH_PG_CurveDeform)
    bpy.types.Object.mch_curve_array = PointerProperty(type=MCH_PG_CurveArray)
    bpy.types.Scene.mch_curve_array = PointerProperty(type=MCH_PG_CurveArray)
    bpy.types.Scene.mch_curve_last = PointerProperty(type=bpy.types.Object)


def unregister():
    for owner, name in ((bpy.types.Scene, 'mch_curve_last'), (bpy.types.Scene, 'mch_curve_array'),
                        (bpy.types.Object, 'mch_curve_array'), (bpy.types.Scene, 'mch_deform_curve'),
                        (bpy.types.Object, 'mch_deform_curve'), (bpy.types.Scene, 'mch_place'),
                        (bpy.types.Object, 'mch_place')):
        if hasattr(owner, name):
            delattr(owner, name)
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
