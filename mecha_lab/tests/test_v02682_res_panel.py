"""0.24.282 / 0.24.283 The bottom row's Resolution settings (user: "해상도 글씨 옆에 세팅 버튼 - 누르면 옆에 세팅 뜨고,
원하는 버튼 누르면 그땐 세팅 조절 가능, 다시 세팅 버튼 눌러서 끄면 버튼 누르면 바로 적용", "컷 툴이랑 스플릿으로 자른 메쉬로",
"라인 컷으로 곡선으로 자른 것도"): on parts made with the Cut tool (a pocket, a hole) + the Split tool (two pieces) and
with a curved Line Cut: Settings off - the buttons run at once (as always); on - a button shows its settings in the
leftmost box, Apply runs it; off again - at once again."""
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


def curved():
    """A block cut with a curved Line Cut (an S stroke across it, one side removed)."""
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    ob = C.active_object
    ob.scale = (1.2, 0.7, 0.4)
    bpy.ops.object.transform_apply(scale=True)
    select(ob)
    cut.depth_mode = 'THROUGH'
    pts = [P(0.1 + 0.18 * math.sin(t / 20 * 2 * math.pi), -0.6 + 1.2 * t / 20) for t in range(21)]
    ce.perform_line(C, 'CUT', [ob], pts, TOP, side_xy=P(0.6, 0.0))
    return ob


def settings(on):
    if rp.settings_on() != on:
        ui_bars.run(C, Item('seg', 0, 0, 1, 1, 'Settings', '', False, True, ('resset',)))


def apply_box(key):
    return ui_bars.run(C, Item('seg', 0, 0, 1, 1, 'Apply', '', True, True, ('resapply', key)))


def click(key):
    """A real click's path: the bottom row's button item through ui_bars.run."""
    return ui_bars.run(C, Item('abtn', 0, 0, 10, 10, key, '', False, True, ('resarm', key)))


parts = pieces()
check('Cut + Split made two pieces', len(parts) == 2, [(o.name, len(o.data.polygons)) for o in parts])

res = next(bs for sec, bs in mm.ACTIONS if sec == 'Resolution')
_w, _h, its = bottom_row._section(C, 'Resolution', res, 1.0)
acts = {i.label: i.action for i in its if i.kind == 'abtn'}
sw = [i for i in its if i.action == ('resset',)]
title = next(i for i in its if i.kind == 'glabel')
check('a Settings switch beside the RESOLUTION title (same row, off)', len(sw) == 1 and not sw[0].on
      and abs((sw[0].y + sw[0].h / 2) - (title.y + title.h / 2)) < 6, [(i.label, i.y) for i in its[:3]])
check('the buttons: Remesh / Quad / Low Poly / HP x3 / Decimate; HP Copy / Clean Materials as before',
      all(acts[lb] == ('resarm', k) for lb, k in rp.KEYS.items()) and acts['HP Copy'][0] == 'mop'
      and acts['Clean Materials'][0] == 'mop', acts)

# Settings off: at once
a, b = parts
select(a)
S.mch_zb.qr_target = 0.6
click('QUAD')
quads = sum(1 for p in a.data.polygons if len(p.vertices) == 4) / max(1, len(a.data.polygons))
check('Settings off: Quad runs at once on the Cut + Split piece (mostly quads, about 600), no box',
      rp.card(C, 1.0) is None and quads > 0.85 and 300 < len(a.data.polygons) < 1200, (len(a.data.polygons), quads))

# Settings on
settings(True)
c = rp.card(C, 1.0)
check('Settings on: the left box says to pick a button', c is not None and rp.armed() is None
      and any('설정' in i.label or 'SETTINGS' in i.label for i in c[2]))
first = bottom_row.boxes(C, 1600, 1000, 1.0)[0][2]
check('... it is the row\'s first (left) box, the switch lit', any(i.action == ('resclose',) for i in first)
      and next(i for i in bottom_row._section(C, 'Resolution', res, 1.0)[2] if i.action == ('resset',)).on)
select(b)
n0 = len(b.data.polygons)
click('QUAD')
c = rp.card(C, 1.0)
props = {i.prop for i in c[2]} if c else set()
check('... Quad: nothing runs, its settings in the box (engine, Target, Hard Edges, Flow, Subdivision), lit',
      rp.armed() == 'QUAD' and len(b.data.polygons) == n0
      and {'mch_res_quad_engine', 'qr_target', 'qr_angle', 'qr_flow', 'qr_subd'} <= props
      and next(i for i in bottom_row._section(C, 'Resolution', res, 1.0)[2] if i.label == 'Quad').on, sorted(props))
click('QUAD')
check('... Quad again: still only the settings', len(b.data.polygons) == n0 and rp.armed() == 'QUAD')
S.mch_zb.qr_subd = 1
apply_box('QUAD')
check('... Apply in the box: runs with them (quads, Subdivision 1), the box stays',
      len(b.data.polygons) > 300 and qf.subdiv_modifier(b) is not None and rp.armed() == 'QUAD')
S.mch_zb.qr_subd = 0
S.mch_res_quad_engine = 'OLD'
c = rp.card(C, 1.0)
check('... engine QuadriFlow / Patch: its own settings', {'method', 'faces', 'edge_angle'} <= {i.prop for i in c[2]})
S.mch_res_quad_engine = 'NEW'
click('DECIMATE')
check('... another button: the box shows its settings', rp.armed() == 'DECIMATE'
      and {'decimate', 'dec_even'} <= {i.prop for i in rp.card(C, 1.0)[2]})
settings(False)
check('Settings off again: the tool\'s box back', rp.card(C, 1.0) is None and rp.armed() is None
      and not any(i.action == ('resclose',) for i in bottom_row.boxes(C, 1600, 1000, 1.0)[0][2]))


def tris(o):
    o.data.calc_loop_triangles()
    return len(o.data.loop_triangles)


# a curved Line Cut piece: every button at once
ob = curved()
xs = [(ob.matrix_world @ v.co).x for v in ob.data.vertices]
check('curved Line Cut: one side gone, the cut follows the S (many points on it)',
      max(xs) < 0.35 and len(ob.data.vertices) >= 24, (round(max(xs), 3), len(ob.data.vertices)))
select(ob)
S.mch_zb.qr_target = 0.8
click('QUAD')
from mecha_lab import core_geometry as cg2
quads = sum(1 for p in ob.data.polygons if len(p.vertices) == 4) / max(1, len(ob.data.polygons))
check('... Quad at once: mostly quads, closed (no open / broken edges)', quads > 0.85
      and cg2.non_manifold_edge_count(ob.data) == 0, (len(ob.data.polygons), round(quads, 2)))
ob = curved()
select(ob)
bpy.ops.object.modifier_add(type='SUBSURF')
ob.modifiers[-1].levels = 3
bpy.ops.object.modifier_apply(modifier=ob.modifiers[-1].name)
t0 = tris(ob)
S.mch_zb.decimate = 30
click('DECIMATE')
check('... Decimate at once: about 30 % of the triangles', 0.2 * t0 < tris(ob) < 0.4 * t0, (t0, tris(ob)))
ob = curved()
select(ob)
S.mch_settings.remesh_by, S.mch_settings.target_points = 'POINTS', 4000
click('REMESH')
check('... Remesh at once: about 4,000 points', 2000 < len(ob.data.vertices) < 8000, len(ob.data.vertices))
click('LOWPOLY')
check('... Low Poly at once: a low-poly copy', C.active_object is not ob, C.active_object.name)

# Cut + Split pieces: the rest at once
a, b = pieces()
select(a)
names0 = {o.name for o in bpy.data.objects}
click('HP_KEEP')
new = [o for o in bpy.data.objects if o.name not in names0]
check('Cut + Split piece: HP Keep at once (a high poly, Bevels Keep)', S.mch_zb.bk_bevels == 'KEEP' and new,
      [o.name for o in new])
summary()
