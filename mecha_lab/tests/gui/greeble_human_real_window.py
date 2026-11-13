"""Real window (0.24.151, user: "인간 바디 + 하이폴리곤으로 테스트"): Greeble Line on a high-poly human body
(tools_dev/make_test_human.py, Subdivision 5: 0.94 M faces) by REAL clicks and REAL drags (xdotool).

  1. a REAL click on Starter Parts (the right panel) with the body active: five parts sized to the body
  2. REAL drags: four lines across the chest, one down the belly - each a Greeble Line on the body, the parts on it;
     the time from the press to the first parts shown (the first stroke includes Blender building its search tree);
     one more drag that STARTS ON parts already laid: still a line on the body (through the parts)
  3. (user: "벽에 붙는 방향을 내가 맘대로 조절하게 해 줘") a REAL click on Up +X in the window: the selected line's parts
     on their side (their +X out of the body)
  4. shots: Solid with the wireframe, Rendered (Cycles)
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
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools_dev'))
    import make_test_human as mth
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
    from mecha_lab import greeble_line as gl
    res = {}
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        body = mth.build(5, clear=False)
        for o in S.objects:
            o.select_set(False)
        body.select_set(True)
        C.view_layer.objects.active = body
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((1.45, 0.0, 0.25)).to_quaternion()
        rv.view_location = (0.0, 0.0, 1.3)
        rv.view_distance = 1.3
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True                  # (the wireframe always shown with a result)
        bpy.ops.mch.bar_tool(tool='GREEBLE')
        bpy.ops.mch.side_page(page='TOOL')
    log('body faces', len(body.data.polygons))
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 3.0
    it = yield from scrolled_item('Starter Parts')
    if it is None:
        log('ERROR no Starter Parts cell')
        bpy.ops.wm.quit_blender()
        return
    yield from press(it)
    yield 1.5
    st = gl.settings(S)
    starters = gl.picked(st)
    log('starter parts', [o.name for o in starters], 'size', starters and round(starters[0].scale.x, 3))
    res['1 a REAL click on Starter Parts: five parts sized to the body in the list'] = len(starters) == 5
    st.scale = 0.35
    st.order = 'RANDOM'
    st.rows = 2
    # REAL drags on the body: four ribs across the chest, one down the belly (points on the body, seen from the view)
    caster = gl._caster(C, body)

    def on_body(x, z):
        h = caster.ray_cast((x, -1.0, z), (0.0, 1.0, 0.0))
        return h[0] if h is not None else None
    strokes = [[(x, z) for x in np.linspace(-0.11, 0.11, 12)] for z in (1.26, 1.30, 1.34, 1.38)]
    strokes.append([(0.0, z) for z in np.linspace(1.22, 1.06, 8)])
    done = []
    for k, path in enumerate(strokes):
        pts3 = [p for p in (on_body(x, z) for x, z in path) if p is not None]
        xy = [screen_xy(p) for p in pts3]
        before = {o.name for o in S.objects if gl.is_line(o)}
        xdo('mousemove', *xy[0])
        yield 0.4
        w, a, r = view3d()
        with C.temp_override(window=w, area=a, region=r):
            pk, _first = gl.pick_surface(C, (xy[0][0] - r.x, w.height - xy[0][1] - r.y))
        if pk is None:
            from bpy_extras import view3d_utils
            with C.temp_override(window=w, area=a, region=r):
                rv3d_ = a.spaces.active.region_3d
                rxy = (xy[0][0] - r.x, w.height - xy[0][1] - r.y)
                o_ = view3d_utils.region_2d_to_origin_3d(r, rv3d_, rxy)
                d_ = view3d_utils.region_2d_to_vector_3d(r, rv3d_, rxy).normalized()
                dg_ = C.evaluated_depsgraph_get()
                for it_ in range(8):
                    h_ = S.ray_cast(dg_, o_, d_)
                    log('   ray', it_, h_[0], h_[4] and h_[4].name, tuple(round(c, 4) for c in h_[1]))
                    if not h_[0]:
                        break
                    o_ = h_[1] + d_ * 1e-4
        log(f'stroke {k + 1} start', xy[0], 'pick', pk and (pk[0].name, tuple(round(c, 3) for c in pk[1])),
            'active', C.view_layer.objects.active and C.view_layer.objects.active.name,
            'tool', __import__('mecha_lab').tool_state.effective_tool(C))
        t0 = time.perf_counter()
        xdo('mousedown', 1)
        first = None
        for x, y in xy[1:]:
            xdo('mousemove', x, y)
            yield 0.06
            if first is None:
                new = [o for o in S.objects if gl.is_line(o) and o.name not in before]
                if new and len(new[0].data.vertices):
                    first = time.perf_counter() - t0
        yield 0.2
        xdo('mouseup', 1)
        yield 1.0
        new = [o for o in S.objects if gl.is_line(o) and o.name not in before]
        n = len(new[0].data.vertices) if new else 0
        done.append((n, first))
        log(f'stroke {k + 1}: parts {n}, first parts shown after {first if first is None else round(first, 2)} s')
    # a drag in empty space beside the body with a line selected: nothing moves
    sel0 = C.view_layer.objects.active
    keep = sel0.matrix_world.copy() if sel0 is not None else None
    ex, ey = screen_xy(Vector((0.25, -0.2, 1.62)))      # (beside the head: clear of the panels and the bars)
    xdo('mousemove', ex, ey)
    yield 0.3
    xdo('mousedown', 1)
    for i in range(1, 6):
        xdo('mousemove', ex + i * 25, ey - i * 10)
        yield 0.06
    xdo('mouseup', 1)
    yield 0.8
    res['2 a REAL drag in empty space beside the body (a line selected): nothing moved'] = (
        keep is not None and (sel0.matrix_world.translation - keep.translation).length < 1e-6)
    lines = [o for o in S.objects if gl.is_line(o)]
    res['2 five REAL drags on the 0.94 M-face body: five Greeble Lines on it, parts along each'] = (
        len(lines) == 5 and all(n > 0 for n, _f in done) and all(o.parent == body for o in lines))
    # a drag that starts on the belly line's parts (laid already): through them onto the body
    belly = lines[-1]
    v0 = belly.matrix_world @ belly.data.vertices[len(belly.data.vertices) // 2].co
    nb = caster.nearest(belly.matrix_world.inverted() @ v0)
    start = v0 + (nb[1] * 0.012 if nb else Vector((0, -0.012, 0)))      # (on top of a part there)
    path = [start] + [p for p in (on_body(x, 1.14) for x in np.linspace(0.03, 0.13, 6)) if p is not None]
    xy = [screen_xy(p) for p in path]
    before = {o.name for o in S.objects if gl.is_line(o)}
    xdo('mousemove', *xy[0])
    yield 0.4
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        pk2, first2 = gl.pick_surface(C, (xy[0][0] - r.x, w.height - xy[0][1] - r.y))
    log('drag on laid parts: start', xy[0], 'pick', pk2 and pk2[0].name, 'first', first2 and tuple(round(c, 3) for c in first2),
        'start 3d', tuple(round(c, 3) for c in start), 'path points', len(path))
    xdo('mousedown', 1)
    for x, y in xy[1:]:
        xdo('mousemove', x, y)
        yield 0.08
    yield 0.2
    xdo('mouseup', 1)
    yield 1.0
    new = [o for o in S.objects if gl.is_line(o) and o.name not in before]
    log('a drag starting on laid parts:', 'line' if new else 'none', new and new[0].parent and new[0].parent.name,
        new and len(new[0].data.vertices))
    res['2 a REAL drag starting ON parts already laid: a new line on the body (through the parts)'] = (
        len(new) == 1 and new[0].parent == body and len(new[0].data.vertices) > 0)
    lines = [o for o in S.objects if gl.is_line(o)]
    for o in lines:
        if len(o.data.vertices):
            vs = [o.matrix_world @ v.co for v in o.data.vertices]
            log('line', o.name, 'parent', o.parent and o.parent.name, 'x', round(min(v.x for v in vs), 3),
                round(max(v.x for v in vs), 3), 'z', round(min(v.z for v in vs), 3), round(max(v.z for v in vs), 3))
    worst = 0.0
    for o in lines:
        for v in o.data.vertices:
            p = o.matrix_world @ v.co
            h = caster.nearest(p)
            worst = max(worst, (h[0] - p).length if h else 1.0)
    log('part origins: worst distance from the body', round(worst * 1000, 1), 'mm')
    res['2 ... the parts on the body (their origins within 2 cm - the bottom of a part, its origin in the middle)'] = worst < 0.02
    firsts = [f for _n, f in done if f is not None]
    res['2 ... the parts follow the drag: the first ones shown within 1 s of the press (each stroke)'] = (
        len(firsts) == len(done) and max(firsts) < 1.0)
    yield 1.0
    shot('1_solid_wire.png')
    # Up +X on the selected (last) line: a REAL click in the window
    sel = C.view_layer.objects.active
    it = yield from scrolled_item('+X')
    if it is not None:
        yield from press(it)
    yield 1.0
    ok_up = False
    if sel is not None and gl.is_line(sel):
        from mathutils import Quaternion
        outs = []
        for v, q in zip(sel.data.vertices, sel.data.attributes['mch_rot'].data):
            p = sel.matrix_world @ v.co
            h = caster.nearest(p)
            if h:
                outs.append((Quaternion(q.value).to_matrix() @ Vector((1, 0, 0))).dot(h[1]))
        ok_up = sel.mch_greeble_line.up == 'POS_X' and outs and min(outs) > 0.8
        log('Up +X on', sel.name, 'up', sel.mch_greeble_line.up, 'n', len(outs), ': +X . normal', [round(x_, 2) for x_ in outs],
            'quats', [tuple(round(c, 2) for c in q.value) for q in sel.data.attributes['mch_rot'].data][:3])
    res['3 a REAL click on Up +X: the selected line\'s parts on their side, +X out of the body'] = bool(ok_up)
    yield 1.0
    shot('1b_up_x_wire.png')
    S.render.engine = 'CYCLES'
    S.cycles.preview_samples = 6
    sp3.shading.type = 'RENDERED'
    yield 40.0
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
