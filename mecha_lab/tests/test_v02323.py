"""0.23.23 Overall Scale also in the sidebar (same value as the HUD slider); the HUD makes any missing slider handle."""
import sys
import types

_src = open(__file__.replace('test_v02323.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
from mecha_lab import cloth_wrinkle as cw, last_used
last_used.forget('wrinkle')
MODE[0], NATIVE[0] = 'WRINKLE', 'mecha.cloth_wrinkle'
S.mch_settings.mch_active_tool = 'WRINKLE'
b = cube('B', 4.0)
r, m = lasso([(330, 330), (670, 330), (680, 660), (320, 670)])
o = C.active_object
p0 = float(cw.get_input(o, 'Pinch Length'))
o.mch_cloth_scale = 150
check('sidebar Overall Scale 150 %: lengths x1.5, the HUD slider shows 150 %',
      abs(float(cw.get_input(o, 'Pinch Length')) - 1.5 * p0) < 1e-6 * max(1, p0) and cw.slider_spec(C, 'all_scale', o)[1] == 150)
cw.slider_spec(C, 'all_scale', o)[4](100)
check('HUD slider back to 100 %: the sidebar shows 100 %, lengths back', o.mch_cloth_scale == 100 and
      abs(float(cw.get_input(o, 'Pinch Length')) - p0) < 1e-6 * max(1, p0),
      (o.mch_cloth_scale, o.get('mch_cloth_scale'), o.get('mch_all_scale'), float(cw.get_input(o, 'Pinch Length')), p0))
# a HUD that was set up before an update (no Overall Scale handle) gets the handle on its next draw
made = []


class FakeGizmos:
    def new(self, idname):
        g = types.SimpleNamespace()
        made.append(g)
        return g


hud = types.SimpleNamespace(gizmos=FakeGizmos(), items={'slider_' + k: object() for k, *_r in cw.SLIDERS if k != 'all_scale'})
cw.MCH_GGT_wrinkle_hud._ensure_sliders(hud)
check('a stale HUD gets the missing Overall Scale handle', 'slider_all_scale' in hud.items and len(made) == 1 and
      made[0].key == 'all_scale')
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
