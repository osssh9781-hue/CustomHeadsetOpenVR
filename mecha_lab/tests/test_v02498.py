"""0.24.66 Fast Decimate: Mecha Lab's own decimation engine (bin/mdecim_*) behind ZBrush Decimate Current - faster
than Blender's Decimate at the same error, closed meshes stay closed, Even Tris (round triangles), Allow Quads,
Keep Mask (more detail where masked), Keep Groups (polygroup borders stay), Keep Borders (open borders stay),
attributes come along (mask, polygroups, materials, colours, UVs), undo, fallback to Blender's modifier."""
import os
import time

import numpy as np

from _harness import bmesh, bpy, check, fresh, summary

import mecha_lab
from mecha_lab import fast_decimate as fd, zb_sculpt as zs

mecha_lab.register()
fresh()
C = bpy.context


def bumpy_sphere(level=6, name='Bumpy'):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=level, radius=1.0)
    ob = C.active_object
    ob.name = name
    me = ob.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    r = 1 + 0.04 * np.sin(12 * co[:, 0]) * np.sin(10 * co[:, 1]) + 0.08 * np.exp(-((co[:, 2] - 0.3) ** 2) / 0.002)
    co *= r[:, None]
    me.vertices.foreach_set('co', co.ravel())
    me.update()
    return ob


def arrays(me):
    V = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', V)
    me.calc_loop_triangles()
    T = np.empty(len(me.loop_triangles) * 3, np.int64)
    me.loop_triangles.foreach_get('vertices', T)
    return V.reshape(-1, 3), T.reshape(-1, 3)


def open_edges(me):
    e = np.empty(len(me.edges) * 2, np.int64)
    me.edges.foreach_get('vertices', e)
    e = e.reshape(-1, 2)
    cnt = np.zeros(len(me.edges), np.int64)
    ek = {tuple(sorted(x)): i for i, x in enumerate(e.tolist())}
    for p in me.polygons:
        vs = list(p.vertices)
        for i in range(len(vs)):
            cnt[ek[tuple(sorted((vs[i], vs[(i + 1) % len(vs)])))]] += 1
    return int((cnt != 2).sum())


def surface_error(V0, T0, V1, n=4000):
    from mathutils.bvhtree import BVHTree
    t = BVHTree.FromPolygons(V0.tolist(), T0.tolist())
    rng = np.random.default_rng(3)
    s = V1[rng.choice(len(V1), min(n, len(V1)), replace=False)]
    return float(np.mean([t.find_nearest(p)[3] for p in s]))


def shape(me):
    V, T = arrays(me)
    p0, p1, p2 = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    n = np.linalg.norm(np.cross(p1 - p0, p2 - p0), axis=1)
    l = ((p1 - p0) ** 2).sum(1) + ((p2 - p1) ** 2).sum(1) + ((p0 - p2) ** 2).sum(1)
    q = 2 * np.sqrt(3) * n / np.maximum(l, 1e-30)
    return float((q < 0.3).mean())


# --- the engine ---------------------------------------------------------------------------------------------------
check('The engine for this system loads (Linux x64 here; Windows x64 DLL ships too)', fd.available(),
      (fd.lib_name(), os.listdir(os.path.join(os.path.dirname(fd.__file__), 'bin'))))
dll = os.path.join(os.path.dirname(fd.__file__), 'bin', 'mdecim_win_x64.dll')
blob = open(dll, 'rb').read() if os.path.isfile(dll) else b''
check('The Windows engine is there: a PE DLL exporting mdecim_run / mdecim_version, only KERNEL32 + msvcrt',
      blob[:2] == b'MZ' and b'mdecim_run' in blob and b'mdecim_version' in blob and b'KERNEL32.dll' in blob
      and b'libwinpthread' not in blob and b'libgcc_s' not in blob, len(blob))
src = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(fd.__file__))), 'tools_dev', 'native')
check('Its source and build script are in tools_dev/native', os.path.isfile(os.path.join(src, 'mdecim.c'))
      and os.path.isfile(os.path.join(src, 'build_mdecim.sh')))

# --- quality and speed against Blender's Decimate ------------------------------------------------------------------
ob = bumpy_sphere(8, 'Speed')
V0, T0 = arrays(ob.data)
ob2 = ob.copy()
ob2.data = ob.data.copy()
C.collection.objects.link(ob2)
t = time.perf_counter()
msg = fd.decimate_object(ob, 5)
t_fast = time.perf_counter() - t
mod = ob2.modifiers.new('d', 'DECIMATE')
mod.ratio = len(ob.data.polygons) / len(T0)
t = time.perf_counter()
with C.temp_override(object=ob2, active_object=ob2):
    bpy.ops.object.modifier_apply(modifier=mod.name)
t_bl = time.perf_counter() - t
e_fast = surface_error(V0, T0, arrays(ob.data)[0])
e_bl = surface_error(V0, T0, arrays(ob2.data)[0])
print(f'  327,680 triangles -> 5 %: engine {t_fast:.2f} s ({fd.threads()} threads), Blender {t_bl:.2f} s; '
      f'mean error {e_fast:.6f} / {e_bl:.6f}')
check('5 % of a 327,680-triangle mesh: about that many polygons', abs(len(ob.data.polygons) - 0.05 * len(T0))
      < 0.002 * len(T0), msg)
check('... faster than Blender\'s Decimate (same polygon count)', t_fast < t_bl, (t_fast, t_bl))
check('... about the same error as Blender (within 15 %)', e_fast < 1.15 * e_bl, (e_fast, e_bl))
check('... the closed mesh stays closed (every edge on 2 faces)', open_edges(ob.data) == 0)
check('... the message says how long and how many threads', 'threads' in msg and '>' in msg, msg)
bpy.data.objects.remove(ob2)
bpy.data.objects.remove(ob)

# --- 0.24.70 an extreme single pass (blocks per thread floored at 5 %) ---------------------------------------------
ob = bumpy_sphere(8, 'Extreme')
V0, T0 = arrays(ob.data)
vol = lambda V, T: float(np.einsum('ij,ij->i', V[T[:, 0]], np.cross(V[T[:, 1]], V[T[:, 2]])).sum() / 6)
v0 = vol(V0, T0)
oV, oF, _vs, _fs = fd.run(V0, T0, 300, nthreads=4)
v1 = vol(oV.astype(np.float64), oF.astype(np.int64))
check('327,680 triangles to 300 in one go on 4 threads: the shape holds (each thread\'s block was taken almost to '
      'nothing and the result lost up to a third of its volume)', len(oF) == 300 and abs(v1 / v0 - 1) < 0.03,
      (len(oF), v1 / v0))
bpy.data.objects.remove(ob)

# --- engine 4: even spacing (the fine sampling the field-aligned quad remesher starts from) ------------------------
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=2.0)
me = bpy.data.meshes.new('Flat')
bm.to_mesh(me)
bm.free()
ob = bpy.data.objects.new('Flat', me)
C.collection.objects.link(ob)
me.remesh_voxel_size = 0.025                     # a DynaMesh-like box: 78,732 triangles
with C.temp_override(object=ob, active_object=ob):
    bpy.ops.object.voxel_remesh()
V0, T0 = arrays(ob.data)
spread = {}
for lw in (0.0, 0.1):
    oV, oF, _vs, _fs = fd.run(V0, T0, 3000, even=True, uniform=lw)
    e = np.concatenate([oF[:, [0, 1]], oF[:, [1, 2]], oF[:, [2, 0]]])
    ln = np.linalg.norm(oV[e[:, 0]] - oV[e[:, 1]], axis=1)
    spread[lw] = (round(float(ln.std() / ln.mean()), 3), round(float(ln.max() / ln.mean()), 2),
                  round(float(np.abs(np.abs(oV).max(1) - 1.0).max()), 6))
check('Even spacing: edges of one length on flat parts (spread and longest edge both clearly smaller), the box '
      'keeps its shape', spread[0.1][0] < 0.85 * spread[0.0][0] and spread[0.1][1] < spread[0.0][1]
      and spread[0.1][2] < 1e-4, spread)
bpy.data.objects.remove(ob)

# --- options ------------------------------------------------------------------------------------------------------
ob = bumpy_sphere(6, 'Even')
ob2 = ob.copy()
ob2.data = ob.data.copy()
C.collection.objects.link(ob2)
fd.decimate_object(ob, 10)
fd.decimate_object(ob2, 10, even=True)
check('Even Tris: far fewer thin triangles (nicer topology)', shape(ob2.data) < 0.5 * shape(ob.data),
      (shape(ob.data), shape(ob2.data)))
ob3 = ob.copy()
ob3.data = ob.data.copy()
C.collection.objects.link(ob3)
fd.join_quads(ob3.data)
check('Allow Quads: pairs of triangles become quads', sum(len(p.vertices) == 4 for p in ob3.data.polygons)
      > 0.3 * len(ob3.data.polygons))
for o in (ob, ob2, ob3):
    bpy.data.objects.remove(o)

# mask: the +x half masked keeps more detail
ob = bumpy_sphere(6, 'Mask')
me = ob.data
co = np.empty(len(me.vertices) * 3)
me.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
mask = me.attributes.new('.sculpt_mask', 'FLOAT', 'POINT')
mask.data.foreach_set('value', (co[:, 0] > 0).astype(np.float32))
fs = me.attributes.new('.sculpt_face_set', 'INT', 'FACE')
cen = np.array([p.center for p in me.polygons])
fs.data.foreach_set('value', np.where(cen[:, 2] > 0.1, 2, 1).astype(np.int32))
mat_a = bpy.data.materials.new('A')
mat_b = bpy.data.materials.new('B')
me.materials.append(mat_a)
me.materials.append(mat_b)
me.polygons.foreach_set('material_index', (cen[:, 1] > 0).astype(np.int32))
col = me.color_attributes.new('Paint', 'FLOAT_COLOR', 'POINT')
col.data.foreach_set('color', np.repeat((co[:, 2:3] > 0).astype(np.float32), 4, 1).ravel())
me.uv_layers.new(name='UVMap')
msg = fd.decimate_object(ob, 10, keep_mask=True, keep_groups=True)
me = ob.data
co = np.empty(len(me.vertices) * 3)
me.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
masked = int((co[:, 0] > 0.02).sum())
unmasked = int((co[:, 0] < -0.02).sum())
check('Keep Mask: the masked half keeps clearly more points', masked > 1.4 * unmasked, (masked, unmasked, msg))
m = np.empty(len(me.vertices), np.float32)
me.attributes['.sculpt_mask'].data.foreach_get('value', m)
check('... and stays masked (the mask comes along)', np.all(m[co[:, 0] > 0.05] == 1.0)
      and np.all(m[co[:, 0] < -0.05] == 0.0))
g = np.empty(len(me.polygons), np.int32)
me.attributes['.sculpt_face_set'].data.foreach_get('value', g)
cen = np.array([p.center for p in me.polygons])
check('Polygroups come along (each polygon keeps its group)', set(g.tolist()) == {1, 2}
      and np.mean((g == 2) == (cen[:, 2] > 0.1)) > 0.97)
# group border: every point on it lies near z = 0.1 (where the border was)
e = np.empty(len(me.edges) * 2, np.int64)
me.edges.foreach_get('vertices', e)
fv = [list(p.vertices) for p in me.polygons]
vg = {}
for i, vs in enumerate(fv):
    for v in vs:
        vg.setdefault(v, set()).add(g[i])
border = [v for v, s in vg.items() if len(s) > 1]
zr = np.abs(co[border, 2] - 0.1)
check('Keep Groups: the polygroup border stays where it was', len(border) > 10 and zr.max() < 0.05, zr.max())
mi = np.empty(len(me.polygons), np.int32)
me.polygons.foreach_get('material_index', mi)
check('Materials come along', len(me.materials) == 2 and np.mean((mi == 1) == (cen[:, 1] > 0)) > 0.97)
c = np.empty(len(me.vertices) * 4, np.float32)
me.color_attributes['Paint'].data.foreach_get('color', c)
far = np.abs(co[:, 2]) > 0.15        # (a point keeps its colour and may move about a polygon: not right at the edge)
bad = (c[0::4] > 0.5)[far] != (co[far, 2] > 0)
check('Colours come along', not bad.any(), (int(bad.sum()), int(far.sum()), co[far][bad][:3].tolist(), c.reshape(-1, 4)[far][bad][:3].tolist()))
check('The UV map is still there', 'UVMap' in me.uv_layers)
bpy.data.objects.remove(ob)

# open border
bpy.ops.mesh.primitive_grid_add(x_subdivisions=80, y_subdivisions=80, size=2.0)
ob = C.active_object
me = ob.data
co = np.empty(len(me.vertices) * 3)
me.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
co[:, 2] = 0.1 * np.sin(4 * co[:, 0]) * np.cos(3 * co[:, 1])
me.vertices.foreach_set('co', co.ravel())
me.update()
edge0 = {tuple(np.round(p, 5)) for p in co if abs(abs(p[0]) - 1) < 1e-6 or abs(abs(p[1]) - 1) < 1e-6}
fd.decimate_object(ob, 10, keep_borders=True)
co = np.empty(len(ob.data.vertices) * 3)
ob.data.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
on_edge = [p for p in co if abs(abs(p[0]) - 1) < 1e-4 or abs(abs(p[1]) - 1) < 1e-4]
check('Keep Borders: border points stay exactly where they were', len(on_edge) > 20
      and all(tuple(np.round(p, 5)) in edge0 for p in on_edge), len(on_edge))
bpy.data.objects.remove(ob)

# --- ZBrush Decimate Current, undo, fallback, refusals ------------------------------------------------------------
zs.on = lambda c: getattr(c, 'mode', '') == 'SCULPT'
ob = bumpy_sphere(6, 'ZB')
bpy.ops.object.mode_set(mode='SCULPT')
zb = C.scene.mch_zb
check('Decimate options on the ZBrush shelf (Even Tris / Allow Quads / Keep Mask / Keep Groups / Keep Borders)',
      all(hasattr(zb, k) for k in ('dec_even', 'dec_quads', 'dec_mask', 'dec_groups', 'dec_borders')))
n0 = len(ob.data.polygons)
zb.decimate = 20
bpy.ops.ed.undo_push(message='before')
r = bpy.ops.mch.zb_action(action='DECIMATE')
n1 = len(ob.data.polygons)
check('Decimate Current runs the engine, back in Sculpt Mode', r == {'FINISHED'} and abs(n1 - 0.2 * n0) < 0.01 * n0
      and C.mode == 'SCULPT', (n0, n1))
bpy.ops.ed.undo()
ob = bpy.data.objects['ZB']
check('Ctrl+Z brings the polygons back', len(ob.data.polygons) == n0, len(ob.data.polygons))
bpy.ops.object.mode_set(mode='OBJECT')
saved = fd._LIB[0]
fd._LIB[0] = False
msg = fd.blender_decimate(C, ob, 50) if not fd.available() else ''
fd._LIB[0] = saved
check('Without the engine (other systems) Blender\'s Decimate is used', 'Blender' in msg
      and abs(len(ob.data.polygons) - 0.5 * n0) < 0.02 * n0, msg)
ob.shape_key_add(name='Basis')
check('Shape keys: it says to remove them first (nothing changed)', 'shape keys' in fd.decimate_object(ob, 50))
ob.shape_key_clear()
ob.modifiers.new('m', 'MULTIRES')
check('Multires: it says to delete / apply the levels first', 'Multires' in fd.decimate_object(ob, 50))

summary()
