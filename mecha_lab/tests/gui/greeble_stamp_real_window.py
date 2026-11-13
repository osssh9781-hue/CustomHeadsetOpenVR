"""Real window (0.24.154, user: "쉬프트 누르고 라쏘로 그리면 그 스탬프 베이스로 만들어 줘, 그리블이랑 크리쳐 둘 다"): in
Greeble Line and Scale Line a REAL Shift + drag (xdotool, Free Draw) makes a part from the outline - then a REAL drag
lays it along a line.

  1. Greeble Line: the top bar's Shift+Draw shapes; REAL clicks on the window's stamp profiles (Dome, then Chamfer)
  2. a REAL Shift + drag round an octagon on the sphere: a Chamfer Base Mesh stamp as big as drawn, beside the sphere,
     ticked alone; no line made
  3. a REAL drag: a Greeble Line of that stamp
  4. Scale Line: a REAL Shift + drag round a pointed scale: a Puff stamp in Scale Line's list (Greeble Line's untouched);
     REAL Ctrl+Z takes it away, Ctrl+Shift+Z brings it back; a REAL drag: a Scale Line of it
  5. shots with the wireframe (solid, Cycles)
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



def region_xy(win_xy):
    w, a, r = view3d()
    return win_xy[0] - r.x, (w.height - win_xy[1]) - r.y


def shift_draw(pts):
    """A REAL Shift + drag (Free Draw) through the window points ``pts`` (closed back to the first)."""
    xdo('mousemove', *pts[0])
    yield 0.4
    xdo('keydown', 'shift')
    yield 0.3
    xdo('mousedown', 1)
    yield 0.3
    for x, y in pts[1:] + [pts[0]]:
        xdo('mousemove', x, y)
        yield 0.05
    yield 0.3
    xdo('mouseup', 1)
    yield 0.3
    xdo('keyup', 'shift')
    yield 2.0


def ring_px(c, rx, ry, n=28, point=0.0):
    """Window points round ``c``: an ellipse rx x ry (px); ``point`` > 0 pulls its right end out to a tip (a scale)."""
    out = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        if point > 0 and math.cos(t) > 0:
            x *= 1.0 + point * math.cos(t) ** 4
            y *= 1.0 - 0.6 * math.cos(t) ** 4
        out.append((c[0] + x, c[1] - y))
    dense = []                                     # (a point every 6 px: Free Draw's smoothing keeps the corners)
    for i, q in enumerate(out):
        nq = out[(i + 1) % len(out)]
        k = max(1, int(math.dist(q, nq) / 6.0))
        dense += [(int(q[0] + (nq[0] - q[0]) * j / k), int(q[1] + (nq[1] - q[1]) * j / k)) for j in range(k)]
    return dense


def world_width(c_win, half_px, depth_pt):
    """World distance across ``2 half_px`` (horizontal, window px) at the depth of ``depth_pt``."""
    from bpy_extras import view3d_utils
    w, a, r = view3d()
    rv = a.spaces.active.region_3d
    l = view3d_utils.region_2d_to_location_3d(r, rv, region_xy((c_win[0] - half_px, c_win[1])), depth_pt)
    rr = view3d_utils.region_2d_to_location_3d(r, rv, region_xy((c_win[0] + half_px, c_win[1])), depth_pt)
    return (rr - l).length


def sphere_pt(az, el):
    return Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el))) * 0.995


def real_drag_line(el, az0=-2.8, az1=-1.2, n=14):
    xy = [screen_xy(sphere_pt(az0 + (az1 - az0) * i / (n - 1), el)) for i in range(n)]
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


def flow():
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
    from mecha_lab import greeble_line as gl, tool_state as ts, top_bar
    res = {}
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32, location=(0, 0, 0))
        body = C.active_object
        bpy.ops.object.shade_smooth()
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((1.25, 0.0, -0.45)).to_quaternion()
        rv.view_location = (0.9, 0.0, 0.3)
        rv.view_distance = 6.5
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True                  # (the wireframe always shown with a result)
        bpy.ops.mch.bar_tool(tool='GREEBLE')
        bpy.ops.mch.side_page(page='TOOL')
    yield 1.0
    S.mch_brush.shape = 'STROKE'                           # (Free Draw: Shift + drag round it)
    mech, crea = gl.settings(S, 'MECH'), gl.settings(S, 'CREATURE')
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 1.5
    with C.temp_override(window=w, area=a, region=r):
        tool_now = ts.effective_tool(C)
        titles = [g[0] for g in top_bar.groups(C, 'GREEBLE')]
    log('tool', tool_now, 'top bar groups', titles)
    res['1 Greeble Line on; the top bar has the Shift+Draw shapes'] = tool_now == 'GREEBLE' and 'Shift+Draw' in titles
    it = yield from scrolled_item('Dome')
    if it is not None:
        yield from press(it)
    dome = mech.stamp_profile
    it = yield from scrolled_item('Chamfer')
    if it is not None:
        yield from press(it)
    log('window stamp profile clicks: Dome ->', dome, ', Chamfer ->', mech.stamp_profile)
    res['1 REAL clicks on the window\'s stamp profiles: Dome, then Chamfer'] = dome == 'DOME' and mech.stamp_profile == 'CHAMFER'
    shot('0_window.png')
    # 2: Shift + drag round an octagon on the sphere's upper left
    p_on = sphere_pt(-2.3, 0.5)                    # (the side facing the view: azimuth about -2)
    c = screen_xy(p_on)
    pts = ring_px(c, 80, 50, n=8)
    before = set(bpy.data.objects)
    yield from shift_draw(pts)
    new = [o for o in bpy.data.objects if o not in before]
    stamp = next((o for o in new if gl.is_stamp(o)), None)
    want = world_width(c, 80, p_on)
    got = stamp.dimensions.x if stamp else 0.0
    log('new objects', [o.name for o in new], 'stamp', stamp and stamp.name, 'width', round(got, 3), 'drawn', round(want, 3),
        'profile', stamp and stamp.mch_base.profile, 'picked', [o.name for o in gl.picked(mech)],
        'loc', stamp and tuple(round(v, 2) for v in stamp.matrix_world.translation))
    res['2 a REAL Shift + drag round an octagon: a Chamfer Base Mesh stamp as wide as drawn (within 12 %), beside the '
        'sphere, ticked alone, no line made'] = (
        stamp is not None and len(new) == 1 and stamp.mch_base.profile == 'CHAMFER' and abs(got - want) < want * 0.12
        and gl.picked(mech) == [stamp] and stamp.matrix_world.translation.x > 1.2
        and not any(gl.is_line(o) for o in S.objects))
    # 3: a REAL drag: a line of it
    yield from real_drag_line(0.12)
    lines = [o for o in S.objects if gl.is_line(o)]
    ln = lines[0] if lines else None
    log('lines', [o.name for o in lines], 'parts', ln and len(ln.data.vertices), 'of', ln and [o.name for o in gl.line_parts(ln)])
    res['3 a REAL drag: a Greeble Line of the stamp'] = (len(lines) == 1 and gl.line_parts(ln) == [stamp]
                                                        and len(ln.data.vertices) >= 2)
    yield 1.0
    shot('1_greeble_stamp_wire.png')
    # 4: Scale Line
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool='CGREEBLE')
    yield 1.0
    S.mch_brush.shape = 'STROKE'
    yield 1.0
    with C.temp_override(window=w, area=a, region=r):
        titles = [g[0] for g in top_bar.groups(C, 'CGREEBLE')]
    p_on = sphere_pt(-1.7, -0.35)
    c = screen_xy(p_on)
    before = set(bpy.data.objects)
    mech_list = [it_.ob for it_ in mech.parts]
    yield from shift_draw(ring_px(c, 45, 32, n=30, point=0.8))
    new = [o for o in bpy.data.objects if o not in before]
    sst = next((o for o in new if gl.is_stamp(o)), None)
    log('Scale Line: top bar', titles, '- new', [o.name for o in new], 'profile', sst and sst.mch_base.profile,
        'picked', [o.name for o in gl.picked(crea)], 'faces', sst and len(sst.data.polygons))
    res['4 Scale Line: a REAL Shift + drag round a pointed scale: a Puff stamp in Scale Line\'s list (ticked alone), '
        'Greeble Line\'s list untouched'] = (
        'Shift+Draw' in titles and sst is not None and sst.mch_base.profile == 'PUFF' and gl.picked(crea) == [sst]
        and [it_.ob for it_ in mech.parts] == mech_list)
    name = sst.name if sst else ''
    xdo('mousemove', *screen_xy(sphere_pt(-2.0, 0.0)))
    yield 0.3
    xdo('key', 'ctrl+z')
    yield 2.0
    gone = name not in bpy.data.objects
    xdo('key', 'ctrl+shift+z')
    yield 2.0
    back = name in bpy.data.objects
    crea = gl.settings(C.scene, 'CREATURE')
    sst = bpy.data.objects.get(name)
    log('Ctrl+Z: stamp gone', gone, '- Ctrl+Shift+Z: back', back, '- in the list', [o.name for o in gl.picked(crea)])
    res['4 REAL Ctrl+Z takes the stamp away, Ctrl+Shift+Z brings it back (in the list again)'] = (
        gone and back and gl.picked(crea) == [sst])
    yield from real_drag_line(-0.6, az0=-2.9, az1=-1.1, n=16)
    slines = [o for o in C.scene.objects if gl.is_line(o) and o.mch_greeble_line.kind == 'CREATURE']
    sl = slines[0] if slines else None
    log('scale lines', [o.name for o in slines], 'parts', sl and len(sl.data.vertices), 'of', sl and [o.name for o in gl.line_parts(sl)])
    res['4 a REAL drag: a Scale Line of the scale stamp'] = (len(slines) == 1 and gl.line_parts(sl) == [sst]
                                                            and len(sl.data.vertices) >= 2)
    yield 1.0
    shot('2_scale_stamp_wire.png')
    S = C.scene
    S.render.engine = 'CYCLES'
    S.cycles.preview_samples = 8
    w, a, r = view3d()
    a.spaces.active.shading.type = 'RENDERED'
    yield 25.0
    shot('3_rendered_wire.png')
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
