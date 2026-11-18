"""Real window 0.24.223: the Press Cut stamp picker is a card of our own - it stays when the mouse leaves it, a
REAL click on a stamp picks it and closes the card, the X closes it without a pick; a number bar's value popup is ready
to type at once (REAL keys)."""
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
    from mecha_lab import top_bar, float_card
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
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=32, radius=1.0)
        a.spaces.active.show_region_ui = False
        bpy.ops.mch.bar_tool(tool='PRESS')
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 1.5
    yield from wait_draws(3)

    def bar():
        with C.temp_override(window=w, area=a, region=r):
            kk_ = ui_factor(C, r)       # (0.24.226: the top LASSO bar + the tool's box at the bottom)
            from mecha_lab import bottom_row
            return [i for i in top_bar.items(C, r.width, r.height, kk_) if i.enabled] + bottom_row.items(C, r.width, r.height, kk_)

    def card():
        with C.temp_override(window=w, area=a, region=r):
            return float_card.items(C, r.width, r.height, ui_factor(C, r))

    def stamp_cell():
        return next((i for i in bar() if i.action and i.action[0] == 'op' and i.action[1] == 'mch.press_shape_grid'), None)
    shot('01_press_bar.png')
    it = stamp_cell()
    if it is not None:
        yield from press(it)
    yield from wait_draws(3)
    tiles = [i for i in card() if i.kind == 'mtile']
    res['B1'] = float_card.is_open() and len(tiles) >= 13
    log('B1 REAL click on the stamp cell: card open', float_card.is_open(), '| tiles', len(tiles))
    shot('02_card_open.png')
    # the mouse leaves the card (far corner, then the middle of the view below it): it stays
    xdo('mousemove', int(r.x + 60), int(w.height - (r.y + 60)))
    yield 1.0
    xdo('mousemove', int(r.x + r.width - 80), int(w.height - (r.y + r.height - 300)))
    yield 1.5
    yield from wait_draws(2)
    res['B2'] = float_card.is_open()
    log('B2 the mouse left the card: still open', float_card.is_open())
    shot('03_mouse_away.png')
    shape0 = S.mch_press.shape
    tiles = [i for i in card() if i.kind == 'mtile' and not i.on]
    t = tiles[5] if len(tiles) > 5 else None
    if t is not None:
        yield from press(t)
    yield from wait_draws(3)
    res['B3'] = t is not None and S.mch_press.shape == t.action[2]['stem'] != shape0 and not float_card.is_open()
    log('B3 REAL click on a stamp:', shape0, '->', S.mch_press.shape, '| wanted', t.action[2]['stem'] if t else None,
        '| card open', float_card.is_open())
    shot('04_picked_closed.png')
    it = stamp_cell()
    if it is not None:
        yield from press(it)
    yield from wait_draws(3)
    shape1 = S.mch_press.shape
    x_btn = next((i for i in card() if i.kind == 'pbtn'), None)
    opened = float_card.is_open()
    if x_btn is not None:
        yield from press(x_btn)
    yield from wait_draws(3)
    res['B4'] = opened and x_btn is not None and not float_card.is_open() and S.mch_press.shape == shape1
    log('B4 the X: opened', opened, '| open after', float_card.is_open(), '| shape kept', S.mch_press.shape == shape1)
    # a number bar: a click (no drag) -> the value popup, the number ready to type at once
    num = next((i for i in bar() if i.kind == 'mini' and i.action and i.action[0] == 'number' and i.enabled), None)
    v0 = getattr(num.data, num.prop) if num is not None else None
    if num is not None:
        yield from press(num)
    yield 1.0
    shot('05_value_popup.png')
    xdo('key', 'ctrl+a')
    yield 0.3
    xdo('type', '--delay', '80', '37')
    yield 0.5
    xdo('key', 'Return')
    yield 1.0
    v1 = getattr(num.data, num.prop) if num is not None else None
    res['B5'] = num is not None and v1 != v0 and abs(float(v1) - 37.0) < 1e-3
    log('B5 value popup typed at once:', num.label if num else None, num.prop if num else None, v0, '->', v1)
    shot('06_value_typed.png')
    xdo('mousemove', int(r.x + 60), int(w.height - (r.y + 60)))
    yield 1.0
    # a colour swatch: the picker is a dialog - shown, and still there after the mouse went far away (screenshots)
    from mecha_lab.mecha_menu import Item
    world = S.world or bpy.data.worlds.new('World')
    S.world = world
    xdo('mousemove', int(r.x + r.width / 2), int(w.height - (r.y + r.height / 2)))
    yield 0.6
    with C.temp_override(window=w, area=a, region=r):
        ui_bars.open_value(C, Item('swatch', 0, 0, 10, 10, 'Colour', '', False, True, ('color',), world, 'color'))
    yield 1.5
    shot('07_colour_dialog.png')
    xdo('mousemove', int(r.x + 80), int(w.height - (r.y + r.height - 80)))
    yield 1.5
    shot('08_colour_dialog_mouse_away.png')
    xdo('key', 'Escape')
    yield 0.8
    names = {'B1': 'a REAL click on the stamp cell opens our own card with the stamp pictures',
             'B2': 'the card stays when the mouse leaves it',
             'B3': 'a REAL click on a stamp picks it and closes the card',
             'B4': 'the X closes the card, nothing picked',
             'B5': 'a number bar\'s value popup takes typing at once (REAL keys, no extra click)'}
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
