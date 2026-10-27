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
import sys
import time
import traceback

import bmesh
import bpy
import gpu
from bpy.props import EnumProperty, FloatProperty, IntProperty
from gpu_extras.batch import batch_for_shader
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

from . import core_geometry as cg
from . import tool_state as ts

SHAPE_POPUP = 'MCH_PT_shape_popup'
TOOL_POPUP = 'MCH_PT_tool_popup'
PROFILE_POPUP = 'MCH_PT_profile_popup'
DUP_PX = 4.0          # clicks closer than this are the same point
HIT_PX = 9.0
CLOSE_PX = 14.0       # start-point snap radius (x UI scale)
DBL_PX = 8.0          # own double-click detection radius (x UI scale)
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


def curve_tangents(points, sharp, overrides, smoothness=1.0, closed=True):
    """Per-point tangents of the Curve Lasso spline (Catmull-Rom by default).

    ``sharp[i]`` makes a corner (zero tangent); ``overrides[i]`` is a tangent
    set by dragging that point's Bezier handle (aligned, symmetric handles).
    """
    n = len(points)
    out = []
    for i in range(n):
        ov = overrides[i] if i < len(overrides) else None
        if ov is not None:
            out.append(ov)
            continue
        if i < len(sharp) and sharp[i]:
            out.append((0.0, 0.0))
            continue
        if closed or 0 < i < n - 1:
            a, b = points[i - 1], points[(i + 1) % n]
        elif i == 0:
            a, b = points[0], points[min(1, n - 1)]
        else:
            a, b = points[max(n - 2, 0)], points[n - 1]
        out.append(((b[0] - a[0]) * 0.5 * smoothness, (b[1] - a[1]) * 0.5 * smoothness))
    return out


def curve_handles(points, tangents, i):
    """(incoming, outgoing) Bezier handle positions of control point ``i``."""
    p, t = points[i], tangents[i]
    return ((p[0] - t[0] / 3.0, p[1] - t[1] / 3.0), (p[0] + t[0] / 3.0, p[1] + t[1] / 3.0))


ROUND_LEVELS = (0.0, 0.12, 0.25, 0.42)   # straight -> soft -> medium -> strong -> straight (v0.7.2)


def corner_handles(points, i, r):
    """The two handle points of a rounded Curve Lasso corner (fraction r of each edge)."""
    p = points[i]
    a = points[i - 1]
    b = points[(i + 1) % len(points)]
    return ((p[0] + (a[0] - p[0]) * r, p[1] + (a[1] - p[1]) * r),
            (p[0] + (b[0] - p[0]) * r, p[1] + (b[1] - p[1]) * r))


def curve_lasso_loop(points, rounds, resolution):
    """Closed outline with per-point quadratic Bezier rounding (v0.7.2 Curve
    Lasso): a point with round 0 is a straight corner."""
    n = len(points)
    if n < 3:
        return list(points)
    out = []
    res = max(2, int(resolution))
    for i in range(n):
        r = rounds[i] if i < len(rounds) else 0.0
        p = points[i]
        if r <= 1e-6:
            out.append(p)
            continue
        h0, h1 = corner_handles(points, i, r)
        for k in range(res + 1):
            t = k / res
            u = 1 - t
            out.append((u * u * h0[0] + 2 * u * t * p[0] + t * t * h1[0],
                        u * u * h0[1] + 2 * u * t * p[1] + t * t * h1[1]))
    return out


def next_round_level(cur):
    idx = min(range(len(ROUND_LEVELS)), key=lambda k: abs(ROUND_LEVELS[k] - cur))
    return ROUND_LEVELS[(idx + 1) % len(ROUND_LEVELS)]


def curve_lasso_spline(points, sharp=(), overrides=(), resolution=12, smoothness=1.0, closed=True):
    """Smooth closed outline through the control points (cubic Bezier spans)."""
    n = len(points)
    if n < 2 or (closed and n < 3):
        return list(points)
    tangents = curve_tangents(points, list(sharp), list(overrides), smoothness, closed)
    res = max(1, int(resolution))
    out = []
    spans = n if closed else n - 1
    for i in range(spans):
        p0, p1 = points[i], points[(i + 1) % n]
        c0 = curve_handles(points, tangents, i)[1]
        c1 = curve_handles(points, tangents, (i + 1) % n)[0]
        for k in range(res):
            t = k / res
            u = 1.0 - t
            out.append((u * u * u * p0[0] + 3 * u * u * t * c0[0] + 3 * u * t * t * c1[0] + t * t * t * p1[0],
                        u * u * u * p0[1] + 3 * u * u * t * c0[1] + 3 * u * t * t * c1[1] + t * t * t * p1[1]))
    if not closed:
        out.append(points[-1])
    return out


def round_corners(loop, radius, mode='ROUND', segments=6):
    """2D outline corner rounding / chamfer (shape option, NOT the 3D edge finish)."""
    n = len(loop)
    if mode == 'NONE' or radius <= 0 or n < 3:
        return list(loop)
    out = []
    for i in range(n):
        p, a, b = loop[i], loop[i - 1], loop[(i + 1) % n]
        la, lb = math.dist(p, a), math.dist(p, b)
        if la < 1e-6 or lb < 1e-6:
            out.append(p)
            continue
        d = min(radius, 0.45 * la, 0.45 * lb)
        cross = (a[0] - p[0]) * (b[1] - p[1]) - (a[1] - p[1]) * (b[0] - p[0])
        if d < 0.5 or abs(cross) < 1e-6 * la * lb:   # tiny or straight-through point
            out.append(p)
            continue
        h0 = (p[0] + (a[0] - p[0]) * d / la, p[1] + (a[1] - p[1]) * d / la)
        h1 = (p[0] + (b[0] - p[0]) * d / lb, p[1] + (b[1] - p[1]) * d / lb)
        if mode == 'CHAMFER':
            out.extend((h0, h1))
            continue
        for k in range(segments + 1):
            t = k / segments
            u = 1 - t
            out.append((u * u * h0[0] + 2 * u * t * p[0] + t * t * h1[0],
                        u * u * h0[1] + 2 * u * t * p[1] + t * t * h1[1]))
    return out


def smooth_open(points, iterations=2):
    """Moving-average smoothing of a freehand path (ends fixed)."""
    pts = list(points)
    for _ in range(max(0, int(iterations))):
        if len(pts) < 3:
            break
        pts = [pts[0]] + [((pts[i - 1][0] + 2 * pts[i][0] + pts[i + 1][0]) / 4.0,
                           (pts[i - 1][1] + 2 * pts[i][1] + pts[i + 1][1]) / 4.0)
                          for i in range(1, len(pts) - 1)] + [pts[-1]]
    return pts


def clean_clicks(points, dup_px=4.0, closed=True):
    """Drop near-duplicate consecutive points (PRESS + DOUBLE_CLICK on one mouse
    down) and a last point that sits on the first, so no zero-length edge."""
    out = []
    for p in points:
        if not out or math.dist(p, out[-1]) > dup_px:
            out.append(p)
    if closed:
        while len(out) > 3 and math.dist(out[0], out[-1]) <= dup_px:
            out.pop()
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
    from . import target_rules
    origin, direction = projector.ray(xy)
    dg = context.evaluated_depsgraph_get()
    hit, _loc, _n, _i, ob, _m = target_rules.scene_ray(context, dg, origin, direction)
    if hit and ob is not None and ob.type == 'MESH':
        original = ob.original
        # The mask preview is a selectable-disabled overlay, not a target mesh.
        # It may still be returned by a scene ray-cast after a mask stroke.
        source_name = original.get('mch_preview_source')
        if source_name:
            return bpy.data.objects.get(source_name)
        return original
    return None


def _auto_candidate(ob):
    if ob.type != 'MESH' or not ob.visible_get() or ob.hide_select:
        return False
    if ob.get('mch_cut_carrier') or ob.get('mch_preview_source') or ob.display_type in {'WIRE', 'BOUNDS'}:
        return False
    return not ob.name.startswith(('MCH_Cutter', 'MCH_GapIn', 'MCH_GapOut'))


def _loop_samples(loops, step=18.0, grid=7):
    """Screen points that represent the drawn area: outline samples + an inner grid."""
    pts = []
    for lp in loops:
        n = len(lp)
        for i in range(n):
            a, b = lp[i], lp[(i + 1) % n]
            k = max(1, int(math.dist(a, b) / step))
            pts.extend((a[0] + (b[0] - a[0]) * t / k, a[1] + (b[1] - a[1]) * t / k) for t in range(k))
    allp = [p for lp in loops for p in lp]
    if allp:
        x0, y0 = min(p[0] for p in allp), min(p[1] for p in allp)
        x1, y1 = max(p[0] for p in allp), max(p[1] for p in allp)
        for i in range(grid):
            for j in range(grid):
                p = (x0 + (x1 - x0) * (i + 0.5) / grid, y0 + (y1 - y0) * (j + 0.5) / grid)
                if cg.point_in_loops(p, loops):
                    pts.append(p)
    return pts


def auto_targets(view_layer, projector, loops):
    """Auto Target: the meshes the drawn screen shape really covers (any selection
    is ignored).  Projected bounds pre-filter, then rays through outline / inner
    sample points, or the object's centre inside the shape."""
    loops = [lp for lp in loops if len(lp) >= 2]
    if not loops:
        return []
    allp = [p for lp in loops for p in lp]
    lx0, ly0 = min(p[0] for p in allp), min(p[1] for p in allp)
    lx1, ly1 = max(p[0] for p in allp), max(p[1] for p in allp)
    samples = None
    out = []
    for ob in view_layer.objects:
        if ob is None or not _auto_candidate(ob):      # 0.24.3 a just-removed temporary object leaves None
            continue
        corners = [projector.to_screen(c) for c in cg.object_world_bounds([ob])]
        corners = [c for c in corners if c is not None]
        if not corners:
            continue
        bx0, by0 = min(c[0] for c in corners), min(c[1] for c in corners)
        bx1, by1 = max(c[0] for c in corners), max(c[1] for c in corners)
        if bx1 < lx0 or bx0 > lx1 or by1 < ly0 or by0 > ly1:
            continue
        centre = projector.to_screen(ob.matrix_world.translation)
        if centre is not None and len(loops[0]) >= 3 and cg.point_in_loops(centre, loops):
            out.append(ob)
            continue
        if samples is None:
            samples = _loop_samples(loops)
        inv = ob.matrix_world.inverted_safe()
        rot = inv.to_3x3()
        for p in samples:
            if not (bx0 <= p[0] <= bx1 and by0 <= p[1] <= by1):
                continue
            o, d = projector.ray(p)
            ok = ob.ray_cast(inv @ o, (rot @ d).normalized())[0]
            if ok:
                out.append(ob)
                break
    return out


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


def offset_loop(loop, d):
    """Offset a closed 2D loop by ``d`` px to the right of its direction.

    With the usual orientation (outlines CCW, holes CW) positive ``d`` grows
    the filled region and negative ``d`` shrinks it.  Miter joins, with a
    two-point bevel join at very sharp corners.
    """
    n = len(loop)
    out = []
    for i in range(n):
        p0, p1, p2 = loop[i - 1], loop[i], loop[(i + 1) % n]
        e1 = (p1[0] - p0[0], p1[1] - p0[1])
        e2 = (p2[0] - p1[0], p2[1] - p1[1])
        l1, l2 = math.hypot(*e1), math.hypot(*e2)
        if l1 < 1e-9 or l2 < 1e-9:
            continue
        n1 = (e1[1] / l1, -e1[0] / l1)
        n2 = (e2[1] / l2, -e2[0] / l2)
        m = (n1[0] + n2[0], n1[1] + n2[1])
        ml = math.hypot(*m)
        cos_half = ml / 2.0
        if ml < 1e-9 or cos_half < 0.35:      # very sharp corner: bevel join
            out.append((p1[0] + n1[0] * d, p1[1] + n1[1] * d))
            out.append((p1[0] + n2[0] * d, p1[1] + n2[1] * d))
            continue
        k = d / cos_half
        out.append((p1[0] + m[0] / ml * k, p1[1] + m[1] / ml * k))
    return out


def pixels_per_unit(projector, targets):
    """Screen pixels per model unit at the targets' centre depth (exact in ortho)."""
    pts = cg.object_world_bounds(targets)
    centre = sum(pts, Vector()) / len(pts)
    v = projector.view_dir.orthogonal().normalized()
    a, b = projector.to_screen(centre), projector.to_screen(centre + v)
    if a is None or b is None:
        raise cg.CutError('Targets are outside the view.')
    return max(math.dist(a, b), 1e-9)


def _gap_groups(groups, d):
    loops = [offset_loop(lp, d) for outer, holes in groups for lp in [outer] + list(holes)]
    try:
        return cg.prepare_loops(loops)
    except cg.CutError:
        raise cg.CutError('Gap Width is too large for this outline (offset outline overlaps itself); '
                          'use a smaller Gap Width or a simpler shape.')


def _finish_side(cut, me, side, scale):
    mode = getattr(cut, f'side_{side}_finish')
    if mode == 'NONE':
        return 0
    return cg.finish_new_edges(me, mode, getattr(cut, f'side_{side}_width') / scale,
                               getattr(cut, f'side_{side}_segments'), 0.5,
                               clamp=getattr(cut, 'finish_clamp', True), label='Side ' + side.upper(),
                               crisp=getattr(cut, 'finish_crisp', True))


def _gn_on(cut, side=None):
    """0.24.41 the GN Edge menu is on (for this Split side)."""
    if getattr(cut, 'gn_finish', 'NONE') == 'NONE' or getattr(cut, 'gn_width', 0.0) <= 0:
        return False
    return side is None or cut.gn_sides in {'BOTH', side.upper()}


def _gn_finish(cut, me, scale):
    from . import rim_sweep
    return rim_sweep.finish(me, cut.gn_finish, cut.gn_width / scale, cut.gn_segments)


def _side_report(cut, counts):
    parts = []
    for side, label in (('a', 'A'), ('b', 'B')):
        mode = getattr(cut, f'side_{side}_finish')
        if mode != 'NONE':
            parts.append(f'{label} {mode.lower()}: {counts.get(side, 0)} edges')
    return (' | ' + ', '.join(parts)) if parts else ''


def _with_finish_notes(fn):
    """B10: append 'width limited' notes of the bevels to the report string."""
    def wrapper(*args, **kwargs):
        cg.FINISH_NOTES.clear()
        msg = fn(*args, **kwargs)
        notes = list(dict.fromkeys(cg.FINISH_NOTES))
        cg.FINISH_NOTES.clear()
        return msg + (' | ' + '; '.join(notes) if notes else '')
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper


def _addon_version():
    pkg = sys.modules.get(__package__)
    v = getattr(pkg, 'bl_info', {}).get('version', ())
    return '.'.join(str(x) for x in v) or '?'


def _leave_edit_mode(context, targets):
    """Booleans and mesh commits need Object Mode (to_mesh fails on an edit mesh)."""
    if not any(t.mode == 'EDIT' for t in targets):
        return
    try:
        bpy.ops.object.mode_set(mode='OBJECT')
    except RuntimeError:
        pass
    for t in targets:
        if t.mode == 'EDIT':
            t.update_from_editmode()


def cut_diagnosis(target, groups, projector, near, far, invert):
    """One-line facts about a failed cut: how much of the object the drawn
    shape really covers (screen loop + depth range), the loop in pixels, the
    view type, Alt state and the running add-on version."""
    loops = [lp for outer, holes in groups for lp in [outer] + list(holes)]
    xs = [p[0] for lp in loops for p in lp]
    ys = [p[1] for lp in loops for p in lp]
    vd = projector.view_dir
    lo, hi = sorted((near.dot(vd), far.dot(vd)))
    mw = target.matrix_world
    verts = target.data.vertices
    step = max(1, len(verts) // 2000)
    inside = total = 0
    for i in range(0, len(verts), step):
        co = mw @ verts[i].co
        total += 1
        sc = projector.to_screen(co)
        if sc is not None and lo - 1e-6 <= co.dot(vd) <= hi + 1e-6 and cg.point_in_loops(sc, loops):
            inside += 1
    reg = getattr(projector, 'region', None)
    size = f'{reg.width}x{reg.height}' if reg is not None else '?'
    return inside, total, (f'shape covers {inside}/{total} vertices of {target.name} | shape px '
                           f'({min(xs):.0f},{min(ys):.0f})-({max(xs):.0f},{max(ys):.0f}) in {size} | '
                           f'{"PERSP" if projector.is_perspective else "ORTHO"} | '
                           f'{"Alt/invert ON" if invert else "Alt/invert off"} | Mecha Lab {_addon_version()}')


def _boolean_checked(context, cut, t, cutter, op, groups, projector, near, far, invert):
    """boolean_result + a precise explanation when the result would be empty."""
    try:
        return cg.boolean_result(context, t, cutter, op, cut.solver, cut.hole_tolerant)
    except cg.CutError as ex:
        if 'whole object' not in str(ex) and 'does not intersect' not in str(ex):
            raise
        inside, total, facts = cut_diagnosis(t, groups, projector, near, far, invert)
        if 'does not intersect' in str(ex):          # 0.24.58 the quick box test says so before any Boolean
            msg = f'The shape does not intersect "{t.name}"; nothing was changed. [{facts}]'
        elif op == 'DIFFERENCE' and total and inside == total:
            msg = (f'The drawn shape covers the whole of "{t.name}", so cutting would delete all of it; '
                   f'nothing was changed. Draw over only part of the object. [{facts}]')
        elif op == 'INTERSECT' and inside == 0:
            msg = f'The shape does not intersect "{t.name}"; nothing was changed. [{facts}]'
        else:
            msg = f'{ex} [{facts}]'
        print('[Mecha Lab] cut failed:', msg)
        raise cg.CutError(msg) from None


def _confirm_fuse(context, targets):
    """0.24.12 a live Smart Fuse preview is baked before it is cut: the cut works on the base mesh, and the
    hidden fuse source was joined back in afterwards (the cut looked broken)."""
    from . import fuse_confirm_live
    try:
        fuse_confirm_live(context, targets)
    except RuntimeError as ex:
        raise cg.CutError(str(ex)) from ex


def cut_ramp(context, targets, loops, projector, edge=None, live=True):
    """0.24.46 Cut with GN Edge > Ramp: the drawn shape carved on a slope (the Base Mesh Alt: Ramp carve) - deepest
    (Cut Depth) at the first side drawn (or ``edge``), rising back to the surface; GN Edge Chamfer / Bevel shape
    the deep wall.  Stays live on one target (the deep side can change after).  Returns a report."""
    from types import SimpleNamespace
    from . import ramp_edit
    from . import surface_draw as sd
    cut = context.scene.mch_cut
    groups = cg.prepare_loops(loops)
    if not groups:
        raise cg.CutError('The outline is empty.')
    if edge is None:
        segs = ramp_edit.sides(loops[0]) if len(loops[0]) >= 3 else []
        if not segs:
            raise cg.CutError('Ramp: draw a shape with at least one clear edge.')
        edge = segs[0]
    depth = max(cut.depth, 1e-5)
    fin = getattr(cut, 'gn_finish', 'NONE')
    st = SimpleNamespace(profile={'CHAMFER': 'CHAMFER', 'BEVEL': 'BEVEL'}.get(fin, 'SQUARE'), edge=0.35, sink=0.0,
                         edge_abs=cut.gn_width if fin != 'NONE' else None, fill_res=28,
                         segments=getattr(cut, 'gn_segments', 4), fine=getattr(cut, 'gn_ramp_res', 20) / 28.0)
    ramp = (edge[0], edge[1], getattr(cut, 'gn_ramp_length', 1.0), getattr(cut, 'gn_ramp_soft', 0.5))
    if live and len(targets) == 1:
        ramp_edit.begin(context, targets[0], loops, projector, kind='cut')
    done, failed = [], []
    for t in targets:
        try:
            sd.carve_area(context, t, groups, projector, st, depth, False, ramp=ramp)
            done.append(t.name)
        except (cg.CutError, RuntimeError) as ex:
            if len(targets) == 1:
                if live:
                    ramp_edit.finish(t)
                raise
            failed.append(f'{t.name} ({str(ex).splitlines()[0][:60]})')
    if not done:
        raise cg.CutError('Ramp: nothing was carved. ' + '; '.join(failed))
    if live and len(targets) == 1:
        ramp_edit.stamp(targets[0])               # 0.24.53 later edits are noticed (not thrown away)
    return (f'Cut Ramp: {", ".join(done)} | {depth:.3g} deep at one side, up to the surface '
            '(deep side: < > / Pick Edge in GN Edge)' + (' | failed: ' + '; '.join(failed) if failed else ''))


@_with_finish_notes
def perform_closed(context, mode, targets, loops, projector, invert=False):
    """Cut / Split all targets with closed screen loops. Returns a report string."""
    scene = context.scene
    cut = scene.mch_cut
    auto_apply = scene.mch_settings.auto_apply if hasattr(scene, 'mch_settings') else True
    if mode == 'CUT' and not invert and auto_apply and getattr(cut, 'gn_ramp', False):
        _leave_edit_mode(context, targets)
        for t in targets:
            cg.check_target(t)
        return cut_ramp(context, targets, loops, projector)          # 0.24.46 GN Edge > Ramp
    groups = cg.prepare_loops(loops)
    _leave_edit_mode(context, targets)
    _confirm_fuse(context, targets)
    from . import station_primitive
    frozen = [t.name for t in targets if station_primitive.freeze(t)]
    baked = [t.name for t in targets if cg.ensure_real_mesh(context, t)]
    for t in targets:
        cg.check_target(t)
    broken = {t.name: n for t in targets for n in (cg.overlap_edges(t),) if any(n)}     # 0.24.21
    try:
        report = _perform_closed(context, mode, targets, groups, projector, invert, cut, auto_apply, baked, frozen)
    except cg.CutError as ex:
        if broken:
            hints = ' '.join(cg.overlap_hint(bpy.data.objects[n], c) for n, c in broken.items() if n in bpy.data.objects)
            raise cg.CutError(f'{hints} ({str(ex).splitlines()[0][:120]})') from ex
        raise
    if broken:
        report += ' | WARNING: ' + '; '.join(f'{n} is not one clean solid ({c[0]} edges shared by 3+ faces, {c[1]} open '
                                            'edges) - the result may be broken; Remesh it first'
                                            for n, c in broken.items())
    return report


def _perform_closed(context, mode, targets, groups, projector, invert, cut, auto_apply, baked, frozen):
    near, far = _planes(context, targets, projector, [g[0] for g in groups])
    gap = mode == 'SPLIT' and cut.split_mode == 'GAP' and cut.gap_width > 0
    if gap and not auto_apply:
        raise cg.CutError('Gap Split needs Auto Apply ON (live cutters support Normal Split only).')
    cutter_out = None
    if gap:
        half_px = 0.5 * cut.gap_width * pixels_per_unit(projector, targets)
        inner_groups = _gap_groups(groups, -half_px)
        outer_groups = _gap_groups(groups, half_px)
        cutter = cg.link_temp_object(context, cg.build_cutter_mesh(inner_groups, projector, near, far, 'MCH_GapIn'))
        try:
            cutter_out = cg.link_temp_object(
                context, cg.build_cutter_mesh(outer_groups, projector, near, far, 'MCH_GapOut'))
        except Exception:
            cg.remove_object_and_mesh(cutter)
            raise
    else:
        cutter_mesh = cg.build_cutter_mesh(groups, projector, near, far, 'MCH_CutterMesh')
        cutter = cg.link_temp_object(context, cutter_mesh)
    from . import radial_sym                 # 0.24.33 a radially symmetric target: every copy is cut
    cutter = radial_sym.replicate_cutter(context, targets, cutter)
    cutter_out = radial_sym.replicate_cutter(context, targets, cutter_out)
    if not auto_apply:
        return _make_live(context, mode, targets, cutter, invert)
    results, pieces, temp = [], [], []
    solvers = []
    t_start = time.perf_counter()
    edge_counts = []
    side_counts = {}
    skipped, failed = [], []
    try:
        for t in targets:
            scale = _object_scale(t)
            try:
                if mode == 'CUT':
                    op = 'INTERSECT' if invert else 'DIFFERENCE'
                    me, _solver = _boolean_checked(context, cut, t, cutter, op, groups, projector, near, far,
                                                   invert)
                    solvers.append(_solver)
                    temp.append(me)
                    if _gn_on(cut):
                        edge_counts.append(_gn_finish(cut, me, scale))
                    else:
                        edge_counts.append(cg.finish_new_edges(
                            me, cut.edge_finish, cut.finish_width / scale,
                            cut.finish_segments, cut.finish_profile, clamp=cut.finish_clamp,
                            crisp=cut.finish_crisp))
                    results.append((t, me))
                else:  # SPLIT
                    inner, _s1 = _boolean_checked(context, cut, t, cutter, 'INTERSECT',
                                                  inner_groups if gap else groups, projector, near, far, False)
                    temp.append(inner)
                    outer, _s2 = _boolean_checked(context, cut, t, cutter_out or cutter, 'DIFFERENCE',
                                                  outer_groups if gap else groups, projector, near, far, False)
                    solvers += [_s1, _s2]
                    temp.append(outer)
                    # Side A = remaining original object, Side B = the new "_Split" piece.
                    for me, side in ((outer, 'a'), (inner, 'b')):
                        if cut.split_cap and _gn_on(cut, side):
                            side_counts[side] = side_counts.get(side, 0) + _gn_finish(cut, me, scale)
                        elif cut.split_cap:
                            side_counts[side] = side_counts.get(side, 0) + _finish_side(cut, me, side, scale)
                        else:
                            cg.strip_cutter_faces(me)
                    results.append((t, outer))
                    pieces.append((t, inner))
            except (cg.CutError, RuntimeError) as ex:
                if len(targets) == 1:
                    raise
                # F01: several targets - a failing one stays unchanged and is listed.
                (skipped if 'does not intersect' in str(ex) else failed).append(
                    t.name if 'does not intersect' in str(ex) else f'{t.name} ({str(ex).splitlines()[0][:70]})')
        if not results:
            raise cg.CutError('The shape does not intersect any target; nothing was changed.' +
                              (' Failed: ' + '; '.join(failed) if failed else ''))
        infos = []
        for t, me in results:
            infos.append(cg.commit_mesh(t, me, cut.shared_mesh))
        new_pieces = []
        for t, me in pieces:
            temp.remove(me)
            new_pieces.append(_make_piece(t, me))
        for p in new_pieces:
            p.select_set(True)
        verb = {'CUT': 'Kept inside' if invert else 'Cut',
                'SPLIT': ('Gap split' if gap else 'Split')}[mode]
        suffix = ''
        if mode == 'SPLIT':
            suffix = _side_report(cut, side_counts) if cut.split_cap else ''
        elif _gn_on(cut):
            suffix = (f' | GN {cut.gn_finish.title()}: {sum(edge_counts)} border edges' if sum(edge_counts)
                      else ' | WARNING: GN Edge found no new border edges')
        elif cut.edge_finish != 'NONE' and cut.finish_width > 0:
            if not edge_counts:
                suffix = ' | Edge Finish skipped (uncapped or Live cut)'
            elif sum(edge_counts) == 0:
                suffix = ' | WARNING: Edge Finish found 0 new edges; no bevel/chamfer'
            else:
                suffix = f' | {cut.edge_finish}: {sum(edge_counts)} newly cut edges'
        took = time.perf_counter() - t_start           # 0.24.58 a slow cut says how long and which solver
        if took > 1.5:
            suffix += f' | {took:.1f} s ({"/".join(sorted(set(solvers))).title()})'
        return (f'{verb}: {", ".join(t.name for t, _ in results)}{"".join(sorted(set(infos)))}{suffix}' +
                _target_report(skipped, failed) +
                (' | live primitive baked first: ' + ', '.join(baked) if baked else '') +
                (' | Station Primitive frozen (cut kept; its parameters no longer rebuild): ' + ', '.join(frozen)
                 if frozen else ''))
    finally:
        for me in temp:
            if me.users == 0:
                bpy.data.meshes.remove(me)
        cg.remove_object_and_mesh(cutter)
        cg.remove_object_and_mesh(cutter_out)


def _target_report(skipped, failed):
    out = ''
    if skipped:
        out += ' | not touched (no overlap): ' + ', '.join(skipped)
    if failed:
        out += ' | FAILED, left unchanged: ' + '; '.join(failed)
    return out


def _world_box(points):
    xs, ys, zs = zip(*points)
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def _boxes_touch(a, b, pad=1e-6):
    return all(a[0][i] <= b[1][i] + pad and b[0][i] <= a[1][i] + pad for i in range(3))


def mirror_live_cutter(target, cutter):
    """0.24.58 Auto Apply off on a part with a live Mirror: a shape drawn over the mirrored copy is moved (its mesh
    mirrored) onto the real half - the live Boolean only sees the base mesh.  True when it was moved."""
    if not target.data.vertices or not cutter.data.vertices:
        return False
    tw, cw = target.matrix_world, cutter.matrix_world
    base = _world_box([tw @ v.co for v in target.data.vertices])
    pts = [cw @ v.co for v in cutter.data.vertices]
    if _boxes_touch(_world_box(pts), base):
        return False
    for r in cg.mirror_reflections(target):
        if _boxes_touch(_world_box([r @ p for p in pts]), base):
            bm = bmesh.new()
            bm.from_mesh(cutter.data)
            bm.transform(cw.inverted_safe() @ r @ cw)
            bmesh.ops.reverse_faces(bm, faces=bm.faces[:])         # a reflection turns the faces inside out
            bm.to_mesh(cutter.data)
            bm.free()
            cutter.data.update()
            return True
    return False


def _make_live(context, mode, targets, cutter, invert):
    """Auto Apply OFF: keep the cutter object and live Boolean modifiers."""
    cut = context.scene.mch_cut
    mirror_live_cutter(targets[0], cutter)
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


@_with_finish_notes
def perform_line(context, mode, targets, points, projector, side_xy, invert=False):
    """Open line cut / split. ``side_xy`` picks the half removed by Cut."""
    scene = context.scene
    cut = scene.mch_cut
    auto_apply = scene.mch_settings.auto_apply if hasattr(scene, 'mch_settings') else True
    _leave_edit_mode(context, targets)
    _confirm_fuse(context, targets)
    from . import station_primitive
    for t in targets:
        station_primitive.freeze(t)
        cg.ensure_real_mesh(context, t)
        cg.check_target(t)
    # 0.24.36 From Surface: a 2-point line also stops at Cut Depth (the Boolean half-plane below, not the
    # plane bisect that goes all the way through)
    if len(points) == 2 and cut.fast_line and auto_apply and cut.depth_mode != 'SURFACE':
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
        side_counts = {}
        skipped, failed = [], []
        try:
            for t in targets:
                scale = _object_scale(t)
                try:
                    if mode == 'CUT':
                        me = cg.plane_split_mesh(t, a_near, normal, side != invert, cut.line_cap)
                        temp.append(me)
                        if cut.line_cap and _gn_on(cut):
                            line_bevel_counts.append(_gn_finish(cut, me, scale))
                        elif cut.line_cap:
                            line_bevel_counts.append(cg.finish_new_edges(
                                me, cut.edge_finish, cut.finish_width / scale,
                                cut.finish_segments, cut.finish_profile, clamp=cut.finish_clamp,
                        crisp=cut.finish_crisp))
                        results.append((t, me))
                    else:
                        cap = cut.split_cap and cut.line_cap
                        # Gap Split: two planes at +-gap/2 around the drawn line (centre kept).
                        half = 0.5 * cut.gap_width if cut.split_mode == 'GAP' else 0.0
                        keep = cg.plane_split_mesh(t, a_near - normal * half, normal, True, cap)
                        temp.append(keep)
                        other = cg.plane_split_mesh(t, a_near + normal * half, normal, False, cap)
                        temp.append(other)
                        if cap:
                            for me, side in ((keep, 'a'), (other, 'b')):
                                n = _gn_finish(cut, me, scale) if _gn_on(cut, side) else _finish_side(cut, me, side,
                                                                                                    scale)
                                side_counts[side] = side_counts.get(side, 0) + n
                        results.append((t, keep))
                        pieces.append((t, other))
                except (cg.CutError, RuntimeError) as ex:
                    if len(targets) == 1:
                        raise
                    if 'does not cross' in str(ex):
                        skipped.append(t.name)
                    else:
                        failed.append(f'{t.name} ({str(ex).splitlines()[0][:70]})')
            if not results:
                raise cg.CutError('The line does not cross any target; nothing was changed.' +
                                  (' Failed: ' + '; '.join(failed) if failed else ''))
            infos = [cg.commit_mesh(t, me, cut.shared_mesh) for t, me in results]
            for t, me in pieces:
                temp.remove(me)
                _make_piece(t, me).select_set(True)
            suffix = ''
            if mode == 'SPLIT':
                suffix = _side_report(cut, side_counts) + (' | gap' if cut.split_mode == 'GAP' else '')
            elif cut.edge_finish != 'NONE' and cut.finish_width > 0:
                if not line_bevel_counts:
                    suffix = ' | Edge Finish skipped (cap disabled)'
                elif sum(line_bevel_counts) == 0:
                    suffix = ' | WARNING: Edge Finish found 0 cap boundary edges'
                else:
                    suffix = f' | {cut.edge_finish}: {sum(line_bevel_counts)} new boundary edges'
            return ('Plane split: ' if mode == 'SPLIT' else 'Plane cut: ') + \
                ', '.join(t.name for t, _ in results) + ''.join(sorted(set(infos))) + suffix + \
                _target_report(skipped, failed)
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

ALT_RED = (1.0, 0.22, 0.30, 1.0)      # 0.23.27 Alt (inverse) is red in every tool

_COLORS = {
    'CUT': (1.0, 0.62, 0.10, 1.0),
    'SPLIT': (0.45, 1.0, 0.35, 1.0),
    'MASK': (0.85, 0.45, 1.0, 1.0),
    'BASE': (1.0, 0.55, 0.12, 1.0),
    'PLATE': (0.30, 0.78, 1.0, 1.0),
    'CBASE': (1.0, 0.62, 0.45, 1.0),
    'CPLATE': (0.55, 0.9, 0.6, 1.0),
    'BELT': (0.95, 0.75, 0.3, 1.0),
    'SPIKE': (0.6, 0.85, 0.4, 1.0),
    'SCALES': (0.45, 0.8, 0.55, 1.0),
    'SBRUSH': (0.55, 0.8, 0.7, 1.0),
    'BRIDGE': (0.6, 0.7, 1.0, 1.0),
    'FLOWER': (0.95, 0.6, 0.8, 1.0),
    'SCURVE': (0.5, 0.75, 1.0, 1.0),
    'SDRAW': (0.95, 0.6, 0.2, 1.0),
    'CAPE': (0.8, 0.55, 0.35, 1.0),
    'SCAPE': (0.8, 0.55, 0.35, 1.0),
    'HAIR': (0.75, 0.7, 0.45, 1.0),
    'GARMENT': (0.55, 0.7, 0.85, 1.0),
    'HOOD': (0.6, 0.5, 0.85, 1.0),
    'SCARF': (0.85, 0.5, 0.55, 1.0),
    'WRINKLE': (0.95, 0.45, 0.75, 1.0),
    'HIDE': (1.0, 0.62, 0.10, 1.0),               # 0.23.17 Box Hide: orange like Cut (hide and Alt = show)
    'DETAIL': (0.95, 0.85, 0.35, 1.0),            # 0.24 Plate Detail: yellow
    'DETAIL2': (0.95, 0.85, 0.35, 1.0),
    'DETAIL3': (0.95, 0.85, 0.35, 1.0),
}


def stroke_color(mode, inverted):
    """Outline colour while drawing; Alt held (inverted) is red for every tool."""
    if inverted:
        return ALT_RED
    return _COLORS.get(mode, _COLORS['CUT'])


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
        color = stroke_color(op.mode, op.inverted())
        fill = (color[0], color[1], color[2], 0.16)
        if op.stage == 'SIDE' and op.side_preview:
            _draw_fill(sh, [op.side_preview], (1.0, 0.25, 0.1, 0.22))
        loops = op.preview_loops()
        for lp in loops:
            _draw_lines(sh, lp, color, closed=op.preview_closed())
        if loops and op.preview_closed() and op.stage != 'SIDE':
            _draw_fill(sh, loops, fill)
        stab = getattr(op, 'stab', None)
        if stab is not None and stab.active and op.stage == 'DRAG' and stab.pos is not None:
            # live tail to the stabilized point, plus the lazy guide (circle + string)
            if op.pts:
                _draw_lines(sh, [op.pts[-1], stab.pos], color, width=2.0)
            if op.brush.stab_guide and op.mouse is not None:
                r = stab.radius
                if r > 0.5:
                    ring = [(op.mouse[0] + r * math.cos(a), op.mouse[1] + r * math.sin(a))
                            for a in (2 * math.pi * i / 40 for i in range(40))]
                    _draw_lines(sh, ring, (1, 1, 1, 0.35), closed=True, width=1.0)
                _draw_lines(sh, [stab.pos, op.mouse], (1, 1, 1, 0.6), width=1.0)
                _draw_squares(sh, [stab.pos], color, 3.0)
        if op.stage in {'POINTS', 'SIDE'}:
            _draw_squares(sh, op.pts, (1, 1, 1, 0.9), 3.5)
            if op.pts:
                _draw_squares(sh, [op.pts[0]], color, 5.5 if op.near_first else 4.0)
            if op.shape == 'CURVE_LASSO' and len(op.pts) >= 3:
                handle_color = (0.3, 0.8, 1.0, 0.9)
                for i, r in enumerate(op.rounds[:len(op.pts)]):
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


def ui_scale(context):
    try:
        return max(0.5, float(context.preferences.system.ui_scale))
    except AttributeError:
        return 1.0


def exit_tool(context):
    """Back to Blender's Select Box.  Leaving Base Mesh auto-applies only the
    live results it created itself."""
    settings = getattr(context.scene, 'mch_settings', None)
    try:
        current = ts.effective_tool(context)
    except (AttributeError, KeyError, TypeError):
        current = None
    if current in {'BASE', 'CBASE'}:
        try:
            from . import base_mesh
            base_mesh.auto_apply_session(context)
        except (AttributeError, ImportError):
            pass
    try:
        from . import workspace_ui
        workspace_ui.set_native_tool(context, 'builtin.select_box')
    except (RuntimeError, TypeError, ImportError) as ex:
        print('[Mecha Lab] could not leave tool:', ex)


def object_under(context, xy, skip=None):
    """The object under a region pixel (or None)."""
    try:
        from bpy_extras import view3d_utils
        region, rv3d = context.region, context.region_data
        o = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
        d = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy)
        dg = context.evaluated_depsgraph_get()
        for _ in range(8):
            hit, loc, _n, _i, hob, _m = context.scene.ray_cast(dg, o, d)
            if not hit or hob is None:
                return None
            ob = bpy.data.objects.get(hob.name)
            if ob is not None and (skip is None or not skip(ob)):
                return ob
            o = loc + d * 1e-4
    except (AttributeError, RuntimeError, ReferenceError, TypeError):
        pass
    return None


def double_click_leave(context, xy, skip=None):
    """0.24.5 double-click with nothing being drawn: leave the tool (Select).
    On another object it becomes the selected / active one; on empty space the
    selection stays."""
    ob = object_under(context, xy, skip)
    if ob is not None:
        try:
            for o_ in context.selected_objects:
                o_.select_set(False)
            ob.select_set(True)
            context.view_layer.objects.active = ob
        except (RuntimeError, ReferenceError, AttributeError):
            pass
    exit_tool(context)
    try:
        bpy.ops.mch.select_move()
    except (RuntimeError, AttributeError):
        pass
    return ob


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


def triple_reset(context):
    """An edit click (moving / toggling a placed point) is not part of a triple."""
    try:
        _TRIPLE_STATE.pop((context.window.as_pointer(), context.area.as_pointer()), None)
    except (AttributeError, ReferenceError):
        pass


FOLLOWERS = {'PLATE', 'CPLATE', 'SDRAW', 'FLOWER'}       # new parts made on a part: they follow its Mirror


def surface_point(context, projector, xy):
    """The first mesh surface under screen point ``xy`` (world location) or None."""
    try:
        o, d = projector.ray(tuple(xy))
        hit, loc, _n, _i, ob, _m = context.scene.ray_cast(context.evaluated_depsgraph_get(), o, d)
    except (AttributeError, TypeError, RuntimeError):
        return None
    return tuple(loc) if hit and ob is not None and ob.type == 'MESH' else None


class StrokeLogic:
    """State machine of one shape stroke (plain Python so tests can drive it
    with simulated events; the Blender operator below only adds RNA).

    Stages: POINTS (Lasso / Curve Lasso), DRAG (Rect / Circle / Ellipse /
    Free Draw / Custom), SIDE (open line: pick the half to remove).
    Exits:  FINISHED = one applied operation (= one undo step);
            CANCELLED = nothing changed.  Esc and RMB double also leave the
            tool (Blender Select Box); completed cuts are never touched.
    """

    # ---- state helpers ---------------------------------------------------

    def inverted(self):
        return self.alt_latch or self.alt_held

    def _line_mode(self):
        from . import lasso_line
        if self.mode == 'SDRAW' and self._fill_area():
            return False                       # 0.24.33 Fill Area: the drawing is an area
        if self.mode in {'BELT', 'SCURVE', 'SDRAW', 'SCAPE'}:    # 0.24.20 Belt Maker / Surface Curve always draw a line
            return self.shape in {'LASSO', 'CURVE_LASSO', 'STROKE'}
        return lasso_line.enabled(bpy.context, self.mode, self.shape)

    def _fill_area(self):
        scene = bpy.context.scene
        st = getattr(scene, 'mch_sdraw', None)
        return bool(st is not None and st.fill and self.shape in {'LASSO', 'CURVE_LASSO', 'STROKE', 'RECT',
                                                                  'CIRCLE', 'ELLIPSE', 'CUSTOM'})

    def _line_path(self, pts=None):
        """Open path of the current drawing (Line mode)."""
        pts = list(self.pts if pts is None else pts)
        if self.shape == 'CURVE_LASSO' and len(pts) >= 3:
            n = len(pts)
            sharp = list(self.sharp[:n]) + [False] * (n - len(self.sharp))
            over = list(self.overrides[:n]) + [None] * (n - len(self.overrides))
            return curve_lasso_spline(pts, sharp, over, self.brush.curve_resolution, self.brush.curve_smoothness,
                                      closed=False)
        if self.shape == 'STROKE':
            pts = smooth_open(pts, self.brush.stroke_smooth)
            return cg.simplify_open(pts, self.brush.stroke_simplify)
        return pts

    def _line_loops(self, pts=None):
        from . import lasso_line
        prof = None
        if self.shape == 'STROKE' and getattr(self.brush, 'line_pressure', False):
            raw = list(self.pts if pts is None else pts)
            prs = list(getattr(self, 'pressures', []))
            prof = lasso_line.pressure_profile(raw[:len(prs)], prs[:len(raw)])
        loop = lasso_line.line_loop(bpy.context, self.projector, self._line_path(pts), self.brush, prof)
        return [loop] if len(loop) >= 3 else []

    def preview_closed(self):
        if self._line_mode():
            return True
        if self.shape in {'LASSO', 'CURVE_LASSO'}:
            return not self._is_open_line()
        if self.shape == 'STROKE' and self.mode == 'MASK':
            return False      # Mask Brush Stroke is an open brush path
        return True

    def _is_open_line(self):
        return self.shape == 'LASSO' and (self.line_open or len(self.pts) == 2 and self.stage == 'SIDE')

    def _popup_name(self):
        return PROFILE_POPUP if self.mode in {'BASE', 'CBASE'} else SHAPE_POPUP

    def _needs_target(self):
        return self.mode not in {'BASE', 'CBASE', 'PLATE', 'CPLATE', 'WRINKLE', 'DETAIL', 'DETAIL2', 'DETAIL3', 'BELT', 'SPIKE', 'SCALES', 'SBRUSH', 'BRIDGE',
                                 'FLOWER', 'SCURVE', 'CAPE', 'SCAPE', 'HAIR', 'GARMENT', 'HOOD', 'SCARF', 'SDRAW'}

    def _tangents(self, pts=None):
        pts = self.pts if pts is None else pts
        n = len(pts)
        sharp = list(self.sharp) + [False] * (n - len(self.sharp))
        over = list(self.overrides) + [None] * (n - len(self.overrides))
        return curve_tangents(pts, sharp, over, self.brush.curve_smoothness, closed=True)

    def _curve(self, pts=None):
        pts = self.pts if pts is None else pts
        n = len(pts)
        rounds = list(self.rounds[:n]) + [0.0] * (n - len(self.rounds))
        return curve_lasso_loop(pts, rounds, self.brush.curve_resolution)

    def _outline(self, loop):
        b = self.brush
        return round_corners(loop, b.outline_radius, b.outline_corner, b.outline_segments)

    def preview_loops(self):
        m = self.mouse
        if self._line_mode():
            pts = list(self.pts)
            if self.stage == 'POINTS' and m is not None and self.drag_index is None \
                    and self.drag_handle is None and not self.free_drag:
                pts = pts + [self._snapped(m, self.shift_held)]
            return self._line_loops(pts) if len(pts) >= 2 else []
        if self.shape in {'LASSO', 'CURVE_LASSO'}:
            pts = list(self.pts)
            if self.stage == 'POINTS' and m is not None and self.drag_index is None \
                    and self.drag_handle is None and not self.free_drag:
                pts = pts + [self._snapped(m, self.shift_held)]
            if self.shape == 'CURVE_LASSO' and len(pts) >= 3:
                return [self._curve(pts)]
            if self.shape == 'LASSO' and len(pts) >= 3 and not self._is_open_line():
                return [self._outline(pts)]
            return [pts] if len(pts) >= 2 else []
        if self.shape == 'STROKE':
            return [self.pts] if len(self.pts) >= 2 else []
        if m is None or self.anchor is None:
            return []
        return self._drag_loops(m, self.ctrl_held, self.shift_held)

    def _drag_loops(self, m, ctrl, shift):
        b = self.brush
        if self.shape == 'RECT':
            return [self._outline(rect_loop(self.anchor, m, shift, ctrl))]
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

    def _clock(self):
        return _now()

    def invoke(self, context, event):
        # (v0.9.x triple-click-to-select removed: it fought with Curve Lasso
        # point clicks and double-click confirm.)
        # Another Mecha tool was picked but the toolbar kept this drawing tool:
        # do not cut; let the click do normal selection.
        try:
            if ts.effective_tool(context) != self.mode:
                return {'PASS_THROUGH'}
        except (AttributeError, KeyError, TypeError):
            pass
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
        self.shape = self.brush_shape = self.brush.shape
        if self.shape in {'LASSO', 'CURVE_LASSO'} and self._line_mode():
            self.shape = 'STROKE'     # 0.24.20 a line: draw while holding LMB, releasing applies (every tool)
        xy, inside = self._region_xy(event)
        if not inside:
            return {'PASS_THROUGH'}
        if event.type == 'LEFTMOUSE' and event.value == 'DOUBLE_CLICK':
            # 0.24.5 second click of a double-click that nothing is being drawn with (the first click of a
            # rectangle / circle ended without a drag): leave the tool, select the object under the mouse
            double_click_leave(context, xy)
            return {'CANCELLED'}
        from . import surface_lasso
        if surface_lasso.enabled(context, self.mode):
            # 0.22.1 Surface Lasso: points on the mesh, its own modal operator
            try:
                bpy.ops.mch.surface_lasso('INVOKE_DEFAULT', mode=self.mode)
            except RuntimeError as ex:
                self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        if self.mode in {'MASK', 'BASE', 'CBASE', 'PLATE', 'CPLATE', 'WRINKLE', 'HIDE', 'DETAIL', 'DETAIL2', 'DETAIL3', 'FLOWER',
                     'SPIKE', 'SCALES', 'SBRUSH', 'BRIDGE', 'CAPE', 'HAIR', 'GARMENT', 'HOOD', 'SCARF'} and self.shape == 'LASSO' and self.brush.line_open:
            self.brush.line_open = False
        self.ui = ui_scale(context)
        self.target_names = []
        cut_props = getattr(context.scene, 'mch_cut', None)
        # 0.12 Auto Target: the finished shape decides what is cut, so a stroke may
        # start anywhere and the tool stays on for the next part.
        self.auto_target = (self.mode in {'CUT', 'SPLIT', 'HIDE'} and cut_props is not None and
                            getattr(cut_props, 'targets', '') == 'AUTO')
        self._auto_cache = None
        from . import lasso_sketch
        if lasso_sketch.enabled(context, self.mode):
            self.auto_target = True          # sketching needs no target yet (the sketch is applied with Enter)
        if self._needs_target() and not self.auto_target:
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
        self.pts, self.redo = [], []
        self.pressures = []          # 0.24.21 pen pressure per Free Draw sample
        self.sharp, self.overrides = [], []
        self.rounds = []            # Curve Lasso corner rounding per point (0 = straight)
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
        self.free_drag = False
        self.near_first = False
        self.side_preview = None
        self.space_xy = None         # 0.23.13: Space held = move the whole outline with the mouse
        self.rmb_time = None
        self.timer = None
        self.last_press = None       # (time, xy, 'ADD' / 'EDIT') for own double-click detection
        self.stab = None             # Free Draw stabilizer (stabilizer.py)
        self.stab_timer = None
        # v0.9.3 behaviour restored: Alt held at the press latches the inverse
        # (Cut: keep inside, Base Mesh: cut the drawn solid into the mesh).
        self._begin(xy)
        self.handle = add_draw_handler(self)
        context.window_manager.modal_handler_add(self)
        self._wm, self._window = context.window_manager, context.window
        if self.stab is not None and self.stab_timer is None and self.stab.active:
            try:
                self.stab_timer = self._wm.event_timer_add(1.0 / 60.0, window=self._window)
            except (TypeError, ValueError, RuntimeError):
                self.stab_timer = None
        self._hint(context)
        self.region.tag_redraw()
        return {'RUNNING_MODAL'}

    def _begin(self, xy):
        if self.shape in {'LASSO', 'CURVE_LASSO'}:
            self.stage = 'POINTS'
            self._add_point(xy)
            self.last_press = (self._clock(), xy, 'ADD')
            self.free_drag = False    # 0.24.18 Lasso = click points only (Free Draw draws freely)
        else:
            self.stage = 'DRAG'
            self.anchor = xy
            if self.shape == 'STROKE':
                self.pts = [xy]
                self.shift_anchor = None
                self._stroke_start(xy)

    def _stroke_start(self, xy):
        """Free Draw: start the Lazy Mouse stabilizer when it is ON."""
        if self.mode == 'MASK' or not getattr(self.brush, 'stab_enable', False):
            return
        from .stabilizer import LazyStabilizer
        self.stab = LazyStabilizer(self.brush)
        self.stab.reset(xy, self._clock())
        ctx_wm = getattr(self, '_wm', None)
        if ctx_wm is not None and self.stab_timer is None:
            try:
                self.stab_timer = ctx_wm.event_timer_add(1.0 / 60.0, window=getattr(self, '_window', None))
            except (TypeError, ValueError, RuntimeError):
                self.stab_timer = None

    def _stroke_sample(self, xy):
        """Free Draw mouse sample (stabilized when active).  0.24.36 Shift held: a straight piece from where Shift
        went down, at 0 / 45 / 90 degrees (let go of Shift and the line goes on freely from its end)."""
        stab = self.stab
        if getattr(self, 'shift_held', False) and self.pts:
            if getattr(self, 'shift_anchor', None) is None:
                self.shift_anchor = (len(self.pts), self.pts[-1])
            n, a = self.shift_anchor
            end = snap45(a, xy)
            parts = max(1, int(math.dist(a, end) / max(1.0, self.brush.stroke_spacing)))
            self.pts = self.pts[:n] + [(a[0] + (end[0] - a[0]) * k / parts, a[1] + (end[1] - a[1]) * k / parts)
                                       for k in range(1, parts + 1)]
            if hasattr(self, 'pressures'):
                pr = self.pressures[:n] or [getattr(self, 'pressure', 1.0)]
                self.pressures = pr + [pr[-1]] * (len(self.pts) - len(pr))
            if stab is not None and stab.active:
                stab.reset(end, self._clock())          # free drawing goes on from the end of the straight piece
            return
        self.shift_anchor = None
        if stab is not None and stab.active:
            xy = stab.update(xy, self._clock())
        if not self.pts or math.dist(self.pts[-1], xy) >= self.brush.stroke_spacing:
            self.pts.append(xy)
            if not hasattr(self, 'pressures'):
                self.pressures = []
            while len(self.pressures) < len(self.pts) - 1:
                self.pressures.append(1.0)
            self.pressures.append(getattr(self, 'pressure', 1.0))

    def _hint(self, context):
        tail = ' | RMB: ' + ('profiles' if self.mode in {'BASE', 'CBASE'} else 'shapes') + ', RMB×2 / Esc: exit tool'
        if self.stage == 'SIDE':
            text = 'Click the side to REMOVE (Alt+click: keep it)' + tail
        elif self.stage == 'POINTS':
            text = ('LMB point (drag = draw) | double-click anywhere or click start: close & apply | Enter | '
                    'Backspace/Ctrl+Z: undo point | Shift 45° | Alt invert | F open line')
            if self.shape == 'CURVE_LASSO':
                text = ('LMB control point (straight) | click a point: round soft / medium / strong / straight | drag point or handle | '
                        'double-click anywhere: close & apply | Backspace/Ctrl+Z: undo point')
            text += tail
        elif self.shape == 'STROKE':
            text = 'Hold LMB and draw, release to apply | Shift: straight 0 / 45 / 90°' + tail
        else:
            text = 'Drag, release to apply | Shift: square/circle | Ctrl: from center | Alt: invert' + tail
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
        if getattr(self, 'stab_timer', None) is not None:
            try:
                context.window_manager.event_timer_remove(self.stab_timer)
            except (ReferenceError, ValueError):
                pass
            self.stab_timer = None
        _status(context, None)
        try:
            self.region.tag_redraw()
        except ReferenceError:
            pass

    def _cancel(self, context):
        self._cleanup(context)
        return {'CANCELLED'}

    def _leave_tool(self, context):
        """Esc / RMB double / triple click: drop the unfinished stroke, back to Select."""
        self._cleanup(context)
        exit_tool(context)
        return {'CANCELLED'}

    def cancel(self, context):
        self._cleanup(context)

    # ---- editing -----------------------------------------------------------

    def _add_point(self, xy):
        p = self._snapped(xy, self.shift_held)
        if self.pts and math.dist(p, self.pts[-1]) <= DUP_PX:
            return False
        self.pts.append(p)
        self.sharp.append(False)
        self.overrides.append(None)
        self.rounds.append(0.0)
        self.redo.clear()
        return True

    def _pop_point(self):
        if not self.pts:
            return False
        self.redo.append((self.pts.pop(), self.sharp.pop(), self.overrides.pop(),
                          self.rounds.pop() if self.rounds else 0.0))
        return True

    def _redo_point(self):
        if self.redo and self.stage == 'POINTS':
            p, sh, ov, rd = self.redo.pop()
            self.pts.append(p)
            self.sharp.append(sh)
            self.overrides.append(ov)
            self.rounds.append(rd)

    def _hit_point(self, xy):
        for i, p in enumerate(self.pts):
            if math.dist(p, xy) <= HIT_PX:
                return i
        return None

    def _hit_handle(self, xy):
        """(point index, side) of a rounded Curve Lasso corner handle under the cursor."""
        if self.shape != 'CURVE_LASSO' or len(self.pts) < 3:
            return None
        for i, r in enumerate(self.rounds[:len(self.pts)]):
            if r > 0:
                h0, h1 = corner_handles(self.pts, i, r)
                if math.dist(h1, xy) <= HIT_PX:
                    return (i, 1)
                if math.dist(h0, xy) <= HIT_PX:
                    return (i, -1)
        return None

    def _clean_points(self):
        keep = clean_clicks(self.pts, DUP_PX, closed=not (self._is_open_line() or self._line_mode()))
        if len(keep) != len(self.pts):
            idx, j = [], 0
            for i, p in enumerate(self.pts):
                if j < len(keep) and p == keep[j]:
                    idx.append(i)
                    j += 1
            self.sharp = [self.sharp[i] for i in idx]
            self.overrides = [self.overrides[i] for i in idx]
            self.rounds = [self.rounds[i] for i in idx if i < len(self.rounds)]
            self.pts = keep

    def _current_loops(self, event_ctrl=False, event_shift=False):
        if self._line_mode():
            return self._line_loops()
        if self.shape in {'LASSO', 'CURVE_LASSO'}:
            if self.shape == 'CURVE_LASSO':
                return [self._curve()]
            return [self._outline(list(self.pts))]
        if self.shape == 'STROKE':
            pts = smooth_open(self.pts, self.brush.stroke_smooth)
            pts = cg.simplify_open(pts, self.brush.stroke_simplify)
            return [cg.trim_closing_overlap(pts)]
        return self._drag_loops(self.mouse, event_ctrl, event_shift)

    # ---- execution ---------------------------------------------------------

    def _targets(self):
        if getattr(self, 'auto_target', False):
            return self._auto_targets()
        return [bpy.data.objects[n] for n in self.target_names if n in bpy.data.objects]

    def _auto_targets(self):
        pts = list(self.pts)
        if self._line_mode():
            loops = self._line_loops() or [pts]
        elif self.shape in {'LASSO', 'CURVE_LASSO', 'STROKE'}:
            loops = [self._curve()] if self.shape == 'CURVE_LASSO' and len(pts) >= 3 else [pts]
            if self.stage == 'SIDE' and len(pts) == 2:          # 2-point line: thin band along the line
                loops = [[pts[0], pts[1], (pts[1][0] + 1, pts[1][1] + 1), (pts[0][0] + 1, pts[0][1] + 1)]]
        else:
            loops = self._current_loops(self.ctrl_held, self.shift_held)
        key = (self.shape, tuple(map(tuple, (p for lp in loops for p in lp))))
        if self._auto_cache is None or self._auto_cache[0] != key:
            found = auto_targets(bpy.context.view_layer, self.projector, loops)
            self._auto_cache = (key, [o.name for o in found])
        return [bpy.data.objects[n] for n in self._auto_cache[1] if n in bpy.data.objects]

    def _execute_closed(self, context):
        from . import lasso_sketch
        sketching = lasso_sketch.enabled(context, self.mode)
        targets = [] if sketching else self._targets()
        if getattr(self, 'auto_target', False) and not sketching:
            if not targets:
                raise cg.CutError('Auto Target: the shape does not cover any mesh; nothing was changed.')
            # what gets cut becomes the selection (visible feedback, and ready for Selected Only)
            try:
                for o in context.selected_objects:
                    o.select_set(False)
                for o in targets:
                    o.select_set(True)
                context.view_layer.objects.active = targets[-1]
            except (AttributeError, RuntimeError, ReferenceError):
                pass
        if self.mode == 'BELT':
            from . import belt_maker
            return belt_maker.perform(context, self._line_path(), self.projector)
        if self.mode == 'SDRAW':                 # 0.24.33 Surface Draw
            from . import surface_draw
            if self.inverted():
                # Alt + draw over a live drawing: that line / area is cut out of it (it stays live); over a plain
                # mesh (0.24.37): the band / area is carved into the mesh, as deep as its Height
                from . import live_subtract
                loops = self._current_loops(self.ctrl_held, self.shift_held)
                if live_subtract.pick(context, 'SDRAW', loops, self.projector) is not None:
                    return live_subtract.perform(context, 'SDRAW', loops, self.projector)
                if self._fill_area():
                    return surface_draw.engrave(context, None, self.projector, loops=loops)
                return surface_draw.engrave(context, self._line_path(), self.projector)
            if self._fill_area():
                return surface_draw.perform_fill(context, self._current_loops(self.ctrl_held, self.shift_held),
                                                 self.projector)
            return surface_draw.perform(context, self._line_path(), self.projector)
        if self.mode == 'SCAPE':                 # 0.24.34 Scarf Cape: the drawn line is the collar, folds across
            from . import cape_gen
            return cape_gen.perform_line(context, self._line_path(), self.projector)
        if self.mode == 'SCURVE':
            from . import surface_curve
            return surface_curve.perform(context, self._line_path(), self.projector)
        if self.mode == 'BRIDGE':
            from . import bridge_patch
            return bridge_patch.perform(context, self._current_loops(self.ctrl_held, self.shift_held), self.projector)
        if self.mode == 'SBRUSH':
            from . import scale_brush
            return scale_brush.perform(context, self._current_loops(self.ctrl_held, self.shift_held), self.projector)
        if self.mode in {'SPIKE', 'SCALES'}:   # 0.24.20 a lasso fills the area, the Line button = along a line
            from . import creature_scales, creature_spike
            mod = creature_spike if self.mode == 'SPIKE' else creature_scales
            if self._line_mode():
                return mod.perform(context, self._line_path(), self.projector)
            return mod.perform_area(context, self._current_loops(self.ctrl_held, self.shift_held), self.projector)
        if self.mode == 'MASK' and self.shape == 'STROKE':
            from . import mask_tools
            points = smooth_open(self.pts, self.brush.stroke_smooth)
            points = cg.simplify_open(points, self.brush.stroke_simplify)
            changed, total = mask_tools.apply_mask_stroke(
                context, targets[0], points, self.projector,
                self.brush.mask_brush_radius, self.inverted())
            msg = f'Mask stroke: {changed} faces changed ({total} masked total; entire faces, not exact outline)'
        else:
            loops = self._current_loops(self.ctrl_held, self.shift_held)
            from . import lasso_sketch
            if sketching:
                # 0.19.3 Sketch First (all lasso tools): add / (Alt) subtract, Enter applies
                # (0.24.3 Box Hide: Alt + draw with no Box Hide sketch = show again right away)
                sub = self.inverted()
                if self.mode == 'HIDE':      # 0.24.3 Box Hide: Alt + draw with nothing sketched yet just starts it
                    sk = lasso_sketch.data(context.scene)
                    sub = sub and sk is not None and sk.get('mode') == 'HIDE'
                return lasso_sketch.add(context, self.mode, loops, self.projector, subtract=sub)
            if self.mode == 'MASK':
                msg = perform_mask(context, targets[0], loops, self.projector, self.inverted())
            elif self.mode == 'PLATE' and self.inverted():
                from . import armor_plate          # 0.24.42 Alt + draw: the plate the other way, carved in
                msg = armor_plate.perform_plate_carve(context, loops, self.projector)
            elif self.mode == 'PLATE':
                from . import armor_plate
                msg = armor_plate.perform_plate(context, loops, self.projector)
            elif self.mode in {'CPLATE', 'DETAIL', 'DETAIL2', 'DETAIL3'} and self.inverted():
                from . import live_subtract        # 0.24.21 Alt + draw: cut that area out of the live plate
                msg = live_subtract.perform(context, 'CPLATE' if self.mode == 'CPLATE' else 'DETAIL', loops,
                                            self.projector, tool=self.mode)
            elif self.mode == 'CPLATE':
                from . import creature_plate
                msg = creature_plate.perform(context, loops, self.projector)
            elif self.mode == 'FLOWER':
                from . import flower_plate
                msg = flower_plate.perform(context, loops, self.projector)
            elif self.mode == 'CAPE':
                from . import cape_gen
                msg = cape_gen.perform(context, loops, self.projector)
            elif self.mode == 'HAIR':
                from . import creature_hair
                msg = creature_hair.perform(context, loops, self.projector)
            elif self.mode == 'GARMENT':
                from . import clothing_gen
                msg = clothing_gen.perform(context, loops, self.projector)
            elif self.mode == 'HOOD':
                from . import hood_gen
                msg = hood_gen.perform(context, loops, self.projector)
            elif self.mode == 'SCARF':
                from . import scarf_gen
                msg = scarf_gen.perform(context, loops, self.projector)
            elif self.mode == 'WRINKLE':
                from . import cloth_wrinkle
                msg = cloth_wrinkle.perform_wrinkle(context, loops, self.projector)
            elif self.mode in {'DETAIL', 'DETAIL2', 'DETAIL3'}:
                from . import plate_detail
                msg = plate_detail.perform(context, loops, self.projector, self.mode)
            elif self.mode == 'HIDE':
                from . import box_hide
                msg = box_hide.perform(context, targets, loops, self.projector, restore=self.inverted())
            elif self.mode in {'BASE', 'CBASE'}:
                from . import base_mesh
                if getattr(base_mesh.scene_defaults(context), 'sketch', False):
                    # 0.14.1 Sketch First: add to / (Alt) subtract from the orange sketch
                    msg = base_mesh.sketch_add(context, loops, self.projector, subtract=self.inverted())
                else:
                    # Alt: the drawn solid cuts into the mesh (flipped bevel sides)
                    attach, alt_loops = (None, None) if self.inverted() else self._line_attach(context, base_mesh)
                    msg = base_mesh.perform_base(context, alt_loops or loops, self.projector, cutter=self.inverted(),
                                                 attach=attach)
            else:
                live = self._live_cut(context, targets)
                from . import ramp_edit
                if live:                     # 0.24.56 the cut stays live: its sliders cut it again
                    ramp_edit.begin(context, targets[0], loops, self.projector, kind='cutlive',
                                    extra={'inverted': bool(self.inverted())})
                try:
                    msg = perform_closed(context, self.mode, targets, loops, self.projector, self.inverted())
                except Exception:
                    if live:
                        ramp_edit.finish(targets[0])
                    raise
                if live:
                    ramp_edit.stamp(targets[0])
        if self.shape == 'CUSTOM' and self.anchor is not None and self.mouse is not None:
            r = math.dist(self.anchor, self.mouse)
            if r >= 4.0:
                self.brush.custom_size = r
        return msg

    def _line_attach(self, context, base_mesh):
        """0.24.57 Base Mesh Line + Attach Ends: ((path, start hit, end hit), loops) - the ends on the meshes under
        the first / last point of the line; Smooth also smooths the line in between (its ends stay)."""
        p = base_mesh.scene_defaults(context)
        if not (self._line_mode() and getattr(p, 'line_attach', False)):
            return None, None
        path = [tuple(q) for q in self._line_path()]
        if len(path) < 2:
            return None, None
        loops = None
        if p.attach_curve == 'SMOOTH' and len(path) > 2:
            path = smooth_open(path, 6)
            loops = self._line_loops(path) or None
        return (path, surface_point(context, self.projector, path[0]),
                surface_point(context, self.projector, path[-1])), loops

    def _live_cut(self, context, targets):
        """0.24.56 keep this cut live (one plain Cut on one part, not a ramp; Preferences: Live Last Cut)."""
        from .workspace_ui import pref
        cut = context.scene.mch_cut
        return (self.mode == 'CUT' and targets is not None and len(targets) == 1 and not getattr(cut, 'gn_ramp', False)
                and pref('live_last_cut', True))

    def _run(self, context, fn, keep_on_shape_error=False):
        from . import safety_save              # 0.24.58 a recovery copy before the heavy step (when one is due)
        safety_save.checkpoint(f'Mecha {self.mode}')
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
        try:                                 # 0.24.33 Point Radial Symmetry: a new part repeats too
            from . import radial_sym
            msg = (msg or '') + radial_sym.after_create(context, self.mode)
        except (ImportError, AttributeError, RuntimeError, ReferenceError):
            pass
        if self.mode in FOLLOWERS:           # 0.24.55 ... and follows the Mirror of the part it was made on
            try:
                from . import symmetry
                msg = (msg or '') + symmetry.follow(context, context.active_object)
            except (ImportError, AttributeError, RuntimeError, ReferenceError):
                pass
        self.report({'INFO'}, msg)
        self._cleanup(context)
        return {'FINISHED'}

    def _confirm(self, context):
        if self._line_mode() and self.shape in {'LASSO', 'CURVE_LASSO'}:
            self._clean_points()
            if len(self.pts) < 2:
                self.report({'WARNING'}, 'Line: place at least 2 points')
                return {'RUNNING_MODAL'}
            return self._run(context, self._execute_closed, keep_on_shape_error=True)
        if self.shape in {'LASSO', 'CURVE_LASSO'}:
            self._clean_points()
            if self.shape == 'LASSO' and len(self.pts) >= 2 and (self.line_open or len(self.pts) == 2):
                if self.mode in {'MASK', 'BASE', 'CBASE', 'PLATE', 'CPLATE', 'WRINKLE', 'HIDE', 'DETAIL', 'DETAIL2', 'DETAIL3', 'FLOWER',
                     'SPIKE', 'SCALES', 'SBRUSH', 'BRIDGE', 'CAPE', 'HAIR', 'GARMENT', 'HOOD', 'SCARF'}:
                    self.report({'WARNING'}, 'This tool needs a closed outline (3+ points)')
                    return {'RUNNING_MODAL'}
                if self.mode == 'SPLIT':
                    return self._run(context, lambda c: perform_line(
                        c, 'SPLIT', self._targets(), self.pts, self.projector, self.pts[0]))
                self.stage = 'SIDE'
                self._update_side_preview()
                self._hint(context)
                return {'RUNNING_MODAL'}
            if len(self.pts) < 3:
                self.report({'WARNING'}, 'Place at least 3 points (Lasso: 2 points = line cut)')
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
        if self._needs_target() and not getattr(self, 'auto_target', False) and not self._targets():
            return self._cancel(context)
        if self.native_tool and ts.native_tool_id(context) != self.native_tool:
            return self._cancel(context)          # tool switched from toolbar/list
        if context.scene.mch_brush.shape != getattr(self, 'brush_shape', self.shape):
            self.report({'INFO'}, 'Shape changed: unfinished stroke discarded')
            return self._cancel(context)

        et, ev = event.type, event.value
        pr = getattr(event, 'pressure', 0.0)
        self.pressure = pr if isinstance(pr, float) and pr > 0.0 else 1.0     # 0.24.21 pen pressure (mouse = 1)
        if et in {'LEFT_BRACKET', 'RIGHT_BRACKET'} and ev == 'PRESS':
            step_line_width(context, 1.0 / 1.15 if et == 'LEFT_BRACKET' else 1.15, self.report)
            self.region.tag_redraw()
            return {'RUNNING_MODAL'}
        if et in {'LEFT_ALT', 'RIGHT_ALT'}:
            self.alt_held = ev == 'PRESS'
        if et in {'LEFT_SHIFT', 'RIGHT_SHIFT'}:
            self.shift_held = ev == 'PRESS'
        if et in {'LEFT_CTRL', 'RIGHT_CTRL', 'OSKEY'}:
            self.ctrl_held = ev == 'PRESS'

        if et == 'TIMER' and self.stab is not None and self.stab.active and self.stage == 'DRAG' \
                and self.rmb_time is None:
            p = None if self.shift_held else self.stab.tick(self._clock())   # glide on (not on a Shift line)
            if p is not None and math.dist(self.pts[-1], p) >= self.brush.stroke_spacing:
                self.pts.append(p)
            self.region.tag_redraw()
            return {'RUNNING_MODAL'}
        if et == 'TIMER':
            if self.rmb_time is not None and event_timer_matches(self, event):
                if _now() - self.rmb_time >= _double_click_seconds(context):
                    self.rmb_time = None
                    self._remove_timer(context)
                    open_popup(self._popup_name())
                return {'RUNNING_MODAL'}
            return {'PASS_THROUGH'}

        xy, inside = self._region_xy(event)
        if et == 'LEFTMOUSE' and ev in {'PRESS', 'DOUBLE_CLICK'} and inside and getattr(self, 'stage', '') != 'DRAG':
            from . import quick_hud                # 0.24.58 a click on the HUD / card / toolbar while a shape is
            if quick_hud.over_ui(context, xy[0], xy[1]):     # being drawn point by point: the panel, not a point
                try:
                    bpy.ops.mch.quick_hud_press('INVOKE_DEFAULT')
                except RuntimeError:
                    pass
                self.region.tag_redraw()
                return {'RUNNING_MODAL'}
        if self.mode == 'PLATE' and et in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'} and not (event.ctrl or event.shift):
            # 0.16 Armor Plate: the wheel steps through the plate profiles while drawing
            from . import armor_plate
            name = armor_plate.cycle_preset(context.scene, 1 if et == 'WHEELDOWNMOUSE' else -1)
            _status(context, f'Armor Plate profile: {name}   (wheel: next / previous)')
            self.region.tag_redraw()
            return {'RUNNING_MODAL'}
        if et in NAV_EVENTS or et.startswith('NDOF') or (et.startswith('NUMPAD_') and et != 'NUMPAD_ENTER'):
            return {'PASS_THROUGH'}

        if et == 'SPACE':
            # 0.23.13: hold Space and move the mouse = move the outline drawn so far (like a marquee)
            if ev == 'PRESS' and getattr(self, 'space_xy', None) is None:
                self.space_xy = self.mouse or xy
            elif ev == 'RELEASE':
                self.space_xy = None
            return {'RUNNING_MODAL'}
        if (et == 'MOUSEMOVE' or et == 'INBETWEEN_MOUSEMOVE') and getattr(self, 'space_xy', None) is not None:
            self._space_move(xy)
            self.region.tag_redraw()
            return {'RUNNING_MODAL'}
        if et == 'MOUSEMOVE' or et == 'INBETWEEN_MOUSEMOVE':
            if inside or self.stage == 'DRAG' or self.drag_index is not None or self.free_drag:
                self.mouse = xy
                self._on_move(xy)
                self.region.tag_redraw()
            return {'RUNNING_MODAL'} if inside else {'PASS_THROUGH'}

        if not inside:
            if et == 'LEFTMOUSE' and ev == 'RELEASE' and (self.stage == 'DRAG' or self.drag_index is not None
                                                           or self.free_drag):
                pass   # finish a drag that ended over another region
            else:
                return {'PASS_THROUGH'}   # palette, sidebar, menus keep working

        if et == 'ESC' and ev == 'PRESS':
            return self._leave_tool(context)
        if et == 'RIGHTMOUSE' and ev in {'PRESS', 'DOUBLE_CLICK'}:
            now = _now()
            if ev == 'DOUBLE_CLICK' or (self.rmb_time is not None and
                                         now - self.rmb_time < _double_click_seconds(context)):
                return self._leave_tool(context)
            self.rmb_time = now
            if self.timer is None:
                self.timer = context.window_manager.event_timer_add(0.04, window=context.window)
            return {'RUNNING_MODAL'}
        if et == 'RIGHTMOUSE':
            return {'RUNNING_MODAL'}

        if et == 'Z' and ev == 'PRESS' and (event.ctrl or event.oskey):
            if event.shift:
                self._redo_point()
            elif self.stage == 'SIDE':
                self.stage = 'POINTS'
                self.side_preview = None
            elif not self._pop_point() or not self.pts:
                return self._cancel(context)
            self._hint(context)
            self.region.tag_redraw()
            return {'RUNNING_MODAL'}
        if et == 'Y' and ev == 'PRESS' and event.ctrl:
            self._redo_point()
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
        if et == 'F' and ev == 'PRESS' and self.shape == 'LASSO' and self.mode not in {'MASK', 'BASE', 'CBASE', 'PLATE', 'CPLATE', 'WRINKLE', 'HIDE', 'DETAIL', 'DETAIL2', 'DETAIL3', 'FLOWER',
                     'SPIKE', 'SCALES', 'SBRUSH', 'BRIDGE', 'CAPE', 'HAIR', 'GARMENT', 'HOOD', 'SCARF'}:
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
        if et == 'TAB' and ev == 'PRESS':
            # Tab = Edit Mode: drop the unfinished stroke and let Blender switch mode
            self._cleanup(context)
            return {'CANCELLED', 'PASS_THROUGH'}
        if et == 'R' and ev == 'PRESS' and self.shape == 'CUSTOM':
            # B06: rotate the PNG stamp while drawing (Shift+R = back), 15° steps.
            rotate_stamp(context, -1 if event.shift else 1)
            self.region.tag_redraw()
            return {'RUNNING_MODAL'}
        # Swallow other keys while a stroke is pending so a stray hotkey cannot
        # delete or transform the target halfway through.
        return {'RUNNING_MODAL'}

    def _space_move(self, xy):
        dx, dy = xy[0] - self.space_xy[0], xy[1] - self.space_xy[1]
        self.space_xy = xy
        self.mouse = xy
        if dx == 0 and dy == 0:
            return
        self.pts = [(p[0] + dx, p[1] + dy) for p in self.pts]
        self.redo = [((r[0][0] + dx, r[0][1] + dy),) + tuple(r[1:]) for r in self.redo]
        if self.anchor is not None:
            self.anchor = (self.anchor[0] + dx, self.anchor[1] + dy)
        if self.press_xy is not None:
            self.press_xy = (self.press_xy[0] + dx, self.press_xy[1] + dy)
        stab = getattr(self, 'stab', None)
        if stab is not None and getattr(stab, 'active', False):
            stab.reset(xy, self._clock())
        if self.stage == 'SIDE':
            self._update_side_preview()

    def _on_move(self, xy):
        if self.stage == 'DRAG' and self.shape == 'STROKE':
            self._stroke_sample(xy)
        elif self.stage == 'POINTS':
            if self.drag_index is not None:
                if math.dist(xy, self.press_xy) > 3.0:
                    self.pts[self.drag_index] = xy
            elif self.drag_handle is not None:
                i, side = self.drag_handle
                p = self.pts[i]
                nb = self.pts[i - 1] if side < 0 else self.pts[(i + 1) % len(self.pts)]
                ref = max(math.dist(p, nb), 1e-6)
                self.rounds[i] = max(0.0, min(0.5, math.dist(p, xy) / ref))
            elif self.free_drag and self.shape == 'LASSO':
                # Holding LMB in Lasso draws continuously (freehand segment).
                if math.dist(self.pts[-1], xy) >= max(self.brush.stroke_spacing * 2.0, DUP_PX + 1):
                    self.pts.append(xy)
                    self.sharp.append(False)
                    self.overrides.append(None)
                    self.rounds.append(0.0)
                    self.redo.clear()
            self.near_first = (len(self.pts) >= 3 or (self.line_open and len(self.pts) >= 2)) and self._hit_start(xy)
        elif self.stage == 'SIDE':
            self._update_side_preview()

    def _apply_side(self, context, xy, alt):
        invert = alt or self.inverted()
        return self._run(context, lambda c: perform_line(
            c, 'CUT', self._targets(), self.pts, self.projector, xy, invert))

    def _close_px(self):
        return max(HIT_PX, CLOSE_PX) * getattr(self, 'ui', 1.0)

    def _hit_start(self, xy):
        return bool(self.pts) and math.dist(self.pts[0], xy) <= self._close_px()

    def _on_lmb(self, context, ev, xy, event):
        is_down = ev in {'PRESS', 'DOUBLE_CLICK'}
        if self.stage == 'SIDE':
            if is_down:
                return self._apply_side(context, xy, bool(getattr(event, 'alt', False)))
            return {'RUNNING_MODAL'}
        if self.stage == 'DRAG':
            if ev == 'RELEASE':
                if self.shape in {'RECT', 'CIRCLE', 'ELLIPSE'} and \
                        math.dist(self.anchor, xy) < 4.0:
                    return self._cancel(context)    # a click, not a drag
                self.mouse = xy
                if self.shape == 'STROKE':
                    self._stroke_finish(xy)
                    if len(self.pts) < (1 if self.mode == 'MASK' else 2 if self._line_mode() else 3):
                        return self._cancel(context)
                return self._run(context, self._execute_closed)
            return {'RUNNING_MODAL'}
        # POINTS
        now = self._clock()
        last = self.last_press
        quick_again = (last is not None and last[2] == 'ADD' and
                       now - last[0] <= _double_click_seconds(context) and
                       math.dist(xy, last[1]) <= DBL_PX * getattr(self, 'ui', 1.0))
        if (ev == 'DOUBLE_CLICK' or (ev == 'PRESS' and quick_again)) and len(self.pts) <= 1 \
                and (last is None or last[2] == 'ADD'):
            # 0.24.5 nothing drawn yet (only the first click of the double-click): leave the tool,
            # selecting the object under the mouse (double-click closes a lasso only while drawing one)
            res = self._cancel(context)
            double_click_leave(context, xy)
            return res
        if ev == 'DOUBLE_CLICK':
            if last is None or last[2] == 'ADD':
                # Double-click anywhere: close from the last point to the first
                # and apply. Never adds a point (no duplicate / zero-length edge).
                self.free_drag = False
                self.last_press = None
                return self._confirm(context)
            ev = 'PRESS'           # double click on a point being edited = two edit clicks
        if ev == 'PRESS':
            if quick_again:
                # Own double-click detection: some systems deliver the second
                # click as a plain PRESS instead of DOUBLE_CLICK.
                self.free_drag = False
                self.last_press = None
                return self._confirm(context)
            open_line = self._is_open_line() or self.line_open
            if self._hit_start(xy) and (len(self.pts) >= 3 or ((open_line or self._line_mode())
                                                               and len(self.pts) >= 2)):
                self.last_press = None
                return self._confirm(context)          # click the start point = close / finish
            handle = self._hit_handle(xy)
            if handle is not None:
                self.drag_handle = handle
                self.last_press = (now, xy, 'EDIT')
                return {'RUNNING_MODAL'}
            hit = self._hit_point(xy)
            if hit is not None and (hit != len(self.pts) - 1 or self.shape == 'CURVE_LASSO'):
                self.drag_index = hit
                self.press_xy = xy
                self.last_press = (now, xy, 'EDIT')
                return {'RUNNING_MODAL'}
            self.shift_held = bool(getattr(event, 'shift', False))
            self._add_point(xy)
            self.last_press = (now, xy, 'ADD')
            self.free_drag = False    # 0.24.18 holding LMB no longer draws: click point by point
            self.region.tag_redraw()
            return {'RUNNING_MODAL'}
        if ev == 'RELEASE':
            if self.drag_index is not None:
                moved = math.dist(xy, self.press_xy) > 3.0
                if not moved and self.shape == 'CURVE_LASSO':
                    i = self.drag_index
                    # click on a control point: straight -> soft -> medium -> strong -> straight (v0.7.2)
                    self.rounds[i] = next_round_level(self.rounds[i])
                self.drag_index = None
            self.drag_handle = None
            self.free_drag = False
            self.region.tag_redraw()
        return {'RUNNING_MODAL'}

    def _stroke_finish(self, xy):
        """Free Draw release: add the final mouse position once (no double point)."""
        if getattr(self, 'shift_held', False) and getattr(self, 'shift_anchor', None) is not None:
            self._stroke_sample(xy)                     # a Shift line ends exactly on its snapped end
            return
        stab = getattr(self, 'stab', None)
        if stab is not None and stab.active:
            for p in stab.finish(xy, self.brush.stroke_spacing):
                self._stroke_append(p)
            return
        if xy != self.pts[-1] and math.dist(self.pts[-1], xy) > 0.5:
            self.pts.append(xy)

    def _stroke_append(self, p):
        if not self.pts or math.dist(self.pts[-1], p) > 0.5:
            self.pts.append(p)

    def _remove_timer(self, context):
        if self.timer is not None:
            context.window_manager.event_timer_remove(self.timer)
            self.timer = None


class MCH_OT_cut_stroke(StrokeLogic, bpy.types.Operator):
    bl_idname = 'mch.cut_stroke'
    bl_label = 'Mecha Shape Stroke'
    bl_description = 'Draw one shape with the shared shape palette and Cut / Split / Mask / Base Mesh with it'
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(name='Mode', items=[
        ('CUT', 'Cut', 'Remove the inside (Alt: keep inside)'),
        ('SPLIT', 'Split', 'Split into two parts'),
        ('MASK', 'Mask', 'Add face mask (Alt: erase)'),
        ('BASE', 'Base Mesh', 'Create a new solid from the drawn outline'),
        ('PLATE', 'Armor Plate', 'New armour plate on the mesh under the outline'),
        ('CBASE', 'Creature Base Mesh', 'New rounded solid (Puff / Ridge / Pillow) from the drawn outline'),
        ('CPLATE', 'Creature Plate', 'New rounded plate (Puff / Ridge / Pillow) on the mesh under the outline'),
        ('BELT', 'Belt Maker', 'A strap around the mesh where the line crosses it, or along the line'),
        ('SPIKE', 'Creature Spike', 'Spikes standing along the drawn line'),
        ('SCALES', 'Creature Scales', 'Overlapping scales along the drawn line'),
        ('SBRUSH', 'Scale Brush', 'Flat-bottomed scales packed close in the drawn area'),
        ('BRIDGE', 'Bridge Patch', 'A smooth patch joining two meshes across the drawn area'),
        ('FLOWER', 'Flower Plate', 'The outline grows from the surface: attached at the start, bending away'),
        ('SCURVE', 'Surface Curve', 'A Mesh Curve lying on the surface along the drawn line'),
        ('SDRAW', 'Surface Draw', 'A raised band on the surface along the drawn line'),
        ('CAPE', 'Cape', 'A live cape hanging from the top edge of the drawing'),
        ('SCAPE', 'Scarf Cape', 'A live cape with folds across (like a draped scarf)'),
        ('HAIR', 'Creature Hair', 'Live dreadlocks / tentacles / quills growing from the drawn area'),
        ('GARMENT', 'Clothing', 'A live top / pants made from the body inside the drawn outline'),
        ('HOOD', 'Hood', 'A live hood over the head drawn round'),
        ('SCARF', 'Scarf', 'A live scarf round the neck drawn round'),
        ('WRINKLE', 'Cloth Wrinkle', 'New cloth layer with wrinkles on the mesh under the outline'),
        ('HIDE', 'Box Hide', 'Hide the meshes inside the shape (Alt: show again)'),
        ('DETAIL', 'Plate Detail', 'Low trim detail on the plate under the outline'),
        ('DETAIL2', 'Plate Detail 2', 'Smooth rise on the surface under the outline'),
        ('DETAIL3', 'Plate Detail 3', 'Flat raised panel (no trim layers) on the surface under the outline')],
        default='CUT')

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
    """RMB in an idle Mecha tool: single = popup (shapes or Base Mesh profiles),
    double = leave the tool."""

    def invoke(self, context, event):
        self.t0 = _now()
        self.timer = context.window_manager.event_timer_add(0.04, window=context.window)
        from . import zb_sculpt                       # 0.24.60 ZBrush style: right-drag turns the view
        self.rmb = zb_sculpt.RMBDrag()
        self.rmb.rmb_drag_start(context, event)
        self.rmb_up = False                         # 0.24.65 (pen: the press can come twice before a release)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _stop(self, context):
        if self.timer is not None:
            context.window_manager.event_timer_remove(self.timer)
            self.timer = None

    def modal(self, context, event):
        if getattr(self, 'rmb', None) is not None and self.rmb.rmb_drag_check(context, event):
            self._stop(context)
            return {'FINISHED'}
        if event.type == 'RIGHTMOUSE' and event.value == 'RELEASE':
            self.rmb_up = True
        if event.type == 'RIGHTMOUSE' and event.value in {'PRESS', 'DOUBLE_CLICK'} and getattr(self, 'rmb_up', True):
            self._stop(context)
            exit_tool(context)
            return {'FINISHED'}
        if event.type == 'TIMER' and _now() - self.t0 >= _double_click_seconds(context):
            self._stop(context)
            from . import mecha_menu
            if not (mecha_menu.use_menu() and mecha_menu.open_menu(context)):     # 0.24.50 Mecha Menu
                open_popup(PROFILE_POPUP if getattr(self, 'popup', 'SHAPE') == 'PROFILE' else SHAPE_POPUP)
            return {'FINISHED'}
        if event.type == 'ESC':
            self._stop(context)
            exit_tool(context)
            return {'CANCELLED'}
        return {'PASS_THROUGH'}

    def cancel(self, context):
        self._stop(context)


class MCH_OT_rmb_gate(GateLogic, bpy.types.Operator):
    """RMB in an idle Mecha tool: single = popup, double = leave the tool."""
    bl_idname = 'mch.rmb_gate'
    bl_label = 'Mecha RMB (Popup / Exit)'
    bl_options = {'INTERNAL'}
    popup: EnumProperty(items=[('SHAPE', 'Shapes', ''), ('PROFILE', 'Base Mesh Profiles', '')],
                        default='SHAPE')

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D'


STAMP_STEP = math.radians(15.0)
_STAMP_CACHE = {}


def rotate_stamp(context, sign=1):
    b = context.scene.mch_brush
    a = b.custom_rotation + STAMP_STEP * sign
    b.custom_rotation = math.atan2(math.sin(a), math.cos(a))     # keep in (-180°, 180°]
    return b.custom_rotation


def stamp_loops_cached(stem):
    from . import cut_presets
    if stem not in _STAMP_CACHE:
        try:
            _STAMP_CACHE[stem] = cut_presets.load_loops(stem)
        except (cg.CutError, ValueError, OSError):
            _STAMP_CACHE[stem] = None
    return _STAMP_CACHE[stem]


def stamp_cursor_point(xy):
    """Where the idle stamp preview is centred: exactly the cursor (window px)."""
    return (float(xy[0]), float(xy[1]))


def draw_stamp_cursor(context, xy):
    """Idle PNG stamp preview at the cursor (WorkSpaceTool.draw_cursor):
    the exact outline a click would cut, with the current size / rotation."""
    try:
        b = context.scene.mch_brush
        if b.shape != 'CUSTOM':
            return
        loops = stamp_loops_cached(context.scene.mch_png_preset)
        if not loops:
            return
        # 0.14: Blender draws tool cursors in WINDOW pixels and passes the mouse
        # in the same space (its own Select Circle cursor draws at ``xy`` as is).
        # Subtracting the region origin put the stamp off the mouse by the
        # viewport's offset inside the window.
        p = stamp_cursor_point(xy)
        sh = _shader()
        gpu.state.blend_set('ALPHA')
        for lp in custom_loops(loops, p, b.custom_size, b.custom_rotation):
            _draw_lines(sh, lp, _COLORS['CUT'], closed=True, width=1.5)
        gpu.state.blend_set('NONE')
    except Exception:      # never break viewport drawing
        pass


def step_line_width(context, factor, report=None):
    """0.24.21 [ / ] = Line Width smaller / bigger (Line mode band, like a brush size)."""
    brush = context.scene.mch_brush
    brush.line_width = max(0.0005, min(20.0, brush.line_width * factor))
    if report is not None:
        report({'INFO'}, f'Line Width {brush.line_width * 100:.2f} cm')
    return brush.line_width


class MCH_OT_line_width_step(bpy.types.Operator):
    """[ / ] in a Mecha drawing tool: Line Width smaller / bigger"""
    bl_idname = 'mch.line_width_step'
    bl_label = 'Line Width Step'
    bl_description = 'Line Width smaller ([) / bigger (])'
    bl_options = {'INTERNAL'}

    factor: FloatProperty(default=1.15, min=0.1, max=10.0)

    @classmethod
    def poll(cls, context):
        return getattr(context.scene, 'mch_brush', None) is not None

    def execute(self, context):
        step_line_width(context, self.factor, self.report)
        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}


class MCH_OT_stamp_rotate(bpy.types.Operator):
    """R in an idle Cut / Split tool with a PNG shape: rotate the stamp."""
    bl_idname = 'mch.stamp_rotate'
    bl_label = 'Rotate PNG Stamp'
    bl_description = 'Rotate the PNG stamp by 15° (Shift: back)'
    bl_options = {'INTERNAL'}

    sign: IntProperty(default=1, min=-1, max=1)

    @classmethod
    def poll(cls, context):
        brush = getattr(context.scene, 'mch_brush', None)
        return brush is not None and brush.shape == 'CUSTOM'   # else Blender's own R runs

    def execute(self, context):
        a = rotate_stamp(context, self.sign)
        self.report({'INFO'}, f'Stamp rotation {math.degrees(a):.0f}°')
        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}


class MCH_OT_exit_tool(bpy.types.Operator):
    """Esc in an idle Mecha tool: back to Blender's Select Box tool."""
    bl_idname = 'mch.exit_tool'
    bl_label = 'Leave Mecha Tool'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D'

    def execute(self, context):
        exit_tool(context)
        return {'FINISHED'}


CLASSES = (MCH_OT_cut_stroke, MCH_OT_rmb_gate, MCH_OT_exit_tool, MCH_OT_stamp_rotate, MCH_OT_line_width_step)
