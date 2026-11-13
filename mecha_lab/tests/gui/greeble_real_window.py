"""Real window (0.24.150): Greeble Line by REAL clicks and a REAL drag (xdotool) in the MECHA LAB workspace.

  1. the tool picked; the right panel (Tool page) shows its window: a REAL click on Pick Part, then REAL clicks on two
     meshes in the 3D view (eyedropper), Esc: both in the parts list
  2. a REAL drag across a sphere: a Greeble Line - the parts laid one after another along it, on the sphere, the
     line selected (the window shows its settings)
  3. shots with the wireframe
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
    from mecha_lab import greeble_line as gl, tool_state as ts
    res = {}
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32, location=(0, 0, 0))
        body = C.active_object
        bpy.ops.object.shade_smooth()
        parts = []
        for name, sx, sy, sz, loc in (('PartA', 0.22, 0.12, 0.07, (2.0, -0.6, 0.0)), ('PartB', 0.12, 0.2, 0.1, (2.0, 0.6, 0.0))):
            me = bpy.data.meshes.new(name)
            bm = bmesh.new()
            bmesh.ops.create_cube(bm, size=1.0)
            for v in bm.verts:
                v.co.x *= sx
                v.co.y *= sy
                v.co.z = (v.co.z + 0.5) * sz
            bm.to_mesh(me)
            bm.free()
            ob = bpy.data.objects.new(name, me)
            S.collection.objects.link(ob)
            ob.location = loc
            ob.scale = (3.0, 3.0, 3.0)                       # (big enough to click; the line lays them x 1/3)
            parts.append(ob)
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((1.15, 0.0, 0.3)).to_quaternion()
        rv.view_location = (0.7, 0.0, 0.0)
        rv.view_distance = 6.0
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True                  # (the wireframe always shown with a result)
        bpy.ops.mch.bar_tool(tool='GREEBLE')
        bpy.ops.mch.side_page(page='TOOL')
    st = gl.settings(S)
    st.scale = 1.0 / 3.0
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 2.0
    with C.temp_override(window=w, area=a, region=r):
        tool_now = ts.effective_tool(C)
    log('tool', tool_now)
    it = yield from scrolled_item('Pick Part')
    log('Pick Part cell', it is not None)
    if it is None:
        log('ERROR no Pick Part cell')
        bpy.ops.wm.quit_blender()
        return
    shot('0_window.png')
    yield from press(it)
    yield 0.8
    for ob in parts:
        x, y = screen_xy(ob.matrix_world @ Vector((0, 0, 0.04)))
        xdo('mousemove', x, y)
        yield 0.4
        xdo('click', 1)
        yield 0.8
    xdo('key', 'Escape')
    yield 0.8
    got = [it_.ob for it_ in st.parts]
    log('parts list', [o.name for o in got if o])
    res['1 the tool on; REAL clicks: Pick Part, then the two meshes in the 3D view - both in the parts list'] = (
        tool_now == 'GREEBLE' and got == parts)
    # a REAL drag across the sphere (its front, a curve)
    path = []
    for i in range(14):
        t = -0.9 + i * 0.13
        path.append((math.cos(t) * 0.995 * math.cos(0.25), math.sin(t) * 0.995 * math.cos(0.25), 0.995 * math.sin(0.25)))
    xy = [screen_xy(p) for p in path]
    xdo('mousemove', *xy[0])
    yield 0.5
    xdo('mousedown', 1)
    yield 0.4
    for x, y in xy[1:]:
        xdo('mousemove', x, y)
        yield 0.1
    yield 0.3
    xdo('mouseup', 1)
    yield 1.5
    lines = [o for o in S.objects if gl.is_line(o)]
    ln = lines[0] if lines else None
    n = len(ln.data.vertices) if ln else 0
    log('lines', len(lines), 'parts', n, 'active', C.view_layer.objects.active and C.view_layer.objects.active.name)
    res['2 a REAL drag on the sphere: a Greeble Line on it, the parts along it, the line selected'] = (
        len(lines) == 1 and ln.parent == body and n >= 4 and C.view_layer.objects.active == ln)
    ok_on = False
    if ln is not None:
        locs = [ln.matrix_world @ v.co for v in ln.data.vertices]
        ok_on = all(0.9 < p.length < 1.1 for p in locs)
        log('part origins from the centre', [round(p.length, 3) for p in locs][:8])
    res['2 ... the parts on the sphere (their origins about 1 from its centre)'] = ok_on
    yield 1.0
    shot('1_line_wire.png')
    it = yield from scrolled_item('Gap')
    it2 = yield from scrolled_item('Use Picked Parts')
    log('the window shows the line\'s settings (Gap, Use Picked Parts)', it is not None, it2 is not None)
    res['3 the window shows the selected line\'s settings'] = it is not None and it2 is not None
    # a REAL click on a part's row: not used any more (the toggle), again: used
    it3 = yield from scrolled_item('PartA')
    if it3 is not None:
        yield from press(it3)
    yield 0.5
    off = not st.parts[0].use
    if it3 is not None:
        it3 = yield from scrolled_item('PartA')
        yield from press(it3)
    yield 0.5
    res['3 a REAL click on a part\'s row: not used / used again'] = off and st.parts[0].use
    S.render.engine = 'CYCLES'
    S.cycles.preview_samples = 6
    sp3.shading.type = 'RENDERED'
    yield 20.0
    shot('2_rendered_wire.png')
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
