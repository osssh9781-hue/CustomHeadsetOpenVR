"""Real window (0.24.129, user: "지금 왜 아머 플레이트 하는데 계속 꺼지냐" + UnicodeDecodeError traceback from the Layers panel):
an object whose name is CP949 Korean bytes (not UTF-8) sits in the scene, the Layers panel is open, the Armor Plate tool is
used with the real mouse.  Before: every UI build (every mouse move / tool invoke) died with the traceback.  Now: the drawn UI
repairs the name (back to the Korean word), no traceback, the plate is made.

  1. a sphere + a cube whose name bytes are b'\\xb6\\xf3\\xb8\\xde' ('라메' in CP949); Layers panel open; mouse moves -> repaired
  2. Armor Plate tool: a lasso on the sphere -> a plate; no UnicodeDecodeError anywhere in the log
"""
import ctypes
import math
import os
import subprocess
import sys

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'addon'))
import mecha_lab  # noqa: E402
from mecha_lab import name_fix as nf, tool_state as ts  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402

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


def shot(name):
    path = os.path.join(OUT, name)
    os.system(f'import -window root "{path}"')
    log('shot', name, os.path.exists(path))


def screen_of(co):
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    w, a, r = view3d()
    p = location_3d_to_region_2d(r, a.spaces.active.region_3d, Vector(co))
    return int(round(r.x + p.x)), int(round(w.height - (r.y + p.y)))


def drag(points):
    xdo('mousemove', *points[0])
    yield 0.3
    xdo('mousedown', 1, 'sleep', 0.12, 'mousemove', *points[1], 'sleep', 0.03, 'mousemove', *points[2])
    yield 0.05
    for p in points[3:]:
        xdo('mousemove', *p)
        yield 0.03
    xdo('mouseup', 1)
    yield 2.5


def circle(cx, cy, r, n=16):
    return [(int(round(cx + r * math.cos(math.tau * k / n))), int(round(cy + r * math.sin(math.tau * k / n)))) for k in range(n)]


def orbit(rot, loc, dist, persp=False):
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        rv = a.spaces.active.region_3d
        rv.view_perspective = 'PERSP' if persp else 'ORTHO'
        rv.view_rotation = Euler(rot).to_quaternion()
        rv.view_location = loc
        rv.view_distance = dist


def poke_name(ob, raw):
    buf = b'OB' + raw + b'\0'
    ctypes.memmove(ob.as_pointer() + nf.NAME_OFFSET, buf, len(buf))


def flow():
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
    WM = C.window_manager
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        a.spaces.active.show_region_ui = False
        a.spaces.active.overlay.show_wireframes = True
        S.cursor.location = (0.0, 0.0, 0.0)
        WM.mch_layers_min = False                 # the Layers panel open: the reader that died
        WM.mch_side_min = True
        WM.mch_legend_min = True
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.5, segments=48, ring_count=24, location=(0, 0, 0))
        sphere = C.active_object
        sphere.name = 'Body'
        bpy.ops.mesh.primitive_cube_add(size=0.6, location=(3.0, 0.0, 0.0))
        bad = C.active_object
        bad.name = 'Imported'
        for o in (sphere, bad):
            o.select_set(False)
        C.view_layer.objects.active = None
        S.mch_settings.auto_apply = True
    res = {}
    orbit((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 9.0)
    yield 1.0
    # 1. the bad name appears (as after an import); the mouse moves over the view -> the drawn UI builds
    poke_name(bad, '라메'.encode('cp949'))
    log('1 poked:', nf.safe_name(bad), 'offset ok', nf.offset_ok(), 'bad blocks', len(nf.bad_blocks()))
    focus()
    for x in (700, 900, 1100):
        xdo('mousemove', x, 700)
        yield 0.4
    log('   after mouse moves: name', nf.safe_name(bad), 'bad blocks', len(nf.bad_blocks()), 'LAST', nf.LAST)
    res['1 a CP949 name in the scene + the Layers panel open: the drawn UI repairs it to the Korean word instead of dying'] = \
        nf.safe_name(bad) == '라메' and not nf.bad_blocks()
    shot('1_repaired.png')
    # 2. Armor Plate with the real mouse
    with C.temp_override(window=w, area=a, region=r):
        S.mch_brush.shape = 'STROKE'
        S.mch_brush.line_open = False
        bpy.ops.mch.set_tool(tool='PLATE')
    yield 0.8
    before = set(bpy.data.objects.keys())
    cx, cy = screen_of((0.0, 0.2, 0.0))
    yield from drag(circle(cx, cy, 90, n=32) + circle(cx, cy, 90, n=32)[:2])
    new = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before if bpy.data.objects[n].type == 'MESH']
    log('2 Armor Plate lasso -> new', [(o.name, len(o.data.polygons)) for o in new], 'tool', ts.effective_tool(C))
    res['2 Armor Plate: a lasso on the body makes a plate (the tool no longer dies)'] = bool(new) and len(new[0].data.polygons) > 10
    yield 0.5
    shot('2_armor_plate.png')
    for k_, v in res.items():
        log(('PASS ' if v else 'FAIL ') + k_)
    log(f'{sum(res.values())}/{len(res)} passed')
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
