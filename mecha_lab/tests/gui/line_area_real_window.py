"""Real window (0.24.108): Line mode strokes that close on themselves, drawn with the REAL mouse (xdotool), Cut tool,
Free Draw shape, From Surface 0.3 deep:
  A: a closed circle stroke, Area off  -> a ring groove (it used to come out as a filled disc, or fail)
  B: the same stroke, Area on          -> the whole disc pocket
  C: Sketch on, four straight strokes forming a square, Area on, Enter -> the whole square pocket
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


def stroke(points):
    """A real drag through screen points."""
    xdo('mousemove', *points[0])
    yield 0.25
    xdo('mousedown', 1)
    yield 0.1
    for p in points[1:]:
        xdo('mousemove', *p)
        yield 0.03
    xdo('mouseup', 1)
    yield 1.8


def circle(cx, cy, r, n=48):
    pts = [screen_of((cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n), 1.0))
           for i in range(n)]
    return pts + pts[:3]            # (closes on itself and runs on a little: the ends overlap)


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
        rv.view_distance = 12.0
        for name, x in (('A', -2.8), ('B', 0.0), ('C', 2.8)):
            bpy.ops.mesh.primitive_cube_add(size=2.4, location=(x, 0.0, 0.0))
            C.active_object.name = 'Box_' + name
            boxes[name] = C.active_object
        bpy.ops.object.select_all(action='DESELECT')
        S.mch_settings.auto_apply = True
        S.mch_cut.depth_mode, S.mch_cut.depth, S.mch_cut.depth_floor = 'SURFACE', 0.3, 'FLAT'
        S.mch_cut.targets = 'AUTO'
        brush = S.mch_brush
        brush.shape = 'STROKE'
        brush.line_mode, brush.line_width, brush.line_caps = True, 0.16, 'ROUND'
        brush.line_area = False
        brush.sketch_first = False
        bpy.ops.mch.set_tool(tool='CUT')
    yield 2.0
    v0 = {k: volume(b) for k, b in boxes.items()}
    brush = C.scene.mch_brush
    # A: closed stroke, Area off
    yield from stroke(circle(-2.8, 0.0, 0.7))
    vA = v0['A'] - volume(boxes['A'])
    log(f'A closed stroke, Area off: removed {vA:.3f} (ring = {math.pi * (0.78 ** 2 - 0.62 ** 2) * 0.3:.3f}, '
        f'disc = {math.pi * 0.78 ** 2 * 0.3:.3f}) closed {closed(boxes["A"])} | objects {len(C.scene.objects)}')
    # B: the same, Area on
    brush.line_area = True
    yield 0.5
    yield from stroke(circle(0.0, 0.0, 0.7))
    vB = v0['B'] - volume(boxes['B'])
    log(f'B closed stroke, Area on: removed {vB:.3f} (disc = {math.pi * 0.78 ** 2 * 0.3:.3f}) closed {closed(boxes["B"])}')
    shot('1_top_A_ring_B_disc.png')
    # C: Sketch, four lines, Area on, Enter
    brush.sketch_first = True
    yield 0.5
    cx, s_ = 2.8, 0.7
    corners = [(cx - s_, -s_), (cx + s_, -s_), (cx + s_, s_), (cx - s_, s_)]
    for i in range(4):
        p0, p1 = corners[i], corners[(i + 1) % 4]
        pts = [screen_of((p0[0] + (p1[0] - p0[0]) * t / 10, p0[1] + (p1[1] - p0[1]) * t / 10, 1.0)) for t in range(11)]
        yield from stroke(pts)
    shot('2_sketch_four_lines.png')
    xdo('key', 'Return')
    yield 2.5
    vC = v0['C'] - volume(boxes['C'])
    side = 2 * s_ + 0.16
    log(f'C sketch of four lines, Area on, Enter: removed {vC:.3f} (square = {side * side * 0.3:.3f}, '
        f'frame only = {(side * side - (2 * s_ - 0.16) ** 2) * 0.3:.3f}) closed {closed(boxes["C"])}')
    brush.sketch_first = False
    brush.line_area = False
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
        rv.view_rotation = Euler((0.9, 0.0, 0.0)).to_quaternion()
        rv.view_location = (0.0, 0.3, 0.9)
        rv.view_distance = 8.5
    xdo('mousemove', 960, 1560)
    yield 1.5
    shot('3_slant_wire.png')
    ok = (abs(vA - math.pi * (0.78 ** 2 - 0.62 ** 2) * 0.3) < 0.08 and abs(vB - math.pi * 0.78 ** 2 * 0.3) < 0.1
          and abs(vC - side * side * 0.3) < 0.12)
    log('RESULT', 'ring / disc / square as expected' if ok else 'NOT as expected', round(vA, 3), round(vB, 3), round(vC, 3))
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
