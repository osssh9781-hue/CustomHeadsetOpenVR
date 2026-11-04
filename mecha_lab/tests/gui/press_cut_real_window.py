"""Real window: Press Cut (0.24.95 user: "내가 정한 라쏘 모양을 저장해 놓으면 그걸로 잘리는데 약간 밀리면서 잘리는 거지 - 오래
누르면 더 잘리고 조금 누르면 조금만 잘리는"): MECHA LAB screen, three 2 m boxes seen from the top, the Press Cut tool;
REAL mouse (xdotool): the stamp over box A (preview shot), a short press on A, a long press on B (a shot while held),
a press on C cancelled with Esc while held, then Split on C; the pocket depth / removed volume of each, shots.
    blender --window-geometry 0 0 W H --python this.py -- OUT"""
import os
import subprocess
import sys

import bmesh
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


def shot(name):
    path = os.path.join(OUT, name)
    os.system(f'import -window root "{path}"')
    log('shot', name, os.path.exists(path))


def screen_of(co):
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    w, a, r = view3d()
    p = location_3d_to_region_2d(r, a.spaces.active.region_3d, co)
    return int(r.x + p.x), int(w.height - (r.y + p.y))


def volume(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    v = bm.calc_volume()
    bm.free()
    return v


def pocket(ob):
    """(lowest point of the pocket below the top, the box's volume)"""
    zs = [(ob.matrix_world @ v.co).z for v in ob.data.vertices]
    inner = [z for z in zs if -0.999 < z < 0.999]
    return (round(1.0 - min(inner), 4) if inner else 0.0), round(volume(ob), 4)


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
    boxes = {}
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        sp = a.spaces.active
        sp.show_region_ui = False
        sp.overlay.show_wireframes = True
        rv = sp.region_3d
        bpy.ops.view3d.view_axis(type='TOP')
        rv.view_perspective = 'ORTHO'
        rv.view_location = (0.0, 0.0, 0.0)
        rv.view_distance = 9.0
        for name, x in (('A', -2.6), ('B', 0.0), ('C', 2.6)):
            bpy.ops.mesh.primitive_cube_add(size=2.0, location=(x, 0.0, 0.0))
            C.active_object.name = name
            boxes[name] = C.active_object
        bpy.ops.object.select_all(action='DESELECT')
        S.mch_settings.auto_apply = True
        S.mch_press.size = 45.0
        S.mch_press.result = 'CUT'
        bpy.ops.mch.set_tool(tool='PRESS')
    yield 2.0
    log('tool', S.mch_press.shape, 'start', S.mch_press.start, 'speed', S.mch_press.speed)
    before = {n: pocket(b) for n, b in boxes.items()}
    log('before', before)

    xy = screen_of((-2.6, 0.0, 1.0))
    xdo('mousemove', *xy)
    yield 1.0
    shot('1_stamp_over_A.png')
    xdo('mousedown', 1)                              # a short press
    yield 0.15
    xdo('mouseup', 1)
    yield 1.5
    a_after = pocket(boxes['A'])
    log('SHORT press on A (about 0.15 s): pocket depth', a_after[0], 'volume', before['A'][1], '->', a_after[1])

    xy = screen_of((0.0, 0.0, 1.0))
    xdo('mousemove', *xy)
    yield 0.6
    xdo('mousedown', 1)                              # a long press
    yield 1.0
    shot('2_holding_B.png')
    yield 1.0
    xdo('mouseup', 1)
    yield 1.5
    b_after = pocket(boxes['B'])
    log('LONG press on B (about 2 s): pocket depth', b_after[0], 'volume', before['B'][1], '->', b_after[1])

    xy = screen_of((2.6, 0.0, 1.0))
    xdo('mousemove', *xy)
    yield 0.6
    xdo('mousedown', 1)                              # pressed, then Esc while held
    yield 0.8
    xdo('key', 'Escape')
    yield 0.4
    xdo('mouseup', 1)
    yield 1.0
    c_after = pocket(boxes['C'])
    log('Esc while holding on C: pocket depth', c_after[0], 'volume', before['C'][1], '->', c_after[1],
        '- backup meshes left', [m.name for m in bpy.data.meshes if m.name.startswith('MCH_PressBackup')])

    S.mch_press.result = 'SPLIT'
    yield 0.5
    xdo('mousedown', 1)
    yield 1.2
    xdo('mouseup', 1)
    yield 1.5
    pieces = [o for o in S.objects if o.name.startswith('C_Split')]
    log('SPLIT press on C (about 1.2 s): pieces', [(o.name, round(volume(o), 4)) for o in pieces],
        'C now', pocket(boxes['C']))
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        for o in pieces:
            o.location.z += 0.8                      # (lifted out to be seen)
        rv = a.spaces.active.region_3d
        rv.view_perspective = 'PERSP'
        from mathutils import Euler
        rv.view_rotation = Euler((1.05, 0.0, 0.5)).to_quaternion()
        rv.view_distance = 10.0
    xdo('mousemove', 960, 1060)
    yield 1.5
    shot('3_result.png')
    log('DONE short', a_after[0], 'long', b_after[0], 'longer is deeper', b_after[0] > a_after[0] > 0.0)
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
