"""0.23.0 Tube / Curve tool (Nomad-style): a live mesh along clicked points.

Pick "Tube" (bottom toolbar / Shift+Q pie) and click in the 3D View:
    click              add a point (on the mesh under the mouse, else in the air
                       at the depth of the last point / 3D cursor)
    click the line     insert a point there        drag a point   move it
    Ctrl+Wheel on a point   that point's radius    X / Delete on a point  remove it
    Enter / Right click / Esc   done (the tube stays live)
    Middle mouse / wheel   view as usual

The result is a solid mesh right away (no black curve line) and stays live
until Apply (N panel / tool panel):
    Tube    radius, start / end taper, profile Round / Square / Flat (ratio),
            sides, cap Flat / Round / Open, hole (pipe wall), rotate, twist
    Repeat  copies of an object (or a sphere) along the curve: count, size,
            follow the radius, align to the curve
    Curve   Smooth (through the points) / B-Spline (soft, like Nomad) / Linear,
            Closed, resolution

``path_samples`` / ``tube_mesh`` / ``repeat_mesh`` are pure (tested headless).
"""
from __future__ import annotations

import math

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty
from mathutils import Matrix, Vector

PTS_KEY = 'mch_tube_pts'          # object custom prop: flat [x, y, z, r, ...] in object space
COLL = 'Mecha Tubes'
HIT_PX = 12.0
_draw_ops = []


# -----------------------------------------------------------------------------
# Pure geometry
# -----------------------------------------------------------------------------


def _catmull(p0, p1, p2, p3, t):
    t2, t3 = t * t, t * t * t
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)


def _bspline(p0, p1, p2, p3, t):
    t2, t3 = t * t, t * t * t
    b0 = (1 - t) ** 3 / 6.0
    b1 = (3 * t3 - 6 * t2 + 4) / 6.0
    b2 = (-3 * t3 + 3 * t2 + 3 * t + 1) / 6.0
    b3 = t3 / 6.0
    return p0 * b0 + p1 * b1 + p2 * b2 + p3 * b3


def path_samples(points, radii, closed=False, spline='SMOOTH', res=12):
    """[(position Vector, radius)] along the curve through / near the control points."""
    pts = [Vector(p) for p in points]
    rad = [float(r) for r in radii]
    n = len(pts)
    if n == 0:
        return []
    if n == 1:
        return [(pts[0].copy(), rad[0])]
    res = max(1, int(res))
    out = []
    if spline == 'LINEAR':
        segs = n if closed else n - 1
        for i in range(segs):
            a, b = pts[i], pts[(i + 1) % n]
            ra, rb = rad[i], rad[(i + 1) % n]
            for k in range(res):
                t = k / res
                out.append((a.lerp(b, t), ra + (rb - ra) * t))
        if not closed:
            out.append((pts[-1].copy(), rad[-1]))
        return out
    if closed:
        P = pts
        R = rad
        idx = lambda i: i % n          # noqa: E731
        segs = n
    else:
        if spline == 'BSPLINE':        # clamp: repeat the end points so the curve reaches them
            P = [pts[0], pts[0]] + pts + [pts[-1], pts[-1]]
            R = [rad[0], rad[0]] + rad + [rad[-1], rad[-1]]
            segs = len(P) - 3
        else:
            P = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
            R = [rad[0]] + rad + [rad[-1]]
            segs = n - 1
        idx = lambda i: i              # noqa: E731
    f = _bspline if spline == 'BSPLINE' else _catmull
    for s in range(segs):
        if closed:
            i0, i1, i2, i3 = idx(s - 1), idx(s), idx(s + 1), idx(s + 2)
        else:
            i0, i1, i2, i3 = s, s + 1, s + 2, s + 3
        for k in range(res):
            t = k / res
            pos = f(P[i0], P[i1], P[i2], P[i3], t)
            r = f(R[i0], R[i1], R[i2], R[i3], t) if spline == 'BSPLINE' else R[i1] + (R[i2] - R[i1]) * t
            out.append((pos, max(1e-6, r)))
    if not closed:
        if spline == 'BSPLINE':
            out.append((pts[-1].copy(), rad[-1]))
        else:
            out.append((pts[-1].copy(), rad[-1]))
    clean = [out[0]]
    for p, r in out[1:]:
        if (p - clean[-1][0]).length > 1e-9:
            clean.append((p, r))
    return clean


def frames(samples, closed=False):
    """(tangent, normal, binormal) per sample, rotation minimising (parallel transport)."""
    n = len(samples)
    if n < 2:
        return [(Vector((0, 0, 1)), Vector((1, 0, 0)), Vector((0, 1, 0)))] * n
    tans = []
    for i in range(n):
        a = samples[(i - 1) % n][0] if (closed or i > 0) else samples[i][0]
        b = samples[(i + 1) % n][0] if (closed or i < n - 1) else samples[i][0]
        t = b - a
        tans.append(t.normalized() if t.length > 1e-12 else Vector((0, 0, 1)))
    t0 = tans[0]
    ref = Vector((0, 0, 1)) if abs(t0.z) < 0.9 else Vector((1, 0, 0))
    nrm = (ref - t0 * ref.dot(t0)).normalized()
    out = []
    for i, t in enumerate(tans):
        if i > 0:
            prev = tans[i - 1]
            axis = prev.cross(t)
            if axis.length > 1e-9:
                ang = math.atan2(axis.length, prev.dot(t))
                nrm = Matrix.Rotation(ang, 3, axis.normalized()) @ nrm
            nrm = (nrm - t * nrm.dot(t)).normalized()
        out.append((t, nrm.copy(), t.cross(nrm).normalized()))
    return out


def profile(kind, sides, ratio=0.5):
    """Unit outline (2D) of the tube cross section."""
    if kind == 'SQUARE':
        k = max(1, int(round(sides / 4.0)))
        pts = []
        corners = [(1, 1), (-1, 1), (-1, -1), (1, -1)]
        for c in range(4):
            a, b = corners[c], corners[(c + 1) % 4]
            for j in range(k):
                t = j / k
                pts.append(((a[0] + (b[0] - a[0]) * t) * 0.85, (a[1] + (b[1] - a[1]) * t) * 0.85))
        return pts
    n = max(3, int(sides))
    sy = ratio if kind == 'FLAT' else 1.0
    return [(math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n) * sy) for i in range(n)]


def tube_mesh(samples, s):
    """Tube verts / faces from path samples and settings dict ``s``."""
    n = len(samples)
    if n < 2:
        return [], []
    closed = s.get('closed', False) and n >= 3
    fr = frames(samples, closed)
    prof = profile(s.get('profile', 'ROUND'), s.get('sides', 16), s.get('ratio', 0.5))
    m = len(prof)
    hole = min(0.95, max(0.0, s.get('hole', 0.0)))
    rot, twist = s.get('rotate', 0.0), s.get('twist', 0.0)
    t0, t1 = s.get('taper_start', 1.0), s.get('taper_end', 1.0)
    base_r = s.get('radius', 0.05)
    cap = s.get('cap', 'FLAT')

    # arc length parameter for taper / twist
    acc = [0.0]
    for i in range(1, n):
        acc.append(acc[-1] + (samples[i][0] - samples[i - 1][0]).length)
    total = acc[-1] or 1.0

    def ring(i, scale=1.0, shift=0.0):
        p, r = samples[i]
        u = acc[i] / total
        rr = base_r * r * (t0 + (t1 - t0) * u) * scale
        T, N, B = fr[i]
        a0 = rot + twist * u
        ca, sa = math.cos(a0), math.sin(a0)
        c = p + T * shift
        return [c + (N * (x * ca - y * sa) + B * (x * sa + y * ca)) * rr for x, y in prof]

    verts, faces = [], []

    def add_ring(pts):
        start = len(verts)
        verts.extend(pts)
        return start

    def bridge(a, b, flip=False):
        for i in range(m):
            j = (i + 1) % m
            f = (a + i, a + j, b + j, b + i)
            faces.append(tuple(reversed(f)) if flip else f)

    outer = [add_ring(ring(i)) for i in range(n)]
    for k in range(n - 1):
        bridge(outer[k], outer[k + 1])
    if closed:
        bridge(outer[-1], outer[0])
    if hole > 0:
        inner = [add_ring(ring(i, hole)) for i in range(n)]
        for k in range(n - 1):
            bridge(inner[k], inner[k + 1], flip=True)
        if closed:
            bridge(inner[-1], inner[0], flip=True)
        elif cap != 'OPEN':
            bridge(inner[0], outer[0])                 # end rings (annulus)
            bridge(outer[-1], inner[-1])
    elif not closed and cap != 'OPEN':
        for end, first in ((0, True), (n - 1, False)):
            base = outer[end]
            T = fr[end][0]
            p, r = samples[end]
            u = acc[end] / total
            rr = base_r * r * (t0 + (t1 - t0) * u)
            out_dir = -1.0 if first else 1.0
            rings_idx = [base]
            if cap == 'ROUND':
                steps = 4
                for k in range(1, steps):
                    ang = (math.pi / 2) * k / steps
                    rings_idx.append(add_ring(ring(end, math.cos(ang), out_dir * rr * math.sin(ang))))
                tip = p + T * out_dir * rr
            else:
                rings_idx.append(add_ring(ring(end, 0.5)))
                tip = p.copy()
            for a, b in zip(rings_idx, rings_idx[1:]):
                bridge(b, a) if first else bridge(a, b)
            c = len(verts)
            verts.append(tip)
            last = rings_idx[-1]
            for i in range(m):
                j = (i + 1) % m
                faces.append((last + j, last + i, c) if first else (last + i, last + j, c))
    # outward normals for closed solids (safety: signed volume)
    if closed or cap != 'OPEN':
        vol = 0.0
        for f in faces:
            a = verts[f[0]]
            for k in range(1, len(f) - 1):
                vol += a.dot(verts[f[k]].cross(verts[f[k + 1]]))
        if vol < 0:
            faces = [tuple(reversed(f)) for f in faces]
    return [tuple(v) for v in verts], faces


def arc_points(samples, count, closed=False):
    """``count`` evenly spaced (position, radius, index) along the samples."""
    n = len(samples)
    if n == 0 or count <= 0:
        return []
    acc = [0.0]
    for i in range(1, n):
        acc.append(acc[-1] + (samples[i][0] - samples[i - 1][0]).length)
    total = acc[-1]
    if closed and n >= 3:
        total += (samples[0][0] - samples[-1][0]).length
    out = []
    for k in range(count):
        d = total * k / count if closed else (total * k / max(1, count - 1) if count > 1 else 0.0)
        i = 0
        while i < n - 1 and acc[i + 1] < d:
            i += 1
        if i >= n - 1:
            if closed and n >= 3:
                seg = (samples[0][0] - samples[-1][0]).length or 1.0
                t = min(1.0, (d - acc[-1]) / seg)
                out.append((samples[-1][0].lerp(samples[0][0], t),
                            samples[-1][1] + (samples[0][1] - samples[-1][1]) * t, n - 1))
            else:
                out.append((samples[-1][0].copy(), samples[-1][1], n - 1))
            continue
        seg = acc[i + 1] - acc[i] or 1.0
        t = (d - acc[i]) / seg
        out.append((samples[i][0].lerp(samples[i + 1][0], t), samples[i][1] + (samples[i + 1][1] - samples[i][1]) * t, i))
    return out


def sphere_source(rings=10, segs=16):
    verts = [(0.0, 0.0, 1.0)]
    for r in range(1, rings):
        th = math.pi * r / rings
        for s_ in range(segs):
            ph = 2 * math.pi * s_ / segs
            verts.append((math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th)))
    verts.append((0.0, 0.0, -1.0))
    faces = []
    for s_ in range(segs):
        faces.append((0, 1 + s_, 1 + (s_ + 1) % segs))
    for r in range(rings - 2):
        a, b = 1 + r * segs, 1 + (r + 1) * segs
        for s_ in range(segs):
            t = (s_ + 1) % segs
            faces.append((a + s_, b + s_, b + t, a + t))
    last = len(verts) - 1
    base = 1 + (rings - 2) * segs
    for s_ in range(segs):
        faces.append((base + (s_ + 1) % segs, base + s_, last))
    return verts, faces


def repeat_mesh(samples, s, src_verts, src_faces):
    """Copies of a source mesh along the curve."""
    closed = s.get('closed', False) and len(samples) >= 3
    pts = arc_points(samples, max(1, int(s.get('count', 8))), closed)
    fr = frames(samples, closed)
    size = max(1e-6, max((Vector(v).length for v in src_verts), default=1.0))
    verts, faces = [], []
    t0, t1 = s.get('taper_start', 1.0), s.get('taper_end', 1.0)
    for k, (p, r, i) in enumerate(pts):
        u = k / max(1, len(pts) - 1)
        sc = s.get('size', 1.0) * (t0 + (t1 - t0) * u)
        if s.get('follow_radius', True):
            sc *= s.get('radius', 0.05) * r / size
        else:
            sc *= s.get('radius', 0.05) / size
        if s.get('align', True):
            T, N, B = fr[min(i, len(fr) - 1)]
            a0 = s.get('rotate', 0.0) + s.get('twist', 0.0) * u
            rot = Matrix((N, B, T)).transposed() @ Matrix.Rotation(a0, 3, 'Z')
        else:
            rot = Matrix.Identity(3)
        m = rot * sc
        off = len(verts)
        verts.extend(tuple(m @ Vector(v) + p) for v in src_verts)
        faces.extend(tuple(off + j for j in f) for f in src_faces)
    return verts, faces


# -----------------------------------------------------------------------------
# Live object
# -----------------------------------------------------------------------------


def get_points(ob):
    raw = list(ob.get(PTS_KEY, []))
    return [(Vector(raw[i:i + 3]), raw[i + 3]) for i in range(0, len(raw) - 3, 4)]


def set_points(ob, pts):
    ob[PTS_KEY] = [c for p, r in pts for c in (p.x, p.y, p.z, float(r))]


def settings(tb):
    return dict(mode=tb.mode, radius=tb.radius, taper_start=tb.taper_start, taper_end=tb.taper_end,
                profile=tb.profile, sides=tb.sides, ratio=tb.ratio, cap=tb.cap, hole=tb.hole, rotate=tb.rotate,
                twist=tb.twist, closed=tb.closed, spline=tb.spline, res=tb.resolution, count=tb.count,
                size=tb.size, follow_radius=tb.follow_radius, align=tb.align)


def build(ob):
    """(verts, faces) of the live tube object from its points and settings."""
    tb = ob.mch_tube
    pts = get_points(ob)
    s = settings(tb)
    samples = path_samples([p for p, _r in pts], [r for _p, r in pts], s['closed'] and len(pts) >= 3,
                           s['spline'], s['res'])
    if len(samples) < 2:
        if len(samples) == 1 and s['mode'] == 'REPEAT':
            pass
        else:
            return [], []
    if s['mode'] == 'REPEAT':
        src = tb.source
        if src is not None and src.type == 'MESH' and src != ob:
            sv = [tuple(v.co) for v in src.data.vertices]
            sf = [tuple(f.vertices) for f in src.data.polygons]
        else:
            sv, sf = sphere_source()
        return repeat_mesh(samples, s, sv, sf)
    return tube_mesh(samples, s)


def rebuild(ob):
    verts, faces = build(ob)
    me = ob.data
    me.clear_geometry()
    if verts:
        me.from_pydata(verts, [], faces)
    for poly in me.polygons:
        poly.use_smooth = ob.mch_tube.smooth_shade
    me.update()


def _update(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and self.live and ob.type == 'MESH':
        rebuild(ob)


def _p(prop, **kw):
    kw.setdefault('update', _update)
    return prop(**kw)


class MCH_PG_Tube(bpy.types.PropertyGroup):
    live: BoolProperty(default=False, options={'HIDDEN'})
    mode: _p(EnumProperty, name='Mode', items=[('TUBE', 'Tube', 'Solid tube along the curve'),
                                               ('REPEAT', 'Repeat', 'Copies of an object along the curve')],
             default='TUBE')
    radius: _p(FloatProperty, name='Radius', default=0.05, min=0.0001, soft_max=2.0, unit='LENGTH', precision=4)
    taper_start: _p(FloatProperty, name='Start Size', default=1.0, min=0.0, soft_max=3.0, subtype='FACTOR')
    taper_end: _p(FloatProperty, name='End Size', default=1.0, min=0.0, soft_max=3.0, subtype='FACTOR')
    profile: _p(EnumProperty, name='Profile', items=[('ROUND', 'Round', ''), ('SQUARE', 'Square', ''),
                                                     ('FLAT', 'Flat', 'Flattened (Ratio)')], default='ROUND')
    sides: _p(IntProperty, name='Sides', default=16, min=3, max=128)
    ratio: _p(FloatProperty, name='Ratio', default=0.4, min=0.05, max=1.0, subtype='FACTOR')
    cap: _p(EnumProperty, name='Cap', items=[('FLAT', 'Flat', ''), ('ROUND', 'Round', ''), ('OPEN', 'Open', '')],
            default='ROUND')
    hole: _p(FloatProperty, name='Hole', default=0.0, min=0.0, max=0.95, subtype='FACTOR',
             description='Hollow pipe: inner size (0 = solid)')
    rotate: _p(FloatProperty, name='Rotate', default=0.0, subtype='ANGLE')
    twist: _p(FloatProperty, name='Twist', default=0.0, subtype='ANGLE')
    closed: _p(BoolProperty, name='Closed', default=False)
    spline: _p(EnumProperty, name='Curve', items=[('SMOOTH', 'Smooth', 'Through the points'),
                                                  ('BSPLINE', 'B-Spline', 'Soft, pulled toward the points'),
                                                  ('LINEAR', 'Linear', 'Straight between points')],
               default='SMOOTH')
    resolution: _p(IntProperty, name='Resolution', default=12, min=1, max=64)
    count: _p(IntProperty, name='Count', default=8, min=1, max=500)
    size: _p(FloatProperty, name='Size', default=1.0, min=0.01, soft_max=5.0)
    follow_radius: _p(BoolProperty, name='Follow Radius', default=True,
                      description='Copies get the radius of the curve at their place')
    align: _p(BoolProperty, name='Align to Curve', default=True)
    source: _p(PointerProperty, name='Object', type=bpy.types.Object,
               poll=lambda self, o: o.type == 'MESH' and not o.mch_tube.live,
               description='Mesh repeated along the curve (empty = sphere)')
    smooth_shade: _p(BoolProperty, name='Smooth Shading', default=True)


def is_tube(ob):
    return ob is not None and ob.type == 'MESH' and getattr(ob, 'mch_tube', None) is not None and ob.mch_tube.live


def new_tube(context, first_world, radius=None):
    me = bpy.data.meshes.new('Tube')
    ob = bpy.data.objects.new('Tube', me)
    coll = bpy.data.collections.get(COLL)
    if coll is None:
        coll = bpy.data.collections.new(COLL)
        context.scene.collection.children.link(coll)
    coll.objects.link(ob)
    ob.location = first_world
    st = getattr(context.scene, 'mch_tube_defaults', None)
    tb = ob.mch_tube
    tb.live = False
    if st is not None:
        for k in ('mode', 'radius', 'profile', 'sides', 'cap', 'spline', 'count'):
            setattr(tb, k, getattr(st, k))
    if radius is not None:
        tb.radius = radius
    set_points(ob, [(Vector((0, 0, 0)), 1.0)])
    tb.live = True
    return ob


# -----------------------------------------------------------------------------
# Drawing / editing
# -----------------------------------------------------------------------------


def make_projector(region, rv3d):
    from . import core_geometry as cg
    return cg.Projector(region, rv3d)


class TubeLogic:
    """Point editing (plain class so the tests can drive it)."""

    def _proj(self, context):
        return make_projector(context.region, context.region_data)

    def _ob(self):
        return bpy.data.objects.get(self.ob_name) if self.ob_name else None

    def _world_pts(self):
        ob = self._ob()
        return [ob.matrix_world @ p for p, _r in get_points(ob)] if ob else []

    def _surface(self, context, xy):
        origin, direction = self._proj(context).ray(xy)
        dg = context.evaluated_depsgraph_get()
        o, d = Vector(origin), Vector(direction).normalized()
        for _ in range(8):
            ok, loc, nrm, _i, hit, _m = context.scene.ray_cast(dg, o, d)
            if not ok:
                return None
            if hit is not None and (hit.name == self.ob_name or is_tube(hit)):
                o = loc + d * 1e-4
                continue
            return loc, nrm
        return None

    def _air(self, context, xy, depth_point):
        proj = self._proj(context)
        origin, direction = proj.ray(xy)
        d = Vector(direction).normalized()
        view = getattr(proj, 'view_dir', d)
        plane_n = Vector(view).normalized()
        denom = d.dot(plane_n)
        if abs(denom) < 1e-9:
            return Vector(depth_point)
        t = (Vector(depth_point) - Vector(origin)).dot(plane_n) / denom
        return Vector(origin) + d * t

    def _place(self, context, xy):
        """World position for a new point: on a surface (lifted by the radius) or in the air."""
        hit = self._surface(context, xy)
        if hit is not None:
            return hit[0]
        pts = self._world_pts()
        depth = pts[-1] if pts else context.scene.cursor.location
        return self._air(context, xy, depth)

    def _near_point(self, context, xy):
        proj = self._proj(context)
        best, bd = None, HIT_PX
        for i, p in enumerate(self._world_pts()):
            s = proj.to_screen(p)
            if s is not None and math.dist(s, xy) <= bd:
                best, bd = i, math.dist(s, xy)
        return best

    def _near_curve(self, context, xy):
        """Segment index (insert after it) if the cursor is on the curve itself."""
        ob = self._ob()
        pts = get_points(ob) if ob else []
        if len(pts) < 2:
            return None
        tb = ob.mch_tube
        n = len(pts)
        closed = tb.closed and n >= 3
        segs = n if closed else n - 1
        samples = path_samples([p for p, _r in pts], [r for _p, r in pts], closed, tb.spline, tb.resolution)
        proj = self._proj(context)
        best, bd = None, HIT_PX
        last = max(1, len(samples) - 1)
        for k, (p, _r) in enumerate(samples):
            s = proj.to_screen(ob.matrix_world @ p)
            if s is not None and math.dist(s, xy) < bd:
                best, bd = min(segs - 1, int(k / last * segs)), math.dist(s, xy)
        return best

    def handle_world(self, context, i):
        """World position of point i's orange radius handle (beside the point, across the view)."""
        ob = self._ob()
        pts = get_points(ob)
        p = ob.matrix_world @ pts[i][0]
        proj = self._proj(context)
        s = proj.to_screen(p)
        if s is None:
            return None
        side = self._air(context, (s[0] + 1.0, s[1] + 0.6), p) - p
        if side.length < 1e-12:
            return None
        return p + side.normalized() * (ob.mch_tube.radius * pts[i][1])

    def _near_handle(self, context, xy):
        ob = self._ob()
        if ob is None:
            return None
        proj = self._proj(context)
        best, bd = None, HIT_PX
        for i in range(len(get_points(ob))):
            h = self.handle_world(context, i)
            hs = proj.to_screen(h) if h is not None else None
            if hs is not None and math.dist(hs, xy) <= bd:
                best, bd = i, math.dist(hs, xy)
        return best

    def radius_text(self):
        ob = self._ob()
        if ob is None or self.drag is None or self.drag_kind != 'RADIUS':
            return ''
        return f'Radius: {ob.mch_tube.radius * get_points(ob)[self.drag][1]:.4f}'

    def start(self, context, ob=None):
        self.ob_name = ob.name if ob is not None else ''
        self.drag = None
        self.drag_kind = 'POINT'
        self.count_added = 0

    def click(self, context, xy):
        ob = self._ob()
        if ob is not None:
            i = self._near_point(context, xy)
            h = self._near_handle(context, xy)
            if h is not None:
                hs = self._proj(context).to_screen(self.handle_world(context, h))
                ps = self._proj(context).to_screen(ob.matrix_world @ get_points(ob)[i][0]) if i is not None else None
                if i is None or ps is None or math.dist(hs, xy) < math.dist(ps, xy):
                    self.drag, self.drag_kind = h, 'RADIUS'
                    return 'RADIUS'
            if i is not None:
                self.drag, self.drag_kind = i, 'POINT'
                return 'DRAG'
            seg = self._near_curve(context, xy)
            if seg is not None:
                pts = get_points(ob)
                w = self._place(context, xy)
                p = ob.matrix_world.inverted() @ w
                r = (pts[seg][1] + pts[(seg + 1) % len(pts)][1]) / 2
                pts.insert(seg + 1, (p, r))
                set_points(ob, pts)
                rebuild(ob)
                self.drag, self.drag_kind = seg + 1, 'POINT'
                return 'INSERT'
        w = self._place(context, xy)
        if ob is None:
            ob = new_tube(context, w)
            self.ob_name = ob.name
            for o in context.view_layer.objects:
                if o.select_get():
                    o.select_set(False)
            ob.select_set(True)
            context.view_layer.objects.active = ob
            rebuild(ob)
            self.count_added += 1
            return 'NEW'
        pts = get_points(ob)
        pts.append((ob.matrix_world.inverted() @ w, pts[-1][1] if pts else 1.0))
        set_points(ob, pts)
        rebuild(ob)
        self.count_added += 1
        return 'ADD'

    def move(self, context, xy):
        if self.drag is None:
            return
        ob = self._ob()
        pts = get_points(ob)
        cur = ob.matrix_world @ pts[self.drag][0]
        w = self._air(context, xy, cur)
        if self.drag_kind == 'RADIUS':           # orange handle: distance to the point = this point's radius
            r = (w - cur).length / max(1e-9, ob.mch_tube.radius)
            pts[self.drag] = (pts[self.drag][0], max(0.01, r))
            set_points(ob, pts)
            rebuild(ob)
            return
        pts[self.drag] = (ob.matrix_world.inverted() @ w, pts[self.drag][1])
        set_points(ob, pts)
        rebuild(ob)

    def release(self):
        self.drag = None
        self.drag_kind = 'POINT'

    def point_radius(self, context, xy, factor):
        ob = self._ob()
        i = self._near_point(context, xy) if ob else None
        if i is None:
            return False
        pts = get_points(ob)
        pts[i] = (pts[i][0], max(0.01, pts[i][1] * factor))
        set_points(ob, pts)
        rebuild(ob)
        return True

    def delete_point(self, context, xy):
        ob = self._ob()
        i = self._near_point(context, xy) if ob else None
        if i is None:
            return False
        pts = get_points(ob)
        if len(pts) <= 1:
            return False
        pts.pop(i)
        set_points(ob, pts)
        rebuild(ob)
        return True

    def done(self, context):
        ob = self._ob()
        if ob is not None and len(get_points(ob)) < 2:
            me = ob.data
            bpy.data.objects.remove(ob)
            if me.users == 0:
                bpy.data.meshes.remove(me)
            return None
        return ob


def _draw():
    try:
        import gpu
        from gpu_extras.batch import batch_for_shader
        for op in list(_draw_ops):
            try:
                pts = op._world_pts()
            except (ReferenceError, AttributeError):
                continue
            if not pts:
                continue
            gpu.state.blend_set('ALPHA')
            gpu.state.depth_test_set('NONE')
            sh = gpu.shader.from_builtin('UNIFORM_COLOR')
            sh.bind()
            if len(pts) >= 2:
                sh.uniform_float('color', (1.0, 1.0, 1.0, 0.55))
                batch_for_shader(sh, 'LINE_STRIP', {'pos': [tuple(p) for p in pts]}).draw(sh)
            ctx = bpy.context
            hs = []
            for i, p in enumerate(pts):
                try:
                    h = op.handle_world(ctx, i)
                except (AttributeError, ReferenceError, TypeError):
                    h = None
                if h is not None:
                    hs.append((p, h))
            if hs:
                sh.uniform_float('color', (1.0, 0.65, 0.3, 0.7))
                batch_for_shader(sh, 'LINES', {'pos': [tuple(c) for pr in hs for c in pr]}).draw(sh)
                gpu.state.point_size_set(8.0)
                sh.uniform_float('color', (1.0, 0.65, 0.3, 1.0))
                batch_for_shader(sh, 'POINTS', {'pos': [tuple(h) for _p, h in hs]}).draw(sh)
            gpu.state.point_size_set(10.0)
            sh.uniform_float('color', (1.0, 1.0, 1.0, 1.0))
            batch_for_shader(sh, 'POINTS', {'pos': [tuple(p) for p in pts]}).draw(sh)
            gpu.state.point_size_set(1.0)
            gpu.state.blend_set('NONE')
    except Exception:            # never break viewport drawing
        pass


class MCH_OT_tube_draw(TubeLogic, bpy.types.Operator):
    """Draw / edit a Tube: click points (on the mesh or in the air), drag to move, Enter when done"""
    bl_idname = 'mch.tube_draw'
    bl_label = 'Draw Tube'
    bl_options = {'REGISTER', 'UNDO'}

    new: BoolProperty(default=False, options={'SKIP_SAVE'}, description='Start a new tube even if one is active')

    def _hint(self, context):
        if context.area:
            context.area.header_text_set(
                'Tube: click = add point (on the mesh or in the air)  |  click the line = insert  |  drag = move  |  '
                'orange dot / Ctrl+Wheel = that point\'s radius  |  X = delete point  |  Enter / Right click = done')

    def _end(self, context):
        if self in _draw_ops:
            _draw_ops.remove(self)
        if context.area:
            context.area.header_text_set(None)
            context.area.tag_redraw()

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            return {'CANCELLED'}
        ob = context.active_object
        self.start(context, ob if (is_tube(ob) and not self.new) else None)
        _draw_ops.append(self)
        context.window_manager.modal_handler_add(self)
        self._hint(context)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if context.area:
            context.area.tag_redraw()
        xy = (event.mouse_region_x, event.mouse_region_y)
        if event.type in {'MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM', 'NDOF_MOTION'}:
            return {'PASS_THROUGH'}
        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            if event.ctrl and self.point_radius(context, xy, 1.1 if event.type == 'WHEELUPMOUSE' else 1 / 1.1):
                return {'RUNNING_MODAL'}
            return {'PASS_THROUGH'}
        if event.type == 'MOUSEMOVE':
            self.move(context, xy)
            if self.radius_text() and context.area:
                context.area.header_text_set(self.radius_text())
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                self.click(context, xy)
            elif event.value == 'RELEASE':
                self.release()
                self._hint(context)
            return {'RUNNING_MODAL'}
        if event.type in {'X', 'DEL'} and event.value == 'PRESS':
            self.delete_point(context, xy)
            return {'RUNNING_MODAL'}
        if event.type in {'RET', 'NUMPAD_ENTER', 'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            ob = self.done(context)
            self._end(context)
            if ob is not None:
                self.report({'INFO'}, 'Tube: live until Apply (N panel / tool panel)')
                return {'FINISHED'}
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}


class MCH_OT_tube_apply(bpy.types.Operator):
    """Apply: the tube becomes a plain mesh (no more live changes)"""
    bl_idname = 'mch.tube_apply'
    bl_label = 'Apply Tube'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(is_tube(o) for o in context.selected_objects) or is_tube(context.active_object)

    def execute(self, context):
        obs = {o for o in context.selected_objects if is_tube(o)}
        if is_tube(context.active_object):
            obs.add(context.active_object)
        for o in obs:
            o.mch_tube.live = False
            if PTS_KEY in o:
                del o[PTS_KEY]
        self.report({'INFO'}, f'Applied {len(obs)} tube(s)')
        return {'FINISHED'}


class MCH_PG_TubeDefaults(bpy.types.PropertyGroup):
    mode: EnumProperty(name='Mode', items=[('TUBE', 'Tube', ''), ('REPEAT', 'Repeat', '')], default='TUBE')
    radius: FloatProperty(name='Radius', default=0.05, min=0.0001, soft_max=2.0, unit='LENGTH', precision=4)
    profile: EnumProperty(name='Profile', items=[('ROUND', 'Round', ''), ('SQUARE', 'Square', ''),
                                                 ('FLAT', 'Flat', '')], default='ROUND')
    sides: IntProperty(name='Sides', default=16, min=3, max=128)
    cap: EnumProperty(name='Cap', items=[('FLAT', 'Flat', ''), ('ROUND', 'Round', ''), ('OPEN', 'Open', '')],
                      default='ROUND')
    spline: EnumProperty(name='Curve', items=[('SMOOTH', 'Smooth', ''), ('BSPLINE', 'B-Spline', ''),
                                              ('LINEAR', 'Linear', '')], default='SMOOTH')
    count: IntProperty(name='Count', default=8, min=1, max=500)


def start_draw(context, new=True):
    """Start drawing in the biggest 3D View (the tool may be picked from another editor)."""
    win = context.window
    screen = win.screen if win is not None else None
    if screen is None:
        return False
    areas = sorted((a for a in screen.areas if a.type == 'VIEW_3D'), key=lambda a: -a.width * a.height)
    for area in areas:
        region = next((r for r in area.regions if r.type == 'WINDOW'), None)
        if region is None:
            continue
        with context.temp_override(window=win, screen=screen, area=area, region=region):
            return bpy.ops.mch.tube_draw('INVOKE_DEFAULT', new=new) == {'RUNNING_MODAL'}
    return False


def draw(layout, context):
    st = context.scene.mch_tube_defaults
    ob = context.active_object
    box = layout.box()
    box.label(text='TUBE / CURVE', icon='CURVE_BEZCURVE')
    r = box.row()
    r.scale_y = 1.4
    r.operator('mch.tube_draw', text='Draw New Tube', icon='GREASEPENCIL').new = True
    if not is_tube(ob):
        c = box.column(align=True)
        c.label(text='New tubes start with:')
        c.row(align=True).prop(st, 'mode', expand=True)
        c.prop(st, 'radius')
        c.row(align=True).prop(st, 'profile', expand=True)
        c.prop(st, 'sides')
        c.row(align=True).prop(st, 'cap', expand=True)
        c.row(align=True).prop(st, 'spline', expand=True)
        c.prop(st, 'count')
        return
    tb = ob.mch_tube
    sub = box.box()
    sub.label(text=f'LIVE: {ob.name}  ({len(get_points(ob))} points)')
    rr = sub.row(align=True)
    rr.operator('mch.tube_draw', text='Edit Points', icon='CURVE_PATH').new = False
    rr.operator('mch.tube_apply', text='Apply', icon='CHECKMARK')
    sub.row(align=True).prop(tb, 'mode', expand=True)
    c = sub.column(align=True)
    c.prop(tb, 'radius')
    c.prop(tb, 'taper_start', slider=True)
    c.prop(tb, 'taper_end', slider=True)
    c = sub.column(align=True)
    c.row(align=True).prop(tb, 'spline', expand=True)
    c.prop(tb, 'closed', toggle=True)
    c.prop(tb, 'resolution')
    if tb.mode == 'TUBE':
        c = sub.column(align=True)
        c.row(align=True).prop(tb, 'profile', expand=True)
        c.prop(tb, 'sides')
        if tb.profile == 'FLAT':
            c.prop(tb, 'ratio', slider=True)
        c.row(align=True).prop(tb, 'cap', expand=True)
        c.prop(tb, 'hole', slider=True)
    else:
        c = sub.column(align=True)
        c.prop(tb, 'source')
        c.prop(tb, 'count')
        c.prop(tb, 'size')
        c.prop(tb, 'follow_radius')
        c.prop(tb, 'align')
    c = sub.column(align=True)
    c.prop(tb, 'rotate')
    c.prop(tb, 'twist')
    c.prop(tb, 'smooth_shade')


class MCH_PT_tube(bpy.types.Panel):
    bl_idname = 'MCH_PT_tube'
    bl_label = 'Tube / Curve'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Mecha Lab'
    bl_order = 72

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, 'mch_tube_defaults') and is_tube(context.active_object)

    def draw(self, context):
        draw(self.layout, context)


_handle = None
CLASSES = (MCH_PG_Tube, MCH_PG_TubeDefaults, MCH_OT_tube_draw, MCH_OT_tube_apply, MCH_PT_tube)


def register():
    global _handle
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Object.mch_tube = bpy.props.PointerProperty(type=MCH_PG_Tube)
    bpy.types.Scene.mch_tube_defaults = bpy.props.PointerProperty(type=MCH_PG_TubeDefaults)
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
    for attr, owner in (('mch_tube', bpy.types.Object), ('mch_tube_defaults', bpy.types.Scene)):
        if hasattr(owner, attr):
            delattr(owner, attr)
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
