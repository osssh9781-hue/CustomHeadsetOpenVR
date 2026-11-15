"""Blender 5.3.0 crash, not Mecha Lab (user: "렌더 모드일 때 쉐이더 탭 끌어올리면 꺼져", 0.24.174): an Asset Browser collapsed to
its header (All libraries, online access not chosen yet), its list loaded, then its border dragged up with the real
mouse - the first draw of its main region writes ``sfile->layout->dirty`` before the layout exists
(file_banners_update, a write to 0x40).  Factory settings, no add-on:

    blender --factory-startup --window-geometry 0 0 2560 1600 --python blender53_asset_browser_crash.py -- plain|handled|local <out>

plain: crashes (5.3.0 02f0899d78e3); handled (Continue Offline chosen) and local (Current File): no crash."""
import os, subprocess, sys, time
import bpy
OUT = sys.argv[-1]
MODE = sys.argv[-2]
LOG = open(os.path.join(OUT, 'log.txt'), 'w')
def log(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); LOG.write(s + '\n'); LOG.flush()
def xdo(*args):
    subprocess.run(['xdotool', *map(str, args)], check=False)
C = bpy.context
def bottom():
    w = C.window_manager.windows[0]
    ar = [a for a in w.screen.areas if a.ui_type in ('TIMELINE', 'ASSETS', 'DOPESHEET', 'DOPESHEET_EDITOR')]
    if not ar:
        log('areas', [(a.ui_type, a.x, a.y, a.width, a.height) for a in w.screen.areas])
    return w, min(ar, key=lambda a: a.y)
def main_h(a):
    r = next(r for r in a.regions if r.type == 'WINDOW')
    return r.height
def focus():
    r = subprocess.run(['xdotool', 'search', '--name', 'Blender'], capture_output=True, text=True)
    for w_ in r.stdout.split():
        subprocess.run(['xdotool', 'windowfocus', '--sync', w_], check=False)
def move_border(a, w, dy):
    # the border by Blender's own area move (what the drag does), if the real drag did not move it
    yb = a.y + a.height + 1
    r = next(r for r in a.regions if r.type == 'WINDOW')
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.screen.area_move(x=a.x + a.width // 2, y=yb, delta=dy)
def flow():
    yield 2.0
    focus()
    yield 0.5
    for _ in range(3):
        xdo('mousemove', 1290, 845); yield 0.3
        xdo('key', 'Escape'); yield 0.6
    xdo('mousemove', 1300, 300); yield 0.3
    xdo('click', 1); yield 0.8
    w, a = bottom()
    log('bottom', a.type, a.ui_type, 'y', a.y, 'h', a.height, 'main', main_h(a), 'win h', w.height)
    top = w.height - (a.y + a.height)          # screen y of the border (from the top)
    x = a.x + a.width // 2
    # 1 collapse it to its header with the real mouse
    os.system(f'import -window root "{OUT}/start.png"')
    xdo('mousemove', x, top - 1); yield 0.5
    log('mouse', subprocess.run(['xdotool', 'getmouselocation'], capture_output=True, text=True).stdout.strip())
    xdo('mousedown', 1); yield 0.3
    for yy in range(top, w.height - 2, 8):
        xdo('mousemove', x, yy); yield 0.02
    xdo('mousemove', x, w.height - 2); yield 0.3
    xdo('mouseup', 1); yield 1.0
    w, a = bottom()
    log('after real drag down', a.ui_type, 'h', a.height, 'main', main_h(a))
    if main_h(a) > 2:
        move_border(a, w, -(a.height - 20))
        yield 1.0
        w, a = bottom()
    log('collapsed', a.ui_type, 'h', a.height, 'main', main_h(a))
    os.system(f'import -window root "{OUT}/collapsed.png"')
    # 2 an Asset Browser there, All, while collapsed
    if MODE == 'handled':
        C.preferences.extensions.use_online_access_handled = True
    a.ui_type = 'ASSETS'
    yield 1.0
    sp_ = a.spaces.active
    try:
        sp_.params.asset_library_reference = 'LOCAL' if MODE == 'local' else 'ALL'
    except Exception as ex:
        log('params', repr(ex))
    log('assets', a.ui_type, getattr(sp_.params, 'asset_library_reference', None), 'online', bpy.app.online_access,
        'handled', C.preferences.extensions.use_online_access_handled, 'main', main_h(a))
    yield 6.0                                   # its list loads
    # 3 drag it up (the user: "쉐이더 창 끌어올리면")
    w, a = bottom()
    top = w.height - (a.y + a.height)
    log('drag up from', top, 'main', main_h(a))
    xdo('mousemove', x, top - 1); yield 0.5
    xdo('mousedown', 1); yield 0.3
    for yy in range(top, top - 500, -10):
        xdo('mousemove', x, yy); yield 0.03
    xdo('mouseup', 1); yield 3.0
    w, a = bottom()
    log('after real drag up', a.ui_type, 'h', a.height, 'main', main_h(a))
    if main_h(a) < 50:
        log('area_move up')
        move_border(a, w, 500)
        yield 3.0
        w, a = bottom()
    log('ALIVE after drag up', a.ui_type, 'h', a.height, 'main', main_h(a))
    os.system(f'import -window root "{OUT}/after.png"')
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
        import traceback; traceback.print_exc(); log('ERROR', repr(ex)); bpy.ops.wm.quit_blender()
bpy.app.timers.register(run, first_interval=2.0)
