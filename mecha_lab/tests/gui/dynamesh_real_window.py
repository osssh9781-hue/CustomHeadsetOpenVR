"""Real window: Safe DynaMesh in the ZBrush screen - a sphere with its top cut off (open), DynaMesh pressed on the
shelf (zb_action) and again through Ctrl + drag on the empty canvas (DYNA_UPDATE): a closed single part each time."""
import bpy, sys, os
sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/addon')
import mecha_lab, bmesh
OUT = sys.argv[-1]; os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, 'log.txt'), 'w')
def log(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); LOG.write(s + '\n'); LOG.flush()
mecha_lab.register()
from mecha_lab import zb_sculpt as zs, dynamesh_fix as dfx
C = bpy.context; S = C.scene
for o in list(S.objects): bpy.data.objects.remove(o)
def view3d():
    for w in C.window_manager.windows:
        for a in w.screen.areas:
            if a.type == 'VIEW_3D':
                return w, a, next(r for r in a.regions if r.type == 'WINDOW')
    return None, None, None
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
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=48, ring_count=24); ob = C.active_object
        bm = bmesh.new(); bm.from_mesh(ob.data)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().z > 0.9], context='FACES')
        bm.to_mesh(ob.data); bm.free()
        log('before', dfx.diagnose(ob.data))
        bpy.ops.mch.zb_switch(target='ZBRUSH')
    yield 1.0
    with C.temp_override(window=w, area=a, region=r):
        S.mch_zb.points = 20
        r1 = bpy.ops.mch.zb_action('EXEC_DEFAULT', True, action='DYNAMESH')
    log('DynaMesh (shelf):', r1, 'mode', C.mode, 'on', zs.dynamesh_on(ob), 'fix:', zs.LAST_FIX['text'])
    yield 0.5
    bpy.ops.object.mode_set(mode='OBJECT'); log('after 1', dfx.diagnose(ob.data)); bpy.ops.object.mode_set(mode='SCULPT')
    with C.temp_override(window=w, area=a, region=r):
        r2 = bpy.ops.mch.zb_action('EXEC_DEFAULT', True, action='DYNA_UPDATE')
    log('DynaMesh again (Ctrl drag canvas path):', r2, 'mode', C.mode, 'fix:', zs.LAST_FIX['text'])
    bpy.ops.object.mode_set(mode='OBJECT'); log('after 2', dfx.diagnose(ob.data))
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
