"""Real window 0.24.208: Cloth Drape Stitches - a cloth laid from a mask, Draw Lines pressed on it (the cloth steps aside,
the Wrinkle Lines tool on the body), a line put on the body, Cloth Drape picked again: the cloth is back with the seam.
(The operators are called in a real window; the line itself is written, not dragged.)"""
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
    import json
    import numpy as np
    from mecha_lab import cloth_drape as cd, mesh_io as mio, tool_state as ts, wrinkle_lines as wl
    C = bpy.context
    res = {}
    try:
        w = C.window_manager.windows[0]
        a = next(x for x in w.screen.areas if x.type == 'VIEW_3D')
        r = next(x for x in a.regions if x.type == 'WINDOW')
        with C.temp_override(window=w, area=a, region=r):
            ws = next((x for x in bpy.data.workspaces if x.name.startswith('MECHA LAB')), None)
            if ws is None:
                bpy.ops.mch.workspace_open()
            for o in list(C.scene.objects):
                bpy.data.objects.remove(o)
            bpy.ops.mesh.primitive_grid_add(x_subdivisions=60, y_subdivisions=60, size=2.0)
            body = C.active_object
            co = mio.read_co(body.data)
            att = body.data.attributes.new('.sculpt_mask', 'FLOAT', 'POINT')
            att.data.foreach_set('value', ((np.abs(co[:, 0]) < 0.6) & (np.abs(co[:, 1]) < 0.6)).astype(np.float32))
            st = cd.settings(C)
            st.mask_points = 100000
            st.use_lines, st.line_mode = True, 'STITCH'
            bpy.ops.mch.bar_tool(tool='CDRAPE')
            for o in C.selected_objects:
                o.select_set(False)
            body.select_set(True)
            C.view_layer.objects.active = body
            cd.perform_masked(C, body)
            cloth = bpy.data.objects[cd.SIM['ob']]
            s0 = cd.SIM['sess'].get('stitches', 0)
            r1 = bpy.ops.mch.cdrape_lines()
            hidden = cloth.hide_get()
            tool = ts.effective_tool(C)
            active = C.view_layer.objects.active.name
            pts = [(float(x), 0.0, 0.0) for x in np.linspace(-0.45, 0.45, 12)]
            body[wl.PROP] = json.dumps([dict(pts=pts, nrm=[(0.0, 0.0, 1.0)] * len(pts), strength=1.0)])
            wl._CACHE.pop(body.name, None)
        log('laid: stitched points', s0, '| Draw Lines:', r1, 'cloth hidden', hidden, 'tool', tool, 'active', active)
        res['1 Draw Lines on a laid cloth: the cloth steps aside, the Wrinkle Lines tool is on, the body is the active mesh'] = (
            'FINISHED' in r1 and hidden and tool == 'WLINES' and active == body.name and s0 == 0)
        STATE.update(cloth=cloth.name, w=w, a=a, r=r)
    except Exception as ex:
        import traceback
        traceback.print_exc()
        log('ERROR', repr(ex))
    RES.update(res)
    bpy.app.timers.register(back, first_interval=2.0)
    return None


STATE, RES = {}, {}


def back():
    C = bpy.context
    try:
        from mecha_lab import tool_state as ts
        w = C.window_manager.windows[0]
        a = next(x for x in w.screen.areas if x.type == 'VIEW_3D')
        r = next(x for x in a.regions if x.type == 'WINDOW')
        cloth = bpy.data.objects[STATE['cloth']]
        with C.temp_override(window=w, area=a, region=r):
            still = (cloth.hide_get(), ts.effective_tool(C))
            log('2 s later, still drawing: cloth hidden', still[0], 'tool', still[1])
            RES['1b ... and it stays aside while the lines are being drawn (2 s later)'] = still[0] is True
            bpy.ops.mch.bar_tool(tool='CDRAPE')             # (the user picks Cloth Drape again)
    except Exception as ex:
        log('ERROR', repr(ex))
    bpy.app.timers.register(finish, first_interval=3.0)
    return None


def finish():
    from mecha_lab import cloth_drape as cd
    C = bpy.context
    try:
        cloth = bpy.data.objects[STATE['cloth']]
        n = cd.SIM.get('sess', {}).get('stitches', 0) if cd.sim_active() else -1
        log('Cloth Drape picked again: cloth hidden', cloth.hide_get(), 'active', C.view_layer.objects.active.name,
            'stitched points', n)
        RES['2 Cloth Drape picked again: the cloth is back (shown, active) and its session has the seam'] = (
            not cloth.hide_get() and C.view_layer.objects.active == cloth and n > 10)
    except Exception as ex:
        log('ERROR', repr(ex))
    for k, v in RES.items():
        log(('PASS ' if v else 'FAIL ') + k)
    log(f'{sum(RES.values())}/{len(RES)} passed')
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(run, first_interval=3.0)
