"""0.24.73 Mesh Tools (sidebar, Mecha Lab tab): the ZBrush shelf's DynaMesh, Decimate, Quad Remesh, Edge Mesh and Hard
Edges in Object Mode, on every selected mesh at once - the same settings as the shelf (``scene.mch_zb``), so a part
started on the ZBrush screen goes on here and the other way round.  One undo step for the whole run; a mesh that
can't be done is skipped with its reason (the others still run).
"""
from __future__ import annotations

import math

import bpy
from bpy.props import StringProperty

ACTIONS = {'DYNAMESH': 'DynaMesh', 'DECIMATE': 'Decimate', 'QUAD_REMESH': 'Quad Remesh', 'EDGE_MESH': 'Edge Mesh',
           'HE_FIND': 'Find Edges', 'HE_APPLY': 'Apply', 'HE_CLEAR': 'Clear', 'FIX_MESH': 'Fix Mesh', 'REFIX': 'Re-Fix'}
HEAVY = {'DYNAMESH', 'DECIMATE', 'QUAD_REMESH', 'EDGE_MESH', 'HE_FIND', 'HE_APPLY', 'REFIX'}


def _targets(context):
    return [o for o in context.selected_objects if o.type == 'MESH']


def run_one(context, ob, zb, action):
    """``action`` on mesh object ``ob`` (Object Mode).  Returns a message; raises RuntimeError when it can't."""
    from . import edge_mesh as em
    from . import fast_decimate as fd
    from . import hard_edges as he
    from . import quad_field as qf
    from . import zb_sculpt as zs
    if zs.multires(ob) is not None:
        raise RuntimeError('has subdivision levels (Multires) - apply or remove them first')
    if action == 'DYNAMESH':
        from . import voxel_for_points
        v = voxel_for_points(context, ob, zb.points)
        if v <= 0.0:
            raise RuntimeError('no surface')
        ob.data.remesh_voxel_size = v
        with context.temp_override(object=ob, active_object=ob, selected_objects=[ob],
                                   selected_editable_objects=[ob]):
            bpy.ops.object.voxel_remesh()
        return f'DynaMesh: {len(ob.data.vertices):,} points'
    if action == 'DECIMATE':
        if not fd.available():
            msg = fd.blender_decimate(context, ob, zb.decimate)
        else:
            msg = fd.decimate_object(ob, zb.decimate, even=zb.dec_even, quads=zb.dec_quads, keep_mask=zb.dec_mask,
                                     keep_groups=zb.dec_groups, keep_borders=zb.dec_borders)
        zs.shade_result(ob, zb)                      # 0.24.85
        return msg
    if action == 'QUAD_REMESH':
        bg = zs.background_job(context, ob, zb, 'QUAD_REMESH')     # 0.24.86
        if bg:
            return bg
        msg = qf.remesh_object(ob, max(1, int(round(zb.qr_target * 1000))), all_quads=zb.qr_mode == 'ALL',
                               crease_deg=math.degrees(zb.qr_angle))
        zs.shade_result(ob, zb)
        return msg
    if action == 'EDGE_MESH':
        if not fd.available():
            raise RuntimeError('the Fast Decimate engine is not available on this system')
        return em.build(context, ob, zb)
    if action == 'HE_FIND':
        if len(ob.data.polygons) > he.MAX_POLYS:
            raise RuntimeError(f'{len(ob.data.polygons):,} polygons - Decimate, Quad Remesh or Edge Mesh first')
        if ob.data.shape_keys is not None:
            raise RuntimeError('remove the shape keys first')
        n, _f0, _f1 = he.find(ob, zb)
        he.set_live(ob, zb)
        return f'Hard Edges: {n:,} edges'
    if action == 'HE_APPLY':
        k = he.apply_live(context, ob, zb)
        ob.pop(he.KEY, None)
        return f'Hard Edges: applied, {len(ob.data.polygons):,} polygons' if k else 'Hard Edges: nothing to apply'
    if action == 'HE_CLEAR':
        he.clear(ob)
        return 'Hard Edges: cleared'
    if action == 'REFIX':                            # 0.24.84 DynaMesh > clean Decimate / Quad Remesh
        from . import refix
        bg = zs.background_job(context, ob, zb, 'REFIX')          # 0.24.86
        if bg:
            return bg
        return refix.run(context, ob, zb)
    if action == 'FIX_MESH':                         # 0.24.76 like ZBrush's Fix Mesh
        from . import mesh_fix
        if ob.data.shape_keys is not None:
            raise RuntimeError('remove the shape keys first')
        return mesh_fix.report(mesh_fix.fix_mesh(ob.data))
    raise RuntimeError(f'unknown action {action}')


class MCH_OT_mesh_tool(bpy.types.Operator):
    """DynaMesh / Decimate / Quad Remesh / Edge Mesh / Hard Edges on the selected meshes (Object Mode; the ZBrush
    shelf's settings)"""
    bl_idname = 'mch.mesh_tool'
    bl_label = 'Mesh Tool'
    bl_options = {'REGISTER', 'UNDO'}
    action: StringProperty()

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and hasattr(context.scene, 'mch_zb') and bool(_targets(context))

    @classmethod
    def description(cls, context, props):
        return f'{ACTIONS.get(props.action, props.action)} on the selected meshes (settings shared with the ZBrush shelf)'

    def execute(self, context):
        zb = context.scene.mch_zb
        obs = _targets(context)
        name = ACTIONS.get(self.action, self.action)
        if self.action in HEAVY:
            try:
                from . import safety_save
                safety_save.before_risky('Mesh Tools ' + name)
            except (ImportError, AttributeError, RuntimeError):
                pass
        wm = context.window_manager
        done, last, skipped = 0, '', []
        wm.progress_begin(0, len(obs))
        try:
            from . import armor_shell
            for k, ob in enumerate(obs):
                try:
                    armor_shell.bake_live(context, ob)      # 0.24.80 a live Armor Shell: on the shell, not its base
                    last = run_one(context, ob, zb, self.action)
                    done += 1
                except (RuntimeError, ValueError, MemoryError) as ex:
                    skipped.append(f'{ob.name}: {str(ex).splitlines()[0] if str(ex) else type(ex).__name__}')
                wm.progress_update(k + 1)
        finally:
            wm.progress_end()
        if not done:
            self.report({'WARNING'}, f'{name}: ' + ('; '.join(skipped[:3]) or 'nothing done'))
            return {'CANCELLED'}
        msg = last if len(obs) == 1 else f'{name}: {done} of {len(obs)} meshes'
        if skipped:
            msg += f' - skipped {len(skipped)}: ' + '; '.join(skipped[:3])
        self.report({'WARNING'} if skipped else {'INFO'}, msg)
        return {'FINISHED'}


def draw(layout, context):
    zb = getattr(context.scene, 'mch_zb', None)
    if zb is None:
        return

    def op(row, text, action):
        row.operator('mch.mesh_tool', text=text).action = action
    box = layout.box()
    box.label(text='MESH TOOLS  (selected meshes)', icon='MOD_REMESH')
    r = box.row(align=True)
    op(r, 'DynaMesh', 'DYNAMESH')
    r.prop(zb, 'points', text='Points')
    box.row(align=True).operator('mch.mesh_tool', text='Fix Mesh (weld cracks, slivers, inside walls, small holes)',
                                 icon='TOOL_SETTINGS').action = 'FIX_MESH'
    from . import refix
    refix.draw_row(box, zb)                          # 0.24.84 Re-Fix
    col = box.column(align=True)
    r = col.row(align=True)
    op(r, 'Decimate', 'DECIMATE')
    r.prop(zb, 'decimate', text='%')
    r = col.row(align=True)
    r.prop(zb, 'dec_even', toggle=True)
    r.prop(zb, 'dec_quads', toggle=True)
    r.prop(zb, 'dec_borders', toggle=True)
    col.row(align=True).prop(zb, 'result_shade', expand=True)     # 0.24.85 result shading (export-ready)
    col = box.column(align=True)
    r = col.row(align=True)
    op(r, 'Quad Remesh', 'QUAD_REMESH')
    r.prop(zb, 'qr_target', text='Target')
    r.prop(zb, 'bg_jobs', text='Background', toggle=True)        # 0.24.86
    from . import bg_jobs
    bg_jobs.draw_status(col, context.active_object)
    col.row(align=True).prop(zb, 'qr_mode', expand=True)
    col = box.column(align=True)
    r = col.row(align=True)
    op(r, 'Edge Mesh', 'EDGE_MESH')
    r.prop(zb, 'em_detail', text='Detail')
    r = col.row(align=True)
    r.prop(zb, 'em_auto', toggle=True)
    r.prop(zb, 'em_tolerance')
    r = col.row(align=True)
    r.prop(zb, 'em_adaptive', toggle=True)
    r.prop(zb, 'em_straight', toggle=True)
    r = col.row(align=True)
    r.prop(zb, 'he_fit', toggle=True)
    r.prop(zb, 'he_match', toggle=True)
    col = box.column(align=True)
    r = col.row(align=True)
    op(r, 'Find Edges', 'HE_FIND')
    r.prop(zb, 'he_angle')
    col.row(align=True).prop(zb, 'he_style', expand=True)
    r = col.row(align=True)
    r.prop(zb, 'he_width')
    r.prop(zb, 'he_segments')
    r = col.row(align=True)
    r.prop(zb, 'he_subdiv')
    r.prop(zb, 'he_client', toggle=True)
    r = col.row(align=True)
    op(r, 'Apply', 'HE_APPLY')
    op(r, 'Clear', 'HE_CLEAR')


class MCH_PT_mesh_tools(bpy.types.Panel):
    bl_idname = 'MCH_PT_mesh_tools'
    bl_label = 'Mesh Tools'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Mecha Lab'
    bl_order = 79

    @classmethod
    def poll(cls, context):
        from . import tool_state as ts
        return context.mode == 'OBJECT' and ts.sidebar_select(context)

    def draw(self, context):
        draw(self.layout, context)


CLASSES = (MCH_OT_mesh_tool, MCH_PT_mesh_tools)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
