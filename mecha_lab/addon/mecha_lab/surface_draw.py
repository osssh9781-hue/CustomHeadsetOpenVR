"""0.24.33 Surface Draw and Cloth Brush: draw on a surface (like painting on a model in VR) - a band of mesh lies
along the stroke.

* Surface Draw: a raised band - edges Square (90 degrees), Chamfer, Bevel (round), or Round / Ridge - Height
  above the surface.  Fill Area: a closed lasso is filled at the same height with the same edge.
* Cloth Brush: a thin strip of cloth along the stroke - it puffs up in the middle, wrinkles across, Thickness.
* Every stroke keeps the same Width and Height as the first one (Keep First Size): lift the pen, draw again and
  the new band matches.  Bands are laid on the mesh you draw on, never on bands drawn before, so crossing strokes
  stay at the same height (nothing piles up).
* Strokes on the same mesh go into one live object (Join Strokes); every slider rebuilds all of them.
  Remove Last Stroke, Apply (plain mesh).
``cross_heights``, ``end_factors``, ``frames`` and ``band_grid`` are pure.
"""
from __future__ import annotations

import json
import math
import random

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from mathutils import Matrix, Vector

from . import core_geometry as cg

SRC_KEY = 'mch_sdraw_src'
COLLECTION = 'Surface Draw'
KIND_ITEMS = [('BAND', 'Surface Draw', 'A raised band on the surface'),
              ('CLOTH', 'Cloth Brush', 'A thin strip of cloth on the surface')]
PROFILE_ITEMS = [
    ('SQUARE', 'Square', 'Flat top, straight (90 degree) sides and ends'),
    ('CHAMFER', 'Chamfer', 'Flat top, a straight slope at the edges'),
    ('BEVEL', 'Bevel', 'Flat top, round edges'),
    ('ROUND', 'Round', 'Half round'),
    ('RIDGE', 'Ridge', 'A sharp ridge along the middle'),
]
LIVE_KEYS = ('profile', 'width', 'height', 'edge', 'fill_res', 'sink', 'smooth', 'density', 'across', 'end_round', 'thickness',
             'puff', 'folds', 'fold_depth', 'fold_random', 'seed')


# -----------------------------------------------------------------------------
# pure parts
# -----------------------------------------------------------------------------


def cross_heights(profile, n, edge=0.3):
    """Heights 0..1 across the band at n points from one edge (-1) to the other (+1)."""
    out = []
    for j in range(n):
        x = -1.0 + 2.0 * j / max(1, n - 1)
        a = abs(x)
        if profile == 'SQUARE':
            h = 1.0                                          # straight sides: the walls stand at the edges
        elif profile == 'ROUND':
            h = math.sqrt(max(0.0, 1.0 - a * a))
        elif profile == 'RIDGE':
            h = 1.0 - a
        elif profile == 'CHAMFER':
            h = min(1.0, (1.0 - a) / max(edge, 1e-3))
        else:                                                # BEVEL: quarter circles at the edges
            e = max(edge, 1e-3)
            h = 1.0 if a <= 1.0 - e else math.sqrt(max(0.0, 1.0 - ((a - (1.0 - e)) / e) ** 2))
        out.append(max(0.0, h))
    return out


def edge_height(profile, d, edge_w, deepest):
    """Lasso fill: height 0..1 of a point ``d`` in from the outline (Square = full right to the edge)."""
    if profile == 'SQUARE':
        return 1.0
    if profile in {'ROUND', 'RIDGE'}:
        edge_w = max(deepest, 1e-9)
    t = min(1.0, d / max(edge_w, 1e-9))
    if profile in {'CHAMFER', 'RIDGE'}:
        return t
    return math.sqrt(max(0.0, 1.0 - (1.0 - t) ** 2))


def end_factors(lengths, reach):
    """0 at both ends of the stroke, 1 after ``reach`` (a round cap: the band slopes down to the surface)."""
    total = lengths[-1] if lengths else 0.0
    out = []
    for s in lengths:
        d = min(s, total - s)
        t = 1.0 if reach <= 1e-9 else min(1.0, d / reach)
        out.append(math.sqrt(max(0.0, 1.0 - (1.0 - t) ** 2)))
    return out


def arc_lengths(pts):
    out = [0.0]
    for a, b in zip(pts, pts[1:]):
        out.append(out[-1] + (Vector(b) - Vector(a)).length)
    return out


def frames(pts, normals):
    """(tangent, side) per point: the tangent along the stroke lying on the surface, side = tangent x normal."""
    out = []
    n = len(pts)
    for i in range(n):
        t = Vector(pts[min(i + 1, n - 1)]) - Vector(pts[max(i - 1, 0)])
        nrm = Vector(normals[i])
        t = t - nrm * t.dot(nrm)
        if t.length < 1e-12:
            t = out[-1][0] if out else nrm.orthogonal()
        t.normalize()
        out.append((t, t.cross(nrm).normalized()))
    return out


def band_grid(rows_top, rows_bottom):
    """Faces of a closed band: top rows [i][j], bottom rows [i][j] (vertex indices)."""
    faces = []
    n, m = len(rows_top), len(rows_top[0])
    for i in range(n - 1):
        for j in range(m - 1):
            faces.append((rows_top[i][j], rows_top[i][j + 1], rows_top[i + 1][j + 1], rows_top[i + 1][j]))
            faces.append((rows_bottom[i + 1][j], rows_bottom[i + 1][j + 1], rows_bottom[i][j + 1], rows_bottom[i][j]))
    for i in range(n - 1):                                   # the two long sides
        faces.append((rows_bottom[i][0], rows_top[i][0], rows_top[i + 1][0], rows_bottom[i + 1][0]))
        faces.append((rows_top[i][m - 1], rows_bottom[i][m - 1], rows_bottom[i + 1][m - 1], rows_top[i + 1][m - 1]))
    for i, flip in ((0, True), (n - 1, False)):              # the two ends
        ring = rows_top[i] + rows_bottom[i][::-1]
        faces.append(tuple(ring[::-1]) if flip else tuple(ring))
    return faces


# -----------------------------------------------------------------------------
# settings
# -----------------------------------------------------------------------------


def _update(self, context):
    ob = self.id_data
    if not isinstance(ob, bpy.types.Object) or not self.live:
        return
    try:
        rebuild(context, ob)
        self.last_error = ''
    except (cg.CutError, ValueError, RuntimeError) as ex:
        self.last_error = str(ex)


def _p(prop, **kw):
    kw.setdefault('update', _update)
    return prop(**kw)


class MCH_PG_SurfaceDraw(bpy.types.PropertyGroup):
    """Scene.mch_sdraw / Scene.mch_clothb = the next stroke; Object.mch_sdraw = a live band object."""
    kind: EnumProperty(items=KIND_ITEMS, default='BAND', options={'HIDDEN'})
    profile: _p(EnumProperty, name='Edge', items=PROFILE_ITEMS, default='SQUARE')
    width: _p(FloatProperty, name='Width', default=0.0, min=0.0, soft_max=1.0, unit='LENGTH', precision=4,
              description='Band width (0 = from the Line Width on screen; Keep First Size stores it)')
    height: _p(FloatProperty, name='Height', default=0.0, min=0.0, soft_max=0.5, unit='LENGTH', precision=4,
               description='How high the band stands above the surface (0 = a third of the width)')
    edge: _p(FloatProperty, name='Edge Size', default=0.35, min=0.02, max=1.0,
             description='Chamfer / Bevel: how wide the slope / round edge is')
    fill_res: _p(IntProperty, name='Fill Resolution', default=15, min=4, max=60,
                 description='Lasso fill: points across the filled area')
    sink: _p(FloatProperty, name='Sink', default=0.0, min=0.0, soft_max=0.1, unit='LENGTH', precision=4,
             description='How far the bottom goes into the surface (0 = Auto, no gaps on curves)')
    smooth: _p(IntProperty, name='Smooth Line', default=3, min=0, max=30, description='Smooth the drawn line')
    density: _p(FloatProperty, name='Density', default=3.0, min=0.5, max=12.0,
                description='Rings along the band per width')
    across: _p(IntProperty, name='Across', default=9, min=3, max=33, description='Points across the band')
    end_round: _p(FloatProperty, name='Round Ends', default=0.5, min=0.0, max=3.0,
                  description='How far (x the width) the ends slope down to the surface')
    thickness: _p(FloatProperty, name='Thickness', default=0.0, min=0.0, soft_max=0.05, unit='LENGTH', precision=4,
                  description='Cloth thickness (0 = Auto, very thin)')
    puff: _p(FloatProperty, name='Puff', default=0.35, min=0.0, max=2.0,
             description='Cloth: how much the middle puffs up off the surface (x the height)')
    folds: _p(FloatProperty, name='Folds', default=1.2, min=0.0, max=6.0,
              description='Cloth: wrinkles across the strip (per width)')
    fold_depth: _p(FloatProperty, name='Fold Depth', default=0.6, min=0.0, max=3.0,
                   description='Cloth: wrinkle depth (x the height)')
    fold_random: _p(FloatProperty, name='Fold Random', default=0.5, min=0.0, max=1.0)
    seed: _p(IntProperty, name='Seed', default=1, min=0)
    keep_size: BoolProperty(name='Keep First Size', default=True,
                            description='Every stroke gets the Width and Height of the first one')
    fill: BoolProperty(name='Fill Area', default=False,
                       description='Lasso (closed): fill the area at the same height (off: the lasso is a line path)')
    join: BoolProperty(name='Join Strokes', default=True,
                       description='Strokes on the same mesh go into one live object')
    live: BoolProperty(default=False, options={'HIDDEN'})
    last_error: StringProperty(default='', options={'HIDDEN', 'SKIP_SAVE'})


# -----------------------------------------------------------------------------
# building
# -----------------------------------------------------------------------------


def source(ob):
    try:
        raw = ob.get(SRC_KEY) if ob is not None else None
        return json.loads(raw) if raw else None
    except (TypeError, ValueError, ReferenceError):
        return None


def _smooth(pts, passes):
    pts = [Vector(p) for p in pts]
    for _ in range(passes):
        if len(pts) < 3:
            break
        pts = [pts[0]] + [(pts[i - 1] + pts[i] * 2 + pts[i + 1]) / 4 for i in range(1, len(pts) - 1)] + [pts[-1]]
    return pts


def _resample(pts, step):
    lens = arc_lengths(pts)
    total = lens[-1]
    if total < 1e-9:
        return [Vector(pts[0])]
    n = max(2, int(math.ceil(total / max(step, 1e-9))) + 1)
    out, j = [], 0
    for i in range(n):
        s = total * i / (n - 1)
        while j < len(pts) - 2 and lens[j + 1] < s:
            j += 1
        seg = lens[j + 1] - lens[j]
        out.append(Vector(pts[j]).lerp(Vector(pts[j + 1]), 0.0 if seg < 1e-12 else (s - lens[j]) / seg))
    return out


def _nearest(bvh, q):
    loc, n, _i, _d = bvh.find_nearest(q)
    if loc is None:
        return Vector(q), Vector((0, 0, 1))
    return loc, n.normalized()


def stroke_mesh(bvh, stroke, p, width, height, size):
    """(verts, faces) of one stroke's band (world)."""
    pts = _resample(_smooth(stroke, p.smooth), width / max(0.5, p.density) / (2.0 if p.kind == 'CLOTH' else 1.0))
    if len(pts) < 2:
        return [], []
    base = [_nearest(bvh, q) for q in pts]
    pts = [b[0] for b in base]
    nrms = [b[1] for b in base]
    fr = frames(pts, nrms)
    lens = arc_lengths(pts)
    ends = end_factors(lens, width * p.end_round) if p.profile != 'SQUARE' or p.kind == 'CLOTH' else [1.0] * len(lens)
    m = max(3, p.across | 1)
    prof = cross_heights(p.profile if p.kind == 'BAND' else 'ROUND', m, p.edge)
    sink = p.sink if p.sink > 0 else width * 0.08
    thick = p.thickness if p.thickness > 0 else max(size * 0.0008, width * 0.04)
    rng = random.Random(p.seed)
    phase = [rng.uniform(0, 2 * math.pi) for _ in range(4)]
    verts, top, bot = [], [], []
    for i, (c, (t, s)) in enumerate(zip(pts, fr)):
        rt, rb = [], []
        for j in range(m):
            x = -1.0 + 2.0 * j / (m - 1)
            b, nb = _nearest(bvh, c + s * (x * width / 2.0))
            if p.kind == 'CLOTH':
                wave = math.sin(2 * math.pi * lens[i] * p.folds / max(width, 1e-9) + phase[0]
                                + p.fold_random * 1.7 * math.sin(3.1 * x + phase[1]))
                wave += p.fold_random * 0.5 * math.sin(2 * math.pi * lens[i] * p.folds * 2.3 / max(width, 1e-9)
                                                       + phase[2])
                lift = height * (p.puff * prof[j] + p.fold_depth * 0.5 * (wave + 1.0) * prof[j]) * ends[i]
                mid = b + nb * (thick * 0.5 + lift)
                rt.append(len(verts))
                verts.append(mid + nb * thick * 0.5)
                rb.append(len(verts))
                verts.append(mid - nb * thick * 0.5)
            else:
                rt.append(len(verts))
                verts.append(b + nb * (prof[j] * height * ends[i]))
                rb.append(len(verts))
                verts.append(b - nb * sink)
        top.append(rt)
        bot.append(rb)
    return verts, band_grid(top, bot)


def build(context, src, p, target):
    from . import cape_gen
    bvh, lo, hi = cape_gen._body(context, target)
    size = (hi - lo).length
    width = p.width if p.width > 0 else size * 0.03
    height = p.height if p.height > 0 else width / 3.0
    bm = bmesh.new()
    for stroke in src['strokes']:
        v, f = stroke_mesh(bvh, [Vector(q) for q in stroke], p, width, height, size)
        if not v:
            continue
        bv = [bm.verts.new(q) for q in v]
        for face in f:
            try:
                bm.faces.new([bv[k] for k in face]).smooth = True
            except ValueError:
                pass
    for fill in src.get('fills', []):
        v, f = fill_mesh(fill, p, width, height, size)
        bv = [bm.verts.new(q) for q in v]
        for face in f:
            try:
                bm.faces.new([bv[k] for k in face]).smooth = True
            except ValueError:
                pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-9)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def fill_mesh(fill, p, width, height, size):
    """(verts, faces) of a filled lasso area: the points on the surface, raised by the edge profile."""
    cos = [Vector(q) for q in fill['cos']]
    nrms = [Vector(q) for q in fill['nrms']]
    dist = fill['dist']
    nb = fill['nb']
    tris = fill['tris']
    deepest = max(dist) if dist else 1.0
    sink = p.sink if p.sink > 0 else width * 0.08
    thick = p.thickness if p.thickness > 0 else max(size * 0.0008, width * 0.04)
    ew = p.edge * height * 2.0
    rng = random.Random(p.seed)
    ph = [rng.uniform(0, 2 * math.pi) for _ in range(4)]
    axis_u = (cos[min(1, len(cos) - 1)] - cos[0]).normalized() if len(cos) > 1 else Vector((1, 0, 0))
    verts, top, bot = [], [], []
    for i, (c, n) in enumerate(zip(cos, nrms)):
        if p.kind == 'CLOTH':
            soft = math.sqrt(min(1.0, dist[i] / max(width * 0.5, 1e-9)))
            u = c.dot(axis_u)
            w = math.sin(2 * math.pi * u * p.folds / max(width, 1e-9) + ph[0]
                         + p.fold_random * 2.0 * math.sin(c.dot(n.orthogonal()) * 7.0 / max(width, 1e-9) + ph[1]))
            lift = height * soft * (p.puff + p.fold_depth * 0.5 * (w + 1.0))
            mid = c + n * (thick * 0.5 + lift)
            top.append(len(verts))
            verts.append(mid + n * thick * 0.5)
            bot.append(len(verts))
            verts.append(mid - n * thick * 0.5)
        else:
            top.append(len(verts))
            verts.append(c + n * (height * edge_height(p.profile, dist[i], ew, deepest)))
            bot.append(len(verts))
            verts.append(c - n * sink)
    faces = []
    for a, b, c in tris:
        faces.append((top[a], top[b], top[c]))
        faces.append((bot[c], bot[b], bot[a]))
    rim = set()
    for a, b, c in tris:
        for u, v in ((a, b), (b, c), (c, a)):
            if u < nb and v < nb:
                rim.add((u, v))
    for u, v in rim:
        if (v, u) in rim:
            continue
        faces.append((top[v], top[u], bot[u], bot[v]))
    return verts, faces


def rebuild(context, ob):
    src = source(ob)
    if src is None:
        raise cg.CutError('This was applied (no strokes kept).')
    target = bpy.data.objects.get(src.get('target', ''))
    if target is None or target.type != 'MESH':
        raise cg.CutError('The mesh it was drawn on is gone.')
    bm = build(context, src, ob.mch_sdraw, target)
    try:
        bmesh.ops.transform(bm, matrix=ob.matrix_world.inverted_safe(), verts=bm.verts[:])
        bm.to_mesh(ob.data)
    finally:
        bm.free()
    try:
        ob.data.set_sharp_from_angle(angle=math.radians(50))
    except (AttributeError, TypeError, RuntimeError):
        pass
    ob.data.update()


def is_generated(ob):
    try:
        return any(k.startswith('mch_') and (k.endswith('_src') or k.endswith('_source')) for k in ob.keys())
    except (TypeError, AttributeError, ReferenceError):
        return True


def pick_base(context, projector, path):
    """The mesh under the line - generated parts (bands drawn before, plates, capes ...) are looked through, so a
    new band never lies on an old one."""
    from . import armor_plate as ap
    dg = context.evaluated_depsgraph_get()
    counts = {}
    probes = list(path[::max(1, len(path) // 30)]) + [path[-1]]
    for xy in probes:
        o, d = projector.ray(xy)
        o, d = Vector(o), Vector(d).normalized()
        for _k in range(64):
            hit, loc, _n, _i, hob, _m = context.scene.ray_cast(dg, o, d)
            if not hit or hob is None:
                break
            real = bpy.data.objects.get(hob.name)
            if real is not None and real.type == 'MESH' and not is_generated(real) and not ap.is_plate_or_part(real):
                counts[real.name] = counts.get(real.name, 0) + 1
                break
            o = loc + d * 1e-4
    return bpy.data.objects[max(counts, key=counts.get)] if counts else None


def scene_settings(scene, kind):
    return scene.mch_clothb if kind == 'CLOTH' else scene.mch_sdraw


def perform(context, path, projector, kind='BAND'):
    """A line drawn on a mesh -> a band on it (joined to that mesh's live band object).  Returns a report."""
    from . import armor_plate as ap
    from . import cape_gen
    from . import face_extract as fx
    from . import lasso_line
    path = [tuple(q) for q in path]
    if len(path) < 2:
        raise cg.CutError('Draw a line on a mesh.')
    target = pick_base(context, projector, path)
    if target is None:
        raise cg.CutError('Draw on a mesh.')
    st = scene_settings(context.scene, kind)
    bvh, lo, hi = cape_gen._body(context, target)
    dense = [path[0]]
    for a, b in zip(path, path[1:]):
        n = max(1, int(math.dist(a, b) / 4.0))
        dense += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(1, n + 1)]
    cos, _n, _miss = ap.project_patch(dense, projector, bvh)
    stroke = [Vector(c) for c in cos]
    if arc_lengths(stroke)[-1] <= 1e-9:
        raise cg.CutError('The line is too short.')
    return _add(context, target, kind, st, stroke=stroke)


def _add(context, target, kind, st, stroke=None, fills=()):
    """Put a stroke / filled areas into the target's live object (new or joined); the first size is kept."""
    from . import cape_gen
    from . import face_extract as fx
    _bvh, lo, hi = cape_gen._body(context, target)
    if st.width <= 0:                                        # the first stroke: Line Width -> the band width
        brush = getattr(context.scene, 'mch_brush', None)
        st.width = max(1e-5, getattr(brush, 'line_width', 0.0)) if brush is not None else (hi - lo).length * 0.03
        if st.width <= 1e-5:
            st.width = (hi - lo).length * 0.03
    if st.height <= 0:
        st.height = st.width / (3.0 if kind == 'BAND' else 4.0)
    ob = None
    if st.join:
        for o in bpy.data.objects:
            s = source(o)
            if s and s.get('target') == target.name and o.mch_sdraw.live and o.mch_sdraw.kind == kind:
                ob = o
                break
    if ob is not None:
        src = source(ob)
        if stroke is not None:
            src['strokes'].append([list(c) for c in stroke])
        src.setdefault('fills', []).extend(fills)
        src.setdefault('order', []).append('fill' if stroke is None else 'stroke')
        ob[SRC_KEY] = json.dumps(src)
    else:
        me = bpy.data.meshes.new(target.name + ('_Cloth' if kind == 'CLOTH' else '_Draw'))
        ob = bpy.data.objects.new(me.name, me)
        fx._parts_collection(context, COLLECTION).objects.link(ob)
        for mat in target.data.materials:
            me.materials.append(mat)
        ob[SRC_KEY] = json.dumps({'target': target.name, 'strokes': [[list(c) for c in stroke]] if stroke else [],
                                  'fills': list(fills), 'order': ['fill' if stroke is None else 'stroke']})
        p = ob.mch_sdraw
        p.kind = kind
        for k in LIVE_KEYS:
            setattr(p, k, getattr(st, k))
        p.live = True
    p = ob.mch_sdraw
    if not st.keep_size:                                     # a new size for this stroke: the object follows
        p.width, p.height = st.width, st.height
    try:
        rebuild(context, ob)
    except Exception:
        raise
    if not st.keep_size:
        st.width = 0.0
        st.height = 0.0
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    s = source(ob)
    n = len(s['strokes'])
    return (f'{"Cloth Brush" if kind == "CLOTH" else "Surface Draw"}: {n} stroke(s), '
            f'{len(s.get("fills", []))} filled area(s) on {target.name}')


def perform_fill(context, loops, projector, kind='BAND'):
    """A closed lasso on a mesh -> the area filled at the same height (joined like the strokes)."""
    from types import SimpleNamespace
    from . import armor_plate as ap
    from . import base_mesh as bmm
    from . import cape_gen
    groups = cg.prepare_loops(loops)
    if not groups:
        raise cg.CutError('Draw a closed outline on a mesh.')
    path = [q for lp in loops for q in lp]
    target = pick_base(context, projector, path)
    if target is None:
        raise cg.CutError('Draw on a mesh.')
    st = scene_settings(context.scene, kind)
    bvh, lo, hi = cape_gen._body(context, target)
    fills = []
    for outer, holes in groups:
        q = SimpleNamespace(profile='PILLOW', outline_smooth=0.0, resolution=st.fill_res, edge_round=0.15, puff=1.0)
        _b, pts, tris, nb, _shape, _nat, _sp = bmm.profile_field(outer, holes, q)
        cos, nrms, _miss = ap.project_patch(pts, projector, bvh)
        ratios = []
        for a, b, _c in tris[::max(1, len(tris) // 200)]:
            dp = math.dist(pts[a], pts[b])
            if dp > 1e-9:
                ratios.append((cos[a] - cos[b]).length / dp)
        ratios.sort()
        k = ratios[len(ratios) // 2] if ratios else 1.0
        dist = [d * k for d in bmm._distances(pts, [outer] + list(holes))]
        nrms = [Vector(n) for n in nrms]
        fills.append({'cos': [list(c) for c in cos], 'nrms': [list(n) for n in nrms], 'tris': [list(t) for t in tris],
                      'nb': nb, 'dist': dist})
    return _add(context, target, kind, st, fills=fills)


def live_object(context, kind=None):
    ob = getattr(context, 'active_object', None)
    if ob is not None and getattr(ob, 'mch_sdraw', None) is not None and ob.mch_sdraw.live and source(ob):
        if kind is None or ob.mch_sdraw.kind == kind:
            return ob
    return None


class MCH_OT_sdraw_pop(bpy.types.Operator):
    bl_idname = 'mch.sdraw_pop'
    bl_label = 'Remove Last Stroke'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return live_object(context) is not None

    def execute(self, context):
        ob = live_object(context)
        src = source(ob)
        if len(src['strokes']) + len(src.get('fills', [])) <= 1:
            me = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            if me.users == 0:
                bpy.data.meshes.remove(me)
            return {'FINISHED'}
        order = src.get('order') or ['stroke'] * len(src['strokes'])
        last = order.pop() if order else 'stroke'
        if last == 'fill' and src.get('fills'):
            src['fills'].pop()
        elif src['strokes']:
            src['strokes'].pop()
        src['order'] = order
        ob[SRC_KEY] = json.dumps(src)
        rebuild(context, ob)
        return {'FINISHED'}


class MCH_OT_sdraw_apply(bpy.types.Operator):
    bl_idname = 'mch.sdraw_apply'
    bl_label = 'Apply'
    bl_description = 'Make it a plain mesh (the sliders stop rebuilding it)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return live_object(context) is not None

    def execute(self, context):
        ob = live_object(context)
        ob.mch_sdraw.live = False
        del ob[SRC_KEY]
        return {'FINISHED'}


class MCH_OT_sdraw_reset_size(bpy.types.Operator):
    bl_idname = 'mch.sdraw_reset_size'
    bl_label = 'New Size'
    bl_description = 'The next stroke takes its size from the Line Width again (and keeps it after)'
    bl_options = {'INTERNAL'}
    kind: EnumProperty(items=KIND_ITEMS, default='BAND')

    def execute(self, context):
        st = scene_settings(context.scene, self.kind)
        st.width = 0.0
        st.height = 0.0
        return {'FINISHED'}


def draw(layout, context, kind='BAND'):
    ob = live_object(context, kind)
    st = scene_settings(context.scene, kind)
    p = ob.mch_sdraw if ob is not None else st
    box = layout.box()
    if ob is not None:
        sr = source(ob)
        box.label(text=f'LIVE: {ob.name} ({len(sr["strokes"])} strokes, {len(sr.get("fills", []))} fills)',
                  icon='GREASEPENCIL')
        if p.last_error:
            box.label(text=p.last_error, icon='ERROR')
    else:
        box.label(text='Next stroke', icon='GREASEPENCIL')
    if kind == 'BAND':
        box.row(align=True).prop(p, 'profile', expand=True)
    col = box.column(align=True)
    col.prop(p, 'width')
    col.prop(p, 'height')
    if kind == 'BAND':
        if p.profile in {'CHAMFER', 'BEVEL'}:
            col.prop(p, 'edge', slider=True)
        col.prop(p, 'sink')
    else:
        col.prop(p, 'thickness')
        col.prop(p, 'puff', slider=True)
        col.prop(p, 'folds', slider=True)
        col.prop(p, 'fold_depth', slider=True)
        col.prop(p, 'fold_random', slider=True)
        col.prop(p, 'seed')
    col = box.column(align=True)
    col.prop(p, 'end_round', slider=True)
    col.prop(p, 'smooth')
    r = col.row(align=True)
    r.prop(p, 'density')
    r.prop(p, 'across')
    if ob is not None:
        row = box.row(align=True)
        row.operator('mch.sdraw_pop', icon='LOOP_BACK')
        row.operator('mch.sdraw_apply', icon='CHECKMARK')
    layout.prop(st, 'fill', toggle=True, icon='MOD_SOLIDIFY')
    if st.fill:
        layout.prop(st, 'fill_res')
    row = layout.row(align=True)
    row.prop(st, 'keep_size', toggle=True)
    row.prop(st, 'join', toggle=True)
    layout.operator('mch.sdraw_reset_size', icon='FILE_REFRESH').kind = kind
    col = layout.column(align=True)
    col.scale_y = 0.8
    for line in ('Draw a line on a mesh (hold and drag); Lasso = a path of points',
                 'Fill Area on: a closed lasso is filled at the same height',
                 'Lift the pen and draw again: same width and height', 'Never piles up on what was drawn before'):
        col.label(text=line)


CLASSES = (MCH_PG_SurfaceDraw, MCH_OT_sdraw_pop, MCH_OT_sdraw_apply, MCH_OT_sdraw_reset_size)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_sdraw = bpy.props.PointerProperty(type=MCH_PG_SurfaceDraw)
    bpy.types.Scene.mch_clothb = bpy.props.PointerProperty(type=MCH_PG_SurfaceDraw)
    bpy.types.Object.mch_sdraw = bpy.props.PointerProperty(type=MCH_PG_SurfaceDraw)


def unregister():
    for n, t in (('mch_sdraw', bpy.types.Object), ('mch_clothb', bpy.types.Scene), ('mch_sdraw', bpy.types.Scene)):
        try:
            delattr(t, n)
        except AttributeError:
            pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
