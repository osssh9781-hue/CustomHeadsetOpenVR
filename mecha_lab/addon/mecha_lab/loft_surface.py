"""Loft / Surface: smooth polygon surfaces between curves (NURBS-like, not CAD NURBS).

* LOFT  - 2+ curve objects are sections.  Each is sampled by arc length to
          the same number of points, aligned (direction / start point) to the
          previous section, then interpolated across sections with a
          Catmull-Rom spline (Smoothness 0 = straight ruled surface, 1 = smooth
          through all sections).  The result is a quad mesh.
* SWEEP - one profile curve is moved along a path curve with parallel
          transport frames (optional twist and scale).

The generated object stores its source curves and settings
(``Object.mch_loft``).  A depsgraph handler rebuilds it when a source curve
changes, so editing the curves updates the surface live.  "Apply" freezes it
(and applies the thickness modifier).  What this is NOT: mathematical NURBS
patches, continuity guarantees (G1/G2) or trimming as in CAD software.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from bpy.app.handlers import persistent
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty,
                       PointerProperty)
from mathutils import Vector
from mathutils.geometry import interpolate_bezier

from . import core_geometry as cg

THICK_MOD = 'MCH_LoftThickness'
_building = False


def _is_curve(self, ob):
    return ob is not None and ob.type == 'CURVE'


def _update(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and getattr(ob, 'mch_loft', None) and ob.mch_loft.live:
        safe_rebuild(ob)


class MCH_PG_LoftCurve(bpy.types.PropertyGroup):
    curve: PointerProperty(type=bpy.types.Object, poll=_is_curve, update=_update)
    reverse: BoolProperty(name='Reverse', default=False, update=_update,
                          description='Reverse this curve direction (overrides auto-align)')


class MCH_PG_Loft(bpy.types.PropertyGroup):
    mode: EnumProperty(name='Mode', items=[
        ('LOFT', 'Loft', 'Surface through 2+ section curves'),
        ('SWEEP', 'Sweep', 'Profile curve moved along a path curve')], default='LOFT', update=_update)
    curves: CollectionProperty(type=MCH_PG_LoftCurve)
    profile: PointerProperty(name='Profile', type=bpy.types.Object, poll=_is_curve, update=_update)
    path: PointerProperty(name='Path', type=bpy.types.Object, poll=_is_curve, update=_update)
    samples: IntProperty(name='Curve Samples', default=32, min=3, max=512, update=_update,
                         description='Points per section (arc-length resampled)')
    segments: IntProperty(name='Surface Segments', default=8, min=1, max=128, update=_update,
                          description='Rows between two neighbouring sections (Sweep: rows along the path)')
    smoothness: FloatProperty(name='Smoothness', default=1.0, min=0.0, max=1.0, update=_update,
                              description='0 = straight ruled surface between sections, 1 = smooth Catmull-Rom')
    thickness: FloatProperty(name='Thickness', default=0.0, soft_min=-1.0, soft_max=1.0, precision=4,
                             unit='LENGTH', update=_update)
    cap_ends: BoolProperty(name='Cap Ends', default=False, update=_update,
                           description='Close both ends (closed sections only)')
    flip_normals: BoolProperty(name='Flip Normals', default=False, update=_update)
    auto_align: BoolProperty(name='Auto Align', default=True, update=_update,
                             description='Match direction and start point of each section to the previous one')
    twist: IntProperty(name='Twist (samples)', default=0, min=-512, max=512, update=_update,
                       description='Shift closed-section start points (fixes twisting)')
    close_loft: BoolProperty(name='Close Loft', default=False, update=_update,
                             description='Connect the last section back to the first (ring-shaped surface)')
    sweep_scale: FloatProperty(name='Profile Scale', default=1.0, min=0.0001, soft_max=10.0, update=_update)
    sweep_twist: FloatProperty(name='Twist Angle', default=0.0, subtype='ANGLE', update=_update)
    live: BoolProperty(name='Live', default=False)


# -----------------------------------------------------------------------------
# Curve sampling
# -----------------------------------------------------------------------------


def curve_polyline(ob, resolution=24):
    """World-space dense polyline of the first spline: (points, cyclic)."""
    if ob is None or ob.type != 'CURVE' or not ob.data.splines:
        raise cg.CutError('Loft source must be a curve object with at least one spline.')
    sp = ob.data.splines[0]
    mw = ob.matrix_world
    pts = []
    if sp.type == 'BEZIER':
        bp = sp.bezier_points
        n = len(bp)
        if n < 2:
            raise cg.CutError(f'Curve "{ob.name}" needs at least 2 points.')
        spans = n if sp.use_cyclic_u else n - 1
        for i in range(spans):
            a, b = bp[i], bp[(i + 1) % n]
            seg = interpolate_bezier(a.co, a.handle_right, b.handle_left, b.co, resolution + 1)
            pts.extend(seg[:-1])
        if not sp.use_cyclic_u:
            pts.append(bp[n - 1].co.copy())
    elif sp.type == 'POLY':
        pts = [Vector(p.co[:3]) for p in sp.points]
    else:   # NURBS: use Blender's own evaluation
        dg = bpy.context.evaluated_depsgraph_get()
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        try:
            pts = [v.co.copy() for v in me.vertices]
        finally:
            ev.to_mesh_clear()
        mw_pts = [mw @ p for p in pts]
        return _dedupe3(mw_pts), bool(sp.use_cyclic_u)
    return _dedupe3([mw @ Vector(p) for p in pts]), bool(sp.use_cyclic_u)


def _dedupe3(pts, eps=1e-7):
    out = []
    for p in pts:
        if not out or (p - out[-1]).length > eps:
            out.append(p)
    return out


def resample(points, count, cyclic):
    """Arc-length resampling to exactly ``count`` points."""
    pts = list(points) + ([points[0]] if cyclic else [])
    if len(pts) < 2:
        raise cg.CutError('Curve is too short to sample.')
    lengths = [0.0]
    for a, b in zip(pts, pts[1:]):
        lengths.append(lengths[-1] + (b - a).length)
    total = lengths[-1]
    if total < 1e-9:
        raise cg.CutError('Curve has zero length.')
    out = []
    steps = count if cyclic else count - 1
    j = 0
    for k in range(count):
        s = total * k / steps
        while j < len(lengths) - 2 and lengths[j + 1] < s:
            j += 1
        seg = lengths[j + 1] - lengths[j]
        t = 0.0 if seg < 1e-12 else (s - lengths[j]) / seg
        out.append(pts[j].lerp(pts[j + 1], min(max(t, 0.0), 1.0)))
    return out


def align_section(prev, cur, cyclic, twist=0):
    """Match direction and start point of ``cur`` to ``prev`` (same length)."""
    n = len(cur)
    if not cyclic:
        straight = (prev[0] - cur[0]).length + (prev[-1] - cur[-1]).length
        flipped = (prev[0] - cur[-1]).length + (prev[-1] - cur[0]).length
        return list(reversed(cur)) if flipped < straight else list(cur)
    best = None
    for cand in (cur, list(reversed(cur))):
        for k in range(n):
            err = 0.0
            for i in range(0, n, max(1, n // 32)):
                err += (prev[i] - cand[(i + k) % n]).length_squared
            if best is None or err < best[0]:
                best = (err, cand, k)
    _e, cand, k = best
    k = (k + twist) % n
    return cand[k:] + cand[:k]


def catmull(p0, p1, p2, p3, t, smooth):
    lin = p1.lerp(p2, t)
    if smooth <= 0:
        return lin
    t2, t3 = t * t, t * t * t
    cr = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
                (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
    return lin.lerp(cr, smooth)


# -----------------------------------------------------------------------------
# Surface builders -> rows of points
# -----------------------------------------------------------------------------


def loft_rows(p):
    entries = [e for e in p.curves if e.curve is not None]
    if len(entries) < 2:
        raise cg.CutError('Loft needs at least 2 curves.')
    polylines = [curve_polyline(e.curve) for e in entries]
    cyclic_flags = {c for _pts, c in polylines}
    if len(cyclic_flags) > 1:
        raise cg.CutError('Mixing open and closed curves is not supported; make all open or all closed.')
    cyclic = cyclic_flags.pop()
    sections = []
    for (pts, _c), e in zip(polylines, entries):
        sec = resample(pts, p.samples, cyclic)
        if e.reverse:
            sec = list(reversed(sec))
        elif p.auto_align and sections:
            sec = align_section(sections[-1], sec, cyclic, 0)
        if cyclic and sections and p.twist:
            k = p.twist % len(sec)
            sec = sec[k:] + sec[:k]
        sections.append(sec)
    m = len(sections)
    closed_loft = p.close_loft and m >= 3
    rows = []
    spans = m if closed_loft else m - 1
    for i in range(spans):
        for s in range(p.segments):
            t = s / p.segments
            row = []
            for j in range(p.samples):
                def sec(k):
                    if closed_loft:
                        return sections[k % m][j]
                    return sections[max(0, min(m - 1, k))][j]
                row.append(catmull(sec(i - 1), sec(i), sec(i + 1), sec(i + 2), t, p.smoothness))
            rows.append(row)
    if not closed_loft:
        rows.append(list(sections[-1]))
    return rows, cyclic, closed_loft


def sweep_rows(p):
    if p.profile is None or p.path is None:
        raise cg.CutError('Sweep needs a profile curve and a path curve.')
    prof_pts, prof_cyclic = curve_polyline(p.profile)
    # Profile in its own local XY (relative to its object origin).
    inv = p.profile.matrix_world.inverted_safe()
    local = [inv @ q for q in resample(prof_pts, p.samples, prof_cyclic)]
    path_pts, path_cyclic = curve_polyline(p.path)
    count = max(2, p.segments * 4)
    path = resample(path_pts, count, path_cyclic)
    tangents = []
    for i in range(len(path)):
        a = path[i - 1] if (i > 0 or path_cyclic) else path[i]
        b = path[(i + 1) % len(path)] if (i < len(path) - 1 or path_cyclic) else path[i]
        t = (b - a)
        tangents.append(t.normalized() if t.length > 1e-12 else Vector((0, 0, 1)))
    ref = Vector((0, 0, 1)) if abs(tangents[0].z) < 0.9 else Vector((1, 0, 0))
    normal = (ref - tangents[0] * ref.dot(tangents[0])).normalized()
    rows = []
    for i, (pos, t) in enumerate(zip(path, tangents)):
        if i:
            normal = normal - t * normal.dot(t)
            normal = normal.normalized() if normal.length > 1e-12 else normal
        binormal = t.cross(normal)
        ang = p.sweep_twist * (i / max(1, len(path) - 1))
        c, s = math.cos(ang), math.sin(ang)
        nx, ny = normal * c + binormal * s, -normal * s + binormal * c
        rows.append([pos + nx * (q.x * p.sweep_scale) + ny * (q.y * p.sweep_scale) for q in local])
    return rows, prof_cyclic, path_cyclic


def build_mesh_from_rows(rows, cyclic_u, cyclic_v, cap, flip):
    bm = bmesh.new()
    try:
        grid = [[bm.verts.new(q) for q in row] for row in rows]
        nu = len(rows[0])
        nv = len(rows)
        span_u = nu if cyclic_u else nu - 1
        span_v = nv if cyclic_v else nv - 1
        for i in range(span_v):
            for j in range(span_u):
                a = grid[i][j]
                b = grid[i][(j + 1) % nu]
                c = grid[(i + 1) % nv][(j + 1) % nu]
                d = grid[(i + 1) % nv][j]
                if len({a, b, c, d}) == 4:
                    f = bm.faces.new((a, b, c, d))
                    f.smooth = True
        if cap and cyclic_u and not cyclic_v:
            bm.faces.new(list(reversed(grid[0])))
            bm.faces.new(grid[-1])
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-7)
        if cap and cyclic_u and not cyclic_v:
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        if flip:
            bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        if not bm.faces:
            raise cg.CutError('Surface has no faces (curves coincide?).')
        return bm
    except Exception:
        bm.free()
        raise


def rebuild(ob):
    p = ob.mch_loft
    if p.mode == 'LOFT':
        rows, cyclic_u, cyclic_v = loft_rows(p)
    else:
        rows, cyclic_u, cyclic_v = sweep_rows(p)
    inv = ob.matrix_world.inverted_safe()
    rows = [[inv @ q for q in row] for row in rows]
    bm = build_mesh_from_rows(rows, cyclic_u, cyclic_v, p.cap_ends, p.flip_normals)
    try:
        bm.to_mesh(ob.data)
    finally:
        bm.free()
    ob.data.update()
    mod = ob.modifiers.get(THICK_MOD)
    if abs(p.thickness) > 0:
        if mod is None:
            mod = ob.modifiers.new(THICK_MOD, 'SOLIDIFY')
            mod.use_even_offset = True
        mod.thickness = p.thickness
    elif mod is not None:
        ob.modifiers.remove(mod)


def safe_rebuild(ob):
    global _building
    if _building:
        return False
    _building = True
    try:
        rebuild(ob)
        ob['mch_loft_error'] = ''
        return True
    except (cg.CutError, ValueError, RuntimeError) as ex:
        ob['mch_loft_error'] = str(ex)
        return False
    finally:
        _building = False


def _sources(ob):
    p = ob.mch_loft
    if p.mode == 'LOFT':
        return [e.curve for e in p.curves if e.curve is not None]
    return [c for c in (p.profile, p.path) if c is not None]


@persistent
def _on_depsgraph(scene, depsgraph):
    if _building:
        return
    changed = set()
    for up in depsgraph.updates:
        idb = up.id
        if isinstance(idb, bpy.types.Object) and idb.type == 'CURVE':
            changed.add(idb.original.name)
        elif isinstance(idb, bpy.types.Curve):
            for ob in bpy.data.objects:
                if ob.data == idb.original:
                    changed.add(ob.name)
    if not changed:
        return
    for ob in list(scene.objects):
        p = getattr(ob, 'mch_loft', None)
        if p is not None and p.live and ob.type == 'MESH':
            if any(c.name in changed for c in _sources(ob)):
                safe_rebuild(ob)


# -----------------------------------------------------------------------------
# Operators
# -----------------------------------------------------------------------------


def _chain_order(curves, start):
    def centre(o):
        return sum((o.matrix_world @ Vector(c) for c in o.bound_box), Vector()) / 8.0
    rest = [c for c in curves if c != start]
    order = [start]
    while rest:
        last = centre(order[-1])
        nxt = min(rest, key=lambda o: (centre(o) - last).length)
        order.append(nxt)
        rest.remove(nxt)
    return order


def _new_carrier(context, name):
    me = bpy.data.meshes.new(name + '_Mesh')
    ob = bpy.data.objects.new(name, me)
    coll = context.collection if context.collection is not None else context.scene.collection
    coll.objects.link(ob)
    return ob


def _copy_defaults(dst, src):
    for key in ('samples', 'segments', 'smoothness', 'thickness', 'cap_ends', 'flip_normals',
                'auto_align', 'twist', 'close_loft', 'sweep_scale', 'sweep_twist'):
        setattr(dst, key, getattr(src, key))


def _select_only(context, ob):
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob


class MCH_OT_loft_create(bpy.types.Operator):
    bl_idname = 'mch.loft_create'
    bl_label = 'Create Loft Surface'
    bl_description = ('Smooth surface through the selected curves (2+). Order: chained from the active '
                      'curve by nearest distance, or by name')
    bl_options = {'REGISTER', 'UNDO'}
    order: EnumProperty(name='Order', items=[
        ('CHAIN', 'Nearest Chain', 'Start at the active curve, then the nearest next one'),
        ('NAME', 'By Name', 'Alphabetical object names')], default='CHAIN')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and len([o for o in context.selected_objects if o.type == 'CURVE']) >= 2

    def execute(self, context):
        curves = [o for o in context.selected_objects if o.type == 'CURVE']
        if self.order == 'NAME':
            curves.sort(key=lambda o: o.name)
        else:
            act = context.view_layer.objects.active
            curves = _chain_order(curves, act if act in curves else curves[0])
        ob = _new_carrier(context, 'MCH_Loft')
        p = ob.mch_loft
        _copy_defaults(p, context.scene.mch_loft)
        p.mode = 'LOFT'
        for c in curves:
            p.curves.add().curve = c
        p.live = True
        if not safe_rebuild(ob):
            msg = ob.get('mch_loft_error', 'Loft failed')
            cg.remove_object_and_mesh(ob)
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}
        _select_only(context, ob)
        self.report({'INFO'}, f'Loft through {len(curves)} curves: {len(ob.data.vertices)} verts (live)')
        return {'FINISHED'}


class MCH_OT_sweep_create(bpy.types.Operator):
    bl_idname = 'mch.sweep_create'
    bl_label = 'Create Sweep'
    bl_description = 'Select 2 curves: the ACTIVE one is the path, the other is the profile'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        act = context.view_layer.objects.active
        return (context.mode == 'OBJECT' and act is not None and act.type == 'CURVE' and
                len([o for o in context.selected_objects if o.type == 'CURVE']) == 2)

    def execute(self, context):
        path = context.view_layer.objects.active
        profile = next(o for o in context.selected_objects if o.type == 'CURVE' and o != path)
        ob = _new_carrier(context, 'MCH_Sweep')
        p = ob.mch_loft
        _copy_defaults(p, context.scene.mch_loft)
        p.mode = 'SWEEP'
        p.path = path
        p.profile = profile
        p.live = True
        if not safe_rebuild(ob):
            msg = ob.get('mch_loft_error', 'Sweep failed')
            cg.remove_object_and_mesh(ob)
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}
        _select_only(context, ob)
        self.report({'INFO'}, f'Sweep: profile "{profile.name}" along "{path.name}" (live)')
        return {'FINISHED'}


def _active_loft(context):
    ob = context.active_object
    if ob is not None and ob.type == 'MESH' and getattr(ob, 'mch_loft', None) and \
            (ob.mch_loft.live or len(ob.mch_loft.curves) or ob.mch_loft.path):
        return ob
    return None


class MCH_OT_loft_rebuild(bpy.types.Operator):
    bl_idname = 'mch.loft_rebuild'
    bl_label = 'Rebuild Surface'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _active_loft(context) is not None

    def execute(self, context):
        ob = _active_loft(context)
        if not safe_rebuild(ob):
            self.report({'ERROR'}, ob.get('mch_loft_error', 'Rebuild failed'))
            return {'CANCELLED'}
        return {'FINISHED'}


class MCH_OT_loft_move(bpy.types.Operator):
    bl_idname = 'mch.loft_move'
    bl_label = 'Move Section'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    index: IntProperty()
    direction: IntProperty(default=-1)

    @classmethod
    def poll(cls, context):
        return _active_loft(context) is not None

    def execute(self, context):
        ob = _active_loft(context)
        p = ob.mch_loft
        j = self.index + self.direction
        if 0 <= self.index < len(p.curves) and 0 <= j < len(p.curves):
            p.curves.move(self.index, j)
            safe_rebuild(ob)
        return {'FINISHED'}


class MCH_OT_loft_apply(bpy.types.Operator):
    bl_idname = 'mch.loft_apply'
    bl_label = 'Apply Surface'
    bl_description = 'Freeze the surface: apply thickness and stop following the curves'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _active_loft(context) is not None

    def execute(self, context):
        ob = _active_loft(context)
        mod = ob.modifiers.get(THICK_MOD)
        try:
            if mod is not None:
                cg.apply_single_modifier(context, ob, mod, 'SINGLE')
        except (cg.CutError, RuntimeError) as ex:
            self.report({'ERROR'}, str(ex))
            return {'CANCELLED'}
        ob.mch_loft.live = False
        ob.mch_loft.curves.clear()
        ob.mch_loft.profile = None
        ob.mch_loft.path = None
        self.report({'INFO'}, f'{ob.name}: surface applied (no longer live)')
        return {'FINISHED'}


CLASSES = (MCH_PG_LoftCurve, MCH_PG_Loft, MCH_OT_loft_create, MCH_OT_sweep_create,
           MCH_OT_loft_rebuild, MCH_OT_loft_move, MCH_OT_loft_apply)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Object.mch_loft = PointerProperty(type=MCH_PG_Loft)
    bpy.types.Scene.mch_loft = PointerProperty(type=MCH_PG_Loft)
    if _on_depsgraph not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph)


def unregister():
    if _on_depsgraph in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph)
    for n, t in (('mch_loft', bpy.types.Scene), ('mch_loft', bpy.types.Object)):
        if hasattr(t, n):
            delattr(t, n)
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
