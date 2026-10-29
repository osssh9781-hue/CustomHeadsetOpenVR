"""0.24.84 Re-Fix: one button that makes a worked-over part clean again - DynaMesh at a resolution picked for it,
then a clean Decimate (or Quad Remesh) back to a light mesh - so a wide bevel / GN Edge / Hard Edges works on it
again.  The way the user works by hand (DynaMesh > Decimate > Quad Remesh) with the numbers chosen for them:

* live stack applied first (Box Hide, Armor Shell, Hard Edges bevel ... become real faces), small holes shut
* DynaMesh: enough points to carry the part's detail (``points_for``: 8 x the target faces, 120k .. 500k; a Quad
  Remesh finish stops at 250k - the quad solver is the slow part) - a self-crossing sculpt comes out as one solid
* Decimate (even, the C engine) or Quad Remesh (Mostly Quads, the shelf's hard-edge angle) to ``faces`` polygons;
  Faces 0 = Auto: what the part has now, 2,000 .. 40,000
* the report says faces before > after, open edges and self-crossings before > after

Mesh Tools (sidebar), the ZBrush N panel (Geometry) and the ZBrush action ``REFIX`` (hotkey-assignable).
"""
from __future__ import annotations

import math

import bpy

FACES_MIN, FACES_MAX = 2_000, 40_000
POINTS_MIN, POINTS_MAX, POINTS_MAX_QUAD = 120_000, 500_000, 250_000
POINTS_PER_FACE = 8
CROSS_LIMIT = 300_000
FINER_TRIES = 2                 # Decimate finish: the faces doubled this many times while the result crosses itself


def auto_faces(ob):
    """Faces for Auto: what the part shows now (modifiers included), 2,000 .. 40,000."""
    try:
        dg = bpy.context.evaluated_depsgraph_get()
        n = len(ob.evaluated_get(dg).data.polygons)
    except (AttributeError, RuntimeError, ReferenceError):
        n = len(ob.data.polygons)
    return int(min(FACES_MAX, max(FACES_MIN, n)))


def points_for(faces, finish):
    """DynaMesh points for a ``faces`` result: 8 per face, 120k .. 500k (250k before a Quad Remesh)."""
    top = POINTS_MAX_QUAD if finish == 'QUAD' else POINTS_MAX
    return int(min(top, max(POINTS_MIN, faces * POINTS_PER_FACE)))


def _bake(context, ob):
    """Every live step into the mesh: Armor Shell, the live stack (Box Hide, Hard Edges bevel, Mirror ...), a live
    primitive.  Returns how many modifiers went in."""
    from . import armor_shell, core_geometry as cg, live_stack
    try:
        armor_shell.bake_live(context, ob)
    except (RuntimeError, AttributeError, ReferenceError):
        pass
    cg.ensure_real_mesh(context, ob)
    n = len(ob.modifiers)
    if n:
        live_stack.apply_all(context, ob)
    return n


def run(context, ob, zb):
    """Re-Fix ``ob`` (Object Mode) with the shelf settings ``zb``.  Returns a report; raises RuntimeError when it
    can't."""
    from . import core_geometry as cg, fast_decimate as fd, mesh_fix, quad_field as qf, voxel_for_points, zb_sculpt as zs
    if ob.type != 'MESH' or ob.data is None:
        raise RuntimeError('not a mesh')
    if zs.multires(ob) is not None:
        raise RuntimeError('has subdivision levels (Multires) - Del Higher / Del Lower first')
    if ob.data.shape_keys is not None:
        raise RuntimeError('remove the shape keys first')
    finish = getattr(zb, 'refix_finish', 'DECIMATE')
    faces = int(getattr(zb, 'refix_faces', 0)) or auto_faces(ob)
    me = ob.data
    faces0, open0 = len(me.polygons), cg.non_manifold_edge_count(me)
    cross0 = cg.self_overlaps(me, CROSS_LIMIT)
    baked = _bake(context, ob)
    me = ob.data
    if not len(me.polygons):
        raise RuntimeError('no faces')
    mesh_fix.fix_mesh(me, fill='SMALL')                       # (a closed input for the voxel remesh)
    points = points_for(faces, finish)
    v = voxel_for_points(context, ob, points)
    if v <= 0.0:
        raise RuntimeError('no surface')
    me.remesh_voxel_size = v
    me.use_remesh_fix_poles = False             # (Fix Poles left 4 open edges, Preserve Volume made the two walls
    me.use_remesh_preserve_volume = False       #  of a pinched fold cross each other: 1,115 crossings - plain is clean)
    with context.temp_override(object=ob, active_object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
        bpy.ops.object.voxel_remesh()
    me = ob.data
    dyna = len(me.vertices)
    if not len(me.polygons):
        raise RuntimeError('DynaMesh gave nothing (the part is thinner than its voxels everywhere)')
    raised = ''
    if finish == 'QUAD':
        note = qf.remesh_object(ob, faces, all_quads=False, crease_deg=math.degrees(getattr(zb, 'qr_angle', math.radians(30))))
        how = 'Quad Remesh'
    else:
        # a wall thinner than the triangles asked for comes back crossing itself (its two sides cut through each
        # other): the Decimate is run again from the DynaMesh with twice the faces, up to FINER_TRIES times
        dyna_me = me.copy()
        try:
            want = faces
            for _try in range(FINER_TRIES + 1):
                me.calc_loop_triangles()
                keep = 100.0 * want / max(1, len(me.loop_triangles))
                if fd.available():
                    note = fd.decimate_object(ob, min(100.0, keep), even=True, quads=bool(getattr(zb, 'dec_quads', False)))
                else:
                    note = fd.blender_decimate(context, ob, min(100.0, keep))
                if cg.self_overlaps(ob.data, CROSS_LIMIT) <= 0 or want * 2 > len(dyna_me.polygons) or _try == FINER_TRIES:
                    break
                fd.swap_mesh(ob, dyna_me.copy())        # back to the DynaMesh, finer
                me = ob.data
                want *= 2
                raised = f' (faces raised to {want:,}: a wall thinner than the triangles)'
        finally:
            if dyna_me.users == 0:
                bpy.data.meshes.remove(dyna_me)
        how = 'Decimate'
    me = ob.data
    if hasattr(cg, 'tidy_result'):
        cg.tidy_result(me, shards=True, slivers=False)
    for _again in range(2):                                   # (sides a Quad Remesh left open: the DynaMesh was
        if not cg.non_manifold_edge_count(me):                #  closed, so every hole here is a new one - shut all,
            break                                             #  twice when the first pass leaves a doubled edge)
        mesh_fix.fix_mesh(me, all_holes=True)
        if hasattr(cg, 'tidy_result'):
            cg.tidy_result(me, shards=False, slivers=False)
    open1, cross1 = cg.non_manifold_edge_count(me), cg.self_overlaps(me, CROSS_LIMIT)
    out = (f'Re-Fix ({how}): {faces0:,} > {len(me.polygons):,} faces (DynaMesh {dyna:,} points, asked {faces:,}{raised}) | '
           f'open edges {open0} > {open1}')
    if cross0 > 0 or cross1 > 0:
        out += f' | self-crossings {max(cross0, 0):,} > {max(cross1, 0):,}'
    if baked:
        out += f' | {baked} live step(s) applied first'
    low = str(note).lower()
    if 'kept as' in low or 'nothing came back' in low or 'could not' in low:
        out += ' | WARNING: ' + str(note)[:120]
    return out


def draw_row(layout, zb):
    """The Re-Fix row: button, finish (Decimate / Quad Remesh), Faces (0 = Auto)."""
    col = layout.column(align=True)
    r = col.row(align=True)
    r.operator('mch.mesh_tool', text='Re-Fix (DynaMesh > clean mesh)', icon='FILE_REFRESH').action = 'REFIX'
    r = col.row(align=True)
    r.prop(zb, 'refix_finish', expand=True)
    r.prop(zb, 'refix_faces', text='Faces')
