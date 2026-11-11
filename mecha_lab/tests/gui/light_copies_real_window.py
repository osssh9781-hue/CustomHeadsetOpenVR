"""Real window (0.24.136 / 0.24.137): Light Copies and Background Colour on the Render page, 15 parts x 1.3 M
triangles (19.7 M; MCH_SUBDIV=6 gives a light trial scene), software OpenGL here (absolute times far slower than a real
GPU - the ratios are what counts):
  1. Fast Viewport + Single Pass AA on; one Solid view change timed; a REAL click on Light Copies (Render page >
     VIEWPORT); the copies made in the background (the window's longest stall meanwhile); the view change again
  2. a REAL click on a part: it shows itself (selected); Wire on it and on its neighbour (itself vs its copy); a REAL
     click on empty space: it goes light again once it rests
  3. (4) a REAL click on Background Colour over a red "HDRI" world: Rendered - the background the colour, the parts
     lit red by the world
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
    from mecha_lab import fast_view as fv, light_copies as lc, bg_color as bgc
    res = {}
    subdiv = int(os.environ.get('MCH_SUBDIV', '9'))
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        S.mch_light.min_tris = 300000 if subdiv >= 9 else 10000    # (a light trial scene: its parts count as heavy)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdiv, radius=0.45, location=(-2.2, -1.1, 0))
        src_ob = C.active_object
        src_me = src_ob.data
        parts = [src_ob]
        for i in range(1, 15):
            ob = bpy.data.objects.new(f'Part{i:02d}', src_me.copy())
            S.collection.objects.link(ob)
            ob.location = ((i % 5) * 1.1 - 2.2, (i // 5) * 1.1 - 1.1, 0.0)
            parts.append(ob)
        bpy.ops.object.light_add(type='SUN', location=(0, 0, 5))
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((1.0, 0.0, 0.5)).to_quaternion()
        rv.view_location = (0.0, 0.0, 0.0)
        rv.view_distance = 9.0
        for o in S.objects:
            o.select_set(False)
        C.view_layer.objects.active = None
        C.preferences.system.viewport_aa = 'FXAA'
        fv.apply(C)
        sp3.show_region_ui = False                 # (the drawn panel hides while the N sidebar is open)
        bpy.ops.mch.bar_tool(tool='SELECT')         # (clicks on parts select them - not a Cut lasso)
        bpy.ops.mch.side_page(page='HDRI')
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    log('scene: 15 parts,', sum(len(o.data.polygons) for o in parts) / 1e6, 'M triangles')
    yield 30.0
    t_full = []
    for k in range(3):
        t = yield from view_change_draw(a, rv, 0.5 + 0.05 * (k + 1))
        t_full.append(t)
        yield 1.5
    t_full = sorted(t_full)[1]
    log(f'1 Solid view change, parts in full: {t_full:.2f} s')
    # the REAL click on Light Copies
    it = yield from scrolled_item('Light Copies (parts not worked on)')
    log('   Light Copies cell', it is not None, it and (round(it.x), round(it.y), round(it.w), round(it.h)),
        'scroll', round(C.window_manager.mch_side_scroll, 1), 'region', r.x, r.y, r.width, r.height)
    if it is None:
        log('ERROR no Light Copies cell')
        bpy.ops.wm.quit_blender()
        return
    with C.temp_override(window=w, area=a, region=r):
        inside, hit_it = ui_bars.hit(C, it.x + it.w / 2, it.y + it.h / 2)
    log('   hit test at its centre:', inside, hit_it and (hit_it.kind, hit_it.label, hit_it.action))
    shot('0_before_click.png')
    yield from press(it)
    yield 3.0
    log('   Light Copies on after the click:', S.mch_light.on, 'queued', list(lc.QUEUE), 'working', lc.WORK['name'])
    if not S.mch_light.on:
        log('ERROR the click did not turn Light Copies on')
        bpy.ops.wm.quit_blender()
        return
    t0 = time.perf_counter()
    gaps = []
    last = time.perf_counter()
    while time.perf_counter() - t0 < 900:
        yield 0.2
        now = time.perf_counter()
        gaps.append(now - last)
        last = now
        if not lc.QUEUE and lc.WORK['thread'] is None and all(lc._holder(o) is not None for o in parts):
            break
    made = time.perf_counter() - t0
    yield 3.0
    light = sum(1 for o in parts if lc._mod(o) is not None and lc._mod(o).show_viewport)
    log(f'   copies made in {made:.0f} s (15 parts, {lc._threads()} threads); longest stall of the window meanwhile '
        f'{max(gaps) if gaps else 0:.1f} s; parts drawn light: {light}')
    log('   status:', lc.status(C))
    yield 15.0
    t_light = []
    for k in range(3):
        t = yield from view_change_draw(a, rv, 0.7 + 0.05 * (k + 1))
        t_light.append(t)
        yield 1.5
    t_light = sorted(t_light)[1]
    log(f'   Solid view change with Light Copies: {t_light:.2f} s (was {t_full:.2f} s)')
    shot('1_light_copies.png')
    res[f'1 a REAL click on Light Copies: 15 copies made in the background ({made:.0f} s); a Solid view change '
        f'{t_full:.2f} s -> {t_light:.2f} s'] = light == 15 and t_light < t_full * 0.6
    # 2. a REAL click on a part: itself; on empty space: back to its copy after it rests
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    target = parts[7]
    p = location_3d_to_region_2d(r, rv, target.matrix_world.translation)
    yield from wait_draws(2)
    xdo('mousemove', int(r.x + p.x), int(w.height - (r.y + p.y)))
    yield 0.6
    xdo('click', 1)
    t1 = time.perf_counter()
    while not target.select_get() and time.perf_counter() - t1 < 40:
        yield 0.5
    yield 2.0
    sel_full = lc._mod(target) is not None and not lc._mod(target).show_viewport and target.select_get()
    n_full = len(target.evaluated_get(C.evaluated_depsgraph_get()).data.polygons)
    log('2 clicked', target.name, 'selected', target.select_get(), 'shows itself', sel_full, 'faces', n_full)
    # 3. Wire on the clicked part (itself) and its neighbour (light): two densities
    target.show_wire = True
    parts[8].show_wire = True
    with C.temp_override(window=w, area=a, region=r):
        rv.view_location = target.matrix_world.translation.lerp(parts[8].matrix_world.translation, 0.5)
        rv.view_distance = 2.6
    yield 25.0
    shot('2_selected_full_vs_light_wire.png')
    target.show_wire = parts[8].show_wire = False
    with C.temp_override(window=w, area=a, region=r):
        rv.view_location = (0.0, 0.0, 0.0)
        rv.view_distance = 9.0
    yield from wait_draws(2)
    xdo('mousemove', int(r.x + r.width * 0.62), int(w.height - (r.y + r.height * 0.74)))   # (empty grid above the parts)
    yield 0.6
    xdo('click', 1)
    t1 = time.perf_counter()
    while target.select_get() and time.perf_counter() - t1 < 40:
        yield 0.5
    yield lc.REST + 4.0
    back = lc._mod(target) is not None and lc._mod(target).show_viewport and not target.select_get()
    log('   clicked empty space:', 'selected', target.select_get(), 'light again', back)
    res[f'2 a REAL click on a part: it shows itself ({len(target.data.polygons):,} faces); a click beside: light '
        'again after it rests'] = sel_full and n_full == len(target.data.polygons) and back
    # 4. Background Colour on a red "HDRI" world: Rendered
    wd = bpy.data.worlds.new('OtherAddonHDRI')
    wd.use_nodes = True
    bgn = wd.node_tree.nodes.get('Background')
    bgn.inputs['Color'].default_value = (1.0, 0.15, 0.1, 1.0)
    bgn.inputs['Strength'].default_value = 1.2
    S.world = wd
    S.mch_bg.color = (0.12, 0.35, 0.7)
    S.render.engine = 'CYCLES'
    S.cycles.device = 'CPU'
    yield 2.0
    it = yield from scrolled_item('Background Colour')
    if it is not None:
        yield from press(it)
    yield 2.0
    log('4 Background Colour on:', bgc.on(S))
    lc.turn_off(C)                                  # (Rendered with the parts themselves)
    sp3.overlay.show_overlays = False
    sp3.shading.type = 'RENDERED'
    yield 60.0
    shot('3_background_colour_rendered.png')
    sp3.shading.type = 'SOLID'
    sp3.overlay.show_overlays = True
    res['4 a REAL click on Background Colour: on (the world kept, the colour seen by the camera)'] = bgc.on(S)
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
