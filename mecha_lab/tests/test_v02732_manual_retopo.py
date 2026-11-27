"""0.24.332 Manual Retopo (user: "내가 메쉬 위에 크게 격자무늬로 리토포를 다 그릴게 그럼 그걸 너가 생성해 주면 돼"): the
selected parts joined in a Retopo scene, lines drawn over it -> faces, the Retopo right-click menu, Finish."""
import json
import math

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import manual_retopo as mr

fresh()
mecha_lab.register()
C = bpy.context
main = C.scene

# two parts (a bumpy plate and a box) - the high poly
bpy.ops.mesh.primitive_grid_add(x_subdivisions=40, y_subdivisions=40, size=2.0, location=(0, 0, 0))
plate = C.active_object
for v in plate.data.vertices:
    v.co.z = 0.05 * math.sin(v.co.x * 3) * math.cos(v.co.y * 2)
bpy.ops.mesh.primitive_cube_add(size=0.5, location=(3, 0, 0.25))
box = C.active_object
plate.select_set(True)
co_before = np.array([v.co[:] for v in plate.data.vertices])
ws = mr.start(C, [plate, box], new_window=False)
d = mr.info(ws)
ref, low = mr.ref_of(ws), mr.low_of(ws)
check('Manual Retopo: a Retopo scene with ONE reference (the parts joined, world space) and an empty low; the parts '
      'themselves stay in the main scene untouched',
      ws is not None and ref is not None and low is not None and ref.name in ws.objects and low.name in ws.objects
      and len(ref.data.polygons) == len(plate.data.polygons) + 6 and len(low.data.polygons) == 0
      and plate.name not in ws.objects and plate.name in main.objects
      and np.allclose(co_before, [v.co[:] for v in plate.data.vertices]) and ref.hide_select)
ts = ws.tool_settings
check('the Retopo scene snaps edits onto the model (its own settings); the main scene\'s snap as it was',
      ts.use_snap and 'FACE_PROJECT' in ts.snap_elements and main.tool_settings.use_snap is False)


def surf(x, y):
    return (x, y, 0.05 * math.sin(x * 3) * math.cos(y * 2))


def line(a, b, n=40, tol=0.03):
    return (tol, np.array([surf(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t) for t in np.linspace(0, 1, n)]))


# 3 lines one way, 3 across (a little wobbly, ends overshooting and stopping a bit short) -> 2 x 2 cells
L = [line((-0.8, y), (0.8, y + 0.03)) for y in (-0.6, 0.0, 0.6)]
L += [line((x, -0.62), (x + 0.04, 0.585)) for x in (-0.6, 0.0, 0.6)]
nodes, edges = mr.graph(L)
check(f'the crossings: 9 points, 12 edges between them ({len(nodes)}, {len(edges)})', len(nodes) == 9 and len(edges) == 12)
cells = mr.faces(nodes, edges, lambda p: (0.0, 0.0, 1.0))
check(f'the cells the lines close: 4, each of 4 sides, the outside left out ({[len(c) for c in cells]})',
      len(cells) == 4 and all(len(c) == 4 for c in cells))
mr.set_lines(ws, L)
got = mr.make(C, ws, cuts=1)
me = low.data
n_up = sum(1 for p in me.polygons if p.normal.z > 0.5)
check(f'Enter: 4 quads on the low, facing out, on the surface ({got}, {len(me.vertices)} points)',
      got == (4, 0) and len(me.polygons) == 4 and len(me.vertices) == 9 and n_up == 4
      and max(abs(v.co.z - surf(v.co.x, v.co.y)[2]) for v in me.vertices) < 0.01)
# more lines next to them: the new faces share the old edge (merged)
# the right column's two lower points of the made faces (a line drawn along the old edge, on its points)
right = sorted((v.co.copy() for v in me.vertices if v.co.x > 0.3), key=lambda c: c.y)[:2]
(x0, y0), (x1, y1) = right[0].xy, right[1].xy
mr.set_lines(ws, [line((x0 - 0.05, y0), (x0 + 0.45, y0)), line((x1 - 0.05, y1), (x1 + 0.45, y1)),
                  line((x0, y0 - 0.05), (x1, y1 + 0.05)), line((x0 + 0.35, y0 - 0.05), (x1 + 0.35, y1 + 0.05))])
got2 = mr.make(C, ws, cuts=1)
check(f'more lines next to the made faces: the new cell joined to the low along the shared edge (its corners merged '
      f'with the old points) ({got2}; {len(me.polygons)} faces, {len(me.vertices)} points)',
      got2 == (1, 0) and len(me.polygons) == 5 and len(me.vertices) == 11)
# Cuts 2: each cell 2 x 2 along the lines
bpy.ops.mesh.primitive_plane_add(size=0.1, location=(50, 50, 50))
tmp = C.active_object
low_me = low.data
low.data = bpy.data.meshes.new('tmp_low')
mr.set_lines(ws, L)
got_c = mr.make(C, ws, cuts=2)
check(f'Cuts 2: the 4 cells made 2 x 2 each - 16 quads, 25 points (shared edges shared) ({got_c}, '
      f'{len(low.data.polygons)}, {len(low.data.vertices)})',
      got_c == (16, 0) and len(low.data.polygons) == 16 and len(low.data.vertices) == 25)
low.data = low_me
bpy.data.objects.remove(tmp)
# 0.24.333 (user: "그 옆에 그리면 추가로 같이 붙는 건 어때") lines drawn next to the low (from it outward + one across):
# the low's open border closes the cells - new faces on its own points, no gap, no T
TOP = {'m': [0.5, 0, 0, 0, 0, 0.5, 0, 0, 0, 0, -0.1, 0, 0, 0, 0, 1], 'w': 800, 'h': 800}   # (seen from above)
bpy.ops.mesh.primitive_plane_add(size=0.1, location=(60, 60, 60))
tmp2 = C.active_object
keep_me = low.data
low.data = bpy.data.meshes.new('side_low')
mr.set_lines(ws, [line(a, b) + (TOP,) for a, b in [((-0.8, y), (0.8, y)) for y in (-0.6, 0.0, 0.6)]
                  + [((x, -0.8), (x, 0.8)) for x in (-0.6, 0.0, 0.6)]])
g0 = mr.make(C, ws, cuts=1)
mr.set_lines(ws, [line((x, 0.3), (x, 1.2)) + (TOP,) for x in (-0.6, 0.0, 0.6)] + [line((-0.75, 1.0), (0.75, 1.0)) + (TOP,)])
g1 = mr.make(C, ws, cuts=1)
sm = low.data
users = {}
for p_ in sm.polygons:
    for ek in p_.edge_keys:
        users[ek] = users.get(ek, 0) + 1
check(f'drawn next to the low: 2 new quads on its border points (no second row of points, no edge used 3 times) '
      f'({g0} then {g1}; {len(sm.polygons)} faces, {len(sm.vertices)} points)',
      g0 == (4, 0) and g1 == (2, 0) and len(sm.polygons) == 6 and len(sm.vertices) == 12 and max(users.values()) <= 2)
mr.set_lines(ws, [line((x, -0.2), (x, -1.1)) + (TOP,) for x in (-0.3, 0.3)] + [line((-0.5, -1.0), (0.5, -1.0)) + (TOP,)])
g2 = mr.make(C, ws, cuts=1)
users = {}
for p_ in sm.polygons:
    for ek in p_.edge_keys:
        users[ek] = users.get(ek, 0) + 1
loose_mid = [v for v in sm.vertices if abs(v.co.y + 0.6) < 0.05 and abs(abs(v.co.x) - 0.3) < 0.05]
check(f'lines meeting the border in the middle between its points: the border edges split there (no T, no gap) - the '
      f'new cell has 5 sides (it takes the border point between) ({g2}; points on the border at x=±0.3: {len(loose_mid)})',
      g2 == (0, 1) and len(loose_mid) == 2 and max(users.values()) <= 2
      and all(sum(v.index in p_.vertices for p_ in sm.polygons) == 2 for v in loose_mid))
mr.set_lines(ws, [line((-0.3, y), (-0.98, y)) + (TOP,) for y in (-0.54, 0.05)] + [line((-0.9, -0.75), (-0.9, 0.2)) + (TOP,)])
nv = len(sm.vertices)
g3 = mr.make(C, ws, cuts=1)
check(f'lines meeting the border NEAR its points (a little off, as a hand draws): on those points - a clean quad, 2 new '
      f'points only ({g3}; {len(sm.vertices) - nv} new points)', g3 == (1, 0) and len(sm.vertices) - nv == 2)
low.data = keep_me
bpy.data.objects.remove(tmp2)
# 0.24.334 (user: "중앙에 난 빵꾸는 내가 라쏘로 동그라미 치면 메꿔지게") a loop drawn round a hole fills it
import bmesh  # noqa: E402
keep_me2 = low.data
low.data = bpy.data.meshes.new('hole_low')
ks = [-0.9 + 0.3 * i for i in range(7)]
mr.set_lines(ws, [line((-0.95, y), (0.95, y), 60) + (TOP,) for y in ks] + [line((x, -0.95), (x, 0.95), 60) + (TOP,) for x in ks])
gh = mr.make(C, ws, cuts=1)
hm = low.data
bm_ = bmesh.new()
bm_.from_mesh(hm)
gone = [f for f in bm_.faces if (-0.6 < f.calc_center_median().x < -0.3 and -0.6 < f.calc_center_median().y < -0.3)
        or (0 < f.calc_center_median().x < 0.6 and 0 < f.calc_center_median().y < 0.6)]
bmesh.ops.delete(bm_, geom=gone, context='FACES_ONLY')
bm_.to_mesh(hm)
bm_.free()
nh = len(mr.holes(low))


def circle(cx, cy, r, n=40):
    return np.array([(cx + r * math.cos(t), cy + r * math.sin(t)) for t in np.linspace(0, 2 * math.pi, n)])


px = lambda v: (v + 2) * 200                                          # noqa: E731  (TOP: world -> pixels)
check(f'a closed loop is a lasso, an open stroke is a line ({mr.is_lasso(circle(300, 300, 50))}, '
      f'{mr.is_lasso(np.array([(100 + 10 * i, 300) for i in range(30)], float))})',
      mr.is_lasso(circle(300, 300, 50)) and not mr.is_lasso(np.array([(100 + 10 * i, 300) for i in range(30)], float)))


def punch():
    bm_ = bmesh.new()
    bm_.from_mesh(low.data)
    gone = [f for f in bm_.faces if (-0.6 < f.calc_center_median().x < -0.3 and -0.6 < f.calc_center_median().y < -0.3)
            or (0 < f.calc_center_median().x < 0.6 and 0 < f.calc_center_median().y < 0.6)]
    bmesh.ops.delete(bm_, geom=gone, context='FACES_ONLY')
    bm_.to_mesh(low.data)
    bm_.free()


with C.temp_override(scene=ws, view_layer=ws.view_layers[0], active_object=low, object=low, selected_objects=[low]):
    nf_before = len(low.data.polygons)
    f1 = mr.fill_holes(C, ws, circle(px(-0.45), px(-0.45), 45), TOP)
    nf1 = len(low.data.polygons)
    f2 = mr.fill_holes(C, ws, circle(px(0.3), px(0.3), 90), TOP)
hm = low.data
off = max(abs(v.co.z - surf(v.co.x, v.co.y)[2]) for v in hm.vertices)
check(f'holes in the middle: a 1-cell hole (4 points) and a 2x2 hole (8 points) found, the outside border is not a '
      f'hole ({gh}; {nh} holes)', gh == (36, 0) and nh == 2)
check(f'a lasso round the 1-cell hole: one quad fills it; round the 2x2 hole: filled with a grid of quads; all quads, '
      f'no hole left, the new points on the model ({f1}, {f2}: {nf_before} -> {nf1} -> {len(hm.polygons)} faces, '
      f'{len(mr.holes(low))} holes, {off:.4f} off)',
      f1 == 1 and f2 == 1 and nf1 == nf_before + 1 and len(hm.polygons) >= nf1 + 4
      and all(len(p_.vertices) == 4 for p_ in hm.polygons) and not mr.holes(low) and off < 0.01)
punch()
nb = sum(1 for e in low.data.edges) 
with C.temp_override(scene=ws, view_layer=ws.view_layers[0], active_object=low, object=low, selected_objects=[low]):
    f_all = mr.fill_holes(C, ws, circle(px(0), px(0), 395), TOP)
import bmesh as _b  # noqa: E402
bm_ = _b.new()
bm_.from_mesh(low.data)
border = sum(1 for e in bm_.edges if e.is_boundary)
bm_.free()
check(f'a lasso round everything: both holes inside filled, the outside border left open ({f_all}; {border} border '
      f'edges = the 24 round the outside)', f_all == 2 and border == 24)
low.data = keep_me2
# 0.24.334 (user: "그냥 내가 영역을 그리면 거기 내부를 쿼드로 채워 주는 모드도") Area Fill
keep_me3 = low.data
low.data = bpy.data.meshes.new('area_low')
with C.temp_override(scene=ws, view_layer=ws.view_layers[0], active_object=low, object=low, selected_objects=[low]):
    na = mr.area_fill(C, ws, circle(px(-0.3), px(0.0), 120), TOP, 40)
am = low.data
quads_a = sum(1 for p_ in am.polygons if len(p_.vertices) == 4)
off_a = max(abs(v.co.z - surf(v.co.x, v.co.y)[2]) for v in am.vertices)
up = sum(1 for p_ in am.polygons if p_.normal.z > 0)


def aspect(me):
    worst = 1.0
    for p_ in me.polygons:
        if len(p_.vertices) != 4:
            continue
        c = [me.vertices[i].co for i in p_.vertices]
        L_ = [(c[i] - c[(i + 1) % 4]).length for i in range(4)]
        worst = max(worst, max(L_) / max(min(L_), 1e-9))
    return worst


asp = aspect(am)
check(f'Area Fill: a round outline filled with quads ({na} faces, {quads_a} quads, worst side ratio {asp:.1f}), every '
      f'point on the model ({off_a:.4f} off), facing the eye ({up}/{len(am.polygons)})',
      na >= 16 and asp < 4 and quads_a == len(am.polygons) and off_a < 0.01 and up == len(am.polygons))
nv_a = len(am.vertices)
sq = np.array([(px(0.15), px(-0.45)), (px(0.75), px(-0.45)), (px(0.75), px(0.45)), (px(0.15), px(0.45))])
sq = np.concatenate([np.linspace(sq[i], sq[(i + 1) % 4], 12, endpoint=False) for i in range(4)])
with C.temp_override(scene=ws, view_layer=ws.view_layers[0], active_object=low, object=low, selected_objects=[low]):
    nb_ = mr.area_fill(C, ws, sq, TOP, 40)
quads_b = sum(1 for p_ in am.polygons if len(p_.vertices) == 4)
check(f'Area Fill again (a square beside it): its own quads ({nb_} faces, {quads_b}/{len(am.polygons)} quads overall)',
      nb_ >= 9 and quads_b >= len(am.polygons) * 0.9)
f_s = len(am.polygons)
strip = np.array([(px(-0.9), px(0.68)), (px(0.9), px(0.68)), (px(0.9), px(0.93)), (px(-0.9), px(0.93))])
strip = np.concatenate([np.linspace(strip[i], strip[(i + 1) % 4], 15, endpoint=False) for i in range(4)])
with C.temp_override(scene=ws, view_layer=ws.view_layers[0], active_object=low, object=low, selected_objects=[low]):
    ns_ = mr.area_fill(C, ws, strip, TOP, 40)
tmp_me = bpy.data.meshes.new('strip_only')
tmp_me.from_pydata([v.co[:] for v in am.vertices], [], [list(p_.vertices) for p_ in am.polygons[f_s:]])
asp_s = aspect(tmp_me)
check(f'Area Fill on a long strip: rows of quads along it, not a twist ({ns_} faces - about 9 x 1 at 40 px; worst side ratio '
      f'{asp_s:.1f})', 8 <= ns_ <= 12 and asp_s < 2.5)
Lsh = np.array([(px(-0.8), px(-0.9)), (px(-0.2), px(-0.9)), (px(-0.2), px(-0.7)), (px(-0.6), px(-0.7)),
                (px(-0.6), px(-0.3)), (px(-0.8), px(-0.3))])
Lsh = np.concatenate([np.linspace(Lsh[i], Lsh[(i + 1) % 6], 10, endpoint=False) for i in range(6)])
f_before = len(am.polygons)
with C.temp_override(scene=ws, view_layer=ws.view_layers[0], active_object=low, object=low, selected_objects=[low]):
    nl_ = mr.area_fill(C, ws, Lsh, TOP, 30)
new_q = sum(1 for p_ in am.polygons[f_before:] if len(p_.vertices) == 4)
check(f'Area Fill on an L shape (not a simple grid): filled, mostly quads ({nl_} faces, {new_q} quads)',
      nl_ > 0 and new_q >= nl_ * 0.6)
with C.temp_override(scene=ws, view_layer=ws.view_layers[0], active_object=low, object=low, selected_objects=[low]):
    n_off = mr.area_fill(C, ws, circle(px(5), px(5), 60), TOP, 40)
check(f'Area Fill off the model: nothing made ({n_off})', n_off == 0)
low.data = keep_me3
# 0.24.335 (user: "전에 만든 거랑 안 붙어? 에리어 필") Area Fill over the low made already: joined to its border
keep_me4 = low.data
low.data = bpy.data.meshes.new('attach_low')
mr.set_lines(ws, [line((-0.8, y), (0.8, y)) + (TOP,) for y in (-0.6, 0.0, 0.6)]
             + [line((x, -0.8), (x, 0.8)) + (TOP,) for x in (-0.6, 0.0, 0.6)])
mr.make(C, ws, cuts=1)
nv0, nf0_ = len(low.data.vertices), len(low.data.polygons)
# an outline starting well inside the made grid (hand drawn: not on its points) and going out to the right
out = np.array([(px(0.2), px(-0.5)), (px(0.95), px(-0.5)), (px(0.95), px(0.5)), (px(0.2), px(0.5))])
out = np.concatenate([np.linspace(out[i], out[(i + 1) % 4], 15, endpoint=False) for i in range(4)])
with C.temp_override(scene=ws, view_layer=ws.view_layers[0], active_object=low, object=low, selected_objects=[low]):
    nat = mr.area_fill(C, ws, out, TOP, 40)
am2 = low.data
users = {}
for p_ in am2.polygons:
    for ek in p_.edge_keys:
        users[ek] = users.get(ek, 0) + 1
bm_ = bmesh.new()
bm_.from_mesh(am2)
right_col = [v for v in bm_.verts if abs(v.co.x - 0.6) < 0.05 and -0.65 < v.co.y < 0.65]
shared = sum(1 for v in right_col if len(v.link_faces) >= 2)
up2 = sum(1 for f in bm_.faces if f.normal.z > 0)
bm_.free()
check(f'Area Fill drawn over the made grid and out of it: the new quads start ON its border (its right column of '
      f'points shared, none doubled, no edge used 3 times), all one way round ({nat} faces; {shared}/{len(right_col)} '
      f'border points shared; {up2}/{len(am2.polygons)} facing up)',
      nat > 0 and shared == len(right_col) == 3 and max(users.values()) <= 2 and up2 == len(am2.polygons))
# Relax: a grid bunched / twisted into a fan spreads out again, the border stays
for v in low.data.vertices:
    if v.co.x < 0.55 and abs(v.co.x) < 0.1 and abs(v.co.y) < 0.1:
        v.co.x += 0.5                            # (the middle point pushed over to the side: folded)
border0 = {v.index: v.co.copy() for v in low.data.vertices}
nr = mr.relax_low(ws)
moved_border = 0
bm_ = bmesh.new()
bm_.from_mesh(low.data)
for v in bm_.verts:
    if v.is_boundary and (v.co - border0[v.index]).length > 1e-6:
        moved_border += 1
mid = [v.co.copy() for v in bm_.verts if not v.is_boundary and abs(v.co.y) < 0.05 and v.co.x < 0.2]
bm_.free()
check(f'Relax: the pushed-over middle point back between its neighbours, the border points not moved, all on the '
      f'model ({nr} moved; middle at x {[round(c.x, 2) for c in mid]}; {moved_border} border points moved)',
      nr > 0 and moved_border == 0 and mid and abs(mid[0].x) < 0.08
      and max(abs(v.co.z - surf(v.co.x, v.co.y)[2]) for v in low.data.vertices) < 0.01)
# Relax as seen (the view): a twisted fill (its inside turned round like a fan) spreads out again on the screen
tw_me = bpy.data.meshes.new('twist_low')
keep_tw = low.data
low.data = tw_me
with C.temp_override(scene=ws, view_layer=ws.view_layers[0], active_object=low, object=low, selected_objects=[low]):
    mr.area_fill(C, ws, np.array([(px(-0.6), px(-0.6)), (px(0.6), px(-0.6)), (px(0.6), px(0.6)), (px(-0.6), px(0.6))]
                                 ).repeat(1, axis=0) if False else np.concatenate(
        [np.linspace(a_, b_, 20, endpoint=False) for a_, b_ in zip(
            [(px(-0.6), px(-0.6)), (px(0.6), px(-0.6)), (px(0.6), px(0.6)), (px(-0.6), px(0.6))],
            [(px(0.6), px(-0.6)), (px(0.6), px(0.6)), (px(-0.6), px(0.6)), (px(-0.6), px(-0.6))])]), TOP, 40)
bm_ = bmesh.new()
bm_.from_mesh(tw_me)
inner = [v.index for v in bm_.verts if not v.is_boundary]
bm_.free()
good = {i: tw_me.vertices[i].co.copy() for i in inner}
for i in inner:                                  # (turned round the middle: a fan)
    v = tw_me.vertices[i]
    r_ = math.hypot(v.co.x, v.co.y)
    ang = 1.5 * (1 - min(r_ / 0.6, 1))
    x, y = v.co.x, v.co.y
    v.co.x, v.co.y = x * math.cos(ang) - y * math.sin(ang), x * math.sin(ang) + y * math.cos(ang)
    v.co.z = surf(v.co.x, v.co.y)[2]
err0 = max((tw_me.vertices[i].co - good[i]).length for i in inner)
nrx = mr.relax_low(ws, view=TOP)
err1 = max((tw_me.vertices[i].co - good[i]).length for i in inner)
check(f'Relax (as seen): a fill twisted like a fan spreads back out - its inside points back by their grid places '
      f'({nrx} moved; furthest off {err0:.3f} -> {err1:.3f})', nrx == len(inner) and err1 < err0 * 0.25)
low.data = keep_tw
# Ctrl+Z while drawing: the last fill taken back
from types import SimpleNamespace  # noqa: E402
D_ = mr.MCH_OT_mretopo_draw
fake = SimpleNamespace(history=[], L=[], area=None)
fake._save = lambda ctx: None
fake._preview = lambda ctx: None
fake._drop_last = lambda: D_._drop_last(fake)
nf_a = len(low.data.polygons)
with C.temp_override(scene=ws, view_layer=ws.view_layers[0], active_object=low, object=low, selected_objects=[low]):
    D_._snap(fake, C)
    mr.area_fill(C, ws, circle(px(-0.3), px(0.85), 40), TOP, 30)
    nf_b = len(low.data.polygons)
    what = D_._undo(fake, C)
check(f'Ctrl+Z while drawing takes the last fill back ({nf_a} -> {nf_b} -> {len(low.data.polygons)} faces, {what})',
      nf_b > nf_a and len(low.data.polygons) == nf_a and what == 'fill')
low.data = keep_me4
# a triangle cell (3 lines): counted apart
mr.set_lines(ws, [line((-0.9, -0.9), (-0.3, -0.9)), line((-0.85, -0.95), (-0.5, -0.4)), line((-0.35, -0.95), (-0.65, -0.35))])
got3 = mr.make(C, ws, cuts=1)
check(f'three lines: one triangle cell, counted as "not 4 sides" ({got3})', got3 == (0, 1))
# the right-click menu in the Retopo scene, the Actions wheel kept out
from mecha_lab import actions_menu as am  # noqa: E402
win = C.window_manager.windows[0] if C.window_manager.windows else None
check('Retopo menu: its operators are there (draw, finish, edit tools: extrude, merge, knife...)',
      hasattr(bpy.ops.mch, 'mretopo_draw') and hasattr(bpy.ops.mch, 'mretopo_finish')
      and {'EXTRUDE', 'MERGE_CENTER', 'COLLAPSE', 'KNIFE', 'LOOPCUT', 'DELETE'} <= set(mr._EDIT))
km = [it for km_, it in mr._keymaps]
check('right click in Object Mode and Edit Mode (Mesh) goes to the Retopo menu (only in a Retopo scene)',
      len(km) == 2 and all(it.idname == 'mch.mretopo_menu' and it.type == 'RIGHTMOUSE' for it in km))
# edit tools on the low
lay = ws.view_layers[0]
with C.temp_override(scene=ws, view_layer=lay, active_object=low, object=low, selected_objects=[low]):
    r1 = bpy.ops.mch.mretopo_edit(action='MODE')
    bpy.ops.mesh.select_all(action='SELECT')
    r2 = bpy.ops.mch.mretopo_edit(action='MERGE_DIST')
    r3 = bpy.ops.mch.mretopo_edit(action='SNAP')
    r4 = bpy.ops.mch.mretopo_edit(action='MODE')
check(f'Edit Mode / By Distance / Snap / Object Mode from the menu ({r1}, {r2}, {r3}, {r4})',
      r1 == r2 == r3 == r4 == {'FINISHED'} and low.mode == 'OBJECT')
ws.mch_mretopo.mirror = True
check('X Mirror: a live Mirror (clipped at the middle) on the low', low.modifiers.get('MCH Retopo Mirror') is not None)
# Finish
nf = len(low.data.polygons)
with C.temp_override(scene=ws, view_layer=lay):
    low2 = mr.finish(C, ws)
check(f'Finish: the low in the main scene ({nf} faces), the reference and the Retopo scene gone, the low and the '
      f'parts selected (ready for 2 Bake)',
      low2 is low and low.name in main.objects and bpy.data.objects.get(d['ref']) is None
      and bpy.data.scenes.get(ws.name if False else 'Retopo - ' + d['src'][0]) is None
      and all(o.select_get(view_layer=main.view_layers[0]) for o in (low, plate, box)))
summary()
