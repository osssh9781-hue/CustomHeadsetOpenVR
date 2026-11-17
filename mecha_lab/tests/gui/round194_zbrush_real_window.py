"""Real window 0.24.194: ZBrush bridge - Send leaves the OBJ path on the clipboard, Find ZBrush / Send say plainly
that no ZBrush is on this machine (none is installed here: the search itself is tested with made-up folders)."""
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
    from mecha_lab import zbrush_bridge as zb
    C = bpy.context
    res = {}
    try:
        w = C.window_manager.windows[0]
        a = next(x for x in w.screen.areas if x.type == 'VIEW_3D')
        r = next(x for x in a.regions if x.type == 'WINDOW')
        with C.temp_override(window=w, area=a, region=r):
            for o in list(C.scene.objects):
                bpy.data.objects.remove(o)
            bpy.ops.mesh.primitive_cube_add()
            found = zb.find_zbrush(fresh=True)
            rr = bpy.ops.mch.zbrush_send()
            clip = C.window_manager.clipboard
            note = zb.launch_zbrush(C.scene.mch_zbrush)
        log('found', repr(found), 'send', rr, 'clipboard', clip, 'note', note)
        res['1 this machine has no ZBrush: the search finds none, Send still finishes'] = found == '' and 'FINISHED' in rr
        res['2 the sent OBJ path is on the clipboard (an existing file)'] = clip.endswith('.obj') and os.path.isfile(clip)
        res['3 the report says ZBrush was not found'] = 'not found' in note
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
