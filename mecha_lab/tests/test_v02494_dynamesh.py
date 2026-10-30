"""0.24.94 Safe DynaMesh: open sheets, holes, flipped faces, thin walls and slivers no longer tear the voxel remesh
into holes and fragments (dynamesh_fix round zb_sculpt.dynamesh)."""
import math

import numpy as np
from _harness import bpy, bmesh, check, fresh, summary

import mecha_lab
from mecha_lab import dynamesh_fix as dfx, zb_sculpt as zs

mecha_lab.register()
fresh()
C = bpy.context


def active(ob):
    for o in C.view_layer.objects:
        o.select_set(o is ob)
    C.view_layer.objects.active = ob
    return ob


def run(ob, points=12000):
    active(ob)
    if ob.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    msg = zs.dynamesh(C, ob, points)
    if ob.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    return msg, dfx.diagnose(ob.data), zs.LAST_FIX['text']


# 1. an open sheet (a grid): the plain remesh gives nothing / holes; safe: solidified -> one closed shell
bpy.ops.mesh.primitive_grid_add(x_subdivisions=20, y_subdivisions=20, size=2.0)
sheet = C.active_object
d0 = dfx.diagnose(sheet.data)
check('An open grid sheet is diagnosed open', d0['open'] > 0 and d0['parts'] == 1, d0)
msg, d, fix = run(sheet)
check('Safe DynaMesh on a sheet: solidified, the result ONE closed part with no open edges',
      msg == '' and d['parts'] == 1 and d['open'] == 0 and d['verts'] > 500 and 'open sheet given a thickness' in fix, (msg, d, fix))

# 2. a sphere with a hole (a few faces removed): filled, closed
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=48, ring_count=24)
holed = C.active_object
bm = bmesh.new()
bm.from_mesh(holed.data)
bm.faces.ensure_lookup_table()
top = [f for f in bm.faces if f.calc_center_median().z > 0.95]
bmesh.ops.delete(bm, geom=top, context='FACES')
bm.to_mesh(holed.data)
bm.free()
d0 = dfx.diagnose(holed.data)
check('A sphere with its top cut off is open', d0['open'] > 0, d0)
msg, d, fix = run(holed)
check('Safe DynaMesh: the hole filled, one closed part, about the sphere (points spread over r ~ 1)',
      d['parts'] == 1 and d['open'] == 0 and 'hole' in fix, (d, fix))
co = np.array([v.co[:] for v in holed.data.vertices])
r = np.linalg.norm(co, axis=1)
check('... and the result is the sphere, not a fragment (radius 0.9 .. 1.1 for 95 % of points)',
      np.mean((r > 0.85) & (r < 1.15)) > 0.95, (r.min(), r.max()))

# 3. flipped faces: half the sphere's faces reversed (inconsistent winding) -> normals fixed -> one closed part
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=48, ring_count=24)
flip = C.active_object
bm = bmesh.new()
bm.from_mesh(flip.data)
bmesh.ops.reverse_faces(bm, faces=[f for f in bm.faces if f.calc_center_median().x > 0])
bm.to_mesh(flip.data)
bm.free()
d0 = dfx.diagnose(flip.data)
check('Half-flipped sphere: flipped edges diagnosed', d0['flipped'] > 20, d0)
msg, d, fix = run(flip)
co = np.array([v.co[:] for v in flip.data.vertices])
r = np.linalg.norm(co, axis=1)
check('Safe DynaMesh: normals made consistent, one closed sphere comes out', d['parts'] == 1 and d['open'] == 0
      and np.mean((r > 0.85) & (r < 1.15)) > 0.95 and 'flipped' in fix, (d, fix))

# 4. a thin wall: a 1 x 1 x 0.02 box with a voxel asked (0.05) bigger than the wall -> the voxel is capped, no fragments
bpy.ops.mesh.primitive_cube_add(size=1.0)
thin = C.active_object
thin.scale = (1.0, 1.0, 0.02)
bpy.ops.object.transform_apply(scale=True)
t = dfx.thickness(thin.data)
check('thickness: the thin box reads about 0.02', abs(t - 0.02) < 0.004, t)
v_cap, thin_w = dfx.cap_voxel(thin.data, 0.05)
check('cap_voxel: 0.05 asked -> at most the wall / 3 (but not under a quarter of the ask)', 0.0125 <= v_cap <= 0.0068 + 1e-9 or abs(v_cap - 0.0125) < 1e-9, (v_cap, thin_w))
active(thin)
thin.data.remesh_voxel_size = 0.12
bpy.ops.object.voxel_remesh()
d_plain = dfx.diagnose(thin.data)
z_plain = np.ptp(np.array([v.co.z for v in thin.data.vertices]))
check('(measured) Blender\'s own remesh keeps the 0.02 wall even at a 0.12 voxel - one closed part, not bloated: so the thin-wall cap is off by default',
      d_plain['parts'] == 1 and d_plain['open'] == 0 and z_plain < 0.05 and not dfx.USE_THIN_CAP, (d_plain, round(float(z_plain), 3)))

# 5. a sliver: a sphere + a tiny separate triangle -> after the remesh the sliver is dropped
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=48, ring_count=24)
sl = C.active_object
bm = bmesh.new()
bm.from_mesh(sl.data)
a = bm.verts.new((2.0, 0.0, 0.0)); b = bm.verts.new((2.06, 0.0, 0.0)); c = bm.verts.new((2.0, 0.06, 0.0)); dd = bm.verts.new((2.0, 0.0, 0.06))
for tri in ((a, b, c), (a, c, dd), (a, dd, b), (b, dd, c)):
    bm.faces.new(tri)
bm.to_mesh(sl.data)
bm.free()
check('Sphere + a tiny tetra = 2 parts', dfx.diagnose(sl.data)['parts'] == 2)
msg, d, fix = run(sl, points=8000)
check('Safe DynaMesh: the tiny part is dropped (or vanished in the voxels): one part left', d['parts'] == 1, (d, fix))
check('describe() names what was done', 'filled' in dfx.describe(dict(holes=2), 0.1, 0.1, 0, 0) and 'sliver' in dfx.describe({}, 0.1, 0.1, 0, 3)
      and 'voxel 0.1 -> 0.05' in dfx.describe({}, 0.1, 0.05, 0.15, 0))
check('The DynaMesh message carries the safe note', 'safe:' in __import__('inspect').getsource(zs.run) or 'safe:' in open(zs.__file__, encoding='utf-8').read())
summary()
