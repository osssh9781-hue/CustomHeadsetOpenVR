"""0.23.24 no slider list under the Cloth Plate popup (buttons only, values in the sidebar); the N sidebar shows
only the chosen tool's panels (the general extras only in Select)."""
import sys

_src = open(__file__.replace('test_v02324.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
from mecha_lab import cloth_wrinkle as cw, tool_state as ts, robot_base as rb, detail_stamp as ds, highpoly as hp
from mecha_lab import primitive_place as pp, workspace_ui as wui, creature_shell as csh, curve_tube as ct
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
MODE[0], NATIVE[0] = 'WRINKLE', 'mecha.cloth_wrinkle'
S.mch_settings.mch_active_tool = 'WRINKLE'
b = cube('B', 4.0)
r, m = lasso([(330, 330), (670, 330), (680, 660), (320, 670)])
o = C.active_object
lay = cw.hud_layout([(400, 300), (600, 500)], 1600, 900, keys=cw.slider_keys(o))
check('Cloth Plate popup: buttons only, no slider list', cw.slider_keys(o) == () and 'apply' in lay and
      not any(k.startswith('slider_') for k in lay))
check('Overall Scale still in the sidebar (Object property)', hasattr(o, 'mch_cloth_scale'))
S.mch_settings.mch_active_tool = 'BASE'
check('Base Mesh tool: Robot Base Mesh panel shown', rb.MCH_PT_robot_base.poll(C))
for klass in (ds.MCH_PT_detail_stamp, hp.MCH_PT_highpoly, pp.MCH_PT_place_shapes, wui.MCH_PT_icon_size,
              wui.MCH_PT_tools, wui.MCH_PT_workspace):
    check(f'Base Mesh tool: {klass.bl_label} hidden', not klass.poll(C))
S.mch_settings.mch_active_tool = 'CUT'
check('Cut tool: Robot Base Mesh hidden', not rb.MCH_PT_robot_base.poll(C))
check('the general extras follow Select mode', ts.sidebar_select(C) is False)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
