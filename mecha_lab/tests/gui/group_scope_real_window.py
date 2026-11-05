"""Real window (0.24.107): groups the Substance 3D Modeler way, with the REAL mouse (xdotool) on Blender 5.2.3.

Four boxes A B C D in group G (C D also in nested group H), box E outside.  Select mode:
click A -> G selected + green outline (shot), double-click A -> inside G, click C -> H, double-click C -> inside H,
double-click empty -> back to G, again -> out; a new box made inside G joins only after the move that follows it
ends; Ctrl+Z keeps the scope; saved and opened again: clicks still work (the timers survive a file load).
Press Cut: contact dots (shot), the stamp picker grid (shot).
    blender --window-geometry 0 0 W H --python this.py -- OUT"""
import os
import subprocess
import sys

import bpy

sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/addon')
import mecha_lab  # noqa: E402

OUT = sys.argv[-1]
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, 'log.txt'), 'w')


def log(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    LOG.write(s + '\n')
    LOG.flush()


mecha_lab.register()
from mecha_lab import groups, group_outline, bottom_bar  # noqa: E402


def C():
    return bpy.context


def xdo(*args):
    subprocess.run(['xdotool', *map(str, args)], check=False)


def focus():
    r = subprocess.run(['xdotool', 'search', '--name', 'Blender'], capture_output=True, text=True)
    for wid in r.stdout.split():
        subprocess.run(['xdotool', 'windowfocus', '--sync', wid], check=False)


def view3d():
    for w in C().window_manager.windows:
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
    return int(r.x + p.x), int(w.height - (r.y + p.y))


def state(tag):
    S = C().scene
    sel = sorted(o.name for o in C().selected_objects)
    sc = groups.scope(C())
    log(f'[{tag}] selected {sel} | active {getattr(C().view_layer.objects.active, "name", None)} | scope '
        f'{sc.name if sc else None} path {groups.scope_path(C())} | outlined '
        f'{sorted(o.name for o in group_outline.outline_objects(C()))} | outline shader failed '
        f'{group_outline._state["shader_failed"]} error {group_outline._state["error"]!r}')
    return sel, (sc.name if sc else None)


def select_mode():
    w, a, r = view3d()
    with C().temp_override(window=w, area=a, region=r):
        bpy.ops.wm.tool_set_by_id(name='builtin.select_box')
        bottom_bar.note_select(C())


def dbl(xy):
    xdo('mousemove', *xy)
    xdo('click', '--repeat', 2, '--delay', 90, 1)


def flow():
    w, a, r = view3d()
    focus()
    xdo('mousemove', 30, 540)
    yield 0.3
    xdo('key', 'Escape')
    yield 0.5
    with C().temp_override(window=w, area=a, region=r):
        ws = next((x for x in bpy.data.workspaces if x.name.startswith('MECHA LAB')), None)
        if ws is None:
            bpy.ops.mch.workspace_open()
            ws = next((x for x in bpy.data.workspaces if x.name.startswith('MECHA LAB')), None)
        w.workspace = ws
    yield 2.0
    w, a, r = view3d()
    S = C().scene
    with C().temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        sp = a.spaces.active
        sp.show_region_ui = False
        rv = sp.region_3d
        bpy.ops.view3d.view_axis(type='TOP')
        rv.view_perspective = 'ORTHO'
        rv.view_location = (0.0, -0.8, 0.0)
        rv.view_distance = 14.0
        boxes = {}
        for name, x, y in (('A', -3.3, 0.0), ('B', -1.1, 0.0), ('C', 1.1, 0.0), ('D', 3.3, 0.0), ('E', 0.0, -3.4)):
            bpy.ops.mesh.primitive_cube_add(size=1.6, location=(x, y, 0.0))
            C().active_object.name = name
            boxes[name] = C().active_object
        G = groups.create(C(), [boxes[n] for n in 'ABCD'], 'G')
        H = groups.create(C(), [boxes['C'], boxes['D']], 'H')
        bpy.ops.object.select_all(action='DESELECT')
    select_mode()
    yield 1.5
    log('keymap items for the group click:', [(k.name, i.type, i.value) for k, i in groups._group_keymaps],
        '| auto-add timer:', bpy.app.timers.is_registered(groups._auto_group_tick),
        '| handle size', G.empty_display_size, '| group boxes on', S.mch_settings.group_boxes)
    try:
        log('modal operators running at rest:', [op.bl_idname for win in C().window_manager.windows
                                                 for op in win.modal_operators])
    except AttributeError as ex:
        log('modal_operators not available', ex)

    xdo('mousemove', *screen_of((-3.3, 0.0, 0.8)))
    yield 0.5
    xdo('click', 1)
    yield 1.0
    s1 = state('click A')
    shot('1_click_A_group_selected.png')
    yield 0.8                                       # (a pause: the next two clicks are a new double-click)
    dbl(screen_of((-3.3, 0.0, 0.8)))
    yield 1.2
    s2 = state('double-click A')
    shot('2_inside_G.png')
    yield 0.8
    xdo('mousemove', *screen_of((1.1, 0.0, 0.8)))
    yield 0.3
    xdo('click', 1)
    yield 1.0
    s3 = state('inside G, click C')
    shot('3_inside_G_H_selected.png')
    yield 0.8
    dbl(screen_of((1.1, 0.0, 0.8)))
    yield 1.2
    s4 = state('double-click C')
    yield 0.8
    xdo('mousemove', *screen_of((-1.1, 0.0, 0.8)))
    yield 0.3
    xdo('click', 1)
    yield 0.8
    s4b = state('inside H, click B (outside H: ghosted, not picked)')
    yield 0.8
    dbl(screen_of((0.0, 3.0, 0.0)))                   # empty space
    yield 1.2
    s5 = state('double-click empty (H -> G)')
    yield 0.8
    xdo('mousemove', *screen_of((5.5, 3.0, 0.0)))
    yield 0.3
    xdo('click', 1)
    yield 0.8
    s5b = state('single click empty (stays in G)')
    yield 0.8
    dbl(screen_of((0.0, 3.0, 0.0)))
    yield 1.2
    s6 = state('double-click empty again (out)')
    yield 0.8
    dbl(screen_of((-1.1, 0.0, 0.8)))                  # into G again for the auto-add part
    yield 1.2
    state('double-click B (into G)')
    w, a, r = view3d()
    with C().temp_override(window=w, area=a, region=r):
        bpy.ops.mesh.primitive_cube_add(size=0.6, location=(0.0, 2.6, 0.0))
    new = C().active_object
    xdo('mousemove', *screen_of((0.0, 2.6, 0.3)))
    yield 0.1
    xdo('key', 'g')
    yield 0.2
    for k in range(10):
        xdo('mousemove_relative', '--', 12, 0)
        yield 0.15
    parent_during = new.parent.name if new.parent else None
    xdo('click', 1)
    yield 1.6
    parent_after = new.parent.name if new.parent else None
    log('AUTO-ADD: a box made inside G then moved at once: parent while moving', parent_during, '| after',
        parent_after, '| where', tuple(round(v, 2) for v in new.matrix_world.translation))
    xdo('mousemove', *screen_of((-3.3, 0.0, 0.8)))
    yield 0.3
    xdo('click', 1)
    yield 0.8
    w, a, r = view3d()
    with C().temp_override(window=w, area=a, region=r):
        bpy.ops.transform.translate(value=(0.0, 0.5, 0.0))
    yield 0.5
    xdo('key', 'ctrl+z')
    yield 1.5
    s7 = state('Ctrl+Z after moving A inside G')
    path = os.path.join(OUT, 'scope_reload.blend')
    bpy.ops.wm.save_as_mainfile(filepath=path)
    yield 0.5
    bpy.ops.wm.open_mainfile(filepath=path)
    yield 3.0
    log('after opening the file again: auto-add timer', bpy.app.timers.is_registered(groups._auto_group_tick),
        '| keymap items', len(groups._group_keymaps))
    s8 = state('opened again')
    groups.clear_scope(C())
    select_mode()
    yield 1.0
    xdo('mousemove', *screen_of((3.3, 0.0, 0.8)))
    yield 0.3
    xdo('click', 1)
    yield 1.0
    s9 = state('opened again, click D')
    shot('4_reopened_click_D.png')
    # Press Cut: contact dots and the stamp picker grid
    w, a, r = view3d()
    S = C().scene
    with C().temp_override(window=w, area=a, region=r):
        bpy.ops.object.select_all(action='DESELECT')
        S.mch_press.size = 45.0
        S.mch_press.shape = 'MCH_BUILTIN_M_CHAMFER_PANEL'
        bpy.ops.mch.set_tool(tool='PRESS')
    yield 1.5
    xdo('mousemove', *screen_of((0.9, -3.4, 0.8)))
    yield 1.2
    shot('5_press_contact_dots.png')
    from mecha_lab import press_cut as pc
    log('dot sizes px (outline, contact ring, core):', pc.dot_sizes(C()))
    w, a, r = view3d()
    with C().temp_override(window=w, area=a, region=r):
        try:
            bpy.ops.mch.press_shape_grid('INVOKE_DEFAULT')
        except Exception as ex:        # noqa
            log('shape grid invoke error', ex)
    yield 1.5
    shot('6_press_shape_grid.png')
    xdo('key', 'Escape')
    yield 0.6
    ok = {
        'click selects the group': s1[0] == ['G'] and s1[1] is None,
        'double-click enters': s2[1] == 'G',
        'inside, click on a nested part picks the nested group': s3[0] == ['H'] and s3[1] == 'G',
        'double-click enters nested': s4[1] == 'H',
        'outside part not picked inside H': 'B' not in s4b[0],
        'double-click empty: one level out': s5[1] == 'G',
        'single click empty stays': s5b[1] == 'G',
        'double-click empty again: out': s6[1] is None,
        'auto-add waits for the move': parent_during is None and parent_after == 'G',
        'Ctrl+Z keeps the scope': s7[1] == 'G',
        'scope back after reopening': s8[1] == 'G',
        'click works after reopening': s9[0] == ['G'],
    }
    for k, v in ok.items():
        log(('PASS ' if v else 'FAIL ') + k)
    log('RESULT', sum(ok.values()), '/', len(ok))
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


bpy.app.timers.register(run, first_interval=2.0, persistent=True)
