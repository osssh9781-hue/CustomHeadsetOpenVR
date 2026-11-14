"""0.24.172 Feathers / Scales on the skin - the Fur tool's other two tabs (user: "퍼 에드온에도 피부에 넣을 수 있는 페더
탭도 만들어 줘, 스케일이랑 이론은 같을 거 아냐, 그리고 비늘 탭도 그렇고 - 여기에 넣는 비늘도 좀 더 리얼하게").

The same as the fur: an area drawn on a body (the Fur tool's lasso; Alt + draw takes some away) - but instead of
strands, feathers (15) or scales (8 real ones) grow there, each lying down the body (the world's down along the skin,
turned by Flow Angle), lifted a little at its free end so they overlap like shingles, spread evenly (none closer than
Spacing to the next), a little random in size and turn.  A cover object (child of the body): its points carry where
each sits, Geometry Nodes put the shape there (light: instances) - live, its sliders lay them again; Enter / Apply
makes real geometry.  The area is a weight on the body's points (``mch_cover_<id>``), like the fur's.
"""
from __future__ import annotations

import json
import math
import random
import uuid

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from mathutils import Matrix, Vector

COVER_KEY = 'mch_cover'            # on a cover object (1)
AREA_KEY = 'mch_cover_area'        # ... the body attribute holding its area
SHAPE_COLLS = {'FEATHERS': 'MCH Cover Feathers', 'SCALES': 'MCH Cover Scales'}
GROWS = (('FUR', 'Fur', 'Strands (the fur)'), ('FEATHERS', 'Feathers', 'Feathers lying down the body, overlapping'),
         ('SCALES', 'Scales', 'Scales lying down the body, overlapping in rows'))
_BUSY = [False]


def is_cover(ob):
    return ob is not None and bool(ob.get(COVER_KEY))


def active_cover(context):
    ob = getattr(context.view_layer.objects, 'active', None)
    try:
        return ob if is_cover(ob) and ob.select_get() else None
    except (RuntimeError, ReferenceError):
        return None


# ---- the shapes (hidden objects the covers instance) ---------------------------------------------------------------

def shape_objects(context, kind):
    """The built-in shapes of ``kind`` (FEATHERS / SCALES) as hidden objects (made the first time): {id: object}."""
    from . import creature_shapes as cs
    cname = SHAPE_COLLS[kind]
    coll = bpy.data.collections.get(cname)
    if coll is None:
        coll = bpy.data.collections.new(cname)
    if coll.name not in context.scene.collection.children:
        context.scene.collection.children.link(coll)
    have = {o.data.get('mch_shape_id'): o for o in coll.objects if o.type == 'MESH'}
    meshes = cs.feather_meshes() if kind == 'FEATHERS' else cs.scale_meshes_real()
    for name, me in meshes:
        sid = me.get('mch_shape_id')
        if sid in have:
            bpy.data.meshes.remove(me)
            continue
        ob = bpy.data.objects.new(name, me)
        k = cs.FEATHER_LENGTHS.get(sid, 1.0) if kind == 'FEATHERS' else 1.0
        ob.scale = (k, k, k)                           # (each feather its own length)
        coll.objects.link(ob)
        ob.hide_render = True
        try:
            ob.hide_set(True)
        except RuntimeError:
            pass
        have[sid] = ob
    return have


# ---- the area ---------------------------------------------------------------------------------------------------------

def area_weights(body, name):
    me = body.data
    a = me.attributes.get(name)
    w = np.zeros(len(me.vertices), np.float32)
    if a is not None and a.domain == 'POINT':
        a.data.foreach_get('value', w)
    return w


def placements(body, w, p, size_world, shapes, seed=0):
    """Where the shapes sit on the area (body space): (locations, quaternions, scales, picks).  Evenly spread (none
    closer than Spacing x the size), lying down the body (turned by Flow Angle), the free end lifted by Lift."""
    me = body.data
    me.calc_loop_triangles()
    n_t = len(me.loop_triangles)
    if n_t == 0 or not np.any(w > 0.5):
        return np.zeros((0, 3)), np.zeros((0, 4)), np.zeros((0, 3)), np.zeros(0, int)
    tri = np.empty(n_t * 3, np.int32)
    me.loop_triangles.foreach_get('vertices', tri)
    tri = tri.reshape(-1, 3)
    keep = (w[tri] > 0.5).sum(1) >= 2
    tri = tri[keep]
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3).astype(float)
    vn = np.empty(len(me.vertices) * 3, np.float32)
    me.vertex_normals.foreach_get('vector', vn)
    vn = vn.reshape(-1, 3).astype(float)
    ms = body.matrix_world.to_scale()
    unit = 1.0 / max((abs(ms.x) + abs(ms.y) + abs(ms.z)) / 3.0, 1e-9)
    size = size_world * unit                          # (in the body's space)
    spacing = max(size * p.spacing, 1e-6)
    a, b, c = co[tri[:, 0]], co[tri[:, 1]], co[tri[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    rng = np.random.default_rng(int(p.seed) + seed * 7919)
    want = area / (spacing * spacing) * 4.0           # (candidates: 4 a spacing square, then thinned)
    cnt = np.floor(want + rng.random(len(want))).astype(int)
    if cnt.sum() > 400000:
        cnt = np.floor(cnt * 400000 / cnt.sum()).astype(int)
    ti = np.repeat(np.arange(len(tri)), cnt)
    r1, r2 = rng.random(len(ti)), rng.random(len(ti))
    flip = r1 + r2 > 1.0
    r1[flip], r2[flip] = 1.0 - r1[flip], 1.0 - r2[flip]
    P = a[ti] + (b[ti] - a[ti]) * r1[:, None] + (c[ti] - a[ti]) * r2[:, None]
    Nn = vn[tri[ti, 0]] * (1 - r1 - r2)[:, None] + vn[tri[ti, 1]] * r1[:, None] + vn[tri[ti, 2]] * r2[:, None]
    Nn /= np.maximum(np.linalg.norm(Nn, axis=1), 1e-12)[:, None]
    # thinned: none closer than the spacing (a grid of cells the spacing wide)
    order = rng.permutation(len(P))
    cell = {}
    acc = []
    inv = 1.0 / spacing
    sp2 = spacing * spacing
    for k in order:
        q = P[k]
        key = (int(math.floor(q[0] * inv)), int(math.floor(q[1] * inv)), int(math.floor(q[2] * inv)))
        ok = True
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for j in cell.get((key[0] + dx, key[1] + dy, key[2] + dz), ()):
                        d = P[j] - q
                        if d @ d < sp2:
                            ok = False
                            break
                    if not ok:
                        break
                if not ok:
                    break
            if not ok:
                break
        if ok:
            cell.setdefault(key, []).append(k)
            acc.append(k)
            if len(acc) >= 60000:
                break
    acc = np.array(acc, int)
    P, Nn = P[acc], Nn[acc]
    # down the body: the world's down along the skin, turned by Flow Angle (and a little at random)
    R = np.array(body.matrix_world.to_3x3().normalized().inverted_safe(), float)
    down = R @ np.array([0.0, 0.0, -1.0])
    T = down[None, :] - Nn * (Nn @ down)[:, None]
    weak = np.linalg.norm(T, axis=1) < 1e-3
    if np.any(weak):
        alt = R @ np.array([0.0, -1.0, 0.0])
        T[weak] = alt[None, :] - Nn[weak] * (Nn[weak] @ alt)[:, None]
    T /= np.maximum(np.linalg.norm(T, axis=1), 1e-12)[:, None]
    prng = random.Random(int(p.seed) * 31 + 7)
    ids = list(shapes)
    locs, quats, scls, picks = [], [], [], []
    for i in range(len(P)):
        n = Vector(Nn[i])
        t = Vector(T[i])
        ang = p.flow + prng.uniform(-1.0, 1.0) * p.turn_random
        t = Matrix.Rotation(ang, 3, n) @ t
        lift = p.lift
        x = (t * math.cos(lift) + n * math.sin(lift)).normalized()
        z = (n * math.cos(lift) - t * math.sin(lift)).normalized()
        y = z.cross(x)
        m = Matrix((x, y, z)).transposed()
        j = 0 if len(ids) == 1 else prng.randrange(len(ids))
        ob = shapes[ids[j]]
        sv = Vector(tuple(ob.scale))
        f = size * (1.0 + prng.uniform(-1.0, 1.0) * p.size_random)
        sc = Vector((sv.x * f * p.length, sv.y * f * p.width, sv.z * f))
        locs.append(tuple(Vector(P[i]) - n * (p.sink * size)))
        quats.append(tuple(m.to_quaternion()))
        scls.append(tuple(sc))
        picks.append(j)
    return np.asarray(locs, float), np.asarray(quats, float), np.asarray(scls, float), np.asarray(picks, int)


def cover_shapes(context, ob):
    p = ob.mch_cover
    kind = p.grow if p.grow in SHAPE_COLLS else 'FEATHERS'
    have = shape_objects(context, kind)
    chosen = [s for s in json.loads(p.shapes_json or '[]') if s in have] or [next(iter(have))]
    return kind, {s: have[s] for s in chosen}


def body_size(body):
    pts = [body.matrix_world @ Vector(c) for c in body.bound_box]
    lo = Vector((min(v.x for v in pts), min(v.y for v in pts), min(v.z for v in pts)))
    hi = Vector((max(v.x for v in pts), max(v.y for v in pts), max(v.z for v in pts)))
    return max((hi - lo).length, 1e-6)


def rebuild(context, ob):
    """The cover's shapes laid again on its area (its own settings).  Returns how many."""
    from . import greeble_line as gl
    body = ob.parent
    if body is None or body.type != 'MESH':
        return 0
    p = ob.mch_cover
    _kind, shapes = cover_shapes(context, ob)
    w = area_weights(body, ob[AREA_KEY])
    size_world = body_size(body) * p.size / 100.0
    locs, quats, scls, picks = placements(body, w, p, size_world, shapes)
    me = ob.data
    me.clear_geometry()
    n = len(locs)
    if n:
        me.vertices.add(n)
        me.vertices.foreach_set('co', locs.astype(np.float32).ravel())
    for name, kind, field, data in (('mch_rot', 'QUATERNION', 'value', quats), ('mch_scale', 'FLOAT_VECTOR', 'vector', scls),
                                    ('mch_pick', 'INT', 'value', picks)):
        at = me.attributes.get(name)
        if at is not None:
            me.attributes.remove(at)
        at = me.attributes.new(name, kind, 'POINT')
        if n:
            at.data.foreach_set(field, np.asarray(data).astype(np.int32 if kind == 'INT' else np.float32).ravel())
    me.update()
    gl._group(ob, list(shapes.values()))
    ob.update_tag()
    return n


# ---- settings -------------------------------------------------------------------------------------------------------

def _upd(self, context):
    if _BUSY[0]:
        return
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and is_cover(ob):
        rebuild(context, ob)
        sc = getattr(context, 'scene', None)
        if sc is not None and hasattr(sc, 'mch_cover'):             # (the next cover starts like this one)
            _BUSY[0] = True
            try:
                for k in LIVE:
                    setattr(sc.mch_cover, k, getattr(self, k))
            finally:
                _BUSY[0] = False


def _upd_grow(self, context):
    """The tab: Feathers / Scales start from their own defaults."""
    if _BUSY[0] or isinstance(self.id_data, bpy.types.Object):
        return
    d = DEFAULTS.get(self.grow)
    if d:
        _BUSY[0] = True
        try:
            for k, v in d.items():
                setattr(self, k, v)
        finally:
            _BUSY[0] = False


DEFAULTS = {'FEATHERS': dict(size=4.0, spacing=0.35, lift=math.radians(14), length=1.0, width=1.0, sink=0.0,
                             size_random=0.15, shapes_json='["CONTOUR"]'),
            'SCALES': dict(size=2.2, spacing=0.55, lift=math.radians(10), length=1.0, width=1.0, sink=0.12,
                           size_random=0.12, shapes_json='["KEELED"]')}
LIVE = ('size', 'size_random', 'spacing', 'lift', 'flow', 'turn_random', 'length', 'width', 'sink', 'seed',
        'shapes_json')


class MCH_PG_Cover(bpy.types.PropertyGroup):
    grow: EnumProperty(name='Grow', items=GROWS, default='FUR', update=_upd_grow,
                       description='What the Fur tool grows on the area you draw')
    size: FloatProperty(name='Size %', default=4.0, min=0.05, max=50.0, soft_max=15.0, update=_upd,
                        description='A feather / scale this long (% of the body\'s size; each feather its own length x '
                                    'this)')
    size_random: FloatProperty(name='Size Random', default=0.15, min=0.0, max=0.9, update=_upd)
    spacing: FloatProperty(name='Spacing', default=0.35, min=0.05, max=3.0, update=_upd,
                           description='How close they sit (x the size): small = dense, overlapping')
    lift: FloatProperty(name='Lift', default=math.radians(14), min=0.0, max=math.radians(80), subtype='ANGLE',
                        update=_upd, description='The free end lifted off the skin (they overlap like shingles)')
    flow: FloatProperty(name='Flow Angle', default=0.0, min=-math.pi, max=math.pi, subtype='ANGLE', update=_upd,
                        description='Which way they lie, turned round the skin\'s normal: 0 down the body')
    turn_random: FloatProperty(name='Turn Random', default=math.radians(8), min=0.0, max=math.pi, subtype='ANGLE',
                               update=_upd)
    length: FloatProperty(name='Length', default=1.0, min=0.1, max=10.0, soft_max=3.0, update=_upd)
    width: FloatProperty(name='Width', default=1.0, min=0.1, max=10.0, soft_max=3.0, update=_upd)
    sink: FloatProperty(name='Sink', default=0.0, min=-0.5, max=0.8, update=_upd,
                        description='Into the skin, x the size')
    seed: IntProperty(name='Seed', default=0, min=0, update=_upd)
    shapes_json: StringProperty(default='["CONTOUR"]', update=_upd)
    mix: BoolProperty(name='Mix', default=False, description='A click adds the shape to the mix (random among them) '
                                                              'instead of taking it alone')


# ---- drawing an area ------------------------------------------------------------------------------------------------

def perform(context, loops, projector, erase=False):
    """The Fur tool's outline with Feathers / Scales on: the area added to (Alt: taken from) the selected cover of
    that body, else a new cover."""
    from . import base_mesh
    from . import core_geometry as cg
    from . import creature_fur as cf
    st = context.scene.mch_cover
    groups = cg.prepare_loops(loops)
    if not groups:
        raise cg.CutError('Draw a bigger area')
    cur = active_cover(context)
    wm = context.window_manager
    if getattr(wm, cf.NEW_KEY, False) or (cur is not None and cur.mch_cover.grow != st.grow):
        cur = None
    _q, found = base_mesh.anchor_hit(context, projector, groups[0][0])
    body = found[2] if found is not None else None
    if body is None and cur is not None:
        body = cur.parent
    if body is None or body.type != 'MESH':
        raise cg.CutError('Draw the area on a mesh (the body)')
    if cur is not None and cur.parent != body:
        cur = None
    if erase and cur is None:
        raise cg.CutError('Alt + draw takes area away from the selected feathers / scales - select them first')
    idx = cf.area_points(context, body, loops, projector, cf.body_mirrors(body))
    if not len(idx) and not erase:
        raise cg.CutError('No surface of the body facing the view inside the outline')
    made = cur is None
    if made:
        me = bpy.data.meshes.new('Feathers' if st.grow == 'FEATHERS' else 'Scales')
        cur = bpy.data.objects.new(me.name, me)
        colls = body.users_collection or (context.scene.collection,)
        colls[0].objects.link(cur)
        cur.parent = body
        cur.matrix_parent_inverse = Matrix.Identity(4)
        cur.matrix_basis = Matrix.Identity(4)
        cur[COVER_KEY] = 1
        cur[AREA_KEY] = 'mch_cover_' + uuid.uuid4().hex[:8]
        _BUSY[0] = True
        try:
            cur.mch_cover.grow = st.grow
            for k in LIVE:
                setattr(cur.mch_cover, k, getattr(st, k))
        finally:
            _BUSY[0] = False
    inside = cf.paint_area(body, cur[AREA_KEY], idx, 0.0 if erase else 1.0)
    n = rebuild(context, cur)
    try:
        setattr(wm, cf.NEW_KEY, False)
    except (AttributeError, TypeError):
        pass
    for o in context.selected_objects:
        o.select_set(False)
    cur.select_set(True)
    context.view_layer.objects.active = cur
    what = 'new' if made else ('area taken away' if erase else 'area added')
    return f'{cur.name} on {body.name}: {what} - {inside:,} points of the body in its area, {n:,} {st.grow.lower()}'


def apply_cover(context, ob):
    """The cover as real geometry (its shapes made real); its area weight on the body removed."""
    from . import greeble_line as gl
    kind = ob.mch_cover.grow
    body = ob.parent
    area = ob.get(AREA_KEY)
    gl.apply_line(context, ob)
    ob.name = ob.data.name = 'Feathers' if kind == 'FEATHERS' else 'Scales'
    for k in (COVER_KEY, AREA_KEY):
        if k in ob:
            del ob[k]
    if body is not None and area:
        a = body.data.attributes.get(area)
        if a is not None:
            body.data.attributes.remove(a)


def apply_targets(context):
    sel = [o for o in getattr(context, 'selected_objects', []) or [] if is_cover(o)]
    if sel:
        return sel
    ob = active_cover(context)
    return [ob] if ob is not None else []


class MCH_OT_cover_apply(bpy.types.Operator):
    """The selected feathers / scales made real geometry (no longer live)"""
    bl_idname = 'mch.cover_apply'
    bl_label = 'Apply Feathers / Scales'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and bool(apply_targets(context))

    def execute(self, context):
        obs = apply_targets(context)
        for ob in obs:
            apply_cover(context, ob)
        self.report({'INFO'}, 'Applied: ' + ', '.join(f'{o.name} ({len(o.data.polygons):,} faces)' for o in obs))
        return {'FINISHED'}


class MCH_OT_cover_shape(bpy.types.Operator):
    """This feather / scale (Mix on: added to / taken from the mix) - the selected cover too"""
    bl_idname = 'mch.cover_shape'
    bl_label = 'Feather / Scale Shape'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    shape: StringProperty(default='CONTOUR')

    def execute(self, context):
        st = context.scene.mch_cover
        ob = active_cover(context)
        pg = ob.mch_cover if ob is not None else st
        cur = json.loads(pg.shapes_json or '[]')
        if st.mix:
            cur = [s for s in cur if s != self.shape] if self.shape in cur else cur + [self.shape]
            cur = cur or [self.shape]
        else:
            cur = [self.shape]
        pg.shapes_json = json.dumps(cur)                     # (its update: the cover laid again)
        if ob is not None:
            _BUSY[0] = True
            try:
                st.shapes_json = pg.shapes_json
            finally:
                _BUSY[0] = False
        return {'FINISHED'}


def draw(layout, context):
    """The Feathers / Scales tab of the Fur window."""
    from . import creature_shapes as cs
    st = context.scene.mch_cover
    ob = active_cover(context)
    pg = ob.mch_cover if ob is not None else st
    col = layout.column(align=True)
    if ob is not None:
        col.label(text=f'{ob.name} on {ob.parent.name if ob.parent else "?"}: {len(ob.data.vertices):,} (live)')
    else:
        col.label(text=f'The next {"feathers" if st.grow == "FEATHERS" else "scales"}: draw an area on the body')
    chosen = json.loads(pg.shapes_json or '[]')
    items = cs.FEATHERS if st.grow == 'FEATHERS' else cs.SCALES
    g = layout.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
    for sid, label, _spec in items:
        g.operator('mch.cover_shape', text=label, depress=sid in chosen).shape = sid
    layout.prop(st, 'mix')
    col = layout.column(align=True)
    for k in ('size', 'size_random', 'spacing', 'lift', 'flow', 'turn_random', 'length', 'width', 'sink', 'seed'):
        col.prop(pg, k)
    if ob is not None:
        layout.operator('mch.cover_apply', text='Apply (Enter)', icon='CHECKMARK')
    col = layout.column(align=True)
    for line in ('Draw an area on the body: they grow there, lying down it',
                 'Draw again: more area for the selected one;  Alt + draw: take area away',
                 'New Fur: the next draw a new one'):
        col.label(text=line)


CLASSES = (MCH_PG_Cover, MCH_OT_cover_apply, MCH_OT_cover_shape)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_cover = PointerProperty(type=MCH_PG_Cover)
    bpy.types.Object.mch_cover = PointerProperty(type=MCH_PG_Cover)


def unregister():
    for T in (bpy.types.Scene, bpy.types.Object):
        if hasattr(T, 'mch_cover'):
            delattr(T, 'mch_cover')
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
