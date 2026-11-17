"""Real window 0.24.195: GoZ (experimental) in a real Blender window - Send writes the .GoZ and the list into a
made-up GoZ folder (no ZBrush on this machine), the file changed as ZBrush would, Auto imports it by itself."""
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
    import tempfile
    import numpy as np
    from mecha_lab import goz_bridge as gz
    C = bpy.context
    res = {}
    try:
        w = C.window_manager.windows[0]
        a = next(x for x in w.screen.areas if x.type == 'VIEW_3D')
        r = next(x for x in a.regions if x.type == 'WINDOW')
        root = tempfile.mkdtemp(prefix='mch_goz_gui_')
        os.makedirs(os.path.join(root, 'GoZBrush'))
        with C.temp_override(window=w, area=a, region=r):
            for o in list(C.scene.objects):
                bpy.data.objects.remove(o)
            C.scene.mch_goz.root = root
            bpy.ops.mesh.primitive_cube_add()
            cube = C.active_object
            r1 = bpy.ops.mch.goz_send()
            rows = gz.listed(root)
            r2 = bpy.ops.mch.goz_watch()
        log('send', r1, 'listed', rows, 'watch', r2, gz.WATCH)
        res['1 Send (GoZ): the .GoZ file and the list written'] = 'FINISHED' in r1 and len(rows) == 1 and os.path.isfile(rows[0])
        d = gz.read_goz(rows[0])
        gz.write_goz(rows[0], d['name'], d['verts'] * 3.0, d['faces'])
        import time
        time.sleep(1.2)
        with open(gz.list_path(root), 'w') as f:
            f.write(rows[0][:-4] + '\n')
        STATE.update(cube=cube.name, root=root)
    except Exception as ex:
        import traceback
        traceback.print_exc()
        log('ERROR', repr(ex))
    RES.update(res)
    bpy.app.timers.register(finish, first_interval=4.0)
    return None


STATE, RES = {}, {}


def finish():
    from mecha_lab import goz_bridge as gz
    try:
        cube = bpy.data.objects[STATE['cube']]
        size = max(cube.dimensions)
        log('after 4 s with Auto on: the cube is', round(size, 3), 'wide (was 2)')
        RES['2 Auto: the changed file ZBrush would write came in by itself (the cube three times as big)'] = abs(size - 6.0) < 1e-3
        bpy.ops.mch.goz_watch()
        RES['3 Auto off again'] = gz.WATCH['on'] is False
    except Exception as ex:
        log('ERROR', repr(ex))
    for k, v in RES.items():
        log(('PASS ' if v else 'FAIL ') + k)
    log(f'{sum(RES.values())}/{len(RES)} passed')
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(run, first_interval=3.0)
