"""Real window (0.24.108): Grow on a BUMPY surface - Top: Follow (left) vs Top: Flat (right), Sharp and Round, with
the real mouse and Alt key; a slanted view with the wireframe on.
    blender --window-geometry 0 0 W H --python this.py -- OUT"""
import os
import random
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


def bumpy(name, x, amp=0.08, seed=1):
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(x, 0.0, 0.0))
    ob = C.active_object
    ob.name = name
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    top = [f for f in bm.faces if f.normal.z > 0.9]
    bmesh.ops.subdivide_edges(bm, edges=list({e for f in top for e in f.edges}), cuts=40, use_grid_fill=True)
    random.seed(seed)
    for v in bm.verts:
        if v.co.z > 0.99 and abs(v.co.x) < 0.99 and abs(v.co.y) < 0.99:
            v.co.z += random.uniform(-amp, amp)
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def closed(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    n = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return n == 0


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
    boxes = {}
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        sp = a.spaces.active
        sp.show_region_ui = False
        rv = sp.region_3d
        bpy.ops.view3d.view_axis(type='TOP')
        rv.view_perspective = 'ORTHO'
        rv.view_location = (0.0, 0.0, 0.0)
        rv.view_distance = 14.0
        for key, x in ((('FOLLOW', 'SHARP'), -3.3), (('FOLLOW', 'ROUND'), -1.1), (('FLAT', 'SHARP'), 1.1),
                       (('FLAT', 'ROUND'), 3.3)):
            boxes[key] = bumpy('Bumpy_' + '_'.join(key), x)
        bpy.ops.object.select_all(action='DESELECT')
        S.mch_press.size = 45.0
        S.mch_press.shape = 'MCH_BUILTIN_M_OCTAGON'
        bpy.ops.mch.set_tool(tool='PRESS')
    yield 2.0
    made = {}
    for (top, edge), box in boxes.items():
        S.mch_press.grow_top, S.mch_press.grow_edge = top, edge
        before = set(bpy.data.objects.keys())
        xdo('mousemove', *screen_of((box.location.x, 0.0, 1.1)))
        yield 0.6
        xdo('keydown', 'alt')
        yield 0.15
        xdo('mousedown', 1)
        yield 1.6
        xdo('mouseup', 1)
        yield 0.15
        xdo('keyup', 'alt')
        yield 1.2
        grown = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before if bpy.data.objects[n].type == 'MESH']
        made[(top, edge)] = grown
        for o in grown:
            co = [o.matrix_world @ v.co for v in o.data.vertices]
            n = len(co) // 2
            tz = [v.z for v in co[n:]]
            log(f'GROW top={top} edge={edge}: {o.name} closed {closed(o)} outer face z {min(tz):.3f}..{max(tz):.3f} '
                f'(spread {max(tz) - min(tz):.3f})')
        if not grown:
            log(f'GROW top={top} edge={edge}: nothing grown')
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.wm.tool_set_by_id(name='builtin.select_box')
        C.window_manager.mch_layers_min = True
        C.window_manager.mch_side_min = True
        sp = a.spaces.active
        sp.overlay.show_wireframes = True
        rv = sp.region_3d
        from mathutils import Euler
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((1.15, 0.0, 0.0)).to_quaternion()
        rv.view_location = (0.0, 0.3, 0.8)
        rv.view_distance = 7.5
    xdo('mousemove', 960, 1560)
    yield 1.5
    shot('1_bumpy_follow_vs_flat.png')
    ok = all(made.get(k) and all(closed(o) for o in made[k]) for k in boxes)
    log('RESULT', 'all four grown and closed' if ok else 'NOT all grown/closed')
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
