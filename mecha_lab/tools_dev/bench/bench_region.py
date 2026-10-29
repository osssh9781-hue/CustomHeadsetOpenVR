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
cutters = [('column (through, 0.2 wide)', box((0.35, 0.1, 0.0), (0.2, 0.2, 2.6))), ('pocket (shallow box)', box((0.0, 0.0, 0.98), (0.3, 0.3, 0.12)))]
for cname, cutter in cutters:
    for op in ('DIFFERENCE', 'INTERSECT'):
        t = time.perf_counter(); full = cg.evaluate_boolean(C, ob, cutter, op, 'MANIFOLD'); t_m = time.perf_counter() - t
        t = time.perf_counter(); fullx = cg.evaluate_boolean(C, ob, cutter, op, 'EXACT'); t_x = time.perf_counter() - t
        bpy.data.meshes.remove(fullx)
        log = []
        t = time.perf_counter(); out = rc.region_boolean(C, ob, cutter, op, log); t_r = time.perf_counter() - t
        if out is None:
            print(f'  {cname} {op}: REGION returned None (fallback) | manifold {t_m:.2f}s exact {t_x:.2f}s'); bpy.data.meshes.remove(full); continue
        nm = cg.non_manifold_edge_count(out)
        vf, vr = volume(full), volume(out)
        # untouched faces: every original face outside the region must be in the output unchanged
        kf, ko = face_keys(me0), face_keys(out)
        in_out = np.isin(kf, ko)
        reg = rc.LAST_TIMES
        untouched_expected = n0 - reg['faces_region']
        # attributes on matched faces
        gr0, gro = attr(me0, 'grp', 'FACE'), attr(out, 'grp', 'FACE')
        mi0 = np.empty(n0, np.int32); me0.polygons.foreach_get('material_index', mi0)
        mio = np.empty(len(out.polygons), np.int32); out.polygons.foreach_get('material_index', mio)
        order_o = np.argsort(ko); pos = np.searchsorted(ko[order_o], kf); pos[pos >= len(ko)] = 0; hit = ko[order_o][pos] == kf
        same_grp = int((gr0[hit, 0] == gro[order_o][pos[hit], 0]).sum()); same_mat = int((mi0[hit] == mio[order_o][pos[hit]]).sum())
        sm = np.empty(len(out.polygons), bool); out.polygons.foreach_get('use_smooth', sm)
        print(f'  {cname} {op}: manifold {t_m:.2f}s exact {t_x:.2f}s REGION {t_r:.2f}s [{log[-1].split(":")[1].strip()}]\n'
              f'      faces full {len(full.polygons):,} region {len(out.polygons):,} | open edges {nm} | volume full {vf:.6f} region {vr:.6f} '
              f'rel diff {abs(vf - vr) / max(1e-12, abs(vf)):.2e}\n'
              f'      original faces found unchanged in the output: {int(in_out.sum()):,} (faces outside the region {untouched_expected:,}; '
              f'in the region {reg["faces_region"]:,}) | grp same {same_grp:,}/{int(hit.sum()):,} material same {same_mat:,} | '
              f'smooth {int(sm.sum()):,}/{len(sm):,} | attrs {sorted(a.name for a in out.attributes if not a.name.startswith("."))} | '
              f'materials {len(out.materials)} uv {bool(out.uv_layers)}', flush=True)
        bpy.data.meshes.remove(full); bpy.data.meshes.remove(out)
for _c, o in cutters: bpy.data.objects.remove(o)

# --- the whole Cut through the tool, stage by stage (20 px lasso) ---------------------------------------------------
T = {}
def wrap(mod, name, key):
    real = getattr(mod, name)
    def f(*a, **k):
        t = time.perf_counter()
        try: return real(*a, **k)
        finally: T[key] = T.get(key, 0.0) + time.perf_counter() - t
    setattr(mod, name, f); return real
wrap(cg, 'boolean_result', 'boolean'); wrap(cg, 'tidy_result', 'post: tidy'); wrap(ce, '_shut_holes', 'post: holes'); wrap(ce, '_finish_guarded', 'post: finish')
wrap(cg, 'commit_mesh', 'commit'); wrap(cg, 'non_manifold_edge_count', 'post: open-edge counts'); wrap(cg, 'is_junk', 'post: junk check'); wrap(cg, 'self_overlaps', 'post: crossings')
MODE[0], NATIVE[0] = 'CUT', ts.TOOL_BY_ID['CUT'][5]; S.mch_settings.mch_active_tool = 'CUT'
bpy.data.objects.remove(ob)
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
