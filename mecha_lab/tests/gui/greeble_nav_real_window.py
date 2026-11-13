"""Real window (0.24.152, user: "왜 갑자기 중간 클릭으로 화면이 안 돌아가?"): with Greeble Line on, the middle mouse turns
the view - REAL presses (xdotool):

  A. a left press on empty space, released over the right panel (the release goes to the panel), then a middle drag
  B. (logged only, not checked: a middle drag while the left button still draws a stroke - Blender's orbit does not
     start then, with or without this add-on's pass-through)
  C. a plain middle drag at the end
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


def rot_now():
    w, a, r = view3d()
    return a.spaces.active.region_3d.view_rotation.copy()


def mmb_drag(x, y, dx=160):
    xdo('mousemove', x, y)
    yield 0.3
    xdo('mousedown', 2)
    yield 0.2
    for i in range(1, 9):
        xdo('mousemove', x + dx * i // 8, y + 10 * i // 8)
        yield 0.06
    xdo('mouseup', 2)
    yield 0.6


def flow():
    import bmesh
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
    from mecha_lab import greeble_line as gl
    res = {}
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=48, ring_count=24, location=(0, 0, 0))
        me = bpy.data.meshes.new('PartA')
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=0.15)
        bm.to_mesh(me)
        bm.free()
        part = bpy.data.objects.new('PartA', me)
        S.collection.objects.link(part)
        part.location = (3.0, 0.0, 0.0)
        gl.add_part(gl.settings(S), part)
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((1.2, 0.0, 0.3)).to_quaternion()
        rv.view_location = (0.0, 0.0, 0.0)
        rv.view_distance = 6.0
        sp3.show_region_ui = False
        bpy.ops.mch.bar_tool(tool='GREEBLE')
        bpy.ops.mch.side_page(page='TOOL')
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 2.0
    # empty space: the upper left of the 3D view, clear of the panels
    ex, ey = screen_xy(Vector((-1.6, 0.0, 1.4)))
    it = yield from scrolled_item('Pick Part')
    px, py = (int(r.x + it.x + it.w / 2), int(w.height - (r.y + it.y + it.h / 2))) if it else (ex + 600, ey)
    # A
    xdo('mousemove', ex, ey)
    yield 0.3
    xdo('mousedown', 1)
    yield 0.3
    for i in range(1, 9):
        xdo('mousemove', ex + (px - ex) * i // 8, ey + (py - ey) * i // 8)
        yield 0.05
    xdo('mouseup', 1)
    yield 0.8
    xdo('key', 'Escape')                                  # (if the panel's button started Pick Part)
    yield 0.5
    r0 = rot_now()
    yield from mmb_drag(ex, ey)
    r1 = rot_now()
    turned_a = r0.rotation_difference(r1).angle
    log('A: middle drag after a left press released over the panel: view turned', round(math.degrees(turned_a), 1), 'deg')
    res['A middle drag turns the view after a left press on empty space released over the panel'] = turned_a > math.radians(5)
    # B
    pts = [screen_xy(Vector((math.cos(t) * 0.99, -math.sin(t) * 0.99 * 0.0 - 0.99 * math.sin(t), 0.3)))
           for t in (0.2, 0.35, 0.5)]
    sx, sy = screen_xy(Vector((0.0, -0.95, 0.3)))
    xdo('mousemove', sx, sy)
    yield 0.3
    xdo('mousedown', 1)
    yield 0.2
    for i in range(1, 5):
        xdo('mousemove', sx + 12 * i, sy)
        yield 0.06
    r0 = rot_now()
    xdo('mousedown', 2)
    for i in range(1, 9):
        xdo('mousemove', sx + 48 + 15 * i, sy + 2 * i)
        yield 0.06
    xdo('mouseup', 2)
    yield 0.4
    r1 = rot_now()
    xdo('mouseup', 1)
    yield 0.8
    turned_b = r0.rotation_difference(r1).angle
    log('B: middle drag while drawing: view turned', round(math.degrees(turned_b), 1), 'deg')
    # C
    r0 = rot_now()
    yield from mmb_drag(ex, ey, dx=-160)
    r1 = rot_now()
    turned_c = r0.rotation_difference(r1).angle
    log('C: a plain middle drag at the end: view turned', round(math.degrees(turned_c), 1), 'deg')
    res['C a plain middle drag turns the view'] = turned_c > math.radians(5)
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
