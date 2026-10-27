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
    me.update()
    ob[KEY] = 1
    return n, faces0, len(me.polygons)


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


def marks(me, st):
    """Crease and bevel weight from the marked (sharp) edges and the shelf settings (works in any mode)."""
    sharp = _edge_bool(me, 'sharp_edge')
    conv = _edge_bool(me, CONVEX)
    _set_edge_float(me, 'crease_edge', sharp * (1.0 if st.he_crease else 0.0))
    _set_edge_float(me, 'bevel_weight_edge', (sharp & (conv | (not st.he_outer))).astype(np.float32))
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


def apply_live(context, ob):
    """Bake the live modifiers into the mesh (Object Mode).  Returns how many."""
    n = 0
    with context.temp_override(object=ob, active_object=ob):
        for name in LIVE:
            if ob.modifiers.get(name) is not None:
                bpy.ops.object.modifier_apply(modifier=name)
                n += 1
    return n


def clear(ob):
    """The hard-edge marks and the live modifiers off ``ob``."""
    for name in LIVE:
        m = ob.modifiers.get(name)
        if m is not None:
            ob.modifiers.remove(m)
    me = ob.data
    for name in ('sharp_edge', 'crease_edge', 'bevel_weight_edge', CONVEX):
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
