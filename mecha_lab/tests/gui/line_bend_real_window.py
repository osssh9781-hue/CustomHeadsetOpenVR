"""Real window (0.24.118 / 0.24.119): how a bend between two pieces drawn from different views looks, with the REAL mouse.
A wide flat stamp (1 x 0.3), three lines on empty space, each: a stroke in the TOP view, then the view turned to the
FRONT and a stroke DOWN from the end:
  A  Each View + Round (radius 1 x)    B  Bend + Round    C  Each View + Sharp
then (0.24.119) D: a click on C's HUD Section dot turns it to Bend; the Bend default is checked.
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
from mecha_lab import line_hud  # noqa: E402

T0 = __import__('time').perf_counter()


def _trace(cls, name, orig, self, *a):
    t = __import__('time').perf_counter() - T0
    extra = ''
    if len(a) >= 2 and hasattr(a[1], 'mouse_region_x'):
        extra = f' at region ({a[1].mouse_region_x}, {a[1].mouse_region_y}) alt={a[1].alt}'
    out = orig(self, *a)
    log(f'  [{t:7.2f}] {cls.__name__}.{name}{extra} -> {str(out)[:80]}')
    return out


def _wrap(cls, name, arity):
    """Blender calls a class's methods with exactly their declared arguments: keep the arity."""
    orig = getattr(cls, name)
    if arity == 1:
        def f(self, a1):
            return _trace(cls, name, orig, self, a1)
    else:
        def f(self, a1, a2):
            return _trace(cls, name, orig, self, a1, a2)
    setattr(cls, name, f)


for _c, _n, _k in ((pc.MCH_OT_press_unified, 'invoke', 2), (pc.MCH_OT_press_unified, '_begin_draw', 2),
                   (pc.MCH_OT_press_unified, '_begin_press', 1), (pc.MCH_OT_press_unified, '_press_to_draw', 2),
                   (pc.MCH_OT_press_unified, '_finish_draw', 2),
                   (line_hud.MCH_GT_line_slider, 'invoke', 2), (line_hud.MCH_GT_line_end, 'invoke', 2),
                   (line_hud.MCH_OT_line_move_toggle, 'execute', 1), (line_hud.MCH_OT_line_corner_toggle, 'execute', 1)):
    _wrap(_c, _n, _k)


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


def closed(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    n = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return n == 0


def ring_turns(ob):
    d = json.loads(ob[base_mesh.SWEEP_KEY])
    nn = len(d['loops'][0])
    co = [v.co.copy() for v in ob.data.vertices]
    rings = [co[i:i + nn] for i in range(0, len(co) - len(co) % nn, nn)]
    worst = 0.0
    for r0, r1 in zip(rings, rings[1:]):
        a, b = (r0[1] - r0[0]), (r1[1] - r1[0])
        if a.length > 1e-9 and b.length > 1e-9:
            worst = max(worst, math.degrees(a.angle(b)))
    return worst, len(rings)


def ui_under(pt):
    """What drawn Mecha UI (the invisible catch gizmo) lies under screen point ``pt``."""
    from mecha_lab import quick_hud, ui_bars, symmetry
    w, a, r = view3d()
    rx, ry = pt[0] - r.x, w.height - pt[1] - r.y
    out = []
    with C.temp_override(window=w, area=a, region=r, region_data=a.spaces.active.region_3d):
        try:
            out.append(('over_ui', quick_hud.over_ui(C, rx, ry)))
            items = ui_bars.drawn_items(C)
            for card, _its in ui_bars._cards(items):
                if card.hit(rx, ry):
                    out.append(('card', type(card).__name__,
                                {k: getattr(card, k, None) for k in getattr(type(card), '__slots__', ()) if k != 'items'}))
            out.append(('sym', symmetry.card_hit(C, rx, ry)[0]))
            out.append(('quick', quick_hud.visible(C) and quick_hud.hit(C, rx, ry)))
        except Exception as ex:
            out.append(('err', repr(ex)[:120]))
    return (rx, ry), out


def drag(points):
    log('  drag', points[0], '->', points[-1], 'move', move_state(), 'under', ui_under(points[0]))
    xdo('mousemove', *points[0])
    yield 0.3
    # the button down and the first moves go to X in one go: a slow Blender frame between them would make the
    # Press tool read the stroke as a hold (= Grow) before the first move arrives
    xdo('mousedown', 1, 'sleep', 0.02, 'mousemove', *points[1], 'sleep', 0.02, 'mousemove', *points[2])
    yield 0.05
    for p in points[3:]:
        xdo('mousemove', *p)
        yield 0.03
    xdo('mouseup', 1)
    yield 1.8


def move_state():
    return bool(getattr(C.window_manager, 'mch_line_move', False))


def hud_px(ob):
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r, region_data=a.spaces.active.region_3d):
        lay = line_hud.layout_for(C, ob)
    return {k: (int(v[0]), int(v[1])) for k, v in lay.items()}


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
        S.mch_press.size = 50.0
        S.mch_press.result = 'CUT'
        S.mch_press.rotation = 0.0
        pc.DRAWN[0] = [[(-0.5, -0.15), (0.5, -0.15), (0.5, 0.15), (-0.5, 0.15)]]
        S.mch_press.drawn = True
        S.mch_base.corner_radius = 1.0
        # the drawn side panel / Layers panel cover the right part of the viewport (a stroke there is a click on
        # the panel): folded away before the strokes
        C.window_manager.mch_layers_min = True
        C.window_manager.mch_side_min = True
        bpy.ops.mch.set_tool(tool='PRESS')
    res = {}
    lines = {}
    dflt = S.mch_base.bl_rna.properties['line_up'].default
    log('default Section:', dflt)
    res['default Section is Bend'] = dflt == 'BEND'
    for name, x0, corner, up in (('A Each View + Round', -7.0, 'ROUND', 'VIEW'), ('B Bend + Round', -2.3, 'ROUND', 'BEND'),
                                 ('C Each View + Sharp', 2.4, 'SHARP', 'VIEW')):
        with C.temp_override(window=w, area=a, region=r):
            S.mch_base.line_corner, S.mch_base.line_up = corner, up
        orbit((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 12.0)
        yield 1.2
        w, a, r = view3d()
        log(name, 'TOP: region', r.x, r.y, r.width, r.height, 'px/unit %.1f' % (screen_of((1.0, 0.0, 0.0))[0] - screen_of((0.0, 0.0, 0.0))[0]),
            'active', C.active_object.name if C.active_object else None,
            'hud', hud_px(C.active_object) if C.active_object and C.active_object.get(base_mesh.SWEEP_KEY) else {})
        before = set(bpy.data.objects.keys())
        yield from drag([screen_of((x0 + 2.0 * k / 8, 0.0, 0.0)) for k in range(9)])
        new = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before if bpy.data.objects[n].type == 'MESH']
        if not new:
            log(name, ': no line made')
            res[name] = False
            continue
        line = new[0]
        orbit((math.pi / 2, 0.0, 0.0), (0.0, 0.0, -0.8), 12.0)     # the front
        yield 1.2
        e = base_mesh.sweep_ends(line)[1]
        s0 = screen_of(e)
        log(name, 'FRONT: end', tuple(round(v, 2) for v in e), 'screen', s0, 'hud', hud_px(line), 'move', move_state())
        pts = [screen_of((e.x, e.y, e.z - 1.8 * k / 8)) for k in range(9)]
        pts[0] = (s0[0] + 2, s0[1] + 2)
        yield from drag(pts)
        d = json.loads(line[base_mesh.SWEEP_KEY])
        worst, nr = ring_turns(line)
        log(f'{name}: {line.name} path {len(d.get("path3", d["path"]))} rings {nr} max ring turn {worst:.1f} deg closed {closed(line)} '
            f'corner {line.mch_base.line_corner} up {line.mch_base.line_up}')
        res[name] = closed(line) and len(d.get('path3', d['path'])) >= 3 and worst < (35.0 if up == 'VIEW' and corner == 'ROUND' else 95.0)
        lines[name] = line
    line = lines.get('C Each View + Sharp')
    if line is not None:                                        # D (0.24.119): C's HUD Section dot - Each View -> Bend
        w, a, r = view3d()
        pos = hud_px(line)
        if 'section' in pos:
            sx, sy = pos['section']
            xdo('mousemove', r.x + sx, w.height - (r.y + sy))
            yield 0.4
            xdo('click', 1)
            yield 1.8
            worst, nr = ring_turns(line)
            log(f'D Section dot click on C at region {pos["section"]}: up {line.mch_base.line_up} rings {nr} '
                f'max ring turn {worst:.1f} deg closed {closed(line)}')
            res['D Section dot: Each View -> Bend (no twist)'] = line.mch_base.line_up == 'BEND' and worst < 5.0 and closed(line)
        else:
            log('D: the HUD has no section slot', pos)
            res['D Section dot: Each View -> Bend (no twist)'] = False
    orbit((1.05, 0.0, 0.5), (-1.3, 0.0, -0.7), 10.5, persp=True)
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.wm.tool_set_by_id(name='builtin.select_box')
        for o in C.selected_objects:
            o.select_set(False)
        C.window_manager.mch_layers_min = True
        C.window_manager.mch_side_min = True
        a.spaces.active.overlay.show_wireframes = True
    xdo('mousemove', 300, 700)
    yield 1.5
    shot('1_bends_three_ways.png')
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
