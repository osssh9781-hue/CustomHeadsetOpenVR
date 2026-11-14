"""Real window (0.24.161, user: "디테일 플레이트 하나 더 만들자 - 내가 그으면 약간 외각 부분이 콘크리트나 크리쳐 질감처럼
디테일이 있는 거야 ... 그 디테일 프리셋도 한 10개"): Plate Detail 4 (Rough Rim) by REAL clicks and drags (xdotool):

  1. a REAL click on the window's "Broken Concrete" preset (nothing selected: for the next plate)
  2. a REAL Free Draw outline on a slab: a live rough plate there, Broken Concrete, its rim rough, its edge chipped
  3. a REAL drag on the window's Strength: the rim rougher at once (the base kept - the value went to the modifier)
  4. a REAL click on "Creature Skin" (the plate selected): that plate becomes Creature Skin (folds, no chips)
  5. a REAL Alt + drag inside it: a hole cut out, the plate still live
  6. shots: solid with the wireframe, Cycles
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
        slab.scale = (2.4, 1.8, 0.2)
        bpy.ops.object.transform_apply(scale=True)
        slab.name = 'Slab'
        sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
        S.collection.objects.link(sun)
        sun.data.energy = 3.0
        sun.rotation_euler = (math.radians(50), 0.0, math.radians(-35))
        for o in C.selected_objects:
            o.select_set(False)
        C.view_layer.objects.active = None
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((math.radians(38), 0.0, math.radians(10))).to_quaternion()
        rv.view_location = (0.0, 0.0, 0.0)
        rv.view_distance = 3.4
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True
        sp3.shading.type = 'SOLID'
        bpy.ops.mch.bar_tool(tool='DETAIL4')
        bpy.ops.mch.side_page(page='TOOL')
    yield 1.0
    S.mch_brush.shape = 'STROKE'
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 1.0
    # 1: the "Broken Concrete" preset on the window (nothing selected: for the next plate)
    it = yield from scrolled_item('Broken Concrete')
    if it is not None:
        yield from press(it)
    nxt = pd._fractions(S).get('r_preset')
    log('1 preset cell', it is not None, '- next plate preset', nxt)
    res['1 a REAL click on "Broken Concrete" in the window: the next plate will be Broken Concrete'] = nxt == 'BROKEN'
    # 2: a REAL Free Draw outline on the slab
    outline = ring_at(Vector((0.0, 0.0, 0.0)), 330, 200, wob=0.08)
    yield from real_outline(outline)
    plates = [o for o in S.objects if pd.is_detail(o)]
    plate = plates[0] if plates else None
    ok2 = False
    if plate is not None:
        p = plate.mch_pdetail
        e = evaluated(plate)
        top = e['mch_rtop'] > 0.5
        d = e['mch_rd']
        band = top & (d > p.r_ramp) & (d < p.r_rim * 0.6)
        core = top & (d > p.r_rim * 1.5)
        sb, sc = float(np.std(e['mch_rough'][band])), float(np.std(e['mch_rough'][core]))
        near = top & (d > p.r_ramp) & (d < p.r_rim * 0.5)
        chipped = float(np.mean(e['co'][near, 2] < 0.6 * p.r_height))
        log('2 plate:', plate.name, 'kind', p.kind, 'preset', p.r_preset, 'on', plate.parent.name if plate.parent else None,
            'faces', e['faces'], '- rough std rim', round(sb, 3), 'inside', round(sc, 3), '- near the edge chipped', f'{chipped:.0%}')
        ok2 = (p.kind == 'ROUGH' and p.r_preset == 'BROKEN' and plate.parent == slab and sb > 2.5 * sc
               and chipped > 0.15)
    res['2 a REAL Free Draw outline on the slab: a live rough plate (Broken Concrete), its rim rough, its edge chipped'] = ok2
    shot('1_broken_wire.png')
    # 3: a REAL drag on the window's Strength
    ok3 = False
    if plate is not None:
        p = plate.mch_pdetail
        base = plate.data
        s0 = p.r_strength
        e0 = evaluated(plate)
        it = yield from scrolled_item('Strength')
        if it is not None:
            yield from slider_drag(it, 0.5, 18)
        e1 = evaluated(plate)
        top = e1['mch_rtop'] > 0.5
        band = top & (e1['mch_rd'] > p.r_ramp) & (e1['mch_rd'] < p.r_rim * 0.6)
        band &= e0['co'][:, 2] > 0.7 * p.r_height          # (the unbroken part of the rim: the chips stay where they are)
        z0, z1 = float(np.std(e0['co'][band, 2])), float(np.std(e1['co'][band, 2]))
        log('3 Strength cell', it is not None, 'strength', round(s0 * 1000, 1), '->', round(p.r_strength * 1000, 1), 'mm',
            '- rim height std', round(z0 * 1000, 2), '->', round(z1 * 1000, 2), 'mm - base kept', plate.data == base)
        ok3 = it is not None and s0 * 1.2 < p.r_strength < s0 * 5 and z1 > z0 * 1.1 and plate.data == base
    res['3 a REAL drag on the window\'s Strength: the rim rougher at once (the base kept), a short drag a moderate change'] = ok3
    # 4: "Creature Skin" with the plate selected
    ok4 = False
    if plate is not None:
        it = yield from scrolled_item('Creature Skin')
        if it is not None:
            yield from press(it)
        p = plate.mch_pdetail
        log('4 skin cell', it is not None, '- plate preset', p.r_preset, 'wrinkles', p.r_wrinkles, 'chips', p.r_chips,
            '- plates', len([o for o in S.objects if pd.is_detail(o)]))
        ok4 = (it is not None and p.r_preset == 'SKIN' and p.r_wrinkles == 1.0 and p.r_chips == 0.0
               and len([o for o in S.objects if pd.is_detail(o)]) == 1)
    res['4 a REAL click on "Creature Skin" with the plate selected: that plate becomes Creature Skin'] = ok4
    shot('2_skin_wire.png')
    # 5: a REAL Alt + drag inside it: a hole
    ok5 = False
    if plate is not None:
        f0 = evaluated(plate)['faces']
        yield from real_outline(ring_at(Vector((0.25, 0.1, 0.0)), 60, 45), mods=('alt',))
        e5 = evaluated(plate)
        c = e5['co']
        hole = (np.abs(c[:, 0] - 0.25) < 0.08) & (np.abs(c[:, 1] - 0.1) < 0.06)
        log('5 Alt: faces', f0, '->', e5['faces'], '- points left in the hole', int(hole.sum()), '- live', pd.is_detail(plate),
            '- modifier', plate.modifiers.get(pr.MOD) is not None)
        ok5 = hole.sum() == 0 and pd.is_detail(plate) and plate.modifiers.get(pr.MOD) is not None
    res['5 a REAL Alt + drag inside the plate: a hole cut out, the plate still live'] = ok5
    yield 1.0
    shot('3_cut_wire.png')
    S.render.engine = 'CYCLES'
    S.cycles.preview_samples = 6
    w, a, r = view3d()
    a.spaces.active.overlay.show_wireframes = False
    a.spaces.active.shading.type = 'RENDERED'
    yield 30.0
    shot('4_cycles.png')
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
