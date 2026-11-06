"""Real window (0.24.108): the four Press Cut gestures with the REAL mouse and Alt key (user: "그냥 그릴 때는 베이스
메쉬 라인, Alt 는 컷 라인, 그냥 꾹 누르면 메쉬가 나오고, Alt + 꾹은 잘려야"), octagon stamp, size 40 px:
  A: plain drag      -> a Base Mesh line whose section is the stamp (as wide / tall as the stamp on screen)
  B: Alt + drag      -> a Line Cut groove as wide as the stamp
  C: plain hold      -> a mesh grows out (Grow)
  D: Alt + hold      -> the stamp pressed in (a pocket)
A slanted view with the wireframe on at the end.
    blender --window-geometry 0 0 W H --python this.py -- OUT"""
import math
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


def volume(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    v = bm.calc_volume()
    bm.free()
    return v


def closed(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    n = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return n == 0


def bbox(ob):
    pts = [ob.matrix_world @ bpy.mathutils_Vector(c) if False else ob.matrix_world @ __import__('mathutils').Vector(c)
           for c in ob.bound_box]
    return [(min(q[i] for q in pts), max(q[i] for q in pts)) for i in range(3)]


def drag(points, alt=False):
    xdo('mousemove', *points[0])
    yield 0.25
    if alt:
        xdo('keydown', 'alt')
        yield 0.1
    xdo('mousedown', 1)
    yield 0.05
    for p in points[1:]:
        xdo('mousemove', *p)
        yield 0.03
    xdo('mouseup', 1)
    yield 0.1
    if alt:
        xdo('keyup', 'alt')
    yield 1.8


def hold(xy, seconds, alt=False):
    xdo('mousemove', *xy)
    yield 0.4
    if alt:
        xdo('keydown', 'alt')
        yield 0.1
    xdo('mousedown', 1)
    yield seconds
    xdo('mouseup', 1)
    yield 0.1
    if alt:
        xdo('keyup', 'alt')
    yield 1.5


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
        for name, x in (('A', -3.3), ('B', -1.1), ('C', 1.1), ('D', 3.3)):
            bpy.ops.mesh.primitive_cube_add(size=2.0, location=(x, 0.0, 0.0))
            C.active_object.name = 'Box_' + name
            boxes[name] = C.active_object
        bpy.ops.object.select_all(action='DESELECT')
        S.mch_settings.auto_apply = True
        S.mch_cut.depth_mode, S.mch_cut.depth, S.mch_cut.depth_floor = 'SURFACE', 0.3, 'FLAT'
        S.mch_press.size = 40.0
        S.mch_press.shape = 'MCH_BUILTIN_M_OCTAGON'
        S.mch_press.result = 'CUT'
        S.mch_press.grow_edge, S.mch_press.grow_top = 'SHARP', 'FLAT'
        bpy.ops.mch.set_tool(tool='PRESS')
    yield 2.0
    x0 = screen_of((0.0, 0.0, 1.0))[0]
    x1 = screen_of((1.0, 0.0, 1.0))[0]
    ppu = abs(x1 - x0)
    span = 2 * 40.0 / ppu
    log(f'px per unit {ppu:.1f} -> the stamp spans {span:.3f} m')
    v0 = {k: volume(b) for k, b in boxes.items()}
    res = {}
    # A: plain drag -> Base Mesh line
    before = set(bpy.data.objects.keys())
    yield from drag([screen_of((-3.3 - 0.6 + 1.2 * k / 12, 0.0, 1.0)) for k in range(13)])
    new = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before if bpy.data.objects[n].type == 'MESH']
    if new:
        bb = bbox(new[0])
        wy, hz, zlo = bb[1][1] - bb[1][0], bb[2][1] - bb[2][0], bb[2][0]
        log(f'A plain drag: new {new[0].name} width {wy:.3f} height {hz:.3f} bottom z {zlo:.3f} (stamp span {span:.3f}) '
            f'| box changed {abs(v0["A"] - volume(boxes["A"])) > 1e-6}')
        res['A plain drag = Base Mesh line the size of the stamp'] = abs(wy - span) < span * 0.1 and abs(hz - span) < span * 0.15
    else:
        log('A plain drag: nothing made')
        res['A plain drag = Base Mesh line the size of the stamp'] = False
    # B: Alt + drag -> Line Cut
    before = set(bpy.data.objects.keys())
    yield from drag([screen_of((-1.1 - 0.6 + 1.2 * k / 12, 0.0, 1.0)) for k in range(13)], alt=True)
    removed = v0['B'] - volume(boxes['B'])
    exp = (span * 1.2 + math.pi * (span / 2) ** 2) * 0.3
    log(f'B Alt + drag: removed {removed:.3f} (stamp-wide groove = {exp:.3f}) new objects {len(set(bpy.data.objects.keys()) - before)}')
    res['B Alt + drag = Line Cut as wide as the stamp'] = abs(removed - exp) < exp * 0.15 and not (set(bpy.data.objects.keys()) - before)
    # C: plain hold -> Grow
    before = set(bpy.data.objects.keys())
    yield from hold(screen_of((1.1, 0.0, 1.0)), 1.4)
    grown = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before if bpy.data.objects[n].type == 'MESH']
    log(f'C plain hold: grown {[o.name for o in grown]} box changed {abs(v0["C"] - volume(boxes["C"])) > 1e-6}')
    res['C plain hold = a mesh grows out'] = len(grown) == 1 and abs(v0['C'] - volume(boxes['C'])) < 1e-6
    # D: Alt + hold -> Press Cut
    before = set(bpy.data.objects.keys())
    yield from hold(screen_of((3.3, 0.0, 1.0)), 1.4, alt=True)
    removed = v0['D'] - volume(boxes['D'])
    log(f'D Alt + hold: removed {removed:.3f} new objects {len(set(bpy.data.objects.keys()) - before)} closed {closed(boxes["D"])}')
    res['D Alt + hold = the stamp pressed in'] = removed > 0.02 and not (set(bpy.data.objects.keys()) - before)
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
        rv.view_rotation = Euler((1.0, 0.0, 0.0)).to_quaternion()
        rv.view_location = (0.0, 0.3, 0.7)
        rv.view_distance = 8.0
    xdo('mousemove', 960, 1560)
    yield 1.5
    shot('1_gestures_slant_wire.png')
    for k, v in res.items():
        log(('PASS ' if v else 'FAIL ') + k)
    log('RESULT', sum(res.values()), '/', len(res))
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
