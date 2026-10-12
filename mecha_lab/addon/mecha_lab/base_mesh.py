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
    bottom_too: BoolProperty(name='Bevel Bottom Too', default=False, update=_rebuild_update)
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


def build_bmesh(groups, p):
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
        if p.profile in {'BEVEL', 'CHAMFER'} and p.bevel_width > 0:
            pairs = rim_top + (rim_bottom if p.bottom_too else [])
            edges = []
            for a, b in pairs:
                if a.is_valid and b.is_valid:
                    e = bm.edges.get((a, b))
                    if e is not None:
                        edges.append(e)
            limit = p.height * (0.48 if p.bottom_too else 0.95)
            width = min(p.bevel_width, limit)
            if edges and width > 0:
                verts = list({v for e in edges for v in e.verts})
                bmesh.ops.bevel(bm, geom=edges + verts, offset=width, offset_type='OFFSET',
                                segments=1 if p.profile == 'CHAMFER' else max(1, p.bevel_segments),
                                profile=0.5, affect='EDGES', clamp_overlap=True)
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


def perform_base(context, loops, projector):
    """Create the new solid. Returns a report string; raises CutError (scene untouched)."""
    screen_groups = cg.prepare_loops(loops)
    origin, x, y, n = plane_frame(context, projector, screen_groups)

    def to_local(q):
        w = _plane_point(projector, q, origin, -n)
        v = w - origin
        return (v.dot(x), v.dot(y))
    groups = [([to_local(q) for q in outer], [[to_local(q) for q in h] for h in holes])
              for outer, holes in screen_groups]
    groups = cg.organize_loops([lp for outer, holes in groups for lp in [outer] + holes])
    defaults = context.scene.mch_base
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
    frame = Matrix.Identity(4)
    for r in range(3):
        frame[r][0], frame[r][1], frame[r][2], frame[r][3] = x[r], y[r], n[r], origin[r]
    ob.matrix_world = frame
    live = ob.mch_base
    for key in ('height', 'wall', 'bevel_width', 'bevel_segments', 'roundness', 'resolution',
                'offset', 'bottom_too'):
        setattr(live, key, getattr(defaults, key))
    live.profile = defaults.profile        # live is still False: no rebuild yet
    live.outline = json.dumps({'groups': [{'outer': g[0], 'holes': g[1]} for g in groups]})
    live.live = True
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    name = dict((p[0], p[1]) for p in PROFILES)[defaults.profile]
    return f'Base Mesh created: {ob.name} ({name}, {len(me.vertices)} verts, closed solid)'


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


def unregister():
    for n, t in (('mch_base', bpy.types.Object), ('mch_base', bpy.types.Scene)):
        if hasattr(t, n):
            delattr(t, n)
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
