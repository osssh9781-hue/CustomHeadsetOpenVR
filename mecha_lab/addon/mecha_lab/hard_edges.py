"""0.24.72 Hard Edges (ZBrush shelf): find the hard edges of a decimated / quad-remeshed hard-surface part, crease them
and put a live, adjustable bevel on them.

Find Edges marks every edge whose faces meet at more than Angle (and open borders) as Sharp, gives it a full Crease
and a Bevel Weight; lone specks (a single short edge on its own) are left out.  Merge Flats first joins the near-flat
triangles between the hard edges into big faces (triangle meshes only - Decimate's output; quads from Quad Remesh
stay quads), so the bevel and the subdivision get clean faces.  Then, live and adjustable at any time (settings on
the ZBrush shelf, ``scene.mch_zb.he_*``):

* Bevel - on the marked edges (Outer Only: the convex ones, inside corners stay sharp), Width / Segments
  (1 = a chamfer) / Shape
* Subdivide - Catmull-Clark levels; creased edges stay sharp, the flat parts get more faces
* Weighted Normals - flat faces shade flat next to the bevels

Apply bakes the live modifiers into the mesh; Clear takes the marks and the live modifiers off.

0.24.73 Client Look (on by default): the mesh itself carries the hard look - no Sharp marks for Blender's display
and no custom normals (Weighted Normals off), so what Blender shows is what Maya / Max / ZBrush show.  The hard
edges are kept in an internal attribute; the support bevel + creased subdivision make them crisp with plain smooth
shading.  Apply then leaves a plain mesh: modifiers baked, no Sharp / Crease / Bevel Weight / custom normals,
every face smooth.
"""
from __future__ import annotations

import math

import numpy as np

import bmesh
import bpy

BEVEL = 'MCH_HE_Bevel'
SUBSURF = 'MCH_HE_Subdivide'
NORMALS = 'MCH_HE_Normals'
LIVE = (BEVEL, SUBSURF, NORMALS)
KEY = 'mch_hard_edges'          # object: Find Edges ran on it (the live modifiers follow the shelf settings)
CONVEX = '.mch_he_convex'       # edge: the faces meet outward (Outer Only)
HARD = '.mch_he_hard'           # edge: a hard edge (kept here: with Client Look nothing is marked Sharp)
FLAT = math.radians(1.0)        # Merge Flats: faces closer than this to flat are joined
SPECK = 0.02                    # a hard edge on its own shorter than this x the part size is not a hard edge
MAX_POLYS = 300000              # beyond this: Decimate / Quad Remesh first (a bevel on a DynaMesh would take ages)


def _size(me):
    if not me.vertices:
        return 1.0
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    return max(float((co.max(0) - co.min(0)).max()), 1e-9)


def _convex(e):
    if len(e.link_faces) != 2:
        return True
    f1, f2 = e.link_faces
    return (f2.calc_center_median() - f1.calc_center_median()).dot(f1.normal) < 0.0


def _drop_specks(hard, size):
    """Hard edges minus the lone ones: a single short edge with no other hard edge at either end."""
    deg = {}
    for e in hard:
        for v in e.verts:
            deg[v.index] = deg.get(v.index, 0) + 1
    return [e for e in hard if not (deg[e.verts[0].index] == 1 and deg[e.verts[1].index] == 1
                                    and e.calc_length() < SPECK * size)]


def find(ob, st):
    """Mark the hard edges of mesh object ``ob`` (Object Mode).  Returns (hard edges, polygons before, after)."""
    me = ob.data
    faces0 = len(me.polygons)
    size = _size(me)
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        hard = [e for e in bm.edges if len(e.link_faces) != 2 or e.calc_face_angle(0.0) > st.he_angle]
        hard = _drop_specks(hard, size)
        for e in bm.edges:
            e.smooth = True
        for e in hard:
            e.smooth = False
        tris = sum(len(f.verts) == 3 for f in bm.faces)
        if st.he_merge and tris > 0.5 * len(bm.faces):
            bmesh.ops.dissolve_limit(bm, angle_limit=FLAT, use_dissolve_boundaries=False, verts=bm.verts[:],
                                     edges=bm.edges[:], delimit={'SHARP', 'MATERIAL'})
        crease = bm.edges.layers.float.get('crease_edge') or bm.edges.layers.float.new('crease_edge')
        weight = bm.edges.layers.float.get('bevel_weight_edge') or bm.edges.layers.float.new('bevel_weight_edge')
        conv = bm.edges.layers.bool.get(CONVEX) or bm.edges.layers.bool.new(CONVEX)
        n = 0
        for e in bm.edges:
            h = not e.smooth
            c = _convex(e) if h else False
            n += h
            e[conv] = c
            e[crease] = 1.0 if h and st.he_crease else 0.0
            e[weight] = 1.0 if h and (c or not st.he_outer) else 0.0
        for f in bm.faces:
            f.smooth = True
        bm.to_mesh(me)
    finally:
        bm.free()
    hard = _edge_bool(me, 'sharp_edge')
    a = me.attributes.get(HARD) or me.attributes.new(HARD, 'BOOLEAN', 'EDGE')
    a.data.foreach_set('value', hard)
    marks(me, st)
    ob[KEY] = 1
    return n, faces0, len(me.polygons)


def _edge_faces(me):
    """For every edge: its first two faces (-1 when missing) and how many faces it has."""
    ne = len(me.edges)
    le = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get('edge_index', le)
    ls = np.empty(len(me.polygons), np.int64)
    me.polygons.foreach_get('loop_total', ls)
    lp = np.repeat(np.arange(len(me.polygons)), ls)
    o = np.argsort(le, kind='stable')
    le, lp = le[o], lp[o]
    cnt = np.bincount(le, minlength=ne)
    start = np.concatenate([[0], np.cumsum(cnt)[:-1]])
    f1 = np.where(cnt > 0, lp[np.minimum(start, len(lp) - 1)], -1) if len(lp) else np.full(ne, -1)
    f2 = np.where(cnt > 1, lp[np.minimum(start + 1, len(lp) - 1)], -1) if len(lp) else np.full(ne, -1)
    return f1, f2, cnt


def convex_edges(me):
    """Edges whose two faces meet outward (open / non-manifold edges count as outward)."""
    f1, f2, cnt = _edge_faces(me)
    cen = np.empty(len(me.polygons) * 3)
    me.polygons.foreach_get('center', cen)
    nrm = np.empty(len(me.polygons) * 3)
    me.polygons.foreach_get('normal', nrm)
    cen, nrm = cen.reshape(-1, 3), nrm.reshape(-1, 3)
    out = np.ones(len(me.edges), bool)
    two = cnt == 2
    a, b = f1[two], f2[two]
    out[two] = ((cen[b] - cen[a]) * nrm[a]).sum(1) < 0.0
    return out


def mark_pairs(me, pairs, crease=True, sharp=False):
    """Mark the edges joining point ``pairs`` (k, 2) hard: a full Crease, a Bevel Weight (Sharp too with ``sharp`` -
    off for Client Look); faces smooth."""
    ev = np.empty(len(me.edges) * 2, np.int64)
    me.edges.foreach_get('vertices', ev)
    ev = ev.reshape(-1, 2)
    n = max(len(me.vertices), 1)
    key = ev.min(1) * n + ev.max(1)
    pairs = np.asarray(pairs, np.int64).reshape(-1, 2)
    pk = pairs.min(1) * n + pairs.max(1) if len(pairs) else np.zeros(0, np.int64)
    hard = np.isin(key, pk)
    a = me.attributes.get(HARD) or me.attributes.new(HARD, 'BOOLEAN', 'EDGE')
    a.data.foreach_set('value', hard)
    a = me.attributes.get('sharp_edge') or me.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE')
    a.data.foreach_set('value', hard & sharp)
    conv = me.attributes.get(CONVEX) or me.attributes.new(CONVEX, 'BOOLEAN', 'EDGE')
    conv.data.foreach_set('value', hard & convex_edges(me))
    _set_edge_float(me, 'crease_edge', hard * (1.0 if crease else 0.0))
    _set_edge_float(me, 'bevel_weight_edge', hard.astype(np.float32))
    sm = np.ones(len(me.polygons), bool)
    me.polygons.foreach_set('use_smooth', sm)
    me.update()
    return int(hard.sum())


def _edge_bool(me, name):
    a = me.attributes.get(name)
    out = np.zeros(len(me.edges), bool)
    if a is not None and a.domain == 'EDGE':
        a.data.foreach_get('value', out)
    return out


def _set_edge_float(me, name, vals):
    a = me.attributes.get(name)
    if a is None or a.domain != 'EDGE' or a.data_type != 'FLOAT':
        if a is not None:
            me.attributes.remove(a)
        a = me.attributes.new(name, 'FLOAT', 'EDGE')
    a.data.foreach_set('value', vals.astype(np.float32))


def hard_flags(me):
    """The hard edges Find Edges / Quad Remesh found (older files: the Sharp marks)."""
    return _edge_bool(me, HARD if me.attributes.get(HARD) is not None else 'sharp_edge')


def marks(me, st):
    """Crease, bevel weight and (no Client Look) Sharp from the hard edges and the shelf settings (any mode)."""
    hard = hard_flags(me)
    conv = _edge_bool(me, CONVEX)
    _set_edge_float(me, 'crease_edge', hard * (1.0 if st.he_crease else 0.0))
    _set_edge_float(me, 'bevel_weight_edge', (hard & (conv | (not st.he_outer))).astype(np.float32))
    a = me.attributes.get('sharp_edge')
    if st.he_client:
        if a is not None:
            me.attributes.remove(a)
    else:
        if a is None:
            a = me.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE')
        a.data.foreach_set('value', hard)
    me.update()


def set_live(ob, st):
    """Add / update / remove the live Bevel, Subdivide and Weighted Normals of ``ob`` (in that order, last)."""
    mods = ob.modifiers
    marks(ob.data, st)
    bev = mods.get(BEVEL)
    if st.he_bevel:
        if bev is None:
            bev = mods.new(BEVEL, 'BEVEL')
        bev.affect = 'EDGES'
        bev.limit_method = 'WEIGHT'
        bev.edge_weight = 'bevel_weight_edge'
        bev.width = st.he_width
        bev.segments = st.he_segments
        bev.profile = st.he_profile
        bev.use_clamp_overlap = True
        bev.harden_normals = st.he_normals
    elif bev is not None:
        mods.remove(bev)
    sub = mods.get(SUBSURF)
    if st.he_subdiv > 0:
        if sub is None:
            sub = mods.new(SUBSURF, 'SUBSURF')
        sub.levels = sub.render_levels = st.he_subdiv
        sub.use_creases = True
        sub.boundary_smooth = 'PRESERVE_CORNERS'
    elif sub is not None:
        mods.remove(sub)
    nrm = mods.get(NORMALS)
    if st.he_normals:
        if nrm is None:
            nrm = mods.new(NORMALS, 'WEIGHTED_NORMAL')
        nrm.keep_sharp = True
        nrm.mode = 'FACE_AREA'
    elif nrm is not None:
        mods.remove(nrm)
    ours = [m for m in (mods.get(n) for n in LIVE) if m is not None]
    for i, m in enumerate(ours):                     # ours at the end, in this order
        target = len(mods) - len(ours) + i
        k = list(mods).index(m)
        if k != target:
            mods.move(k, target)


def plain_mesh(context, ob):
    """Client Look: no Sharp / Crease / Bevel Weight / custom normals, every face smooth - the mesh alone gives
    the look (the same in Maya / Max / ZBrush)."""
    me = ob.data
    for name in ('sharp_edge', 'crease_edge', 'bevel_weight_edge', HARD, CONVEX, 'custom_normal'):
        a = me.attributes.get(name)
        if a is not None:
            me.attributes.remove(a)
    if getattr(me, 'has_custom_normals', False):
        try:
            with context.temp_override(object=ob, active_object=ob):
                bpy.ops.mesh.customdata_custom_splitnormals_clear()
        except RuntimeError:
            pass
    me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), bool))
    me.update()


def apply_live(context, ob, st=None):
    """Bake the live modifiers into the mesh (Object Mode); with Client Look the result is a plain mesh.  Returns how
    many modifiers."""
    n = 0
    with context.temp_override(object=ob, active_object=ob):
        for name in LIVE:
            if ob.modifiers.get(name) is not None:
                bpy.ops.object.modifier_apply(modifier=name)
                n += 1
    if st is None or st.he_client:
        plain_mesh(context, ob)
    return n


def clear(ob):
    """The hard-edge marks and the live modifiers off ``ob``."""
    for name in LIVE:
        m = ob.modifiers.get(name)
        if m is not None:
            ob.modifiers.remove(m)
    me = ob.data
    for name in ('sharp_edge', 'crease_edge', 'bevel_weight_edge', CONVEX, HARD):
        a = me.attributes.get(name)
        if a is not None:
            me.attributes.remove(a)
    me.update()
    ob.pop(KEY, None)


def live_update(st, context):
    """A Hard Edges setting changed on the shelf: the active SubTool's live modifiers follow."""
    ob = context.active_object
    if ob is not None and ob.type == 'MESH' and KEY in ob:
        set_live(ob, st)
