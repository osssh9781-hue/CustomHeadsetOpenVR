"""Real window: Bake High Poly from the ZBrush screen (zb_action BAKE_HP) on a cut cube that carries Edge Memory
marks - the dense copy appears in the BakeHP collection, its marked lines stay exactly, the original is hidden;
then the same from Mesh Tools (mch.mesh_tool) in Object Mode."""
import bpy, sys, os
sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/addon')
import mecha_lab, bmesh
import numpy as np
from mathutils import Quaternion, Vector
OUT = sys.argv[-1]; os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, 'log.txt'), 'w')
def log(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); LOG.write(s + '\n'); LOG.flush()
mecha_lab.register()
from mecha_lab import bake_highpoly as bk, core_geometry as cg, cut_engine as ce, edge_memory as em, zb_sculpt as zs
C = bpy.context; S = C.scene
for o in list(S.objects): bpy.data.objects.remove(o)
def view3d():
    for w in C.window_manager.windows:
        for a in w.screen.areas:
            if a.type == 'VIEW_3D':
                return w, a, next(r for r in a.regions if r.type == 'WINDOW')
    return None, None, None
PPU = 100.0
TOP = cg.OrthoProjector(Quaternion(), center=Vector((0, 0, 0)), pixels_per_unit=PPU)
def P(x, y): return (500 + x * PPU, 500 + y * PPU)
def rect(cx, cy, w, h): return ce.rect_loop(P(cx - w / 2, cy - h / 2), P(cx + w / 2, cy + h / 2))
def flow():
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        ws = next((x for x in bpy.data.workspaces if x.name.startswith('MECHA LAB')), None)
        if ws is None:
            bpy.ops.mch.workspace_open(); ws = next((x for x in bpy.data.workspaces if x.name.startswith('MECHA LAB')), None)
        w.workspace = ws
    yield 2.0
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        S.mch_settings.auto_apply = True
        S.mch_cut.targets = 'ACTIVE'
        bpy.ops.mesh.primitive_cube_add(size=2.0); ob = C.active_object; ob.name = 'Part'
        ce.perform_closed(C, 'CUT', [ob], [rect(0.0, 0.0, 1.0, 1.0)], TOP)
        log('cut: faces', len(ob.data.polygons), 'memory', em.describe(ob.data))
        bpy.ops.mch.zb_switch(target='ZBRUSH')
    yield 1.0
    with C.temp_override(window=w, area=a, region=r):
        S.mch_zb.bk_target = 50; S.mch_zb.bk_rounding = 100; S.mch_zb.bk_fillet = 0.0
        r1 = bpy.ops.mch.zb_action('EXEC_DEFAULT', True, action='BAKE_HP')
    hp = bpy.data.objects.get('Part_BakeHP')
    log('Bake High Poly (shelf):', r1, 'mode', C.mode, 'result', hp.name if hp else None,
        'faces', len(hp.data.polygons) if hp else 0, 'collection', hp.users_collection[0].name if hp else None,
        'original hidden', ob.hide_get(), 'active', C.view_layer.objects.active.name if C.view_layer.objects.active else None)
    if hp:
        co = np.array([v.co[:] for v in hp.data.vertices])
        on_line = (np.abs(np.abs(co[:, 0]) - 0.5) < 1e-4) & (np.abs(co[:, 2] - 1.0) < 1e-4) & (np.abs(co[:, 1]) <= 0.5 + 1e-4)
        log('pocket outline points on the bake (x = +-0.5, z = 1):', int(on_line.sum()), 'max |co|', float(np.abs(co).max()))
    yield 0.5
    bpy.ops.object.mode_set(mode='OBJECT')
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.zb_switch(target='MECHA')
    yield 0.5
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=1.0, depth=2.0, location=(4, 0, 0)); cyl = C.active_object; cyl.name = 'Cyl'
        r2 = bpy.ops.mch.mesh_tool(action='BAKE_HP')
    hp2 = bpy.data.objects.get('Cyl_BakeHP')
    log('Bake High Poly (Mesh Tools):', r2, 'result', hp2.name if hp2 else None, 'faces', len(hp2.data.polygons) if hp2 else 0)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'bake_highpoly_real_window.blend'))
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
