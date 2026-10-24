"""0.24.32 Quad Cloth: your own quad retopo -> select faces in Edit Mode -> turn them into Cloth, Rib Knit or Padding.

The selected faces are copied to a new object (quads kept); the source faces are only hidden (Alt+H shows them).
* Cloth: the panel gets some slack (Loose / Extra Length) and is simulated with Blender's Cloth (gravity, the body
  as collider, pinned where it joins the rest of your mesh / at the top / its open edges), then the result is kept.
* Rib Knit (cuffs, hems, collars): pulled snug onto the body, ridges running across the band.
* Padding (puffer): every quad becomes a quilted pillow, the original edges stay as stitched seams.
A Solidify modifier gives the thickness (still editable).  Works in Blender 5.0 and 5.2.
``rib_wave`` and ``pillow_weight`` are pure.
"""
from __future__ import annotations

import math

import bmesh
import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

KIND_ITEMS = [
    ('CLOTH', 'Cloth', 'Simulated cloth: hangs and folds under gravity over the body'),
    ('RIB', 'Rib Knit', 'Snug knitted band (cuffs, hems, collars) with ridges across it'),
    ('PADDING', 'Padding', 'Quilted puffer: each quad becomes a pillow, the edges stay stitched'),
]
PIN_ITEMS = [
    ('SEAM', 'Joins', 'Pin where the selection meets the rest of your mesh (falls back to Top)'),
    ('TOP', 'Top', 'Pin the highest open edge (waistband, neckline, shoulders)'),
    ('OPEN', 'All Open Edges', 'Pin every open edge (only the inside moves)'),
    ('NONE', 'None', 'Nothing pinned (it rests on the body)'),
]
FABRIC_ITEMS = [
    ('SILK', 'Silk', 'Light and soft, many small folds'),
    ('COTTON', 'Cotton', 'Shirts, hoodies'),
    ('DENIM', 'Denim', 'Heavier, bigger folds'),
    ('LEATHER', 'Leather', 'Stiff, few big folds'),
]
FABRICS = {          # mass, tension, bending
    'SILK': (0.15, 5.0, 0.05),
    'COTTON': (0.3, 15.0, 0.5),
    'DENIM': (0.4, 40.0, 10.0),
    'LEATHER': (0.4, 80.0, 50.0),
}
SUFFIX = {'CLOTH': '_Cloth', 'RIB': '_Rib', 'PADDING': '_Pad'}


class QuadClothError(Exception):
    pass


def rib_wave(t):
    """Rib profile for a phase t (in ridges): 1 on a ridge, 0 in the groove, smooth between."""
    return 0.5 + 0.5 * math.cos(2.0 * math.pi * t)


def pillow_weight(d, half):
    """Puff for a vertex d steps from the nearest seam, half = steps to the cell middle (0 at the seam, 1 middle)."""
    if half <= 0:
        return 0.0
    x = min(1.0, d / float(half))
    return math.sin(0.5 * math.pi * x) ** 0.8


# -----------------------------------------------------------------------------
# helpers
# -----------------------------------------------------------------------------


def _world_bvh(context, ob):
    dg = context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        verts = [ob.matrix_world @ v.co for v in me.vertices]
        polys = [tuple(p.vertices) for p in me.polygons]
    finally:
        ev.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys), verts


def _bounds(points):
    lo = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    hi = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    return lo, hi


def pick_body(context, source, points):
    """The collider: the setting if given, else the biggest other visible mesh overlapping the selection, else the
    source mesh itself (faces picked straight from the body)."""
    st = context.scene.mch_quad_cloth
    if st.body is not None and st.body.type == 'MESH':
        return st.body
    lo, hi = _bounds(points)
    best, best_n = None, 0
    for ob in context.visible_objects:
        if ob is source or ob.type != 'MESH' or SUFFIX_KEY in ob:
            continue
        corners = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        blo, bhi = _bounds(corners)
        if all(blo[i] <= hi[i] and bhi[i] >= lo[i] for i in range(3)):
            n = len(ob.data.vertices)
            if n > best_n:
                best, best_n = ob, n
    return best if best is not None else source


SUFFIX_KEY = 'mch_quad_cloth'


def copy_selection(source, hide=False):
    """Selected faces of the edit mesh -> (bmesh in world space, set of seam vert indices, faces, quads); hide =
    hide those faces in the source."""
    src = bmesh.from_edit_mesh(source.data)
    faces = [f for f in src.faces if f.select and not f.hide]
    if not faces:
        raise QuadClothError('Select the quad faces to turn into cloth (Edit Mode, face select).')
    sel = set(faces)
    out = bmesh.new()
    vmap, seam = {}, set()
    mw = source.matrix_world
    for f in faces:
        for v in f.verts:
            if v not in vmap:
                nv = out.verts.new(mw @ v.co)
                vmap[v] = nv
                if any(g not in sel and not g.hide for g in v.link_faces):
                    seam.add(nv)
    for f in faces:
        try:
            out.faces.new([vmap[v] for v in f.verts])
        except ValueError:
            pass
    out.verts.ensure_lookup_table()
    out.verts.index_update()
    quads = sum(1 for f in faces if len(f.verts) == 4)
    if hide:
        for f in faces:
            f.hide_set(True)
    bmesh.update_edit_mesh(source.data)
    return out, {v.index for v in seam}, len(faces), quads


def orient_outward(bm, bvh):
    """Face normals away from the body (so offsets / puffs go outward)."""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    score = 0.0
    for f in bm.faces:
        c = f.calc_center_median()
        hit = bvh.find_nearest(c)
        if hit[0] is not None:
            score += (c - hit[0]).dot(f.normal) * f.calc_area()
    if score < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        bm.normal_update()


def _smooth_normals(bm, passes=3):
    nrm = {v: v.normal.copy() for v in bm.verts}
    for _ in range(passes):
        new = {}
        for v in bm.verts:
            acc = nrm[v].copy()
            for e in v.link_edges:
                acc += nrm[e.other_vert(v)]
            new[v] = acc.normalized() if acc.length > 1e-9 else nrm[v]
        nrm = new
    return nrm


def _pin_set(bm, mode, seam):
    boundary = {v.index for v in bm.verts if v.is_boundary}
    if mode == 'NONE':
        return set()
    if mode == 'SEAM' and seam:
        return set(seam)
    if mode == 'OPEN':
        return boundary
    # TOP (also the fallback): the open edge verts near the highest point
    pts = [bm.verts[i] for i in boundary] or list(bm.verts)
    zs = [v.co.z for v in bm.verts]
    span = max(zs) - min(zs)
    ztop = max(v.co.z for v in pts)
    return {v.index for v in pts if v.co.z > ztop - max(1e-4, span * 0.04)}


def _new_object(context, source, bm, kind):
    me = bpy.data.meshes.new(source.name + SUFFIX[kind])
    bm.to_mesh(me)
    for p in me.polygons:
        p.use_smooth = True
    for mat in source.data.materials:
        me.materials.append(mat)
    ob = bpy.data.objects.new(me.name, me)
    cols = source.users_collection or [context.scene.collection]
    cols[0].objects.link(ob)
    ob[SUFFIX_KEY] = kind
    return ob


def _add_thickness(ob, thickness):
    if thickness <= 0:
        return
    m = ob.modifiers.new('MCH Thickness', 'SOLIDIFY')
    m.thickness = thickness
    m.offset = 0.0
    m.use_even_offset = False
    m.thickness_clamp = 1.0             # never thicker than the faces are wide (no spikes on crumpled spots)
    m.use_quality_normals = True


# -----------------------------------------------------------------------------
# the three kinds
# -----------------------------------------------------------------------------


def simulate_cloth(context, ob, body, pins, frames, fabric, distance):
    """Blender Cloth on ob (gravity, body collider, pins), keep the last frame, clean up everything it added."""
    scene = context.scene
    added_col = None
    if body is not None and body is not ob and not any(m.type == 'COLLISION' for m in body.modifiers):
        added_col = body.modifiers.new('MCH Temp Collision', 'COLLISION')
        body.collision.thickness_outer = distance
    vg = None
    if pins:
        vg = ob.vertex_groups.new(name='MCH Pin')
        vg.add(sorted(pins), 1.0, 'REPLACE')
    mass, tension, bending = FABRICS.get(fabric, FABRICS['COTTON'])
    mod = ob.modifiers.new('MCH Cloth', 'CLOTH')
    cs = mod.settings
    cs.quality = 6
    cs.mass = mass
    cs.tension_stiffness = cs.compression_stiffness = tension
    cs.shear_stiffness = tension * 0.4
    cs.bending_stiffness = bending
    if vg is not None:
        cs.vertex_group_mass = vg.name
    mod.collision_settings.distance_min = distance
    mod.collision_settings.use_self_collision = True
    mod.collision_settings.self_distance_min = distance
    old_frame = scene.frame_current
    start = scene.frame_start
    mod.point_cache.frame_start = start
    mod.point_cache.frame_end = start + frames
    try:
        for f in range(start, start + frames + 1):
            scene.frame_set(f)
        dg = context.evaluated_depsgraph_get()
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        try:
            coords = [v.co.copy() for v in me.vertices]
        finally:
            ev.to_mesh_clear()
    finally:
        ob.modifiers.remove(mod)
        if vg is not None:
            ob.vertex_groups.remove(vg)
        if added_col is not None:
            body.modifiers.remove(added_col)
        scene.frame_set(old_frame)
    if len(coords) == len(ob.data.vertices):
        for v, c in zip(ob.data.vertices, coords):
            v.co = c
        ob.data.update()


def _boundary_loops(bm):
    """Open edge loops as ordered vert lists."""
    edges = {e for e in bm.edges if e.is_boundary}
    loops = []
    while edges:
        e = edges.pop()
        loop = [e.verts[0], e.verts[1]]
        grow = True
        while grow:
            grow = False
            tail = loop[-1]
            for f in tail.link_edges:
                if f in edges:
                    w = f.other_vert(tail)
                    edges.discard(f)
                    if w is loop[0]:
                        break
                    loop.append(w)
                    grow = True
                    break
        loops.append(loop)
    return loops


def _relax(bm, passes, factor, keep=()):
    keep = set(keep)
    for _ in range(passes):
        new = {}
        for v in bm.verts:
            if v in keep or v.is_boundary or not v.link_edges:
                continue
            avg = sum((e.other_vert(v).co for e in v.link_edges), Vector()) / len(v.link_edges)
            new[v] = v.co.lerp(avg, factor)
        for v, c in new.items():
            v.co = c


def _subdivide(bm, cuts):
    """Split every quad into (cuts+1)^2 quads (quads stay quads)."""
    if cuts > 0:
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    bm.normal_update()


def _add_smooth(ob, levels=1):
    if levels > 0:
        m = ob.modifiers.new('MCH Smooth', 'SUBSURF')
        m.levels = m.render_levels = levels


def make_cloth(context, source, bm, seam, body, bvh, size, st):
    orient_outward(bm, bvh)
    seam_pts = [bm.verts[i].co.copy() for i in seam]
    _subdivide(bm, st.sim_res)                           # finer cloth = real folds
    if seam_pts:                                         # joins after the split: on / between the old seam verts
        from mathutils.kdtree import KDTree
        kd = KDTree(len(seam_pts))
        for i, c in enumerate(seam_pts):
            kd.insert(c, i)
        kd.balance()
        tol = size * 1e-5
        new_seam = set()
        for v in bm.verts:
            if not v.is_boundary:
                continue
            near = kd.find_n(v.co, 2)
            if near and near[0][2] < tol:
                new_seam.add(v.index)
            elif len(near) == 2:
                a, b_ = near[0][0], near[1][0]
                if abs((v.co - a).length + (v.co - b_).length - (a - b_).length) < tol * 10:
                    new_seam.add(v.index)
        seam = new_seam
    nrm = _smooth_normals(bm)
    loose = st.loose * size
    for v in bm.verts:
        v.co += nrm[v] * loose
    if st.extra_length > 0:
        ztop = max(v.co.z for v in bm.verts)
        for v in bm.verts:
            v.co.z = ztop - (ztop - v.co.z) * (1.0 + st.extra_length)
    pins = _pin_set(bm, st.pin, seam)
    ob = _new_object(context, source, bm, 'CLOTH')
    simulate_cloth(context, ob, body, pins, st.frames, st.fabric, max(1e-4, size * 0.002))
    # calm the sim noise a little (pins and open edges stay)
    sb = bmesh.new()
    sb.from_mesh(ob.data)
    sb.verts.ensure_lookup_table()
    _relax(sb, 2, 0.3, keep=[sb.verts[i] for i in pins])
    sb.to_mesh(ob.data)
    sb.free()
    _add_thickness(ob, st.thickness * size)
    _add_smooth(ob, 1)
    return ob, len(pins)


def make_rib(context, source, bm, body, bvh, size, st):
    orient_outward(bm, bvh)
    pitch = max(1e-5, st.rib_pitch * size)
    edge = sum(e.calc_length() for e in bm.edges) / max(1, len(bm.edges))
    _subdivide(bm, max(1, min(5, int(math.ceil(2.5 * edge / pitch)) - 1)))   # enough verts per ridge
    nrm = _smooth_normals(bm, 2)
    # snug: the whole band moves in by the same amount (keeps your retopo smooth, no body bumps)
    gaps = []
    for v in bm.verts:
        hit = bvh.find_nearest(v.co)
        if hit[0] is not None:
            gaps.append((v.co - hit[0]).length)
    if gaps:
        shift = max(0.0, sorted(gaps)[len(gaps) // 2] - st.rib_fit * size)
        for v in bm.verts:
            v.co -= nrm[v] * shift
    # ridges across the band: phase = arc length along the longest open edge (follows your quad flow)
    loops = _boundary_loops(bm)
    if loops:
        ref = max(loops, key=lambda lp: sum((lp[i].co - lp[i - 1].co).length for i in range(1, len(lp))))
        arc = [0.0]
        for i in range(1, len(ref)):
            arc.append(arc[-1] + (ref[i].co - ref[i - 1].co).length)
        closed = (ref[0].co - ref[-1].co).length < edge * 2
        total = arc[-1] + ((ref[0].co - ref[-1].co).length if closed else 0.0)
        n = max(4, int(round(total / pitch)))
        step = total / n                                 # whole number of ridges round a closed band
        from mathutils.kdtree import KDTree
        kd = KDTree(len(ref))
        for i, v in enumerate(ref):
            kd.insert(v.co, i)
        kd.balance()
        depth = st.rib_depth * size
        for v in bm.verts:
            _co, i, _d = kd.find(v.co)
            v.co += nrm[v] * (depth * rib_wave(arc[i] / step) ** 0.7)
    ob = _new_object(context, source, bm, 'RIB')
    _add_thickness(ob, st.thickness * size * 1.3)
    _add_smooth(ob, 1)
    return ob


def make_padding(context, source, bm, body, bvh, size, st):
    orient_outward(bm, bvh)
    corners = {tuple(round(c, 6) for c in v.co) for v in bm.verts}   # (subdivide re-creates the verts)
    cuts = max(1, st.pad_cuts)
    res = bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    seam = {g for g in res.get('geom_split', []) if isinstance(g, bmesh.types.BMVert)}   # on the old edges
    seam.update(v for v in bm.verts if tuple(round(c, 6) for c in v.co) in corners)   # old corners
    bm.normal_update()
    dist = {v: 0 for v in seam}                          # steps from the seams (breadth first)
    frontier = list(seam)
    while frontier:
        nxt = []
        for v in frontier:
            for e in v.link_edges:
                w = e.other_vert(v)
                if w not in dist:
                    dist[w] = dist[v] + 1
                    nxt.append(w)
        frontier = nxt
    half = (cuts + 1) / 2.0
    nrm = _smooth_normals(bm, 2)
    puff = st.puff * size
    for v in bm.verts:
        w = pillow_weight(dist.get(v, 0), half)
        # full, flat-topped pillow; the stitch line pulled in a little
        v.co += nrm[v] * (puff * (w ** 0.45) if v not in seam else -puff * 0.12)
    ob = _new_object(context, source, bm, 'PADDING')
    _add_thickness(ob, st.thickness * size)
    _add_smooth(ob, 1)
    return ob


# -----------------------------------------------------------------------------
# operator / settings / panel
# -----------------------------------------------------------------------------


def perform(context, kind=None):
    """Edit Mode selection of the active mesh -> a new cloth / rib / padding object.  Returns (object, report)."""
    source = context.active_object
    if source is None or source.type != 'MESH' or source.mode != 'EDIT':
        raise QuadClothError('Edit Mode on your retopo mesh, select the quad faces first.')
    st = context.scene.mch_quad_cloth
    kind = kind or st.kind
    bm, seam, nfaces, quads = copy_selection(source, st.hide_source)
    bpy.ops.object.mode_set(mode='OBJECT')
    try:
        pts = [v.co for v in bm.verts]
        body = pick_body(context, source, pts)
        bvh, bverts = _world_bvh(context, body)
        lo, hi = _bounds(bverts)
        size = max(1e-4, hi.z - lo.z)                    # body height: all distances are a part of it
        if kind == 'CLOTH':
            ob, npin = make_cloth(context, source, bm, seam, body, bvh, size, st)
            extra = f', {npin} pinned, {st.frames} frames'
        elif kind == 'RIB':
            ob = make_rib(context, source, bm, body, bvh, size, st)
            extra = ''
        else:
            ob = make_padding(context, source, bm, body, bvh, size, st)
            extra = ''
    finally:
        bm.free()
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    name = dict((k[0], k[1]) for k in KIND_ITEMS)[kind]
    msg = f'{name} "{ob.name}" from {nfaces} faces ({quads} quads) on {body.name}{extra}'
    return ob, msg


class MCH_PG_QuadCloth(bpy.types.PropertyGroup):
    kind: EnumProperty(name='Type', items=KIND_ITEMS, default='CLOTH')
    body: PointerProperty(name='Body', type=bpy.types.Object, poll=lambda self, o: o.type == 'MESH',
                          description='Collider / surface (empty = the biggest mesh under the selection)')
    hide_source: BoolProperty(name='Hide Source Faces', default=True,
                              description='Hide the selected faces of your mesh (Alt+H shows them again)')
    thickness: FloatProperty(name='Thickness', default=0.003, min=0.0, max=0.05, precision=4,
                             description='Cloth thickness (part of the body height)')
    # cloth
    fabric: EnumProperty(name='Fabric', items=FABRIC_ITEMS, default='COTTON')
    pin: EnumProperty(name='Pin', items=PIN_ITEMS, default='SEAM')
    loose: FloatProperty(name='Loose', default=0.008, min=0.0, max=0.1, precision=4,
                         description='Moves the panel off the body before it falls (part of the body height)')
    extra_length: FloatProperty(name='Extra Length', default=0.04, min=0.0, max=0.5,
                                description='Longer than the retopo: the spare cloth turns into folds')
    frames: IntProperty(name='Frames', default=60, min=5, max=400, description='Simulation length')
    sim_res: IntProperty(name='Detail', default=1, min=0, max=3,
                         description='Each quad is split this many times before the sim (finer folds, slower)')
    # rib
    rib_fit: FloatProperty(name='Snug', default=0.004, min=0.0, max=0.05, precision=4,
                           description='Distance from the body (part of the body height)')
    rib_pitch: FloatProperty(name='Rib Width', default=0.005, min=0.001, max=0.05, precision=4)
    rib_depth: FloatProperty(name='Rib Depth', default=0.0018, min=0.0, max=0.03, precision=4)
    # padding
    puff: FloatProperty(name='Puff', default=0.012, min=0.0, max=0.08, precision=4,
                        description='How far each quad swells out (part of the body height)')
    pad_cuts: IntProperty(name='Smoothness', default=4, min=1, max=8, description='Cuts per quad')


class MCH_OT_quad_cloth(bpy.types.Operator):
    bl_idname = 'mch.quad_cloth'
    bl_label = 'Quad Cloth'
    bl_description = 'Turn the selected quad faces into Cloth, Rib Knit or Padding (a new object)'
    bl_options = {'REGISTER', 'UNDO'}

    kind: EnumProperty(name='Type', items=KIND_ITEMS, default='CLOTH')

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.type == 'MESH' and context.mode == 'EDIT_MESH'

    def invoke(self, context, event):
        self.kind = context.scene.mch_quad_cloth.kind
        return self.execute(context)

    def execute(self, context):
        try:
            _ob, msg = perform(context, self.kind)
        except QuadClothError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


def draw(layout, context):
    st = context.scene.mch_quad_cloth
    box = layout.box()
    box.label(text='Selected quads -> new piece', icon='MOD_CLOTH')
    box.row(align=True).prop(st, 'kind', expand=True)
    box.prop(st, 'body')
    col = box.column(align=True)
    if st.kind == 'CLOTH':
        col.prop(st, 'fabric')
        col.prop(st, 'pin')
        col.prop(st, 'loose', slider=True)
        col.prop(st, 'extra_length', slider=True)
        col.prop(st, 'frames')
        col.prop(st, 'sim_res')
    elif st.kind == 'RIB':
        col.prop(st, 'rib_fit', slider=True)
        col.prop(st, 'rib_pitch', slider=True)
        col.prop(st, 'rib_depth', slider=True)
    else:
        col.prop(st, 'puff', slider=True)
        col.prop(st, 'pad_cuts')
    col = box.column(align=True)
    col.prop(st, 'thickness', slider=True)
    col.prop(st, 'hide_source')
    row = box.row()
    row.scale_y = 1.4
    label = {'CLOTH': 'MAKE CLOTH', 'RIB': 'MAKE RIB KNIT', 'PADDING': 'MAKE PADDING'}[st.kind]
    row.operator('mch.quad_cloth', text=label, icon='MOD_CLOTH').kind = st.kind
    col = layout.column(align=True)
    col.scale_y = 0.8
    for line in ('Edit Mode: select the quads of your retopo', 'Cloth: simulated (a few seconds)',
                 'Rib: cuffs / hems / collars', 'Padding: every quad puffs up'):
        col.label(text=line)


class MCH_PT_quad_cloth(bpy.types.Panel):
    bl_label = 'Quad Cloth'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Mecha Lab'

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def draw(self, context):
        draw(self.layout, context)


def _menu(self, context):
    self.layout.separator()
    self.layout.operator_menu_enum('mch.quad_cloth', 'kind', text='Mecha Quad Cloth', icon='MOD_CLOTH')


CLASSES = (MCH_PG_QuadCloth, MCH_OT_quad_cloth, MCH_PT_quad_cloth)
_MENUS = ('VIEW3D_MT_edit_mesh_faces', 'VIEW3D_MT_edit_mesh_context_menu')


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_quad_cloth = PointerProperty(type=MCH_PG_QuadCloth)
    for name in _MENUS:
        menu = getattr(bpy.types, name, None)
        if menu is not None:
            menu.append(_menu)


def unregister():
    for name in _MENUS:
        menu = getattr(bpy.types, name, None)
        if menu is not None:
            try:
                menu.remove(_menu)
            except (ValueError, RuntimeError):
                pass
    try:
        del bpy.types.Scene.mch_quad_cloth
    except AttributeError:
        pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
