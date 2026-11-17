"""Real window 0.24.217: the top bar as sections (like the bottom tool menu) in a wide viewport - the 3D view made
the whole window; screenshots of four tools, every fixed cell at one place, a REAL click on a cell in a section."""
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
    import collections
    from mecha_lab import i18n, top_bar
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
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.screen.screen_full_area()                    # the 3D view: the whole window (a wide viewport)
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
        a.spaces.active.show_region_toolbar = False
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')

    def bar():
        with C.temp_override(window=w, area=a, region=r):
            return top_bar.items(C, r.width, r.height, ui_factor(C, r))
    def bar_h(its_):
        cards = [i for i in its_ if i.kind == 'card' and i.icon != 'outer']
        return round(max(c.y + c.h for c in cards) - min(c.y for c in cards))
    FIXED = {}
    for _title, _sources, specs in top_bar.common_slots():
        if isinstance(specs, list):
            for label, kind, _icon, _w, match in specs:
                FIXED[(kind, label)] = match
    where = collections.defaultdict(set)
    heights = {}
    rows_h = {}
    for n, tool in enumerate(('CUT', 'BASE', 'SMART', 'FUR', 'PLATE')):
        with C.temp_override(window=w, area=a, region=r):
            bpy.ops.mch.bar_tool(tool=tool)
        yield 1.5
        yield from wait_draws(3)
        its = bar()
        heights[tool] = bar_h(its)
        top_bar.FORCE_SECTIONS[0] = False
        rows_h[tool] = bar_h(bar())
        top_bar.FORCE_SECTIONS[0] = None
        for i in its:
            key = (i.kind, i.label)
            if key in FIXED and FIXED[key](dict(action=i.action, prop=i.prop)):
                where[key].add((round(i.x, 1), round(i.y, 1), round(i.w, 1)))
        shot(f'0{n + 1}_wide_{tool}.png')
    # Slow Line on (Cut): its Strength / Radius show in a row under the Draw section, nothing moves sideways
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool='CUT')
    yield 1.5
    yield from wait_draws(3)
    before = {(i.kind, i.label): round(i.x, 1) for i in bar() if (i.kind, i.label) in FIXED}
    h_before = bar_h(bar())
    it = next((i for i in bar() if i.kind == 'seg' and i.label == 'Slow Line'), None)
    if it is not None:
        yield from press(it)
    yield 1.0
    yield from wait_draws(3)
    after = {(i.kind, i.label): round(i.x, 1) for i in bar() if (i.kind, i.label) in FIXED}
    h_after = bar_h(bar())
    shot('06_wide_CUT_slow_line.png')
    res['A4'] = bool(S.mch_brush.stab_enable) and ('mini', 'Strength') in after and h_after > h_before \
        and all(after[k_] == v_ for k_, v_ in before.items())
    log('A4 REAL click on Slow Line:', S.mch_brush.stab_enable, '| Strength shown', ('mini', 'Strength') in after,
        '| bar', h_before, '->', h_after, 'px | cells that moved sideways',
        [k_ for k_, v_ in before.items() if after.get(k_) != v_])
    S.mch_brush.stab_enable = False
    moved = {k: v for k, v in where.items() if len(v) != 1}
    its = bar()
    titles_above = [i for i in its if i.kind == 'glabel']
    res['A1'] = not moved and len(where) >= 15
    log('A1 wide viewport', r.width, 'px, interface x%.2f: fixed cells' % ui_factor(C, r), len(where), '| moved', moved, '| bar heights: sections', heights, 'rows', rows_h)
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool='CUT')
    yield 1.5
    yield from wait_draws(3)
    its = bar()
    rc = next((i for i in its if i.kind == 'mini' and i.label == 'Res'), None)
    rt = next((i for i in its if i.kind == 'glabel' and i.label == 'RESOLUTION'), None)
    res['A2'] = rc is not None and rt is not None and rt.y > rc.y
    log('A2 sections: the Resolution title is above its cell', rt is not None and rc is not None and rt.y > rc.y)
    S.mch_cut.targets = 'AUTO'
    it = next((i for i in its if i.kind == 'seg' and i.prop == 'targets' and i.label == 'Active'), None)
    if it is not None:
        yield from press(it)
    yield 0.8
    res['A3'] = it is not None and S.mch_cut.targets == 'ACTIVE'
    log('A3 REAL click on Active (the Target section):', S.mch_cut.targets)
    S.mch_cut.targets = 'AUTO'
    i18n.force(None)
    names = {'A1': 'a wide viewport: every fixed cell at one place for 5 tools',
             'A2': 'the bar is sections: a title above its cells', 'A3': 'a REAL click on a cell in a section lands',
             'A4': 'Slow Line on (REAL click): its numbers show in a row under the section, the bar grows down, no cell moves sideways'}
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
