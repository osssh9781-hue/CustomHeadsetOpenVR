"""Panel Cloth Tension / Gravity sliders on the baked cloth (0.24.4: a change only marks the cloth, Refresh bakes
it again); the new cloth keeps the values; a preset redo resets Gravity to the preset."""
import sys

_src = open(__file__.replace('test_v02328.py', 'test_v0200.py')).read()
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
S.mch_wrinkle.sim_preset = 'CLOTH'
r, m = lasso([(330, 330), (670, 330), (670, 670), (330, 670)])
pc = C.active_object
check('cloth made with the sliders on it', cs.is_pcloth(pc) and abs(pc.mch_pcloth_tension - 1.0) < 1e-6 and
      abs(pc.mch_pcloth_gravity - cs.preset_values('CLOTH')['gravity']) < 1e-6, m)
check('setting the values on a new cloth did not queue a bake', not cs._PENDING)


def zspan(ob):
    co = np.array([v.co[:] for v in ob.data.vertices])
    return float(co[:, 2].max() - co[:, 2].min())


z0 = zspan(pc)
name = pc.name
pc.mch_pcloth_tension = 3.0
check('Tension change does not bake by itself, the cloth is marked', C.active_object == pc and
      pc.get(cs.DIRTY_KEY) is True and not bpy.app.timers.is_registered(cs._rebake_timer))
bpy.ops.mch.panel_cloth_refresh()
new = C.active_object
check('baked again: new cloth active, keeps Tension 3', cs.is_pcloth(new) and abs(new.mch_pcloth_tension - 3.0) < 1e-6
      and new.get('mch_pcloth_preset') == 'CLOTH')
mod_vals = cs.sim_values('CLOTH', 3.0, 2.0)
check('Tension 3 = a third of the preset slack, stiffer', abs(mod_vals['shrink'] - cs.preset_values('CLOTH')['shrink'] / 3)
      < 1e-9 and mod_vals['tension'] == 3.0 and mod_vals['gravity'] == 2.0)
z1 = zspan(new)
check('tighter cloth folds less (height span not bigger)', z1 <= z0 + 1e-4, (z0, z1))
check('refreshed cloth is not marked', not new.get(cs.DIRTY_KEY))
new.mch_pcloth_gravity = 4.0
bpy.ops.mch.panel_cloth_refresh()
g = C.active_object
check('Gravity change bakes again and is kept', cs.is_pcloth(g) and abs(g.mch_pcloth_gravity - 4.0) < 1e-6 and
      abs(g.mch_pcloth_tension - 3.0) < 1e-6)
bpy.ops.mch.panel_cloth_redo(preset='SILK')
s = C.active_object
check('preset redo: Gravity back to the preset, Tension kept', abs(s.mch_pcloth_gravity - cs.preset_values('SILK')['gravity'])
      < 1e-6 and abs(s.mch_pcloth_tension - 3.0) < 1e-6)
check('Fast Start is off by default (the usual result)', S.mch_pcloth_fast is False)
S.mch_pcloth_fast = True
for o in list(bpy.data.objects):
    o.select_set(False)
s.select_set(True)
C.view_layer.objects.active = s
bpy.ops.mch.panel_cloth_redo(preset='SILK')
f = C.active_object
check('Fast Start bakes too', cs.is_pcloth(f) and len(f.data.vertices) > 0)
S.mch_pcloth_fast = False
mecha_lab.unregister()
check('unregister removes the slider properties', not hasattr(bpy.types.Object, 'mch_pcloth_tension'))
sys.exit(1 if summary() else 0)
