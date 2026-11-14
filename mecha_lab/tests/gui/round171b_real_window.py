"""Real window (0.24.171, user: "클로스 드레이프에서 진공팩마냥 내가 선택한 거 감싸 주는 것도 만들어 주라" / on Wrap This Mesh:
"결과가 별로라네"): Vacuum Pack by REAL clicks and drags (xdotool) in the Cloth Drape window:

  1. three parts selected, a REAL click on "Vacuum Pack Selected" - one live film round them
  2. a REAL drag on the Hug slider (to the left: looser) - the film spans more (the torus's hole closes over)
  3. a REAL click on "Black Latex" - the film's material
  4. a REAL click on "Apply (a plain mesh)" - a plain mesh
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
    from mecha_lab import vacuum_pack as vp
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
        parts = []
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.45, segments=48, ring_count=24, location=(-0.6, 0, 0.45))
        parts.append(C.active_object)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.35, minor_radius=0.12, location=(0.35, 0.1, 0.13))
        parts.append(C.active_object)
        bpy.ops.mesh.primitive_cube_add(size=0.4, location=(-0.1, 0.5, 0.2))
        parts.append(C.active_object)
        for o in C.selected_objects:
            o.select_set(False)
        for o in parts:
            o.select_set(True)
        C.view_layer.objects.active = parts[0]
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((math.radians(55), 0.0, math.radians(25))).to_quaternion()
        rv.view_location = (0.0, 0.1, 0.2)
        rv.view_distance = 3.6
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True
        sp3.shading.type = 'SOLID'
        sp3.shading.color_type = 'MATERIAL'
        S.mch_vacuum.hug, S.mch_vacuum.film = 0.6, 'CLEAR'
        bpy.ops.mch.bar_tool(tool='CDRAPE')
        bpy.ops.mch.side_page(page='TOOL')
    yield 2.0
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 1.0

    def film_state(film):
        dg = C.evaluated_depsgraph_get()
        me = film.evaluated_get(dg).data
        P = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', P)
        P = P.reshape(-1, 3)
        hole = not (np.linalg.norm(P - np.array([0.35, 0.1, 0.13]), axis=1) < 0.12).any()
        return len(P), hole, {m.name for m in me.materials if m}
    # 1
    it = yield from scrolled_item('Vacuum Pack Selected')
    if it is not None:
        yield from press(it)
    yield 3.0
    film = next((o for o in S.objects if vp.is_film(o)), None)
    st1 = film_state(film) if film else None
    log('1 the button', it is not None, '- film', film and film.name, '- parts', film and len(vp.film_parts(film)),
        '- points, hole open, materials', st1)
    res['1 three parts selected, a REAL click on "Vacuum Pack Selected": one live film round them'] = (
        it is not None and film is not None and len(vp.film_parts(film)) == 3 and st1[0] > 3000 and st1[1])
    shot('1_packed.png')
    # 2: Hug slider dragged left
    h0 = film.mch_vacuum.hug if film else None
    it = yield from scrolled_item('Hug')
    if it is not None:
        yield from slider_drag(it, 0.6, -int(it.w * 0.045), steps=10)
    yield 3.0
    h1 = film.mch_vacuum.hug if film else None
    st2 = film_state(film) if film else None
    log('2 Hug slider', it is not None, '- hug', h0, '->', h1, '- points, hole open', st2)
    res['2 a REAL drag on Hug (looser): the film spans the torus\'s hole now'] = (
        it is not None and film is not None and h1 < h0 - 0.2 and not st2[1])
    shot('2_looser.png')
    # 3: Black Latex
    it = yield from scrolled_item('Black Latex')
    if it is not None:
        yield from press(it)
    yield 2.0
    st3 = film_state(film) if film else None
    log('3 Black Latex', it is not None, '- materials', st3 and st3[2])
    res['3 a REAL click on "Black Latex": the film\'s material'] = (
        it is not None and st3 is not None and st3[2] == {'MCH Vacuum Film - Black Latex'})
    shot('3_black.png')
    # 4: Apply
    it = yield from scrolled_item('Apply (a plain mesh)')
    if it is not None:
        yield from press(it)
    yield 2.0
    log('4 Apply', it is not None, '- still live', film and vp.is_film(film), '- modifiers', film and len(film.modifiers),
        '- faces', film and len(film.data.polygons))
    res['4 a REAL click on "Apply (a plain mesh)": a plain mesh'] = (
        it is not None and film is not None and not vp.is_film(film) and not film.modifiers and len(film.data.polygons) > 3000)
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
