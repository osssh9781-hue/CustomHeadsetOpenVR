"""Real window (0.24.166, user: "핀 몸통이 큰 쪽이 메쉬에 붙는 거야 - 갭이 무조건 있어야 ... 우리 저번에 만들었던 메쉬 따라서
할 수 있는 스플릿으로 만들면 될 거 같아 같이 해서"): by REAL drags and clicks (xdotool):

  1. Print Cut, Key: a REAL drag of a bent line (a V) across a block seen from above - it is split along the line as
     drawn (Split's line), a key on the smaller part, its socket a Fit Gap wider, the original hidden
  2. the Split tool: a REAL lasso round another block's end, then - the two halves selected - a REAL click on Print
     Cut's "Keys Between 2 Parts": a key on the end, along the way it comes off
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


def path_drag(world_pts, mods=(), steps=10):
    pts = [screen_xy(p) for p in world_pts]
    xdo('mousemove', *pts[0])
    yield 0.4
    for m in mods:
        xdo('keydown', m)
    xdo('mousedown', 1)
    yield 0.3
    for a_, b_ in zip(pts, pts[1:]):
        for i in range(1, steps + 1):
            xdo('mousemove', int(a_[0] + (b_[0] - a_[0]) * i / steps), int(a_[1] + (b_[1] - a_[1]) * i / steps))
            yield 0.04
    yield 0.3
    xdo('mouseup', 1)
    for m in mods:
        xdo('keyup', m)
    yield 3.0


def flow():
    import json
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

    def block(name, y0):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, y0, 0.04))
        ob = C.active_object
        ob.scale = (0.16, 0.06, 0.08)
        bpy.ops.object.transform_apply(scale=True)
        ob.name = name
        return ob

    def closed(o):
        bm_ = bmesh.new()
        bm_.from_mesh(o.data)
        ok = not any(e_.is_boundary for e_ in bm_.edges)
        v = abs(bm_.calc_volume())
        bm_.free()
        return ok, v

    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        arm = block('Arm', 0.0)
        for o in C.selected_objects:
            o.select_set(False)
        C.view_layer.objects.active = None
        rv = sp3.region_3d
        rv.view_perspective = 'ORTHO'
        rv.view_rotation = Euler((0.0, 0.0, 0.0)).to_quaternion()          # (from above)
        rv.view_location = (0.0, 0.0, 0.08)
        rv.view_distance = 0.3
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True
        sp3.shading.type = 'SOLID'
        bpy.ops.mch.bar_tool(tool='PCUT')
        bpy.ops.mch.side_page(page='TOOL')
    yield 2.0
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 1.0
    S.mch_print.pin_count, S.mch_print.pin_auto = 'AUTO', True
    it = yield from scrolled_item('Key')
    if it is not None:
        yield from press(it)
    yield 1.0
    # 1: a REAL bent drag (a V) across the block
    yield from path_drag([Vector((-0.03, -0.045, 0.08)), Vector((0.01, 0.0, 0.08)), Vector((-0.03, 0.045, 0.08))])
    parts = [o for o in S.objects if o.get(p3.FROM_KEY) == 'Arm']
    info = json.loads(parts[0]['mch_print_pins']) if parts and parts[0].get('mch_print_pins') else {}
    cl = [closed(o) for o in parts]
    log('1 Key cell', it is not None, '- style', S.mch_print.pin_style, '- parts', [o.name for o in parts], 'closed',
        [c[0] for c in cl], 'volumes', [round(c[1] * 1e6, 1) for c in cl], 'cm3 - keys', len(info.get('pins', [])),
        'on', info.get('on'), '- width', round(info.get('radius', 0) * 2000, 2), 'mm, gap', round(info.get('clearance', 0) * 1000, 2),
        'mm - original hidden', arm.hide_get())
    small = min(parts, key=lambda o: closed(o)[1]).name if len(parts) == 2 else None
    res['1 a REAL bent drag with Print Cut (Key): split along the line as drawn, one key on the smaller part, closed, the original hidden'] = (
        it is not None and len(parts) == 2 and all(c[0] for c in cl) and len(info.get('pins', [])) == 1
        and info.get('on') == small and arm.hide_get() and abs(info.get('clearance', 0) - 0.0002) < 1e-6)
    with C.temp_override(window=w, area=a, region=r):
        rv = a.spaces.active.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((math.radians(60), 0.0, math.radians(35))).to_quaternion()
        rv.view_distance = 0.42
        if len(parts) == 2:
            other = next(o for o in parts if o.name != small)
            other.location.x += 0.05
    yield 2.0
    shot('1_bent_cut_key.png')
    # 2: the Split tool's lasso, then Keys Between 2 Parts
    with C.temp_override(window=w, area=a, region=r):
        for o in parts:
            o.hide_set(True)
        core_src = block('Leg', 0.0)
        for o in C.selected_objects:
            o.select_set(False)
        C.view_layer.objects.active = None
        rv = a.spaces.active.region_3d
        rv.view_perspective = 'ORTHO'
        rv.view_rotation = Euler((0.0, 0.0, 0.0)).to_quaternion()
        rv.view_location = (0.07, 0.0, 0.08)                     # (the lasso clear of the window on the right)
        rv.view_distance = 0.3
        bpy.ops.mch.bar_tool(tool='SPLIT')
    yield 2.0
    S.mch_brush.shape = 'STROKE'
    S.mch_cut.depth_mode = 'THROUGH'
    S.mch_cut.split_mode = 'NORMAL'
    yield from real_outline([screen_xy(Vector((0.09 + 0.05 * math.cos(t), 0.05 * math.sin(t), 0.08)))
                             for t in np.linspace(0, 2 * math.pi, 40, endpoint=False)])   # (round the block's end)
    halves = [o for o in S.objects if o.type == 'MESH' and o.name.startswith('Leg') and o.visible_get()]
    log('2 Split lasso: halves', [o.name for o in halves])
    with C.temp_override(window=w, area=a, region=r):
        for o in C.selected_objects:
            o.select_set(False)
        for o in halves:
            o.select_set(True)
        if halves:
            C.view_layer.objects.active = halves[0]
        bpy.ops.mch.bar_tool(tool='PCUT')
        bpy.ops.mch.side_page(page='TOOL')
        S.mch_print.pin_style = 'KEY'
    yield 2.0
    it = yield from scrolled_item('Keys Between 2 Parts')
    if it is not None:
        yield from press(it)
    yield 2.0
    info2 = json.loads(halves[0]['mch_print_pins']) if halves and halves[0].get('mch_print_pins') else {}
    core = next((o for o in halves if o.name.endswith('_Split')), None)
    log('2b Keys Between cell', it is not None, '- keys', len(info2.get('pins', [])), 'on', info2.get('on'),
        '- closed', [closed(o)[0] for o in halves])
    pull = info2.get('normals', [[0, 0, 1]])[0]
    log('2c the key along', [round(v, 3) for v in pull], '- one way', info2.get('one_way'))
    res['2 a REAL lasso with Split, then a REAL click on "Keys Between 2 Parts": a key on the end, along the way it comes off'] = (
        it is not None and len(halves) == 2 and core is not None and len(info2.get('pins', [])) >= 1
        and info2.get('on') == core.name and all(closed(o)[0] for o in halves) and abs(abs(pull[0]) - 1) < 1e-3)
    with C.temp_override(window=w, area=a, region=r):
        rv = a.spaces.active.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((math.radians(60), 0.0, math.radians(35))).to_quaternion()
        rv.view_distance = 0.42
        if core is not None:
            core.location.x += 0.05
    yield 2.0
    shot('2_split_keys.png')
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
