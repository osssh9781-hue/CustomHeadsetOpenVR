"""0.24.73 Edge Mesh (ZBrush shelf): decimate in steps -> hard edges -> quads on the flats -> live bevel (fitted per
edge) + subdivide + Fit to Original; Bevel Style Chamfer; no add-on undo steps in Sculpt Mode."""
import math

import numpy as np

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import edge_mesh as em, hard_edges as he, panel_capture as pc, undo_keep, zb_sculpt as zs
from mecha_lab import zb_ui as zu

mecha_lab.register()
fresh()
C = bpy.context
zb = C.scene.mch_zb


def boolean(ob, cutter):
    m = ob.modifiers.new('b', 'BOOLEAN')
    m.object = cutter
    m.operation = 'DIFFERENCE'
    m.solver = 'EXACT'
    with C.temp_override(object=ob, active_object=ob):
        bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(cutter)


def box(loc, size, name='c'):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = C.active_object
    o.scale = size
    o.name = name
    bpy.ops.object.transform_apply(scale=True)
    return o


def dense_part(name='Part'):
    """A hard-surface block with a step, a slot and a round hole, made dense (a clean high poly hand-off mesh)."""
    p = box((0, 0, 0), (1.0, 0.6, 0.4), name)
    boolean(p, box((0.55, 0, 0.35), (0.5, 0.7, 0.2)))
    boolean(p, box((-0.1, 0, 0.4), (0.08, 0.7, 0.15)))
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.18, depth=2, location=(-0.5, 0, 0),
                                        rotation=(math.pi / 2, 0, 0))
    boolean(p, C.active_object)
    m = p.modifiers.new('s', 'SUBSURF')
    m.subdivision_type = 'SIMPLE'
    m.levels = 4
    with C.temp_override(object=p, active_object=p):
        bpy.ops.object.modifier_apply(modifier='s')
    for o in C.selected_objects:
        o.select_set(False)
    p.select_set(True)
    C.view_layer.objects.active = p
    return p


def edge_attr(me, name):
    a = me.attributes.get(name)
    out = np.zeros(len(me.edges), np.float32)
    if a is not None:
        a.data.foreach_get('value', out)
    return out


def tris(me):
    me.calc_loop_triangles()
    return len(me.loop_triangles)


# --- pieces ---------------------------------------------------------------------------------------------------------
V = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0], [2, 1, 0], [1, 1.05, 0], [0, 1, 0], [1, 0.5, 0.0]], np.float64)
H = np.array([[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 0]])
p, o1, o2, turn, deg = em.line_points(V, H)
check('Edge lines: every point on a closed outline has two hard neighbours; a straight run turns ~0, a corner 90',
      len(p) == 6 and abs(math.degrees(turn[list(p).index(1)])) < 1.0
      and abs(math.degrees(turn[list(p).index(0)]) - 90.0) < 1.0, [round(math.degrees(t)) for t in turn])
S = em.straighten(V, H)
check('Straighten: the slightly bent point (1, 1.05) moves towards the line, corners stay put',
      abs(S[4, 1] - 1.0) < abs(V[4, 1] - 1.0) and np.allclose(S[[0, 2, 3, 5]], V[[0, 2, 3, 5]]), S[4].tolist())

part = dense_part()
me = part.data
V0 = np.array([v.co for v in me.vertices], np.float64)
me.calc_loop_triangles()
T0 = np.array([t.vertices for t in me.loop_triangles], np.int32)
w = em.turn_weights(V0, T0, math.radians(30))
check('Adaptive weights: corners / bending edge lines cost more to take away, flat points cost nothing extra',
      w.max() > 2.0 and np.median(w) == 1.0, (float(w.max()), float(np.median(w))))
Vp, Tp, _m, steps = em.progressive(V0, T0, 1500, math.radians(30))
check('Decimate in steps: down to the Detail triangles in several steps (fresh error every step)',
      abs(len(Tp) - 1500) <= 40 and steps >= 3, (len(Tp), steps))
Hp = em.hard_lines(Vp.astype(np.float64), Tp, math.radians(30))
check('... the edges come out: the step, the slot and the hole leave hard edge lines', len(Hp) > 60, len(Hp))

# --- Edge Mesh on the object ------------------------------------------------------------------------------------------
zb.em_detail = 1500
zb.he_width = 0.01
zb.he_segments = 2
zb.he_style = 'ROUND'
zb.he_subdiv = 0
zb.he_crease = True
dense_faces = len(me.polygons)
msg = em.build(C, part, zb)
me = part.data
src = he.source(part)
check('Edge Mesh: a light mesh (about Detail triangles) with its hard edges marked', 1300 <= tris(me) <= 1600
      and he.hard_flags(me).sum() > 50 and 'hard edges' in msg, (tris(me), msg))
check('... flats joined into quads (triangles stay where it is hard)',
      sum(len(f.vertices) == 4 for f in me.polygons) > 100, sum(len(f.vertices) == 4 for f in me.polygons))
check('... live Bevel + Subdivide (Subdivide set to 2, Crease off: the support bevel makes the edge) + Fit to Original',
      [m.name for m in part.modifiers] == [he.BEVEL, he.SUBSURF, he.FIT] and zb.he_subdiv == 2 and not zb.he_crease,
      [m.name for m in part.modifiers])
check('... the dense original is kept off-scene for Fit to Original: in no scene (never exported), kept by a fake user',
      src is not None and src.use_fake_user and src.name not in C.scene.objects and len(src.data.polygons) == dense_faces
      and part.modifiers[he.FIT].target == src, src and (src.use_fake_user, len(src.data.polygons)))
g = part.vertex_groups.get(he.FIT_GROUP)
check('... the fit point group holds the hard edges where they are (0) and fits the rest (1)', g is not None)
ev = part.evaluated_get(C.evaluated_depsgraph_get())
check('... the live result evaluates (subdivided client mesh)', len(ev.data.polygons) > 4 * len(me.polygons),
      len(ev.data.polygons))

# --- bevel fitted per edge, Clamp only where needed --------------------------------------------------------------
bev = part.modifiers[he.BEVEL]
wts = edge_attr(me, 'bevel_weight_edge')
hard = he.hard_flags(me)
check('Bevel weights: on the hard edges only, full Width where it fits, narrower only where it must be',
      (wts[~hard] == 0).all() and (wts[hard] > 0).all() and np.median(wts[hard]) >= 0.39, float(np.median(wts[hard])))
off = he._probe_off(part, bev)
check('... the test run without Clamp leaves no point off the surface (no bevel runs over a neighbour)',
      off is not None and len(off) == 0, None if off is None else len(off))
check('... so Clamp Overlap stays off (with Clamp one tight spot narrowed every bevel of the part)',
      not bev.use_clamp_overlap)

# --- again from the original, Chamfer ---------------------------------------------------------------------------------
zb.he_style = 'CHAMFER'
zb.em_detail = 1000
msg = em.build(C, part, zb)
check('Edge Mesh again: from the kept dense original (not the light result), the same original kept',
      he.source(part) == src and 900 <= tris(part.data) <= 1100, (tris(part.data), msg))
bev = part.modifiers[he.BEVEL]
pts = sorted((round(q.location[0], 2), round(q.location[1], 2)) for q in bev.custom_profile.points)
check('Bevel Style Chamfer: a straight cut with a support point near each side (custom profile, 3 segments)',
      bev.profile_type == 'CUSTOM' and bev.segments == 3 and pts == [(0.0, 1.0), (0.12, 0.88), (0.88, 0.12),
                                                                     (1.0, 0.0)], pts)
zb.he_style = 'ROUND'
check('... back to Round: the round profile again', bev.profile_type == 'SUPERELLIPSE' and bev.segments == 2)

# --- apply / clear ------------------------------------------------------------------------------------------------
n = he.apply_live(C, part, zb)
me = part.data
check('Apply: the client mesh - plain, no Sharp / custom normals, every face smooth', n >= 2
      and me.attributes.get('sharp_edge') is None and not me.has_custom_normals
      and all(f.use_smooth for f in me.polygons) and len(part.modifiers) == 0, n)
check('... the off-scene original is gone (nothing left to export or to keep in the file)',
      he.source(part) is None and not any(o.name.endswith('_EdgeSource') for o in bpy.data.objects))
part2 = dense_part('Part2')
em.build(C, part2, zb)
he.clear(part2)
check('Clear: marks, live modifiers and the off-scene original gone', he.source(part2) is None
      and not part2.modifiers and not any(o.name == 'Part2_EdgeSource' for o in bpy.data.objects))

# --- shelf ------------------------------------------------------------------------------------------------------------
node = pc.capture(zu.draw_tool_shelf, C)
acts = {x.opts.get('props', {}).get('action') for x in pc.walk(node) if x.kind == 'op'} - {None}
check('ZBrush shelf: Edge Mesh box (Edge Mesh, Half, Double) next to Hard Edges',
      {'EDGE_MESH', 'EM_HALF', 'EM_DOUBLE', 'HE_FIND'} <= acts, sorted(a for a in acts if a.startswith(('E', 'H'))))
zb.em_detail = 2000
zs.run(C, 'EM_HALF')
check('... Half / Double change Detail', zb.em_detail == 1000)
part3 = dense_part('Part3')
zs.on = lambda c: getattr(c, 'mode', '') == 'SCULPT'
bpy.ops.object.mode_set(mode='SCULPT')
r = bpy.ops.mch.zb_action(action='EDGE_MESH')
check('... Edge Mesh from the shelf in Sculpt Mode: done, back in Sculpt Mode', r == {'FINISHED'}
      and C.mode == 'SCULPT' and he.source(part3) is not None, (r, C.mode))

# --- undo steps in Sculpt Mode ------------------------------------------------------------------------------------------
check('No add-on undo step in Sculpt Mode (an empty sculpt step after another one broke Blender\'s undo)',
      undo_keep.push('test') is False)
bpy.ops.object.mode_set(mode='OBJECT')
check('... in Object Mode the step is pushed', undo_keep.push('test') is True)

summary()
