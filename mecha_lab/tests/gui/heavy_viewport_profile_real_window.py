"""Real window (0.24.135, user: "뷰포트에서도 빨라야 돼"): how much time the add-on's own Python takes in a heavy scene
(15 parts x 0.33 M triangles - Blender's ico sphere "subdivisions 8" - separate meshes, 4 with Mirror: about
6.2 M triangles) on the MECHA LAB screen - idle, orbiting the
view, moving a part, clicking parts.  Profiled with cProfile across Blender's timers / draw / depsgraph callbacks; the
add-on's functions summed (file under addon/mecha_lab)."""
import os
import subprocess
import sys
import time

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'addon'))
import mecha_lab  # noqa: E402
from mecha_lab import quick_render as qr, side_panel as sp, ui_bars  # noqa: E402
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


def to_x(w, r, x, y):
    return int(r.x + x), int(w.height - (r.y + y))


def panel_items():
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        return sp.items(C, r.width, r.height, ui_factor(C, r))


def scroll(dy):
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        sp.scroll_by(C, r.width, r.height, ui_factor(C, r), dy)
        a.tag_redraw()


def press(it):
    w, a, r = view3d()
    x, y = to_x(w, r, it.x + it.w / 2, it.y + it.h / 2)
    xdo('mousemove', x, y)
    yield 0.4
    xdo('click', 1)
    yield 1.0


def dock_tile(label):
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        items = ui_bars.drawn_items(C)
    return next((i for i in items if getattr(i, 'label', '') == label and i.clickable()), None)


def settings_snapshot(S, body, box):
    r_, cy = S.render, S.cycles
    keys = [(r_, 'engine'), (r_, 'resolution_x'), (r_, 'resolution_y'), (r_, 'resolution_percentage'),
            (r_, 'film_transparent'), (r_, 'use_lock_interface'), (r_, 'use_border'), (r_, 'pixel_aspect_x'),
            (r_.image_settings, 'file_format'), (r_.image_settings, 'color_mode'), (cy, 'samples'), (cy, 'max_bounces'),
            (cy, 'diffuse_bounces'), (cy, 'glossy_bounces'), (cy, 'adaptive_threshold'), (cy, 'use_adaptive_sampling'),
            (cy, 'use_denoising'), (cy, 'denoising_prefilter'), (cy, 'device'), (cy, 'caustics_reflective'),
            (cy, 'blur_glossy'), (cy, 'volume_bounces'), (S, 'camera'), (C.view_layer, 'material_override'),
            (body, 'hide_render'), (box, 'hide_render')]
    vals = [getattr(o, a) for o, a in keys]
    shade = []
    for mat in {m for ob in (body, box) for m in ob.data.materials if m and m.node_tree}:
        for n in mat.node_tree.nodes:
            if n.bl_idname in qr.RAY_NODES:
                shade.append((mat.name, n.name, n.samples))
            elif n.bl_idname == 'ShaderNodeBsdfPrincipled':
                shade.append((mat.name, n.name, n.subsurface_method))
    return [a for _o, a in keys], vals, sorted(shade, key=str)


def diff(a, b):
    return [(k, x, y) for k, x, y in zip(a[0], a[1], b[1]) if x != y] + ([('shaders', a[2], b[2])] if a[2] != b[2] else [])


def alpha_bbox(path):
    import numpy as np
    img = bpy.data.images.load(path, check_existing=False)
    w_, h_ = img.size
    px = np.empty(w_ * h_ * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    al = px.reshape(h_, w_, 4)[:, :, 3]
    ys, xs = np.nonzero(al > 0.5)
    bpy.data.images.remove(img)
    if not len(xs):
        return (w_, h_), None
    # (normalised 0..1, y up as Blender's pixels are bottom-up)
    return (w_, h_), (xs.min() / w_, ys.min() / h_, (xs.max() + 1) / w_, (ys.max() + 1) / h_)


def view_bbox(obs):
    import numpy as np
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    w, a, r = view3d()
    rv = a.spaces.active.region_3d
    pts = []
    for ob in obs:
        me = ob.data
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)[::7 if len(me.vertices) > 1000 else 1]
        mw = ob.matrix_world
        pts += [location_3d_to_region_2d(r, rv, mw @ Vector(p)) for p in co]
    pts = [p for p in pts if p is not None]
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    return (min(xs) / r.width, min(ys) / r.height, max(xs) / r.width, max(ys) / r.height)


def wait_render(limit):
    t0 = time.monotonic()
    while qr._JOB.get('active') and time.monotonic() - t0 < limit:
        yield 0.5
    return time.monotonic() - t0



import cProfile  # noqa: E402
import pstats  # noqa: E402

PROF = {'p': None, 't0': 0.0}
REDRAWS = {'n': 0}


def _count_draw():
    REDRAWS['n'] += 1


def prof_on():
    PROF['p'] = cProfile.Profile()
    PROF['t0'] = time.perf_counter()
    REDRAWS['n'] = 0
    PROF['p'].enable()


def prof_off(tag, top=14):
    p = PROF['p']
    p.disable()
    wall = time.perf_counter() - PROF['t0']
    st = pstats.Stats(p)
    rows = []
    addon_tt = 0.0
    for (fn, line, name), (cc, nc, tt, ct, callers) in st.stats.items():
        if '/addon/mecha_lab/' in fn:
            addon_tt += tt
            rows.append((ct, tt, nc, fn.split('/addon/mecha_lab/')[-1] + ':' + str(line) + ' ' + name))
    rows.sort(reverse=True)
    log(f'== {tag}: wall {wall:.1f} s, redraws {REDRAWS["n"]}, add-on own time {addon_tt:.3f} s '
        f'({addon_tt / max(wall, 1e-9) * 100:.1f} %), per redraw {addon_tt / max(REDRAWS["n"], 1) * 1000:.1f} ms')
    for ct, tt, nc, name in rows[:top]:
        log(f'   cum {ct:7.3f}  own {tt:7.3f}  calls {nc:6d}  {name}')
    return addon_tt, wall


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
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=8, radius=0.45, location=(0, 0, 0))
        src_ob = C.active_object
        src_me = src_ob.data
        parts = [src_ob]
        for i in range(1, 15):
            ob = bpy.data.objects.new(f'Part{i:02d}', src_me.copy())
            S.collection.objects.link(ob)
            ob.location = ((i % 5) * 1.1 - 2.2, (i // 5) * 1.1 - 1.1, 0.0)
            parts.append(ob)
        src_ob.location = (-2.2, -1.1, 0.0)
        for ob in parts[::4]:
            ob.modifiers.new('Mirror', 'MIRROR')
        bpy.ops.object.light_add(type='SUN', location=(0, 0, 5))
        rv = a.spaces.active.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((1.0, 0.0, 0.5)).to_quaternion()
        rv.view_location = (0.0, 0.0, 0.0)
        rv.view_distance = 9.0
        for o in S.objects:
            o.select_set(False)
    C.view_layer.update()
    tris = sum(len(o.evaluated_get(C.evaluated_depsgraph_get()).data.loop_triangles) for o in parts)
    log('scene', len(parts), 'parts,', f'{tris / 1e6:.1f} M triangles (evaluated)')
    yield 20.0                                       # (the first draw of 20 M triangles in software GL)
    shot('0_heavy_scene.png')
    # 1. idle 20 s
    prof_on()
    yield 20.0
    idle = prof_off('idle 20 s')
    # 2. orbit: the view turned a little every tick
    prof_on()
    t0 = time.perf_counter()
    k = 0
    while time.perf_counter() - t0 < 25.0:
        rv.view_rotation = Euler((1.0, 0.0, 0.5 + 0.02 * k)).to_quaternion()
        a.tag_redraw()
        k += 1
        yield 0.05
    orbit = prof_off('orbit 25 s')
    # 3. move a part: its location changed every tick (depsgraph updates + handlers)
    mover = parts[5]
    mover.select_set(True)
    C.view_layer.objects.active = mover
    prof_on()
    t0 = time.perf_counter()
    k = 0
    while time.perf_counter() - t0 < 25.0:
        mover.location.z = 0.02 * (k % 20)
        k += 1
        yield 0.05
    move = prof_off('move a part 25 s')
    # 4. clicks on parts (real clicks: Blender's selection + the add-on's click handling)
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    prof_on()
    for ob in parts[:6]:
        p = location_3d_to_region_2d(r, rv, ob.matrix_world.translation)
        if p is None:
            continue
        x, y = int(r.x + p.x), int(w.height - (r.y + p.y))
        xdo('mousemove', x, y)
        yield 0.5
        xdo('click', 1)
        yield 4.0
    clicks = prof_off('6 clicks on parts')
    log('selected after clicks', [o.name for o in C.selected_objects])
    bpy.types.SpaceView3D.draw_handler_remove(handle, 'WINDOW')
    log('DONE')
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
