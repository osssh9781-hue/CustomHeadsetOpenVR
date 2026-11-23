"""0.24.296 (user: "아머플레이트 알트로 빼낼 때 바닥 쪽에 계단처럼 한 단 더 파이면서 들어가는 것도"): Alt carve Steps -
the floor stepped down again inside (outline moved in by Step Inset, Step Depth deeper)."""
import math

from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import armor_plate as ap, core_geometry as cg, ramp_edit as re_

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
LOOP = [(500 + 60 * math.cos(a), 500 + 60 * math.sin(a)) for a in (2 * math.pi * k / 64 for k in range(64))]


def depth(x, y=0.0):
    C.view_layer.update()
    r = S.ray_cast(C.evaluated_depsgraph_get(), Vector((x, y, 5)), Vector((0, 0, -1)))
    return round(1.0 - r[1].z, 4) if r[0] else None


def fresh_cube():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    return C.active_object


pl = S.mch_plate
pl.preset = 'FLAT'
pl.carve_depth = 0.1
cube = fresh_cube()
pl.carve_steps = 1
pl.step_inset = 0.2
pl.step_depth = 0.08
msg = ap.perform_plate_carve(C, [LOOP], TOP, live=False)
ring, mid = depth(0.5), depth(0.0)
check('Steps 1 (inset 0.2, depth 0.08): the ring near the edge 0.1 deep, the middle 0.18 (one step more), closed',
      abs(ring - 0.1) < 0.005 and abs(mid - 0.18) < 0.005 and non_manifold(cube) == 0 and '1 step more' in msg,
      (ring, mid, msg))
check('... the step starts 0.2 in from the edge (0.6 -> 0.4): 0.38 on the step, 0.42 on the ring',
      abs(depth(0.38) - 0.18) < 0.005 and abs(depth(0.42) - 0.1) < 0.005, (depth(0.38), depth(0.42)))
cube = fresh_cube()
pl.carve_steps = 2
pl.step_inset = 0.15
msg = ap.perform_plate_carve(C, [LOOP], TOP, live=False)
check('Steps 2: three floors 0.1 / 0.18 / 0.26', abs(depth(0.52) - 0.1) < 0.005 and abs(depth(0.37) - 0.18) < 0.005
      and abs(depth(0.0) - 0.26) < 0.005 and non_manifold(cube) == 0, (depth(0.52), depth(0.37), depth(0.0), msg))
cube = fresh_cube()
pl.carve_steps = 5
pl.step_inset = 0.2
msg = ap.perform_plate_carve(C, [LOOP], TOP, live=False)
check('Steps 5 with a 0.2 inset on a 0.6 shape: stops when the shape runs out (2 steps fit), no error',
      '2 steps more' in msg and non_manifold(cube) == 0, msg)
# Auto inset / depth
cube = fresh_cube()
pl.carve_steps = 1
pl.step_inset = 0.0
pl.step_depth = 0.0
ap.perform_plate_carve(C, [LOOP], TOP, live=False)
check('Auto: the step half the carve deeper (0.15 in the middle), the ring 0.1', abs(depth(0.0) - 0.15) < 0.005
      and abs(depth(0.55) - 0.1) < 0.005, (depth(0.0), depth(0.55)))
# live: steps changed after the carve
cube = fresh_cube()
pl.carve_steps = 0
ap.perform_plate_carve(C, [LOOP], TOP)
d0 = depth(0.0)
pl.carve_steps = 1
re_.flush()
check('live: Steps 0 -> 1 after the carve: carved again with the step', abs(d0 - 0.1) < 0.005
      and abs(depth(0.0) - 0.15) < 0.005 and non_manifold(cube) == 0, (d0, depth(0.0)))
pl.carve_steps = 0
re_.flush()
check('... back to 0: one floor again', abs(depth(0.0) - 0.1) < 0.005)
check('Steps default 0 (a plain floor as before)', pl.bl_rna.properties['carve_steps'].default == 0)
pl.carve_depth = 0.0
summary()
