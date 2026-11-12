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

from . import target_rules

MODES = {'HIDE', 'CAPE', 'HAIR', 'GARMENT', 'HOOD', 'SCARF', 'CUT', 'SPLIT', 'BASE', 'CBASE', 'PLATE', 'CPLATE', 'WRINKLE', 'ZONE', 'SPIKE', 'SCALES',
         'DETAIL', 'DETAIL2', 'DETAIL3'}      # 0.24.20 + Plate Detail 1 / 2 / 3
CAPS = (('ROUND', 'Round', 'Round line ends'), ('FLAT', 'Flat', 'Square line ends'))


ALWAYS = {'BELT', 'SCURVE', 'SDRAW', 'SCAPE'}      # these always draw a line (the cut engine's forced line mode)


def enabled(context, mode, shape=None):
    brush = getattr(getattr(context, 'scene', None), 'mch_brush', None)
    if brush is None or not getattr(brush, 'line_mode', False) or mode not in MODES:
        return False
    return shape is None or shape in {'LASSO', 'CURVE_LASSO', 'STROKE'}


def _resample(path, step, ceil=False):
    out = [tuple(path[0])]
    for a, b in zip(path, path[1:]):
        d = math.dist(a, b)
        n = max(1, int(math.ceil(d / step - 1e-9)) if ceil else int(d / step))
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


def _loop_area(pts):
    return 0.5 * abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1])))


def remove_loops(pts, max_area=None):
    """Cut out the little loops an offset curve makes on the inside of tight turns.  0.24.108 ``max_area``: a loop
    bigger than that is the stroke crossing itself (or its end meeting its start) - it is left alone for
    ``band_union`` to resolve exactly (splicing it away used to drop a whole side of the band: a closed stroke came
    out as a filled disc)."""
    pts = list(pts)
    changed = True
    guard = 0
    skip = set()
    while changed and guard < 200:
        changed = False
        guard += 1
        n = len(pts)
        for i in range(n - 1):
            for j in range(n - 2, i + 1, -1):
                if (i, j) in skip:
                    continue
                hit = _seg_hit(pts[i], pts[i + 1], pts[j], pts[j + 1])
                if hit is not None:
                    if max_area is not None and _loop_area([hit] + pts[i + 1:j + 1]) > max_area:
                        skip.add((i, j))
                        continue
                    pts = pts[:i + 1] + [hit] + pts[j + 1:]
                    changed = True
                    skip = set()
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


def taper_factor(t, taper):
    """Width factor at ``t`` (0..1 along the line) for Taper: pointed ends, full width in the middle - pure."""
    if taper <= 1e-6:
        return 1.0
    reach = 0.5 * taper                       # how far in from each end the thinning goes
    e = min(t, 1.0 - t) / max(reach, 1e-9)
    return max(0.0, min(1.0, e)) ** 0.6


def _profile_at(profile, t):
    """Linear lookup in [(t, value)] (sorted by t)."""
    if not profile:
        return 1.0
    if t <= profile[0][0]:
        return profile[0][1]
    for (t0, v0), (t1, v1) in zip(profile, profile[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * ((t - t0) / max(t1 - t0, 1e-12))
    return profile[-1][1]


def _prepared(path, width_px, taper=0.0, pressure=None):
    """The band's path as it is used: cleaned, resampled, smoothed; (path, half width, widths per point, normals)."""
    path = [tuple(p) for p in path]
    path = [p for i, p in enumerate(path) if i == 0 or math.dist(p, path[i - 1]) > 1e-6]
    if len(path) < 2:
        return [], 0.0, [], []
    hw = max(0.5, width_px / 2.0)
    from . import tool_state as _ts                  # 0.24.95 (user, a Line cut at Res 800 %: "덜 촘촘해"): the band's
    step = hw / 2.0 / _ts.res_scale()                # path was resampled every half half-width whatever the
    path = _resample(path, max(0.25, step), ceil=_ts.res_scale() > 1.0)   # Resolution - a wide band's curve came
    #                                                  out in 10 px facets (above 100 %: no segment over the step)
    path = _smooth(path, min(200, max(2, int(round(2 * _ts.res_scale() ** 2)))))   # (the same smoothing width:
    #                                                                   passes x the square of the point density)
    n = len(path)
    acc = [0.0]
    for a, b in zip(path, path[1:]):
        acc.append(acc[-1] + math.dist(a, b))
    total = acc[-1] or 1.0
    widths = [max(0.3, hw * taper_factor(d / total, taper) * _profile_at(pressure, d / total)) for d in acc]
    normals = []
    for i in range(n):
        a = path[max(0, i - 1)]
        b = path[min(n - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1.0
        normals.append((-dy / ln, dx / ln))
    return path, hw, widths, normals


def band(path, width_px, cap='ROUND', cap_segments=8, taper=0.0, pressure=None):
    """Closed outline (screen px) of a band ``width_px`` wide around an open polyline.  0.24.21 ``taper`` thins it
    to points at both ends, ``pressure`` = [(t along the line 0..1, factor)] (pen pressure) scales the width.
    A stroke that crosses itself or closes on itself gives an outline that crosses itself: ``line_loops`` /
    ``band_union`` turn that into clean loops."""
    if cap == 'POINT':                               # (Pointed: round tips, thinned - see ends_of)
        cap, taper = 'ROUND', max(taper, 0.5)
    path, hw, widths, normals = _prepared(path, width_px, taper, pressure)
    if len(path) < 2:
        return []
    n = len(path)
    varied = taper > 1e-6 or bool(pressure)
    big = 4.0 * hw * hw                              # (0.24.108 only the offset kinks are spliced away)
    left = [(p[0] + nx * w, p[1] + ny * w) for p, (nx, ny), w in zip(path, normals, widths)]
    right = [(p[0] - nx * w, p[1] - ny * w) for p, (nx, ny), w in zip(path, normals, widths)]
    left, right = remove_loops(left, big), remove_loops(right, big)
    if varied:
        hw_end, hw_start = widths[-1], widths[0]
    else:
        hw_end = hw_start = hw

    def cap_pts(center, nrm, forward, hw):
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
    loop = left + cap_pts(e, normals[-1], fwd_e, hw_end) + right[::-1]
    n0 = (-normals[0][0], -normals[0][1])
    loop += cap_pts(s, n0, fwd_s, hw_start)
    return remove_loops(loop + [loop[0]], big)[:-1]


# --- 0.24.108 a stroke that crosses or closes on itself ---------------------------------------------------------------
# (user: "선끼리 닿으면 내부가 채워지는데 ... 그냥 그리는 대로 유지되고 / 전체 영역을 도형으로")

def band_pieces(path, width_px, cap='ROUND', taper=0.0, pressure=None, disc_segments=16):
    """Pieces whose union is the band: a quad per path segment (consecutive quads share their edge exactly, so they
    tile the band without gaps - a quad on the inside of a tight turn may fold over itself, which the union
    takes as covered) and, with Round caps, a disc at each end.  (A disc at every point made edges that only
    touched the quads' edges: the Delaunay union left slivers and holes there.)"""
    path, hw, widths, normals = _prepared(path, width_px, taper, pressure)
    n = len(path)
    if n < 2:
        return []
    pieces = []
    for i in range(n - 1):
        (x0, y0), (x1, y1) = path[i], path[i + 1]
        (ax, ay), (bx, by) = normals[i], normals[i + 1]
        w0, w1 = widths[i], widths[i + 1]
        quad = [(x0 + ax * w0, y0 + ay * w0), (x1 + bx * w1, y1 + by * w1),
                (x1 - bx * w1, y1 - by * w1), (x0 - ax * w0, y0 - ay * w0)]
        if _loop_area(quad) > 1e-6:
            pieces.append(quad)
    if cap != 'FLAT':
        k = max(8, int(disc_segments))
        r_scale = 1.0 / math.cos(math.pi / k)        # (the polygon covers the circle, not inscribed in it)
        for i in (0, n - 1):
            (x, y), w = path[i], widths[i]
            r = w * r_scale
            if r < 0.3:
                continue
            pieces.append([(x + r * math.cos(2 * math.pi * j / k + 0.1), y + r * math.sin(2 * math.pi * j / k + 0.1))
                           for j in range(k)])
    return pieces


def union_loops(polys, fill=False, eps=1e-6):
    """Exact union of simple polygons (Blender's constrained Delaunay, the way the Sketch combines strokes):
    outer loops CCW + hole loops CW; ``fill`` drops the holes (the whole enclosed area).  Collinear points on the
    result are dropped; the loops have no self-crossings."""
    from . import base_mesh as bm_
    from . import core_geometry as cg
    polys = [[(float(q[0]), float(q[1])) for q in p] for p in polys if len(p) >= 3]
    if not polys:
        return []
    item = {'op': 'ADD', 'groups': [[p, []] for p in polys]}
    verts, tris = bm_.sketch_triangles([item])
    if not tris:
        return []
    loops = bm_._boundary_loops(verts, tris)
    loops = [cg.dedupe_loop([tuple(q) for q in lp], eps=1e-3) for lp in loops]
    loops = [lp for lp in loops if len(lp) >= 3 and _loop_area(lp) > 0.25]     # (no degenerate slivers)
    groups = cg.organize_loops(loops)
    out = []
    for outer, holes in groups:
        out.append([tuple(q) for q in outer])
        if not fill:
            out += [[tuple(q) for q in h] for h in holes]
    return out


def band_union(path, width_px, cap='ROUND', taper=0.0, pressure=None, fill=False):
    """The band of a stroke as clean loops, however the stroke crosses or closes on itself: outer loops (+ the
    holes it encloses, unless ``fill``)."""
    return union_loops(band_pieces(path, width_px, cap, taper, pressure), fill=fill)


def crosses(loop):
    from . import core_geometry as cg
    return len(loop) >= 4 and bool(cg.find_intersections([loop]))


def ends_of(brush):
    """(cap, taper) for a band from the brush: Line Ends Round / Flat, or Pointed = round tips + Taper Amount (the
    older Taper button still works with Round / Flat)."""
    cap = getattr(brush, 'line_caps', 'ROUND')
    amount = float(getattr(brush, 'line_taper', 0.5))
    if cap == 'POINT':
        return 'ROUND', max(amount, 0.05)
    return cap, (amount if getattr(brush, 'line_taper_on', False) else 0.0)


def line_loops(context, projector, path, brush, pressure=None, width_px=None):
    """0.24.108 The band(s) handed to a tool for an open path in Line mode.  A stroke that does not meet itself:
    the one band outline.  One that crosses or closes on itself: the exact union - with its holes as holes (a closed
    stroke = a ring), or, with the brush's Area on, filled (the whole region the line encloses is the shape).
    ``width_px``: the band's width on screen instead of the brush's Line Width (Press Cut: the stamp's width)."""
    if len(path) < 2:
        return []
    from . import tool_state as ts
    if width_px is not None:
        width = max(1.0, float(width_px))
    else:
        ppu = pixels_per_unit(context, projector, path[0])
        width = max(1.0, brush.line_width * ppu)
    cap, taper = ends_of(brush)
    prof = pressure if getattr(brush, 'line_pressure', False) else None
    loop = band(path, width, cap, cap_segments=ts.res_n(8, 2), taper=taper, pressure=prof)
    if len(loop) < 3:
        return []
    if not crosses(loop):
        return [loop]
    loops = band_union(path, width, cap, taper, prof, fill=bool(getattr(brush, 'line_area', False)))
    return loops or [loop]


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
        ok, loc, *_r = target_rules.scene_ray(context, dg, Vector(origin), direction)
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


def line_loop(context, projector, path, brush, pressure=None):
    """The band handed to the tool for an open path drawn in Line mode (Taper / pen Pressure, 0.24.21)."""
    if len(path) < 2:
        return []
    ppu = pixels_per_unit(context, projector, path[0])
    from . import tool_state as ts
    return band(path, max(1.0, brush.line_width * ppu), brush.line_caps, cap_segments=ts.res_n(8, 2),
                taper=getattr(brush, 'line_taper', 0.0) if getattr(brush, 'line_taper_on', False) else 0.0,
                pressure=pressure if getattr(brush, 'line_pressure', False) else None)


def pressure_profile(pts, pressures):
    """[(t along the drawn path 0..1, pressure)] from Free Draw samples - pure."""
    if not pts or len(pressures) != len(pts) or len(pts) < 2:
        return None
    acc = [0.0]
    for a, b in zip(pts, pts[1:]):
        acc.append(acc[-1] + math.dist(a, b))
    total = acc[-1] or 1.0
    return [(d / total, max(0.05, min(1.0, p))) for d, p in zip(acc, pressures)]
