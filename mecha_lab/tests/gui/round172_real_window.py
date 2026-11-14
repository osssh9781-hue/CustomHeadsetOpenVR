"""Real window (0.24.172, user: "깃털 탭도 만들어 줘 ... 내가 그으면 그 라인 따라서 주욱 생기는 느낌, 길이랑 폭은 내가
조정, 끝부분으로 갈수록 길어지게 하는 거랑 시작 부분이 길어지게 하는 거"; "퍼 에드온에도 피부에 넣을 수 있는 페더 탭, 비늘
탭"; "지금 말한 거 싹 다 엔터 누르면 어플라이"), by REAL clicks, drags and keys (xdotool), a front view, wireframe on:

  1. the Feather Line tool, a REAL click on the feather "Primary", a REAL drag along the body - feathers along it
  2. a REAL drag on the slider "Longer to End" - the feathers longer toward the line's end
  3. a REAL Enter - the line applied (real feathers)
  4. the Fur tool, a REAL click on its "Feathers" tab, a REAL lasso on the body - feathers lying down it there
  5. a REAL Enter - applied
  6. a REAL click on the "Scales" tab, a REAL lasso, a REAL click on "Dragon" - dragon scales there; a REAL Enter
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


def drag_path(points):
    xy = [screen_xy(p) for p in points]
    xdo('mousemove', *xy[0])
    yield 0.5
    xdo('mousedown', 1)
    yield 0.4
    for x, y in xy[1:]:
        xdo('mousemove', x, y)
        yield 0.1
    yield 0.3
    xdo('mouseup', 1)
    yield 2.0


def enter():
    w, a, r = view3d()
    xdo('mousemove', int(r.x + r.width * 0.5), int(w.height - (r.y + r.height * 0.12)))
    yield 0.5
    xdo('key', 'Return')
    yield 2.5


def flow():
    import numpy as np
    from mecha_lab import greeble_line as gl, skin_cover as sc
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
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=96, ring_count=48, location=(0, 0, 0))
        body = C.active_object
        body.name = 'Bird'
        body.scale = (1.6, 0.8, 1.0)
        bpy.ops.object.transform_apply(scale=True)
        bpy.ops.object.shade_smooth()
        for o in C.selected_objects:
            o.select_set(False)
        C.view_layer.objects.active = None
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((math.radians(90), 0.0, 0.0)).to_quaternion()
        rv.view_location = (0.0, 0.0, 0.0)
        rv.view_distance = 6.5
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True
        sp3.shading.type = 'SOLID'
        bpy.ops.mch.bar_tool(tool='FGREEBLE')
        bpy.ops.mch.side_page(page='TOOL')
    yield 2.0
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 1.0
    # 1: Primary, a drag along the body's front (left to right, a little above the middle)
    it = yield from scrolled_item('Primary')
    if it is not None:
        yield from press(it)
    st = gl.settings(S, 'FEATHER')
    picked = [o.name for o in gl.picked(st)]
    path = []
    for i in range(16):
        t = -0.85 + i * 0.11
        x = 1.6 * math.sin(t)
        y = -0.8 * math.cos(t) * math.cos(0.3)
        path.append((x, y * 1.01, 0.3))
    yield from drag_path(path)
    lines = [o for o in S.objects if gl.is_line(o)]
    ln = lines[0] if lines else None
    n = len(ln.data.vertices) if ln else 0
    log('1 Primary cell', it is not None, 'picked', picked, '- lines', len(lines), 'feathers', n,
        'kind', ln and ln.mch_greeble_line.kind)
    res['1 the Feather Line tool: a REAL click on "Primary", a REAL drag along the body - feathers along it'] = (
        it is not None and picked and 'Primary' in picked[0] and ln is not None and n >= 5
        and ln.mch_greeble_line.kind == 'FEATHER')
    shot('1_feather_line.png')
    # 2: Longer to End
    def scales_of(o):
        s_ = np.empty(len(o.data.vertices) * 3, np.float32)
        o.data.attributes['mch_scale'].data.foreach_get('vector', s_)
        return s_.reshape(-1, 3)
    s0 = scales_of(ln) if ln else None
    it = yield from scrolled_item('Longer to End')
    if it is not None:
        yield from slider_drag(it, 0.2, 14)
    yield from wait_draws(2)
    s1 = scales_of(ln) if ln else None
    ge = ln.mch_greeble_line.grow_end if ln else 0
    log('2 Longer to End cell', it is not None, '- grow_end', round(ge, 2), '- first/last length',
        s1 is not None and (round(float(s1[0, 0]), 3), round(float(s1[-1, 0]), 3)))
    res['2 a REAL drag on "Longer to End": the feathers longer toward the line\'s end'] = (
        it is not None and ge > 0.2 and s1 is not None and s1[-1, 0] > s1[0, 0] * (1 + ge * 0.6))
    shot('2_longer_to_end.png')
    # 3: Enter
    yield from enter()
    log('3 after Enter: still a line', ln and gl.is_line(ln), '- name', ln and ln.name, '- faces', ln and len(ln.data.polygons))
    res['3 a REAL Enter: the feather line applied (real feathers)'] = (
        ln is not None and not gl.is_line(ln) and len(ln.data.polygons) > 100 and ln.name.startswith('Feathers'))
    # 4: Fur tool, Feathers tab, a lasso
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool='FUR')
        bpy.ops.mch.side_page(page='TOOL')
        for o in C.selected_objects:
            o.select_set(False)
        C.view_layer.objects.active = None
        ln.hide_set(True)
    S.mch_brush.shape = 'STROKE'
    yield 1.5
    it = yield from scrolled_item('Feathers')
    if it is not None:
        yield from press(it)
    grow = S.mch_cover.grow
    yield from real_outline(ring_at(Vector((-0.6, -0.7, -0.25)), 85, 75, wob=0.08))
    yield 2.0
    cov = next((o for o in S.objects if sc.is_cover(o)), None)
    nf = len(cov.data.vertices) if cov else 0
    log('4 Feathers cell', it is not None, 'grow', grow, '- cover', cov and cov.name, nf, 'feathers')
    res['4 the Fur tool: a REAL click on "Feathers", a REAL lasso - feathers lying down the body there'] = (
        it is not None and grow == 'FEATHERS' and cov is not None and cov.parent == body and nf > 10)
    shot('3_fur_feathers.png')
    yield from enter()
    log('5 after Enter: cover', cov and sc.is_cover(cov), '- faces', cov and len(cov.data.polygons))
    res['5 a REAL Enter: the feathers applied'] = cov is not None and not sc.is_cover(cov) and len(cov.data.polygons) > 1000
    # 6: Scales tab, a lasso, Dragon, Enter
    it = yield from scrolled_item('Scales')
    if it is not None:
        yield from press(it)
    grow = S.mch_cover.grow
    yield from real_outline(ring_at(Vector((0.65, -0.7, -0.2)), 85, 80, wob=0.06))
    yield 2.0
    cov2 = next((o for o in S.objects if sc.is_cover(o)), None)
    it2 = yield from scrolled_item('Dragon')
    if it2 is not None:
        yield from press(it2)
    yield from wait_draws(2)
    ng = cov2.modifiers['MCH Greeble'].node_group if cov2 else None
    shapes = [n_.inputs['Object'].default_value.name for n_ in ng.nodes if n_.bl_idname == 'GeometryNodeObjectInfo'] if ng else []
    ns = len(cov2.data.vertices) if cov2 else 0
    log('6 Scales cell', it is not None, 'grow', grow, '- cover', cov2 and cov2.name, ns, '- Dragon cell', it2 is not None,
        'shapes', shapes)
    shot('4_fur_scales.png')
    ok6 = (it is not None and grow == 'SCALES' and cov2 is not None and cov2.mch_cover.grow == 'SCALES' and ns > 10
           and it2 is not None and shapes == ['Scale Dragon'])
    yield from enter()
    log('6 after Enter: cover', cov2 and sc.is_cover(cov2), '- faces', cov2 and len(cov2.data.polygons))
    res['6 a REAL click on "Scales", a REAL lasso, a REAL click on "Dragon": dragon scales there; a REAL Enter applies'] = (
        ok6 and not sc.is_cover(cov2) and len(cov2.data.polygons) > 1000)
    with C.temp_override(window=w, area=a, region=r):
        ln.hide_set(False)
    yield from wait_draws(2)
    shot('5_all_applied.png')
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
