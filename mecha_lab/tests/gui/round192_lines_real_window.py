"""Real window 0.24.192: Scale Line honours Targets (user: "그리블이랑 스케일 둘 다 왜 셀렉트랑 오토 이런 거 다 빠져 있어?") and the
selected line follows the parts list at once ("왜 실시간으로 내가 선택한 메쉬 바뀌는 거 없앴어?")."""
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
    import json
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
    from mecha_lab import greeble_line as gl, tool_state as ts, top_bar as tb
    res = {}
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_cube_add(size=2.0, location=(-1.3, 0, 0))
        A = C.active_object
        A.name = 'Left'
        bpy.ops.mesh.primitive_cube_add(size=2.0, location=(1.3, 0, 0))
        B = C.active_object
        B.name = 'Right'
        for o in S.objects:
            o.select_set(False)
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((0.9, 0.0, 0.0)).to_quaternion()
        rv.view_location = (0.0, 0.0, 0.6)
        rv.view_distance = 8.0
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True
        bpy.ops.mch.bar_tool(tool='CGREEBLE')
        bpy.ops.mch.side_page(page='TOOL')
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 3.0
    crea = gl.settings(S, 'CREATURE')
    it = yield from scrolled_item('Scale Parts')
    if it is not None:
        yield from press(it)
    yield 1.5

    def top_cell(label):
        w_, a_, r_ = view3d()
        with C.temp_override(window=w_, area=a_, region=r_):
            its = tb.items(C, r_.width, r_.height, ui_factor(C, r_))
        return next((i for i in its if getattr(i, 'label', '') == label), None)

    def lines():
        return {o.name for o in S.objects if gl.is_line(o)}

    def stroke(cx):
        before = lines()
        yield from drag([(cx + x, 0.0, 1.0) for x in np.linspace(-0.7, 0.7, 12)])
        return [o for o in S.objects if gl.is_line(o) and o.name not in before]
    cells = [top_cell(n) for n in ('Auto', 'Selected', 'Active')]
    log('tool', ts.effective_tool(C), 'top bar target cells', [c is not None for c in cells], 'targets', S.mch_cut.targets)
    res['1 Scale Line on: the top bar shows Target - Auto / Selected / Active'] = (
        ts.effective_tool(C) == 'CGREEBLE' and all(c is not None for c in cells))
    new = yield from stroke(-1.3)
    l1 = new[0] if new else None
    log('auto: line', l1 and l1.name, 'on', l1 and l1.parent and l1.parent.name)
    res['2 Auto: a REAL drag on the left cube lays a Scale Line on it'] = l1 is not None and l1.parent == A
    shot('1_auto_wire.png')
    for o in S.objects:
        o.select_set(False)
    B.select_set(True)
    C.view_layer.objects.active = B
    yield 0.5
    c = top_cell('Selected')
    if c is not None:
        yield from press(c)
    yield 1.0
    log('after a REAL click on Selected: targets', S.mch_cut.targets, 'selected', [o.name for o in C.selected_objects])
    res['3 a REAL click on Selected in the top bar: Targets = Selected'] = S.mch_cut.targets == 'SELECTED'
    if S.mch_cut.targets != 'SELECTED':
        S.mch_cut.targets = 'SELECTED'
    for o in S.objects:
        o.select_set(False)
    B.select_set(True)
    C.view_layer.objects.active = B
    yield 0.5
    new = yield from stroke(-1.3)
    log('selected = Right, drag on Left: new lines', [o.name for o in new])
    res['4 Selected (the right cube): a REAL drag on the left cube lays nothing'] = not new
    for o in S.objects:
        o.select_set(False)
    B.select_set(True)
    C.view_layer.objects.active = B
    yield 0.5
    new = yield from stroke(1.3)
    l2 = new[0] if new else None
    log('selected = Right, drag on Right: line', l2 and l2.name, 'on', l2 and l2.parent and l2.parent.name,
        'selected now', [o.name for o in C.selected_objects])
    res['5 ... a REAL drag on the right cube lays a Scale Line on it'] = l2 is not None and l2.parent == B
    new = yield from stroke(1.3)
    l3 = new[0] if new else None
    log('again (the new line is the selection now): line', l3 and l3.name, 'on', l3 and l3.parent and l3.parent.name)
    res['6 ... and again with the new line selected: the next stroke still lands on the right cube'] = (
        l3 is not None and l3.parent == B)
    shot('2_selected_wire.png')
    ln = l3 or l2
    if ln is not None:
        with C.temp_override(window=w, area=a, region=r):
            for o in S.objects:
                o.select_set(False)
            ln.select_set(True)
            C.view_layer.objects.active = ln
            n0 = len(json.loads(ln.mch_greeble_line.parts_json))
            bpy.ops.mch.greeble_parts(action='TOGGLE', kind='CREATURE', index=0)
            bpy.ops.mch.greeble_parts(action='TOGGLE', kind='CREATURE', index=1)
        yield 1.5
        n1 = len(json.loads(ln.mch_greeble_line.parts_json))
        log('parts in the selected line', n0, '->', n1, '(two unticked, by the list operator)')
        res['7 two parts unticked in the list (operator call): the selected line has two fewer at once'] = n1 == n0 - 2
        shot('3_live_parts_wire.png')
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
