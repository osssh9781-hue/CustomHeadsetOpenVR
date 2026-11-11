"""Real window (0.24.134, user: "1억 폴리곤이면?" - GAMERA 192 M triangles, 64 GB RAM, RTX 5090): the Quick Render
section shows the triangles that will render and what Cycles needs against the free RAM; when the RAM is short (simulated
here: the free memory read as 1 KB) a click on the dock tile does not render but warns (toast), a second click within
15 s renders; with a GPU set (simulated: the panel then offers CPU Only) a real click on CPU Only turns it on.
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
    WM = C.window_manager
    res = {}
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        a.spaces.active.show_region_ui = False
        a.spaces.active.overlay.show_wireframes = True
        WM.mch_layers_min = True
        WM.mch_legend_min = True
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=48, ring_count=24, location=(0.0, 0.0, 1.0))
        body = C.active_object
        body.data.remesh_voxel_size = 0.008
        bpy.ops.object.voxel_remesh()
        m = body.modifiers.new('Mirror', 'MIRROR')
        body.location.x = 1.2
        bpy.ops.object.light_add(type='AREA', location=(2.5, -3.0, 4.0))
        cd = bpy.data.cameras.new('Cam')
        cam = bpy.data.objects.new('Cam', cd)
        S.collection.objects.link(cam)
        cam.location, cam.rotation_euler = (0.0, -9.0, 1.0), (1.5708, 0.0, 0.0)
        S.camera = cam
        rv = a.spaces.active.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((1.15, 0.0, 0.3)).to_quaternion()
        rv.view_location = (0.0, 0.0, 0.8)
        rv.view_distance = 8.0
        st = S.mch_qrender
        st.folder = os.path.join(OUT, 'renders')
        st.quality = 'DRAFT'
        bpy.ops.mch.side_page(page='HDRI')
    me_tris = len(body.data.loops) - 2 * len(body.data.polygons)
    yield 3.0
    labels = [i.label for i in panel_items() if getattr(i, 'label', '')]
    mem = [lb for lb in labels if lb.startswith(('Scene: ', 'Cycles needs'))]
    log('1 body triangles (no modifier)', me_tris, 'panel memory lines', mem)
    res['1 the panel shows the triangles that will render (the Mirror doubles them) and Cycles\' memory vs free RAM'] = \
        len(mem) == 2 and mem[0] == f'Scene: {qr._count(2 * me_tris)} triangles' and 'free RAM' in mem[1]
    shot('1_memory_lines.png')
    # 2. the RAM short (simulated): the first click warns, nothing renders; the second renders
    real_ram = qr.ram_info
    qr.ram_info = lambda: (64 * 2 ** 30, 1000.0)
    qr.LOAD['t'] = -1e9
    yield 1.0
    tile = dock_tile('Quick Render')
    if tile is not None:
        yield from press(tile)
    yield 1.5
    first = (qr._JOB.get('active'), bpy.app.is_job_running('RENDER'), len(C.window_manager.windows))
    log('2 first click: job', first, 'confirm armed', qr.CONFIRM['t'] > 0)
    shot('2_warning_toast.png')
    focus()
    if tile is not None:
        yield from press(tile)
    yield 2.0
    second = (qr._JOB.get('active'), bpy.app.is_job_running('RENDER'))
    log('   second click: job', second)
    dt = yield from wait_render(600)
    qr.ram_info = real_ram
    files = sorted(f for f in os.listdir(st.folder) if f.endswith('.png')) if os.path.isdir(st.folder) else []
    log('   finished after', round(dt, 1), 's, files', files)
    res['2 RAM short: the first click warns and does not render; the second click (within 15 s) renders'] = \
        not first[0] and not first[1] and second[0] and len(files) == 1
    for win in list(C.window_manager.windows)[1:]:
        with C.temp_override(window=win):
            try:
                bpy.ops.wm.window_close()
            except RuntimeError as ex:
                log('   close window:', ex)
    yield 1.5
    # 3. a GPU set (simulated): the panel offers CPU Only - a real click turns it on
    real_state = qr.gpu_state
    qr.gpu_state = lambda context=None, refresh=False: ('OPTIX', ['NVIDIA GeForce RTX 5090'])
    sp.dirty() if hasattr(sp, 'dirty') else None
    yield 1.5
    focus()
    cell = next((i for i in panel_items() if getattr(i, 'label', '') == 'CPU Only (scene too big for the GPU)'
                 and i.clickable()), None)
    log('3 CPU Only cell', cell is not None)
    if cell is not None:
        yield from press(cell)
    yield 1.0
    dev_line = qr.status_lines(C)[0]
    log('   cpu_only', st.cpu_only, 'device line', dev_line)
    shot('3_cpu_only.png')
    res['3 with a GPU set: a real click on CPU Only turns it on, the device line says the GPU is not used'] = \
        st.cpu_only and dev_line.startswith('CPU (CPU Only on')
    qr.gpu_state = real_state
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
