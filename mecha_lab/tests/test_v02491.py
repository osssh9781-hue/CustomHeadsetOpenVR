"""0.24.59 Remesh in ZBrush numbers: say how many points (vertices) the result gets, the voxel size is worked out
from the mesh's surface; Half / Same / Double from the active mesh; Active / Total Points Count like ZBrush."""
import inspect

from _harness import bpy, check, cube, fresh, select_only, summary

import mecha_lab
from mecha_lab import layers_panel as lp, ui_tool_settings as uts

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
s = S.mch_settings
check('Remesh by Points is the default (ZBrush point count), Voxel Size the other way',
      s.remesh_by == 'POINTS' and s.target_points > 0 and 'VOXEL' in {i.identifier for i in
                                                                          s.bl_rna.properties['remesh_by'].enum_items})
results = []
for name, maker in (('sphere', lambda: bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=48, ring_count=24)),
                    ('cube', lambda: bpy.ops.mesh.primitive_cube_add(size=2.0)),
                    ('long', lambda: (bpy.ops.mesh.primitive_cylinder_add(radius=0.3, depth=6.0),))):
    for target in (8000, 30000):
        fresh()
        s = C.scene.mch_settings
        maker()
        ob = C.active_object
        select_only(ob)
        s.remesh_by, s.target_points, s.apply_remesh, s.join_remesh = 'POINTS', target, True, False
        s.smooth_iterations = 0
        bpy.ops.mch.one_click_remesh()
        got = len(C.active_object.data.vertices)
        results.append((name, target, got))
check('Voxel remesh lands near the asked point count (sphere / cube / long cylinder, 8,000 and 30,000: within 15 %)',
      all(abs(g - t) / t < 0.15 for _n, t, g in results), results)
fresh()
s = C.scene.mch_settings
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32)
ob = C.active_object
select_only(ob)
act, tot = mecha_lab.point_counts(C)
check('Active / Total Points Count (as shown, modifiers included)', act == len(ob.data.vertices) and tot >= act,
      (act, tot))
bpy.ops.mch.remesh_points(factor=0.5)
half = s.target_points
bpy.ops.mch.remesh_points(factor=2.0)
check('Half / Double from the active mesh (like ZRemesher)', half == round(act / 2) and s.target_points == act * 2,
      (half, s.target_points))
src = inspect.getsource(uts.draw_remesh)
check("The Remesh panel: Points / Voxel Size, Target Points, Half / Same / Double, 'Now N points -> about M'",
      "'remesh_by'" in src and "'target_points'" in src and 'mch.remesh_points' in src and 'Now' in src)
check('The Layers panel shows Active / Total Points', 'Active Points' in inspect.getsource(lp.content))
from mecha_lab import quick_hud as qh
s.target_points = 20000
check('Big numbers with a thousands comma (20,000)', qh.value_text(s, 'target_points').endswith('20,000'))
v = qh.drag_value(s, 'target_points', 20000, 100.0, px=200.0)
check('A points bar drags in big steps (not one point per 4 px)', v - 20000 > 10000, v)
summary()
