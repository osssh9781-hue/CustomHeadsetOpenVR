"""0.23.12: Center Calm - the folds stay near the border and fade out toward the middle of the panel."""
import math
import sys

_src = open(__file__.replace('test_v02312.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
import numpy as np

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
from mecha_lab import cloth_wrinkle as cw, last_used
last_used.forget('wrinkle')
check('Center Calm input (default 0.8) + HUD slider', next(x for x in cw.INPUTS if x[0] == 'Center Calm')[2] == 0.8
      and 'calm' in {k[0] for k in cw.SLIDERS})
MODE[0], NATIVE[0] = 'WRINKLE', 'mecha.cloth_wrinkle'
S.mch_settings.mch_active_tool = 'WRINKLE'
S.mch_wrinkle.wtype = 'DENIM'
b = cube('B', 4.0)
r, m = lasso([(330, 330), (670, 330), (680, 660), (320, 670)])
o = C.active_object
o.modifiers[cw.MOD_SHELL].show_viewport = False           # measure the cloth surface, not its two sides
for nm in ('Puff', 'Roll', 'Stitch', 'Pinch 2'):
    cw.set_input(o, nm, 0.0)


def center_rough(calm):
    cw.set_input(o, 'Center Calm', calm)
    dg = C.evaluated_depsgraph_get()
    me = o.evaluated_get(dg).data
    co = np.array([v.co[:] for v in me.vertices])
    r_ = np.hypot(co[:, 0], co[:, 1])
    mid = r_ < r_.max() * 0.25
    edge = (r_ > r_.max() * 0.55) & (r_ < r_.max() * 0.8)
    return co[mid, 2].std(), co[edge, 2].std()


m0, e0 = center_rough(0.0)
m1, e1 = center_rough(1.0)
check('Center Calm 1: the middle is much flatter', m1 < m0 * 0.4, (round(float(m0), 5), round(float(m1), 5)))
check('... the folds near the border stay', e1 > e0 * 0.5, (round(float(e0), 5), round(float(e1), 5)))
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
