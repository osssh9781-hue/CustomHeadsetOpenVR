"""Real window: Decals (0.24.95 user: "데칼 - 번호, 경고 줄무늬, 로고를 표면에 붙이는 기능"; "추가 데칼이야! 이거도 추가해
줘 / 이건 데칼 탭으로 가자! 메테리얼도 크리쳐랑 메카닉이랑 좀 분리해 줘").  MECHA LAB screen, a part with the Mech
Shader, the drawn side panel on the Mech page: REAL mouse clicks (xdotool) - the Decals tab, the Sci-Fi Radiation ball,
then a click on the part (the decal lands where clicked, wrapped on; its settings on the Decals page); the Creature tab
(skin types, a note that the part's material is a Mech one); the Decals tab, the two-tone Warning ball then Esc
(cancelled: no decal); a shot of each.
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


def decal_objects():
    return [o for o in bpy.data.objects if dc.is_decal(o)]


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
        part = C.active_object
        part.name = 'Part'
        bpy.ops.mch.mech_shader_apply(preset='PAINTED')
        sp3 = a.spaces.active
        sp3.shading.type = 'MATERIAL'
        sp3.overlay.show_wireframes = True
        sp3.region_3d.view_distance = 7.0
        sp3.show_region_ui = False
        bpy.ops.mch.bar_tool(tool='SELECT')
        bpy.ops.mch.side_page(page='MATERIAL')
    xdo('mousemove', 300, 1200)
    yield 40.0                                             # (EEVEE compiles)
    with C.temp_override(window=w, area=a, region=r):
        log('panel on', sp.on(C), 'page', sp.page(C), 'sidebar', a.spaces.active.show_region_ui,
            'heads', [i.label.split('   ')[0] for i in panel_items() if i.kind == 'shead'])
    log('tabs', [(i.label, i.on) for i in panel_items() if i.kind == 'ptab'])
    shot('0_mech_page.png')
    # the Decals tab: a real click shows the Decals page
    tab = find(lambda i: i.kind == 'ptab' and i.label == 'Decals')
    log('Decals tab at', hover(tab))
    yield 0.4
    xdo('click', 1)
    yield 1.5
    log('page after the click', sp.page(C), 'heads', [i.label.split('   ')[0] for i in panel_items()
                                                      if i.kind == 'shead'])
    shot('1_decals_page.png')
    tile = yield from scrolled_to(lambda i: i.kind == 'mtile' and i.action[:2] == ('op', 'mch.decal_place')
                                  and i.action[2].get('decal') == 'SF_RADIATION')
    log('Sci-Fi Radiation ball at', hover(tile))
    yield 0.4
    xdo('click', 1)
    yield 1.0
    # then a real click on the part's front face (projected into the window)
    from bpy_extras import view3d_utils
    w, a, r = view3d()
    rv3d = r.data
    p2 = view3d_utils.location_3d_to_region_2d(r, rv3d, (0.0, 0.0, 0.0))   # (the part's middle: the face in front)
    log('view', tuple(round(v, 2) for v in rv3d.view_rotation), round(rv3d.view_distance, 2), 'part at', p2)
    if p2 is None:
        p2 = type('P', (), {'x': r.width / 2, 'y': r.height / 2})
    x, y = to_x(w, r, p2.x, p2.y)
    xdo('mousemove', x, y)
    yield 0.5
    shot('2_placing.png')
    xdo('click', 1)
    yield 2.0
    decs = decal_objects()
    d = decs[0] if decs else None
    log('real click on the part: decals', len(decs), 'parent', d.parent.name if d and d.parent else None,
        'at', tuple(round(v, 3) for v in d.matrix_world.translation) if d else None,
        'facing', tuple(round(v, 3) for v in d.matrix_world.to_3x3().col[2]) if d else None)
    if d is not None:
        log('its look: kind', d.mch_decal.kind, 'picture', d.active_material.node_tree.nodes['mch:img:decal'].image.name,
            d.active_material.node_tree.nodes['mch:img:decal'].image.colorspace_settings.name)
    with C.temp_override(window=w, area=a, region=r):
        sp.scroll_by(C, r.width, r.height, ui_factor(C, r), -100000)
    xdo('mousemove', 300, 1200)
    yield 25.0
    log('page with the decal selected: heads', [i.label.split('   ')[0] for i in panel_items() if i.kind == 'shead'],
        'props', sorted({getattr(i, 'prop', '') for i in panel_items()} - {''})[:12])
    shot('3_placed.png')
    # 0.24.95 (user: "데칼은 회전도 넣어 줘") a real drag on its Rotation bar
    bar = yield from scrolled_to(lambda i: getattr(i, 'prop', '') == 'rotation')
    bx, by = hover(bar)
    m0 = d.matrix_world.to_3x3().col[0].copy() if d else None
    yield 0.3
    xdo('mousedown', 1)
    yield 0.2
    for dx in range(0, 91, 10):
        xdo('mousemove', bx + dx, by)
        yield 0.05
    xdo('mouseup', 1)
    yield 1.0
    if d is not None:
        import math as _m
        m1 = d.matrix_world.to_3x3().col[0]
        log('Rotation bar dragged: rotation', round(_m.degrees(d.mch_decal.rotation), 1), 'deg; its width axis turned',
            round(_m.degrees(m0.angle(m1)), 1), 'deg; still on the part', d.parent.name if d.parent else None)
    xdo('mousemove', 300, 1200)
    yield 15.0
    shot('3b_rotated.png')
    # the Creature tab (the part selected: its material is a Mech one - a note + the skin types)
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        for o in C.selected_objects:
            o.select_set(False)
        bpy.data.objects['Part'].select_set(True)
        bpy.context.view_layer.objects.active = bpy.data.objects['Part']
    yield 1.0
    tab = find(lambda i: i.kind == 'ptab' and i.label == 'Creature')
    hover(tab)
    yield 0.4
    xdo('click', 1)
    yield 1.5
    log('Creature tab: page', sp.page(C), 'heads', [i.label.split('   ')[0] for i in panel_items()
                                                    if i.kind == 'shead'],
        'notes', [i.label for i in panel_items() if i.kind == 'pnote'][:2])
    xdo('mousemove', 300, 1200)
    yield 2.0
    shot('4_creature_page.png')
    # Esc cancels: the Decals tab, the two-tone Warning ball, then Esc - no new decal
    tab = find(lambda i: i.kind == 'ptab' and i.label == 'Decals')
    hover(tab)
    yield 0.4
    xdo('click', 1)
    yield 1.0
    tile = yield from scrolled_to(lambda i: i.kind == 'mtile' and i.label == 'Warning')
    hover(tile)
    yield 0.4
    xdo('click', 1)
    yield 1.0
    xdo('mousemove', x, y)
    yield 0.4
    xdo('key', 'Escape')
    yield 1.5
    log('Warning then Esc: decals', len(decal_objects()))
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
