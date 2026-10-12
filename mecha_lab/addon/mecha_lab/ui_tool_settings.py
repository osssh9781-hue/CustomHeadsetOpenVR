"""Right-hand sidebar content: settings of ONE tool at a time.

Each ``draw_<tool>`` receives the layout of the contextual ``MCH_PT_main``
panel.  Mirror, Radial Array and Surface Conform keep their own sub-panels
(their polls use ``tool_state.tool_is``).
"""
import bpy

from . import tool_state as ts


def _hint(layout, *lines):
    col = layout.column(align=True)
    col.scale_y = 0.8
    for text in lines:
        col.label(text=text)


def _section(layout, title, icon='NONE'):
    box = layout.box()
    box.label(text=title, icon=icon)
    return box


def draw_shape_options(layout, context, mode):
    brush = context.scene.mch_brush
    shape = brush.shape
    name = ts.SHAPE_BY_ID[shape][1]
    box = _section(layout, 'Shape: ' + name + '  (palette at top-left / RMB)', 'SELECT_SET')
    col = box.column(align=True)
    if shape in {'CIRCLE', 'ELLIPSE'}:
        col.prop(brush, 'circle_segments')
    elif shape == 'CURVE_LASSO':
        col.prop(brush, 'curve_resolution')
        _hint(box, 'Click a placed point again: sharp > soft > medium > strong',
              'Drag a point to move it, drag a handle to change rounding')
    elif shape == 'STROKE':
        col.prop(brush, 'stroke_spacing')
        col.prop(brush, 'stroke_simplify')
        if mode == 'MASK':
            col.prop(brush, 'mask_brush_radius')
    elif shape == 'LASSO':
        if mode != 'MASK':
            col.prop(brush, 'line_open')
        _hint(box, '2 points + Enter = straight line cut', 'Shift = 45° snap, Backspace = undo point')
    elif shape == 'CUSTOM':
        row = box.row(align=True)
        row.template_icon_view(context.scene, 'mch_png_preset', show_labels=True, scale=5.0,
                               scale_popup=5.0)
        row = box.row(align=True)
        row.operator('mch.import_cut_png', text='Import PNG', icon='IMPORT')
        if context.scene.mch_png_preset != 'NONE':
            row.operator('mch.delete_cut_preset', text='', icon='TRASH')
        col = box.column(align=True)
        col.prop(brush, 'custom_size')
        col.prop(brush, 'custom_rotation')
        col.prop(brush, 'custom_drag_rotate')
        _hint(box, 'Click = stamp at Stamp Radius, drag = size',
              'Tip: Depth "From Surface" for engraved vents')


def draw_cut(layout, context, mode='CUT'):
    s = context.scene.mch_settings
    cut = context.scene.mch_cut
    col = layout.column(align=True)
    col.prop(cut, 'depth_mode', expand=True)
    if cut.depth_mode == 'SURFACE':
        col.prop(cut, 'depth')
    col.prop(cut, 'targets', expand=True)
    col.prop(s, 'auto_apply', text='Auto Apply (OFF = live, editable cutter)')
    if mode == 'SPLIT':
        col.prop(cut, 'split_cap')

    draw_shape_options(layout, context, mode)

    box = _section(layout, 'Edge Finish (new cut edges only)', 'MOD_BEVEL')
    box.prop(cut, 'edge_finish', expand=True)
    if cut.edge_finish != 'NONE':
        c = box.column(align=True)
        c.prop(cut, 'finish_width')
        if cut.edge_finish == 'BEVEL':
            c.prop(cut, 'finish_segments')
            c.prop(cut, 'finish_profile', slider=True)
        if not s.auto_apply:
            box.label(text='Edge Finish is skipped in Live mode', icon='INFO')

    box = _section(layout, 'Advanced', 'PREFERENCES')
    c = box.column(align=True)
    c.prop(cut, 'solver')
    if cut.solver in {'AUTO', 'EXACT'}:
        c.prop(cut, 'hole_tolerant')
    c.prop(cut, 'shared_mesh')
    c.prop(cut, 'fast_line')
    c.prop(cut, 'line_cap')

    row = layout.row(align=True)
    row.operator('mch.cut_finalize', text='Apply Live Cut', icon='CHECKMARK')
    if mode == 'CUT':
        row.operator('mch.surface_cut', text='Knife Edges', icon='EDITMODE_HLT')
    if mode == 'CUT':
        _hint(layout, 'LMB draw: remove inside | Alt: keep inside', 'Enter / double-click: apply | Esc: cancel stroke',
              'Ctrl+Z: undo last point, then last cut', 'RMB: shapes | RMB double-click: exit tool')
    else:
        _hint(layout, 'LMB draw: split into two parts', 'Inside becomes "<name>_Split"',
              'RMB: shapes | RMB double-click: exit tool')


def draw_split(layout, context):
    draw_cut(layout, context, 'SPLIT')


def draw_boolean(layout, context):
    s = context.scene.mch_settings
    col = layout.column(align=True)
    row = col.row(align=True)
    row.scale_y = 1.4
    op = row.operator('mch.boolean', text='Difference', icon='REMOVE')
    op.operation = 'DIFFERENCE'
    op = row.operator('mch.boolean', text='Union', icon='ADD')
    op.operation = 'UNION'
    row = col.row(align=True)
    op = row.operator('mch.boolean', text='Intersect', icon='SELECT_INTERSECT')
    op.operation = 'INTERSECT'
    row.operator('mch.slice', text='Slice (keep both)', icon='MOD_EDGESPLIT')
    col.separator()
    col.prop(s, 'auto_apply')
    col.prop(s, 'keep_cutter')
    col.prop(context.scene.mch_cut, 'shared_mesh')
    _hint(layout, 'Select 2 meshes; active (yellow) = target', 'B: Difference (MECHA LAB workspace only)')


def draw_fuse(layout, context):
    from . import fuse_target_from_context
    target = fuse_target_from_context(context)
    if target:
        p = target.mch_fuse
        layout.label(text='LIVE PREVIEW | ' + target.name, icon='GEOMETRY_NODES')
        layout.label(text='Source: ' + (p.source.name if p.source else 'Missing'))
        layout.prop(p, 'mode', expand=True)
        if p.mode == 'SEAM':
            layout.prop(p, 'edge_style', expand=True)
            layout.prop(p, 'radius', text=('Chamfer Width' if p.edge_style == 'CHAMFER' else 'Fillet Width'),
                        slider=True)
            if p.edge_style == 'FILLET':
                layout.prop(p, 'segments')
        else:
            layout.prop(p, 'voxel_size')
            layout.prop(p, 'smooth_iterations')
            layout.prop(p, 'smooth_factor')
        row = layout.row(align=True)
        op = row.operator('mch.smart_fuse_source', text='Edit Source', icon='EDITMODE_HLT')
        op.action = 'EDIT'
        op = row.operator('mch.smart_fuse_source', text='Preview', icon='HIDE_OFF')
        op.action = 'HIDE'
        layout.prop(p, 'delete_source_on_confirm')
        row = layout.row(align=True)
        row.scale_y = 1.3
        row.operator('mch.smart_fuse_confirm', text='CONFIRM / APPLY', icon='CHECKMARK')
        row.operator('mch.smart_fuse_cancel', text='CANCEL', icon='CANCEL')
        return
    s = context.scene.mch_settings
    layout.label(text='Select exactly 2 overlapping meshes')
    layout.prop(s, 'fuse_mode', expand=True)
    if s.fuse_mode == 'SEAM':
        layout.prop(s, 'fuse_edge_style', expand=True)
        layout.prop(s, 'fuse_radius', text='Seam Width', slider=True)
        if s.fuse_edge_style == 'FILLET':
            layout.prop(s, 'fuse_segments')
    else:
        layout.prop(s, 'fuse_voxel_size')
        layout.prop(s, 'fuse_smooth_iterations')
        layout.prop(s, 'fuse_smooth_factor')
    row = layout.row()
    row.scale_y = 1.4
    row.operator('mch.smart_fuse', text='CREATE LIVE SMART FUSE', icon='MOD_BEVEL')
    _hint(layout, 'Active (yellow) object keeps the result',
          'Works best: closed meshes that really overlap',
          'Touching-only / open meshes: refused with a message')


def draw_mask(layout, context):
    s = context.scene.mch_settings
    draw_shape_options(layout, context, 'MASK')
    if context.mode == 'EDIT_MESH':
        layout.operator('mch.mask_selected_faces', text='ADD SELECTED FACES', icon='FACESEL')
    layout.prop(s, 'mch_mask_thickness')
    row = layout.row(align=True)
    row.operator('mch.mask_extract', text='EXTRACT & RAISE', icon='MOD_SOLIDIFY')
    row.operator('mch.mask_clear', text='CLEAR', icon='X')
    box = layout.box()
    box.label(text='Status: PARTIAL', icon='INFO')
    _hint(box, 'Painted faces are selected in their ENTIRETY',
          'Subdivide large polygons for smaller mask patches',
          'Mask does NOT protect from Cut/Boolean yet',
          'Alt+draw erases')


def draw_draw(layout, context):
    s = context.scene.mch_settings
    layout.prop(s, 'path_draw_mode', expand=True)
    if s.path_draw_mode == 'FREE':
        layout.prop(s, 'path_sample_px')
    layout.prop(s, 'profile_shape')
    if s.profile_shape == 'CUSTOM':
        layout.prop(s, 'profile_preset')
    row = layout.row(align=True)
    row.prop(s, 'line_width')
    row.prop(s, 'line_depth')
    row = layout.row(align=True)
    row.scale_y = 1.3
    op = row.operator('mch.draw_path', text='Draw Panel Cut', icon='MOD_BOOLEAN')
    op.kind = 'PANEL'
    op = row.operator('mch.draw_path', text='Draw Curve', icon='CURVE_BEZCURVE')
    op.kind = 'CURVE'
    row = layout.row(align=True)
    op = row.operator('mch.edit_handles', text='Straight')
    op.shape = 'VECTOR'
    op = row.operator('mch.edit_handles', text='Smooth')
    op.shape = 'AUTOMATIC'
    _hint(layout, 'Free: LMB drag | Polyline: LMB points', 'Shift+click: 45° | Enter/RMB: finish',
          'Select path > Tab to move points')


def draw_array(layout, context):
    s = context.scene.mch_settings
    layout.prop(s, 'array_source')
    layout.prop(s, 'array_spacing')
    layout.prop(s, 'array_scale')
    row = layout.row()
    row.scale_y = 1.3
    op = row.operator('mch.draw_path', text='Draw Array Path', icon='MOD_ARRAY')
    op.kind = 'ARRAY'
    layout.prop(s, 'point_radius')
    layout.operator('mch.point_radius', text='Set Selected Point Size')
    _hint(layout, 'Path edit: G move / V handles')


def draw_edit(layout, context):
    ob = context.active_object
    carrier = ob
    if ob and ob.get('mch_path'):
        carrier = bpy.data.objects.get(ob.get('mch_carrier', ''))
    if carrier and carrier.get('mch_role') in {'PANEL', 'CURVE', 'ARRAY'}:
        props = carrier.mch_live
        layout.label(text='Mode: ' + carrier.get('mch_role'))
        layout.prop(props, 'path')
        if carrier.get('mch_role') in {'PANEL', 'CURVE'}:
            layout.prop(props, 'shape')
            if props.shape == 'CUSTOM':
                layout.prop(props, 'custom_profile')
            layout.prop(props, 'width')
            layout.prop(props, 'depth')
        if carrier.get('mch_role') == 'ARRAY':
            layout.prop(props, 'source')
            layout.prop(props, 'spacing')
            layout.prop(props, 'array_scale')
        layout.operator('mch.bake_live', text='CONFIRM / APPLY', icon='CHECKMARK')
    else:
        layout.label(text='Select a generated path or result')
    layout.prop(context.scene.mch_settings, 'delete_path_on_bake')
    layout.separator()
    layout.operator('mch.cut_finalize', text='Apply Live Cut (selected cutter)', icon='CHECKMARK')


def draw_library(layout, context):
    s = context.scene.mch_settings
    layout.prop(s, 'library_path')
    layout.prop(s, 'asset_name')
    row = layout.row(align=True)
    op = row.operator('mch.save_asset', text='Save Mesh', icon='MESH_CUBE')
    op.kind = 'MESH'
    op = row.operator('mch.save_asset', text='Save Curve Section', icon='CURVE_BEZCIRCLE')
    op.kind = 'PROFILE'
    layout.prop(s, 'mesh_preset')
    layout.operator('mch.insert_asset', text='Insert Mesh from Library', icon='IMPORT')
    layout.prop(s, 'profile_preset')
    _hint(layout, 'Saved as individual .blend files', 'FBX / Asset Browser cutters: not implemented')


def draw_remesh(layout, context):
    s = context.scene.mch_settings
    layout.operator('mch.sculpt_move', icon='BRUSH_DATA')
    layout.separator()
    layout.prop(s, 'join_remesh')
    layout.prop(s, 'voxel_size')
    row = layout.row(align=True)
    row.prop(s, 'smooth_iterations')
    row.prop(s, 'smooth_factor')
    layout.prop(s, 'apply_remesh')
    if s.apply_remesh:
        layout.prop(s, 'apply_existing')
    layout.operator('mch.one_click_remesh', text='REMESH + SMOOTH', icon='MOD_REMESH')
    _hint(layout, 'Voxel remesh loses UVs / attributes')


def draw_pose(layout, context):
    box = layout.box()
    box.label(text='NOT IMPLEMENTED in v0.7.0', icon='ERROR')
    _hint(box, 'Rigid / Soft Pose is on the P2 backlog.', 'Available now: Sculpt Move brush')
    layout.operator('mch.sculpt_move', icon='BRUSH_DATA')


DRAWERS = {
    'CUT': draw_cut, 'SPLIT': draw_split, 'BOOLEAN': draw_boolean, 'FUSE': draw_fuse,
    'MASK': draw_mask, 'DRAW': draw_draw, 'ARRAY': draw_array, 'EDIT': draw_edit,
    'LIBRARY': draw_library, 'REMESH': draw_remesh, 'POSE': draw_pose,
    # MIRROR, RADIAL, SURFACE: own sub-panels.
}
