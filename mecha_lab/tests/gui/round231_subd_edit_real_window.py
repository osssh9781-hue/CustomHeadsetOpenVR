"""Real window 0.24.231: the SubD Plane edited in MECHA LAB's Object Mode (no Edit Mode) - REAL mouse: drag a point,
drag an outline edge (a new face pulled out), Shift + drag an edge (it moves), Alt + click a point (removed), Ctrl +
click an edge (crease), Ctrl+Z (back); the mode stays Object all the time."""
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
import numpy as np  # noqa: E402

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


def flow():
    from mecha_lab import subd_edit, subd_plane, ui_bars as ub
    from bpy_extras import view3d_utils
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
    res = {}
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        a.spaces.active.show_region_ui = False
        rv = a.spaces.active.region_3d
        rv.view_perspective = 'ORTHO'
        rv.view_rotation = Euler((0.0, 0.0, 0.0)).to_quaternion()          # (from the top)
        rv.view_location = (0.0, 0.0, 0.0)
        rv.view_distance = 6.0
        S.cursor.location = (0.0, 0.0, 0.0)
        bpy.ops.mch.bar_tool(tool='SUBD')
        bpy.ops.mch.subd_plane_create()
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 1.5
    yield from wait_draws(3)
    from mecha_lab import tool_state as ts2
    ob = C.active_object
    log('tool', ts2.effective_tool(C), 'native', ts2.native_tool_id(C), 'object', ob.name, 'points', len(ob.data.vertices),
        'faces', len(ob.data.polygons), 'mode', C.mode)
    shot('01_plane.png')

    def scr(p_local):
        p = view3d_utils.location_3d_to_region_2d(r, rv, ob.matrix_world @ Vector(p_local))
        return int(r.x + p.x), int(w.height - (r.y + p.y))

    def drag(a_xy, b_xy, mods=()):
        xdo('mousemove', *a_xy)
        yield 0.5
        for m in mods:
            xdo('keydown', m)
        yield 0.2
        xdo('mousedown', 1)
        yield 0.3
        for t in range(1, 11):
            xdo('mousemove', int(a_xy[0] + (b_xy[0] - a_xy[0]) * t / 10), int(a_xy[1] + (b_xy[1] - a_xy[1]) * t / 10))
            yield 0.05
        yield 0.3
        xdo('mouseup', 1)
        yield 0.3
        for m in mods:
            xdo('keyup', m)
        yield 1.0

    def click(xy, mods=()):
        xdo('mousemove', *xy)
        yield 0.5
        for m in mods:
            xdo('keydown', m)
        yield 0.2
        xdo('click', 1)
        yield 0.3
        for m in mods:
            xdo('keyup', m)
        yield 1.0
    me = ob.data
    corner = max(range(len(me.vertices)), key=lambda i: me.vertices[i].co.x + me.vertices[i].co.y)
    c0 = me.vertices[corner].co.copy()
    yield from drag(scr(c0), scr(c0 + Vector((0.6, 0.3, 0.0))))
    c1 = ob.data.vertices[corner].co.copy()
    res['D1'] = (c1 - c0 - Vector((0.6, 0.3, 0.0))).length < 0.08 and C.mode == 'OBJECT'
    log('D1 REAL drag of a corner point: moved by', tuple(round(v, 3) for v in (c1 - c0)), '| mode', C.mode)
    shot('02_point_moved.png')
    # an outline edge: the one on the left (x min)
    me = ob.data
    xs = [v.co.x for v in me.vertices]
    left = [e for e in me.edges if all(abs(me.vertices[i].co.x - min(xs)) < 1e-6 for i in e.vertices)][0]
    mid = (me.vertices[left.vertices[0]].co + me.vertices[left.vertices[1]].co) / 2
    nf0, nv0 = len(me.polygons), len(me.vertices)
    yield from drag(scr(mid), scr(mid + Vector((-0.8, 0.0, 0.0))))
    me = ob.data
    res['D2'] = len(me.polygons) == nf0 + 1 and len(me.vertices) == nv0 + 2 and min(v.co.x for v in me.vertices) < min(xs) - 0.6
    log('D2 REAL drag of an outline edge: faces', nf0, '->', len(me.polygons), '| points', nv0, '->', len(me.vertices),
        '| reaches x', round(min(v.co.x for v in me.vertices), 3))
    shot('03_face_pulled_out.png')
    # Shift + drag the new outline edge: it moves, no new face
    xs = [v.co.x for v in me.vertices]
    left = [e for e in me.edges if all(abs(me.vertices[i].co.x - min(xs)) < 1e-6 for i in e.vertices)][0]
    mid = (me.vertices[left.vertices[0]].co + me.vertices[left.vertices[1]].co) / 2
    nf1 = len(me.polygons)
    ia, ib = left.vertices[0], left.vertices[1]
    log('   before D3 verts', [tuple(round(c, 2) for c in v.co) for v in me.vertices], 'edge', tuple(left.vertices), 'view', tuple(round(c, 2) for c in rv.view_location))
    yield from drag(scr(mid), scr(mid + Vector((0.0, 0.5, 0.0))), mods=('shift',))
    me = ob.data
    log('   after D3 verts', [tuple(round(c, 2) for c in v.co) for v in me.vertices], 'view', tuple(round(c, 2) for c in rv.view_location), 'last op', [o.bl_idname for o in C.window_manager.operators[-3:]])
    now_y = (me.vertices[ia].co.y + me.vertices[ib].co.y) / 2
    res['D3'] = len(me.polygons) == nf1 and abs(now_y - mid.y - 0.5) < 0.08
    log('D3 REAL Shift + drag of an edge: faces', nf1, '->', len(me.polygons), '| edge middle y', round(mid.y, 3), '->',
        round(now_y, 3))
    # Ctrl + click an edge: crease
    e0 = me.edges[0]
    mid = (me.vertices[e0.vertices[0]].co + me.vertices[e0.vertices[1]].co) / 2
    yield from click(scr(mid), mods=('ctrl',))
    att = ob.data.attributes.get(subd_plane.CREASE_ATTR)
    cv = att.data[0].value if att is not None else 0.0
    res['D4'] = cv > 0.0
    log('D4 REAL Ctrl + click an edge: crease', round(cv, 3))
    shot('04_crease.png')
    # Alt + click the far left point: removed
    me = ob.data
    vi = min(range(len(me.vertices)), key=lambda i: me.vertices[i].co.x)
    nv2 = len(me.vertices)
    yield from click(scr(me.vertices[vi].co), mods=('alt',))
    res['D5'] = len(ob.data.vertices) == nv2 - 1 and len(ob.data.polygons) >= 1
    log('D5 REAL Alt + click a point: points', nv2, '->', len(ob.data.vertices))
    shot('05_point_removed.png')
    # Ctrl+Z: the point is back
    xdo('mousemove', int(r.x + r.width * 0.5), int(w.height - (r.y + r.height * 0.2)))
    yield 0.4
    xdo('key', 'ctrl+z')
    yield 1.5
    ob = bpy.data.objects.get(ob.name) or C.active_object
    res['D6'] = len(ob.data.vertices) == nv2 and C.mode == 'OBJECT'
    log('D6 REAL Ctrl+Z: points', len(ob.data.vertices), '| mode', C.mode)
    # 0.24.232 a point brought onto another snaps and joins it; with Ctrl held it does not
    me = ob.data
    lone = min(range(len(me.vertices)), key=lambda i: me.vertices[i].co.x)          # the far left point
    nbr = {v for e in me.edges if lone in e.vertices for v in e.vertices if v != lone}      # (a corner joined to its
    goal = min(nbr, key=lambda i: (me.vertices[i].co - me.vertices[lone].co).length)      # neighbour: a triangle)
    a_co, g_co = me.vertices[lone].co.copy(), me.vertices[goal].co.copy()
    nv3 = len(me.vertices)
    off = (g_co - a_co)
    yield from drag(scr(a_co), scr(g_co + off.normalized() * 0.03), mods=('ctrl',))     # (near, Ctrl: no snap)
    me = ob.data
    no_snap = len(me.vertices) == nv3 and (me.vertices[lone].co - g_co).length > 0.01
    log('D8 REAL Ctrl + drag next to a point: points', nv3, '->', len(me.vertices), '| apart by',
        round((me.vertices[lone].co - g_co).length, 3))
    xdo('key', 'ctrl+z')
    yield 1.5
    ob = bpy.data.objects.get(ob.name) or C.active_object
    me = ob.data
    log('   D7 before', [tuple(round(c, 2) for c in v.co) for v in me.vertices], [tuple(p.vertices) for p in me.polygons], 'lone', lone, 'goal', goal)
    yield from drag(scr(me.vertices[lone].co), scr(g_co + off.normalized() * 0.03))      # (near: snaps, joins)
    me = ob.data
    log('   D7 after', [tuple(round(c, 2) for c in v.co) for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
    joined = len(me.vertices) == nv3 - 1 and any((v.co - g_co).length < 1e-5 for v in me.vertices) \
        and len(me.polygons) == 2 and sorted(len(p_.vertices) for p_ in me.polygons) == [3, 4]
    res['D7'] = joined
    res['D8'] = no_snap
    log('D7 REAL drag of a point onto another (let go a little off it): points', nv3, '->', len(me.vertices),
        '| faces', len(me.polygons))
    shot('06_points_joined.png')
    names = {'D7': 'a point dragged near another snaps onto it and joins it when let go (the quad becomes a triangle)',
             'D8': 'with Ctrl held while dragging it does not snap',
             'D1': 'a REAL drag of a point moves it (Object Mode)',
             'D2': 'a REAL drag of an outline edge pulls a new face out of it',
             'D3': 'a REAL Shift + drag of an edge moves it (no new face)',
             'D4': 'a REAL Ctrl + click on an edge creases it',
             'D5': 'a REAL Alt + click on a point removes it',
             'D6': 'Ctrl+Z brings it back; never Edit Mode'}
    n = 0
    for kk_ in sorted(names):
        ok = bool(res.get(kk_))
        n += ok
        log('PASS' if ok else 'FAIL', kk_, names[kk_])
    log(f'{n}/{len(names)} passed')
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
