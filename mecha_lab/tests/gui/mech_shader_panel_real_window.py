"""Real window: the Mech Shader panel as the user sees it (0.24.95 user: "메테리얼 뷰포트 프리셋 슬라이드에서 베이스 컬러,
러프니스, 메탈릭, 유리 재질, 알파 다 만질 수 있게 해 주고, 그거도 한번 먼저 보여 주고").  A part with a Mech material
(Clear Glass: Glass on shows IOR), Material Preview with an HDRI behind it (blurred), the panel opened at the mouse
(wm.call_panel) and screenshot; a second shot with Chipped Paint for the paint / dirt / snow rows.
    blender --window-geometry 0 0 W H --python this.py -- OUT"""
import os
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
from mecha_lab import mech_shader as ms  # noqa: E402
C = bpy.context
S = C.scene


def view3d():
    for w in C.window_manager.windows:
        for a in w.screen.areas:
            if a.type == 'VIEW_3D':
                return w, a, next(r for r in a.regions if r.type == 'WINDOW')
    return None, None, None


def flow():
    yield 1.5
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
        r1 = bpy.ops.mch.mech_shader_apply(preset='GLASS')
        S.mch_mech_hdri = 'courtyard.exr'
        S.mch_mech_hdri_blur = 0.5
        r2 = bpy.ops.mch.mech_hdri(action='SET')
        a.spaces[0].shading.type = 'MATERIAL'
        a.spaces[0].region_3d.view_distance = 7.0
        log('apply', r1, 'hdri', r2, 'material', ob.active_material.name)
    yield 2.0
    for name, preset in (('panel_glass.png', 'GLASS'), ('panel_chipped.png', 'CHIPPED')):
        w, a, r = view3d()
        ob = C.active_object
        ms.active_mech(C).mch_mech.preset = preset
        w.cursor_warp(int(w.width * 0.62), int(w.height * 0.97))
        with C.temp_override(window=w, area=a, region=r):
            res = bpy.ops.wm.call_panel(name='MCH_PT_mech_shader', keep_open=True)
        log('panel', preset, res)
        yield 2.5
        path = os.path.join(OUT, name)
        os.system(f'import -window root "{path}"')          # (the X screen: Blender's own GL screenshot is black
        log('shot', name, os.path.exists(path))              #  under software GL on a virtual screen)
        yield 0.5
        try:
            bpy.ops.wm.call_panel  # (the popup closes when the mouse leaves; move it away)
            w.cursor_warp(5, 5)
        except Exception:
            pass
        yield 1.0
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
