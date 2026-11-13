"""Real window (0.24.152, user: "이 버전 깔고 나서 계속 화면이 지지직거리면서 움직여"): does the 3D view keep changing while
nothing moves?  A still scene (a monkey, the background on), Material Preview and Rendered (Cycles): the view region's
pixels compared between screenshots a second apart, the viewport compositor Always (what the Compositor background sets)
against Disabled; and the redraw count while still.
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
from mathutils import Euler  # noqa: E402

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


def region_px(path, r):
    import numpy as np
    img = bpy.data.images.load(path)
    try:
        W, H = img.size
        px = np.empty(W * H * 4, np.float32)
        img.pixels.foreach_get(px)
        return px.reshape(H, W, 4)[r.y:r.y + r.height, r.x:r.x + r.width, :3].copy()
    finally:
        bpy.data.images.remove(img)


def flow():
    import numpy as np
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
    from mecha_lab import bg_color as bgc
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_monkey_add(size=1.6, location=(0, 0, 0.9))
        bpy.ops.object.shade_smooth()
        S.world = bpy.data.worlds.new('My World')
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((1.3, 0.0, 0.45)).to_quaternion()
        rv.view_location = (0.0, 0.0, 0.7)
        rv.view_distance = 6.0
        sp3.show_region_ui = False
        bpy.ops.mch.bar_tool(tool='SELECT')
    st = bgc.settings(S)
    st.color = (0.3, 0.35, 0.45)
    st.method = 'COMP'
    bgc.apply(S)
    S.render.engine = 'CYCLES'
    S.cycles.preview_samples = 16
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    log('viewport compositor', sp3.shading.use_compositor, 'film transparent', S.render.film_transparent)
    xdo('mousemove', 20, 20)                             # (the mouse out of the 3D view: nothing hovered)
    for shading in ('RENDERED',):
        for comp in ('ALWAYS', 'DISABLED'):
            sp3.shading.type = shading
            sp3.shading.use_compositor = comp
            yield 60.0                                    # (settled: samples done)
            n0 = DRAWS['n']
            p1 = region_px(shot(f'{shading}_{comp}_1.png'), r)
            yield 1.5
            p2 = region_px(shot(f'{shading}_{comp}_2.png'), r)
            yield 1.5
            p3 = region_px(shot(f'{shading}_{comp}_3.png'), r)
            yield 5.0
            p4 = region_px(shot(f'{shading}_{comp}_4.png'), r)
            n1 = DRAWS['n']
            log(f'   ... 5 s later {float(np.mean(np.abs(p3 - p4) > 2 / 255)) * 100:.2f} %')
            d12 = float(np.mean(np.abs(p1 - p2) > 2 / 255))
            d23 = float(np.mean(np.abs(p2 - p3) > 2 / 255))
            log(f'{shading} compositor {comp}: pixels changing while still {d12 * 100:.2f} % / {d23 * 100:.2f} %, '
                f'redraws in 3 s {n1 - n0}')
    bpy.types.SpaceView3D.draw_handler_remove(handle, 'WINDOW')
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
