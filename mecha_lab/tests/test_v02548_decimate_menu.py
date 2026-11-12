"""0.24.143 (user: "우클릭 패널에 데시메이트 버튼도 만들어 줘"): Decimate in the right-click Mecha menu (the Resolution row's
free slot - the card no taller) and in the Blender-style Actions popup; it decimates every selected mesh, keeping the
Mesh Tools %."""
import inspect

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import actions_menu as am, mecha_menu as mm, mesh_tools as mt, ui_gpu  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
res = dict(mm.ACTIONS)['Resolution']
item = next((it for it in res if it[0] == 'Decimate'), None)
check('the Mecha menu: Decimate in the Resolution row (mch.mesh_tool DECIMATE, needs a selected mesh), still 3 rows of 3',
      item is not None and item[2] == 'mch.mesh_tool' and item[3] == {'action': 'DECIMATE'} and item[4] == 'mesh'
      and len(res) <= 9, [it[0] for it in res])
check('its icon is drawn (a "decimate" glyph)', "name == 'decimate'" in inspect.getsource(ui_gpu.glyph))
check('the Blender-style Actions popup has it too', "action='DECIMATE'" in inspect.getsource(am))
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5)
a = C.active_object
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, location=(3, 0, 0))
b = C.active_object
a.select_set(True)
b.select_set(True)
na, nb = len(a.data.polygons), len(b.data.polygons)
S.mch_zb.decimate = 25
desc = mt.MCH_OT_mesh_tool.description(C, type('P', (), {'action': 'DECIMATE'})())
r = bpy.ops.mch.mesh_tool(action='DECIMATE')
check('the button: every selected mesh decimated to about the Mesh Tools % (25 %), the tooltip says so',
      'FINISHED' in r and 0.15 * na < len(a.data.polygons) < 0.35 * na and 0.15 * nb < len(b.data.polygons) < 0.35 * nb
      and 'keep 25%' in desc, (na, len(a.data.polygons), nb, len(b.data.polygons), desc))
summary()
