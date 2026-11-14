"""Real window (0.24.169, user: "머리카락 색 바뀌게 해 줘", "생머리, 파마머리, 수염, 동물털 프리셋", "머리카락도 엔터 치면
어플라이 되게", "머리카락은 왜 미러가 안 돼?"): Creature Hair by REAL clicks, drags and keys (xdotool) on a head with a
live Mirror:

  1. a REAL click on the window's "Perm" style, a REAL lasso on the head's +X side - permed hair, mirrored to -X too
  2. a REAL click on the colour preset "Blonde" - the hair's own material blonde (the strands not rebuilt)
  3. a REAL Enter - the hair applied
  4. another hair, then the head made active (as when clicked in the layers): a REAL Enter still applies the hair
  5. the actions' tool tile (user: "이거 왜 컷인데 퍼로 떠?"): with Fur remembered and the viewport on Cut it says
     Cut ON; REAL clicks on it: Cut OFF, Cut ON
  6. two Scale Lines and a Greeble Line selected (user: "스케일 ... 다 선택해서 엔터 누르면 어플라이, 그리블도"): a REAL
     Enter applies all three
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
    from mecha_lab import creature_hair as ch, mirror_tools, symmetry
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
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32, location=(0, 0, 0))
        head = C.active_object
        head.name = 'Head'
        bpy.ops.object.shade_smooth()
        symmetry.set_mode(C, head, 'MIRROR')
        for o in C.selected_objects:
            o.select_set(False)
        C.view_layer.objects.active = None
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((math.radians(55), 0.0, 0.0)).to_quaternion()
        rv.view_location = (0.0, 0.0, 0.2)
        rv.view_distance = 5.2
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True
        sp3.shading.type = 'SOLID'
        sp3.shading.color_type = 'MATERIAL'
        bpy.ops.mch.bar_tool(tool='HAIR')
        bpy.ops.mch.side_page(page='TOOL')
    yield 2.0
    S.mch_brush.shape = 'STROKE'
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 1.0
    # 1: Perm, a lasso on the +X side
    it = yield from scrolled_item('Perm')
    if it is not None:
        yield from press(it)
    yield 1.0
    st = S.mch_hair
    log('1 Perm cell', it is not None, '- next hair style', st.style, 'curl', round(st.curl, 2))
    yield from real_outline([screen_xy(Vector((0.4 + 0.25 * math.cos(t), 0.25 * math.sin(t), 0.88)))
                             for t in np.linspace(0, 2 * math.pi, 36, endpoint=False)])
    yield 2.0
    hair = next((o for o in S.objects if o.get(ch.SRC_KEY)), None)
    mod = hair.modifiers.get(mirror_tools.MOD_NAME) if hair else None
    xs = np.array([0.0])
    if hair is not None:
        ev = hair.evaluated_get(C.evaluated_depsgraph_get()).data
        xs = np.array([hair.matrix_world @ v.co for v in ev.vertices])[:, 0]
    log('1b hair', hair and hair.name, 'style', hair and hair.mch_hair.style, 'curl', hair and round(hair.mch_hair.curl, 2),
        '- mirror', mod is not None, '- x', round(float(xs.min()), 2), '..', round(float(xs.max()), 2))
    res['1 a REAL click on "Perm" + a REAL lasso on the +X side: permed hair, mirrored to -X like the head'] = (
        it is not None and hair is not None and hair.mch_hair.style == 'PERM' and hair.mch_hair.curl > 0
        and mod is not None and xs.min() < -0.2 and xs.max() > 0.2)
    shot('1_perm_mirrored.png')
    # 2: Blonde
    nf = len(hair.data.polygons) if hair else 0
    it = yield from scrolled_item('Blonde')
    if it is not None:
        yield from press(it)
    yield 1.0
    root = tuple(hair.mch_hair.root_colour) if hair else (0, 0, 0)
    blonde = next(c for c in ch.COLOUR_PRESETS if c[0] == 'BLONDE')
    mat0 = hair.data.materials[0] if hair else None
    log('2 Blonde cell', it is not None, '- root', [round(v, 3) for v in root], '- material', mat0 and mat0.name,
        '- faces', nf, '->', len(hair.data.polygons) if hair else 0)
    res['2 a REAL click on "Blonde": the hair\'s own material blonde, the strands not rebuilt'] = (
        it is not None and hair is not None and np.allclose(root, blonde[2], atol=1e-4)
        and mat0 is not None and mat0.name.startswith('MCH Hair - ') and len(hair.data.polygons) == nf)
    shot('2_blonde.png')
    # 3: Enter
    w, a, r = view3d()
    xdo('mousemove', int(r.x + r.width * 0.4), int(w.height - (r.y + r.height * 0.5)))
    yield 0.5
    xdo('key', 'Return')
    yield 2.0
    log('3 after Enter: live', hair.mch_hair.live if hair else None, '- outline kept', bool(hair and hair.get(ch.SRC_KEY)))
    res['3 a REAL Enter: the hair applied (no longer live)'] = hair is not None and not hair.mch_hair.live
    # 4: another hair, then the head made active (as when it is clicked in the layers) - Enter still applies the hair
    yield from real_outline([screen_xy(Vector((-0.1 + 0.25 * math.cos(t), -0.3 + 0.2 * math.sin(t), 0.92)))
                             for t in np.linspace(0, 2 * math.pi, 36, endpoint=False)])
    yield 2.0
    hair2 = next((o for o in S.objects if o.get(ch.SRC_KEY)), None)
    with C.temp_override(window=w, area=a, region=r):
        for o in C.selected_objects:
            o.select_set(False)
        head.select_set(True)
        C.view_layer.objects.active = head
    yield 1.0
    xdo('mousemove', int(r.x + r.width * 0.4), int(w.height - (r.y + r.height * 0.5)))
    yield 0.5
    xdo('key', 'Return')
    yield 2.0
    log('4 second hair', hair2 and hair2.name, '- the head active, after Enter: live', hair2.mch_hair.live if hair2 else None)
    res['4 a second hair, the head clicked active, a REAL Enter in the Hair tool: the hair just made applied'] = (
        hair2 is not None and not hair2.mch_hair.live)
    # 5: the tool tile (user: "이거 왜 컷인데 퍼로 떠?"): Fur remembered, the viewport switched to Cut as opening a file
    # does - the tile says Cut; a REAL click on it: off (Select) and it offers Cut; a REAL click again: Cut on
    from mecha_lab import ui_bars

    def tile():
        w_, a_, r_ = view3d()
        with C.temp_override(window=w_, area=a_, region=r_):
            its = ui_bars.dock_items(C, r_.width, r_.height, ui_factor(C, r_))
        return next((i for i in its if getattr(i, 'label', '').endswith((' ON', ' OFF'))), None)
    S.mch_settings.mch_active_tool = 'FUR'
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.wm.tool_set_by_id(name='mecha.cut', space_type='VIEW_3D')
    yield from wait_draws(2)
    t1 = tile()
    l1 = t1.label if t1 else None
    if t1 is not None:
        yield from press(t1)
    yield from wait_draws(2)
    t2 = tile()
    l2 = t2.label if t2 else None
    if t2 is not None:
        yield from press(t2)
    yield from wait_draws(2)
    t3 = tile()
    l3 = t3.label if t3 else None
    log('5 the tile: in Cut (Fur remembered)', repr(l1), '- clicked', repr(l2), '- clicked again', repr(l3))
    res['5 the tool tile shows the tool in use (Cut ON, not Fur), a REAL click: Cut OFF, again: Cut ON'] = (
        l1 == 'Cut ON' and l2 == 'Cut OFF' and l3 == 'Cut ON')
    shot('3_tile.png')
    # 6: two Scale Lines and a Greeble Line (user: "스케일 어제 만든 것도 다 선택해서 엔터 누르면 어플라이 되게, 그리블도"):
    # all selected, a REAL Enter - all three applied
    from mecha_lab import greeble_line as gl
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=48, ring_count=24, location=(0.0, 6.0, 0.0))
        ball = C.active_object
        lines = []
        for which, kind, yy in (('SCALES', 'CREATURE', -0.6), ('SCALES', 'CREATURE', -0.2), ('MECH', 'MECH', 0.3)):
            gl.make_starters(C, ball, which)
            stg = gl.settings(S, kind)
            pts, nrm = [], []
            for tt in np.linspace(-0.9, 0.9, 40):
                v = Vector((math.sin(tt), yy, math.cos(tt))).normalized()
                pts.append(tuple(v))
                nrm.append(tuple(v))
            ln = gl.new_line(C, ball, pts, nrm, gl.picked(stg), stg, kind)
            gl.rebuild(ln, C)
            lines.append(ln)
        for o in C.selected_objects:
            o.select_set(False)
        for ln in lines:
            ln.select_set(True)
        C.view_layer.objects.active = lines[0]
        bpy.ops.mch.bar_tool(tool='CGREEBLE')
    yield 2.0
    w, a, r = view3d()
    xdo('mousemove', int(r.x + r.width * 0.4), int(w.height - (r.y + r.height * 0.5)))
    yield 0.5
    xdo('key', 'Return')
    yield 2.5
    left = [o.name for o in S.objects if gl.is_line(o)]
    names = [o.name for o in lines if o.name in bpy.data.objects]
    log('6 lines', len(lines), 'selected, after Enter still live:', left, '- now', names)
    res['6 two Scale Lines and a Greeble Line selected, a REAL Enter: all three applied (real meshes)'] = (
        len(lines) == 3 and not left)
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
