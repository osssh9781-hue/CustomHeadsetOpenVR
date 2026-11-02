"""Real window (0.24.95 user: "콜렉션도 오리진 투 오브젝트랑 미러 되게 해 주고 레이어에도 나오게 해 주고 레이어 이름도
바꿀 수 있게 해 줘"): MECHA LAB screen, a collection 'Robot' (a part, a sub-collection 'Arms' with two parts) and a loose
part.  The Layers panel shows the collections (a shot); a REAL click on the Robot row's Mirror button (a shot: the
mirrored copy), on its Origin button; a REAL click on the Arms eye (hidden, then shown); a REAL double click on the
Torso row: the rename box (a shot), a new name typed, Enter.
    blender --window-geometry 0 0 W H --python this.py -- OUT"""
import os
import subprocess
import sys

import bpy

sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/addon')
import mecha_lab  # noqa: E402

ARGS = sys.argv[sys.argv.index('--') + 1:]
OUT = ARGS[0]
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, 'log.txt'), 'w')


def log(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    LOG.write(s + '\n')
    LOG.flush()


mecha_lab.register()
from mecha_lab import groups, layers_panel as lp  # noqa: E402
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


def layer_items():
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        return lp.items(C, r.width, r.height, ui_factor(C, r))


def find(pred):
    return next((i for i in layer_items() if pred(i)), None)


def move_to(it):
    w, a, r = view3d()
    x, y = to_x(w, r, it.x + it.w / 2, it.y + it.h / 2)
    xdo('mousemove', x, y)
    return x, y


def shot(name):
    path = os.path.join(OUT, name)
    os.system(f'import -window root "{path}"')
    log('shot', name, os.path.exists(path))
    return path


def rows():
    return [(it.name, d, kind) for it, d, _g, _f, kind in lp.tree(C)]


def button(row_name, label_start):
    """The small button on ``row_name``'s row whose label starts with ``label_start``."""
    row = find(lambda i: i.kind == 'lrow' and i.label == row_name)
    if row is None:
        return None
    return find(lambda i: i.kind == 'pmin' and i.label.startswith(label_start) and abs(i.y - row.y) < 3)


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
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        for c in list(S.collection.children):
            S.collection.children.unlink(c)
        robot = bpy.data.collections.new('Robot')
        S.collection.children.link(robot)
        arms = bpy.data.collections.new('Arms')
        robot.children.link(arms)

        def part(name, loc, size, coll):
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
            ob = C.active_object
            ob.name = name
            ob.scale = size
            for c in list(ob.users_collection):
                c.objects.unlink(ob)
            coll.objects.link(ob)
            return ob
        part('Torso', (1.6, 0, 0), (1.0, 0.7, 1.4), robot)
        part('Arm_L', (2.5, 0, 0.6), (0.5, 0.5, 1.0), arms)
        part('Arm_R', (2.5, 0, -0.6), (0.5, 0.5, 0.4), arms)
        part('Rock', (0, 2.5, -0.5), (0.8, 0.8, 0.5), S.collection)
        sp3 = a.spaces.active
        sp3.shading.type = 'SOLID'
        sp3.show_region_ui = False
        r3 = sp3.region_3d
        r3.view_perspective = 'PERSP'
        r3.view_location = (0.0, 0.5, 0.0)
        r3.view_distance = 11.0
        from mathutils import Euler
        r3.view_rotation = Euler((1.15, 0.0, 0.35)).to_quaternion()
        bpy.ops.mch.bar_tool(tool='SELECT')
        bpy.ops.object.select_all(action='DESELECT')
    yield 4.0
    log('rows', rows())
    log('Robot row', bool(find(lambda i: i.kind == 'lrow' and i.label == 'Robot')),
        'buttons', [i.label for i in layer_items() if i.kind == 'pmin'][:12])
    shot('1_layers_collections.png')

    # Mirror on the Robot collection: a real click
    b = button('Robot', 'Mirror')
    log('Mirror button', b is not None and b.label)
    move_to(b)
    yield 0.4
    xdo('click', 1)
    yield 3.0
    g = bpy.data.objects.get('Robot')
    log('after Mirror click: handle', groups.is_group(g), 'mode', groups.repeat_mode(g),
        'carrier', groups.carrier_of(g) is not None, 'rows', rows())
    xdo('mousemove', 1200, 800)
    yield 3.0
    shot('2_robot_mirror.png')

    # Origin: move the handle away first, then a real click on Origin
    kids = [(o, o.matrix_world.copy()) for o in g.children]
    g.location = (4.0, -2.0, 1.0)
    C.view_layer.update()
    for o, mw in kids:                                  # (the handle alone moved away; the parts stay)
        o.matrix_world = mw
    C.view_layer.update()
    log('handle moved away to', tuple(round(v, 3) for v in g.matrix_world.translation))
    yield 1.0
    before = [tuple(round(v, 3) for v in o.matrix_world.translation) for o in groups.members(g) if o.type == 'MESH']
    b = button('Robot', 'Origin')
    move_to(b)
    yield 0.4
    xdo('click', 1)
    yield 2.0
    after = [tuple(round(v, 3) for v in o.matrix_world.translation) for o in groups.members(g) if o.type == 'MESH']
    box = groups.group_box(g)
    log('after Origin click: handle at', tuple(round(v, 3) for v in g.matrix_world.translation), 'box middle',
        tuple(round(v, 3) for v in (box[0] + box[1]) / 2), 'parts kept', before == after)

    # the Arms eye: a real click, again
    for n in range(2):
        b = button('Arms', 'Hide' if n == 0 else 'Show')
        log('Arms eye button', b is not None and b.label)
        move_to(b)
        yield 0.4
        xdo('click', 1)
        yield 2.0
        lc = lp.layer_coll(C, bpy.data.collections['Arms'])
        log('after eye click', n + 1, 'Arms hidden', lc.hide_viewport, 'Arm_L shown', bpy.data.objects['Arm_L'].visible_get())
        if n == 0:
            xdo('mousemove', 1200, 800)
            yield 2.0
            shot('3_arms_hidden.png')

    # rename: a real double click on the Torso row
    row = find(lambda i: i.kind == 'lrow' and i.label == 'Torso')
    x, y = move_to(row)
    yield 0.4
    xdo('click', '--repeat', 2, '--delay', 120, 1)
    yield 2.0
    shot('4_rename_box.png')
    xdo('key', 'ctrl+a')
    xdo('type', '--delay', 40, 'Chest')
    yield 0.5
    shot('4b_typed.png')
    xdo('key', 'Return')
    yield 1.0
    log('after typing + Enter once: Chest', 'Chest' in bpy.data.objects)
    if 'Chest' not in bpy.data.objects:
        xdo('key', 'Return')
    yield 2.0
    log('after double click + typing: Chest', 'Chest' in bpy.data.objects, 'Torso', 'Torso' in bpy.data.objects,
        'rows', rows())
    xdo('mousemove', 1200, 800)
    yield 2.0
    shot('5_renamed.png')
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
