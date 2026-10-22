"""0.22.0 Line lasso: draw a line instead of an area.

With the Line button on (next to Sketch in the viewport header) the Lasso, Curve
Lasso and Brush Stroke shapes are read as an OPEN path; the tool gets a band of
``Line Width`` around that path (round or flat ends) - a groove for Cut / Split,
a strip for Base Mesh / Armor Plate / Cloth Plate.  Lasso points: click points,
double-click / Enter finishes (2 points are enough).

``band`` is pure (screen space) and tested headless.
"""
from __future__ import annotations

import math

from mathutils import Vector

MODES = {'CUT', 'SPLIT', 'BASE', 'CBASE', 'PLATE', 'CPLATE', 'WRINKLE'}
CAPS = (('ROUND', 'Round', 'Round line ends'), ('FLAT', 'Flat', 'Square line ends'))


def enabled(context, mode, shape=None):
    brush = getattr(getattr(context, 'scene', None), 'mch_brush', None)
    if brush is None or not getattr(brush, 'line_mode', False) or mode not in MODES:
        return False
    return shape is None or shape in {'LASSO', 'CURVE_LASSO', 'STROKE'}


def _resample(path, step):
    out = [tuple(path[0])]
    for a, b in zip(path, path[1:]):
        d = math.dist(a, b)
        n = max(1, int(d / step))
        for k in range(1, n + 1):
            t = k / n
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    clean = [out[0]]
    for p in out[1:]:
        if math.dist(p, clean[-1]) > 1e-6:
            clean.append(p)
    return clean


def _seg_hit(p1, p2, p3, p4):
    d = (p2[0] - p1[0]) * (p4[1] - p3[1]) - (p2[1] - p1[1]) * (p4[0] - p3[0])
    if abs(d) < 1e-12:
        return None
    t = ((p3[0] - p1[0]) * (p4[1] - p3[1]) - (p3[1] - p1[1]) * (p4[0] - p3[0])) / d
    u = ((p3[0] - p1[0]) * (p2[1] - p1[1]) - (p3[1] - p1[1]) * (p2[0] - p1[0])) / d
    if 0.0 < t < 1.0 and 0.0 < u < 1.0:
        return (p1[0] + (p2[0] - p1[0]) * t, p1[1] + (p2[1] - p1[1]) * t)
    return None


def remove_loops(pts):
    """Cut out the little loops an offset curve makes on the inside of tight turns."""
    pts = list(pts)
    changed = True
    guard = 0
    while changed and guard < 200:
        changed = False
        guard += 1
        n = len(pts)
        for i in range(n - 1):
            for j in range(n - 2, i + 1, -1):
                hit = _seg_hit(pts[i], pts[i + 1], pts[j], pts[j + 1])
                if hit is not None:
                    pts = pts[:i + 1] + [hit] + pts[j + 1:]
                    changed = True
                    break
            if changed:
                break
    return pts


def _smooth(path, passes=2):
    for _ in range(passes):
        if len(path) < 3:
            return path
        path = [path[0]] + [((a[0] + 2 * b[0] + c[0]) / 4, (a[1] + 2 * b[1] + c[1]) / 4)
                            for a, b, c in zip(path, path[1:], path[2:])] + [path[-1]]
    return path


def band(path, width_px, cap='ROUND', cap_segments=8):
    """Closed outline (screen px) of a band ``width_px`` wide around an open polyline."""
    path = [tuple(p) for p in path]
    path = [p for i, p in enumerate(path) if i == 0 or math.dist(p, path[i - 1]) > 1e-6]
    if len(path) < 2:
        return []
    hw = max(0.5, width_px / 2.0)
    path = _resample(path, max(1.0, hw / 2.0))
    path = _smooth(path, 2)
    n = len(path)
    normals = []
    for i in range(n):
        a = path[max(0, i - 1)]
        b = path[min(n - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1.0
        normals.append((-dy / ln, dx / ln))
    left = [(p[0] + nx * hw, p[1] + ny * hw) for p, (nx, ny) in zip(path, normals)]
    right = [(p[0] - nx * hw, p[1] - ny * hw) for p, (nx, ny) in zip(path, normals)]
    left, right = remove_loops(left), remove_loops(right)

    def cap_pts(center, nrm, forward):
        """Points from the left side around the end to the right side."""
        if cap == 'FLAT':
            fx, fy = forward
            return [(center[0] + nrm[0] * hw + fx * hw, center[1] + nrm[1] * hw + fy * hw),
                    (center[0] - nrm[0] * hw + fx * hw, center[1] - nrm[1] * hw + fy * hw)]
        a0 = math.atan2(nrm[1], nrm[0])
        side = -1.0 if (nrm[0] * forward[1] - nrm[1] * forward[0]) < 0 else 1.0
        return [(center[0] + hw * math.cos(a0 + side * math.pi * k / cap_segments),
                 center[1] + hw * math.sin(a0 + side * math.pi * k / cap_segments))
                for k in range(1, cap_segments)]
    e = path[-1]
    fwd_e = (e[0] - path[-2][0], e[1] - path[-2][1])
    ln = math.hypot(*fwd_e) or 1.0
    fwd_e = (fwd_e[0] / ln, fwd_e[1] / ln)
    s = path[0]
    fwd_s = (s[0] - path[1][0], s[1] - path[1][1])
    ln = math.hypot(*fwd_s) or 1.0
    fwd_s = (fwd_s[0] / ln, fwd_s[1] / ln)
    loop = left + cap_pts(e, normals[-1], fwd_e) + right[::-1]
    n0 = (-normals[0][0], -normals[0][1])
    loop += cap_pts(s, n0, fwd_s)
    return remove_loops(loop + [loop[0]])[:-1]


def pixels_per_unit(context, projector, xy):
    """Screen pixels per metre at the surface under ``xy`` (or 1 m in front of the view)."""
    try:
        origin, direction = projector.ray(xy)
    except (AttributeError, TypeError, ValueError):
        return 100.0
    direction = Vector(direction).normalized()
    hit = None
    try:
        dg = context.evaluated_depsgraph_get()
        ok, loc, *_r = context.scene.ray_cast(dg, Vector(origin), direction)
        if ok:
            hit = loc
    except (AttributeError, RuntimeError, TypeError):
        hit = None
    if hit is None:
        rv3d = getattr(context, 'region_data', None)
        dist = getattr(rv3d, 'view_distance', 5.0) if rv3d is not None else 5.0
        hit = Vector(origin) + direction * dist
    o2, d2 = projector.ray((xy[0] + 10.0, xy[1]))
    d2 = Vector(d2).normalized()
    # point on the neighbouring ray at the same depth along the view
    t = (hit - Vector(o2)).dot(direction) / max(1e-6, d2.dot(direction))
    p2 = Vector(o2) + d2 * t
    world = (p2 - hit).length
    return 10.0 / world if world > 1e-9 else 100.0


def line_loop(context, projector, path, brush):
    """The band handed to the tool for an open path drawn in Line mode."""
    if len(path) < 2:
        return []
    ppu = pixels_per_unit(context, projector, path[0])
    return band(path, max(1.0, brush.line_width * ppu), brush.line_caps)
