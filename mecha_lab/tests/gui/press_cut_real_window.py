"""Real window: Press Cut (0.24.95 user: "내가 정한 라쏘 모양을 저장해 놓으면 그걸로 잘리는데 약간 밀리면서 잘리는 거지 - 오래
누르면 더 잘리고 조금 누르면 조금만 잘리는"): MECHA LAB screen, three 2 m boxes seen from the top, the Press Cut tool;
REAL mouse (xdotool): the stamp over box A (preview shot), a short press on A, a long press on B (a shot while held),
a press on C cancelled with Esc while held, then Split on C; the pocket depth / removed volume of each; R + mouse
turns the stamp finely (Ctrl: 5 degree steps, Shift+R: 0); shots.
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
        rv.view_location = (0.0, -1.2, 0.0)
        rv.view_distance = 11.0
        for name, x, y in (('A', -2.6, 0.0), ('B', 0.0, 0.0), ('C', 2.6, 0.0), ('D', -1.4, -2.7), ('E', 1.4, -2.7)):
            bpy.ops.mesh.primitive_cube_add(size=2.0, location=(x, y, 0.0))
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
    # 0.24.95 (user: "스탬프 돌리는 것도 로테이션 각도가 좀 더 섬세하게") R + mouse: a fine turn
    import math
    S.mch_press.rotation = 0.0
    xdo('mousemove', *screen_of((0.0, -2.2, 1.0)))
    yield 0.6
    xdo('key', 'r')
    yield 0.4
    xdo('mousemove_relative', '--', 25, 0)
    yield 0.6
    shot('3_turning.png')
    xdo('click', 1)
    yield 0.5
    t1 = math.degrees(S.mch_press.rotation)
    xdo('key', 'r')
    yield 0.4
    xdo('keydown', 'ctrl')
    yield 0.2
    xdo('mousemove_relative', '--', 31, 0)
    yield 0.5
    xdo('keyup', 'ctrl')
    yield 0.2
    xdo('click', 1)
    yield 0.5
    t2 = math.degrees(S.mch_press.rotation)
    xdo('key', 'shift+r')
    yield 0.5
    t3 = math.degrees(S.mch_press.rotation)
    log('TURN R + 25 px:', round(t1, 2), 'deg | then R + Ctrl + 31 px:', round(t2, 2), 'deg (5 degree steps) | Shift+R:',
        round(t3, 2), 'deg')
    # 0.24.95 (user: "곡률은 이 스탬프가 결국 평면일 텐데 그걸 좌우로 동그랗게 커브를 주는 거지 - 위아래 좌우로 나누면")
    S.mch_press.result = 'CUT'
    S.mch_press.curve_x, S.mch_press.curve_y = 0.6, 0.0
    xdo('mousemove', *screen_of((-1.4, -2.7, 1.0)))
    yield 0.8
    shot('4_curved_stamp_over_D.png')
    xdo('mousedown', 1)
    yield 1.6
    xdo('mouseup', 1)
    yield 1.5

    def fl(ob, x, y):
        zs = [(ob.matrix_world @ v.co).z for v in ob.data.vertices
              if -0.999 < (ob.matrix_world @ v.co).z < 0.999
              and abs((ob.matrix_world @ v.co).x - x) < 0.06 and abs((ob.matrix_world @ v.co).y - y) < 0.06]
        return round(1.0 - min(zs), 3) if zs else None
    log('CURVE Left-Right 0.6 on D (about 1.6 s): depth middle', fl(boxes['D'], -1.4, -2.7), 'left/right side',
        fl(boxes['D'], -1.4 + 0.35, -2.7), 'up/down side', fl(boxes['D'], -1.4, -2.7 + 0.3), 'points',
        len(boxes['D'].data.vertices))
    S.mch_press.curve_x, S.mch_press.curve_y = 0.5, 0.5
    xdo('mousemove', *screen_of((1.4, -2.7, 1.0)))
    yield 0.8
    xdo('mousedown', 1)
    yield 1.6
    xdo('mouseup', 1)
    yield 1.5
    log('CURVE both 0.5 on E (about 1.6 s): depth middle', fl(boxes['E'], 1.4, -2.7), 'left/right side',
        fl(boxes['E'], 1.4 + 0.35, -2.7), 'up/down side', fl(boxes['E'], 1.4, -2.7 + 0.3))
    S.mch_press.curve_x = S.mch_press.curve_y = 0.0
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        for o in pieces:
            o.location.z += 0.8                      # (lifted out to be seen)
        rv = a.spaces.active.region_3d
        rv.view_perspective = 'PERSP'
        from mathutils import Euler
        rv.view_rotation = Euler((1.0, 0.0, 0.45)).to_quaternion()
        rv.view_location = (0.0, -1.3, 0.0)
        rv.view_distance = 12.0
    xdo('mousemove', 960, 1060)
    yield 1.5
    shot('5_result.png')
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
