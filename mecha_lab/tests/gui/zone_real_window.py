"""Real window: Lasso Zones (0.24.95 user: "메카닉 할 때 내가 라쏘로 그은 영역 색이랑 재질 다르게 할 수 있나?").
MECHA LAB screen, a box with the Mech Shader (Painted Metal), the Mech page of the drawn side panel: REAL mouse (xdotool)
- the ZONES title (opens it), Paint Zone, then a lasso DRAGGED over the box's front (a zone of its own paint); Split Zone,
then a straight-edged lasso of CLICKED corners + Enter over the top (edges cut, the faces inside a material of their
own); Paint Zone then Esc (cancelled); a shot of each.
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
    from mecha_lab import zones as zn
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
    head = yield from scrolled_to(lambda i: i.kind == 'shead' and i.label.startswith('ZONES'))
    log('ZONES title at', hover(head), 'open before', head.on)
    yield 0.4
    xdo('click', 1)
    yield 1.5
    btn = yield from scrolled_to(lambda i: i.kind == 'tbtn' and i.label == 'Paint Zone')
    log('Paint Zone at', hover(btn))
    yield 0.4
    xdo('click', 1)
    yield 1.0
    from bpy_extras import view3d_utils
    w, a, r = view3d()
    rv3d = r.data

    def scr(co):
        p = view3d_utils.location_3d_to_region_2d(r, rv3d, co)
        return to_x(w, r, p.x, p.y)
    # a lasso dragged over the +X face's top edge (the side and the top both seen: the edge inside the zone)
    ring = [scr((1.0, -0.2 + 0.6 * math.cos(t), 0.75 + 0.45 * math.sin(t))) for t in
            [k * 2 * math.pi / 24 for k in range(25)]]
    xdo('mousemove', *ring[0])
    yield 0.3
    xdo('mousedown', 1)
    yield 0.2
    for p in ring[1:]:
        xdo('mousemove', *p)
        yield 0.05
    xdo('mouseup', 1)
    yield 2.0
    mat = part.active_material
    log('dragged lasso: zones', len(mat.mch_zones), 'projector', mat.mch_zones[0].projector.name if len(mat.mch_zones)
        else None, 'mask', mat.mch_zones[0].mask.size[:] if len(mat.mch_zones) else None)
    # Own Wear: a real click on its switch, then the zone's own chips + rust (the part clean)
    with C.temp_override(window=w, area=a, region=r):
        part.active_material.mch_mech.edge_wear = 0.0
        part.active_material.mch_mech.rust = 0.0
    sw = yield from scrolled_to(lambda i: getattr(i, 'prop', '') == 'own_wear')
    hover(sw)
    yield 0.4
    xdo('click', 1)
    yield 1.0
    z = mat.mch_zones[0]
    log('Own Wear switch clicked:', z.own_wear, 'its sliders on the page',
        sorted({getattr(i, 'prop', '') for i in panel_items()} & {'edge_wear', 'scratches', 'rust', 'dirt'}))
    with C.temp_override(window=w, area=a, region=r):
        z.edge_wear, z.rust, z.scratches = 0.9, 0.45, 0.5
    xdo('mousemove', 300, 1200)
    yield 25.0
    shot('1_paint_zone.png')
    # Split Zone: corners clicked on the top, then Enter
    btn = yield from scrolled_to(lambda i: i.kind == 'tbtn' and i.label == 'Split Zone')
    hover(btn)
    yield 0.4
    xdo('click', 1)
    yield 1.0
    nf = len(part.data.polygons)
    for co in ((-0.6, -0.6, 1.0), (0.6, -0.6, 1.0), (0.6, 0.2, 1.0), (-0.6, 0.2, 1.0)):
        xdo('mousemove', *scr(co))
        yield 0.3
        xdo('click', 1)
        yield 0.5
    xdo('key', 'Return')
    yield 2.0
    me = part.data
    inside = [p for p in me.polygons if p.material_index == 1]
    log('clicked lasso + Enter: faces', nf, '->', len(me.polygons), 'slots', len(part.material_slots),
        'zone faces', len(inside), 'area', round(sum(p.area for p in inside), 3),
        'their height', sorted({round(p.center.z, 3) for p in inside}))
    # Same Wear as the Part: on for the new Split Zone - a real click turns it off, then its own dirt on top
    zm = part.active_material
    sw = yield from scrolled_to(lambda i: getattr(i, 'prop', '') == 'mch_zone_follow')
    log('Split Zone material', zm.name, 'Same Wear', zm.mch_zone_follow, 'switch at', hover(sw))
    yield 0.4
    xdo('click', 1)
    yield 1.0
    with C.temp_override(window=w, area=a, region=r):
        zm.mch_mech.dirt_top = 1.0
        zm.mch_mech.edge_wear = 0.6
    log('... after the click: Same Wear', zm.mch_zone_follow, 'zone dirt on top', zm.mch_mech.dirt_top,
        'part dirt on top', mat.mch_mech.dirt_top)
    xdo('mousemove', 300, 1200)
    yield 25.0
    shot('2_split_zone.png')
    # Esc cancels
    with C.temp_override(window=w, area=a, region=r):
        part.active_material_index = 0
    yield 1.0
    btn = yield from scrolled_to(lambda i: i.kind == 'tbtn' and i.label == 'Paint Zone')
    hover(btn)
    yield 0.4
    xdo('click', 1)
    yield 1.0
    xdo('mousemove', *scr((1.0, 0.5, 0.5)))
    yield 0.3
    xdo('click', 1)
    yield 0.3
    xdo('key', 'Escape')
    yield 1.5
    log('Paint Zone then Esc: zones', len(part.material_slots[0].material.mch_zones))
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
