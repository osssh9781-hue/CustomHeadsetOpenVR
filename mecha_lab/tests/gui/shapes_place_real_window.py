"""Real window: the Shapes page's thumbnails (0.24.95 user: "쉐입 페이지에서 썸네일도 보여 주라, 그거 선택하고 변경 가능하게",
"쉐입 실시간으로 바뀌어야지"): MECHA LAB screen, the Shapes page, Real Parts (Car Bot); Summon Part; REAL mouse
(xdotool) - a click on another part's thumbnail: the summoned part becomes it at once; shots.  Then (0.24.95 user:
"썸네일 클릭하고 원하는 메쉬 근처에 클릭하면 거기에 붙는 게 좋겠어 - 에셋 라이브러리처럼"): a thumbnail clicked, the mouse
over the box, a click - the part stands on the box's surface there; Shift+click two, Esc.
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


def to_screen(w, r, co):
    from bpy_extras import view3d_utils
    a = [x for x in w.screen.areas if x.type == 'VIEW_3D'][0]
    p = view3d_utils.location_3d_to_region_2d(r, a.spaces.active.region_3d, co)
    return to_x(w, r, p.x, p.y)


def flow():
    from mathutils import Vector
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
        bpy.ops.mesh.primitive_cube_add(size=4.0, location=(0.0, 0.0, 0.0))
        box = C.active_object
        box.name = 'Box'
        sv = a.spaces.active
        sv.show_region_ui = False
        sv.region_3d.view_distance = 16.0
        bpy.ops.mch.bar_tool(tool='SELECT')
        bpy.ops.mch.side_page(page='SHAPES')
        bpy.ops.mch.random_shape_ref(vehicle='CARBOT')
        S.mch_rshape.size = 1.2
    xdo('mousemove', 300, 1200)
    yield 3.0
    from mecha_lab import random_shapes as rs
    tile = yield from scrolled_to(lambda i: i.kind == 'mtile' and i.action[1] == 'mch.random_shape_place'
                                  and i.action[2].get('part') == 'HEAD')
    log('Head thumbnail at', hover(tile))
    yield 0.4
    xdo('click', 1)
    yield 1.0
    w, a, r = view3d()
    top = to_screen(w, r, Vector((0.3, -0.4, 2.0)))           # (on the box's top face)
    xdo('mousemove', top[0], top[1])
    yield 0.8
    shot('3_placing.png')
    xdo('click', 1)
    yield 1.5
    heads = [o for o in S.objects if rs.is_shape(o)]
    ob = heads[-1] if heads else None
    if ob is not None:
        C.view_layer.update()
        low = min((ob.matrix_world @ v.co).z for v in ob.data.vertices)
        up = (ob.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
        log('placed', rs.params_of(ob)['part'], 'its lowest point z', round(low, 4), '(box top 2.0)', 'up',
            tuple(round(c, 3) for c in up), 'selected', ob.select_get())
    tile = yield from scrolled_to(lambda i: i.kind == 'mtile' and i.action[1] == 'mch.random_shape_place'
                                  and i.action[2].get('part') == 'WHEEL')
    hover(tile)
    yield 0.4
    xdo('click', 1)
    yield 1.0
    side = to_screen(w, r, Vector((2.0, -0.8, 0.3)))          # (on the box's +X side)
    xdo('mousemove', side[0], side[1])
    yield 0.6
    xdo('keydown', 'shift')
    xdo('click', 1)
    xdo('keyup', 'shift')
    yield 1.2
    side2 = to_screen(w, r, Vector((2.0, 0.9, 0.3)))
    xdo('mousemove', side2[0], side2[1])
    yield 0.6
    xdo('click', 1)
    yield 1.5
    wheels = [o for o in S.objects if rs.is_shape(o) and rs.params_of(o)['part'] == 'WHEEL']
    for o in wheels:
        up = (o.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
        log('wheel on the side: up', tuple(round(c, 3) for c in up), 'at x', round(o.location.x, 3))
    log('wheels placed', len(wheels), 'shapes in the scene', len([o for o in S.objects if rs.is_shape(o)]))
    xdo('mousemove', 300, 1200)
    yield 2.0
    shot('4_placed.png')
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
