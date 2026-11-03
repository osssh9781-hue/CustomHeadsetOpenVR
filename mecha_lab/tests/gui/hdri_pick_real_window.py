"""Real window: the HDRI page's previews (0.24.95 user: "지금 hdri 고를 때 하나 밑에 칸으로 밀려서 선택돼"): MECHA LAB
screen, the HDRI page; REAL mouse (xdotool) - a click on each preview tile of the page (and after a page turn): the HDRI
set must be the one clicked.
    blender --window-geometry 0 0 W H --python this.py -- OUT"""
import math
import os
import subprocess
import sys

import bpy

sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/addon')
import mecha_lab  # noqa: E402

OUT = sys.argv[-1]
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, 'log.txt'), 'w')


def log(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    LOG.write(s + '\n')
    LOG.flush()


mecha_lab.register()
from mecha_lab import decals as dc, side_panel as sp  # noqa: E402
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


def find(pred):
    return next((i for i in panel_items() if pred(i)), None)


def scroll(dy):
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        sp.scroll_by(C, r.width, r.height, ui_factor(C, r), dy)
        a.tag_redraw()


def scrolled_to(pred):
    for _n in range(150):
        it = find(pred)
        if it is not None:
            return it
        scroll(60)
        yield 0.3
    return None


def shot(name):
    path = os.path.join(OUT, name)
    os.system(f'import -window root "{path}"')
    log('shot', name, os.path.exists(path))


def hover(it):
    w, a, r = view3d()
    x, y = to_x(w, r, it.x + it.w / 2, it.y + it.h / 2)
    xdo('mousemove', x, y)
    return x, y


def user_folder():
    """A temp HDRI folder of the user's kind: copies of Blender's HDRIs in two folders (their previews made in the
    background while the page is used); the add-on's HDRI folder pointed at it (never the user's own)."""
    import shutil
    import tempfile
    from mecha_lab import mech_shader as ms
    d = tempfile.mkdtemp(prefix='mch_hdri_')
    src = [ms.hdri_path(f) for f in ms.hdri_files()]
    for i, f in enumerate(src * 2):
        sub = os.path.join(d, 'Outdoor' if i % 2 else 'Studio')
        os.makedirs(sub, exist_ok=True)
        shutil.copy(f, os.path.join(sub, f'copy{i:02d}_' + os.path.basename(f)))
    ms.user_hdri_dir = lambda: d
    return d


def flow():
    d = user_folder()
    log('user HDRI folder', d, len(os.listdir(os.path.join(d, 'Studio'))) + len(os.listdir(os.path.join(d, 'Outdoor'))))
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
        a.spaces.active.show_region_ui = False
        bpy.ops.mch.bar_tool(tool='SELECT')
        bpy.ops.mch.side_page(page='HDRI')
    xdo('mousemove', 300, 1200)
    yield 3.0
    bad = 0
    for turn in range(6):
        if turn % 2 == 1:                               # (the panel scrolled with the real wheel first)
            first = [i for i in panel_items() if i.kind == 'htile']
            if first:
                hover(first[0])
                yield 0.2
                for _n in range(3):
                    xdo('click', 5)
                    yield 0.15
                yield 0.6
        tiles = [i for i in panel_items() if i.kind == 'htile']
        notes = [i.label for i in panel_items() if i.kind == 'pnote']
        log('page', turn, 'tiles', [(t.label, round(t.y)) for t in tiles], 'notes', notes[:3])
        for t in tiles:
            ident = t.action[2].get('ident')
            hover(t)
            yield 0.15
            xdo('click', 1)
            yield 1.0
            got = S.mch_mech_hdri
            ok = got == ident
            bad += not ok
            log('clicked', t.label, ident, '-> set', got, 'OK' if ok else 'WRONG')
        shot(f'page{turn}.png')
        nxt = find(lambda i: i.kind == 'tbtn' and i.label == '▶' and i.action[1] == 'mch.mech_hdri_page')
        if nxt is None:
            break
        hover(nxt)
        yield 0.4
        xdo('click', 1)
        yield 1.5
    log('WRONG CLICKS', bad)
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
