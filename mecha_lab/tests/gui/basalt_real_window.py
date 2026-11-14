"""Real window (0.24.163, user: "주상절리 같은 절벽 스타일 ... 높이는 동서남북 기준으로 내가 돌릴 수 있게", then two photos -
a sea cliff ("절벽의 옆면 같은 돌의 깊이 차이가 윗면에") and a rock creature's carapace ("테두리는 외곽 라인처럼 튀어나오고
가운데는 볼록, 내부는 릿지")): Plate Detail 4's Columnar Basalt, Layered Cliff and Creature Carapace by REAL clicks and drags:

  1. a REAL click on the window's "Columnar Basalt" preset (nothing selected: for the next plate)
  2. a REAL Free Draw outline: basalt columns rising east (the compass default)
  3. a REAL click on the window's "N": they rise north instead
  4. a REAL drag on the window's Slope: flatter (rebuilt once the drag stops)
  5. a REAL click on "Layered Cliff" (the plate selected): rock layers in long lines running down the cliff (north
     here; 0.24.165 - before that, stacked plates)
  6. a REAL click on "Creature Carapace": a raised lip along the outline, a groove, the middle up again
  7. shots: solid with the wireframe, Cycles
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


def tops(ob):
    import numpy as np
    mw = ob.matrix_world
    return np.array([tuple(mw @ f.center) for f in ob.data.polygons if f.normal.z > 0.95 and f.center.z > 1e-3])


def corr_axis(ob, axis):
    import numpy as np
    T = tops(ob)
    return float(np.corrcoef(T[:, axis], T[:, 2])[0, 1]) if len(T) > 3 else 0.0


def evaluated_top(ob):
    import numpy as np
    from mecha_lab import plate_rough as pr
    me = ob.evaluated_get(C.evaluated_depsgraph_get()).data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    out = []
    for nm in (pr.TOP_ATTR, pr.D_ATTR):
        at = me.attributes.get(nm)
        a_ = np.empty(len(me.vertices), np.float32)
        at.data.foreach_get('value', a_)
        out.append(a_)
    return co, out[0] > 0.5, out[1]


def flow():
    import numpy as np
    from mecha_lab import plate_detail as pd, plate_rough as pr
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
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, -0.1))
        slab = C.active_object
        slab.scale = (4.4, 3.0, 0.2)
        bpy.ops.object.transform_apply(scale=True)
        slab.name = 'Slab'
        sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
        S.collection.objects.link(sun)
        sun.data.energy = 3.0
        sun.rotation_euler = (math.radians(55), 0.0, math.radians(-35))
        for o in C.selected_objects:
            o.select_set(False)
        C.view_layer.objects.active = None
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((math.radians(50), 0.0, 0.0)).to_quaternion()
        rv.view_location = (0.0, 0.0, 0.0)
        rv.view_distance = 4.6
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True
        sp3.shading.type = 'SOLID'
        bpy.ops.mch.bar_tool(tool='DETAIL4')
        bpy.ops.mch.side_page(page='TOOL')
    yield 1.0
    S.mch_brush.shape = 'STROKE'
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 1.0
    # 1: the "Columnar Basalt" preset on the window (nothing selected: for the next plate)
    it = yield from scrolled_item('Columnar Basalt')
    if it is not None:
        yield from press(it)
    f = pd._fractions(S)
    log('1 preset cell', it is not None, '- next plate', f.get('r_preset'), f.get('r_style'))
    res['1 a REAL click on "Columnar Basalt" in the window: the next plate will be basalt columns'] = (
        f.get('r_preset') == 'BASALT' and f.get('r_style') == 'COLUMNS')
    # 2: a REAL outline: rising east (the default)
    yield from real_outline(ring_at(Vector((0.0, 0.0, 0.0)), 300, 170))
    plates = [o for o in S.objects if pd.is_detail(o)]
    A = plates[-1] if plates else None
    ce = corr_axis(A, 0) if A else 0.0
    log('2 plate', A and A.name, 'style', A and A.mch_pdetail.r_style, 'columns', len(tops(A)) if A else 0,
        '- rise toward', A and round(math.degrees(A.mch_pdetail.r_compass)), '- height vs x', round(ce, 2))
    res['2 a REAL outline: basalt columns rising east (the compass default)'] = (
        A is not None and A.mch_pdetail.r_style == 'COLUMNS' and len(tops(A)) > 30 and ce > 0.7)
    shot('1_basalt_east.png')
    if A is None:                                   # (nothing made: report and stop)
        for k_, v in res.items():
            log(('PASS ' if v else 'FAIL ') + k_)
        log(f'{sum(bool(v) for v in res.values())}/{len(res) + 4} passed')
        bpy.ops.wm.quit_blender()
        return
    # 3: a REAL click on "N"
    it = yield from scrolled_item('N')
    if it is not None:
        yield from press(it)
    yield 1.0
    cn, cx = corr_axis(A, 1), corr_axis(A, 0)
    log('3 N cell', it is not None, '- rise toward', round(math.degrees(A.mch_pdetail.r_compass)), '- height vs y',
        round(cn, 2), 'vs x', round(cx, 2))
    res['3 a REAL click on "N": the columns rise north instead'] = it is not None and cn > 0.7 and abs(cx) < 0.4
    shot('2_basalt_north.png')
    # 4: a REAL drag on Slope to the left: flatter
    p = A.mch_pdetail
    s0, sp0 = p.r_slope, float(np.ptp(tops(A)[:, 2]))
    it = yield from scrolled_item('Slope')
    if it is not None:
        yield from slider_drag(it, 0.8, -20)
    yield 2.0
    sp1 = float(np.ptp(tops(A)[:, 2]))
    log('4 Slope cell', it is not None, 'slope', round(s0, 2), '->', round(p.r_slope, 2), '- tallest - shortest',
        round(sp0 * 1000), '->', round(sp1 * 1000), 'mm')
    res['4 a REAL drag on the window\'s Slope to the left: flatter (rebuilt once the drag stopped)'] = (
        it is not None and p.r_slope < s0 - 0.2 and sp1 < sp0 * 0.85)
    # 5: a REAL click on "Layered Cliff"
    it = yield from scrolled_item('Layered Cliff')
    if it is not None:
        yield from press(it)
    yield 2.0
    co, top, d = evaluated_top(A)
    q = co[top & (d > p.r_ramp * 0.55)]               # (0.24.165 lines down the cliff: here north, along y)
    ij = np.round(q[:, :2] / 0.03).astype(int)
    keys, inv = np.unique(ij, axis=0, return_inverse=True)
    zm = np.bincount(inv.ravel(), q[:, 2]) / np.bincount(inv.ravel())
    cell = {tuple(k): z_ for k, z_ in zip(keys, zm)}
    dx = float(np.mean([abs(cell[(a_ + 1, b_)] - z_) for (a_, b_), z_ in cell.items() if (a_ + 1, b_) in cell]))
    dy = float(np.mean([abs(cell[(a_, b_ + 1)] - z_) for (a_, b_), z_ in cell.items() if (a_, b_ + 1) in cell]))
    log('5 cliff cell', it is not None, '- style', p.r_style, 'modifier', A.modifiers.get(pr.MOD) is not None,
        '- height change across the lines (x)', round(dx * 1000, 1), 'along them (y)', round(dy * 1000, 1), 'mm a cell')
    res['5 a REAL click on "Layered Cliff": rock layers in lines running down the cliff (north here)'] = (
        it is not None and p.r_style == 'CLIFF' and A.modifiers.get(pr.MOD) is not None and dx > 2.5 * dy)
    shot('3_cliff.png')
    # 6: a REAL click on "Creature Carapace"
    it = yield from scrolled_item('Creature Carapace')
    if it is not None:
        yield from press(it)
    yield 2.0
    co, top, d = evaluated_top(A)
    wid = p.r_ramp

    def at(lo, hi):
        m = top & (d >= lo) & (d < hi)
        return float(np.median(co[m, 2])) if m.any() else 0.0
    lip, groove, crest = at(0.85 * wid, 1.15 * wid), at(2.0 * wid, 2.4 * wid), at(0.92 * d[top].max(), d[top].max() + 1)
    log('6 carapace cell', it is not None, '- profile', p.r_profile, '- lip', round(lip * 1000), 'groove', round(groove * 1000),
        'middle', round(crest * 1000), 'mm')
    res['6 a REAL click on "Creature Carapace": a raised lip along the outline, a groove, the middle up again'] = (
        it is not None and p.r_profile == 'CARAPACE' and p.r_style == 'ROUGH' and lip > groove * 1.2 and crest > lip)
    yield 1.0
    shot('4_carapace.png')
    S.render.engine = 'CYCLES'
    S.cycles.preview_samples = 6
    w, a, r = view3d()
    a.spaces.active.overlay.show_wireframes = False
    a.spaces.active.shading.type = 'RENDERED'
    yield 30.0
    shot('5_cycles.png')
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
