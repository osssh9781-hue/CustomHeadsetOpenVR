"""Real window (0.24.158, user: "웨더링 메뉴 - 흙, 먼지, 나뭇잎, 눈 ... 내가 만든 메쉬를 클릭하면 그런 형태로 바꿔 줘"): the
Weathering tools by REAL clicks (xdotool) on four shapes - a live Base Mesh, a Creature Base Mesh lump, a sheet, a
sphere: Dirt, Dust, Leaves, Snow; a REAL Alt + click takes one back to its shape; a REAL drag on a window slider.
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





def click_at(p, mods=()):
    x, y = screen_xy(p)
    xdo('mousemove', x, y)
    yield 0.4
    for m in mods:
        xdo('keydown', m)
    yield 0.15
    xdo('click', 1)
    yield 0.2
    for m in mods:
        xdo('keyup', m)
    yield 1.5


def flow():
    import math
    import numpy as np
    from mecha_lab import base_mesh, core_geometry as cg, weathering as wx
    from mathutils import Quaternion
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
    res = {}
    TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)

    def blob(cx, cy, rad, n=40):
        return [[(500 + (cx + rad * math.cos(t) * (1 + 0.2 * math.sin(3 * t))) * 100, 500 + (cy + rad * math.sin(t)) * 100)
                 for t in np.linspace(0, 2 * math.pi, n, endpoint=False)]]
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        S.mch_base.sketch = False
        S.mch_base.profile = 'BEVEL'
        S.mch_base.height = 0.4
        before = set(bpy.data.objects)
        base_mesh.perform_base(C, blob(-2.4, 0, 0.9), TOP)
        shape = [o for o in bpy.data.objects if o not in before][0]
        prev = S.mch_settings.mch_active_tool
        S.mch_settings.mch_active_tool = 'CBASE'
        S.mch_cbase.sketch = False
        before = set(bpy.data.objects)
        base_mesh.perform_base(C, blob(-0.8, 0, 0.7), TOP)
        lump = [o for o in bpy.data.objects if o not in before][0]
        S.mch_settings.mch_active_tool = prev
        bpy.ops.mesh.primitive_plane_add(size=1.6, location=(0.9, 0, 0))
        sheet = C.active_object
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.6, location=(2.5, 0, 0.3))
        ball = C.active_object
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((0.95, 0.0, 0.0)).to_quaternion()
        rv.view_location = (0.0, 0.0, 0.0)
        rv.view_distance = 8.5
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True
        sp3.shading.type = 'MATERIAL'
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 2.0
    plan = (('WDIRT', shape, 'DIRT', Vector((-2.4, 0.0, 0.3))), ('WDUST', lump, 'DUST', Vector((-0.8, 0.0, 0.2))),
            ('WLEAF', sheet, 'LEAVES', Vector((0.9, 0.0, 0.0))), ('WSNOW', ball, 'SNOW', Vector((2.5, 0.0, 0.85))))
    for tool, ob, kind, p in plan:
        w, a, r = view3d()
        with C.temp_override(window=w, area=a, region=r):
            bpy.ops.mch.bar_tool(tool=tool)
            bpy.ops.mch.side_page(page='TOOL')
        yield 1.0
        yield from click_at(p)
        log(tool, ob.name, '->', wx.kind_of(ob), 'modifier', ob.modifiers.get(wx.MOD) is not None, 'active',
            C.view_layer.objects.active and C.view_layer.objects.active.name)
        res[f'a REAL click with {wx.LABEL[kind]} on {ob.name}: it becomes {kind.lower()} (live), selected'] = (
            wx.kind_of(ob) == kind and ob.modifiers.get(wx.MOD) is not None and C.view_layer.objects.active == ob)
    yield 1.0
    shot('1_weathered.png')
    # a REAL drag on a slider in the window (Snow is the tool now, the ball selected): Puff
    p0 = ball.mch_wsnow.puff
    it = yield from scrolled_item('Puff')
    if it is not None:
        w, a, r = view3d()
        x, y = int(r.x + it.x + it.w * 0.3), int(w.height - (r.y + it.y + it.h / 2))
        xdo('mousemove', x, y)
        yield 0.5
        xdo('mousedown', 1)
        yield 0.3
        for i in range(1, 12):
            xdo('mousemove', x + i * 15, y)
            yield 0.06
        yield 0.3
        xdo('mouseup', 1)
        yield 1.5
    log('Puff cell', it is not None, 'puff', round(p0, 3), '->', round(ball.mch_wsnow.puff, 3))
    res['a REAL drag on the window\'s Puff: the snow puffs more (the selected ball\'s value)'] = (
        it is not None and ball.mch_wsnow.puff > p0 + 0.1)
    # a REAL Alt + click on the dusted lump with the Dust tool: back to its shape
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool='WDUST')
    yield 1.0
    yield from click_at(Vector((-0.8, 0.0, 0.2)), mods=('alt',))
    log('Alt + click on', lump.name, '->', wx.kind_of(lump), 'modifier', lump.modifiers.get(wx.MOD) is not None)
    res['a REAL Alt + click on the dusted lump: back to its shape'] = (wx.kind_of(lump) is None
                                                                      and lump.modifiers.get(wx.MOD) is None)
    yield 1.0
    shot('2_after.png')
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
