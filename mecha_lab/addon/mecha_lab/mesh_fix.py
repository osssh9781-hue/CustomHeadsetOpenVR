"""0.24.76 Fix Mesh (like ZBrush's Fix Mesh): repair what Booleans, joins and exports leave behind so a part is one
closed solid again - Quad Remesh / Make Quad / Edge Mesh then work on it.

In order (``fix_bm``):
1. Points lying on each other along an open side, a sliver or a 3+-face edge are welded (cracks zip shut).
2. Zero-area faces and zero-length edges are dissolved (Boolean slivers, split n-gons).
3. A face repeated on the same points is removed.
4. Inside walls: a piece of surface bounded by 3+-face edges that lies inside the solid (rays from it leave the
   solid an odd number of times) is removed - a join / union with its shared wall left in.  Any 3+-face edge still
   there: its faces are removed and the hole filled (as Quad Remesh's own hole closing).
5. Small holes (at most HOLE_SIDES sides, a rim under HOLE_RIM of the part size, or no area - a seam crack; all
   with ``all_holes``) are filled; a flap hanging into a hole by two open sides is removed.  Quad Remesh's own
   repair ('CRACKS') never caps the part's own open border.
6. Normals made consistent.
Returns what was done (``stats``)."""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Vector

WELD = 1e-4               # points closer than this x the part size are one (only where the surface is broken)
DEGEN = 1e-6              # faces / edges smaller than this x the part size are dissolved
HOLE_SIDES = 12           # holes with at most this many sides are filled ...
HOLE_RIM = 0.05           # ... or with a rim shorter than this x the part size
CRACK_AREA = 5e-4         # ... or spanning less than this x its rim squared (a seam / T-junction crack: always)
RAYS = (Vector((0.267, 0.534, 0.802)), Vector((-0.802, 0.267, 0.534)), Vector((0.534, -0.802, 0.267)))


def size_of(bm):
    if not bm.verts:
        return 1.0
    lo = Vector([min(v.co[k] for v in bm.verts) for k in range(3)])
    hi = Vector([max(v.co[k] for v in bm.verts) for k in range(3)])
    return max((hi - lo).length, 1e-9)


def faults(bm):
    """(open sides, 3+-face edges)."""
    return (sum(1 for e in bm.edges if e.is_boundary), sum(1 for e in bm.edges if len(e.link_faces) > 2))


def _drop_loose(bm):
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
    wires = [e for e in bm.edges if not e.link_faces]
    if wires:
        bmesh.ops.delete(bm, geom=wires, context='EDGES')


def _inside(bvh, faces, size, nfaces):
    """True when the surface piece ``faces`` lies inside the rest of the solid: from points on it, rays leave the
    rest an odd number of times (majority of a few rays from a few faces).  0.24.81 ``bvh`` is one tree of the
    whole mesh (hits on the piece itself are stepped over) - a tree of the rest was built for every piece before:
    270 pieces on a 163k-face ZBrush part = 47 s of a 51 s Fix Mesh."""
    keep = {f.index for f in faces}
    if len(keep) >= nfaces:
        return False
    probes = sorted(faces, key=lambda f: -f.calc_area())[:5]
    votes = 0
    total = 0
    for f in probes:
        c = f.calc_center_median()
        for d in RAYS:
            n = 0
            o = c + d * (size * 1e-6)
            for _k in range(64):
                hit = bvh.ray_cast(o, d, size * 4.0)
                if hit[0] is None:
                    break
                if hit[2] not in keep:
                    n += 1
                o = hit[0] + d * (size * 1e-6)
            votes += n % 2
            total += 1
    return total > 0 and votes * 2 > total


def _inside_walls(bm, size):
    """Remove surface pieces bounded by 3+-face edges that lie inside the solid.  Returns how many faces went."""
    multi = {e for e in bm.edges if len(e.link_faces) > 2}
    if not multi:
        return 0
    seen, pieces = set(), []
    for f0 in {f for e in multi for f in e.link_faces}:
        if f0 in seen:
            continue
        piece, stack = [], [f0]
        seen.add(f0)
        while stack:
            f = stack.pop()
            piece.append(f)
            for e in f.edges:
                if e in multi or not e.is_manifold:
                    continue
                for g in e.link_faces:
                    if g not in seen:
                        seen.add(g)
                        stack.append(g)
        pieces.append(piece)
    gone = []
    from mathutils.bvhtree import BVHTree
    bm.faces.index_update()
    bvh = BVHTree.FromBMesh(bm, epsilon=0.0)
    nfaces = len(bm.faces)
    for piece in sorted(pieces, key=len):
        if len(piece) > 0.5 * nfaces:
            continue                                 # (the main surface itself is never a wall)
        if _inside(bvh, piece, size, nfaces):
            gone += piece
    if gone:
        bmesh.ops.delete(bm, geom=gone, context='FACES_ONLY')
        _drop_loose(bm)
    return len(gone)


def _hole_loops(bm):
    seen, loops = set(), []
    for e0 in bm.edges:
        if not e0.is_boundary or e0 in seen:
            continue
        loop, stack = [], [e0]
        seen.add(e0)
        while stack:
            e = stack.pop()
            loop.append(e)
            for v in e.verts:
                for g in v.link_edges:
                    if g.is_boundary and g not in seen:
                        seen.add(g)
                        stack.append(g)
        loops.append(loop)
    return loops


def _on_border(lp, border, tol):
    """Most of hole loop ``lp`` lies on the part's own open border (``border``: KD tree of its sides' middles)."""
    if border is None:
        return False
    on = sum(1 for e in lp if border.find((e.verts[0].co + e.verts[1].co) * 0.5)[2] <= tol)
    return on * 2 > len(lp)


def _loop_area(lp):
    """Area spanned by hole loop ``lp`` (its points in order round it; Newell)."""
    nxt = {}
    for e in lp:
        a, b = e.verts
        nxt.setdefault(a, []).append(b)
        nxt.setdefault(b, []).append(a)
    start = lp[0].verts[0]
    ring, prev, cur = [start], None, start
    for _k in range(len(lp)):
        nb = [v for v in nxt.get(cur, ()) if v is not prev]
        if not nb or nb[0] is start:
            break
        prev, cur = cur, nb[0]
        ring.append(cur)
    n = Vector()
    for i in range(len(ring)):
        a, b = ring[i - 1].co, ring[i].co
        n += a.cross(b)
    return 0.5 * n.length


def _crack(lp):
    """A hole with (almost) no area - a T-junction / seam crack, however long its rim."""
    rim = sum(e.calc_length() for e in lp)
    return rim > 0.0 and _loop_area(lp) <= CRACK_AREA * rim * rim


def _fill(bm, size, fill, border=None):
    """Fill holes: 'ALL', 'SMALL' (few sides or a short rim) or 'CRACKS' (a short rim, or a hole the repair made
    itself: an open part's own border - ``border`` - is never capped, however few sides it has)."""
    filled = 0
    tol = size * WELD * 10.0
    for _r in range(3):
        loops = _hole_loops(bm)
        todo = [lp for lp in loops if fill == 'ALL' or (fill == 'SMALL' and len(lp) <= HOLE_SIDES)
                or sum(e.calc_length() for e in lp) <= HOLE_RIM * size or _crack(lp)
                or (fill == 'CRACKS' and not _on_border(lp, border, tol))]
        if not todo:
            break
        res = bmesh.ops.holes_fill(bm, edges=[e for lp in todo for e in lp], sides=0)
        new = res.get('faces', [])
        filled += len(new)
        if new:
            tri = bmesh.ops.triangulate(bm, faces=new)['faces']
            bmesh.ops.join_triangles(bm, faces=tri, cmp_seam=False, cmp_sharp=False, cmp_uvs=False,
                                     cmp_vcols=False, cmp_materials=False, angle_face_threshold=math.radians(30),
                                     angle_shape_threshold=math.radians(60))
        flaps = list({f for e in bm.edges if e.is_boundary for f in e.link_faces
                      if sum(1 for g in f.edges if g.is_boundary) >= 2})
        if not flaps:
            break
        bmesh.ops.delete(bm, geom=flaps, context='FACES_ONLY')
        _drop_loose(bm)
    return filled


def fix_bm(bm, all_holes=False, fill='SMALL'):
    """Repair ``bm`` in place (``fill``: which holes are filled, see ``_fill``; ``all_holes`` = 'ALL').  Returns
    stats."""
    if all_holes:
        fill = 'ALL'
    st = {'faces_before': len(bm.faces)}
    st['open_before'], st['multi_before'] = faults(bm)
    size = size_of(bm)
    border = None
    if fill == 'CRACKS':                             # (the part's own open border, to tell it from new holes)
        from mathutils.kdtree import KDTree
        sides = [e for e in bm.edges if e.is_boundary]
        if sides:
            border = KDTree(len(sides))
            for i, e in enumerate(sides):
                border.insert((e.verts[0].co + e.verts[1].co) * 0.5, i)
            border.balance()
    # 1. weld where the surface is broken
    broken = set()
    for e in bm.edges:
        if not e.is_manifold:
            broken.update(e.verts)
    for f in bm.faces:
        if f.calc_area() <= (size * DEGEN) ** 2 * 10.0:
            broken.update(f.verts)
    st['welded'] = 0
    if broken:
        tm = bmesh.ops.find_doubles(bm, verts=list(broken), keep_verts=[], dist=size * WELD)['targetmap']
        if tm:
            st['welded'] = len(tm)
            bmesh.ops.weld_verts(bm, targetmap=tm)
    # 2. slivers
    n = len(bm.faces)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=size * DEGEN)
    _drop_loose(bm)
    st['slivers'] = max(0, n - len(bm.faces))
    # 3. repeated faces
    keys, dup = {}, []
    for f in bm.faces:
        k = frozenset(v.index for v in f.verts)
        if k in keys:
            dup.append(f)
        else:
            keys[k] = f
    if dup:
        bmesh.ops.delete(bm, geom=dup, context='FACES_ONLY')
    st['repeated'] = len(dup)
    # 4. inside walls, then any 3+-face edge left: its faces out, the hole filled (5. small holes) - again while
    # filling made new ones (a few rounds)
    st['walls'] = _inside_walls(bm, size)
    st['fins'] = st['filled'] = 0
    for _r in range(4):
        multi = list({f for e in bm.edges if len(e.link_faces) > 2 for f in e.link_faces})
        if multi:
            bmesh.ops.delete(bm, geom=multi, context='FACES_ONLY')
            _drop_loose(bm)
            st['fins'] += len(multi)
        st['filled'] += _fill(bm, size, fill, border)
        if not multi:
            break
    # a fill that lay over a face next to it (an edge with 4 faces, two of them on top of each other): the smallest
    # faces at such an edge go, the hole they leave is filled once more
    extra = set()
    for e in bm.edges:
        if len(e.link_faces) > 2:
            extra.update(sorted(e.link_faces, key=lambda f: f.calc_area())[:len(e.link_faces) - 2])
    if extra:
        bmesh.ops.delete(bm, geom=list(extra), context='FACES_ONLY')
        _drop_loose(bm)
        st['fins'] += len(extra)
        st['filled'] += _fill(bm, size, fill, border)
    # 6. normals
    if bm.faces:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    st['open_after'], st['multi_after'] = faults(bm)
    st['faces_after'] = len(bm.faces)
    return st


def needs_fix(me):
    """Quick test: any open side / 3+-face edge (mesh data, no bmesh)."""
    import numpy as np
    if not len(me.polygons):
        return False
    lv = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get('edge_index', lv)
    cnt = np.bincount(lv, minlength=len(me.edges))
    return bool((cnt != 2).any())


def auto_fix(context, targets, what='Cut'):
    """0.24.81 Fix Mesh by itself before a Cut / Split / Box Hide / Boolean on a part that is not one clean solid
    (open sides, edges shared by 3+ faces - most ZBrush / FBX parts): the Booleans failed on such parts with a
    yellow "not one clean solid ... Fix Mesh it first" warning and nothing was cut.  Preferences > Auto Fix Mesh
    (on).  Returns {part name: (broken edges before, after)} for the parts that were repaired."""
    from .workspace_ui import pref
    if not pref('auto_fix_mesh', True):
        return {}
    out = {}
    for t in targets:
        try:
            me = t.data
            if t.type != 'MESH' or me is None or me.library or not needs_fix(me):
                continue
            st = fix_mesh(me)
            before = st.get('open_before', 0) + st.get('multi_before', 0)
            after = st.get('open_after', 0) + st.get('multi_after', 0)
            if changed(st) or after < before:
                out[t.name] = (before, after)
                t.update_tag()
        except (RuntimeError, ReferenceError, AttributeError, ValueError):
            continue
    return out


def auto_fix_note(fixed):
    """' | Fix Mesh first: Body 71 -> 0 broken edges' or ''."""
    if not fixed:
        return ''
    return ' | Fix Mesh first: ' + ', '.join(f'{n} {b:,} -> {a:,} broken edges' for n, (b, a) in fixed.items())


def changed(st):
    return any(st.get(k) for k in ('welded', 'slivers', 'repeated', 'walls', 'fins', 'filled'))


def fix_mesh(me, all_holes=False, fill='SMALL'):
    """Repair mesh data ``me`` in place (materials / smooth flags kept on the faces that stay).  Returns stats."""
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        st = fix_bm(bm, all_holes, fill)
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()
    return st


def report(st):
    done = []
    for key, word in (('welded', 'points welded'), ('slivers', 'slivers'), ('repeated', 'repeated faces'),
                      ('walls', 'inside wall faces'), ('fins', 'faces at 3+-face edges'), ('filled', 'holes filled')):
        if st.get(key):
            done.append(f'{st[key]:,} {word}')
    left = st['open_after'] + st['multi_after']
    head = (f'Fix Mesh: {st["open_before"] + st["multi_before"]:,} broken edges -> {left:,}'
            + (' (closed)' if not left else ' (a bigger hole: Close All Holes)'))
    return head + (' | ' + ', '.join(done) if done else ' | nothing to fix')


class MCH_OT_fix_mesh(bpy.types.Operator):
    """Repair the selected meshes like ZBrush's Fix Mesh: weld cracks, remove slivers, repeated faces and inside
    walls, fill small holes, make normals consistent (Quad Remesh / Make Quad need a closed solid)"""
    bl_idname = 'mch.fix_mesh'
    bl_label = 'Fix Mesh'
    bl_options = {'REGISTER', 'UNDO'}
    all_holes: bpy.props.BoolProperty(name='Close All Holes', default=False,
                                      description='Also fill big holes (an open plate gets capped)')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        obs = [o for o in context.selected_objects if o.type == 'MESH']
        msgs, shared = [], set()
        for ob in obs:
            if ob.data in shared:
                continue
            shared.add(ob.data)
            if ob.data.shape_keys is not None:
                msgs.append(f'{ob.name}: has shape keys (skipped)')
                continue
            st = fix_mesh(ob.data, self.all_holes)
            msgs.append(report(st) if len(obs) == 1 else f'{ob.name}: {st["open_after"] + st["multi_after"]} left')
        self.report({'INFO'}, '; '.join(msgs)[:400])
        return {'FINISHED'}


def register():
    bpy.utils.register_class(MCH_OT_fix_mesh)


def unregister():
    try:
        bpy.utils.unregister_class(MCH_OT_fix_mesh)
    except RuntimeError:
        pass
