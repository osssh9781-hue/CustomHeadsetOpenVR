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


def prepare(me, voxel):
    """The mesh made remesh-safe in place: doubles merged, normals consistent, small holes filled, an open sheet
    solidified, loose bits dropped.  Returns dict of what was done."""
    done = dict(merged=0, flipped=0, holes=0, solidified=False, loose=0)
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
            sheet = [f for f in caps if f.is_valid and f.calc_area() > area * SHEET_CAP]   # ... a cap as big as the
            if sheet:                                                        # mesh itself is a sheet's outline
                bmesh.ops.delete(bm, geom=sheet, context='FACES_ONLY')
            done['holes'] = len(caps) - len(sheet)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
            if any(len(e.link_faces) == 1 for e in bm.edges):      # still open: a sheet - give it a thickness
                bmesh.ops.solidify(bm, geom=bm.faces[:] + bm.edges[:] + bm.verts[:], thickness=voxel * SHEET_VOXELS)
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
