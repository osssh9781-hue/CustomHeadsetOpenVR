"""0.24.31 Hood: draw round a head (looking at the face) -> a live hood: a shell round the head, open toward you,
with a cowl draping over the shoulders.

The drawing only says which head and how big: the hits inside it give the head centre and size, the view gives the
face direction (Turn rotates it).  The shell follows the head at Looseness (rays from outside toward the centre,
so it hugs the skull shape), the back top is pulled out into a Peak, an oval Face Opening is left out, and from the
bottom ring the Cowl drapes down over the shoulders like the cape (pushed out of the body).  Folds and a Thickness
make it cloth (closed mesh, a rim round the face).

Styles: Cloak Hood (pointed, deep, big cowl), Tactical (close, closed front below the chin), Monk (deep, loose).
``direction`` is pure.
"""
from __future__ import annotations

import json
import math

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from mathutils import Matrix, Vector, noise

from . import core_geometry as cg

SRC_KEY = 'mch_hood_src'
COLLECTION = 'Hoods'
STYLE_ITEMS = [
    ('CLOAK', 'Cloak Hood', 'Pointed, deep hood with a big cowl over the shoulders'),
    ('TACTICAL', 'Tactical', 'Close-fitting hood, the front closed below the chin'),
    ('MONK', 'Monk', 'Deep, loose hood'),
]
STYLES = {
    'CLOAK': dict(loose=0.4, depth=0.35, open_w=46.0, open_h=55.0, open_drop=8.0, peak=1.0, cowl=1.0,
                  front_open=False, folds=0.6, thickness=0.06),
    'TACTICAL': dict(loose=0.12, depth=0.0, open_w=42.0, open_h=36.0, open_drop=-6.0, peak=0.1, cowl=0.45, front_open=False,
                     folds=0.25, thickness=0.05),
    'MONK': dict(loose=0.6, depth=0.5, open_w=52.0, open_h=62.0, open_drop=10.0, peak=0.25, cowl=0.7, front_open=True,
                 folds=0.7, thickness=0.07),
}
LIVE_KEYS = ('loose', 'depth', 'open_w', 'open_h', 'open_drop', 'turn', 'peak', 'cowl', 'front_open', 'folds', 'seed',
             'thickness', 'columns', 'rows')
NECK = math.radians(118)        # where the hood part ends and the cowl begins (angle down from the top)


def direction(theta, phi, front):
    """Unit direction from the head centre: theta round the vertical (0 = front), phi down from the top."""
    side = Vector((-front.y, front.x, 0.0))
    h = front * math.cos(theta) + side * math.sin(theta)
    return Vector((h.x * math.sin(phi), h.y * math.sin(phi), math.cos(phi)))


def locate(context, projector, outline, bvh):
    """Head centre, radius and the face direction (toward the viewer) from the drawn outline."""
    from . import creature_hair
    pts = creature_hair.root_points(outline, 60, 3) + list(outline[::2])
    hits = []
    for xy in pts:
        o, d = projector.ray(xy)
        o, d = Vector(o), Vector(d).normalized()
        loc, _n, _i, _dist = bvh.ray_cast(o, d)
        if loc is None:
            continue
        hits.append(loc)
        # the far side of the head too
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
        raise cg.CutError('Draw round the head (the hood goes over it).')
    c = sum(hits, Vector()) / len(hits)
    r = sum((h - c).length for h in hits) / len(hits)
    front = -Vector(projector.view_dir)
    front.z = 0.0
    if front.length < 1e-6:
        front = Vector((0.0, -1.0, 0.0))
    return c, r, front.normalized()


def source(ob):
    if ob is None:
        return None
    try:
        raw = ob.get(SRC_KEY)
        return json.loads(raw) if raw else None
    except (TypeError, ValueError, ReferenceError):
        return None


def build(context, src, p, target):
    from . import armor_plate as ap
    from . import cape_gen
    from . import clothing_gen
    projector = ap.thaw_projector(src['proj'])
    bvh, lo, hi = cape_gen._body(context, target)
    groups = cg.prepare_loops([[tuple(q) for q in lp] for lp in src['loops']])
    if not groups:
        raise cg.CutError('The outline is empty.')
    c, r, front = locate(context, projector, groups[0][0], bvh)
    front = Matrix.Rotation(p.turn, 3, 'Z') @ front
    ncol = max(12, p.columns)
    nhood = max(6, p.rows)
    off = r * (0.06 + p.loose * 0.35)
    far = r * 4.0
    face_ph = math.radians(90.0 + p.open_drop)
    ow, oh = math.radians(max(5.0, p.open_w)), math.radians(max(5.0, p.open_h))

    def in_face(th, ph):
        dth = (th + math.pi) % (2 * math.pi) - math.pi
        return (dth / ow) ** 2 + ((ph - face_ph) / oh) ** 2

    def point(th, ph):
        d = direction(th, ph, front)
        loc, _n, _i, _dd = bvh.ray_cast(c + d * far, -d, far)
        base = loc if loc is not None and (loc - c).length < r * 2.2 else c + d * r
        q = base + d * off
        # peak: the back top pulled back / up into a point
        back = max(0.0, -d.dot(front))
        up = max(0.0, math.cos(ph) + 0.35)
        q += (-front + Vector((0, 0, 0.55))) * (p.peak * r * 1.1 * (back ** 3) * (up ** 2))
        # the rim round the face stands forward (a deep hood)
        e = math.sqrt(in_face(th, ph))
        q += front * (p.depth * r * max(0.0, 1.0 - (e - 1.0) / 0.9) * (1.0 if ph <= NECK else 0.0))
        return q

    grid = []
    for i in range(ncol):
        th = 2 * math.pi * i / ncol
        grid.append([point(th, NECK * k / nhood) for k in range(nhood + 1)])
    # cowl: from the bottom ring down over the shoulders (drape like the cape)
    gap = r * 0.05
    if p.cowl > 0.01:
        ring = [col[-1] for col in grid]
        lengths = [p.cowl * r * 2.4] * ncol
        rows_c = max(3, int(nhood * p.cowl * 0.8))
        axis = Vector((c.x, c.y, c.z))
        drop = cape_gen.drape(bvh, axis, ring, lengths, rows_c, gap + off * 0.5, 0.35 + p.loose * 0.3)
        for col, extra in zip(grid, drop):
            col.extend(extra[1:])
    nrow = len(grid[0])
    # folds: soft noise, more toward the cowl
    if p.folds > 0:
        seed = Vector((p.seed * 3.1, p.seed * 1.7, p.seed * 5.3))
        for i in range(ncol):
            for k in range(nrow):
                q = grid[i][k]
                w = 0.3 + 0.7 * (k / max(1, nrow - 1))
                n = (q - c)
                n = n.normalized() if n.length > 1e-9 else Vector((0, 0, 1))
                f = noise.noise(Vector((q.x, q.y, q.z * 2.5)) * (3.0 / r) + seed)
                grid[i][k] = cape_gen._push_out(bvh, q + n * (f * p.folds * r * 0.08 * w), gap)
    # face opening (oval round the front, a little below the middle) and an open front for the cowl
    hole = set()
    for i in range(ncol):
        th = 2 * math.pi * (i + 0.5) / ncol
        dth = (th + math.pi) % (2 * math.pi) - math.pi
        for k in range(nrow - 1):
            if k < nhood:
                if in_face(th, NECK * (k + 0.5) / nhood) < 1.0:
                    hole.add((i, k))
            elif p.front_open and abs(dth) < ow * 0.55:
                hole.add((i, k))
    # the opening edge: move its points onto the oval (no stair steps)
    rim = set()
    for (i, k) in hole:
        if k < nhood:
            for a, b in ((i, k), ((i + 1) % ncol, k), (i, k + 1), ((i + 1) % ncol, k + 1)):
                rim.add((a, b))
    for (i, k) in rim:
        quads = [((i - di) % ncol, k - dk) for di in (0, 1) for dk in (0, 1)]
        quads = [q for q in quads if 0 <= q[1] < nrow - 1]
        if all(q in hole for q in quads) or k > nhood:
            continue
        th = 2 * math.pi * i / ncol
        ph = NECK * k / nhood
        dth = (th + math.pi) % (2 * math.pi) - math.pi
        e = math.sqrt(max(in_face(th, ph), 1e-9))
        if e < 1e-3:
            continue
        ph2 = min(NECK, max(0.02, face_ph + (ph - face_ph) / e))
        q = point(dth / e, ph2)
        if p.folds > 0:
            q = q + (grid[i][k] - point(th, ph))
        grid[i][k] = q
    bm = bmesh.new()
    vs = [[bm.verts.new(q) for q in col] for col in grid]
    for i in range(ncol):
        j = (i + 1) % ncol
        for k in range(nrow - 1):
            if (i, k) in hole:
                continue
            bm.faces.new((vs[i][k], vs[j][k], vs[j][k + 1], vs[i][k + 1]))
    # top: close the pole with a fan
    top = bm.verts.new(sum((col[0] for col in grid), Vector()) / ncol)
    for i in range(ncol):
        j = (i + 1) % ncol
        bm.faces.new((vs[j][0], vs[i][0], top))
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=r * 1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    # normals out (away from the head)
    bm.normal_update()
    outward = sum(((f.calc_center_median() - c).dot(f.normal) for f in bm.faces), 0.0)
    if outward < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    clothing_gen._clean(bm)
    out = clothing_gen.shell(bm, p.thickness * r)
    bm.free()
    for f in out.faces:
        f.smooth = True
    return out


def rebuild(context, ob):
    src = source(ob)
    if src is None:
        raise cg.CutError('This hood was applied (no outline kept).')
    target = bpy.data.objects.get(src.get('target', ''))
    if target is None or target.type != 'MESH':
        raise cg.CutError('The head the hood was drawn on is gone.')
    bm = build(context, src, ob.mch_hood, target)
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
    st = getattr(getattr(context, 'scene', None), 'mch_hood', None)
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


class MCH_PG_Hood(bpy.types.PropertyGroup):
    """Scene.mch_hood = settings for the next hood; Object.mch_hood = live hood."""
    style: EnumProperty(name='Style', items=STYLE_ITEMS, default='CLOAK', update=_style_update)
    loose: FloatProperty(name='Looseness', default=0.4, min=0.0, max=1.5, update=_update,
                         description='How far the hood stands off the head')
    depth: FloatProperty(name='Depth', default=0.35, min=0.0, max=1.5, update=_update,
                         description='How far the rim round the face stands forward (deep hood = face in shadow)')
    open_w: FloatProperty(name='Opening Width', default=46.0, min=5.0, max=110.0, update=_update,
                          description='Face opening, degrees to each side')
    open_h: FloatProperty(name='Opening Height', default=55.0, min=5.0, max=110.0, update=_update)
    open_drop: FloatProperty(name='Opening Drop', default=8.0, min=-40.0, max=40.0, update=_update,
                             description='Moves the face opening down (+) / up (-)')
    turn: FloatProperty(name='Turn', default=0.0, subtype='ANGLE', update=_update,
                        description='Which way the face opening looks (0 = toward the view it was drawn in)')
    peak: FloatProperty(name='Peak', default=1.0, min=0.0, max=2.0, update=_update,
                        description='The back top pulled out into a point')
    cowl: FloatProperty(name='Cowl', default=1.0, min=0.0, max=3.0, update=_update,
                        description='How far it drapes down over the shoulders')
    front_open: BoolProperty(name='Open Front', default=False, update=_update,
                             description='The cowl is open under the chin (off = closed, like a balaclava)')
    folds: FloatProperty(name='Folds', default=0.6, min=0.0, max=2.0, update=_update)
    seed: IntProperty(name='Seed', default=1, min=0, update=_update)
    thickness: FloatProperty(name='Thickness', default=0.06, min=0.005, max=0.3, update=_update,
                             description='Cloth thickness (part of the head size)')
    columns: IntProperty(name='Columns', default=48, min=12, max=160, update=_update)
    rows: IntProperty(name='Rows', default=22, min=6, max=100, update=_update)
    live: BoolProperty(default=False, options={'HIDDEN'})
    last_error: StringProperty(default='', options={'HIDDEN', 'SKIP_SAVE'})


def perform(context, loops, projector):
    """Outline round a head -> a live hood.  Returns a report; raises cg.CutError."""
    from . import armor_plate as ap
    from . import cape_gen
    from . import face_extract as fx
    scene = context.scene
    st = scene.mch_hood
    groups = cg.prepare_loops(loops)
    target = cape_gen.pick_body(context, projector, groups)
    if target is None:
        raise cg.CutError('Draw round the head (the hood goes over it).')
    frozen = ap.freeze_projector(projector)
    if frozen is None:
        raise cg.CutError('This view cannot be saved for the hood.')
    me = bpy.data.meshes.new(target.name + '_Hood')
    ob = bpy.data.objects.new(me.name, me)
    fx._parts_collection(context, COLLECTION).objects.link(ob)
    for mat in target.data.materials:
        me.materials.append(mat)
    ob[SRC_KEY] = json.dumps({'loops': [[[float(x), float(y)] for x, y in lp] for lp in loops], 'proj': frozen,
                              'target': target.name})
    p = ob.mch_hood
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
    return f'Hood "{ob.name}" on {target.name} ({name}, {len(me.polygons)} faces)'


def live_hood(context):
    ob = getattr(context, 'active_object', None)
    if ob is not None and getattr(ob, 'mch_hood', None) is not None and ob.mch_hood.live and source(ob):
        return ob
    return None


def apply(ob):
    ob.mch_hood.live = False
    if SRC_KEY in ob:
        del ob[SRC_KEY]


class MCH_OT_hood_apply(bpy.types.Operator):
    bl_idname = 'mch.hood_apply'
    bl_label = 'Apply Hood'
    bl_description = 'The hood becomes a plain mesh (the sliders stop rebuilding it)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return live_hood(context) is not None

    def execute(self, context):
        apply(live_hood(context))
        return {'FINISHED'}


def draw(layout, context):
    ob = live_hood(context)
    p = ob.mch_hood if ob is not None else context.scene.mch_hood
    box = layout.box()
    if ob is not None:
        box.label(text='LIVE Hood: ' + ob.name, icon='USER')
        if p.last_error:
            box.label(text=p.last_error, icon='ERROR')
    else:
        box.label(text='Hood: settings for the next one', icon='USER')
    box.row(align=True).prop(p, 'style', expand=True)
    col = box.column(align=True)
    col.prop(p, 'loose', slider=True)
    col.prop(p, 'depth', slider=True)
    col.prop(p, 'peak', slider=True)
    col.prop(p, 'cowl', slider=True)
    col.prop(p, 'front_open', toggle=True)
    col = box.column(align=True)
    col.prop(p, 'open_w', slider=True)
    col.prop(p, 'open_h', slider=True)
    col.prop(p, 'open_drop', slider=True)
    col.prop(p, 'turn')
    col = box.column(align=True)
    col.prop(p, 'folds', slider=True)
    col.prop(p, 'seed')
    col.prop(p, 'thickness', slider=True)
    r = col.row(align=True)
    r.prop(p, 'columns')
    r.prop(p, 'rows')
    if ob is not None:
        box.operator('mch.hood_apply', icon='CHECKMARK')
    col = layout.column(align=True)
    col.scale_y = 0.8
    for line in ('Look at the face, draw round the head', 'The face opening looks at you (Turn to change)',
                 'Cowl = the part over the shoulders', 'Apply: plain mesh'):
        col.label(text=line)


CLASSES = (MCH_PG_Hood, MCH_OT_hood_apply)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_hood = bpy.props.PointerProperty(type=MCH_PG_Hood)
    bpy.types.Object.mch_hood = bpy.props.PointerProperty(type=MCH_PG_Hood)


def unregister():
    for n, t in (('mch_hood', bpy.types.Object), ('mch_hood', bpy.types.Scene)):
        try:
            delattr(t, n)
        except AttributeError:
            pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
