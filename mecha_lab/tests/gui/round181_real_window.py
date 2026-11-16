"""Real window (0.24.181), by REAL clicks, drags and keys (xdotool), wireframe on - hair mirror (user: "근데 머리카락
미러는 왜 아직 안 되지?"):

  1. a head with a live Mirror X, a lock sculpted on one side: a REAL click on "Hair in the Selected Shape", a REAL
     Enter - the hair mirrored like the head
  2. a REAL drag on Amount - still mirrored (live)
  3. a REAL click on the hair's Apply - the mirror baked into its strands
"""
import math
import os
import subprocess
import sys
import time

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'addon'))
import mecha_lab  # noqa: E402
from mecha_lab import side_panel as sp  # noqa: E402
from mecha_lab.ui_gpu import ui_factor  # noqa: E402
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


def wins():
    r = subprocess.run(['xdotool', 'search', '--name', 'Blender'], capture_output=True, text=True)
    return r.stdout.split()


def focus(wid=None):
    for w_ in ([wid] if wid else wins()):
        subprocess.run(['xdotool', 'windowfocus', '--sync', w_], check=False)


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
    return path


DRAWS = {'n': 0}


def _count_draw():
    DRAWS['n'] += 1


def wait_draws(n, limit=120.0):
    w, a, r = view3d()
    n0 = DRAWS['n']
    t0 = time.perf_counter()
    while DRAWS['n'] < n0 + n and time.perf_counter() - t0 < limit:
        a.tag_redraw()
        yield 0.1


def press(it):
    w, a, r = view3d()
    x, y = int(r.x + it.x + it.w / 2), int(w.height - (r.y + it.y + it.h / 2))
    xdo('mousemove', x, y)
    yield 0.6
    xdo('click', 1)
    yield 1.5


def panel_item(label):
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        its = sp.items(C, r.width, r.height, ui_factor(C, r))
    return next((i for i in its if getattr(i, 'label', '') == label and i.clickable()), None)


def scrolled_item(label):
    """The panel scrolled until the cell ``label`` is in its window; the cell (after two redraws), or None."""
    w, a, r = view3d()
    C.window_manager.mch_side_scroll = 0.0
    yield from wait_draws(2)
    for _i in range(40):
        it = panel_item(label)
        if it is not None:
            yield from wait_draws(2)
            return panel_item(label)
        with C.temp_override(window=w, area=a, region=r):
            sp.scroll_by(C, r.width, r.height, ui_factor(C, r), 120)
        yield from wait_draws(1)
    return None


def screen_xy(p):
    from bpy_extras import view3d_utils
    w, a, r = view3d()
    c = view3d_utils.location_3d_to_region_2d(r, a.spaces.active.region_3d, Vector(p))
    return int(r.x + c.x), int(w.height - (r.y + c.y))


def real_outline(pts, mods=()):
    xdo('mousemove', *pts[0])
    yield 0.4
    for m in mods:
        xdo('keydown', m)
    yield 0.2
    xdo('mousedown', 1)
    yield 0.3
    for x, y in pts[1:] + [pts[0]]:
        xdo('mousemove', x, y)
        yield 0.04
    yield 0.3
    xdo('mouseup', 1)
    yield 0.3
    for m in mods:
        xdo('keyup', m)
    yield 2.5


def ring_at(p, rx_px, ry_px, n=48, wob=0.0):
    c = screen_xy(p)
    return [(int(c[0] + rx_px * math.cos(2 * math.pi * i / n) * (1 + wob * math.sin(3 * 2 * math.pi * i / n))),
             int(c[1] - ry_px * math.sin(2 * math.pi * i / n))) for i in range(n)]


def evaluated(ob):
    import numpy as np
    dg = C.evaluated_depsgraph_get()
    me = ob.evaluated_get(dg).data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    out = {'co': co.reshape(-1, 3), 'faces': len(me.polygons)}
    for nm in ('mch_rd', 'mch_rtop', 'mch_rough'):
        at = me.attributes.get(nm)
        a_ = np.empty(len(at.data), np.float32)
        at.data.foreach_get('value', a_)
        out[nm] = a_
    return out


def slider_drag(it, frac0, dx, steps=12):
    w, a, r = view3d()
    x, y = int(r.x + it.x + it.w * frac0), int(w.height - (r.y + it.y + it.h / 2))
    xdo('mousemove', x, y)
    yield 0.5
    xdo('mousedown', 1)
    yield 0.3
    for i in range(1, steps + 1):
        xdo('mousemove', x + i * dx, y)
        yield 0.06
    yield 0.3
    xdo('mouseup', 1)
    yield 2.5


def drag_world(a, b, mods=()):
    xa, xb = screen_xy(a), screen_xy(b)
    xdo('mousemove', *xa)
    yield 0.4
    for m in mods:
        xdo('keydown', m)
    yield 0.2
    xdo('mousedown', 1)
    yield 0.3
    for i in range(1, 16):
        xdo('mousemove', int(xa[0] + (xb[0] - xa[0]) * i / 15), int(xa[1] + (xb[1] - xa[1]) * i / 15))
        yield 0.05
    yield 0.3
    xdo('mouseup', 1)
    yield 0.4
    for m in mods:
        xdo('keyup', m)
    yield 1.5


def to_x(w, r, x, y):
    return int(r.x + x), int(w.height - (r.y + y))


def layer_items():
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        return lp.items(C, r.width, r.height, ui_factor(C, r))


def lfind(pred):
    return next((i for i in layer_items() if pred(i)), None)


def lclick(it, mods=()):
    w, a, r = view3d()
    x, y = to_x(w, r, it.x + it.w / 2, it.y + it.h / 2)
    xdo('mousemove', x, y)
    yield 0.4
    for m in mods:
        xdo('keydown', m)
    yield 0.2
    xdo('click', 1)
    yield 0.4
    for m in mods:
        xdo('keyup', m)
    yield 1.2


def lbutton(row_name, label_start):
    row = lfind(lambda i: i.kind == 'lrow' and i.label == row_name)
    if row is None:
        return None
    return lfind(lambda i: i.kind == 'pmin' and i.label.startswith(label_start) and abs(i.y - row.y) < 3)


def drag_path(points):
    xy = [screen_xy(p) for p in points]
    xdo('mousemove', *xy[0])
    yield 0.5
    xdo('mousedown', 1)
    yield 0.4
    for x, y in xy[1:]:
        xdo('mousemove', x, y)
        yield 0.08
    yield 0.3
    xdo('mouseup', 1)
    yield 2.0


def key_over_view(key):
    w, a, r = view3d()
    xdo('mousemove', int(r.x + r.width * 0.5), int(w.height - (r.y + r.height * 0.12)))
    yield 0.5
    xdo('key', key)
    yield 3.0


def set_tool(tool):
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool=tool)
        bpy.ops.mch.side_page(page='TOOL')
        for o in C.selected_objects:
            o.select_set(False)
        C.view_layer.objects.active = None




def flow():
    import numpy as np
    import bmesh
    from mecha_lab import hair_shape as hs
    from mathutils.bvhtree import BVHTree
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
    sp3 = a.spaces.active
    res = {}

    def view(rot, loc, dist):
        rv = sp3.region_3d
        rv.view_perspective = 'ORTHO'
        rv.view_rotation = Euler(rot).to_quaternion()
        rv.view_location = loc
        rv.view_distance = dist

    from mecha_lab import mirror_tools as mt
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=48, ring_count=24)
        head = C.active_object
        head.name = 'Head'
        mt.setup_mirror(head, S.mch_mirror, S, (True, False, False), (False, False, False), Vector((0.0, 0.0, 0.0)))
        bm = bmesh.new()
        path = [Vector((0.55 + 0.3 * t, -0.2, 0.8 - 1.2 * t)) for t in np.linspace(0, 1, 30)]
        rings = []
        for i, c in enumerate(path):
            tan = (path[min(i + 1, 29)] - path[max(i - 1, 0)]).normalized()
            u = tan.orthogonal().normalized()
            v = tan.cross(u)
            rings.append([bm.verts.new(c + (u * math.cos(t) + v * math.sin(t)) * (0.15 - 0.1 * i / 29))
                          for t in np.linspace(0, 2 * math.pi, 14, endpoint=False)])
        for a_, b_ in zip(rings[:-1], rings[1:]):
            for k in range(14):
                bm.faces.new((a_[k], a_[(k + 1) % 14], b_[(k + 1) % 14], b_[k]))
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        me = bpy.data.meshes.new('Lock')
        bm.to_mesh(me)
        bm.free()
        lock = bpy.data.objects.new('Lock', me)
        S.collection.objects.link(lock)
        view((math.radians(80), 0.0, 0.0), (0.0, 0.0, 0.3), 4.2)
    sp3.show_region_ui = False
    sp3.overlay.show_wireframes = True
    sp3.shading.type = 'SOLID'
    S.mch_hshape.count = 1500
    S.mch_cover.grow = 'FUR'
    set_tool('FUR')
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    with C.temp_override(window=w, area=a, region=r):
        lock.select_set(True)
        C.view_layer.objects.active = lock
    yield 2.0
    it = yield from scrolled_item('Hair in the Selected Shape')
    if it is not None:
        yield from press(it)
    yield 1.0
    xdo('mousemove', int(r.x + r.width * 0.5), int(w.height - (r.y + r.height * 0.3)))
    yield 0.4
    xdo('key', 'Return')
    yield 6.0
    hair = next((o for o in S.objects if hs.is_hair(o)), None)

    def count(ob):
        dg = C.evaluated_depsgraph_get()
        dg.update()
        e = ob.evaluated_get(dg)
        xs = [p.position.x for p in e.data.points]
        return len(e.data.curves), (min(xs), max(xs)) if xs else (0, 0)

    ok1 = False
    if hair is not None:
        n1, xr = count(hair)
        ok1 = mt.curves_mod(hair) is not None and n1 == 2 * len(hair.data.curves) and abs(xr[0] + xr[1]) < 0.05
        log('1 hair', hair.name, 'strands', len(hair.data.curves), 'shown', n1, 'x', [round(v, 2) for v in xr])
    res['1 a head with a live Mirror X: a REAL click on "Hair in the Selected Shape", a REAL Enter - the hair '
        'mirrored like the head'] = ok1
    shot('1_hair_mirrored.png')
    ok2 = False
    if hair is not None:
        with C.temp_override(window=w, area=a, region=r):
            for o in C.selected_objects:
                o.select_set(False)
            hair.select_set(True)
            C.view_layer.objects.active = hair
        yield 1.5
        it = yield from scrolled_item('Amount')
        if it is not None:
            yield from slider_drag(it, 0.3, int(it.w * 0.03), steps=8)
        yield 3.0
        n2, xr2 = count(hair)
        ok2 = n2 == 2 * len(hair.data.curves) and len(hair.data.curves) != 1500 and abs(xr2[0] + xr2[1]) < 0.05
        log('2 amount', len(hair.data.curves), 'shown', n2)
    res['2 a REAL drag on Amount - still mirrored'] = ok2
    shot('2_amount_mirrored.png')
    ok3 = False
    if hair is not None:
        n_before = count(hair)[0]
        it = yield from scrolled_item('Apply')
        if it is not None:
            yield from press(it)
        yield 2.0
        ok3 = (not hs.is_hair(hair)) and mt.curves_mod(hair) is None and len(hair.data.curves) == n_before
        log('3 apply: strands', len(hair.data.curves), 'was shown', n_before, 'mirror left', mt.curves_mod(hair) is not None)
    res['3 a REAL click on the hair\'s Apply - the mirror baked into its strands'] = ok3
    bpy.types.SpaceView3D.draw_handler_remove(handle, 'WINDOW')
    for k_, v in res.items():
        log(('PASS ' if v else 'FAIL ') + k_)
    log(f'{sum(bool(v) for v in res.values())}/{len(res)} passed')
    bpy.ops.wm.quit_blender()


lp = None
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
