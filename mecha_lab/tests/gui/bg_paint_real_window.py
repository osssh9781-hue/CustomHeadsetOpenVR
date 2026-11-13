"""Real window (0.24.149): Paint Background, by a REAL click and a REAL brush stroke (xdotool).

  1. a REAL click on Paint Background… (Render page): a canvas behind the model (red, the colour that was there), a
     new window with the Image Editor in Paint mode on it
  2. a REAL drag across the canvas in that window with a blue brush: the canvas painted blue there
  3. the main 3D view (Material Preview, the viewport compositor): blue in the background now (it follows the paint)
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


def blue_share(path, r):
    """The share of the main 3D view's pixels (region ``r``) that are the painted blue."""
    img = bpy.data.images.load(path)
    try:
        import numpy as np
        W, H = img.size
        px = np.empty(W * H * 4, np.float32)
        img.pixels.foreach_get(px)
        c = px.reshape(H, W, 4)[r.y:r.y + r.height, r.x:r.x + r.width, :3] * 255
        return float(np.mean((c[..., 2] > 120) & (c[..., 2] > 1.5 * c[..., 0]) & (c[..., 2] > 1.3 * c[..., 1])))
    finally:
        bpy.data.images.remove(img)


def blue(c):
    return c[2] > 120 and c[2] > 1.5 * c[0] and c[2] > 1.3 * c[1]


def xgeom(wid):
    out = subprocess.run(['xdotool', 'getwindowgeometry', wid], capture_output=True, text=True).stdout
    pos = out.split('Position:')[1].split('(')[0].strip().split(',')
    size = out.split('Geometry:')[1].strip().split('x')
    return int(pos[0]), int(pos[1]), int(size[0]), int(size[1].split()[0])


def flow():
    w, a, r = view3d()
    main_ids = set(wins())
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
    import numpy as np
    res = {}
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_monkey_add(size=1.2, location=(0, 0, 0.9))
        S.world = bpy.data.worlds.new('My World')
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((1.3, 0.0, 0.45)).to_quaternion()
        rv.view_location = (0.0, 0.0, 0.7)
        rv.view_distance = 6.0
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True
        bpy.ops.mch.bar_tool(tool='SELECT')
        bpy.ops.mch.side_page(page='HDRI')
    st = bgc.settings(S)
    st.color = (0.85, 0.12, 0.12)
    st.mode = 'COLOR'
    S.render.resolution_x, S.render.resolution_y = 1920, 1080
    sp3.shading.type = 'MATERIAL'
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 2.0
    it = yield from scrolled_item('Paint Background…')
    yield 3.0
    b0 = blue_share(shot('0_main_before.png'), r)
    if it is None:
        log('ERROR no Paint Background cell')
        bpy.ops.wm.quit_blender()
        return
    nwin0 = len(C.window_manager.windows)
    yield from press(it)
    yield 3.0
    cv = bgc.canvas_image(S)
    pw = [x for x in C.window_manager.windows if x != w]
    pa = next((ar for x in pw for ar in x.screen.areas if ar.type == 'IMAGE_EDITOR'), None)
    log('windows', nwin0, '->', len(C.window_manager.windows), 'canvas', cv and (cv.name, tuple(cv.size)),
        'image editor', pa is not None and (pa.spaces.active.ui_mode, pa.spaces.active.image and pa.spaces.active.image.name))
    res['1 a REAL click on Paint Background…: a canvas behind the model, a new window: Image Editor, Paint, on it'] = (
        cv is not None and bgc.comp_on(S) and len(C.window_manager.windows) == nwin0 + 1 and pa is not None
        and pa.spaces.active.ui_mode == 'PAINT' and pa.spaces.active.image is cv)
    if pa is None:
        bpy.ops.wm.quit_blender()
        return
    yield 1.0
    shot('1_paint_window.png')
    before = np.empty(cv.size[0] * cv.size[1] * 4, np.float32)
    cv.pixels.foreach_get(before)
    ip = S.tool_settings.image_paint
    ups = ip.unified_paint_settings
    ups.use_unified_color = True
    ups.color = (0.05, 0.1, 1.0)
    ups.use_unified_size = True
    ups.size = 40
    if ip.brush is not None:
        ip.brush.color = (0.05, 0.1, 1.0)
    # the paint window on the screen: its X window (the one not there before), the Image Editor's region in it
    new_ids = [i for i in wins() if i not in main_ids]
    pwin = next(x for x in pw if any(ar == pa for ar in x.screen.areas))
    preg = next(rg for rg in pa.regions if rg.type == 'WINDOW')
    gx, gy, gw, gh = xgeom(new_ids[-1]) if new_ids else (pwin.x, 0, pwin.width, pwin.height)
    log('paint window X geometry', (gx, gy, gw, gh), 'blender', (pwin.x, pwin.y, pwin.width, pwin.height),
        'region', (preg.x, preg.y, preg.width, preg.height))
    pts = []
    sh = w.height                                       # (Blender's window y: from the bottom of the screen)
    for u in (0.15, 0.3, 0.45, 0.6, 0.75, 0.9):
        rx, ry = preg.view2d.view_to_region(u, 0.5, clip=False)
        pts.append((int(pwin.x + preg.x + rx), int(sh - (pwin.y + preg.y + ry))))
    log('stroke on screen', pts[0], '->', pts[-1])
    if new_ids:
        focus(new_ids[-1])
    yield 1.0
    xdo('mousemove', *pts[0])
    yield 0.5
    xdo('mousedown', 1)
    yield 0.3
    for x, y in pts[1:]:
        xdo('mousemove', x, y)
        yield 0.15
    xdo('mouseup', 1)
    yield 2.0
    after = np.empty(cv.size[0] * cv.size[1] * 4, np.float32)
    cv.pixels.foreach_get(after)
    a4 = after.reshape(cv.size[1], cv.size[0], 4)
    changed = float(np.mean(np.any(np.abs(after - before).reshape(-1, 4)[:, :3] > 0.05, axis=1)))
    row = a4[cv.size[1] // 2, :, :3]                    # (the stroke along the canvas's middle)
    blue_px = int(np.sum((row[:, 2] > 0.5) & (row[:, 0] < 0.4)))
    log('canvas changed share', round(changed, 4), 'blue pixels on the middle row', blue_px, 'of', cv.size[0])
    res['2 a REAL brush stroke in the paint window: the canvas painted blue along it'] = changed > 0.005 and blue_px > cv.size[0] * 0.3
    shot('2_painted_window.png')
    with C.temp_override(window=pwin):                 # (the paint window closed: the main view seen again)
        bpy.ops.wm.window_close()
    yield 2.0
    w, a, r = view3d()
    a.tag_redraw()
    yield 6.0
    p3 = shot('3_main_view_follows.png')
    b1 = blue_share(p3, r)
    log('main 3D view (Material Preview): blue share before', round(b0, 4), 'after', round(b1, 4),
        'canvas still the background', bgc.canvas_image(S) is cv)
    res['3 the main 3D view: the painted blue in the background (it follows the paint)'] = b1 > b0 + 0.005
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
