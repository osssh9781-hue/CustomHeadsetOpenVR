"""Real window (0.24.173, user: the kestrel's tail feather photo - "이런 모양 깃털만 하나 추가하고 3차 해 줘"; the Insect
Wing - "내가 그린 영역 내부에 곤충 날개 무늬가 양각으로"; Creature Cloth - "메쉬 위에 따라 그리면 메쉬랑 붙어 있는 부분만 고정되고
나머지는 클로스로 흘러내리게", "콜리전이 아니라 고정하는 핀 정보로만"), by REAL clicks, drags and keys (xdotool), a front view,
wireframe on:

  1. the Feather Line tool: a REAL click on the new "Kestrel Tail" feather - picked
  2. the Insect Wing tool: a REAL click on "Dragonfly", a REAL lasso beside a body - a wing, its veins raised
  3. a REAL drag on "Vein Height %", a REAL click on "Cicada Photo" (the user's photo) - the wing laid again
  4. a REAL drag on "Bend" (from the root), a REAL Enter - the wing kept
  5. Sketch mode on: two REAL lassos (nothing made yet), a REAL Enter - one wing from both
  6. the Creature Cloth tool: a REAL click on "Taut Skin", a REAL lasso over a wing's bones - a membrane pinned on
     them; a REAL Space - it falls
  7. a REAL click on "Bat"; a REAL Enter - kept: a plain mesh, Thickness, on the bones
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


def flow():
    import numpy as np
    import bmesh
    from mecha_lab import cloth_drape as cd, creature_membrane as cm, greeble_line as gl, insect_wing as iw
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
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.25, location=(-0.3, 0, 0.4))
        body = C.active_object
        body.name = 'Insect Body'
        body.scale = (0.6, 0.6, 1.6)
        bm = bmesh.new()
        for a_, b_, rr in (((0, 0, -1.0), (1.4, 0, -0.85), 0.06), ((1.4, 0, -0.85), (2.4, 0, -1.8), 0.04),
                           ((1.4, 0, -0.85), (1.6, 0, -2.3), 0.04)):
            A, B = Vector(a_), Vector(b_)
            m = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=rr, radius2=rr * 0.6, depth=(B - A).length)
            bmesh.ops.rotate(bm, verts=m['verts'], cent=(0, 0, 0), matrix=(B - A).to_track_quat('Z', 'Y').to_matrix())
            bmesh.ops.translate(bm, verts=m['verts'], vec=(A + B) / 2)
        me = bpy.data.meshes.new('Wing Bones')
        bm.to_mesh(me)
        bm.free()
        bones = bpy.data.objects.new('Wing Bones', me)
        S.collection.objects.link(bones)
        for o in C.selected_objects:
            o.select_set(False)
        C.view_layer.objects.active = None
        rv = sp3.region_3d
        rv.view_perspective = 'ORTHO'
        rv.view_rotation = Euler((math.radians(90), 0.0, 0.0)).to_quaternion()
        rv.view_location = (0.9, 0.0, -0.6)
        rv.view_distance = 5.0
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True
        sp3.shading.type = 'SOLID'
        bpy.ops.mch.bar_tool(tool='FGREEBLE')
        bpy.ops.mch.side_page(page='TOOL')
    yield 2.0
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 1.0
    # 1: the new feather
    it = yield from scrolled_item('Kestrel Tail')
    if it is not None:
        yield from press(it)
    picked = [o.name for o in gl.picked(gl.settings(S, 'FEATHER'))]
    log('1 Kestrel Tail cell', it is not None, 'picked', picked)
    res['1 the Feather Line tool: a REAL click on the new "Kestrel Tail" - that feather picked'] = (
        it is not None and len(picked) == 1 and 'Kestrel' in picked[0])
    # 2: Insect Wing
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool='WING')
        bpy.ops.mch.side_page(page='TOOL')
    S.mch_brush.shape = 'STROKE'
    yield 1.5
    it = yield from scrolled_item('Dragonfly')
    if it is not None:
        yield from press(it)
    wpts = [(-0.12 + 1.3 * i / 39, 0.0, 0.75 + 0.02 * math.sin(math.pi * i / 39)) for i in range(40)]
    wpts += [(-0.12 + 1.3 * (1 - i / 39), 0.0, 0.75 - 0.3 * math.sin(math.pi * (1 - i / 39)) ** 0.7) for i in range(40)]
    yield from real_outline(outline_xy(wpts))
    yield 2.0
    wing = next((o for o in S.objects if iw.is_wing(o)), None)
    nf = len(wing.data.polygons) if wing else 0
    zr = 0.0
    if wing is not None:
        co = np.array([tuple(wing.matrix_world @ v.co) for v in wing.data.vertices])
        zr = float(np.ptp(co[:, 1]))
    log('2 Dragonfly cell', it is not None, '- wing', wing and wing.name, nf, 'faces, thick', round(zr, 4),
        'preset', wing and wing.mch_wing.preset)
    res['2 the Insect Wing tool: a REAL click on "Dragonfly", a REAL lasso: a wing, its veins raised'] = (
        it is not None and wing is not None and nf > 2000 and wing.mch_wing.preset == 'DRAGONFLY' and zr > 0.004)
    shot('1_wing.png')
    # 3: Vein Height slider, Bee / Wasp
    h0 = wing.mch_wing.vein_height if wing else 0
    it = yield from scrolled_item('Vein Height %')
    if it is not None:
        yield from slider_drag(it, 0.3, 12)
    yield from wait_draws(2)
    h1 = wing.mch_wing.vein_height if wing else 0
    it2 = yield from scrolled_item('Cicada Photo')
    if it2 is not None:
        yield from press(it2)
    yield from wait_draws(2)
    log('3 Vein Height cell', it is not None, round(h0, 2), '->', round(h1, 2), '- Cicada Photo cell', it2 is not None,
        'preset', wing and wing.mch_wing.preset)
    res['3 a REAL drag on "Vein Height %", a REAL click on "Cicada Photo": the wing laid again with the photo\'s veins'] = (
        it is not None and abs(h1 - h0) > 0.1 and it2 is not None and wing.mch_wing.preset == 'P_CICADA')
    shot('2_wing_photo.png')
    co0 = np.array([tuple(wing.matrix_world @ v.co) for v in wing.data.vertices]) if wing else None
    it = yield from scrolled_item('Bend')
    if it is not None:
        yield from slider_drag(it, 0.5, 10)
    yield from wait_draws(2)
    bend = wing.mch_wing.bend if wing else 0
    co1 = np.array([tuple(wing.matrix_world @ v.co) for v in wing.data.vertices]) if wing else None
    lift = float(np.abs(co1[:, 1] - co0[:, 1]).max()) if wing is not None and len(co1) == len(co0) else \
        float(np.ptp(co1[:, 1])) if wing is not None else 0.0
    shot('3_wing_bend.png')
    yield from key_over_view('Return')
    log('4 Bend cell', it is not None, 'bend', round(math.degrees(bend), 1), 'out of the plane', round(lift, 3),
        '- after Enter: still live', wing and iw.is_wing(wing), '- faces', wing and len(wing.data.polygons))
    res['4 a REAL drag on "Bend": the wing bent from its root; a REAL Enter: kept (a plain mesh)'] = (
        it is not None and abs(bend) > math.radians(5) and lift > 0.03 and wing is not None and not iw.is_wing(wing)
        and len(wing.data.polygons) > 2000)
    # 5: Sketch mode
    S.mch_brush.sketch_first = True
    yield 1.0
    n0 = len([o for o in S.objects if o.get('mch_wing_done') or iw.is_wing(o)])
    sk1 = [(1.4 + 0.9 * i / 29, 0.0, 0.45 + 0.01 * math.sin(math.pi * i / 29)) for i in range(30)]
    sk1 += [(1.4 + 0.9 * (1 - i / 29), 0.0, 0.45 - 0.2 * math.sin(math.pi * (1 - i / 29))) for i in range(30)]
    sk2 = [(2.1 + 0.25 * math.cos(2 * math.pi * i / 24), 0.0, 0.33 + 0.15 * math.sin(2 * math.pi * i / 24)) for i in range(24)]
    yield from real_outline(outline_xy(sk1))
    yield from real_outline(outline_xy(sk2))
    n1 = len([o for o in S.objects if o.get('mch_wing_done') or iw.is_wing(o)])
    from mecha_lab import lasso_sketch
    sketched = lasso_sketch.data(S) is not None
    shot('4_wing_sketch.png')
    yield from key_over_view('Return')
    n2 = len([o for o in S.objects if o.get('mch_wing_done') or iw.is_wing(o)])
    w2 = next((o for o in S.objects if iw.is_wing(o)), None)
    log('5 sketch: wings before', n0, 'after two lassos', n1, 'sketch kept', sketched, '- after Enter', n2,
        'new live wing', w2 and w2.name)
    res['5 Sketch mode: two REAL lassos (nothing made yet), a REAL Enter: one wing from both'] = (
        n1 == n0 and sketched and n2 == n0 + 1 and w2 is not None and lasso_sketch.data(S) is None)
    S.mch_brush.sketch_first = False
    with C.temp_override(window=w, area=a, region=r):
        if w2 is not None:
            iw.apply_wing(w2)
    # 5: Creature Cloth
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool='MEMBRANE')
        bpy.ops.mch.side_page(page='TOOL')
        for o in C.selected_objects:
            o.select_set(False)
        C.view_layer.objects.active = None
    S.mch_brush.shape = 'STROKE'
    yield 1.5
    it_t = yield from scrolled_item('Taut Skin')
    if it_t is not None:
        yield from press(it_t)
    style = S.mch_membrane.style
    mp = [(0.05, -1.0), (0.7, -0.93), (1.4, -0.85), (1.9, -1.32), (2.38, -1.78), (2.0, -1.9), (1.6, -2.28),
          (1.0, -2.1), (0.4, -1.7), (0.05, -1.4)]
    ring3 = []
    for i in range(len(mp)):
        x0, z0 = mp[i]
        x1, z1 = mp[(i + 1) % len(mp)]
        for k in range(6):
            ring3.append((x0 + (x1 - x0) * k / 6, 0.0, z0 + (z1 - z0) * k / 6))
    yield from real_outline(outline_xy(ring3))
    yield 2.0
    mem = next((o for o in S.objects if cm.is_membrane(o)), None)
    npin = 0
    if mem is not None:
        g = mem.vertex_groups[cm.PIN].index
        npin = sum(1 for v in mem.data.vertices if any(x.group == g for x in v.groups))
    log('6 membrane', mem and mem.name, mem and len(mem.data.vertices), 'points', npin, 'pinned; session',
        cd.SIM.get('mode'))
    shot('5_membrane_drawn.png')
    yield from key_over_view('space')
    for _i in range(80):
        if cd.SIM.get('done'):
            break
        yield 0.5
    fr = (cd.SIM.get('sess') or {}).get('frame', 0)
    log('6 Taut Skin cell', it_t is not None, 'style', style, '- after Space: frame', fr, 'done', cd.SIM.get('done'))
    res['6 the Creature Cloth tool: a REAL click on "Taut Skin", a REAL lasso over the bones: a membrane pinned on '
        'them; a REAL Space: it falls'] = (it_t is not None and style == 'TAUT' and mem is not None and npin > 30
                                           and fr >= 40)
    shot('6_membrane_fallen.png')
    it = yield from scrolled_item('Bat')
    if it is not None:
        yield from press(it)
    yield from key_over_view('Return')
    sol = mem.modifiers.get(cm.THICK_MOD) if mem else None
    log('7 Bat cell', it is not None, 'preset', S.mch_membrane.preset, '- after Enter: session', cd.sim_active(),
        'modifiers', mem and [m.type for m in mem.modifiers], 'parent', mem and mem.parent and mem.parent.name)
    res['7 a REAL click on "Bat"; a REAL Enter: kept - a plain mesh, Thickness, on the bones'] = (
        it is not None and S.mch_membrane.preset == 'BAT' and not cd.sim_active() and mem is not None
        and mem.modifiers.get(cm.CLOTH_MOD) is None and sol is not None and mem.parent == bones)
    yield from wait_draws(2)
    shot('7_all.png')
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
