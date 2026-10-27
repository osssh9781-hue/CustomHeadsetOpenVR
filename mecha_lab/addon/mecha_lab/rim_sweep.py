"""0.24.41 Cut / Split edge finish made by Geometry Nodes: the border of the drawn area is swept.

Blender's Bevel on the Boolean result clamped to almost nothing next to the slivers a Boolean leaves on a dense
mesh, so the chamfer / bevel came out uneven or not at all.  Here the finish is carved instead:

* Python reads the new rim (edges between the cut's faces and the old surface) and, for every rim point, the
  cross-section of what has to go: from ``width`` along the surface to ``width`` down the cut wall, straight
  (Chamfer) or round (Bevel, ``segments``), plus a cap outside the part.  Those points are stored as vertex
  attributes ``mch_rp0`` ... and the rim edges as ``mch_rim``.
* A Geometry Nodes group (``MCH_RimSweep_<n>``) turns the rim edges into curves (Mesh to Curve), sweeps an
  ``n``-point profile along them (Curve to Mesh), puts every profile point where its attribute says (Index
  Switch on index mod n) and subtracts that band from the part (Mesh Boolean, Exact).
* The modifier is applied to a temporary object and the result goes back into the mesh.

0.24.53: the band is first joined with itself (Exact with Self Intersection, the band alone - it crosses itself at
concave corners) and then taken from the part with the Manifold solver: 7-13x faster on dense parts, the same
shape.  An open part, or a result that is not clean, falls back to the old all-Exact group.  Corners get the
miter length (the averaged direction alone made a 90 degree corner 71 % as wide).

The band follows the rim exactly, so the chamfer / bevel is as even as the drawn outline.
"""
from __future__ import annotations

import bmesh
import bpy
from mathutils import Vector

from . import core_geometry as cg

RIM = 'mch_rim'
POINT = 'mch_rp'
DIR = 'mch_rdir'


def _link(ng, a, b):
    ng.links.new(a, b)


def ensure_group(n, fast=True):
    """The node group for an ``n``-point profile (made once per n): ``fast`` = band self-union (Exact) then a
    Manifold difference; else the whole difference Exact with Self Intersection (slow, takes any mesh)."""
    name = f'MCH_RimSweep5_{n}' if fast else f'MCH_RimSweep4_{n}'
    ng = bpy.data.node_groups.get(name)
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    nodes = ng.nodes
    gin = nodes.new('NodeGroupInput')
    gout = nodes.new('NodeGroupOutput')
    rim = nodes.new('GeometryNodeInputNamedAttribute')
    rim.data_type = 'BOOLEAN'
    rim.inputs['Name'].default_value = RIM
    m2c = nodes.new('GeometryNodeMeshToCurve')
    _link(ng, gin.outputs[0], m2c.inputs['Mesh'])
    _link(ng, rim.outputs['Attribute'], m2c.inputs['Selection'])
    # every curve runs the same way round (Mesh to Curve picks a direction per curve): a curve against the
    # stored rim direction is reversed, else its swept band would come out inside out and cut nothing
    tan = nodes.new('GeometryNodeInputTangent')
    ref = nodes.new('GeometryNodeInputNamedAttribute')
    ref.data_type = 'FLOAT_VECTOR'
    ref.inputs['Name'].default_value = DIR
    dot = nodes.new('ShaderNodeVectorMath')
    dot.operation = 'DOT_PRODUCT'
    _link(ng, tan.outputs[0], dot.inputs[0])
    _link(ng, ref.outputs['Attribute'], dot.inputs[1])
    cap = nodes.new('GeometryNodeCaptureAttribute')      # per point first (a closed loop's mean tangent is 0),
    cap.domain = 'POINT'                                   # then the curve's mean of those decides
    cap.capture_items.new('FLOAT', 'Dot')
    _link(ng, m2c.outputs['Curve'], cap.inputs['Geometry'])
    _link(ng, dot.outputs['Value'], cap.inputs['Dot'])
    less = nodes.new('FunctionNodeCompare')
    less.data_type = 'FLOAT'
    less.operation = 'LESS_THAN'
    _link(ng, cap.outputs['Dot'], less.inputs[0])
    less.inputs[1].default_value = 0.0
    rev = nodes.new('GeometryNodeReverseCurve')
    _link(ng, cap.outputs['Geometry'], rev.inputs['Curve'])
    _link(ng, less.outputs['Result'], rev.inputs['Selection'])
    prof = nodes.new('GeometryNodeCurvePrimitiveCircle')
    prof.mode = 'RADIUS'
    prof.inputs['Resolution'].default_value = n
    c2m = nodes.new('GeometryNodeCurveToMesh')
    c2m.inputs['Fill Caps'].default_value = True
    _link(ng, rev.outputs['Curve'], c2m.inputs['Curve'])
    _link(ng, prof.outputs['Curve'], c2m.inputs['Profile Curve'])
    idx = nodes.new('GeometryNodeInputIndex')
    mod = nodes.new('ShaderNodeMath')
    mod.operation = 'FLOORED_MODULO'
    mod.inputs[1].default_value = n
    _link(ng, idx.outputs['Index'], mod.inputs[0])
    sw = nodes.new('GeometryNodeIndexSwitch')
    sw.data_type = 'VECTOR'
    while len(sw.index_switch_items) < n:
        sw.index_switch_items.new()
    _link(ng, mod.outputs[0], sw.inputs['Index'])
    for j in range(n):
        a = nodes.new('GeometryNodeInputNamedAttribute')
        a.data_type = 'FLOAT_VECTOR'
        a.inputs['Name'].default_value = f'{POINT}{j}'
        _link(ng, a.outputs['Attribute'], sw.inputs[j + 1])
    setp = nodes.new('GeometryNodeSetPosition')
    _link(ng, c2m.outputs['Mesh'], setp.inputs['Geometry'])
    _link(ng, sw.outputs['Output'], setp.inputs['Position'])
    boo = nodes.new('GeometryNodeMeshBoolean')
    boo.operation = 'DIFFERENCE'
    if fast:
        boo.solver = 'MANIFOLD'
    else:
        boo.solver = 'EXACT'
        boo.inputs['Self Intersection'].default_value = True
    # the band carries the part's attributes along its curves (as point attributes): dropped here, else the
    # Boolean result has a second UVMap / cutter flag on the points (and the next cut finished this one again)
    strip = nodes.new('GeometryNodeRemoveAttribute')
    strip.inputs['Pattern Mode'].default_value = 'Wildcard'
    strip.inputs['Name'].default_value = '*'
    _link(ng, setp.outputs['Geometry'], strip.inputs['Geometry'])
    _link(ng, gin.outputs[0], boo.inputs['Mesh 1'])
    if fast:
        uni = nodes.new('GeometryNodeMeshBoolean')       # the band alone, made one clean solid first
        uni.operation = 'UNION'
        uni.solver = 'EXACT'
        uni.inputs['Self Intersection'].default_value = True
        _link(ng, strip.outputs['Geometry'], uni.inputs['Mesh 2'])
        _link(ng, uni.outputs['Mesh'], boo.inputs['Mesh 2'])
    else:
        _link(ng, strip.outputs['Geometry'], boo.inputs['Mesh 2'])
    _link(ng, boo.outputs['Mesh'], gout.inputs[0])
    return ng


def profile_points(p, d_face, d_wall, out, width, mode, segments):
    """The cross-section to remove at rim point ``p``: ``d_face`` = along the old surface away from the rim,
    ``d_wall`` = down the cut wall, ``out`` = out of the part.  Chamfer = a straight cut from ``width`` on the
    surface to ``width`` on the wall; Bevel = a round one (tangent to both); then two points outside."""
    a = p + d_face * width
    b = p + d_wall * width
    if mode == 'CHAMFER':
        arc = [a, b]
    else:
        c = p + d_face * width + d_wall * width          # the round's centre (exact for a square corner)
        k = max(1, segments)
        import math
        arc = [c + (a - c) * math.cos(0.5 * math.pi * i / k) + (b - c) * math.sin(0.5 * math.pi * i / k)
               for i in range(k + 1)]
    h = width * 1.5
    return arc + [b + out * h, a + out * h]


def miter(total, k, cap=3.0):
    """The direction (and length) to go ``width`` from both edges at a corner: ``total`` = the sum of the ``k``
    unit directions of the edges meeting there.  Two edges at angle t: length 1 / cos(t / 2) (capped)."""
    if k != 2:
        return total.normalized()
    sq = total.length_squared                  # |d1 + d2|^2 = 2 (1 + d1.d2)
    if sq < 1e-12:
        return total.normalized()
    m = total * (2.0 / sq)
    return m if m.length <= cap else m.normalized() * cap


def _chains(edges):
    """The rim as ordered runs of vertices: [(verts, closed)].  A vertex where 3+ rim edges meet ends a run."""
    nbr = {}
    for e in edges:
        a, b = e.verts
        nbr.setdefault(a, []).append(b)
        nbr.setdefault(b, []).append(a)
    seen_e = set()
    out = []

    def walk(start, nxt):
        run = [start]
        prev, cur = start, nxt
        while True:
            seen_e.add(frozenset((prev.index, cur.index)))
            run.append(cur)
            if cur is start:
                return run[:-1], True
            if len(nbr[cur]) != 2:
                return run, False
            n2 = nbr[cur][0] if nbr[cur][1] is prev else nbr[cur][1]
            if frozenset((cur.index, n2.index)) in seen_e:
                return run, False
            prev, cur = cur, n2
    for v, ns in nbr.items():                     # open runs first: from their ends / junctions
        if len(ns) != 2:
            for n in ns:
                if frozenset((v.index, n.index)) not in seen_e:
                    out.append(walk(v, n))
    for v, ns in nbr.items():                     # then the closed loops
        for n in ns:
            if frozenset((v.index, n.index)) not in seen_e:
                out.append(walk(v, n))
    return out


def smooth_frames(bm, edges, acc, width, corner_deg=35.0):
    """0.24.58 Per rim point (d_face, d_wall, out, corner?): the directions averaged over the rim within ``width``
    either side, so a hand-drawn (slightly zigzag) cut gets one smooth bevel instead of a notch at every kink -
    big widths crossed their neighbours' profiles (torn faces, very slow Booleans).  A real corner at that scale
    (the rim turns more than ``corner_deg`` between ``width`` before and after) keeps its exact mitred profile."""
    import math
    out = {}
    cos_c = math.cos(math.radians(corner_deg))
    for run, closed in _chains(edges):
        n = len(run)
        if n < 3:
            continue
        pos = [v.co.copy() for v in run]
        s = [0.0]
        for i in range(1, n):
            s.append(s[-1] + (pos[i] - pos[i - 1]).length)
        total = s[-1] + ((pos[0] - pos[-1]).length if closed else 0.0)
        for i, v in enumerate(run):
            if v.index not in acc:
                continue
            sums = [Vector(), Vector(), Vector()]
            before = after = None
            for j, u in enumerate(run):
                d = s[j] - s[i]
                if closed:
                    d = (d + 0.5 * total) % total - 0.5 * total
                if abs(d) > width or u.index not in acc:
                    continue
                df, dw, o, _k = acc[u.index]
                sums[0] += df.normalized()
                sums[1] += dw.normalized()
                sums[2] += o.normalized()
                if d < 0 and (before is None or d < before[0]):
                    before = (d, pos[j])
                if d > 0 and (after is None or d > after[0]):
                    after = (d, pos[j])
            corner = True                         # no neighbour within the width (long straight edges) / a run's
            if before is not None and after is not None:      # end: the exact mitred profile, as before
                t0, t1 = pos[i] - before[1], after[1] - pos[i]
                if t0.length > 1e-12 and t1.length > 1e-12:
                    corner = t0.normalized().dot(t1.normalized()) < cos_c
            if all(x.length > 1e-9 for x in sums):
                out[v.index] = (sums[0].normalized(), sums[1].normalized(), sums[2].normalized(), corner)
    return out


def room_limits(bm, acc, frames, width):
    """0.24.58 How wide the bevel may be at each rim point: under half the part's thickness along the old surface
    and across the cut wall (rays from just inside the corner) - a width bigger than the part made the two sides'
    bevels run into each other."""
    from mathutils.bvhtree import BVHTree
    bvh = BVHTree.FromBMesh(bm)
    lim = {}
    for vi, (df, dw, o, k) in acc.items():
        fr = frames.get(vi)
        dirs = (fr[0], fr[1]) if fr is not None and not fr[3] else (miter(df, k), miter(dw, k))
        o = (fr[2] if fr is not None else o.normalized())
        q = bm.verts[vi].co - o * (width * 0.02)
        w = width
        for d in dirs:
            if d.length < 1e-9:
                continue
            hit = bvh.ray_cast(q, d.normalized(), width * 4.0 * d.length)
            if hit[0] is not None:
                w = min(w, 0.45 * hit[3] / d.length)
        lim[vi] = max(w, width * 0.05)
    return lim


def mark_rim(mesh, mode, width, segments):
    """Store the rim edges and each rim point's profile on ``mesh``.  Returns (profile size, rim edge count)."""
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        layer = cg._face_flag_layer(bm)
        if layer is None:
            return 0, 0
        edges = cg._rim_edges(bm, layer)
        if not edges:
            return 0, 0
        acc = {}
        for e in edges:
            f0, f1 = e.link_faces
            fo, fc = (f1, f0) if f0[layer] else (f0, f1)       # old surface / cut wall
            t = (e.verts[1].co - e.verts[0].co)
            if t.length < 1e-12:
                continue
            t.normalize()
            dirs = []
            for f in (fo, fc):                       # into the face: left of its loop along the edge
                lp = next(l for l in e.link_loops if l.face == f)
                along = lp.link_loop_next.vert.co - lp.vert.co
                dirs.append(f.normal.cross(along).normalized())
            out = (fo.normal + fc.normal)
            for v in e.verts:
                s = acc.setdefault(v.index, [Vector(), Vector(), Vector(), 0])
                s[0] += dirs[0]
                s[1] += dirs[1]
                s[2] += out
                s[3] += 1
        n = (segments + 1 if mode != 'CHAMFER' else 2) + 2
        cols = [[0.0, 0.0, 0.0] * len(bm.verts) for _j in range(n)]
        dcol = [0.0, 0.0, 0.0] * len(bm.verts)
        bm.verts.ensure_lookup_table()
        frames = smooth_frames(bm, edges, acc, width)
        lim = room_limits(bm, acc, frames, width)
        lim = _smooth_limits(edges, lim, width)
        LAST['limited'] = min(lim.values()) if lim and min(lim.values()) < width * 0.98 else None
        for vi, (df, dw, out, k) in acc.items():
            if df.length < 1e-9 or dw.length < 1e-9 or out.length < 1e-9:
                continue
            fr = frames.get(vi)
            if fr is not None and not fr[3]:
                d_face, d_wall, o = fr[0], fr[1], fr[2]
            else:
                d_face, d_wall, o = miter(df, k), miter(dw, k), out.normalized()
            pts = profile_points(bm.verts[vi].co, d_face, d_wall, o, lim.get(vi, width), mode, segments)
            for j, q in enumerate(pts):
                cols[j][vi * 3:vi * 3 + 3] = list(q)
            dcol[vi * 3:vi * 3 + 3] = list((dw.normalized() - df.normalized()).cross(out.normalized()))
        rim_flags = [False] * len(bm.edges)
        for e in edges:
            rim_flags[e.index] = True
    finally:
        bm.free()
    for name in [a.name for a in mesh.attributes if a.name in (RIM, DIR) or a.name.startswith(POINT)]:
        mesh.attributes.remove(mesh.attributes[name])
    attr = mesh.attributes.new(RIM, 'BOOLEAN', 'EDGE')
    attr.data.foreach_set('value', rim_flags)
    for j in range(n):
        attr = mesh.attributes.new(f'{POINT}{j}', 'FLOAT_VECTOR', 'POINT')
        attr.data.foreach_set('vector', cols[j])
    attr = mesh.attributes.new(DIR, 'FLOAT_VECTOR', 'POINT')
    attr.data.foreach_set('vector', dcol)
    return n, len(edges)


def drop_copies(mesh, keep):
    """The sweep carries the part's attributes along its curves (as point attributes) and the Boolean keeps both:
    a second ``UVMap`` / cutter flag on the points.  Only the ones the mesh had before stay."""
    names = {n for n, _d in keep}
    for _ in range(64):
        extra = next((a for a in mesh.attributes if a.name in names and (a.name, a.domain) not in keep), None)
        if extra is None:
            break
        twins = [a for a in mesh.attributes if a.name == extra.name]
        if len(twins) > 1:            # removing by a shared name could hit the wrong one: rename it first
            extra.name = extra.name + '_mch_drop'
            extra = mesh.attributes.get(extra.name)
        mesh.attributes.remove(extra)


def clear(mesh):
    for name in [a.name for a in mesh.attributes if a.name in (RIM, DIR) or a.name.startswith(POINT)]:
        mesh.attributes.remove(mesh.attributes[name])


def _sweep(mesh, n, fast):
    scene = bpy.context.scene
    ob = bpy.data.objects.new('MCH_RimSweep_tmp', mesh)
    scene.collection.objects.link(ob)
    try:
        mod = ob.modifiers.new('MCH_RimSweep', 'NODES')
        mod.node_group = ensure_group(n, fast)
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
        ev = ob.evaluated_get(dg)
        return bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    finally:
        bpy.data.objects.remove(ob)


def _volume(me):
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        return bm.calc_volume(signed=True), sum(1 for e in bm.edges if not e.is_manifold)
    finally:
        bm.free()


def _clean(res, before):
    """A closed result that is a bit smaller than the part (a flipped or lost piece changes the volume a lot)."""
    if len(res.polygons) == 0:
        return False
    v1, open_edges = _volume(res)
    v0, _o = _volume(before)
    return open_edges == 0 and v0 > 0 and 0.5 * v0 < v1 <= v0 * 1.0001


def _smooth_limits(edges, lim, width, passes=12):
    """The width limits eased along the rim (a smaller limit spreads to its neighbours, never grows)."""
    nbr = {}
    for e in edges:
        a, b = e.verts[0].index, e.verts[1].index
        nbr.setdefault(a, []).append(b)
        nbr.setdefault(b, []).append(a)
    w = dict(lim)
    if all(v >= width * 0.98 for v in w.values()):
        return w
    for _p in range(passes):
        nxt = {}
        for vi, val in w.items():
            ns = [w[j] for j in nbr.get(vi, []) if j in w]
            nxt[vi] = min(val, 0.5 * val + 0.5 * sum(ns) / len(ns)) if ns else val
        w = nxt
    return w


LAST = {}


def finish(mesh, mode='CHAMFER', width=0.01, segments=3):
    """Chamfer / bevel the cut's rim on ``mesh`` (object space) with the Geometry Nodes sweep.  Returns the
    number of rim edges finished (0 = nothing done, the mesh unchanged)."""
    if mode not in {'CHAMFER', 'BEVEL'} or width <= 0 or mesh.attributes.get(cg.CUTTER_ATTR) is None:
        return 0
    keep = {(a.name, a.domain) for a in mesh.attributes}
    n, count = mark_rim(mesh, mode, width, segments)
    if not count:
        clear(mesh)
        return 0
    closed = cg.non_manifold_edge_count(mesh) == 0
    res = _sweep(mesh, n, fast=closed)
    if closed and not _clean(res, mesh):       # the fast result is not right: the slow, sure way
        bpy.data.meshes.remove(res)
        res = _sweep(mesh, n, fast=False)
    try:
        if len(res.polygons) == 0:
            clear(mesh)
            return 0
        smooth = {i for i, p in enumerate(mesh.polygons) if p.use_smooth}
        mesh.clear_geometry()
        bm = bmesh.new()
        try:
            bm.from_mesh(res)
            bm.to_mesh(mesh)
        finally:
            bm.free()
        clear(mesh)
        drop_copies(mesh, keep)
        if not smooth:
            for p in mesh.polygons:
                p.use_smooth = False
    finally:
        bpy.data.meshes.remove(res)
    mesh.update()
    return count
