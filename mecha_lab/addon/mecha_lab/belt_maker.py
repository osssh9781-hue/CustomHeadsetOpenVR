"""0.24.20 Belt Maker: draw a line over a mesh, get a strap.

    Wrap    the line only says WHERE: the strap goes all the way around the mesh there (the mesh is cut by
            the plane through the line and the view, the loop under the line is used - the back too)
    Follow  the strap runs exactly along the drawn line on the surface (open, flat ends)

Presets (cross-section swept along the path, sitting on the surface, lifted by Lift):
    Plain   a plain rectangular strap (Edge Round softens its corners)
    Rail    sci-fi strap: raised rails on both edges, a groove down the middle, bolts along it

Everything stays live until Apply (the path on the mesh is cached, so the sliders only re-sweep).
``strap_profile``, ``sweep`` and ``loops_from_edges`` are pure and tested headless.
"""
from __future__ import annotations

import json
import math

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from mathutils import Matrix, Vector

from . import target_rules
from . import core_geometry as cg

SRC_KEY = 'mch_belt_src'
COLLECTION = 'Belts'
PRESET_ITEMS = [('PLAIN', 'Plain Strap', 'A plain rectangular strap', 'MESH_PLANE', 0),
                ('RAIL', 'Rail Strap', 'Sci-fi strap: raised edge rails, a middle groove and bolts', 'MOD_ARRAY', 1),
                ('WEBBING', 'Webbing', 'Tactical nylon webbing: thin, fine ribs along it, stitched edges, '
                 'side-release buckle and ladder lock', 'MOD_LINEART', 2)]
MODE_ITEMS = [('WRAP', 'Wrap Around', 'All the way around the mesh where the line crosses it', 'MESH_TORUS', 0),
              ('FOLLOW', 'Follow Line', 'Exactly along the drawn line on the surface', 'IPO_LINEAR', 1)]
LIVE_KEYS = ('preset', 'mode', 'width', 'thickness', 'lift', 'edge_round', 'rail_height', 'rail_width',
             'groove', 'bolts', 'bolt_spacing', 'smooth', 'density', 'ribs', 'buckle', 'buckle_shift')
PATH_KEYS = ('mode', 'smooth', 'density')           # these change the path on the mesh
_CACHE = {}


def _update(self, context):
    ob = self.id_data
    if not isinstance(ob, bpy.types.Object) or not self.live:
        return
    try:
        rebuild(context, ob)
        self.last_error = ''
    except (cg.CutError, ValueError, RuntimeError) as ex:
        self.last_error = str(ex)
    st = getattr(getattr(context, 'scene', None), 'mch_belt', None)
    if st is not None:                       # the next belt starts like this one
        for k in LIVE_KEYS:
            try:
                if getattr(st, k) != getattr(self, k):
                    setattr(st, k, getattr(self, k))
            except (AttributeError, TypeError):
                pass


def _p(prop, **kw):
    kw.setdefault('update', _update)
    return prop(**kw)


class MCH_PG_Belt(bpy.types.PropertyGroup):
    """Scene.mch_belt = settings for the next belt; Object.mch_belt = live belt."""
    preset: _p(EnumProperty, name='Preset', items=PRESET_ITEMS, default='PLAIN')
    mode: _p(EnumProperty, name='Mode', items=MODE_ITEMS, default='WRAP')
    width: _p(FloatProperty, name='Width', default=0.15, min=0.001, soft_max=2.0, precision=4, unit='LENGTH')
    thickness: _p(FloatProperty, name='Thickness', default=0.025, min=0.0005, soft_max=0.5, precision=4,
                  unit='LENGTH')
    lift: _p(FloatProperty, name='Lift', default=0.003, min=-0.5, soft_max=0.5, precision=4, unit='LENGTH',
             description='Gap between the surface and the strap (below 0 = sunk in)')
    edge_round: _p(FloatProperty, name='Edge Round', default=0.3, min=0.0, max=1.0, subtype='FACTOR',
                   description='Plain: round the strap corners')
    rail_height: _p(FloatProperty, name='Rail Height', default=0.4, min=0.0, soft_max=2.0,
                    description='Rail: how far the edge rails stand up (x Thickness)')
    rail_width: _p(FloatProperty, name='Rail Width', default=0.14, min=0.02, max=0.45, subtype='FACTOR',
                   description='Rail: rail width (x Width)')
    groove: _p(FloatProperty, name='Groove', default=0.35, min=0.0, max=0.9, subtype='FACTOR',
               description='Rail: depth of the middle groove (x Thickness, 0 = none)')
    bolts: _p(BoolProperty, name='Bolts', default=True, description='Rail: bolts along the strap')
    bolt_spacing: _p(FloatProperty, name='Bolt Spacing', default=0.25, min=0.01, soft_max=2.0, precision=3,
                     unit='LENGTH')
    ribs: _p(IntProperty, name='Ribs', default=9, min=0, max=40,
             description='Webbing: fine ribs along the strap (the woven nylon look)')
    buckle: _p(BoolProperty, name='Buckle', default=True,
               description='Webbing: a side-release buckle and a ladder lock on the strap')
    buckle_shift: _p(FloatProperty, name='Buckle Position', default=0.0, min=-0.5, max=0.5, subtype='FACTOR',
                     description='Move the buckle along the strap (0 = where you drew, the front)')
    smooth: _p(IntProperty, name='Smooth Path', default=3, min=0, max=30,
               description='Soften the path on the mesh (bumps of the surface under the strap)')
    density: _p(FloatProperty, name='Density', default=1.0, min=0.2, max=4.0,
                description='Path points per strap width (higher = follows the surface closer)')
    live: BoolProperty(default=False, options={'HIDDEN'})
    last_error: StringProperty(default='', options={'HIDDEN', 'SKIP_SAVE'})


# -----------------------------------------------------------------------------
# Pure geometry
# -----------------------------------------------------------------------------


def _rounded_rect(w, t, r, seg=3):
    r = max(0.0, min(r, w / 2.0, t / 2.0))
    if r <= 1e-9:
        return [(-w / 2, 0.0), (w / 2, 0.0), (w / 2, t), (-w / 2, t)]
    pts = []
    for cx, cy, a0 in ((w / 2 - r, r, -90), (w / 2 - r, t - r, 0), (-w / 2 + r, t - r, 90), (-w / 2 + r, r, 180)):
        for k in range(seg + 1):
            a = math.radians(a0 + 90.0 * k / seg)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def webbing_profile(width, thickness, ribs=9):
    """0.24.20 nylon webbing: a thin strap, a stitched (slightly raised, rounded) edge on both sides and fine
    ribs along the top."""
    w, t = width, thickness * 0.55
    edge = w * 0.07
    top = []
    n = max(0, int(ribs))
    inner = w / 2 - edge
    steps = max(2, n * 4)
    for k in range(steps + 1):                      # ribs: a small wave across the inner top
        x = inner - 2 * inner * k / steps
        wave = 0.5 * (1 - math.cos(2 * math.pi * k * n / steps)) if n else 0.0
        top.append((x, t * (1.0 + 0.12 * wave)))
    pts = [(-w / 2 + t * 0.4, 0.0), (w / 2 - t * 0.4, 0.0)]
    pts += [(w / 2, t * 0.45), (w / 2 - edge * 0.25, t * 1.25), (w / 2 - edge * 0.85, t * 1.2)]
    pts += top
    pts += [(-w / 2 + edge * 0.85, t * 1.2), (-w / 2 + edge * 0.25, t * 1.25), (-w / 2, t * 0.45)]
    return pts


def strap_profile(preset, width, thickness, edge_round=0.3, rail_height=0.4, rail_width=0.14, groove=0.35,
                  ribs=9):
    """Closed 2D section, CCW: x across the strap (-w/2 .. w/2), y up from the surface (0 .. thickness)."""
    w, t = width, thickness
    if preset == 'WEBBING':
        return webbing_profile(w, t, ribs)
    if preset != 'RAIL':
        return _rounded_rect(w, t, edge_round * min(w, t) / 2.0)
    rh, rw = t * rail_height, w * rail_width
    gw, gd = w * 0.16, t * groove
    pts = [(-w / 2, 0.0), (w / 2, 0.0), (w / 2, t + rh), (w / 2 - rw, t + rh), (w / 2 - rw, t)]
    if gd > 1e-9:
        pts += [(gw / 2, t), (gw / 2, t - gd), (-gw / 2, t - gd), (-gw / 2, t)]
    pts += [(-w / 2 + rw, t), (-w / 2 + rw, t + rh), (-w / 2, t + rh)]
    return pts


def sweep(points, normals, profile, closed, lift=0.0):
    """(verts, faces) of ``profile`` swept along ``points`` (surface normals ``normals``)."""
    n, m = len(points), len(profile)
    if n < 2 or m < 3:
        return [], []
    verts, faces = [], []
    for i in range(n):
        a = points[(i - 1) % n] if (closed or i > 0) else points[i]
        b = points[(i + 1) % n] if (closed or i < n - 1) else points[i]
        T = (b - a)
        T = T.normalized() if T.length > 1e-12 else Vector((1, 0, 0))
        N = normals[i] - T * normals[i].dot(T)
        N = N.normalized() if N.length > 1e-9 else Vector((0, 0, 1))
        S = T.cross(N).normalized()
        for x, y in profile:
            verts.append(points[i] + S * x + N * (lift + y))
    for i in range(n if closed else n - 1):
        a, b = i * m, ((i + 1) % n) * m
        for j in range(m):
            k = (j + 1) % m
            faces.append((a + j, a + k, b + k, b + j))
    if not closed:
        faces.append(tuple(range(m - 1, -1, -1)))
        faces.append(tuple((n - 1) * m + j for j in range(m)))
    return verts, faces


def loops_from_edges(edges):
    """Chains of connected edges [(a, b)] -> [(vertex list in order, closed?)]."""
    adj = {}
    for a, b in edges:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    seen, out = set(), []
    for start in adj:
        if start in seen:
            continue
        comp, stack = {start}, [start]
        while stack:                         # the connected component
            v = stack.pop()
            for w in adj[v]:
                if w not in comp:
                    comp.add(w)
                    stack.append(w)
        seen |= comp
        first = next((v for v in comp if len(adj[v]) == 1), start)
        chain, prev, cur = [first], None, first
        while True:
            nxt = [w for w in adj[cur] if w != prev and w not in chain[1:]]
            if not nxt or nxt[0] == first:
                break
            prev, cur = cur, nxt[0]
            chain.append(cur)
        out.append((chain, all(len(adj[v]) == 2 for v in comp)))
    return out


def resample(points, step, closed):
    """Points every ``step`` along a polyline (closed: back to the start)."""
    pts = list(points) + ([points[0]] if closed else [])
    if len(pts) < 2:
        return list(points)
    out = [pts[0].copy()]
    carry = 0.0
    for a, b in zip(pts, pts[1:]):
        seg = (b - a).length
        if seg < 1e-12:
            continue
        d = step - carry
        while d <= seg:
            out.append(a.lerp(b, d / seg))
            d += step
        carry = seg - (d - step)
    if closed:
        if len(out) > 2 and (out[-1] - out[0]).length < step * 0.5:
            out.pop()
    elif (out[-1] - pts[-1]).length > step * 0.25:
        out.append(pts[-1].copy())
    return out


def smooth_path(points, passes, closed):
    pts = [p.copy() for p in points]
    n = len(pts)
    for _ in range(passes):
        new = []
        for i in range(n):
            if not closed and i in (0, n - 1):
                new.append(pts[i])
                continue
            new.append(pts[i] * 0.5 + (pts[(i - 1) % n] + pts[(i + 1) % n]) * 0.25)
        pts = new
    return pts


# -----------------------------------------------------------------------------
# Path on the mesh
# -----------------------------------------------------------------------------


def pick_target(context, projector, path):
    dg = context.evaluated_depsgraph_get()
    counts = {}
    probes = []                               # along the whole line: its ends may lie past the part
    for a, b in zip(path, path[1:]):
        n = max(1, int(math.dist(a, b) / 12.0))
        probes += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n)]
    probes.append(path[-1])
    for xy in probes[::max(1, len(probes) // 40)]:
        o, d = projector.ray(xy)
        for _ in range(16):
            hit, loc, _n, _i, ob, _m = target_rules.scene_ray(context, dg, o, d)
            if not hit or ob is None:
                break
            real = bpy.data.objects.get(ob.name)
            if real is not None and real.type == 'MESH' and not real.get(SRC_KEY) and not real.get('mch_spike_src') \
                    and not real.get('mch_scales_src') and not real.get('mch_sbrush_src'):
                counts[real.name] = counts.get(real.name, 0) + 1
                break
            o = loc + d * 1e-4
    return bpy.data.objects[max(counts, key=counts.get)] if counts else None


def _world_mesh(context, ob):
    dg = context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.transform(ev.matrix_world)
    finally:
        ev.to_mesh_clear()
    return bm


def _wrap_path(context, target, projector, path):
    """Closed loop around ``target`` in the plane through the drawn line and the view."""
    p0, p1 = path[0], path[-1]
    if math.dist(p0, p1) < 2.0:
        raise cg.CutError('Wrap: draw a line across the part (it says where the belt goes).')
    bm = _world_mesh(context, target)
    try:
        center = sum((v.co for v in bm.verts), Vector()) / max(1, len(bm.verts))
        o0, d0 = (Vector(v) for v in projector.ray(p0))
        o1, d1 = (Vector(v) for v in projector.ray(p1))
        k = max(0.1, (center - o0).dot(d0))
        a, b = o0 + d0 * k, o1 + d1 * k
        c = o0 + d0 * (k + 1.0)
        no = (b - a).cross(c - a)
        if no.length < 1e-12:
            raise cg.CutError('Wrap: the line is too short.')
        no.normalize()
        res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=a, plane_no=no,
                                     dist=1e-7)
        cut_edges = [e for e in res['geom_cut'] if isinstance(e, bmesh.types.BMEdge)]
        chains = loops_from_edges([(e.verts[0].index, e.verts[1].index) for e in cut_edges]) if cut_edges else []
        bm.verts.ensure_lookup_table()
        if not chains:
            raise cg.CutError('Wrap: the line does not cross the mesh.')
        mid = path[len(path) // 2]
        om, dm = (Vector(v) for v in projector.ray(mid))

        def ray_dist(co):
            v = co - om
            return (v - dm * v.dot(dm)).length

        best = min(chains, key=lambda ch: min(ray_dist(bm.verts[i].co) for i in ch[0]))
        pts = [bm.verts[i].co.copy() for i in best[0]]
        return pts, best[1]
    finally:
        bm.free()


def _follow_path(context, target, projector, path, step_px=4.0):
    from . import armor_plate as ap
    dense = [tuple(path[0])]
    for a, b in zip(path, path[1:]):
        n = max(1, int(math.dist(a, b) / step_px))
        dense += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(1, n + 1)]
    bvh, _v, _p = ap._target_bvh(context, target)
    cos, _n, _miss = ap.project_patch(dense, projector, bvh)
    return [Vector(c) for c in cos], False


def surface_path(context, ob, src, p):
    """Cached (points, normals, closed) of the belt path on its mesh."""
    key = (src.get('stamp'), tuple(round(float(getattr(p, k)), 4) if not isinstance(getattr(p, k), str)
                                   else getattr(p, k) for k in PATH_KEYS), round(p.width, 5))
    hit = _CACHE.get(ob.name)
    if hit is not None and hit[0] == key:
        return hit[1]
    from . import armor_plate as ap
    target = bpy.data.objects.get(src.get('target', ''))
    if target is None or target.type != 'MESH':
        raise cg.CutError('The mesh the belt was drawn on is gone.')
    projector = ap.thaw_projector(src['proj'])
    path = [tuple(q) for q in src['path']]
    if p.mode == 'WRAP':
        pts, closed = _wrap_path(context, target, projector, path)
    else:
        pts, closed = _follow_path(context, target, projector, path)
    step = max(1e-5, p.width / max(0.2, p.density))
    pts = resample(pts, step, closed)
    if len(pts) < 2:
        raise cg.CutError('The belt path is too short.')
    pts = smooth_path(pts, p.smooth, closed)
    bvh, _v, _f = ap._target_bvh(context, target)
    center = sum(pts, Vector()) / len(pts)
    nrms, snapped = [], []
    for q in pts:
        loc, n, _i, _d = bvh.find_nearest(q)
        if loc is not None:
            q = loc                 # smoothing a loop pulls it inward: back onto the surface
        if n is None:
            n = q - center
        elif (q - center).dot(n) < 0 and p.mode == 'WRAP':
            n = -n
        snapped.append(q)
        nrms.append(n.normalized() if n.length > 1e-9 else Vector((0, 0, 1)))
    pts = snapped
    # soften the normals too (facets of a low-poly surface would twist the strap)
    for _ in range(2):
        m = len(nrms)
        nrms = [((nrms[(i - 1) % m] if (closed or i > 0) else nrms[i]) + nrms[i] * 2.0 +
                 (nrms[(i + 1) % m] if (closed or i < m - 1) else nrms[i])).normalized() for i in range(m)]
    if p.mode == 'FOLLOW':                     # normals face the viewer side of the surface
        view = Vector(projector.view_dir)
        nrms = [(-n if n.dot(view) > 0 else n) for n in nrms]
    data = (pts, nrms, closed)
    _CACHE[ob.name] = (key, data)
    return data


def build(context, ob):
    src = source(ob)
    if src is None:
        raise cg.CutError('This belt was applied.')
    p = ob.mch_belt
    pts, nrms, closed = surface_path(context, ob, src, p)
    prof = strap_profile(p.preset, p.width, p.thickness, p.edge_round, p.rail_height, p.rail_width, p.groove,
                         p.ribs)
    verts, faces = sweep(pts, nrms, prof, closed, p.lift)
    extra = []
    if p.preset == 'RAIL' and p.bolts:
        extra.append(bolts(pts, nrms, closed, p))
    if p.preset == 'WEBBING' and p.buckle:
        extra.append(buckle(pts, nrms, closed, p, front_index(src, pts, nrms)))
    for bv, bf in extra:
        off = len(verts)
        verts += bv
        faces += [tuple(i + off for i in f) for f in bf]
    return verts, faces


def front_index(src, pts, nrms):
    """The path point under the middle of the drawn line, facing the view (where the buckle goes)."""
    from . import armor_plate as ap
    try:
        pr = ap.thaw_projector(src['proj'])
        path = src['path']
        mid = path[len(path) // 2] if len(path) > 2 else [(path[0][0] + path[-1][0]) / 2,
                                                            (path[0][1] + path[-1][1]) / 2]
        view = Vector(pr.view_dir)
    except (KeyError, TypeError, ValueError):
        return len(pts) // 2
    best, best_d = len(pts) // 2, math.inf
    for i, q in enumerate(pts):
        if nrms[i].dot(view) > 0.2:
            continue                        # the back side
        s = pr.to_screen(q)
        if s is None:
            continue
        d = math.dist(s, mid)
        if d < best_d:
            best, best_d = i, d
    return best


def _box(verts, faces, c, T, N, S, lt, ws, hn, taper=1.0):
    """A box (optionally tapered toward +T) in the strap frame: length lt, width ws, height hn, bottom at c."""
    start = len(verts)
    for x in (-0.5, 0.5):
        k = taper if x > 0 else 1.0
        for y in (-0.5, 0.5):
            for z in (0.0, 1.0):
                verts.append(c + T * (x * lt) + S * (y * ws * k) + N * (z * hn))
    q = lambda a, b, c_, d: (start + a, start + b, start + c_, start + d)
    faces += [q(0, 2, 3, 1), q(4, 5, 7, 6), q(0, 1, 5, 4), q(2, 6, 7, 3), q(0, 4, 6, 2), q(1, 3, 7, 5)]


def buckle(pts, nrms, closed, p, at):
    """Side-release buckle (housing + tapered tongue + release tabs) and a ladder lock beside it."""
    n = len(pts)
    acc = [0.0]
    seq = pts + ([pts[0]] if closed else [])
    for a, b in zip(seq, seq[1:]):
        acc.append(acc[-1] + (b - a).length)
    total = acc[-1] or 1.0
    s = (acc[at] + p.buckle_shift * total) % total if closed else min(max(acc[at] + p.buckle_shift * total, 0.0),
                                                                       total)
    j = max(0, min(len(acc) - 2, next((k for k in range(len(acc) - 1) if acc[k + 1] >= s), len(acc) - 2)))
    t = (s - acc[j]) / max(acc[j + 1] - acc[j], 1e-12)
    pos = seq[j].lerp(seq[j + 1], t)
    N = nrms[j % n].lerp(nrms[(j + 1) % n], t).normalized()
    T = (seq[j + 1] - seq[j])
    T = (T - N * T.dot(N)).normalized() if T.length > 1e-12 else Vector((1, 0, 0))
    S = T.cross(N).normalized()
    w, th = p.width, p.thickness * 0.55
    base = pos + N * p.lift
    verts, faces = [], []
    _box(verts, faces, base + T * (-0.45 * w), T, N, S, 1.0 * w, 1.3 * w, 3.2 * th)            # housing
    _box(verts, faces, base + T * (0.45 * w), T, N, S, 0.8 * w, 1.15 * w, 2.4 * th, taper=0.55)  # tongue
    for side in (-1, 1):                                                                           # release tabs
        _box(verts, faces, base + T * (0.15 * w) + S * (side * 0.62 * w), T, N, S, 0.45 * w, 0.12 * w, 2.0 * th)
    lx = 1.35 * w                                                                                  # ladder lock
    for side in (-1, 1):
        _box(verts, faces, base + T * lx + S * (side * 0.6 * w), T, N, S, 0.5 * w, 0.1 * w, 2.2 * th)
    for dx in (-0.2, 0.2):
        _box(verts, faces, base + T * (lx + dx * w), T, N, S, 0.08 * w, 1.3 * w, 2.2 * th)
    return verts, faces


def bolts(pts, nrms, closed, p, sides=8):
    """Small round bolt heads on the strap top, both sides of the groove, every Bolt Spacing."""
    acc = [0.0]
    seq = pts + ([pts[0]] if closed else [])
    for a, b in zip(seq, seq[1:]):
        acc.append(acc[-1] + (b - a).length)
    total = acc[-1]
    if total <= 0:
        return [], []
    count = max(1, int(total / max(p.bolt_spacing, 1e-4)))
    r = p.width * 0.055
    h = p.thickness * 0.45
    verts, faces = [], []
    j = 0
    for c in range(count):
        s = (c + 0.5) * total / count
        while j < len(acc) - 2 and acc[j + 1] < s:
            j += 1
        t = (s - acc[j]) / max(acc[j + 1] - acc[j], 1e-12)
        a, b = seq[j], seq[j + 1]
        pos = a.lerp(b, t)
        n = nrms[j % len(nrms)].lerp(nrms[(j + 1) % len(nrms)], t).normalized()
        T = (b - a).normalized()
        S = T.cross(n).normalized()
        x = p.width * (0.5 - p.rail_width) * 0.55
        for side in (-1, 1):
            base = pos + S * (side * x) + n * (p.lift + p.thickness)
            start = len(verts)
            for k in range(sides):
                ang = 2 * math.pi * k / sides
                off = (T * math.cos(ang) + S * math.sin(ang)) * r
                verts.append(base + off - n * h * 0.3)
                verts.append(base + off * 0.8 + n * h)
            for k in range(sides):
                k2 = (k + 1) % sides
                faces.append((start + 2 * k, start + 2 * k2, start + 2 * k2 + 1, start + 2 * k + 1))
            faces.append(tuple(start + 2 * k + 1 for k in range(sides)))
            faces.append(tuple(start + 2 * k for k in range(sides - 1, -1, -1)))
    return verts, faces


def source(ob):
    if ob is None:
        return None
    try:
        raw = ob.get(SRC_KEY)
    except (TypeError, ReferenceError):
        return None
    try:
        return json.loads(raw) if raw else None
    except (TypeError, ValueError):
        return None


def rebuild(context, ob):
    verts, faces = build(context, ob)
    inv = ob.matrix_world.inverted_safe()
    me = ob.data
    me.clear_geometry()
    me.from_pydata([tuple(inv @ v) for v in verts], [], faces)
    me.validate()
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        for f in bm.faces:
            f.smooth = True
        bm.to_mesh(me)
    finally:
        bm.free()
    try:
        me.set_sharp_from_angle(angle=math.radians(35))      # smooth along the strap, crisp corners
    except (AttributeError, TypeError, RuntimeError):
        pass
    ob.data.update()


def perform(context, path, projector):
    """Open drawn path (pixels) -> a live belt.  Returns a report; raises cg.CutError."""
    from . import armor_plate as ap
    from . import face_extract as fx
    path = [tuple(q) for q in path]
    if len(path) < 2:
        raise cg.CutError('Belt: draw a line (at least 2 points).')
    target = pick_target(context, projector, path)
    if target is None:
        raise cg.CutError('Belt: draw the line over a mesh.')
    frozen = ap.freeze_projector(projector)
    if frozen is None:
        raise cg.CutError('This view cannot be saved for the belt.')
    st = context.scene.mch_belt
    me = bpy.data.meshes.new(target.name + '_Belt')
    ob = bpy.data.objects.new(me.name, me)
    fx._parts_collection(context, COLLECTION).objects.link(ob)
    ob[SRC_KEY] = json.dumps({'path': [[float(x), float(y)] for x, y in path], 'proj': frozen,
                              'target': target.name, 'stamp': id(ob) % 100000})
    p = ob.mch_belt
    for k in LIVE_KEYS:
        setattr(p, k, getattr(st, k))
    try:
        rebuild(context, ob)
    except Exception:
        _CACHE.pop(ob.name, None)
        bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.meshes.remove(me)
        raise
    cen = sum((v.co for v in me.vertices), Vector()) / max(1, len(me.vertices))
    me.transform(Matrix.Translation(-cen))
    ob.matrix_world = Matrix.Translation(cen)
    p.live = True
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    preset = dict((i[0], i[1]) for i in PRESET_ITEMS)[p.preset]
    how = 'around' if p.mode == 'WRAP' else 'along the line on'
    return f'Belt "{ob.name}" {how} {target.name} ({preset})'


def live_belt(context):
    ob = getattr(context, 'active_object', None)
    if ob is not None and getattr(ob, 'mch_belt', None) is not None and ob.mch_belt.live and source(ob):
        return ob
    return None


class MCH_OT_belt_apply(bpy.types.Operator):
    bl_idname = 'mch.belt_apply'
    bl_label = 'Apply Belt'
    bl_description = 'The belt becomes a plain mesh (the sliders stop rebuilding it)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return live_belt(context) is not None

    def execute(self, context):
        ob = live_belt(context)
        ob.mch_belt.live = False
        del ob[SRC_KEY]
        _CACHE.pop(ob.name, None)
        self.report({'INFO'}, f'{ob.name}: applied')
        return {'FINISHED'}


def draw(layout, context):
    ob = live_belt(context)
    p = ob.mch_belt if ob is not None else context.scene.mch_belt
    if ob is not None:
        box = layout.box()
        box.label(text='LIVE: ' + ob.name, icon='MOD_CURVE')
        if p.last_error:
            box.label(text=p.last_error, icon='ERROR')
        target = box
    else:
        layout.label(text='Settings for the next belt', icon='MOD_CURVE')
        target = layout
    target.row(align=True).prop(p, 'mode', expand=True)
    target.row(align=True).prop(p, 'preset', expand=True)
    col = target.column(align=True)
    col.prop(p, 'width')
    col.prop(p, 'thickness')
    col.prop(p, 'lift')
    col = target.column(align=True)
    if p.preset == 'PLAIN':
        col.prop(p, 'edge_round', slider=True)
    elif p.preset == 'WEBBING':
        col.prop(p, 'ribs')
        row = col.row(align=True)
        row.prop(p, 'buckle', toggle=True)
        sub = row.row(align=True)
        sub.enabled = p.buckle
        sub.prop(p, 'buckle_shift', text='Position', slider=True)
    else:
        col.prop(p, 'rail_height')
        col.prop(p, 'rail_width', slider=True)
        col.prop(p, 'groove', slider=True)
        row = col.row(align=True)
        row.prop(p, 'bolts', toggle=True)
        sub = row.row(align=True)
        sub.enabled = p.bolts
        sub.prop(p, 'bolt_spacing', text='Spacing')
    col = target.column(align=True)
    col.prop(p, 'smooth')
    col.prop(p, 'density')
    if ob is not None:
        target.operator('mch.belt_apply', icon='CHECKMARK')
    col = layout.column(align=True)
    col.scale_y = 0.8
    for line in ('Click points (or Free Draw) over a mesh, Enter / double-click',
                 'Wrap: all the way around where the line crosses', 'Follow: only along the line',
                 'Apply: plain mesh'):
        col.label(text=line)


CLASSES = (MCH_PG_Belt, MCH_OT_belt_apply)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_belt = bpy.props.PointerProperty(type=MCH_PG_Belt)
    bpy.types.Object.mch_belt = bpy.props.PointerProperty(type=MCH_PG_Belt)


def unregister():
    for n, t in (('mch_belt', bpy.types.Object), ('mch_belt', bpy.types.Scene)):
        try:
            delattr(t, n)
        except AttributeError:
            pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
    _CACHE.clear()
