"""Real window 0.24.215: every tool's window in big titled sections - screenshots of six tools (Korean), and the
cells still answer the REAL mouse: a section title folds, a slider inside a made section drags (Fur: Density), a
button inside one clicks (Greeble: Chamfer stamp)."""
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
    from mecha_lab import i18n
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
    res = {}
    i18n.force('KO')
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=32, radius=1.0)
        a.spaces.active.show_region_ui = False
    sp.FOLDED.clear()
    sp.OPENED.clear()
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')

    def panel():
        with C.temp_override(window=w, area=a, region=r):
            return sp.items(C, r.width, r.height, ui_factor(C, r))
    counts = {}
    for n, tool in enumerate(('FUR', 'SPIKE', 'GREEBLE', 'MUSCLE', 'PLATE', 'CUT')):
        with C.temp_override(window=w, area=a, region=r):
            bpy.ops.mch.bar_tool(tool=tool)
            bpy.ops.mch.side_page(page='TOOL')
        C.window_manager.mch_side_scroll = 0.0
        yield 1.5
        yield from wait_draws(3)
        counts[tool] = len([i for i in panel() if i.kind == 'shead' and str(i.icon).startswith('big:')])
        shot(f'0{n + 1}_{tool}.png')
    res['A1'] = all(v >= 1 for v in counts.values())
    log('A1 big section titles on screen (first screenful):', counts)
    # Fur: a title folds; a slider inside a made section drags
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool='FUR')
    yield 1.5
    it = yield from scrolled_item('STRANDS')
    if it is not None:
        yield from press(it)
    yield from wait_draws(3)
    res['A2'] = it is not None and 'FUR:Strands' in sp.FOLDED
    log('A2 REAL click on the Strands title: folded', 'FUR:Strands' in sp.FOLDED)
    it = next((i for i in panel() if i.kind == 'shead' and i.label == 'STRANDS'), None)
    if it is not None:
        yield from press(it)
    yield from wait_draws(3)
    fur = S.mch_fur
    v0 = fur.density
    it = yield from scrolled_item('Density')
    if it is not None:
        x, y = int(r.x + it.x + it.w * 0.3), int(w.height - (r.y + it.y + it.h / 2))
        xdo('mousemove', x, y)
        yield 0.5
        xdo('mousedown', 1)
        yield 0.3
        for k_ in range(1, 9):
            xdo('mousemove', x + 6 * k_, y)
            yield 0.1
        xdo('mouseup', 1)
        yield 0.8
    res['A3'] = it is not None and fur.density != v0 and 'FUR:Strands' not in sp.FOLDED
    log('A3 opened again; REAL drag on Density (in Strands):', v0, '->', fur.density)
    fur.density = v0
    # Greeble: a button inside a made section
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool='GREEBLE')
    yield 1.5
    g = S.mch_greeble
    p0 = getattr(g, 'stamp_profile', None)
    it = yield from scrolled_item('Dome')
    if it is not None:
        yield from press(it)
    yield 0.8
    p1 = getattr(g, 'stamp_profile', None)
    res['A4'] = it is not None and p1 != p0
    log('A4 REAL click on Dome (Greeble, in its Stamp section):', p0, '->', p1)
    i18n.force(None)
    names = {'A1': 'six tools: big coloured section titles on screen', 'A2': 'a REAL click on a made section\'s title folds it',
             'A3': 'a slider inside a made section answers a REAL drag (Fur: Density)',
             'A4': 'a button inside a made section answers a REAL click (Greeble: Dome stamp)'}
    n = 0
    for k in sorted(names):
        ok = bool(res.get(k))
        n += ok
        log('PASS' if ok else 'FAIL', k, names[k])
    log(f'{n}/{len(names)} passed')
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
