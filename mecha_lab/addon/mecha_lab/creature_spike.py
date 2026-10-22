"""0.24.20 Creature Spike: draw a line over a mesh, spikes stand up along it.

Each spike is a side silhouette (four presets traced from the user's sketch) inflated like a Creature Base Mesh
Puff - thick at the base, round, thin toward the tip - standing on the surface: the silhouette's ground line on
the surface, its up along the surface normal, leaning along the drawn line.

    Presets     tick the ones to use (one, two or all four); with more than one they are mixed at random
    Size        height of a spike, Size Random varies it per spike
    Lean        tilt forward / back along the line, Lean Random varies it
    Turn Random spikes turned around their up axis a little
    Spacing     distance between spikes (x Size), Thickness (x width), Sink (into the surface), Seed, Flip

Everything stays live until Apply.  ``spike_outline`` and ``layout`` are pure and tested headless.
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

SRC_KEY = 'mch_spike_src'
COLLECTION = 'Creature Spikes'
GROUND_TILT = 12.0      # the sketch's ground line runs down to the right this many degrees: turned level
# side silhouettes (px, y down) from the user's sketch; scale 1 = 400 px
SKETCH = {
    'FIN': [(70, 1355), (85, 1290), (120, 1180), (165, 1090), (180, 1095), (180, 1310), (205, 1330), (205, 1360)],
    'HORN': [(280, 1300), (330, 1180), (400, 1000), (470, 860), (600, 680), (540, 800), (470, 1000), (400, 1250),
             (360, 1395), (290, 1370), (275, 1330)],
    'HOOK': [(400, 1360), (430, 1350), (440, 1395), (460, 1390), (530, 1290), (610, 1180), (700, 1095), (665, 1165),
             (600, 1285), (525, 1410), (480, 1440), (420, 1420), (395, 1385)],
    'NOTCH': [(580, 1440), (660, 1360), (730, 1310), (770, 1295), (790, 1330), (780, 1380), (745, 1440), (770, 1450),
              (770, 1510), (660, 1510), (600, 1470)],
}
PRESETS = (('FIN', 'Short Fin'), ('HORN', 'Long Horn'), ('HOOK', 'Hook'), ('NOTCH', 'Notched Fin'))
LIVE_KEYS = ('use_fin', 'use_horn', 'use_hook', 'use_notch', 'size', 'size_random', 'lean', 'lean_random',
             'turn_random', 'spacing', 'thickness', 'sink', 'seed', 'flip', 'smooth')
_CACHE = {}          # object name -> (key, path)
_UNIT = {}           # (preset, thickness) -> (verts, faces) of one spike, height scale 1


def spike_outline(kind):
    """The silhouette of a preset: y up, ground at y = 0, base centred on x = 0, 400 px = 1 (CCW)."""
    a = math.radians(GROUND_TILT)
    pts = [(x, -y) for x, y in SKETCH[kind]]
    c, s = math.cos(a), math.sin(a)
    pts = [(x * c - y * s, x * s + y * c) for x, y in pts]          # level the ground line
    ymin = min(p[1] for p in pts)
    base = [p for p in pts if p[1] < ymin + 0.08 * (max(q[1] for q in pts) - ymin)]
    cx = sum(p[0] for p in base) / len(base)
    pts = [((x - cx) / 400.0, (y - ymin) / 400.0) for x, y in pts]
    area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
               for i in range(len(pts)))
    return pts if area > 0 else pts[::-1]


def layout(total, spacing, presets, size, size_random, lean, lean_random, turn_random, seed):
    """[(distance along the line, preset, size, lean, turn)] - pure, the same for the same inputs."""
    rnd = random.Random(seed)
    out = []
    if not presets or total <= 0:
        return out
    step = max(spacing, 1e-4)
    count = max(1, int(total / step))
    start = (total - (count - 1) * step) / 2.0 if count > 1 else total / 2.0
    for i in range(count):
        kind = presets[rnd.randrange(len(presets))]
        sz = size * (1.0 + size_random * (rnd.random() * 2.0 - 1.0))
        ln = lean + lean_random * (rnd.random() * 2.0 - 1.0)
        tn = turn_random * (rnd.random() * 2.0 - 1.0)
        out.append((start + i * step, kind, max(sz, size * 0.05), ln, tn))
    return out


def unit_spike(kind, thickness):
    """(verts, faces) of one spike, height 1: the silhouette inflated (Creature Base Mesh Puff), z = sideways."""
    key = (kind, round(thickness, 4))
    hit = _UNIT.get(key)
    if hit is not None:
        return hit
    from . import base_mesh as bmm
    outline = spike_outline(kind)
    p = types.SimpleNamespace(profile='PUFF', puff=1.0, peak=0.0, resolution=22, outline_smooth=0.5,
                              edge_round=0.15, offset=0.0, embed=0.0, height=0.2, wall=0.0, roundness=0.3)
    bm = bmm.build_bmesh([(outline, [])], p)
    try:
        verts = [(v.co.x, v.co.y, v.co.z * thickness) for v in bm.verts]
        faces = [tuple(v.index for v in f.verts) for f in bm.faces]
    finally:
        bm.free()
    _UNIT[key] = (verts, faces)
    return verts, faces


def _update(self, context):
    ob = self.id_data
    if not isinstance(ob, bpy.types.Object) or not self.live:
        return
    try:
        rebuild(context, ob)
        self.last_error = ''
    except (cg.CutError, ValueError, RuntimeError) as ex:
        self.last_error = str(ex)
    st = getattr(getattr(context, 'scene', None), 'mch_spike', None)
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


class MCH_PG_Spike(bpy.types.PropertyGroup):
    use_fin: _p(BoolProperty, name='Short Fin', default=True)
    use_horn: _p(BoolProperty, name='Long Horn', default=True)
    use_hook: _p(BoolProperty, name='Hook', default=True)
    use_notch: _p(BoolProperty, name='Notched Fin', default=True)
    size: _p(FloatProperty, name='Size', default=0.3, min=0.001, soft_max=5.0, precision=3, unit='LENGTH')
    size_random: _p(FloatProperty, name='Size Random', default=0.3, min=0.0, max=0.95, subtype='FACTOR')
    lean: _p(FloatProperty, name='Lean', default=0.0, min=-math.radians(80), max=math.radians(80), subtype='ANGLE',
             description='Tilt every spike forward / back along the line')
    lean_random: _p(FloatProperty, name='Lean Random', default=math.radians(8), min=0.0, max=math.radians(60),
                    subtype='ANGLE')
    turn_random: _p(FloatProperty, name='Turn Random', default=math.radians(6), min=0.0, max=math.radians(90),
                    subtype='ANGLE', description='Turn spikes a little around their up axis')
    spacing: _p(FloatProperty, name='Spacing', default=0.8, min=0.1, soft_max=4.0,
                description='Distance between spikes (x Size)')
    thickness: _p(FloatProperty, name='Thickness', default=0.6, min=0.05, soft_max=2.0,
                  description='How thick a spike is sideways (1 = as thick as it is wide)')
    sink: _p(FloatProperty, name='Sink', default=0.06, min=0.0, max=0.5, subtype='FACTOR',
             description='How far the base goes into the surface (x Size)')
    seed: _p(IntProperty, name='Seed', default=1, min=0)
    flip: _p(BoolProperty, name='Flip', default=False, description='Spikes lean the other way along the line')
    smooth: _p(IntProperty, name='Smooth Path', default=3, min=0, max=30)
    live: BoolProperty(default=False, options={'HIDDEN'})
    last_error: StringProperty(default='', options={'HIDDEN', 'SKIP_SAVE'})


def enabled_presets(p):
    return [k for k, attr in (('FIN', 'use_fin'), ('HORN', 'use_horn'), ('HOOK', 'use_hook'), ('NOTCH', 'use_notch'))
            if getattr(p, attr)]


def source(ob):
    if ob is None:
        return None
    try:
        raw = ob.get(SRC_KEY)
        return json.loads(raw) if raw else None
    except (TypeError, ValueError, ReferenceError):
        return None


def surface_line(context, ob, src, p):
    """Cached (points, normals) of the drawn line on the mesh."""
    key = (src.get('stamp'), p.smooth)
    hit = _CACHE.get(ob.name)
    if hit is not None and hit[0] == key:
        return hit[1]
    from . import armor_plate as ap
    from . import belt_maker as bmk
    target = bpy.data.objects.get(src.get('target', ''))
    if target is None or target.type != 'MESH':
        raise cg.CutError('The mesh the spikes were drawn on is gone.')
    projector = ap.thaw_projector(src['proj'])
    pts, _closed = bmk._follow_path(context, target, projector, [tuple(q) for q in src['path']])
    length = sum((b - a).length for a, b in zip(pts, pts[1:]))
    pts = bmk.resample(pts, max(length / 200.0, 1e-5), False)
    pts = bmk.smooth_path(pts, p.smooth, False)
    bvh, _v, _f = ap._target_bvh(context, target)
    view = Vector(projector.view_dir)
    snapped, nrms = [], []
    for q in pts:
        loc, n, _i, _d = bvh.find_nearest(q)
        q = loc if loc is not None else q
        n = n if n is not None else -view
        if n.dot(view) > 0:
            n = -n
        snapped.append(q)
        nrms.append(n.normalized())
    for _ in range(3):
        m = len(nrms)
        nrms = [(nrms[max(i - 1, 0)] + nrms[i] * 2.0 + nrms[min(i + 1, m - 1)]).normalized() for i in range(m)]
    data = (snapped, nrms)
    _CACHE[ob.name] = (key, data)
    return data


def build(context, ob):
    src = source(ob)
    if src is None:
        raise cg.CutError('These spikes were applied.')
    p = ob.mch_spike
    presets = enabled_presets(p)
    if not presets:
        raise cg.CutError('Tick at least one spike preset.')
    pts, nrms = surface_line(context, ob, src, p)
    acc = [0.0]
    for a, b in zip(pts, pts[1:]):
        acc.append(acc[-1] + (b - a).length)
    total = acc[-1]
    if total <= 0:
        raise cg.CutError('The line is too short.')
    verts, faces = [], []
    j = 0
    for s, kind, size, lean, turn in layout(total, p.spacing * p.size, presets, p.size, p.size_random, p.lean,
                                             p.lean_random, p.turn_random, p.seed):
        while j < len(acc) - 2 and acc[j + 1] < s:
            j += 1
        t = (s - acc[j]) / max(acc[j + 1] - acc[j], 1e-12)
        pos = pts[j].lerp(pts[j + 1], t)
        N = nrms[j].lerp(nrms[j + 1], t).normalized()
        T = pts[j + 1] - pts[j]
        T = (T - N * T.dot(N)).normalized()
        if p.flip:
            T = -T
        rot = Matrix.Rotation(turn, 3, N)
        T = rot @ T
        Sd = T.cross(N).normalized()
        cl, sl = math.cos(-lean), math.sin(-lean)
        uv, uf = unit_spike(kind, p.thickness)
        off = len(verts)
        for x, y, z in uv:
            xx, yy = x * cl - y * sl, x * sl + y * cl          # lean in the silhouette plane
            verts.append(pos + (T * xx + N * (yy - p.sink) + Sd * z) * size)
        faces += [tuple(i + off for i in f) for f in uf]
    if not verts:
        raise cg.CutError('No spike fits on the line (lower Spacing or Size).')
    return verts, faces


def rebuild(context, ob):
    verts, faces = build(context, ob)
    inv = ob.matrix_world.inverted_safe()
    me = ob.data
    me.clear_geometry()
    me.from_pydata([tuple(inv @ v) for v in verts], [], faces)
    for poly in me.polygons:
        poly.use_smooth = True
    me.update()


def perform(context, path, projector):
    """Open drawn path (pixels) -> live spikes along it.  Returns a report; raises cg.CutError."""
    from . import armor_plate as ap
    from . import belt_maker as bmk
    from . import face_extract as fx
    path = [tuple(q) for q in path]
    if len(path) < 2:
        raise cg.CutError('Spikes: draw a line (at least 2 points).')
    target = bmk.pick_target(context, projector, path)
    if target is None:
        raise cg.CutError('Spikes: draw the line over a mesh.')
    frozen = ap.freeze_projector(projector)
    if frozen is None:
        raise cg.CutError('This view cannot be saved for the spikes.')
    st = context.scene.mch_spike
    me = bpy.data.meshes.new(target.name + '_Spikes')
    ob = bpy.data.objects.new(me.name, me)
    fx._parts_collection(context, COLLECTION).objects.link(ob)
    for mat in target.data.materials:
        me.materials.append(mat)
    ob[SRC_KEY] = json.dumps({'path': [[float(x), float(y)] for x, y in path], 'proj': frozen,
                              'target': target.name, 'stamp': id(ob) % 100000})
    p = ob.mch_spike
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
    st.seed += 1                       # the next line gets a different mix
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    return f'Spikes "{ob.name}" on {target.name} ({", ".join(enabled_presets(p))})'


def live_spikes(context):
    ob = getattr(context, 'active_object', None)
    if ob is not None and getattr(ob, 'mch_spike', None) is not None and ob.mch_spike.live and source(ob):
        return ob
    return None


class MCH_OT_spike_apply(bpy.types.Operator):
    bl_idname = 'mch.spike_apply'
    bl_label = 'Apply Spikes'
    bl_description = 'The spikes become a plain mesh (the sliders stop rebuilding them)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return live_spikes(context) is not None

    def execute(self, context):
        ob = live_spikes(context)
        ob.mch_spike.live = False
        del ob[SRC_KEY]
        _CACHE.pop(ob.name, None)
        self.report({'INFO'}, f'{ob.name}: applied')
        return {'FINISHED'}


def draw(layout_, context):
    ob = live_spikes(context)
    p = ob.mch_spike if ob is not None else context.scene.mch_spike
    if ob is not None:
        box = layout_.box()
        box.label(text='LIVE: ' + ob.name, icon='CON_TRACKTO')
        if p.last_error:
            box.label(text=p.last_error, icon='ERROR')
        target = box
    else:
        layout_.label(text='Settings for the next line of spikes', icon='CON_TRACKTO')
        target = layout_
    target.label(text='Presets (ticked ones are mixed at random):')
    grid = target.grid_flow(columns=2, align=True)
    for attr in ('use_fin', 'use_horn', 'use_hook', 'use_notch'):
        grid.prop(p, attr, toggle=True)
    col = target.column(align=True)
    col.prop(p, 'size')
    col.prop(p, 'size_random', slider=True)
    col = target.column(align=True)
    col.prop(p, 'lean')
    col.prop(p, 'lean_random')
    col.prop(p, 'turn_random')
    col = target.column(align=True)
    col.prop(p, 'spacing')
    col.prop(p, 'thickness')
    col.prop(p, 'sink', slider=True)
    row = target.row(align=True)
    row.prop(p, 'seed')
    row.prop(p, 'flip', toggle=True)
    target.prop(p, 'smooth')
    if ob is not None:
        target.operator('mch.spike_apply', icon='CHECKMARK')
    col = layout_.column(align=True)
    col.scale_y = 0.8
    for line in ('Draw a line over a mesh (click points / Free Draw), Enter',
                 'Spikes stand along it, leaning along the line', 'Seed: another random mix, Apply: plain mesh'):
        col.label(text=line)


CLASSES = (MCH_PG_Spike, MCH_OT_spike_apply)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_spike = bpy.props.PointerProperty(type=MCH_PG_Spike)
    bpy.types.Object.mch_spike = bpy.props.PointerProperty(type=MCH_PG_Spike)


def unregister():
    for n, t in (('mch_spike', bpy.types.Object), ('mch_spike', bpy.types.Scene)):
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
    _UNIT.clear()
