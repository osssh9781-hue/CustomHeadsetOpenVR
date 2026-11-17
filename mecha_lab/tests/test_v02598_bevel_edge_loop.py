"""0.24.180 (user: "엣지 루프 기능도 만들어 주라" - "베벨 말이지"): Edge Loop for the bevels - a click takes the whole
loop round the face area on the mouse's side of the edge (a box's top: its four edges; a cylinder's cap: its rim; a
plate with a hole: the hole's rim or the outline, whichever was clicked): Boolean Bevel cuts it all (corners meet,
closed), Alt takes it all off; an L-step's loop fills its inside corner (0.24.180); Geo Sculpt Chamfer / Round marks it all."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import bmesh  # noqa: E402
import mecha_lab
from mecha_lab import bool_bevel as bb, edge_runs, geo_sculpt as gs  # noqa: E402

fresh()
mecha_lab.register()
bpy.context.scene.mch_bool_bevel.method = 'CUT'   # (0.24.221 the tool starts on Move Points: this is the Cut's test)
C = bpy.context
S = C.scene


def closed_ok(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bad = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    vol = bm.calc_volume(signed=True)
    bm.free()
    return bad, vol


def dist(ob, p):
    me = ob.data
    bvh = BVHTree.FromPolygons([tuple(v.co) for v in me.vertices], [tuple(f.vertices) for f in me.polygons])
    return bvh.find_nearest(Vector(p))[3]


def mids(runs, edges):
    return sorted(tuple(np.round((runs.co[runs.edges[e][0]] + runs.co[runs.edges[e][1]]) / 2, 3)) for e in edges)


# --- the loops
bpy.ops.mesh.primitive_cube_add(size=2.0)
box = C.active_object
runs = edge_runs.get(box)
top_front = runs.nearest((0.0, -1.0, 1.0), 0.05)[1]
top = runs.loop(top_front, (0.0, -0.9, 1.0))          # (the mouse on the top, by the edge)
front = runs.loop(top_front, (0.0, -1.0, 0.9))        # (on the front)
check(f'a box\'s top front edge, the mouse on the top: the top\'s loop - its four edges ({mids(runs, top)}); on the '
      f'front: the front\'s four ({len(front)}, z of their middles {sorted({m[2] for m in mids(runs, front)})})',
      len(top) == 4 and all(abs(m[2] - 1.0) < 1e-3 for m in mids(runs, top))
      and len(front) == 4 and all(abs(m[1] + 1.0) < 1e-3 for m in mids(runs, front)))
bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=1.0, depth=2.0, location=(5.0, 0.0, 0.0))
cyl = C.active_object
rc = edge_runs.get(cyl)
rim_e = rc.nearest((1.0, 0.0, 1.0), 0.05)[1]
rim = rc.loop(rim_e, (0.9, 0.0, 1.0))
check(f'a cylinder\'s cap: its rim ({len(rim)} edges)', len(rim) == 32)
# a plate with a hole
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 6.0, 0.0))
pl = C.active_object
pl.scale = (1.0, 0.1, 1.0)
bpy.ops.object.transform_apply(scale=True)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 6.0, 0.0))
hole = C.active_object
hole.scale = (0.8, 1.0, 0.6)
m = pl.modifiers.new('B', 'BOOLEAN')
m.object, m.solver = hole, 'EXACT'
C.view_layer.objects.active = pl
bpy.ops.object.modifier_apply(modifier='B')
bpy.data.objects.remove(hole)
rp = edge_runs.get(pl)
L = lambda x, y, z: tuple(pl.matrix_world.inverted() @ Vector((x, 6.0 + y, z)))  # noqa: E731  (world -> its own)
he = rp.nearest(L(0.0, -0.1, 0.3), 0.05)[1]           # (the hole's top front rim)
hole_loop = rp.loop(he, L(0.0, -0.1, 0.35))
oe = rp.nearest(L(0.0, -0.1, 1.0), 0.05)[1]
out_loop = rp.loop(oe, L(0.0, -0.1, 0.95))
hz = sorted({m[2] for m in mids(rp, hole_loop)})
ys = {round(float((pl.matrix_world @ Vector(m))[1]), 3) for m in mids(rp, out_loop)}
check(f'a plate with a hole, the front face: clicked on the hole\'s rim - the hole\'s rim alone ({len(hole_loop)} edges, '
      f'z {hz}); on the outline - the outline alone ({len(out_loop)})',
      len(hole_loop) == 4 and max(abs(z) for z in hz) < 0.31 and len(out_loop) == 4 and ys == {5.9})
# --- Boolean Bevel: the box's top loop
st = S.mch_bool_bevel
st.profile, st.width, st.edge_loop = 'CHAMFER', 0.2, True
msg = bb.perform(C, box, [(0.0, -0.95, 1.0)], whole=True, reach=0.08, loop=True)
cut_at = [dist(box, p) * math.sqrt(2) for p in ((0, -1, 1), (0, 1, 1), (-1, 0, 1), (1, 0, 1))]
below = dist(box, (0.0, -1.0, -1.0))
bad, vol = closed_ok(box)
check(f'Boolean Bevel, Edge Loop, a click on the top front edge: all four top edges chamfered '
      f'({[round(x, 3) for x in cut_at]} = Width 0.2), the bottom as it was ({below:.4f}), closed ({bad}), volume '
      f'{vol:.4f} (8 - 4 x 2 x 0.02 + 4 x 0.2^3 / 3 where two meet at a corner: 7.8507) - {msg}',
      all(abs(x - 0.2) < 3e-3 for x in cut_at) and below < 1e-6 and bad == 0 and abs(vol - 7.8507) < 2e-3
      and 'edge loop' in msg)
corner = dist(box, (1.0, -1.0, 1.0))
check(f'... the corners meet (the box\'s top corner {corner:.3f} off the new surface: cut away, both ways)', corner > 0.1)
msg2 = bb.perform(C, box, [(0.0, -0.95, 1.0)], whole=True, reach=0.08, remove=True, loop=True)
back = max(dist(box, p) for p in ((0, -1, 1), (0, 1, 1), (-1, 0, 1), (1, 0, 1)))
check(f'Alt + click, Edge Loop: the whole loop off ({back:.5f} - the edges there again) - {msg2}', back < 1e-5)
# an L step: its low top's loop has an inside corner (where it meets the wall) - 0.24.180 filled
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(10.0, 0.0, 0.0))
lo = C.active_object
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(10.0, 1.0, 1.0))
hi_ = C.active_object
hi_.scale = (1.0, 0.5, 2.0)
bpy.ops.object.transform_apply(scale=True)
mm = lo.modifiers.new('U', 'BOOLEAN')
mm.object, mm.operation, mm.solver = hi_, 'UNION', 'EXACT'
C.view_layer.objects.active = lo
bpy.ops.object.modifier_apply(modifier='U')
bpy.data.objects.remove(hi_)
msg3 = bb.perform(C, lo, [(0.0, -0.95, 1.0)], whole=True, reach=0.08, loop=True)      # (the mouse on the low top)
f_edge = dist(lo, (0.0, -1.0, 1.0)) * math.sqrt(2)
side = dist(lo, (1.0, -0.25, 1.0)) * math.sqrt(2)
inner = dist(lo, (0.0, 0.5, 1.0))                         # (the inside corner: the low top meets the wall)
bad3, _v = closed_ok(lo)
check(f'an L step, the low top\'s loop: its outside edges chamfered (the front {f_edge:.3f}, a side {side:.3f} = '
      f'Width 0.2), the inside corner where it meets the wall filled - a chamfer joined on ({inner:.4f} of the corner '
      f'under the new face = 0.2 / sqrt 2 = 0.1414), closed ({bad3}) - {msg3}',
      abs(f_edge - 0.2) < 3e-3 and abs(side - 0.2) < 3e-3 and abs(inner - 0.2 / math.sqrt(2)) < 3e-3 and bad3 == 0
      and 'filled' in msg3)
# a shown edge picked off the part (on the edge itself): the side facing the view
rb = edge_runs.get(box)
e0 = rb.nearest((0.0, -1.0, 1.0), 0.05)[1]
from_top = rb.loop(e0, (0.0, -1.0, 1.0), view=(0.0, 0.3, -1.0))
from_front = rb.loop(e0, (0.0, -1.0, 1.0), view=(0.0, 1.0, -0.3))
check(f'the point on the edge itself (a bevelled edge picked off the part): the side facing you - looking down the '
      f'top\'s loop ({sorted({m[2] for m in mids(rb, from_top)})}), looking at the front the front\'s '
      f'({sorted({m[1] for m in mids(rb, from_front)})})',
      all(abs(m[2] - 1) < 1e-3 for m in mids(rb, from_top)) and all(abs(m[1] + 1) < 1e-3 for m in mids(rb, from_front)))
# --- Geo Sculpt Chamfer, Edge Loop
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, -6.0, 0.0))
gb = C.active_object
got = gs.pick_run(gb, (0.0, -0.95, 1.0), 0.1, loop=True)
n = gs.mark_edges(gb, 'CHAMFER', got[1], 0.1)
w = gs.safe_widths(gb.data)['CHAMFER']
marked = [i for i in np.nonzero(w > 0)[0]]
rg = edge_runs.get(gb)
check(f'Geo Sculpt Chamfer, Edge Loop: the top\'s four edges marked ({len(marked)}, all at z 1: '
      f'{all(abs(m[2] - 1) < 1e-3 for m in mids(rg, [int(i) for i in marked]))})',
      len(marked) == 4 and all(abs(m[2] - 1) < 1e-3 for m in mids(rg, [int(i) for i in marked])))
gs.mark_edges(gb, 'CHAMFER', gs.pick_run(gb, (0.0, -0.95, 1.0), 0.1, loop=True)[1], 0.1, remove=True)
check('... Alt: all four off', not (gs.safe_widths(gb.data)['CHAMFER'] > 0).any())
check('the windows: an Edge Loop switch on both tools (Shift + click too)',
      hasattr(S.mch_bool_bevel, 'edge_loop') and hasattr(S.mch_geo, 'edge_loop')
      and any(k.get('shift') for _o, k, _p in bb.MCH_TOOL_bool_bevel.bl_keymap if _o == 'mch.bool_bevel_draw'))
summary()
