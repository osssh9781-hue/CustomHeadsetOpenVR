"""0.23.7 Through: an Armor / Cloth Plate lasso that goes through the mesh.

Drawn on the front, the outline also takes the back (and every layer in between):
the region is cut out of the target's own faces - every face whose screen
projection falls inside the outline, whichever way it faces - instead of the
first surface the view rays hit.  The region is then split into panels where it
turns away from the view (front / back - the silhouette) and where the surface
folds sharply (Crease angle), and every panel goes through the normal plate /
cloth pipeline, so a band drawn across an arm becomes a front and a back panel
meeting at the sides like the seams of a sleeve.

Pure bmesh / mathutils (tested headless).
"""
from __future__ import annotations

import math

import bmesh
from mathutils import Vector

from . import core_geometry as cg

MAX_FACES = 250000


def _flat_loops(groups):
    loops = []
    for outer, holes in groups:
        loops.append(list(outer))
        loops.extend(list(h) for h in holes)
    return loops


def _view_dir(projector, co):
    if getattr(projector, 'is_perspective', False):
        d = Vector(co) - Vector(projector.eye)
        if d.length > 1e-12:
            return d.normalized()
    return Vector(projector.view_dir).normalized()


def through_panels(bm_world, groups, projector, spacing_px=14.0, crease_deg=50.0, min_faces=4, split=True):
    """Cut the outline out of ``bm_world`` (a bmesh in world space - it is changed) through every layer.

    Returns a list of panels ``{'cos': [Vector], 'nrms': [Vector], 'tris': [(a, b, c)], 'front': bool}``
    in world space, largest first.  Raises ``cg.CutError`` when nothing is inside."""
    loops = _flat_loops(groups)
    xs = [p[0] for lp in loops for p in lp]
    ys = [p[1] for lp in loops for p in lp]
    if not xs:
        raise cg.CutError('Draw an outline first.')
    pad = spacing_px
    bx0, bx1, by0, by1 = min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad
    bm = bm_world
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    scr = {}

    def screen(v):
        s = scr.get(v)
        if s is None:
            p = projector.to_screen(v.co)
            s = scr[v] = (p if p is not None else (float('inf'), float('inf')))
        return s

    # 1. only faces whose screen box meets the outline box (a big face may cover the outline)
    drop = []
    for f in bm.faces:
        pts = [screen(v) for v in f.verts]
        if (max(p[0] for p in pts) < bx0 or min(p[0] for p in pts) > bx1 or
                max(p[1] for p in pts) < by0 or min(p[1] for p in pts) > by1):
            drop.append(f)
    if drop:
        bmesh.ops.delete(bm, geom=drop, context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
    if not bm.faces:
        raise cg.CutError('Nothing of the mesh is inside the outline.')
    # 2. resolution: pixels per metre from faces seen face-on, then split long edges
    ratios = []
    for e in bm.edges:
        a, b = e.verts
        wl = (a.co - b.co).length
        if wl < 1e-12:
            continue
        fn = e.link_faces[0].normal if e.link_faces else None
        if fn is not None and abs(fn.dot(_view_dir(projector, a.co))) < 0.6:
            continue
        sa, sb = screen(a), screen(b)
        if math.isinf(sa[0]) or math.isinf(sb[0]):
            continue
        ratios.append(math.hypot(sa[0] - sb[0], sa[1] - sb[1]) / wl)
    ppu = sorted(ratios)[len(ratios) // 2] if ratios else 100.0
    target = max(spacing_px / max(ppu, 1e-9), 1e-6)
    for _pass in range(6):
        long_ = [e for e in bm.edges if e.calc_length() > target * 1.4]
        if not long_ or len(bm.faces) > MAX_FACES:
            break
        bmesh.ops.subdivide_edges(bm, edges=long_, cuts=1, use_grid_fill=False)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
    scr.clear()
    # 3. inside test; points just outside move onto the outline (along their edge to an inside point)
    inside = {v: (not math.isinf(screen(v)[0]) and cg.point_in_loops(screen(v), loops)) for v in bm.verts}
    snapped = {}
    for v in bm.verts:
        if inside[v]:
            continue
        hits = []
        for e in v.link_edges:
            o = e.other_vert(v)
            if not inside[o]:
                continue
            lo, hi = 0.0, 1.0                    # 0 = inside point, 1 = this point
            for _i in range(14):
                mid = 0.5 * (lo + hi)
                p = projector.to_screen(o.co.lerp(v.co, mid))
                if p is not None and cg.point_in_loops(p, loops):
                    lo = mid
                else:
                    hi = mid
            hits.append(o.co.lerp(v.co, lo))
        if hits:
            snapped[v] = sum(hits, Vector()) / len(hits)
    for v, co in snapped.items():
        v.co = co
    keep = [f for f in bm.faces if all(inside[v] or v in snapped for v in f.verts) and
            any(inside[v] for v in f.verts)]
    keep_set = set(keep)
    gone = [f for f in bm.faces if f not in keep_set]
    if gone:
        bmesh.ops.delete(bm, geom=gone, context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.normal_update()
    faces = [f for f in bm.faces if f.calc_area() > 1e-14]
    if not faces:
        raise cg.CutError('Nothing of the mesh is inside the outline.')
    # 4. panels: split where the surface turns away from the view and at sharp creases
    front = {f: f.normal.dot(_view_dir(projector, f.calc_center_median())) < 0.0 for f in faces}
    cos_lim = math.cos(math.radians(crease_deg))
    if not split:                  # 0.24.20 Creature Plate: front and back stay one piece (no seams)
        front = {f: True for f in faces}
        cos_lim = -2.0
    fset = set(faces)
    seen, comps = set(), []
    for f0 in faces:
        if f0 in seen:
            continue
        comp, stack = [], [f0]
        seen.add(f0)
        while stack:
            f = stack.pop()
            comp.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g is f or g in seen or g not in fset:
                        continue
                    if front[g] != front[f] or f.normal.dot(g.normal) < cos_lim:
                        continue
                    seen.add(g)
                    stack.append(g)
        if len(comp) >= min_faces:
            comps.append(comp)
    panels = []
    for comp in comps:
        vmap, cos, acc, tris = {}, [], [], []
        for f in comp:
            idx = []
            for v in f.verts:
                if v not in vmap:
                    vmap[v] = len(cos)
                    cos.append(v.co.copy())
                    acc.append(Vector())
                acc[vmap[v]] += f.normal * f.calc_area()
                idx.append(vmap[v])
            tris.append(tuple(idx))
        nrms = [(n.normalized() if n.length > 1e-12 else Vector((0, 0, 1))) for n in acc]
        panels.append({'cos': cos, 'nrms': nrms, 'tris': tris, 'front': front[comp[0]],
                       'area': sum(f.calc_area() for f in comp)})
    if not panels:
        raise cg.CutError('Nothing of the mesh is inside the outline.')
    panels.sort(key=lambda p: -p['area'])
    return panels


def target_bmesh(context, target):
    """The evaluated target as a world-space bmesh (caller frees it)."""
    dg = context.evaluated_depsgraph_get()
    ev = target.evaluated_get(dg)
    me = ev.to_mesh()
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
    finally:
        ev.to_mesh_clear()
    bm.transform(target.matrix_world)
    bm.normal_update()
    return bm


def panels_for(context, target, groups, projector, spacing_px, crease_deg, split=True):
    bm = target_bmesh(context, target)
    try:
        return through_panels(bm, groups, projector, spacing_px, crease_deg, split=split)
    finally:
        bm.free()
