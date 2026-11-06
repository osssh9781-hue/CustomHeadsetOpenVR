"""Real window (0.24.109): going on with a Press Cut line after the view turned, with the REAL mouse and Alt key.
  Box A: plain drag (top view) -> orbit the view -> plain drag from the line's end: ONE object, the path longer
  Box B: Alt + drag (Line Cut, Max 0.15) -> orbit -> Alt + drag from the groove's end: the groove goes on
  Box C: the stamp turned 90 deg (a pentagon): a Base Mesh line and a Line Cut with the turned section
A slanted view with the wireframe on at the end.
    blender --window-geometry 0 0 W H --python this.py -- OUT"""
import json
import math
import os
import subprocess
import sys

import bmesh
import bpy

sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/addon')
import mecha_lab  # noqa: E402
from mecha_lab import base_mesh, press_cut as pc  # noqa: E402

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
    return int(round(r.x + p.x)), int(round(w.height - (r.y + p.y)))


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


def drag(points, alt=False):
    xdo('mousemove', *points[0])
    yield 0.3
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


def orbit(rot, loc, dist):
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        rv = a.spaces.active.region_3d
        from mathutils import Euler
        rv.view_perspective = 'ORTHO'
        rv.view_rotation = Euler(rot).to_quaternion()
        rv.view_location = loc
        rv.view_distance = dist


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
        for name, x in (('A', -3.3), ('B', -1.1), ('C', 1.1)):
            bpy.ops.mesh.primitive_cube_add(size=2.0, location=(x, 0.0, 0.0))
            C.active_object.name = 'Box_' + name
            boxes[name] = C.active_object
        bpy.ops.object.select_all(action='DESELECT')
        S.mch_settings.auto_apply = True
        S.mch_press.size = 36.0
        S.mch_press.shape = 'MCH_BUILTIN_M_OCTAGON'
        S.mch_press.result = 'CUT'
        S.mch_press.max_depth = 0.15
        S.mch_press.rotation = 0.0
        bpy.ops.mch.set_tool(tool='PRESS')
    orbit((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 14.0)
    yield 2.0
    res = {}
    # --- A: a Base Mesh line, the view orbited, the line continued from its end ---------------------------------------
    before = set(bpy.data.objects.keys())
    yield from drag([screen_of((-3.3 - 0.8 + 0.8 * k / 8, -0.3, 1.0)) for k in range(9)])
    new = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before if bpy.data.objects[n].type == 'MESH']
    line = new[0] if new else None
    n_path0 = len(json.loads(line[base_mesh.SWEEP_KEY])['path']) if line is not None and line.get(base_mesh.SWEEP_KEY) else 0
    log(f'A1 plain drag: {[o.name for o in new]} path points {n_path0} remembered {pc.CONTINUE["base"]}')
    orbit((1.0, 0.0, 0.35), (-2.2, -0.2, 0.6), 9.0)             # the user turns the view
    yield 1.5
    ends = base_mesh.sweep_ends(line) if line is not None else None
    n_obj = len(bpy.data.objects)
    if ends:
        e = ends[1]
        s0 = screen_of(e)
        # a stroke from the end on, bending up: in the turned view, towards +x then +y on the box top
        pts = [screen_of((e.x + 0.9 * k / 9, e.y + 0.6 * (k / 9) ** 2, 1.0)) for k in range(10)]
        pts[0] = (s0[0] + 3, s0[1] - 2)                             # (3 px off the end marker, like a real hand)
        yield from drag(pts)
        n_path1 = len(json.loads(line[base_mesh.SWEEP_KEY])['path'])
        ends1 = base_mesh.sweep_ends(line)
        zs = [(line.matrix_world @ v.co).z for v in line.data.vertices]
        log(f'A2 continued (view turned): objects {len(bpy.data.objects) - n_obj:+d} path points {n_path0} -> {n_path1} '
            f'end {tuple(round(c, 2) for c in ends1[1])} z {min(zs):.2f}..{max(zs):.2f} closed {closed(line)}')
        res['A line continued after the view turned: one object, the path longer, still on the first plane'] = \
            len(bpy.data.objects) == n_obj and n_path1 > n_path0 and closed(line) and min(zs) > 0.9 and max(zs) < 1.95
    else:
        log('A2: no line to continue')
        res['A line continued after the view turned: one object, the path longer, still on the first plane'] = False
    # --- B: a Line Cut, the view orbited, the groove continued ------------------------------------------------------
    orbit((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 14.0)
    yield 1.2
    vb0 = volume(boxes['B'])
    before = set(bpy.data.objects.keys())
    yield from drag([screen_of((-1.1 - 0.8 + 0.8 * k / 8, 0.3, 1.0)) for k in range(9)], alt=True)
    vb1 = volume(boxes['B'])
    cutd = pc.CONTINUE['cut']
    log(f'B1 Alt + drag: removed {vb0 - vb1:.3f} new objects {len(set(bpy.data.objects.keys()) - before)} '
        f'remembered cut {cutd is not None and len(cutd["path"])}')
    orbit((1.0, 0.0, -0.3), (-1.0, 0.2, 0.6), 9.0)
    yield 1.5
    if cutd:
        fr = pc._cut_frame(cutd)
        from mathutils import Vector
        e = fr @ Vector((cutd['path'][-1][0], cutd['path'][-1][1], 0.0))
        s0 = screen_of(e)
        pts = [screen_of((e.x + 0.9 * k / 9, e.y - 0.5 * (k / 9) ** 2, 1.0)) for k in range(10)]
        pts[0] = (s0[0] - 2, s0[1] + 3)
        yield from drag(pts, alt=True)
        vb2 = volume(boxes['B'])
        log(f'B2 Alt + drag from the groove\'s end (view turned): removed {vb1 - vb2:.3f} more, path points '
            f'{len(cutd["path"])} -> {len(pc.CONTINUE["cut"]["path"])} new objects {len(set(bpy.data.objects.keys()) - before)} '
            f'closed {closed(boxes["B"])}')
        res['B Line Cut continued after the view turned: more taken out, the box still closed, no new object'] = \
            vb1 - vb2 > 0.02 and closed(boxes['B']) and not (set(bpy.data.objects.keys()) - before) \
            and len(pc.CONTINUE['cut']['path']) > len(cutd['path'])
    else:
        res['B Line Cut continued after the view turned: more taken out, the box still closed, no new object'] = False
    # --- C: the stamp turned 90 deg: a pentagon's section turned on the line and on the cut -------------------------
    orbit((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 14.0)
    yield 1.2
    with C.temp_override(window=w, area=a, region=r):
        S.mch_press.shape = 'MCH_BUILTIN_PENTAGON'
        S.mch_press.rotation = math.pi / 2
    yield 0.5
    before = set(bpy.data.objects.keys())
    yield from drag([screen_of((1.1 - 0.8 + 1.6 * k / 12, -0.45, 1.0)) for k in range(13)])
    new = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before if bpy.data.objects[n].type == 'MESH']
    vc0 = volume(boxes['C'])
    yield from drag([screen_of((1.1 - 0.8 + 1.6 * k / 12, 0.45, 1.0)) for k in range(13)], alt=True)
    vc1 = volume(boxes['C'])
    if new:
        co = [new[0].matrix_world @ v.co for v in new[0].data.vertices]
        wy, hz = max(v.y for v in co) - min(v.y for v in co), max(v.z for v in co) - min(v.z for v in co)
        log(f'C turned stamp: line {new[0].name} width {wy:.3f} height {hz:.3f} | cut removed {vc0 - vc1:.3f} closed {closed(boxes["C"])}')
        res['C the stamp turned 90 deg: the line\'s section taller than wide (a pentagon on its side), the cut made'] = \
            hz > wy * 1.02 and vc0 - vc1 > 0.02 and closed(boxes['C'])
    else:
        log('C: no line made')
        res['C the stamp turned 90 deg: the line\'s section taller than wide (a pentagon on its side), the cut made'] = False
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
        rv.view_rotation = Euler((1.05, 0.0, 0.25)).to_quaternion()
        rv.view_location = (-1.1, -0.3, 0.6)
        rv.view_distance = 8.5
    xdo('mousemove', 960, 1560)
    yield 1.5
    shot('1_line_continue_slant_wire.png')
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
