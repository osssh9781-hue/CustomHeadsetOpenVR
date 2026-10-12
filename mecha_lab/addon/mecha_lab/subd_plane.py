"""SubD Plane: a plane with a Simple + Catmull-Clark + Solidify modifier stack.

Both subdivision modifiers are used AT THE SAME TIME, each with its own level
slider (Simple first densifies the cage without rounding it, Catmull-Clark
then smooths), followed by Solidify.  Settings live on the object
(``Object.mch_subd``) and drive the modifiers directly, so changes show in the
viewport immediately and the plane stays editable in Edit Mode (extrude edges,
add points...).  "Apply All" bakes the three modifiers in stack order with the
data-level apply from core_geometry (works on Alt+D shared meshes).
"""
from __future__ import annotations

import bmesh
import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty

from . import core_geometry as cg

MOD_SIMPLE = 'MCH_SubD_Simple'
MOD_CC = 'MCH_SubD_CatmullClark'
MOD_SOLID = 'MCH_SubD_Solidify'
ORDER = (MOD_SIMPLE, MOD_CC, MOD_SOLID)
CREASE_ATTR = 'crease_edge'


def _sync(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and ob.type == 'MESH' and self.active:
        sync_modifiers(ob)


class MCH_PG_SubD(bpy.types.PropertyGroup):
    """Scene.mch_subd = defaults for new planes; Object.mch_subd = live settings."""
    active: BoolProperty(default=False, options={'HIDDEN'})
    simple_levels: IntProperty(name='Simple Levels', default=1, min=0, max=5, update=_sync,
                               description='Simple subdivision (densify without rounding)')
    cc_levels: IntProperty(name='Catmull-Clark Levels', default=2, min=0, max=5, update=_sync,
                           description='Catmull-Clark smoothing subdivision (applied after Simple)')
    thickness: FloatProperty(name='Thickness', default=0.05, soft_min=-1.0, soft_max=1.0, precision=4,
                             unit='LENGTH', update=_sync)
    offset: FloatProperty(name='Offset', default=-1.0, min=-1.0, max=1.0, update=_sync,
                          description='Solidify offset: -1 inward, 0 centred, 1 outward')
    even_thickness: BoolProperty(name='Even Thickness', default=True, update=_sync)
    use_creases: BoolProperty(name='Use Edge Creases', default=True, update=_sync,
                              description='Catmull-Clark respects edge crease values')
    size: FloatProperty(name='Plane Size', default=1.0, min=0.0001, soft_max=100.0, unit='LENGTH')
    crease_value: FloatProperty(name='Crease', default=1.0, min=0.0, max=1.0,
                                description='Value written to selected edges by "Set Crease"')


def sync_modifiers(ob):
    """Create missing modifiers in the right order and write the slider values."""
    p = ob.mch_subd
    mods = ob.modifiers
    simple = mods.get(MOD_SIMPLE) or mods.new(MOD_SIMPLE, 'SUBSURF')
    simple.subdivision_type = 'SIMPLE'
    cc = mods.get(MOD_CC) or mods.new(MOD_CC, 'SUBSURF')
    cc.subdivision_type = 'CATMULL_CLARK'
    solid = mods.get(MOD_SOLID) or mods.new(MOD_SOLID, 'SOLIDIFY')
    for mod, lv in ((simple, p.simple_levels), (cc, p.cc_levels)):
        mod.levels = lv
        mod.render_levels = lv
        mod.show_in_editmode = True
        mod.show_on_cage = False
    if hasattr(cc, 'use_creases'):
        cc.use_creases = p.use_creases
    solid.thickness = p.thickness
    solid.offset = p.offset
    solid.use_even_offset = p.even_thickness
    solid.show_in_editmode = True
    # Keep the three in stack order: Simple -> Catmull-Clark -> Solidify (other
    # user modifiers stay where they are, after ours).
    for i, name in enumerate(ORDER):
        idx = mods.find(name)
        if idx != i and idx >= 0:
            try:
                mods.move(idx, i)
            except (AttributeError, RuntimeError):
                pass


def active_subd(context):
    ob = context.active_object
    if ob is not None and ob.type == 'MESH' and getattr(ob, 'mch_subd', None) and ob.mch_subd.active:
        return ob
    return None


class MCH_OT_subd_plane_create(bpy.types.Operator):
    bl_idname = 'mch.subd_plane_create'
    bl_label = 'Create SubD Plane'
    bl_description = ('Add a plane at the 3D cursor with Simple + Catmull-Clark subdivision and Solidify '
                      '(all live). Tab into Edit Mode and extrude edges to build armour panels')
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        d = context.scene.mch_subd
        me = bpy.data.meshes.new('MCH_SubDPlane')
        bm = bmesh.new()
        try:
            bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=d.size / 2.0)
            bm.to_mesh(me)
        finally:
            bm.free()
        ob = bpy.data.objects.new('MCH_SubDPlane', me)
        coll = context.collection if context.collection is not None else context.scene.collection
        coll.objects.link(ob)
        ob.location = context.scene.cursor.location.copy()
        p = ob.mch_subd
        for key in ('simple_levels', 'cc_levels', 'thickness', 'offset', 'even_thickness', 'use_creases'):
            setattr(p, key, getattr(d, key))
        p.active = True
        sync_modifiers(ob)
        for o in context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        self.report({'INFO'}, 'SubD Plane created: Tab to edit, extrude edges with E')
        return {'FINISHED'}


class MCH_OT_subd_set_crease(bpy.types.Operator):
    bl_idname = 'mch.subd_set_crease'
    bl_label = 'Set Crease on Selected Edges'
    bl_description = 'Edit Mode: write the Crease value to the selected edges (1 = sharp under Catmull-Clark)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object is not None

    def execute(self, context):
        ob = context.active_object
        value = context.scene.mch_subd.crease_value
        bm = bmesh.from_edit_mesh(ob.data)
        layer = bm.edges.layers.float.get(CREASE_ATTR) or bm.edges.layers.float.new(CREASE_ATTR)
        count = 0
        for e in bm.edges:
            if e.select:
                e[layer] = value
                count += 1
        bmesh.update_edit_mesh(ob.data)
        self.report({'INFO'}, f'Crease {value:.2f} on {count} edges')
        return {'FINISHED'}


class MCH_OT_subd_apply_all(bpy.types.Operator):
    bl_idname = 'mch.subd_apply_all'
    bl_label = 'Apply All'
    bl_description = 'Bake Simple, Catmull-Clark and Solidify (in that order) into the mesh'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return active_subd(context) is not None

    def execute(self, context):
        ob = active_subd(context)
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        policy = getattr(getattr(context.scene, 'mch_cut', None), 'shared_mesh', 'SINGLE')
        try:
            for name in ORDER:
                mod = ob.modifiers.get(name)
                if mod is not None:
                    cg.apply_single_modifier(context, ob, mod, policy)
        except (cg.CutError, RuntimeError) as ex:
            self.report({'ERROR'}, f'Apply failed (remaining modifiers kept): {ex}')
            return {'CANCELLED'}
        ob.mch_subd.active = False
        self.report({'INFO'}, f'{ob.name}: SubD stack applied ({len(ob.data.polygons)} faces)')
        return {'FINISHED'}


class MCH_OT_subd_adopt(bpy.types.Operator):
    bl_idname = 'mch.subd_adopt'
    bl_label = 'Add SubD Stack to Selected'
    bl_description = 'Give the active mesh the same Simple + Catmull-Clark + Solidify live stack'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.type == 'MESH' and not ob.mch_subd.active

    def execute(self, context):
        ob = context.active_object
        d = context.scene.mch_subd
        p = ob.mch_subd
        for key in ('simple_levels', 'cc_levels', 'thickness', 'offset', 'even_thickness', 'use_creases'):
            setattr(p, key, getattr(d, key))
        p.active = True
        sync_modifiers(ob)
        return {'FINISHED'}


CLASSES = (MCH_PG_SubD, MCH_OT_subd_plane_create, MCH_OT_subd_set_crease, MCH_OT_subd_apply_all,
           MCH_OT_subd_adopt)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_subd = bpy.props.PointerProperty(type=MCH_PG_SubD)
    bpy.types.Object.mch_subd = bpy.props.PointerProperty(type=MCH_PG_SubD)


def unregister():
    for t in (bpy.types.Object, bpy.types.Scene):
        if hasattr(t, 'mch_subd'):
            delattr(t, 'mch_subd')
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
