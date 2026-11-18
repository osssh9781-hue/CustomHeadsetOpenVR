"""Real window 0.24.226 (4K): the LASSO bar alone at the top, in every tool (dim where the tool has no such cell);
at the bottom the bar with Select (with Options: Ortho, 한글) ABOVE a row of boxes - the tool's own box at the left, then
the right-click popup's actions in three boxes; REAL clicks: an action button, the 한글 switch, a right click opens the
Tool Wheel; the menu's open button sits beside the key legend."""
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
    from mecha_lab import i18n, top_bar, bottom_row, radial_menu, key_legend, ui_bars as ub
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
        ub.set_menu_folded(True)
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    k = ui_factor(C, r)
    log('region', r.width, r.height, 'k', round(k, 3))

    def every():
        with C.temp_override(window=w, area=a, region=r):
            ub.bump()
            return list(ub.all_items(C))

    def top():
        with C.temp_override(window=w, area=a, region=r):
            return top_bar.items(C, r.width, r.height, k)

    def row():
        with C.temp_override(window=w, area=a, region=r):
            ub.bump()
            return bottom_row.items(C, r.width, r.height, k)

    def dock():
        with C.temp_override(window=w, area=a, region=r):
            return ub.dock_items(C, r.width, r.height, k)

    def tool(t):
        with C.temp_override(window=w, area=a, region=r):
            bpy.ops.mch.bar_tool(tool=t)
    pos = {}
    for n, t in enumerate(('CUT', 'BASE', 'SMART', 'CDRAPE')):
        tool(t)
        yield 1.5
        yield from wait_draws(3)
        shot(f'0{n + 1}_{t}.png')
        its = top()
        pos[t] = {(i.kind, i.label): (round(i.x, 1), round(i.y, 1), i.enabled) for i in its
                  if i.kind in {'ibtn', 'seg', 'mini'} and i.label in {'Lasso', 'Sketch', 'Sharp', 'Res', 'Selected'}}
    same = all({kk_: v[:2] for kk_, v in pos[t].items()} == {kk_: v[:2] for kk_, v in pos['CUT'].items()} for t in pos)
    res['C1'] = same and len(pos['CUT']) == 5 and all(v[2] for v in pos['CUT'].values()) \
        and not any(v[2] for kk_, v in pos['SMART'].items() if kk_[1] != 'Selected' or True) is False or same
    dim_smart = [kk_[1] for kk_, v in pos['SMART'].items() if not v[2]]
    res['C1'] = same and len(pos['CUT']) == 5 and all(v[2] for v in pos['CUT'].values()) and len(dim_smart) >= 4
    log('C1 the LASSO bar in 4 tools: same places', same, '| Cut cells', len(pos['CUT']), '| dim in Smart Move', dim_smart)
    tool('CUT')
    S.mch_brush.stab_enable = True              # (0.24.227 the user's screenshot: Slow Line on, the Stroke shape)
    S.mch_brush.shape = 'STROKE'
    ub.bump()
    yield 1.5
    yield from wait_draws(3)
    shot('04b_CUT_slow_line_stroke.png')
    bar_card = top()[0]
    log('top bar (Slow Line + Stroke): height', round(bar_card.h), 'px =', round(bar_card.h / k), 'at scale 1 | width', round(bar_card.w))
    S.mch_brush.stab_enable = False
    S.mch_brush.shape = 'LASSO'
    ub.bump()
    yield 1.0
    yield from wait_draws(3)
    rw, dk = row(), dock()
    cards = [i for i in rw if i.kind == 'card']
    dcard = dk[0]
    labels = [i.label for i in rw if i.kind == 'glabel']
    opt = [i.label for i in dk if i.kind == 'seg']
    res['C2'] = len(cards) == 4 and all(dcard.y >= c.y + c.h for c in cards) and 'Ortho' in opt and top_bar.LANG_LABEL in opt \
        and cards[0].x == min(c.x for c in cards) and 'DEPTH' in labels and 'SYMMETRY' in labels \
        and all(c.x >= 0 and c.x + c.w <= r.width for c in cards) \
        and not any(i.kind == 'glabel' and i.label in {'DEPTH', 'OPTIONS'} for i in top())
    log('C2 bottom: boxes', len(cards), [(round(c.x), round(c.w)) for c in cards], '| dock y', round(dcard.y), 'row top',
        round(max(c.y + c.h for c in cards)), '| dock options', opt, '| row titles', labels)
    # a REAL click on an action button: Symmetry X
    ob = C.active_object
    it = next((i for i in rw if i.kind == 'abtn' and i.action[0] == 'mop' and i.action[1] == 'mch.actions_mirror'
               and i.action[2].get('axis') == 0), None)
    n0 = len(ob.modifiers)
    if it is not None:
        yield from press(it)
    yield from wait_draws(3)
    ob = C.active_object
    res['C3'] = it is not None and ob is not None and len(ob.modifiers) == n0 + 1
    log('C3 REAL click on Symmetry X:', n0, '->', len(ob.modifiers) if ob else None, [m.type for m in ob.modifiers] if ob else None)
    shot('05_symmetry_x.png')
    # the 한글 switch in the dock
    it = next((i for i in dock() if i.kind == 'seg' and i.label == top_bar.LANG_LABEL), None)
    l0 = i18n.lang()
    if it is not None:
        yield from press(it)
    yield from wait_draws(3)
    l1 = i18n.lang()
    shot('06_english.png')
    it = next((i for i in dock() if i.kind == 'seg' and i.label == top_bar.LANG_LABEL), None)
    if it is not None:
        yield from press(it)
    yield from wait_draws(3)
    res['C4'] = (l0, l1, i18n.lang()) == ('KO', 'EN', 'KO')
    log('C4 REAL clicks on 한글 in the dock:', l0, '->', l1, '->', i18n.lang())
    # a REAL right click on the empty view: the Tool Wheel
    xdo('mousemove', int(r.x + r.width * 0.5), int(w.height - (r.y + r.height * 0.6)))
    yield 0.6
    xdo('click', 3)
    yield 2.0
    opened = radial_menu.is_open()
    shot('07_right_click_wheel.png')
    # it stays: the mouse moves far away, time passes
    xdo('mousemove', int(r.x + r.width * 0.2), int(w.height - (r.y + r.height * 0.75)))
    yield 2.0
    stays = radial_menu.is_open()
    # a REAL click on another menu (the dock's Ortho): the wheel closes AND the click lands
    from mecha_lab.workspace_ui import _ORTHO_LOCK_KEY
    lock0 = bool(C.workspace.get(_ORTHO_LOCK_KEY, False))
    it = next((i for i in dock() if i.kind == 'seg' and i.label == 'Ortho'), None)
    if it is not None:
        yield from press(it)
    yield from wait_draws(3)
    lock1 = bool(C.workspace.get(_ORTHO_LOCK_KEY, False))
    closed = not radial_menu.is_open()
    if it is not None and lock1 != lock0:
        yield from press(next(i for i in dock() if i.kind == 'seg' and i.label == 'Ortho'))     # (back)
    res['C5'] = opened and stays and closed and lock1 != lock0
    log('C5 REAL right click: wheel open', opened, '| still open after the mouse left', stays,
        '| a REAL click on Ortho: closed', closed, 'Ortho', lock0, '->', lock1)
    # the tool menu's open button is in the dock's Options; a REAL click opens the menu, the row and the dock go up
    fold = next((i for i in dock() if i.kind == 'seg' and i.label == 'Tools'), None)
    with C.temp_override(window=w, area=a, region=r):
        no_pill = ub.menu_items(C, r.width, r.height, k) == []
    beside = fold is not None and not fold.on and no_pill
    y_dock0 = dock()[0].y
    if fold is not None:
        yield from press(fold)
    yield from wait_draws(3)
    shot('08_menu_open.png')
    y_dock1 = dock()[0].y
    rw1 = row()
    c1 = [i for i in rw1 if i.kind == 'card']
    res['C6'] = beside and not ub.menu_folded() and y_dock1 > y_dock0 + 50 and all(dock()[0].y >= c.y + c.h for c in c1)
    log('C6 open button in Options (not lit), no pill at the bottom', beside, '| menu open', not ub.menu_folded(), '| dock y', round(y_dock0), '->',
        round(y_dock1))
    with C.temp_override(window=w, area=a, region=r):
        ub.set_menu_folded(True)
    # 0.24.227 Blender's tool settings row: no tool icon in MECHA LAB (it shows while the toolbar - T - is hidden)
    from mecha_lab import tool_header_icon
    a.spaces.active.show_region_toolbar = False
    tool('CUT')
    yield 1.5
    for r_ in a.regions:
        r_.tag_redraw()
    yield 1.5
    p_off = shot('09_tool_row_no_icon.png')
    tool_header_icon.unregister()
    for r_ in a.regions:
        r_.tag_redraw()
    yield 1.5
    p_on = shot('10_tool_row_blender_icon.png')
    tool_header_icon.register()
    for r_ in a.regions:
        r_.tag_redraw()
    yield 1.5
    th = next(r_ for r_ in a.regions if r_.type == 'TOOL_HEADER')
    box_ = (th.x, w.height - (th.y + th.height), th.x + th.width, w.height - th.y)
    code = ('import sys; from PIL import Image, ImageChops; b = tuple(int(float(v)) for v in sys.argv[3:7]); '
            'd = ImageChops.difference(Image.open(sys.argv[1]).convert("RGB").crop(b), '
            'Image.open(sys.argv[2]).convert("RGB").crop(b)); '
            'print(d.convert("L").point(lambda v: 255 if v > 24 else 0).getbbox())')
    out_ = subprocess.run(['python3', '-c', code, p_off, p_on, *map(str, box_)], capture_output=True, text=True).stdout.strip()
    bb = eval(out_) if out_.startswith('(') else None
    res['C7'] = bb is not None and (bb[2] - bb[0]) < 80 * k and (bb[3] - bb[1]) < 40 * k
    log('C7 tool settings row: what differs with / without our patch (the icon)', bb, '| row', box_)
    a.spaces.active.show_region_toolbar = True
    i18n.force(None)
    names = {'C1': 'the LASSO bar alone at the top, the same places in every tool; dim in a tool without them (Smart Move)',
             'C2': 'the bar with Select (with Ortho, 한글) above a row of 4 boxes: the tool\'s own at the left, then the actions',
             'C3': 'a REAL click on an action button works (Symmetry X: a Mirror modifier)',
             'C4': 'REAL clicks on 한글 in the dock: English and back',
             'C5': 'a REAL right click opens the Tool Wheel; it stays when the mouse leaves; a REAL click on another menu closes it and lands there',
             'C7': 'Blender\'s tool settings row: the active tool\'s icon is not shown in MECHA LAB (only that icon differs)',
             'C6': 'the tool menu\'s open button is in the dock\'s Options; a REAL click opens the menu and the row + bar go up'}
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
