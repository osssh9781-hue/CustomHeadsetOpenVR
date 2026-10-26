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
summary()
