"""Real window: My Materials (0.24.95 user: "기존에 만들어 놓은 재질도 프리셋으로 등록 가능한가? 가능하게 해 줘").
MECHA LAB screen, a box with the Mech Shader (Painted Metal, its paint turned blue), a ball with no material, a
hand-made material on nothing; the Mech page: REAL mouse (xdotool) - the MY MATERIALS title, Save Material... -> the
dialog -> Enter (the box's material saved, its ball picture rendered); the ball selected, a click on the saved ball ->
the material on it; a shot.  The presets go to a temp folder (never the user's).
    blender --window-geometry 0 0 W H --python this.py -- OUT"""
import math
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
from mecha_lab import decals as dc, side_panel as sp  # noqa: E402
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


def find(pred):
    return next((i for i in panel_items() if pred(i)), None)


def scroll(dy):
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        sp.scroll_by(C, r.width, r.height, ui_factor(C, r), dy)
        a.tag_redraw()


def scrolled_to(pred):
    for _n in range(150):
        it = find(pred)
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


def flow():
    import tempfile
    from mecha_lab import my_materials as mm
    mm.DIR[0] = tempfile.mkdtemp()
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
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(2.6, 0.0, 0.0))
        target = C.active_object
        target.name = 'Ball'
        bpy.ops.mesh.primitive_cube_add(size=2.0)
        part = C.active_object
        part.name = 'Part'
        bpy.ops.mch.mech_shader_apply(preset='PAINTED')
        part.active_material.mch_mech.paint_color = (0.05, 0.18, 0.55)
        part.active_material.mch_mech.edge_wear = 0.4
        own = bpy.data.materials.new('My Green Glass')
        own.use_nodes = True
        own.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.1, 0.7, 0.2, 1.0)
        own.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.1
        sp3 = a.spaces.active
        sp3.shading.type = 'MATERIAL'
        sp3.overlay.show_wireframes = True
        sp3.region_3d.view_distance = 9.0
        sp3.show_region_ui = False
        bpy.ops.mch.bar_tool(tool='SELECT')
        bpy.ops.mch.side_page(page='MATERIAL')
    xdo('mousemove', 300, 1200)
    yield 40.0                                             # (EEVEE compiles)
    head = yield from scrolled_to(lambda i: i.kind == 'shead' and i.label.startswith('MY MATERIALS'))
    log('MY MATERIALS title at', hover(head), 'open before', head.on)
    yield 0.4
    xdo('click', 1)
    yield 1.5
    btn = yield from scrolled_to(lambda i: i.kind == 'tbtn' and i.label == 'Save Material...')
    log('Save Material... at', hover(btn))
    yield 0.4
    xdo('click', 1)
    yield 2.0
    shot('1_dialog.png')
    xdo('key', 'Return')
    yield 12.0                                             # (the ball picture renders)
    log('after Enter in the dialog: saved', mm.names(), 'picture', bool(mm.icon_path(mm.names()[0]))
        if mm.names() else None)
    with C.temp_override(window=w, area=a, region=r):
        mm.save(bpy.data.materials['My Green Glass'], 'Green Glass')
        for o in C.selected_objects:
            o.select_set(False)
        target.select_set(True)
        C.view_layer.objects.active = target
    yield 1.0
    name = mm.names()[0] if mm.names() else ''
    tile = yield from scrolled_to(lambda i: i.kind == 'mtile' and i.action[:2] == ('op', 'mch.my_material_apply')
                                  and i.action[2].get('name') == name)
    log('its ball at', hover(tile), 'picture', tile.icon[:5] if tile else None)
    yield 0.4
    xdo('click', 1)
    yield 2.0
    tm = target.active_material
    log('ball clicked: Ball\'s material', tm.name if tm else None, 'Mech', bool(tm and tm.get('mch_mech')),
        'blue paint', tuple(round(c, 2) for c in tm.mch_mech.paint_color) if tm and tm.get('mch_mech') else None,
        'a copy (not the box\'s own)', tm is not None and tm != part.active_material)
    xdo('mousemove', 300, 1200)
    yield 25.0
    shot('2_applied.png')
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
