"""0.24.46 Cut > GN Edge > Ramp: a closed Cut carved on a slope - deepest (Cut Depth) at the first side drawn,
rising back to the surface (Ramp Length / Ramp Soft); GN Edge Chamfer / Bevel shape the deep wall; stays live
(< > / Pick Edge, Cut Depth re-carves, Apply / Remove)."""
import inspect

from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce, ramp_edit as re_, ui_tool_settings as uts

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
S.mch_settings.auto_apply = True
cut = S.mch_cut
check('Ramp is in the GN Edge menu of the Cut panel, Off by default', not cut.gn_ramp
      and 'gn_ramp' in inspect.getsource(uts.draw_gn_edge))
SQUARE = [(440, 440), (440, 560), (560, 560), (560, 440)]     # sides: left, top, right, bottom


def depth_at(x, y):
    C.view_layer.update()
    hit, loc, _n, _i, _o, _m = S.ray_cast(C.evaluated_depsgraph_get(), Vector((x, y, 5)), Vector((0, 0, -1)))
    return round(1.0 - loc.z, 3) if hit else None


cut.depth_mode, cut.depth = 'SURFACE', 0.2
cut.gn_ramp, cut.gn_finish, cut.gn_ramp_length, cut.gn_ramp_soft = True, 'NONE', 1.0, 0.0
bpy.ops.mesh.primitive_cube_add(size=2.0)
cube = C.active_object
n0 = len(cube.data.vertices)
msg = ce.perform_closed(C, 'CUT', [cube], [SQUARE], TOP, False)
check('Cut with Ramp: a slope, deep at the first side (left), up to the surface at the far side, closed',
      'Ramp' in msg and depth_at(-0.55, 0) > 0.15 and abs(depth_at(0, 0) - 0.1) < 0.03 and depth_at(0.5, 0) < 0.03
      and non_manifold(cube) == 0, (msg, depth_at(-0.55, 0), depth_at(0, 0), depth_at(0.5, 0)))
check('... it stays live (a Cut ramp)', re_.live_target(C) == cube and re_.record(cube)['kind'] == 'cut')
bpy.ops.mch.ramp_side(step=2)
check('> > : the right side is deep now', depth_at(0.55, 0) > 0.15 and depth_at(-0.5, 0) < 0.03,
      (depth_at(0.55, 0), depth_at(-0.5, 0)))
cut.depth = 0.1
re_.flush()                                   # 0.24.83 (the UI's timer)
check('Cut Depth slider: carved again at once', abs(depth_at(0.55, 0) - 0.095) < 0.02, depth_at(0.55, 0))
bpy.ops.mch.ramp_remove()
check('Remove: back as it was', len(cube.data.vertices) == n0 and depth_at(0.55, 0) == 0.0 and re_.record(cube) is None)
cut.depth, cut.gn_finish, cut.gn_width = 0.2, 'CHAMFER', 0.05
ce.perform_closed(C, 'CUT', [cube], [SQUARE], TOP, False)
check('GN Edge Chamfer: the deep wall is a chamfer (part way down next to the outline), closed',
      0.01 < depth_at(-0.585, 0) < 0.15 and depth_at(-0.5, 0) > 0.15 and non_manifold(cube) == 0,
      (depth_at(-0.585, 0), depth_at(-0.5, 0)))
bpy.ops.mch.ramp_apply()
check('Apply: kept, nothing live', re_.record(cube) is None and depth_at(-0.5, 0) > 0.15)
cut.gn_ramp = False
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=2.0)
cube = C.active_object
cut.gn_finish = 'NONE'
ce.perform_closed(C, 'CUT', [cube], [SQUARE], TOP, False)
check('Ramp off: the usual flat pocket', abs(depth_at(-0.5, 0) - 0.2) < 0.01 and abs(depth_at(0.5, 0) - 0.2) < 0.01,
      (depth_at(-0.5, 0), depth_at(0.5, 0)))
# 0.24.47 no sawtooth on the softened sides of a long thin ramp: enough rows of points where the sides round off
import math as _m
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=1.0, scale=(3.0, 2.0, 0.4))
plate = C.active_object
bpy.ops.object.transform_apply(scale=True)
cut.depth_mode, cut.depth, cut.gn_ramp, cut.gn_finish, cut.gn_ramp_length, cut.gn_ramp_soft = 'SURFACE', 0.12, True, 'NONE', 1.0, 0.5
ce.perform_closed(C, 'CUT', [plate], [[(380, 420), (420, 420), (640, 600), (600, 600)]], TOP, False)
# walk along the soft side band: the depth must change smoothly (no teeth)
d = (Vector((2.2, 1.8, 0)) / Vector((2.2, 1.8, 0)).length)
side = Vector((-d.y, d.x, 0))
SIDE_OFF = 0.095                    # inside the band where the sides round off
prof = []
for k in range(60):
    p_ = Vector((-1.0, -0.8, 0)) + d * (0.6 + 1.2 * k / 59) + side * SIDE_OFF
    prof.append(depth_at(p_.x, p_.y) or 0.0)
jumps = [abs(prof[i + 1] - 2 * prof[i] + prof[i - 1]) for i in range(1, len(prof) - 1)]
check('a long thin ramp with Ramp Soft: the softened side is smooth along its length (no sawtooth), closed',
      max(jumps) < 0.003 and non_manifold(plate) == 0 and 'gn_ramp_res' in inspect.getsource(uts.draw_gn_edge),
      (round(max(jumps), 4), [round(x, 3) for x in prof[::8]]))
cut.gn_ramp = False
summary()
