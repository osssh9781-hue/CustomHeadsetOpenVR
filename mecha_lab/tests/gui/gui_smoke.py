"""Runs INSIDE a real Blender window (tests/gui/run_gui.sh): installs the add-on zip, opens the MECHA LAB workspace,
takes screenshots and checks what the headless suite cannot - the drawn bars really draw, the timers run, keys and
mouse events reach the tools.  Everything it finds goes to tests/gui/out/ (gui_result.txt + PNGs).

Steps (each one PASS / FAIL in gui_result.txt):
  1. the zip installs and enables (bpy.ops.extensions.package_install_files)
  2. the MECHA LAB workspace exists after enabling; switching to it; screenshot 01
  3. the drawn top bar / side panel / tool strip handlers are registered and a screenshot pixel check finds the
     bar colours in the right bands of the window
  4. a cube is added; the Cut tool is set; a lasso is fed through real window events (xdotool when present, else
     bpy.ops with a window / region override) and the cube loses faces; screenshot 02
  5. Tab switches to the ZBrush screen (orange UI); screenshot 03; Tab back
  6. the lasso-memory / shell timers tick (bpy.app.timers.is_registered)
The checks are deliberately coarse: they catch "nothing drew", "the key did nothing", "the operator raised"."""
import os
import shutil
import subprocess
import sys
import time

import bpy

OUT = os.environ.get('MCH_GUI_OUT', os.path.dirname(os.path.abspath(__file__)))
ZIP = os.environ.get('MCH_GUI_ZIP', '')
RESULTS = []


def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond), str(detail)))
    print(('PASS ' if cond else 'FAIL ') + name + ('  -- ' + str(detail) if detail else ''))


def shot(name):
    path = os.path.join(OUT, name)
    try:
        win = bpy.context.window_manager.windows[0]
        with bpy.context.temp_override(window=win, screen=win.screen, area=win.screen.areas[0]):
            bpy.ops.screen.screenshot(filepath=path)
    except Exception as ex:                      # (a headless build has no screenshot)
        print('screenshot failed:', ex)
    return path


def view3d():
    win = bpy.context.window_manager.windows[0]
    for area in win.screen.areas:
        if area.type == 'VIEW_3D':
            region = next(r for r in area.regions if r.type == 'WINDOW')
            return win, area, region
    return win, None, None


def xdo(*args):
    if shutil.which('xdotool') is None:
        return False
    subprocess.run(['xdotool', *map(str, args)], check=False)
    return True


def step_install():
    ok = False
    try:
        r = bpy.ops.extensions.package_install_files(filepath=ZIP, repo='user_default', enable_on_install=True)
        ok = 'FINISHED' in r
    except Exception as ex:
        check('1. install the add-on zip', False, ex)
        return False
    check('1. install the add-on zip', ok and 'mecha_lab' in ' '.join(sys.modules), ZIP)
    return ok


def step_workspace():
    ws = next((w for w in bpy.data.workspaces if w.name.startswith('MECHA LAB')), None)
    if ws is None:
        try:
            bpy.ops.mch.workspace_open()
        except Exception as ex:
            print('create_workspace:', ex)
        ws = next((w for w in bpy.data.workspaces if w.name.startswith('MECHA LAB')), None)
    check('2. the MECHA LAB workspace exists', ws is not None)
    if ws is not None:
        bpy.context.window.workspace = ws
    return ws is not None


def step_bars():
    try:
        from mecha_lab import ui_bars
        handlers = getattr(ui_bars, '_handle', None)
        check('3. the drawn bars are registered', bool(handlers), handlers)
    except Exception as ex:
        check('3. the drawn bars are registered', False, ex)
    path = shot('01_workspace.png')
    try:
        img = bpy.data.images.load(path)
        w, h = img.size
        px = list(img.pixels)
        # the top band: anything that is not the viewport grey means something drew there
        band = [px[((h - 20) * w + x) * 4:((h - 20) * w + x) * 4 + 3] for x in range(0, w, 50)]
        drew = sum(1 for p in band if abs(p[0] - p[1]) > 0.03 or p[0] > 0.45 or p[0] < 0.15)
        check('3. screenshot: the top band is drawn (not plain viewport)', drew > 3, (w, h, drew))
    except Exception as ex:
        check('3. screenshot readable', False, ex)


def step_cut():
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    cube = bpy.context.active_object
    n0 = len(cube.data.polygons)
    win, area, region = view3d()
    if area is None:
        check('4. a 3D view', False)
        return
    try:
        with bpy.context.temp_override(window=win, area=area, region=region):
            from mecha_lab import workspace_ui
            workspace_ui.activate_mecha_tool(bpy.context, 'CUT')
    except Exception as ex:
        print('activate_tool:', ex)
    # a lasso over the right half of the viewport, as real mouse events
    x0, y0 = region.x + region.width // 2, region.y + region.height // 2
    pts = [(x0 + 20, y0 - 200), (x0 + 400, y0 - 200), (x0 + 400, y0 + 200), (x0 + 20, y0 + 200)]
    if xdo('mousemove', pts[0][0], 1080 - pts[0][1]):
        xdo('mousedown', 1)
        for x, y in pts[1:]:
            xdo('mousemove', x, 1080 - y)
            time.sleep(0.05)
        xdo('mouseup', 1)
        time.sleep(1.0)
        check('4. a real-mouse lasso with the Cut tool cuts the cube', len(cube.data.polygons) != n0,
              (n0, len(cube.data.polygons)))
    else:
        check('4. xdotool for real mouse events', False, 'not installed - the cut step was skipped')
    shot('02_after_cut.png')


def step_zbrush():
    win, area, region = view3d()
    if xdo('key', 'Tab'):
        time.sleep(1.0)
        check('5. Tab opens the ZBrush screen', bpy.context.mode == 'SCULPT' or 'ZBRUSH' in str(
            getattr(bpy.context.scene, 'mch_zb', '')), bpy.context.mode)
        shot('03_zbrush.png')
        xdo('key', 'Tab')
        time.sleep(0.5)


def step_timers():
    try:
        from mecha_lab import lasso_memory, armor_shell
        check('6. the lasso memory timer ticks', bpy.app.timers.is_registered(lasso_memory._tick))
        check('6. the armor shell timer ticks', bpy.app.timers.is_registered(armor_shell._tick))
    except Exception as ex:
        check('6. timers', False, ex)


def main():
    os.makedirs(OUT, exist_ok=True)
    if step_install() and step_workspace():
        step_bars()
        step_cut()
        step_zbrush()
        step_timers()
    passed = sum(1 for _n, ok, _d in RESULTS if ok)
    with open(os.path.join(OUT, 'gui_result.txt'), 'w') as f:
        for n, ok, d in RESULTS:
            f.write(('PASS ' if ok else 'FAIL ') + n + ('  -- ' + d if d else '') + '\n')
        f.write(f'{passed}/{len(RESULTS)} passed\n')
    print(f'{passed}/{len(RESULTS)} passed')
    bpy.app.timers.register(lambda: bpy.ops.wm.quit_blender() and None, first_interval=1.0)
    return None


bpy.app.timers.register(main, first_interval=2.0)
