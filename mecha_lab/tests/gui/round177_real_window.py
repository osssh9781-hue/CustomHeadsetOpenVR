"""Real window (0.24.177), by REAL drags, clicks and keys (xdotool), wireframe on:

  1. Print Cut, Sketch (user: "3d 프린트 메뉴 ... 스케치 모드도 되게 해 줘, 너무 한 번에 그어야 되는디?"): a REAL click on
     "Sketch (draw the line in pieces)", two REAL drags (pieces of the line - nothing cut yet), a REAL Enter - cut
     along both, keys in
  2. Creature Spike (user: "크리쳐 스파이크는 길이 조절 좀 넣어 줘"): a REAL lasso on a ball - spikes; a REAL drag on
     "Length" - longer spikes
  3. Layers (user: "쉬프트 누르고 처음 꺼 마지막 꺼 선택하면 그 영역 선택되게, 컨트롤 누르면 빠지고"): a REAL click on a
     row, Shift + a REAL click on another - every row between; Ctrl + a REAL click - that one out
  4. a folder's eye (user: "그룹 된 거 내가 눈 감게 하면 내부에 메쉬들도 같이 눈 감겨서 하이드 되어야지"): a REAL click -
     its parts hidden, their rows' eyes closed
  5. a group's row REALLY clicked, Flip (user: "왜 그룹은 뒤집기가 안 돼?") - its parts flipped
  6. Edge Molding (user: "엣지 몰딩은 작동이 되긴 하는 거야?" - before: its buttons only said "Tab into Edit Mode", and
     Tab goes to ZBrush in this tab): its tile, a REAL drag along a hull - a molding on it; a REAL drag on "Molding
     Width" - wider; a REAL click on a box - a molding along its edges
  8. Mirror on a Plate Detail 4 (user: "플레이트 디테일4 할 때나 다른 것도 종종 미러가 개무거운데 좀 더 가볍고 빠르게"): a
     REAL lasso - a rough detail; a REAL Alt+X, REAL leans, a REAL Enter - its mirror live, the same as before; each
     lean change timed (to the next viewport draw), against the way it was (a REAL Alt+X, the same leans, a REAL Esc)
  9. Press Cut stamps (user: "프레스 컷에서 스탬프 썸넬 보기가 쉽지가 않삼"): the window shows them as picture tiles;
     a REAL click on the "Arch" tile - the stamp is Arch
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
    from mecha_lab import creature_spike as csp, groups, layers_panel as lp_, print3d as p3
    global lp
    lp = lp_
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
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        for c in list(bpy.data.collections):
            if c.name in {'Parts'}:
                bpy.data.collections.remove(c)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5, radius=0.8, location=(0, 0, 0))
        ball = C.active_object
        ball.name = 'Ball'
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.7, segments=48, ring_count=24, location=(2.4, 0, 0))
        sball = C.active_object
        sball.name = 'Spike Ball'
        rv = sp3.region_3d
        rv.view_perspective = 'ORTHO'
        rv.view_rotation = Euler((math.radians(90), 0.0, 0.0)).to_quaternion()
        rv.view_location = (1.0, 0.0, 0.0)
        rv.view_distance = 7.0
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True
        sp3.shading.type = 'SOLID'
    S.mch_brush.shape = 'STROKE'
    S.mch_brush.sketch_first = False
    S.mch_print.sketch = False
    set_tool('PCUT')
    yield 2.0
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    # 1 Print Cut sketch
    it = yield from scrolled_item('Sketch (draw the line in pieces)')
    if it is not None:
        yield from press(it)
    on = S.mch_print.sketch
    line = [(x, -1.0, 0.1 + 0.2 * math.sin(x * 2.5)) for x in np.linspace(-1.2, 1.2, 40)]
    yield from drag_path(line[:21])
    yield from drag_path(line[20:])
    n_sk = p3.sketch_count()
    cut_before = len([o for o in S.objects if o.get(p3.FROM_KEY) == 'Ball'])
    shot('1_sketch_two_pieces.png')
    yield from key_over_view('Return')
    yield 2.0
    parts = [o for o in S.objects if o.get(p3.FROM_KEY) == 'Ball' and not o.get(p3.PIN_KEY)]
    keys = bool(parts and parts[0].get('mch_print_pins'))
    log('1 Sketch cell', it is not None, 'on', on, 'pieces', n_sk, 'cut before Enter', cut_before, 'after', [o.name for o in parts],
        'keys', keys, 'sketch left', p3.sketch_count())
    res['1 Print Cut: a REAL click on "Sketch", two REAL drags (nothing cut yet), a REAL Enter: cut along both, keys in'] = (
        it is not None and on and n_sk == 2 and cut_before == 0 and len(parts) == 2 and keys and p3.sketch_count() == 0)
    shot('1_sketch_cut.png')
    S.mch_print.sketch = False
    # 2 Creature Spike Length
    set_tool('SPIKE')
    yield 1.5
    yield from real_outline([screen_xy((2.4 + 0.45 * math.cos(t), -1.0, 0.1 + 0.4 * math.sin(t)))
                             for t in np.linspace(0, 2 * math.pi, 36, endpoint=False)])
    yield 2.5
    sp = next((o for o in S.objects if getattr(o, 'mch_spike', None) is not None and o.mch_spike.live), None)

    def tallest(o):
        P = np.array([tuple(o.matrix_world @ v.co) for v in o.data.vertices])
        return float((np.linalg.norm(P - np.array([2.4, 0.0, 0.0]), axis=1) - 0.7).max())
    h0 = tallest(sp) if sp else 0.0
    it2 = yield from scrolled_item('Length')
    if it2 is not None:
        yield from slider_drag(it2, 0.08, 14, 16)
    yield from wait_draws(2)
    h1 = tallest(sp) if sp else 0.0
    log('2 spikes', sp and sp.name, 'Length cell', it2 is not None, 'length', sp and round(sp.mch_spike.length, 2),
        'tallest', round(h0, 3), '->', round(h1, 3))
    res['2 Creature Spike: a REAL lasso, a REAL drag on "Length": longer spikes'] = (
        sp is not None and it2 is not None and sp.mch_spike.length > 1.3 and h1 > h0 * 1.25)
    shot('2_spike_length.png')
    # 3 Layers: Shift range, Ctrl out
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            if o.name.startswith('Spike Ball') or o.get(csp.SRC_KEY):
                bpy.data.objects.remove(o)
        col = bpy.data.collections.new('Parts')
        S.collection.children.link(col)
        cones = []
        for i in range(4):
            bpy.ops.mesh.primitive_cone_add(radius1=0.25, depth=0.5, location=(-1.5 + i, 0, -1.6))
            o = C.active_object
            o.name = f'Part {i + 1}'
            for c in list(o.users_collection):
                c.objects.unlink(o)
            col.objects.link(o)
            cones.append(o)
        for o in C.selected_objects:
            o.select_set(False)
    yield 2.0
    r1 = lfind(lambda i: i.kind == 'lrow' and i.label == 'Part 1')
    r4 = lfind(lambda i: i.kind == 'lrow' and i.label == 'Part 4')
    if r1 is not None:
        yield from lclick(r1)
    r4 = lfind(lambda i: i.kind == 'lrow' and i.label == 'Part 4')
    if r4 is not None:
        yield from lclick(r4, ('shift',))
    sel1 = sorted(o.name for o in C.selected_objects)
    r2 = lfind(lambda i: i.kind == 'lrow' and i.label == 'Part 2')
    if r2 is not None:
        yield from lclick(r2, ('ctrl',))
    sel2 = sorted(o.name for o in C.selected_objects)
    log('3 rows', r1 is not None, r4 is not None, 'shift range', sel1, 'ctrl out', sel2)
    res['3 Layers: a REAL click on a row, Shift + a REAL click on another: every row between; Ctrl + a REAL click: out'] = (
        sel1 == ['Part 1', 'Part 2', 'Part 3', 'Part 4'] and sel2 == ['Part 1', 'Part 3', 'Part 4'])
    shot('3_layers_range.png')
    # 4 the folder's eye
    eye = lbutton('Parts', 'Hide')
    if eye is not None:
        yield from lclick(eye)
    hid = [o.hide_get() for o in cones]
    closed = [lp._hidden(C, o) for o in cones]
    log('4 eye', eye is not None, 'parts hidden', hid, 'rows closed', closed)
    res['4 a folder\'s eye REALLY clicked: its parts hidden, their rows\' eyes closed'] = (
        eye is not None and all(hid) and all(closed))
    shot('4_folder_eye.png')
    eye2 = lbutton('Parts', 'Show')
    if eye2 is not None:
        yield from lclick(eye2)
    # 5 a group: its row clicked, Flip
    with C.temp_override(window=w, area=a, region=r):
        for o in C.selected_objects:
            o.select_set(False)
        cones[0].select_set(True)
        cones[1].select_set(True)
        C.view_layer.objects.active = cones[0]
        bpy.ops.mch.group()
        for o in C.selected_objects:
            o.select_set(False)
    yield 1.5
    g = next((o for o in S.objects if groups.is_group(o)), None)
    xs0 = sorted(round((o.matrix_world @ o.data.vertices[0].co).x, 3) for o in cones[:2])
    grow = lfind(lambda i: i.kind == 'lrow' and g is not None and i.label == g.name)
    if grow is not None:
        yield from lclick(grow)
    picked = g is not None and g.select_get()
    poll = bpy.ops.mch.flip_object.poll()
    with C.temp_override(window=w, area=a, region=r):
        fr = bpy.ops.mch.flip_object(axis='X') if poll else None
    yield 1.0
    xs1 = sorted(round(-(o.matrix_world @ o.data.vertices[0].co).x, 3) for o in cones[:2])
    log('5 group', g and g.name, 'row', grow is not None, 'picked', picked, 'flip poll', poll, fr, 'x', xs0, '->', xs1)
    res['5 a group\'s row REALLY clicked, Flip: its parts flipped across the world'] = (
        grow is not None and picked and poll and fr == {'FINISHED'} and xs0 == xs1)
    shot('5_group_flip.png')
    # 6 Edge Molding in Object Mode
    from mecha_lab import edge_molding as em, tool_state as ts_
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 0))
        hull = C.active_object
        hull.name = 'Hull'
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.subdivide(number_cuts=5)
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(2.6, 0, 0))
        box = C.active_object
        box.name = 'Box'
        rv = sp3.region_3d
        rv.view_perspective = 'ORTHO'
        rv.view_rotation = Euler((math.radians(75), 0.0, math.radians(-25))).to_quaternion()
        rv.view_location = (1.2, 0.0, 0.0)
        rv.view_distance = 7.0
    S.mch_molding.width, S.mch_molding.height = 0.06, 0.03
    set_tool('MOLDING')
    yield 2.0
    tool_id = ts_.native_tool_id(C)
    yield from drag_path([(x, -1.0, 0.35 + 0.15 * math.sin(2.5 * x)) for x in np.linspace(-0.75, 0.75, 30)])
    yield from wait_draws(2)
    m1 = next((o for o in S.objects if o.mch_molding.is_molding and o.parent == hull), None)
    P = np.array([tuple(m1.matrix_world @ v.co) for v in m1.data.vertices]) if m1 else np.zeros((1, 3))
    on_face = m1 is not None and P[:, 1].max() < -1.0 + 1e-3 and P[:, 1].min() > -1.0 - 0.031
    shot('6_molding_line.png')
    z0 = float(np.ptp(P[:, 2]))
    it6 = yield from scrolled_item('Molding Width')
    if it6 is not None:
        yield from slider_drag(it6, 0.1, 8, 12)
    yield from wait_draws(2)
    P2 = np.array([tuple(m1.matrix_world @ v.co) for v in m1.data.vertices]) if m1 else np.zeros((1, 3))
    z1 = float(np.ptp(P2[:, 2]))
    log('6 tool', tool_id, 'molding', m1 and m1.name, 'on the face', on_face, 'width', m1 and round(m1.mch_molding.width, 4),
        'height on face', round(z0, 3), '->', round(z1, 3))
    res['6 Edge Molding: its tile, a REAL drag along a hull - a molding on its face (it follows it); a REAL drag on '
        '"Molding Width" - wider'] = (tool_id == 'mecha.edge_molding' and m1 is not None and on_face
                                      and m1.mch_molding.width > 0.07 and z1 > z0 + 0.01)
    shot('6_molding_width.png')
    for o in C.selected_objects:
        o.select_set(False)
    x_, y_ = screen_xy((2.6, -0.5, 0.15))
    xdo('mousemove', x_, y_)
    yield 0.5
    xdo('click', 1)
    yield 3.0
    m2 = next((o for o in S.objects if o.mch_molding.is_molding and o.parent == box), None)
    n2 = len(__import__('json').loads(m2.mch_molding.chains)) if m2 else 0
    log('7 box click', m2 and m2.name, 'pieces', n2)
    res['7 Edge Molding: a REAL click on a box - a molding along its 12 edges'] = m2 is not None and n2 == 12
    shot('7_molding_box_edges.png')
    # 8 Mirror on a Plate Detail 4
    from mecha_lab import mirror_tools as mt
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32, location=(0, 0, 0))
        hull8 = C.active_object
        hull8.name = 'Hull'
        rv = sp3.region_3d
        rv.view_perspective = 'ORTHO'
        rv.view_rotation = Euler((math.radians(90), 0.0, 0.0)).to_quaternion()
        rv.view_location = (0.0, 0.0, 0.0)
        rv.view_distance = 5.0
    S.mch_mirror.bisect = True
    S.mch_brush.shape = 'STROKE'
    set_tool('DETAIL4')
    yield 2.0
    yield from real_outline([screen_xy((0.45 + 0.35 * math.cos(t), -1.5, 0.1 + 0.3 * math.sin(t)))
                             for t in np.linspace(0, 2 * math.pi, 40, endpoint=False)])
    yield 3.0
    det = next((o for o in S.objects if o.get('mch_pdetail') is not None or getattr(o, 'mch_pdetail', None)
                and o.mch_pdetail.live), None)
    n_det = len(det.evaluated_get(C.evaluated_depsgraph_get()).data.polygons) if det else 0
    set_tool('CUT')
    yield 1.0
    with C.temp_override(window=w, area=a, region=r):
        for o in C.selected_objects:
            o.select_set(False)
        if det is not None:
            det.select_set(True)
            C.view_layer.objects.active = det
    yield 1.0
    gx, gy = int(r.x + r.width / 2), int(w.height - (r.y + r.height * 0.18))     # (the lean's centre)

    def lean_gesture(finish):
        xdo('mousemove', gx + 5, gy - 5)
        yield 0.5
        t0 = time.perf_counter()
        xdo('key', 'alt+x')
        yield from wait_draws(2)
        times = [time.perf_counter() - t0]
        yield 0.5
        t2 = time.perf_counter()
        yield from wait_draws(2)                      # (two draws with nothing changed: what drawing alone costs)
        idle.append(time.perf_counter() - t2)
        for dx, dy in ((0, -160), (-160, 0), (0, -160), (-160, 0)):      # (empty view: up, left, up, left)
            xdo('mousemove', gx + dx, gy + dy)
            t1 = time.perf_counter()
            yield from wait_draws(2)
            times.append(time.perf_counter() - t1)
            yield 0.3
        mid = [o.name for o in S.objects if o.get(mt.PREVIEW_KEY)]
        xdo('key', finish)
        yield 2.0
        return times, mid
    idle = []
    keep_faces = mt.PREVIEW_FACES
    mt.PREVIEW_FACES = 10 ** 12                    # (the way it was)
    t_old, _mid = yield from lean_gesture('Escape')
    mt.PREVIEW_FACES = keep_faces
    gone = det is not None and det.modifiers.get(mt.MOD_NAME) is None
    t_new, mid = yield from lean_gesture('Return')
    shot('8_mirror_detail4.png')
    m8 = det.modifiers.get(mt.MOD_NAME) if det else None
    dg = C.evaluated_depsgraph_get()
    ev = det.evaluated_get(dg) if det else None
    xs = [(det.matrix_world @ v.co).x for v in ev.data.vertices] if ev else [0.0]
    over_old = [max(x - idle[0], 0.0) for x in t_old[1:]]
    over_new = [max(x - idle[1], 0.0) for x in t_new[1:]]
    log('8 detail', det and det.name, n_det, 'old lean', [round(x, 2) for x in t_old], 'idle', [round(x, 2) for x in idle],
        'over the draws: old', [round(x, 2) for x in over_old], 'new', [round(x, 2) for x in over_new],
        'esc gone', gone, 'new lean', [round(x, 2) for x in t_new], 'preview while leaning', mid, 'mirror', m8 and tuple(m8.use_axis),
        m8 and tuple(m8.use_bisect_axis), 'x', round(min(xs), 2), round(max(xs), 2),
        'hidden', det and det.hide_viewport, 'left', [o.name for o in S.objects if o.get(mt.PREVIEW_KEY)])
    res['8 Mirror on a Plate Detail 4: a REAL Alt+X, REAL leans, a REAL Enter - its mirror live (both sides), each '
        'change (over what drawing alone costs) under half the way it was'] = (
        det is not None and n_det > 50_000 and gone and bool(mid) and m8 is not None and min(xs) < -0.2
        and max(xs) > 0.2 and not det.hide_viewport and not [o for o in S.objects if o.get(mt.PREVIEW_KEY)]
        and sum(over_new) < sum(over_old) * 0.5)
    # 9 Press Cut stamp tiles
    set_tool('PRESS')
    yield 2.0
    it9 = yield from scrolled_item('Arch')
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        from mecha_lab import side_panel as side9          # (``sp`` is the spikes object here)
        tiles9 = [i for i in side9.items(C, r.width, r.height, ui_factor(C, r)) if i.kind == 'mtile']
    shot('9_press_tiles_before.png')
    if it9 is not None:
        yield from press(it9)
    picked9 = S.mch_press.shape
    yield from wait_draws(2)
    shot('9_press_tiles.png')
    log('9 tiles in sight', len(tiles9), 'with pictures', sum(1 for i in tiles9 if i.icon.startswith('file:')),
        'Arch tile', it9 is not None, it9 and round(it9.w), 'picked', picked9)
    res['9 Press Cut: the stamps as picture tiles in the window; a REAL click on "Arch" picks it'] = (
        len(tiles9) >= 8 and all(i.icon.startswith('file:') for i in tiles9) and it9 is not None
        and picked9.endswith('M_ARCH'))
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
