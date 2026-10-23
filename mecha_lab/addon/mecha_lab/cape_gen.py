"""0.24.28 Cape Generator: draw on a body (from the side the cape should hang) -> a live cloak / capelet / poncho.

The TOP edge of what you draw is where the cape hangs from (collar / shoulders).  Shape:

    Outline   the drawn silhouette is the cape (its bottom edge = the hem, as seen from the view)
    Preset    only the top edge counts; Length and Hem (Straight / Round / Pointed / Split) make the rest
    Auto      a short wide drawing (or Line mode) = Preset, a tall one = Outline

How it hangs (no simulation, so every slider is instant): the collar is the top edge laid on the body through the
view, pushed out by Gap and, with Wrap, carried on round the body on both sides.  Every column of cloth falls
straight down from the collar; wherever it would go into the body it is pushed back out to Gap (so it drapes over
the shoulders and hangs at the back), Flare spreads it outward as it falls.  Then folds (vertical, growing toward
the hem, with some randomness), Wind (the lower part swings sideways) and Tatter (a ragged hem) are added and the
sheet gets its thickness (a closed mesh).

Styles fill in the sliders from the references: Capelet (short, round), Cloak (long), Poncho (wide, pointed),
Ragged (long, tattered).  ``hem_profile``, ``tatter_profile`` and ``columns`` are pure and tested headless.
"""
from __future__ import annotations

import json
import math
import random

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from . import core_geometry as cg

SRC_KEY = 'mch_cape_src'
COLLECTION = 'Capes'
STYLE_ITEMS = [
    ('CAPELET', 'Capelet', 'Short shoulder cape, round hem'),
    ('CLOAK', 'Cloak', 'Long cloak down to the legs'),
    ('PONCHO', 'Poncho', 'Wide and spread out, pointed hem, wraps far round'),
    ('RAGGED', 'Ragged', 'Long cloak with a torn, ragged hem'),
]
STYLES = {
    'CAPELET': dict(length=0.32, hem='ROUND', flare=0.35, straight=0.3, wrap=70.0, folds=7, fold_depth=0.025,
                    tatter=0.0),
    'CLOAK': dict(length=0.9, hem='ROUND', flare=0.22, straight=0.6, wrap=60.0, folds=9, fold_depth=0.035, tatter=0.0),
    'PONCHO': dict(length=0.55, hem='POINTED', flare=0.6, straight=0.0, wrap=110.0, folds=8, fold_depth=0.03,
                   tatter=0.0),
    'RAGGED': dict(length=0.88, hem='STRAIGHT', flare=0.25, straight=0.6, wrap=60.0, folds=11, fold_depth=0.04,
                   tatter=0.55),
}
HEM_ITEMS = [('STRAIGHT', 'Straight', 'Even hem'), ('ROUND', 'Round', 'Longest in the middle'),
             ('POINTED', 'Pointed', 'A point in the middle'), ('SPLIT', 'Split', 'Two tails, a notch in the middle')]
LIVE_KEYS = ('shape', 'length', 'hem', 'flare', 'straight', 'wrap', 'folds', 'fold_depth', 'fold_random', 'wind', 'wind_dir',
             'tatter', 'seed', 'thickness', 'gap', 'columns', 'rows')
_CACHE = {}          # object name -> (key, BVH data)


# -----------------------------------------------------------------------------
# Pure helpers
# -----------------------------------------------------------------------------


def hem_profile(s, hem):
    """Length factor at s (0..1 across the cape) for a hem shape."""
    c = abs(2.0 * s - 1.0)                # 0 in the middle, 1 at the sides
    if hem == 'ROUND':
        return 0.72 + 0.28 * math.cos(c * math.pi / 2)
    if hem == 'POINTED':
        return 0.6 + 0.4 * (1.0 - c)
    if hem == 'SPLIT':
        return 0.7 + 0.3 * min(1.0, c * 2.2) * (1.0 - 0.25 * c)
    return 1.0


def tatter_profile(n, amount, seed):
    """Per column length factor for a ragged hem: torn strips of random width and depth (1 = untouched)."""
    if amount <= 0 or n <= 0:
        return [1.0] * n
    rng = random.Random(seed)
    out = []
    while len(out) < n:
        w = rng.randint(1, 4)
        depth = rng.random() ** 1.5 * amount
        tooth = [1.0 - depth * (1.0 - abs(2 * (i + 0.5) / w - 1.0)) for i in range(w)]   # a pointed strip
        out += tooth
    return out[:n]


def columns(loop, n):
    """Top and bottom of the outline in n columns across it (screen x): [(x, top_y, bottom_y)]."""
    xs = [q[0] for q in loop]
    lo, hi = min(xs), max(xs)
    if hi - lo < 1e-6:
        return []
    out = []
    m = len(loop)
    for i in range(n):
        x = lo + (hi - lo) * (0.002 + 0.996 * i / max(1, n - 1))
        ys = []
        for j in range(m):
            a, b = loop[j], loop[(j + 1) % m]
            if (a[0] - x) * (b[0] - x) <= 0 and a[0] != b[0]:
                t = (x - a[0]) / (b[0] - a[0])
                ys.append(a[1] + (b[1] - a[1]) * t)
        if len(ys) >= 2:
            out.append((x, max(ys), min(ys)))
    return out


# -----------------------------------------------------------------------------
# Body
# -----------------------------------------------------------------------------


def _body(context, target):
    """World-space BVH of the evaluated body (cached until the body changes)."""
    dg = context.evaluated_depsgraph_get()
    ev = target.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        key = (target.name, len(me.vertices), len(me.polygons), tuple(round(x, 5) for r in target.matrix_world
                                                                        for x in r))
        hit = _CACHE.get(('body', target.name))
        if hit is not None and hit[0] == key:
            return hit[1]
        mw = ev.matrix_world
        verts = [mw @ v.co for v in me.vertices]
        polys = [tuple(p.vertices) for p in me.polygons]
    finally:
        ev.to_mesh_clear()
    lo = Vector([min(v[k] for v in verts) for k in range(3)])
    hi = Vector([max(v[k] for v in verts) for k in range(3)])
    data = (BVHTree.FromPolygons(verts, polys), lo, hi)
    _CACHE[('body', target.name)] = (key, data)
    return data


def _axis_at(bvh, lo, hi, z):
    """Centre (x, y) of the body's cross-section at height z (rays from outside toward the middle)."""
    c = (lo + hi) / 2
    r = (hi - lo).length + 1.0
    pts = []
    for k in range(24):
        a = 2 * math.pi * k / 24
        d = Vector((math.cos(a), math.sin(a), 0.0))
        o = Vector((c.x, c.y, z)) + d * r
        loc, _n, _i, _dist = bvh.ray_cast(o, -d, 2 * r)
        if loc is not None:
            pts.append(loc)
    if not pts:
        return Vector((c.x, c.y, z))
    s = sum(pts, Vector())
    return Vector((s.x / len(pts), s.y / len(pts), z))


def _surface_at(bvh, lo, hi, axis, angle, z):
    """The body surface point seen from outside along a horizontal direction at height z."""
    r = (hi - lo).length + 1.0
    d = Vector((math.cos(angle), math.sin(angle), 0.0))
    o = Vector((axis.x, axis.y, z)) + d * r
    loc, n, _i, _dist = bvh.ray_cast(o, -d, 2 * r)
    if loc is None:
        return None, d
    if n.dot(d) < 0:
        n = -n
    return loc, n


# -----------------------------------------------------------------------------
# Build
# -----------------------------------------------------------------------------


def _collar(context, src, p, bvh, lo, hi):
    """Collar points (world) + length per column (world) + the axis."""
    from . import armor_plate as ap
    projector = ap.thaw_projector(src['proj'])
    groups = cg.prepare_loops([[tuple(q) for q in lp] for lp in src['loops']])
    if not groups:
        raise cg.CutError('The outline is empty.')
    outer = groups[0][0]
    n = max(6, p.columns)
    cols = columns(outer, n)
    if len(cols) < 3:
        raise cg.CutError('Draw the cape wider (across the shoulders).')
    xs = [c[0] for c in cols]
    width_px = max(xs) - min(xs)
    tall_px = sum(c[1] - c[2] for c in cols) / len(cols)
    mode = p.shape
    if mode == 'AUTO':
        mode = 'PRESET' if tall_px < 0.35 * width_px else 'OUTLINE'
    tops = [(c[0], c[1]) for c in cols]
    cos, nrms, _miss = ap.project_patch(tops, projector, bvh)
    # world per pixel along the collar
    ratios = [(cos[i] - cos[i - 1]).length / max(1e-6, math.dist(tops[i], tops[i - 1])) for i in range(1, len(cos))]
    ratios.sort()
    k = ratios[len(ratios) // 2] if ratios else 0.01
    size = (hi - lo).length
    zc = sum(c.z for c in cos) / len(cos)
    axis = _axis_at(bvh, lo, hi, zc)
    ground = max(size * 0.05, zc - lo.z)
    if mode == 'OUTLINE':
        lengths = [max(size * 0.01, (c[1] - c[2]) * k) for c in cols]
    else:
        base = p.length * ground
        lengths = [base * hem_profile(i / (len(cols) - 1), p.hem) for i in range(len(cols))]
    pts = list(cos)
    # Wrap: carry the collar on round the body on both sides
    if p.wrap > 0.5 and len(pts) >= 2:
        ang = [math.atan2(c.y - axis.y, c.x - axis.x) for c in pts]

        def unwrap(a, ref):
            while a - ref > math.pi:
                a -= 2 * math.pi
            while a - ref < -math.pi:
                a += 2 * math.pi
            return a
        for i in range(1, len(ang)):
            ang[i] = unwrap(ang[i], ang[i - 1])
        span = abs(ang[-1] - ang[0])
        wrap = min(math.radians(p.wrap), max(0.0, (2 * math.pi - span) / 2 - math.radians(8)))
        step = max(span / max(1, len(pts) - 1), math.radians(4))
        extra = int(wrap / step)
        sgn = 1.0 if ang[-1] >= ang[0] else -1.0
        add_lo, add_hi = [], []
        for j in range(1, extra + 1):
            for end, sign, dest in ((0, -sgn, add_lo), (-1, sgn, add_hi)):
                # carry on round at the end's distance from the axis (rays sideways would catch the arms);
                # the drape pushes it out of the body where it is wider
                e = pts[end]
                r = math.hypot(e.x - axis.x, e.y - axis.y)
                a = ang[end] + sign * step * j
                dest.append(Vector((axis.x + r * math.cos(a), axis.y + r * math.sin(a), e.z)))
        pts = add_lo[::-1] + pts + add_hi
        if mode == 'OUTLINE':
            lengths = [lengths[0]] * len(add_lo) + lengths + [lengths[-1]] * len(add_hi)
        else:
            base = p.length * ground
            lengths = [base * hem_profile(i / (len(pts) - 1), p.hem) for i in range(len(pts))]
    t = tatter_profile(len(pts), p.tatter, p.seed)
    lengths = [L * f for L, f in zip(lengths, t)]
    return pts, lengths, axis, size


def _push_out(bvh, p, gap):
    hit = bvh.find_nearest(p)
    if hit[0] is None:
        return p
    q, n = hit[0], hit[1]
    d = (p - q).dot(n)
    if d < gap:
        return p + n * (gap - d)
    return p


def drape(bvh, axis, collar, lengths, rows, gap, flare):
    """Grid [column][row] of the hanging sheet (world)."""
    down = Vector((0.0, 0.0, -1.0))
    grid = []
    longest = max(lengths)
    step = max(longest / (rows * 4.0), 1e-5)
    for c, L in zip(collar, lengths):
        p = _push_out(bvh, c.copy(), gap)
        col = [p.copy()]
        travelled = 0.0
        want = [L * k / rows for k in range(1, rows + 1)]
        wi = 0
        prev = p.copy()
        guard = 0
        while wi < len(want) and guard < rows * 40:
            guard += 1
            out = Vector((p.x - axis.x, p.y - axis.y, 0.0))
            out = out.normalized() if out.length > 1e-9 else Vector()
            p = p + down * step + out * (flare * step)
            p = _push_out(bvh, p, gap)
            seg = (p - prev).length
            while wi < len(want) and travelled + seg >= want[wi]:
                t = (want[wi] - travelled) / max(seg, 1e-12)
                col.append(prev.lerp(p, t))
                wi += 1
            travelled += seg
            prev = p.copy()
        while len(col) < rows + 1:
            col.append(col[-1] + down * step)
        grid.append(col)
    return grid


def shape_sheet(grid, axis, p, size, bvh, gap):
    """Folds, wind, then keep it out of the body."""
    rng = random.Random(p.seed + 17)
    ncol, nrow = len(grid), len(grid[0])
    phases = [rng.uniform(0, 2 * math.pi) for _ in range(3)]
    amps = [1.0, 0.45 * p.fold_random, 0.25 * p.fold_random]
    freqs = [max(1, p.folds), max(1, p.folds) * 2.3, max(1, p.folds) * 0.55]
    depth = p.fold_depth * size
    wa = p.wind_dir
    wind = Vector((math.cos(wa), math.sin(wa), 0.0)) * (p.wind * size)
    out = []
    for i, col in enumerate(grid):
        s = i / max(1, ncol - 1)
        f = sum(a * math.sin(2 * math.pi * fr * s + ph) for a, fr, ph in zip(amps, freqs, phases))
        f /= max(1e-6, sum(amps))
        new = []
        for k, q in enumerate(col):
            v = k / max(1, nrow - 1)
            # sheet normal: away from the body axis (horizontal part)
            nrm = Vector((q.x - axis.x, q.y - axis.y, 0.0))
            nrm = nrm.normalized() if nrm.length > 1e-9 else Vector((0, 0, 1))
            amp = depth * (v ** 0.8)
            r = q + nrm * (amp * f) + wind * (v * v)
            new.append(_push_out(bvh, r, gap * 0.6) if k > 0 else r)
        out.append(new)
    return out


def solid_mesh(grid, thickness, axis):
    """Closed sheet: the grid, a copy pushed toward the body by thickness, walls round the border."""
    bm = bmesh.new()
    ncol, nrow = len(grid), len(grid[0])
    top = [[bm.verts.new(q) for q in col] for col in grid]
    bot = []
    for i, col in enumerate(grid):
        row = []
        for k, q in enumerate(col):
            a = grid[min(i + 1, ncol - 1)][k] - grid[max(i - 1, 0)][k]
            b = col[min(k + 1, nrow - 1)] - col[max(k - 1, 0)]
            n = a.cross(b)
            if n.length < 1e-12:
                n = Vector((q.x - axis.x, q.y - axis.y, 0.0))
            n.normalize()
            if n.dot(Vector((q.x - axis.x, q.y - axis.y, 0.0))) < 0:
                n = -n
            row.append(bm.verts.new(q - n * thickness))
        bot.append(row)
    for i in range(ncol - 1):
        for k in range(nrow - 1):
            bm.faces.new((top[i][k], top[i + 1][k], top[i + 1][k + 1], top[i][k + 1]))
            bm.faces.new((bot[i][k + 1], bot[i + 1][k + 1], bot[i + 1][k], bot[i][k]))
    border = [(i, 0) for i in range(ncol)] + [(ncol - 1, k) for k in range(1, nrow)] + \
             [(i, nrow - 1) for i in range(ncol - 2, -1, -1)] + [(0, k) for k in range(nrow - 2, 0, -1)]
    for j in range(len(border)):
        a, b = border[j], border[(j + 1) % len(border)]
        bm.faces.new((top[a[0]][a[1]], bot[a[0]][a[1]], bot[b[0]][b[1]], top[b[0]][b[1]]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        f.smooth = True
    return bm


def build(context, src, p, target):
    bvh, lo, hi = _body(context, target)
    collar, lengths, axis, size = _collar(context, src, p, bvh, lo, hi)
    gap = p.gap if p.gap > 0 else size * 0.012
    rows = max(4, p.rows)
    # 0.24.29 Straight: the sides drop plumb instead of spreading out diagonally
    grid = drape(bvh, axis, collar, lengths, rows, gap, p.flare * (1.0 - p.straight))
    grid = shape_sheet(grid, axis, p, size, bvh, gap)
    thick = p.thickness if p.thickness > 0 else size * 0.006
    return solid_mesh(grid, thick, axis)


# -----------------------------------------------------------------------------
# Live object
# -----------------------------------------------------------------------------


def source(ob):
    if ob is None:
        return None
    try:
        raw = ob.get(SRC_KEY)
        return json.loads(raw) if raw else None
    except (TypeError, ValueError, ReferenceError):
        return None


def rebuild(context, ob):
    src = source(ob)
    if src is None:
        raise cg.CutError('This cape was applied (no outline kept).')
    target = bpy.data.objects.get(src.get('target', ''))
    if target is None or target.type != 'MESH':
        raise cg.CutError('The body the cape was drawn on is gone.')
    bm = build(context, src, ob.mch_cape, target)
    try:
        bmesh.ops.transform(bm, matrix=ob.matrix_world.inverted_safe(), verts=bm.verts[:])
        bm.to_mesh(ob.data)
    finally:
        bm.free()
    ob.data.update()


_BUSY = [False]


def _update(self, context):
    if _BUSY[0]:
        return
    ob = self.id_data
    if not isinstance(ob, bpy.types.Object) or not self.live:
        return
    try:
        rebuild(context, ob)
        self.last_error = ''
    except (cg.CutError, ValueError, RuntimeError) as ex:
        self.last_error = str(ex)
    st = getattr(getattr(context, 'scene', None), 'mch_cape', None)
    if st is not None:                       # the next cape starts like this one
        _BUSY[0] = True
        try:
            for k in LIVE_KEYS + ('style',):
                if getattr(st, k) != getattr(self, k):
                    setattr(st, k, getattr(self, k))
        except (AttributeError, TypeError):
            pass
        finally:
            _BUSY[0] = False


def _style_update(self, context):
    if _BUSY[0]:
        return
    vals = STYLES.get(self.style)
    if not vals:
        return
    _BUSY[0] = True
    try:
        for k, v in vals.items():
            setattr(self, k, v)
    finally:
        _BUSY[0] = False
    _update(self, context)


class MCH_PG_Cape(bpy.types.PropertyGroup):
    """Scene.mch_cape = settings for the next cape; Object.mch_cape = live cape."""
    style: EnumProperty(name='Style', items=STYLE_ITEMS, default='CLOAK', update=_style_update,
                        description='Fills in the sliders (Length, Hem, Flare, Wrap, folds, Tatter)')
    shape: EnumProperty(name='Shape', items=[
        ('AUTO', 'Auto', 'A short wide drawing = Preset, a tall one = Outline'),
        ('OUTLINE', 'Outline', 'The drawn silhouette is the cape (its bottom = the hem)'),
        ('PRESET', 'Preset', 'Only the top edge counts; Length and Hem make the rest')], default='AUTO', update=_update)
    length: FloatProperty(name='Length', default=0.9, min=0.05, max=1.5, update=_update,
                          description='Preset: how far down it hangs (1 = from the collar to the bottom of the body)')
    hem: EnumProperty(name='Hem', items=HEM_ITEMS, default='ROUND', update=_update)
    straight: FloatProperty(name='Straight', default=0.6, min=0.0, max=1.0, update=_update,
                            description='How straight it falls: 1 = the sides drop plumb (no spreading out), '
                                        '0 = it spreads out as much as Flare says')
    flare: FloatProperty(name='Flare', default=0.22, min=0.0, max=1.5, update=_update,
                         description='How much it spreads out as it falls')
    wrap: FloatProperty(name='Wrap', default=60.0, min=0.0, max=170.0, update=_update,
                        description='Degrees the collar carries on round the body on each side (0 = as drawn)')
    folds: IntProperty(name='Folds', default=9, min=0, max=40, update=_update)
    fold_depth: FloatProperty(name='Fold Depth', default=0.035, min=0.0, max=0.3, update=_update,
                              description='How deep the folds are (part of the body size), growing toward the hem')
    fold_random: FloatProperty(name='Fold Random', default=0.6, min=0.0, max=1.0, update=_update)
    wind: FloatProperty(name='Wind', default=0.0, min=-0.6, max=0.6, update=_update,
                        description='The lower part swings sideways')
    wind_dir: FloatProperty(name='Wind Direction', default=0.0, subtype='ANGLE', update=_update)
    tatter: FloatProperty(name='Tatter', default=0.0, min=0.0, max=0.9, update=_update,
                          description='Ragged, torn hem')
    seed: IntProperty(name='Seed', default=1, min=0, update=_update)
    thickness: FloatProperty(name='Thickness', default=0.0, min=0.0, soft_max=0.1, precision=4, unit='LENGTH',
                             update=_update, description='Cloth thickness (0 = Auto)')
    gap: FloatProperty(name='Gap', default=0.0, min=0.0, soft_max=0.2, precision=4, unit='LENGTH', update=_update,
                       description='Distance from the body (0 = Auto)')
    columns: IntProperty(name='Columns', default=48, min=8, max=200, update=_update)
    rows: IntProperty(name='Rows', default=36, min=6, max=200, update=_update)
    live: BoolProperty(default=False, options={'HIDDEN'})
    last_error: StringProperty(default='', options={'HIDDEN', 'SKIP_SAVE'})


def pick_body(context, projector, groups):
    """The mesh under the drawing; capes, hair and other live generated parts (and armour parts / plates) are
    looked through."""
    from . import armor_plate as ap
    from . import creature_hair
    outer = groups[0][0]
    probes = [(sum(q[0] for q in outer) / len(outer), sum(q[1] for q in outer) / len(outer))] + list(outer[::3])
    probes += creature_hair.root_points(outer, 40, 0)     # inside too (an outline round two legs misses at the edge)
    dg = context.evaluated_depsgraph_get()
    counts = {}
    for xy in probes:
        o, d = projector.ray(xy)
        o, d = Vector(o), Vector(d).normalized()
        for _k in range(256):                # through hair / capes in front (many surfaces)
            hit, loc, _n, _i, hob, _m = context.scene.ray_cast(dg, o, d)
            if not hit or hob is None:
                break
            real = bpy.data.objects.get(hob.name)
            generated = any(k.startswith('mch_') and k.endswith('_src') for k in real.keys()) if real else True
            if real is not None and real.type == 'MESH' and not generated and not ap.is_plate_or_part(real) \
                    and not any(c.name.startswith(COLLECTION) for c in real.users_collection):
                counts[real.name] = counts.get(real.name, 0) + 1
                break
            o = loc + d * 1e-4
    if not counts:
        return None
    return bpy.data.objects[max(counts, key=counts.get)]


def perform(context, loops, projector):
    """Outline drawn on a body -> a live cape.  Returns a report; raises cg.CutError."""
    from . import armor_plate as ap
    from . import face_extract as fx
    scene = context.scene
    st = scene.mch_cape
    groups = cg.prepare_loops(loops)
    target = pick_body(context, projector, groups)
    if target is None:
        raise cg.CutError('Draw the cape over a body (start at the shoulders).')
    frozen = ap.freeze_projector(projector)
    if frozen is None:
        raise cg.CutError('This view cannot be saved for the cape.')
    me = bpy.data.meshes.new(target.name + '_Cape')
    ob = bpy.data.objects.new(me.name, me)
    fx._parts_collection(context, COLLECTION).objects.link(ob)
    for mat in target.data.materials:
        me.materials.append(mat)
    ob[SRC_KEY] = json.dumps({'loops': [[[float(x), float(y)] for x, y in lp] for lp in loops], 'proj': frozen,
                              'target': target.name})
    p = ob.mch_cape
    _BUSY[0] = True
    try:
        for k in LIVE_KEYS + ('style',):
            setattr(p, k, getattr(st, k))
    finally:
        _BUSY[0] = False
    try:
        rebuild(context, ob)
    except Exception:
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
    return f'Cape "{ob.name}" on {target.name} ({dict((s[0], s[1]) for s in STYLE_ITEMS)[p.style]}, ' \
           f'{len(me.polygons)} faces)'


def live_cape(context):
    ob = getattr(context, 'active_object', None)
    if ob is not None and getattr(ob, 'mch_cape', None) is not None and ob.mch_cape.live and source(ob):
        return ob
    return None


def apply(ob):
    ob.mch_cape.live = False
    if SRC_KEY in ob:
        del ob[SRC_KEY]


class MCH_OT_cape_apply(bpy.types.Operator):
    bl_idname = 'mch.cape_apply'
    bl_label = 'Apply Cape'
    bl_description = 'The cape becomes a plain mesh (the sliders stop rebuilding it)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return live_cape(context) is not None

    def execute(self, context):
        apply(live_cape(context))
        return {'FINISHED'}


def draw(layout, context):
    ob = live_cape(context)
    p = ob.mch_cape if ob is not None else context.scene.mch_cape
    box = layout.box()
    if ob is not None:
        box.label(text='LIVE Cape: ' + ob.name, icon='MOD_CLOTH')
        if p.last_error:
            box.label(text=p.last_error, icon='ERROR')
    else:
        box.label(text='Cape: settings for the next one', icon='MOD_CLOTH')
    box.row(align=True).prop(p, 'style', expand=True)
    box.row(align=True).prop(p, 'shape', expand=True)
    col = box.column(align=True)
    col.prop(p, 'length', slider=True)
    col.row(align=True).prop(p, 'hem', expand=True)
    col.prop(p, 'flare', slider=True)
    col.prop(p, 'straight', slider=True)
    col.prop(p, 'wrap', slider=True)
    col = box.column(align=True)
    col.prop(p, 'folds')
    col.prop(p, 'fold_depth', slider=True)
    col.prop(p, 'fold_random', slider=True)
    col = box.column(align=True)
    col.prop(p, 'wind', slider=True)
    if abs(p.wind) > 1e-4:
        col.prop(p, 'wind_dir')
    col.prop(p, 'tatter', slider=True)
    col.prop(p, 'seed')
    col = box.column(align=True)
    col.prop(p, 'thickness')
    col.prop(p, 'gap')
    r = col.row(align=True)
    r.prop(p, 'columns')
    r.prop(p, 'rows')
    if ob is not None:
        box.operator('mch.cape_apply', icon='CHECKMARK')
    col = layout.column(align=True)
    col.scale_y = 0.8
    for line in ('Draw on the body from the side the cape hangs on', 'The top of what you draw = the collar',
                 'Short wide drawing = Preset, tall = your outline', 'Apply: plain mesh'):
        col.label(text=line)


CLASSES = (MCH_PG_Cape, MCH_OT_cape_apply)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_cape = bpy.props.PointerProperty(type=MCH_PG_Cape)
    bpy.types.Object.mch_cape = bpy.props.PointerProperty(type=MCH_PG_Cape)


def unregister():
    for n, t in (('mch_cape', bpy.types.Object), ('mch_cape', bpy.types.Scene)):
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
