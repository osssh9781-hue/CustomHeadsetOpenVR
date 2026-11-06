"""Real window (0.24.108): Press Cut Alt + hold (Grow) with each top edge - Sharp / Chamfer / Bevel / Round - on four
2 m boxes seen from the top, with the REAL mouse and Alt key (xdotool); then a slanted view with the wireframe on.
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
        for name, x in (('SHARP', -3.3), ('CHAMFER', -1.1), ('BEVEL', 1.1), ('ROUND', 3.3)):
            bpy.ops.mesh.primitive_cube_add(size=2.0, location=(x, 0.0, 0.0))
            C.active_object.name = 'Box_' + name
            boxes[name] = C.active_object
        bpy.ops.object.select_all(action='DESELECT')
        S.mch_press.size = 45.0
        S.mch_press.shape = 'MCH_BUILTIN_M_OCTAGON'
        S.mch_press.grow_edge_size = 0.4
        S.mch_press.grow_edge_segments = 5
        bpy.ops.mch.set_tool(tool='PRESS')
    yield 2.0
    made = {}
    for edge, box in boxes.items():
        S.mch_press.grow_edge = edge
        before = set(bpy.data.objects.keys())
        xdo('mousemove', *screen_of((box.location.x, 0.0, 1.0)))
        yield 0.6
        xdo('mousedown', 1)                 # (0.24.108: a plain hold grows; Alt + hold presses in)
        yield 1.6
        xdo('mouseup', 1)
        yield 1.2
        new = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before]
        grown = [o for o in new if o.type == 'MESH']
        made[edge] = grown
        for o in grown:
            zs = [(o.matrix_world @ v.co).z for v in o.data.vertices]
            log(f'GROW {edge}: {o.name} faces {len(o.data.polygons)} closed {closed(o)} height {max(zs) - 1.0:.3f} '
                f'smooth {sum(p.use_smooth for p in o.data.polygons)} | selected {[x.name for x in C.selected_objects]}')
        if not grown:
            log(f'GROW {edge}: nothing grown')
    shot('1_grown_top.png')
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.wm.tool_set_by_id(name='builtin.select_box')     # (the Press key legend goes away)
        C.window_manager.mch_layers_min = True                  # (the drawn panels folded for the picture)
        C.window_manager.mch_side_min = True
        sp = a.spaces.active
        sp.overlay.show_wireframes = True
        rv = sp.region_3d
        from mathutils import Euler
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((0.95, 0.0, 0.0)).to_quaternion()
        rv.view_location = (0.0, 0.3, 0.6)
        rv.view_distance = 8.0
    xdo('mousemove', 960, 1560)
    yield 1.5
    shot('2_grown_slant_wire.png')
    ok = all(made.get(e) and all(closed(o) for o in made[e]) for e in boxes)
    log('RESULT', 'all four grown and closed' if ok else 'NOT all grown/closed', {e: len(v) for e, v in made.items()})
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
