"""Real window 0.24.210: (A) the mask in MECHA LAB with the ZBRUSH screen's mouse - drag = mask, Alt = erase, X = mirror,
Ctrl + click on empty = invert, Shift does not touch the mesh; (B) stitches drawn ON the laid cloth - the line shows
while it is drawn, Ctrl+Z takes it back, Space drapes with it."""
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
    from mecha_lab import cloth_drape as cd, mecha_mask as mm, mesh_io as mio, tool_state as ts, zb_sculpt as zs
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
        cd.settings(C).frames = 30
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 3.0

    def masked():
        with C.temp_override(window=w, area=a, region=r):
            if C.mode == 'SCULPT':
                bpy.ops.object.mode_set(mode='OBJECT')
                v = int((mm.values(body) > 0.5).sum())
                bpy.ops.object.mode_set(mode='SCULPT')
                return v
            return int((mm.values(body) > 0.5).sum())
    it = yield from scrolled_item('Paint Mask')
    if it is not None:
        yield from press(it)
    yield 2.0
    co0 = mio.read_co(body.data).copy()
    band = [(float(x) * 0.5 - 0.2, -0.85, 0.3) for x in np.linspace(-1, 1, 16)]
    yield from drag(band)
    yield 1.0
    n1 = masked()
    yield from drag(band[:9], mods=('alt',))
    yield 1.0
    n2 = masked()
    log('Paint Mask on:', mm.on(C), '| a REAL drag: masked', n1, '| Alt + REAL drag over half of it: masked', n2)
    res['A1 the ZBRUSH mouse in MECHA LAB: a REAL drag masks, Alt + drag erases (fewer masked points)'] = (
        mm.on(C) and n1 > 30 and n2 < n1 * 0.85)
    sx0 = bool(body.data.use_mirror_x)
    xdo('mousemove', *screen_xy((0.0, -1.0, 0.0)))
    yield 0.5
    xdo('key', 'x')
    yield 1.0
    sx1 = bool(body.data.use_mirror_x)
    log('X (REAL key): mirror', sx0, '->', sx1, 'still painting', mm.on(C), 'mode', C.mode)
    res['A2 X (REAL key) switches the mirror, the painting goes on'] = sx0 != sx1 and mm.on(C)
    if sx1:
        xdo('key', 'x')
        yield 0.6
    xdo('mousemove', *screen_xy((0.6, 2.0, 1.25)))            # (empty canvas, up right of the ball)
    yield 0.5
    xdo('keydown', 'ctrl')
    yield 0.2
    xdo('click', 1)
    yield 0.4
    xdo('keyup', 'ctrl')
    yield 1.2
    n3 = masked()
    total = len(body.data.vertices)
    log('Ctrl + REAL click on empty canvas: masked', n2, '->', n3, 'of', total)
    res['A3 Ctrl + REAL click on empty canvas inverts the mask'] = abs(n3 - (total - n2)) < total * 0.03
    xdo('keydown', 'ctrl')
    yield 0.2
    xdo('click', 1)
    yield 0.4
    xdo('keyup', 'ctrl')
    yield 1.0
    yield from drag(band, mods=('shift',))
    yield 1.0
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.object.mode_set(mode='OBJECT')
        moved = float(np.abs(mio.read_co(body.data) - co0).max())
        bpy.ops.object.mode_set(mode='SCULPT')
    log('Shift + REAL drag on the model: the mesh moved', moved)
    res['A4 Shift + drag (Smooth in the ZBRUSH screen) does not change the mesh here'] = moved < 1e-6
    if masked() < 30:                               # (the second Ctrl + click may have cleared it: paint the band again)
        yield from drag(band)
        yield 1.0
    log('masked before Drape Mask', masked())
    shot('1_mask.png')
    # (B) stitches on the cloth
    it = yield from scrolled_item('Drape Mask (masked faces lift off as the cloth)')
    if it is not None:
        yield from press(it)
    yield 3.0
    ob = bpy.data.objects.get(cd.SIM.get('ob', '')) if cd.sim_active() else None
    it = yield from scrolled_item('Draw Stitches')
    log('cloth', ob and ob.name, 'running', cd.SIM.get('running'), 'Draw Stitches cell', it is not None)
    if it is not None:
        yield from press(it)
    yield 1.5
    seam = [(float(x) * 0.35 - 0.2, -0.99, 0.3) for x in np.linspace(-1, 1, 14)]
    xy = [screen_xy(p) for p in seam]
    xdo('mousemove', *xy[0])
    yield 0.4
    xdo('mousedown', 1)
    yield 0.3
    for x, y in xy[1:8]:
        xdo('mousemove', x, y)
        yield 0.08
    yield 0.6
    mid = len(cd.STITCH.get('stroke') or [])
    shot('2_stitch_while_drawing.png')
    for x, y in xy[8:]:
        xdo('mousemove', x, y)
        yield 0.08
    yield 0.3
    xdo('mouseup', 1)
    yield 2.0
    n_seam = len(cd.stitch_paths(ob.data)) if ob else -1
    pts = cd.SIM.get('sess', {}).get('stitches', 0) if cd.sim_active() else -1
    log('Draw Stitches on:', cd.STITCH.get('on'), '| half way through the REAL drag the stroke has', mid,
        'points | let go: seams', n_seam, 'seam points', pts, 'cloth hidden', ob.hide_get() if ob else None)
    res['B1 Draw Stitches: a REAL drag on the cloth itself - the line is there while it is drawn (points mid-drag), a seam on the cloth after'] = (
        mid >= 3 and n_seam == 1 and pts > 5 and ob is not None and not ob.hide_get())
    shot('3_seam.png')
    xdo('keydown', 'ctrl')
    yield 0.2
    xdo('key', 'z')
    yield 0.3
    xdo('keyup', 'ctrl')
    yield 1.5
    n_undo = len(cd.stitch_paths(ob.data)) if ob else -1
    log('Ctrl + Z (REAL keys): seams', n_seam, '->', n_undo, 'cloth still there', cd.sim_active())
    res['B2 Ctrl + Z (REAL keys) takes the last seam off (the cloth stays)'] = n_undo == 0 and cd.sim_active()
    yield from drag(seam)
    yield 2.0
    n_again = len(cd.stitch_paths(ob.data)) if ob else -1
    xdo('mousemove', *screen_xy((0.9, 0.0, -0.9)))
    yield 0.5
    xdo('key', 'space')
    yield 5.0
    frame = cd.SIM.get('sess', {}).get('frame', -1) if cd.sim_active() else -1
    log('drawn again: seams', n_again, '| Space (REAL key): frame', frame, 'drawing on', cd.STITCH.get('on'))
    res['B3 drawn again, then Space (REAL key): drawing ends and it drapes with the seam'] = (
        n_again == 1 and frame > 0 and not cd.STITCH.get('on'))
    yield 4.0
    shot('4_draped.png')
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
