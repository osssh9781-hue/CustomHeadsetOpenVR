"""Interactive shape strokes shared by the Cut, Split and Mask tools.

Interaction model (fixes the v0.5.9 "Ctrl+Z does nothing / Esc needed before
clicking a menu" problems):

* Cut / Split / Mask are native WorkSpaceTools.  Between strokes NOTHING is
  modal: Ctrl+Z, menus, the sidebar and other editors behave like normal
  Blender.  LMB in the viewport starts ``mch.cut_stroke``.
* ``mch.cut_stroke`` is modal only for one stroke and returns FINISHED after
  one cut, so every cut is exactly one undo step.  A failed cut returns
  CANCELLED and pushes nothing.
* While a stroke is pending, events outside the viewport region pass through
  (shape palette, sidebar, menus work without Esc).  Changing the shape or the
  tool discards only the unfinished stroke.
* Keys: Enter / LMB double-click confirm, Esc cancels the stroke, Backspace or
  Ctrl+Z removes the last point, Ctrl+Shift+Z re-adds it, Shift snaps to 45
  degrees, Alt inverts (keep inside / erase mask), F toggles open line.
* RMB once = shape popup, RMB twice (double-click) = leave the tool.  The popup
  waits for the double-click interval so the second click is never eaten.
"""
from __future__ import annotations

import math
import time
import traceback

import bpy
import gpu
from bpy.props import EnumProperty
from gpu_extras.batch import batch_for_shader
from mathutils.geometry import tessellate_polygon

from . import core_geometry as cg
from . import tool_state as ts

SHAPE_POPUP = 'MCH_PT_shape_popup'
TOOL_POPUP = 'MCH_PT_tool_popup'
ROUND_LEVELS = (0.0, 0.12, 0.25, 0.42)   # sharp -> soft -> medium -> strong -> sharp
HIT_PX = 9.0
NAV_EVENTS = {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'WHEELINMOUSE', 'WHEELOUTMOUSE',
              'TRACKPADPAN', 'TRACKPADZOOM', 'MOUSEROTATE', 'MOUSESMARTZOOM'}


# -----------------------------------------------------------------------------
# Pure 2D shape generation
# -----------------------------------------------------------------------------


def rect_loop(a, b, square=False, centered=False):
    dx, dy = b[0] - a[0], b[1] - a[1]
    if square:
        s = max(abs(dx), abs(dy))
        dx, dy = math.copysign(s, dx or 1), math.copysign(s, dy or 1)
    if centered:
        x0, y0, x1, y1 = a[0] - dx, a[1] - dy, a[0] + dx, a[1] + dy
    else:
        x0, y0, x1, y1 = a[0], a[1], a[0] + dx, a[1] + dy
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def ellipse_loop(a, b, segments, circle=False, centered=False):
    if centered:
        cx, cy = a
        rx, ry = abs(b[0] - a[0]), abs(b[1] - a[1])
    else:
        cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        rx, ry = abs(b[0] - a[0]) / 2, abs(b[1] - a[1]) / 2
    if circle:
        rx = ry = max(rx, ry)
    return [(cx + rx * math.cos(2 * math.pi * i / segments),
             cy + ry * math.sin(2 * math.pi * i / segments)) for i in range(segments)]


def circle_loop(c, edge, segments):
    r = math.dist(c, edge)
    return [(c[0] + r * math.cos(2 * math.pi * i / segments),
             c[1] + r * math.sin(2 * math.pi * i / segments)) for i in range(segments)]


def corner_handles(points, i, r):
    p = points[i]
    a = points[i - 1]
    b = points[(i + 1) % len(points)]
    return ((p[0] + (a[0] - p[0]) * r, p[1] + (a[1] - p[1]) * r),
            (p[0] + (b[0] - p[0]) * r, p[1] + (b[1] - p[1]) * r))


def curve_lasso_loop(points, rounds, resolution):
    """Closed outline with per-point quadratic Bezier rounding."""
    n = len(points)
    if n < 3:
        return list(points)
    out = []
    for i in range(n):
        r = rounds[i] if i < len(rounds) else 0.0
        p = points[i]
        if r <= 1e-6:
            out.append(p)
            continue
        h0, h1 = corner_handles(points, i, r)
        for k in range(resolution + 1):
            t = k / resolution
            u = 1 - t
            out.append((u * u * h0[0] + 2 * u * t * p[0] + t * t * h1[0],
                        u * u * h0[1] + 2 * u * t * p[1] + t * t * h1[1]))
    return out


def custom_loops(norm_loops, center, radius, angle):
    c, s = math.cos(angle), math.sin(angle)
    scale = radius * 2.0   # normalized loops span [-0.5, 0.5]
    out = []
    for lp in norm_loops:
        out.append([(center[0] + (x * c - y * s) * scale, center[1] + (x * s + y * c) * scale)
                    for x, y in lp])
    return out


def snap45(anchor, p):
    dx, dy = p[0] - anchor[0], p[1] - anchor[1]
    r = math.hypot(dx, dy)
    if r < 1e-6:
        return p
    ang = round(math.atan2(dy, dx) / (math.pi / 4)) * (math.pi / 4)
    return (anchor[0] + math.cos(ang) * r, anchor[1] + math.sin(ang) * r)


# Open line -> half-plane polygon inside a padded screen box (from v0.5.9).


def _ray_box_exit(point, direction, box):
    x, y = point
    dx, dy = direction
    xmin, ymin, xmax, ymax = box
    best = None
    for border, orig, d in ((xmin, x, dx), (xmax, x, dx), (ymin, y, dy), (ymax, y, dy)):
        if abs(d) > 1e-9:
            t = (border - orig) / d
            if t > 1e-9:
                px, py = x + t * dx, y + t * dy
                if xmin - 0.01 <= px <= xmax + 0.01 and ymin - 0.01 <= py <= ymax + 0.01:
                    if best is None or t < best[0]:
                        best = (t, (max(xmin, min(xmax, px)), max(ymin, min(ymax, py))))
    if best is None:
        raise cg.CutError('Line endpoints coincide; place two distinct points.')
    return best[1]


def _perimeter_param(p, box):
    xmin, ymin, xmax, ymax = box
    x, y = p
    w, h = xmax - xmin, ymax - ymin
    e = 0.03
    if abs(y - ymin) < e:
        return x - xmin
    if abs(x - xmax) < e:
        return w + y - ymin
    if abs(y - ymax) < e:
        return w + h + xmax - x
    if abs(x - xmin) < e:
        return 2 * w + h + ymax - y
    raise cg.CutError('Line endpoint is not on the view boundary.')


def _border_ccw(a, b, box):
    xmin, ymin, xmax, ymax = box
    w, h = xmax - xmin, ymax - ymin
    per = 2 * (w + h)
    lo, hi = _perimeter_param(a, box), _perimeter_param(b, box)
    if hi <= lo + 1e-6:
        hi += per
    corners = [(w, (xmax, ymin)), (w + h, (xmax, ymax)), (2 * w + h, (xmin, ymax)), (per, (xmin, ymin))]
    route = [c for t, c in ((t + k * per, p) for k in (0, 1) for t, p in corners) if lo + 1e-5 < t < hi - 1e-5]
    return route + [b]


def side_polygon(points, box):
    if len(points) < 2:
        raise cg.CutError('Draw at least two points.')
    p0, p1 = points[0], points[1]
    q1, q0 = points[-2], points[-1]
    a = _ray_box_exit(p0, (p0[0] - p1[0], p0[1] - p1[1]), box)
    b = _ray_box_exit(q0, (q0[0] - q1[0], q0[1] - q1[1]), box)
    if math.dist(a, b) < 2:
        raise cg.CutError('Line ends meet at the same boundary point.')
    return cg.dedupe_loop([a] + list(points) + [b] + _border_ccw(b, a, box)[:-1], 0.05)


# -----------------------------------------------------------------------------
# Targets
# -----------------------------------------------------------------------------


def pick_mesh_under(context, projector, xy):
    origin, direction = projector.ray(xy)
    dg = context.evaluated_depsgraph_get()
    hit, _loc, _n, _i, ob, _m = context.scene.ray_cast(dg, origin, direction)
    if hit and ob is not None and ob.type == 'MESH':
        original = ob.original
        # The mask preview is a selectable-disabled overlay, not a target mesh.
        # It may still be returned by a scene ray-cast after a mask stroke.
        source_name = original.get('mch_preview_source')
        if source_name:
            return bpy.data.objects.get(source_name)
        return original
    return None


def gather_targets(context, projector, xy, mode):
    cut = context.scene.mch_cut
    active = context.view_layer.objects.active
    if mode != 'MASK' and cut.targets == 'SELECTED':
        targets = [o for o in context.selected_objects if o.type == 'MESH' and o.visible_get()]
        if targets:
            return targets
    if active is not None and active.type == 'MESH' and active.visible_get() and \
            (active.select_get() or not context.selected_objects):
        return [active]
    picked = pick_mesh_under(context, projector, xy)
    if picked is not None:
        for o in context.selected_objects:
            o.select_set(False)
        picked.select_set(True)
        context.view_layer.objects.active = picked
        return [picked]
    return []


def surface_hit(context, targets, projector, xy):
    origin, direction = projector.ray(xy)
    best = None
    for ob in targets:
        inv = ob.matrix_world.inverted_safe()
        ok, loc, _n, _f = ob.ray_cast(inv @ origin, (inv.to_3x3() @ direction).normalized())
        if ok:
            world = ob.matrix_world @ loc
            d = (world - origin).length
            if best is None or d < best[0]:
                best = (d, world)
    return None if best is None else best[1]


def _loops_centroid(loops):
    pts = loops[0]
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def _planes(context, targets, projector, loops):
    cut = context.scene.mch_cut
    hit = None
    if cut.depth_mode == 'SURFACE':
        hit = surface_hit(context, targets, projector, _loops_centroid(loops))
        if hit is None:
            for p in loops[0]:
                hit = surface_hit(context, targets, projector, p)
                if hit is not None:
                    break
    return cg.depth_planes(projector, cg.object_world_bounds(targets), cut.depth_mode, hit, cut.depth)


def _object_scale(ob):
    s = ob.matrix_world.to_scale()
    return max((abs(s.x) + abs(s.y) + abs(s.z)) / 3.0, 1e-9)


def _make_piece(target, mesh, suffix='_Split'):
    piece = target.copy()
    piece.data = mesh
    mesh.name = target.data.name + suffix
    piece.name = target.name + suffix
    for coll in target.users_collection:
        coll.objects.link(piece)
    cg.remove_cutter_attribute(mesh)
    return piece


# -----------------------------------------------------------------------------
# Operations (usable headless with any projector)
# -----------------------------------------------------------------------------


def perform_closed(context, mode, targets, loops, projector, invert=False):
    """Cut / Split all targets with closed screen loops. Returns a report string."""
    scene = context.scene
    cut = scene.mch_cut
    auto_apply = scene.mch_settings.auto_apply if hasattr(scene, 'mch_settings') else True
    groups = cg.prepare_loops(loops)
    for t in targets:
        cg.check_target(t)
    near, far = _planes(context, targets, projector, [g[0] for g in groups])
    cutter_mesh = cg.build_cutter_mesh(groups, projector, near, far, 'MCH_CutterMesh')
    cutter = cg.link_temp_object(context, cutter_mesh)
    if not auto_apply:
        return _make_live(context, mode, targets, cutter, invert)
    results, pieces, temp = [], [], []
    edge_counts = []
    try:
        for t in targets:
            scale = _object_scale(t)
            try:
                if mode == 'CUT':
                    op = 'INTERSECT' if invert else 'DIFFERENCE'
                    me, _solver = cg.boolean_result(context, t, cutter, op, cut.solver, cut.hole_tolerant)
                    temp.append(me)
                    edge_counts.append(cg.finish_new_edges(
                        me, cut.edge_finish, cut.finish_width / scale,
                        cut.finish_segments, cut.finish_profile))
                    results.append((t, me))
                else:  # SPLIT
                    inner, _s1 = cg.boolean_result(context, t, cutter, 'INTERSECT', cut.solver, cut.hole_tolerant)
                    temp.append(inner)
                    outer, _s2 = cg.boolean_result(context, t, cutter, 'DIFFERENCE', cut.solver, cut.hole_tolerant)
                    temp.append(outer)
                    for me in (inner, outer):
                        if cut.split_cap:
                            edge_counts.append(cg.finish_new_edges(
                                me, cut.edge_finish, cut.finish_width / scale,
                                cut.finish_segments, cut.finish_profile))
                        else:
                            cg.strip_cutter_faces(me)
                    results.append((t, outer))
                    pieces.append((t, inner))
            except cg.CutError as ex:
                if len(targets) > 1 and 'does not intersect' in str(ex):
                    continue
                raise
        if not results:
            raise cg.CutError('The shape does not intersect any target; nothing was changed.')
        infos = []
        for t, me in results:
            infos.append(cg.commit_mesh(t, me, cut.shared_mesh))
        new_pieces = []
        for t, me in pieces:
            temp.remove(me)
            new_pieces.append(_make_piece(t, me))
        for p in new_pieces:
            p.select_set(True)
        verb = {'CUT': 'Kept inside' if invert else 'Cut', 'SPLIT': 'Split'}[mode]
        suffix = ''
        if cut.edge_finish != 'NONE' and cut.finish_width > 0:
            if not edge_counts:
                suffix = ' | Edge Finish skipped (uncapped or Live cut)'
            elif sum(edge_counts) == 0:
                suffix = ' | WARNING: Edge Finish found 0 new edges; no bevel/chamfer'
            else:
                suffix = f' | {cut.edge_finish}: {sum(edge_counts)} newly cut edges'
        return f'{verb}: {", ".join(t.name for t, _ in results)}{"".join(sorted(set(infos)))}{suffix}'
    finally:
        for me in temp:
            if me.users == 0:
                bpy.data.meshes.remove(me)
        cg.remove_object_and_mesh(cutter)


def _make_live(context, mode, targets, cutter, invert):
    """Auto Apply OFF: keep the cutter object and live Boolean modifiers."""
    cut = context.scene.mch_cut
    solver = {'AUTO': 'EXACT', 'FAST': 'FLOAT'}.get(cut.solver, cut.solver)
    cutter.name = 'MCH_Cut_Live'
    cutter.data.name = 'MCH_Cut_Live_Mesh'
    cutter['mch_cut_carrier'] = True
    first = targets[0]
    for t in targets:
        mod = t.modifiers.new('MCH_LiveCut', 'BOOLEAN')
        mod.object = cutter
        mod.solver = solver
        mod.operation = 'INTERSECT' if (mode == 'CUT' and invert) else 'DIFFERENCE'
        if t == first:
            cutter['mch_cut_target_name'] = t.name
            cutter['mch_cut_target_mod'] = mod.name
            if hasattr(cutter, 'mch_live'):
                cutter.mch_live.target = t
        t['mch_recent_cut'] = cutter.name
    if mode == 'SPLIT':
        piece = first.copy()
        piece.data = first.data.copy()
        piece.name = first.name + '_Split'
        for coll in first.users_collection:
            coll.objects.link(piece)
        for m in [m for m in piece.modifiers if m.name.startswith('MCH_LiveCut')]:
            piece.modifiers.remove(m)
        pm = piece.modifiers.new('MCH_LiveCut_Piece', 'BOOLEAN')
        pm.object = cutter
        pm.solver = solver
        pm.operation = 'INTERSECT'
        cutter['mch_cut_piece_name'] = piece.name
        cutter['mch_cut_piece_mod'] = pm.name
        if hasattr(cutter, 'mch_live'):
            cutter.mch_live.source = piece
    return ('Live cut created (edit cutter, then Apply Live Cut). ' +
            ('Edge Finish requires Auto Apply ON; no bevel generated.' if cut.edge_finish != 'NONE' else ''))


def perform_line(context, mode, targets, points, projector, side_xy, invert=False):
    """Open line cut / split. ``side_xy`` picks the half removed by Cut."""
    scene = context.scene
    cut = scene.mch_cut
    auto_apply = scene.mch_settings.auto_apply if hasattr(scene, 'mch_settings') else True
    for t in targets:
        cg.check_target(t)
    if len(points) == 2 and cut.fast_line and auto_apply:
        near, far = cg.depth_planes(projector, cg.object_world_bounds(targets))
        vd = projector.view_dir

        def at(xy, plane):
            o, d = projector.ray(xy)
            return cg._plane_hit(o, d, plane, vd)[0]
        a_near, a_far, b_near = at(points[0], near), at(points[0], far), at(points[1], near)
        normal = (a_far - a_near).cross(b_near - a_near)
        if normal.length < 1e-12:
            raise cg.CutError('Line is too short.')
        normal.normalize()
        side = (at(side_xy, near) - a_near).dot(normal) > 0
        results, pieces, temp = [], [], []
        line_bevel_counts = []
        try:
            for t in targets:
                scale = _object_scale(t)
                try:
                    if mode == 'CUT':
                        me = cg.plane_split_mesh(t, a_near, normal, side != invert, cut.line_cap)
                        temp.append(me)
                        if cut.line_cap:
                            line_bevel_counts.append(cg.finish_new_edges(
                                me, cut.edge_finish, cut.finish_width / scale,
                                cut.finish_segments, cut.finish_profile))
                        results.append((t, me))
                    else:
                        cap = cut.split_cap and cut.line_cap
                        keep = cg.plane_split_mesh(t, a_near, normal, True, cap)
                        temp.append(keep)
                        other = cg.plane_split_mesh(t, a_near, normal, False, cap)
                        temp.append(other)
                        if cap:
                            for me in (keep, other):
                                line_bevel_counts.append(cg.finish_new_edges(
                                    me, cut.edge_finish, cut.finish_width / scale,
                                    cut.finish_segments, cut.finish_profile))
                        results.append((t, keep))
                        pieces.append((t, other))
                except cg.CutError as ex:
                    if len(targets) > 1 and 'does not cross' in str(ex):
                        continue
                    raise
            if not results:
                raise cg.CutError('The line does not cross any target; nothing was changed.')
            infos = [cg.commit_mesh(t, me, cut.shared_mesh) for t, me in results]
            for t, me in pieces:
                temp.remove(me)
                _make_piece(t, me).select_set(True)
            suffix = ''
            if cut.edge_finish != 'NONE' and cut.finish_width > 0:
                if not line_bevel_counts:
                    suffix = ' | Edge Finish skipped (cap disabled)'
                elif sum(line_bevel_counts) == 0:
                    suffix = ' | WARNING: Edge Finish found 0 cap boundary edges'
                else:
                    suffix = f' | {cut.edge_finish}: {sum(line_bevel_counts)} new boundary edges'
            return ('Plane split: ' if mode == 'SPLIT' else 'Plane cut: ') + \
                ', '.join(t.name for t, _ in results) + ''.join(sorted(set(infos))) + suffix
        finally:
            for me in temp:
                if me.users == 0:
                    bpy.data.meshes.remove(me)
    # Polyline: half-plane polygon prism through the Boolean pipeline.
    corners = []
    for co in cg.object_world_bounds(targets):
        p = projector.to_screen(co)
        if p is not None:
            corners.append(p)
    if not corners:
        raise cg.CutError('Targets are outside the view.')
    corners.extend(points)
    corners.append(side_xy)   # the clicked side must lie inside the half-plane box
    xs = [p[0] for p in corners]
    ys = [p[1] for p in corners]
    pad = max(80.0, 0.2 * max(max(xs) - min(xs), max(ys) - min(ys)))
    box = (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)
    half = side_polygon(points, box)
    if mode == 'CUT':
        clicked_inside = cg.point_in_loop(side_xy, half)
        if not clicked_inside:
            half = side_polygon(list(reversed(points)), box)
        # Removing the clicked half; Alt keeps it instead.
        return perform_closed(context, 'CUT', targets, [half], projector, invert=invert)
    return perform_closed(context, 'SPLIT', targets, [half], projector)


def perform_mask(context, target, loops, projector, erase):
    from . import mask_tools
    groups = cg.prepare_loops(loops)
    flat = [lp for outer, holes in groups for lp in [outer] + holes]
    changed, total = mask_tools.apply_mask_loops(context, target, flat, projector, erase)
    return f'Mask faces {"removed" if erase else "added"}: {changed} (total {total})'


# -----------------------------------------------------------------------------
# Drawing overlay
# -----------------------------------------------------------------------------

_COLORS = {
    'CUT': (1.0, 0.62, 0.10, 1.0),
    'CUT_INV': (0.25, 0.90, 1.0, 1.0),
    'SPLIT': (0.45, 1.0, 0.35, 1.0),
    'MASK': (0.85, 0.45, 1.0, 1.0),
    'MASK_INV': (0.55, 0.55, 0.60, 1.0),
}


def _shader():
    return gpu.shader.from_builtin('UNIFORM_COLOR')


def _draw_lines(sh, pts, color, closed=False, width=2.0):
    if len(pts) < 2:
        return
    seq = list(pts) + ([pts[0]] if closed else [])
    gpu.state.line_width_set(width)
    sh.bind()
    sh.uniform_float('color', color)
    batch_for_shader(sh, 'LINE_STRIP', {'pos': seq}).draw(sh)


def _draw_squares(sh, pts, color, size=4.0):
    if not pts:
        return
    tris = []
    for x, y in pts:
        a, b, c, d = (x - size, y - size), (x + size, y - size), (x + size, y + size), (x - size, y + size)
        tris.extend((a, b, c, a, c, d))
    sh.bind()
    sh.uniform_float('color', color)
    batch_for_shader(sh, 'TRIS', {'pos': tris}).draw(sh)


def _draw_fill(sh, loops, color):
    try:
        tris = tessellate_polygon([[(p[0], p[1], 0.0) for p in lp] for lp in loops if len(lp) >= 3])
    except Exception:
        return
    flat = [p for lp in loops if len(lp) >= 3 for p in lp]
    coords = [flat[i] for tri in tris for i in tri]
    if coords:
        sh.bind()
        sh.uniform_float('color', color)
        batch_for_shader(sh, 'TRIS', {'pos': coords}).draw(sh)


def draw_overlay(op):
    try:
        if bpy.context.region != op.region:
            return
    except ReferenceError:
        return
    sh = _shader()
    gpu.state.blend_set('ALPHA')
    try:
        key = op.mode + ('_INV' if op.inverted() and op.mode != 'SPLIT' else '')
        color = _COLORS.get(key, _COLORS['CUT'])
        fill = (color[0], color[1], color[2], 0.16)
        if op.stage == 'SIDE' and op.side_preview:
            _draw_fill(sh, [op.side_preview], (1.0, 0.25, 0.1, 0.22))
        loops = op.preview_loops()
        for lp in loops:
            _draw_lines(sh, lp, color, closed=op.preview_closed())
        if loops and op.preview_closed() and op.stage != 'SIDE':
            _draw_fill(sh, loops, fill)
        if op.stage in {'POINTS', 'SIDE'}:
            _draw_squares(sh, op.pts, (1, 1, 1, 0.9), 3.5)
            if op.pts:
                _draw_squares(sh, [op.pts[0]], color, 5.5 if op.near_first else 4.0)
            if op.shape == 'CURVE_LASSO' and len(op.pts) >= 3:
                handle_color = (0.3, 0.8, 1.0, 0.9)
                for i, r in enumerate(op.rounds):
                    if r > 0:
                        h0, h1 = corner_handles(op.pts, i, r)
                        _draw_lines(sh, [h0, op.pts[i], h1], handle_color, width=1.0)
                        _draw_squares(sh, [h0, h1], handle_color, 3.0)
    finally:
        gpu.state.line_width_set(1.0)
        gpu.state.blend_set('NONE')


# -----------------------------------------------------------------------------
# Operators
# -----------------------------------------------------------------------------


def exit_tool(context):
    try:
        bpy.ops.wm.tool_set_by_id(name='builtin.select_box', space_type='VIEW_3D')
    except RuntimeError as ex:
        print('[Mecha Lab] could not leave tool:', ex)


def open_popup(name):
    try:
        bpy.ops.wm.call_panel(name=name, keep_open=False)
    except RuntimeError as ex:
        print('[Mecha Lab] popup failed:', ex)


def _status(context, text):
    try:
        context.workspace.status_text_set(text)
    except (AttributeError, ReferenceError, TypeError):
        pass


def make_projector(region, rv3d):
    return cg.Projector(region, rv3d)


def add_draw_handler(op):
    return bpy.types.SpaceView3D.draw_handler_add(draw_overlay, (op,), 'WINDOW', 'POST_PIXEL')


def remove_draw_handler(handle):
    bpy.types.SpaceView3D.draw_handler_remove(handle, 'WINDOW')


def _now():
    return time.monotonic()


# Blender exposes double-click, but not a portable TRIPLE_CLICK event.
# Count distinct mouse-down events across individual (one-stroke) operators.
# A triple click must stay near the same screen position; clicking successive
# lasso vertices must never accidentally leave the Cut/Split/Mask tool.
_TRIPLE_STATE = {}
_TRIPLE_RADIUS_PX = 12.0
_TRIPLE_MAX_SECONDS = 0.72


def triple_click_to_select(context, event, clock=None):
    """Return True for a third quick LMB at the same viewport position.

    Event's DOUBLE_CLICK replaces PRESS on many Blender builds. Some OS/keymap
    configurations can deliver both events on one mouse down: the 25 ms
    duplicate filter prevents a phantom third click in that case.
    """
    if event.type != 'LEFTMOUSE' or event.value not in {'PRESS', 'DOUBLE_CLICK'}:
        return False
    if getattr(event, 'mouse_x', None) is None:
        return False
    if context.window is None or context.area is None:
        return False
    now = _now() if clock is None else clock
    try:
        key = (context.window.as_pointer(), context.area.as_pointer())
    except ReferenceError:
        return False
    pt = (float(event.mouse_x), float(event.mouse_y))
    state = _TRIPLE_STATE.get(key)
    double_time = max(0.32, min(_TRIPLE_MAX_SECONDS,
                                2.0 * _double_click_seconds(context)))
    if state:
        last_time, last_pt, count, last_type = state
        if (event.value == 'DOUBLE_CLICK' and last_type == 'PRESS' and
                now - last_time <= 0.025 and math.dist(pt, last_pt) <= 2.0):
            return False
        if now - last_time <= double_time and math.dist(pt, last_pt) <= _TRIPLE_RADIUS_PX:
            count += 1
        else:
            count = 1
    else:
        count = 1
    if count >= 3:
        _TRIPLE_STATE.pop(key, None)
        return True
    _TRIPLE_STATE[key] = (now, pt, count, event.value)
    return False


class StrokeLogic:
    """State machine of one shape stroke (plain Python so tests can drive it
    with simulated events; the Blender operator below only adds RNA)."""

    # ---- state helpers ---------------------------------------------------

    def inverted(self):
        return self.alt_latch or self.alt_held

    def preview_closed(self):
        if self.shape in {'LASSO', 'CURVE_LASSO'}:
            return not self._is_open_line()
        return True

    def _is_open_line(self):
        return self.shape == 'LASSO' and (self.line_open or len(self.pts) == 2 and self.stage == 'SIDE')

    def preview_loops(self):
        m = self.mouse
        if self.shape in {'LASSO', 'CURVE_LASSO'}:
            pts = list(self.pts)
            if self.stage == 'POINTS' and m is not None and self.drag_index is None and self.drag_handle is None:
                pts = pts + [self._snapped(m, self.shift_held)]
            if self.shape == 'CURVE_LASSO' and len(pts) >= 3:
                rounds = list(self.rounds) + [0.0] * (len(pts) - len(self.rounds))
                return [curve_lasso_loop(pts, rounds, self.brush.curve_resolution)]
            return [pts] if len(pts) >= 2 else []
        if self.shape == 'STROKE':
            return [self.pts] if len(self.pts) >= 2 else []
        if m is None or self.anchor is None:
            return []
        return self._drag_loops(m, self.ctrl_held, self.shift_held)

    def _drag_loops(self, m, ctrl, shift):
        b = self.brush
        if self.shape == 'RECT':
            return [rect_loop(self.anchor, m, shift, ctrl)]
        if self.shape == 'CIRCLE':
            return [circle_loop(self.anchor, m, b.circle_segments)]
        if self.shape == 'ELLIPSE':
            return [ellipse_loop(self.anchor, m, b.circle_segments, shift, ctrl)]
        if self.shape == 'CUSTOM':
            r = math.dist(self.anchor, m)
            angle = b.custom_rotation
            if r < 4.0:
                r = b.custom_size
            elif b.custom_drag_rotate:
                angle += math.atan2(m[1] - self.anchor[1], m[0] - self.anchor[0])
            return custom_loops(self.custom, self.anchor, r, angle)
        return []

    def _snapped(self, p, shift):
        if shift and self.pts:
            return snap45(self.pts[-1], p)
        return p

    def _region_xy(self, event):
        r = self.region
        x, y = event.mouse_x - r.x, event.mouse_y - r.y
        inside = 0 <= x < r.width and 0 <= y < r.height
        return (float(x), float(y)), inside

    # ---- lifecycle -----------------------------------------------------------

    def invoke(self, context, event):
        # The third LMB may be delivered to a fresh stroke operator after the
        # double-click finished the previous cut.  Check before adding points.
        if triple_click_to_select(context, event):
            exit_tool(context)
            return {'CANCELLED'}
        region = context.region
        if region is None or region.type != 'WINDOW':
            region = next((r for r in context.area.regions if r.type == 'WINDOW'), None)
        rv3d = context.region_data if context.region_data else context.space_data.region_3d
        if region is None or rv3d is None:
            return {'PASS_THROUGH'}
        self.region = region
        self.rv3d = rv3d
        self.projector = make_projector(region, rv3d)
        scene = context.scene
        self.brush = scene.mch_brush
        self.shape = self.brush.shape
        xy, inside = self._region_xy(event)
        if not inside:
            return {'PASS_THROUGH'}
        if self.mode == 'MASK' and self.shape == 'LASSO' and self.brush.line_open:
            self.brush.line_open = False
        targets = gather_targets(context, self.projector, xy, self.mode)
        if not targets:
            self.report({'WARNING'}, 'Click on a mesh or select one first')
            return {'PASS_THROUGH'}
        self.target_names = [t.name for t in targets]
        self.custom = None
        if self.shape == 'CUSTOM':
            from . import cut_presets
            try:
                self.custom = cut_presets.load_loops(scene.mch_png_preset)
            except (cg.CutError, ValueError, OSError) as ex:
                self.report({'WARNING'}, str(ex))
                return {'CANCELLED'}
        self.native_tool = ts.native_tool_id(context)
        self.pts, self.rounds, self.redo = [], [], []
        self.alt_latch = bool(event.alt)
        self.alt_held = bool(event.alt)
        self.shift_held = bool(event.shift)
        self.ctrl_held = bool(event.ctrl)
        self.line_open = bool(self.brush.line_open)
        self.mouse = xy
        self.anchor = None
        self.drag_index = None
        self.drag_handle = None
        self.press_xy = None
        self.near_first = False
        self.side_preview = None
        self.rmb_time = None
        self.timer = None
        if self.shape in {'LASSO', 'CURVE_LASSO'}:
            self.stage = 'POINTS'
            self._add_point(xy)
        else:
            self.stage = 'DRAG'
            self.anchor = xy
            if self.shape == 'STROKE':
                self.pts = [xy]
        self.handle = add_draw_handler(self)
        context.window_manager.modal_handler_add(self)
        self._hint(context)
        self.region.tag_redraw()
        return {'RUNNING_MODAL'}

    def _hint(self, context):
        if self.stage == 'SIDE':
            text = 'Click the side to REMOVE (Alt+click: keep it) | Esc cancel'
        elif self.stage == 'POINTS':
            text = ('LMB point | Enter/double-click/first point: apply | Backspace/Ctrl+Z: undo point | '
                    'Shift: 45° | Alt: invert | F: open line | RMB: shapes, RMB×2: exit | Esc: cancel')
            if self.shape == 'CURVE_LASSO':
                text = 'Click a point again: round it | drag point/handle | ' + text
        else:
            text = 'Drag, release to apply | Shift: square/circle | Ctrl: from center | Alt: invert | Esc: cancel'
        _status(context, f'MECHA {self.mode}: ' + text)

    def _cleanup(self, context):
        if getattr(self, 'handle', None) is not None:
            remove_draw_handler(self.handle)
            self.handle = None
        if getattr(self, 'timer', None) is not None:
            try:
                context.window_manager.event_timer_remove(self.timer)
            except (ReferenceError, ValueError):
                pass
            self.timer = None
        _status(context, None)
        try:
            self.region.tag_redraw()
        except ReferenceError:
            pass

    def _cancel(self, context):
        self._cleanup(context)
        return {'CANCELLED'}

    def cancel(self, context):
        self._cleanup(context)

    # ---- editing -----------------------------------------------------------

    def _add_point(self, xy):
        p = self._snapped(xy, self.shift_held)
        if self.pts and math.dist(p, self.pts[-1]) < 2.0:
            return
        self.pts.append(p)
        self.rounds.append(0.0)
        self.redo.clear()

    def _pop_point(self):
        if not self.pts:
            return False
        self.redo.append((self.pts.pop(), self.rounds.pop()))
        return True

    def _hit_point(self, xy):
        for i, p in enumerate(self.pts):
            if math.dist(p, xy) <= HIT_PX:
                return i
        return None

    def _hit_handle(self, xy):
        if self.shape != 'CURVE_LASSO' or len(self.pts) < 3:
            return None
        for i, r in enumerate(self.rounds):
            if r > 0:
                for h in corner_handles(self.pts, i, r):
                    if math.dist(h, xy) <= HIT_PX:
                        return i
        return None

    def _current_loops(self, event_ctrl=False, event_shift=False):
        if self.shape in {'LASSO', 'CURVE_LASSO'}:
            if self.shape == 'CURVE_LASSO':
                return [curve_lasso_loop(self.pts, self.rounds, self.brush.curve_resolution)]
            return [list(self.pts)]
        if self.shape == 'STROKE':
            pts = cg.simplify_open(self.pts, self.brush.stroke_simplify)
            return [cg.trim_closing_overlap(pts)]
        return self._drag_loops(self.mouse, event_ctrl, event_shift)

    # ---- execution ---------------------------------------------------------

    def _targets(self):
        return [bpy.data.objects[n] for n in self.target_names if n in bpy.data.objects]

    def _execute_closed(self, context):
        loops = self._current_loops(self.ctrl_held, self.shift_held)
        targets = self._targets()
        if self.mode == 'MASK':
            if self.shape == 'STROKE':
                from . import mask_tools
                points = cg.simplify_open(self.pts, self.brush.stroke_simplify)
                changed, total = mask_tools.apply_mask_stroke(
                    context, targets[0], points, self.projector,
                    self.brush.mask_brush_radius, self.inverted())
                msg = f'Mask stroke: {changed} faces changed ({total} masked total; entire faces, not exact outline)'
            else:
                msg = perform_mask(context, targets[0], loops, self.projector, self.inverted())
        else:
            msg = perform_closed(context, self.mode, targets, loops, self.projector, self.inverted())
        if self.shape == 'CUSTOM' and self.anchor is not None and self.mouse is not None:
            r = math.dist(self.anchor, self.mouse)
            if r >= 4.0:
                self.brush.custom_size = r
        return msg

    def _run(self, context, fn, keep_on_shape_error=False):
        try:
            msg = fn(context)
        except cg.CutError as ex:
            self.report({'WARNING'}, str(ex))
            if keep_on_shape_error and ('crosses itself' in str(ex) or 'too small' in str(ex)):
                return {'RUNNING_MODAL'}
            return self._cancel(context)
        except Exception as ex:  # unexpected: report, keep the scene intact
            traceback.print_exc()
            self.report({'ERROR'}, f'Mecha {self.mode} failed: {ex}')
            return self._cancel(context)
        self.report({'INFO'}, msg)
        self._cleanup(context)
        return {'FINISHED'}

    def _confirm(self, context):
        if self.shape in {'LASSO', 'CURVE_LASSO'}:
            if self.shape == 'LASSO' and len(self.pts) >= 2 and (self.line_open or len(self.pts) == 2):
                if self.mode == 'MASK':
                    self.report({'WARNING'}, 'Mask needs a closed outline (3+ points)')
                    return {'RUNNING_MODAL'}
                if self.mode == 'SPLIT':
                    return self._run(context, lambda c: perform_line(
                        c, 'SPLIT', self._targets(), self.pts, self.projector, self.pts[0]))
                self.stage = 'SIDE'
                self._update_side_preview()
                self._hint(context)
                return {'RUNNING_MODAL'}
            if len(self.pts) < 3:
                self.report({'WARNING'}, 'Place at least 3 points (2 points = line cut)')
                return {'RUNNING_MODAL'}
        return self._run(context, self._execute_closed, keep_on_shape_error=True)

    def _update_side_preview(self):
        self.side_preview = None
        try:
            corners = [self.projector.to_screen(c) for c in cg.object_world_bounds(self._targets())]
            corners = [c for c in corners if c is not None] + list(self.pts)
            if self.mouse:
                corners.append(self.mouse)
            xs = [p[0] for p in corners]
            ys = [p[1] for p in corners]
            pad = max(80.0, 0.2 * max(max(xs) - min(xs), max(ys) - min(ys)))
            box = (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)
            half = side_polygon(self.pts, box)
            if self.mouse and not cg.point_in_loop(self.mouse, half):
                half = side_polygon(list(reversed(self.pts)), box)
            self.side_preview = half
        except (cg.CutError, ValueError, ZeroDivisionError):
            pass

    # ---- modal ---------------------------------------------------------------

    def modal(self, context, event):
        try:
            return self._modal(context, event)
        except ReferenceError:
            # Undo from a menu / area closed while a stroke was pending: the
            # stored scene, brush or region no longer exists. Drop the stroke.
            try:
                self._cleanup(context)
            except ReferenceError:
                pass
            return {'CANCELLED'}
        except Exception as ex:
            traceback.print_exc()
            self.report({'ERROR'}, f'Mecha stroke aborted: {ex}')
            return self._cancel(context)

    def _modal(self, context, event):
        if not self._targets():
            return self._cancel(context)
        if self.native_tool and ts.native_tool_id(context) != self.native_tool:
            return self._cancel(context)          # tool switched from toolbar/list
        if context.scene.mch_brush.shape != self.shape:
            self.report({'INFO'}, 'Shape changed: unfinished stroke discarded')
            return self._cancel(context)

        et, ev = event.type, event.value
        if et == 'LEFTMOUSE' and ev in {'PRESS', 'DOUBLE_CLICK'} and \
                triple_click_to_select(context, event):
            self._cleanup(context)  # unfinished path must never be applied
            exit_tool(context)
            return {'CANCELLED'}
        if et in {'LEFT_ALT', 'RIGHT_ALT'}:
            self.alt_held = ev == 'PRESS'
        if et in {'LEFT_SHIFT', 'RIGHT_SHIFT'}:
            self.shift_held = ev == 'PRESS'
        if et in {'LEFT_CTRL', 'RIGHT_CTRL', 'OSKEY'}:
            self.ctrl_held = ev == 'PRESS'

        if et == 'TIMER':
            if self.rmb_time is not None and event_timer_matches(self, event):
                if _now() - self.rmb_time >= _double_click_seconds(context):
                    self.rmb_time = None
                    self._remove_timer(context)
                    open_popup(SHAPE_POPUP)
                return {'RUNNING_MODAL'}
            return {'PASS_THROUGH'}

        xy, inside = self._region_xy(event)
        if et in NAV_EVENTS or et.startswith('NDOF') or (et.startswith('NUMPAD_') and et != 'NUMPAD_ENTER'):
            return {'PASS_THROUGH'}

        if et == 'MOUSEMOVE' or et == 'INBETWEEN_MOUSEMOVE':
            if inside or self.stage == 'DRAG' or self.drag_index is not None:
                self.mouse = xy
                self._on_move(xy)
                self.region.tag_redraw()
            return {'RUNNING_MODAL'} if inside else {'PASS_THROUGH'}

        if not inside:
            if et == 'LEFTMOUSE' and ev == 'RELEASE' and (self.stage == 'DRAG' or self.drag_index is not None):
                pass   # finish a drag that ended over another region
            else:
                return {'PASS_THROUGH'}   # palette, sidebar, menus keep working

        if et == 'ESC' and ev == 'PRESS':
            return self._cancel(context)
        if et == 'SPACE' and ev == 'PRESS':
            self._cleanup(context)
            open_popup(TOOL_POPUP)
            return {'CANCELLED'}
        if et == 'RIGHTMOUSE' and ev in {'PRESS', 'DOUBLE_CLICK'}:
            now = _now()
            if ev == 'DOUBLE_CLICK' or (self.rmb_time is not None and
                                         now - self.rmb_time < _double_click_seconds(context)):
                self._cleanup(context)
                exit_tool(context)
                return {'CANCELLED'}
            self.rmb_time = now
            if self.timer is None:
                self.timer = context.window_manager.event_timer_add(0.04, window=context.window)
            return {'RUNNING_MODAL'}
        if et == 'RIGHTMOUSE':
            return {'RUNNING_MODAL'}

        if et == 'Z' and ev == 'PRESS' and (event.ctrl or event.oskey):
            if event.shift:
                if self.redo and self.stage == 'POINTS':
                    p, r = self.redo.pop()
                    self.pts.append(p)
                    self.rounds.append(r)
            elif self.stage == 'SIDE':
                self.stage = 'POINTS'
                self.side_preview = None
            elif not self._pop_point() or not self.pts:
                return self._cancel(context)
            self._hint(context)
            self.region.tag_redraw()
            return {'RUNNING_MODAL'}
        if et == 'Y' and ev == 'PRESS' and event.ctrl and self.redo and self.stage == 'POINTS':
            p, r = self.redo.pop()
            self.pts.append(p)
            self.rounds.append(r)
            self.region.tag_redraw()
            return {'RUNNING_MODAL'}
        if et == 'BACK_SPACE' and ev == 'PRESS':
            if self.stage == 'SIDE':
                self.stage = 'POINTS'
                self.side_preview = None
            elif not self._pop_point() or not self.pts:
                return self._cancel(context)
            self._hint(context)
            self.region.tag_redraw()
            return {'RUNNING_MODAL'}
        if et == 'F' and ev == 'PRESS' and self.shape == 'LASSO' and self.mode != 'MASK':
            self.line_open = not self.line_open
            self.brush.line_open = self.line_open
            self.region.tag_redraw()
            return {'RUNNING_MODAL'}
        if et in {'RET', 'NUMPAD_ENTER'} and ev == 'PRESS':
            if self.stage == 'SIDE':
                return self._apply_side(context, self.mouse or self.pts[0], event.alt)
            if self.stage == 'POINTS':
                return self._confirm(context)
            return {'RUNNING_MODAL'}

        if et == 'LEFTMOUSE':
            if ev in {'PRESS', 'DOUBLE_CLICK'} and event.alt:
                self.alt_latch = True
            return self._on_lmb(context, ev, xy, event)
        if et in {'LEFT_ALT', 'RIGHT_ALT', 'LEFT_SHIFT', 'RIGHT_SHIFT', 'LEFT_CTRL', 'RIGHT_CTRL'}:
            self.region.tag_redraw()
            return {'RUNNING_MODAL'}
        # Swallow other keys while a stroke is pending so a stray hotkey cannot
        # delete or transform the target halfway through.
        return {'RUNNING_MODAL'}

    def _on_move(self, xy):
        if self.stage == 'DRAG' and self.shape == 'STROKE':
            if not self.pts or math.dist(self.pts[-1], xy) >= self.brush.stroke_spacing:
                self.pts.append(xy)
        elif self.stage == 'POINTS':
            if self.drag_index is not None:
                if math.dist(xy, self.press_xy) > 3.0:
                    self.pts[self.drag_index] = xy
            elif self.drag_handle is not None:
                i = self.drag_handle
                p = self.pts[i]
                a = self.pts[i - 1]
                ref = max(math.dist(p, a), 1e-6)
                self.rounds[i] = max(0.0, min(0.5, math.dist(p, xy) / ref))
            self.near_first = len(self.pts) >= 3 and math.dist(self.pts[0], xy) <= HIT_PX
        elif self.stage == 'SIDE':
            self._update_side_preview()

    def _apply_side(self, context, xy, alt):
        invert = alt or self.inverted()
        return self._run(context, lambda c: perform_line(
            c, 'CUT', self._targets(), self.pts, self.projector, xy, invert))

    def _on_lmb(self, context, ev, xy, event):
        if self.stage == 'SIDE':
            if ev == 'PRESS':
                return self._apply_side(context, xy, event.alt)
            return {'RUNNING_MODAL'}
        if self.stage == 'DRAG':
            if ev == 'RELEASE':
                if self.shape in {'RECT', 'CIRCLE', 'ELLIPSE'} and \
                        math.dist(self.anchor, xy) < 4.0:
                    return self._cancel(context)    # a click, not a drag
                self.mouse = xy
                if self.shape == 'STROKE':
                    if len(self.pts) < (1 if self.mode == 'MASK' else 3):
                        return self._cancel(context)
                return self._run(context, self._execute_closed)
            return {'RUNNING_MODAL'}
        # POINTS
        if ev == 'DOUBLE_CLICK':
            return self._confirm(context)
        if ev == 'PRESS':
            handle = self._hit_handle(xy)
            if handle is not None:
                self.drag_handle = handle
                return {'RUNNING_MODAL'}
            hit = self._hit_point(xy)
            if hit == 0 and len(self.pts) >= 3 and not self.line_open:
                return self._confirm(context)
            if hit is not None and (hit != len(self.pts) - 1 or self.shape == 'CURVE_LASSO'):
                self.drag_index = hit
                self.press_xy = xy
                return {'RUNNING_MODAL'}
            self.shift_held = bool(event.shift)
            self._add_point(xy)
            self.region.tag_redraw()
            return {'RUNNING_MODAL'}
        if ev == 'RELEASE':
            if self.drag_index is not None:
                moved = math.dist(xy, self.press_xy) > 3.0
                if not moved and self.shape == 'CURVE_LASSO':
                    i = self.drag_index
                    cur = self.rounds[i]
                    idx = min(range(len(ROUND_LEVELS)), key=lambda k: abs(ROUND_LEVELS[k] - cur))
                    self.rounds[i] = ROUND_LEVELS[(idx + 1) % len(ROUND_LEVELS)]
                self.drag_index = None
            self.drag_handle = None
            self.region.tag_redraw()
        return {'RUNNING_MODAL'}

    def _remove_timer(self, context):
        if self.timer is not None:
            context.window_manager.event_timer_remove(self.timer)
            self.timer = None


class MCH_OT_cut_stroke(StrokeLogic, bpy.types.Operator):
    bl_idname = 'mch.cut_stroke'
    bl_label = 'Mecha Shape Stroke'
    bl_description = 'Draw one shape with the shared shape palette and Cut / Split / Mask with it'
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(name='Mode', items=[
        ('CUT', 'Cut', 'Remove the inside (Alt: keep inside)'),
        ('SPLIT', 'Split', 'Split into two parts'),
        ('MASK', 'Mask', 'Add face mask (Alt: erase)')], default='CUT')

    @classmethod
    def poll(cls, context):
        return (context.area is not None and context.area.type == 'VIEW_3D'
                and context.mode == 'OBJECT')


def _double_click_seconds(context):
    try:
        return max(0.15, context.preferences.inputs.mouse_double_click_time / 1000.0)
    except AttributeError:
        return 0.35


def event_timer_matches(op, event):
    # Event timers are not exposed on the event; any TIMER event while our timer
    # exists is good enough because we only compare elapsed wall-clock time.
    return op.timer is not None


class GateLogic:
    """RMB in an idle Mecha tool: single = shape popup, double = leave the tool."""

    def invoke(self, context, event):
        self.t0 = _now()
        self.timer = context.window_manager.event_timer_add(0.04, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _stop(self, context):
        if self.timer is not None:
            context.window_manager.event_timer_remove(self.timer)
            self.timer = None

    def modal(self, context, event):
        if event.type == 'RIGHTMOUSE' and event.value in {'PRESS', 'DOUBLE_CLICK'}:
            self._stop(context)
            exit_tool(context)
            return {'FINISHED'}
        if event.type == 'TIMER' and _now() - self.t0 >= _double_click_seconds(context):
            self._stop(context)
            open_popup(SHAPE_POPUP)
            return {'FINISHED'}
        if event.type == 'ESC':
            self._stop(context)
            return {'CANCELLED'}
        return {'PASS_THROUGH'}

    def cancel(self, context):
        self._stop(context)


class MCH_OT_rmb_gate(GateLogic, bpy.types.Operator):
    """RMB in an idle Mecha tool: single = shape popup, double = leave the tool."""
    bl_idname = 'mch.rmb_gate'
    bl_label = 'Mecha RMB (Shapes / Exit)'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D'


CLASSES = (MCH_OT_cut_stroke, MCH_OT_rmb_gate)
