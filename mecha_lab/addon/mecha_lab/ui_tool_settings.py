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
    if shape == 'STROKE' and mode == 'MASK':
        name = 'Free Draw (open brush stroke)'
    elif shape == 'STROKE':
        name = 'Free Draw (closed outline)'
    box = _section(layout, 'Shape: ' + name + '  (palette top-left / RMB)', 'SELECT_SET')
    col = box.column(align=True)
    if shape in {'CIRCLE', 'ELLIPSE'}:
        col.prop(brush, 'circle_segments')
    elif shape == 'CURVE_LASSO':
        col.prop(brush, 'curve_resolution')
        col.prop(brush, 'curve_smoothness', slider=True)
        _hint(box, 'Smooth spline through every click', 'Click a point: sharp <-> smooth',
              'Drag a point or its Bezier handle', 'Double-click anywhere: close & apply')
    elif shape == 'STROKE':
        if mode != 'MASK':
            sb = box.box()
            sb.prop(brush, 'stab_enable')
            sc = sb.column(align=True)
            sc.active = brush.stab_enable
            sc.prop(brush, 'stab_strength', slider=True)
            sc.prop(brush, 'stab_radius', slider=True)
            sc.prop(brush, 'stab_guide')
        col.prop(brush, 'stroke_spacing')
        col.prop(brush, 'stroke_smooth')
        col.prop(brush, 'stroke_simplify')
        if mode == 'MASK':
            col.prop(brush, 'mask_brush_radius')
            _hint(box, 'Hold LMB and paint; faces under the brush path')
        else:
            _hint(box, 'Hold LMB and draw; release closes the outline')
    elif shape == 'LASSO':
        if mode not in {'MASK', 'BASE'}:
            col.prop(brush, 'line_open')
        _hint(box, 'Click points, hold LMB to draw freely', 'Double-click anywhere: close & apply',
              '2 points + Enter = straight line cut (Cut/Split)')
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
        _hint(box, 'Click = stamp at Stamp Radius, drag = size')
    if shape in {'LASSO', 'RECT'}:
        sub = box.column(align=True)
        sub.label(text='Outline corners (2D shape, not the 3D edge):')
        sub.row(align=True).prop(brush, 'outline_corner', expand=True)
        if brush.outline_corner != 'NONE':
            sub.prop(brush, 'outline_radius')
            if brush.outline_corner == 'ROUND':
                sub.prop(brush, 'outline_segments')


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

    if mode == 'SPLIT':
        box = _section(layout, 'Split', 'MOD_EDGESPLIT')
        box.row(align=True).prop(cut, 'split_mode', expand=True)
        if cut.split_mode == 'GAP':
            box.prop(cut, 'gap_width')
            if not s.auto_apply:
                box.label(text='Gap Split needs Auto Apply ON', icon='ERROR')
        box = _section(layout, 'Cut edge finish per side (new edges only)', 'MOD_BEVEL')
        if not cut.split_cap:
            box.label(text='Needs Cap Split ON', icon='INFO')
        for side, label in (('a', 'Side A (original object)'), ('b', 'Side B (new _Split part)')):
            sub = box.column(align=True)
            sub.label(text=label)
            sub.row(align=True).prop(cut, f'side_{side}_finish', expand=True)
            if getattr(cut, f'side_{side}_finish') != 'NONE':
                sub.prop(cut, f'side_{side}_width')
                if getattr(cut, f'side_{side}_finish') == 'BEVEL':
                    sub.prop(cut, f'side_{side}_segments')
        box.operator('mch.split_swap_sides', icon='ARROW_LEFTRIGHT')
        if cut.side_a_finish != 'NONE' or cut.side_b_finish != 'NONE':
            box.prop(cut, 'finish_clamp')
    else:
        box = _section(layout, 'Edge Finish (new cut edges only)', 'MOD_BEVEL')
        box.prop(cut, 'edge_finish', expand=True)
        if cut.edge_finish != 'NONE':
            c = box.column(align=True)
            c.prop(cut, 'finish_width')
            if cut.edge_finish == 'BEVEL':
                c.prop(cut, 'finish_segments')
                c.prop(cut, 'finish_profile', slider=True)
            box.prop(cut, 'finish_clamp')
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
        _hint(layout, 'LMB draw: remove inside | Alt: keep inside',
              'Double-click anywhere / click start point / Enter: apply',
              'Esc: back to Select | Select / Move: W (or Mecha menu)',
              'Ctrl+Z: undo last point, then last cut', 'RMB: shapes | RMB double-click: exit tool',
              'PNG shape: R / Shift+R rotates 15°', 'All selected meshes are cut (Targets: Selected)')
    else:
        _hint(layout, 'LMB draw: split into two parts', 'Inside becomes "<name>_Split"',
              'Double-click anywhere / click start point / Enter: apply',
              'Esc: back to Select | Select / Move: W', 'RMB: shapes | RMB double-click: exit tool')


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
    from . import boolean_roles
    cutter, targets = boolean_roles(context)
    box = layout.box()
    box.label(text='CUTTER: ' + (cutter.name + '  (active, yellow)' if cutter else '-'), icon='MOD_BOOLEAN')
    box.label(text=f'TARGETS: {len(targets)} other selected mesh(es)', icon='MESH_DATA')
    if cutter is None or not targets:
        box.label(text='Select targets, then the cutter LAST', icon='ERROR')
    _hint(layout, 'Active (yellow) = cutter, applied to every other selected mesh',
          'B: Difference (MECHA LAB workspace only)')


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
    from . import fuse_pending_elsewhere
    pending = fuse_pending_elsewhere(context)
    if pending is not None:
        box = layout.box()
        box.label(text='Unconfirmed preview on: ' + pending.name, icon='INFO')
        box.label(text='Select it to Confirm / Cancel (a new fuse is possible)')
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


def _live_curve_carrier(context):
    ob = context.active_object
    if ob is None:
        return None
    if ob.get('mch_path'):
        ob = bpy.data.objects.get(ob.get('mch_carrier', ''))
    if ob is not None and ob.get('mch_role') in {'PANEL', 'CURVE', 'ARRAY'}:
        return ob
    return None


def draw_live_curve_controls(layout, context):
    """Live Mesh Curve settings of the selected result (sweep or curve array)."""
    carrier = _live_curve_carrier(context)
    if carrier is None:
        return
    p = carrier.mch_live
    box = _section(layout, 'LIVE: ' + carrier.name, 'CURVE_BEZCURVE')
    row = box.row(align=True)
    row.operator('mch.path_handles_all', text='All Smooth', icon='HANDLE_AUTO').kind = 'AUTO'
    row.operator('mch.path_handles_all', text='All Straight', icon='HANDLE_VECTOR').kind = 'VECTOR'
    col = box.column(align=True)
    col.prop(p, 'resolution')
    if carrier.get('mch_role') in {'PANEL', 'CURVE'}:
        col.prop(p, 'shape')
        if p.shape == 'ROUND':
            col.prop(p, 'profile_segments')
        if p.shape == 'CUSTOM':
            col.prop(p, 'custom_profile')
        col.prop(p, 'width')
        col.prop(p, 'depth')
    else:
        col.prop(p, 'spacing')
        col.prop(p, 'array_scale')
    col = box.column(align=True)
    col.prop(p, 'rot_x')
    col.prop(p, 'rot_y')
    col.prop(p, 'rot_z')
    col.prop(p, 'twist')
    _hint(box, 'Tab on the path: click/double-click a point = Smooth <-> Straight')
    box.operator('mch.bake_live', text='CONFIRM / APPLY', icon='CHECKMARK')


def draw_draw(layout, context):
    s = context.scene.mch_settings
    layout.prop(s, 'path_draw_mode', expand=True)
    layout.prop(s, 'path_point_type', expand=True)
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
    _hint(layout, 'Free: LMB drag (smooth) | Polyline: LMB points', 'Click/double-click a point: Smooth <-> Straight',
          'S: new point type | Shift+click: 45° | Enter/RMB: finish')
    draw_live_curve_controls(layout, context)


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
    layout.prop(s, 'path_point_type', expand=True)
    _hint(layout, 'Path edit: G move / V handles')
    draw_live_curve_controls(layout, context)


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
    from . import deform_tools
    deform_tools.draw(layout, context)


def draw_base(layout, context):
    from . import base_mesh
    ob = base_mesh.active_live_base(context)
    if ob is not None:
        p = ob.mch_base
        box = _section(layout, 'LIVE: ' + ob.name, 'MESH_CUBE')
        if p.last_error:
            box.label(text=p.last_error, icon='ERROR')
        target = box
    else:
        p = context.scene.mch_base
        target = layout
        layout.label(text='Settings for the next shape', icon='MESH_CUBE')
    target.row(align=True).prop(p, 'profile', expand=True)
    col = target.column(align=True)
    col.prop(p, 'height')
    if p.profile == 'DOME':
        col.prop(p, 'wall')
        col.prop(p, 'roundness', slider=True)
        col.prop(p, 'resolution')
    elif p.profile in {'BEVEL', 'CHAMFER'}:
        target.row(align=True).prop(p, 'bevel_sides', expand=True)
        if p.bevel_sides != 'NONE':
            col = target.column(align=True)
            both = p.bevel_sides == 'BOTH'
            col.prop(p, 'bevel_width', text='Top Width' if both and not p.bevel_link else 'Width')
            if p.profile == 'BEVEL':
                col.prop(p, 'bevel_segments', text='Top Segments' if both and not p.bevel_link else 'Segments')
            if both:
                col.prop(p, 'bevel_link')
                if not p.bevel_link:
                    col.prop(p, 'bevel_width_bottom')
                    if p.profile == 'BEVEL':
                        col.prop(p, 'bevel_segments_bottom')
        col = target.column(align=True)
    if p.profile == 'DOME':
        target.label(text='Dome: Bevel Sides not used (the top is the bulge)', icon='INFO')
    elif p.profile == 'FLAT':
        target.label(text='Flat: no bevel (choose Bevel / Chamfer for Bevel Sides)', icon='INFO')
    col.prop(p, 'offset')
    if ob is not None:
        target.operator('mch.base_freeze', icon='FREEZE')
    draw_shape_options(layout, context, 'BASE')
    _hint(layout, 'Draw: creates a NEW object', 'Alt + draw: cut it INTO the mesh below (Boolean),',
          '  bevel sides flipped (Top <-> Bottom)', 'Placed on the surface under the shape, else 3D cursor',
          'Leaving the tool (Esc / other tool / other tab)', '  applies only the shapes made in this session',
          'RMB: profiles | RMB x2: exit tool')


def draw_loft(layout, context):
    from . import loft_surface
    ob = loft_surface._active_loft(context)
    p = ob.mch_loft if ob is not None else context.scene.mch_loft
    row = layout.row(align=True)
    row.scale_y = 1.3
    row.operator('mch.loft_create', icon='SURFACE_DATA')
    row.operator('mch.sweep_create', icon='CURVE_PATH')
    _hint(layout, 'Loft: select 2+ curves (active = first)', 'Sweep: profile + path (active = path)')
    if ob is not None:
        box = _section(layout, ('LIVE: ' if p.live else '') + ob.name, 'SURFACE_DATA')
        err = ob.get('mch_loft_error')
        if err:
            box.label(text=err, icon='ERROR')
        if p.mode == 'LOFT':
            for i, e in enumerate(p.curves):
                r = box.row(align=True)
                r.prop(e, 'curve', text=str(i + 1))
                r.prop(e, 'reverse', text='', icon='ARROW_LEFTRIGHT')
                op = r.operator('mch.loft_move', text='', icon='TRIA_UP')
                op.index, op.direction = i, -1
                op = r.operator('mch.loft_move', text='', icon='TRIA_DOWN')
                op.index, op.direction = i, 1
        else:
            box.prop(p, 'profile')
            box.prop(p, 'path')
        target = box
    else:
        target = layout.box()
        target.label(text='Defaults for new surfaces')
    col = target.column(align=True)
    col.prop(p, 'samples')
    col.prop(p, 'segments')
    if p.mode == 'LOFT':
        col.prop(p, 'smoothness', slider=True)
        col.prop(p, 'auto_align')
        col.prop(p, 'twist')
        col.prop(p, 'close_loft')
    else:
        col.prop(p, 'sweep_scale')
        col.prop(p, 'sweep_twist')
    col.prop(p, 'thickness')
    col.prop(p, 'cap_ends')
    col.prop(p, 'flip_normals')
    if ob is not None:
        row = target.row(align=True)
        row.operator('mch.loft_rebuild', icon='FILE_REFRESH')
        row.operator('mch.loft_apply', icon='CHECKMARK')
    _hint(layout, 'NURBS-like interpolated mesh, not CAD NURBS patches')


def draw_zbrush(layout, context):
    from . import zbrush_bridge
    s = context.scene.mch_zbrush
    row = layout.row(align=True)
    row.scale_y = 1.4
    row.operator('mch.zbrush_send', icon='EXPORT')
    row.operator('mch.zbrush_import', icon='IMPORT')
    layout.operator('mch.zbrush_open_folder', icon='FILE_FOLDER')
    col = layout.column(align=True)
    col.prop(s, 'exchange_dir')
    col.prop(s, 'zbrush_exe')
    col.prop(s, 'scale')
    row = col.row(align=True)
    row.prop(s, 'forward_axis')
    row.prop(s, 'up_axis')
    col.prop(s, 'apply_modifiers')
    col.prop(s, 'keep_backup')
    col.prop(s, 'import_all')
    rows = zbrush_bridge.manifest_rows(s)
    if rows:
        box = _section(layout, 'Sent objects', 'OUTLINER')
        for name, fname, state in rows[:20]:
            box.label(text=f'{name}  [{state}]', icon='CHECKMARK' if state == 'CHANGED' else 'DOT')
    goz = zbrush_bridge.detect_goz()
    _hint(layout, 'OBJ bridge, NOT GoZ' + (f' (GoZ found: {goz}, unused)' if goz else ''),
          'Each object = its own OBJ (no auto Join)', 'ZBrush: Tool > Import, work,',
          'then Tool > Export to the SAME file', 'Back here: Import Back')


def draw_subd(layout, context):
    from . import subd_plane
    ob = subd_plane.active_subd(context)
    row = layout.row()
    row.scale_y = 1.4
    row.operator('mch.subd_plane_create', icon='MESH_PLANE')
    if ob is None:
        p = context.scene.mch_subd
        target = layout.box()
        target.label(text='Settings for the next plane')
        target.prop(p, 'size')
        act = context.active_object
        if act is not None and act.type == 'MESH':
            layout.operator('mch.subd_adopt', icon='MODIFIER')
    else:
        p = ob.mch_subd
        target = _section(layout, 'LIVE: ' + ob.name, 'MOD_SUBSURF')
    col = target.column(align=True)
    col.prop(p, 'simple_levels', slider=True)
    col.prop(p, 'cc_levels', slider=True)
    col = target.column(align=True)
    col.prop(p, 'thickness')
    col.prop(p, 'offset', slider=True)
    col.prop(p, 'even_thickness')
    col.prop(p, 'use_creases')
    box = _section(layout, 'Edge Crease (Edit Mode)', 'EDGESEL')
    box.prop(context.scene.mch_subd, 'crease_value', slider=True)
    box.operator('mch.subd_set_crease', icon='EDGESEL')
    if ob is not None:
        row = layout.row()
        row.scale_y = 1.3
        row.operator('mch.subd_apply_all', icon='CHECKMARK')
    _hint(layout, 'Simple and Catmull-Clark work together (two sliders)', 'Tab: Edit Mode, E: extrude edges',
          'Order: Simple -> Catmull-Clark -> Solidify')


def draw_primitive(layout, context):
    from . import primitive_tools as prim
    ob = prim.active_primitive(context)
    p = ob.mch_primitive if ob is not None else context.scene.mch_primitive
    box = layout.box()
    box.label(text='PARAMETRIC PRIMITIVES', icon='GEOMETRY_NODES')
    row = box.row(align=True)
    row.scale_y = 1.3
    row.operator('mch.primitive_create', text='New Box', icon='MESH_CUBE').kind = 'BOX'
    row.menu('MCH_MT_primitive_picker', text='Shape Picker (RMB)', icon='DOWNARROW_HLT')
    if ob is not None:
        box.label(text='LIVE: ' + ob.name, icon='GEOMETRY_NODES')
        box.prop(p, 'kind', text='Shape')
    else:
        box.label(text='Settings for new primitives')
    col = box.column(align=True)
    if p.kind == 'BOX':
        col.label(text='BOTTOM FACE')
        row=col.row(align=True);row.prop(p,'bottom_x');row.prop(p,'bottom_y')
        col.label(text='TOP FACE')
        row=col.row(align=True);row.prop(p,'top_x');row.prop(p,'top_y')
        col.prop(p,'height')
    elif p.kind in {'CYLINDER','CONE'}:
        col.prop(p,'height')
        col.prop(p,'radius_top')
        col.prop(p,'radius_bottom')
        col.prop(p,'segments')
    elif p.kind == 'SPHERE':
        col.prop(p,'radius');col.prop(p,'segments');col.prop(p,'rings')
    elif p.kind == 'CAPSULE':
        col.prop(p,'radius');col.prop(p,'length');col.prop(p,'segments');col.prop(p,'rings')
        if p.length < 2*p.radius:
            col.label(text='Min total length = 2 x radius', icon='INFO')
    if p.kind in {'BOX','CYLINDER','CONE'}:
        hole=layout.box()
        hole.prop(p,'hole_enabled',text='Central Through Hole (Z)')
        if p.hole_enabled:
            hole.prop(p,'hole_radius')
            row=hole.row(align=True)
            row.prop(p,'hole_offset_x');row.prop(p,'hole_offset_y')
            hole.label(text='Use radius smaller than the solid cross-section',icon='INFO')
    edge=layout.box()
    edge.label(text='EDGE FINISH',icon='MOD_BEVEL')
    edge.prop(p,'bevel_width')
    edge.prop(p,'bevel_segments')
    if ob is not None:
        row=layout.row();row.scale_y=1.3
        row.operator('mch.primitive_apply',text='APPLY TO MESH',icon='CHECKMARK')
    _hint(layout,'Geometry Nodes shape + Blender Bevel modifier',
          'RMB inside MECHA LAB Primitive tool = shape picker',
          'Change parameters live; Apply when finished')



def draw_extract(layout, context):
    from . import face_extract
    face_extract.draw(layout, context)


def draw_molding(layout, context):
    from . import edge_molding
    edge_molding.draw(layout, context)


def draw_hollow(layout, context):
    from . import hollow_shell
    hollow_shell.draw(layout, context)


def draw_along(layout, context):
    from . import along_curve
    along_curve.draw(layout, context)


def draw_cable(layout, context):
    from . import cable
    cable.draw(layout, context)


DRAWERS = {
    'CUT': draw_cut, 'SPLIT': draw_split, 'BOOLEAN': draw_boolean, 'FUSE': draw_fuse,
    'MASK': draw_mask, 'DRAW': draw_draw, 'ARRAY': draw_array, 'EDIT': draw_edit,
    'LIBRARY': draw_library, 'REMESH': draw_remesh, 'POSE': draw_pose,
    'BASE': draw_base, 'LOFT': draw_loft, 'ZBRUSH': draw_zbrush, 'SUBD': draw_subd,
    'PRIMITIVE': draw_primitive,
    'EXTRACT': draw_extract, 'MOLDING': draw_molding, 'HOLLOW': draw_hollow, 'ALONG': draw_along,
    'CABLE': draw_cable,
    # MIRROR, RADIAL, SURFACE: own sub-panels.
}
