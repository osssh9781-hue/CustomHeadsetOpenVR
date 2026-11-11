"""Real window (0.24.135, user: "뷰포트에서도 빨라야 돼"): Fast Viewport on 15 parts x 1.3 M triangles (19.7 M), software
OpenGL + CPU Cycles here (absolute times far slower than a real GPU - the ratios are what counts):
  1. Solid with the heavy extras the user may have on (Mecha Lab Wire on every part, shadows): the time of one redraw;
     a REAL click on the VIEW row's Fast; the time of one redraw again
  2. Blender's viewport anti-aliasing 8 Samples vs Single Pass: how many full redraws one view change costs
  3. Rendered (Cycles): the time until the viewport stops refining (the picture done) - Blender's defaults
     (1024 samples, full resolution) vs Fast (64, denoised, half resolution)
  4. Fast off (real click): everything back
"""
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
from mecha_lab.ui_gpu import ui_factor  # noqa: E402

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






def press(it):
    w, a, r = view3d()
    x, y = int(r.x + it.x + it.w / 2), int(w.height - (r.y + it.y + it.h / 2))
    xdo('mousemove', x, y)
    yield 0.6
    xdo('click', 1)
    yield 1.0

DRAWS = {'n': 0, 'last': 0.0}


def _count_draw():
    DRAWS['n'] += 1
    DRAWS['last'] = time.perf_counter()


def redraw_time(a, n=2):
    """Seconds one full redraw takes (median of n)."""
    out = []
    for _i in range(n):
        n0 = DRAWS['n']
        t0 = time.perf_counter()
        a.tag_redraw()
        while DRAWS['n'] == n0 and time.perf_counter() - t0 < 60:
            yield 0.01
        out.append(time.perf_counter() - t0)
        yield 0.5
    out.sort()
    return out[len(out) // 2]


def settle(change, quiet=4.0, limit=240.0):
    """After ``change``: (redraws, seconds until the last redraw) - waits until no redraw for ``quiet`` s."""
    n0 = DRAWS['n']
    t0 = time.perf_counter()
    DRAWS['last'] = t0
    change()
    while time.perf_counter() - t0 < limit:
        yield 0.1
        if time.perf_counter() - DRAWS['last'] > quiet and DRAWS['n'] > n0:
            break
    return DRAWS['n'] - n0, DRAWS['last'] - t0, time.perf_counter() - t0 >= limit


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
    sp = a.spaces.active
    res = {}
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=9, radius=0.45, location=(-2.2, -1.1, 0))
        src_ob = C.active_object
        src_me = src_ob.data
        parts = [src_ob]
        for i in range(1, 15):
            ob = bpy.data.objects.new(f'Part{i:02d}', src_me.copy())
            S.collection.objects.link(ob)
            ob.location = ((i % 5) * 1.1 - 2.2, (i // 5) * 1.1 - 1.1, 0.0)
            parts.append(ob)
        bpy.ops.object.light_add(type='AREA', location=(0, -2, 4))
        C.active_object.data.energy = 800
        rv = sp.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((1.0, 0.0, 0.5)).to_quaternion()
        rv.view_location = (0.0, 0.0, 0.0)
        rv.view_distance = 9.0
        for o in S.objects:
            o.select_set(False)
        S.render.engine = 'CYCLES'
        S.cycles.device = 'CPU'
        # what a user may have on: Mecha Lab's Wire on every part, shadows; Blender's default viewport settings
        for o in parts:
            o.show_wire = True
            o.show_all_edges = True
        sp.shading.show_shadows = True
        C.preferences.system.viewport_aa = '8'
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    log('scene: 15 parts,', sum(len(o.data.polygons) for o in parts) / 1e6, 'M triangles; Wire on all, shadows on')
    yield 30.0
    t_heavy = yield from redraw_time(a)
    shot('1_solid_wire_shadows.png')
    log(f'1 Solid, Wire on every part + shadows: one redraw {t_heavy:.2f} s')
    # the REAL click on Fast in the VIEW row
    from mecha_lab import zb_ui, fast_view as fv
    with C.temp_override(window=w, area=a, region=r):
        items = zb_ui.corner_items(C, r.width, r.height, ui_factor(C, r))
    fast = next((i for i in items if getattr(i, 'label', '') == 'Fast'), None)
    log('   Fast segment', fast and (round(fast.x), round(fast.y)))
    if fast is not None:
        yield from press(fast)
    yield 20.0
    log('   Fast on:', fv.on(S), 'wire', any(o.show_wire for o in parts), 'shadows', sp.shading.show_shadows)
    t_fast = yield from redraw_time(a)
    shot('2_solid_fast.png')
    log(f'   Solid with Fast: one redraw {t_fast:.2f} s')
    res[f'1 a REAL click on VIEW > Fast: Wire and shadows off; one Solid redraw {t_heavy:.1f} s -> {t_fast:.1f} s'] = \
        fv.on(S) and not any(o.show_wire for o in parts) and not sp.shading.show_shadows and t_fast < t_heavy
    # 2. viewport anti-aliasing: redraws after one view change
    C.preferences.system.viewport_aa = '8'
    yield 3.0
    n8, s8, _lim = yield from settle(lambda: setattr(rv, 'view_rotation', Euler((1.0, 0.0, 0.55)).to_quaternion()))
    C.preferences.system.viewport_aa = 'FXAA'
    yield 8.0
    n1, s1, _lim = yield from settle(lambda: setattr(rv, 'view_rotation', Euler((1.0, 0.0, 0.6)).to_quaternion()))
    log(f'2 one view change: AA 8 Samples -> {n8} redraws, busy {s8:.1f} s; Single Pass -> {n1} redraw(s), busy {s1:.1f} s')
    res[f'2 viewport AA: one view change = {n8} full redraws (8 Samples) vs {n1} (Single Pass)'] = n1 < n8
    C.preferences.system.viewport_aa = '8'
    # 3. Rendered (Cycles): until the picture is done - defaults vs Fast
    fv.restore(C)
    for o in parts:
        o.show_wire = False
    sp.shading.show_shadows = False
    sp.overlay.show_overlays = False
    yield 3.0
    nd, sd, lim_d = yield from settle(lambda: setattr(sp.shading, 'type', 'RENDERED'), quiet=6.0, limit=300.0)
    shot('3_rendered_defaults.png')
    log(f'3 Rendered, Blender defaults (1024 samples, full size): {nd} redraws, picture '
        + (f'still refining after {sd:.0f} s' if lim_d else f'done after {sd:.0f} s'))
    sp.shading.type = 'SOLID'
    yield 3.0
    fv.apply(C)
    yield 1.0
    nf, sf, lim_f = yield from settle(lambda: setattr(sp.shading, 'type', 'RENDERED'), quiet=6.0, limit=300.0)
    shot('4_rendered_fast.png')
    log(f'   Rendered, Fast (64 samples, denoised, half size): {nf} redraws, picture '
        + (f'still refining after {sf:.0f} s' if lim_f else f'done after {sf:.0f} s'))
    res[f'3 Rendered: the picture done in {sf:.0f} s with Fast vs ' + (f'not done after {sd:.0f} s' if lim_d else f'{sd:.0f} s')
        + ' with the defaults'] = (not lim_f) and (lim_d or sf < sd)
    sp.shading.type = 'SOLID'
    yield 3.0
    # 3b. Rendered with Solo (Blender's Local View: Cycles reads only the soloed part)
    for o in S.objects:
        o.select_set(False)
    parts[7].select_set(True)
    C.view_layer.objects.active = parts[7]
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.view_toggle(action='SOLO')
    yield 3.0
    with C.temp_override(window=w, area=a, region=r):
        rv.view_rotation = Euler((1.0, 0.0, 0.5)).to_quaternion()
        rv.view_distance = 9.0
    ns, ss, lim_s = yield from settle(lambda: setattr(sp.shading, 'type', 'RENDERED'), quiet=6.0, limit=300.0)
    shot('5_rendered_fast_solo.png')
    log(f'   Rendered, Fast + Solo (1 of 15 parts): {ns} redraws, picture '
        + (f'still refining after {ss:.0f} s' if lim_s else f'done after {ss:.0f} s'))
    res[f'3b Rendered with Solo (one part): the picture done in {ss:.0f} s (all 15 parts: {sf:.0f} s)'] = \
        (not lim_s) and ss < sf
    sp.shading.type = 'SOLID'
    yield 2.0
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.view_toggle(action='SOLO')
    sp.overlay.show_overlays = True
    yield 3.0
    # 4. Fast off by a real click: back
    with C.temp_override(window=w, area=a, region=r):
        items = zb_ui.corner_items(C, r.width, r.height, ui_factor(C, r))
    fast = next((i for i in items if getattr(i, 'label', '') == 'Fast'), None)
    if fast is not None:
        yield from press(fast)
    yield 15.0
    log('4 Fast off:', not fv.on(S), 'preview samples', S.cycles.preview_samples, 'pixel size', S.render.preview_pixel_size)
    res['4 a REAL click on Fast again: off, the Cycles viewport settings back (1024, AUTO)'] = \
        not fv.on(S) and S.cycles.preview_samples == 1024 and S.render.preview_pixel_size == 'AUTO'
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
