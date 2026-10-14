"""0.22.1 Surface Lasso (stage 1): draw ON the mesh, orbit while drawing, split along the loop.

With the Surface button on (viewport header, next to Line) the Cut / Split tools
draw on the surface instead of the screen:

    click            add a point stuck to the surface (stored on the object,
                     so it stays on the mesh when you orbit / zoom / pan)
    drag a point     move it along the surface
    click the first point (3+ points)   close the loop
    Enter            split the part along the loop (closes it if needed)
    Backspace        remove the last point      Esc / Right click  cancel
    Middle mouse / wheel   view as usual (the loop stays on the mesh)

Between two points the line follows the surface (the straight chord pushed onto
the mesh along the surface normals).  The loop must go AROUND the part (an arm,
a leg, a neck ...): a thin "soap film" spanning the loop, made Cut Gap thick, is
subtracted (exact boolean) and the loose pieces become separate objects.
"""
from __future__ import annotations

import math

import bpy
from bpy.props import StringProperty
from mathutils import Vector
from mathutils.bvhtree import BVHTree

MODES = {'CUT', 'SPLIT'}
HIT_PX = 12.0
_draw_ops = []


def enabled(context, mode):
    brush = getattr(getattr(context, 'scene', None), 'mch_brush', None)
    return bool(brush is not None and getattr(brush, 'surface_mode', False) and mode in MODES)


def make_projector(region, rv3d):
    from . import core_geometry as cg
    return cg.Projector(region, rv3d)


# -----------------------------------------------------------------------------
# Surface queries (object local space)
# -----------------------------------------------------------------------------


class SurfaceTarget:
    """One mesh object with a BVH of its evaluated mesh (local space)."""

    def __init__(self, context, ob):
        self.name = ob.name
        dg = context.evaluated_depsgraph_get()
        self.bvh = BVHTree.FromObject(ob, dg)
        self.mw = ob.matrix_world.copy()
        self.imw = self.mw.inverted()
        self.nmw = self.mw.to_3x3().inverted().transposed()
        dims = [ob.dimensions[i] for i in range(3)]
        self.size = max(1e-6, math.sqrt(sum(d * d for d in dims)))

    def ray(self, origin_w, direction_w):
        o = self.imw @ Vector(origin_w)
        d = (self.imw.to_3x3() @ Vector(direction_w)).normalized()
        loc, nrm, _i, _d = self.bvh.ray_cast(o, d)
        if loc is None:
            return None
        if nrm.dot(d) > 0:
            nrm = -nrm
        return loc, nrm.normalized()

    def nearest(self, p):
        loc, nrm, _i, _d = self.bvh.find_nearest(p)
        return (loc, nrm.normalized()) if loc is not None else None

    def to_world(self, p):
        return self.mw @ Vector(p)

    def normal_world(self, n):
        return (self.nmw @ Vector(n)).normalized()


def trace(target, a, na, b, nb, step=None):
    """Points (local) from a to b following the surface: the chord pushed onto the mesh
    along the interpolated normals."""
    a, b, na, nb = Vector(a), Vector(b), Vector(na), Vector(nb)
    length = (b - a).length
    if length < 1e-9:
        return [a.copy()]
    step = step or max(target.size / 300.0, length / 200.0)
    n = max(2, min(400, int(length / step) + 1))
    out = []
    for k in range(n + 1):
        t = k / n
        p = a.lerp(b, t)
        nrm = na.lerp(nb, t)
        if nrm.length < 1e-9:
            nrm = na
        nrm.normalize()
        h = max(length * 0.6, target.size * 0.02)
        hit = target.bvh.ray_cast(p + nrm * h, -nrm, 2.0 * h)[0]
        if hit is None:
            hit = target.bvh.ray_cast(p - nrm * h, nrm, 2.0 * h)[0]
        if hit is None or (hit - p).length > h:
            near = target.nearest(p)
            hit = near[0] if near else p
        if not out or (hit - out[-1]).length > 1e-9:
            out.append(hit)
    return out


# -----------------------------------------------------------------------------
# Splitting along a loop
# -----------------------------------------------------------------------------


def resample_loop(pts, count):
    """Closed polyline -> ``count`` evenly spaced points."""
    pts = [Vector(p) for p in pts]
    if len(pts) < 3:
        return pts
    seg = [(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]
    lens = [(b - a).length for a, b in seg]
    total = sum(lens)
    if total < 1e-12:
        return pts[:count]
    out, acc, i = [], 0.0, 0
    for k in range(count):
        target = total * k / count
        while i < len(lens) - 1 and acc + lens[i] < target:
            acc += lens[i]
            i += 1
        a, b = seg[i]
        t = 0.0 if lens[i] < 1e-12 else (target - acc) / lens[i]
        out.append(a.lerp(b, min(1.0, max(0.0, t))))
    return out


def membrane(loop, normals, margin, rings=8, smooth=30):
    """Disk spanning a closed loop (world): outer ring pushed out along the surface
    normals by ``margin`` (so it crosses the surface), the loop, then rings toward
    the middle relaxed like a soap film.  Returns verts, faces."""
    n = len(loop)
    c = sum(loop, Vector()) / n
    rows = [[p + nrm * margin for p, nrm in zip(loop, normals)], [p.copy() for p in loop]]
    for k in range(1, rings):
        f = 1.0 - k / rings
        rows.append([c + (p - c) * f for p in loop])
    center = c.copy()
    for _it in range(smooth):                      # relax the inner rings (boundary rows 0, 1 fixed)
        new = [rows[0], rows[1]]
        for r in range(2, len(rows)):
            inner = rows[r + 1] if r + 1 < len(rows) else None
            row = []
            for i in range(n):
                nb = [rows[r][(i - 1) % n], rows[r][(i + 1) % n], rows[r - 1][i]]
                nb.append(inner[i] if inner is not None else center)
                row.append(sum(nb, Vector()) / 4.0)
            new.append(row)
        rows = new
        center = sum(rows[-1], Vector()) / n
    verts = [p for row in rows for p in row] + [center]
    faces = []
    for r in range(len(rows) - 1):
        for i in range(n):
            j = (i + 1) % n
            faces.append((r * n + i, r * n + j, (r + 1) * n + j, (r + 1) * n + i))
    ci = len(verts) - 1
    last = (len(rows) - 1) * n
    for i in range(n):
        faces.append((last + i, last + (i + 1) % n, ci))
    return verts, faces


def split_along_loop(context, ob, loop_world, normals_world, gap=0.0005, margin=None):
    """Cut ``ob`` along a closed surface loop with a ``gap`` thick film; loose pieces
    become separate objects.  Returns the list of resulting objects (ob first)."""
    import bmesh
    size = max(1e-6, max(ob.dimensions))
    margin = margin if margin is not None else max(size * 0.03, gap * 4.0)
    count = max(24, min(160, len(loop_world)))
    loop = resample_loop(loop_world, count)
    # normals at the resampled points: nearest original sample
    nrms = []
    for p in loop:
        k = min(range(len(loop_world)), key=lambda i: (Vector(loop_world[i]) - p).length_squared)
        nrms.append(Vector(normals_world[k]).normalized())
    verts, faces = membrane(loop, nrms, margin)
    me = bpy.data.meshes.new('MCH_SurfaceCutter')
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    cutter = bpy.data.objects.new('MCH_SurfaceCutter', me)
    context.scene.collection.objects.link(cutter)
    sol = cutter.modifiers.new('Gap', 'SOLIDIFY')
    sol.thickness = max(gap, 1e-5)
    sol.offset = 0.0
    sol.use_even_offset = False
    cutter.hide_render = True
    mod = ob.modifiers.new('MCH_SurfaceSplit', 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.object = cutter
    try:
        mod.solver = 'EXACT'
    except TypeError:
        pass
    try:
        context.view_layer.update()
        dg = context.evaluated_depsgraph_get()
        new_me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    finally:
        ob.modifiers.remove(mod)
        bpy.data.objects.remove(cutter)
        if me.users == 0:
            bpy.data.meshes.remove(me)
    # loose pieces -> objects (largest stays in ob); nothing came off -> keep the mesh unchanged
    bm = bmesh.new()
    bm.from_mesh(new_me)
    islands, seen = [], set()
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, isl = [f], []
        seen.add(f.index)
        while stack:
            g = stack.pop()
            isl.append(g.index)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index)
                        stack.append(h)
        islands.append(isl)
    bm.free()
    if len(islands) < 2:
        bpy.data.meshes.remove(new_me)
        return [ob]
    old = ob.data
    ob.data = new_me
    new_me.name = old.name
    if old.users == 0:
        bpy.data.meshes.remove(old)
    islands.sort(key=len, reverse=True)
    out = [ob]
    src = ob.data
    for k, isl in enumerate(islands[1:], 1):
        keep = set(isl)
        bm = bmesh.new()
        bm.from_mesh(src)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in keep], context='FACES')
        part_me = bpy.data.meshes.new(f'{ob.name}_part{k}')
        bm.to_mesh(part_me)
        bm.free()
        part = bpy.data.objects.new(part_me.name, part_me)
        for coll in ob.users_collection:
            coll.objects.link(part)
        part.matrix_world = ob.matrix_world.copy()
        for mat in src.materials:
            part_me.materials.append(mat)
        out.append(part)
    main = set(islands[0])
    bm = bmesh.new()
    bm.from_mesh(src)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in main], context='FACES')
    bm.to_mesh(src)
    bm.free()
    src.update()
    return out


# -----------------------------------------------------------------------------
# Modal logic
# -----------------------------------------------------------------------------


class SurfaceLogic:
    """Plain class (driven headless by the tests); MCH_OT_surface_lasso uses it."""

    def _proj(self, context):
        return make_projector(context.region, context.region_data)

    def _hit(self, context, xy):
        origin, direction = self._proj(context).ray(xy)
        if self.target is None:
            dg = context.evaluated_depsgraph_get()
            ok, loc, nrm, _i, ob, _m = context.scene.ray_cast(dg, Vector(origin), Vector(direction))
            if not ok or ob is None or ob.type != 'MESH':
                return None
            self.target = SurfaceTarget(context, ob)
        return self.target.ray(origin, direction)

    def _screen(self, context, p_local):
        return self._proj(context).to_screen(self.target.to_world(p_local))

    def _near_point(self, context, xy):
        """Index of a VISIBLE point under the cursor (points on the far side are ignored)."""
        best, bd = None, HIT_PX * getattr(self, 'ui', 1.0)
        proj = self._proj(context)
        for i, (p, n) in enumerate(self.points):
            s = self._screen(context, p)
            if s is None:
                continue
            _o, d = proj.ray(s)
            if self.target.normal_world(n).dot(Vector(d)) > 0.0:
                continue
            d = math.dist(s, xy)
            if d <= bd:
                best, bd = i, d
        return best

    def _segment(self, i):
        """Surface path from point i to point i + 1 (wraps when closed)."""
        a, na = self.points[i]
        b, nb = self.points[(i + 1) % len(self.points)]
        return trace(self.target, a, na, b, nb)

    def _rebuild(self):
        n = len(self.points)
        segs = n if (self.closed and n >= 3) else n - 1
        self.segments = [self._segment(i) for i in range(max(0, segs))]

    def loop_local(self):
        pts = []
        for s in self.segments:
            pts.extend(s[:-1] if len(s) > 1 else s)
        return pts

    def world_lines(self):
        """Polylines (world) for drawing: placed segments + hover segment."""
        if self.target is None:
            return []
        lines = [[self.target.to_world(p) for p in s] for s in self.segments]
        if self.hover is not None and self.points and not self.closed and self.drag is None:
            a, na = self.points[-1]
            seg = trace(self.target, a, na, self.hover[0], self.hover[1])
            lines.append([self.target.to_world(p) for p in seg])
        return lines

    def world_points(self):
        return [self.target.to_world(p) for p, _n in self.points] if self.target else []

    def start(self, context, xy, mode):
        self.mode = mode
        self.points, self.segments = [], []
        self.target = None
        self.closed = False
        self.drag = None
        self.hover = None
        self.ui = 1.0
        hit = self._hit(context, xy)
        if hit is None:
            return False
        self.points.append(hit)
        return True

    def click(self, context, xy):
        i = self._near_point(context, xy)
        if i == 0 and len(self.points) >= 3 and not self.closed:
            self.closed = True
            self._rebuild()
            return 'CLOSED'
        if i is not None:
            self.drag = i
            return 'DRAG'
        if self.closed:
            return 'NONE'
        hit = self._hit(context, xy)
        if hit is None:
            return 'NONE'
        self.points.append(hit)
        self._rebuild()
        return 'ADD'

    def move(self, context, xy):
        hit = self._hit(context, xy)
        if self.drag is not None:
            if hit is not None:
                self.points[self.drag] = hit
                self._rebuild()
            return
        self.hover = hit

    def release(self):
        self.drag = None

    def undo_point(self):
        if self.closed:
            self.closed = False
        elif self.points:
            self.points.pop()
        self._rebuild()

    def finish(self, context):
        if len(self.points) < 3:
            return None, 'Surface Lasso: place at least 3 points around the part'
        if not self.closed:
            self.closed = True
            self._rebuild()
        ob = bpy.data.objects.get(self.target.name)
        if ob is None:
            return None, 'Surface Lasso: the object is gone'
        loop = [self.target.to_world(p) for p in self.loop_local()]
        nrms = []
        for s, (i, _p) in zip(self.segments, enumerate(self.points)):
            a_n, b_n = self.points[i][1], self.points[(i + 1) % len(self.points)][1]
            cnt = max(1, len(s) - 1)
            for k in range(cnt):
                nrms.append(self.target.normal_world(Vector(a_n).lerp(Vector(b_n), k / cnt)))
        gap = getattr(context.scene.mch_brush, 'surface_gap', 0.0005)
        parts = split_along_loop(context, ob, loop, nrms, gap=gap)
        if len(parts) < 2:
            return parts, 'Surface Lasso: the loop does not go all the way around the part (nothing came off)'
        return parts, f'Surface Lasso: {len(parts)} parts'


def _draw():
    try:
        import gpu
        from gpu_extras.batch import batch_for_shader
        for op in list(_draw_ops):
            try:
                lines = op.world_lines()
                pts = op.world_points()
            except (ReferenceError, AttributeError):
                continue
            region = bpy.context.region
            size = (region.width, region.height) if region else (1, 1)
            sh = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
            gpu.state.blend_set('ALPHA')
            for depth, alpha in (('NONE', 0.25), ('LESS_EQUAL', 1.0)):
                gpu.state.depth_test_set(depth)
                sh.bind()
                sh.uniform_float('viewportSize', size)
                sh.uniform_float('lineWidth', 2.5)
                sh.uniform_float('color', (1.0, 0.25, 0.2, alpha))
                for ln in lines:
                    if len(ln) >= 2:
                        batch_for_shader(sh, 'LINE_STRIP', {'pos': [tuple(p) for p in ln]}).draw(sh)
            gpu.state.depth_test_set('NONE')
            psh = gpu.shader.from_builtin('UNIFORM_COLOR')
            gpu.state.point_size_set(9.0)
            psh.bind()
            psh.uniform_float('color', (0.3, 1.0, 0.35, 1.0))
            if pts:
                batch_for_shader(psh, 'POINTS', {'pos': [tuple(p) for p in pts]}).draw(psh)
            gpu.state.point_size_set(1.0)
            gpu.state.blend_set('NONE')
    except Exception:            # never break viewport drawing
        pass


class MCH_OT_surface_lasso(SurfaceLogic, bpy.types.Operator):
    """Draw on the mesh surface (orbit while drawing); Enter splits the part along the loop"""
    bl_idname = 'mch.surface_lasso'
    bl_label = 'Surface Lasso'
    bl_options = {'REGISTER', 'UNDO'}

    mode: StringProperty(default='SPLIT', options={'SKIP_SAVE'})

    def _hint(self, context):
        if context.area:
            context.area.header_text_set(
                'Surface Lasso: click points on the mesh (orbit freely)  |  click the first point: close  |  '
                'drag a point: move  |  Enter: split  |  Backspace: last  |  Esc: cancel')

    def _end(self, context):
        if self in _draw_ops:
            _draw_ops.remove(self)
        if context.area:
            context.area.header_text_set(None)
            context.area.tag_redraw()

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            return {'CANCELLED'}
        xy = (event.mouse_region_x, event.mouse_region_y)
        if not self.start(context, xy, self.mode):
            self.report({'WARNING'}, 'Surface Lasso: click on a mesh')
            return {'CANCELLED'}
        _draw_ops.append(self)
        context.window_manager.modal_handler_add(self)
        self._hint(context)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if context.area:
            context.area.tag_redraw()
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM',
                          'NDOF_MOTION'} or event.type.startswith('NUMPAD_') and event.type != 'NUMPAD_ENTER':
            return {'PASS_THROUGH'}
        xy = (event.mouse_region_x, event.mouse_region_y)
        if event.type == 'MOUSEMOVE':
            self.move(context, xy)
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                self.click(context, xy)
            elif event.value == 'RELEASE':
                self.release()
            return {'RUNNING_MODAL'}
        if event.type == 'BACK_SPACE' and event.value == 'PRESS':
            self.undo_point()
            return {'RUNNING_MODAL'}
        if event.type in {'RET', 'NUMPAD_ENTER', 'SPACE'} and event.value == 'PRESS':
            try:
                parts, msg = self.finish(context)
            except Exception as ex:        # keep the scene intact, report
                import traceback
                traceback.print_exc()
                self._end(context)
                self.report({'ERROR'}, f'Surface Lasso failed: {ex}')
                return {'CANCELLED'}
            if parts is None:
                self.report({'WARNING'}, msg)
                return {'RUNNING_MODAL'}
            self._end(context)
            self.report({'INFO'} if len(parts) > 1 else {'WARNING'}, msg)
            return {'FINISHED'}
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            self._end(context)
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}


_handle = None
CLASSES = (MCH_OT_surface_lasso,)


def register():
    global _handle
    for c in CLASSES:
        bpy.utils.register_class(c)
    if not bpy.app.background and _handle is None:
        _handle = bpy.types.SpaceView3D.draw_handler_add(_draw, (), 'WINDOW', 'POST_VIEW')


def unregister():
    global _handle
    if _handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_handle, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _handle = None
    _draw_ops.clear()
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
