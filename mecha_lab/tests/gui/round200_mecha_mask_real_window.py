"""Real window 0.24.200: Paint Mask in the MECHA LAB screen - a REAL click turns it on (Sculpt Mode underneath, the
Mecha screen kept), a REAL drag paints the mask, a REAL click on Drape Mask makes the cloth from it."""
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
    S = C.scene
    sp3 = a.spaces.active
    from mecha_lab import cloth_drape as cd, mecha_mask as mm, tool_state as ts, ui_bars as ub, zb_sculpt as zs
    res = {}
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=64, radius=1.0)
        body = C.active_object
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((1.25, 0.0, 0.5)).to_quaternion()
        rv.view_location = (0.0, 0.0, 0.0)
        rv.view_distance = 6.0
        sp3.show_region_ui = False
        bpy.ops.mch.bar_tool(tool='CDRAPE')
        bpy.ops.mch.side_page(page='TOOL')
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 3.0

    def labels():
        w_, a_, r_ = view3d()
        with C.temp_override(window=w_, area=a_, region=r_):
            return {getattr(i, 'label', '') for i in ub.all_items(C)}
    before = labels()
    it = yield from scrolled_item('Paint Mask')
    log('tool', ts.effective_tool(C), 'Paint Mask cell', it is not None)
    if it is not None:
        yield from press(it)
    yield 2.0
    after = labels()
    brush = zs.brush(C)
    log('after a REAL click on Paint Mask: mode', C.mode, 'on', mm.on(C), 'brush', brush and brush.name,
        'ZBrush screen', zs.on(C), 'MECHA lit / tool tiles kept:', 'Cut' in after, 'Paint Mask (on)' in after)
    shelf_on = bool(getattr(sp3, 'show_region_asset_shelf', False))
    log('brush shelf shown while painting:', shelf_on)
    res['1b Blender\'s brush shelf is hidden while painting (it lay over the tool menu)'] = not shelf_on
    res['1 a REAL click on Paint Mask: Sculpt Mode underneath, the Mask brush, the MECHA LAB screen kept (no ZBrush screen)'] = (
        C.mode == 'SCULPT' and mm.on(C) and not zs.on(C) and 'Cut' in before and 'Cut' in after)
    shot('1_painting_screen.png')
    yield from drag([(x, -0.2 - 0.9 * abs(x) * 0, z) for x, z in zip(np.linspace(-0.35, 0.35, 16), np.linspace(0.5, 0.2, 16))]
                    and [(float(x) * 0.5 - 0.2, -0.85, 0.35 + 0.1 * float(x)) for x in np.linspace(-1, 1, 16)])
    yield 1.0
    yield from drag([(float(x) * 0.5 - 0.2, -0.9, 0.1 + 0.1 * float(x)) for x in np.linspace(-1, 1, 16)])
    yield 1.0
    shot('2_painted.png')
    it = yield from scrolled_item('Drape Mask (masked faces lift off as the cloth)')
    if it is not None:
        yield from press(it)
    yield 3.0
    n_mask = int((mm.values(body) > 0.5).sum())
    ob = bpy.data.objects.get(cd.SIM.get('ob', '')) if cd.sim_active() else None
    log('after a REAL click on Drape Mask: mode', C.mode, 'painting', mm.on(C), 'masked points', n_mask, 'cloth',
        ob and ob.name, ob and len(ob.data.vertices))
    log('brush shelf back after:', bool(getattr(sp3, 'show_region_asset_shelf', False)))
    res['3b ... and back after'] = bool(getattr(sp3, 'show_region_asset_shelf', False))
    res['2 REAL drags on the ball painted a mask'] = n_mask > 30
    res['3 a REAL click on Drape Mask: the painting ended (Object Mode) and the cloth of the masked part is there'] = (
        C.mode == 'OBJECT' and not mm.on(C) and ob is not None and len(ob.data.vertices) > 10)
    shot('3_cloth.png')
    xdo('mousemove', *screen_xy((0.0, 0.0, 0.0)))
    yield 0.5
    xdo('key', 'Escape')
    yield 1.5
    bpy.types.SpaceView3D.draw_handler_remove(handle, 'WINDOW')
    for k_, v_ in res.items():
        log(('PASS ' if v_ else 'FAIL ') + k_)
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
