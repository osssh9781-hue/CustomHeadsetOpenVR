"""Real window (0.24.174, user: "깃털이랑 비늘 퍼에 달린 거 가생이로 갈수록 얇아지는 버튼", "스케일 라인에도 퍼에 있는 비늘",
"인섹트 윙은 내가 그린 대로 안 나와, 혈관이", "스케일 라인도 테이퍼", "스노우랑 덜트들도 아머플레이트처럼 내가 그리게",
"표면에 그리는 게 안 돼, 합치지 않은 여러 개 메쉬에 올릴 수 있게"), by REAL clicks, drags and keys (xdotool), wireframe on:

  1. the Fur tool's Scales tab: a REAL lasso, a REAL click on "Thinner at Edge" - smaller at the area's edge
  2. Scale Line: a REAL click on "Dragon" (the Fur tool's scale), a REAL drag along the body, a REAL drag on
     "Taper End" - the scales smaller toward the end
  3. Insect Wing: a REAL lasso of a curved wing - its long veins spread across it (they follow the shape)
  4. Dirt: a REAL lasso on the ground - a plate there, made dirt; Snow with "Click a Mesh": a REAL click on a box
  5. Creature Cloth with Surface on: REAL clicks on three bone meshes (not joined), a REAL Enter - a membrane held
     on each of them
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


def drag_path(points):
    xy = [screen_xy(p) for p in points]
    xdo('mousemove', *xy[0])
    yield 0.5
    xdo('mousedown', 1)
    yield 0.4
    for x, y in xy[1:]:
        xdo('mousemove', x, y)
        yield 0.1
    yield 0.3
    xdo('mouseup', 1)
    yield 2.0


def key_over_view(key):
    w, a, r = view3d()
    xdo('mousemove', int(r.x + r.width * 0.5), int(w.height - (r.y + r.height * 0.12)))
    yield 0.5
    xdo('key', key)
    yield 2.0


def outline_xy(pts3):
    return [screen_xy(p) for p in pts3]


def click_at(p):
    xdo('mousemove', *screen_xy(p))
    yield 0.5
    xdo('click', 1)
    yield 1.2


def set_tool(tool):
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool=tool)
        bpy.ops.mch.side_page(page='TOOL')
        for o in C.selected_objects:
            o.select_set(False)
        C.view_layer.objects.active = None


def flow():
    import numpy as np
    import bmesh
    from mecha_lab import (cloth_drape as cd, creature_membrane as cm, greeble_line as gl, insect_wing as iw,
                           skin_cover as sc, weathering as wt)
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
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=96, ring_count=48, location=(0, 0, 0))
        body = C.active_object
        body.name = 'Body'
        bpy.ops.object.shade_smooth()
        bpy.ops.mesh.primitive_plane_add(size=1.6, location=(2.2, 0.0, -1.9), rotation=(math.radians(90), 0, 0))
        ground = C.active_object
        ground.name = 'Ground Wall'
        bpy.ops.mesh.primitive_cube_add(size=0.6, location=(-2.0, -0.3, 3.0))
        box = C.active_object
        box.name = 'Box'
        bone_obs = []
        for name, a_, b_, rr in (('Arm Bone', (-4.0, 0, 1.0), (-2.6, 0, 1.15), 0.06),
                                 ('Finger Bone A', (-2.6, 0, 1.15), (-1.6, 0, 0.2), 0.045),
                                 ('Finger Bone B', (-2.6, 0, 1.15), (-2.4, 0, -0.3), 0.045)):
            bm = bmesh.new()
            A, B = Vector(a_), Vector(b_)
            m = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=rr, radius2=rr * 0.7, depth=(B - A).length)
            bmesh.ops.rotate(bm, verts=m['verts'], cent=(0, 0, 0), matrix=(B - A).to_track_quat('Z', 'Y').to_matrix())
            bmesh.ops.translate(bm, verts=m['verts'], vec=(A + B) / 2)
            me = bpy.data.meshes.new(name)
            bm.to_mesh(me)
            bm.free()
            ob_ = bpy.data.objects.new(name, me)
            S.collection.objects.link(ob_)
            bone_obs.append(ob_)
        for o in C.selected_objects:
            o.select_set(False)
        C.view_layer.objects.active = None
        rv = sp3.region_3d
        rv.view_perspective = 'ORTHO'
        rv.view_rotation = Euler((math.radians(90), 0.0, 0.0)).to_quaternion()
        rv.view_location = (-0.2, 0.0, 0.3)
        rv.view_distance = 12.0
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True
        sp3.shading.type = 'SOLID'
    S.mch_brush.shape = 'STROKE'
    set_tool('FUR')
    yield 2.0
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 1.0
    # 1: Scales + Thinner at Edge
    it = yield from scrolled_item('Scales')
    if it is not None:
        yield from press(it)
    yield from real_outline(outline_xy([(0.6 * math.cos(t), -1.0, 0.1 + 0.5 * math.sin(t))
                                        for t in np.linspace(0, 2 * math.pi, 40, endpoint=False)]))
    yield 2.0
    cov = next((o for o in S.objects if sc.is_cover(o)), None)

    def sizes(o):
        n = len(o.data.vertices)
        s_ = np.empty(n * 3, np.float32)
        o.data.attributes['mch_scale'].data.foreach_get('vector', s_)
        return s_.reshape(-1, 3)
    s0 = sizes(cov) if cov else np.ones((1, 3))
    it2 = yield from scrolled_item('Thinner at Edge')
    if it2 is not None:
        yield from press(it2)
    yield from wait_draws(2)
    s1 = sizes(cov) if cov else np.ones((1, 3))
    log('1 Scales cell', it is not None, 'cover', cov and cov.name, len(s0), '- Thinner at Edge cell', it2 is not None,
        'on', cov and cov.mch_cover.edge_thin, 'smallest', round(float(s0[:, 0].min()), 4), '->', round(float(s1[:, 0].min()), 4))
    res['1 the Fur tool: a REAL click on "Scales", a REAL lasso, a REAL click on "Thinner at Edge": smaller at the edge'] = (
        cov is not None and it2 is not None and cov.mch_cover.edge_thin and s1[:, 0].min() < s0[:, 0].min() * 0.6)
    shot('1_thinner_edge.png')
    # 2: Scale Line - Dragon + Taper End
    set_tool('CGREEBLE')
    yield 1.5
    it = yield from scrolled_item('Dragon')
    if it is not None:
        yield from press(it)
    picked = [o.data.get('mch_shape_id') for o in gl.picked(gl.settings(S, 'CREATURE'))]
    path = [(math.sin(t) * 1.0, -math.cos(t) * 1.0 - 0.005, 0.75) for t in np.linspace(-0.6, 0.6, 14)]
    path = [(x * 0.66, y * 0.66, z) for x, y, z in path]
    yield from drag_path(path)
    ln = next((o for o in S.objects if gl.is_line(o)), None)
    t0 = sizes(ln) if ln else np.ones((1, 3))
    it3 = yield from scrolled_item('Taper End')
    if it3 is not None:
        yield from slider_drag(it3, 0.05, 18)
    yield from wait_draws(2)
    t1 = sizes(ln) if ln else np.ones((1, 3))
    te = ln.mch_greeble_line.taper_end if ln else 0
    log('2 Dragon cell', it is not None, 'picked', picked, '- line', ln and ln.name, len(t0), '- Taper End cell', it3 is not None,
        round(te, 2), 'first/last', round(float(t1[0, 0]), 4), round(float(t1[-1, 0]), 4))
    res['2 Scale Line: a REAL click on "Dragon", a REAL drag, a REAL drag on "Taper End": smaller toward the end'] = (
        it is not None and picked == ['DRAGON'] and ln is not None and it3 is not None and te > 0.2
        and t1[-1, 0] < t1[0, 0] * (1 - te * 0.6))
    shot('2_scale_taper.png')
    # 3: a curved wing
    set_tool('WING')
    yield 1.5
    inner, outer = [], []
    for i in range(30):
        t = i / 29
        an = math.radians(-20 + 80 * t)
        w_ = 0.22 * math.sin(math.pi * t) ** 0.7 + 0.03
        cx, cz = 1.3 + 1.4 * math.sin(an), 1.6 + 1.4 * (1 - math.cos(an))
        nx_, nz_ = -math.sin(an), math.cos(an)
        inner.append((cx + nx_ * w_ * 0.3, -1.0, cz + nz_ * w_ * 0.3))
        outer.append((cx - nx_ * w_, -1.0, cz - nz_ * w_))
    yield from real_outline(outline_xy(inner + outer[::-1]))
    yield 2.0
    wing = next((o for o in S.objects if iw.is_wing(o)), None)
    info = ''
    if wing is not None:
        d = iw.data(wing)
        fr = iw.HFrame(np.array(d['outline']), d['root'])
        info = f'frame {type(fr).__name__}'
    log('3 wing', wing and wing.name, wing and len(wing.data.polygons), info)
    res['3 Insect Wing: a REAL lasso of a curved wing - built on its drawn shape'] = wing is not None and \
        len(wing.data.polygons) > 2000 and 'HFrame' in info
    shot('3_curved_wing.png')
    yield from key_over_view('Return')
    # 4: Dirt drawn, Snow clicked
    set_tool('WDIRT')
    yield 1.5
    how = S.mch_weather_how
    yield from real_outline(outline_xy([(2.2 + 0.5 * math.cos(t), -0.9, -1.9 + 0.4 * math.sin(t))
                                        for t in np.linspace(0, 2 * math.pi, 36, endpoint=False)]))
    yield 3.0
    dirt = next((o for o in S.objects if wt.kind_of(o) == 'DIRT'), None)
    set_tool('WSNOW')
    yield 1.5
    it4 = yield from scrolled_item('Click a Mesh')
    if it4 is not None:
        yield from press(it4)
    CALLS = []
    _inv = wt.MCH_OT_weather_click.invoke

    def _spy(self, context, event):
        r_ = _inv(self, context, event)
        CALLS.append((event.type, event.value, context.scene.mch_weather_how,
                      getattr(wt.pick(context, (event.mouse_region_x, event.mouse_region_y)), 'name', None), r_))
        return r_
    wt.MCH_OT_weather_click.invoke = _spy
    tid = C.workspace.tools.from_space_view3d_mode('OBJECT').idname
    yield from click_at((-2.0, -0.62, 3.0))
    yield 3.0
    wt.MCH_OT_weather_click.invoke = _inv
    log('4 tool', tid, '- the click reached Click a Mesh:', CALLS)
    log('4 Dirt (how', how, ')', dirt and dirt.name, '- Click a Mesh cell', it4 is not None, S.mch_weather_how,
        '- box', wt.kind_of(box))
    res['4 Dirt: a REAL lasso on the wall - a plate there, made dirt; Snow, "Click a Mesh", a REAL click on the box'] = (
        how == 'DRAW' and dirt is not None and dirt != ground and it4 is not None and wt.kind_of(box) == 'SNOW'
        and len(CALLS) == 1 and CALLS[0][3] == 'Box')
    shot('4_weathering.png')
    S.mch_weather_how = 'DRAW'
    # 5: Creature Cloth on Surface
    set_tool('MEMBRANE')
    S.mch_brush.surface_mode = True
    yield 1.5
    def on_bone(a_, b_, t):                     # (a point on the bone's axis: the click lands on its front)
        return (a_[0] + (b_[0] - a_[0]) * t, -0.1, a_[1] + (b_[1] - a_[1]) * t)
    for p in [on_bone((-4.0, 1.0), (-2.6, 1.15), 0.12), on_bone((-4.0, 1.0), (-2.6, 1.15), 0.6),
              on_bone((-2.6, 1.15), (-1.6, 0.2), 0.45), on_bone((-2.6, 1.15), (-1.6, 0.2), 0.92),
              on_bone((-2.6, 1.15), (-2.4, -0.3), 0.88), on_bone((-2.6, 1.15), (-2.4, -0.3), 0.45)]:
        yield from click_at(p)
    yield from key_over_view('Return')
    yield 2.0
    S.mch_brush.surface_mode = False
    mem = next((o for o in S.objects if cm.is_membrane(o)), None)
    groups = sorted(g.name for g in mem.vertex_groups if g.name.startswith(cm.HOST_PREFIX)) if mem else []
    log('5 surface membrane', mem and mem.name, mem and len(mem.data.vertices), 'held by', groups, 'session', cd.SIM.get('mode'))
    res['5 Creature Cloth with Surface: REAL clicks on three bone meshes, a REAL Enter: held on each of them'] = (
        mem is not None and len(groups) == 3 and cd.SIM.get('mode') == 'MEMBRANE')
    shot('5_surface_membrane.png')
    if cd.sim_active():
        yield from key_over_view('Escape')
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
