"""0.24.20 Creature Plate: the Armor Plate idea with the creature shapes of Creature Base Mesh.

Draw an outline on a mesh: a separate plate is laid onto the surface and bulges out of it -

    Puff     round, as thick as it is wide (thin parts stay thin)
    Ridge    a sharp ridge along the middle (diamond cross-section)
    Pillow   flat top, only the edge is round

The outline is filled with the same even point set as Creature Base Mesh (``base_mesh.profile_field``,
screen pixels), every point is projected through the view onto the mesh it was drawn on (like Armor Plate,
the mesh is never changed) and pushed out along the (smoothed) surface normal:

    top    = surface + normal * (Edge Thickness + shape * height)
    bottom = surface - normal * Sink

``height`` runs from Height at one end to End Height at the other (along the long side of the outline,
turned by Direction), so one end can lift like a scale.  Every slider rebuilds the plate (the projected
points are cached, so only the first build and Outline / Resolution changes cast rays).  Apply makes it a
plain mesh.  ``ramp_values`` and ``long_axis`` are pure and tested headless.
"""
from __future__ import annotations

import json
import math

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from mathutils import Matrix, Vector

from . import core_geometry as cg

SRC_KEY = 'mch_cplate_src'
COLLECTION = 'Creature Plates'
AUTO_RATIO = 0.3      # Auto height: a plate is a third as thick as a Creature Base Mesh lump of that width
PROFILE_ITEMS = [
    ('PUFF', 'Puff', 'Round, about as thick as it is wide (thin parts stay thin)', 'META_BALL', 0),
    ('RIDGE', 'Ridge', 'A sharp ridge along the middle (diamond cross-section)', 'MESH_ICOSPHERE', 1),
    ('PILLOW', 'Pillow', 'Flat top, only the edge is round', 'MESH_CYLINDER', 2),
    ('SCALE', 'Scale', 'A real scale: thick at the root (where you started drawing), thin toward the tip, '
     'knife-thin edges, the tip lifts off the body', 'SHARPCURVE', 3),
]
LIVE_KEYS = ('profile', 'peak', 'end_peak', 'direction', 'edge_round', 'edge_thickness', 'sink', 'outline_smooth',
             'resolution', 'tip_lift')
POINT_KEYS = ('outline_smooth', 'resolution', 'profile', 'edge_round')    # change the point set / shape field
_CACHE = {}          # object name -> (key, field data): rays are cast only when the point set changes


def _update(self, context):
    ob = self.id_data
    if not isinstance(ob, bpy.types.Object) or not self.live:
        return
    try:
        rebuild(context, ob)
        self.last_error = ''
    except (cg.CutError, ValueError, RuntimeError) as ex:
        self.last_error = str(ex)
    st = getattr(getattr(context, 'scene', None), 'mch_cplate', None)
    if st is not None:                     # the next plate starts like this one (heights stay Auto)
        for k in ('profile', 'direction', 'edge_round', 'edge_thickness', 'sink', 'outline_smooth', 'resolution'):
            try:
                if getattr(st, k) != getattr(self, k):
                    setattr(st, k, getattr(self, k))
            except (AttributeError, TypeError):
                pass


class MCH_PG_CreaturePlate(bpy.types.PropertyGroup):
    """Scene.mch_cplate = settings for the next plate; Object.mch_cplate = live plate."""
    profile: EnumProperty(name='Shape', items=PROFILE_ITEMS, default='PUFF', update=_update)
    peak: FloatProperty(name='Height', default=0.0, min=0.0, soft_max=5.0, precision=4, unit='LENGTH',
                        update=_update, description='Height of the top at the start (0 = Auto: the shape\'s own '
                                                    'height; set to the real value when the plate is made)')
    end_peak: FloatProperty(name='End Height', default=-1.0, min=-1.0, soft_max=5.0, precision=4, unit='LENGTH',
                            update=_update, description='Height of the top at the far end (-1 = same as Height): '
                                                        'one end lifts like a scale')
    direction: FloatProperty(name='Direction', default=0.0, min=-math.pi, max=math.pi, subtype='ANGLE',
                             update=_update, description='Which way Height -> End Height runs (0 = along the long '
                                                         'side of the outline)')
    edge_round: FloatProperty(name='Edge Round', default=0.15, min=0.0, max=1.0, update=_update,
                              description='Ridge / Pillow: how round the outer edge is')
    edge_thickness: FloatProperty(name='Edge Thickness', default=0.0, min=0.0, soft_max=1.0, precision=4,
                                  unit='LENGTH', update=_update,
                                  description='Straight side wall under the rounded top (0 = thin edge)')
    tip_lift: FloatProperty(name='Tip Lift', default=-1.0, min=-1.0, soft_max=2.0, precision=4, unit='LENGTH',
                            update=_update, description='The far end rises off the body (scales overlap); -1 = '
                                                        'Auto: Scale lifts 1.5 x its thickness, others 0')
    sink: FloatProperty(name='Sink', default=0.0, min=0.0, soft_max=0.5, precision=4, unit='LENGTH',
                        update=_update, description='How far the bottom goes into the surface (0 = Auto, 2% of '
                                                    'the plate size: no gap on curved surfaces)')
    outline_smooth: FloatProperty(name='Soft Outline', default=0.5, min=0.0, max=1.0, update=_update,
                                  description='Round off the corners of the drawn outline')
    resolution: IntProperty(name='Resolution', default=15, min=4, max=96, update=_update,
                            description='Points across the plate (higher = smoother, slower)')
    puff: FloatProperty(default=1.0, options={'HIDDEN'})
    live: BoolProperty(default=False, options={'HIDDEN'})
    last_error: StringProperty(default='', options={'HIDDEN', 'SKIP_SAVE'})


# -----------------------------------------------------------------------------
# Pure helpers
# -----------------------------------------------------------------------------


def long_axis(pts):
    """Unit 2D direction of the longest spread of ``pts`` (principal axis)."""
    n = max(1, len(pts))
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - cx) ** 2 for p in pts)
    syy = sum((p[1] - cy) ** 2 for p in pts)
    sxy = sum((p[0] - cx) * (p[1] - cy) for p in pts)
    a = 0.5 * math.atan2(2.0 * sxy, sxx - syy)
    return math.cos(a), math.sin(a)


def ramp_values(pts, direction=0.0, start=None):
    """0..1 for every 2D point along the long axis turned by ``direction`` (radians); with ``start`` (the first
    point drawn: the root of a scale) along the way from it to the middle of the shape instead."""
    ax, ay = long_axis(pts)
    if start is not None:
        # 0.24.20 from the root (the first point drawn) straight across the shape, not along its long side
        cx = sum(p[0] for p in pts) / max(1, len(pts))
        cy = sum(p[1] for p in pts) / max(1, len(pts))
        vx, vy = cx - start[0], cy - start[1]
        ln = math.hypot(vx, vy)
        if ln > 1e-9:
            ax, ay = vx / ln, vy / ln
    c, s = math.cos(direction), math.sin(direction)
    dx, dy = ax * c - ay * s, ax * s + ay * c
    proj = [p[0] * dx + p[1] * dy for p in pts]
    lo, hi = min(proj), max(proj)
    span = max(hi - lo, 1e-12)
    return [(v - lo) / span for v in proj]


# -----------------------------------------------------------------------------
# Build
# -----------------------------------------------------------------------------


def _smooth_normals(nrms, tris, passes=3):
    nb = [set() for _ in nrms]
    for a, b, c in tris:
        nb[a] |= {b, c}
        nb[b] |= {a, c}
        nb[c] |= {a, b}
    out = [Vector(n) for n in nrms]
    for _ in range(passes):
        out = [(out[i] + sum((out[j] for j in nb[i]), Vector())).normalized() if nb[i] else out[i]
               for i in range(len(out))]
    return out


def surface_field(cos, tris, p):
    """0.24.20 Through: the creature shape on a piece of surface (3D triangles).  Returns (order, nb, shape,
    natural): ``order`` puts the outline points first (``nb`` of them), ``shape`` 0..1 per reordered point."""
    import heapq
    from . import base_mesh as bmm
    count = {}
    for a, b, c in tris:
        for u, v in ((a, b), (b, c), (c, a)):
            k = (min(u, v), max(u, v))
            count[k] = count.get(k, 0) + 1
    rim = {i for k, n in count.items() if n == 1 for i in k}
    if not rim:
        raise cg.CutError('Through: the outline covers the whole mesh (no edge left for the plate).')
    order = sorted(range(len(cos)), key=lambda i: (i not in rim, i))
    nb = len(rim)
    new = {old: i for i, old in enumerate(order)}
    pts = [cos[i] for i in order]
    t2 = [tuple(new[i] for i in t) for t in tris]
    # distance to the outline over the surface (edge graph)
    adj = [[] for _ in pts]
    for (u, v) in count:
        a, b = new[u], new[v]
        w = (pts[a] - pts[b]).length
        adj[a].append((b, w))
        adj[b].append((a, w))
    dist = [math.inf] * len(pts)
    heap = [(0.0, i) for i in range(nb)]
    for i in range(nb):
        dist[i] = 0.0
    while heap:
        d, i = heapq.heappop(heap)
        if d > dist[i]:
            continue
        for j, w in adj[i]:
            if d + w < dist[j]:
                dist[j] = d + w
                heapq.heappush(heap, (d + w, j))
    dist = [0.0 if math.isinf(x) else x for x in dist]
    if p.profile == 'RIDGE':
        h = bmm.ridge_heights(dist, nb, 1.0, p.edge_round)
    elif p.profile == 'SCALE':
        h = bmm.scale_heights(dist, nb, p.edge_round)
    elif p.profile == 'PILLOW':
        h = bmm.pillow_heights(dist, nb, p.edge_round)
    else:
        h = bmm.puff_heights([tuple(v) for v in pts], t2, nb, 1.0)
    top = max(max(h), 1e-12)
    return order, nb, t2, [x / top for x in h], top


def _through_parts(context, src, p, target, projector):
    from . import through_region as tr
    groups = cg.prepare_loops([[tuple(q) for q in lp] for lp in src['loops']])
    xs = [q[0] for lp in src['loops'] for q in lp]
    ys = [q[1] for lp in src['loops'] for q in lp]
    extent = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
    spacing = max(2.0, extent / max(4.0, p.resolution * 1.5))
    panels = tr.panels_for(context, target, groups, projector, spacing, 180.0, split=False)
    parts = []
    for pn in panels:
        order, nb, tris, shape, natural = surface_field(pn['cos'], pn['tris'], p)
        cos = [pn['cos'][i] for i in order]
        nrms = _smooth_normals([pn['nrms'][i] for i in order], tris)
        scr = []
        for c in cos:
            q = projector.to_screen(c)
            scr.append(q if q is not None else (0.0, 0.0))
        parts.append(dict(pts=scr, tris=tris, nb=nb, cos=cos, nrms=nrms, shape=shape, natural=natural,
                          start=tuple(src['loops'][0][0])))
    return parts


def _field(context, ob, src, p, target, projector):
    """Cached point set on the surface: (pts px, tris, nb per group, cos, nrms, shape, natural world height)."""
    from . import armor_plate as ap
    from . import base_mesh as bmm
    key = (src.get('stamp'), tuple(round(float(getattr(p, k)), 5) if not isinstance(getattr(p, k), str)
                                   else getattr(p, k) for k in POINT_KEYS))
    hit = _CACHE.get(ob.name)
    if hit is not None and hit[0] == key:
        return hit[1]
    if src.get('through'):                 # 0.24.20 front and back of the mesh under the outline
        parts = _through_parts(context, src, p, target, projector)
        _CACHE[ob.name] = (key, parts)
        return parts
    groups = cg.prepare_loops([[tuple(q) for q in lp] for lp in src['loops']])
    if not groups:
        raise cg.CutError('The outline is empty.')
    bvh, _wv, _polys = ap._target_bvh(context, target)
    parts = []
    for outer, holes in groups:
        boundary, pts, tris, nb, shape, natural_px, _sp = bmm.profile_field(outer, holes, p)
        cos, nrms, _missing = ap.project_patch(pts, projector, bvh)
        nrms = _smooth_normals(nrms, tris)
        # world units per pixel here (median over the triangle edges)
        ratios = []
        for a, b, _c in tris[::max(1, len(tris) // 200)]:
            dp = math.dist(pts[a], pts[b])
            if dp > 1e-9:
                ratios.append((cos[a] - cos[b]).length / dp)
        ratios.sort()
        scale = ratios[len(ratios) // 2] if ratios else 1.0
        parts.append(dict(pts=pts, tris=tris, nb=nb, cos=cos, nrms=nrms, shape=shape, natural=natural_px * scale,
                          start=tuple(src['loops'][0][0])))
    _CACHE[ob.name] = (key, parts)
    return parts


def build_mesh(parts, p, peak, end_peak):
    """BMesh (world space) of the plate from the cached point sets."""
    bm = bmesh.new()
    size = 0.0
    for part in parts:
        cs = part['cos']
        lo = Vector([min(c[k] for c in cs) for k in range(3)])
        hi = Vector([max(c[k] for c in cs) for k in range(3)])
        size = max(size, (hi - lo).length)
    sink = p.sink if p.sink > 0 else size * 0.02
    for part in parts:
        pts, tris, nb, cos, nrms, shape = (part[k] for k in ('pts', 'tris', 'nb', 'cos', 'nrms', 'shape'))
        ramp = ramp_values(pts, p.direction, part.get('start'))
        h0, h1 = peak, (end_peak if end_peak >= 0 else peak)
        hgt = [h0 + (h1 - h0) * t for t in ramp]
        wall = [p.edge_thickness * (hh / max(h0, 1e-9) if h0 > 0 else 1.0) for hh in hgt]
        lift_tip = p.tip_lift if p.tip_lift >= 0 else (1.5 * peak if p.profile == 'SCALE' else 0.0)
        lift = [lift_tip * t ** 1.6 for t in ramp]               # the far end rises off the body
        # the bottom stays in the surface at the root and comes out to it toward the tip (thin edge there)
        down = [sink * max(0.05, 1.0 - t) if lift_tip > 0 else sink for t in ramp]
        top = [bm.verts.new(cos[i] + nrms[i] * (lift[i] + wall[i] + shape[i] * hgt[i])) for i in range(len(pts))]
        bot = [bm.verts.new(cos[i] + nrms[i] * (lift[i] - down[i])) for i in range(len(pts))]
        for a, b, c in tris:
            bm.faces.new((top[a], top[b], top[c])).smooth = True
            bm.faces.new((bot[c], bot[b], bot[a]))
        # side wall around every outline loop (the first nb points, in loop order per loop)
        bm.verts.ensure_lookup_table()
        rim = set()
        for a, b, c in tris:
            for u, v in ((a, b), (b, c), (c, a)):
                if u < nb and v < nb:
                    rim.add((u, v))
        for u, v in rim:
            if (v, u) in rim:
                continue         # an inside edge between two outline points (should not happen: split)
            bm.faces.new((top[v], top[u], bot[u], bot[v])).smooth = True
        inner = [top[i] for i in range(nb, len(pts))]
        bmesh.ops.smooth_vert(bm, verts=inner, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def source(ob):
    if ob is None:
        return None
    try:
        raw = ob.get(SRC_KEY)
    except (TypeError, ReferenceError):
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def rebuild(context, ob):
    from . import armor_plate as ap
    src = source(ob)
    p = ob.mch_cplate
    if src is None:
        raise cg.CutError('This plate was applied (no outline kept).')
    target = bpy.data.objects.get(src.get('target', ''))
    if target is None or target.type != 'MESH':
        raise cg.CutError('The mesh the plate was drawn on is gone.')
    parts = _field(context, ob, src, p, target, ap.thaw_projector(src['proj']))
    # Pillow's own height is only its round edge: it is already flat (no third of it)
    natural = max(part['natural'] for part in parts) * {'PILLOW': 1.0, 'SCALE': 0.5}.get(p.profile, AUTO_RATIO)
    peak = p.peak if p.peak > 0 else natural
    bm = build_mesh(parts, p, peak, p.end_peak)
    try:
        inv = ob.matrix_world.inverted_safe()
        bmesh.ops.transform(bm, matrix=inv, verts=bm.verts[:])
        bm.to_mesh(ob.data)
    finally:
        bm.free()
    from . import live_subtract
    live_subtract.apply(context, ob)          # 0.24.21 the Alt outlines cut out again
    try:
        ob.data.set_sharp_from_angle(angle=math.radians(60))   # crisp edges
    except (AttributeError, TypeError, RuntimeError):
        pass
    ob.data.update()
    return natural


def perform(context, loops, projector):
    """Lasso -> a live Creature Plate on the mesh under it.  Returns a report; raises cg.CutError."""
    from . import armor_plate as ap
    from . import face_extract as fx
    scene = context.scene
    st = scene.mch_cplate
    groups = cg.prepare_loops(loops)
    target = ap.pick_surface(context, projector, groups)
    if target is None:
        raise cg.CutError('Draw the plate over a mesh.')
    frozen = ap.freeze_projector(projector)
    if frozen is None:
        raise cg.CutError('This view cannot be saved for the plate.')
    me = bpy.data.meshes.new(target.name + '_CreaturePlate')
    ob = bpy.data.objects.new(me.name, me)
    fx._parts_collection(context, COLLECTION).objects.link(ob)
    for mat in target.data.materials:
        me.materials.append(mat)
    brush = getattr(scene, 'mch_brush', None)
    ob[SRC_KEY] = json.dumps({'loops': [[[float(x), float(y)] for x, y in lp] for lp in loops], 'proj': frozen,
                              'target': target.name, 'stamp': id(ob) % 100000,
                              'through': bool(getattr(brush, 'through_mode', False))})
    p = ob.mch_cplate
    for k in LIVE_KEYS:
        setattr(p, k, getattr(st, k))
    try:
        natural = rebuild(context, ob)
    except Exception:
        _CACHE.pop(ob.name, None)
        bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.meshes.remove(me)
        raise
    # move the origin to the middle of the plate, the sliders start at the real heights
    cen = sum((v.co for v in me.vertices), Vector()) / max(1, len(me.vertices))
    me.transform(Matrix.Translation(-cen))
    ob.matrix_world = Matrix.Translation(cen)
    if st.peak <= 0:
        p.peak = natural
    if st.end_peak < 0:
        p.end_peak = p.peak * (0.15 if p.profile == 'SCALE' else 1.0)     # a scale thins out to its tip
    p.live = True
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    name = dict((i[0], i[1]) for i in PROFILE_ITEMS)[p.profile]
    through = ' through front and back' if source(ob).get('through') else ''
    return f'Creature plate "{ob.name}" on {target.name}{through} ({name}, {len(me.polygons)} faces)'


def live_plate(context):
    ob = getattr(context, 'active_object', None)
    if ob is not None and getattr(ob, 'mch_cplate', None) is not None and ob.mch_cplate.live and source(ob):
        return ob
    return None


def apply(ob):
    from . import live_subtract
    ob.mch_cplate.live = False
    if SRC_KEY in ob:
        del ob[SRC_KEY]
    live_subtract.clear(ob)
    _CACHE.pop(ob.name, None)


class MCH_OT_cplate_apply(bpy.types.Operator):
    bl_idname = 'mch.cplate_apply'
    bl_label = 'Apply Creature Plate'
    bl_description = 'The plate becomes a plain mesh (the sliders stop rebuilding it)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return live_plate(context) is not None

    def execute(self, context):
        ob = live_plate(context)
        apply(ob)
        self.report({'INFO'}, f'{ob.name}: applied')
        return {'FINISHED'}


def draw(layout, context):
    ob = live_plate(context)
    p = ob.mch_cplate if ob is not None else context.scene.mch_cplate
    if ob is not None:
        box = layout.box()
        box.label(text='LIVE: ' + ob.name, icon='MOD_SMOOTH')
        if p.last_error:
            box.label(text=p.last_error, icon='ERROR')
        target = box
    else:
        layout.label(text='Settings for the next plate', icon='MOD_SMOOTH')
        target = layout
    target.row(align=True).prop(p, 'profile', expand=True)
    col = target.column(align=True)
    col.prop(p, 'peak')
    col.prop(p, 'end_peak')
    col.prop(p, 'direction')
    col = target.column(align=True)
    if p.profile in {'RIDGE', 'PILLOW', 'SCALE'}:
        col.prop(p, 'edge_round', slider=True)
    col.prop(p, 'edge_thickness')
    col.prop(p, 'tip_lift')
    col.prop(p, 'sink')
    col = target.column(align=True)
    col.prop(p, 'outline_smooth', slider=True)
    col.prop(p, 'resolution')
    if ob is not None:
        target.operator('mch.cplate_apply', icon='CHECKMARK')
    col = layout.column(align=True)
    col.scale_y = 0.8
    for line in ('Draw an outline on a mesh: a rounded plate on it', 'Height 0 = Auto, End Height -1 = same',
                 'End Height: the far end lifts (or sinks) like a scale', 'Apply: plain mesh'):
        col.label(text=line)


CLASSES = (MCH_PG_CreaturePlate, MCH_OT_cplate_apply)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_cplate = bpy.props.PointerProperty(type=MCH_PG_CreaturePlate)
    bpy.types.Object.mch_cplate = bpy.props.PointerProperty(type=MCH_PG_CreaturePlate)


def unregister():
    for n, t in (('mch_cplate', bpy.types.Object), ('mch_cplate', bpy.types.Scene)):
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
