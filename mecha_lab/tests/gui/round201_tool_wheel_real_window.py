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
        for d in (60, 160, 270, 380):
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
    # 3b. the middle: Select <-> the tool
    from mecha_lab import bottom_bar as bb
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool='CUT')
    yield 1.0
    states = []
    for _n in range(2):
        xdo('mousemove', cxs, cys)
        yield 0.5
        xdo('key', 'v')
        yield 0.9
        if _n == 0:
            shot('4_middle.png')
        xdo('click', 1)
        yield 1.2
        with C.temp_override(window=w, area=a, region=r):
            states.append((bb.in_select(C), bb.tool_live(C), rm.is_open()))
    log('Cut on; tap V + REAL click on the middle, twice: (select, tool on, wheel open) =', states)
    res['4b the middle: a REAL click switches Cut -> Select, again Select -> Cut (the wheel closes each time)'] = (
        states == [(True, False, False), (False, True, False)])
    # 3b2. Alt + right click, with a tool on (Cut) and over the model: tap = it stays, then a click picks
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool='CUT')
    yield 1.0
    xdo('mousemove', cxs, cys)
    yield 0.5
    xdo('keydown', 'alt')
    yield 0.2
    xdo('click', 3)
    yield 0.3
    xdo('keyup', 'alt')
    yield 1.0
    alt_open = rm.is_open()
    alt_tool = None
    if alt_open:
        xdo('mousemove', *scr(bubble('group', 'Cut')))
        yield 0.7
        xdo('click', 1)
        yield 0.6
        b_ = bubble('tool', 'BOOLEAN')
        if b_:
            xdo('mousemove', *scr(b_))
            yield 0.6
            xdo('click', 1)
            yield 1.2
        alt_tool = ts.effective_tool(C)
    # ... held: Alt + right button down, onto Cut -> Press Cut, let go
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool='CUT')
    yield 1.0
    xdo('mousemove', cxs, cys)
    yield 0.5
    xdo('keydown', 'alt')
    yield 0.2
    xdo('mousedown', 3)
    yield 0.6
    held_tool = None
    if rm.is_open():
        xdo('mousemove', *scr(bubble('group', 'Cut')))
        yield 0.7
        b_ = bubble('tool', 'PRESS')
        if b_:
            xdo('mousemove', *scr(b_))
            yield 0.7
    xdo('mouseup', 3)
    yield 0.3
    xdo('keyup', 'alt')
    yield 1.2
    held_tool = ts.effective_tool(C)
    log('Cut on - REAL Alt + right click: wheel', alt_open, '-> clicks pick', alt_tool, '| Alt + right button held, onto Press Cut, let go:', held_tool, 'open', rm.is_open())
    res['4b2 Alt + REAL right click with the Cut tool on: the wheel opens and stays, clicks pick Boolean; held and let go on Press Cut picks it'] = (
        alt_open and alt_tool == 'BOOLEAN' and held_tool == 'PRESS' and not rm.is_open())
    # 3c. a plain left click on empty space (Select on) opens it; a click on the cube does not; a drag does not
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.select_move()
        for o in list(C.scene.objects):
            if o.type == 'MESH':
                bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_cube_add()
        cube = C.active_object
        rv = a.spaces.active.region_3d
        rv.view_location = (0, 0, 0)
        rv.view_distance = 12.0
        bpy.ops.mch.select_move()
    yield 1.5
    ex, ey = int(r.x + r.width * 0.62), int(w.height - (r.y + r.height * 0.36))   # (empty: right of and below the cube, clear of the cards)
    cube_xy = screen_xy((0, 0, 0))
    xdo('mousemove', *cube_xy)
    yield 0.6
    xdo('click', 1)
    yield 1.2
    on_cube = rm.is_open()
    if on_cube:
        xdo('key', 'Escape')
        yield 0.5
    log('empty spot (screen)', ex, ey, 'cube (screen)', cube_xy, 'region', r.x, r.y, r.width, r.height, 'window h', w.height)
    xdo('mousemove', ex, ey)
    yield 0.8
    xdo('click', 1)
    yield 1.5
    opened = rm.is_open()
    cx0 = rm.STATE.get('cx') if opened else None
    shot('5_click_open.png')
    xdo('key', 'Escape')
    yield 0.8
    xdo('mousemove', ex, ey)
    yield 0.4
    xdo('mousedown', 1)
    yield 0.2
    xdo('mousemove', ex + 120, ey - 60)
    yield 0.3
    xdo('mouseup', 1)
    yield 1.0
    on_drag = rm.is_open()
    if on_drag:
        xdo('key', 'Escape')
        yield 0.5
    log('Select on - REAL left click on empty space: wheel', opened, 'at x', cx0, '| on the cube:', on_cube,
        '(selected', [o.name for o in C.selected_objects], ') | a drag:', on_drag)
    res['4c a plain REAL left click (Tool Wheel on Click is off by default since 0.24.206): no wheel on empty space, on the cube, or after a drag'] = (
        not opened and not on_cube and not on_drag)
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
