"""0.24.20 Flower Plate: draw an outline on a mesh, that shape grows from it and bends away (creature parts,
fins, petals, leaves).

The outline keeps the shape you drew.  Only the part near the START of the outline (the first point drawn) stays
on the surface; the rest lifts off and bends:

    Lift        how steeply it rises off the surface right after the attached part
    Curl        extra bend from there to the tip: + = curls up and back over the root, - = bends outward / droops
    Curl Power  1 = even bend, above 1 = straight first and curling at the tip, below 1 = bending at once
    Side Bend   sweeps the far end to the left / right
    Roll        rolls the sides up (+) or down (-) across the width, like a half pipe
    Attach      how much of the length stays on the surface
    Thickness   sheet thickness at the root (0 = Auto), Tip Thin = how much thinner the tip is
    Edge Round  the rim is thinner than the middle

The sheet is the outline filled with the Creature point set (``base_mesh.profile_field``) projected onto the
mesh (like Creature Plate), then laid along a bent centre line in the frame at the root: U = from the root
across the shape, W = sideways, N = the surface normal there.  Live until Apply.  ``spine`` is pure and tested
headless.
"""
from __future__ import annotations

import json
import math
import types

import bmesh
import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty, StringProperty
from mathutils import Matrix, Vector

from . import core_geometry as cg

SRC_KEY = 'mch_flower_src'
COLLECTION = 'Flower Plates'
LIVE_KEYS = ('lift', 'curl', 'curl_power', 'side_bend', 'roll', 'attach', 'thickness', 'tip_thin', 'edge_round', 'outline_smooth',
             'resolution', 'sink', 'tip_sharp')
_CACHE = {}


def spine(span, lift, curl, power=1.0, side=0.0, steps=160):
    """The bent centre line in the root frame (u, w, n): [(position, tangent, side, normal)] at ``steps`` + 1
    even stations over ``span``.  Pitch = Lift (eased in over the first third) + Curl * t ** power, yaw = Side
    Bend * t ** power.  Pure."""
    def frame(t):
        a = lift * _ease(min(1.0, t / 0.35)) + curl * (t ** power)
        b = side * (t ** power)
        tan = Vector((math.cos(a) * math.cos(b), math.cos(a) * math.sin(b), math.sin(a)))
        sd = Vector((-math.sin(b), math.cos(b), 0.0))
        return tan, sd, tan.cross(sd).normalized()
    ds = span / steps
    pos = Vector()
    out = [(pos.copy(),) + frame(0.0)]
    for k in range(steps):
        pos += frame((k + 0.5) / steps)[0] * ds
        out.append((pos.copy(),) + frame((k + 1) / steps))
    return out


def _ease(x):
    return x * x * (3.0 - 2.0 * x)


def _update(self, context):
    ob = self.id_data
    if not isinstance(ob, bpy.types.Object) or not self.live:
        return
    try:
        rebuild(context, ob)
        self.last_error = ''
    except (cg.CutError, ValueError, RuntimeError) as ex:
        self.last_error = str(ex)
    st = getattr(getattr(context, 'scene', None), 'mch_flower', None)
    if st is not None:
        for k in LIVE_KEYS:
            if k == 'thickness':
                continue
            try:
                if getattr(st, k) != getattr(self, k):
                    setattr(st, k, getattr(self, k))
            except (AttributeError, TypeError):
                pass


def _p(prop, **kw):
    kw.setdefault('update', _update)
    return prop(**kw)


class MCH_PG_Flower(bpy.types.PropertyGroup):
    lift: _p(FloatProperty, name='Lift', default=math.radians(55), min=math.radians(-30), max=math.radians(120),
             subtype='ANGLE', description='How steeply it rises off the surface after the attached part')
    curl: _p(FloatProperty, name='Curl', default=math.radians(-120), min=math.radians(-300), max=math.radians(300),
             subtype='ANGLE', description='Bend from there to the tip: + curls up and back over, - bends outward')
    side_bend: _p(FloatProperty, name='Side Bend', default=0.0, min=math.radians(-180), max=math.radians(180),
                  subtype='ANGLE', description='Sweep the far end to the left / right')
    roll: _p(FloatProperty, name='Roll', default=0.0, min=math.radians(-180), max=math.radians(180),
             subtype='ANGLE', description='Roll the sides up (+) or down (-) across the width')
    curl_power: _p(FloatProperty, name='Curl Power', default=1.3, min=0.3, max=4.0,
                   description='1 = even bend; higher = straight first, curling at the tip; lower = bends at once')
    attach: _p(FloatProperty, name='Attach', default=0.15, min=0.0, max=0.9, subtype='FACTOR',
               description='How much of the length stays on the surface (from the start of the outline)')
    thickness: _p(FloatProperty, name='Thickness', default=0.0, min=0.0, soft_max=0.5, precision=4, unit='LENGTH',
                  description='Sheet thickness at the root (0 = Auto: 4% of the length)')
    tip_thin: _p(FloatProperty, name='Tip Thin', default=0.4, min=0.0, max=0.95, subtype='FACTOR',
                 description='How much thinner the tip is than the root')
    edge_round: _p(FloatProperty, name='Edge Round', default=0.25, min=0.0, max=1.0,
                   description='Thinner rim, fuller middle')
    outline_smooth: _p(FloatProperty, name='Soft Outline', default=0.5, min=0.0, max=1.0)
    resolution: _p(IntProperty, name='Resolution', default=24, min=6, max=64)
    sink: _p(FloatProperty, name='Sink', default=1.2, min=0.0, max=4.0,
             description='How far the root goes into the surface (x Thickness)')
    tip_sharp: _p(FloatProperty, name='Tip Sharp', default=0.0, min=0.0, max=0.95, subtype='FACTOR',
                  description='Narrow the far end to a point (0 = exactly the shape you drew)')
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


def _field(context, ob, src, p):
    """Cached: points on the surface (cos, nrms), triangles, outline count, rim shape, start index."""
    key = (src.get('stamp'), p.resolution, round(p.outline_smooth, 4), round(p.edge_round, 4))
    hit = _CACHE.get(ob.name)
    if hit is not None and hit[0] == key:
        return hit[1]
    from . import armor_plate as ap
    from . import base_mesh as bmm
    from . import creature_plate as cpl
    target = bpy.data.objects.get(src.get('target', ''))
    if target is None or target.type != 'MESH':
        raise cg.CutError('The mesh the part was drawn on is gone.')
    projector = ap.thaw_projector(src['proj'])
    groups = cg.prepare_loops([[tuple(q) for q in lp] for lp in src['loops']])
    outer, holes = groups[0]
    fp = types.SimpleNamespace(profile='PILLOW', resolution=p.resolution, outline_smooth=p.outline_smooth,
                               edge_round=max(p.edge_round, 0.02), puff=1.0)
    _b, pts, tris, nb, shape, _nat, _sp = bmm.profile_field(outer, holes, fp)
    bvh = ap._target_bvh(context, target)[0]
    cos, nrms, _miss = ap.project_patch(pts, projector, bvh)
    nrms = cpl._smooth_normals(nrms, tris)
    start = tuple(src['loops'][0][0])
    root = min(range(len(pts)), key=lambda i: math.dist(pts[i], start))
    data = (cos, nrms, tris, nb, shape, root)
    _CACHE[ob.name] = (key, data)
    return data


def build(context, ob):
    src = source(ob)
    if src is None:
        raise cg.CutError('This part was applied.')
    p = ob.mch_flower
    cos, nrms, tris, nb, shape, root = _field(context, ob, src, p)
    r0, n0 = cos[root], nrms[root].normalized()
    cen = sum(cos, Vector()) / len(cos)
    U = (cen - r0) - n0 * (cen - r0).dot(n0)
    U = U.normalized() if U.length > 1e-9 else Vector((1, 0, 0))
    W = n0.cross(U).normalized()
    us = [(c - r0).dot(U) for c in cos]
    ws = [(c - r0).dot(W) for c in cos]
    length = max(max(us), 1e-9)
    a0 = p.attach * length
    span = max(length - a0, 1e-9)
    thick0 = p.thickness if p.thickness > 0 else 0.04 * length
    dive = thick0 * p.sink                             # the root sits this deep in the surface
    steps = 160
    line = spine(span, p.lift, p.curl, p.curl_power, p.side_bend, steps)
    basis = Matrix((U, W, n0)).transposed()            # root frame (u, w, n) -> world
    base0 = r0 + U * a0
    half = max(max(abs(w) for w in ws), 1e-9)
    verts_top, verts_bot = [], []
    for i, c in enumerate(cos):
        s = max(us[i] - a0, 0.0)
        frac = min(max(us[i], 0.0) / length, 1.0)
        th = thick0 * (1.0 - p.tip_thin * frac) * (0.35 + 0.65 * shape[i])
        if s <= 0.0:
            n = nrms[i]
            top = c + n * (th - dive * 0.5)
            bot = c - n * dive
        else:
            x = min(s / span, 1.0) * steps
            k = min(int(x), steps - 1)
            f = x - k
            (p0, t0, s0, n0_), (p1, t1, s1, n1_) = line[k], line[k + 1]
            pos_l = p0.lerp(p1, f)
            sd = s0.lerp(s1, f).normalized()
            nl = n0_.lerp(n1_, f).normalized()
            w = ws[i] * (1.0 - p.tip_sharp * frac ** 2.5)          # 0 = the drawn shape
            rl = p.roll * _ease(min(1.0, s / (0.3 * span)))
            if abs(rl) > 1e-4:
                r = half / rl
                th_ = w / r
                pos_l = pos_l + sd * (r * math.sin(th_)) + nl * (r * (1.0 - math.cos(th_)))
                nl = (nl * math.cos(th_) - sd * math.sin(th_)).normalized()
            else:
                pos_l = pos_l + sd * w
            pos = base0 + basis @ pos_l
            nb_ = (basis @ nl).normalized()
            blend = _ease(min(1.0, s / (0.12 * span)))   # leave the surface smoothly
            pos = c.lerp(pos, blend)
            n = nrms[i].lerp(nb_, blend).normalized()
            top = pos + n * (th - dive * 0.5 * (1.0 - blend))
            bot = pos - n * dive * (1.0 - blend)
        verts_top.append(top)
        verts_bot.append(bot)
    verts = verts_top + verts_bot
    m = len(cos)
    faces = []
    for a, b, c in tris:
        faces.append((a, b, c))
        faces.append((m + c, m + b, m + a))
    rim = set()
    for a, b, c in tris:
        for u_, v_ in ((a, b), (b, c), (c, a)):
            if u_ < nb and v_ < nb:
                rim.add((u_, v_))
    for u_, v_ in rim:
        if (v_, u_) not in rim:
            faces.append((v_, u_, m + u_, m + v_))
    return verts, faces


def rebuild(context, ob):
    verts, faces = build(context, ob)
    inv = ob.matrix_world.inverted_safe()
    me = ob.data
    me.clear_geometry()
    me.from_pydata([tuple(inv @ v) for v in verts], [], faces)
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        for f in bm.faces:
            f.smooth = True
        bm.to_mesh(me)
        from . import edge_memory as _em; _em.mark_generated(me)   # 0.24.95 Edge Memory: the part's own lines
    finally:
        bm.free()
    try:
        me.set_sharp_from_angle(angle=math.radians(60))
    except (AttributeError, TypeError, RuntimeError):
        pass
    me.update()


def perform(context, loops, projector):
    """Lasso -> a live Flower Plate (petal) on the mesh under it.  Returns a report; raises cg.CutError."""
    from . import armor_plate as ap
    from . import face_extract as fx
    groups = cg.prepare_loops(loops)
    target = ap.pick_surface(context, projector, groups)
    if target is None:
        raise cg.CutError('Draw the part over a mesh.')
    frozen = ap.freeze_projector(projector)
    if frozen is None:
        raise cg.CutError('This view cannot be saved for the part.')
    st = context.scene.mch_flower
    me = bpy.data.meshes.new(target.name + '_Petal')
    ob = bpy.data.objects.new(me.name, me)
    fx._parts_collection(context, COLLECTION).objects.link(ob)
    for mat in target.data.materials:
        me.materials.append(mat)
    ob[SRC_KEY] = json.dumps({'loops': [[[float(x), float(y)] for x, y in lp] for lp in loops], 'proj': frozen,
                              'target': target.name, 'stamp': id(ob) % 100000})
    p = ob.mch_flower
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
    return f'Flower plate "{ob.name}" on {target.name} (curl {math.degrees(p.curl):.0f} deg)'


def live_flower(context):
    ob = getattr(context, 'active_object', None)
    if ob is not None and getattr(ob, 'mch_flower', None) is not None and ob.mch_flower.live and source(ob):
        return ob
    return None


class MCH_OT_flower_apply(bpy.types.Operator):
    bl_idname = 'mch.flower_apply'
    bl_label = 'Apply Flower Plate'
    bl_description = 'The part becomes a plain mesh (the sliders stop rebuilding it)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return live_flower(context) is not None

    def execute(self, context):
        ob = live_flower(context)
        ob.mch_flower.live = False
        del ob[SRC_KEY]
        _CACHE.pop(ob.name, None)
        self.report({'INFO'}, f'{ob.name}: applied')
        return {'FINISHED'}


def draw(layout, context):
    ob = live_flower(context)
    p = ob.mch_flower if ob is not None else context.scene.mch_flower
    if ob is not None:
        box = layout.box()
        box.label(text='LIVE: ' + ob.name, icon='OUTLINER_OB_FORCE_FIELD')
        if p.last_error:
            box.label(text=p.last_error, icon='ERROR')
        target = box
    else:
        layout.label(text='Settings for the next part', icon='OUTLINER_OB_FORCE_FIELD')
        target = layout
    col = target.column(align=True)
    col.prop(p, 'lift')
    col.prop(p, 'curl')
    col.prop(p, 'curl_power')
    col.prop(p, 'side_bend')
    col.prop(p, 'roll')
    col.prop(p, 'attach', slider=True)
    col = target.column(align=True)
    col.prop(p, 'thickness')
    col.prop(p, 'tip_thin', slider=True)
    col.prop(p, 'tip_sharp', slider=True)
    col.prop(p, 'edge_round', slider=True)
    col.prop(p, 'sink')
    col = target.column(align=True)
    col.prop(p, 'outline_smooth', slider=True)
    col.prop(p, 'resolution')
    if ob is not None:
        target.operator('mch.flower_apply', icon='CHECKMARK')
    col = layout.column(align=True)
    col.scale_y = 0.8
    for line in ('Draw an outline on a mesh: where you START stays on it,',
                 'the rest lifts off (Lift) and bends: Curl + back over, - outward',
                 'Apply: plain mesh'):
        col.label(text=line)


CLASSES = (MCH_PG_Flower, MCH_OT_flower_apply)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_flower = bpy.props.PointerProperty(type=MCH_PG_Flower)
    bpy.types.Object.mch_flower = bpy.props.PointerProperty(type=MCH_PG_Flower)


def unregister():
    for n, t in (('mch_flower', bpy.types.Object), ('mch_flower', bpy.types.Scene)):
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
