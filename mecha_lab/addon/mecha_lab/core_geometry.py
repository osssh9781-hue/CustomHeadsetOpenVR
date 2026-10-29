"""Mecha Lab geometry core: screen shapes -> watertight cutters -> safe Booleans.

Nothing in this module calls ``bpy.ops`` or depends on a window/region, so the
same code runs inside the interactive tools and in headless regression tests.

Pipeline used by Cut / Split / PNG shapes:

1. 2D loops in region pixels (outer loops CCW, holes CW) are cleaned and
   validated (``prepare_loops``).
2. Every loop point is cast through the view (``Projector.ray``) onto a near and
   a far plane perpendicular to the view direction.  The result is a frustum
   shaped prism that matches the drawn screen silhouette in both perspective
   and orthographic views (``build_cutter_mesh``).  Caps are triangulated with
   holes, walls share the cap vertices, so the cutter is closed by construction
   and is checked for manifoldness before use.
3. The Boolean is evaluated on the *base mesh only* (other modifiers are
   muted while evaluating), the result is validated (empty / non-manifold /
   unchanged) and only then written back (``commit_mesh``).  Any failure leaves
   the original object untouched.  Shared (Alt+D) mesh data is handled
   explicitly instead of failing like ``modifier_apply``.
4. Faces that come from the cutter carry the ``mch_cutter_face`` attribute.
   Edges between cutter faces and original faces are exactly the *new cut
   edges*, which Edge Finish bevels/chamfers without touching other edges.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.geometry import tessellate_polygon

CUTTER_ATTR = 'mch_cutter_face'
TEMP_MODIFIER = 'MCH_TMP_Boolean'


class CutError(RuntimeError):
    """User facing failure; the scene has not been modified."""


# -----------------------------------------------------------------------------
# 2D loop helpers (region pixel coordinates, y up)
# -----------------------------------------------------------------------------


def signed_area(loop):
    n = len(loop)
    return 0.5 * sum(loop[i][0] * loop[(i + 1) % n][1] - loop[(i + 1) % n][0] * loop[i][1]
                     for i in range(n))


def point_in_loop(p, loop):
    inside = False
    x, y = p
    n = len(loop)
    for i in range(n):
        ax, ay = loop[i]
        bx, by = loop[(i + 1) % n]
        if (ay > y) != (by > y):
            xi = ax + (bx - ax) * (y - ay) / (by - ay)
            if x < xi:
                inside = not inside
    return inside


def point_in_loops(p, loops):
    """Even-odd test against a set of loops (outer loops and holes)."""
    inside = False
    for loop in loops:
        if point_in_loop(p, loop):
            inside = not inside
    return inside


def dedupe_loop(loop, eps=0.5):
    out = []
    for p in loop:
        p = (float(p[0]), float(p[1]))
        if not out or math.dist(p, out[-1]) > eps:
            out.append(p)
    while len(out) > 2 and math.dist(out[0], out[-1]) <= eps:
        out.pop()
    # Remove exact back-tracking spikes (a, b, a) which tessellation rejects.
    changed = True
    while changed and len(out) > 3:
        changed = False
        n = len(out)
        for i in range(n):
            if math.dist(out[i - 1], out[(i + 1) % n]) <= eps:
                del out[i]
                changed = True
                break
    return out


def _orient(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def segments_cross(a, b, c, d, eps=1e-9):
    """True when the segments properly intersect or touch (excluding shared endpoints)."""
    d1 = _orient(c, d, a)
    d2 = _orient(c, d, b)
    d3 = _orient(a, b, c)
    d4 = _orient(a, b, d)
    if ((d1 > eps and d2 < -eps) or (d1 < -eps and d2 > eps)) and \
            ((d3 > eps and d4 < -eps) or (d3 < -eps and d4 > eps)):
        return True

    def on_segment(p, q, r):
        return (min(p[0], q[0]) - eps <= r[0] <= max(p[0], q[0]) + eps and
                min(p[1], q[1]) - eps <= r[1] <= max(p[1], q[1]) + eps)
    if abs(d1) <= eps and on_segment(c, d, a):
        return True
    if abs(d2) <= eps and on_segment(c, d, b):
        return True
    if abs(d3) <= eps and on_segment(a, b, c):
        return True
    if abs(d4) <= eps and on_segment(a, b, d):
        return True
    return False


def find_intersections(loops, limit=1):
    """Return up to ``limit`` intersecting segment pairs across/within loops.

    Uses a uniform grid so PNG contours with thousands of points stay fast.
    Adjacent segments of the same loop (which share a vertex) are ignored.
    """
    segs = []
    for li, loop in enumerate(loops):
        n = len(loop)
        for i in range(n):
            segs.append((li, i, n, loop[i], loop[(i + 1) % n]))
    if len(segs) < 4:
        return []
    total = sum(math.dist(s[3], s[4]) for s in segs)
    cell = max(total / len(segs) * 2.0, 1e-6)
    grid = {}
    for k, (_li, _i, _n, a, b) in enumerate(segs):
        x0, x1 = sorted((a[0], b[0]))
        y0, y1 = sorted((a[1], b[1]))
        for gx in range(int(math.floor(x0 / cell)), int(math.floor(x1 / cell)) + 1):
            for gy in range(int(math.floor(y0 / cell)), int(math.floor(y1 / cell)) + 1):
                grid.setdefault((gx, gy), []).append(k)
    found = []
    tested = set()
    for bucket in grid.values():
        m = len(bucket)
        for u in range(m):
            for v in range(u + 1, m):
                k1, k2 = bucket[u], bucket[v]
                key = (k1, k2) if k1 < k2 else (k2, k1)
                if key in tested:
                    continue
                tested.add(key)
                l1, i1, n1, a, b = segs[k1]
                l2, i2, n2, c, d = segs[k2]
                if l1 == l2:
                    if abs(i1 - i2) == 1 or abs(i1 - i2) == n1 - 1:
                        continue
                if segments_cross(a, b, c, d):
                    found.append(key)
                    if len(found) >= limit:
                        return found
    return found


def trim_closing_overlap(loop):
    """Freehand strokes often overshoot the start; cut the loop at that crossing."""
    n = len(loop)
    if n < 6:
        return loop
    head = min(n // 3, 40)
    for j in range(n - 2, max(n - 1 - head, 1), -1):
        c, d = loop[j], loop[j + 1]
        for i in range(0, min(head, j - 1)):
            a, b = loop[i], loop[i + 1]
            if segments_cross(a, b, c, d):
                # Intersection point replaces the overshoot on both ends.
                denom = (b[0] - a[0]) * (d[1] - c[1]) - (b[1] - a[1]) * (d[0] - c[0])
                if abs(denom) < 1e-12:
                    continue
                t = ((c[0] - a[0]) * (d[1] - c[1]) - (c[1] - a[1]) * (d[0] - c[0])) / denom
                x = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
                return [x] + loop[i + 1:j + 1]
    return loop


def simplify_open(points, tolerance):
    """Iterative Ramer-Douglas-Peucker for an open polyline."""
    if len(points) < 3 or tolerance <= 0:
        return list(points)
    keep = {0, len(points) - 1}
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        ax, ay = points[a]
        bx, by = points[b]
        dx, dy = bx - ax, by - ay
        ll = dx * dx + dy * dy
        best, idx = -1.0, None
        for i in range(a + 1, b):
            px, py = points[i]
            if ll < 1e-12:
                d = math.hypot(px - ax, py - ay)
            else:
                t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / ll))
                d = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
            if d > best:
                best, idx = d, i
        if best > tolerance:
            keep.add(idx)
            stack.append((a, idx))
            stack.append((idx, b))
    return [points[i] for i in sorted(keep)]


def organize_loops(loops):
    """Group loops into (outer, [holes]) by containment depth.

    Even depth = solid outline (forced CCW), odd depth = hole (forced CW).
    Islands inside holes become new solid groups.
    """
    loops = [lp for lp in loops if len(lp) >= 3 and abs(signed_area(lp)) > 1e-9]
    info = []
    for i, lp in enumerate(loops):
        xs = [p[0] for p in lp]
        ys = [p[1] for p in lp]
        info.append((min(xs), min(ys), max(xs), max(ys)))
    depth = [0] * len(loops)
    parent = [None] * len(loops)
    areas = [abs(signed_area(lp)) for lp in loops]
    for i, lp in enumerate(loops):
        probe = lp[0]
        best = None
        for j, other in enumerate(loops):
            if i == j or areas[j] <= areas[i]:
                continue
            b = info[j]
            if not (b[0] <= probe[0] <= b[2] and b[1] <= probe[1] <= b[3]):
                continue
            if point_in_loop(probe, other):
                depth[i] += 1
                if best is None or areas[j] < areas[best]:
                    best = j
        parent[i] = best
    groups = {}
    for i, lp in enumerate(loops):
        if depth[i] % 2 == 0:
            outer = lp if signed_area(lp) > 0 else list(reversed(lp))
            groups[i] = (outer, [])
    for i, lp in enumerate(loops):
        if depth[i] % 2 == 1 and parent[i] in groups:
            hole = lp if signed_area(lp) < 0 else list(reversed(lp))
            groups[parent[i]][1].append(hole)
    return list(groups.values())


def prepare_loops(loops, min_area=4.0):
    """Clean, validate and group screen loops. Raises CutError when unusable."""
    clean = []
    for lp in loops:
        lp = dedupe_loop(lp)
        if len(lp) >= 3 and abs(signed_area(lp)) >= min_area:
            clean.append(lp)
    if not clean:
        raise CutError('The drawn shape is too small or has zero area.')
    if find_intersections(clean):
        raise CutError('The outline crosses itself. Draw a simpler outline '
                       '(or use Brush Stroke, which trims the closing overlap).')
    return organize_loops(clean)


# -----------------------------------------------------------------------------
# Projection
# -----------------------------------------------------------------------------


class Projector:
    """Region/view projection. Interactive tools wrap a real RegionView3D."""

    def __init__(self, region, rv3d):
        from bpy_extras import view3d_utils
        self._u = view3d_utils
        self.region = region
        self.rv3d = rv3d
        self.view_dir = (rv3d.view_rotation @ Vector((0.0, 0.0, -1.0))).normalized()
        self.is_perspective = bool(rv3d.is_perspective)
        self.eye = rv3d.view_matrix.inverted().translation.copy()

    def ray(self, xy):
        o = self._u.region_2d_to_origin_3d(self.region, self.rv3d, xy)
        d = self._u.region_2d_to_vector_3d(self.region, self.rv3d, xy).normalized()
        return o, d

    def to_screen(self, co):
        p = self._u.location_3d_to_region_2d(self.region, self.rv3d, co)
        return None if p is None else (p.x, p.y)


class OrthoProjector:
    """Deterministic orthographic projector used by headless tests."""

    def __init__(self, rotation, center=Vector((0, 0, 0)), pixels_per_unit=100.0,
                 size=(1000, 1000)):
        self.rot = rotation.to_matrix()
        self.center = Vector(center)
        self.ppu = pixels_per_unit
        self.size = size
        self.view_dir = (self.rot @ Vector((0, 0, -1))).normalized()
        self.is_perspective = False
        self.eye = self.center - self.view_dir * 1000.0

    def _axes(self):
        return self.rot @ Vector((1, 0, 0)), self.rot @ Vector((0, 1, 0))

    def ray(self, xy):
        right, up = self._axes()
        dx = (xy[0] - self.size[0] / 2) / self.ppu
        dy = (xy[1] - self.size[1] / 2) / self.ppu
        origin = self.center + right * dx + up * dy - self.view_dir * 1000.0
        return origin, self.view_dir.copy()

    def to_screen(self, co):
        right, up = self._axes()
        d = Vector(co) - self.center
        return (self.size[0] / 2 + d.dot(right) * self.ppu,
                self.size[1] / 2 + d.dot(up) * self.ppu)


def _plane_hit(origin, direction, plane_co, plane_no):
    den = direction.dot(plane_no)
    if abs(den) < 1e-12:
        raise CutError('View ray is parallel to the cut plane.')
    t = (plane_co - origin).dot(plane_no) / den
    return origin + direction * t, t


def object_world_bounds(objects):
    pts = []
    for ob in objects:
        mw = ob.matrix_world
        pts.extend(mw @ Vector(c) for c in ob.bound_box)
    return pts


def depth_planes(projector, bounds_points, mode='THROUGH', hit=None, depth=0.1,
                 above=None):
    """Return (near_co, far_co) on planes perpendicular to the view direction."""
    vd = projector.view_dir
    if mode == 'SURFACE':
        if hit is None:
            raise CutError('Aim the shape at the mesh surface (Depth mode = From Surface).')
        if depth <= 0:
            raise CutError('Cut depth must be positive.')
        above = max(1e-4, depth * 0.05) if above is None else above
        near = hit - vd * above
        far = hit + vd * depth
    else:
        if not bounds_points:
            raise CutError('No target geometry to cut.')
        ref = bounds_points[0]
        s = [(p - ref).dot(vd) for p in bounds_points]
        lo, hi = min(s), max(s)
        diag = max((max(bounds_points, key=lambda p: (p - ref).length) - ref).length, 1e-3)
        pad = diag * 0.05 + 1e-3
        near = ref + vd * (lo - pad)
        far = ref + vd * (hi + pad)
    if projector.is_perspective:
        eye_s = (projector.eye - near).dot(vd)
        if eye_s > -1e-5:   # near plane is behind or at the eye
            near = projector.eye + vd * 1e-4
    return near, far


def build_cutter_mesh(groups, projector, near_co, far_co, name='MCH_Cutter'):
    """Build a closed, outward-facing frustum prism mesh from grouped screen loops."""
    vd = projector.view_dir
    verts = []
    faces = []
    for outer, holes in groups:
        loops = [outer] + list(holes)
        flat = [p for lp in loops for p in lp]
        count = len(flat)
        base = len(verts)
        near_pts = []
        far_pts = []
        for xy in flat:
            o, d = projector.ray(xy)
            p_near, t_near = _plane_hit(o, d, near_co, vd)
            p_far, t_far = _plane_hit(o, d, far_co, vd)
            if projector.is_perspective and (t_near < 0 or t_far <= t_near):
                raise CutError('Shape projects behind the view; zoom out or use orthographic view.')
            near_pts.append(p_near)
            far_pts.append(p_far)
        verts.extend(near_pts)
        verts.extend(far_pts)
        tris = tessellate_polygon([[(x, y, 0.0) for x, y in lp] for lp in loops])
        if not tris:
            raise CutError('Shape could not be triangulated.')
        for a, b, c in tris:
            faces.append((base + a, base + b, base + c))
            faces.append((base + count + c, base + count + b, base + count + a))
        offset = 0
        for lp in loops:
            n = len(lp)
            for i in range(n):
                i0 = base + offset + i
                i1 = base + offset + (i + 1) % n
                faces.append((i0, i1, i1 + count, i0 + count))
            offset += n
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-7)
        if not bm.faces or any(not e.is_manifold for e in bm.edges):
            raise CutError('Cutter is not watertight (degenerate outline).')
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        if bm.calc_volume(signed=True) < 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        if abs(bm.calc_volume()) < 1e-12:
            raise CutError('Cutter has no volume.')
        bm.to_mesh(me)
    except Exception:
        bm.free()
        bpy.data.meshes.remove(me)
        raise
    bm.free()
    attr = me.attributes.new(CUTTER_ATTR, 'BOOLEAN', 'FACE')
    attr.data.foreach_set('value', [True] * len(me.polygons))
    me.update()
    return me


def link_temp_object(context, mesh, name='MCH_Cutter_TEMP'):
    ob = bpy.data.objects.new(name, mesh)
    # The master collection is always part of the view layer, so the Boolean
    # operand is evaluated even when the active collection is hidden/excluded.
    context.scene.collection.objects.link(ob)
    ob.display_type = 'WIRE'
    ob.hide_render = True
    return ob


def remove_object_and_mesh(ob):
    if ob is None:
        return
    try:
        me = ob.data if ob.type == 'MESH' else None
        bpy.data.objects.remove(ob, do_unlink=True)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
    except ReferenceError:
        pass


# -----------------------------------------------------------------------------
# Mesh validation / Boolean
# -----------------------------------------------------------------------------


def gn_get(mod, ident):
    """A Geometry Nodes modifier input value (Blender 5.2+: mod.properties.inputs, older: mod[ident])."""
    props = getattr(mod, 'properties', None)
    if props is not None and hasattr(props, 'inputs'):
        return getattr(props.inputs, ident).value
    return mod[ident]


def gn_set(mod, ident, value):
    """Set a Geometry Nodes modifier input (Blender 5.2+ and older)."""
    props = getattr(mod, 'properties', None)
    if props is not None and hasattr(props, 'inputs'):
        getattr(props.inputs, ident).value = value
    else:
        mod[ident] = value


def non_manifold_edge_count(mesh):
    """Edges not shared by exactly two faces (BMesh's is_manifold).  0.24.73 counted from the face corners with numpy
    (a BMesh copy + a Python loop over every edge was ~0.5 s of a 4.5 s Cut on 390k faces)."""
    import numpy as np
    ne = len(mesh.edges)
    if not ne:
        return 0
    le = np.empty(len(mesh.loops), np.int64)
    mesh.loops.foreach_get('edge_index', le)
    return int((np.bincount(le, minlength=ne) != 2).sum())


def overlap_edges(ob):
    """0.24.21 (edges shared by 3+ faces, open edges with 1 face): overlapping parts joined together / holes - the
    mesh is not one closed solid, and Booleans (Cut / Split) give broken results on it."""
    try:
        import numpy as np
        me = ob.data
        idx = np.zeros(len(me.loops), dtype=np.int64)
        me.loops.foreach_get('edge_index', idx)
        count = np.bincount(idx, minlength=len(me.edges))
        return int((count > 2).sum()), int((count == 1).sum())
    except (AttributeError, ImportError, ValueError):
        return 0, 0


def overlap_hint(ob, counts):
    multi, open_ = counts
    what = []
    if multi:
        what.append(f'{multi} edges are shared by 3+ faces (overlapping parts joined together)')
    if open_:
        what.append(f'{open_} edges are open (holes)')
    return (f'"{ob.name}" is not one clean solid: {" and ".join(what)}. Cut / Split need one closed volume - '
            'Fix Mesh it (Mesh Tools tab / Remesh tool / ZBrush shelf) or Remesh it first (Remesh tool or its Run Key), then '
            'split / cut again.')


def check_target(ob):
    if ob is None or ob.type != 'MESH':
        raise CutError('Select a mesh object to cut.')
    if ob.library or (ob.data and ob.data.library):
        raise CutError(f'"{ob.name}" is linked from a library; make it local first.')
    if ob.data.shape_keys:
        raise CutError(f'"{ob.name}" has shape keys. Apply or remove them before cutting.')
    if ob.hide_viewport:
        raise CutError(f'"{ob.name}" is disabled in viewports.')


def evaluate_boolean(context, target, cutter, operation, solver='EXACT',
                     hole_tolerant=False):
    """Mesh of ``target`` base geometry with one Boolean; caller owns the mesh."""
    saved = [(m, m.show_viewport) for m in target.modifiers]
    mod = None
    try:
        for m, _ in saved:
            m.show_viewport = False
        mod = target.modifiers.new(TEMP_MODIFIER, 'BOOLEAN')
        mod.operation = operation
        mod.solver = solver
        mod.object = cutter
        if hasattr(mod, 'use_hole_tolerant'):
            mod.use_hole_tolerant = bool(hole_tolerant and solver == 'EXACT')
        dg = context.evaluated_depsgraph_get()
        ev = target.evaluated_get(dg)
        return bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    finally:
        if mod is not None:
            target.modifiers.remove(mod)
        for m, show in saved:
            m.show_viewport = show


SOLVER_ORDER = {
    # AUTO on a closed target: Manifold first (fast, closed result), Exact fallback.
    # AUTO on an open/non-manifold target: Exact only (Manifold refuses such input).
    'AUTO': ('MANIFOLD', 'EXACT'),
    'EXACT': ('EXACT',),
    'MANIFOLD': ('MANIFOLD',),
    'FAST': ('FLOAT',),
}


def mirror_reflections(target):
    """World-space reflection matrices of the target's live Mirror modifiers (every axis combination)."""
    out = [Matrix.Identity(4)]
    for m in target.modifiers:
        if m.type != 'MIRROR' or not m.show_viewport:
            continue
        frame = m.mirror_object.matrix_world if m.mirror_object is not None else target.matrix_world
        inv = frame.inverted_safe()
        for axis in range(3):
            if not m.use_axis[axis]:
                continue
            flip = Matrix.Identity(4)
            flip[axis][axis] = -1.0
            r = frame @ flip @ inv
            out += [r @ q for q in out]
    return out[1:]


def _cutter_with_reflections(cutter, reflections):
    """A new mesh: the cutter plus its mirrored copies (cutter space)."""
    cw = cutter.matrix_world
    cwi = cw.inverted_safe()
    bm = bmesh.new()
    bm.from_mesh(cutter.data)
    for r in reflections:
        tmp = bmesh.new()
        tmp.from_mesh(cutter.data)
        tmp.transform(cwi @ r @ cw)
        bmesh.ops.reverse_faces(tmp, faces=tmp.faces[:])
        me_tmp = bpy.data.meshes.new('MCH_mirror_tmp')
        tmp.to_mesh(me_tmp)
        tmp.free()
        bm.from_mesh(me_tmp)
        bpy.data.meshes.remove(me_tmp)
    me = bpy.data.meshes.new(cutter.data.name + '_mirrored')
    bm.to_mesh(me)
    bm.free()
    return me


def loose_labels(mesh):
    """0.24.58 A part number per vertex (vertices joined by edges share it) - numpy hooking + pointer jumping."""
    import numpy as np
    n = len(mesh.vertices)
    labels = np.arange(n, dtype=np.int64)
    if not len(mesh.edges):
        return labels
    ev = np.empty(len(mesh.edges) * 2, dtype=np.int64)
    mesh.edges.foreach_get('vertices', ev)
    a, b = ev[0::2], ev[1::2]
    for _round in range(64):
        la, lb = labels[a], labels[b]
        diff = la != lb
        if not diff.any():
            break
        lo, hi = np.minimum(la[diff], lb[diff]), np.maximum(la[diff], lb[diff])
        np.minimum.at(labels, hi, lo)                     # hook the higher root under the lower
        while True:
            nxt = labels[labels]
            if np.array_equal(nxt, labels):
                break
            labels = nxt
    return labels


def _world_box(ob):
    import numpy as np
    co = np.empty(len(ob.data.vertices) * 3, dtype=np.float64)
    ob.data.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    m = np.array(ob.matrix_world, dtype=np.float64)
    return co @ m[:3, :3].T + m[:3, 3]


def touched_parts(target, cutter):
    """0.24.58 (vertex mask of the loose parts whose box meets the cutter's box, parts touched, parts in all) - a
    Cut only needs those (a mesh of many joined tubes: the Boolean on everything was slow, and the untouched
    overlapping parts kept the fast Manifold solver from being used)."""
    import numpy as np
    labels = loose_labels(target.data)
    uniq, inv = np.unique(labels, return_inverse=True)
    if not len(cutter.data.vertices) or not len(uniq):
        return None, 1, len(uniq)
    tw, cw = _world_box(target), _world_box(cutter)
    lo = np.full((len(uniq), 3), np.inf)
    hi = np.full((len(uniq), 3), -np.inf)
    np.minimum.at(lo, inv, tw)
    np.maximum.at(hi, inv, tw)
    pad = 1e-4 * max(1e-9, float(np.ptp(tw, axis=0).max()))
    c_lo, c_hi = cw.min(axis=0) - pad, cw.max(axis=0) + pad
    hit = np.all((lo <= c_hi) & (hi >= c_lo), axis=1)
    return hit[inv], int(hit.sum()), len(uniq)


def _mesh_without(mesh, drop_mask, name):
    """A copy of ``mesh`` without the vertices in ``drop_mask`` (and their faces)."""
    me = mesh.copy()
    me.name = name
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        bm.verts.ensure_lookup_table()
        idx = [int(i) for i in drop_mask.nonzero()[0]]
        bmesh.ops.delete(bm, geom=[bm.verts[i] for i in idx], context='VERTS')
        bm.to_mesh(me)
    finally:
        bm.free()
    return me


def _boolean_local(context, target, cutter, operation, solver, hole_tolerant, allow_empty):
    """0.24.58 The Boolean on only the loose parts the cutter can reach; the others are added back untouched
    (Difference) or left out (Intersect: they are outside the cutter).  None = not worth it (one part / all hit)."""
    if operation not in {'DIFFERENCE', 'INTERSECT'}:
        return None
    try:
        context.view_layer.update()                    # matrix_world up to date for the box test
    except (AttributeError, RuntimeError):
        pass
    mask, n_hit, n_all = touched_parts(target, cutter)
    if mask is None:
        return None
    if n_hit == 0:
        raise CutError('The shape does not intersect the mesh; nothing was changed.')
    if n_all < 2 or mask.all() or mask.mean() > 0.9:
        return None
    sub = _mesh_without(target.data, ~mask, target.data.name + '_mch_sub')
    full = target.data
    target.data = sub
    try:
        me, used = _boolean_result(context, target, cutter, operation, solver, hole_tolerant, allow_empty)
    finally:
        target.data = full
        bpy.data.meshes.remove(sub)
    if operation == 'DIFFERENCE':
        rest = _mesh_without(full, mask, full.name + '_mch_rest')
        bm = bmesh.new()
        try:
            bm.from_mesh(me)
            bm.from_mesh(rest)
            bm.to_mesh(me)
        finally:
            bm.free()
            bpy.data.meshes.remove(rest)
    LAST_BOOLEAN['parts'] = (n_hit, n_all)
    return me, used


LAST_BOOLEAN = {}


def boolean_result(context, target, cutter, operation, solver='AUTO',
                   hole_tolerant=False, allow_empty=False):
    """Run the Boolean with validation + solver fallback. Returns (mesh, solver).
    0.24.58 only on the loose parts the cutter reaches (``_boolean_local``)."""
    LAST_BOOLEAN.clear()
    try:
        got = _boolean_local(context, target, cutter, operation, solver, hole_tolerant, allow_empty)
        if got is not None:
            return got
        return _boolean_result(context, target, cutter, operation, solver, hole_tolerant, allow_empty)
    except CutError as ex:
        # 0.24.58 a Split's inner part (Intersect) of a shape off the base mesh is empty, not 'unchanged'
        missed = 'does not intersect' in str(ex) or (operation == 'INTERSECT' and 'whole object' in str(ex))
        reflections = mirror_reflections(target) if missed else []
        if not reflections or cutter.type != 'MESH':
            raise
    # 0.24.9 a live Mirror: the shape was drawn over the mirrored copy, which the Boolean (base mesh only)
    # never sees - cut the base mesh with the shape mirrored back; the Mirror shows it on both sides again
    old = cutter.data
    cutter.data = _cutter_with_reflections(cutter, reflections)
    try:
        got = _boolean_local(context, target, cutter, operation, solver, hole_tolerant, allow_empty)
        if got is not None:
            return got
        return _boolean_result(context, target, cutter, operation, solver, hole_tolerant, allow_empty)
    finally:
        tmp = cutter.data
        cutter.data = old
        if tmp.users == 0:
            bpy.data.meshes.remove(tmp)


def _any_true(attr):
    """Any element of a boolean / number attribute set (numpy, not a Python loop over every face)."""
    import numpy as np
    vals = np.zeros(len(attr.data), np.float32 if attr.data_type == 'FLOAT' else bool)
    try:
        attr.data.foreach_get('value', vals)
    except (TypeError, AttributeError, RuntimeError):
        return any(v.value for v in attr.data)
    return bool(vals.any())


def _boolean_result(context, target, cutter, operation, solver='AUTO',
                    hole_tolerant=False, allow_empty=False):
    source_nm = non_manifold_edge_count(target.data)
    src_counts = (len(target.data.vertices), len(target.data.polygons))
    problems = []
    for name in SOLVER_ORDER.get(solver, ('EXACT',)):
        if name == 'MANIFOLD' and source_nm:
            if solver != 'AUTO':
                problems.append('Manifold solver skipped: target mesh is not manifold')
            continue
        try:
            me = evaluate_boolean(context, target, cutter, operation, name, hole_tolerant)
        except RuntimeError as ex:
            problems.append(f'{name}: {ex}')
            continue
        if not me.polygons and not allow_empty:
            # some solver / input combinations return nothing: try the next solver
            bpy.data.meshes.remove(me)
            problems.append(f'{name}: empty result')
            continue
        attr = me.attributes.get(CUTTER_ATTR)
        cutter_faces = attr is not None and _any_true(attr)
        unchanged = not cutter_faces and (len(me.vertices), len(me.polygons)) == src_counts
        if unchanged:
            bpy.data.meshes.remove(me)
            problems.append(f'{name}: the shape did not intersect the mesh')
            continue
        nm = non_manifold_edge_count(me)
        if source_nm == 0 and nm:
            bpy.data.meshes.remove(me)
            problems.append(f'{name}: result has {nm} non-manifold edges')
            continue
        return me, name
    if problems and all('did not intersect' in p for p in problems):
        raise CutError('The shape does not intersect the mesh; nothing was changed.')
    if problems and all('empty result' in p for p in problems):
        what = {'DIFFERENCE': 'Cut', 'INTERSECT': 'Keep inside (Alt invert or Split inner part) - the shape may not overlap this object', 'UNION': 'Union'}.get(
            operation, operation)
        raise CutError(f'The result would delete the whole object; nothing was changed. [{target.name}: {what}, '
                       f'solvers tried: {", ".join(p.split(":")[0] for p in problems)}]')
    raise CutError('Boolean failed safely, mesh unchanged. ' + '; '.join(problems))


def ensure_real_mesh(context, ob):
    """A live Primitive (Geometry Nodes) has an EMPTY base mesh; Booleans work
    on the base mesh, so cutting it removed everything ("would delete the whole
    object").  Bake its evaluated geometry into a mesh of its own first (Alt+D
    twins keep theirs).  Returns True when the object was baked.
    0.24.80 a live Armor Shell too: its base mesh is the copy of the part under the shell modifiers."""
    from . import armor_shell
    if armor_shell.bake_live(context, ob):
        return True
    if ob.type != 'MESH' or len(ob.data.polygons) or not ob.modifiers:
        return False
    dg = context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    if not me.polygons:
        bpy.data.meshes.remove(me)
        return False
    old = ob.data
    me.name = old.name
    for mat in old.materials:
        me.materials.append(mat)
    ob.data = me
    ob.modifiers.clear()
    prim = getattr(ob, 'mch_primitive', None)
    if prim is not None and hasattr(prim, 'active'):
        try:
            prim.active = False
        except (AttributeError, TypeError):
            pass
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return True


NEEDLE = 2e-4                   # 0.24.83 tidy_result: a face with area / perimeter^2 under this is a needle (a square
#                                 is 1/16 = 0.0625, a 1:100 strip 0.0025, a 1:1000 strip 0.00025)


def mesh_size(me):
    """Diagonal of the mesh's own bounds (0 for no points)."""
    import numpy as np
    if not len(me.vertices):
        return 0.0
    co = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    return float(np.linalg.norm(co.max(0) - co.min(0)))


def _bad_edges(bm):
    """Edges with faces that are not shared by exactly two (open sides, 3+-face edges); wire edges do not count."""
    return sum(1 for e in bm.edges if e.link_faces and len(e.link_faces) != 2)


def _guarded(bm, fn):
    """0.24.83 Run a clean-up stage on a copy; keep it only when it does not open the mesh or add 3+-face edges
    (``bmesh.ops.dissolve_degenerate`` opened closed boolean results - 35 open edges on a 300-face part).
    Returns (bmesh to go on with, the stage's count or 0 when it was dropped)."""
    bad = _bad_edges(bm)
    trial = bm.copy()
    try:
        n = fn(trial)
    except (RuntimeError, ValueError, TypeError):
        trial.free()
        return bm, 0
    if not n or _bad_edges(trial) > bad:
        trial.free()
        return bm, 0
    bm.free()
    return trial, n


def _one_by_one(bm, pick, fixes, limit=256):
    """0.24.83 The faces ``pick`` finds (zero-area, needles), each tried on its own with the ``fixes`` in turn (the
    first that does not open the mesh is kept) - the bulk dissolve of a GN Edge / bevel result opened the mesh and was
    dropped whole, and its zero-area faces all stayed.  Returns (bmesh, faces fixed)."""
    done, tried = 0, set()
    for _ in range(limit):
        bm.faces.ensure_lookup_table()
        cand = None
        for f in pick(bm):
            key = tuple(round(c, 6) for c in f.calc_center_median()) + (len(f.verts),)
            if key not in tried:
                cand, ckey = f.index, key
                break
        if cand is None:
            break
        tried.add(ckey)
        for fix in fixes:
            def stage(b, i=cand, fix=fix):
                b.faces.ensure_lookup_table()
                nf = len(b.faces)
                fix(b, b.faces[i])
                return 1 if len(b.faces) < nf else 0
            bm, n = _guarded(bm, stage)
            if n:
                done += 1
                break
    return bm, done


def _shortest(f):
    return min(f.edges, key=lambda e: e.calc_length())


def _longest(f):
    return max(f.edges, key=lambda e: e.calc_length())


def _collapse_short(b, f):
    bmesh.ops.collapse(b, edges=[_shortest(f)], uvs=False)


def _dissolve_long(b, f):
    bmesh.ops.dissolve_edges(b, edges=[_longest(f)], use_verts=False, use_face_split=False)


def _is_zero(f):
    return f.calc_area() < 1e-12


def _is_needle(f):
    per = sum(e.calc_length() for e in f.edges)
    return per > 0 and f.calc_area() / (per * per) < NEEDLE


SPIKE_RATIO = 8.0               # a spike's shortest edge is this many times the typical edge round its neighbours
SPIKE_ANGLE = math.radians(4.0)  # ... and every face at it is this thin there
SPIKE_MAX_VERTS = 60000         # (the scan is Python per point)


def _spike_verts(b):
    """0.24.83 Points a bevel / GN edge left sticking out as a fan of needle faces: every edge at the point is far
    longer than the edges round its neighbours and every face is needle-thin there (the fuzz's spike rule)."""
    if len(b.verts) > SPIKE_MAX_VERTS:
        return []
    out = []
    for v in b.verts:
        if len(v.link_edges) < 2 or not v.link_faces:
            continue
        mine = min(e.calc_length() for e in v.link_edges)
        around = sorted(e2.calc_length() for e in v.link_edges for e2 in e.other_vert(v).link_edges if e2 is not e)
        if not around or mine <= SPIKE_RATIO * around[len(around) // 2]:
            continue
        thin = True
        for f in v.link_faces:
            vs = list(f.verts)
            i = vs.index(v)
            a, c = vs[i - 1].co - v.co, vs[(i + 1) % len(vs)].co - v.co
            if a.length <= 0 or c.length <= 0 or a.angle(c) >= SPIKE_ANGLE:
                thin = False
                break
        if thin:
            out.append(v)
    return out


def _spikes_one_by_one(bm, limit=64):
    """Each spike point dissolved on its own (its needle faces become one face), kept only when the mesh does not
    open.  Returns (bmesh, spikes removed)."""
    done, tried = 0, set()
    for _ in range(limit):
        bm.verts.ensure_lookup_table()
        cand = None
        for v in _spike_verts(bm):
            key = tuple(round(c, 6) for c in v.co)
            if key not in tried:
                cand, ckey = v.index, key
                break
        if cand is None:
            break
        tried.add(ckey)

        def stage(b, i=cand):
            b.verts.ensure_lookup_table()
            nv = len(b.verts)
            bmesh.ops.dissolve_verts(b, verts=[b.verts[i]], use_face_split=False, use_boundary_tear=False)
            return 1 if len(b.verts) < nv else 0

        bm, n = _guarded(bm, stage)
        done += n
    return bm, done


def tidy_result(me, ref_size=None, shards=True, slivers=True):
    """0.24.82 A boolean / decimate / remesh result made clean: points on the same spot welded, zero-area faces
    dissolved, needle slivers dissolved into their neighbours, folded faces (two faces on the same points, back to
    back - a paper-thin fin) removed, loose points gone, and (``shards``) separate pieces of under 6 faces that are
    tiny next to the part (under 2 % of ``ref_size``) dropped.  0.24.83 every stage is dropped again when it would
    open the mesh (``_guarded``), and short edges are only welded when they are really degenerate (a millionth of
    the part): the old 5 % of the median edge collapsed real bevel steps.  Returns a dict of counts (all zero =
    nothing was wrong)."""
    out = dict(welded=0, degenerate=0, needles=0, spikes=0, folds=0, fins=0, loose=0, shards=0, flipped=0)
    if me is None or not len(me.polygons):
        return out
    size = ref_size or mesh_size(me)
    eps = max(1e-9, 1e-6 * size)
    bm = bmesh.new()
    try:
        bm.from_mesh(me)

        def weld(b):
            nv = len(b.verts)
            bmesh.ops.remove_doubles(b, verts=b.verts[:], dist=eps)
            return nv - len(b.verts)

        bm, out['welded'] = _guarded(bm, weld)

        def folds(b):             # (first: two faces on the same points are a fin, not two needles)
            seen, twins = {}, []
            for f in b.faces:
                key = tuple(sorted(v.index for v in f.verts))
                if key in seen:
                    twins += [seen[key], f]
                else:
                    seen[key] = f
            twins = list({f.index: f for f in twins}.values())
            if twins:
                bmesh.ops.delete(b, geom=twins, context='FACES')
            return len(twins)

        bm, out['folds'] = _guarded(bm, folds)

        def degenerate(b):
            nf = len(b.faces)
            bmesh.ops.dissolve_degenerate(b, edges=b.edges[:], dist=eps)
            return nf - len(b.faces)

        bm, out['degenerate'] = _guarded(bm, degenerate)
        if any(_is_zero(f) for f in bm.faces):              # (the bulk pass was dropped or missed some: one by one)
            bm, n = _one_by_one(bm, lambda b: [f for f in b.faces if _is_zero(f)], (_collapse_short, _dissolve_long))
            out['degenerate'] += n
        if slivers and len(bm.faces) > 1:
            # needles: faces far thinner than long (area / perimeter^2 under NEEDLE) - the boolean's slivers along a
            # cut on a dense part - dissolved into their neighbours
            def needles(b):
                thin = []
                for f in b.faces:
                    per = sum(e.calc_length() for e in f.edges)
                    if per > 0 and f.calc_area() / (per * per) < NEEDLE:
                        thin.append(f)
                if not thin or len(thin) >= len(b.faces) // 2:
                    return 0
                bmesh.ops.dissolve_faces(b, faces=thin, use_verts=False)
                return len(thin)

            bm, out['needles'] = _guarded(bm, needles)
            if any(_is_needle(f) for f in bm.faces):        # (a needle on its own: dissolve_faces leaves it)
                bm, n = _one_by_one(bm, lambda b: [f for f in b.faces if _is_needle(f)], (_collapse_short, _dissolve_long))
                out['needles'] += n
            bm, out['spikes'] = _spikes_one_by_one(bm)      # 0.24.83 fans of needle faces round one far point
        if shards and len(bm.faces):
            def shard(b):
                b.verts.ensure_lookup_table()
                seen_v = set()
                drop = []
                for v in b.verts:
                    if v.index in seen_v or not v.link_faces:
                        continue
                    stack, comp = [v], []
                    while stack:
                        x = stack.pop()
                        if x.index in seen_v:
                            continue
                        seen_v.add(x.index)
                        comp.append(x)
                        stack.extend(e.other_vert(x) for e in x.link_edges)
                    faces = {f for x in comp for f in x.link_faces}
                    if len(faces) < 8:
                        lo = Vector((min(x.co.x for x in comp), min(x.co.y for x in comp), min(x.co.z for x in comp)))
                        hi = Vector((max(x.co.x for x in comp), max(x.co.y for x in comp), max(x.co.z for x in comp)))
                        # 0.24.83 ... or a few faces with next to no volume (a corner a GN chamfer shaved off)
                        vol = abs(sum(f.calc_area() * f.normal.dot(f.calc_center_median()) for f in faces)) / 3.0
                        if (hi - lo).length < 0.02 * size or len(faces) < 3 or vol < 1e-4 * size ** 3:
                            drop += list(faces)
                if not drop or len(drop) >= len(b.faces):
                    return 0
                bmesh.ops.delete(b, geom=drop, context='FACES')
                return len(drop)

            bm, out['shards'] = _guarded(bm, shard)

        # fins: an edge with 3+ faces keeps its two largest, the tiny ones hanging off it go
        def fins(b):
            gone = set()
            for e in b.edges:
                if len(e.link_faces) > 2:
                    fs = sorted(e.link_faces, key=lambda f: f.calc_area())
                    for f in fs[:-2]:
                        if f.calc_area() < 0.05 * fs[-1].calc_area():
                            gone.add(f)
            if gone:
                bmesh.ops.delete(b, geom=list(gone), context='FACES')
            return len(gone)

        bm, out['fins'] = _guarded(bm, fins)
        loose = [v for v in bm.verts if not v.link_faces]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context='VERTS')
            out['loose'] = len(loose)
        # a closed result with faces wound the wrong way (a remesh / boolean twist): the normals made consistent
        flipped = 0
        if len(bm.faces):                       # (0.24.83 an open result too: a Quad Remesh left 11 flipped faces)
            for e in bm.edges:
                if len(e.link_faces) == 2:
                    l1, l2 = e.link_loops[0], e.link_loops[1]
                    if l1.vert == l2.vert:
                        flipped += 1
            if flipped:
                bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
                out['flipped'] = flipped
        if any(out.values()):
            bm.to_mesh(me)
            me.update()
    finally:
        bm.free()
    return out


def is_junk(me, ref_size=None, open_ok=False):
    """A result not worth a part: under 4 faces, no area, a speck next to ``ref_size`` (under 1 % with fewer than 8
    faces), or paper (no volume to speak of: under a millionth of ``ref_size`` cubed - a Split's gap shard).
    ``open_ok`` (a Split with Cap off: open shells are what was asked) skips the open-scrap and the volume rules."""
    if me is None or not len(me.polygons):
        return True
    area = sum(p.area for p in me.polygons)
    size = mesh_size(me)
    if area <= 1e-12 * max(1.0, size * size) or size <= 0.0:
        return True
    if open_ok:                  # (an uncapped Split piece can be two flat patches: a part all the same)
        return False
    if len(me.polygons) < 4:
        return True
    if ref_size:
        if size < 0.01 * ref_size and len(me.polygons) < 8:
            return True
        if len(me.polygons) < 32 and non_manifold_edge_count(me) > 0:   # a small open scrap (a boolean that broke)
            return True
        bm = bmesh.new()
        try:
            bm.from_mesh(me)
            vol = abs(bm.calc_volume(signed=True))
        finally:
            bm.free()
        if vol < 1e-6 * ref_size ** 3:
            return True
    return False


def multi_edge_count(me):
    """Edges shared by 3+ faces (mesh data, no bmesh)."""
    try:
        import numpy as np
        if me is None or not len(me.polygons):
            return 0
        lv = np.empty(len(me.loops), np.int64)
        me.loops.foreach_get('edge_index', lv)
        return int((np.bincount(lv, minlength=len(me.edges)) > 2).sum())
    except (AttributeError, ValueError, ImportError):
        return 0


def inconsistent_edges(me):
    """0.24.83 Edges whose two faces run the same way along them (one is flipped against the other) - after
    recalc_face_normals this is only non-zero on a non-orientable sheet (a wall thinner than a quad whose two sides
    fused: a Quad Remesh result to retry finer or keep)."""
    if me is None or not len(me.polygons):
        return 0
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        n = 0
        for e in bm.edges:
            if len(e.link_faces) == 2 and e.link_loops[0].vert == e.link_loops[1].vert:
                n += 1
        return n
    finally:
        bm.free()


def self_overlaps(me, limit=300000):
    """0.24.83 How many pairs of faces of ``me`` cross each other (faces that share a point are neighbours, not
    crossings): a sculpted thin plate pushed through its other side.  Booleans give broken results on such a part.
    -1 = not checked (too big)."""
    if me is None or not len(me.polygons) or len(me.polygons) > limit:
        return -1
    try:
        from mathutils.bvhtree import BVHTree
        bm = bmesh.new()
        try:
            bm.from_mesh(me)
            bm.faces.ensure_lookup_table()
            tree = BVHTree.FromBMesh(bm)
            n = 0
            for a, b in tree.overlap(tree):
                if a >= b:
                    continue
                fa, fb = bm.faces[a], bm.faces[b]
                if {v.index for v in fa.verts} & {v.index for v in fb.verts}:
                    continue
                # a real crossing: each face has points clearly on both sides of the other's plane - clearly = past
                # a thousandth of the faces' own size (faces that only touch - a boolean seam, a T-junction, coplanar
                # neighbours, the two walls of a pinched fold a voxel remesh leaves - do not)
                eps = 1e-3 * max(max(e.calc_length() for e in fa.edges), max(e.calc_length() for e in fb.edges))
                crossing = True
                for f, g in ((fa, fb), (fb, fa)):
                    ds = [(v.co - g.verts[0].co).dot(g.normal) for v in f.verts]
                    if min(ds) > -eps or max(ds) < eps:
                        crossing = False
                        break
                if crossing:
                    n += 1
            return n
        finally:
            bm.free()
    except (RuntimeError, ValueError, ImportError):
        return -1


def strip_cutter_faces(mesh):
    """Delete faces that came from the cutter (open, un-capped cut)."""
    attr = mesh.attributes.get(CUTTER_ATTR)
    if attr is None:
        return 0
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        layer = _face_flag_layer(bm)
        doomed = [f for f in bm.faces if layer is not None and f[layer]]
        if doomed:
            bmesh.ops.delete(bm, geom=doomed, context='FACES')
        bm.to_mesh(mesh)
        return len(doomed)
    finally:
        bm.free()


def _face_flag_layer(bm):
    layers = bm.faces.layers
    for kind in ('bool', 'int'):
        coll = getattr(layers, kind, None)
        if coll is not None:
            layer = coll.get(CUTTER_ATTR)
            if layer is not None:
                return layer
    return None


FINISH_NOTES = []   # B10: per-operation notes about widths Blender had to limit


def _bevel_limit(edges):
    """Approximate largest width Blender's clamp allows: the shortest edge that
    meets a bevelled edge at one of its vertices (half of it where two bevelled
    edges share that neighbour)."""
    bevel = set(edges)
    limit = float('inf')
    for e in edges:
        for v in e.verts:
            for other in v.link_edges:
                if other in bevel:
                    continue
                length = other.calc_length()
                far = other.other_vert(v)
                shared = any(x in bevel for x in far.link_edges)
                limit = min(limit, length * (0.5 if shared else 1.0))
    return limit


def _open_edges(bm):
    return sum(1 for e in bm.edges if not e.is_manifold)


def _rim_edges(bm, layer):
    return [e for e in bm.edges if len(e.link_faces) == 2 and
            bool(e.link_faces[0][layer]) != bool(e.link_faces[1][layer])]


def _safe_step(bm, step):
    """Run ``step(bm)``; when it opens the mesh (it can at odd Boolean corners) go back.  Returns the bmesh
    to keep (the same one, or the copy from before the step)."""
    before = bm.copy()
    open0 = _open_edges(bm)
    step(bm)
    if _open_edges(bm) > open0:
        bm.free()
        return before
    before.free()
    return bm


def tidy_rim(bm, width, passes=6):
    """0.24.23 the Boolean leaves slivers where the cut crosses a dense (triangulated) mesh close to its
    vertices: edges of 0.00002 next to the new rim.  Blender's Clamp Overlap limits the WHOLE bevel to the
    shortest of them, so the bevel / chamfer came out invisible (a plain box has no such edges, so it worked
    there).  The flat cutter walls are merged back to big faces and the short edges at the rim are collapsed
    with Degenerate Dissolve: tiny rim pieces, chords between two rim points (Blender's clamp halves those)
    and short edges into the surface.  0.24.24: a collapse moves a rim point to the middle of the edge, off the
    cut, which made the rim zigzag and the bevel band uneven - every rim point is now put back onto the flat
    cut wall(s) it touches, so the rim is straight again.  Every step that would open the mesh is undone.
    Returns the bmesh to keep (may be a new one)."""
    def layer_of(b):
        return _face_flag_layer(b)

    def dissolve_walls(b):
        lay = layer_of(b)
        inner = [e for e in b.edges if len(e.link_faces) == 2 and e.link_faces[0][lay] and e.link_faces[1][lay]]
        if inner:
            bmesh.ops.dissolve_limit(b, angle_limit=math.radians(0.5), verts=[], edges=inner)
    bm = _safe_step(bm, dissolve_walls)
    lay0 = layer_of(bm)
    bm.normal_update()
    planes = [(f.calc_center_median(), f.normal.copy()) for f in bm.faces if f[lay0] and f.calc_area() > 0]

    def groups(b):
        lay = layer_of(b)
        edges = _rim_edges(b, lay)
        bevel = set(edges)
        rim_v = {v for e in edges for v in e.verts}
        near = {o for v in rim_v for o in v.link_edges if o not in bevel}
        both = [o for o in near if o.verts[0] in rim_v and o.verts[1] in rim_v]
        one = [o for o in near if not (o.verts[0] in rim_v and o.verts[1] in rim_v)]
        return ((0, edges, width * 0.5), (1, both, width * 2.0), (2, one, width))

    for _pass in range(passes):
        edges = _rim_edges(bm, layer_of(bm))
        if not edges or _bevel_limit(edges) >= width:
            break
        before = len(bm.edges)
        for kind, _g, dist in groups(bm):
            def run(b, kind=kind, dist=dist, part=None):
                g = [e for e in groups(b)[kind][1] if e.is_valid and e.calc_length() < dist]
                if part is not None:
                    g = g[part::4]
                if g:
                    bmesh.ops.dissolve_degenerate(b, dist=dist, edges=g)
            n0 = len(bm.edges)
            bm = _safe_step(bm, run)
            if len(bm.edges) == n0:                 # undone (or nothing to do): try it in smaller parts
                for part in range(4):
                    bm = _safe_step(bm, lambda b, part=part, kind=kind, dist=dist: run(b, kind, dist, part))
        if len(bm.edges) == before:
            break
    _snap_rim(bm, planes, width)
    return bm


def _snap_rim(bm, planes, width):
    """Put each rim point back onto the cut wall plane(s) of the cutter faces around it (the planes were taken
    before the collapse).  Only small moves (under the bevel width) are made."""
    lay = _face_flag_layer(bm)
    if lay is None or not planes:
        return
    bm.normal_update()
    rim_v = {v for e in _rim_edges(bm, lay) for v in e.verts}
    for v in rim_v:
        mine = []
        for f in v.link_faces:
            if not f[lay]:
                continue
            best = None
            for co, n in planes:
                if n.dot(f.normal) < 0.995:
                    continue
                d = abs((v.co - co).dot(n))
                if best is None or d < best[0]:
                    best = (d, co, n)
            if best is not None and best[0] < width and all(best[2].dot(m[1]) < 0.999 for m in mine):
                mine.append((best[1], best[2]))
        if not mine:
            continue
        p = v.co.copy()
        for _it in range(12):                        # alternate projections: the point on all its walls
            for co, n in mine:
                p = p - n * (p - co).dot(n)
        if (p - v.co).length < width:
            v.co = p


def crisp_shading(bm, bevel_faces, round_):
    """0.24.24 hard-surface shading of a finished cut: the bevel band shades on its own (smooth inside when it is
    round, a flat strip when it is a chamfer), its borders are sharp, so the smooth body next to it no longer
    smears into it; the flat cut walls stay flat."""
    band = set(bevel_faces)
    for f in band:
        f.smooth = bool(round_)
    layer = _face_flag_layer(bm)
    if layer is not None:
        for f in bm.faces:
            if f not in band and f[layer]:
                f.smooth = False
    for f in band:
        for e in f.edges:
            if any(g not in band for g in e.link_faces):
                e.smooth = False


def drop_custom_normals(mesh):
    """Imported custom normals (FBX) override sharp edges and get smeared over the new faces: drop them so
    Blender's own normals (with the sharp edges) are used.  Returns True when there were some."""
    attr = mesh.attributes.get('custom_normal')
    if attr is not None:
        try:
            mesh.attributes.remove(attr)
            return True
        except (RuntimeError, TypeError):
            pass
    if getattr(mesh, 'has_custom_normals', False):
        try:
            mesh.free_normals_split() if hasattr(mesh, 'free_normals_split') else None
        except RuntimeError:
            pass
    return False


def pulled_back(bm, before, verts, width):
    """Points of ``verts`` that lie outside the shape ``before`` (a BVH of it) go onto its nearest surface.
    Returns how many moved."""
    moved = 0
    tol = max(width * 1e-3, 1e-7)
    for v in {v for v in verts if v.is_valid}:
        loc, nrm, _i, _d = before.find_nearest(v.co)
        if loc is not None and (v.co - loc).dot(nrm) > tol:
            v.co = loc
            moved += 1
    return moved


def _rim_extent(edges):
    """The biggest size of the cut's border (a width as big as the cut itself is not carved, it is limited)."""
    pts = [v.co for e in edges for v in e.verts]
    return max(max(p[i] for p in pts) - min(p[i] for p in pts) for i in range(3)) if pts else 0.0


def finish_new_edges(mesh, mode='NONE', width=0.01, segments=3, profile=0.5, clamp=True, label='',
                     crisp=True):
    """Bevel/chamfer only edges between cutter faces and original faces.

    ``clamp`` keeps Blender's overlap clamp (safe geometry); when the requested
    width is larger than what the neighbouring edges allow, a note is added to
    FINISH_NOTES so the user learns the effective width instead of silently
    getting a smaller bevel."""
    if mode == 'NONE' or width <= 0 or mesh.attributes.get(CUTTER_ATTR) is None:
        return 0
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        layer = _face_flag_layer(bm)
        if layer is None:
            return 0
        edges = _rim_edges(bm, layer)
        if not edges:
            return 0
        limit = _bevel_limit(edges)
        if clamp and width > limit and mode in {'CHAMFER', 'BEVEL'} and not label.startswith('Seam') \
                and width < 0.25 * _rim_extent(edges):
            # 0.24.56 the edges next to the cut are too short for Blender's bevel (slivers of the Boolean): carve the
            # chamfer / round along the border instead (the GN Edge sweep - the full width, even all round; the
            # old tidy-up below left notches and widths from 0 to 2x)
            from . import rim_sweep
            bm.free()
            bm = bmesh.new()
            n = rim_sweep.finish(mesh, mode, width, segments)
            if n:
                if crisp:
                    flat_cut_faces(mesh)
                    drop_custom_normals(mesh)
                return n
            bm.from_mesh(mesh)
            layer = _face_flag_layer(bm)
            edges = _rim_edges(bm, layer) if layer is not None else []
            if not edges:
                return 0
        if clamp and width > limit:
            # 0.24.23 slivers from the Boolean would clamp it to nothing: tidy a copy, keep it only when the
            # mesh stays as closed as it was
            work = tidy_rim(bm.copy(), width)
            wlayer = _face_flag_layer(work)
            wedges = _rim_edges(work, wlayer)
            if wedges and _open_edges(work) <= _open_edges(bm) and _bevel_limit(wedges) > limit:
                bm.free()
                bm, layer, edges = work, wlayer, wedges
                limit = _bevel_limit(edges)
            else:
                work.free()
        if clamp and width > limit:
            FINISH_NOTES.append(f'{label + " " if label else ""}{mode.lower()} width {width:.4g} limited to '
                                f'about {limit:.4g} by short neighbouring edges (Clamp Overlap ON)')
        elif not clamp and width > limit:
            FINISH_NOTES.append(f'{label + " " if label else ""}{mode.lower()} width {width:.4g} exceeds the '
                                f'safe {limit:.4g} (Clamp Overlap OFF: geometry may overlap)')
        verts = list({v for e in edges for v in e.verts})
        from mathutils.bvhtree import BVHTree
        before = BVHTree.FromBMesh(bm)              # 0.24.42 the shape before the bevel (see below)
        res = bmesh.ops.bevel(bm, geom=edges + verts, offset=width, offset_type='OFFSET',
                              segments=1 if mode == 'CHAMFER' else max(1, segments),
                              profile=profile, affect='EDGES', clamp_overlap=bool(clamp),
                              loop_slide=True)
        # 0.24.42 where the cut meets another (bevelled) edge of the part, Blender's bevel can slide points OUT of
        # the part - dark spikes sticking out at the ends of a notch.  A bevel only takes material away: any
        # point that ended outside the old shape goes back onto its surface.
        pulled_back(bm, before, res.get('verts', []), width)
        if crisp:
            crisp_shading(bm, res.get('faces', []), mode == 'BEVEL' and segments > 1)
        bm.normal_update()
        bm.to_mesh(mesh)
        if crisp:
            drop_custom_normals(mesh)
        return len(edges)
    finally:
        bm.free()


def flat_cut_faces(mesh):
    """0.24.26 the faces a cutter made shade flat with sharp borders (a smooth plate next to them no longer smears
    dark streaks into the cut walls); the other faces keep their own shading."""
    attr = mesh.attributes.get(CUTTER_ATTR)
    if attr is None or attr.domain != 'FACE':
        return 0
    cut = [i for i, d in enumerate(attr.data) if d.value]
    if not cut:
        return 0
    cut_set = set(cut)
    for i in cut:
        mesh.polygons[i].use_smooth = False
    sharp = mesh.attributes.get('sharp_edge') or mesh.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE')
    edge_faces = {}
    for poly in mesh.polygons:
        for ek in poly.edge_keys:
            edge_faces.setdefault(ek, []).append(poly.index)
    for e in mesh.edges:
        fs = edge_faces.get(e.key, ())
        if any(f in cut_set for f in fs) and any(f not in cut_set for f in fs):
            sharp.data[e.index].value = True
    return len(cut)


def remove_cutter_attribute(mesh):
    """Every copy of the cutter flag goes (0.24.42: a Geometry Nodes result can carry it twice, on faces and on
    points - a copy left behind made the NEXT cut finish this cut's border again)."""
    for _ in range(8):
        attr = mesh.attributes.get(CUTTER_ATTR)
        if attr is None:
            break
        mesh.attributes.remove(attr)


def commit_mesh(target, new_mesh, shared_policy='SINGLE'):
    """Write ``new_mesh`` geometry into the target. Returns a short info string."""
    info = ''
    me = target.data
    if me.users > 1 and shared_policy == 'SINGLE':
        me = me.copy()
        target.data = me
        info = ' (shared mesh made single-user for this object)'
    elif me.users > 1:
        info = f' (shared mesh: {me.users} users updated)'
    bm = bmesh.new()
    try:
        bm.from_mesh(new_mesh)
        bm.to_mesh(me)
    finally:
        bm.free()
    for mat in list(new_mesh.materials)[len(me.materials):]:
        me.materials.append(mat)
    remove_cutter_attribute(me)
    me.update()
    return info


def plane_split_mesh(target, plane_co_world, plane_no_world, clear_positive, cap=True):
    """BMesh bisect of target base mesh. Returns a new Mesh (caller owns).

    ``clear_positive`` deletes the half on the side the plane normal points to.
    New cap faces are tagged with the cutter attribute for Edge Finish.
    """
    mw = target.matrix_world
    inv = mw.inverted_safe()
    co = inv @ plane_co_world
    no = (mw.transposed().to_3x3() @ plane_no_world)
    if no.length < 1e-12:
        raise CutError('Object scale is degenerate; apply a valid scale first.')
    no.normalize()
    bm = bmesh.new()
    try:
        bm.from_mesh(target.data)
        res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
                                     dist=1e-6, plane_co=co, plane_no=no,
                                     clear_outer=bool(clear_positive),
                                     clear_inner=not clear_positive)
        cut_edges = [g for g in res['geom_cut'] if isinstance(g, bmesh.types.BMEdge) and g.is_valid]
        if not cut_edges:
            raise CutError('The line does not cross the mesh; nothing was changed.')
        if not bm.faces:
            raise CutError('The plane cut would delete the whole object.')
        layer = bm.faces.layers.bool.new(CUTTER_ATTR) if hasattr(bm.faces.layers, 'bool') \
            else bm.faces.layers.int.new(CUTTER_ATTR)
        if cap:
            boundary = [e for e in cut_edges if e.is_boundary]
            if boundary:
                try:
                    filled = bmesh.ops.holes_fill(bm, edges=boundary, sides=0)
                    for f in filled.get('faces', []):
                        f[layer] = True
                except (ValueError, RuntimeError):
                    pass
        bm.normal_update()
        me = bpy.data.meshes.new(target.data.name + '_bisect')
        bm.to_mesh(me)
        for mat in target.data.materials:
            me.materials.append(mat)
        return me
    finally:
        bm.free()


def apply_single_modifier(context, ob, mod, shared_policy='SINGLE'):
    """Data-level replacement for ``bpy.ops.object.modifier_apply``.

    Evaluates the base mesh with only ``mod`` enabled (Blender's own semantics
    for applying a modifier), validates, writes it back and removes ``mod``.
    Works on multi-user (Alt+D) data and needs no active object or UI context.
    Raises CutError/RuntimeError and leaves the object unchanged on failure.
    """
    if ob.type != 'MESH':
        raise CutError(f'"{ob.name}" is not a mesh.')
    if ob.data.shape_keys:
        raise CutError(f'"{ob.name}" has shape keys; apply or remove them first.')
    if isinstance(mod, str):
        mod = ob.modifiers.get(mod)
    if mod is None:
        raise CutError('Modifier not found.')
    name = mod.name
    saved = [(m, m.show_viewport) for m in ob.modifiers]
    try:
        for m, _ in saved:
            m.show_viewport = (m == mod)
        dg = context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True,
                                             depsgraph=dg)
    finally:
        for m, show in saved:
            m.show_viewport = show
    try:
        info = commit_mesh(ob, me, shared_policy)
    finally:
        bpy.data.meshes.remove(me)
    m = ob.modifiers.get(name)
    if m is not None:
        ob.modifiers.remove(m)
    return info
