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
