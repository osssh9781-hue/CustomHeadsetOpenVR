"""0.24.94 Safe DynaMesh: why Blender's voxel remesh (our DynaMesh) tears a mesh into holes and fragments where
ZBrush's DynaMesh does not, and the four fixes made before every remesh.

ZBrush turns any mesh into a closed volume first.  Blender's voxel remesh (OpenVDB mesh-to-volume) needs one:

    1. **open edges** (a sheet, a hole, an extracted plate): the volume leaks, the remesh comes out with holes or
       nothing - holes are capped (a cap as big as the mesh is a sheet's outline: not kept), a sheet that stays open
       gets a thickness (solidified);
    2. **flipped faces** (inconsistent winding): the volume is inside out there - the normals are made consistent;
    3. **walls thinner than the voxel** (a thin plate, a horn tip): ``cap_voxel`` can cap the voxel at a third of the
       thinnest wall (ray cast) - off by default: measured, Blender's remesh keeps a 0.02 wall at a 0.12 voxel;
    4. **non-manifold edges / loose bits**: slivers survive as fragments - after the remesh, loose parts smaller
       than a few percent of the mesh are dropped.

``prepare`` + ``cleanup`` run round ``bpy.ops.object.voxel_remesh`` (see zb_sculpt.dynamesh); ``diagnose`` says what
a mesh has, so the panel / message can tell the user what was done.
"""
from __future__ import annotations

import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

SHEET_CAP = 0.5            # a boundary cap bigger than this share of the mesh's area is a sheet's outline, not a hole
CAP_BEND = 0.25            # 0.24.95 a cap whose corners stand off its own plane more than this x its width: not kept
CAP_OVERLAP = 1.1          # 0.24.95 ... or whose triangles cover this much more than the opening (it doubles back)
THICK_VOXELS = 3.0         # the voxel must fit this many times into the thinnest wall
SHEET_VOXELS = 3.0         # an open sheet gets this many voxels of thickness
MIN_PART = 0.02            # loose parts under this share of the faces are dropped after the remesh
MAX_PART_RATIO = 0.5       # ... unless they are at least this share of the biggest part (a real second piece)
SAMPLES = 400              # rays for the thickness estimate
MIN_VOXEL_FACTOR = 0.25    # the thin-wall cap never shrinks the voxel below this x the asked size (point explosion)
USE_THIN_CAP = False       # measured: Blender's remesh keeps a 0.02 wall at a 0.12 voxel (no fragments, no bloat), so
#                            the cap only multiplied the points - off; cap_voxel stays for a tool that wants it


def diagnose(me):
    """What the mesh has that breaks a voxel remesh: dict(open, nonmanifold, flipped, parts, verts, faces)."""
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        open_e = sum(1 for e in bm.edges if len(e.link_faces) == 1)
        nonman = sum(1 for e in bm.edges if len(e.link_faces) > 2)
        flipped = 0
        for e in bm.edges:
            if len(e.link_faces) == 2:
                fa, fb = e.link_faces
                # consistent winding: the edge runs opposite ways round the two faces
                da = _edge_dir(fa, e)
                db = _edge_dir(fb, e)
                if da == db:
                    flipped += 1
        parts = _parts(bm)
        return dict(open=open_e, nonmanifold=nonman, flipped=flipped, parts=len(parts), verts=len(bm.verts),
                    faces=len(bm.faces))
    finally:
        bm.free()


def _edge_dir(face, edge):
    vs = face.verts
    n = len(vs)
    for i in range(n):
        a, b = vs[i], vs[(i + 1) % n]
        if {a, b} == set(edge.verts):
            return a is edge.verts[0]
    return None


def _parts(bm):
    """Connected face groups: list of lists of face indices."""
    bm.faces.ensure_lookup_table()
    seen = set()
    out = []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack = [f]
        seen.add(f.index)
        comp = []
        while stack:
            g = stack.pop()
            comp.append(g.index)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index)
                        stack.append(h)
        out.append(comp)
    return out


def thickness(me, samples=SAMPLES, seed=7):
    """The thinnest wall (10th percentile of the inward ray hits from sampled faces); 0 when nothing hits
    (a sheet / open mesh)."""
    n = len(me.polygons)
    if n == 0:
        return 0.0
    verts = [v.co for v in me.vertices]
    polys = [list(p.vertices) for p in me.polygons]
    tree = BVHTree.FromPolygons(verts, polys, all_triangles=False)
    rng = np.random.default_rng(seed)
    idx = rng.choice(n, size=min(samples, n), replace=False)
    hits = []
    for i in idx:
        p = me.polygons[int(i)]
        c = p.center
        nrm = p.normal
        if nrm.length < 1e-9:
            continue
        o = c - nrm * 1e-4
        loc, _n, _i, d = tree.ray_cast(o, -nrm)
        if loc is not None and d is not None and d > 1e-6:
            hits.append(float(d))
    if len(hits) < max(4, len(idx) // 8):
        return 0.0
    return float(np.percentile(hits, 10))


def cap_voxel(me, voxel):
    """The voxel size capped so it fits THICK_VOXELS times into the thinnest wall; (voxel, thinnest)."""
    t = thickness(me)
    if t <= 0.0:
        return voxel, 0.0
    want = t / THICK_VOXELS
    if want < voxel:
        return max(want, voxel * MIN_VOXEL_FACTOR), t
    return voxel, t


def thicken(bm, t):
    """0.24.95 an open sheet made a closed slab ``t`` thick: a copy moved ``t`` back along the point normals, joined to
    the sheet along its open edges.  Blender's solidify makes a corner thicker by 1 / cos of its angle, and at a fold
    (a crumpled cloth turning back on itself) that factor blew a point 10 voxels out - a spike after the remesh.
    Here no point moves more than ``t``."""
    bm.normal_update()
    faces = list(bm.faces)
    border = [e for e in bm.edges if len(e.link_faces) == 1]
    old = set(bm.verts)
    res = bmesh.ops.duplicate(bm, geom=faces)
    vmap = {a: b for a, b in res['vert_map'].items() if a in old and b not in old}
    for a, b in vmap.items():
        n = a.normal
        b.co = a.co - (n.normalized() if n.length > 1e-12 else n) * t
    bmesh.ops.reverse_faces(bm, faces=[f for f in res['geom'] if isinstance(f, bmesh.types.BMFace)])
    for e in border:
        a, b = e.verts
        if a not in vmap or b not in vmap:
            continue
        forward = any(lp.vert is a and lp.link_loop_next.vert is b for lp in e.link_faces[0].loops)
        quad = (b, a, vmap[a], vmap[b]) if forward else (a, b, vmap[b], vmap[a])
        try:
            bm.faces.new(quad)
        except ValueError:                       # (that side face is there already)
            pass
    return len(vmap)


def folded_cap(face):
    """0.24.95 (user: "다이나메쉬 하면 가끔 뾰족하게 메쉬가 튀어") a hole cap that cannot lie flat: Blender fills a face in
    its own plane, so the cap of a bent or folded opening (a crumpled cloth's outline, a twisted cut) became
    triangles folding back over each other and out through the part - the voxel remesh turned them into spikes
    (a crumpled cloth: 1,867 points up to 12 voxels off it).  Such an opening is left open instead (the sheet gets
    its thickness).  True when the cap's corners stand off its plane more than CAP_BEND x its width, or its
    outline doubles back over itself - its triangles then cover more than the opening (the cloth: 2.23 against
    1.34) - or turn against it."""
    from mathutils.geometry import tessellate_polygon
    co = [v.co.copy() for v in face.verts]
    if len(co) < 4:
        return False
    face.normal_update()
    n = face.normal
    if n.length < 0.5:
        return True
    c = sum(co, Vector()) / len(co)
    width = 2.0 * max((p - c).length for p in co)
    if width <= 0.0:
        return False
    if max(abs((p - c).dot(n)) for p in co) > CAP_BEND * width:
        return True
    cover = 0.0
    for a, b, d in tessellate_polygon([co]):
        t = (co[b] - co[a]).cross(co[d] - co[a])
        if t.length > 1e-12 * width * width and t.dot(n) < 0.0:
            return True
        cover += t.length / 2.0
    return cover > CAP_OVERLAP * face.calc_area()


def quick_diag(me):
    """0.24.130 (user: "블렌더에서 다이나 메쉬 하는 것도 엄청 오래 걸려") What ``prepare`` would have to fix, read with numpy
    alone (no bmesh): loose points / edges, open (boundary) edges, non-manifold edges and inconsistently wound
    (flipped) faces - an edge shared by two faces must run opposite ways in them.  About 0.8 s on a million points
    where the bmesh pass took 11 s; None when the mesh has no faces."""
    import numpy as np
    nv, ne, nl, nf = len(me.vertices), len(me.edges), len(me.loops), len(me.polygons)
    if not nf or not ne:
        return None
    lv = np.empty(nl, dtype=np.int32)
    me.loops.foreach_get('vertex_index', lv)
    le = np.empty(nl, dtype=np.int32)
    me.loops.foreach_get('edge_index', le)
    used = np.zeros(nv, dtype=bool)
    used[lv] = True
    ecount = np.bincount(le, minlength=ne)
    ev = np.empty(ne * 2, dtype=np.int32)
    me.edges.foreach_get('vertices', ev)
    ev = ev.reshape(-1, 2)
    sign = np.where(lv == ev[le, 0], 1.0, -1.0)
    s = np.bincount(le, weights=sign, minlength=ne)
    two = ecount == 2
    return dict(loose=int((~used).sum()) + int((ecount == 0).sum()), boundary=int((ecount == 1).sum()),
                nonman=int((ecount > 2).sum()), flipped=int((two & (s != 0)).sum()))


def is_remesh_safe(me):
    """Closed, consistently wound, nothing loose: the voxel remesh needs no preparation."""
    d = quick_diag(me)
    return d is not None and d['loose'] == 0 and d['boundary'] == 0 and d['flipped'] == 0


def components(me):
    """0.24.130 Connected parts over the points (edges joined), numpy union-find: (label per point, number of parts).
    0.3 s on a million points where the bmesh walk took 2.7 s."""
    import numpy as np
    nv, ne = len(me.vertices), len(me.edges)
    parent = np.arange(nv, dtype=np.int64)
    if not ne:
        return parent, nv
    ev = np.empty(ne * 2, dtype=np.int64)
    me.edges.foreach_get('vertices', ev)
    ev = ev.reshape(-1, 2)
    a, b = ev[:, 0], ev[:, 1]

    def compress(par):
        for _j in range(64):
            p2 = par[par]
            if np.array_equal(p2, par):
                return par
            par = p2
        return par

    for _ in range(200):
        parent = compress(parent)
        ra, rb = parent[a], parent[b]
        diff = ra != rb
        if not diff.any():
            break
        lo = np.minimum(ra[diff], rb[diff])
        hi = np.maximum(ra[diff], rb[diff])
        np.minimum.at(parent, hi, lo)
    parent = compress(parent)
    roots, labels = np.unique(parent, return_inverse=True)
    return labels, len(roots)


def prepare(me, voxel):
    """The mesh made remesh-safe in place: doubles merged, normals consistent, small holes filled, an open sheet
    solidified, loose bits dropped.  Returns dict of what was done."""
    done = dict(merged=0, flipped=0, holes=0, solidified=False, loose=0)
    try:                              # 0.24.130 a closed, consistent mesh (the usual one - any earlier DynaMesh output)
        if is_remesh_safe(me):        # needs nothing: no bmesh pass (doubles do not matter to a volume remesh)
            return done
    except (ValueError, TypeError, RuntimeError):
        pass
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        nv = len(bm.verts)
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=max(voxel * 0.05, 1e-6))
        done['merged'] = nv - len(bm.verts)
        loose_v = [v for v in bm.verts if not v.link_faces]
        loose_e = [e for e in bm.edges if not e.link_faces]
        done['loose'] = len(loose_v) + len(loose_e)
        if loose_e:
            bmesh.ops.delete(bm, geom=loose_e, context='EDGES')
        loose_v = [v for v in loose_v if v.is_valid]     # 0.24.95 (deleting the loose edges took their points)
        if loose_v:
            bmesh.ops.delete(bm, geom=loose_v, context='VERTS')
        before = sum(1 for e in bm.edges if len(e.link_faces) == 2 and _edge_dir(e.link_faces[0], e) == _edge_dir(e.link_faces[1], e))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        done['flipped'] = before
        open_edges = [e for e in bm.edges if len(e.link_faces) == 1]
        if open_edges:
            area = sum(f.calc_area() for f in bm.faces)
            res = bmesh.ops.holes_fill(bm, edges=open_edges, sides=0)       # every boundary loop capped ...
            caps = res.get('faces', [])
            sheet = [f for f in caps if f.is_valid and (f.calc_area() > area * SHEET_CAP    # ... a cap as big as the
                                                        or folded_cap(f))]                    # mesh itself is a sheet's
            if sheet:                                                        # outline; 0.24.95 or one that folds
                bmesh.ops.delete(bm, geom=sheet, context='FACES_ONLY')
            done['holes'] = len(caps) - len(sheet)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
            if any(len(e.link_faces) == 1 for e in bm.edges):      # still open: a sheet - give it a thickness
                thicken(bm, voxel * SHEET_VOXELS)
                bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
                done['solidified'] = True
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()
    return done


def cleanup(me):
    """After the remesh: loose parts much smaller than the mesh dropped (slivers of a thin wall).  Returns the
    number of parts dropped."""
    import numpy as np
    nf = len(me.polygons)
    if nf < 2:
        return 0
    try:                                      # 0.24.130 the parts found with numpy (the bmesh walk took seconds)
        labels, n = components(me)
    except (ValueError, TypeError, RuntimeError, MemoryError):
        labels, n = None, 0
    if labels is None:
        bm = bmesh.new()
        try:
            bm.from_mesh(me)
            parts = _parts(bm)
            if len(parts) <= 1:
                return 0
            sizes = sorted((len(p) for p in parts), reverse=True)
            biggest, total = sizes[0], len(bm.faces)
            drop = [p for p in parts if len(p) < total * MIN_PART and len(p) < biggest * MAX_PART_RATIO]
            if not drop:
                return 0
            bm.faces.ensure_lookup_table()
            faces = [bm.faces[i] for p in drop for i in p]
            bmesh.ops.delete(bm, geom=faces, context='FACES')
            bm.to_mesh(me)
            return len(drop)
        finally:
            bm.free()
    if n <= 1:
        return 0
    starts = np.empty(nf, dtype=np.int64)
    me.polygons.foreach_get('loop_start', starts)
    lv = np.empty(len(me.loops), dtype=np.int64)
    me.loops.foreach_get('vertex_index', lv)
    fpart = labels[lv[starts]]                # a face's part = its first corner's
    sizes = np.bincount(fpart, minlength=n)
    biggest = int(sizes.max())
    small = np.nonzero((sizes < nf * MIN_PART) & (sizes < biggest * MAX_PART_RATIO))[0]
    if not len(small):
        return 0
    drop_mask = np.isin(fpart, small)
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        faces = [bm.faces[i] for i in np.nonzero(drop_mask)[0]]
        bmesh.ops.delete(bm, geom=faces, context='FACES')
        bm.to_mesh(me)
    finally:
        bm.free()
    return int(len(small))


def describe(done, voxel_asked, voxel_used, thin, dropped):
    """One line for the message: what Safe DynaMesh changed."""
    bits = []
    if done.get('holes'):
        bits.append(f'{done["holes"]} hole{"s" * (done["holes"] != 1)} filled')
    if done.get('solidified'):
        bits.append('open sheet given a thickness')
    if done.get('flipped'):
        bits.append(f'{done["flipped"]} flipped edge{"s" * (done["flipped"] != 1)} fixed')
    if voxel_used < voxel_asked * 0.999:
        bits.append(f'voxel {voxel_asked:.4g} -> {voxel_used:.4g} (thin wall {thin:.3g})')
    if dropped:
        bits.append(f'{dropped} sliver{"s" * (dropped != 1)} dropped')
    if done.get('loose'):
        bits.append(f'{done["loose"]} loose bits removed')
    return ', '.join(bits)
