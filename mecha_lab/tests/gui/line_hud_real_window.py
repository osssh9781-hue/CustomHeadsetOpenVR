"""Real window (0.24.112): the Line HUD with the REAL mouse - a Press line drawn as an L on a box, then the floating
dot next to its end is CLICKED (Sharp -> Round), the Thickness slider is DRAGGED (thicker), the Radius slider dragged;
a slanted view with the wireframe on and the HUD showing at the end.
    blender --window-geometry 0 0 W H --python this.py -- OUT"""
import json
import os
import subprocess
import sys

import bmesh
import bpy

sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/addon')
import mecha_lab  # noqa: E402
from mecha_lab import base_mesh, line_hud  # noqa: E402

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


def win_of_region_px(px):
    w, a, r = view3d()
    return int(round(r.x + px[0])), int(round(w.height - (r.y + px[1])))


def hud_positions(ob):
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r, region_data=a.spaces.active.region_3d):
        lay = line_hud.layout_for(C, ob)
    return {k: win_of_region_px(v) for k, v in lay.items()}


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


def orbit(rot, loc, dist, persp=False):
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        rv = a.spaces.active.region_3d
        from mathutils import Euler
        rv.view_perspective = 'PERSP' if persp else 'ORTHO'
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
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        sp = a.spaces.active
        sp.show_region_ui = False
        bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 0.0))
        C.active_object.name = 'Box'
        bpy.ops.object.select_all(action='DESELECT')
        S.mch_settings.auto_apply = True
        S.mch_press.size = 36.0
        S.mch_press.shape = 'MCH_BUILTIN_M_OCTAGON'
        S.mch_press.result = 'CUT'
        S.mch_press.rotation = 0.0
        S.mch_base.line_corner = 'SHARP'
        S.mch_base.corner_radius = 1.0
        bpy.ops.mch.set_tool(tool='PRESS')
    orbit((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 7.0)
    yield 2.0
    res = {}
    # the L: along x, then on from the end along +y
    before = set(bpy.data.objects.keys())
    yield from drag([screen_of((-0.9 + 1.4 * k / 7, -0.7, 1.0)) for k in range(8)])   # legs 1.4 (a Round bend needs legs > 1.2 x the width)
    new = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before if bpy.data.objects[n].type == 'MESH']
    line = new[0] if new else None
    if line is None:
        log('no line made')
        res['L line'] = False
    else:
        e = base_mesh.sweep_ends(line)[1]
        s0 = screen_of(e)
        pts = [screen_of((e.x, e.y + 1.4 * k / 7, 1.0)) for k in range(8)]
        pts[0] = (s0[0] + 2, s0[1] - 2)
        yield from drag(pts)
        n_path = len(json.loads(line[base_mesh.SWEEP_KEY])['path'])
        log(f'L line: {line.name} path points {n_path} corners {line.mch_base.line_corner} width {line.mch_base.section_width:.3f} closed {closed(line)}')
        res['L line'] = n_path >= 3 and closed(line)
    if line is not None:
        n_sharp = len(line.data.vertices)
        co_sharp = [tuple(v.co) for v in line.data.vertices]
        pos = hud_positions(line)
        log(f'HUD at (window px): {pos}')
        # 1. click the corner dot -> Round
        xdo('mousemove', *pos['corner'])
        yield 0.5
        xdo('click', 1)
        yield 1.5
        log(f'after the dot click: corners {line.mch_base.line_corner} verts {n_sharp} -> {len(line.data.vertices)} closed {closed(line)}')
        res['dot click: Sharp -> Round, the line rebuilt'] = line.mch_base.line_corner == 'ROUND' \
            and [tuple(v.co) for v in line.data.vertices] != co_sharp and closed(line)
        pos = hud_positions(line)
        # 2. drag the Thickness slider 80 px right -> x1.41
        w0 = line.mch_base.section_width
        xdo('mousemove', *pos['thick'])
        yield 0.5
        xdo('mousedown', 1)
        yield 0.1
        for k in range(1, 9):
            xdo('mousemove', pos['thick'][0] + 10 * k, pos['thick'][1])
            yield 0.08
        xdo('mouseup', 1)
        yield 1.5
        log(f'after the thickness drag: width {w0:.3f} -> {line.mch_base.section_width:.3f} height {line.mch_base.height:.3f} closed {closed(line)}')
        res['thickness drag: the line thicker, live'] = line.mch_base.section_width > w0 * 1.25 and closed(line)
        # 3. drag the Radius slider 30 px left -> smaller radius
        pos = hud_positions(line)
        if 'radius' in pos:
            r0 = line.mch_base.corner_radius
            xdo('mousemove', *pos['radius'])
            yield 0.5
            xdo('mousedown', 1)
            yield 0.1
            for k in range(1, 4):
                xdo('mousemove', pos['radius'][0] - 10 * k, pos['radius'][1])
                yield 0.08
            xdo('mouseup', 1)
            yield 1.5
            log(f'after the radius drag: radius {r0:.2f} -> {line.mch_base.corner_radius:.2f} closed {closed(line)}')
            res['radius drag: smaller bend radius, live'] = line.mch_base.corner_radius < r0 - 0.2 and closed(line)
        else:
            res['radius drag: smaller bend radius, live'] = False
    orbit((1.0, 0.0, 0.35), (0.0, 0.0, 0.6), 5.5, persp=True)
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.wm.tool_set_by_id(name='builtin.select_box')     # (the HUD stays with the select tool; no key legend)
        C.window_manager.mch_layers_min = True
        C.window_manager.mch_side_min = True
        a.spaces.active.overlay.show_wireframes = True
    xdo('mousemove', 300, 700)
    yield 1.5
    pos = hud_positions(line) if line is not None else {}
    log(f'HUD at the end (select tool): {pos}')
    shot('1_line_hud_round_thick.png')
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
