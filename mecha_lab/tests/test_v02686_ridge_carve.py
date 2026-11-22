"""0.24.291 (user: "릿지는?") Armor Plate Alt with a ridge preset (Center Ridge / Mech Ridge): the ridge plate turned the
other way and carved out - a valley, deepest along the ridge line, rising to the rim; closed; no plate object left."""
import math

from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import armor_plate as ap, core_geometry as cg

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
LOOP = [(500 + 55 * math.cos(a), 500 + 45 * math.sin(a)) for a in (2 * math.pi * k / 48 for k in range(48))]


def depth(x, y):
    r = S.ray_cast(C.evaluated_depsgraph_get(), Vector((x, y, 5)), Vector((0, 0, -1)))
    return 1.0 - r[1].z if r[0] else None


for preset in ('RIDGE', 'MRIDGE'):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    cube = C.active_object
    n0 = len(bpy.data.objects)
    nme = len(bpy.data.meshes)
    msg = ap.perform_plate_carve(C, [LOOP], TOP, preset)
    C.view_layer.update()
    d0 = depth(0, 0)
    side = [d for d in (depth(0.38, 0.0), depth(-0.38, 0.0)) if d is not None]     # across the ridge line (N-S)
    check(f'{preset}: carved, closed, no plate object / mesh left', 'carved' in msg and non_manifold(cube) == 0
          and len(bpy.data.objects) == n0 and len(bpy.data.meshes) == nme, (msg, non_manifold(cube),
                                                                             len(bpy.data.objects), len(bpy.data.meshes)))
    check(f'{preset}: a valley - the middle deeper than the sides across the ridge', d0 is not None and d0 > 0.01
          and side and min(d0 - d for d in side) > d0 * 0.1, (d0, side))
    far = depth(0.85, 0.85)
    check(f'{preset}: outside the drawn shape the top is untouched', far is not None and abs(far) < 1e-5, far)
S.mch_plate.carve_depth = 0.03
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=2.0)
cube = C.active_object
ap.perform_plate_carve(C, [LOOP], TOP, 'RIDGE')
C.view_layer.update()
check('RIDGE with Carve Depth 0.03: the valley is 0.03 deep', abs(depth(0, 0) - 0.03) < 0.006
      and non_manifold(cube) == 0, depth(0, 0))
S.mch_plate.carve_depth = 0.0

# (user: "표면 따라서 들어가야지 왜 한쪽이 깊게 들어가?") on a slanted face the recess is as deep at both ends
from mathutils import Matrix
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=2.0)
cube = C.active_object
cube.rotation_euler = (math.radians(30), 0, 0)
C.view_layer.update()
nrm = (cube.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
along = (cube.matrix_world.to_3x3() @ Vector((0, 1, 0))).normalized()
top = cube.matrix_world @ Vector((0, 0, 1))
LOOPS = [(500 + 100 * top.x + 30 * math.cos(a), 500 + 100 * top.y + 30 * math.sin(a))
         for a in (2 * math.pi * k / 48 for k in range(48))]
msg = ap.perform_plate_carve(C, [LOOPS], TOP, 'CHAMFER')
C.view_layer.update()


def ndepth(t):
    o = top + along * t + nrm * 1.0
    r = S.ray_cast(C.evaluated_depsgraph_get(), o, -nrm)
    return (r[1] - o).length - 1.0 if r[0] else None


ds = [ndepth(t) for t in (-0.12, 0.0, 0.12)]
check('slanted face (30 deg): the recess follows the surface - as deep at the high end as at the low end',
      None not in ds and min(ds) > 0.005 and max(ds) - min(ds) < max(ds) * 0.2 and non_manifold(cube) == 0,
      (ds, msg))
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=2.0)
cube = C.active_object
cube.rotation_euler = (math.radians(30), 0, 0)
C.view_layer.update()
S.mch_plate.carve_floor = 'FLAT'
ap.perform_plate_carve(C, [LOOPS], TOP, 'CHAMFER')
C.view_layer.update()
S.mch_plate.carve_floor = 'FOLLOW'
fl = [ndepth(t) for t in (-0.12, 0.0, 0.12)]
check('Alt Carve Floor Flat (the old way): uneven on the slanted face; the Cut tool floor setting untouched',
      None not in fl and max(fl) - min(fl) > max(fl) * 0.3 and S.mch_cut.depth_floor == 'FLAT', fl)
from mecha_lab import top_bar
src = open(top_bar.__file__).read()
check('the Armor Plate tool box has Alt Carve: Follow / Level / Flat + Depth',
      "('Alt Carve', _enum_segs(pst, 'carve_floor'" in src and "prop='carve_depth'" in src
      and S.mch_plate.bl_rna.properties['carve_floor'].default == 'FOLLOW')
summary()
