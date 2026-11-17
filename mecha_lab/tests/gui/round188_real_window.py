"""Real window 0.24.188: a one-piece body's part picked by a REAL click (user: "조인트에서 바꾸는 게 너무 가시성이 안 좋으니까
내가 원하는 부분 클릭하면 옆에 슬라이더에서 바꿀 수 있게").

  1. Body Kit tool, REAL click on "Creature 2" (One-Piece Body): the body on its bones, at once
  2. REAL click on the shin / the head / the right upper arm: the window's Part is that one
  3. the Bend slider dragged for REAL: the picked upper arm (and the left one, Symmetry) bends
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


def to_x(w, r, x, y):
    return int(r.x + x), int(w.height - (r.y + y))


def layer_items():
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        return lp.items(C, r.width, r.height, ui_factor(C, r))


def lfind(pred):
    return next((i for i in layer_items() if pred(i)), None)


def lclick(it, mods=()):
    w, a, r = view3d()
    x, y = to_x(w, r, it.x + it.w / 2, it.y + it.h / 2)
    xdo('mousemove', x, y)
    yield 0.4
    for m in mods:
        xdo('keydown', m)
    yield 0.2
    xdo('click', 1)
    yield 0.4
    for m in mods:
        xdo('keyup', m)
    yield 1.2


def lbutton(row_name, label_start):
    row = lfind(lambda i: i.kind == 'lrow' and i.label == row_name)
    if row is None:
        return None
    return lfind(lambda i: i.kind == 'pmin' and i.label.startswith(label_start) and abs(i.y - row.y) < 3)


def drag_path(points):
    xy = [screen_xy(p) for p in points]
    xdo('mousemove', *xy[0])
    yield 0.5
    xdo('mousedown', 1)
    yield 0.4
    for x, y in xy[1:]:
        xdo('mousemove', x, y)
        yield 0.08
    yield 0.3
    xdo('mouseup', 1)
    yield 2.0


def key_over_view(key):
    w, a, r = view3d()
    xdo('mousemove', int(r.x + r.width * 0.5), int(w.height - (r.y + r.height * 0.12)))
    yield 0.5
    xdo('key', key)
    yield 3.0


def set_tool(tool):
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool=tool)
        bpy.ops.mch.side_page(page='TOOL')
        for o in C.selected_objects:
            o.select_set(False)
        C.view_layer.objects.active = None




def flow():
    from mecha_lab import body_whole as bw
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
        rv = sp3.region_3d
        rv.view_perspective = 'ORTHO'
        rv.view_rotation = Euler((math.radians(90), 0.0, 0.0)).to_quaternion()
        rv.view_location = (0.0, 0.0, 0.95)
        rv.view_distance = 2.6
    S.cursor.location = (0.0, 0.0, 0.0)
    sp3.show_region_ui = False
    sp3.shading.type = 'SOLID'
    set_tool('BODYKIT')
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 2.0
    yield from wait_draws(2)
    it = yield from scrolled_item('Creature 2')
    t0 = time.perf_counter()
    if it is not None:
        yield from press(it)
    yield from wait_draws(3)
    body = next((o for o in S.objects if o.type == 'MESH' and bw.is_body(o)), None)
    rig = bw.pair(body)[1] if body is not None else None
    log('1 body', body, rig, round(time.perf_counter() - t0, 1), 's')
    res['1 REAL click "Creature 2" (One-Piece Body): the body on its bones'] = body is not None and rig is not None and \
        len(rig.pose.bones) == 51
    shot('1_body.png')
    if rig is None:
        raise RuntimeError('no body')
    kp = rig.mch_bodywhole

    def mid(bone, t=0.5):
        C.view_layer.update()
        pb = rig.pose.bones[bone]
        return rig.matrix_world @ pb.head.lerp(pb.tail, t)
    got = {}
    for bone in ('Shin.L', 'Head', 'UpperArm.R'):
        x, y = screen_xy(mid(bone))
        xdo('mousemove', x, y)
        yield 0.5
        xdo('click', 1)
        yield 1.0
        yield from wait_draws(2)
        got[bone] = kp.joint
        log('2 click', bone, '->', kp.joint, 'active', C.view_layer.objects.active)
    res[f'2 REAL clicks on the shin, the head, the right upper arm: the window\'s Part is each one {got}'] = all(
        got[k] == k for k in got) and C.view_layer.objects.active == body
    shot('2_picked.png')
    it = yield from scrolled_item('Bend')
    b0 = bw.joint(rig, 'UpperArm.R')['bend']
    if it is not None:
        yield from slider_drag(it, 0.5, 60)
    yield from wait_draws(2)
    b1, b1l = bw.joint(rig, 'UpperArm.R')['bend'], bw.joint(rig, 'UpperArm.L')['bend']
    log('3 bend', b0, '->', b1, 'left', b1l)
    res['3 the Bend slider dragged for REAL: the picked upper arm bends, the left one too (Symmetry)'] = (
        abs(b1 - b0) > 0.05 and abs(b1l - b1) < 1e-6)
    shot('3_bent.png')
    bpy.types.SpaceView3D.draw_handler_remove(handle, 'WINDOW')
    for k_, v in res.items():
        log(('PASS ' if v else 'FAIL ') + k_)
    log(f'{sum(bool(v) for v in res.values())}/{len(res)} passed')
    bpy.ops.wm.quit_blender()


lp = None
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
