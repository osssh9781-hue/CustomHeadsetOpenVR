"""Real window (0.24.132, user crash logs: plates on a mirrored sphere, then EXCEPTION_ACCESS_VIOLATION while the drawn
UI rebuilt its items on a mouse move; "컨트롤 제트 하면 꺼지는 것도 있네"): a dense sphere with the Mecha Mirror, Creature
and Armor Plates drawn with the real mouse, the mouse swept over the drawn UI between strokes, Ctrl+Z / Ctrl+Shift+Z
mixed in.  Every step is logged (flushed) so a crash shows the last step.  MCH_ADDON (env) picks the add-on folder, so
the same run can be made against an older build."""
import faulthandler
import math
import os
import subprocess
import sys
import time

import bpy

ADDON = os.environ.get('MCH_ADDON') or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'addon')
sys.path.insert(0, ADDON)
OUT = sys.argv[-1]
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, 'log.txt'), 'w')


def log(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    LOG.write(s + '\n')
    LOG.flush()
    os.fsync(LOG.fileno())


faulthandler.enable(file=open(os.path.join(OUT, 'fault.txt'), 'w'), all_threads=False)   # a crash: the Python frames
PROF = None
if os.environ.get('MCH_PROFILE'):
    import cProfile
    PROF = cProfile.Profile()


import mecha_lab  # noqa: E402
from mecha_lab import symmetry, tool_state as ts  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402
mecha_lab.register()
C = bpy.context
log('add-on from', os.path.dirname(mecha_lab.__file__), 'version', mecha_lab.bl_info.get('version'))
ROUNDS = int(os.environ.get('MCH_ROUNDS', '18'))


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


def screen_of(co):
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    w, a, r = view3d()
    p = location_3d_to_region_2d(r, a.spaces.active.region_3d, Vector(co))
    return int(round(r.x + p.x)), int(round(w.height - (r.y + p.y)))


def drag(points):
    xdo('mousemove', *points[0])
    yield 0.25
    xdo('mousedown', 1, 'sleep', 0.1, 'mousemove', *points[1], 'sleep', 0.03, 'mousemove', *points[2])
    yield 0.05
    for p in points[3:]:
        xdo('mousemove', *p)
        yield 0.02
    xdo('mouseup', 1)
    yield 1.2


def circle(cx, cy, r, n=24):
    return [(int(round(cx + r * math.cos(math.tau * k / n))), int(round(cy + r * math.sin(math.tau * k / n)))) for k in range(n)]


def sweep_ui():
    """The mouse over the drawn bars (top bar, side panel, bottom menu): every move rebuilds / reads the UI items."""
    w, a, r = view3d()
    pts = [(r.x + 300, w.height - r.y - r.height + 60), (r.x + r.width // 2, w.height - r.y - r.height + 70),
           (r.x + r.width - 200, w.height - r.y - r.height + 200), (r.x + r.width // 2, w.height - r.y - 120),
           (r.x + 200, w.height - r.y - 300)]
    for p in pts:
        xdo('mousemove', *p)
        yield 0.12


def orbit(rot, loc, dist):
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        rv = a.spaces.active.region_3d
        rv.view_perspective = 'ORTHO'
        rv.view_rotation = Euler(rot).to_quaternion()
        rv.view_location = loc
        rv.view_distance = dist


def set_tool(tool):
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.set_tool(tool=tool)
        C.scene.mch_brush.shape = 'STROKE'          # (after the tool switch: each tool remembers its own lasso)
        C.scene.mch_brush.line_open = False


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
        WM.mch_legend_min = True
        S.mch_settings.auto_apply = True
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.5, segments=64, ring_count=32, location=(0, 0, 0))
        body = C.active_object
        body.name = 'PM3D_Sphere3D_1'
        body.data.remesh_voxel_size = mecha_lab.voxel_for_points(C, body, int(os.environ.get('MCH_POINTS', '150000')))
        bpy.ops.object.voxel_remesh()
        symmetry._mirror_on(C, body)
        WM.mch_sym_card = ''
        if os.environ.get('MCH_RADIAL') == '1':              # what the Symmetry card's Radial button does
            symmetry.set_mode(C, body, 'RADIAL')
    log('body', len(body.data.vertices), 'verts, mods', [m.type for m in body.modifiers], 'radial on',
        getattr(S.mch_rsym, 'active', None))
    if PROF is not None:
        PROF.enable()
    T0 = time.perf_counter()
    orbit((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 4.5)
    yield 1.0
    step = 0
    RADIAL = os.environ.get('MCH_RADIAL') == '1'
    from mecha_lab import quick_hud

    def clear_of_ui(cx, cy, rad):
        w_, a_, r_ = view3d()
        with C.temp_override(window=w_, area=a_, region=r_):
            for k in range(12):
                px = cx + rad * math.cos(math.tau * k / 12) - r_.x
                py = (w_.height - cy - rad * math.sin(math.tau * k / 12)) - r_.y
                if quick_hud.over_ui(C, px, py):
                    return False
        return True

    for rnd in range(ROUNDS):
        S = C.scene                                      # (fresh each round: Ctrl+Z re-reads the scene)
        tool = 'PLATE' if rnd % 3 == 2 else 'CPLATE'
        set_tool(tool)
        with C.temp_override(window=w, area=a, region=r):
            WM.mch_sym_card = ''                         # (the Symmetry card stays shut: strokes on the mesh only)
            if not RADIAL and getattr(S.mch_rsym, 'active', False):
                log('   (radial got switched on - off again)')
                S.mch_rsym.active = False
        yield 0.4
        rad = 30 + 6 * (rnd % 3)
        for tries in range(24):
            ang = rnd * 0.9 + tries * 0.55
            rr = 0.35 + 0.08 * (tries % 6)
            p = Vector((rr * math.cos(ang) - 0.25, rr * math.sin(ang) + 0.25, 1.4))
            cx, cy = screen_of(p)
            if clear_of_ui(cx, cy, rad + 8):
                break
        n0 = len(bpy.data.objects)
        t_r = time.perf_counter()
        yield from drag(circle(cx, cy, rad, n=26) + circle(cx, cy, rad, n=26)[:2])
        step += 1
        log(f'{step:02d} round {rnd + 1} {tool} at {(cx, cy)}: objects {n0} -> {len(bpy.data.objects)}, tool {ts.effective_tool(C)}, '
            f'radial {getattr(C.scene.mch_rsym, "active", None)}, drag+make {time.perf_counter() - t_r:.1f}s, total {time.perf_counter() - T0:.0f}s')
        if rnd == 0:
            shot('round1.png')
        yield from sweep_ui()
        if rnd % 4 == 3:                                     # undo twice, redo once
            focus()
            for k in ('ctrl+z', 'ctrl+z', 'ctrl+shift+z'):
                xdo('key', k)
                yield 1.0
                yield from sweep_ui()
                log(f'   {k}: objects {len(bpy.data.objects)}')
        if rnd % 5 == 4:                                     # Enter applies the live plate
            focus()
            xdo('key', 'Return')
            yield 0.8
            log('   Return (apply)')
    shot('end.png')
    log(f'DONE: {step} strokes, objects {len(bpy.data.objects)}, meshes {len(bpy.data.meshes)}, {time.perf_counter() - T0:.0f}s')
    if PROF is not None:
        PROF.disable()
        import io
        import pstats
        buf = io.StringIO()
        pstats.Stats(PROF, stream=buf).sort_stats('cumulative').print_stats(45)
        open(os.path.join(OUT, 'profile.txt'), 'w').write(buf.getvalue())
        buf = io.StringIO()
        pstats.Stats(PROF, stream=buf).sort_stats('tottime').print_stats(30)
        open(os.path.join(OUT, 'profile_tottime.txt'), 'w').write(buf.getvalue())
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
