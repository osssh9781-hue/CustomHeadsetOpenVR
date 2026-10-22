"""0.24.20 Creature Scales: draw a line over a mesh, a row (or rows) of overlapping scales is laid along it.

Every scale is a Creature Plate Scale (thick root, thin knife edge, the far side lifts) made from one of the
scale stamp shapes (Scale A / B / C, first point = root).  The roots point back along the drawn line, so the
tips overlap the next scale like on a fish or a lizard.

    Presets       tick A / B / C (one, two or all); ticked ones are mixed at random
    Size          length of a scale; Size Random varies it per scale
    Rotate Random a slight random turn per scale
    Spacing       along the line (x Size), Rows across it (staggered), Row Gap
    Height / Tip Lift / Edge Round   the Creature Plate Scale shape; Seed, Flip (roots the other way)

Everything stays live until Apply.  ``placements`` is pure and tested headless.
"""
from __future__ import annotations

import json
import math
import random
import types

import bmesh
import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty, StringProperty
from mathutils import Matrix, Vector

from . import core_geometry as cg

SRC_KEY = 'mch_scales_src'
COLLECTION = 'Creature Scales'
SHAPES = (('A', 'MCH_BUILTIN_SCALE_A'), ('B', 'MCH_BUILTIN_SCALE_B'), ('C', 'MCH_BUILTIN_SCALE_C'))
LIVE_KEYS = ('use_a', 'use_b', 'use_c', 'size', 'size_random', 'rotate_random', 'spacing', 'rows', 'row_gap',
             'height', 'tip_lift', 'edge_round', 'seed', 'flip', 'resolution')
_CACHE = {}


def placements(path_px, step_px, rows, row_gap_px, presets, size_px, size_random, rotate_random, seed, flip=False):
    """[(centre px, angle of the root direction, preset, size px)] along an open screen path - pure."""
    rnd = random.Random(seed)
    if len(path_px) < 2 or not presets:
        return []
    acc = [0.0]
    for a, b in zip(path_px, path_px[1:]):
        acc.append(acc[-1] + math.dist(a, b))
    total = acc[-1]
    if total <= 0:
        return []
    out = []
    step = max(step_px, 1.0)
    count = max(1, int(total / step) + 1)
    for r in range(max(1, rows)):
        off = (r - (rows - 1) / 2.0) * row_gap_px
        shift = 0.5 * step if r % 2 else 0.0                   # staggered rows
        j = 0
        for i in range(count):
            s = i * step + shift
            if s > total:
                break
            while j < len(acc) - 2 and acc[j + 1] < s:
                j += 1
            t = (s - acc[j]) / max(acc[j + 1] - acc[j], 1e-9)
            a, b = path_px[j], path_px[j + 1]
            tx, ty = b[0] - a[0], b[1] - a[1]
            ln = math.hypot(tx, ty) or 1.0
            tx, ty = tx / ln, ty / ln
            cx = a[0] + (b[0] - a[0]) * t - ty * off
            cy = a[1] + (b[1] - a[1]) * t + tx * off
            back = math.atan2(-ty, -tx) if not flip else math.atan2(ty, tx)     # roots point back
            ang = back + rotate_random * (rnd.random() * 2.0 - 1.0)
            kind = presets[rnd.randrange(len(presets))]
            sz = size_px * (1.0 + size_random * (rnd.random() * 2.0 - 1.0))
            out.append(((cx, cy), ang, kind, max(sz, size_px * 0.1)))
    return out


def scale_outline(stem, centre, angle, size):
    """A scale stamp turned so its root points along ``angle``, ``size`` px long, root first."""
    from . import cut_presets
    loop = [tuple(q) for q in cut_presets.load_loops(stem)[0]]
    cx = sum(q[0] for q in loop) / len(loop)
    cy = sum(q[1] for q in loop) / len(loop)
    root = math.atan2(loop[0][1] - cy, loop[0][0] - cx)
    rot = angle - root
    c, s = math.cos(rot), math.sin(rot)
    return [(centre[0] + ((x - cx) * c - (y - cy) * s) * size, centre[1] + ((x - cx) * s + (y - cy) * c) * size)
            for x, y in loop]


def _update(self, context):
    ob = self.id_data
    if not isinstance(ob, bpy.types.Object) or not self.live:
        return
    try:
        rebuild(context, ob)
        self.last_error = ''
    except (cg.CutError, ValueError, RuntimeError) as ex:
        self.last_error = str(ex)
    st = getattr(getattr(context, 'scene', None), 'mch_scales', None)
    if st is not None:
        for k in LIVE_KEYS:
            try:
                if getattr(st, k) != getattr(self, k):
                    setattr(st, k, getattr(self, k))
            except (AttributeError, TypeError):
                pass


def _p(prop, **kw):
    kw.setdefault('update', _update)
    return prop(**kw)


class MCH_PG_Scales(bpy.types.PropertyGroup):
    use_a: _p(BoolProperty, name='Scale A', default=True, description='Wide scale')
    use_b: _p(BoolProperty, name='Scale B', default=True, description='Round scale')
    use_c: _p(BoolProperty, name='Scale C', default=True, description='Pear scale')
    size: _p(FloatProperty, name='Size', default=0.3, min=0.001, soft_max=5.0, precision=3, unit='LENGTH',
             description='Length of a scale')
    size_random: _p(FloatProperty, name='Size Random', default=0.2, min=0.0, max=0.9, subtype='FACTOR')
    rotate_random: _p(FloatProperty, name='Rotate Random', default=math.radians(10), min=0.0,
                      max=math.radians(90), subtype='ANGLE')
    spacing: _p(FloatProperty, name='Spacing', default=0.7, min=0.15, soft_max=3.0,
                description='Distance between scales along the line (x Size; below 1 = overlapping)')
    rows: _p(IntProperty, name='Rows', default=1, min=1, max=12, description='Rows of scales across the line')
    row_gap: _p(FloatProperty, name='Row Gap', default=0.75, min=0.1, soft_max=3.0, description='x Size')
    height: _p(FloatProperty, name='Height', default=1.0, min=0.05, soft_max=4.0,
               description='Thickness of the scales (1 = Auto)')
    tip_lift: _p(FloatProperty, name='Tip Lift', default=1.0, min=0.0, soft_max=4.0,
                 description='How far the tips rise off the body (x thickness)')
    edge_round: _p(FloatProperty, name='Edge Round', default=0.2, min=0.0, max=1.0)
    resolution: _p(IntProperty, name='Resolution', default=16, min=6, max=40)
    seed: _p(IntProperty, name='Seed', default=1, min=0)
    flip: _p(BoolProperty, name='Flip', default=False, description='Roots point forward instead of back')
    live: BoolProperty(default=False, options={'HIDDEN'})
    last_error: StringProperty(default='', options={'HIDDEN', 'SKIP_SAVE'})


def enabled(p):
    return [stem for k, stem in SHAPES if getattr(p, 'use_' + k.lower())]


def source(ob):
    if ob is None:
        return None
    try:
        raw = ob.get(SRC_KEY)
        return json.loads(raw) if raw else None
    except (TypeError, ValueError, ReferenceError):
        return None


def _world_per_px(context, target, projector, path):
    from . import belt_maker as bmk
    pts, _c = bmk._follow_path(context, target, projector, path)
    wl = sum((b - a).length for a, b in zip(pts, pts[1:]))
    pl = sum(math.dist(a, b) for a, b in zip(path, path[1:]))
    return wl / max(pl, 1e-9)


def build(context, ob):
    from . import armor_plate as ap
    from . import base_mesh as bmm
    from . import creature_plate as cpl
    src = source(ob)
    if src is None:
        raise cg.CutError('These scales were applied.')
    p = ob.mch_scales
    stems = enabled(p)
    if not stems:
        raise cg.CutError('Tick at least one scale preset.')
    target = bpy.data.objects.get(src.get('target', ''))
    if target is None or target.type != 'MESH':
        raise cg.CutError('The mesh the scales were drawn on is gone.')
    projector = ap.thaw_projector(src['proj'])
    path = [tuple(q) for q in src['path']]
    hit = _CACHE.get(ob.name)
    if hit is None or hit[0] != src.get('stamp'):
        hit = (src.get('stamp'), _world_per_px(context, target, projector, path), ap._target_bvh(context, target)[0])
        _CACHE[ob.name] = hit
    wpp, bvh = hit[1], hit[2]
    size_px = p.size / max(wpp, 1e-9)
    field_p = types.SimpleNamespace(profile='SCALE', resolution=p.resolution, outline_smooth=0.3,
                                    edge_round=p.edge_round, puff=1.0)
    plate_p = types.SimpleNamespace(profile='SCALE', direction=0.0, edge_thickness=0.0, sink=0.0, tip_lift=-1.0)
    verts, faces = [], []
    for centre, ang, stem, sz in placements(path, p.spacing * size_px, p.rows, p.row_gap * size_px, stems,
                                            size_px, p.size_random, p.rotate_random, p.seed, p.flip):
        outline = scale_outline(stem, centre, ang, sz)
        try:
            _b, pts, tris, nb, shape, natural_px, _sp = bmm.profile_field(outline, [], field_p)
            cos, nrms, _miss = ap.project_patch(pts, projector, bvh)
        except cg.CutError:
            continue                                   # a scale off the mesh: skip it
        nrms = cpl._smooth_normals(nrms, tris)
        peak = natural_px * wpp * 0.5 * p.height
        plate_p.tip_lift = 1.5 * peak * p.tip_lift
        part = dict(pts=pts, tris=tris, nb=nb, cos=cos, nrms=nrms, shape=shape, start=outline[0])
        bm = cpl.build_mesh([part], plate_p, peak, peak * 0.15)
        try:
            off = len(verts)
            verts += [v.co.copy() for v in bm.verts]
            bm.verts.index_update()
            faces += [tuple(off + v.index for v in f.verts) for f in bm.faces]
        finally:
            bm.free()
    if not verts:
        raise cg.CutError('No scale landed on the mesh (draw over it, or lower Size).')
    return verts, faces


def rebuild(context, ob):
    verts, faces = build(context, ob)
    inv = ob.matrix_world.inverted_safe()
    me = ob.data
    me.clear_geometry()
    me.from_pydata([tuple(inv @ v) for v in verts], [], faces)
    for poly in me.polygons:
        poly.use_smooth = True
    try:
        me.set_sharp_from_angle(angle=math.radians(60))
    except (AttributeError, TypeError, RuntimeError):
        pass
    me.update()


def perform(context, path, projector):
    from . import armor_plate as ap
    from . import belt_maker as bmk
    from . import face_extract as fx
    path = [tuple(q) for q in path]
    if len(path) < 2:
        raise cg.CutError('Scales: draw a line (at least 2 points).')
    target = bmk.pick_target(context, projector, path)
    if target is None:
        raise cg.CutError('Scales: draw the line over a mesh.')
    frozen = ap.freeze_projector(projector)
    if frozen is None:
        raise cg.CutError('This view cannot be saved for the scales.')
    st = context.scene.mch_scales
    me = bpy.data.meshes.new(target.name + '_Scales')
    ob = bpy.data.objects.new(me.name, me)
    fx._parts_collection(context, COLLECTION).objects.link(ob)
    for mat in target.data.materials:
        me.materials.append(mat)
    ob[SRC_KEY] = json.dumps({'path': [[float(x), float(y)] for x, y in path], 'proj': frozen,
                              'target': target.name, 'stamp': id(ob) % 100000})
    p = ob.mch_scales
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
    st.seed += 1
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    return f'Scales "{ob.name}" on {target.name}'


def live_scales(context):
    ob = getattr(context, 'active_object', None)
    if ob is not None and getattr(ob, 'mch_scales', None) is not None and ob.mch_scales.live and source(ob):
        return ob
    return None


class MCH_OT_scales_apply(bpy.types.Operator):
    bl_idname = 'mch.scales_apply'
    bl_label = 'Apply Scales'
    bl_description = 'The scales become a plain mesh (the sliders stop rebuilding them)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return live_scales(context) is not None

    def execute(self, context):
        ob = live_scales(context)
        ob.mch_scales.live = False
        del ob[SRC_KEY]
        _CACHE.pop(ob.name, None)
        self.report({'INFO'}, f'{ob.name}: applied')
        return {'FINISHED'}


def draw(layout, context):
    ob = live_scales(context)
    p = ob.mch_scales if ob is not None else context.scene.mch_scales
    if ob is not None:
        box = layout.box()
        box.label(text='LIVE: ' + ob.name, icon='SHARPCURVE')
        if p.last_error:
            box.label(text=p.last_error, icon='ERROR')
        target = box
    else:
        layout.label(text='Settings for the next row of scales', icon='SHARPCURVE')
        target = layout
    target.label(text='Presets (ticked ones are mixed at random):')
    row = target.row(align=True)
    for attr in ('use_a', 'use_b', 'use_c'):
        row.prop(p, attr, toggle=True)
    col = target.column(align=True)
    col.prop(p, 'size')
    col.prop(p, 'size_random', slider=True)
    col.prop(p, 'rotate_random')
    col = target.column(align=True)
    col.prop(p, 'spacing')
    col.prop(p, 'rows')
    if p.rows > 1:
        col.prop(p, 'row_gap')
    col = target.column(align=True)
    col.prop(p, 'height')
    col.prop(p, 'tip_lift')
    col.prop(p, 'edge_round', slider=True)
    col.prop(p, 'resolution')
    row = target.row(align=True)
    row.prop(p, 'seed')
    row.prop(p, 'flip', toggle=True)
    if ob is not None:
        target.operator('mch.scales_apply', icon='CHECKMARK')
    col = layout.column(align=True)
    col.scale_y = 0.8
    for line in ('Draw a line over a mesh, Enter: scales along it',
                 'Roots point back along the line, tips overlap the next', 'Seed: another mix, Apply: plain mesh'):
        col.label(text=line)


CLASSES = (MCH_PG_Scales, MCH_OT_scales_apply)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_scales = bpy.props.PointerProperty(type=MCH_PG_Scales)
    bpy.types.Object.mch_scales = bpy.props.PointerProperty(type=MCH_PG_Scales)


def unregister():
    for n, t in (('mch_scales', bpy.types.Object), ('mch_scales', bpy.types.Scene)):
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
