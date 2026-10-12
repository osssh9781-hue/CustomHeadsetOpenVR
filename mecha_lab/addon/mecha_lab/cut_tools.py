"""v0.5.9 compatibility layer for the old Cut entry points.

The long-running ``mch.draw_delete_cut`` modal of v0.5.9 kept the whole Cut
session inside one operator, so Ctrl+Z could not undo single cuts and every
menu click needed Esc first.  It is replaced by the native Cut / Split tools
(see cut_engine).  The old operator id is kept as a thin alias so existing
keymaps and buttons still work.  ``mch.cut_finalize`` applies Live cuts with
the data-safe modifier apply (works on Alt+D shared meshes, rolls back on
failure).
"""
import bpy
from bpy.props import BoolProperty

from . import core_geometry as cg


class MCH_OT_draw_delete_cut(bpy.types.Operator):
    bl_idname = 'mch.draw_delete_cut'
    bl_label = 'Cut Tool [C]'
    bl_description = 'Activate the Mecha Cut tool (Split with Keep Both)'
    bl_options = {'INTERNAL'}
    keep_both: BoolProperty(name='Keep Both Halves', default=False)

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D'

    def execute(self, context):
        from . import workspace_ui
        workspace_ui.activate_mecha_tool(context, 'SPLIT' if self.keep_both else 'CUT')
        return {'FINISHED'}


def _live_parts(ob):
    if ob.get('mch_cut_carrier'):
        cutter = ob
    else:
        cutter = bpy.data.objects.get(ob.get('mch_recent_cut', ''))
        if cutter is None and ob.get('mch_cut_path'):
            cutter = bpy.data.objects.get(ob.get('mch_cut_cutter_name', ''))
    if cutter is None or not cutter.get('mch_cut_carrier'):
        return None, None, None, None
    live = getattr(cutter, 'mch_live', None)
    target = (live.target if live and live.target else None) or \
        bpy.data.objects.get(cutter.get('mch_cut_target_name', ''))
    piece = (live.source if live and live.source else None) or \
        bpy.data.objects.get(cutter.get('mch_cut_piece_name', ''))
    path = (live.path if live and live.path else None) or \
        bpy.data.objects.get(cutter.get('mch_cut_path_name', ''))
    return cutter, target, piece, path


class MCH_OT_cut_finalize(bpy.types.Operator):
    bl_idname = 'mch.cut_finalize'
    bl_label = 'Apply Live Cut'
    bl_description = 'Apply live cut Booleans (all targets using this cutter) and delete the cutter'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.active_object is not None

    def execute(self, context):
        cutter, target, piece, path = _live_parts(context.active_object)
        if cutter is None:
            self.report({'WARNING'}, 'Select a live cutter, or a mesh with a recent live cut')
            return {'CANCELLED'}
        policy = context.scene.mch_cut.shared_mesh if hasattr(context.scene, 'mch_cut') else 'SINGLE'
        users = [ob for ob in bpy.data.objects if ob.type == 'MESH' and
                 any(m.type == 'BOOLEAN' and m.object == cutter for m in ob.modifiers)]
        if not users:
            self.report({'ERROR'}, 'No live Boolean uses this cutter')
            return {'CANCELLED'}
        applied = []
        try:
            for ob in users:
                for m in [m for m in ob.modifiers if m.type == 'BOOLEAN' and m.object == cutter]:
                    cg.apply_single_modifier(context, ob, m, policy)
                applied.append(ob.name)
                if ob.get('mch_recent_cut') == cutter.name:
                    del ob['mch_recent_cut']
        except (cg.CutError, RuntimeError) as ex:
            self.report({'ERROR'}, 'Apply failed: ' + str(ex))
            return {'CANCELLED'}
        cg.remove_object_and_mesh(cutter)
        if path is not None:
            try:
                bpy.data.objects.remove(path, do_unlink=True)
            except ReferenceError:
                pass
        if target is not None and target.name in bpy.data.objects:
            for o in context.selected_objects:
                o.select_set(False)
            target.select_set(True)
            context.view_layer.objects.active = target
        if piece is not None and piece.name in bpy.data.objects:
            piece.select_set(True)
        self.report({'INFO'}, 'Live cut applied: ' + ', '.join(applied))
        return {'FINISHED'}


CLASSES = (MCH_OT_draw_delete_cut, MCH_OT_cut_finalize)
