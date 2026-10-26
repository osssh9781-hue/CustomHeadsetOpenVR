"""0.24.44 Base Mesh Alt: Ramp - the drawn polygon carved on a slope: deepest (Carve Depth) at the FIRST edge
drawn, rising back to the surface across the shape (Ramp Length 1 = meets it at the far side; less = deep and
flat first, then the slope).  A facet pressed into the surface, not a flat-bottomed pocket."""
from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import base_mesh as bm_, core_geometry as cg, surface_draw as sd

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)

r = sd.ramp_scale([(0, 5), (5, 5), (10, 5)], [(0, 0), (0, 10), (10, 10), (10, 0)], (0, 0), (0, 10))
check('ramp scale: 1 at the first edge, 0.5 half way, 0 at the far side', [round(x, 6) for x in r] == [1.0, 0.5, 0.0], r)
r = sd.ramp_scale([(0, 5), (5, 5), (10, 5)], [(0, 0), (0, 10), (10, 10), (10, 0)], (0, 10), (0, 0), 0.5)
check('... whichever way round the edge was drawn; Ramp Length 0.5 = flush half way', [round(x, 6) for x in r] == [1.0, 0.0, 0.0], r)
check('first edge = the first two points of the outline', bm_.first_edge([[(1, 1), (1, 1.5), (5, 1), (5, 5)]]) ==
      ((1, 1), (5, 1)))

p = bm_.scene_defaults(C)
p.sketch, p.profile, p.alt_mode, p.carve_depth, p.ramp_length, p.ramp_soft = False, 'FLAT', 'RAMP', 0.2, 1.0, 0.0
SQUARE = [(440, 440), (440, 560), (560, 560), (560, 440)]           # x -0.6 .. 0.6, the first edge at x = -0.6


def depth_at(x):
    C.view_layer.update()
    hit, loc, _n, _i, _o, _m = S.ray_cast(C.evaluated_depsgraph_get(), Vector((x, 0, 5)), Vector((0, 0, -1)))
    return round(1.0 - loc.z, 3) if hit else None


bpy.ops.mesh.primitive_cube_add(size=2.0)
cube = C.active_object
msg = bm_.perform_base(C, [SQUARE], TOP, cutter=True)
d = [depth_at(x) for x in (-0.55, 0.0, 0.5)]
check('Ramp: carved, closed', 'ramp' in msg and non_manifold(cube) == 0, (msg, non_manifold(cube)))
check('... deep at the first edge, half way down in the middle, almost flush at the far side',
      abs(d[0] - 0.19) < 0.02 and abs(d[1] - 0.1) < 0.02 and d[2] < 0.03, d)
check('... outside the shape the top is untouched', depth_at(0.8) == 0.0, depth_at(0.8))
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=2.0)
cube = C.active_object
p.ramp_length = 0.5
bm_.perform_base(C, [SQUARE], TOP, cutter=True)
d = [depth_at(x) for x in (-0.55, -0.3, 0.2)]
check('Ramp Length 0.5: the slope reaches the surface half way across, the far half untouched',
      abs(d[0] - 0.18) < 0.03 and abs(d[1] - 0.1) < 0.03 and d[2] == 0.0, d)
# Ramp Soft
sc = sd.soften_ramp([1.0, 0.5, 0.1, 0.5], [5.0, 5.0, 5.0, 0.2], 1.0)
check('Ramp Soft: eased (smoothstep) along the slope - near the surface it fades in gently, deep end unchanged',
      abs(sc[0] - 1.0) < 1e-9 and abs(sc[1] - 0.5) < 1e-9 and sc[2] < 0.1 * 0.5, sc)
check('... and the sides round off where it is shallow (a point near the outline gets less)', sc[3] < sc[1] * 0.6, sc)
check('Ramp Soft 0 = the straight slope', sd.soften_ramp([0.3, 0.7], [1.0, 1.0], 0.0) == [0.3, 0.7])
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=2.0)
cube = C.active_object
p.ramp_length, p.ramp_soft = 1.0, 1.0
bm_.perform_base(C, [SQUARE], TOP, cutter=True)
d = [depth_at(x) for x in (-0.55, 0.0, 0.35, 0.5)]
check('Soft 1 on the cube: still deep at the first edge, closed, and the far part eases out to the surface',
      abs(d[0] - 0.19) < 0.03 and 0.05 < d[1] < 0.15 and d[2] < 0.03 and d[3] < 0.01 and non_manifold(cube) == 0, d)
# 0.24.46 no thin fins left at the corners on a bevelled edge (the opening goes up toward the viewer)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=1.0, scale=(1.0, 6.0, 0.6))
bar = C.active_object
bpy.ops.object.transform_apply(scale=True)
mod = bar.modifiers.new('b', 'BEVEL')
mod.width, mod.segments = 0.12, 4
bpy.ops.object.modifier_apply(modifier='b')
probe = [(x, y) for x in (-0.405, 0.405) for y in (2.9, 2.94, 2.97)]          # just inside the corners, on the bevel
C.view_layer.update()
before = [S.ray_cast(C.evaluated_depsgraph_get(), Vector((x, y, 5)), Vector((0, 0, -1)))[1].z for x, y in probe]
p.carve_depth, p.ramp_length, p.ramp_soft = 0.15, 1.0, 0.5
bm_.perform_base(C, [[(458, 798), (542, 798), (542, 500), (458, 500)]], TOP, cutter=True)
C.view_layer.update()
after = [S.ray_cast(C.evaluated_depsgraph_get(), Vector((x, y, 5)), Vector((0, 0, -1)))[1].z for x, y in probe]
check('Ramp over a bevelled end: the corners are carved too (no fin of the old surface left), closed',
      all(b - a > 0.08 for a, b in zip(after, before)) and non_manifold(bar) == 0,
      [round(b - a, 3) for a, b in zip(after, before)])
p.alt_mode, p.ramp_length, p.ramp_soft = 'HEIGHT', 1.0, 0.5
summary()
