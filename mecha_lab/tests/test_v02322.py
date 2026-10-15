"""0.23.22 Low Poly from a sculpt: flat sides (one n-gon each), live Bevel / Chamfer, original kept."""
import math
import sys
import time

from _harness import bpy, check, fresh, non_manifold, summary
import bmesh
import mecha_lab

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
from mecha_lab import lowpoly as lp

# a "sculpt": a rounded cube (dense, soft edges), with an unapplied 0.01 scale like a ZBrush FBX
bpy.ops.mesh.primitive_cube_add(size=200.0)
sc = C.active_object
sc.name = 'Sculpt'
m = sc.modifiers.new('s', 'SUBSURF')
m.levels = 2
r = sc.modifiers.new('r', 'REMESH')
r.mode = 'VOXEL'
r.voxel_size = 2.0
bpy.ops.object.modifier_apply(modifier='s')
bpy.ops.object.modifier_apply(modifier='r')
sc.scale = (0.01, 0.01, 0.01)
C.view_layer.update()
n0 = len(sc.data.polygons)
check('dense rounded sculpt with scale 0.01', n0 > 20000 and abs(sc.dimensions.x - 1.5) < 0.6, (n0, tuple(sc.dimensions)))
t0 = time.time()
res = bpy.ops.mch.lowpoly_make()
dt = time.time() - t0
lo = C.active_object
check('Make Low Poly: a new object, the original kept and hidden', res == {'FINISHED'} and lo is not sc and
      lp.is_lowpoly(lo) and sc.hide_get() and len(sc.data.polygons) == n0)
check('quick (object-space voxel size - the 0.01 scale used to freeze it)', dt < 20.0, round(dt, 2))
nf = len(lo.data.polygons)
check('a rounded cube becomes a few flat sides (6 sides + its round corners, one face each)', 6 <= nf <= 40, nf)
bm = bmesh.new()
bm.from_mesh(lo.data)
devs = sorted((max(abs((v.co - f.calc_center_median()).dot(f.normal)) for v in f.verts), len(f.verts)) for f in bm.faces)
big = [d for d, n in devs if n > 4]
flat = max(big) < 2e-4 * 167 and devs[-1][0] < 1e-2 * 167
check('closed; the big faces (n-gons) flat, small corner faces nearly', non_manifold(lo) == 0 and flat,
      [(round(d, 3), n) for d, n in devs[-4:]])
bm.free()
check('same size as the sculpt (about)', all(abs(a - b) < 0.25 * b for a, b in zip(lo.dimensions, sc.dimensions)),
      (tuple(lo.dimensions), tuple(sc.dimensions)))
bev = lo.modifiers.get(lp.BEVEL)
check('live Bevel (angle limited) + Weighted Normals', bev is not None and bev.limit_method == 'ANGLE' and
      lo.modifiers.get(lp.NORMALS) is not None)
dg = C.evaluated_depsgraph_get()
f1 = len(lo.evaluated_get(dg).data.polygons)
bev.segments = 4
dg = C.evaluated_depsgraph_get()
f4 = len(lo.evaluated_get(dg).data.polygons)
check('Segments 1 = chamfer, 4 = round (more faces), live', f4 > f1 > nf, (nf, f1, f4))
S.mch_lowpoly.side_angle = 0.0
bpy.ops.mch.lowpoly_make()
check('Re-make with Flatten Sides off: more, smaller faces', len(lo.data.polygons) > nf, len(lo.data.polygons))
bpy.ops.mch.lowpoly_apply()
check('Apply: an ordinary mesh with the bevel baked', not lp.is_lowpoly(lo) and not lo.modifiers.get(lp.BEVEL))
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
