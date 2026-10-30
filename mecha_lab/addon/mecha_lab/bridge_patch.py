"""0.24.20 Bridge Patch: lasso across two meshes (or two parts of one) to fill the gap between them - for a rough
creature silhouette that is merged later (e.g. DynaMesh in ZBrush).

Default: the whole lasso becomes one solid that simply overlaps both meshes: along the lasso its front follows the
meshes' surfaces and joins them with a smooth curve across the gap, across it the sides curve back.
Trim to Gap: only the gap plus a band of the meshes' surface that is sunk into them; where the view ray hits a
mesh surface that faces you the patch follows it, the gap and the steep sides (Wrap) are filled smoothly.

    Fill Crease fills the valley where two meshes meet (touching parts): the patch rides over it
    Round       how round / thick across: 1 = a circle's section (radius = half the lasso's width there)
    Bulge       push the middle out (+) or in (-)
    Fill        the back: 1 = mirrors the front about the meshes' middle (a full solid), 0 = only to the middle
    Thickness   the least thickness anywhere (0 = Auto)
    Smooth      0 = straight join across the gap, 1 = the surfaces' slope carries on
    Wrap        the meshes' sides steeper than this are not followed (the join stays smooth over them)
    Sink        how far the patch stays under the meshes where they show (x Thickness); Trim to Gap: Overlap
    Resolution  Low / Mid / High

Live until Apply.  ``soft_fill`` / ``bump`` / ``spread`` are pure and tested headless.
"""
from __future__ import annotations

import json
import math
import types

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from mathutils import Matrix, Vector

from . import target_rules
from . import core_geometry as cg

SRC_KEY = 'mch_bridge_src'
COLLECTION = 'Bridge Patches'
LIVE_KEYS = ('trim', 'crease', 'smooth', 'bulge', 'round', 'wrap', 'fill', 'thickness', 'sink', 'overlap', 'quality')
QUALITY = {'LOW': 24, 'MID': 40, 'HIGH': 64}
_CACHE = {}


# ---------------------------------------------------------------------------- pure solver

def _laplacian(n, edges):
    """Graph Laplacian (uniform weights) as a function x -> L x (numpy)."""
    import numpy as np
    I = np.asarray([e[0] for e in edges], dtype=np.int64)
    J = np.asarray([e[1] for e in edges], dtype=np.int64)
    deg = np.zeros(n)
    np.add.at(deg, I, 1.0)
    np.add.at(deg, J, 1.0)

    def L(x):
        y = -deg * x
        np.add.at(y, I, x[J])
        np.add.at(y, J, x[I])
        return y
    return L


def _cg(apply, rhs, iters):
    import numpy as np
    x = np.zeros_like(rhs)
    r = rhs.copy()
    p = r.copy()
    rr = r @ r
    tol = 1e-20 * max(rhs @ rhs, 1e-300)
    for _ in range(iters):
        if rr <= tol:
            break
        Ap = apply(p)
        alpha = rr / max(p @ Ap, 1e-300)
        x += alpha * p
        r -= alpha * Ap
        rr_new = r @ r
        p = r + (rr_new / rr) * p
        rr = rr_new
    return x


def bump(n, edges, known):
    """A round bump over the unknown points (0 on the known ones, 1 at the top) - pure."""
    import numpy as np
    unk = np.asarray([i for i in range(n) if i not in known], dtype=np.int64)
    out = np.zeros(n)
    if len(unk) == 0:
        return out.tolist()
    L = _laplacian(n, edges)

    def harm(xu):
        full = np.zeros(n)
        full[unk] = xu
        return -L(full)[unk]
    u = _cg(harm, np.ones(len(unk)), 6 * len(unk) + 200)
    top = max(u.max(), 1e-12)
    out[unk] = u / top
    return out.tolist()


def soft_fill(n, edges, target, weight, smooth=1.0, stiff=200.0):
    """Depth of every point: close to ``target[i]`` where ``weight[i]`` is 1, free where it is 0, smooth in between
    and across (smooth 0 = harmonic, 1 = biharmonic: the slope carries on) - pure.  Minimises
    stiff * sum w (d - t)^2 + (1 - smooth) * d.(-L)d + smooth * |L d|^2 (conjugate gradients)."""
    import numpy as np
    w = np.asarray(weight, dtype=np.float64)
    t = np.asarray([x if x is not None else 0.0 for x in target], dtype=np.float64)
    if w.max() <= 0:
        raise ValueError('nothing to hold the patch')
    L = _laplacian(n, edges)

    def A(x):
        return stiff * w * x + (1.0 - smooth) * (-L(x)) + smooth * L(L(x))
    # start from the weighted mean so the free part converges fast
    x0 = np.full(n, (w * t).sum() / w.sum())
    rhs = stiff * w * t - A(x0)
    return (x0 + _cg(A, rhs, 8 * n + 400)).tolist()


def spread(n, edges, values, passes):
    """``values`` blurred over the point graph ``passes`` times (each point: half itself, half its neighbours)."""
    import numpy as np
    I = np.asarray([e[0] for e in edges], dtype=np.int64)
    J = np.asarray([e[1] for e in edges], dtype=np.int64)
    deg = np.zeros(n)
    np.add.at(deg, I, 1.0)
    np.add.at(deg, J, 1.0)
    g = np.asarray(values, dtype=np.float64)
    for _k in range(passes):
        s = np.zeros(n)
        np.add.at(s, I, g[J])
        np.add.at(s, J, g[I])
        g = 0.5 * g + 0.5 * s / np.maximum(deg, 1.0)
    return g.tolist()


def local_max(n, edges, values, passes):
    """Each point gets the largest value within ``passes`` edges of it - pure."""
    import numpy as np
    I = np.asarray([e[0] for e in edges], dtype=np.int64)
    J = np.asarray([e[1] for e in edges], dtype=np.int64)
    g = np.asarray(values, dtype=np.float64)
    for _k in range(passes):
        h = g.copy()
        np.maximum.at(h, I, g[J])
        np.maximum.at(h, J, g[I])
        g = h
    return g.tolist()


def drape(n, edges, front, depth, passes):
    """``front`` smoothed ``passes`` times, never behind ``depth`` (where known) - pure.  Creases between the
    surfaces fill in, convex parts stay on the surface (like a cloth laid over them, seen from the front)."""
    import numpy as np
    S = np.asarray(front, dtype=np.float64)
    if passes <= 0:
        return S.tolist()
    known = np.asarray([d is not None for d in depth])
    D = np.asarray([d if d is not None else 0.0 for d in depth], dtype=np.float64)
    I = np.asarray([e[0] for e in edges], dtype=np.int64)
    J = np.asarray([e[1] for e in edges], dtype=np.int64)
    deg = np.zeros(n)
    np.add.at(deg, I, 1.0)
    np.add.at(deg, J, 1.0)
    for _k in range(passes):
        acc = np.zeros(n)
        np.add.at(acc, I, S[J])
        np.add.at(acc, J, S[I])
        S = 0.5 * S + 0.5 * acc / np.maximum(deg, 1.0)
        S = np.where(known, np.minimum(S, D), S)
    return S.tolist()


def _smoothstep(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


# ---------------------------------------------------------------------------- live object

def _update(self, context):
    ob = self.id_data
    if not isinstance(ob, bpy.types.Object) or not self.live:
        return
    try:
        rebuild(context, ob)
        self.last_error = ''
    except (cg.CutError, ValueError, RuntimeError) as ex:
        self.last_error = str(ex)
    st = getattr(getattr(context, 'scene', None), 'mch_bridge', None)
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


class MCH_PG_Bridge(bpy.types.PropertyGroup):
    trim: _p(BoolProperty, name='Trim to Gap', default=False,
             description='Off: the whole lasso becomes one round solid that overlaps both meshes (merge it later, '
                         'e.g. DynaMesh). On: only the gap plus a sunk rim, following the meshes\' surfaces')
    crease: _p(FloatProperty, name='Fill Crease', default=0.5, min=0.0, max=1.0, subtype='FACTOR',
               description='Fill the valley where two meshes meet (touching parts, e.g. torso and pelvis): the '
                           'patch rides over it; 0 = follow the surfaces exactly')
    smooth: _p(FloatProperty, name='Smooth', default=1.0, min=0.0, max=1.0, subtype='FACTOR',
               description='0 = the straightest join, 1 = the surfaces\' slope carries on across the gap')
    bulge: _p(FloatProperty, name='Bulge', default=0.0, min=-1.0, max=1.0,
              description='Push the middle of the gap out (+) or in (-)')
    wrap: _p(FloatProperty, name='Wrap', default=math.radians(50), min=math.radians(10), max=math.radians(85),
             subtype='ANGLE', description='The patch also covers the sides of the meshes steeper than this '
                                          '(toward their outline), like a skin; lower = covers more')
    thickness: _p(FloatProperty, name='Thickness', default=0.0, min=0.0, soft_max=0.5, precision=4, unit='LENGTH',
                  description='Of the patch behind its front face (0 = Auto: 3% of its size)')
    round: _p(FloatProperty, name='Round', default=1.0, min=0.0, max=1.5,
              description='Across the gap the patch follows a round neck around the meshes\' middle (radius = '
                          'half the lasso\'s width there): its sides curve back into the meshes (0 = a flat sheet)')
    fill: _p(FloatProperty, name='Fill', default=1.0, min=0.0, max=1.0, subtype='FACTOR',
             description='Solid: the back mirrors the front about the meshes\' middle (1 = a full round neck) - '
                         'overlaps them well for merging (DynaMesh); 0 = a sheet of Thickness')
    sink: _p(FloatProperty, name='Sink', default=1.5, min=0.0, max=6.0,
             description='How far the overlap band goes into the meshes (x Thickness)')
    overlap: _p(IntProperty, name='Overlap', default=4, min=1, max=10,
                description='Rows of the surrounding surface the patch also covers (hides the seam)')
    quality: _p(EnumProperty, name='Resolution', default='MID',
                items=(('LOW', 'Low', 'Light'), ('MID', 'Mid', ''), ('HIGH', 'High', 'Smooth')))
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


def _cast(context, origin, direction, skip):
    """(depth along the ray, facing) of the first mesh hit that is not a Bridge Patch, else (None, 0):
    facing = how much the surface there looks at the viewer (1 = straight at it, 0 = edge on)."""
    depsgraph = context.evaluated_depsgraph_get()
    o = Vector(origin)
    d = Vector(direction).normalized()
    travelled = 0.0
    for _k in range(8):
        hit, loc, nrm, _i, ob, _m = target_rules.scene_ray(context, depsgraph, o, d)
        if not hit:
            return None, 0.0
        travelled += (loc - o).length
        if ob is not None and (ob.get(SRC_KEY) or ob.name in skip):
            o = loc + d * 1e-4
            travelled += 1e-4
            continue
        return travelled, abs(nrm.dot(d))
    return None, 0.0


def _exit_depth(context, origin, direction, entry):
    """Depth where the ray leaves the mesh it entered at ``entry`` (its far side), or None."""
    depsgraph = context.evaluated_depsgraph_get()
    d = Vector(direction).normalized()
    o = Vector(origin) + d * (entry + 1e-4)
    hit, loc, _n, _i, ob, _m = target_rules.scene_ray(context, depsgraph, o, d)
    if not hit or (ob is not None and ob.get(SRC_KEY)):
        return None
    return entry + 1e-4 + (loc - o).length


def _samples(context, ob, src, p):
    """Cached: points (px), triangles, edges, ray origins / directions and the depth where a mesh was hit."""
    key = (src.get('stamp'), p.quality)
    hit = _CACHE.get(ob.name)
    if hit is not None and hit[0] == key:
        return hit[1]
    from . import armor_plate as ap
    from . import base_mesh as bmm
    projector = ap.thaw_projector(src['proj'])
    groups = cg.prepare_loops([[tuple(q) for q in lp] for lp in src['loops']])
    outer, holes = groups[0]
    fp = types.SimpleNamespace(profile='PILLOW', resolution=QUALITY[p.quality], outline_smooth=0.2, edge_round=0.1,
                               puff=1.0, rings=(0.35, 0.9), rim=1.0)
    _b, pts, tris, nb, _shape, _nat, _sp = bmm.profile_field(outer, holes, fp)
    origins, dirs, depth, facing, middle = [], [], [], [], []
    skip = {ob.name}
    for q in pts:
        o, d = projector.ray(q)
        d = Vector(d).normalized()
        origins.append(Vector(o))
        dirs.append(d)
        t, f = _cast(context, o, d, skip)
        depth.append(t)
        facing.append(f)
        far = _exit_depth(context, o, d, t) if t is not None else None
        middle.append((t + far) / 2.0 if far is not None else None)      # halfway through the mesh
    found = [t for t in depth if t is not None]
    if not found:
        raise cg.CutError('Bridge Patch: the lasso touches no mesh.')
    # something far behind the two meshes (a floor, a wall) is not one of them: treat it as gap
    found.sort()
    med = found[len(found) // 2]
    xs = [q[0] for q in pts]
    ys = [q[1] for q in pts]
    a, b = projector.ray((min(xs), min(ys))), projector.ray((max(xs), max(ys)))
    size = (Vector(a[0]) + Vector(a[1]).normalized() * med - Vector(b[0]) - Vector(b[1]).normalized() * med).length
    depth = [t if t is not None and t <= med + size else None for t in depth]
    edges = set()
    for t in tris:
        for k in range(3):
            i, j = t[k], t[(k + 1) % 3]
            edges.add((min(i, j), max(i, j)))
    # how round the lasso is across (Teddy inflation, 0 on the outline): for Round, in world units
    px = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
    puff = [h * size / max(px, 1e-9) for h in bmm.puff_heights(pts, tris, nb, 1.0)]
    data = (pts, tris, sorted(edges), origins, dirs, depth, facing, size, puff, middle)
    _CACHE[ob.name] = (key, data)
    return data


def build(context, ob):
    src = source(ob)
    if src is None:
        raise cg.CutError('This patch was applied.')
    p = ob.mch_bridge
    pts, tris, edges, origins, dirs, depth, facing, size, puff, middle = _samples(context, ob, src, p)
    n = len(pts)
    if not p.trim:
        return _build_whole(n, tris, edges, origins, dirs, depth, facing, size, puff, middle, p)
    # the surfaces hold the patch where they face you; their steep sides (toward the outline) are covered by the
    # patch like a skin, so it does not dive into the gap along them.  Soft weights: no stair-step seam.
    grip = math.cos(p.wrap)
    weight = [_smoothstep((facing[i] - grip) / 0.15 + 0.5) if depth[i] is not None else 0.0 for i in range(n)]
    if max(weight) <= 0.0:
        raise cg.CutError('Bridge Patch: no surface faces you inside the lasso (lower Wrap).')
    if min(weight) >= 0.99:
        raise cg.CutError('Bridge Patch: the whole lasso is on a mesh - draw it across the gap.')
    # the middle of the meshes (halfway through them), carried smoothly across the gap
    if any(m is not None for m in middle):
        core = soft_fill(n, edges, middle, [1.0 if m is not None else 0.0 for m in middle], 0.5)
    else:                                            # open meshes (no far side): somewhat behind the surfaces
        base = soft_fill(n, edges, depth, weight, 0.0)
        core = [x + 0.15 * size for x in base]
    # Round: across the gap the patch follows a round neck around that middle (radius = half the lasso's width
    # there); the meshes' surfaces hold it where they face you
    hold = min(p.round, 1.0) * 0.3
    target, strength = [], []
    for i in range(n):
        tube = core[i] - p.round * puff[i]
        w = weight[i] if depth[i] is not None else 0.0
        k = w + (1.0 - w) * hold                     # the surface (w) and the neck (hold) pull together
        target.append((w * (depth[i] or 0.0) + (1.0 - w) * hold * tube) / k if k > 0 else tube)
        strength.append(k)
    d = soft_fill(n, edges, target, strength, p.smooth)
    if abs(p.bulge) > 1e-6:
        bp = bump(n, edges, {i: 0.0 for i in range(n) if weight[i] >= 0.5})
        d = [d[i] - p.bulge * 0.25 * size * bp[i] for i in range(n)]
    # how much a point belongs to the patch: 1 in the gap, fading out over Overlap rows of surface
    g = spread(n, edges, [1.0 - x for x in weight], 2 * p.overlap)
    use = {i for i in range(n) if g[i] > 0.04}
    thick = p.thickness if p.thickness > 0 else 0.03 * size
    front, back = {}, {}
    for i in use:
        dep = d[i]
        if depth[i] is not None and g[i] >= 0.5:
            dep = min(dep, depth[i])                 # over a steep side: stay in front of the surface
        dep += thick * p.sink * max(0.0, min(1.0, (0.5 - g[i]) / 0.46))     # the rim slips under the surface
        front[i] = origins[i] + dirs[i] * dep
        # Fill: the back mirrors the front about the meshes' middle - a solid neck that overlaps them well,
        # so it fuses cleanly (e.g. DynaMesh in ZBrush); 0 = a sheet of Thickness
        behind = max(thick, p.fill * 2.0 * (core[i] - dep))
        back[i] = front[i] + dirs[i] * behind
    faces = [t for t in tris if all(i in use for i in t)]
    if not faces:
        raise cg.CutError('Bridge Patch: the gap is too small for this Resolution.')
    order = sorted(use)
    index = {i: k for k, i in enumerate(order)}
    m = len(order)
    verts = [front[i] for i in order] + [back[i] for i in order]
    out = []
    edge_count = {}
    for a, b, c in faces:
        out.append((index[a], index[b], index[c]))
        out.append((m + index[c], m + index[b], m + index[a]))
        for u, v in ((a, b), (b, c), (c, a)):
            edge_count[(u, v)] = edge_count.get((u, v), 0) + 1
    for (u, v) in edge_count:
        if (v, u) not in edge_count:                     # an edge on the rim of the patch: side wall
            out.append((index[v], index[u], m + index[u], m + index[v]))
    return verts, out


def _build_whole(n, tris, edges, origins, dirs, depth, facing, size, puff, middle, p):
    """0.24.20 the whole lasso as one solid (not trimmed to the gap), overlapping both meshes - to be merged
    later (e.g. DynaMesh in ZBrush).  Along the lasso the front follows the meshes' surfaces where they face you
    and joins them with a smooth curve across the gap (Smooth, Wrap); across it the sides curve back (Round);
    the back mirrors the front about the meshes' middle (Fill)."""
    grip = math.cos(p.wrap)
    weight = [_smoothstep((facing[i] - grip) / 0.15 + 0.5) if depth[i] is not None else 0.0 for i in range(n)]
    if max(weight) <= 0.0:
        raise cg.CutError('Bridge Patch: no surface faces you inside the lasso (lower Wrap).')
    surface = soft_fill(n, edges, depth, weight, p.smooth)
    if any(m is not None for m in middle):
        core = soft_fill(n, edges, middle, [1.0 if m is not None else 0.0 for m in middle], 0.5)
    else:                                            # open meshes (no far side): somewhat behind the surfaces
        core = [x + 0.15 * size for x in surface]
    if abs(p.bulge) > 1e-6:
        bp = bump(n, edges, {i: 0.0 for i in range(n) if weight[i] >= 0.5})
        surface = [surface[i] - p.bulge * 0.25 * size * bp[i] for i in range(n)]
    # 0.24.21 ride over the creases between the meshes (two parts touching, e.g. torso and pelvis): smooth the
    # front and keep it in front of the surfaces, again and again - a valley fills, a bulge stays the mesh's own
    surface = drape(n, edges, surface, depth, int(round(p.crease * 30 * QUALITY[p.quality])))
    top = local_max(n, edges, puff, max(2, QUALITY[p.quality] // 3))
    thick = p.thickness if p.thickness > 0 else 0.03 * size
    verts_f, verts_b = [], []
    for i in range(n):
        dep = surface[i] + p.round * max(0.0, top[i] - puff[i])     # the sides curve back (a round section)
        if depth[i] is not None:                                   # on a mesh: just under it (it shows there)
            on = max(0.0, min(1.0, 1.0 - (depth[i] - surface[i]) / max(thick, 1e-9)))
            dep += thick * p.sink * on
        behind = max(thick, (core[i] - dep) * (1.0 + p.fill))
        verts_f.append(origins[i] + dirs[i] * dep)
        verts_b.append(origins[i] + dirs[i] * (dep + behind))
    return _solid(verts_f, verts_b, tris)


def _solid(verts_f, verts_b, tris):
    """Closed solid from a front and a back point set on the same triangles (side wall along the rim)."""
    m = len(verts_f)
    out = []
    edge_count = {}
    for a, b, c in tris:
        out.append((a, b, c))
        out.append((m + c, m + b, m + a))
        for u, v in ((a, b), (b, c), (c, a)):
            edge_count[(u, v)] = edge_count.get((u, v), 0) + 1
    for (u, v) in edge_count:
        if (v, u) not in edge_count:
            out.append((v, u, m + u, m + v))
    return list(verts_f) + list(verts_b), out


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
    """Closed lasso -> a live Bridge Patch.  Returns a report; raises cg.CutError."""
    from . import armor_plate as ap
    from . import face_extract as fx
    loops = [[tuple(q) for q in lp] for lp in loops if len(lp) >= 3]
    if not loops:
        raise cg.CutError('Bridge Patch: lasso an area across the gap (3+ points).')
    frozen = ap.freeze_projector(projector)
    if frozen is None:
        raise cg.CutError('This view cannot be saved for the patch.')
    st = context.scene.mch_bridge
    me = bpy.data.meshes.new('Bridge_Patch')
    ob = bpy.data.objects.new(me.name, me)
    fx._parts_collection(context, COLLECTION).objects.link(ob)
    ob[SRC_KEY] = json.dumps({'loops': [[[float(x), float(y)] for x, y in lp] for lp in loops], 'proj': frozen,
                              'stamp': id(ob) % 100000})
    p = ob.mch_bridge
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
    return f'Bridge patch "{ob.name}" ({len(me.vertices) // 2} points)'


def live_bridge(context):
    ob = getattr(context, 'active_object', None)
    if ob is not None and getattr(ob, 'mch_bridge', None) is not None and ob.mch_bridge.live and source(ob):
        return ob
    return None


class MCH_OT_bridge_apply(bpy.types.Operator):
    bl_idname = 'mch.bridge_apply'
    bl_label = 'Apply Bridge Patch'
    bl_description = 'The patch becomes a plain mesh (the sliders stop rebuilding it)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return live_bridge(context) is not None

    def execute(self, context):
        ob = live_bridge(context)
        ob.mch_bridge.live = False
        del ob[SRC_KEY]
        _CACHE.pop(ob.name, None)
        self.report({'INFO'}, f'{ob.name}: applied')
        return {'FINISHED'}


def draw(layout, context):
    ob = live_bridge(context)
    p = ob.mch_bridge if ob is not None else context.scene.mch_bridge
    if ob is not None:
        box = layout.box()
        box.label(text='LIVE: ' + ob.name, icon='MOD_LATTICE')
        if p.last_error:
            box.label(text=p.last_error, icon='ERROR')
        target = box
    else:
        layout.label(text='Settings for the next patch', icon='MOD_LATTICE')
        target = layout
    target.prop(p, 'trim', toggle=True, icon='MOD_BOOLEAN')
    col = target.column(align=True)
    if not p.trim:
        col.prop(p, 'crease', slider=True)
    col.prop(p, 'round', slider=True)
    col.prop(p, 'bulge', slider=True)
    col.prop(p, 'fill', slider=True)
    col.prop(p, 'thickness', text='Min Thickness')
    col = target.column(align=True)
    col.prop(p, 'smooth', slider=True)
    col.prop(p, 'wrap')
    col.prop(p, 'sink')
    if p.trim:
        col.prop(p, 'overlap')
    target.row().prop(p, 'quality', expand=True)
    if ob is not None:
        target.operator('mch.bridge_apply', icon='CHECKMARK')
    col = layout.column(align=True)
    col.scale_y = 0.8
    for line in ('Lasso across two meshes: a round solid along the lasso', 'around their middle, overlapping them (merge later);',
                 'Trim to Gap: only the gap, edges sunk into them',
                 'Apply: plain mesh'):
        col.label(text=line)


CLASSES = (MCH_PG_Bridge, MCH_OT_bridge_apply)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_bridge = bpy.props.PointerProperty(type=MCH_PG_Bridge)
    bpy.types.Object.mch_bridge = bpy.props.PointerProperty(type=MCH_PG_Bridge)


def unregister():
    for n, t in (('mch_bridge', bpy.types.Object), ('mch_bridge', bpy.types.Scene)):
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
