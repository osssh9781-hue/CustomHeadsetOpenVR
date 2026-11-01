"""Real window: ClayBuildup build-up (0.24.95 user: "지브러시에서는 ㄹㅇ 빌드업이 돼서 계속 올라오는데 블렌더는 안 그래").
A 240 x 240 grid seen from the top (orthographic), ZBrush tab brush ClayBuildup (Blender Clay Strips, 40 px), scripted
strokes (sculpt.brush_stroke, pressure 1): one stroke going back and forth 1 / 3 / 6 times over the same line, and
3 / 6 separate strokes; the height reached (max, mm) and the strip's cross-section.  Configs: the add-on's defaults
and the old ones (or CB_CONFIGS, a JSON list of {name, brush setting: value}).
    blender --window-geometry 0 0 1600 1000 --python this.py -- OUT"""
import os, sys, json
import bpy
import numpy as np
from bpy_extras import view3d_utils
sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/addon')
import mecha_lab
OUT = sys.argv[-1]; os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, 'log.txt'), 'w')
def log(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); LOG.write(s + '\n'); LOG.flush()
mecha_lab.register()
from mecha_lab import zb_sculpt as zs
C = bpy.context; S = C.scene
CONFIGS = json.loads(os.environ.get('CB_CONFIGS', '[]')) or [
    {'name': 'ClayBuildup now (the add-on\'s defaults)'},
    {'name': 'before 0.24.95 (Accu off, plane 0.15, strength 0.55)', 'use_accumulate': False, 'plane_offset': 0.15,
     'strength': 0.55}]

def view3d():
    for w in C.window_manager.windows:
        for a in w.screen.areas:
            if a.type == 'VIEW_3D':
                return w, a, next(r for r in a.regions if r.type == 'WINDOW')

def make_plane():
    for o in list(S.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=240, y_subdivisions=240, size=2.0)
    return C.active_object

def heights(ob):
    co = np.empty(len(ob.data.vertices) * 3); ob.data.vertices.foreach_get('co', co)
    return co.reshape(-1, 3)

def stroke_pts(r, rv3d, passes, y_px, x0, x1, step=3):
    pts = []
    xs = list(range(x0, x1 + 1, step))
    for p in range(passes):
        seq = xs if p % 2 == 0 else xs[::-1]
        pts += seq if p == 0 else seq[1:]
    out = []
    for i, x in enumerate(pts):
        loc = view3d_utils.region_2d_to_location_3d(r, rv3d, (x, y_px), (0, 0, 0))
        out.append({'name': '', 'location': loc, 'mouse': (x, y_px), 'mouse_event': (x, y_px),
                    'is_start': i == 0, 'pressure': 1.0, 'size': 40.0, 'time': i * 0.01, 'x_tilt': 0.0,
                    'y_tilt': 0.0})
    return out

def flow():
    w, a, r = view3d()
    yield 1.0
    rv3d = a.spaces.active.region_3d
    results = {}
    for cfg in CONFIGS:
        name = cfg.pop('name')
        with C.temp_override(window=w, area=a, region=r):
            if C.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            ob = make_plane()
            bpy.ops.view3d.view_axis(type='TOP')
            rv3d.view_perspective = 'ORTHO'
            rv3d.view_location = (0, 0, 0)
            rv3d.view_distance = 3.0
            bpy.ops.object.mode_set(mode='SCULPT')
            msg = zs.activate(C, 'ClayBuildup')
            b = zs.brush(C)
            ups = zs.unified(C)
            for k, v in cfg.items():
                setattr(b, k, v)
            if ups is not None and getattr(ups, 'use_unified_size', False):
                ups.size = 40
            b.size = 40
        yield 0.5
        row = []
        cx, cy = r.width // 2, r.height // 2
        for label, passes, strokes in (('1 pass', 1, 1), ('3 passes, one stroke', 3, 1),
                                       ('6 passes, one stroke', 6, 1), ('3 strokes', 1, 3), ('6 strokes', 1, 6)):
            with C.temp_override(window=w, area=a, region=r):
                bpy.ops.object.mode_set(mode='OBJECT')
                ob = make_plane()
                bpy.ops.object.mode_set(mode='SCULPT')
                z0 = heights(ob)[:, 2].copy()
                for _s in range(strokes):
                    res = bpy.ops.sculpt.brush_stroke(stroke=stroke_pts(r, rv3d, passes, cy, cx - 120, cx + 120),
                                                      mode='NORMAL')
                bpy.ops.object.mode_set(mode='OBJECT')
                co = heights(ob)
                z = co[:, 2] - z0
                if label == '3 passes, one stroke':      # the cross-section across the strip at its middle
                    mid = np.abs(co[:, 0]) < 0.006
                    ys, zs_ = co[mid, 1], z[mid]
                    order = np.argsort(ys)
                    ys, zs_ = ys[order], zs_[order]
                    peak = zs_.max()
                    half = ys[zs_ > peak * 0.5]
                    flat = ys[zs_ > peak * 0.9]
                    prof = ' '.join(f'{v * 1000:.0f}' for v in np.interp(np.linspace(-0.12, 0.12, 13), ys, zs_))
                    log('      profile (mm, -0.12 .. 0.12):', prof, '| width at half', round(float(np.ptp(half)) * 1000),
                        'top (90 %) width', round(float(np.ptp(flat)) * 1000))
            row.append((label, round(float(z.max()) * 1000, 2), round(float(np.percentile(z[z > 1e-5], 90)) * 1000, 2)
                        if (z > 1e-5).any() else 0.0, sorted(res)))
            yield 0.2
        log(name, 'brush', b.name, 'accu', b.use_accumulate, 'strength', round(b.strength, 2), 'offset',
            round(b.plane_offset, 2), 'size', b.size)
        for lab, mx, p90, res in row:
            log('   ', lab, ': max', mx, 'mm  (90th pct', p90, 'mm)', res)
        results[name] = row
    json.dump(results, open(os.path.join(OUT, 'results.json'), 'w'))
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
        import traceback; traceback.print_exc(); log('ERROR', repr(ex)); bpy.ops.wm.quit_blender(); return None
bpy.app.timers.register(run, first_interval=2.0)
