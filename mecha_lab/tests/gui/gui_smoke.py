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
The checks are deliberately coarse: they catch "nothing drew", "the key did nothing", "the operator raised".

The steps run as one generator driven by an app timer: every ``yield seconds`` hands the window back to Blender's
event loop for that long.  That is what lets a workspace switch take effect (Blender applies it from the event loop),
real X mouse / key events get handled, and the screen redraw between them - a ``time.sleep`` inside the timer only
freezes everything."""
import importlib
import os
import shutil
import subprocess
import sys
import time

import bpy


def mod(name):
    """The add-on's module ``name`` (an installed extension lives under bl_ext.<repo>.mecha_lab)."""
    pkg = next((k for k in sys.modules if k == 'mecha_lab' or k.endswith('.mecha_lab')), None)
    if pkg is None:
        raise ImportError('mecha_lab is not loaded')
    return importlib.import_module(f'{pkg}.{name}')

OUT = os.environ.get('MCH_GUI_OUT', os.path.dirname(os.path.abspath(__file__)))
ZIP = os.environ.get('MCH_GUI_ZIP', '')
RESULTS = []


def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond), str(detail)))
    print(('PASS ' if cond else 'FAIL ') + name + ('  -- ' + str(detail) if detail else ''))


def redraw(n=3):
    """A few real redraws (the drawn bars draw in the POST_PIXEL handler of a real window redraw)."""
    try:
        win = bpy.context.window_manager.windows[0]
        with bpy.context.temp_override(window=win, screen=win.screen, area=win.screen.areas[0]):
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=n)
    except Exception as ex:
        print('redraw failed:', ex)


def shot(name):
    """Blender's own screenshot (the GL framebuffer) and the X screen (ImageMagick import) next to it."""
    path = os.path.join(OUT, name)
    redraw()
    try:
        win = bpy.context.window_manager.windows[0]
        with bpy.context.temp_override(window=win, screen=win.screen, area=win.screen.areas[0]):
            bpy.ops.screen.screenshot(filepath=path)
    except Exception as ex:                      # (a headless build has no screenshot)
        print('screenshot failed:', ex)
    if shutil.which('import'):
        subprocess.run(['import', '-window', 'root', path.replace('.png', '_x.png')], check=False)
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


def focus_window():
    """The Blender window gets the keyboard focus (no window manager on Xvfb: nothing gives it otherwise)."""
    if shutil.which('xdotool') is None:
        return False
    r = subprocess.run(['xdotool', 'search', '--name', 'Blender'], capture_output=True, text=True)
    ids = [x for x in r.stdout.split() if x.strip()]
    for wid in ids:
        subprocess.run(['xdotool', 'windowfocus', '--sync', wid], check=False)
    return bool(ids)


def to_x(win, x, y):
    """Blender window coords (origin bottom-left) -> X screen coords (origin top-left)."""
    return int(x), int(win.height - y)


def step_install():
    ok = False
    try:
        r = bpy.ops.extensions.package_install_files(filepath=ZIP, repo='user_default', enable_on_install=True)
        ok = 'FINISHED' in r
    except Exception as ex:
        check('1. install the add-on zip', False, ex)
        return False
    check('1. install the add-on zip', ok and any(k.endswith('mecha_lab') for k in sys.modules), ZIP)
    return ok


def close_splash():
    """The splash screen takes every click until the mouse leaves it: the mouse goes to a corner, then Escape."""
    focus_window()
    xdo('mousemove', 30, 540)
    yield 0.3
    xdo('key', 'Escape')
    yield 0.5
    redraw()


def step_workspace():
    yield from close_splash()
    ws = next((w for w in bpy.data.workspaces if w.name.startswith('MECHA LAB')), None)
    win = bpy.context.window_manager.windows[0]
    if ws is None:
        try:
            with bpy.context.temp_override(window=win, screen=win.screen, area=win.screen.areas[0]):
                bpy.ops.mch.workspace_open()
        except Exception as ex:
            print('workspace_open:', ex)
        ws = next((w for w in bpy.data.workspaces if w.name.startswith('MECHA LAB')), None)
    check('2. the MECHA LAB workspace exists', ws is not None, [w.name for w in bpy.data.workspaces])
    if ws is not None:
        try:
            win.workspace = ws                      # (applied by the event loop: hence the yield)
        except Exception as ex:
            print('set workspace:', ex)
        yield 1.0
        redraw(5)
        yield 0.5
        check('2. ... and is the window\'s workspace', win.workspace == ws, win.workspace.name)
    STATE['ws'] = ws is not None


def step_bars():
    try:
        ui_bars = mod('ui_bars')
        handlers = getattr(ui_bars, '_handle', None)
        check('3. the drawn bars are registered', bool(handlers), handlers)
    except Exception as ex:
        check('3. the drawn bars are registered', False, ex)
    path = shot('01_workspace.png')
    xpath = path.replace('.png', '_x.png')          # the X screen capture (Blender's own is black on software GL)
    try:
        img = bpy.data.images.load(xpath if os.path.isfile(xpath) else path)
        img.colorspace_settings.name = 'Non-Color'      # (as sRGB the dark greys all read 0.0 in linear)
        w, h = img.size
        px = list(img.pixels)
        win, area, region = view3d()
        # the Mecha top bar sits just under the 3D view's header: a band across the viewport's top, 40 - 80 px down
        band = [px[(y * w + x) * 4:(y * w + x) * 4 + 3] for y in range(region.y + region.height - 80,
                                                                          region.y + region.height - 40, 10)
                for x in range(region.x + 10, region.x + region.width - 10, 25)]
        colours = {tuple(round(c * 20) for c in p) for p in band}
        black = sum(1 for p in band if max(p) < 0.02)
        blue = sum(1 for p in band if p[2] > 0.5 and p[2] > p[0] + 0.2)      # the blue accent (SHAPE / MECHA LAB)
        check('3. the window drew (X capture not black) and the band under the 3D view header is drawn on '
              '(several greys + the blue accent: the Mecha top bar)', black < len(band) // 2 and len(colours) >= 6
              and blue > 0, (w, h, black, len(colours), blue))
    except Exception as ex:
        check('3. screenshot readable', False, ex)


def step_cut():
    for o in [o for o in bpy.data.objects if o.name == 'Cube']:    # the start-up file's own cube sits exactly where
        bpy.data.objects.remove(o)                                  # ours goes: two targets, so no live last cut
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    cube = bpy.context.active_object
    n0 = len(cube.data.polygons)

    def extent(ob):                               # (a box lasso cuts the cube down to a smaller box: still 6 faces
        dg = bpy.context.evaluated_depsgraph_get()   # and 8 points, so the points themselves are compared)
        return sorted(tuple(round(c, 3) for c in v.co) for v in ob.evaluated_get(dg).data.vertices)
    e0 = extent(cube)
    win, area, region = view3d()
    if area is None:
        check('4. a 3D view', False)
        return
    try:
        with bpy.context.temp_override(window=win, area=area, region=region):
            mod('workspace_ui').activate_mecha_tool(bpy.context, 'CUT')
    except Exception as ex:
        print('activate_tool:', ex)
    yield 0.5
    redraw()
    try:
        tool = bpy.context.workspace.tools.from_space_view3d_mode('OBJECT', create=False)
        print('active tool:', tool.idname if tool else None, '| workspace:', bpy.context.window.workspace.name)
    except Exception as ex:
        print('tool lookup:', ex)
    # a lasso over the right half of the viewport, as real mouse clicks (the cube sits in the middle): the Cut tool's
    # click flow - a click per corner, a click on the first corner closes and applies
    x0, y0 = region.x + region.width // 2, region.y + region.height // 2
    # (the WINDOW region runs under the overlapping sidebar: the corners stay within 250 px of the middle)
    pts = [(x0 + 10, y0 + 200), (x0 + 250, y0 + 200), (x0 + 250, y0 - 200), (x0 + 10, y0 - 200)]
    if focus_window() and xdo('mousemove', *to_x(win, x0, y0)):
        yield 0.5
        for x, y in pts + [pts[0]]:
            xdo('mousemove', *to_x(win, x, y))
            yield 0.3
            xdo('click', 1)
            yield 0.4
        xdo('mousemove', *to_x(win, x0, y0))      # (the tool finishes the cut on the next event / redraw)
        yield 0.5
        redraw()
        yield 2.0
        redraw()
        check('4. a real-mouse lasso with the Cut tool cuts the cube (its points move or its faces change)',
              extent(cube) != e0 or len(cube.data.polygons) != n0,
              (n0, len(cube.data.polygons), e0[:2], extent(cube)[:2], [m.name for m in cube.modifiers]))
        # 0.24.83 Ctrl+Z after the cut in the real window (the headless fuzz dies on undo: a bpy-without-a-window
        # artefact - here it must put the cube back), then Ctrl+Shift+Z
        xdo('key', 'ctrl+z')
        yield 1.5
        redraw()
        cube = bpy.data.objects.get('Cube.001') or bpy.data.objects.get('Cube')
        back = cube is not None and extent(cube) == e0
        xdo('key', 'ctrl+shift+z')
        yield 1.5
        redraw()
        cube = bpy.data.objects.get('Cube.001') or bpy.data.objects.get('Cube')
        check('4. Ctrl+Z puts the cube back after the cut, Ctrl+Shift+Z cuts it again (no crash)',
              back and cube is not None and extent(cube) != e0, (back, cube and extent(cube)[:2]))
        # Box Hide + Ctrl+Z (the headless fuzz segfaults on exactly this: the real window must not)
        try:
            with bpy.context.temp_override(window=win, area=area, region=region):
                mod('workspace_ui').activate_mecha_tool(bpy.context, 'HIDE')
        except Exception as ex:
            print('activate HIDE:', ex)
        yield 0.5
        n_mods = len(cube.modifiers) if cube else -1
        for x, y in pts + [pts[0]]:
            xdo('mousemove', *to_x(win, x, y))
            yield 0.3
            xdo('click', 1)
            yield 0.4
        xdo('mousemove', *to_x(win, x0, y0))
        yield 2.0
        redraw()
        cube = bpy.data.objects.get('Cube.001') or bpy.data.objects.get('Cube')
        hid = cube is not None and any(m.name == 'MCH_BoxHide' for m in cube.modifiers)
        xdo('key', 'ctrl+z')
        yield 2.0
        redraw()
        cube = bpy.data.objects.get('Cube.001') or bpy.data.objects.get('Cube')
        check('4. Box Hide by real mouse, then Ctrl+Z: the hiding gone, Blender alive',
              hid and cube is not None and not any(m.name == 'MCH_BoxHide' for m in cube.modifiers),
              (hid, cube and [m.name for m in cube.modifiers]))
        # 0.24.83 a Cut setting changed after a cut: the live last cut is cut again from a timer (never inside the
        # property update - that took Blender down in the fuzz); the real window must stay up and the cut must change
        try:
            with bpy.context.temp_override(window=win, area=area, region=region):
                mod('workspace_ui').activate_mecha_tool(bpy.context, 'CUT')
        except Exception as ex:
            print('activate CUT again:', ex)
        yield 0.5
        pts2 = [(x0 - 150, y0 + 60), (x0 + 5, y0 + 60), (x0 + 5, y0 + 250), (x0 - 150, y0 + 250)]   # (a notch out
        for x, y in pts2 + [pts2[0]]:                       # of the top of what is left; x0 - 250 hit the tool strip)
            xdo('mousemove', *to_x(win, x, y))
            yield 0.3
            xdo('click', 1)
            yield 0.4
        xdo('mousemove', *to_x(win, x0, y0))
        yield 2.0
        redraw()
        cube = bpy.data.objects.get('Cube.001') or bpy.data.objects.get('Cube')
        n_cut = len(cube.data.polygons) if cube else -1
        re_ = mod('ramp_edit')
        print('second cut:', cube and cube.name, n_cut, 'extent', cube and extent(cube)[:2], 'live record:',
              cube and re_.record(cube) is not None, 'live target:', re_.live_target(bpy.context, re_.ALL_KINDS))
        print('   props', cube and list(cube.keys()), 'pref live_last_cut', mod('workspace_ui').pref('live_last_cut', True),
              'backups', [m.name for m in bpy.data.meshes if 'RampBackup' in m.name], 'mch objects',
              [o.name for o in bpy.data.objects])
        scene = bpy.context.scene
        _orig_recarve = re_.recarve

        def _logged_recarve(context, ob):           # (what the timer's re-cut says or raises)
            try:
                out = _orig_recarve(context, ob)
                print('recarve ->', str(out)[:160])
                return out
            except Exception as ex:
                print('recarve raised:', type(ex).__name__, str(ex)[:160])
                raise
        re_.recarve = _logged_recarve
        print('before GN: edited', re_.edited(cube), 'depth mode', scene.mch_cut.depth_mode, scene.mch_cut.depth)
        scene.mch_cut.gn_finish, scene.mch_cut.gn_width = 'CHAMFER', 0.15   # (the update queues the re-cut)
        print('after setting GN: pending', list(re_._PENDING), 'timer registered', bpy.app.timers.is_registered(re_.flush))
        yield 2.5
        redraw()
        cube = bpy.data.objects.get('Cube.001') or bpy.data.objects.get('Cube')
        n_gn = len(cube.data.polygons) if cube else -1
        print('after 2.5 s: pending', list(re_._PENDING), 'faces', n_gn, 'extent', cube and extent(cube)[:2])
        scene.mch_cut.gn_finish = 'NONE'
        yield 2.5
        redraw()
        cube = bpy.data.objects.get('Cube.001') or bpy.data.objects.get('Cube')
        n_back = len(cube.data.polygons) if cube else -1
        # (the mouse cut and the timer's re-cut of the same outline do not land on the same face count - 25 and
        # 13 here - so the two re-cuts are compared with each other: chamfered vs plain)
        check('4. GN Edge switched on after a live cut: the cut is made again from a timer (chamfer: more faces than '
              'the plain re-cut), off again: the plain cut again - Blender alive',
              n_cut > 0 and n_gn > 0 and n_back > 0 and n_gn > n_back, (n_cut, n_gn, n_back))
    else:
        check('4. xdotool for real mouse events', False, 'not installed - the cut step was skipped')
    shot('02_after_cut.png')


def step_zbrush():
    win, area, region = view3d()
    before = bpy.context.window.workspace.name
    focus_window()
    xdo('mousemove', *to_x(win, region.x + region.width // 2, region.y + region.height // 2))
    yield 0.3
    if xdo('key', 'Tab'):
        yield 2.0
        redraw()
        after = bpy.context.window.workspace.name
        check('5. Tab switches MECHA LAB <-> the ZBrush screen', after != before or bpy.context.mode == 'SCULPT',
              (before, after, bpy.context.mode))
        shot('03_zbrush.png')
        xdo('key', 'Tab')
        yield 1.5


def step_hotkeys():
    """0.24.82 the hotkey conflict list needs Blender's real keyconfig (empty headless): Shift+D must be found
    sitting on object.duplicate_move in Object Mode."""
    try:
        kc = mod('keymap_check')
        found = kc.lines('user')
        check('7. hotkey conflicts listed against the real keyconfig (Shift+D on object.duplicate_move among them)',
              any('mch.duplicate' in l and 'object.duplicate_move' in l for l in found), (len(found), found[:3]))
        with open(os.path.join(OUT, 'hotkey_conflicts.txt'), 'w') as f:
            f.write('\n'.join(found) + '\n')
    except Exception as ex:
        check('7. hotkey conflicts', False, ex)


def step_timers():
    try:
        lasso_memory, armor_shell = mod('lasso_memory'), mod('armor_shell')
        check('6. the lasso memory timer ticks', bpy.app.timers.is_registered(lasso_memory._tick))
        check('6. the armor shell timer ticks', bpy.app.timers.is_registered(armor_shell._tick))
    except Exception as ex:
        check('6. timers', False, ex)


STATE = {}


def steps():
    os.makedirs(OUT, exist_ok=True)
    if step_install():
        yield from step_workspace()
        if STATE.get('ws'):
            step_bars()
            yield from step_cut()
            yield from step_zbrush()
            step_hotkeys()
            step_timers()
    passed = sum(1 for _n, ok, _d in RESULTS if ok)
    with open(os.path.join(OUT, 'gui_result.txt'), 'w') as f:
        for n, ok, d in RESULTS:
            f.write(('PASS ' if ok else 'FAIL ') + n + ('  -- ' + d if d else '') + '\n')
        f.write(f'{passed}/{len(RESULTS)} passed\n')
    print(f'{passed}/{len(RESULTS)} passed')
    bpy.app.timers.register(lambda: bpy.ops.wm.quit_blender() and None, first_interval=1.0)


GEN = steps()


def main():
    """One step per timer tick; the value a step yields is the pause (seconds of event loop) before the next."""
    try:
        return next(GEN)
    except StopIteration:
        return None
    except Exception as ex:
        import traceback
        traceback.print_exc()
        check('the smoke test itself raised', False, ex)
        passed = sum(1 for _n, ok, _d in RESULTS if ok)
        with open(os.path.join(OUT, 'gui_result.txt'), 'w') as f:
            for n, ok, d in RESULTS:
                f.write(('PASS ' if ok else 'FAIL ') + n + ('  -- ' + d if d else '') + '\n')
            f.write(f'{passed}/{len(RESULTS)} passed\n')
        bpy.app.timers.register(lambda: bpy.ops.wm.quit_blender() and None, first_interval=1.0)
        return None


bpy.app.timers.register(main, first_interval=6.0)
