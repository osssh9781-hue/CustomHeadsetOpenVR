"""Real window 0.24.233: the usage card (bottom left) - REAL click on its title opens it (Korean, then English),
for a drawing tool (Cut) and a click tool (SubD Plane); REAL click on its Search: the usage search; REAL typing of a
Korean-free word ("crease") and Enter switches to SubD Plane with its card open; Ctrl+Shift+F opens the search."""
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
    from mecha_lab import key_legend as kl, i18n, ui_bars as ub, tool_state as ts2
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
    res = {}
    i18n.force('KO')
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=32, radius=1.0)
        a.spaces.active.show_region_ui = False
        bpy.ops.mch.bar_tool(tool='CUT')
    C.window_manager.mch_legend_min = True
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 1.5
    yield from wait_draws(3)

    def card():
        with C.temp_override(window=w, area=a, region=r):
            return kl.box(C)

    def sbox():
        with C.temp_override(window=w, area=a, region=r):
            return kl.search_box(C)

    def click_at(x, y):
        xdo('mousemove', int(r.x + x), int(w.height - (r.y + y)))
        yield 0.5
        xdo('click', 1)
        yield 1.2
    b = card()
    yield from click_at(b[0] + 30, b[1] + b[3] - 20)          # the title line
    yield from wait_draws(3)
    b2 = card()
    res['E1'] = b is not None and b2 is not None and not C.window_manager.mch_legend_min and b2[3] > b[3] * 5
    log('E1 REAL click on the Cut card title: open', not C.window_manager.mch_legend_min, '| height', round(b[3]), '->', round(b2[3]))
    shot('01_cut_card_ko.png')
    i18n.force('EN')
    ub.bump()
    yield 1.0
    yield from wait_draws(3)
    shot('02_cut_card_en.png')
    i18n.force('KO')
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool='SUBD')
        bpy.ops.mch.subd_plane_create()
    yield 1.5
    yield from wait_draws(3)
    b3 = card()
    res['E2'] = b3 is not None and ts2.effective_tool(C) == 'SUBD'
    log('E2 SubD Plane (a click tool): the card shows', b3 is not None)
    shot('03_subd_card_ko.png')
    # a REAL click on the card must not edit the plate
    me = C.active_object.data
    co0 = [tuple(v.co) for v in me.vertices]
    yield from click_at(b3[0] + b3[2] / 2, b3[1] + b3[3] / 2)
    res['E3'] = [tuple(v.co) for v in C.active_object.data.vertices] == co0 and len(C.active_object.data.vertices) == 4
    log('E3 REAL click on the card body: the plate unchanged', res['E3'])
    # Search: back on Cut, a REAL click on the card's Search pill, type, Enter
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool='CUT')
    C.window_manager.mch_legend_min = True
    yield 1.5
    yield from wait_draws(3)
    sb = sbox()
    yield from click_at(sb[0] + sb[2] / 2, sb[1] + sb[3] / 2)
    yield 1.0
    shot('04_search_popup.png')
    xdo('type', '--delay', '90', 'subd crease')      # (0.24.235: "crease" alone also finds Wrinkle Lines now)
    yield 1.5
    shot('05_search_typed.png')
    xdo('key', 'Return')
    yield 2.0
    yield from wait_draws(3)
    res['E4'] = ts2.effective_tool(C) == 'SUBD' and not C.window_manager.mch_legend_min
    log('E4 REAL Search click + "subd crease" + Enter: tool', ts2.effective_tool(C), '| card open', not C.window_manager.mch_legend_min)
    shot('06_after_search.png')
    # Ctrl+Shift+F
    C.window_manager.mch_legend_min = True
    xdo('mousemove', int(r.x + r.width * 0.5), int(w.height - (r.y + r.height * 0.55)))
    yield 0.5
    xdo('key', 'ctrl+shift+f')
    yield 1.2
    xdo('type', '--delay', '90', 'stamp')
    yield 1.2
    shot('07_ctrl_shift_f.png')
    xdo('key', 'Return')
    yield 2.0
    res['E5'] = ts2.effective_tool(C) == 'PRESS'
    log('E5 REAL Ctrl+Shift+F + "stamp" + Enter: tool', ts2.effective_tool(C))
    # 0.24.235 closed (folded): just the title line; the "?" of a page section; more tools' cards
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool='CUT')
    C.window_manager.mch_legend_min = True
    yield 1.5
    yield from wait_draws(3)
    bf = card()
    shot('08_folded.png')
    from mecha_lab import side_panel as sp2, key_legend as kl2
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.side_page(page='SHAPES')
    ub.bump()
    yield 1.5
    yield from wait_draws(3)
    with C.temp_override(window=w, area=a, region=r):
        q = next((i for i in sp2.items(C, r.width, r.height, ui_factor(C, r)) if i.kind == 'pbtn' and i.label == '?'
                  and 'TIRE' in i.action[1]), None)
    if q is None:                                   # (scroll down to it)
        for _i in range(30):
            with C.temp_override(window=w, area=a, region=r):
                sp2.scroll_by(C, r.width, r.height, ui_factor(C, r), 150)
            yield from wait_draws(1)
            with C.temp_override(window=w, area=a, region=r):
                q = next((i for i in sp2.items(C, r.width, r.height, ui_factor(C, r)) if i.kind == 'pbtn' and i.label == '?'
                          and 'TIRE' in i.action[1]), None)
            if q is not None:
                yield from wait_draws(2)
                with C.temp_override(window=w, area=a, region=r):
                    q = next((i for i in sp2.items(C, r.width, r.height, ui_factor(C, r)) if i.kind == 'pbtn'
                              and i.label == '?' and 'TIRE' in i.action[1]), None)
                break
    if q is not None:
        yield from press(q)
    yield from wait_draws(3)
    bt = card()
    res['E6'] = bf is not None and bf[3] < 80 and q is not None and kl2.FEATURE[0] == 'SHAPES:TIRE & WHEEL' and bt is not None \
        and bt[3] > 200
    log('E6 folded card height', round(bf[3]) if bf else None, '| REAL click on the Tire & Wheel "?":', kl2.FEATURE[0],
        '| card height', round(bt[3]) if bt else None)
    shot('09_tire_help.png')
    b9 = card()
    yield from click_at(b9[0] + 30, b9[1] + b9[3] - 20)          # its title: closed
    yield from wait_draws(2)
    res['E7'] = kl2.FEATURE[0] is None
    log('E7 REAL click on its title: closed', kl2.FEATURE[0] is None)
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.side_page(page='TOOL')
    for n_, t_ in enumerate(('FUR', 'GREEBLE', 'MIRROR')):
        with C.temp_override(window=w, area=a, region=r):
            bpy.ops.mch.bar_tool(tool=t_)
        C.window_manager.mch_legend_min = False
        yield 1.5
        yield from wait_draws(3)
        shot(f'1{n_}_{t_}_card.png')
    i18n.force(None)
    names = {'E6': 'closed: the title only; a REAL click on a page section\'s "?" (Tire & Wheel) shows its card',
             'E7': 'a REAL click on that card\'s title closes it',
             'E1': 'a REAL click on the card title opens the usage (Cut)',
             'E2': 'a click tool (SubD Plane) has the card too',
             'E3': 'a REAL click on the card is the card\'s, never an edit',
             'E4': 'the card\'s Search: REAL typing + Enter switches to that tool, its card open',
             'E5': 'Ctrl+Shift+F opens the search'}
    n = 0
    for kk_ in sorted(names):
        ok = bool(res.get(kk_))
        n += ok
        log('PASS' if ok else 'FAIL', kk_, names[kk_])
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
