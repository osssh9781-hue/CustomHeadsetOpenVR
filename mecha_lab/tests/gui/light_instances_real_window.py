"""Real window (0.24.139, user: "다른 블렌더에서 가져왔어"): Light Copies for linked collection instances - a library
file holds a collection with a 1.3 M triangle part (+ a small cube); this file links it and places 15 instances
(19.7 M triangles drawn).  Software OpenGL here - the ratios count:
  1. one Solid view change timed; a REAL click on Light Copies (Render tab > VIEWPORT); one copy made in the
     background for all 15 instances; the view change again
  2. a REAL click on an instance: it shows the linked collection itself; Wire on: the clicked one (itself) and its
     neighbour (light); a REAL click on empty space: light again once it rests
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
from mathutils import Euler  # noqa: E402

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
    from mecha_lab import fast_view as fv, light_copies as lc
    import bmesh
    res = {}
    subdiv = int(os.environ.get('MCH_SUBDIV', '9'))
    lib = os.path.join(OUT, 'mech_parts_lib.blend')
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        S.mch_light.min_tris = 300000 if subdiv >= 9 else 10000
        # the library file: collection "MechLeg" (a heavy part + a small cube), written beside, then linked
        coll = bpy.data.collections.new('MechLeg')
        me = bpy.data.meshes.new('LegArmor')
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=0.45)
        bm.to_mesh(me)
        bm.free()
        heavy = bpy.data.objects.new('LegArmor', me)
        coll.objects.link(heavy)
        cme = bpy.data.meshes.new('Bolt')
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=0.15)
        bm.to_mesh(cme)
        bm.free()
        cube = bpy.data.objects.new('Bolt', cme)
        cube.location = (0, 0, 0.5)
        coll.objects.link(cube)
        bpy.data.libraries.write(lib, {coll}, fake_user=True)
        for o in (heavy, cube):
            m_ = o.data
            bpy.data.objects.remove(o)
            bpy.data.meshes.remove(m_)
        bpy.data.collections.remove(coll)
        with bpy.data.libraries.load(lib, link=True) as (_src, dst):
            dst.collections = ['MechLeg']
        linked = next(c for c in bpy.data.collections if c.name == 'MechLeg' and c.library is not None)
        insts = []
        for i in range(15):
            e = bpy.data.objects.new(f'Leg{i:02d}', None)
            e.instance_type, e.instance_collection = 'COLLECTION', linked
            e.location = ((i % 5) * 1.1 - 2.2, (i // 5) * 1.1 - 1.1, 0.0)
            S.collection.objects.link(e)
            insts.append(e)
        bpy.ops.object.light_add(type='SUN', location=(0, 0, 5))
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((1.0, 0.0, 0.5)).to_quaternion()
        rv.view_location = (0.0, 0.0, 0.0)
        rv.view_distance = 9.0
        for o in S.objects:
            o.select_set(False)
        C.view_layer.objects.active = None
        C.preferences.system.viewport_aa = 'FXAA'
        fv.apply(C)
        sp3.show_region_ui = False
        bpy.ops.mch.bar_tool(tool='SELECT')
        bpy.ops.mch.side_page(page='HDRI')
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    log('scene: 15 instances of a linked collection,', 15 * len(linked.all_objects[0].data.polygons) / 1e6
        if linked.all_objects[0].type == 'MESH' else '?', 'M triangles drawn')
    yield 30.0
    t_full = []
    for k in range(3):
        t = yield from view_change_draw(a, rv, 0.5 + 0.05 * (k + 1))
        t_full.append(t)
        yield 1.5
    t_full = sorted(t_full)[1]
    log(f'1 Solid view change, instances in full: {t_full:.2f} s')
    it = yield from scrolled_item('Light Copies (parts not worked on)')
    if it is None:
        log('ERROR no Light Copies cell')
        bpy.ops.wm.quit_blender()
        return
    yield from press(it)
    yield 3.0
    log('   Light Copies on after the click:', S.mch_light.on, 'queued', list(lc.QUEUE), 'working', lc.WORK['name'])
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 600:
        yield 0.2
        if all(e.instance_collection is not None and e.instance_collection.get(lc.SET) for e in insts):
            break
    made = time.perf_counter() - t0
    yield 3.0
    light = sum(1 for e in insts if e.instance_collection is not None and e.instance_collection.get(lc.SET))
    log(f'   one copy made and the light set built in {made:.0f} s; instances drawn light: {light}')
    log('   status:', lc.status(C))
    yield 10.0
    t_light = []
    for k in range(3):
        t = yield from view_change_draw(a, rv, 0.7 + 0.05 * (k + 1))
        t_light.append(t)
        yield 1.5
    t_light = sorted(t_light)[1]
    log(f'   Solid view change with Light Copies: {t_light:.2f} s (was {t_full:.2f} s)')
    shot('1_instances_light.png')
    res[f'1 a REAL click on Light Copies: 15 linked instances light ({made:.0f} s); a Solid view change '
        f'{t_full:.2f} s -> {t_light:.2f} s'] = light == 15 and t_light < t_full * 0.6
    # 2. a REAL click on an instance
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    target = insts[7]
    p = location_3d_to_region_2d(r, rv, target.matrix_world.translation)
    yield from wait_draws(2)
    xdo('mousemove', int(r.x + p.x), int(w.height - (r.y + p.y)))
    yield 0.6
    xdo('click', 1)
    t1 = time.perf_counter()
    while not target.select_get() and time.perf_counter() - t1 < 40:
        yield 0.5
    yield 2.0
    own = target.instance_collection == linked
    log('2 clicked', target.name, 'selected', target.select_get(), 'shows the linked collection itself', own)
    sp3.overlay.show_wireframes = True
    with C.temp_override(window=w, area=a, region=r):
        rv.view_location = target.matrix_world.translation.lerp(insts[8].matrix_world.translation, 0.5)
        rv.view_distance = 2.6
    yield 25.0
    shot('2_selected_full_vs_light_wire.png')
    sp3.overlay.show_wireframes = False
    with C.temp_override(window=w, area=a, region=r):
        rv.view_location = (0.0, 0.0, 0.0)
        rv.view_distance = 9.0
    yield from wait_draws(2)
    xdo('mousemove', int(r.x + r.width * 0.62), int(w.height - (r.y + r.height * 0.74)))
    yield 0.6
    xdo('click', 1)
    t1 = time.perf_counter()
    while target.select_get() and time.perf_counter() - t1 < 40:
        yield 0.5
    yield lc.REST + 4.0
    back = target.instance_collection is not None and bool(target.instance_collection.get(lc.SET))
    log('   clicked empty space: selected', target.select_get(), 'light again', back)
    res['2 a REAL click on an instance: the linked collection itself; a click beside: light again after it rests'] = \
        own and back
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
