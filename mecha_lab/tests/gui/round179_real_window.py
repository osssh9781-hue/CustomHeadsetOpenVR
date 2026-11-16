"""Real window (0.24.179), by REAL clicks, drags and keys (xdotool), wireframe on:

  1. Boolean Bevel (user, two screenshots: "옆에 라인 클릭해서 베벨 하면 이렇게 돼, 저 베벨이 만나야 되는 거 아니여?"): a
     REAL click rounds a block's bottom front edge, a REAL click chamfers its right front edge - they meet at the corner;
     Alt + a REAL click on the round - off, the chamfer kept
  2. Target Selected (user: "셀렉트랑 오토"): with another block selected, the block under the mouse is passed by
  3. Hair in a sculpted shape (user: "결 시작 부분은 내가 찍어 주는 게 낫지 않나?"): the lock selected, a REAL click on
     "Hair in the Selected Shape", a REAL click where it starts on the lock, a REAL Enter - hair from there
  4. Face Pop (user: "내가 선택한 면이 튀어나오게"): its tile, a REAL click on a face - out; a REAL drag over two more -
     out; Alt + a REAL click - that one off
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
    from mecha_lab import bool_bevel as bb, face_pop as fp, hair_shape as hs
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

    def dist_local(ob, p):
        me = ob.data
        bvh = BVHTree.FromPolygons([tuple(v.co) for v in me.vertices], [tuple(f.vertices) for f in me.polygons])
        return bvh.find_nearest(ob.matrix_world.inverted() @ Vector(p))[3]

    def view(rot, loc, dist):
        rv = sp3.region_3d
        rv.view_perspective = 'ORTHO'
        rv.view_rotation = Euler(rot).to_quaternion()
        rv.view_location = loc
        rv.view_distance = dist

    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 0.0))
        blk = C.active_object
        blk.name = 'Block'
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, -3.0, 0.0))
        other = C.active_object
        other.name = 'Other'
        view((math.radians(78), 0.0, math.radians(-30)), (0.0, 0.0, 0.0), 7.0)
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True
        sp3.shading.type = 'SOLID'
        for o in C.selected_objects:
            o.select_set(False)
        other.hide_set(True)
    S.mch_cut.targets = 'AUTO'
    S.mch_bool_bevel.profile, S.mch_bool_bevel.width, S.mch_bool_bevel.segments = 'ROUND', 0.25, 8
    set_tool('BBEVEL')
    yield 2.0
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    # 1 round the bottom front edge, chamfer the right front edge, Alt off the round
    bot = screen_xy((0.0, -1.0, -0.98))
    xdo('mousemove', *bot)
    yield from wait_draws(2)
    xdo('click', 1)
    yield 2.5
    S.mch_bool_bevel.profile = 'CHAMFER'
    rgt = screen_xy((0.98, -1.0, 0.2))
    xdo('mousemove', *rgt)
    yield from wait_draws(2)
    xdo('click', 1)
    yield 2.5
    meet = dist_local(blk, (1.0, -1.0, -0.78)) * math.sqrt(2)          # (the chamfer just above the round)
    st_ = bb.state(blk)
    shot('1_bevels_meet.png')
    xdo('mousemove', *bot)
    yield from wait_draws(2)
    xdo('keydown', 'alt')
    yield 0.2
    xdo('click', 1)
    yield 0.3
    xdo('keyup', 'alt')
    yield 2.5
    round_gone = dist_local(blk, (0.0, -1.0, -1.0))
    cham_kept = dist_local(blk, (1.0, -1.0, 0.2)) * math.sqrt(2)
    log('1 meet', round(meet, 4), 'cuts', st_ and len(st_['cuts']), 'alt: round', round(round_gone, 5), 'chamfer',
        round(cham_kept, 4))
    res['1 Boolean Bevel: a REAL click rounds one edge, a REAL click chamfers the one beside it - they meet at the corner; '
        'Alt + a REAL click - the round off, the chamfer kept'] = (
        abs(meet - 0.25) < 0.02 and st_ is not None and len(st_['cuts']) == 2 and round_gone < 1e-6
        and abs(cham_kept - 0.25) < 0.02)
    shot('1_alt_off.png')
    # 2 Target Selected: the other block selected, the block under the mouse passed by
    with C.temp_override(window=w, area=a, region=r):
        other.hide_set(False)
        for o in C.selected_objects:
            o.select_set(False)
        other.select_set(True)
        C.view_layer.objects.active = other
    S.mch_cut.targets = 'SELECTED'
    yield 1.0
    f0 = len(blk.data.polygons)
    top = screen_xy((0.0, 1.0, 1.0))
    xdo('mousemove', *top)
    yield from wait_draws(2)
    xdo('click', 1)
    yield 2.0
    passed = len(blk.data.polygons) == f0
    S.mch_cut.targets = 'AUTO'
    log('2 selected only: block untouched', passed)
    res['2 Target Selected: the block not selected is passed by (a REAL click on its edge: nothing)'] = passed
    # 3 hair in a sculpted shape: the lock, start clicked
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=48, ring_count=24)
        head = C.active_object
        head.name = 'Head'
        bm = bmesh.new()
        path = [Vector((0.0, 0.0, 0.92)) + Vector((0.6 * t, 0.0, 0.35 * math.sin(math.pi * t) - 1.1 * t * t))
                for t in np.linspace(0, 1, 40)]
        rings = []
        for i, c in enumerate(path):
            tan = (path[min(i + 1, 39)] - path[max(i - 1, 0)]).normalized()
            u = tan.orthogonal().normalized()
            v = tan.cross(u)
            rr = 0.14 - 0.1 * i / 39
            rings.append([bm.verts.new(c + (u * math.cos(t) + v * math.sin(t)) * rr)
                          for t in np.linspace(0, 2 * math.pi, 16, endpoint=False)])
        for a_, b_ in zip(rings[:-1], rings[1:]):
            for k in range(16):
                bm.faces.new((a_[k], a_[(k + 1) % 16], b_[(k + 1) % 16], b_[k]))
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        me = bpy.data.meshes.new('Lock')
        bm.to_mesh(me)
        bm.free()
        lock = bpy.data.objects.new('Lock', me)
        S.collection.objects.link(lock)
        for o in C.selected_objects:
            o.select_set(False)
        lock.select_set(True)
        C.view_layer.objects.active = lock
        view((math.radians(90), 0.0, 0.0), (0.3, 0.0, 0.6), 4.0)
    S.mch_hshape.count = 600
    S.mch_cover.grow = 'FUR'
    set_tool('FUR')
    with C.temp_override(window=w, area=a, region=r):
        lock.select_set(True)
        C.view_layer.objects.active = lock
    yield 2.0
    it = yield from scrolled_item('Hair in the Selected Shape')
    if it is not None:
        yield from press(it)
    yield 1.0
    start = screen_xy(tuple(path[-5]))                 # (near the lock's far end, on its side: the start clicked there)
    xdo('mousemove', *start)
    yield 0.5
    xdo('click', 1)
    yield 1.0
    shot('3_start_clicked.png')
    xdo('mousemove', int(r.x + r.width * 0.5), int(w.height - (r.y + r.height * 0.3)))
    yield 0.4
    xdo('key', 'Return')
    yield 5.0
    hair = next((o for o in S.objects if hs.is_hair(o)), None)
    ok3 = False
    if hair is not None:
        seg = hair.mch_hshape.segments
        P = np.empty(len(hair.data.points) * 3, np.float32)
        hair.data.attributes['position'].data.foreach_get('vector', P)
        M = np.array(hair.matrix_world)
        W = (P.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]).reshape(-1, seg, 3)
        d_root = float(np.median(np.linalg.norm(W[:, 0] - np.array(tuple(path[-5])), axis=1)))
        ok3 = d_root < 0.3 and bool(hair.get(hs.STARTS))
        log('3 hair', hair.name, len(hair.data.curves), 'roots from the clicked end', round(d_root, 3))
    else:
        log('3 no hair', it is not None)
    res['3 Hair: a REAL click on "Hair in the Selected Shape", a REAL click where it starts, a REAL Enter - hair from '
        'there'] = ok3
    shot('3_hair.png')
    # 4 Face Pop
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=1.0)
        rock = C.active_object
        rock.name = 'Rock'
        for o in C.selected_objects:
            o.select_set(False)
        view((math.radians(70), 0.0, math.radians(20)), (0.0, 0.0, 0.0), 4.5)
    S.mch_pop.height, S.mch_pop.taper, S.mch_pop.each = 0.12, 0.35, True
    set_tool('FPOP')
    yield 2.0
    from bpy_extras import view3d_utils
    def face_xy(f):
        c = rock.matrix_world @ rock.data.polygons[f].center
        return screen_xy(tuple(c))
    rv = sp3.region_3d
    facing = sorted([p.index for p in rock.data.polygons
                     if (rv.view_rotation @ Vector((0, 0, 1))).dot(p.normal) > 0.75],
                    key=lambda i: rock.data.polygons[i].center.z)
    f1 = facing[len(facing) // 2]
    xdo('mousemove', *face_xy(f1))
    yield from wait_draws(2)
    xdo('click', 1)
    yield 2.0
    n1 = int(fp.picked(rock.data).sum())
    others = [f for f in facing if f != f1][:2]
    pts = [face_xy(f) for f in others]
    xdo('mousemove', *pts[0])
    yield 0.4
    xdo('mousedown', 1)
    yield 0.3
    for k in range(1, 9):
        xdo('mousemove', int(pts[0][0] + (pts[1][0] - pts[0][0]) * k / 8), int(pts[0][1] + (pts[1][1] - pts[0][1]) * k / 8))
        yield 0.08
    xdo('mouseup', 1)
    yield 2.0
    n2 = int(fp.picked(rock.data).sum())
    shot('4_face_pop.png')
    xdo('mousemove', *face_xy(f1))
    yield from wait_draws(2)
    xdo('keydown', 'alt')
    yield 0.2
    xdo('click', 1)
    yield 0.3
    xdo('keyup', 'alt')
    yield 2.0
    n3 = int(fp.picked(rock.data).sum())
    log('4 face pop: click', n1, 'drag', n2, 'alt', n3, 'modifier', rock.modifiers.get(fp.MOD) is not None)
    res['4 Face Pop: a REAL click on a face - out; a REAL drag over two more - out; Alt + a REAL click - that one off'] = (
        n1 == 1 and n2 >= 3 and n3 == n2 - 1 and rock.modifiers.get(fp.MOD) is not None)
    shot('4_face_pop_alt.png')
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
