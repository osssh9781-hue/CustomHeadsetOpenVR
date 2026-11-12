"""Real window (0.24.138, user: "백그라운드 이미지가 안 보여", "뒤에 넣는 스튜디오 이미지들 다 어디 갔어?"): the studio
backdrops behind the model on another add-on's HDRI world (Blender's own forest HDRI as the scene's world):
  1. Material Preview, before: Blender's studio light, no picture
  2. a REAL click on Picture (Render tab > BACKGROUND), then on the backdrop "Grey Spot": Material Preview now shows the
     scene's world - the picture behind the parts, the HDRI lighting them (wireframe on)
  3. Rendered (Cycles): the same picture behind, the HDRI's light on the parts
"""
import os
import subprocess
import sys
import time

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'addon'))
import mecha_lab  # noqa: E402
from mecha_lab import side_panel as sp, ui_bars  # noqa: E402
from mecha_lab.ui_gpu import ui_factor  # noqa: E402
from mathutils import Euler  # noqa: E402

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


DRAWS = {'n': 0, 'last': 0.0}


def _count_draw():
    DRAWS['n'] += 1
    DRAWS['last'] = time.perf_counter()


def wait_draws(n, limit=120.0):
    """Until ``n`` more redraws of the 3D view happened (the panel shows what sp.items says)."""
    w, a, r = view3d()
    n0 = DRAWS['n']
    t0 = time.perf_counter()
    while DRAWS['n'] < n0 + n and time.perf_counter() - t0 < limit:
        a.tag_redraw()
        yield 0.1


def view_change_draw(a, rv, angle):
    """Seconds from a view change to the end of the redraw it causes."""
    n0 = DRAWS['n']
    t0 = time.perf_counter()
    rv.view_rotation = Euler((1.0, 0.0, angle)).to_quaternion()
    a.tag_redraw()
    while DRAWS['n'] == n0 and time.perf_counter() - t0 < 120:
        yield 0.01
    return DRAWS['last'] - t0


def press(it):
    w, a, r = view3d()
    x, y = int(r.x + it.x + it.w / 2), int(w.height - (r.y + it.y + it.h / 2))
    xdo('mousemove', x, y)
    yield 0.6
    xdo('click', 1)
    yield 1.0


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
    sp3 = a.spaces.active
    from mecha_lab import bg_color as bgc
    res = {}
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=0.8, location=(-1.0, 0, 0.8))
        bpy.ops.object.shade_smooth()
        bpy.ops.mch.mech_shader_apply(preset='PAINTED')
        bpy.ops.mesh.primitive_cube_add(size=1.2, location=(1.1, 0.2, 0.6))
        bpy.ops.mch.mech_shader_apply(preset='PAINTED')
        # "another add-on's HDRI": the scene's world an Environment Texture of Blender's own forest HDRI
        wd = bpy.data.worlds.new('OtherAddonHDRI')
        wd.use_nodes = True
        nt = wd.node_tree
        env = nt.nodes.new('ShaderNodeTexEnvironment')
        env.image = bpy.data.images.load(os.path.join(bpy.utils.system_resource('DATAFILES', path='studiolights/world'),
                                                      'forest.exr'))
        nt.links.new(env.outputs['Color'], nt.nodes['Background'].inputs['Color'])
        S.world = wd
        bpy.ops.object.camera_add(location=(0.2, -7.0, 2.2), rotation=(1.33, 0.0, 0.03))
        S.camera = C.active_object
        S.render.engine = 'CYCLES'
        S.cycles.device = 'CPU'
        S.cycles.preview_samples = 16
        for o in S.objects:
            o.select_set(False)
        C.view_layer.objects.active = None
        rv = sp3.region_3d
        rv.view_perspective = 'CAMERA'
        sp3.shading.type = 'MATERIAL'
        sp3.overlay.show_wireframes = True
        sp3.show_region_ui = False
        bpy.ops.mch.bar_tool(tool='SELECT')
        bpy.ops.mch.side_page(page='HDRI')
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 20.0
    p0 = shot('1_material_preview_before.png')
    it = yield from scrolled_item('Picture')
    log('Picture cell', it is not None)
    if it is None:
        log('ERROR no Picture cell')
        bpy.ops.wm.quit_blender()
        return
    yield from press(it)
    yield 3.0
    log('after Picture:', 'on', bgc.on(S), 'mode', S.mch_bg.mode, 'picture', bgc.picture_ident(S))
    it = yield from scrolled_item('Grey Spot')
    log('Grey Spot tile', it is not None)
    if it is not None:
        yield from press(it)
    yield 20.0
    st = S.mch_bg
    log('after the tile:', 'on', bgc.on(S), 'mode', st.mode, 'picture', st.image, 'Material Preview scene world',
        sp3.shading.use_scene_world)
    p1 = shot('2_material_preview_picture.png')
    res['2 REAL clicks on Picture and on the backdrop Grey Spot: the picture behind the model, Material Preview on '
        'the scene\'s world'] = bgc.on(S) and st.mode == 'IMAGE' and st.image == 'B:mid_grey_spot_land.jpg' \
        and sp3.shading.use_scene_world
    sp3.shading.type = 'RENDERED'
    n0 = DRAWS['n']
    yield 20.0
    log('Rendered: engine', S.render.engine, 'shading', sp3.shading.type, 'redraws in 20 s', DRAWS['n'] - n0)
    shot('3a_rendered_20s.png')
    yield 100.0
    log('   redraws in 120 s', DRAWS['n'] - n0)
    shot('3_rendered_picture.png')
    sp3.shading.type = 'MATERIAL'
    bpy.types.SpaceView3D.draw_handler_remove(handle, 'WINDOW')
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
