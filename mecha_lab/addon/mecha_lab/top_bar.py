"""0.24.59 Top bar: what the drawing tools share, big and clear at the top middle of the viewport (it replaces the
shape / Sketch / Line / Surface ... buttons of Blender's tool header, which keeps only the Custom PNG picker).

    SHAPE [lasso][curve][rect][circle][ellipse][free][custom]  |  LASSO (the shape's own options)  |  CORNERS
    [Sharp][Round][Chamfer] (Width) (Segments)  |  DRAW [Line] [Sketch] [Slow Line] (Strength) (Radius)  |  LINE
    (Width) [Caps v] [Taper] (Taper) [Pressure] [Attach Ends]  |  [Surface] (Gap) [Through] [Sim] [Preset v]  |
    TARGET [Auto] [Selected] [Active]  |  DEPTH [Through All] [From Surface] (Depth)  |  [Auto Apply]  |  GN EDGE /
    EDGE FINISH / SIDE A · B / EDGE (the cut edge's bevel)  |  [Ortho]

0.24.78 every lasso setting sits here, in the same place for every drawing tool (right after the shapes), and the
bevel of the new cut edges (Cut / Split GN Edge, Edge Finish, Split per side; Base Mesh edge bevel) too.

Only what the tool in use has; groups wrap to a second / third row when the room between the tool strip and the
side panel is too narrow.  The tool's own settings are in the side panel (``side_panel``), which leaves these out.
"""
from __future__ import annotations

import collections
import math

from . import i18n
from . import tool_state as ts

ROW = 30.0
ICON = 34.0
GAP = 5.0
PAD = 8.0
TOP = 10.0
CUT_LIKE = {'CUT', 'SPLIT', 'HIDE'}


def _cell(kind, label, on=False, action=None, data=None, prop='', width=None, icon=''):
    return {'kind': kind, 'label': label, 'on': on, 'action': action, 'data': data, 'prop': prop,
            'width': width, 'icon': icon}


def _seg(label, data, prop, on=None):
    return _cell('seg', label, bool(getattr(data, prop)) if on is None else on, ('bool',), data, prop)


RES_TOOLS = (ts.SHAPE_TOOLS - {'ZONE'}) | {'SCREW', 'PERF', 'SUBD'}     # (0.24.95 a zone makes no geometry to resolve)


def groups(context, tool):
    """[(title, [cells])] for the tool in use."""
    from . import lasso_line, lasso_sketch, mecha_menu, target_rules
    scene = context.scene
    brush = getattr(scene, 'mch_brush', None)
    out = []
    if brush is None:
        return out
    if tool in ts.SHAPE_TOOLS:
        out.append(('Shape', [_cell('ibtn', label, brush.shape == sid, ('shape', sid), icon='png:' + stem,
                                    width=ICON) for sid, label, _d, stem, _f in ts.SHAPES]))
    if tool in ts.SHAPE_TOOLS:
        out += lasso_groups(brush, tool)
    if tool in {'GREEBLE', 'CGREEBLE'}:   # 0.24.154 Greeble / Scale Line: Shift + draw a part with the shared shapes
        out.append(('Shift+Draw', [_cell('ibtn', label, brush.shape == sid or (sid == 'STROKE' and brush.shape == 'CUSTOM'),
                                         ('shape', sid), icon='png:' + stem, width=ICON)
                                   for sid, label, _d, stem, _f in ts.SHAPES if sid != 'CUSTOM']))
        out += lasso_groups(brush, tool) if brush.shape != 'CUSTOM' else []
    if tool == 'ZONE' and hasattr(scene, 'mch_zone_kind'):        # 0.24.95 Lasso Zone: what it makes
        out.append(('Zone', _enum_segs(scene, 'mch_zone_kind', (('PAINT', 'Paint'), ('SPLIT', 'Split')))))
    if tool in RES_TOOLS and hasattr(scene, 'mch_settings'):       # 0.24.95 one Resolution for all made / cut shapes
        out.append(('Resolution', [_mini('Res', scene.mch_settings, 'geo_res', 120),
                                   _cell('seg', 'Apply to Parts', action=('op', 'mch.apply_resolution', {}))]))
    draw = [_cell('seg', label, on, ('mode', key)) for key, label, on in mecha_menu.draw_modes(context)]
    drawing = tool in target_rules.PICKING | target_rules.OWN_ROW - target_rules.MOVE_TOOLS
    if drawing:
        draw.append(_seg('Slow Line', brush, 'stab_enable'))
        if brush.stab_enable:
            draw.append(_cell('mini', 'Strength', action=('number',), data=brush, prop='stab_strength', width=150))
            draw.append(_cell('mini', 'Radius', action=('number',), data=brush, prop='stab_radius', width=130))
    if draw:
        out.append(('Draw', draw))
    line_tool = tool in lasso_line.MODES or tool in lasso_line.ALWAYS
    if line_tool and (brush.line_mode or tool in lasso_line.ALWAYS):
        sd = getattr(scene, 'mch_sdraw', None) if tool == 'SDRAW' else None
        if sd is not None:                     # 0.24.143 Surface Draw: its own Ends (live: every band rebuilds)
            line = [_cell('mini', 'Width', action=('number',), data=brush, prop='line_width', width=140),
                    _cell('drop', '', action=('menu_enum',), data=sd, prop='ends', width=110)]
            if sd.ends == 'POINT':
                line.append(_cell('mini', 'Taper', action=('number',), data=sd, prop='taper', width=120))
        else:
            line = [_cell('mini', 'Width', action=('number',), data=brush, prop='line_width', width=140),
                    _cell('drop', '', action=('menu_enum',), data=brush, prop='line_caps', width=110)]
            if brush.line_caps != 'POINT':
                line.append(_seg('Taper', brush, 'line_taper_on'))
            if brush.line_caps == 'POINT' or brush.line_taper_on:
                line.append(_cell('mini', 'Taper', action=('number',), data=brush, prop='line_taper', width=120))
        line.append(_seg('Pressure', brush, 'line_pressure'))
        line.append(_seg('Area', brush, 'line_area'))          # 0.24.108 the enclosed region as the shape
        if tool in {'BASE', 'CBASE'}:
            from . import base_mesh
            bd = base_mesh.scene_defaults(context)
            line.append(_seg('Attach Ends', bd, 'line_attach'))
            if bd.line_attach:
                line.append(_cell('drop', '', action=('menu_enum',), data=bd, prop='attach_curve', width=104))
        out.append(('Line', line))
    extra = []
    if tool in {'CUT', 'SPLIT', 'PLATE', 'WRINKLE', 'CDRAPE', 'ZONE', 'PCUT'}:
        extra.append(_seg('Surface', brush, 'surface_mode'))
        if brush.surface_mode and tool in {'CUT', 'SPLIT', 'PCUT'}:
            extra.append(_cell('mini', 'Gap', action=('number',), data=brush, prop='surface_gap', width=110))
    if tool in {'PLATE', 'WRINKLE', 'CPLATE', 'ZONE'}:       # (0.24.95 Lasso Zone: the back faces too)
        extra.append(_seg('Through', brush, 'through_mode'))
        if brush.through_mode and tool not in {'CPLATE', 'ZONE'}:
            extra.append(_cell('mini', 'Crease', action=('number',), data=brush, prop='through_crease', width=120))
    if tool == 'WRINKLE' and hasattr(scene, 'mch_wrinkle'):
        ws = scene.mch_wrinkle
        extra.append(_seg('Sim', ws, 'sim_after'))
        if ws.sim_after:
            extra.append(_cell('drop', '', action=('menu_enum',), data=ws, prop='sim_preset', width=110))
    if extra:
        out.append(('', extra))
    if tool == 'PLATE' and ts.mold_on(context):
        # 0.24.298 Top / Bottom Edge Molding (0.24.305 Mold Armor Plate only): the live plate's, else the next plates'
        from . import armor_plate as ap_
        lp = ap_.pending_plate(context)
        pp = lp.mch_extract if lp is not None else getattr(scene, 'mch_extract', None)
        if pp is not None and hasattr(pp, 'emold_top'):
            out.append(edge_molding_group(pp))
        if hasattr(scene, 'mch_moldcut'):
            out.append(mold_cut_group(scene.mch_moldcut))         # 0.24.304
    if tool == 'ACUT' and hasattr(scene, 'mch_acut'):
        # 0.24.297 Array Cut: the guide (Shift + draw) and the array - live after the cut
        from . import array_cut
        ac_ = scene.mch_acut
        out.append(('Guide', _enum_segs(ac_, 'guide', (('LINE', 'Line'), ('FREE', 'Free'), ('CIRCLE', 'Circle'),
                                                        ('BOX', 'Box')))))
        cells = [_mini('Count', ac_, 'count', 110), _mini('Spacing', ac_, 'spacing', 140),
                 _mini('End Size', ac_, 'end_scale', 140), _seg('Align', ac_, 'align')]
        if array_cut.record(scene) is not None:
            cells.append(_cell('seg', 'Apply', action=('op', 'mch.array_cut_apply', {})))
        out.append(('Array', cells))
    if tool == 'BASE' and ts.mold_on(context):          # 0.24.305 (Mold Base Mesh only)
        # 0.24.295 (user: "만든 모양대로 옆면 쪽에 몰딩처럼 튀어나오게, 두께랑 개수 정할 수 있게") in the tool's own box (the
        # LASSO block keeps its size: its cells stay where they are for every tool)
        from . import base_mesh
        ob_ = base_mesh.active_live_base(context)
        bp = ob_.mch_base if ob_ is not None else base_mesh.scene_defaults(context)
        if bp is not None and hasattr(bp, 'mold_count') and bp.profile in {'FLAT', 'BEVEL', 'CHAMFER'}:
            cells = [_mini('Count', bp, 'mold_count', 110)]
            if bp.mold_count > 0:
                cells += [_mini('Thickness', bp, 'mold_thick', 150), _mini('Width', bp, 'mold_width', 130)]
                cells += _enum_segs(bp, 'mold_shape', (('SQUARE', 'Square'), ('CHAMFER', 'Chamfer'),
                                                       ('ROUND', 'Round')))
            out.append(('Side Molding', cells))
            out.append(edge_molding_group(bp))                    # 0.24.298
        if hasattr(scene, 'mch_moldcut'):
            out.append(mold_cut_group(scene.mch_moldcut, context))   # 0.24.304 (0.24.323 the Alt check)
    pst = getattr(scene, 'mch_plate', None)
    if tool == 'PLATE' and pst is not None and hasattr(pst, 'carve_floor'):
        # 0.24.291 (user: "옆에 세팅에 플렛 팔로우 레벨 버튼 만들면 되것네") Alt + draw (the carve): floor and depth
        out.append(('Alt Carve', _enum_segs(pst, 'carve_floor', (('FOLLOW', 'Follow'), ('LEVEL', 'Level'),
                                                                 ('FLAT', 'Flat')))
                    + [_cell('mini', 'Depth', action=('number',), data=pst, prop='carve_depth', width=130),
                       # 0.24.295 (user: "프레스 컷처럼 대각선으로 잘리는 버튼") the walls slant in
                       _cell('mini', 'Wall Angle', action=('number',), data=pst, prop='carve_wall', width=150),
                       # 0.24.296 (user: "바닥 쪽에 계단처럼 한 단 더") the stepped floor
                       _cell('mini', 'Steps', action=('number',), data=pst, prop='carve_steps', width=110)]
                    + ([_cell('mini', 'Step In', action=('number',), data=pst, prop='step_inset', width=130),
                        _cell('mini', 'Step Depth', action=('number',), data=pst, prop='step_depth', width=150)]
                       if pst.carve_steps > 0 else [])))
    if tool == 'PRESS' and hasattr(scene, 'mch_press'):          # 0.24.95 Press Cut: the stamp and how it presses
        pr = scene.mch_press
        # (user: "원래 쓰던 라쏘랑 스케치 다 넣어 줘") Shift + draw: the stamp drawn with the shared shapes
        lasso_on = getattr(pr, 'draw_mode', 'LINE') == 'LASSO'          # 0.24.122 the shapes draw the lasso itself
        out.insert(0, ('Shape' if lasso_on else 'Shift+Draw',
                       [_cell('ibtn', label, brush.shape == sid or (sid == 'STROKE' and brush.shape == 'CUSTOM'),
                              ('shape', sid), icon='png:' + stem, width=ICON)
                        for sid, label, _d, stem, _f in ts.SHAPES if sid != 'CUSTOM']))
        out[1:1] = lasso_groups(brush, tool) if brush.shape != 'CUSTOM' else []
        # 0.24.122 (user: "프레스 컷에 라쏘 모드도") Line = the stamp swept along a drag, Lasso = the Base Mesh tool's lasso
        # - at the front of the one Draw group (0.24.123: a second group named Draw hid the first one's Sketch / Slow Line)
        mode_segs = _enum_segs(pr, 'draw_mode', (('LINE', 'Line'), ('LASSO', 'Lasso')))
        i_draw = next((i for i, g in enumerate(out) if g[0] == 'Draw'), None)
        if i_draw is None:
            out.append(('Draw', mode_segs))
        else:
            out[i_draw] = ('Draw', mode_segs + list(out[i_draw][1]))
        out.append(('Floor', _enum_segs(pr, 'floor_mode', (('FOLLOW', 'Follow'), ('LEVEL', 'Level'), ('FLAT', 'Flat')))))
        out.append(('Press', _enum_segs(pr, 'result', (('CUT', 'Cut'), ('SPLIT', 'Split'))) + [
            (_cell('seg', 'Drawn', True, ('enum', False), pr, 'drawn') if pr.drawn else
             _cell('seg', pc_shape_name(pr) + '  \u25be', False, ('op', 'mch.press_shape_grid', {}), width=170)),
                                                       # (0.24.95 the stamps as pictures, not a list of names)
            _cell('mini', 'Size', action=('number',), data=pr, prop='size', width=110),
            _cell('mini', 'Dots', action=('number',), data=pr, prop='dot_size', width=100),
            _cell('mini', 'Curve LR', action=('number',), data=pr, prop='curve_x', width=130),
            _cell('mini', 'Curve UD', action=('number',), data=pr, prop='curve_y', width=130),
            _cell('mini', 'Start', action=('number',), data=pr, prop='start', width=110),
            _cell('mini', 'Speed', action=('number',), data=pr, prop='speed', width=120),
            _cell('mini', 'Max', action=('number',), data=pr, prop='max_depth', width=100),
            _cell('mini', 'Wall Angle', action=('number',), data=pr, prop='wall_angle', width=150)]))
        # 0.24.124 (user: "프레스 컷에 플레이트 버튼 넣어 주라") Plate: press = the stamp as a plate, Line = its section
        # along the surface, Lasso = that plate tool's lasso
        out.append(('Plate', _enum_segs(pr, 'result', (('PLATE', 'Armor'), ('CPLATE', 'Creature')))))
        # 0.24.108 (user: "뺄 때 챔퍼랑 베벨 그리고 원형도") hold = Grow: the top edge of what grows out
        grow = _enum_segs(pr, 'grow_top', (('FLAT', 'Flat'), ('FOLLOW', 'Follow'))) + \
            _enum_segs(pr, 'grow_edge', (('SHARP', 'Sharp'), ('CHAMFER', 'Chamfer'), ('BEVEL', 'Bevel'),
                                         ('ROUND', 'Round')))
        if pr.grow_edge in {'CHAMFER', 'BEVEL'}:
            grow.append(_cell('mini', 'Edge', action=('number',), data=pr, prop='grow_edge_size', width=110))
        if pr.grow_edge == 'BEVEL':
            grow.append(_cell('mini', 'Segs', action=('number',), data=pr, prop='grow_edge_segments', width=100))
        out.append(('Grow', grow))
    if tool in {'CUT', 'SPLIT', 'PRESS'}:                          # 0.24.95 the last drawn outline -> a shape
        from . import cut_presets
        if cut_presets.LAST_LOOPS[0] is not None:
            out.append(('', [_cell('seg', 'Save Shape', action=('op', 'mch.save_cut_shape', {}))]))
    cut = getattr(scene, 'mch_cut', None)
    if cut is not None and (drawing or tool in target_rules.TARGET_ONLY):
        out.append(('Target', [_cell('seg', label, cut.targets == ident, ('enum', ident), cut, 'targets')
                               for ident, label in (('AUTO', 'Auto'), ('SELECTED', 'Selected'),
                                                    ('ACTIVE', 'Active'))]))
    if cut is not None and tool in CUT_LIKE:
        depth = [_cell('seg', label, cut.depth_mode == ident, ('enum', ident), cut, 'depth_mode')
                 for ident, label in (('THROUGH', 'Through All'), ('SURFACE', 'From Surface'))]
        if cut.depth_mode == 'SURFACE':
            depth.append(_cell('mini', 'Depth', action=('number',), data=cut, prop='depth', width=130))
            if tool in {'CUT', 'SPLIT'}:                   # 0.24.95 the floor: Follow / Level / Flat
                depth += _enum_segs(cut, 'depth_floor', (('FOLLOW', 'Follow'), ('LEVEL', 'Level'), ('FLAT', 'Flat')))
        out.append(('Depth', depth))
        st = getattr(scene, 'mch_settings', None)
        if st is not None and tool != 'HIDE':
            out.append(('', [_seg('Auto Apply', st, 'auto_apply')]))
    out += edge_groups(context, tool)
    out += concept_groups(context, tool)
    if tool == 'SMART':                                        # 0.24.123 Smart Move: turn / push / lift
        from . import smart_move
        out += smart_move.top_bar_groups(context, tool)
    from .workspace_ui import _ORTHO_LOCK_KEY
    locked = bool(context.workspace and context.workspace.get(_ORTHO_LOCK_KEY, False))
    out.append(('', [_cell('seg', 'Ortho', locked, ('op', 'mch.ortho_lock', {})),
                     # 0.24.225 (user: "옵션에 한글 영어 바꾸는 토글 버튼도 만들어 줘")
                     _cell('seg', LANG_LABEL, i18n.lang() == 'KO', ('op', 'mch.toggle_language', {}))]))
    return out



def mold_cut_group(mc, context=None):
    """0.24.304 ('Mold Cut', cells): on / off, and with it on: Bottom, Top, Out, Height, Lip Rim, Dome, the shape.
    0.24.323 with ``context`` (Mold Base Mesh): a button to Alt: Carve Height when Alt is something else (it would
    carve flat)."""
    cells = [_seg('Mold Cut', mc, 'on')]
    if context is not None:
        from . import mold_cut
        if mold_cut.wrong_alt(context, mc):
            cells.append(_cell('seg', 'Alt is not Carve Height: Use It', action=('op', 'mch.mold_cut_height', {})))
    if mc.on:
        cells += [_seg('Bottom', mc, 'emold_bottom'), _seg('Top', mc, 'emold_top'), _mini('Out', mc, 'emold_out', 110),
                  _mini('Height', mc, 'emold_band', 130)]
        if mc.emold_top:
            cells.append(_mini('Lip Rim', mc, 'emold_lip', 130))
        cells.append(_mini('Dome', mc, 'emold_dome', 110))
        cells += _enum_segs(mc, 'emold_shape', (('SQUARE', 'Square'), ('CHAMFER', 'Chamfer'), ('ROUND', 'Round'),
                                                ('SLOPE', 'Slope')))
    return ('Mold Cut', cells)


def edge_molding_group(p):
    """0.24.298 ('Edge Molding', cells): Top / Bottom, and with one on: Out, Height, Lip, the shape."""
    cells = [_seg('Top', p, 'emold_top'), _seg('Bottom', p, 'emold_bottom'),
             _mini('Top Dome', p, 'emold_dome', 140)]                # 0.24.299 (on its own too)
    if p.emold_top or p.emold_bottom:
        cells += [_mini('Out', p, 'emold_out', 110), _mini('Height', p, 'emold_band', 130)]
        if p.emold_top:
            cells.append(_mini('Lip Rim', p, 'emold_lip', 130))
        cells += _enum_segs(p, 'emold_shape', (('SQUARE', 'Square'), ('CHAMFER', 'Chamfer'), ('ROUND', 'Round'),
                                               ('SLOPE', 'Slope')))
    return ('Edge Molding', cells)

def pc_shape_name(pr):
    from . import press_cut
    try:
        return press_cut.shape_name(pr)
    except Exception:
        return 'Stamp'


def _mini(label, data, prop, width=130):
    return _cell('mini', label, action=('number',), data=data, prop=prop, width=width)


def _enum_segs(data, prop, items):
    v = getattr(data, prop)
    return [_cell('seg', label, v == ident, ('enum', ident), data, prop) for ident, label in items]


def lasso_groups(brush, tool):
    """0.24.78 LASSO = the drawn shape's own options, CORNERS = the 2D lasso's corners (Lasso / Rectangle) - they
    were in a folded Lasso section of the side panel."""
    shape = brush.shape
    cells = []
    if shape in {'CIRCLE', 'ELLIPSE'}:
        cells.append(_mini('Segments', brush, 'circle_segments', 140))
    elif shape == 'CURVE_LASSO':
        cells.append(_mini('Samples', brush, 'curve_resolution', 130))
    elif shape == 'STROKE':
        cells += [_mini('Spacing', brush, 'stroke_spacing', 130), _mini('Smooth', brush, 'stroke_smooth', 120),
                  _mini('Simplify', brush, 'stroke_simplify', 130)]
        if tool == 'MASK':
            cells.append(_mini('Radius', brush, 'mask_brush_radius', 130))
    elif shape == 'LASSO' and tool not in {'MASK', 'BASE', 'CBASE'}:
        cells.append(_seg('Open Line', brush, 'line_open'))
    elif shape == 'CUSTOM':
        cells += [_mini('Size', brush, 'custom_size', 130), _mini('Rotation', brush, 'custom_rotation', 140),
                  _seg('Rotate With Drag', brush, 'custom_drag_rotate')]
    out = [('Lasso', cells)] if cells else []
    if shape in {'LASSO', 'RECT'}:
        corners = _enum_segs(brush, 'outline_corner', (('NONE', 'Sharp'), ('ROUND', 'Round'), ('CHAMFER', 'Chamfer')))
        if brush.outline_corner != 'NONE':
            corners.append(_mini('Width', brush, 'outline_radius', 130))
            if brush.outline_corner == 'ROUND':
                corners.append(_mini('Segments', brush, 'outline_segments', 140))
        out.append(('Corners', corners))
    return out


FINISH3 = (('NONE', 'Off'), ('CHAMFER', 'Chamfer'), ('BEVEL', 'Bevel'))


def _finish(label, data, kind, width, segments, extra=()):
    """[Off][Chamfer][Bevel] (Width) (Segments on a bevel) for one finish enum."""
    cells = _enum_segs(data, kind, FINISH3)
    if getattr(data, kind) != 'NONE':
        cells.append(_mini('Width', data, width, 130))
        if getattr(data, kind) == 'BEVEL' and segments:
            cells.append(_mini('Segments', data, segments, 140))
        cells += list(extra)
    return (label, cells)


def edge_groups(context, tool):
    """0.24.78 the bevel of the new cut edges: Cut / Split GN Edge (+ Split sides), the Edge Finish under it when GN
    Edge is off (Split: per side), Base Mesh: its edge bevel."""
    scene = context.scene
    out = []
    cut = getattr(scene, 'mch_cut', None)
    if cut is not None and tool in {'CUT', 'SPLIT'}:
        extra = [_cell('drop', '', action=('menu_enum',), data=cut, prop='gn_sides', width=96)] if tool == 'SPLIT' else []
        out.append(_finish('GN Edge', cut, 'gn_finish', 'gn_width', 'gn_segments', extra))
        if cut.gn_finish == 'NONE':
            safe = [_seg('Clamp', cut, 'finish_clamp'), _seg('Crisp', cut, 'finish_crisp')]
            if tool == 'CUT':
                lbl, cells = _finish('Edge Finish', cut, 'edge_finish', 'finish_width', 'finish_segments')
                if cut.edge_finish == 'BEVEL':
                    cells.append(_mini('Profile', cut, 'finish_profile', 120))
                if cut.edge_finish != 'NONE':
                    cells += safe
                out.append((lbl, cells))
            else:
                for side in ('a', 'b'):
                    out.append(_finish(f'Side {side.upper()}', cut, f'side_{side}_finish', f'side_{side}_width',
                                       f'side_{side}_segments'))
                swap = [_cell('seg', '⇄ Swap', action=('op', 'mch.split_swap_sides', {}))]
                out.append(('', swap + (safe if cut.side_a_finish != 'NONE' or cut.side_b_finish != 'NONE' else [])))
    if tool == 'BASE':                           # (Creature Base Mesh: Puff / Ridge / Pillow, no edge bevel)
        from . import base_mesh
        ob = base_mesh.active_live_base(context)
        p = ob.mch_base if ob is not None else base_mesh.scene_defaults(context)
        if p is not None and hasattr(p, 'bevel_sides'):
            cells = [_cell('seg', label, p.profile == pid, ('op', 'mch.set_profile', {'profile': pid}))
                     for pid, label in (('FLAT', 'Flat'), ('CHAMFER', 'Chamfer'), ('BEVEL', 'Bevel'))]
            if p.profile in {'BEVEL', 'CHAMFER'}:
                # 0.24.212 (user: "위랑 아래 어디 할지 선택하는 게 마우스 대면 사라졌다가 꾹 누르고 있어야 나타나는 것도
                # 불편하니까 그냥 잘 나오게 해 주고 위아래 베벨 조절도 섬세하게"): the sides as buttons that are always
                # there (it was a closed list: a pop-up that went when the mouse moved), and with Both the top and
                # the bottom each their own Width / Segments beside it
                out.append(('Edge', cells))
                cells = _enum_segs(p, 'bevel_sides', (('TOP', 'Top'), ('BOTTOM', 'Bottom'), ('BOTH', 'Both'),
                                                      ('NONE', 'Off')))
                if p.bevel_sides != 'NONE':
                    both = p.bevel_sides == 'BOTH'
                    split = both and not p.bevel_link
                    if both:
                        cells.append(_seg('Same', p, 'bevel_link'))
                    out.append(('Sides', cells))       # (0.24.214 the numbers their own group: the row can break here)
                    cells = []
                    cells.append(_mini('Top W' if split else 'Width', p, 'bevel_width', 140))
                    if p.profile == 'BEVEL':
                        cells.append(_mini('Top Segs' if split else 'Segments', p, 'bevel_segments', 140))
                    if split:
                        cells.append(_mini('Bottom W', p, 'bevel_width_bottom', 150))
                        if p.profile == 'BEVEL':
                            cells.append(_mini('Bottom Segs', p, 'bevel_segments_bottom', 150))
                    out.append(('', cells))
                else:
                    out.append(('Sides', cells))
            else:
                out.append(('Edge', cells))
    return out


CONCEPT_TOOLS = {'CMOVE', 'CPATH', 'SMOVE'}


def concept_groups(context, tool):
    """0.24.79 Concept Move / Path Move / Silhouette Move: the brush settings that filled Blender's tool header
    (method, area, size, hardness, taper, turns, back mask, shape, mirror, generate, follow view) - here, in the
    Mecha bar; the side panel keeps the rest (cuts, knife, auto apply, moves)."""
    st = getattr(context.scene, 'mch_concept', None)
    if st is None or tool not in CONCEPT_TOOLS:
        return []
    out = []
    if tool == 'CPATH':
        method = [_cell('drop', '', action=('menu_enum',), data=st, prop='path_method', width=150)]
        if st.path_method == 'EXTEND':
            method += _enum_segs(st, 'path_area', (('BRUSH', 'Brush'), ('SECTION', 'Whole')))
        out.append(('Method', method))
    brush = [_mini('Size', st, 'radius_world' if st.lock_size else 'radius_px', 140), _seg('Real Size', st, 'lock_size')]
    if tool == 'CMOVE':
        if st.falloff == 'CLAY':
            brush.append(_mini('Hardness', st, 'hardness', 140))
        brush.append(_cell('drop', '', action=('menu_enum',), data=st, prop='falloff', width=110))
        brush.append(_mini('Strength', st, 'strength', 140))
    else:
        brush += [_mini('Hardness', st, 'path_hardness', 140), _mini('Taper', st, 'path_taper', 120),
                  _seg('Follow Turns', st, 'path_turn')]
        if tool == 'CPATH':
            brush.append(_seg('Back Mask', st, 'path_back_mask'))
    brush.append(_cell('drop', '', action=('menu_enum',), data=st, prop='shape', width=110))
    out.append(('Brush', brush))
    more = []
    ob = getattr(context, 'active_object', None)
    try:
        from . import concept_move
        own = ob is not None and concept_move.mirror_reflections(ob)
    except (ImportError, AttributeError, TypeError, ReferenceError):
        own = False
    if not own:                                   # (an object with its own Mirror: that one, nothing to pick)
        more.append(_seg('Mirror X', st, 'mirror_x'))
    more.append(_seg('Generate', st, 'keep_density'))
    if st.keep_density:
        more.append(_seg('Even Out', st, 'even_out'))
    more.append(_seg('Follow View', st, 'follow_view'))
    out.append(('', more))
    return out


def _width(c, k):
    if c['width']:
        return c['width'] * k
    return (i18n.vlen(c['label']) * 7.0 + 24.0) * k


def _group_width(title, cells, k):
    w = sum(_width(c, k) for c in cells) + GAP * k * (len(cells) - 1)
    if title:
        w += (i18n.vlen(title) * 7.0 + 8.0) * k + GAP * k
    return w


def rows_of(gs, room, k):
    """Groups in the fewest rows that fit ``room`` px (at most 3), split so the rows are about equally wide (a
    row with one lonely button looked odd)."""
    import itertools
    sep = 14.0 * k
    widths = [_group_width(t, c, k) for t, c in gs]

    def row_w(a, b):
        return sum(widths[a:b]) + sep * (b - a - 1)
    n = len(gs)
    for rows in (1, 2, 3):
        best = None
        for cuts in itertools.combinations(range(1, n), rows - 1):
            bounds = (0,) + cuts + (n,)
            w = max(row_w(a, b) for a, b in zip(bounds, bounds[1:]))
            if best is None or w < best[0]:
                best = (w, bounds)
        if best is not None and (best[0] <= room or rows == 3 or rows >= n):
            b = best[1]
            return [gs[x:y] for x, y in zip(b, b[1:])]
    return [gs]


def room(context, region_w, k):
    """(left, right) px the bar may use: right of the tool strip, left of the side panel (``items`` uses the whole
    width while the bar stays above the side panel's top)."""
    from . import ui_bars
    left = ui_bars.left_inset(context) + ui_bars.strip_width(context, k)
    right = 0.0
    try:
        from . import side_panel
        right = side_panel.taken(context, k)
    except (ImportError, AttributeError, TypeError, ReferenceError):
        pass
    return left, region_w - right


# --- 0.24.216 every group in its own fixed place -----------------------------------------------------------------
# (user 0.24.214: "모든 툴 공통으로 배치 유지해 놓고 툴마다 달라지는 설정만 추가로 아래에다가"; 0.24.216: "해상도 표시 위치가
#  다 다르잖아 - 사용 안 하는 게 있으면 거기를 그냥 블랭크로 비워 놓고 모든 위치는 똑같이 만들어 줘, 계속 찾아야 되잖아"):
# every group that more than one tool shows has ONE place in the bar, the same for every tool, and inside it every cell
# its own place.  A place the tool in use does not need stays empty - nothing moves into it.  Only what a single tool
# has (Edge, GN Edge, Press, 3D Mouse ...) comes after them, from the left.

def _is_mode(c, key):
    return c['action'] == ('mode', key)


def _is_prop(prop):
    return lambda c: c['prop'] == prop and c['action'] in {('bool',), ('number',), None}


def _is_enum(prop, ident):
    return lambda c: c['prop'] == prop and c['action'] == ('enum', ident)


def _is_op(idname):
    return lambda c: bool(c['action']) and c['action'][0] == 'op' and c['action'][1] == idname


def _seg_w(label):
    return i18n.vlen(label) * 7.0 + 24.0


LANG_LABEL = '한글'              # the Options section's 한글 / English switch (lit = Korean)
LASSO_ROOM = 560.0            # the Lasso group's place: as wide as its longest set (Free Draw: four numbers)


def common_slots():
    """The fixed places: [(title, source group titles, cells)] with cells = [(label, kind, icon, width, match)],
    or cells = a number: a free place that many px wide - the group's own cells from its left edge (Lasso: they
    change with the shape)."""
    shapes = [(label, 'ibtn', 'png:' + stem, ICON, (lambda sid: lambda c: c['action'] == ('shape', sid))(sid))
              for sid, label, _d, stem, _f in ts.SHAPES]

    def seg(label, match):
        return (label, 'seg', '', None, match)

    def mini(label, prop, width):
        return (label, 'mini', '', width, _is_prop(prop))
    return [
        ('Shape', ('Shape', 'Shift+Draw'), shapes),
        ('Draw', ('Draw',), [seg('Line', lambda c: _is_mode(c, 'line')), seg('Sketch', lambda c: _is_mode(c, 'sketch')),
                             seg('Slow Line', _is_prop('stab_enable')), mini('Strength', 'stab_strength', 150),
                             mini('Radius', 'stab_radius', 130)]),
        ('Target', ('Target',), [seg('Auto', _is_enum('targets', 'AUTO')), seg('Selected', _is_enum('targets', 'SELECTED')),
                                 seg('Active', _is_enum('targets', 'ACTIVE'))]),
        ('Depth', ('Depth',), [seg('Through All', _is_enum('depth_mode', 'THROUGH')),
                               seg('From Surface', _is_enum('depth_mode', 'SURFACE')), mini('Depth', 'depth', 130),
                               seg('Follow', _is_enum('depth_floor', 'FOLLOW')), seg('Level', _is_enum('depth_floor', 'LEVEL')),
                               seg('Flat', _is_enum('depth_floor', 'FLAT'))]),
        ('', ('',), [seg('Auto Apply', _is_prop('auto_apply')), seg('Ortho', _is_op('mch.ortho_lock')),
                     seg(LANG_LABEL, _is_op('mch.toggle_language'))]),
        ('Resolution', ('Resolution',), [mini('Res', 'geo_res', 120), seg('Apply to Parts', _is_op('mch.apply_resolution'))]),
        ('Corners', ('Corners',), [seg('Sharp', _is_enum('outline_corner', 'NONE')), seg('Round', _is_enum('outline_corner', 'ROUND')),
                                   seg('Chamfer', _is_enum('outline_corner', 'CHAMFER')), mini('Width', 'outline_radius', 130),
                                   mini('Segments', 'outline_segments', 140)]),
        ('', ('',), [seg('Surface', _is_prop('surface_mode')), mini('Gap', 'surface_gap', 110),
                     seg('Through', _is_prop('through_mode')), mini('Crease', 'through_crease', 120)]),
        ('Lasso', ('Lasso',), LASSO_ROOM),
    ]


def split_common(gs):
    """``groups()`` as (the fixed places, the tool's own groups).  The fixed places: [(title, cells)] for every
    slot of ``common_slots`` - each cell the tool's own cell, or None (an empty place); a free slot: its cells as
    they are.  Every cell of ``gs`` is in exactly one of the two."""
    rest = [(t, list(c)) for t, c in gs]
    row = []
    for title, sources, slots in common_slots():
        shown = title
        if not isinstance(slots, list):                 # a free place: the whole group
            gi = next((i for i, (t, cs) in enumerate(rest) if t in sources and cs), None)
            cells = rest[gi][1][:] if gi is not None else []
            if gi is not None:
                del rest[gi][1][:]
            row.append((shown, cells))
            continue
        cells = []
        for _label, _kind, _icon, _width, match in slots:
            hit = None
            for t, cs in rest:
                if t not in sources:
                    continue
                ci = next((i for i, c in enumerate(cs) if match(c)), None)
                if ci is not None:
                    hit = cs.pop(ci)
                    if t:
                        shown = t                       # (Shift+Draw: the title the tool gives it)
                    break
            cells.append(hit)
        row.append((shown, cells))
    return row, [(t, c) for t, c in rest if c]


def _slot_title_w(title, sources, k):
    return max((i18n.vlen(t) * 7.0 + 8.0) * k + GAP * k for t in sources if t) if any(sources) else 0.0


def _spec_w(spec, k):
    """The width a fixed cell's place has (the same whether the cell is there or not)."""
    label, kind, _icon, width, _match = spec
    return (width if width else _seg_w(label)) * k


def _slot_width(slot, k):
    _title, sources, specs = slot
    body = specs * k if not isinstance(specs, list) else \
        sum(_spec_w(sp_, k) for sp_ in specs) + GAP * k * (len(specs) - 1)
    return body + _slot_title_w(_title, sources, k)


# 0.24.217 (user, with a picture of the bottom tool menu: "우리 여기 밑에 나눴던 거처럼 위에 상단 막대도 그렇게 구다리로
# 나눠서 보기 좋게 하는 건 어떨까?"): the bar as sections side by side, like the tool menu - a small title on top, the
# section's cells in two rows under it, a rule between sections.  The places are still fixed (0.24.216).
TITLE_H = 19.0                # a section's title line
SPLIT_W = 230.0               # a section wider than this in one row puts its cells in two rows
BAND_GAP = 22.0               # between two bands of sections (their cards: 6 px apart)
SEP = 22.0                    # between two sections (their cards: 6 px apart)
CARD_PAD = 8.0                # a section's card round its cells
OUTER_PAD = 8.0               # the lighter box round all the section cards
SECTION_NAMES = {4: 'Options', 7: 'Surface'}     # the two fixed sections whose group has no name of its own
LASSO_SECTION = 300.0


FORCE_SECTIONS = [None]       # tests: True / False whatever the setting says


def sections_wanted():
    """Preferences > Top Bar Sections (on by default): the bar as sections; off: plain rows (0.24.216)."""
    if FORCE_SECTIONS[0] is not None:
        return bool(FORCE_SECTIONS[0])
    from .workspace_ui import pref
    return bool(pref('bar_sections', True))


# 0.24.218 (user: "A 가 좋은 듯"): a section is its title and ONE row of cells - the ones that are always there.  The
# cells that only show when something is switched on (Slow Line's Strength / Radius, the Depth value and floor, a
# corner's Width / Segments, Surface's Gap, Through's Crease) have their own places in a second row right under their
# section: the band grows down by a row while one of them shows, nothing moves sideways.
COND = {('mini', 'Strength'), ('mini', 'Radius'), ('mini', 'Depth'), ('seg', 'Follow'), ('seg', 'Level'), ('seg', 'Flat'),
        ('mini', 'Width'), ('mini', 'Segments'), ('mini', 'Gap'), ('mini', 'Crease')}


def _two_rows(ws, k):
    """Cell widths -> [(row 0 / 1, x, w)] and the section's width: one row when short, else two rows split where
    the longer one is shortest (from the widths alone) - a tool's own section."""
    gap = GAP * k
    total = sum(ws) + gap * (len(ws) - 1)
    if total <= SPLIT_W * k or len(ws) < 2:
        cut = len(ws)
    else:
        cut = min(range(1, len(ws)), key=lambda i: max(sum(ws[:i]) + gap * (i - 1), sum(ws[i:]) + gap * (len(ws) - i - 1)))
    out, x = [], 0.0
    for i, w in enumerate(ws):
        if i == cut:
            x = 0.0
        out.append((0 if i < cut else 1, x, w))
        x += w + gap
    return out, max(sum(ws[:cut]) + gap * (cut - 1), (sum(ws[cut:]) + gap * (len(ws) - cut - 1)) if cut < len(ws) else 0.0)


def _flow_two(ws, room, k):
    """Cell widths into two rows of ``room`` px (a free section): [(row, x, w)]."""
    out, x, row = [], 0.0, 0
    for w in ws:
        if x > 0 and x + w > room + 1e-6 and row == 0:
            row, x = 1, 0.0
        out.append((row, x, w))
        x += w + GAP * k
    return out


def _title_w(title, k):
    return (i18n.vlen(title) * 7.6 + 6.0) * k if title else 0.0


OPTIONS_SLOT = 4              # Auto Apply / Ortho: at the bar's top right (0.24.219), out of the flow


def _slot_size(si, slot, k):
    """(place dict without its position, width) of fixed slot ``si``."""
    title, sources, specs = slot
    tw = max([_title_w(t, k) for t in sources] + [_title_w(SECTION_NAMES.get(si, ''), k)])
    if isinstance(specs, list):
        cells, xs = [], [0.0, 0.0]
        for sp_ in specs:
            row = 1 if (sp_[1], sp_[0]) in COND else 0
            w = _spec_w(sp_, k)
            cells.append((row, xs[row], w))
            xs[row] += w + GAP * k
        return dict(cells=cells), max(max(xs) - GAP * k, tw)
    return dict(free=LASSO_SECTION * k), max(LASSO_SECTION * k, tw)


def fixed_layout(room_w, k):
    """Where every fixed section is in a bar ``room_w`` px wide - from the width alone, never from the tool:
    (bands, [dict(band, x, w, rule, cells=[(row, x, w)] | free=room)]), x from the bar's inner left edge; row 0 =
    the cells that are always there, row 1 = the ones that come and go (``COND``).  The Options section
    (0.24.219, user: "옵션은 오른쪽 위로 보내자") sits at the right end of the first band; the others fill the
    bands from the left.  None when the bar is narrower than a section."""
    slots = common_slots()
    opt_place, opt_w = _slot_size(OPTIONS_SLOT, slots[OPTIONS_SLOT], k)
    x, band = 0.0, 0
    out = [None] * len(slots)
    for si, slot in enumerate(slots):
        if si == OPTIONS_SLOT:
            continue
        place, w = _slot_size(si, slot, k)
        room = room_w - (opt_w + SEP * k if band == 0 else 0.0)     # (the first band: Options is at its right)
        if w > room_w - opt_w - SEP * k:
            return None
        rule = x > 0
        if x > 0 and x + SEP * k + w > room:
            band += 1
            x = 0.0
            rule = False
        elif x > 0:
            x += SEP * k
        place.update(band=band, x=x, w=w, rule=rule)
        out[si] = place
        x += w
    opt_place.update(band=0, x=room_w - opt_w, w=opt_w, rule=False)
    out[OPTIONS_SLOT] = opt_place
    return band + 1, out


# 0.24.224 the LASSO block: the drawing sections every lasso tool shares, in one card at the bar's left
BLOCK_SLOTS = (0, 1, 6, 5, 2, 8)      # Shape, Draw, Corners, Resolution, Target, the shape's own settings
SIDE_SLOTS = (4, 3, 7)                # Options, Depth, Surface: a column of cards at the right
BLOCK_TITLE = 'Lasso'
BLOCK_NAMES = {8: 'Shape Settings'}   # (the group named Lasso: the block has that name now)
BLOCK_TITLE_H = 24.0
BLOCK_PAD = 14.0                      # the block card round its parts
BLOCK_GAP = 12.0                      # between two bands of parts inside the block
BLOCK_SEP = 8.0                       # between the two blocks
BLOCK_SHARE = 0.62                    # the LASSO block: at most this much of the bar's width
BOTTOM_GAP = 10.0                     # the tool's block: this far above the bottom dock
HALF_FROM = 700.0                     # 0.24.286 a tool's box wider than this in one row is cut in two rows
SIDE_TITLE = 'Settings'               # the block at the right: Options, Depth, Surface and the tool's own


def block_layout(room_w, k):
    """Where the LASSO block's parts are in a bar ``room_w`` px wide - from the width alone, never from the tool:
    ([per slot: dict(band, x, w, cells=[(row, x, w)] | free=room) - None for the slots of the block at the right],
    the block's inner width).  The block is as wide as its parts need (at most ``BLOCK_SHARE`` of the bar); the rest
    of the bar is the block at the right.  None when the bar is too narrow."""
    slots = common_slots()
    sized = [_slot_size(si, slot, k) for si, slot in enumerate(slots)]
    widest = max(sized[si][1] for si in BLOCK_SLOTS)
    most = room_w + 2 * CARD_PAD * k - 2 * BLOCK_PAD * k      # 0.24.226 the long form: the whole bar is the block
    if most < widest:
        return None
    out = [None] * len(slots)
    x, band, extent = 0.0, 0, 0.0
    for si in BLOCK_SLOTS:
        place, w = sized[si]
        if x > 0 and x + SEP * k + w > most:
            band += 1
            x = 0.0
        elif x > 0:
            x += SEP * k
        place.update(band=band, x=x, w=w)
        out[si] = place
        x += w
        extent = max(extent, x)
    return out, extent


def fixed_rows_layout(room_w, k):
    """Where every fixed place is, for a bar ``room_w`` px wide - from the width alone, never from the tool:
    (rows, [per slot: dict(title=(row, x, w), rule=(row, x) or None, cells=[(row, x, w)]) or, a free slot,
    dict(title=..., rule=..., free=(row, x, room, rows))]), x from the bar's inner left edge.  A slot that does not
    fit the rest of a row starts the next one; one too wide for a whole row breaks between its cells.  None when
    the bar is too narrow even for that."""
    sep = 14.0 * k
    x, row = 0.0, 0
    out = []
    for title, sources, specs in common_slots():
        tw = _slot_title_w(title, sources, k)
        if isinstance(specs, list):
            ws = [_spec_w(sp_, k) for sp_ in specs]
            total = tw + sum(ws) + GAP * k * (len(ws) - 1)
            if max(ws) + tw > room_w:
                return None
        else:
            ws = None
            total = tw + min(specs * k, room_w - tw)
            if room_w - tw < 150.0 * k:
                return None
        rule = None
        if x > 0 and x + sep + total > room_w:
            row += 1
            x = 0.0
        elif x > 0:
            rule = (row, x)
            x += sep
        place = dict(title=(row, x, tw), rule=rule)
        x += tw
        if ws is None:
            free = min(specs * k, room_w - x)
            if free < 150.0 * k:                      # (hardly any room left in this row: its own row)
                row += 1
                x = tw
                place['title'] = (row, 0.0, tw)
                place['rule'] = None
                free = min(specs * k, room_w - x)
            rows_needed = max(1, math.ceil(specs * k / free - 1e-6))
            place['free'] = (row, x, free, rows_needed)
            row += rows_needed - 1
            x += free
        else:
            cells = []
            for w in ws:
                if x + w > room_w and x > tw + 1e-6:
                    row += 1
                    x = tw                              # (under its own cells, the title's width left free)
                cells.append((row, x, w))
                x += w + GAP * k
            x -= GAP * k
            place['cells'] = cells
        out.append(place)
    return row + 1, out


BAR_SCALE = 0.8               # the LASSO bar's cells: this much of the other bars' size
BAR_PAD = 13.0                # 0.24.227 the thin LASSO bar: its card round the rows
BAR_GAP = 8.0                 # between two rows of the bar
BAR_SEP = 20.0                # between two parts in a row
BAR_FIXED = (0, 1, 6, 5, 2)   # Shape, Draw, Corners, Resolution, Target: one place each, for every tool


def lasso_bar_layout(room_w, k):
    """0.24.227 Where the LASSO bar's fixed parts are - from the width alone: ({slot: dict(band, x, tw, cells=[(x, w)
    per cell that is always there])}, bands, the widest band).  A part is its name and its cells in ONE row; the
    parts follow each other with the same gap; the block's name leads the first band."""
    slots = common_slots()
    lead = _title_w(BLOCK_TITLE, k) * 1.25 + BAR_SEP * k
    out, x, band, widest = {}, lead, 0, 0.0
    for si in BAR_FIXED:
        title, sources, specs = slots[si]
        tw = max(_title_w(t, k) for t in list(sources) + [title]) + GAP * k
        cells, cx = [], tw
        for sp_ in specs:
            if (sp_[1], sp_[0]) in COND:
                cells.append(None)
                continue
            w = _spec_w(sp_, k)
            cells.append((cx, w))
            cx += w + GAP * k
        w = cx - GAP * k
        if lead + w > room_w:
            return None
        if x > lead and x + BAR_SEP * k + w > room_w:
            band += 1
            x = lead
        elif x > lead:
            x += BAR_SEP * k
        out[si] = dict(band=band, x=x, tw=tw, cells=cells)
        x += w
        widest = max(widest, x)
    return out, band + 1, widest


def _lasso_bar(context, tool, common, own, room_w, k):
    """0.24.227 (user, 4K screenshot: "상단 바를 좀 더 얇게 만들어 줘, 지금 간격도 엉망이니까 정리도 좀 해 주고"): the
    LASSO bar as thin rows - a part's name at the LEFT of its cells (no title line above), the fixed parts side by
    side with one gap; the cells that come and go (Slow Line's numbers, a corner's width ...) packed in one row under
    them, each group led by its part's name; then the shape's own settings and the edge parts, packed.
    (items with the card's bottom left at 0, 0; width; height) or None when the view is too narrow."""
    from .mecha_menu import Item
    slots = common_slots()
    inner = room_w - 2 * BAR_PAD * k
    lay = lasso_bar_layout(inner, k)
    if lay is None:
        return None
    places, n_bands, widest = lay
    row_h, gap = ROW * k, BAR_GAP * k
    rows = []                                   # each: [(kind 'title' | 'cell' | 'block', x, w, payload)]
    for b_ in range(n_bands):
        rows.append([])
    rows[0].append(('block', 0.0, _title_w(BLOCK_TITLE, k) * 1.25, BLOCK_TITLE))
    cond = []                                   # [(title, [cells])] the ones that show now
    for si in BAR_FIXED:
        title, cells = common[si]
        pl = places[si]
        name = title or slots[si][0]
        rows[pl['band']].append(('title', pl['x'], pl['tw'] - GAP * k, name))
        shown = []
        for c, sp_, spot in zip(cells, slots[si][2], pl['cells']):
            if spot is None:
                if c is not None:
                    shown.append(c)
                continue
            if c is None:                       # (the tool has no such cell: dim, no click)
                c = dict(kind=sp_[1], label=sp_[0], icon=sp_[2], on=False, action=None, data=None, prop='', off=True)
            rows[pl['band']].append(('cell', pl['x'] + spot[0], spot[1], c))
        if shown:
            cond.append((name, shown))

    def packed(groups_):
        """Groups (name, cells) into rows of ``inner`` px, packed from the left."""
        out_, cur, x = [], [], 0.0
        for name, cells in groups_:
            tw = (_title_w(name, k) + GAP * k) if name else 0.0
            ws = [_width(c, k) for c in cells]
            w = tw + sum(ws) + GAP * k * (len(ws) - 1)
            if cur and x + BAR_SEP * k + w > inner:
                out_.append(cur)
                cur, x = [], 0.0
            elif cur:
                x += BAR_SEP * k
            if name:
                cur.append(('title', x, tw - GAP * k, name))
            cx = x + tw
            for c, cw in zip(cells, ws):
                if cx + cw > inner and cx > x + tw:      # (a very long group: goes on in the next row)
                    out_.append(cur)
                    cur, cx = [], 0.0
                cur.append(('cell', cx, cw, c))
                cx += cw + GAP * k
            x = cx - GAP * k
        if cur:
            out_.append(cur)
        return out_
    rows += packed(cond)
    eg = edge_groups(context, tool)
    more = []
    free = common[8][1]
    if free:
        more.append((BLOCK_NAMES.get(8, 'Lasso'), free))
    more += [(t, c) for t, c in own if any(t == et and c == ec for et, ec in eg)]
    rows += packed(more)
    width = max([widest] + [max(x + w for _k, x, w, _p in r) for r in rows if r]) + 2 * BAR_PAD * k
    height = len(rows) * row_h + (len(rows) - 1) * gap + 2 * BAR_PAD * k
    out = [Item('card', 0.0, 0.0, width, height)]
    for n, r in enumerate(rows):
        y = height - BAR_PAD * k - (n + 1) * row_h - n * gap
        for kind, x, w, p_ in r:
            px = BAR_PAD * k + x
            if kind == 'block':
                out.append(Item('glabel', px, y, w, row_h, p_.upper(), 'block'))
            elif kind == 'title':
                out.append(Item('glabel', px, y, w, row_h, p_.upper(), 'title'))
            else:
                out.append(Item(p_['kind'], px, y, w, row_h, p_['label'], p_['icon'], p_['on'], not p_.get('off'),
                                p_['action'], p_['data'], p_['prop']))
    return out, width, height


def items(context, region_w, region_h, k=1.0, left=None, right=None, part='TOP'):
    """The bar as Mecha Menu Items (region px).  ``part``: 'TOP' the bar at the top (0.24.226: the LASSO block);
    'BOTTOM' the tool's own block above the bottom dock (nothing when the bar is not in sections)."""
    from .mecha_menu import Item
    tool = ts.effective_tool(context)
    gs = groups(context, tool)
    if not gs:
        return []
    panel_top = None
    l_low = left
    if left is None or right is None:
        from . import side_panel, ui_bars
        left, right = room(context, region_w, k)
        l_low = left
        if not ui_bars.strip_on(context):          # 0.24.59 the Layers panel starts as low as the side panel
            l_low = ui_bars.left_inset(context)
        if right < region_w or l_low < left:        # ... and the side panel starts lower: use the whole width
            panel_top = side_panel.frame(region_w, region_h, k, context)[1]
    sep = 14.0 * k
    from . import ui_bars
    inset = ui_bars.top_inset(context)             # 0.24.59 under Blender's see-through header rows
    corner = 0.0
    try:                                             # 0.24.60 the MECHA LAB / ZBRUSH card in the corner
        from . import zb_ui
        corner = zb_ui.corner_reserve(context, region_w, region_h, k)
    except (ImportError, AttributeError, TypeError, ReferenceError):
        pass
    common, own = split_common(gs)
    # the fixed places are laid out for the band between the tool strip and the side panel - whatever the tool:
    # so they are in the same place for every tool
    band_l, band_r = left, min(right, region_w - corner)
    band = max(300.0 * k, band_r - band_l - 24 * k)
    inner = band - 2 * PAD * k
    fixed = block_layout(inner, k) if sections_wanted() else None
    if fixed and part == 'TOP':
        # 0.24.227 (user, a picture of the bar shrunk: "이 정도 비율로 하고 싶어"): the LASSO bar drawn smaller
        ks = k * BAR_SCALE
        bar = _lasso_bar(context, tool, common, own, inner + 2 * CARD_PAD * k, ks)
        if bar is not None:
            its_, w_, h_ = bar
            for i in its_:
                if i.kind == 'glabel':
                    i.icon += '_s'              # (drawn at the bar's own scale)
            # 0.24.228 (user: "상단 바 중앙 정렬이 안 돼"): in the middle of the view, like the bar with Select below
            x0 = max(band_l + 8 * k, min((region_w - w_) / 2.0, band_r - 8 * k - w_))
            y_top = region_h - TOP * k - inset
            for i in its_:
                i.x += x0
                i.y += y_top - h_
            return its_
    if fixed:
        # 0.24.224 (user: "모양 그리기 모서리 해상도는 다 공통이잖아 - 한 묶음으로 라쏘 칸으로 묶어 줘, 왼쪽으로 블록 하나
        # 만들어 줘, 이름은 써 주고" / "대상까지도"): the drawing sections in ONE block at the left (LASSO, each part
        # with its name, each at its own place for every tool).
        # 0.24.226 (user: "배치가 빈 곳이 이상한데, 그리고 오른쪽도 한 박스로 묶어 줘 - 저긴 변동성이 있는 거야"): the
        # block is as wide as its parts; everything else (Options, Depth, Surface, the tool's own) is ONE block at its
        # right that takes the rest of the bar - what the tool has, packed from the left, no empty places.
        places, extent = fixed
        slots = common_slots()

        def used_of(cells, pl):
            return any(c is not None for c in cells) if 'cells' in pl else bool(cells)
        rows_in = collections.defaultdict(lambda: 1)       # (block, band) -> rows of cells
        lasso_rows = {}
        last = {0: -1, 1: -1}
        for si in BLOCK_SLOTS:
            (title, cells), pl = common[si], places[si]
            if not used_of(cells, pl):
                continue
            last[0] = max(last[0], pl['band'])
            if 'cells' in pl:
                if any(c is not None and pr == 1 for c, (pr, _x, _w) in zip(cells, pl['cells'])):
                    rows_in[(0, pl['band'])] = 2
            else:
                lasso_rows[si] = _flow_two([_width(c, k) for c in cells], pl['free'], k)
                if any(pr == 1 for pr, _x, _w in lasso_rows[si]):
                    rows_in[(0, pl['band'])] = 2
        last[0] = max(last[0], max(places[si]['band'] for si in BLOCK_SLOTS if 'cells' in places[si]))   # (all there)
        # the edge sections (GN Edge / Edge Finish / Base Mesh's Edge): parts of the LASSO block too, after the fixed ones
        eg = edge_groups(context, tool)
        edge_own = [g for g in own if any(g[0] == t and g[1] == c for t, c in eg)]
        own = [g for g in own if not any(g is e for e in edge_own)]

        def flow(parts, room_, col, band0):
            """[(title, cells, spots, width)] into bands of ``room_`` px: [dict(band, x, w, cells)], last band."""
            out_, x_, b_ = [], 0.0, band0
            for _t, _c, spots_, w_ in parts:
                if x_ > 0 and x_ + SEP * k + w_ > room_:
                    b_ += 1
                    x_ = 0.0
                elif x_ > 0:
                    x_ += SEP * k
                out_.append(dict(band=b_, x=x_, w=w_, cells=spots_))
                if any(pr == 1 for pr, _x, _w in spots_):
                    rows_in[(col, b_)] = 2
                x_ += w_
            return out_, (b_ if parts else band0 - 1)

        def two(title, cells):
            cl, w = _two_rows([_width(c, k) for c in cells], k)
            return (title, cells, cl, max(w, _title_w(title, k)))
        edge_parts = [two(t, c) for t, c in edge_own]
        edge_places, eb = flow(edge_parts, extent, 0, last[0] + 1)
        if edge_parts:
            last[0] = eb
        has_left = last[0] >= 0
        # the block at the right: Options, Depth, Surface - only the cells the tool has, packed - then the tool's own
        side_parts = []
        for si in SIDE_SLOTS:
            if si == OPTIONS_SLOT:                  # (user: "옵션은 여기다가 그냥 넣어 줘": in the bottom dock)
                continue
            title, cells = common[si]
            xs, spots, shown = [0.0, 0.0], [], []
            for c, sp_ in zip(cells, slots[si][2]):
                if c is None:
                    continue
                row = 1 if (sp_[1], sp_[0]) in COND else 0
                w = _spec_w(sp_, k)
                spots.append((row, xs[row], w))
                shown.append(c)
                xs[row] += w + GAP * k
            if shown:
                name = title or SECTION_NAMES.get(si, '')
                side_parts.append((name, shown, spots, max(max(xs) - GAP * k, _title_w(name, k))))
        side_parts += [two(t, c) for t, c in own]
        # 0.24.226 (user: "변동성 있는 메뉴도 다 내려놓고, 모든 공통인 라쏘랑 지금 왼쪽에 묶어 놓은 것만 위에 놓으면"): the
        # LASSO block alone at the top; the tool's block - what changes from tool to tool - at the bottom, above the dock
        room_b = inner - 2 * BLOCK_PAD * k
        # 0.24.286 (user: "프레스 컷 이거 왼쪽 바가 너무 옆으로 길어서 반으로 잘라서 짧게"): the tool's box at about half
        # of its one-row width - its parts wrap into a second row (never narrower than its widest part)
        if side_parts:
            one_row = sum(p_[3] for p_ in side_parts) + SEP * k * (len(side_parts) - 1)
            widest = max(p_[3] for p_ in side_parts)
            if one_row > HALF_FROM * k:
                room_b = min(room_b, max(widest, one_row * 0.5 + SEP * k))
        side_places, last[1] = flow(side_parts, room_b, 1, 0)

        def bh(key):
            return (TITLE_H + rows_in[key] * ROW + (rows_in[key] - 1) * GAP) * k

        def col_h(col):
            n = last[col] + 1
            return sum(bh((col, b_)) for b_ in range(n)) + max(0, n - 1) * BLOCK_GAP * k if n else 0.0
        head = BLOCK_TITLE_H * k
        x0 = max(band_l + 8 * k, min((region_w - band) / 2.0, band_r - 8 * k - band))
        out = []

        def block(col, parts, places_, name, card_x, card_top, w):
            """One block: its card, its name, its parts (title over cells)."""
            card_h = col_h(col) + head + 2 * BLOCK_PAD * k
            out.append(Item('card', card_x, card_top - card_h, w, card_h))
            out.append(Item('glabel', card_x + BLOCK_PAD * k, card_top - BLOCK_PAD * k - head + 4 * k, 200 * k,
                            head, name.upper(), 'block'))
            tops, yy = {}, card_top - BLOCK_PAD * k - head
            for b_ in range(last[col] + 1):
                tops[b_] = yy
                yy -= bh((col, b_)) + BLOCK_GAP * k
            for (title, cells, spots), pl in zip(parts, places_):
                by = tops[pl['band']]
                sx = card_x + BLOCK_PAD * k + pl['x']
                if title:                           # (icon 'title': drawn bigger and bright - a part's name)
                    out.append(Item('glabel', sx, by - TITLE_H * k, pl['w'], TITLE_H * k, title.upper(), 'title'))
                for c, (cr, cx, cw) in zip(cells, spots):
                    if c is not None:               # (else: its place stays empty)
                        out.append(Item(c['kind'], sx + cx, by - TITLE_H * k - (cr + 1) * ROW * k - cr * GAP * k, cw,
                                        ROW * k, c['label'], c['icon'], c['on'], not c.get('off'), c['action'],
                                        c['data'], c['prop']))
        if part == 'TOP':
            parts, pls = [], []
            for si in BLOCK_SLOTS:
                (title, cells), pl = common[si], places[si]
                if 'cells' in pl:
                    # (user: "상단 바는 라쏘 안 쓰는 것도 걍 들어가 있게"): every part is there in every tool - a
                    # cell the tool does not have is shown dim (no click); the ones that come and go stay hidden
                    cells = [c if c is not None or (sp_[1], sp_[0]) in COND else
                             dict(kind=sp_[1], label=sp_[0], icon=sp_[2], on=False, action=None, data=None, prop='', off=True)
                             for c, sp_ in zip(cells, slots[si][2])]
                    parts.append((BLOCK_NAMES.get(si, title or slots[si][0]), cells, pl['cells']))
                    pls.append(pl)
                elif cells:
                    parts.append((BLOCK_NAMES.get(si, title), cells, lasso_rows.get(si, [])))
                    pls.append(pl)
            parts += [(t, c, sp_) for t, c, sp_, _w in edge_parts]
            pls += edge_places
            block(0, parts, pls, BLOCK_TITLE, x0, region_h - TOP * k - inset, extent + 2 * BLOCK_PAD * k)
            return out
        if not side_parts:
            return []
        w = max(pl['x'] + pl['w'] for pl in side_places) + 2 * BLOCK_PAD * k      # as wide as what is in it
        floor = ui_bars.bottom_taken(context, k, region_w)    # (bottom_row moves the box to its place in the row)
        card_h = col_h(1) + head + 2 * BLOCK_PAD * k
        t = ts.TOOL_BY_ID.get(tool)
        block(1, [(t_, c, sp_) for t_, c, sp_, _w in side_parts], side_places, t[1] if t else SIDE_TITLE,
              x0 + (band - w) / 2.0, floor + BOTTOM_GAP * k + card_h, w)
        return out
    if part != 'TOP':
        return []
    # Preferences > Top Bar Sections off (or a view narrower than a section): the fixed places as plain rows (0.24.216)
    fixed = fixed_rows_layout(inner, k)             # (None, a very narrow view: the old way, all packed)
    if fixed:
        n_fixed, places = fixed
        # the rows under the last place this tool uses are left out (its own groups follow at once); an empty
        # place above or between used ones stays empty - nothing ever moves sideways or up into it
        last = -1
        for (title, cells), place in zip(common, places):
            if 'cells' in place:
                last = max([last] + [pr for c, (pr, _x, _w) in zip(cells, place['cells']) if c is not None])
            elif cells:
                fr, fx, froom, _n = place['free']
                cx, cr = fx, fr
                for c in cells:
                    w = _width(c, k)
                    if cx + w > fx + froom + 1e-6 and cx > fx:
                        cr += 1
                        cx = fx
                    cx += w + GAP * k
                last = max(last, cr)
        n_fixed = last + 1
        # the tool's own groups: under the fixed rows, from the same left edge, in the same width
        rows = rows_of(own, inner, k) if own else []
        n_rows = n_fixed + len(rows)
        width = band
        height = n_rows * ROW * k + (n_rows - 1) * GAP * k + 2 * PAD * k
        y0 = region_h - TOP * k - inset - height
        x0 = max(band_l + 8 * k, min((region_w - width) / 2.0, band_r - 8 * k - width))
        out = [Item('card', x0, y0, width, height)]
        top = y0 + height - PAD * k - ROW * k
        left_x = x0 + PAD * k

        def ry(row):
            return top - row * (ROW * k + GAP * k)
        for (title, cells), place, (_t, sources, specs) in zip(common, places, common_slots()):
            used = any(c is not None for c in cells)
            if place['rule'] is not None and used:
                rr, rx = place['rule']
                out.append(Item('vrule', left_x + rx + sep / 2 - 0.5 * k, ry(rr) + 6 * k, 1.0 * k, ROW * k - 12 * k))
            tr_, tx, tw = place['title']
            if tw and used:
                out.append(Item('glabel', left_x + tx, ry(tr_), tw - GAP * k, ROW * k, title.upper()))
            if 'cells' in place:
                for c, (cr, cx, cw) in zip(cells, place['cells']):
                    if c is not None:               # (else: its place stays empty)
                        out.append(Item(c['kind'], left_x + cx, ry(cr), cw, ROW * k, c['label'], c['icon'], c['on'],
                                        True, c['action'], c['data'], c['prop']))
            else:
                fr, fx, froom, _n = place['free']
                cx, cr = fx, fr
                for c in cells:
                    w = _width(c, k)
                    if cx + w > fx + froom + 1e-6 and cx > fx:
                        cr += 1
                        cx = fx
                    out.append(Item(c['kind'], left_x + cx, ry(cr), w, ROW * k, c['label'], c['icon'], c['on'], True,
                                    c['action'], c['data'], c['prop']))
                    cx += w + GAP * k
        y = ry(n_fixed)
        for r in rows:
            x = left_x                              # (from the left: a group does not move when another comes or goes)
            for gi, (title, cells) in enumerate(r):
                if gi:
                    out.append(Item('vrule', x + sep / 2 - 0.5 * k, y + 6 * k, 1.0 * k, ROW * k - 12 * k))
                    x += sep
                if title:
                    tw = (i18n.vlen(title) * 7.0 + 8.0) * k
                    out.append(Item('glabel', x, y, tw, ROW * k, title.upper()))
                    x += tw + GAP * k
                for c in cells:
                    w = _width(c, k)
                    out.append(Item(c['kind'], x, y, w, ROW * k, c['label'], c['icon'], c['on'], True, c['action'],
                                    c['data'], c['prop']))
                    x += w + GAP * k
                x -= GAP * k
            y -= ROW * k + GAP * k
        return out
    # a view too narrow for the fixed places: the groups packed into rows (as before 0.24.214)
    for full in ((True, False) if panel_top is not None else (False,)):
        r_edge = (region_w - corner) if full else min(right, region_w - corner)
        l_edge = l_low if full else left
        avail = max(300.0 * k, r_edge - l_edge - 24 * k)
        rows = rows_of(gs, avail - 2 * PAD * k, k)
        widths = [sum(_group_width(t, c, k) for t, c in r) + sep * (len(r) - 1) for r in rows]
        width = max(widths) + 2 * PAD * k
        height = len(rows) * ROW * k + (len(rows) - 1) * GAP * k + 2 * PAD * k
        y0 = region_h - TOP * k - inset - height
        if not full or y0 >= panel_top + 6 * k:
            break
    x0 = max(l_edge + 8 * k, min((region_w - width) / 2.0, r_edge - 8 * k - width))
    out = [Item('card', x0, y0, width, height)]
    y = y0 + height - PAD * k - ROW * k
    for r, rw in zip(rows, widths):
        x = x0 + (width - rw) / 2.0
        for gi, (title, cells) in enumerate(r):
            if gi:
                out.append(Item('vrule', x + sep / 2 - 0.5 * k, y + 6 * k, 1.0 * k, ROW * k - 12 * k))
                x += sep
            if title:
                tw = (i18n.vlen(title) * 7.0 + 8.0) * k
                out.append(Item('glabel', x, y, tw, ROW * k, title.upper()))
                x += tw + GAP * k
            for c in cells:
                w = _width(c, k)
                it = Item(c['kind'], x, y, w, ROW * k, c['label'], c['icon'], c['on'], True, c['action'],
                          c['data'], c['prop'])
                out.append(it)
                x += w + GAP * k
            x -= GAP * k
        y -= ROW * k + GAP * k
    return out


def option_cells(context):
    """0.24.226 the Options cells of the tool in use (Auto Apply, Ortho, 한글) - shown in the bottom dock."""
    gs = groups(context, ts.effective_tool(context))
    if not gs:
        return []
    common, _own = split_common(gs)
    return [c for c in common[OPTIONS_SLOT][1] if c is not None]


def holds(context, item):
    """Is ``item`` (a drawn cell) one of the top bar's?  (Looked up by its setting and place in the bar as it is now.)"""
    region = getattr(context, 'region', None)
    if region is None or not on(context):
        return False
    from .ui_gpu import ui_factor
    k = ui_factor(context, region)
    its = items(context, region.width, region.height, k) + items(context, region.width, region.height, k, part='BOTTOM')
    return any(i.kind == item.kind and i.prop == item.prop and abs(i.x - item.x) < 1.0 and abs(i.y - item.y) < 1.0
               for i in its)


def on(context):
    from .workspace_ui import pref
    from . import bottom_bar
    return pref('top_bar', True) and bottom_bar.ui_active(context)
