"""0.24.95 (user: "다이나메쉬 하면 가끔 뾰족하게 메쉬가 튀어서 다이나메쉬 되는데 이거 왜 그래?") Safe DynaMesh closes every
opening with one face before the voxel remesh.  Blender fills a face in its own plane, so the cap of an opening that
cannot lie flat - a crumpled cloth's outline doubling back over itself, a bent / twisted cut - became triangles
folding over each other and out through the model, and the remesh made spikes of them (a crumpled cloth: 1,867
points up to 12 voxels off it).  Such a cap is not kept (``dynamesh_fix.folded_cap``): the sheet gets its thickness
instead.  Also: a mesh with loose edges AND loose points stopped Safe DynaMesh with a Python error."""
import math
import random

from _harness import bmesh, bpy, check, fresh, summary
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import mecha_lab
from mecha_lab import dynamesh_fix as dfx, voxel_for_points

mecha_lab.register()
fresh()
C = bpy.context


def obj(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    C.scene.collection.objects.link(ob)
    return ob


def crumpled():
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=40, y_segments=40, size=1.0)
    rnd = random.Random(5)
    for v in bm.verts:
        v.co.z = 0.25 * math.sin(9 * v.co.x + 3 * v.co.y) + rnd.uniform(-0.02, 0.02)
    for v in bm.verts:                                   # (the right side folded back over the left)
        if v.co.x > 0.3:
            v.co.z = -v.co.z * 0.3
            v.co.x = 0.3 - (v.co.x - 0.3) * 0.9
    return bm


def remesh(ob, points=20000):
    v = voxel_for_points(C, ob, points)
    done = dfx.prepare(ob.data, v)
    ob.data.remesh_voxel_size = v
    with C.temp_override(object=ob, active_object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
        bpy.ops.object.voxel_remesh()
    dfx.cleanup(ob.data)
    return v, done


# ---- the cap test on its own
bm = crumpled()
res = bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if len(e.link_faces) == 1], sides=0)
cap = res['faces'][0]
check('folded_cap: the crumpled cloth\'s outline cap (160 sides, doubling back over itself) would fold',
      len(cap.verts) == 160 and dfx.folded_cap(cap))
bm.free()
bm = bmesh.new()
f = bm.faces.new([bm.verts.new((math.cos(2 * math.pi * i / 32), math.sin(2 * math.pi * i / 32), 0.0)) for i in range(32)])
saddle = bmesh.new()
g = saddle.faces.new([saddle.verts.new((math.cos(a), math.sin(a), 0.6 * math.cos(2 * a)))
                      for a in (2 * math.pi * i / 32 for i in range(32))])
check('... a flat round opening does not, a saddle-bent one (corners 0.6 off its plane on a width of 2) does',
      not dfx.folded_cap(f) and dfx.folded_cap(g))
bm.free()
saddle.free()

# ---- Safe DynaMesh on the crumpled cloth: no spikes
ob = obj('cloth', crumpled())
ref = BVHTree.FromPolygons([v.co.copy() for v in ob.data.vertices], [p.vertices[:] for p in ob.data.polygons])
v, done = remesh(ob)
co = np.array([p.co[:] for p in ob.data.vertices])
d = np.array([ref.find_nearest(Vector(c))[3] for c in co]) / v
check(f'Safe DynaMesh of the crumpled cloth: the outline left open and the sheet thickened (not capped), every point '
      f'within {d.max():.1f} voxels of the cloth (before: 1,867 points out to 12 voxels - spikes)',
      done['holes'] == 0 and done['solidified'] and d.max() <= dfx.SHEET_VOXELS + 1.5 and len(co) > 10000,
      (done, round(float(d.max()), 1), len(co)))

# ---- an ordinary opening is still closed
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=1.0)
bmesh.ops.delete(bm, geom=[q for q in bm.faces if q.calc_center_median().z < -0.7], context='FACES')
ob = obj('bowl', bm)
v, done = remesh(ob)
zmin = min(p.co.z for p in ob.data.vertices)
check('A sphere with its bottom cut off: the flat opening is still capped (a closed, solid result)',
      done['holes'] == 1 and not done['solidified'] and zmin > -0.85, (done, round(zmin, 3)))

# ---- loose edges and loose points together
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=2.0)
a, b = bm.verts.new((3, 0, 0)), bm.verts.new((3, 1, 0))
bm.edges.new((a, b))
bm.verts.new((4, 4, 4))
ob = obj('wire', bm)
try:
    v, done = remesh(ob)
    ok, err = True, ''
except TypeError as ex:
    ok, err = False, str(ex)
check('Safe DynaMesh of a part with a loose edge and a loose point: runs (before: "TypeError: BMVert has been '
      'removed" - the Python error in the status bar)', ok and done['loose'] >= 2, err or done)
summary()
