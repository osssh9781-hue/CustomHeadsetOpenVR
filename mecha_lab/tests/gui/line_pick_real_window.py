"""Real window (0.24.121): the pentagon L corner, and the new line HUD bits with the REAL mouse.
  1. a pentagon stamp (drawn), Sharp + Bend: a stroke right, then a one-stroke L from its end -> no notch at the corners
  2. a straight line: Pick on -> press on the line's MIDDLE and drag up (a new joint, a V) -> Pick off -> the blue ring
     stays and drags again (Move off) -> Ends dot -> Round -> Detail slider drag -> more rings
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
from mecha_lab import base_mesh, line_hud, press_cut as pc  # noqa: E402
from mathutils import Vector  # noqa: E402

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
PENT = [[(0.5 * math.cos(math.tau * k / 5 + math.pi / 2), 0.5 * math.sin(math.tau * k / 5 + math.pi / 2)) for k in range(5)]]


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


def win_of_region(px):
    w, a, r = view3d()
    return int(round(r.x + px[0])), int(round(w.height - (r.y + px[1])))


def closed(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    n = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return n == 0


def ring_folds(ob):
    d = json.loads(ob[base_mesh.SWEEP_KEY])
    nn = len(d['loops'][0])
    co = [v.co.copy() for v in ob.data.vertices]
    rings = [co[i:i + nn] for i in range(0, len(co) - len(co) % nn, nn)]
    cents = [sum(r, Vector()) / len(r) for r in rings]
    folds = 0
    for i in range(len(rings) - 1):
        t = cents[i + 1] - cents[i]
        if t.length < 1e-9:
            continue
        t.normalize()
        if any((rings[i + 1][k] - rings[i][k]).dot(t) < -1e-6 for k in range(nn)):
            folds += 1
    return folds, len(rings)


def hud_px(ob):
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r, region_data=a.spaces.active.region_3d):
        lay = line_hud.layout_for(C, ob)
    return {k: (int(v[0]), int(v[1])) for k, v in lay.items()}


def drag(points):
    xdo('mousemove', *points[0])
    yield 0.3
    xdo('mousedown', 1, 'sleep', 0.02, 'mousemove', *points[1], 'sleep', 0.02, 'mousemove', *points[2])
    yield 0.05
    for p in points[3:]:
        xdo('mousemove', *p)
        yield 0.03
    xdo('mouseup', 1)
    yield 1.8


def click(pt):
    xdo('mousemove', *pt)
    yield 0.4
    xdo('click', 1)
    yield 1.2


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
        a.spaces.active.show_region_ui = False
        S.cursor.location = (0.0, 0.0, 0.0)
        S.mch_settings.auto_apply = True
        S.mch_press.size = 33.6
        S.mch_press.result = 'CUT'
        S.mch_press.rotation = 0.0
        pc.DRAWN[0] = PENT
        S.mch_press.drawn = True
        S.mch_base.line_corner, S.mch_base.line_up, S.mch_base.corner_radius = 'SHARP', 'BEND', 1.0
        C.window_manager.mch_layers_min = True
        C.window_manager.mch_side_min = True
        bpy.ops.mch.set_tool(tool='PRESS')
    res = {}
    orbit((0.0, 0.0, 0.0), (-1.0, 1.0, 0.0), 12.0)
    yield 1.2
    # 1. the pentagon L: a stroke right, then a one-stroke L up and right from its end
    before = set(bpy.data.objects.keys())
    yield from drag([screen_of((-7.0 + 2.0 * k / 8, 1.5, 0.0)) for k in range(9)])
    new = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before if bpy.data.objects[n].type == 'MESH']
    line_l = new[0] if new else None
    if line_l is not None:
        e = base_mesh.sweep_ends(line_l)[1]
        s0 = screen_of(e)
        pts = [screen_of((e.x, e.y + 1.5 * k / 6, e.z)) for k in range(7)] + [screen_of((e.x + 1.6 * k / 6, e.y + 1.5, e.z)) for k in range(1, 7)]
        pts[0] = (s0[0] + 2, s0[1] - 2)
        yield from drag(pts)
        folds, nr = ring_folds(line_l)
        d = json.loads(line_l[base_mesh.SWEEP_KEY])
        log(f'1 pentagon L: {line_l.name} path {len(d.get("path3") or d["path"])} rings {nr} folds {folds} closed {closed(line_l)} '
            f'width {line_l.mch_base.section_width:.3f} corner {line_l.mch_base.line_corner} up {line_l.mch_base.line_up}')
        res['1 pentagon L: two clean mitres, no notch (no ring folded back), closed'] = folds == 0 and closed(line_l) and len(d.get('path3') or d['path']) >= 3
    else:
        log('1: no line made')
        res['1 pentagon L: two clean mitres, no notch (no ring folded back), closed'] = False
    # 2. a straight line for Pick / Ends / Detail
    with C.temp_override(window=w, area=a, region=r):
        S.mch_press.drawn = False
        S.mch_press.shape = 'MCH_BUILTIN_M_OCTAGON'
        for o in C.selected_objects:
            o.select_set(False)
    yield 0.5
    before = set(bpy.data.objects.keys())
    yield from drag([screen_of((-1.5 + 4.0 * k / 10, -1.0, 0.0)) for k in range(11)])
    new = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before if bpy.data.objects[n].type == 'MESH']
    line = new[0] if new else None
    if line is not None:
        pos = hud_px(line)
        log('2 line', line.name, 'hud', pos, 'pick flag', C.window_manager.mch_line_pick)
        # Pick on
        yield from click(win_of_region(pos['pick']))
        log('   Pick flag after the dot:', C.window_manager.mch_line_pick)
        # press on the middle of the line and drag up 90 px
        mid = screen_of((0.5, -1.0, 0.0))
        yield from drag([mid, (mid[0], mid[1] - 12), (mid[0], mid[1] - 24), (mid[0], mid[1] - 45), (mid[0], mid[1] - 70), (mid[0], mid[1] - 90)])
        d = json.loads(line[base_mesh.SWEEP_KEY])
        js = base_mesh.sweep_joints(line)
        log(f'   after the Pick drag: path {[tuple(round(c, 2) for c in q) for q in d["path"]]} joints {d.get("joints")} rings {len(js)} closed {closed(line)}')
        res['2a Pick: pressed on the middle of the line and dragged - a new joint there, the line bent into a V, closed'] = \
            len(d['path']) == 3 and len(js) == 1 and abs(js[0][1].x - 0.5) < 0.15 and js[0][1].y > -0.6 and closed(line)
        # Pick off: the ring stays; drag it again (Move off)
        pos = hud_px(line)
        yield from click(win_of_region(pos['pick']))
        js = base_mesh.sweep_joints(line)
        log('   Pick off: flag', C.window_manager.mch_line_pick, 'joint rings', len(js))
        if js:
            w_, a_, r_ = view3d()
            with C.temp_override(window=w_, area=a_, region=r_, region_data=a_.spaces.active.region_3d):
                jpx = line_hud.joint_handles_px(C, line)
            if jpx:
                jx, jy = win_of_region(jpx[0][0])
                yield from drag([(jx, jy), (jx + 12, jy), (jx + 24, jy), (jx + 40, jy), (jx + 55, jy), (jx + 70, jy)])
                js2 = base_mesh.sweep_joints(line)
                log(f'   joint ring dragged after Pick off: {tuple(round(c, 2) for c in js[0][1])} -> {tuple(round(c, 2) for c in js2[0][1])} closed {closed(line)}')
                res['2b Pick off: the new ring stays and drags again (Move off)'] = not C.window_manager.mch_line_pick \
                    and (js2[0][1] - js[0][1]).length > 0.25 and closed(line)
            else:
                res['2b Pick off: the new ring stays and drags again (Move off)'] = False
        else:
            res['2b Pick off: the new ring stays and drags again (Move off)'] = False
        # Ends -> Round
        pos = hud_px(line)
        n_flat = len(line.data.vertices)
        yield from click(win_of_region(pos['ends']))
        log(f'   Ends dot: {line.mch_base.line_end} verts {n_flat} -> {len(line.data.vertices)} closed {closed(line)}')
        res['2c Ends dot: Flat -> Round, domes on both ends, closed'] = line.mch_base.line_end == 'ROUND' and len(line.data.vertices) > n_flat and closed(line)
        # Detail slider
        pos = hud_px(line)
        if 'detail' in pos:
            dx, dy = win_of_region(pos['detail'])
            n_d1, d1 = len(line.data.vertices), line.mch_base.line_detail
            yield from drag([(dx, dy), (dx + 10, dy), (dx + 20, dy), (dx + 40, dy), (dx + 65, dy), (dx + 90, dy), (dx + 110, dy)])
            log(f'   Detail slider: {d1:.2f} -> {line.mch_base.line_detail:.2f}, verts {n_d1} -> {len(line.data.vertices)} closed {closed(line)}')
            res['2d Detail slider: more rings along the line, live'] = line.mch_base.line_detail > d1 * 1.3 and len(line.data.vertices) > n_d1 and closed(line)
        else:
            res['2d Detail slider: more rings along the line, live'] = False
    else:
        log('2: no line made')
        for k in ('2a Pick: pressed on the middle of the line and dragged - a new joint there, the line bent into a V, closed',
                  '2b Pick off: the new ring stays and drags again (Move off)', '2c Ends dot: Flat -> Round, domes on both ends, closed',
                  '2d Detail slider: more rings along the line, live'):
            res[k] = False
    orbit((1.05, 0.0, 0.45), (-1.5, 0.3, -0.6), 11.0, persp=True)     # both lines in view, the HUD column clear of the toolbar
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.wm.tool_set_by_id(name='builtin.select_box')
        for o in C.selected_objects:
            o.select_set(False)
        if line is not None:
            line.select_set(True)
            C.view_layer.objects.active = line
        a.spaces.active.overlay.show_wireframes = True
    xdo('mousemove', 300, 700)
    yield 1.5
    shot('1_pentagon_l_pick_ends.png')
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
