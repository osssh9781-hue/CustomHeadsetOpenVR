"""0.24.71 Quad Remesh: Mecha Lab's own field-aligned quad remesher (C engine mquad, ZBrush shelf box)."""
import math
import os
import time

import numpy as np

from _harness import bmesh, bpy, check, fresh, summary

import mecha_lab
from mecha_lab import fast_decimate as fd, panel_capture as pc, quad_field as qf, zb_sculpt as zs, zb_ui as zu

mecha_lab.register()
fresh()
C = bpy.context


def boolean(ob, cutter):
    m = ob.modifiers.new('b', 'BOOLEAN')
    m.object = cutter
    m.operation = 'DIFFERENCE'
    m.solver = 'EXACT'
    with C.temp_override(object=ob, active_object=ob):
        bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(cutter)


def box(loc, size, name='c'):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = C.active_object
    o.scale = size
    o.name = name
    bpy.ops.object.transform_apply(scale=True)
    return o


def part(name='Block', voxel=0.012):
    """A hard-surface part like a DynaMesh one: a block with a step, a slot and a round hole, voxel remeshed."""
    p = box((0, 0, 0), (1.0, 0.6, 0.4), name)
    boolean(p, box((0.55, 0, 0.35), (0.5, 0.7, 0.2)))
    boolean(p, box((-0.1, 0, 0.4), (0.08, 0.7, 0.15)))
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.18, depth=2, location=(-0.5, 0, 0),
                                        rotation=(math.pi / 2, 0, 0))
    boolean(p, C.active_object)
    p.data.remesh_voxel_size = voxel
    with C.temp_override(object=p, active_object=p):
        bpy.ops.object.voxel_remesh()
    C.view_layer.objects.active = p
    return p


def arrays(me):
    V = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', V)
    me.calc_loop_triangles()
    T = np.empty(len(me.loop_triangles) * 3, np.int64)
    me.loop_triangles.foreach_get('vertices', T)
    return V.reshape(-1, 3), T.reshape(-1, 3)


def topo(me):
    """(open edges, edges on 3+ faces, share of quads, share of inner points with 4 edges)"""
    bm = bmesh.new()
    bm.from_mesh(me)
    opn = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    nm = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    quads = sum(1 for f in bm.faces if len(f.verts) == 4) / max(len(bm.faces), 1)
    inner = [len(v.link_edges) for v in bm.verts if not v.is_boundary and v.is_manifold]
    val4 = sum(1 for k in inner if k == 4) / max(len(inner), 1)
    bm.free()
    return opn, nm, quads, val4


def surface_error(V0, T0, me):
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    t = BVHTree.FromPolygons(V0.tolist(), T0.tolist())
    cen = [sum((me.vertices[i].co for i in p.vertices), Vector()) / len(p.vertices) for p in me.polygons]
    d = np.array([t.find_nearest(c)[3] for c in cen])
    return float(d.mean()), float(d.max())


def creases(V, T, deg=30.0):
    """Midpoints of the edges where faces meet at more than ``deg``."""
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-30)
    e = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]])
    f = np.tile(np.arange(len(T)), 3)
    e.sort(1)
    key = e[:, 0] * len(V) + e[:, 1]
    o = np.argsort(key, kind='stable')
    key, e, f = key[o], e[o], f[o]
    same = np.nonzero(key[1:] == key[:-1])[0]
    sharp = (fn[f[same]] * fn[f[same + 1]]).sum(1) < math.cos(math.radians(deg))
    s = e[same[sharp]]
    return (V[s[:, 0]] + V[s[:, 1]]) * 0.5


def on_sharp(me, pts, h, deg=30.0):
    """Share of ``pts`` within 0.1 h of an edge of ``me`` where its faces meet at more than ``deg``."""
    bm = bmesh.new()
    bm.from_mesh(me)
    segs = np.array([(e.verts[0].co[:], e.verts[1].co[:]) for e in bm.edges
                     if len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(deg)])
    bm.free()
    if not len(segs) or not len(pts):
        return 0.0
    a, b = segs[:, 0], segs[:, 1]
    ab = b - a
    ll = np.maximum((ab * ab).sum(1), 1e-30)
    hit = 0
    for p in pts:
        t = np.clip(((p - a) * ab).sum(1) / ll, 0, 1)
        d = np.linalg.norm(a + ab * t[:, None] - p, axis=1).min()
        hit += d < 0.1 * h
    return hit / len(pts)


def fingerprint(P, F):
    return round(float(np.abs(P).sum()), 3), len(P), len(F), int(F[F >= 0].sum())


# --- the engine ---------------------------------------------------------------------------------------------------
check('The quad remesher is in the engine (Linux x64 here)', qf.available(), fd.lib_name())
dll = os.path.join(os.path.dirname(fd.__file__), 'bin', 'mdecim_win_x64.dll')
blob = open(dll, 'rb').read() if os.path.isfile(dll) else b''
check('... and in the Windows DLL (mquad_run / mquad_version / mquad_free; still only KERNEL32 + msvcrt)',
      blob[:2] == b'MZ' and all(k in blob for k in (b'mquad_run', b'mquad_version', b'mquad_free', b'mdecim_run'))
      and b'libwinpthread' not in blob and b'libgcc_s' not in blob, len(blob))
src = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(fd.__file__))), 'tools_dev', 'native')
build = open(os.path.join(src, 'build_mdecim.sh')).read()
check('Its source is in tools_dev/native and the build script builds it into the same library',
      os.path.isfile(os.path.join(src, 'mquad.c')) and build.count('mdecim.c mquad.c') == 2)

# --- a hard-surface part, Mostly Quads ------------------------------------------------------------------------------
ob = part()
V0, T0 = arrays(ob.data)
target = 3000
t = time.perf_counter()
P, Fq, tsrc, psrc, st = qf.remesh_arrays(V0, T0, target)
dt = time.perf_counter() - t
me = bpy.data.meshes.new('Q')
me.from_pydata(P.tolist(), [], [[int(x) for x in f if x >= 0] for f in Fq])
me.update()
opn, nm, quads, val4 = topo(me)
h = st['scale']
err_mean, err_max = surface_error(V0, T0, me)
check(f'{len(T0):,} triangles -> about {target:,} polygons (within 15 %)', abs(len(Fq) - target) < 0.15 * target,
      (len(Fq), st['levels']))
check('... mostly quads (95 %+), 93 %+ of the points with 4 edges', quads > 0.95 and val4 > 0.93, (quads, val4))
check('... closed: no holes, no edge on 3 faces', opn == 0 and nm == 0, (opn, nm))
check('... on the surface (face centres: mean < 2 %, max < 15 % of a quad)', err_mean < 0.02 * h
      and err_max < 0.15 * h, (err_mean / h, err_max / h))
cr = creases(V0, T0)
share = on_sharp(me, cr, h)
check('... the hard edges stay hard edges of the quads (90 %+ of the original crease within 0.1 quad of one)',
      share > 0.9, share)
check('... quick (C engine: under 15 s here, 4 threads)', dt < 15.0, round(dt, 2))
again = qf.remesh_arrays(V0, T0, target)
check('The same result every time', fingerprint(P, Fq) == fingerprint(again[0], again[1]),
      (fingerprint(P, Fq), fingerprint(again[0], again[1])))
bpy.data.meshes.remove(me)

# --- All Quads ------------------------------------------------------------------------------------------------------
P2, F2, _t2, _p2, st2 = qf.remesh_arrays(V0, T0, target, all_quads=True)
me = bpy.data.meshes.new('QA')
me.from_pydata(P2.tolist(), [], [[int(x) for x in f if x >= 0] for f in F2])
me.update()
opn, nm, quads, val4 = topo(me)
check('All Quads: only quads, about the same count, closed', quads == 1.0 and abs(len(F2) - target) < 0.2 * target
      and opn == 0 and nm == 0, (len(F2), quads, opn, nm))
share = on_sharp(me, cr, st2['scale'] * 0.5)
check('... hard edges kept too (85 %+)', share > 0.85, share)
bpy.data.meshes.remove(me)

# --- attributes: polygroups, materials, mask ---------------------------------------------------------------------
me = ob.data
cen = np.array([p.center[:] for p in me.polygons])
fs = me.attributes.new('.sculpt_face_set', 'INT', 'FACE')
fs.data.foreach_set('value', np.where(cen[:, 0] > 0, 2, 1).astype(np.int32))
for n in ('Gray', 'Red'):
    me.materials.append(bpy.data.materials.new(n))
me.polygons.foreach_set('material_index', (cen[:, 1] > 0).astype(np.int32))
co = np.empty(len(me.vertices) * 3)
me.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
mk = me.attributes.new('.sculpt_mask', 'FLOAT', 'POINT')
mk.data.foreach_set('value', (co[:, 2] > 0.1).astype(np.float32))
nmat = len(me.materials)
msg = qf.remesh_object(ob, 2000)
me = ob.data
cen = np.array([p.center[:] for p in me.polygons])
g = np.empty(len(me.polygons), np.int32)
me.attributes['.sculpt_face_set'].data.foreach_get('value', g)
mi = np.empty(len(me.polygons), np.int32)
me.polygons.foreach_get('material_index', mi)
far = np.abs(cen[:, 0]) > 0.1
check('remesh_object: the SubTool itself becomes quads, the message says how many and how long',
      'Quad Remesh' in msg and '% quads' in msg and abs(len(me.polygons) - 2000) < 300, msg)
check('Polygroups come along', np.mean(g[far] == np.where(cen[far, 0] > 0, 2, 1)) > 0.97, set(g.tolist()))
farm = np.abs(cen[:, 1]) > 0.1
check('Materials come along', len(me.materials) == nmat and np.mean(mi[farm] == (cen[farm, 1] > 0)) > 0.97,
      (len(me.materials), float(np.mean(mi[farm] == (cen[farm, 1] > 0))), np.bincount(mi).tolist()))
co = np.empty(len(me.vertices) * 3)
me.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
m = np.empty(len(me.vertices), np.float32)
me.attributes['.sculpt_mask'].data.foreach_get('value', m)
farz = np.abs(co[:, 2] - 0.1) > 0.05
check('The mask comes along', np.mean(m[farz] == (co[farz, 2] > 0.1)) > 0.97)
bpy.data.objects.remove(ob)

# --- a coarse input (12 triangles) and an open one ----------------------------------------------------------------
cube = box((0, 0, 0), (1.0, 0.5, 0.25), 'Cube')
msg = qf.remesh_object(cube, 1500)
opn, nm, quads, val4 = topo(cube.data)
d = cube.dimensions
check('A 12-triangle cube is subdivided first: about 1,500 quads, closed, same size', abs(len(cube.data.polygons)
      - 1500) < 300 and opn == 0 and quads > 0.95 and abs(d.x - 2.0) < 1e-3 and abs(d.z - 0.5) < 1e-3,
      (msg, opn, quads, tuple(d)))
bpy.ops.mesh.primitive_grid_add(x_subdivisions=60, y_subdivisions=60, size=2.0)
grid = C.active_object
co = np.empty(len(grid.data.vertices) * 3)
grid.data.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
co[:, 2] = 0.15 * np.sin(co[:, 0] * 2.0)
grid.data.vertices.foreach_set('co', co.ravel())
grid.data.update()
msg = qf.remesh_object(grid, 800)
opn, nm, quads, val4 = topo(grid.data)
co = np.empty(len(grid.data.vertices) * 3)
grid.data.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
check('An open sheet keeps its border (not filled) and its size', opn > 40 and nm == 0 and quads > 0.9
      and abs(co[:, 0].max() - 1.0) < 1e-3 and abs(co[:, 1].min() + 1.0) < 1e-3, (msg, opn, nm, quads))
bpy.data.objects.remove(cube)
bpy.data.objects.remove(grid)

# --- 0.24.73 a decimated part: its hard edges are followed (guide lines) and marked for Hard Edges -----------------
from mecha_lab import hard_edges as he
ob = part('Guided', 0.012)
V0, T0 = arrays(ob.data)
cr = creases(V0, T0)
fd.decimate_object(ob, 3, even=True)
Vd, Td = arrays(ob.data)
P, Fq, _t, _p, st = qf.remesh_arrays(Vd, Td, 2500)
check('A decimated input (few triangles per wanted face) is followed edge by edge: its hard edges become guide '
      'lines', st['guide'] > 50, st['guide'])
twin = ob.copy()
C.collection.objects.link(twin)
msg = qf.remesh_object(ob, 2500)
me = ob.data
hard = he.hard_flags(me)
check('... the quads\' hard edges come marked (crease + bevel weight; Hard Edges bevel / subdivide work at once)',
      hard.sum() > 50 and he.KEY in ob and (np.array([d.value for d in me.attributes['crease_edge'].data])[hard]
                                             == 1.0).all() and 'hard edges marked' in msg, (int(hard.sum()), msg))
ev = np.empty(len(me.edges) * 2, np.int64)
me.edges.foreach_get('vertices', ev)
ev = ev.reshape(-1, 2)[hard]
co = np.empty(len(me.vertices) * 3)
me.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
from mathutils.kdtree import KDTree
kd = KDTree(len(cr))
for i, p in enumerate(cr.tolist()):
    kd.insert(p, i)
kd.balance()
far = np.array([kd.find(((co[a] + co[b]) * 0.5).tolist())[2] for a, b in ev])
check('... and they run along the original creases (90 %+ of them within 2 % of the size)', np.mean(far < 0.04) > 0.9,
      round(float(np.mean(far < 0.04)), 3))
check('... an Alt+D twin keeps its own (old) mesh: only the SubTool worked on changes', twin.data is not me
      and len(twin.data.polygons) != len(me.polygons), (len(twin.data.polygons), len(me.polygons)))
n_before = len(ob.data.polygons)
saved = fd._write_attrs
fd._write_attrs = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('simulated failure'))
try:
    try:
        qf.remesh_object(ob, 1000)
        failed = False
    except RuntimeError:
        failed = True
finally:
    fd._write_attrs = saved
check('A failure halfway leaves the SubTool\'s mesh as it was (the result is built apart, then swapped in)',
      failed and len(ob.data.polygons) == n_before and ob.data.name == me.name, (failed, len(ob.data.polygons)))
bpy.data.objects.remove(twin)
bpy.data.objects.remove(ob)

# --- the ZBrush shelf -----------------------------------------------------------------------------------------------
ob = part('ZB', 0.02)
zs.on = lambda c: getattr(c, 'mode', '') == 'SCULPT'
bpy.ops.object.mode_set(mode='SCULPT')
zb = C.scene.mch_zb
root = pc.capture(zu.draw_tool_shelf, C)
boxes = {}
for nd in pc.walk(root):
    if nd.kind == 'box':
        lab = next((c.opts.get('text') for c in nd.children if c.kind == 'label'), None)
        acts = {x.opts.get('props', {}).get('action') for x in pc.walk(nd) if x.kind == 'op'}
        props = {x.prop for x in pc.walk(nd) if x.kind == 'prop'}
        boxes[lab] = (acts, props, [x.opts.get('expand') for x in pc.walk(nd) if x.prop == 'qr_mode'])
qb = boxes.get('Quad Remesh')
check('Quad Remesh has its own box on the ZBrush shelf (not under Decimation)', qb is not None
      and 'QUAD_REMESH' not in boxes.get('Decimation', (set(),))[0], sorted(k for k in boxes if k))
check('... Quad Remesh + Target, Mostly Quads / All Quads side by side, Hard Edges, Half / Same / Double',
      qb is not None and {'QUAD_REMESH', 'QR_HALF', 'QR_SAME', 'QR_DOUBLE'} <= qb[0]
      and {'qr_target', 'qr_mode', 'qr_angle'} <= qb[1] and qb[2] == [True], qb)
check('Mostly Quads by default, Hard Edges 30 degrees', zb.qr_mode == 'MOSTLY'
      and abs(math.degrees(zb.qr_angle) - 30.0) < 1e-4)
n0 = len(ob.data.polygons)
steps0 = len(bpy.context.window_manager.operators) if bpy.context.window_manager else 0
r = bpy.ops.mch.zb_action(action='QR_HALF')
check('Half: the target becomes half the polygons now (a setting, no undo step)', abs(zb.qr_target * 1000 - n0 / 2)
      < 10, (zb.qr_target, n0))
zb.qr_target = 1.5
zb.qr_mode = 'ALL'
bpy.ops.ed.undo_push(message='before')
r = bpy.ops.mch.zb_action(action='QUAD_REMESH')
ob = bpy.data.objects['ZB']
opn, nm, quads, val4 = topo(ob.data)
check('Quad Remesh on the shelf: All Quads, about 1,500, back in Sculpt Mode', r == {'FINISHED'} and quads == 1.0
      and abs(len(ob.data.polygons) - 1500) < 300 and C.mode == 'SCULPT', (len(ob.data.polygons), quads, C.mode))
check('... a recovery copy is made before it (one of the risky steps)', 'QUAD_REMESH' in zs.RISKY
      and 'QR_HALF' in zs.SETTING_ACTIONS)
bpy.ops.ed.undo()
ob = bpy.data.objects['ZB']
check('Ctrl+Z brings the polygons back, still in Sculpt Mode', len(ob.data.polygons) == n0 and C.mode == 'SCULPT',
      (len(ob.data.polygons), n0, C.mode))
bpy.ops.object.mode_set(mode='OBJECT')
ob.shape_key_add(name='Basis')
check('Shape keys: it says to remove them first (nothing changed)', 'shape keys' in qf.remesh_object(ob, 500)
      and len(ob.data.polygons) == n0)
ob.shape_key_clear()
ob.modifiers.new('m', 'MULTIRES')
check('Multires: it says to delete / apply the levels first', 'Multires' in qf.remesh_object(ob, 500))

summary()
