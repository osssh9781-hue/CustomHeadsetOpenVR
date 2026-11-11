"""Real window (0.24.133, user: "폴리곤이 높아서 렌더링이 빡센데 좀 더 빠르고 편하게 렌더 못 하나?", "난 사이클만 써"):
Quick Render (Cycles) clicked for real on the actions dock, the render running in Blender's render window (the UI not
blocked), the picture saved, every scene setting back - and the picture framed like the viewport.

  1. MECHA LAB screen, a dense creature-shaded body (voxel remesh + Creature Shader: AO nodes, random-walk skin) and a
     Mech-shaded box, a light; the viewport at an angle (not through a camera); the scene's own heavy settings
  2. the HDRI page: QUICK RENDER (CYCLES) section; a real click on Final, then on Draft (the quality switch)
  3. a real click on the dock's Quick Render tile (Draft, Transparent): the render window, the job runs, then: the PNG
     saved (half the scene's long side, the viewport's shape), all settings back, the temporary camera gone, no empty
     entry in view_layer.objects; the body's outline in the picture = its outline in the viewport
  4. a second click (Preview) and Esc in the render window: "Stopped", nothing saved, all back
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
        # 1. a dense body with the Creature Shader, a Mech box, a light, a (scene) camera somewhere else
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=48, ring_count=24, location=(0.0, 0.0, 1.0))
        body = C.active_object
        body.name = 'Body'
        body.data.remesh_voxel_size = 0.012
        bpy.ops.object.voxel_remesh()
        bpy.ops.object.shade_smooth()
        bpy.ops.mch.creature_apply()
        bpy.ops.mesh.primitive_cube_add(size=0.8, location=(1.9, 0.4, 0.4))
        box = C.active_object
        box.name = 'Box'
        bpy.ops.mch.mech_shader_apply(preset='PAINTED')
        bpy.ops.object.light_add(type='AREA', location=(2.5, -3.0, 4.0))
        C.active_object.data.energy = 900
        C.active_object.data.size = 3.0
        cd = bpy.data.cameras.new('Cam')
        cam = bpy.data.objects.new('Cam', cd)
        S.collection.objects.link(cam)
        cam.location, cam.rotation_euler = (0.0, -9.0, 1.0), (1.5708, 0.0, 0.0)
        S.camera = cam
        # the scene's own (heavy) render settings - Quick Render leaves them as they are
        S.render.engine = 'CYCLES'
        S.render.resolution_x, S.render.resolution_y, S.render.resolution_percentage = 1920, 1080, 100
        S.cycles.samples, S.cycles.max_bounces = 4096, 12
        S.render.image_settings.file_format = 'JPEG'
        for o in S.objects:
            o.select_set(False)
        body.select_set(True)
        C.view_layer.objects.active = body
        rv = a.spaces.active.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((1.15, 0.0, 0.55)).to_quaternion()
        rv.view_location = (0.5, 0.0, 0.8)
        rv.view_distance = 6.5
        st = S.mch_qrender
        st.folder = os.path.join(OUT, 'renders')
        bpy.ops.mch.side_page(page='HDRI')
    log('1 body verts', len(body.data.vertices), 'region', r.width, 'x', r.height)
    yield 3.0
    shot('1_viewport_wire.png')
    # 2. the HDRI page section; real clicks on Final, then Draft
    labels = [i.label for i in panel_items() if getattr(i, 'label', '')]
    log('2 panel', labels[:20])
    res['2 the HDRI page opens with QUICK RENDER (CYCLES): Quick Render, Draft / Preview / Final, This View, the device line'] = \
        any(lb.startswith('QUICK RENDER (CYCLES)') for lb in labels) and {'Quick Render', 'Draft', 'Preview', 'Final', 'This View'} <= set(labels) \
        and any(lb.startswith('CPU only') for lb in labels)
    shot('2_hdri_page_section.png')
    fin = next((i for i in panel_items() if i.label == 'Final' and i.clickable()), None)
    if fin is not None:
        yield from press(fin)
    q1 = st.quality
    dr = next((i for i in panel_items() if i.label == 'Draft' and i.clickable()), None)
    if dr is not None:
        yield from press(dr)
    log('   quality after clicking Final:', q1, '- after Draft:', st.quality)
    res['2b real clicks on Final, then Draft switch the quality'] = q1 == 'FINAL' and st.quality == 'DRAFT'
    st.transparent = True                         # (the outline from the alpha: the framing check)
    yield 0.5
    before = settings_snapshot(S, body, box)
    exp = qr.view_frame(r.width, r.height, 1920)
    exp = (exp[0] * 50 // 100, exp[1] * 50 // 100)
    vb = view_bbox((body, box))                       # (the picture's alpha holds both)
    # 3. a real click on the dock's Quick Render tile
    tile = dock_tile('Quick Render')
    log('3 dock tile', (tile.x, tile.y, tile.w, tile.h) if tile else None)
    n_win = len(C.window_manager.windows)
    if tile is not None:
        yield from press(tile)
    yield 3.0
    running = qr._JOB.get('active') and bpy.app.is_job_running('RENDER')
    log('   3 s after the click: job active', qr._JOB.get('active'), 'render job', bpy.app.is_job_running('RENDER'),
        'windows', n_win, '->', len(C.window_manager.windows), 'camera now', S.camera.name if S.camera else None)
    shot('3_rendering.png')
    dt = yield from wait_render(900)
    yield 1.0
    shot('3b_render_done.png')
    files = sorted(f for f in os.listdir(st.folder) if f.endswith('.png')) if os.path.isdir(st.folder) else []
    log('   finished after', round(dt, 1), 's; LAST', qr.LAST.get('text'), 'files', files)
    after = settings_snapshot(S, body, box)
    size, ab = alpha_bbox(os.path.join(st.folder, files[0])) if files else ((0, 0), None)
    log('   picture', size, 'expected', exp, 'alpha bbox', ab and tuple(round(v, 3) for v in ab),
        'viewport bbox', tuple(round(v, 3) for v in vb))
    res['3 the dock tile starts the render in the render window (the job runs, the UI is not blocked)'] = bool(running)
    res['3b ... one PNG saved: half the scene\'s long side, the viewport\'s shape'] = len(files) == 1 and tuple(size) == tuple(exp)
    res['3c ... every scene setting back (engine, size, 4096 samples, 12 bounces, JPEG, camera, AO rays, random-walk skin)'] = \
        not diff(before, after)
    res['3d ... the temporary camera gone, no empty entry in view_layer.objects, the last line "<s> s - <file>"'] = \
        not bpy.data.objects.get(qr.CAM_NAME) and all(o is not None for o in C.view_layer.objects) \
        and ' s - ' in qr.LAST.get('text', '')
    res['3e ... framed as in the viewport: the parts\' outline in the picture = in the viewport (within 1.5 %)'] = \
        ab is not None and max(abs(x - y) for x, y in zip(ab, vb)) < 0.015
    if diff(before, after):
        log('   DIFF', diff(before, after))
    # 4. Preview, then Esc in the render window
    for win in list(C.window_manager.windows)[1:]:                   # (the render window from 3)
        with C.temp_override(window=win):
            try:
                bpy.ops.wm.window_close()
            except RuntimeError as ex:
                log('   close window:', ex)
    yield 1.5
    st.quality, st.transparent = 'PREVIEW', False
    focus()
    tile = dock_tile('Quick Render')
    if tile is not None:
        yield from press(tile)
    yield 6.0
    log('4 Preview running', qr._JOB.get('active'), bpy.app.is_job_running('RENDER'), 'windows', len(C.window_manager.windows))
    shot('4_preview_running.png')
    ids = wins()
    log('   X windows', ids)
    if ids:
        focus(ids[-1])
        xdo('mousemove', 1280, 800)
        yield 0.4
        xdo('key', 'Escape')
    dt = yield from wait_render(120)
    yield 1.0
    files2 = sorted(f for f in os.listdir(st.folder) if f.endswith('.png'))
    after2 = settings_snapshot(S, body, box)
    log('   after Esc:', round(dt, 1), 's; LAST', qr.LAST.get('text'), 'files', files2)
    res['4 Esc in the render window: "Stopped after ...", nothing more saved, every setting back'] = \
        qr.LAST.get('text', '').startswith('Stopped') and files2 == files and not diff(before, after2)
    shot('4b_after_esc.png')
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
