"""Real window (0.24.164, user: "3D 프린팅 전용 기능 - 사이즈 측정, 수직 수평으로 잴 수 있는 거, 컷하고 그 사이에 연결 핀"):
the 3D Print tools by REAL drags and clicks (xdotool) on a 100 mm cube:

  1. Print Measure: a REAL Shift + drag down the cube's front - straight vertical (horizontal 0)
  2. a REAL free drag - its length, horizontal and vertical parts
  3. a REAL Alt + click on the first measure: it is gone, the second kept
  4. a REAL click on the window's "Scale to Height" (150 mm): the cube 150 mm tall
  5. Print Cut: a REAL Shift + drag of a line across the cube: two closed parts, pins across the cut
  6. shots: solid with the wireframe
"""
import math
import os
import subprocess
import sys
import time

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'addon'))
import mecha_lab  # noqa: E402
from mecha_lab import side_panel as sp  # noqa: E402
from mecha_lab.ui_gpu import ui_factor  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402

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


DRAWS = {'n': 0}


def _count_draw():
    DRAWS['n'] += 1


def wait_draws(n, limit=120.0):
    w, a, r = view3d()
    n0 = DRAWS['n']
    t0 = time.perf_counter()
    while DRAWS['n'] < n0 + n and time.perf_counter() - t0 < limit:
        a.tag_redraw()
        yield 0.1


def press(it):
    w, a, r = view3d()
    x, y = int(r.x + it.x + it.w / 2), int(w.height - (r.y + it.y + it.h / 2))
    xdo('mousemove', x, y)
    yield 0.6
    xdo('click', 1)
    yield 1.5


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


def real_outline(pts, mods=()):
    xdo('mousemove', *pts[0])
    yield 0.4
    for m in mods:
        xdo('keydown', m)
    yield 0.2
    xdo('mousedown', 1)
    yield 0.3
    for x, y in pts[1:] + [pts[0]]:
        xdo('mousemove', x, y)
        yield 0.04
    yield 0.3
    xdo('mouseup', 1)
    yield 0.3
    for m in mods:
        xdo('keyup', m)
    yield 2.5


def ring_at(p, rx_px, ry_px, n=48, wob=0.0):
    c = screen_xy(p)
    return [(int(c[0] + rx_px * math.cos(2 * math.pi * i / n) * (1 + wob * math.sin(3 * 2 * math.pi * i / n))),
             int(c[1] - ry_px * math.sin(2 * math.pi * i / n))) for i in range(n)]


def evaluated(ob):
    import numpy as np
    dg = C.evaluated_depsgraph_get()
    me = ob.evaluated_get(dg).data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    out = {'co': co.reshape(-1, 3), 'faces': len(me.polygons)}
    for nm in ('mch_rd', 'mch_rtop', 'mch_rough'):
        at = me.attributes.get(nm)
        a_ = np.empty(len(at.data), np.float32)
        at.data.foreach_get('value', a_)
        out[nm] = a_
    return out


def slider_drag(it, frac0, dx, steps=12):
    w, a, r = view3d()
    x, y = int(r.x + it.x + it.w * frac0), int(w.height - (r.y + it.y + it.h / 2))
    xdo('mousemove', x, y)
    yield 0.5
    xdo('mousedown', 1)
    yield 0.3
    for i in range(1, steps + 1):
        xdo('mousemove', x + i * dx, y)
        yield 0.06
    yield 0.3
    xdo('mouseup', 1)
    yield 2.5


def drag_world(a, b, mods=()):
    xa, xb = screen_xy(a), screen_xy(b)
    xdo('mousemove', *xa)
    yield 0.4
    for m in mods:
        xdo('keydown', m)
    yield 0.2
    xdo('mousedown', 1)
    yield 0.3
    for i in range(1, 16):
        xdo('mousemove', int(xa[0] + (xb[0] - xa[0]) * i / 15), int(xa[1] + (xb[1] - xa[1]) * i / 15))
        yield 0.05
    yield 0.3
    xdo('mouseup', 1)
    yield 0.4
    for m in mods:
        xdo('keyup', m)
    yield 1.5


def flow():
    import numpy as np
    import bmesh
    from mecha_lab import print3d as p3
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
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0, 0, 0.05))
        cube = C.active_object
        cube.name = 'Cube100'
        rv = sp3.region_3d
        rv.view_perspective = 'ORTHO'
        rv.view_rotation = Euler((math.radians(75), 0.0, math.radians(20))).to_quaternion()
        rv.view_location = (0.0, 0.0, 0.05)
        rv.view_distance = 0.3
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True
        sp3.shading.type = 'SOLID'
        bpy.ops.mch.bar_tool(tool='PMEASURE')
        bpy.ops.mch.side_page(page='TOOL')
    yield 1.5
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 1.0
    # 1: Shift + drag down the front face: straight vertical
    yield from drag_world(Vector((-0.03, -0.05, 0.085)), Vector((0.02, -0.05, 0.02)), mods=('shift',))
    ms = p3.measures(S)
    L1, H1, V1 = p3.components(*ms[-1]) if ms else (0, 0, 0)
    log('1 measures', len(ms), '- L', round(L1 * 1000, 1), 'H', round(H1 * 1000, 1), 'V', round(V1 * 1000, 1), 'mm')
    res['1 a REAL Shift + drag down the cube: a straight vertical measure (horizontal 0), about 65 mm'] = (
        len(ms) == 1 and H1 < 0.0005 and abs(V1 - 0.065) < 0.006)
    # 2: a free drag
    yield from drag_world(Vector((-0.03, -0.05, 0.03)), Vector((0.03, -0.05, 0.08)))
    ms = p3.measures(S)
    L2, H2, V2 = p3.components(*ms[-1]) if ms else (0, 0, 0)
    log('2 measures', len(ms), '- L', round(L2 * 1000, 1), 'H', round(H2 * 1000, 1), 'V', round(V2 * 1000, 1), 'mm')
    res['2 a REAL free drag: its length with the horizontal and vertical parts (L2 = H2 + V2)'] = (
        len(ms) == 2 and H2 > 0.04 and V2 > 0.035 and abs(L2 * L2 - H2 * H2 - V2 * V2) < 1e-8)
    shot('1_measures.png')
    # 3: Alt + click on the first measure
    mid = (ms[0][0] + ms[0][1]) / 2 if ms else Vector()
    xy = screen_xy(mid)
    xdo('mousemove', *xy)
    yield 0.4
    xdo('keydown', 'alt')
    yield 0.2
    xdo('click', 1)
    yield 0.3
    xdo('keyup', 'alt')
    yield 1.0
    ms3 = p3.measures(S)
    log('3 after Alt + click: measures', len(ms3))
    res['3 a REAL Alt + click on the first measure: it is gone, the second kept'] = (
        len(ms3) == 1 and ms and (ms3[0][0] - ms[1][0]).length < 1e-6)
    # 4: Scale to Height 150 mm
    S.mch_print.fit_height = 150.0
    with C.temp_override(window=w, area=a, region=r):
        for o in C.selected_objects:
            o.select_set(False)
        cube.select_set(True)
        C.view_layer.objects.active = cube
    yield 1.0
    it = yield from scrolled_item('Scale to Height')
    if it is not None:
        yield from press(it)
    yield 1.0
    sz = p3.size_of(C, [cube])
    log('4 Scale to Height cell', it is not None, '- size', [round(x * 1000, 1) for x in sz])
    res['4 a REAL click on "Scale to Height": the cube 150 mm tall (in proportion)'] = (
        it is not None and abs(sz.z - 0.15) < 1e-4 and abs(sz.x - 0.15) < 1e-4)
    # 5: Print Cut - a Shift + drag of a line across it
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool='PCUT')
        rv = a.spaces.active.region_3d
        rv.view_location = (0.0, 0.0, 0.075)
        rv.view_distance = 0.42
    yield 2.0
    zc = 0.075
    yield from drag_world(Vector((-0.12, -0.075, zc)), Vector((0.12, -0.075, zc + 0.005)), mods=('shift',))
    parts = [o for o in S.objects if o.get(p3.FROM_KEY) == 'Cube100']

    def closed(o):
        bm = bmesh.new()
        bm.from_mesh(o.data)
        ok = not any(e.is_boundary for e in bm.edges)
        bm.free()
        return ok
    import json
    npins = len(json.loads(parts[0]['mch_print_pins'])['pins']) if parts else 0
    log('5 parts', [o.name for o in parts], 'closed', [closed(o) for o in parts], '- pins', npins, '- original hidden',
        cube.hide_get())
    res['5 a REAL Shift + drag across the cube with Print Cut: two closed parts, pins across the cut, the original hidden'] = (
        len(parts) == 2 and all(closed(o) for o in parts) and npins >= 2 and cube.hide_get())
    with C.temp_override(window=w, area=a, region=r):
        parts[-1].location.z += 0.03 if parts else 0.0
    yield 2.0
    shot('2_cut.png')
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
