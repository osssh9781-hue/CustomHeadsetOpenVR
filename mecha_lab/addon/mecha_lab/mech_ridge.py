"""0.24.24 Mech Ridge (Armor Plate profile): the mechanical cousin of Creature Plate's Ridge.

Every edge of the drawn outline slopes up at the same angle until it meets the slopes of the other edges: a faceted
roof (straight skeleton) with crisp ridge lines - a box lasso gives a hip roof, a long box a ridge down the middle.
Height caps it to a flat top (a mesa).  0.24.25: an Edge Pattern picks which edges slope (Hip, Gable, Every Other,
Half Hip, Corner, Shed, Custom per edge) and Turn steps it round the outline.  The ridge lines and the outer top edge each get their own Chamfer / Bevel.

How it is built (screen pixels, z in pixels too, so everything is isotropic):

    1. the outline is straightened (Douglas-Peucker, ``straighten`` px) and made counter-clockwise;
    2. a prism of the outline is cut by one convex cutter per edge: the part of that edge's wedge (between the two
       corner bisectors) above its slope plane.  min over the wedges = the roof, exact, so the facets are flat and
       the ridges are sharp.  One Exact Boolean (self intersection on) does all cutters at once;
    3. ridge lines (roof / roof) and the outer top edge (roof / wall) get their Chamfer / Bevel here, on the clean
       big faces (so no short edges limit the width);
    4. a grid of cuts adds inner points and every point is laid onto the mesh through the view (like Armor Plate)
       and pushed out along the smoothed surface normal by its height.

The plate is live (sliders rebuild it) until Apply.  ``simplify_closed``, ``ccw`` and ``wedge_planes`` are pure.
"""
from __future__ import annotations

import json
import math

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from mathutils import Matrix, Vector

from . import core_geometry as cg

SRC_KEY = 'mch_mridge_src'
COLLECTION = 'Armor Plates'
FINISH_ITEMS = [('NONE', 'Sharp', 'Sharp edge'), ('CHAMFER', 'Chamfer', 'One flat cut'),
                ('BEVEL', 'Bevel', 'Rounded (Segments)')]
LIVE_KEYS = ('pattern', 'turn', 'custom', 'angle', 'height', 'wall', 'sink', 'straighten', 'resolution', 'ridge_finish', 'ridge_width',
             'ridge_segments', 'edge_finish', 'edge_width', 'edge_segments', 'harden')
EDGE_LAYER = 'mch_mridge_edge'       # 1 = ridge line, 2 = outer top edge
ROUND_LAYER = 'mch_mridge_round'     # faces of a round bevel
CLICKED_MAX = 48                     # up to this many points with real edges (median >= CLICKED_EDGE px) the
CLICKED_EDGE = 10.0                  # outline is a clicked polygon and kept as drawn
MASK_KEY = 'mch_mridge_mask'         # sloped edges of the (first) outline, '1' / '0' per edge (for the panel)


# -----------------------------------------------------------------------------
# Pure helpers (2D, screen pixels)
# -----------------------------------------------------------------------------


def signed_area(pts):
    return 0.5 * sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))


def ccw(pts):
    pts = [tuple(map(float, q)) for q in pts]
    return pts if signed_area(pts) > 0 else pts[::-1]


def _dp(pts, tol):
    if len(pts) < 3:
        return pts
    a, b = Vector(pts[0]), Vector(pts[-1])
    ab = b - a
    best, idx = -1.0, 0
    for i in range(1, len(pts) - 1):
        p = Vector(pts[i])
        if ab.length < 1e-12:
            d = (p - a).length
        else:
            d = abs(ab.x * (p.y - a.y) - ab.y * (p.x - a.x)) / ab.length
        if d > best:
            best, idx = d, i
    if best <= tol:
        return [pts[0], pts[-1]]
    return _dp(pts[:idx + 1], tol)[:-1] + _dp(pts[idx:], tol)


def simplify_closed(pts, tol):
    """Straighten a closed outline: a free-drawn one (many points or tiny steps) gets Douglas-Peucker from
    the two farthest points and loses near-straight corners (< 2 degrees); a clicked polygon (pentagon, hexagon,
    ... a 24-gon) keeps every corner, only repeated clicks and dead straight ones (< 1 degree) go.  Keeps at
    least a triangle."""
    pts = [tuple(map(float, q)) for q in pts]
    if len(pts) > 1 and math.dist(pts[0], pts[-1]) < 1e-6:
        pts = pts[:-1]
    out = []
    for q in pts:                                     # drop repeated clicks
        if not out or math.dist(out[-1], q) > 0.5:
            out.append(q)
    if len(out) > 3 and math.dist(out[0], out[-1]) <= 0.5:
        out.pop()
    if len(out) <= 3:
        return out
    seg = sorted(math.dist(out[i - 1], out[i]) for i in range(len(out)))
    # 0.24.26 a clicked polygon (few points, real edges) keeps every corner you set; free draw = many tiny steps
    clicked = len(out) <= CLICKED_MAX and seg[len(seg) // 2] >= CLICKED_EDGE
    limit = math.radians(1.0 if clicked else 2.0)
    if not clicked and tol > 0:                     # a free-drawn outline: straight edges
        i1 = max(range(len(out)), key=lambda i: math.dist(out[i], out[0]))
        a = out[:i1 + 1]
        b = out[i1:] + out[:1]
        out = _dp(a, tol)[:-1] + _dp(b, tol)[:-1]
    changed = True
    while changed and len(out) > 3:
        changed = False
        for i in range(len(out)):
            p, q, r = Vector(out[i - 1]), Vector(out[i]), Vector(out[(i + 1) % len(out)])
            u, v = q - p, r - q
            if u.length < 1e-9 or v.length < 1e-9 or abs(u.angle(v)) < limit:
                out.pop(i)
                changed = True
                break
    return out


def _inward(a, b):
    d = Vector((b[0] - a[0], b[1] - a[1]))
    if d.length < 1e-12:
        return Vector((0.0, 0.0))
    d.normalize()
    return Vector((-d.y, d.x))           # left of the edge = inside for a counter-clockwise outline


def long_axis(poly):
    """Unit direction of the long side of the outline (principal axis of its corners)."""
    cx = sum(q[0] for q in poly) / len(poly)
    cy = sum(q[1] for q in poly) / len(poly)
    sxx = sum((q[0] - cx) ** 2 for q in poly)
    syy = sum((q[1] - cy) ** 2 for q in poly)
    sxy = sum((q[0] - cx) * (q[1] - cy) for q in poly)
    ang = 0.5 * math.atan2(2 * sxy, sxx - syy)
    return Vector((math.cos(ang), math.sin(ang)))


def end_edges(poly, swap=False):
    """0.24.24 Gable: the edges across the ridge direction (more than 60 degrees off the long axis) do not slope -
    the ridge runs straight to them and they stay upright walls."""
    axis = long_axis(poly)
    if swap:
        axis = Vector((-axis.y, axis.x))
    out = set()
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        d = Vector((b[0] - a[0], b[1] - a[1]))
        if d.length > 1e-9 and abs(d.normalized().dot(axis)) < 0.5:
            out.add(i)
    if len(out) == len(poly):
        out.clear()
    return out


PATTERN_ITEMS = [
    ('HIP', 'All Edges (Hip)', 'Every edge slopes up to the ridge'),
    ('LONG', 'Gable (long side)', 'The ridge runs along the long side straight to the ends; the ends stay upright '
                                  '(Turn: across instead)'),
    ('ALTERNATE', 'Every Other Edge', 'Every second edge slopes, the others stay upright (Turn: shift by one)'),
    ('HALF', 'Half Hip', 'All edges but one slope: one upright end (Turn: which one)'),
    ('CORNER', 'Corner', 'Two neighbouring edges slope (Turn: which corner)'),
    ('SHED', 'Shed (one edge)', 'Only one edge slopes: a single slope rising to the upright far side (Turn: which '
                                'edge)'),
    ('CUSTOM', 'Custom', 'Pick every edge yourself (the numbered buttons)'),
]


def sloped_edges(poly, pattern, turn=0, custom=''):
    """0.24.25 which edges of the outline slope (the others stay upright walls; the slopes run on to them).
    ``turn`` steps the pattern round the outline one edge at a time (edges in drawing order)."""
    n = len(poly)
    r = turn % n if n else 0
    if pattern == 'LONG':
        out = set(range(n)) - end_edges(poly, swap=bool(turn % 2))
    elif pattern == 'ALTERNATE':
        out = {i for i in range(n) if (i - r) % 2 == 0}
    elif pattern == 'HALF':
        out = set(range(n)) - {r}
    elif pattern == 'CORNER':
        out = {r, (r + 1) % n}
    elif pattern == 'SHED':
        out = {r}
    elif pattern == 'CUSTOM':
        out = {i for i in range(n) if (custom[i] if i < len(custom) else '1') == '1'}
    else:
        out = set(range(n))
    return out or set(range(n))


def wedge_planes(poly, i, slope, wall, margin=2.0, overlap=0.5, ends=()):
    """Half-spaces (a, d) with a . (x, y, z) + d >= 0 that make edge ``i``'s cutter: inside its line (a bit past
    it), between the corner bisectors (a hair wider, so neighbours overlap) and above its slope plane."""
    n = len(poly)
    p0, p1 = poly[i], poly[(i + 1) % n]
    ni = _inward(p0, p1)
    out = []
    # 1. inside of the edge line (margin past the outline: the prism walls cut that away)
    out.append((Vector((ni.x, ni.y, 0.0)), -(ni.x * p0[0] + ni.y * p0[1]) + margin))
    # 2. corner bisectors
    for corner, other, prev_edge, nb in ((p0, p1, (poly[i - 1], p0), (i - 1) % n),
                                         (p1, p0, (p1, poly[(i + 2) % n]), (i + 1) % n)):
        if nb in ends:
            continue                     # next to a gable end: the slope runs on to the end wall
        nn = _inward(*prev_edge)
        b = ni + nn
        if b.length < 1e-9:
            b = ni.copy()
        b.normalize()
        m = Vector((-b.y, b.x))
        if m.dot(Vector((other[0] - corner[0], other[1] - corner[1]))) < 0:
            m = -m
        out.append((Vector((m.x, m.y, 0.0)), -(m.x * corner[0] + m.y * corner[1]) + overlap))
    # 3. above the slope plane z = wall + slope * dist(line)
    a = Vector((-slope * ni.x, -slope * ni.y, 1.0))
    out.append((a, -wall + slope * (ni.x * p0[0] + ni.y * p0[1])))
    return out


# -----------------------------------------------------------------------------
# Geometry
# -----------------------------------------------------------------------------


def _box(lo, hi):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    c, s = (lo + hi) / 2, hi - lo
    for v in bm.verts:
        v.co = Vector((c.x + v.co.x * s.x, c.y + v.co.y * s.y, c.z + v.co.z * s.z))
    return bm


def _clip(bm, a, d):
    """Keep a . p + d >= 0 of a convex closed bmesh (cap the cut)."""
    if a.length < 1e-12:
        return
    co = -a * (d / a.length_squared)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6, plane_co=co,
                           plane_no=-a, clear_outer=True)
    open_edges = [e for e in bm.edges if len(e.link_faces) < 2]
    if open_edges:
        bmesh.ops.holes_fill(bm, edges=open_edges, sides=0)


def _prism(poly, top):
    bm = bmesh.new()
    vb = [bm.verts.new((x, y, 0.0)) for x, y in poly]
    vt = [bm.verts.new((x, y, top)) for x, y in poly]
    bm.faces.new(vb[::-1])
    bm.faces.new(vt)
    n = len(poly)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((vb[i], vb[j], vt[j], vt[i]))
    return bm


def _boolean_difference(context, bm_a, bm_b):
    me_a = bpy.data.meshes.new('MCH_MRidge_A')
    me_b = bpy.data.meshes.new('MCH_MRidge_B')
    bm_a.to_mesh(me_a)
    bm_b.to_mesh(me_b)
    a = cg.link_temp_object(context, me_a, 'MCH_MRidge_A')
    b = cg.link_temp_object(context, me_b, 'MCH_MRidge_B')
    try:
        mod = a.modifiers.new('MCH_MRidge', 'BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.solver = 'EXACT'
        mod.object = b
        if hasattr(mod, 'use_self'):
            mod.use_self = True
        dg = context.evaluated_depsgraph_get()
        ev = a.evaluated_get(dg)
        res = bpy.data.meshes.new_from_object(ev, depsgraph=dg)
    finally:
        cg.remove_object_and_mesh(a)
        cg.remove_object_and_mesh(b)
    out = bmesh.new()
    out.from_mesh(res)
    bpy.data.meshes.remove(res)
    return out


def _boolean_difference_each(context, bm_a, cutters):
    """0.24.26 one Boolean per (convex) cutter, Manifold solver (fast) - Exact with self intersection when the
    Manifold result is not a closed mesh."""
    solvers = ('MANIFOLD', 'EXACT')
    for solver in solvers:
        made = []
        try:
            me_a = bpy.data.meshes.new('MCH_MRidge_A')
            bm_a.to_mesh(me_a)
            a = cg.link_temp_object(context, me_a, 'MCH_MRidge_A')
            made.append(a)
            for k, c in enumerate(cutters):
                me = bpy.data.meshes.new('MCH_MRidge_C')
                c.to_mesh(me)
                ob = cg.link_temp_object(context, me, 'MCH_MRidge_C')
                made.append(ob)
                mod = a.modifiers.new(f'MCH_MRidge{k}', 'BOOLEAN')
                mod.operation = 'DIFFERENCE'
                try:
                    mod.solver = solver
                except TypeError:
                    raise RuntimeError('solver missing')
                mod.object = ob
                if solver == 'EXACT' and hasattr(mod, 'use_self'):
                    mod.use_self = True
            dg = context.evaluated_depsgraph_get()
            res = bpy.data.meshes.new_from_object(a.evaluated_get(dg), depsgraph=dg)
        except RuntimeError:
            res = None
        finally:
            for ob in made:
                cg.remove_object_and_mesh(ob)
        if res is None:
            continue
        out = bmesh.new()
        out.from_mesh(res)
        bpy.data.meshes.remove(res)
        if out.faces and all(e.is_manifold for e in out.edges):
            return out
        out.free()
    raise cg.CutError('Could not build the Mech Ridge roof for this outline (try fewer, larger edges).')


def roof_bmesh(context, poly, slope, wall, cap, ends=()):
    """The faceted roof solid of one outline (pixels; z = height in pixels)."""
    xs, ys = [q[0] for q in poly], [q[1] for q in poly]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
    ridge_top = wall + slope * span            # higher than any roof point
    prism = _prism(poly, ridge_top * 1.5 + 5.0)   # above the highest roof point (a Shed rises across all of it)
    if is_convex(poly):
        # 0.24.26 a convex outline: the roof is the prism under every sloped edge's plane (exact, no Boolean -
        # instant for any number of edges)
        try:
            for i in range(len(poly)):
                if i in ends:
                    continue
                p0, p1 = poly[i], poly[(i + 1) % len(poly)]
                ni = _inward(p0, p1)
                _clip(prism, Vector((slope * ni.x, slope * ni.y, -1.0)), wall - slope * (ni.x * p0[0] + ni.y * p0[1]))
            if cap > wall:
                _clip(prism, Vector((0.0, 0.0, -1.0)), cap)
            # many planes meeting in one apex (a 20+ sided hip) leave slivers there
            bmesh.ops.remove_doubles(prism, verts=prism.verts[:], dist=0.02)
            bmesh.ops.dissolve_degenerate(prism, dist=0.02, edges=prism.edges[:])
        except Exception:
            prism.free()
            raise
        if prism.faces and all(e.is_manifold for e in prism.edges):
            return _tidy_roof(prism)
        prism.free()                     # odd case: the Boolean way below
        prism = _prism(poly, ridge_top * 1.5 + 5.0)
    lo = Vector((min(xs) - span, min(ys) - span, -1.0))
    hi = Vector((max(xs) + span, max(ys) + span, ridge_top * 2 + 10.0))
    cutters = []
    for i in range(len(poly)):
        if i in ends:
            continue                     # a gable end does not slope
        c = _box(lo, hi)
        for a, d in wedge_planes(poly, i, slope, wall, ends=ends):
            _clip(c, a, d)
            if not c.faces:
                break
        if c.faces:
            cutters.append(c)
        else:
            c.free()
    if cap > wall:
        cutters.append(_box(Vector((lo.x, lo.y, cap)), hi))
    try:
        roof = _boolean_difference_each(context, prism, cutters)
    finally:
        prism.free()
        for c in cutters:
            c.free()
    return _tidy_roof(roof)


def _tidy_roof(roof):
    """Merge the doubled corners the Boolean leaves and dissolve the extra edges inside flat facets; each step is
    undone when it would open the mesh (odd concave outlines)."""
    roof = cg._safe_step(roof, lambda b: bmesh.ops.remove_doubles(b, verts=b.verts[:], dist=1e-3))
    roof = cg._safe_step(roof, lambda b: bmesh.ops.dissolve_limit(b, angle_limit=math.radians(0.2),
                                                                  verts=b.verts[:], edges=b.edges[:]))
    bmesh.ops.recalc_face_normals(roof, faces=roof.faces[:])
    return roof


def is_convex(poly, eps=1e-6):
    """Counter-clockwise outline with no inward (reflex) corner."""
    n = len(poly)
    for i in range(n):
        a, b, c = poly[i - 1], poly[i], poly[(i + 1) % n]
        if (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) < -eps:
            return False
    return True


def mark_edges(bm):
    """Edge layer: 1 = ridge line (two roof faces meeting at an angle), 2 = outer top edge (roof / wall)."""
    lay = bm.edges.layers.int.get(EDGE_LAYER) or bm.edges.layers.int.new(EDGE_LAYER)
    bm.normal_update()
    for e in bm.edges:
        e[lay] = 0
        if len(e.link_faces) != 2:
            continue
        f, g = e.link_faces
        rf, rg = f.normal.z > 0.05, g.normal.z > 0.05
        wf, wg = abs(f.normal.z) <= 0.05, abs(g.normal.z) <= 0.05
        if rf and rg and f.normal.angle(g.normal) > math.radians(0.5):
            e[lay] = 1
        elif (rf and wg) or (rg and wf):
            e[lay] = 2
    return lay


def _finish(bm, lay, kind, mode, width, segments):
    if mode == 'NONE' or width <= 0:
        return 0
    edges = [e for e in bm.edges if e.is_valid and e[lay] == kind]
    if not edges:
        return 0
    rl = bm.faces.layers.int.get(ROUND_LAYER) or bm.faces.layers.int.new(ROUND_LAYER)   # before: a new layer
    lay = bm.edges.layers.int.get(EDGE_LAYER)                                            # drops references
    edges = [e for e in bm.edges if e.is_valid and e[lay] == kind]
    verts = list({v for e in edges for v in e.verts})
    res = bmesh.ops.bevel(bm, geom=edges + verts, offset=width, offset_type='OFFSET',
                          segments=1 if mode == 'CHAMFER' else max(1, segments), profile=0.5, affect='EDGES',
                          clamp_overlap=True, loop_slide=True)
    if mode == 'BEVEL' and segments > 1:
        for f in res.get('faces', []):
            f[rl] = 1                        # the steps of a round bevel shade smooth
    return len(edges)


FINISH_NOTES = []


def _finish_safe(bm, kind, mode, width, segments):
    """0.24.26 Blender's bevel can tear where many ridge lines meet at an inward corner (a star outline): try the
    width, then half, then a quarter; never keep a torn mesh (the finish is left off and a note says so)."""
    if mode == 'NONE' or width <= 0:
        return bm
    for factor in (1.0, 0.5, 0.25):
        work = bm.copy()
        lay = work.edges.layers.int.get(EDGE_LAYER)
        open0 = sum(1 for e in work.edges if not e.is_manifold)
        _finish(work, lay, kind, mode, width * factor, segments)
        if sum(1 for e in work.edges if not e.is_manifold) <= open0:
            bm.free()
            if factor < 1.0:
                FINISH_NOTES.append(f'{"ridge" if kind == 1 else "edge"} {mode.lower()} narrowed to '
                                    f'{int(factor * 100)}% (tight corners)')
            return work
        work.free()
    FINISH_NOTES.append(f'{"ridge" if kind == 1 else "edge"} {mode.lower()} left off here (corners too tight)')
    return bm


def mark_creases(bm):
    """In pixels every facet is exactly flat, so every edge with an angle is a real crease: mark it sharp, except
    the steps inside a round bevel.  Everything shades smooth; later grid cuts keep the marks."""
    rl = bm.faces.layers.int.get(ROUND_LAYER)
    bm.normal_update()
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        e.smooth = True
        if len(e.link_faces) != 2:
            continue
        f, g = e.link_faces
        if rl is not None and f[rl] and g[rl]:
            continue
        if f.normal.angle(g.normal, 0.0) > math.radians(0.5):
            e.smooth = False


def grid_cut(bm, step):
    """Inner points so the plate can follow a curved surface (planar cuts keep the facets flat in pixels)."""
    if step <= 0:
        return
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    for axis, lo, hi in ((0, min(xs), max(xs)), (1, min(ys), max(ys))):
        k = math.floor(lo / step) + 1
        while k * step < hi:
            co = Vector((k * step, 0, 0)) if axis == 0 else Vector((0, k * step, 0))
            no = Vector((1, 0, 0)) if axis == 0 else Vector((0, 1, 0))
            bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-5, plane_co=co,
                                   plane_no=no)
            k += 1
    # a cut right through a ridge point leaves zero-size slivers (undone if it would open the mesh)
    work = cg._safe_step(bm.copy(), lambda b: bmesh.ops.dissolve_degenerate(b, dist=1e-3, edges=b.edges[:]))
    if sum(1 for e in work.edges if not e.is_manifold) <= sum(1 for e in bm.edges if not e.is_manifold):
        bm.clear()
        tmp = bpy.data.meshes.new('MCH_MRidge_grid')
        try:
            work.to_mesh(tmp)
            bm.from_mesh(tmp)
        finally:
            bpy.data.meshes.remove(tmp)
    work.free()


# -----------------------------------------------------------------------------
# Live object
# -----------------------------------------------------------------------------


def source(ob):
    if ob is None:
        return None
    try:
        raw = ob.get(SRC_KEY)
        return json.loads(raw) if raw else None
    except (TypeError, ValueError, ReferenceError):
        return None


def _world_per_px(context, projector, bvh, poly):
    from . import armor_plate as ap
    pts = []
    for a, b in zip(poly, poly[1:] + poly[:1]):
        for t in (0.0, 0.5):
            pts.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    cx = sum(q[0] for q in poly) / len(poly)
    cy = sum(q[1] for q in poly) / len(poly)
    pts.append((cx, cy))
    cos, _n, _m = ap.project_patch(pts, projector, bvh)
    ratios = []
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            dp = math.dist(pts[i], pts[j])
            if dp > 1.0:
                ratios.append((cos[i] - cos[j]).length / dp)
    ratios.sort()
    return ratios[len(ratios) // 2] if ratios else 0.01, cos


def build(context, src, p, target):
    """BMesh (world space) of the plate.  Returns (bm, size)."""
    from . import armor_plate as ap
    projector = ap.thaw_projector(src['proj'])
    bvh, _wv, _polys = ap._target_bvh(context, target)
    groups = cg.prepare_loops([[tuple(q) for q in lp] for lp in src['loops']])
    if not groups:
        raise cg.CutError('The outline is empty.')
    out = bmesh.new()
    tmp = bpy.data.meshes.new('MCH_MRidge_part')
    size = 0.0
    try:
        for outer, _holes in groups:
            poly = ccw(simplify_closed(outer, p.straighten))
            if len(poly) < 3 or abs(signed_area(poly)) < 4.0:
                continue
            k, cos = _world_per_px(context, projector, bvh, poly)
            lo = Vector([min(c[i] for c in cos) for i in range(3)])
            hi = Vector([max(c[i] for c in cos) for i in range(3)])
            size = max(size, (hi - lo).length)
            wall = (p.wall if p.wall > 0 else 0.03 * (hi - lo).length) / k
            cap = p.height / k if p.height > 0 else 0.0
            sloped = sloped_edges(poly, p.pattern, p.turn, p.custom)
            ends = set(range(len(poly))) - sloped
            owner = p.id_data
            if isinstance(owner, bpy.types.Object) and not out.verts:
                owner[MASK_KEY] = ''.join('1' if i in sloped else '0' for i in range(len(poly)))
            roof = roof_bmesh(context, poly, math.tan(p.angle), wall, cap, ends)
            try:
                lay = mark_edges(roof)
                auto = (hi - lo).length
                roof = _finish_safe(roof, 2, p.edge_finish,
                                    (p.edge_width if p.edge_width > 0 else 0.012 * auto) / k, p.edge_segments)
                roof = _finish_safe(roof, 1, p.ridge_finish,
                                    (p.ridge_width if p.ridge_width > 0 else 0.012 * auto) / k, p.ridge_segments)
                mark_creases(roof)
                xs = [q[0] for q in poly]
                ys = [q[1] for q in poly]
                grid_cut(roof, max(max(xs) - min(xs), max(ys) - min(ys)) / max(2, p.resolution))
                _lay_on_surface(roof, projector, bvh, k, p.sink if p.sink > 0 else 0.02 * auto)
                roof.to_mesh(tmp)
                out.from_mesh(tmp)
            finally:
                roof.free()
    finally:
        bpy.data.meshes.remove(tmp)
    if not out.verts:
        out.free()
        raise cg.CutError('The outline is too small for a Mech Ridge plate.')
    return out, size


def _lay_on_surface(bm, projector, bvh, k, sink):
    from . import armor_plate as ap
    from mathutils.kdtree import KDTree
    keys = {}
    for v in bm.verts:
        keys.setdefault((round(v.co.x, 3), round(v.co.y, 3)), []).append(v)
    xy = list(keys)
    cos, nrms, _m = ap.project_patch(xy, projector, bvh)
    # smooth the surface normals (a faceted body would show through every facet)
    kd = KDTree(len(xy))
    for i, q in enumerate(xy):
        kd.insert((q[0], q[1], 0.0), i)
    kd.balance()
    xs = [q[0] for q in xy]
    ys = [q[1] for q in xy]
    radius = max(max(xs) - min(xs), max(ys) - min(ys), 1.0) * 0.08
    smooth = []
    for q in xy:
        acc = Vector()
        for _co, j, dist in kd.find_range((q[0], q[1], 0.0), radius):
            acc += nrms[j] * (1.0 - dist / radius + 1e-3)
        smooth.append(acc.normalized() if acc.length > 1e-9 else nrms[xy.index(q)])
    for i, q in enumerate(xy):
        for v in keys[q]:
            h = v.co.z * k
            v.co = cos[i] + smooth[i] * (h - sink if h > 1e-9 * k else -sink)


def rebuild(context, ob):
    src = source(ob)
    if src is None:
        raise cg.CutError('This plate was applied (no outline kept).')
    target = bpy.data.objects.get(src.get('target', ''))
    if target is None or target.type != 'MESH':
        raise cg.CutError('The mesh the plate was drawn on is gone.')
    p = ob.mch_mridge
    FINISH_NOTES.clear()
    bm, _size = build(context, src, p, target)
    ob['mch_mridge_notes'] = '; '.join(FINISH_NOTES)
    try:
        bmesh.ops.transform(bm, matrix=ob.matrix_world.inverted_safe(), verts=bm.verts[:])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.to_mesh(ob.data)
        from . import edge_memory as _em; _em.mark_generated(ob.data)   # 0.24.95 Edge Memory: the part's own lines
    finally:
        bm.free()
    _shade(ob.data, p.harden, p.angle)
    ob.data.update()


def _shade(me, harden, slope):
    """Smooth Bevels on: everything shades smooth and only the real creases are sharp (marked exactly while the
    plate is still flat, ``mark_creases``), so facets read clean on a curved body and edges stay crisp.  Off:
    everything flat."""
    if not harden:
        for poly in me.polygons:
            poly.use_smooth = False


def _update(self, context):
    ob = self.id_data
    if not isinstance(ob, bpy.types.Object) or not self.live:
        return
    try:
        rebuild(context, ob)
        self.last_error = ''
    except (cg.CutError, ValueError, RuntimeError) as ex:
        self.last_error = str(ex)
    st = getattr(getattr(context, 'scene', None), 'mch_mridge', None)
    if st is not None:                       # the next plate starts like this one
        for k in LIVE_KEYS:
            try:
                if getattr(st, k) != getattr(self, k):
                    setattr(st, k, getattr(self, k))
            except (AttributeError, TypeError):
                pass


class MCH_PG_MechRidge(bpy.types.PropertyGroup):
    """Scene.mch_mridge = settings for the next plate; Object.mch_mridge = live plate."""
    pattern: EnumProperty(name='Edge Pattern', items=PATTERN_ITEMS, default='HIP', update=_update,
                          description='Which edges slope up to the ridge (the others stay upright walls)')
    turn: IntProperty(name='Turn', default=0, update=_update,
                      description='Step the pattern round the outline, one edge at a time')
    custom: StringProperty(name='Custom Edges', default='', update=_update,
                           description='Custom: 1 = the edge slopes, 0 = it stays upright (one per edge)')
    angle: FloatProperty(name='Slope', default=math.radians(25), min=math.radians(2), max=math.radians(75),
                         subtype='ANGLE', update=_update, description='How steep every side rises to the ridge')
    height: FloatProperty(name='Max Height', default=0.0, min=0.0, soft_max=2.0, precision=4, unit='LENGTH',
                          update=_update, description='Cut the ridge flat at this height (0 = full ridge)')
    wall: FloatProperty(name='Edge Wall', default=0.0, min=0.0, soft_max=0.5, precision=4, unit='LENGTH',
                        update=_update, description='Straight side wall under the slopes (0 = Auto, 3% of the '
                                                    'plate size)')
    sink: FloatProperty(name='Sink', default=0.0, min=0.0, soft_max=0.5, precision=4, unit='LENGTH',
                        update=_update, description='How far the bottom goes into the surface (0 = Auto)')
    straighten: FloatProperty(name='Straighten (px)', default=6.0, min=0.0, max=60.0, update=_update,
                              description='Free-drawn outlines become straight edges (bigger = fewer facets)')
    resolution: IntProperty(name='Resolution', default=10, min=2, max=60, update=_update,
                            description='Inner cuts so the plate follows a curved surface')
    ridge_finish: EnumProperty(name='Ridge', items=FINISH_ITEMS, default='CHAMFER', update=_update,
                               description='Finish of the ridge lines (where two slopes meet)')
    ridge_width: FloatProperty(name='Ridge Width', default=0.0, min=0.0, soft_max=0.2, precision=4,
                               unit='LENGTH', update=_update, description='0 = Auto (1.2% of the plate size)')
    ridge_segments: IntProperty(name='Ridge Segments', default=3, min=1, max=12, update=_update)
    edge_finish: EnumProperty(name='Edge', items=FINISH_ITEMS, default='CHAMFER', update=_update,
                              description='Finish of the outer top edge (slopes / side wall)')
    edge_width: FloatProperty(name='Edge Width', default=0.0, min=0.0, soft_max=0.2, precision=4, unit='LENGTH',
                              update=_update, description='0 = Auto (1.2% of the plate size)')
    edge_segments: IntProperty(name='Edge Segments', default=3, min=1, max=12, update=_update)
    harden: BoolProperty(name='Smooth Bevels', default=True, update=_update,
                         description='Bevels shade round, flat facets stay crisp')
    live: BoolProperty(default=False, options={'HIDDEN'})
    last_error: StringProperty(default='', options={'HIDDEN', 'SKIP_SAVE'})


def perform(context, loops, projector):
    """Lasso -> a live Mech Ridge plate on the mesh under it.  Returns a report; raises cg.CutError."""
    from . import armor_plate as ap
    from . import face_extract as fx
    scene = context.scene
    st = scene.mch_mridge
    groups = cg.prepare_loops(loops)
    target = ap.pick_surface(context, projector, groups)
    if target is None:
        raise cg.CutError('Draw the plate over a mesh (armour parts and plates are skipped).')
    frozen = ap.freeze_projector(projector)
    if frozen is None:
        raise cg.CutError('This view cannot be saved for the plate.')
    me = bpy.data.meshes.new(target.name + '_MechRidge')
    ob = bpy.data.objects.new(me.name, me)
    fx._parts_collection(context, COLLECTION).objects.link(ob)
    for mat in target.data.materials:
        me.materials.append(mat)
    ob[SRC_KEY] = json.dumps({'loops': [[[float(x), float(y)] for x, y in lp] for lp in loops], 'proj': frozen,
                              'target': target.name})
    p = ob.mch_mridge
    for k in LIVE_KEYS:
        setattr(p, k, getattr(st, k))
    try:
        rebuild(context, ob)
    except Exception:
        bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.meshes.remove(me)
        raise
    cen = sum((v.co for v in me.vertices), Vector()) / max(1, len(me.vertices))
    me.transform(Matrix.Translation(-cen))
    ob.matrix_world = Matrix.Translation(cen)
    p.live = True
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    return f'Mech Ridge plate "{ob.name}" on {target.name} ({len(me.polygons)} faces)'


def live_plate(context):
    ob = getattr(context, 'active_object', None)
    if ob is not None and getattr(ob, 'mch_mridge', None) is not None and ob.mch_mridge.live and source(ob):
        return ob
    return None


def apply(ob):
    ob.mch_mridge.live = False
    if SRC_KEY in ob:
        del ob[SRC_KEY]


class MCH_OT_mridge_apply(bpy.types.Operator):
    bl_idname = 'mch.mridge_apply'
    bl_label = 'Apply Mech Ridge'
    bl_description = 'The plate becomes a plain mesh (the sliders stop rebuilding it)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return live_plate(context) is not None

    def execute(self, context):
        apply(live_plate(context))
        return {'FINISHED'}


def draw(layout, context):
    ob = live_plate(context)
    p = ob.mch_mridge if ob is not None else context.scene.mch_mridge
    box = layout.box()
    if ob is not None:
        box.label(text='LIVE Mech Ridge: ' + ob.name, icon='MOD_BEVEL')
        if p.last_error:
            box.label(text=p.last_error, icon='ERROR')
        if ob.get('mch_mridge_notes'):
            box.label(text=ob['mch_mridge_notes'], icon='INFO')
    else:
        box.label(text='Mech Ridge: settings for the next plate', icon='MOD_BEVEL')
    r = box.row(align=True)
    r.prop(p, 'pattern', text='')
    if p.pattern not in {'HIP', 'CUSTOM'}:
        r.operator('mch.mridge_turn', text='', icon='TRIA_LEFT').step = -1
        r.label(text=f'Turn {p.turn}')
        r.operator('mch.mridge_turn', text='', icon='TRIA_RIGHT').step = 1
    mask = ob.get(MASK_KEY, '') if ob is not None else ''
    if mask:
        er = box.row(align=True)
        er.label(text='Edges')
        for i, bit in enumerate(mask[:24]):
            er.operator('mch.mridge_edge_toggle', text=str(i + 1), depress=(bit == '1')).index = i
    col = box.column(align=True)
    col.prop(p, 'angle')
    col.prop(p, 'height')
    col.prop(p, 'wall')
    col.prop(p, 'sink')
    for label, fin, width, seg in (('Ridge Lines', 'ridge_finish', 'ridge_width', 'ridge_segments'),
                                   ('Outer Edge', 'edge_finish', 'edge_width', 'edge_segments')):
        sub = box.column(align=True)
        sub.label(text=label)
        sub.row(align=True).prop(p, fin, expand=True)
        if getattr(p, fin) != 'NONE':
            r = sub.row(align=True)
            r.prop(p, width, text='Width')
            if getattr(p, fin) == 'BEVEL':
                r.prop(p, seg, text='Segments')
    col = box.column(align=True)
    col.prop(p, 'straighten')
    col.prop(p, 'resolution')
    col.prop(p, 'harden', toggle=True)
    if ob is not None:
        box.operator('mch.mridge_apply', icon='CHECKMARK')


def _settings(context):
    ob = live_plate(context)
    return (ob.mch_mridge if ob is not None else context.scene.mch_mridge), ob


class MCH_OT_mridge_turn(bpy.types.Operator):
    """Step the edge pattern round the outline (one edge)"""
    bl_idname = 'mch.mridge_turn'
    bl_label = 'Turn Edge Pattern'
    bl_options = {'REGISTER', 'UNDO'}
    step: IntProperty(default=1)

    def execute(self, context):
        p, _ob = _settings(context)
        p.turn = p.turn + self.step
        return {'FINISHED'}


class MCH_OT_mridge_edge_toggle(bpy.types.Operator):
    """This edge slopes / stays upright (switches the pattern to Custom)"""
    bl_idname = 'mch.mridge_edge_toggle'
    bl_label = 'Toggle Edge'
    bl_options = {'REGISTER', 'UNDO'}
    index: IntProperty(default=0)

    @classmethod
    def poll(cls, context):
        return live_plate(context) is not None

    def execute(self, context):
        ob = live_plate(context)
        p = ob.mch_mridge
        mask = list(ob.get(MASK_KEY, '') or '')
        if not 0 <= self.index < len(mask):
            return {'CANCELLED'}
        mask[self.index] = '0' if mask[self.index] == '1' else '1'
        if '1' not in mask:
            self.report({'WARNING'}, 'At least one edge must slope')
            return {'CANCELLED'}
        p.live = False                      # one rebuild at the end
        p.custom = ''.join(mask)
        p.pattern = 'CUSTOM'
        p.live = True
        rebuild(context, ob)
        return {'FINISHED'}


CLASSES = (MCH_PG_MechRidge, MCH_OT_mridge_apply, MCH_OT_mridge_turn, MCH_OT_mridge_edge_toggle)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_mridge = bpy.props.PointerProperty(type=MCH_PG_MechRidge)
    bpy.types.Object.mch_mridge = bpy.props.PointerProperty(type=MCH_PG_MechRidge)


def unregister():
    for n, t in (('mch_mridge', bpy.types.Object), ('mch_mridge', bpy.types.Scene)):
        try:
            delattr(t, n)
        except AttributeError:
            pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
