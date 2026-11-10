"""Real window (0.24.128, user: "메쉬 커브로 커브 그으면 ... 다른 오브젝트 클릭해서 ... 커브에 연결해서 나열되게 해 줘"):
draw a Mesh Curve with the real mouse, Enter; Q (Select); Shift + click a part -> the part is repeated along the curve.

  1. Mesh Curve tool: four clicks in the air + Return -> a live tube (active, yellow)
  2. Q -> Select; Shift + click the part: the part active (yellow), the curve selected (orange) -> Repeat, source = the part
  3. a plain click on the part first (curve not selected) does nothing; screenshot
"""
import os
import subprocess
import sys

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'addon'))
import mecha_lab  # noqa: E402
from mecha_lab import curve_tube as ct, tool_state as ts  # noqa: E402
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


def click(pt, shift=False):
    xdo('mousemove', *pt)
    yield 0.35
    if shift:
        xdo('keydown', 'shift')
        yield 0.1
    xdo('click', 1)
    if shift:
        yield 0.1
        xdo('keyup', 'shift')
    yield 0.9


def orbit(rot, loc, dist, persp=False):
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        rv = a.spaces.active.region_3d
        rv.view_perspective = 'PERSP' if persp else 'ORTHO'
        rv.view_rotation = Euler(rot).to_quaternion()
        rv.view_location = loc
        rv.view_distance = dist


def sel_state():
    act = C.view_layer.objects.active
    return (act.name if act else None, sorted(o.name for o in C.selected_objects))


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
        WM.mch_layers_min = True
        WM.mch_side_min = True
        WM.mch_legend_min = True
        bpy.ops.mesh.primitive_cube_add(size=0.5, location=(3.0, 0.0, 0.0))
        part = C.active_object
        part.name = 'Part'
        part.select_set(False)
        C.view_layer.objects.active = None
        S.mch_tube_defaults.radius = 0.12
    res = {}
    orbit((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 10.0)
    yield 1.0
    # 1. the Mesh Curve tool starts drawing right away: four clicks in the air, Return
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.set_tool(tool='TUBE')
    yield 1.0
    log('1 tool', ts.effective_tool(C), 'draw ops', len(ct._draw_ops))
    before = set(bpy.data.objects.keys())
    for p3 in ((-3.0, -1.0, 0.0), (-1.5, 0.6, 0.0), (0.0, -0.6, 0.0), (1.5, 0.9, 0.0)):
        yield from click(screen_of(p3))
    focus()
    xdo('key', 'Return')
    yield 1.2
    tubes = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before if ct.is_tube(bpy.data.objects[n])]
    tube = tubes[0] if tubes else None
    log('   tube', tube.name if tube else None, 'points', len(ct.get_points(tube)) if tube else 0, 'sel', sel_state(), 'draw ops', len(ct._draw_ops))
    res['1 Mesh Curve: four clicks + Return make a live tube, the active (yellow) one'] = \
        tube is not None and len(ct.get_points(tube)) == 4 and sel_state() == (tube.name, [tube.name]) and tube.mch_tube.mode == 'TUBE'
    if tube is None:
        shot('1_no_tube.png')
        for k_, v in res.items():
            log(('PASS ' if v else 'FAIL ') + k_)
        bpy.ops.wm.quit_blender()
        return
    # 1b. the bar's Radius slider (a 2D rect gizmo: its hit test is test_select since 0.24.129) - drag it right
    ui = C.preferences.system.ui_scale
    pos = ct.tube_bar_layout(r.width / ui, r.height / ui)['slider_radius']
    sx, sy = int(round(r.x + pos[0] * ui)), int(round(w.height - (r.y + pos[1] * ui)))
    r0 = tube.mch_tube.radius
    xdo('mousemove', sx, sy)
    yield 0.4
    xdo('mousedown', 1, 'sleep', 0.1, 'mousemove', sx + 30, sy, 'sleep', 0.08, 'mousemove', sx + 60, sy, 'sleep', 0.08, 'mouseup', 1)
    yield 1.0
    log('1b radius slider drag at', (sx, sy), 'radius', round(r0, 4), '->', round(tube.mch_tube.radius, 4))
    res['1b the bar\'s Radius slider takes a drag (the 2D gizmo hit test works in Blender 5.2)'] = tube.mch_tube.radius > r0 * 1.2
    # 2. Q -> Select, Shift + click the part
    focus()
    xdo('key', 'q')
    yield 0.8
    log('2 after Q: tool', ts.effective_tool(C), ts.native_tool_id(C), 'sel', sel_state())
    yield from click(screen_of((3.0, 0.0, 0.25)), shift=True)
    yield 0.8                                             # (the selection watcher ticks every 0.2 s)
    st = sel_state()
    log('   after Shift+click: sel', st, 'mode', tube.mch_tube.mode, 'source', tube.mch_tube.source.name if tube.mch_tube.source else None,
        'verts', len(tube.data.vertices), 'count', tube.mch_tube.count, 'spacing', tube.mch_tube.spacing_mode, round(tube.mch_tube.spacing, 3))
    res['2 Shift + click the part (part yellow, curve orange): the part is repeated along the curve'] = \
        st == ('Part', ['Part', tube.name]) and tube.mch_tube.mode == 'REPEAT' and tube.mch_tube.source == part \
        and len(tube.data.vertices) % 8 == 0 and len(tube.data.vertices) >= 16 and tube.mch_tube.spacing_mode == 'DISTANCE' \
        and abs(tube.mch_tube.spacing - 0.5) < 1e-6
    shot('2_repeat_along_curve.png')
    # 3. a plain click on empty space, then on the part: nothing changes (curve back to Tube first)
    with C.temp_override(window=w, area=a, region=r):
        tube.mch_tube.mode, tube.mch_tube.source = 'TUBE', None
    yield 0.6
    yield from click(screen_of((-3.0, 3.0, 0.0)))                     # empty space: deselect all
    yield from click(screen_of((3.0, 0.0, 0.25)))                     # the part alone
    yield 0.8
    log('3 plain click: sel', sel_state(), 'mode', tube.mch_tube.mode)
    res['3 a plain click on the part (the curve not selected) links nothing'] = tube.mch_tube.mode == 'TUBE' and tube.mch_tube.source is None
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
