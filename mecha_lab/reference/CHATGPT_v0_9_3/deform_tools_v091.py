"""Mecha Lab Deform: editable Lattice Cage and curve-driven Bend/Twist.

Controllers use Blender's native Lattice/Curve modifiers, not destructive
mesh replacement. Edit the controller in Edit Mode; G/R/S with Proportional
Editing ON gives ZBrush-like point/falloff deformation of neighbouring points.
Curve points can also be moved, tilted (Ctrl+T) and scaled (Alt+S).

The lattice supports multi-object *soft* deformation; true rigid-body part
posing is intentionally not claimed here.
"""
from __future__ import annotations

import math
import bpy
from mathutils import Matrix, Vector
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty

from . import core_geometry as cg

TAG = 'mch_deform_kind'
MOD = 'MCH_Deform'


def _targets(ctrl):
    if ctrl is None:
        return []
    return [(ob, mod) for ob in bpy.data.objects if ob.type == 'MESH'
            for mod in ob.modifiers if mod.type in {'LATTICE', 'CURVE'}
            and mod.object == ctrl and mod.name.startswith(MOD)]


def controller(context):
    ob = context.active_object
    if ob is not None and ob.get(TAG) in {'LATTICE', 'BEND'}:
        return ob
    if ob and ob.type == 'MESH':
        for mod in reversed(ob.modifiers):
            if mod.type in {'LATTICE', 'CURVE'} and mod.object and mod.object.get(TAG) in {'LATTICE', 'BEND'}:
                return mod.object
    return None


def _sync(self, context):
    ctrl = self.id_data
    if not isinstance(ctrl, bpy.types.Object) or not ctrl.get(TAG):
        return
    p = ctrl.mch_deform
    if ctrl.type == 'LATTICE':
        lat = ctrl.data
        # Native Blender interpolates previously moved cage points when
        # changing point counts.  Do not recreate the lattice data block.
        for attr, value in [('points_u', p.res_x), ('points_v', p.res_y), ('points_w', p.res_z)]:
            if getattr(lat, attr) != value:
                setattr(lat, attr, value)
        for ob, mod in _targets(ctrl):
            if mod.type == 'LATTICE':
                mod.strength = p.strength
    elif ctrl.type == 'CURVE':
        ctrl.data.resolution_u = p.curve_resolution
        # Applied along curve length, leaving the start untwisted.
        for sp in ctrl.data.splines:
            pts = list(sp.bezier_points) if sp.type == 'BEZIER' else []
            for index, point in enumerate(pts):
                fraction = index / max(1, len(pts) - 1)
                point.tilt = p.twist * fraction
                point.radius = 1.0 + (p.taper - 1.0) * fraction


class MCH_PG_Deform(bpy.types.PropertyGroup):
    res_x: IntProperty(name='X Points', min=2, max=32, default=4, update=_sync)
    res_y: IntProperty(name='Y Points', min=2, max=32, default=3, update=_sync)
    res_z: IntProperty(name='Z Points', min=2, max=32, default=3, update=_sync)
    strength: FloatProperty(name='Strength', default=1.0, min=0, max=1, update=_sync)
    curve_resolution: IntProperty(name='Curve Resolution', min=2, max=64, default=24, update=_sync)
    twist: FloatProperty(name='Twist', subtype='ANGLE', default=0.0, soft_min=-6.283185, soft_max=6.283185, update=_sync)
    taper: FloatProperty(name='Taper', default=1.0, min=0.01, soft_min=0.2, soft_max=3.0, update=_sync)


class MCH_OT_deform_lattice(bpy.types.Operator):
    bl_idname = 'mch.deform_lattice'
    bl_label = 'Create Lattice Cage'
    bl_description = 'Fit an editable Lattice around selected meshes; one cage can deform multiple objects'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        objects = [o for o in context.selected_objects if o.type == 'MESH']
        active = context.active_object if context.active_object in objects else objects[0]
        from mathutils import Quaternion
        rot = active.matrix_world.to_quaternion().to_matrix().to_4x4()
        inv = rot.inverted_safe()
        dg = context.evaluated_depsgraph_get()
        verts = [inv @ (ob.matrix_world @ Vector(corner))
                 for ob in objects for corner in ob.evaluated_get(dg).bound_box]
        lower = Vector([min(v[i] for v in verts) for i in range(3)])
        upper = Vector([max(v[i] for v in verts) for i in range(3)])
        size = upper - lower
        # Avoid 0-size flat planes producing a degenerate cage.
        for i in range(3):
            size[i] = max(size[i] * 1.03, 0.04)
        middle = (lower + upper) * 0.5
        lat = bpy.data.lattices.new('MCH_Lattice')
        ctrl = bpy.data.objects.new('MCH_Lattice', lat)
        context.collection.objects.link(ctrl)
        ctrl.matrix_world = rot @ Matrix.Translation(middle) @ Matrix.Diagonal((size[0], size[1], size[2], 1.0))
        ctrl.display_type = 'WIRE'
        ctrl.show_in_front = True
        ctrl[TAG] = 'LATTICE'
        p = ctrl.mch_deform
        p.res_x, p.res_y, p.res_z = 4, 3, 3
        for ob in objects:
            mod = ob.modifiers.new(MOD + '_Lattice', 'LATTICE')
            mod.object = ctrl
            mod.strength = p.strength
            mod.show_in_editmode = True
        for ob in context.selected_objects:
            ob.select_set(False)
        ctrl.select_set(True)
        context.view_layer.objects.active = ctrl
        self.report({'INFO'}, f'Lattice created for {len(objects)} mesh(es). Edit Cage → select a point → G/R/S (Proportional ON)')
        return {'FINISHED'}


# ROT maps the curve's local +X to the selected mesh's chosen local long axis.
# The Curve modifier's +X rest line from x=0 gives identity deformation.
_AXIS_ROT = (
    Matrix.Identity(4),
    Matrix.Rotation(math.pi / 2.0, 4, 'Z'),
    Matrix.Rotation(-math.pi / 2.0, 4, 'Y'),
)


class MCH_OT_deform_bend(bpy.types.Operator):
    bl_idname = 'mch.deform_bend'
    bl_label = 'Create Bend Curve'
    bl_description = 'Create a straight editable Curve modifier along the longest local axis of the mesh'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        ob = context.active_object
        dg = context.evaluated_depsgraph_get()
        locs = [Vector(c) for c in ob.evaluated_get(dg).bound_box]
        lower = Vector([min(c[i] for c in locs) for i in range(3)])
        upper = Vector([max(c[i] for c in locs) for i in range(3)])
        axis = max(range(3), key=lambda i: upper[i] - lower[i])
        length = max(upper[axis] - lower[axis], 0.1)
        other = [i for i in range(3) if i != axis]
        center = (lower + upper) * 0.5
        origin = Vector((0.0, 0.0, 0.0))
        origin[axis] = lower[axis]
        for i in other:
            origin[i] = center[i]
        curve = bpy.data.curves.new('MCH_Bend', 'CURVE')
        curve.dimensions = '3D'
        curve.resolution_u = 24
        curve.twist_mode = 'MINIMUM'
        sp = curve.splines.new('BEZIER')
        sp.bezier_points.add(3)
        # Curve starts at x=0 in its own coordinates, with controller
        # origin aligned to the selected mesh's minimum axis coordinate.
        # This leaves the straight rest pose unchanged and covers the entire
        # body (including geometry on the negative side of object origin).
        far = length
        for i, pt in enumerate(sp.bezier_points):
            pt.co = (far * (i / 3), 0.0, 0.0)
            pt.handle_left_type = 'AUTO'
            pt.handle_right_type = 'AUTO'
            pt.radius = 1.0
        ctrl = bpy.data.objects.new('MCH_BendCurve', curve)
        context.collection.objects.link(ctrl)
        ctrl.matrix_world = ob.matrix_world @ Matrix.Translation(origin) @ _AXIS_ROT[axis]
        ctrl.show_in_front = True
        ctrl[TAG] = 'BEND'
        ctrl['mch_bend_length'] = far
        ctrl['mch_bend_axis'] = axis
        mod = ob.modifiers.new(MOD + '_Bend', 'CURVE')
        mod.object = ctrl
        mod.deform_axis = 'POS_X'
        mod.show_in_editmode = True
        for other_ob in context.selected_objects:
            other_ob.select_set(False)
        ctrl.select_set(True)
        context.view_layer.objects.active = ctrl
        self.report({'INFO'}, 'Bend Curve created. Edit Curve → move points (G), tilt points (Ctrl+T), radius (Alt+S)')
        return {'FINISHED'}


class MCH_OT_deform_edit(bpy.types.Operator):
    bl_idname = 'mch.deform_edit'
    bl_label = 'Edit Deform Controller'
    bl_description = 'Edit control points with native G/R/S and proportional falloff (scroll-wheel adjusts radius)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return controller(context) is not None

    def execute(self, context):
        ctrl = controller(context)
        if context.object and context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        for ob in context.selected_objects:
            ob.select_set(False)
        ctrl.select_set(True)
        context.view_layer.objects.active = ctrl
        bpy.ops.object.mode_set(mode='EDIT')
        ctrl['_mch_previous_prop'] = bool(context.scene.tool_settings.use_proportional_edit)
        context.scene.tool_settings.use_proportional_edit = True
        context.scene.tool_settings.proportional_edit_falloff = 'SMOOTH'
        self.report({'INFO'}, 'Choose a controller point, then G/R/S. Mouse wheel = falloff radius, O = toggle proportional edit')
        return {'FINISHED'}


class MCH_OT_deform_finish_edit(bpy.types.Operator):
    bl_idname = 'mch.deform_finish_edit'
    bl_label = 'Exit Controller Edit'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode in {'EDIT_LATTICE', 'EDIT_CURVE'} and controller(context) is not None

    def execute(self, context):
        ctrl = controller(context)
        bpy.ops.object.mode_set(mode='OBJECT')
        if ctrl and '_mch_previous_prop' in ctrl:
            context.scene.tool_settings.use_proportional_edit = bool(ctrl.pop('_mch_previous_prop'))
        return {'FINISHED'}


class MCH_OT_deform_gizmo(bpy.types.Operator):
    bl_idname = 'mch.deform_gizmo'
    bl_label = 'Deform Transform Gizmo'
    bl_description = 'Activate native Blender Move / Rotate / Scale gizmo for selected controller points'
    bl_options = {'REGISTER', 'INTERNAL'}

    action: EnumProperty(items=[('MOVE', 'Move', ''), ('ROTATE', 'Rotate', ''), ('SCALE', 'Scale', '')], default='MOVE')

    @classmethod
    def poll(cls, context):
        return context.mode in {'EDIT_LATTICE', 'EDIT_CURVE'} and controller(context) is not None

    def execute(self, context):
        name = {'MOVE': 'builtin.move', 'ROTATE': 'builtin.rotate', 'SCALE': 'builtin.scale'}[self.action]
        try:
            bpy.ops.wm.tool_set_by_id(name=name, space_type='VIEW_3D')
        except (RuntimeError, TypeError) as ex:
            self.report({'WARNING'}, f'Toolbar unavailable here ({ex}); use G / R / S')
            return {'CANCELLED'}
        return {'FINISHED'}


class MCH_OT_deform_reset(bpy.types.Operator):
    bl_idname = 'mch.deform_reset'
    bl_label = 'Reset Deformation'
    bl_description = 'Reset controller points to the original straight cage/curve; modifiers remain live'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return controller(context) is not None

    def execute(self, context):
        ctrl = controller(context)
        if context.object and context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        if ctrl.type == 'LATTICE':
            for p in ctrl.data.points:
                p.co_deform = p.co.copy()
            ctrl.mch_deform.strength = 1.0
        else:
            sp = ctrl.data.splines[0]
            far = float(ctrl.get('mch_bend_length', 1))
            for i, p in enumerate(sp.bezier_points):
                p.co = (far * i / max(1, len(sp.bezier_points) - 1), 0, 0)
                p.handle_left_type = 'AUTO'
                p.handle_right_type = 'AUTO'
                p.tilt = 0
                p.radius = 1
            ctrl.mch_deform.twist = 0
            ctrl.mch_deform.taper = 1
        self.report({'INFO'}, 'Controller reset to rest shape')
        return {'FINISHED'}


class MCH_OT_deform_apply(bpy.types.Operator):
    bl_idname = 'mch.deform_apply'
    bl_label = 'Apply Deformation'
    bl_description = 'Bake deformation AND modifiers earlier in the stack. Later modifiers remain live; linked mesh twins are untouched'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and controller(context) is not None

    def execute(self, context):
        ctrl = controller(context)
        targets = _targets(ctrl)
        if not targets:
            self.report({'ERROR'}, 'No mesh currently uses this controller')
            return {'CANCELLED'}
        if any(ob.data.shape_keys for ob, _ in targets):
            self.report({'ERROR'}, 'Shape keys must be removed or applied before deform baking')
            return {'CANCELLED'}
        # Bake the evaluated stack THROUGH each deformation modifier in one
        # operation. Blender's regular "Apply modifier" is not a valid answer
        # for a modifier after SubD: applying Lattice alone changes the result.
        # We bake all earlier modifiers too; modifiers *after* Deform remain.
        # All meshes are prepared before any object is mutated (multi-target
        # creation errors cannot half-apply a controller).
        prepared = []
        try:
            for ob, mod in targets:
                mod_list = list(ob.modifiers)
                idx = mod_list.index(mod)
                changed = [(m, m.show_viewport) for m in mod_list[idx + 1:]]
                try:
                    for m, _ in changed:
                        m.show_viewport = False
                    dg = context.evaluated_depsgraph_get()
                    dg.update()
                    new_mesh = bpy.data.meshes.new_from_object(
                        ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
                    if new_mesh is None or len(new_mesh.vertices) == 0:
                        raise RuntimeError(f'Empty evaluated mesh: {ob.name}')
                    prepared.append((ob, mod_list[:idx + 1], new_mesh))
                finally:
                    for m, original in changed:
                        m.show_viewport = original
        except Exception as ex:
            for _ob, _mods, mesh in prepared:
                if mesh.users == 0:
                    bpy.data.meshes.remove(mesh)
            self.report({'ERROR'}, f'Cannot prepare deformation bake: {ex}. Meshes unchanged')
            return {'CANCELLED'}
        for ob, mods, new_mesh in prepared:
            # Direct datablock replacement preserves custom attributes and UVs
            # in the evaluated mesh, keeps Alt+D twins intact, and avoids
            # operator context / multi-user restrictions.
            ob.data = new_mesh
            for m in mods:
                ob.modifiers.remove(m)
        done = len(prepared)
        bpy.data.objects.remove(ctrl, do_unlink=True)
        self.report({'INFO'}, f'Applied deformation to {done} object(s)')
        return {'FINISHED'}


class MCH_OT_deform_remove(bpy.types.Operator):
    bl_idname = 'mch.deform_remove'
    bl_label = 'Remove Controller (No Apply)'
    bl_description = 'Remove the controller and its modifiers; original mesh geometry is kept'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and controller(context) is not None

    def execute(self, context):
        ctrl = controller(context)
        for ob, mod in _targets(ctrl):
            ob.modifiers.remove(mod)
        bpy.data.objects.remove(ctrl, do_unlink=True)
        self.report({'INFO'}, 'Controller removed; original geometry restored')
        return {'FINISHED'}


def draw(layout, context):
    layout.label(text='Lattice / Bend Curve | Soft Deform', icon='MOD_LATTICE')
    ctrl = controller(context)
    if ctrl is None:
        box = layout.box()
        box.label(text='Select a mesh (or multiple meshes for Lattice)')
        row = box.row(align=True)
        row.scale_y = 1.4
        row.operator('mch.deform_lattice', text='Create Lattice', icon='MOD_LATTICE')
        row.operator('mch.deform_bend', text='Create Bend Curve', icon='CURVE_BEZCURVE')
    else:
        p = ctrl.mch_deform
        box = layout.box()
        box.label(text=f'LIVE: {ctrl.name}', icon='MOD_LATTICE' if ctrl.type == 'LATTICE' else 'CURVE_BEZCURVE')
        box.label(text=f'Target meshes: {len(_targets(ctrl))}')
        col = box.column(align=True)
        if ctrl.type == 'LATTICE':
            col.label(text='Cage Points (X / Y / Z)')
            row = col.row(align=True)
            row.prop(p, 'res_x', text='X')
            row.prop(p, 'res_y', text='Y')
            row.prop(p, 'res_z', text='Z')
            col.prop(p, 'strength', slider=True)
        else:
            col.prop(p, 'curve_resolution')
            col.prop(p, 'twist', slider=True)
            col.prop(p, 'taper', slider=True)
        row = box.row(align=True)
        row.scale_y = 1.2
        if context.mode == 'OBJECT':
            row.operator('mch.deform_edit', text='Edit Points', icon='EDITMODE_HLT')
        elif context.mode in {'EDIT_LATTICE', 'EDIT_CURVE'}:
            row.operator('mch.deform_finish_edit', text='Exit Edit', icon='OBJECT_DATAMODE')
        if context.mode in {'EDIT_LATTICE', 'EDIT_CURVE'}:
            tools = box.row(align=True)
            for value, label, icon in [('MOVE','Move','MOUSE_MOVE'),
                                       ('ROTATE','Rotate','GESTURE_ROTATE'),
                                       ('SCALE','Scale','FULLSCREEN_ENTER')]:
                tools.operator('mch.deform_gizmo', text=label, icon=icon).action = value
            ts = context.scene.tool_settings
            box.prop(ts, 'use_proportional_edit', text='Proportional Editing (O)')
            box.prop(ts, 'proportional_edit_falloff', text='Falloff Type')
            box.prop(ts, 'proportional_size', text='Falloff Radius')
        row = box.row(align=True)
        row.operator('mch.deform_reset', text='Reset', icon='LOOP_BACK')
        if context.mode == 'OBJECT':
            row.operator('mch.deform_apply', text='Apply (bake stack)', icon='CHECKMARK')
            row.operator('mch.deform_remove', text='Remove', icon='TRASH')
        info = layout.box()
        info.label(text='Select point + G/R/S | Proportional ON', icon='INFO')
        if ctrl.type == 'LATTICE':
            info.label(text='O: toggle falloff | Wheel: change radius')
        else:
            info.label(text='Curve: G move | Ctrl+T tilt | Alt+S radius')
        info.label(text='Apply bakes modifiers BEFORE Deform, too')
        info.label(text='Multi-object Soft = YES | Rigid parts = NOT YET')


CLASSES = (MCH_PG_Deform, MCH_OT_deform_lattice, MCH_OT_deform_bend,
           MCH_OT_deform_edit, MCH_OT_deform_finish_edit, MCH_OT_deform_gizmo, MCH_OT_deform_reset,
           MCH_OT_deform_apply, MCH_OT_deform_remove)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Object.mch_deform = PointerProperty(type=MCH_PG_Deform)


def unregister():
    del bpy.types.Object.mch_deform
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
