"""0.24.56 Live last cut: the last plain Cut stays live until the next one - Cut Depth / Depth mode / GN Edge /
Edge Finish sliders (Quick HUD, menu, panel) cut it again from the kept mesh; an edit after it ends it (edits stay);
Preferences: Live Last Cut."""
import inspect
import types

from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce, ramp_edit as re_

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
S.mch_settings.auto_apply = True
cut = S.mch_cut
cut.depth_mode, cut.depth, cut.gn_finish, cut.gn_ramp = 'SURFACE', 0.3, 'NONE', False
SQ = [(440, 440), (440, 560), (560, 560), (560, 440)]


def floor():
    C.view_layer.update()
    hit, loc, _n, _i, _o, _m = S.ray_cast(C.evaluated_depsgraph_get(), Vector((0, 0, 5)), Vector((0, 0, -1)))
    return round(loc.z, 4) if hit else None


bpy.ops.mesh.primitive_cube_add(size=2.0)
cube = C.active_object
fake = types.SimpleNamespace(mode='CUT')
check('Live last cut: a plain Cut on one part (not Split, not two parts, not a ramp)',
      ce.StrokeLogic._live_cut(fake, C, [cube]) and not ce.StrokeLogic._live_cut(fake, C, [cube, cube])
      and not ce.StrokeLogic._live_cut(types.SimpleNamespace(mode='SPLIT'), C, [cube]))
cut.gn_ramp = True
check('... a ramp keeps its own live way', not ce.StrokeLogic._live_cut(fake, C, [cube]))
cut.gn_ramp = False
src = inspect.getsource(ce.StrokeLogic._execute_closed)
check('The drawing tool keeps the cut live (begin before, fingerprint after)', "kind='cutlive'" in src
      and 'ramp_edit.stamp' in src)

# what the tool does
re_.begin(C, cube, [SQ], TOP, kind='cutlive', extra={'inverted': False})
ce.perform_closed(C, 'CUT', [cube], [SQ], TOP, False)
re_.stamp(cube)
check('After the cut: 0.3 deep, live (no ramp UI for it)', abs(floor() - 0.7) < 1e-3
      and re_.live_target(C, re_.ALL_KINDS) == cube and re_.live_target(C) is None, floor())
cut.depth = 0.5
re_.flush()                                   # 0.24.83 (the UI's timer; never inside the property update)
check('Cut Depth slider: the cut is made again 0.5 deep', abs(floor() - 0.5) < 1e-3 and non_manifold(cube) == 0,
      floor())
cut.gn_finish, cut.gn_width = 'CHAMFER', 0.05
re_.flush()
C.view_layer.update()
hit, loc, *_ = S.ray_cast(C.evaluated_depsgraph_get(), Vector((0.6 + 0.025, 0, 5)), Vector((0, 0, -1)))
check('GN Edge on: the same cut chamfered', hit and loc.z < 0.999 and abs(floor() - 0.5) < 1e-3, loc.z)
cut.gn_finish = 'NONE'
re_.flush()
nv = len(cube.data.vertices)
cube.data.vertices[0].co.z += 0.2
moved = cube.data.vertices[0].co.copy()
cut.depth = 0.2
re_.flush()
check('Edit after the cut, then a slider: the edit stays, the cut is no longer live',
      (cube.data.vertices[0].co - moved).length < 1e-6 and re_.live_target(C, re_.ALL_KINDS) is None)
backups = [m for m in bpy.data.meshes if m.name.startswith('MCH_RampBackup_')]
check('... its kept mesh is gone', not backups, [m.name for m in backups])

# preference off
from mecha_lab import workspace_ui as wui
real = wui.pref
wui.pref = lambda k, d=None: False if k == 'live_last_cut' else real(k, d)
check('Preferences: Live Last Cut off', not ce.StrokeLogic._live_cut(fake, C, [cube]))
wui.pref = real
summary()
