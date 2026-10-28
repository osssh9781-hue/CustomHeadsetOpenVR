"""0.24.53 speed and bug fixes: GN Edge band self-union + Manifold difference (an open part / a bad result falls
back to the old all-Exact way) and even width at corners; Path Move Stretch in one pass (no point explosion, one
remembered Path Move); a live Ramp keeps its layout (another deep side does not lay it out again) and no longer
throws away edits made after it; Quad Remesh: live Bevel on the kept hard edges (Outer / All)."""
import json
import math

from _harness import bpy, check, fresh, non_manifold, summary
import bmesh
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import (base_mesh as bm_, concept_move as cm, core_geometry as cg, cut_engine as ce,
                       quad_remesh as qr, ramp_edit as re_, rim_sweep as rs, surface_draw as sd)

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
S.mch_settings.auto_apply = True


def block(name, cuts=6, loc=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=loc)
    o = C.active_object
    o.name = name
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=cuts)
    bpy.ops.object.mode_set(mode='OBJECT')
    return o


def top_at(x, y):
    C.view_layer.update()
    hit, loc, _n, _i, ob, _m = S.ray_cast(C.evaluated_depsgraph_get(), Vector((x, y, 5)), Vector((0, 0, -1)))
    return round(loc.z, 4) if hit else None


# --- GN Edge --------------------------------------------------------------------------------------------------
fast = rs.ensure_group(4, True)
slow = rs.ensure_group(4, False)
kinds = lambda ng: sorted((n.operation, n.solver) for n in ng.nodes if n.bl_idname == 'GeometryNodeMeshBoolean')
check('GN Edge group: the band joined with itself (Exact) then taken away with Manifold; the old one all Exact',
      kinds(fast) == [('DIFFERENCE', 'MANIFOLD'), ('UNION', 'EXACT')] and kinds(slow) == [('DIFFERENCE', 'EXACT')])
r2 = rs.miter(Vector((1, 0, 0)) + Vector((0, 1, 0)), 2)
check('Corner width: two edges at 90 degrees go sqrt(2) along the middle (was 1: 71 % at corners), capped',
      abs(r2.length - math.sqrt(2)) < 1e-6 and abs(rs.miter(Vector((1, 0, 0)) + Vector((-0.999, 0.04, 0)), 2).length
                                                    - 3.0) < 1e-6 and rs.miter(Vector((0, 0, 2)), 1).length == 1.0)
used = []
real = rs._sweep
rs._sweep = lambda me, n, fast: used.append(fast) or real(me, n, fast)
cut = S.mch_cut
cut.depth_mode, cut.depth = 'SURFACE', 0.4
W = 0.08
SQ = [(440, 440), (440, 560), (560, 560), (560, 440)]
t = block('Dense', cuts=12)
cut.gn_finish, cut.gn_width, cut.gn_segments = 'CHAMFER', W, 4
msg = ce.perform_closed(C, 'CUT', [t], [SQ], TOP, False)
check('Cut + GN Chamfer on a closed part: the fast way, closed result (0.24.68: the band is looked at first - a '
      'square pocket\'s band crosses itself at the corners: self-union + Manifold)', used == ['band', True] and 'GN Chamfer' in msg
      and non_manifold(t) == 0, (used, msg))
corner = top_at(0.6 + W / 2 * 0.7, 0.6 + W / 2 * 0.7)
side = top_at(0.6 + W / 2, 0.0)
check('... the chamfer is as wide at the corner as along the side', side is not None and corner is not None
      and abs(side - (1 - W / 2)) < 0.012 and corner < 1.0 - W * 0.25, (side, corner))
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
used.clear()
bpy.ops.mesh.primitive_grid_add(x_subdivisions=16, y_subdivisions=16, size=2.0)
sheet = C.active_object
me = sheet.data
check('An open part never takes the fast way (Manifold needs a closed solid)',
      cg.non_manifold_edge_count(me) > 0 and rs._clean(me, me) is False)
rs._sweep = real

# --- Path Move Stretch ------------------------------------------------------------------------------------------
pl = block('Plate', cuts=20)
n0 = len(pl.data.vertices)
path = [(1.0 + 0.1 * i, 0.0, 0.3 * math.sin(i / 3)) for i in range(12)]
res = bpy.ops.mch.concept_path('EXEC_DEFAULT', method='STRETCH', space='WORLD', objects=json.dumps(['Plate']),
                               path=json.dumps([list(p) for p in path]), radius=0.25, hardness=0.9, mirror=False,
                               generate_mesh=True, auto_apply=False)
n1 = len(pl.data.vertices)
rec = cm.recorded_moves(pl)
check('Stretch along a path: one pass - the points grow a little, not about 1.5x per step; closed',
      res == {'FINISHED'} and n0 < n1 < 3 * n0 and non_manifold(pl) == 0, (n0, n1))
check('... remembered as one Path Move (Undo Last takes the whole path)', len(rec) == 1 and rec[0]['kind'] == 'path'
      and len(rec[0]['moves']) >= 2)
far = max(v.co.x for v in pl.data.vertices)
check('... the part follows the path', far > 1.8, far)
cm.drop_base(pl)

# --- Ramp ------------------------------------------------------------------------------------------------------
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
p = bm_.scene_defaults(C)
p.sketch, p.profile, p.alt_mode, p.carve_depth, p.ramp_length, p.ramp_soft = False, 'FLAT', 'RAMP', 0.2, 1.0, 0.5
bpy.ops.mesh.primitive_cube_add(size=2.0)
cube = C.active_object
laid = []
real_layout = sd._carve_layout
sd._carve_layout = lambda *a, **k: laid.append(1) or real_layout(*a, **k)
from mecha_lab import facet_carve as fc_       # 0.24.76 a flat top gets the facet carve (no layout at all): the
fc_.ENABLED = False                            # layout cache is the old carve's (still the fallback) - tested on it
bm_.perform_base(C, [SQ], TOP, cutter=True)
first = len(laid)
re_.set_side(C, cube, 1)
re_.set_side(C, cube, 2)
check('Live ramp: another deep side reuses the layout (the slow part is not done again)',
      first == 1 and len(laid) == 1 and re_.record(cube)['side'] == 2, laid)
p.carve_depth = 0.15
check('... a new depth too (for a Cut Ramp the edge width stays; Base Mesh edge follows depth: laid out again)',
      re_.record(cube) is not None)
check('... the carved mesh is fingerprinted', 'stamp' in re_.record(cube) and not re_.edited(cube))
cube.data.vertices[0].co.z += 0.37
moved = cube.data.vertices[0].co.copy()
p.ramp_soft = 0.2                              # a slider: before 0.24.53 this silently undid the edit
check('Edit after the ramp, then move a Ramp slider: the edit stays, the ramp is kept as it is (no longer live)',
      (cube.data.vertices[0].co - moved).length < 1e-6 and re_.record(cube) is None and re_.live_target(C) is None)
try:
    re_.recarve(C, cube)
    ok = True
except cg.CutError:
    ok = False
check('... nothing to re-carve any more', ok)
sd._carve_layout = real_layout
fc_.ENABLED = True

# --- Quad Remesh bevel -----------------------------------------------------------------------------------------
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
part = block('Part', cuts=2)
cut.gn_finish = 'NONE'
ce.perform_closed(C, 'CUT', [part], [SQ], TOP, False)
st = S.mch_quadremesh
st.method, st.faces, st.bevel, st.bevel_edges = 'PATCH', 1500, False, 'OUTER'
bpy.ops.object.select_all(action='DESELECT')
part.select_set(True)
C.view_layer.objects.active = part
bpy.ops.mch.quad_remesh()
q = C.active_object
check('Quad result: no bevel unless asked', qr.is_quad(q) and q.modifiers.get(qr.BEVEL) is None)
st.bevel = True
bev = q.modifiers.get(qr.BEVEL)
outer = qr.edge_weights(q.data, True)
every = qr.edge_weights(q.data, False)
qr.edge_weights(q.data, True)
check('Bevel Edges: a live Bevel on the kept edges by weight, 2 segments (all quads); Outer = fewer edges than All '
      '(the pocket floor corners stay sharp)', bev is not None and bev.limit_method == 'WEIGHT' and bev.segments == 2
      and 0 < outer < every, (outer, every))
dg = C.evaluated_depsgraph_get()
ev = q.evaluated_get(dg).to_mesh()
check('... the bevelled result is all quads and closed', all(len(f.vertices) == 4 for f in ev.polygons),
      len(ev.polygons))
q.evaluated_get(dg).to_mesh_clear()
st.bevel_edges = 'ALL'
st.bevel = False
check('Bevel off: the modifier goes', q.modifiers.get(qr.BEVEL) is None)
st.bevel = True
nf = len(q.data.polygons)
bpy.ops.mch.quad_apply()
check('Apply: the bevel is made real', q.modifiers.get(qr.BEVEL) is None and len(q.data.polygons) > nf
      and not qr.is_quad(q), (nf, len(q.data.polygons)))
st.bevel = False
summary()
