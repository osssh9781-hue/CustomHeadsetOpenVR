"""Real window 0.24.221: the bevel tool's Method - Move Points (the default): a REAL drag along an edge of a dense box
moves the points there onto a chamfer, the mesh keeps its faces; a REAL click on the Cut cell of the tool's window,
then a REAL click on another edge: that one is cut by the boolean."""
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
    import bmesh
    from mecha_lab import i18n, bool_bevel as bb, edge_runs as er
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
    i18n.force('EN')
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=2.0)
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=39, use_grid_fill=True)
        me = bpy.data.meshes.new('Box')
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new('Box', me)
        S.collection.objects.link(ob)
        sp3 = a.spaces.active
        sp3.show_region_ui = False
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((1.05, 0.0, 0.6)).to_quaternion()
        rv.view_location = (0.0, 0.0, 0.0)
        rv.view_distance = 11.0
        bpy.ops.mch.bar_tool(tool='BBEVEL')
        bpy.ops.ed.undo_push(message='the box')     # (Ctrl+Z after the bevel stops here, at the box)
        bpy.ops.mch.side_page(page='TOOL')
        for o in C.selected_objects:
            o.select_set(False)
    st = S.mch_bool_bevel
    st.profile, st.width = 'CHAMFER', 0.2
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 3.0
    yield from wait_draws(3)

    def box():
        return bpy.data.objects['Box']               # (looked up each time: Ctrl+Z makes the old reference stale)

    def co():
        arr = np.empty(len(box().data.vertices) * 3)
        box().data.vertices.foreach_get('co', arr)
        return arr.reshape(-1, 3)
    res['A1'] = st.method == 'MOVE' and panel_item('Move Points') is not None and panel_item('Cut') is not None
    log('A1 the tool starts on', st.method, '| Move Points / Cut cells in its window:', panel_item('Move Points') is not None,
        panel_item('Cut') is not None)
    c0 = co()
    f0 = len(box().data.polygons)
    yield from drag([(x, -1.0, 1.0) for x in np.linspace(-0.6, 0.6, 13)])          # along the top front edge
    yield 2.0
    c1 = co()
    mv = np.linalg.norm(c1 - c0, axis=1)
    edge = (np.abs(c0[:, 1] + 1) < 1e-6) & (np.abs(c0[:, 2] - 1) < 1e-6) & (np.abs(c0[:, 0]) < 0.3)
    depth = float(mv[edge].max()) if np.any(edge) else 0.0
    res['A2'] = int((mv > 1e-9).sum()) > 50 and len(box().data.polygons) == f0 and abs(depth - 0.2 / math.sqrt(2)) < 1e-4
    log('A2 REAL drag along the top front edge (Move Points):', int((mv > 1e-9).sum()), 'points moved, faces', f0, '->',
        len(box().data.polygons), '| the edge moved', round(depth, 4), '(a 0.2 chamfer:', round(0.2 / math.sqrt(2), 4), ')')
    shot('01_move_points.png')
    xdo('key', 'ctrl+z')
    yield 2.0
    c2 = co()
    res['A3'] = float(np.abs(c2 - c0).max()) < 1e-6
    log('A3 Ctrl + Z (REAL keys): the mesh is as before', float(np.abs(c2 - c0).max()))
    it = yield from scrolled_item('Cut')
    if it is not None:
        yield from press(it)
    yield 1.0
    f1 = len(box().data.polygons)
    xdo('mousemove', *screen_xy((1.0, 0.0, 1.0)))                               # the top right edge: a click = all of it
    yield from wait_draws(2)
    xdo('click', 1)
    yield 3.0
    st = bpy.context.scene.mch_bool_bevel            # (looked up again: Ctrl+Z made the old reference stale)
    res['A4'] = st.method == 'CUT' and len(box().data.polygons) != f1
    log('A4 REAL click on the Cut cell, then a REAL click on the top right edge: method', st.method, '| faces', f1, '->',
        len(box().data.polygons))
    shot('02_cut.png')
    st.method = 'MOVE'
    i18n.force(None)
    names = {'A1': 'the tool starts on Move Points; Move Points / Cut are cells of its window',
             'A2': 'a REAL drag along an edge: the points there are moved onto the chamfer, the mesh keeps its faces',
             'A3': 'Ctrl + Z takes it back', 'A4': 'Cut (a REAL click on its cell): the boolean bevel as before'}
    n = 0
    for k in sorted(names):
        ok = bool(res.get(k))
        n += ok
        log('PASS' if ok else 'FAIL', k, names[k])
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
