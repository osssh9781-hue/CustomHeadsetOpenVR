"""0.24.20 Scale Brush: lasso an area on a mesh, it fills with flat-bottomed scales (pebbles / plates) packed close
together without touching - like crocodile or tortoise skin.

Every scale is a Creature Plate lump (Dome or Pillow) made from one of twelve pebble outlines traced from the
user's sketch.  The bottoms sit in the surface; nothing lifts off.

    Presets       1 .. 12, the ticked ones are mixed at random
    Size          about how big a scale is; Size Random varies it, the gaps are filled with smaller ones
    Rotate Random a random turn per scale (180 = any way round)
    Gap           space between neighbours (x Size); small = close but not touching
    Profile       Dome (rounded) or Pillow (flat top, round edge); Height, Edge Round, Resolution (Low/Mid/High)

Everything stays live until Apply.  ``pack`` is pure and tested headless.
"""
from __future__ import annotations

import json
import math
import random
import types

import bpy
from bpy.props import BoolProperty, BoolVectorProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from mathutils import Matrix, Vector

from . import core_geometry as cg

SRC_KEY = 'mch_sbrush_src'
COLLECTION = 'Scale Brush'
COUNT = 12
LIVE_KEYS = ('use', 'size', 'size_random', 'rotate_random', 'gap', 'profile', 'height', 'edge_round', 'quality',
             'seed')
_CACHE = {}
# Resolution: (point spacing, rows of points inside the rim, outline density) - same steps as Creature Scales
QUALITY = {'LOW': (6, (0.3, 0.85), 1.0), 'MID': (8, (0.2, 0.55, 0.9), 0.75),
           'HIGH': (12, (0.12, 0.3, 0.55, 0.85), 0.5)}

# the user's twelve pebble outlines (px, y down), two sheets of six
SKETCH = (
    [(390, 250), (440, 310), (465, 365), (430, 405), (385, 440), (330, 460), (270, 465), (240, 430), (235, 360),
     (270, 320), (330, 280)],
    [(560, 350), (605, 375), (590, 420), (545, 470), (510, 490), (485, 465), (490, 420), (520, 370)],
    [(580, 465), (660, 460), (740, 495), (770, 520), (775, 590), (740, 630), (680, 645), (600, 645), (575, 560)],
    [(430, 485), (460, 560), (495, 630), (490, 690), (440, 750), (385, 810), (320, 785), (275, 750), (245, 700),
     (240, 620), (270, 595), (330, 560), (390, 515)],
    [(590, 720), (625, 780), (630, 880), (600, 940), (560, 965), (500, 965), (440, 940), (415, 850), (470, 800),
     (530, 750)],
    [(270, 890), (320, 895), (410, 930), (410, 1000), (380, 1070), (320, 1110), (255, 1115), (240, 1050),
     (235, 950)],
    [(440, 320), (480, 320), (540, 350), (590, 360), (650, 345), (650, 390), (625, 445), (545, 445), (530, 470),
     (480, 490), (430, 470), (400, 450), (400, 410)],
    [(600, 480), (670, 475), (690, 520), (675, 555), (630, 600), (600, 595), (585, 570), (560, 590), (555, 540)],
    [(370, 560), (420, 570), (480, 610), (505, 660), (500, 730), (470, 800), (440, 845), (370, 870), (310, 850),
     (250, 815), (250, 785), (210, 740), (250, 670), (300, 590)],
    [(700, 600), (765, 600), (780, 680), (790, 720), (820, 730), (820, 800), (800, 840), (745, 840), (700, 800),
     (650, 815), (615, 780), (620, 730), (660, 670)],
    [(600, 905), (640, 915), (680, 945), (740, 965), (780, 1000), (775, 1060), (760, 1110), (770, 1190),
     (780, 1250), (740, 1300), (690, 1340), (580, 1335), (550, 1300), (510, 1270), (515, 1150), (505, 1120),
     (465, 1100), (455, 1040), (495, 1000), (540, 955)],
    [(310, 1100), (355, 1140), (380, 1180), (370, 1210), (335, 1240), (290, 1215), (250, 1185), (255, 1150)],
)


def _normalized(loop):
    """Centred on its middle, y up, longest side 1, counter-clockwise."""
    xs = [q[0] for q in loop]
    ys = [q[1] for q in loop]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    ext = max(max(xs) - min(xs), max(ys) - min(ys))
    out = [((x - cx) / ext, (cy - y) / ext) for x, y in loop]
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(out, out[1:] + out[:1]))
    return out if area > 0 else out[::-1]


PEBBLES = tuple(_normalized(lp) for lp in SKETCH)


def _cell(c, others, gap, reach):
    """Half-planes (n, d) with n . x <= d of the Voronoi cell of ``c`` among ``others``, pulled in by gap / 2."""
    planes = []
    for o in others:
        dx, dy = o[0] - c[0], o[1] - c[1]
        ln = math.hypot(dx, dy)
        if ln < 1e-9 or ln > reach:
            continue
        n = (dx / ln, dy / ln)
        planes.append((n, n[0] * (c[0] + o[0]) / 2 + n[1] * (c[1] + o[1]) / 2 - gap / 2))
    return planes


def _clip(poly, planes):
    """Convex polygon cut by half-planes (n . x <= d)."""
    for (nx, ny), d in planes:
        out = []
        for i, a in enumerate(poly):
            b = poly[(i + 1) % len(poly)]
            fa, fb = nx * a[0] + ny * a[1] - d, nx * b[0] + ny * b[1] - d
            if fa <= 0:
                out.append(a)
            if (fa < 0) != (fb < 0) and abs(fa - fb) > 1e-12:
                t = fa / (fa - fb)
                out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        poly = out
        if len(poly) < 3:
            return []
    return poly


def _centroid(poly):
    a = cx = cy = 0.0
    for p0, p1 in zip(poly, poly[1:] + poly[:1]):
        w = p0[0] * p1[1] - p1[0] * p0[1]
        a += w
        cx += (p0[0] + p1[0]) * w
        cy += (p0[1] + p1[1]) * w
    if abs(a) < 1e-12:
        return (sum(q[0] for q in poly) / len(poly), sum(q[1] for q in poly) / len(poly))
    return (cx / (3 * a), cy / (3 * a))


def _fit_scale(c, loop, planes):
    """Largest scale of ``loop`` (around ``c``) that stays inside every half-plane - exact for a convex cell."""
    best = 1e18
    for (nx, ny), d in planes:
        room = d - (nx * c[0] + ny * c[1])
        if room <= 0:
            return 0.0
        for x, y in loop:
            reach = nx * x + ny * y
            if reach > 1e-12:
                best = min(best, room / reach)
    return best


def pack(loops, kinds, size_px, size_random, rotate_random, gap_px, seed):
    """[(outline px, kind, centre, size, angle)]: pebble outlines filling the area of ``loops``, close together but
    never overlapping (at least ``gap_px`` apart) - pure.  The area is split into Voronoi cells around jittered
    points about ``size_px`` apart; every cell gets a preset, turned (within Rotate Random) and sized to fill it."""
    from . import base_mesh as bmm
    if not loops or not kinds or size_px <= 0:
        return []
    rnd = random.Random(seed)
    xs = [q[0] for lp in loops for q in lp]
    ys = [q[1] for lp in loops for q in lp]
    step = size_px * 0.9
    jit = step * (0.15 + 0.4 * size_random)
    seeds = []
    j = 0
    y = min(ys) - step
    while y <= max(ys) + step:
        x = min(xs) - step + (step / 2 if j % 2 else 0.0)
        while x <= max(xs) + step:
            seeds.append((x + rnd.uniform(-jit, jit), y + rnd.uniform(-jit, jit)))
            x += step
        y += step * 0.866
        j += 1
    cell_sz = step * 2.0

    def cells(pts):
        grid = {}
        for q in pts:
            grid.setdefault((int(q[0] // cell_sz), int(q[1] // cell_sz)), []).append(q)
        res = []
        for c in pts:
            gx, gy = int(c[0] // cell_sz), int(c[1] // cell_sz)
            others = [o for i in (gx - 1, gx, gx + 1) for k in (gy - 1, gy, gy + 1) for o in grid.get((i, k), ())]
            box = [(c[0] - cell_sz, c[1] - cell_sz), (c[0] + cell_sz, c[1] - cell_sz),
                   (c[0] + cell_sz, c[1] + cell_sz), (c[0] - cell_sz, c[1] + cell_sz)]
            res.append((c, others, _clip(box, _cell(c, others, 0.0, step * 2.5))))
        return res

    for _k in range(2):                     # Lloyd: move every point to the middle of its cell (rounder cells)
        seeds = [_centroid(poly) if len(poly) >= 3 else c for c, _o, poly in cells(seeds)]
    inside = bmm._inside_many(seeds, loops)
    out = []
    tries = 6 if rotate_random > 1e-4 else 1
    for (c, others, poly), ok in zip(cells(seeds), inside):
        if not ok or len(poly) < 3:
            continue
        planes = _cell(c, others, gap_px, step * 2.5)
        c = _centroid(_clip(poly, planes) or poly)
        picks = [kinds[rnd.randrange(len(kinds))] for _k in range(3)]     # the best of three random presets
        base = rnd.uniform(-math.pi, math.pi) if rotate_random >= math.pi - 1e-3 else 0.0
        r0 = step * 0.12
        spots = [c] + [(c[0] + r0 * math.cos(a), c[1] + r0 * math.sin(a)) for a in (0.0, 1.57, 3.14, 4.71)]
        best = None
        for kind in picks:
            for t in range(tries):
                ang = base + rotate_random * (rnd.random() * 2.0 - 1.0)
                ca, sa = math.cos(ang), math.sin(ang)
                unit = [(x * ca - y * sa, x * sa + y * ca) for x, y in PEBBLES[kind]]
                for q in spots:
                    sc = min(_fit_scale(q, unit, planes), size_px * 1.6)
                    if best is None or sc > best[0]:
                        best = (sc, ang, unit, kind, q)
        sc, ang, unit, kind, c = best
        for _k in range(4):                     # keep inside the drawn area (it may be concave)
            if sc < size_px * 0.2:
                break
            outline = [(c[0] + x * sc, c[1] + y * sc) for x, y in unit]
            if all(bmm._inside_many(outline, loops)):
                out.append((outline, kind, c, sc, ang))
                break
            sc *= 0.75
    return out


def _update(self, context):
    ob = self.id_data
    if not isinstance(ob, bpy.types.Object) or not self.live:
        return
    try:
        rebuild(context, ob)
        self.last_error = ''
    except (cg.CutError, ValueError, RuntimeError) as ex:
        self.last_error = str(ex)
    st = getattr(getattr(context, 'scene', None), 'mch_sbrush', None)
    if st is not None:
        for k in LIVE_KEYS:
            try:
                a, b = getattr(st, k), getattr(self, k)
                if k == 'use':
                    a, b = tuple(a), tuple(b)
                if a != b:
                    setattr(st, k, b)
            except (AttributeError, TypeError):
                pass


def _p(prop, **kw):
    kw.setdefault('update', _update)
    return prop(**kw)


class MCH_PG_ScaleBrush(bpy.types.PropertyGroup):
    use: _p(BoolVectorProperty, name='Presets', size=COUNT, default=(True,) * COUNT,
            description='Pebble shapes to mix')
    size: _p(FloatProperty, name='Size', default=0.25, min=0.001, soft_max=5.0, precision=3, unit='LENGTH',
             description='About how big a scale is')
    size_random: _p(FloatProperty, name='Size Random', default=0.3, min=0.0, max=0.9, subtype='FACTOR')
    rotate_random: _p(FloatProperty, name='Rotate Random', default=math.radians(180), min=0.0,
                      max=math.radians(180), subtype='ANGLE')
    gap: _p(FloatProperty, name='Gap', default=0.05, min=0.0, soft_max=0.5,
            description='Space between neighbours (x Size); small = close but not touching')
    profile: _p(EnumProperty, name='Profile', default='PUFF',
                items=(('PUFF', 'Dome', 'Rounded lumps'), ('PILLOW', 'Pillow', 'Flat top, round edge')))
    height: _p(FloatProperty, name='Height', default=1.0, min=0.05, soft_max=4.0, description='1 = Auto')
    edge_round: _p(FloatProperty, name='Edge Round', default=0.4, min=0.0, max=1.0)
    quality: _p(EnumProperty, name='Resolution', default='LOW',
                items=(('LOW', 'Low', 'Light'), ('MID', 'Mid', ''), ('HIGH', 'High', 'Smooth')))
    seed: _p(IntProperty, name='Seed', default=1, min=0)
    live: BoolProperty(default=False, options={'HIDDEN'})
    last_error: StringProperty(default='', options={'HIDDEN', 'SKIP_SAVE'})


def source(ob):
    if ob is None:
        return None
    try:
        raw = ob.get(SRC_KEY)
        return json.loads(raw) if raw else None
    except (TypeError, ValueError, ReferenceError):
        return None


def build(context, ob):
    from . import armor_plate as ap
    from . import base_mesh as bmm
    from . import creature_plate as cpl
    from . import creature_spike as csp
    src = source(ob)
    if src is None:
        raise cg.CutError('This Scale Brush area was applied.')
    p = ob.mch_sbrush
    kinds = [i for i in range(COUNT) if p.use[i]]
    if not kinds:
        raise cg.CutError('Tick at least one preset.')
    target = bpy.data.objects.get(src.get('target', ''))
    if target is None or target.type != 'MESH':
        raise cg.CutError('The mesh the scales were drawn on is gone.')
    projector = ap.thaw_projector(src['proj'])
    loops = [[tuple(q) for q in lp] for lp in src['loops']]
    hit = _CACHE.get(ob.name)
    if hit is None or hit[0] != src.get('stamp'):
        bvh, wpp, _d = csp.area_frame(context, target, projector, loops, loops[0][0])
        hit = (src.get('stamp'), wpp, bvh)
        _CACHE[ob.name] = hit
    wpp, bvh = hit[1], hit[2]
    size_px = p.size / max(wpp, 1e-9)
    key = (tuple(kinds), round(size_px, 4), round(p.size_random, 4), round(p.rotate_random, 4), round(p.gap, 4),
           p.seed)
    if len(hit) > 3 and hit[3] == key:
        where = hit[4]                                 # only the look changed (height, profile, resolution)
    else:
        where = pack(loops, kinds, size_px, p.size_random, p.rotate_random, p.gap * size_px, p.seed)
        _CACHE[ob.name] = hit[:3] + (key, where)
    res, rings, rim = QUALITY[p.quality]
    field_p = types.SimpleNamespace(profile=p.profile, resolution=res, outline_smooth=0.5, edge_round=p.edge_round,
                                    puff=1.0, rings=rings, rim=rim)
    plate_p = types.SimpleNamespace(profile=p.profile, direction=0.0, edge_thickness=0.0, sink=0.0, tip_lift=0.0)
    ratio = 1.0 if p.profile == 'PILLOW' else cpl.AUTO_RATIO
    fields = {}                     # one unit field per preset: every pebble of it is that, turned and sized
    verts, faces = [], []
    for _outline, kind, c, sz, ang in where:
        if kind not in fields:
            fields[kind] = bmm.profile_field(list(PEBBLES[kind]), [], field_p)
        _b, upts, tris, nb, shape, unat, _sp = fields[kind]
        ca, sa = math.cos(ang), math.sin(ang)
        pts = [(c[0] + (x * ca - y * sa) * sz, c[1] + (x * sa + y * ca) * sz) for x, y in upts]
        natural_px = unat * sz
        try:
            cos, nrms, _miss = ap.project_patch(pts, projector, bvh)
        except cg.CutError:
            continue                                   # off the mesh: skip it
        nrms = cpl._smooth_normals(nrms, tris)
        peak = natural_px * wpp * ratio * p.height
        part = dict(pts=pts, tris=tris, nb=nb, cos=cos, nrms=nrms, shape=shape, start=pts[0])
        bm = cpl.build_mesh([part], plate_p, peak, -1.0)
        try:
            off = len(verts)
            verts += [v.co.copy() for v in bm.verts]
            bm.verts.index_update()
            faces += [tuple(off + v.index for v in f.verts) for f in bm.faces]
        finally:
            bm.free()
    if not verts:
        raise cg.CutError('No scale fits the area (draw it bigger, or lower Size).')
    return verts, faces, len(where)


def rebuild(context, ob):
    verts, faces, n = build(context, ob)
    inv = ob.matrix_world.inverted_safe()
    me = ob.data
    me.clear_geometry()
    me.from_pydata([tuple(inv @ v) for v in verts], [], faces)
    me.update()
    from . import edge_memory as _em; _em.mark_generated(me)   # 0.24.95 Edge Memory: the part's own lines
    for poly in me.polygons:
        poly.use_smooth = True
    try:
        me.set_sharp_from_angle(angle=math.radians(60))
    except (AttributeError, TypeError, RuntimeError):
        pass
    me.update()
    return n


def perform(context, loops, projector):
    """Closed lasso -> a live Scale Brush area.  Returns a report; raises cg.CutError."""
    from . import armor_plate as ap
    from . import belt_maker as bmk
    from . import face_extract as fx
    loops = [[tuple(q) for q in lp] for lp in loops if len(lp) >= 3]
    if not loops:
        raise cg.CutError('Scale Brush: lasso an area (3+ points).')
    target = bmk.pick_target(context, projector, [q for lp in loops for q in lp])
    if target is None:
        raise cg.CutError('Scale Brush: draw the area over a mesh.')
    frozen = ap.freeze_projector(projector)
    if frozen is None:
        raise cg.CutError('This view cannot be saved for the scales.')
    st = context.scene.mch_sbrush
    me = bpy.data.meshes.new(target.name + '_ScaleBrush')
    ob = bpy.data.objects.new(me.name, me)
    fx._parts_collection(context, COLLECTION).objects.link(ob)
    for mat in target.data.materials:
        me.materials.append(mat)
    ob[SRC_KEY] = json.dumps({'loops': [[[float(x), float(y)] for x, y in lp] for lp in loops], 'proj': frozen,
                              'target': target.name, 'stamp': id(ob) % 100000})
    p = ob.mch_sbrush
    for k in LIVE_KEYS:
        v = getattr(st, k)
        setattr(p, k, tuple(v) if k == 'use' else v)
    try:
        n = rebuild(context, ob)
    except Exception:
        _CACHE.pop(ob.name, None)
        bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.meshes.remove(me)
        raise
    cen = sum((v.co for v in me.vertices), Vector()) / max(1, len(me.vertices))
    me.transform(Matrix.Translation(-cen))
    ob.matrix_world = Matrix.Translation(cen)
    p.live = True
    st.seed += 1
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    return f'Scale Brush "{ob.name}" on {target.name} ({n} scales)'


def live_brush(context):
    ob = getattr(context, 'active_object', None)
    if ob is not None and getattr(ob, 'mch_sbrush', None) is not None and ob.mch_sbrush.live and source(ob):
        return ob
    return None


class MCH_OT_sbrush_apply(bpy.types.Operator):
    bl_idname = 'mch.sbrush_apply'
    bl_label = 'Apply Scale Brush'
    bl_description = 'The scales become a plain mesh (the sliders stop rebuilding them)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return live_brush(context) is not None

    def execute(self, context):
        ob = live_brush(context)
        ob.mch_sbrush.live = False
        del ob[SRC_KEY]
        _CACHE.pop(ob.name, None)
        self.report({'INFO'}, f'{ob.name}: applied')
        return {'FINISHED'}


def draw(layout, context):
    ob = live_brush(context)
    p = ob.mch_sbrush if ob is not None else context.scene.mch_sbrush
    if ob is not None:
        box = layout.box()
        box.label(text='LIVE: ' + ob.name, icon='MESH_ICOSPHERE')
        if p.last_error:
            box.label(text=p.last_error, icon='ERROR')
        target = box
    else:
        layout.label(text='Settings for the next area', icon='MESH_ICOSPHERE')
        target = layout
    target.label(text='Presets (ticked ones are mixed at random):')
    for start in (0, 6):
        row = target.row(align=True)
        for i in range(start, start + 6):
            row.prop(p, 'use', index=i, text=str(i + 1), toggle=True)
    col = target.column(align=True)
    col.prop(p, 'size')
    col.prop(p, 'size_random', slider=True)
    col.prop(p, 'rotate_random')
    col.prop(p, 'gap')
    target.row().prop(p, 'profile', expand=True)
    col = target.column(align=True)
    col.prop(p, 'height')
    col.prop(p, 'edge_round', slider=True)
    target.row().prop(p, 'quality', expand=True)
    target.prop(p, 'seed')
    if ob is not None:
        target.operator('mch.sbrush_apply', icon='CHECKMARK')
    col = layout.column(align=True)
    col.scale_y = 0.8
    for line in ('Lasso an area on a mesh: it fills with scales packed', 'close together; Seed: another mix',
                 'Apply: plain mesh'):
        col.label(text=line)


CLASSES = (MCH_PG_ScaleBrush, MCH_OT_sbrush_apply)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_sbrush = bpy.props.PointerProperty(type=MCH_PG_ScaleBrush)
    bpy.types.Object.mch_sbrush = bpy.props.PointerProperty(type=MCH_PG_ScaleBrush)


def unregister():
    for n, t in (('mch_sbrush', bpy.types.Object), ('mch_sbrush', bpy.types.Scene)):
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
