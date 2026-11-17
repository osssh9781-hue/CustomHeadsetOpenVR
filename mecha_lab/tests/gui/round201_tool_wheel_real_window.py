"""Real window 0.24.201: the Tool Wheel - V by a REAL key at the mouse, the three ways to pick: tap + clicks, hold + hover
+ let go, hold + flick + let go."""
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
    from mecha_lab import radial_menu as rm, tool_state as ts
    res = {}
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool='CUT')
    yield 1.5
    cxs, cys = int(r.x + r.width * 0.45), int(w.height - (r.y + r.height * 0.5))

    def scr(it):
        return int(r.x + it['x']), int(w.height - (r.y + it['y']))

    def items():
        st = rm.STATE
        return rm.layout(st['cx'], st['cy'], st['k'], st['groups'], st['open'])

    def bubble(kind, ident):
        return next((i for i in items() if i['kind'] == kind and (i['id'] == ident)), None)
    # 1. click: tap V, click a group, click a tool
    xdo('mousemove', cxs, cys)
    yield 0.6
    xdo('key', 'v')
    yield 1.0
    opened = rm.is_open()
    n_groups = len([i for i in items() if i['kind'] == 'group']) if opened else 0
    log('tap V: wheel open', opened, 'groups', n_groups)
    res['1 a REAL tap on V: the wheel opens at the mouse with the eleven groups and stays'] = opened and n_groups == 11
    shot('1_wheel.png')
    if opened:
        xdo('mousemove', *scr(bubble('group', 'Cloth')))
        yield 0.8
        xdo('click', 1)
        yield 0.8
        tools = [i['id'] for i in items() if i['kind'] == 'tool']
        log('REAL click on Cloth: tools shown', tools)
        shot('2_cloth_open.png')
        b = bubble('tool', 'CDRAPE')
        if b:
            xdo('mousemove', *scr(b))
            yield 0.8
            xdo('click', 1)
            yield 1.2
    log('after the REAL click on Cloth Drape: tool', ts.effective_tool(C), 'wheel open', rm.is_open())
    res['2 click: a REAL click on the Cloth group, then on Cloth Drape - that tool is on, the wheel gone'] = (
        ts.effective_tool(C) == 'CDRAPE' and not rm.is_open())
    # 2. hover: hold V, onto Cut, onto Split, let go
    xdo('mousemove', cxs, cys)
    yield 0.6
    xdo('keydown', 'v')
    yield 0.6
    if rm.is_open():
        xdo('mousemove', *scr(bubble('group', 'Cut')))
        yield 0.7
        b = bubble('tool', 'SPLIT')
        if b:
            xdo('mousemove', *scr(b))
            yield 0.7
        shot('3_hover_split.png')
    xdo('keyup', 'v')
    yield 1.2
    log('hold V, onto Cut, onto Split, let go: tool', ts.effective_tool(C), 'wheel open', rm.is_open())
    res['3 hover: V held, the mouse onto Cut then Split, V let go - Split is on'] = (
        ts.effective_tool(C) == 'SPLIT' and not rm.is_open())
    # 3. flick: hold V, a quick move toward Block-out and on outward (not onto a bubble), let go
    xdo('mousemove', cxs, cys)
    yield 0.6
    xdo('keydown', 'v')
    yield 0.5
    want = None
    if rm.is_open():
        g0 = bubble('group', 'Block-out')
        st = rm.STATE
        ang = math.atan2(g0['y'] - st['cy'], g0['x'] - st['cx'])
        for d in (60, 140, 230, 330):
            x, y = st['cx'] + math.cos(ang) * d * st['k'], st['cy'] + math.sin(ang) * d * st['k']
            xdo('mousemove', int(r.x + x), int(w.height - (r.y + y)))
            yield 0.12
        yield 0.4
        want = rm.STATE.get('hover')
    xdo('keyup', 'v')
    yield 1.2
    block = [t[0] for t in dict(rm.groups())['Block-out']]
    log('flick up toward Block-out and past its tools, let go: hover was', want, 'tool', ts.effective_tool(C))
    res['4 flick: V held, a flick toward Block-out and on out, V let go - a Block-out tool is on (the nearest)'] = (
        want is not None and want[0] == 'tool' and ts.effective_tool(C) == want[1] and want[1] in block
        and not rm.is_open())
    # 4. Esc closes, the tool unchanged
    xdo('mousemove', cxs, cys)
    yield 0.5
    xdo('key', 'v')
    yield 0.8
    was = ts.effective_tool(C)
    xdo('key', 'Escape')
    yield 0.8
    res['5 tap V then Esc: closed, the tool as it was'] = not rm.is_open() and ts.effective_tool(C) == was
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
