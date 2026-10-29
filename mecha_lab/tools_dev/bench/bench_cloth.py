"""Panel Cloth profile: a Cloth Plate on a box, every preset simulated through run_preset with the stages timed,
plus quality numbers (faces, penetration into the panel surface, self-crossings, fold amplitude, pin drift,
needle faces)."""
import sys, time, bpy, bmesh, numpy as np
sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/tests')
_src = open('/home/user/CustomHeadsetOpenVR/mecha_lab/tests/test_v0200.py').read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
fresh(); mecha_lab.register()
from mecha_lab import cloth_sim as cs, core_geometry as cg, last_used
from mathutils.bvhtree import BVHTree
from mathutils import Vector
C = bpy.context; S = C.scene
S.mch_brush.shape = 'LASSO'; S.mch_brush.line_open = False
last_used.forget('wrinkle')
MODE[0], NATIVE[0] = 'WRINKLE', 'mecha.cloth_wrinkle'
S.mch_settings.mch_active_tool = 'WRINKLE'
box = cube('Box', 4.0)
S.mch_wrinkle.sim_after = False
r, m = lasso([(330, 330), (670, 330), (670, 670), (330, 670)])
plate = C.active_object
print('plate:', plate.name, len(plate.data.polygons), 'faces', m[:80], flush=True)
which = sys.argv[-1] if sys.argv[-1] in cs.PRESET_IDS else None

T = {}
def wrap(mod, name, key):
    real = getattr(mod, name)
    def f(*a, **k):
        t = time.perf_counter()
        try: return real(*a, **k)
        finally: T[key] = T.get(key, 0.0) + time.perf_counter() - t
    setattr(mod, name, f)
wrap(cs, 'build_cloth_mesh', 'build'); wrap(cs, 'setup_cloth', 'setup'); wrap(cs, 'bake', 'bake'); wrap(cs, '_region_collider', 'collider')
FR = []
def _bake(context, objs, frames):
    scene = context.scene
    keep = scene.frame_current
    start = scene.frame_start
    for f in range(start, start + frames + 1):
        t = time.perf_counter(); scene.frame_set(f); FR.append(time.perf_counter() - t)
    t = time.perf_counter()
    dg = context.evaluated_depsgraph_get()
    for ob in objs:
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
        old = ob.data
        for mm in [mm for mm in ob.modifiers if mm.type == 'CLOTH']:
            ob.modifiers.remove(mm)
        ob.data = me
        me.name = old.name
        if old.users == 0:
            bpy.data.meshes.remove(old)
    scene.frame_set(keep)
    T['bake: keep last frame'] = time.perf_counter() - t
cs.bake = _bake

def quality(ob, src):
    me = ob.data
    mw = ob.matrix_world
    P = np.array([mw @ v.co for v in me.vertices])
    sm = src.matrix_world
    bm = bmesh.new(); bm.from_mesh(src.data); bm.transform(sm)
    bvh = BVHTree.FromBMesh(bm)
    below, depth = 0, 0.0
    for p in P:
        loc, nrm, idx, dist = bvh.find_nearest(Vector(p))
        if loc is None: continue
        d = (Vector(p) - loc).dot(nrm)
        if d < -1e-4:
            below += 1; depth = max(depth, -d)
    bm.free()
    # fold amplitude: displacement along the plate's mean normal
    nm = np.array(sum((src.matrix_world.to_3x3() @ p.normal for p in src.data.polygons), Vector())); nm /= np.linalg.norm(nm)
    h = P @ nm
    # needle / sliver faces
    area = np.empty(len(me.polygons)); me.polygons.foreach_get('area', area)
    ratio = float(area.min() / max(1e-12, area.mean()))
    cross = cg.self_overlaps(ob.data)
    return dict(verts=len(me.vertices), faces=len(me.polygons), below=below, depth=round(depth, 4), fold_std=round(float(h.std()), 4),
                fold_range=round(float(h.max() - h.min()), 4), min_area_ratio=round(ratio, 4), crossings=cross)

for preset in (cs.PRESET_IDS if which is None else (which,)):
    T.clear(); FR.clear()
    plate.hide_set(False); plate.select_set(True); C.view_layer.objects.active = plate
    t = time.perf_counter()
    made = cs.run_preset(C, [plate], preset, collider='REGION')
    dt = time.perf_counter() - t
    ob = made[0]
    q = quality(ob, plate)
    v = cs.preset_values(preset)
    print(f'{preset:8s} total {dt:5.2f}s | build {T.get("build", 0):.2f} setup {T.get("setup", 0):.2f} collider {T.get("collider", 0):.2f} bake {T.get("bake", 0):.2f} '
          f'(frames {len(FR)}: first {FR[0] if FR else 0:.2f} avg {np.mean(FR[1:]) if len(FR) > 1 else 0:.3f} max {max(FR) if FR else 0:.2f}) other {dt - sum(T.values()):.2f} | '
          f'cuts {v["cuts"]} quality {v["quality"]} | {q}', flush=True)
    bpy.data.objects.remove(ob)
