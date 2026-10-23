"""0.24.31 Clothing: draw the outline of a garment over a body (front view) -> a live top / pants made from the body.

The body surface inside the outline - front AND back, seen through - becomes the garment: openings (neck, sleeve
ends, waist, cuffs) are where the outline crosses the body.  The surface is then

    pushed out by Fit (tight .. loose) along smoothed normals,
    relaxed (Smooth) so it bridges hollows instead of hugging every muscle, kept off the body by Gap,
    hangs a little at the bottom (Hem Flare spreads the lowest part out),
    wrinkled (Wrinkles / Wrinkle Size, more where the body bends - joints - than on flat parts),
    and given Thickness (a closed mesh, rims at the openings).

Types fill in the sliders: T-Shirt, Hoodie (loose, thick), Pants, Cargo (loose pants).  ``relax`` is pure.
"""
from __future__ import annotations

import json
import math

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from mathutils import Matrix, Vector, noise

from . import core_geometry as cg

SRC_KEY = 'mch_clothing_src'
COLLECTION = 'Clothing'
TYPE_ITEMS = [
    ('TSHIRT', 'T-Shirt', 'Close-fitting top'),
    ('HOODIE', 'Hoodie', 'Loose, thick top'),
    ('PANTS', 'Pants', 'Regular trousers'),
    ('CARGO', 'Cargo', 'Loose trousers'),
]
TYPES = {
    'TSHIRT': dict(fit=0.012, smooth=6, flare=0.15, wrinkles=0.35, wrinkle_size=0.06, thickness=0.004, layer=1),
    'HOODIE': dict(fit=0.03, smooth=10, flare=0.35, wrinkles=0.55, wrinkle_size=0.08, thickness=0.009, layer=1),
    'PANTS': dict(fit=0.014, smooth=6, flare=0.1, wrinkles=0.4, wrinkle_size=0.05, thickness=0.005, layer=0),
    'CARGO': dict(fit=0.028, smooth=9, flare=0.25, wrinkles=0.6, wrinkle_size=0.07, thickness=0.007, layer=0),
}
LIVE_KEYS = ('layer', 'fit', 'smooth', 'flare', 'wrinkles', 'wrinkle_size', 'seed', 'thickness', 'gap')


def relax(coords, neighbours, fixed, passes, factor=0.5):
    """Laplacian smoothing of positions (fixed indices stay)."""
    co = [c.copy() for c in coords]
    for _ in range(passes):
        new = []
        for i, c in enumerate(co):
            nb = neighbours[i]
            if i in fixed or not nb:
                new.append(c)
                continue
            avg = sum((co[j] for j in nb), Vector()) / len(nb)
            new.append(c.lerp(avg, factor))
        co = new
    return co


def source(ob):
    if ob is None:
        return None
    try:
        raw = ob.get(SRC_KEY)
        return json.loads(raw) if raw else None
    except (TypeError, ValueError, ReferenceError):
        return None


def _region(context, src, target):
    """The body surface inside the outline (front and back): bmesh, world space, open at the outline."""
    from . import armor_plate as ap
    projector = ap.thaw_projector(src['proj'])
    groups = cg.prepare_loops([[tuple(q) for q in lp] for lp in src['loops']])
    if not groups:
        raise cg.CutError('The outline is empty.')
    near, far = cg.depth_planes(projector, cg.object_world_bounds([target]), 'THROUGH')
    cutter = cg.link_temp_object(context, cg.build_cutter_mesh(groups, projector, near, far, 'MCH_ClothCut'))
    try:
        me = cg.evaluate_boolean(context, target, cutter, 'INTERSECT', solver='EXACT')
    finally:
        cg.remove_object_and_mesh(cutter)
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
    finally:
        bpy.data.meshes.remove(me)
    bmesh.ops.transform(bm, matrix=target.matrix_world, verts=bm.verts[:])
    layer = bm.faces.layers.bool.get(cg.CUTTER_ATTR) or bm.faces.layers.int.get(cg.CUTTER_ATTR)
    if layer is not None:
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f[layer]], context='FACES')
    if not bm.faces:
        bm.free()
        raise cg.CutError('The outline does not cover the body: draw the garment over it.')
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges[:])
    _clean(bm)
    return bm


def _clean(bm):
    """Drop what a thin garment cannot use: loose bits, edges shared by 3+ faces (their extra faces), tiny faces."""
    bad = [f for f in bm.faces if f.calc_area() < 1e-12]
    for e in bm.edges:
        if len(e.link_faces) > 2:
            bad += list(e.link_faces)[2:]
    if bad:
        bmesh.ops.delete(bm, geom=list(set(bad)), context='FACES')
    loose_e = [e for e in bm.edges if not e.link_faces]
    if loose_e:
        bmesh.ops.delete(bm, geom=loose_e, context='EDGES')
    loose_v = [v for v in bm.verts if not v.link_edges]
    if loose_v:
        bmesh.ops.delete(bm, geom=loose_v, context='VERTS')
    # a vertex where two separate fans touch (bow-tie) would make the shell pinch: split it
    bmesh.ops.split_edges(bm, edges=[e for e in bm.edges if not e.is_manifold and not e.is_boundary])


def shell(bm, thickness):
    """A closed cloth: the surface, an inner copy (toward the body) along smoothed vertex normals, and walls along
    the openings.  Normals are averaged over the faces and smoothed, so a sliver can never throw a spike."""
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bm.normal_update()
    nb = [[e.other_vert(v).index for e in v.link_edges] for v in bm.verts]
    nrm = []
    for v in bm.verts:
        acc = Vector()
        for f in v.link_faces:
            acc += f.normal * f.calc_area()
        nrm.append(acc.normalized() if acc.length > 1e-15 else Vector((0, 0, 1)))
    nrm = relax(nrm, nb, set(), 2)
    nrm = [n.normalized() if n.length > 1e-9 else Vector((0, 0, 1)) for n in nrm]
    out = bmesh.new()
    top = [out.verts.new(v.co) for v in bm.verts]
    bot = [out.verts.new(v.co - nrm[i] * thickness) for i, v in enumerate(bm.verts)]
    for f in bm.faces:
        ids = [v.index for v in f.verts]
        try:
            out.faces.new([top[i] for i in ids])
            out.faces.new([bot[i] for i in reversed(ids)])
        except ValueError:
            pass
    for e in bm.edges:
        if e.is_boundary:
            a, b = e.verts[0].index, e.verts[1].index
            try:
                out.faces.new((top[a], top[b], bot[b], bot[a]))
            except ValueError:
                pass
    bmesh.ops.recalc_face_normals(out, faces=out.faces[:])
    return out


def build(context, src, p, target):
    from . import cape_gen
    bvh, lo, hi = cape_gen._body(context, target)
    size = (hi - lo).length
    bm = _region(context, src, target)
    # even, small faces so it can bend and wrinkle
    edge_len = size * 0.012
    long_edges = [e for e in bm.edges if e.calc_length() > edge_len * 1.6]
    for _ in range(3):
        if not long_edges:
            break
        bmesh.ops.subdivide_edges(bm, edges=long_edges, cuts=1, use_grid_fill=True)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
        long_edges = [e for e in bm.edges if e.calc_length() > edge_len * 1.6]
    bm.verts.ensure_lookup_table()
    bm.normal_update()
    verts = bm.verts
    n = len(verts)
    nbrs = [[e.other_vert(v).index for e in v.link_edges] for v in verts]
    rim = {v.index for v in verts if v.is_boundary}
    nrm = [v.normal.copy() for v in verts]
    nrm = relax(nrm, nbrs, set(), 3)
    nrm = [x.normalized() if x.length > 1e-9 else Vector((0, 0, 1)) for x in nrm]
    gap = (p.gap if p.gap > 0 else size * 0.003) + p.layer * size * 0.008   # a top (layer 1) sits over pants (0)
    fit = p.fit * size
    co = [v.co + nrm[i] * (gap + fit) for i, v in enumerate(verts)]
    # relax: bridges the hollows, then keep it off the body
    keep = gap + fit * 0.35
    for _round in range(max(0, p.smooth) // 2 + 1):
        co = relax(co, nbrs, set(), 2)
        co = [cape_gen._push_out(bvh, c, keep) for c in co]
    # hem flare: the lowest part spreads out (along the horizontal normal)
    zs = [c.z for c in co]
    zlo, zhi = min(zs), max(zs)
    span = max(1e-6, zhi - zlo)
    if p.flare > 0:
        for i, c in enumerate(co):
            w = max(0.0, 1.0 - (c.z - zlo) / (span * 0.35)) ** 2
            hn = Vector((nrm[i].x, nrm[i].y, 0.0))
            if hn.length > 1e-9 and w > 0:
                co[i] = c + hn.normalized() * (w * p.flare * fit * 3.0)
    # wrinkles: more where the surface bends (joints), noise along the normal
    if p.wrinkles > 0:
        bend = []
        for i in range(n):
            nb = nbrs[i]
            bend.append(sum((1.0 - nrm[i].dot(nrm[j])) for j in nb) / max(1, len(nb)))
        top = max(bend) or 1.0
        scale = 1.0 / max(1e-6, p.wrinkle_size * size)
        off = Vector((p.seed * 13.1, p.seed * 7.7, p.seed * 3.3))
        amp = p.wrinkles * size * 0.012
        for i, c in enumerate(co):
            q = (c * scale) + off
            # stretched noise: folds run round the limbs / body more than along them
            q2 = Vector((q.x * 0.6, q.y * 0.6, q.z * 2.2))
            f = noise.noise(q2) + 0.5 * noise.noise(q2 * 2.1)
            weight = 0.35 + 0.65 * min(1.0, 3.0 * bend[i] / top)
            co[i] = c + nrm[i] * (amp * weight * f)
        co = [cape_gen._push_out(bvh, c, gap) for c in co]
    for i, v in enumerate(verts):
        v.co = co[i]
    bm.normal_update()
    # thickness: inner copy toward the body + walls at the openings (closed mesh)
    t = p.thickness * size if p.thickness > 0 else size * 0.004
    out = shell(bm, t)
    bm.free()
    for f in out.faces:
        f.smooth = True
    _ = rim
    return out


def rebuild(context, ob):
    src = source(ob)
    if src is None:
        raise cg.CutError('This garment was applied (no outline kept).')
    target = bpy.data.objects.get(src.get('target', ''))
    if target is None or target.type != 'MESH':
        raise cg.CutError('The body the garment was drawn on is gone.')
    bm = build(context, src, ob.mch_clothing, target)
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
    st = getattr(getattr(context, 'scene', None), 'mch_clothing', None)
    if st is not None:
        _BUSY[0] = True
        try:
            for k in LIVE_KEYS + ('kind',):
                if getattr(st, k) != getattr(self, k):
                    setattr(st, k, getattr(self, k))
        except (AttributeError, TypeError):
            pass
        finally:
            _BUSY[0] = False


def _kind_update(self, context):
    if _BUSY[0]:
        return
    vals = TYPES.get(self.kind)
    if not vals:
        return
    _BUSY[0] = True
    try:
        for k, v in vals.items():
            setattr(self, k, v)
    finally:
        _BUSY[0] = False
    _update(self, context)


class MCH_PG_Clothing(bpy.types.PropertyGroup):
    """Scene.mch_clothing = settings for the next garment; Object.mch_clothing = live garment."""
    kind: EnumProperty(name='Type', items=TYPE_ITEMS, default='TSHIRT', update=_kind_update,
                       description='Fills in the sliders')
    layer: IntProperty(name='Layer', default=1, min=0, max=4, update=_update,
                       description='Stacking order: a higher layer sits further out (a top over pants, a jacket over '
                                   'a shirt)')
    fit: FloatProperty(name='Fit', default=0.012, min=0.0, max=0.15, precision=3, update=_update,
                       description='How loose it is (distance from the body, part of the body size)')
    smooth: IntProperty(name='Smooth', default=6, min=0, max=40, update=_update,
                        description='Bridges the hollows of the body instead of following every muscle')
    flare: FloatProperty(name='Hem Flare', default=0.15, min=0.0, max=2.0, update=_update,
                         description='The lowest part spreads out')
    wrinkles: FloatProperty(name='Wrinkles', default=0.35, min=0.0, max=2.0, update=_update)
    wrinkle_size: FloatProperty(name='Wrinkle Size', default=0.06, min=0.01, max=0.4, update=_update)
    seed: IntProperty(name='Seed', default=1, min=0, update=_update)
    thickness: FloatProperty(name='Thickness', default=0.004, min=0.0, max=0.05, precision=4, update=_update,
                             description='Cloth thickness (part of the body size)')
    gap: FloatProperty(name='Gap', default=0.0, min=0.0, soft_max=0.1, precision=4, unit='LENGTH', update=_update,
                       description='Smallest distance from the body (0 = Auto)')
    live: BoolProperty(default=False, options={'HIDDEN'})
    last_error: StringProperty(default='', options={'HIDDEN', 'SKIP_SAVE'})


def perform(context, loops, projector):
    """Outline drawn over a body -> a live garment.  Returns a report; raises cg.CutError."""
    from . import armor_plate as ap
    from . import cape_gen
    from . import face_extract as fx
    scene = context.scene
    st = scene.mch_clothing
    groups = cg.prepare_loops(loops)
    target = cape_gen.pick_body(context, projector, groups)
    if target is None:
        raise cg.CutError('Draw the garment outline over a body.')
    frozen = ap.freeze_projector(projector)
    if frozen is None:
        raise cg.CutError('This view cannot be saved for the garment.')
    me = bpy.data.meshes.new(target.name + '_' + dict((t[0], t[1]) for t in TYPE_ITEMS)[st.kind].replace('-', ''))
    ob = bpy.data.objects.new(me.name, me)
    fx._parts_collection(context, COLLECTION).objects.link(ob)
    for mat in target.data.materials:
        me.materials.append(mat)
    ob[SRC_KEY] = json.dumps({'loops': [[[float(x), float(y)] for x, y in lp] for lp in loops], 'proj': frozen,
                              'target': target.name})
    p = ob.mch_clothing
    _BUSY[0] = True
    try:
        for k in LIVE_KEYS + ('kind',):
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
    name = dict((t[0], t[1]) for t in TYPE_ITEMS)[p.kind]
    return f'{name} "{ob.name}" on {target.name} ({len(me.polygons)} faces)'


def live_garment(context):
    ob = getattr(context, 'active_object', None)
    if ob is not None and getattr(ob, 'mch_clothing', None) is not None and ob.mch_clothing.live and source(ob):
        return ob
    return None


def apply(ob):
    ob.mch_clothing.live = False
    if SRC_KEY in ob:
        del ob[SRC_KEY]


class MCH_OT_clothing_apply(bpy.types.Operator):
    bl_idname = 'mch.clothing_apply'
    bl_label = 'Apply Garment'
    bl_description = 'The garment becomes a plain mesh (the sliders stop rebuilding it)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return live_garment(context) is not None

    def execute(self, context):
        apply(live_garment(context))
        return {'FINISHED'}


def draw(layout, context):
    ob = live_garment(context)
    p = ob.mch_clothing if ob is not None else context.scene.mch_clothing
    box = layout.box()
    if ob is not None:
        box.label(text='LIVE Garment: ' + ob.name, icon='MATCLOTH')
        if p.last_error:
            box.label(text=p.last_error, icon='ERROR')
    else:
        box.label(text='Clothing: settings for the next one', icon='MATCLOTH')
    box.row(align=True).prop(p, 'kind', expand=True)
    col = box.column(align=True)
    col.prop(p, 'layer')
    col.prop(p, 'fit', slider=True)
    col.prop(p, 'smooth')
    col.prop(p, 'flare', slider=True)
    col = box.column(align=True)
    col.prop(p, 'wrinkles', slider=True)
    col.prop(p, 'wrinkle_size', slider=True)
    col.prop(p, 'seed')
    col = box.column(align=True)
    col.prop(p, 'thickness', slider=True)
    col.prop(p, 'gap')
    if ob is not None:
        box.operator('mch.clothing_apply', icon='CHECKMARK')
    col = layout.column(align=True)
    col.scale_y = 0.8
    for line in ('Front view: draw the garment outline over the body', 'Front and back are both covered',
                 'Openings = where the outline crosses the body', 'Apply: plain mesh'):
        col.label(text=line)


CLASSES = (MCH_PG_Clothing, MCH_OT_clothing_apply)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_clothing = bpy.props.PointerProperty(type=MCH_PG_Clothing)
    bpy.types.Object.mch_clothing = bpy.props.PointerProperty(type=MCH_PG_Clothing)


def unregister():
    for n, t in (('mch_clothing', bpy.types.Object), ('mch_clothing', bpy.types.Scene)):
        try:
            delattr(t, n)
        except AttributeError:
            pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
