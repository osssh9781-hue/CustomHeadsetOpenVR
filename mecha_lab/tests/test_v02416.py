"""0.24.16 Panel Cloth Puff slider (how much it puffs up): 1 = the preset (identical), 0 = flat, 2 = more;
like Tension / Gravity a change only marks the cloth and Refresh bakes it; the value stays on the new cloth."""
import sys

_src = open(__file__.replace('test_v02416.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
import numpy as np

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
from mecha_lab import cloth_sim as cs, last_used
last_used.forget('wrinkle')
MODE[0], NATIVE[0] = 'WRINKLE', 'mecha.cloth_wrinkle'
S.mch_settings.mch_active_tool = 'WRINKLE'
box = cube('Box', 4.0)
S.mch_wrinkle.sim_after = True
S.mch_wrinkle.sim_preset = 'PADDING'

check('Puff 1 = the preset (no pressure override, same result as before)', 'pressure' not in cs.sim_values('PADDING'))
check('Puff 2 = twice the preset pressure, 0 = none',
      cs.sim_values('PADDING', puff=2.0)['pressure'] == 2 * cs.preset_values('PADDING')['pressure'] and
      cs.sim_values('PADDING', puff=0.0)['pressure'] == 0.0)
check('a preset with no puff (Cloth) gets some added', cs.sim_values('CLOTH', puff=2.0)['pressure'] > 1.0)

r, m = lasso([(330, 330), (670, 330), (670, 670), (330, 670)])
pc = C.active_object
check('new cloth: Puff slider at 1', cs.is_pcloth(pc) and abs(pc.mch_pcloth_puff - 1.0) < 1e-6, m)


def height(ob):
    co = np.array([(ob.matrix_world @ v.co)[2] for v in ob.data.vertices])
    return float(np.percentile(co, 95) - 2.0)


h1 = height(pc)
pc.mch_pcloth_puff = 2.5
check('Puff change only marks the cloth (no bake by itself)', pc.get(cs.DIRTY_KEY) is True and C.active_object == pc)
bpy.ops.mch.panel_cloth_refresh()
p2 = C.active_object
h2 = height(p2)
check('Refresh with Puff 2.5: new cloth keeps 2.5 and puffs higher', abs(p2.mch_pcloth_puff - 2.5) < 1e-6 and h2 > h1 * 1.1,
      (h1, h2))
p2.mch_pcloth_puff = 0.0
bpy.ops.mch.panel_cloth_refresh()
p0 = C.active_object
h0 = height(p0)
check('Puff 0: flatter than the preset', abs(p0.mch_pcloth_puff) < 1e-6 and h0 < h1, (h0, h1))
check('Puff slider drawn in the panel', "'mch_pcloth_puff'" in open(cs.__file__).read())
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
