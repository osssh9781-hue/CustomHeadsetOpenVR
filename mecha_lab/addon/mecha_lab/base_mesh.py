"""Base Mesh from Shape: create a NEW closed solid from a drawn screen outline.

This is a generator, not a cut and not a mask extract: the scene is never
modified except for the new object.  Outline -> plane -> profile:

* The outline is projected through the view onto a plane perpendicular to the
  view, placed at the surface under the shape (if any) or at the 3D cursor.
  The object's local XY is that plane and local +Z points toward the viewer,
  so the silhouette seen from the drawing view is exactly the drawn outline.
* FLAT     straight walls, flat top.
* CHAMFER  flat solid + one-segment bevel on the TOP rim only.
* BEVEL    flat solid + rounded (N-segment) bevel on the TOP rim only.
* DOME     the whole top surface bulges: height = Edge Height + Height *
           f(d / R), where d is the distance to the outline (holes included)
           and R the largest such distance.  The top is a constrained Delaunay
           triangulation of the densified outline plus interior grid points,
           so concave outlines never produce the flipped faces of a
           centre-fan.  This is a real height field, not a bevel.
* PUFF     0.24.20 an inflated lump: the same point set, a height field on BOTH sides meeting at the outline
           (no wall), every cross-section round - a thin part (arm) gets a thin tube, a wide part a fat one:
           height = Puff * sqrt(2 w d - d^2), d = distance to the outline, w = the local half width (the
           distance at the nearest ridge point of the distance field).

The outline and settings are stored on the object (``Object.mch_base``), so
changing the profile / height / resolution later rebuilds the mesh (Live).
"""
from __future__ import annotations

import json
import math

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from mathutils import Matrix, Vector
from mathutils.geometry import delaunay_2d_cdt

from . import core_geometry as cg

PROFILES = (
    ('FLAT', 'Flat', 'Flat top and straight side walls', 'profile_flat', 'MESH_PLANE'),
    ('CHAMFER', 'Chamfer', 'Straight angled cut along the top border', 'profile_chamfer', 'MOD_BEVEL'),
    ('BEVEL', 'Bevel', 'Rounded top border only (width / segments)', 'profile_bevel', 'MOD_SUBSURF'),
    ('DOME', 'Rounded / Dome', 'The whole top bulges smoothly from the border inward '
     '(height field, not a bevel)', 'profile_dome', 'MESH_UVSPHERE'),
    ('PUFF', 'Puff', 'Inflated lump: round on both sides, every part as thick as it is wide '
     '(arm-like outlines become tubes) - a sculpting base', 'profile_puff', 'META_BALL'),
)
PROFILE_ITEMS = [(p[0], p[1], p[2], p[4], i) for i, p in enumerate(PROFILES)]
SIDE_ITEMS = [
    ('TOP', 'Top Only', 'Bevel / Chamfer on the top rim; bottom flat and sharp', 'TRIA_UP', 0),
    ('BOTTOM', 'Bottom Only', 'Bevel / Chamfer on the bottom rim; top flat and sharp', 'TRIA_DOWN', 1),
    ('BOTH', 'Both Sides', 'Top and bottom rims (separate width / segments possible)', 'ARROW_LEFTRIGHT', 2),
    ('NONE', 'None', 'No bevel: flat and sharp', 'X', 3),
]
FLIP_SIDES = {'TOP': 'BOTTOM', 'BOTTOM': 'TOP', 'BOTH': 'BOTH', 'NONE': 'NONE'}
SETTING_KEYS = ('height', 'wall', 'bevel_width', 'bevel_segments', 'roundness', 'resolution', 'offset',
                'bottom_too', 'bevel_sides', 'bevel_width_bottom', 'bevel_segments_bottom', 'bevel_link', 'puff')
MAX_DOME_POINTS = 12000


CARRY_KEYS = ('profile', 'height', 'wall', 'bevel_width', 'bevel_segments', 'roundness', 'resolution', 'offset',
              'bevel_sides', 'bevel_width_bottom', 'bevel_segments_bottom', 'bevel_link', 'puff')


def _rebuild_update(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and self.live and self.outline:
        try:
            rebuild(ob)
            self.last_error = ''
        except (cg.CutError, ValueError, RuntimeError) as ex:
            self.last_error = str(ex)
        # 0.24.5 what you set on the live shape is used for the next one too (it reset to the old defaults)
        st = getattr(getattr(context, 'scene', None), 'mch_base', None)
        if st is not None:
            for k in CARRY_KEYS:
                try:
                    if getattr(st, k) != getattr(self, k):
                        setattr(st, k, getattr(self, k))
                except (AttributeError, TypeError):
                    pass


class MCH_PG_BaseMesh(bpy.types.PropertyGroup):
    """Scene.mch_base = defaults for new shapes; Object.mch_base = live settings."""
    profile: EnumProperty(name='Profile', items=PROFILE_ITEMS, default='FLAT', update=_rebuild_update)
    height: FloatProperty(name='Height', default=0.2, min=0.0001, soft_max=10.0, precision=4,
                          unit='LENGTH', update=_rebuild_update,
                          description='Flat/Chamfer/Bevel: total thickness. Dome: bulge above the edge height')
    wall: FloatProperty(name='Edge Height', default=0.03, min=0.0, soft_max=5.0, precision=4,
                        unit='LENGTH', update=_rebuild_update,
                        description='Dome: straight side wall below the bulge (minimum 1% of Height)')
    bevel_width: FloatProperty(name='Border Width', default=0.05, min=0.0, soft_max=2.0, precision=4,
                               unit='LENGTH', update=_rebuild_update)
    bevel_segments: IntProperty(name='Segments', default=4, min=1, max=32, update=_rebuild_update)
    roundness: FloatProperty(name='Roundness', default=0.34, min=0.0, max=1.0, update=_rebuild_update,
                             description='Dome profile: 0 = straight roof, ~0.33 = circular, 1 = full / boxy')
    resolution: IntProperty(name='Resolution', default=28, min=4, max=128, update=_rebuild_update,
                            description='Dome / Puff samples across the shape (higher = smoother, heavier)')
    puff: FloatProperty(name='Puff', default=1.0, min=0.05, soft_max=2.5, update=_rebuild_update,
                        description='Puff: thickness against width - 1 = round cross-sections, '
                                    '0.5 = flattened, 2 = taller than wide')
    offset: FloatProperty(name='Offset', default=0.0, soft_min=-5.0, soft_max=5.0, precision=4,
                          unit='LENGTH', update=_rebuild_update,
                          description='Move the solid along its normal (toward the viewer is positive)')
    bottom_too: BoolProperty(name='Bevel Bottom Too (old)', default=False, update=_rebuild_update,
                             description='v0.8-0.9 option, migrated to Bevel Sides = Both')
    bevel_sides: EnumProperty(name='Bevel Sides', items=SIDE_ITEMS, default='TOP', update=_rebuild_update,
                              description='Where the Bevel / Chamfer profile goes (Alt + draw cutter flips Top/Bottom)')
    bevel_width_bottom: FloatProperty(name='Bottom Width', default=0.05, min=0.0, soft_max=2.0, precision=4,
                                      unit='LENGTH', update=_rebuild_update)
    bevel_segments_bottom: IntProperty(name='Bottom Segments', default=4, min=1, max=32, update=_rebuild_update)
    bevel_link: BoolProperty(name='Same Top / Bottom', default=True, update=_rebuild_update,
                             description='Both Sides: bottom uses the top Width / Segments')
    sketch: BoolProperty(name='Sketch First', default=True,
                         description='Draw = add to an orange sketch, Alt+draw = subtract from it; '
                                     'Enter makes the mesh (Alt+Enter cuts it into the mesh below). '
                                     'Off: every outline becomes a mesh at once (Alt+draw = cutter)')
    surface_align: BoolProperty(name='Stick to Surface', default=True,
                                description='Drawn over a mesh: the new solid sits ON that surface (turned to the '
                                            'surface normal, its bottom sunk just enough to leave no gap). '
                                            'Off: the solid faces the view (old behaviour)')
    embed: FloatProperty(name='Sink Into Surface', default=0.0, min=0.0, soft_max=1.0, precision=4,
                         unit='LENGTH', update=_rebuild_update,
                         description='How far the bottom reaches into the surface it was drawn on '
                                     '(set automatically so a curved surface leaves no gap)')
    live: BoolProperty(name='Live', default=False,
                       description='Settings rebuild this object (outline stored on the object)')
    outline: StringProperty(default='', options={'HIDDEN'})
    last_error: StringProperty(default='', options={'HIDDEN', 'SKIP_SAVE'})


# -----------------------------------------------------------------------------
# 2D helpers
# -----------------------------------------------------------------------------


def _densify(loop, spacing):
    out = []
    n = len(loop)
    for i in range(n):
        a, b = loop[i], loop[(i + 1) % n]
        steps = max(1, int(math.ceil(math.dist(a, b) / spacing))) if spacing > 0 else 1
        for k in range(steps):
            t = k / steps
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def _distances(points, loops):
    """Distance of each point to the nearest outline segment (numpy if present)."""
    segs = [(lp[i], lp[(i + 1) % len(lp)]) for lp in loops for i in range(len(lp))]
    try:
        import numpy as np
        P = np.asarray(points, dtype=np.float64)
        A = np.asarray([s[0] for s in segs], dtype=np.float64)
        B = np.asarray([s[1] for s in segs], dtype=np.float64)
        AB = B - A
        L2 = np.maximum((AB * AB).sum(1), 1e-18)
        out = np.empty(len(P))
        for start in range(0, len(P), 2048):
            p = P[start:start + 2048, None, :]
            t = np.clip(((p - A) * AB).sum(2) / L2, 0.0, 1.0)
            d = p - (A + t[..., None] * AB)
            out[start:start + 2048] = np.sqrt((d * d).sum(2)).min(1)
        return out.tolist()
    except ImportError:   # pragma: no cover
        res = []
        for p in points:
            best = 1e30
            for a, b in segs:
                dx, dy = b[0] - a[0], b[1] - a[1]
                ll = dx * dx + dy * dy
                t = 0.0 if ll < 1e-18 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / ll))
                best = min(best, math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy))
            res.append(best)
        return res


def dome_profile(t, roundness):
    """0 at the border, 1 at the deepest interior point; superellipse family."""
    t = max(0.0, min(1.0, t))
    q = 1.0 + 3.0 * max(0.0, min(1.0, roundness))
    return (1.0 - (1.0 - t) ** q) ** (1.0 / q)


def _triangulate(points, n_boundary, loops_for_test, edges):
    """Constrained Delaunay; keep the triangles inside the outline.

    Triangles are grouped into regions separated by the constraint (outline)
    edges; each region is classified once by its largest triangle.  A per-
    triangle centroid test is unreliable for slivers along nearly collinear
    outline points (seen in oblique views).
    """
    res = delaunay_2d_cdt([Vector(p) for p in points], edges, [], 0, 1e-9, True)
    out_verts, out_edges, faces, orig_verts, orig_edges = res[0], res[1], res[2], res[3], res[4]
    mapping = []
    for orig in orig_verts:
        if not orig:
            raise cg.CutError('Outline intersects itself or touches a hole; redraw it.')
        mapping.append(orig[0])
    n_in = len(edges)
    constraint = set()
    for (a, b), orig in zip(out_edges, orig_edges):
        if any(o < n_in for o in orig):
            constraint.add((min(a, b), max(a, b)))
    edge_faces = {}
    for fi, f in enumerate(faces):
        for k in range(len(f)):
            key = (min(f[k], f[(k + 1) % len(f)]), max(f[k], f[(k + 1) % len(f)]))
            edge_faces.setdefault(key, []).append(fi)
    # Flood regions bounded by outline edges, then classify them by crossing
    # parity from the outside (beyond the convex hull): inside = odd number
    # of outline edges crossed.  Exact for holes and islands; no centroid
    # tests on slivers.
    region = [-1] * len(faces)
    n_regions = 0
    for seed in range(len(faces)):
        if region[seed] != -1:
            continue
        stack = [seed]
        region[seed] = n_regions
        while stack:
            fi = stack.pop()
            f = faces[fi]
            for k in range(len(f)):
                key = (min(f[k], f[(k + 1) % len(f)]), max(f[k], f[(k + 1) % len(f)]))
                if key in constraint:
                    continue
                for nb in edge_faces.get(key, ()):
                    if region[nb] == -1:
                        region[nb] = n_regions
                        stack.append(nb)
        n_regions += 1
    OUT = n_regions                      # virtual region beyond the hull
    links = {}
    for key, fl in edge_faces.items():
        regs = [region[fi] for fi in fl] + ([OUT] if len(fl) == 1 else [])
        if len(regs) != 2 or regs[0] == regs[1]:
            continue
        w = 1 if key in constraint else 0
        links.setdefault(regs[0], set()).add((regs[1], w))
        links.setdefault(regs[1], set()).add((regs[0], w))
    parity = {OUT: 0}
    queue = [OUT]
    while queue:
        r = queue.pop()
        for other, w in links.get(r, ()):
            if other not in parity:
                parity[other] = parity[r] ^ w
                queue.append(other)
    keep = []
    for fi in range(len(faces)):
        par = parity.get(region[fi])
        if par is None:      # disconnected (should not happen): fall back to a point test
            f = faces[fi]
            cx = sum(out_verts[i].x for i in f) / len(f)
            cy = sum(out_verts[i].y for i in f) / len(f)
            par = 1 if cg.point_in_loops((cx, cy), loops_for_test) else 0
        if par == 1:
            keep.append(fi)
    tris = []
    for fi in keep:
        idx = [mapping[i] for i in faces[fi]]
        if len(set(idx)) == len(idx):
            tris.append(idx)
    if not tris:
        raise cg.CutError('Outline could not be triangulated.')
    return tris


# -----------------------------------------------------------------------------
# Solid builders (local plane space: outline in XY, +Z = up)
# -----------------------------------------------------------------------------


def _orient_ccw(tri, pts):
    a, b, c = (pts[i] for i in tri)
    area = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return tri if area > 0 else [tri[0], tri[2], tri[1]]


def _add_prism(bm, outer, holes, height):
    loops = [outer] + list(holes)
    flat = [p for lp in loops for p in lp]
    bottom = [bm.verts.new((x, y, 0.0)) for x, y in flat]
    top = [bm.verts.new((x, y, height)) for x, y in flat]
    if not holes:
        bm.faces.new([bottom[i] for i in reversed(range(len(outer)))])
        bm.faces.new(top[:len(outer)])
    else:
        edges = []
        off = 0
        for lp in loops:
            n = len(lp)
            edges += [(off + i, off + (i + 1) % n) for i in range(n)]
            off += n
        for tri in _triangulate(flat, len(flat), loops, edges):
            tri = _orient_ccw(tri, flat)
            bm.faces.new([top[i] for i in tri])
            bm.faces.new([bottom[i] for i in reversed(tri)])
    rim_top, rim_bottom = [], []
    off = 0
    for lp in loops:
        n = len(lp)
        for i in range(n):
            a, b = off + i, off + (i + 1) % n
            bm.faces.new((bottom[a], bottom[b], top[b], top[a]))
            rim_top.append((top[a], top[b]))
            rim_bottom.append((bottom[a], bottom[b]))
        off += n
    return rim_top, rim_bottom


def _dome_points(outer, holes, p, rings=()):
    """(dense loops, boundary points, interior points, distance of every point, spacing) for Dome / Puff.
    ``rings`` (fractions of the spacing): rows of points that far inside the outline (Puff: an even round rim)."""
    loops = [outer] + list(holes)
    xs = [q[0] for lp in loops for q in lp]
    ys = [q[1] for lp in loops for q in lp]
    extent = max(max(xs) - min(xs), max(ys) - min(ys))
    if extent <= 1e-9:
        raise cg.CutError('Outline has no size.')
    spacing = extent / max(4, p.resolution)
    dense = [cg.dedupe_loop(_densify(lp, spacing), spacing * 1e-3) for lp in loops]
    boundary = [q for lp in dense for q in lp]
    interior = []
    nx = int(math.ceil((max(xs) - min(xs)) / spacing))
    ny = int(math.ceil((max(ys) - min(ys)) / spacing))
    if nx * ny > MAX_DOME_POINTS * 2:
        raise cg.CutError('Dome resolution too high for this outline; lower Resolution.')
    cand = []
    for i in range(nx + 1):
        for j in range(ny + 1):
            q = (min(xs) + i * spacing + (0.5 * spacing if j % 2 else 0.0), min(ys) + j * spacing)
            if cg.point_in_loops(q, dense):
                cand.append(q)
    if cand:
        dist = _distances(cand, dense)
        keep = (max(rings) + 0.4) * spacing if rings else 0.45 * spacing
        interior = [q for q, d in zip(cand, dist) if d > keep]
    for r in rings:
        ring = []
        for lp in dense:
            n = len(lp)
            for i in range(n):
                a, b, c = lp[i - 1], lp[i], lp[(i + 1) % n]
                # left of the walking direction is inside (outer CCW, holes CW)
                nx_, ny_ = -(c[1] - a[1]), c[0] - a[0]
                ln = math.hypot(nx_, ny_)
                if ln < 1e-12:
                    continue
                ring.append((b[0] + nx_ / ln * r * spacing, b[1] + ny_ / ln * r * spacing))
        ring = [q for q in ring if cg.point_in_loops(q, dense)]
        if ring:
            dist = _distances(ring, dense)
            interior += [q for q, d in zip(ring, dist) if 0.6 * r * spacing < d < 1.4 * r * spacing]
    if len(interior) > MAX_DOME_POINTS:
        raise cg.CutError('Dome resolution too high for this outline; lower Resolution.')
    d_all = [0.0] * len(boundary) + (_distances(interior, dense) if interior else [])
    return dense, boundary, interior, d_all, spacing


def _loop_edges(dense):
    edges = []
    off = 0
    for lp in dense:
        n = len(lp)
        edges += [(off + i, off + (i + 1) % n) for i in range(n)]
        off += n
    return edges


def _add_dome(bm, outer, holes, p):
    dense, boundary, interior, d_all, spacing = _dome_points(outer, holes, p)
    pts = boundary + interior
    radius = max(max(d_all), spacing)
    nb = len(boundary)
    edges = _loop_edges(dense)
    # A zero edge height would make border-only top triangles coincide with the
    # bottom cap; keep a minimal wall (1% of the height) so the solid stays valid.
    wall = max(p.wall, p.height * 0.01, 1e-5)
    top = [bm.verts.new((x, y, wall + p.height * dome_profile(d / radius, p.roundness)))
           for (x, y), d in zip(pts, d_all)]
    bottom = [bm.verts.new((x, y, 0.0)) for x, y in boundary]
    top_faces = []
    for tri in _triangulate(pts, nb, dense, edges):
        tri = _orient_ccw(tri, pts)
        top_faces.append(bm.faces.new([top[i] for i in tri]))
    for tri in _triangulate(boundary, nb, dense, edges):
        tri = _orient_ccw(tri, boundary)
        bm.faces.new([bottom[i] for i in reversed(tri)])
    off = 0
    for lp in dense:
        n = len(lp)
        for i in range(n):
            a, b = off + i, off + (i + 1) % n
            bm.faces.new((bottom[a], bottom[b], top[b], top[a]))
        off += n
    for f in top_faces:
        f.smooth = True


def puff_heights(pts, d_all, nb, spacing, puff=1.0):
    """0.24.20 heights of an inflated lump: round cross-sections everywhere.  ``w`` (local half width) =
    the distance at the nearest ridge point (a point whose distance is not beaten by its neighbours), so an
    arm-like part gets its own radius, not the body's.  Boundary points (the first ``nb``) stay 0."""
    from mathutils.kdtree import KDTree
    n = len(pts)
    if n <= nb:
        return [0.0] * n
    kd = KDTree(n)
    for i, (x, y) in enumerate(pts):
        kd.insert((x, y, 0.0), i)
    kd.balance()
    reach, tol = 1.6 * spacing, 0.05 * spacing
    ridge = [i for i in range(nb, n)
             if d_all[i] + tol >= max(d_all[j] for _co, j, _dd in kd.find_range((*pts[i], 0.0), reach))]
    kr = KDTree(len(ridge))
    for k, i in enumerate(ridge):
        kr.insert((*pts[i], 0.0), k)
    kr.balance()
    out = [0.0] * n
    for i in range(nb, n):
        d = d_all[i]
        _co, k, _dd = kr.find((*pts[i], 0.0))
        w = max(d_all[ridge[k]], d, 1e-9)
        out[i] = puff * math.sqrt(max(0.0, 2.0 * w * d - d * d))
    return out


def _add_puff(bm, outer, holes, p):
    dense, boundary, interior, d_all, spacing = _dome_points(outer, holes, p, rings=(0.3, 0.8))
    pts = boundary + interior
    nb = len(boundary)
    edges = _loop_edges(dense)
    tris = [list(_orient_ccw(t, pts)) for t in _triangulate(pts, nb, dense, edges)]
    # an edge across the shape between two outline points (narrow spots) would be shared by the top AND the
    # bottom: split it at its middle (a new inside point)
    outline = {(min(e), max(e)) for e in edges}
    chords = {}
    for t in tris:
        for k in range(3):
            e = (min(t[k], t[(k + 1) % 3]), max(t[k], t[(k + 1) % 3]))
            if e[1] < nb and e not in outline and e not in chords:
                chords[e] = len(pts) + len(chords)
    if chords:
        extra = [None] * len(chords)
        for (i, j), m in chords.items():
            extra[m - len(pts)] = ((pts[i][0] + pts[j][0]) / 2.0, (pts[i][1] + pts[j][1]) / 2.0)
        split = True
        while split:                       # a triangle can carry up to three chords
            split = False
            out = []
            for t in tris:
                for k in range(3):
                    a, b, c = t[k], t[(k + 1) % 3], t[(k + 2) % 3]
                    m = chords.get((min(a, b), max(a, b)))
                    if m is not None:
                        out += [[a, m, c], [m, b, c]]
                        split = True
                        break
                else:
                    out.append(t)
            tris = out
        pts = pts + extra
        d_all = list(d_all) + _distances(extra, dense)
    if len(pts) == nb:
        raise cg.CutError('Outline too small for Puff; draw it bigger or raise Resolution.')
    h = puff_heights(pts, d_all, nb, spacing, getattr(p, 'puff', 1.0))
    # two light smoothing passes (the ridge search works on a grid: no steps)
    nbrs = [set() for _ in pts]
    for a, b, c in tris:
        nbrs[a] |= {b, c}
        nbrs[b] |= {a, c}
        nbrs[c] |= {a, b}
    inner_nb = [[j for j in nbrs[i] if j >= nb] for i in range(len(pts))]   # outline zeros would flatten tubes
    for _ in range(2):
        h = [0.0 if i < nb or not inner_nb[i] else 0.5 * h[i] + 0.5 * sum(h[j] for j in inner_nb[i]) / len(inner_nb[i])
             for i in range(len(pts))]
    floor = spacing * 0.02          # top and bottom never meet inside (they would be merged as doubles)
    h = [hh if i < nb else max(hh, floor) for i, hh in enumerate(h)]
    rim = [bm.verts.new((x, y, 0.0)) for x, y in boundary]
    inner = pts[nb:]
    top = rim + [bm.verts.new((x, y, hh)) for (x, y), hh in zip(inner, h[nb:])]
    bottom = rim + [bm.verts.new((x, y, -hh)) for (x, y), hh in zip(inner, h[nb:])]
    for tri in tris:
        bm.faces.new([top[i] for i in tri]).smooth = True
        bm.faces.new([bottom[i] for i in reversed(tri)]).smooth = True


def side_values(p, flip=False):
    """(sides, top (width, segments), bottom (width, segments)).  ``flip`` =
    Alt cutter: Top<->Bottom, Both swaps the two settings, None unchanged."""
    sides = getattr(p, 'bevel_sides', 'TOP')
    top = (p.bevel_width, p.bevel_segments)
    bottom = top if getattr(p, 'bevel_link', True) else (p.bevel_width_bottom, p.bevel_segments_bottom)
    if flip:
        sides = FLIP_SIDES[sides]
        if sides == 'BOTH':
            top, bottom = bottom, top
    return sides, top, bottom


LAST_NOTES = []


def _bevel_rims(bm, p, rim_top, rim_bottom, flip=False):
    sides, top, bottom = side_values(p, flip)
    jobs = []
    if sides in {'TOP', 'BOTH'}:
        jobs.append(('top', rim_top, top))
    if sides in {'BOTTOM', 'BOTH'}:
        jobs.append(('bottom', rim_bottom, bottom))
    notes = []
    both = len(jobs) == 2
    for name, pairs, (width, segs) in jobs:
        limit = p.height * (0.48 if both else 0.95)     # rims never meet / pass the other side
        if width > limit:
            notes.append(f'{name} width limited to {limit:.4g} by the height')
            width = limit
        if width <= 0:
            continue
        edges = []
        for a, b in pairs:
            if a.is_valid and b.is_valid:
                e = bm.edges.get((a, b))
                if e is not None:
                    edges.append(e)
        if edges:
            verts = list({v for e in edges for v in e.verts})
            bmesh.ops.bevel(bm, geom=edges + verts, offset=width, offset_type='OFFSET',
                            segments=1 if p.profile == 'CHAMFER' else max(1, segs),
                            profile=0.5, affect='EDGES', clamp_overlap=True)
    return notes


def _region_ok(faces, up):
    for f in faces:
        if not f.is_valid or f.calc_area() <= 1e-12:
            return False
        f.normal_update()
        if (f.normal.z <= 0.0) if up else (f.normal.z >= 0.0):
            return False
    return True


def _profile_one(bm, faces, width, drop, segs, round_, up):
    """0.23.17 Bevel / Chamfer by insets: the rim drops by ``drop`` and the profile runs ``width`` across the
    flat side (the old bevel could not be wider than the thickness).  Returns False if the insets overlap."""
    if not faces:
        return True
    sign = 1.0 if up else -1.0
    verts = list({v for f in faces for v in f.verts})
    bmesh.ops.translate(bm, verts=verts, vec=(0.0, 0.0, -sign * drop))     # the outer rim goes down first
    n = 1 if not round_ else max(1, segs)
    xs, zs = [0.0], [0.0]
    for j in range(1, n + 1):
        if round_:
            phi = 0.5 * math.pi * j / n
            xs.append(width * (1.0 - math.cos(phi)))
            zs.append(drop * math.sin(phi))
        else:
            xs.append(width)
            zs.append(drop)
    region = list(faces)
    x0 = min(v.co.x for v in verts)
    x1 = max(v.co.x for v in verts)
    y0 = min(v.co.y for v in verts)
    y1 = max(v.co.y for v in verts)
    tol = 1e-6 * max(x1 - x0, y1 - y0, 1e-9)
    area = sum(f.calc_area() for f in region)
    for j in range(1, n + 1):
        dx, dz = xs[j] - xs[j - 1], zs[j] - zs[j - 1]
        if dx <= 1e-9 and dz <= 1e-9:
            continue
        res = bmesh.ops.inset_region(bm, faces=region, thickness=dx, depth=dz, use_even_offset=True,
                                     use_boundary=True, use_relative_offset=False)
        if not _region_ok(region, up):
            return False
        # an inset wider than the shape folds over itself: the slope faces flip or points leave the outline
        for f in res.get('faces', []):
            f.normal_update()
            if f.calc_area() > 1e-12 and ((f.normal.z <= 0.0) if up else (f.normal.z >= 0.0)):
                return False
        for f in region:
            for v in f.verts:
                if not (x0 - tol <= v.co.x <= x1 + tol and y0 - tol <= v.co.y <= y1 + tol):
                    return False
        new_area = sum(f.calc_area() for f in region)
        if dx > 1e-9 and new_area >= area:
            return False
        area = new_area
    return True


def _profile_rims(bm, p, flip=False):
    """Bevel / Chamfer on the top and / or bottom of a prism.  Returns (bmesh, notes) - the bmesh may be a
    new one (the given one is freed then)."""
    sides, top, bottom = side_values(p, flip)
    jobs = []
    if sides in {'TOP', 'BOTH'}:
        jobs.append(('top', True, top))
    if sides in {'BOTTOM', 'BOTH'}:
        jobs.append(('bottom', False, bottom))
    notes = []
    h = p.height
    eps = max(h * 1e-4, 1e-7)
    for name, up, (width, segs) in jobs:
        if width <= 0:
            continue
        limit = h * (0.48 if len(jobs) == 2 else 0.95)       # the drop never reaches the other side
        w = width
        for _try in range(8):
            trial = bm.copy()
            zf = h if up else 0.0
            faces = [f for f in trial.faces if all(abs(v.co.z - zf) <= eps for v in f.verts)]
            ok = _profile_one(trial, faces, w, min(w, limit), segs, p.profile == 'BEVEL', up)
            if ok:
                bm.free()
                bm = trial
                break
            trial.free()
            w *= 0.7
        else:
            notes.append(f'{name}: no room for a bevel on this shape')
            continue
        if w < width - 1e-9:
            notes.append(f'{name} width limited to {w:.4g} by the shape')
    return bm, notes


def build_bmesh(groups, p, flip=False):
    """groups: [(outer CCW, [holes CW])] in local plane units. Returns a validated BMesh."""
    bm = bmesh.new()
    try:
        rim_top, rim_bottom = [], []
        for outer, holes in groups:
            if p.profile == 'DOME':
                _add_dome(bm, outer, holes, p)
            elif p.profile == 'PUFF':
                _add_puff(bm, outer, holes, p)
            else:
                rt, rb = _add_prism(bm, outer, holes, p.height)
                rim_top += rt
                rim_bottom += rb
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-7)
        LAST_NOTES.clear()
        if p.profile in {'BEVEL', 'CHAMFER'}:
            bm, notes = _profile_rims(bm, p, flip)
            LAST_NOTES.extend(notes)
        embed = getattr(p, 'embed', 0.0) if p.profile != 'PUFF' else 0.0   # Puff: centred on the plane
        if embed > 0:
            # Stick to Surface: the bottom reaches into the surface (no gap on curves)
            for v in bm.verts:
                if v.co.z <= 1e-7:
                    v.co.z -= embed
        if abs(p.offset) > 0:
            bmesh.ops.translate(bm, verts=bm.verts[:], vec=(0.0, 0.0, p.offset))
        if not bm.faces or any(not e.is_manifold for e in bm.edges):
            raise cg.CutError('Generated solid is not closed (outline too thin or touching itself).')
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        if bm.calc_volume(signed=True) < 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        if bm.calc_volume() <= 1e-12:
            raise cg.CutError('Generated solid has no volume.')
        return bm
    except Exception:
        bm.free()
        raise


def _groups_from_json(text):
    data = json.loads(text)
    return [([tuple(q) for q in g['outer']], [[tuple(q) for q in h] for h in g['holes']])
            for g in data['groups']]


def rebuild(ob):
    """Regenerate a live Base Mesh object from its stored outline + settings."""
    groups = _groups_from_json(ob.mch_base.outline)
    bm = build_bmesh(groups, ob.mch_base)
    try:
        bm.to_mesh(ob.data)
    finally:
        bm.free()
    ob.data.update()
    ob['mch_base_notes'] = '; '.join(LAST_NOTES)      # 0.23.17 shown in the LIVE panel (e.g. width limited)


# -----------------------------------------------------------------------------
# Screen outline -> plane
# -----------------------------------------------------------------------------


def _plane_point(projector, xy, plane_co, normal):
    o, d = projector.ray(xy)
    return cg._plane_hit(o, d, plane_co, normal)[0]


def plane_frame(context, projector, groups):
    """(origin, X, Y, N) for the outline plane; N points toward the viewer."""
    vd = projector.view_dir
    outer = groups[0][0]
    c = (sum(q[0] for q in outer) / len(outer), sum(q[1] for q in outer) / len(outer))
    origin = None
    try:
        o, d = projector.ray(c)
        dg = context.evaluated_depsgraph_get()
        hit, loc, _n, _i, ob, _m = context.scene.ray_cast(dg, o, d)
        if hit and ob is not None and ob.type == 'MESH':
            origin = loc
    except (AttributeError, RuntimeError, TypeError):
        origin = None
    if origin is None:
        origin = _plane_point(projector, c, context.scene.cursor.location.copy(), vd)
    else:
        origin = _plane_point(projector, c, origin, vd)
    n = -vd
    px = _plane_point(projector, (c[0] + 100.0, c[1]), origin, vd)
    x = px - origin
    x = (x - n * x.dot(n))
    if x.length < 1e-12:
        raise cg.CutError('Cannot place the outline plane in this view.')
    x.normalize()
    y = n.cross(x).normalized()
    return origin, x, y, n


def _outline_samples(outer, count=24):
    step = max(1, len(outer) // count)
    return [outer[i] for i in range(0, len(outer), step)]


def surface_frame(context, projector, screen_groups, height=0.2):
    """0.14.2+ Stick to Surface: (origin, X, Y, N, embed) for an outline drawn
    over a mesh, or None (nothing under it / seen edge-on).

    N = the average surface normal under the outline (turned toward the
    viewer), origin = the surface point under the outline centre, embed = how
    far the bottom must reach below that plane so a curved surface leaves no
    gap (at least 2 % of the height, so the bottom never z-fights with a flat
    surface)."""
    outer = screen_groups[0][0]
    c = (sum(q[0] for q in outer) / len(outer), sum(q[1] for q in outer) / len(outer))
    try:
        dg = context.evaluated_depsgraph_get()
        o, d = projector.ray(c)
        hit, loc, nrm, _i, ob, _m = context.scene.ray_cast(dg, o, d)
    except (AttributeError, RuntimeError, TypeError):
        return None
    if not hit or ob is None or ob.type != 'MESH':
        return None
    name = ob.name
    hits = [(Vector(loc), Vector(nrm))]
    for q in _outline_samples(outer):
        o2, d2 = projector.ray(q)
        h2, l2, n2, _i2, ob2, _m2 = context.scene.ray_cast(dg, o2, d2)
        if h2 and ob2 is not None and ob2.name == name:
            hits.append((Vector(l2), Vector(n2)))
    n = Vector((0.0, 0.0, 0.0))
    for _p, nv in hits:
        n += nv if nv.dot(-d) >= 0 else -nv
    if n.length < 1e-9:
        return None
    n.normalize()
    if abs(n.dot(projector.view_dir)) < 0.2:
        return None                      # seen almost edge-on: drawing onto it would smear
    origin = Vector(loc)
    below = min((pt - origin).dot(n) for pt, _nv in hits)
    embed = max(0.0, -below) + max(height * 0.02, 1e-5)
    px = _plane_point(projector, (c[0] + 100.0, c[1]), origin, n)
    x = px - origin
    x = x - n * x.dot(n)
    if x.length < 1e-12:
        return None
    x.normalize()
    y = n.cross(x).normalized()
    return origin, x, y, n, embed


SESSION_KEY = 'mch_base_session'     # Scene ID prop: live Base Meshes made since the tool was entered


def frame_for(context, projector, screen_groups):
    """(origin, X, Y, N, embed): on the surface under the outline when Stick
    to Surface is on and there is one, else facing the view (embed 0)."""
    p = context.scene.mch_base
    sf = surface_frame(context, projector, screen_groups, p.height) if getattr(p, 'surface_align', False) else None
    if sf is not None:
        return sf
    return (*plane_frame(context, projector, screen_groups), 0.0)


def _local_groups(context, loops, projector):
    screen_groups = cg.prepare_loops(loops)
    origin, x, y, n, embed = frame_for(context, projector, screen_groups)

    def to_local(q):
        w = _plane_point(projector, q, origin, n)
        v = w - origin
        return (v.dot(x), v.dot(y))
    groups = [([to_local(q) for q in outer], [[to_local(q) for q in h] for h in holes])
              for outer, holes in screen_groups]
    groups = cg.organize_loops([lp for outer, holes in groups for lp in [outer] + holes])
    frame = Matrix.Identity(4)
    for r in range(3):
        frame[r][0], frame[r][1], frame[r][2], frame[r][3] = x[r], y[r], n[r], origin[r]
    return groups, frame, screen_groups, embed


def perform_base(context, loops, projector, cutter=False, targets=None):
    """Create the new solid (or, ``cutter=True`` = Alt, cut it into the
    mesh below).  Returns a report string; raises CutError (scene untouched)."""
    if cutter:
        return cut_like_cut_tool(context, loops, projector, targets)
    groups, frame, screen_groups, embed = _local_groups(context, loops, projector)
    defaults = context.scene.mch_base
    return _create_live_base(context, groups, frame, defaults, embed)


class _WithEmbed:
    """Settings view: ``defaults`` with this shape's own embed."""

    def __init__(self, base, embed):
        self._base = base
        self.embed = embed

    def __getattr__(self, name):
        return getattr(self._base, name)


def _create_live_base(context, groups, frame, defaults, embed=0.0):
    """New live Base Mesh object from plane-local ``groups`` at ``frame``."""
    bm = build_bmesh(groups, _WithEmbed(defaults, embed))
    me = bpy.data.meshes.new('MCH_BaseMesh')
    try:
        bm.to_mesh(me)
    finally:
        bm.free()
    ob = bpy.data.objects.new('MCH_Base', me)
    coll = context.collection if context.collection is not None else context.scene.collection
    try:
        coll.objects.link(ob)
    except RuntimeError:
        context.scene.collection.objects.link(ob)
    ob.matrix_world = frame
    live = ob.mch_base
    for key in SETTING_KEYS:
        setattr(live, key, getattr(defaults, key))
    live.profile = defaults.profile        # live is still False: no rebuild yet
    live.embed = embed
    live.outline = json.dumps({'groups': [{'outer': g[0], 'holes': g[1]} for g in groups]})
    live.live = True
    session = list(context.scene.get(SESSION_KEY, []))
    session.append(ob.name)
    context.scene[SESSION_KEY] = session
    _arm_tab_watch(context)
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    name = dict((p[0], p[1]) for p in PROFILES)[defaults.profile]
    notes = (' | ' + '; '.join(LAST_NOTES)) if LAST_NOTES else ''
    return f'Base Mesh created: {ob.name} ({name}, {len(me.vertices)} verts, closed solid){notes}'


def _cutter_targets(context, projector, screen_groups, targets):
    if targets:
        return [t for t in targets if t.type == 'MESH']
    sel = [o for o in context.selected_objects if o.type == 'MESH' and not
           (getattr(o, 'mch_base', None) and o.mch_base.live)]
    if sel:
        return sel
    outer = screen_groups[0][0]
    c = (sum(q[0] for q in outer) / len(outer), sum(q[1] for q in outer) / len(outer))
    o, d = projector.ray(c)
    hit, _loc, _n, _i, ob, _m = context.scene.ray_cast(context.evaluated_depsgraph_get(), o, d)
    return [bpy.data.objects[ob.name]] if hit and ob is not None and ob.type == 'MESH' else []


def _sketch_cutter_targets(context, groups, frame):
    """Selected meshes, else the mesh under the sketch (ray from in front of
    the plane, against its normal)."""
    sel = [o for o in context.selected_objects if o.type == 'MESH' and not
           (getattr(o, 'mch_base', None) and o.mch_base.live)]
    if sel:
        return sel
    dg = context.evaluated_depsgraph_get()
    n = frame.col[2].to_3d().normalized()
    found = []
    for outer, _holes in groups:
        cx = sum(q[0] for q in outer) / len(outer)
        cy = sum(q[1] for q in outer) / len(outer)
        start = frame @ Vector((cx, cy, 0.0)) + n * 1000.0
        hit, _loc, _n, _i, ob, _m = context.scene.ray_cast(dg, start, -n)
        if hit and ob is not None and ob.type == 'MESH':
            real = bpy.data.objects[ob.name]
            if real not in found:
                found.append(real)
    return found


def cut_like_cut_tool(context, loops, projector, targets=None):
    """0.24.5 Alt in Base Mesh works like the Cut tool (its depth mode, depth, edge finish and solver): the
    old profile cutter was Height deep and went through thin plates."""
    from . import cut_engine as ce
    if not targets:
        targets = ce.auto_targets(context.view_layer, projector, loops)
    if not targets:
        raise cg.CutError('Alt Base Mesh cuts like the Cut tool: draw over a mesh.')
    return ce.perform_closed(context, 'CUT', targets, loops, projector, False)


def _view_projector(context):
    try:
        region, rv3d = context.region, context.region_data
        if region is None or region.type != 'WINDOW' or rv3d is None:
            return None
        from . import cut_engine as ce
        return ce.make_projector(region, rv3d)
    except (AttributeError, TypeError):
        return None


def _perform_cutter(context, groups, frame, p, projector, screen_groups, targets):
    """Alt: the drawn solid becomes a Boolean Difference cutter.  Its bevel
    sides are flipped (Top <-> Bottom, Both swaps top/bottom settings) and it is
    mirrored INTO the surface, so the flipped bevel lands on the opening of the
    pocket.  Depth = Height."""
    targets = _cutter_targets(context, projector, screen_groups, targets) if projector is not None \
        else (targets or [])
    if not targets:
        raise cg.CutError('Alt Base Mesh cuts into a mesh: start on a mesh or select the target first.')
    if p.profile in {'DOME', 'PUFF'}:
        raise cg.CutError('Alt cutter supports Flat / Chamfer / Bevel profiles (Dome / Puff have no flat cap).')
    bm = build_bmesh(groups, _WithEmbed(p, 0.0), flip=True)
    try:
        # mirror along local Z (into the surface) and lift a hair above it so the
        # opening is not coplanar with the surface
        eps = max(p.height * 0.01, 1e-5)
        for v in bm.verts:
            v.co.z = -v.co.z + eps
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        me = bpy.data.meshes.new('MCH_BaseCutter')
        bm.to_mesh(me)
    finally:
        bm.free()
    cutter = cg.link_temp_object(context, me)
    cutter.matrix_world = frame
    cut = context.scene.mch_cut
    done, failed, temp = [], [], []
    try:
        results = []
        for t in targets:
            try:
                cg.check_target(t)
                res, _solver = cg.boolean_result(context, t, cutter, 'DIFFERENCE', cut.solver, cut.hole_tolerant)
                temp.append(res)
                results.append((t, res))
            except (cg.CutError, RuntimeError) as ex:
                if len(targets) == 1:
                    raise
                failed.append(f'{t.name} ({str(ex).splitlines()[0][:60]})')
        if not results:
            raise cg.CutError('The Base Mesh cutter does not intersect any target; nothing was changed.')
        for t, res in results:
            cg.commit_mesh(t, res, cut.shared_mesh)
            done.append(t.name)
    finally:
        for m in temp:
            if m.users == 0:
                bpy.data.meshes.remove(m)
        cg.remove_object_and_mesh(cutter)
    sides, _t, _b = side_values(p, flip=True)
    msg = f'Base Mesh cutter (Alt): {", ".join(done)} | cutter bevel: {sides.title()}'
    if failed:
        msg += ' | FAILED, unchanged: ' + '; '.join(failed)
    return msg


# -----------------------------------------------------------------------------
# 0.14.1 Sketch First: orange outline you add to / subtract from, Enter = mesh
# -----------------------------------------------------------------------------

SKETCH_KEY = 'mch_base_sketch'     # Scene ID prop (JSON): undo (Ctrl+Z) removes the last stroke
SKETCH_EPS = 1e-7


def sketch_data(scene):
    text = scene.get(SKETCH_KEY) if scene is not None else None
    if not text:
        return None
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return None
    return data if data.get('items') else None


def sketch_frame(data):
    m = Matrix.Identity(4)
    vals = data['frame']
    for r in range(4):
        for c in range(4):
            m[r][c] = vals[r * 4 + c]
    return m


def sketch_clear(scene):
    if scene is not None and SKETCH_KEY in scene:
        del scene[SKETCH_KEY]


def _region_loops(items):
    """Flatten sketch items into CDT input: loops + (item index, is_hole)."""
    loops, owner = [], []
    for k, item in enumerate(items):
        for outer, holes in item['groups']:
            loops.append(outer)
            owner.append((k, False))
            for h in holes:
                loops.append(h)
                owner.append((k, True))
    return loops, owner


def sketch_triangles(items):
    """(verts, kept triangles) of the combined sketch: every stroke region is
    added or subtracted IN ORDER.  Blender's constrained Delaunay splits all
    outlines at their crossings and reports which input outlines contain each
    triangle, so overlaps, holes and islands come out exactly."""
    loops, owner = _region_loops(items)
    if not loops:
        return [], []
    verts, faces = [], []
    for lp in loops:
        if cg.signed_area(lp) < 0:
            lp = list(reversed(lp))      # the CDT needs counter-clockwise faces (holes are known by owner)
        start = len(verts)
        verts += [Vector((q[0], q[1])) for q in lp]
        faces.append(list(range(start, start + len(lp))))
    out_v, _e, out_f, _vo, _eo, out_fo = delaunay_2d_cdt(verts, [], faces, 1, SKETCH_EPS, True)
    kept = []
    for f, orig in zip(out_f, out_fo):
        if len(f) != 3:
            continue
        inside = False
        for k, item in enumerate(items):
            mine = [owner[i][1] for i in orig if owner[i][0] == k]
            # inside this stroke = inside one of its outlines and not in its holes
            in_region = bool(mine) and (mine.count(False) - mine.count(True)) > 0
            if not in_region:
                continue
            inside = item['op'] == 'ADD'
        if inside:
            a, b, c = f
            area = (out_v[b] - out_v[a]).cross(out_v[c] - out_v[a])
            kept.append((a, b, c) if area > 0 else (a, c, b))
    return [tuple(v) for v in out_v], kept


def _boundary_loops(verts, tris):
    """Outline loops of a set of counter-clockwise triangles."""
    directed = set()
    for a, b, c in tris:
        directed.update(((a, b), (b, c), (c, a)))
    nxt = {}
    for a, b in directed:
        if (b, a) not in directed:
            nxt.setdefault(a, []).append(b)
    loops = []
    while nxt:
        start = next(iter(nxt))
        lp = [start]
        cur = start
        for _ in range(len(directed) + 1):
            outs = nxt.get(cur)
            if not outs:
                break
            n = outs.pop()
            if not outs:
                del nxt[cur]
            if n == start:
                break
            lp.append(n)
            cur = n
        if len(lp) >= 3:
            loops.append([verts[i] for i in lp])
    return [_drop_collinear(lp) for lp in loops]


def _drop_collinear(lp, eps=1e-10):
    out = []
    n = len(lp)
    for i in range(n):
        a, b, c = lp[i - 1], lp[i], lp[(i + 1) % n]
        cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if abs(cross) > eps * max(1e-12, math.dist(a, b) * math.dist(b, c)) or math.dist(a, c) < 1e-12:
            out.append(b)
    return out if len(out) >= 3 else lp


def sketch_regions(items):
    """Combined sketch as Base Mesh groups [(outer CCW, [holes CW])]."""
    verts, tris = sketch_triangles(items)
    if not tris:
        return []
    return cg.organize_loops(_boundary_loops(verts, tris))


def sketch_add(context, loops, projector, subtract=False):
    """Add (or, Alt, subtract) a drawn outline to the sketch.  The first stroke
    fixes the drawing plane; later strokes are projected onto that plane, so
    the view may be orbited between strokes."""
    scene = context.scene
    screen_groups = cg.prepare_loops(loops)
    data = sketch_data(scene)
    if data is None:
        if subtract:
            raise cg.CutError('Draw a shape first: Alt subtracts from the orange sketch.')
        origin, x, y, n, embed = frame_for(context, projector, screen_groups)
        frame = Matrix.Identity(4)
        for r in range(3):
            frame[r][0], frame[r][1], frame[r][2], frame[r][3] = x[r], y[r], n[r], origin[r]
        data = {'frame': [frame[r][c] for r in range(4) for c in range(4)], 'items': [], 'embed': embed}
    else:
        frame = sketch_frame(data)
    origin = frame.translation
    n = frame.col[2].to_3d().normalized()
    inv = frame.inverted()

    def to_local(q):
        o, d = projector.ray(q)
        if abs(d.dot(n)) < 1e-6:
            raise cg.CutError('The view is edge-on to the sketch plane: orbit a little and draw again.')
        w = cg._plane_hit(o, d, origin, n)[0]
        v = inv @ w
        return (v.x, v.y)
    local_loops = [[to_local(q) for q in lp] for outer, holes in screen_groups for lp in [outer] + holes]
    groups = cg.organize_loops(local_loops)
    data['items'].append({'op': 'SUB' if subtract else 'ADD',
                          'groups': [[[list(q) for q in o], [[list(q) for q in h] for h in hs]] for o, hs in groups]})
    regions = sketch_regions(data['items'])
    scene[SKETCH_KEY] = json.dumps(data)
    adds = sum(1 for it in data['items'] if it['op'] == 'ADD')
    subs = len(data['items']) - adds
    state = f'{len(regions)} piece(s)' if regions else 'empty'
    return (f'Sketch: {"subtracted" if subtract else "added"} ({adds} added, {subs} subtracted, {state}) | '
            f'Enter: make mesh, Alt+Enter: cut into mesh, Esc: clear')


def sketch_commit(context, cutter=False):
    """Enter: the sketch becomes a live Base Mesh (Alt+Enter: a cutter into
    the mesh below).  The sketch is cleared only on success."""
    scene = context.scene
    data = sketch_data(scene)
    if data is None:
        raise cg.CutError('No sketch: draw a shape with the Base Mesh tool first.')
    groups = sketch_regions(data['items'])
    if not groups:
        raise cg.CutError('The sketch is empty (everything was subtracted). Esc clears it.')
    frame = sketch_frame(data)
    groups = [([tuple(q) for q in o], [[tuple(q) for q in h] for h in hs]) for o, hs in groups]
    proj = _view_projector(context) if cutter else None
    if cutter and proj is not None:
        # 0.24.5 Alt+Enter cuts like the Cut tool too: the sketch seen from the current view
        loops = []
        for o, hs in groups:
            for lp in [o] + list(hs):
                pts = [proj.to_screen(frame @ Vector((q[0], q[1], 0.0))) for q in lp]
                if any(p_ is None for p_ in pts):
                    raise cg.CutError('The sketch is behind the view: orbit so it is in front, then Alt+Enter.')
                loops.append([tuple(p_) for p_ in pts])
        msg = cut_like_cut_tool(context, loops, proj)
    elif cutter:
        targets = _sketch_cutter_targets(context, groups, frame)
        msg = _perform_cutter(context, groups, frame, scene.mch_base, None, None, targets)
    else:
        msg = _create_live_base(context, groups, frame, scene.mch_base, data.get('embed', 0.0))
    sketch_clear(scene)
    return msg


_SKETCH_CACHE = {}
_sketch_handle = None


def _sketch_draw_data(scene):
    text = scene.get(SKETCH_KEY)
    hit = _SKETCH_CACHE.get('v')
    if hit is not None and hit[0] == text:
        return hit[1]
    data = sketch_data(scene)
    out = None
    if data is not None:
        frame = sketch_frame(data)
        verts, tris = sketch_triangles(data['items'])
        world = [tuple(frame @ Vector((v[0], v[1], 0.0))) for v in verts]
        lines = []
        for lp in (_boundary_loops(verts, tris) if tris else []):
            pts = [tuple(frame @ Vector((q[0], q[1], 0.0))) for q in lp]
            for i in range(len(pts)):
                lines += [pts[i], pts[(i + 1) % len(pts)]]
        out = (world, tris, lines)
    _SKETCH_CACHE['v'] = (text, out)
    return out


def _draw_sketch():
    try:
        context = bpy.context
        scene = context.scene
        if scene is None or not scene.get(SKETCH_KEY):
            return
        from . import tool_state as ts
        if ts.effective_tool(context) != 'BASE':
            return
        d = _sketch_draw_data(scene)
        if not d:
            return
        import gpu
        from gpu_extras.batch import batch_for_shader
        world, tris, lines = d
        sh = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        gpu.state.depth_test_set('NONE')
        orange = (1.0, 0.55, 0.12)
        if tris:
            sh.uniform_float('color', (*orange, 0.18))
            batch_for_shader(sh, 'TRIS', {'pos': world}, indices=tris).draw(sh)
        if lines:
            gpu.state.line_width_set(2.0)
            sh.uniform_float('color', (*orange, 0.95))
            batch_for_shader(sh, 'LINES', {'pos': lines}).draw(sh)
            gpu.state.line_width_set(1.0)
        gpu.state.blend_set('NONE')
    except Exception:      # never break viewport drawing
        pass


def _sketch_poll(context):
    from . import tool_state as ts
    try:
        return (context.area is not None and context.area.type == 'VIEW_3D' and
                ts.effective_tool(context) == 'BASE' and sketch_data(context.scene) is not None)
    except (AttributeError, KeyError, TypeError):
        return False


class MCH_OT_base_sketch_commit(bpy.types.Operator):
    """Enter: the orange sketch becomes a Base Mesh.  Alt+Enter: it cuts into the mesh below"""
    bl_idname = 'mch.base_sketch_commit'
    bl_label = 'Make Mesh from Sketch'
    bl_options = {'REGISTER', 'UNDO'}
    cutter: BoolProperty(name='Cut Into Mesh', default=False, options={'SKIP_SAVE'})

    @classmethod
    def description(cls, context, properties):
        return ('Cut the sketch into the mesh below (selected meshes first)  (Alt+Enter)' if properties.cutter
                else 'Make a new Base Mesh from the orange sketch  (Enter)')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and sketch_data(context.scene) is not None

    def execute(self, context):
        try:
            msg = sketch_commit(context, self.cutter)
        except cg.CutError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class MCH_OT_base_sketch_key(bpy.types.Operator):
    """Enter / Alt+Enter in the Base Mesh tool while a sketch exists"""
    bl_idname = 'mch.base_sketch_key'
    bl_label = 'Sketch Key'
    bl_options = {'INTERNAL'}
    cutter: BoolProperty(default=False, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return _sketch_poll(context)

    def execute(self, context):
        return bpy.ops.mch.base_sketch_commit('EXEC_DEFAULT', cutter=self.cutter)


class MCH_OT_base_sketch_clear(bpy.types.Operator):
    """Throw the orange sketch away (Esc in the Base Mesh tool)"""
    bl_idname = 'mch.base_sketch_clear'
    bl_label = 'Clear Sketch'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return sketch_data(context.scene) is not None

    def execute(self, context):
        sketch_clear(context.scene)
        self.report({'INFO'}, 'Sketch cleared')
        return {'FINISHED'}


class MCH_OT_base_sketch_undo(bpy.types.Operator):
    """Remove the last shape from the sketch (Backspace)"""
    bl_idname = 'mch.base_sketch_undo'
    bl_label = 'Remove Last Sketch Shape'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return sketch_data(context.scene) is not None

    def execute(self, context):
        data = sketch_data(context.scene)
        data['items'].pop()
        if data['items']:
            context.scene[SKETCH_KEY] = json.dumps(data)
        else:
            sketch_clear(context.scene)
        return {'FINISHED'}


def auto_apply_session(context):
    """F02: leaving / switching away from the Base Mesh tool applies (freezes)
    ONLY the live Base Meshes this tool created since it was entered.  Other
    objects and modifiers are never touched.  Freezing keeps the geometry
    (no data change) and is one undo step."""
    names = list(context.scene.get(SESSION_KEY, []))
    for key in (SESSION_KEY, WS_KEY):
        if key in context.scene:
            del context.scene[key]
    frozen = []
    for name in names:
        ob = bpy.data.objects.get(name)
        if ob is not None and getattr(ob, 'mch_base', None) and ob.mch_base.live:
            ob.mch_base.live = False
            frozen.append(name)
    if frozen:
        try:
            bpy.ops.ed.undo_push(message='Base Mesh: auto apply')
        except RuntimeError:
            pass
    return frozen


WS_KEY = 'mch_base_session_ws'      # workspace the session was started in
WATCH_INTERVAL = 0.5


def _current_workspaces():
    wm = bpy.context.window_manager
    try:
        return {w.workspace.name for w in wm.windows if w.workspace is not None}
    except (AttributeError, ReferenceError):
        return set()


def _arm_tab_watch(context):
    """Leaving the workspace (another top tab) also applies this session's
    shapes.  A light timer runs only while unapplied shapes exist."""
    try:
        ws = context.workspace.name if context.workspace is not None else ''
    except (AttributeError, ReferenceError):
        ws = ''
    if ws and not context.scene.get(WS_KEY):
        context.scene[WS_KEY] = ws
    if not bpy.app.timers.is_registered(_tab_watch):
        bpy.app.timers.register(_tab_watch, first_interval=WATCH_INTERVAL)


def check_tab_left(context=None, workspaces=None):
    """Apply the session when its workspace is no longer shown in any window.
    Returns the frozen object names (testable without a window)."""
    context = context or bpy.context
    scene = context.scene
    if scene is None or not scene.get(SESSION_KEY):
        return None
    ws = scene.get(WS_KEY, '')
    shown = _current_workspaces() if workspaces is None else set(workspaces)
    if ws and shown and ws not in shown:
        frozen = auto_apply_session(context)
        return frozen
    return []


def _tab_watch():
    try:
        scene = bpy.context.scene
        if scene is None or not scene.get(SESSION_KEY):
            return None                      # nothing pending: stop the timer
        check_tab_left()
        return WATCH_INTERVAL if bpy.context.scene.get(SESSION_KEY) else None
    except (AttributeError, ReferenceError, RuntimeError):
        return None


@bpy.app.handlers.persistent
def _migrate_on_load(_dummy=None):
    """v0.8-0.9 'Bevel Bottom Too' -> Bevel Sides = Both (only when unset)."""
    pgs = [sc.mch_base for sc in bpy.data.scenes if hasattr(sc, 'mch_base')]
    pgs += [ob.mch_base for ob in bpy.data.objects if hasattr(ob, 'mch_base')]
    for p in pgs:
        if p.bottom_too and 'bevel_sides' not in p:
            live = p.live
            p.live = False          # no rebuild while migrating
            p.bevel_sides = 'BOTH'
            p.live = live


# -----------------------------------------------------------------------------
# Operators
# -----------------------------------------------------------------------------


def active_live_base(context):
    ob = context.active_object
    if ob is not None and ob.type == 'MESH' and getattr(ob, 'mch_base', None) and \
            ob.mch_base.live and ob.mch_base.outline and ob.select_get():
        return ob
    return None


class MCH_OT_set_profile(bpy.types.Operator):
    bl_idname = 'mch.set_profile'
    bl_label = 'Base Mesh Profile'
    bl_description = 'Profile for new Base Mesh shapes (also applied to the selected live Base Mesh)'
    bl_options = {'REGISTER', 'UNDO'}
    profile: EnumProperty(items=PROFILE_ITEMS, default='FLAT')

    @classmethod
    def description(cls, context, properties):
        p = next((p for p in PROFILES if p[0] == properties.profile), None)
        return p[2] if p else cls.bl_description

    def execute(self, context):
        context.scene.mch_base.profile = self.profile
        ob = active_live_base(context)
        if ob is not None:
            ob.mch_base.profile = self.profile
            if ob.mch_base.last_error:
                self.report({'WARNING'}, ob.mch_base.last_error)
        return {'FINISHED'}


class MCH_OT_base_freeze(bpy.types.Operator):
    bl_idname = 'mch.base_freeze'
    bl_label = 'Freeze Base Mesh'
    bl_description = 'Stop live rebuilding; the mesh becomes an ordinary mesh you can edit freely'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return active_live_base(context) is not None

    def execute(self, context):
        ob = active_live_base(context)
        ob.mch_base.live = False
        self.report({'INFO'}, f'{ob.name}: frozen (no longer live)')
        return {'FINISHED'}


CLASSES = (MCH_PG_BaseMesh, MCH_OT_set_profile, MCH_OT_base_freeze, MCH_OT_base_sketch_commit,
           MCH_OT_base_sketch_key, MCH_OT_base_sketch_clear, MCH_OT_base_sketch_undo)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_base = bpy.props.PointerProperty(type=MCH_PG_BaseMesh)
    bpy.types.Object.mch_base = bpy.props.PointerProperty(type=MCH_PG_BaseMesh)
    if _migrate_on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_migrate_on_load)
    global _sketch_handle
    if not bpy.app.background and _sketch_handle is None:
        _sketch_handle = bpy.types.SpaceView3D.draw_handler_add(_draw_sketch, (), 'WINDOW', 'POST_VIEW')


def unregister():
    global _sketch_handle
    if _sketch_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_sketch_handle, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _sketch_handle = None
    if bpy.app.timers.is_registered(_tab_watch):
        bpy.app.timers.unregister(_tab_watch)
    if _migrate_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_migrate_on_load)
    for n, t in (('mch_base', bpy.types.Object), ('mch_base', bpy.types.Scene)):
        if hasattr(t, n):
            delattr(t, n)
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
