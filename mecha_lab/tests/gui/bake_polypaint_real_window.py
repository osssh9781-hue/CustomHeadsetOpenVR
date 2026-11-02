"""Real window: Bake to Polypaint (0.24.95 user: "폴리페인트로 구워 줘").  MECHA LAB screen, a creature head (a
monkey, subdivided) with the Creature Shader (Reptile), two markings (Paint Zones) and some mud; the Creature page:
REAL mouse (xdotool) - the BAKE title, Bake to Polypaint (the colour into "Baked Color", one per point), then Show
Polypaint (Solid shading with the colour layer); shots before / after, wireframe on.
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
    from mecha_lab import zones as zn, bake_material as bk
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
        sub.levels = 3
        bpy.ops.object.convert(target='MESH')
        bpy.ops.object.shade_smooth()
        bpy.ops.mch.creature_apply(skin='REPTILE', condition='CLEAN')
        mat = part.active_material
        mat.mch_creature.mud_low = 0.7
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
    yield 1.0
    from bpy_extras import view3d_utils
    w, a, r = view3d()
    rv3d = r.data

    def px(co):
        p = view3d_utils.location_3d_to_region_2d(r, rv3d, co)
        return (p.x, p.y)

    def ell(c, rx, ry):
        cx, cy = px(c)
        return [(cx + rx * math.cos(t), cy + ry * math.sin(t)) for t in [k * 2 * math.pi / 32 for k in range(32)]]
    with C.temp_override(window=w, area=a, region=r):
        z1 = zn.add_paint_zone(C, part, ell((0.0, -0.8, 0.5), 170, 36), rv3d.view_matrix, rv3d.window_matrix, True,
                               r.width, r.height, color=(0.05, 0.045, 0.035))
        z1.edge, z1.edge_width = 'AIRBRUSH', 6.0
        z2 = zn.add_paint_zone(C, part, ell((0.6, -0.6, -0.15), 70, 60), rv3d.view_matrix, rv3d.window_matrix, True,
                               r.width, r.height, color=(0.55, 0.06, 0.04))
        z2.edge, z2.edge_width = 'TEXTURE', 5.0
    xdo('mousemove', 300, 1200)
    yield 45.0                                             # (EEVEE compiles)
    shot('1_material.png')
    head = yield from scrolled_to(lambda i: i.kind == 'shead' and i.label.startswith('BAKE'))
    log('BAKE title at', hover(head), 'open before', head.on)
    yield 0.4
    xdo('click', 1)
    yield 1.5
    btn = yield from scrolled_to(lambda i: i.kind == 'tbtn' and i.label == 'Bake to Polypaint')
    log('Bake to Polypaint at', hover(btn), 'points', len(part.data.vertices))
    yield 0.4
    xdo('click', 1)
    yield 15.0
    lay = part.data.color_attributes.get(bk.LAYER)
    log('after the click: layer', lay.name if lay else None, 'active', part.data.color_attributes.active_color_name,
        'last', bk.LAST)
    btn = yield from scrolled_to(lambda i: i.kind == 'tbtn' and i.label == 'Show Polypaint')
    hover(btn)
    yield 0.4
    xdo('click', 1)
    yield 2.0
    log('Show Polypaint: shading', a.spaces.active.shading.type, a.spaces.active.shading.color_type)
    xdo('mousemove', 300, 1200)
    yield 5.0
    shot('2_polypaint.png')
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
