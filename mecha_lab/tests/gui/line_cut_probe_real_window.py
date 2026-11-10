"""Real window probe (user: "이거 컷이 안돼" - an S-shaped Press line cannot be cut): draw an S line with the Press
tool (real mouse), then try to cut it with (1) the Cut tool's Free Draw circle, (2) the Press tool's Alt + hold,
(3) the Press tool's Alt + drag (Line Cut) - logging every report and what each operator did.
    blender --window-geometry 0 0 W H --python this.py -- OUT"""
import json
import math
import os
import subprocess
import sys
import time

import bmesh
import bpy

sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/addon')
import mecha_lab  # noqa: E402
from mecha_lab import base_mesh, cut_engine as ce, press_cut as pc, tool_state as ts  # noqa: E402
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

# --- instrumentation: every cut path reports here
CALLS = []
_real_perform_closed = ce.perform_closed


def _pc(context, mode, targets, loops, projector, invert=False):
    t0 = time.perf_counter()
    try:
        msg = _real_perform_closed(context, mode, targets, loops, projector, invert)
        CALLS.append(('perform_closed', mode, [t.name for t in targets], msg[:160], round(time.perf_counter() - t0, 2)))
        return msg
    except Exception as ex:
        CALLS.append(('perform_closed FAILED', mode, [t.name for t in targets], repr(ex)[:200], round(time.perf_counter() - t0, 2)))
        raise


ce.perform_closed = _pc
_real_cut_to = pc.Press.cut_to


def _cut_to(self, context, depth):
    ok = _real_cut_to(self, context, depth)
    CALLS.append(('Press.cut_to', round(depth, 4), ok, str(self.message)[:160]))
    return ok


pc.Press.cut_to = _cut_to
_real_invoke = ce.MCH_OT_cut_stroke.invoke


def _inv(self, context, event):
    r = _real_invoke(self, context, event)
    CALLS.append(('cut_stroke.invoke', self.mode, getattr(self, 'press_lasso', None), sorted(r)))
    return r


ce.MCH_OT_cut_stroke.invoke = _inv
_real_pu_invoke = pc.MCH_OT_press_unified.invoke


def _pu_inv(self, context, event):
    r = _real_pu_invoke(self, context, event)
    CALLS.append(('press_unified.invoke', bool(event.alt), sorted(r)))
    return r


pc.MCH_OT_press_unified.invoke = _pu_inv


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


def drag(points, alt=False, hold_first=0.0):
    xdo('mousemove', *points[0])
    yield 0.3
    if alt:
        xdo('keydown', 'alt')
        yield 0.05
    xdo('mousedown', 1)
    if hold_first:
        yield hold_first
    xdo('sleep', 0.03, 'mousemove', *points[1], 'sleep', 0.03, 'mousemove', *points[2])
    yield 0.05
    for p in points[3:]:
        xdo('mousemove', *p)
        yield 0.03
    xdo('mouseup', 1)
    if alt:
        xdo('keyup', 'alt')
    yield 2.0


def hold(pt, seconds, alt=False):
    xdo('mousemove', *pt)
    yield 0.3
    if alt:
        xdo('keydown', 'alt')
        yield 0.05
    xdo('mousedown', 1)
    yield seconds
    xdo('mouseup', 1)
    if alt:
        xdo('keyup', 'alt')
    yield 2.0


def orbit(rot, loc, dist, persp=False):
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        rv = a.spaces.active.region_3d
        rv.view_perspective = 'PERSP' if persp else 'ORTHO'
        rv.view_rotation = Euler(rot).to_quaternion()
        rv.view_location = loc
        rv.view_distance = dist


def stats(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    r = (len(bm.verts), len(bm.faces), nm, round(bm.calc_volume(signed=True), 4))
    bm.free()
    return r


def dump_calls(tag):
    log(f'--- calls after {tag}:')
    for c in CALLS:
        log('   ', c)
    CALLS.clear()


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
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        a.spaces.active.show_region_ui = False
        a.spaces.active.overlay.show_wireframes = True
        S.cursor.location = (0.0, 0.0, 0.0)
        WM.mch_layers_min = True
        WM.mch_side_min = True
        WM.mch_legend_min = True
        S.mch_settings.auto_apply = True
        pr = S.mch_press
        pr.shape = 'MCH_BUILTIN_M_ROUND_PANEL'
        pr.result = 'CUT'
        pr.draw_mode = 'LINE'
        pr.drawn = False
        pr.size = 24.0
        pr.rotation = 0.0
        S.mch_base.line_corner, S.mch_base.line_up, S.mch_base.line_end = 'ROUND', 'BEND', 'ROUND'
        bpy.ops.mch.set_tool(tool='PRESS')
    res = {}
    orbit((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 12.0)          # top view, like a plan drawing
    yield 1.0
    log('tool', ts.native_tool_id(C), ts.effective_tool(C), 'cut settings', S.mch_cut.depth_mode, S.mch_cut.targets, S.mch_cut.solver, getattr(S.mch_cut, 'gn_finish', None))
    # 1. the S line: a curl, a diagonal, a curl back (world points on z = 0)
    pts3 = [(-2.2 + 1.3 * math.cos(t), 1.2 + 1.3 * math.sin(t), 0.0) for t in (math.radians(d) for d in range(210, 500, 8))]
    pts3 += [(pts3[-1][0] + 0.09 * k, pts3[-1][1] - 0.11 * k, 0.0) for k in range(1, 28, 2)]
    pts3 += [(pts3[-1][0] + 1.3 - 1.3 * math.cos(t), pts3[-1][1] - 1.3 * math.sin(t), 0.0) for t in (math.radians(d) for d in range(0, 230, 8))]
    before = set(bpy.data.objects.keys())
    yield from drag([screen_of(p) for p in pts3])
    new = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before]
    line = next((o for o in new if o.get(base_mesh.SWEEP_KEY)), None)
    dump_calls('the S line')
    if line is None:
        log('NO LINE MADE', [o.name for o in new])
        bpy.ops.wm.quit_blender()
        return
    st0 = stats(line)
    log('1 line', line.name, 'live', line.mch_base.live, st0, 'selected', line.select_get())
    orbit((0.9, 0.0, 0.3), (-0.2, 0.3, 0.0), 12.0, persp=True)     # a slanted view like the user's picture
    yield 1.0
    # 2. the Cut tool: a Free Draw circle across the diagonal part
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.set_tool(tool='CUT')
        S.mch_brush.shape = 'STROKE'
    yield 0.8
    log('2 cut tool', ts.native_tool_id(C), ts.effective_tool(C), 'shape', S.mch_brush.shape, 'sketch', getattr(S.mch_brush, 'sketch_first', None))
    mid = Vector(pts3[len(pts3) // 2])
    circ = [screen_of((mid.x + 0.45 * math.cos(t), mid.y + 0.45 * math.sin(t), 0.0)) for t in (2 * math.pi * k / 28 for k in range(29))]
    yield from drag(circ)
    st1 = stats(line)
    log('   after the Cut tool stroke:', st1, 'live', line.mch_base.live)
    dump_calls('the Cut tool stroke')
    res['2 Cut tool (Free Draw circle) cuts the live S line'] = st1[3] < st0[3] - 1e-4
    # 3. Press tool: Alt + hold on the first curl
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.set_tool(tool='PRESS')
    yield 0.8
    at = screen_of(pts3[8])
    st2a = stats(line)
    yield from hold(at, 1.2, alt=True)
    st2 = stats(line)
    log('3 after Alt + hold:', st2, 'was', st2a)
    dump_calls('Alt + hold')
    res['3 Press tool Alt + hold cuts the live S line'] = st2[3] < st2a[3] - 1e-4
    # 4. Press tool: Alt + drag (Line Cut) across the second curl
    p0 = Vector(pts3[-12])
    seg = [screen_of((p0.x - 0.7 + 1.4 * k / 8, p0.y - 0.6 + 1.2 * k / 8, 0.0)) for k in range(9)]
    st3a = stats(line)
    yield from drag(seg, alt=True)
    st3 = stats(line)
    log('4 after Alt + drag (Line Cut):', st3, 'was', st3a)
    dump_calls('Alt + drag')
    res['4 Press tool Alt + drag (Line Cut) cuts the live S line'] = st3[3] < st3a[3] - 1e-4
    # 5. the same Cut tool stroke after Enter (the line applied)
    focus()
    xdo('key', 'Return')
    yield 1.0
    log('5 after Enter: live', line.mch_base.live, stats(line))
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.set_tool(tool='CUT')
    yield 0.8
    mid2 = Vector(pts3[len(pts3) // 2 + 6])
    circ2 = [screen_of((mid2.x + 0.4 * math.cos(t), mid2.y + 0.4 * math.sin(t), 0.0)) for t in (2 * math.pi * k / 28 for k in range(29))]
    st4a = stats(line)
    yield from drag(circ2)
    st4 = stats(line)
    log('   after the Cut tool stroke (applied line):', st4)
    dump_calls('the Cut tool stroke, applied line')
    res['5 Cut tool after Enter cuts the line'] = st4[3] < st4a[3] - 1e-4
    xdo('mousemove', 300, 820)
    yield 1.0
    shot('1_line_cut_probe.png')
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
