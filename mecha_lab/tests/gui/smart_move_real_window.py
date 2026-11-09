"""Real window (0.24.123): Smart Move with the REAL mouse.
  1. the Smart Move tool on, LMB on the tilted part -> it is held (the operator runs, the part selected)
  2. LMB on the slab -> the part's origin is at that point, its rotation and size unchanged
  3. Lift 0.2 + LMB on the ramp -> the origin 0.2 off the ramp along its normal
  4. a 3D-mouse twist (a fake NDOF event through the running operator's own modal - no device here) -> 9 deg about the
     origin, the origin stays
  5. Return -> the hold ends, the part stays;  then LMB part, LMB slab elsewhere, Escape -> the part is back
A screenshot while the part is held (ring + name + hit mark), wireframe on.
    blender --window-geometry 0 0 W H --python this.py -- OUT"""
import math
import os
import subprocess
import sys
import types

import bpy

sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/addon')
import mecha_lab  # noqa: E402
from mecha_lab import smart_move as sm, tool_state as ts  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402

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
    p = location_3d_to_region_2d(r, a.spaces.active.region_3d, Vector(co))
    return int(round(r.x + p.x)), int(round(w.height - (r.y + p.y)))


def click(pt):
    xdo('mousemove', *pt)
    yield 0.4
    xdo('click', 1)
    yield 1.0


def orbit(rot, loc, dist, persp=False):
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        rv = a.spaces.active.region_3d
        rv.view_perspective = 'PERSP' if persp else 'ORTHO'
        rv.view_rotation = Euler(rot).to_quaternion()
        rv.view_location = loc
        rv.view_distance = dist


def same_rot(m1, m2, tol=1e-4):
    return all(abs(a - b) < tol for ra, rb in zip(m1.to_3x3(), m2.to_3x3()) for a, b in zip(ra, rb))


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
        a.spaces.active.overlay.show_wireframes = True
        S.cursor.location = (0.0, 0.0, 0.0)
        C.window_manager.mch_layers_min = True
        C.window_manager.mch_side_min = True
        bpy.ops.mesh.primitive_cube_add(size=1)
        slab = C.active_object
        slab.name = 'Slab'
        slab.scale = (12, 12, 0.6)
        slab.location = (0, 0, -0.3)
        bpy.ops.mesh.primitive_cube_add(size=1)
        ramp = C.active_object
        ramp.name = 'Ramp'
        ramp.scale = (3, 3, 0.4)
        ramp.rotation_euler = (0, math.radians(-30), 0)
        ramp.location = (-3.0, 2.0, 1.0)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(3.0, -1.0, 2.0))
        part = C.active_object
        part.name = 'Part'
        part.rotation_euler = (math.radians(20), 0, math.radians(35))
        part.scale = (1.0, 1.6, 0.6)
        for o in (slab, ramp, part):
            o.select_set(False)
        S.mch_smart.axes, S.mch_smart.speed, S.mch_smart.lift, S.mch_smart.push = 'VIEW', 1.0, 0.0, 'OFF'
        bpy.ops.mch.set_tool(tool='SMART')
    C.view_layer.update()
    res = {}
    orbit((1.0, 0.0, 0.6), (0.0, 0.5, 0.5), 16.0, persp=True)
    yield 1.2
    log('tool', ts.native_tool_id(C), ts.effective_tool(C))
    m0 = part.matrix_world.copy()
    # 1. hold the part
    yield from click(screen_of(part.matrix_world.translation))
    op = sm.ACTIVE[0]
    log('1 held:', None if op is None else op.ob_name, 'selected', part.select_get(), 'active', C.view_layer.objects.active.name)
    res['1 LMB on the part: it is held (the operator runs on it, the part selected)'] = op is not None and op.ob_name == 'Part' and part.select_get()
    # 2. put it on the slab
    p1 = Vector((-1.5, -2.5, 0.0))
    yield from click(screen_of(p1))
    t = part.matrix_world.translation
    log(f'2 slab: origin {tuple(round(c, 3) for c in t)} wanted {tuple(p1)} rot same {same_rot(part.matrix_world, m0)} scale {tuple(round(c, 3) for c in part.matrix_world.to_scale())}')
    res['2 LMB on the slab: the origin is at that point, rotation and size unchanged'] = (t - p1).length < 0.03 and same_rot(part.matrix_world, m0)
    # 3. Lift + the ramp
    S.mch_smart.lift = 0.2
    top = ramp.matrix_world @ Vector((0.1, -0.1, 0.5))
    nrm = (ramp.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
    yield from click(screen_of(top))
    t = part.matrix_world.translation
    off = t - top
    loc = ramp.matrix_world.inverted() @ t          # in the ramp's own space: the top face is z = 0.5, 0.2 world = 0.5 local
    log(f'3 ramp: origin {tuple(round(c, 3) for c in t)} off the aimed point {off.length:.3f}; in the ramp\'s space {tuple(round(c, 3) for c in loc)} '
        f'(top face z 0.5 + lift 0.5) normal {tuple(round(c, 3) for c in nrm)} rot same {same_rot(part.matrix_world, m0)}')
    res['3 Lift 0.2 + LMB on the ramp: the origin 0.2 off the ramp top along its normal, rotation unchanged'] = \
        abs(loc.z - 1.0) < 0.02 and abs(loc.x) < 0.5 and abs(loc.y) < 0.5 and off.length < 0.3 and same_rot(part.matrix_world, m0)
    S.mch_smart.lift = 0.0
    shot('1_smart_move_held.png')
    # 4. a 3D-mouse twist through the operator's own modal (fake event; no device here)
    before = part.matrix_world.copy()
    w, a, r = view3d()
    rv = a.spaces.active.region_3d
    ev = types.SimpleNamespace(type='NDOF_MOTION', value='NOTHING', mouse_region_x=100, mouse_region_y=100, shift=False, alt=False, ctrl=False,
                               ndof_motion=types.SimpleNamespace(rotation=Vector((0.0, 0.25, 0.0)), translation=Vector((0.0, 0.0, 0.0)), time_delta=0.1))
    with C.temp_override(window=w, area=a, region=r, region_data=rv):
        ret = sm.ACTIVE[0].modal(C, ev) if sm.ACTIVE[0] is not None else None
    after = part.matrix_world
    turn = (after.to_3x3() @ before.to_3x3().inverted()).to_quaternion()
    up = (rv.view_matrix.to_3x3().inverted() @ Vector((0, 1, 0))).normalized()
    log(f'4 ndof: {ret} turned {math.degrees(turn.angle):.2f} deg about {tuple(round(c, 3) for c in turn.axis)} (view up {tuple(round(c, 3) for c in up)}) '
        f'origin moved {(after.translation - before.translation).length:.5f}')
    res['4 3D-mouse twist (fake event, the same code path): 9 deg about the view up axis through the ORIGIN, the origin stays'] = \
        ret == {'RUNNING_MODAL'} and abs(math.degrees(turn.angle) - 9.0) < 0.1 and abs(abs(turn.axis.dot(up)) - 1.0) < 1e-3 \
        and (after.translation - before.translation).length < 1e-5
    yield 0.5
    # 5. Return keeps; then hold again, move, Escape puts back
    kept = part.matrix_world.copy()
    focus()
    xdo('key', 'Return')
    yield 1.0
    same = (part.matrix_world.translation - kept.translation).length < 1e-4 and same_rot(part.matrix_world, kept)
    log('5 Return: running', sm.ACTIVE[0] is not None, 'same', same)
    ok5 = sm.ACTIVE[0] is None and same
    yield from click(screen_of(part.matrix_world.translation))
    held = sm.ACTIVE[0] is not None
    p2 = Vector((2.5, 2.0, 0.0))
    yield from click(screen_of(p2))
    moved = (part.matrix_world.translation - p2).length < 0.03
    focus()
    xdo('key', 'Escape')
    yield 1.0
    back = (part.matrix_world.translation - kept.translation).length < 1e-4 and same_rot(part.matrix_world, kept)
    log('   Escape: held again', held, 'moved to the slab', moved, 'back', back, tuple(round(c, 4) for c in part.matrix_world.translation),
        tuple(round(c, 4) for c in kept.translation), 'running', sm.ACTIVE[0] is not None)
    res['5 Return keeps (the hold ends, the part stays); hold again + move + Escape puts it back'] = ok5 and held and moved and back and sm.ACTIVE[0] is None
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
