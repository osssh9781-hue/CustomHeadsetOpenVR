"""0.24.95 The Mech Shader's edges / crevices (mch_curv) on DENSE meshes (DynaMesh, Bake High Poly, sculpted creatures):
a sharp edge is one row of points there, and averaging it with the flat on either side read only ~0.46 of an edge
(a DynaMesh cube's edges 0.13) - the edge wear hardly showed.  Now the convexity at the wear width is measured too
(the points smoothed over about the wear width, how far each stands out of its smoothed place) and the stronger kept:
sharp edges read full across a band the wear width wide, crevices too; fine bumps (skin) stay small; a coarse face
next to its bevel stays flat (a point with an edge longer than the wear width fades that measure)."""
import math
import os
import sys
import time

from _harness import bmesh, bpy, check, fresh, summary

import numpy as np

import mecha_lab
from mecha_lab import mech_shader as ms

mecha_lab.register()
fresh()
C = bpy.context
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools_dev'))
import make_mech_preset_icons as mk  # noqa: E402


def curv(me):
    t0 = time.time()
    ms.store_curvature(me)
    dt = time.time() - t0
    k = np.empty(len(me.vertices))
    me.attributes[ms.CURV].data.foreach_get('value', k)
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    return k, co.reshape(-1, 3), dt


# a DynaMesh-like cube
bpy.ops.mesh.primitive_cube_add(size=2.0)
cube = C.active_object
m = cube.modifiers.new('r', 'REMESH')
m.mode, m.voxel_size = 'VOXEL', 0.02
bpy.ops.object.modifier_apply(modifier='r')
k, co, dt = curv(cube.data)
srt = np.sort(np.abs(co), 1)
edge = srt[:, 1] > 0.97
mid = srt[:, 1] < 0.5
check('A dense cube (voxel 0.02, 61 k points): its edges read as edges (mean > 0.5, top 10 % > 0.85 - before: 0.13), '
      'its face middles flat', k[edge].mean() > 0.5 and np.percentile(k[edge], 90) > 0.85
      and np.abs(k[mid]).max() < 0.05, (round(float(k[edge].mean()), 2), round(float(np.percentile(k[edge], 90)), 2),
                                         round(float(np.abs(k[mid]).max()), 3)))
check('... measured fast (well under a second for 61 k points)', dt < 1.5, round(dt, 2))

# the panelled icon ball: groove lips edges, groove bottoms crevices
ball = mk.ball()
k, co, _dt = curv(ball.data)
z = co[:, 2]
r = np.linalg.norm(co, axis=1)
lip = (r > 0.985) & (np.abs(np.abs(z - 0.3) - (mk.GROOVE_HALF + mk.GROOVE_LIP)) < 0.02)
bottom = (np.abs(z - 0.3) < mk.GROOVE_HALF * 0.6) & (r < 0.95)
check('A dense panelled ball (41 k points): the grooves\' lips edges (mean > 0.85 - before 0.24), their bottoms '
      'crevices (< -0.2 - before 0.0)', k[lip].mean() > 0.85 and k[bottom].mean() < -0.2,
      (round(float(k[lip].mean()), 2), round(float(k[bottom].mean()), 2)))

# fine bumps (skin): stay small
bm = bmesh.new()
bmesh.ops.create_icosphere(bm, subdivisions=6, radius=1.0)
for v in bm.verts:
    p = v.co
    v.co = p * (1.0 + 0.006 * math.sin(p.x * 60) * math.sin(p.y * 60) * math.sin(p.z * 60))
me = bpy.data.meshes.new('bumpy')
bm.to_mesh(me)
bm.free()
k, co, _dt = curv(me)
check('Fine bumps much smaller than the wear width (skin) read little (mean < 0.25)', np.abs(k).mean() < 0.25,
      round(float(np.abs(k).mean()), 2))

# a coarse bevelled block: its face stays flat right next to the bevel
bpy.ops.mesh.primitive_cube_add(location=(0, 6, 0))
cq = C.active_object
cq.modifiers.new('b', 'BEVEL').width = 0.03
cq.modifiers['b'].segments = 3
sub = cq.modifiers.new('s', 'SUBSURF')
sub.subdivision_type, sub.levels = 'SIMPLE', 2
bpy.ops.object.convert(target='MESH')
k, co, _dt = curv(cq.data)
mid = ((np.abs(co) > 0.999).sum(1) == 1) & (np.abs(co).min(1) < 0.9)
on_bevel = (np.abs(co) > 0.975).sum(1) >= 2
check('A coarse block (big faces next to a thin bevel): the faces stay flat (< 0.15 - the long face edges fade the new '
      'measure), the bevels read', np.abs(k[mid]).max() < 0.15 and k[on_bevel].mean() > 0.25,
      (round(float(np.abs(k[mid]).max()), 3), round(float(k[on_bevel].mean()), 2)))
summary()
