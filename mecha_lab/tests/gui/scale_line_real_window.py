"""Real window (0.24.151, user: "그리블 라인을 크리쳐 탭도 만들어 줘, 비늘 전용이나 디테일 전용으로"): Scale Line on the
high-poly test human (0.94 M faces) by REAL clicks and REAL drags (xdotool).

  1. the Scale Line tool (Creature); a REAL click on Scale Parts: the scale shapes in its list, the scale settings
  2. a REAL drag across the chest: a Scale Line - overlapping scales in staggered rows on the body
  3. a REAL click on Detail Parts, a REAL drag down the belly: a line of details on the body
  4. shots: Solid with the wireframe, Rendered (Cycles)
"""
import os
import subprocess
import sys
import time

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'addon'))
import mecha_lab  # noqa: E402
from mecha_lab import side_panel as sp, ui_bars  # noqa: E402
from mecha_lab.ui_gpu import ui_factor  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402
import math  # noqa: E402
import numpy as np  # noqa: E402

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


DRAWS = {'n': 0, 'last': 0.0}


def _count_draw():
    DRAWS['n'] += 1
    DRAWS['last'] = time.perf_counter()


def wait_draws(n, limit=120.0):
    """Until ``n`` more redraws of the 3D view happened (the panel shows what sp.items says)."""
    w, a, r = view3d()
    n0 = DRAWS['n']
    t0 = time.perf_counter()
    while DRAWS['n'] < n0 + n and time.perf_counter() - t0 < limit:
        a.tag_redraw()
        yield 0.1


def view_change_draw(a, rv, angle):
    """Seconds from a view change to the end of the redraw it causes."""
    n0 = DRAWS['n']
    t0 = time.perf_counter()
    rv.view_rotation = Euler((1.0, 0.0, angle)).to_quaternion()
    a.tag_redraw()
    while DRAWS['n'] == n0 and time.perf_counter() - t0 < 120:
        yield 0.01
    return DRAWS['last'] - t0


def press(it):
    w, a, r = view3d()
    x, y = int(r.x + it.x + it.w / 2), int(w.height - (r.y + it.y + it.h / 2))
    xdo('mousemove', x, y)
    yield 0.6
    xdo('click', 1)
    yield 1.0


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


def drag(points, mods=()):
    """A real drag through the 3D points (screen positions now)."""
    xy = [screen_xy(p) for p in points]
    xdo('mousemove', *xy[0])
    yield 0.4
    for m in mods:
        xdo('keydown', m)
    yield 0.2
    xdo('mousedown', 1)
    yield 0.4
    for x, y in xy[1:]:
        xdo('mousemove', x, y)
        yield 0.08
    yield 0.3
    xdo('mouseup', 1)
    yield 0.3
    for m in mods:
        xdo('keyup', m)
    yield 1.5


def flow():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools_dev'))
    import make_test_human as mth
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
    from mecha_lab import greeble_line as gl, tool_state as ts
    res = {}
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        body = mth.build(5, clear=False)
        for o in S.objects:
            o.select_set(False)
        body.select_set(True)
        C.view_layer.objects.active = body
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((1.45, 0.0, 0.25)).to_quaternion()
        rv.view_location = (0.0, 0.0, 1.25)
        rv.view_distance = 1.1
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True                  # (the wireframe always shown with a result)
        bpy.ops.mch.bar_tool(tool='CGREEBLE')
        bpy.ops.mch.side_page(page='TOOL')
        tool_now = ts.effective_tool(C)
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 3.0
    crea = gl.settings(S, 'CREATURE')
    it = yield from scrolled_item('Scale Parts')
    if it is None:
        log('ERROR no Scale Parts cell')
        bpy.ops.wm.quit_blender()
        return
    yield from press(it)
    yield 1.5
    scales = gl.picked(crea)
    log('tool', tool_now, 'scale parts', [o.name for o in scales], 'gap', round(crea.gap, 2), 'rows', crea.rows,
        'stagger', crea.stagger)
    res['1 Scale Line on; a REAL click on Scale Parts: five scales in its list, the scale settings'] = (
        tool_now == 'CGREEBLE' and len(scales) == 5 and crea.rows == 3 and crea.stagger and crea.gap < 0)
    caster = gl._caster(C, body)

    def on_body(x, z):
        h = caster.ray_cast((x, -1.0, z), (0.0, 1.0, 0.0))
        return h[0] if h is not None else None

    def drag(path):
        pts3 = [p for p in (on_body(x, z) for x, z in path) if p is not None]
        xy = [screen_xy(p) for p in pts3]
        before = {o.name for o in S.objects if gl.is_line(o)}
        xdo('mousemove', *xy[0])
        yield 0.4
        xdo('mousedown', 1)
        for x, y in xy[1:]:
            xdo('mousemove', x, y)
            yield 0.06
        yield 0.2
        xdo('mouseup', 1)
        yield 1.0
        return [o for o in S.objects if gl.is_line(o) and o.name not in before]
    new = yield from drag([(x, 1.33) for x in np.linspace(-0.11, 0.11, 14)])
    ln = new[0] if new else None
    n = len(ln.data.vertices) if ln else 0
    log('scale line', ln and ln.name, 'kind', ln and ln.mch_greeble_line.kind, 'scales', n)
    res['2 a REAL drag across the chest: a Scale Line of overlapping scales on the body'] = (
        ln is not None and ln.mch_greeble_line.kind == 'CREATURE' and ln.parent == body and n >= 15)
    shot('1_scales_wire.png')
    it = yield from scrolled_item('Detail Parts')
    if it is not None:
        yield from press(it)
    yield 1.5
    det = gl.picked(crea)
    new = yield from drag([(0.0, z) for z in np.linspace(1.24, 1.06, 10)])
    ln2 = new[0] if new else None
    n2 = len(ln2.data.vertices) if ln2 else 0
    worst = max(((caster.nearest(ln2.matrix_world @ v.co)[0] - ln2.matrix_world @ v.co).length
                 for v in ln2.data.vertices), default=1.0) if ln2 else 1.0
    log('detail parts', [o.name for o in det], 'detail line', ln2 and ln2.name, n2, 'worst', round(worst * 1000, 1), 'mm')
    res['3 a REAL click on Detail Parts, a REAL drag down the belly: details on the body'] = (
        len(det) == 5 and det[0].name.startswith('Detail') and ln2 is not None and n2 >= 2 and worst < 0.01)
    yield 1.0
    shot('2_details_wire.png')
    S.render.engine = 'CYCLES'
    S.cycles.preview_samples = 6
    sp3.shading.type = 'RENDERED'
    yield 40.0
    shot('3_rendered_wire.png')
    bpy.types.SpaceView3D.draw_handler_remove(handle, 'WINDOW')
    for k_, v in res.items():
        log(('PASS ' if v else 'FAIL ') + k_)
    log(f'{sum(res.values())}/{len(res)} passed')
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
