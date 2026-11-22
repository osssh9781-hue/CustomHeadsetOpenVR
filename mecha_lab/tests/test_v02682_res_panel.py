"""0.24.282 The bottom row's Resolution buttons in two steps (user: "레졸루션 탭의 리메시 / 데시메이션 - 누르면 상세
설정이 왼쪽 패널에, 버튼 다시 누르면 그냥 적용", "컷 툴이랑 스플릿으로 자른 메쉬로 돌려 줘"): on parts made with the
Cut tool (a pocket, a hole) and then the Split tool (two pieces), each button's first click only shows its settings in
the leftmost box, the second runs it with them."""
import math

from _harness import bpy, check, fresh, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import (bottom_row, core_geometry as cg, cut_engine as ce, mecha_menu as mm, quad_field as qf,
                       quad_remesh as qr, res_panel as rp, ui_bars)
from mecha_lab.mecha_menu import Item

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
S.mch_settings.auto_apply = True
PPU = 400.0
TOP = cg.OrthoProjector(Quaternion(), center=Vector((0, 0, 0)), pixels_per_unit=PPU)
cut = S.mch_cut
cut.targets = 'ACTIVE'


def P(x, y):
    return (500 + x * PPU, 500 + y * PPU)


def select(*obs):
    for o in list(C.selected_objects):
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    C.view_layer.objects.active = obs[0]


def pieces():
    """A block cut with the Cut tool (a pocket, a round hole), then split in two with the Split tool."""
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    ob = C.active_object
    ob.scale = (1.2, 0.7, 0.4)
    bpy.ops.object.transform_apply(scale=True)
    select(ob)
    cut.gn_finish, cut.gn_ramp = 'NONE', False
    cut.depth_mode, cut.depth = 'SURFACE', 0.1
    ce.perform_closed(C, 'CUT', [ob], [ce.rect_loop(P(-0.45, -0.15), P(-0.1, 0.15))], TOP)
    ce.perform_closed(C, 'CUT', [ob], [ce.circle_loop(P(0.3, 0.0), P(0.4, 0.0), 24)], TOP)
    before = set(bpy.data.objects)
    ce.perform_line(C, 'SPLIT', [ob], [P(0.05, -0.6), P(0.05, 0.6)], TOP, side_xy=P(0.5, 0.0))
    parts = [o for o in bpy.data.objects if o.type == 'MESH' and o.visible_get()]
    return sorted(parts, key=lambda o: o.location.x + sum((o.matrix_world @ v.co).x for v in o.data.vertices[:50]))


def click(key):
    """A real click's path: the bottom row's button item through ui_bars.run."""
    return ui_bars.run(C, Item('abtn', 0, 0, 10, 10, key, '', False, True, ('resarm', key)))


parts = pieces()
check('Cut + Split made two pieces', len(parts) == 2, [(o.name, len(o.data.polygons)) for o in parts])

# the buttons
res = next(bs for sec, bs in mm.ACTIONS if sec == 'Resolution')
_w, _h, its = bottom_row._section(C, 'Resolution', res, 1.0)
acts = {i.label: i.action for i in its if i.kind == 'abtn'}
check('bottom row: Remesh / Quad / Low Poly / HP x3 / Decimate arm their settings; HP Copy / Clean Materials as before',
      all(acts[lb] == ('resarm', k) for lb, k in rp.KEYS.items()) and acts['HP Copy'][0] == 'mop'
      and acts['Clean Materials'][0] == 'mop', acts)

# Quad, the new engine
a, b = parts
select(a)
n0 = len(a.data.polygons)
click('QUAD')
c = rp.card(C, 1.0)
props = {i.prop for i in c[2]} if c else set()
check('Quad, 1st click: nothing runs, its settings in the left box (engine, Target, Hard Edges, Flow, Subdivision)',
      rp.armed() == 'QUAD' and len(a.data.polygons) == n0
      and {'mch_res_quad_engine', 'qr_target', 'qr_angle', 'qr_flow', 'qr_subd'} <= props, sorted(props))
_w, _h, its = bottom_row._section(C, 'Resolution', res, 1.0)
check('... the Quad button is lit', next(i for i in its if i.label == 'Quad').on)
boxes = bottom_row.boxes(C, 1600, 1000, 1.0)
first = boxes[0][2]
check('... the row\'s first (left) box is those settings', any(getattr(i, 'prop', '') == 'qr_flow' for i in first)
      and not any(i.kind == 'glabel' and i.label.upper() == 'DEPTH' for i in first))
C.scene.mch_zb.qr_target, C.scene.mch_zb.qr_subd = 0.6, 1
click('QUAD')
quads = sum(1 for p in a.data.polygons if len(p.vertices) == 4) / max(1, len(a.data.polygons))
check('Quad, 2nd click: the cut piece remeshed (mostly quads, about 600), Subdivision 1, the box back to the tool',
      rp.armed() is None and quads > 0.85 and 300 < len(a.data.polygons) < 1200
      and qf.subdiv_modifier(a) is not None, (len(a.data.polygons), round(quads, 2)))
C.scene.mch_zb.qr_subd = 0

# Quad, the old engine on the other piece
select(b)
S.mch_res_quad_engine = 'OLD'
click('QUAD')
c = rp.card(C, 1.0)
props = {i.prop for i in c[2]} if c else set()
check('Quad (QuadriFlow / Patch): its own settings', {'method', 'faces', 'edge_angle'} <= props, sorted(props))
S.mch_quadremesh.faces = 600
click('QUAD')
act = C.active_object
check('... 2nd click: Make Quad as before (a quad copy, the original kept hidden)', qr.is_quad(act) and act is not b,
      (act.name, len(act.data.polygons)))
S.mch_res_quad_engine = 'NEW'

# switch / close
click('DECIMATE')
click('REMESH')
check('another button switches the box over (nothing run)', rp.armed() == 'REMESH')
ui_bars.run(C, Item('seg', 0, 0, 1, 1, 'Close', '', False, True, ('resclose',)))
check('Close: the tool\'s box back', rp.armed() is None and not any(getattr(i, 'prop', '') == 'qr_flow'
                                                                    for i in bottom_row.boxes(C, 1600, 1000, 1.0)[0][2]))

# Decimate on a fresh piece
a, b = pieces()
select(a)
bpy.ops.object.modifier_add(type='SUBSURF')
a.modifiers[-1].levels = 3
bpy.ops.object.modifier_apply(modifier=a.modifiers[-1].name)


def tris(o):
    o.data.calc_loop_triangles()
    return len(o.data.loop_triangles)


n0 = len(a.data.polygons)
t0 = tris(a)
click('DECIMATE')
c = rp.card(C, 1.0)
check('Decimate, 1st click: its settings (Keep %, Even, Quads, Borders, shading)', rp.armed() == 'DECIMATE'
      and len(a.data.polygons) == n0 and {'decimate', 'dec_even', 'dec_quads'} <= {i.prop for i in c[2]})
S.mch_zb.decimate = 30
click('DECIMATE')
check('... 2nd click: about 30 % of the triangles left', 0.2 * t0 < tris(a) < 0.4 * t0, (t0, tris(a)))

# Remesh on the other piece
select(b)
S.mch_settings.remesh_by = 'POINTS'
S.mch_settings.target_points = 4000
click('REMESH')
c = rp.card(C, 1.0)
check('Remesh, 1st click: its settings (Remesh By, Target Points, Smooth ...)', rp.armed() == 'REMESH'
      and {'remesh_by', 'target_points', 'smooth_iterations'} <= {i.prop for i in c[2]})
n0 = len(b.data.vertices)
click('REMESH')
check('... 2nd click: voxel remeshed (about 4,000 points)', 2000 < len(b.data.vertices) < 8000,
      (n0, len(b.data.vertices)))

# Low Poly on it
click('LOWPOLY')
c = rp.card(C, 1.0)
check('Low Poly, 1st click: its settings', rp.armed() == 'LOWPOLY' and 'faces' in {i.prop for i in c[2]})
S.mch_lowpoly.faces = 400
click('LOWPOLY')
act = C.active_object
check('... 2nd click: a low-poly copy', act is not b and len(act.data.polygons) < 1200, (act.name,
                                                                                       len(act.data.polygons)))

# HP Keep on a fresh cut piece
a, b = pieces()
select(a)
click('HP_KEEP')
c = rp.card(C, 1.0)
check('HP Keep, 1st click: Bake High Poly settings', rp.armed() == 'HP_KEEP' and 'bk_target' in {i.prop for i in c[2]})
names0 = {o.name for o in bpy.data.objects}
nf0 = len(a.data.polygons)
click('HP_KEEP')
new = [o for o in bpy.data.objects if o.name not in names0]
hp = new[0] if new else a
check('... 2nd click: the high poly made (Bevels = Keep)', S.mch_zb.bk_bevels == 'KEEP'
      and len(hp.evaluated_get(C.evaluated_depsgraph_get()).data.polygons) > nf0, ([o.name for o in new], nf0))
summary()
