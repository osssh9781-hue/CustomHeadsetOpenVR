"""Real window (0.24.180), by REAL clicks, drags and keys (xdotool), wireframe on - hair in a sculpted shape:

  1. Amount (user: "머리카락 양도 조절 가능하게"): a REAL drag on the Amount slider in the window - more strands at once,
     nothing traced again
  2. Comb (user: "머리카락 빗는 것도 만들어 주고"): a REAL click on Comb, a REAL drag across the lock - the strands turn
     that way; Alt + a REAL drag back over it - back toward the shape; a REAL Ctrl + Z - that stroke off; a REAL
     Enter - done
  3. Gravity (user: "그래비티나 그런 게 왜 메쉬 머리카락에는 안 되는겨"): a REAL drag on the Gravity slider - the tips
     come down, none into the head
  4. a colour preset (user: "원래 기존에 있던 헤어 세팅 다 쓸 수 있으면"): a REAL click on Blonde - its colour
  5. Boolean Bevel Edge Loop (user: "엣지 루프 기능도 만들어 주라 - 베벨 말이지"): Shift + a REAL click by a box's top
     front edge, on the top - the top's four edges cut; Shift + Alt + a REAL click - all off
  6. Geo Sculpt Chamfer: a REAL click on "Edge Loop" in the window, a REAL click by the edge - the top's four edges
  7. Plate Detail 4 (user: "디테일 플레이트 4에 프리셋 저장도 만들어 줘"): a REAL click on Save Preset, a REAL Enter -
     saved (a scratch config folder, not the user's); a value changed, a REAL click on the saved one - back
  8. Face Pop Split (user: "페이스 팝은 별개의 메쉬로 분리되어야지" - "그냥 페이스 팝도 유지하고 스플릿 버전도"): a REAL
     click on "Split", a REAL click on a rock's face - a piece of its own (the rock not touched); a REAL drag over two
     more - into the same piece; Alt + a REAL click - one off
  9. Bend any part (user: "내가 만든 오브젝트를 나중에 벤드로 휠 수 있는 거"): a bar selected, a REAL click on "Bend" in
     the Layers window's Live Stack, a REAL drag on "Bend Up / Down" - bent
 10. (user: "눈 끈 거만 한 번에 카메라 꺼지게, 다시 켜는 것도"): a part's eye off, a REAL click on "No Render" (the hidden ones) -
     out of renders; a REAL click on "Render Again" - back
"""
import math
import os
import subprocess
import sys
import time

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'addon'))
import mecha_lab  # noqa: E402
from mecha_lab import side_panel as sp  # noqa: E402
from mecha_lab.ui_gpu import ui_factor  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402

OUT = sys.argv[-1]
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, 'log.txt'), 'w')


def log(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    LOG.write(s + '\n')
    LOG.flush()


mecha_lab.register()
C = bpy.context


def xdo(*args):
    subprocess.run(['xdotool', *map(str, args)], check=False)


def wins():
    r = subprocess.run(['xdotool', 'search', '--name', 'Blender'], capture_output=True, text=True)
    return r.stdout.split()


def focus(wid=None):
    for w_ in ([wid] if wid else wins()):
        subprocess.run(['xdotool', 'windowfocus', '--sync', w_], check=False)


def view3d():
    for w in C.window_manager.windows:
        for a in w.screen.areas:
            if a.type == 'VIEW_3D':
                return w, a, next(r for r in a.regions if r.type == 'WINDOW')
    return None, None, None


def shot(name):
    path = os.path.join(OUT, name)
    os.system(f'import -window root "{path}"')
    log('shot', name, os.path.exists(path))
    return path


DRAWS = {'n': 0}


def _count_draw():
    DRAWS['n'] += 1


def wait_draws(n, limit=120.0):
    w, a, r = view3d()
    n0 = DRAWS['n']
    t0 = time.perf_counter()
    while DRAWS['n'] < n0 + n and time.perf_counter() - t0 < limit:
        a.tag_redraw()
        yield 0.1


def press(it):
    w, a, r = view3d()
    x, y = int(r.x + it.x + it.w / 2), int(w.height - (r.y + it.y + it.h / 2))
    xdo('mousemove', x, y)
    yield 0.6
    xdo('click', 1)
    yield 1.5


def panel_item(label):
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        its = sp.items(C, r.width, r.height, ui_factor(C, r))
    return next((i for i in its if getattr(i, 'label', '') == label and i.clickable()), None)


def scrolled_item(label):
    """The panel scrolled until the cell ``label`` is in its window; the cell (after two redraws), or None."""
    w, a, r = view3d()
    C.window_manager.mch_side_scroll = 0.0
    yield from wait_draws(2)
    for _i in range(40):
        it = panel_item(label)
        if it is not None:
            yield from wait_draws(2)
            return panel_item(label)
        with C.temp_override(window=w, area=a, region=r):
            sp.scroll_by(C, r.width, r.height, ui_factor(C, r), 120)
        yield from wait_draws(1)
    return None


def screen_xy(p):
    from bpy_extras import view3d_utils
    w, a, r = view3d()
    c = view3d_utils.location_3d_to_region_2d(r, a.spaces.active.region_3d, Vector(p))
    return int(r.x + c.x), int(w.height - (r.y + c.y))


def real_outline(pts, mods=()):
    xdo('mousemove', *pts[0])
    yield 0.4
    for m in mods:
        xdo('keydown', m)
    yield 0.2
    xdo('mousedown', 1)
    yield 0.3
    for x, y in pts[1:] + [pts[0]]:
        xdo('mousemove', x, y)
        yield 0.04
    yield 0.3
    xdo('mouseup', 1)
    yield 0.3
    for m in mods:
        xdo('keyup', m)
    yield 2.5


def ring_at(p, rx_px, ry_px, n=48, wob=0.0):
    c = screen_xy(p)
    return [(int(c[0] + rx_px * math.cos(2 * math.pi * i / n) * (1 + wob * math.sin(3 * 2 * math.pi * i / n))),
             int(c[1] - ry_px * math.sin(2 * math.pi * i / n))) for i in range(n)]


def evaluated(ob):
    import numpy as np
    dg = C.evaluated_depsgraph_get()
    me = ob.evaluated_get(dg).data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    out = {'co': co.reshape(-1, 3), 'faces': len(me.polygons)}
    for nm in ('mch_rd', 'mch_rtop', 'mch_rough'):
        at = me.attributes.get(nm)
        a_ = np.empty(len(at.data), np.float32)
        at.data.foreach_get('value', a_)
        out[nm] = a_
    return out


def slider_drag(it, frac0, dx, steps=12):
    w, a, r = view3d()
    x, y = int(r.x + it.x + it.w * frac0), int(w.height - (r.y + it.y + it.h / 2))
    xdo('mousemove', x, y)
    yield 0.5
    xdo('mousedown', 1)
    yield 0.3
    for i in range(1, steps + 1):
        xdo('mousemove', x + i * dx, y)
        yield 0.06
    yield 0.3
    xdo('mouseup', 1)
    yield 2.5


def drag_world(a, b, mods=()):
    xa, xb = screen_xy(a), screen_xy(b)
    xdo('mousemove', *xa)
    yield 0.4
    for m in mods:
        xdo('keydown', m)
    yield 0.2
    xdo('mousedown', 1)
    yield 0.3
    for i in range(1, 16):
        xdo('mousemove', int(xa[0] + (xb[0] - xa[0]) * i / 15), int(xa[1] + (xb[1] - xa[1]) * i / 15))
        yield 0.05
    yield 0.3
    xdo('mouseup', 1)
    yield 0.4
    for m in mods:
        xdo('keyup', m)
    yield 1.5


def to_x(w, r, x, y):
    return int(r.x + x), int(w.height - (r.y + y))


def layer_items():
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        return lp.items(C, r.width, r.height, ui_factor(C, r))


def lfind(pred):
    return next((i for i in layer_items() if pred(i)), None)


def lclick(it, mods=()):
    w, a, r = view3d()
    x, y = to_x(w, r, it.x + it.w / 2, it.y + it.h / 2)
    xdo('mousemove', x, y)
    yield 0.4
    for m in mods:
        xdo('keydown', m)
    yield 0.2
    xdo('click', 1)
    yield 0.4
    for m in mods:
        xdo('keyup', m)
    yield 1.2


def lbutton(row_name, label_start):
    row = lfind(lambda i: i.kind == 'lrow' and i.label == row_name)
    if row is None:
        return None
    return lfind(lambda i: i.kind == 'pmin' and i.label.startswith(label_start) and abs(i.y - row.y) < 3)


def drag_path(points):
    xy = [screen_xy(p) for p in points]
    xdo('mousemove', *xy[0])
    yield 0.5
    xdo('mousedown', 1)
    yield 0.4
    for x, y in xy[1:]:
        xdo('mousemove', x, y)
        yield 0.08
    yield 0.3
    xdo('mouseup', 1)
    yield 2.0


def key_over_view(key):
    w, a, r = view3d()
    xdo('mousemove', int(r.x + r.width * 0.5), int(w.height - (r.y + r.height * 0.12)))
    yield 0.5
    xdo('key', key)
    yield 3.0


def set_tool(tool):
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool=tool)
        bpy.ops.mch.side_page(page='TOOL')
        for o in C.selected_objects:
            o.select_set(False)
        C.view_layer.objects.active = None




def flow():
    import numpy as np
    import bmesh
    from mecha_lab import hair_shape as hs
    from mathutils.bvhtree import BVHTree
    w, a, r = view3d()
    focus()
    xdo('mousemove', 30, 540)
    yield 0.3
    xdo('key', 'Escape')
    yield 0.5
    with C.temp_override(window=w, area=a, region=r):
        ws = next((x for x in bpy.data.workspaces if x.name.startswith('MECHA LAB')), None)
        if ws is None:
            bpy.ops.mch.workspace_open()
            ws = next((x for x in bpy.data.workspaces if x.name.startswith('MECHA LAB')), None)
        w.workspace = ws
    yield 2.0
    w, a, r = view3d()
    S = C.scene
    sp3 = a.spaces.active
    res = {}

    def view(rot, loc, dist):
        rv = sp3.region_3d
        rv.view_perspective = 'ORTHO'
        rv.view_rotation = Euler(rot).to_quaternion()
        rv.view_location = loc
        rv.view_distance = dist

    # the head and a lock (sculpted as its own mesh), the hair made in it
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=48, ring_count=24)
        head = C.active_object
        head.name = 'Head'
        bm = bmesh.new()
        path = [Vector((0.0, 0.0, 0.92)) + Vector((0.6 * t, 0.0, 0.35 * math.sin(math.pi * t) - 1.1 * t * t))
                for t in np.linspace(0, 1, 40)]
        rings = []
        for i, c in enumerate(path):
            tan = (path[min(i + 1, 39)] - path[max(i - 1, 0)]).normalized()
            u = tan.orthogonal().normalized()
            v = tan.cross(u)
            rr = 0.16 - 0.1 * i / 39
            rings.append([bm.verts.new(c + (u * math.cos(t) + v * math.sin(t)) * rr)
                          for t in np.linspace(0, 2 * math.pi, 16, endpoint=False)])
        for a_, b_ in zip(rings[:-1], rings[1:]):
            for k in range(16):
                bm.faces.new((a_[k], a_[(k + 1) % 16], b_[(k + 1) % 16], b_[k]))
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        me = bpy.data.meshes.new('Lock')
        bm.to_mesh(me)
        bm.free()
        lock = bpy.data.objects.new('Lock', me)
        S.collection.objects.link(lock)
        for o in C.selected_objects:
            o.select_set(False)
        lock.select_set(True)
        C.view_layer.objects.active = lock
        S.mch_hshape.count = 2000
        hair, _msg = hs.make(C, lock)
        view((math.radians(90), 0.0, 0.0), (0.4, 0.0, 0.5), 3.6)
    sp3.show_region_ui = False
    sp3.overlay.show_wireframes = True
    sp3.shading.type = 'SOLID'
    S.mch_cover.grow = 'FUR'
    set_tool('FUR')
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    with C.temp_override(window=w, area=a, region=r):
        hair.select_set(True)
        C.view_layer.objects.active = hair
    yield 2.0
    p = hair.mch_hshape

    def tips():
        seg = p.segments
        P = np.empty(len(hair.data.points) * 3, np.float32)
        hair.data.attributes['position'].data.foreach_get('vector', P)
        M = np.array(hair.matrix_world)
        return (P.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]).reshape(-1, seg, 3)

    # 1 Amount
    traced = hs._CACHE[hair.name]['strands']
    n0 = len(hair.data.curves)
    it = yield from scrolled_item('Amount')
    if it is not None:
        yield from slider_drag(it, 0.3, int(it.w * 0.04), steps=10)
    yield 2.0
    n1 = len(hair.data.curves)
    same = hs._CACHE.get(hair.name, {}).get('strands') is traced
    log('1 amount', n0, '->', n1, 'p.count', p.count, 'traced again', not same)
    res['1 Amount: a REAL drag on its slider - more strands at once, nothing traced again'] = (
        n1 > n0 and n1 == p.count and same)
    shot('1_amount.png')
    p.count = 2000
    hs.rebuild(hair)
    yield from wait_draws(2)
    # 2 Comb
    W0 = tips()
    it = yield from scrolled_item('Comb')
    if it is not None:
        yield from press(it)
    yield 1.0
    on = hs._COMB['op'] is not None
    mid = tuple(path[22])
    a3, b3 = Vector(mid) + Vector((-0.15, 0.0, 0.0)), Vector(mid) + Vector((0.55, 0.0, 0.25))
    yield from drag_world(a3, b3)
    shot('2_comb.png')
    W1 = tips()
    n_strokes = len(hs.combs_of(hair))
    dx1 = float(np.mean(W1[:, -1, 0] - W0[:, -1, 0]))
    dz1 = float(np.mean(W1[:, -1, 2] - W0[:, -1, 2]))
    yield from drag_world(a3, b3, mods=('alt',))
    W2 = tips()
    back = float(np.mean(np.linalg.norm(W2[:, -1] - W0[:, -1], axis=1)))
    moved = float(np.mean(np.linalg.norm(W1[:, -1] - W0[:, -1], axis=1)))
    n2 = len(hs.combs_of(hair))
    w_, a_, r_ = view3d()
    xdo('mousemove', int(r_.x + r_.width * 0.5), int(w_.height - (r_.y + r_.height * 0.2)))
    yield 0.4
    xdo('key', 'ctrl+z')
    yield 2.0
    n3 = len(hs.combs_of(hair))
    W3 = tips()
    redo = float(np.abs(W3 - W1).max())
    xdo('key', 'Return')
    yield 1.5
    off = hs._COMB['op'] is None
    log('2 comb on', on, 'strokes', n_strokes, n2, n3, 'tips dx', round(dx1, 3), 'dz', round(dz1, 3), 'moved',
        round(moved, 3), 'alt back to', round(back, 3), 'ctrl+z -> as after the first', round(redo, 4), 'ended', off)
    res['2 Comb: a REAL click on Comb, a REAL drag - the strands turn that way; Alt + a REAL drag - back toward the '
        'shape; a REAL Ctrl + Z - that stroke off; a REAL Enter - done'] = (
        on and n_strokes == 1 and dx1 > 0.05 and n2 == 2 and back < moved * 0.8 and n3 == 1 and redo < 1e-3 and off)
    shot('2_comb_done.png')
    # 3 Gravity
    bvh = BVHTree.FromPolygons([tuple(v.co) for v in head.data.vertices], [tuple(f.vertices) for f in head.data.polygons])

    def in_head(W):
        n = 0
        for q in W.reshape(-1, 3)[::5]:
            loc, nrm, _i, _d = bvh.find_nearest(Vector(q))
            n += (Vector(q) - loc).dot(nrm) < -0.01
        return n / len(W.reshape(-1, 3)[::5])

    Wg0 = tips()
    it = yield from scrolled_item('Gravity')
    if it is not None:
        yield from slider_drag(it, 0.05, int(it.w * 0.07), steps=10)
    yield 2.5
    Wg1 = tips()
    dz = float(np.median(Wg1[:, -1, 2] - Wg0[:, -1, 2]))
    log('3 gravity', round(p.gravity, 3), 'tips dz', round(dz, 3), 'in head', round(in_head(Wg0), 4), '->',
        round(in_head(Wg1), 4))
    res['3 Gravity: a REAL drag on its slider - the tips come down, none into the head'] = (
        p.gravity > 0.2 and dz < -0.05 and in_head(Wg1) <= in_head(Wg0) + 0.005)
    shot('3_gravity.png')
    # 4 a colour preset
    it = yield from scrolled_item('Blonde')
    if it is not None:
        yield from press(it)
    yield 1.0
    from mecha_lab import creature_hair as ch
    blonde = next(c for c in ch.COLOUR_PRESETS if c[0] == 'BLONDE')
    col = np.empty(len(hair.data.points) * 4, np.float32)
    hair.data.attributes['mch_fur_col'].data.foreach_get('color', col)
    ok4 = np.allclose(tuple(p.root_color), blonde[2], atol=1e-3) and np.allclose(col[:3], blonde[2], atol=1e-3)
    log('4 colour', tuple(round(x, 3) for x in p.root_color), ok4)
    res['4 a colour preset: a REAL click on Blonde - its colour'] = bool(ok4)
    shot('4_blonde.png')
    # 5 Boolean Bevel: Edge Loop by Shift + click
    from mecha_lab import bool_bevel as bb, geo_sculpt as gs, my_presets as mp, plate_detail as pd
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_cube_add(size=2.0)
        box = C.active_object
        box.name = 'Box'
        for o in C.selected_objects:
            o.select_set(False)
        view((math.radians(62), 0.0, math.radians(-28)), (0.0, 0.0, 0.0), 6.5)
    bpy.context.scene.mch_bool_bevel.method = 'CUT'     # (0.24.221 the tool starts on Move Points: this checks the Cut)
    S.mch_bool_bevel.profile, S.mch_bool_bevel.width, S.mch_bool_bevel.edge_loop = 'CHAMFER', 0.2, False
    set_tool('BBEVEL')
    yield 2.0

    def cutd(ob, pts):
        me = ob.data
        bv = BVHTree.FromPolygons([tuple(v.co) for v in me.vertices], [tuple(f.vertices) for f in me.polygons])
        return [round(bv.find_nearest(Vector(q))[3] * math.sqrt(2), 3) for q in pts]

    tops = [(0, -1, 1), (0, 1, 1), (-1, 0, 1), (1, 0, 1)]
    xdo('mousemove', *screen_xy((0.0, -0.92, 1.0)))
    yield from wait_draws(2)
    xdo('mousemove', *screen_xy((0.02, -0.92, 1.0)))
    yield from wait_draws(3)
    log('5 hover: part, run, loop', bb.HOVER.get('part'), bb.HOVER.get('run'), bb.HOVER.get('loop'))
    shot('5_loop_hover.png')
    xdo('keydown', 'shift')
    yield 0.3
    xdo('mousemove', *screen_xy((0.05, -0.92, 1.0)))
    yield from wait_draws(2)
    xdo('mousemove', *screen_xy((0.07, -0.92, 1.0)))
    yield from wait_draws(3)
    hov = (bb.HOVER.get('part'), bb.HOVER.get('run'), len(bb.HOVER.get('loop') or ()))
    log('5 hover with Shift: part, run, loop edges', hov)
    shot('5_loop_shift_hover.png')
    xdo('click', 1)
    yield 0.4
    xdo('keyup', 'shift')
    yield 3.0
    c1 = cutd(box, tops)
    shot('5_loop_cut.png')
    xdo('mousemove', *screen_xy((0.0, -0.95, 0.95)))
    yield from wait_draws(2)
    xdo('keydown', 'shift')
    xdo('keydown', 'alt')
    yield 0.3
    xdo('click', 1)
    yield 0.4
    xdo('keyup', 'alt')
    xdo('keyup', 'shift')
    yield 3.0
    c2 = cutd(box, tops)
    log('5 bool bevel loop', c1, '-> alt', c2)
    res['5 Boolean Bevel Edge Loop: Shift + a REAL click by the top front edge - the top\'s four edges cut; Shift + Alt + '
        'a REAL click - all off'] = all(abs(x - 0.2) < 5e-3 for x in c1) and all(x < 1e-4 for x in c2)
    # 6 Geo Sculpt Chamfer with the Edge Loop switch
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_cube_add(size=2.0)
        gb = C.active_object
        for o in C.selected_objects:
            o.select_set(False)
    S.mch_geo.brush, S.mch_geo.size_px, S.mch_geo.edge_loop = 'CHAMFER', 40, False
    set_tool('GSCULPT')
    yield 2.0
    it = yield from scrolled_item('Edge Loop  (Shift + click)')
    if it is not None:
        yield from press(it)
    on6 = S.mch_geo.edge_loop
    xdo('mousemove', *screen_xy((0.0, -0.9, 1.0)))
    yield from wait_draws(2)
    xdo('click', 1)
    yield 3.0
    wts = gs.safe_widths(gb.data)['CHAMFER']
    n6 = int((wts > 0).sum())
    log('6 geo chamfer loop: switch', on6, 'edges marked', n6)
    res['6 Geo Sculpt Chamfer: a REAL click on "Edge Loop", a REAL click by the edge - the top\'s four edges'] = (
        on6 and n6 == 4)
    shot('6_geo_loop.png')
    # 7 Plate Detail 4: Save Preset
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_plane_add(size=4.0)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.subdivide(number_cuts=30)
        bpy.ops.object.mode_set(mode='OBJECT')
        for o in C.selected_objects:
            o.select_set(False)
        view((math.radians(38), 0.0, math.radians(10)), (0.0, 0.0, 0.0), 4.0)
    S.mch_brush.shape = 'STROKE'
    set_tool('DETAIL4')
    yield 2.0
    yield from real_outline(ring_at(Vector((0.0, 0.0, 0.0)), 260, 160, wob=0.08))
    plate = next((o for o in S.objects if pd.is_detail(o)), None)
    ok7 = False
    if plate is not None:
        with C.temp_override(window=w, area=a, region=r):
            for o in C.selected_objects:
                o.select_set(False)
            plate.select_set(True)
            C.view_layer.objects.active = plate
        plate.mch_pdetail.r_cracks = 0.66
        yield 1.0
        before = set(mp.names(pd.MY_KIND))
        it = yield from scrolled_item('Save Preset')
        if it is not None:
            yield from press(it)
        yield 1.0
        shot('7_save_dialog.png')
        xdo('key', 'Return')
        yield 2.0
        new = sorted(set(mp.names(pd.MY_KIND)) - before)
        plate.mch_pdetail.r_cracks = 0.1
        yield 1.0
        it2 = (yield from scrolled_item(new[0])) if new else None
        if it2 is not None:
            yield from press(it2)
        yield 1.5
        back7 = plate.mch_pdetail.r_cracks
        conf = mp.path()
        log('7 saved', new, 'file', conf, 'cracks back', round(back7, 3))
        ok7 = bool(new) and abs(back7 - 0.66) < 1e-4 and 'gui_clean' in conf
    res['7 Plate Detail 4: a REAL click on Save Preset, a REAL Enter - saved; a REAL click on it - its values back'] = ok7
    shot('7_preset.png')
    # 8 Face Pop: a part of its own
    from mecha_lab import face_pop as fp
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=1.0)
        rock = C.active_object
        rock.name = 'Rock'
        for o in C.selected_objects:
            o.select_set(False)
        C.view_layer.objects.active = None
        view((math.radians(70), 0.0, math.radians(20)), (0.0, 0.0, 0.0), 4.5)
    n_rock = len(rock.data.polygons)
    S.mch_pop.height, S.mch_pop.taper, S.mch_pop.each = 0.15, 0.3, True
    set_tool('FPOP')
    yield 1.0
    it = yield from scrolled_item('Split')               # (the window's switch: In the Part / Split)
    if it is not None:
        yield from press(it)
    log('8 mode', S.mch_pop.mode)
    yield 2.0
    rv = sp3.region_3d
    facing = sorted([q.index for q in rock.data.polygons
                     if (rv.view_rotation @ Vector((0, 0, 1))).dot(q.normal) > 0.75],
                    key=lambda i: rock.data.polygons[i].center.z)
    fxy = lambda f: screen_xy(tuple(rock.matrix_world @ rock.data.polygons[f].center))  # noqa: E731
    f1 = facing[len(facing) // 2]
    xdo('mousemove', *fxy(f1))
    yield from wait_draws(2)
    xdo('click', 1)
    yield 2.0
    pcs = fp.pieces_of(rock)
    m1 = (len(pcs), len(fp.faces_of(pcs[0])) if pcs else 0)
    others = [f for f in facing if f != f1][:2]
    xy0 = fxy(others[0])
    xdo('mousemove', *xy0)
    yield from wait_draws(2)
    xdo('mousedown', 1)
    yield 0.3
    xy1 = fxy(others[1])
    for i in range(1, 13):
        xdo('mousemove', int(xy0[0] + (xy1[0] - xy0[0]) * i / 12), int(xy0[1] + (xy1[1] - xy0[1]) * i / 12))
        yield 0.06
    yield 0.3
    xdo('mouseup', 1)
    yield 2.0
    pcs = fp.pieces_of(rock)
    m2 = (len(pcs), len(fp.faces_of(pcs[0])) if pcs else 0)
    shot('8_face_pop_piece.png')
    xdo('mousemove', *fxy(f1))                         # (on the piece now: the rock's face under it)
    yield from wait_draws(2)
    xdo('keydown', 'alt')
    yield 0.2
    xdo('click', 1)
    yield 0.3
    xdo('keyup', 'alt')
    yield 2.0
    pcs = fp.pieces_of(rock)
    m3 = (len(pcs), len(fp.faces_of(pcs[0])) if pcs else 0)
    same = len(rock.data.polygons) == n_rock and not len(rock.modifiers) and rock.data.attributes.get(fp.ATTR) is None
    log('8 face pop pieces/faces: click', m1, 'drag', m2, 'alt', m3, 'rock untouched', same,
        'piece', pcs[0].name if pcs else None, 'parent', pcs[0].parent.name if pcs and pcs[0].parent else None)
    res['8 Face Pop Split: a REAL click on "Split", a REAL click - a piece of its own (the rock not touched); a REAL drag '
        '- into the same piece; Alt + a REAL click on it - one off'] = (
        S.mch_pop.mode == 'SPLIT' and m1 == (1, 1) and m2[0] == 1 and m2[1] >= 3 and m3 == (1, m2[1] - 1) and same)
    shot('8_face_pop_alt.png')
    # 9 Bend a bar from the Layers window's Live Stack
    from mecha_lab import bend_any, layers_panel, render_hidden
    globals()['lp'] = layers_panel
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=48, y_subdivisions=3, size=1.0)
        bar = C.active_object
        bar.name = 'Bar'
        bar.scale = (3.0, 0.4, 1.0)
        bpy.ops.object.transform_apply(scale=True)
        sm = bar.modifiers.new('S', 'SOLIDIFY')
        sm.thickness = 0.08
        bpy.ops.object.modifier_apply(modifier='S')
        for o in C.selected_objects:
            o.select_set(False)
        bar.select_set(True)
        C.view_layer.objects.active = bar
        view((math.radians(80), 0.0, 0.0), (0.0, 0.0, 0.3), 5.0)
    set_tool('SELECT') if 'SELECT' in __import__('mecha_lab').tool_state.TOOL_BY_ID else None
    with C.temp_override(window=w, area=a, region=r):
        for o in C.selected_objects:
            o.select_set(False)
        bar.select_set(True)
        C.view_layer.objects.active = bar
    yield 2.0
    it = lfind(lambda i: getattr(i, 'label', '') == 'Bend' and i.clickable())
    if it is not None:
        yield from lclick(it)
    yield 1.0
    on9 = bend_any.has(bar)
    it2 = None
    for _k in range(30):                               # (the Layers window scrolled to it: the wheel's way)
        it2 = lfind(lambda i: getattr(i, 'label', '') == 'Bend Up / Down' and i.clickable())
        if it2 is not None:
            break
        with C.temp_override(window=w, area=a, region=r):
            layers_panel.scroll_by(C, r.width, r.height, ui_factor(C, r), 80)
        yield from wait_draws(1)
    yield from wait_draws(2)
    it2 = lfind(lambda i: getattr(i, 'label', '') == 'Bend Up / Down' and i.clickable())
    if it2 is not None:
        yield from slider_drag(it2, 0.5, int(it2.w * 0.05), steps=10)
    yield 1.5
    dg = C.evaluated_depsgraph_get()
    zmax = max(v.co.z for v in bar.evaluated_get(dg).data.vertices)
    log('9 bend: added', on9, 'slider', it2 is not None, 'up', round(math.degrees(bar.mch_bend.up), 1), 'ends z',
        round(zmax, 3))
    res['9 Bend any part: a REAL click on "Bend" in the Live Stack, a REAL drag on "Bend Up / Down" - bent'] = (
        on9 and abs(bar.mch_bend.up) > math.radians(10) and zmax > 0.1)
    shot('9_bend.png')
    C.window_manager.mch_layers_scroll = 0.0
    yield from wait_draws(2)
    # 10 eye-off parts out of renders, and back
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mesh.primitive_cube_add(size=0.5, location=(0.0, 0.0, 1.5))
        cub = C.active_object
        cub.name = 'Hidden Cube'
        cub.hide_set(True)
    yield 1.0
    it = lfind(lambda i: getattr(i, 'label', '').startswith('No Render') and i.clickable())
    if it is not None:
        yield from lclick(it)
    yield 1.0
    off10 = cub.hide_render
    it = lfind(lambda i: getattr(i, 'label', '').startswith('Render Again') and i.clickable())
    if it is not None:
        yield from lclick(it)
    yield 1.0
    back10 = not cub.hide_render
    log('10 hidden: no render', off10, 'render again', back10)
    res['10 a part\'s eye off: a REAL click on "No Render" (the hidden ones) - out of renders; "Render Again" - back'] = (
        off10 and back10)
    bpy.types.SpaceView3D.draw_handler_remove(handle, 'WINDOW')
    for k_, v in res.items():
        log(('PASS ' if v else 'FAIL ') + k_)
    log(f'{sum(bool(v) for v in res.values())}/{len(res)} passed')
    bpy.ops.wm.quit_blender()


lp = None
gen = None


def run():
    global gen
    try:
        if gen is None:
            gen = flow()
        return next(gen)
    except StopIteration:
        return None
    except Exception as ex:
        import traceback
        traceback.print_exc()
        log('ERROR', repr(ex))
        bpy.ops.wm.quit_blender()
        return None


bpy.app.timers.register(run, first_interval=2.0)
