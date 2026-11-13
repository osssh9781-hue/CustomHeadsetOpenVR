"""Real window (0.24.148): the Background the Compositor way, by REAL clicks (xdotool) on the Render page.

  1. a REAL click on Background Colour (Compositor): Film Transparent on, the scene's compositor ours, every 3D view's
     viewport compositor Always - nothing else to set by hand
  2. Material Preview and Rendered (Cycles): the colour behind the model in the viewport (pixels read from the screen)
  3. a REAL click on Picture: the picture behind (shots, with the wireframe)
  4. a REAL click on Background Colour again: Film Transparent, the compositor and the views as they were
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


def red_share(path, w, r):
    """The share of a 24 x 14 grid over the 3D view (window region) that is the red background colour."""
    img = bpy.data.images.load(path)
    try:
        import numpy as np
        W, H = img.size
        px = np.empty(W * H * 4, np.float32)
        img.pixels.foreach_get(px)
        px = px.reshape(H, W, 4)
        n = red = 0
        for i in range(24):
            for j in range(14):
                x = int(r.x + r.width * (i + 0.5) / 24)
                y = int(r.y + r.height * (j + 0.5) / 14)          # (from the bottom, as Blender's pixels)
                c = px[y, x, :3] * 255
                n += 1
                red += c[0] > 150 and c[0] > 1.5 * c[1] and c[0] > 1.5 * c[2]      # (AgX: about 203, 110, 105)
        return red / n
    finally:
        bpy.data.images.remove(img)


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
    from mecha_lab import bg_color as bgc
    res = {}
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_monkey_add(size=1.6, location=(0, 0, 0.9))
        bpy.ops.object.shade_smooth()
        S.world = bpy.data.worlds.new('My World')
        S.world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.5, 0.5, 0.5, 1)
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((1.3, 0.0, 0.45)).to_quaternion()
        rv.view_location = (0.0, 0.0, 0.7)
        rv.view_distance = 6.0
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True                  # (the wireframe always shown with a result)
        bpy.ops.mch.bar_tool(tool='SELECT')
        bpy.ops.mch.side_page(page='HDRI')
    st = bgc.settings(S)
    st.color = (0.85, 0.12, 0.12)
    st.mode = 'COLOR'
    S.render.film_transparent = False
    before = (sp3.shading.use_compositor, S.render.film_transparent, S.compositing_node_group)
    log('before: viewport compositor', before[0], 'film transparent', before[1], 'compositor', before[2])
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 2.0
    it = yield from scrolled_item('Background Colour')
    if it is None:
        log('ERROR no Background Colour cell')
        bpy.ops.wm.quit_blender()
        return
    yield from press(it)
    yield 1.0
    log('after: viewport compositor', sp3.shading.use_compositor, 'film', S.render.film_transparent,
        'compositor', S.compositing_node_group and S.compositing_node_group.name)
    res['1 one REAL click: Film Transparent, our compositor, the viewport compositor Always (set for you)'] = (
        st.method == 'COMP' and bgc.comp_on(S) and S.render.film_transparent and sp3.shading.use_compositor == 'ALWAYS')
    # a corner of the 3D view (away from the panels): the background colour seen in the viewport?
    sp3.shading.type = 'MATERIAL'
    yield 12.0
    p1 = shot('1_material_preview_colour.png')
    c1 = red_share(p1, w, r)
    S.render.engine = 'CYCLES'
    S.cycles.preview_samples = 4
    sp3.shading.type = 'RENDERED'
    yield 25.0
    p2 = shot('2_rendered_colour_wire.png')
    c2 = red_share(p2, w, r)
    log('the 3D view red (the background colour): Material Preview', round(c1, 2), 'Rendered', round(c2, 2))
    res['2 Material Preview: the colour behind the model in the viewport (most of the view red)'] = c1 > 0.4
    res['2 Rendered (Cycles): the colour behind the model in the viewport (most of the view red)'] = c2 > 0.4
    it = yield from scrolled_item('Picture')
    if it is not None:
        yield from press(it)
    yield 25.0
    p3 = shot('3_rendered_picture_wire.png')
    c3 = red_share(p3, w, r)
    log('picture: mode', st.mode, 'red share', round(c3, 2))
    res['3 a REAL click on Picture: a picture behind (no red background left)'] = st.mode == 'IMAGE' and c3 < 0.05
    sp3.shading.type = 'SOLID'
    yield 1.0
    it = yield from scrolled_item('Background Colour')
    if it is not None:
        yield from press(it)
    yield 1.0
    log('off: viewport compositor', sp3.shading.use_compositor, 'film', S.render.film_transparent,
        'compositor', S.compositing_node_group)
    res['4 a REAL click again: off - Film Transparent, the compositor, the viewport compositor as before'] = (
        not bgc.on(S) and (sp3.shading.use_compositor, S.render.film_transparent, S.compositing_node_group) == before)
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
