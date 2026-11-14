"""Real window (0.24.157, user: "털도 방법이 있니? 내가 지정한 영역에 털이 ... 색은 폴리페인트에서 가져오는 것도"): the Fur
tool by REAL drags (xdotool) on the test human (striped polypaint):

  1. a REAL Free Draw outline on the chest: a fur there (the strands' roots inside what was drawn, coloured by the
     stripes)
  2. a REAL Alt + drag over its left part: that part taken away
  3. a REAL drag on the belly: the same fur, more area
  4. a REAL drag on the window's Length slider: the strands longer
  5. (0.24.159) a REAL click on the window's "Area 1", a REAL drag on its Lie Down: only that area's tilt changes
  6. shots: solid with the wireframe, Cycles
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





sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools_dev'))


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
    yield 2.0


def ring_at(p, rx_px, ry_px, n=40):
    c = screen_xy(p)
    return [(int(c[0] + rx_px * math.cos(2 * math.pi * i / n)), int(c[1] - ry_px * math.sin(2 * math.pi * i / n)))
            for i in range(n)]


def roots_of(fur):
    import numpy as np
    dg = C.evaluated_depsgraph_get()
    cv = fur.evaluated_get(dg).data
    k = len(cv.curves)
    if not k:
        return np.zeros((0, 3))
    pos = np.empty(len(cv.points) * 3, np.float32)
    cv.attributes['position'].data.foreach_get('vector', pos)
    return pos.reshape(k, -1, 3)


def flow():
    import numpy as np
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
    from mecha_lab import creature_fur as cf
    res = {}
    with C.temp_override(window=w, area=a, region=r):
        human = mth.build(3)
        me = human.data
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        ca = me.color_attributes.new('Polypaint', 'FLOAT_COLOR', 'POINT')
        stripe = (np.sin(co[:, 2] * 60.0 + co[:, 0] * 20.0) > 0.3)[:, None]           # (dark stripes on orange)
        ca.data.foreach_set('color', np.where(stripe, [[0.04, 0.03, 0.025, 1]], [[0.85, 0.42, 0.08, 1]]).astype(np.float32).ravel())
        me.color_attributes.active_color = ca
        C.view_layer.objects.active = human
        human.select_set(True)
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((math.radians(88), 0.0, math.radians(8))).to_quaternion()
        rv.view_location = (0.0, 0.0, 1.22)
        rv.view_distance = 1.5
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True
        sp3.shading.type = 'SOLID'
        bpy.ops.mch.bar_tool(tool='FUR')
        bpy.ops.mch.side_page(page='TOOL')
    yield 1.0
    S.mch_brush.shape = 'STROKE'
    S.mch_fur.length = 0.035
    S.mch_fur.density = 30000.0
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 1.0
    # 1: the chest (seen from the front, a little turned)
    chest = Vector((0.0, -0.13, 1.33))
    outline = ring_at(chest, 120, 70)
    yield from real_outline(outline)
    furs = [o for o in S.objects if cf.is_fur(o)]
    fur = furs[0] if furs else None
    P = roots_of(fur) if fur else np.zeros((0, 2, 3))
    from bpy_extras import view3d_utils
    w, a, r = view3d()
    rv = a.spaces.active.region_3d

    def screen_of(p):
        s = view3d_utils.location_3d_to_region_2d(r, rv, Vector(p))
        return (r.x + s.x, w.height - (r.y + s.y)) if s is not None else (-1e9, -1e9)

    def inside_poly(pt, poly):
        x, y = pt
        ins = False
        for i in range(len(poly)):
            (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                ins = not ins
        return ins

    def grow(poly, k):
        cx = sum(p[0] for p in poly) / len(poly)
        cy = sum(p[1] for p in poly) / len(poly)
        return [(cx + (x - cx) * k, cy + (y - cy) * k) for x, y in poly]
    n1 = len(P)
    inn = [inside_poly(screen_of(p), grow(outline, 1.06)) for p in P[:, 0]] if n1 else []
    col = None
    if fur:
        dg = C.evaluated_depsgraph_get()
        cv = fur.evaluated_get(dg).data
        c = np.empty(len(cv.points) * 4, np.float32)
        cv.attributes['mch_fur_col'].data.foreach_get('color', c)
        col = c.reshape(n1, -1, 4)[:, 0, :3]
    dark = int(np.sum(col.max(1) < 0.1)) if col is not None else 0
    orange = int(np.sum((col[:, 0] > 0.6) & (col[:, 2] < 0.2))) if col is not None else 0
    log('1 chest: furs', len(furs), 'strands', n1, 'roots inside the drawn outline', sum(inn), '/', n1,
        '- root colours: dark', dark, 'orange', orange)
    res['1 a REAL Free Draw outline on the chest: a fur on the body, every root inside what was drawn (6 %), the root '
        'colours the stripes (dark and orange)'] = (fur is not None and fur.parent == human and n1 > 200
                                                    and sum(inn) == n1 and dark > 20 and orange > 20)
    shot('1_chest_wire.png')
    # 2: Alt + drag over the left part of it (the body's right: screen left)
    left = [(x, y) for x, y in ring_at(chest + Vector((-0.09, 0.0, 0.0)), 60, 90)]
    yield from real_outline(left, mods=('alt',))
    P2 = roots_of(fur)
    gone = [inside_poly(screen_of(p), grow(left, 0.7)) for p in P2[:, 0]]   # (a face the line crosses: ~15 px)
    log('2 Alt: strands', n1, '->', len(P2), '- roots well inside the erased outline', sum(gone))
    res['2 a REAL Alt + drag over its left part: the strands there gone'] = len(P2) < n1 * 0.85 and sum(gone) == 0
    # 3: the belly - the same fur
    yield from real_outline(ring_at(Vector((0.0, -0.11, 1.15)), 90, 50))
    furs = [o for o in S.objects if cf.is_fur(o)]
    P3 = roots_of(fur)
    log('3 belly: furs', len(furs), 'strands', len(P2), '->', len(P3))
    res['3 a REAL drag on the belly: the same fur (one), more strands'] = len(furs) == 1 and len(P3) > len(P2) * 1.2
    # 4: Length on the window, a REAL drag
    l0 = fur.mch_fur.length
    it = yield from scrolled_item('Length')
    if it is not None:
        w, a, r = view3d()
        x, y = int(r.x + it.x + it.w * 0.3), int(w.height - (r.y + it.y + it.h / 2))
        xdo('mousemove', x, y)
        yield 0.5
        xdo('mousedown', 1)
        yield 0.3
        for i in range(1, 12):
            xdo('mousemove', x + i * 12, y)
            yield 0.06
        yield 0.3
        xdo('mouseup', 1)
        yield 2.0
    P4 = roots_of(fur)
    lens = np.linalg.norm(np.diff(P4, axis=1), axis=2).sum(1) if len(P4) else np.zeros(1)
    log('4 Length cell', it is not None, 'length', round(l0, 4), '->', round(fur.mch_fur.length, 4), 'longest strand',
        round(float(lens.max()), 4))
    res['4 a REAL drag on the window\'s Length: the fur longer (the strands redone)'] = (
        fur.mch_fur.length > l0 * 1.2 and lens.max() > l0 * 1.15)
    # 5: areas (0.24.159) - a REAL click on the window's "Area 1" row (the chest), a REAL drag on its Lie Down: only
    #    the chest's fur stands up more; the belly (Area 2) as it was
    fur.mch_fur.gravity = 0.0
    yield 1.0

    def tilts():
        P = roots_of(fur)
        d = P[:, 1] - P[:, 0]
        d = d / np.linalg.norm(d, axis=1)[:, None]
        out = []
        for i in range(0, len(P), 3):
            ok, loc, nrm, _f = human.closest_point_on_mesh(Vector(P[i, 0]))
            out.append((P[i, 0, 2], math.degrees(math.acos(max(-1.0, min(1.0, Vector(d[i]).dot(nrm)))))))
        a = np.array(out)
        return a[a[:, 0] > 1.25, 1].mean(), a[a[:, 0] < 1.2, 1].mean()
    c0, b0 = tilts()
    pg = fur.mch_fur

    def area_row(prefix):
        w, a, r = view3d()
        with C.temp_override(window=w, area=a, region=r):
            its = sp.items(C, r.width, r.height, ui_factor(C, r))
        return next((i for i in its if getattr(i, 'label', '').startswith(prefix) and i.clickable()), None)
    row = None
    C.window_manager.mch_side_scroll = 0.0
    yield from wait_draws(2)
    for _i in range(30):
        row = area_row('Area 1')
        if row is not None:
            break
        w, a, r = view3d()
        with C.temp_override(window=w, area=a, region=r):
            sp.scroll_by(C, r.width, r.height, ui_factor(C, r), 100)
        yield from wait_draws(1)
    if row is not None:
        yield from press(row)
    picked = pg.part_index
    lie_before = [round(math.degrees(p_.lie), 1) for p_ in pg.parts]
    it = yield from scrolled_item('Lie Down')
    if it is not None:
        w, a, r = view3d()
        x, y = int(r.x + it.x + it.w * 0.5), int(w.height - (r.y + it.y + it.h / 2))
        xdo('mousemove', x, y)
        yield 0.5
        xdo('mousedown', 1)
        yield 0.3
        for i in range(1, 16):
            xdo('mousemove', x - i * 12, y)
            yield 0.06
        yield 0.3
        xdo('mouseup', 1)
        yield 2.0
    lie_after = [round(math.degrees(p_.lie), 1) for p_ in pg.parts]
    c1, b1 = tilts()
    log('5 areas: row', row is not None, '- picked', picked, '- Lie Down per area', lie_before, '->', lie_after,
        '- measured chest', round(c0, 1), '->', round(c1, 1), 'belly', round(b0, 1), '->', round(b1, 1))
    res['5 a REAL click on "Area 1" in the window, a REAL drag on its Lie Down: only the chest stands up more, the belly '
        '(Area 2) as it was'] = (row is not None and picked == 0 and lie_after[0] < lie_before[0] - 10
                                 and lie_after[1:] == lie_before[1:] and c1 < c0 - 8 and abs(b1 - b0) < 2)
    yield 1.0
    shot('2_fur_wire.png')
    S.render.engine = 'CYCLES'
    S.cycles.preview_samples = 6
    w, a, r = view3d()
    a.spaces.active.shading.type = 'RENDERED'
    yield 30.0
    shot('3_fur_cycles.png')
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
