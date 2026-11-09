"""Real window (0.24.122): Press Cut in Draw: Lasso mode with the REAL mouse - a press is the Base Mesh tool's lasso.
  1. Lasso mode, shape Free Draw: a closed drag on empty space, Enter (Sketch First) -> a Base Mesh part
  1b. shape Lasso: four clicks + a double-click (the Base Mesh tool's polygon lasso), Enter -> another part
  2. a Free Draw drawn over the first part, then Alt+Enter -> the sketch cut into the part, as in the Base Mesh tool
  3. back to Line mode: a drag makes a line again
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
from mecha_lab import cut_engine as _ce, base_mesh as _bm  # noqa: E402
_orig_exec = _ce.StrokeLogic._execute_closed
_orig_perform = _bm.perform_base


def _traced_exec(self, context):
    try:
        b = context.scene.mch_brush
        lazy = {k: getattr(b, k) for k in dir(b) if 'lazy' in k.lower() or 'stabil' in k.lower()}
        log(f'  [stroke pts] n={len(self.pts)} head={[tuple(int(c) for c in q) for q in self.pts[:5]]} '
            f'tail={[tuple(int(c) for c in q) for q in self.pts[-5:]]} lazy={lazy} smooth={b.stroke_smooth} simplify={b.stroke_simplify}')
    except Exception as ex:
        log('  [stroke pts] probe failed', repr(ex))
    try:
        out = _orig_exec(self, context)
        log(f'  [_execute_closed] mode={self.mode} shape={self.shape} -> {str(out)[:120]}')
        return out
    except Exception as ex:
        log(f'  [_execute_closed] mode={self.mode} shape={self.shape} EXC {repr(ex)[:160]}')
        raise


def _traced_perform(*a, **k):
    try:
        out = _orig_perform(*a, **k)
        log('  [perform_base] ->', str(out)[:120])
        return out
    except Exception as ex:
        log('  [perform_base] EXC', repr(ex)[:160])
        raise


_ce.StrokeLogic._execute_closed = _traced_exec
_bm.perform_base = _traced_perform


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


def drag(points, alt=False):
    xdo('mousemove', *points[0])
    yield 0.3
    if alt:
        xdo('keydown', 'alt')
        yield 0.1
    # (the lasso modal starts on the press and Blender then queues a move at the press spot: give it a moment before
    #  the first real move, or that stale move lands after it and the outline retraces itself at the start)
    xdo('mousedown', 1, 'sleep', 0.12, 'mousemove', *points[1], 'sleep', 0.03, 'mousemove', *points[2])
    yield 0.05
    for p in points[3:]:
        xdo('mousemove', *p)
        yield 0.03
    xdo('mouseup', 1)
    yield 0.3
    if alt:
        xdo('keyup', 'alt')
    yield 2.2


def circle(cx, cy, r, n=16):
    # (no repeated first point: the tool closes the outline itself - a closing overlap reads as a self-crossing)
    return [(int(round(cx + r * math.cos(math.tau * k / n))), int(round(cy + r * math.sin(math.tau * k / n)))) for k in range(n)]


def key(name):
    xdo('key', name)
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
        a.spaces.active.show_region_ui = False
        S.cursor.location = (0.0, 0.0, 0.0)
        S.mch_settings.auto_apply = True
        S.mch_press.size = 40.0
        S.mch_press.result = 'CUT'
        S.mch_press.draw_mode = 'LASSO'
        S.mch_brush.shape = 'STROKE'                           # Free Draw: a drag draws the closed outline
        S.mch_brush.line_open = False
        C.window_manager.mch_layers_min = True
        C.window_manager.mch_side_min = True
        bpy.ops.mch.set_tool(tool='PRESS')
    res = {}
    orbit((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 10.0)
    yield 1.2
    log('Press draw mode', S.mch_press.draw_mode, 'brush shape', S.mch_brush.shape, 'base sketch', getattr(S.mch_base, 'sketch', None),
        'profile_sweep', getattr(S.mch_base, 'profile_sweep', None), 'line_attach', getattr(S.mch_base, 'line_attach', None))
    # 1. a closed lasso on empty space -> a part
    before = set(bpy.data.objects.keys())
    cx, cy = screen_of((-1.5, 0.0, 0.0))
    yield from drag(circle(cx, cy, 150, n=48) + circle(cx, cy, 150, n=48)[:3])      # dense like a hand, a little overlap
    from mecha_lab import base_mesh as _b
    log('  sketch after the drag:', bool(_b.sketch_data(S)) if hasattr(_b, 'sketch_data') else 'n/a')
    yield from key('Return')                                    # Base Mesh's Sketch First: Enter makes the mesh
    new = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before if bpy.data.objects[n].type == 'MESH']
    part = new[0] if new else None
    try:
        from mecha_lab import lasso_sketch, cut_presets
        log('  after drag: sketch data', lasso_sketch.data(C.scene) is not None, 'LAST_LOOPS', cut_presets.LAST_LOOPS[0] is not None,
            'objects', sorted(bpy.data.objects.keys()))
    except Exception as ex:
        log('  after drag: probe failed', repr(ex))
    if part is not None:
        log(f'1 lasso -> {part.name}: verts {len(part.data.vertices)} faces {len(part.data.polygons)} closed {closed(part)} '
            f'dims {tuple(round(c, 2) for c in part.dimensions)} line? {bool(part.get(base_mesh.SWEEP_KEY))}')
        res['1 Lasso mode: a closed lasso on empty space makes a Base Mesh part (not a line), closed'] = \
            len(part.data.polygons) >= 10 and closed(part) and not part.get(base_mesh.SWEEP_KEY) and part.dimensions.x > 1.5
    else:
        log('1: nothing made')
        res['1 Lasso mode: a closed lasso on empty space makes a Base Mesh part (not a line), closed'] = False
    # 1b. the polygon Lasso: four clicks + a double-click, as in the Base Mesh tool
    with C.temp_override(window=w, area=a, region=r):
        S.mch_brush.shape = 'LASSO'
        for o in C.selected_objects:
            o.select_set(False)
    yield 0.5
    before = set(bpy.data.objects.keys())
    sq = [screen_of(q) for q in ((1.5, 1.2, 0.0), (3.0, 1.2, 0.0), (3.0, 2.6, 0.0), (1.5, 2.6, 0.0))]
    for q in sq:
        xdo('mousemove', *q)
        yield 0.3
        xdo('click', 1)
        yield 0.5
    xdo('click', '--repeat', 2, '--delay', 80, 1)              # the double-click confirms
    yield 2.2
    yield from key('Return')                                    # Sketch First: Enter makes the mesh
    new = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before if bpy.data.objects[n].type == 'MESH']
    poly = new[0] if new else None
    log(f'1b polygon lasso (clicks + double-click) -> {poly.name if poly else None}' + (
        f': faces {len(poly.data.polygons)} dims {tuple(round(c, 2) for c in poly.dimensions)} closed {closed(poly)}' if poly else ''))
    res['1b Lasso shape: four clicks + a double-click make a part, as the Base Mesh tool does'] = \
        poly is not None and closed(poly) and abs(poly.dimensions.x - 1.5) < 0.2 and abs(poly.dimensions.y - 1.4) < 0.2
    with C.temp_override(window=w, area=a, region=r):
        S.mch_brush.shape = 'STROKE'
        for o in C.selected_objects:
            o.select_set(False)
        if part is not None:
            part.select_set(True)
            C.view_layer.objects.active = part
    yield 0.5
    # 2. Alt + Free Draw over the part: as in the Base Mesh tool (subtract)
    if part is not None:
        n_before = len(part.data.polygons)
        objs_before = set(bpy.data.objects.keys())
        yield from drag(circle(cx, cy, 55, n=24) + circle(cx, cy, 55, n=24)[:2])     # a plain outline over the part ...
        xdo('keydown', 'alt')                                   # ... Alt + Enter: cut the sketch into the mesh below
        yield 0.2
        xdo('key', 'Return')
        yield 0.3
        xdo('keyup', 'alt')
        yield 2.0
        objs_after = set(bpy.data.objects.keys())
        log(f'2 outline over the part + Alt+Enter: faces {n_before} -> {len(part.data.polygons)} new objects {sorted(objs_after - objs_before)} closed {closed(part)}')
        res['2 an outline over the part, Alt+Enter: cut into it (the part changed), as in the Base Mesh tool'] = \
            len(part.data.polygons) != n_before or bool(objs_after - objs_before)
    else:
        res['2 an outline over the part, Alt+Enter: cut into it (the part changed), as in the Base Mesh tool'] = False
    # 3. back to Line: a drag is a line again
    with C.temp_override(window=w, area=a, region=r):
        S.mch_press.draw_mode = 'LINE'
        for o in C.selected_objects:
            o.select_set(False)
    yield 0.6
    before = set(bpy.data.objects.keys())
    yield from drag([screen_of((1.0 + 2.0 * k / 8, -1.5, 0.0)) for k in range(9)])
    new = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before if bpy.data.objects[n].type == 'MESH']
    line = new[0] if new else None
    log('3 Line mode drag ->', line.name if line else None, 'line?', bool(line and line.get(base_mesh.SWEEP_KEY)))
    res['3 Line mode again: a drag makes a swept line'] = bool(line and line.get(base_mesh.SWEEP_KEY))
    with C.temp_override(window=w, area=a, region=r):
        S.mch_press.draw_mode = 'LASSO'                      # (the top bar shows Draw: Lasso in the picture)
    orbit((1.0, 0.0, 0.4), (-0.3, -0.5, -0.3), 9.0, persp=True)
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.wm.tool_set_by_id(name='builtin.select_box')    # (the Press key legend would cover the parts)
        for o in C.selected_objects:
            o.select_set(False)
        if part is not None:
            part.select_set(True)
            C.view_layer.objects.active = part
        a.spaces.active.overlay.show_wireframes = True
    xdo('mousemove', 300, 700)
    yield 1.5
    shot('1_press_lasso.png')
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
