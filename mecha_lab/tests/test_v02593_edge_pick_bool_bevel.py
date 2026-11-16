"""0.24.178 (user: "차라리 이건 내가 선을 긋는 게 아니라 내가 선택할 수 있는 엣지들을 보여 주는 게 나을 거 같고, 내가 설정한
브러시 크기로 베벨이랑 챔퍼가 생기고, 알트 누르면 지워지게" + "불린 베벨 만들자, 그건 걍 메뉴로 빼 주고, 내가 원하는 만큼
그리면 걍 그 부분이 베벨 불린이 되는 거, 챔퍼랑"):
- edge runs: a part's hard edges joined where they go on straight (a box: 12, a round hole's rim: one loop, an edge
  split along the way: one run);
- Geo Sculpt Chamfer / Round: the run under the brush taken whole, the brush's width; Alt: off;
- Boolean Bevel (its own tool): drag along an edge - that much of it cut off (Chamfer: flat at 45 degrees, Round: an
  arc), a click: all of it (through the corners); the part's own mesh cut, its other modifiers left alone; a loop's
  rim; an inside corner: told."""
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
try:
    bb.perform(C, L_, [(0.0, y, 0.0) for y in np.linspace(-0.5, 0.5, 8)])
    err = None
except bb.BevelError as ex:
    err = str(ex)
check(f'an inside corner: told ({err})', err is not None and 'inside' in err)
summary()
