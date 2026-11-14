"""Real window (0.24.171, user, Alt+X on a Fur: "Mirror: select a mesh or a collection instance (selected: Curves)" -
"머리카락은 실시간 미러를 원하는 게 아니라, 내가 만들고 어플라이 한 걸 Alt+X 로 미러하고 싶다고"; "머리카락을 내가 보는
뷰포트 방향에서 꺾을 수 있게 밴드 옵션"), by REAL clicks, drags and keys (xdotool), a front view:

  1. the Fur tool, a REAL lasso on the head's right side (screen) - long hanging fur there only
  2. a REAL click on the Fur window's Bend "Left" - the strands bend toward the screen's left
  3. a REAL click on "Apply" - real hair curves
  4. a REAL Alt+X, the mouse leaned left from the bottom centre (over the body), a REAL Enter - a mirrored copy of
     every strand on the other side of the face (not under the chin)
  5. a REAL click on "Apply Modifiers" - the mirror baked: twice the curves, no modifier
  6. Creature Hair: a REAL click on its Bend "Right" - the direction the view's right
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


def strands_of(ob):
    import numpy as np
    dg = C.evaluated_depsgraph_get()
    d = ob.evaluated_get(dg).data
    P = np.empty(len(d.points) * 3, np.float32)
    d.attributes['position'].data.foreach_get('vector', P)
    P = P.reshape(-1, 3)
    off = np.empty(len(d.curves), np.int32)
    d.curves.foreach_get('first_point_index', off)
    sz = np.empty(len(d.curves), np.int32)
    d.curves.foreach_get('points_length', sz)
    M = np.array(ob.matrix_world)
    W = P @ M[:3, :3].T + M[:3, 3]
    return W[off], W[off + sz - 1]


def flow():
    import numpy as np
    from mecha_lab import creature_fur as cf, creature_hair as ch, mirror_tools as mt, ui_bars
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
        bpy.ops.mesh.primitive_cylinder_add(radius=1.1, depth=2.6, location=(0, 0, -2.5))
        C.active_object.name = 'Body'
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=96, ring_count=48, location=(0, 0, 0))
        head = C.active_object
        head.name = 'Head'
        bpy.ops.object.shade_smooth()
        for o in C.selected_objects:
            o.select_set(False)
        C.view_layer.objects.active = None
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((math.radians(90), 0.0, 0.0)).to_quaternion()
        rv.view_location = (0.0, 0.0, -0.9)
        rv.view_distance = 8.0
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True
        sp3.shading.type = 'SOLID'
        st = S.mch_fur
        st.density, st.length, st.gravity, st.lie, st.frizz, st.clump, st.spread = 4000.0, 0.9, 2.5, 0.35, 0.05, 0.3, 0.1
        st.bend = 0.0
        st.root_thick, st.tip_thick = 0.004, 0.001
        S.mch_mirror.space, S.mch_mirror.center = 'WORLD', 'ORIGIN'
        bpy.ops.mch.bar_tool(tool='FUR')
        bpy.ops.mch.side_page(page='TOOL')
    yield 2.0
    S.mch_brush.shape = 'STROKE'
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 1.0
    # 1: a REAL lasso on the head's right side (screen right = +X in this front view)
    yield from real_outline(ring_at(Vector((0.55, -0.75, 0.3)), 40, 55))
    yield 2.0
    fur = next((o for o in S.objects if cf.is_fur(o)), None)
    r0, t0 = strands_of(fur) if fur else (np.zeros((1, 3)), np.zeros((1, 3)))
    log('1 fur', fur and fur.name, len(r0), 'strands, roots x', round(float(r0[:, 0].min()), 2), '..',
        round(float(r0[:, 0].max()), 2))
    res['1 the Fur tool, a REAL lasso on the head\'s right side: fur there only'] = (
        fur is not None and len(r0) > 100 and r0[:, 0].min() > 0.0)
    shot('1_fur.png')
    # 2: Bend "Left"
    it = yield from scrolled_item('Left')
    if it is not None:
        yield from press(it)
    yield from wait_draws(2)
    r1, t1 = strands_of(fur) if fur else (r0, t0)
    bd = tuple(round(v, 3) for v in fur.mch_fur.bend_dir) if fur else None
    dx = float(t1[:, 0].mean() - t0[:, 0].mean())
    log('2 Left cell', it is not None, '- bend', fur and round(math.degrees(fur.mch_fur.bend)), 'dir', bd,
        '- tips moved x', round(dx, 3))
    res['2 a REAL click on Bend "Left": the strands bend toward the screen\'s left (world -X in this view)'] = (
        it is not None and fur is not None and bd is not None and bd[0] < -0.99 and dx < -0.1)
    shot('2_bend_left.png')
    # 3: Apply
    n_live = len(r1)
    it = yield from scrolled_item('Apply')
    if it is not None:
        yield from press(it)
    yield 1.0
    log('3 Apply cell', it is not None, '- still a live fur', fur and cf.is_fur(fur), '- curves in the data',
        fur and len(fur.data.curves))
    res['3 a REAL click on "Apply": real hair curves (not live)'] = (
        it is not None and fur is not None and not cf.is_fur(fur) and len(fur.data.curves) == n_live)
    # 4: Alt+X, lean left from the bottom centre (over the body), Enter
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        for o in C.selected_objects:
            o.select_set(False)
        fur.select_set(True)
        C.view_layer.objects.active = fur
    yield 0.5
    bx, by = int(r.x + r.width / 2), int(w.height - (r.y + r.height * 0.18))
    xdo('mousemove', bx, by)
    yield 0.6
    xdo('key', 'alt+x')
    yield 1.0
    for i in range(1, 16):
        xdo('mousemove', bx - 12 * i, by)
        yield 0.06
    yield 0.8
    shot('3_leaning.png')
    xdo('key', 'Return')
    yield 1.5
    cm = mt.curves_mod(fur)
    r4, t4 = strands_of(fur)
    log('4 after Alt+X + lean left + Enter: mirror', cm is not None, 'axes', cm and tuple(bool(mt._gn_get(cm, k)) for k in 'XYZ'),
        '- strands', len(r4), '- roots x', round(float(r4[:, 0].min()), 2), '..', round(float(r4[:, 0].max()), 2),
        'z', round(float(r4[:, 2].min()), 2), '..', round(float(r4[:, 2].max()), 2))
    res['4 a REAL Alt+X, leaned left, a REAL Enter: a mirrored copy of every strand on the other side of the face'] = (
        cm is not None and len(r4) == 2 * n_live and r4[:, 0].min() < -0.3 and abs(r4[:, 0].min() + r4[:, 0].max()) < 0.02
        and abs(float(r4[:, 2].min()) - float(r1[:, 2].min())) < 0.02)
    shot('4_mirrored.png')
    # 5: Apply Modifiers
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        its = ui_bars.dock_items(C, r.width, r.height, ui_factor(C, r))
    am = next((i for i in its if getattr(i, 'label', '') == 'Apply Modifiers'), None)
    if am is not None:
        yield from press(am)
    yield 1.5
    log('5 Apply Modifiers tile', am is not None, '- modifiers left', [m.name for m in fur.modifiers],
        '- curves in the data', len(fur.data.curves))
    res['5 a REAL click on "Apply Modifiers": the mirror baked (twice the curves, no modifier)'] = (
        am is not None and not fur.modifiers and len(fur.data.curves) == 2 * n_live)
    # 6: Creature Hair Bend "Right"
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool='HAIR')
        bpy.ops.mch.side_page(page='TOOL')
        S.mch_hair.style = 'STRAIGHT'
        S.mch_hair.count = 80
        S.mch_hair.bend = 0.0
        for o in C.selected_objects:
            o.select_set(False)
        head.select_set(True)
        C.view_layer.objects.active = head
    yield 1.0
    yield from real_outline(ring_at(Vector((-0.45, -0.7, 0.45)), 40, 40))
    yield 2.0
    hair = next((o for o in S.objects if o.get(ch.SRC_KEY)), None)
    it = yield from scrolled_item('Right')
    if it is not None:
        yield from press(it)
    yield from wait_draws(2)
    hd = tuple(round(v, 3) for v in hair.mch_hair.bend_dir) if hair else None
    log('6 hair', hair and hair.name, '- Right cell', it is not None, '- bend', hair and round(math.degrees(hair.mch_hair.bend)),
        'dir', hd)
    res['6 Creature Hair: a REAL click on Bend "Right": bent toward the view\'s right (world +X here)'] = (
        it is not None and hair is not None and hd is not None and hd[0] > 0.99 and hair.mch_hair.bend > 0)
    shot('5_hair_bend.png')
    bpy.types.SpaceView3D.draw_handler_remove(handle, 'WINDOW')
    for k_, v in res.items():
        log(('PASS ' if v else 'FAIL ') + k_)
    log(f'{sum(bool(v) for v in res.values())}/{len(res)} passed')
    bpy.ops.wm.quit_blender()


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
