"""0.24.178 (user: "차라리 이건 내가 선을 긋는 게 아니라 내가 선택할 수 있는 엣지들을 보여 주는 게 나을 거 같고, 내가 설정한
브러시 크기로 베벨이랑 챔퍼가 생기고, 알트 누르면 지워지게" + "불린 베벨 만들자, 그건 걍 메뉴로 빼 주고, 내가 원하는 만큼
그리면 걍 그 부분이 베벨 불린이 되는 거, 챔퍼랑"):
- edge runs: a part's hard edges joined where they go on straight (a box: 12, a round hole's rim: one loop, an edge
  split along the way: one run);
- Geo Sculpt Chamfer / Round: the run under the brush taken whole, the brush's width; Alt: off;
- Boolean Bevel (its own tool): drag along an edge - that much of it cut off (Chamfer: flat at 45 degrees, Round: an
  arc), a click: all of it (through the corners); the part's own mesh cut, its other modifiers left alone; a loop's
  rim; an inside corner: (0.24.180) a fillet joined on."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import bmesh  # noqa: E402
import mecha_lab
from mecha_lab import bool_bevel as bb, edge_runs as er, geo_sculpt as gs, tool_state as ts  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_bool_bevel.method = 'CUT'          # (0.24.221 the tool now starts on Move Points: this is the Cut's test)


def closed_ok(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bad = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    vol = bm.calc_volume(signed=True)
    bm.free()
    return bad, vol


def dist_to_surface(ob, p):
    me = ob.data
    bvh = BVHTree.FromPolygons([tuple(v.co) for v in me.vertices], [tuple(f.vertices) for f in me.polygons])
    return bvh.find_nearest(Vector(p))[3]


check(f'the tool: its own tile in the Cut group ({ts.TOOL_BY_ID["BBEVEL"][5]})',
      ts.TOOL_BY_ID['BBEVEL'][5] == 'mecha.bool_bevel' and 'BBEVEL' in dict(ts.TOOL_GROUPS)['Cut'])
# --- runs
bpy.ops.mesh.primitive_cube_add(size=2.0)
box = C.active_object
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.subdivide(number_cuts=3)
bpy.ops.object.mode_set(mode='OBJECT')
r = er.get(box)
bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.5, depth=1.0, location=(4, 0, 0))
cyl = C.active_object
rc = er.get(cyl)
check(f'edge runs: a subdivided box - 12 (each side of it one run, {sorted(set(len(p) for p in r.paths))} points); a '
      f'cylinder - its two rims, each one loop ({rc.closed})', len(r.paths) == 12 and set(len(p) for p in r.paths) == {5}
      and len(rc.paths) == 2 and all(rc.closed))
# --- Geo Sculpt Chamfer / Round: a run picked whole
got = gs.pick_run(box, (0.3, -1.0, 1.0), 0.1)
n = gs.mark_edges(box, 'CHAMFER', got[1], 0.12)
eff = gs.safe_widths(box.data)['CHAMFER']
check(f'Chamfer: the run under the brush (near its middle) taken whole ({n} edges = that side of the box), the brush\'s '
      f'width ({sorted(set(np.round(eff[eff > 0], 3).tolist()))})', n == 4 and np.allclose(eff[eff > 0], 0.12))
got2 = gs.pick_run(box, (1.0, 0.0, 1.0), 0.1)
gs.mark_edges(box, 'ROUND', got2[1], 0.08)
gs.mark_edges(box, 'CHAMFER', got[1], 0.12, remove=True)
w_c = gs.safe_widths(box.data)['CHAMFER']
w_r = gs.safe_widths(box.data)['ROUND']
check(f'Round on another side; Alt on the first: off (chamfered edges left {int((w_c > 0).sum())}, rounded '
      f'{int((w_r > 0).sum())}, the chamfer modifier gone {box.modifiers.get(gs.CHAMFER_MOD) is None})',
      not (w_c > 0).any() and (w_r > 0).sum() == 4 and box.modifiers.get(gs.CHAMFER_MOD) is None)
check('nothing near: nothing picked', gs.pick_run(box, (0.0, 0.0, 1.0), 0.1) is None)
# a thin plate (0.12) with a wide chamfer (0.108) on its top front edge: the mouse on the chamfer, near the back edge
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 6.0))
thin = C.active_object
thin.scale = (2.0, 0.12, 1.4)
bpy.ops.object.transform_apply(location=False, scale=True)
g0 = gs.pick_run(thin, (-0.5, -0.06, 0.7), 0.1)
gs.mark_edges(thin, 'CHAMFER', g0[1], 0.108)
g1 = gs.pick_run(thin, (-0.5, 0.03, 0.68), 0.1)       # (on the chamfer's upper part: nearer the back edge's line)
check(f'Alt + click on a wide chamfer near another edge: the chamfered edge picked (run {g1 and g1[0]}, the chamfered '
      f'one {g0[0]}) - before: the edge behind it, so nothing came off', g1 is not None and g1[0] == g0[0])
bpy.data.objects.remove(thin)
bpy.data.objects.remove(box)
bpy.data.objects.remove(cyl)
# --- Boolean Bevel
bpy.ops.mesh.primitive_cube_add(size=2.0)
blk = C.active_object
blk.name = 'Block'
blk.modifiers.new('Keep Me', 'BEVEL').width = 0.01                     # (another modifier: left as it is)
st = S.mch_bool_bevel
st.profile, st.width = 'CHAMFER', 0.2
msg = bb.perform(C, blk, [(-0.6 + 0.6 * i / 9, -1.0, 1.0) for i in range(10)])
bad, vol = closed_ok(blk)
d_mid = dist_to_surface(blk, (-0.3, -1.0, 1.0))
d_out = dist_to_surface(blk, (0.6, -1.0, 1.0))
check(f'Chamfer dragged along part of the top front edge (x -0.6 .. 0): cut there - the corner 45 degrees in '
      f'({d_mid * math.sqrt(2):.3f} = Width 0.2), the rest of the edge as it was ({d_out:.4f}); closed ({bad} open), '
      f'volume {vol:.4f} (8 - 0.6 x 0.02 = 7.988); its Bevel modifier kept - {msg}',
      abs(d_mid * math.sqrt(2) - 0.2) < 2e-3 and d_out < 1e-6 and bad == 0 and abs(vol - (8 - 0.6 * 0.02)) < 1e-3
      and blk.modifiers.get('Keep Me') is not None and len(blk.modifiers) == 1)
st.profile, st.segments = 'ROUND', 12
bb.perform(C, blk, [(1.0, 0.0, 1.0)], whole=True)                       # (a click on the top right edge: all of it)
bad2, vol2 = closed_ok(blk)
r_ = 0.2
removed = (r_ * r_ - math.pi * r_ * r_ / 4) * 2.0
d_c = dist_to_surface(blk, (1.0, 0.0, 1.0))
check(f'Round, a click on the top right edge: all of it, an arc (the corner {d_c:.4f} in; a quarter circle of 0.2: '
      f'{0.2 * (math.sqrt(2) - 1):.4f}), through both ends - closed ({bad2} open), volume {vol2:.4f} (less by '
      f'{vol - vol2:.4f}; the arc takes {removed:.4f})', abs(d_c - 0.2 * (math.sqrt(2) - 1)) < 4e-3 and bad2 == 0
      and abs((vol - vol2) - removed) < 4e-3)
bpy.data.objects.remove(blk)
# drawn along the top front edge and on round the corner down the right front edge: both snapped onto, both cut
bpy.ops.mesh.primitive_cube_add(size=2.0)
blk2 = C.active_object
st.profile, st.width = 'CHAMFER', 0.15
path = [(x, -1.02, 1.03) for x in np.linspace(0.2, 0.98, 10)] + [(1.03, -1.02, z) for z in np.linspace(0.95, 0.2, 10)]
parts = bb.portions(er.get(blk2), path, 0.1)
msg2 = bb.perform(C, blk2, path, reach=0.1)
bad4, _v4 = closed_ok(blk2)
d_top = dist_to_surface(blk2, (0.6, -1.0, 1.0)) * math.sqrt(2)
d_side = dist_to_surface(blk2, (1.0, -1.0, 0.5)) * math.sqrt(2)
d_far = dist_to_surface(blk2, (-0.6, -1.0, 1.0))
check(f'drawn along an edge and on round the corner: it snaps onto both ({len(parts)} edges) - both cut (top '
      f'{d_top:.3f}, side {d_side:.3f}), not past where it was drawn ({d_far:.4f}); closed ({bad4} open) - {msg2}',
      len(parts) == 2 and abs(d_top - 0.15) < 3e-3 and abs(d_side - 0.15) < 3e-3 and d_far < 1e-6 and bad4 == 0)
bpy.data.objects.remove(blk2)
# a rectangular hole's top rim, clicked: the cut stops at the hole's corners (no notch into the face beyond them);
# its two sides too: they meet mitred at the corners
bpy.ops.mesh.primitive_cube_add(size=2.0)
pl = C.active_object
pl.scale = (1.0, 0.1, 1.0)
bpy.ops.object.transform_apply(scale=True)
bpy.ops.mesh.primitive_cube_add(size=1.0)
hole = C.active_object
hole.scale = (0.8, 1.0, 0.6)
m = pl.modifiers.new('B', 'BOOLEAN')
m.object, m.solver = hole, 'EXACT'
C.view_layer.objects.active = pl
bpy.ops.object.modifier_apply(modifier='B')
bpy.data.objects.remove(hole)
st.profile, st.width = 'CHAMFER', 0.08
bb.perform(C, pl, [(0.0, -0.1, 0.3)], whole=True, reach=0.05)              # (the hole's top front rim)
beyond = dist_to_surface(pl, (-0.46, -0.1, 0.34))                        # (on the face, left of the hole's corner)
mid = dist_to_surface(pl, (0.0, -0.1, 0.3)) * math.sqrt(2)
bad5, _v5 = closed_ok(pl)
bb.perform(C, pl, [(-0.4, -0.1, 0.0)], whole=True, reach=0.05)            # (its left front rim)
corner = dist_to_surface(pl, (-0.4, -0.1, 0.3))
bad6, _v6 = closed_ok(pl)
check(f'a hole\'s top rim clicked: chamfered ({mid:.3f}), not past the hole\'s corner into the face ({beyond:.4f} off it); '
      f'its left rim too: they meet at the corner (the corner {corner * math.sqrt(2):.3f} in), closed ({bad5}, {bad6})',
      abs(mid - 0.08) < 3e-3 and beyond < 1e-6 and abs(corner * math.sqrt(2) - 0.08) < 0.02 and bad5 == 0 and bad6 == 0)
bpy.data.objects.remove(pl)
# (user, two screenshots: "옆에 라인 클릭해서 베벨 하면 이렇게 돼, 저 베벨이 만나야 되는 거 아니여?") one edge, then the
# one beside it: they meet at their corner, whichever came first
bpy.ops.mesh.primitive_cube_add(size=2.0)
bx = C.active_object
st.profile, st.width, st.segments = 'ROUND', 0.2, 8
bb.perform(C, bx, [(0.0, -1.0, -1.0)], whole=True, reach=0.05)          # (the bottom front edge, rounded)
st.profile = 'CHAMFER'
msg_b = bb.perform(C, bx, [(1.0, -1.0, 0.0)], whole=True, reach=0.05)   # (then the right front edge, chamfered)
near_corner = dist_to_surface(bx, (1.0, -1.0, -0.85)) * math.sqrt(2)   # (on the right edge, just above the round)
bad7, vol7 = closed_ok(bx)
# the same two, the other way round: the same part
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 0.0))
bx2 = C.active_object
st.profile = 'CHAMFER'
bb.perform(C, bx2, [(1.0, -1.0, 0.0)], whole=True, reach=0.05)
st.profile = 'ROUND'
bb.perform(C, bx2, [(0.0, -1.0, -1.0)], whole=True, reach=0.05)
bad8, vol8 = closed_ok(bx2)
check(f'round one edge, then chamfer the one beside it: the chamfer runs on into the corner and meets the round (just '
      f'above it: {near_corner:.3f} in, the chamfer 0.2 - before: a notch, it stopped square), closed ({bad7}); the '
      f'other way round: the same part (volume {vol7:.4f} / {vol8:.4f}) - {msg_b}',
      abs(near_corner - 0.2) < 0.01 and bad7 == 0 and bad8 == 0 and abs(vol7 - vol8) < 1e-4)
# Alt + click the round: off - the chamfer stays, running on to the corner now
r_alt = bb.perform(C, bx, [(0.0, -1.0, -1.0)], whole=True, reach=0.05, remove=True)
d_round_gone = dist_to_surface(bx, (0.0, -1.0, -1.0))
d_cham_still = dist_to_surface(bx, (1.0, -1.0, 0.0)) * math.sqrt(2)
check(f'Alt + click the round edge: its cut off (the corner {d_round_gone:.4f} off the surface: there again), the '
      f'chamfer kept ({d_cham_still:.3f}) - {r_alt}', d_round_gone < 1e-6 and abs(d_cham_still - 0.2) < 0.01)
# a thin one (0.24.179 "불린 베벨도 더 얇은 두께도 되게"): 1 mm on a 2 m block
st.profile, st.width = 'CHAMFER', 0.001
bb.perform(C, bx2, [(-1.0, 0.0, 1.0)], whole=True, reach=0.05)
d_thin = dist_to_surface(bx2, (-1.0, 0.0, 1.0)) * math.sqrt(2)
bad_t, _vt = closed_ok(bx2)
rna = bb.MCH_PG_BoolBevel.bl_rna.properties['width']
check(f'thin: Width 1 mm cut ({d_thin * 1000:.2f} mm), closed ({bad_t}); the slider from {rna.soft_min * 1000:.1f} mm '
      f'to {rna.soft_max * 1000:.0f} mm (min {rna.hard_min * 1000:.2f} mm)', abs(d_thin - 0.001) < 1e-4 and bad_t == 0
      and rna.hard_min <= 0.0001 and rna.soft_max <= 0.2 + 1e-6)
st.width = 0.2
bpy.data.objects.remove(bx)
bpy.data.objects.remove(bx2)
# Targets (0.24.179 "셀렉트랑 오토"): Selected - a mesh not selected is looked through
from mecha_lab import geo_sculpt as gs2, target_rules as tr  # noqa: E402
check('Targets: the Boolean Bevel and Geo Sculpt tools have the Target row (Auto / Selected / Active)',
      {'BBEVEL', 'GSCULPT'} <= tr.TARGET_ONLY)
# a step (a low block and a tall one joined): the low one's top front edge and the tall one's front edge, rounded
bpy.ops.mesh.primitive_cube_add(size=1.0)
stp = C.active_object
stp.scale = (2.0, 1.0, 1.0)
stp.location = (0.0, 0.0, 0.0)
bpy.ops.object.transform_apply(location=True, scale=True)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(1.5, 0.0, 0.5))
tall = C.active_object
tall.scale = (1.0, 1.0, 2.0)
bpy.ops.object.transform_apply(location=True, scale=True)
m = stp.modifiers.new('U', 'BOOLEAN')
m.object, m.operation, m.solver = tall, 'UNION', 'EXACT'
C.view_layer.objects.active = stp
bpy.ops.object.modifier_apply(modifier='U')
bpy.data.objects.remove(tall)
st.profile, st.width = 'ROUND', 0.15
bb.perform(C, stp, [(0.0, -0.5, 0.5)], whole=True, reach=0.05)        # (the low block's top front edge)
bb.perform(C, stp, [(1.0, -0.5, 1.0)], whole=True, reach=0.05)        # (the tall block's front left edge)
bad9, _v9 = closed_ok(stp)
corner_left = dist_to_surface(stp, (0.98, -0.48, 0.52))                 # (where the two met: the corner's block)
on_wall = dist_to_surface(stp, (0.9, -0.3, 0.5))                         # (the low block's top beside the wall)
check(f'a step: the low block\'s top edge and the tall block\'s front edge rounded, one after the other - no block left '
      f'in the corner where they meet ({corner_left:.4f} of the corner point off the new surface), the low block\'s top '
      f'by the wall untouched ({on_wall:.4f}), closed ({bad9})', corner_left > 0.01 and on_wall < 1e-6 and bad9 == 0)
bpy.data.objects.remove(stp)
# a loop: the top rim of a cylinder, half of it
bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=1.0, depth=1.0)
cy = C.active_object
st.profile, st.width = 'CHAMFER', 0.1
half = [(math.cos(a), math.sin(a), 0.5) for a in np.linspace(0.1, math.pi - 0.1, 30)]
bb.perform(C, cy, half)
bad3, _v = closed_ok(cy)
d_in = dist_to_surface(cy, (0.0, 1.0, 0.5))
d_far = dist_to_surface(cy, (0.0, -1.0, 0.5))
check(f'a cylinder\'s top rim, half of it drawn: chamfered there ({d_in * math.sqrt(2):.3f}), the other half as it was '
      f'({d_far:.4f}); closed ({bad3} open)', abs(d_in * math.sqrt(2) - 0.1) < 0.01 and d_far < 1e-3 and bad3 == 0)
bpy.data.objects.remove(cy)
# an inside corner (an L block's inner edge): told
bpy.ops.mesh.primitive_cube_add(size=2.0)
L_ = C.active_object
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.5, 0.0, 0.5))
notch = C.active_object
notch.scale = (1.0, 3.0, 1.0)
m = L_.modifiers.new('B', 'BOOLEAN')
m.object, m.solver = notch, 'EXACT'
C.view_layer.objects.active = L_
bpy.ops.object.modifier_apply(modifier='B')
bpy.data.objects.remove(notch)
# 0.24.180 (user: "베벨은 왜 안으로 들어간 건 안 돼?"): an inside edge - a fillet joined on
_b0, vol0 = closed_ok(L_)
msg_in = bb.perform(C, L_, [(0.0, y, 0.0) for y in np.linspace(-0.5, 0.5, 8)])
bad9, vol9 = closed_ok(L_)
d_mid = dist_to_surface(L_, (0.0, 0.0, 0.0))
d_out = dist_to_surface(L_, (0.0, 0.9, 0.0))
check(f'an inside corner (an L block\'s inner edge) drawn along: a chamfer joined on there (the corner {d_mid:.4f} under '
      f'the new face = 0.1 / sqrt 2 = 0.0707), past it as it was ({d_out:.4f}); closed ({bad9}), volume {vol0:.4f} -> '
      f'{vol9:.4f} (+ 0.1 x 0.1 / 2 x 1 = 0.005) - {msg_in}', abs(d_mid - 0.1 / math.sqrt(2)) < 3e-3 and d_out < 1e-6
      and bad9 == 0 and abs(vol9 - vol0 - 0.005) < 6e-4)
bb.perform(C, L_, [(0.0, 0.0, 0.0)], whole=True, reach=0.05, remove=True)
_b, vol_back = closed_ok(L_)
st.profile, st.width, st.segments = 'ROUND', 0.2, 16
bb.perform(C, L_, [(0.0, 0.0, 0.0)], whole=True, reach=0.05)
bad10, vol10 = closed_ok(L_)
d_r = dist_to_surface(L_, (0.0, 0.0, 0.0))
want_v = 0.2 * 0.2 * (1 - math.pi / 4) * 2.0          # (the room between a quarter round and the corner, all along)
check(f'Alt: the fillet off (volume {vol_back:.4f}); Round 0.2 on the whole inside edge: a quarter round joined on (the '
      f'corner {d_r:.4f} under it = 0.2 x (sqrt 2 - 1) = 0.0828; volume + {vol10 - vol_back:.4f}, the room between a '
      f'quarter round and the corner: {want_v:.4f}), closed ({bad10})',
      abs(vol_back - vol0) < 1e-6 and abs(d_r - 0.2 * (math.sqrt(2) - 1)) < 4e-3
      and abs((vol10 - vol_back) - want_v) < 2e-3 and bad10 == 0)
summary()
