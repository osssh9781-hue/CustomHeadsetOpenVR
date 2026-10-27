"""0.24.70 Hard Edges: use the clean edges a decimated hard-surface part keeps (ZBrush shelf: Decimation).

Find Edges marks every edge sharper than ``Angle`` (and open borders): Sharp, a Crease (subdivision keeps it) and a
Bevel Weight; Merge Flats first joins the near-flat triangles between them into big faces (the hard edges stay), so
the bevel and the subdivision have clean faces to work on.  Then, live and adjustable at any time:

* Bevel - on the marked edges (Outer Only: convex edges, inside corners stay sharp), Width / Segments (1 = chamfer)
* Subdivide - Catmull-Clark levels; the creased edges stay sharp, the flat parts get more faces
* Weighted Normals - flat faces shade flat next to the bevels

Quad Remesh (the Mecha Quad Remesh, Patch or Flow) keeps the marked edges as quad lines.  Apply bakes the live
modifiers into the mesh.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty

BEVEL = 'MCH_HE_Bevel'
SUBSURF = 'MCH_HE_Subdivide'
NORMALS = 'MCH_HE_Normals'
KEY = 'mch_hard_edges'          # object: Find Edges ran on it (the live parts belong to it)


def _live_update(self, context):
    ob = context.active_object
    if ob is not None and ob.type == 'MESH' and KEY in ob:
        set_live(ob, self)


class MCH_PG_HardEdges(bpy.types.PropertyGroup):
    angle: FloatProperty(name='Angle', default=math.radians(30.0), min=math.radians(1.0), max=math.radians(150.0),
                         subtype='ANGLE', description='Edges sharper than this are hard edges')
    merge_flats: BoolProperty(name='Merge Flats', default=True,
                              description='Join the near-flat triangles between the hard edges into big faces first '
                                          '(cleaner bevels and subdivision; the hard edges stay)')
    flat_angle: FloatProperty(name='Flat', default=math.radians(1.0), min=0.0, max=math.radians(10.0),
                              subtype='ANGLE', description='Merge Flats: faces closer than this to flat are joined')
    crease: BoolProperty(name='Crease', default=True, description='Give the hard edges a full crease (subdivision '
                                                                  'keeps them sharp)')
    outer_only: BoolProperty(name='Outer Only', default=False, update=_live_update,
                             description='Bevel only the convex (outside) hard edges; inside corners stay sharp')
    bevel: BoolProperty(name='Bevel', default=True, update=_live_update, description='A live bevel on the hard edges')
    width: FloatProperty(name='Width', default=0.01, min=0.0, soft_max=1.0, precision=4, unit='LENGTH',
                         update=_live_update, description='Bevel width')
    segments: IntProperty(name='Segments', default=2, min=1, max=12, update=_live_update,
                          description='Bevel segments (1 = chamfer)')
    subdivide: IntProperty(name='Subdivide', default=0, min=0, max=4, update=_live_update,
                           description='Catmull-Clark levels; creased edges stay sharp, flat parts get more faces')
    normals: BoolProperty(name='Weighted Normals', default=True, update=_live_update,
                          description='Flat faces shade flat next to the bevels')


def _size(me):
    if not me.vertices:
        return 1.0
    import numpy as np
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    return max(float((co.max(0) - co.min(0)).max()), 1e-9)


def _convex(e):
    f1, f2 = e.link_faces[:2]
    return (f2.calc_center_median() - f1.calc_center_median()).dot(f1.normal) < 0.0


def find(ob, st):
    """Mark the hard edges of mesh object ``ob`` (Object Mode).  Returns (hard edges, faces before, faces after)."""
    me = ob.data
    faces0 = len(me.polygons)
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=_size(me) * 1e-6)
        for e in bm.edges:
            e.smooth = not (not e.is_manifold or e.calc_face_angle(0.0) > st.angle)
        if st.merge_flats and st.flat_angle > 0.0:
            bmesh.ops.dissolve_limit(bm, angle_limit=st.flat_angle, use_dissolve_boundaries=False,
                                     verts=list(bm.verts), edges=list(bm.edges), delimit={'SHARP'})
        crease = bm.edges.layers.float.get('crease_edge') or bm.edges.layers.float.new('crease_edge')
        weight = bm.edges.layers.float.get('bevel_weight_edge') or bm.edges.layers.float.new('bevel_weight_edge')
        hard = 0
        for e in bm.edges:
            h = not e.smooth
            hard += h
            e[crease] = 1.0 if h and st.crease else 0.0
            e[weight] = 1.0 if h else 0.0
        for f in bm.faces:
            f.smooth = True
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()
    ob[KEY] = 1
    return hard, faces0, len(me.polygons)


def bevel_weights(ob, outer_only):
    """Bevel weight on the marked (sharp) edges - only the convex ones with ``outer_only``."""
    me = ob.data
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        weight = bm.edges.layers.float.get('bevel_weight_edge') or bm.edges.layers.float.new('bevel_weight_edge')
        for e in bm.edges:
            h = not e.smooth
            e[weight] = 1.0 if h and (not outer_only or not e.is_manifold or len(e.link_faces) != 2
                                      or _convex(e)) else 0.0
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()


def set_live(ob, st):
    """Add / update / remove the live Bevel, Subdivide and Weighted Normals of ``ob`` (in that order)."""
    mods = ob.modifiers
    bev = mods.get(BEVEL)
    if st.bevel:
        if bev is None:
            bev = mods.new(BEVEL, 'BEVEL')
        bev.limit_method = 'WEIGHT'
        bev.width = st.width
        bev.segments = st.segments
        bev.profile = 0.5
        bev.use_clamp_overlap = True
        bev.harden_normals = st.normals
        bev.miter_outer = 'MITER_ARC'
        try:
            bev.affect = 'EDGES'
        except (AttributeError, TypeError):
            pass
    elif bev is not None:
        mods.remove(bev)
    if ob.mode != 'EDIT':
        bevel_weights(ob, st.outer_only)
    sub = mods.get(SUBSURF)
    if st.subdivide > 0:
        if sub is None:
            sub = mods.new(SUBSURF, 'SUBSURF')
        sub.levels = sub.render_levels = st.subdivide
        if hasattr(sub, 'use_creases'):
            sub.use_creases = True
        sub.boundary_smooth = 'PRESERVE_CORNERS'
    elif sub is not None:
        mods.remove(sub)
    nrm = mods.get(NORMALS)
    if st.normals:
        if nrm is None:
            nrm = mods.new(NORMALS, 'WEIGHTED_NORMAL')
        nrm.keep_sharp = True
        nrm.mode = 'FACE_AREA'
    elif nrm is not None:
        mods.remove(nrm)
    order = [m for m in (mods.get(BEVEL), mods.get(SUBSURF), mods.get(NORMALS)) if m is not None]
    for i, m in enumerate(order):                  # ours at the end, in this order
        target = len(mods) - len(order) + i
        if list(mods).index(m) != target:
            with bpy.context.temp_override(object=ob, active_object=ob):
                bpy.ops.object.modifier_move_to_index(modifier=m.name, index=target)


def apply_live(context, ob):
    """Bake our live modifiers into the mesh (Object Mode).  Returns how many."""
    n = 0
    with context.temp_override(object=ob, active_object=ob):
        for name in (BEVEL, SUBSURF, NORMALS):
            if ob.modifiers.get(name) is not None:
                bpy.ops.object.modifier_apply(modifier=name)
                n += 1
    return n


def quad_remesh(context, ob):
    """The Mecha Quad Remesh of ``ob`` keeping the marked edges (a new SubTool; the original is kept, hidden)."""
    from . import quad_remesh as qr
    st = context.scene.mch_quadremesh
    keep = st.keep_marked
    st.keep_marked = True
    try:
        new, kept, miss = qr.make(context, ob, st)
    finally:
        st.keep_marked = keep
    return new, kept, miss


def register():
    bpy.utils.register_class(MCH_PG_HardEdges)
    bpy.types.Scene.mch_hardedge = bpy.props.PointerProperty(type=MCH_PG_HardEdges)


def unregister():
    if hasattr(bpy.types.Scene, 'mch_hardedge'):
        del bpy.types.Scene.mch_hardedge
    try:
        bpy.utils.unregister_class(MCH_PG_HardEdges)
    except RuntimeError:
        pass
