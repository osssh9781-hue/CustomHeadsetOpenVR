"""0.24.183 Mecha Holes (user, with mecha detail photos: "저 메카 표면 디테일 홀은 다른 메쉬에 라쏘로 그릴 수 있게 서페이스
디테일로 넣어 줘"; "홀이랑 끝부분 마감 메쉬도"): draw an outline on a part - a panel on its surface in that shape: a raised
frame round it (the finishing edge), the floor inside a little lower, and a pattern of holes in the floor (Square,
Round, Hex, Slots, Diamond - or Hex Tiles: raised tiles with grooves between).  A mesh of its own lying on the part,
following its curve (light: the floor's flat parts merged, the holes' walls exact).  Live until Apply.
"""
from __future__ import annotations

import json
import math

import bpy
import numpy as np
from bpy.props import EnumProperty, FloatProperty, FloatVectorProperty, PointerProperty
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

KEY = 'mch_mholes'
DONE = 'mch_mholes_done'
PATTERNS = (('SQUARE', 'Square', 'Square holes in rows (dots)'),
            ('ROUND', 'Round', 'Round holes in rows'),
            ('HEX', 'Hex', 'Six-sided holes, every other row half a hole on (honeycomb)'),
            ('SLOT', 'Slots', 'Long slots'),
            ('DIAMOND', 'Diamond', 'Diamond holes'),
            ('TILES', 'Hex Tiles', 'Raised six-sided tiles, grooves between them'))
_BUSY = [False]
_BVH = {}


def is_holes(ob):
    return ob is not None and bool(ob.get(KEY))


def active_holes(context):
    ob = getattr(context, 'active_object', None)
    return ob if is_holes(ob) else None


def data(ob):
    try:
        return json.loads(ob.get(KEY, '{}'))
    except ValueError:
        return {}


def pattern_field(kind, XY, cell, angle):
    """Each point's distance-like value to the middle of its hole's cell (0 at the middle, 0.5 at the cell's edge):
    the hole is where it is under Hole Size / 2."""
    c, s = math.cos(angle), math.sin(angle)
    u = (XY[:, 0] * c + XY[:, 1] * s) / cell
    v = (-XY[:, 0] * s + XY[:, 1] * c) / cell
    if kind in {'HEX', 'TILES'}:
        v = v / 0.866
        row = np.floor(v)
        u = u + 0.5 * (row % 2)
    fu = u - np.floor(u) - 0.5
    fv = v - np.floor(v) - 0.5
    if kind in {'HEX', 'TILES'}:
        fv = fv * 0.866
        a = np.abs(fu)
        b = np.abs(fv)
        return np.maximum(a, a * 0.5 + b * 0.866)
    if kind == 'ROUND':
        return np.sqrt(fu * fu + fv * fv)
    if kind == 'SLOT':
        return np.maximum(np.abs(fu) / 0.45, np.abs(fv) / 1.0) * 0.5
    if kind == 'DIAMOND':
        return np.abs(fu) + np.abs(fv)
    return np.maximum(np.abs(fu), np.abs(fv))


def heights(F, pg, size):
    """The panel's top over the surface: the frame raised at the outline (a bevel up to it), the floor inside a little
    lower, the holes sunk to just over the surface (Hex Tiles: the tiles raised, the grooves sunk)."""
    d, hk = F['d'], F['hk']
    fw = max(float(pg.frame_width), 1e-4) * size
    fh = float(pg.frame_height) * size
    flo = float(pg.floor_height) * size
    hole = float(pg.hole_size) * 0.5
    bev = fw * 0.3
    z = np.where(d < bev, fh * np.clip(d / bev, 0.0, 1.0) ** 0.5, fh)
    inner = d >= fw
    rim_in = (d >= fw * 0.82) & (d < fw)                  # (the frame's inner side: a short slope down)
    z = np.where(rim_in, fh + (flo - fh) * (d - fw * 0.82) / (fw * 0.18), z)
    if pg.pattern == 'TILES':
        groove = hk > hole
        z = np.where(inner, np.where(groove, flo * 0.35, flo + fh * 0.25), z)
    else:
        pit = hk < hole
        z = np.where(inner, np.where(pit, size * 0.0015, flo), z)
    return z


HOLE_SIDES = {'SQUARE': 4, 'ROUND': 14, 'HEX': 6, 'SLOT': 14, 'DIAMOND': 4, 'TILES': 6}


def hole_ring(kind, c, r, angle):
    """A hole's outline (k, 2) round ``c``, as big as ``r`` (half a cell x Hole Size)."""
    k = HOLE_SIDES[kind]
    ca, sa = math.cos(angle), math.sin(angle)
    pts = []
    for q in range(k):
        a = 2 * math.pi * q / k
        if kind == 'SQUARE':
            a += math.pi / 4
            x, y = math.cos(a) * r * math.sqrt(2), math.sin(a) * r * math.sqrt(2)
        elif kind == 'SLOT':                          # (a stadium: long along the rows' other way)
            x, y = math.cos(a) * r * 0.45, math.sin(a) * r * 1.0
            y += math.copysign(r * 0.55, y) if abs(y) > 1e-9 else 0.0
            y *= 0.75
        elif kind in {'HEX', 'TILES'}:
            a += math.pi / 6
            x, y = math.cos(a) * r * 1.12, math.sin(a) * r * 1.12
        else:                                         # ROUND, DIAMOND
            x, y = math.cos(a) * r, math.sin(a) * r
        pts.append((c[0] + x * ca - y * sa, c[1] + x * sa + y * ca))
    return np.array(pts)


def hole_centres(kind, P2, cell, angle):
    """The cells' middles over the outline (rows turned by Angle; Hex / Tiles: every other row half a cell on)."""
    lo, hi = P2.min(0), P2.max(0)
    span = float(np.linalg.norm(hi - lo))
    c0 = (lo + hi) * 0.5
    ca, sa = math.cos(angle), math.sin(angle)
    hexy = kind in {'HEX', 'TILES'}
    dv = cell * (0.866 if hexy else 1.0)
    nu, nv = int(span / cell) + 2, int(span / dv) + 2
    out = []
    for j in range(-nv, nv + 1):
        for i in range(-nu, nu + 1):
            u = (i + (0.5 if hexy and j % 2 else 0.0)) * cell
            v = j * dv
            out.append((c0[0] + u * ca - v * sa, c0[1] + u * sa + v * ca))
    return np.array(out)


def build_mesh(P2, pg, size):
    """(V2 (n, 2), top heights, triangles, distance to the outline): the outline's area in coarse triangles, every
    hole an exact polygon (its rim and its foot) in it, the frame's edges cut in exactly."""
    import bmesh
    from mathutils import geometry
    from .creature_hair import outline_distance
    from .organic_mass import _densify, _inside
    from .plate_detail import cut_iso
    cell = max(float(pg.cell), 0.005) * size
    fw = max(float(pg.frame_width), 1e-4) * size
    fh = float(pg.frame_height) * size
    flo = float(pg.floor_height) * size
    tiles = pg.pattern == 'TILES'
    r = cell * 0.5 * float(pg.hole_size)
    step = max(cell, size / 60.0)
    loop = _densify(P2, min(step, fw * 0.5) if fw > 0 else step)
    lo, hi = P2.min(0), P2.max(0)
    xs = np.arange(lo[0] + step * 0.5, hi[0], step)
    ys = np.arange(lo[1] + step * 0.5, hi[1], step * 0.866)
    G = np.array([(x + (step * 0.5 if j % 2 else 0.0), y) for j, y in enumerate(ys) for x in xs]).reshape(-1, 2)
    G = G[_inside(G, P2)] if len(G) else G

    def dist(Q):
        return outline_distance([tuple(q) for q in Q], [tuple(q) for q in P2])
    rings = []
    C = hole_centres(pg.pattern, P2, cell, float(pg.angle))
    C = C[_inside(C, P2)] if len(C) else C
    if len(C):
        C = C[dist(C) > fw + r * 1.6]
    for c in C:
        rim = hole_ring(pg.pattern, c, r, float(pg.angle))
        foot = c + (rim - c) * (0.92 if not tiles else 1.1)
        rings.append((rim, foot))
    if len(G):
        G = G[dist(G) > step * 0.45]
        if rings:                                     # (no grid point inside a hole or on its wall)
            near = pattern_field(pg.pattern, G, cell, float(pg.angle))
            G = G[(near > float(pg.hole_size) * 0.5 * 1.25) | (dist(G) < fw + r)]
    if fw > 0:                                        # (rows of points along the frame: its edges cut in clean)
        bl = _densify(P2, fw * 0.45)
        nb_ = np.roll(bl, -1, axis=0) - np.roll(bl, 1, axis=0)
        inw = np.stack([-nb_[:, 1], nb_[:, 0]], axis=1)
        inw /= np.maximum(np.linalg.norm(inw, axis=1, keepdims=True), 1e-12)
        band = np.concatenate([bl + inw * fw * f for f in (0.15, 0.55, 0.91, 1.25)])
        band = band[_inside(band, P2)]
        if len(band):
            dd = dist(band)
            band = band[dd > fw * 0.08]
            G = np.concatenate([G, band]) if len(G) else band
    verts = [Vector((float(x), float(y))) for x, y in loop]
    edges = [(i, (i + 1) % len(loop)) for i in range(len(loop))]
    kind_of = [0] * len(loop)                         # 0 the floor / frame, 1 a hole's rim, 2 its foot
    for rim, foot in rings:
        for ring, kd in ((rim, 1), (foot, 2)):
            b = len(verts)
            verts += [Vector((float(x), float(y))) for x, y in ring]
            edges += [(b + q, b + (q + 1) % len(ring)) for q in range(len(ring))]
            kind_of += [kd] * len(ring)
    verts += [Vector((float(x), float(y))) for x, y in G]
    kind_of += [0] * len(G)
    out = geometry.delaunay_2d_cdt(verts, edges, [], 0, step * 1e-4)
    V2 = np.array([tuple(v) for v in out[0]], float)
    kinds = np.zeros(len(V2), np.int64)
    for i, orig in enumerate(out[3]):
        if orig:
            kinds[i] = max(kind_of[o] for o in orig if o < len(kind_of))
    T0 = [f for f in out[2] if len(f) == 3]
    cen = np.array([V2[list(f)].mean(0) for f in T0]).reshape(-1, 2)
    keep = _inside(cen, P2) if len(cen) else np.zeros(0, bool)
    T0 = [f for f, k in zip(T0, keep) if k]
    d = dist(V2)
    bm = bmesh.new()
    ld = bm.verts.layers.float.new('d')
    lk = bm.verts.layers.float.new('k')
    bv = [bm.verts.new((float(x), float(y), 0.0)) for x, y in V2]
    for v, a, k in zip(bv, d, kinds):
        v[ld], v[lk] = float(a), float(k)
    for t in T0:
        try:
            bm.faces.new([bv[i] for i in t])
        except ValueError:
            pass
    for level in (fw * 0.3, fw * 0.82, fw):
        if level > 0:
            cut_iso(bm, ld, level, 1e-9, (ld, lk))
    bm.verts.index_update()
    V2 = np.array([(v.co.x, v.co.y) for v in bm.verts])
    d = np.array([v[ld] for v in bm.verts])
    kinds = np.array([round(v[lk]) for v in bm.verts])
    T = np.array([[v.index for v in f.verts] for f in bm.faces if len(f.verts) == 3], np.int64).reshape(-1, 3)
    bm.free()
    # heights: the frame, the floor, the holes (a point inside a hole: its foot's height)
    bev = max(fw * 0.3, 1e-9)
    z = np.where(d < bev, fh * np.clip(d / bev, 0.0, 1.0) ** 0.5, fh)
    rim_in = (d >= fw * 0.82) & (d < fw)
    z = np.where(rim_in, fh + (flo - fh) * (d - fw * 0.82) / max(fw * 0.18, 1e-9), z)
    inner = d >= fw
    pit = size * 0.0015
    inside = pattern_field(pg.pattern, V2, cell, float(pg.angle)) < float(pg.hole_size) * 0.5 * 0.9
    if len(C):                                        # 0.24.186 only in the holes that were made: a cell too near the
        dc = np.full(len(V2), np.inf)                 # frame has no hole - its floor stays flat (no dents there)
        for k0 in range(0, len(C), 256):
            dc = np.minimum(dc, np.linalg.norm(V2[:, None, :] - C[None, k0:k0 + 256, :], axis=2).min(1))
        inside &= dc < r * 1.15
    else:
        inside[:] = False
    if tiles:
        top, groove = flo + fh * 0.25, flo * 0.35
        zin = np.where(kinds == 1, top, np.where(kinds == 2, groove, np.where(inside, top, groove)))
    else:
        zin = np.where(kinds == 1, flo, np.where(kinds == 2, pit, np.where(inside, pit, flo)))
    z = np.where(inner, zin, z)
    return V2, z, T, d


def target_bvh(context, target, frame_inv):
    """The part's surface (as shown) in the panel's space (``frame_inv``: the part's space -> the panel's)."""
    dg = context.evaluated_depsgraph_get()
    key = (target.name, len(target.data.vertices), tuple(round(x, 5) for r in frame_inv for x in r))
    if _BVH.get('key') == key:
        return _BVH['bvh']
    ev = target.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        me.calc_loop_triangles()
        M = frame_inv
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3) @ np.array(M.to_3x3()).T + np.array(M.translation)
        tri = np.empty(len(me.loop_triangles) * 3, np.int64)
        me.loop_triangles.foreach_get('vertices', tri)
        bvh = BVHTree.FromPolygons(co.tolist(), tri.reshape(-1, 3).tolist())
    finally:
        ev.to_mesh_clear()
    _BVH.update(key=key, bvh=bvh)
    return bvh


def build(ob, context=None):
    """The panel again from its outline and sliders, lying on its part.  Returns its face count."""
    import bmesh
    context = context or bpy.context
    d = data(ob)
    P2 = np.asarray(d.get('outline', []), float)
    target = bpy.data.objects.get(d.get('target', ''))
    if len(P2) < 3 or target is None:
        return 0
    pg = ob.mch_mholes
    size = float(np.ptp(P2, axis=0).max())
    V2, z, T, dist = build_mesh(P2, pg, size)
    rel = Matrix(d['frame'])                          # (the panel's frame in its part's space)
    bvh = target_bvh(context, target, rel.inverted())
    n = len(V2)
    top, bot = np.zeros((n, 3)), np.zeros((n, 3))
    lift = size * 0.0005
    for i, (x, y) in enumerate(V2):
        o = Vector((x, y, size))
        loc, nrm, _i, _dd = bvh.ray_cast(o, Vector((0.0, 0.0, -1.0)), size * 4)
        if loc is None:
            loc, nrm, _i, _dd = bvh.find_nearest(Vector((x, y, 0.0)))
        if loc is None:
            loc, nrm = Vector((x, y, 0.0)), Vector((0.0, 0.0, 1.0))
        if nrm.z < 0:
            nrm = -nrm
        top[i] = loc + nrm * (z[i] + lift)
        bot[i] = loc - nrm * size * 0.004
    V = np.concatenate([top, bot])
    Fc = [tuple(t) for t in T] + [tuple(n + t[::-1]) for t in T]
    from collections import Counter
    cnt = Counter()
    for a, b_, c_ in T:
        for e in ((a, b_), (b_, c_), (c_, a)):
            cnt[(min(e), max(e))] += 1
    for a, b_, c_ in T:
        for x, y in ((a, b_), (b_, c_), (c_, a)):
            if cnt[(min(x, y), max(x, y))] == 1:
                Fc.append((y, x, n + x, n + y))
    me = ob.data
    me.clear_geometry()
    me.from_pydata(V.tolist(), [], Fc)
    me.validate(clean_customdata=False)
    # the faces down in a hole (or a groove): the dark material
    zc = np.concatenate([z, np.full(n, -1.0)])
    flo = float(pg.floor_height) * size
    mats = np.zeros(len(me.polygons), np.int32)
    for f in me.polygons:
        zz = zc[list(f.vertices)]
        if f.index < len(T) and zz.max() < flo * (0.5 if pg.pattern != 'TILES' else 0.6):
            mats[f.index] = 1
    me.polygons.foreach_set('material_index', mats)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(2.0), use_dissolve_boundaries=False, verts=bm.verts[:],
                             edges=bm.edges[:], delimit={'MATERIAL'})
    bmesh.ops.connect_verts_concave(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bm.to_mesh(me)
    bm.free()
    _materials(ob)
    me.update()
    ob.update_tag()
    return len(me.polygons)


def _materials(ob):
    pg = ob.mch_mholes
    me = ob.data
    names = data(ob).get('mats') or []
    mats = [bpy.data.materials.get(n) for n in names]
    if len(mats) != 2 or any(m is None for m in mats):
        mats = []
        for nm in ('Panel', 'Holes'):
            m = bpy.data.materials.new(f'MCH Holes {nm}')
            m.use_nodes = True
            mats.append(m)
        d = data(ob)
        d['mats'] = [m.name for m in mats]
        ob[KEY] = json.dumps(d)
    for m, col, rough, metal in ((mats[0], pg.color, 0.4, 0.6), (mats[1], pg.hole_color, 0.8, 0.0)):
        bs = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if bs is not None:
            bs.inputs['Base Color'].default_value = tuple(col) + (1.0,)
            bs.inputs['Roughness'].default_value = rough
            bs.inputs['Metallic'].default_value = metal
        m.diffuse_color = tuple(col) + (1.0,)
    if len(me.materials) != 2:
        me.materials.clear()
        for m in mats:
            me.materials.append(m)


def _upd(self, context):
    if _BUSY[0]:
        return
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and is_holes(ob):
        build(ob, context)
        sc = getattr(context, 'scene', None)
        if sc is not None:
            _BUSY[0] = True
            try:
                for k in LIVE:
                    setattr(sc.mch_mholes, k, getattr(self, k))
            finally:
                _BUSY[0] = False


LIVE = ('pattern', 'cell', 'hole_size', 'angle', 'frame_width', 'frame_height', 'floor_height', 'color', 'hole_color')


class MCH_PG_MechaHoles(bpy.types.PropertyGroup):
    pattern: EnumProperty(name='Pattern', items=PATTERNS, default='SQUARE', update=_upd)
    cell: FloatProperty(name='Spacing', default=0.05, min=0.008, max=0.5, update=_upd,
                        description='From one hole to the next (a share of the panel\'s size)')
    hole_size: FloatProperty(name='Hole Size', default=0.6, min=0.1, max=0.95, update=_upd,
                             description='How much of its cell a hole takes')
    angle: FloatProperty(name='Angle', default=0.0, min=-math.pi, max=math.pi, subtype='ANGLE', update=_upd,
                         description='The rows turned')
    frame_width: FloatProperty(name='Frame Width', default=0.06, min=0.0, max=0.4, update=_upd,
                               description='The finishing frame round the outline (a share of its size)')
    frame_height: FloatProperty(name='Frame Height', default=0.025, min=0.0, max=0.2, update=_upd)
    floor_height: FloatProperty(name='Floor Height', default=0.012, min=0.002, max=0.2, update=_upd,
                                description='The floor inside the frame (lower than the frame: recessed)')
    color: FloatVectorProperty(name='Panel', subtype='COLOR', size=3, min=0.0, max=1.0, default=(0.42, 0.43, 0.4),
                               update=_upd)
    hole_color: FloatVectorProperty(name='Holes', subtype='COLOR', size=3, min=0.0, max=1.0,
                                    default=(0.03, 0.03, 0.035), update=_upd)


def perform(context, loops, projector):
    """The outline drawn over a part -> a live panel of holes on it."""
    from . import base_mesh
    from . import core_geometry as cg
    groups = cg.prepare_loops(loops)
    if not groups:
        raise cg.CutError('Draw a bigger outline')
    outer, _holes = max(groups, key=lambda g: abs(cg.signed_area(g[0])))
    _q, found = base_mesh.anchor_hit(context, projector, outer)
    if found is None:
        raise cg.CutError('Draw the outline over a part')
    loc, nrm, target = found
    target = bpy.data.objects.get(target.name) or target
    vd = Vector(projector.view_dir)
    n = Vector(nrm).normalized()
    if n.dot(vd) > 0:
        n = -n
    o0, d0 = projector.ray(outer[0])
    x = Vector((1.0, 0.0, 0.0))
    px = base_mesh._plane_point(projector, (outer[0][0] + 100.0, outer[0][1]), loc, n)
    p0 = base_mesh._plane_point(projector, outer[0], loc, n)
    x = (px - p0)
    x = x - n * x.dot(n)
    if x.length < 1e-9:
        x = n.orthogonal()
    x.normalize()
    y = n.cross(x).normalized()
    P2 = []
    for q in outer:
        p = base_mesh._plane_point(projector, q, loc, n)
        P2.append(((p - loc).dot(x), (p - loc).dot(y)))
    P2 = np.array(P2, float)
    if cg.signed_area([tuple(q) for q in P2]) < 0:
        P2 = P2[::-1]
    M = Matrix.Identity(4)
    for r in range(3):
        M[r][0], M[r][1], M[r][2], M[r][3] = x[r], y[r], n[r], loc[r]
    st = context.scene.mch_mholes
    me = bpy.data.meshes.new('Mecha Holes')
    ob = bpy.data.objects.new('Mecha Holes', me)
    (context.collection or context.scene.collection).objects.link(ob)
    ob.matrix_world = M
    ob.parent = target
    ob.matrix_parent_inverse = target.matrix_world.inverted()
    ob[KEY] = json.dumps({'outline': P2.round(7).tolist(), 'target': target.name,      # (the frame kept in the
                          'frame': [list(r) for r in (target.matrix_world.inverted() @ M)]})  # part's space: it follows)
    _BUSY[0] = True
    try:
        for k in LIVE:
            setattr(ob.mch_mholes, k, getattr(st, k))
    finally:
        _BUSY[0] = False
    nf = build(ob, context)
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    return f'{ob.name} on "{target.name}" ({nf:,} faces) - live: its sliders lay it again; Enter: keep'


class MCH_OT_mholes_apply(bpy.types.Operator):
    """Keep the selected hole panels as they are (no longer live)"""
    bl_idname = 'mch.mholes_apply'
    bl_label = 'Apply Mecha Holes'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and any(is_holes(o) for o in context.selected_objects)

    def execute(self, context):
        obs = [o for o in context.selected_objects if is_holes(o)]
        for ob in obs:
            del ob[KEY]
            ob[DONE] = 1
        self.report({'INFO'}, 'Kept: ' + ', '.join(o.name for o in obs))
        return {'FINISHED'}


class MCH_OT_mholes_pattern(bpy.types.Operator):
    """This pattern (the selected panel too)"""
    bl_idname = 'mch.mholes_pattern'
    bl_label = 'Mecha Holes Pattern'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    pattern: EnumProperty(items=PATTERNS)

    def execute(self, context):
        ob = active_holes(context)
        context.scene.mch_mholes.pattern = self.pattern
        if ob is not None:
            ob.mch_mholes.pattern = self.pattern
        return {'FINISHED'}


def draw(layout, context):
    st = context.scene.mch_mholes
    ob = active_holes(context)
    pg = ob.mch_mholes if ob is not None else st
    layout.label(text=f'{ob.name} (live)' if ob is not None else 'Draw an outline on a part')
    g = layout.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
    for pid, label, _d in PATTERNS:
        g.operator('mch.mholes_pattern', text=label, depress=pg.pattern == pid).pattern = pid
    col = layout.column(align=True)
    for k in ('cell', 'hole_size', 'angle', 'frame_width', 'frame_height', 'floor_height'):
        col.prop(pg, k, slider=k not in {'angle'})
    r = layout.row(align=True)
    r.prop(pg, 'color', text='')
    r.prop(pg, 'hole_color', text='')
    if ob is not None:
        layout.operator('mch.mholes_apply', text='Apply (Enter)', icon='CHECKMARK')
    col = layout.column(align=True)
    for line in ('Draw an outline on a part: a panel of holes on it',
                 'A frame round it, the floor recessed, the holes in it',
                 'Select a panel: its sliders lay it again;  Enter: keep'):
        col.label(text=line)


CLASSES = (MCH_PG_MechaHoles, MCH_OT_mholes_apply, MCH_OT_mholes_pattern)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_mholes = PointerProperty(type=MCH_PG_MechaHoles)
    bpy.types.Object.mch_mholes = PointerProperty(type=MCH_PG_MechaHoles)


def unregister():
    for T in (bpy.types.Scene, bpy.types.Object):
        if hasattr(T, 'mch_mholes'):
            delattr(T, 'mch_mholes')
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
