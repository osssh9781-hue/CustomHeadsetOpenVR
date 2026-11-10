"""Real window (0.24.127, user: "왜 크리쳐 베이스가 안나와?"): is the Creature Base Mesh tool there and does a drawn outline make
a part?  Also the Press tool's Creature Plate result and the new 3D Mouse Settings window (a picture of each).

  0. the drawn tool strip: the Block-out group lists Creature Base Mesh; the V tool pie too
  1. Creature Base Mesh + a free-drawn circle on empty space, Enter -> a new rounded part (Puff)
  1b. the polygon lasso (clicks + a double-click), Enter -> another part
  2. Press, result Creature Plate: a press on a part -> a plate
  3. the 3D Mouse Settings window open (screenshot)
"""
import math
import os
import subprocess
import sys

import bmesh
import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'addon'))
import mecha_lab  # noqa: E402
from mecha_lab import tool_state as ts, ui_bars  # noqa: E402
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


def win_of_region(px):
    w, a, r = view3d()
    return int(round(r.x + px[0])), int(round(w.height - (r.y + px[1])))


def closed(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    n = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return n == 0


def drag(points):
    xdo('mousemove', *points[0])
    yield 0.3
    xdo('mousedown', 1, 'sleep', 0.12, 'mousemove', *points[1], 'sleep', 0.03, 'mousemove', *points[2])
    yield 0.05
    for p in points[3:]:
        xdo('mousemove', *p)
        yield 0.03
    xdo('mouseup', 1)
    yield 2.2


def circle(cx, cy, r, n=16):
    return [(int(round(cx + r * math.cos(math.tau * k / n))), int(round(cy + r * math.sin(math.tau * k / n)))) for k in range(n)]


def key(name):
    xdo('key', name)
    yield 2.5


def click(pt, n=1):
    xdo('mousemove', *pt)
    yield 0.3
    xdo('click', '--repeat', n, '--delay', 60, 1)
    yield 0.8


def orbit(rot, loc, dist, persp=False):
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        rv = a.spaces.active.region_3d
        rv.view_perspective = 'PERSP' if persp else 'ORTHO'
        rv.view_rotation = Euler(rot).to_quaternion()
        rv.view_location = loc
        rv.view_distance = dist


def new_meshes(before):
    return [bpy.data.objects[n] for n in sorted(set(bpy.data.objects.keys()) - before) if bpy.data.objects[n].type == 'MESH']


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
        bpy.ops.mch.set_tool(tool='CBASE')
    res = {}
    orbit((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 10.0)
    yield 1.2
    # 0. the tool strip and the pie
    from mecha_lab.ui_gpu import ui_factor
    with C.temp_override(window=w, area=a, region=r):
        k = ui_factor(C, r)
        on = ui_bars.strip_on(C)
        its = ui_bars.strip_items(C, r.width, r.height, k) if on else []
    labels = [i.label for i in its if i.kind in {'sbtn', 'button'}]
    heads = [i.label for i in its if i.kind == 'striphead']
    log('0 strip on', on, 'groups', heads, 'has Creature Base Mesh', 'Creature Base Mesh' in labels, 'tool', ts.native_tool_id(C), ts.effective_tool(C))
    log('   visible tools', [t[0] for t in ts.VISIBLE_TOOLS][:60])
    log('   grouped Block-out', [t[1] for n, rows in ts.grouped_tools() for t in rows if n == 'Block-out'])
    grid = [t[1] for n, rows in ts.grouped_tools() for t in rows if n == 'Block-out']     # the bottom tool grid's groups
    res['0 the tool grid lists Creature Base Mesh (Block-out group; the left strip is a preference, off here); the tool is the active one'] = \
        'Creature Base Mesh' in grid and ts.effective_tool(C) == 'CBASE'
    shot('0_strip_cbase.png')
    log('   base settings: sketch', getattr(S.mch_base, 'sketch', None), 'profile', getattr(S.mch_cbase, 'profile', None) if hasattr(S, 'mch_cbase') else None,
        'brush shape', S.mch_brush.shape, 'line_open', S.mch_brush.line_open, 'res', getattr(S.mch_cbase, 'resolution', None) if hasattr(S, 'mch_cbase') else None)
    # 1. a free-drawn circle on empty space, Enter
    with C.temp_override(window=w, area=a, region=r):
        S.mch_brush.shape = 'STROKE'
        S.mch_brush.line_open = False
    before = set(bpy.data.objects.keys())
    cx, cy = screen_of((-2.0, 0.0, 0.0))
    yield from drag(circle(cx, cy, 150, n=48) + circle(cx, cy, 150, n=48)[:3])
    from mecha_lab import lasso_sketch
    log('1 after the drag: sketch data', lasso_sketch.data(S) is not None, 'new meshes', [o.name for o in new_meshes(before)])
    focus()
    yield from key('Return')
    new = new_meshes(before)
    part = new[0] if new else None
    if part is not None:
        log(f'   -> {part.name}: verts {len(part.data.vertices)} faces {len(part.data.polygons)} closed {closed(part)} '
            f'dims {tuple(round(d, 2) for d in part.dimensions)} profile {part.mch_base.profile if hasattr(part, "mch_base") else "?"}')
    else:
        log('   -> NO new mesh; objects', sorted(bpy.data.objects.keys()), 'tool', ts.effective_tool(C))
    res['1 Creature Base Mesh: a free-drawn circle on empty space + Enter makes a closed rounded part'] = \
        part is not None and len(part.data.polygons) > 50 and closed(part) and part.dimensions.z > 0.05
    # 1b. the polygon lasso (clicks + a double-click)
    with C.temp_override(window=w, area=a, region=r):
        S.mch_brush.shape = 'LASSO'
    before = set(bpy.data.objects.keys())
    px, py = screen_of((2.2, 0.0, 0.0))
    pts = [(px - 140, py - 120), (px + 160, py - 140), (px + 150, py + 130), (px - 120, py + 110)]
    for p in pts[:-1]:
        yield from click(p)
    yield from click(pts[-1], n=2)
    yield 1.0
    focus()
    yield from key('Return')
    new = new_meshes(before)
    poly = new[0] if new else None
    log(f'1b polygon lasso -> {poly.name if poly else None}' + (f': verts {len(poly.data.vertices)} faces {len(poly.data.polygons)} closed {closed(poly)}' if poly else
                                                              f'; objects {sorted(bpy.data.objects.keys())}'))
    res['1b the polygon lasso (clicks + a double-click) + Enter makes a part too'] = poly is not None and len(poly.data.polygons) > 50 and closed(poly)
    shot('1_cbase_parts.png')
    # 2. Press, result Creature Plate, on the first part
    ok2 = False
    if part is not None:
        with C.temp_override(window=w, area=a, region=r):
            WM.mch_legend_min = True                      # (the open key legend card would take the press)
            S.mch_press.result = 'CPLATE'
            S.mch_press.size = 35.0
            bpy.ops.mch.set_tool(tool='PRESS')
            for o in S.objects:
                o.select_set(o is part)
            C.view_layer.objects.active = part
        yield 0.8
        before = set(bpy.data.objects.keys())
        sp = screen_of(part.matrix_world @ Vector(part.bound_box[0]) * 0 + part.matrix_world.translation)
        xdo('mousemove', *sp)
        yield 0.3
        xdo('mousedown', 1)
        yield 1.2
        xdo('mouseup', 1)
        yield 2.5
        plates = new_meshes(before)
        log('2 Press (Creature Plate) on', part.name, 'at', sp, '-> new', [(o.name, len(o.data.polygons)) for o in plates], 'tool', ts.effective_tool(C))
        ok2 = bool(plates) and len(plates[0].data.polygons) > 10
        shot('2_press_cplate.png')
    res['2 Press with result Creature Plate: a press on the part makes a plate'] = ok2
    # 3. the 3D Mouse Settings window
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.wm.tool_set_by_id(name='builtin.select_box')
    xdo('mousemove', *win_of_region((r.width * 0.5, r.height * 0.55)))
    yield 0.5
    try:
        with C.temp_override(window=w, area=a, region=r):
            rr = bpy.ops.mch.ndof_settings('INVOKE_DEFAULT')
        log('3 ndof_settings invoke ->', rr)
        yield 1.5
        shot('3_ndof_settings.png')
        res['3 the 3D Mouse Settings window opens (its picture taken)'] = 'RUNNING_MODAL' in rr or 'FINISHED' in rr
    except Exception as ex:
        log('3 ndof_settings failed', repr(ex))
        res['3 the 3D Mouse Settings window opens (its picture taken)'] = False
    xdo('key', 'Escape')
    yield 0.5
    for k_, v in res.items():
        log(('PASS ' if v else 'FAIL ') + k_)
    log(f'{sum(res.values())}/{len(res)} passed')
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
