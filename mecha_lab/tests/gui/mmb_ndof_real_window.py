"""Real window (0.24.153, user: "왜 갑자기 중간 클릭으로 화면이 안 돌아가?" ... "3D 마우스 연결이 이상했나 봐"): a 3D mouse
with a bad connection sends motion events all the time; the middle mouse must still turn the view (drag) and open the
Mecha Menu (click) in MECHA LAB.

Blender started with --enable-event-simulate: every event below is made with Window.event_simulate (real 3D-mouse
events cannot be made with xdotool; a simulated NDOF_MOTION carries no motion of its own, so it does not turn the view
itself - checked in B; Blender's own 3D-mouse operators would read that missing motion and crash, so the add-on's
3D-mouse key, after the gate, counts each one and keeps it from them).  The gestures, in the 3D view's empty space:

  A. a middle click, no 3D mouse                  -> the Mecha Menu
  B. a middle click, the 3D mouse sending motion  -> the Mecha Menu, the view not turned
  C. a middle drag, the 3D mouse sending motion   -> the view turns, no menu, nothing left waiting
  D. a middle drag, no 3D mouse                   -> the view turns
  E. Blender's own 3D-mouse settings (Preferences > Input > NDOF) the same as before the add-on was turned on

    MCH_ADDON_DIR=<an older add-on's parent folder> to run it on another version (0.24.152: C fails).
"""
import math
import os
import sys

import bpy

ADDON = os.environ.get('MCH_ADDON_DIR') or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'addon')
sys.path.insert(0, ADDON)
import mecha_lab  # noqa: E402
from mecha_lab import mecha_menu as mm, smart_move  # noqa: E402
from mathutils import Euler  # noqa: E402

OUT = sys.argv[-1]
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, 'log.txt'), 'w')


def log(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    LOG.write(s + '\n')
    LOG.flush()


C = bpy.context
INP = C.preferences.inputs
NDOF_KEYS = [p.identifier for p in INP.bl_rna.properties if p.identifier.startswith('ndof_')
             and p.type in {'BOOLEAN', 'FLOAT', 'INT', 'ENUM'} and not getattr(p, 'is_array', False)]
PREFS_BEFORE = {k: getattr(INP, k) for k in NDOF_KEYS}      # Blender's 3D-mouse settings before the add-on is on
mecha_lab.register()
log('add-on from', os.path.abspath(mecha_lab.__file__))

# how many 3D-mouse events reached the add-on's own 3D-mouse key (after the middle-click gate passed them on)
SEEN = {'ndof': 0}
_orig_invoke = smart_move.MCH_OT_smart_ndof.invoke


def _counting_invoke(self, context, event):
    SEEN['ndof'] += 1
    _orig_invoke(self, context, event)          # (3D MOUSE: View - it passes it on)
    return {'FINISHED'}                         # a simulated event: no motion data for Blender's own operators


smart_move.MCH_OT_smart_ndof.invoke = _counting_invoke


def view3d():
    for w in C.window_manager.windows:
        for a in w.screen.areas:
            if a.type == 'VIEW_3D':
                return w, a, next(r for r in a.regions if r.type == 'WINDOW')
    return None, None, None


def rot_now():
    w, a, r = view3d()
    return a.spaces.active.region_3d.view_rotation.copy()


def modal_names():
    w, a, r = view3d()
    try:
        return [op.bl_idname for op in w.modal_operators]
    except (AttributeError, RuntimeError):
        return ['?']


def sim(t, v='NOTHING', x=0, y=0):
    w, a, r = view3d()
    w.event_simulate(type=t, value=v, x=int(x), y=int(y))


def gesture(x0, y0, drag, ndof, steps=10):
    """A middle press at (x0, y0), ``steps`` ticks (3D-mouse motion events in each when ``ndof``; the mouse 22 px on
    each tick when ``drag``), the release."""
    sim('MOUSEMOVE', x=x0, y=y0)
    yield 0.2
    sim('MIDDLEMOUSE', 'PRESS', x0, y0)
    yield 0.1
    x = x0
    for _i in range(steps):
        if ndof:
            for _k in range(5):
                sim('NDOF_MOTION', x=x, y=y0)
        yield 0.05
        if drag:
            x += 22
            sim('MOUSEMOVE', x=x, y=y0 + 2)
        yield 0.05
    sim('MIDDLEMOUSE', 'RELEASE', x, y0 + 2)
    yield 0.6


def close_menu(x, y):
    if mm._OPEN[0]:
        sim('ESC', 'PRESS', x, y)
        yield 0.1
        sim('ESC', 'RELEASE', x, y)
        yield 0.6


def flow():
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        ws = next((x for x in bpy.data.workspaces if x.name.startswith('MECHA LAB')), None)
        if ws is None:
            bpy.ops.mch.workspace_open()
            ws = next((x for x in bpy.data.workspaces if x.name.startswith('MECHA LAB')), None)
        w.workspace = ws
    yield 2.0
    w, a, r = view3d()
    sp3 = a.spaces.active
    with C.temp_override(window=w, area=a, region=r):
        for o in list(C.scene.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(0, 0, 0))
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((1.2, 0.0, 0.3)).to_quaternion()
        rv.view_location = (0.0, 0.0, 0.0)
        rv.view_distance = 8.0
        sp3.show_region_ui = False
    yield 1.5
    # empty space: left of the sphere, above the bottom bar, clear of the side panel
    x0, y0 = r.x + r.width * 0.25, r.y + r.height * 0.62
    log('3D view', r.width, 'x', r.height, '- gestures at', int(x0), int(y0), '(window pixels)')
    res = {}

    def turned(q0):
        return math.degrees(q0.rotation_difference(rot_now()).angle)

    # A
    q0, n0 = rot_now(), SEEN['ndof']
    yield from gesture(x0, y0, drag=False, ndof=False)
    log('A click, no 3D mouse: menu open', mm._OPEN[0], '- view turned', round(turned(q0), 2), 'deg')
    res['A a middle click opens the Mecha Menu'] = mm._OPEN[0]
    yield from close_menu(x0, y0)
    # B
    q0, n0 = rot_now(), SEEN['ndof']
    yield from gesture(x0, y0, drag=False, ndof=True)
    nb = SEEN['ndof'] - n0
    tb = turned(q0)
    log('B click, 3D mouse sending: menu open', mm._OPEN[0], '- view turned', round(tb, 2), 'deg -', nb,
        '3D-mouse events passed on to the keys')
    res['B a middle click with the 3D mouse sending still opens the menu; the 3D-mouse events go on (the view not '
        'turned by them)'] = mm._OPEN[0] and nb >= 40 and tb < 0.5
    yield from close_menu(x0, y0)
    # C
    q0, n0 = rot_now(), SEEN['ndof']
    yield from gesture(x0, y0, drag=True, ndof=True)
    tc = turned(q0)
    left = [n for n in modal_names() if 'mmb' in n.lower()]
    log('C drag, 3D mouse sending: view turned', round(tc, 1), 'deg - menu open', mm._OPEN[0], '- gate left waiting',
        left, '-', SEEN['ndof'] - n0, '3D-mouse events passed on')
    res['C a middle drag with the 3D mouse sending turns the view (no menu, nothing left waiting)'] = (
        tc > 5.0 and not mm._OPEN[0] and not left)
    yield from close_menu(x0, y0)
    # D
    q0 = rot_now()
    yield from gesture(x0, y0, drag=True, ndof=False)
    td = turned(q0)
    log('D drag, no 3D mouse: view turned', round(td, 1), 'deg - menu open', mm._OPEN[0])
    res['D a middle drag turns the view'] = td > 5.0 and not mm._OPEN[0]
    yield from close_menu(x0, y0)
    log('modal operators at the end:', modal_names())
    after = {k: getattr(INP, k) for k in NDOF_KEYS}
    changed = {k: (PREFS_BEFORE[k], after[k]) for k in NDOF_KEYS if PREFS_BEFORE[k] != after[k]}
    log(len(NDOF_KEYS), 'Blender 3D-mouse settings; changed:', changed)
    res[f'E Blender\'s {len(NDOF_KEYS)} 3D-mouse settings the same as before the add-on was turned on'] = (
        len(NDOF_KEYS) > 5 and not changed)
    for k_, v in res.items():
        log(('PASS ' if v else 'FAIL ') + k_)
    log(f'{sum(bool(v) for v in res.values())}/{len(res)} passed')
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
