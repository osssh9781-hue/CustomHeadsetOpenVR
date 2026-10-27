"""Field-aligned quad remesher - prototype driver (not part of the add-on yet).

    <python with bpy 5.2> run_proto.py [--allquads] [--deg=30] [--relax] <target quads> <block|strap|file.blend> <out.blend>

block / strap: built-in hard-surface test parts (voxel remeshed); a .blend: its first mesh object.
Prints RESULT lines (quads %, valence-4 %, open edges, error to the original, hard-edge fidelity)."""
import os
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tests'))
sys.path.insert(0, HERE)
import time, math
from _harness import bpy, fresh
import numpy as np, bmesh
import mecha_lab
from mecha_lab import fast_decimate as fd
mecha_lab.register(); fresh(); C = bpy.context; S = C.scene

def boolean(ob, cutter, op='DIFFERENCE'):
    m = ob.modifiers.new('b', 'BOOLEAN'); m.object = cutter; m.operation = op; m.solver = 'EXACT'
    with C.temp_override(object=ob, active_object=ob):
        bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(cutter)

def box(loc, size, name='c'):
    bpy.ops.mesh.primitive_cube_add(location=loc); o = C.active_object; o.scale = size; o.name = name
    bpy.ops.object.transform_apply(scale=True); return o

def voxel(ob, size):
    ob.data.remesh_voxel_size = size
    with C.temp_override(object=ob, active_object=ob):
        bpy.ops.object.voxel_remesh()

def part_block():
    p = box((0, 0, 0), (1.0, 0.6, 0.4), 'Block')
    boolean(p, box((0.55, 0, 0.35), (0.5, 0.7, 0.2)))
    boolean(p, box((-0.1, 0, 0.4), (0.08, 0.7, 0.15)))
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.18, depth=2, location=(-0.5, 0, 0), rotation=(math.pi / 2, 0, 0))
    boolean(p, C.active_object)
    voxel(p, 0.008)
    return p

def part_strap():
    p = box((0, 0, 0), (1.3, 0.16, 0.06), 'Strap')
    with C.temp_override(object=p, active_object=p):
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.subdivide(number_cuts=40); bpy.ops.object.mode_set(mode='OBJECT')
    for x in (-0.55, 0.15):                                   # two long slots
        c = box((x, 0, 0), (0.28, 0.07, 0.2)); boolean(p, c)
    m = p.modifiers.new('bend', 'SIMPLE_DEFORM'); m.deform_method = 'BEND'; m.angle = math.radians(140); m.deform_axis = 'Z'
    with C.temp_override(object=p, active_object=p):
        bpy.ops.object.modifier_apply(modifier=m.name)
    voxel(p, 0.006)
    return p

def arrays(me):
    me.calc_loop_triangles()
    V = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('co', V)
    T = np.empty(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get('vertices', T)
    return V.reshape(-1, 3), T.reshape(-1, 3)

import fieldquad as fq3
which = sys.argv[-2]
target = int(sys.argv[-3])
ALLQ = '--allquads' in sys.argv
TARGET_OUT = target
if ALLQ:
    target = max(target // 4, 50)
LW = 0.1
if which == 'block':
    p = part_block()
elif which == 'strap':
    p = part_strap()
else:
    bpy.ops.wm.open_mainfile(filepath=which)
    p = next(o for o in bpy.data.objects if o.type == 'MESH')
V0, T0 = arrays(p.data)
print(f'RESULT input {len(V0):,} points')
t = time.perf_counter()
area0 = 0.5 * np.linalg.norm(np.cross(V0[T0[:, 1]] - V0[T0[:, 0]], V0[T0[:, 2]] - V0[T0[:, 0]]), axis=1).sum()
h0 = math.sqrt(area0 / target)
CDEG = float(next((a.split('=')[1] for a in sys.argv if a.startswith('--deg=')), 30))
CHAIN = float(next((a.split('=')[1] for a in sys.argv if a.startswith('--chain=')), 1.5))
levels = []
src = (V0, T0)
for mult in (16, 4, 1, 0.25):
    dV, dF, _a, _b = fd.run(src[0], src[1], max(int(target * mult), 200), even=True, uniform=LW)
    src = (dV, dF)
    levels.append(fq3.Level(dV, dF, crease_deg=CDEG, min_chain=CHAIN * h0))
print(f'RESULT levels {[L.n for L in levels]} in {time.perf_counter() - t:.2f}s')
h = math.sqrt(levels[0].area / target)
L0 = levels[0]
el = np.linalg.norm(L0.V[L0.E[:, 0]] - L0.V[L0.E[:, 1]], axis=1)
print(f'RESULT h {h:.4f}, fine edges mean {el.mean() / h:.2f} h, max {el.max() / h:.2f} h, creases {L0.crease.sum()}')
t = time.perf_counter()
Q, O = fq3.solve(levels, h, orient_iters=(20, 30, 60, 200), pos_iters=(30, 40, 80, 200), log=lambda s: print('RESULT', s))
print(f'RESULT solve {time.perf_counter() - t:.2f}s')
t = time.perf_counter()
pos, faces, kind = fq3.extract(L0, Q, O, h, log=lambda s: print('RESULT', s))
print(f'RESULT extract {time.perf_counter() - t:.2f}s')
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
from mathutils import Vector
bvh = BVHTree.FromPolygons(V0.tolist(), T0.tolist())
ce = L0.E[L0.crease]
ca, cb = L0.V[ce[:, 0]], L0.V[ce[:, 1]]
kd = KDTree(len(ce))
for k, m in enumerate(((ca + cb) * 0.5).tolist()):
    kd.insert(m, k)
kd.balance()
def snap(P, kind):
    out = P.copy()
    for c, v in enumerate(P):
        if kind[c] == 2:
            continue
        if kind[c] == 1 and len(ce):
            best = None
            for _co, k, _d in kd.find_n(v.tolist(), 8):
                a, b = ca[k], cb[k]
                ab = b - a
                tt = min(1.0, max(0.0, (v - a) @ ab / max(ab @ ab, 1e-30)))
                x = a + ab * tt
                dd = ((x - v) ** 2).sum()
                if best is None or dd < best[0]:
                    best = (dd, x)
            out[c] = best[1]
        else:
            out[c] = bvh.find_nearest(Vector(v))[0][:]
    return out
pos = snap(pos, kind)
if '--relax' in sys.argv:
    pos = fq3.relax(pos, faces, kind, snap, iters=2)
faces, nj = fq3.join_tris(pos, faces)
print(f'RESULT joined {nj} triangle pairs')
if ALLQ:
    pos, faces, kind = fq3.split_all(pos, faces, kind)
    pos = snap(pos, kind)
    h = h * 0.5
ar = []
for f in faces:
    pp = pos[f]
    a = 0.0
    for k in range(1, len(f) - 1):
        a += 0.5 * np.linalg.norm(np.cross(pp[k] - pp[0], pp[k + 1] - pp[0]))
    ar.append(a)
ar = np.array(ar)
from collections import Counter
print('RESULT slivers', (ar < 0.05 * h * h).sum())
sizes = {}
for f in faces: sizes[len(f)] = sizes.get(len(f), 0) + 1
me = bpy.data.meshes.new('FQ'); me.from_pydata(pos.tolist(), [], faces); me.validate(); me.update()
bm = bmesh.new(); bm.from_mesh(me)
val = [len(v.link_edges) for v in bm.verts if v.is_manifold and not v.is_boundary]
bnd = sum(1 for e in bm.edges if e.is_boundary)
nonman = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
bm.free()
cen = [sum((me.vertices[i].co for i in f.vertices), Vector()) / len(f.vertices) for f in me.polygons]
err = np.array([bvh.find_nearest(c)[3] for c in cen])
print(f'RESULT mesh: {len(me.vertices):,} points, faces {dict(sorted(sizes.items()))}, quads {sizes.get(4,0)/max(len(faces),1)*100:.1f}%, '
      f'valence4 {sum(1 for k in val if k == 4)/max(len(val),1)*100:.1f}%, open edges {bnd}, non-manifold {nonman}, '
      f'face-centre error mean {err.mean()/h:.3f} h max {err.max()/h:.3f} h')
# hard-edge fidelity: crease points of the fine level -> distance to the result's sharp edges
rb = bmesh.new(); rb.from_mesh(me); rb.edges.ensure_lookup_table()
sh = [e for e in rb.edges if e.is_manifold and e.calc_face_angle(0) > math.radians(30)]
if len(ce) and sh:
    sa = np.array([e.verts[0].co[:] for e in sh]); sb = np.array([e.verts[1].co[:] for e in sh])
    kd2 = KDTree(len(sh))
    for k, m in enumerate(((sa + sb) * 0.5).tolist()): kd2.insert(m, k)
    kd2.balance()
    dists = []
    for v in ((ca + cb) * 0.5):
        best = 1e9
        for _co, k, _d in kd2.find_n(v.tolist(), 6):
            a, b = sa[k], sb[k]; ab = b - a
            tt = min(1.0, max(0.0, (v - a) @ ab / max(ab @ ab, 1e-30)))
            best = min(best, np.linalg.norm(a + ab * tt - v))
        dists.append(best)
    dists = np.array(dists)
    print(f'RESULT hard edges: {len(sh)} sharp result edges; crease points within 0.1h of one {np.mean(dists < 0.1 * h) * 100:.1f}%, '
          f'mean {dists.mean() / h:.3f} h')
for e in rb.edges:
    e.smooth = not (e.is_manifold and e.calc_face_angle(0) > math.radians(30))
for f in rb.faces: f.smooth = True
rb.to_mesh(me); rb.free()
ob = bpy.data.objects.new(which + '_Field', me); bpy.context.collection.objects.link(ob)
for o2 in list(bpy.data.objects):
    if o2 is not ob: bpy.data.objects.remove(o2)
bpy.ops.wm.save_as_mainfile(filepath=[a for a in sys.argv if a.endswith('.blend')][-1])
