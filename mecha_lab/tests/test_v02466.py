"""0.24.45 Alt: Ramp stays live: draw the polygon first, pick the deep side after (< > / Pick Edge), Carve Depth /
Ramp Length / Ramp Soft re-carve it at once, Apply keeps it, Remove puts the mesh back."""
from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import base_mesh as bm_, core_geometry as cg, ramp_edit as re_

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)

check('a clicked polygon keeps its corners', re_.corners([(0, 0), (0, 10), (10, 10), (10, 0)]) ==
      [(0, 0), (0, 10), (10, 10), (10, 0)])
dense = [(x, 0) for x in range(0, 100, 2)] + [(100, y) for y in range(0, 100, 2)] + \
        [(x, 100) for x in range(100, 0, -2)] + [(0, y) for y in range(100, 0, -2)]
check('a free-drawn square: simplified to its 4 sides', len(re_.sides(dense)) == 4, len(re_.sides(dense)))
check('the side nearest a point', re_.nearest_side((5, 9), [((0, 0), (0, 10)), ((0, 10), (10, 10)),
                                                          ((10, 10), (10, 0))]) == 1)

p = bm_.scene_defaults(C)
p.sketch, p.profile, p.alt_mode, p.carve_depth, p.ramp_length, p.ramp_soft = False, 'FLAT', 'RAMP', 0.2, 1.0, 0.0
SQUARE = [(440, 440), (440, 560), (560, 560), (560, 440)]     # sides: left, top, right, bottom


def depth_at(x, y):
    C.view_layer.update()
    hit, loc, _n, _i, _o, _m = S.ray_cast(C.evaluated_depsgraph_get(), Vector((x, y, 5)), Vector((0, 0, -1)))
    return round(1.0 - loc.z, 3) if hit else None


bpy.ops.mesh.primitive_cube_add(size=2.0)
cube = C.active_object
n0 = len(cube.data.vertices)
bm_.perform_base(C, [SQUARE], TOP, cutter=True)
rec = re_.record(cube)
check('after Alt: Ramp the ramp is live (the mesh before it is kept)', rec is not None and re_.live_target(C) == cube
      and bpy.data.meshes.get(rec['backup']) is not None and len(rec['corners_w']) == 4)
check('deep side 1 = the first edge (left)', depth_at(-0.55, 0) > 0.15 and depth_at(0.5, 0) < 0.03,
      (depth_at(-0.55, 0), depth_at(0.5, 0)))
bpy.ops.mch.ramp_side(step=1)
check('> : the next side (top) is deep now, the left is not any more', depth_at(0, 0.55) > 0.15
      and depth_at(0, -0.5) < 0.03 and abs(depth_at(-0.55, 0) - 0.1) < 0.03 and non_manifold(cube) == 0,
      (depth_at(0, 0.55), depth_at(0, -0.5), depth_at(-0.55, 0)))
bpy.ops.mch.ramp_side(step=-2)
check('< < : back past the first side to the last one (bottom)', depth_at(0, -0.55) > 0.15, depth_at(0, -0.55))
p.carve_depth = 0.1
check('Carve Depth slider: the live ramp is carved again at once', abs(depth_at(0, -0.55) - 0.095) < 0.02,
      depth_at(0, -0.55))
import inspect
check('the panel shows it (< > / Pick Edge / Apply / Remove)', 'ramp_edit.draw_panel' in inspect.getsource(
      __import__('mecha_lab.ui_tool_settings', fromlist=['x'])._draw_base_sketch) and hasattr(bpy.ops.mch, 'ramp_pick'))
bpy.ops.mch.ramp_remove()
check('Remove: the mesh is back as it was, nothing live left', len(cube.data.vertices) == n0 and depth_at(0, -0.55) == 0.0
      and re_.record(cube) is None and not [m for m in bpy.data.meshes if m.name.startswith('MCH_RampBackup')])
p.carve_depth = 0.2
bm_.perform_base(C, [SQUARE], TOP, cutter=True)
bpy.ops.mch.ramp_side(step=2)
bpy.ops.mch.ramp_apply()
check('Apply: kept with the picked side (right deep), nothing live left',
      depth_at(0.55, 0) > 0.15 and re_.record(cube) is None and re_.live_target(C) is None
      and not [m for m in bpy.data.meshes if m.name.startswith('MCH_RampBackup')], depth_at(0.55, 0))
SMALL = [(470, 470), (470, 530), (530, 530), (530, 470)]
bm_.perform_base(C, [SMALL], TOP, cutter=True)          # a live ramp on the first cube again
live_before = re_.live_target(C) == cube
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(5, 0, 0))
c2 = C.active_object
bm_.perform_base(C, [[(x + 500, y) for x, y in SQUARE]], TOP, cutter=True)
check('a new ramp keeps the earlier live one as it is (one live at a time)', live_before and re_.live_target(C) == c2
      and re_.record(cube) is None and len([m for m in bpy.data.meshes if m.name.startswith('MCH_RampBackup')]) == 1)
p.alt_mode = 'HEIGHT'
summary()
