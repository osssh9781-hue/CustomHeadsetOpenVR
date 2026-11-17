"""Real window 0.24.214: the top bar's first row is the same for every tool - screenshots of five tools, the cells'
positions compared in the real viewport; a REAL click on a first-row cell (Selected) and on a tool's own cell below
(Base Mesh: Chamfer) lands; a greyed cell does nothing."""
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
    from mecha_lab import i18n, top_bar, base_mesh
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
    i18n.force('KO')
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=32, radius=1.0)
        a.spaces.active.show_region_ui = False
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')

    def bar():
        with C.temp_override(window=w, area=a, region=r):
            return top_bar.items(C, r.width, r.height, ui_factor(C, r))

    def bar_rows(its):
        ys = sorted({round(i.y, 1) for i in its if i.kind not in {'card', 'vrule'}}, reverse=True)
        return [[(i.kind, i.label, round(i.x, 1), round(i.w, 1)) for i in its
                 if round(i.y, 1) == y and i.kind not in {'card', 'vrule'}] for y in ys]
    rows = {}
    for n, tool in enumerate(('CUT', 'BASE', 'CDRAPE', 'SMART', 'PLATE')):
        with C.temp_override(window=w, area=a, region=r):
            bpy.ops.mch.bar_tool(tool=tool)
        yield 1.5
        yield from wait_draws(3)
        rows[tool] = bar_rows(bar())
        shot(f'0{n + 1}_bar_{tool}.png')
    # ... also when the tool's own rows make the bar tall (Base Mesh: Bevel on both sides, each its own width)
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool='BASE')
        d0 = base_mesh.scene_defaults(C)
        d0.profile, d0.bevel_sides, d0.bevel_link = 'BEVEL', 'BOTH', False
    yield 1.5
    yield from wait_draws(3)
    rows['BASE tall'] = bar_rows(bar())
    shot('07_bar_BASE_tall.png')
    d0.profile, d0.bevel_sides, d0.bevel_link = 'FLAT', 'TOP', True
    n_common = 0
    while n_common < min(len(v) for v in rows.values()) and all(v[n_common] == rows['CUT'][n_common] for v in rows.values()):
        n_common += 1
    labels = [c[1] for row_ in rows['CUT'][:n_common] for c in row_]
    res['A1'] = n_common >= 1 and all(x in labels for x in ('Lasso', 'Sketch', 'Slow Line', 'Selected', 'From Surface',
                                                            'Auto Apply', 'Ortho'))
    log('A1 the common rows in the real viewport (5 tools):', n_common, 'row(s) the same |', len(labels), 'cells | region', r.width)
    # a first-row cell: Selected (Target) on Cut
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool='CUT')
    yield 1.5
    yield from wait_draws(3)
    S.mch_cut.targets = 'AUTO'
    it = next((i for i in bar() if i.kind == 'seg' and i.prop == 'targets' and i.label == 'Selected'), None)
    if it is not None:
        yield from press(it)
    yield 0.8
    res['A2'] = it is not None and S.mch_cut.targets == 'SELECTED'
    log('A2 REAL click on Selected (first row):', S.mch_cut.targets)
    S.mch_cut.targets = 'AUTO'
    # a greyed cell on Smart Move does nothing
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool='SMART')
    yield 1.5
    yield from wait_draws(3)
    shape0, tool0 = S.mch_brush.shape, None
    from mecha_lab import tool_state as ts
    tool0 = ts.effective_tool(C)
    it = next((i for i in bar() if i.kind == 'ibtn' and not i.enabled), None)
    if it is not None:
        yield from press(it)
    yield 0.8
    res['A3'] = it is not None and S.mch_brush.shape == shape0 and ts.effective_tool(C) == tool0 == 'SMART'
    log('A3 REAL click on a greyed shape (Smart Move): shape', shape0, '->', S.mch_brush.shape, '| tool', ts.effective_tool(C))
    # the tool's own row: Base Mesh, Chamfer
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool='BASE')
        d = base_mesh.scene_defaults(C)
        d.profile = 'FLAT'
    yield 1.5
    yield from wait_draws(3)
    it = next((i for i in bar() if i.kind == 'seg' and i.label == 'Chamfer' and i.action and i.action[0] == 'op'), None)
    if it is not None:
        yield from press(it)
    yield 1.0
    res['A4'] = it is not None and d.profile == 'CHAMFER'
    log('A4 REAL click on Chamfer (Base Mesh, its own row):', d.profile)
    shot('06_bar_BASE_chamfer.png')
    i18n.force(None)
    names = {'A1': 'the common row(s): the same cells at the same places for 5 tools in the real viewport',
             'A2': 'a REAL click on a first-row cell lands (Target: Selected)',
             'A3': 'a greyed cell does nothing', 'A4': 'a REAL click on the tool\'s own row lands (Base Mesh: Chamfer)'}
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
