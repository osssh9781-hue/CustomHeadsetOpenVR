"""Real window (0.24.147): Creature Light on the Render page, driven by REAL clicks (xdotool) in the MECHA LAB workspace.

  1. a REAL click on Creature Light: the scene's world is ours (your world remembered)
  2. a REAL click on a preview tile (Museum): that set-up; a REAL click on the page arrow: the next 9 tiles
  3. a REAL click on Fade Floor: the disc under the creature; on Shadow Catcher: the same disc a catcher
  4. Rendered (Cycles) view with the wireframe: shots;  a REAL click on Creature Light again: your world back
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
    from mecha_lab import creature_light as cl
    res = {}
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_monkey_add(size=1.6, location=(0, 0, 0.9))
        head = C.active_object
        head.modifiers.new('sub', 'SUBSURF').levels = 1
        bpy.ops.object.shade_smooth()
        S.world = bpy.data.worlds.new('My World')
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((1.3, 0.0, 0.45)).to_quaternion()
        rv.view_location = (0.0, 0.0, 0.7)
        rv.view_distance = 6.0
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True                  # (the wireframe always shown with a result)
        bpy.ops.mch.bar_tool(tool='SELECT')
        bpy.ops.mch.side_page(page='HDRI')
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 2.0
    it = yield from scrolled_item('Creature Light')
    log('Creature Light cell', it is not None)
    if it is None:
        log('ERROR no Creature Light cell')
        bpy.ops.wm.quit_blender()
        return
    yield from press(it)
    yield 1.0
    res['1 a REAL click on Creature Light: our world on, your world remembered'] = (
        cl.on(S) and S.get(cl.PREV_KEY) == 'My World')
    it = yield from scrolled_item('Museum')
    if it is not None:
        yield from press(it)
    yield 1.0
    st = cl.settings(S)
    res['2 a REAL click on the Museum tile: that set-up'] = it is not None and st.preset == 'museum' and cl.on(S)
    shot('0_render_page.png')
    it = yield from scrolled_item('▶')
    log('page arrow', it is not None, it and (it.kind, it.action))
    if it is not None:
        yield from press(it)
    yield 1.0
    yield from wait_draws(2)
    nxt = yield from scrolled_item(cl.PRESETS[9][1])
    log('page', st.page, 'tile', nxt is not None)
    res['2 the page arrow: the next 9 tiles'] = st.page == 1 and nxt is not None
    it = yield from scrolled_item('Fade Floor')
    if it is not None:
        yield from press(it)
    yield 1.0
    fl = cl.floor_object(S)
    res['3 a REAL click on Fade Floor: the disc under the creature'] = (
        fl is not None and st.floor == 'FADE' and fl.active_material is not None and abs(fl.location.z - (
            min((head.matrix_world @ __import__('mathutils').Vector(c)).z for c in head.bound_box))) < 1e-3)
    S.render.engine = 'CYCLES'
    S.cycles.preview_samples = 8
    sp3.shading.type = 'RENDERED'
    yield 25.0
    shot('1_rendered_fade_floor_wire.png')
    it = yield from scrolled_item('Shadow Catcher')
    if it is not None:
        yield from press(it)
    yield 1.0
    res['3 a REAL click on Shadow Catcher: the same disc a catcher'] = (
        cl.floor_object(S) is fl and fl.is_shadow_catcher and st.floor == 'CATCHER')
    yield 25.0
    shot('2_rendered_catcher_wire.png')
    sp3.shading.type = 'SOLID'
    yield 1.0
    it = yield from scrolled_item('Creature Light')
    if it is not None:
        yield from press(it)
    yield 1.0
    res['4 a REAL click on Creature Light again: your world back'] = (
        not cl.on(S) and S.world is not None and S.world.name == 'My World')
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
