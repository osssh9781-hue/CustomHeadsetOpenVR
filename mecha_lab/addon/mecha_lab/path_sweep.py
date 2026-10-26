"""0.24.33 Path Move without stretching the mesh: read the section where you grab, then sweep it along the path.

* Extend: the mesh is cut where you grab (a plane across the drag direction, only the part you grabbed); the cut
  section runs along the path as new rings and the cut-off end (the tip) is carried to the end of the path, turned
  with it.  The rings start on the cut edge itself, so it is one clean mesh - it looks as if the part was pulled.
* Separate Tube: the same section swept into a new object (the original is untouched); Merge joins it later
  (Join = one object, Union = boolean).
Both are light while you drag: only the new rings (and the tip) are rebuilt, never the whole mesh.
``min_rotation``, ``sweep_frames``, ``order_loop``, ``rings`` and ``tube_faces`` are pure; ``analyse``, ``extend``
and ``sweep_object`` work on a mesh.
"""
from __future__ import annotations

import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

SOURCE_KEY = 'mch_path_source'           # a Separate Tube remembers the mesh it came from (Merge)


# -----------------------------------------------------------------------------
# pure parts
# -----------------------------------------------------------------------------


def min_rotation(a, b):
    """The smallest turn (3x3) taking direction a to direction b."""
    a, b = Vector(a).normalized(), Vector(b).normalized()
    c = a.cross(b)
    d = max(-1.0, min(1.0, a.dot(b)))
    if c.length < 1e-9:
        if d > 0:
            return Matrix.Identity(3)
        axis = a.orthogonal().normalized()                  # half turn round any axis across a
        return Matrix.Rotation(math.pi, 3, axis)
    return Matrix.Rotation(math.atan2(c.length, d), 3, c.normalized())


def sweep_frames(path, start_dir, turn=True):
    """One turn (3x3) per path point: the section turns with the path (parallel transport) - or stays (turn off)."""
    n = len(path)
    rot = Matrix.Identity(3)
    out = [rot.copy()]
    prev = Vector(start_dir).normalized()
    for k in range(1, n):
        t = Vector(path[min(k + 1, n - 1)]) - Vector(path[k - 1])
        if t.length < 1e-12:
            out.append(rot.copy())
            continue
        t.normalize()
        if turn:
            rot = min_rotation(prev, t) @ rot
        prev = t
        out.append(rot.copy())
    return out


def rings(loop, centre, path, frames, taper=0.0):
    """Ring k = the section moved to path point k, turned by frame k, scaled by the taper."""
    n = len(path)
    out = []
    for k, (p, rot) in enumerate(zip(path, frames)):
        s = 1.0 - taper * (k / max(n - 1, 1))
        out.append([Vector(p) + rot @ ((Vector(q) - centre) * s) for q in loop])
    return out


def tube_faces(n_rings, n_loop, first=0):
    """Quads between consecutive rings (vertex index = first + ring * n_loop + i)."""
    faces = []
    for k in range(n_rings - 1):
        a, b = first + k * n_loop, first + (k + 1) * n_loop
        for i in range(n_loop):
            j = (i + 1) % n_loop
            faces.append((a + i, a + j, b + j, b + i))
    return faces


def order_loop(edges):
    """Edges (vertex pairs) of one closed loop -> its vertices in order; None when it is not one closed loop."""
    adj = {}
    for a, b in edges:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    if not adj or any(len(v) != 2 for v in adj.values()):
        return None
    start = next(iter(adj))
    out, prev, cur = [start], None, start
    while True:
        nxt = adj[cur][0] if adj[cur][0] != prev else adj[cur][1]
        if nxt == start:
            break
        out.append(nxt)
        prev, cur = cur, nxt
        if len(out) > len(adj):
            return None
    return out if len(out) == len(adj) else None


def ccw(loop, normal):
    """True when the loop turns counter-clockwise seen from the normal's tip."""
    c = sum((Vector(q) for q in loop), Vector()) / len(loop)
    s = Vector()
    for i in range(len(loop)):
        s += (Vector(loop[i]) - c).cross(Vector(loop[(i + 1) % len(loop)]) - c)
    return s.dot(Vector(normal)) > 0


def even_resample(loop, count):
    """A closed loop resampled to ``count`` points evenly along its length."""
    pts = [Vector(q) for q in loop] + [Vector(loop[0])]
    lens = [0.0]
    for a, b in zip(pts, pts[1:]):
        lens.append(lens[-1] + (b - a).length)
    total = lens[-1]
    out, j = [], 0
    for i in range(count):
        s = total * i / count
        while j < len(pts) - 2 and lens[j + 1] < s:
            j += 1
        seg = lens[j + 1] - lens[j]
        out.append(pts[j].lerp(pts[j + 1], 0.0 if seg < 1e-12 else (s - lens[j]) / seg))
    return out


# -----------------------------------------------------------------------------
# reading the section
# -----------------------------------------------------------------------------


def _component(bm, face):
    seen = {face}
    stack = [face]
    while stack:
        f = stack.pop()
        for e in f.edges:
            for g in e.link_faces:
                if g not in seen:
                    seen.add(g)
                    stack.append(g)
    return seen


def _cut(bm, hit, normal):
    """Cut the grabbed part (the connected piece under the hit) with the plane; the closed cut loop nearest the
    hit as (ordered verts, its edges) - or None."""
    bvh = BVHTree.FromBMesh(bm)
    loc, _n, idx, _d = bvh.find_nearest(hit)
    if loc is None:
        return None
    bm.faces.ensure_lookup_table()
    comp = _component(bm, bm.faces[idx])
    verts = {v for f in comp for v in f.verts}
    edges = {e for f in comp for e in f.edges}
    res = bmesh.ops.bisect_plane(bm, geom=list(verts) + list(edges) + list(comp), dist=1e-7,
                                 plane_co=hit, plane_no=normal)
    cut = [e for e in res['geom_cut'] if isinstance(e, bmesh.types.BMEdge)]
    if not cut:
        return None
    groups, left = [], set(cut)                              # connected pieces of the cut
    while left:
        e = left.pop()
        grp, stack = [e], [e]
        while stack:
            x = stack.pop()
            for v in x.verts:
                for y in v.link_edges:
                    if y in left:
                        left.remove(y)
                        grp.append(y)
                        stack.append(y)
        groups.append(grp)
    best = min(groups, key=lambda g: min((v.co - hit).length for e in g for v in e.verts))
    order = order_loop([(e.verts[0], e.verts[1]) for e in best])
    if order is None or len(order) < 3:
        return None
    return order, best


def analyse(me, hit, normal):
    """What a grab at ``hit`` dragged along ``normal`` would sweep (on a copy, nothing changes):
    {'loop': section points CCW, 'centre', 'tip': (coords, faces) of the cut-off end or None}."""
    bm = bmesh.new()
    bm.from_mesh(me)
    try:
        got = _cut(bm, Vector(hit), Vector(normal))
        if got is None:
            return None
        order, cut_edges = got
        loop = [v.co.copy() for v in order]
        if not ccw(loop, normal):
            loop.reverse()
        centre = sum(loop, Vector()) / len(loop)
        tip = _tip_faces(bm, cut_edges, Vector(hit), Vector(normal))
        tip_mesh = None
        if tip is not None:
            vs = sorted({v for f in tip for v in f.verts}, key=lambda v: v.index)
            index = {v: i for i, v in enumerate(vs)}
            tip_mesh = (np.array([v.co[:] for v in vs], dtype=np.float64),
                        [tuple(index[v] for v in f.verts) for f in tip])
        return {'loop': loop, 'centre': centre, 'tip': tip_mesh}
    finally:
        bm.free()


def _tip_faces(bm, cut_edges, hit, normal):
    """Split along the cut; the faces on the far side (the drag side) that the cut really cuts off - None when the
    cut does not separate them (an open sheet, a cut that misses part of the loop)."""
    bmesh.ops.split_edges(bm, edges=cut_edges)
    seeds = set()
    for e in cut_edges:
        for v in e.verts:
            for f in v.link_faces:
                if (f.calc_center_median() - hit).dot(normal) > 0:
                    seeds.add(f)
    if not seeds:
        return None
    tip, stack = set(seeds), list(seeds)
    while stack:
        f = stack.pop()
        for e in f.edges:
            for g in e.link_faces:
                if g not in tip:
                    tip.add(g)
                    stack.append(g)
    if any((f.calc_center_median() - hit).dot(normal) < -1e-6 for f in tip):
        return None                                          # it leaks round to the near side: not cut off
    behind = [f for e in cut_edges for v in e.verts for f in v.link_faces if f not in tip]
    if not behind:
        return None                                          # nothing stays behind
    return tip


# -----------------------------------------------------------------------------
# building
# -----------------------------------------------------------------------------


def path_from(centre, offsets):
    return [Vector(centre) + Vector(o) for o in offsets]


def preview_geometry(info, path, normal, turn=True, taper=0.0, method='EXTEND', hardness=1.0):
    """(verts, faces) for the drag preview: the rings, end caps (Separate Tube) or the carried tip (Extend)."""
    loop, centre = info['loop'], info['centre']
    path = soften_path(path, normal, soft_length(loop, centre, hardness))
    frames = sweep_frames(path, normal, turn)
    rs = rings(loop, centre, path, frames, taper)
    n = len(loop)
    verts = [q for r in rs for q in r]
    faces = tube_faces(len(rs), n)
    s_end = 1.0 - taper
    if method == 'EXTEND' and info.get('tip') is not None:
        co, tf = info['tip']
        rot = np.array(frames[-1])
        moved = (co - np.array(centre)) @ rot.T * s_end + np.array(path[-1])
        base = len(verts)
        verts += [Vector(q) for q in moved]
        faces += [tuple(base + i for i in f) for f in tf]
    else:
        faces.append(tuple(range(n - 1, -1, -1)))            # start cap (inside the mesh)
        last = (len(rs) - 1) * n
        faces.append(tuple(last + i for i in range(n)))
    return verts, faces


def soften_path(path, start_dir, length):
    """0.24.40 Hardness < 1: the first ``length`` of the path becomes a smooth curve that leaves the cut straight
    along ``start_dir`` (the way the part already points) and runs into the drawn path - a soft bend instead of a
    kink at the cut.  Same number of points; the rest of the path is unchanged."""
    path = [Vector(p) for p in path]
    if length <= 1e-9 or len(path) < 3:
        return path
    lens = [0.0]
    for a, b in zip(path, path[1:]):
        lens.append(lens[-1] + (b - a).length)
    length = min(length, lens[-1] * 0.6)
    k = max((i for i in range(len(path) - 1) if lens[i] <= length), default=0)
    if k < 1:
        return path
    p0, p3 = path[0], path[k]
    t3 = (path[min(k + 1, len(path) - 1)] - path[k - 1])
    t3 = t3.normalized() if t3.length > 1e-12 else Vector(start_dir).normalized()
    h = lens[k] / 3.0
    p1, p2 = p0 + Vector(start_dir).normalized() * h, p3 - t3 * h
    out = []
    for i in range(k + 1):
        t = lens[i] / lens[k]
        u = 1.0 - t
        out.append(p0 * (u * u * u) + p1 * (3 * u * u * t) + p2 * (3 * u * t * t) + p3 * (t * t * t))
    return out + path[k + 1:]


def soft_length(loop, centre, hardness):
    """How long the soft bend at the start is: (1 - Hardness) x 3 section radii."""
    soft = max(0.0, min(1.0, 1.0 - hardness))
    if soft <= 1e-3:
        return 0.0
    return soft * 3.0 * max((Vector(q) - Vector(centre)).length for q in loop)


def extend(me, hit, normal, offsets, turn=True, taper=0.0, hardness=1.0):
    """Extend on the mesh itself.  Returns a short report, or raises ValueError (mesh untouched).
    0.24.40 ``hardness`` < 1: a soft start - where the path turns, the part bends out of the cut in a smooth curve
    instead of a kink (0 = softest); 1 = hard, the section follows the drawn path right from the cut."""
    hit, normal = Vector(hit), Vector(normal).normalized()
    bm = bmesh.new()
    bm.from_mesh(me)
    try:
        got = _cut(bm, hit, normal)
        if got is None:
            raise ValueError('no closed section where you grabbed')
        order, cut_edges = got
        loop = [v.co.copy() for v in order]
        if not ccw(loop, normal):
            loop.reverse()
        centre = sum(loop, Vector()) / len(loop)
        tip = _tip_faces(bm, cut_edges, hit, normal)
        if tip is None:
            raise ValueError('the cut does not cut the end off (try Separate Tube)')
        tip_verts = {v for f in tip for v in f.verts}
        kd = KDTree(len(bm.verts))
        for v in bm.verts:
            kd.insert(v.co, v.index)
        kd.balance()
        bm.verts.ensure_lookup_table()
        base_ring, tip_ring = [], []
        for q in loop:                                       # each cut point: its base copy and its tip copy
            pair = [bm.verts[i] for _c, i, _d in kd.find_range(q, 1e-6)]
            b = [v for v in pair if v not in tip_verts and v.link_faces]
            t = [v for v in pair if v in tip_verts]
            if not b or not t:
                raise ValueError('the cut edge could not be followed')
            base_ring.append(b[0])
            tip_ring.append(t[0])
        path = soften_path(path_from(centre, offsets), normal, soft_length(loop, centre, hardness))
        frames = sweep_frames(path, normal, turn)
        rs = rings(loop, centre, path, frames, taper)
        rot, s_end = frames[-1], 1.0 - taper
        for v in tip_verts:                                  # the cut-off end goes to the end of the path
            v.co = path[-1] + rot @ ((v.co - centre) * s_end)
        ref = next(iter(base_ring[0].link_faces))
        all_rings = [base_ring] + [[bm.verts.new(q) for q in r] for r in rs[1:-1]] + [tip_ring]
        n = len(loop)
        for k in range(len(all_rings) - 1):
            a, b = all_rings[k], all_rings[k + 1]
            for i in range(n):
                j = (i + 1) % n
                try:
                    f = bm.faces.new((a[i], a[j], b[j], b[i]))
                    f.smooth, f.material_index = ref.smooth, ref.material_index
                except ValueError:
                    pass
        bm.normal_update()
        bm.to_mesh(me)
        me.update()
        return f'Extend: {len(path) - 1} steps, section {n} points'
    finally:
        bm.free()


def sweep_object(context, ob, hit, normal, offsets, turn=True, taper=0.0, max_points=64, hardness=1.0):
    """Separate Tube: a new object next to ob (same place, materials, Mirror)."""
    info = analyse(ob.data, hit, normal)
    if info is None:
        raise ValueError('no closed section where you grabbed')
    loop = info['loop']
    if len(loop) > max_points:
        loop = even_resample(loop, max_points)
        info = dict(info, loop=loop, centre=sum(loop, Vector()) / len(loop))
    path = path_from(info['centre'], offsets)
    verts, faces = preview_geometry(info, path, normal, turn, taper, 'SWEEP', hardness)
    me = bpy.data.meshes.new(ob.name + '_Path')
    me.from_pydata([tuple(v) for v in verts], [], faces)
    smooth = any(p.use_smooth for p in ob.data.polygons[:64])
    for p in me.polygons:
        p.use_smooth = smooth
    me.update()
    for m in ob.data.materials:
        me.materials.append(m)
    new = bpy.data.objects.new(ob.name + '_Path', me)
    for coll in ob.users_collection:
        coll.objects.link(new)
    new.matrix_world = ob.matrix_world.copy()
    copy_mirror(ob, new)
    new[SOURCE_KEY] = ob.name
    return new


def copy_mirror(src, dst):
    for m in src.modifiers:
        if m.type == 'MIRROR' and m.show_viewport:
            nm = dst.modifiers.new(m.name, 'MIRROR')
            nm.use_axis = m.use_axis[:]
            nm.mirror_object = m.mirror_object
            nm.use_clip, nm.use_mirror_merge = m.use_clip, m.use_mirror_merge
            break


def merge(context, tube, mode='JOIN'):
    """Merge a Separate Tube into the mesh it came from: Join (one object) or Union (boolean)."""
    src = bpy.data.objects.get(tube.get(SOURCE_KEY, ''))
    if src is None or src.type != 'MESH':
        raise ValueError('the mesh it came from is gone')
    for m in [m for m in tube.modifiers if m.type == 'MIRROR']:
        tube.modifiers.remove(m)                             # the source's own Mirror copies it again
    if mode == 'UNION':
        mod = src.modifiers.new('MCH_PathUnion', 'BOOLEAN')
        mod.operation, mod.object = 'UNION', tube
        try:
            mod.solver = 'EXACT'
        except TypeError:
            pass
        with context.temp_override(object=src, active_object=src, selected_objects=[src]):
            bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=0)   # before the Mirror
            bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(tube, do_unlink=True)
        return src
    with context.temp_override(object=src, active_object=src, selected_editable_objects=[src, tube],
                               selected_objects=[src, tube]):
        bpy.ops.object.join()
    return src
