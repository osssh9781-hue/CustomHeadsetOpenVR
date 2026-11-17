"""Real window (0.24.178), by REAL clicks and drags (xdotool), wireframe on:

  1. Geo Sculpt Chamfer (user: "선을 긋는 게 아니라 내가 선택할 수 있는 엣지들을 보여 주는 게 나을 거 같고, 내가 설정한
     브러시 크기로 베벨이랑 챔퍼가 생기고, 알트 누르면 지워지게"): the edges you can pick shown, the one under the brush lit;
     a REAL click on the top front edge of a panel with holes - chamfered whole, the brush's width
  2. a REAL click on another edge, between two holes (user: "처음엔 돼도 같은 메쉬 다른 곳에 한 번 더 그으면 이렇게 돼") -
     the first chamfer stays as it was
  3. Alt + a REAL click on the first edge - off
  4. Boolean Bevel (user: "불린 베벨 만들자, 메뉴로 빼 주고, 원하는 만큼 그리면 그 부분이 베벨 불린, 챔퍼랑"): its tile, a
     REAL drag along part of a block's top edge - only that much cut off (Chamfer)
  5. Round, a REAL click on another edge of the block - all of it, rounded
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
    from mecha_lab import bool_bevel as bb, geo_sculpt as gs
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
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        # an armour panel 2 x 1.4, 0.12 thick, with holes at its right (a narrow strip between two of them)
        bpy.ops.mesh.primitive_cube_add(size=1.0)
        panel = C.active_object
        panel.name = 'Panel'
        panel.scale = (2.0, 0.12, 1.4)
        bpy.ops.object.transform_apply(scale=True)
        for (x, z, ww, hh) in ((0.55, 0.3, 0.18, 0.3), (0.55, -0.1, 0.18, 0.3), (0.78, 0.1, 0.06, 0.5)):
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, 0, z))
            cut = C.active_object
            cut.scale = (ww, 0.5, hh)
            m = panel.modifiers.new('B', 'BOOLEAN')
            m.object, m.operation, m.solver = cut, 'DIFFERENCE', 'EXACT'
            C.view_layer.objects.active = panel
            bpy.ops.object.modifier_apply(modifier='B')
            bpy.data.objects.remove(cut)
        bpy.ops.mesh.primitive_cube_add(size=1.2, location=(0.0, 0.0, -2.0))
        block = C.active_object
        block.name = 'Block'
        rv = sp3.region_3d
        rv.view_perspective = 'ORTHO'
        rv.view_rotation = Euler((math.radians(68), 0.0, math.radians(-22))).to_quaternion()
        rv.view_location = (0.0, 0.0, -0.6)
        rv.view_distance = 6.0
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True
        sp3.shading.type = 'SOLID'
        for o in C.selected_objects:
            o.select_set(False)
    S.mch_geo.brush = 'CHAMFER'
    S.mch_geo.size_px = 40
    set_tool('GSCULPT')
    yield 2.0
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')

    def chamfer_at(ob, p):
        dg = C.evaluated_depsgraph_get()
        dg.update()
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        bvh = BVHTree.FromPolygons([tuple(v.co) for v in me.vertices], [tuple(f.vertices) for f in me.polygons])
        ev.to_mesh_clear()
        return bvh.find_nearest(ob.matrix_world.inverted() @ Vector(p))[3] * math.sqrt(2)     # (its own space)
    # 1 hover then a real click on the panel's top front edge
    top = screen_xy((-0.5, -0.06, 0.7))
    xdo('mousemove', top[0] + 3, top[1] + 2)
    yield 0.6
    xdo('mousemove', *top)
    yield from wait_draws(2)
    lit = gs.HOVER['run']
    shot('1_hover.png')
    xdo('click', 1)
    yield 2.0
    w1 = chamfer_at(panel, (-0.5, -0.06, 0.7))
    mod = panel.modifiers.get(gs.CHAMFER_MOD)
    log('1 hover run', lit, 'chamfer', round(w1, 4), 'mod', mod and round(mod.width, 4))
    res['1 Chamfer: the edge under the brush shown lit; a REAL click - that edge chamfered whole'] = (
        lit is not None and mod is not None and w1 > 0.01)
    shot('1_chamfer.png')
    # 2 another edge, between two holes
    strip = screen_xy((0.75, -0.06, 0.1))
    xdo('mousemove', *strip)
    yield from wait_draws(2)
    xdo('click', 1)
    yield 2.0
    w1b = chamfer_at(panel, (-0.5, -0.06, 0.7))
    eff = gs.safe_widths(panel.data)['CHAMFER']
    log('2 first chamfer', round(w1, 4), '->', round(w1b, 4), 'widths', sorted(set(np.round(eff[eff > 0], 3).tolist())))
    res['2 a REAL click on an edge between two holes: the first chamfer stays as it was'] = (
        abs(w1b - w1) < 1e-4 and len(set(np.round(eff[eff > 0], 4).tolist())) >= 1 and (eff > 0).sum() > 1)
    shot('2_second.png')
    # 3 Alt + click the first: off
    xdo('mousemove', *top)
    yield from wait_draws(2)
    xdo('keydown', 'alt')
    yield 0.2
    xdo('click', 1)
    yield 0.3
    xdo('keyup', 'alt')
    yield 2.0
    w1c = chamfer_at(panel, (-0.5, -0.06, 0.7))
    log('3 alt click: the first edge', round(w1c, 4))
    res['3 Alt + a REAL click on the first edge: off'] = w1c < 1e-4
    shot('3_alt_off.png')
    # 4 Boolean Bevel: a real drag along part of the block's top front edge
    bpy.context.scene.mch_bool_bevel.method = 'CUT'     # (0.24.221 the tool starts on Move Points: this checks the Cut)
    S.mch_bool_bevel.profile, S.mch_bool_bevel.width = 'CHAMFER', 0.15
    set_tool('BBEVEL')
    yield 2.0
    tool_ok = bpy.context.workspace.tools.from_space_view3d_mode('OBJECT').idname == 'mecha.bool_bevel'
    f0 = len(block.data.polygons)
    yield from drag_path([(x, -0.62, -1.38) for x in np.linspace(-0.45, 0.6, 14)]
                         + [(0.57, -0.61, z) for z in np.linspace(-1.45, -1.95, 8)])   # (round the corner, down its front)
    yield 2.0
    d_cut = chamfer_at(block, (-0.2, -0.6, -1.4))
    d_side = chamfer_at(block, (0.6, -0.6, -1.85))
    d_off = chamfer_at(block, (-0.55, -0.6, -1.4))
    log('4 tool', tool_ok, 'faces', f0, '->', len(block.data.polygons), 'cut along the top', round(d_cut, 4),
        'down the side', round(d_side, 4), 'before where it was drawn', round(d_off, 4))
    res['4 Boolean Bevel: its tile; a REAL drag along an edge and on round the corner - it snaps onto both, only that '
        'much cut off'] = tool_ok and d_cut > 0.12 and d_side > 0.12 and d_off < 1e-3
    shot('4_bool_bevel.png')
    # 5 Round, a real click on the block's top right edge
    S.mch_bool_bevel.profile = 'ROUND'
    edge_r = screen_xy((0.6, 0.0, -1.4))
    xdo('mousemove', *edge_r)
    yield from wait_draws(2)
    xdo('click', 1)
    yield 2.5
    d_r = chamfer_at(block, (0.6, 0.0, -1.4)) / math.sqrt(2)
    log('5 round: the corner', round(d_r, 4), 'in (a quarter circle of 0.15:', round(0.15 * (math.sqrt(2) - 1), 4), ')')
    res['5 Round: a REAL click on another edge - all of it rounded'] = abs(d_r - 0.15 * (math.sqrt(2) - 1)) < 0.01
    shot('5_round.png')
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
