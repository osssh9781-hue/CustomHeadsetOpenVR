"""Real window: the Lasso Zone tool (0.24.95 user: "라쏘도 컷이나 이런 거처럼 위에 막대에 옵션 다 넣어 줘 - 스케치랑
라인 이런 거 다").  MECHA LAB screen, a part with Mech Steel (an FBX given after OUT, else a cube), the Mech page: REAL
mouse (xdotool) - Paint Zone (the button), then from the TOP BAR: Rectangle + Round corners (a dragged rectangle);
Lasso + Line (a dragged line: a stripe); Sketch + Circle (a circle, Alt + a smaller one, Enter: a ring);
then a thicker line (Width 4 %, Height -1.5) and Mirror X (the zones on the other side too); Split + Through +
Ellipse (a Split Zone, the back faces too); Esc (back to Select); a shot after each, wireframe on.
    blender --window-geometry 0 0 W H --python this.py -- OUT [FBX]"""
import math
import os
import subprocess
import sys

import bpy

sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/addon')
import mecha_lab  # noqa: E402

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[-1:]
OUT = ARGS[0]
FBX = ARGS[1] if len(ARGS) > 1 else None
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, 'log.txt'), 'w')


def log(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    LOG.write(s + '\n')
    LOG.flush()


mecha_lab.register()
from mecha_lab import side_panel as sp, tool_state as ts, top_bar as tb  # noqa: E402
from mecha_lab.ui_gpu import ui_factor  # noqa: E402
C = bpy.context
S = C.scene


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


def to_x(w, r, x, y):
    return int(r.x + x), int(w.height - (r.y + y))


def panel_items():
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        return sp.items(C, r.width, r.height, ui_factor(C, r))


def bar_items():
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        return tb.items(C, r.width, r.height, ui_factor(C, r))


def tool():
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        return ts.effective_tool(C)


def scroll(dy):
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        sp.scroll_by(C, r.width, r.height, ui_factor(C, r), dy)
        a.tag_redraw()


def scrolled_to(pred):
    for _n in range(150):
        it = next((i for i in panel_items() if pred(i)), None)
        if it is not None:
            return it
        scroll(60)
        yield 0.3
    return None


def shot(name):
    path = os.path.join(OUT, name)
    os.system(f'import -window root "{path}"')
    log('shot', name, os.path.exists(path))


def hover(it):
    w, a, r = view3d()
    x, y = to_x(w, r, it.x + it.w / 2, it.y + it.h / 2)
    xdo('mousemove', x, y)
    return x, y


def bar_click(label, kind=None):
    """A real click on the top bar's cell ``label``."""
    it = next((i for i in bar_items() if i.label == label and (kind is None or i.kind == kind)), None)
    if it is None:
        log('top bar: no', label)
        return None
    pos = hover(it)
    xdo('click', 1)
    return pos


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
    from mathutils import Vector
    from bpy_extras import view3d_utils
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        if FBX:
            bpy.ops.import_scene.fbx(filepath=FBX)
        else:
            bpy.ops.mesh.primitive_cube_add(size=1.0)
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.subdivide(number_cuts=24)
            bpy.ops.object.mode_set(mode='OBJECT')
        part = next(o for o in S.objects if o.type == 'MESH')
        for o in C.selected_objects:
            o.select_set(False)
        part.select_set(True)
        C.view_layer.objects.active = part
        bpy.ops.mch.mech_shader_apply(preset='STEEL')
        bb = [part.matrix_world @ Vector(c) for c in part.bound_box]
        ctr = sum(bb, Vector()) / 8
        sp3 = a.spaces.active
        sp3.shading.type = 'MATERIAL'
        sp3.overlay.show_wireframes = True
        sp3.show_region_ui = False
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        d = Vector((0.35, 1.0, -0.45)).normalized() if FBX else Vector((0.3, 1.0, -0.5)).normalized()
        rv.view_rotation = d.to_track_quat('-Z', 'Z')
        rv.view_location = ctr
        rv.view_distance = 1.9 if FBX else 2.6
        bpy.ops.mch.bar_tool(tool='SELECT')
        bpy.ops.mch.side_page(page='MATERIAL')
        S.mch_brush.line_width = 0.05
    mat = part.active_material
    log('part', part.name, 'points', len(part.data.vertices), 'material', mat.name)
    xdo('mousemove', 300, 1200)
    yield 40.0
    w, a, r = view3d()
    rv3d = r.data
    # the part's visible surface on the screen: rays through a grid over its projected box
    pts2 = [view3d_utils.location_3d_to_region_2d(r, rv3d, c) for c in bb]
    x0, x1 = min(p.x for p in pts2), max(p.x for p in pts2)
    y0, y1 = min(p.y for p in pts2), max(p.y for p in pts2)
    hits = []
    dg = C.evaluated_depsgraph_get()
    for i in range(41):
        for j in range(25):
            sx, sy = x0 + (x1 - x0) * i / 40, y0 + (y1 - y0) * j / 24
            o = view3d_utils.region_2d_to_origin_3d(r, rv3d, (sx, sy))
            v = view3d_utils.region_2d_to_vector_3d(r, rv3d, (sx, sy))
            ok, loc, _n, _i, ob, _m = S.ray_cast(dg, o, v)
            if ok and ob == part:
                hits.append((sx, sy, loc))
    log('surface samples', len(hits))
    span = max(h[2].x for h in hits) - min(h[2].x for h in hits)
    xmin = min(h[2].x for h in hits)

    def on_part(fx):
        """A screen point on the part at fraction fx of its width (the middle of that column)."""
        col = [h for h in hits if abs((h[2].x - xmin) / span - fx) < 0.04]
        col.sort(key=lambda h: h[1])
        h = col[len(col) // 2]
        return h[0], h[1]

    def drag(p0, p1, steps=12, alt=False):
        X0, Y0 = to_x(w, r, *p0)
        X1, Y1 = to_x(w, r, *p1)
        if alt:
            xdo('keydown', 'alt')
        xdo('mousemove', X0, Y0)
        yield 0.3
        xdo('mousedown', 1)
        yield 0.2
        for k in range(1, steps + 1):
            xdo('mousemove', int(X0 + (X1 - X0) * k / steps), int(Y0 + (Y1 - Y0) * k / steps))
            yield 0.05
        xdo('mouseup', 1)
        if alt:
            xdo('keyup', 'alt')
        yield 1.5

    def zones():
        return [(z.name, z.kind) for z in mat.mch_zones]

    shot('0_steel.png')
    # ---- Paint Zone (the page button): the Lasso Zone tool, the top bar its lasso
    head = yield from scrolled_to(lambda i: i.kind == 'shead' and i.label.startswith('ZONES'))
    if not head.on:
        hover(head)
        yield 0.4
        xdo('click', 1)
        yield 1.5
    btn = yield from scrolled_to(lambda i: i.kind == 'tbtn' and i.label == 'Paint Zone')
    hover(btn)
    yield 0.4
    xdo('click', 1)
    yield 1.5
    groups = [i.label for i in bar_items() if i.kind == 'glabel']
    log('Paint Zone clicked: tool', tool(), 'kind', S.mch_zone_kind, 'top bar groups', groups)
    btn = next((i for i in panel_items() if i.kind == 'tbtn' and i.label == 'Paint Zone'), None)
    log('... the Paint Zone button lit:', bool(btn and btn.on))
    shot('1_tool_on.png')
    # ---- Rectangle + Round corners: a dragged rectangle on the left
    bar_click('Rectangle')
    yield 0.6
    bar_click('Round')
    yield 0.6
    log('shape', S.mch_brush.shape, 'corners', S.mch_brush.outline_corner)
    a0, a1 = on_part(0.12), on_part(0.3)
    yield from drag((a0[0], a0[1] - 25), (a1[0], a1[1] + 25))
    log('rectangle dragged: zones', zones())
    # ---- Lasso + Line: a line dragged across the right side
    bar_click('Lasso')
    yield 0.6
    bar_click('Sharp')
    yield 0.6
    bar_click('Line')
    yield 0.6
    log('shape', S.mch_brush.shape, 'Line', S.mch_brush.line_mode, 'width', round(S.mch_brush.line_width, 3))
    p0, p1 = on_part(0.62), on_part(0.9)                # (Line: the lasso is drawn holding the button, release applies)
    yield from drag(p0, p1, steps=16)
    log('line dragged: zones', zones())
    bar_click('Line')
    yield 0.6
    # ---- Sketch + Circle: a circle, Alt + a smaller one inside, Enter -> a ring
    bar_click('Sketch')
    yield 0.6
    bar_click('Circle')
    yield 0.6
    c = on_part(0.5)
    log('Sketch', S.mch_brush.sketch_first, 'shape', S.mch_brush.shape)
    yield from drag(c, (c[0] + 55, c[1]))
    yield from drag(c, (c[0] + 22, c[1]), alt=True)
    xdo('key', 'Return')
    yield 1.5
    log('sketch (circle - Alt circle) + Enter: zones', zones())
    bar_click('Sketch')
    yield 0.6
    yield 25.0
    with C.temp_override(window=w, area=a, region=r):
        part.select_set(False)
    xdo('mousemove', 300, 1200)
    yield 25.0
    shot('2_paint_zones.png')
    with C.temp_override(window=w, area=a, region=r):
        part.select_set(True)
    # ---- a thicker, deeper boundary line on the first zone (Line Width 4 %, Line Height -1.5)
    with C.temp_override(window=w, area=a, region=r):
        z0 = mat.mch_zones[0]
        z0.line_width, z0.line_height = 4.0, -1.5
    log('zone 1 line: width', z0.line_width, 'height', z0.line_height)
    # ---- Mirror X on the part: every zone shows on the other side too
    from mecha_lab import symmetry as sy, zones as zn
    with C.temp_override(window=w, area=a, region=r):
        sy.set_mode(C, part, 'MIRROR')
    yield 2.0
    log('Mirror on:', sy.mode_of(part), 'zone 1 mirror copies', len(zn.mirror_maps(mat.mch_zones[0])),
        'copy nodes', mat.node_tree.nodes.get('mchz:0:v1:mask') is not None)
    with C.temp_override(window=w, area=a, region=r):
        part.select_set(False)
    xdo('mousemove', 300, 1200)
    yield 30.0
    shot('3_mirror_line.png')
    with C.temp_override(window=w, area=a, region=r):
        part.select_set(True)
    # ---- Split (top bar) + Through (top bar) + Ellipse: a Split Zone, the back faces too
    bar_click('Split')
    yield 0.6
    bar_click('Through')
    yield 0.6
    bar_click('Ellipse')
    yield 0.6
    log('kind', S.mch_zone_kind, 'Through', S.mch_brush.through_mode, 'shape', S.mch_brush.shape)
    nf = len(part.data.polygons)
    e0 = on_part(0.38)
    yield from drag((e0[0] - 30, e0[1] - 18), (e0[0] + 30, e0[1] + 18))
    yield 2.0
    log('ellipse dragged (Split, Through): faces', nf, '->', len(part.data.polygons), 'materials',
        [sl.material.name for sl in part.material_slots if sl.material])
    # ---- Esc (the mouse in the viewport, below the part): back to Select
    X, Y = to_x(w, r, *on_part(0.5))
    xdo('mousemove', X, Y + 260)
    yield 0.3
    xdo('key', 'Escape')
    yield 1.0
    log('Esc: tool', tool())
    with C.temp_override(window=w, area=a, region=r):
        part.select_set(False)
    yield 30.0
    shot('4_split_through.png')
    log('DONE')
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
