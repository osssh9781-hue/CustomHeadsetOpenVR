"""Real window (0.24.142): the Geo Sculpt tool driven by REAL mouse / key events (xdotool) in the MECHA LAB workspace.

  1. the tool picked; a REAL drag on a part with Standard: a stroke (kind 0, strength > 0), the region subdivided
  2. Alt + drag: a stroke with negative strength (a dent);  Shift + drag: Smooth (kind 4)
  3. S at the cursor: the Draw Size popup (shot), the mouse moved right: bigger, a click keeps it;  U: Intensity
  4. Ctrl+Z: the last stroke back
  5. Flat + Alt drag: a raised pad (kind 5, strength < 0);  Edge Line and Panel Line drags (kinds 6 / 7)
  6. shots with the wireframe;  Apply: the layer baked (the part closed)
"""
import os
import subprocess
import sys

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'addon'))
import mecha_lab  # noqa: E402
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
    for w_ in r.stdout.split():
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


def screen_xy(p):
    from bpy_extras import view3d_utils
    w, a, r = view3d()
    c = view3d_utils.location_3d_to_region_2d(r, a.spaces.active.region_3d, Vector(p))
    return int(r.x + c.x), int(w.height - (r.y + c.y))


def drag(points, mods=()):
    """A real drag through the 3D points (screen positions now)."""
    xy = [screen_xy(p) for p in points]
    xdo('mousemove', *xy[0])
    yield 0.4
    for m in mods:
        xdo('keydown', m)
    yield 0.2
    xdo('mousedown', 1)
    yield 0.4
    for x, y in xy[1:]:
        xdo('mousemove', x, y)
        yield 0.08
    yield 0.3
    xdo('mouseup', 1)
    yield 0.3
    for m in mods:
        xdo('keyup', m)
    yield 1.5


def strokes(ob):
    from mecha_lab import geo_sculpt as gs
    sob = gs.strokes_of(ob)
    if sob is None or not len(sob.data.vertices):
        return []
    d = gs.read_strokes(sob)
    out = []
    for sid in sorted(set(d['stroke'].tolist())):
        m = d['stroke'] == sid
        out.append((int(d['kind'][m][0]), float(d['strength'][m][0]), int(m.sum())))
    return out


def flow():
    import bmesh
    from mecha_lab import geo_sculpt as gs, tool_state as ts
    res = {}
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
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        me = bpy.data.meshes.new('Part')
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=2.0)
        bmesh.ops.bevel(bm, geom=list(bm.verts) + list(bm.edges), offset=0.1, segments=1, affect='EDGES', profile=0.5,
                        clamp_overlap=True)
        bm.to_mesh(me)
        bm.free()
        part = bpy.data.objects.new('Part', me)
        S.collection.objects.link(part)
        bpy.ops.object.light_add(type='SUN', location=(0, 0, 5))
        rv = sp3.region_3d
        rv.view_perspective = 'PERSP'
        rv.view_rotation = Euler((0.95, 0.0, 0.35)).to_quaternion()
        rv.view_location = (0.0, 0.0, 0.3)
        rv.view_distance = 6.5
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True                  # (the wireframe always shown with a result)
        bpy.ops.mch.bar_tool(tool='GSCULPT')
    yield 1.5
    with C.temp_override(window=w, area=a, region=r):
        tool_now = ts.effective_tool(C)
    log('tool', tool_now)
    res['1 the Geo Sculpt tool is the active tool (one tool in the list)'] = tool_now == 'GSCULPT'
    st = gs.settings(C)
    st.brush = 'STANDARD'
    st.size_px = 70
    st.intensity = 0.6
    # the brush circle follows the mouse (no button down): two REAL moves, the circle drawn where the mouse is
    follow = []
    for p3 in ((-0.5, -0.5, 1.0), (0.5, 0.4, 1.0)):
        sx, sy = screen_xy(p3)
        for k_ in range(6):                                  # (a few steps there, like a hand)
            xdo('mousemove', sx - 30 + k_ * 6, sy)
            yield 0.1
        yield 0.6
        w, a, r = view3d()
        want = (sx - r.x, (w.height - sy) - r.y)
        got = gs.HOVER['drawn']
        follow.append((want, got))
    shot('0_circle_follows.png')
    log('circle follows', follow)
    res['0 the brush circle follows the mouse (drawn where the mouse is after each move)'] = all(
        g_ is not None and abs(g_[0] - w_[0]) <= 2 and abs(g_[1] - w_[1]) <= 2 for w_, g_ in follow)
    yield from drag([(x, -0.45, 1.0) for x in (-0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6)])
    s1 = strokes(part)
    log('after a Standard drag', s1)
    dg = C.evaluated_depsgraph_get()
    faces = len(part.evaluated_get(dg).data.polygons)
    res['1 a REAL drag: one Standard stroke (positive), the region subdivided, the mesh itself untouched'] = (
        len(s1) == 1 and s1[0][0] == 0 and s1[0][1] > 0 and s1[0][2] >= 3 and faces > 500 and len(part.data.polygons) == 26)
    yield from drag([(x, 0.0, 1.0) for x in (-0.6, -0.3, 0.0, 0.3, 0.6)], mods=('alt',))
    yield from drag([(x, -0.45, 1.0) for x in (0.1, 0.3, 0.5)], mods=('shift',))
    s2 = strokes(part)
    log('after Alt and Shift drags', s2)
    res['2 Alt + drag: a negative stroke (a dent); Shift + drag: Smooth'] = (
        len(s2) == 3 and s2[1][0] == 0 and s2[1][1] < 0 and s2[2][0] == gs.KIND['SMOOTH'])
    shot('1_strokes_wire.png')
    # S: Draw Size at the cursor
    x0, y0 = screen_xy((0.3, 0.45, 1.0))
    xdo('mousemove', x0, y0)
    yield 0.5
    size0 = st.size_px
    xdo('key', 's')
    yield 0.8
    running = gs.MCH_OT_geo_size.RUNNING[0] is not None
    xdo('mousemove', x0 + 120, y0)
    yield 0.8
    shot('2_draw_size_popup.png')
    xdo('click', 1)
    yield 0.8
    log('S: running', running, 'size', size0, '->', st.size_px, 'strokes', len(strokes(part)))
    res['3 S: the Draw Size popup at the cursor; the mouse right = bigger; a click keeps it (no stroke made)'] = (
        running and st.size_px > size0 * 1.5 and gs.MCH_OT_geo_size.RUNNING[0] is None and len(strokes(part)) == 3)
    st.size_px = 70
    k0 = st.intensity
    xdo('key', 'u')
    yield 0.6
    xdo('mousemove', x0 - 60, y0)
    yield 0.6
    xdo('key', 'Return')
    yield 0.6
    res['3 U: Intensity at the cursor (left = weaker)'] = st.intensity < k0
    st.intensity = 0.6
    # Ctrl+Z
    xdo('mousemove', x0, y0)
    yield 0.3
    xdo('key', 'ctrl+z')
    yield 2.0
    part = bpy.data.objects.get('Part')
    st = gs.settings(C)                  # (undo reloads the scene: the settings looked up again, not the old pointer)
    s3 = strokes(part)
    log('after Ctrl+Z', s3)
    res['4 Ctrl+Z: the last stroke back'] = len(s3) == 2
    # Flat + Alt, Edge Line, Panel Line
    st.brush = 'FLAT'
    yield from drag([(x, 0.5, 1.0) for x in (-0.5, -0.3, -0.1)], mods=('alt',))
    st.brush = 'EDGE'
    st.size_px = 60
    yield from drag([(0.95, y, z) for y, z in ((-0.7, 0.6), (-0.4, 0.6), (-0.1, 0.6), (0.2, 0.6), (0.5, 0.6))])
    st.brush = 'PANEL'
    st.size_px = 14
    yield from drag([(x, -1.0, 0.2) for x in (-0.7, -0.4, -0.1, 0.2, 0.5)])
    s4 = strokes(part)
    log('after Flat+Alt, Edge Line, Panel Line', s4)
    res['5 Flat + Alt: a raised pad stroke; Edge Line and Panel Line strokes (kinds 6 / 7)'] = (
        len(s4) == 5 and s4[2][0] == gs.KIND['FLAT'] and s4[2][1] < 0 and s4[3][0] == gs.KIND['EDGE']
        and s4[4][0] == gs.KIND['PANEL'])
    yield 2.0
    shot('3_all_brushes_wire.png')
    # Apply (the window's button: the operator)
    if os.environ.get('MCH_SAVE_BEFORE_APPLY'):
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'before_apply.blend'), copy=True)
    with C.temp_override(window=w, area=a, region=r):
        C.view_layer.objects.active = part
        r_ = bpy.ops.mch.geo_apply()
    bm = bmesh.new()
    bm.from_mesh(part.data)
    open_e = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    log('apply', r_, 'faces', len(part.data.polygons), 'open edges', open_e)
    res['6 Apply: baked into the part, the part closed'] = ('FINISHED' in r_ and gs.layer(part) is None and open_e == 0
                                                             and len(part.data.polygons) > 1000)
    yield 1.5
    shot('4_applied_wire.png')
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
