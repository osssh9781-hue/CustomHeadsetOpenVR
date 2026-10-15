"""0.23.11: cloth folds cleaned up - the clean 0.23.2 lines from the border are the main folds again,
the asymmetric thin folds became Surface Detail (one slider, off by default), padding pinches its folds in
(Fold In), cloth folds stick out; the fold heights are smoothed after the subdivision (no beads)."""
import math
import sys

_src = open(__file__.replace('test_v02311.py', 'test_v0200.py')).read()
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
names = [x[0] for x in cw.INPUTS]
check('Surface Detail + Fold In inputs, Surface Detail off by default', 'Surface Detail' in names and
      'Fold In' in names and next(x for x in cw.INPUTS if x[0] == 'Surface Detail')[2] == 0.0)
check('HUD sliders for them', {'surf_detail', 'fold_in'} <= {k[0] for k in cw.SLIDERS})
ng = cw.build_group()
check('fold heights smoothed after the subdivision (Blur Attribute)',
      sum(1 for n in ng.nodes if n.bl_idname == 'GeometryNodeBlurAttribute') >= 2)
MODE[0], NATIVE[0] = 'WRINKLE', 'mecha.cloth_wrinkle'
S.mch_settings.mch_active_tool = 'WRINKLE'
made = {}
for k, wt in enumerate(('DENIM', 'PADDING')):
    b = cube('B%d' % k, 4.0, loc=(6.0 * k, 0, 0))
    VIEW[0] = cg.OrthoProjector(Quaternion(), center=Vector((6.0 * k, 0, 0)))
    S.mch_wrinkle.wtype = wt
    last_used.forget('wrinkle')
    r, m = lasso([(330, 330), (670, 330), (680, 660), (320, 670)])
    made[wt] = C.active_object
d = made['DENIM']
check('cloth folds stick out (Fold In 0), padding pinches in (Fold In 1)',
      int(cw.get_input(d, 'Fold In')) == 0 and int(cw.get_input(made['PADDING'], 'Fold In')) == 1)
check('both height fields written: main folds + surface detail',
      d.data.attributes.get(cw.FOLD_H) is not None and d.data.attributes.get(cw.FOLD_D) is not None)


def field(o, name):
    return np.array([x.value for x in o.data.attributes[name].data])


h0 = field(d, cw.FOLD_H)
cw.set_input(d, 'Fold Asymmetry', 0.0)
h1 = field(d, cw.FOLD_H)
dd = field(d, cw.FOLD_D)
cw.set_input(d, 'Fold Asymmetry', 1.0)
check('main folds do not change with Fold Asymmetry (that only shapes the surface detail)',
      np.abs(h0 - h1).max() < 1e-6 and np.abs(field(d, cw.FOLD_D) - dd).max() > 1e-4)


def evz(o):
    dg = C.evaluated_depsgraph_get()
    return np.array([v.co.z for v in o.evaluated_get(dg).data.vertices])


z_off = evz(d)
cw.set_input(d, 'Surface Detail', cw.get_input(d, 'Pinch'))
z_on = evz(d)
check('Surface Detail slider adds the asymmetric folds (whole layer on one slider)', np.abs(z_on - z_off).max() > 1e-4)
cw.set_input(d, 'Surface Detail', 0.0)
p = made['PADDING']
for nm in ('Puff', 'Roll', 'Stitch', 'Pinch 2'):
    cw.set_input(p, nm, 0.0)
cw.set_input(p, 'Fold In', 0)
z_out = evz(p)
cw.set_input(p, 'Fold In', 1)
z_in = evz(p)
check('Fold In: the same folds dig into the surface instead of standing up',
      z_in.min() < z_out.min() - 1e-4 and z_in.max() < z_out.max(), (round(float(z_in.min()), 4), round(float(z_out.min()), 4)))
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
