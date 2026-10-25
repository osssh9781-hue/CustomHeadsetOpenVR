"""0.24.33 Jungle Gym (prototype): draw in 3D by crawling along a light lattice of bars.

A lattice of bars (a jungle gym) sits in the scene - only drawn on screen, never an object, never stored.  Press
and drag: the line crawls along the bars from node to node, like climbing through a vent.  Each step goes to the
neighbour (right / left / up / down / front / back) that best matches the way the mouse moves on screen, so in an
angled view the line also climbs in depth.  The wheel steps toward / away from you (when a depth bar is too short
on screen); going back over the last node erases it.
* Magnet: 1 = the line sits on the bars (sharp frame), lower = a free curve that only leans toward the bars.
* Corner: how round the turns are (0 = sharp, 1 = round curve).
* 45° (on): also across the cells - drag at 45 degrees on screen and the line goes diagonally.
* Back to the start node = a closed loop: flat loops become a live Base Mesh, the rest live tubes.
* Grid direction: World / Object / View / Surface, R / Shift+R turns it by 15 degrees.  The bar spacing follows
  the zoom (1 / 2 / 5 steps) unless a fixed spacing is set.
* After the stroke, F9 (Adjust Last Operation): Magnet, Corner, Thickness, Make.
``nice_step``, ``nearest_node``, ``crawl``, ``depth_offset``, ``path_points``, ``planar_axis`` and ``lattice_lines``
are the working parts (no UI).
"""
from __future__ import annotations

import json
import math

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, StringProperty
from bpy_extras import view3d_utils
from mathutils import Matrix, Vector

NEIGHBOURS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
# 45 degree bars: across each face of a cell (two axes at once) - 12 of them
DIAGONALS = tuple((i, j, k) for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1)
                  if abs(i) + abs(j) + abs(k) == 2)
WITH_45 = NEIGHBOURS + DIAGONALS
ORIENT_ITEMS = [
    ('WORLD', 'World', 'Bars along the world axes'),
    ('OBJECT', 'Object', 'Bars along the active object (its rotation, centred on it)'),
    ('VIEW', 'View', 'Bars facing the view when you start the stroke'),
    ('SURFACE', 'Surface', 'Bars standing on the surface where you start'),
]
MAKE_ITEMS = [
    ('AUTO', 'Auto', 'Flat closed loop = Base Mesh, anything else = Tube'),
    ('TUBE', 'Tube', 'Always a live tube along the line'),
    ('BASE', 'Base Mesh', 'A live Base Mesh from the loop (flattened onto its first layer)'),
]
ARC_MID = 1.0 - 1.0 / math.sqrt(2.0)     # 90 degree fillet: arc middle sits this far along (ua + ub) * r


# -----------------------------------------------------------------------------
# pure parts
# -----------------------------------------------------------------------------


def nice_step(x):
    """The 1 / 2 / 5 x 10^k value nearest to ``x`` (log scale)."""
    x = max(float(x), 1e-6)
    k = 10.0 ** math.floor(math.log10(x))
    return min((m * k for m in (1.0, 2.0, 5.0, 10.0)), key=lambda c: abs(math.log(c / x)))


def node_world(frame, n):
    origin, rot, step = frame
    return origin + rot @ (Vector(n) * step)


def nearest_node(frame, p):
    origin, rot, step = frame
    local = rot.transposed() @ (Vector(p) - origin) / step
    return tuple(int(round(c)) for c in local)


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _step_to(path, node):
    """Append ``node`` - or, when it is the node before, erase the last one (crawling back)."""
    if len(path) >= 2 and tuple(path[-2]) == tuple(node):
        path.pop()
    else:
        path.append(tuple(node))


def crawl(path, mouse, to_screen, frame, neighbours=NEIGHBOURS, reach=0.6, min_px=6.0, max_steps=64):
    """Move the end of ``path`` (lattice nodes) toward the screen point ``mouse``.

    A step is taken to the neighbour whose screen direction best matches the way to the mouse, once the mouse is
    ``reach`` of the way there.  Bars shorter than ``min_px`` on screen are skipped (the wheel takes those).
    Returns the number of steps (erasing steps count too)."""
    mouse = Vector(mouse)
    steps = 0
    for _ in range(max_steps):
        cur = tuple(path[-1])
        c2 = to_screen(node_world(frame, cur))
        if c2 is None:
            break
        c2 = Vector(c2)
        d = mouse - c2
        best, best_score = None, -1e9
        for off in neighbours:
            nb = _add(cur, off)
            s2 = to_screen(node_world(frame, nb))
            if s2 is None:
                continue
            v = Vector(s2) - c2
            length = v.length
            if length < min_px:
                continue
            t = d.dot(v) / (length * length)             # how far along that bar the mouse is
            if t < reach:
                continue
            perp = (d - v * t).length / length          # how far off that bar
            score = t - 1.5 * perp
            if score > best_score:
                best, best_score = nb, score
        if best is None:
            break
        _step_to(path, best)
        steps += 1
    return steps


def depth_offset(frame, view_dir, toward_viewer):
    """The lattice step most along the view (wheel): away from the viewer or toward."""
    rot = frame[1]
    axis = max(range(3), key=lambda i: abs(rot.col[i].dot(view_dir)))
    sign = 1 if rot.col[axis].dot(view_dir) > 0 else -1             # + = away from the viewer
    if toward_viewer:
        sign = -sign
    off = [0, 0, 0]
    off[axis] = sign
    return tuple(off)


def corners_only(pts, eps=1e-6):
    """Drop the middle points of straight runs (and repeats)."""
    out = []
    for p in pts:
        if out and (p - out[-1]).length < eps:
            continue
        if len(out) >= 2:
            a, b = out[-2], out[-1]
            u, v = b - a, p - b
            if u.length > eps and v.length > eps and u.normalized().dot(v.normalized()) > 1 - 1e-6:
                out[-1] = p
                continue
        out.append(p)
    return out


def _closest_on(poly, q):
    best, best_d = poly[0], 1e30
    for a, b in zip(poly, poly[1:]):
        ab = b - a
        t = 0.0 if ab.length_squared < 1e-12 else max(0.0, min(1.0, (q - a).dot(ab) / ab.length_squared))
        c = a + ab * t
        d = (q - c).length_squared
        if d < best_d:
            best, best_d = c, d
    return best


def _resample(pts, count):
    if len(pts) < 2 or count < 2:
        return list(pts)
    lens = [0.0]
    for a, b in zip(pts, pts[1:]):
        lens.append(lens[-1] + (b - a).length)
    total = lens[-1]
    if total < 1e-9:
        return [pts[0]]
    out, j = [], 0
    for i in range(count):
        s = total * i / (count - 1)
        while j < len(pts) - 2 and lens[j + 1] < s:
            j += 1
        seg = lens[j + 1] - lens[j]
        t = 0.0 if seg < 1e-12 else (s - lens[j]) / seg
        out.append(pts[j].lerp(pts[j + 1], t))
    return out


def path_points(frame, path, raw=(), magnet=1.0, corner=0.0, closed=False):
    """World points of the line: the bars (corners rounded by ``corner``), pulled toward the freehand ``raw``
    stroke as ``magnet`` drops below 1."""
    pts = corners_only([node_world(frame, n) for n in path])
    if closed and len(pts) > 2 and (pts[-1] - pts[0]).length < 1e-6:
        pts = pts[:-1]
    if corner > 0 and len(pts) >= 3:
        out = []
        n = len(pts)
        for i, p in enumerate(pts):
            if not closed and i in (0, n - 1):
                out.append(p)
                continue
            a, b = pts[i - 1], pts[(i + 1) % n]
            ua, ub = a - p, b - p
            r = corner * 0.5 * min(ua.length, ub.length)
            if r < 1e-9:
                out.append(p)
                continue
            ua.normalize()
            ub.normalize()
            out += [p + ua * r, p + (ua + ub) * r * ARC_MID, p + ub * r]
        pts = out
    if magnet < 1.0 and len(raw) >= 2 and len(pts) >= 2:
        poly = pts + [pts[0]] if closed else pts
        free = _resample([Vector(q) for q in raw], max(len(pts) * 3, 8))
        pts = [c.lerp(q, 1.0 - magnet) for q in free for c in (_closest_on(poly, q),)]
        if closed and len(pts) > 2:
            pts = pts[:-1]
    return pts


def planar_axis(path):
    """The lattice axis all nodes share (a flat loop), or None."""
    for a in range(3):
        if len({n[a] for n in path}) == 1:
            return a
    return None


def lattice_lines(centre, radius=2, path=()):
    """Bars and nodes near ``centre`` (lattice coordinates): [(node_a, node_b, fade)], [(node, fade)].
    Only a small block is drawn so the lattice costs the same however big it is."""
    cx, cy, cz = centre
    lines, nodes = [], []
    lim = radius + 0.5
    for i in range(-radius, radius + 1):
        for j in range(-radius, radius + 1):
            for k in range(-radius, radius + 1):
                d = math.sqrt(i * i + j * j + k * k)
                if d > lim:
                    continue
                n = (cx + i, cy + j, cz + k)
                fade = 1.0 - d / (lim + 0.5)
                nodes.append((n, fade))
                for off in NEIGHBOURS[::2]:
                    m = (i + off[0], j + off[1], k + off[2])
                    dm = math.sqrt(m[0] ** 2 + m[1] ** 2 + m[2] ** 2)
                    if dm <= lim:
                        lines.append((n, _add(n, off), min(fade, 1.0 - dm / (lim + 0.5))))
    return lines, nodes


# -----------------------------------------------------------------------------
# frames from the scene
# -----------------------------------------------------------------------------


def _rot_from_z(z):
    z = Vector(z).normalized()
    x = Vector((1, 0, 0)) if abs(z.x) < 0.9 else Vector((0, 1, 0))
    x = (x - z * x.dot(z)).normalized()
    y = z.cross(x)
    return Matrix((x, y, z)).transposed()


def grid_rotation(context, orient, normal=None):
    st = context.scene.mch_gym
    if orient == 'OBJECT' and context.active_object is not None:
        rot = context.active_object.matrix_world.to_quaternion().to_matrix()
    elif orient == 'VIEW' and context.region_data is not None:
        rot = context.region_data.view_rotation.to_matrix()
    elif orient == 'SURFACE' and normal is not None:
        rot = _rot_from_z(normal)
    else:
        rot = Matrix.Identity(3)
    return rot @ Matrix.Rotation(st.turn, 3, 'Z')


def grid_origin(context, orient):
    if orient == 'OBJECT' and context.active_object is not None:
        return context.active_object.matrix_world.translation.copy()
    return context.scene.cursor.location.copy()


def world_per_px(region, rv3d, at):
    c = view3d_utils.location_3d_to_region_2d(region, rv3d, at)
    if c is None:
        return 0.01
    a = view3d_utils.region_2d_to_location_3d(region, rv3d, c, at)
    b = view3d_utils.region_2d_to_location_3d(region, rv3d, (c[0] + 1.0, c[1]), at)
    return max((a - b).length, 1e-6)


def frame_at(context, region, rv3d, mouse):
    """(frame, start point) under the mouse: the surface hit, else the depth of the 3D cursor."""
    st = context.scene.mch_gym
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, mouse)
    ray = view3d_utils.region_2d_to_vector_3d(region, rv3d, mouse).normalized()
    normal = None
    hit = False
    try:
        dg = context.evaluated_depsgraph_get()
        hit, loc, normal, _i, _ob, _m = context.scene.ray_cast(dg, origin, ray)
    except (RuntimeError, AttributeError):
        hit = False
    if hit and st.use_surface:
        p = loc
    else:
        normal = None
        p = view3d_utils.region_2d_to_location_3d(region, rv3d, mouse, context.scene.cursor.location)
    step = st.spacing if not st.auto_spacing else nice_step(world_per_px(region, rv3d, p) * st.cell_px)
    return (grid_origin(context, st.orient), grid_rotation(context, st.orient, normal), step), p


# -----------------------------------------------------------------------------
# making the result
# -----------------------------------------------------------------------------


def make_result(context, frame, path, raw, magnet, corner, radius_cells, make, view_dir):
    """Create the tube / Base Mesh. Returns (object, message)."""
    from . import curve_tube as ct
    closed = len(path) >= 4 and tuple(path[-1]) == tuple(path[0])
    axis = planar_axis(path) if closed else None
    kind = make if make != 'AUTO' else ('BASE' if closed and axis is not None else 'TUBE')
    pts = path_points(frame, path, raw, magnet, corner, closed)
    if len(pts) < 2:
        raise ValueError('The line is too short (crawl at least one bar).')
    if kind == 'BASE':
        if not closed or len(pts) < 3:
            raise ValueError('Base Mesh needs a closed loop (come back to the start).')
        return _make_base(context, frame, path, pts, view_dir)
    ob = ct.new_tube(context, pts[0], radius=radius_cells * frame[2])
    tb = ob.mch_tube
    tb.live = False
    tb.spline = 'LINEAR' if corner <= 0 and magnet >= 1.0 else 'SMOOTH'
    tb.closed = closed
    ct.set_points(ob, [(p - pts[0], 1.0) for p in pts])
    tb.live = True
    ct.rebuild(ob)
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    return ob, f'Jungle Gym: tube along {len(path) - 1} bars'


def _make_base(context, frame, path, pts, view_dir):
    from . import base_mesh as bmod
    from . import core_geometry as cg
    rot = frame[1]
    axis = planar_axis(path)
    if axis is None:                                   # not flat: flatten onto the plane facing the view most
        axis = max(range(3), key=lambda i: abs(rot.col[i].dot(view_dir)))
    n = rot.col[axis].copy()
    if n.dot(view_dir) > 0:                            # the solid grows toward the viewer
        n.negate()
    x = rot.col[(axis + 1) % 3].copy()
    y = n.cross(x)
    origin = node_world(frame, path[0])
    loop = [((p - origin).dot(x), (p - origin).dot(y)) for p in pts]
    groups = cg.organize_loops([loop])
    if not groups:
        raise ValueError('The loop has no area.')
    m = Matrix.Identity(4)
    for r in range(3):
        m[r][0], m[r][1], m[r][2], m[r][3] = x[r], y[r], n[r], origin[r]
    bmod._create_live_base(context, groups, m, bmod.scene_defaults(context))
    return context.view_layer.objects.active, f'Jungle Gym: Base Mesh from a {len(path) - 1}-bar loop'


# -----------------------------------------------------------------------------
# settings / drawing / operators
# -----------------------------------------------------------------------------


def _redraw(_self, context):
    if context.area:
        context.area.tag_redraw()


class MCH_PG_Gym(bpy.types.PropertyGroup):
    orient: EnumProperty(name='Direction', items=ORIENT_ITEMS, default='WORLD', update=_redraw)
    turn: FloatProperty(name='Turn', default=0.0, subtype='ANGLE', update=_redraw,
                        description='Turn the bars round their up axis (R / Shift+R: 15 degrees)')
    auto_spacing: BoolProperty(name='Auto Spacing', default=True,
                               description='Bar spacing follows the zoom (1 / 2 / 5 steps)')
    cell_px: IntProperty(name='Cell Size', default=40, min=10, max=400, subtype='PIXEL',
                         description='About how big one cell looks on screen (Auto Spacing)')
    spacing: FloatProperty(name='Spacing', default=0.1, min=0.001, soft_max=2.0, unit='LENGTH',
                           description='Fixed bar spacing (Auto Spacing off)')
    use_surface: BoolProperty(name='Start on Surface', default=True,
                              description='Start at the surface under the mouse (else at the 3D cursor depth)')
    diagonals: BoolProperty(name='45°', default=True, update=_redraw,
                            description='Also crawl at 45 degrees (across the cells)')
    magnet: FloatProperty(name='Magnet', default=1.0, min=0.0, max=1.0,
                          description='1 = on the bars (sharp frame), lower = a free curve leaning to the bars')
    corner: FloatProperty(name='Corner', default=0.0, min=0.0, max=1.0, description='How round the turns are')
    radius_cells: FloatProperty(name='Thickness', default=0.15, min=0.01, max=2.0,
                                description='Tube radius (x the bar spacing)')
    make: EnumProperty(name='Make', items=MAKE_ITEMS, default='AUTO')


STATE = {'hover': None, 'op': None, 'handle': None}


def _shader(names):
    import gpu
    for name in names:
        try:
            return gpu.shader.from_builtin(name)
        except (ValueError, KeyError):
            continue
    return None


def draw_data(frame, centre, path=(), preview=(), with_45=False):
    """World-space draw lists: bars (pairs) and colours, nodes and colours, the path, the preview line."""
    lines, nodes = lattice_lines(centre, 2)
    bar_pos, bar_col = [], []
    for a, b, f in lines:
        c = (0.55, 0.8, 1.0, 0.45 * f)
        bar_pos += [node_world(frame, a), node_world(frame, b)]
        bar_col += [c, c]
    node_pos = [node_world(frame, n) for n, _f in nodes]
    node_col = [(0.75, 0.9, 1.0, 0.8 * f) for _n, f in nodes]
    path_pos = [node_world(frame, n) for n in path]
    return (bar_pos, bar_col, node_pos, node_col, path_pos, list(preview), axis_bars(frame, centre),
            axis_bars(frame, centre, 0.5, DIAGONALS) if with_45 else [])


def axis_bars(frame, centre, reach=1.0, offsets=NEIGHBOURS):
    """The X / Y / Z bars through the node you are on (drawn orange): the ways you can crawl next
    (``offsets=DIAGONALS``: the 45 degree ones, drawn shorter and fainter)."""
    c = node_world(frame, centre)
    out = []
    for off in offsets:
        out += [c, c.lerp(node_world(frame, _add(centre, off)), reach)]
    return out


def _draw_view():
    import gpu
    from gpu_extras.batch import batch_for_shader
    context = bpy.context
    try:
        op = STATE['op']
        if op is not None:
            frame, centre, path, preview = op.frame, op.path[-1], op.path, op.preview
        else:
            hv = STATE['hover']
            if hv is None or not _tool_active(context) or hv[2] != context.region.as_pointer():
                return
            frame, centre, path, preview = hv[0], hv[1], (), ()
        bars, bcol, nodes, ncol, pts, prev, axes, diag = draw_data(frame, centre, path, preview,
                                                                 context.scene.mch_gym.diagonals)
        gpu.state.blend_set('ALPHA')
        gpu.state.depth_test_set('NONE')
        flat = _shader(('FLAT_COLOR',))
        if flat is not None and bars:
            batch_for_shader(flat, 'LINES', {'pos': bars, 'color': bcol}).draw(flat)
        pts_sh = _shader(('POINT_FLAT_COLOR', 'FLAT_COLOR'))
        if pts_sh is not None and nodes:
            gpu.state.point_size_set(5.0)
            batch_for_shader(pts_sh, 'POINTS', {'pos': nodes, 'color': ncol}).draw(pts_sh)
            here = [node_world(frame, centre)]
            gpu.state.point_size_set(11.0)
            batch_for_shader(pts_sh, 'POINTS', {'pos': here, 'color': [(1.0, 0.62, 0.15, 1.0)]}).draw(pts_sh)
        uni = _shader(('UNIFORM_COLOR',))
        gpu.state.line_width_set(3.0)
        if uni is not None and diag:                   # fainter, shorter: the 45 degree ways
            gpu.state.line_width_set(2.0)
            uni.uniform_float('color', (1.0, 0.55, 0.1, 0.45))
            batch_for_shader(uni, 'LINES', {'pos': diag}).draw(uni)
            gpu.state.line_width_set(3.0)
        if uni is not None and axes:                   # orange X / Y / Z through where you are
            uni.uniform_float('color', (1.0, 0.55, 0.1, 0.95))
            batch_for_shader(uni, 'LINES', {'pos': axes}).draw(uni)
        if uni is not None and len(pts) >= 2:
            uni.uniform_float('color', (1.0, 0.62, 0.15, 0.55))
            batch_for_shader(uni, 'LINE_STRIP', {'pos': pts}).draw(uni)
        if uni is not None and len(prev) >= 2:
            uni.uniform_float('color', (1.0, 0.85, 0.3, 1.0))
            batch_for_shader(uni, 'LINE_STRIP', {'pos': prev}).draw(uni)
        gpu.state.line_width_set(1.0)
        gpu.state.point_size_set(1.0)
        gpu.state.blend_set('NONE')
    except Exception:          # never break the viewport drawing
        pass


def _tool_active(context):
    try:
        tool = context.workspace.tools.from_space_view3d_mode(context.mode, create=False)
        return tool is not None and tool.idname == MCH_TOOL_jungle_gym.bl_idname
    except (AttributeError, RuntimeError, TypeError):
        return False


class MCH_OT_gym_hover(bpy.types.Operator):
    """Show the bars near the mouse (tool keymap: mouse move)."""
    bl_idname = 'mch.gym_hover'
    bl_label = 'Jungle Gym Hover'
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D' or context.region_data is None:
            return {'PASS_THROUGH'}
        frame, p = frame_at(context, context.region, context.region_data,
                            (event.mouse_region_x, event.mouse_region_y))
        STATE['hover'] = (frame, nearest_node(frame, p), context.region.as_pointer())
        context.area.tag_redraw()
        return {'PASS_THROUGH'}


class MCH_OT_gym_turn(bpy.types.Operator):
    bl_idname = 'mch.gym_turn'
    bl_label = 'Turn Jungle Gym'
    bl_options = {'INTERNAL'}
    angle: FloatProperty(default=math.radians(15.0), subtype='ANGLE')

    def execute(self, context):
        st = context.scene.mch_gym
        st.turn = (st.turn + self.angle + math.pi) % (2 * math.pi) - math.pi
        STATE['hover'] = None
        return {'FINISHED'}


class MCH_OT_gym_draw(bpy.types.Operator):
    """Crawl along the bars; let go = a live tube (or a Base Mesh from a closed flat loop). F9 adjusts it."""
    bl_idname = 'mch.gym_draw'
    bl_label = 'Jungle Gym Draw'
    bl_options = {'REGISTER', 'UNDO', 'BLOCKING'}

    frame_origin: FloatVectorProperty(size=3, options={'HIDDEN'})
    frame_rot: FloatVectorProperty(size=9, default=(1, 0, 0, 0, 1, 0, 0, 0, 1), options={'HIDDEN'})
    frame_step: FloatProperty(default=0.1, min=1e-6, options={'HIDDEN'})
    nodes: StringProperty(options={'HIDDEN'})
    raw: StringProperty(options={'HIDDEN'})
    view_dir: FloatVectorProperty(size=3, default=(0, 0, -1), options={'HIDDEN'})
    magnet: FloatProperty(name='Magnet', default=1.0, min=0.0, max=1.0)
    corner: FloatProperty(name='Corner', default=0.0, min=0.0, max=1.0)
    radius_cells: FloatProperty(name='Thickness', default=0.15, min=0.01, max=2.0)
    make: EnumProperty(name='Make', items=MAKE_ITEMS, default='AUTO')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def stored_frame(self):
        r = self.frame_rot
        rot = Matrix(((r[0], r[1], r[2]), (r[3], r[4], r[5]), (r[6], r[7], r[8])))
        return Vector(self.frame_origin), rot, self.frame_step

    def execute(self, context):
        path = [tuple(n) for n in json.loads(self.nodes or '[]')]
        raw = [Vector(q) for q in json.loads(self.raw or '[]')]
        if len(path) < 2:
            self.report({'WARNING'}, 'Jungle Gym: crawl at least one bar')
            return {'CANCELLED'}
        try:
            _ob, msg = make_result(context, self.stored_frame(), path, raw, self.magnet, self.corner,
                                   self.radius_cells, self.make, Vector(self.view_dir))
        except Exception as exc:          # noqa: BLE001  (CutError / ValueError: tell, change nothing)
            self.report({'WARNING'}, f'Jungle Gym: {exc}')
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}

    def draw(self, context):
        col = self.layout.column(align=True)
        col.prop(self, 'magnet', slider=True)
        col.prop(self, 'corner', slider=True)
        col.prop(self, 'radius_cells', slider=True)
        self.layout.prop(self, 'make', expand=True)

    # --- the drag ------------------------------------------------------------

    def invoke(self, context, event):
        if context.mode != 'OBJECT' or context.area is None or context.area.type != 'VIEW_3D':
            return {'PASS_THROUGH'}
        region, rv3d = context.region, context.region_data
        mouse = (event.mouse_region_x, event.mouse_region_y)
        self.frame, p = frame_at(context, region, rv3d, mouse)
        self.path = [nearest_node(self.frame, p)]
        self.raw_pts = [node_world(self.frame, self.path[0])]
        self.preview = []
        self.vd = (rv3d.view_rotation @ Vector((0.0, 0.0, -1.0))).normalized()
        self.neigh = WITH_45 if context.scene.mch_gym.diagonals else NEIGHBOURS
        STATE['op'] = self
        if STATE['handle'] is None:
            STATE['handle'] = bpy.types.SpaceView3D.draw_handler_add(_draw_view, (), 'WINDOW', 'POST_VIEW')
        context.window_manager.modal_handler_add(self)
        self._header(context)
        return {'RUNNING_MODAL'}

    def _header(self, context):
        st = context.scene.mch_gym
        context.area.header_text_set(
            f'Jungle Gym  |  {len(self.path) - 1} bars  spacing {self.frame[2]:g}  |  Magnet {st.magnet:.2f}  '
            f'Corner {st.corner:.2f}  |  Wheel: front / back   go back = erase   3D mouse / MMB: view   '
            'RMB/Esc: cancel')

    def _to_screen(self, context):
        region, rv3d = context.region, context.region_data
        return lambda co: view3d_utils.location_3d_to_region_2d(region, rv3d, co)

    def _raw_point(self, context, mouse):
        """The free stroke point: on the plane facing the view through the current node."""
        region, rv3d = context.region, context.region_data
        at = node_world(self.frame, self.path[-1])
        return view3d_utils.region_2d_to_location_3d(region, rv3d, mouse, at)

    def _update_preview(self, context):
        st = context.scene.mch_gym
        closed = len(self.path) >= 4 and self.path[-1] == self.path[0]
        try:
            self.preview = path_points(self.frame, self.path, self.raw_pts, st.magnet, st.corner, closed)
            if closed and self.preview:
                self.preview = self.preview + [self.preview[0]]
        except Exception:          # noqa: BLE001
            self.preview = []

    def _finish_ui(self, context):
        STATE['op'] = None
        if context.area:
            context.area.header_text_set(None)
            context.area.tag_redraw()

    def modal(self, context, event):
        st = context.scene.mch_gym
        if event.type in {'NDOF_MOTION', 'MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM'} \
                or event.type.startswith('NDOF_BUTTON'):
            return {'PASS_THROUGH'}
        if event.type == 'MOUSEMOVE':
            mouse = (event.mouse_region_x, event.mouse_region_y)
            crawl(self.path, mouse, self._to_screen(context), self.frame, self.neigh)
            self.raw_pts.append(self._raw_point(context, mouse))
            self._update_preview(context)
            self._header(context)
        elif event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            off = depth_offset(self.frame, self.vd, event.type == 'WHEELUPMOUSE')
            _step_to(self.path, _add(self.path[-1], off))
            self.raw_pts.append(node_world(self.frame, self.path[-1]))
            self._update_preview(context)
            self._header(context)
        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            self._finish_ui(context)
            o, rot, step = self.frame
            self.frame_origin, self.frame_step = o, step
            self.frame_rot = [rot[i][j] for i in range(3) for j in range(3)]
            self.nodes = json.dumps([list(n) for n in self.path])
            self.raw = json.dumps([list(q) for q in self.raw_pts])
            self.view_dir = self.vd
            self.magnet, self.corner, self.radius_cells, self.make = st.magnet, st.corner, st.radius_cells, st.make
            if len(self.path) < 2:
                return {'CANCELLED'}
            return self.execute(context)
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self._finish_ui(context)
            return {'CANCELLED'}
        if context.area:
            context.area.tag_redraw()
        return {'RUNNING_MODAL'}


class MCH_TOOL_jungle_gym(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.jungle_gym'
    bl_label = 'Mecha Jungle Gym'
    bl_description = ('Prototype: draw in 3D by crawling along a lattice of bars.\n'
                      'Drag = crawl (wheel: front / back, go back = erase), back to the start = closed loop.\n'
                      'R / Shift+R: turn the bars')
    bl_icon = 'ops.mesh.primitive_cube_add_gizmo'
    bl_widget = None
    bl_keymap = (
        ('mch.gym_draw', {'type': 'LEFTMOUSE', 'value': 'PRESS'}, None),
        ('mch.gym_hover', {'type': 'MOUSEMOVE', 'value': 'ANY'}, None),
        ('mch.gym_turn', {'type': 'R', 'value': 'PRESS'}, {'properties': [('angle', math.radians(15.0))]}),
        ('mch.gym_turn', {'type': 'R', 'value': 'PRESS', 'shift': True},
         {'properties': [('angle', math.radians(-15.0))]}),
    )

    def draw_settings(context, layout, tool):
        draw(layout, context, compact=True)


def draw(layout, context, compact=False):
    st = context.scene.mch_gym
    layout.prop(st, 'orient', text='' if compact else 'Direction')
    layout.prop(st, 'turn')
    layout.prop(st, 'auto_spacing', toggle=True)
    layout.prop(st, 'cell_px' if st.auto_spacing else 'spacing')
    layout.prop(st, 'magnet', slider=True)
    layout.prop(st, 'corner', slider=True)
    layout.prop(st, 'radius_cells')
    layout.prop(st, 'make', text='' if compact else 'Make')
    layout.prop(st, 'diagonals', toggle=True)
    layout.prop(st, 'use_surface', toggle=True)


CLASSES = (MCH_PG_Gym, MCH_OT_gym_hover, MCH_OT_gym_turn, MCH_OT_gym_draw)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_gym = bpy.props.PointerProperty(type=MCH_PG_Gym)
    try:
        STATE['handle'] = bpy.types.SpaceView3D.draw_handler_add(_draw_view, (), 'WINDOW', 'POST_VIEW')
    except (AttributeError, RuntimeError, ValueError):
        STATE['handle'] = None
    try:
        bpy.utils.register_tool(MCH_TOOL_jungle_gym, after={'mecha.concept_move'}, group=False)
    except (ValueError, RuntimeError, KeyError):
        try:
            bpy.utils.register_tool(MCH_TOOL_jungle_gym, separator=True, group=False)
        except (ValueError, RuntimeError):
            pass


def unregister():
    try:
        bpy.utils.unregister_tool(MCH_TOOL_jungle_gym)
    except (ValueError, RuntimeError, KeyError, AttributeError):
        pass
    if STATE['handle'] is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(STATE['handle'], 'WINDOW')
        except (ValueError, RuntimeError):
            pass
    STATE.update(handle=None, hover=None, op=None)
    try:
        del bpy.types.Scene.mch_gym
    except AttributeError:
        pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
