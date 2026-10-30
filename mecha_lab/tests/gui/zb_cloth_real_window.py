"""Real window: the ZBrush screen's cloth brushes + Cloth Filter.
  A. sphere, ZBrush screen, ClothDrag picked through the shelf operator, a python stroke and a REAL mouse drag
     (xdotool) -> points moved.
  B. padding: a subdivided plane, quilting lines masked (a 0.5 m grid), Cloth Filter Inflate started from our
     shelf operator, the mouse dragged with xdotool, click to confirm -> the unmasked cells puff up, the masked
     lines stay.  Screenshots + a workbench render (shaded + wire)."""
import bpy, sys, os, time, subprocess, math
sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/addon')
import numpy as np
import mecha_lab
OUT = sys.argv[-1]; os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, 'log.txt'), 'w')
def log(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); LOG.write(s + '\n'); LOG.flush()
mecha_lab.register()
from mecha_lab import zb_sculpt as zs, workspace_ui
C = bpy.context; S = C.scene
for o in list(S.objects): bpy.data.objects.remove(o)
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
    """region-local (origin bottom-left) -> X screen (origin top-left)"""
    return int(r.x + x), int(w.height - (r.y + y))
def shot(name):
    bpy.ops.screen.screenshot(filepath=os.path.join(OUT, name)); log('shot', name)
def co(ob):
    v = np.zeros(len(ob.data.vertices) * 3); ob.data.vertices.foreach_get('co', v); return v.reshape(-1, 3)
def mask_of(ob):
    att = ob.data.attributes.get('.sculpt_mask')
    if att is None: return np.zeros(len(ob.data.vertices), np.float32)
    v = np.zeros(len(ob.data.vertices), np.float32); att.data.foreach_get('value', v); return v

def flow():
    w, a, r = view3d()
    focus(); xdo('mousemove', 30, 540); yield 0.3; xdo('key', 'Escape'); yield 0.5
    with C.temp_override(window=w, area=a, region=r):
        ws = next((x for x in bpy.data.workspaces if x.name.startswith('MECHA LAB')), None)
        if ws is None:
            bpy.ops.mch.workspace_open()
            ws = next((x for x in bpy.data.workspaces if x.name.startswith('MECHA LAB')), None)
        w.workspace = ws
    log('workspace', ws.name if ws else None)
    yield 2.0
    w, a, r = view3d()
    # ---- A. the sphere + ClothDrag
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=128, ring_count=64)
        ob = C.active_object
        for p in ob.data.polygons: p.use_smooth = True
        bpy.ops.view3d.view_axis(type='FRONT'); bpy.ops.view3d.view_all(); bpy.ops.view3d.zoom(delta=2)
    yield 1.0
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.zb_switch(target='ZBRUSH')
    log('mode', C.mode)
    yield 1.0
    with C.temp_override(window=w, area=a, region=r):
        res = bpy.ops.mch.zb_brush(name='ClothDrag')
        b = zs.brush(C)
        log('zb_brush ClothDrag:', res, b.name if b else None, 'cloth', zs.is_cloth(b), 'deform', getattr(b, 'cloth_deform_type', None),
            'sim area', getattr(b, 'cloth_simulation_area_type', None))
        u = zs.unified(C)
        if u is not None and u.use_unified_size: u.size = 120
        else: b.size = 120
    yield 0.5
    shot('A1_clothdrag_shelf.png')
    c0 = co(ob)
    cx, cy = r.width // 2, r.height // 2
    with C.temp_override(window=w, area=a, region=r):
        stroke = [dict(name='', location=(0, 0, 0), mouse=(cx - 150 + dx, cy + 100), mouse_event=(cx - 150 + dx, cy + 100), pressure=1.0,
                       size=120.0, x_tilt=0.0, y_tilt=0.0, time=i * 0.02, is_start=(i == 0)) for i, dx in enumerate(range(0, 121, 6))]
        res = bpy.ops.sculpt.brush_stroke(stroke=stroke, mode='NORMAL', ignore_background_click=True)
    yield 0.5
    moved = np.linalg.norm(co(ob) - c0, axis=1)
    log('A2 python stroke ClothDrag:', res, 'points moved', int((moved > 1e-4).sum()), 'max', round(float(moved.max()), 4))
    c1 = co(ob)
    x0, y0 = to_x(w, r, cx + 40, cy - 120)
    xdo('mousemove', x0, y0); yield 0.3
    xdo('mousedown', 1); yield 0.2
    for k in range(1, 21):
        xdo('mousemove', x0 + k * 6, y0 - k * 2); yield 0.05
    xdo('mouseup', 1); yield 0.8
    moved2 = np.linalg.norm(co(ob) - c1, axis=1)
    log('A3 REAL mouse drag ClothDrag (xdotool):', 'points moved', int((moved2 > 1e-4).sum()), 'max', round(float(moved2.max()), 4))
    shot('A4_clothdrag_strokes.png')
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.object.mode_set(mode='OBJECT')
    mat0 = bpy.data.materials.new('sph'); mat0.diffuse_color = (0.55, 0.3, 0.45, 1); ob.data.materials.append(mat0)
    S.render.engine = 'BLENDER_WORKBENCH'; S.render.resolution_x, S.render.resolution_y = 800, 800
    sh = S.display.shading; sh.light = 'STUDIO'; sh.show_object_outline = False; sh.color_type = 'MATERIAL'; sh.show_shadows = True; sh.show_cavity = True
    cam0 = bpy.data.objects.new('Cam0', bpy.data.cameras.new('Cam0')); S.collection.objects.link(cam0); S.camera = cam0
    cam0.location = (0.0, -4.2, 0.0); cam0.rotation_euler = (math.radians(90), 0, 0); cam0.data.lens = 50
    S.render.filepath = os.path.join(OUT, 'A5_render_sphere.png'); bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam0)
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.zb_switch(target='ZBRUSH')
    # ---- B. padding: a plane with masked quilting lines + Cloth Filter Inflate
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.data.objects.remove(ob)
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=96, y_subdivisions=96, size=2.0)
        pl = C.active_object
        for p in pl.data.polygons: p.use_smooth = True
        bpy.ops.view3d.view_axis(type='TOP'); bpy.ops.view3d.view_all(); bpy.ops.view3d.zoom(delta=1)
        att = pl.data.attributes.get('.sculpt_mask')
        if att is None:
            try:
                att = pl.data.attributes.new('.sculpt_mask', 'FLOAT', 'POINT')
            except Exception as ex:
                log('attributes.new .sculpt_mask failed:', ex)
        bpy.ops.mch.zb_switch(target='ZBRUSH')
        if pl.data.attributes.get('.sculpt_mask') is None:
            bpy.ops.paint.mask_flood_fill(mode='VALUE', value=1.0)
    yield 0.5
    att = pl.data.attributes.get('.sculpt_mask')
    log('mask attribute', att is not None, [a.name for a in pl.data.attributes][:8])
    v = co(pl)
    q = 0.5                                              # the quilt: lines every 0.5 m, about 2 points wide
    on_line = (np.abs((v[:, 0] + 1.0) % q - 0) < 0.022) | (np.abs((v[:, 1] + 1.0) % q) < 0.022) | (np.abs((v[:, 0] + 1.0) % q - q) < 0.022) | (np.abs((v[:, 1] + 1.0) % q - q) < 0.022)
    rim = (np.abs(np.abs(v[:, 0]) - 1.0) < 1e-6) | (np.abs(np.abs(v[:, 1]) - 1.0) < 1e-6)
    m = (on_line | rim).astype(np.float32)
    att.data.foreach_set('value', m); pl.data.update()
    log('masked points', int(m.sum()), 'of', len(m))
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.object.mode_set(mode='OBJECT'); bpy.ops.object.mode_set(mode='SCULPT')     # the mask shown
    yield 0.5
    shot('B1_mask_grid.png')
    z0 = co(pl)[:, 2].copy()
    cx, cy = r.width // 2, r.height // 2
    x0, y0 = to_x(w, r, cx, cy)
    xdo('mousemove', x0, y0); yield 0.3
    with C.temp_override(window=w, area=a, region=r):
        res = bpy.ops.mch.zb_cloth_filter('INVOKE_DEFAULT', kind='INFLATE')
    log('B2 Cloth Filter Inflate (our shelf operator) invoke:', res)
    yield 0.5
    for k in range(1, 41):
        xdo('mousemove', x0 + k * 8, y0); yield 0.05
    yield 0.5
    xdo('click', 1); yield 1.0
    z = co(pl)[:, 2]
    masked = m > 0.5
    log('B3 after the drag: masked lines moved max', round(float(np.abs(z[masked] - z0[masked]).max()), 4),
        'cells moved max', round(float(np.abs(z[~masked] - z0[~masked]).max()), 4),
        'cells mean |dz|', round(float(np.abs(z[~masked] - z0[~masked]).mean()), 4))
    shot('B4_padding.png')
    # a workbench render of the result (shaded + wire)
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.object.mode_set(mode='OBJECT')
    mat = bpy.data.materials.new('pad'); mat.diffuse_color = (0.55, 0.3, 0.45, 1); pl.data.materials.append(mat)
    S.render.engine = 'BLENDER_WORKBENCH'; S.render.resolution_x, S.render.resolution_y = 900, 700
    sh = S.display.shading; sh.light = 'STUDIO'; sh.show_object_outline = False; sh.color_type = 'MATERIAL'; sh.show_shadows = True; sh.show_cavity = True
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam')); S.collection.objects.link(cam); S.camera = cam
    cam.location = (0.0, -3.2, 2.6); cam.rotation_euler = (math.radians(52), 0, 0); cam.data.lens = 45
    S.render.filepath = os.path.join(OUT, 'B5_render_shaded.png'); bpy.ops.render.render(write_still=True)
    wv = pl.copy(); wv.data = pl.data.copy(); S.collection.objects.link(wv)
    md = wv.modifiers.new('W', 'WIREFRAME'); md.thickness = 0.004; md.use_replace = True
    wv.data.materials.clear(); mw = bpy.data.materials.new('wire'); mw.diffuse_color = (0.05, 0.05, 0.08, 1); wv.data.materials.append(mw)
    S.render.filepath = os.path.join(OUT, 'B6_render_wire.png'); bpy.ops.render.render(write_still=True)
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
