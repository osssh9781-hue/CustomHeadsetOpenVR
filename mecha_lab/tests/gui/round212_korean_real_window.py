"""Real window 0.24.212: the Mecha Lab screen in Korean - the side panel, the top bar and the tool menu are drawn with
the Korean table (screenshots), a REAL click on a cell still lands (the items keep their English names, only what
is drawn changes), and Preferences > Korean off brings English back at once."""
import os
import subprocess
import sys
import time

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'addon'))
import mecha_lab  # noqa: E402
from mecha_lab import side_panel as sp, ui_bars  # noqa: E402
from mecha_lab.ui_gpu import ui_factor  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402
import math  # noqa: E402
import numpy as np  # noqa: E402

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


def screen_xy(p):
    from bpy_extras import view3d_utils
    w, a, r = view3d()
    c = view3d_utils.location_3d_to_region_2d(r, a.spaces.active.region_3d, Vector(p))
    return int(r.x + c.x), int(w.height - (r.y + c.y))


def drag(points, mods=()):
    """A real drag through the 3D points (screen positions now)."""
    xy = [screen_xy(p) for p in points]
    xdo('mousemove', *xy[0])
    yield 0.4
    for m in mods:
        xdo('keydown', m)
    yield 0.2
    xdo('mousedown', 1)
    yield 0.4
    for x, y in xy[1:]:
        xdo('mousemove', x, y)
        yield 0.08
    yield 0.3
    xdo('mouseup', 1)
    yield 0.3
    for m in mods:
        xdo('keyup', m)
    yield 1.5


def flow():
    import json
    from mecha_lab import i18n, workspace_ui as wu, cloth_drape as cd, mecha_mask as mm, top_bar, ui_bars
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
    res = {}
    p = wu.prefs()                                # (None here: the add-on is loaded from its folder, no Preferences)

    def set_lang(ko):
        if p is not None:
            p.korean = ko
        else:
            i18n.force('KO' if ko else 'EN')
            sp.dirty()
    set_lang(True)
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=64, radius=1.0)
        body = C.active_object
        sp3.show_region_ui = False
        ui_bars.set_menu_folded(False)
        bpy.ops.mch.bar_tool(tool='CDRAPE')
        bpy.ops.mch.side_page(page='TOOL')
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 3.0
    yield from wait_draws(3)
    shot('01_korean_cloth_drape.png')
    with C.temp_override(window=w, area=a, region=r):
        its = sp.items(C, r.width, r.height, ui_factor(C, r))
    labels = [i.label for i in its if getattr(i, 'label', '')]
    shown = [i18n.tr(s) for s in labels]
    ko = sum(1 for s in shown if any(ord(ch) >= 0xac00 for ch in s))
    res['A1'] = i18n.lang() == 'KO' and ko > len(labels) * 0.7
    log('A1 korean on', i18n.lang(), 'side panel cells', len(labels), 'drawn in Korean', ko, '| e.g.',
        [(a_, b_) for a_, b_ in zip(labels, shown) if a_ != b_][:6])
    # a REAL click on a cell (drawn "마스크 ..." now) still lands
    it = yield from scrolled_item('Paint Mask')
    if it is not None:
        yield from press(it)
    yield 1.5
    res['A2'] = it is not None and mm.on(C)
    log('A2 REAL click on the Paint Mask cell (Korean on screen): mask session on', mm.on(C))
    shot('02_korean_mask_session.png')
    with C.temp_override(window=w, area=a, region=r):
        if mm.on(C):
            mm.end(C)
        bpy.ops.mch.bar_tool(tool='CUT')
    yield 2.0
    yield from wait_draws(3)
    shot('03_korean_cut_tool.png')
    # Base Mesh: the bevel sides are buttons in the top bar; a REAL click on Both, then the two widths are there
    from mecha_lab import base_mesh

    def bar_item(pred):
        w_, a_, r_ = view3d()
        with C.temp_override(window=w_, area=a_, region=r_):
            its_ = top_bar.items(C, r_.width, r_.height, ui_factor(C, r_))
        return next((i for i in its_ if pred(i)), None), [i.label for i in its_ if i.label]
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool='BASE')
        d = base_mesh.scene_defaults(C)
        d.profile, d.bevel_sides, d.bevel_link = 'BEVEL', 'TOP', False
    yield 2.0
    yield from wait_draws(3)
    it, labs = bar_item(lambda i: i.kind == 'seg' and i.prop == 'bevel_sides' and i.label == 'Both')
    if it is not None:
        yield from press(it)
    yield 1.0
    yield from wait_draws(3)
    it2, labs2 = bar_item(lambda i: i.kind == 'mini' and i.prop == 'bevel_width_bottom')
    res['B1'] = it is not None and d.bevel_sides == 'BOTH' and it2 is not None
    log('B1 Base Mesh top bar: REAL click on Both ->', d.bevel_sides, '| bottom width cell there', it2 is not None, labs2)
    shot('05_korean_base_mesh_bar.png')
    # the bottom width dragged 40 px with the REAL mouse: a small, fine change
    v0 = d.bevel_width_bottom
    if it2 is not None:
        x, y = int(r.x + it2.x + it2.w / 2), int(w.height - (r.y + it2.y + it2.h / 2))
        xdo('mousemove', x, y)
        yield 0.5
        xdo('mousedown', 1)
        yield 0.3
        for k_ in range(1, 9):
            xdo('mousemove', x + 5 * k_, y)
            yield 0.1
        xdo('mouseup', 1)
        yield 0.8
    dv = d.bevel_width_bottom - v0
    res['B2'] = 0.0 < dv < 0.2
    log('B2 the Bottom width dragged 40 px (REAL): %.4f -> %.4f (it was the whole 0..2 range over the cell: +0.6)' % (v0, d.bevel_width_bottom))
    # a closed list (Split: GN Edge sides) opened by a REAL click stays while the mouse moves
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool='SPLIT')
        S.mch_cut.gn_finish = 'CHAMFER'
    yield 2.0
    yield from wait_draws(3)
    it3, _l = bar_item(lambda i: i.kind == 'drop' and i.prop == 'gn_sides')
    before = S.mch_cut.gn_sides
    if it3 is not None:
        yield from press(it3)
        shot('06a_right_after_click.png')
        x, y = int(r.x + it3.x + it3.w / 2), int(w.height - (r.y + it3.y + it3.h / 2))
        xdo('mousemove', x + 6, y + 30)
        yield 0.8
        shot('06_list_stays_open.png')
        xdo('mousemove', x + 6, y + 52)             # (the second row of the list)
        yield 0.6
        xdo('click', 1)
        yield 1.0
    res['B3'] = it3 is not None and S.mch_cut.gn_sides != before
    log('B3 a closed list: REAL click opens it, the mouse moves, a second REAL click picks:', before, '->', S.mch_cut.gn_sides)
    xdo('key', 'Escape')
    yield 0.5
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool='CUT')
    yield 1.5
    yield from wait_draws(3)
    set_lang(False)
    yield 1.0
    yield from wait_draws(3)
    shot('04_english_cut_tool.png')
    res['A3'] = i18n.lang() == 'EN' and i18n.tr('Thickness') == 'Thickness'
    log('A3 Preferences > Korean off: English again', i18n.lang(), i18n.tr('Thickness'))
    set_lang(True)
    yield 0.5
    res['A4'] = i18n.lang() == 'KO' and i18n.tr('Thickness') != 'Thickness'
    log('A4 ... and on again', i18n.lang(), i18n.tr('Thickness'))
    json.dump(sorted(i18n.MISSES), open(os.path.join(OUT, 'misses.json'), 'w'), ensure_ascii=False, indent=0)
    log('not in the table (drawn in English):', len(i18n.MISSES))
    names = {'A1': 'Korean on: the side panel\'s cells are drawn from the Korean table',
             'A2': 'a REAL click on a cell drawn in Korean lands (Paint Mask starts)',
             'A3': 'Korean off: English at once', 'A4': 'on again: Korean',
             'B1': 'Base Mesh: the bevel sides are buttons - REAL click on Both, the bottom has its own width cell',
             'B2': 'the width cell drags finely (REAL drag)',
             'B3': 'a closed list opened by a REAL click stays open until a choice is clicked'}
    n = 0
    for k in sorted(names):
        ok = bool(res.get(k))
        n += ok
        log('PASS' if ok else 'FAIL', k, names[k])
    log(f'{n}/{len(names)} passed')
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
