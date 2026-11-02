"""Real window (0.24.95 user: "또 안 돼 - 뒤로 갔다 앞으로 다시 가면 생겨", "왜 이번 거 다시 시메트리가 안 돼?"): a cube
with Titanium Cermet in Material Preview (MCH_MIRROR=1: with Mecha Lab's Mirror, no Bisect), a Paint Zone added
(zones.add_paint_zone, the view's own matrices); screenshots after the zone and after undo + redo (OUT/after_zone.png,
after_undo.png) - the pixels on the drawn half and the mirrored half read from them (SCREEN lines give where).
    blender --window-geometry 0 0 2560 1600 --python this.py -- OUT"""
import bpy, sys, os, math, subprocess
import bpy, sys, os, math, subprocess
sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/addon')
import mecha_lab
from mathutils import Vector
OUT = sys.argv[sys.argv.index('--') + 1]
LOG = open(os.path.join(OUT, 'log.txt'), 'w')
def log(*a):
    s = ' '.join(map(str, a)); print(s, flush=True); LOG.write(s + '\n'); LOG.flush()
mecha_lab.register()
from mecha_lab import zones as zn
C = bpy.context
FIX = os.environ.get('MCH_FIX') == '1'
def view3d():
    for w in C.window_manager.windows:
        for a in w.screen.areas:
            if a.type == 'VIEW_3D':
                return w, a, next(r for r in a.regions if r.type == 'WINDOW')
SEEN = {}
def _read():
    import gpu
    if 'xy' not in SEEN or bpy.context.region is None or bpy.context.region.type != 'WINDOW':
        return
    fb = gpu.state.active_framebuffer_get(); vx, vy, vw, vh = gpu.state.viewport_get()
    x, y = SEEN['xy']
    buf = fb.read_color(vx + int(x), vy + int(y), 1, 1, 4, 0, 'FLOAT')
    SEEN['rgb'] = [round(v, 3) for v in buf.to_list()[0][0][:3]]
bpy.types.SpaceView3D.draw_handler_add(_read, (), 'WINDOW', 'POST_PIXEL')
def pixel(x, y):
    return SEEN.get('rgb')
def flow():
    subprocess.run(['xdotool', 'mousemove', '800', '500'])
    subprocess.run(['xdotool', 'key', 'Escape'])
    yield 1.0
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        for o in list(C.scene.objects): bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-0.8, 0.0, 0.0))
        ob = C.active_object
        bpy.ops.mch.mech_shader_apply(preset='CERMET')
        if os.environ.get('MCH_MIRROR'):
            from mecha_lab import symmetry as sy
            sy.set_mode(C, ob, 'MIRROR')
            m = sy.mirror_mod(ob)
            for i in range(3):
                m.use_bisect_axis[i] = False
        sp3 = a.spaces.active
        sp3.shading.type = 'MATERIAL'
        sp3.overlay.show_overlays = False
        rv = sp3.region_3d; rv.view_perspective = 'PERSP'
        rv.view_rotation = Vector((0, 1, 0)).to_track_quat('-Z', 'Z'); rv.view_location = (0, 0, 0); rv.view_distance = 5.5
    yield 25.0
    w, a, r = view3d(); rv3d = r.data
    vm = rv3d.view_matrix.copy(); wm = rv3d.window_matrix.copy()
    from bpy_extras import view3d_utils as vu
    def px(co):
        p = vu.location_3d_to_region_2d(r, rv3d, Vector(co)); return (p.x, p.y)
    pts = [px(c) for c in ((-1.1, -0.5, -0.3), (-0.5, -0.5, -0.3), (-0.5, -0.5, 0.3), (-1.1, -0.5, 0.3))]
    cx, cy = px((0.15, -0.5, 0.12))
    SEEN['xy'] = (cx, cy); a.tag_redraw()
    yield 3.0
    X, Y = cx, cy
    log('before zone, centre pixel', pixel(X, Y), 'pid', ob_pid())
    with C.temp_override(window=w, area=a, region=r):
        z = zn.add_paint_zone(C, C.active_object, pts, vm, wm, True, r.width, r.height, color=(0.85, 0.6, 0.05))
    log('zone added; pid now', ob_pid(), 'fix', FIX)
    if FIX:
        C.active_object.update_tag(refresh={'OBJECT'})
    for _k in range(5):
        yield 5.0
        a.tag_redraw()
    log('after zone (25 s)')
    from bpy_extras import view3d_utils as vu
    for nm, co in (('left (drawn)', (-0.8, -0.5, 0.1)), ('right (mirror)', (0.8, -0.5, 0.1))):
        q = vu.location_3d_to_region_2d(r, rv3d, Vector(co))
        log('SCREEN', nm, int(r.x + q.x), int(w.height - (r.y + q.y)))
    os.system(f'import -window root "{OUT}/after_zone.png"')
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.ed.undo_push(message='x')
        bpy.ops.ed.undo()
        bpy.ops.ed.redo()
    for _k in range(5):
        yield 5.0
        w, a, r = view3d(); a.tag_redraw()
    log('after undo + redo, centre pixel', pixel(X, Y))
    os.system(f'import -window root "{OUT}/after_undo.png"')
    bpy.ops.wm.quit_blender()
def ob_pid():
    o = C.active_object
    return o.get(zn.ZONE_ID) if o else None
gen = None
def run():
    global gen
    try:
        if gen is None: gen = flow()
        return next(gen)
    except StopIteration:
        return None
    except Exception as ex:
        import traceback; traceback.print_exc(); log('ERROR', repr(ex)); bpy.ops.wm.quit_blender()
bpy.app.timers.register(run, first_interval=3.0)
