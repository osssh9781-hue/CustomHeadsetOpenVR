"""Real window (0.24.156, user: "근데 왜 크리쳐 베이스 메쉬는 스케치 모드가 안 먹혀?"): Sketch First in Base Mesh and
Creature Base Mesh - Sketch on, two REAL Free Draw outlines (xdotool), REAL Enter: the orange sketch, then one solid
(Creature Base Mesh: a Puff lump).  The same steps in both tools; the sketch must be SEEN while drawing (orange
pixels in the screenshot where it was drawn - 0.24.155 drew it in Base Mesh only).
    MCH_ADDON_DIR=<an older add-on's parent folder> to run it on another version.
"""
import os
import subprocess
import sys
import time

import bpy

sys.path.insert(0, os.environ.get('MCH_ADDON_DIR') or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..',
                                                                      'addon'))
import mecha_lab  # noqa: E402
from mecha_lab import side_panel as sp, ui_bars  # noqa: E402
from mecha_lab.ui_gpu import ui_factor  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402
import math  # noqa: E402

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





def orange_pixels(path, c, half=(170, 110)):
    """Orange pixels (the sketch's outline / fill) in the screenshot round window point ``c`` (top-left origin)."""
    import numpy as np
    img = bpy.data.images.load(path)
    try:
        w_, h_ = img.size
        px = np.array(img.pixels[:], dtype=np.float32).reshape(h_, w_, 4)
    finally:
        bpy.data.images.remove(img)
    y0, y1 = max(0, h_ - 1 - (c[1] + half[1])), min(h_, h_ - 1 - (c[1] - half[1]))
    x0, x1 = max(0, c[0] - half[0]), min(w_, c[0] + half[0])
    box = px[y0:y1, x0:x1, :3]
    r, g, b = box[..., 0], box[..., 1], box[..., 2]
    return int(np.sum((r > 0.55) & (g > 0.18) & (g < 0.62 * r) & (b < 0.45 * r)))


def ring(c, rx, ry, n=36):
    return [(int(c[0] + rx * math.cos(2 * math.pi * i / n)), int(c[1] - ry * math.sin(2 * math.pi * i / n)))
            for i in range(n)]


def real_outline(pts):
    xdo('mousemove', *pts[0])
    yield 0.4
    xdo('mousedown', 1)
    yield 0.3
    for x, y in pts[1:] + [pts[0]]:
        xdo('mousemove', x, y)
        yield 0.04
    yield 0.3
    xdo('mouseup', 1)
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
    from mecha_lab import base_mesh, lasso_sketch, mecha_menu, tool_state as ts
    res = {}
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((1.1, 0.0, 0.4)).to_quaternion()
        rv.view_location = (0.0, 0.0, 0.0)
        rv.view_distance = 8.0
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    for tool, cx in (('BASE', 0.33), ('CBASE', 0.55)):
        w, a, r = view3d()
        with C.temp_override(window=w, area=a, region=r):
            bpy.ops.mch.bar_tool(tool=tool)
            bpy.ops.mch.side_page(page='TOOL')
        yield 1.0
        S.mch_brush.shape = 'STROKE'
        with C.temp_override(window=w, area=a, region=r):
            lasso_sketch.set_on(C, True)
            on, modes = lasso_sketch.is_on(C), mecha_menu.draw_modes(C)
            tnow = ts.effective_tool(C)
        yield 1.0
        log(tool, 'tool now', tnow, '- sketch on', on, '- top bar modes', modes, '- mch_cbase.sketch', S.mch_cbase.sketch,
            'mch_base.sketch', S.mch_base.sketch)
        c = (int(r.x + r.width * cx), int(w.height - (r.y + r.height * 0.55)))
        before = set(bpy.data.objects)
        yield from real_outline(ring(c, 90, 60))
        d1 = base_mesh.sketch_data(S)
        new1 = [o.name for o in bpy.data.objects if o not in before]
        yield from real_outline(ring((c[0] + 70, c[1] - 30), 60, 60))
        d2 = base_mesh.sketch_data(S)
        new2 = [o.name for o in bpy.data.objects if o not in before]
        log(tool, 'after outline 1: sketch items', d1 and len(d1['items']), 'new objects', new1,
            '| after 2:', d2 and len(d2['items']), new2)
        seen = orange_pixels(shot(f'{tool}_sketch.png'), (c[0] + 30, c[1] - 10))
        log(tool, 'orange sketch pixels where it was drawn:', seen)
        xdo('mousemove', c[0], c[1] + 150)
        yield 0.3
        xdo('key', 'Return')
        yield 2.5
        new3 = [o for o in bpy.data.objects if o not in before]
        prof = [getattr(o.mch_base, 'profile', None) for o in new3 if getattr(o, 'mch_base', None)]
        log(tool, 'after Enter: new objects', [o.name for o in new3], 'profiles', prof, 'sketch left',
            base_mesh.sketch_data(S) is not None)
        want = 'PUFF' if tool == 'CBASE' else S.mch_base.profile
        res[f'{tool}: Sketch on, two REAL outlines stay an orange sketch (no mesh), REAL Enter makes one solid '
            f'({want}); the sketch SEEN while drawing (orange in the screenshot)'] = (seen > 300 and on and d1 is not None and len(d1['items']) == 1 and not new1 and d2 is not None
                            and len(d2['items']) == 2 and not new2 and len(new3) == 1 and prof == [want]
                            and base_mesh.sketch_data(S) is None)
        shot(f'{tool}_made.png')
    bpy.types.SpaceView3D.draw_handler_remove(handle, 'WINDOW')
    for k_, v in res.items():
        log(('PASS ' if v else 'FAIL ') + k_)
    log(f'{sum(bool(v) for v in res.values())}/{len(res)} passed')
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
