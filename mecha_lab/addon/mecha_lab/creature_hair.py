"""0.24.29 Creature Hair: draw an area on a head (the scalp) -> live dreadlocks / tentacles / quills / strands.

Roots are spread evenly inside the drawn area (on the surface, through the view).  Every strand starts along the
surface normal (Lift), bends down under Gravity, wanders a little (Wave) and never goes into the body (it slides
over the shoulders and down the back like the cape does).  Each strand is a closed tube: rope ridges twisting round
it (Rope), thinner toward the tip (Taper), and Rings - metal bands / beads at random places (material slot 2, so
they can get their own colour).

Styles fill in the sliders: Dreads (Predator: thick roped dreads with bands), Tentacles (thick, smooth, tapering,
curling), Quills (stiff spikes, little gravity), Strands (many thin hairs).  ``root_points``, ``strand_path`` and
``tube_radius`` are pure-ish and tested headless.
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

SRC_KEY = 'mch_hair_src'
COLLECTION = 'Creature Hair'
STYLE_ITEMS = [
    ('DREADS', 'Dreads', 'Predator dreadlocks: thick roped strands with metal bands'),
    ('TENTACLE', 'Tentacles', 'Thick smooth tentacles, tapering and curling'),
    ('QUILLS', 'Quills', 'Stiff spikes standing out'),
    ('STRANDS', 'Strands', 'Many thin hairs'),
]
STYLES = {
    'DREADS': dict(count=34, length=0.55, length_random=0.3, radius=0.022, radius_random=0.2, taper=0.35, lift=0.55,
                   gravity=1.0, wave=0.15, straight=0.7, rope=0.18, rope_twist=6.0, rings=2, ring_size=1.35),
    'TENTACLE': dict(count=10, length=0.5, length_random=0.35, radius=0.05, radius_random=0.25, taper=0.9, lift=0.8,
                     gravity=0.55, wave=0.45, straight=0.2, rope=0.0, rope_twist=0.0, rings=0, ring_size=1.3),
    'QUILLS': dict(count=40, length=0.3, length_random=0.4, radius=0.014, radius_random=0.3, taper=1.0, lift=1.0,
                   gravity=0.08, wave=0.05, straight=0.0, rope=0.0, rope_twist=0.0, rings=0, ring_size=1.3),
    'STRANDS': dict(count=120, length=0.5, length_random=0.25, radius=0.006, radius_random=0.3, taper=0.6, lift=0.4,
                    gravity=1.2, wave=0.25, straight=0.7, rope=0.0, rope_twist=0.0, rings=0, ring_size=1.3),
}
LIVE_KEYS = ('count', 'length', 'length_random', 'radius', 'radius_random', 'taper', 'lift', 'gravity', 'wave',
             'straight', 'rope',
             'rope_twist', 'rings', 'ring_size', 'seed', 'gap', 'sides', 'segments')


# -----------------------------------------------------------------------------
# Pure helpers
# -----------------------------------------------------------------------------


def _inside(pt, poly):
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if (a[1] > y) != (b[1] > y):
            if x < a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]):
                inside = not inside
    return inside


def root_points(poly, count, seed):
    """About ``count`` points spread evenly inside the outline (jittered grid), screen pixels."""
    xs = [q[0] for q in poly]
    ys = [q[1] for q in poly]
    lo_x, hi_x, lo_y, hi_y = min(xs), max(xs), min(ys), max(ys)
    area = abs(0.5 * sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1])))
    if area < 1.0 or count <= 0:
        return []
    step = math.sqrt(area / count)
    rng = random.Random(seed)
    out = []
    y = lo_y + step * 0.5
    row = 0
    while y < hi_y:
        x = lo_x + step * (0.25 if row % 2 else 0.75)
        while x < hi_x:
            q = (x + rng.uniform(-0.35, 0.35) * step, y + rng.uniform(-0.35, 0.35) * step)
            if _inside(q, poly):
                out.append(q)
            x += step
        y += step * 0.866
        row += 1
    return out


def tube_radius(t, theta, r0, taper, rope, twist, length):
    """Radius of a strand at t (0 root .. 1 tip) and angle theta: taper + rope ridges twisting round it."""
    r = r0 * max(0.04, 1.0 - taper * t ** 1.3)
    if rope > 0:
        r *= 1.0 + rope * math.sin(3.0 * theta + twist * t * length / max(r0, 1e-9) * 0.25)
    return r


def strand_path(root, normal, length, segments, lift, gravity, wave, rng, push=None, outward=None, straight=0.0):
    """Points of one strand: starts along the normal (Lift), bends down (Gravity), wanders (Wave); ``push`` keeps
    it out of the body.  ``outward`` (horizontal) is where a strand standing straight up falls to.  ``straight``
    (0.24.29, 0..1): once it has turned over it hangs plumb - the turn speeds up and the sideways drift / wave fade."""
    down = Vector((0.0, 0.0, -1.0))
    n = normal.normalized()
    v = (n * max(0.05, lift) + down * (1.0 - lift) * 0.3)
    if v.length < 1e-9:
        v = n.copy()
    v.normalize()
    step = length / segments
    p = root.copy()
    pts = [p.copy()]
    wdir = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.3, 0.3)))
    side = outward if outward is not None and outward.length > 1e-9 else Vector((wdir.x, wdir.y, 0.0))
    if side.length < 1e-9:
        side = Vector((1.0, 0.0, 0.0))
    turn = gravity * 0.18 * 28.0 / max(4, segments)     # radians per step toward down (the same over any length)
    for k in range(segments):
        t = (k + 1) / segments
        # 0.24.29 gravity turns the strand toward down by an angle (adding a down vector did nothing to a strand
        # pointing straight up)
        axis = v.cross(down)
        if axis.length < 1e-6:
            axis = v.cross(side)
        falling = v.dot(down) > 0.0                 # past the top of its arc
        if axis.length > 1e-9:
            ang = min(v.angle(down, 0.0), turn * (1.0 + 3.0 * straight if falling else 1.0))
            v = Matrix.Rotation(ang, 3, axis.normalized()) @ v
        if falling and straight > 0:
            v = Vector((v.x * (1.0 - 0.6 * straight), v.y * (1.0 - 0.6 * straight), v.z))   # less sideways drift
        v = v + wdir * (wave * (1.0 - 0.8 * straight) * 0.12 * math.sin(t * 6.0 + rng.random()))
        if v.length < 1e-9:
            v = down.copy()
        v.normalize()
        p = p + v * step
        if push is not None:
            q = push(p)
            if (q - p).length > 1e-9:
                # slide along the body: keep going in the pushed direction
                v = (v + (q - p).normalized() * 0.5).normalized()
                p = q
        pts.append(p.copy())
    return pts


# -----------------------------------------------------------------------------
# Mesh
# -----------------------------------------------------------------------------


def _frames(pts):
    """Parallel-transport frames (tangent, normal, binormal) along a path."""
    tans = []
    for i in range(len(pts)):
        a = pts[max(i - 1, 0)]
        b = pts[min(i + 1, len(pts) - 1)]
        d = b - a
        tans.append(d.normalized() if d.length > 1e-12 else Vector((0, 0, 1)))
    ref = Vector((0, 0, 1)) if abs(tans[0].z) < 0.9 else Vector((1, 0, 0))
    nrm = tans[0].cross(ref).normalized()
    out = []
    for i, t in enumerate(tans):
        if i > 0:
            prev = tans[i - 1]
            axis = prev.cross(t)
            if axis.length > 1e-9:
                ang = prev.angle(t)
                nrm = (Matrix.Rotation(ang, 3, axis.normalized()) @ nrm)
            nrm = (nrm - t * nrm.dot(t)).normalized()
        out.append((t, nrm, t.cross(nrm)))
    return out


def add_tube(bm, pts, r0, p, length, sides, mat=0, radius_fn=None):
    """Closed tube along pts (flat root cap, pointed tip)."""
    fr = _frames(pts)
    rings = []
    m = len(pts)
    for i, (q, (t, nv, bv)) in enumerate(zip(pts, fr)):
        tt = i / max(1, m - 1)
        ring = []
        for s in range(sides):
            th = 2 * math.pi * s / sides
            r = radius_fn(tt, th) if radius_fn else tube_radius(tt, th, r0, p.taper, p.rope, p.rope_twist, length)
            ring.append(bm.verts.new(q + (nv * math.cos(th) + bv * math.sin(th)) * r))
        rings.append(ring)
    faces = []
    for i in range(m - 1):
        a, b = rings[i], rings[i + 1]
        for s in range(sides):
            s2 = (s + 1) % sides
            faces.append(bm.faces.new((a[s], a[s2], b[s2], b[s])))
    faces.append(bm.faces.new(rings[0][::-1]))
    tip = bm.verts.new(pts[-1] + fr[-1][0] * (r0 * 0.3))
    for s in range(sides):
        faces.append(bm.faces.new((rings[-1][s], rings[-1][(s + 1) % sides], tip)))
    for f in faces:
        f.material_index = mat
        f.smooth = True
    return faces


def add_ring(bm, pts, at, r, width, sides):
    """A metal band round the strand at fraction ``at`` of its length (its own closed short tube)."""
    m = len(pts)
    i = min(m - 2, max(0, int(at * (m - 1))))
    centre = pts[i].lerp(pts[i + 1], at * (m - 1) - i)
    d = (pts[i + 1] - pts[i])
    if d.length < 1e-12:
        return
    d.normalize()
    seg = [centre - d * width * 0.5, centre, centre + d * width * 0.5]
    add_tube(bm, seg, r, None, 1.0, sides, mat=1,
             radius_fn=lambda tt, th: r * (0.92 if tt in (0.0, 1.0) else 1.0))


# -----------------------------------------------------------------------------
# Build / live object
# -----------------------------------------------------------------------------


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
    projector = ap.thaw_projector(src['proj'])
    bvh, lo, hi = cape_gen._body(context, target)
    groups = cg.prepare_loops([[tuple(q) for q in lp] for lp in src['loops']])
    if not groups:
        raise cg.CutError('The outline is empty.')
    outer = groups[0][0]
    roots2d = root_points(outer, p.count, p.seed)
    if not roots2d:
        raise cg.CutError('Draw a bigger area for the hair.')
    cos, nrms, missing = ap.project_patch(roots2d, projector, bvh)
    size = (hi - lo).length
    miss = set(missing)
    gap = p.gap if p.gap > 0 else size * 0.004
    rng = random.Random(p.seed * 7 + 1)
    good = [c for i, c in enumerate(cos) if i not in miss]
    mid = sum(good, Vector()) / max(1, len(good))
    bm = bmesh.new()
    sides = max(3, p.sides)
    segs = max(3, p.segments)
    for i, (c, n) in enumerate(zip(cos, nrms)):
        if i in miss:
            continue                         # off the head: no strand there
        L = p.length * size * (1.0 + p.length_random * rng.uniform(-1, 1))
        r0 = p.radius * size * (1.0 + p.radius_random * rng.uniform(-1, 1))
        if L <= r0 or r0 <= 0:
            continue
        keep = r0 * (max(1.0, p.ring_size) if p.rings else 1.0) + gap     # the rings are fatter than the strand

        def push(q, keep=keep):
            return cape_gen._push_out(bvh, q, keep)
        out = Vector((n.x, n.y, 0.0))
        if out.length < 0.2:                 # on top of the head: fall away from the middle of the area
            out = Vector((c.x - mid.x, c.y - mid.y, 0.0))
        pts = strand_path(c + n * (r0 * 0.3), n, L, segs, p.lift, p.gravity, p.wave, rng, push, out, p.straight)
        add_tube(bm, pts, r0, p, L, sides)
        for _k in range(p.rings):
            at = rng.uniform(0.12, 0.8)
            add_ring(bm, pts, at, r0 * p.ring_size * max(0.1, 1.0 - p.taper * at ** 1.3), r0 * rng.uniform(1.2, 2.4),
                     sides + 2)
    if not bm.faces:
        bm.free()
        raise cg.CutError('No hair could grow there (draw on the head).')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def rebuild(context, ob):
    src = source(ob)
    if src is None:
        raise cg.CutError('This hair was applied (no outline kept).')
    target = bpy.data.objects.get(src.get('target', ''))
    if target is None or target.type != 'MESH':
        raise cg.CutError('The head the hair was drawn on is gone.')
    bm = build(context, src, ob.mch_hair, target)
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
    st = getattr(getattr(context, 'scene', None), 'mch_hair', None)
    if st is not None:                       # the next hair starts like this one
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


class MCH_PG_Hair(bpy.types.PropertyGroup):
    """Scene.mch_hair = settings for the next hair; Object.mch_hair = live hair."""
    style: EnumProperty(name='Style', items=STYLE_ITEMS, default='DREADS', update=_style_update,
                        description='Fills in the sliders')
    count: IntProperty(name='Count', default=34, min=1, max=600, update=_update, description='How many strands')
    length: FloatProperty(name='Length', default=0.55, min=0.01, max=2.0, update=_update,
                          description='Strand length (part of the body size)')
    length_random: FloatProperty(name='Length Random', default=0.3, min=0.0, max=0.95, update=_update)
    radius: FloatProperty(name='Thickness', default=0.022, min=0.001, max=0.2, precision=4, update=_update,
                          description='Strand thickness (part of the body size)')
    radius_random: FloatProperty(name='Thickness Random', default=0.2, min=0.0, max=0.9, update=_update)
    taper: FloatProperty(name='Taper', default=0.35, min=0.0, max=1.0, update=_update,
                         description='Thinner toward the tip (1 = pointed)')
    lift: FloatProperty(name='Lift', default=0.55, min=0.0, max=1.0, update=_update,
                        description='How far a strand stands out of the scalp before it bends down')
    gravity: FloatProperty(name='Gravity', default=1.0, min=0.0, max=3.0, update=_update)
    wave: FloatProperty(name='Wave', default=0.15, min=0.0, max=1.5, update=_update, description='Random wander / curl')
    straight: FloatProperty(name='Straight', default=0.7, min=0.0, max=1.0, update=_update,
                            description='How straight the strands hang once they fall (1 = plumb, little sideways '
                                        'drift or wave; 0 = loose and wavy)')
    rope: FloatProperty(name='Rope', default=0.18, min=0.0, max=0.6, update=_update,
                        description='Twisted rope ridges on the strands (dreadlock texture)')
    rope_twist: FloatProperty(name='Rope Twist', default=6.0, min=0.0, max=30.0, update=_update)
    rings: IntProperty(name='Rings', default=2, min=0, max=8, update=_update,
                       description='Metal bands / beads per strand (material slot 2)')
    ring_size: FloatProperty(name='Ring Size', default=1.35, min=1.05, max=3.0, update=_update)
    seed: IntProperty(name='Seed', default=1, min=0, update=_update)
    gap: FloatProperty(name='Gap', default=0.0, min=0.0, soft_max=0.1, precision=4, unit='LENGTH', update=_update,
                       description='Distance kept from the body (0 = Auto)')
    sides: IntProperty(name='Sides', default=8, min=3, max=24, update=_update)
    segments: IntProperty(name='Segments', default=28, min=4, max=120, update=_update)
    live: BoolProperty(default=False, options={'HIDDEN'})
    last_error: StringProperty(default='', options={'HIDDEN', 'SKIP_SAVE'})


def _material(name, colour, metal, rough):
    """A plain material (reused when it already exists) so the rings show apart from the strands."""
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.diffuse_color = (*colour, 1.0)
        m.metallic = metal
        m.roughness = rough
        try:
            m.use_nodes = True
            b = m.node_tree.nodes.get('Principled BSDF')
            if b is not None:
                b.inputs['Base Color'].default_value = (*colour, 1.0)
                b.inputs['Metallic'].default_value = metal
                b.inputs['Roughness'].default_value = rough
        except (AttributeError, KeyError, TypeError):
            pass
    return m


def perform(context, loops, projector):
    """Area drawn on a head -> live creature hair.  Returns a report; raises cg.CutError."""
    from . import armor_plate as ap
    from . import cape_gen
    from . import face_extract as fx
    scene = context.scene
    st = scene.mch_hair
    groups = cg.prepare_loops(loops)
    target = cape_gen.pick_body(context, projector, groups)
    if target is not None and SRC_KEY in target:
        target = None
    if target is None:
        raise cg.CutError('Draw the hair area on a head (the scalp).')
    frozen = ap.freeze_projector(projector)
    if frozen is None:
        raise cg.CutError('This view cannot be saved for the hair.')
    me = bpy.data.meshes.new(target.name + '_Hair')
    ob = bpy.data.objects.new(me.name, me)
    fx._parts_collection(context, COLLECTION).objects.link(ob)
    first = next((m for m in target.data.materials if m is not None), None)
    me.materials.append(first or _material('MCH Hair', (0.05, 0.045, 0.04), 0.0, 0.7))
    me.materials.append(_material('MCH Hair Rings', (0.8, 0.62, 0.28), 1.0, 0.3))   # slot 2: bands / beads
    ob[SRC_KEY] = json.dumps({'loops': [[[float(x), float(y)] for x, y in lp] for lp in loops], 'proj': frozen,
                              'target': target.name})
    p = ob.mch_hair
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
    return f'Creature hair "{ob.name}" on {target.name} ({name}, {len(me.polygons)} faces)'


def live_hair(context):
    ob = getattr(context, 'active_object', None)
    if ob is not None and getattr(ob, 'mch_hair', None) is not None and ob.mch_hair.live and source(ob):
        return ob
    return None


def apply(ob):
    ob.mch_hair.live = False
    if SRC_KEY in ob:
        del ob[SRC_KEY]


class MCH_OT_hair_apply(bpy.types.Operator):
    bl_idname = 'mch.hair_apply'
    bl_label = 'Apply Hair'
    bl_description = 'The hair becomes a plain mesh (the sliders stop rebuilding it)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return live_hair(context) is not None

    def execute(self, context):
        apply(live_hair(context))
        return {'FINISHED'}


def draw(layout, context):
    ob = live_hair(context)
    p = ob.mch_hair if ob is not None else context.scene.mch_hair
    box = layout.box()
    if ob is not None:
        box.label(text='LIVE Hair: ' + ob.name, icon='CURVES')
        if p.last_error:
            box.label(text=p.last_error, icon='ERROR')
    else:
        box.label(text='Creature Hair: settings for the next one', icon='CURVES')
    box.row(align=True).prop(p, 'style', expand=True)
    col = box.column(align=True)
    col.prop(p, 'count')
    col.prop(p, 'length', slider=True)
    col.prop(p, 'length_random', slider=True)
    col.prop(p, 'radius', slider=True)
    col.prop(p, 'radius_random', slider=True)
    col.prop(p, 'taper', slider=True)
    col = box.column(align=True)
    col.prop(p, 'lift', slider=True)
    col.prop(p, 'gravity', slider=True)
    col.prop(p, 'wave', slider=True)
    col.prop(p, 'straight', slider=True)
    col = box.column(align=True)
    col.prop(p, 'rope', slider=True)
    if p.rope > 0:
        col.prop(p, 'rope_twist', slider=True)
    r = col.row(align=True)
    r.prop(p, 'rings')
    if p.rings:
        r.prop(p, 'ring_size')
    col = box.column(align=True)
    col.prop(p, 'seed')
    col.prop(p, 'gap')
    r = col.row(align=True)
    r.prop(p, 'sides')
    r.prop(p, 'segments')
    if ob is not None:
        box.operator('mch.hair_apply', icon='CHECKMARK')
    col = layout.column(align=True)
    col.scale_y = 0.8
    for line in ('Draw the scalp area on a head', 'Strands grow there and fall over the body',
                 'Rings = material slot 2', 'Apply: plain mesh'):
        col.label(text=line)


CLASSES = (MCH_PG_Hair, MCH_OT_hair_apply)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_hair = bpy.props.PointerProperty(type=MCH_PG_Hair)
    bpy.types.Object.mch_hair = bpy.props.PointerProperty(type=MCH_PG_Hair)


def unregister():
    for n, t in (('mch_hair', bpy.types.Object), ('mch_hair', bpy.types.Scene)):
        try:
            delattr(t, n)
        except AttributeError:
            pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
