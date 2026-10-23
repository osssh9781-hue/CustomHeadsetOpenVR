"""0.24.31 Scarf: draw round a neck (looking at the front) -> a live scarf: thick cloth wraps round the neck plus
hanging ends.

The hits inside the drawing give the neck centre and height; at that height rays from outside toward the centre
find the neck surface all round, so the wraps follow the real neck shape.  Each wrap is a closed tube (an oval
section: Height x Thickness) a little outside the one under it, bunched by noise.  Ends: none, one tail, two tails
or a Front Drape (the shemagh triangle hanging over the chest, draped like the cape).  Tails are flat ribbons that
fall along the body (pushed out of it), with Taper and a Fringe at the bottom.

Styles: Wrap (two wraps, two tails), Cowl (one tall loose wrap), Shemagh (wraps + front drape), Long Tail.
``ring_section`` and ``tail_widths`` are pure.
"""
from __future__ import annotations

import json
import math
import random

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from mathutils import Matrix, Vector, noise

from . import core_geometry as cg

SRC_KEY = 'mch_scarf_src'
COLLECTION = 'Scarves'
STYLE_ITEMS = [
    ('WRAP', 'Wrap', 'Two wraps round the neck, two tails hanging in front'),
    ('COWL', 'Cowl', 'One tall, loose wrap, no ends'),
    ('SHEMAGH', 'Shemagh', 'Wraps and a triangle hanging over the chest'),
    ('LONG', 'Long Tail', 'Wraps and one long tail thrown over the shoulder'),
]
ENDS_ITEMS = [
    ('NONE', 'None', 'Only the wraps'),
    ('ONE', 'One Tail', 'One tail'),
    ('TWO', 'Two Tails', 'Two tails, one a little longer'),
    ('DRAPE', 'Front Drape', 'A triangle hanging over the chest (shemagh)'),
]
STYLES = {
    'WRAP': dict(wraps=2, height=1.0, thick=0.55, loose=0.15, bunch=0.5, flare=0.0, ends='TWO', tail_len=4.0,
                 tail_w=1.1, taper=0.15, fringe=0.0, tail_angle=25.0),
    'COWL': dict(wraps=1, height=1.8, thick=0.8, loose=0.5, bunch=0.9, flare=0.6, ends='NONE', tail_len=3.0,
                 tail_w=1.0, taper=0.0, fringe=0.0, tail_angle=25.0),
    'SHEMAGH': dict(wraps=2, height=0.9, thick=0.45, loose=0.2, bunch=0.7, flare=0.2, ends='DRAPE', tail_len=3.0,
                    tail_w=2.2, taper=0.0, fringe=0.3, tail_angle=0.0),
    'LONG': dict(wraps=2, height=1.0, thick=0.55, loose=0.15, bunch=0.5, flare=0.0, ends='ONE', tail_len=6.0,
                 tail_w=1.2, taper=0.1, fringe=0.4, tail_angle=40.0),
}
LIVE_KEYS = ('wraps', 'height', 'thick', 'loose', 'bunch', 'flare', 'ends', 'tail_len', 'tail_w', 'taper', 'fringe',
             'tail_angle', 'turn', 'seed', 'segments')
SECTION = 10        # points round a tube section


def ring_section(n, half_w, half_d, squash=0.0):
    """Oval section points (u = up, v = out) - a flattened ellipse, ``squash`` flattens the inner side."""
    out = []
    for k in range(n):
        a = 2 * math.pi * k / n
        u, v = math.sin(a) * half_w, math.cos(a) * half_d
        if v < 0:
            v *= 1.0 - squash
        out.append((u, v))
    return out


def tail_widths(rows, taper):
    """Width factor down a tail (1 at the top, 1 - taper at the bottom)."""
    return [1.0 - taper * (k / max(1, rows - 1)) for k in range(rows)]


def locate(context, projector, outline, bvh):
    """Neck centre (on the axis), radius, height of the drawing and the front direction."""
    from . import creature_hair
    pts = creature_hair.root_points(outline, 50, 5) + list(outline[::2])
    hits = []
    for xy in pts:
        o, d = projector.ray(xy)
        o, d = Vector(o), Vector(d).normalized()
        loc, _n, _i, _dist = bvh.ray_cast(o, d)
        if loc is None:
            continue
        hits.append(loc)
        o2 = loc + d * 1e-3
        for _k in range(8):
            loc2, _n2, _i2, _d2 = bvh.ray_cast(o2, d)
            if loc2 is None:
                break
            if (loc2 - loc).length > 1e-3:
                hits.append(loc2)
                break
            o2 = loc2 + d * 1e-3
    if len(hits) < 4:
        raise cg.CutError('Draw round the neck (the scarf wraps round it).')
    c = sum(hits, Vector()) / len(hits)
    zs = sorted(h.z for h in hits)
    span = zs[int(len(zs) * 0.9)] - zs[int(len(zs) * 0.1)]
    r = sum(Vector((h.x - c.x, h.y - c.y)).length for h in hits) / len(hits)
    front = -Vector(projector.view_dir)
    front.z = 0.0
    if front.length < 1e-6:
        front = Vector((0.0, -1.0, 0.0))
    return c, max(r, 1e-4), max(span, r * 0.3), front.normalized()


def _neck_ring(bvh, c, r, z, n, front):
    """Neck surface distance from the axis at height z, n angles (0 = front)."""
    side = Vector((-front.y, front.x, 0.0))
    radii = []
    for i in range(n):
        a = 2 * math.pi * i / n
        d = front * math.cos(a) + side * math.sin(a)
        o = Vector((c.x, c.y, z)) + d * (r * 4.0)
        loc, _n, _i, _dd = bvh.ray_cast(o, -d, r * 4.0)
        rr = (Vector((loc.x - c.x, loc.y - c.y)).length if loc is not None else r)
        radii.append(min(max(rr, r * 0.3), r * 2.2))
    # smooth (a hair / collar bump should not dent the scarf)
    for _p in range(2):
        radii = [(radii[i - 1] + 2 * radii[i] + radii[(i + 1) % n]) / 4 for i in range(n)]
    return radii


def _tube(bm, rings, closed):
    """Faces between consecutive section rings; ``closed`` joins the last to the first, else both ends capped."""
    vs = [[bm.verts.new(q) for q in ring] for ring in rings]
    m = len(rings[0])
    count = len(vs) if closed else len(vs) - 1
    for k in range(count):
        a, b = vs[k], vs[(k + 1) % len(vs)]
        for j in range(m):
            jj = (j + 1) % m
            bm.faces.new((a[j], a[jj], b[jj], b[j]))
    if not closed:
        bm.faces.new(list(reversed(vs[0])))
        bm.faces.new(vs[-1])


def _frame_ring(centre, up, out, section):
    return [centre + up * u + out * v for u, v in section]


def build(context, src, p, target):
    from . import armor_plate as ap
    from . import cape_gen
    from . import clothing_gen
    projector = ap.thaw_projector(src['proj'])
    bvh, lo, hi = cape_gen._body(context, target)
    groups = cg.prepare_loops([[tuple(q) for q in lp] for lp in src['loops']])
    if not groups:
        raise cg.CutError('The outline is empty.')
    c, r, span, front = locate(context, projector, groups[0][0], bvh)
    front = Matrix.Rotation(p.turn, 3, 'Z') @ front
    side = Vector((-front.y, front.x, 0.0))
    n = max(16, p.segments)
    half_h = span * 0.5 * p.height
    half_t = r * 0.5 * p.thick
    gap = r * 0.04
    rng = random.Random(p.seed)
    seed = Vector((p.seed * 2.3, p.seed * 4.1, p.seed * 0.7))
    bm = bmesh.new()
    zc = c.z
    wraps = max(1, p.wraps)
    outer = []          # (angle -> centre, out) of the last wrap, for the ends
    for w in range(wraps):
        lift = (w - (wraps - 1) * 0.5) * half_h * 0.7
        tilt = rng.uniform(-0.12, 0.12) * half_h
        phase = rng.uniform(0, 2 * math.pi)
        z = zc + lift
        radii = _neck_ring(bvh, c, r, z, n, front)
        rings = []
        rec = []
        for i in range(n):
            a = 2 * math.pi * i / n
            d = front * math.cos(a) + side * math.sin(a)
            q = Vector((c.x, c.y, z + tilt * math.cos(a + phase)))
            f = noise.noise(Vector((math.cos(a), math.sin(a), w * 1.7)) * 1.8 + seed)
            bunch = 1.0 + p.bunch * 0.45 * f
            rad = radii[i] + gap + half_t * (1.0 + 1.6 * w) * (1.0 + p.loose) + r * p.loose * 0.3
            centre = q + d * rad
            up = Vector((0.0, 0.0, 1.0))
            out = d.copy()
            # flare: the lower edge stands further out (a cowl)
            sec = [(u, v + max(0.0, -u) * p.flare * 0.6) for u, v in
                   ring_section(SECTION, half_h * bunch, half_t * (2.0 - bunch), 0.3)]
            rings.append(_frame_ring(centre, up, out, sec))
            rec.append((centre, out, half_h * bunch))
        _tube(bm, rings, True)
        outer = rec
    # ends
    if p.ends in {'ONE', 'TWO'}:
        angs = [math.radians(p.tail_angle)]
        if p.ends == 'TWO':
            angs = [math.radians(p.tail_angle), -math.radians(p.tail_angle) * 0.6]
        for t, a in enumerate(angs):
            L = p.tail_len * r * (1.0 if t == 0 else 0.72)
            _add_tail(bm, bvh, c, outer, n, a, front, side, L, p, r, half_t, gap, seed + Vector((t * 9.0, 0, 0)))
    elif p.ends == 'DRAPE':
        _add_drape(bm, bvh, c, outer, n, front, side, p, r, half_t, gap)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        f.smooth = True
    return bm


def _ring_at(outer, n, a):
    i = int(round((a % (2 * math.pi)) / (2 * math.pi) * n)) % n
    return outer[i]


def _add_tail(bm, bvh, c, outer, n, a, front, side, L, p, r, half_t, gap, seed):
    from . import cape_gen
    centre, out, hh = _ring_at(outer, n, a)
    start = centre - Vector((0.0, 0.0, hh * 0.4)) + out * (half_t * 0.5)
    rows = max(6, int(p.segments * 0.6))
    step = L / rows
    keep = gap + half_t
    path = [start]
    q = start.copy()
    for k in range(rows):
        q = q + Vector((0.0, 0.0, -step)) + out * (step * 0.08)
        sway = noise.noise(Vector((0.0, k * 0.35, 0.0)) + seed) * step * 0.6
        q = q + side * sway
        q = cape_gen._push_out(bvh, q, keep)
        path.append(q.copy())
    widths = tail_widths(len(path), p.taper)
    half_w = p.tail_w * r * 0.5
    rings = []
    for k, q in enumerate(path):
        t = (path[min(k + 1, len(path) - 1)] - path[max(k - 1, 0)])
        t = t.normalized() if t.length > 1e-9 else Vector((0, 0, -1))
        hit = bvh.find_nearest(q)
        nrm = hit[1] if hit[0] is not None else out
        wv = t.cross(nrm)
        wv = wv.normalized() if wv.length > 1e-9 else side
        nv = wv.cross(t).normalized()
        if nv.dot(nrm) < 0:
            nv = -nv
        rings.append(_frame_ring(q, wv, nv, ring_section(SECTION, half_w * widths[k], half_t * 0.6, 0.4)))
    _tube(bm, rings, False)
    if p.fringe > 0.01:
        # thin threads hanging from the bottom edge
        q, wv = path[-1], None
        t = (path[-1] - path[-2]).normalized()
        hit = bvh.find_nearest(q)
        nrm = hit[1] if hit[0] is not None else out
        wv = t.cross(nrm).normalized() if t.cross(nrm).length > 1e-9 else side
        count = 7
        flen = p.fringe * r * 1.2
        for j in range(count):
            s = (j / (count - 1) - 0.5) * 2.0 * half_w * widths[-1] * 0.9
            base = q + wv * s
            pts = [base, base + Vector((0, 0, -flen * 0.5)), base + Vector((0, 0, -flen))]
            th = half_t * 0.25
            rr = [_frame_ring(pt, wv, wv.cross(Vector((0, 0, -1))), ring_section(6, th, th)) for pt in pts]
            _tube(bm, rr, False)


def _add_drape(bm, bvh, c, outer, n, front, side, p, r, half_t, gap):
    from . import cape_gen
    from . import clothing_gen
    span = math.radians(70.0) * min(2.0, p.tail_w / 2.2 + 0.3)
    cols = max(8, n // 3)
    collar, lengths = [], []
    for j in range(cols):
        s = j / (cols - 1) * 2.0 - 1.0
        centre, out, hh = _ring_at(outer, n, s * span)
        collar.append(centre - Vector((0.0, 0.0, hh * 0.5)))
        lengths.append(max(r * 0.15, p.tail_len * r * (1.0 - abs(s)) ** 1.1))
    rows = max(6, int(p.segments * 0.5))
    axis = Vector((c.x, c.y, c.z))
    grid = cape_gen.drape(bvh, axis, collar, lengths, rows, gap + half_t, 0.15)
    sheet = bmesh.new()
    vs = [[sheet.verts.new(q) for q in col] for col in grid]
    for i in range(cols - 1):
        for k in range(rows):
            sheet.faces.new((vs[i][k], vs[i][k + 1], vs[i + 1][k + 1], vs[i + 1][k]))
    bmesh.ops.remove_doubles(sheet, verts=sheet.verts[:], dist=r * 1e-3)
    sheet.normal_update()
    outward = sum(((f.calc_center_median() - axis).dot(f.normal) for f in sheet.faces), 0.0)
    if outward < 0:
        bmesh.ops.reverse_faces(sheet, faces=sheet.faces[:])
    clothing_gen._clean(sheet)
    solid = clothing_gen.shell(sheet, half_t * 0.5)
    sheet.free()
    me = bpy.data.meshes.new('_mch_scarf_tmp')
    try:
        solid.to_mesh(me)
        bm.from_mesh(me)
    finally:
        solid.free()
        bpy.data.meshes.remove(me)


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
        raise cg.CutError('This scarf was applied (no outline kept).')
    target = bpy.data.objects.get(src.get('target', ''))
    if target is None or target.type != 'MESH':
        raise cg.CutError('The body the scarf was drawn on is gone.')
    bm = build(context, src, ob.mch_scarf, target)
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
    st = getattr(getattr(context, 'scene', None), 'mch_scarf', None)
    if st is not None:
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


class MCH_PG_Scarf(bpy.types.PropertyGroup):
    """Scene.mch_scarf = settings for the next scarf; Object.mch_scarf = live scarf."""
    style: EnumProperty(name='Style', items=STYLE_ITEMS, default='WRAP', update=_style_update)
    wraps: IntProperty(name='Wraps', default=2, min=1, max=5, update=_update)
    height: FloatProperty(name='Height', default=1.0, min=0.2, max=4.0, update=_update,
                          description='Scarf height (1 = as drawn)')
    thick: FloatProperty(name='Thickness', default=0.55, min=0.05, max=2.0, update=_update,
                         description='Cloth bulk (part of the neck size)')
    loose: FloatProperty(name='Looseness', default=0.15, min=0.0, max=2.0, update=_update)
    bunch: FloatProperty(name='Bunching', default=0.5, min=0.0, max=1.5, update=_update,
                         description='Uneven, gathered cloth along the wraps')
    flare: FloatProperty(name='Flare', default=0.0, min=0.0, max=2.0, update=_update,
                         description='The lower edge stands out (cowl)')
    ends: EnumProperty(name='Ends', items=ENDS_ITEMS, default='TWO', update=_update)
    tail_len: FloatProperty(name='Tail Length', default=4.0, min=0.3, max=20.0, update=_update,
                            description='Length of the tails / drape (part of the neck size)')
    tail_w: FloatProperty(name='Tail Width', default=1.1, min=0.2, max=6.0, update=_update)
    taper: FloatProperty(name='Taper', default=0.15, min=0.0, max=0.9, update=_update)
    fringe: FloatProperty(name='Fringe', default=0.0, min=0.0, max=2.0, update=_update,
                          description='Threads at the end of the tails')
    tail_angle: FloatProperty(name='Tail Position', default=25.0, min=-180.0, max=180.0, update=_update,
                              description='Where the tail hangs, degrees from the front')
    turn: FloatProperty(name='Turn', default=0.0, subtype='ANGLE', update=_update,
                        description='Which way is the front (0 = toward the view it was drawn in)')
    seed: IntProperty(name='Seed', default=1, min=0, update=_update)
    segments: IntProperty(name='Segments', default=40, min=16, max=160, update=_update)
    live: BoolProperty(default=False, options={'HIDDEN'})
    last_error: StringProperty(default='', options={'HIDDEN', 'SKIP_SAVE'})


def perform(context, loops, projector):
    """Outline round a neck -> a live scarf.  Returns a report; raises cg.CutError."""
    from . import armor_plate as ap
    from . import cape_gen
    from . import face_extract as fx
    scene = context.scene
    st = scene.mch_scarf
    groups = cg.prepare_loops(loops)
    target = cape_gen.pick_body(context, projector, groups)
    if target is None:
        raise cg.CutError('Draw round the neck (the scarf wraps round it).')
    frozen = ap.freeze_projector(projector)
    if frozen is None:
        raise cg.CutError('This view cannot be saved for the scarf.')
    me = bpy.data.meshes.new(target.name + '_Scarf')
    ob = bpy.data.objects.new(me.name, me)
    fx._parts_collection(context, COLLECTION).objects.link(ob)
    for mat in target.data.materials:
        me.materials.append(mat)
    ob[SRC_KEY] = json.dumps({'loops': [[[float(x), float(y)] for x, y in lp] for lp in loops], 'proj': frozen,
                              'target': target.name})
    p = ob.mch_scarf
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
    name = dict((s[0], s[1]) for s in STYLE_ITEMS)[p.style]
    return f'Scarf "{ob.name}" on {target.name} ({name}, {len(me.polygons)} faces)'


def live_scarf(context):
    ob = getattr(context, 'active_object', None)
    if ob is not None and getattr(ob, 'mch_scarf', None) is not None and ob.mch_scarf.live and source(ob):
        return ob
    return None


def apply(ob):
    ob.mch_scarf.live = False
    if SRC_KEY in ob:
        del ob[SRC_KEY]


class MCH_OT_scarf_apply(bpy.types.Operator):
    bl_idname = 'mch.scarf_apply'
    bl_label = 'Apply Scarf'
    bl_description = 'The scarf becomes a plain mesh (the sliders stop rebuilding it)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return live_scarf(context) is not None

    def execute(self, context):
        apply(live_scarf(context))
        return {'FINISHED'}


def draw(layout, context):
    ob = live_scarf(context)
    p = ob.mch_scarf if ob is not None else context.scene.mch_scarf
    box = layout.box()
    if ob is not None:
        box.label(text='LIVE Scarf: ' + ob.name, icon='MOD_CLOTH')
        if p.last_error:
            box.label(text=p.last_error, icon='ERROR')
    else:
        box.label(text='Scarf: settings for the next one', icon='MOD_CLOTH')
    box.row(align=True).prop(p, 'style', expand=True)
    col = box.column(align=True)
    col.prop(p, 'wraps')
    col.prop(p, 'height', slider=True)
    col.prop(p, 'thick', slider=True)
    col.prop(p, 'loose', slider=True)
    col.prop(p, 'bunch', slider=True)
    col.prop(p, 'flare', slider=True)
    box.row(align=True).prop(p, 'ends', expand=True)
    if p.ends != 'NONE':
        col = box.column(align=True)
        col.prop(p, 'tail_len', slider=True)
        col.prop(p, 'tail_w', slider=True)
        if p.ends != 'DRAPE':
            col.prop(p, 'taper', slider=True)
            col.prop(p, 'tail_angle', slider=True)
        col.prop(p, 'fringe', slider=True)
    col = box.column(align=True)
    col.prop(p, 'turn')
    r = col.row(align=True)
    r.prop(p, 'seed')
    r.prop(p, 'segments')
    if ob is not None:
        box.operator('mch.scarf_apply', icon='CHECKMARK')
    col = layout.column(align=True)
    col.scale_y = 0.8
    for line in ('Look at the front, draw round the neck', 'The drawing height = scarf height',
                 'Ends: tails or a front drape', 'Apply: plain mesh'):
        col.label(text=line)


CLASSES = (MCH_PG_Scarf, MCH_OT_scarf_apply)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_scarf = bpy.props.PointerProperty(type=MCH_PG_Scarf)
    bpy.types.Object.mch_scarf = bpy.props.PointerProperty(type=MCH_PG_Scarf)


def unregister():
    for n, t in (('mch_scarf', bpy.types.Object), ('mch_scarf', bpy.types.Scene)):
        try:
            delattr(t, n)
        except AttributeError:
            pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
