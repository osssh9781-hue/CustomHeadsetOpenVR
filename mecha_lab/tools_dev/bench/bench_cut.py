"""Equivalence + stage timing of the High Poly (region) cut against the whole-part boolean.
usage: python bench_region.py <body: ico8 | ico9 | vox3m>"""
import sys, time, bpy, bmesh, numpy as np
sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/tests')
from _harness import bpy, check, cube, fresh, non_manifold, summary
import mecha_lab
from mecha_lab import tool_state as ts, core_geometry as cg, region_cut as rc, cut_engine as ce
_src = open('/home/user/CustomHeadsetOpenVR/mecha_lab/tests/test_v0200.py').read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
fresh(); mecha_lab.register()
C = bpy.context; S = C.scene
S.mch_brush.shape = 'LASSO'; S.mch_cut.targets = 'AUTO'; S.mch_cut.shared_mesh = 'SINGLE'
which = sys.argv[-1]

def body():
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=9 if which != 'ico8' else 8, radius=1.0)
    ob = C.active_object
    m = ob.modifiers.new('d', 'DISPLACE'); t = bpy.data.textures.new('t', 'CLOUDS'); t.noise_scale = 0.3; m.texture = t; m.strength = 0.2
    with C.temp_override(object=ob, active_object=ob):
        bpy.ops.object.modifier_apply(modifier='d')
    if which == 'vox3m':
        ob.data.remesh_voxel_size = 0.0031
        with C.temp_override(object=ob, active_object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
            bpy.ops.object.voxel_remesh()
    me = ob.data
    n = len(me.polygons)
    a = me.attributes.new('grp', 'INT', 'FACE'); a.data.foreach_set('value', (np.arange(n) % 5).astype(np.int32))
    a = me.attributes.new('mask', 'FLOAT', 'POINT'); a.data.foreach_set('value', np.linspace(0, 1, len(me.vertices)).astype(np.float32))
    a = me.attributes.new('col', 'FLOAT_COLOR', 'CORNER'); a.data.foreach_set('color', np.tile([0.2, 0.5, 0.8, 1.0], len(me.loops)).astype(np.float32))
    me.polygons.foreach_set('material_index', (np.arange(n) % 2).astype(np.int32))
    me.materials.append(bpy.data.materials.new('A')); me.materials.append(bpy.data.materials.new('B'))
    me.polygons.foreach_set('use_smooth', np.ones(n, bool))
    a = me.attributes.get('sharp_edge') or me.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE'); a.data.foreach_set('value', (np.arange(len(me.edges)) % 7 == 0))
    if not me.uv_layers: me.uv_layers.new(name='UVMap')
    me.update()
    return ob

def volume(me):
    bm = bmesh.new(); bm.from_mesh(me); v = bm.calc_volume(signed=True); bm.free(); return v

def face_keys(me):
    co, tot, start, vi = rc.arrays(me)
    k = np.round(co * 1e5).astype(np.int64)
    h = (k[:, 0] * 73856093) ^ (k[:, 1] * 19349663) ^ (k[:, 2] * 83492791)
    return np.add.reduceat(h[vi], start) ^ tot.astype(np.int64)      # (order-free per face)

def attr(me, name, domain, key='value'):
    a = me.attributes.get(name)
    if a is None: return None
    w = {'value': 1, 'color': 4}[key]
    v = np.empty(len(a.data) * w, np.float32 if a.data_type != 'INT' else np.int32); a.data.foreach_get(key, v); return v.reshape(len(a.data), w)

ob = body(); me0 = ob.data; n0 = len(me0.polygons)
print(f'BODY {which}: {n0:,} faces, {len(me0.vertices):,} points, volume {volume(me0):.6f}', flush=True)
def box(loc, scale):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc); o = C.active_object; o.scale = scale; C.view_layer.update(); return o
cutters = []
# --- the whole Cut through the tool, stage by stage (20 px lasso) ---------------------------------------------------
T = {}
def wrap(mod, name, key):
    real = getattr(mod, name)
    def f(*a, **k):
        t = time.perf_counter()
        try: return real(*a, **k)
        finally: T[key] = T.get(key, 0.0) + time.perf_counter() - t
    setattr(mod, name, f); return real
_real_bool = cg.boolean_result
def _probe_bool(*a, **k):
    r = _real_bool(*a, **k)
    try:
        m = r[0] if isinstance(r, tuple) else r
        print(f'   [probe] open edges right after the boolean: {cg.non_manifold_edge_count(m)}', flush=True)
    except Exception as ex: print('   [probe]', ex)
    return r
cg.boolean_result = _probe_bool
wrap(cg, 'boolean_result', 'boolean'); wrap(cg, 'tidy_result', 'post: tidy'); wrap(ce, '_shut_holes', 'post: holes'); wrap(ce, '_finish_guarded', 'post: finish')
wrap(cg, 'commit_mesh', 'commit'); wrap(cg, 'non_manifold_edge_count', 'post: open-edge counts'); wrap(cg, 'is_junk', 'post: junk check'); wrap(cg, 'self_overlaps', 'post: crossings')
MODE[0], NATIVE[0] = 'CUT', ts.TOOL_BY_ID['CUT'][5]; S.mch_settings.mch_active_tool = 'CUT'
bpy.data.objects.remove(ob)
_rf = rc.region_faces_of
def _p_rf(me, before, size):
    t=time.perf_counter(); fm=_rf(me, before, size); print(f'   [probe] region_faces_of: {time.perf_counter()-t:.2f}s faces {None if fm is None else int(fm.sum())} of {len(me.polygons)} LAST_REGION {rc.LAST_REGION.get("name")} me {me.name}', flush=True); return fm
rc.region_faces_of = _p_rf
_ts = rc.tidy_sub
def _p_ts(me, fm, size, sh, sl):
    t=time.perf_counter(); r=_ts(me, fm, size, sh, sl); print(f'   [probe] tidy_sub: {time.perf_counter()-t:.2f}s -> {r}', flush=True); return r
rc.tidy_sub = _p_ts
_tr = cg.tidy_result
def _p_tr(me, *a, **k):
    t=time.perf_counter(); r=_tr(me, *a, **k); print(f'   [probe] tidy_result({len(me.polygons)} faces, before={k.get("before") is not None}): {time.perf_counter()-t:.2f}s -> {r}', flush=True); return r
cg.tidy_result = _p_tr
_ef = rc.extract_faces
def _p_ef(*a, **k):
    t=time.perf_counter(); r=_ef(*a, **k); print(f'   [probe] extract_faces: {time.perf_counter()-t:.2f}s', flush=True); return r
rc.extract_faces = _p_ef
_rp = rc.replace_faces
def _p_rp(*a, **k):
    t=time.perf_counter(); r=_rp(*a, **k); print(f'   [probe] replace_faces: {time.perf_counter()-t:.2f}s -> {r}', flush=True); return r
rc.replace_faces = _p_rp
for hip in (False, True):
    T.clear()
    ob = body()                                    # (a fresh body each time: a second cut into the same hole is no test)
    for o in C.selected_objects: o.select_set(False)
    ob.select_set(True); C.view_layer.objects.active = ob
    S.mch_cut.hipoly = hip
    t = time.perf_counter(); r, msg = lasso([(490, 490), (510, 490), (510, 510), (490, 510)]); dt = time.perf_counter() - t
    reg = dict(rc.LAST_TIMES) if hip else {}
    other = dt - sum(T.values())
    print(f'CUT hipoly={hip}: {dt:.2f}s total  nm {non_manifold(ob)}  {msg[:40]}')
    print('   ' + ' | '.join(f'{k} {v:.2f}' for k, v in sorted(T.items())) + f' | other (lasso, planes, cutter, bookkeeping) {other:.2f}')
    if reg: print('   boolean stages: ' + ' | '.join(f'{k} {reg[k]:.2f}' for k in ('region', 'extract', 'boolean', 'knife', 'sort', 'stitch')) + f' | region faces {reg["faces_region"]:,} walls {reg["walls"]}')
    bpy.data.objects.remove(ob)
