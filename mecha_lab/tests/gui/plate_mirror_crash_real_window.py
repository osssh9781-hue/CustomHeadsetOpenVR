"""Real window (0.24.132, user: "이 파일에다가 미러하고 플레이트 한 4 개 하면 꺼져" + back01.fbx): the user's parts, the
Mecha Mirror on all of them, then Armor Plates with the real mouse (apply some, mirror some, slider rebuilds) and Creature
Plates - does Blender crash here?  Every step is logged with flush so a crash shows where it died."""
import math
import os
import subprocess
import sys
import time

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'addon'))
OUT = sys.argv[-1]
BLEND = sys.argv[-2]
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, 'log.txt'), 'w')


def log(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    LOG.write(s + '\n')
    LOG.flush()


bpy.ops.wm.open_mainfile(filepath=BLEND)
import mecha_lab  # noqa: E402
from mecha_lab import armor_plate as ap, symmetry, target_rules, tool_state as ts  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402
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


def drag(points):
    xdo('mousemove', *points[0])
    yield 0.3
    xdo('mousedown', 1, 'sleep', 0.12, 'mousemove', *points[1], 'sleep', 0.03, 'mousemove', *points[2])
    yield 0.05
    for p in points[3:]:
        xdo('mousemove', *p)
        yield 0.03
    xdo('mouseup', 1)
    yield 2.0


def circle(cx, cy, r, n=24):
    return [(int(round(cx + r * math.cos(math.tau * k / n))), int(round(cy + r * math.sin(math.tau * k / n)))) for k in range(n)]


def orbit(rot, loc, dist, persp=False):
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        rv = a.spaces.active.region_3d
        rv.view_perspective = 'PERSP' if persp else 'ORTHO'
        rv.view_rotation = Euler(rot).to_quaternion()
        rv.view_location = loc
        rv.view_distance = dist


def top_point(ob):
    """A point on the top surface of ob (a ray from above through its middle), or its origin."""
    dg = C.evaluated_depsgraph_get()
    c = ob.matrix_world @ (sum((Vector(b) for b in ob.bound_box), Vector()) / 8.0)
    o = c + Vector((0, 0, 10.0))
    ok, loc, _n, _i, hit, _m = target_rules.scene_ray(C, dg, o, Vector((0, 0, -1.0)))
    return loc if ok else c


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
    parts = [o for o in S.objects if o.type == 'MESH']
    with C.temp_override(window=w, area=a, region=r):
        a.spaces.active.show_region_ui = False
        a.spaces.active.overlay.show_wireframes = True
        WM.mch_legend_min = True
        S.mch_settings.auto_apply = True
        S.mch_brush.shape = 'STROKE'
        S.mch_brush.line_open = False
        # 1. the Mecha Mirror on every part (as the Mirror button does)
        for o in parts:
            o.select_set(True)
        C.view_layer.objects.active = parts[0]
        for o in parts:
            symmetry._mirror_on(C, o)
    log('1 parts mirrored:', [(o.name, [m.type for m in o.modifiers]) for o in parts][:3], '...')
    centre = sum((o.matrix_world.translation for o in parts), Vector()) / len(parts)
    orbit((0.0, 0.0, 0.0), centre, 3.2)
    yield 1.0
    shot('0_start.png')
    # 2. Armor Plates with the real mouse
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.set_tool(tool='PLATE')
    yield 0.8
    big = sorted(parts, key=lambda o: -len(o.data.vertices))[:4]
    made = 0
    for i in range(6):
        ob = big[i % len(big)]
        p = top_point(ob) + Vector((0.15 * ((i % 3) - 1), 0.1 * ((i // 3) - 0.5), 0.0))
        cx, cy = screen_of(p)
        before = set(bpy.data.objects.keys())
        yield from drag(circle(cx, cy, 34, n=28) + circle(cx, cy, 34, n=28)[:2])
        new = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before if bpy.data.objects[n].type == 'MESH']
        log(f'2 plate {i + 1} on {ob.name} at {(cx, cy)} -> {[(o.name, len(o.data.polygons)) for o in new]} tool {ts.effective_tool(C)}')
        if new:
            made += 1
            plate = new[0]
            if i % 2 == 0:                       # the HUD slider: Face Size rebuild
                with C.temp_override(window=w, area=a, region=r):
                    ok = ap.rebuild_plate(C, plate, 80)
                log('   rebuild_plate 80:', ok)
                yield 0.6
            if i % 3 == 1:                       # mirror the plate too
                with C.temp_override(window=w, area=a, region=r):
                    symmetry._mirror_on(C, plate)
                log('   plate mirrored:', [m.type for m in plate.modifiers])
                yield 0.6
            if i % 2 == 1:                       # Enter = apply the live plate
                focus()
                xdo('key', 'Return')
                yield 1.2
                log('   Return (apply):', ap.plate_source(plate) is None, [m.type for m in plate.modifiers])
        shot(f'2_plate_{i + 1}.png') if i in (1, 5) else None
    # 3. Creature Plates
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.set_tool(tool='CPLATE')
    yield 0.8
    for i in range(3):
        ob = big[(i + 1) % len(big)]
        p = top_point(ob) + Vector((-0.2 + 0.2 * i, 0.15, 0.0))
        cx, cy = screen_of(p)
        before = set(bpy.data.objects.keys())
        yield from drag(circle(cx, cy, 30, n=24) + circle(cx, cy, 30, n=24)[:2])
        new = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before if bpy.data.objects[n].type == 'MESH']
        log(f'3 creature plate {i + 1} on {ob.name} -> {[(o.name, len(o.data.polygons)) for o in new]}')
        if new and i == 1:
            focus()
            xdo('key', 'Return')
            yield 1.0
    # 4. a few undos like a user would
    focus()
    for k in range(3):
        xdo('key', 'ctrl+z')
        yield 1.0
        log(f'4 undo {k + 1}: objects {len(bpy.data.objects)}')
    for k in range(2):
        xdo('key', 'ctrl+shift+z')
        yield 1.0
    log('4 redo x2: objects', len(bpy.data.objects))
    # 5. orbit around (draw handlers run with the plates + mirrors)
    for k in range(4):
        orbit((0.3 * k, 0.0, 0.5 * k), centre, 3.2, persp=True)
        yield 0.5
    shot('5_end.png')
    log(f'DONE: {made} armor plates made, objects {len(bpy.data.objects)}, meshes {len(bpy.data.meshes)}')
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
