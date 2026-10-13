"""Deform tool: Lattice Cage and Bend Curve driven by clicked control points.

Both controllers are NON-DESTRUCTIVE until Apply: the mesh only carries a
Lattice / Curve modifier that points at a controller object, so the controller
can be re-edited at any time (Edit Controller, or select it and Tab).

Point editing
-------------
* Click a control point (Shift = add, B/box = several) in the controller's Edit
  Mode.  A Move / Rotate / Scale gizmo appears on the selection.
* The transform is applied with a FALLOFF around the selection, so rotating or
  scaling a SINGLE point (pivot = that point) still bends the neighbouring
  points and therefore the mesh.  Weight of a point = 1 when selected, else
  ``falloff_weight(distance to nearest selected point)``.
* Two gizmo styles:
  - ``MECHA``   : our gizmo, continuous Falloff Smoothness, Bend Curve aware
                  (rotation about the curve tangent = local twist through the
                  point tilt, scale = point radius = local thickness).
  - ``BLENDER`` : Blender's own transform gizmo + Proportional Editing, whose
                  size/falloff/pivot are synced from the Mecha settings.

The math (weights, transforms, state read/write) is plain Python so tests can
drive it without a viewport; ``DragLogic`` turns mouse movement into transform
amounts through two projection hooks that tests replace.
"""
from __future__ import annotations

import math

import bpy
from bpy.props import (BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty,
                       PointerProperty)
from mathutils import Matrix, Quaternion, Vector

from . import core_geometry as cg

# Names kept from v0.9.1 so controllers in saved files keep working.
MOD_LATTICE = 'MCH_Deform_Lattice'
MOD_BEND = 'MCH_Deform_Bend'
MOD_PREFIX = 'MCH_Deform'
ROLE_KEY = 'mch_deform_kind'          # 'LATTICE' / 'BEND' on controller objects
SAVED_KEY = 'mch_deform_saved'        # Scene ID prop: native settings to restore
AXES = (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))
# Rotation that maps the curve's own X axis onto mesh axis X / Y / Z.  The Bend
# Curve is always built along curve-space +X (deform axis POS_X) because only
# that axis gives an exact identity + correct tilt sign in Blender's curve frame.
_AXIS_ROT = (Matrix.Identity(4), Matrix.Rotation(math.pi / 2, 4, 'Z'), Matrix.Rotation(-math.pi / 2, 4, 'Y'))


# =============================================================================
# Pure math
# =============================================================================


def falloff_weight(dist, radius, smoothness):
    """1 at the selected point, 0 at ``radius``.  smoothness 0 = linear cone,
    1 = smooth bell (cosine).  Values in between blend the two."""
    if radius <= 0.0:
        return 1.0 if dist <= 1e-9 else 0.0
    t = dist / radius
    if t >= 1.0:
        return 0.0
    lin = 1.0 - t
    bell = 0.5 * (1.0 + math.cos(math.pi * t))
    return lin + (bell - lin) * max(0.0, min(1.0, smoothness))


def native_falloff(smoothness):
    """Closest Blender proportional falloff for the continuous smoothness."""
    if smoothness < 0.2:
        return 'SHARP'
    if smoothness < 0.45:
        return 'LINEAR'
    if smoothness < 0.8:
        return 'SMOOTH'
    return 'SPHERE'


def compute_weights(positions, selected, radius, smoothness):
    """Return (weights, nearest selected index) for world-space positions."""
    sel = [i for i, s in enumerate(selected) if s]
    weights, nearest = [], []
    for i, p in enumerate(positions):
        if selected[i]:
            weights.append(1.0)
            nearest.append(i)
            continue
        best, best_d = -1, float('inf')
        for j in sel:
            d = (positions[j] - p).length
            if d < best_d:
                best, best_d = j, d
        nearest.append(best)
        weights.append(falloff_weight(best_d, radius, smoothness) if best >= 0 else 0.0)
    return weights, nearest


def pivot_points(positions, selected, nearest, mode, cursor):
    """Pivot for every point: MEDIAN (centre of selection), INDIVIDUAL (each
    point's nearest selected point, so a lone point pivots on itself) or CURSOR."""
    sel = [positions[i] for i, s in enumerate(selected) if s]
    if not sel:
        return [None] * len(positions)
    if mode == 'CURSOR':
        c = Vector(cursor)
        return [c] * len(positions)
    if mode == 'INDIVIDUAL':
        return [positions[n] if n >= 0 else None for n in nearest]
    centre = sum(sel, Vector()) / len(sel)
    return [centre] * len(positions)


def transform_point(p, w, pivot, op):
    """Weighted Move / Rotate / Scale of one world-space point."""
    if w <= 0.0:
        return p.copy()
    mode = op['mode']
    if mode == 'MOVE':
        return p + Vector(op['move']) * w
    if mode == 'ROTATE':
        q = Quaternion(Vector(op['axis']).normalized(), op['angle'] * w)
        return pivot + q @ (p - pivot)
    basis = op.get('basis') or Matrix.Identity(3)
    local = basis.transposed() @ (p - pivot)
    s = op['scale']
    local = Vector([local[k] * (1.0 + w * (s[k] - 1.0)) for k in range(3)])
    return pivot + basis @ local


# =============================================================================
# Controller state (lattice points / Bezier points) <-> world space
# =============================================================================


def role(ob):
    return ob.get(ROLE_KEY, '') if ob is not None else ''


def read_state(ctrl):
    """Snapshot of every control point, in the controller's LOCAL space."""
    if ctrl.type == 'LATTICE':
        return {'kind': 'LATTICE',
                'points': [(p.co_deform.copy(), bool(p.select)) for p in ctrl.data.points]}
    pts = []
    for si, spl in enumerate(ctrl.data.splines):
        if spl.type != 'BEZIER':
            continue
        for pi, bp in enumerate(spl.bezier_points):
            sel = bool(bp.select_control_point or bp.select_left_handle or bp.select_right_handle)
            pts.append({'s': si, 'i': pi, 'co': bp.co.copy(), 'hl': bp.handle_left.copy(),
                        'hr': bp.handle_right.copy(), 'tl': bp.handle_left_type, 'tr': bp.handle_right_type,
                        'tilt': bp.tilt, 'radius': bp.radius, 'sel': sel})
    return {'kind': 'CURVE', 'points': pts}


def write_state(ctrl, state):
    if state['kind'] == 'LATTICE':
        for p, (co, _sel) in zip(ctrl.data.points, state['points']):
            p.co_deform = co
    else:
        splines = ctrl.data.splines
        for d in state['points']:
            bp = splines[d['s']].bezier_points[d['i']]
            bp.handle_left_type, bp.handle_right_type = d['tl'], d['tr']
            bp.co = d['co']
            if d['tl'] != 'AUTO':
                bp.handle_left = d['hl']
            if d['tr'] != 'AUTO':
                bp.handle_right = d['hr']
            bp.tilt = d['tilt']
            bp.radius = d['radius']
    ctrl.data.update_tag()


def _positions(ctrl, state):
    mw = ctrl.matrix_world
    if state['kind'] == 'LATTICE':
        return [mw @ co for co, _ in state['points']], [s for _, s in state['points']]
    return [mw @ d['co'] for d in state['points']], [d['sel'] for d in state['points']]


def curve_tangent(ctrl, state, k):
    """World tangent of Bezier point k (from its handles, else neighbours)."""
    mw = ctrl.matrix_world
    d = state['points'][k]
    t = (mw @ d['hr']) - (mw @ d['hl'])
    if t.length < 1e-9:
        pts = [p for p in state['points'] if p['s'] == d['s']]
        i = d['i']
        a = pts[max(i - 1, 0)]['co']
        b = pts[min(i + 1, len(pts) - 1)]['co']
        t = (mw @ b) - (mw @ a)
    return t.normalized() if t.length > 1e-9 else Vector((1, 0, 0))


def selection_pivot(ctrl, state, mode, cursor):
    pos, sel = _positions(ctrl, state)
    chosen = [p for p, s in zip(pos, sel) if s]
    if not chosen:
        return None
    if mode == 'CURSOR':
        return Vector(cursor)
    return sum(chosen, Vector()) / len(chosen)


def orientation_basis(ctrl, state, orient):
    """3x3 orthonormal basis of the gizmo axes (columns = X, Y, Z)."""
    if orient == 'GLOBAL':
        return Matrix.Identity(3)
    rot = ctrl.matrix_world.to_3x3().normalized()
    use_tangent = orient == 'TANGENT' or (orient == 'AUTO' and state['kind'] == 'CURVE')
    if use_tangent and state['kind'] == 'CURVE':
        sel = [k for k, d in enumerate(state['points']) if d['sel']]
        if sel:
            x = Vector()
            for k in sel:
                x += curve_tangent(ctrl, state, k)
            if x.length > 1e-9:
                x.normalize()
                up = rot.col[2].normalized()
                if abs(up.dot(x)) > 0.98:
                    up = rot.col[1].normalized()
                y = up.cross(x).normalized()
                z = x.cross(y).normalized()
                return Matrix((x, y, z)).transposed()
    return rot


def apply_falloff(ctrl, state, op):
    """Apply ``op`` to the snapshot ``state`` with falloff and write it.

    op keys: mode MOVE/ROTATE/SCALE, move (world vec), axis + angle (world),
    scale (3 factors along ``basis`` columns), basis (3x3), radius, smoothness,
    pivot MEDIAN/INDIVIDUAL/CURSOR, cursor.  Returns (affected point count,
    max weight of an unselected point).
    """
    pos, sel = _positions(ctrl, state)
    if not any(sel):
        return 0, 0.0
    weights, nearest = compute_weights(pos, sel, op['radius'], op['smoothness'])
    pivots = pivot_points(pos, sel, nearest, op.get('pivot', 'MEDIAN'), op.get('cursor', (0, 0, 0)))
    mw = ctrl.matrix_world
    inv = mw.inverted_safe()
    new = {'kind': state['kind'], 'points': []}
    affected = 0
    neighbour_max = 0.0
    for k, w in enumerate(weights):
        if w > 0.0:
            affected += 1
            if not sel[k]:
                neighbour_max = max(neighbour_max, w)
        piv = pivots[k] if pivots[k] is not None else pos[k]
        if state['kind'] == 'LATTICE':
            co, s = state['points'][k]
            new['points'].append((inv @ transform_point(pos[k], w, piv, op), s))
            continue
        d = dict(state['points'][k])
        if w > 0.0:
            mode = op['mode']
            if mode == 'SCALE':
                # Bend Curve: scale = point radius (local thickness); position kept.
                f = sum(op['scale']) / 3.0 if op.get('axis_index', -1) < 0 else op['scale'][op['axis_index']]
                d['radius'] = max(0.001, d['radius'] * (1.0 + w * (f - 1.0)))
            else:
                d['co'] = inv @ transform_point(pos[k], w, piv, op)
                hl, hr = mw @ d['hl'], mw @ d['hr']
                d['hl'] = inv @ transform_point(hl, w, piv, op)
                d['hr'] = inv @ transform_point(hr, w, piv, op)
                if mode == 'ROTATE':
                    axis = Vector(op['axis']).normalized()
                    tangent = curve_tangent(ctrl, state, k)
                    # Rotation about the tangent = twist (tilt); the rest bends.
                    d['tilt'] = d['tilt'] + w * op['angle'] * axis.dot(tangent)
                    # Rotated handles must not be recomputed by AUTO/VECTOR.
                    d['tl'] = 'ALIGNED' if d['tl'] == 'AUTO' else ('FREE' if d['tl'] == 'VECTOR' else d['tl'])
                    d['tr'] = 'ALIGNED' if d['tr'] == 'AUTO' else ('FREE' if d['tr'] == 'VECTOR' else d['tr'])
        new['points'].append(d)
    write_state(ctrl, new)
    return affected, neighbour_max


# =============================================================================
# Controllers: create / find
# =============================================================================


def _local_bounds(ob):
    vs = [v.co for v in ob.data.vertices] if ob.type == 'MESH' and ob.data.vertices else \
        [Vector(c) for c in ob.bound_box]
    lo = Vector((min(v[k] for v in vs) for k in range(3)))
    hi = Vector((max(v[k] for v in vs) for k in range(3)))
    return lo, hi


def target_mods(ctrl):
    """(mesh, modifier) pairs whose Mecha Deform modifier points at ``ctrl``."""
    if ctrl is None:
        return []
    return [(o, m) for o in bpy.data.objects if o.type == 'MESH' for m in o.modifiers
            if m.type in {'LATTICE', 'CURVE'} and m.object == ctrl and m.name.startswith(MOD_PREFIX)]


def targets_of(ctrl):
    out = []
    for o, _m in target_mods(ctrl):
        if o not in out:
            out.append(o)
    return out


def controller(context, kind=None):
    """(controller, target mesh) for the active object: a controller itself or
    a mesh carrying a Mecha Lattice / Bend modifier."""
    ob = context.active_object
    if ob is None:
        return None, None
    r = role(ob)
    if r and (kind is None or r == kind):
        t = targets_of(ob)
        return ob, (t[0] if t else None)
    if ob.type == 'MESH':
        for m in reversed(ob.modifiers):
            if m.type in {'LATTICE', 'CURVE'} and m.object is not None and role(m.object) and \
                    (kind is None or role(m.object) == kind):
                return m.object, ob
    return None, None


def _link(context, ob):
    coll = context.collection if context.collection is not None else context.scene.collection
    coll.objects.link(ob)


def create_lattice(context, meshes, res=(4, 4, 4), padding=0.05, interp='KEY_BSPLINE'):
    """Cage aligned to the first (active) mesh, around the EVALUATED bounds of
    all meshes (earlier modifiers such as SubD are inside the cage)."""
    rot = meshes[0].matrix_world.to_quaternion().to_matrix().to_4x4()
    inv = rot.inverted_safe()
    dg = context.evaluated_depsgraph_get()
    pts = [inv @ (o.matrix_world @ Vector(c)) for o in meshes for c in o.evaluated_get(dg).bound_box]
    lo = Vector((min(p[k] for p in pts) for k in range(3)))
    hi = Vector((max(p[k] for p in pts) for k in range(3)))
    size = hi - lo
    big = max(max(size), 1e-4)
    size = Vector([max(v, big * 0.05) * (1.0 + 2.0 * padding) for v in size])
    centre = (lo + hi) / 2.0
    lt = bpy.data.lattices.new('MCH_Lattice')
    lt.points_u, lt.points_v, lt.points_w = (max(2, int(r)) for r in res)
    for attr in ('interpolation_type_u', 'interpolation_type_v', 'interpolation_type_w'):
        setattr(lt, attr, interp)
    lo_ob = bpy.data.objects.new('MCH_Lattice', lt)
    _link(context, lo_ob)
    lo_ob.matrix_world = rot @ Matrix.Translation(centre) @ Matrix.Diagonal(size.to_4d())
    lo_ob[ROLE_KEY] = 'LATTICE'
    lo_ob.display_type = 'WIRE'
    lo_ob.show_in_front = True
    p = lo_ob.mch_deform
    p.res_x, p.res_y, p.res_z = lt.points_u, lt.points_v, lt.points_w
    for ob in meshes:
        for _o, m in [(o, m) for o, m in target_mods(lo_ob) if o == ob]:
            ob.modifiers.remove(m)
        m = ob.modifiers.new(MOD_LATTICE, 'LATTICE')
        m.object = lo_ob
        m.strength = p.strength
        m.show_in_editmode = True
    return lo_ob


def _bend_points(count, length):
    return [Vector((length * k / (count - 1), 0.0, 0.0)) for k in range(count)]


def create_bend(context, ob, count=5, axis='AUTO'):
    lo, hi = _local_bounds(ob)
    size = hi - lo
    ax = max(range(3), key=lambda k: size[k]) if axis == 'AUTO' else 'XYZ'.index(axis)
    length = max(size[ax], 1e-4)
    start = (lo + hi) / 2.0
    start[ax] = lo[ax]
    cu = bpy.data.curves.new('MCH_BendCurve', 'CURVE')
    cu.dimensions = '3D'
    cu.use_radius = True
    cu.use_stretch = False
    cu.use_deform_bounds = False
    cu.twist_mode = 'MINIMUM'
    cu.resolution_u = 24
    spl = cu.splines.new('BEZIER')
    spl.tilt_interpolation = 'CARDINAL'
    spl.radius_interpolation = 'CARDINAL'
    count = max(2, int(count))
    spl.bezier_points.add(count - 1)
    for bp, co in zip(spl.bezier_points, _bend_points(count, length)):
        bp.handle_left_type = bp.handle_right_type = 'AUTO'
        bp.co = co
    co_ob = bpy.data.objects.new('MCH_BendCurve', cu)
    _link(context, co_ob)
    co_ob.matrix_world = ob.matrix_world @ Matrix.Translation(start) @ _AXIS_ROT[ax]
    co_ob[ROLE_KEY] = 'BEND'
    co_ob.show_in_front = True
    co_ob.mch_deform.bend_count = count
    m = ob.modifiers.new(MOD_BEND, 'CURVE')
    m.object = co_ob
    m.deform_axis = 'POS_X'
    m.show_in_editmode = True
    co_ob['mch_bend_length'] = length
    co_ob['mch_bend_axis'] = ax
    return co_ob


def resample_bend(ctrl, count):
    """Rebuild the Bend Curve with ``count`` points along its CURRENT shape
    (positions, tilt and radius sampled by arc length)."""
    from mathutils.geometry import interpolate_bezier
    spl = next((s for s in ctrl.data.splines if s.type == 'BEZIER'), None)
    if spl is None or count < 2:
        return
    bps = spl.bezier_points
    samples = []   # (pos, tilt, radius)
    steps = 32
    for i in range(len(bps) - 1):
        a, b = bps[i], bps[i + 1]
        seg = interpolate_bezier(a.co, a.handle_right, b.handle_left, b.co, steps + 1)
        for j, p in enumerate(seg[:-1] if i < len(bps) - 2 else seg):
            t = j / steps
            samples.append((p.copy(), a.tilt + (b.tilt - a.tilt) * t, a.radius + (b.radius - a.radius) * t))
    if len(samples) < 2:
        return
    acc = [0.0]
    for i in range(1, len(samples)):
        acc.append(acc[-1] + (samples[i][0] - samples[i - 1][0]).length)
    total = acc[-1] or 1.0
    picked = []
    j = 0
    for k in range(count):
        target = total * k / (count - 1)
        while j < len(acc) - 2 and acc[j + 1] < target:
            j += 1
        span = acc[j + 1] - acc[j] or 1.0
        t = max(0.0, min(1.0, (target - acc[j]) / span))
        p0, p1 = samples[j], samples[j + 1]
        picked.append((p0[0].lerp(p1[0], t), p0[1] + (p1[1] - p0[1]) * t, p0[2] + (p1[2] - p0[2]) * t))
    ctrl.data.splines.remove(spl)
    new = ctrl.data.splines.new('BEZIER')
    new.tilt_interpolation = 'CARDINAL'
    new.radius_interpolation = 'CARDINAL'
    new.bezier_points.add(count - 1)
    for bp, (co, tilt, rad) in zip(new.bezier_points, picked):
        bp.handle_left_type = bp.handle_right_type = 'AUTO'
        bp.co = co
        bp.tilt = tilt
        bp.radius = rad


# =============================================================================
# Property groups
# =============================================================================


def _in_edit(ctrl):
    ctx = bpy.context
    return ctx.object == ctrl and ctx.mode in {'EDIT_LATTICE', 'EDIT_CURVE'}


def _with_object_mode(ctrl, fn):
    """Run ``fn`` with ``ctrl`` out of Edit Mode (resolution can't change in
    Edit Mode), then return to Edit Mode."""
    editing = _in_edit(ctrl)
    if editing:
        bpy.ops.object.mode_set(mode='OBJECT')
    try:
        fn()
    finally:
        if editing:
            bpy.ops.object.mode_set(mode='EDIT')


def _update_res(self, context):
    ctrl = self.id_data
    if not isinstance(ctrl, bpy.types.Object) or ctrl.type != 'LATTICE' or role(ctrl) != 'LATTICE':
        return
    lt = ctrl.data
    want = (self.res_x, self.res_y, self.res_z)
    if (lt.points_u, lt.points_v, lt.points_w) == want:
        return

    def resize():
        # Blender re-samples the existing deformation into the new grid.
        lt.points_u, lt.points_v, lt.points_w = want
    try:
        _with_object_mode(ctrl, resize)
    except RuntimeError:
        pass


def _update_bend_count(self, context):
    ctrl = self.id_data
    if not isinstance(ctrl, bpy.types.Object) or role(ctrl) != 'BEND':
        return
    spl = next((s for s in ctrl.data.splines if s.type == 'BEZIER'), None)
    if spl is None or len(spl.bezier_points) == self.bend_count:
        return
    try:
        _with_object_mode(ctrl, lambda: resample_bend(ctrl, self.bend_count))
    except RuntimeError:
        pass


def _update_strength(self, context):
    for _o, m in target_mods(self.id_data):
        if m.type == 'LATTICE':
            m.strength = self.strength


def _update_curve_res(self, context):
    ctrl = self.id_data
    if role(ctrl) == 'BEND':
        ctrl.data.resolution_u = self.curve_resolution


def _update_ramp(self, context):
    """Twist / Taper ramps are ADDED along the curve (start 0 -> end full) on
    top of per-point edits, by applying only the change since last time."""
    ctrl = self.id_data
    if role(ctrl) != 'BEND':
        return
    d_twist = self.twist - self.applied_twist
    ratio = self.taper / self.applied_taper if self.applied_taper > 1e-6 else 1.0
    if abs(d_twist) < 1e-9 and abs(ratio - 1.0) < 1e-9:
        return
    for spl in ctrl.data.splines:
        if spl.type != 'BEZIER':
            continue
        n = max(1, len(spl.bezier_points) - 1)
        for i, bp in enumerate(spl.bezier_points):
            f = i / n
            bp.tilt += d_twist * f
            bp.radius = max(0.001, bp.radius * (1.0 + (ratio - 1.0) * f))
    self.applied_twist = self.twist
    self.applied_taper = self.taper
    ctrl.data.update_tag()


class MCH_PG_DeformObject(bpy.types.PropertyGroup):
    """Object.mch_deform: live values of one controller (names kept from v0.9.1)."""
    res_x: IntProperty(name='Resolution X', default=4, min=2, max=64, update=_update_res,
                       description='Lattice points along X (keeps the current deformation)')
    res_y: IntProperty(name='Resolution Y', default=4, min=2, max=64, update=_update_res)
    res_z: IntProperty(name='Resolution Z', default=4, min=2, max=64, update=_update_res)
    strength: FloatProperty(name='Strength', default=1.0, min=0.0, max=1.0, update=_update_strength)
    curve_resolution: IntProperty(name='Curve Resolution', default=24, min=2, max=64, update=_update_curve_res)
    twist: FloatProperty(name='Twist Ramp', subtype='ANGLE', default=0.0, soft_min=-2 * math.pi,
                         soft_max=2 * math.pi, update=_update_ramp,
                         description='Extra twist growing from the start (0) to the end of the curve; '
                                     'added on top of per-point rotations')
    taper: FloatProperty(name='Taper Ramp', default=1.0, min=0.01, soft_min=0.2, soft_max=3.0,
                         update=_update_ramp, description='Thickness factor growing along the curve; '
                                                          'multiplies per-point scale')
    applied_twist: FloatProperty(default=0.0, options={'HIDDEN'})
    applied_taper: FloatProperty(default=1.0, options={'HIDDEN'})
    bend_count: IntProperty(name='Control Points', default=5, min=2, max=64, update=_update_bend_count,
                            description='Bend Curve control points (re-sampled along the current shape)')


def _sync_native(self, context):
    """Live: keep Blender's Proportional Editing in step while a controller is edited."""
    ctrl, _t = controller(context)
    if ctrl is not None and _in_edit(ctrl):
        sync_native_settings(context)


def sync_native_settings(context):
    d = context.scene.mch_deform_tool
    ts = context.scene.tool_settings
    ts.use_proportional_edit = True
    ts.use_proportional_connected = False
    ts.use_proportional_projected = False
    ts.proportional_size = max(d.falloff_radius, 1e-4)
    ts.proportional_edit_falloff = native_falloff(d.falloff_smoothness)
    ts.transform_pivot_point = {'MEDIAN': 'MEDIAN_POINT', 'INDIVIDUAL': 'INDIVIDUAL_ORIGINS',
                                'CURSOR': 'CURSOR'}[d.pivot]


class MCH_PG_DeformTool(bpy.types.PropertyGroup):
    """Scene.mch_deform_tool: tool settings."""
    kind: EnumProperty(name='Controller', items=[
        ('LATTICE', 'Lattice Cage', 'Box of control points around the mesh', 'MOD_LATTICE', 0),
        ('BEND', 'Bend Curve', 'Curve through the mesh: move / rotate (twist) / scale points', 'CURVE_BEZCURVE', 1)],
        default='LATTICE')
    res_x: IntProperty(name='Resolution X', default=4, min=2, max=64)
    res_y: IntProperty(name='Resolution Y', default=4, min=2, max=64)
    res_z: IntProperty(name='Resolution Z', default=4, min=2, max=64)
    padding: FloatProperty(name='Padding', default=0.05, min=0.0, max=1.0, subtype='FACTOR',
                           description='Cage margin around the mesh bounds')
    interpolation: EnumProperty(name='Interpolation', items=[
        ('KEY_BSPLINE', 'Smooth', 'B-Spline: smooth deformation'),
        ('KEY_LINEAR', 'Linear', 'Linear: deformation follows the cage exactly')], default='KEY_BSPLINE')
    bend_count: IntProperty(name='Control Points', default=5, min=2, max=64)
    bend_axis: EnumProperty(name='Axis', items=[
        ('AUTO', 'Auto', 'Longest side of the mesh'), ('X', 'X', ''), ('Y', 'Y', ''), ('Z', 'Z', '')],
        default='AUTO')
    falloff_radius: FloatProperty(name='Falloff Radius', default=0.6, min=0.0, soft_max=10.0, unit='LENGTH',
                                  update=_sync_native,
                                  description='Points within this distance of the selection follow it '
                                              '(Mouse Wheel / Page Up-Down while dragging)')
    falloff_smoothness: FloatProperty(name='Falloff Smoothness', default=0.7, min=0.0, max=1.0,
                                      subtype='FACTOR', update=_sync_native,
                                      description='0 = linear cone, 1 = smooth bell')
    pivot: EnumProperty(name='Pivot', items=[
        ('MEDIAN', 'Selection Centre', 'Rotate / scale around the selected point (centre of several)'),
        ('INDIVIDUAL', 'Each Point', 'Every selected point is its own pivot'),
        ('CURSOR', '3D Cursor', 'Rotate / scale around the 3D cursor')], default='MEDIAN', update=_sync_native)
    orientation: EnumProperty(name='Orientation', items=[
        ('AUTO', 'Auto', 'Lattice: cage axes. Bend Curve: X = curve direction (rotate X = twist)'),
        ('LOCAL', 'Local', 'Controller axes'), ('GLOBAL', 'Global', 'World axes'),
        ('TANGENT', 'Curve Tangent', 'X along the curve at the selection')], default='AUTO')
    gizmo_style: EnumProperty(name='Gizmo', items=[
        ('MECHA', 'Mecha Falloff', 'Mecha gizmo: continuous falloff, Bend twist / radius'),
        ('BLENDER', 'Blender', 'Blender transform gizmo + Proportional Editing (synced to these settings)')],
        default='MECHA')
    show_move: BoolProperty(name='Move', default=True)
    show_rotate: BoolProperty(name='Rotate', default=True)
    show_scale: BoolProperty(name='Scale', default=True)
    show_falloff: BoolProperty(name='Show Falloff', default=True,
                               description='Draw the falloff radius and the influenced points')
    keep_controller: BoolProperty(name='Keep Controller', default=False,
                                  description='Apply keeps the controller object (else it is deleted)')
    step_angle: FloatProperty(name='Step Angle', default=math.radians(15.0), subtype='ANGLE')
    step_scale: FloatProperty(name='Step Scale', default=1.1, min=0.01, max=10.0)


# =============================================================================
# Operators
# =============================================================================


def op_from_settings(context, ctrl, state, mode, axis_index=-1, amount=None):
    d = context.scene.mch_deform_tool
    basis = orientation_basis(ctrl, state, d.orientation)
    op = {'mode': mode, 'radius': d.falloff_radius, 'smoothness': d.falloff_smoothness, 'pivot': d.pivot,
          'cursor': tuple(context.scene.cursor.location), 'basis': basis, 'axis_index': axis_index,
          'move': (0, 0, 0), 'axis': (0, 0, 1), 'angle': 0.0, 'scale': (1, 1, 1)}
    if amount is not None:
        if mode == 'MOVE':
            op['move'] = tuple(basis.col[axis_index] * amount) if axis_index >= 0 else tuple(amount)
        elif mode == 'ROTATE':
            op['axis'] = tuple(basis.col[axis_index]) if axis_index >= 0 else op['axis']
            op['angle'] = amount
        else:
            s = [1.0, 1.0, 1.0]
            if axis_index >= 0:
                s[axis_index] = amount
            else:
                s = [amount] * 3
            op['scale'] = tuple(s)
    return op


class DragLogic:
    """Mouse drag -> transform amount.  Hooks: ``to_screen(world) -> Vector2``,
    ``view_toward()`` (unit world vector pointing at the viewer) and
    ``screen_delta_to_world(pivot, a, b)`` for free move."""

    def drag_begin(self, ctrl, op, mouse):
        self.ctrl = ctrl
        self.state = read_state(ctrl)
        self.op = op
        self.start = Vector(mouse)
        self.pivot = selection_pivot(ctrl, self.state, op['pivot'], op['cursor'])
        if self.pivot is None:
            return False
        self.p2d = Vector(self.to_screen(self.pivot))
        return True

    def drag_axis_world(self):
        k = self.op['axis_index']
        if k >= 0:
            return self.op['basis'].col[k].normalized()
        return self.view_toward().normalized()

    def drag_update(self, mouse, precise=False, snap=False):
        mouse = Vector(mouse)
        if precise:
            mouse = self.start + (mouse - self.start) * 0.1
        mode = self.op['mode']
        k = self.op['axis_index']
        if mode == 'MOVE':
            if k >= 0:
                a = self.drag_axis_world()
                sv = Vector(self.to_screen(self.pivot + a)) - self.p2d
                amt = (mouse - self.start).dot(sv) / max(sv.length_squared, 1e-9)
                if snap:
                    amt = round(amt / 0.1) * 0.1
                self.op['move'] = tuple(a * amt)
            else:
                self.op['move'] = tuple(self.screen_delta_to_world(self.pivot, self.start, mouse))
        elif mode == 'ROTATE':
            v0, v1 = self.start - self.p2d, mouse - self.p2d
            if v0.length < 1e-6 or v1.length < 1e-6:
                return
            ang = math.atan2(v0.x * v1.y - v0.y * v1.x, v0.dot(v1))
            a = self.drag_axis_world()
            if a.dot(self.view_toward()) < 0.0:
                ang = -ang
            if snap:
                step = math.radians(5.0)
                ang = round(ang / step) * step
            self.op['axis'] = tuple(a)
            self.op['angle'] = ang
        else:
            if k >= 0:
                sv = Vector(self.to_screen(self.pivot + self.drag_axis_world())) - self.p2d
                d0 = (self.start - self.p2d).dot(sv)
                f = (mouse - self.p2d).dot(sv) / d0 if abs(d0) > 1e-6 else 1.0
            else:
                d0 = (self.start - self.p2d).length
                f = (mouse - self.p2d).length / d0 if d0 > 1e-6 else 1.0
            if snap:
                f = round(f / 0.1) * 0.1
            s = [1.0, 1.0, 1.0]
            if k >= 0:
                s[k] = f
            else:
                s = [f] * 3
            self.op['scale'] = tuple(s)
        self.drag_apply()

    def drag_apply(self):
        return apply_falloff(self.ctrl, self.state, self.op)

    def drag_cancel(self):
        write_state(self.ctrl, self.state)


def _editing_controller(context):
    ob = context.active_object
    if ob is not None and role(ob) and context.mode in {'EDIT_LATTICE', 'EDIT_CURVE'}:
        return ob
    return None


class MCH_OT_deform_transform(DragLogic, bpy.types.Operator):
    """Move / Rotate / Scale the selected control points with falloff."""
    bl_idname = 'mch.deform_transform'
    bl_label = 'Falloff Transform'
    bl_description = ('Move / Rotate / Scale the selected control points; neighbours within the Falloff '
                      'Radius follow, so a single point also rotates / scales its area')
    bl_options = {'REGISTER', 'UNDO', 'BLOCKING'}

    mode: EnumProperty(name='Mode', items=[('MOVE', 'Move', ''), ('ROTATE', 'Rotate', ''), ('SCALE', 'Scale', '')])
    axis_index: IntProperty(name='Axis', default=-1, min=-1, max=2,
                            description='0/1/2 = gizmo X/Y/Z, -1 = view / free / uniform')
    move: FloatVectorProperty(name='Move', subtype='TRANSLATION', size=3)
    rot_axis: FloatVectorProperty(name='Rotation Axis', size=3, default=(0, 0, 1))
    angle: FloatProperty(name='Angle', subtype='ANGLE')
    scale: FloatVectorProperty(name='Scale', size=3, default=(1, 1, 1))
    radius: FloatProperty(name='Falloff Radius', default=-1.0, soft_min=0.0, unit='LENGTH',
                          description='Negative = use the tool setting')
    smoothness: FloatProperty(name='Falloff Smoothness', default=-1.0, soft_min=0.0, max=1.0)

    @classmethod
    def poll(cls, context):
        return _editing_controller(context) is not None

    # -- non-interactive (buttons, redo panel, tests) --------------------------
    def _op(self, context, ctrl, state):
        op = op_from_settings(context, ctrl, state, self.mode, self.axis_index)
        if self.radius >= 0.0:
            op['radius'] = self.radius
        if self.smoothness >= 0.0:
            op['smoothness'] = self.smoothness
        op['move'] = tuple(self.move)
        op['axis'] = tuple(self.rot_axis)
        op['angle'] = self.angle
        op['scale'] = tuple(self.scale)
        return op

    def execute(self, context):
        ctrl = _editing_controller(context)
        state = read_state(ctrl)
        affected, _n = apply_falloff(ctrl, state, self._op(context, ctrl, state))
        if affected == 0:
            self.report({'WARNING'}, 'Select control points first (click / Shift-click / B)')
            return {'CANCELLED'}
        return {'FINISHED'}

    # -- interactive drag (gizmo) ----------------------------------------------
    def to_screen(self, co):
        from bpy_extras.view3d_utils import location_3d_to_region_2d
        p = location_3d_to_region_2d(self._region, self._rv3d, co)
        return p if p is not None else Vector((0.0, 0.0))

    def view_toward(self):
        return self._rv3d.view_rotation @ Vector((0.0, 0.0, 1.0))

    def screen_delta_to_world(self, pivot, a, b):
        from bpy_extras.view3d_utils import region_2d_to_location_3d
        return region_2d_to_location_3d(self._region, self._rv3d, b, pivot) - \
            region_2d_to_location_3d(self._region, self._rv3d, a, pivot)

    def invoke(self, context, event):
        ctrl = _editing_controller(context)
        if context.region is None or context.region_data is None:
            return self.execute(context)
        self._region, self._rv3d = context.region, context.region_data
        state = read_state(ctrl)
        op = op_from_settings(context, ctrl, state, self.mode, self.axis_index)
        if not self.drag_begin(ctrl, op, (event.mouse_region_x, event.mouse_region_y)):
            self.report({'WARNING'}, 'Select control points first (click / Shift-click / B)')
            return {'CANCELLED'}
        context.window_manager.modal_handler_add(self)
        self._header(context)
        return {'RUNNING_MODAL'}

    def _header(self, context):
        op = self.op
        txt = {'MOVE': 'Move %.3f' % Vector(op['move']).length,
               'ROTATE': 'Rotate %.1f°' % math.degrees(op['angle']),
               'SCALE': 'Scale %.3f' % (sum(op['scale']) / 3.0)}[op['mode']]
        try:
            context.area.header_text_set(f'{txt}   Falloff {op["radius"]:.3f}  (Wheel / PgUp-PgDn)   '
                                         'Shift precise  Ctrl snap  Esc/RMB cancel')
        except AttributeError:
            pass

    def _finish(self, context):
        try:
            context.area.header_text_set(None)
        except AttributeError:
            pass
        op = self.op
        self.move, self.rot_axis, self.angle, self.scale = op['move'], op['axis'], op['angle'], op['scale']
        self.radius, self.smoothness = op['radius'], op['smoothness']

    def modal(self, context, event):
        t = event.type
        if t in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE', 'LEFT_SHIFT', 'RIGHT_SHIFT', 'LEFT_CTRL', 'RIGHT_CTRL'}:
            self._last = (event.mouse_region_x, event.mouse_region_y)
            self.drag_update(self._last, precise=event.shift, snap=event.ctrl)
        elif t in {'WHEELUPMOUSE', 'PAGE_UP', 'WHEELDOWNMOUSE', 'PAGE_DOWN'} and event.value == 'PRESS':
            f = 1.1 if t in {'WHEELUPMOUSE', 'PAGE_UP'} else 1.0 / 1.1
            self.op['radius'] = max(0.0, self.op['radius'] * f) or 0.01
            context.scene.mch_deform_tool.falloff_radius = self.op['radius']
            self.drag_apply()
        elif t in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER'} and event.value in {'RELEASE', 'PRESS'} and \
                not (t == 'LEFTMOUSE' and event.value == 'PRESS'):
            self._finish(context)
            return {'FINISHED'}
        elif t in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            self.drag_cancel()
            try:
                context.area.header_text_set(None)
            except AttributeError:
                pass
            return {'CANCELLED'}
        else:
            return {'RUNNING_MODAL'}
        self._header(context)
        if context.area:
            context.area.tag_redraw()
        return {'RUNNING_MODAL'}


class MCH_OT_deform_step(bpy.types.Operator):
    """Button version of a falloff transform (fixed step)."""
    bl_idname = 'mch.deform_step'
    bl_label = 'Step Transform'
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(items=[('ROTATE', 'Rotate', ''), ('SCALE', 'Scale', '')])
    axis_index: IntProperty(default=0, min=-1, max=2)
    sign: IntProperty(default=1, min=-1, max=1)

    @classmethod
    def description(cls, context, props):
        ax = 'XYZ'[props.axis_index] if props.axis_index >= 0 else 'uniform'
        return f'{props.mode.title()} the selected points ({ax}, {"+" if props.sign > 0 else "-"}) with falloff'

    @classmethod
    def poll(cls, context):
        return _editing_controller(context) is not None

    def execute(self, context):
        ctrl = _editing_controller(context)
        d = context.scene.mch_deform_tool
        state = read_state(ctrl)
        if self.mode == 'ROTATE':
            amount = d.step_angle * self.sign
        else:
            amount = d.step_scale if self.sign > 0 else 1.0 / d.step_scale
        op = op_from_settings(context, ctrl, state, self.mode, self.axis_index, amount)
        affected, _n = apply_falloff(ctrl, state, op)
        if affected == 0:
            self.report({'WARNING'}, 'Select control points first')
            return {'CANCELLED'}
        return {'FINISHED'}


def _save_native(context):
    ts = context.scene.tool_settings
    saved = {'use_proportional_edit': ts.use_proportional_edit,
             'use_proportional_connected': ts.use_proportional_connected,
             'use_proportional_projected': ts.use_proportional_projected,
             'proportional_size': ts.proportional_size,
             'proportional_edit_falloff': ts.proportional_edit_falloff,
             'transform_pivot_point': ts.transform_pivot_point}
    space = context.space_data if getattr(context.space_data, 'type', '') == 'VIEW_3D' else None
    if space is not None:
        for k in ('show_gizmo_object_translate', 'show_gizmo_object_rotate', 'show_gizmo_object_scale'):
            saved[k] = getattr(space, k)
    if SAVED_KEY not in context.scene:
        context.scene[SAVED_KEY] = saved


def _restore_native(context):
    saved = context.scene.get(SAVED_KEY)
    if saved is None:
        return
    saved = dict(saved)
    ts = context.scene.tool_settings
    for k in ('use_proportional_edit', 'use_proportional_connected', 'use_proportional_projected',
              'proportional_size', 'proportional_edit_falloff', 'transform_pivot_point'):
        if k in saved:
            try:
                setattr(ts, k, saved[k])
            except (TypeError, ValueError):
                pass
    space = context.space_data if getattr(context.space_data, 'type', '') == 'VIEW_3D' else None
    if space is not None:
        for k in ('show_gizmo_object_translate', 'show_gizmo_object_rotate', 'show_gizmo_object_scale'):
            if k in saved:
                setattr(space, k, bool(saved[k]))
    del context.scene[SAVED_KEY]


def begin_edit(context, ctrl):
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for o in context.selected_objects:
        o.select_set(False)
    ctrl.hide_set(False)
    ctrl.select_set(True)
    context.view_layer.objects.active = ctrl
    bpy.ops.object.mode_set(mode='EDIT')
    _save_native(context)
    sync_native_settings(context)
    d = context.scene.mch_deform_tool
    space = context.space_data if getattr(context.space_data, 'type', '') == 'VIEW_3D' else None
    if space is not None and d.gizmo_style == 'BLENDER':
        space.show_gizmo_object_translate = d.show_move
        space.show_gizmo_object_rotate = d.show_rotate
        space.show_gizmo_object_scale = d.show_scale


def end_edit(context):
    ctrl = context.active_object
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    _restore_native(context)
    targets = targets_of(ctrl) if role(ctrl) else []
    if targets:
        ctrl.select_set(False)
        for t in targets:
            t.select_set(True)
        context.view_layer.objects.active = targets[0]


def _create(op, context, kind):
    d = context.scene.mch_deform_tool
    meshes = [o for o in context.selected_objects if o.type == 'MESH' and not role(o)]
    act = context.active_object
    if act in meshes:
        meshes.remove(act)
        meshes.insert(0, act)
    if not meshes:
        op.report({'ERROR'}, 'Select a mesh')
        return {'CANCELLED'}
    if kind == 'LATTICE':
        ctrl = create_lattice(context, meshes, (d.res_x, d.res_y, d.res_z), d.padding, d.interpolation)
        msg = f'Lattice Cage {d.res_x}x{d.res_y}x{d.res_z} on {len(meshes)} mesh(es)'
    else:
        ctrl = create_bend(context, meshes[0], d.bend_count, d.bend_axis)
        msg = f'Bend Curve with {d.bend_count} points on {meshes[0].name}'
    if op.edit:
        begin_edit(context, ctrl)
        msg += ': click a point, then drag the gizmo'
    else:
        for o in context.selected_objects:
            o.select_set(False)
        ctrl.select_set(True)
        context.view_layer.objects.active = ctrl
    op.report({'INFO'}, msg)
    return {'FINISHED'}


class MCH_OT_deform_lattice(bpy.types.Operator):
    bl_idname = 'mch.deform_lattice'
    bl_label = 'Create Lattice Cage'
    bl_description = ('Fit an editable Lattice Cage around the selected meshes (one cage can deform several). '
                      'Non-destructive until Apply')
    bl_options = {'REGISTER', 'UNDO'}

    edit: BoolProperty(name='Edit Points Now', default=True)

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        return _create(self, context, 'LATTICE')


class MCH_OT_deform_bend(bpy.types.Operator):
    bl_idname = 'mch.deform_bend'
    bl_label = 'Create Bend Curve'
    bl_description = ('Straight editable Bend Curve through the active mesh along its longest axis: '
                      'move / rotate (twist) / scale its points. Non-destructive until Apply')
    bl_options = {'REGISTER', 'UNDO'}

    edit: BoolProperty(name='Edit Points Now', default=True)

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        return _create(self, context, 'BEND')


class MCH_OT_deform_edit(bpy.types.Operator):
    bl_idname = 'mch.deform_edit'
    bl_label = 'Edit Controller'
    bl_description = 'Enter the controller Edit Mode: click points and use the gizmo (re-edit any time before Apply)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return controller(context)[0] is not None and context.mode == 'OBJECT'

    def execute(self, context):
        ctrl, _t = controller(context)
        begin_edit(context, ctrl)
        return {'FINISHED'}


class MCH_OT_deform_finish_edit(bpy.types.Operator):
    bl_idname = 'mch.deform_finish_edit'
    bl_label = 'Done Editing'
    bl_description = 'Leave point editing (restores your Proportional Editing / gizmo settings)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _editing_controller(context) is not None

    def execute(self, context):
        end_edit(context)
        return {'FINISHED'}


class MCH_OT_deform_gizmo(bpy.types.Operator):
    """v0.9.1: switch Blender's own Move / Rotate / Scale tool (Blender gizmo style)."""
    bl_idname = 'mch.deform_gizmo'
    bl_label = 'Blender Transform Tool'
    bl_description = 'Activate Blender\'s Move / Rotate / Scale tool for the selected controller points'
    bl_options = {'REGISTER', 'INTERNAL'}

    action: EnumProperty(items=[('MOVE', 'Move', ''), ('ROTATE', 'Rotate', ''), ('SCALE', 'Scale', '')],
                         default='MOVE')

    @classmethod
    def poll(cls, context):
        return _editing_controller(context) is not None

    def execute(self, context):
        name = {'MOVE': 'builtin.move', 'ROTATE': 'builtin.rotate', 'SCALE': 'builtin.scale'}[self.action]
        try:
            bpy.ops.wm.tool_set_by_id(name=name, space_type='VIEW_3D')
        except (RuntimeError, TypeError) as ex:
            self.report({'WARNING'}, f'Toolbar unavailable here ({ex}); use G / R / S')
            return {'CANCELLED'}
        return {'FINISHED'}


class MCH_OT_deform_reset(bpy.types.Operator):
    bl_idname = 'mch.deform_reset'
    bl_label = 'Reset Shape'
    bl_description = 'Return every control point to its rest position (keeps the controller)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return controller(context)[0] is not None

    def execute(self, context):
        ctrl, target = controller(context)
        if role(ctrl) == 'LATTICE':
            for p in ctrl.data.points:
                p.co_deform = p.co
        else:
            spl = next((s for s in ctrl.data.splines if s.type == 'BEZIER'), None)
            if spl is None:
                return {'CANCELLED'}
            bps = spl.bezier_points
            length = (bps[-1].co - bps[0].co).length
            if target is not None and target.data.vertices:
                # Rest length = extent of the mesh along the curve's X axis.
                to_curve = ctrl.matrix_world.inverted_safe() @ target.matrix_world
                length = max(max((to_curve @ v.co).x for v in target.data.vertices), 1e-4)
            for bp, co in zip(bps, _bend_points(len(bps), length)):
                bp.handle_left_type = bp.handle_right_type = 'AUTO'
                bp.co = co
                bp.tilt = 0.0
                bp.radius = 1.0
            p = ctrl.mch_deform
            p.applied_twist, p.applied_taper = 0.0, 1.0
            p.twist, p.taper = 0.0, 1.0
        ctrl.data.update_tag()
        return {'FINISHED'}


def _bake_through(context, ob, mod):
    """Evaluated mesh of ``ob`` up to and including ``mod`` (later modifiers
    hidden).  Earlier modifiers are baked too: applying a Lattice that sits
    after a SubD alone would change the result (v0.9.1 behaviour)."""
    mods = list(ob.modifiers)
    idx = mods.index(mod)
    later = [(m, m.show_viewport) for m in mods[idx + 1:]]
    try:
        for m, _v in later:
            m.show_viewport = False
        dg = context.evaluated_depsgraph_get()
        dg.update()
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    finally:
        for m, v in later:
            m.show_viewport = v
    if me is None or len(me.vertices) == 0:
        if me is not None:
            bpy.data.meshes.remove(me)
        raise cg.CutError(f'Empty evaluated mesh: {ob.name}')
    return me, mods[:idx + 1]


def _finish_controller(context, ctrl, apply):
    if _in_edit(ctrl):
        bpy.ops.object.mode_set(mode='OBJECT')
        _restore_native(context)
    pairs = target_mods(ctrl)
    done = []
    if apply:
        if any(o.data.shape_keys for o, _m in pairs):
            raise cg.CutError('Shape keys must be removed or applied before baking the deformation')
        prepared = []
        try:      # prepare every mesh before touching any object (all or nothing)
            for o, m in pairs:
                me, baked = _bake_through(context, o, m)
                prepared.append((o, me, baked))
        except Exception:
            for _o, me, _b in prepared:
                if me.users == 0:
                    bpy.data.meshes.remove(me)
            raise
        for o, me, baked in prepared:
            old = o.data
            o.data = me          # Alt+D twins keep the old mesh
            for m in baked:
                o.modifiers.remove(m)
            if old.users == 0:
                bpy.data.meshes.remove(old)
            done.append(o)
    else:
        for o, m in pairs:
            o.modifiers.remove(m)
            if o not in done:
                done.append(o)
    keep = context.scene.mch_deform_tool.keep_controller and apply
    if not keep:
        data = ctrl.data
        bpy.data.objects.remove(ctrl)
        if data.users == 0:
            (bpy.data.lattices if isinstance(data, bpy.types.Lattice) else bpy.data.curves).remove(data)
    for t in done:
        t.select_set(True)
    if done:
        context.view_layer.objects.active = done[0]
    return done


class MCH_OT_deform_apply(bpy.types.Operator):
    bl_idname = 'mch.deform_apply'
    bl_label = 'Apply Deform'
    bl_description = 'Bake the deformation into the mesh and remove the controller (the only destructive step)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return controller(context)[0] is not None

    def execute(self, context):
        ctrl, _t = controller(context)
        try:
            done = _finish_controller(context, ctrl, True)
        except (cg.CutError, RuntimeError) as ex:
            self.report({'ERROR'}, f'Apply failed, nothing changed: {ex}')
            return {'CANCELLED'}
        self.report({'INFO'}, f'Deform applied to {len(done)} mesh(es)')
        return {'FINISHED'}


class MCH_OT_deform_remove(bpy.types.Operator):
    bl_idname = 'mch.deform_remove'
    bl_label = 'Remove Controller'
    bl_description = 'Delete the controller and its modifier WITHOUT applying (mesh returns to its original shape)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return controller(context)[0] is not None

    def execute(self, context):
        ctrl, _t = controller(context)
        _finish_controller(context, ctrl, False)
        return {'FINISHED'}


# =============================================================================
# Gizmo (MECHA style)
# =============================================================================

_COLORS = ((0.96, 0.2, 0.32), (0.55, 0.86, 0.0), (0.16, 0.56, 0.96))


def _gizmo_frame(context):
    ctrl = _editing_controller(context)
    if ctrl is None:
        return None
    state = read_state(ctrl)
    d = context.scene.mch_deform_tool
    pivot = selection_pivot(ctrl, state, d.pivot, context.scene.cursor.location)
    if pivot is None:
        return None
    return ctrl, state, pivot, orientation_basis(ctrl, state, d.orientation)


def _axis_matrix(pivot, axis):
    rot = Vector((0, 0, 1)).rotation_difference(axis).to_matrix().to_4x4()
    return Matrix.Translation(pivot) @ rot


class MCH_GGT_deform(bpy.types.GizmoGroup):
    bl_idname = 'MCH_GGT_deform'
    bl_label = 'Mecha Deform Gizmo'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D', 'PERSISTENT', 'SHOW_MODAL_ALL'}

    @classmethod
    def poll(cls, context):
        d = getattr(context.scene, 'mch_deform_tool', None)
        if d is None or d.gizmo_style != 'MECHA' or _editing_controller(context) is None:
            return False
        return _gizmo_frame(context) is not None

    def _add(self, kind, mode, axis, color, style=None):
        gz = self.gizmos.new(kind)
        props = gz.target_set_operator('mch.deform_transform')
        props.mode = mode
        props.axis_index = axis
        gz.color = color
        gz.alpha = 0.85
        gz.color_highlight = (1.0, 1.0, 1.0)
        gz.alpha_highlight = 1.0
        gz.use_draw_modal = True
        if style:
            gz.draw_style = style
        return gz

    def setup(self, context):
        self.moves = [self._add('GIZMO_GT_arrow_3d', 'MOVE', k, _COLORS[k]) for k in range(3)]
        self.free = self._add('GIZMO_GT_move_3d', 'MOVE', -1, (1.0, 1.0, 1.0), 'RING_2D')
        self.free.scale_basis = 0.12
        self.rots = [self._add('GIZMO_GT_dial_3d', 'ROTATE', k, _COLORS[k]) for k in range(3)]
        for gz in self.rots:
            gz.draw_options = {'CLIP'}
            gz.scale_basis = 1.0
        self.view_rot = self._add('GIZMO_GT_dial_3d', 'ROTATE', -1, (1.0, 1.0, 1.0))
        self.view_rot.scale_basis = 1.15
        self.scales = [self._add('GIZMO_GT_arrow_3d', 'SCALE', k, _COLORS[k], 'BOX') for k in range(3)]
        for gz in self.scales:
            gz.length = 0.55
        self.uniform = self._add('GIZMO_GT_move_3d', 'SCALE', -1, (1.0, 0.75, 0.3), 'RING_2D')
        self.uniform.scale_basis = 1.35

    def draw_prepare(self, context):
        frame = _gizmo_frame(context)
        if frame is None:
            return
        _ctrl, _state, pivot, basis = frame
        d = context.scene.mch_deform_tool
        for k in range(3):
            axis = basis.col[k].normalized()
            for group, show in ((self.moves, d.show_move), (self.rots, d.show_rotate), (self.scales, d.show_scale)):
                group[k].matrix_basis = _axis_matrix(pivot, axis)
                group[k].hide = not show
        rv3d = context.region_data
        view = rv3d.view_rotation.to_matrix().to_4x4() if rv3d else Matrix.Identity(4)
        for gz, show in ((self.free, d.show_move), (self.view_rot, d.show_rotate), (self.uniform, d.show_scale)):
            gz.matrix_basis = Matrix.Translation(pivot) @ view
            gz.hide = not show


# =============================================================================
# Falloff overlay
# =============================================================================

_draw_handle = None


def _draw_falloff():
    try:
        context = bpy.context
        d = context.scene.mch_deform_tool
        ctrl = _editing_controller(context)
        if ctrl is None or not d.show_falloff:
            return
        import gpu
        from gpu_extras.batch import batch_for_shader
        state = read_state(ctrl)
        pos, sel = _positions(ctrl, state)
        if not any(sel):
            return
        weights, _n = compute_weights(pos, sel, d.falloff_radius, d.falloff_smoothness)
        rv3d = context.region_data
        rot = rv3d.view_rotation if rv3d else Quaternion()
        ring = [rot @ Vector((math.cos(a), math.sin(a), 0.0)) for a in
                (2 * math.pi * i / 48 for i in range(49))]
        sh = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        gpu.state.line_width_set(1.5)
        sh.bind()
        sh.uniform_float('color', (1.0, 0.62, 0.16, 0.8))
        for p, s in zip(pos, sel):
            if s:
                batch_for_shader(sh, 'LINE_STRIP', {'pos': [p + v * d.falloff_radius for v in ring]}).draw(sh)
        pts = [p for p, w, s in zip(pos, weights, sel) if w > 0.0 and not s]
        cols = [(1.0, 0.62, 0.16, 0.25 + 0.75 * w) for w, s in zip(weights, sel) if w > 0.0 and not s]
        if pts:
            try:
                psh = gpu.shader.from_builtin('POINT_FLAT_COLOR')
            except (ValueError, SystemError):
                psh = gpu.shader.from_builtin('FLAT_COLOR')
            gpu.state.point_size_set(7.0)
            batch_for_shader(psh, 'POINTS', {'pos': pts, 'color': cols}).draw(psh)
        gpu.state.blend_set('NONE')
    except Exception:   # never break viewport drawing
        pass


# =============================================================================
# Panel (drawn by ui_tool_settings.draw_pose: tool id POSE = "Deform")
# =============================================================================


def _hint(layout, *lines):
    col = layout.column(align=True)
    col.scale_y = 0.8
    for text in lines:
        col.label(text=text)


def draw(layout, context):
    d = context.scene.mch_deform_tool
    ctrl, target = controller(context)
    editing = _editing_controller(context) is not None
    if ctrl is None:
        layout.row(align=True).prop(d, 'kind', expand=True)
        box = layout.box()
        box.label(text='New ' + ('Lattice Cage' if d.kind == 'LATTICE' else 'Bend Curve'))
        col = box.column(align=True)
        if d.kind == 'LATTICE':
            col.prop(d, 'res_x', slider=True)
            col.prop(d, 'res_y', slider=True)
            col.prop(d, 'res_z', slider=True)
            box.prop(d, 'padding', slider=True)
            box.prop(d, 'interpolation', text='')
        else:
            col.prop(d, 'bend_count')
            box.row(align=True).prop(d, 'bend_axis', expand=True)
        row = layout.row()
        row.scale_y = 1.5
        if d.kind == 'LATTICE':
            row.operator('mch.deform_lattice', icon='MOD_LATTICE')
        else:
            row.operator('mch.deform_bend', icon='CURVE_BEZCURVE')
        _hint(layout, 'Select a mesh, then Create', 'The mesh only gets a modifier (non-destructive)')
    else:
        kind = role(ctrl)
        box = layout.box()
        box.label(text=('LATTICE CAGE: ' if kind == 'LATTICE' else 'BEND CURVE: ') + ctrl.name,
                  icon='MOD_LATTICE' if kind == 'LATTICE' else 'CURVE_BEZCURVE')
        if target is not None:
            box.label(text='Deforms: ' + target.name, icon='MESH_DATA')
        p = ctrl.mch_deform
        col = box.column(align=True)
        if kind == 'LATTICE':
            col.prop(p, 'res_x', slider=True)
            col.prop(p, 'res_y', slider=True)
            col.prop(p, 'res_z', slider=True)
            box.prop(p, 'strength', slider=True)
        else:
            col.prop(p, 'bend_count')
            col.prop(p, 'curve_resolution')
            sub = box.column(align=True)
            sub.prop(p, 'twist')
            sub.prop(p, 'taper')
        row = layout.row()
        row.scale_y = 1.5
        if editing:
            row.operator('mch.deform_finish_edit', icon='CHECKMARK')
        else:
            row.operator('mch.deform_edit', icon='EDITMODE_HLT')
    box = layout.box()
    box.label(text='Falloff', icon='PROP_ON')
    col = box.column(align=True)
    col.prop(d, 'falloff_radius')
    col.prop(d, 'falloff_smoothness', slider=True)
    box.prop(d, 'pivot')
    box.prop(d, 'orientation')
    box.prop(d, 'show_falloff')
    box = layout.box()
    box.label(text='Gizmo', icon='ORIENTATION_GIMBAL')
    box.row(align=True).prop(d, 'gizmo_style', expand=True)
    row = box.row(align=True)
    row.prop(d, 'show_move', toggle=True)
    row.prop(d, 'show_rotate', toggle=True)
    row.prop(d, 'show_scale', toggle=True)
    if editing and d.gizmo_style == 'BLENDER':
        row = box.row(align=True)
        for action, icon in (('MOVE', 'OBJECT_ORIGIN'), ('ROTATE', 'DRIVER_ROTATIONAL_DIFFERENCE'),
                             ('SCALE', 'FULLSCREEN_ENTER')):
            row.operator('mch.deform_gizmo', text=action.title(), icon=icon).action = action
    if editing:
        box = layout.box()
        box.label(text='Step (selected points + falloff)', icon='DRIVER_ROTATIONAL_DIFFERENCE')
        for k, axis in enumerate('XYZ'):
            row = box.row(align=True)
            row.label(text='Rotate ' + axis)
            for sign, icon in ((-1, 'TRIA_LEFT'), (1, 'TRIA_RIGHT')):
                op = row.operator('mch.deform_step', text='', icon=icon)
                op.mode, op.axis_index, op.sign = 'ROTATE', k, sign
        row = box.row(align=True)
        row.label(text='Scale')
        for sign, icon in ((-1, 'REMOVE'), (1, 'ADD')):
            op = row.operator('mch.deform_step', text='', icon=icon)
            op.mode, op.axis_index, op.sign = 'SCALE', -1, sign
        col = box.column(align=True)
        col.prop(d, 'step_angle')
        col.prop(d, 'step_scale')
    if ctrl is not None:
        row = layout.row(align=True)
        row.operator('mch.deform_reset', icon='LOOP_BACK')
        row.operator('mch.deform_remove', icon='X')
        row = layout.row()
        row.scale_y = 1.3
        row.operator('mch.deform_apply', icon='CHECKMARK')
        layout.prop(d, 'keep_controller')
    if editing:
        _hint(layout, 'Click a point (Shift = add, B = box)', 'Drag gizmo: arrows move, rings rotate,',
              'boxes / outer ring scale', 'Wheel while dragging: falloff radius',
              'Bend: rotate around X (curve) = twist')


@bpy.app.handlers.persistent
def _migrate_on_load(_dummy=None):
    """v0.9.1 files: its Twist/Taper set tilt/radius absolutely; mark them as
    already applied so the additive ramp does not double them."""
    for ob in bpy.data.objects:
        if role(ob) == 'BEND' and hasattr(ob, 'mch_deform'):
            p = ob.mch_deform
            if 'applied_twist' not in p:
                p.applied_twist = p.twist
                p.applied_taper = p.taper


CLASSES = (MCH_PG_DeformObject, MCH_PG_DeformTool, MCH_OT_deform_transform, MCH_OT_deform_step,
           MCH_OT_deform_lattice, MCH_OT_deform_bend, MCH_OT_deform_edit, MCH_OT_deform_finish_edit,
           MCH_OT_deform_gizmo, MCH_OT_deform_reset, MCH_OT_deform_apply, MCH_OT_deform_remove, MCH_GGT_deform)


def register():
    global _draw_handle
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_deform_tool = PointerProperty(type=MCH_PG_DeformTool)
    bpy.types.Object.mch_deform = PointerProperty(type=MCH_PG_DeformObject)
    if _migrate_on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_migrate_on_load)
    if not bpy.app.background:
        _draw_handle = bpy.types.SpaceView3D.draw_handler_add(_draw_falloff, (), 'WINDOW', 'POST_VIEW')


def unregister():
    global _draw_handle
    if _migrate_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_migrate_on_load)
    if _draw_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, 'WINDOW')
        _draw_handle = None
    if hasattr(bpy.types.Scene, 'mch_deform_tool'):
        del bpy.types.Scene.mch_deform_tool
    if hasattr(bpy.types.Object, 'mch_deform'):
        del bpy.types.Object.mch_deform
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
