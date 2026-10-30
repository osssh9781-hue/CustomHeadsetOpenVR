"""Prototype: bake-ready high poly - hard edges kept exactly, the faces between them subdivided and rounded
(midpoint subdivision + Taubin smoothing with line / corner constraints).  Usage: bakehp.py in.fbx OBJECT levels out_dir"""
import bpy, bmesh, sys, os, math, time
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

FBX, NAME, LEVELS, OUT = sys.argv[-4], sys.argv[-3], int(sys.argv[-2]), sys.argv[-1]
ANGLE = math.radians(30.0)
LAM, MU = 0.5, -0.53
ITERS = 10
os.makedirs(OUT, exist_ok=True)
C = bpy.context
bpy.ops.import_scene.fbx(filepath=FBX)
for o in list(bpy.data.objects):
    if o.name != NAME:
        bpy.data.objects.remove(o, do_unlink=True)
src = bpy.data.objects[NAME]
me0 = src.data


def mark_hard(me, angle):
    bm = bmesh.new(); bm.from_mesh(me)
    hard = [e for e in bm.edges if len(e.link_faces) != 2 or e.calc_face_angle(0.0) > angle]
    for e in bm.edges: e.smooth = True
    for e in hard: e.smooth = False
    # drop lone specks: a single hard edge whose ends have no other hard edge
    deg = {}
    for e in hard:
        for v in e.verts: deg[v.index] = deg.get(v.index, 0) + 1
    n = 0
    for e in hard:
        if deg[e.verts[0].index] == 1 and deg[e.verts[1].index] == 1:
            e.smooth = True; n += 1
    bm.to_mesh(me); bm.free()
    return len(hard) - n


def subdivide_once(me):
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=1, use_grid_fill=True)
    bm.to_mesh(me); bm.free()


def arrays(me):
    nv = len(me.vertices)
    co = np.empty(nv * 3, np.float32); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3).astype(np.float64)
    ne = len(me.edges)
    E = np.empty(ne * 2, np.int32); me.edges.foreach_get('vertices', E); E = E.reshape(-1, 2)
    sharp = np.zeros(ne, bool)
    a = me.attributes.get('sharp_edge')
    if a is not None: a.data.foreach_get('value', sharp)
    return co, E, sharp


def smooth(me, iters):
    co, E, sharp = arrays(me)
    nv = len(co)
    Eh = E[sharp]
    deg_all = np.bincount(E.ravel(), minlength=nv).astype(np.float64)
    deg_h = np.bincount(Eh.ravel(), minlength=nv).astype(np.float64)
    corner = (deg_h >= 3) | (deg_h == 1)
    line = deg_h == 2
    free = ~corner
    def avg(c, EE, deg):
        s = np.zeros_like(c)
        for k in range(3):
            s[:, k] = np.bincount(EE[:, 0], weights=c[EE[:, 1], k], minlength=nv) + np.bincount(EE[:, 1], weights=c[EE[:, 0], k], minlength=nv)
        return s / np.maximum(deg, 1)[:, None]
    for _ in range(iters):
        for w in (LAM, MU):
            t = avg(co, E, deg_all)
            if len(Eh):
                th = avg(co, Eh, deg_h)
                t[line] = th[line]
            d = (t - co); d[~free] = 0
            co += w * d
    me.vertices.foreach_set('co', co.astype(np.float32).ravel()); me.update()
    return int(corner.sum()), int(line.sum())


t0 = time.time()
n_hard0 = mark_hard(me0, ANGLE)
faces0, verts0 = len(me0.polygons), len(me0.vertices)
hp = src.copy(); hp.data = me0.copy(); hp.name = NAME + '_BakeHP'
C.scene.collection.objects.link(hp)
me = hp.data
for lv in range(LEVELS):
    subdivide_once(me)
    _, _, sh = arrays(me)
    nc, nl = smooth(me, ITERS)
    print(f'level {lv+1}: {len(me.polygons):,} faces, hard edges {int(sh.sum()):,}, corners {nc}, line verts {nl}, {time.time()-t0:.1f}s')
nc, nl = smooth(me, ITERS)
# measure: distance of the result to the original surface, and that hard-edge vertices did not move
verts = [v.co for v in me0.vertices]; polys = [list(p.vertices) for p in me0.polygons]
tree = BVHTree.FromPolygons(verts, polys, all_triangles=False)
co, E, sharp = arrays(me)
size = max(src.dimensions)
rng = np.random.default_rng(1); idx = rng.choice(len(co), size=min(20000, len(co)), replace=False)
dist = []
for i in idx:
    r = tree.find_nearest(Vector(co[i]))
    dist.append(r[3] if r[0] is not None else 0.0)
dist = np.array(dist) / size * 100
# original vertices are the first verts0 of the subdivided mesh (bmesh keeps order)
co0 = np.empty(verts0 * 3, np.float32); me0.vertices.foreach_get('co', co0); co0 = co0.reshape(-1, 3)
E0 = np.empty(len(me0.edges) * 2, np.int32); me0.edges.foreach_get('vertices', E0); E0 = E0.reshape(-1, 2)
sh0 = np.zeros(len(me0.edges), bool); me0.attributes['sharp_edge'].data.foreach_get('value', sh0)
dh0 = np.bincount(E0[sh0].ravel(), minlength=verts0)
corner0 = (dh0 >= 3) | (dh0 == 1)
mv = np.linalg.norm(co[:verts0] - co0, axis=1) / size * 100
print(f'RESULT faces {faces0:,} -> {len(me.polygons):,}; hard edges {n_hard0:,}; surface distance %size: mean {dist.mean():.3f} '
      f'p95 {np.percentile(dist,95):.3f} max {dist.max():.3f}; corner verts moved max {mv[corner0].max() if corner0.any() else 0:.4f}% '
      f'({int(corner0.sum())} corners); all original verts moved mean {mv.mean():.3f}% max {mv.max():.3f}%; {time.time()-t0:.1f}s')
for o in (src, hp):
    o.data.shade_smooth()
bpy.data.meshes.remove(bpy.data.meshes.get('unused'), do_unlink=True) if bpy.data.meshes.get('unused') else None
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, f'{NAME}_bakehp_L{LEVELS}.blend'))
print('SAVED')
