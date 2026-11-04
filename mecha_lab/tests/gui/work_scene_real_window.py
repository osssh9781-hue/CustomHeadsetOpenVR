"""Real window (0.24.95 user: "그렇게 버튼 만들어 줘" - Work Scene): MECHA LAB screen, a group 'Arm' (two parts).  A REAL
click on the Layers panel's "Work Scene" button: a second window opens showing the scene "Work - Arm" (only the
group), the first one still the main scene with a Collection Instance where the group was (a shot).  A part edited
in the work scene: the instance in the main scene follows.  Bring Back pressed in the work window: the group back in
the main scene, the work scene gone, the work window closed (a shot).
    blender --window-geometry 0 0 W H --python this.py -- OUT"""
import os
import subprocess
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/addon')
import mecha_lab  # noqa: E402

ARGS = sys.argv[sys.argv.index('--') + 1:]
OUT = ARGS[0]
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, 'log.txt'), 'w')


def log(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    LOG.write(s + '\n')
    LOG.flush()


mecha_lab.register()
from mecha_lab import groups, layers_panel as lp, work_scene as wk  # noqa: E402
from mecha_lab.ui_gpu import ui_factor  # noqa: E402
C = bpy.context


def xdo(*args):
    subprocess.run(['xdotool', *map(str, args)], check=False)


def focus():
    r = subprocess.run(['xdotool', 'search', '--name', 'Blender'], capture_output=True, text=True)
    for wid in r.stdout.split()[:1]:
        subprocess.run(['xdotool', 'windowfocus', '--sync', wid], check=False)


def view3d(win=None):
    for w in ([win] if win else C.window_manager.windows):
        for a in w.screen.areas:
            if a.type == 'VIEW_3D':
                return w, a, next(r for r in a.regions if r.type == 'WINDOW')
    return None, None, None


def shot(name):
    path = os.path.join(OUT, name)
    os.system(f'import -window root "{path}"')
    log('shot', name, os.path.exists(path))


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
    main = w.scene
    with C.temp_override(window=w, area=a, region=r):
        for o in list(main.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(1.5, 0.0, 0.0))
        p1 = C.active_object
        bpy.ops.mesh.primitive_cylinder_add(radius=0.3, depth=1.2, location=(2.4, 0.4, 0.0))
        p2 = C.active_object
        g = groups.create(C, [p1, p2], 'Arm')
        sp3 = a.spaces.active
        sp3.shading.type = 'SOLID'
        r3 = sp3.region_3d
        r3.view_perspective = 'PERSP'
        r3.view_location = (1.5, 0.0, 0.0)
        r3.view_distance = 9.0
        bpy.ops.mch.bar_tool(tool='SELECT')
    yield 3.0
    with C.temp_override(window=w, area=a, region=r):
        its = lp.items(C, r.width, r.height, ui_factor(C, r))
    b = next((i for i in its if i.kind == 'tbtn' and i.label == 'Work Scene'), None)
    log('main', main.name, 'windows', len(C.window_manager.windows), 'Work Scene button', b is not None and b.enabled)
    shot('1_group_in_main.png')
    x, y = int(r.x + b.x + b.w / 2), int(w.height - (r.y + b.y + b.h / 2))
    xdo('mousemove', x, y)
    yield 0.5
    xdo('click', 1)
    yield 4.0
    wins = list(C.window_manager.windows)
    work = bpy.data.scenes.get('Work - Arm')
    inst = next((o for o in main.objects if o.get(wk.OF)), None)
    log('after the REAL click: windows', len(wins), 'scenes shown', [x.scene.name for x in wins],
        'work scene objects', sorted(o.name for o in work.objects) if work else None,
        'main objects', sorted(o.name for o in main.objects), 'instance', inst and inst.instance_collection.name)
    shot('2_work_window_opened.png')
    if work is None or inst is None:
        log('DONE (not sent)')
        bpy.ops.wm.quit_blender()
        return
    p1.data.vertices[0].co += Vector((0.0, 0.0, 0.6))     # (an edit in the work scene)
    p1.data.update()
    yield 2.0
    dg = main.view_layers[0].depsgraph
    z = None
    for di in dg.object_instances:
        if di.is_instance and di.parent is not None and di.parent.original == inst and di.object.original == p1:
            z = round(di.object.data.vertices[0].co.z, 3)
    log('the instance in the main scene shows the edit: vertex z', z)
    ww = next((x for x in wins if x.scene == work), None)
    w2, a2, r2 = view3d(ww)
    if ww is not None:
        with C.temp_override(window=ww, area=a2, region=r2, scene=work):
            res = bpy.ops.mch.work_scene(action='BACK')
        log('Bring Back from the work window:', res)
    yield 3.0
    wins = list(C.window_manager.windows)
    log('after Bring Back: windows', len(wins), 'scenes shown', [x.scene.name for x in wins],
        'Work - Arm left', 'Work - Arm' in bpy.data.scenes, 'group in main', g.name in main.objects,
        'parts in main', p1.name in main.objects and p2.name in main.objects,
        'instances left', [o.name for o in main.objects if o.get(wk.OF)])
    shot('3_brought_back.png')
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
