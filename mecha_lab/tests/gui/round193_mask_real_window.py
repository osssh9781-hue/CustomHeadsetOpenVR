"""Real window 0.24.193: Drape Mask - Fall Free by a REAL click, the cloth made by a REAL click, Space drapes: it
comes off the body (user: "옵션 하나 만들어서 그냥 떨어지게 만들어 줘"); the rim without stair steps."""
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
    from mecha_lab import cloth_drape as cd, mesh_io as mio, tool_state as ts
    res = {}
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=64, radius=1.0)
        body = C.active_object
        co = mio.read_co(body.data)
        att = body.data.attributes.new('.sculpt_mask', 'FLOAT', 'POINT')
        u = co @ np.array([0.5, -0.75, 0.43])
        v = co @ np.array([0.6, 0.1, -0.5])
        att.data.foreach_set('value', ((u > 0.35) & (np.abs(v) < 0.45)).astype(np.float32))
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((1.25, 0.0, 0.5)).to_quaternion()
        rv.view_location = (0.0, 0.0, -0.3)
        rv.view_distance = 6.5
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True
        bpy.ops.mch.bar_tool(tool='CDRAPE')
        bpy.ops.mch.side_page(page='TOOL')
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 3.0
    st = cd.settings(C)
    st.mask_points = 100000
    it = yield from scrolled_item('Drape Mask: Fall Free (not held at the rim)')
    log('tool', ts.effective_tool(C), 'Fall Free cell', it is not None, 'before', st.mask_free)
    if it is not None:
        yield from press(it)
    yield 1.0
    res['1 a REAL click on Drape Mask: Fall Free turns it on'] = it is not None and bool(st.mask_free)
    it = yield from scrolled_item('Drape Mask (masked faces lift off as the cloth)')
    if it is not None:
        yield from press(it)
    yield 2.0
    ob = bpy.data.objects.get(cd.SIM.get('ob', ''))
    pins = int(np.count_nonzero(cd.SIM['sess']['cloth'].pin >= 1)) if ob is not None else -1
    lp = max(cd.rim_loops_idx(ob.data), key=len) if ob is not None else []
    p = np.asarray(cd.SIM['surface'])[lp] if len(lp) else np.zeros((3, 3))      # (the laid patch: the drape has begun)
    e1, e2 = p - np.roll(p, 1, 0), np.roll(p, -1, 0) - p
    turn = float(np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', e1, e2) / np.maximum(
        np.linalg.norm(e1, axis=1) * np.linalg.norm(e2, axis=1), 1e-12), -1, 1))).mean())
    z0 = float(np.asarray(cd.SIM['surface'])[:, 2].mean()) if ob is not None else 0.0
    log('cloth', ob and ob.name, 'points', ob and len(ob.data.vertices), 'held', pins, 'rim mean turn', round(turn, 1), 'deg')
    res['2 a REAL click on Drape Mask: the cloth of the masked faces, nothing held, the rim smooth'] = (
        ob is not None and pins == 0 and turn < 12)
    shot('1_laid_wire.png')
    t0 = time.perf_counter()                       # (the click starts the drape: wait for its 60 frames)
    while not cd.SIM.get('done') and cd.sim_active() and time.perf_counter() - t0 < 320:
        yield 2.0
    ob = bpy.data.objects.get(cd.SIM.get('ob', ''))
    z1 = float(mio.read_co(ob.data)[:, 2].mean()) if ob is not None else z0
    log(f'after the drape ({time.perf_counter() - t0:.0f} s): mean height', round(z0, 3), '->', round(z1, 3), 'running', cd.SIM.get('running'), 'done', cd.SIM.get('done'))
    res['3 the drape the click started: the cloth comes off and falls'] = z1 < z0 - 0.2
    shot('2_fallen_wire.png')
    xdo('mousemove', *screen_xy((0.0, 0.0, -0.3)))
    yield 0.5
    xdo('key', 'Return')
    yield 2.0
    kept = [o.name for o in S.objects if o.name.startswith('Cloth Drape')]
    log('after Enter: sim active', cd.sim_active(), 'kept', kept)
    res['4 Enter (REAL key): the cloth kept where it fell'] = not cd.sim_active() and bool(kept)
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
