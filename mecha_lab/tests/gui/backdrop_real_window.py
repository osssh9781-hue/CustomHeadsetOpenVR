"""Real window (0.24.95 user: "배경 이미지를 넣을 수 있게 - 기본으로 몇 장, 세로 가로", "배경은 스튜디오 이미지처럼"):
MECHA LAB screen, a ball with Mech Painted, the HDRI on, the HDRI page: Show the HDRI off (a REAL click on its switch),
Picture (a REAL click), then REAL clicks on two studio backdrop previews (a wide one, a tall one with Fit); the Colour
Ramp switch (a REAL click; its ends set navy .. orange) and Edit Ramp… (a REAL click: Blender's ramp popup); the 3D view
in Material Preview looking through the camera - a shot after each.
    blender --window-geometry 0 0 W H --python this.py -- OUT"""
import os
import subprocess
import sys
import time

import bpy

sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/addon')
import mecha_lab  # noqa: E402

ARGS = sys.argv[sys.argv.index('--') + 1:]
OUT = ARGS[0]
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, 'log.txt'), 'w')


def log(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    LOG.write(s + '\n')
    LOG.flush()


mecha_lab.register()
from mecha_lab import color_pick as cp, mech_shader as ms, side_panel as sp, ui_gpu, workspace_ui  # noqa: E402
_real_shot_read = cp._screenshot_read


def _shot_read(*a, **k):
    log('(the eyedropper fell back to the screen capture)')
    return _real_shot_read(*a, **k)


cp._screenshot_read = _shot_read
# what the window does while previews are made: its 3D view drawn (times), redraws asked by a preview arriving, data
# changes (each one starts the 3D view's drawing again), pictures loaded by the panel
DRAWS, TAGS, DEPS, LOADS = [], [], [], []


def _since():
    return round(time.perf_counter() - TICK.get('t0', 0.0), 2)


def _draw_mark():
    if TICK.get('on'):
        DRAWS.append(_since())


bpy.types.SpaceView3D.draw_handler_add(_draw_mark, (), 'WINDOW', 'POST_PIXEL')
_real_redraw = ms._redraw


def _count_redraw():
    if TICK.get('on'):
        TAGS.append(_since())
    return _real_redraw()


ms._redraw = _count_redraw


def _deps(scene, dg):
    if TICK.get('on'):
        DEPS.append(_since())


bpy.app.handlers.depsgraph_update_post.append(_deps)
_real_tex = ui_gpu._texture


def _tex(path, mono=False, thumb=0):
    if (path, mono, thumb) not in ui_gpu._TEX and TICK.get('on'):
        LOADS.append(_since())
    return _real_tex(path, mono, thumb)


ui_gpu._texture = _tex
from mecha_lab.ui_gpu import ui_factor  # noqa: E402
C = bpy.context
S = C.scene

def xdo(*args):
    subprocess.run(['xdotool', *map(str, args)], check=False)


def focus():
    r = subprocess.run(['xdotool', 'search', '--name', 'Blender'], capture_output=True, text=True)
    for wid in r.stdout.split():
        subprocess.run(['xdotool', 'windowfocus', '--sync', wid], check=False)


def view3d():
    for w in C.window_manager.windows:
        for a in w.screen.areas:
            if a.type == 'VIEW_3D':
                return w, a, next(r for r in a.regions if r.type == 'WINDOW')
    return None, None, None


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


def scrolled_to(pred):
    for _n in range(150):
        it = next((i for i in panel_items() if pred(i)), None)
        if it is not None:
            return it
        scroll(60)
        yield 0.3
    return None


def shot(name):
    path = os.path.join(OUT, name)
    os.system(f'import -window root "{path}"')
    log('shot', name, os.path.exists(path))
    return path


def click(it):
    w, a, r = view3d()
    x, y = to_x(w, r, it.x + it.w / 2, it.y + it.h / 2)
    xdo('mousemove', x, y)
    return x, y


GAPS = []
TICK = {'on': False, 'last': 0.0}


def _gap_timer():
    now = time.perf_counter()
    if TICK['on']:
        GAPS.append(now - TICK['last'])
    TICK['last'] = now
    return 0.02


def measure(on):
    if on:
        GAPS.clear()
        DRAWS.clear()
        TAGS.clear()
        DEPS.clear()
        LOADS.clear()
        TICK['t0'] = time.perf_counter()
    TICK['on'] = on
    TICK['last'] = time.perf_counter()


def to_display(c):
    return [12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055 for v in c]


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
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.8)
        bpy.ops.object.shade_smooth()
        bpy.ops.mch.mech_shader_apply(preset='PAINTED')
        cd = bpy.data.cameras.new('Cam')
        cam = bpy.data.objects.new('Cam', cd)
        S.collection.objects.link(cam)
        cam.location, cam.rotation_euler = (0.0, -5.0, 0.3), (1.5108, 0.0, 0.0)
        S.camera = cam
        S.render.resolution_x, S.render.resolution_y = 1920, 1080
        sp3 = a.spaces.active
        sp3.shading.type = 'MATERIAL'
        sp3.overlay.show_overlays = False
        sp3.show_region_ui = False
        sp3.region_3d.view_perspective = 'CAMERA'
        bpy.ops.mch.bar_tool(tool='SELECT')
        bpy.ops.mch.mech_hdri(action='SET')
        bpy.ops.mch.side_page(page='HDRI')
    yield 25.0
    shot('1_hdri_on.png')

    def find(pred):
        return next((i for i in panel_items() if pred(i)), None)
    sw_ = yield from scrolled_to(lambda i: getattr(i, 'prop', '') == 'mch_mech_hdri_show')
    click(sw_)
    yield 0.3
    xdo('click', 1)
    yield 3.0
    log('Show the HDRI', S.mch_mech_hdri_show)
    pic = yield from scrolled_to(lambda i: i.kind == 'tbtn' and i.label == 'Picture')
    click(pic)
    yield 0.3
    xdo('click', 1)
    yield 3.0
    for name, fit in (('Grey Spot', None), ('Warm Paper - Tall', 'Fit')):
        if fit:
            fb = yield from scrolled_to(lambda i, f=fit: i.kind == 'tbtn' and i.label == f)
            click(fb)
            yield 0.3
            xdo('click', 1)
            yield 2.0
        tile = yield from scrolled_to(lambda i, n=name: i.kind == 'btile' and i.label == n)
        if tile is None:
            nxt = find(lambda i: i.kind == 'tbtn' and i.action and i.action[:2] == ('op', 'mch.mech_bg_page')
                       and i.action[2].get('step') == 1)
            click(nxt)
            yield 0.3
            xdo('click', 1)
            yield 2.0
            tile = yield from scrolled_to(lambda i, n=name: i.kind == 'btile' and i.label == n)
        click(tile)
        yield 0.3
        xdo('click', 1)
        xdo('mousemove', 900, 800)
        yield 25.0
        log('clicked', name, '-> mode', S.mch_mech_hdri_bg_mode, 'picture', S.mch_mech_hdri_bg_image, 'fit',
            S.mch_mech_hdri_bg_fit, 'tiles on', [i.label for i in panel_items() if i.kind == 'btile' and i.on])
        shot(f'2_{name.replace(" ", "_")}.png')
    # ---- the Colour Ramp (user: "사진에 컬러램프 기능 넣어 주라"): a real click on its switch, the ramp's ends set
    ramp_sw = yield from scrolled_to(lambda i: getattr(i, 'prop', '') == 'mch_mech_hdri_bg_ramp')
    click(ramp_sw)
    yield 0.3
    xdo('click', 1)
    yield 2.0
    from mecha_lab import backdrops as bd
    rn = bd.ramp_node(S)
    log('Colour Ramp', S.mch_mech_hdri_bg_ramp, 'ramp node', rn is not None)
    if rn is not None:
        rn.color_ramp.elements[0].color = (0.01, 0.02, 0.08, 1.0)
        rn.color_ramp.elements[1].color = (1.0, 0.55, 0.2, 1.0)
    for lab in ('Dark', 'Light', 'Edit Ramp…'):
        log('panel has', lab, any(i.label == lab for i in panel_items()))
    xdo('mousemove', 900, 800)
    yield 25.0
    shot('3_ramp_on.png')
    er = yield from scrolled_to(lambda i: i.kind == 'tbtn' and i.label == 'Edit Ramp…')
    click(er)
    yield 0.3
    xdo('click', 1)
    yield 3.0
    shot('4_edit_ramp_popup.png')
    xdo('key', 'Escape')
    yield 1.0
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
