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


def non_manifold_edge_count(mesh):
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        return sum(1 for e in bm.edges if not e.is_manifold)
    finally:
        bm.free()


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
            'Remesh it first (Remesh tool or its Run Key), then split / cut again.')


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


def boolean_result(context, target, cutter, operation, solver='AUTO',
                   hole_tolerant=False, allow_empty=False):
    """Run the Boolean with validation + solver fallback. Returns (mesh, solver)."""
    try:
        return _boolean_result(context, target, cutter, operation, solver, hole_tolerant, allow_empty)
    except CutError as ex:
        reflections = mirror_reflections(target) if 'does not intersect' in str(ex) else []
        if not reflections or cutter.type != 'MESH':
            raise
    # 0.24.9 a live Mirror: the shape was drawn over the mirrored copy, which the Boolean (base mesh only)
    # never sees - cut the base mesh with the shape mirrored back; the Mirror shows it on both sides again
    old = cutter.data
    cutter.data = _cutter_with_reflections(cutter, reflections)
    try:
        return _boolean_result(context, target, cutter, operation, solver, hole_tolerant, allow_empty)
    finally:
        tmp = cutter.data
        cutter.data = old
        if tmp.users == 0:
            bpy.data.meshes.remove(tmp)


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
        cutter_faces = attr is not None and any(v.value for v in attr.data)
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
    twins keep theirs).  Returns True when the object was baked."""
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
    and short edges into the surface.  Points move by less than the bevel width, which the bevel rounds over
    anyway.  Every step that would open the mesh is undone.  Returns the bmesh to keep (may be a new one)."""
    def layer_of(b):
        return _face_flag_layer(b)

    def dissolve_walls(b):
        lay = layer_of(b)
        inner = [e for e in b.edges if len(e.link_faces) == 2 and e.link_faces[0][lay] and e.link_faces[1][lay]]
        if inner:
            bmesh.ops.dissolve_limit(b, angle_limit=math.radians(0.5), verts=[], edges=inner)
    bm = _safe_step(bm, dissolve_walls)

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
    return bm


def finish_new_edges(mesh, mode='NONE', width=0.01, segments=3, profile=0.5, clamp=True, label=''):
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
        bmesh.ops.bevel(bm, geom=edges + verts, offset=width, offset_type='OFFSET',
                        segments=1 if mode == 'CHAMFER' else max(1, segments),
                        profile=profile, affect='EDGES', clamp_overlap=bool(clamp),
                        loop_slide=True)
        bm.normal_update()
        bm.to_mesh(mesh)
        return len(edges)
    finally:
        bm.free()


def remove_cutter_attribute(mesh):
    attr = mesh.attributes.get(CUTTER_ATTR)
    if attr is not None:
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
