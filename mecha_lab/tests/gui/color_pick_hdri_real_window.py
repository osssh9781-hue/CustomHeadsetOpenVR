"""Real window (0.24.95): the colour picker's Hue / Saturation / Value + Pick (user: "컬러 피커에 휴 · 새츄레이션 · 밸류 다
넣어 주고 스포이드도 넣어 줘") and a big HDRI folder (user: "hdri 뭉탱이로 불러왔더니 캐무거워").

* MECHA LAB screen, a cube with Mech Painted, the Mech page: a REAL click (xdotool) on the Base Color swatch - the popup
  (shot); then the eyedropper (mch.color_eyedrop) and a REAL click on the viewport's plain green background - the
  swatch takes that green (compared with the screen picture's own pixel)
* a folder (made here, in OUT) of three folders A B C x 6 links to one 8k EXR (+ Blender's 8: 26, 5 pages of 6): the
  HDRI page shows the page of the HDRI in use; a REAL click on the page's ◀ turns to folder C's 6 - their previews
  made by a second Blender while a 20 ms timer measures how long the window stops; ◀ again (folder B) the old way
  (made here, one per tick) - the same measure; REAL clicks on two previews: the HDRI picked before let go (one HDRI
  image in memory)
    blender --window-geometry 0 0 W H --python this.py -- OUT BIG_EXR"""
import os
import subprocess
import sys
import time

import bpy

sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/addon')
import mecha_lab  # noqa: E402

ARGS = sys.argv[sys.argv.index('--') + 1:]
OUT, BIG = ARGS[0], ARGS[1]
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

HD = os.path.join(OUT, 'hdris')
for g in ('A', 'B', 'C'):
    os.makedirs(os.path.join(HD, g), exist_ok=True)
    for i in range(6):
        p = os.path.join(HD, g, f'{g.lower()}_{i}.exr')
        if not os.path.exists(p):
            os.symlink(BIG, p)
real_pref = workspace_ui.pref
workspace_ui.pref = lambda name, default=True: HD if name == 'hdri_folder' else real_pref(name, default)
ms.rescan()


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
        bpy.ops.mesh.primitive_cube_add(size=0.6, location=(0.0, 0.0, 0.0))
        part = C.active_object
        bpy.ops.mch.mech_shader_apply(preset='PAINTED')
        sp3 = a.spaces.active
        sp3.shading.type = 'SOLID'
        sp3.shading.background_type = 'VIEWPORT'
        sp3.shading.background_color = (0.05, 0.6, 0.12)
        sp3.overlay.show_floor = False
        sp3.overlay.show_axis_x = sp3.overlay.show_axis_y = False
        sp3.show_region_ui = False
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_location = (0.0, 0.0, 0.0)
        rv.view_distance = 6.0
        bpy.ops.mch.bar_tool(tool='SELECT')
        bpy.ops.mch.side_page(page='MATERIAL')
    st = part.active_material.mch_mech
    st.base_color = (0.6, 0.1, 0.05)
    bpy.app.timers.register(_gap_timer, first_interval=0.02, persistent=True)
    xdo('mousemove', 300, 1200)
    yield 8.0
    # ---- the Base Color swatch: a real click - the picker
    sw = yield from scrolled_to(lambda i: i.kind == 'swatch' and getattr(i, 'prop', '') == 'base_color')
    log('swatch', sw is not None)
    click(sw)
    yield 0.4
    xdo('click', 1)
    yield 2.0
    shot('1_picker_popup.png')
    log('picker: H S V', round(C.window_manager.mch_pick_h, 3), round(C.window_manager.mch_pick_s, 3),
        round(C.window_manager.mch_pick_v, 3), 'colour', [round(v, 3) for v in st.base_color])
    xdo('key', 'Escape')
    xdo('mousemove', 300, 1200)
    yield 1.0
    # ---- the eyedropper, a real click on the plain green background (left of the cube)
    w, a, r = view3d()
    px, py = r.width * 0.30, r.height * 0.55
    with C.temp_override(window=w, area=a, region=r):
        res = bpy.ops.mch.color_eyedrop('INVOKE_DEFAULT')
    log('eyedropper invoked', res)
    X, Y = to_x(w, r, px, py)
    xdo('mousemove', X, Y)
    yield 0.6
    ref = shot('2_before_pick.png')
    xdo('click', 1)
    yield 1.5
    got = to_display(tuple(st.base_color))
    seen = None
    try:
        out = subprocess.run(['convert', ref, '-format', f'%[pixel:p{{{X},{Y}}}]', 'info:'], capture_output=True,
                             text=True).stdout
        seen = out.strip()
    except OSError:
        pass
    log('picked: swatch (display)', [round(v, 3) for v in got], 'screen pixel there', seen)
    log('PICK_OK', got[1] > got[0] * 2 and got[1] > got[2] * 2)
    shot('3_after_pick.png')
    # ---- the HDRI page: a big folder
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.side_page(page='HDRI')
        sp3 = a.spaces.active
        sp3.shading.type = 'SOLID'            # (software OpenGL here: a Material Preview redraw alone takes long -
        #                                        the add-on's own stops measured)
    yield 3.0
    its = panel_items()
    log('HDRI page:', [i.label for i in its if i.kind == 'tbtn' and i.label.startswith('Page ')],
        'previews', [i.label for i in its if i.kind == 'htile'])
    shot('4_hdri_page.png')

    def pager(step):
        return next((i for i in panel_items() if i.kind == 'tbtn' and i.action[:2] == ('op', 'mch.mech_hdri_page')
                     and i.action[2].get('step') == step), None)
    w, a, r = view3d()
    measure(True)                                  # (a baseline: 3 s of nothing)
    yield 3.0
    measure(False)
    log('IDLE 3 s: ticks', len(GAPS), 'longest', round(max(GAPS) * 1000) if GAPS else None, 'ms')
    measure(True)                                  # (one redraw of the 3D view, asked for)
    a.tag_redraw()
    yield 1.5
    measure(False)
    log('ONE REDRAW: longest', round(max(GAPS) * 1000) if GAPS else None, 'ms')
    # ---- ◀ (a real click): folder C's page, made by the second Blender
    click(pager(-1))
    yield 0.3
    measure(True)
    t0 = time.perf_counter()
    xdo('click', 1)
    yield 0.3
    xdo('mousemove', 1300, 900)                    # (the mouse off the panel, over the empty view)
    for _n in range(400):
        yield 0.2
        if ms.thumbs_pending() == 0 and time.perf_counter() - t0 > 1.0:
            break
    took = time.perf_counter() - t0
    measure(False)
    new_gap = max(GAPS) if GAPS else -1.0
    its = panel_items()
    tiles = [i for i in its if i.kind == 'htile']
    made = sum(1 for i in tiles if i.icon.startswith('file:'))
    log('after ◀:', [i.label for i in its if i.kind == 'tbtn' and i.label.startswith('Page ')], [i.label for i in tiles])
    log(f'NEW (second Blender): 6 previews in {took:.1f} s, the window\'s longest stop {new_gap * 1000:.0f} ms '
        f'(timer every 20 ms: {len(GAPS)} ticks); previews shown {made}/{len(tiles)}')
    log('NEW stops over 100 ms', [round(g * 1000) for g in GAPS if g > 0.1])
    log('NEW 3D view drawn at', DRAWS, '; a preview arrived (redraw asked) at', TAGS, '; data changes', DEPS,
        '; pictures loaded by the panel at', LOADS)
    measure(True)                                  # (after: 3 s of nothing - do the redraws stop?)
    yield 3.0
    measure(False)
    log('AFTER (3 s of nothing): ticks', len(GAPS), 'longest', round(max(GAPS) * 1000) if GAPS else None,
        'ms; 3D view drawn', DRAWS, '; worker gone', not ms._THUMB_JOB)
    shot('5_hdri_page_c.png')
    # ---- ◀ again: folder B's page the old way (made here, one per tick)
    ms.thumbs_in_background = lambda: False
    click(pager(-1))
    yield 0.3
    measure(True)
    t0 = time.perf_counter()
    xdo('click', 1)
    yield 0.3
    xdo('mousemove', 1300, 900)
    for _n in range(400):
        yield 0.2
        if ms.thumbs_pending() == 0 and time.perf_counter() - t0 > 1.0:
            break
    took = time.perf_counter() - t0
    measure(False)
    old_gap = max(GAPS) if GAPS else -1.0
    log(f'OLD (in this Blender): 6 previews in {took:.1f} s, the window\'s longest stop {old_gap * 1000:.0f} ms '
        f'(timer every 20 ms: {len(GAPS)} ticks)')
    log('OLD stops over 100 ms', [round(g * 1000) for g in GAPS if g > 0.1])
    # ---- two previews clicked: the HDRI before let go
    for name in ('b_1', 'b_2'):
        t = yield from scrolled_to(lambda i, n=name: i.kind == 'htile' and i.label == n)
        click(t)
        yield 0.3
        xdo('click', 1)
        yield 4.0
        hd = [im.name for im in bpy.data.images if im.filepath.lower().endswith('.exr')]
        log('clicked', name, '-> HDRI', S.mch_mech_hdri, 'HDRI images in memory', hd)
    shot('6_hdri_picked.png')
    log('DONE')
    ms.cancel_thumbs()
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
