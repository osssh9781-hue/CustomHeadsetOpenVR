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
                'bottom_too', 'bevel_sides', 'bevel_width_bottom', 'bevel_segments_bottom', 'bevel_link')
MAX_DOME_POINTS = 12000


def _rebuild_update(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and self.live and self.outline:
        try:
            rebuild(ob)
            self.last_error = ''
        except (cg.CutError, ValueError, RuntimeError) as ex:
            self.last_error = str(ex)


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
                            description='Dome samples across the shape (higher = smoother, heavier)')
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


def _add_dome(bm, outer, holes, p):
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
        interior = [q for q, d in zip(cand, dist) if d > 0.45 * spacing]
    if len(interior) > MAX_DOME_POINTS:
        raise cg.CutError('Dome resolution too high for this outline; lower Resolution.')
    pts = boundary + interior
    d_all = [0.0] * len(boundary) + (_distances(interior, dense) if interior else [])
    radius = max(max(d_all), spacing)
    nb = len(boundary)
    edges = []
    off = 0
    for lp in dense:
        n = len(lp)
        edges += [(off + i, off + (i + 1) % n) for i in range(n)]
        off += n
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


def build_bmesh(groups, p, flip=False):
    """groups: [(outer CCW, [holes CW])] in local plane units. Returns a validated BMesh."""
    bm = bmesh.new()
    try:
        rim_top, rim_bottom = [], []
        for outer, holes in groups:
            if p.profile == 'DOME':
                _add_dome(bm, outer, holes, p)
            else:
                rt, rb = _add_prism(bm, outer, holes, p.height)
                rim_top += rt
                rim_bottom += rb
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-7)
        LAST_NOTES.clear()
        if p.profile in {'BEVEL', 'CHAMFER'}:
            LAST_NOTES.extend(_bevel_rims(bm, p, rim_top, rim_bottom, flip))
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


SESSION_KEY = 'mch_base_session'     # Scene ID prop: live Base Meshes made since the tool was entered


def _local_groups(context, loops, projector):
    screen_groups = cg.prepare_loops(loops)
    origin, x, y, n = plane_frame(context, projector, screen_groups)

    def to_local(q):
        w = _plane_point(projector, q, origin, -n)
        v = w - origin
        return (v.dot(x), v.dot(y))
    groups = [([to_local(q) for q in outer], [[to_local(q) for q in h] for h in holes])
              for outer, holes in screen_groups]
    groups = cg.organize_loops([lp for outer, holes in groups for lp in [outer] + holes])
    frame = Matrix.Identity(4)
    for r in range(3):
        frame[r][0], frame[r][1], frame[r][2], frame[r][3] = x[r], y[r], n[r], origin[r]
    return groups, frame, screen_groups


def perform_base(context, loops, projector, cutter=False, targets=None):
    """Create the new solid (or, ``cutter=True`` = Alt, cut it into the
    mesh below).  Returns a report string; raises CutError (scene untouched)."""
    groups, frame, screen_groups = _local_groups(context, loops, projector)
    defaults = context.scene.mch_base
    if cutter:
        return _perform_cutter(context, groups, frame, defaults, projector, screen_groups, targets)
    bm = build_bmesh(groups, defaults)
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


def _perform_cutter(context, groups, frame, p, projector, screen_groups, targets):
    """Alt: the drawn solid becomes a Boolean Difference cutter.  Its bevel
    sides are flipped (Top <-> Bottom, Both swaps top/bottom settings) and it is
    mirrored INTO the surface, so the flipped bevel lands on the opening of the
    pocket.  Depth = Height."""
    targets = _cutter_targets(context, projector, screen_groups, targets)
    if not targets:
        raise cg.CutError('Alt Base Mesh cuts into a mesh: start on a mesh or select the target first.')
    if p.profile == 'DOME':
        raise cg.CutError('Alt cutter supports Flat / Chamfer / Bevel profiles (Dome has no flat cap).')
    bm = build_bmesh(groups, p, flip=True)
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


CLASSES = (MCH_PG_BaseMesh, MCH_OT_set_profile, MCH_OT_base_freeze)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_base = bpy.props.PointerProperty(type=MCH_PG_BaseMesh)
    bpy.types.Object.mch_base = bpy.props.PointerProperty(type=MCH_PG_BaseMesh)
    if _migrate_on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_migrate_on_load)


def unregister():
    if bpy.app.timers.is_registered(_tab_watch):
        bpy.app.timers.unregister(_tab_watch)
    if _migrate_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_migrate_on_load)
    for n, t in (('mch_base', bpy.types.Object), ('mch_base', bpy.types.Scene)):
        if hasattr(t, n):
            delattr(t, n)
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
