"""0.24.164 3D Print (user: "3D 프린팅 전용 기능도 하나 만들어 줘 - 일단 사이즈 측정이랑, 사이즈는 수직 수평으로 잴 수 있는
거, 그리고 컷하고 그 사이에 연결 핀 넣어 주는 거"): two tools in the 3D Print group.

Print Measure - drag on the model: the length between the two points and how much of it is horizontal and how much
vertical (Shift: a straight horizontal or vertical line; X / Y / Z while dragging: along that axis).  The measures stay
drawn until cleared (Alt + click: the nearest one).  Its window: the selected part's size (width x depth x height), if
it fits the printer's build volume, Scale to Height; the measures listed.

Print Cut - drag a line across a part (Shift: horizontal / vertical / 45 degrees): it is cut there (a plane through the
line and the view) into two closed parts with connection pins across the cut - a peg on one part and a hole a
Clearance wider in the other (Peg), or holes in both and separate pins to print (Dowel).  Pins: Auto (two on each piece
of the cut where they fit, so it cannot turn) or 1 - 4; their size Auto (from the cut) or set.  The window also cuts
the selected part at its middle, horizontally or vertically.  The original is kept, hidden.

Lengths are shown in the window's unit (mm by default; 1 Blender unit = 1 m x the scene's Unit Scale).
"""
from __future__ import annotations

import json
import math

import bmesh
import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, PointerProperty, StringProperty
from mathutils import Matrix, Vector

UNITS = (('MM', 'mm', 'Millimetres'), ('CM', 'cm', 'Centimetres'), ('M', 'm', 'Metres'), ('IN', 'in', 'Inches'))
PER_M = {'MM': 1000.0, 'CM': 100.0, 'M': 1.0, 'IN': 1000.0 / 25.4}
MEASURE_KEY = 'mch_print_measures'
FROM_KEY = 'mch_print_from'            # on a cut part: the part it was cut from
PIN_KEY = 'mch_print_pin'              # on a separate (Dowel) pin
_LIVE = {'a': None, 'b': None, 'line': None}


# -----------------------------------------------------------------------------
# Units
# -----------------------------------------------------------------------------

def metres(context, v):
    """Blender units -> metres (the scene's Unit Scale)."""
    us = context.scene.unit_settings
    return float(v) * (us.scale_length if us.system != 'NONE' else 1.0)


def blender_units(context, m):
    us = context.scene.unit_settings
    return float(m) / (us.scale_length if us.system != 'NONE' and us.scale_length > 0 else 1.0)


def fmt(context, v, digits=None):
    """A length in Blender units as text in the window's unit."""
    pg = context.scene.mch_print
    x = metres(context, v) * PER_M[pg.unit]
    d = digits if digits is not None else (1 if pg.unit == 'MM' else 2 if pg.unit in {'CM', 'IN'} else 3)
    return f'{x:.{d}f} {dict((u[0], u[1]) for u in UNITS)[pg.unit]}'


# -----------------------------------------------------------------------------
# Measures
# -----------------------------------------------------------------------------

def components(a, b):
    """(length, horizontal, vertical) of the measure a -> b (world Z is up)."""
    d = Vector(b) - Vector(a)
    return d.length, math.hypot(d.x, d.y), abs(d.z)


def measures(scene):
    try:
        return [(Vector(m[:3]), Vector(m[3:6])) for m in json.loads(scene.get(MEASURE_KEY, '[]'))]
    except (TypeError, ValueError):
        return []


def add_measure(scene, a, b):
    ms = [list(a) + list(b) for a, b in measures(scene)]
    ms.append([float(x) for x in tuple(a) + tuple(b)])
    scene[MEASURE_KEY] = json.dumps(ms)


def clear_measures(scene):
    if MEASURE_KEY in scene:
        del scene[MEASURE_KEY]


def remove_nearest(context, xy, px=40.0):
    """The measure drawn nearest the screen point ``xy`` (within ``px``) removed.  True if one was."""
    from bpy_extras import view3d_utils
    region, rv3d = context.region, context.region_data
    best, k_best = px, None
    for k, (a, b) in enumerate(measures(context.scene)):
        sa = view3d_utils.location_3d_to_region_2d(region, rv3d, a)
        sb = view3d_utils.location_3d_to_region_2d(region, rv3d, b)
        if sa is None or sb is None:
            continue
        ab = sb - sa
        t = max(0.0, min(1.0, (Vector(xy) - sa).dot(ab) / max(ab.length_squared, 1e-9)))
        d = (sa + ab * t - Vector(xy)).length
        if d < best:
            best, k_best = d, k
    if k_best is None:
        return False
    ms = [list(a) + list(b) for a, b in measures(context.scene)]
    del ms[k_best]
    context.scene[MEASURE_KEY] = json.dumps(ms)
    return True


def constrain(a, b, lock):
    """``b`` held to the lock: 'H' level with a, 'V' straight above / below it, 'X' / 'Y' / 'Z' along that axis."""
    a, b = Vector(a), Vector(b)
    if lock == 'H':
        return Vector((b.x, b.y, a.z))
    if lock == 'V':
        return Vector((a.x, a.y, b.z))
    if lock in {'X', 'Y', 'Z'}:
        c = a.copy()
        i = 'XYZ'.index(lock)
        c[i] = b[i]
        return c
    return b


def surface_point(context, xy):
    """The model's surface under the screen point (or, off the model, the point at the 3D cursor's depth)."""
    from bpy_extras import view3d_utils
    from . import target_rules
    region, rv3d = context.region, context.region_data
    o = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
    d = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy)
    try:
        hit, loc, _n, _i, _ob, _m = target_rules.scene_ray(context, context.evaluated_depsgraph_get(), o, d)
    except (RuntimeError, TypeError):
        hit = False
    if hit:
        return Vector(loc)
    return view3d_utils.region_2d_to_location_3d(region, rv3d, xy, context.scene.cursor.location)


def _draw_overlay():
    """The kept measures, the one being dragged, the cut line being drawn (region pixels)."""
    context = bpy.context
    sc = getattr(context, 'scene', None)
    region, rv3d = getattr(context, 'region', None), getattr(context, 'region_data', None)
    if sc is None or region is None or rv3d is None or not hasattr(sc, 'mch_print'):
        return
    from bpy_extras import view3d_utils
    from . import ui_gpu as ug
    k = ug.ui_factor(context, region)
    items = list(measures(sc)) if sc.mch_print.show_measures else []
    if _LIVE['a'] is not None and _LIVE['b'] is not None:
        items.append((_LIVE['a'], _LIVE['b']))

    def scr(p):
        s = view3d_utils.location_3d_to_region_2d(region, rv3d, p)
        return (s.x, s.y) if s is not None else None

    def label(p, s, color):
        if p is None:
            return
        import blf
        size = int(12 * k)
        blf.size(0, size)
        w, _h = blf.dimensions(0, s)
        ug.rounded_rect(p[0] - w / 2 - 6 * k, p[1] - 10 * k, w + 12 * k, 20 * k, 6 * k, (0.06, 0.065, 0.075, 0.85))
        ug.text(p[0], p[1], s, size, color, align='CENTER')
    for a, b in items:
        c = Vector((b.x, b.y, a.z))
        sa, sb, sc_ = scr(a), scr(b), scr(c)
        if sa is None or sb is None:
            continue
        L, H, V = components(a, b)
        if sc_ is not None and H > 1e-9 and V > 1e-9:
            ug.lines([(sa, sc_)], (0.35, 0.8, 1.0, 0.8), 1.5 * k)          # (the horizontal leg)
            ug.lines([(sc_, sb)], (0.45, 1.0, 0.45, 0.8), 1.5 * k)         # (the vertical leg)
        ug.lines([(sa, sb)], ug.ORANGE, 2.5 * k)
        for p in (sa, sb):
            ug.polyline(ug.circle_pts(p[0], p[1], 4 * k, 12), ug.ORANGE, 2.0 * k, closed=True)
        mid = ((sa[0] + sb[0]) / 2, (sa[1] + sb[1]) / 2 + 16 * k)
        label(mid, f'L {fmt(context, L)}', ug.TEXT)
        if sc_ is not None and H > 1e-9 and V > 1e-9:
            label(((sa[0] + sc_[0]) / 2, (sa[1] + sc_[1]) / 2 - 16 * k), f'H {fmt(context, H)}', (0.55, 0.88, 1.0, 1.0))
            label(((sc_[0] + sb[0]) / 2 + 40 * k, (sc_[1] + sb[1]) / 2), f'V {fmt(context, V)}', (0.6, 1.0, 0.6, 1.0))
    if _LIVE['line'] is not None:
        pts = _LIVE['line']
        ug.lines(list(zip(pts, pts[1:])), (1.0, 0.3, 0.25, 1.0), 2.5 * k)


class MCH_OT_print_measure(bpy.types.Operator):
    """Drag on the model: the length and how much of it is horizontal / vertical.  Shift: straight horizontal or
    vertical; X / Y / Z: along that axis.  Alt + click: the nearest measure gone"""
    bl_idname = 'mch.print_measure'
    bl_label = 'Print Measure'
    bl_options = {'REGISTER', 'UNDO'}
    remove: BoolProperty(default=False, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        xy = (event.mouse_region_x, event.mouse_region_y)
        if self.remove:
            ok = remove_nearest(context, xy)
            context.area.tag_redraw()
            return {'FINISHED'} if ok else {'CANCELLED'}
        a = surface_point(context, xy)
        if a is None:
            return {'CANCELLED'}
        _LIVE['a'], _LIVE['b'] = a, a
        self.lock = None
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def _move(self, context, event):
        b = surface_point(context, (event.mouse_region_x, event.mouse_region_y))
        if b is None:
            return
        lock = self.lock
        if lock is None and event.shift:
            _L, H, V = components(_LIVE['a'], b)
            lock = 'V' if V > H else 'H'
        _LIVE['b'] = constrain(_LIVE['a'], b, lock)
        context.area.tag_redraw()

    def modal(self, context, event):
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE', 'LEFT_SHIFT', 'RIGHT_SHIFT'}:
            self._move(context, event)
            return {'RUNNING_MODAL'}
        if event.type in {'X', 'Y', 'Z'} and event.value == 'PRESS':
            self.lock = None if self.lock == event.type else event.type
            self._move(context, event)
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            a, b = _LIVE['a'], _LIVE['b']
            _LIVE['a'] = _LIVE['b'] = None
            context.area.tag_redraw()
            if a is None or b is None or (b - a).length < 1e-6:
                return {'CANCELLED'}
            add_measure(context.scene, a, b)
            L, H, V = components(a, b)
            self.report({'INFO'}, f'Length {fmt(context, L)}  (horizontal {fmt(context, H)}, vertical {fmt(context, V)})')
            return {'FINISHED'}
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            _LIVE['a'] = _LIVE['b'] = None
            context.area.tag_redraw()
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}


class MCH_OT_print_clear_measures(bpy.types.Operator):
    """Remove every measure"""
    bl_idname = 'mch.print_clear_measures'
    bl_label = 'Clear Measures'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        clear_measures(context.scene)
        for a in context.screen.areas if context.screen else ():
            a.tag_redraw()
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# Size
# -----------------------------------------------------------------------------

def world_bounds(context, obs):
    """(min, max) of the meshes as they are (modifiers on), in world space; None when there is nothing."""
    dg = context.evaluated_depsgraph_get()
    lo, hi = None, None
    for ob in obs:
        if ob.type != 'MESH':
            continue
        me = ob.evaluated_get(dg).data
        if not len(me.vertices):
            continue
        co = np.empty(len(me.vertices) * 3, np.float64)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        m = np.array(ob.matrix_world)
        w = co @ m[:3, :3].T + m[:3, 3]
        a, b = w.min(0), w.max(0)
        lo = a if lo is None else np.minimum(lo, a)
        hi = b if hi is None else np.maximum(hi, b)
    return None if lo is None else (Vector(lo), Vector(hi))


def size_of(context, obs):
    bb = world_bounds(context, obs)
    return None if bb is None else bb[1] - bb[0]


def fits(context, size):
    """(fits as it stands, fits turned 90 degrees on the bed) in the build volume."""
    pg = context.scene.mch_print
    vol = [blender_units(context, x / 1000.0) for x in (pg.build_x, pg.build_y, pg.build_z)]
    straight = size.x <= vol[0] and size.y <= vol[1] and size.z <= vol[2]
    turned = size.y <= vol[0] and size.x <= vol[1] and size.z <= vol[2]
    return straight, turned


def _selected_meshes(context):
    return [o for o in context.selected_objects if o.type == 'MESH']


class MCH_OT_print_scale_height(bpy.types.Operator):
    """Scale the selected parts together (from their bottom middle) so they are this tall"""
    bl_idname = 'mch.print_scale_height'
    bl_label = 'Scale to Height'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(_selected_meshes(context))

    def execute(self, context):
        obs = _selected_meshes(context)
        bb = world_bounds(context, obs)
        if bb is None or bb[1].z - bb[0].z < 1e-9:
            self.report({'WARNING'}, 'Nothing with a height selected')
            return {'CANCELLED'}
        pg = context.scene.mch_print
        want = blender_units(context, pg.fit_height / PER_M[pg.unit])
        f = want / (bb[1].z - bb[0].z)
        pivot = Vector(((bb[0].x + bb[1].x) / 2, (bb[0].y + bb[1].y) / 2, bb[0].z))
        m = Matrix.Translation(pivot) @ Matrix.Scale(f, 4) @ Matrix.Translation(-pivot)
        for o in obs:
            o.matrix_world = m @ o.matrix_world
        self.report({'INFO'}, f'Scaled x {f:.4f}: {fmt(context, want)} tall')
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# Cut with connection pins
# -----------------------------------------------------------------------------

class PrintError(Exception):
    pass


def _world_mesh(context, ob):
    """The part as it is (modifiers on) in world space: (verts n x 3, faces)."""
    dg = context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    me.transform(ob.matrix_world)
    return me


def _basis(n):
    n = Vector(n).normalized()
    u = n.orthogonal().normalized()
    return n, u, n.cross(u).normalized()


def section_loops(me, co, n):
    """The cut through mesh ``me`` by the plane (co, n): closed loops of world points."""
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-7, plane_co=co, plane_no=n)
        edges = [e for e in res['geom_cut'] if isinstance(e, bmesh.types.BMEdge)]
        nb = {}
        for e in edges:
            a, b = e.verts
            nb.setdefault(a, []).append(b)
            nb.setdefault(b, []).append(a)
        loops, seen = [], set()
        for start in list(nb):
            if start in seen:
                continue
            lp, prev, v = [], None, start
            while v is not None and v not in seen:
                seen.add(v)
                lp.append(v.co.copy())
                nxt = [w for w in nb[v] if w is not prev and w not in seen]
                prev, v = v, (nxt[0] if nxt else None)
            if len(lp) >= 3:
                loops.append(lp)
        return loops
    finally:
        bm.free()


def _half(me, co, n, keep_positive):
    """The part of mesh ``me`` on one side of the plane, its cut capped (a closed part when ``me`` is closed).
    Returns (mesh, closed?)."""
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-7, plane_co=co, plane_no=n,
                               clear_inner=keep_positive, clear_outer=not keep_positive)
        on = [e for e in bm.edges if e.is_boundary and all(abs((v.co - co).dot(n)) < 1e-5 for v in e.verts)]
        if on:
            bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=on, normal=n)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        closed = not any(e.is_boundary for e in bm.edges)
        out = bpy.data.meshes.new('MCH_PrintPart')
        bm.to_mesh(out)
        return out, closed
    finally:
        bm.free()


def _seg_dist(p, segs):
    a, b = segs[:, 0], segs[:, 1]
    ab = b - a
    t = np.clip(((p[:, None, :] - a) * ab).sum(2) / np.maximum((ab * ab).sum(1), 1e-18), 0.0, 1.0)
    q = a + ab * t[..., None]
    return np.sqrt(((p[:, None, :] - q) ** 2).sum(2)).min(1)


def _inside(px, py, loops):
    ins = np.zeros(len(px), bool)
    for lp in loops:
        n = len(lp)
        for i in range(n):
            x1, y1 = lp[i]
            x2, y2 = lp[(i + 1) % n]
            cross = (y1 > py) != (y2 > py)
            with np.errstate(divide='ignore', invalid='ignore'):
                xi = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            ins ^= cross & (px < xi)
    return ins


def islands(loops2d):
    """The cut's pieces: [(outer, [holes])] (2D)."""
    from . import core_geometry as cg
    return cg.organize_loops([[tuple(p) for p in lp] for lp in loops2d])


def depth_field(outer, holes, res=48):
    """Sample points inside a piece and their distance to its border: (points k x 2, distance k)."""
    lo = np.min(np.array(outer), 0)
    hi = np.max(np.array(outer), 0)
    step = max(float((hi - lo).max()) / res, 1e-9)
    xs = np.arange(lo[0] + step / 2, hi[0], step)
    ys = np.arange(lo[1] + step / 2, hi[1], step)
    gx, gy = np.meshgrid(xs, ys)
    px, py = gx.ravel(), gy.ravel()
    ins = _inside(px, py, [outer] + list(holes))
    pts = np.stack([px[ins], py[ins]], 1)
    if not len(pts):
        return pts, np.zeros(0)
    segs = []
    for lp in [outer] + list(holes):
        a = np.array(lp)
        segs.append(np.stack([a, np.roll(a, -1, 0)], 1))
    segs = np.concatenate(segs)
    d = np.concatenate([_seg_dist(pts[i:i + 2048], segs) for i in range(0, len(pts), 2048)])
    return pts, d


def place_pins(pieces, r, count, auto_n=2, owners=None):
    """Pin centres (2D) on each piece: as deep in it as can be, spread apart.  ``count`` 'AUTO' = ``auto_n`` where they
    fit (round pins: 2, so the parts cannot turn; a square key: 1), else fewer.  ``owners``: a list given gets each
    pin's piece index.  Returns ([(x, y)], pieces with no room)."""
    out, missed = [], 0
    need = r * 1.9                                   # (the hole and a wall round it)
    for pi, (outer, holes) in enumerate(pieces):
        pts, d = depth_field(outer, holes)
        ok = d >= need
        if not ok.any():
            missed += 1
            continue
        cand, cd = pts[ok], d[ok]
        want = auto_n if count == 'AUTO' else int(count)
        if want == 1:                                # (one: of the deepest places, the one nearest the middle)
            mid = np.asarray(outer, float).mean(0)
            near = cd >= cd.max() * 0.97
            chosen = [cand[near][int(np.argmin(np.linalg.norm(cand[near] - mid, axis=1)))]]
        else:
            chosen = [cand[int(np.argmax(cd))]]
        while len(chosen) < want:
            sep = np.min(np.linalg.norm(cand[:, None, :] - np.array(chosen)[None], axis=2), 1)
            good = sep >= r * 3.5
            if not good.any():
                break
            score = np.where(good, sep + 0.6 * cd, -1.0)
            chosen.append(cand[int(np.argmax(score))])
        out.extend(tuple(c) for c in chosen)
        if owners is not None:
            owners.extend([pi] * len(chosen))
    return out, missed


def _cylinder(c, n, r, z0, z1, chamfer0=0.0, chamfer1=0.0, segs=32):
    """A closed cylinder along ``n`` from c + n z0 to c + n z1, radius r, its ends chamfered by chamfer0 / chamfer1."""
    rings = [(z0, r - chamfer0)] if chamfer0 > 0 else []
    rings += [(z0 + chamfer0, r), (z1 - chamfer1, r)]
    rings += [(z1, r - chamfer1)] if chamfer1 > 0 else []
    return _solid(c, n, rings, segs)


def _solid(c, n, rings, segs=32, axis=None):
    """A closed solid along ``n`` through ``rings`` [(z, size)]: round (``segs`` sides, size = radius), or - ``segs`` 4 -
    a square, size = its half width, one side along ``axis``."""
    n, u, w = _basis(n)
    if axis is not None:
        a = Vector(axis) - n * Vector(axis).dot(n)
        if a.length > 1e-9:
            u = a.normalized()
            w = n.cross(u)
    square = segs == 4
    verts, faces = [], []
    for z, rr in rings:
        for k in range(segs):
            a = 2 * math.pi * k / segs + (math.pi / 4 if square else 0.0)
            rad = rr * (math.sqrt(2.0) if square else 1.0)                  # (a square's corner)
            verts.append(Vector(c) + n * z + (u * math.cos(a) + w * math.sin(a)) * rad)
    for i in range(len(rings) - 1):
        for k in range(segs):
            k2 = (k + 1) % segs
            faces.append([i * segs + k, i * segs + k2, (i + 1) * segs + k2, (i + 1) * segs + k])
    faces.append(list(reversed(range(segs))))
    last = (len(rings) - 1) * segs
    faces.append([last + k for k in range(segs)])
    return verts, faces


def _mesh(name, parts):
    verts, faces = [], []
    for vs, fs in parts:
        o = len(verts)
        verts += [tuple(v) for v in vs]
        faces += [[o + i for i in f] for f in fs]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    return me


def _boolean(context, ob, cutter_me, op):
    """``ob``'s mesh with ``cutter_me`` added / taken out (Exact)."""
    from . import core_geometry as cg
    cutter = cg.link_temp_object(context, cutter_me, 'MCH_PrintPin_TEMP')
    try:
        mod = ob.modifiers.new('MCH_PrintPin', 'BOOLEAN')
        mod.operation = op
        mod.solver = 'EXACT'
        mod.object = cutter
        try:
            dg = context.evaluated_depsgraph_get()
            me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
        finally:
            ob.modifiers.remove(mod)
        old = ob.data
        ob.data = me
        if not len(me.materials):                    # (the evaluated copy keeps them already)
            for m in old.materials:
                me.materials.append(m)
        if old.users == 0:
            bpy.data.meshes.remove(old)
    finally:
        cg.remove_object_and_mesh(cutter)


def _set_origin(ob):
    """The part's origin to the middle of its bounds (it was made in world space)."""
    me = ob.data
    if not len(me.vertices):
        return
    co = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    c = (co.min(0) + co.max(0)) / 2
    me.transform(Matrix.Translation(Vector(-c)))
    ob.location = Vector(c)


KEY_TAPER = 0.15            # 0.24.165 a square key 15 % narrower at its tip than at the cut (it finds its socket)


def pin_size(context, pieces):
    """(radius - a Key: half its width -, length out of the cut) for the pins: set in the window, or Auto from the cut
    (the deepest point's depth from the cut's border: round pins x 0.25, 1.5 - 8 mm across, twice as long; a key
    x 0.3, 2 - 15 mm wide, 1.2 x as long)."""
    deep = 0.0
    for outer, holes in pieces:
        _p, d = depth_field(outer, holes, 32)
        if len(d):
            deep = max(deep, float(d.max()))
    return size_from_deep(context, deep)


def size_from_deep(context, deep):
    """(radius / a key's half width, length out of the cut) from the cut's depth (its deepest point's distance from
    its border) - or the window's values (Auto Size off)."""
    pg = context.scene.mch_print
    if not pg.pin_auto:
        return blender_units(context, pg.pin_diameter / 2000.0), blender_units(context, pg.pin_length / 1000.0)
    if pg.pin_style == 'KEY':
        r = max(min(deep * 0.3, blender_units(context, 0.0075)), blender_units(context, 0.001))
        return r, r * 2.4
    r = min(deep * 0.25, blender_units(context, 0.004))               # (8 mm across at most)
    r = max(r, blender_units(context, 0.00075))                       # (1.5 mm at least)
    return r, r * 4.0


def piece_axis(outer):
    """The long way of a piece of the cut (2D, unit): its outline's main axis - a key lies along it."""
    pts = np.asarray(outer, float)
    if len(pts) < 3:
        return (1.0, 0.0)
    q = pts - pts.mean(0)
    vals, vecs = np.linalg.eigh(q.T @ q)
    a = vecs[:, int(np.argmax(vals))]
    return (float(a[0]), float(a[1]))


def _connect(context, a, b, world, normals, axes, r, length, tol, style, name, coll):
    """The connectors at ``world`` (normals from ``a`` into ``b``): Key - a square key on ``a`` (its big end on a's
    mesh, narrowing into b, the tip chamfered) and a square socket a Clearance (the fit gap) wider all round and
    deeper in ``b``; Peg - a peg on a, a hole in b; Dowel - holes in both, separate pins (returned)."""
    pins = []
    if not world:
        return pins
    ch = min(r * 0.3, length * 0.2)
    if style == 'KEY':
        # 0.24.165 (user, with photos of a Dovetail Key add-on: "레퍼런스로 준 거 참고해서"); 0.24.166 ("핀 몸통이 큰 쪽이
        # 메쉬에 붙는 거야 ... 갭이 무조건 있어야"): the big end on a's mesh, the socket a gap wider all round
        tip = r * (1.0 - KEY_TAPER)
        ch = min(r * 0.25, length * 0.2)
        embed = min(r * 1.5, length)
        at = r + (tip - r) * (length - ch) / length
        keys = _mesh('MCH_Keys', [_solid(c, n, [(-embed, r), (0.0, r), (length - ch, at), (length, at - ch * 0.7)], 4, x)
                                  for c, n, x in zip(world, normals, axes)])
        sockets = _mesh('MCH_Sockets', [_solid(c, n, [(-r * 0.05, r + tol), (0.0, r + tol), (length + tol, tip + tol)], 4, x)
                                        for c, n, x in zip(world, normals, axes)])
        _boolean(context, a, keys, 'UNION')
        _boolean(context, b, sockets, 'DIFFERENCE')
    elif style == 'PEG':
        embed = min(r * 1.5, length)
        pegs = _mesh('MCH_Pegs', [_cylinder(c, n, r, -embed, length, 0.0, ch) for c, n in zip(world, normals)])
        holes = _mesh('MCH_Holes', [_cylinder(c, n, r + tol, -r * 0.05, length + tol) for c, n in zip(world, normals)])
        _boolean(context, a, pegs, 'UNION')
        _boolean(context, b, holes, 'DIFFERENCE')
    else:
        half = length * 0.5
        _boolean(context, a, _mesh('MCH_Holes', [_cylinder(c, n, r + tol, -(half + tol), r * 0.05)
                                                 for c, n in zip(world, normals)]), 'DIFFERENCE')
        _boolean(context, b, _mesh('MCH_Holes', [_cylinder(c, n, r + tol, -r * 0.05, half + tol)
                                                 for c, n in zip(world, normals)]), 'DIFFERENCE')
        for k, (c, n) in enumerate(zip(world, normals)):
            pm = _mesh(f'{name}.Pin{k + 1}', [_cylinder(c, n, r, -half + tol * 0.5, half - tol * 0.5, ch, ch)])
            pin = bpy.data.objects.new(pm.name, pm)
            coll.objects.link(pin)
            pin[PIN_KEY] = name
            pins.append(pin)
    return pins


def cut_with_pins(context, ob, co, n, pg=None):
    """Cut part ``ob`` by the plane (co, n) (world space) into two closed parts with connection pins across the cut.
    Returns (part below, part above, separate pins, report).  Raises PrintError."""
    pg = pg or context.scene.mch_print
    co, n = Vector(co), Vector(n).normalized()
    me = _world_mesh(context, ob)
    try:
        loops = section_loops(me, co, n)
        if not loops:
            raise PrintError(f'The cut misses "{ob.name}"')
        n, u, w = _basis(n)
        loops2d = [[((p - co).dot(u), (p - co).dot(w)) for p in lp] for lp in loops]
        pieces = islands(loops2d)
        r, length = pin_size(context, pieces)
        tol = blender_units(context, pg.clearance / 1000.0)
        key = pg.pin_style == 'KEY'
        owners = []
        centres, missed = place_pins(pieces, (r + tol) * (math.sqrt(2.0) if key else 1.0), pg.pin_count,
                                     1 if key else 2, owners)       # (a square key cannot turn: one is enough)
        axes = [piece_axis(pieces[o][0]) for o in owners]
        neg_me, c1 = _half(me, co, n, False)
        pos_me, c2 = _half(me, co, n, True)
    finally:
        bpy.data.meshes.remove(me)
    if not len(neg_me.vertices) or not len(pos_me.vertices):
        for m in (neg_me, pos_me):
            bpy.data.meshes.remove(m)
        raise PrintError(f'The cut does not go through "{ob.name}"')
    coll = ob.users_collection[0] if ob.users_collection else context.scene.collection
    parts = []
    for tag, m in (('A', neg_me), ('B', pos_me)):
        m.name = f'{ob.name}.{tag}'
        part = bpy.data.objects.new(m.name, m)
        coll.objects.link(part)
        for mat in ob.data.materials if ob.type == 'MESH' else ():
            m.materials.append(mat)
        part[FROM_KEY] = ob.name
        parts.append(part)
    neg, pos = parts
    world = [(co + u * x + w * y) for x, y in centres]
    world_axes = [(u * ax + w * ay) for ax, ay in axes]
    pins = _connect(context, neg, pos, world, [n] * len(world), world_axes, r, length, tol, pg.pin_style, ob.name, coll)
    info = json.dumps({'pins': [list(c) for c in world], 'normal': list(n), 'radius': r, 'length': length,
                       'clearance': tol, 'style': pg.pin_style, 'axes': [list(a) for a in world_axes]})
    for o in parts:
        o['mch_print_pins'] = info                    # (where the pins went - world space at the cut)
    for o in parts + pins:
        _set_origin(o)
    if pg.gap > 0:
        pos.location += n * blender_units(context, pg.gap / 1000.0)
    ob.hide_set(True)
    ob.hide_render = True
    for o in context.selected_objects:
        o.select_set(False)
    for o in parts + pins:
        o.select_set(True)
    context.view_layer.objects.active = pos
    style = {'PEG': 'peg + hole', 'DOWEL': 'dowel pins to print', 'KEY': 'square key + socket'}[pg.pin_style]
    what = 'key' if key else 'pin'
    msg = (f'Cut "{ob.name}" into 2 parts with {len(centres)} {what}{"s" if len(centres) != 1 else ""} ({style}, '
           f'{fmt(context, r * 2)} wide, {fmt(context, length)} long, {fmt(context, tol)} clearance)')
    if missed:
        msg += f'; {missed} piece{"s" if missed > 1 else ""} of the cut too thin for a {what}'
    if not (c1 and c2):
        msg += '; the part was not closed - check the cut faces'
    return neg, pos, pins, msg


def shared_faces(context, a, b):
    """0.24.166 The faces of ``a`` lying on ``b``'s surface, facing it (the cut both share after any Split - a straight
    one, a drawn line, a lasso): (a's world mesh (bmesh), [face lists of each connected piece]).  The caller frees the
    bmesh."""
    from mathutils.bvhtree import BVHTree
    ma, mb = _world_mesh(context, a), _world_mesh(context, b)
    try:
        bma, bmb = bmesh.new(), bmesh.new()
        bma.from_mesh(ma)
        bmb.from_mesh(mb)
    finally:
        bpy.data.meshes.remove(ma)
        bpy.data.meshes.remove(mb)
    bmesh.ops.triangulate(bmb, faces=bmb.faces[:])
    tree = BVHTree.FromBMesh(bmb)
    co = np.array([v.co for v in bma.verts]) if bma.verts else np.zeros((0, 3))
    size = float(np.linalg.norm(co.max(0) - co.min(0))) if len(co) else 1.0
    tol = max(size * 2e-5, 1e-7)
    on = set()
    for f in bma.faces:
        if f.calc_area() < 1e-14:
            continue
        hit = tree.find_nearest(f.calc_center_median(), tol * 4)
        if hit[0] is None or hit[3] > tol:
            continue
        if hit[1].dot(f.normal) > -0.9:
            continue
        if all(tree.find_nearest(v.co, tol * 4)[0] is not None for v in f.verts):
            on.add(f.index)
    bmb.free()
    bma.faces.ensure_lookup_table()
    pieces, seen = [], set()
    for fi in sorted(on):
        if fi in seen:
            continue
        stack, piece = [fi], []
        seen.add(fi)
        while stack:
            f = bma.faces[stack.pop()]
            piece.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index in on and g.index not in seen:
                        seen.add(g.index)
                        stack.append(g.index)
        pieces.append(piece)
    return bma, pieces


def _piece_spots(piece, n_samples=1600, seed=1):
    """Points over a piece of the shared cut (by area), each with its depth (distance to the piece's border) and its
    face normal; the border points; the piece's mean normal."""
    import random as _rnd
    from mathutils.kdtree import KDTree
    ids = {f.index for f in piece}
    area = sum(f.calc_area() for f in piece)
    border = []
    step = max(math.sqrt(max(area, 1e-18)) / 80.0, 1e-9)
    for f in piece:
        for e in f.edges:
            on = [g for g in e.link_faces if g.index in ids]
            crease = len(on) == 2 and on[0].normal.dot(on[1].normal) < math.cos(math.radians(15.0))
            if len(on) == 1 or crease:               # (the border - and a sharp bend of the cut: a key not over it)
                a_, b_ = e.verts[0].co, e.verts[1].co
                k = max(1, int((b_ - a_).length / step))
                border.extend(a_.lerp(b_, t / k) for t in range(k))
    if not border:
        return None
    kd = KDTree(len(border))
    for i, p_ in enumerate(border):
        kd.insert(p_, i)
    kd.balance()
    rng = _rnd.Random(seed)
    pts, nrm, dep = [], [], []
    for f in piece:
        want = max(1, int(round(n_samples * f.calc_area() / max(area, 1e-18))))
        vs = [v.co for v in f.verts]
        for _k in range(want):
            t = rng.randrange(len(vs) - 2) + 1 if len(vs) > 3 else 1          # (a fan triangle of the face)
            u_, v_ = rng.random(), rng.random()
            if u_ + v_ > 1.0:
                u_, v_ = 1.0 - u_, 1.0 - v_
            p_ = vs[0] + (vs[t] - vs[0]) * u_ + (vs[t + 1] - vs[0]) * v_
            pts.append(p_)
            nrm.append(f.normal.copy())
            dep.append(kd.find(p_)[2])
    mean = sum((f.normal * f.calc_area() for f in piece), Vector())
    return (np.array([tuple(p_) for p_ in pts]), np.array([tuple(n_) for n_ in nrm]), np.array(dep),
            np.array([tuple(p_) for p_ in border]), mean.normalized() if mean.length > 1e-12 else Vector((0, 0, 1)))


def keys_between(context, a, b, pg=None, report_name=None):
    """0.24.166 (user: "우리 저번에 만들었던 메쉬 따라서 할 수 있는 스플릿으로 ... 같이 해서"): connectors across the cut
    two parts share - whatever made it (Split's lasso, a drawn line, a straight cut): on each piece of the shared cut,
    as deep in it as can be, along its face there; Key / Peg on ``a`` (its big end on a's mesh) into ``b`` with the fit
    gap (Clearance) all round, Dowel - holes in both + separate pins.  Returns (pins, report).  Raises PrintError."""
    pg = pg or context.scene.mch_print
    bma, pieces = shared_faces(context, a, b)
    try:
        if not pieces:
            raise PrintError(f'"{a.name}" and "{b.name}" do not touch along a cut (split them with a thin cut, '
                             'not Gap)')
        data = [d for d in (_piece_spots(pc) for pc in pieces) if d is not None]
        tot = sum(f.calc_area() for pc in pieces for f in pc)
        flow = sum((f.normal * f.calc_area() for pc in pieces for f in pc), Vector())
    finally:
        bma.free()
    # the way the two parts come apart: every key along it (a key along its own spot's face on a bent cut would
    # lock the parts); the cut's faces mostly facing one way - else (a plug in its hole) each along its face
    pull = flow / max(tot, 1e-18)
    one_way = pull.length >= 0.6
    pull = pull.normalized() if pull.length > 1e-12 else Vector((0.0, 0.0, 1.0))
    across = math.cos(math.radians(60.0))       # (a face up to 60 degrees off the pull still takes a key)
    if not data:
        raise PrintError('No cut faces found between the two parts')
    deep = max(float(d[2].max()) for d in data)
    r, length = size_from_deep(context, deep)
    tol = blender_units(context, pg.clearance / 1000.0)
    key = pg.pin_style == 'KEY'
    need = (r + tol) * (math.sqrt(2.0) if key else 1.0) * 1.9
    want_n = (1 if key else 2) if pg.pin_count == 'AUTO' else int(pg.pin_count)
    world, normals, axes, missed = [], [], [], 0
    for pts, nrm, dep, border, mean in data:
        ok = dep >= need
        if one_way:                                   # (on a face across the pull, not on a side wall)
            ok &= (nrm @ np.asarray(pull)) >= across
        if not ok.any():
            missed += 1
            continue
        cand, cd, cn = pts[ok], dep[ok], nrm[ok]
        if want_n == 1:
            near = cd >= cd.max() * 0.97
            mid = pts.mean(0)
            pick = [np.flatnonzero(near)[int(np.argmin(np.linalg.norm(cand[near] - mid, axis=1)))]]
        else:
            pick = [int(np.argmax(cd))]
        while len(pick) < want_n:
            sep = np.min(np.linalg.norm(cand[:, None, :] - cand[pick][None], axis=2), 1)
            good = sep >= (r + tol) * 3.5
            if not good.any():
                break
            pick.append(int(np.argmax(np.where(good, sep + 0.6 * cd, -1.0))))
        for i in pick:
            c = Vector(cand[i])
            close = np.linalg.norm(pts - cand[i], axis=1) < max(r * 2.0, 1e-9)
            nv = Vector(nrm[close].sum(0)) if close.any() else Vector(cn[i])     # (the cut's face round it)
            nv = nv.normalized() if nv.length > 1e-12 else mean
            if one_way:
                nv = pull.copy()
            q = border - np.asarray(c)
            q = q - np.outer(q @ np.asarray(nv), np.asarray(nv))
            vals, vecs = np.linalg.eigh(q.T @ q)
            world.append(c)
            normals.append(nv)
            axes.append(Vector(vecs[:, int(np.argmax(vals))]))
    coll = a.users_collection[0] if a.users_collection else context.scene.collection
    pins = _connect(context, a, b, world, normals, axes, r, length, tol, pg.pin_style, report_name or a.name, coll)
    info = json.dumps({'pins': [list(c) for c in world], 'normal': list(normals[0]) if normals else [0, 0, 1],
                       'normals': [list(n_) for n_ in normals], 'radius': r, 'length': length, 'clearance': tol,
                       'style': pg.pin_style, 'axes': [list(x) for x in axes], 'on': a.name, 'pull': list(pull),
                       'one_way': one_way})
    for o in (a, b):
        o['mch_print_pins'] = info
    style = {'PEG': 'peg + hole', 'DOWEL': 'dowel pins to print', 'KEY': 'square key + socket'}[pg.pin_style]
    what = 'key' if key else 'pin'
    msg = (f'{len(world)} {what}{"s" if len(world) != 1 else ""} between "{a.name}" and "{b.name}" ({style}, '
           f'{fmt(context, r * 2)} wide, {fmt(context, length)} long, {fmt(context, tol)} gap all round)')
    if missed:
        msg += f'; {missed} piece{"s" if missed > 1 else ""} of the cut too thin for a {what}'
    if not one_way:
        msg += ('; the cut wraps round (a plug in its hole): each key along its face there - check the parts can '
                'go together')
    return pins, msg


def _volume(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    v = abs(bm.calc_volume())
    bm.free()
    s_ = ob.matrix_world.to_scale()
    return v * abs(s_.x * s_.y * s_.z)


def key_carrier(a, b):
    """(the part the keys stand on, the part with the sockets): the smaller part carries them (like the reference's
    arm - its keys go into the body)."""
    return (a, b) if _volume(a) <= _volume(b) else (b, a)


SPLIT_FORCE = dict(split_mode='NORMAL', depth_mode='THROUGH', side_a_finish='NONE', side_b_finish='NONE',
                   split_cap=True, line_cap=True, gn_finish='NONE')   # (a thin, filled, plain cut: the parts touch)


def split_along_line(context, ob, path, projector):
    """0.24.166 (user: "메쉬 따라서 할 수 있는 스플릿으로"): ``ob`` split along a line drawn across it on the screen -
    the Split tool's line (the cut follows the drawn line through the part along the view), into two closed parts
    that touch along the cut.  The original is kept, hidden.  Returns (part A, part B)."""
    from . import core_geometry as cg, cut_engine as ce
    cut = context.scene.mch_cut
    st = getattr(context.scene, 'mch_settings', None)
    saved = {k: getattr(cut, k) for k in SPLIT_FORCE if hasattr(cut, k)}
    saved_apply = getattr(st, 'auto_apply', True) if st is not None else True
    dup = ob.copy()
    dup.data = ob.data.copy()
    for coll in ob.users_collection or (context.scene.collection,):
        coll.objects.link(dup)
    dup.name = ob.name + '.A'
    before = set(bpy.data.objects)
    try:
        for k, v in SPLIT_FORCE.items():
            if k in saved:
                setattr(cut, k, v)
        if st is not None:
            st.auto_apply = True
        try:
            ce.perform_line(context, 'SPLIT', [dup], [tuple(p_) for p_ in path], projector, tuple(path[0]))
        except cg.CutError as ex:
            raise PrintError(str(ex))
    except PrintError:
        bpy.data.objects.remove(dup)
        raise
    finally:
        for k, v in saved.items():
            setattr(cut, k, v)
        if st is not None:
            st.auto_apply = saved_apply
    made = [o for o in bpy.data.objects if o not in before and o.type == 'MESH' and o.name in bpy.data.objects]
    piece = next((o for o in made if o.name.startswith(dup.name)), made[0] if made else None)
    if piece is None:
        bpy.data.objects.remove(dup)
        raise PrintError(f'The line does not split "{ob.name}" in two')
    piece.name = ob.name + '.B'
    for o in (dup, piece):
        o[FROM_KEY] = ob.name
    ob.hide_set(True)
    ob.hide_render = True
    return dup, piece


def cut_along_line(context, ob, path, projector, pg=None):
    """The Print Cut drag: split along the drawn line, then keys / pins across the cut (on the smaller part, into
    the bigger).  Returns (part A, part B, separate pins, report)."""
    pg = pg or context.scene.mch_print
    a, b = split_along_line(context, ob, path, projector)
    carrier, other = key_carrier(a, b)
    try:
        pins, msg = keys_between(context, carrier, other, pg, ob.name)
    except PrintError as ex:
        pins, msg = [], f'Split "{ob.name}" in two - no keys: {ex}'
    if pg.gap > 0:
        info = json.loads(other.get('mch_print_pins', '{}') or '{}')
        n_ = Vector(info.get('normal', (0, 0, 1)))
        other.location += n_ * blender_units(context, pg.gap / 1000.0)
    for o in context.selected_objects:
        o.select_set(False)
    for o in (a, b, *pins):
        o.select_set(True)
    context.view_layer.objects.active = b
    return a, b, pins, f'Split "{ob.name}" along the line: ' + msg


class MCH_OT_print_keys(bpy.types.Operator):
    """Keys (or pins) across the cut two selected parts share - parts from any Split (a lasso, a line), touching
    along the cut: the smaller part gets the keys, the bigger the sockets (a fit gap all round)"""
    bl_idname = 'mch.print_keys'
    bl_label = 'Keys Between 2 Parts'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and len(_selected_meshes(context)) == 2

    def execute(self, context):
        a, b = key_carrier(*_selected_meshes(context))
        try:
            _pins, msg = keys_between(context, a, b)
        except PrintError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


def plane_from_line(context, p0, p1, depth_point):
    """The plane through the screen line p0 - p1 and the view (world): (point, normal)."""
    from bpy_extras import view3d_utils
    region, rv3d = context.region, context.region_data
    a = view3d_utils.region_2d_to_location_3d(region, rv3d, p0, depth_point)
    b = view3d_utils.region_2d_to_location_3d(region, rv3d, p1, depth_point)
    mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
    d = view3d_utils.region_2d_to_vector_3d(region, rv3d, mid)
    nrm = (b - a).cross(d)
    if nrm.length < 1e-12:
        return None
    return (a + b) / 2, nrm.normalized()


def _bends(path, px=6.0):
    """A drawn path that is not a straight line (some point more than ``px`` off the line from its start to its end)."""
    if len(path) < 3:
        return False
    a, b = np.asarray(path[0], float), np.asarray(path[-1], float)
    d = b - a
    ln = float(np.hypot(*d))
    if ln < 1e-9:
        return False
    q = np.asarray(path, float) - a
    return float(np.abs(q[:, 0] * d[1] - q[:, 1] * d[0]).max() / ln) > px


def _simplify(path, px=2.5):
    """The drawn path with its points closer than a few pixels to the line through their neighbours dropped."""
    from . import core_geometry as cg
    try:
        out = cg.simplify_open([tuple(p_) for p_ in path], px)
        if out and len(out) >= 2:
            return out
    except (AttributeError, TypeError, ValueError):
        pass
    keep = [path[0]]
    for p_ in path[1:-1]:
        if math.dist(p_, keep[-1]) >= 6.0:
            keep.append(p_)
    return keep + [path[-1]]


def _part_under_line(context, p0, p1, path=None):
    """The mesh the line (or the drawn ``path``) crosses most (the active one if it is crossed)."""
    from bpy_extras import view3d_utils
    from . import target_rules
    region, rv3d = context.region, context.region_data
    dg = context.evaluated_depsgraph_get()
    counts = {}
    if path and len(path) > 2:
        idx = np.linspace(0, len(path) - 1, 25)
        spots = [tuple(np.asarray(path[int(i)], float)) for i in idx]
    else:
        spots = [(p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t) for t in np.linspace(0.0, 1.0, 25)]
    for xy in spots:
        o = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
        d = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy)
        try:
            hit, _l, _n, _i, hob, _m = target_rules.scene_ray(context, dg, o, d)
        except (RuntimeError, TypeError):
            continue
        if hit and hob is not None:
            real = bpy.data.objects.get(hob.name)
            if real is not None and real.type == 'MESH' and not real.get(PIN_KEY):
                counts[real.name] = counts.get(real.name, 0) + 1
    act = context.active_object
    if act is not None and act.name in counts:
        return act
    return bpy.data.objects[max(counts, key=counts.get)] if counts else None


def _snap_line(p0, p1):
    """Shift: the line straight - horizontal, vertical or 45 degrees on screen."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    ang = round(math.atan2(dy, dx) / (math.pi / 4)) * (math.pi / 4)
    L = math.hypot(dx, dy)
    return (p0[0] + L * math.cos(ang), p0[1] + L * math.sin(ang))


class MCH_OT_print_cut(bpy.types.Operator):
    """Drag a line across a part: it is split along the line you draw (like Split's line, following it through the
    part) into two closed parts, keys / pins across the cut.  Shift: a straight line (horizontal / vertical / 45)"""
    bl_idname = 'mch.print_cut'
    bl_label = 'Print Cut'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'

    def invoke(self, context, event):
        self.p0 = (event.mouse_region_x, event.mouse_region_y)
        self.path = [self.p0]
        self.straight = bool(event.shift)
        _LIVE['line'] = [self.p0, self.p0]
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        xy = (event.mouse_region_x, event.mouse_region_y)
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE', 'LEFT_SHIFT', 'RIGHT_SHIFT'}:
            self.straight = self.straight or event.shift
            if self.straight:                     # (Shift: a straight line, snapped)
                _LIVE['line'] = [self.p0, _snap_line(self.p0, xy) if event.shift else xy]
            else:                                 # (0.24.166 the line as drawn: Split's line)
                if math.dist(self.path[-1], xy) >= 4.0:
                    self.path.append(xy)
                _LIVE['line'] = self.path + [xy]
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            path = list(_LIVE['line'] or [])
            _LIVE['line'] = None
            context.area.tag_redraw()
            if len(path) < 2 or math.dist(path[0], path[-1]) < 8:
                return {'CANCELLED'}
            p0, p1 = path[0], path[-1]
            ob = _part_under_line(context, p0, p1, path)
            if ob is None:
                self.report({'WARNING'}, 'Draw the line across a part')
                return {'CANCELLED'}
            if not self.straight and _bends(path):
                from . import cut_engine as ce
                try:
                    *_r, msg = cut_along_line(context, ob, _simplify(path), ce.make_projector(context.region,
                                                                                             context.region_data))
                except PrintError as ex:
                    self.report({'WARNING'}, str(ex))
                    return {'CANCELLED'}
                self.report({'INFO'}, msg)
                return {'FINISHED'}
            bb = world_bounds(context, [ob])
            plane = plane_from_line(context, p0, p1, (bb[0] + bb[1]) / 2 if bb else ob.matrix_world.translation)
            if plane is None:
                return {'CANCELLED'}
            try:
                *_r, msg = cut_with_pins(context, ob, plane[0], plane[1])
            except PrintError as ex:
                self.report({'WARNING'}, str(ex))
                return {'CANCELLED'}
            self.report({'INFO'}, msg)
            return {'FINISHED'}
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            _LIVE['line'] = None
            context.area.tag_redraw()
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}


class MCH_OT_print_cut_axis(bpy.types.Operator):
    """Cut the selected part through its middle, with connection pins"""
    bl_idname = 'mch.print_cut_axis'
    bl_label = 'Cut Through the Middle'
    bl_options = {'REGISTER', 'UNDO'}
    axis: EnumProperty(items=(('Z', 'Horizontal', 'A horizontal cut (across Z) through the middle'),
                              ('X', 'Vertical X', 'A vertical cut across X through the middle'),
                              ('Y', 'Vertical Y', 'A vertical cut across Y through the middle')))

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.type == 'MESH' and context.mode == 'OBJECT'

    def execute(self, context):
        ob = context.active_object
        bb = world_bounds(context, [ob])
        if bb is None:
            return {'CANCELLED'}
        n = Vector({'X': (1, 0, 0), 'Y': (0, 1, 0), 'Z': (0, 0, 1)}[self.axis])
        try:
            *_r, msg = cut_with_pins(context, ob, (bb[0] + bb[1]) / 2, n)
        except PrintError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# Settings, window
# -----------------------------------------------------------------------------

def _redraw(self, context):
    for a in context.screen.areas if getattr(context, 'screen', None) else ():
        if a.type == 'VIEW_3D':
            a.tag_redraw()


class MCH_PG_Print(bpy.types.PropertyGroup):
    unit: EnumProperty(name='Unit', items=UNITS, default='MM', update=_redraw)
    show_measures: BoolProperty(name='Show Measures', default=True, update=_redraw)
    build_x: FloatProperty(name='Bed X', default=220.0, min=1.0, soft_max=1000.0, description='Build volume width (mm)')
    build_y: FloatProperty(name='Bed Y', default=220.0, min=1.0, soft_max=1000.0, description='Build volume depth (mm)')
    build_z: FloatProperty(name='Height', default=250.0, min=1.0, soft_max=1000.0, description='Build volume height (mm)')
    fit_height: FloatProperty(name='Height', default=150.0, min=0.0001, soft_max=1000.0,
                              description='Scale to Height: the height the selected parts get (in the unit above)')
    pin_style: EnumProperty(name='Pins', items=(
        ('PEG', 'Peg', 'A peg on one part, a hole (a Clearance wider) in the other'),
        ('DOWEL', 'Dowel', 'Holes in both parts and separate pins to print'),
        ('KEY', 'Key', 'A square key (narrowing to its tip, like a dovetail key) on one part, a square socket a '
                       'Clearance wider in the other - square, so one is enough to stop it turning')), default='PEG')
    pin_count: EnumProperty(name='Count', items=(
        ('AUTO', 'Auto', 'Round pins: two on each piece of the cut where they fit (it cannot turn), else one; a key: '
                         'one on each piece'),
        ('1', '1', ''), ('2', '2', ''), ('3', '3', ''), ('4', '4', '')), default='AUTO')
    pin_auto: BoolProperty(name='Auto Size', default=True, description='Pin size from the cut (else the values below)')
    # (in mm - what a printer is set up in; the side panel shows a length in metres with 3 decimals: 0.2 mm read 0.000)
    pin_diameter: FloatProperty(name='Diameter (mm)', default=5.0, min=0.1, soft_max=30.0, precision=2)
    pin_length: FloatProperty(name='Length (mm)', default=8.0, min=0.1, soft_max=60.0, precision=2,
                              description='Peg: how far it goes into the other part; Dowel: the whole pin')
    clearance: FloatProperty(name='Fit Gap (mm)', default=0.2, min=0.0, soft_max=1.0, precision=2,
                             description='The gap all round between a key / pin and its socket - a print needs it to '
                                         'fit (the socket is twice this wider and this deeper; 0.2 mm: snug on most '
                                         'FDM printers, 0.1 - 0.15 on resin)')
    gap: FloatProperty(name='Move Apart (mm)', default=0.0, min=0.0, soft_max=100.0, precision=1,
                       description='Move the upper part off this much after the cut (to see the pins)')


def draw_measure(layout, context):
    pg = context.scene.mch_print
    row = layout.row(align=True)
    row.prop(pg, 'unit', expand=True)
    box = layout.box()
    obs = _selected_meshes(context)
    sz = size_of(context, obs) if obs else None
    if sz is None:
        box.label(text='Select a part to see its size', icon='INFO')
    else:
        box.label(text=f'Size ({len(obs)} part{"s" if len(obs) > 1 else ""})', icon='FULLSCREEN_ENTER')
        col = box.column(align=True)
        col.label(text=f'Width (X)   {fmt(context, sz.x)}')
        col.label(text=f'Depth (Y)   {fmt(context, sz.y)}')
        col.label(text=f'Height (Z)  {fmt(context, sz.z)}')
        straight, turned = fits(context, sz)
        box.label(text='Fits the printer' if straight else 'Fits turned 90 degrees' if turned
                  else 'Too big for the printer - cut it (Print Cut) or scale it',
                  icon='CHECKMARK' if (straight or turned) else 'ERROR')
    col = layout.column(align=True)
    col.label(text='Printer (mm)')
    row = col.row(align=True)
    row.prop(pg, 'build_x', text='X')
    row.prop(pg, 'build_y', text='Y')
    row.prop(pg, 'build_z', text='Z')
    row = layout.row(align=True)
    row.prop(pg, 'fit_height', text=f'Height ({dict((u[0], u[1]) for u in UNITS)[pg.unit]})')
    row.operator('mch.print_scale_height', text='Scale to Height')
    ms = measures(context.scene)
    col = layout.column(align=True)
    col.prop(pg, 'show_measures')
    for k, (a, b) in enumerate(ms[-8:], max(1, len(ms) - 7)):
        L, H, V = components(a, b)
        col.label(text=f'{k}.  L {fmt(context, L)}   H {fmt(context, H)}   V {fmt(context, V)}')
    if ms:
        col.operator('mch.print_clear_measures', icon='TRASH')
    col = layout.column(align=True)
    for line in ('Drag on the model: length, horizontal (H), vertical (V)', 'Shift: straight horizontal / vertical',
                 'X / Y / Z while dragging: along that axis', 'Alt + click: the nearest measure gone'):
        col.label(text=line)


def draw_cut(layout, context):
    pg = context.scene.mch_print
    col = layout.column(align=True)
    col.row(align=True).prop(pg, 'pin_style', expand=True)
    col.row(align=True).prop(pg, 'pin_count', expand=True)
    col.prop(pg, 'pin_auto')
    if not pg.pin_auto:
        if pg.pin_style == 'KEY':
            col.prop(pg, 'pin_diameter', text='Width (mm)')       # (0.24.165 a square key: its width at the cut)
        else:
            col.prop(pg, 'pin_diameter')
        col.prop(pg, 'pin_length')
    col.prop(pg, 'clearance')
    col.prop(pg, 'gap')
    col = layout.column(align=True)
    col.label(text='Cut the selected part through its middle')
    row = col.row(align=True)
    for ax, label in (('Z', 'Horizontal'), ('X', 'Vertical X'), ('Y', 'Vertical Y')):
        row.operator('mch.print_cut_axis', text=label).axis = ax
    col = layout.column(align=True)                       # 0.24.166 parts from any Split: keys between them
    col.operator('mch.print_keys', icon='MOD_BOOLEAN')
    col.label(text='(select the 2 halves of any Split)')
    col = layout.column(align=True)
    for line in ('Drag across a part: split along the line you draw', 'Shift: a straight line (horizontal / vertical / 45)',
                 'Keys on the smaller part, sockets in the bigger', 'The original is kept, hidden'):
        col.label(text=line)


# -----------------------------------------------------------------------------
# Tools
# -----------------------------------------------------------------------------

def _tool(key, idname, label, desc, keymap, drawer):
    def draw_settings(context, layout, tool):
        region = getattr(context, 'region', None)
        if region is not None and region.type == 'TOOL_HEADER':
            return
        drawer(layout, context)
    return type(f'MCH_TOOL_{key.lower()}', (bpy.types.WorkSpaceTool,), {
        'bl_space_type': 'VIEW_3D', 'bl_context_mode': 'OBJECT', 'bl_idname': idname, 'bl_label': label,
        'bl_description': desc, 'bl_icon': 'ops.generic.select_box', 'bl_widget': None, 'bl_keymap': keymap,
        'draw_settings': staticmethod(draw_settings)})


TOOLS = (
    _tool('PMEASURE', 'mecha.print_measure', 'Mecha Print Measure',
          'Drag on the model: the length and how much of it is horizontal / vertical (Shift: straight).\n'
          'Alt + click: the nearest measure gone',
          (('mch.print_measure', {'type': 'LEFTMOUSE', 'value': 'PRESS'}, None),
           ('mch.print_measure', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'shift': True}, None),   # (Shift held first)
           ('mch.print_measure', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'alt': True}, {'properties': [('remove', True)]}),
           ('mch.exit_tool', {'type': 'ESC', 'value': 'PRESS'}, None)), draw_measure),
    _tool('PCUT', 'mecha.print_cut', 'Mecha Print Cut',
          'Drag a line across a part: cut into two closed parts with connection pins across the cut (Shift: straight)',
          (('mch.print_cut', {'type': 'LEFTMOUSE', 'value': 'PRESS'}, None),
           ('mch.print_cut', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'shift': True}, None),
           ('mch.exit_tool', {'type': 'ESC', 'value': 'PRESS'}, None)), draw_cut),
)
CLASSES = (MCH_PG_Print, MCH_OT_print_measure, MCH_OT_print_clear_measures, MCH_OT_print_scale_height, MCH_OT_print_cut,
           MCH_OT_print_cut_axis, MCH_OT_print_keys)
_HANDLE = [None]


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_print = PointerProperty(type=MCH_PG_Print)
    prev = 'mecha.weather_snow'
    for t in TOOLS:
        try:
            bpy.utils.register_tool(t, after={prev}, group=False)
        except (ValueError, RuntimeError, KeyError):
            try:
                bpy.utils.register_tool(t, separator=True, group=False)
            except (ValueError, RuntimeError):
                pass
        prev = t.bl_idname
    if _HANDLE[0] is None:
        _HANDLE[0] = bpy.types.SpaceView3D.draw_handler_add(_draw_overlay, (), 'WINDOW', 'POST_PIXEL')


def unregister():
    if _HANDLE[0] is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_HANDLE[0], 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _HANDLE[0] = None
    for t in reversed(TOOLS):
        try:
            bpy.utils.unregister_tool(t)
        except (ValueError, RuntimeError, KeyError):
            pass
    if hasattr(bpy.types.Scene, 'mch_print'):
        del bpy.types.Scene.mch_print
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
