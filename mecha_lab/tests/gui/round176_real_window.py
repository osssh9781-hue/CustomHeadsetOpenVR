"""Real window (0.24.176, user: "곤충 날개도 크리쳐 클로스처럼 메쉬에 붙게 할 수 있어?", "벌레 날개도 처음 선 긋는 부분이
벌레 날개 [뿌리] 되게 해 줘"), by REAL drags, clicks and keys (xdotool), wireframe on:

  1. Insect Wing: a REAL lasso started over a body (a thorax ball) going right - the part over it sits on it, the wing a
     child of the thorax (follows it), its root where the lasso started
  2. a REAL lasso started at the far end - its root there
  3. a REAL click on "Stick to Mesh" - off: flat; a REAL click again - on it
  4. over two meshes (the thorax + an arm): a REAL Enter - kept, a Hook to the arm (its points follow it)
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


def set_tool(tool):
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool=tool)
        bpy.ops.mch.side_page(page='TOOL')
        for o in C.selected_objects:
            o.select_set(False)
        C.view_layer.objects.active = None


def key_over_view(key):
    w, a, r = view3d()
    xdo('mousemove', int(r.x + r.width * 0.5), int(w.height - (r.y + r.height * 0.12)))
    yield 0.5
    xdo('key', key)
    yield 2.0


def flow():
    import numpy as np
    from mecha_lab import creature_membrane as cm, insect_wing as iw
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
    R = 0.4
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=R, segments=96, ring_count=48, location=(0, 0, 0))
        body = C.active_object
        body.name = 'Thorax'
        rv = sp3.region_3d
        rv.view_perspective = 'ORTHO'
        rv.view_rotation = Euler((math.radians(90), 0.0, 0.0)).to_quaternion()
        rv.view_location = (0.7, 0.0, -0.2)
        rv.view_distance = 5.5
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True
        sp3.shading.type = 'SOLID'
    S.mch_brush.shape = 'STROKE'
    S.mch_wing.preset = 'FLY'
    set_tool('WING')
    yield 2.0
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')

    def outline(x0, z0, L, Wd, n=30, from_tip=False):
        pts = [(x0 + L * i / (n - 1), z0 + 0.02 * L * math.sin(math.pi * i / (n - 1))) for i in range(n)]
        pts += [(x0 + L * (1 - i / (n - 1)), z0 - Wd * math.sin(math.pi * (1 - i / (n - 1))) ** 0.7) for i in range(n)]
        if from_tip:
            pts = pts[n - 1:] + pts[:n - 1]
        return [screen_xy((x, -1.0, z)) for x, z in pts]

    def world(ob):
        C.view_layer.update()
        ev = ob.evaluated_get(C.evaluated_depsgraph_get())
        me = ev.to_mesh()
        P = np.array([tuple(ev.matrix_world @ v.co) for v in me.vertices])
        ev.to_mesh_clear()
        return P

    def root_x(ob):
        d = iw.data(ob)
        return (Vector(d['origin']) + Vector(d['x']) * d['outline'][d['root']][0]).x

    # 1
    yield from real_outline(outline(0.05, 0.1, 1.5, 0.32))
    yield 2.0
    wing = next((o for o in S.objects if iw.is_wing(o)), None)
    P = world(wing) if wing else np.zeros((1, 3))
    over = np.hypot(P[:, 0], P[:, 2]) < R * 0.9
    err = float(np.median(np.abs(np.linalg.norm(P[over], axis=1) - R))) if over.any() else 9.9
    rx1 = root_x(wing) if wing else None
    log('1 wing', wing and wing.name, 'parent', wing and wing.parent and wing.parent.name, 'over', int(over.sum()),
        'on err', round(err, 4), 'root x', rx1 and round(rx1, 3))
    res['1 a REAL lasso started over the thorax: the part over it on it, the wing its child, the root where it started'] = (
        wing is not None and over.sum() > 50 and err < 0.02 and wing.parent == body and rx1 is not None and rx1 < 0.25)
    shot('1_wing_on_thorax.png')
    # 3 Stick to Mesh off / on (on this wing)
    it = yield from scrolled_item('Stick to Mesh')
    if it is not None:
        yield from press(it)
    yield from wait_draws(2)
    off = wing.mch_wing.stick if wing else None
    Pf = world(wing) if wing else np.zeros((1, 3))
    flat = float(np.ptp(Pf[over, 1])) if over.any() else 9.9
    shot('3_stick_off.png')
    it2 = yield from scrolled_item('Stick to Mesh')
    if it2 is not None:
        yield from press(it2)
    yield from wait_draws(2)
    Pn = world(wing) if wing else np.zeros((1, 3))
    err_on = float(np.median(np.abs(np.linalg.norm(Pn[over], axis=1) - R))) if over.any() else 9.9
    log('3 Stick cell', it is not None, 'off', off, 'flat y spread', round(flat, 4), '- on again', wing and wing.mch_wing.stick,
        'err', round(err_on, 4))
    res['3 a REAL click on "Stick to Mesh": off - flat in its plane; a REAL click again: on the thorax again'] = (
        it is not None and off is False and flat < 0.03 and wing.mch_wing.stick and err_on < 0.02)
    with C.temp_override(window=w, area=a, region=r):
        bpy.data.objects.remove(wing)
    set_tool('WING')
    yield 1.0
    # 2 from the far end
    yield from real_outline(outline(0.05, 0.1, 1.5, 0.32, from_tip=True))
    yield 2.0
    wing2 = next((o for o in S.objects if iw.is_wing(o)), None)
    rx2 = root_x(wing2) if wing2 else None
    log('2 wing', wing2 and wing2.name, 'root x', rx2 and round(rx2, 3))
    res['2 a REAL lasso started at the far end: its root there'] = rx2 is not None and rx2 > 1.4
    shot('2_root_at_far_end.png')
    with C.temp_override(window=w, area=a, region=r):
        bpy.data.objects.remove(wing2)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.14, segments=48, ring_count=24, location=(0.62, 0.0, 0.05))
        arm = C.active_object
        arm.name = 'Arm'
    set_tool('WING')
    yield 1.0
    # 4 over two meshes, a REAL Enter
    yield from real_outline(outline(0.05, 0.1, 1.5, 0.32))
    yield 2.0
    wing3 = next((o for o in S.objects if iw.is_wing(o)), None)
    groups = sorted(g.name for g in wing3.vertex_groups if g.name.startswith(cm.HOST_PREFIX)) if wing3 else []
    yield from key_over_view('Return')
    yield 1.0
    hooks = [m.object.name for m in wing3.modifiers if m.type == 'HOOK'] if wing3 else []
    Pa = world(wing3)
    arm.location.z += 0.3
    Pb = world(wing3)
    dz = Pb[:, 2] - Pa[:, 2]
    log('4 groups', groups, 'hooks', hooks, 'kept', wing3 and iw.data(wing3) is None, 'moved', round(float(dz.max()), 3),
        'still', round(float(np.abs(dz[dz < 0.15]).max()) if (dz < 0.15).any() else -1, 5))
    res['4 over the thorax and an arm: a REAL Enter - kept, a child of the thorax + a Hook to the arm (its points follow '
        'it)'] = (wing3 is not None and len(groups) == 2 and hooks == ['Arm'] and iw.data(wing3) is None
                  and abs(float(dz.max()) - 0.3) < 1e-3 and (dz < 0.15).any() and float(np.abs(dz[dz < 0.15]).max()) < 1e-4)
    shot('4_kept_hook.png')
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
