"""Real window 0.24.213: the Cloth Drape window in big coloured sections - screenshots (Korean and English), a REAL
click on a section title folds it (its settings shown in the title), a second one opens it; a setting inside a
section still answers a REAL click (Pin Rim) and a REAL drag (Looseness)."""
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
    from mecha_lab import i18n, cloth_drape as cd, ui_bars
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
        bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=64, radius=1.0)
        a.spaces.active.show_region_ui = False
        bpy.ops.mch.bar_tool(tool='CDRAPE')
        bpy.ops.mch.side_page(page='TOOL')
    sp.FOLDED.clear()
    sp.dirty()
    st = cd.settings(C)
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 3.0
    yield from wait_draws(3)
    shot('01_sections_korean_top.png')

    def heads():
        with C.temp_override(window=w, area=a, region=r):
            its = sp.items(C, r.width, r.height, ui_factor(C, r))
        return [i for i in its if i.kind == 'shead' and str(i.icon).startswith('big:')], its
    C.window_manager.mch_side_scroll = 0.0
    yield from wait_draws(2)
    big, its = heads()
    res['A1'] = len(big) >= 2 and big[0].label == 'CLOTH DRAPE'
    log('A1 big titles in the window now:', [(i.label, i18n.tr(i.label)) for i in big])
    it = yield from scrolled_item('FABRIC')
    n0 = len(heads()[1])
    if it is not None:
        yield from press(it)
    yield from wait_draws(3)
    big, its = heads()
    fab = next((i for i in big if i.label == 'FABRIC'), None)
    note = str(fab.icon).partition('|')[2] if fab else ''
    res['A2'] = fab is not None and not fab.on and bool(note) and 'CDRAPE:Fabric' in sp.FOLDED
    log('A2 REAL click on the Fabric title: folded', fab is not None and not fab.on, '| shown in the title:', note)
    shot('02_fabric_folded.png')
    if fab is not None:
        yield from press(fab)
    yield from wait_draws(3)
    res['A3'] = 'CDRAPE:Fabric' not in sp.FOLDED
    log('A3 a second REAL click opens it again', res['A3'])
    # a switch and a slider inside the sections still answer the REAL mouse
    was = st.pin_rim
    it = yield from scrolled_item('Pin Rim')
    if it is not None:
        yield from press(it)
    yield 0.6
    res['A4'] = it is not None and st.pin_rim != was
    log('A4 REAL click on Pin Rim (in Pins & Stitches):', was, '->', st.pin_rim)
    st.pin_rim = was
    v0 = st.slack
    it = yield from scrolled_item('Looseness')
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
    res['A5'] = it is not None and st.slack > v0
    log('A5 REAL drag on Looseness (in Fabric): %.1f -> %.1f' % (v0, st.slack))
    st.slack = v0
    with C.temp_override(window=w, area=a, region=r):
        for _i in range(6):
            sp.scroll_by(C, r.width, r.height, ui_factor(C, r), 240)
    yield from wait_draws(3)
    shot('03_sections_korean_lower.png')
    i18n.force('EN')
    sp.dirty()
    C.window_manager.mch_side_scroll = 0.0
    yield 1.0
    yield from wait_draws(3)
    shot('04_sections_english_top.png')
    i18n.force(None)
    names = {'A1': 'the window starts with the big Cloth Drape title; big coloured titles are drawn',
             'A2': 'a REAL click on the Fabric title folds it; the title shows what it is set to',
             'A3': 'a second REAL click opens it', 'A4': 'a switch inside a section answers a REAL click (Pin Rim)',
             'A5': 'a slider inside a section answers a REAL drag (Looseness)'}
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
