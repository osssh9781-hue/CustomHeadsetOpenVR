"""Real window (0.24.124) with the REAL mouse and keyboard:
  1. E in the Cut tool: the part under the mouse is held (Smart Move in any tool), LMB on the slab puts it there,
     Return keeps - the Cut tool stays
  2. the corner card's 3D MOUSE: Parts (a real click) -> a 3D-mouse event through the operator's own invoke turns the
     selected part about its origin (no device here) -> View again
  3. the key legend card's title (a real click) folds it to one line
  4. Press Cut + Plate (Armor): a line dragged over a sphere -> the stamp's section laid along the surface (a live
     swept part on the sphere); a quick press on the sphere -> the stamp as an Armor Plate
  5. a box cut by the Cut tool, D + drag (Concept Move) beside the hole -> a grid bump, not a fan of slivers
Two screenshots, wireframe on.
    blender --window-geometry 0 0 W H --python this.py -- OUT"""
import json
import math
import os
import subprocess
import sys
import types

import bmesh
import bpy

sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/addon')
import mecha_lab  # noqa: E402
from mecha_lab import base_mesh, cut_engine as ce, key_legend as kl, smart_move as sm, tool_state as ts, zb_ui as zu  # noqa: E402
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


def click(pt):
    xdo('mousemove', *pt)
    yield 0.4
    xdo('click', 1)
    yield 1.0


def drag(points, hold_key=None):
    xdo('mousemove', *points[0])
    yield 0.3
    if hold_key:
        xdo('keydown', hold_key)
        yield 0.1
    xdo('mousedown', 1, 'sleep', 0.03, 'mousemove', *points[1], 'sleep', 0.03, 'mousemove', *points[2])
    yield 0.05
    for p in points[3:]:
        xdo('mousemove', *p)
        yield 0.03
    xdo('mouseup', 1)
    if hold_key:
        yield 0.1
        xdo('keyup', hold_key)
    yield 1.8


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


def mesh_stats(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    sl = 0
    for f in bm.faces:
        if len(f.verts) == 3:
            a, b, c = [v.co for v in f.verts]
            try:
                angs = [(b - a).angle(c - a), (a - b).angle(c - b), (a - c).angle(b - c)]
            except ValueError:
                angs = [0.0]
            if min(angs) < math.radians(5):
                sl += 1
    top = max((ob.matrix_world @ v.co).z for v in bm.verts)
    n = (len(bm.verts), len(bm.faces), nm, sl, top)
    bm.free()
    return n


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
    SC = Vector((-2.6, 0.4, 1.3))
    R = 1.3
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        a.spaces.active.show_region_ui = False
        a.spaces.active.overlay.show_wireframes = True
        S.cursor.location = (0.0, 0.0, 0.0)
        WM.mch_layers_min = True
        WM.mch_side_min = True
        WM.mch_legend_min = False
        WM.mch_ndof_parts = False
        bpy.ops.mesh.primitive_cube_add(size=1)
        slab = C.active_object
        slab.name = 'Slab'
        slab.scale = (14, 14, 0.6)
        slab.location = (0, 0, -0.3)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=R, segments=48, ring_count=24, location=SC)
        sphere = C.active_object
        sphere.name = 'Sphere'
        bpy.ops.mesh.primitive_cube_add(size=0.8, location=(0.3, 0.9, 0.9))      # (mid-screen: clear of the drawn bars)
        part = C.active_object
        part.name = 'Part'
        part.rotation_euler = (math.radians(15), 0, math.radians(30))
        part.scale = (1.0, 1.5, 0.6)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(3.0, 0.6, 0.4))
        cutbox = C.active_object
        cutbox.name = 'CutBox'
        cutbox.scale = (2.6, 1.8, 0.8)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        for o in (slab, sphere, part, cutbox):
            o.select_set(False)
        S.mch_smart.axes, S.mch_smart.speed, S.mch_smart.push, S.mch_smart.lift = 'VIEW', 1.0, 'FREE', 0.0
        bpy.ops.mch.set_tool(tool='CUT')
    C.view_layer.update()
    res = {}
    orbit((1.0, 0.0, 0.45), (0.2, 0.2, 0.5), 11.5, persp=True)
    yield 1.2
    log('tool', ts.native_tool_id(C), ts.effective_tool(C))
    # 1. E in the Cut tool
    m0 = part.matrix_world.copy()
    sp = screen_of(part.matrix_world.translation)
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    from mecha_lab import quick_hud
    with C.temp_override(window=w, area=a, region=r, region_data=a.spaces.active.region_3d):
        p2 = location_3d_to_region_2d(r, a.spaces.active.region_3d, part.matrix_world.translation)
        over = quick_hud.over_ui(C, p2.x, p2.y)
        under = sm.hit_under(C, (p2.x, p2.y))
    log('1 E at', sp, 'region', (round(p2.x), round(p2.y)), 'over UI', over, 'under the mouse', None if under is None else under[2].name)
    xdo('mousemove', *sp)
    yield 0.4
    focus()
    xdo('key', 'e')
    yield 0.8
    op = sm.ACTIVE[0]
    log('   held:', None if op is None else (op.ob_name, op.tool0, op.from_key), 'tool now', ts.effective_tool(C))
    held = op is not None and op.ob_name == 'Part' and op.tool0 == 'CUT'
    p1 = Vector((-0.9, 0.2, 0.0))                 # (a slab point nothing stands in front of from this view)
    yield from click(screen_of(p1))
    t = part.matrix_world.translation
    placed = (t - p1).length < 0.03 and same_rot(part.matrix_world, m0)
    log(f'   placed at {tuple(round(c, 3) for c in t)} wanted {tuple(p1)} rot same {same_rot(part.matrix_world, m0)}')
    focus()
    xdo('key', 'Return')
    yield 0.8
    log('   Return: running', sm.ACTIVE[0] is not None, 'tool', ts.effective_tool(C))
    res['1 E in the Cut tool holds the part under the mouse; LMB on the slab puts it there (rotation kept); Return keeps; the Cut tool stays'] = \
        held and placed and sm.ACTIVE[0] is None and ts.effective_tool(C) == 'CUT'
    # 2. the corner card: 3D MOUSE Parts
    w, a, r = view3d()
    from mecha_lab.ui_gpu import ui_factor
    with C.temp_override(window=w, area=a, region=r):
        k = ui_factor(C, r)
        its = zu.corner_items(C, r.width, r.height, k)
    seg = {(i.label, i.action[1] if i.action else ''): i for i in its if i.kind == 'seg'}
    parts_it = seg.get(('Parts', 'mch.ndof_parts'))
    view_it = seg.get(('View', 'mch.ndof_parts'))
    log('2 corner card rows', [i.label for i in its if i.kind == 'glabel'], 'Parts item', parts_it is not None)
    ok2 = False
    if parts_it is not None:
        yield from click(win_of_region((parts_it.x + parts_it.w / 2, parts_it.y + parts_it.h / 2)))
        on = bool(WM.mch_ndof_parts)
        with C.temp_override(window=w, area=a, region=r):     # (the part selected and active, as a user would have it)
            for o in C.selected_objects:
                o.select_set(False)
            part.select_set(True)
            C.view_layer.objects.active = part
        before = part.matrix_world.copy()
        ev = types.SimpleNamespace(type='NDOF_MOTION', value='NOTHING',
                                   ndof_motion=types.SimpleNamespace(rotation=Vector((0.0, 0.25, 0.0)), translation=Vector((0.0, 0.0, 0.0)),
                                                                     time_delta=0.1, progress='IN_PROGRESS'))
        w, a, r = view3d()
        with C.temp_override(window=w, area=a, region=r, region_data=a.spaces.active.region_3d):
            ret = sm.MCH_OT_smart_ndof.invoke(types.SimpleNamespace(), C, ev)
        turn = (part.matrix_world.to_3x3() @ before.to_3x3().inverted()).to_quaternion()
        log(f'   Parts on {on}; ndof through the operator: {ret} turned {math.degrees(turn.angle):.2f} deg, origin moved '
            f'{(part.matrix_world.translation - before.translation).length:.5f}, active {C.view_layer.objects.active.name}')
        ok2 = on and ret == {'FINISHED'} and abs(math.degrees(turn.angle) - 9.0) < 0.1 and \
            (part.matrix_world.translation - before.translation).length < 1e-5
        yield from click(win_of_region((view_it.x + view_it.w / 2, view_it.y + view_it.h / 2)))
        log('   View again:', not WM.mch_ndof_parts)
        ok2 = ok2 and not WM.mch_ndof_parts
    res['2 corner card 3D MOUSE: Parts (real click) - a 3D-mouse event turns the selected part about its origin in the Cut tool; View again'] = ok2
    # 3. the legend card folds on its title
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        b1 = kl.box(C)
    log('3 legend box', None if b1 is None else tuple(round(v) for v in b1[:4]), 'rows', None if b1 is None else len(b1[4]))
    ok3 = False
    if b1 is not None:
        x0, y0, bw, bh = b1[:4]
        yield from click(win_of_region((x0 + bw * 0.4, y0 + bh - 14 * k)))
        with C.temp_override(window=w, area=a, region=r):
            b2 = kl.box(C)
        log('   folded', WM.mch_legend_min, None if b2 is None else tuple(round(v) for v in b2[:4]), 'rows', None if b2 is None else len(b2[4]))
        ok3 = bool(WM.mch_legend_min) and b2 is not None and len(b2[4]) == 1 and b2[3] < bh * 0.5
    res['3 the key legend card folds to its title line on a real click (and stays foldable)'] = ok3
    # 4. Press + Plate: a line on the sphere, a press on the sphere
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.set_tool(tool='PRESS')
        pr = S.mch_press
        ids = {e.identifier for e in pr.bl_rna.properties['shape'].enum_items} if hasattr(pr.bl_rna.properties['shape'], 'enum_items') else set()
        pr.shape = 'MCH_BUILTIN_M_L_BLOCK' if 'MCH_BUILTIN_M_L_BLOCK' in ids else 'MCH_BUILTIN_M_OCTAGON'
        pr.result = 'PLATE'
        pr.draw_mode = 'LINE'
        pr.drawn = False
        pr.size = 26.0
        pr.rotation = 0.0
        for o in C.selected_objects:
            o.select_set(False)
    yield 0.6
    log('4 press', ts.effective_tool(C), pr.shape, pr.result, pr.draw_mode)
    before = set(bpy.data.objects.keys())
    arc = []
    for t in range(-55, 56, 10):
        d = Vector((math.sin(math.radians(t)), -0.35, math.cos(math.radians(t)))).normalized()
        arc.append(screen_of(SC + d * R))
    yield from drag(arc)
    new = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before]
    line = next((o for o in new if o.get(base_mesh.SWEEP_KEY)), None)
    ok4a = False
    if line is not None:
        data = json.loads(line[base_mesh.SWEEP_KEY])
        rs = [((line.matrix_world @ v.co) - SC).length for v in line.data.vertices]
        st_ = mesh_stats(line)
        log(f'   plate line {line.name}: surface {data.get("surface")} points {len(data.get("path3", []))} verts {st_[0]} faces {st_[1]} '
            f'non-manifold {st_[2]} radius {min(rs):.3f}..{max(rs):.3f} (sphere {R})')
        ok4a = data.get('surface') == 'Sphere' and len(data.get('path3', [])) >= 6 and st_[2] == 0 and \
            min(rs) > R - 0.15 and max(rs) < R + 1.2 and max(rs) > R + 0.1
    else:
        log('   no plate line made', [o.name for o in new])
    before = set(bpy.data.objects.keys())
    d = Vector((0.75, -0.6, 0.3)).normalized()
    yield from click(screen_of(SC + d * R))
    new = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before]
    plate = next((o for o in new if 'Plate' in o.name), None)
    log('   press:', [o.name for o in new])
    res['4a Press + Plate, Line: the stamp\'s section laid along the sphere (a live swept part standing on the surface)'] = ok4a
    res['4b Press + Plate, press: the stamp as an Armor Plate on the sphere'] = plate is not None and plate.type == 'MESH' and len(plate.data.polygons) > 0
    orbit((1.0, 0.0, 0.45), (-1.5, 0.3, 0.9), 7.5, persp=True)
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.wm.tool_set_by_id(name='builtin.select_box')
    xdo('mousemove', 300, 820)
    yield 1.5
    shot('1_press_plate_line.png')
    # 5. Concept Move on a cut box (D + drag)
    orbit((1.0, 0.0, 0.45), (2.6, 0.4, 0.4), 6.0, persp=True)
    yield 0.8
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r, region_data=a.spaces.active.region_3d):
        proj = ce.make_projector(r, a.spaces.active.region_3d)
        from bpy_extras.view3d_utils import location_3d_to_region_2d
        c2 = location_3d_to_region_2d(r, a.spaces.active.region_3d, Vector((3.0, 0.6, 0.8)))
        loops = [[(c2.x + 70 * math.cos(t), c2.y + 45 * math.sin(t)) for t in (2 * math.pi * i / 28 for i in range(28))]]
        n_before = len(cutbox.data.polygons)
        try:
            msg = ce.perform_closed(C, 'CUT', [cutbox], loops, proj)
        except Exception as ex:
            msg = 'cut failed: ' + repr(ex)
        for o in C.selected_objects:
            o.select_set(False)
        bpy.ops.mch.set_tool(tool='CUT')
    st0 = mesh_stats(cutbox)
    log('5 cut box:', msg[:80], 'faces', n_before, '->', st0[1])
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.set_tool(tool='CMOVE')          # the Concept Move tool itself (D + drag is the same operator)
        S.mch_concept.radius_px = 140
    yield 0.8
    from mecha_lab import concept_move as cm
    calls = {'invoke': 0, 'apply': 0}
    real_invoke, real_apply = cm.MCH_OT_concept_move.invoke, cm.apply_moves

    def _inv(self_, context, event):
        calls['invoke'] += 1
        return real_invoke(self_, context, event)

    def _apply(ob, moves, generate_mesh=True, auto_apply=True):
        calls['apply'] += 1
        return real_apply(ob, moves, generate_mesh, auto_apply)
    cm.MCH_OT_concept_move.invoke, cm.apply_moves = _inv, _apply
    log('   tool', ts.native_tool_id(C), ts.effective_tool(C))
    grab = screen_of((3.0 - 0.9, 0.6 + 0.45, 0.8))
    yield from drag([grab] + [(grab[0], grab[1] - 8 * k_) for k_ in range(1, 14)])
    cm.MCH_OT_concept_move.invoke, cm.apply_moves = real_invoke, real_apply
    st1 = mesh_stats(cutbox)
    log(f'   after the drag: invoke {calls["invoke"]} apply {calls["apply"]} verts {st1[0]} faces {st1[1]} non-manifold {st1[2]} slivers {st1[3]} '
        f'top z {st1[4]:.3f} (was {st0[4]:.3f}, faces {st0[1]})')
    res['5 Concept Move on a part cut by the Cut tool: the pull makes a grid bump - refined faces, no fan of slivers, manifold'] = \
        st1[1] > st0[1] + 40 and st1[4] > st0[4] + 0.05 and st1[2] == 0 and st1[3] <= max(12, st1[1] // 12)
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.wm.tool_set_by_id(name='builtin.select_box')
    xdo('mousemove', 300, 820)
    yield 1.5
    shot('2_concept_move_cut_box.png')
    for kname, v in res.items():
        log(('PASS ' if v else 'FAIL ') + kname)
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
