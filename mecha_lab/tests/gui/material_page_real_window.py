"""Real window: the Material page of Mecha Lab's own side panel (0.24.95 user: "우리 예쁘게 만든 우리의 유아이가 이미
메카 랩에 있는데 왜 다시 블렌더 기본 패널로 바꿨어").  MECHA LAB screen, a part with Chipped Paint, the interior HDRI
(blurred) in Material Preview with the wireframe over it; the Material page opened through the Mecha Menu's button
(the operator), then REAL mouse clicks (xdotool): ▶ on the preset, the DIRT title (opens it), a drag on Roughness,
the Base Color swatch (the colour picker opens); shots of each.
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
from mecha_lab import mech_shader as ms, side_panel as sp, ui_bars  # noqa: E402
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


def top_of_rows():
    lay = layout()
    return lay['clip'][1] + lay['clip'][3]


def layout():
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        return sp.layout(C, r.width, r.height, ui_factor(C, r))


def scrolled_to(pred):
    """Scroll the panel down until an item is in its window (a real user scrolls with the wheel)."""
    for _n in range(40):
        it = find(pred)
        if it is not None:
            return it
        scroll(60)
        yield 0.3
    return None


def shot(name):
    path = os.path.join(OUT, name)
    os.system(f'import -window root "{path}"')       # (Blender's own GL screenshot is black under software GL)
    log('shot', name, os.path.exists(path))


def click(it):
    w, a, r = view3d()
    x, y = to_x(w, r, it.x + it.w / 2, it.y + it.h / 2)
    xdo('mousemove', x, y)
    return x, y


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
        bpy.ops.mesh.primitive_cube_add(size=2.0)
        ob = C.active_object
        bv = ob.modifiers.new('b', 'BEVEL')
        bv.width, bv.segments = 0.08, 3
        sub = ob.modifiers.new('s', 'SUBSURF')
        sub.levels = 2
        bpy.ops.object.convert(target='MESH')
        bpy.ops.object.shade_smooth()
        r1 = bpy.ops.mch.mech_shader_apply(preset='CHIPPED')
        S.mch_mech_hdri = 'interior.exr'
        S.mch_mech_hdri_rot = math.radians(90)
        S.mch_mech_hdri_blur = 0.5
        r2 = bpy.ops.mch.mech_hdri(action='SET')
        sp3 = a.spaces.active
        sp3.shading.type = 'MATERIAL'
        sp3.overlay.show_wireframes = True                # (the wireframe always shown with the model)
        sp3.region_3d.view_distance = 6.5
        sidebar = next((rg for rg in a.regions if rg.type == 'UI'), None)
        log('apply', r1, 'hdri', r2, 'material', ob.active_material.name, 'sidebar width',
            sidebar.width if sidebar else None)
        sp3.show_region_ui = False                        # (the drawn panel shows while the sidebar (N) is closed)
        bpy.ops.mch.bar_tool(tool='SELECT')
        r3 = bpy.ops.mch.side_page(page='MATERIAL')        # (what the Mecha Menu's Material button runs)
        log('side_page', r3, 'page', sp.page(C), 'panel on', sp.on(C))
    xdo('mousemove', 300, 1200)
    yield 45.0                                             # (Material Preview: EEVEE compiles its shaders)
    with C.temp_override(window=w, area=a, region=r):
        log('panel on', sp.on(C), 'page', sp.page(C), 'tool', __import__('mecha_lab').tool_state.effective_tool(C))
    shot('1_material_page.png')

    # REAL clicks: ▶ steps the preset
    st = ms.active_mech(C).mch_mech
    nxt = find(lambda i: i.kind == 'tbtn' and i.label == '▶' and i.action and i.action[2].get('prop') == 'preset')
    before = st.preset
    log('next button at', click(nxt))
    yield 0.4
    xdo('click', 1)
    yield 2.5
    log('real click ▶: preset', before, '->', st.preset)
    st.preset = 'CHIPPED'                                  # (back: the shots below on Chipped Paint)
    yield 3.0
    # a real drag on Roughness
    rough = find(lambda i: i.kind == 'mini' and i.prop == 'roughness')
    r0 = st.roughness
    x, y = click(rough)
    yield 0.4
    xdo('mousedown', 1)
    yield 0.2
    for dx in range(10, 130, 10):
        xdo('mousemove', x + dx, y)
        yield 0.05
    xdo('mouseup', 1)
    yield 1.5
    log('real drag Roughness:', round(r0, 3), '->', round(st.roughness, 3))
    # the Base Color swatch: a real click opens the colour picker
    swatch = find(lambda i: i.kind == 'swatch' and i.prop == 'base_color')
    log('swatch at', click(swatch))
    yield 0.4
    xdo('click', 1)
    yield 3.0
    log('colour popup edits', ui_bars.EDIT[1])
    shot('2_color_picker.png')
    xdo('mousemove', 300, 1200)                            # (the popup closes when the mouse leaves it)
    yield 1.0
    xdo('key', 'Escape')
    yield 1.0
    # the DIRT title (scrolled to): a real click opens the section
    dirt = yield from scrolled_to(lambda i: i.kind == 'shead' and i.label.startswith('DIRT'))
    log('DIRT title at', click(dirt), 'open before', dirt.on)
    yield 0.4
    xdo('click', 1)
    yield 1.5
    dirt2 = find(lambda i: i.kind == 'shead' and i.label.startswith('DIRT'))
    log('real click DIRT: open now', dirt2.on if dirt2 else None,
        'rows', sorted({i.prop for i in panel_items() if getattr(i, 'prop', '').startswith('dirt')}))
    xdo('mousemove', 300, 1200)
    yield 1.0
    scroll(top_of_rows() - (dirt2.y + dirt2.h) if dirt2 else 0)
    yield 1.5
    shot('3_dirt_open.png')
    # the Edge Wear section (open on Chipped Paint): a real click on ▶ of its presets
    scroll(-5000)
    yield 0.5
    wnext = yield from scrolled_to(lambda i: i.kind == 'tbtn' and i.label == '▶' and i.action
                                   and i.action[2].get('prop') == 'wear_preset')
    w0 = st.wear_preset
    log('wear ▶ at', click(wnext))
    yield 0.4
    xdo('click', 1)
    yield 2.0
    log('real click wear ▶:', w0, '->', st.wear_preset, 'edge_wear', round(st.edge_wear, 2))
    st.wear_preset = 'BRASS'
    yield 2.0
    head = find(lambda i: i.kind == 'shead' and i.label.startswith('EDGE WEAR'))
    scroll(top_of_rows() - (head.y + head.h) if head else 0)
    xdo('mousemove', 300, 1200)
    yield 3.0
    shot('4_edge_wear.png')
    # the HDRI tab: a real click - the HDRI page apart from the material
    tab = find(lambda i: i.kind == 'ptab' and i.label == 'HDRI')
    log('HDRI tab at', click(tab))
    yield 0.4
    xdo('click', 1)
    yield 2.0
    log('real click HDRI tab: page', sp.page(C), 'rows',
        sorted({i.prop for i in panel_items() if getattr(i, 'prop', '').startswith('mch_mech')}))
    xdo('mousemove', 300, 1200)
    yield 1.5
    shot('5_hdri_page.png')
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
