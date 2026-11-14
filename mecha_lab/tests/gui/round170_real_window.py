"""Real window (0.24.170, user: "그리블 할 때 어플라이 안 해도 내가 재질 바꿀 수 있게 해 줘, 크리쳐도 그렇고"): a live
Scale Line and a live Greeble Line take a material by REAL clicks (xdotool), still live:

  1. a live Scale Line on a skinned ball, the Scale Line window: a REAL click on "Body's Material" - every scale the
     ball's skin (evaluated), the line still live
  2. a REAL click on "Parts' Own" - the scales' own material back
  3. the Creature page: a REAL click on the skin type "Reptile Dry" - a Creature material on every live scale
  4. a live Greeble Line, the Mech page: a REAL click on the preset "Steel" - a Mech material on every live part
  5. both selected, a REAL Enter - real meshes, each with its material (the Mech one's edges measured)
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


def ev_mats(ln):
    """The materials the evaluated line shows (realized: by face; instances: what each instance's mesh carries)."""
    import numpy as np
    C.view_layer.update()
    dg = C.evaluated_depsgraph_get()
    me = ln.evaluated_get(dg).data
    if len(me.polygons):
        idx = np.zeros(len(me.polygons), np.int32)
        me.polygons.foreach_get('material_index', idx)
        return {(me.materials[i].name if i < len(me.materials) and me.materials[i] else None) for i in np.unique(idx)}
    out = set()
    for inst in dg.object_instances:
        if inst.is_instance and inst.parent and inst.parent.original == ln:
            out |= {m.name if m else None for m in inst.object.data.materials}
    return out


def page_tab(label, page):
    """A REAL click on the panel's page tab ``label`` (the operator only if no such tab is drawn)."""
    yield from wait_draws(2)
    it = panel_item(label)
    if it is not None:
        yield from press(it)
    else:
        w, a, r = view3d()
        with C.temp_override(window=w, area=a, region=r):
            bpy.ops.mch.side_page(page=page)
        yield 1.5
    yield from wait_draws(2)
    return it is not None


def cell(label, header=None):
    """The cell ``label`` (scrolled to); its section ``header`` opened by a REAL click first when folded."""
    it = yield from scrolled_item(label)
    if it is None and header is not None:
        h = yield from scrolled_item(header)
        if h is not None:
            yield from press(h)
            it = yield from scrolled_item(label)
    return it


def flow():
    import numpy as np
    from mecha_lab import creature_shader as cs, greeble_line as gl, mech_shader as ms
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
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=48, ring_count=24, location=(0, 0, 0))
        ball = C.active_object
        ball.name = 'Creature'
        bpy.ops.object.shade_smooth()
        skin = bpy.data.materials.new('Skin')
        skin.diffuse_color = (0.75, 0.45, 0.35, 1)
        ball.data.materials.append(skin)
        paint = bpy.data.materials.new('Part Paint')
        paint.diffuse_color = (0.2, 0.35, 0.8, 1)
        lines = []
        for which, kind, yy in (('SCALES', 'CREATURE', -0.35), ('MECH', 'MECH', 0.4)):
            made = gl.make_starters(C, ball, which)
            for p in made:
                p.data.materials.clear()
                p.data.materials.append(paint)
            C.view_layer.update()
            stg = gl.settings(S, kind)
            pts, nrm = [], []
            for tt in np.linspace(-1.0, 1.0, 44):
                v = Vector((math.sin(tt), yy, math.cos(tt))).normalized()
                pts.append(tuple(v))
                nrm.append(tuple(v))
            ln = gl.new_line(C, ball, pts, nrm, gl.picked(stg), stg, kind)
            gl.rebuild(ln, C)
            lines.append(ln)
        scl, grb = lines
        for o in C.selected_objects:
            o.select_set(False)
        scl.select_set(True)
        C.view_layer.objects.active = scl
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((math.radians(50), 0.0, math.radians(20))).to_quaternion()
        rv.view_location = (0.0, 0.0, 0.5)
        rv.view_distance = 4.2
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True
        sp3.shading.type = 'SOLID'
        sp3.shading.color_type = 'MATERIAL'
        bpy.ops.mch.bar_tool(tool='CGREEBLE')
        bpy.ops.mch.side_page(page='TOOL')
    yield 2.0
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 1.0
    m0 = ev_mats(scl)
    log('0 the live Scale Line', scl.name, '- its scales show', m0)
    # 1: Body's Material
    it = yield from cell("Body's Material")
    if it is not None:
        yield from press(it)
    yield 1.0
    m1 = ev_mats(scl)
    log("1 Body's Material cell", it is not None, '- scales now', m1, '- live', gl.is_line(scl))
    res["1 a REAL click on \"Body's Material\": every live scale the creature's skin"] = (
        it is not None and m0 == {'Part Paint'} and m1 == {'Skin'} and gl.is_line(scl))
    shot('1_body_material.png')
    # 2: Parts' Own
    it = yield from cell("Parts' Own")
    if it is not None:
        yield from press(it)
    yield 1.0
    m2 = ev_mats(scl)
    log("2 Parts' Own cell", it is not None, '- scales now', m2)
    res["2 a REAL click on \"Parts' Own\": the scales' own material back"] = it is not None and m2 == {'Part Paint'}
    # 3: the Creature page, Reptile Dry
    tab = yield from page_tab('Creature', 'CREATURE')
    it = yield from cell('Reptile Dry', 'Skin Types')
    if it is not None:
        yield from press(it)
    yield 1.5
    m3 = ev_mats(scl)
    lm = gl.line_material(scl)
    log('3 Creature tab', tab, '- Reptile Dry cell', it is not None, '- scales now', m3, '- live', gl.is_line(scl))
    res['3 the Creature page, a REAL click on "Reptile Dry": a Creature material on every live scale'] = (
        it is not None and lm is not None and cs.is_creature(lm) and m3 == {lm.name} and gl.is_line(scl))
    shot('2_creature_reptile.png')
    # 4: the Greeble Line, the Mech page, Steel
    with C.temp_override(window=w, area=a, region=r):
        for o in C.selected_objects:
            o.select_set(False)
        grb.select_set(True)
        C.view_layer.objects.active = grb
    yield 1.0
    tab = yield from page_tab('Mech', 'MATERIAL')
    it = yield from cell('Steel', 'Presets')
    if it is not None:
        yield from press(it)
    yield 1.5
    m4 = ev_mats(grb)
    gm = gl.line_material(grb)
    log('4 Mech tab', tab, '- Steel cell', it is not None, '- greebles now', m4, '- live', gl.is_line(grb),
        '- the scales still', ev_mats(scl))
    res['4 a live Greeble Line, the Mech page, a REAL click on "Steel": a Mech material on every live part '
        '(the scales keep theirs)'] = (
        it is not None and gm is not None and ms.is_mech(gm) and m4 == {gm.name} and gl.is_line(grb)
        and ev_mats(scl) == {lm.name if lm else None})
    shot('3_mech_steel.png')
    # 5: both selected, Enter
    with C.temp_override(window=w, area=a, region=r):
        for o in C.selected_objects:
            o.select_set(False)
        scl.select_set(True)
        grb.select_set(True)
        C.view_layer.objects.active = scl
        bpy.ops.mch.side_page(page='TOOL')
        bpy.ops.mch.bar_tool(tool='CGREEBLE')
    yield 2.0
    w, a, r = view3d()
    xdo('mousemove', int(r.x + r.width * 0.4), int(w.height - (r.y + r.height * 0.5)))
    yield 0.5
    xdo('key', 'Return')
    yield 2.5
    ms_ = {m.name for m in scl.data.materials if m}
    mg_ = {m.name for m in grb.data.materials if m}
    log('5 after Enter: live', gl.is_line(scl), gl.is_line(grb), '- names', scl.name, grb.name, '- materials', ms_, mg_,
        '- faces', len(scl.data.polygons), len(grb.data.polygons), '- edges measured', ms.CURV in grb.data.attributes)
    res['5 both selected, a REAL Enter: real meshes, each with the material it had live (the Mech one\'s edges '
        'measured)'] = (
        not gl.is_line(scl) and not gl.is_line(grb) and len(scl.data.polygons) > 0 and len(grb.data.polygons) > 0
        and ms_ == {lm.name if lm else None} and mg_ == {gm.name if gm else None} and ms.CURV in grb.data.attributes)
    shot('4_applied.png')
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
