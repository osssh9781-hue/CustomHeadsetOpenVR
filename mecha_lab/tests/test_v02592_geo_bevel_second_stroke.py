"""0.24.178 Geo Sculpt Chamfer / Round (user, two screenshots of a mecha panel: "처음엔 돼도 같은 메쉬 다른 곳에 한 번 더 그으면
이렇게 돼"): the first stroke chamfered its edge; a second stroke elsewhere on the same part changed the first one.  The
part's Bevel modifier had Clamp Overlap on, which narrows EVERY bevelled edge of the part to its tightest spot - a second
stroke along the narrow strip between two panel holes shrank the first chamfer 0.08 -> 0.06 (busier parts: further, and
slivers).  Now each run of joined edges is capped by what fits beside it (its own spot), Clamp Overlap off."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import bmesh  # noqa: E402
import mecha_lab
from mecha_lab import geo_sculpt as gs  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
# an armour plate 2 x 1.4, 0.12 thick, with panel holes near its right side (a narrow strip between two of them)
bpy.ops.mesh.primitive_cube_add(size=1.0)
plate = C.active_object
plate.scale = (2.0, 0.12, 1.4)
bpy.ops.object.transform_apply(scale=True)
for (x, z, w, h) in ((0.55, 0.3, 0.18, 0.3), (0.55, -0.1, 0.18, 0.3), (0.55, -0.45, 0.18, 0.2), (0.78, 0.1, 0.06, 0.5)):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, 0, z))
    cut = C.active_object
    cut.scale = (w, 0.5, h)
    m = plate.modifiers.new('B', 'BOOLEAN')
    m.object, m.operation, m.solver = cut, 'DIFFERENCE', 'EXACT'
    C.view_layer.objects.active = plate
    bpy.ops.object.modifier_apply(modifier='B')
    bpy.data.objects.remove(cut)


def chamfer_at(p):
    """The chamfer's width at a point of a 90 degree edge (its face is w / sqrt 2 from the corner)."""
    dg = C.evaluated_depsgraph_get()
    dg.update()
    ev = plate.evaluated_get(dg)
    me = ev.to_mesh()
    bvh = BVHTree.FromPolygons([tuple(v.co) for v in me.vertices], [tuple(f.vertices) for f in me.polygons])
    ev.to_mesh_clear()
    return bvh.find_nearest(Vector(p))[3] * math.sqrt(2)


def broken():
    dg = C.evaluated_depsgraph_get()
    dg.update()
    ev = plate.evaluated_get(dg)
    bm = bmesh.new()
    bm.from_mesh(ev.to_mesh())
    ev.to_mesh_clear()
    out = (sum(1 for e in bm.edges if len(e.link_faces) != 2), sum(1 for f in bm.faces if f.calc_area() < 1e-9))
    bm.free()
    return out


def seg(a, b, n=24):
    return [tuple(Vector(a).lerp(Vector(b), i / (n - 1))) for i in range(n)]


def reset():
    for m_ in list(plate.modifiers):
        plate.modifiers.remove(m_)
    for nm in [a.name for a in plate.data.attributes if a.name.startswith('mch_geo_')]:
        plate.data.attributes.remove(plate.data.attributes[nm])


TOP = (-0.5, -0.06, 0.7)
gs.mark_bevel(plate, 'CHAMFER', seg((-0.9, -0.06, 0.7), (-0.1, -0.06, 0.7)), 0.08)
w1 = chamfer_at(TOP)
gs.mark_bevel(plate, 'CHAMFER', seg((0.75, -0.06, -0.1), (0.75, -0.06, 0.3)), 0.08)
w1b = chamfer_at(TOP)
eff = gs.safe_widths(plate.data)['CHAMFER']
widths = sorted(set(np.round(eff[eff > 0], 3).tolist()))
mod = plate.modifiers[gs.CHAMFER_MOD]
check(f'a second stroke along the narrow strip between two holes: the first chamfer stays ({w1:.3f} -> {w1b:.3f}; '
      f'before 0.080 -> 0.060), the strip\'s own edge narrower where it does not fit ({widths}), no Clamp Overlap '
      f'({mod.use_clamp_overlap}), nothing broken {broken()}',
      abs(w1 - 0.08) < 2e-3 and abs(w1b - w1) < 1e-4 and len(widths) == 2 and widths[0] < 0.08 and widths[0] > 0.02
      and not mod.use_clamp_overlap and broken() == (0, 0))
# a long edge split at a boolean's T point (straight on): its run still bevelled (not 0)
reset()
bm = bmesh.new()
bm.from_mesh(plate.data)
straight = [e for e in bm.edges if abs(e.verts[0].co.x - 0.46) < 1e-4 and abs(e.verts[1].co.x - 0.46) < 1e-4
            and abs(e.verts[0].co.y + 0.06) < 1e-4 and abs(e.verts[1].co.y + 0.06) < 1e-4]
bm.free()
gs.mark_bevel(plate, 'ROUND', seg((0.46, -0.06, 0.2), (0.46, -0.06, 0.4)), 0.04)
eff = gs.safe_widths(plate.data)['ROUND']
check(f'an edge going on straight past a split point: bevelled ({sorted(set(np.round(eff[eff > 0], 3).tolist()))})',
      (eff > 0.02).any())
# twelve more strokes, Chamfer and Round, on random hard edges: the first chamfer keeps its width (the way it was:
# narrowed to 0.054 and a broken face)
rng = np.random.default_rng(3)
bmo = bmesh.new()
bmo.from_mesh(plate.data)
cands = [(e.verts[0].co.copy(), e.verts[1].co.copy()) for e in bmo.edges
         if len(e.link_faces) == 2 and e.calc_face_angle(0) > 0.6]
bmo.free()


def fuzz(old):
    reset()
    keep = gs.safe_widths
    if old:
        gs.safe_widths = lambda me: {kd: gs._raw_widths(me, kd) for kd in gs.BEVEL_MODS}
    try:
        gs.mark_bevel(plate, 'CHAMFER', seg((-0.9, -0.06, 0.7), (-0.1, -0.06, 0.7)), 0.08)
        r = np.random.default_rng(3)
        for k in range(12):
            a, b = cands[int(r.integers(len(cands)))]
            gs.mark_bevel(plate, 'CHAMFER' if k % 2 else 'ROUND', seg(a.lerp(b, 0.15), a.lerp(b, 0.85)),
                          float(r.uniform(0.02, 0.12)))
            if old:
                for mm in plate.modifiers:
                    if mm.type == 'BEVEL':
                        mm.use_clamp_overlap = True
    finally:
        gs.safe_widths = keep
    return chamfer_at(TOP), broken()


w_old, b_old = fuzz(True)
w_new, b_new = fuzz(False)
check(f'12 more strokes (Chamfer / Round, random edges): the first chamfer {w_new:.3f} (the way it was: {w_old:.3f}), '
      f'nothing broken {b_new} (the way it was: {b_old})', w_new > w_old + 0.01 and b_new == (0, 0))
summary()
