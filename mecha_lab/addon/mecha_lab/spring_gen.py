"""0.24.294 Spring Generator (user: "직선 어레이 메뉴처럼 스프링 제네레이터도 - 내가 원하는 대로 그으면 거기에 스프링이
생기는데 두께나 폭 이런 건 내가 추후에 정해서 엔터 치거나 어플라이 누르면 확정").

Draw a line (any of the shared shapes, like Line Array): a coil spring along it.

* Path: Straight - from where the drawing starts to where it ends (Snap: Free / Straight / Diagonal); Follow - along
  the drawn path as it is (a bent spring).  A straight line whose both ends land on parts goes from one part's surface
  to the other's (in 3D); otherwise the spring lies in the plane through the surface under its start (or the 3D
  cursor) facing the view.
* The spring stays live ("Spring" object, its own settings): Width (outer diameter), Wire (thickness), Coils, Closed
  Ends (tight end turns), End Width (a cone), Wire profile (Round / Square / Flat), Left / Right hand, resolution -
  change them after drawing; Enter (or Apply) keeps it as a plain mesh.
* Width / Wire 0 in the tool settings = Auto: a size from the line's length.
"""
from __future__ import annotations

import json
import math

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty
from mathutils import Vector

KEY = 'mch_spring'               # on a live spring: its axis path (json)
CLOSED_SHAPES = {'RECT', 'CIRCLE', 'ELLIPSE', 'POLY', 'POLYGON', 'CUSTOM', 'STAR', 'HEX'}
MAX_RINGS = 20000


# ---- the axis ---------------------------------------------------------------------------------------------------

def _resample(pts, n):
    """``n`` + 1 points evenly along the polyline ``pts`` (Vectors)."""
    seg = [(a, b, (b - a).length) for a, b in zip(pts, pts[1:])]
    total = sum(s[2] for s in seg)
    if total <= 1e-12:
        return [pts[0].copy() for _ in range(n + 1)], 0.0
    out = []
    for i in range(n + 1):
        d = total * i / n
        acc = 0.0
        for a, b, ln in seg:
            if ln > 1e-12 and acc + ln >= d - 1e-12:
                out.append(a.lerp(b, min(1.0, max(0.0, (d - acc) / ln))))
                break
            acc += ln
        else:
            out.append(pts[-1].copy())
    return out, total


def _smooth(pts, rounds=2):
    """A drawn (hand) path softened a little, its ends kept."""
    if len(pts) < 3:
        return pts
    for _ in range(rounds):
        pts = [pts[0]] + [(pts[i - 1] + pts[i] * 2.0 + pts[i + 1]) * 0.25 for i in range(1, len(pts) - 1)] + [pts[-1]]
    return pts


def axis_frames(path, samples, up_hint):
    """[(point, tangent, normal, binormal)] at ``samples`` + 1 even steps along ``path`` (parallel transport: no
    twist on a bent spring), and the path's length."""
    pts, total = _resample([Vector(p) for p in path], samples)
    tans = []
    for i in range(len(pts)):
        a, b = pts[max(0, i - 1)], pts[min(len(pts) - 1, i + 1)]
        t = b - a
        tans.append(t.normalized() if t.length > 1e-12 else (tans[-1] if tans else Vector((1, 0, 0))))
    n = Vector(up_hint) - tans[0] * Vector(up_hint).dot(tans[0])
    if n.length < 1e-6:
        n = tans[0].orthogonal()
    n.normalize()
    out = []
    for i, (p, t) in enumerate(zip(pts, tans)):
        if i:
            n = n - t * n.dot(t)
            n = n.normalized() if n.length > 1e-9 else t.orthogonal().normalized()
        out.append((p, t, n, t.cross(n).normalized()))
    return out, total


# ---- the spring mesh ------------------------------------------------------------------------------------------------

def coil_params(length, st):
    """(turns in all, axial position s(u) for u in turns, coil radius at s)."""
    wire = max(1e-5, st.wire)
    ec = max(0.0, st.end_coils)
    coils = max(0.25, st.coils)
    body = length - wire - 2.0 * ec * wire
    if body < coils * wire * 1.05:                    # (too short for the coils: they touch, ends share the room)
        ec = 0.0
        body = max(length - wire, 1e-6)
    pitch = body / coils
    total = 2.0 * ec + coils

    def s_of(u):
        if u <= ec:
            return wire * 0.5 + u * wire
        if u <= ec + coils:
            return wire * 0.5 + ec * wire + (u - ec) * pitch
        return wire * 0.5 + ec * wire + body + (u - ec - coils) * wire
    r0 = max(st.width * 0.5 - wire * 0.5, wire * 0.25)
    r1 = max(st.width * 0.5 * st.end_width - wire * 0.5, wire * 0.25)

    def r_of(s):
        k = min(1.0, max(0.0, s / max(length, 1e-9)))
        return r0 + (r1 - r0) * k
    return total, s_of, r_of


def profile(st):
    """The wire's cross-section: [(x radial, y along)] round the wire's centre."""
    w = max(1e-5, st.wire) * 0.5
    if st.profile == 'SQUARE':
        return [(w, -w), (w, w), (-w, w), (-w, -w)]
    if st.profile == 'FLAT':                          # (a flat band: wide along the axis, thin across)
        h = w * 0.45
        return [(h, -w * 1.4), (h, w * 1.4), (-h, w * 1.4), (-h, -w * 1.4)]
    n = max(3, int(st.sides))
    return [(w * math.cos(2 * math.pi * k / n), w * math.sin(2 * math.pi * k / n)) for k in range(n)]


def build(path, up_hint, st):
    """(verts, faces) of the spring round the axis ``path`` (object space)."""
    length = sum((Vector(b) - Vector(a)).length for a, b in zip(path, path[1:]))
    if length <= 1e-6:
        return [], []
    total, s_of, r_of = coil_params(length, st)
    per = max(6, int(st.resolution))
    rings = min(MAX_RINGS, max(8, int(math.ceil(total * per))))
    frames, flen = axis_frames(path, max(64, min(4000, rings)), up_hint)
    hand = 1.0 if st.hand == 'RIGHT' else -1.0
    prof = profile(st)
    m = len(prof)
    centres = []
    for i in range(rings + 1):
        u = total * i / rings
        s = s_of(u)
        f = frames[min(len(frames) - 1, max(0, int(round(s / max(flen, 1e-9) * (len(frames) - 1)))))]
        p, t, n, b = f
        a = 2.0 * math.pi * u * hand
        radial = n * math.cos(a) + b * math.sin(a)
        centres.append((p + radial * r_of(s), radial, t))
    verts, faces = [], []
    for i, (c, radial, t) in enumerate(centres):
        a_, b_ = centres[max(0, i - 1)][0], centres[min(rings, i + 1)][0]
        tang = (b_ - a_)
        tang = tang.normalized() if tang.length > 1e-12 else t
        x = radial - tang * radial.dot(tang)
        x = x.normalized() if x.length > 1e-9 else radial
        y = tang.cross(x).normalized()
        if y.dot(t) < 0:
            y = -y
        for px, py in prof:
            verts.append(tuple(c + x * px + y * py))
    for i in range(rings):
        r0, r1 = i * m, (i + 1) * m
        for k in range(m):
            k1 = (k + 1) % m
            faces.append((r0 + k, r0 + k1, r1 + k1, r1 + k))
    if st.caps:
        faces.append(tuple(reversed(range(m))))
        faces.append(tuple(rings * m + k for k in range(m)))
    return verts, faces


# ---- the live object ------------------------------------------------------------------------------------------------

def _data(ob):
    try:
        return json.loads(ob.get(KEY, '{}'))
    except (ValueError, TypeError):
        return {}


def is_spring(ob):
    return ob is not None and ob.type == 'MESH' and bool(ob.get(KEY))


def rebuild(ob):
    d = _data(ob)
    if not d:
        return 0
    path = [Vector(p) for p in d['path']]
    verts, faces = build(path, Vector(d.get('view', (0, 0, 1))), ob.mch_spring)
    me = ob.data
    me.clear_geometry()
    me.from_pydata(verts, [], faces)
    me.validate(clean_customdata=False)
    try:
        me.shade_smooth()
    except AttributeError:
        for p in me.polygons:
            p.use_smooth = True
    if ob.mch_spring.profile != 'ROUND':
        _sharp_corners(me, len(profile(ob.mch_spring)))
    me.update()
    ob.update_tag()
    return len(me.polygons)


def _sharp_corners(me, m):
    """Square / Flat wire: its corner lines sharp (flat sides), the turns stay smooth."""
    import numpy as np
    ne = len(me.edges)
    ev = np.empty(ne * 2, np.int32)
    me.edges.foreach_get('vertices', ev)
    ev = ev.reshape(-1, 2)
    along = (ev[:, 1] - ev[:, 0]) % m == 0        # an edge from ring to ring: a corner line of the wire
    att = me.attributes.get('sharp_edge') or me.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE')
    att.data.foreach_set('value', along.tolist())


def _upd(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and is_spring(ob):
        rebuild(ob)


def _upd_path(self, context):
    """Straight / Follow / Snap changed on a live spring: its axis made again from the stored drawing."""
    ob = self.id_data
    if not (isinstance(ob, bpy.types.Object) and is_spring(ob)):
        return
    d = _data(ob)
    raw = [Vector(p) for p in d.get('raw', [])]
    if len(raw) < 2 or d.get('ends3d'):
        return
    if self.path == 'STRAIGHT':
        end = raw[-1]
        if self.snap != 'FREE':
            from .line_array import snap_screen
            ax, ay = Vector(d['right']), Vector(d['up'])
            v = end - raw[0]
            sx, sy = snap_screen((0.0, 0.0), (v.dot(ax), v.dot(ay)), self.snap)
            end = raw[0] + ax * sx + ay * sy
        path = [raw[0], end]
    else:
        path = _smooth(raw)
    d['path'] = [tuple(p) for p in path]
    ob[KEY] = json.dumps(d)
    rebuild(ob)


class MCH_PG_Spring(bpy.types.PropertyGroup):
    path: EnumProperty(name='Path', default='STRAIGHT', update=_upd_path, items=[
        ('STRAIGHT', 'Straight', 'A straight spring from where the drawing starts to where it ends'),
        ('FOLLOW', 'Follow', 'Along the drawn path as it is (a bent spring)')])
    snap: EnumProperty(name='Snap', default='FREE', update=_upd_path, items=[
        ('FREE', 'Free', 'The line at any angle'),
        ('STRAIGHT', 'Straight', 'The line at 0 / 90 deg on the screen'),
        ('DIAG', 'Diagonal', 'The line at every 45 deg on the screen')])
    width: FloatProperty(name='Width', default=0.0, min=0.0, soft_max=2.0, subtype='DISTANCE', update=_upd,
                         description='Outer diameter of the coils (tool setting 0 = Auto: from the line length)')
    wire: FloatProperty(name='Wire', default=0.0, min=0.0, soft_max=0.5, subtype='DISTANCE', update=_upd,
                        description='Thickness of the wire (tool setting 0 = Auto: from the width)')
    coils: FloatProperty(name='Coils', default=8.0, min=0.25, soft_max=40.0, max=400.0, step=50, update=_upd,
                         description='Turns between the closed ends')
    end_coils: FloatProperty(name='Closed Ends', default=1.0, min=0.0, soft_max=3.0, max=10.0, step=25, update=_upd,
                             description='Tight turns at each end (wire touching wire, like a real compression spring)')
    end_width: FloatProperty(name='End Width', default=1.0, min=0.05, soft_max=2.0, max=5.0, update=_upd,
                             subtype='FACTOR', description='Width at the end of the line x this (1: straight, '
                                                           'less: a cone)')
    profile: EnumProperty(name='Wire Profile', default='ROUND', update=_upd, items=[
        ('ROUND', 'Round', 'Round wire'),
        ('SQUARE', 'Square', 'Square wire'),
        ('FLAT', 'Flat', 'A flat band (wide along the spring)')])
    hand: EnumProperty(name='Hand', default='RIGHT', update=_upd, items=[
        ('RIGHT', 'Right', 'Right-hand coil'), ('LEFT', 'Left', 'Left-hand coil')])
    resolution: IntProperty(name='Resolution', default=24, min=6, max=96, update=_upd,
                            description='Steps per turn')
    sides: IntProperty(name='Wire Sides', default=10, min=3, max=32, update=_upd,
                       description='Round wire: sides of its cross-section')
    caps: BoolProperty(name='Caps', default=True, update=_upd, description='The wire ends closed')


AUTO_WIDTH = 0.22        # x the line length
AUTO_WIRE = 0.12         # x the width


def _hit(context, projector, xy):
    from . import target_rules as tr
    o, d = projector.ray(xy)
    try:
        hit, loc, _n, _i, ob, _m = tr.scene_ray(context, context.evaluated_depsgraph_get(), o, d)
    except (RuntimeError, ReferenceError, AttributeError):
        return None
    if hit and ob is not None and not is_spring(ob.original):
        return loc
    return None


def make(context, projector, spts_raw, shape, st):
    """A live spring from the drawing (screen points).  Returns the new object, or None (too short)."""
    from .line_array import screen_path, world_path
    spts, closed = screen_path(spts_raw, shape, st.path, st.snap)
    if closed:                                        # (an outline: the spring goes round it)
        spts = list(spts) + [spts[0]]
    if len(spts) < 2:
        return None
    no = Vector(projector.view_dir).normalized()
    h0 = _hit(context, projector, spts[0])
    h1 = _hit(context, projector, spts[-1]) if st.path == 'STRAIGHT' and not closed else None
    ends3d = h0 is not None and h1 is not None and (h1 - h0).length > 1e-6
    origin = h0 if h0 is not None else context.scene.cursor.location.copy()
    if ends3d:
        wpath = [h0, h1]
    else:
        wpath, no = world_path(projector, spts, origin)
    raw, _no = world_path(projector, [tuple(p) for p in spts_raw], origin)
    if len(wpath) < 2:
        return None
    if st.path == 'FOLLOW' and not ends3d:
        wpath = _smooth(wpath)
    start = wpath[0].copy()
    length = sum((b - a).length for a, b in zip(wpath, wpath[1:]))
    if length < 1e-5:
        return None
    try:
        right = projector.rv3d.view_rotation @ Vector((1, 0, 0))
    except AttributeError:
        right = (getattr(projector, 'rot', None) @ Vector((1, 0, 0))) if hasattr(projector, 'rot') else Vector((1, 0, 0))
    up = right.cross(no).normalized() if right.cross(no).length > 1e-9 else Vector((0, 0, 1))
    me = bpy.data.meshes.new('Spring')
    ob = bpy.data.objects.new('Spring', me)
    (context.collection or context.scene.collection).objects.link(ob)
    ob.location = start
    # path / raw: offsets from the start; view: the frame's first normal (toward the viewer); right / up: the
    # drawing's screen axes (Snap)
    ob[KEY] = json.dumps({'path': [tuple(p - start) for p in wpath],
                          'raw': [tuple(p - start) for p in (raw or wpath)],
                          'view': tuple(no), 'right': tuple(right.normalized()), 'up': tuple(up), 'ends3d': ends3d})
    sp = ob.mch_spring
    for k in ('path', 'snap', 'coils', 'end_coils', 'end_width', 'profile', 'hand', 'resolution', 'sides', 'caps'):
        try:
            setattr(sp, k, getattr(st, k))
        except (AttributeError, TypeError):
            pass
    width = st.width if st.width > 0 else max(length * AUTO_WIDTH, 1e-4)
    wire = st.wire if st.wire > 0 else width * AUTO_WIRE
    sp.width = width
    sp.wire = min(wire, width * 0.45)
    mat = _material()
    if mat is not None:
        me.materials.append(mat)
    rebuild(ob)
    return ob


def _material():
    mat = bpy.data.materials.get('MCH Spring Steel')
    if mat is None:
        mat = bpy.data.materials.new('MCH Spring Steel')
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get('Principled BSDF')
        if bsdf is not None:
            bsdf.inputs['Base Color'].default_value = (0.35, 0.36, 0.38, 1.0)
            bsdf.inputs['Metallic'].default_value = 1.0
            bsdf.inputs['Roughness'].default_value = 0.32
        mat.diffuse_color = (0.35, 0.36, 0.38, 1.0)
    return mat


def perform(context, pts, shape, projector):
    """The drawing finished: a live spring along it.  Returns the report."""
    if len(pts) < 2:
        return 'Spring: draw a line (2 points or more)'
    st = context.scene.mch_spring
    ob = make(context, projector, pts, shape, st)
    if ob is None:
        return 'Spring: the line is too short'
    for o in list(context.selected_objects):
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    sp = ob.mch_spring
    return (f'Spring: {sp.coils:g} coils, width {sp.width:.3g}, wire {sp.wire:.3g} '
            '(change Width / Wire / Coils now; Enter or Apply keeps it)')


def apply(ob):
    """The live spring kept as a plain mesh."""
    if not is_spring(ob):
        return False
    del ob[KEY]
    return True


class MCH_OT_spring_apply(bpy.types.Operator):
    """Apply: the selected live springs kept as they are (plain meshes, no longer live)"""
    bl_idname = 'mch.spring_apply'
    bl_label = 'Apply Spring'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(is_spring(o) for o in context.selected_objects) or is_spring(context.active_object)

    def execute(self, context):
        obs = [o for o in context.selected_objects if is_spring(o)]
        if is_spring(context.active_object) and context.active_object not in obs:
            obs.append(context.active_object)
        n = sum(1 for o in obs if apply(o))
        self.report({'INFO'}, f'Spring: {n} applied')
        return {'FINISHED'}


def draw(layout, context):
    """The tool window: the settings for the next spring, or those of the selected live spring."""
    ob = context.active_object
    live = is_spring(ob)
    st = ob.mch_spring if live else context.scene.mch_spring
    box = layout.box()
    col = box.column(align=True)
    col.label(text=('Spring: ' + ob.name) if live else 'Spring', icon='MOD_SCREW')
    col.prop(st, 'path', expand=True)
    if st.path == 'STRAIGHT':
        col.prop(st, 'snap', expand=True)
    col = box.column(align=True)
    col.prop(st, 'width', text='Width (0: Auto)' if not live else 'Width')
    col.prop(st, 'wire', text='Wire (0: Auto)' if not live else 'Wire')
    col.prop(st, 'coils')
    col.prop(st, 'end_coils')
    col.prop(st, 'end_width')
    col = box.column(align=True)
    col.prop(st, 'profile', expand=True)
    col.prop(st, 'hand', expand=True)
    row = col.row(align=True)
    row.prop(st, 'resolution')
    if st.profile == 'ROUND':
        row.prop(st, 'sides')
    col.prop(st, 'caps')
    if live:
        box.operator('mch.spring_apply', text='Apply (Enter)', icon='CHECKMARK')
        box.label(text='Change it now; Enter or Apply keeps it')
    else:
        box.label(text='Draw a line: a spring along it')


CLASSES = (MCH_PG_Spring, MCH_OT_spring_apply)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_spring = bpy.props.PointerProperty(type=MCH_PG_Spring)
    bpy.types.Object.mch_spring = bpy.props.PointerProperty(type=MCH_PG_Spring)


def unregister():
    for t in (bpy.types.Scene, bpy.types.Object):
        if hasattr(t, 'mch_spring'):
            delattr(t, 'mch_spring')
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
