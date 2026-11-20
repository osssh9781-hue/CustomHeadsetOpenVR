"""0.24.265 (user: "렌더 탭에다가 이거 넣어 줘" - Camera to View, Format, Color Management, camera Type / Focal Length,
Depth of Field): the Render page shows the scene's / camera's own settings."""
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import side_panel as sp  # noqa: E402

mecha_lab.register(); fresh()
C = bpy.context
S = C.scene
for o in list(S.objects):
    if o.type == 'CAMERA':
        bpy.data.objects.remove(o)
for k in ('r_dof', 'r_colour'):
    sp.OPENED.add(f'MATERIAL:{k}')
C.window_manager.mch_side_page = 'HDRI'


def labels():
    items, _h = sp.content(C, 'CUT', 0, 300, 1.0)
    return [getattr(i, 'label', '') or '' for i in items], items


L, _ = labels()
check('no camera: "No scene camera" + Add Camera from View, Camera to View there',
      'Add Camera from View' in L and 'Camera to View' in L and 'No scene camera' in ' '.join(L))
bpy.ops.mch.render_add_camera()
cam = S.camera
check('Add Camera from View: the scene camera', cam is not None and cam.type == 'CAMERA')
L, items = labels()
want = ['Type', 'Focal Length', 'Lens Unit', 'Resolution X', '%', 'Aspect X', 'Render Region', 'Display', 'View', 'Look',
        'Exposure', 'Gamma', 'Curves', 'Depth of Field', 'F-Stop', 'Blades', 'Rotation', 'Ratio', 'Focus Distance']
miss = [w for w in want if w not in L]
check(f'the rows: camera Type / Focal Length, Format, Color Management, Depth of Field (missing {miss})', not miss)
by = {getattr(i, 'label', ''): i for i in items}
from mecha_lab import live_ref
d = live_ref.resolve(by['Focal Length'].ref)
check('Focal Length is the camera\'s own lens', d is not None and d == cam.data and by['Focal Length'].prop == 'lens')
check('Resolution is the scene\'s own', live_ref.resolve(by['Resolution X'].ref) == S.render)
bpy.ops.mesh.primitive_cube_add(); cube = C.active_object
bpy.ops.mch.render_dof_focus()
check('Focus on Active Object: the camera focuses the cube', cam.data.dof.focus_object is cube)
bpy.ops.mch.render_dof_focus()
check('... again: back to Focus Distance', cam.data.dof.focus_object is None)
S.view_settings.use_curve_mapping = True
S.view_settings.curve_mapping.black_level = (0.2, 0.2, 0.2)
L, _ = labels()
check('Curves on: Black / White Level + Reset', 'Black Level' in L and 'White Level' in L and 'Reset Curves' in L)
bpy.ops.mch.render_curves_reset()
check('Reset Curves: levels back', tuple(S.view_settings.curve_mapping.black_level) == (0, 0, 0))
cam.data.type = 'ORTHO'
L, _ = labels()
check('Orthographic: Orthographic Scale instead of Focal Length', 'Orthographic Scale' in L and 'Focal Length' not in L)
summary()
