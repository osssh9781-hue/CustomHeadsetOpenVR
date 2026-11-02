"""Real window: Creature zones (0.24.95 user: "크리쳐도 이 라쏘 영역으로 재질 다르게 - 크리쳐 버전은 외곽에 에어브러시
버전, 텍스쳐 버전").  MECHA LAB screen, a creature head (a monkey, subdivided) with the Creature Shader (Reptile Dry),
the Creature page: REAL mouse (xdotool) - the ZONES title, Paint Zone, a lasso DRAGGED over the brow (Airbrush, the
default), again on a cheek (then Edge: Texture), again round an eye (Edge: Hard); shots.
    blender --window-geometry 0 0 W H --python this.py -- OUT"""
import math
import os
import subprocess
import sys

import bpy
from mathutils import Euler

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


def flow():
    from mecha_lab import zones as zn
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
        bpy.ops.mesh.primitive_monkey_add(size=2.0)
        part = C.active_object
        part.name = 'Head'
        sub = part.modifiers.new('s', 'SUBSURF')
        sub.levels = 2
        bpy.ops.object.convert(target='MESH')
        bpy.ops.object.shade_smooth()
        bpy.ops.mch.creature_apply(skin='REPTILE', condition='CLEAN')
        sp3 = a.spaces.active
        sp3.shading.type = 'MATERIAL'
        sp3.overlay.show_wireframes = True
        rv = sp3.region_3d
        rv.view_rotation = (Euler((math.radians(80), 0.0, math.radians(20))).to_quaternion())
        rv.view_location = (0.0, 0.0, 0.1)
        rv.view_distance = 5.5
        sp3.show_region_ui = False
        bpy.ops.mch.bar_tool(tool='SELECT')
        bpy.ops.mch.side_page(page='CREATURE')
    xdo('mousemove', 300, 1200)
    yield 45.0                                             # (EEVEE compiles)
    head = yield from scrolled_to(lambda i: i.kind == 'shead' and i.label.startswith('ZONES'))
    log('ZONES title at', hover(head), 'open before', head.on)
    yield 0.4
    xdo('click', 1)
    yield 1.5
    from bpy_extras import view3d_utils
    mat = part.active_material

    def scr(co):
        w2, a2, r2 = view3d()
        p = view3d_utils.location_3d_to_region_2d(r2, r2.data, co)
        return to_x(w2, r2, p.x, p.y)

    def lasso(centre, rx, rz):
        cx, cy, cz = centre
        return [scr((cx + rx * math.cos(t), cy, cz + rz * math.sin(t))) for t in
                [k * 2 * math.pi / 28 for k in range(29)]]
    for label, centre, rx, rz, edge in (('brow', (0.0, -0.95, 0.42), 0.55, 0.16, 'AIRBRUSH'),
                                         ('cheek', (0.55, -0.75, -0.15), 0.25, 0.2, 'TEXTURE'),
                                         ('eye', (-0.35, -0.85, 0.15), 0.2, 0.14, 'HARD')):
        btn = yield from scrolled_to(lambda i: i.kind == 'tbtn' and i.label == 'Paint Zone')
        hover(btn)
        yield 0.4
        xdo('click', 1)
        yield 1.0
        ring = lasso(centre, rx, rz)
        xdo('mousemove', *ring[0])
        yield 0.3
        xdo('mousedown', 1)
        yield 0.2
        for p in ring[1:]:
            xdo('mousemove', *p)
            yield 0.04
        xdo('mouseup', 1)
        yield 2.0
        z = mat.mch_zones[len(mat.mch_zones) - 1]
        with C.temp_override(window=w, area=a, region=r):
            z.edge = edge
            if edge == 'TEXTURE':
                z.edge_width = 6.0
            if edge == 'AIRBRUSH':
                z.edge_width = 8.0
        log('dragged lasso on the', label, ': zones', len(mat.mch_zones), 'its edge', z.edge, 'colour',
            tuple(round(c, 2) for c in z.color))
    xdo('mousemove', 300, 1200)
    yield 30.0
    shot('1_creature_zones.png')
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
