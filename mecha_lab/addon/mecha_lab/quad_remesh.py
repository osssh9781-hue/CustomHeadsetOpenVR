"""0.24.48 Quad Remesh that keeps the hard edges left by cuts and booleans.

Two methods: Flow (QuadriFlow) and Patch (the hard edges cut the part into flat patches, each gets an even
grid; see ``build_patch``).  After Flow a check measures how far the old hard edges are from the new ones and
warns when thin slivers got lost.

Make Quad: a copy of the selected part (modifiers baked) is cleaned (close points merged, normals made
consistent), every edge sharper than ``Edge Angle`` (and, if wanted, edges already marked sharp or with a
crease) is marked sharp, then Blender's QuadriFlow rebuilds it as all quads with ``Preserve Sharp`` on, so
the new quad lines run along those edges.  The original is kept, hidden.  Re-make with other settings or
Apply (the copy becomes an ordinary mesh).
"""
from __future__ import annotations

import math
import time

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty

SRC_KEY = 'mch_quad_source'
MISS_KEY = 'mch_quad_miss'
BEVEL = 'MCH_Quad_Bevel'
MISS_LIMIT = 1.0          # warn when more than one quad length of the cut edges got lost (> half a quad away)


class MCH_PG_QuadRemesh(bpy.types.PropertyGroup):
    method: EnumProperty(name='Method', default='FLOW', items=(
        ('FLOW', 'Flow', 'QuadriFlow: flowing quads over the whole part; the hard edges pull the quad lines '
                         'onto them (thin slivers left by a cut can get lost)'),
        ('PATCH', 'Patch', 'The hard edges cut the part into flat patches, each filled with an even grid: '
                           'the hard edges stay exactly; best for flat hard-surface parts')))
    faces: IntProperty(name='Faces', default=4000, min=100, max=200000,
                       description='About this many quads. More = thin chamfers and small cuts keep their shape')
    edge_angle: FloatProperty(name='Edge Angle', default=math.radians(30.0), min=math.radians(1.0),
                              max=math.radians(150.0), subtype='ANGLE',
                              description='Edges sharper than this are kept as hard quad lines')
    keep_marked: BoolProperty(name='Keep Marked Edges', default=True,
                              description='Also keep edges you marked Sharp or gave a Crease')
    smooth_shade: BoolProperty(name='Smooth + Sharp Edges', default=True,
                               description='Shade the result smooth with the kept edges sharp')
    bevel: BoolProperty(name='Bevel Edges', default=False, update=_bevel_update,
                        description='0.24.53 a live Bevel on the kept hard edges of the quad result')
    bevel_edges: EnumProperty(name='Bevel', default='OUTER', update=_bevel_update, items=(
        ('OUTER', 'Outer', 'Only the outside (convex) hard edges; inside corners of pockets stay sharp'),
        ('ALL', 'All', 'Every kept hard edge')))


def _bevel_update(self, context):
    ob = context.active_object
    if is_quad(ob):
        set_bevel(ob, self)


def is_quad(ob):
    return ob is not None and ob.type == 'MESH' and SRC_KEY in ob


def _size(me):
    if not me.vertices:
        return 1.0
    import numpy as np
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    return max(float((co.max(0) - co.min(0)).max()), 1e-9)


def _baked(context, src):
    dg = context.evaluated_depsgraph_get()
    return bpy.data.meshes.new_from_object(src.evaluated_get(dg), preserve_all_data_layers=False, depsgraph=dg)


def _marked(me):
    """Edge indices marked sharp or creased on ``me``."""
    out = set()
    att = me.attributes.get('sharp_edge')
    if att is not None and att.domain == 'EDGE':
        out.update(i for i, d in enumerate(att.data) if d.value)
    att = me.attributes.get('crease_edge')
    if att is not None and att.domain == 'EDGE':
        out.update(i for i, d in enumerate(att.data) if d.value > 0.0)
    return out


def prepare(me, angle, keep_marked=True):
    """Clean ``me`` for QuadriFlow and mark the edges to keep sharp.  Returns (kept edges, open edges)."""
    marked = _marked(me) if keep_marked else set()
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        bm.edges.ensure_lookup_table()
        for i in marked:
            if i < len(bm.edges):
                bm.edges[i].tag = True
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=_size(me) * 1e-5)
        loose = [v for v in bm.verts if not v.link_faces]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context='VERTS')
        bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=_size(me) * 1e-6)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        kept = 0
        open_edges = 0
        for e in bm.edges:
            if not e.is_manifold:
                open_edges += 1
            hard = e.tag or (e.is_manifold and e.calc_face_angle(0.0) > angle)
            e.smooth = not hard
            kept += hard
            e.tag = False
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()
    return kept, open_edges


def _shade(me, angle):
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        for f in bm.faces:
            f.smooth = True
        for e in bm.edges:
            e.smooth = not (not e.is_manifold or e.calc_face_angle(0.0) > angle)
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()


PT_CHUNK = 256                  # 0.24.73 points x segments are compared in blocks: all at once a (N, M, 2) array
SEG_CHUNK = 128                 # (50,000 points x 2,000 segments = 1.6 GB per temporary) took the memory


def _inside(pts, segs):
    """Even-odd test of 2D points (N, 2) against segments (M, 2, 2) (in blocks: the crossings are counted per block)."""
    import numpy as np
    out = np.zeros(len(pts), bool)
    for i in range(0, len(pts), PT_CHUNK):
        p = pts[i:i + PT_CHUNK]
        px, py = p[:, 0:1], p[:, 1:2]
        odd = np.zeros(len(p), bool)
        for j in range(0, len(segs), SEG_CHUNK):
            s = segs[j:j + SEG_CHUNK]
            a, b = s[:, 0], s[:, 1]
            ay, by_ = a[None, :, 1], b[None, :, 1]
            cross = (ay > py) != (by_ > py)
            with np.errstate(divide='ignore', invalid='ignore'):
                x = a[None, :, 0] + (py - ay) * (b[None, :, 0] - a[None, :, 0]) / (by_ - ay)
            odd ^= ((cross & (px < x)).sum(1) % 2) == 1
        out[i:i + len(p)] = odd
    return out


def _seg_dist_block(pts, segs):
    import numpy as np
    a, b = segs[None, :, 0], segs[None, :, 1]
    d = b - a
    t = ((pts[:, None] - a) * d).sum(2) / np.maximum((d * d).sum(2), 1e-30)
    q = a + d * np.clip(t, 0.0, 1.0)[..., None]
    return np.sqrt(((pts[:, None] - q) ** 2).sum(2)).min(1)


def _seg_dist(pts, segs):
    """Distance of each 2D point (N, 2) to the nearest segment (M, 2, 2), in blocks (same result, a fraction of the
    memory)."""
    import numpy as np
    if not len(segs):
        raise ValueError('Quad Remesh: no outline segments')
    out = np.empty(len(pts), np.float64)
    for i in range(0, len(pts), PT_CHUNK):
        p = pts[i:i + PT_CHUNK]
        best = np.full(len(p), np.inf)
        for j in range(0, len(segs), SEG_CHUNK):
            best = np.minimum(best, _seg_dist_block(p, segs[j:j + SEG_CHUNK]))
        out[i:i + len(p)] = best
    return out


def _regions(bm, tol):
    """Faces grouped into flat regions: neighbours across soft edges that lie in the seed face's plane."""
    cos_t = math.cos(math.radians(2.0))
    seen = set()
    out = []
    for seed in sorted(bm.faces, key=lambda f: -f.calc_area()):
        if seed in seen:
            continue
        n0, p0 = seed.normal.copy(), seed.verts[0].co.copy()
        group, stack = [seed], [seed]
        seen.add(seed)
        while stack:
            f = stack.pop()
            for e in f.edges:
                if not e.smooth or not e.is_manifold:
                    continue
                for g in e.link_faces:
                    if g in seen or g.normal.dot(n0) < cos_t:
                        continue
                    if any(abs((v.co - p0).dot(n0)) > tol for v in g.verts):
                        continue
                    seen.add(g)
                    group.append(g)
                    stack.append(g)
        out.append(group)
    return out


def _direction(edges, n):
    """Main direction of a region's outline (length weighted, folded to 90 degrees)."""
    ref = None
    sx = sy = 0.0
    for e in edges:
        d = e.verts[1].co - e.verts[0].co
        d -= n * d.dot(n)
        if d.length < 1e-12:
            continue
        if ref is None:
            ref = d.normalized()
        a = math.atan2(n.cross(ref).dot(d), ref.dot(d)) * 4.0
        sx += d.length * math.cos(a)
        sy += d.length * math.sin(a)
    if ref is None:
        ref = n.orthogonal().normalized()
    a = math.atan2(sy, sx) / 4.0
    u = ref * math.cos(a) + n.cross(ref) * math.sin(a)
    return u.normalized()


def _fill_region(bm, faces, g):
    """Replace a flat region by a grid (spacing ``g``) laid on its main direction, filled up to the outline
    with triangles that are then joined into quads.  Returns the new faces (or None: left as it was)."""
    import numpy as np
    from mathutils import Vector
    from mathutils.geometry import delaunay_2d_cdt
    fs = set(faces)
    border = [e for f in faces for e in f.edges if not all(lf in fs for lf in e.link_faces)]
    border = list(dict.fromkeys(border))
    if len(border) < 3:
        return None
    n = Vector()
    for f in faces:
        n += f.normal * f.calc_area()
    if n.length < 1e-12:
        return None
    n.normalize()
    u = _direction(border, n)
    v = n.cross(u)
    bverts = list(dict.fromkeys(vv for e in border for vv in e.verts))
    index = {vv: i for i, vv in enumerate(bverts)}
    longest = max(border, key=lambda e: e.calc_length())
    o = longest.verts[0].co.copy()
    co2 = np.array([((vv.co - o).dot(u), (vv.co - o).dot(v)) for vv in bverts])
    cons = [(index[e.verts[0]], index[e.verts[1]]) for e in border]
    segs = co2[np.array(cons)]
    lo, hi = co2.min(0), co2.max(0)
    xs = np.arange(math.floor(lo[0] / g), math.ceil(hi[0] / g) + 1) * g
    ys = np.arange(math.floor(lo[1] / g), math.ceil(hi[1] / g) + 1) * g
    grid = np.stack(np.meshgrid(xs, ys), -1).reshape(-1, 2)
    if len(grid):
        grid = grid[_inside(grid, segs)]
    if len(grid):
        grid = grid[_seg_dist(grid, segs) > 0.45 * g]
    pts = [Vector(p) for p in co2] + [Vector(p) for p in grid]
    try:
        out_co, _oe, out_f, orig_v, _o2, _o3 = delaunay_2d_cdt(pts, cons, [], 0, g * 1e-4, True)
    except Exception:
        return None
    if not out_f:
        return None
    def area2(t):
        (ax, ay), (bx, by_), (cx, cy) = (out_co[i][:] for i in t)
        return abs((bx - ax) * (cy - ay) - (by_ - ay) * (cx - ax))

    # collinear outline points (a long edge split in parts) can give flat slivers: they are no faces
    tris = [t for t in out_f if len(t) == 3 and area2(t) > g * g * 1e-6]
    if not tris:
        return None
    cen = np.array([[sum(out_co[i][k] for i in t) / 3.0 for k in (0, 1)] for t in tris])
    keep = _inside(cen, segs)
    nb = len(bverts)
    made = {}

    def vert(i):
        if i not in made:
            ids = [j for j in orig_v[i] if j < nb]
            if ids:
                made[i] = bverts[ids[0]]
            else:
                p = out_co[i]
                made[i] = bm.verts.new(o + u * p[0] + v * p[1])
        return made[i]

    keep_tris = [t for t, k in zip(tris, keep) if k]
    if not keep_tris:
        return None
    bmesh.ops.delete(bm, geom=list(faces), context='FACES_ONLY')
    new = []
    for t in keep_tris:
        vs = [vert(i) for i in t]
        if len(set(vs)) < 3:
            continue
        a, b, c = (x.co for x in vs)
        if (b - a).cross(c - a).dot(n) < 0:
            vs.reverse()
        try:
            new.append(bm.faces.new(vs))
        except ValueError:
            pass
    loose_e = [e for e in bm.edges if not e.link_faces]
    if loose_e:
        bmesh.ops.delete(bm, geom=loose_e, context='EDGES')
    for f in new:
        f.normal_update()                                  # join_triangles compares face normals
    res = bmesh.ops.join_triangles(bm, faces=new, angle_face_threshold=math.radians(5.0),
                                   angle_shape_threshold=math.radians(50.0))
    return res.get('faces', new)


def _split_quads(bm, bvh):
    """Every n-sided face becomes n quads (corner, edge middles, face middle): all quads, the hard edges
    keep their place (their middles stay on them).  New points go onto the old surface."""
    out = bmesh.new()
    vmap = {v: out.verts.new(v.co) for v in bm.verts}
    emid = {}
    for e in bm.edges:
        p = (e.verts[0].co + e.verts[1].co) * 0.5
        if e.smooth:
            hit = bvh.find_nearest(p)
            if hit[0] is not None:
                p = hit[0]
        emid[e] = (out.verts.new(p), e.smooth)
    hard = set()
    for f in bm.faces:
        c = f.calc_center_median()
        hit = bvh.find_nearest(c)
        cv = out.verts.new(hit[0] if hit[0] is not None else c)
        loops = list(f.loops)
        for i, lp in enumerate(loops):
            prev = loops[i - 1]
            m_next, soft_n = emid[lp.edge]
            m_prev, soft_p = emid[prev.edge]
            corner = vmap[lp.vert]
            try:
                out.faces.new((corner, m_next, cv, m_prev))
            except ValueError:
                continue
            if not soft_n:
                hard.add(frozenset((corner, m_next)))
            if not soft_p:
                hard.add(frozenset((corner, m_prev)))
    for e in out.edges:
        e.smooth = frozenset(e.verts) not in hard
    loose = [v for v in out.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(out, geom=loose, context='VERTS')
    return out


def build_patch(me, faces):
    """0.24.48 Patch method: the hard edges cut the part into flat regions; each is filled with an even grid
    lined up with its outline, then split so it is all quads.  The hard edges stay exactly where they were.
    Curved areas (no flat region) keep their own faces, split into quads."""
    from mathutils.bvhtree import BVHTree
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        bvh = BVHTree.FromBMesh(bm)
        area = sum(f.calc_area() for f in bm.faces)
        h = math.sqrt(area / max(faces, 1))
        g = 2.0 * h
        groups = {}
        for e in bm.edges:
            k = int(round(e.calc_length() / g)) - 1
            if k >= 1:
                groups.setdefault(min(k, 400), []).append(e)
        for k, es in groups.items():
            bmesh.ops.subdivide_edges(bm, edges=es, cuts=k, use_grid_fill=False)
        bm.normal_update()
        for group in _regions(bm, _size(me) * 1e-4):
            if len(group) == 1 and len(group[0].verts) == 3:
                continue
            _fill_region(bm, group, g)
        out = _split_quads(bm, bvh)
    finally:
        bm.free()
    try:
        bmesh.ops.recalc_face_normals(out, faces=out.faces)
        out.to_mesh(me)
    finally:
        out.free()
    me.update()


def _edge_miss(src_edges, me, h, angle):
    """How much of the source's hard edges got lost, in quad sizes ``h``: the length along them that is further
    than half a quad from every edge of ``me`` sharper than ``angle``."""
    step = h * 0.25
    from mathutils.kdtree import KDTree
    pts = []
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        for e in bm.edges:
            if not e.is_manifold or e.calc_face_angle(0.0) > angle:
                a, b = e.verts[0].co, e.verts[1].co
                k = max(1, int((a - b).length * 8.0 / step))
                pts += [a.lerp(b, i / k) for i in range(k + 1)]
    finally:
        bm.free()
    if not src_edges:
        return 0.0
    if not pts:                                  # 0.24.73 every hard edge gone is all lost, not "nothing lost"
        return sum((a - b).length for a, b in src_edges) / h
    kd = KDTree(len(pts))
    for i, p in enumerate(pts):
        kd.insert(p, i)
    kd.balance()
    lost = 0.0
    for a, b in src_edges:
        k = max(1, int((a - b).length / step))
        part = (a - b).length / (k + 1)
        lost += part * sum(kd.find(a.lerp(b, i / k))[2] > 0.5 * h for i in range(k + 1))
    return lost / h


def _hard_list(me):
    return [(me.vertices[e.vertices[0]].co.copy(), me.vertices[e.vertices[1]].co.copy())
            for e in me.edges if e.use_edge_sharp]


def build_mesh(context, src, st):
    """The quad mesh (object space of ``src``).  Returns (mesh, kept hard edges, edge miss / quad size)."""
    me = _baked(context, src)
    kept, open_edges = prepare(me, st.edge_angle, st.keep_marked)
    if open_edges:
        bpy.data.meshes.remove(me)
        raise RuntimeError(f'The part has {open_edges} open / non-manifold edges. Close it first '
                           '(Quad Remesh needs a closed solid).')
    if st.method == 'PATCH':
        build_patch(me, st.faces)
        for name in [a.name for a in me.attributes if a.name.startswith('mch_')]:
            me.attributes.remove(me.attributes[name])
        if st.smooth_shade:
            _shade(me, st.edge_angle)
        return me, kept, 0.0
    src_hard = _hard_list(me)
    area = sum(p.area for p in me.polygons)
    tmp = bpy.data.objects.new('MCH_Quad_tmp', me)
    tmp.matrix_world = src.matrix_world.copy()
    context.scene.collection.objects.link(tmp)
    before = len(me.polygons)
    try:
        with context.temp_override(object=tmp, active_object=tmp, selected_objects=[tmp],
                                   selected_editable_objects=[tmp]):
            bpy.ops.object.quadriflow_remesh(use_mesh_symmetry=False, use_preserve_sharp=kept > 0,
                                             use_preserve_boundary=True, preserve_attributes=False,
                                             smooth_normals=False, mode='FACES', target_faces=st.faces, seed=0)
    except RuntimeError as ex:
        bpy.data.objects.remove(tmp, do_unlink=True)
        bpy.data.meshes.remove(me)
        raise RuntimeError('QuadriFlow failed: ' + str(ex).strip())
    bpy.data.objects.remove(tmp, do_unlink=True)
    polys = me.polygons
    if not polys or (len(polys) == before and any(len(p.vertices) != 4 for p in polys)):
        bpy.data.meshes.remove(me)
        raise RuntimeError('QuadriFlow could not remesh this part (try more Faces or a smaller Edge Angle).')
    for name in [a.name for a in me.attributes if a.name.startswith('mch_')]:
        me.attributes.remove(me.attributes[name])
    if st.smooth_shade:
        _shade(me, st.edge_angle)
    h = math.sqrt(area / max(st.faces, 1))
    miss = _edge_miss(src_hard, me, h, st.edge_angle * 0.6)
    return me, kept, miss


def edge_weights(me, outer=True):
    """Bevel weight 1 on the hard (sharp marked) edges - only the convex ones with ``outer``.  Returns how many."""
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        lay = bm.edges.layers.float.get('bevel_weight_edge') or bm.edges.layers.float.new('bevel_weight_edge')
        n = 0
        for e in bm.edges:
            w = 0.0
            if not e.smooth and e.is_manifold:
                f1, f2 = e.link_faces
                if not outer or (f2.calc_center_median() - f1.calc_center_median()).dot(f1.normal) < 0.0:
                    w = 1.0
            e[lay] = w
            n += w > 0.0
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()
    return n


def set_bevel(ob, st):
    """Add / update / remove the live Bevel of a quad result (width, segments, profile stay as the user set them)."""
    bev = ob.modifiers.get(BEVEL)
    if not st.bevel:
        if bev is not None:
            ob.modifiers.remove(bev)
        return None
    edge_weights(ob.data, st.bevel_edges == 'OUTER')
    if bev is None:
        bev = ob.modifiers.new(BEVEL, 'BEVEL')
        bev.width = _size(ob.data) * 0.01
        bev.segments = 2                                   # an even count keeps the corners all quads
        bev.profile = 0.5
    bev.limit_method = 'WEIGHT'
    bev.use_clamp_overlap = True
    bev.harden_normals = True
    bev.miter_outer = 'MITER_ARC'
    return bev


def make(context, src, st):
    if src is None or src.type != 'MESH':
        raise RuntimeError('Select a mesh part first.')
    me, kept, miss = build_mesh(context, src, st)
    me.name = src.name + '_Quad'
    ob = bpy.data.objects.new(src.name + '_Quad', me)
    for coll in src.users_collection:
        coll.objects.link(ob)
    ob.matrix_world = src.matrix_world.copy()
    for mat in src.data.materials:
        me.materials.append(mat)
    ob[SRC_KEY] = src.name
    set_bevel(ob, st)
    src.hide_set(True)
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    return ob, kept, miss


def remake(context, ob, st):
    src = bpy.data.objects.get(ob.get(SRC_KEY, ''))
    if src is None:
        raise RuntimeError('The original part is gone; cannot re-make.')
    me, kept, miss = build_mesh(context, src, st)
    old = ob.data
    me.name = old.name
    for mat in old.materials:
        me.materials.append(mat)
    ob.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    set_bevel(ob, st)
    return ob, kept, miss


class MCH_OT_quad_make(bpy.types.Operator):
    """All-quad copy of the selected part; the hard edges from cuts / booleans stay as quad lines
    (the original is kept, hidden)"""
    bl_idname = 'mch.quad_remesh'
    bl_label = 'Quad Remesh (keep edges)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.type == 'MESH'

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        st = context.scene.mch_quadremesh
        ob = context.active_object
        t = time.time()
        try:
            if is_quad(ob):
                ob, kept, miss = remake(context, ob, st)
            else:
                ob, kept, miss = make(context, ob, st)
        except RuntimeError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        ob[MISS_KEY] = miss
        note = f'{ob.name}: {len(ob.data.polygons)} quads, {kept} hard edges kept ({time.time() - t:.1f} s)'
        if miss > MISS_LIMIT:
            self.report({'WARNING'}, note + '. Some cut edges were not kept (thin slivers): raise Faces '
                                            'or use the Patch method')
        else:
            self.report({'INFO'}, note)
        return {'FINISHED'}


class MCH_OT_quad_apply(bpy.types.Operator):
    """Keep the quad mesh as an ordinary mesh, the Bevel made permanent (the hidden original stays in the file)"""
    bl_idname = 'mch.quad_apply'
    bl_label = 'Apply Quad'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return is_quad(context.active_object)

    def execute(self, context):
        ob = context.active_object
        if ob.modifiers.get(BEVEL) is not None:
            with context.temp_override(object=ob, active_object=ob, selected_objects=[ob],
                                       selected_editable_objects=[ob]):
                bpy.ops.object.modifier_apply(modifier=BEVEL)
        del ob[SRC_KEY]
        if MISS_KEY in ob:
            del ob[MISS_KEY]
        return {'FINISHED'}


class MCH_OT_quad_show_source(bpy.types.Operator):
    """Show / hide the original part"""
    bl_idname = 'mch.quad_show_source'
    bl_label = 'Show Original'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return is_quad(context.active_object)

    def execute(self, context):
        src = bpy.data.objects.get(context.active_object.get(SRC_KEY, ''))
        if src is not None:
            src.hide_set(not src.hide_get())
        return {'FINISHED'}


def draw(layout, context):
    st = context.scene.mch_quadremesh
    ob = context.active_object
    box = layout.box()
    box.label(text='QUAD REMESH (keep cut edges)', icon='MOD_REMESH')
    box.row(align=True).prop(st, 'method', expand=True)
    col = box.column(align=True)
    col.prop(st, 'faces')
    col.prop(st, 'edge_angle')
    col.prop(st, 'keep_marked')
    col.prop(st, 'smooth_shade')
    row = box.row(align=True)
    row.scale_y = 1.3
    row.operator('mch.quad_remesh', text='Re-make Quad' if is_quad(ob) else 'Make Quad',
                 icon='FILE_REFRESH' if is_quad(ob) else 'MOD_REMESH')
    col = box.column(align=True)
    row = col.row(align=True)
    row.prop(st, 'bevel')
    if st.bevel:
        row.prop(st, 'bevel_edges', expand=True)
        bev = ob.modifiers.get(BEVEL) if is_quad(ob) else None
        if bev is not None:
            col.prop(bev, 'width')
            col.prop(bev, 'segments', text='Segments (even = all quads)')
            col.prop(bev, 'profile', slider=True)
    if is_quad(ob):
        box.label(text=f'{len(ob.data.polygons)} quads')
        if ob.get(MISS_KEY, 0.0) > MISS_LIMIT:
            box.label(text='Some cut edges got lost: raise Faces or use Patch', icon='ERROR')
        row = box.row(align=True)
        row.operator('mch.quad_show_source', icon='HIDE_OFF')
        row.operator('mch.quad_apply', icon='CHECKMARK')
    else:
        box.label(text='Needs a closed part. Big meshes take a while', icon='INFO')
    if st.method == 'FLOW':
        box.label(text='Thin slivers from cuts: raise Faces or use Patch', icon='INFO')


CLASSES = (MCH_PG_QuadRemesh, MCH_OT_quad_make, MCH_OT_quad_apply, MCH_OT_quad_show_source)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_quadremesh = bpy.props.PointerProperty(type=MCH_PG_QuadRemesh)


def unregister():
    if hasattr(bpy.types.Scene, 'mch_quadremesh'):
        del bpy.types.Scene.mch_quadremesh
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
