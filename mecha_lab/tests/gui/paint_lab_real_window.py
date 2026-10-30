"""Real window: Paint Lab - switch to the PAINT screen, a photo loaded as the stencil, Q (real key) toggles it,
a REAL mouse stroke with the Paint brush colours the sphere, Alt + click reads the polypaint colour back,
Mask by Brightness, then a workbench render of the painted sphere."""
import bpy, sys, os, math, subprocess
sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/addon')
import numpy as np
import mecha_lab
OUT = sys.argv[-1]; os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, 'log.txt'), 'w')
def log(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); LOG.write(s + '\n'); LOG.flush()
mecha_lab.register()
from mecha_lab import zb_sculpt as zs, paint_lab as pl
C = bpy.context; S = C.scene
for o in list(S.objects): bpy.data.objects.remove(o)
def xdo(*args): subprocess.run(['xdotool', *map(str, args)], check=False)
def focus():
    r = subprocess.run(['xdotool', 'search', '--name', 'Blender'], capture_output=True, text=True)
    for wid in r.stdout.split(): subprocess.run(['xdotool', 'windowfocus', '--sync', wid], check=False)
def view3d():
    for w in C.window_manager.windows:
        for a in w.screen.areas:
            if a.type == 'VIEW_3D':
                return w, a, next(r for r in a.regions if r.type == 'WINDOW')
    return None, None, None
def to_x(w, r, x, y): return int(r.x + x), int(w.height - (r.y + y))
def colours(ob):
    att = pl.colour_attribute(ob.data); n = len(att.data); v = np.zeros(n * 4, np.float32); att.data.foreach_get('color', v); return v.reshape(-1, 4)

def flow():
    w, a, r = view3d()
    focus(); xdo('mousemove', 30, 540); yield 0.3; xdo('key', 'Escape'); yield 0.5
    with C.temp_override(window=w, area=a, region=r):
        ws = next((x for x in bpy.data.workspaces if x.name.startswith('MECHA LAB')), None)
        if ws is None:
            bpy.ops.mch.workspace_open(); ws = next((x for x in bpy.data.workspaces if x.name.startswith('MECHA LAB')), None)
        w.workspace = ws
    yield 2.0
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=128, ring_count=64); ob = C.active_object
        for p in ob.data.polygons: p.use_smooth = True
        bpy.ops.view3d.view_axis(type='FRONT'); bpy.ops.view3d.view_all(); bpy.ops.view3d.zoom(delta=2)
        res = bpy.ops.mch.zb_switch(target='PAINT')
    log('switch PAINT', res, 'mode', C.mode, 'flag', pl.flag(C), 'on', pl.on(C), 'brush', zs.zb_name(zs.brush(C)))
    sp = a.spaces.active
    log('look', sp.shading.type, sp.shading.light, sp.shading.studio_light, sp.shading.color_type, S.view_settings.view_transform)
    yield 1.0
    # a photo: colour stripes, saved and loaded through the operator
    img = bpy.data.images.new('stripes', 256, 128, alpha=True); px = np.zeros((128, 256, 4), np.float32)
    for i in range(8): px[:, i * 32:(i + 1) * 32, :3] = [(i % 3 == 0), (i % 3 == 1), (i % 3 == 2)]
    px[..., 3] = 1; img.pixels.foreach_set(px.ravel()); path = os.path.join(OUT, 'stripes.png'); img.filepath_raw = path; img.file_format = 'PNG'; img.save()
    with C.temp_override(window=w, area=a, region=r):
        res = bpy.ops.mch.paint_load_photo(filepath=path)
    st = S.mch_paint; b = zs.brush(C)
    log('load photo', res, 'photo', st.photo.name if st.photo else None, 'tex', b.texture_slot.texture.name if b.texture_slot.texture else None, 'linked', b.texture_slot.texture.library is not None if b.texture_slot.texture else None, 'map', b.texture_slot.map_mode)
    st.hue = 120; yield 0.6
    stim = pl.stencil_image(); log('hue 120 rebaked: first stripe (was red) ->', [round(v, 2) for v in stim.pixels[:3]])
    # Q (a real key) toggles the stencil
    cx, cy = r.width // 2, r.height // 2
    xdo('mousemove', *to_x(w, r, cx, cy)); yield 0.2
    xdo('key', 'q'); yield 0.6
    log('Q pressed: stencil_on', st.stencil_on, 'map', b.texture_slot.map_mode, 'pos', tuple(round(v) for v in b.stencil_pos), 'dim', tuple(round(v) for v in b.stencil_dimension))
    bpy.ops.screen.screenshot(filepath=os.path.join(OUT, 'stencil_screen.png'))
    xdo('key', 'q'); yield 0.6
    log('Q again: stencil_on', st.stencil_on, 'map', b.texture_slot.map_mode)
    # a real stroke with the Paint brush in red
    pl.set_brush_colour(C, (1.0, 0.1, 0.1))
    u = zs.unified(C)
    if u is not None and u.use_unified_size: u.size = 90
    else: b.size = 90
    c0 = colours(ob)
    x0, y0 = to_x(w, r, cx - 120, cy + 60)
    xdo('mousemove', x0, y0); yield 0.3; xdo('mousedown', 1); yield 0.2
    for k in range(1, 25): xdo('mousemove', x0 + k * 10, y0 + k * 2); yield 0.04
    xdo('mouseup', 1); yield 0.8
    bpy.ops.object.mode_set(mode='OBJECT'); c1 = colours(ob); bpy.ops.object.mode_set(mode='SCULPT')
    changed = np.abs(c1[:, :3] - c0[:, :3]).max(1) > 0.05
    log('REAL stroke Paint (red):', int(changed.sum()), 'points coloured, mean colour there', tuple(np.round(c1[changed, :3].mean(0), 2)) if changed.any() else None)
    # Alt + click on the painted stroke = eyedropper
    pl.set_brush_colour(C, (0.0, 0.0, 1.0))
    xdo('mousemove', x0 + 120, y0 + 24); yield 0.3
    xdo('keydown', 'alt'); yield 0.1; xdo('click', 1); yield 0.3; xdo('keyup', 'alt'); yield 0.5
    log('Alt + click eyedrop: brush colour now', tuple(round(v, 2) for v in pl.brush_colour(C)), '(expected red)')
    # Mask by brightness over the painted stroke
    with C.temp_override(window=w, area=a, region=r):
        res = bpy.ops.mch.paint_mask(kind='VALUE')
    mk = pl.read_mask(ob.data)
    log('mask by brightness', res, 'masked mean', round(float(mk.mean()), 3), 'max', round(float(mk.max()), 3))
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.paint_mask(kind='CLEAR')
    # a render of the painted sphere (colour attribute)
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.object.mode_set(mode='OBJECT')
    S.render.engine = 'BLENDER_WORKBENCH'; S.render.resolution_x, S.render.resolution_y = 800, 800
    sh = S.display.shading; sh.light = 'STUDIO'; sh.color_type = 'VERTEX'; sh.show_specular_highlight = False; sh.show_cavity = False; sh.show_object_outline = False
    try: sh.studio_light = 'paint.sl'
    except TypeError: pass
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam')); S.collection.objects.link(cam); S.camera = cam
    cam.location = (0.0, -4.2, 0.0); cam.rotation_euler = (math.radians(90), 0, 0); cam.data.lens = 50
    S.render.filepath = os.path.join(OUT, 'painted.png'); bpy.ops.render.render(write_still=True)
    log('DONE'); bpy.ops.wm.quit_blender()

gen = None
def run():
    global gen
    try:
        if gen is None: gen = flow()
        return next(gen)
    except StopIteration: return None
    except Exception as ex:
        import traceback; traceback.print_exc(); log('ERROR', repr(ex)); bpy.ops.wm.quit_blender(); return None
bpy.app.timers.register(run, first_interval=2.0)
