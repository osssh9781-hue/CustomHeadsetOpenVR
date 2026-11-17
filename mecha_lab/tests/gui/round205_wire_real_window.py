"""Real window 0.24.205: one wireframe for both screens - the ZBRUSH screen's PolyF switched off by MECHA LAB's Wire,
and MECHA LAB's Wire switched off by PolyF (the operators called in a real 3D view)."""
import os
import sys

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'addon'))
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


def run():
    from mecha_lab import zb_sculpt as zs
    C = bpy.context
    res = {}
    try:
        w = C.window_manager.windows[0]
        a = next(x for x in w.screen.areas if x.type == 'VIEW_3D')
        r = next(x for x in a.regions if x.type == 'WINDOW')
        ov = a.spaces.active.overlay
        with C.temp_override(window=w, area=a, region=r):
            for o in list(C.scene.objects):
                bpy.data.objects.remove(o)
            bpy.ops.mesh.primitive_cube_add()
            cube = C.active_object
            zb = C.scene.mch_zb
            ov.show_wireframes = False
            zb.polyf = True                                # (the ZBRUSH screen's PolyF)
            s1 = (ov.show_wireframes, zs.wire_on(C))
            bpy.ops.mch.view_toggle(action='WIRE')         # (MECHA LAB's Wire button)
            s2 = (ov.show_wireframes, cube.show_wire, zb.polyf, zs.wire_on(C))
            bpy.ops.mch.view_toggle(action='WIRE')
            s3 = (ov.show_wireframes, cube.show_wire, zb.polyf, zs.wire_on(C))
            zb.polyf = False
            s4 = (ov.show_wireframes, cube.show_wire, zb.polyf, zs.wire_on(C))
        log('PolyF on:', s1, '| Wire pressed:', s2, '| Wire pressed again:', s3, '| PolyF off:', s4)
        res['1 PolyF on in the ZBRUSH screen: MECHA LAB\'s Wire button shows it as on'] = s1 == (True, True)
        res['2 Wire pressed in MECHA LAB: the PolyF wireframe is off (PolyF reads off too)'] = s2 == (False, False, False, False)
        res['3 Wire pressed again: the part\'s wire on - and PolyF reads on in the ZBRUSH screen'] = s3 == (False, True, True, True)
        res['4 PolyF switched off in the ZBRUSH screen: the part\'s wire is off too'] = s4 == (False, False, False, False)
    except Exception as ex:
        import traceback
        traceback.print_exc()
        log('ERROR', repr(ex))
    for k, v in res.items():
        log(('PASS ' if v else 'FAIL ') + k)
    log(f'{sum(res.values())}/{len(res)} passed')
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(run, first_interval=3.0)
